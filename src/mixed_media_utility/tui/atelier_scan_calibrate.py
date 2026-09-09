# -*- coding: utf-8 -*-
"""`E3-9` -- calibrer une chaine de scan (story 11.6, lot G, AC 8).

L'ecran qui **produit** un profil de chaine, servi depuis le menu de l'atelier
Scan (`EPIC11-ARB-28`) et non par un parcours a part. Son voisin `E3-5`
(`atelier_scan_calibration`) en **choisit** un ; celui-ci en ecrit un.

**Ce module ne redige AUCUNE regle de collision, et c'est son invariant
central** (AC 8.2). La regle vit au coeur, une seule fois, dans
`io.calibration_profile.write_profile` -- et elle n'est pas celle que la fiche
d'epic decrivait. Verbatim du coeur (`io/calibration_profile.py:948-961`) :

> « Il y a donc collision quand le fichier vise porte deja **une autre identite
> de chaine** (ou une identite qu'on ne peut pas lire). Et il n'y en a **pas**
> quand la chaine est la meme : c'est la recalibration [...] que le module
> documente depuis 5.22 comme un remplacement voulu -- poser la question a
> chaque recalibration serait une invite qui apprend a repondre « oui » sans
> lire. »

D'ou les **deux situations** de l'AC 8.1, et la facon dont cet ecran les
distingue -- qui est la seule honnete, parce qu'elle ne suppose rien :

* le coeur dit « collision » en **appelant** `confirmer_l_ecrasement`. C'est le
  seul signal, et il porte l'occupant et le radical vises, verbatim
  (:class:`CollisionDeProfil`). L'ecran ouvre alors un `ChoixExclusif` a
  **trois** issues (`EPIC11-ARB-89` : « toujours au moins deux issues, jamais un
  blocage sec ») ;
* le coeur dit « recalibration » en **ne l'appelant pas** alors qu'il ecrit
  par-dessus un fichier que le releve d'avant-passe portait deja
  (:func:`profils_du_projet`). Aucun radical n'est calcule ici, aucune identite
  de chaine n'est comparee : un **releve de dossier** et le chemin que le coeur
  rend, rien d'autre.

**Les deux questions passent par des RAPPELS, jamais par `stdin`**
(`EPIC7-ARB-106`) : `demander_le_nom_et_le_commentaire` et
`confirmer_l_ecrasement` sont les deux parametres que
`scan_calibrate.calibrer_la_chaine` expose pour ca. Sous une boucle
d'evenements, un appel bloquant sur `stdin` gele l'interface entiere.

**Ce module appelle le coeur, jamais `cli.py`** (`EPIC11-ARB-67`) : le point
d'entree est `scan_calibrate.calibrer_la_chaine`, livre par le lot B de cette
meme story (`EPIC11-ARB-129`).

**Ce que ce module NE fait pas, et c'est structurel :**

* il ne se cable pas lui-meme dans le menu du Scan ni dans le parcours : le
  cablage est le lot H. Les classes sont exposees, elles ne sont pas montees ;
* il n'ecrit **aucun** profil lui-meme : `write_profile` n'est appele nulle part
  ici, et un comptage a zero le mesure (AC 8.2).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping

from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Static

from .. import scan_calibrate, scan_ingest
from ..io import calibration_profile, profile_designation
from . import aide_de_champ, jetons
from .atelier_scan import (INDENT_DU_CURSEUR, INDENT_DU_TEXTE, LIBELLE_DPI,
                           LIBELLE_REPRISE, MENTION_REQUIS, MENTION_REQUIS_DPI,
                           UNITE_DPI, FormulaireDuDepot, SourceDesignee,
                           _cale_a_droite, designer, dpi_lisible, filet,
                           mention_de_la_mesure, source_acceptable)
from .atelier_scan_calibration import (LIBELLE_CHAINE,
                                       SEPARATEUR_DE_CARTE,
                                       date_lisible,
                                       divergence_brute)
from .coque import Palier
from .ecran_projet import CoutureExplorateur, raccourcis_de_l_explorateur
from .explorateur import FAMILLE_MATIERE, Explorateur
from .execution import EcranChiffre, EcranResultat
from .panneau import ChoixExclusif, Issue, LigneChiffree, Panneau

# ===========================================================================
# Le vocabulaire de l'ecran -- une seule redaction, celle-ci
# ===========================================================================

# **Il n'y a PLUS d'`OBJET_DU_BANDEAU` sur cet ecran**, et son retrait est un
# arbitrage d'Egan du 2026-09-01, sur la planche de relecture du temps 2.
#
# La droite du bandeau portait « depuis le menu Scan ». Verbatim d'Egan : « Oui
# mais il y a écrit "depuis le menu scan". On met juste rien à cet endroit... »
# -- **rien**, et non une autre mention : `Palier.bandeau` (la redaction unique
# du bandeau) traite deja le cas d'un ecran sans objet travaille, et un ecran qui
# n'a rien a dire a droite s'y range au lieu d'inventer une glose.
#
# La mention venait d'`EPIC11-ARB-28`, qui avait retire « parcours a part » de
# l'interface et repondait ainsi a la note d'Egan du 2026-08-27 en pied de la
# maquette (« je n'ai pas compris comment on entre dans ce panneau ? »). La
# reponse tient toujours -- `calibrate` EST une entree du menu d'atelier `E3-0`,
# et le bandeau porte deja `Scan · Calibrer` a gauche --, mais elle se lit dans
# la structure et non dans une phrase posee a cote.

#: Le segment de bandeau. **Deux segments et non un** : l'atelier, puis le geste
#: -- c'est ce que la maquette dessine (`mmu · projet_demo · Scan · Calibrer`).
PALIER_DE_L_ECRAN = "Scan · Calibrer"

#: Le titre de l'ecran, verbatim de la maquette (l. 5).
TITRE = "Calibrer une chaîne de scan"

#: Le titre du filet qui separe la saisie de ce qu'elle produira (l. 14).
TITRE_DE_LA_SORTIE = "Ce qui sera écrit"

#: La ligne de raccourcis, verbatim de la maquette (l. 23). **Constante de
#: module**, comme celles des autres ecrans du Scan : c'est ce qui la fait
#: balayer par la garde d'epic du repli ASCII et par celle des majuscules.
#:
#: **Aucune lettre n'y figure** (`EPIC11-ARB-68`) : trois des six lignes de ce
#: formulaire sont des champs de saisie, et « aucune lettre n'est un raccourci
#: dans un champ de saisie, sans exception ».
#: **Le raccourci du choix, et le pied ne le porte que sur SA ligne** (point 3
#: d'Egan : « on ecrit "Espace Oui/non" quand le curseur est sur ce champ »).
#: `Espace` porte sa majuscule comme `Tab` et `Échap` : c'est un nom de touche,
#: et la regle des majuscules du depot porte sur les raccourcis, pas sur les
#: valeurs du formulaire.
#:
#: **`RACCOURCI_` et non `MENTION_`, et le nom n'est pas indifferent** :
#: `test_majuscules_des_raccourcis.py` balaye les constantes `MENTION_*` du
#: paquet et y interdit tout nom de touche -- c'est la sobriete de la LIGNE
#: D'ETAT qu'`EPIC11-ARB-56` impose. Celle-ci vit dans la ligne de RACCOURCIS,
#: ou un nom de touche est precisement ce qu'on attend. La garde a donc eu
#: raison de rougir sur le premier nom, et c'est le nom qui a change, pas la
#: garde : une exception ajoutee a une frontiere pour y faire entrer son propre
#: travail est le debut de son desarmement.
RACCOURCI_ESPACE = "Espace Oui/non"

#: Le suffixe commun aux cinq lignes contextuelles. Ecrit UNE fois : cinq
#: redactions divergeraient au premier ajustement, et c'est le defaut que le
#: finding `F-17` sanctionne.
_QUEUE_CALIBRATE = "↑↓ champ  Échap menu Scan  F1 aide"

#: La ligne de raccourcis, **contextuelle** (`EPIC11-ARB-158`, Egan le
#: 2026-09-01). `DESIGN.md` section 4 : « elle ne montre que ce qui marche sur
#: l'ecran courant » -- et sur ce formulaire, ce qui marche depend de la ligne
#: ou est le curseur.
#:
#: **`Tab` a disparu de la ligne**, et c'est litteral : « d'un champ a l'autre
#: avec les fleches haut-bas **et non avec tab** ». Il reste **fonctionnel**,
#: en synonyme non annonce, parce qu'une touche universelle de formulaire qui
#: cesserait de repondre est une regression pour qui l'a dans les doigts ;
#: l'inverse -- l'annoncer sans qu'elle marche -- serait le defaut `I8`.
#:
#: **Aucune LETTRE n'y figure** (`EPIC11-ARB-68`) : trois des sept lignes de ce
#: formulaire sont des champs de saisie, et « aucune lettre n'est un raccourci
#: dans un champ de saisie, sans exception ». `Espace` n'est pas une lettre, et
#: la bascule ne s'arme que sur la ligne du choix -- une espace frappee dans le
#: commentaire s'y ECRIT.
RACCOURCIS_CALIBRATE = f"{_QUEUE_CALIBRATE}"
RACCOURCIS_SUR_LE_SCAN = f"⏎ désigner le scan  {_QUEUE_CALIBRATE}"
RACCOURCIS_SUR_LA_REPRISE = f"⏎ reprendre la mesure  {_QUEUE_CALIBRATE}"
RACCOURCIS_SUR_LE_CHOIX = f"{RACCOURCI_ESPACE}  {_QUEUE_CALIBRATE}"
RACCOURCIS_SUR_VALIDER = f"⏎ calibrer  {_QUEUE_CALIBRATE}"


#: La ligne de raccourcis des deux points de jugement de cet ecran -- la
#: collision et l'impasse. `Tab` n'y est pas : il n'y a aucun champ a parcourir
#: sur un choix d'issues, et une touche annoncee qui ne fait rien se lit comme
#: une panne (finding `I8`).
RACCOURCIS_DU_CHOIX = "⏎ valider  ↑↓ choisir  Échap retour  F1 aide"

#: Largeur de la colonne des libelles du formulaire. **Mesuree sur la maquette**
#: (le libelle ouvre a la colonne 5 de la zone utile, la valeur a la colonne 26,
#: le glyphe de focus juste avant) : `Reprendre la mesure` est le plus long des
#: huit et tient dedans avec son creux.
LARGEUR_DU_LIBELLE = 21

# ---------------------------------------------------------------------------
# Les six lignes du formulaire, dans l'ordre ou `Tab` les parcourt
# ---------------------------------------------------------------------------

CHAMP_SCAN = "scan"
CHAMP_DPI = "dpi"
CHAMP_REPRISE = "reprise"
CHAMP_ETIQUETTE = "etiquette"
CHAMP_COMMENTAIRE = "commentaire"
CHAMP_DEFAUT = "defaut"
#: La ligne d'action, **en bas du formulaire** (`EPIC11-ARB-158`, point 4 :
#: « il faut qu'il y ait un choix explicite en bas du formulaire : Valider. On
#: y accede en descendant avec les fleches »).
#:
#: C'est une ligne du formulaire et non une issue : elle se parcourt avec les
#: autres, et c'est ce qui la rend ATTEIGNABLE au sens ou Egan l'entend. En
#: faire une liste d'issues separee la mettrait derriere un second geste, ce
#: que le grief -- « la validation avec Entree n'est pas claire » -- vise
#: precisement.
CHAMP_VALIDER = "valider"

#: Les libelles, verbatim de la maquette (l. 7 a 12 et 16 a 18). `LIBELLE_DPI`
#: et `LIBELLE_REPRISE` sont **lus de `E3-1`** et non recopies : les deux ecrans
#: posent la meme question, et deux redactions divergeraient au premier
#: renommage -- l'operateur lirait deux noms pour un seul champ.
LIBELLE_SCAN = "Scan de la page"
LIBELLE_ETIQUETTE = "Nom de la chaîne"
LIBELLE_COMMENTAIRE = "Commentaire"
#: `LIBELLE_CHAINE` (« Chaîne ») est **lu de `E3-5`** et non recopie : les deux
#: ecrans nomment le meme fait, et deux redactions divergeraient au premier
#: renommage. `E3-5` la lit d'un profil pose, `E3-9` la lit du profil qu'il
#: vient d'ecrire -- c'est la meme colonne, et l'operateur passe de l'un a
#: l'autre.
LIBELLE_PROFIL = "Profil"
LIBELLE_REMPLACE = "Remplace"
LIBELLE_DEFAUT = "Devient le défaut"
LIBELLE_VALIDER = "Valider"
#: Ce que la ligne `Valider` porte en valeur. **Un verbe, pas un libelle
#: repete** : la colonne de droite d'un champ dit ce que la ligne FAIT, et
#: « Valider · Valider » ne dirait rien de plus que la colonne de gauche.
ACTION_VALIDER = "lancer la calibration"
#: Ce que la meme ligne porte en mention quand la passe ne peut pas partir.
#: **Le motif est sur la ligne de l'action**, la ou l'operateur regarde au
#: moment ou il appuie -- pas seulement en ligne d'etat.
#:
#: **Sans glyphe, et c'est une frontiere du depot qui l'a impose.** La premiere
#: redaction portait un `▲`. `test_G1_la_recalibration_se_DIT_sans_triangle_et_
#: sans_question` a rougi : une recalibration « se dit sans triangle et sans
#: question », et un `▲` pose sur une AUTRE ligne du meme ecran suffit a rompre
#: cette promesse -- l'operateur voit un avertissement, pas la ligne qui le
#: porte. La colonne de mention de ce formulaire est d'ailleurs en texte nu
#: partout (`requis`, `facultatif`), et c'est la grammaire qu'on suit ici.
MENTION_VALIDER_SANS_DPI = "résolution requise"
#: Et son symetrique, qui manquait. `peut_calibrer` est faux pour **deux**
#: motifs -- pas de scan, ou pas de resolution -- et la ligne n'en nommait
#: qu'un : sur un `E3-9` vierge, elle disait « resolution requise » alors que
#: la resolution n'etait meme pas en cause. Une mention qui nomme le mauvais
#: manque est pire qu'une mention absente, parce qu'elle envoie l'operateur
#: corriger un champ qui va bien (revue de vague B, couche 2).
MENTION_VALIDER_SANS_SCAN = "scan requis"
#: Et le troisieme : une resolution SAISIE que le coeur refuse. « requise » y
#: serait faux -- elle est la, elle ne convient pas.
MENTION_VALIDER_DPI_REFUSE = "résolution hors bornes"


def motif_du_refus_de_partir(formulaire: "FormulaireDeCalibration"
                             ) -> tuple[str, str]:
    """Ce qui manque en premier, pour la mention ET pour la ligne d'etat.

    **Une seule redaction pour les deux surfaces** : la mention de la ligne
    `Valider` et la phrase d'etat disaient le meme fait a deux endroits, et
    seule la premiere a ete corrigee la premiere fois. L'ordre est celui du
    formulaire -- le scan se choisit avant sa resolution --, donc le motif rendu
    est celui du **premier** champ requis encore vide.
    """
    if formulaire.scan is None:
        return MENTION_VALIDER_SANS_SCAN, PHRASE_SCAN_REQUIS
    if not formulaire.saisie(CHAMP_DPI):
        return MENTION_VALIDER_SANS_DPI, PHRASE_DPI_REQUIS
    # **Le troisieme regime, que la premiere redaction ne nommait pas.**
    # `peut_calibrer` est faux pour un dpi PRESENT mais invalide (`abc`, `0`,
    # `999999`) : l'ecran disait alors « resolution requise » avec `999999`
    # ecrit dans le champ, c'est-a-dire son propre defaut retourne -- « une
    # mention qui nomme le mauvais manque envoie l'operateur corriger un champ
    # qui va bien » (revue de reprise, couches 1 et 3).
    return MENTION_VALIDER_DPI_REFUSE, PHRASE_DPI_REFUSE

LIBELLES = {
    CHAMP_SCAN: LIBELLE_SCAN,
    CHAMP_DPI: LIBELLE_DPI,
    CHAMP_REPRISE: LIBELLE_REPRISE,
    CHAMP_ETIQUETTE: LIBELLE_ETIQUETTE,
    CHAMP_COMMENTAIRE: LIBELLE_COMMENTAIRE,
    CHAMP_DEFAUT: LIBELLE_DEFAUT,
    CHAMP_VALIDER: LIBELLE_VALIDER,
}
#: **`F1` sur un champ : ce que ce champ attend** (`EPIC11-ARB-14`, story 11.9
#: lot B). Le mecanisme vient du paquet (`aide_de_champ`) ; ces phrases sont la
#: **donnee de cet ecran**, et elles restent ici.
#:
#: Les **sept** lignes du parcours en portent une -- y compris `Valider`, qui
#: est une ligne du formulaire et non une issue (`EPIC11-ARB-158`, point 4) :
#: une touche annoncee qui se tairait sur une ligne du parcours serait le
#: finding `I8` en plus petit.
#:
#: Chacune dit ce que la ligne attend, sa forme, et une **valeur du contexte
#: courant** (`{valeur}`, remplie par
#: :meth:`EcranCalibrerLaChaine.valeur_de_l_aide`). Le plafond du dpi est **lu
#: du coeur**, comme sur `E3-1` et pour le meme motif.
AIDE_PAR_CHAMP = {
    CHAMP_SCAN: "La page de mire scannée, un fichier ; ici : {valeur}.",
    CHAMP_DPI: (f"Un entier jusqu'à {scan_ingest.MAX_SCAN_DPI}, celui du "
                "scanner ; ici : {valeur}."),
    CHAMP_REPRISE: ("Relit la résolution écrite dans le scan ; "
                    "ici : {valeur}."),
    CHAMP_ETIQUETTE: "Le nom qui retrouvera ce profil ; ici : {valeur}.",
    CHAMP_COMMENTAIRE: "Texte libre gardé dans le profil ; ici : {valeur}.",
    CHAMP_DEFAUT: ("Oui ou non, le profil pris sans le nommer ; "
                   "ici : {valeur}."),
    # **La ligne d'ACTION dit ce que `⏎` FAIT, et `⏎` n'ecrit rien ici**
    # (finding `F-C1-3`, couche 1 de la revue du 2026-09-04). Cette place
    # portait « Écrit le profil de calibration », c'est-a-dire une ecriture
    # **immediate** -- alors que `⏎` sur cette ligne appelle
    # `atelier_scan_parcours.consigner_le_profil`, dont le docstring dit
    # verbatim : « Ce que `Valider` fait : **montrer ce qui va etre fait**, pas
    # ecrire ». L'ecriture arrive apres l'issue `ISSUE_LANCER` **et** apres une
    # passe de plusieurs minutes.
    #
    # L'erreur allait dans le sens dangereux : elle **niait le point d'arret**
    # qu'`EPIC11-ARB-89` exige (« toujours proposer une issue plutot qu'un
    # blocage sec » -- la confirmation EST cette issue). Des trois canaux de la
    # ligne, l'aide etait le seul a mentir : la valeur dit « lancer la
    # calibration », le pied dit « ⏎ calibrer », ni l'un ni l'autre ne promet
    # un fichier ecrit.
    #
    # La phrase nomme donc le point d'arret, avec un mot que la ligne ne montre
    # pas deja -- ni le libelle (`Valider`, qu'`EPIC11-ARB-14` interdit de
    # paraphraser), ni le pied. La frontiere qui l'y tient est dans
    # `tests/unit/tui/test_atelier_scan_calibrate_aide_de_l_action.py` : elle
    # confronte cette phrase a l'ecran que `⏎` atteint REELLEMENT, mesure faite,
    # et non a une phrase recopiee.
    CHAMP_VALIDER: "Récapitule la passe, à confirmer ; ici : {valeur}.",
}

#: Ce que la valeur de contexte dit d'un scan non designe et d'une mesure
#: absente. Des constats, pas des conseils.
#:
#: **Le champ de TEXTE vide, lui, n'est PAS ici** : il dit
#: `aide_de_champ.VALEUR_ABSENTE`, le mot partage. Cette place portait
#: `AIDE_CHAMP_VIDE = "vide"`, si bien que sur ce meme formulaire `dpi`
#: repondait « rien de saisi » quand `etiquette` et `commentaire` repondaient
#: « vide » -- exactement la divergence que le docstring de `VALEUR_ABSENTE`
#: annoncait. Ces deux constantes-ci disent autre chose (un fichier non
#: designe, une mesure jamais faite), et c'est pour cela qu'elles restent.
AIDE_SANS_SCAN = "rien de désigné"
AIDE_SANS_MESURE = "aucune mesure lue"
#: Et de la ligne d'action, quand la passe peut partir. Le cas contraire est
#: **lu de `motif_du_refus_de_partir`**, qui est deja la seule redaction du
#: motif pour la mention et pour la ligne d'etat : une troisieme diverge.
AIDE_PRET_A_PARTIR = "prêt à partir"

#: Quelle ligne de pied pour quelle ligne du formulaire. Les champs absents de
#: la table -- les trois champs de saisie -- prennent `RACCOURCIS_CALIBRATE`,
#: qui n'annonce pas `⏎` : il y **descend**, et annoncer une touche pour dire
#: qu'elle fait la meme chose que la fleche du dessous serait du bruit.
PIED_PAR_CHAMP = {
    CHAMP_SCAN: RACCOURCIS_SUR_LE_SCAN,
    CHAMP_REPRISE: RACCOURCIS_SUR_LA_REPRISE,
    CHAMP_DEFAUT: RACCOURCIS_SUR_LE_CHOIX,
    CHAMP_VALIDER: RACCOURCIS_SUR_VALIDER,
}

#: Les trois champs ou une frappe imprimable s'ecrit. Les trois autres lignes
#: sont un chemin (l'explorateur le pose), une reprise (`⏎` la valide) et un
#: choix de formulaire (`⏎` le bascule) : y ecrire une lettre n'aurait pas de
#: sens, et la frappe y est **consommee** plutot que remontee au binding
#: applicatif `q` -- une meme touche qui quitterait ici et saisirait deux lignes
#: plus haut serait pire qu'inerte.
CHAMPS_DE_SAISIE = (CHAMP_DPI, CHAMP_ETIQUETTE, CHAMP_COMMENTAIRE)

#: Ce que la ligne d'etat dit quand le scan est la et la resolution non,
#: **verbatim de la maquette** (l. 22). Une mesure de l'ecran courant, sans
#: touche, sans conseil et sans motif de conception (`EPIC11-ARB-56`).
PHRASE_DPI_REQUIS = "résolution de scan requise — la calibration ne peut pas partir"
#: Le symetrique, meme motif que `MENTION_VALIDER_SANS_SCAN`.
PHRASE_SCAN_REQUIS = "scan requis — la calibration ne peut pas partir"
#: Et celui du troisieme regime.
PHRASE_DPI_REFUSE = (
    "résolution de scan hors bornes — la calibration ne peut pas partir")

#: Ce que la colonne de droite dit du champ d'etiquette laisse vide. **Un fait
#: sur ce qui sera ecrit, pas un conseil** : sans etiquette, le coeur nomme le
#: fichier par l'identite qu'il derive du scan (`write_profile` : « le
#: `chain_id` du document sinon »), et c'est exactement le regime de la story
#: 5.22. La ligne le dit parce que c'est le seul moment ou l'operateur peut en
#: decider.
MENTION_ETIQUETTE_VIDE = "à défaut, l'identité dérivée du scan"

#: Ce que la colonne de droite dit du commentaire. Il ne nomme rien -- il ne
#: sert qu'a se relire au survol (`write_profile`, AC 8quater de 5.23) --, donc
#: il n'est **pas** requis, et le dire evite qu'un champ vide se lise comme un
#: manque.
MENTION_COMMENTAIRE = "facultatif"

#: Les deux moities du choix de formulaire « Devient le défaut » (l. 18).
#: **Ce n'est PAS une liste d'issues** : `EPIC11-ARB-126` (« Flèche seule ! »)
#: borne sa regle aux listes ou l'on choisit une **issue**, et `DESIGN.md`
#: section 7.3 pose `(•) 16 bits ( ) 8 bits` comme la forme d'un **champ**.
#: L'AC 8.6 le dit nommement pour qu'une revue ne le corrige pas a tort.
CHOIX_OUI = "oui"
CHOIX_NON = "non"

#: Le creux entre les deux moities du choix, mesure sur la maquette (l. 18 :
#: `( ) oui    (•) non`).
CREUX_DU_CHOIX = 4


def _surligne(libelle: str, retenu: bool) -> str:
    """L'option retenue d'un choix, mise en avant. `EPIC11-ARB-158`.

    **Le surlignage passe par la CASSE, et c'est un choix assume plutot qu'un
    defaut de moyens.** `jetons.peindre` colore des LIGNES ENTIERES : un
    surlignage de sous-chaine demanderait de lui ajouter un mecanisme, partage
    par tous les ecrans du produit, pour un quart d'un retour d'usage. Et la
    couleur seule ne porterait rien -- `DESIGN.md` section 5 l'interdit
    explicitement.

    Ce que la casse donne et qu'une peinture ne donnerait pas : elle tient la
    grille a l'identique (meme nombre de colonnes), elle survit au repli ASCII
    sans table, et elle se **mesure** dans un banc sans monter de terminal.

    **La limite, dite plutot que tue** : la regle du depot veut les RACCOURCIS
    en majuscules, et une valeur en majuscules pourrait a la relecture se lire
    comme un raccourci. Le risque est borne ici -- le corps du formulaire ne
    porte aucun raccourci, et la seule ligne qui en porte est le pied.
    """
    return libelle.upper() if retenu else libelle

#: Ce que la ligne `Profil` porte tant que le coeur n'a rien ecrit. **Le chemin
#: ne se devine pas** : il depend du radical, que `write_profile` compose seul
#: (`profile_file_stem`), et le recomposer ici serait la seconde redaction que
#: l'AC 8.2 ferme. `DESIGN.md` section 3 : ce qu'on ne sait pas ne s'affiche pas
#: comme une valeur.
PROFIL_PAS_ENCORE_ECRIT = "sera nommé par le cœur, à l'écriture"

#: Ce que la ligne `Remplace` dit d'une recalibration (AC 8.1, premiere
#: situation) : **un fait, sans `▲` et sans question**. Poser la question a
#: chaque recalibration serait « une invite qui apprend a repondre oui sans
#: lire » (`EPIC5-ARB-99`), donc l'inverse de ce que l'arbitrage cherche.
PHRASE_RECALIBRATION = "la passe du {date} — même chaîne"

#: Ce que la ligne `Remplace` dit quand rien n'est remplace. Le profil est neuf,
#: et le dire vaut mieux qu'une ligne absente : l'operateur verifie du coin de
#: l'oeil qu'il n'ecrase rien.
PHRASE_PROFIL_NEUF = "rien — ce profil est nouveau dans ce projet"

#: La mesure que la ligne d'etat porte apres une recalibration (AC 8.1) :
#: **l'ancienne date et la nouvelle**, deux mesures, aucun avertissement.
ETAT_RECALIBRATION = "profil posé le {ancienne} · remplacé le {nouvelle}"

#: La mesure que la ligne d'etat porte apres une ecriture qui ne remplace rien.
ETAT_PROFIL_ECRIT = "profil écrit le {date} · {chemin}"

#: Ce que la ligne d'etat des deux points de jugement porte : **une mesure** --
#: combien d'issues, et combien ecrivent (`EPIC11-ARB-56`). Le compte de celles
#: qui ecrivent est le fait qui compte a un point de decision, et c'est ce
#: qu'`EPIC11-ARB-89` demande qu'on puisse verifier d'un coup d'oeil.
#:
#: **Trois formes et non un pluriel pose sans condition** : le cas a un et le
#: cas a zero sont les seuls ou la faute d'accord se voie, et une fabrique les
#: porte tous les deux -- meme geste qu'`atelier_scan.mention_de_la_mesure`.
ETAT_DU_CHOIX = "{issues} issues · {ecrivent} écrivent"
ETAT_DU_CHOIX_UNE = "{issues} issues · 1 écrit"
ETAT_DU_CHOIX_AUCUNE = "{issues} issues · aucune n'écrit"


def etat_du_choix(choix: "ChoixExclusif") -> str:
    """« 3 issues · 1 écrit ». Voir :data:`ETAT_DU_CHOIX`."""
    ecrivent = sum(1 for issue in choix.issues if issue.ecrit)
    if ecrivent == 0:
        modele = ETAT_DU_CHOIX_AUCUNE
    elif ecrivent == 1:
        modele = ETAT_DU_CHOIX_UNE
    else:
        modele = ETAT_DU_CHOIX
    return modele.format(issues=len(choix.issues), ecrivent=ecrivent)

# ---------------------------------------------------------------------------
# Les deux zones de l'ecran
# ---------------------------------------------------------------------------

#: La zone du formulaire, et celle de l'explorateur monte par-dessus le champ
#: de scan (**sixieme site** d'`EPIC11-ARB-48`, ecart `H11`).
ZONE_FORMULAIRE = "formulaire"
ZONE_EXPLORATEUR = "explorateur"


# ===========================================================================
# La collision -- ce que le COEUR en dit, et rien de plus
# ===========================================================================

@dataclass(frozen=True)
class CollisionDeProfil:
    """Ce que `confirm_overwrite` recoit du coeur, **verbatim**.

    Les deux champs sont ceux que `calibration_profile.write_profile` passe a
    son rappel : `(document_existant, radical)`. Ils ne sont ni recalcules, ni
    reformules, ni completes ici -- l'ecran les **relaie**.

    `occupant` vaut `None` quand le fichier vise porte une identite que le coeur
    n'a pas pu lire (fichier tronque, non-UTF-8). C'est un cas distinct de
    « une autre chaine », et les confondre ferait annoncer une chaine qui
    n'existe pas.
    """

    occupant: str | None
    radical: str


#: Les trois issues de la vraie collision (AC 8.1, seconde situation).
CLE_NOM_DIFFERENCIE = "nom-differencie"
CLE_ECRASER = "ecraser"
CLE_ANNULER = "annuler"

#: Les libelles des trois issues. Le premier est **le defaut du coeur** --
#: « Hors terminal, le defaut est l'empreinte, jamais l'ecrasement »
#: (`EPIC5-ARB-99`) --, et c'est celui que le curseur vise au montage.
LIBELLE_NOM_DIFFERENCIE = "Écrire sous un nom différencié"
LIBELLE_ECRASER_CHAINE = "Écraser le profil de la chaîne {occupant}"
LIBELLE_ECRASER_ILLISIBLE = "Écraser le profil illisible qui porte ce nom"
LIBELLE_ANNULER = "Annuler, ne rien écrire"

#: Le titre du point de jugement de la collision, et sa phrase de cartouche.
#: **Le radical et l'occupant voyagent verbatim** (`EPIC11-ARB-30`).
TITRE_DE_LA_COLLISION = "Un autre profil porte déjà ce nom"
PHRASE_DE_LA_COLLISION = (
    "« {radical} » porte déjà la chaîne {occupant}, et non celle qui vient "
    "d'être mesurée.")
PHRASE_DE_LA_COLLISION_ILLISIBLE = (
    "« {radical} » existe déjà et son identité de chaîne n'a pas pu être lue.")


def libelle_de_l_ecrasement(collision: CollisionDeProfil) -> str:
    """« Écraser le profil de la chaîne X », ou son cas illisible.

    L'occupant est **nomme** quand le coeur a su le lire : une issue qui ecrase
    doit dire ce qu'elle ecrase, sans quoi le consentement d'`EPIC11-ARB-89`
    (« une ecriture destructive CONSCIENTE ») porte sur rien.
    """
    if not collision.occupant:
        return LIBELLE_ECRASER_ILLISIBLE
    return LIBELLE_ECRASER_CHAINE.format(occupant=collision.occupant)


def issues_de_la_collision(collision: CollisionDeProfil) -> list[Issue]:
    """Les **trois** issues de l'AC 8.1, dans l'ordre ou l'ecran les pose.

    **Pourquoi « nom differencie » ne porte PAS `ecrit=True`.** Dans ce depot,
    `Issue.ecrit` marque l'issue dont la validation **detruit** quelque chose :
    c'est l'usage de `execution.EcranInterruption`, dont la seule issue `ecrit`
    est « effacer ce qui est deja ecrit », les deux autres ecrivant elles aussi.
    L'AC 8.1 n'annote qu'une seule des trois -- *ecraser le profil existant*
    (`ecrit=True`) -- et exige que « le curseur part sur celle qui n'ecrase
    pas ». Marquer l'empreinte differenciante ferait partir le curseur sur
    « Annuler », c'est-a-dire l'inverse de ce que l'AC demande.

    **Aucune n'est preselectionnee** : c'est `ChoixExclusif.__post_init__` qui
    le leve, et cet invariant n'est pas reecrit ici.
    """
    return [
        Issue(CLE_NOM_DIFFERENCIE, LIBELLE_NOM_DIFFERENCIE),
        Issue(CLE_ECRASER, libelle_de_l_ecrasement(collision), ecrit=True),
        Issue(CLE_ANNULER, LIBELLE_ANNULER),
    ]


def choix_de_la_collision(collision: CollisionDeProfil) -> ChoixExclusif:
    """Le point de jugement de la collision. Le curseur part sur l'empreinte."""
    return ChoixExclusif(issues_de_la_collision(collision))


#: Ce que la reponse de chaque issue vaut pour `confirm_overwrite`. **Une table
#: et non un `if`** : c'est le seul endroit qui traduit une issue en booleen, et
#: `None` y dit « ne rien ecrire », qui n'est pas un booleen.
REPONSE_DES_ISSUES: Mapping[str, bool | None] = {
    CLE_NOM_DIFFERENCIE: False,
    CLE_ECRASER: True,
    CLE_ANNULER: None,
}


class CalibrationAnnulee(Exception):
    """L'operateur a retenu « Annuler » devant la collision : rien n'est ecrit.

    Elle traverse `write_profile` **avant** le `mkdir` et l'ecriture atomique --
    c'est l'ordre du corps du coeur, et c'est ce qui fait de cette issue un
    vrai refus : « un refus qui arrive apres une destruction n'est pas un
    refus » (`EPIC5-ARB-34`).
    """


class RelaisDeCollision:
    """Le `confirm_overwrite` de la TUI : il **pose** la question, il ne tranche pas.

    C'est l'unique chemin par lequel l'ecrasement conscient d'`EPIC11-ARB-89`
    est atteignable (AC 8.2), et il n'y a **aucune** regle de collision de ce
    cote : le relais n'est appele que si le coeur a decide qu'il y a collision,
    et il rend ce que l'operateur a repondu.

    `poser` est **requis et sans defaut** : c'est le finding `K3`, paye quatre
    fois dans cet epic -- « un `Callable | None = None` assorti d'un
    `if ... is not None` fait de l'oubli de cablage un silence ». Un relais sans
    question repondrait a la place de l'operateur, ce qui est exactement
    l'ecrasement silencieux qu'`ARB-89` interdit.

    :param poser: appele avec la :class:`CollisionDeProfil`, il rend la cle de
        l'issue retenue (:data:`REPONSE_DES_ISSUES`).
    """

    def __init__(self, poser: Callable[[CollisionDeProfil], str]) -> None:
        self._poser = poser
        #: La collision telle que le coeur l'a posee, ou `None` s'il n'en a
        #: pose aucune. **C'est le signal de l'AC 8.1** : pas de collision =
        #: pas d'appel.
        self.collision: CollisionDeProfil | None = None
        #: La cle de l'issue retenue, ou `""`.
        self.issue: str = ""

    def __call__(self, occupant, radical) -> bool:
        self.collision = CollisionDeProfil(occupant=occupant, radical=radical)
        self.issue = self._poser(self.collision)
        reponse = REPONSE_DES_ISSUES.get(self.issue)
        if reponse is None:
            raise CalibrationAnnulee(
                "calibration annulée devant la collision de profil : rien "
                "n'a été écrit.")
        return reponse


# ===========================================================================
# L'impasse -- le troisieme chemin du coeur, qui n'a AUCUNE issue (AC 8.3)
# ===========================================================================

#: Les deux issues de l'impasse. **Jamais zero** : « un refus qui n'offre
#: aucune issue est aussi fautif qu'une destruction silencieuse »
#: (`EPIC11-ARB-89`). Renommer l'etiquette change le radical vise, donc sort de
#: l'impasse -- c'est la seule issue que le coeur laisse ouverte, et l'ecran la
#: nomme plutot que de laisser l'operateur devant un mur.
CLE_RENOMMER = "renommer"
CLE_ABANDONNER = "abandonner"
LIBELLE_RENOMMER = "Renommer l'étiquette et reprendre"
LIBELLE_ABANDONNER = "Revenir au menu Scan"

#: La troisieme issue, et elle n'apparait que pour UN motif
#: (`EPIC11-ARB-266`, retour d'Egan du 2026-09-07 : « moi c'est la TUI qui
#: m'interesse : pas de refus sec sans issue »). Le refus de pile mixte nommait
#: le tri en vrac dans sa phrase -- donc une commande de terminal --, et les
#: deux issues offertes ne servaient a rien : renommer l'etiquette ne change
#: rien a une pile qui porte des planches. L'operateur au clavier lisait une
#: sortie qu'il ne pouvait pas prendre.
#:
#: **Elle n'est PAS offerte sur les autres refus**, et c'est le point : trier
#: en vrac devant « aucune page de calibration lue » nommerait le mauvais
#: probleme, et une issue qui ne repond pas au refus qu'elle accompagne est
#: pire qu'une issue absente.
CLE_TRIER_EN_VRAC = "trier-en-vrac"
LIBELLE_TRIER_EN_VRAC = "Trier cette pile par QR (scan sans lot imposé)"

#: Le titre du refus. Il ne dit **jamais** « echec » (`DESIGN.md` section 9) :
#: il nomme ce qui n'a pas eu lieu.
TITRE_DU_REFUS = "Aucun profil n'a été écrit"


def issues_de_l_impasse(motif: str = "") -> list[Issue]:
    """Les issues du refus -- **au moins deux, jamais zero**, et parfois trois.

    Le coeur porte un chemin sans issue : « l'empreinte differenciante n'a pas
    separe les deux ; ecraser ferait perdre un profil qu'aucune autre trace ne
    porte » (`io/calibration_profile.py:998-1002`), un `ProfileValidationError`
    qui ne propose rien. L'ecran ne le laisse pas nu.

    **Aucune n'ecrit** : renommer ramene au formulaire, abandonner remonte au
    menu, trier relance une passe qui n'a encore rien ecrit. `ChoixExclusif`
    exige au moins une issue qui n'ecrit pas ; toutes le sont, et c'est juste --
    l'ecriture, s'il y en a une, sera celle de la passe suivante.

    **La troisieme depend du MOTIF, et c'est tout le sujet.** Une pile mixte se
    trie ; une page de calibration illisible ne se trie pas. Offrir la meme
    liste aux deux ferait lire, devant un raster abime, une issue qui ne
    repond pas au probleme -- et une issue qui ne repond pas est pire qu'une
    issue absente, parce qu'elle se prend.

    Le motif par defaut est vide : un appelant qui ne le passe pas obtient
    exactement les deux issues d'avant, jamais la troisieme par accident.
    """
    issues = [Issue(CLE_RENOMMER, LIBELLE_RENOMMER)]
    if motif == scan_calibrate.REFUS_PILE_MIXTE_EN_CALIBRATION:
        # Elle passe **avant** « revenir au menu » : c'est celle qui fait
        # avancer l'operateur, et le curseur part sur la premiere.
        issues.append(Issue(CLE_TRIER_EN_VRAC, LIBELLE_TRIER_EN_VRAC))
    issues.append(Issue(CLE_ABANDONNER, LIBELLE_ABANDONNER))
    return issues


def choix_de_l_impasse(motif: str = "") -> ChoixExclusif:
    """Le point de jugement d'un refus. Jamais un ecran sans issue."""
    return ChoixExclusif(issues_de_l_impasse(motif))


# ===========================================================================
# `EPIC11-ARB-261` -- une chaine qui porte DEJA un profil sous un autre nom
# ===========================================================================

#: Les deux issues d'`EPIC11-ARB-261`, tranche par Egan le 2026-09-07 :
#: « avertir et proposer les deux issues » -- remplacer le profil existant, ou
#: garder les deux.
CLE_GARDER_LES_DEUX = "garder-les-deux"
CLE_REMPLACER_LE_PROFIL = "remplacer-le-profil"
LIBELLE_GARDER_LES_DEUX = "Garder les deux profils"
LIBELLE_REMPLACER_LE_PROFIL = "Ne garder que le profil qui vient d'être mesuré"

#: Le titre du point de jugement, et ses deux phrases. **Le nom du fichier
#: voyage verbatim**, comme le radical de la collision : l'operateur doit
#: pouvoir le retrouver a l'oeil dans `versions/calibration/`.
TITRE_DE_LA_CHAINE_DEJA_CALIBREE = "Cette chaîne portait déjà un profil"
PHRASE_DE_LA_CHAINE_DEJA_CALIBREE = (
    "La chaîne {chaine} porte déjà « {autre} », mesuré sous un autre nom. "
    "Le profil qui vient d'être écrit ne le remplace pas : les deux fichiers "
    "décrivent la même chaîne.")
PHRASE_DE_LA_CHAINE_DEJA_CALIBREE_PLURIEL = (
    "La chaîne {chaine} porte déjà {cardinal} autres profils ({autres}), "
    "mesurés sous d'autres noms. Le profil qui vient d'être écrit ne les "
    "remplace pas : tous décrivent la même chaîne.")

#: Ce que la ligne d'etat dit quand le remplacement a eu lieu, et ce qu'elle
#: dit quand un fichier a resiste. **Un echec de retrait se PRONONCE**
#: (`EPIC11-ARB-258`) : un fichier qu'on annonce retire et qui reste est la
#: destruction silencieuse a l'envers -- une conservation silencieuse.
PHRASE_DU_REMPLACEMENT = "{cardinal} profil(s) retiré(s) de la chaîne"
PHRASE_DU_RETRAIT_IMPOSSIBLE = "{nom} n'a pas pu être retiré : {motif}"
PHRASE_DU_DEFAUT_SUIVI = "le profil par défaut du projet suit le remplacement"


def profils_a_remplacer(dossier, passe: "PasseDeCalibration") -> list[Path]:
    """Les AUTRES fichiers de profil que cette chaine porte, apres la passe.

    C'est la moitie appelante d'`EPIC11-ARB-261`, et elle manquait : les trois
    couches de la revue du 2026-09-07 ont trouve independamment que
    `io/calibration_profile.profils_de_la_chaine` -- le balayage inverse ecrit
    la veille -- n'etait **cable nulle part**. Son docstring decrit le regime
    qu'il ferme et delegue explicitement a son appelant (« elle ne decide
    rien : elle rend, l'appelant avertit et propose les deux issues »). Cet
    appelant est ici.

    **Le releve se fait APRES l'ecriture, et ce n'est pas un pis-aller.** Le
    chemin reellement ecrit est le seul qui se connaisse sans deviner : le nom
    du fichier suit la precedence *saisie -> libelle du QR -> identite de
    chaine* (`scan_calibrate.etiquette_du_profil`), dont le terme du milieu vit
    dans la detection et n'atteint jamais la TUI. Une prediction d'avant-passe
    se tromperait exactement dans le cas nominal d'Egan -- ne rien saisir --,
    et se tromperait dans le sens qui coute : elle annoncerait une seconde
    calibration sur une simple recalibration.

    **Ce que ce releve NE confond pas** : le fichier qu'on vient d'ecrire, qui
    est ecarte par comparaison de chemins resolus. Une recalibration pure --
    meme chaine, meme nom -- rend donc une liste **vide**, et l'operateur ne
    voit aucun ecran : `write_profile` a deja ecrase son propre fichier sans
    poser de question, ce qui est le regime documente depuis 5.22 (« poser la
    question a chaque recalibration serait une invite qui apprend a repondre
    oui sans lire »).

    **Aucun rang de version n'entre ici, et c'est mesure plutot qu'oublie.**
    Un profil de calibration n'est pas l'un des cinq objets versionnables
    d'`EPIC11-ARB-104` (lots, masters, planches, scans, et les frames
    d'un lot reprises sous un profil ameliore) :
    `io/version_ranks.py` n'a aucun appelant du cote de `versions/calibration/`
    et l'ecriture d'un profil ne consomme aucun rang. `EPIC11-ARB-108` -- « le
    mecanisme est le meme PARTOUT » -- n'est donc pas contourne ici : il n'y a
    rien a appeler, et recopier un calcul de rang pour un objet qui n'en porte
    pas serait la faute symetrique.
    """
    # **Le corps a quitte ce module le 2026-09-07** et vit dans
    # `scan_calibrate.autres_profils_de_la_chaine` : la ligne de commande en a
    # besoin du meme cote, et une seconde redaction de la meme regle aurait
    # diverge -- le symptome aurait ete deux interfaces qui ne comptent pas les
    # memes profils. Ce qui reste ici est la projection de `PasseDeCalibration`.
    return scan_calibrate.autres_profils_de_la_chaine(
        dossier, passe.chemin, passe.chaine)


def phrase_de_la_chaine_deja_calibree(passe: "PasseDeCalibration",
                                      autres: list[Path]) -> str:
    """La phrase du point de jugement, **au singulier et au pluriel**.

    Deux redactions et non une avec un `(s)` : « porte déjà 2 autres profils »
    et « porte déjà « X » » ne se disent pas de la meme facon, et un pluriel
    postiche est ce que `DESIGN.md` ecarte. Le cas pluriel existe pour de vrai
    -- deux libelles differents sur la meme chaine avant que cet ecran
    n'existe -- et c'est meme le regime des projets d'aujourd'hui.
    """
    if len(autres) == 1:
        return PHRASE_DE_LA_CHAINE_DEJA_CALIBREE.format(
            chaine=passe.chaine, autre=autres[0].name)
    return PHRASE_DE_LA_CHAINE_DEJA_CALIBREE_PLURIEL.format(
        chaine=passe.chaine, cardinal=len(autres),
        autres=", ".join(autre.name for autre in autres))


def issues_de_la_chaine_deja_calibree() -> list[Issue]:
    """Les DEUX issues d'`EPIC11-ARB-261`, dans l'ordre ou l'ecran les pose.

    « Garder les deux » vient en tete, donc le curseur y part : c'est l'issue
    qui n'ecrit rien, et `EPIC5-ARB-99` pose deja la meme regle pour la
    collision (« hors terminal, le defaut est l'empreinte, jamais
    l'ecrasement »). La seconde porte `ecrit=True` : elle **retire** des
    fichiers, ce qui est la seule destruction de ce parcours.

    **Il n'y a pas d'issue « annuler », et ce n'est pas un oubli.** Le profil
    est deja ecrit quand cet ecran monte ; il n'y a rien a annuler. Ce que
    l'operateur tranche ici est ce qu'il advient de l'ANCIEN, et les deux
    reponses possibles sont exactement ces deux-la. Un troisieme choix qui
    dirait « annuler » mentirait sur ce qu'il defait.
    """
    return [
        Issue(CLE_GARDER_LES_DEUX, LIBELLE_GARDER_LES_DEUX),
        Issue(CLE_REMPLACER_LE_PROFIL, LIBELLE_REMPLACER_LE_PROFIL,
              ecrit=True),
    ]


def choix_de_la_chaine_deja_calibree() -> ChoixExclusif:
    """Le point de jugement d'`EPIC11-ARB-261`. Le curseur part sur « garder »."""
    return ChoixExclusif(issues_de_la_chaine_deja_calibree())


@dataclass(frozen=True)
class RemplacementDesProfils:
    """Ce qu'un remplacement a **reellement** fait. Aucun champ n'est une phrase."""

    #: Les fichiers effectivement retires.
    retires: tuple[Path, ...] = ()
    #: Les fichiers qui ont resiste, avec le motif systeme, **verbatim**.
    resistants: tuple[tuple[Path, str], ...] = ()
    #: Le profil par defaut du projet designait-il l'un des retires, et a-t-il
    #: ete repointe sur le profil qui vient d'etre ecrit ?
    defaut_suivi: bool = False


def remplacer_les_profils_de_la_chaine(
        dossier, passe: "PasseDeCalibration", autres: list[Path], *,
        designer_le_defaut: Callable[..., Any] = (
            profile_designation.record_designated_profile),
        chemin_du_defaut: Callable[..., Any] = (
            profile_designation.default_profile_path),
) -> RemplacementDesProfils:
    """Retirer les autres profils de cette chaine, et **faire suivre le defaut**.

    C'est la seule ecriture destructive de ce parcours, et elle n'est atteinte
    que par une issue `ecrit=True` retenue a la main : c'est l'ecrasement
    CONSCIENT d'`EPIC11-ARB-89`, jamais un effet de bord.

    **Le defaut se releve AVANT le retrait, et l'ordre est le correctif.**
    `profile_designation.default_profile_path` rend `None` des que le fichier a
    disparu -- mesure dans son propre docstring : « l'entree de manifest reste
    vraie de ce que le projet a utilise, mais elle ne fabrique pas un profil
    absent. L'appelant avertit, et le lot sort brut. » Le relever apres le
    retrait rendrait donc `None` dans **les deux** cas, et le suivi ne se
    declencherait jamais.

    **Pourquoi le defaut suit, et ce que ca vaut d'etre dit** : c'est le point
    que l'invite d'`EPIC11-ARB-261` n'a pas pose a Egan, et la decision est
    prise ici plutot que laissee muette. Sans suivi, `color.default_profile` et
    `color.designated_profiles[]` gardent un `path` relatif parfaitement
    valide vers un fichier absent : le manifeste ne rougit pas, et le regime
    mesure est un **scan qui sort brut** avec un avertissement, c'est-a-dire
    une degradation silencieuse de la correction couleur. Le contraire du
    suivi n'est donc pas « ne rien faire », c'est « casser le defaut du projet
    sans le dire ».

    Le suivi vise **le profil qui vient d'etre ecrit** : meme chaine, meme
    mesure, et `_upsert` dedoublonne le registre par `chain_id`, donc l'entree
    du registre est remplacee plutot que doublee.

    **Un retrait qui echoue se PRONONCE** (`EPIC11-ARB-258`) et n'emporte pas
    les autres : un fichier en lecture seule ne doit pas faire perdre le
    retrait des trois autres, et il ne doit pas non plus etre annonce retire.
    Les deux listes sont rendues separement pour cela.
    """
    # **Corps deplace dans `scan_calibrate.retirer_les_profils_de_la_chaine`**
    # le 2026-09-07, meme motif que ci-dessus : la seule ecriture destructive de
    # ce parcours ne pouvait pas rester dans une interface quand l'autre en a
    # besoin. Ce qui reste ici est la projection de `PasseDeCalibration` et la
    # conversion vers le type que les ecrans de cet atelier lisent deja.
    retrait = scan_calibrate.retirer_les_profils_de_la_chaine(
        dossier, autres,
        chemin_garde=passe.chemin,
        document_garde=(None if passe.profil is None
                        else passe.profil.document),
        designer_le_defaut=designer_le_defaut,
        chemin_du_defaut=chemin_du_defaut)
    return RemplacementDesProfils(retires=retrait.retires,
                                  resistants=retrait.resistants,
                                  defaut_suivi=retrait.defaut_suivi)


def etat_du_remplacement(remplacement: RemplacementDesProfils) -> str:
    """Ce que la ligne d'etat dit apres un remplacement. **Une mesure.**

    Les resistants passent **en tete** : ce qui n'a pas eu lieu prime sur ce
    qui a eu lieu, sans quoi l'operateur lit « 2 profils retirés » et rate le
    troisieme qui est reste.
    """
    parts = [PHRASE_DU_RETRAIT_IMPOSSIBLE.format(nom=chemin.name, motif=motif)
             for chemin, motif in remplacement.resistants]
    parts.append(PHRASE_DU_REMPLACEMENT.format(
        cardinal=len(remplacement.retires)))
    if remplacement.defaut_suivi:
        parts.append(PHRASE_DU_DEFAUT_SUIVI)
    return " — ".join(parts)


# ===========================================================================
# Le releve d'avant-passe -- comment les DEUX situations se distinguent
# ===========================================================================

def dossier_des_profils(dossier) -> Path:
    """`versions/calibration/` du projet, **compose par le coeur**.

    `calibration_profile.profile_path` est le seul endroit du depot qui joint
    `versions/` et `calibration/` ; en prendre le parent est ce qui garantit
    que ce releve regarde le dossier ou le coeur ecrit, et non un chemin
    recompose qui divergerait au premier deplacement.
    """
    return calibration_profile.profile_path(dossier, "profil").parent


def profils_du_projet(dossier) -> dict[Path, float]:
    """Le releve des fichiers de profil **avant** la passe : chemin -> mtime.

    **Ce n'est pas la regle de collision, et la distinction est ce qui le rend
    legitime** (AC 8.2) : aucun radical n'est compose, aucune identite de chaine
    n'est lue ni comparee, et ce releve ne decide de rien. Il sert une seule
    question, posee **apres** que le coeur a rendu le chemin qu'il a ecrit :
    « ce fichier existait-il deja ? ». Le coeur ayant, lui, deja tranche qu'il
    n'y avait pas collision -- il n'a pas appele le relais --, la reponse
    « oui » **est** la recalibration de l'AC 8.1.

    Un dossier absent rend un releve vide : un projet qui n'a jamais calibre
    n'est pas une faute.
    """
    releve: dict[Path, float] = {}
    try:
        fichiers = sorted(dossier_des_profils(dossier).iterdir())
    except OSError:
        return releve
    for chemin in fichiers:
        try:
            releve[chemin.resolve()] = chemin.stat().st_mtime
        except OSError:
            # Un fichier qui disparait entre le listage et la mesure n'est pas
            # une faute : il n'entre pas au releve, et la passe le traitera
            # comme un profil neuf -- ce qu'il sera devenu.
            continue
    return releve


def date_du_fichier(horodate: float | None) -> str:
    """`12/08`, ou `""` quand on ne sait pas.

    **La date est celle du FICHIER, mesuree sur le disque**, et non un champ du
    document : `calibration_profile._REQUIRED_FIELDS` n'en porte aucun, et
    inventer un horodatage serait la valeur qui a l'air juste -- la pire des
    deux erreurs possibles (`DESIGN.md` section 3).

    Le format `JJ/MM` est celui de `E3-5`, **lu de son module** et non recopie :
    deux redactions de la meme date se seraient repondues differemment.
    """
    if horodate is None:
        return ""
    try:
        return date_lisible(datetime.fromtimestamp(horodate).isoformat())
    except (OSError, OverflowError, ValueError):
        return ""


# ===========================================================================
# Le formulaire -- modele PUR, aucune dependance a `textual`
# ===========================================================================

def dpi_valide(saisie: str) -> int | None:
    """Le dpi saisi, valide **par la seule autorite du depot**, ou `None`.

    La regle n'est pas reecrite ici : c'est celle de `E3-1`
    (`atelier_scan.FormulaireDuDepot.dpi_valide`, qui appelle
    `scan_ingest.validate_scan_dpi`), lue sur un formulaire nu. C'est ce qui
    garantit que les deux ecrans du Scan refusent **exactement** les memes
    saisies -- une seconde regle ecrite ici accepterait un `20001` que
    l'ingestion refuserait dix secondes plus tard.
    """
    return FormulaireDuDepot(dpi=saisie).dpi_valide


@dataclass
class FormulaireDeCalibration:
    """Le modele de `E3-9` : un scan, un dpi, deux textes, un choix.

    **Modele pur**, comme `panneau.py` et `explorateur.py` : aucune dependance
    a `textual`, aucune ecriture. C'est ce qui rend mesurables sans terminal les
    deux appariements a risque de cet ecran -- le champ au focus contre la ligne
    rendue, et ce que la frappe ecrit contre le champ qu'elle vise.

    ``dpi`` est une **chaine** et non un entier : c'est ce que l'operateur
    frappe, et le champ doit pouvoir etre **vide**, ce qu'aucun entier ne sait
    dire. Il part vide (`EPIC11-ARB-38` : « elle n'est pas preremplie. Le champ
    reste requis, et vide »), et c'est l'ecart `H12` de la fiche.

    ``etiquette`` part vide elle aussi, et son absence n'est **pas** un manque :
    le coeur nomme alors le fichier par l'identite qu'il derive du scan. Aucune
    borne de longueur n'est posee ici -- `write_profile` refuse un radical hors
    budget, et une seconde borne ecrite en TUI divergerait de la sienne
    (`CANONICAL_ID_MAX_LENGTH` a valu 48, puis 64, puis 48).
    """

    scan: SourceDesignee | None = None
    dpi: str = ""
    etiquette: str = ""
    commentaire: str = ""
    #: `EPIC11-ARB-89` et AC 8.6 : « poser un defaut est une decision, pas un
    #: effet de bord ». Le champ part donc a `non`.
    devient_le_defaut: bool = False
    #: Le champ courant, **suivi** : `aide_de_champ.ChampSuivi` compte chaque
    #: deplacement du curseur, et c'est ce compte qui fait TOMBER l'aide de
    #: champ au lieu de la cacher (correctif du 2026-09-04). Le comptage se
    #: fait a l'AFFECTATION : aucun chemin de navigation -- ni ceux d'ici, ni
    #: un chemin ajoute plus tard -- n'a rien a appeler pour cela.
    champ: str = aide_de_champ.ChampSuivi(CHAMP_SCAN)

    # -- lecture ------------------------------------------------------------

    def saisie(self, cle: str) -> str:
        """Ce qu'un champ de saisie porte VRAIMENT, blancs de bord retires.

        **Une seule redaction pour trois surfaces** : la valeur dessinee, la
        mention de la colonne de droite, et ce qui part au coeur. La premiere
        redaction ne strippait que la valeur : une etiquette de blancs affichait
        alors le glyphe neutre -- qui signifie VIDE -- pendant que sa mention
        (« a defaut, l'identite derivee du scan ») disparaissait, et le coeur
        recevait `'   '` comme nom de chaine. Les deux canaux de l'ecran se
        contredisaient, et le document de profil portait un libelle blanc
        (revue de reprise, trouve par les trois couches).
        """
        valeur = getattr(self, cle, "")
        return valeur.strip() if isinstance(valeur, str) else valeur

    def champs(self) -> tuple[str, ...]:
        """Les champs que `Tab` parcourt, dans l'ordre de saisie.

        **La reprise n'en est un que quand une mesure existe** (`E3-1`, meme
        regle) : une ligne qui proposerait de reprendre ce qui n'a pas ete
        mesure serait une cible qui ne fait rien, et le curseur s'y arreterait
        pour rien.
        """
        avec_reprise = bool(mention_de_la_mesure(self.scan))
        return tuple(cle for cle in (CHAMP_SCAN, CHAMP_DPI, CHAMP_REPRISE,
                                     CHAMP_ETIQUETTE, CHAMP_COMMENTAIRE,
                                     CHAMP_DEFAUT, CHAMP_VALIDER)
                     if cle != CHAMP_REPRISE or avec_reprise)

    @property
    def dpi_valide(self) -> int | None:
        return dpi_valide(self.dpi)

    @property
    def peut_calibrer(self) -> bool:
        """L'action principale est **inaccessible** tant qu'un champ requis est
        vide ou invalide (`DESIGN.md` section 7.3, `EPIC7-ARB-44` : le dpi est
        « obligatoire et sans defaut, aucun appelant n'en invente un »)."""
        return self.scan is not None and self.dpi_valide is not None

    @property
    def chemin_du_scan(self) -> Path | None:
        """Le chemin qui part au coeur, ou `None`.

        `E3-9` calibre **une page** : la quatrieme forme d'`EPIC7-ARB-88` -- une
        sequence de chemins -- n'a pas de sens ici, et l'explorateur de ce site
        est monte **sans** `selection_multiple`. Le champ rend donc toujours un
        chemin unique.
        """
        return None if self.scan is None else self.scan.chemin

    # -- ecriture -----------------------------------------------------------

    def avancer(self, pas: int = 1) -> bool:
        """`↓` (`pas=1`) et `↑` (`pas=-1`) : le champ suivant, en boucle.

        **C'etait `Tab`, et Egan l'a retire** (`EPIC11-ARB-158`) : « il faudrait
        passer d'un champ a l'autre avec les fleches haut-bas et non avec tab ».
        `Tab` continue de fonctionner en synonyme non annonce.

        En boucle, et non borne : le formulaire tient sur six lignes, et une
        borne obligerait a une seconde touche pour revenir en arriere.
        """
        champs = self.champs()
        if self.champ not in champs:
            # La ligne de reprise a disparu sous le curseur (un scan
            # redesigne, sans mesure cette fois) : on retombe sur le dpi plutot
            # que de laisser un focus qui ne designe plus rien.
            self.champ = CHAMP_DPI
            return True
        self.champ = champs[(champs.index(self.champ) + pas) % len(champs)]
        return True

    def poser_le_scan(self, scan: SourceDesignee) -> None:
        """Retenir le scan mesure. **Le dpi n'est pas touche.**

        `EPIC11-ARB-38` : la mesure « est confrontee au DPI declare, jamais
        substituee ». Poser la valeur mesuree ici serait la substitution que
        l'arbitrage interdit, sous la forme la plus difficile a voir -- un champ
        qui se remplit tout seul et qu'on ne relit pas.
        """
        self.scan = scan
        self.champ = CHAMP_DPI

    def frapper(self, caractere: str) -> bool:
        """Un caractere dans le champ de saisie au focus.

        **Toute lettre s'y ecrit** (`EPIC11-ARB-68`) : « aucune lettre n'est un
        raccourci dans un champ de saisie, sans exception et sans ordre de
        priorite a maintenir ». Filtrer les caracteres non numeriques du dpi
        serait une facon detournee de rendre une lettre inerte ; le champ les
        accepte et la validation les refuse, ce qui est visible.
        """
        if self.champ not in CHAMPS_DE_SAISIE:
            return False
        setattr(self, self.champ, getattr(self, self.champ) + caractere)
        return True

    def effacer(self) -> bool:
        if self.champ not in CHAMPS_DE_SAISIE or not getattr(self, self.champ):
            return False
        setattr(self, self.champ, getattr(self, self.champ)[:-1])
        return True

    def reprendre_la_mesure(self) -> bool:
        """Le geste qui reprend le dpi mesure d'un coup (AC 8.5).

        **Ce geste n'est pas une lettre** (`EPIC11-ARB-68`) : la mesure est une
        **ligne du formulaire**, atteinte par `Tab` et validee par `⏎`. Zero
        ressaisie, mais un acte de l'operateur -- ce qui reste conforme a
        `EPIC11-ARB-38` : la valeur est offerte, jamais posee.
        """
        if self.scan is None or self.scan.dpi is None:
            return False
        self.dpi = dpi_lisible(self.scan.dpi)
        return True

    def basculer_le_defaut(self) -> bool:
        """`⏎` sur la ligne « Devient le défaut » : elle bascule.

        C'est un **champ de formulaire** et non une liste d'issues (AC 8.6) :
        `EPIC11-ARB-126` ne s'y applique pas, et le dire evite qu'une revue le
        corrige a tort.
        """
        if self.champ != CHAMP_DEFAUT:
            return False
        self.devient_le_defaut = not self.devient_le_defaut
        return True


# ===========================================================================
# La passe -- ce que le coeur a fait, lu de lui et jamais suppose
# ===========================================================================

@dataclass(frozen=True)
class PasseDeCalibration:
    """Ce qu'une passe de calibration a **reellement** produit.

    Aucun champ n'est une phrase : la redaction appartient a l'ecran, exactement
    comme `scan_calibrate.ProfilDeChaineConsigne` -- dont cette classe est la
    projection cote TUI, augmentee des deux faits que seul l'appelant peut
    tenir : la collision que le coeur a posee, et le releve d'avant-passe.
    """

    #: Le `ProfilDeChaineConsigne` du coeur, ou `None` si rien n'a ete ecrit.
    profil: Any = None
    #: Le refus, tel que le coeur l'a leve. Son message est **verbatim**.
    refus: BaseException | None = None
    #: Le motif nomme du refus, lu de `RefusDeCalibration.motif` -- l'une des
    #: constantes de `scan_calibrate.MOTIFS_DE_REFUS_DE_CALIBRATION`, ou `""`.
    motif: str = ""
    #: La collision **posee par le coeur**, ou `None` s'il n'en a pose aucune.
    collision: CollisionDeProfil | None = None
    #: La cle de l'issue retenue devant la collision, ou `""`.
    issue: str = ""
    #: L'identite de chaine, **lue du rappel de nommage** ou du resultat.
    chaine: str = ""
    #: Le fichier remplace existait-il **avant** la passe ? Voir
    #: :func:`profils_du_projet` : c'est la recalibration de l'AC 8.1.
    recalibration: bool = False
    #: La date du fichier remplace, `JJ/MM`, ou `""`.
    date_precedente: str = ""
    #: La date du fichier ecrit, `JJ/MM`, ou `""`.
    date_ecrite: str = ""

    @property
    def a_ecrit(self) -> bool:
        return self.profil is not None

    @property
    def chemin(self) -> Path | None:
        return None if self.profil is None else Path(self.profil.profile_path)


#: Les refus du coeur que cet ecran met en forme. **La table est LUE du coeur**
#: (`scan_calibrate.CODES_DE_SORTIE`) et non recopiee : une seconde redaction du
#: vocabulaire des refus est exactement la dette que le lot B a fermee en
#: publiant `scan_detect.REFUS_DU_COEUR`.
REFUS_DU_COEUR = tuple(classe for classe, _ in scan_calibrate.CODES_DE_SORTIE)


def motif_du_refus(exception: BaseException) -> str:
    """Le motif nomme d'un refus, ou `""` quand il n'en porte pas.

    Seul `RefusDeCalibration` en porte un ; `ScanIngestError` et
    `ScanDetectionError` disent leur phase par leur type. Rendre `""` plutot
    qu'inventer un motif garde l'ensemble ferme du coeur exactement ferme.
    """
    motif = getattr(exception, "motif", None)
    return motif if isinstance(motif, str) else ""


#: L'unite des jalons de la calibration. Ce sont des PAGES : le canal du
#: coeur emet un jalon par page detectee (`detect_pages`), et nommer autre
#: chose ferait lire « 3 mires » la ou il y a trois pages.
UNITE_DE_LA_PASSE = "pages"

#: Le titre de la tache, sur l'ecran d'execution.
TITRE_DE_LA_PASSE = "Calibration de la chaîne"

#: Les DEUX lots de la passe, dans l'ordre ou le coeur les joue. Ils portent
#: les noms des deux phases que `scan_calibrate.calibrer_la_chaine` enchaine et
#: qui emettent -- l'ecriture du profil, negligeable, n'en est pas un.
#:
#: **Nommer les deux lots n'a de sens que depuis que l'ingestion parle**
#: (dette `CALIB-N1`, fermee cote coeur le 2026-09-07). Avant, declarer la
#: passe n'aurait fait que DEPLACER le saut : la barre serait restee immobile
#: sur un lot « ingestion » muet, puis aurait saute d'un coup. C'est cette
#: dependance qui interdisait de livrer la moitie bon marche.
LOT_DE_L_INGESTION = "Lecture des pages du scan"
LOT_DE_LA_DETECTION = "Détection des mires et des QR"

#: Les deux issues de la page de confirmation. **Aucune n'ecrit** : c'est un
#: point de jugement, et `EPIC11-ARB-7` interdit qu'une issue y ecrive sans
#: l'avoir dit.
ISSUE_LANCER = "lancer"
ISSUE_REVENIR = "revenir"

#: Le titre du cartouche de la confirmation. Il porte la promesse que la page
#: existe pour tenir : rien n'est encore ecrit.
TITRE_DE_LA_CONFIRMATION = "Ce qui va être fait — rien n'est encore écrit"

#: Ce que la garde de re-entrance DIT quand elle refuse (finding `F3`). Elle
#: etait muette, huit lignes sous un commentaire qui rappelle qu'« une touche
#: annoncee qui ne fait rien et ne dit rien est indistinguable d'un clavier
#: casse ».
PHRASE_PASSE_EN_COURS = "une calibration est déjà en cours"


#: Ou l'application note QUEL ecran porte la tache en cours. Sans lui,
#: l'extinction du drapeau au demontage est inconditionnelle : un ecran de
#: passe demonte eteignait le drapeau d'une passe SUIVANTE deja lancee (mesure
#: de la revue de reprise -- « le fil de la passe 2 tourne, son drapeau est
#: tombe, une 3e passe part »), c'est-a-dire le symetrique exact du defaut que
#: cette classe ferme.
_ATTRIBUT_DE_L_ECRAN_DE_TACHE = "_ecran_de_la_tache"


def _classe_de_l_ecran_de_passe() -> Any:
    """La classe de l'ecran d'execution de la passe, construite une seule fois.

    `EcranExecution` vit dans `execution.py`, que l'AC 10.3 reserve au lot qui
    en a le mandat : on le SOUS-CLASSE plutot que de l'ouvrir, comme
    `EcranDetectionEnCours` et `EcranEcritureDuScan` le font deja.

    **Une seule fois**, et c'est un correctif : la premiere redaction
    construisait une classe NEUVE a chaque appel (`a is b` -> `False`), si bien
    que deux passes d'une meme session portaient deux types differents -- un
    `isinstance` croise aurait rendu faux sans que rien ne le dise.
    """
    global _CLASSE_DE_L_ECRAN_DE_PASSE
    if _CLASSE_DE_L_ECRAN_DE_PASSE is not None:
        return _CLASSE_DE_L_ECRAN_DE_PASSE

    from .execution import EcranExecution

    class EcranCalibrationEnCours(EcranExecution):
        """L'ecran d'execution de la passe, **avec le cycle de vie complet**.

        `EcranExecution.on_mount` pose `app.tache_en_cours = True` ; rien ne le
        retire au demontage, et jusqu'ici c'etait sans consequence parce que le
        parcours l'eteignait lui-meme. Ce n'est plus vrai depuis que la
        calibration monte cet ecran : `descendre` **differe** le montage, et une
        passe que le coeur refuse vite peut se terminer avant que le message de
        montage ne soit traite. L'ordre observe alors, 18 tours sur 20 :

            True  <- lancer_la_passe_de_calibration
            False <- oublier_la_tache            (fin de passe)
            True  <- EcranExecution.on_mount     et plus personne ne l'eteint

        Ce qui reste : `Échap` ne depile plus, `q` ne quitte plus, et la garde
        de re-entrance refuse **toute calibration suivante**. L'atelier est mort
        pour la session (mesure 10/10).

        Le correctif est la **symetrie** : ce que le montage pose, le demontage
        le retire. `Mount` precede toujours `Unmount` pour une meme instance,
        donc l'ordre d'arrivee des messages ne peut plus laisser le drapeau a
        vrai.

        **Mais l'extinction est CONDITIONNELLE**, et ce second tour l'a impose :
        `on_unmount` est differe lui aussi. Demonter l'ecran d'une passe finie
        puis lancer la suivante dans le meme tour de boucle faisait tomber le
        drapeau de la passe NEUVE -- fil vivant, garde de re-entrance desarmee,
        « deux ingestions, deux ecritures de profil », le risque que le
        docstring de `lancer_la_passe_de_calibration` nomme lui-meme. On
        n'eteint donc que si l'ecran demonte est encore celui de la tache.
        """

        def on_mount(self) -> None:
            super().on_mount()
            setattr(self.app, _ATTRIBUT_DE_L_ECRAN_DE_TACHE, self)

        def on_unmount(self) -> None:
            super().on_unmount()
            if getattr(self.app, _ATTRIBUT_DE_L_ECRAN_DE_TACHE, None) is self:
                setattr(self.app, _ATTRIBUT_DE_L_ECRAN_DE_TACHE, None)
                # Idempotent : le parcours l'eteint aussi dans son `finally`,
                # et l'eteindre deux fois ne coute rien -- c'est le laisser
                # allume qui coute.
                self.app.oublier_la_tache()

    _CLASSE_DE_L_ECRAN_DE_PASSE = EcranCalibrationEnCours
    return _CLASSE_DE_L_ECRAN_DE_PASSE


#: Memoire de la classe ci-dessus. `None` tant que le premier ecran de passe
#: n'a pas ete monte -- l'import d'`execution` est differe pour la meme raison
#: que partout ailleurs dans ce module.
_CLASSE_DE_L_ECRAN_DE_PASSE: Any = None


#: Ce que l'ecran d'execution DIT quand l'operateur demande l'arret d'une passe
#: qui n'a pas de point d'arret. **Le dire vaut mieux que le taire** : une issue
#: qui pose un drapeau en silence est indistinguable d'un clavier casse, et
#: c'est le reproche que cette meme revue a fait a la version precedente.
PHRASE_ARRET_SANS_POINT_D_ARRET = (
    "arrêt demandé — la passe en cours va jusqu'à son terme")


def _interrompre_la_calibration(app, issue) -> None:
    """L'issue qui demande l'arret. « Reprendre » ne vient jamais ici.

    Sans ce rappel, `EcranExecution.issue_d_interruption` jette les deux issues
    qui ne sont pas « Reprendre » : elles etaient **annoncees, choisies et
    inertes**, pile inchangee et pas un mot.

    **Le poser ne suffisait pas**, et le second tour de revue l'a mesure : le
    calque d'`atelier_scan_detection._interrompre` se contente d'armer le
    drapeau parce que la detection, elle, le CONSULTE et conclut. Ici personne
    ne le consulte -- `consigner` ne prend pas d'`interrompu` --, si bien que
    du siege de l'operateur le regime restait identique a celui d'avant :
    l'ecran d'interruption ne bougeait pas, rien n'etait dit, et il fallait un
    second `Échap` pour sortir.

    Ce rappel fait donc les trois gestes que l'operateur attend : il enregistre
    la demande, il **depile** la question a laquelle il vient de repondre, et il
    **dit** ce qui va se passer.

    **Ce qu'il ne fait toujours PAS, dit plutot que tu** : il n'arrete pas la
    passe. `calibrer_la_chaine` est un appel synchrone **sans point d'arret**,
    et l'entree est portee a `deferred-work.md`.
    """
    app.interruption_demandee = True
    ecran_de_passe = getattr(app, _ATTRIBUT_DE_L_ECRAN_DE_TACHE, None)
    if app.screen_stack and len(app.screen_stack) > 1 and (
            app.screen is not ecran_de_passe):
        # La question est consommee : l'operateur a tranche.
        app.pop_screen()
    if ecran_de_passe is not None:
        # **Au JOURNAL et pas seulement en ligne d'etat.** La ligne d'etat de
        # l'ecran d'execution porte l'avancement et se fait donc reecrire au
        # jalon suivant : un message pose la disparaitrait au bout d'une page.
        # Le journal, lui, garde la trace -- c'est ce que l'operateur relira
        # quand la passe se terminera quand meme.
        ecran_de_passe.surface.journal.inscrire(
            PHRASE_ARRET_SANS_POINT_D_ARRET)
        ecran_de_passe.rafraichir()


class RelaisDesPhasesDeLaCalibration:
    """Router les jalons du coeur vers le BON lot de la passe (dette `CALIB-N1`).

    Le coeur emet deux suites de jalons par le **meme** rappel -- l'ingestion,
    puis la detection -- et il ne peut pas faire autrement : l'invariant du
    depot est que le rappel est **passe, jamais enveloppe**
    (`EPIC7-ARB-79`), et agreger dans `calibrer_la_chaine` obligerait a
    l'envelopper. C'est donc a l'appelant qui **affiche** une barre de recoller
    les deux suites, et cette classe est cet appelant.

    **La frontiere de phase se lit sur un jalon NON PROGRESSIF**, et ce n'est
    pas une devinette : les deux phases parcourent les memes pages, donc la
    seconde suite repart a `1` alors que la premiere s'est arretee a `N >= 1`.
    C'est mesure dans le coeur --
    `tests/unit/test_progression_de_l_ingestion_du_scan.py`, banc
    `test_les_DEUX_phases_emettent_et_la_seconde_REPART_a_un` -- plutot que
    suppose ici, et `EmetteurProgression` garantit de son cote que, *dans* une
    phase, `faites` croit strictement.

    **Le total des deux lots est pose des le premier jalon**, et il n'est pas
    invente : la detection parcourt exactement les pages que l'ingestion a
    produites, donc son cardinal est celui de l'ingestion. Si les deux
    divergent -- un fichier saute, et la detection en compte un de moins --,
    c'est le cardinal **mesure** qui l'emporte, `PasseEnCours` s'en charge
    (`mesurer_le_lot_courant`). La barre corrige alors d'elle-meme.

    **Ce qu'elle ne fait PAS, dit plutot que tu** : elle ne devine aucun total
    AVANT le premier jalon. Tant que rien n'est arrive, la passe n'est pas
    declaree et l'ecran montre ce qu'il montrait deja -- zero sur un total
    inconnu. Inventer « 2 pages » sur une mire serait un chiffre faux presente
    comme une mesure.
    """

    def __init__(self, surface) -> None:
        self.surface = surface
        #: Le dernier `faites` vu, toutes phases confondues. C'est lui, et rien
        #: d'autre, qui detecte la frontiere.
        self._dernier = 0
        #: Combien de phases ont ete ouvertes. Deux au plus : une troisieme
        #: suite de jalons -- qui n'existe pas aujourd'hui -- resterait dans le
        #: second lot plutot que de deborder, ce que `commencer_le_lot_suivant`
        #: borne deja de son cote.
        self.phases_ouvertes = 0

    def noter(self, faites: int, total: int) -> None:
        """Un jalon du coeur, route vers son lot. **Appele sur la boucle.**

        Cette methode mute la passe et l'arbre de widgets : elle est appelee
        par `call_from_thread`, jamais depuis le fil de travail directement.
        C'est la meme discipline que `noter_le_jalon` portait deja seul.
        """
        if self.phases_ouvertes == 0:
            # Premiere phase : la passe se declare ICI, avec le cardinal que le
            # coeur vient de mesurer -- pas plus tot, ou il faudrait le deviner.
            self.surface.declarer_la_passe(
                TITRE_DE_LA_PASSE,
                [(LOT_DE_L_INGESTION, total), (LOT_DE_LA_DETECTION, total)])
            self.surface.passe.commencer_le_lot_suivant(total)
            self.phases_ouvertes = 1
        elif faites <= self._dernier and self.phases_ouvertes < 2:
            # La frontiere. `<= ` et non `< ` : sur une MIRE les deux phases
            # emettent `(1, 1)`, et un `<` strict laisserait les deux jalons
            # dans le premier lot -- c'est-a-dire exactement le cas du grief.
            self.surface.passe.commencer_le_lot_suivant(total)
            self.phases_ouvertes = 2
        self._dernier = faites
        self.surface.noter(faites, total)


def ouvrir_la_calibration_en_cours(app, *, objet: str = "",
                                   surface: Any = None) -> Any:
    """Monter l'ecran d'execution de la passe.

    **Le total part a ZERO et n'est pas devine.** Il n'est connu qu'apres
    l'ingestion, et l'inventer ici serait un chiffre faux presente comme une
    mesure ; le premier jalon du coeur le pose.

    C'est un `EcranExecution` du module partage, **pas un ecran neuf** : la
    barre, le journal, `Tab` et `Échap interrompre` y sont deja, et un second
    ecran divergerait au premier ajustement.

    **`objet` reste vide, et c'est un arbitrage d'Egan et non un oubli** : « on
    met juste rien a cet endroit » (2026-09-01). La premiere redaction portait
    `OBJET_DU_DEPOT if "OBJET_DU_DEPOT" in globals() else ""` -- un test
    d'existence de nom au moment de l'execution, dont la branche vraie etait
    **inatteignable** (la constante vit dans `atelier_scan.py`) et dont la
    branche vraie aurait de toute facon affiche « temps 1 sur 2 · detecter »,
    le libelle de la DETECTION. Les deux branches etaient fausses.
    """
    from .execution import SurfaceExecution

    # **La surface se FOURNIT**, parce que le parcours la cree avant le fil et
    # ne monte l'ecran qu'au premier jalon (AC 9.6) : deux surfaces feraient
    # ecrire le coeur dans l'une et dessiner l'ecran depuis l'autre.
    if surface is None:
        surface = SurfaceExecution(unite=UNITE_DE_LA_PASSE)
    ecran = _classe_de_l_ecran_de_passe()(
        surface, titre_tache=TITRE_DE_LA_PASSE, objet=objet,
        # **Le rappel n'est pas facultatif**, et le docstring de
        # `ouvrir_l_interruption` le dit : sans lui l'ecran d'interruption est
        # « un cul-de-sac clavier ». C'etait le seul des trois sites du paquet a
        # ne pas le passer.
        sur_issue=lambda issue: _interrompre_la_calibration(app, issue))
    app.descendre(ecran)
    return ecran


def panneau_de_la_confirmation(formulaire: FormulaireDeCalibration) -> Any:
    """Le cartouche de la page de confirmation. Trois faits, et trois seulement.

    Ce qui sera lu, avec quelle resolution, et si le profil deviendra le
    defaut. Rien d'autre : un cartouche qui recopierait le formulaire entier
    ferait relire ce qu'on vient de saisir au lieu de le RESUMER.
    """
    scan = formulaire.chemin_du_scan
    return Panneau(TITRE_DE_LA_CONFIRMATION, [
        LigneChiffree(LIBELLE_SCAN, scan.name if scan is not None else ""),
        LigneChiffree(LIBELLE_DPI, formulaire.dpi_valide or 0, UNITE_DPI),
        LigneChiffree(LIBELLE_DEFAUT,
                      CHOIX_OUI if formulaire.devient_le_defaut else CHOIX_NON),
    ])


def issues_de_la_confirmation() -> ChoixExclusif:
    """Les deux issues, et **celle qui mene a l'ecriture le porte**.

    `ecrit` marque l'issue qui MENE a une ecriture, pas celle qui ecrit dans la
    milliseconde : `E3-6` pose `Issue(ISSUE_ECRIRE, ..., ecrit=True)` sur un
    ecran qui, lui non plus, n'a encore rien mis sur le disque. La premiere
    redaction avait lu `ecrit` comme « ecrit maintenant » et pose `False` des
    deux cotes -- au nom de la verite du cartouche (« rien n'est encore
    ecrit »), qui reste vraie et que le panneau porte deja.

    **Ce que ce `False` desarmait**, et c'est la couche 2 de la revue qui l'a
    mesure : `ChoixExclusif` ne deplace le curseur hors de l'issue principale
    que si celle-ci `ecrit` (`EPIC11-ARB-7` apres `EPIC11-ARB-45`). Curseur pose
    sur « Lancer », un `⏎` nu partait donc dans la passe de plusieurs minutes --
    la page ajoutee pour empecher un `⏎` reflexe se franchissait d'un `⏎`
    reflexe.
    """
    return ChoixExclusif([Issue(ISSUE_LANCER, "Lancer la calibration",
                                ecrit=True),
                          Issue(ISSUE_REVENIR, "Revenir au formulaire", False)])


class EcranCalibrationAConfirmer(EcranChiffre):
    """Le point de jugement AVANT la passe (Egan, 2026-09-01).

    « Pas de page de validation avant, ce n'est pas conforme au reste des
    parcours. » Il avait raison sur les deux moities : le parcours du Scan pose
    un `EcranChiffre` avant toute ecriture (`E3-6` pour le temps 2), et la
    calibration partait sans.

    **Elle n'ecrit pas un second point de jugement** : `EcranChiffre` porte deja
    le cartouche, le choix exclusif, la fleche seule (`EPIC11-ARB-126`) et le
    placement du curseur sur une issue qui n'ecrit pas (`EPIC11-ARB-45`). Cette
    classe ne fournit que son panneau et ses issues.
    """

    #: **Deux segments et non un**, comme `EcranCalibrerLaChaine` et
    #: `EcranRefusDeCalibration` : la page de jugement appartient au geste
    #: `Calibrer`, et un bandeau qui ne dirait que `Scan` ferait perdre a
    #: l'operateur le seul repere qui dit ou il est dans l'atelier.
    titre = PALIER_DE_L_ECRAN
    TRANSITOIRE = True

    def __init__(self, formulaire: FormulaireDeCalibration, *,
                 sur_issue: Callable[[Any], None] | None = None,
                 objet: str = "") -> None:
        super().__init__(panneau_de_la_confirmation(formulaire),
                         issues_de_la_confirmation(),
                         sur_issue=sur_issue, objet=objet)
        self.formulaire = formulaire


def consigner(dossier, formulaire: FormulaireDeCalibration, *,
              poser_la_collision: Callable[[CollisionDeProfil], str],
              hote: Callable[..., Any] | None = None,
              logger=None,
              # **Annote, et l'annotation EST la mesure.** `test_rappels_cables`
              # -- la garde batie apres sept occurrences de « un mecanisme
              # juste, cable nulle part » -- ne retient que les parametres
              # annotes `Callable ... None` avec defaut `None`. Sans annotation
              # ce rappel lui etait invisible : retirer le mot-cle du site
              # d'appel laissait les huit tests verts (mesure de la revue de
              # vague B, couche 3).
              rappel_progression: Callable[[int, int], None] | None = None,
              calibrer: Callable[..., Any] = scan_calibrate.calibrer_la_chaine,
              designer_le_defaut: Callable[..., Any] = (
                  profile_designation.record_designated_profile)
              ) -> PasseDeCalibration:
    """Une passe de `scan ... calibrate`, **hebergee** et jamais relancee.

    `hote` est `CoqueTui.executer_en_processus` (`EPIC11-ARB-1`, AC 5.1) ; il
    vaut l'appel direct par defaut, pour que la passe se mesure sans monter
    d'application.

    Les **deux questions du coeur** entrent par ses deux rappels, et par eux
    seuls (`EPIC7-ARB-106`) :

    * `demander_le_nom_et_le_commentaire` rend ce que le formulaire porte deja.
      Il n'ouvre aucune invite : l'operateur a nomme **avant** de lancer, sur
      les deux lignes que la maquette dessine. Son autre role est de capter le
      `chain_id` que le coeur derive -- c'est le seul moment ou il traverse ;
    * `confirmer_l_ecrasement` est :class:`RelaisDeCollision`. Il n'est appele
      que si le coeur a **decide** qu'il y a collision, et il ne fait que poser
      la question et relayer la reponse (AC 8.2).

    ``rappel_progression`` est **passe** au coeur, comme partout ailleurs
    (story 11.4e, AC 9.4). C'est la moitie TUI du lot J : le coeur porte le
    canal depuis J1, et cette fonction est le seul point ou la surface de
    l'ecran s'y branche. Il reste **optionnel** (`AR3`) -- sans lui, memes
    refus, meme profil.

    Les erreurs hors table **traversent** : deguiser une panne inconnue en refus
    metier ferait lire un motif rassurant sur un bug.

    :param poser_la_collision: rend la cle de l'issue retenue
        (:data:`REPONSE_DES_ISSUES`). **Requis** -- finding `K3`.
    :param designer_le_defaut: appele **uniquement** quand le formulaire porte
        « Devient le défaut = oui ». A `non`, cette passe fait exactement ce que
        `mmu scan ... calibrate` fait : elle ecrit le profil et n'inscrit rien
        au manifeste (AC 10.2 -- la TUI est un appelant de plus, pas un
        appelant qui en fait plus).
    """
    hote = hote or (lambda fonction, *args, **kwargs: fonction(*args, **kwargs))
    dossier = Path(dossier)
    avant = profils_du_projet(dossier)
    relais = RelaisDeCollision(poser_la_collision)
    capte: dict[str, str] = {}

    def nommer(chain_id):
        # **Le `chain_id` traverse ici et nulle part ailleurs** : le coeur le
        # derive, l'ecran ne le recompose pas. C'est ce qui permet a `E3-9` de
        # nommer la chaine sans jamais deriver d'identite lui-meme.
        capte["chaine"] = chain_id
        # **Ce que l'ecran dit vide part vide.** Sans `saisie`, une etiquette de
        # blancs traversait verbatim et le document de profil portait
        # `label: '   '` pendant que l'ecran affichait le glyphe neutre.
        return (formulaire.saisie(CHAMP_ETIQUETTE),
                formulaire.saisie(CHAMP_COMMENTAIRE))

    try:
        profil = hote(calibrer, dossier, formulaire.chemin_du_scan,
                      dpi=formulaire.dpi_valide, logger=logger,
                      demander_le_nom_et_le_commentaire=nommer,
                      confirmer_l_ecrasement=relais,
                      rappel_progression=rappel_progression)
    except CalibrationAnnulee as annulation:
        return PasseDeCalibration(refus=annulation, collision=relais.collision,
                                  issue=relais.issue,
                                  chaine=capte.get("chaine", ""))
    except REFUS_DU_COEUR as refus:
        return PasseDeCalibration(refus=refus, motif=motif_du_refus(refus),
                                  collision=relais.collision,
                                  issue=relais.issue,
                                  chaine=capte.get("chaine", ""))

    chemin = Path(profil.profile_path).resolve()
    if formulaire.devient_le_defaut:
        # « Devient le défaut » est un **acte de l'operateur** : il designe le
        # profil qu'il vient d'ecrire, exactement comme `--profil` le fait
        # depuis la ligne de commande (`cli.py:2099`). A `non`, rien n'est
        # inscrit -- « poser un defaut est une decision, pas un effet de bord ».
        #
        # **`source` est le PROFIL, jamais le scan** (corrige le 2026-09-06,
        # retour terrain d'Egan). `profile_designation.manifest_entry` en fait
        # `Path(source).name` et le persiste dans `project.json` sous
        # `designated_from`, aux deux cles -- `designated_profiles[]` et
        # `default_profile`. Le champ veut dire « le fichier de profil que
        # l'operateur a designe » : c'est ce que les deux autres sites du depot
        # y mettent (`scan_write.py`, qui passe le `.json` retenu, et
        # `profile_designation.import_designated_profile`, dont la source est
        # un `.json` par contrat). Ce site etait le SEUL du depot a y passer
        # autre chose, et ce qu'il y passait etait le scan : le manifeste
        # portait donc `designated_from = 'ma_planche.pdf'`.
        #
        # Ce n'est pas cosmetique -- `palier_projet.nom_du_profil` met
        # `designated_from` **en tete** de sa precedence, devant le `chain_id`,
        # et trois ecrans l'affichent. L'operateur lisait donc le nom de son
        # PDF comme nom de profil : mesure sur son scan reel, profil affiche
        # `HP envy Gambetta.pdf` la ou la feuille portait `hp envy Gambetta`.
        # Le corriger ICI plutot que par un `Path.stem` dans `manifest_entry`
        # est ce qui distingue une entree juste d'un symptome masque : le
        # `.name` y est **a bon droit**, et trois bancs l'assertent.
        designer_le_defaut(dossier, profil.document, project_path=Path(
            profil.profile_path), source=profil.profile_path,
            as_default=True)
    return PasseDeCalibration(
        profil=profil, collision=relais.collision, issue=relais.issue,
        chaine=capte.get("chaine", "") or getattr(profil, "chain_id", ""),
        # **La recalibration se lit du releve, pas d'une comparaison de
        # chaines** : le coeur n'a pose aucune collision -- sinon le relais
        # aurait ete appele --, et le fichier qu'il a ecrit etait deja la.
        recalibration=relais.collision is None and chemin in avant,
        date_precedente=date_du_fichier(avant.get(chemin)),
        date_ecrite=date_du_fichier(_mtime(chemin)))


def _mtime(chemin: Path) -> float | None:
    try:
        return chemin.stat().st_mtime
    except OSError:
        return None


# ===========================================================================
# `E3-9` -- l'ecran
# ===========================================================================

class EcranCalibrerLaChaine(CoutureExplorateur, Palier):
    """`E3-9` -- calibrer une chaine, et jamais une seule sortie.

    **L'explorateur est celui du depot, pas un second** (AC 8.4,
    `EPIC11-ARB-48`) : `E3-9` demande un chemin et n'etait dans la table
    d'aucun des cinq sites de l'arbitrage -- il a ete **oublie**, c'est le
    **sixieme site** et non une exception (ecart `H11`). Le clavier passe par
    :class:`~mixed_media_utility.tui.ecran_projet.CoutureExplorateur` : cet
    ecran ne recable aucune touche a la main.

    `calibrer` est **injecte et REQUIS**, sans defaut (finding `K3`) : l'ecran
    ne calibre rien lui-meme, il le demande. C'est ce qui garde le formulaire
    separable de la passe, et mesurable sans elle.

    **Cet ecran n'est pas cable dans le menu du Scan** : le cablage est le lot H
    de la story 11.6. La classe est exposee, elle n'est pas montee.
    """

    titre = PALIER_DE_L_ECRAN
    raccourcis = RACCOURCIS_CALIBRATE
    #: **La declaration qui fait entrer cet ecran dans l'ensemble borne** de
    #: `aide_de_champ.ECRANS_A_TABLE_D_AIDE` (AC 1.5, `EPIC11-ARB-198`).
    TABLE_D_AIDE = AIDE_PAR_CHAMP

    #: **La famille de memoire de session de cet explorateur.** Sans elle, cet
    #: ecran repartait de `Path.cwd()` a chaque ouverture, la ou les sites
    #: voisins reprennent l'operateur ou il en etait. Les deux derniers sites
    #: de `A_POSER` sont fermes ici, le meme jour que les six autres.
    FAMILLE_D_EXPLORATION = FAMILLE_MATIERE

    def __init__(self, dossier=None, *,
                 calibrer: Callable[[FormulaireDeCalibration], None],
                 mesurer=None) -> None:
        super().__init__()
        self.dossier = Path(dossier) if dossier is not None else None
        self._calibrer = calibrer
        self._mesurer = mesurer
        self.formulaire = FormulaireDeCalibration()
        self.zone = ZONE_FORMULAIRE
        # **Monte a la construction et non a l'ouverture**, comme `E3-1` et
        # `E3-5` : l'explorateur lit `Path.cwd()`, et le lire plus tard ferait
        # dependre le dossier de depart du moment ou l'on appuie.
        #
        # **Sans `selection_multiple`** : on calibre **une** page, et une
        # sequence de chemins n'a pas de sens ici.
        self.explorateur = Explorateur(montrer_fichiers=True,
                                       accepte=source_acceptable)
        self._etat_a_dire = ""
        #: `F1` : l'aide du champ courant (story 11.9, AC 1). Elle **remplace**
        #: la ligne blanche qui suit le titre : le cardinal de lignes du corps
        #: est donc le meme aide ouverte et aide fermee, et `E3-9` ne bouge pas
        #: d'un caractere tant qu'elle est fermee -- l'ecran ne dessine aucune
        #: consigne, et lui en inventer une serait un changement de dessin que
        #: personne n'a demande.
        self.aide = aide_de_champ.AideDeChamp(
            AIDE_PAR_CHAMP, formulaire=self.formulaire)
        #: La derniere passe annoncee, ou `None`. **Elle vit sur l'ecran et non
        #: dans la ligne d'etat** : « `poser_etat` seul se fait effacer par le
        #: dessin suivant », et une mesure posee en reaction a un evenement doit
        #: survivre au redessin.
        self.passe: PasseDeCalibration | None = None

    # -- lecture ------------------------------------------------------------

    def _appliquer_la_zone(self) -> None:
        """Poser la ligne de raccourcis de la zone courante.

        **`raccourcis` reste un ATTRIBUT, jamais une propriete** : la garde
        d'epic de `test_repli_ascii.py` lit `classe.raccourcis` au niveau de la
        CLASSE, et une propriete ferait echapper cet ecran a la mesure.

        **L'aide de champ tombe en quittant le formulaire** : entrer dans
        l'explorateur ne change aucun champ, donc la chute structurelle du
        mecanisme ne suffit pas la -- sans ce geste, l'aide reapparaitrait au
        retour sans que personne ne l'ait redemandee.
        """
        if self.zone != ZONE_FORMULAIRE:
            self.aide.fermer()
        if self.zone == ZONE_EXPLORATEUR:
            self.raccourcis = raccourcis_de_l_explorateur(self.explorateur)
            return
        # **Le pied dit le geste de la LIGNE COURANTE** (`EPIC11-ARB-158`) :
        # « on ecrit "Espace Oui/non" quand le curseur est sur ce champ ». Une
        # table plutot qu'une chaine de `if` : elle se lit d'un coup d'oeil, et
        # c'est elle que le banc confronte a l'ensemble des champs.
        self.raccourcis = PIED_PAR_CHAMP.get(self.formulaire.champ,
                                             RACCOURCIS_CALIBRATE)

    def valeur_du_champ(self, cle: str) -> str:
        """Ce que le champ affiche a droite de son libelle.

        Le glyphe `neutre` -- et jamais une chaine vide -- marque un champ non
        renseigne : `DESIGN.md` section 6 en fait le second canal de « rien
        ici », et une case vide se lit comme un defaut de rendu.
        """
        neutre = self.app.glyphes["neutre"]
        if cle == CHAMP_SCAN:
            chemin = self.formulaire.chemin_du_scan
            if chemin is None:
                return neutre
            utile = jetons.largeur_utile(self.app.size.width)
            place = utile - len(INDENT_DU_CURSEUR) - LARGEUR_DU_LIBELLE - 2
            return jetons.abreger_chemin(str(chemin), max(place, 1),
                                         self.app.ascii_seul)
        if cle == CHAMP_REPRISE:
            scan = self.formulaire.scan
            if scan is None or scan.dpi is None:
                return neutre
            return f"{dpi_lisible(scan.dpi)} {UNITE_DPI}"
        if cle == CHAMP_DEFAUT:
            return self.ligne_du_choix()
        if cle == CHAMP_VALIDER:
            return ACTION_VALIDER
        # Meme lecture que la mention et que ce qui part au coeur.
        return self.formulaire.saisie(cle) or neutre

    def ligne_du_choix(self) -> str:
        """`( ) oui    (•) non` -- un **champ de formulaire** (AC 8.6).

        `DESIGN.md` section 7.3 pose `(•) 16 bits ( ) 8 bits` comme la forme
        d'un champ, et `EPIC11-ARB-126` (« Flèche seule ! ») borne sa regle aux
        listes d'**issues**. Les deux glyphes ont leur repli ASCII
        (`(o)` / `( )`), donc le second canal survit au repli.

        **L'option retenue est SURLIGNEE** (`EPIC11-ARB-158`, Egan : « avec oui
        surligne »), et le surlignage double le glyphe plutot qu'il ne le
        remplace -- meme regle que la couleur en section 5.
        """
        table = self.app.glyphes
        retenu, libre = table["exclusif-retenu"], table["exclusif-libre"]
        pris = self.formulaire.devient_le_defaut
        oui = f"{retenu if pris else libre} {_surligne(CHOIX_OUI, pris)}"
        non = f"{libre if pris else retenu} {_surligne(CHOIX_NON, not pris)}"
        return f"{oui}{' ' * CREUX_DU_CHOIX}{non}"

    def valeur_de_l_aide(self, cle: str) -> str:
        """La **valeur du contexte courant** que l'aide de ce champ cite (AC 1.1).

        Elle dit ce que la ligne du champ **ne montre pas** : le nom du fichier
        la ou la ligne montre un chemin abrege, le verdict du coeur sur le dpi
        la ou la ligne montre la frappe, et le motif du refus sur la ligne
        d'action -- **lu de `motif_du_refus_de_partir`**, qui est deja la seule
        redaction de ce motif pour la mention et pour la ligne d'etat.

        **Aucune lecture de `self.app`** : mesurable sans terminal.
        """
        if cle == CHAMP_SCAN:
            chemin = self.formulaire.chemin_du_scan
            return AIDE_SANS_SCAN if chemin is None else chemin.name
        if cle == CHAMP_DPI:
            saisi = self.formulaire.saisie(CHAMP_DPI)
            if not saisi:
                return aide_de_champ.VALEUR_ABSENTE
            if self.formulaire.dpi_valide is None:
                return f"{saisi} — hors bornes"
            return saisi
        if cle == CHAMP_REPRISE:
            scan = self.formulaire.scan
            if scan is None or scan.dpi is None:
                return AIDE_SANS_MESURE
            return f"{dpi_lisible(scan.dpi)} {UNITE_DPI}"
        if cle == CHAMP_DEFAUT:
            return CHOIX_OUI if self.formulaire.devient_le_defaut else CHOIX_NON
        if cle == CHAMP_VALIDER:
            if self.formulaire.peut_calibrer:
                return AIDE_PRET_A_PARTIR
            return motif_du_refus_de_partir(self.formulaire)[0]
        return self.formulaire.saisie(cle) or aide_de_champ.VALEUR_ABSENTE

    def mention_du_champ(self, cle: str) -> str:
        """La colonne de droite d'un champ : ce qui manque, ou la mesure."""
        if cle == CHAMP_SCAN:
            return "" if self.formulaire.scan is not None else MENTION_REQUIS
        if cle == CHAMP_DPI:  # noqa: E501 -- garde le commentaire ci-dessous
            # **`.strip()`, et ce n'est pas de la coquetterie.** `Espace` est
            # desormais un geste annonce sur la ligne voisine (`Espace
            # Oui/non`) ; frappe ici par reflexe, elle tombait sur `frapper(" ")`
            # et rendait `dpi` VRAI. La ligne perdait alors **les deux** canaux
            # qui disaient « rien ici » -- le glyphe neutre et la mention
            # `requis` -- pendant que `peut_calibrer` restait faux. Un champ
            # requis qui se lit comme rempli et ne l'est pas (revue de vague B).
            return ("" if self.formulaire.saisie(CHAMP_DPI)
                    else MENTION_REQUIS_DPI)
        if cle == CHAMP_REPRISE:
            return mention_de_la_mesure(self.formulaire.scan)
        if cle == CHAMP_ETIQUETTE:
            # Meme lecture que la valeur dessinee (`saisie`) : sans elle, une
            # etiquette de blancs affichait le glyphe neutre -- qui dit VIDE --
            # pendant que cette mention disparaissait.
            return ("" if self.formulaire.saisie(CHAMP_ETIQUETTE)
                    else MENTION_ETIQUETTE_VIDE)
        if cle == CHAMP_COMMENTAIRE:
            return ("" if self.formulaire.saisie(CHAMP_COMMENTAIRE)
                    else MENTION_COMMENTAIRE)
        if cle == CHAMP_VALIDER:
            if self.formulaire.peut_calibrer:
                return ""
            return motif_du_refus_de_partir(self.formulaire)[0]
        return ""

    def ligne_de_champ(self, cle: str, utile: int) -> str:
        """Une ligne de formulaire : libelle, glyphe de focus, valeur, mention.

        Le glyphe `>` marque la ligne **au focus** (`DESIGN.md` section 7.3), et
        il ouvre sa colonne : les autres lignes portent un blanc a sa place,
        pour que les valeurs restent alignees quand le focus se deplace.
        """
        table = self.app.glyphes
        focus = table["invite"] if self.formulaire.champ == cle else " "
        gauche = (f"{INDENT_DU_CURSEUR}{LIBELLES[cle]:<{LARGEUR_DU_LIBELLE}}"
                  f"{focus} {self.valeur_du_champ(cle)}")
        return _cale_a_droite(gauche, self.mention_du_champ(cle), utile)

    def ligne_de_fait(self, libelle: str, valeur: str) -> str:
        """Une ligne du panneau qui ne se saisit pas : ni focus, ni cible `Tab`.

        La colonne de la valeur est **la meme** que celle des champs : deux
        colonnes differentes a deux lignes d'ecart feraient lire le panneau
        comme un second formulaire.
        """
        return f"{INDENT_DU_CURSEUR}{libelle:<{LARGEUR_DU_LIBELLE}}  {valeur}"

    def ligne_du_profil(self) -> str:
        """Ce que la ligne `Profil` porte -- **le chemin que le coeur a rendu**.

        Tant qu'aucune passe n'a abouti, le chemin n'est pas connu et ne se
        devine pas : il depend du radical, que `write_profile` compose seul, et
        le recomposer ici serait la seconde redaction que l'AC 8.2 ferme.
        """
        if self.passe is None or self.passe.chemin is None:
            return PROFIL_PAS_ENCORE_ECRIT
        return str(self.passe.chemin)

    def ligne_de_remplacement(self) -> str:
        """Ce que la ligne `Remplace` porte (AC 8.1, premiere situation).

        **Sans `▲` et sans question** : une recalibration de la meme chaine est
        « un remplacement voulu » que le coeur documente depuis 5.22, et poser
        la question ici serait l'invite qui apprend a repondre oui sans lire.
        """
        if self.passe is None:
            return ""
        if self.passe.recalibration:
            return PHRASE_RECALIBRATION.format(
                date=self.passe.date_precedente or self.passe.date_ecrite)
        if self.passe.a_ecrit:
            return PHRASE_PROFIL_NEUF
        return ""

    def lignes_du_formulaire(self, utile: int) -> list[str]:
        corps = ["", INDENT_DU_TEXTE + TITRE,
                 aide_de_champ.ligne_de_tete_de(
                     self, self.formulaire.champ, utile=utile,
                     indent=INDENT_DU_TEXTE,
                     ascii_seul=self.app.ascii_seul)]
        for cle in self.formulaire.champs():
            if cle == CHAMP_ETIQUETTE:
                # La ligne vide separe ce qu'on a scanne de ce qu'on va
                # nommer : ce sont deux questions, et la reprise appartient a
                # la premiere -- elle reste donc collee au champ de dpi.
                corps.append("")
            if cle in (CHAMP_DEFAUT, CHAMP_VALIDER):
                # Les deux lignes du bas vivent **sous le filet**, avec ce
                # qu'elles decident : le choix du defaut porte sur le profil
                # ecrit, et `Valider` est le geste qui l'ecrit.
                continue
            corps.append(self.ligne_de_champ(cle, utile))
        corps += ["", filet(utile, TITRE_DE_LA_SORTIE, self.app.ascii_seul), ""]
        if self.passe is not None and self.passe.chaine:
            # **L'identite de chaine est DERIVEE par le coeur**, et elle ne
            # traverse qu'a un seul endroit : le rappel de nommage. L'ecran la
            # nomme (AC 8.1, « recalibration de la chaine X »), il ne la
            # recompose jamais -- `scan_chain.derive_chain_id` est la seule
            # redaction de cette recette, et une seconde ferait un profil que
            # plus aucun scan ne retrouve.
            corps.append(self.ligne_de_fait(LIBELLE_CHAINE, self.passe.chaine))
        corps.append(self.ligne_de_fait(LIBELLE_PROFIL, self.ligne_du_profil()))
        remplacement = self.ligne_de_remplacement()
        if remplacement:
            corps.append(self.ligne_de_fait(LIBELLE_REMPLACE, remplacement))
        corps.append(self.ligne_de_champ(CHAMP_DEFAUT, utile))
        # **La ligne d'action ferme le formulaire** (`EPIC11-ARB-158`, point 4).
        # La ligne vide qui la precede n'est pas decorative : elle separe ce
        # qu'on decide de ce qui l'execute, et sans elle `Valider` se lit comme
        # une septieme question.
        corps += ["", self.ligne_de_champ(CHAMP_VALIDER, utile)]
        return corps

    def lignes(self) -> list[str]:
        if self.zone == ZONE_EXPLORATEUR:
            # **Par mots-cles, et la largeur BRUTE** : `Explorateur.lignes`
            # prend `(largeur, titre, libelle, ascii_seul)`, et l'appeler
            # positionnellement poserait `ascii_seul` dans `titre`.
            return self.explorateur.lignes(
                self.app.size.width, titre=TITRE, libelle=LIBELLE_SCAN,
                ascii_seul=self.app.ascii_seul)
        return self.lignes_du_formulaire(
            jetons.largeur_utile(self.app.size.width))

    def etat(self) -> str:
        """La ligne d'etat : une **mesure**, jamais une touche ni un conseil.

        `EPIC11-ARB-56`. Apres une recalibration, elle porte **les deux dates**
        -- l'ancienne et la nouvelle --, ce que l'AC 8.1 demande nommement ; et
        elle ne porte aucun `▲`, parce qu'il n'y a rien a avertir.
        """
        if self._etat_a_dire:
            return self._etat_a_dire
        if self.zone == ZONE_EXPLORATEUR:
            return self.explorateur.etat(
                jetons.largeur_utile(self.app.size.width),
                self.app.ascii_seul)
        if self.passe is not None and self.passe.a_ecrit:
            if self.passe.recalibration:
                return ETAT_RECALIBRATION.format(
                    ancienne=self.passe.date_precedente,
                    nouvelle=self.passe.date_ecrite)
            return ETAT_PROFIL_ECRIT.format(
                date=self.passe.date_ecrite,
                chemin=Path(self.passe.chemin).name)
        if self.formulaire.scan is not None and not self.formulaire.dpi:
            return jetons.marque("absent", PHRASE_DPI_REQUIS,
                                 self.app.ascii_seul)
        return ""

    # -- rendu ---------------------------------------------------------------

    def contenu(self) -> list[Widget]:
        self._corps = Static("", id="corps-scan-calibrate")
        return [Vertical(self._corps, id="centre-scan-calibrate")]

    def rafraichir(self) -> None:
        if not self._assez_grand_au_dernier_dessin:
            return
        utile = jetons.largeur_utile(self.app.size.width)
        rang = (self.explorateur.rang_du_curseur()
                if self.zone == ZONE_EXPLORATEUR else None)
        self._corps.update(jetons.peindre(
            [jetons.ajuster(ligne, utile, self.app.ascii_seul)
             for ligne in self.lignes()],
            ascii_seul=self.app.ascii_seul, sans_couleur=self.app.sans_couleur,
            ligne_du_curseur=rang))
        self.poser_etat(self.etat())
        super().rafraichir()

    def on_mount(self) -> None:
        self._appliquer_la_zone()
        self.rafraichir()

    def annoncer(self, passe: PasseDeCalibration) -> None:
        """Poser ce qu'une passe a produit, **et le faire survivre au redessin**.

        La passe vit sur l'ecran et non dans la ligne d'etat : « `poser_etat`
        seul se fait effacer par le dessin suivant », et une mesure posee en
        reaction a un evenement doit survivre au redessin -- c'est l'ajout du
        lot E de la 11.5, paye la-bas.
        """
        self.passe = passe
        self._etat_a_dire = ""
        if passe.refus is not None:
            # **Le motif du coeur, verbatim** (`EPIC11-ARB-30`) : c'est deja
            # une phrase pour l'operateur, et la resumer la detruirait.
            self._etat_a_dire = jetons.marque(
                "absent", str(passe.refus),
                getattr(self.app, "ascii_seul", False))

    # -- navigation ----------------------------------------------------------

    def on_key(self, evenement) -> None:
        if self.traiter(evenement.key, getattr(evenement, "character", None)):
            evenement.stop()
            self.rafraichir()

    def traiter(self, touche: str, caractere: str | None = None) -> bool:
        """Mesurable sans clavier, comme tous les ecrans du depot.

        **Le pied se repose a CHAQUE touche, pas seulement au changement de
        zone** (`EPIC11-ARB-158`). Il ne l'etait qu'au changement de zone tant
        que la ligne de raccourcis etait une constante ; depuis qu'elle depend
        de la LIGNE COURANTE, un `↓` qui deplace le curseur doit la reposer.
        Defaut mesure au produit le 2026-09-01, et invisible au banc : le banc
        appelait `_appliquer_la_zone` a la main, donc il mesurait la table du
        pied et non ce que l'operateur lit. Un test qui appelle le mecanisme
        qu'il veut mesurer ne mesure que lui-meme.
        """
        if self.zone == ZONE_EXPLORATEUR:
            traite = self._traiter_l_explorateur(touche, caractere)
            self._appliquer_la_zone()
            return traite
        self._etat_a_dire = ""
        traite = self._traiter_le_formulaire(touche, caractere)
        self._appliquer_la_zone()
        return traite

    def _traiter_le_formulaire(self, touche: str,
                               caractere: str | None = None) -> bool:
        """Le clavier du formulaire seul. Separe pour que `traiter` puisse
        reposer le pied **quelle que soit la branche prise**."""
        if touche == "f1":
            # **`F1` est consommee ICI quand le focus est sur un champ**, et
            # elle ne l'est pas autrement (AC 1.4) : dans l'explorateur, elle
            # remonte a la liaison applicative, qui ouvre le manuel des
            # raccourcis. Les deux volets comptent autant l'un que l'autre --
            # sans le premier, le manuel s'ouvrirait par-dessus le formulaire ;
            # sans le second, il ne s'ouvrirait jamais d'ici.
            return self.aide.basculer(self.formulaire.champ)
        if touche in ("down", "up"):
            # **Le geste de navigation** (`EPIC11-ARB-158`) : « d'un champ a
            # l'autre avec les fleches haut-bas ».
            return self.formulaire.avancer(1 if touche == "down" else -1)
        if touche == "tab":
            # Synonyme **non annonce** : Egan a retire `Tab` de la ligne de
            # raccourcis, pas du clavier. Une touche universelle de formulaire
            # qui cesserait de repondre est une regression pour qui l'a dans
            # les doigts ; l'annoncer sans qu'elle marche serait le defaut `I8`.
            return self.formulaire.avancer()
        if touche == "space" and self.formulaire.champ == CHAMP_DEFAUT:
            # **Et SEULEMENT sur cette ligne.** Sur les trois champs de saisie,
            # une espace est un CARACTERE qui doit s'ecrire : `EPIC11-ARB-68`
            # (« toute lettre imprimable est du texte a cote d'un champ de
            # saisie ») vaut aussi pour l'espace, et un commentaire est
            # precisement l'endroit ou l'on en tape. La garde est donc sur le
            # champ, jamais sur la touche seule.
            return self.formulaire.basculer_le_defaut()
        if touche == "enter":
            return self._valider_le_formulaire()
        if touche == "backspace":
            return self.formulaire.effacer()
        if caractere and caractere.isprintable():
            # **Aucune lettre n'est un raccourci ici** (`EPIC11-ARB-68`). Hors
            # d'un champ de saisie, la frappe est **consommee** plutot que de
            # remonter au binding applicatif `q`.
            self.formulaire.frapper(caractere)
            return True
        return False

    def _valider_le_formulaire(self) -> bool:
        """Ce que `⏎` fait, champ par champ. **Une seule ligne lance la passe.**

        `EPIC11-ARB-158` : « la validation avec Entree n'est pas claire ».
        Elle ne l'etait pas parce que `⏎` lancait la calibration depuis
        n'importe quel champ de saisie -- taper le nom de la chaine puis
        valider par reflexe partait dans une passe de plusieurs minutes.
        Desormais `⏎` fait **le geste de sa ligne**, et seule la ligne
        `Valider` lance.

        Sur les trois champs de saisie, il n'y a pas de geste propre : `⏎` y
        **descend**, ce qui est la convention de tout formulaire et ne surprend
        personne. Il n'y est donc jamais inerte -- « une touche annoncee qui ne
        fait rien et ne dit rien est indistinguable d'un clavier casse » --,
        et le pied ne l'annonce que la ou il fait autre chose que descendre.
        """
        if self.formulaire.champ == CHAMP_SCAN:
            return self._ouvrir_l_explorateur()
        if self.formulaire.champ == CHAMP_REPRISE:
            return self.formulaire.reprendre_la_mesure()
        if self.formulaire.champ == CHAMP_DEFAUT:
            return self.formulaire.basculer_le_defaut()
        if self.formulaire.champ != CHAMP_VALIDER:
            return self.formulaire.avancer()
        if not self.formulaire.peut_calibrer:
            # **L'action principale reste inaccessible**, et elle DIT pourquoi :
            # une touche annoncee qui ne fait rien et ne dit rien est
            # indistinguable d'un clavier casse.
            self._etat_a_dire = jetons.marque(
                "absent", motif_du_refus_de_partir(self.formulaire)[1],
                self.app.ascii_seul)
            return True
        self._calibrer(self.formulaire)
        return True

    def _ouvrir_l_explorateur(self) -> bool:
        # `reprendre_la_memoire_de_session` relit elle-meme quand elle deplace ;
        # le `relire` qui suit reste pour le cas ou elle ne deplace rien -- le
        # dossier a pu changer sous nos pieds depuis la derniere visite.
        self.reprendre_la_memoire_de_session()
        self.explorateur.relire()
        self.zone = ZONE_EXPLORATEUR
        self._appliquer_la_zone()
        return True

    # -- les deux gestes que la couture laisse a l'ecran ----------------------

    def _sortir_de_l_explorateur(self) -> bool:
        """Ou mene `Échap` : au formulaire, jamais d'un dossier vers son parent
        (`EPIC11-ARB-2`)."""
        self.zone = ZONE_FORMULAIRE
        self._appliquer_la_zone()
        return True

    def _valider_l_explorateur(self) -> None:
        """Ce que `⏎` fait de la cible : **il la mesure, il n'ingere rien**."""
        cible = self.explorateur.valider()
        if cible is None:
            self._etat_a_dire = jetons.marque(
                "substitute", "rien a valider", self.app.ascii_seul)
            return
        try:
            scan = designer(cible, mesurer=self._mesurer)
        except scan_ingest.ScanIngestError as refus:
            # **Le motif du coeur, verbatim** (`EPIC11-ARB-30`). L'ecran reste
            # sur l'explorateur : la cible est fautive, pas le geste.
            self._etat_a_dire = jetons.marque("absent", str(refus),
                                              self.app.ascii_seul)
            return
        self.formulaire.poser_le_scan(scan)
        self.zone = ZONE_FORMULAIRE
        self._appliquer_la_zone()


# ===========================================================================
# Les deux points de jugement -- jamais un ecran sans issue
# ===========================================================================

class EcranDeJugement(Palier):
    """Le tronc commun des deux points de jugement de `E3-9`.

    Un titre, une phrase du coeur, un `ChoixExclusif`. **Il n'existe pas
    d'instance a zero issue** : `ChoixExclusif.__post_init__` en exige deux, et
    cet invariant n'est pas reecrit ici (AC 8.3).

    `retenir` est **injecte et REQUIS** (finding `K3`) : un point de jugement
    qui ne sait pas a qui rendre son issue est un cul-de-sac.
    """

    titre = PALIER_DE_L_ECRAN
    raccourcis = RACCOURCIS_DU_CHOIX

    #: Un passage : on y decide, puis on en sort.
    TRANSITOIRE = True

    def __init__(self, titre_du_choix: str, phrase: str, choix: ChoixExclusif,
                 *, retenir: Callable[[Issue], None]) -> None:
        super().__init__()
        self.titre_du_choix = titre_du_choix
        self.phrase = phrase
        self.choix = choix
        self._retenir = retenir

    def lignes(self) -> list[str]:
        ascii_seul = self.app.ascii_seul
        utile = jetons.largeur_utile(self.app.size.width)
        corps = ["", INDENT_DU_TEXTE + self.titre_du_choix, ""]
        corps += [INDENT_DU_CURSEUR + ligne
                  for ligne in jetons.envelopper(
                      self.phrase, utile - len(INDENT_DU_CURSEUR), ascii_seul)]
        corps.append("")
        corps += [INDENT_DU_CURSEUR + ligne
                  for ligne in self.choix.rendu(ascii_seul)]
        return corps

    def rang_du_curseur(self) -> int | None:
        """Le rang **rendu** de la ligne du curseur.

        Il est **derive** du nombre de lignes de tete et non compte a la main :
        deux comptes divergeraient a la premiere ligne inseree, et le curseur se
        peindrait alors sur une autre issue sans que rien ne le dise.
        """
        tete = len(self.lignes()) - len(self.choix.issues)
        return tete + self.choix.curseur

    def contenu(self) -> list[Widget]:
        self._corps = Static("", id="corps-jugement-calibrate")
        return [Vertical(self._corps, id="centre-jugement-calibrate")]

    def rafraichir(self) -> None:
        if not self._assez_grand_au_dernier_dessin:
            return
        utile = jetons.largeur_utile(self.app.size.width)
        self._corps.update(jetons.peindre(
            [jetons.ajuster(ligne, utile, self.app.ascii_seul)
             for ligne in self.lignes()],
            ascii_seul=self.app.ascii_seul, sans_couleur=self.app.sans_couleur,
            ligne_du_curseur=self.rang_du_curseur()))
        self.poser_etat(self.etat())
        super().rafraichir()

    def etat(self) -> str:
        """Une **mesure** : combien d'issues, et combien ecrivent.

        `EPIC11-ARB-56` : aucune touche, aucun conseil, aucun motif de
        conception. Voir :func:`etat_du_choix`.
        """
        return etat_du_choix(self.choix)

    def on_mount(self) -> None:
        self.rafraichir()

    def on_key(self, evenement) -> None:
        if self.traiter(evenement.key, getattr(evenement, "character", None)):
            evenement.stop()
            self.rafraichir()

    def traiter(self, touche: str, caractere: str | None = None) -> bool:
        if touche in ("up", "down"):
            self.choix.deplacer(-1 if touche == "up" else 1)
            return True
        if touche == "enter":
            issue = self.choix.valider()
            if issue is not None:
                self._retenir(issue)
            return True
        if caractere and caractere.isprintable():
            # La frappe est **consommee** : la ligne de raccourcis n'annonce
            # aucune sortie par lettre, et laisser remonter `q` fermerait
            # l'application sur une touche que rien n'annonce.
            return True
        return False


class EcranCollisionDeProfil(EcranDeJugement):
    """Le point de jugement de la vraie collision (AC 8.1, seconde situation).

    Les **trois** issues d'`EPIC11-ARB-89`, dont une seule ecrase. Le radical et
    l'occupant viennent du coeur et voyagent **verbatim** : l'ecran ne les
    reformule pas, il les relaie.
    """

    def __init__(self, collision: CollisionDeProfil, *,
                 retenir: Callable[[Issue], None]) -> None:
        modele = (PHRASE_DE_LA_COLLISION_ILLISIBLE if not collision.occupant
                  else PHRASE_DE_LA_COLLISION)
        super().__init__(
            TITRE_DE_LA_COLLISION,
            modele.format(radical=collision.radical,
                          occupant=collision.occupant),
            choix_de_la_collision(collision), retenir=retenir)
        self.collision = collision


class EcranChaineDejaCalibree(EcranDeJugement):
    """Le point de jugement d'`EPIC11-ARB-261`, et il n'existait pas.

    Le balayage inverse (`calibration_profile.profils_de_la_chaine`) etait
    ecrit, juste, et **cable nulle part** -- les trois couches de la revue du
    2026-09-07 l'ont trouve independamment. Son docstring disait deja ce qui
    manquait : « elle ne decide rien : elle rend, l'appelant avertit et propose
    les deux issues ». Cet ecran est cet appelant.

    Ce qu'il ferme, verbatim du docstring du coeur : « recalibrer une chaine
    deja calibree sous un libelle different ecrivait un second fichier,
    l'ancien devenait orphelin **sans un mot**, et l'ecran annoncait "nouveau
    profil" sur ce qui est une recalibration ».

    **Deux issues, et l'ecran monte APRES l'ecriture.** Le profil mesure est
    donc a l'abri quoi qu'il arrive : c'est le sort de l'ANCIEN qui se tranche,
    jamais celui de la mesure qu'on vient de prendre. `EPIC11-ARB-89` est tenu
    des deux cotes -- aucun blocage sec (les deux issues sortent), aucune
    destruction silencieuse (le retrait passe par une issue `ecrit=True`).
    """

    def __init__(self, passe: "PasseDeCalibration", autres: list[Path], *,
                 retenir: Callable[[Issue], None]) -> None:
        super().__init__(TITRE_DE_LA_CHAINE_DEJA_CALIBREE,
                         phrase_de_la_chaine_deja_calibree(passe, autres),
                         choix_de_la_chaine_deja_calibree(), retenir=retenir)
        self.passe = passe
        self.autres = list(autres)


class EcranRefusDeCalibration(EcranDeJugement):
    """Le refus, et **il n'est jamais nu** (AC 8.3, AC 8.7).

    Aucun profil n'a ete ecrit -- c'est le contrat de `calibrate`, qui « ne se
    replie pas sur un profil vide » --, et l'ecran ne dit **jamais** « echec »
    (`DESIGN.md` section 9) : il nomme ce qui n'a pas eu lieu, porte le message
    du coeur verbatim, et offre **deux** issues.

    C'est ce qui ferme le troisieme chemin du coeur, celui qui n'a aucune issue
    a lui : « l'empreinte differenciante n'a pas separe les deux ; ecraser
    ferait perdre un profil qu'aucune autre trace ne porte ». Renommer
    l'etiquette change le radical vise, donc en sort.
    """

    def __init__(self, passe: PasseDeCalibration, *,
                 retenir: Callable[[Issue], None]) -> None:
        super().__init__(TITRE_DU_REFUS, str(passe.refus),
                         choix_de_l_impasse(passe.motif), retenir=retenir)
        self.passe = passe



# ===========================================================================
# `E3-9c` -- LE RESULTAT (2026-09-06). Consommer la mire en a un, comme la
#            produire (`E5-6e`)
# ===========================================================================
#
# Retour terrain d'Egan : « Calibration : pas d'ecran de succes et on revient
# directement a la page pour lancer une calibration. Incoherent avec le reste. »
# Il a raison sur la comparaison la plus parlante : le geste **symetrique** --
# produire la mire, `atelier_pdf_calibration.EcranMireEcrite` (`E5-6e`) -- en a
# un depuis le lot H de la 11.1. Consommer la mire n'en avait pas.
#
# **Le court-circuit etait structurel, et non un ecran oublie** :
# `atelier_scan_parcours.ouvrir_ce_que_le_refus_demande` commence par
# `if passe.refus is None: return None`. La conclusion d'une passe n'avait
# **qu'une** branche de navigation, et elle etait reservee au REFUS.
#
# **`atelier_scan_resultat` n'est PAS reutilisable ici**, et le verifier a coute
# moins cher que de le decouvrir en revue : ses fonctions sont typees sur un
# `RapportDEcriture` -- frames ecrites, profondeur de sortie, dossiers de lots.
# Rien de cela n'existe pour une calibration, qui ecrit **un** fichier JSON.
# C'est donc `EcranResultat` du module partage qui est sous-classe, comme
# `EcranMireEcrite` et `EcranResultatDuScan` le font tous les deux.
#
# **Aucun appel de coeur n'est ajoute** : tout ce qui suit se lit de la
# `PasseDeCalibration` que `consigner` a deja rendue.

#: Le titre du cartouche. **Le meme mot que `E5-6e`** (`Écrit`) : les deux
#: ecrans disent la meme chose du meme objet, aux deux bouts de sa vie.
TITRE_DU_RESULTAT = "Écrit"

#: Les libelles propres au cartouche du resultat. Les quatre autres --
#: `Profil`, `Chaîne`, `Remplace`, `Commentaire` -- sont **ceux du formulaire**
#: et de `E3-5`, lus et non recopies : l'operateur vient de les lire une ligne
#: plus haut, et deux redactions divergeraient au premier renommage.
LIBELLE_PASTILLES_DU_RESULTAT = "Pastilles"
LIBELLE_DOSSIER_DU_RESULTAT = "Emplacement"
#: Le libelle de l'ecart brut. **`E3-5` n'en a pas** -- il plie la divergence
#: dans sa ligne « Posé le », qui est une carte de liste et non un cartouche --,
#: et la MESURE, elle, est lue de lui (`divergence_brute`) : c'est la valeur
#: qui ne doit pas etre redigee deux fois, pas le mot de la colonne de gauche.
LIBELLE_DIVERGENCE_DU_RESULTAT = "Écart brut"

#: Ce que la ligne « Pastilles » porte : **lues et retenues**, deux cardinaux
#: mesures et jamais un seul. Le second seul ferait croire qu'aucune n'a ete
#: ecartee, le premier seul cacherait qu'on en a ecarte.
PASTILLES_DU_RESULTAT = "{lues} lues · {retenues} retenues"

#: Ce que la mire consommee sert, **dans le corps du compte rendu et pas en
#: ligne d'etat** : meme geste et meme motif que `PROSE_DE_LA_MIRE` de `E5-6e`
#: (`EPIC11-ARB-56` interdirait un conseil d'usage en ligne d'etat). Le seul
#: moment ou l'operateur peut apprendre ce que son profil va servir est celui
#: ou il vient de le produire.
PROSE_DU_PROFIL = (
    "Ce profil corrige les planches de cette chaîne au scan : il se",
    "choisit à l'étape « Calibration » de la détection.",
)

#: Les trois suites, **et chacune mene ailleurs**. `EcranResultat` ajoute
#: lui-meme `Retour aux ateliers` en dernier s'il manque (`EPIC11-ARB-13`) : on
#: ne l'ecrit donc pas ici, sous peine de le voir deux fois.
SUITE_DOSSIER_DES_PROFILS = "Ouvrir le dossier"
SUITE_AUTRE_CHAINE = "Calibrer une autre chaîne"
SUITE_DETECTER = "Détecter des planches"

#: Ce que la ligne d'etat du resultat porte. **Des chiffres mesures**, jamais
#: un majorant : le travail est fait.
ETAT_RESULTAT_NEUF = "profil écrit le {date} · {pastilles} pastilles retenues"
ETAT_RESULTAT_RECALIBRE = (
    "profil posé le {ancienne} · remplacé le {nouvelle} · "
    "{pastilles} pastilles retenues")



def suites_du_resultat() -> list[str]:
    """Les trois suites de l'ecran de resultat. **Ensemble exact et ordonne.**

    Elles nomment ce que l'operateur peut faire **de ce profil-la**, jamais un
    menu generique : ouvrir le dossier ou il vient d'etre ecrit, recommencer
    sur une autre chaine, ou passer a ce que le profil sert -- detecter des
    planches. C'est la forme d'`E5-6e` et d'`E3-8`, et il n'y en a pas d'autre
    dans le depot.
    """
    return [SUITE_DOSSIER_DES_PROFILS, SUITE_AUTRE_CHAINE, SUITE_DETECTER]


def pastilles_du_resultat(passe: PasseDeCalibration) -> str:
    """« 164 lues · 161 retenues », ou `""` quand rien n'est mesure.

    Les deux cardinaux sont **lus de la correction ajustee**
    (`lot_correction.read_patch_count` / `.retained_patch_count`), jamais
    recalcules : c'est le coeur qui les a comptes sur la feuille.

    Rend `""` -- donc une ligne **omise** -- plutot que `0 lues · 0 retenues`
    quand la passe n'a pas de correction a montrer : « un champ non mesure est
    omis, jamais rendu faux » (`DESIGN.md` section 3).
    """
    correction = getattr(passe.profil, "lot_correction", None)
    lues = getattr(correction, "read_patch_count", None)
    retenues = getattr(correction, "retained_patch_count", None)
    if not isinstance(lues, int) or not isinstance(retenues, int):
        return ""
    return PASTILLES_DU_RESULTAT.format(lues=lues, retenues=retenues)


def panneau_du_resultat(passe: PasseDeCalibration, dossier,
                        largeur: int = jetons.LARGEUR_PLANCHER,
                        ascii_seul: bool = False) -> Panneau:
    """Le cartouche du resultat : ce que la passe a **reellement** ecrit.

    La premiere ligne est le fichier ecrit, ouverte par le glyphe de l'etat
    `complete` -- c'est le sujet du compte rendu, et le glyphe le double comme
    `DESIGN.md` section 5 l'exige. La ligne vide qui la suit est une
    `LigneChiffree` sans libelle ni valeur : `Panneau` ne sait pas espacer ses
    lignes, et c'est la forme la moins couteuse pour rendre la respiration que
    les cartouches de resultat du depot portent tous.

    **Le nom du fichier est abrege ICI, a la construction**, et pour la raison
    exacte que `atelier_pdf_calibration.panneau_du_resultat` donne :
    `EcranResultat` consomme `Panneau.rendu` en trois endroits, et surcharger
    le premier seul ferait diverger les deux autres.

    **Chaque ligne non mesuree est OMISE, jamais rendue a zero ou a vide** : un
    profil sans commentaire n'affiche pas de ligne `Commentaire`, une passe qui
    ne remplace rien affiche :data:`PHRASE_PROFIL_NEUF` -- qui est un fait, pas
    un vide -- et une divergence non mesurable n'affiche pas `0,0 ΔE`.
    """
    tete = f"{jetons.glyphes(ascii_seul)['complete']} "
    budget = (jetons.largeur_de_cartouche(largeur) - jetons.CREUX_MINIMAL
              - jetons.colonnes(tete))
    nom = (jetons.abreger_nom(Path(passe.chemin).name, max(budget, 0),
                              ascii_seul)
           if passe.chemin is not None else "")
    lignes = [LigneChiffree(tete + nom, ""), LigneChiffree("", "")]
    if passe.chaine:
        lignes.append(LigneChiffree(LIBELLE_CHAINE, passe.chaine))
    etiquette = getattr(passe.profil, "etiquette", "") or ""
    if etiquette:
        lignes.append(LigneChiffree(LIBELLE_ETIQUETTE, etiquette))
    commentaire = getattr(passe.profil, "commentaire", "") or ""
    if commentaire:
        lignes.append(LigneChiffree(LIBELLE_COMMENTAIRE, commentaire))
    pastilles = pastilles_du_resultat(passe)
    if pastilles:
        lignes.append(LigneChiffree(LIBELLE_PASTILLES_DU_RESULTAT, pastilles))
    # **La divergence est celle du profil ECRIT**, relue par la redaction
    # unique de `E3-5` (`divergence_brute`) et jamais recalculee ici : c'est
    # `acceptance.mean_delta_e_before`, l'ecart moyen des pastilles avant toute
    # correction, et le seul champ du document qui reponde a la question.
    divergence = divergence_brute(getattr(passe.profil, "document", None),
                                  ascii_seul)
    if divergence:
        lignes.append(LigneChiffree(LIBELLE_DIVERGENCE_DU_RESULTAT, divergence))
    lignes.append(LigneChiffree(
        LIBELLE_REMPLACE,
        PHRASE_RECALIBRATION.format(date=passe.date_precedente)
        if passe.recalibration else PHRASE_PROFIL_NEUF))
    lignes.append(LigneChiffree(LIBELLE_DOSSIER_DU_RESULTAT,
                                str(dossier_des_profils(dossier))))
    return Panneau(TITRE_DU_RESULTAT, lignes, noms=list(PROSE_DU_PROFIL))


def ligne_d_etat_du_resultat(passe: PasseDeCalibration,
                             ascii_seul: bool = False) -> str:
    """`●  profil écrit le 06/09 · 161 pastilles retenues`.

    **Les deux regimes de l'AC 8.1 se disent differemment**, et c'est la meme
    distinction que la ligne d'etat de `E3-9` porte deja
    (:data:`ETAT_RECALIBRATION` contre :data:`ETAT_PROFIL_ECRIT`) : une
    recalibration nomme les deux dates, une ecriture neuve n'en a qu'une. Aucun
    avertissement dans l'un ni dans l'autre -- une recalibration « se dit sans
    triangle et sans question ».

    Le cardinal des pastilles **retenues** est la seule mesure ajoutee : c'est
    ce qui dit si la feuille a ete bien lue, et la ligne d'etat porte une
    mesure ou rien (`EPIC11-ARB-56`).
    """
    glyphe = jetons.glyphes(ascii_seul)["complete"]
    correction = getattr(passe.profil, "lot_correction", None)
    retenues = getattr(correction, "retained_patch_count", None)
    if passe.recalibration:
        corps = ETAT_RESULTAT_RECALIBRE.format(
            ancienne=passe.date_precedente, nouvelle=passe.date_ecrite,
            pastilles=retenues)
    else:
        corps = ETAT_RESULTAT_NEUF.format(date=passe.date_ecrite,
                                          pastilles=retenues)
    if not isinstance(retenues, int):
        # **La part non mesuree est RETIREE, pas rendue a `None`** : « un champ
        # non mesure est omis, jamais rendu faux ». La coupe se fait sur le
        # separateur, qui est le seul point de jointure de cette ligne.
        corps = SEPARATEUR_DE_CARTE.join(
            part for part in corps.split(SEPARATEUR_DE_CARTE)
            if "None" not in part)
    return f"{glyphe}  {corps}"


class EcranCalibrationEcrite(EcranResultat):
    """L'`EcranResultat` du depot, avec le bandeau de la calibration.

    Une sous-classe et **rien d'autre**, exactement comme `EcranMireEcrite`
    (`E5-6e`) et `EcranResultatDuScan` (`E3-8`) : le cartouche, les suites
    navigables, la ligne de raccourcis contextuelle et `Tab journal` sont ceux
    de `execution.EcranResultat`. Un ecran neuf divergerait au premier
    ajustement de la barre ou de la ligne de raccourcis, et `execution.py` est
    un module partage qu'on ne touche pas pour un atelier.

    Ce qu'elle redonne tient en un attribut : le **titre**, segment du milieu du
    bandeau. La base porte `Resultat`, qui nommerait l'ecran au lieu du geste --
    l'operateur perdrait, sur le seul ecran ou il en a besoin, l'indication
    d'ou sort ce profil.
    """

    titre = PALIER_DE_L_ECRAN


def ouvrir_le_resultat(app, passe: PasseDeCalibration, dossier, *,
                       sur_suite: Callable[[str], None],
                       journal=None) -> EcranCalibrationEcrite:
    """Monter l'ecran de resultat. `sur_suite` est **REQUIS**.

    Un `Callable | None = None` assorti d'un `if ... is not None` transforme
    l'oubli du cablage en **silence** -- c'est le finding `K3`, paye quatre fois
    dans cet epic, et il a mordu exactement sur un ecran de resultat dont les
    suites etaient navigables et decoratives.

    `journal` est celui de la passe qui vient de finir. Il est **facultatif et
    il le reste** : sans lui, la ligne de raccourcis n'annonce pas
    `Tab journal` et ne le traite pas, ce qui est la seule facon de ne pas
    annoncer une touche inerte (finding `I8`).
    """
    ascii_seul = getattr(app, "ascii_seul", False)
    ecran = EcranCalibrationEcrite(
        panneau_du_resultat(passe, dossier, app.size.width, ascii_seul),
        suites_du_resultat(), sur_suite=sur_suite, journal=journal)
    app.descendre(ecran)
    # **`poser_etat` APRES le montage**, jamais avant : la ligne d'etat est
    # posee sur l'ecran monte, et un ecran pas encore empile la perdrait au
    # premier dessin.
    ecran.poser_etat(ligne_d_etat_du_resultat(passe, ascii_seul))
    return ecran


__all__ = [
    "AIDE_PAR_CHAMP",
    "CHAMPS_DE_SAISIE",
    "CHAMP_COMMENTAIRE",
    "CHAMP_DEFAUT",
    "CHAMP_DPI",
    "CHAMP_ETIQUETTE",
    "CHAMP_REPRISE",
    "CHAMP_SCAN",
    "CHOIX_NON",
    "CHOIX_OUI",
    "CLE_ABANDONNER",
    "CLE_ANNULER",
    "CLE_ECRASER",
    "CLE_GARDER_LES_DEUX",
    "CLE_NOM_DIFFERENCIE",
    "CLE_REMPLACER_LE_PROFIL",
    "CLE_RENOMMER",
    "CREUX_DU_CHOIX",
    "CalibrationAnnulee",
    "CollisionDeProfil",
    "ETAT_DU_CHOIX",
    "ETAT_DU_CHOIX_AUCUNE",
    "ETAT_DU_CHOIX_UNE",
    "ETAT_PROFIL_ECRIT",
    "ETAT_RECALIBRATION",
    "ETAT_RESULTAT_NEUF",
    "ETAT_RESULTAT_RECALIBRE",
    "EcranCalibrationEcrite",
    "EcranCalibrerLaChaine",
    "EcranChaineDejaCalibree",
    "EcranCollisionDeProfil",
    "EcranDeJugement",
    "EcranRefusDeCalibration",
    "FormulaireDeCalibration",
    "LARGEUR_DU_LIBELLE",
    "LIBELLES",
    "LIBELLE_ABANDONNER",
    "LIBELLE_ANNULER",
    "LIBELLE_CHAINE",
    "LIBELLE_COMMENTAIRE",
    "LIBELLE_DEFAUT",
    "LIBELLE_DIVERGENCE_DU_RESULTAT",
    "LIBELLE_DOSSIER_DU_RESULTAT",
    "LIBELLE_ECRASER_CHAINE",
    "LIBELLE_ECRASER_ILLISIBLE",
    "LIBELLE_ETIQUETTE",
    "LIBELLE_GARDER_LES_DEUX",
    "LIBELLE_NOM_DIFFERENCIE",
    "LIBELLE_PASTILLES_DU_RESULTAT",
    "LIBELLE_PROFIL",
    "LIBELLE_REMPLACE",
    "LIBELLE_REMPLACER_LE_PROFIL",
    "LIBELLE_RENOMMER",
    "LIBELLE_SCAN",
    "MENTION_COMMENTAIRE",
    "MENTION_ETIQUETTE_VIDE",
    "MENTION_VALIDER_DPI_REFUSE",
    "MENTION_VALIDER_SANS_DPI",
    "MENTION_VALIDER_SANS_SCAN",
    "PALIER_DE_L_ECRAN",
    "PASTILLES_DU_RESULTAT",
    "PHRASE_ARRET_SANS_POINT_D_ARRET",
    "PHRASE_DE_LA_CHAINE_DEJA_CALIBREE",
    "PHRASE_DE_LA_CHAINE_DEJA_CALIBREE_PLURIEL",
    "PHRASE_DE_LA_COLLISION",
    "PHRASE_DE_LA_COLLISION_ILLISIBLE",
    "PHRASE_DPI_REFUSE",
    "PHRASE_DPI_REQUIS",
    "PHRASE_DU_DEFAUT_SUIVI",
    "PHRASE_DU_REMPLACEMENT",
    "PHRASE_DU_RETRAIT_IMPOSSIBLE",
    "PHRASE_PROFIL_NEUF",
    "PHRASE_RECALIBRATION",
    "PHRASE_SCAN_REQUIS",
    "PROFIL_PAS_ENCORE_ECRIT",
    "PROSE_DU_PROFIL",
    "PasseDeCalibration",
    "RACCOURCIS_CALIBRATE",
    "RACCOURCIS_DU_CHOIX",
    "REFUS_DU_COEUR",
    "REPONSE_DES_ISSUES",
    "RelaisDeCollision",
    "RemplacementDesProfils",
    "SUITE_AUTRE_CHAINE",
    "SUITE_DETECTER",
    "SUITE_DOSSIER_DES_PROFILS",
    "TITRE",
    "TITRE_DE_LA_CHAINE_DEJA_CALIBREE",
    "TITRE_DE_LA_COLLISION",
    "TITRE_DE_LA_SORTIE",
    "TITRE_DU_REFUS",
    "TITRE_DU_RESULTAT",
    "ZONE_EXPLORATEUR",
    "ZONE_FORMULAIRE",
    "choix_de_l_impasse",
    "choix_de_la_chaine_deja_calibree",
    "choix_de_la_collision",
    "consigner",
    "date_du_fichier",
    "dossier_des_profils",
    "dpi_valide",
    "etat_du_choix",
    "etat_du_remplacement",
    "issues_de_l_impasse",
    "issues_de_la_chaine_deja_calibree",
    "issues_de_la_collision",
    "libelle_de_l_ecrasement",
    "ligne_d_etat_du_resultat",
    "motif_du_refus",
    "motif_du_refus_de_partir",
    "ouvrir_le_resultat",
    "panneau_du_resultat",
    "pastilles_du_resultat",
    "phrase_de_la_chaine_deja_calibree",
    "profils_a_remplacer",
    "profils_du_projet",
    "remplacer_les_profils_de_la_chaine",
    "suites_du_resultat",
]
