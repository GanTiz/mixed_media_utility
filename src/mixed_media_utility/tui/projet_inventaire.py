# -*- coding: utf-8 -*-
"""`E6-1` -- l'arborescence des objets produits d'un projet (story 11.11, lot B).

**Pourquoi cet ecran existe** (`EPIC11-ARB-155`, Egan le 2026-09-01, verbatim) :
« il manque un ecran pour ca car **rien ne consomme une planche** donc aucun
ecran de liste n'est susceptible de l'afficher ». Les listes de la TUI listent
ce qu'elles vont CONSOMMER -- l'Extraction des rushes, le Pdf des lots. Une
planche produite n'est l'entree d'aucun atelier : sans cet ecran elle est
invisible pour toujours, et un master encode et un scan ingere avec elle.

**Ce module ne parcourt aucun disque et ne compte rien.**
`project_inventory.inventorier_le_projet` rend l'arbre, ses poids et ses
cardinaux, mesures (AC 1.2) ; l'ecran les LIT. Une seconde mesure cote TUI
serait une seconde verite, et elle divergerait au premier ajustement du coeur.

**Ce que cet ecran ajoute, et qui n'est pas dans le coeur : le REGROUPEMENT PAR
NATURE.** `project_inventory` ne produit aucun noeud de regroupement -- un lot
porte directement ses frames, ses masters, ses planches et ses scans. Les
maquettes `E6-1` et `E6-1e` posent au contraire un niveau de GROUPE entre le lot
et ses objets (`planches — 2 planches`), tranche par `EPIC11-ARB-210` sur la
note d'Egan du 2026-09-03 : « Quand on deplie on voit le detail par dossier ».
Ce niveau est donc de l'AFFICHAGE, et il vit ici.

**Un ecart nomme plutot que tu** : le regroupement REORDONNE les enfants d'un
lot. `_enfants_du_lot` les pose frames, masters, planches ; les maquettes les
montrent frames, planches, masters, scans. L'ordre du manifeste est preserve
**a l'interieur** d'une nature -- ce qui est la seule chose que l'invariant du
coeur protege (« l'ordre est celui du manifeste, que le tri detruirait ») --,
et l'ordre DES natures est celui de :data:`ORDRE_DES_GROUPES`, lu de la
maquette.

**Ce module n'importe jamais `cli`** (`EPIC11-ARB-67`) : son point d'entree de
coeur est `project_inventory.inventorier_le_projet`, et la frontiere de
`tests/unit/tui/test_frontiere_cli.py` balaye tout `tui/` sans qu'on ait rien a
declarer.
"""
from __future__ import annotations

import re

from dataclasses import dataclass, field
from typing import Callable, Iterator, Sequence

from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Static

from ..io import naming, version_ranks
from ..project_inventory import (ETAT_DECLARE_ABSENT, ETAT_NON_DECLARE,
                                 ETAT_PRESENT, NATURE_FRAMES_EXTRAITES,
                                 NATURE_FRAMES_SCANNEES,
                                 NATURE_LOT, NATURE_LOT_SCANNE, NATURE_MASTER,
                                 NATURE_PLANCHE, NATURE_RUSH, NATURE_SCAN,
                                 InventaireDuProjet, InventaireError,
                                 ObjetInventorie,
                                 inventorier_le_projet,
                                 libelles_de_nature)
from . import jetons, projet_lecture
from .atelier_extraction import Composition, _application_montee
from .coque import EcranPasEncore, ObjetTravaille, Palier
from .execution import EcranRefus
from .explorateur import taille_lisible

# ---------------------------------------------------------------------------
# La geometrie, RELEVEE sur les maquettes et jamais choisie
# ---------------------------------------------------------------------------

#: Colonnes de tete : trois blancs, le curseur, un blanc. C'est
#: `_gen_a.TETE_ARBRE`, et c'est la meme tete que toutes les listes du depot.
TETE_ARBRE = 5

#: Largeur de la colonne des noms, marque de pliage et case comprises.
NOM_ARBRE = 46

#: Largeur de la colonne des cardinaux (`2 lots · 445 f.`, `124 f.`, `4 pages`).
#: **Dix-sept et pas seize** : `3 lots · 1 204 f.` d'`E6-1c` en fait exactement
#: dix-sept, et c'est la ligne la plus longue que les maquettes portent.
FICHIERS_ARBRE = 17

#: Largeur de la colonne des poids (`8,1 Go`, `770 Mo`, `·`).
POIDS_ARBRE = 8

#: **La profondeur du niveau OBJET** (`EPIC11-ARB-210`). Quatre niveaux :
#: rush (0) -> lot (1) -> groupe (2) -> objet (3). Un objet est TERMINAL par
#: defaut : il porte le glyphe de rattachement et perd les deux colonnes de
#: marque de pliage, que rien a ce niveau n'emploie.
PROFONDEUR_OBJET = 3

#: Hauteur de la zone d'arbre, **derivee** de la grille : la zone centrale
#: vaut :func:`jetons.hauteur_centrale`, dont le titre du projet et ses deux
#: respirations prennent trois lignes.
#:
#: **Elle n'est pas recopiee de la maquette, et l'ecart est nomme.** `E6-1c`
#: dessine une fenetre de douze lignes suivie de deux blancs ; le budget
#: derive en rend quatorze, donc deux rushes de plus et aucun blanc de queue.
#: Recopier douze aurait fige une place perdue le jour ou la grille change.
HAUTEUR_ARBRE = jetons.hauteur_centrale() - 3

#: Le trait de separation d'`E6-1a`, aux colonnes de la maquette : trois blancs
#: puis le trait sur ce qui reste, moins la marge symetrique.
_MARGE_DE_LA_REGLE = 4

# ---------------------------------------------------------------------------
# Le VOCABULAIRE des groupes -- lu du coeur quand le coeur l'a (AC 2.4, 2.6)
# ---------------------------------------------------------------------------

#: Les natures qui forment un groupe, **dans l'ordre d'affichage des maquettes**
#: (`E6-1`, `E6-1e`) : frames, planches, masters, scans, et le lot scanne dont
#: aucun scan n'est connu.
#:
#: **Ce n'est PAS l'ordre du coeur**, et c'est dit plutot que tu :
#: `_enfants_du_lot` pose frames, masters, planches. Voir le docstring du
#: module.
ORDRE_DES_GROUPES: tuple[str, ...] = (
    NATURE_FRAMES_EXTRAITES,
    NATURE_PLANCHE,
    NATURE_MASTER,
    NATURE_SCAN,
    NATURE_LOT_SCANNE,
    # **Elle ne pend d'aucun lot, et elle est quand meme ici** : le coeur ne la
    # rend jamais comme enfant d'un lot -- elle vit sous un lot scanne, qui
    # l'absorbe dans son libelle -- mais `_orphelins` en produit une des qu'un
    # dossier `frames-scannees/<slug>/` n'est declare par personne. Sans cette
    # entree, cette nature-la sortirait en queue de table avec un libelle
    # derive, et un dossier d'images resterait mal nomme au lieu d'etre
    # invisible : c'est mieux, ce n'est pas assez.
    NATURE_FRAMES_SCANNEES,
)

#: Les natures dont le nom de groupe et le mot de contenu se LISENT du coeur
#: (`project_inventory.libelles_de_nature`) : les trois pour lesquelles le mot
#: du coeur et celui de la maquette coincident deja.
NATURES_AU_LIBELLE_DU_COEUR: tuple[str, ...] = (
    NATURE_PLANCHE, NATURE_MASTER, NATURE_SCAN)

#: Les deux natures dont le coeur **ne peut pas** rendre le mot des maquettes,
#: declarees ici avec leur motif : `(nom du groupe, contenu au singulier,
#: contenu au pluriel)`.
#:
#: `project_inventory._libelles` DERIVE le singulier de l'identifiant : la
#: nature `frames_extraites` rend « frames extraites » et `lot_scanne` rend
#: « lot scanne », sans accent, parce qu'un identifiant Python n'en porte pas.
#: `E6-1` et `E6-1e` ecrivent « frames » et « lot scanné ».
#:
#: **Le nom du groupe et le mot du contenu ne coincident PAS ici**, et c'est ce
#: qui interdit de les deriver l'un de l'autre : le groupe des frames se nomme
#: au pluriel (`frames — 124 frames`), celui du lot scanne au SINGULIER et son
#: contenu se compte dans une autre unite encore (`lot scanné — 124 frames
#: scannées`). Un lot ne porte qu'un lot scanne -- `output_frames_dir` est
#: singulier au manifeste --, donc compter des lots scannes n'aurait rien dit.
#:
#: **Le generateur des maquettes fait exactement le meme geste** et dit
#: pourquoi : « Seules les MAQUETTES le portent aujourd'hui. Le renommage des
#: dossiers, des commandes et de leurs arguments [...] est une story qu'Egan
#: demande lui-meme au debut d'une vague. » Ces deux entrees sont donc une
#: DETTE nommee, pas une seconde redaction du vocabulaire : le jour ou le coeur
#: porte le mot accentue, la frontiere qui mesure la partition rougit et la
#: table se vide.
GROUPES_DECLARES: dict[str, tuple[str, str, str]] = {
    NATURE_FRAMES_EXTRAITES: ("frames", "frame", "frames"),
    NATURE_LOT_SCANNE: ("lot scanné", "frame scannée", "frames scannées"),
    NATURE_FRAMES_SCANNEES: ("frames scannées", "frame scannée",
                             "frames scannées"),
}

#: Un scan se compte en **pages**, jamais en fichiers : « Un scan compte pour
#: UN, jamais par page » (exigence d'Egan portee par `E6-1`), et la colonne de
#: cardinal porte donc les pages qui font la somme du lot.
UNITE_DES_PAGES = "pages"
UNITE_DE_LA_PAGE = "page"

#: L'unite ordinaire de la colonne de cardinal : `62 f.`, abregee parce que la
#: colonne vaut dix-sept colonnes et que `2 lots · 491 fichiers` n'y tient pas.
UNITE_DES_FICHIERS = "f."

#: La mention qu'un objet trouve sur le disque et declare par aucun manifeste
#: porte a la suite de son nom (`E6-1`, `E6-1c`, `E6-1d`).
MENTION_NON_DECLARE = "non déclaré"

#: Ce que la ligne d'etat dit quand le curseur porte un objet declare au
#: manifeste et absent du disque (`E6-1`, `EPIC11-ARB-217` : le contenu de
#: `E6-1b` fondu ici).
ETAT_DE_L_OBJET_ABSENT = "déclaré au manifeste, absent du disque"
ETAT_DU_CHEMIN_ATTENDU = "attendu dans {dossier}"
ETAT_DE_L_OBJET_NON_DECLARE = "trouvé sur le disque, déclaré par aucun manifeste"

#: Le mot des ecarts en ligne d'etat. Un ecart est un objet dont l'etat n'est
#: pas :data:`ETAT_PRESENT` -- les deux familles a la fois, comme
#: `EPIC11-ARB-217` les a fondues.
MOT_DES_ECARTS = {False: "écart", True: "écarts"}

# ---------------------------------------------------------------------------
# Les marques de pliage (`EPIC11-ARB-200`)
# ---------------------------------------------------------------------------

#: **Elles ne sont PAS dans `jetons.GLYPHES`, et c'est mesure plutot que subi.**
#: `-` y est deja le repli ASCII de `barre-vide`, si bien qu'y verser la marque
#: de pliage telle quelle casserait l'injectivite de `GLYPHES_ASCII` -- ce que
#: `test_chaque_table_est_injective` mesure. Le generateur des maquettes fait
#: le meme constat et le meme geste.
#:
#: Les deux dessins sont de l'ASCII pur : leur repli est eux-memes, donc cette
#: table n'a pas de jumelle `_ASCII` et le second canal de `DESIGN.md` section 6
#: n'est pas en cause -- une marque de pliage n'est pas un ETAT.
PLIAGE_REPLIE = "+"
PLIAGE_DEPLIE = "-"

# ---------------------------------------------------------------------------
# Les textes de l'ecran
# ---------------------------------------------------------------------------

#: `E6-1a` -- la lecture en cours. Le rotor est le seul signe honnete que la
#: machine travaille : `inventorier_le_projet` batit son arbre puis rend, sans
#: jalon intermediaire, donc aucun compte reel n'existe (`jetons.ROTOR`).
PHRASE_DE_LECTURE = "lecture du disque"
CORPS_DE_LECTURE = (
    "Le manifeste est lu, puis le disque est parcouru : c'est",
    "l'écart entre les deux qui fait l'intérêt de cet écran, et il",
    "ne se mesure pas sans les deux.",
    "",
    "Sur un projet local la lecture est immédiate. Elle se voit sur",
    "un volume réseau, ou sur plusieurs dizaines de milliers de",
    "fichiers.",
)
ETAT_DE_LA_LECTURE = "lecture en cours — aucune écriture, aucun décompte disponible"

#: `E6-1` -- la ligne de raccourcis, et elle est **CONTEXTUELLE**
#: (`EPIC11-ARB-215`, issue C, tranchee par Egan le 2026-09-04). La barre ne
#: porte que ce qui AGIT sur l'objet sous le curseur ; les gestes de
#: deplacement (`→`, `←`, `Échap`) vivent dans `F1`, ou ils sont deja decrits.
#:
#: **`Ctrl+D` et `Ctrl+L` sont EXCLUSIFS** : on declare ce qui n'est declare
#: nulle part, on relinke ce qui est **deja** declare absent. Les annoncer tous
#: les deux valait 105 colonnes au pire cas reel pour une zone utile de 76 ;
#: l'exclusion est ce qui fait tenir la ligne.
#: MESURE: 70/76 (`Ctrl+D`), 70/76 (`Ctrl+L`) -- les deux libelles font la meme
#: longueur, ce qui est un hasard et non une regle.
RACCOURCIS_INVENTAIRE_DECLARER = ("Espace cocher  Suppr retirer  "
                                  "Ctrl+A ajouter  Ctrl+D déclarer  F1 aide")
RACCOURCIS_INVENTAIRE_RELINKER = ("Espace cocher  Suppr retirer  "
                                  "Ctrl+A ajouter  Ctrl+L relinker  F1 aide")

#: `E6-1a` : **aucune annulation annoncee**, pour le meme motif que `E6-2c` --
#: aucun point d'interruption n'existe dans ce chemin, et « une touche annoncee
#: qui n'agit pas » est le finding `I8`.
#: MESURE: 7/7
RACCOURCIS_LECTURE = "F1 aide"

#: Ce que `Ctrl+A` et `Ctrl+L` demandent quand **aucun appelant n'a cable leur
#: parcours** -- c'est-a-dire hors produit depuis le 2026-09-07.
#:
#: Les deux touches ont desormais leur cablage
#: (`projet_medias.ouvrir_l_ajout_de_media` et
#: `projet_medias.ouvrir_le_relink_du_rush`, injectes par
#: :func:`ouvrir_l_inventaire_du_projet`), et ces deux phrases sont ce que
#: l'ecran repond a un appelant qui construirait l'inventaire sans elles. Meme
#: contrat, meme forme et meme motif que
#: :data:`CE_QUI_MANQUE_A_LA_SUPPRESSION` : un rappel absent se DIT, plutot que
#: de rendre la touche indistinguable d'un clavier casse (finding `K1.1a`).
CE_QUI_MANQUE_A_L_AJOUT = "Ajouter un media au projet depuis le disque"
CE_QUI_MANQUE_AU_RELINK = "Relinker un objet declare dont le fichier a bouge"

#: Ce que `Ctrl+D` demande, et **ce qui manque REELLEMENT pour le servir**.
#:
#: **La phrase precedente mentait a qui la lisait, et c'est le meme defaut que
#: le 2026-09-06 a deja paye deux fois** (`EPIC11-ARB-260`, puis le lot C sur
#: `ProjectMaintenanceError`). Elle disait « Declarer au manifeste un objet
#: trouve sur le disque », et l'echeance ajoutait « il arrive avec les ecrans
#: de gestion des medias du palier Projet » -- annoncee a un operateur qui **est
#: dans ces ecrans**, puisqu'il vient d'y frapper `Ctrl+D`. Une echeance qui
#: nomme l'endroit d'ou l'on frappe est pire qu'une absence d'echeance : elle
#: fait attendre quelque chose qui est deja la.
#:
#: **Ce qui manque n'est pas un dessin, c'est un point d'entree de COEUR**, et
#: la mesure le dit (2026-09-07) : `project_maintenance` ne porte que
#: `remove_project_element`, `project_inventory` ne fait que LIRE, et les deux
#: seules sous-commandes de `mmu project` sont `remove` et `add-rush` --
#: laquelle declare un rush **depuis un fichier video**, elle ne recolle pas un
#: objet orphelin trouve sur le disque. Aucune fonction du depot n'inscrit au
#: manifeste un objet **deja present**. La dette existait deja
#: (`deferred-work.md`, « Un lot absent du manifeste n'a AUCUNE issue de
#: completion manuelle »), elle n'avait simplement pas de phrase a l'ecran.
#:
#: La phrase le DIT donc elle-meme, et **sans echeance** : c'est le geste
#: qu'`EPIC11-ARB-260` a pose sur `projet_suppression.ouvrir_la_suppression`,
#: pour ce motif exact. Elle se verifie a l'oeil -- le jour ou une commande de
#: coeur sait le faire, cette phrase devient fausse et se voit.
CE_QUI_MANQUE_A_LA_DECLARATION = (
    "Declarer au manifeste un objet deja present sur le disque : aucune "
    "commande du coeur ne sait le faire")

#: L'echeance des filets de gestion des medias qui **attendent encore un
#: ecran**. Depuis le 2026-09-07 il n'en reste qu'un seul dans ce module -- le
#: repli de `Suppr` sans rappel de suppression, hors produit --, `Ctrl+A` et
#: `Ctrl+L` ayant gagne leur cablage (`tui/projet_medias.py`) et `Ctrl+D`
#: n'ayant, lui, aucune echeance a annoncer.
QUAND_LA_GESTION_DES_MEDIAS = "les ecrans de gestion des medias du palier Projet"


class InventaireMalForme(ValueError):
    """Un invariant d'affichage que la revue ne devrait pas avoir a trouver."""


def nom_du_groupe(nature: str) -> str:
    """Le mot qui NOMME un groupe : `planches`, `frames`, `lot scanné`.

    Le pluriel publie par le coeur pour les trois natures ou il porte deja le
    mot de la maquette ; :data:`GROUPES_DECLARES` pour les deux autres. Une
    frontiere mesure la partition **dans les deux sens**, si bien qu'une nature
    qui passerait d'un cote a l'autre sans qu'on le veuille rougit.
    """
    if nature in GROUPES_DECLARES:
        return GROUPES_DECLARES[nature][0]
    return _libelles_ou_identifiant(nature)[1]


def libelles_du_contenu(nature: str) -> tuple[str, str]:
    """Le couple (singulier, pluriel) de ce qu'un groupe CONTIENT.

    Distinct de :func:`nom_du_groupe`, et le distinguo n'est pas cosmetique :
    le groupe du lot scanne se nomme au singulier et compte des frames
    scannees. Deriver l'un de l'autre rendrait `lot scanné — 124 lots scannés`.
    """
    if nature in GROUPES_DECLARES:
        return GROUPES_DECLARES[nature][1:]
    return _libelles_ou_identifiant(nature)


def _libelles_ou_identifiant(nature: str) -> tuple[str, str]:
    """Les libelles du coeur, ou l'IDENTIFIANT NU quand il n'en publie pas.

    **Sans ce repli, une nature inconnue ne disparaissait pas : elle faisait
    tomber l'ecran entier.** `libelles_de_nature` leve le `KeyError` ordinaire
    de sa table, et il a raison de le faire -- « ce module ne LEVE que ses
    quatre refus propres », dit sa docstring, et un cinquieme refus serait un
    refus non publie. C'est donc a l'ecran de tenir le cas, et
    :func:`_groupes_du_lot` PROMET deja qu'il le tient : « une nature inconnue
    de la table n'est jamais avalee : elle est posee en queue ». La promesse
    etait vraie du RANGEMENT et fausse du LIBELLE, et un `KeyError` remonte
    plus loin qu'un objet avale -- le lot, le rush et l'arbre entier tombent
    avec lui.

    Trouve en ecrivant le banc du mutant `B26` de la couche 1, qui cherchait
    une disparition silencieuse et a rencontre une exception.

    **L'identifiant nu plutot qu'un pluriel derive** : `nature + "s"` est
    exactement le calcul que ce module refuse ailleurs (« un pluriel calcule
    sur un groupe nominal accorde le dernier mot et jamais le premier »).
    Montrer `lot_scanne` est laid et VRAI ; montrer `lot_scannes` serait un mot
    invente. Le jour ou le coeur publie le libelle, ce repli cesse de servir
    sans qu'on ait rien a retirer.
    """
    try:
        return libelles_de_nature(nature)
    except KeyError:
        return nature, nature


def accorder_le_contenu(cardinal: int, nature: str) -> str:
    """`2 planches`, `1 master`, `124 frames scannées`, `0 scan`.

    Le singulier vaut aussi pour zero -- meme regle d'accord que
    `projet_lecture.accorder`, qui ne peut pas servir ici : sa table `PLURIELS`
    est indexee par un mot francais et ne connait ni `frames_extraites` ni
    `lot_scanne`. Le pluriel vient donc du couple publie plutot que d'un
    `+ "s"` -- « un pluriel calcule sur un groupe nominal accorde le dernier
    mot et jamais le premier », defaut deja paye dans `cli.py` (« les jeu de
    framess posterieurs »).
    """
    singulier, pluriel = libelles_du_contenu(nature)
    return f"{grouper_les_milliers(cardinal)} {pluriel if cardinal > 1 else singulier}"


def grouper_les_milliers(valeur: int) -> str:
    """`1204` -> `1 204`, l'espace des milliers que les maquettes ecrivent.

    Une espace ORDINAIRE et non insecable : la grille se mesure en colonnes et
    `jetons.colonnes` compte les deux pareil, mais le repli ASCII ne connait
    pas l'insecable, qui sortirait telle quelle sur un terminal qui ne la
    dessine pas.

    **Seconde redaction assumee et versee a `deferred-work.md`** : la meme
    ligne vit dans `atelier_pdf_versions._grouper`, sous un souligne de tete
    qui dit qu'elle n'avait qu'un appelant. La publier touche un module qui
    n'est pas de cette story ; la recopier est le moindre des deux maux, et
    l'ecart est nomme plutot que tu.
    """
    return f"{valeur:,}".replace(",", " ")


def poids_lisible(octets: int) -> str:
    """Le poids d'un noeud, ou le glyphe NEUTRE quand il est nul.

    **Un poids nul n'est pas `0 o`** : les maquettes posent `·` sur la planche
    declaree-absente comme sur le rush sans lot, et le glyphe neutre dit
    exactement ce qu'il faut -- « non renseigne, sans objet ». Un `0 o` se
    lirait comme un fichier vide, qui est une autre chose.

    Le format vient d'`explorateur.taille_lisible`, la seule recette du depot.

    **Un ecart nomme** : cette recette rend `13 Go` la ou `E6-0` et `E6-1`
    ecrivent `12,7 Go`, sa decimale tombant a partir de dix. Ecrire une seconde
    recette pour une decimale serait la duplication que ce depot paie le plus
    souvent ; c'est donc la maquette qui a raison sur le papier et le code qui
    a une seule verite.
    """
    if octets <= 0:
        return jetons.GLYPHES["neutre"]
    return taille_lisible(octets)


def cardinal_lisible(fichiers: int, nature: str) -> str:
    """`124 f.`, `4 pages` -- le cardinal d'un noeud, dans SON unite.

    Un scan se compte en pages (`E6-1`), tout le reste en fichiers.
    """
    if nature == NATURE_SCAN:
        mot = UNITE_DES_PAGES if fichiers > 1 else UNITE_DE_LA_PAGE
        return f"{grouper_les_milliers(fichiers)} {mot}"
    return f"{grouper_les_milliers(fichiers)} {UNITE_DES_FICHIERS}"


# ---------------------------------------------------------------------------
# Le modele pur : l'arbre d'AFFICHAGE
# ---------------------------------------------------------------------------

@dataclass
class NoeudAffiche:
    """Un noeud de l'arbre tel que l'ECRAN le montre.

    Il double l'`ObjetInventorie` du coeur plutot que de le decorer, et pour
    deux raisons de nature :

    * un noeud de GROUPE (`planches — 2 planches`) n'existe pas au coeur : il
      n'a ni chemin, ni etat propre, et son poids est la somme de ses membres ;
    * le pliage et la coche sont des etats d'ECRAN. Les poser sur un
      `ObjetInventorie`, qui est `frozen`, demanderait de le reconstruire a
      chaque fleche.

    ``cible`` est l'objet du coeur quand ce noeud en designe un, ``None`` sur un
    groupe. C'est lui, et lui seul, qu'une suppression vise : un groupe n'est
    pas un objet du produit, et `remove_project_element` n'a aucune cible qui
    le designe -- ecart connu, nomme par la maquette `E6-1` et par la fiche.
    """

    nature: str
    #: Le nom affiche, mention de groupe comprise (`planches — 2 planches`).
    #: Jamais compose au rendu : la ligne se contente de le poser.
    nom: str
    etat: str
    profondeur: int
    poids: int
    fichiers: int
    #: Le texte de la colonne de cardinal, deja compose (`2 lots · 445 f.`).
    cardinal: str
    #: Ce que ce noeud REMONTE a ses ancetres, qui n'est pas toujours ce que sa
    #: colonne montre. **Un scan est le seul ecart, et il est mesure** : sa
    #: colonne dit ses PAGES (`4 pages`, ses propres images) tandis qu'il
    #: remonte a son lot ses pages ET les frames scannees du lot scanne qu'il
    #: porte. Sans cette distinction, le groupe `scans` d'`E6-1e` afficherait
    #: « 250 pages » -- des frames comptees en pages -- et le total du lot
    #: cesserait de tomber juste (378 f. / 6,7 Go, recomptes a la main dans le
    #: generateur de la maquette). Les deux valeurs sont egales partout
    #: ailleurs.
    poids_porte: int = 0
    fichiers_porte: int = 0
    chemin: str | None = None
    cible: ObjetInventorie | None = None
    enfants: list["NoeudAffiche"] = field(default_factory=list)
    deplie: bool = False
    coche: bool = False
    #: **Surcharge la regle de profondeur** : un scan vit au niveau des objets
    #: et porte pourtant un enfant, donc il se plie. Sans elle il recevrait le
    #: `└─` d'une feuille et perdrait sa marque de pliage (`EPIC11-ARB-244`,
    #: seconde passe).
    terminal: bool | None = None
    #: Un noeud de GROUPE n'est pas un objet : il ne compte pas dans le
    #: « 9 objets » d'une ligne de lot, et il ne se supprime pas.
    groupe: bool = False

    def __post_init__(self) -> None:
        if self.profondeur < 0:
            raise InventaireMalForme(
                f"Profondeur negative sur {self.nom!r} : l'indentation est la "
                "seule chose qui dise la filiation, elle ne se calcule pas a "
                "l'envers.")
        if self.groupe and self.cible is not None:
            raise InventaireMalForme(
                f"{self.nom!r} est declare groupe ET porte un objet du coeur. "
                "Un groupe n'a pas de cible : le supprimer viserait un objet "
                "que le produit ne nomme pas.")

    @property
    def pliable(self) -> bool:
        """Un noeud se plie des qu'il porte un enfant, et jamais sinon."""
        return bool(self.enfants)

    @property
    def est_terminal(self) -> bool:
        """Le niveau OBJET est terminal par defaut ; ``terminal`` surcharge."""
        if self.terminal is not None:
            return self.terminal
        return self.profondeur >= PROFONDEUR_OBJET

    def parcourir(self) -> Iterator["NoeudAffiche"]:
        """Ce noeud puis toute sa descendance, plie ou non."""
        yield self
        for enfant in self.enfants:
            yield from enfant.parcourir()

    def visibles(self) -> Iterator["NoeudAffiche"]:
        """Ce noeud, puis sa descendance **tant qu'il est deplie**."""
        yield self
        if not self.deplie:
            return
        for enfant in self.enfants:
            yield from enfant.visibles()

    @property
    def objets(self) -> int:
        """Le cardinal d'OBJETS sous ce noeud, groupes exclus.

        C'est le « 9 objets » de la ligne de lot d'`E6-1e`, et il se compte sur
        les lignes que l'ECRAN montrerait deplie : les groupes n'en sont pas, et
        les frames scannees d'un lot scanne non plus -- elles sont absorbees
        dans le libelle de leur parent, donc elles n'ont pas de ligne a elles.
        """
        return sum(1 for noeud in self.parcourir()
                   if noeud is not self and not noeud.groupe)


# ---------------------------------------------------------------------------
# La construction de l'arbre d'affichage
# ---------------------------------------------------------------------------

#: Le mot du cardinal d'objets d'une ligne de LOT (`9 objets · 378 f.`). Il ne
#: nomme aucune nature -- c'est le compte de toutes natures confondues --, donc
#: il ne peut pas se lire d'une table de natures.
MOT_DES_OBJETS = {False: "objet", True: "objets"}


def _mention_de_groupe(nature: str, membres: Sequence[NoeudAffiche]) -> str:
    """`planches — 2 planches`, `frames — 124 frames`.

    **Le cardinal d'un groupe et son cardinal de fichiers ne se lisent pas au
    meme endroit**, et le piege est reel : `frames` et le lot scanne sont
    **un seul noeud** portant N fichiers, tandis que masters, planches et scans
    sont **N noeuds**. « 62 frames » se lit dans `fichiers`, « 2 planches »
    dans le cardinal des membres. Deux recettes derriere deux lignes qui se
    ressemblent.
    """
    if nature in GROUPES_DECLARES:
        cardinal = sum(membre.fichiers for membre in membres)
    else:
        cardinal = len(membres)
    return f"{nom_du_groupe(nature)} — {accorder_le_contenu(cardinal, nature)}"


def _nom_affiche(objet: ObjetInventorie) -> str:
    """Le nom d'un objet, **avec sa mention d'ecart** quand il en porte une.

    `ETAT_NON_DECLARE` ajoute ` · non déclaré` (`E6-1`, `E6-1c`, `E6-1d`) ;
    `ETAT_DECLARE_ABSENT` n'ajoute rien -- sa croix, posee au rendu, le dit
    deja, et la ligne d'etat en donne le chemin attendu. Les deux vocabulaires
    sont ceux du coeur : ce module ne connait aucun troisieme etat, et une
    frontiere le mesure.
    """
    if objet.etat == ETAT_NON_DECLARE:
        return f"{objet.nom} · {MENTION_NON_DECLARE}"
    return objet.nom


def _lot_scanne_affiche(objet: ObjetInventorie, profondeur: int) -> NoeudAffiche:
    """Le lot scanne, **absorbe avec son unique enfant** (`E6-1`, `E6-1e`).

    Le coeur lui donne un enfant -- le dossier de frames scannees --, et les
    maquettes ne le montrent jamais : la ligne dit `lot scanné — 124 frames
    scannées`, ce qui EST son enfant. Poser une ligne de plus dessous la
    redirait, et Egan l'a retire lui-meme du libelle du scan pour ce motif
    (« on le lit juste en dessous »).

    Le noeud garde sa `cible` : c'est un OBJET du produit, versionnable et
    supprimable (`EPIC11-ARB-104`), pas un groupe. Il compte donc dans le
    « 9 objets » de son lot.
    """
    fichiers = objet.fichiers_total
    return NoeudAffiche(
        nature=objet.nature,
        nom=f"{nom_du_groupe(objet.nature)} — "
            f"{accorder_le_contenu(fichiers, objet.nature)}",
        etat=objet.etat, profondeur=profondeur,
        poids=objet.poids_total, fichiers=fichiers,
        cardinal=cardinal_lisible(fichiers, objet.nature),
        poids_porte=objet.poids_total, fichiers_porte=fichiers,
        chemin=objet.chemin, cible=objet)


def _frames_extraites_affichees(objet: ObjetInventorie,
                                profondeur: int) -> NoeudAffiche:
    """Le dossier de frames extraites : `frames — 124 frames`, sans enfant.

    **Le nom porte `extraites`, et c'est une frontiere qui l'exige** : un
    nom neuf portant `frame` sans marqueur est **ambigu** au sens de la
    story 11.14 (`EPIC11-ARB-214`), et `test_vocabulaire_des_objets.py` le
    fait rougir plutot que de l'inscrire a son releve -- « un nom NEUF
    portant `frame` sans marqueur, a corriger et non a inscrire ». Il
    s'appelait `_frames_affichees` en arrivant ici, et la premiere course
    large posterieure a la fusion l'a rendu.

    **Il ne se plie pas, et c'est une mesure et non un oubli** : le coeur
    additionne les frames d'un lot et jette leurs chemins
    (`_mesure_du_dossier`), si bien qu'il n'existe aucun objet a montrer
    dessous. C'est aussi la regle produit qu'Egan a posee -- « on ne peut pas
    supprimer une unique frame d'un lot d'images » --, donc un niveau de plus
    ne serait pas seulement invendable, il serait faux.
    """
    fichiers = objet.fichiers_total
    return NoeudAffiche(
        nature=objet.nature,
        nom=f"{nom_du_groupe(objet.nature)} — "
            f"{accorder_le_contenu(fichiers, objet.nature)}",
        etat=objet.etat, profondeur=profondeur,
        poids=objet.poids_total, fichiers=fichiers,
        cardinal=cardinal_lisible(fichiers, objet.nature),
        poids_porte=objet.poids_total, fichiers_porte=fichiers,
        chemin=objet.chemin, cible=objet)


def _objet_affiche(objet: ObjetInventorie, profondeur: int) -> NoeudAffiche:
    """Un objet nomme par SON nom : une planche, un master, un scan.

    « J'avais aussi parle de nommer les objets par leurs noms et cela n'a pas
    ete pris en compte » (Egan, 2026-09-04). Le nom vient du coeur, qui le lit
    d'`io.naming` ou du disque -- **aucun nom n'est compose ici**, et une
    frontiere mesure qu'aucun identifiant de cet ecran n'est une chaine
    litterale (AC 2.6).

    Un scan porte son lot scanne comme enfant (`EPIC11-ARB-244`) et se plie
    donc, bien qu'il vive au niveau des objets : `terminal=False` surcharge la
    regle de profondeur, faute de quoi il recevrait le `└─` d'une feuille.
    """
    enfants = [_lot_scanne_affiche(enfant, profondeur + 1)
               for enfant in objet.enfants
               if enfant.nature == NATURE_LOT_SCANNE]
    #: **La colonne d'un noeud a enfants dit son poids PROPRE**, la remontee
    #: dit le total. Le seul cas reel est le scan : `E6-1e` lui fait dire
    #: « 4 pages · 550 Mo » alors qu'il porte un lot scanne de 1,5 Go. Un
    #: objet sans enfant a les deux egaux, et la ligne est la meme.
    return NoeudAffiche(
        nature=objet.nature, nom=_nom_affiche(objet), etat=objet.etat,
        profondeur=profondeur, poids=objet.poids, fichiers=objet.fichiers,
        cardinal=cardinal_lisible(objet.fichiers, objet.nature),
        poids_porte=objet.poids_total, fichiers_porte=objet.fichiers_total,
        chemin=objet.chemin, cible=objet, enfants=enfants,
        terminal=False if enfants else None)


def _groupes_du_lot(lot: ObjetInventorie, profondeur: int) -> list[NoeudAffiche]:
    """Les groupes d'objets d'un lot, dans l'ordre de :data:`ORDRE_DES_GROUPES`.

    **Le regroupement est de l'AFFICHAGE, pas du coeur** : `project_inventory`
    ne produit aucun noeud de regroupement, et `EPIC11-ARB-210` en exige un
    niveau. L'ordre du manifeste est preserve **a l'interieur** d'une nature ;
    l'ordre DES natures est celui des maquettes.

    **Une nature inconnue de la table n'est jamais avalee** : elle est posee en
    queue, dans son ordre d'apparition. Un enfant que le coeur ajouterait
    demain disparaitrait sinon de l'arbre en silence -- exactement la panne que
    l'AC 1.4 existe pour fermer, un cran plus haut.
    """
    par_nature: dict[str, list[ObjetInventorie]] = {}
    for enfant in lot.enfants:
        par_nature.setdefault(enfant.nature, []).append(enfant)
    ordre = list(ORDRE_DES_GROUPES) + [nature for nature in par_nature
                                       if nature not in ORDRE_DES_GROUPES]
    lignes: list[NoeudAffiche] = []
    for nature in ordre:
        membres = par_nature.get(nature)
        if not membres:
            continue
        if nature == NATURE_FRAMES_EXTRAITES:
            lignes.extend(_frames_extraites_affichees(objet, profondeur)
                          for objet in membres)
            continue
        if nature == NATURE_LOT_SCANNE:
            lignes.extend(_lot_scanne_affiche(objet, profondeur)
                          for objet in membres)
            continue
        objets = [_objet_affiche(objet, profondeur + 1) for objet in membres]
        fichiers = sum(objet.fichiers for objet in objets)
        lignes.append(NoeudAffiche(
            nature=nature, nom=_mention_de_groupe(nature, objets),
            etat=ETAT_PRESENT, profondeur=profondeur,
            poids=sum(objet.poids for objet in objets), fichiers=fichiers,
            cardinal=cardinal_lisible(fichiers, nature),
            poids_porte=sum(objet.poids_porte for objet in objets),
            fichiers_porte=sum(objet.fichiers_porte for objet in objets),
            enfants=objets, groupe=True))
    return lignes


def _lot_affiche(lot: ObjetInventorie, profondeur: int) -> NoeudAffiche:
    """Une ligne de lot : `9 objets · 378 f.` a droite de son nom."""
    groupes = _groupes_du_lot(lot, profondeur + 1)
    noeud = NoeudAffiche(
        nature=lot.nature, nom=_nom_affiche(lot), etat=lot.etat,
        profondeur=profondeur, poids=0, fichiers=0, cardinal="",
        chemin=lot.chemin, cible=lot, enfants=groupes)
    _resommer(noeud)
    return noeud


def _resommer(noeud: NoeudAffiche) -> None:
    """Recalculer ce qu'un noeud de REGROUPEMENT montre et remonte.

    Appelee a la construction, puis **a nouveau apres chaque greffe
    d'orphelin** : un lot qui gagne une version non declaree gagne son poids
    avec, et une ligne de lot qui garderait le total d'avant ferait mentir la
    seule colonne qui dise ce qu'une suppression toucherait.
    """
    noeud.poids_porte = sum(enfant.poids_porte for enfant in noeud.enfants)
    noeud.fichiers_porte = sum(enfant.fichiers_porte for enfant in noeud.enfants)
    if noeud.groupe:
        # **La colonne d'un GROUPE somme les colonnes de ses membres, pas ce
        # qu'ils remontent.** C'est ce qui garde `scans — 2 scans` a
        # « 8 pages · 1,1 Go » quand les deux scans portent en plus deux lots
        # scannes de 1,5 et 1,4 Go : additionner des frames a des pages
        # rendrait « 250 pages », qui n'est le compte de rien.
        noeud.poids = sum(enfant.poids for enfant in noeud.enfants)
        noeud.fichiers = sum(enfant.fichiers for enfant in noeud.enfants)
        noeud.cardinal = cardinal_lisible(noeud.fichiers, noeud.nature)
        noeud.nom = _mention_de_groupe(noeud.nature, noeud.enfants)
        return
    noeud.poids = noeud.poids_porte
    noeud.fichiers = noeud.fichiers_porte
    if noeud.nature == NATURE_LOT:
        noeud.cardinal = _cardinal_du_lot(noeud)
    elif noeud.nature == NATURE_RUSH:
        noeud.cardinal = _cardinal_du_rush(
            sum(1 for enfant in noeud.enfants if enfant.nature == NATURE_LOT),
            noeud.fichiers)


def _cardinal_du_lot(noeud: NoeudAffiche) -> str:
    """`9 objets · 378 f.` -- le compte d'objets, puis celui de fichiers.

    **La colonne de compte nomme les objets** (`EPIC11-ARB-218`) : elle dit
    « 2 lots · 491 f. » la ou elle disait « 491 fichiers ». Le compte de
    fichiers reste, parce que c'est le seul chiffre qui dit ce qu'une
    suppression toucherait vraiment.
    """
    objets = noeud.objets
    texte = f"{grouper_les_milliers(objets)} {MOT_DES_OBJETS[objets > 1]}"
    if noeud.fichiers:
        texte += f" · {cardinal_lisible(noeud.fichiers, noeud.nature)}"
    return texte


def _cardinal_du_rush(lots: int, fichiers: int) -> str:
    """`2 lots · 445 f.`, ou `0 lot` quand le rush ne porte rien.

    Le segment des fichiers **disparait** a zero plutot que d'ecrire `0 f.` :
    `E6-1c` pose `0 lot` seul sur `plan-15_sons_seuls`, et redire zero deux
    fois n'ajoute rien a ce que le premier dit deja.
    """
    texte = projet_lecture.accorder(lots, "lot")
    if fichiers:
        texte += f" · {cardinal_lisible(fichiers, NATURE_RUSH)}"
    return texte


def _rush_affiche(rush: ObjetInventorie) -> NoeudAffiche:
    """Un rush et ses lots. Ce que le coeur poserait ICI d'autre est groupe.

    **Le coeur a bascule, et cette fonction n'a pas bouge d'une ligne.**
    `EPIC11-ARB-219` (2026-09-04) faisait du scan un FRERE du lot, pendu au
    rush ; `EPIC11-ARB-244` (2026-09-05) en refait l'enfant du lot qu'il
    reproduit, et `_enfants_du_lot` le rend desormais la-bas. La redaction
    precedente de cette docstring annoncait ce basculement au futur -- « le
    jour ou le coeur bascule » -- : il a eu lieu, et l'arbre est devenu celui
    d'`E6-1e` sans un caractere de changement ici. C'est la promesse tenue,
    donc elle se raconte au passe.

    **Ce qui reste, et qui n'est PAS un vestige d'`ARB-219`** : un rush ne
    porte aujourd'hui que des lots, mais rien n'oblige le coeur a s'y tenir
    demain -- il vient d'en changer deux fois en deux jours. Un enfant de rush
    d'une autre nature forme donc un groupe sous ce rush plutot que de
    disparaitre : c'est l'AC 1.4 un cran plus haut que :func:`_groupes_du_lot`,
    et `test_un_enfant_de_rush_d_une_AUTRE_nature_ne_DISPARAIT_pas` le mesure
    sur une nature que le coeur ne pose plus la.
    """
    lots = [_lot_affiche(enfant, 1) for enfant in rush.enfants
            if enfant.nature == NATURE_LOT]
    autres = ObjetInventorie(
        nature=rush.nature, nom=rush.nom, chemin=rush.chemin, etat=rush.etat,
        enfants=tuple(enfant for enfant in rush.enfants
                      if enfant.nature != NATURE_LOT))
    enfants = lots + _groupes_du_lot(autres, 1)
    noeud = NoeudAffiche(
        nature=rush.nature, nom=_nom_affiche(rush), etat=rush.etat,
        profondeur=0, poids=0, fichiers=0, cardinal="",
        chemin=rush.chemin, cible=rush, enfants=enfants)
    _resommer(noeud)
    return noeud


# ---------------------------------------------------------------------------
# Les orphelins, GREFFES par la regle des VERSIONS et par elle seule
# ---------------------------------------------------------------------------

#: Le decomposeur de version est **lu du coeur**, jamais redige ici.
#:
#: Il a d'abord ete ecrit dans ce module, et la frontiere
#: `test_AUCUN_module_de_la_TUI_ne_redige_une_regle_de_RANG` a dit que c'etait
#: faux -- a raison : sa propre docstring citait « l'inverse exact de la
#: fabrique, et il vit a cote d'elle pour la meme raison que la regle des rangs
#: vit une seule fois », puis le posait ailleurs. Il vit desormais dans
#: `io.naming`, contre `rang_du_fragment_de_version` dont il est le compose.
tige_et_rang = naming.tige_et_rang

#: Le decomposeur qui sait qu'un FICHIER porte son rang avant son extension.
#:
#: Il existe parce que `tige_et_rang` seul ne suffisait pas, et la couche 2 de
#: la revue l'a mesure : `plan-04_25_mmu_prores_hq_v2.mov` en ressortait
#: INTACT, donc les deux entrees `NATURE_MASTER` et `NATURE_PLANCHE` de
#: :data:`ANCRES_DES_ORPHELINS` etaient MORTES -- aucune version de master ni
#: de planche ne se greffait, et toutes partaient en queue d'arbre.
tige_et_rang_de_fichier = naming.tige_et_rang_de_fichier


#: **Sur QUOI un orphelin peut se greffer, par nature et par ordre de
#: priorite** -- et c'est ce qui empeche la question d'etre ambigue.
#:
#: Le piege est reel et il a ete mesure : le dossier de frames d'un lot porte
#: le nom du LOT (`extract-frames/plan-04_25/`), donc le nom `plan-04_25`
#: designe DEUX noeuds declares a la fois -- le lot, et son dossier de frames.
#: Un index par nom seul rendait donc toute tige de frames ambigue, et plus
#: rien ne se greffait.
#:
#: La lecture qui leve l'ambiguite est celle du produit : un dossier
#: `extract-frames/plan-04_25_v2/` est le dossier de frames d'un LOT nomme
#: `plan-04_25_v2` -- un lot que le manifeste ignore --, et non « une version
#: du dossier de frames ». C'est la lecture qu'`E6-1` dessine, et c'est la
#: seule qui rende un objet supprimable : le produit sait retirer un lot.
ANCRES_DES_ORPHELINS: dict[str, tuple[str, ...]] = {
    NATURE_FRAMES_EXTRAITES: (NATURE_LOT,),
    NATURE_FRAMES_SCANNEES: (NATURE_LOT,),
    NATURE_LOT_SCANNE: (NATURE_SCAN, NATURE_LOT),
    #: Un slug d'ingestion est libre : il vaut souvent `<lot_id>_scan`, parfois
    #: le `lot_id` lui-meme. Les deux ancres sont donc essayees, le scan
    #: d'abord -- une version de scan est plus specifique qu'une version de lot.
    NATURE_SCAN: (NATURE_SCAN, NATURE_LOT),
    NATURE_MASTER: (NATURE_MASTER,),
    NATURE_PLANCHE: (NATURE_PLANCHE,),
}


def _declares_par_nom(rushes: Sequence[NoeudAffiche]
                      ) -> dict[tuple[str, str], list[NoeudAffiche]]:
    """Les noeuds DECLARES de l'arbre, indexes par `(nature, nom)`.

    La valeur est une LISTE et non un noeud : deux objets declares de la meme
    nature peuvent porter le meme nom a deux endroits de l'arbre, et greffer
    sur l'un des deux au hasard serait exactement la filiation devinee que le
    coeur refuse. Une tige ambigue ne greffe donc rien.
    """
    par_nom: dict[tuple[str, str], list[NoeudAffiche]] = {}
    for rush in rushes:
        for noeud in rush.parcourir():
            if noeud.groupe or noeud.etat == ETAT_NON_DECLARE:
                continue
            par_nom.setdefault((noeud.nature, noeud.nom), []).append(noeud)
    return par_nom


def _parent_de(rushes: Sequence[NoeudAffiche],
               cible: NoeudAffiche) -> NoeudAffiche | None:
    """Le noeud dont `cible` est un enfant direct, ou `None` a la racine."""
    for rush in rushes:
        for noeud in rush.parcourir():
            if any(enfant is cible for enfant in noeud.enfants):
                return noeud
    return None


def _lot_orphelin(nom: str, membres: Sequence[ObjetInventorie]) -> ObjetInventorie:
    """Un LOT de synthese portant les orphelins d'une meme tige et d'un meme rang.

    C'est ce que dessine `E6-1` : `▲ plan-04_12p5_v2 · non déclaré` avec
    « 3 objets », alors que le coeur rend ces trois objets **separement** et a
    plat -- il n'a aucun moyen de savoir qu'ils vont ensemble, et il refuse
    explicitement de le deviner par ressemblance de nom.

    **Ce noeud n'est PAS une devinette, et c'est le point.** Il ne rassemble
    que des orphelins dont la tige, lue par :func:`tige_et_rang`, EGALE le nom
    d'un lot declare, et dont le rang de version est le meme. C'est la regle
    des versions du depot (`EPIC11-ARB-104`, `EPIC11-ARB-88`), appliquee avec
    les fonctions qui l'ecrivent -- pas une comparaison approchee.

    Il ne porte **aucune cible** : ce lot n'existe dans aucun manifeste, donc
    `remove_project_element(lot_id=...)` ne le trouverait pas. Ses OBJETS, eux,
    sont bien sur le disque et portent chacun leur chemin.
    """
    return ObjetInventorie(nature=NATURE_LOT, nom=nom, chemin=None,
                           etat=ETAT_NON_DECLARE, enfants=tuple(membres))


def _place_de_la_version(parent: NoeudAffiche, ancre: NoeudAffiche,
                        rang: int) -> int:
    """Ou poser une version de rang `rang` a cote de son ancre : APRES les rangs
    inferieurs de la meme famille, avant les rangs superieurs.

    **Le rang croissant, et il a fallu deux mesures pour l'obtenir** (finding
    `F4` de la couche 1, puis le banc de `B04` qui a montre que la premiere
    correction ne suffisait pas) :

    * poser toujours a `index(ancre) + 1` faisait sortir des orphelins fournis
      `v2, v3, v4` dans l'ordre `v4, v3, v2` -- chaque insertion repoussant la
      precedente ;
    * les parcourir du rang le plus haut au plus bas corrigeait CE cas et pas
      l'autre : une version greffee s'inserait alors devant une version
      **DECLAREE** de rang inferieur, donnant `scan, scan_v3, scan_v2`. Le
      tri ne voit que les greffes ; les declarees etaient deja la.

    Calculer la place plutot que l'ordre de parcours rend le resultat
    independant de l'un comme de l'autre, ce qu'aucun tri ne donne.

    **Le sens attendu est celui des maquettes** : `E6-1e` pose
    `…_6f-pay.pdf` puis `…_6f-pay_v2.pdf`, et `…_scan` puis `…_scan_v2`. Deux
    familles voisines rangees a l'envers l'une de l'autre sur le meme ecran est
    un ecart qui se lit.

    Le nom d'un voisin se lit de son objet de COEUR quand il en a un : la ligne
    porte ` · non declare` sur une greffe, et decomposer cette mention comme un
    fragment de version rendrait une tige qui ne correspond a rien.
    """
    place = parent.enfants.index(ancre) + 1
    while place < len(parent.enfants):
        voisin = parent.enfants[place]
        nu = voisin.cible.nom if voisin.cible is not None else voisin.nom
        tige, rang_du_voisin = tige_et_rang_de_fichier(nu)
        if tige != ancre.nom or rang_du_voisin >= rang:
            break
        place += 1
    return place


def greffer_les_orphelins(rushes: list[NoeudAffiche],
                          orphelins: Sequence[ObjetInventorie]
                          ) -> list[NoeudAffiche]:
    """Poser les orphelins dans l'arbre, et rendre ceux qui n'ont pas de place.

    **La regle, et elle est exacte plutot qu'approchee** (arbitrage d'Egan du
    2026-09-05, sur invite) : un orphelin dont la TIGE egale le nom d'un noeud
    declare est une VERSION de ce noeud, et se pose a cote de lui. Rien d'autre
    ne se greffe.

    **Pourquoi la tige et pas le prefixe.** Le nom d'un lot est fabrique par
    `naming.build_lot_id`, qui **condense et tronque** au-dela de
    `CANONICAL_ID_MAX_LENGTH` : la fabrique est a SENS UNIQUE, et `io.naming`
    ne publie aucun inverse. Retrouver le rush d'un orphelin en decoupant son
    nom serait donc faux des que le nom est long -- le `rush_id` a litteralement
    disparu dans un condensat. La tige de version, elle, est lisible : c'est le
    seul fragment que le depot sache retirer, et il le sait parce que c'est
    sa propre fabrique de suffixe de version qui l'a ecrit.

    **Une tige ambigue ne greffe rien** : deux noeuds declares du meme nom a
    deux endroits de l'arbre laissent l'orphelin a plat. Le taire pour choisir
    l'un des deux serait la filiation devinee que `project_maintenance` refuse
    (« un lien qui designe un autre lot ne se devine pas par ressemblance de
    nom »).

    Les orphelins qui ne se greffent pas ne disparaissent PAS : ils sont rendus
    a l'appelant, qui les pose en queue d'arbre. Un dossier d'images qui pese
    sur le disque et qu'aucun ecran ne montre est exactement le sujet de cette
    story.
    """
    par_nom = _declares_par_nom(rushes)
    #: Les orphelins qui visent un LOT se rassemblent par `(lot, rang)` : c'est
    #: le noeud de synthese d'`E6-1`. Ceux qui visent un objet se posent un par
    #: un, a cote de lui.
    familles: dict[tuple[int, int], list[ObjetInventorie]] = {}
    ancres: dict[tuple[int, int], NoeudAffiche] = {}
    restants: list[ObjetInventorie] = []
    for orphelin in orphelins:
        tige, rang = tige_et_rang_de_fichier(orphelin.nom)
        candidats: list[NoeudAffiche] = []
        for nature in ANCRES_DES_ORPHELINS.get(orphelin.nature, ()):
            candidats = par_nom.get((nature, tige)) or []
            if candidats:
                break
        # Un nom que la decomposition rend INTACT ne porte aucun fragment de
        # version : ce n'est donc pas une version, et rien ne s'y greffe. Dit
        # ainsi plutot que par la borne, l'ecran ne redige aucune regle de rang.
        if tige == orphelin.nom or len(candidats) != 1:
            restants.append(orphelin)
            continue
        ancre = candidats[0]
        cle = (id(ancre), rang)
        ancres[cle] = ancre
        familles.setdefault(cle, []).append(orphelin)

    for cle, membres in familles.items():
        ancre = ancres[cle]
        _, rang = cle
        parent = _parent_de(rushes, ancre)
        if parent is None:
            restants.extend(membres)
            continue
        nom = naming.nom_de_version_de_fichier(ancre.nom, rang)
        if ancre.nature == NATURE_LOT:
            greffe = _lot_affiche(_lot_orphelin(nom, membres), ancre.profondeur)
        elif len(membres) == 1:
            greffe = _objet_affiche(membres[0], ancre.profondeur)
        else:
            # Plusieurs orphelins de meme tige et de meme rang sur une ancre
            # qui n'est PAS un lot : rien dans le produit ne dit ce qu'ils
            # forment ensemble, donc on ne l'invente pas.
            restants.extend(membres)
            continue
        parent.enfants.insert(_place_de_la_version(parent, ancre, rang),
                              greffe)
    for rush in rushes:
        _resommer_en_profondeur(rush)
    return restants


def orphelins_affiches(restants: Sequence[ObjetInventorie]
                       ) -> list[NoeudAffiche]:
    """Les orphelins qu'aucune ancre n'a pris, groupes par nature, en QUEUE.

    **Ils sont rendus par leur NOM, jamais fondus dans le libelle de leur
    nature** : un orphelin est precisement l'objet dont le nom est la seule
    information disponible -- il n'a pas de declaration ou lire autre chose --,
    et une ligne `frames — 1 frame` le ferait disparaitre en le montrant.
    C'est la difference avec le meme dossier vu SOUS un lot, ou le lot le
    nomme deja.

    **Le groupe qui les porte SE COCHE, comme tout groupe** -- corrige le
    2026-09-07 (finding `C1-5`). Cette phrase disait « donc il ne se coche
    pas », ce qui etait vrai jusqu'a `EPIC11-ARB-264` et faux depuis :
    `ArbreDuProjet.basculer` coche desormais tous les groupes, orphelins
    compris, et le refus qui vivait la est tombe avec son motif.

    **Ce qui change pour un groupe d'ORPHELINS, et c'est mesure** : il se
    coche, mais `Suppr` n'aboutit pas sur les cinq natures fines. Un orphelin
    vit en QUEUE d'arbre, a la racine ; `projet_suppression.lot_ancetre` rend
    donc `None`, `cible_du_noeud` rend `None` a son tour pour chaque membre,
    et l'ecran monte un refus `GROUPE_SANS_CIBLE_VISABLE` qui NOMME les
    membres un par un (`EPIC11-ARB-258`) au lieu de se taire. Mesure :
    `test_orphelins_le_groupe_SE_COCHE_et_Suppr_nomme_ses_membres_non_visables`.
    """
    par_nature: dict[str, list[ObjetInventorie]] = {}
    for orphelin in restants:
        par_nature.setdefault(orphelin.nature, []).append(orphelin)
    ordre = list(ORDRE_DES_GROUPES) + [nature for nature in par_nature
                                       if nature not in ORDRE_DES_GROUPES]
    lignes: list[NoeudAffiche] = []
    for nature in ordre:
        membres = par_nature.get(nature)
        if not membres:
            continue
        objets = [_objet_affiche(objet, 1) for objet in membres]
        groupe = NoeudAffiche(
            nature=nature, nom=_mention_de_groupe(nature, objets),
            etat=ETAT_PRESENT, profondeur=0, poids=0, fichiers=0, cardinal="",
            enfants=objets, groupe=True)
        _resommer(groupe)
        lignes.append(groupe)
    return lignes


def _resommer_en_profondeur(noeud: NoeudAffiche) -> None:
    """Resommer un sous-arbre de bas en haut, apres les greffes.

    De bas en haut, et jamais l'inverse : un lot resomme avant le groupe qui
    le porte lirait le total d'avant la greffe -- c'est-a-dire exactement le
    chiffre qu'on vient de corriger.
    """
    for enfant in noeud.enfants:
        _resommer_en_profondeur(enfant)
    if noeud.groupe or noeud.nature in (NATURE_RUSH, NATURE_LOT):
        _resommer(noeud)


# ---------------------------------------------------------------------------
# Le modele pur : l'arbre, son curseur, sa fenetre
# ---------------------------------------------------------------------------

@dataclass
class ArbreDuProjet:
    """L'arbre d'`E6-1` : des racines, un curseur, une fenetre, des coches.

    **Modele PUR** : aucune methode n'ouvre un fichier, ne mesure un disque ni
    ne touche a `textual`. C'est ce qui rend tout ce qui suit mesurable sans
    clavier et sans terminal, comme les trois autres listes du depot.
    """

    racines: list[NoeudAffiche]
    #: Le nom du projet, en titre de la zone : « Au lieu de "ce que projet_demo
    #: contien" mettre juste le nom du projet » (Egan, 2026-09-04, note 1).
    titre: str = ""
    curseur: int = 0
    premier_visible: int = 0

    def __post_init__(self) -> None:
        noms = [racine.nom for racine in self.racines]
        if len(set(noms)) != len(noms):
            raise InventaireMalForme(
                f"Deux racines portent le meme nom : {noms}. Deux lignes du "
                "meme rush doubleraient son poids dans la ligne d'etat.")

    # -- construction --------------------------------------------------------

    @classmethod
    def depuis_l_inventaire(cls, inventaire: InventaireDuProjet) -> "ArbreDuProjet":
        """L'arbre d'affichage d'un inventaire de coeur.

        **Replie au niveau des lots a l'ouverture** (AC 2.2) : les rushes sont
        deplies, tout ce qui pend d'un lot est replie. Un arbre entierement
        deplie ne tiendrait pas -- `E6-1e` en fait la mesure, un seul lot
        deplie remplissant les dix-sept lignes de la zone.

        Les orphelins qui ne se greffent pas sont poses **en queue**, groupes
        par nature : ils sont sur le disque, donc ils se voient.
        """
        racines = [_rush_affiche(rush) for rush in inventaire.rushes]
        # **Les scans de mire declares par leur profil passent par le MEME
        # chemin que les orphelins** (`EPIC11-ARB-262`), et c'est la moitie de
        # l'arbitrage sans laquelle l'autre serait un recul : les sortir de la
        # liste des orphelins sans les reposer ici les rendrait INVISIBLES,
        # c'est-a-dire des octets qui pesent sur le disque et qu'aucun ecran ne
        # montre -- le sujet meme de cette story.
        #
        # Ils ne se greffent sur rien (leur nom ne porte aucun fragment de
        # version, donc `tige == nom`), donc ils tombent dans les restants et
        # rejoignent le groupe `scans` en queue. Ils y sont nommes SANS la
        # mention « · non declare », que :func:`_nom_affiche` ne pose que sur
        # `ETAT_NON_DECLARE` : c'est exactement le defaut qu'Egan a signale.
        racines.extend(orphelins_affiches(greffer_les_orphelins(
            racines, tuple(inventaire.orphelins) + tuple(inventaire.calibrations))))
        arbre = cls(racines=racines, titre=inventaire.project_id or "")
        for racine in racines:
            racine.deplie = True
        return arbre

    # -- lecture -------------------------------------------------------------

    def lignes_visibles(self) -> list[NoeudAffiche]:
        """Les noeuds que l'arbre montrerait sans fenetre, de haut en bas."""
        vues: list[NoeudAffiche] = []
        for racine in self.racines:
            vues.extend(racine.visibles())
        return vues

    def __len__(self) -> int:
        return len(self.lignes_visibles())

    @property
    def courant(self) -> NoeudAffiche | None:
        """Le noeud sous le curseur, ou `None` sur un projet vide."""
        vues = self.lignes_visibles()
        if not vues:
            return None
        return vues[min(self.curseur, len(vues) - 1)]

    def tous(self) -> Iterator[NoeudAffiche]:
        """Tous les noeuds, plies ou non."""
        for racine in self.racines:
            yield from racine.parcourir()

    @property
    def coches(self) -> tuple[NoeudAffiche, ...]:
        return tuple(noeud for noeud in self.tous() if noeud.coche)

    @property
    def ecarts(self) -> int:
        """Le cardinal d'objets dont l'etat n'est pas :data:`ETAT_PRESENT`.

        **Les DEUX familles a la fois** -- declare-absent et non-declare --,
        comme `EPIC11-ARB-217` les a fondues dans cet ecran. Les groupes n'en
        sont pas : ils n'ont pas d'etat propre.
        """
        return sum(1 for noeud in self.tous()
                   if not noeud.groupe and noeud.etat != ETAT_PRESENT)

    @property
    def poids_total(self) -> int:
        return sum(racine.poids_porte for racine in self.racines)

    @property
    def fichiers_total(self) -> int:
        return sum(racine.fichiers_porte for racine in self.racines)

    @property
    def objets_total(self) -> int:
        """Le cardinal d'OBJETS du projet, groupes exclus."""
        return sum(1 for noeud in self.tous() if not noeud.groupe)

    def rang(self, nom: str) -> int | None:
        """Le rang VISIBLE du noeud de ce nom exact, ou `None`.

        **Sur la liste que le CODE parcourt**, jamais sur celle que la fabrique
        ecrit : un banc qui viserait par indice dans sa propre fabrique
        mesurerait sa fabrique.
        """
        for rang, noeud in enumerate(self.lignes_visibles()):
            if noeud.nom == nom:
                return rang
        return None

    def rang_du_noeud(self, cible: NoeudAffiche) -> int | None:
        """Le rang VISIBLE d'un noeud, trouve par IDENTITE et jamais par NOM.

        **Distinct de :meth:`rang`, et le distinguo a ete paye** : les noms de
        groupe sont FORMULAIRES (`planches — 1 planche`), donc deux lots
        portant un objet de la meme nature produisent deux groupes strictement
        homonymes. Ce n'est pas un cas exotique, c'est le cas courant. La
        couche 1 de la revue (finding `F3`) a mesure `←` posant le curseur sur
        le groupe d'un AUTRE lot : le repliage s'appliquait au bon noeud, le
        curseur atterrissait dans un autre sous-arbre.

        `rang(nom)` reste, et il reste juste pour ce qu'il fait : un banc vise
        par nom, et un nom d'OBJET est unique dans sa portee. C'est le code de
        navigation, qui tient deja le noeud, qui n'a aucune raison de repasser
        par son nom -- meme famille que `lot_ancetre`, qui compare par identite
        pour ce motif exact.
        """
        for rang, noeud in enumerate(self.lignes_visibles()):
            if noeud is cible:
                return rang
        return None

    # -- navigation ----------------------------------------------------------

    def deplacer(self, pas: int) -> None:
        """`↑↓` : le curseur reste dans l'arbre, il n'en sort jamais."""
        total = len(self.lignes_visibles())
        if not total:
            return
        self.curseur = min(max(self.curseur + pas, 0), total - 1)
        self._recadrer()

    def viser(self, nom: str) -> NoeudAffiche:
        """Poser le curseur sur un noeud NOMME, jamais sur un rang devine."""
        rang = self.rang(nom)
        if rang is None:
            raise InventaireMalForme(
                f"Aucun noeud visible ne s'appelle {nom!r} ; visibles : "
                f"{[noeud.nom for noeud in self.lignes_visibles()]}.")
        self.curseur = rang
        self._recadrer()
        return self.lignes_visibles()[rang]

    def deplier(self) -> bool:
        """`→` : ouvrir le noeud sous le curseur. Rend `True` s'il a bouge."""
        noeud = self.courant
        if noeud is None or not noeud.pliable or noeud.deplie:
            return False
        noeud.deplie = True
        self._recadrer()
        return True

    def replier(self) -> bool:
        """`←` : refermer le noeud sous le curseur, ou remonter a son parent.

        **Remonter quand il n'y a rien a fermer** est ce qui rend la touche
        utile sur une feuille : sans cela, `←` sur un objet ne ferait rien et
        serait indistinguable d'un clavier casse.
        """
        noeud = self.courant
        if noeud is None:
            return False
        if noeud.pliable and noeud.deplie:
            noeud.deplie = False
            self._recadrer()
            return True
        parent = _parent_de(self.racines, noeud)
        if parent is None:
            return False
        # Par IDENTITE : `rang(parent.nom)` posait le curseur sur le PREMIER
        # homonyme visible, c'est-a-dire souvent le groupe d'un autre lot
        # (finding `F3` de la couche 1). Et `or 0` avalait le rang 0.
        rang = self.rang_du_noeud(parent)
        self.curseur = 0 if rang is None else rang
        parent.deplie = False
        self._recadrer()
        return True

    def basculer(self) -> bool:
        """`Espace` coche et decoche le noeud sous le curseur, **groupe compris**.

        **Un groupe se coche depuis `EPIC11-ARB-264`** (2026-09-07), et le
        refus qui vivait ici tombe avec son motif. Il disait vrai quand il a
        ete ecrit : `remove_project_element` n'a aucune cible qui vise un
        groupe, donc cocher en promettait une. Ce qui a change n'est pas le
        jugement mais le fait -- supprimer un groupe est N appels, portes par
        `remove_project_group`, et le constat d'Egan du 2026-09-06 est
        litteralement « planches (l'ensemble) et masters (l'ensemble d'un lot)
        ne sont pas selectionnables ».

        **Cocher un groupe ne coche PAS ses membres**, et c'est dit plutot que
        tu : la coche du groupe est celle du groupe, `Suppr` la deplie en N
        cibles au moment d'agir. Propager la coche aux membres ferait de
        `coches` une liste de N+1 entrees pour un seul geste, donc ferait
        tomber `visee()` dans sa branche « plusieurs coches » -- l'inverse de
        ce que l'arbitrage ouvre. Le regime de la case (un groupe coche
        coche-t-il ses membres ?) est un point d'ecran que
        `EPIC11-ARB-264` laisse ouvert, et ne rien propager est le choix qui ne
        le prejuge pas.
        """
        noeud = self.courant
        if noeud is None:
            return False
        noeud.coche = not noeud.coche
        return True

    # -- ce sur quoi un GESTE agit ------------------------------------------

    def visee(self) -> tuple[NoeudAffiche | None, str]:
        """Ce sur quoi `Suppr` agit, et le motif quand rien n'est visable.

        **La selection PRIME sur la ligne active** (`EPIC11-ARB-257`, retour
        terrain d'Egan du 2026-09-06 : « Suppr lance la suppression pour la
        ligne active plutot que pour la selection cochee »). Le piege exact
        qu'il a rencontre : un lot coche, le curseur reste sur le rush, et
        `Suppr` ouvrait la suppression du RUSH -- c'est-a-dire un objet qu'il
        n'avait pas designe, et dont le coeur refuse ensuite la suppression
        parce qu'il porte encore ce lot-la.

        Trois regimes, et le troisieme est une **limite nommee** plutot qu'un
        silence :

        * **aucune coche** -> la ligne active. Sans ce repli, `Suppr`
          deviendrait inerte sur un arbre jamais coche, ce qui est le defaut
          inverse et pas un progres ;
        * **une seule coche** -> elle, et le curseur ne compte pas. C'est
          exactement le cas d'Egan, et il se sert avec le cartouche `E6-2` tel
          qu'il est dessine : une cible, un plan, un rapport ;
        * **plusieurs coches** -> rien, et le motif le DIT. Le modele de
          suppression est mono-cible de bout en bout -- `ouvrir_la_suppression`
          prend un noeud singulier, `PlanDeSuppression` porte une cible, et
          aucune maquette validee ne dessine un cartouche a N cibles, ce
          qu'`EPIC11-ARB-144` interdit de coder. Agir en silence sur le curseur
          serait la destruction non demandee qu'`EPIC11-ARB-257` ferme ; ne
          rien faire sans le dire serait le finding `I8`.
        """
        coches = self.coches
        if len(coches) > 1:
            return None, MOTIF_DE_LA_SELECTION_MULTIPLE.format(
                cardinal=grouper_les_milliers(len(coches)))
        if coches:
            return coches[0], ""
        return self.courant, ""

    # -- ce que la fenetre montre -------------------------------------------

    def fenetre(self) -> tuple[int, int]:
        """`(premier, dernier)` rangs visibles, bornes incluses."""
        return jetons.fenetre_de_liste(len(self.lignes_visibles()),
                                       self.premier_visible, HAUTEUR_ARBRE)

    def _recadrer(self) -> None:
        self.premier_visible = jetons.recadrer_la_fenetre(
            self.premier_visible, self.curseur, len(self.lignes_visibles()),
            HAUTEUR_ARBRE)

    # -- rendu ---------------------------------------------------------------

    def ligne(self, rang: int, ascii_seul: bool = False) -> str:
        """Une ligne d'arbre, aux colonnes d'`E6-1` (5 / 46 / 17 / 8).

        L'ordre des marques est celui du generateur des maquettes, et il n'est
        pas libre : **la marque de pliage precede le rattachement**. `└─` dit
        d'ou la feuille pend, la marque dit si le noeud se plie ; dans l'autre
        ordre le `└─` s'ecarte de trois colonnes de son nom et l'indentation
        cesse de dire la profondeur, qui est la seule chose qu'elle dit.

        **Un noeud terminal n'a ni marque ni colonnes de marque, et c'est
        mesure plutot que choisi** : aucun noeud du niveau objet ne se plie
        (sauf un scan, qui le declare), donc les deux colonnes y seraient
        mortes sur toutes les lignes a la fois. Les retirer ne desaligne rien a
        l'interieur du niveau et rend les deux colonnes que le rattachement
        reprend.

        **Le nom s'abrege AU MILIEU** (`jetons.abreger_nom`), jamais par la
        fin : les objets de ce depot se distinguent par leur SUFFIXE --
        `_v2`, `_prores_hq` --, et une elision par la queue rendrait deux
        versions d'un meme objet indiscernables a l'ecran, c'est-a-dire le
        risque R12 remonte au niveau de l'affichage.
        """
        vues = self.lignes_visibles()
        noeud = vues[rang]
        table = jetons.glyphes(ascii_seul)
        tete = ("   " + table["curseur"] + " " if rang == self.curseur
                else " " * TETE_ARBRE)
        indent = "  " * noeud.profondeur
        deco = f"{table['rattachement']} " if noeud.est_terminal else ""
        if noeud.est_terminal:
            marque = ""
        elif noeud.pliable:
            marque = (PLIAGE_DEPLIE if noeud.deplie else PLIAGE_REPLIE) + " "
        else:
            marque = "  "
        case = _case_a_cocher(noeud, table)
        etat = "" if noeud.etat == ETAT_PRESENT else _glyphe_d_etat(
            noeud.etat, ascii_seul) + " "
        prefixe = f"{indent}{marque}{deco}{case}{etat}"
        nom = jetons.abreger_nom(
            _replie(noeud.nom, ascii_seul),
            NOM_ARBRE - jetons.colonnes(prefixe), ascii_seul)
        corps = prefixe + nom
        cardinal = _replie(noeud.cardinal, ascii_seul)
        poids = _replie(poids_lisible(noeud.poids), ascii_seul)
        return (tete + corps + " " * max(0, NOM_ARBRE - jetons.colonnes(corps))
                + _a_droite(cardinal, FICHIERS_ARBRE, ascii_seul)
                + _a_droite(poids, POIDS_ARBRE, ascii_seul)).rstrip()

    def lignes_de_l_arbre(self, ascii_seul: bool = False) -> list[str]:
        """Les :data:`HAUTEUR_ARBRE` lignes de la zone, `…` compris.

        L'idiome du debordement est celui de `X4` et de l'explorateur, repris
        et non reinvente : un `…` en tete, un `…` en pied portant la fenetre.
        La zone est completee par des lignes vides quand l'arbre est plus court
        qu'elle, ce qui tient la ligne d'etat a la meme place d'un projet a
        l'autre.
        """
        vues = self.lignes_visibles()
        total = len(vues)
        if not total:
            return [""] * HAUTEUR_ARBRE
        premier, dernier = self.fenetre()
        points = jetons.points_d_abregement(ascii_seul)
        rendues: list[str] = []
        if premier > 0:
            rendues.append(" " * (TETE_ARBRE + 2) + points)
        for rang in range(premier, dernier + 1):
            rendues.append(self.ligne(rang, ascii_seul))
        if dernier < total - 1:
            position = f"{premier + 1}-{dernier + 1} sur {total}"
            tete = " " * (TETE_ARBRE + 2) + points
            utile = TETE_ARBRE + NOM_ARBRE + FICHIERS_ARBRE + POIDS_ARBRE
            creux = utile - jetons.colonnes(tete) - jetons.colonnes(position)
            rendues.append(tete + " " * max(jetons.CREUX_MINIMAL, creux)
                           + position)
        return rendues + [""] * max(0, HAUTEUR_ARBRE - len(rendues))

    def rang_du_curseur(self) -> int | None:
        """Le rang, dans :meth:`lignes_de_l_arbre`, de la ligne a accentuer.

        **Passe explicitement a `jetons.peindre`, jamais devine** : ces lignes
        sont indentees, et l'auto-detection teste `startswith` sur le glyphe de
        curseur -- elle ne trouverait rien, en silence.
        """
        premier, dernier = self.fenetre()
        if not self.lignes_visibles() or not premier <= self.curseur <= dernier:
            return None
        return (1 if premier > 0 else 0) + (self.curseur - premier)

    def etats_des_lignes(self) -> dict[int, str]:
        """L'etat de chaque ligne d'ECART, par rang dans la zone.

        **Donne et jamais retrouve dans le texte** (`EPIC11-ARB-71`) : la
        reconnaissance par motif marcherait ici par accident et cesserait de
        marcher au premier nom d'objet valant `x` en repli ASCII.

        Seules les lignes d'ecart portent un etat : peindre les lignes
        `present` en vert ferait un arbre entierement colore, ou l'ecart ne se
        verrait plus -- c'est le contraire de ce que la couleur sert ici.
        """
        vues = self.lignes_visibles()
        premier, dernier = self.fenetre()
        decalage = 1 if premier > 0 else 0
        etats: dict[int, str] = {}
        for rang in range(premier, min(dernier + 1, len(vues))):
            noeud = vues[rang]
            if noeud.etat != ETAT_PRESENT:
                etats[decalage + (rang - premier)] = _NOM_D_ETAT[noeud.etat]
        return etats

    def ligne_de_compte(self, ascii_seul: bool = False) -> str:
        """La ligne d'etat quand le curseur ne porte aucun ecart (AC 2.3).

        **Tous ses chiffres sont LUS de l'arbre**, jamais recalcules a
        l'ecran : `poids_total`, `fichiers_total` et `objets_total` viennent
        des mesures du coeur remontees noeud par noeud.
        """
        rushes = sum(1 for racine in self.racines
                     if racine.nature == NATURE_RUSH)
        lots = sum(1 for noeud in self.tous() if noeud.nature == NATURE_LOT)
        segments = [projet_lecture.accorder(rushes, "rush"),
                    projet_lecture.accorder(lots, "lot"),
                    f"{grouper_les_milliers(self.objets_total)} "
                    f"{MOT_DES_OBJETS[self.objets_total > 1]}",
                    cardinal_lisible(self.fichiers_total, NATURE_RUSH),
                    poids_lisible(self.poids_total)]
        if self.ecarts:
            segments.append(f"{self.ecarts} {MOT_DES_ECARTS[self.ecarts > 1]}")
        return _replie(" · ".join(segments), ascii_seul)

    def ligne_de_l_ecart(self, ascii_seul: bool = False) -> str | None:
        """La ligne d'etat CONTEXTUELLE quand le curseur porte un ecart.

        C'est ce qui remplace `E6-1b` (`EPIC11-ARB-217`, tranche le
        2026-09-04 : « fondre dans E6-1 »). Le CHEMIN ATTENDU -- seule chose
        que l'ecran des ecarts disait de plus -- se lit ici.
        """
        noeud = self.courant
        if noeud is None or noeud.etat == ETAT_PRESENT:
            return None
        glyphe = _glyphe_d_etat(noeud.etat, ascii_seul)
        if noeud.etat == ETAT_DECLARE_ABSENT:
            phrase = ETAT_DE_L_OBJET_ABSENT
        else:
            phrase = ETAT_DE_L_OBJET_NON_DECLARE
        segments = [f"{glyphe} {phrase}"]
        if noeud.chemin:
            dossier = noeud.chemin.rsplit("/", 1)[0] + "/" \
                if "/" in noeud.chemin else noeud.chemin
            segments.append(ETAT_DU_CHEMIN_ATTENDU.format(dossier=dossier))
        if self.ecarts:
            segments.append(f"{self.ecarts} {MOT_DES_ECARTS[self.ecarts > 1]}")
        return _replie(" · ".join(segments), ascii_seul)

    def raccourcis(self) -> str:
        """La ligne de raccourcis du moment (`EPIC11-ARB-215`, issue C).

        `Ctrl+L relinker` quand le curseur porte un objet sur lequel un lien
        peut etre a refaire ; `Ctrl+D declarer` partout ailleurs. Les deux ne
        s'annoncent JAMAIS ensemble : c'est la mesure qui fait tenir la ligne
        sous les 76 colonnes de la zone utile.

        **Le RUSH DECLARE a rejoint le premier regime le 2026-09-07**, et il
        n'aurait jamais du en etre absent : c'est le SEUL objet que le coeur
        sache relinker (`mmu relink --rush <rush_id>`, et
        `relink.appliquer_relink`, qui ecrit dans `rushes[]`). Or il n'entrait
        pas dans la garde precedente --
        `project_inventory` pose `etat=ETAT_PRESENT` sur tout rush du
        manifeste et ne regarde **jamais** si son `source_path` existe, la
        source vivant hors du projet. La touche etait donc annoncee sur les
        planches, masters, scans et jeux de frames -- que le coeur ne relinke
        pas -- et tue sur les rushes, qu'il relinke. Ce n'est pas une
        preference d'affichage : c'etait la touche annoncee exactement la ou
        elle ne pouvait rien.

        **L'ancien regime est RETIRE de l'ANNONCE** (`EPIC11-ARB-263`, Egan
        par invite le 2026-09-07 : « garder le refus nomme mais retirer
        l'annonce partout ou ce n'est pas actif »).

        Deux arbitrages deja tranches tiraient en sens inverse sur ce cas
        precis, et c'est ce qui le rendait indecidable sans lui :
        `EPIC11-ARB-258` veut qu'un refus se prononce, `EPIC11-ARB-215` veut
        que la barre ne porte **que ce qui agit** sur l'objet sous le curseur.
        La reponse les concilie plutot qu'elle n'en sacrifie un : la barre suit
        `-215` -- elle n'annonce plus rien la ou rien n'agit --, et la TOUCHE
        suit `-258` -- frappee ailleurs, elle repond
        :data:`MOTIF_DU_RELINK_HORS_RUSH` au lieu de ne rien faire. Qui a
        appris le raccourci sur un rush ne tombe donc pas dans le vide.

        **Le motif de fond, mesure, et il tranche le \"pourquoi\" qu'Egan a
        pose** : `rushes[].source_path` est la **seule** exception a
        l'invariant de portabilite v2 « aucun chemin absolu au manifeste »,
        levee par `EPIC7-ARB-41` et pour ce champ seul. Les cinq autres
        natures vivent DANS le projet et leur emplacement est **calcule** par
        `io/project_layout` : il n'y a aucune reference a reparer, un fichier
        absent y est simplement absent. Un relink d'objet produit n'est donc
        pas un coeur qui manque -- c'est un geste qui n'a pas de sens.

        Le jour ou un objet produit gagnerait un chemin stocke, c'est cette
        garde-ci qui bougerait, et le refus de la touche avec elle.
        """
        noeud = self.courant
        if noeud is None:
            return RACCOURCIS_INVENTAIRE_DECLARER
        relinkable = (noeud.nature == NATURE_RUSH
                      and noeud.etat != ETAT_NON_DECLARE)
        return (RACCOURCIS_INVENTAIRE_RELINKER if relinkable
                else RACCOURCIS_INVENTAIRE_DECLARER)


#: La projection des etats du coeur sur les noms d'etat de `jetons` (AC 2.4).
#: **Les deux vocabulaires sont LUS**, jamais rediges : les cles viennent de
#: `project_inventory.ETATS`, les valeurs de `jetons.NOMS_D_ETAT`, et une
#: frontiere mesure que la table les couvre exactement tous les deux.
_NOM_D_ETAT = {
    ETAT_DECLARE_ABSENT: "absent",
    ETAT_NON_DECLARE: "substitute",
}


def _case_a_cocher(noeud: NoeudAffiche, table) -> str:
    """La case d'une ligne. **Toutes les lignes en portent une**, groupes compris.

    **Elle avait ete RETIREE des groupes le 2026-09-06, et elle revient le
    2026-09-07** -- c'est `EPIC11-ARB-264` qui a change le fait sous la regle,
    pas un retour en arriere. Le raisonnement d'alors etait juste : une case
    inerte est une promesse faite a l'oeil que `Espace` ne tenait pas
    (`EPIC11-ARB-258`, finding `I8`), et retirer la case coutait moins que de
    tenir la promesse. Son propre commentaire annoncait la sortie : « le jour
    ou cocher un groupe cochera ses membres, cette fonction rend une case et
    rien d'autre ne bouge ». C'est ce jour-la.

    Ce qui a change, mesure : le coeur porte `remove_project_group`, la
    suppression d'un groupe est N appels a `remove_project_element`, et le
    constat d'Egan qui l'a declenchee est litteralement « planches (l'ensemble)
    et masters (l'ensemble d'un lot) ne sont pas selectionnables ». La case
    n'est plus inerte, donc elle n'est plus une promesse cassee.

    **L'ECART entre les deux maquettes est TRANCHE par le fait, et dans le sens
    de `E6-1d`** : ce dessin-la porte `[ ]` sur `planches — 2 planches` et sur
    `masters — 1 master`, `E6-1e` n'en porte sur aucune ligne. Le produit suit
    desormais `E6-1d`, qui est le dessin de la SELECTION -- c'est-a-dire
    exactement l'ecran dont la question relevait.
    """
    return table["coche" if noeud.coche else "decoche"] + " "


def _glyphe_d_etat(etat: str, ascii_seul: bool = False) -> str:
    """`✕` ou `▲`, du mode courant. Un etat present n'a pas de glyphe."""
    return jetons.glyphes(ascii_seul)[_NOM_D_ETAT[etat]]


def _replie(texte: str, ascii_seul: bool) -> str:
    return jetons.replier_ascii(texte) if ascii_seul else texte


def _a_droite(texte: str, largeur: int, ascii_seul: bool = False) -> str:
    """Un champ cale a DROITE, mesure en COLONNES et jamais en `len()`.

    Un ideogramme occupe deux colonnes : `str.rjust` calerait un champ de dix
    caracteres sur vingt colonnes, et toutes les colonnes de droite partiraient
    avec.
    """
    texte = jetons.ajuster(texte, largeur, ascii_seul)
    return " " * max(0, largeur - jetons.colonnes(texte)) + texte


# ---------------------------------------------------------------------------
# `E6-1` / `E6-1a` -- l'ecran, et ses deux moments
# ---------------------------------------------------------------------------

class EcranInventaireDuProjet(ObjetTravaille, Palier):
    """L'inventaire du projet : `E6-1` deplie, `E6-1a` pendant la lecture.

    **Un seul ecran a deux moments, jamais deux ecrans.** Egan, note 3 du
    2026-09-04, verbatim : « Ce ne sont pas deux ecrans differents ! ». En
    faire deux `Screen` empilerait deux paliers la ou `EPIC11-ARB-2` en veut
    un, et ferait changer le titre sous les yeux a la seconde ou la lecture
    s'acheve.

    **Le chargement se fait a l'OUVERTURE**, et c'est mesure : l'inventaire
    complet d'un projet de 15 000 fichiers tient sous 200 ms sur disque local
    (Q1 de la fiche, ~12 us par fichier). Le chargement a la demande couterait
    un etat de plus par noeud pour un gain invisible. Le rotor d'`E6-1a` reste
    utile : la mesure ne couvre ni le cache froid ni un volume reseau.
    """

    titre = projet_lecture.PROJET
    raccourcis = RACCOURCIS_INVENTAIRE_DECLARER
    #: Une station du parcours et non un passage : `Échap` y ramene au palier
    #: Projet, et on y revient apres chaque suppression.
    TRANSITOIRE = False
    ID_DU_CORPS = "corps-inventaire-projet"

    def __init__(self, arbre: ArbreDuProjet | None = None,
                 supprimer: Callable[[NoeudAffiche], None] | None = None,
                 pas_du_rotor: int = 0, *,
                 dossier=None,
                 ajouter: Callable[[], None] | None = None,
                 relinker: Callable[[str], None] | None = None) -> None:
        super().__init__()
        self.arbre = arbre
        self._supprimer = supprimer
        self.pas_du_rotor = pas_du_rotor
        #: Le dossier du projet, quand l'appelant le donne. Il ne sert **qu'a
        #: relire** (:meth:`reprendre`) : l'ecran ne lit aucun disque de
        #: lui-meme, `ouvrir_l_inventaire_du_projet` lui pose son arbre deja
        #: mesure. Un banc qui monte l'ecran nu n'a donc rien a fournir, et
        #: `reprendre` se contente alors de redessiner -- ce qui est le
        #: comportement d'avant, pas une version degradee.
        self.dossier = dossier
        #: `Ctrl+A` et `Ctrl+L`, injectes par l'ouvreur. Ils portent le meme
        #: contrat que `supprimer` : absents, la touche NOMME ce qui manque au
        #: lieu de se taire (finding `K1.1a`).
        self._ajouter = ajouter
        self._relinker = relinker
        #: Le message d'un geste REFUSE, pose sur la ligne d'etat le temps
        #: d'une touche. Meme mecanisme que `palier_projet._etat_a_dire`, et
        #: pour le meme motif : une touche annoncee qui ne fait rien est
        #: indistinguable d'un clavier casse (finding `K1.1a`).
        self._message = ""

    def poser_la_suppression(
            self, rappel: "Callable[[NoeudAffiche], None] | None") -> None:
        """Poser APRES construction le rappel que `Suppr` declenche.

        **Le noeud est reel et il ne se denoue pas dans un constructeur** : le
        rappel de suppression a besoin de l'ecran -- il lui demande son noeud
        courant et lui monte `E6-2` par-dessus --, et l'ecran a besoin du
        rappel. Un ecran ne peut pas se citer dans son propre appel de
        construction, donc l'un des deux se pose en second. C'est le meme geste
        que `projet_suppression.ouvrir_la_suppression`.

        **Ce que cette methode ajoute a l'affectation directe, et ce n'est pas
        du confort.** Sans elle, le seul cablage possible est
        `ecran._supprimer = ...` depuis l'exterieur -- ce qu'un banc peut se
        permettre et ce qu'un PRODUIT ne peut pas. Poser un attribut prive
        depuis un autre module fait de la forme du champ une interface, si bien
        que le renommer casse un appelant qui n'etait cense connaitre que
        l'ecran. Signale par la session coordinatrice de l'Epic 11 le
        2026-09-06, en concevant le cablage du palier.

        `None` **retire** le cablage plutot que d'etre refuse : un ecran sans
        rappel n'est pas casse, il repond `CE_QUI_MANQUE_A_LA_SUPPRESSION` --
        une touche annoncee qui dit ce qui manque, jamais une touche muette.

        **Le PRODUIT ne l'appelle plus depuis le 2026-09-06, et il faut savoir
        pourquoi avant de la reintroduire quelque part.** La reconciliation des
        deux ouvreurs du palier Projet a mesure que la route par setter rend
        `test_rappels_cables.py::test_les_RAPPELS_acceptes_par_les_ecrans_sont_INJECTES_ou_DECLARES`
        ROUGE : cette garde lit les **mots-cles des appels** sur l'arbre
        syntaxique et ne voit aucune affectation d'attribut, si bien que
        `("EcranInventaireDuProjet", "supprimer")` y redevient un rappel
        optionnel qu'aucun appel n'injecte. `ouvrir_l_inventaire_du_projet`
        passe donc `supprimer=` **a la construction**, par la methode liee de
        :class:`_CablageDeLaSuppression`.

        Cette methode reste : elle est l'API publique du champ, mesuree dans
        les deux sens, et c'est elle qui evite qu'un appelant ecrive
        `ecran._supprimer = ...`. Mais elle n'a plus de site d'appel de
        production, ce qui est **nomme** dans `deferred-work.md` plutot que
        laisse silencieux -- une surface publique sans appelant est exactement
        la forme que ce depot a payee quatre fois dans cet epic.
        """
        self._supprimer = rappel

    # -- lecture --------------------------------------------------------------

    @property
    def en_lecture(self) -> bool:
        """`E6-1a` tant qu'aucun arbre n'est pose."""
        return self.arbre is None

    def composer(self, largeur: int, ascii_seul: bool = False
                 ) -> tuple[list[str], int | None, dict[int, str]]:
        """Le corps de l'ecran, **sous la hauteur de la zone centrale**.

        Les respirations sont sacrifiables et tombent de haut en bas : c'est le
        budget de `Composition`, qui existe parce que `textual` coupe par le
        bas, en silence. `E6-1e` en fait la mesure -- son arbre deplie reclame
        les dix-sept lignes, et les deux blancs tombent.
        """
        utile = jetons.largeur_utile(largeur)
        composition = Composition()
        composition.respirer()
        composition.poser(f"  {self._titre_du_projet()}")
        composition.respirer()
        if self.en_lecture:
            composition.poser(
                " " * 5 + jetons.rotor(self.pas_du_rotor, ascii_seul)
                + f"  {_replie(PHRASE_DE_LECTURE, ascii_seul)}")
            composition.respirer()
            composition.poser("   " + ("-" if ascii_seul else "─")
                              * (utile - _MARGE_DE_LA_REGLE))
            composition.respirer()
            composition.poser(*[" " * 5 + _replie(ligne, ascii_seul)
                                for ligne in CORPS_DE_LECTURE])
            return composition.rendu(jetons.hauteur_centrale())
        composition.bloc(self.arbre.lignes_de_l_arbre(ascii_seul),
                         etats=self.arbre.etats_des_lignes(),
                         curseur=self.arbre.rang_du_curseur())
        return composition.rendu(jetons.hauteur_centrale())

    def _titre_du_projet(self) -> str:
        """Le NOM DU PROJET, et rien d'autre (Egan, 2026-09-04, note 1)."""
        if self.arbre is not None and self.arbre.titre:
            return self.arbre.titre
        return getattr(self.app, "nom_du_projet", "") or ""

    def objet_du_bandeau(self) -> str:
        """La droite du bandeau : `inventaire · 801 fichiers · 12,7 Go`.

        **Elle est LUE de l'arbre**, comme la ligne d'etat, et les deux
        chiffres sont ceux du coeur : « tous deux lus de l'inventaire, jamais
        recalcules a l'ecran » (AC 2.3).
        """
        ascii_seul = getattr(self.app, "ascii_seul", False)
        if self.en_lecture:
            return _replie("inventaire · lecture en cours", ascii_seul)
        return _replie(
            "inventaire · "
            f"{grouper_les_milliers(self.arbre.fichiers_total)} fichiers · "
            f"{poids_lisible(self.arbre.poids_total)}", ascii_seul)

    def ligne_d_etat(self, ascii_seul: bool = False) -> str:
        if self.en_lecture:
            return _replie(ETAT_DE_LA_LECTURE, ascii_seul)
        return (self.arbre.ligne_de_l_ecart(ascii_seul)
                or self.arbre.ligne_de_compte(ascii_seul))

    def lignes(self) -> list[str]:
        return self.composer(self.app.size.width, self.app.ascii_seul)[0]

    def etat(self) -> str:
        """Le message d'un geste refuse PRIME sur le compte, le temps d'une touche."""
        if self._message:
            return _replie(self._message, self.app.ascii_seul)
        return self.ligne_d_etat(self.app.ascii_seul)

    # -- rendu ----------------------------------------------------------------

    def contenu(self) -> list[Widget]:
        self._corps = Static("", id=self.ID_DU_CORPS)
        return [Vertical(self._corps, id=f"centre-{self.ID_DU_CORPS}")]

    def _appliquer_les_raccourcis(self) -> None:
        """Poser la ligne de raccourcis du MOMENT courant (finding `I8`).

        Une constante de module posee sur l'instance, jamais une propriete :
        la garde d'epic de `test_repli_ascii.py` balaye les sous-classes de
        `Palier` et lit `classe.raccourcis` **au niveau de la CLASSE** -- une
        propriete y rendrait l'objet `property` et ferait echapper l'ecran a la
        mesure. Meme geste que `EcranChiffre` et `EcranProjet`.
        """
        self.raccourcis = (RACCOURCIS_LECTURE if self.en_lecture
                           else self.arbre.raccourcis())

    def rafraichir(self) -> None:
        if not self._assez_grand_au_dernier_dessin:
            return
        largeur = jetons.largeur_utile(self.app.size.width)
        self._appliquer_les_raccourcis()
        lignes, rang, etats = self.composer(self.app.size.width,
                                            self.app.ascii_seul)
        self._corps.update(jetons.peindre(
            [jetons.ajuster(ligne, largeur, self.app.ascii_seul)
             for ligne in lignes],
            ascii_seul=self.app.ascii_seul,
            sans_couleur=self.app.sans_couleur,
            ligne_du_curseur=rang, etats=etats))
        self.poser_etat(self.etat())
        super().rafraichir()

    def on_mount(self) -> None:
        self.rafraichir()

    # -- clavier --------------------------------------------------------------

    def on_key(self, evenement) -> None:
        if self.traiter(evenement.key, getattr(evenement, "character", None)):
            evenement.stop()
            self.rafraichir()

    def traiter(self, touche: str, caractere: str | None = None) -> bool:
        """Mesurable sans clavier, comme tous les ecrans du depot.

        **Aucune touche n'agit pendant la lecture** : `E6-1a` n'annonce que
        `F1`, et une touche qui agirait sans etre annoncee serait le symetrique
        du finding `I8`.
        """
        self._message = ""
        if self.en_lecture:
            return False
        if touche in ("up", "down"):
            self.arbre.deplacer(-1 if touche == "up" else 1)
            return True
        if touche == "right":
            self.arbre.deplier()
            return True
        if touche == "left":
            self.arbre.replier()
            return True
        if touche == "space" or caractere == " ":
            # **Plus aucun refus a prononcer ici depuis `EPIC11-ARB-264`** : un
            # groupe se coche comme le reste, et `basculer` ne rend faux que
            # sur un arbre VIDE -- c'est l'absence d'objet, pas un refus, et
            # `EPIC11-ARB-258` n'en demande pas de mot.
            self.arbre.basculer()
            return True
        if touche == "delete":
            return self._retirer()
        if touche == "ctrl+a":
            return self._ajouter_un_media()
        if touche == "ctrl+d":
            # **Sans echeance, et c'est la seule des trois touches a rester un
            # filet** : ce qui lui manque est un point d'entree de coeur, pas
            # un dessin. Voir :data:`CE_QUI_MANQUE_A_LA_DECLARATION`.
            return self._pas_encore(CE_QUI_MANQUE_A_LA_DECLARATION, "")
        if touche == "ctrl+l":
            return self._relinker_l_objet()
        return False

    def _ajouter_un_media(self) -> bool:
        """`Ctrl+A` : designer un fichier sur le disque et le declarer.

        **Cette touche ne lit NI le curseur NI la selection**, et c'est la
        seule des trois : ajouter un media ne vise rien de ce que l'arbre
        montre, puisque ce qu'on ajoute n'y est pas encore. Lui faire visiter
        `visee()` aurait fabrique un refus la ou il n'y a pas de cible a
        refuser.

        Le parcours vit dans `tui/projet_medias.py` et il monte l'ecran qui
        existe deja -- `E2-1` avec son explorateur, son panneau chiffre
        `E2-1e` et son refus de conflit `E2-1f`. Voir le docstring de ce
        module-la pour ce que la mesure a trouve.
        """
        if self._ajouter is None:
            return self._pas_encore(CE_QUI_MANQUE_A_L_AJOUT)
        self._ajouter()
        return True

    def _relinker_l_objet(self) -> bool:
        """`Ctrl+L` : repointer un objet declare dont le fichier a bouge.

        **La cible est celle de l'arbre**, comme `Suppr` : la selection cochee
        quand il y en a une, la ligne active sinon (`EPIC11-ARB-257`,
        `ArbreDuProjet.visee`). Lire le curseur ici aurait rouvert le piege
        exact qu'Egan a rencontre le 2026-09-06 -- un objet coche, le geste
        parti sur un autre.

        **Quatre refus, et les quatre se DISENT** (`EPIC11-ARB-258`) : la ligne
        de raccourcis annonce `Ctrl+L relinker` des que la ligne active porte
        un rush declare ou un objet declare absent -- et `visee()` peut rendre
        autre chose que cette ligne-la --, donc la touche ne peut jamais etre
        muette.

        * plusieurs lignes cochees -> le motif de `visee()`, mono-cible ;
        * un GROUPE -> il n'est pas un objet du produit, ses membres se
          relinkent un par un ;
        * un objet qui n'est pas un rush -> **le coeur ne sait relinker qu'un
          rush**, et c'est une limite mesuree, pas un oubli : `mmu relink`
          prend un `--rush`, `relink.appliquer_relink` ecrit dans `rushes[]`,
          et aucun chemin du depot ne repointe un lot, un master, une planche
          ni un scan. Le dire est la seule issue honnete ; l'ecran de manque
          promettrait une echeance qui n'existe pas ;
        * un rush que le manifeste ne connait PAS -> il n'y a pas de lien a
          refaire, il y a une declaration a faire, et c'est l'autre touche.

        **Ce que la mesure a corrige, et le brief de ce lot se trompait**
        (2026-09-07) : il n'y a **aucune** garde sur `ETAT_DECLARE_ABSENT`
        ici, et il ne peut pas y en avoir. `project_inventory` construit un
        noeud de rush avec `chemin=None` et `etat=ETAT_PRESENT` des qu'il est
        au manifeste (`ETAT_NON_DECLARE` sinon) : il ne regarde **jamais** si
        le `source_path` du rush existe, la source vivant hors du projet. Un
        rush delie est donc indistinguable d'un rush lie **dans l'arbre**, et
        la seule chose qui sache la difference est
        `relink.statut_de_liaison`, que le parcours interroge. Refuser ici sur
        l'etat aurait ferme le relink pour **tous** les rushes, sans un mot --
        c'est-a-dire exactement le contraire de ce que la touche existe pour
        faire. Le refus « deja lie » est donc porte par la porte
        (`projet_medias.MOTIF_RUSH_DEJA_LIE`), qui l'a mesure.
        """
        noeud, motif = self.arbre.visee()
        if motif:
            self._message = motif
            return True
        if noeud is None:
            return False
        if noeud.groupe or noeud.cible is None:
            self._message = MOTIF_DU_GROUPE_NON_RELINKABLE
            return True
        if noeud.nature != NATURE_RUSH:
            self._message = MOTIF_DU_RELINK_HORS_RUSH.format(
                nature=libelles_de_nature(noeud.nature)[0])
            return True
        if noeud.etat == ETAT_NON_DECLARE:
            self._message = MOTIF_DU_RUSH_NON_DECLARE.format(
                rush_id=noeud.cible.nom)
            return True
        if self._relinker is None:
            return self._pas_encore(CE_QUI_MANQUE_AU_RELINK)
        self._relinker(noeud.cible.nom)
        return True

    def _retirer(self) -> bool:
        """`Suppr` : monter la confirmation sur ce que l'arbre DESIGNE.

        **Ce n'est plus « le noeud sous le curseur »** : c'est ce que
        :meth:`ArbreDuProjet.visee` rend, c'est-a-dire la selection cochee
        quand il y en a une et la ligne active sinon (`EPIC11-ARB-257`). Tant
        que ce gestionnaire lisait `courant`, la propriete `coches` n'avait
        **aucun consommateur en production** : `Espace` dessinait une croix qui
        ne produisait rien, et `Suppr` agissait ailleurs que la ou l'operateur
        avait designe.

        **Cet ecran ne supprime rien lui-meme** (AC 4.1), et une frontiere
        negative le mesure a l'AST : aucun `unlink`, `rmtree` ni `remove` n'y
        apparait. Il monte un point de jugement chiffre, et c'est tout.
        """
        noeud, motif = self.arbre.visee()
        if motif:
            self._message = motif
            return True
        if noeud is None:
            return False
        if not noeud.groupe and noeud.cible is None:
            # **Le refus se DIT** (finding `F5` de la couche 1). Les deux
            # lignes de raccourcis annoncent `Suppr retirer`
            # inconditionnellement ; rendre `False` en silence laissait
            # `on_key` ne rien faire et ne rien dire.
            #
            # **Le GROUPE est SORTI de cette branche le 2026-09-07**
            # (`EPIC11-ARB-264`). Un groupe reste un niveau d'AFFICHAGE que le
            # coeur ne nomme pas -- c'est toujours vrai --, mais le supprimer
            # est desormais N appels que `remove_project_group` porte, et
            # `ouvrir_la_suppression` deplie la ligne en N cibles. Ce qui reste
            # ici est le noeud SANS objet de coeur et sans membres : ni un
            # groupe depliable, ni une cible.
            #
            # **Et la phrase a suivi la branche le 2026-09-07** (`C1-4` /
            # `C2-3`) : elle parlait encore du groupe, c'est-a-dire du seul cas
            # que cette condition exclut. Le motif du renommage, et pourquoi la
            # branche est gardee plutot que retiree, vivent sur la constante.
            self._message = MOTIF_DU_NOEUD_SANS_OBJET
            return True
        if self._supprimer is not None:
            self._supprimer(noeud)
        else:
            self._pas_encore(CE_QUI_MANQUE_A_LA_SUPPRESSION)
        return True

    def _pas_encore(self, ce_qui_manque: str,
                    quand: str = QUAND_LA_GESTION_DES_MEDIAS) -> bool:
        """Une touche annoncee qui mene a une absence **le DIT**.

        Un `if ... is not None` sans branche `else` rendrait la touche
        indistinguable d'un clavier casse -- c'est litteralement le finding
        `K1.1a`, et la garde structurelle des rappels existe pour l'attraper.

        **L'echeance est un ARGUMENT depuis le 2026-09-07**, et ce n'est pas
        de la souplesse : les sites de cette methode ne demandent plus la meme
        chose. Ceux qui attendent un ecran gardent
        :data:`QUAND_LA_GESTION_DES_MEDIAS` ; `Ctrl+D`, lui, attend un point
        d'entree de coeur et n'a **aucune** echeance a annoncer -- une echeance
        qui nomme l'endroit d'ou l'on frappe fait attendre quelque chose qui est
        deja la (`EPIC11-ARB-260`, meme geste sur `projet_suppression`).
        """
        application = _application_montee(self)
        if application is None:
            return True
        application.descendre(EcranPasEncore(ce_qui_manque, quand))
        return True

    def reprendre(self) -> None:
        """Ce que cet ecran fait quand on **revient** dessus : il relit d'abord.

        **Elle ferme un apercu qui mentirait** (`EPIC11-ARB-46`). Depuis que
        `Ctrl+A` declare un rush et que `Ctrl+L` en relinke un, revenir sur
        l'inventaire montrait l'arbre d'AVANT l'ecriture : un rush qui vient
        d'etre declare n'y figurait pas, et un rush relinke y restait marque
        absent. C'est exactement le defaut `V2-M2` -- « un menu gardait les
        compteurs du projet precedent » --, et le palier au-dessus le ferme du
        meme geste.

        Sans dossier, elle se contente de redessiner : c'est le comportement
        d'avant, pour un ecran monte nu par un banc. `relire_l_inventaire` ne
        leve jamais et garde l'arbre precedent quand le coeur refuse le
        manifeste -- un arbre vide dirait « ce projet n'a rien » la ou il faut
        dire « je n'ai pas pu relire ».
        """
        if self.dossier:
            relire_l_inventaire(self, self.dossier)
        super().reprendre()


#: Ce que `Suppr` demande quand aucun appelant n'a cable la confirmation.
CE_QUI_MANQUE_A_LA_SUPPRESSION = "Retirer cet objet du projet"

#: Ce que la ligne d'etat dit quand `Suppr` vise un noeud qui ne porte NI
#: objet de coeur NI membres.
#:
#: **Renommee et reecrite le 2026-09-07** (findings `C1-4` / `C2-3`, trouves
#: par deux couches). Elle s'appelait `MOTIF_DU_GROUPE_NON_SUPPRIMABLE` et
#: disait « Un groupe n'est pas un objet : ses elements se retirent un par
#: un. » -- c'est-a-dire exactement ce que sa propre branche EXCLUT depuis
#: qu'`EPIC11-ARB-264` a sorti le groupe de la condition (`not noeud.groupe
#: and noeud.cible is None`). Trois bancs ressemblaient donc a une couverture
#: du refus de GROUPE sans en etre une : ils fabriquaient un noeud de synthese
#: et lisaient une phrase qui parlait d'autre chose.
#:
#: **La branche est GARDEE, et c'est une mesure et non un gout.** Aucun des
#: sept sites de construction de :class:`NoeudAffiche` de ce module ne produit
#: cet etat -- ils posent tous soit `groupe=True`, soit une `cible` non nulle,
#: et `depuis_l_inventaire` est le seul batisseur d'arbre en production. Mais
#: le type le PERMET (`__post_init__` n'interdit que l'inverse, `groupe` avec
#: une `cible`), et la seule autre issue mesuree ment sur la cause : sans
#: cette branche, le noeud descend a `projet_suppression.motif_sans_cible`,
#: qui rend `OBJET_SANS_LOT` -- « n'est rattaché à aucun lot de ce projet »,
#: faux dans ses deux moities sur un noeud qui ne porte aucun objet. Un refus
#: qui nomme la mauvaise cause est pire qu'un refus de plus.
#:
#: Il ne dit pas seulement « non » : il dit ce qui MARCHE, parce qu'un refus
#: qui n'offre aucune issue est aussi fautif qu'une destruction silencieuse
#: (`EPIC11-ARB-89`) -- et ce qui marche, depuis `EPIC11-ARB-264`, est un
#: objet **ou** un groupe.
#:
#: MESURE: 71/76.
MOTIF_DU_NOEUD_SANS_OBJET = (
    "Cette ligne ne porte ni objet ni élément : visez un objet ou un groupe.")

#: Ce que la ligne d'etat dit quand `Suppr` trouve PLUSIEURS lignes cochees.
#:
#: **Une LIMITE nommee, pas un refus de principe** (`EPIC11-ARB-257`). Le
#: modele de suppression est mono-cible de bout en bout et aucune maquette
#: validee ne dessine un cartouche a N cibles -- `EPIC11-ARB-144` interdit d'en
#: coder un sans elle. Ce que cette phrase remplace est pire que ce qu'elle
#: dit : `Suppr` agissait alors **en silence sur la ligne active**, c'est-a-dire
#: sur un objet que l'operateur n'avait pas designe.
#:
#: MESURE: 54/76 au cardinal a deux chiffres.
MOTIF_DE_LA_SELECTION_MULTIPLE = (
    "{cardinal} objets cochés : le retrait vise un objet à la fois.")

#: Ce que la ligne d'etat dit quand `Ctrl+L` vise un GROUPE.
#:
#: Meme famille et meme motif que ses deux voisins ci-dessus : la ligne de
#: raccourcis annonce `Ctrl+L relinker` sans savoir ce que la selection porte,
#: donc la touche ne peut pas etre muette la ou elle refuse -- et le refus dit
#: ce qui MARCHE, parce qu'un refus sans issue est aussi fautif qu'une
#: destruction silencieuse (`EPIC11-ARB-89`).
#:
#: MESURE: 63/76.
MOTIF_DU_GROUPE_NON_RELINKABLE = (
    "Un groupe ne se relinke pas : ses éléments un par un.")

#: Ce que la ligne d'etat dit quand `Ctrl+L` vise un objet qui n'est pas un
#: rush.
#:
#: **C'est une LIMITE DU COEUR, nommee plutot que tue**, et elle est mesuree
#: (2026-09-07) : `mmu relink` prend un `--rush`, `relink.appliquer_relink`
#: ecrit dans `rushes[]` du manifeste, et aucun chemin du depot ne repointe un
#: lot, un master, une planche ou un scan. Ce n'est donc pas un ecran qui
#: manque -- `EcranPasEncore` promettrait une echeance que rien ne porte --,
#: c'est un mot-cle de coeur, exactement comme la cible fine de la suppression
#: (`EPIC11-ARB-260`). La phrase le dit, et elle nomme la nature visee pour que
#: l'operateur sache que la machine a bien lu sa selection.
#:
#: MESURE: 66/76 sur `frames extraites`, la plus longue des natures.
MOTIF_DU_RELINK_HORS_RUSH = (
    "Seul un rush se relinke ; {nature} ne s'y prête pas.")

#: Ce que la ligne d'etat dit quand `Ctrl+L` vise un rush que le manifeste **ne
#: connait pas** -- un ORPHELIN, trouve sur le disque et jamais declare.
#:
#: Le cas s'atteint : `project_inventory` greffe un noeud de rush
#: `ETAT_NON_DECLARE` pour tout identifiant lu du disque et absent de
#: `rushes[]`. Il n'y a alors aucun lien a refaire, il y a une declaration a
#: faire -- et le refus dit laquelle des deux touches la fait, parce qu'un
#: refus sans issue est aussi fautif qu'une destruction silencieuse
#: (`EPIC11-ARB-89`).
#:
#: MESURE: 66/76 sur un identifiant de dix caracteres.
MOTIF_DU_RUSH_NON_DECLARE = (
    "{rush_id} n'est pas au manifeste : c'est Ctrl+A qui le déclare.")


# ---------------------------------------------------------------------------
# L'OUVREUR : le seul point par lequel le produit atteint cet ecran
# ---------------------------------------------------------------------------

#: Ce qui manque quand l'entree « Gestion des medias » est atteinte sans
#: qu'aucun projet ne soit ouvert. Le cas n'arrive pas dans le parcours reel --
#: le palier Projet ne se monte qu'apres `ChaineReelle.ouvrir` --, mais un
#: rappel qui suppose son appelant est exactement ce que la garde des rappels
#: existe pour attraper : une touche annoncee qui ne fait RIEN est
#: indistinguable d'un clavier casse (finding `K1.1a`).
CE_QUI_MANQUE_SANS_PROJET = "L'inventaire, tant qu'aucun projet n'est ouvert"


#: Ce qui separe deux mots dans un nom de classe en casse chameau. Pose une
#: fois : la derivation du code de refus est la seule a s'en servir.
_AVANT_UNE_MAJUSCULE = re.compile(r"(?<!^)(?=[A-Z])")


def code_du_refus(refus: BaseException) -> str:
    """Le code d'un refus d'inventaire, **derive de son nom de classe**.

    Les quatre refus du coeur ne portent pas d'attribut `code` : ce sont des
    classes, et c'est leur nom qui les nomme. `ProjetIntrouvable` rend donc
    `PROJET_INTROUVABLE`, qui est la forme des codes que les autres ecrans de
    refus du depot affichent (`AUCUN_LOT_A_ENCODER`, par exemple).

    **Une derivation plutot qu'une table**, et c'est un choix mesure : une
    table serait une seconde redaction du coeur, qui perimerait **en silence**
    le jour ou un cinquieme refus serait publie -- l'ecran afficherait alors un
    code vide ou celui d'un autre refus. La derivation, elle, nomme un refus
    qu'elle n'a jamais vu, et une frontiere le mesure sur un refus de synthese
    inconnu de ce module.
    """
    return _AVANT_UNE_MAJUSCULE.sub("_", type(refus).__name__).upper()


def refus_de_l_inventaire(refus: InventaireError) -> EcranRefus:
    """L'ecran d'un refus de lecture du projet. Le message y voyage VERBATIM.

    **Un refus du coeur n'est pas un « pas encore », et le distinguo n'est pas
    de style** (tranche le 2026-09-06 en reconciliant les deux ouvreurs du
    palier Projet). `EcranPasEncore` dit « cet ecran n'existe pas encore » :
    il annonce une absence a venir, et le lot `MQ-A` vient de lui imposer une
    echeance pour cette raison meme. Un `project.json` illisible n'annonce
    rien : **rien n'est a venir, un fichier ne se lit pas**. Le mettre sous un
    « pas encore » ferait promettre a l'outil qu'il saura un jour lire ce
    fichier-la, ce qui est faux, et ferait disparaitre le code du refus.

    `EPIC11-ARB-30` : le code **et** la phrase viennent du coeur. Rien n'est
    ajoute a la phrase levee, et rien n'en est retire -- l'ecran la pose telle
    quelle, et son banc mesure une sur-chaine exacte.

    **L'ecran est `execution.EcranRefus`, et il n'y en a pas de neuf.**
    `EPIC11-ARB-144` interdit de coder un dessin qu'aucune maquette ne porte,
    et aucune ne dessine ce refus-la ; `EcranRefus` est deja valide et deja
    monte par huit sites. Ses deux sorties -- `⏎ revenir aux ateliers`,
    `Q quitter` -- satisfont `EPIC11-ARB-89` : jamais une seule issue, jamais
    un blocage sec. **Et pas une troisieme** : `EPIC11-ARB-147` a tranche
    qu'« un refus qui ne detruit rien n'a pas besoin d'issue de secours, et lui
    en fabriquer une produit un ecran qui demande de choisir entre deux facons
    de ne rien faire ». Ces quatre refus n'ecrivent rien.

    Ni `conserve` ni `non_ecrit` ne sont renseignes, et c'est un fait et non un
    oubli : lire un inventaire n'ecrit rien, donc il n'y a ni ce qui a ete
    garde ni ce qui n'a pas ete ecrit a dire.
    """
    return EcranRefus(code_du_refus(refus), str(refus))


class _CablageDeLaSuppression:
    """Le porteur qui permet d'injecter `supprimer=` A LA CONSTRUCTION.

    **Le noeud est reel** : `cabler_la_suppression` a besoin de l'ecran, et
    l'ecran a besoin du rappel. :meth:`poser_la_suppression` le denoue en
    posant le rappel apres coup, et c'est une API publique correcte -- mais
    **une garde du depot ne la voit pas**, et c'est mesure : le
    2026-09-06, la route par setter rend
    `test_rappels_cables.py::test_les_RAPPELS_acceptes_par_les_ecrans_sont_INJECTES_ou_DECLARES`
    ROUGE, `("EcranInventaireDuProjet", "supprimer")` redevenant un rappel
    optionnel qu'aucun appel n'injecte. Cette garde lit les **mots-cles des
    appels** sur l'arbre syntaxique et jamais les affectations d'attributs :
    c'est la lecon du finding `I3`, ou le nom etait partout dans les
    commentaires et nulle part dans le code.

    Une **methode liee** rompt le cycle sans rien perdre : elle existe avant
    l'ecran, donc elle se passe en mot-cle de construction, et elle retrouve
    l'ecran au moment ou la touche est frappee. C'est exactement le geste que
    `ChaineReelle` documente pour elle-meme -- « les methodes liees rompent le
    cycle sans toucher aux attributs prives des ecrans ».
    """

    def __init__(self, projet, arbre: "ArbreDuProjet", *,
                 retirer_du_projet=None) -> None:
        self.projet = projet
        self.arbre = arbre
        self.retirer_du_projet = retirer_du_projet
        #: Pose juste apres la construction de l'ecran. Il n'y a pas d'instant
        #: ou `supprimer` serait appelable avant : la seule chose qui l'appelle
        #: est une touche de cet ecran-la.
        self.ecran: "EcranInventaireDuProjet | None" = None

    def supprimer(self, noeud: NoeudAffiche) -> bool:
        """`Suppr` sur un noeud : le point de jugement `E6-2`.

        Le rappel est refabrique a chaque frappe plutot que garde : c'est une
        fermeture de trois lignes, et la refabriquer garantit qu'elle lit
        l'arbre et le projet **courants**.

        **L'ARBRE SE LIT DE L'ECRAN, jamais de ce porteur** -- et c'est le
        correctif du 2026-09-07, trouve par la couche 3 de la revue de la
        vague 2. La phrase ci-dessus disait deja « courants » ; le code ne le
        tenait que pour le projet. Ce porteur recoit son arbre **a la
        construction**, et :meth:`EcranInventaireDuProjet.reprendre` en pose un
        AUTRE des le premier montage (`relire_l_inventaire` : `ecran.arbre =
        ArbreDuProjet.depuis_l_inventaire(...)`, pose pour fermer
        `EPIC11-ARB-46`). Les deux arbres divergeaient donc immediatement.

        **Ce que ca coutait, mesure** : `lot_ancetre` cherchait le noeud
        courant -- issu de l'arbre de l'ecran -- dans l'arbre d'avant, qui ne
        le contient plus. Il rendait `None`, et `cible_du_noeud` refusait
        **toute cible fine** : planche, master, scan, lot scanne, frames
        extraites, et tout groupe. C'est-a-dire exactement les trois constats
        de terrain d'Egan des lignes 16, 17 et 23, fermes au coeur et en ligne
        de commande, et refuses au clavier :

            inventaire.arbre is porteur.arbre     -> False
            lot_ancetre(inventaire.arbre, noeud)  -> 'a-premier_25'
            lot_ancetre(porteur.arbre,    noeud)  -> None

        **Pourquoi 255 tests TUI restaient verts** : un LOT ENTIER passe, parce
        que c'est la seule nature qui n'a pas besoin de son `lot_id` -- et le
        seul banc du depot qui joue la chaine complete depuis l'ouvreur vise
        justement un lot.

        L'arbre du porteur reste le repli pour un ecran monte nu par un banc,
        ou `self.ecran` n'a pas ete pose. Il n'est plus la source des lors
        qu'un ecran existe.

        L'import est **differe au corps**, et pour une raison de structure
        plutot que de gout : `projet_suppression` importe ce module-ci -- il
        lit `NoeudAffiche` --, donc un import de tete refermerait le cycle.
        """
        from .projet_suppression import cabler_la_suppression

        cablage = ({} if self.retirer_du_projet is None
                   else {"retirer_du_projet": self.retirer_du_projet})
        arbre = self.arbre if self.ecran is None else self.ecran.arbre
        return cabler_la_suppression(self.ecran, arbre, self.projet,
                                     **cablage)(noeud)


def relire_l_inventaire(ecran, dossier_projet, *,
                        inventorier=inventorier_le_projet) -> bool:
    """Relire le projet SUR LE DISQUE et reposer l'arbre dans `ecran`.

    **Ce que cette fonction ferme, et c'est une regression qu'elle EVITE plutot
    qu'un defaut qu'elle repare.** Tant que « Retour a l'inventaire » remontait
    au menu des ateliers, l'inventaire etait **jete** a chaque suppression et
    reconstruit a la reouverture : l'operateur ne voyait jamais d'arbre perime.
    Le jour ou cette suite mene reellement a l'inventaire, l'ecran retrouve est
    celui d'AVANT la suppression -- il listerait un lot que le coeur vient de
    retirer, c'est-a-dire un apercu qui ment (`EPIC11-ARB-46`).

    **Trois sorties, aucune n'est un blocage sec** (`EPIC11-ARB-89`) :

    * le coeur refuse le manifeste (`InventaireError`) -> faux, et l'arbre
      **precedent reste en place**. Un arbre vide serait pire que perime : il
      dirait « ce projet n'a rien » la ou il dit « je n'ai pas pu relire » ;
    * l'ecran n'est pas monte -> l'arbre est repose quand meme et le
      rafraichissement est saute : c'est le regime d'un banc qui relit hors
      application, et il ne doit pas lever ;
    * tout va bien -> l'arbre du disque remplace l'arbre en memoire, et l'ecran
      se redessine.

    Le curseur repart en tete, et c'est assume : l'objet qu'il visait est
    precisement celui qui vient de disparaitre.
    """
    try:
        inventaire = inventorier(dossier_projet)
    except InventaireError:
        return False
    ecran.arbre = ArbreDuProjet.depuis_l_inventaire(inventaire)
    if getattr(ecran, "is_mounted", False):
        ecran.rafraichir()
    return True


class _CablageDesMedias:
    """Le porteur des deux gestes de media, pour les injecter A LA CONSTRUCTION.

    **Meme noeud, meme denouement et meme mesure que
    :class:`_CablageDeLaSuppression`** : `test_rappels_cables.py` lit les
    mots-cles des APPELS sur l'arbre syntaxique et ne voit aucune affectation
    d'attribut, donc un rappel pose apres coup y redevient « accepte et jamais
    injecte ». Les deux methodes liees existent avant l'ecran, donc elles se
    passent en mot-cle de construction.

    Ce porteur ne connait ni l'arbre ni l'ecran, et c'est ce qui le distingue
    de son voisin : `Ctrl+A` ne vise rien, et `Ctrl+L` recoit son `rush_id` de
    l'ecran qui l'appelle. Il ne porte donc que l'application et le dossier --
    les deux choses que `projet_medias` demande.
    """

    def __init__(self, application, dossier, *,
                 ajouter=None, relinker=None) -> None:
        self.application = application
        self.dossier = dossier
        #: Les deux parcours, **injectes pour la mesure** et par defaut ceux du
        #: produit. Ils sont resolus a l'appel plutot qu'a la construction : un
        #: import de tete de `projet_medias` refermerait le cycle, ce module-la
        #: important `atelier_extraction`, qui n'importe pas celui-ci mais que
        #: celui-ci importe.
        self._ajouter = ajouter
        self._relinker = relinker

    def ajouter(self) -> bool:
        """`Ctrl+A` : le parcours de declaration d'un rush depuis le disque."""
        from .projet_medias import ouvrir_l_ajout_de_media

        parcours = self._ajouter or ouvrir_l_ajout_de_media
        return parcours(self.application, self.dossier)

    def relinker(self, rush_id: str) -> bool:
        """`Ctrl+L` : le parcours de relink, sur le rush que l'arbre designe."""
        from .projet_medias import ouvrir_le_relink_du_rush

        parcours = self._relinker or ouvrir_le_relink_du_rush
        return parcours(self.application, self.dossier, rush_id)


def ouvrir_l_inventaire_du_projet(app, dossier_projet, *,
                                  inventorier=inventorier_le_projet,
                                  retirer_du_projet=None,
                                  ajouter_un_media=None,
                                  relinker_un_rush=None) -> bool:
    """Ce que l'entree *Gestion des medias* du palier Projet ouvre.

    **Cette fonction existe pour une raison de DECOUPAGE, pas de confort.**
    L'ecran, l'arbre et le cablage de la suppression vivent dans ces deux
    modules ; le seul endroit du depot qui monte le palier Projet est
    `atelier_extraction_ecriture.ChaineReelle`, qu'aucun agent de cette story
    n'a le droit d'ouvrir. Sans elle, cabler `E6-1` demanderait d'y ecrire une
    quinzaine de lignes qui savent lire un inventaire, construire un arbre et
    fabriquer un rappel de suppression. Avec elle, il y reste **un `if` et un
    appel** -- la meme forme exactement que `ouvrir_l_atelier_pdf`,
    `ouvrir_l_atelier_scan` et `ouvrir_l_atelier_exports`, qui sont deja
    injectes par `chaine_du_produit` pour ce motif.

    **Ce qu'elle ferme, et qui a un nom dans ce depot** : « un composant livre,
    teste, et cable nulle part dans l'application est un composant que le
    produit n'a pas » (la panne du lot `E9`, citee par `chaine_du_produit`).
    `EcranInventaireDuProjet` etait dans cet etat : deux bancs, 129 tests, et
    aucun chemin depuis le produit.

    **Trois sorties, aucune n'est un blocage sec** (`EPIC11-ARB-89`) :

    * aucune application montee -> faux, et l'appelant sait que rien n'a bouge ;
    * pas de projet, ou le coeur refuse le manifeste (`InventaireError`) ->
      `EcranPasEncore` qui NOMME ce qui manque, avec le message du coeur quand
      il y en a un ;
    * tout va bien -> `E6-1`, avec ses TROIS gestes cables.

    **Trois et non plus un depuis le 2026-09-07** (retour terrain d'Egan du
    2026-09-06 : « Ajouter un media au projet depuis le disque : n'existe pas
    encore »). `Suppr` etait cable ; `Ctrl+A` et `Ctrl+L` menaient tous deux a
    un filet alors que leur coeur **et** leur ecran existaient depuis la story
    11.4. Les deux parcours vivent dans `tui/projet_medias.py` et sont
    **injectes pour la mesure**, leur defaut etant le vrai chemin -- meme forme
    que `retirer_du_projet` ci-dessus. `Ctrl+D`, lui, reste un filet : la
    mesure du 2026-09-07 ne trouve **aucune** commande de coeur qui inscrive au
    manifeste un objet deja present sur le disque.

    L'import de `projet_suppression` est **differe au corps**, et pour une
    raison de structure plutot que de gout : ce module-la importe celui-ci --
    il lit `NoeudAffiche` --, donc un import de tete refermerait le cycle.
    C'est l'idiome du depot, employe partout ou deux modules se tiennent.
    """
    application = _application_montee(app)
    if application is None:
        return False
    if not dossier_projet:
        application.descendre(EcranPasEncore(CE_QUI_MANQUE_SANS_PROJET,
                                             QUAND_LA_GESTION_DES_MEDIAS))
        return True
    try:
        inventaire = inventorier(dossier_projet)
    except InventaireError as refus:
        application.descendre(refus_de_l_inventaire(refus))
        return True

    arbre = ArbreDuProjet.depuis_l_inventaire(inventaire)
    # Le rappel est passe EN MOT-CLE DE CONSTRUCTION, par une methode liee du
    # porteur : c'est la seule route que la garde des rappels cables voit, et
    # c'est mesure (voir `_CablageDeLaSuppression`).
    cablage = _CablageDeLaSuppression(dossier_projet, arbre,
                                      retirer_du_projet=retirer_du_projet)
    medias = _CablageDesMedias(application, dossier_projet,
                               ajouter=ajouter_un_media,
                               relinker=relinker_un_rush)
    # Les TROIS rappels sont passes EN MOT-CLE DE CONSTRUCTION, par des
    # methodes liees de leur porteur : c'est la seule route que la garde des
    # rappels cables voit, et c'est mesure (voir `_CablageDeLaSuppression`).
    ecran = EcranInventaireDuProjet(arbre, supprimer=cablage.supprimer,
                                    dossier=dossier_projet,
                                    ajouter=medias.ajouter,
                                    relinker=medias.relinker)
    cablage.ecran = ecran
    application.descendre(ecran)
    return True


__all__ = [
    "ArbreDuProjet",
    "CE_QUI_MANQUE_A_LA_DECLARATION",
    "CE_QUI_MANQUE_A_L_AJOUT",
    "CE_QUI_MANQUE_A_LA_SUPPRESSION",
    "CE_QUI_MANQUE_AU_RELINK",
    "CE_QUI_MANQUE_SANS_PROJET",
    "CORPS_DE_LECTURE",
    "EcranInventaireDuProjet",
    "ETAT_DE_LA_LECTURE",
    "ETAT_DE_L_OBJET_ABSENT",
    "ETAT_DE_L_OBJET_NON_DECLARE",
    "ETAT_DU_CHEMIN_ATTENDU",
    "FICHIERS_ARBRE",
    "GROUPES_DECLARES",
    "HAUTEUR_ARBRE",
    "InventaireMalForme",
    "MENTION_NON_DECLARE",
    "MOTIF_DE_LA_SELECTION_MULTIPLE",
    "MOTIF_DU_GROUPE_NON_RELINKABLE",
    "MOTIF_DU_NOEUD_SANS_OBJET",
    "MOTIF_DU_RELINK_HORS_RUSH",
    "MOTIF_DU_RUSH_NON_DECLARE",
    "MOT_DES_ECARTS",
    "MOT_DES_OBJETS",
    "NATURES_AU_LIBELLE_DU_COEUR",
    "NOM_ARBRE",
    "NoeudAffiche",
    "ANCRES_DES_ORPHELINS",
    "ORDRE_DES_GROUPES",
    "PHRASE_DE_LECTURE",
    "PLIAGE_DEPLIE",
    "PLIAGE_REPLIE",
    "POIDS_ARBRE",
    "PROFONDEUR_OBJET",
    "QUAND_LA_GESTION_DES_MEDIAS",
    "RACCOURCIS_INVENTAIRE_DECLARER",
    "RACCOURCIS_INVENTAIRE_RELINKER",
    "RACCOURCIS_LECTURE",
    "TETE_ARBRE",
    "accorder_le_contenu",
    "cardinal_lisible",
    "code_du_refus",
    "greffer_les_orphelins",
    "orphelins_affiches",
    "ouvrir_l_inventaire_du_projet",
    "grouper_les_milliers",
    "libelles_du_contenu",
    "nom_du_groupe",
    "poids_lisible",
    "refus_de_l_inventaire",
    "relire_l_inventaire",
    "tige_et_rang",
    "tige_et_rang_de_fichier",
]
