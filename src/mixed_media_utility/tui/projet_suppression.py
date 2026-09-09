# -*- coding: utf-8 -*-
"""`E6-2`, `E6-2b`, `E6-2c` et `E6-3` -- retirer un objet du projet (story 11.11,
lot C, AC 3 et AC 4).

**Ce module n'ecrit rien lui-meme, et c'est sa propriete la plus mesuree.** Il
prepare, il montre, il demande -- puis il appelle
:func:`project_maintenance.remove_project_element`, qui est le seul endroit du
depot qui supprime. Une frontiere NEGATIVE le tient a l'AST : aucun `unlink`,
`rmtree` ni `remove` n'est appele ici (AC 4.1). Une frontiere negative est le
seul moyen d'attraper la REINTRODUCTION du defaut -- aucun test positif ne
verrait revenir un `shutil.rmtree` glisse dans une branche d'erreur.

Le cartouche porte le rapport de `dry_run`, jamais un recalcul (AC 3.2)
------------------------------------------------------------------------
Chaque chiffre du panneau vient du `RapportSuppression` que le coeur a rendu
en `dry_run=True` : le cardinal, la liste des fichiers, les dossiers de scan,
les rangs liberables, les annexes attendues-absentes. L'ecran les met en page,
il n'en produit aucun.

**Deux valeurs que le rapport ne porte PAS, dites plutot que tues.**

1. **le poids libere.** `RapportSuppression` ne porte aucun octet -- c'est
   l'ecart 1 du lot D, ouvert depuis le 2026-09-01 et toujours ouvert. Il est
   donc **mesure sur le disque** par :func:`poids_des_fichiers`, un `lstat`
   garde sur chacun des chemins que le rapport nomme. Mesurer le disque n'est
   pas recalculer le coeur : c'est le meme geste, et le meme precedent, que
   `atelier_exports_resultat.octets_du_master`. Ce qui serait fautif serait
   d'estimer un poids par nature ou par cardinal moyen ;
2. **le motif d'un fichier reste.** Le coeur nomme les chemins
   (`fichiers_non_supprimes`) et pas la raison. `E6-3` en dessine une
   (« droits refusés ou fichier verrouillé ») : elle est ici une phrase
   **generique** et assumee comme telle, pas un diagnostic -- voir
   :data:`MOTIF_DES_RESTES`.

Ce que ce module ne fait pas, et c'est structurel
--------------------------------------------------
* il **ne modifie ni `execution.py` ni `project_maintenance.py`** : le point de
  jugement chiffre est le patron deja livre par la story 11.1, et la
  suppression est le point d'entree de coeur deja livre par la 11.13 ;
* il **n'ouvre aucun champ de saisie** (`EPIC11-ARB-141`) : le modele de noms
  est vide, donc `Tab` n'a aucune destination et `EcranChiffre.traiter` le rend
  inerte de lui-meme ;
* il **n'importe jamais `cli`** (`EPIC11-ARB-67`) ;
* il **ne dessine aucun ecran dont la maquette n'est pas validee**
"""
from __future__ import annotations

import os

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Static

from ..io import naming
from ..project_inventory import (ETAT_DECLARE_ABSENT, NATURE_FRAMES_EXTRAITES,
                                 NATURE_FRAMES_SCANNEES, NATURE_LOT,
                                 NATURE_LOT_SCANNE, NATURE_MASTER,
                                 NATURE_PLANCHE, NATURE_RUSH, NATURE_SCAN)
from ..project_maintenance import (LastLotRefusedError, ProjectMaintenanceError,
                                   RapportDeGroupe, RapportSuppression,
                                   remove_project_element, remove_project_group)
from . import jetons, projet_lecture
from .atelier_extraction import Composition, _application_montee
from .atelier_extraction_ecriture import _lancer_apres_le_dessin
from .coque import EcranPasEncore, ObjetTravaille, Palier
from .execution import (EcranChiffre, EcranRefus, EcranResultat, bloc_peint,
                        ouvrir_dans_l_explorateur_du_systeme)
from .panneau import (RIEN_ECRIT, ChoixExclusif, Issue, LigneChiffree, Panneau)
from .projet_inventaire import (EcranInventaireDuProjet, NoeudAffiche,
                                QUAND_LA_GESTION_DES_MEDIAS, code_du_refus,
                                grouper_les_milliers, poids_lisible,
                                relire_l_inventaire, tige_et_rang)

# ---------------------------------------------------------------------------
# Les textes, verbatim des maquettes validees
# ---------------------------------------------------------------------------

#: Le titre du cartouche d'`E6-2` : `À supprimer — tout le lot plan-04_12p5`.
#: Le motif est un gabarit et non une concatenation au point d'usage : c'est
#: ce qui le fait balayer par les gardes d'epic de repli ASCII.
TITRE_A_SUPPRIMER = "À supprimer — {cible}"

#: Le titre du cartouche d'`E6-3`, en capitales sur le mot qui compte.
#: `E6-3` ne dessine QUE le cas incomplet, et c'est voulu -- voir
TITRE_INCOMPLETE = "Suppression INCOMPLÈTE"
#: Le titre de `E6-3b`. Il dit `Supprimé` la ou les quatre autres ecrans de
#: compte rendu du depot disent `Écrit` : meme role -- nommer ce qui vient
#: d'avoir lieu --, et `Écrit` serait faux ici, le manifeste etant la seule
#: chose que la suppression ecrive.
TITRE_REUSSITE = "Supprimé"

#: Le titre de l'ecran de progression `E6-2c`.
TITRE_EN_COURS = "Suppression en cours"

LIBELLE_ELEMENT = "Élément"
LIBELLE_FICHIERS = "Fichiers"
LIBELLE_POIDS = "Poids libéré"
LIBELLE_EMPORTES = "Emportés avec le lot"
LIBELLE_RANGS = "Rangs libérables"
LIBELLE_MANIFESTE = "Manifeste"
LIBELLE_SUPPRIMES = "Supprimés"
LIBELLE_RESTES = "Restés"
LIBELLE_MOTIF = "Motif"

#: Le meme libelle sur un plan de GROUPE, **prive de sa moitie fausse**
#: (finding `C2-7`, seconde moitie, mesuree au rendu le 2026-09-07).
#:
#: `LIBELLE_EMPORTES` dit « avec le lot ». Sur un groupe, **aucun lot n'est
#: retire** : :func:`cibles_du_groupe` ne produit que des cibles FINES --
#: planches, masters, scans, lots scannes, frames extraites --, et le lot reste
#: declare apres chacune. `E6-2` annoncait donc un emport qui n'a pas lieu, sur
#: le seul ecran ou l'operateur decide.
#:
#: **Seule la moitie fausse tombe.** Ce que la ligne compte -- les fichiers du
#: rapport, groupes par dossier -- est bien emporte par le geste ; ce n'est
#: simplement pas un lot qui les emporte. Reecrire la ligne entiere ferait
#: diverger deux libelles pour un meme cartouche.
LIBELLE_EMPORTES_DU_GROUPE = "Emportés"

#: La ligne chiffree qui compte les ECARTES d'un groupe sur `E6-3`.
#:
#: Elle est en **éléments**, jamais en fichiers, et l'unite le dit : un membre
#: refuse par le coeur ne rend AUCUN chemin (`LigneDeGroupe.rapport` vaut
#: ``None``), donc rien ne permet de le compter en fichiers. Le compter quand
#: meme dans `Restés` melangerait deux unites dans une meme colonne.
LIBELLE_ECARTES = "Écartés"

#: Les unites du cartouche. Toute ligne chiffree porte la sienne : `LigneChiffree`
#: **refuse a la construction** un nombre sans unite (story 11.1, AC 1.2).
UNITE_FICHIER = "fichier"
UNITE_FICHIERS = "fichiers"
UNITE_GROUPES = "groupes d'objets"
UNITE_GROUPE = "groupe d'objets"
#: L'unite des ECARTES. Voir :data:`LIBELLE_ECARTES` : des elements, pas des
#: fichiers.
UNITE_ELEMENT = "élément"
UNITE_ELEMENTS = "éléments"

#: Ce qu'`E6-2` ecrit a droite de `Manifeste` sur `E6-3`. **Ce n'est pas une
#: supposition** : l'AC 10 de la story 11.13 impose au coeur d'ecrire le
#: manifeste AVANT les fichiers, donc un rapport qui porte des restes porte
#: aussi un manifeste deja a jour. La phrase enonce le contrat du coeur.
MANIFESTE_A_JOUR = "à jour · l'entrée est retirée"

#: Le motif d'`E6-3`, **generique et assume comme tel**. Le coeur nomme les
#: chemins restes, jamais la raison : `fichiers_non_supprimes` est une suite de
#: chemins. Ecrire ici un diagnostic par chemin (« droits refusés » contre
#: « fichier verrouillé ») serait inventer une mesure que rien ne produit --
#: `DESIGN.md` section 3 : un champ non mesure est omis, jamais rendu faux.
MOTIF_DES_RESTES = "droits refusés ou fichier verrouillé"

#: La tete de la premiere ligne d'`E6-3`, sous le glyphe d'absence.
PHRASE_DES_RESTES = "{cardinal} occupent toujours le disque"
PHRASE_DES_RESTES_SINGULIER = "{cardinal} occupe toujours le disque"

#: La tete du bloc des ECARTES d'un groupe, aux deux TEMPS du parcours
#: (`EPIC11-ARB-264`, findings `C1-1` / `C1-2` / `C3-2` / `C3-3`).
#:
#: **Deux temps et non un**, parce que le bloc parait sur deux ecrans que
#: l'ecriture separe : `E6-2` promet (« ne partira pas »), `E6-3` constate
#: (« n'est pas parti »). Une phrase unique au futur ferait lire au compte
#: rendu une promesse pour un fait, et c'est exactement l'ecart qu'`AC 4.2`
#: ferme de l'autre cote -- un ecran de resultat n'annonce pas ce qu'il
#: allait faire.
PHRASE_DES_ECARTES = "{cardinal} ne partiront pas"
PHRASE_DES_ECARTES_SINGULIER = "{cardinal} ne partira pas"
PHRASE_DES_ECARTES_APRES = "{cardinal} ne sont pas partis"
PHRASE_DES_ECARTES_APRES_SINGULIER = "{cardinal} n'est pas parti"

#: Ce que la ligne d'etat d'`E6-2` et d'`E6-2b` dit en queue.
#:
#: **Epinglee PAR REFERENCE a `panneau.RIEN_ECRIT`**, et non recopiee : les
#: maquettes l'ecrivent en bas de casse et sans point final, la constante du
#: depot la porte en phrase. Deux redactions divergeraient au premier ajustement
#: ; une frontiere mesure donc que celle-ci reste `RIEN_ECRIT` a la casse et au
#: point pres, ce qu'aucune relecture ne garantirait.
PHRASE_RIEN_ECRIT = "rien n'a encore été écrit"

#: Ce que la ligne d'etat d'`E6-2c` dit pendant l'ecriture.
PHRASE_ECRITURE_EN_COURS = "écriture en cours"

#: Ce que la ligne d'etat d'`E6-3` dit, verbatim de la maquette.
PHRASE_DES_RESTES_EN_ETAT = "{cardinal} n'ont pas pu être supprimés"
PHRASE_DES_RESTES_EN_ETAT_SINGULIER = "{cardinal} n'a pas pu être supprimé"
PHRASE_MANIFESTE_EN_ETAT = "manifeste à jour"
PHRASE_RETIRES = "{cardinal} retirés"
PHRASE_RETIRE = "{cardinal} retiré"
#: Les phrases de `E6-3b`. `LIBELLE_RANG_LIBERE` ne parait que si le rapport
#: declare un rang rendu : `EPIC11-ARB-92` point 3 -- un rang se consomme et
#: ne se rend que **sur demande**. Une ligne inconditionnelle annoncerait un
#: rang rendu que l'operateur n'a pas demande.
LIBELLE_RANG_LIBERE = "Rang libéré"
MOTIF_DU_RANG_RENDU = "{rang} · le prochain lot le reprendra"
PHRASE_SUPPRIMES_EN_ETAT = "{cardinal} supprimés"
PHRASE_SUPPRIME_EN_ETAT = "{cardinal} supprimé"
PHRASE_LIBERES = "{poids} libérés"
PHRASE_AUCUN_RESTE = "aucun reste"
PHRASE_RANG_RENDU = "rang {rang} rendu"

#: `E6-2b` : la phrase du dernier lot, celle qui dit POURQUOI la confirmation
#: supplementaire existe (AC 3.5).
#:
#: **Ecart nomme, et il n'est pas corrige ici** (ecart 2 du lot D) : le coeur
#: garde le dernier lot du **PROJET** (`confirmation_dernier_lot`), la ou
#: l'AC 3.5 et `E6-2b` decrivent le dernier lot d'un **RUSH**. La phrase dit
#: donc ce que le coeur garde reellement, et non ce que la maquette dessine :
#: annoncer « dernier lot du rush » sur une garde qui compte les lots du projet
#: serait une ligne fausse. Le mot de la maquette est au registre de la story.
PHRASE_DERNIER_LOT = ("Dernier lot du projet : le projet restera déclaré "
                      "sans lot.")

#: La mention de rang portee par la ligne `Rangs libérables`.
#:
#: **Ecart nomme** : `E6-2` dessine `lot v2 · scans v1 · planches v1`,
#: c'est-a-dire un rang PAR NATURE. `RapportSuppression.rangs_liberables` est un
#: tuple d'entiers sans nature -- le coeur ne dit pas de quelle famille chaque
#: rang releve. La ligne rend donc les rangs que le coeur nomme, prefixes du
#: `v` d'`EPIC11-ARB-88`, et rien de plus.
MOTIF_DU_RANG = "v{rang}"
SEPARATEUR = " · "

#: Les libelles des issues. `EPIC11-ARB-89` : jamais une seule issue, jamais un
#: blocage sec, et **toujours** une sortie qui n'ecrit pas.
#:
#: **La mention de droite de la maquette est FONDUE dans le libelle**, et c'est
#: un ecart de mise en page assume : `E6-2` dessine deux colonnes
#: (`Supprimer` … `▲ 67 fichiers, définitif`), et `ChoixExclusif.rendu` rend
#: une ligne par issue, curseur plus libelle. Rendre la seconde colonne
#: demanderait de modifier `panneau.py`, partage par les quatre ateliers et
#: hors perimetre de cette story. La mention n'est donc pas perdue, elle est
#: derriere un tiret -- meme geste que `LIBELLE_FRAMES` de l'atelier Exports.
LIBELLE_SUPPRIMER = "Supprimer"
LIBELLE_SUPPRIMER_ET_LIBERER = "Supprimer et libérer les rangs"
LIBELLE_SUPPRIMER_AVEC_SCANS = "Supprimer, scans compris"
LIBELLE_ANNULER = "Annuler"
MENTION_DEFINITIF = "{cardinal}, définitif"
MENTION_DES_RANGS = "le prochain objet reprendrait le {rangs}"
MENTION_DES_SCANS = "{cardinal} de scan, non refabricables"
MENTION_RIEN_TOUCHE = "rien n'est touché"
MOTIF_DE_L_ISSUE = "{libelle} — {mention}"

#: Les cles des issues. Elles ne sont **jamais** des litteraux au point
#: d'usage : c'est par elles que le parcours reconnait ce qu'il doit appeler.
CLE_SUPPRIMER = "supprimer"
CLE_SUPPRIMER_ET_LIBERER = "supprimer-et-liberer"
CLE_SUPPRIMER_AVEC_SCANS = "supprimer-avec-scans"
CLE_ANNULER = "annuler"

#: Les suites d'`E6-3`, dans l'ordre du dessin.
SUITE_REESSAYER = "Réessayer"
SUITE_OUVRIR = "Ouvrir le dossier"
SUITE_RETOUR = "Retour à l'inventaire"
#: Les suites de `E6-3b`, et elles sont **DEUX**. « Reessayer » n'y figure pas
#: -- il n'y a rien a reprendre, et c'est la difference de fond entre les deux
#: ecrans de compte rendu. « Supprimer un autre element » a ete ecrit puis
#: retire : dans cette TUI, revenir a l'inventaire EST la facon d'en supprimer
#: un autre, si bien que les deux entrees auraient declenche le meme geste.
#: Deux suites qui font la meme chose sont pires qu'une seule -- elles font
#: croire qu'elles different.
SUITE_OUVRIR_PROJET = "Ouvrir le dossier du projet"

#: Ce que les deux ouvertures disent quand elles n'ont **aucun dossier** a
#: remettre au bureau. Une suite qui ne rendrait rien serait la suite
#: decorative que le finding `K3` a payee quatre fois dans cet epic : les
#: ouvertures des trois autres ateliers rendent toutes une phrase dans tous
#: les cas, y compris quand aucun bureau n'est joignable.
AUCUN_DOSSIER_A_OUVRIR = ("Aucun fichier n'est resté sur le disque : il n'y a "
                          "aucun dossier à ouvrir.")
AUCUN_PROJET_A_OUVRIR = "Ce projet n'a plus de dossier lisible à ouvrir."

#: MESURE: 44/49 -- zone utile de 76 colonnes.
RACCOURCIS_CONFIRMATION = "⏎ valider  ↑↓ choisir  Échap retour  F1 aide"
#: MESURE: 7/7 -- `E6-2c` n'annonce que l'aide, et rien d'autre n'agit.
RACCOURCIS_EN_COURS = "F1 aide"
#: La ligne des DEUX comptes rendus, `E6-3` et `E6-3b`, verbatim des maquettes.
#:
#: **`Tab journal` en est RETIRE** (`EPIC11-ARB-246`, Egan le 2026-09-06, par
#: invite, verbatim : « Retirer le jeton de ces deux ecrans »). Ni annonce, ni
#: traite : ces deux ecrans n'ont **aucun journal** a ouvrir -- ils sont montes
#: par :func:`monter_le_compte_rendu`, qui ne leur en passe pas, et depuis cet
#: arbitrage leurs deux `__init__` ne savent meme plus en recevoir un. Annoncer
#: une touche inerte est le defaut `I8`, que ce depot a paye quarante fois ; la
#: traiter sans l'annoncer en est le symetrique, et il n'est pas meilleur.
#:
#: MESURE: 49/54 -- zone utile de 76 colonnes.
RACCOURCIS_RESULTAT = "⏎ choisir  ↑↓ naviguer  Échap inventaire  F1 aide"

#: Ce que `EcranPasEncore` annonce quand la nature visee n'a **aucun** point
#: d'entree fin dans le coeur -- voir :data:`NATURES_SANS_CIBLE_FINE`.
#:
#: **La phrase nomme le COEUR et non un ecran** (`EPIC11-ARB-260`, 2026-09-06).
#: Elle disait « Retirer un {nature} seul du projet », et l'ecran ajoutait
#: « Il arrive avec les ecrans de gestion des medias du palier Projet » --
#: c'est-a-dire une echeance annoncee a un operateur qui est **deja dans** ces
#: ecrans-la. Ce qui manque ici n'est pas un dessin : c'est un mot-cle de
#: `remove_project_element`. L'echeance a donc ete retiree du site plutot que
#: reecrite, et la phrase dit ou est le manque.
CE_QUI_MANQUE_A_LA_CIBLE_FINE = (
    "Retirer un {nature} seul : le coeur n'a pas cette cible")

# ---------------------------------------------------------------------------
# `EPIC11-ARB-260` -- un refus de DOMAINE n'est pas un ecran qui manque
# ---------------------------------------------------------------------------

#: Ce que la ligne de suite propose quand un rush porte encore des lots.
#:
#: **Elle est lue de l'ARBRE, jamais du message du coeur.** La phrase levee
#: nomme bien les `lot_id` en cause, mais la relire pour en extraire un
#: cardinal serait une seconde redaction du coeur logee dans un ecran -- et
#: elle perimerait en silence a la premiere reformulation de cette phrase-la.
#: L'arbre, lui, PORTE la filiation : les lots d'un rush sont ses enfants.
#:
#: MESURE: 48/48 -- le gabarit NU, comme les trois autres lignes
#: mesurees de ce module. Rempli au cardinal a deux chiffres il fait 39
#: colonnes, et `EcranRefus` indente ses suites de cinq (`  └─ `) sur une
#: zone utile de 76 : la marge est large, et c'est voulu -- cette ligne
#: est la SEULE issue nommee d'un refus dont le message, lui, est tronque.
#: **PHRASE et non SUITE, et le nom est le fond du sujet** (renomme le
#: 2026-09-07, sur finding `C1-2` de la couche 1 de la revue). Ce texte parait
#: sur `EcranRefus`, qui rend ses suites **en lecture** et ne traite que `⏎` au
#: clavier : il n'est jamais distribue par :func:`suivre`. Le nommer `SUITE_*`
#: le faisait recenser par `test_couverture_des_suites`, qui exige alors une
#: **branche nommee** dans le dispatcheur -- et la frontiere avait raison de
#: rougir : une suite proposee que rien ne distribue est exactement le defaut
#: `MQ-4`/`MQ-5` qu'elle mesure. La renommer est l'aveu de ce qu'elle est, pas
#: un contournement ; lui inventer une branche aurait cable un chemin mort.
#: Le module portait deja la convention (`PHRASE_MASTER_ILLISIBLE`,
#: `PHRASE_SANS_LOT`) -- c'est elle qui est suivie ici.
PHRASE_DES_LOTS_D_ABORD = "Retirer d'abord ses {cardinal} {mot}, un par un."

#: Le singulier et le pluriel de `lot`, poses plutot que calcules -- « un
#: pluriel calcule sur un groupe nominal accorde le dernier mot et jamais le
#: premier », defaut deja paye dans `cli.py`.
MOT_DES_LOTS = ("lot", "lots")

#: Ce que l'ecran de refus dit quand l'objet vise ne vit sous **aucun** lot.
#:
#: `EPIC11-ARB-224` impose un `lot_id` aux cinq cibles fines : sans lui, il
#: n'y a pas de cible a former. Ce n'est **pas** un ecran qui manque -- c'est
#: un fait sur cet objet-la, et il se dit.
CODE_SANS_LOT = "OBJET_SANS_LOT"
PHRASE_SANS_LOT = (
    "{objet} n'est rattaché à aucun lot de ce projet : ni l'arbre ne le porte "
    "sous un lot, ni son nom ne nomme un lot déclaré. Les cibles fines du "
    "coeur se désignent DANS un lot.")

#: Ce que l'ecran de refus dit quand le nom d'un master ne nomme aucun profil.
CODE_MASTER_ILLISIBLE = "PROFIL_DU_MASTER_ILLISIBLE"
PHRASE_MASTER_ILLISIBLE = (
    "{objet} porte le marqueur de master, mais son nom ne nomme aucun profil "
    "du registre sous le lot {lot}. Le profil ne se devine pas : le coeur "
    "refuserait une cible inventée.")

#: Le repli des deux phrases ci-dessus quand l'objet n'a meme pas de nom de
#: coeur -- un groupe passe a `ouvrir_la_suppression` par un appelant qui ne
#: l'a pas filtre. Il ne devrait pas arriver depuis `E6-1`, qui le refuse en
#: ligne d'etat ; il ne se **suppose** pas pour autant.
OBJET_SANS_NOM = "Cet objet"


# ---------------------------------------------------------------------------
# Designer la cible : ce que le coeur sait viser, et ce qu'il ne sait pas
# ---------------------------------------------------------------------------

#: Les natures que `remove_project_element` ne sait **pas** viser finement, et
#: pourquoi -- mesure du 2026-09-05 sur la signature reelle du coeur.
#:
#: **La table est VIDE depuis le 2026-09-07, et c'est un fait sur le coeur, pas
#: un relachement de la garde.** Elle portait `frames_extraites` : « le coeur
#: n'a aucun mot-cle pour un jeu de frames extraites seul », ce qui etait vrai
#: et ce qu'Egan a rapporte du terrain le 2026-09-06 (« on ne peut pas retirer
#: d'un projet un jeu de frames extraites sans emporter autre chose »). Le
#: coeur porte desormais `frames_extraites=`, cinquieme cible fine, et
#: `EPIC11-ARB-111` (« un master, un scan ou un jeu de frames SEUL ») est
#: ferme. La table reste -- vide -- parce qu'elle est le mecanisme, pas la
#: liste : une nature future sans cible fine s'y inscrit, et le chemin
#: `EcranPasEncore` qui la sert est mesure par ailleurs.
#:
#: **Le MASTER n'y figure plus** (Egan, 2026-09-05 : « il faut resoudre le
#: probleme du "profile". Il est contenu dans le nom du master »). La cible
#: exige `profile=`, qu'`ObjetInventorie` ne porte pas -- mais le nom du
#: fichier le porte, et :func:`profil_du_master` le relit **exactement** :
#: prefixe retire par egalite avec un `lot_id` connu, profil reconnu dans le
#: registre ferme de `codec_profiles`. Un nom qui ne nomme aucun profil connu
#: retombe sur la sortie ci-dessous plutot que sur une valeur plausible.
#:
#: **Ce n'est pas un blocage sec** (`EPIC11-ARB-89`) : `Suppr` sur une nature
#: sans cible mene a `EcranPasEncore`, qui NOMME ce qui manque et laisse
#: l'interaction possible -- « ce qui distingue « pas encore construit » de
#: « casse » ». Supprimer le lot entier a la place serait une destruction PLUS
#: large que celle demandee, ce qui est pire qu'un refus.
NATURES_SANS_CIBLE_FINE: dict[str, str] = {}


#: Le relecteur de nom de master est **lu du coeur**, jamais redige ici.
#:
#: Il a d'abord ete ecrit dans ce module, et la frontiere
#: `test_AUCUN_module_de_la_TUI_ne_redige_une_regle_de_RANG` a dit que c'etait
#: faux. Elle avait raison sur le fond et pas seulement sur la lettre : ce nom
#: se decompose avec `MASTER_FILENAME_MARKER` et le registre ferme des profils,
#: c'est-a-dire avec les deux choses que `build_master_filename` emploie pour
#: le COMPOSER. Un decomposeur loge loin de sa fabrique est la seconde
#: convention que `io.naming` existe pour empecher.
ProfilDuMaster = naming.ProfilDuMaster
profil_du_master = naming.profil_du_master


def identifiant_du_noeud(noeud: NoeudAffiche) -> str | None:
    """Le nom que le COEUR connait, jamais celui que l'ecran AFFICHE.

    **Les deux ne coincident PAS, et l'ecart a ete paye.** `_nom_affiche`
    suffixe ` · non declare` a tout objet que le manifeste ignore : c'est une
    mention d'affichage, dessinee par `E6-1`, `E6-1c` et `E6-1d`. Lue comme un
    identifiant, elle produit `{"lot_id": "plan-04_25_v2 · non declare"}` --
    un identifiant qui n'existe nulle part. Le coeur refuse, donc rien n'est
    detruit ; mais le seul chemin de suppression des orphelins se ferme, et il
    se ferme en montrant a l'operateur un nom qui n'est pas le sien.

    **Le regime exact** : `Suppr` sur un objet non declare -- c'est-a-dire sur
    precisement les objets que cet ecran existe pour rendre visibles. Trouve
    par la couche 1 de la revue de la story (finding `F2`), et par elle seule :
    aucune assertion du banc ne portait sur un noeud non declare.

    L'objet de coeur porte le nom brut ; il suffit de le LIRE. Rendre ``None``
    plutot que retomber sur `noeud.nom` est delibere : un noeud sans objet de
    coeur est un groupe, et un groupe ne se supprime pas. Un repli sur le nom
    affiche remettrait la mention dans le tuyau par la petite porte.
    """
    cible = getattr(noeud, "cible", None)
    return None if cible is None else cible.nom


def cible_du_noeud(noeud: NoeudAffiche, lot_id: str | None = None
                   ) -> dict[str, object] | None:
    """Les mots-cles de `remove_project_element` qui designent ce noeud.

    Rend ``None`` quand aucun point d'entree du coeur ne vise cette nature --
    l'appelant monte alors `EcranPasEncore` plutot que d'elargir la cible.

    ``lot_id`` est le CONTEXTE des cinq cibles fines (`EPIC11-ARB-224`) :
    l'identifiant du lot sous lequel l'objet vit. Il est **donne** par
    l'appelant, qui connait l'arbre, plutot que devine ici a partir du nom --
    `build_lot_id` condense et tronque, la decomposition est a sens unique.

    Le **rang** ne se devine pas non plus : il est lu de `ObjetInventorie.rang`,
    que le coeur remplit. Le rang d'origine ne se transmet **pas** (`version=`
    absent le designe, `EPIC11-ARB-88`), et le transmettre quand meme serait
    accepte par le coeur mais dirait deux fois la meme chose.
    """
    if noeud.groupe or noeud.cible is None:
        return None
    # Le nom du COEUR, jamais celui de la ligne : voir `identifiant_du_noeud`.
    nom = identifiant_du_noeud(noeud)
    nature = noeud.nature
    if nature == NATURE_RUSH:
        return {"rush_id": nom}
    if nature == NATURE_LOT:
        return {"lot_id": nom}
    if nature in NATURES_SANS_CIBLE_FINE or lot_id is None:
        return None
    fine: dict[str, object] = {"lot_id": lot_id}
    if nature == NATURE_PLANCHE:
        fine["planche"] = True
    elif nature in (NATURE_LOT_SCANNE, NATURE_FRAMES_SCANNEES):
        # `lot_scanne=` est l'ancienne cible `frames_scannees=`, RENOMMEE et
        # non doublee (`EPIC11-ARB-214`) : les deux natures du coeur designent
        # le meme objet a deux niveaux de l'arbre.
        fine["lot_scanne"] = True
    elif nature == NATURE_FRAMES_EXTRAITES:
        # **Un DRAPEAU nu, et aucun `version=` ne le suit** -- le coeur le
        # refuserait, et il a raison : le dossier de frames extraites porte le
        # rang du LOT, pas le sien. Le `version=` general de la fin de fonction
        # est donc court-circuite par un retour immediat plutot que filtre
        # apres coup : un rang lu de l'arbre et transmis ici designerait le
        # dossier d'un AUTRE lot.
        fine["frames_extraites"] = True
        return fine
    elif nature == NATURE_MASTER:
        lu = profil_du_master(nom, lot_id)
        if lu is None:
            # Le nom ne nomme aucun profil du registre : un master renomme a
            # la main, ou produit par une version anterieure. On ne devine
            # pas -- l'appelant montre ce qui manque.
            return None
        fine["master"] = True
        fine["profile"] = lu.profil
        if lu.resolution is not None:
            fine["resolution"] = lu.resolution
    elif nature == NATURE_SCAN:
        # `scan=` prend un slug de FAMILLE, « le nom du dossier prive de son
        # fragment `_vN` » -- c'est litteralement ce que `tige_et_rang` lit,
        # avec les fonctions du depot qui ecrivent la regle des rangs.
        fine["scan"] = tige_et_rang(nom)[0]
    else:
        return None
    #: Un objet sans rang n'a pas de rang -- `None` le dit. Une sentinelle
    #: chiffree tiree de la borne des rangs serait une regle de rang ecrite
    #: dans un ecran, et le rang d'ORIGINE ne se transmet jamais au coeur :
    #: `version=1` lui ferait viser un fragment que rien n'ecrit.
    rang = getattr(noeud.cible, "rang", None)
    if naming.est_un_rang_de_version(rang):
        fine["version"] = rang
    return fine


#: Ce que l'ecran de refus dit quand AUCUN membre d'un groupe n'est visable.
CODE_GROUPE_SANS_CIBLE = "GROUPE_SANS_CIBLE_VISABLE"
PHRASE_GROUPE_SANS_CIBLE = (
    "Aucun des {cardinal} éléments de {objet} ne peut être visé : {raisons}")


def cibles_du_groupe(noeud: NoeudAffiche, lot_id: str | None
                     ) -> tuple[tuple[tuple[str, dict[str, object]], ...],
                                tuple[str, ...]]:
    """Les N cibles d'un GROUPE, et les membres que rien ne sait viser.

    `EPIC11-ARB-264` : supprimer un groupe est **N appels**, la boucle
    au-dessus du coeur. Cette fonction ne fait que la traduction -- un membre,
    une cible --, et elle appelle :func:`cible_du_noeud` plutot que de recopier
    son jugement : les cinq natures fines s'y designent chacune a sa facon, et
    une seconde table serait une seconde verite (`EPIC5-ARB-78`).

    **L'ORDRE est celui de l'arbre, jamais trie** : il porte celui du manifeste
    (`EPIC11-ARB-109`), et c'est aussi l'ordre de DESTRUCTION que l'apercu
    montre.

    **Les MEMBRES DIRECTS, et eux seuls.** Un groupe de scans porte des scans,
    qui portent eux-memes leurs lots scannes ; descendre jusqu'aux petits-fils
    viserait deux fois les memes fichiers -- le coeur supprime deja le
    sous-arbre d'un scan. La profondeur du groupe est donc UN, comme l'arbre la
    dessine.

    Rend `(cibles, non_visables)`. Un membre que `cible_du_noeud` ne sait pas
    designer n'est pas tu : son nom part dans la seconde moitie, et l'appelant
    le DIT (`EPIC11-ARB-258`). Le taire ferait supprimer « le groupe » en en
    laissant une partie, sans un mot.
    """
    cibles: list[tuple[str, dict[str, object]]] = []
    non_visables: list[str] = []
    for membre in noeud.enfants:
        cible = cible_du_noeud(membre, lot_id)
        if cible is None:
            non_visables.append(identifiant_du_noeud(membre) or membre.nom)
            continue
        cibles.append((membre.nom, cible))
    return tuple(cibles), tuple(non_visables)


def ecartes_du_groupe(noeud: NoeudAffiche, lot_id: str | None
                      ) -> tuple[tuple[str, str], ...]:
    """Les membres que le produit ne sait pas viser, chacun avec son POURQUOI.

    Le pendant nomme de la seconde moitie de :func:`cibles_du_groupe`, qui rend
    des noms nus. Un nom seul ne suffit pas a l'ecran : « ce membre reste »
    laisse l'operateur sans rien a faire, la ou « son nom ne nomme aucun profil
    du registre » lui dit quoi corriger. C'est la meme exigence
    qu'`EPIC11-ARB-258` pose sur les refus du coeur, appliquee aux refus du
    PRODUIT.

    **Le jugement n'est pas redit ici, il est APPELE** : la visabilite se lit de
    :func:`cible_du_noeud` et le motif de :func:`motif_sans_cible` -- les deux
    memes autorites que le chemin d'un OBJET seul consulte, si bien qu'un
    membre de groupe et le meme objet vise seul rendent la meme phrase. Une
    table de motifs propre aux groupes serait la seconde verite qu'`EPIC5-ARB-78`
    interdit, et elle perimerait a la premiere nature ajoutee.

    **C'est un second PARCOURS, pas un second jugement**, et l'ecart possible
    entre les deux parcours se mesure plutot qu'il ne se promet : une frontiere
    verifie que les noms rendus ici sont exactement ceux que
    :func:`cibles_du_groupe` range en non-visables, sur un groupe mixte.

    Un membre dont :func:`motif_sans_cible` rend ``None`` -- une nature de
    :data:`NATURES_SANS_CIBLE_FINE`, c'est-a-dire un manque du COEUR et non un
    fait sur cet objet -- porte la phrase de ce manque, celle-la meme que
    `EcranPasEncore` affiche sur le chemin d'un objet seul. **La table est vide
    au 2026-09-07**, donc aucune nature livree ne passe par la ; elle est ecrite
    pour que la prochaine trouve une phrase plutot qu'une chaine vide.
    """
    ecartes: list[tuple[str, str]] = []
    for membre in noeud.enfants:
        if cible_du_noeud(membre, lot_id) is not None:
            continue
        nom = identifiant_du_noeud(membre) or membre.nom
        motif = motif_sans_cible(membre, lot_id)
        if motif is None:
            nature = NATURES_SANS_CIBLE_FINE.get(membre.nature, membre.nature)
            ecartes.append((nom, CE_QUI_MANQUE_A_LA_CIBLE_FINE.format(
                nature=nature)))
            continue
        ecartes.append((nom, motif[1]))
    return tuple(ecartes)


def libelle_du_groupe(noeud: NoeudAffiche, cardinal: int) -> str:
    """`les 2 éléments de « planches — 2 planches »`.

    Le nom du groupe est celui que la LIGNE porte, mention comprise : c'est ce
    que l'operateur a sous les yeux quand il frappe `Suppr`, et le recomposer
    d'une table de natures ferait lire au cartouche un mot different de celui
    de l'arbre -- le finding `F2` de la revue 11.14, deux mots pour un objet.
    """
    mot = "élément" if cardinal == 1 else "éléments"
    return f"les {cardinal} {mot} de « {noeud.nom} »"


def libelle_de_la_cible(noeud: NoeudAffiche) -> str:
    """`tout le lot plan-04_12p5`, `le rush hiver`, `le master ...`.

    Le mot de nature est **lu** de `project_inventory.libelles_de_nature` par
    l'arbre, jamais reecrit ici : deux tables de libelles divergeraient au
    premier renommage, et c'est exactement le defaut que `GROUPES_DECLARES`
    documente deja de l'autre cote.
    """
    if noeud.nature == NATURE_LOT:
        return f"tout le lot {noeud.nom}"
    if noeud.nature == NATURE_RUSH:
        return f"tout le rush {noeud.nom}"
    return noeud.nom


# ---------------------------------------------------------------------------
# Ce que le rapport ne porte pas : le poids, mesure sur le disque
# ---------------------------------------------------------------------------


def poids_des_fichiers(projet: Path, chemins: Sequence[str]) -> int:
    """La somme des octets des chemins nommes par le rapport, **mesuree**.

    Un `lstat` par chemin, garde : un fichier deja parti, un lien casse ou un
    droit refuse rend zero pour ce chemin plutot que de faire echouer le
    panneau entier. Un point de jugement qui leve au lieu de s'afficher est un
    blocage sec, et `EPIC11-ARB-89` n'en veut nulle part.

    **`lstat` et non `stat`** : un lien symbolique pese son lien, pas sa cible.
    Compter la cible ferait annoncer un poids libere que la suppression du lien
    ne rendrait jamais.
    """
    total = 0
    for relatif in chemins:
        try:
            total += os.lstat(Path(projet) / relatif).st_size
        except OSError:
            continue
    return total


@dataclass(frozen=True)
class GroupeEmporte:
    """Une ligne de la liste « Emportés avec le lot » d'`E6-2`.

    Un DOSSIER quand plusieurs fichiers partagent leur emplacement, un FICHIER
    quand il est seul -- c'est ce que la maquette dessine
    (`extract-frames/plan-04_12p5/  62 fichiers` face a
    `plan-04_12p5_mmu_prores_hq.mov  1 fichier`), et c'est aussi la seule mise
    en page qui tienne : nommer 62 frames une par une deborderait la zone de
    cinquante lignes.
    """

    libelle: str
    fichiers: int
    poids: int
    absent: bool = False

    def rendu(self, ascii_seul: bool = False) -> str:
        """`  extract-frames/plan-04_12p5/    62 fichiers · 770 Mo`.

        Une annexe **attendue-absente** ne porte ni cardinal ni poids : elle
        n'occupe rien sur le disque. Elle porte le glyphe d'absence, comme
        partout ailleurs -- `DESIGN.md` section 5 veut les deux canaux, jamais
        la couleur seule.
        """
        table = jetons.glyphes(ascii_seul)
        if self.absent:
            return _replie(f"{table['absent']} {self.libelle} — "
                           f"{ETAT_ANNEXE_ABSENTE}", ascii_seul)
        cardinal = f"{grouper_les_milliers(self.fichiers)} " + (
            UNITE_FICHIER if self.fichiers == 1 else UNITE_FICHIERS)
        # **Le repli porte sur la ligne ENTIERE**, glyphe de poids compris :
        # `poids_lisible` rend le glyphe neutre `·` sur un poids nul, et
        # `SEPARATEUR` porte le meme caractere. Replier le seul glyphe d'etat
        # -- ce que faisait la premiere redaction -- laissait donc deux
        # caracteres non-ASCII par ligne, trouves par la garde de repli.
        return _replie(f"{self.libelle} — {cardinal}{SEPARATEUR}"
                       f"{poids_lisible(self.poids)}", ascii_seul)


#: Ce qu'`E6-2` ecrit a droite d'une annexe designee par la filiation mais
#: absente du disque (« déclarée, absente »). **Le genre n'est pas accorde** :
#: le rapport nomme des chemins, pas des natures, et deviner le genre depuis
#: une extension serait une regle de plus a tenir pour rien.
ETAT_ANNEXE_ABSENTE = "déclaré au manifeste, absent du disque"


def groupes_emportes(projet: Path, rapport: RapportSuppression
                     ) -> tuple[GroupeEmporte, ...]:
    """Les lignes « Emportés » : les fichiers du rapport, groupes par dossier.

    **L'ordre du rapport est preserve** : `fichiers_a_supprimer` les nomme
    « dans l'ordre ou l'appelant les a construits », et cet ordre porte de
    l'information (les frames d'abord, le master ensuite, le scan enfin, comme
    `E6-2` le dessine). Un tri alphabetique le detruirait.

    Les annexes **attendues-absentes** viennent en queue, chacune sur sa ligne
    et sans chiffre : elles n'occupent rien.
    """
    par_dossier: dict[str, list[str]] = {}
    for relatif in rapport.fichiers_a_supprimer:
        par_dossier.setdefault(str(Path(relatif).parent), []).append(relatif)
    groupes: list[GroupeEmporte] = []
    for dossier, membres in par_dossier.items():
        poids = poids_des_fichiers(projet, membres)
        if len(membres) == 1:
            groupes.append(GroupeEmporte(Path(membres[0]).name, 1, poids))
        else:
            libelle = "" if dossier in (".", "") else f"{dossier}/"
            groupes.append(GroupeEmporte(libelle or "/", len(membres), poids))
    for relatif in rapport.fichiers_attendus_absents:
        groupes.append(GroupeEmporte(Path(relatif).name, 0, 0, absent=True))
    return tuple(groupes)


# ---------------------------------------------------------------------------
# Le plan : ce que le coeur a rendu en dry-run, plus ce qui s'est mesure
# ---------------------------------------------------------------------------


@dataclass
class PlanDeSuppression:
    """Tout ce que l'ecran montre, **produit une fois** et jamais recalcule.

    Il porte le rapport du coeur tel quel, la cible qui l'a produit, et les
    deux seules choses que le rapport ne dit pas : le poids mesure et la mise
    en page des emportes.
    """

    projet: Path
    cible: dict[str, object]
    libelle: str
    rapport: RapportSuppression
    poids: int = 0
    groupes: tuple[GroupeEmporte, ...] = ()
    #: Vrai quand le coeur a REFUSE la cible sans `confirmation_dernier_lot` --
    #: c'est-a-dire quand c'est le dernier lot ou le dernier rush du projet.
    #: Il n'est jamais suppose : il est le constat d'un `LastLotRefusedError`.
    dernier_lot: bool = False
    #: Les N cibles d'un GROUPE (`EPIC11-ARB-264`), `(libelle, mots-cles)`.
    #: Vide sur un plan ordinaire, et c'est ce qui distingue les deux.
    #:
    #: **`cible` reste VIDE sur un plan de groupe**, et ce n'est pas un oubli :
    #: `mots_cles_de_l_issue` l'etale dans l'appel au coeur, et un groupe n'a
    #: aucun jeu de mots-cles qui le designe -- `remove_project_element` vise
    #: EXACTEMENT un objet. Y ranger une cible plausible ferait supprimer
    #: l'un des N en croyant les supprimer tous.
    cibles_du_groupe: tuple[tuple[str, dict[str, object]], ...] = ()
    #: L'apercu ligne par ligne d'un groupe, garde tel que le coeur l'a rendu.
    #:
    #: **Le rapport AGREGE ne le remplace pas** : il dit un total, la ou
    #: `EPIC11-ARB-264` veut « ce qui est parti, ce qui a refuse, et pourquoi
    #: pour chacun ». L'agregat sert les ecrans deja dessines ; le detail reste
    #: ici, entier, pour l'ecran qui le montrera.
    apercu_du_groupe: RapportDeGroupe | None = None
    #: Le meme detail APRES l'ecriture, pose par :func:`executer_la_suppression`.
    #:
    #: **Le symetrique exact d'`apercu_du_groupe`, et il manquait.** L'agregat
    #: rendu au compte rendu est un :class:`RapportSuppression` : il porte des
    #: CHEMINS, et un membre refuse par le coeur n'en rend aucun. Le POURQUOI de
    #: chaque refus -- ce qu'`EPIC11-ARB-264` reclame nommement -- ne vit donc
    #: que sur les lignes du rapport de groupe, et sans ce champ il etait
    #: produit puis jete entre l'appel au coeur et l'ecran (findings `C3-2` et
    #: `C3-2b` : un groupe a moitie ou entierement refuse s'annoncait REUSSI).
    #:
    #: Il vaut ``None`` tant que rien n'a ete ecrit ; « Reessayer » le remplace
    #: par le rapport du dernier passage, qui est bien ce que l'ecran doit
    #: montrer.
    execution_du_groupe: RapportDeGroupe | None = None
    #: Les membres du groupe que le PRODUIT ne sait pas viser, `(nom, motif)`.
    #:
    #: Rendus par :func:`ecartes_du_groupe`. Ils ne figurent dans AUCUN des deux
    #: rapports de groupe -- le coeur ne les a jamais vus, faute de cible a lui
    #: passer --, et c'est precisement ce qui les rendait invisibles : le
    #: cartouche disait « les 2 elements de "masters — 3 masters" » et le
    #: troisieme restait sur le disque sans qu'un mot le nomme (`C1-1`, `C2-1`,
    #: `C3-3`, trouve par les trois couches de revue independamment).
    membres_ecartes: tuple[tuple[str, str], ...] = ()

    @property
    def est_un_groupe(self) -> bool:
        """Ce plan porte-t-il N cibles au lieu d'une ?"""
        return bool(self.cibles_du_groupe)

    @property
    def fichiers(self) -> int:
        return len(self.rapport.fichiers_a_supprimer)

    @property
    def scans_nommes(self) -> tuple[str, ...]:
        """Les dossiers de scan que le coeur NOMME sans les inclure.

        « Le dossier de scan est NOMME dans le rapport meme sans ce
        consentement : l'operateur doit voir qu'il existe pour decider, sinon
        le consentement n'est pas eclaire. »
        """
        if self.rapport.scan_inclus:
            return ()
        return tuple(self.rapport.dossiers_de_scan)


def preparer_la_suppression(projet, cible: dict[str, object], libelle: str,
                            *, avec_scans: bool = False,
                            retirer_du_projet=remove_project_element) -> PlanDeSuppression:
    """Le `dry_run` du coeur, plus les deux mesures que son rapport ne porte pas.

    **Le refus du dernier lot est CONSTATE, pas devine** : le coeur leve
    `LastLotRefusedError` sans le consentement supplementaire ; l'appel est
    alors refait **en dry-run** avec `confirmation_dernier_lot=True`, ce qui
    rend le rapport sans rien ecrire, et le plan retient que la confirmation
    supplementaire sera exigee. Compter les lots ici pour le predire serait une
    seconde redaction de la garde du coeur, et elle divergerait -- c'est
    exactement l'ecart 2 du lot D, mesure : la garde compte les lots du PROJET
    quand `E6-2b` parle du dernier lot d'un RUSH.

    ``retirer_du_projet`` est injectable pour que le banc mesure l'appel sans
    coeur ; le defaut est le point d'entree reel.

    **Le mot-cle ne s'appelle pas `remove`**, et ce n'est pas une preference :
    la frontiere negative d'`AC 4.1` mesure a l'AST qu'aucun `remove(...)`
    n'est appele dans ce module. Un parametre nomme `remove` produirait
    exactement cet appel -- et masquerait un `os.remove` reintroduit un jour au
    meme nom. La frontiere l'a trouve a la premiere execution ; c'est ce
    qu'elle existe pour trouver.
    """
    projet = Path(projet)
    commun = dict(cible, dry_run=True, avec_scans=avec_scans)
    dernier_lot = False
    try:
        rapport = retirer_du_projet(projet, **commun)
    except LastLotRefusedError:
        dernier_lot = True
        rapport = retirer_du_projet(projet, **commun,
                                    confirmation_dernier_lot=True)
    return PlanDeSuppression(
        projet=projet, cible=dict(cible), libelle=libelle, rapport=rapport,
        poids=poids_des_fichiers(projet, rapport.fichiers_a_supprimer),
        groupes=groupes_emportes(projet, rapport),
        dernier_lot=dernier_lot)


def rapport_agrege_du_groupe(
    libelle: str, groupe: RapportDeGroupe,
    apercu: RapportDeGroupe | None = None,
) -> RapportSuppression:
    """Ce que N suppressions font voir aux ecrans **deja dessines**.

    `EPIC11-ARB-144` interdit de coder un ecran qu'aucune maquette ne dessine,
    et aucune n'en dessine un a N cartouches. Le cartouche d'`E6-2` --
    « Élément / Fichiers / Poids libéré / Emportés » -- accueille en revanche un
    groupe sans qu'un trait change : c'est un total et une liste de dossiers,
    ce qu'un groupe produit exactement. Cette fonction est le SEUL lieu de la
    traduction, ecrite une fois pour l'apercu et pour l'execution : deux
    redactions divergeraient, et l'une des deux annoncerait a l'operateur autre
    chose que ce qu'il a confirme.

    **Ce que l'agregat dit, et comment** :

    * `fichiers_a_supprimer` concatene les lignes ACCEPTEES, dans leur ordre ;
    * `fichiers_non_supprimes` porte deux choses de meme nature pour
      l'operateur -- ce qui a resiste sur une ligne acceptee, et ce qu'une
      ligne REFUSEE laisse derriere elle. Les chemins d'une ligne refusee sont
      relus de l'APERCU, **par rang** : a l'execution, un refus ne rend aucun
      chemin, et taire ce qui reste ferait annoncer une reussite sur un groupe
      a moitie parti ;
    * `fichiers_attendus_absents` est l'union, dedupliquee et dans l'ordre ;
    * `dossiers_de_scan` est VIDE par ecriture, jamais par collecte -- voir le
      commentaire du champ, et le finding `C2-7`.

    **Ce que l'agregat ne peut pas porter, et ou ca se lit maintenant.** Un
    :class:`RapportSuppression` porte des CHEMINS ; une ligne refusee n'en rend
    aucun, donc le POURQUOI d'un refus n'a ici aucune place ou aller. Il n'est
    plus jete pour autant : le rapport de groupe est garde sur le plan
    (`apercu_du_groupe` avant l'ecriture, `execution_du_groupe` apres), et
    :func:`ecartes_du_plan` l'y relit pour les deux ecrans. C'est ce qui
    manquait quand un groupe a moitie refuse s'annoncait REUSSI (`C3-2`).

    **Aucun RANG n'est porte** (`rangs_liberables` vide, `tirage_en_queue`
    faux, `rang_independant` faux) et ce n'est pas une omission : un groupe
    n'est pas un objet versionne. En rendre un ferait apparaitre l'issue
    « Supprimer et libérer les rangs » sur un ensemble, c'est-a-dire une
    liberation en bloc que personne n'a demandee -- l'inverse du point 3
    d'`EPIC11-ARB-92`.
    """
    promesses = apercu.lignes if apercu is not None else ()
    partis: list[str] = []
    restes: list[str] = []
    absents: list[str] = []
    for rang, ligne in enumerate(groupe.lignes):
        if ligne.rapport is None:
            # Ligne REFUSEE : elle n'a rien detruit, donc tout ce que l'apercu
            # lui promettait est encore la.
            #
            # **Apparie par RANG, et non plus par libelle** (finding `C2-6`).
            # Les deux rapports naissent des MEMES cibles dans le MEME ordre :
            # `remove_project_group` emet une ligne par cible, dans l'ordre
            # recu, et ne trie ni ne saute jamais (son propre docstring :
            # « L'ORDRE est celui que l'appelant donne, et il n'est pas
            # trie »). Le rang est donc exact et gratuit, la ou le libelle
            # supposait une unicite que **rien ne garantit** : deux membres
            # homonymes faisaient relire au second les chemins du premier --
            # mesure, `restes` portait `outputs/SECOND.pdf` quand le survivant
            # etait `PREMIER.pdf`.
            #
            # **Ce n'est pas la fermeture d'un defaut atteignable, et il faut
            # le dire ainsi** : aucune des deux couches de revue qui l'ont vu
            # n'a su produire un manifeste sain donnant deux membres
            # homonymes. C'est une dependance a une unicite non garantie qui
            # disparait, pas un regime de terrain qui se ferme.
            promis = promesses[rang] if rang < len(promesses) else None
            if promis is not None and promis.rapport is not None:
                restes.extend(promis.rapport.fichiers_a_supprimer)
            continue
        partis.extend(ligne.rapport.fichiers_a_supprimer)
        restes.extend(ligne.rapport.fichiers_non_supprimes)
        absents.extend(ligne.rapport.fichiers_attendus_absents)
    if groupe.dry_run:
        # En apercu, rien n'a resiste et rien n'a ete refuse au sens du disque :
        # ce qu'une ligne refusee promettait n'existe pas, elle n'a pas
        # d'apercu. La liste des restes n'a donc pas de sens ici.
        restes = []
    return RapportSuppression(
        cible=libelle,
        fichiers_a_supprimer=tuple(partis),
        dry_run=groupe.dry_run,
        supprime=not groupe.dry_run and not restes and not groupe.refusees,
        fichiers_non_supprimes=tuple(dict.fromkeys(restes)),
        fichiers_attendus_absents=tuple(dict.fromkeys(absents)),
        # **VIDE, et c'est desormais ecrit plutot que collecte** (`C2-7`,
        # premiere moitie). La ligne qui precedait -- `scans.extend(
        # ligne.rapport.dossiers_de_scan)` -- ne pouvait rien collecter, et le
        # mutant `M32` qui la supprimait survivait a tout le banc. Mesure du
        # 2026-09-07, les six cibles du coeur en `dry_run` :
        #
        #     planche / master / frames_extraites / lot_scanne / scan -> ()
        #     lot entier (`lot_id` seul)                 -> ('scans/...',)
        #
        # Un groupe ne porte que des cibles FINES (`cibles_du_groupe`), donc
        # jamais la seule qui renseigne le champ. Le seul chemin par lequel une
        # cible de LOT entrerait dans un groupe est un lot ORPHELIN pose en
        # queue d'arbre -- et un orphelin n'est par definition pas declare, si
        # bien que le coeur le refuse (« Lot inconnu du manifeste », mesure) :
        # la ligne n'a alors pas de rapport, et l'`extend` etait saute de toute
        # facon.
        #
        # **Et si elle avait pu tirer, elle aurait nui.** `scan_inclus` est
        # faux ici par construction, donc des dossiers collectes seraient
        # devenus `plan.scans_nommes`, donc l'issue « Supprimer avec les
        # scans » -- que :func:`executer_la_suppression` IGNORE sur un groupe,
        # ou seul `issue.ecrit` est lu. Une issue sans effet est exactement la
        # promesse cassee qu'`issues_de_la_suppression` interdit.
        dossiers_de_scan=(),
        scan_inclus=False,
        tirage_en_queue=False,
        rangs_liberables=(),
        rang_libere=False,
        rang_independant=False,
    )


def preparer_la_suppression_du_groupe(
    projet, cibles: Sequence[tuple[str, dict[str, object]]], libelle: str,
    *, retirer_le_groupe=remove_project_group,
    ecartes: Sequence[tuple[str, str]] = (),
) -> PlanDeSuppression:
    """L'apercu d'un GROUPE : un `dry_run` par cible, un cartouche pour tous.

    Pendant exact de :func:`preparer_la_suppression`, et il ne partage pas son
    corps pour une raison de nature : le refus du dernier lot ne s'y pose pas.
    Les cibles d'un groupe sont des cibles FINES -- planches, masters, scans,
    lots scannes, frames extraites --, et le coeur refuse deja
    `confirmation_dernier_lot` sur chacune d'elles (« il n'a aucun sens avec
    --<cible>, qui ne retire pas le lot »). Recopier ici le `except
    LastLotRefusedError` ajouterait une branche que rien ne peut atteindre, et
    une branche morte est une garde qu'on croit avoir.

    ``ecartes`` porte les membres que le PRODUIT n'a pas su viser, `(nom,
    motif)`, leves par :func:`ecartes_du_groupe`. Ils ne descendent pas dans
    l'appel au coeur -- il n'y a aucune cible a lui passer pour eux --, mais ils
    doivent atteindre l'ecran : sans eux le cartouche annonce « les 2 elements »
    d'un groupe qui en montre trois, et le troisieme reste sur le disque sans
    qu'un mot le nomme (`C1-1` / `C2-1` / `C3-3`).

    **Le libelle continue de compter les membres VISES, et c'est voulu.** Il
    est compose par l'appelant avant cet appel, donc avant que le coeur ait dit
    lesquels il refuse ; le recalculer apres coup ferait lire au cartouche un
    cardinal que le titre de la ligne d'arbre ne porte pas. Ce qu'un membre
    refuse ajoute n'est pas un chiffre en moins : c'est une ligne en plus, dans
    le bloc des ecartes, avec son nom et sa raison.
    """
    projet = Path(projet)
    cibles = tuple((libelle_ligne, dict(cible))
                   for libelle_ligne, cible in cibles)
    apercu = retirer_le_groupe(projet, cibles, dry_run=True)
    rapport = rapport_agrege_du_groupe(libelle, apercu)
    return PlanDeSuppression(
        projet=projet, cible={}, libelle=libelle, rapport=rapport,
        poids=poids_des_fichiers(projet, rapport.fichiers_a_supprimer),
        groupes=groupes_emportes(projet, rapport),
        cibles_du_groupe=cibles, apercu_du_groupe=apercu,
        membres_ecartes=tuple(ecartes))


# ---------------------------------------------------------------------------
# `E6-2` / `E6-2b` : le cartouche et les issues
# ---------------------------------------------------------------------------


def _cardinal_de_fichiers(combien: int) -> str:
    unite = UNITE_FICHIER if combien == 1 else UNITE_FICHIERS
    return f"{grouper_les_milliers(combien)} {unite}"


def panneau_de_la_confirmation(plan: PlanDeSuppression,
                               ascii_seul: bool = False) -> Panneau:
    """Le cartouche d'`E6-2`, et d'`E6-2b` quand c'est le dernier lot.

    **Toute ligne chiffree porte son unite** ; `LigneChiffree` refuse le
    contraire a la construction. `Poids libéré` porte son unite dans sa valeur
    (`1,5 Go`), qui est un TEXTE -- c'est le cas que `LigneChiffree` prevoit
    explicitement pour les valeurs deja formatees.
    """
    lignes = [
        LigneChiffree(LIBELLE_ELEMENT, plan.libelle),
        LigneChiffree(LIBELLE_FICHIERS, plan.fichiers,
                      unite=UNITE_FICHIER if plan.fichiers == 1
                      else UNITE_FICHIERS),
        LigneChiffree(LIBELLE_POIDS, poids_lisible(plan.poids)),
    ]
    if plan.groupes:
        combien = len(plan.groupes)
        # **Le libelle depend du PLAN, pas du contenu de la ligne** (`C2-7`) :
        # un groupe ne retire aucun lot, donc « Emportés avec le lot » y
        # nommait un emport qui n'a pas lieu. Voir
        # :data:`LIBELLE_EMPORTES_DU_GROUPE`.
        lignes.append(LigneChiffree(
            LIBELLE_EMPORTES_DU_GROUPE if plan.est_un_groupe
            else LIBELLE_EMPORTES, combien,
            unite=UNITE_GROUPE if combien == 1 else UNITE_GROUPES))
    if plan.rapport.rangs_liberables:
        lignes.append(LigneChiffree(
            LIBELLE_RANGS,
            SEPARATEUR.join(MOTIF_DU_RANG.format(rang=rang)
                            for rang in plan.rapport.rangs_liberables)))
    panneau = Panneau(TITRE_A_SUPPRIMER.format(cible=plan.libelle), lignes)
    return panneau


def lignes_des_emportes(plan: PlanDeSuppression,
                        ascii_seul: bool = False) -> list[str]:
    """Les lignes indentees sous « Emportés », plus la phrase du dernier lot.

    Elles sont HORS `Panneau` parce qu'elles ne sont pas des lignes chiffrees :
    `LigneChiffree` cale un chiffre a droite de la largeur utile, ce qui
    ecraserait le creux de la maquette. Elles sont ajoutees par
    :meth:`EcranSuppressionConfirmation.lignes_du_panneau`, apres le cartouche.
    """
    lignes = [f"  {groupe.rendu(ascii_seul)}" for groupe in plan.groupes]
    if plan.dernier_lot:
        # **Repliee comme les autres** (finding `C2-4` de la couche 2). Elle
        # etait la seule ligne du module a ne pas passer par `_replie`, et
        # l'effet visible etait NUL -- `bloc_peint` replie au dessin via
        # `jetons.ajuster`. Ce qui etait casse, c'est la FRONTIERE : les deux
        # gardes de repli assertent sur cette fonction, avant dessin, et
        # passaient uniquement parce qu'aucune ne faisait varier `dernier_lot`.
        # Regle des fabriques, point 1, sur un booleen.
        lignes.extend(["", _replie(PHRASE_DERNIER_LOT, ascii_seul)])
    return lignes


def issues_de_la_suppression(plan: PlanDeSuppression) -> ChoixExclusif:
    """Les issues d'`E6-2`. `EPIC11-ARB-89`, et il est tenu par CONSTRUCTION.

    Jamais une seule issue, jamais un blocage sec, et **toujours** une sortie
    qui n'ecrit pas : `ChoixExclusif` leve a la construction si toutes les
    issues ecrivent, et `Annuler` ferme la liste. Le curseur s'y pose tout
    seul -- « le curseur part sur une issue qui n'ecrit pas » (AC 3.4 est donc
    tenu par le patron, pas par une ligne ajoutee ici).

    Les deux consentements supplementaires du coeur donnent chacun leur issue,
    et **seulement quand ils ont un objet** : liberer un rang qu'aucun rapport
    ne declare liberable serait une issue sans effet, et une issue sans effet
    est une promesse cassee.
    """
    issues = [Issue(CLE_SUPPRIMER,
                    MOTIF_DE_L_ISSUE.format(
                        libelle=LIBELLE_SUPPRIMER,
                        mention=MENTION_DEFINITIF.format(
                            cardinal=_cardinal_de_fichiers(plan.fichiers))),
                    ecrit=True)]
    if plan.rapport.rangs_liberables:
        rangs = SEPARATEUR.join(MOTIF_DU_RANG.format(rang=rang)
                                for rang in plan.rapport.rangs_liberables)
        issues.append(Issue(
            CLE_SUPPRIMER_ET_LIBERER,
            MOTIF_DE_L_ISSUE.format(libelle=LIBELLE_SUPPRIMER_ET_LIBERER,
                                    mention=MENTION_DES_RANGS.format(
                                        rangs=rangs)),
            ecrit=True))
    if plan.scans_nommes:
        issues.append(Issue(
            CLE_SUPPRIMER_AVEC_SCANS,
            MOTIF_DE_L_ISSUE.format(
                libelle=LIBELLE_SUPPRIMER_AVEC_SCANS,
                mention=MENTION_DES_SCANS.format(
                    cardinal=f"{len(plan.scans_nommes)} "
                             f"{'dossier' if len(plan.scans_nommes) == 1 else 'dossiers'}")),
            ecrit=True))
    issues.append(Issue(CLE_ANNULER,
                        MOTIF_DE_L_ISSUE.format(libelle=LIBELLE_ANNULER,
                                                mention=MENTION_RIEN_TOUCHE)))
    return ChoixExclusif(issues)


def mots_cles_de_l_issue(plan: PlanDeSuppression, issue: Issue
                         ) -> dict[str, object] | None:
    """Les mots-cles de l'appel REEL que cette issue declenche.

    Rend ``None`` pour l'issue qui n'ecrit pas -- il n'y a alors aucun appel,
    et c'est le point : `annuler` ne touche pas le coeur du tout.

    **Les trois consentements du coeur restent DISTINCTS** : `dry_run=False`,
    `confirmation_dernier_lot=` et `avec_scans=` sont trois mots-cles separes
    (« deux consentements empiles, jamais un seul qui couvre les deux »), et
    cette fonction ne fusionne rien -- elle leve exactement ceux que l'issue
    choisie nomme.
    """
    if not issue.ecrit:
        return None
    if plan.est_un_groupe:
        # **Un refus BRUYANT plutot qu'un `dict` plausible** (`EPIC11-ARB-264`).
        # `plan.cible` est vide sur un plan de groupe, donc l'etaler produirait
        # `remove_project_element(projet, dry_run=False)` -- « vise EXACTEMENT
        # un lot ou un rush, jamais aucun des deux ». Le coeur refuserait, mais
        # sous un message qui parle de `lot_id`, pas de groupe.
        # `executer_la_suppression` branche AVANT d'arriver ici ; cette levee
        # existe pour qu'un appelant neuf ne trouve pas une surface muette.
        raise ProjectMaintenanceError(
            "Un plan de GROUPE porte N cibles: il n'a pas de mots-cles "
            "d'appel unique. Passer par remove_project_group."
        )
    mots = dict(plan.cible, dry_run=False)
    if plan.dernier_lot:
        mots["confirmation_dernier_lot"] = True
    if issue.cle == CLE_SUPPRIMER_ET_LIBERER:
        mots["liberer_le_rang"] = True
    if issue.cle == CLE_SUPPRIMER_AVEC_SCANS:
        mots["avec_scans"] = True
    return mots


def ligne_d_etat_de_la_confirmation(plan: PlanDeSuppression,
                                    ascii_seul: bool = False) -> str:
    """`67 fichiers · 1,5 Go · 4 groupes — rien n'a encore été écrit`."""
    morceaux = [_cardinal_de_fichiers(plan.fichiers), poids_lisible(plan.poids)]
    if plan.groupes:
        combien = len(plan.groupes)
        morceaux.append(f"{combien} "
                        f"{UNITE_GROUPE if combien == 1 else UNITE_GROUPES}")
    texte = f"{SEPARATEUR.join(morceaux)} — {PHRASE_RIEN_ECRIT}"
    return jetons.replier_ascii(texte) if ascii_seul else texte


# ---------------------------------------------------------------------------
# `E6-3` : le resultat, quand il RESTE quelque chose
# ---------------------------------------------------------------------------


def panneau_du_resultat(plan: PlanDeSuppression, rapport: RapportSuppression,
                        ascii_seul: bool = False) -> Panneau:
    """Le cartouche d'`E6-3`. **Il n'annonce pas la suppression** (AC 4.2).

    `fichiers_non_supprimes` non vide n'est PAS un succes : c'est la fuite de
    disque que cette story existe pour fermer. Le titre porte le mot
    `INCOMPLÈTE`, la premiere ligne porte le glyphe d'absence, et les chemins
    restes sont NOMMES un par un -- un cardinal seul ne permettrait pas d'aller
    les chercher.

    Les poids sont **mesures**, pas soustraits a l'aveugle : ce qui reste
    occupe encore le disque, donc il se `lstat` ; ce qui est parti vaut le
    poids d'avant moins celui-la.
    """
    restes = tuple(rapport.fichiers_non_supprimes)
    poids_restant = poids_des_fichiers(plan.projet, restes)
    partis = partis_du_rapport(plan, rapport)
    lignes = [
        LigneChiffree(LIBELLE_MANIFESTE, MANIFESTE_A_JOUR),
        LigneChiffree(LIBELLE_SUPPRIMES,
                      f"{_cardinal_de_fichiers(partis)}{SEPARATEUR}"
                      f"{poids_lisible(max(plan.poids - poids_restant, 0))}"),
        LigneChiffree(LIBELLE_RESTES,
                      f"{_cardinal_de_fichiers(len(restes))}{SEPARATEUR}"
                      f"{poids_lisible(poids_restant)}"),
    ]
    ecartes = ecartes_du_plan(plan)
    if ecartes:
        # **Sans cette ligne, le cartouche se contredisait tout seul** : un
        # groupe entierement refuse rendait « Supprimés 0 fichiers / Restés
        # 0 fichiers » au-dessus d'un bloc qui nomme deux membres restes. Les
        # deux disent vrai -- aucun FICHIER n'a resiste, puisque aucun n'a ete
        # touche -- et c'est justement pourquoi le cardinal manquant est en
        # ELEMENTS (voir :data:`LIBELLE_ECARTES`).
        lignes.append(LigneChiffree(
            LIBELLE_ECARTES, len(ecartes),
            unite=UNITE_ELEMENT if len(ecartes) == 1 else UNITE_ELEMENTS))
    return Panneau(TITRE_INCOMPLETE, lignes)


def lignes_des_restes(rapport: RapportSuppression,
                      ascii_seul: bool = False) -> list[str]:
    """La tete d'`E6-3`, les chemins restes, et le motif generique.

    **Chaque chemin est nomme**, en entier : c'est ce qui distingue ce compte
    rendu d'un compteur. `jetons.ajuster` les abrege a la largeur au dessin, et
    par le MILIEU (`abreger_nom`) -- un chemin coupe par la fin perdrait son
    nom de fichier, la seule partie qu'on cherche.
    """
    restes = tuple(rapport.fichiers_non_supprimes)
    if not restes:
        return []
    table = jetons.glyphes(ascii_seul)
    motif = (PHRASE_DES_RESTES_SINGULIER if len(restes) == 1
             else PHRASE_DES_RESTES)
    tete = motif.format(cardinal=_cardinal_de_fichiers(len(restes)))
    return ([_replie(f"{table['absent']} {tete}", ascii_seul), ""]
            + [f"  {chemin}" for chemin in restes]
            + ["", _replie(f"{LIBELLE_MOTIF}  {MOTIF_DES_RESTES}",
                           ascii_seul)])


def ecartes_du_plan(plan: PlanDeSuppression,
                    groupe: RapportDeGroupe | None = None
                    ) -> tuple[tuple[str, str], ...]:
    """Ce qui ne part PAS d'un groupe, **des deux causes a la fois**.

    C'est le seul lieu ou les deux familles se rassemblent, et elles doivent se
    rassembler parce que l'operateur ne les distingue pas : un master qui reste
    sur le disque reste, que ce soit le produit ou le coeur qui ait recule.

    * les membres que le PRODUIT ne sait pas viser -- `plan.membres_ecartes`,
      leves par :func:`ecartes_du_groupe`. Ils n'ont jamais atteint le coeur ;
    * les lignes que le COEUR a refusees, avec sa phrase VERBATIM
      (`EPIC11-ARB-258`). Elles n'existent que sur un rapport de groupe.

    ``groupe`` dit **quel des deux temps** on lit. Omis, il vaut l'execution si
    elle a eu lieu, et l'apercu sinon : c'est ce que veut un appelant qui
    demande « ou en est-on », et les deux ecrans le prennent tel quel.

    **L'ordre : les non-visables d'abord, puis les refus du coeur dans l'ordre
    des lignes.** Ce n'est pas l'ordre de l'arbre, et le dire vaut mieux que de
    le laisser croire -- les non-visables n'ont pas de ligne, donc rien ne les
    situe parmi celles-ci. L'ordre des lignes, lui, est celui du manifeste
    (`EPIC11-ARB-109`), et il est aussi l'ordre de destruction.

    Rend un tuple vide sur un plan ordinaire : un objet seul n'a pas de membre,
    et son refus a deja son propre ecran (:func:`refus_de_la_suppression`).

    **La garde `est_un_groupe` est un mutant EQUIVALENT, et c'est dit plutot
    que tu** (campagne du 2026-09-07, mutant `M-B4` survivant). La retirer ne
    change AUCUNE sortie : :func:`preparer_la_suppression` ne pose ni
    `membres_ecartes` ni aucun des deux rapports de groupe, si bien qu'un plan
    d'objet parcourt deux collections vides et rend `()` de toute facon. Aucun
    banc ne peut donc la tuer sans fabriquer a la main un plan que le produit
    n'ecrit jamais -- ce qui mesurerait le banc, pas le produit. Elle reste
    parce qu'elle dit l'intention et coupe court ; elle n'est pas comptee
    comme un survivant a fermer.
    """
    if not plan.est_un_groupe:
        return ()
    if groupe is None:
        groupe = plan.execution_du_groupe or plan.apercu_du_groupe
    ecartes = list(plan.membres_ecartes)
    for ligne in (groupe.lignes if groupe is not None else ()):
        if ligne.refus:
            ecartes.append((ligne.libelle, ligne.refus))
    return tuple(ecartes)


def lignes_des_ecartes(ecartes: Sequence[tuple[str, str]],
                       ascii_seul: bool = False, *,
                       apres: bool = False) -> list[str]:
    """Le bloc « ce qui ne part pas » : un membre NOMME, sa raison SOUS lui.

    Le pendant de :func:`lignes_des_restes` pour ce que le compte rendu d'un
    groupe ne savait pas dire. La difference de forme n'est pas cosmetique :
    `lignes_des_restes` porte N chemins sous **un** motif generique, parce que
    le coeur ne rend aucune raison par chemin ; ici chaque membre porte **sa**
    raison, parce que le coeur la rend, une par ligne, et qu'`EPIC11-ARB-264`
    la veut « pour chacun » -- Egan, verbatim : « Le projet peut rester a moitie
    supprime, et il faut relancer en sachant ce qui reste. »

    ``apres`` choisit le temps : promesse sur `E6-2`, constat sur `E6-3`. Voir
    :data:`PHRASE_DES_ECARTES`.

    **Aucune borne sur N**, et ce n'est pas un oubli : `lignes_des_restes` n'en
    a pas davantage, et en poser une ici seulement ferait deux regles de
    troncature pour deux blocs voisins du meme ecran. Un groupe de vingt
    membres tous refuses depasse donc la hauteur d'un terminal de 24 lignes --
    l'ecart est reel, il vaut pour les deux blocs, et il se tranche pour les
    deux a la fois plutot qu'a moitie ici.
    """
    if not ecartes:
        return []
    table = jetons.glyphes(ascii_seul)
    if apres:
        motif = (PHRASE_DES_ECARTES_APRES_SINGULIER if len(ecartes) == 1
                 else PHRASE_DES_ECARTES_APRES)
    else:
        motif = (PHRASE_DES_ECARTES_SINGULIER if len(ecartes) == 1
                 else PHRASE_DES_ECARTES)
    cardinal = (f"{grouper_les_milliers(len(ecartes))} "
                f"{UNITE_ELEMENT if len(ecartes) == 1 else UNITE_ELEMENTS}")
    lignes = [_replie(f"{table['absent']} {motif.format(cardinal=cardinal)}",
                      ascii_seul), ""]
    for nom, raison in ecartes:
        lignes.append(f"  {nom}")
        # La raison est INDENTEE sous son membre plutot que collee a sa suite :
        # les phrases du coeur font deux a trois cents caracteres, et
        # `jetons.ajuster` coupe a la largeur -- accolee, elle emporterait le
        # nom avec elle, qui est la seule partie qu'on vient chercher.
        lignes.append(f"    {_replie(raison, ascii_seul)}")
    return lignes


def panneau_de_la_reussite(plan: PlanDeSuppression,
                           rapport: RapportSuppression) -> Panneau:
    """Le cartouche de `E6-3b`. **Il annonce ce qui a eu lieu**, pas ce qui reste.

    Il ne se monte que lorsque `fichiers_non_supprimes` est VIDE : c'est la
    symetrie exacte de :func:`panneau_du_resultat`, et les deux ecrans ne
    peuvent donc pas se monter tous les deux.

    **Le poids est celui du plan, sans soustraction.** Rien ne reste, donc rien
    n'est a `lstat` : le poids libere est exactement celui que la confirmation
    avait promis. Le mesurer a nouveau sur un disque ou les fichiers n'existent
    plus rendrait zero.

    La ligne du rang n'existe **que** si le rapport declare un rang rendu
    (`EPIC11-ARB-92`, point 3 : un rang se consomme et ne se rend que sur
    demande). L'operateur qui a retenu `Supprimer` sans liberer ne doit pas
    lire qu'un rang lui a ete rendu.
    """
    lignes = [
        LigneChiffree(LIBELLE_SUPPRIMES,
                      f"{_cardinal_de_fichiers(plan.fichiers)}{SEPARATEUR}"
                      + PHRASE_LIBERES.format(poids=poids_lisible(plan.poids))),
        LigneChiffree(LIBELLE_MANIFESTE, MANIFESTE_A_JOUR),
    ]
    if rapport.rang_libere:
        lignes.append(LigneChiffree(
            LIBELLE_RANG_LIBERE,
            MOTIF_DU_RANG_RENDU.format(
                rang=MOTIF_DU_RANG.format(rang=rapport.rang_vise))))
    return Panneau(TITRE_REUSSITE, lignes)


def lignes_de_la_reussite(plan: PlanDeSuppression,
                          ascii_seul: bool = False) -> list[str]:
    """La tete de `E6-3b` : le glyphe PLEIN et l'objet supprime.

    Elle est HORS `Panneau` pour la meme raison que :func:`lignes_des_emportes`
    -- ce n'est pas une ligne chiffree, et `LigneChiffree` calerait un chiffre
    a droite la ou la maquette ne veut qu'une phrase.

    Le glyphe est celui de la completude, comme sur les quatre autres ecrans de
    compte rendu du depot. Il est **declare** a la maquette plutot que devine :
    pose dans un cartouche, il n'ouvre pas de colonne et le repli par motif ne
    le verrait pas.
    """
    table = jetons.glyphes(ascii_seul)
    return [_replie(f"{table['complete']} {plan.libelle}", ascii_seul), ""]


def ligne_d_etat_de_la_reussite(plan: PlanDeSuppression,
                                rapport: RapportSuppression,
                                ascii_seul: bool = False) -> str:
    """`●  67 fichiers supprimés · 1,5 Go libérés · manifeste à jour · aucun reste`.

    La derniere mention est le **volet symetrique** de celle de `E6-3` : la ou
    l'ecran incomplet nomme ce qui reste, celui-ci dit qu'il ne reste rien. Un
    compte rendu qui se tairait sur ce point laisserait la question ouverte,
    et c'est exactement la question que la story existe pour fermer.

    Quand un rang a ete rendu, il remplace `aucun reste` : c'est l'information
    neuve, et la maquette la porte a cette place.
    """
    supprimes = (PHRASE_SUPPRIME_EN_ETAT if plan.fichiers == 1
                 else PHRASE_SUPPRIMES_EN_ETAT)
    queue = (PHRASE_RANG_RENDU.format(
                 rang=MOTIF_DU_RANG.format(rang=rapport.rang_vise))
             if rapport.rang_libere else PHRASE_AUCUN_RESTE)
    texte = (f"{jetons.GLYPHES['complete']}  "
             f"{supprimes.format(cardinal=_cardinal_de_fichiers(plan.fichiers))}"
             f"{SEPARATEUR}"
             f"{PHRASE_LIBERES.format(poids=poids_lisible(plan.poids))}"
             f"{SEPARATEUR}{PHRASE_MANIFESTE_EN_ETAT}{SEPARATEUR}{queue}")
    return jetons.replier_ascii(texte) if ascii_seul else texte


def partis_du_rapport(plan: "PlanDeSuppression",
                      rapport: RapportSuppression) -> int:
    """Combien de fichiers sont REELLEMENT partis, **borne a zero**.

    **Une seule redaction, et il a fallu deux findings pour l'obtenir.** `F9`
    (couche 1) a montre que le cardinal pouvait devenir negatif : `plan.fichiers`
    vient du **dry-run**, `fichiers_non_supprimes` du run **REEL**, et rien ne
    garantit que le reel ne nomme pas plus de fichiers que le dry-run n'en
    prevoyait -- un fichier apparu entre les deux passes suffit. `C2-3`
    (couche 2) a montre que la borne posee au cartouche ne fermait que la
    MOITIE du defaut : `EcranResultatDeSuppression.etat()` refaisait la
    soustraction pour son compte et rendait toujours « -1 retirés ».

    Deux surfaces qui calculent la meme grandeur avec deux redactions
    divergent a la premiere correction qui n'en touche qu'une. C'est
    exactement ce qui s'est passe, entre le commit de `F9` et la mesure de
    `C2-3` -- quelques heures.
    """
    return max(plan.fichiers - len(rapport.fichiers_non_supprimes), 0)


def ligne_d_etat_du_resultat(rapport: RapportSuppression, partis: int,
                             ascii_seul: bool = False) -> str:
    """`✕  3 fichiers n'ont pas pu être supprimés · manifeste à jour · 64 retirés`.

    **Ce qu'elle ne dit PAS d'un groupe, dit plutot que tu** (2026-09-07, en
    fermant `C3-2`). Elle compte des FICHIERS, et un membre refuse par le coeur
    n'en rend aucun : sur un groupe entierement refuse, elle annonce donc
    « 0 fichiers n'ont pas pu être supprimés · 0 retirés ». Chaque moitie est
    vraie -- aucun fichier n'a resiste, puisque aucun n'a ete touche -- mais
    prise seule la ligne se lit comme un succes.

    Ce qui la rattrape est sur le meme ecran et au-dessus d'elle : le titre
    porte `INCOMPLÈTE`, le cartouche porte `Écartés  N éléments`, et le bloc
    des ecartes nomme chaque membre avec sa raison. Elle n'est donc pas
    corrigee ici : lui faire porter un second cardinal dans une autre unite
    demanderait de trancher lequel des deux ouvre la ligne, ce qu'aucune
    maquette ne dessine (`EPIC11-ARB-144`).
    """
    restes = len(rapport.fichiers_non_supprimes)
    motif = (PHRASE_DES_RESTES_EN_ETAT_SINGULIER if restes == 1
             else PHRASE_DES_RESTES_EN_ETAT)
    retires = (PHRASE_RETIRE if partis == 1 else PHRASE_RETIRES)
    texte = (f"{jetons.GLYPHES['absent']}  "
             f"{motif.format(cardinal=_cardinal_de_fichiers(restes))}"
             f"{SEPARATEUR}{PHRASE_MANIFESTE_EN_ETAT}{SEPARATEUR}"
             f"{retires.format(cardinal=grouper_les_milliers(partis))}")
    return jetons.replier_ascii(texte) if ascii_seul else texte


# ---------------------------------------------------------------------------
# Les trois ecrans
# ---------------------------------------------------------------------------


class EcranSuppressionConfirmation(EcranChiffre):
    """`E6-2` / `E6-2b` -- le point de jugement. **Rien n'est ecrit** (AC 3.3).

    Elle herite d'`EcranChiffre` et n'ecrit **pas** un second point de
    jugement : le cartouche, le `ChoixExclusif`, la navigation et la ligne
    d'etat y sont deja, livres par la story 11.1, et `execution.py` -- partage
    par les quatre ateliers -- n'est pas modifie (AC 3.1). Le banc le mesure
    par l'absence du chemin dans la liste des fichiers de la story.

    **`E6-2` et `E6-2b` sont le meme ecran a deux moments**, comme `E6-1` et
    `E6-1a` le sont de l'autre cote. Ce qui les separe est une phrase de plus
    dans le cartouche et une issue de plus dans le choix -- pas un `Screen`
    de plus, qui empilerait deux paliers la ou `EPIC11-ARB-2` en veut un.

    **Aucun nom n'est editable** (`EPIC11-ARB-141`, AC 5.1) : cet ecran ne
    passe **aucun** modele de noms, et la base en pose un vide d'elle-meme.
    `Tab` n'a donc aucune destination et `EcranChiffre.traiter` le rend
    inerte. Ce n'est pas une garde ajoutee ici, c'est la consequence de ne
    pas donner de noms editables -- et la ligne de raccourcis
    ne l'annonce pas non plus, les deux allant ensemble.

    ``sur_issue`` est **requis et sans defaut** (finding `K3`, paye quatre fois
    dans cet epic) : un point de jugement qui ne sait pas a qui rendre son
    issue est un cul-de-sac.
    """

    titre = projet_lecture.PROJET
    #: Un ATTRIBUT de classe, jamais une `@property` : la garde d'epic de
    #: `test_repli_ascii.py` lit `classe.raccourcis` au niveau de la CLASSE.
    raccourcis = RACCOURCIS_CONFIRMATION
    #: Un passage : un point de jugement franchi ne reste pas sur le chemin du
    #: retour.
    TRANSITOIRE = True

    def __init__(self, plan: PlanDeSuppression, *,
                 sur_issue: Callable[[Issue], None]) -> None:
        super().__init__(panneau_de_la_confirmation(plan),
                         issues_de_la_suppression(plan),
                         sur_issue=sur_issue)
        #: Le plan montre. Il porte les chiffres ; l'ecran n'en recalcule aucun.
        self.plan = plan

    # -- rendu ---------------------------------------------------------------

    def lignes_du_panneau(self) -> list[str]:
        """Le cartouche, les emportes, la phrase du dernier lot, les ECARTES.

        Le panneau est **recompose** plutot que garde tel quel : `ascii_seul`
        commande les glyphes, et il n'est connu qu'une fois l'ecran monte.
        `ascii_seul` **precede la mesure** -- `…` vaut une colonne, `...` en
        vaut trois.

        **Le bloc des ecartes est ici, sur le point de JUGEMENT, et c'est la
        moitie qui manquait** (`C1-1` / `C1-2` / `C3-3`). Le cartouche promet
        « les 2 elements de "masters — 3 masters" » : l'ecart entre les deux
        cardinaux etait le seul indice qu'un membre restait, et il n'en est pas
        un -- il faut connaitre les deux nombres et savoir ce qu'ils comptent.
        Un consentement donne sans savoir ce qui ne partira pas n'est pas
        eclaire, et `EPIC11-ARB-89` demande a l'inverse qu'une ecriture
        destructrice soit CONSCIENTE.

        Il se lit de l'APERCU, jamais de l'execution : sur cet ecran, rien n'a
        encore ete ecrit (AC 3.3). **Le passer explicitement est un mutant
        EQUIVALENT** (campagne du 2026-09-07, `M-G4`) : cet ecran est
        `TRANSITOIRE` et se construit avant tout appel d'ecriture, donc
        `execution_du_groupe` y vaut toujours ``None`` et le defaut
        d'`ecartes_du_plan` retombe deja sur l'apercu. Aucun banc ne peut
        distinguer les deux sans monter une confirmation sur un plan deja
        execute, ce que le parcours ne fait pas. L'argument est ecrit ici
        plutot que la ligne simplifiee : la lire dit de quel TEMPS cet ecran
        parle, et c'est la seule chose qui empeche de la brancher un jour sur
        l'execution par symetrie avec `E6-3`.
        """
        ascii_seul = getattr(self.app, "ascii_seul", False)
        lignes = panneau_de_la_confirmation(self.plan, ascii_seul).rendu(
            self.app.size.width, ascii_seul)
        lignes = lignes + lignes_des_emportes(self.plan, ascii_seul)
        ecartes = lignes_des_ecartes(
            ecartes_du_plan(self.plan, self.plan.apercu_du_groupe), ascii_seul)
        if ecartes:
            lignes = lignes + [""] + ecartes
        return lignes

    def titre_du_cartouche(self, ascii_seul: bool | None = None) -> str:
        if ascii_seul is None:
            ascii_seul = getattr(self.app, "ascii_seul", False)
        titre = TITRE_A_SUPPRIMER.format(cible=self.plan.libelle)
        return jetons.replier_ascii(titre) if ascii_seul else titre

    def objet_du_bandeau(self) -> str:
        """La droite du bandeau : `suppression · plan-04_12p5`."""
        ascii_seul = getattr(self.app, "ascii_seul", False)
        texte = f"{MOT_DE_LA_SUPPRESSION}{SEPARATEUR}{self.plan.libelle}"
        return jetons.replier_ascii(texte) if ascii_seul else texte

    def etat(self) -> str:
        """La ligne d'etat, et elle DIT que rien n'est ecrit (AC 3.3).

        Le refus d'une issue, quand il y en a un, passe avant : c'est le
        comportement d'`EcranChiffre`, et le taire rendrait une touche
        indistinguable d'un clavier casse.
        """
        if self._refus_annonce is not None:
            return self._refus_annonce
        return ligne_d_etat_de_la_confirmation(
            self.plan, getattr(self.app, "ascii_seul", False))


#: Le mot que le bandeau porte a gauche de la cible, sur les quatre ecrans de
#: suppression. Un seul littéral : deux redactions divergeraient entre la
#: confirmation et le resultat, sur le meme objet.
MOT_DE_LA_SUPPRESSION = "suppression"


#: La periode du rotor, en secondes. Meme valeur et meme motif que les quatre
#: autres ecrans a rotor du paquet : quatre dessins, donc un cycle complet en
#: quatre fois cette valeur -- assez lent pour qu'un terminal lent suive, assez
#: rapide pour qu'on voie que ca bouge.
PERIODE_DU_ROTOR = 0.25


class EcranSuppressionEnCours(ObjetTravaille, Palier):
    """`E6-2c` -- l'ecriture en cours. **Un rotor, pas une barre**, et c'est
    ce que le coeur permet de dire.

    `remove_project_element` **ne publie aucun canal de progression** : sa
    signature ne porte ni `emetteur` ni rappel de jalon (mesure du 2026-09-05
    sur la signature reelle). Une barre chiffree exigerait un total et un
    compte, donc elle serait fabriquee ici -- « un champ non mesure est omis,
    jamais rendu faux » (`DESIGN.md` section 3). La maquette valide exactement
    ca : `E6-2c` dessine un rotor et **aucune** barre.

    **Ecart nomme** : l'AC 4.4 demande « un ecran de progression [...] meme
    patron que partout ailleurs », et le patron `execution.EcranExecution` --
    barre, journal, liste de lots -- ne s'applique pas ici faute de canal. Le
    patron qui s'applique est celui du rotor, deja livre par `E6-1a`.

    **Aucune touche n'agit** : la ligne de raccourcis n'annonce que `F1`, et
    une touche qui agirait sans etre annoncee serait le symetrique du finding
    `I8`.
    """

    titre = projet_lecture.PROJET
    raccourcis = RACCOURCIS_EN_COURS
    #: Un passage : la duree d'une ecriture, pas une station.
    TRANSITOIRE = True
    ID_DU_CORPS = "corps-suppression-en-cours"
    def __init__(self, plan: PlanDeSuppression, pas_du_rotor: int = 0) -> None:
        super().__init__()
        self.plan = plan
        self.pas_du_rotor = pas_du_rotor
        #: Le minuteur qui fait tourner le rotor, **retenu** et non oublie.
        #: Meme poignee, et memes deux motifs, que `EcranMireEnCours` : un
        #: minuteur qu'on ne tient pas continue d'appeler
        #: :meth:`avancer_le_rotor` sur un ecran demonte -- donc de redessiner
        #: un arbre de widgets detruit --, et sans elle la seule facon de
        #: mesurer le rotor serait d'attendre l'horloge, c'est-a-dire de
        #: mesurer l'attente.
        self.minuteur = None

    def composer(self, largeur: int, ascii_seul: bool = False,
                 hauteur: int | None = None) -> list[str]:
        hauteur = jetons.hauteur_centrale() if hauteur is None else hauteur
        composition = Composition()
        composition.respirer()
        composition.poser(f"  {_replie(TITRE_EN_COURS, ascii_seul)}")
        composition.respirer()
        composition.poser(
            " " * 5 + jetons.rotor(self.pas_du_rotor, ascii_seul)
            + f"  {_replie(self.ligne_de_la_tache(), ascii_seul)}")
        lignes = composition.rendu(hauteur)[0]
        # **La zone se COMPLETE, elle ne se laisse pas courte.** `Composition`
        # sacrifie les respirations quand on deborde ; elle ne remplit pas
        # quand on manque -- c'est son contrat, et les autres ecrans du depot
        # n'en ont pas besoin parce que leur bloc central pose lui-meme sa
        # hauteur. `E6-2c` n'a que quatre lignes de contenu : sans ce
        # complement, la zone en rendrait quatre et le filet du bas remonterait
        # de treize lignes sous les yeux de l'operateur pendant l'ecriture.
        return lignes + [""] * max(hauteur - len(lignes), 0)

    def ligne_de_la_tache(self) -> str:
        """`tout le lot plan-04_12p5 — 67 fichiers, 1,5 Go`, verbatim d'`E6-2c`."""
        return (f"{self.plan.libelle} — "
                f"{_cardinal_de_fichiers(self.plan.fichiers)}, "
                f"{poids_lisible(self.plan.poids)}")

    def objet_du_bandeau(self) -> str:
        ascii_seul = getattr(self.app, "ascii_seul", False)
        return _replie(f"{MOT_DE_LA_SUPPRESSION}{SEPARATEUR}"
                       f"{self.plan.libelle}", ascii_seul)

    def ligne_d_etat(self, ascii_seul: bool = False) -> str:
        """`67 fichiers · 1,5 Go — écriture en cours`."""
        return _replie(
            f"{_cardinal_de_fichiers(self.plan.fichiers)}{SEPARATEUR}"
            f"{poids_lisible(self.plan.poids)} — {PHRASE_ECRITURE_EN_COURS}",
            ascii_seul)

    def etat(self) -> str:
        return self.ligne_d_etat(getattr(self.app, "ascii_seul", False))

    def lignes(self) -> list[str]:
        return self.composer(self.app.size.width, self.app.ascii_seul)

    def contenu(self) -> list[Widget]:
        self._corps = Static("", id=self.ID_DU_CORPS)
        return [Vertical(self._corps, id=f"centre-{self.ID_DU_CORPS}")]

    def rafraichir(self) -> None:
        if not self._assez_grand_au_dernier_dessin:
            return
        self._corps.update(bloc_peint(
            self.lignes(), jetons.largeur_utile(self.app.size.width),
            self.app))
        self.poser_etat(self.etat())
        super().rafraichir()

    def avancer_le_rotor(self) -> None:
        """Un pas de plus, et on redessine. C'est **tout** ce qui bouge ici.

        Appelee par un intervalle `textual` monte dans :meth:`on_mount`, et
        appelable a la main : c'est ce qui rend le mouvement mesurable sans
        terminal et sans horloge.

        Le pas ne se remet **jamais** a zero : le modulo est fait par
        `jetons.rotor`, precisement pour qu'un ecran qui compte ses propres pas
        ne rende pas un `IndexError` au quatrieme tour.
        """
        self.pas_du_rotor += 1
        self.rafraichir()

    def on_mount(self) -> None:
        """**Le rotor tourne**, et il ne tournait pas.

        `E6-2c` etait ecrit, complet et valide, mais orphelin -- rien ne le
        montait, et il ne portait aucun minuteur. Monte tel quel, il aurait
        montre un rotor FIGE, c'est-a-dire le contraire de ce qu'un rotor dit :
        « le seul signe honnete que la machine travaille ».
        """
        self.minuteur = self.set_interval(PERIODE_DU_ROTOR,
                                          self.avancer_le_rotor)
        self.rafraichir()

    def on_unmount(self) -> None:
        """Arreter le minuteur. Un ecran demonte n'a plus rien a faire tourner.

        Symetrique de :meth:`on_mount`, et meme motif qu'`EcranExecution` qui
        se desabonne : un rappel qui survit a son ecran ecrit dans un arbre de
        widgets detruit.
        """
        if self.minuteur is not None:
            self.minuteur.stop()
            self.minuteur = None

    def traiter(self, touche: str, caractere: str | None = None) -> bool:
        """**Aucune touche n'agit pendant l'ecriture.**

        Ce n'est pas une prudence : interrompre une suppression a mi-course
        laisserait un manifeste a jour et des fichiers sur le disque, qui est
        exactement la fuite que l'AC 4.2 existe pour nommer. `E6-2c` n'annonce
        d'ailleurs aucune touche d'interruption, la ou `E2-4` en annonce une.
        """
        return False


class EcranResultatDeSuppression(EcranResultat):
    """`E6-3` -- ce qui RESTE. **Il n'annonce pas la suppression** (AC 4.2).

    Il ne se monte que lorsque `fichiers_non_supprimes` est non vide : c'est la
    seule chose que `E6-3` dessine, et son titre le dit. Le cas reussi a
    desormais sa maquette et son ecran, :class:`EcranReussiteDeSuppression` ;
    les deux s'excluent dans :func:`suite_de_la_suppression`.

    Les trois suites sont celles de la maquette, et la troisieme est le retour :
    `EcranResultat` ajoute d'office sa propre `RETOUR` quand l'appelant n'en
    met pas, ce qui produirait ici DEUX retours. Elle est donc passee
    explicitement, et sous le mot d'`E6-3`.
    """

    titre = projet_lecture.PROJET
    raccourcis = RACCOURCIS_RESULTAT
    RETOUR = SUITE_RETOUR

    def __init__(self, plan: PlanDeSuppression, rapport: RapportSuppression,
                 sur_suite: Callable[[str], None] | None = None) -> None:
        """**Aucun `journal` ne se passe ici, et le mot-cle n'existe plus.**

        `EPIC11-ARB-246` retire `Tab journal` de cet ecran ; le laisser
        recevable aurait laisse ouvert le chemin qui le RETABLIT sans un mot --
        `EcranResultat.__init__` remplace la ligne de raccourcis par
        `execution.RACCOURCIS_RESULTAT_AVEC_JOURNAL` des qu'un journal lui est
        passe, et cette ligne-la porte `Échap ateliers` la ou ces deux ecrans
        disent `Échap inventaire`. Le retrait est donc structurel : le seul
        appelant du produit (:func:`monter_le_compte_rendu`) n'en passait
        aucun, et plus personne ne le peut.
        """
        self.plan = plan
        self.rapport = rapport
        super().__init__(panneau_du_resultat(plan, rapport),
                         suites=[SUITE_REESSAYER, SUITE_OUVRIR, SUITE_RETOUR],
                         sur_suite=sur_suite, journal=None)

    def _lignes_des_ecartes(self, ascii_seul: bool) -> list[str]:
        """Le bloc des ecartes de cet ecran, **au temps du CONSTAT**.

        Ecrit une fois et appele deux : par :meth:`lignes` qui le dessine et
        par :meth:`rang_du_curseur` qui le compte. Deux redactions divergeraient
        et le curseur colorerait la mauvaise ligne -- le piege que cet ecran
        documente deja pour les restes.
        """
        return lignes_des_ecartes(ecartes_du_plan(self.plan), ascii_seul,
                                  apres=True)

    def lignes(self) -> list[str]:
        """Le cartouche, les chemins restes, les ECARTES, puis les suites.

        Les chemins sont poses **entre** le cartouche et les suites, comme
        `E6-3` les dessine : ils sont ce qu'on vient lire, les suites sont ce
        qu'on fait ensuite.

        **Les ecartes viennent APRES les restes**, et l'ordre porte un sens :
        les restes sont des fichiers qu'on a tente de retirer et qui ont
        resiste ; les ecartes sont des objets qu'on n'a pas retires du tout. On
        lit d'abord l'echec de ce qui a ete tente.
        """
        ascii_seul = getattr(self.app, "ascii_seul", False)
        table = jetons.glyphes(ascii_seul)
        lignes = self.panneau.rendu(self.app.size.width, ascii_seul)
        lignes.extend(lignes_des_restes(self.rapport, ascii_seul))
        ecartes = self._lignes_des_ecartes(ascii_seul)
        if ecartes:
            lignes.append("")
            lignes.extend(ecartes)
        lignes.append("")
        for rang, suite in enumerate(self.suites):
            curseur = table["curseur"] if rang == self.curseur else " "
            lignes.append(f"  {curseur} {_replie(suite, ascii_seul)}")
        lignes.extend(self.lignes_du_journal())
        return lignes

    def rang_du_curseur(self) -> int | None:
        """Le rang de la suite sous le curseur, **passe explicitement**.

        Il est recalcule ici plutot qu'herite : `EcranResultat` compte les
        lignes du panneau plus une, et ce module en intercale d'autres entre
        les deux. Un rang herite designerait un chemin reste au lieu d'une
        suite -- et ne planterait pas : il colorerait la mauvaise ligne.
        """
        if not self.suites:
            return None
        ascii_seul = getattr(self.app, "ascii_seul", False)
        avant = len(self.panneau.rendu(self.app.size.width, ascii_seul))
        avant += len(lignes_des_restes(self.rapport, ascii_seul))
        ecartes = self._lignes_des_ecartes(ascii_seul)
        if ecartes:
            # La ligne vide que `lignes` intercale compte, elle aussi.
            avant += 1 + len(ecartes)
        return avant + 1 + self.curseur

    def choisir(self) -> str:
        """`⏎` : la suite sous le curseur, **retour compris**, part au parcours.

        Voir :func:`_choisir_par_le_parcours` : la base intercepte sa propre
        `RETOUR` **avant** de consulter le parcours, et la mene au menu des
        ateliers -- pas a l'inventaire que le libelle annonce.
        """
        return _choisir_par_le_parcours(self)

    def on_key(self, evenement) -> None:
        """`Échap` mene a l'inventaire, comme la ligne de raccourcis le dit.

        Voir :func:`_echapper_par_le_parcours`. Tout le reste du clavier reste
        celui du patron -- `↑↓` et `⏎` ne sont pas reecrits ici, et **la base
        n'est pas appelee** : `textual` la joue deja elle-meme, toute la MRO
        etant dispatchee.

        **`Tab` ne figure plus dans cette liste** (`EPIC11-ARB-246`). Le patron
        le traite bien, mais `EcranResultat.basculer_le_journal` rend faux sans
        journal et l'evenement n'est alors ni consomme ni suivi d'effet : cet
        ecran n'ayant plus aucun moyen d'en recevoir un, la touche est inerte
        **par construction** plutot que par convention.
        """
        _echapper_par_le_parcours(self, evenement)

    def objet_du_bandeau(self) -> str:
        ascii_seul = getattr(self.app, "ascii_seul", False)
        return _replie(f"{MOT_DE_LA_SUPPRESSION}{SEPARATEUR}"
                       f"{self.plan.libelle}", ascii_seul)

    def _partis_a_dire(self) -> int:
        """Le cardinal que la ligne d'etat porte, **mesurable sans coque**.

        `etat()` a besoin de `self.app` pour son repli ASCII ; le cardinal, non.
        Les separer est ce qui rend `C2-3` mesurable sur la surface REELLE de
        l'ecran plutot que sur la fonction seule.
        """
        return partis_du_rapport(self.plan, self.rapport)

    def etat(self) -> str:
        return ligne_d_etat_du_resultat(
            self.rapport, self._partis_a_dire(),
            getattr(self.app, "ascii_seul", False))


# ---------------------------------------------------------------------------
# Le cablage : ce que `Suppr` fait depuis l'inventaire
# ---------------------------------------------------------------------------


def executer_la_suppression(plan: PlanDeSuppression, issue: Issue,
                            *, retirer_du_projet=remove_project_element,
                            retirer_le_groupe=None,
                            ) -> RapportSuppression | None:
    """L'appel REEL au coeur. Rend ``None`` pour l'issue qui n'ecrit pas.

    **C'est la seule fonction de ce module qui puisse ecrire**, et elle
    n'ecrit pas elle-meme : elle appelle le point d'entree du coeur avec les
    mots-cles que :func:`mots_cles_de_l_issue` a leves. Une frontiere negative
    mesure a l'AST qu'aucun `unlink`, `rmtree` ni `remove` n'est appele dans ce
    module -- `remove_project_element` est un NOM, pas un appel a `remove`, et
    c'est la difference qu'un `grep` ne saurait pas faire et que l'AST fait.
    """
    if plan.est_un_groupe:
        if not issue.ecrit:
            return None
        # **N appels, au mieux** (`EPIC11-ARB-264`). L'agregat est produit par
        # LA fonction qui a servi l'apercu, donc l'operateur lit apres coup une
        # sortie de meme forme que celle qu'il a confirmee.
        retirer_le_groupe = retirer_le_groupe or remove_project_group
        execution = retirer_le_groupe(plan.projet, plan.cibles_du_groupe,
                                      dry_run=False)
        # **Le detail est GARDE, et il etait jete ici meme** (`C3-2`). L'agregat
        # ne porte que des chemins ; le refus d'une ligne, lui, porte une
        # phrase que seul le coeur sait rediger, et elle n'avait plus aucun
        # support entre cet appel et l'ecran. Voir
        # `PlanDeSuppression.execution_du_groupe`.
        plan.execution_du_groupe = execution
        return rapport_agrege_du_groupe(
            plan.libelle, execution, plan.apercu_du_groupe)
    mots = mots_cles_de_l_issue(plan, issue)
    if mots is None:
        return None
    return retirer_du_projet(plan.projet, **mots)


class EcranReussiteDeSuppression(EcranResultat):
    """`E6-3b` -- la suppression a ABOUTI. Le volet symetrique de `E6-3`.

    **Pourquoi cet ecran existe, et ce que son absence coutait.** `E6-3` ne
    dessine que l'incomplete. Le chemin nominal -- celui que l'operateur verra
    presque toujours -- remontait donc a l'inventaire sans un mot, et **le poids
    libere n'etait annonce nulle part**. C'est pourtant le seul endroit du
    produit qui puisse le CONFIRMER : la confirmation, elle, ne peut que le
    promettre, et entre les deux il y a eu une ecriture.

    La maquette a ete dessinee le 2026-09-05 sur demande d'Egan (« Maquette a
    dessiner depuis le meme modele que les autres ecrans de reussite »), sur le
    modele mesure de `E2-5`, `E3-8`, `E4-5` et `E5-5`. `EPIC11-ARB-144` est donc
    tenu : l'ecran n'est code qu'apres avoir ete dessine.

    **Les deux ecrans de compte rendu s'excluent par construction** : celui-ci
    se monte quand `fichiers_non_supprimes` est vide, `E6-3` quand il ne l'est
    pas. Aucune condition n'est ecrite deux fois -- c'est
    :func:`suite_de_la_suppression` qui tranche, une seule fois.

    Les trois suites sont celles de la maquette, et la troisieme est le retour.
    `EcranResultat` ajouterait d'office sa propre `RETOUR` si l'appelant n'en
    mettait pas, ce qui produirait ici DEUX retours ; elle est donc passee
    explicitement, sous le mot de `E6-3b`.
    """

    titre = projet_lecture.PROJET
    raccourcis = RACCOURCIS_RESULTAT
    RETOUR = SUITE_RETOUR

    def __init__(self, plan: PlanDeSuppression, rapport: RapportSuppression,
                 sur_suite: Callable[[str], None] | None = None) -> None:
        """**Aucun `journal` ne se passe ici, et le mot-cle n'existe plus.**

        `EPIC11-ARB-246` retire `Tab journal` de cet ecran ; le laisser
        recevable aurait laisse ouvert le chemin qui le RETABLIT sans un mot --
        `EcranResultat.__init__` remplace la ligne de raccourcis par
        `execution.RACCOURCIS_RESULTAT_AVEC_JOURNAL` des qu'un journal lui est
        passe, et cette ligne-la porte `Échap ateliers` la ou ces deux ecrans
        disent `Échap inventaire`. Le retrait est donc structurel : le seul
        appelant du produit (:func:`monter_le_compte_rendu`) n'en passait
        aucun, et plus personne ne le peut.
        """
        self.plan = plan
        self.rapport = rapport
        super().__init__(panneau_de_la_reussite(plan, rapport),
                         suites=[SUITE_OUVRIR_PROJET, SUITE_RETOUR],
                         sur_suite=sur_suite, journal=None)

    def lignes(self) -> list[str]:
        """La tete, le cartouche chiffre, les groupes emportes, puis les suites.

        L'ordre est celui de la maquette et il n'est pas indifferent : on lit
        d'abord CE QUI a disparu, ensuite COMBIEN, enfin le detail par groupe.
        Les suites viennent apres, parce qu'elles sont ce qu'on fait ensuite.
        """
        ascii_seul = getattr(self.app, "ascii_seul", False)
        table = jetons.glyphes(ascii_seul)
        lignes = lignes_de_la_reussite(self.plan, ascii_seul)
        lignes.extend(self.panneau.rendu(self.app.size.width, ascii_seul))
        emportes = lignes_des_emportes(self.plan, ascii_seul)
        if emportes:
            lignes.append("")
            lignes.extend(emportes)
        lignes.append("")
        for rang, suite in enumerate(self.suites):
            curseur = table["curseur"] if rang == self.curseur else " "
            lignes.append(f"  {curseur} {_replie(suite, ascii_seul)}")
        lignes.extend(self.lignes_du_journal())
        return lignes

    def rang_du_curseur(self) -> int | None:
        """Le rang de la suite sous le curseur, **compte sur les lignes RENDUES**.

        Il est recalcule ici plutot qu'herite, pour la meme raison que sur
        `E6-3` : cet ecran intercale des lignes entre le cartouche et les
        suites. Un rang herite ne planterait pas -- il colorerait la mauvaise
        ligne, ce qui est pire.
        """
        if not self.suites:
            return None
        ascii_seul = getattr(self.app, "ascii_seul", False)
        avant = len(lignes_de_la_reussite(self.plan, ascii_seul))
        avant += len(self.panneau.rendu(self.app.size.width, ascii_seul))
        emportes = lignes_des_emportes(self.plan, ascii_seul)
        if emportes:
            avant += 1 + len(emportes)
        return avant + 1 + self.curseur

    def choisir(self) -> str:
        """`⏎` : la suite sous le curseur, **retour compris**, part au parcours.

        Voir :func:`_choisir_par_le_parcours` : la base intercepte sa propre
        `RETOUR` **avant** de consulter le parcours, et la mene au menu des
        ateliers -- pas a l'inventaire que le libelle annonce.
        """
        return _choisir_par_le_parcours(self)

    def on_key(self, evenement) -> None:
        """`Échap` mene a l'inventaire, comme la ligne de raccourcis le dit.

        Voir :func:`_echapper_par_le_parcours`. Tout le reste du clavier reste
        celui du patron -- `↑↓` et `⏎` ne sont pas reecrits ici, et **la base
        n'est pas appelee** : `textual` la joue deja elle-meme, toute la MRO
        etant dispatchee.

        **`Tab` ne figure plus dans cette liste** (`EPIC11-ARB-246`). Le patron
        le traite bien, mais `EcranResultat.basculer_le_journal` rend faux sans
        journal et l'evenement n'est alors ni consomme ni suivi d'effet : cet
        ecran n'ayant plus aucun moyen d'en recevoir un, la touche est inerte
        **par construction** plutot que par convention.
        """
        _echapper_par_le_parcours(self, evenement)

    def objet_du_bandeau(self) -> str:
        ascii_seul = getattr(self.app, "ascii_seul", False)
        return _replie(f"{MOT_DE_LA_SUPPRESSION}{SEPARATEUR}"
                       f"{self.plan.libelle}", ascii_seul)

    def etat(self) -> str:
        return ligne_d_etat_de_la_reussite(
            self.plan, self.rapport,
            getattr(self.app, "ascii_seul", False))


def refus_de_la_suppression(code: str, message: str,
                            suites: list[str] | None = None) -> EcranRefus:
    """L'ecran d'un refus de suppression. **Un refus, jamais un « pas encore ».**

    **Le mur qu'Egan a rencontre le 2026-09-06, verbatim** : « Supprimer un
    rushe (alors qu'il ne reste qu'un lot) - l'ecran n'existe pas encore ». Le
    coeur avait raison de refuser -- `remove_project_element` ne cascade jamais
    une suppression, et une cascade ferait partir N lots, leurs frames, leurs
    masters, leurs planches et leurs scans sur un geste qui n'en nommait qu'un.
    C'est son HABILLAGE qui mentait : `EcranPasEncore` dit « Cet ecran n'existe
    pas encore. Il arrive avec les ecrans de gestion des medias du palier
    Projet », c'est-a-dire une echeance pour un ecran **qui n'arrivera jamais**,
    annoncee a un operateur qui est deja dans ces ecrans-la.

    `EPIC11-ARB-89` : « un refus qui n'offre aucune issue est aussi fautif
    qu'une destruction silencieuse ». Trois choses changent, et elles se
    mesurent une par une :

    * le titre devient `Refus` au lieu de `Pas encore` -- rien n'est a venir ;
    * le refus porte un **code**, derive du nom de sa classe par
      `projet_inventaire.code_du_refus`. C'etait le seul obstacle nomme au
      registre des filets (« le router vers `EcranRefus` demande de decider
      quel CODE afficher -- `ProjectMaintenanceError` n'en porte pas »), et la
      derivation le leve sans table a tenir a jour : `LastLotRefusedError` et
      `ProjectMaintenanceError` rendent deux codes distincts, ce qui distingue
      a l'oeil « il reste des lots » de « ce serait le dernier rush » ;
    * l'issue est **nommee** dans `Suites`, et pas seulement suggeree par le
      message du coeur -- qui est tronque a 76 colonnes comme toute ligne de
      cet ecran (c'est exactement ce qu'Egan a vu : « ne supprime jamais un
      rush qui porte encore des l... »). Une entree de `Suites` est une ligne
      a elle, donc elle survit a la troncature du message.

    **Le message du coeur voyage VERBATIM** (`EPIC11-ARB-30`) : rien n'y est
    ajoute, rien n'en est retire. Ce qui s'ajoute est a cote, dans les suites.

    Ni `conserve` ni `non_ecrit` ne sont renseignes : ces refus sont leves
    **avant** toute ecriture -- `preparer_la_suppression` appelle le coeur en
    `dry_run`, et le chemin de reessai restaure le manifeste d'avant. Il n'y a
    donc ni ce qui a ete garde ni ce qui n'a pas ete ecrit a dire.
    """
    return EcranRefus(code, message, suites=suites or [])


def suites_du_refus(noeud: NoeudAffiche | None) -> list[str]:
    """Ce que l'operateur peut FAIRE, lu de l'arbre plutot que du message.

    Un rush que le coeur refuse de supprimer porte encore des lots, et ces
    lots sont **ses enfants dans l'arbre d'affichage** : les compter n'exige ni
    de relire la phrase du coeur, ni de redemander l'inventaire.

    Rend une liste vide quand il n'y a rien de nommable -- une suite inventee
    serait pire que pas de suite. Les deux issues d'`EcranRefus` (`Échap` qui
    ramene a l'inventaire, `⏎` qui remonte aux ateliers) restent annoncees dans
    tous les cas, donc l'ecran n'est jamais un blocage sec.
    """
    if noeud is None:
        return []
    lots = [enfant for enfant in noeud.enfants
            if enfant.nature == NATURE_LOT]
    if not lots:
        return []
    return [PHRASE_DES_LOTS_D_ABORD.format(
        cardinal=grouper_les_milliers(len(lots)),
        mot=MOT_DES_LOTS[len(lots) > 1])]


def motif_sans_cible(noeud: NoeudAffiche,
                     lot_id: str | None) -> tuple[str, str] | None:
    """Pourquoi `cible_du_noeud` n'a rien rendu, ou ``None`` si c'est le COEUR.

    **Les deux cas ne se ressemblent que par leur valeur de retour.** Rendre
    `None` sur une nature de :data:`NATURES_SANS_CIBLE_FINE` dit « le produit
    ne sait pas encore » (`frames_extraites` l'etait jusqu'au 2026-09-07, ou le
    coeur a recu la cible) ; le
    rendre sur un master orphelin dit « cet objet-la n'est pas visable », et
    les habiller pareil est ce qui a fait afficher « Retirer un master seul du
    projet / Cet ecran n'existe pas encore » sur un objet que le coeur sait
    parfaitement supprimer (`master=True` + `profile=`).

    Rend ``None`` -- « c'est bien un manque de produit » -- pour la seule
    famille qui en est un : :data:`NATURES_SANS_CIBLE_FINE`. Pour tout le
    reste, rend le couple `(code, phrase)` d'un refus, dans l'ordre ou les
    causes se presentent.
    """
    if noeud.groupe or noeud.cible is None:
        return CODE_SANS_LOT, PHRASE_SANS_LOT.format(objet=OBJET_SANS_NOM)
    if noeud.nature in NATURES_SANS_CIBLE_FINE:
        return None
    objet = identifiant_du_noeud(noeud) or OBJET_SANS_NOM
    if lot_id is None:
        return CODE_SANS_LOT, PHRASE_SANS_LOT.format(objet=objet)
    if noeud.nature == NATURE_MASTER:
        return (CODE_MASTER_ILLISIBLE,
                PHRASE_MASTER_ILLISIBLE.format(objet=objet, lot=lot_id))
    # Une nature que ce module ne sait pas viser et que le coeur ne nomme pas
    # non plus : elle n'a pas de lot manquant, elle n'a pas de profil illisible.
    # Le dire ainsi vaut mieux que d'inventer une troisieme cause.
    return CODE_SANS_LOT, PHRASE_SANS_LOT.format(objet=objet)


def lot_de_rattachement(arbre, noeud: NoeudAffiche) -> str | None:
    """Le `lot_id` d'un ORPHELIN, retrouve par EGALITE avec un lot declare.

    **Le mur, et sa cause exacte** (`EPIC11-ARB-260`). Un master qui ne se
    greffe sur rien atterrit en queue d'arbre, a la racine : :func:`lot_ancetre`
    rend alors ``None``, `cible_du_noeud` rend ``None`` a son tour, et l'ecran
    annoncait un manque de produit sur un objet que le coeur sait supprimer.

    **Jamais par decoupage de nom** -- la regle du depot est explicite, et deux
    modules la portent deja (`project_maintenance`, `project_inventory`) :
    `build_lot_id` condense et tronque, la decomposition est a sens unique.
    C'est donc `naming.profil_du_master` qui tranche, et il ne fait rien
    d'autre que ce que le point 1 de sa propre docstring promet -- « le prefixe
    se retire par egalite avec un lot CONNU ». Les lots connus sont ceux que
    l'ARBRE declare ; un lot non declare ne pose aucun contexte, meme regle que
    :func:`lot_ancetre`.

    **L'ambiguite se REFUSE plutot qu'elle ne s'arbitre**, comme pour la greffe
    des orphelins (`test_un_orphelin_a_TIGE_AMBIGUE_ne_se_greffe_PAS`) : deux
    lots declares dont l'un prefixe l'autre a travers le marqueur de master
    rendraient deux lectures valides du meme nom, et en choisir une viserait un
    objet que l'operateur n'a pas designe -- le risque R12.

    **Ce qu'elle N'OUVRE PAS, et le brief du lot se trompait dessus.** « Le
    coeur sait pourtant le faire (`master=True` + `profile=`) » est vrai d'un
    master DECLARE -- et un master declare est greffe sous son lot, donc
    :func:`lot_ancetre` le trouve et cette fonction-ci ne le voit jamais. Le
    seul master qui arrive ici est un orphelin, c'est-a-dire celui qu'aucun
    manifeste ne declare, et `_annexes_du_lot` resout la cible `master=` **par
    le manifeste** : mesure faite le 2026-09-06, le coeur rend « Le lot X ne
    declare aucun master au profil P ». Ce que cette fonction change n'est donc
    pas la suppression -- elle reste impossible -- mais **ce que l'operateur
    lit** : la raison reelle, qui nomme le lot et le profil, au lieu de « cet
    ecran n'existe pas encore », qui etait faux dans les deux sens. La cible
    d'un master non declare est une extension du coeur, portee a
    `deferred-work.md` sous `EPIC11-ARB-260`.

    **Ce qu'elle NE couvre pas non plus, dit plutot que tu** : les masters, et
    eux seuls. Une planche s'appelle `projet_demo_plan-04_25_6f-pay.pdf` -- le
    `lot_id` y est **au milieu**, derriere un prefixe de projet, et aucun
    lecteur exact n'existe pour ce nom-la dans `io.naming`. En ecrire un ici
    serait exactement la regle de nommage redigee loin de sa fabrique que la
    frontiere `test_AUCUN_module_de_la_TUI_ne_redige_une_regle_de_RANG` refuse.
    Une planche orpheline reste donc sans lot, et l'ecran le **dit** au lieu
    d'annoncer un ecran qui manque.
    """
    if noeud.nature != NATURE_MASTER:
        return None
    nom = identifiant_du_noeud(noeud)
    if nom is None:
        return None
    candidats = [lot for lot in lots_declares(arbre)
                 if naming.profil_du_master(nom, lot) is not None]
    return candidats[0] if len(candidats) == 1 else None


def lots_declares(arbre) -> tuple[str, ...]:
    """Les `lot_id` que l'arbre DECLARE, dans l'ordre de parcours.

    Le nom vient du COEUR (`identifiant_du_noeud`) et jamais de la ligne : un
    lot non declare porte la mention ` · non declare` a l'affichage, et la
    prendre pour un identifiant produirait un `lot_id` qui n'existe nulle part
    -- le finding `F2` de la couche 1, vu par un troisieme bout.
    """
    noms: list[str] = []
    for racine in getattr(arbre, "racines", ()):
        for noeud in racine.parcourir():
            if noeud.nature != NATURE_LOT:
                continue
            nom = identifiant_du_noeud(noeud)
            if nom is not None and nom not in noms:
                noms.append(nom)
    return tuple(noms)


def lot_ancetre(arbre, noeud: NoeudAffiche) -> str | None:
    """Le `lot_id` sous lequel ce noeud vit, ou ``None`` a la racine.

    **Il est LU de l'arbre, jamais decoupe du nom de l'objet.** Un master
    s'appelle `plan-04_25_mmu_prores_hq.mov` et une planche
    `projet_demo_plan-04_25_planches.pdf` : retrouver `plan-04_25` en decoupant
    l'un ou l'autre marcherait sur ces deux exemples et casserait des que le
    `lot_id` serait condense par `derive_short_id`. L'arbre, lui, PORTE la
    filiation -- c'est ce qu'il est.

    Le lot le plus PROCHE gagne, pas le premier rencontre : un lot scanne vit
    sous un scan qui vit sous un lot, et remonter jusqu'au premier lot croise
    en descendant rendrait le meme resultat par accident sur trois niveaux et
    le mauvais sur quatre.
    """

    def chercher(courant: NoeudAffiche,
                 lot: str | None) -> tuple[bool, str | None]:
        if courant is noeud:
            return True, lot
        #: Le lot se pose EN DESCENDANT, donc un noeud qui est lui-meme un lot
        #: ne se prend pas pour contexte -- une cible fine `lot_id=X` posee sur
        #: le lot X lui-meme viserait un objet DANS X, pas X.
        #: Et il se lit du COEUR, pas de la ligne : un lot non declare
        #: propagerait sinon sa mention d'affichage a TOUS ses enfants, ce qui
        #: est le finding `F2` de la couche 1 vu par son autre bout. Un lot
        #: sans objet de coeur ne pose aucun contexte -- l'appelant montre
        #: alors ce qui manque, plutot que d'inventer un identifiant.
        prochain = (identifiant_du_noeud(courant)
                    if courant.nature == NATURE_LOT else lot)
        for enfant in courant.enfants:
            trouve, valeur = chercher(enfant, prochain)
            if trouve:
                return True, valeur
        return False, None

    for racine in getattr(arbre, "racines", ()):
        trouve, valeur = chercher(racine, None)
        if trouve:
            return valeur
    return None


# ---------------------------------------------------------------------------
# Les suites des deux comptes rendus : ce que chacune fait REELLEMENT
# ---------------------------------------------------------------------------


def _dire(app, fait: str) -> str:
    """Poser le fait en ligne d'etat, replie si l'application l'est.

    Meme geste que `atelier_exports_resultat._dire` : **l'ecran ne change
    pas**. Descendre d'un palier pour annoncer qu'un dossier a ete ouvert
    ferait perdre le compte rendu au moment meme ou l'operateur va le comparer
    au contenu du dossier.
    """
    if getattr(app, "ascii_seul", False):
        fait = jetons.replier_ascii(fait)
    # **`None` est un appelant legitime**, et pas seulement en banc : la phrase
    # est ce que la fonction REND, la ligne d'etat n'est que l'endroit ou elle
    # s'affiche. Un appel sans ecran doit rendre la phrase, jamais lever --
    # `_application_montee` ne rattrape que l'ecran non monte, pas l'absence
    # d'ecran.
    application = None if app is None else _application_montee(app)
    if application is not None:
        application.palier_courant.poser_etat(fait)
    return fait


def dossier_des_restes(plan: PlanDeSuppression,
                       rapport: RapportSuppression) -> Path | None:
    """Le dossier qu'« Ouvrir le dossier » designe sur `E6-3`, ou ``None``.

    C'est le **parent commun** des fichiers restes, et le calcul est celui
    d'`atelier_scan_resultat.dossier_a_ouvrir` -- a ceci pres que le rapport
    nomme ici des FICHIERS et non des dossiers, d'ou le `.parent` avant la
    mise en commun. Sur le regime de la maquette -- un master a la racine et
    deux TIFF sous le dossier de frames extraites du lot --, le parent commun
    est le dossier du projet : c'est le seul dossier qui les contienne tous, et
    en ouvrir un seul cacherait les autres. La maquette, dessinee avant le
    renommage du lot `D1`, ecrit encore l'ancien nom de ce dossier ; la citer
    verbatim ici ferait rougir `test_vocabulaire_de_la_tui.py`, et elle aurait
    raison -- un docstring est une chaine de `tui/` comme une autre.

    Les chemins sont ceux que **le coeur a rendus**, resolus sous
    `plan.projet` : aucune recomposition depuis un nom d'objet, ce qui
    ouvrirait un dossier ou rien n'est reste (`EPIC11-ARB-46`).
    """
    parents = [str((Path(plan.projet) / relatif).parent)
               for relatif in rapport.fichiers_non_supprimes]
    if not parents:
        return None
    try:
        commun = os.path.commonpath(parents)
    except ValueError:
        # Des chemins sans racine commune -- deux volumes sous Windows. Aucun
        # dossier ne les contient tous ; on ouvre celui du premier reste, et
        # le fait affiche NOMME le chemin ouvert, si bien que l'operateur voit
        # lequel.
        commun = parents[0]
    return Path(commun)


def ouvrir_le_dossier_des_restes(app, plan: PlanDeSuppression,
                                 rapport: RapportSuppression) -> str:
    """`E6-3` / « Ouvrir le dossier » : le dossier ou les restes vivent.

    **Le resultat est DIT, dans tous les cas** -- le chemin ouvert, l'absence
    de dossier, ou le motif qui a empeche l'ouverture (un conteneur sans
    bureau n'a pas d'`xdg-open`). Un echec silencieux serait indistinguable de
    la suite decorative que le finding `K3` a payee.

    **L'appel systeme est celui d'`execution.py`, et il n'y en a pas d'autre**
    (`EPIC11-ARB-85` : « un seul site d'appel dans le paquet `tui/` »). Ce
    module n'en ouvre aucun second, et la frontiere AST de
    `test_coeur_en_processus.py` compte ce site-la.
    """
    dossier = dossier_des_restes(plan, rapport)
    fait = (AUCUN_DOSSIER_A_OUVRIR if dossier is None
            else ouvrir_dans_l_explorateur_du_systeme(dossier))
    return _dire(app, fait)


def ouvrir_le_dossier_du_projet(app, plan: PlanDeSuppression) -> str:
    """`E6-3b` / « Ouvrir le dossier du projet » : la racine du projet.

    Le dossier est **lu du plan** (`plan.projet`, celui que le coeur a recu),
    jamais du dossier courant du processus : c'est la meme derivation que
    celle des trois autres ateliers, et elle vaut apres une suppression, ou
    l'objet ouvert n'existe plus mais son projet, si.
    """
    dossier = None if plan.projet is None else Path(plan.projet)
    fait = (AUCUN_PROJET_A_OUVRIR if dossier is None
            else ouvrir_dans_l_explorateur_du_systeme(dossier))
    return _dire(app, fait)


def remonter_a_l_inventaire(app, plan: PlanDeSuppression | None = None
                            ) -> bool:
    """`Retour a l'inventaire` : depiler jusqu'a `E6-1`, et le RELIRE.

    **La surcharge du libelle ne suffisait pas a changer la destination, et
    c'est le defaut que cette fonction ferme.** Les deux ecrans posent
    `RETOUR = SUITE_RETOUR` -- « Retour a l'inventaire » --, mais
    `EcranResultat.choisir` traite sa propre `RETOUR` par
    `revenir_aux_ateliers()`, qui depile jusqu'au **menu des ateliers**
    (`RANG_DES_ATELIERS`), c'est-a-dire deux stations au-dessus de
    l'inventaire. L'ecran annoncait donc une destination et en servait une
    autre : le frere exact de `MQ-4`/`MQ-5`, pris par le libelle plutot que
    par le filet.

    On depile **jusqu'a l'ecran vise** et non jusqu'a un rang : la profondeur
    entre l'inventaire et le compte rendu depend du chemin suivi (`E6-2` seul,
    ou `E6-2` puis un reessai), et un rang ecrit en dur la fausserait au
    premier ecran intercale -- meme motif que
    `atelier_scan_resultat.remonter_a_l_ouverture_de_l_atelier`.

    **Trois sorties, aucune n'est un blocage sec** (`EPIC11-ARB-89`) :

    * aucune application montee -> faux, et l'appelant sait que rien n'a bouge ;
    * aucun inventaire dans la pile -> on remonte d'UN cran, comme `Echap`.
      C'est le regime d'un banc qui monte `E6-3` seul, et vider la pile
      jusqu'a la racine y serait pire que ne rien faire ;
    * l'inventaire est retrouve -> on s'y arrete, et on le RELIT sur le
      disque quand le plan nomme son projet.
    """
    application = _application_montee(app)
    if application is None:
        return False
    if not any(isinstance(ecran, EcranInventaireDuProjet)
               for ecran in application.screen_stack):
        application.action_remonter()
        return False
    while len(application.screen_stack) > 1 and not isinstance(
            application.screen, EcranInventaireDuProjet):
        application.pop_screen()
    inventaire = application.screen
    if plan is not None and plan.projet is not None:
        # L'arbre d'AVANT la suppression listerait l'objet qui vient de
        # partir. Relire est ce qui empeche l'apercu de mentir ; l'echec de
        # relecture laisse l'arbre precedent plutot qu'un arbre vide.
        relire_l_inventaire(inventaire, plan.projet)
    return True


def monter_le_compte_rendu(application, plan: PlanDeSuppression,
                           rapport: RapportSuppression, issue: Issue, *,
                           retirer_du_projet=remove_project_element
                           ) -> EcranResultat:
    """Construire `E6-3` ou `E6-3b` **et poser son rappel de suites**.

    **Les deux comptes rendus s'excluent ici, une seule fois.** Ecrire la
    condition dans chacun des deux ecrans la ferait diverger, et deux ecrans
    qui se croient tous deux legitimes en empileraient deux.

    Le rappel se pose **APRES** construction : il a besoin de l'ecran lui-meme
    pour retrouver l'application montee, et un ecran ne peut pas se citer dans
    son propre appel de construction. C'est le piege deja paye par
    :func:`ouvrir_la_suppression`.

    `issue` voyage jusqu'ici parce que « Reessayer » la rejoue : les trois
    consentements du coeur (`dry_run`, `confirmation_dernier_lot`,
    `avec_scans`) sont ceux de l'issue retenue, et un reessai qui les
    reinventerait supprimerait autre chose que ce que l'operateur a valide.
    """
    # **Deux causes d'incompletude, et une seule etait lue** (`C3-2`/`C3-2b`).
    # `fichiers_non_supprimes` attrape ce qui a RESISTE. Il n'attrape pas ce que
    # le coeur a REFUSE : un refus ne rend aucun chemin, donc un groupe dont
    # une ligne -- ou toutes -- avait ete refusee arrivait ici avec une liste de
    # restes vide et montait l'ecran de REUSSITE. Mesure avant correction :
    # deux masters, le second refuse, « Supprimés 1 fichier · 3,9 ko libérés /
    # Manifeste à jour », ni le nom du master reste ni la phrase du coeur.
    #
    # Les deux causes sont donc lues, et `ecartes_du_plan` rend vide sur un plan
    # ordinaire : le chemin d'un objet seul ne change pas.
    classe = (EcranResultatDeSuppression
              if rapport.fichiers_non_supprimes or ecartes_du_plan(plan)
              else EcranReussiteDeSuppression)
    ecran = classe(plan, rapport)
    ecran._sur_suite = lambda suite: suivre(
        ecran, plan, rapport, issue, suite,
        retirer_du_projet=retirer_du_projet)
    return ecran


def reessayer_la_suppression(app, plan: PlanDeSuppression, issue: Issue, *,
                             retirer_du_projet=remove_project_element) -> bool:
    """`E6-3` / « Reessayer » : rejouer la suppression sur ce qui RESTE.

    **Le coeur EST rejouable, et c'est une mesure et non une supposition** :
    « des lors que des fichiers restent, le lot EXISTE encore : le manifeste
    doit le declarer, et le geste redevient rejouable ». Sur un echec partiel,
    `remove_project_element` **restaure le manifeste d'avant** -- le chemin du
    lot et du rush (`EPIC11-ARB-89`, le `rm -rf` manuel qu'il ferme) comme
    celui des cibles fines `master`, `scan` et `lot_scanne`. La cible se
    resout donc encore, et le meme appel repasse sur les fichiers survivants :
    ceux qui sont deja partis ne sont plus `presents`, ils ne sont ni
    recomptes ni redemandes.

    **La cible `planche` est l'exception, et elle est NOMMEE plutot que tue.**
    Son chemin ne restaure pas l'entree du manifeste apres un echec partiel :
    un reessai y rend `ProjectMaintenanceError`, et cette fonction le montre
    sur :func:`refus_de_la_suppression` avec le message du coeur -- verbatim,
    `EPIC11-ARB-30`. **Sur un ecran de REFUS depuis `EPIC11-ARB-260`, et plus
    sur un « pas encore »** : un reessai qui echoue n'annonce aucun ecran a
    venir, il constate que le manifeste ne porte plus la cible.
    C'est une issue, pas un blocage sec, et l'ecart est porte a
    `deferred-work.md` sous `SUP-PL-1` plutot que corrige ici : il vit dans
    `project_maintenance.py`, que ce module ne modifie pas -- une frontiere
    negative mesure ce fait sur le diff.

    **Le compte rendu est REMPLACE, jamais empile** : trois reessais de suite
    laisseraient sinon trois `E6-3` l'un sur l'autre, et l'operateur devrait
    remonter trois fois -- le defaut mesure le 2026-08-28 sur `descendre`.
    """
    application = _application_montee(app)
    if application is None:
        return False
    try:
        rapport = executer_la_suppression(plan, issue,
                                          retirer_du_projet=retirer_du_projet)
    except ProjectMaintenanceError as refus:
        application.descendre(
            refus_de_la_suppression(code_du_refus(refus), str(refus)))
        return False
    if rapport is None:
        # L'issue n'ecrit pas -- impossible depuis `E6-3`, dont l'issue est
        # toujours une issue d'ecriture, mais on ne suppose pas : on remonte.
        application.action_remonter()
        return False
    remplacer_le_compte_rendu(application, app, monter_le_compte_rendu(
        application, plan, rapport, issue,
        retirer_du_projet=retirer_du_projet))
    return True


def remplacer_le_compte_rendu(application, ancien, nouveau) -> None:
    """Poser `nouveau` **a la place** d'`ancien`, jamais par-dessus.

    Le depilement est conditionne a ce que le sommet SOIT bien l'ancien ecran :
    un appel venu d'ailleurs ne doit pas depiler l'ecran de quelqu'un d'autre.
    """
    if (application.screen is ancien
            and len(application.screen_stack) > 1):
        application.pop_screen()
    application.descendre(nouveau)


def suivre(app, plan: PlanDeSuppression, rapport: RapportSuppression,
           issue: Issue, suite: str, *,
           retirer_du_projet=remove_project_element) -> None:
    """Ce que `E6-3` et `E6-3b` font d'une suite choisie. **Aucune n'est muette.**

    Cinq destinations, et la derniere est le filet :

    * :data:`SUITE_REESSAYER` rejoue la suppression sur ce qui reste -- la
      **seule** des quatre qui ecrive, et elle passe par le chemin existant
      (:func:`executer_la_suppression`) plutot que d'en ouvrir un second ;
    * :data:`SUITE_OUVRIR` remet a l'explorateur du bureau le dossier ou les
      restes vivent, et **dit** ce qui s'est passe -- y compris qu'aucun
      bureau n'est joignable ici, ce qui est le cas d'un conteneur sans
      affichage. Tolerance nommee d'`EPIC11-ARB-85`, et **la TUI ne se quitte
      pas** ;
    * :data:`SUITE_OUVRIR_PROJET` fait de meme avec le dossier du projet ;
    * :data:`SUITE_RETOUR` depile jusqu'a l'inventaire et le relit ;
    * **tout libelle inconnu** mene a l'ecran qui **NOMME** l'absence.

    **Le defaut que ce dispatcheur ferme** (`MQ-4`/`MQ-5`, audit du parcours
    complet du 2026-09-06, mesure a nouveau le meme jour sur ce module) : les
    deux ecrans etaient construits **sans `sur_suite`**, et
    `EcranResultat.__init__` le dit en toutes lettres -- « Absent, toute suite
    autre que le retour mene a l'ecran "pas encore" ». Au clavier, « Reessayer
    », « Ouvrir le dossier » et « Ouvrir le dossier du projet » tombaient donc
    dans le filet, sur deux ecrans livres et valides. La frontiere qui mesure
    desormais ce fait vit dans `tests/unit/tui/test_couverture_des_suites.py`,
    et le parcours reel dans `test_suites_de_la_suppression.py`.

    **Ce que cette fonction n'ecrit jamais elle-meme** : rien. Le seul chemin
    d'ecriture reste :func:`executer_la_suppression`, et la frontiere negative
    de l'AC 4.1 mesure qu'aucun `unlink`, `rmtree` ni `remove` n'est appele
    dans ce module.
    """
    if suite == SUITE_REESSAYER:
        reessayer_la_suppression(app, plan, issue,
                                 retirer_du_projet=retirer_du_projet)
        return
    if suite == SUITE_OUVRIR:
        ouvrir_le_dossier_des_restes(app, plan, rapport)
        return
    if suite == SUITE_OUVRIR_PROJET:
        ouvrir_le_dossier_du_projet(app, plan)
        return
    if suite == SUITE_RETOUR:
        remonter_a_l_inventaire(app, plan)
        return
    application = _application_montee(app)
    if application is not None:
        application.descendre(EcranPasEncore(suite,
                                             QUAND_LA_GESTION_DES_MEDIAS))


def _choisir_par_le_parcours(ecran: EcranResultat) -> str:
    """La suite sous le curseur passe TOUJOURS par le parcours, retour compris.

    **Pourquoi `EcranResultat.choisir` ne suffit pas ici.** Il intercepte sa
    propre `RETOUR` **avant** de consulter `_sur_suite`, et la mene a
    `revenir_aux_ateliers()`. Les deux ecrans de suppression surchargent bien
    le LIBELLE (`RETOUR = SUITE_RETOUR`, « Retour a l'inventaire ») mais la
    surcharge d'un libelle ne change pas une destination : l'operateur lisait
    « inventaire » et atterrissait au menu des ateliers, deux stations plus
    haut.

    Sans parcours cable, on retombe sur le comportement de la base -- c'est le
    regime d'un banc qui monte l'ecran seul, et il garde ainsi sa sortie.
    """
    suite = ecran.suites[ecran.curseur]
    if ecran._sur_suite is None:
        return EcranResultat.choisir(ecran)
    ecran._sur_suite(suite)
    return suite


def _echapper_par_le_parcours(ecran: EcranResultat, evenement) -> bool:
    """`Echap` tient la promesse de sa LIGNE DE RACCOURCIS : l'inventaire.

    **Le meme defaut que `SUITE_RETOUR`, par l'autre touche, et il aurait ete
    trouve au clavier d'Egan.** :data:`RACCOURCIS_RESULTAT` annonce
    « Échap inventaire » -- c'est le verbatim des maquettes `E6-3` et `E6-3b` --
    et `EcranResultat.on_key` traite `escape` par `revenir_aux_ateliers()`,
    deux stations plus haut. Une touche annoncee qui mene ailleurs que la ou
    elle le dit se lit comme une panne, exactement comme une touche annoncee
    qui ne fait rien (`EPIC11-ARB-58`).

    On passe par le parcours plutot que par un second appel a
    :func:`remonter_a_l_inventaire` : `Echap` et la suite `Retour` sont **le
    meme geste**, et deux redactions de la meme destination divergeraient au
    premier ajustement -- c'est ce que la coque appelle « une quatrieme
    redaction de la meme regle ».

    **`prevent_default()` et JAMAIS un `super().on_key()`**, et cette ligne a
    ete payee : `textual` dispatche un evenement a **tous** les `on_key` de la
    MRO, pas seulement au plus derive. Appeler la base depuis la surcharge la
    faisait donc jouer DEUX fois -- mesure du 2026-09-06, `↓` sautait deux
    suites et deux bancs de ce fichier sont passes au rouge. `prevent_default`
    est ce qui rompt cette boucle (`_get_dispatch_methods` sort sur
    `message._no_default_action`) ; `stop()`, lui, ne fait qu'empecher la
    remontee vers l'application, ce qui est un autre besoin.

    Rend vrai quand la touche a ete consommee ici. Sans parcours cable on rend
    faux **sans rien empecher**, et la base garde alors sa sortie -- c'est le
    regime d'un ecran monte seul en banc.
    """
    if evenement.key != "escape" or ecran._sur_suite is None:
        return False
    evenement.stop()
    evenement.prevent_default()
    ecran._sur_suite(ecran.RETOUR)
    return True


def suite_de_la_suppression(app, plan: PlanDeSuppression, issue: Issue, *,
                            retirer_du_projet=remove_project_element) -> bool:
    """Ce que le parcours fait de l'issue retenue. Rend vrai s'il a ECRIT.

    **`sur_issue` n'est pas un cul-de-sac** (finding `K3`, paye quatre fois
    dans cet epic) : un point de jugement qui rend son issue a une lambda vide
    est un ecran qui demande une decision et la jette.

    Les trois sorties :

    * `Annuler` -> on remonte, et **rien n'est appele** -- pas meme un dry-run ;
    * l'ecriture aboutit -> `E6-3b`, qui CONFIRME le poids libere. C'est le
      seul endroit du produit qui puisse le faire : la confirmation ne
      pouvait que le promettre, et entre les deux il y a eu une ecriture ;
    * il RESTE des fichiers -> `E6-3`, qui les nomme. C'est la fuite que la
      story existe pour fermer, et elle ne se tait pas.

    **Les deux comptes rendus partent CABLES** (`MQ-4`/`MQ-5`, 2026-09-06) :
    `issue` voyage jusqu'a leur rappel de suites, parce que « Reessayer » la
    rejoue avec exactement les consentements que l'operateur a valides.
    """
    application = _application_montee(app)
    if not issue.ecrit:
        if application is not None:
            application.action_remonter()
        return False
    if application is None:
        # **Aucune application montee : rien a faire voir, rien a differer.**
        # C'est le regime des appelants qui n'ont pas d'ecran -- le coeur est
        # appele ici meme, comme avant.
        executer_la_suppression(plan, issue,
                                retirer_du_projet=retirer_du_projet)
        return True

    # **`E6-2c` se monte, et il ne se montait PAS.** L'ecran d'ecriture en
    # cours etait ecrit, complet et valide par sa maquette, et pourtant
    # ORPHELIN : cette fonction appelait le coeur puis empilait son compte
    # rendu, si bien que l'operateur passait de la confirmation au resultat
    # sans jamais rien voir. Sur un lot de plusieurs gigaoctets, c'est une
    # interface figee pendant toute la suppression -- le defaut qu'Egan a
    # signale sur les autres ateliers, ici par l'autre bout.
    ecran = EcranSuppressionEnCours(plan)
    application.descendre(ecran)

    def conclure(rapport) -> None:
        """Ce que la boucle fait du rapport, **en un seul passage**.

        Deux passages laisseraient la boucle libre entre eux avec `E6-2c`
        encore au sommet et la passe deja finie -- c'est le finding `F1` de la
        vague 4, ferme ici par construction plutot que par attention.

        **Le drapeau tombe D'ABORD**, et l'ordre est celui des quatre autres
        ateliers : oublier, puis conclure. Aucun ecran ne l'eteindrait a notre
        place ici -- `E6-2c` est un `Palier` et non un `EcranExecution`, donc
        il n'a pas le filet d'`on_unmount` --, et un drapeau laisse allume tue
        l'atelier pour la session : `Echap` cesse de depiler, `q` ne quitte
        plus.
        """
        application.oublier_la_tache()
        if rapport is None:
            application.action_remonter()
            return
        #: **Les deux comptes rendus s'excluent une seule fois**, dans
        #: :func:`monter_le_compte_rendu`, qui pose aussi leur rappel de
        #: suites -- sans quoi « Reessayer », « Ouvrir le dossier » et
        #: « Ouvrir le dossier du projet » tombent dans le filet « pas
        #: encore » (`MQ-4`/`MQ-5`).
        #
        # Le compte rendu se monte PAR-DESSUS `E6-2c`, qui est `TRANSITOIRE` :
        # la remontee le saute, exactement comme `E5-5` par-dessus `E5-4`.
        application.descendre(monter_le_compte_rendu(
            application, plan, rapport, issue,
            retirer_du_projet=retirer_du_projet))

    def passe() -> None:
        """Le coeur, **au fil de travail**.

        `remove_project_element` ne publie aucun canal de progression -- c'est
        ce que le docstring de `E6-2c` mesure, et c'est pourquoi l'ecran porte
        un rotor et non une barre. Le fil ne sert donc pas a faire avancer un
        compte : il sert a **rendre la boucle a `textual`**, sans quoi le rotor
        ne tourne pas et l'ecran n'est jamais peint.
        """
        try:
            rapport = executer_la_suppression(
                plan, issue, retirer_du_projet=retirer_du_projet)
        except BaseException:
            # Le drapeau tombe ici, puisque `conclure` ne sera pas atteinte --
            # sans quoi l'atelier reste attache pour la session. L'exception
            # continue son chemin, elle n'est pas avalee.
            application.call_from_thread(application.oublier_la_tache)
            raise
        application.call_from_thread(conclure, rapport)

    # **Le drapeau se pose AVANT le fil**, jamais dans le fil : entre le
    # `run_worker` et la premiere ligne du fil, la boucle tourne, et un `Echap`
    # qui y tomberait depilerait `E6-2c` sous l'ecriture.
    application.tache_en_cours = True
    # **Et le fil ne part qu'APRES le dessin.** `descendre` empile l'ecran,
    # mais `Mount` est distribue par la boucle : un fil parti dans la foulee
    # peindrait au mieux apres coup, et au pire jamais.
    _lancer_apres_le_dessin(application, lambda: application.run_worker(
        passe, thread=True, name="projet-suppression",
        description="supprimer un element de projet"))
    # **Rend vrai des que l'ecriture est LANCEE**, et non plus terminee : le
    # rapport n'existe pas encore quand cette fonction rend la main. C'est le
    # prix de l'ecran vivant, et c'est ce qui change pour un appelant.
    return True


def _ouvrir_la_suppression_du_groupe(application, noeud: NoeudAffiche, *,
                                     projet, lot_id: str | None,
                                     retirer_le_groupe) -> bool:
    """`Suppr` sur une ligne de GROUPE : N cibles, un cartouche.

    **Ce chemin remplace un refus** (`EPIC11-ARB-264`, retour terrain d'Egan du
    2026-09-06 : « planches (l'ensemble) et masters (l'ensemble d'un lot) ne
    sont pas selectionnables »). L'ecran disait
    `MOTIF_DU_GROUPE_NON_SUPPRIMABLE` et rendait la main ; il ouvre desormais
    la meme confirmation que pour un objet, sur un plan agrege.

    **Aucun ecran neuf** (`EPIC11-ARB-144`) : `E6-2` accueille un total et une
    liste de dossiers sans qu'un trait change, et c'est exactement ce qu'un
    groupe produit. Le detail ligne par ligne voyage sur le plan
    (`apercu_du_groupe`) sans etre dessine -- il attend sa maquette.

    **DEUX sorties, et le compte est desormais juste** (finding `C1-3`). Ce
    paragraphe annoncait « les memes QUATRE sorties que le chemin d'un objet »
    puis en listait trois, et il n'y en a que deux :

    * **aucun membre visable** -> un ecran de REFUS qui NOMME les membres et
      pourquoi (:data:`PHRASE_GROUPE_SANS_CIBLE`) ;
    * **au moins un membre visable** -> `E6-2`, dont le cartouche porte le bloc
      des ECARTES quand une partie du groupe ne partira pas.

    Le chemin d'un objet en a quatre parce qu'il distingue « le produit ne sait
    pas viser cette nature » de « cet objet-la n'est pas visable » et qu'il peut
    voir le coeur refuser SA cible unique. Un groupe ne fait ni l'un ni
    l'autre : ses membres non visables ne l'empechent pas d'avancer, et le refus
    d'une de ses N cibles n'est pas un refus du groupe -- c'est une ligne du
    rapport, et elle se lit sur `E6-2` puis sur `E6-3`.

    **Le `except ProjectMaintenanceError` ci-dessous est GARDE, et ce qu'il
    couvre est dit plutot que suppose** (finding `C1-3`, tolerance documentee,
    tranchee le 2026-09-07 apres mesure).

    Il est inatteignable par le coeur REEL : `remove_project_group` ne leve
    que sur une liste de cibles VIDE (« la liste de cibles est vide, il n'y a
    rien a supprimer »), cas que le `if not cibles` ci-dessus a deja renvoye une
    ligne plus haut ; et les refus de LIGNE ne remontent jamais -- la boucle du
    coeur les range dans le rapport, un par un, ce qui est tout le sujet
    d'`EPIC11-ARB-264`.

    Il n'est pas mort pour autant, et c'est ce qui a tranche : `retirer_le_groupe`
    est un point d'INJECTION, et
    `test_le_refus_du_COEUR_sur_un_groupe_monte_le_meme_ecran_de_REFUS` y passe
    un double qui leve. Le retirer transformait ce refus en trace de pile --
    c'est-a-dire un blocage sec, ce qu'`EPIC11-ARB-89` interdit --, et la
    mesure l'a montre : le banc est passe au rouge a la seconde ou la branche a
    disparu. Une premiere redaction de ce paragraphe annoncait le retrait ; elle
    est **retractee**, la branche couvre la seule chose qu'un `except` puisse
    couvrir ici, une implantation du coeur autre que celle d'aujourd'hui.
    """
    cibles, non_visables = cibles_du_groupe(noeud, lot_id)
    if not cibles:
        # **Le refus NOMME ce qui bloque**, membre par membre. « Ce groupe ne
        # peut pas etre supprime » ne dirait pas quoi cocher a la place.
        raisons = ", ".join(non_visables) or OBJET_SANS_NOM
        application.descendre(refus_de_la_suppression(
            CODE_GROUPE_SANS_CIBLE,
            PHRASE_GROUPE_SANS_CIBLE.format(
                cardinal=len(noeud.enfants), objet=noeud.nom,
                raisons=raisons)))
        return True
    try:
        plan = preparer_la_suppression_du_groupe(
            projet, cibles, libelle_du_groupe(noeud, len(cibles)),
            ecartes=ecartes_du_groupe(noeud, lot_id),
            **({"retirer_le_groupe": retirer_le_groupe}
               if retirer_le_groupe is not None else {}))
    except ProjectMaintenanceError as refus:
        application.descendre(refus_de_la_suppression(
            code_du_refus(refus), str(refus), suites_du_refus(noeud)))
        return True
    ecran = EcranSuppressionConfirmation(plan, sur_issue=lambda issue: None)
    # Le rappel se pose APRES construction, comme sur le chemin d'un objet : un
    # ecran ne peut pas se citer dans son propre appel de construction.
    ecran._sur_issue = lambda issue: suite_de_la_suppression(ecran, plan, issue)
    application.descendre(ecran)
    return True


def ouvrir_la_suppression(app, noeud: NoeudAffiche, *, projet,
                          lot_id: str | None = None,
                          retirer_du_projet=remove_project_element,
                          retirer_le_groupe=None) -> bool:
    """`Suppr` depuis l'inventaire : preparer, puis monter le point de jugement.

    Rend faux quand rien n'a ete monte -- l'appelant sait alors que le geste
    n'a pas abouti, plutot que de le supposer.

    **QUATRE sorties, et aucune n'est un blocage sec** (`EPIC11-ARB-89`). La
    quatrieme est la correction d'`EPIC11-ARB-260` : les deux premieres etaient
    fondues, et la fusion faisait annoncer un ecran qui manque sur des objets
    que le coeur sait parfaitement supprimer.

    * **le PRODUIT ne sait pas viser cette nature**
      (:data:`NATURES_SANS_CIBLE_FINE`) -> `EcranPasEncore`, qui NOMME le
      manque. C'est le seul des quatre cas ou « pas encore » est vrai : il
      manque un mot-cle a `remove_project_element`. **La table est vide depuis
      le 2026-09-07** -- `frames_extraites` en etait la seule entree et le
      coeur la porte desormais --, donc ce chemin ne sert plus aucune nature
      livree ; il reste cable parce que la prochaine nature sans cible fine
      doit trouver une sortie nommee plutot qu'un mur ;
    * **cet OBJET-la n'est pas visable** -- il ne vit sous aucun lot, ou son
      nom ne nomme aucun profil connu -> un ecran de REFUS qui dit lequel des
      deux. « Cet ecran n'existe pas encore » y etait faux dans les deux sens :
      l'ecran existe, et rien n'arrivera qui change ce fait-la ;
    * **le coeur refuse la cible** (`ProjectMaintenanceError`) -> un ecran de
      REFUS portant le message du coeur verbatim et, quand elle se lit de
      l'arbre, l'issue nommee (:func:`suites_du_refus`) ;
    * la cible est bonne -> `E6-2`.
    """
    application = _application_montee(app)
    if application is None:
        return False
    if noeud.groupe:
        return _ouvrir_la_suppression_du_groupe(
            application, noeud, projet=projet, lot_id=lot_id,
            retirer_le_groupe=retirer_le_groupe)
    cible = cible_du_noeud(noeud, lot_id)
    if cible is None:
        motif = motif_sans_cible(noeud, lot_id)
        if motif is None:
            nature = NATURES_SANS_CIBLE_FINE.get(noeud.nature, noeud.nature)
            # **Sans echeance** (`EPIC11-ARB-260`) : ce qui manque est un
            # mot-cle du coeur, pas un dessin, et l'annoncer « avec les ecrans
            # de gestion des medias » le promettait a un operateur qui est
            # deja dedans.
            application.descendre(EcranPasEncore(
                CE_QUI_MANQUE_A_LA_CIBLE_FINE.format(nature=nature)))
            return True
        code, phrase = motif
        application.descendre(refus_de_la_suppression(code, phrase))
        return True
    try:
        plan = preparer_la_suppression(projet, cible,
                                       libelle_de_la_cible(noeud),
                                       retirer_du_projet=retirer_du_projet)
    except ProjectMaintenanceError as refus:
        application.descendre(refus_de_la_suppression(
            code_du_refus(refus), str(refus), suites_du_refus(noeud)))
        return True
    ecran = EcranSuppressionConfirmation(plan, sur_issue=lambda issue: None)
    # Le rappel se pose APRES construction : il a besoin de l'ecran lui-meme
    # pour retrouver l'application montee, et un ecran ne peut pas se citer
    # dans son propre appel de construction.
    ecran._sur_issue = lambda issue: suite_de_la_suppression(
        ecran, plan, issue, retirer_du_projet=retirer_du_projet)
    application.descendre(ecran)
    return True


def cabler_la_suppression(ecran_inventaire, arbre, projet, *,
                          retirer_du_projet=remove_project_element):
    """Le rappel que `EcranInventaireDuProjet(arbre, supprimer=...)` attend.

    Il est fabrique ici plutot que dans l'ecran d'inventaire : c'est ce module
    qui sait ce qu'une suppression demande, et l'inventaire n'a pas a le
    savoir. La filiation, elle, est lue de l'arbre par :func:`lot_ancetre`.

    **DEUX lectures de la filiation, et la seconde ne sert que les orphelins**
    (`EPIC11-ARB-260`). :func:`lot_ancetre` lit la POSITION dans l'arbre, et
    c'est la bonne lecture pour tout objet greffe. Un master qui ne se greffe
    sur rien vit a la racine : sa position ne dit plus rien, et
    :func:`lot_de_rattachement` retrouve alors son lot par egalite avec un
    `lot_id` declare. L'ordre n'est pas commutatif -- la position prime, parce
    qu'elle est un fait de l'arbre la ou l'autre est une lecture de nom.
    """
    def supprimer(noeud: NoeudAffiche) -> bool:
        lot_id = lot_ancetre(arbre, noeud)
        if lot_id is None:
            lot_id = lot_de_rattachement(arbre, noeud)
        return ouvrir_la_suppression(
            ecran_inventaire, noeud, projet=projet, lot_id=lot_id,
            retirer_du_projet=retirer_du_projet)

    return supprimer


def _replie(texte: str, ascii_seul: bool) -> str:
    return jetons.replier_ascii(texte) if ascii_seul else texte


__all__ = [
    "CE_QUI_MANQUE_A_LA_CIBLE_FINE",
    "CODE_MASTER_ILLISIBLE",
    "CODE_SANS_LOT",
    "MOT_DES_LOTS",
    "OBJET_SANS_NOM",
    "PHRASE_DES_LOTS_D_ABORD",
    "PHRASE_MASTER_ILLISIBLE",
    "PHRASE_SANS_LOT",
    "CLE_ANNULER",
    "CLE_SUPPRIMER",
    "CLE_SUPPRIMER_AVEC_SCANS",
    "CLE_SUPPRIMER_ET_LIBERER",
    "EcranResultatDeSuppression",
    "EcranReussiteDeSuppression",
    "EcranSuppressionConfirmation",
    "EcranSuppressionEnCours",
    "ETAT_ANNEXE_ABSENTE",
    "GroupeEmporte",
    "LIBELLE_ANNULER",
    "LIBELLE_SUPPRIMER",
    "LIBELLE_SUPPRIMER_AVEC_SCANS",
    "LIBELLE_SUPPRIMER_ET_LIBERER",
    "MANIFESTE_A_JOUR",
    "MOTIF_DES_RESTES",
    "MOT_DE_LA_SUPPRESSION",
    "NATURES_SANS_CIBLE_FINE",
    "ProfilDuMaster",
    "PHRASE_DERNIER_LOT",
    "PHRASE_ECRITURE_EN_COURS",
    "PHRASE_RIEN_ECRIT",
    "PlanDeSuppression",
    "RACCOURCIS_CONFIRMATION",
    "RACCOURCIS_EN_COURS",
    "RACCOURCIS_RESULTAT",
    "SUITE_OUVRIR_PROJET",
    "TITRE_REUSSITE",
    "LIBELLE_RANG_LIBERE",
    "panneau_de_la_reussite",
    "lignes_de_la_reussite",
    "ligne_d_etat_de_la_reussite",
    "SUITE_OUVRIR",
    "SUITE_REESSAYER",
    "SUITE_RETOUR",
    "TITRE_A_SUPPRIMER",
    "TITRE_EN_COURS",
    "TITRE_INCOMPLETE",
    "cabler_la_suppression",
    "cible_du_noeud",
    "identifiant_du_noeud",
    "executer_la_suppression",
    "groupes_emportes",
    "issues_de_la_suppression",
    "libelle_de_la_cible",
    "lot_ancetre",
    "lot_de_rattachement",
    "lots_declares",
    "motif_sans_cible",
    "refus_de_la_suppression",
    "suites_du_refus",
    "ligne_d_etat_de_la_confirmation",
    "ligne_d_etat_du_resultat",
    "lignes_des_emportes",
    "lignes_des_restes",
    "mots_cles_de_l_issue",
    "ouvrir_la_suppression",
    "panneau_de_la_confirmation",
    "panneau_du_resultat",
    "partis_du_rapport",
    "poids_des_fichiers",
    "profil_du_master",
    "preparer_la_suppression",
    "suite_de_la_suppression",
    "AUCUN_DOSSIER_A_OUVRIR",
    "AUCUN_PROJET_A_OUVRIR",
    "dossier_des_restes",
    "monter_le_compte_rendu",
    "ouvrir_le_dossier_des_restes",
    "ouvrir_le_dossier_du_projet",
    "reessayer_la_suppression",
    "remonter_a_l_inventaire",
    "remplacer_le_compte_rendu",
    "suivre",
]
