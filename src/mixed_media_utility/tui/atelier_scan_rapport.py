# -*- coding: utf-8 -*-
"""Le rapport de detection du Scan, temps 1 -- `E3-3` et `E3-4` (story 11.5, AC 6).

**Modele pur : aucun `textual`, aucune lecture de disque, aucune ecriture.** Ce
module projette ce que le coeur a produit -- les documents de detection de 5.25
et la partition du tri de 5.24 -- en ce que les deux ecrans de rapport
montrent : **un panneau par lot reconnu**, la file « en attente de lecture »
**nommee fichier par fichier**, et les issues du jugement.

**Il ne juge rien qu'il calcule lui-meme** (`EPIC11-ARB-30`). La completude d'un
lot est LUE de :func:`scan_detect.completude_des_planches`, qui est sa **seule**
derivation dans le depot (`EPIC7-ARB-73`) ; la classe d'une page non rattachee
est LUE du vocabulaire ferme de :mod:`scan_sorting`. Une seconde redaction de
l'une ou de l'autre divergerait de la premiere le jour ou l'une des deux change,
et le rapport de la TUI contredirait celui de la GUI sur le meme scan.

**Ce que ce module ne fait pas, et c'est structurel :**

* il **n'ecrit aucune frame** -- c'est l'invariant du temps 1 (`EPIC11-ARB-6`).
  Aucune fonction d'ici n'ouvre un fichier ;
* il **ne lit aucun document sur le disque** : il recoit des
  :class:`scan_previz.ScanPreviz` deja relus. Le paquet `tui/` n'a pas le droit
  d'importer `gui.chargeur_detections` -- la frontiere de
  `test_frontiere_gui_tui.py` est une **egalite** sur deux modules nommes --,
  et une seconde redaction du lecteur normatif n'appartient pas a l'AC 6 ;
* il **ne rejoue aucune regle de rattachement** : le tri par QR est une fonction
  du coeur, cet ecran **montre** son resultat (`EPIC7-ARB-64`).

**Les deux listes que ce module parcourt sont les lots et les pages**, et c'est
exactement la ou la 11.4b a laisse survivre trois mutants `continue` -> `break`.
L'ordre des lots est celui des documents recus -- celui du tri du coeur --, il
n'est **jamais recalcule ici** : c'est ce qui permet a un banc de verifier le
rang d'une cible sur la liste que ce code parcourt, et non sur celle que sa
fabrique croit ecrire.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Mapping, Sequence

from .. import qr_codes, scan_detect, scan_sorting
from .panneau import ChoixExclusif, Issue

# ---------------------------------------------------------------------------
# Textes d'ecran. En constantes, pour le meme motif qu'aux paliers precedents :
# un texte ecrit deux fois divergerait, et les frontieres negatives les
# balayent.
# ---------------------------------------------------------------------------

#: Titre du cartouche des lots (`E3-3` et `E3-4`), verbatim des maquettes.
TITRE_LOTS_RECONNUS = "Lots reconnus"

#: Titre de la file, verbatim des maquettes. C'est le nom qu'`EXPERIENCE.md`
#: emploie d'un bout a l'autre de l'atelier : une page que le tri n'a rattachee
#: a rien n'est pas perdue, elle **attend d'etre lue**.
TITRE_EN_ATTENTE = "En attente de lecture"

#: Ce que la file dit quand elle est vide. Une ligne vide y serait illisible :
#: l'operateur ne saurait pas si la question a ete posee (meme regle que
#: `atelier_extraction_ecriture.BORNES_ABSENTES`).
AUCUN_FICHIER_EN_ATTENTE = "aucun fichier non rattaché"

#: Les cles des issues du rapport. Elles ne sont **jamais** affichees : le
#: libelle l'est. Une cle est ce par quoi un test et un ecran se designent la
#: meme issue sans recopier une chaine francaise.
ISSUE_ECRIRE = "ecrire"
#: **La valeur de cette cle evite le mot que `EPIC11-ARB-48` compte a zero
#: sur le paquet `tui/`** (AC 8.2, frontiere mesuree par
#: `EPIC11-ARB-127` : la frontiere du depot vise le geste qu'`EPIC11-ARB-48` a
#: retire de la barre d'adresse -- proposer la suite d'un chemin qu'on tape --
#: et non le mot isole. Ce qui se fait ici n'a aucun rapport avec lui : c'est la
#: saisie de ce qu'un QR muet n'a pas livre (`EPIC11-ARB-29`).
#:
#: **La cle a porte `saisir-le-qr` pendant une soiree**, le temps que
#: l'arbitrage soit rendu : le lot D avait renomme la CHOSE pour la faire
#: passer sous la frontiere, en refusant explicitement d'ajouter une tolerance
#: en silence. C'etait le bon reflexe faute de decision, et c'est l'inverse de
#: la regle qu'`EPIC11-ARB-127` a posee -- « quand une frontiere attrape un
#: homonyme, on resserre la frontiere sur la chose ; on ne renomme pas la chose
#: pour la faire passer sous la frontiere ». Le nom est rendu.
ISSUE_COMPLETER = "completer-le-qr"
ISSUE_REPRENDRE = "reprendre-la-detection"
ISSUE_ANNULER = "annuler"

#: Le libelle de la premiere issue quand un lot au moins est incomplet.
LIBELLE_ECRIRE_QUAND_MEME = "Écrire quand même"

#: Le libelle de la deuxieme issue. `EPIC11-ARB-29` l'a **remplace** : le mot
#: qu'il retire ne se lit plus nulle part dans les modules du Scan, et une
#: frontiere negative le compte a zero. Motif d'Egan, verbatim : « cela ne
#: resoudra rien » -- repasser une planche dont le pli traverse le QR rend le
#: meme QR muet -- et « pas toujours possible » -- la planche est chez le
#: prestataire, ou detruite.
LIBELLE_COMPLETER_LE_QR = "Compléter le QR"

#: La troisieme issue. Son libelle est celui de la maquette ; ce qu'elle fait
#: est dit **a cote** d'elle, comme pour les deux autres (AC 6.5).
LIBELLE_ANNULER = "Annuler"

#: Ce qu'`Annuler` fait, a cote d'elle. Verbatim de `E3-4`.
A_COTE_ANNULER = "ne rien écrire"

#: La suite de reprise de `E3-3`. `EPIC11-ARB-101`, note 9 : « oui, retour a
#: `E3-1`, le depot, avec le champ vide ».
#: **Mesure, pas un gout** (2026-08-31) : la forme longue -- « Reprendre la
#: detection avec d'autres fichiers » -- faisait 45 colonnes, et sa ligne
#: complete avec le a-cote en faisait **79 pour 76 utiles**, dans les DEUX
#: rendus. « La detection » est redondant a deux titres : on est sur le rapport
#: DE DETECTION, et `A_COTE_REPRENDRE` dit deja « retour au depot, le champ
#: vide ». La forme retenue rend la ligne a **66** colonnes. Aucun sens perdu --
#: c'est ce qui distingue un raccourcissement d'une troncature.
LIBELLE_REPRENDRE = "Reprendre avec d'autres fichiers"
A_COTE_REPRENDRE = "retour au dépôt, le champ vide"

#: Les trois etats de completude, **lus du coeur** et jamais redefinis ici
#: (`scan_detect.COMPLETUDES`). Le glyphe de chacun vient de la table de
#: `DESIGN.md` section 6 par sa cle, jamais par son dessin.
GLYPHE_PAR_COMPLETUDE: Mapping[str, str] = {
    scan_detect.COMPLETUDE_COMPLET: "complete",
    scan_detect.COMPLETUDE_COMPLET_AVEC_MIRES: "substitute",
    scan_detect.COMPLETUDE_INCOMPLET: "absent",
}

#: Les statuts de QR qui decrivent une planche **lue dont le symbole n'a rien
#: livre** -- absent, illisible, ou plusieurs dans le champ.
#:
#: `QR_NOT_ATTEMPTED` n'y est **pas**, et l'omission est mesuree : ce statut
#: marque une page refusee **avant** que le QR ait ete cherche (fichier
#: illisible, dpi invalide). La proposer a la completion enverrait l'operateur
#: recopier ce qui est imprime sur une planche que rien n'a su ouvrir -- c'est
#: le defaut que `scan_detection.QR_NOT_ATTEMPTED` existe pour empecher, sa
#: docstring le dit mot pour mot.
QR_MUETS: tuple[str, ...] = (
    qr_codes.DECODE_NO_SYMBOL,
    qr_codes.DECODE_UNREADABLE,
    qr_codes.DECODE_MULTIPLE,
)

#: Les motifs de reliquat qui decrivent une page **lue dont le QR a echoue**,
#: donc completable par `E3-4b`. **Un seul**, et c'est `EPIC11-ARB-29` :
#: `RELIQUAT_QR_MUET` est litteralement « la page est presente sur la vitre, son
#: identite est inconnue ».
#:
#: Les trois autres motifs du vocabulaire ferme n'y sont pas, chacun pour son
#: motif : `RELIQUAT_PAYLOAD_REFUSE` decrit un QR qui **a** parle et dont le
#: contenu est refuse (planche perimee, champ abime) ; `RELIQUAT_LOT_INCONNU`
#: decrit une identite lue mais incomplete ; les deux motifs de calibration
#: decrivent une feuille de mires, qui n'est la planche d'aucun lot.
MOTIFS_COMPLETABLES: tuple[str, ...] = (scan_sorting.RELIQUAT_QR_MUET,)


# ---------------------------------------------------------------------------
# Ce que le rapport porte
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PageMuette:
    """Une planche **lue** dont le QR n'a rien livre -- elle se complete.

    A ne pas confondre avec une planche **absente** (jamais scannee), qui vit
    dans :attr:`PanneauDeLot.planches_manquantes` : « une page absente ne se
    complete pas : il n'y a rien a lire » (`EPIC11-ARB-29`). Les deux manques
    n'ont pas la meme reparation, et c'est la distinction que l'AC 6.7 mesure.
    """

    #: Le rang de lecture de la page dans la passe -- ce qui la designe pour le
    #: coeur, et ce que `E3-4b` recevra pour poser la correction au bon endroit.
    read_rank: int
    #: Le chemin source de la page, **relatif au projet**, tel que le coeur
    #: l'ecrit. Jamais un compte : la file se nomme fichier par fichier.
    fichier: str
    #: Le code enumere de la story 5.27 quand il y en a un, ou le statut de QR.
    #: Rendu **verbatim** du coeur, jamais traduit (`DESIGN.md` section 9).
    code: str | None = None
    #: Le lot auquel la page a ete rattachee, quand elle l'a ete. `None` quand
    #: elle est au reliquat -- personne ne la reclame.
    lot_id: str | None = None

    @property
    def nom_court(self) -> str:
        """Le nom du fichier sans son dossier ni son extension.

        C'est ce que la maquette montre a cote de « Compléter le QR » --
        « saisir ce que planche_03 n'a pas livré ». Le chemin complet y serait
        illisible, et le rapport le porte deja sur sa propre ligne.
        """
        return PurePosixPath(self.fichier).stem


@dataclass(frozen=True)
class EnAttenteDeLecture:
    """Un fichier que le tri n'a rattache a aucun lot, **nomme**.

    Deux classes disjointes du coeur y entrent -- le **reliquat** (« je n'ai pas
    su te rattacher ») et le **hors-perimetre** (« tu n'es pas ici chez toi ») --,
    et elles ne se confondent pas : `projet_a_utiliser` n'est renseigne que sur
    la seconde, ou il porte le projet lu dans le QR de la page. « L'operateur ne
    doit pas avoir a le deviner » (`EPIC5-ARB-105`).
    """

    fichier: str
    motif: str
    projet_a_utiliser: str | None = None
    read_rank: int | None = None

    @property
    def completable(self) -> bool:
        """Cette page se complete-t-elle ? Voir :data:`MOTIFS_COMPLETABLES`."""
        return self.motif in MOTIFS_COMPLETABLES


@dataclass(frozen=True)
class PanneauDeLot:
    """Un lot reconnu, tel que `E3-3` et `E3-4` le montrent.

    Pages trouvees **sur** pages attendues, frames **sur** frames attendues,
    etat -- et rien qui ne se derive du coeur.

    Les deux cardinaux attendus valent `None` quand aucune source ne les porte,
    et le panneau ne montre alors **rien** a leur place : jamais `0`, jamais
    `--`, jamais une valeur devinee. C'est la meme regle que le dpi non mesure
    (`DESIGN.md` section 3), et elle vaut ici parce qu'un attendu invente est
    exactement ce qui ferait declarer un lot incomplet a tort.
    """

    lot_id: str
    pages_trouvees: int
    pages_attendues: int | None
    frames: int
    frames_attendues: int | None
    completude: str
    planches_manquantes: tuple[int, ...] = ()
    mires: int = 0
    pages_muettes: tuple[PageMuette, ...] = ()

    @property
    def glyphe(self) -> str:
        """La **cle** du glyphe d'etat, jamais son dessin.

        `●` complet, `▲` complet mais portant des mires, `✕` incomplet. Un lot
        complet portant des mires n'est pas `●` : « le fichier existe, l'image
        du film non » -- **une mire n'est pas une frame** (AC 6.2).
        """
        return GLYPHE_PAR_COMPLETUDE[self.completude]

    @property
    def incomplet(self) -> bool:
        return self.completude == scan_detect.COMPLETUDE_INCOMPLET

    @property
    def porte_des_mires(self) -> bool:
        return self.completude == scan_detect.COMPLETUDE_COMPLET_AVEC_MIRES


@dataclass(frozen=True)
class RapportDeDetection:
    """Ce que la detection a trouve -- et **rien n'est encore ecrit**."""

    #: Un panneau par lot reconnu, **dans l'ordre des documents recus**, qui est
    #: celui du tri du coeur. Cette liste n'est jamais retriee ici.
    lots: tuple[PanneauDeLot, ...] = ()
    #: La file, nommee fichier par fichier. Jamais reduite a un compte.
    en_attente: tuple[EnAttenteDeLecture, ...] = ()

    @property
    def lots_incomplets(self) -> tuple[PanneauDeLot, ...]:
        return tuple(lot for lot in self.lots if lot.incomplet)

    @property
    def complet(self) -> bool:
        """Vrai quand aucun lot reconnu n'est incomplet.

        Un rapport **sans aucun lot** n'est pas complet : « aucun QR decode du
        tout » rend zero lot reconnu et tout en attente de lecture, ce qui n'est
        pas un plantage mais n'est pas davantage un rapport dont on peut ecrire
        les frames.
        """
        return bool(self.lots) and not self.lots_incomplets

    @property
    def pages_completables(self) -> tuple[PageMuette, ...]:
        """Les planches **lues dont le QR a echoue**, dans l'ordre du rapport.

        Deux provenances, et elles sont parcourues dans cet ordre : les pages
        muettes rattachees a un lot -- une pile mono-lot les absorbe
        (`scan_detect.pages_du_lot`) --, puis celles que le tri a laissees au
        reliquat avec `RELIQUAT_QR_MUET`.
        """
        muettes: list[PageMuette] = []
        for lot in self.lots:
            muettes.extend(lot.pages_muettes)
        for entree in self.en_attente:
            if entree.completable:
                muettes.append(PageMuette(
                    read_rank=-1 if entree.read_rank is None else entree.read_rank,
                    fichier=entree.fichier,
                    code=entree.motif,
                ))
        return tuple(muettes)

    @property
    def frames(self) -> int:
        """Le total des frames **reelles** de tous les lots du rapport."""
        return sum(lot.frames for lot in self.lots)

    def lignes_en_attente(self) -> list[str]:
        """La file, **une ligne par fichier**, jamais un compte seul (AC 6.1).

        « Ce que la detection n'a rattache a rien reste dans la file, nomme,
        avec le motif lu du rapport de tri. » Le motif est rendu verbatim du
        vocabulaire ferme du coeur ; le projet a utiliser le suit quand la page
        est hors perimetre, parce que c'est lui le geste suivant.
        """
        if not self.en_attente:
            return [AUCUN_FICHIER_EN_ATTENTE]
        lignes = []
        for entree in self.en_attente:
            ligne = f"{entree.fichier}  {entree.motif}"
            if entree.projet_a_utiliser:
                ligne = f"{ligne}  {entree.projet_a_utiliser}"
            lignes.append(ligne)
        return lignes


@dataclass(frozen=True)
class IssuesDuRapport:
    """Les issues du rapport, et **ce que chacune fait, a cote d'elle**.

    Le a-cote est indexe **par cle d'issue**, jamais par rang : « deux listes
    qui doivent rester en correspondance sont deux occasions de les desapparier »
    (`scan_detect.ecrire_le_document_de_detection`, et c'est le defaut central
    que la regle des fabriques de ce depot existe pour attraper). Une
    permutation des issues ne peut donc pas deplacer un a-cote sur une autre.
    """

    choix: ChoixExclusif
    a_cote: Mapping[str, str] = field(default_factory=dict)

    def lignes(self, ascii_seul: bool = False) -> list[str]:
        """Une ligne par issue : le curseur, le libelle, puis son a-cote.

        Le rendu passe par :meth:`ChoixExclusif.rendu`, **pas par une boucle
        reecrite ici** -- meme geste que `palier_projet`, et meme motif : le
        curseur y est pose une seule fois, et c'est lui que `jetons.bloc_peint`
        reconnait pour accentuer la ligne courante.
        """
        rendues = self.choix.rendu(ascii_seul)
        lignes = []
        for issue, ligne in zip(self.choix.issues, rendues):
            supplement = self.a_cote.get(issue.cle)
            lignes.append(f"{ligne}  {supplement}" if supplement else ligne)
        return lignes


# ---------------------------------------------------------------------------
# La projection
# ---------------------------------------------------------------------------


def _cardinal_de_planches(documents) -> int | None:
    """Le cardinal attendu **publie** par les documents d'un lot.

    C'est une **lecture**, pas une seconde regle (`EPIC7-ARB-73`) : le compteur
    a ete ecrit par `scan_detect.cardinal_de_planches_attendu`, et le repli
    rappelle **la meme fonction** sur les pages quand le compteur manque --
    document tronque, ou fixture qui ne le pose pas. Deux documents du meme lot
    qui se contredisent ne rendent aucun cardinal : la contradiction ne se lit
    jamais comme une garantie (`EPIC5-ARB-32`).
    """
    cardinaux = set()
    for document in documents:
        publie = document.counters.pages_expected
        if publie is None:
            publie = scan_detect.cardinal_de_planches_attendu(document.pages)
        if publie is not None:
            cardinaux.add(publie)
    if len(cardinaux) != 1:
        return None
    return cardinaux.pop()


def _frames_attendues(manifeste, lot_id: str) -> int | None:
    """`lots[].expected_frame_count` du manifeste, ou `None`.

    **Lu, jamais derive.** Le document de detection ne porte aucun cardinal de
    frames -- `scan_previz._state_counters` les refuse explicitement en regime
    `detected`, « aucune frame n'est encore ecrite » --, et deduire un attendu
    d'un nombre de zones par planche inventerait une regle que le coeur n'a
    pas. Un lot que le manifeste ne connait pas rend `None`, et le panneau ne
    montre alors rien a la place.
    """
    lots = (manifeste or {}).get("lots")
    if not isinstance(lots, list):
        return None
    for lot in lots:
        if not isinstance(lot, dict) or lot.get("lot_id") != lot_id:
            continue
        attendu = lot.get("expected_frame_count")
        return attendu if isinstance(attendu, int) else None
    return None


def _est_muette(page) -> bool:
    """Cette page a-t-elle ete lue sans que son QR livre quoi que ce soit ?

    Les deux conditions sont **cumulatives** et aucune ne suffit seule : une
    page peut porter un payload et un statut de QR degrade (le template vient
    alors du manifeste), et une page sans payload peut n'avoir jamais vu son QR
    cherche -- voir :data:`QR_MUETS`.
    """
    return page.payload is None and page.qr_status in QR_MUETS


def _pages_muettes(documents, lot_id: str) -> tuple[PageMuette, ...]:
    """Les planches muettes rattachees a ce lot, dans l'ordre des documents."""
    muettes = []
    for document in documents:
        for page in document.pages:
            if _est_muette(page):
                muettes.append(PageMuette(
                    read_rank=page.read_rank,
                    fichier=page.source_path_relative,
                    code=page.refusal_code or page.qr_status,
                    lot_id=lot_id,
                ))
    return tuple(muettes)


def _mesures_de_frames(documents) -> tuple[int, int]:
    """Les frames **reelles** de ce lot, et combien d'entre elles sont des mires.

    Une frame reelle est une zone de decoupe : c'est ce qui sera ecrit, et c'est
    donc le chiffre que l'issue « Écrire quand même » doit porter -- « le compte
    reel, jamais le compte attendu. Aucun trou n'est comble par repetition »
    (AC 6.5). Une page dont le QR est muet n'a aucune zone : elle ne gonfle pas
    ce compte.

    Le comptage des mires porte sur `zone.synthetic is True`, jamais sur sa
    seule verite : le champ vaut `None` tant qu'aucune frame n'est ecrite, et
    `None` n'est pas `False` -- « un drapeau omis se relit "vraie frame" »
    (`scan_previz.PrevizFrameZone`).
    """
    frames = 0
    mires = 0
    for document in documents:
        for page in document.pages:
            for zone in page.frame_zones:
                frames += 1
                if zone.synthetic is True:
                    mires += 1
    return frames, mires


def _grouper_par_lot(documents) -> list[tuple[str, list]]:
    """Les documents groupes par lot, **dans l'ordre de leur venue**.

    Plusieurs documents du meme lot s'additionnent -- c'est le contrat de 5.25
    (plusieurs scans de la meme planche) --, et le lot garde le rang de son
    **premier** document. Aucun tri : l'ordre est celui du tri du coeur, et le
    recalculer ici ferait deux ordres pour un lot.
    """
    index: dict[str, list] = {}
    ordre: list[str] = []
    for document in documents:
        lot_id = document.subject.lot_id
        if lot_id not in index:
            index[lot_id] = []
            ordre.append(lot_id)
        index[lot_id].append(document)
    return [(lot_id, index[lot_id]) for lot_id in ordre]


def projeter(documents: Sequence, *, partition=None,
             manifeste: Mapping | None = None) -> RapportDeDetection:
    """Projeter les documents de detection en un rapport d'ecran.

    :param documents: les :class:`scan_previz.ScanPreviz` de la passe, **deja
        relus**, dans l'ordre ou le coeur les a ecrits (`ScanDetectOutcome.
        documents` porte leurs chemins, un par lot trouve).
    :param partition: la :class:`scan_sorting.PartitionDeVrac` de la passe
        (`ScanDetectOutcome.partition`), ou `None` en regime `--lot-slug`, ou
        il n'y a pas de tri et donc pas de reliquat.
    :param manifeste: le manifeste du projet, pour le seul cardinal de frames
        attendu. Optionnel : sans lui, les frames attendues valent `None` et le
        panneau ne montre rien a leur place.

    **Aucun lot n'est saute et aucun n'est reordonne** : la liste rendue a
    exactement un panneau par lot reconnu, dans l'ordre des documents. C'est la
    liste que ce code parcourt, et c'est sur elle qu'un banc verifie le rang
    d'une cible.
    """
    lots = []
    for lot_id, documents_du_lot in _grouper_par_lot(documents):
        # `completude_des_planches` ne rend `None` que **sans aucun document**,
        # et `_grouper_par_lot` ne produit jamais un lot vide : la garde qui
        # occupait cette ligne etait inatteignable, donc non mesurable. Elle a
        # ete retiree plutot que doublee d'un test impossible a ecrire -- un
        # mutant `continue` -> `break` y survivait sans qu'aucune fabrique
        # puisse l'atteindre, ce qui est la definition d'un chemin mort.
        completude, manquantes = scan_detect.completude_des_planches(
            documents_du_lot)
        frames, mires = _mesures_de_frames(documents_du_lot)
        presentes = {
            page.page_index
            for document in documents_du_lot
            for page in document.pages
            if page.page_index is not None
        }
        lots.append(PanneauDeLot(
            lot_id=lot_id,
            pages_trouvees=len(presentes),
            pages_attendues=_cardinal_de_planches(documents_du_lot),
            frames=frames,
            frames_attendues=_frames_attendues(manifeste, lot_id),
            completude=completude,
            planches_manquantes=manquantes,
            mires=mires,
            pages_muettes=_pages_muettes(documents_du_lot, lot_id),
        ))
    return RapportDeDetection(
        lots=tuple(lots), en_attente=file_en_attente(partition))


def file_en_attente(partition) -> tuple[EnAttenteDeLecture, ...]:
    """La file « en attente de lecture », **nommee fichier par fichier**.

    Le reliquat d'abord, le hors-perimetre ensuite : ce sont deux classes
    disjointes de la partition du coeur, et les fondre ferait chercher
    l'operateur au mauvais endroit -- `scan_sorting` leve a l'import si leurs
    vocabulaires se recouvrent, et c'est le meme motif ici.

    Le localisateur est rendu tel que le coeur l'ecrit : le chemin source, et
    l'index de page quand la source est un PDF -- sans quoi deux pages du meme
    fichier porteraient le meme nom dans la file.
    """
    if partition is None:
        return ()
    entrees = [
        EnAttenteDeLecture(
            fichier=_texte_de_localisateur(reste.locator),
            motif=reste.motif,
            read_rank=reste.read_rank,
        )
        for reste in partition.reliquat
    ]
    entrees.extend(
        EnAttenteDeLecture(
            fichier=_texte_de_localisateur(dehors.locator),
            motif=dehors.motif,
            projet_a_utiliser=dehors.projet_a_utiliser,
            read_rank=dehors.read_rank,
        )
        for dehors in partition.hors_perimetre
    )
    return tuple(entrees)


def _texte_de_localisateur(locator) -> str:
    """Le nom d'une page non rattachee : son fichier, et sa page s'il en a une."""
    if locator.page_index is None:
        return locator.source_path
    return f"{locator.source_path} p.{locator.page_index}"


# ---------------------------------------------------------------------------
# Les issues du jugement
# ---------------------------------------------------------------------------


def _accorder(valeur: int, singulier: str, pluriel: str) -> str:
    return f"{valeur} {singulier if valeur <= 1 else pluriel}"


def issues_du_rapport(rapport: RapportDeDetection) -> IssuesDuRapport:
    """Les issues de `E3-3` ou de `E3-4`, selon ce que le rapport porte.

    **Aucune n'est preselectionnee, et cela ne se reecrit pas ici** : c'est un
    invariant leve a la construction par :class:`panneau.ChoixExclusif`
    (`EPIC11-ARB-7`), qui refuse aussi qu'aucune issue n'ecrive et **place** le
    curseur, au montage, sur la premiere issue qui n'ecrit pas. Sur `E3-4` cette
    issue est « Compléter le QR » : c'est l'etat exact que le modele produit, et
    la maquette le montre.

    **« Compléter le QR » n'est proposee que sur une page lue dont le QR a
    echoue** (`EPIC11-ARB-29`, AC 6.7). Un lot a qui il manque une planche
    **absente** ne la recoit pas : « il n'y a rien a lire », et la reparation de
    ce manque-la est de reprendre la detection avec la planche manquante.
    """
    if rapport.lots_incomplets:
        return _issues_du_rapport_incomplet(rapport)
    return _issues_du_rapport_complet(rapport)


def _issues_du_rapport_incomplet(rapport: RapportDeDetection) -> IssuesDuRapport:
    incomplets = rapport.lots_incomplets
    frames = sum(lot.frames for lot in incomplets)
    if len(incomplets) == 1:
        a_cote_ecrire = (f"{incomplets[0].lot_id} sera écrit incomplet, "
                         f"{_accorder(frames, 'frame', 'frames')}")
    else:
        a_cote_ecrire = (f"{len(incomplets)} lots seront écrits incomplets, "
                         f"{_accorder(frames, 'frame', 'frames')}")

    issues = [Issue(ISSUE_ECRIRE, LIBELLE_ECRIRE_QUAND_MEME, ecrit=True)]
    a_cote = {ISSUE_ECRIRE: a_cote_ecrire, ISSUE_ANNULER: A_COTE_ANNULER}

    completables = rapport.pages_completables
    if completables:
        issues.append(Issue(ISSUE_COMPLETER, LIBELLE_COMPLETER_LE_QR))
        a_cote[ISSUE_COMPLETER] = (
            f"saisir ce que {completables[0].nom_court} n'a pas livré")
    else:
        # Aucune planche lue n'a de QR muet : ce qui manque est **absent**, et
        # la seule reparation est d'aller le chercher. Sans cette issue, le
        # cartouche resterait a deux issues, ce que `ChoixExclusif` accepte --
        # il en exige deux, pas trois.
        issues.append(Issue(ISSUE_REPRENDRE, LIBELLE_REPRENDRE))
        a_cote[ISSUE_REPRENDRE] = A_COTE_REPRENDRE

    issues.append(Issue(ISSUE_ANNULER, LIBELLE_ANNULER))
    return IssuesDuRapport(choix=ChoixExclusif(issues), a_cote=a_cote)


def _issues_du_rapport_complet(rapport: RapportDeDetection) -> IssuesDuRapport:
    """Les suites de `E3-3`.

    **Trois, et non quatre** : « Voir le detail d'un lot » est **retiree**
    (`EPIC11-ARB-101`, note 9, verbatim d'Egan : « Si rien n'existe on retire
    cette option »). Mesure faite le 2026-08-31 : aucun ecran de detail de lot
    n'existe dans les maquettes du temps 1.
    """
    lots = len(rapport.lots)
    libelle = ("Écrire les frames de ce lot" if lots <= 1
               else f"Écrire les frames de ces {lots} lots")
    return IssuesDuRapport(
        choix=ChoixExclusif([
            Issue(ISSUE_ECRIRE, libelle, ecrit=True),
            Issue(ISSUE_REPRENDRE, LIBELLE_REPRENDRE),
            Issue(ISSUE_ANNULER, LIBELLE_ANNULER),
        ]),
        a_cote={
            ISSUE_ECRIRE: _accorder(rapport.frames, "frame", "frames"),
            ISSUE_REPRENDRE: A_COTE_REPRENDRE,
            ISSUE_ANNULER: A_COTE_ANNULER,
        },
    )
