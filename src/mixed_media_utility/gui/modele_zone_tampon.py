# -*- coding: utf-8 -*-
"""Modele PUR de la file « En attente de lecture » (story 7.3, AC 1).

Aucun import Qt : c'est le meme decoupage qu'en 7.2 (`modele_chutier` sans
Qt, `chutier` avec), et c'est ce qui rend la moitie des AC de cette story
testable sans widget.

**Ce que ce module tient, et pourquoi il est une FILE et pas un depotoir**
(correction A2 de la revue de couche 3, « une file se vide, un fond de tiroir
se remplit ») :

* on y depose **un fichier**, **une selection** de plusieurs fichiers -- qui
  produit **une seule** entree, le lot que le coeur ingerera d'un bloc
  (`EPIC7-ARB-88`) -- ou **un dossier entier**, qui en produit **une** ;
* chaque entree porte une **case a cocher** independante, et une entree neuve
  est cochee ;
* **rien n'en sort tout seul** : ni une detection terminee, ni une detection
  echouee ne retire quoi que ce soit. Seul :meth:`ModeleDeZoneTampon.retirer`
  enleve une entree, et il n'est appele que par un geste explicite ;
* ce que la detection ne rattache a aucun lot **reste ici, nomme** : le
  reliquat est POSE sur l'entree, lu du rapport de tri de 5.24, jamais
  recompose (`EPIC7-ARB-64`, AC 8b).

**Le dpi est obligatoire et sans defaut** (`EPIC7-ARB-44`). Ce module n'en
propose aucun : `dpi` vaut `None` tant que l'operateur n'a pas saisi le sien,
et :meth:`ModeleDeZoneTampon.motif_d_inactivite` dit alors POURQUOI le bouton
`Detecter` est inactif -- un bouton grise sans phrase est une impasse.

**Aucune forme n'est plus demandee a l'operatrice** (`EPIC7-ARB-89`). Le
couple « pile de planches / planche seule » a vecu ici jusqu'au 2026-08-27 :
il etait **decoratif**, et la mesure qui l'a tranche est simple -- le champ
`forme` n'etait transmis a aucun appel du coeur (`AtelierScan.lancer` ne passe
que `project_dir`, `scan_path`, `dpi`). Le tri est fait par le coeur
(`run_scan_detect` avec `ingest_slug=None` insere le tri par QR de 5.24 et
ecrit un document par lot trouve), donc l'interface n'a rien a deduire ni a
faire corriger. `EPIC7-ARB-13` (« l'ambiguite d'un PDF depose ») est **clos
sans objet** par la meme occasion : l'ambiguite n'existait que dans la lecture
qu'en faisait la surface, jamais dans le traitement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .. import scan_ingest

# ---------------------------------------------------------------------------
# Les trois natures qu'un chemin depose peut avoir. Vocabulaire FERME : une
# valeur hors de ce tuple est un defaut de ce module, pas une extension.
# ---------------------------------------------------------------------------

#: Un dossier depose : le coeur l'ingere d'un bloc, tel quel.
NATURE_DOSSIER = "dossier"

#: Un PDF depose : il porte ses pages en interne et **ne se melange pas** a
#: des images dans une meme selection -- c'est le refus que `scan_ingest`
#: ecrit lui-meme (« Un dossier s'ingere en designant le dossier, un PDF en le
#: designant seul »).
NATURE_PDF = "pdf"

#: Une image. Ce sont les seuls chemins qu'une selection multiple regroupe.
NATURE_IMAGE = "image"

#: Un chemin dont le suffixe n'est ni celui d'un PDF ni celui d'une image
#: ACCEPTEE PAR LE COEUR. Il fait entree a part -- exactement comme un dossier
#: ou un PDF, et pour la meme raison : c'est un refus que `scan_ingest` ecrit
#: lui-meme, et le regrouper avec des images ferait echouer TOUT le depot.
#: Mesure du defaut (revue du 2026-08-27) : deposer `page.tiff` et `notes.txt`
#: ensemble produisait UNE entree de deux chemins, que le coeur refusait en
#: bloc -- « Une selection de scan ne porte que des images » --, si bien que
#: l'image valide etait perdue avec le fichier fautif. Isole, `notes.txt`
#: echoue seul, avec son motif verbatim, et `page.tiff` aboutit.
NATURE_ETRANGERE = "etrangere"

NATURES = (NATURE_DOSSIER, NATURE_PDF, NATURE_IMAGE, NATURE_ETRANGERE)

#: Suffixe reconnu comme PDF, en minuscules. Un seul, et il n'est pas une
#: liste d'extensions d'images : ce module ne juge PAS de la lisibilite d'un
#: fichier -- c'est `scan_ingest` qui refuse un format non supporte, avec son
#: motif. Ici on ne fait que dire ce que l'entree ANNONCE.
SUFFIXE_PDF = ".pdf"

#: Les suffixes qu'une selection multiple peut regrouper, **lus du coeur** et
#: jamais recopies : `scan_ingest.IMAGE_EXTENSIONS` decide ce que l'ingestion
#: accepte, et une seconde liste ici divergerait au premier ajout de format --
#: c'est la meme frontiere dure que celle du filtre du selecteur de fichiers.
#: Ce module continue de ne juger AUCUNE lisibilite : un `.tiff` illisible
#: reste une image ici, et c'est `scan_ingest` qui le refusera, avec son motif.
#: Ce que ce jeu de suffixes decide, c'est uniquement le GROUPEMENT.
SUFFIXES_D_IMAGE = scan_ingest.IMAGE_EXTENSIONS


class ZoneTamponError(ValueError):
    """Refus du modele de file, avec son motif."""


@dataclass
class EntreeDeTampon:
    """Un depot, ce qu'il annonce, et ce qui lui est arrive.

    `chemin` porte **soit** un chemin unique (un fichier, un PDF, un dossier)
    **soit** un tuple de chemins -- une selection de plusieurs images, qui est
    **UN lot** et donc **un seul** `ingest.json` (`EPIC7-ARB-88`).
    `scan_ingest.ingest_scan_lot` accepte cette sequence comme quatrieme forme
    d'entree, et `run_scan_detect` la transmet telle quelle : la GUI n'a donc
    rien a regrouper ni a decouper, elle passe ce qu'on lui a donne.

    Le tuple est **hachable**, et ce n'est pas un detail : `AtelierScan.lancer`
    dedoublonne ses taches par le contenu de :attr:`chemins` (F15), ce qu'une
    liste rendrait impossible.

    `motif` et `reliquat` sont poses APRES coup, par l'appelant, a partir de
    ce que le coeur a rendu : un motif d'echec verbatim (`str(exc)`), et les
    pages que le tri n'a rattachees a aucun lot. Aucun des deux n'est redige
    ici -- « la GUI ne recopie jamais un code du coeur : elle le lit » (P9).
    """

    identifiant: str
    chemin: Path | tuple
    nature: str
    #: Le slug que le coeur retiendra pour ce lot, **derive par le coeur**
    #: (`scan_ingest.slug_par_defaut`) et jamais devine ici. `None` tant
    #: qu'aucun projet n'est pose, ou quand le coeur refuse l'entree -- la
    #: passe dira alors pourquoi, avec son propre motif.
    nom_de_lot: str | None = None
    cochee: bool = True
    #: Le dpi de numerisation, saisi. `None` tant qu'il ne l'est pas.
    dpi: int | None = None
    #: Le motif d'echec de la derniere detection lancee sur cette entree,
    #: VERBATIM. `None` quand elle n'a pas echoue.
    motif: str | None = None
    #: Les pages que le tri n'a rattachees a aucun lot : des couples
    #: `(localisateur, motif)`, lus du rapport de tri, jamais recomposes.
    reliquat: tuple[tuple[str, str], ...] = ()
    #: Les pages que le tri a rangees HORS PERIMETRE (projet etranger) : des
    #: triplets `(localisateur, motif, projet_a_utiliser)`, lus du rapport de
    #: tri, jamais recomposes. CLASSE DISJOINTE du reliquat -- `scan_sorting.
    #: PartitionDeVrac` les separe deja en deux classes de la partition, et
    #: cette entree ne les fusionne pas (F14, revue de vague 3 de l'Epic 7).
    hors_perimetre: tuple[tuple[str, str, str | None], ...] = ()
    #: Les lot_id trouves par la derniere detection, dans l'ordre du tri.
    lot_trouves: tuple[str, ...] = field(default_factory=tuple)

    @property
    def chemins(self) -> tuple:
        """Les chemins de l'entree, **toujours** sous forme de tuple.

        Une seule forme a lire pour tout ce qui compte, compare ou dedoublonne
        -- l'entree a un chemin et l'entree a N chemins cessent d'etre deux cas
        a traiter separement, ce qui est exactement l'endroit ou un correctif
        d'ARB-88 se serait oublie.
        """
        if isinstance(self.chemin, (str, Path)):
            return (Path(self.chemin),)
        return tuple(Path(chemin) for chemin in self.chemin)

    @property
    def est_une_selection(self) -> bool:
        """Vrai quand l'entree porte PLUSIEURS fichiers, donc un lot compose."""
        return len(self.chemins) > 1

    @property
    def nom(self) -> str:
        """Le nom de l'entree : celui du chemin, ou celui du LOT.

        Un chemin unique se nomme par son nom de fichier -- inchange depuis
        7.3. Une selection se nomme par le slug que le **coeur** retiendra
        (:attr:`nom_de_lot`), parce que c'est sous ce nom-la que le lot
        existera sur le disque ; le deviner cote GUI le ferait diverger au
        premier changement du coeur. Tant qu'aucun projet n'est pose, aucun
        slug n'est derivable : on retombe alors sur le nom du premier fichier,
        et le nom du lot le remplace des que le projet arrive.
        """
        if self.est_une_selection and self.nom_de_lot is not None:
            return self.nom_de_lot
        return self.chemins[0].name


def libelle_d_entree(entree: EntreeDeTampon, chaines) -> str:
    """Le texte qui NOMME une entree a l'ecran, en une seule redaction.

    Un chemin unique s'affiche par son nom, exactement comme avant
    `EPIC7-ARB-88`. Une selection s'affiche avec `zone-tampon-entree-selection`
    -- le nom du lot, et **combien** de fichiers il porte : sans le cardinal,
    une selection de vingt-cinq TIFF et le dossier qui les contient
    porteraient le meme libelle, alors que ce sont deux gestes differents.

    La phrase vient du catalogue, jamais d'ici (NFR2). Cette fonction vit dans
    le modele et non dans une surface parce que **deux** surfaces la
    demandent -- la ligne de la file et la carte de tache de l'atelier --, et
    deux redactions divergeraient.
    """
    if not entree.est_une_selection:
        return entree.nom
    return chaines["zone-tampon-entree-selection"].format(
        nom=entree.nom, pages=len(entree.chemins))


def _nature_du_chemin(chemin: Path) -> str:
    """La nature d'un chemin depose : dossier, PDF, ou image.

    Un dossier se reconnait au disque (`is_dir`), un PDF et une image a leur
    suffixe. Le reste est ETRANGER a la selection multiple -- ce module ne
    l'ouvre pas plus qu'avant : juger de la lisibilite d'un fichier reste le
    travail de `scan_ingest`, qui a le motif pour le dire. Ce qui se decide
    ici est uniquement de savoir ce qui peut faire lot AVEC autre chose.
    """
    if chemin.is_dir():
        return NATURE_DOSSIER
    suffixe = chemin.suffix.lower()
    if suffixe == SUFFIXE_PDF:
        return NATURE_PDF
    if suffixe in SUFFIXES_D_IMAGE:
        return NATURE_IMAGE
    return NATURE_ETRANGERE


def _grouper_le_depot(chemins) -> list[tuple]:
    """Repartir les chemins d'UN depot en entrees, dans l'ordre du depot.

    **Les images d'un meme depot forment un seul groupe** : c'est
    `EPIC7-ARB-88`, et c'est exactement ce que `scan_ingest.ingest_scan_lot`
    sait ingerer d'un bloc depuis le 2026-08-27. Un dossier et un PDF, eux,
    restent chacun leur propre entree -- non pas par choix de la GUI, mais
    parce que c'est le refus que le **coeur** ecrit lui-meme quand on les
    melange a une selection : « Un dossier s'ingere en designant le dossier,
    un PDF en le designant seul » (`scan_ingest._normaliser_la_selection`).
    Les regrouper ferait echouer tout le depot la ou trois entrees
    aboutissaient.

    Le groupe d'images prend la place de sa **premiere** image dans l'ordre du
    depot : un depot `[image, dossier, image]` rend donc `[(image, image),
    (dossier,)]`, et non l'inverse. L'ordre de la file reste celui du geste.
    """
    groupes: list[tuple] = []
    selection: list[Path] = []
    place = None
    for chemin in chemins:
        if _nature_du_chemin(chemin) == NATURE_IMAGE:
            if place is None:
                place = len(groupes)
                groupes.append(())
            selection.append(chemin)
        else:
            groupes.append((chemin,))
    if place is not None:
        groupes[place] = tuple(selection)
    return groupes


class ModeleDeZoneTampon:
    """La file : des entrees ordonnees, cochees, et qui ne partent jamais seules."""

    def __init__(self):
        self._entrees: list[EntreeDeTampon] = []
        # Compteur monotone : deux depots du MEME chemin restent deux entrees
        # distinctes. Un identifiant derive du seul chemin les confondrait, et
        # cocher l'une cocherait l'autre.
        self._prochain = 0
        # Le projet ouvert. Il ne sert QU'A demander au coeur le slug d'un lot
        # (`scan_ingest.slug_par_defaut`) : ce modele n'ecrit ni ne lit rien
        # sur le disque.
        self._project_dir: Path | None = None

    # --- Lecture -------------------------------------------------------

    @property
    def entrees(self) -> tuple[EntreeDeTampon, ...]:
        """Les entrees, **dans l'ordre du depot**."""
        return tuple(self._entrees)

    @property
    def project_dir(self) -> Path | None:
        """Le projet ouvert, ou `None`."""
        return self._project_dir

    def entree(self, identifiant: str) -> EntreeDeTampon | None:
        """L'entree portant cet identifiant, ou `None`."""
        for entree in self._entrees:
            if entree.identifiant == identifiant:
                return entree
        return None

    def cochees(self) -> tuple[EntreeDeTampon, ...]:
        """Les seules entrees cochees, dans l'ordre du depot."""
        return tuple(entree for entree in self._entrees if entree.cochee)

    # --- Le projet, et le nom que le coeur donnera a un lot --------------

    def poser_le_projet(self, project_dir) -> None:
        """Dire au modele sur quel projet il travaille.

        Les entrees deja deposees sont **renommees** dans le meme mouvement :
        une selection deposee avant l'ouverture d'un projet n'avait aucun slug
        derivable, et resterait sinon affichee sous le nom de son premier
        fichier alors que le lot existera sous un autre nom.
        """
        self._project_dir = None if project_dir is None else Path(project_dir)
        for entree in self._entrees:
            if entree.est_une_selection:
                entree.nom_de_lot = self._nom_de_lot(entree.chemins)

    def _nom_de_lot(self, chemins) -> str | None:
        """Le slug que le coeur retiendra pour ces chemins, ou `None`.

        **Demande au coeur**, jamais recompose : `scan_ingest.slug_par_defaut`
        applique exactement la regle d'`ingest_scan_lot` (le dossier parent
        commun, ou le nom du premier fichier dans l'ordre de lecture), et une
        seconde derivation ecrite ici divergerait au premier changement.

        Rend `None` quand aucun projet n'est ouvert -- il n'y a alors pas de
        racine `scans/` a comparer -- et quand le coeur **refuse** l'entree :
        ce refus n'est pas rendu ici, il sera dit par la passe elle-meme, avec
        son motif verbatim. Nommer un lot n'est pas le moment de refuser.
        """
        if self._project_dir is None:
            return None
        try:
            return scan_ingest.slug_par_defaut(
                self._project_dir, tuple(chemins))
        except scan_ingest.ScanIngestError:
            return None

    # --- Depot ---------------------------------------------------------

    def deposer(self, chemins) -> tuple[EntreeDeTampon, ...]:
        """Deposer un ou plusieurs chemins ; rend les entrees creees.

        **Une selection de N images est UNE entree** (`EPIC7-ARB-88`), donc un
        lot, donc **un seul** `ingest.json`. C'est l'inverse exact du choix de
        7.3 (« N chemins produisent N entrees »), que l'essai de terrain du
        2026-08-27 a refuse : « il devrait y avoir un unique ingest.json pour
        ce lot de fichiers ». Ce choix n'etait tenable que parce que
        `ingest_scan_lot` ne prenait qu'un chemin ; il en prend desormais une
        **sequence**, et `run_scan_detect` la transmet telle quelle.

        Un **dossier** produit **une** entree, comme avant : c'est deja un lot
        pour le coeur, et l'enumerer ici serait refaire son travail. Un
        **fichier seul** produit une entree a un seul chemin, identique en
        tout point a ce que 7.3 produisait.

        Le detail de la repartition -- et pourquoi un dossier ou un PDF ne
        rejoint jamais une selection d'images -- est dans
        :func:`_grouper_le_depot`.
        """
        if isinstance(chemins, (str, Path)):
            chemins = [chemins]
        chemins = [Path(chemin) for chemin in chemins]
        creees = []
        for groupe in _grouper_le_depot(chemins):
            multiple = len(groupe) > 1
            entree = EntreeDeTampon(
                identifiant=f"entree-{self._prochain}",
                chemin=tuple(groupe) if multiple else groupe[0],
                nature=_nature_du_chemin(groupe[0]),
                nom_de_lot=self._nom_de_lot(groupe) if multiple else None,
                cochee=True,
            )
            self._prochain += 1
            self._entrees.append(entree)
            creees.append(entree)
        return tuple(creees)

    # --- Gestes sur une entree -----------------------------------------

    def _exiger(self, identifiant: str) -> EntreeDeTampon:
        entree = self.entree(identifiant)
        if entree is None:
            raise ZoneTamponError(
                f"aucune entree {identifiant!r} dans la file")
        return entree

    def cocher(self, identifiant: str, cochee: bool = True) -> None:
        """Cocher ou decocher UNE entree -- les autres n'en savent rien."""
        self._exiger(identifiant).cochee = bool(cochee)

    def basculer(self, identifiant: str) -> bool:
        """Basculer la case d'une entree ; rend son nouvel etat."""
        entree = self._exiger(identifiant)
        entree.cochee = not entree.cochee
        return entree.cochee

    def poser_le_dpi(self, identifiant: str, dpi) -> None:
        """Poser le dpi de numerisation d'une entree, ou l'effacer (`None`).

        Aucun defaut n'est propose ni suppose (`EPIC7-ARB-44`) : un dpi non
        saisi vaut `None`, et rien ici ne le remplace.
        """
        entree = self._exiger(identifiant)
        if dpi is None:
            entree.dpi = None
            return
        valeur = int(dpi)
        if valeur <= 0:
            raise ZoneTamponError(
                f"le dpi de numerisation doit etre strictement positif, recu {dpi!r}")
        entree.dpi = valeur

    def poser_le_motif(self, identifiant: str, motif) -> None:
        """Poser le motif d'echec VERBATIM d'une entree (ou l'effacer)."""
        self._exiger(identifiant).motif = None if motif is None else str(motif)

    def poser_le_reliquat(self, identifiant: str, entrees) -> None:
        """Poser ce que le tri n'a rattache a aucun lot, LU du rapport de tri.

        `entrees` est une suite de couples `(localisateur, motif)`. Les deux
        viennent du document de 5.24 : le localisateur nomme la page, le motif
        est un code du vocabulaire ferme `scan_sorting.MOTIFS_DE_RELIQUAT`.
        Ni l'un ni l'autre n'est fabrique ici.
        """
        entree = self._exiger(identifiant)
        entree.reliquat = tuple(
            (str(localisateur), str(motif)) for localisateur, motif in entrees)

    def poser_le_hors_perimetre(self, identifiant: str, entrees) -> None:
        """Poser ce que le tri a range HORS PERIMETRE, LU du rapport de tri.

        `entrees` est une suite de triplets `(localisateur, motif,
        projet_a_utiliser)`. Les trois viennent du document de 5.24 -- aucun
        n'est fabrique ici (meme regle que :meth:`poser_le_reliquat`).
        **Jamais fusionne avec le reliquat** : `scan_sorting.PartitionDeVrac`
        porte deja `reliquat` et `hors_perimetre` comme deux classes
        disjointes de sa partition, et cette methode garde cette disjonction
        jusque sur l'entree (F14, revue de vague 3 de l'Epic 7).
        `projet_a_utiliser` peut etre `None` (le QR ne l'a pas livre) : ce
        `None` est preserve tel quel, jamais transforme en la chaine
        `"None"`.
        """
        entree = self._exiger(identifiant)
        entree.hors_perimetre = tuple(
            (str(localisateur), str(motif),
             None if projet is None else str(projet))
            for localisateur, motif, projet in entrees)

    def poser_les_lot_trouves(self, identifiant: str, identifiants_de_lot) -> None:
        """Poser les identifiants de lot que la detection a trouves.

        Ils viennent des documents ecrits par le coeur, dans leur ordre. La
        GUI les MONTRE : elle ne rejoue aucune regle de rattachement.
        """
        self._exiger(identifiant).lot_trouves = tuple(
            str(valeur) for valeur in identifiants_de_lot)

    def retirer(self, identifiant: str) -> bool:
        """**Le seul** geste qui enleve une entree de la file.

        Il n'est jamais appele par une fin de detection, reussie ou non : une
        entree qui disparaitrait toute seule ferait de la file un fond de
        tiroir, ce que la correction A2 interdit nommement. Un « Non » a la
        question de remplacement (`EPIC7-ARB-90`) ne l'appelle pas non plus :
        l'entree refusee reste dans la file, intacte.
        """
        entree = self.entree(identifiant)
        if entree is None:
            return False
        self._entrees.remove(entree)
        return True

    # --- Le bouton Detecter, et pourquoi il est inactif -----------------

    def motif_d_inactivite(self) -> str | None:
        """La CLE DE CATALOGUE du libelle inactif, ou `None` si actif.

        Deux causes, ordonnees de la plus large a la plus fine : aucune entree
        cochee, puis une entree cochee sans dpi. Rendre une cle et non une
        phrase est ce qui garde la redaction au catalogue (NFR2).
        """
        cochees = self.cochees()
        if not cochees:
            return "zone-tampon-detecter-sans-entree"
        if any(entree.dpi is None for entree in cochees):
            return "zone-tampon-detecter-sans-dpi"
        return None

    def peut_detecter(self) -> bool:
        """Vrai quand au moins une entree cochee porte son dpi."""
        return self.motif_d_inactivite() is None
