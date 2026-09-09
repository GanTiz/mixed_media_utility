# -*- coding: utf-8 -*-
"""Story 11.11, lot A (`EPIC11-ARB-155`) : l'INVENTAIRE d'un projet.

Ce module rend l'arbre des objets produits d'un projet -- **rushes -> lots**,
un lot portant ses frames extraites, ses masters, ses planches et ses
**scans**, un scan portant les lots scannes qu'il a produits et chacun ses
frames scannees (story 11.14, `EPIC11-ARB-244`) --, chaque noeud portant son
poids sur le disque et son cardinal de fichiers, **mesures** par un parcours
et jamais estimes.

**L'arbre a QUATRE niveaux sous le projet, et il en a eu cinq pendant un
jour.** `EPIC11-ARB-219` (2026-09-04) faisait du scan un FRERE du lot, pendu
au rush ; `EPIC11-ARB-244` (2026-09-05) en renverse la premiere moitie et
garde la seconde -- Egan, verbatim : « Je change d'avis pour le lot B : le
scan est le fils du lot qu'il reproduit. Le lot scanne est bien le fils du
scan. » Ce qui a change n'est donc QUE le parent du scan ; la filiation
scan -> lot scanne -> frames scannees est celle d'`ARB-219`, intacte.

**Pourquoi il existe.** Les ecrans de liste de la TUI listent ce qu'ils vont
**consommer** : l'Extraction liste des rushes parce qu'elle en extrait, le Pdf
liste des lots parce qu'il les met en pages. Une **planche produite** n'est
l'entree d'aucun atelier, donc aucune liste ne peut l'afficher, et elle est
invisible pour toujours (Egan, 2026-09-01, verbatim : « il manque un ecran pour
ca car rien ne consomme une planche »). Le meme raisonnement vaut pour un
master encode et pour un scan ingere.

**Signature de producteur** (AC 1.1) : :func:`inventorier_le_projet` ne prend
aucun `args`, n'imprime rien et ne rend aucun code de sortie. Elle **leve** ce
qui refuse -- la table de ces refus est publiee, voir :data:`REFUS_DU_COEUR` --
et elle **rend** un document. La mise en forme appartient a ses enveloppeurs.

**Les deux ecarts entre le manifeste et le disque sont l'information la plus
utile de cet inventaire**, et ils sont symetriques :

* :data:`ETAT_DECLARE_ABSENT` (AC 1.3) -- l'objet est declare au manifeste et
  introuvable sur le disque. Il est **nomme**, jamais tu, et jamais confondu
  avec un objet de poids zero : un dossier de frames vide EXISTE (il porte
  :data:`ETAT_PRESENT` et un poids nul), un dossier de frames efface n'existe
  pas. Meme exigence que `fichiers_attendus_absents` de
  `project_maintenance.RapportSuppression`, et pour le meme motif ;
* :data:`ETAT_NON_DECLARE` (AC 1.4) -- l'objet est sur le disque et aucun
  manifeste ne le declare. **C'est le vrai livrable de ce lot** : c'est
  exactement ce que produit un nettoyage manuel interrompu -- celui du
  2026-08-27, qui a detruit des frames irrecuperables --, et rien dans le depot
  ne le montrait.

**Ce module ne LIT qu'une filiation, celle de `project_maintenance`.** Les
chemins des masters, des planches et des dossiers de scan d'un lot sont lus par
les fonctions de ce module-la, importees telles quelles plutot que redigees ici
(`EPIC11-ARB-108`, « il n'y a pas de mecanisme different par objet » ; et le
grief mesure de la story 11.6 : « deux copies d'une meme regle divergent au
premier ajustement »). Elles portent aujourd'hui un souligne de tete parce
qu'elles n'avaient qu'un appelant ; les publier est un geste qui appartient a
une story qui touche `project_maintenance`, et cet inventaire n'en touche pas
une ligne. `test_inventaire_de_projet` mesure l'ACCORD des deux lectures en
confrontant cet inventaire au rapport de `remove_project_element(dry_run=True)`
sur le meme lot -- une egalite d'ensembles, dans les deux sens.

**Aucun nom n'est compose ici** (AC 1.1, tache A2). Les noms de dossiers
viennent de `io.project_layout`, les marqueurs de fichiers et la lecture d'un
rang de version de `io.naming`, le nom du manifeste de `io.extraction_manifest`.
Un banc mesure a l'AST qu'aucun de ces fragments n'est un litteral de ce
module.

**Ce que cet inventaire NE mesure PAS, dit plutot que tu :**

* le **fichier source d'un rush** ne pese rien ici. Il vit hors du dossier
  projet (`rushes[].source_path`, invariant de portabilite v2) : le compter
  ferait figurer au poids du projet des octets que supprimer le projet ne
  libererait pas ;
* le poids d'un noeud est celui de son emplacement propre, et le poids total
  la **somme** des noeuds. L'arborescence v2 garantit que ces emplacements sont
  disjoints (`extract-frames/`, `frames-scannees/`, `outputs/`,
  `planches/`, `scans/`) ;
  un manifeste qui declarerait un master **dans** un dossier de frames ferait
  compter ses octets deux fois. Le cas est refuse ailleurs -- deux lots ne
  partagent ni master ni planche (`_refuser_l_annexe_partagee`) -- mais pas
  ici, et cet inventaire ne supprime rien ;
* les dossiers `logs/` et `versions/` ne sont pas des objets produits par un
  lot : ils ne figurent ni dans l'arbre ni parmi les orphelins. Un profil de
  calibration n'est pas un objet supprimable de la liste d'`EPIC11-ARB-104`.
  **Precise le 2026-09-07 (`EPIC11-ARB-262`)** : `versions/calibration/` est
  desormais LU, pour y chercher le dossier de scan qu'un profil DECLARE. La
  phrase ci-dessus ne change pas de sens -- un profil reste un non-objet, il
  n'entre ni dans l'arbre ni dans aucune liste --, mais il serait faux de lire
  « ce module n'ouvre jamais `versions/` ». Il l'ouvre comme il ouvre le
  manifeste : pour lire une declaration, jamais pour inventorier son contenu.
"""
from __future__ import annotations

import stat as stat_module
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterator, Mapping

from .io import calibration_profile, naming, project_layout, version_ranks
from .io.extraction_manifest import MANIFEST_FILENAME
from .io.manifest import load_manifest
from .project_maintenance import (
    ProjectMaintenanceError,
    _Declares,
    _masters_declares,
    _planche_pdf_declaree,
    _scans_du_lot,
    _sous_le_projet,
)

__all__ = [
    "NATURE_RUSH",
    "NATURE_LOT",
    "NATURE_FRAMES_EXTRAITES",
    "NATURE_MASTER",
    "NATURE_PLANCHE",
    "NATURE_SCAN",
    "NATURE_LOT_SCANNE",
    "NATURE_FRAMES_SCANNEES",
    "NATURES",
    "LIBELLES_DES_NATURES",
    "libelles_de_nature",
    "ETAT_PRESENT",
    "ETAT_DECLARE_ABSENT",
    "ETAT_NON_DECLARE",
    "ETATS",
    "InventaireError",
    "ProjetIntrouvable",
    "ManifesteIntrouvable",
    "ManifesteIllisible",
    "ManifesteIncoherent",
    "REFUS_DU_COEUR",
    "ObjetInventorie",
    "InventaireDuProjet",
    "inventorier_le_projet",
]


# ---------------------------------------------------------------------------
# Le vocabulaire, publie -- une interface le LIT, elle ne le redige pas
# ---------------------------------------------------------------------------

#: Les HUIT natures d'objet de l'arbre. Publiees parce qu'un ecran doit
#: distinguer un master d'une planche pour choisir son glyphe, et qu'une
#: seconde redaction de ce vocabulaire cote interface divergerait au premier
#: ajout -- le defaut exact que la story 11.6 a paye sur la table des refus de
#: `scan_detect`.
#:
#: Aucune de ces valeurs n'est un nom de dossier de l'arborescence v2 : elles
#: nomment une NATURE, pas un emplacement, et les confondre ferait recomposer
#: un chemin a partir d'une etiquette d'affichage.
#:
#: **Story 11.14 (`EPIC11-ARB-214`, `EPIC11-ARB-220`), le vocabulaire d'Egan
#: dans ses mots :** « Un lot est un ensemble de frames extraites depuis le
#: rushe source avec extract. [...] L'ensemble de ces pages une fois scannees
#: forment un scan. A partir d'un scan on reproduit donc un "lot scanne" qui
#: est lui meme un ensemble de "frames scannees". » Deux consequences ecrites
#: ici, et pas ailleurs :
#:
#: * `frames_rescannees` devient :data:`NATURE_FRAMES_SCANNEES`. Le mot
#:   « rescannees » n'etait celui de personne : ni celui du disque
#:   (`output-frames/`), ni celui du manifeste, ni celui d'Egan ;
#: * le lot scanne devient un OBJET a part entiere
#:   (:data:`NATURE_LOT_SCANNE`), la ou le depot ne connaissait que son
#:   contenu. C'est ce qui le rend versionnable et supprimable comme les
#:   autres (`EPIC11-ARB-104`, `EPIC11-ARB-108`).
NATURE_RUSH = "rush"
NATURE_LOT = "lot"
NATURE_FRAMES_EXTRAITES = "frames_extraites"
NATURE_MASTER = "master"
NATURE_PLANCHE = "planche"
NATURE_SCAN = "scan"

#: Le lot reproduit depuis un scan. **Noeud de REGROUPEMENT**, exactement comme
#: :data:`NATURE_LOT` : il ne pese rien de lui-meme et tout son poids vit dans
#: son unique enfant, le dossier de frames scannees. La symetrie est voulue --
#: un lot porte ses frames extraites, un lot scanne porte ses frames scannees
#: -- et c'est elle qui rend la phrase d'Egan lisible dans l'arbre.
NATURE_LOT_SCANNE = "lot_scanne"

#: Le contenu d'un lot scanne : le dossier `frames-scannees/<slug>/` (ou le
#: `output-frames/<slug>/` d'avant, toujours reconnu, `EPIC11-ARB-171`).
NATURE_FRAMES_SCANNEES = "frames_scannees"

NATURES: tuple[str, ...] = (
    NATURE_RUSH,
    NATURE_LOT,
    NATURE_FRAMES_EXTRAITES,
    NATURE_MASTER,
    NATURE_PLANCHE,
    NATURE_SCAN,
    NATURE_LOT_SCANNE,
    NATURE_FRAMES_SCANNEES,
)

#: **Le LIBELLE de chaque nature, au singulier et au pluriel** -- la moitie de
#: la table publiee qu'une SURFACE peut afficher telle quelle (AC 1.3, ferme le
#: 2026-09-04 par la revue couche 3, finding `F2`).
#:
#: **Pourquoi elle existe, et ce que son absence avait deja coute.** Les huit
#: valeurs ci-dessus sont des IDENTIFIANTS (`lot_scanne`), pas des mots
#: francais : aucun ecran ne peut les afficher tels quels. Faute d'un libelle
#: publie, chaque surface en redigeait un -- et deux d'entre elles ont diverge
#: **dans le meme ecran** : `mmu project remove --lot L --lot-scanne --version 2`
#: rendait « element 'L (lot scanne v2)' » (le coeur) juste au-dessus de « les
#: jeux de frames scannees posterieurs » (`cli.py`). Deux mots pour un objet,
#: c'est exactement ce que la story 11.14 existe pour retirer, et
#: `EPIC11-ARB-223` a tranche : « lot scanne », partout.
#:
#: **Le singulier DERIVE de l'identifiant** -- il vaut la nature dont les
#: soulignes sont des espaces --, et c'est mesure dans les deux sens plutot que
#: promis : un troisieme mot ne peut donc pas entrer ici. Le PLURIEL, lui, est
#: declare : aucune regle ne rend « rushes » depuis « rush » sans se tromper
#: ailleurs, et un pluriel calcule par `objet + "s"` est precisement le defaut
#: que la couche 1 a trouve dans `cli.py` (« les jeu de framess posterieurs »).
#:
#: Les deux natures de CONTENU sont deja plurielles : « frames extraites » et
#: « frames scannees » ne bougent pas. Ce n'est pas une omission, c'est la
#: forme du mot.
#: Les natures dont le libelle est DEJA pluriel : « une frames extraites » ne
#: se dit pas, et leur pluriel est leur singulier. Ce n'est pas une omission,
#: c'est la forme du mot -- ce sont les deux natures de CONTENU.
_NATURES_INVARIABLES = (NATURE_FRAMES_EXTRAITES, NATURE_FRAMES_SCANNEES)

#: Les pluriels que la regle ordinaire (« + s ») ne rend PAS, declares un par
#: un. « rushs » et « lot scannes » sont ce que rendrait la regle seule, et le
#: second est litteralement le defaut que la couche 1 a trouve dans `cli.py`
#: (« les jeu de framess posterieurs ») : un pluriel calcule sur un groupe
#: nominal accorde le dernier mot et jamais le premier.
_PLURIELS_IRREGULIERS = {
    NATURE_RUSH: "rushes",
    NATURE_LOT_SCANNE: "lots scannes",
}


def _libelles(nature: str) -> tuple[str, str]:
    """Le couple d'une nature -- le singulier DERIVE de son identifiant."""
    singulier = nature.replace("_", " ")
    if nature in _NATURES_INVARIABLES:
        return singulier, singulier
    return singulier, _PLURIELS_IRREGULIERS.get(nature, singulier + "s")


LIBELLES_DES_NATURES: Mapping[str, tuple[str, str]] = {
    nature: _libelles(nature) for nature in NATURES
}


def libelles_de_nature(nature: str) -> tuple[str, str]:
    """Le couple (singulier, pluriel) d'une nature publiee.

    C'est le point de LECTURE de :data:`LIBELLES_DES_NATURES` : une surface
    appelle cette fonction plutot que de recopier le mot. Une nature inconnue
    rend le `KeyError` ordinaire de la table -- ce module ne LEVE que ses
    quatre refus propres, et une frontiere le mesure (AC 1.6) : un refus
    supplementaire ici serait un cinquieme refus non publie.
    """
    return LIBELLES_DES_NATURES[nature]


#: Declare au manifeste ET trouve a son emplacement. Un poids nul est ici une
#: information vraie : le dossier existe et il est vide.
ETAT_PRESENT = "present"

#: **AC 1.3** -- declare au manifeste, introuvable sur le disque. L'objet est
#: rendu quand meme, avec son nom et son chemin promis : un master efface a la
#: main ou une planche renommee disparaitraient sinon de tout affichage, et
#: l'operateur croirait avoir tout libere.
ETAT_DECLARE_ABSENT = "declare_absent"

#: **AC 1.4** -- trouve sur le disque, declare par aucun manifeste. C'est ce
#: que laisse un nettoyage manuel interrompu, et c'est la seule information de
#: cet inventaire que rien d'autre dans le depot ne produit.
ETAT_NON_DECLARE = "non_declare"

ETATS: tuple[str, ...] = (ETAT_PRESENT, ETAT_DECLARE_ABSENT, ETAT_NON_DECLARE)


# ---------------------------------------------------------------------------
# Les refus, publies (AC 1.6)
# ---------------------------------------------------------------------------


class InventaireError(RuntimeError):
    """Refus de coeur de l'inventaire de projet."""


class ProjetIntrouvable(InventaireError):
    """`project_dir` n'existe pas, ou n'est pas un dossier."""


class ManifesteIntrouvable(InventaireError):
    """Le dossier existe mais ne porte aucun manifeste de projet.

    Distincte de :class:`ProjetIntrouvable` : l'issue n'est pas la meme --
    ouvrir un autre dossier d'un cote, reconstruire le manifeste de l'autre --
    et un appelant qui ne peut pas les distinguer proposerait la mauvaise.
    """


class ManifesteIllisible(InventaireError):
    """Le manifeste existe et ne se lit pas : JSON invalide, ou acces refuse."""


class ManifesteIncoherent(InventaireError):
    """Le manifeste se lit mais ne porte pas les structures qu'il promet.

    `rushes` et `lots` sont des **listes** au schema v2. Un objet ou une chaine
    a leur place n'est pas un projet vide : c'est un manifeste ecrit par autre
    chose que cet outil, et l'inventorier a l'aveugle rendrait un arbre faux
    plutot qu'un refus nomme.
    """


#: **Les refus que l'inventaire leve**, publies sur le modele de
#: `scan_detect.REFUS_DU_COEUR` (AC 1.6). La TUI n'a pas le droit d'importer
#: `cli` (`EPIC11-ARB-67`) : sans cette table elle rédigerait une seconde copie
#: du vocabulaire, ce que la story 11.5 a du faire faute de mieux et que la
#: 11.6 a ferme.
#:
#: `ProjectMaintenanceError` y figure et n'est pas levee par ce module : elle
#: **traverse** depuis la filiation de `project_maintenance`, que cet inventaire
#: lit plutot que de la rediger (chemin declare qui sort du projet, slug
#: d'ingestion qui n'est pas un segment). La table publie ce qu'un appelant doit
#: attraper, pas ce que ce fichier ecrit -- exactement comme
#: `scan_detect.REFUS_DU_COEUR` publie les refus de `scan_ingest` et de
#: `scan_detection`.
#:
#: `OSError` n'y figure pas : les acces disque du PARCOURS sont absorbes noeud
#: par noeud (un fichier illisible pese zero et compte pour un) plutot que de
#: faire echouer l'inventaire entier. Un refus de lecture du MANIFESTE, lui,
#: devient `ManifesteIllisible`.
REFUS_DU_COEUR: tuple[type[BaseException], ...] = (
    ProjetIntrouvable,
    ManifesteIntrouvable,
    ManifesteIllisible,
    ManifesteIncoherent,
    ProjectMaintenanceError,
)


# ---------------------------------------------------------------------------
# Le document rendu
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ObjetInventorie:
    """Un noeud de l'arbre : ce qu'il est, ou il est, ce qu'il pese.

    `poids` et `fichiers` sont **son** emplacement propre, mesures ; un noeud
    de regroupement (rush, lot) porte zero des deux et tout son poids vit dans
    ses enfants. `poids_total` et `fichiers_total` font la somme -- c'est ce
    qu'un ecran affiche sur un noeud replie, et il le LIT au lieu de le
    recalculer.
    """

    #: L'une de :data:`NATURES`.
    nature: str
    #: Le nom de l'objet : un identifiant du manifeste (rush, lot) ou le nom du
    #: fichier ou du dossier. Jamais compose ici.
    nom: str
    #: Chemin **relatif POSIX** au dossier projet, ou `None` quand l'objet n'en
    #: a pas (un rush, dont la source vit hors du projet).
    chemin: str | None
    #: L'un de :data:`ETATS`.
    etat: str
    #: Octets mesures a l'emplacement propre de ce noeud.
    poids: int = 0
    #: Cardinal de fichiers mesure a l'emplacement propre de ce noeud.
    fichiers: int = 0
    #: Rang de version porte par le nom, lu par `naming.rang_du_fragment_de_version`
    #: -- la seule recette du depot. Vaut `version_ranks.RANG_ORIGINE` pour un
    #: objet d'origine, qui ne porte aucun fragment.
    rang: int = version_ranks.RANG_ORIGINE
    enfants: tuple["ObjetInventorie", ...] = ()

    @property
    def poids_total(self) -> int:
        """Le poids de ce noeud ET de toute sa descendance."""
        return self.poids + sum(enfant.poids_total for enfant in self.enfants)

    @property
    def fichiers_total(self) -> int:
        """Le cardinal de fichiers de ce noeud ET de toute sa descendance."""
        return self.fichiers + sum(enfant.fichiers_total for enfant in self.enfants)

    def parcourir(self) -> Iterator["ObjetInventorie"]:
        """Ce noeud, puis sa descendance, en profondeur d'abord.

        L'ordre est celui de l'arbre et n'est **jamais trie** : il porte
        l'ordre du manifeste, que le tri detruirait (meme motif que
        l'historique de reconstruction, `EPIC11-ARB-109`).
        """
        yield self
        for enfant in self.enfants:
            yield from enfant.parcourir()


@dataclass(frozen=True)
class InventaireDuProjet:
    """Ce que le projet contient : son arbre, et son ecart au disque.

    `orphelins` est **plat** et non greffe dans l'arbre, et c'est un choix :
    un objet non declare n'a, par definition, aucun parent declare. Le
    rattacher au lot dont son nom **ressemble** serait deviner une filiation --
    le geste meme que `project_maintenance` refuse (« un lien qui designe un
    autre lot ne se devine pas par ressemblance de nom »).
    """

    dossier: Path
    project_id: str | None
    rushes: tuple[ObjetInventorie, ...] = ()
    orphelins: tuple[ObjetInventorie, ...] = ()
    #: **Les dossiers de scan qu'un profil de calibration DECLARE**
    #: (`EPIC11-ARB-262`, tranche par Egan le 2026-09-07). Ils sont a plat comme
    #: les orphelins, et pour la meme raison -- une mire n'appartient a aucun lot
    #: --, mais ils portent :data:`ETAT_PRESENT` : ils sont declares, par le
    #: profil qui les nomme.
    #:
    #: **Pourquoi une famille a part plutot qu'un retrait.** Le constat d'Egan
    #: etait « le scan de la page de calibration apparait en non declare alors
    #: que je l'ai importe au projet » : c'est l'ETAT qui etait faux, pas la
    #: presence. Les ecarter de l'inventaire ferait disparaitre d'un ecran des
    #: octets qui pesent bel et bien sur le disque -- exactement le defaut que
    #: cet inventaire existe pour fermer. Ils comptent donc dans
    #: :meth:`parcourir`, donc dans les deux totaux.
    calibrations: tuple[ObjetInventorie, ...] = ()

    def parcourir(self) -> Iterator[ObjetInventorie]:
        """Tous les noeuds : l'arbre en profondeur, puis les orphelins."""
        for rush in self.rushes:
            yield from rush.parcourir()
        for orphelin in self.orphelins:
            yield from orphelin.parcourir()
        for calibration in self.calibrations:
            yield from calibration.parcourir()

    @property
    def poids_total(self) -> int:
        """Les octets du projet, orphelins COMPRIS.

        Compris, parce qu'ils occupent bel et bien le disque : les exclure
        rendrait un total qui ne correspond a rien de ce que l'operateur voit
        dans son explorateur de fichiers.
        """
        return sum(noeud.poids for noeud in self.parcourir())

    @property
    def fichiers_total(self) -> int:
        """Le cardinal de fichiers du projet, orphelins compris."""
        return sum(noeud.fichiers for noeud in self.parcourir())

    @property
    def objets_total(self) -> int:
        """Le cardinal de NOEUDS de l'inventaire, orphelins compris."""
        return sum(1 for _ in self.parcourir())


# ---------------------------------------------------------------------------
# La mesure du disque -- mesuree, jamais estimee (AC 1.2)
# ---------------------------------------------------------------------------


def _mesure_du_fichier(chemin: Path) -> tuple[int, int]:
    """`(poids, cardinal)` d'un fichier : sa taille en octets, et un.

    `lstat` et non `stat` : un lien symbolique pese **zero** et compte pour un
    fichier. Supprimer un lien ne libere pas les octets de sa cible -- les
    compter ferait annoncer un gain que la suppression ne rendrait pas.

    Un `OSError` (droits, chemin trop long) rend `(0, 1)` : le fichier est la,
    sa taille est inconnue. Faire echouer l'inventaire entier pour un fichier
    illisible serait le blocage sec qu'`EPIC11-ARB-89` interdit.
    """
    try:
        etat = chemin.lstat()
    except OSError:
        return 0, 1
    if stat_module.S_ISLNK(etat.st_mode):
        return 0, 1
    return etat.st_size, 1


def _mesure_du_dossier(dossier: Path) -> tuple[int, int]:
    """`(poids, cardinal)` d'un dossier, par PARCOURS de son contenu.

    Mesure et non estimation (AC 1.2) : ni « cardinal x taille moyenne », ni
    `expected_frame_count` lu au manifeste. Un lot dont l'extraction s'est
    interrompue porte moins de frames que le manifeste n'en promet, et c'est
    precisement l'ecart que cet inventaire existe pour montrer.

    `rglob` ne descend pas dans un lien symbolique de dossier (mesure de
    `project_maintenance._fichiers_du_lot`, Python 3.11) : les octets d'un
    dossier lie ne sont donc jamais comptes ici, ce qui est voulu -- ils
    n'appartiennent pas au projet.
    """
    poids = 0
    cardinal = 0
    for chemin in dossier.rglob("*"):
        try:
            etat = chemin.lstat()
        except OSError:
            continue
        if stat_module.S_ISDIR(etat.st_mode):
            continue
        octets, compte = _mesure_du_fichier(chemin)
        poids += octets
        cardinal += compte
    return poids, cardinal


def _rang_du_nom(nom: str) -> int:
    """Le rang de version que porte ce nom, par la seule recette du depot.

    La tige est prise **sans son extension** : un master `..._v3.mov` porte son
    fragment avant le point, et `naming.rang_du_fragment_de_version` reconnait
    le fragment en fin de chaine. Aucune expression reguliere n'est ecrite ici
    (`io/version_ranks.py` et `io/naming.py` portent la regle, « ecrite une
    fois pour tous »).
    """
    return naming.rang_du_fragment_de_version(PurePosixPath(nom).stem)


def _relatif(project_dir: Path, chemin: Path) -> str:
    """Le chemin relatif POSIX de `chemin` sous `project_dir`."""
    return chemin.relative_to(project_dir).as_posix()


def _noeud_de_dossier(
    project_dir: Path, relatif: str, nature: str,
    enfants: tuple[ObjetInventorie, ...] = (),
) -> ObjetInventorie:
    """Un noeud pour un dossier DECLARE : present et mesure, ou nomme et absent.

    **Le poids nul ne dit rien de l'existence**, et c'est l'exigence de
    l'AC 1.3 : un dossier vide rend `(ETAT_PRESENT, 0, 0)`, un dossier efface
    rend `(ETAT_DECLARE_ABSENT, 0, 0)`. Les deux pesent zero ; un seul des deux
    est une perte.

    `enfants` existe depuis la story 11.14 : un dossier de scan porte les lots
    scannes qu'il a produits (`EPIC11-ARB-219`, dont `EPIC11-ARB-244` ne
    change que le PARENT du scan, pas ses enfants). Un noeud absent du disque
    en porte aussi -- un scan efface a la main ne fait pas disparaitre les
    frames qu'il avait rendues, et les taire les rendrait invisibles.
    """
    chemin = project_dir / relatif
    nom = PurePosixPath(relatif).name
    if chemin.is_dir():
        poids, cardinal = _mesure_du_dossier(chemin)
        return ObjetInventorie(
            nature=nature, nom=nom, chemin=relatif, etat=ETAT_PRESENT,
            poids=poids, fichiers=cardinal, rang=_rang_du_nom(nom),
            enfants=enfants)
    return ObjetInventorie(
        nature=nature, nom=nom, chemin=relatif, etat=ETAT_DECLARE_ABSENT,
        rang=_rang_du_nom(nom), enfants=enfants)


def _noeud_de_fichier(
    project_dir: Path, relatif: str, nature: str
) -> ObjetInventorie:
    """Un noeud pour un fichier DECLARE : present et mesure, ou nomme et absent.

    Meme regime que :func:`_noeud_de_dossier` : un fichier de zero octet
    existe, un fichier efface non.
    """
    chemin = project_dir / relatif
    nom = PurePosixPath(relatif).name
    if chemin.is_file():
        poids, cardinal = _mesure_du_fichier(chemin)
        return ObjetInventorie(
            nature=nature, nom=nom, chemin=relatif, etat=ETAT_PRESENT,
            poids=poids, fichiers=cardinal, rang=_rang_du_nom(nom))
    return ObjetInventorie(
        nature=nature, nom=nom, chemin=relatif, etat=ETAT_DECLARE_ABSENT,
        rang=_rang_du_nom(nom))


# ---------------------------------------------------------------------------
# La filiation d'un lot -- LUE de `project_maintenance`, jamais redigee
# ---------------------------------------------------------------------------


def _planches_attendues(
    project_dir: Path, manifest: Mapping[str, Any], lot: Mapping[str, Any]
) -> list[str]:
    """Les tirages que ce lot promet, avec la regle de selection du coeur.

    Elle se lit dans `project_maintenance._annexes_du_lot`, et elle a deux
    regimes que la classe marqueur `_Declares` separe :

    * **declares** au manifeste (`lots[].sheets_pdfs`, `EPIC11-ARB-90`) : tous
      sont attendus, y compris absents. Un tirage renomme a la main garde son
      entree, et son absence a l'emplacement promis doit se voir ;
    * **deduits** d'un recalcul de nom (manifeste anterieur a cet inventaire) :
      seul le tirage de rang 1 est attendu, les 98 autres ne sont signales que
      s'ils existent. Sans cette nuance, chaque lot ancien rendrait 98 objets
      « declares et absents » qui n'apprennent rien et noieraient les vrais.
    """
    planches = _planche_pdf_declaree(project_dir, manifest, lot)
    if isinstance(planches, _Declares):
        return list(planches)
    if not planches:
        return []
    return [planches[0]] + [
        relatif for relatif in planches[1:] if (project_dir / relatif).is_file()
    ]


def _frames_scannees_declarees(
    lot: Mapping[str, Any]
) -> list[tuple[str | None, str]]:
    """Les dossiers de frames scannees que ce lot declare, avec LEUR scan.

    Rend des couples `(ingest_slug | None, chemin declare)` dans l'ordre
    d'ecriture du manifeste : d'abord ceux que `lots[].reconstructions[]`
    attribue **explicitement** a un scan -- ce registre porte
    `output_frames_dir` depuis `EPIC11-ARB-105` --, puis, s'il n'y figure pas
    deja, le `output_frames_dir` de tete du lot, celui de la derniere passe.

    Le second n'est PAS attribue ici : le manifeste ne dit pas de quel scan il
    vient. C'est la filiation differee qu'`EPIC11-ARB-90` a laissee ouverte
    (« a l'ingestion, le lot n'est pas connu »), et la deviner par
    ressemblance de nom est exactement le geste que ce module refuse.

    Deduplique PAR CHEMIN : le registre et la tete designent le plus souvent
    le meme dossier, et le compter deux fois doublerait son poids.
    """
    declares: list[tuple[str | None, str]] = []
    vus: set[str] = set()
    for entree in lot.get("reconstructions") or []:
        if not isinstance(entree, Mapping):
            continue
        chemin = entree.get("output_frames_dir")
        if not isinstance(chemin, str) or not chemin or chemin in vus:
            continue
        slug = entree.get("ingest_slug")
        vus.add(chemin)
        declares.append((slug if isinstance(slug, str) and slug else None, chemin))
    tete = lot.get("output_frames_dir")
    if isinstance(tete, str) and tete and tete not in vus:
        declares.append((None, tete))
    return declares


def _noeud_de_lot_scanne(project_dir: Path, declare: str) -> ObjetInventorie:
    """Le lot scanne, et son unique enfant : ses frames scannees.

    **Noeud de regroupement**, comme le lot : il ne pese rien de lui-meme, et
    la symetrie est le propos. Un lot porte ses frames extraites ; un lot
    scanne porte ses frames scannees. C'est la phrase d'Egan lue dans l'arbre
    -- « a partir d'un scan on reproduit un lot scanne qui est lui meme un
    ensemble de frames scannees » -- et c'est ce qui fait du lot scanne un
    OBJET, donc quelque chose qui se supprime et se versionne
    (`EPIC11-ARB-104`).

    Son nom est celui du dossier, jamais recompose : c'est lui qui porte le
    rang de version de la passe de rescan (`EPIC11-ARB-105`).
    """
    chemin = _sous_le_projet(
        project_dir, project_dir / str(declare), "output_frames_dir", declare)
    relatif = _relatif(project_dir, chemin)
    frames = _noeud_de_dossier(project_dir, relatif, NATURE_FRAMES_SCANNEES)
    return ObjetInventorie(
        nature=NATURE_LOT_SCANNE, nom=frames.nom, chemin=None,
        etat=ETAT_PRESENT, rang=frames.rang, enfants=(frames,))


def _scans_et_lots_scannes(
    project_dir: Path, manifest: Mapping[str, Any], lot: Mapping[str, Any]
) -> tuple[tuple[ObjetInventorie, ...], tuple[ObjetInventorie, ...]]:
    """`(noeuds de scan, lots scannes SANS scan connu)` -- `EPIC11-ARB-244`.

    Egan, verbatim le 2026-09-05 : « **Je change d'avis pour le lot B : le
    scan est le fils du lot qu'il reproduit. Le lot scanne est bien le fils du
    scan.** » Le scan **redevient** une annexe du lot, ce qu'`EPIC11-ARB-90`
    en avait fait, et les deux verites coexistent enfin : le scan reproduit un
    lot, et du scan on reproduit un lot scanne.

    **Ce que ce retournement remplace**, parce que ce depot garde son
    historique plutot que de l'effacer : `EPIC11-ARB-219` (2026-09-04)
    disait -- verbatim -- « Le scan est frere du lot et le lot scanne est
    enfant du scan », et cette fonction rendait alors des noeuds de scan que
    l'appelant posait A COTE des lots, sous le rush. `EPIC11-ARB-244` renverse
    cette premiere moitie et garde la seconde : le tuple rendu est le meme,
    seul son PREMIER membre change de destination -- il part desormais dans
    les enfants du lot, par :func:`_enfants_du_lot`.

    **Ce qui n'a pas bouge d'une ligne** : la deduction du parent d'un lot
    scanne, ci-dessous. Elle ne dependait pas du parent du scan, et
    `EPIC11-ARB-244` ne la touche pas.

    **Ce qui reste ouvert, et qui n'est pas devine ici.** Un lot scanne dont
    aucun `reconstructions[]` ne nomme le scan n'a pas de parent LU. Deux cas :

    * le lot n'a qu'UN seul scan : il n'y a alors qu'un parent possible, et le
      rattacher n'est pas une devinette mais une deduction ;
    * le lot en a plusieurs, ou aucun : le lot scanne reste alors sous son
      LOT. C'est le seul endroit ou il ne disparait pas de l'arbre, et le
      taire serait pire que le mal ranger -- un dossier d'images invisible est
      exactement le sujet de la story 11.11.
    """
    scans = _scans_du_lot(project_dir, manifest, lot)
    par_slug: dict[str, list[str]] = {}
    sans_scan: list[str] = []
    for slug, chemin in _frames_scannees_declarees(lot):
        if slug is None:
            sans_scan.append(chemin)
        else:
            par_slug.setdefault(slug, []).append(chemin)

    if len(scans) == 1 and sans_scan and scans[0].name not in par_slug:
        par_slug[scans[0].name] = sans_scan
        sans_scan = []

    noeuds_de_scan = tuple(
        _noeud_de_dossier(
            project_dir, _relatif(project_dir, dossier), NATURE_SCAN,
            enfants=tuple(
                _noeud_de_lot_scanne(project_dir, chemin)
                for chemin in par_slug.get(dossier.name, ())),
        )
        for dossier in scans
    )
    orphelins_de_scan = tuple(
        _noeud_de_lot_scanne(project_dir, chemin) for chemin in sans_scan)
    return noeuds_de_scan, orphelins_de_scan


def _enfants_du_lot(
    project_dir: Path, manifest: Mapping[str, Any], lot: Mapping[str, Any]
) -> tuple[ObjetInventorie, ...]:
    """Les objets produits d'un lot : frames, masters, planches, **scans**.

    **Le scan y figure de nouveau** (`EPIC11-ARB-244`, 2026-09-05 : « le scan
    est le fils du lot qu'il reproduit »). Il en etait sorti la veille, le
    temps d'`EPIC11-ARB-219`, qui en faisait un frere du lot pendu au rush --
    cette docstring portait alors la phrase inverse, « le scan n'y figure
    plus ». Ce sont donc TOUS les objets d'un lot qui se lisent ici, ceux
    qu'il produit par CALCUL depuis son rush comme ceux qui lui reviennent par
    le PAPIER.

    **L'ORDRE que cette fonction rend, dit plutot que laisse deviner.** Chaque
    famille garde l'ordre de sa liste au manifeste et n'est jamais triee --
    cet ordre porte une information qu'un tri detruirait (`EPIC11-ARB-109`).
    Entre familles, en revanche, l'ordre est celui de cette fonction :

    1. les **frames extraites** -- ce que le lot est ;
    2. les **masters**, puis les **planches** -- ce qu'il produit par calcul ;
    3. les **scans**, et sous chacun ses lots scannes -- ce qui lui revient du
       papier ;
    4. en QUEUE, les lots scannes **dont aucun scan n'est deductible**. Un
       ecart se pose apres ce qui est nominal -- meme geste que le rush non
       declare, que :func:`inventorier_le_projet` pose apres les rushes
       declares -- et le taire ferait disparaitre de l'arbre un dossier
       d'images bel et bien present.

    **Ce que la maquette validee dicte, et ce qu'elle ne dicte pas.**
    `E6-1e-projet-inventaire-filiation` pose les scans APRES les frames, les
    planches et les masters : c'est le point 3, et c'est le seul que le
    retournement d'`EPIC11-ARB-244` avait a trancher. Elle pose en revanche
    les **planches avant les masters**, la ou cette fonction fait l'inverse
    depuis l'origine -- et cet ecart-la est **sans effet**, parce que l'ecran
    regroupe les enfants par nature avant de les afficher : l'ordre qui se
    voit entre deux groupes est le sien, pas celui d'ici. Ce qui se voit de
    l'ordre rendu ici, c'est l'ordre AU SEIN d'un groupe, celui du manifeste.
    Le mesurer serait mesurer une surface qui n'existe pas encore ; le taire
    ferait croire a un accord qui n'est pas verifie.

    Un ecran reste libre de regrouper ces enfants par nature pour les
    afficher, et c'est ce que fait la maquette : **le coeur ne produit aucun
    noeud de regroupement par type**. Il n'y a ni noeud `frames`, ni
    `planches`, ni `masters`, ni `scans` -- :data:`NATURES` n'en porte pas, et
    un banc mesure ce tuple a la main.

    Chaque chemin declare repasse par `project_maintenance._sous_le_projet`
    avant d'etre approche : un `frames_dir` valant `"../../ailleurs"` ou `"."`
    designe un emplacement hors du lot, et le PARCOURIR pour le peser
    reviendrait a inventorier le disque entier sous le nom d'un lot.
    """
    enfants: list[ObjetInventorie] = []

    declare = lot.get("frames_dir")
    if declare:
        chemin = _sous_le_projet(
            project_dir, project_dir / str(declare), "frames_dir", declare)
        enfants.append(
            _noeud_de_dossier(
                project_dir, _relatif(project_dir, chemin),
                NATURE_FRAMES_EXTRAITES))

    for relatif in _masters_declares(lot):
        chemin = _sous_le_projet(
            project_dir, project_dir / relatif, "encoded_masters", relatif)
        enfants.append(
            _noeud_de_fichier(
                project_dir, _relatif(project_dir, chemin), NATURE_MASTER))

    for relatif in _planches_attendues(project_dir, manifest, lot):
        chemin = _sous_le_projet(
            project_dir, project_dir / relatif, "sheets_pdfs", relatif)
        enfants.append(
            _noeud_de_fichier(
                project_dir, _relatif(project_dir, chemin), NATURE_PLANCHE))

    scans, lots_scannes_sans_scan = _scans_et_lots_scannes(
        project_dir, manifest, lot)
    enfants.extend(scans)
    # En QUEUE, et seulement en queue : un lot scanne sans parent deductible
    # est un ECART, il se pose apres ce qui est nominal.
    enfants.extend(lots_scannes_sans_scan)

    return tuple(enfants)


# ---------------------------------------------------------------------------
# L'ecart du disque au manifeste (AC 1.4) -- le vrai livrable
# ---------------------------------------------------------------------------


def _sous_dossiers(racine: Path) -> list[Path]:
    """Les sous-dossiers immediats de `racine`, tries par nom.

    Immediats : `frames/<slug>/` est un objet, `frames/<slug>/<sous-dossier>/`
    n'en est pas un second. Tries, parce que l'ordre du systeme de fichiers
    n'est pas un ordre -- il n'y a ici aucun ordre de manifeste a preserver.

    Les noms CACHES sont ecartes, pour le motif de :func:`_est_cache`.
    """
    if not racine.is_dir():
        return []
    return sorted(
        (chemin for chemin in racine.iterdir()
         if chemin.is_dir() and not _est_cache(chemin)),
        key=lambda chemin: chemin.name,
    )


#: Ce qui prefixe un nom que le systeme de fichiers tient pour cache. Pose une
#: fois : deux ecritures de ce point divergeraient le jour ou l'une d'elles
#: gagnerait une exception.
_PREFIXE_CACHE = "."


def _est_cache(chemin: Path) -> bool:
    """Un nom qui commence par un point n'est **pas un objet du projet**.

    **Le regime exact, et il a ete rencontre sur le disque d'Egan.** Un export
    ProRes/DNxHD interrompu laisse son fichier d'attente d'ecriture atomique --
    `.<nom final>.<pid>-<aleatoire>.mov` --, **conserve expres** pour
    diagnostic (`encode.py`, l'ecriture atomique des masters). Ce nom porte
    `MASTER_FILENAME_MARKER`, donc le balayage des orphelins l'inventoriait
    comme un master non declare : il se greffait sur rien, atterrissait en
    queue d'arbre sans lot parent, et la seule chose que l'ecran pouvait en
    dire etait fausse dans les deux sens -- ni un objet du produit, ni un objet
    supprimable.

    **Un filtre par PREFIXE et non par motif d'attente.** Reconnaitre
    `.<...>.<pid>-<hex>.<ext>` serait une seconde redaction de la convention
    d'ecriture atomique, logee loin de sa fabrique -- exactement ce que
    `io.naming` existe pour empecher. Et la propriete qui compte est plus
    large que ce motif-la : **aucun** fichier ni dossier cache n'est un objet
    de ce projet. Les fichiers de service du systeme (`.DS_Store`,
    `.Trashes`), les restes d'un editeur et les dossiers d'outillage tombent
    sous la meme regle, et pour la meme raison.

    **Ce que ce filtre NE ferme pas, dit plutot que tu** : il ne ramasse rien.
    Un fichier d'attente abandonne pese toujours sur le disque et cesse
    seulement d'etre montre comme un objet du projet. Le ramassage est un autre
    sujet, et il vit du cote de l'encodage.
    """
    return chemin.name.startswith(_PREFIXE_CACHE)


def _fichiers_immediats(racine: Path) -> list[Path]:
    """Les fichiers immediats de `racine`, tries par nom.

    Les noms CACHES sont ecartes, pour le motif de :func:`_est_cache`.
    """
    if not racine.is_dir():
        return []
    return sorted(
        (chemin for chemin in racine.iterdir()
         if chemin.is_file() and not _est_cache(chemin)),
        key=lambda chemin: chemin.name,
    )


def _orphelin_de_dossier(project_dir: Path, chemin: Path, nature: str) -> ObjetInventorie:
    poids, cardinal = _mesure_du_dossier(chemin)
    return ObjetInventorie(
        nature=nature, nom=chemin.name, chemin=_relatif(project_dir, chemin),
        etat=ETAT_NON_DECLARE, poids=poids, fichiers=cardinal,
        rang=_rang_du_nom(chemin.name))


def _orphelin_de_fichier(project_dir: Path, chemin: Path, nature: str) -> ObjetInventorie:
    poids, cardinal = _mesure_du_fichier(chemin)
    return ObjetInventorie(
        nature=nature, nom=chemin.name, chemin=_relatif(project_dir, chemin),
        etat=ETAT_NON_DECLARE, poids=poids, fichiers=cardinal,
        rang=_rang_du_nom(chemin.name))


def _orphelins(
    project_dir: Path, declares: Mapping[str, set[str]]
) -> tuple[tuple[ObjetInventorie, ...], tuple[ObjetInventorie, ...]]:
    """`(ce qu'aucun lot ne declare, les scans de mire declares par un profil)`.

    **Le second membre est ce qu'`EPIC11-ARB-262` a tranche** (Egan, 2026-09-07).
    Un dossier de `scans/` qu'un profil de `versions/calibration/` NOMME par son
    champ `scan_dir` n'est pas un orphelin : il est declare, par le seul artefact
    qui puisse le declarer. Il sort donc de la premiere liste et entre dans la
    seconde, avec :data:`ETAT_PRESENT` -- il ne DISPARAIT pas, ce qui serait le
    remede pire que le mal (des octets qui pesent et qu'aucun ecran ne montre).

    **La declaration se LIT, elle ne se devine pas** (`CLAUDE.md`, regle 6). Les
    trois heuristiques disponibles -- un fragment de nom, l'absence
    d'`ingest.json`, une page unique -- ecarteraient un vrai lot de planches ;
    `io/calibration_profile.dossiers_de_scan_declares` rend une identite.

    **Le docstring de module est precise par la meme occasion, et il le fallait** :
    il dit que `versions/` n'est pas un objet produit par un lot, ce qui reste
    vrai -- un profil n'est ni inventorie ni supprimable. Il est LU ici comme une
    declaration, exactement comme le manifeste l'est, et lire n'est pas
    inventorier.

    **Ce que ca ne repare pas** : un projet calibre AVANT le 2026-09-07 porte un
    profil sans `scan_dir`, donc son scan de mire reste un orphelin. Rien ne les
    relie retroactivement -- ni le manifeste, ni le dossier, ni le profil --, et
    ce faux orphelin ne se fermera qu'a la prochaine recalibration.

    **CE QUE L'APPARIEMENT NE COUVRE PAS, dit plutot que tu** (revue du
    2026-09-07, findings `B2` et `B6` -- deux moities que le diff d'origine ne
    disait pas alors qu'il disait tout le reste). Les deux sont **mesurees** par
    ce banc, bord par bord, plutot que promises :
    `tests/unit/test_orphelin_du_scan_de_calibration.py`.

    * **la declaration porte sur le LOT, pas sur la page de mire.**
      `report.scans_dir` est le dossier du lot de scan, et la comparaison
      ci-dessous ne regarde que le chemin. Un lot qui porte la mire **et** de
      vraies planches passe donc en entier dans `calibrations`, avec son poids et
      son cardinal complets, et ces planches-la perdent la mention « non
      declare ». Ce n'est pas une violation d'`EPIC11-ARB-262` -- le profil nomme
      bel et bien ce dossier --, c'est la portee reelle de ce qu'il nomme. Mesure
      du 2026-09-07, parcours nominal et rasters reels : une pile de deux fichiers
      (la mire + le lot « 4f heteroclytes ») passee a
      `scan_calibrate.calibrer_la_chaine` rend `calibrations=['scans/pile']`,
      2 fichiers, 14 256 199 octets, `orphelins=[]`. `calibrer_la_chaine` ne borne
      pas le nombre de pages et `check_scan_conflicts` n'est pas appele depuis ce
      chemin : le regime est atteignable par le parcours nominal v2.1 ;
    * **l'appariement est une IDENTITE, jamais une ascendance.** Un `scan_dir` a
      plus d'un cran sous `scans/` ne s'apparie a aucun noeud, ce balayage ne
      construisant d'objet que pour les sous-dossiers **immediats** de chaque
      racine. Or `scan_ingest._est_un_dossier_de_lot` accepte n'importe quelle
      profondeur, et l'ingestion en place produit alors reellement un tel champ.
      Mesure du 2026-09-07, parcours entier sur le raster reel depose dans
      `scans/2026/janvier/` : le produit ecrit `scan_dir = 'scans/2026/janvier'`
      et l'inventaire rend `orphelins=['scans/2026']`, `calibrations=[]`. Celui
      qui range ses scans par date garde donc son faux orphelin.

      **L'apparier par ascendance a ete mesure et ECARTE**, plutot que juge : le
      noeud `scans/2026` porte l'annee ENTIERE, si bien que le rattacher au profil
      ferait passer douze mois de planches en `calibrations` -- c'est le regime
      ci-dessus, multiplie par le nombre de lots de l'annee. « On n'arrete jamais
      un process par ressemblance, toujours par identite » : un noeud qui
      *contient* le dossier declare n'est pas le dossier declare. Le choix
      appartient a Egan et n'est pas tranche ici -- `deferred-work.md`, entree
      `ARB262-N1`, qui porte les deux sorties chiffrees.

    **Quatre emplacements, et le motif de chaque filtre :**

    * `extract-frames/` et `frames-scannees/` -- et les noms d'avant,
      toujours RECONNUS (`EPIC11-ARB-171`) : un sous-dossier immediat par
      lot. Tout slug que nul `frames_dir` ni `output_frames_dir` ne declare
      est le residu d'un lot retire du manifeste sans que ses images le
      soient ;
    * `outputs/` : le dossier est **partage**, et le POC y ecrit aussi des
      frames de travail. Seuls les fichiers portant le marqueur de master
      (`naming.MASTER_FILENAME_MARKER`) sont donc des objets de cette liste --
      le marqueur est lu du nommage, jamais recopie ;
    * `planches/` -- et le nom d'avant, `patches/`, toujours RECONNU
      (`EPIC11-ARB-225`) : partage lui aussi, entre les tirages et les **pages de
      calibration**. Une page de calibration n'appartient a aucun lot et n'est
      declaree par aucun inventaire : elle est reconnue par son suffixe
      (`naming.CALIBRATION_PDF_SUFFIX`) et ecartee, sans quoi tout projet
      calibre montrerait un faux orphelin ;
    * `scans/` : un sous-dossier par slug d'ingestion. La filiation d'un scan
      est **differee** -- elle n'existe qu'apres reconstruction --, si bien
      qu'un scan ingere et jamais reconstruit apparait ici. Ce n'est pas un
      defaut de la mesure : c'est un dossier d'images qui pese sur le disque et
      qu'aucun ecran ne montre, ce qui est exactement le sujet de la story.
    """
    trouves: list[ObjetInventorie] = []

    # **Les DEUX racines de chaque famille de frames**, story 11.14 : le nom
    # neuf et celui d'avant, qui reste RECONNU (`EPIC11-ARB-171`). Elles sont
    # LUES de `project_layout`, jamais recomposees ici -- un projet migre a
    # moitie porte les deux, et n'en balayer qu'une rendrait invisible tout ce
    # qui vit dans l'autre.
    familles: list[tuple[Path, str]] = [
        (racine, NATURE_FRAMES_EXTRAITES)
        for racine in project_layout.racines_de_frames_extraites(project_dir)
    ]
    familles += [
        (racine, NATURE_FRAMES_SCANNEES)
        for racine in project_layout.racines_de_frames_scannees(project_dir)
    ]
    familles.append((project_dir / project_layout.SCANS_DIRNAME, NATURE_SCAN))

    for racine, nature in familles:
        for chemin in _sous_dossiers(racine):
            if _relatif(project_dir, chemin) in declares[nature]:
                continue
            trouves.append(_orphelin_de_dossier(project_dir, chemin, nature))

    for chemin in _fichiers_immediats(project_dir / project_layout.OUTPUTS_DIRNAME):
        if naming.MASTER_FILENAME_MARKER not in chemin.name:
            continue
        if _relatif(project_dir, chemin) in declares[NATURE_MASTER]:
            continue
        trouves.append(_orphelin_de_fichier(project_dir, chemin, NATURE_MASTER))

    # **LES DEUX RACINES** (`EPIC11-ARB-225`), lues de `project_layout` et
    # jamais recomposees ici -- meme geste que les deux familles de frames
    # au-dessus. Une racine unique rendrait INVISIBLES les planches d'un projet
    # ancien, c'est-a-dire un inventaire qui annonce zero orphelin sur un
    # dossier qui en porte : le defaut `E2-1`, que ce module a deja paye.
    for racine in project_layout.racines_de_planches(project_dir):
        for chemin in _fichiers_immediats(racine):
            if chemin.name.endswith(naming.CALIBRATION_PDF_SUFFIX):
                continue
            if _relatif(project_dir, chemin) in declares[NATURE_PLANCHE]:
                continue
            trouves.append(_orphelin_de_fichier(project_dir, chemin, NATURE_PLANCHE))

    # **Le partage se fait ICI, en fin de balayage, et non pendant** : un profil
    # declare un CHEMIN, et le chemin d'un noeud n'est connu qu'une fois le noeud
    # construit. Le comparer plus haut ferait recomposer `scans/<slug>` a la main,
    # c'est-a-dire la seconde ecriture que ce module s'interdit.
    declares_par_un_profil = calibration_profile.dossiers_de_scan_declares(project_dir)
    orphelins: list[ObjetInventorie] = []
    calibrations: list[ObjetInventorie] = []
    for objet in trouves:
        # **La garde de NATURE porte, et elle est mesuree** (finding `B5` du
        # 2026-09-07, ou elle survivait a 57 tests). `scan_dir` est un chemin
        # relatif au PROJET, pas a `scans/` : `_validate_scan_dir` accepte donc
        # `'extract-frames/lot-a'`, qui est un chemin relatif POSIX parfaitement
        # bien forme. Sans cette garde, un tel profil ferait basculer un dossier
        # de FRAMES orphelin dans la famille « calibrations » avec
        # :data:`ETAT_PRESENT`. Le banc qui la fait varier est
        # `test_un_scan_dir_qui_NOMME_UN_DOSSIER_DE_FRAMES_ne_declare_rien` : sans
        # lui, elle se serait fait retirer au premier nettoyage comme du code mort.
        if objet.nature == NATURE_SCAN and objet.chemin in declares_par_un_profil:
            calibrations.append(ObjetInventorie(
                nature=objet.nature, nom=objet.nom, chemin=objet.chemin,
                etat=ETAT_PRESENT, poids=objet.poids, fichiers=objet.fichiers,
                rang=objet.rang, enfants=objet.enfants))
        else:
            orphelins.append(objet)
    return tuple(orphelins), tuple(calibrations)


# ---------------------------------------------------------------------------
# Le point d'entree (AC 1.1)
# ---------------------------------------------------------------------------


def _lire_le_manifeste(project_dir: Path) -> dict[str, Any]:
    """Le manifeste du projet, ou l'un des trois refus nommes de la table."""
    if not project_dir.is_dir():
        raise ProjetIntrouvable(
            f"{project_dir} n'existe pas ou n'est pas un dossier : il n'y a "
            "aucun projet a inventorier."
        )
    manifeste = project_dir / MANIFEST_FILENAME
    if not manifeste.is_file():
        raise ManifesteIntrouvable(
            f"{project_dir} ne porte aucun manifeste ({MANIFEST_FILENAME}) : ce "
            "dossier n'est pas un projet ouvert, ou son manifeste a ete efface. "
            "Aucun inventaire n'a pu etre dresse."
        )
    try:
        contenu = dict(load_manifest(manifeste))
    except (ValueError, TypeError, OSError) as erreur:
        raise ManifesteIllisible(
            f"{manifeste} est illisible ou n'est pas un JSON valide ({erreur}). "
            "Aucun inventaire n'a pu etre dresse."
        ) from erreur
    for champ in ("rushes", "lots"):
        valeur = contenu.get(champ)
        if valeur is not None and not isinstance(valeur, list):
            raise ManifesteIncoherent(
                f"{manifeste} declare {champ!r} sous la forme "
                f"{type(valeur).__name__}, la ou le schema v2 attend une liste. "
                "Aucun inventaire n'a pu etre dresse."
            )
    return contenu


def _entrees(manifest: Mapping[str, Any], champ: str) -> list[Mapping[str, Any]]:
    """Les entrees exploitables de `manifest[champ]`, dans leur ordre d'ecriture."""
    return [
        entree for entree in (manifest.get(champ) or [])
        if isinstance(entree, Mapping)
    ]


def inventorier_le_projet(project_dir: str | Path) -> InventaireDuProjet:
    """Rendre l'arbre des objets produits de `project_dir` (AC 1.1 a 1.4).

    **Signature de producteur** : aucun `args`, aucun `print`, aucun code de
    sortie. Elle leve l'un des refus de :data:`REFUS_DU_COEUR` et elle rend un
    :class:`InventaireDuProjet`.

    L'arbre est **rushes -> lots**, dans l'ordre du manifeste : un lot porte
    ses frames extraites, ses masters, ses planches et ses **scans** ; un
    scan, **fils du lot qu'il reproduit** depuis `EPIC11-ARB-244`, porte les
    lots scannes qu'il a produits, et chacun ses frames scannees.
    `EPIC11-ARB-219`, la veille, en faisait un FRERE du lot : le rush avait
    alors deux familles d'enfants, « les lots d'abord, les scans ensuite »,
    et cette fonction concatenait deux dictionnaires pour les poser. Il n'en
    reste qu'un. L'ordre des enfants d'un lot est celui
    de :func:`_enfants_du_lot`, qui le documente. Un lot dont le `rush_id`
    n'est declare par aucune entree de `rushes[]` recoit malgre tout son rush,
    marque :data:`ETAT_NON_DECLARE` et pose **apres** les rushes declares :
    c'est le seul endroit ou cet etat designe un ecart INTERNE au manifeste et
    non un ecart au disque, et le taire ferait disparaitre le lot de l'arbre
    entier.

    Les deux couts, mesures plutot que supposes (Q1 de la fiche) : le manifeste
    se lit d'un bloc, le disque se parcourt. Le second domine, et il croit avec
    le cardinal de fichiers du projet -- le chiffre est ecrit dans la fiche de
    la story pour que l'ecran decide de charger a l'ouverture ou a la demande.
    """
    project_dir = Path(project_dir)
    manifest = _lire_le_manifeste(project_dir)

    lots = _entrees(manifest, "lots")
    #: Ce que chaque lot declare, accumule pendant la construction de l'arbre :
    #: l'ecart au disque se mesure contre CE que l'arbre a lu, jamais contre
    #: une seconde lecture du manifeste.
    #: Indexe par NATURE, jamais par un nom de dossier : une cle valant
    #: `"extract-frames"` serait un nom de `project_layout` recopie,
    #: c'est-a-dire la seconde ecriture que ce module s'interdit.
    declares: dict[str, set[str]] = {nature: set() for nature in NATURES}

    noeuds_de_lot: dict[str, list[ObjetInventorie]] = {}
    ordre_des_rushes: list[str] = []
    for lot in lots:
        lot_id = lot.get("lot_id")
        if not isinstance(lot_id, str) or not lot_id:
            # Une entree sans identite n'est pas inventoriable : la nommer
            # demanderait de la deviner. Elle n'est pas non plus une panne du
            # projet -- ses fichiers, eux, ressortiront en orphelins.
            continue
        # Le scan est un enfant du lot depuis `EPIC11-ARB-244` :
        # `_enfants_du_lot` rend TOUT, il n'y a plus de seconde famille a
        # accumuler a cote.
        enfants = _enfants_du_lot(project_dir, manifest, lot)
        rush_id = lot.get("rush_id")
        rush_id = rush_id if isinstance(rush_id, str) and rush_id else ""
        if rush_id not in noeuds_de_lot:
            noeuds_de_lot[rush_id] = []
            ordre_des_rushes.append(rush_id)
        noeuds_de_lot[rush_id].append(
            ObjetInventorie(
                nature=NATURE_LOT, nom=lot_id, chemin=None, etat=ETAT_PRESENT,
                rang=_rang_du_nom(lot_id), enfants=enfants))

    # **L'ecart au disque se mesure contre ce que l'ARBRE a lu**, et l'arbre a
    # TROIS etages sous un lot -- scan, lot scanne, frames scannees : le
    # parcourir en profondeur est la seule facon de n'oublier aucun chemin
    # declare. La redaction d'avant ne lisait que les enfants IMMEDIATS d'un
    # lot ; le lot scanne etant range sous son scan (`EPIC11-ARB-219`, que
    # `EPIC11-ARB-244` n'a pas touche sur ce point), elle aurait rendu
    # orphelin tout dossier de frames scannees pourtant declare. Le piege est
    # le MEME depuis qu'`ARB-244` a remis le scan sous le lot : la profondeur
    # a augmente de ce cote, elle n'a pas diminue.
    for lus in noeuds_de_lot.values():
        for racine in lus:
            for noeud in racine.parcourir():
                if noeud.chemin is not None and noeud.nature in declares:
                    declares[noeud.nature].add(noeud.chemin)

    rushes: list[ObjetInventorie] = []
    declares_au_manifeste: list[str] = []
    for rush in _entrees(manifest, "rushes"):
        rush_id = rush.get("rush_id")
        if not isinstance(rush_id, str) or not rush_id:
            continue
        declares_au_manifeste.append(rush_id)
        rushes.append(
            ObjetInventorie(
                nature=NATURE_RUSH, nom=rush_id, chemin=None, etat=ETAT_PRESENT,
                enfants=tuple(noeuds_de_lot.get(rush_id, ()))))

    for rush_id in ordre_des_rushes:
        if rush_id in declares_au_manifeste:
            continue
        rushes.append(
            ObjetInventorie(
                nature=NATURE_RUSH, nom=rush_id, chemin=None,
                etat=ETAT_NON_DECLARE,
                enfants=tuple(noeuds_de_lot.get(rush_id, ()))))

    orphelins, calibrations = _orphelins(project_dir, declares)
    project_id = manifest.get("project_id")
    return InventaireDuProjet(
        dossier=project_dir,
        project_id=project_id if isinstance(project_id, str) else None,
        rushes=tuple(rushes),
        orphelins=orphelins,
        calibrations=calibrations,
    )
