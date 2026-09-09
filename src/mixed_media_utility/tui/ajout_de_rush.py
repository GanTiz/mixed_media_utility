# -*- coding: utf-8 -*-
"""Les MODELES PURS de la declaration d'un rush en TUI (story 11.4e, lot C).

**Ce module ne porte aucun ecran, et c'est deliberement le meme partage que
`atelier_extraction.py` annonce de lui-meme** : « Ce module ne porte que des
ECRANS. Les deux modeles purs qu'il consomme vivent a cote et se testent sans
clavier ». `rushes` et `cadences` sont ces deux-la ; celui-ci est le troisieme,
et il porte ce que les ecrans `E2-1e` a `E2-1h` calculent avant de dessiner.

**Pourquoi les modeles arrivent AVANT leurs ecrans, et ce n'est pas un
decoupage de confort.** `EPIC11-ARB-144` (Egan, 2026-09-01) exige que la
declaration d'un rush recoive « sa maquette `E2-1e` **et sa validation** AVANT
d'etre codee ». Les maquettes existent -- `E2-1e`, `E2-1f`, `E2-1g`, `E2-1h`,
redessinees a la source apres treize notes puis huit puis deux --, mais aucune
approbation d'Egan n'est consignee. Les ECRANS attendent donc cette reponse ;
ce que les ecrans **calculent** ne l'attend pas, parce que chacun des deux
calculs ci-dessous est tranche par un arbitrage nomme, independamment de la
mise en page :

* le repliement du chemin source, par `EPIC11-ARB-151` et les notes 6 et 9
  d'Egan ;
* l'issue et les deux suites du rush deja declare, par `EPIC11-ARB-147`,
  `-152` et `-156`.

Il **n'importe JAMAIS `cli.py`** (`EPIC11-ARB-67`), et il n'importe pas non
plus `textual` : tout s'y mesure sans clavier et sans boucle d'evenements.
"""
from __future__ import annotations

from dataclasses import dataclass

from .. import source_confirmation
from ..declaration_de_rush import (
    ISSUES_PAR_MOTIF,
    MOTIF_RUSH_DEJA_DECLARE,
)
from ..io.version_ranks import cardinal_des_homonymes
from . import jetons, rushes
from .panneau import ChoixExclusif, Issue

__all__ = [
    "TETE_DE_CHEMIN",
    "QUEUE_DE_CHEMIN",
    "segments_de_chemin",
    "plier_le_chemin",
    "CLE_RELINKER",
    "CLE_SEPARER",
    "CLE_ANNULER",
    "issues_du_refus",
    "libelle_de_relink",
    "suites_du_rush_deja_declare",
    # `E2-1f` -- le refus de conflit d'identite (`EPIC11-ARB-231`, 2026-09-05)
    "TITRE_DU_REFUS_DE_CONFLIT",
    "PHRASE_DU_CONFLIT",
    "LIBELLE_SEPARER",
    "PHRASE_DES_RANGS_D_HOMONYME_EPUISES",
    "phrase_des_rangs_epuises",
    "LIBELLE_DUREE_SOURCE",
    "LIBELLE_BASE_DE_TIMECODE",
    "LIBELLE_TIMECODE_INITIAL",
    "LIBELLE_DECLARE_DEPUIS",
    "MENTION_REFUSE",
    "FicheDeRefusDeConflit",
    "code_de_refus",
    "etat_du_refus_de_conflit",
    # Les quatre etats de `E2-1e` (`EPIC11-ARB-226`, 2026-09-05)
    "ASSERTION_REC709",
    "CLE_DECLARER",
    "CLE_DESIGNER",
    "COLONNE_DE_VALEUR",
    "COULEUR_NON_SIGNALEE",
    "ETAT_COULEUR_ABSENTE",
    "LIGNES_DU_CHEMIN",
    "RIEN_ECRIT_ENCORE",
    "TITRE_DU_CARTOUCHE",
    "FicheDeDeclaration",
    "cardinal_lisible",
    "issues_de_la_declaration",
    "ligne_de_fiche",
    "rang_ordinal",
    "texte_de_la_resolution",
    "texte_de_l_espace_couleur",
    "texte_du_codec",
]


# ==========================================================================
# Le chemin source : entier si possible, coupe SUR UN SEPARATEUR sinon
# ==========================================================================

#: Combien de segments de tete la coupe garde -- verbatim d'Egan, note 6 de la
#: relecture v2 (2026-09-01) : « on coupe au milieu en gardant les **3 premiers
#: dossiers** de l'arborescence et les deux derniers au moins ».
TETE_DE_CHEMIN = 3

#: Combien de segments de queue la coupe garde **au moins**. « Au moins » est
#: le mot d'Egan, et il est tenu par la recherche elle-meme : la queue est
#: essayee de la plus longue a la plus courte, donc le premier repliement qui
#: tient est celui qui garde le plus de queue possible.
QUEUE_DE_CHEMIN = 2


def segments_de_chemin(chemin: str) -> list[str]:
    """Les segments de `chemin`, **separateur compris**.

    Recoller les segments rend le chemin, caractere pour caractere : c'est
    l'invariant qui rend la coupe sure. Un separateur emporte par le decoupage
    devrait etre remis a la main a chaque recollement, et c'est exactement la
    facon dont une coupe finit par tomber au milieu d'un nom de dossier -- ce
    que la note 9 d'Egan interdit.

    Les deux separateurs sont traites ensemble (`jetons.SEPARATEURS_DE_CHEMIN`,
    et pour son motif : le depot tourne sous Windows et sous Linux, et un
    chemin saisi a la main peut porter l'un ou l'autre).
    """
    morceaux: list[str] = []
    courant = ""
    for caractere in chemin:
        courant += caractere
        if caractere in jetons.SEPARATEURS_DE_CHEMIN:
            morceaux.append(courant)
            courant = ""
    if courant:
        morceaux.append(courant)
    return morceaux


def _separateur(morceaux: list[str]) -> str | None:
    """Le separateur employe par ce chemin, ou `None` s'il n'en a aucun.

    Lu sur le chemin plutot que choisi : rendre `\\` a un chemin POSIX ferait
    de la coupe un chemin qui n'existe sur aucune des deux plateformes.
    """
    for morceau in morceaux:
        if morceau[-1:] in jetons.SEPARATEURS_DE_CHEMIN:
            return morceau[-1]
    return None


def _empiler(morceaux: list[str], largeur: int,
             lignes: int) -> list[str] | None:
    """Replier `morceaux` sur au plus `lignes` lignes de `largeur`, ou `None`.

    **Aucune ligne ne se brise ailleurs qu'entre deux segments** : c'est la
    note 9 d'Egan prise a la lettre (« traiter les dossiers comme des blocs
    insecables »), et c'est pourquoi un segment plus large que la ligne rend
    `None` plutot qu'une coupure nette. `None` n'est pas un echec : c'est ce
    qui fait essayer la coupe suivante, puis, en dernier ressort, la regle du
    depot pour un chemin qu'on LIT (:func:`jetons.abreger_chemin`).

    La mesure est en **colonnes** et jamais en `len()` : un nom de dossier en
    ideogrammes rendrait une ligne que le code croit calee juste pour le double
    de sa largeur reelle -- le defaut mesure sur `panneau.LigneChiffree`.
    """
    if largeur <= 0 or lignes <= 0:
        return None
    empilees: list[str] = []
    courante = ""
    for morceau in morceaux:
        if jetons.colonnes(morceau) > largeur:
            return None
        if jetons.colonnes(courante + morceau) <= largeur:
            courante += morceau
            continue
        empilees.append(courante)
        courante = morceau
    if courante:
        empilees.append(courante)
    return empilees if len(empilees) <= lignes else None


def plier_le_chemin(chemin: str, largeur: int, lignes: int = 2,
                    ascii_seul: bool = False) -> list[str]:
    """Le chemin source de `E2-1e`, replie -- et coupe **sur un separateur**.

    `EPIC11-ARB-151` : sur cet ecran le chemin est **complet**, quitte a
    prendre plusieurs lignes. La regle du depot pour un chemin qu'on lit
    (:func:`jetons.abreger_chemin`, coupe au milieu au caractere pres) ne vaut
    pas ici, et la mesure qui l'a etabli est dans le generateur des maquettes :
    a 43 colonnes elle rend
    `D:\\HOKO\\Documents\\rushe…plan séquence 12.mov`, c'est-a-dire qu'elle
    mange `03_tournage_mai` -- **le seul segment qui distingue deux journees de
    tournage**.

    **Deux notes d'Egan, et la seconde change l'algorithme et pas un
    reglage.** La note 6 (relecture v2, 2026-09-01) donne la forme : « 2 lignes
    puis on coupe au milieu en gardant les 3 premiers dossiers de
    l'arborescence et les deux derniers au moins ». La note 9 (relecture v3,
    2026-09-02) ajoute par-dessus que la coupe tombe sur une **frontiere de
    separateur**, jamais au milieu d'un nom de dossier : «
    `...uc/tournage_juin/hd` » est fautif, « `.../tournage_juin/hd` » et
    « `.../truc/tournage_juin/hd` » sont tous deux acceptables. Un compte de
    caracteres devient un decoupage sur segments.

    **« Dans la mesure du possible » est ecrit deux fois dans la note 9, et
    cette fonction le tient plutot que de promettre l'impossible.** Un chemin
    dont un seul segment depasse la largeur ne peut etre coupe a aucune
    frontiere : la fonction retombe alors sur :func:`jetons.abreger_chemin`,
    qui coupe au caractere. Ce repli est **nomme et mesure**, jamais silencieux
    -- et il rend toujours quelque chose, parce qu'un ecran qui leverait sur un
    nom de dossier long serait pire que le chemin ampute qu'il refuse.

    **L'ordre de preference suit la forme de la note, qui n'est pas
    symetrique** : la tete est une quantite FIXE (« les **3** premiers
    dossiers »), la queue un MINIMUM (« les deux derniers **au moins** »).
    C'est donc la queue qui s'etend jusqu'a remplir la place, a tete constante
    -- et la tete ne cede que si aucune queue, pas meme d'un seul segment, ne
    tient a cote d'elle. Prendre l'inverse rend un chemin licite mais pas celui
    de la maquette : sur `E2-1h`, maximiser la queue d'abord donne
    `D:\\HOKO\\…\\tournage\\03_tournage_mai\\` la ou Egan a valide
    `D:\\HOKO\\Documents\\…\\03_tournage_mai\\`.

    `ascii_seul` **precede toute mesure** : `…` vaut une colonne, `...` en vaut
    trois, et choisir les points apres avoir compte ferait deborder de deux
    colonnes une ligne calee juste (la regression payee sur le bandeau le
    2026-08-28).
    """
    if ascii_seul:
        chemin = jetons.replier_ascii(chemin)
    if largeur <= 0 or lignes <= 0:
        return []
    morceaux = segments_de_chemin(chemin)
    if not morceaux:
        return []

    entier = _empiler(morceaux, largeur, lignes)
    if entier is not None:
        # Le cas nominal, et c'est `EPIC11-ARB-151` : rien n'est retire.
        return entier

    separateur = _separateur(morceaux)
    if separateur is not None:
        coupe = jetons.points_d_abregement(ascii_seul) + separateur
        # La tete est fixe et la queue s'etend : la boucle exterieure ne
        # descend donc la tete qu'une fois toutes les queues epuisees.
        for tete in range(min(TETE_DE_CHEMIN, len(morceaux) - 2), -1, -1):
            for queue in range(len(morceaux) - tete - 1, 0, -1):
                candidat = morceaux[:tete] + [coupe] + morceaux[-queue:]
                empilees = _empiler(candidat, largeur, lignes)
                if empilees is not None:
                    return empilees

    # Dernier ressort : aucune frontiere ne permet de tenir, on rend la regle
    # du depot plutot que rien. Une ligne, bornee, jamais une exception.
    return [jetons.abreger_chemin(chemin, largeur, ascii_seul)]


# ==========================================================================
# Le rush deja declare : TROIS issues lues au coeur, TROIS suites composees ici
#
# **Les deux cardinaux ont cesse de diverger le 2026-09-05, et c'est la
# fermeture d'un ecart NOMME.** Le coeur porte trois issues depuis
# `EPIC11-ARB-231` ; l'ecran en portait deux, parce que sa maquette n'avait
# pas encore ete redessinee (`EPIC11-ARB-144` interdit de coder un dessin non
# valide). La maquette `E2-1f` porte desormais les trois sorties dans l'ordre
# de l'arbitrage, et c'est ce lot-ci qui les fait atteindre la TUI.
# ==========================================================================

#: La suite qui mene ailleurs et qui **ecrit** : relinker le rush deja declare
#: vers le fichier qu'on vient de designer (`EPIC11-ARB-152`, verbatim d'Egan :
#: « on garde le premier choix pour relinker vers ce fichier »).
CLE_RELINKER = "relinker"

#: La suite qui affirme que ce n'est PAS le meme rush, et le declare a part.
#: **Elle ECRIT** -- elle cree une seconde entree `rushes[]`, sous
#: l'identifiant leve par un RANG (`EPIC11-ARB-233`).
#:
#: **Corrige le 2026-09-05, finding `F17` de la revue 11.4e.** Cette place
#: disait « leve par le suffixe de dossier d'`EPIC11-ARB-9` ». La conclusion
#: restait vraie -- une seconde entree, sous un identifiant leve --, sa raison
#: ne l'etait plus : `EPIC11-ARB-9` **tient**, c'est lui qui decide qu'il faut
#: lever plutot qu'ecraser, mais la FORME de la levee est un rang depuis
#: `EPIC11-ARB-233`, calcule par `io/version_ranks`. Ce lot a ete fusionne
#: AVANT cet arbitrage, qui n'est pas repasse sur sa prose.
#:
#: `EPIC11-ARB-231` (Egan, 2026-09-05, verbatim : « Une 3e sortie sur
#: l'ecran »). Le contre-exemple qui la rend necessaire n'est pas
#: hypothetique : deux cameras jam-synchronisees, cartes formatees pareil,
#: `prise01.mov` sur les deux -- les quatre criteres coincident et ce sont
#: pourtant deux angles. Depuis qu'`EPIC11-ARB-230` a retire le dossier des
#: criteres, sans cette sortie ce cas serait un **faux conflit sans issue**,
#: ce qu'`EPIC11-ARB-89` interdit nommement.
#:
#: En ligne de commande, la meme sortie prend la forme de `--force-distinct`
#: (`EPIC11-ARB-232`) ; ici elle repasse par `preparer_une_declaration` avec
#: `force_distinct=True`, jamais par une seconde redaction de la separation.
CLE_SEPARER = "separer"

#: La suite qui sort, et **elle n'ecrit rien** : c'est elle que
#: `ChoixExclusif.__post_init__` fait viser au curseur (`EPIC11-ARB-7`).
CLE_ANNULER = "annuler"

#: Le libelle de la sortie neuve, **verbatim de la maquette `E2-1f`**. Il n'est
#: pas lu dans `ISSUES_PAR_MOTIF` et ce n'est pas un oubli : la table du coeur
#: porte la phrase de LIGNE DE COMMANDE (« ... avec `mmu project add-rush
#: --force-distinct` »), qui ne se tape pas depuis une TUI. Ce qui se lit du
#: coeur est le cardinal et l'ordre ; le texte appartient au dessin.
LIBELLE_SEPARER = "C'est un autre rush, le déclarer séparément"

#: Ce que `E2-1j` met A LA PLACE de :data:`LIBELLE_SEPARER` quand les rangs
#: d'homonyme sont tous pris (`EPIC11-ARB-239`, tranche par Egan le
#: 2026-09-05 : « une ligne d'explication »).
#:
#: **Une LIGNE, pas une quatrieme sortie**, et c'est tout l'arbitrage. Le coeur
#: ne se contente pas de retirer la seconde issue : il NOMME une issue de
#: remplacement (`version_ranks.refus_de_rangs_epuises`). Ce texte-la est une
#: prose de ligne de commande ; le rendre comme un libelle inventerait la
#: sortie qu'`EPIC11-ARB-144` interdit d'inventer. Les deux issues qui restent
#: -- le relink et `Annuler` -- suffisent a tenir `EPIC11-ARB-89` : deux
#: issues, donc pas de blocage sec.
#:
#: **Le CARDINAL se lit au coeur, le TEXTE appartient au dessin** -- meme
#: partage que :data:`LIBELLE_SEPARER` ci-dessus. Le nombre vient de
#: :func:`~mixed_media_utility.io.version_ranks.cardinal_des_homonymes` et
#: jamais d'un `99` recopie : ce depot a paye TROIS fois une borne citee de
#: memoire et fausse (CLAUDE.md, « les politiques se mesurent »). Le banc
#: confronte la phrase FORMATEE a la maquette, si bien qu'un deplacement de la
#: borne fait rougir le dessin -- ce qui est juste, il faudrait le regenerer.
#:
#: **La premiere redaction IMPORTAIT la borne, et c'etait un defaut**, ferme
#: le 2026-09-06 sur signalement de la frontiere
#: `test_AUCUN_module_de_la_TUI_ne_redige_une_regle_de_RANG`, qui interdit au
#: paquet de nommer le vocabulaire des rangs **prose comprise**. Elle avait
#: raison sur le fond et pas seulement sur la lettre : le coeur porte deja
#: `refus_de_rangs_epuises`, donc cette ligne-ci ecrivait bien une SECONDE
#: regle de rang en TUI. Le cardinal se demande desormais, il ne se recompose
#: plus -- et l'ecart entre les deux comptes (l'original porte un nom sans
#: rang) est documente au coeur, la ou il se calcule.
PHRASE_DES_RANGS_D_HOMONYME_EPUISES = (
    "Les {rangs} rangs d'homonyme sont pris : en retirer un du projet, "
    "ou renommer.")


def phrase_des_rangs_epuises(ascii_seul: bool = False) -> str:
    """La ligne d'explication de `E2-1j`, formatee sur la borne du coeur.

    Elle passe par :func:`_replie` comme toute autre phrase de ce module : une
    ligne qui ne fait pas varier `ascii_seul` ne mesure que la moitie du
    produit et l'annonce verte (CLAUDE.md, regle posee le 2026-09-06 apres
    deux occurrences dans la meme nuit -- dont `PHRASE_DERNIER_LOT`, qui etait
    la seule ligne de son module a ne pas etre repliee).
    """
    return _replie(
        PHRASE_DES_RANGS_D_HOMONYME_EPUISES.format(
            rangs=cardinal_des_homonymes()),
        ascii_seul)


#: Le titre du CADRE de `E2-1f`, verbatim. Porte par la bordure et jamais par
#: une ligne de texte (`DESIGN.md` 7.4) -- meme geste que
#: :data:`TITRE_DU_CARTOUCHE` sur `E2-1e`.
TITRE_DU_REFUS_DE_CONFLIT = "Un rush identique existe déjà"

#: La phrase qui explique le code, verbatim de la maquette. Elle est **une
#: phrase** et non deux lignes : la maquette la dessine sur deux lignes de 68
#: colonnes, mais c'est :func:`jetons.envelopper` qui doit la couper -- une
#: coupure ecrite en dur serait fausse des la premiere largeur differente, et
#: la TUI se redimensionne.
PHRASE_DU_CONFLIT = ("Les quatre critères d'identité coïncident avec ceux "
                     "d'un rush déjà déclaré. Le chemin ne compte pas.")

#: Les quatre libelles de criteres et celui de la provenance, verbatim de
#: `E2-1f`. `Nom du fichier` est :data:`LIBELLE_NOM`, partage avec `E2-1e` :
#: deux redactions du meme libelle divergeraient au premier ajustement, et ce
#: sont deux cartouches que le meme operateur voit a une frappe d'intervalle.
LIBELLE_DUREE_SOURCE = "Durée source"
LIBELLE_BASE_DE_TIMECODE = "Base de timecode"
LIBELLE_TIMECODE_INITIAL = "Timecode initial"
LIBELLE_DECLARE_DEPUIS = "Déclaré depuis"

#: La droite du bandeau de `E2-1f` : `plan séquence 12.mov · refusé`.
MENTION_REFUSE = "refusé"


def issues_du_refus(motif: str = MOTIF_RUSH_DEJA_DECLARE) -> tuple[str, ...]:
    """Les issues du refus, **LUES** dans la table publiee du coeur.

    `EPIC11-ARB-156` distingue deux objets que l'AC 3.6 confondait : une
    **issue** agit sur ce que le refus refuse -- ecraser, versionner, forcer --,
    une **suite** mene ailleurs.

    **Le refus de conflit en porte TROIS des deux cotes depuis
    `EPIC11-ARB-231`** (2026-09-05). Ce n'etait pas le cas jusque-la, et
    l'ecart valait d'etre garde : `EPIC11-ARB-147` posait un refus SEC a issue
    unique, `EPIC11-ARB-152` lui donnait deux suites d'ecran, et le cardinal
    du coeur (3) divergeait de celui de l'ecran (2) tant que la maquette a
    trois sorties n'etait pas validee. Elle l'est ; les deux cardinaux se
    rejoignent, et c'est :func:`suites_du_rush_deja_declare` qui le montre.

    **Les issues du coeur et les suites de l'ecran ne se recopient pas pour
    autant** : la table du coeur porte des phrases de LIGNE DE COMMANDE --
    l'invocation de relink, avec son projet, son rush et sa video --, l'ecran
    porte les libelles de sa maquette. Ce qui se rejoint est le cardinal et
    l'ORDRE, pas le texte -- et c'est exactement ce que la frontiere de ce lot
    mesure.

    **La commande n'est pas CITEE ici, et c'est deliberé.**
    `test_conformite_sorties_nommees` rejoue toute commande citee dans une
    chaine de ce depot et exige qu'argparse l'accepte (`EPIC11-ARB-224`). Une
    citation tronquee a des fins d'illustration -- `--project` suivi de points
    de suspension -- ne parse pas, donc la frontiere rougit, et elle a raison
    de rougir : elle ne peut pas distinguer une prose explicative d'une issue
    offerte a l'operateur, et c'est precisement ce qui la rend efficace. Une
    prose se reformule ; on n'elargit pas la frontiere pour la laisser passer.

    La table est lue et jamais recopiee, pour le motif exact qui l'a fait
    publier : dupliquer le vocabulaire des refus laisserait deux verites au
    meme moment, et un test symetrique ne rougirait qu'**apres** qu'on a
    diverge.
    """
    return ISSUES_PAR_MOTIF[motif]


def libelle_de_relink(source_name: str, chemin_designe: str, largeur: int,
                      ascii_seul: bool = False) -> str:
    """« Relinker <fichier> vers <chemin designe> », note 3 d'Egan.

    Verbatim : « Mettre **relinker [rushe] vers [chemin designe a l'etape
    precedente]**, comme ca c'est clair ». La note 4 dit pourquoi cette
    formulation suffit a elle seule : elle **reintroduit le chemin designe**,
    que l'ecran ne portait nulle part ailleurs.

    Le nom affiche est `source_name` -- le VRAI nom du fichier, accents et
    espaces compris --, jamais l'identifiant derive (`EPIC11-ARB-153`,
    renforce par `-141` : on n'affiche pas ce qu'on ne peut plus corriger).

    Le chemin, lui, est coupe par :func:`plier_le_chemin` sur **une seule
    ligne** -- une issue fait une ligne par contrat --, et non par
    :func:`jetons.abreger_chemin`. Le motif est mesure : le chemin designe est
    un DOSSIER, donc il finit par un separateur, donc son « dernier segment »
    est vide. `abreger_chemin` sert alors la queue d'abord sur un budget nul et
    rend `D:\\HOKO\\Documents\\rushes\\2026\\04_tournage_…`, c'est-a-dire
    qu'elle mange `04_tournage_juin\\hd\\` -- le seul bout du chemin qui
    distingue le fichier designe de celui deja declare, et donc la seule raison
    d'etre de la note 4. Le decoupage sur segments rend
    `D:\\HOKO\\Documents\\…\\04_tournage_juin\\hd\\`, et c'est aussi ce que la
    maquette dessine.
    """
    prefixe = f"Relinker {source_name} vers "
    place = largeur - jetons.colonnes(
        jetons.replier_ascii(prefixe) if ascii_seul else prefixe)
    coupe = plier_le_chemin(chemin_designe, place, lignes=1,
                            ascii_seul=ascii_seul)
    return (jetons.replier_ascii(prefixe) if ascii_seul else prefixe) + (
        coupe[0] if coupe else "")


def suites_du_rush_deja_declare(source_name: str, chemin_designe: str,
                                largeur: int = jetons.LARGEUR_PLANCHER,
                                ascii_seul: bool = False,
                                separation_offerte: bool = True
                                ) -> ChoixExclusif:
    """Les TROIS suites de `E2-1f`, et le curseur sur la seule qui n'ecrit pas.

    **L'ORDRE porte la recommandation** (`EPIC11-ARB-231`, verbatim), et c'est
    pourquoi il est mesure en egalite exacte plutot qu'en appartenance :

    1. **relinker** vers le fichier qu'on vient de designer -- c'est le geste
       ordinaire devant un rush deja declare (`EPIC11-ARB-152`, verbatim
       d'Egan : « on garde le premier choix pour relinker vers ce fichier ») ;
    2. **c'est un autre rush, le declarer separement** -- la sortie neuve. Ni
       en tete (le cas ordinaire reste le relink) ni en queue (elle passerait
       pour une variante d'`Annuler`) ;
    3. **annuler** -- rien n'a ete ecrit, il n'y a rien a defaire.

    **Ce que `EPIC11-ARB-231` supersede, dit plutot que tu** : `-152` disait
    « on garde annuler et c'est tout », et cette fonction rendait deux issues.
    Elle en rend trois depuis le 2026-09-05, du choix explicite d'Egan. `-152`
    tient sur le reste -- le rang 1 est bien le relink, et « lui donner un
    autre identifiant » reste retire par `EPIC11-ARB-141`, parce que c'est une
    edition de nom et non une suite.

    **Le curseur n'est pas pose ici**, et c'est voulu : `ChoixExclusif` le
    deplace hors de toute issue qui ecrit (`EPIC11-ARB-7` tenu par
    `EPIC11-ARB-45`, `panneau.py`). Des trois, seule `Annuler` n'ecrit pas --
    la sortie neuve cree une seconde entree `rushes[]` --, donc le curseur y
    atterrit de lui-meme, ce que la maquette dessine. Le contourner en posant
    `curseur=` a la main rendrait l'ecriture atteignable en UNE frappe.

    **`separation_offerte=False` retire la SECONDE suite, et c'est une lecture
    du coeur et non une decision d'ecran** (fermeture de `F1` de la revue de la
    11.4e). Il existe un regime ou `--force-distinct` -- ce que cette suite fait
    repasser dans `preparer_une_declaration` -- est refuse par la garde meme qui
    vient de lever le refus : les **99 rangs d'homonymie consommes**. Le coeur le
    sait deja et le dit deja, en remplacant la seconde entree de sa liste
    d'issues (`declaration_de_rush._refus_de_rush_deja_declare`,
    `issue_de_remplacement`, `EPIC11-ARB-233`). L'offrir quand meme rendrait une
    issue qui se tape, qui parse, et **qui ne change rien** : le meme ecran, les
    memes suites, aucune information neuve -- la troisieme condition
    d'`EPIC11-ARB-224` en defaut, et le blocage sec deguise qu'`EPIC11-ARB-89`
    interdit.

    Il reste alors **deux** issues, ce qui n'est pas un blocage sec : le relink
    et `Annuler`. `ChoixExclusif` tient les deux invariants sans qu'on pose
    quoi que ce soit -- son plancher est de deux issues, et `Annuler` reste la
    seule qui n'ecrit pas, donc le curseur y atterrit toujours de lui-meme.

    **Ce qui n'est PAS tranche ici, et se voit a ce que la fonction ne fait
    pas** : le coeur ne se contente pas de retirer, il **nomme** une seconde
    issue de remplacement (« retirer l'un des homonymes … ou renommer le
    fichier source »). Ce texte est une prose de LIGNE DE COMMANDE, pas un
    libelle de bouton, et aucune maquette ne dessine ou l'ecran le porterait.
    Le rendre ici inventerait la sortie que la revue reproche justement d'avoir
    inventee. La suite est donc retiree, et la question -- **quel libelle, a
    quel rang, dans quelle zone** -- est posee a Egan plutot que tranchee.
    """
    issues = [
        Issue(CLE_RELINKER,
              libelle_de_relink(source_name, chemin_designe, largeur,
                                ascii_seul),
              ecrit=True),
    ]
    if separation_offerte:
        issues.append(
            Issue(CLE_SEPARER, _replie(LIBELLE_SEPARER, ascii_seul),
                  ecrit=True))
    issues.append(
        Issue(CLE_ANNULER, _replie(LIBELLE_ANNULER, ascii_seul), ecrit=False))
    return ChoixExclusif(issues=issues)


# ==========================================================================
# La FICHE de declaration : les quatre etats de `E2-1e`, en modele pur
#
# `EPIC11-ARB-226` (Egan, 2026-09-05, verbatim : « Je valide la v4 ») leve
# `EPIC11-ARB-144` pour quatre maquettes. Trois d'entre elles sont des ETATS
# du meme ecran et non des ecrans de plus -- c'est ce que leurs generateurs
# disent chacun en tete, et c'est pourquoi il n'y a **qu'une** fiche ici :
#
# | maquette | ce qui varie, et rien d'autre |
# |---|---|
# | `E2-1e` | l'etat nominal |
# | `E2-1h` | le chemin ne tient pas sur deux lignes, donc il est coupe |
# | `E2-1g` | le triplet colorimetrique n'est pas signale par la source |
# | `E2-1i` | le moteur n'a pas corrobore le cardinal, donc il s'OMET |
#
# Quatre fiches recopiees divergeraient au premier ajustement, et l'ecart ne
# se verrait pas a la relecture : c'est litteralement le motif que
# `_gen_extraction.fiche_de_declaration` ecrit pour lui-meme cote maquette.
# ==========================================================================

#: Le titre du CADRE, verbatim des quatre maquettes. Porte par la bordure et
#: jamais par une ligne de texte (`DESIGN.md` 7.4).
TITRE_DU_CARTOUCHE = "À déclarer"

#: La colonne ou commence la valeur, **mesuree sur les quatre maquettes** :
#: `Codec · format de pixel` est le libelle le plus long (23 colonnes) et il
#: garde deux espaces de creux. Une continuation de chemin s'y aligne sans que
#: personne ne compte a la main -- c'est le `RETRAIT_DE_VALEUR` du generateur,
#: relu ici cote produit.
COLONNE_DE_VALEUR = 25

LIBELLE_NOM = "Nom du fichier"
LIBELLE_CHEMIN = "Chemin complet"
LIBELLE_CODEC = "Codec · format de pixel"
LIBELLE_CADENCE = "Cadence source"
LIBELLE_RESOLUTION = "Résolution"
LIBELLE_TIMECODE = "Timecode de départ"
LIBELLE_COULEUR = "Espace couleur"

#: Sur combien de lignes le chemin source a le droit de se replier
#: (`EPIC11-ARB-151` amende par la note 6 d'Egan : « 2 lignes puis on coupe »).
LIGNES_DU_CHEMIN = 2

#: Ce que la ligne `Espace couleur` dit quand le triplet n'est pas signale --
#: verbatim de `E2-1g`. Le glyphe `substitute` (`▲`) est pose par
#: :func:`jetons.marque`, jamais recopie.
COULEUR_NON_SIGNALEE = "non signalé — enregistré comme absent"

#: L'assertion de traitement de `E2-1g`, **hors du cartouche** et verbatim.
#: `EPIC11-ARB-149`, note 1 d'Egan : « on **annonce** "le rushe sera traite
#: comme Rec709 par defaut" a la place d'un choix unique. » Elle est hors du
#: cadre parce que le cadre s'appelle « À déclarer » : tout ce qu'il porte se
#: lit comme destine au manifeste, or `bt709` n'y est **jamais** ecrit
#: (`source_confirmation._normalize_probe_value` l'interdit nommement).
ASSERTION_REC709 = ("Le rush sera traité comme Rec. 709 par défaut · aucune "
                    "valeur écrite.")

#: Les trois issues de l'ecran, verbatim des quatre maquettes.
CLE_DECLARER = "declarer"
CLE_DESIGNER = "designer"

LIBELLE_DECLARER = "Déclarer le rush"
LIBELLE_DESIGNER = "Désigner un autre fichier"
LIBELLE_ANNULER = "Annuler"

#: La moitie de la ligne d'etat qui dit l'etat du DISQUE. Minuscule et sans
#: point : elle se compose derriere un tiret cadratin, la ou
#: `panneau.RIEN_ECRIT` est une phrase entiere. Les deux disent la meme chose
#: et ne s'ecrivent pas au meme endroit -- celle-ci est **accentuee a la
#: source**, meme motif que le finding `I6` : une chaine desaccentuee rendrait
#: le repli ASCII indistinguable du nominal.
RIEN_ECRIT_ENCORE = "rien n'a encore été écrit"

#: Ce que la ligne d'etat dit quand le triplet colorimetrique manque -- une
#: MESURE de l'ecran courant (`EPIC11-ARB-56`), verbatim de `E2-1g`.
ETAT_COULEUR_ABSENTE = "espace couleur non signalé — aucune valeur écrite"


def _replie(texte: str, ascii_seul: bool) -> str:
    """Le repli d'un texte de ce module : la table de `jetons`, et rien d'autre."""
    return jetons.replier_ascii(texte) if ascii_seul else texte


def cardinal_lisible(cardinal: int) -> str:
    """`6300` -> `6 300`. L'espace est une espace ORDINAIRE, et c'est mesure.

    Les maquettes portent `0x20` entre le `6` et le `300` -- pas une espace
    fine, pas une insecable. Une espace insecable rendrait un point
    d'interrogation sur les consoles que le repli ASCII existe pour servir, et
    la mesure de largeur en colonnes ne la distinguerait pas.
    """
    return f"{cardinal:,}".replace(",", " ")


def ligne_de_fiche(libelle: str, valeur: str, largeur: int,
                   mention: str | None = None,
                   ascii_seul: bool = False) -> str:
    """Une ligne du cartouche : libelle a gauche, valeur a la colonne 25.

    **Ce n'est PAS `panneau.LigneChiffree`, et l'ecart est voulu.** Celle-la
    cale son chiffre a DROITE ; les quatre maquettes de la declaration calent
    toutes leurs valeurs sur une meme colonne, parce que la fiche se lit comme
    une fiche technique et non comme un tableau de quantites. Deux valeurs
    calees a droite -- `plan séquence 12.mov` et `00:00:04:12` -- ne se
    liraient plus l'une sous l'autre.

    `mention` est la seule chose qui se cale a droite (`(exacte 25/1)`), et
    elle est la parce qu'elle qualifie la valeur sans etre elle : c'est le meme
    role que `MENTION_MAJORANT` sur `E2-3`.

    Tout est mesure en **colonnes** et jamais en `len()` : c'est le defaut paye
    sur `panneau.LigneChiffree`, ou un nom de dossier en ideogrammes rendait
    une ligne que le code croyait calee juste pour le double de sa largeur.
    `ascii_seul` **precede** toute mesure, pour le meme motif.
    """
    libelle = _replie(libelle, ascii_seul)
    valeur = _replie(valeur, ascii_seul)
    mention = None if mention is None else _replie(mention, ascii_seul)
    creux = max(COLONNE_DE_VALEUR - jetons.colonnes(libelle),
                jetons.CREUX_MINIMAL)
    # **La valeur est BORNEE, et pas seulement calee** -- meme geste que
    # `LigneChiffree.rendu`, et pour le meme motif : `textual` ne tronque pas
    # une ligne trop longue, il la **replie**, et sur une zone de hauteur 1 la
    # fin part sur une ligne qui n'est jamais dessinee. Une valeur coupee y
    # serait indistinguable d'une valeur absente. La mention garde sa place
    # entiere : elle qualifie la valeur, donc une mention amputee ferait lire
    # un panneau qui ment sur sa propre precision.
    reserve = 0 if mention is None else (
        jetons.colonnes(mention) + jetons.CREUX_MINIMAL)
    valeur = jetons.abreger_nom(
        valeur, max(largeur - creux - jetons.colonnes(libelle) - reserve, 0),
        ascii_seul)
    ligne = libelle + " " * creux + valeur
    if mention is None:
        return ligne
    reste = largeur - jetons.colonnes(ligne) - jetons.colonnes(mention)
    return ligne + " " * max(reste, jetons.CREUX_MINIMAL) + mention


def texte_du_codec(source_fields) -> str | None:
    """`prores_ks · yuv422p10le`, ou ce qui en est mesure, ou `None`.

    `EPIC11-ARB-150` a la lettre : une ligne pour deux champs que `ffprobe`
    suit separement. Un champ que la source ne signale pas s'**omet**
    (`DESIGN.md` §3) plutot que de rendre `unknown` -- et si les deux manquent,
    la ligne entiere disparait, parce qu'une etiquette sans valeur n'apprend
    rien. La table est celle du coeur (`SOURCE_FIELD_SPECS`), lue et jamais
    recopiee.
    """
    morceaux = [source_fields.get("source_codec"),
                source_fields.get("source_pix_fmt")]
    presents = [str(morceau) for morceau in morceaux if morceau is not None]
    return rushes.SEPARATEUR.join(presents) if presents else None


def texte_de_l_espace_couleur(source_fields,
                              ascii_seul: bool = False) -> tuple[str, bool]:
    """`(texte de la ligne, le triplet est-il signale ?)`.

    `EPIC11-ARB-150`, verbatim d'Egan : « on peut mettre "espace couleur -
    bt 709" plutot que de le remettre 3 fois meme s'il y a 3 parametres
    distincts derriere ». Le triplet reste **trois** champs au manifeste
    (`COLOR_TRIPLET_REPORT_KEYS`, lus ici et non recopies) ; c'est leur
    AFFICHAGE separe qui tombe.

    **Les trois valeurs ne sont fondues en une que si elles COINCIDENT.** Sur
    une source signalee elles valent toutes `bt709`, et c'est le cas que
    `E2-1g` oppose a l'absence ; trois valeurs differentes fondues en une
    seraient un mensonge, et elles se rendent alors cote a cote.

    **Un triplet PARTIEL prend la ligne de l'absence**, et c'est un choix
    nomme : le coeur escalade sur le triplet **entier**
    (`COLOR_TRIPLET_STATUS_PARTIAL` est traite comme `ABSENT` par
    `source_confirmation`), et aucune autre formulation n'a ete validee par
    Egan. Inventer ici « partiellement signalé » ferait dire a l'ecran ce
    qu'aucune maquette ne dessine.
    """
    valeurs = [source_fields.get(cle)
               for cle in source_confirmation.COLOR_TRIPLET_REPORT_KEYS]
    if any(valeur is None for valeur in valeurs):
        return jetons.marque("substitute",
                             _replie(COULEUR_NON_SIGNALEE, ascii_seul),
                             ascii_seul), False
    distinctes: list[str] = []
    for valeur in valeurs:
        if str(valeur) not in distinctes:
            distinctes.append(str(valeur))
    return rushes.SEPARATEUR.join(distinctes), True


def texte_de_la_resolution(largeur_source: int, hauteur_source: int,
                           cardinal: int | None, fps: float | None,
                           duree_secondes: float | None = None) -> str:
    """`1920 × 1080 · 6 300 frames · 4:12`, et `1920 × 1080 · 4:12` sans cardinal.

    **`EPIC11-ARB-227`, verbatim d'Egan : « On n'affiche rien si on ne
    corrobore pas ».** Le cardinal sort **sans un mot a sa place** -- ni `0`,
    ni `--`, ni un libelle d'absence. Trois issues avaient ete posees et c'est
    la premiere qu'Egan prend ; la deuxieme (« dire l'absence ») a ete ECARTEE
    nommement, et ce commentaire la garde ecrite pour qu'on ne la repropose pas
    comme neuve.

    Ce n'est pas une exception a la regle d'omission, c'est son application
    stricte : `DESIGN.md` §3 la tient depuis `EPIC7-ARB-67` -- « rien a la
    place du temps -- jamais `0:00`, jamais `--:--` presente comme une duree ».

    **La duree, elle, NE part PAS avec le cardinal** -- corrige le 2026-09-05,
    et c'est ce que la maquette `E2-1i` dessinait depuis le debut : elle garde
    `4:12` a l'instant meme ou le cardinal s'en va. Le motif est dans le coeur :
    la duree du flux est la grandeur qui sert a **tenter** la corroboration du
    cardinal, donc elle existe par construction quand celui-ci manque.

    Les deux chemins ne sont pas equivalents et l'ordre compte :

    * `cardinal / fps` d'abord -- c'est la duree **exacte**, celle des trois
      autres etats, et celle que la colonne technique de `E2-1` affiche deja ;
    * `duree_secondes` en **repli**, la duree que le conteneur declare. Elle
      n'est pas fausse, elle est simplement moins precise -- et elle est la
      seule disponible quand le cardinal ne se corrobore pas.

    `duree_secondes` est optionnel et vaut `None` par defaut : un appelant qui
    ne la connait pas retrouve exactement le comportement d'avant, ce qui rend
    cet ajout **pur** au sens de la table de liaison de la vague 3.
    """
    # **Le signe est ESPACE ici, colle dans la liste** -- ce n'est pas une
    # incoherence, c'est ce que les quatre maquettes validees dessinent :
    # `1920 × 1080` dans le panneau, `1920×1080` dans la colonne technique de
    # `E2-1`. La colonne est un budget de 32 colonnes partage a trois
    # (`rushes.py:135`) ; le panneau n'a pas cette contrainte, et le signe y
    # respire. Le GLYPHE, lui, est lu de `rushes.SIGNE_MULTIPLIER` : deux
    # redactions du meme signe divergeraient au premier repli ASCII.
    morceaux = [f"{largeur_source} {rushes.SIGNE_MULTIPLIER} {hauteur_source}"]
    if cardinal is not None:
        morceaux.append(f"{cardinal_lisible(cardinal)} frames")
    duree = (rushes.duree_de_rush(cardinal, fps)
             or rushes.duree_lisible_de_secondes(duree_secondes))
    if duree is not None:
        morceaux.append(duree)
    return rushes.SEPARATEUR.join(morceaux)


def issues_de_la_declaration() -> ChoixExclusif:
    """Les TROIS issues de `E2-1e`, et le curseur sur celle qui n'ecrit pas.

    `Déclarer le rush` est la seule qui ecrit. `ChoixExclusif.__post_init__`
    deplace donc le curseur sur `Désigner un autre fichier` (`EPIC11-ARB-7`
    tenu par `EPIC11-ARB-45`) -- ce que les quatre maquettes dessinent, `▸` sur
    la deuxieme ligne. Le poser a la main ici rendrait l'ecriture atteignable
    en UNE frappe, et le rang de l'issue principale ne bouge pas pour autant.
    """
    return ChoixExclusif(issues=[
        Issue(CLE_DECLARER, LIBELLE_DECLARER, ecrit=True),
        Issue(CLE_DESIGNER, LIBELLE_DESIGNER, ecrit=False),
        Issue(CLE_ANNULER, LIBELLE_ANNULER, ecrit=False),
    ])


def rang_ordinal(rang: int) -> str:
    """`1` -> `1er`, `4` -> `4e`. La forme de la ligne d'etat de `E2-1e`."""
    return "1er" if rang == 1 else f"{rang}e"


@dataclass(frozen=True)
class FicheDeDeclaration:
    """Ce que les quatre etats de `E2-1e` affichent, sur une seule redaction.

    Elle est **pure** : elle ne lit ni le disque ni `ffprobe`, elle prend une
    :class:`~mixed_media_utility.declaration_de_rush.DeclarationPreparee` --
    le temps 1 du coeur, celui qui ne touche aucun octet -- et rend des lignes.
    C'est ce qui la rend mesurable sans clavier, comme les deux autres modeles
    de ce module.

    `rang` est le rang du rush dans le projet une fois declare (`4e rush du
    projet`). Il n'est **pas** dans `DeclarationPreparee` et ne peut pas y
    etre : c'est un cardinal de la LISTE, que l'ecran lit sur le modele qu'il
    porte deja. `None` retire la moitie de phrase plutot que d'inventer un
    rang.

    ------------------------------------------------------------------------
    **L'ECART AVEC `E2-1i` EST FERME** (2026-09-05, meme journee que sa mise en
    dette). Ce paragraphe decrivait, jusqu'a la fermeture, une divergence :
    la maquette du cardinal absent garde `4:12` sur la ligne `Résolution` --
    « la duree ne disparait pas avec le cardinal, c'est elle qui a servi a
    tenter la corroboration, donc elle existe par construction », dit son
    generateur -- alors que l'ecran rendait `1920 × 1080` seul.

    La cause etait exactement celle que la dette annoncait : la duree existait
    au coeur (`extraction.SourceQualification.stream_duration_seconds`) sans
    atteindre l'ecran, et le seul chemin restant, `cardinal / fps`, est
    precisement celui qui manque dans cet etat-la.
    `DeclarationPreparee.duree_source_secondes` la porte desormais, et
    :func:`texte_de_la_resolution` s'en sert **en repli** -- jamais a la place
    de `cardinal / fps`, qui reste la grandeur exacte quand elle existe.

    Ce qui reste vrai et vaut d'etre garde : c'est l'INVENTAIRE de
    :mod:`tests.unit.tui.test_ecrans_declaration_de_rush` qui a rendu la
    fermeture sure, parce qu'il portait le volet symetrique -- une entree qui
    cesse de diverger fait rougir. La divergence ne pouvait donc pas etre
    fermee en silence, ni survivre a sa propre fermeture.
    """

    preparee: object
    rang: int | None = None

    # -- le corps du cartouche ----------------------------------------------

    def lignes(self, largeur: int = jetons.LARGEUR_PLANCHER,
               ascii_seul: bool = False) -> list[str]:
        """Les lignes du cartouche « À déclarer », dans l'ordre des maquettes.

        `largeur` est la largeur ECRIVABLE du cartouche, pas celle de la
        fenetre : l'ecran la derive par `jetons.largeur_de_cartouche`, et un
        banc peut la poser a la main pour se comparer a une maquette dessinee
        sur une autre grille.

        **Aucune ligne n'est fabriquee pour combler un trou.** Un codec absent
        retire sa ligne, un timecode absent retire la sienne : c'est
        `DESIGN.md` §3, et c'est ce que le manifeste fait deja de ces champs
        (« Omission stricte: jamais `null`, jamais une valeur par defaut »).
        """
        preparee = self.preparee
        champs = preparee.record.source_fields
        lignes = [ligne_de_fiche(LIBELLE_NOM, preparee.source_name, largeur,
                                 ascii_seul=ascii_seul)]

        replie = self.chemin_replie(largeur, ascii_seul)
        lignes.append(ligne_de_fiche(LIBELLE_CHEMIN, replie[0], largeur,
                                     ascii_seul=ascii_seul))
        # Les continuations se calent sur la colonne de valeur, sans etiquette :
        # `EPIC11-ARB-151` veut le chemin ENTIER, pas une seconde etiquette.
        lignes.extend(" " * COLONNE_DE_VALEUR + suite for suite in replie[1:])

        codec = texte_du_codec(champs)
        if codec is not None:
            lignes.append(ligne_de_fiche(LIBELLE_CODEC, codec, largeur,
                                         ascii_seul=ascii_seul))
        lignes.append(ligne_de_fiche(
            LIBELLE_CADENCE,
            rushes.cadence_lisible(preparee.fps_source) or "",
            largeur, mention=self.mention_de_cadence_exacte(),
            ascii_seul=ascii_seul))
        lignes.append(ligne_de_fiche(
            LIBELLE_RESOLUTION,
            texte_de_la_resolution(preparee.source_width,
                                   preparee.source_height,
                                   preparee.cardinal_de_frames,
                                   preparee.fps_source,
                                   preparee.duree_source_secondes),
            largeur, ascii_seul=ascii_seul))
        if preparee.source_start_timecode is not None:
            lignes.append(ligne_de_fiche(LIBELLE_TIMECODE,
                                         preparee.source_start_timecode,
                                         largeur, ascii_seul=ascii_seul))
        couleur, _signale = texte_de_l_espace_couleur(champs, ascii_seul)
        lignes.append(ligne_de_fiche(LIBELLE_COULEUR, couleur, largeur,
                                     ascii_seul=ascii_seul))
        return lignes

    def mention_de_cadence_exacte(self) -> str:
        """`(exacte 25/1)` -- la cadence exacte, LUE de la fonction du coeur.

        `codec_profiles.exact_frame_rate` est celle que
        `declaration_de_rush._qualifier_la_source` emploie deja pour refuser
        une cadence non representable, et c'est aussi celle que le manifeste
        serialise. Une seconde redaction de la conversion ferait afficher
        `24000/1001` a un endroit et `23.976` a l'autre pour la meme source.
        """
        from ..codec_profiles import exact_frame_rate

        return f"(exacte {exact_frame_rate(self.preparee.fps_source)})"

    # -- le chemin, et ce qu'il coute ---------------------------------------

    def chemin_replie(self, largeur: int = jetons.LARGEUR_PLANCHER,
                      ascii_seul: bool = False) -> list[str]:
        """Le chemin source, replie -- et coupe sur un separateur s'il le faut.

        Un seul appel a :func:`plier_le_chemin`, avec la place reellement
        disponible a droite de la colonne de valeur. La recalculer chez
        l'appelant ferait deux redactions du meme budget.
        """
        return plier_le_chemin(self.preparee.source_path,
                               largeur - COLONNE_DE_VALEUR,
                               LIGNES_DU_CHEMIN, ascii_seul) or [""]

    def colonnes_du_chemin(self, ascii_seul: bool = False) -> int:
        """La largeur du chemin ENTIER, en colonnes -- la mesure de `E2-1h`."""
        return jetons.colonnes(_replie(self.preparee.source_path, ascii_seul))

    def chemin_coupe(self, largeur: int = jetons.LARGEUR_PLANCHER,
                     ascii_seul: bool = False) -> bool:
        """Le repliement a-t-il du retirer quelque chose ?

        Mesure et non declaration : on recolle ce qui est rendu et on le
        compare au chemin. C'est l'invariant que :func:`segments_de_chemin`
        promet (« recoller les segments rend le chemin, caractere pour
        caractere »), pris comme oracle -- un test de presence du glyphe `…`
        serait faux le jour ou un vrai dossier en porterait un.
        """
        return "".join(self.chemin_replie(largeur, ascii_seul)) != _replie(
            self.preparee.source_path, ascii_seul)

    # -- ce qui vit HORS du cartouche ---------------------------------------

    def colorimetrie_signalee(self) -> bool:
        """Le triplet colorimetrique est-il signale par la source ?"""
        return texte_de_l_espace_couleur(self.preparee.record.source_fields)[1]

    def assertion(self, ascii_seul: bool = False) -> str | None:
        """La ligne `▲ Le rush sera traité comme Rec. 709…`, ou `None`.

        Elle n'apparait que sur `E2-1g`, et **hors du cartouche** : voir
        :data:`ASSERTION_REC709` pour ce que cette place engage.
        """
        if self.colorimetrie_signalee():
            return None
        return jetons.marque("substitute", _replie(ASSERTION_REC709,
                                                   ascii_seul), ascii_seul)

    def bandeau(self, ascii_seul: bool = False) -> str:
        """La droite du bandeau : `plan séquence 12.mov · 25 fps · 4:12`.

        **Le VRAI nom du fichier, jamais l'identifiant derive**
        (`EPIC11-ARB-153`, renforce par `EPIC11-ARB-228` : « Ok ainsi » --
        l'ecran ne montre pas `plan-sequence-12`, et une ligne « nom sur le
        disque » a ete refusee nommement). C'est la seule difference avec
        :func:`rushes.bandeau_du_rush`, et elle suffit a interdire de l'appeler.

        La seconde difference est une consequence d'`EPIC11-ARB-227` : une
        valeur absente **s'omet** ici, la ou `bandeau_du_rush` pose le glyphe
        `neutre` pour garder ses trois colonnes alignees d'un rush a l'autre.
        Un bandeau n'est pas une colonne : rien ne s'aligne dessous.
        """
        morceaux = [self.preparee.source_name,
                    rushes.cadence_lisible(self.preparee.fps_source),
                    rushes.duree_de_rush(self.preparee.cardinal_de_frames,
                                         self.preparee.fps_source)]
        return _replie(
            rushes.SEPARATEUR.join(m for m in morceaux if m), ascii_seul)

    def etat(self, largeur: int = jetons.LARGEUR_PLANCHER,
             ascii_seul: bool = False) -> str:
        """La ligne d'etat : une MESURE de l'ecran courant (`EPIC11-ARB-56`).

        Elle porte un prefixe et une mesure, et les quatre maquettes la
        dessinent dans trois etats :

        * `6 300 frames source · 4e rush du projet — rien n'a encore été écrit`
        * `6 300 frames source · espace couleur non signalé — aucune valeur écrite`
        * `6 300 frames source · chemin de 115 colonnes, coupé au milieu`

        **Le prefixe part avec le cardinal** (`E2-1i`), et c'est une deduction
        ecrite plutot qu'un arbitrage : `EPIC11-ARB-227` porte nommement sur la
        ligne `Résolution`, mais la ligne d'etat porte le meme chiffre, et
        `EPIC11-ARB-56` veut qu'elle porte une MESURE -- un cardinal non
        corrobore n'en est pas une, et l'ecrire ferait dire a la ligne d'etat
        ce que le panneau vient de se refuser a dire.

        **L'ORDRE DES TROIS MESURES EST UN CHOIX, et aucune maquette ne le
        tranche** : aucune ne montre un chemin coupe ET une colorimetrie
        absente en meme temps. La colorimetrie passe devant parce qu'elle porte
        sur ce que le manifeste ECRIT -- une absence enregistree --, la ou la
        coupe du chemin ne porte que sur le rendu de cet ecran-ci. Le jour ou
        Egan tranche autrement, c'est ici et nulle part ailleurs.
        """
        if not self.colorimetrie_signalee():
            mesure = ETAT_COULEUR_ABSENTE
        elif self.chemin_coupe(largeur, ascii_seul):
            mesure = (f"chemin de {self.colonnes_du_chemin(ascii_seul)} "
                      "colonnes, coupé au milieu")
        elif self.rang is not None:
            mesure = (f"{rang_ordinal(self.rang)} rush du projet — "
                      f"{RIEN_ECRIT_ENCORE}")
        else:
            mesure = RIEN_ECRIT_ENCORE
        cardinal = self.preparee.cardinal_de_frames
        if cardinal is not None:
            mesure = (f"{cardinal_lisible(cardinal)} frames source"
                      f"{rushes.SEPARATEUR}{mesure}")
        return _replie(mesure, ascii_seul)


# ==========================================================================
# La FICHE de refus de conflit : ce que `E2-1f` affiche, en modele pur
#
# `EPIC11-ARB-231` (Egan, 2026-09-05) a redessine cette maquette et lui a
# donne sa troisieme sortie ; `EPIC11-ARB-148` a donne au refus du coeur de
# quoi la remplir. Jusqu'a ce lot, la TUI n'avait ni l'un ni l'autre : elle
# attrapait `RefusDeDeclaration` et NOMMAIT l'ecran manquant.
#
# **Aucune valeur de ce cartouche n'est recalculee, et aucune n'est relue dans
# le manifeste.** Tout se lit sur le refus -- `refus.criteres.declares` pour
# les criteres, `refus.entree` pour le nom et le chemin d'origine. C'est
# `EPIC11-ARB-148` a la lettre : la comparaison se tient a UN SEUL endroit, et
# relire le manifeste depuis la TUI y poserait une seconde source de verite
# pour la meme question.
# ==========================================================================


def code_de_refus(motif: str) -> str:
    """`rush_deja_declare` -> `rush-deja-declare`, le code que l'ecran montre.

    **Deux conventions coexistent dans le depot, et aucune des deux n'est
    fautive** : le coeur nomme ses motifs comme des identifiants Python
    (`MOTIF_RUSH_DEJA_DECLARE = "rush_deja_declare"`), les ECRANS de refus
    portent un code a tirets -- c'est la forme de `rushes.CODES_DE_REFUS`,
    tous en minuscules a tirets, et c'est ce que la maquette `E2-1f` dessine.

    La conversion est ecrite **une fois** plutot que le code recopie a cote du
    motif : deux redactions divergeraient au premier motif ajoute, et le
    generateur des maquettes le dit deja de son cote (« un code de refus est un
    identifiant enumere que rien n'autorise a renommer depuis une maquette »).
    """
    return motif.replace("_", "-")


def etat_du_refus_de_conflit(motif: str, choix: ChoixExclusif,
                             ascii_seul: bool = False) -> str:
    """`✕  rush-deja-declare · 3 issues, 2 écrivent · le manifest est inchangé`.

    **Les deux cardinaux sont COMPTES sur le choix rendu, jamais ecrits**
    (`EPIC11-ARB-56`, `DESIGN.md` section 3 : la ligne d'etat porte une
    MESURE). C'est exactement la panne qu'`EPIC11-ARB-231` a produite du cote
    de la maquette : l'ecran gagne une sortie, la ligne d'etat continue d'en
    annoncer deux, et personne ne rougit. Un cardinal perime est pire
    qu'absent -- il se lit comme une verification.

    **L'accord du verbe suit le cardinal**, pour le meme motif : `2 écrivent`
    contre `1 écrit`. Une ligne qui dirait `2 écrit` se lirait comme une faute
    de frappe, et une relecture ne la rattrape pas plus qu'elle n'a rattrape le
    cardinal perime.

    Le dernier tiers est `rushes.MANIFESTE_INCHANGE`, **lu et non recopie** :
    c'est un FAIT garanti par `_atomic_write`, et c'est la meme phrase que
    `E2-1d` porte apres un refus de relink.
    """
    ecrivantes = sum(1 for issue in choix.issues if issue.ecrit)
    verbe = "écrivent" if ecrivantes > 1 else "écrit"
    texte = (f"{jetons.glyphes(ascii_seul)['absent']}  "
             f"{code_de_refus(motif)}{rushes.SEPARATEUR}"
             f"{len(choix.issues)} issues, {ecrivantes} {verbe}"
             f"{rushes.SEPARATEUR}{rushes.MANIFESTE_INCHANGE}")
    return _replie(texte, ascii_seul)


@dataclass(frozen=True)
class FicheDeRefusDeConflit:
    """Ce que le cartouche de `E2-1f` affiche, sur une seule redaction.

    Elle est **pure**, comme :class:`FicheDeDeclaration` dont elle reprend la
    facture (`TITRE_*`, `COLONNE_DE_VALEUR`, `LIBELLE_*`, une methode
    :meth:`lignes`) : elle ne lit ni le disque ni le manifeste, elle prend le
    refus que le coeur a leve et rend des lignes.

    `refus` est un
    :class:`~mixed_media_utility.declaration_de_rush.RefusDeDeclaration` de
    motif `MOTIF_RUSH_DEJA_DECLARE`. Il porte tout ce que la maquette dessine
    depuis `EPIC11-ARB-148` : `source_name`, `rush_id`, `entree` (l'entree
    `rushes[]` qui bloque) et `criteres` (la preuve, partitionnee).

    **Le cote DECLARE, et lui seul.** Les quatre criteres se lisent sur
    `refus.criteres.declares` -- ce que le manifeste porte deja --, jamais sur
    `mesures`. Ce n'est pas indifferent alors meme que les deux coincident par
    construction (c'est ce qui fait le refus) : le cartouche s'appelle « un
    rush identique existe **deja** » et sa derniere ligne dit « **Déclaré**
    depuis ». Il decrit le rush enregistre, pas le fichier qu'on vient de
    designer. Et prendre l'un pour l'autre serait invisible a la relecture --
    d'ou la fabrique du banc, qui fait DIVERGER les deux cotes sur chaque axe.

    **Une valeur absente retire sa ligne** (`DESIGN.md` section 3, « omission
    stricte : jamais `null`, jamais une valeur par defaut »), exactement comme
    sur `E2-1e`. Le cas se produit : un rush declare avant que la duree ne
    devienne un critere d'identite ne porte aucun cardinal, et son critere est
    alors **non verifiable** -- ce que la maquette ne dessine pas. Voir
    :meth:`criteres_absents` pour ce que ce lot a laisse ouvert plutot que
    d'inventer une formulation qu'Egan n'a pas validee.
    """

    refus: object

    # -- les valeurs, toutes lues sur le refus ------------------------------

    @property
    def _entree(self):
        """L'entree `rushes[]` qui bloque, ou un mapping vide.

        Vide plutot que `None` : les cinq lectures qui suivent seraient sinon
        cinq gardes, et une garde oubliee ferait lever l'ecran au lieu de
        retirer une ligne.
        """
        return getattr(self.refus, "entree", None) or {}

    @property
    def _declares(self):
        """Le cote DECLARE de la preuve, ou `None` si le refus n'en porte pas.

        Un refus construit a la main -- c'est le cas d'un banc qui substitue le
        coeur -- peut n'avoir aucun `criteres` : le cartouche se reduit alors a
        ce que l'entree porte, plutot que de lever.
        """
        criteres = getattr(self.refus, "criteres", None)
        return None if criteres is None else criteres.declares

    def cadence(self) -> float | None:
        """La cadence declaree, en nombre -- lue du critere, jamais du record.

        Le critere est un rationnel exact (`25/1`, `24000/1001`) parce que
        c'est sous cette forme que le coeur le compare ; l'ecran a besoin d'un
        nombre pour :func:`rushes.cadence_lisible`. La conversion vit **ici et
        une seule fois**, et elle sert aussi bien la ligne `Base de timecode`
        que la duree de la ligne `Durée source` -- deux lectures separees
        (l'une du critere, l'autre de `entree["fps_source"]`) pourraient
        diverger sur la meme cadence, et le cartouche se contredirait
        lui-meme.
        """
        from fractions import Fraction

        declares = self._declares
        exact = None if declares is None else declares.fps_source_exact
        if exact is None:
            return None
        try:
            return float(Fraction(str(exact)))
        except (ValueError, ZeroDivisionError):
            # Un manifeste corrompu ne fait pas lever un ecran de refus : il
            # retire la ligne. Le refus lui-meme reste montrable, et c'est la
            # seule chose qui compte devant un operateur bloque.
            return None

    def cardinal(self) -> int | None:
        """Le cardinal de frames declare, ou `None`."""
        declares = self._declares
        return None if declares is None else declares.source_frame_count

    def timecode(self) -> str | None:
        """Le timecode initial declare, ou `None`."""
        declares = self._declares
        return None if declares is None else declares.source_start_timecode

    def nom_du_fichier(self) -> str | None:
        """Le nom du fichier **du rush deja declare**.

        Pris sur l'entree et non sur `refus.source_name`, qui est le nom du
        fichier que l'operateur vient de designer. Les deux coincident dans le
        cas nominal -- le `rush_id` derive du nom, donc deux entrees comparees
        sous le meme identifiant portent le meme nom de base --, mais pas
        toujours : `normalize_identifier` replie les accents et les espaces, si
        bien que `plan séquence 12.mov` et `plan_sequence_12.MOV` rendent le
        meme identifiant. Le cartouche decrit le rush **declare** ; c'est donc
        son nom a lui qu'il porte, et le nom designe reste au bandeau.
        """
        nom = self._entree.get("source_name")
        return str(nom) if nom else None

    def declare_depuis(self) -> str | None:
        """Le DOSSIER d'ou le rush declare a ete pris, separateur final compris.

        Lu sur `entree["source_path"]` -- le chemin absolu resolu que
        `EPIC7-ARB-41` fait ecrire au manifeste, et le seul champ exempte de
        l'interdit des chemins absolus. `source_parent` ne convient pas : il ne
        porte que le NOM du dossier (`hd`), et la maquette dessine un chemin.

        Le dernier segment -- le nom du fichier -- est retire par
        :func:`segments_de_chemin`, jamais par `Path.parent` : un chemin
        Windows lu sous Linux ne se decompose pas, et `PurePath` rendrait le
        chemin entier comme un seul nom. Recoller les segments restants rend le
        dossier **avec** son separateur final, ce que la maquette dessine.

        `None` quand l'entree ne porte aucun chemin : la ligne s'omet alors,
        plutot que d'afficher le nom de dossier nu, qui se lirait comme un
        chemin ampute.
        """
        chemin = self._entree.get("source_path")
        if not chemin:
            return None
        morceaux = segments_de_chemin(str(chemin))
        if len(morceaux) < 2:
            return None
        return "".join(morceaux[:-1])

    def criteres(self) -> tuple[tuple[str, str | None], ...]:
        """Les quatre couples `(libelle, valeur)` du cartouche, dans l'ordre.

        **La seule redaction des quatre criteres**, et c'est la fermeture de
        `F16`. Ils vivaient en deux exemplaires -- l'inventaire de
        :meth:`criteres_absents` et le rendu de :meth:`lignes_des_criteres` --
        et les deux ne posaient pas la meme question : l'un testait `is None`,
        l'autre la VERACITE. Mesure de l'ecart : sur
        `source_start_timecode = ""`, la ligne du cartouche etait bien retiree
        et le critere n'etait nomme absent par personne. L'inventaire annoncait
        alors quatre criteres montres quand l'ecran en montrait trois --
        exactement l'ecart tu que cette mesure existe pour rendre visible.

        **Ce que l'ecart n'est PAS, dit plutot que tu** : il est LATENT et non
        vivant, et c'est pourquoi la revue le classe en tolerance documentee.
        `extraction.CriteresIdentiteRush.declares` replie `""` en `None` avant
        que la preuve n'arrive ici, donc aucun chemin du coeur ne produit
        aujourd'hui une valeur fausse qui ne soit pas `None`. Le contrat n'en
        est pas moins rompu : `CriteresIdentiteRush` est une dataclasse publique
        sans validation, et la docstring de cette fiche pose nommement le cas
        d'« un banc qui substitue le coeur ».

        Une source unique ne les rend pas seulement d'accord aujourd'hui : elle
        les rend **structurellement incapables** de diverger, ce qu'une seconde
        relecture ne garantit pas. Les deux methodes partitionnent desormais ce
        couple-ci par la meme veracite, donc l'ensemble nomme absent est le
        complement exact de l'ensemble dessine.

        Les valeurs sont celles du RENDU -- `texte_de_la_duree` et
        `cadence_lisible`, pas le cardinal ni la cadence brute --, parce que
        c'est le rendu qui decide de l'omission : une duree derivee peut manquer
        la ou son cardinal ne manque pas.
        """
        return (
            (LIBELLE_NOM, self.nom_du_fichier()),
            (LIBELLE_DUREE_SOURCE, self.texte_de_la_duree()),
            (LIBELLE_BASE_DE_TIMECODE, rushes.cadence_lisible(self.cadence())),
            (LIBELLE_TIMECODE_INITIAL, self.timecode()),
        )

    def criteres_absents(self) -> tuple[str, ...]:
        """Les criteres que le cartouche ne peut PAS montrer, nommes.

        **Ce n'est pas un rendu, c'est une mesure de ce qui manque**, et elle
        existe pour que l'ecart avec la maquette soit visible plutot que tu.
        `E2-1f` dessine quatre criteres ; un rush declare avant que la duree ne
        devienne un critere d'identite n'en porte que deux, et les lignes
        manquantes s'omettent (`DESIGN.md` section 3).

        **L'arbitrage que cette methode attendait est tranche**
        (`EPIC11-ARB-237`, Egan le 2026-09-05) : un critere d'identite non
        mesurable s'**OMET** du cartouche -- ni glyphe, ni mention « non
        vérifiable », ni refus de monter l'ecran. C'est `EPIC11-ARB-227`
        applique (« on n'affiche rien si on ne corrobore pas »), et le cout est
        ecrit dans l'arbitrage : le lecteur ne sait pas sur combien de criteres
        la machine a juge. La position etant desormais tenue plutot que subie,
        cette methode doit nommer **exactement** l'ensemble omis, et une
        frontiere le tient -- ce qu'elle ne faisait pas : voir
        :meth:`criteres`.
        """
        return tuple(libelle for libelle, valeur in self.criteres()
                     if not valeur)

    # -- le corps du cartouche ---------------------------------------------

    def texte_de_la_duree(self) -> str | None:
        """`6 300 frames · 4:12` -- le cardinal declare et ce qu'il fait.

        La duree est **derivee** du cardinal et de la cadence, tous deux lus
        sur le refus : c'est `rushes.duree_de_rush`, la meme fonction que la
        colonne technique de `E2-1` et que la ligne `Résolution` de `E2-1e`
        appellent. Une troisieme redaction rendrait `4:12` sur un ecran et
        `4:11` sur le suivant pour le meme rush.

        Rend `None` quand le cardinal manque : la ligne s'omet alors entiere,
        plutot que de porter une duree sans la grandeur qui la fonde --
        `EPIC11-ARB-227` a tranche « on n'affiche rien si on ne corrobore
        pas », et l'entree qui ne porte pas de cardinal est exactement le cas
        ou il n'a pas ete corrobore.
        """
        cardinal = self.cardinal()
        if cardinal is None:
            return None
        morceaux = [f"{cardinal_lisible(cardinal)} frames"]
        duree = rushes.duree_de_rush(cardinal, self.cadence())
        if duree is not None:
            morceaux.append(duree)
        return rushes.SEPARATEUR.join(morceaux)

    def code(self, ascii_seul: bool = False) -> str:
        """`✕ rush-deja-declare` -- le glyphe d'etat, puis le code.

        Le glyphe est pose par :func:`jetons.marque` et jamais recopie, comme
        `rushes.Refus.titre` le fait deja pour `E2-1d`.
        """
        return jetons.marque("absent",
                             code_de_refus(getattr(self.refus, "motif", "")),
                             ascii_seul)

    def lignes(self, largeur: int = jetons.LARGEUR_PLANCHER,
               ascii_seul: bool = False) -> list[str]:
        """Le contenu du cartouche `Un rush identique existe déjà`.

        L'ordre est celui de la maquette, et les DEUX lignes vides qu'il porte
        ne sont pas interchangeables -- c'est le generateur de `E2-1f` qui le
        dit, et c'est pourquoi elles sont posees ici plutot que par l'ecran :

        * le code et la phrase qui l'explique **font un bloc** : ils disent la
          meme chose a deux grains, et c'est la ligne vide qui les separait
          qu'`EPIC11-ARB-231` a prise pour loger sa troisieme sortie ;
        * la ligne vide qui **precede** les quatre criteres ouvre le bloc de
          la preuve ;
        * celle qui precede `Déclaré depuis` tient une separation de SENS
          (`DESIGN.md` section 7.4). La retirer ferait lire la provenance comme
          un CINQUIEME critere, c'est-a-dire le defaut exact que nomme
          `EPIC11-ARB-150`.

        `largeur` est la largeur ECRIVABLE du cartouche, pas celle de la
        fenetre : l'ecran la derive par `jetons.largeur_de_cartouche`, et un
        banc peut la poser a la main pour se comparer a la maquette.
        """
        lignes = [self.code(ascii_seul)]
        lignes.extend(jetons.envelopper(PHRASE_DU_CONFLIT, largeur,
                                        ascii_seul))
        criteres = self.lignes_des_criteres(largeur, ascii_seul)
        if criteres:
            lignes.append("")
            lignes.extend(criteres)
        provenance = self.ligne_de_provenance(largeur, ascii_seul)
        if provenance is not None:
            lignes.append("")
            lignes.append(provenance)
        return lignes

    def lignes_des_criteres(self, largeur: int = jetons.LARGEUR_PLANCHER,
                            ascii_seul: bool = False) -> list[str]:
        """Les quatre criteres chiffres, dans l'ordre de la maquette.

        Chacun s'omet si sa valeur manque -- voir :meth:`criteres_absents`. La
        composition de la ligne est :func:`ligne_de_fiche`, **partagee avec
        `E2-1e`** : c'est elle qui cale la valeur sur
        :data:`COLONNE_DE_VALEUR` et qui BORNE la valeur a la largeur du
        cartouche. Une seconde redaction du calage ferait deux cartouches qui
        ne se lisent plus l'un sous l'autre, et c'est le meme operateur qui les
        voit a une frappe d'intervalle.

        Les couples sont pris a :meth:`criteres`, qui est leur seule redaction :
        le rendu et l'inventaire de :meth:`criteres_absents` partitionnent la
        MEME liste par la MEME veracite, et ne peuvent donc plus se contredire
        (`F16`).
        """
        return [ligne_de_fiche(libelle, valeur, largeur, ascii_seul=ascii_seul)
                for libelle, valeur in self.criteres() if valeur]

    def ligne_de_provenance(self, largeur: int = jetons.LARGEUR_PLANCHER,
                            ascii_seul: bool = False) -> str | None:
        """`Déclaré depuis           D:\\HOKO\\Documents\\…\\03_tournage_mai\\hd\\`.

        Le chemin est replie par :func:`plier_le_chemin` sur **une seule
        ligne**, et non par `jetons.abreger_chemin` : c'est la note 6 d'Egan
        (trois premiers dossiers, coupe, les deux derniers au moins), et c'est
        ce que la maquette dessine. Le motif est mesure et il est le meme que
        pour :func:`libelle_de_relink` -- ce chemin est un DOSSIER, donc il
        finit par un separateur, donc `abreger_chemin` sert la queue sur un
        budget nul et mange precisement le segment qui distingue deux journees
        de tournage.

        `plier_le_chemin` rend toujours quelque chose (au pire la regle du
        depot, sur une ligne bornee) : la ligne ne disparait donc jamais parce
        que le chemin serait trop long, seulement parce que l'entree n'en porte
        aucun.
        """
        chemin = self.declare_depuis()
        if chemin is None:
            return None
        place = largeur - COLONNE_DE_VALEUR
        coupe = plier_le_chemin(chemin, place, lignes=1, ascii_seul=ascii_seul)
        return ligne_de_fiche(LIBELLE_DECLARE_DEPUIS,
                              coupe[0] if coupe else chemin, largeur,
                              ascii_seul=ascii_seul)

    def etats_des_lignes(self) -> dict[int, str]:
        """Quelle ligne du cartouche porte l'etat `absent`, et elle est SEULE.

        **C'est une MESURE du rendu valide, pas une deduction.** Le rendu
        couleur de `E2-1f` (`maquettes-couleur/`) peint la ligne du code en
        `state-absent` (`#EE878A`) et **toutes** les autres en texte ordinaire :
        la phrase d'explication comme les quatre criteres.

        Cela n'entre pas en conflit avec `EPIC11-ARB-71` (« toutes les lignes
        du refus sont en `absent`, y compris les repliees »), qui porte sur
        `E2-1d` : la-bas, le bloc entier **est** le message du coeur, replie.
        Ici, le message du coeur n'est pas affiche du tout -- le cartouche
        porte le code, une explication, et la PREUVE. Une preuve peinte en
        rouge se lirait comme quatre erreurs.
        """
        return {0: "absent"}

    # -- ce qui vit HORS du cartouche --------------------------------------

    def bandeau(self, ascii_seul: bool = False) -> str:
        """La droite du bandeau : `plan séquence 12.mov · refusé`.

        **Le nom DESIGNE, et pas celui de l'entree** -- c'est la seule place de
        cet ecran ou les deux se separent, et le partage est celui
        d'`EPIC11-ARB-153` : le bandeau dit ce que l'operateur vient de faire,
        le cartouche dit ce que le projet porte deja. Le VRAI nom du fichier,
        accents et espaces compris, jamais l'identifiant derive
        (`EPIC11-ARB-228`).
        """
        nom = getattr(self.refus, "source_name", None) or ""
        morceaux = [morceau for morceau in (nom, MENTION_REFUSE) if morceau]
        return _replie(rushes.SEPARATEUR.join(morceaux), ascii_seul)

    def separation_offerte(self) -> bool:
        """La sortie « c'est un autre rush » est-elle encore une issue ?

        **LUE sur `refus.issues`, jamais redecidee ici.** C'est la fermeture de
        `F1` : l'ecran composait ses trois suites sans jamais ouvrir la liste
        d'issues que le refus porte, si bien que le mecanisme
        d'`issue_de_remplacement` -- ecrit dans le coeur pour cesser de proposer
        `--force-distinct` la ou il ne change rien (`EPIC11-ARB-233`) --
        s'arretait au coeur. Deux couches de la revue ont mesure la
        consequence au clavier : entree sur la seconde suite, **meme ecran**,
        memes issues, aucune information neuve, boucle indefinie.

        Le partage est celui d'`issues_du_refus` et il ne bouge pas : ce qui se
        lit du coeur est le **cardinal et l'ordre**, jamais le texte -- les
        libelles appartiennent au dessin. La comparaison est donc positionnelle
        et porte sur le RANG 1, le seul emplacement que le coeur remplace, et
        elle se fait contre la table publiee plutot que contre une chaine
        recopiee ici : deux redactions du meme libelle divergeraient au premier
        ajustement, et cette methode cesserait alors de mesurer sans rougir.

        Trois regimes de repli rendent `True`, c'est-a-dire le cas ordinaire :
        un refus sans liste d'issues (un banc qui substitue le coeur en
        construit), un motif absent de la table, et une table a moins de deux
        entrees. Aucun des trois ne dit que le coeur a retire la sortie ; la
        retirer sur un silence serait la redecider.
        """
        issues = getattr(self.refus, "issues", None) or ()
        defaut = ISSUES_PAR_MOTIF.get(getattr(self.refus, "motif", "")) or ()
        if len(defaut) < 2:
            return True
        if not issues:
            return True
        return len(issues) > 1 and issues[1] == defaut[1]

    def suites(self, chemin_designe: str,
               largeur: int = jetons.LARGEUR_PLANCHER,
               ascii_seul: bool = False) -> ChoixExclusif:
        """Les sorties, composees sur le nom DESIGNE et le chemin designe.

        Le chemin est celui que l'operateur vient de designer, **jamais celui
        d'ou vient le rush deja declare** (`EPIC11-ARB-153`, note 3) : relinker
        vers le dossier d'origine ne repointerait rien. C'est aussi la note 4 --
        c'est la seule place de l'ecran ou le chemin designe apparait, le
        cartouche ne portant que celui de l'entree.

        **Trois dans le cas ordinaire, deux quand le coeur a retire la
        seconde** : le cardinal n'est pas ecrit ici, il se lit sur le refus par
        :meth:`separation_offerte`. La ligne d'etat le recompte d'elle-meme,
        `etat` prenant le choix REELLEMENT rendu.
        """
        nom = getattr(self.refus, "source_name", None) or ""
        return suites_du_rush_deja_declare(nom, chemin_designe, largeur,
                                           ascii_seul,
                                           self.separation_offerte())

    def ligne_des_rangs_epuises(self, ascii_seul: bool = False) -> str | None:
        """La ligne d'explication de `E2-1j`, ou `None` sur `E2-1f` ordinaire.

        **Elle est le PENDANT exact de la suite retiree**, et c'est ce que la
        maquette dessine : `E2-1j` n'ajoute pas une ligne a `E2-1f`, il en
        remplace une. La zone centrale de cet ecran est pleine a 17 sur 17
        (voir la docstring d'`EcranRefusDeConflit`) -- une ligne de plus la
        ferait deborder, et une ligne de moins laisserait un trou.

        Elle se lit donc sur :meth:`separation_offerte`, jamais sur un second
        predicat : deux lectures du meme regime divergeraient au premier
        ajustement, et l'ecran porterait alors la ligne ET la suite, ou
        aucune des deux.
        """
        if self.separation_offerte():
            return None
        return phrase_des_rangs_epuises(ascii_seul)

    def etat(self, choix: ChoixExclusif, ascii_seul: bool = False) -> str:
        """La ligne d'etat, MESUREE sur le choix que l'ecran dessine.

        Le choix est **passe** plutot que refabrique : c'est celui que l'ecran
        porte, donc celui dont le curseur bouge, et le compter deux fois
        laisserait la ligne d'etat annoncer un ecran qui n'est pas a l'ecran.
        """
        return etat_du_refus_de_conflit(getattr(self.refus, "motif", ""),
                                        choix, ascii_seul)
