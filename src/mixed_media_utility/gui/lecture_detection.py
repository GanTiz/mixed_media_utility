# -*- coding: utf-8 -*-
"""Lecture, cote GUI, du document de detection de scan (story 7.4, AC 1 et 2).

**Ce module LIT et n'ecrit rien.** Il ouvre le document ecrit par
``scan detect`` (story 5.25) sous
``scans/<ingest_slug>/detections/detect-<horodatage>.json``, le donne a relire
au coeur (:func:`scan_previz.scan_previz_from_json_dict` -- la forme normative,
ses vocabulaires fermes et ses invariants), et pose par-dessus exactement
trois services dont la GUI a besoin :

1. **l'acces par adresse** ``(read_rank, page_index, slot_index)``, celle que
   ``scan_previz`` declare stable (``PAGE_ADDRESS_FIELDS``,
   ``FRAME_ZONE_ADDRESS_FIELDS``) -- l'ecran DESIGNE par cette adresse, il
   n'ecrit jamais par elle ;
2. **les marqueurs de coin manquants**, par difference entre
   ``layout.CORNER_MARKER_IDS`` et ce que la page porte -- des IDENTIFIANTS,
   jamais des positions : sans homographie il n'existe aucune position
   attendue, et en fabriquer une donnerait une geometrie fausse d'apparence
   valide, exactement ce que le refus du coeur evite ;
3. **les deux verrous** d'``A8`` -- identite (QR) et geometrie (ArUco) --,
   chacun rendu a partir de CHAMPS FERMES et **jamais** de l'autre, ni de la
   presence des zones.

Ce que ce module s'interdit, et qui est mesure par grep dans les tests :

* **aucune geometrie refaite** -- pas de ``compute_template_homography``, pas
  de ``resolve_page_geometry``, pas de ``build_page_crop_plan``, aucune
  conversion mm -> px, aucune constante de dpi. La taille en pixels d'une zone
  se LIT (``crop_*_px``), elle ne se calcule pas (``EPIC7-ARB-15``) ;
* **aucune decision prise sur le CONTENU de ``refusal_reason``**. Cette phrase
  francaise s'affiche verbatim et ne se teste jamais -- ni sous-chaine, ni
  prefixe, ni suffixe, ni casse (``EPIC7-ARB-66``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .. import layout, qr_codes, scan_detection, scan_previz

# ---------------------------------------------------------------------------
# Le code de refus enumere -- champ de COEUR, LIVRE depuis le 2026-08-26
# ---------------------------------------------------------------------------

#: Nom du champ, par page, ou la story de coeur **5.27** (``EPIC7-ARB-66``,
#: geste 2) pose le code de refus enumere, sur le modele des constantes de
#: ``relink.py``.
#:
#: **Etat mesure du depot au 2026-08-26 : 5.27 EST livree** (vague 2 bis).
#: `scan_detection` pose desormais un code d'un vocabulaire ferme a cote de la
#: phrase, et `scan_previz` le transporte jusqu'au document. Le nom de la cle,
#: qui etait une hypothese de 7.4, a ete **repris tel quel** par 5.27 : il n'y
#: a jamais eu qu'un nom.
#:
#: Ce que la livraison ne change PAS -- et c'est ce qu'il faut lire avant de
#: toucher a ce module :
#:
#: * le **REPLI de l'AC 1 reste permanent** : un document ecrit avant 5.27
#:   n'en portera jamais de code, donc la GUI affiche la phrase seule. Elle
#:   n'invente **jamais** de code et n'en deduit aucun de la phrase ;
#: * la GUI **ne branche jamais sur la phrase** ``refusal_reason``, livree ou
#:   non. Le code est ce sur quoi un ecran a le droit de brancher, la phrase
#:   est ce qu'il a le droit de montrer.
#:
#: **Correction du 2026-08-26** (`[Review][Patch]` sur 7.4, regime
#: `EPIC7-ARB-78`), issue du finding `BH-8` de la revue de vague 2 bis : la
#: tolerance de lecture de ce champ est desormais **la meme des deux cotes**.
#: Le coeur (`scan_previz._code_de_refus`) traite « rien d'exploitable » comme
#: absent -- vide, blanc, non textuel --, et ce module fait de meme. Le motif
#: est celui que la vague ecrit elle-meme : un champ **purement informatif** ne
#: peut pas rendre un scan entier illisible, et un code blanc se lirait comme
#: un code, ce qui est pire que pas de code.
CLE_CODE_DE_REFUS = "refusal_code"

# ---------------------------------------------------------------------------
# Les trois etats d'un verrou (AC 2). Le troisieme n'est pas une fusion des
# deux premiers : c'est « le document ne le dit pas ».
# ---------------------------------------------------------------------------

VERROU_TENU = "tenu"                # vert : le document dit que ce verrou tient
VERROU_ROMPU = "rompu"              # rouge : le document dit qu'il ne tient pas
VERROU_INDETERMINE = "indetermine"  # le document ne le dit pas

ETATS_DE_VERROU: tuple[str, ...] = (VERROU_TENU, VERROU_ROMPU, VERROU_INDETERMINE)

# ---------------------------------------------------------------------------
# Motifs de non-proposition des zones (AC 2). Ce sont des CLES de catalogue,
# pas des phrases : le libelle vit dans `catalogue.py`.
# ---------------------------------------------------------------------------

MOTIF_IDENTITE = "scan-motif-identite"
MOTIF_GEOMETRIE = "scan-motif-geometrie"
MOTIF_AUCUNE_ZONE = "scan-motif-aucune-zone"
#: Le motif NEUTRE, pose par `EPIC7-ARB-75` (revue de vague 3) : la planche a
#: ete refusee au scan et **le document ne dit pas lequel des deux verrous a
#: lache**. Il ne nomme aucun verrou, exprès -- c'est le seul motif honnête
#: dans ce regime. Le detail reel arrive par `refusal_reason`, affiche
#: verbatim juste a cote (`scan_jugement.BandeauDEtatDePage`).
MOTIF_REFUS_AU_SCAN = "scan-motif-refus-au-scan"


class LectureDetectionError(ValueError):
    """Document de detection illisible ou non conforme.

    Enveloppe le refus du coeur plutot que de le reparer : la GUI n'a aucune
    tolerance propre. Un document altere est refuse **ici comme la-bas**.
    """


# ---------------------------------------------------------------------------
# Une page, telle que la GUI la lit
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PageLue:
    """Une page du document : l'objet du coeur, plus ce que le coeur n'a pas.

    ``page`` est le :class:`~scan_previz.ScanPrevizPage` relu par le coeur, et
    il fait foi sur tout ce qu'il porte. ``code_de_refus`` est le **seul**
    ajout : il vaut ``None`` sur tout document ecrit avant la story de coeur
    5.27 -- c'est-a-dire, au 2026-08-25, sur **tous**.
    """

    page: scan_previz.ScanPrevizPage
    code_de_refus: str | None

    @property
    def adresse(self) -> tuple[int, int | None]:
        """L'adresse de la page : ``(read_rank, page_index)``.

        Les deux, toujours, et **jamais l'un deduit de l'autre** : une page
        peut etre lue en troisieme et declarer etre la page 1 du lot.
        """
        return (self.page.read_rank, self.page.page_index)

    @property
    def marqueurs_manquants(self) -> tuple[int, ...]:
        """Les identifiants de coin attendus que la page ne porte pas.

        Difference d'ensembles sur ``layout.CORNER_MARKER_IDS``, dans l'ordre
        de cette constante. **Des identifiants, aucune position** : le rendu
        les NOMME et n'en dessine aucun.
        """
        portes = {marqueur.marker_id for marqueur in self.page.corner_markers}
        return tuple(
            identifiant
            for identifiant in layout.CORNER_MARKER_IDS
            if identifiant not in portes
        )

    def zone(self, slot_index: int) -> scan_previz.PrevizFrameZone:
        """La zone de cet emplacement, ou ``KeyError``.

        Recherche par ``slot_index`` et non par position dans la liste : un
        acces positionnel rendrait la premiere zone quel que soit
        l'emplacement demande, et c'est litteralement le mutant M25 de la
        story 5.7.
        """
        for zone in self.page.frame_zones:
            if zone.slot_index == slot_index:
                return zone
        raise KeyError(
            f"aucune zone d'emplacement {slot_index} sur la page "
            f"{self.adresse}"
        )


# ---------------------------------------------------------------------------
# Le document
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DocumentLu:
    """Le document de detection, relu et adressable. **Lecture seule.**"""

    previz: scan_previz.ScanPreviz
    pages: tuple[PageLue, ...]

    def page_par_adresse(self, read_rank: int, page_index: int | None) -> PageLue:
        """La page de cette adresse, ou ``KeyError``.

        L'adresse est le COUPLE : deux pages peuvent porter le meme
        ``page_index`` a ``None`` (plusieurs planches au QR non lu sont
        legitimement muettes), et seul ``read_rank`` les distingue alors.
        """
        for page in self.pages:
            if page.page.read_rank == read_rank and page.page.page_index == page_index:
                return page
        raise KeyError(
            f"aucune page d'adresse (read_rank={read_rank}, "
            f"page_index={page_index}) dans ce document"
        )

    def page_par_rang(self, read_rank: int) -> PageLue:
        """La page de ce rang de lecture, ou ``KeyError``."""
        for page in self.pages:
            if page.page.read_rank == read_rank:
                return page
        raise KeyError(f"aucune page de rang de lecture {read_rank}")

    def zone_par_adresse(
        self, read_rank: int, page_index: int | None, slot_index: int
    ) -> scan_previz.PrevizFrameZone:
        """La zone de cette adresse complete, ou ``KeyError``."""
        return self.page_par_adresse(read_rank, page_index).zone(slot_index)


def depuis_json(document: Any) -> DocumentLu:
    """Relire un document deja charge en memoire.

    Le coeur valide (vocabulaires fermes, unicite des adresses, coherence des
    compteurs) ; ce module ne fait qu'ajouter le code de refus, lu **du mapping
    brut**.

    **Pourquoi du mapping brut alors que le coeur le porte depuis 5.27**
    (2026-08-26) : `ScanPrevizPage.refusal_code` existe desormais, et cette
    lecture-ci fait donc double emploi. Elle est **conservee volontairement**
    tant qu'aucune story ne les reunit, pour une raison mesuree -- le repli de
    l'AC 1 de 7.4 est **permanent**, donc ce module doit rester capable de lire
    un document **anterieur** a 5.27, ou la cle est absente. Les deux chemins
    ont la **meme tolerance** depuis le correctif du 2026-08-26 (`BH-8`) ;
    c'est cette egalite qui rend le double emploi sans danger, et c'est elle
    qu'il faut preserver si l'un des deux bouge.

    Verse a `deferred-work.md` : reunir les deux lectures quand une story de
    GUI touchera legitimement ce module.
    """
    try:
        previz = scan_previz.scan_previz_from_json_dict(document)
    except scan_previz.ScanPrevizError as erreur:
        raise LectureDetectionError(str(erreur)) from erreur

    codes = _codes_de_refus_par_rang(document)
    pages = tuple(
        PageLue(page=page, code_de_refus=codes.get(page.read_rank))
        for page in previz.pages
    )
    return DocumentLu(previz=previz, pages=pages)


def charger(chemin: Path | str) -> DocumentLu:
    """Ouvrir un document de detection sur le disque. **Lecture seule.**"""
    chemin = Path(chemin)
    try:
        brut = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError) as erreur:
        raise LectureDetectionError(
            f"document de detection illisible ({chemin}) : {erreur}"
        ) from erreur
    return depuis_json(brut)


def _codes_de_refus_par_rang(document: Any) -> dict[int, str]:
    """Les codes de refus portes par le document, par rang de lecture.

    Rien n'est invente : une page qui ne porte pas la cle n'entre pas dans le
    dictionnaire, et une cle presente mais **sans rien d'exploitable** est
    ignoree -- vide, uniquement blanche, ou non textuelle. Un code blanc se
    lirait comme un code, ce qui est pire que pas de code.

    **La tolerance est exactement celle du coeur** (`scan_previz._code_de_refus`),
    et c'est voulu : les deux extremites du champ partageaient le meme trou sur
    la chaine uniquement blanche (finding `BH-8` de la revue de vague 2 bis,
    2026-08-26). Le `strip` **decide**, il ne normalise pas : un code qui porte
    du contenu traverse **verbatim**, espaces compris.
    """
    codes: dict[int, str] = {}
    if not isinstance(document, Mapping):
        return codes
    pages = document.get("pages")
    if not isinstance(pages, (list, tuple)):
        return codes
    for page in pages:
        if not isinstance(page, Mapping):
            continue
        valeur = page.get(CLE_CODE_DE_REFUS)
        rang = page.get("read_rank")
        # `isinstance(rang, int)` exclut `True`/`False`, qui sont des `int` en
        # Python : un booleen n'est pas un rang de lecture.
        if isinstance(rang, bool) or not isinstance(rang, int):
            continue
        if isinstance(valeur, str) and valeur.strip():
            codes[rang] = valeur
    return codes


# ---------------------------------------------------------------------------
# Les deux verrous (AC 2) -- deux fonctions, deux jeux de champs, zero
# croisement
# ---------------------------------------------------------------------------


def etat_verrou_identite(page: PageLue) -> str:
    """Le verrou d'IDENTITE : quel lot, quelle page. Lu du QR.

    Champs lus, et **eux seuls** : ``qr_status`` et ``status``. Ni
    ``homography``, ni ``corner_markers``, ni ``frame_zones`` -- un verrou
    derive de l'autre les fondrait en un seul signe, ce qui est un Don't de
    ``DESIGN.md``.

    * **rompu** quand le QR n'a rien livre (``qr_status`` autre que
      ``decoded``) : le document dit que ce verrou ne tient pas ;
    * **tenu** quand le QR a livre ET que la page est ``ok`` : le document dit
      qu'il tient ;
    * **indetermine** quand le QR a livre et que la page est pourtant refusee.
      C'est le cas mesure de la planche **perimee** (revue de 5.17, bloquant
      B1) : elle sort avec une identite parfaitement lisible et un refus, et
      **aucun champ ferme du document ne dit lequel des deux verrous a
      motive ce refus**. Un vert serait faux, un rouge le serait aussi, et
      lire la phrase francaise serait pire que les deux. C'est exactement le
      trou que le code de refus enumere de la story de coeur 5.27 comblera --
      non livree au 2026-08-25, d'ou cet etat.
    """
    if page.page.qr_status != qr_codes.DECODE_OK:
        return VERROU_ROMPU
    if page.page.status == scan_detection.PAGE_OK:
        return VERROU_TENU
    return VERROU_INDETERMINE


def etat_verrou_geometrie(page: PageLue) -> str:
    """Le verrou de GEOMETRIE : ou. Lu des ArUco et de l'homographie.

    Champs lus, et **eux seuls** : ``homography`` et ``corner_markers``. Ni
    ``qr_status``, ni ``status``, ni ``frame_zones``.

    * **tenu** : homographie presente ET les quatre coins de
      ``layout.CORNER_MARKER_IDS`` portes ;
    * **rompu** : homographie absente ET aucun coin porte -- le document dit
      franchement que la geometrie n'a pas ete resolue. C'est ce que le
      producteur d'aujourd'hui ecrit sur toute page refusee
      (``scan_detection._detect_one_page``, voie de refus) ;
    * **indetermine** : toute description PARTIELLE -- une homographie sans
      ses quatre coins, ou des coins sans homographie. Le producteur
      d'aujourd'hui n'en emet pas (``MIN_CORNER_MARKERS_REQUIRED`` vaut
      quatre : c'est tout ou rien), mais la GUI lit des documents qu'elle
      n'ecrit pas, et de versions qu'elle ne choisit pas. Devant une
      description partielle elle **ne tranche pas** plutot que de choisir au
      hasard entre un vert faux et un rouge faux.
    """
    homographie = page.page.homography is not None
    manquants = page.marqueurs_manquants
    if homographie and not manquants:
        return VERROU_TENU
    if not homographie and len(manquants) == len(layout.CORNER_MARKER_IDS):
        return VERROU_ROMPU
    return VERROU_INDETERMINE


def motif_de_non_proposition(page: PageLue) -> str | None:
    """Pourquoi cette page ne propose aucune zone, ou ``None`` si elle en a.

    Rend une CLE de catalogue. L'ordre compte et il est celui du produit :
    « Quand le QR n'est pas decode, les zones d'image ne sont pas proposees --
    et l'ecran le dit avec ce motif-la, pas avec "geometrie non resolue" »
    (``EXPERIENCE.md``, State Pattern « QR non decode »). L'identite passe
    donc **avant** la geometrie.

    Le quatrieme motif couvre le cas ou les deux verrous tiennent et ou le
    document ne porte pourtant aucune zone -- une page de calibration, ou une
    page dont le plan de decoupe etait indisponible (``cli.py``, boucle
    ``crop_plans``, qui la montre « sans zone » plutot que de tomber).

    **`EPIC7-ARB-75` (revue de vague 3) -- on ne nomme plus un verrou qu'on ne
    peut pas distinguer.** Jusqu'ici, toute identite non-``tenu`` sortait sous
    ``MOTIF_IDENTITE``. C'etait faux sur le cas de terrain dominant, et mesure
    comme tel : une planche au QR **parfaitement decode** dont les quatre ArUco
    ont echoue sort avec ``identite = indetermine`` et ``geometrie = rompu``,
    et l'ecran lui disait « le QR n'a pas livre l'identite de cette planche »
    -- alors qu'il avait tout livre. L'operatrice etait envoyee verifier le
    mauvais element, sur la seule phrase qu'elle lit pour decider quoi refaire.

    La distinction que fait desormais cette fonction est celle que le document
    **porte reellement** :

    * identite ``rompu`` -- le QR n'a rien livre : le document l'affirme, on le
      dit (``MOTIF_IDENTITE``) ;
    * identite ``indetermine`` -- le QR a livre et la page est pourtant
      refusee : **aucun champ ferme du document ne dit lequel des deux verrous
      a motive ce refus**. On ne tranche pas : ``MOTIF_REFUS_AU_SCAN``, neutre,
      et ``refusal_reason`` verbatim porte le detail ;
    * identite ``tenu`` et geometrie non-``tenu`` -- la, et la seulement, la
      geometrie est nommement en cause (``MOTIF_GEOMETRIE``).

    Ce que la revue a **infirme** au passage : ``MOTIF_GEOMETRIE`` n'est pas du
    code mort. Il est inatteignable avec le producteur d'aujourd'hui (une page
    ``ok`` a forcement son homographie, et ``MIN_CORNER_MARKERS_REQUIRED`` vaut
    quatre : tout ou rien), mais la GUI lit des documents qu'elle n'ecrit pas
    -- une description **partielle** venue d'une autre version le rend, et
    ``test_le_motif_de_geometrie_n_est_rendu_que_quand_l_identite_tient`` en
    construit le cas.

    C'est un regime **permanent** et non une attente : 5.27, qui devait livrer
    le code de refus enumere permettant de nommer le bon verrou, a ete
    abandonnee le 2026-08-25.
    """
    if page.page.frame_zones:
        return None
    if etat_verrou_identite(page) == VERROU_ROMPU:
        return MOTIF_IDENTITE
    if etat_verrou_identite(page) == VERROU_INDETERMINE:
        return MOTIF_REFUS_AU_SCAN
    if etat_verrou_geometrie(page) != VERROU_TENU:
        return MOTIF_GEOMETRIE
    return MOTIF_AUCUNE_ZONE


__all__ = [
    "CLE_CODE_DE_REFUS",
    "DocumentLu",
    "ETATS_DE_VERROU",
    "LectureDetectionError",
    "MOTIF_AUCUNE_ZONE",
    "MOTIF_GEOMETRIE",
    "MOTIF_IDENTITE",
    "MOTIF_REFUS_AU_SCAN",
    "PageLue",
    "VERROU_INDETERMINE",
    "VERROU_ROMPU",
    "VERROU_TENU",
    "charger",
    "depuis_json",
    "etat_verrou_geometrie",
    "etat_verrou_identite",
    "motif_de_non_proposition",
]
