"""Composition pure des planches PDF (story 4.1).

Ce module calcule le **plan de page** complet d'un lot -- pagination,
zones de frames, QR, marqueurs ArUco, patchs, texte -- sans aucune ecriture,
sans reportlab et sans lecture de pixel. Le rendu (``pdf_render``) consomme ce
plan sans rien recalculer, et la previz (story 4.9) projettera le meme plan:
sa forme est un contrat.

Contrat du plan (consomme par pdf_render et par la story 4.9)
-------------------------------------------------------------
``compose_lot_plan`` rend un :class:`LotComposition`:

- identite: ``project_id`` / ``rush_id`` / ``lot_id`` / ``fps_target``,
  parametres resolus (``template_id``, ``patch_preset_id``, ``render_dpi``,
  ``scan_dpi``), ``frames_dir`` (relatif au projet) et ``pdf_filename``
  (convention EPIC4-ARB-3, ``io.naming.build_sheets_pdf_filename``);
- ``pages``: un :class:`PagePlan` par page, ``page_index`` **base zero**
  partout (convention normative 3.1; la base un n'existe qu'a l'affichage);
- chaque :class:`PagePlan` porte: les slots de frames (:class:`FrameSlotPlan`:
  zone 16:9 exacte du template, rectangle utile de l'image derive du preset
  de marge, nom de fichier de la convention 2.3, politique letterbox), le QR
  (:class:`QRPagePlan`: payload valide 2.3, budget, geometrie 4.6, emprise
  physique symbole + zone de silence), les 4 marqueurs de coin
  (:class:`MarkerPlan`, politique ``layout.PRINTED_MARKER_IDS``), les patchs
  (resolution 4.7, jamais copies) et le texte (:class:`PageTextPlan`,
  contrat 4.2 / EPIC4-ARB-8).

Determinisme
------------
Memes entrees + memes parametres -> plan strictement egal (teste). Aucune
horloge ici: la date-heure imprimee (EPIC4-ARB-8) est une **entree du rendu**,
jamais un champ du plan -- c'est precisement ce qui limite l'abandon du
byte-identique au fichier PDF sans toucher au determinisme contractuel.

Contenu du lot
--------------
Le contenu vient du manifest et de la selection **recalculee**
(``frame_selection.select_source_frames``), jamais d'un glob: l'ordre est
celui des ``output_rank``, les ``frame_timecode`` viennent de la selection
(forme ``hh:mm:ss:ff``), les noms de fichiers de la convention
``io.naming.build_extracted_frame_filename``. ``slot_index`` est continu a
l'echelle du lot (= ``output_rank``), jamais remis a zero par page.

Letterbox (piege 4)
-------------------
Les zones sont 16:9 exact. Une source non 16:9 n'est **jamais** etiree: la
politique du plan est ``letterbox-centre`` -- l'image est ajustee a
l'interieur de son rectangle utile en preservant son ratio, centree, fond
blanc. Le POC (`preserveAspectRatio=False`) n'est pas reproduit.

Rasterisation embarquee (fait documente, piege 5)
-------------------------------------------------
Les TIFF 16 bits du lot sont embarques dans le PDF en 8 bits par canal
(conversion deterministe, voir ``pdf_render.load_frame_image_for_print``).
C'est un support d'impression, pas une copie d'archivage.

Refus geometriques
------------------
Une combinaison qui ne tient pas geometriquement est **refusee**
(:class:`GeometryOverflowError`), jamais reduite en silence sous les minima
prouves: QR sous la cible 4.6, raster QR sous ~8 px/module dans le PDF
(``qr_codes.MIN_PIXELS_PER_MODULE_RELIABLE``), emprise QR debordant la bande
haute. Les deux DPI restent distincts: ``render_dpi`` (rasterisation des
elements embarques, defaut 600) et ``scan_dpi`` (consigne de scan 4.6,
``qr_codes.QR_MIN_SCAN_DPI``, seule grandeur utilisee pour classer la
geometrie du QR).
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass
from datetime import date, datetime, timezone
from types import MappingProxyType
from typing import Any, Mapping

from . import (
    gamut_map,
    layout,
    page_payload,
    page_roles,
    page_templates,
    patch_presets,
    qr_codes,
)
from .io import extraction_manifest, naming, project_layout, version_ranks
from .io import payload as payload_io
from .io.payload import PAYLOAD_SCHEMA_VERSION, PayloadBudgetReport

#: DPI de rasterisation par defaut des elements embarques dans le PDF. Egal
#: numeriquement a ``qr_codes.QR_MIN_SCAN_DPI`` mais c'est une autre grandeur:
#: l'un fabrique le PDF, l'autre est la consigne de scan imprimee (4.2). Le
#: defaut 300 du POC est refute par 4.6 a la taille cible: il n'est pas herite.
RENDER_DPI_DEFAULT = 600

#: Borne basse dure du DPI de rendu: sous 150 dpi meme les marqueurs ArUco
#: sortent du domaine confirme par 4.3 ("DICT_6X6_250 / 30 mm confirme pour
#: DPI >= 150"). Le QR impose en pratique une borne plus haute, verifiee page
#: par page contre le payload reel (jamais une constante seule).
RENDER_DPI_MIN = 150

#: Borne haute dure du DPI de rendu: 4x la consigne de scan (600 dpi, 4.6)
#: couvre toute imprimante reelle (1200-2400 dpi natifs). Au-dela, le raster
#: QR atteint des dizaines de milliers de pixels de cote et la commande
#: s'effondre en memoire au lieu de refuser (revue 4.1 du 2026-08-06).
RENDER_DPI_MAX = 2400

#: Preset de patchs par defaut.
#:
#: **`patches-14-v3` depuis `EPIC5-ARB-67`** (Egan, 2026-08-12), et le defaut est
#: **global**: il ne depend ni de la version de geometrie ni de l'orientation. Ce preset
#: est place sur les 63 gabarits du registre, donc un defaut unique suffit, et un defaut
#: conditionnel aurait cree une seconde regle a maintenir au menage d'`EPIC5-ARB-66`.
#:
#: Ce que l'ancien defaut `patches-12-v1` produisait, mesure par la revue de 5.16 (B2 de
#: la couche 3) et non deduit: une planche composee sans `--nombre-patchs` portait les
#: **trois secondaires** que l'AC 7 de 5.16 interdit sur une planche d'images, et surtout
#: `sentinel_chains(patch-values-1)` rend un jeu **vide** -- le verdict d'ecretage etait
#: donc inatteignable sur les cinq axes de ce qui s'imprimait reellement. Le defaut
#: produisait la seule configuration ou la calibration ne peut pas fonctionner.
#:
#: Ce que cet arbitrage ne fait pas: `patches-9-v1` et `patches-12-v1` restent
#: enregistres et resolvables, et les planches deja imprimees sous eux restent
#: relisibles. Leur retrait du vocabulaire operateur appartient au menage
#: d'`EPIC5-ARB-66`.
#:
#: **`patches-17-v4` depuis `EPIC5-ARB-82`** (story 5.23): meme jeu que
#: `patches-14-v3` plus les trois secondaires. Le defaut bascule parce que la
#: divergence se mesure desormais entre **deux feuilles imprimees** et qu'une derive
#: d'encre cyan ou magenta ne se voit pas sur un jeu RVB + neutres. `patches-14-v3`
#: reste enregistre, resolvable et inchange: une planche deja imprimee sous lui reste
#: relisible, et le passage au nouveau jeu se fait a l'impression suivante.
DEFAULT_PATCH_PRESET = "patches-17-v4"

#: Index de la **page de calibration**, **relu** de `page_roles` et non pose ici.
#:
#: La constante a demenage a la passe de correction de 5.16 (finding F1 de la couche 2):
#: la relecture doit refuser une page de calibration ailleurs qu'a cet index, et
#: `io/reconstruction` ne peut pas importer la composition PDF pour lire un entier. Elle
#: vit donc dans `page_roles`, qui n'importe rien -- exactement le motif qui a fait naitre
#: ce module. Le nom reste expose ici parce que c'est ici qu'on le lit le plus.
CALIBRATION_PAGE_INDEX = page_roles.CALIBRATION_PAGE_INDEX

#: Code stable de l'avertissement « ce lot ne porte pas de page de calibration ».
#:
#: Une page absente **en silence** serait exactement le faux succes que ce depot
#: combat: l'operateur croirait que la correction du lot s'ajuste sur une page dediee
#: alors qu'aucune n'a ete imprimee. Le motif chiffre accompagne le code -- il vient de
#: `patch_presets.calibration_page_refusal`, seule redaction pour les deux usages.
WARNING_NO_CALIBRATION_PAGE = "PAGE_DE_CALIBRATION_NON_COMPOSABLE"

#: Defaut de la compression de gamut (EPIC5-ARB-15). L'identite, et non
#: `gamut-map-lin-1`: la moitie « decomprimer » (`G^-1`) vit dans la story
#: 5.4b, post-MVP, et un defaut comprimant ferait imprimer, scanner et exporter
#: des frames que **rien** ne decomprime -- visiblement delavees, sans qu'aucune
#: etape n'echoue. Il bascule le jour ou 5.4b livre.
DEFAULT_GAMUT_MAP = gamut_map.DEFAULT_GAMUT_MAP

#: Politique unique de placement d'une image dans son rectangle utile.
LETTERBOX_POLICY = "letterbox-centre"

#: Bande haute reservee au QR et aux textes d'en-tete: x entre les silences des
#: marqueurs de coin, y entre la marge physique d'imprimante et la bande de frames,
#: moins cette garde. Les trois autres bornes sont **derivees de la geometrie du
#: spec** dans `_qr_band_mm`; seule la garde est un choix libre.
#: En geometrie v1 cela redonne exactement y = 5 et hauteur = 50 (la bande de frames
#: ouvrant a 60), les valeurs ecrites en litteral jusqu'au 2026-08-11.
_TOP_BAND_GUARD_MM = page_templates.TOP_BAND_GUARD_MM
#: Retrait des blocs d'en-tete dans la bande haute. Les deux nombres etaient des
#: litteraux (y = 10, hauteur = 40) jusqu'au 2026-08-11: en geometrie v1 ils valent
#: exactement `bande + 5` et `hauteur de bande - 2 x 5`, la bande ouvrant a 5 sur
#: 50 mm. Sous la v2 la bande haute ne fait plus que 38,8 mm de haut, et les litteraux
#: auraient pose l'en-tete jusqu'a 50 mm -- donc **dans** la bande de frames, qui ouvre
#: a 48,8 mm. Un test verrouille la non-regression des deux valeurs v1.
_TEXT_HEADER_INSET_MM = 5.0
_TEXT_GAP_MM = 2.0
_SLOT_LABEL_OFFSET_MM = 1.0
_SLOT_LABEL_HEIGHT_MM = 4.0

# --- Typographie du texte lisible (story 4.2, AC 5) ------------------------
#
# Police standard PDF base-14 (fournie par le lecteur, jamais embarquee),
# noir sur blanc, ASCII. Tailles minimales posees en constantes; instruction
# contre la bande disponible (AC 5): un identifiant canonique atteint 48
# caracteres et le bloc d'identite portrait fait 90 mm -- a 10 pt le modele
# de largeur ne loge que ~42 caracteres, a 8 pt il en loge 53. Les lignes
# d'identifiants s'impriment donc au plancher de 8 pt (jamais en dessous,
# AC 6), et le rang >= 10 pt est tenu par "page N/M" et la cadence dans
# l'en-tete.
TEXT_FONT_NAME = "Helvetica"
BODY_FONT_MIN_PT = 8.0
IDENTITY_FONT_MIN_PT = 10.0

#: Modele de largeur conservatif: 0.6 em par caractere. La composition est
#: pure (pas de reportlab, donc pas de metriques AFM): ce majorant simple et
#: deterministe de l'Helvetica reelle (~0.52 em de moyenne) garantit qu'une
#: ligne declaree "tenante" tient aussi au rendu.
CHAR_WIDTH_EM = 0.6

#: Marqueur visible de troncature (AC 6): jamais de coupe silencieuse.
TRUNCATION_MARKER = "..."

#: Cardinal des lignes d'identite du bloc ``footer_block`` (label, projet,
#: rush, page+cadence). Le rendu insere la ligne de date-heure (EPIC4-ARB-8)
#: APRES ces lignes: la constante est le contrat partage (revue 4.2: le rendu
#: dupliquait la valeur en ``lines[:4]`` magique).
FOOTER_IDENTITY_LINE_COUNT = 4

#: Queue preservee lors d'une troncature: la fin d'un identifiant derive
#: porte le suffixe de hachage discriminant (`-` + 8 hex, io.naming).
_TRUNCATION_TAIL_CHARS = 9


class CompositionError(ValueError):
    """Racine des refus de composition (message actionnable, jamais un trace)."""


class ParameterVocabularyError(CompositionError):
    """Un parametre sort du vocabulaire ferme (EPIC4-ARB-1 / registres)."""


class GeometryOverflowError(CompositionError):
    """La combinaison demandee ne tient pas geometriquement (jamais reduite)."""


class LotContentError(CompositionError):
    """Le manifest ne permet pas de composer le lot demande."""


@dataclass(frozen=True)
class MarkerPlan:
    """Un marqueur ArUco a imprimer: id, centre et cote en mm."""

    marker_id: int
    center_x_mm: float
    center_y_mm: float
    size_mm: float


@dataclass(frozen=True)
class FrameSlotPlan:
    """Un slot de frame sur la page.

    ``zone_rect_mm`` est la zone 16:9 du template (emprise imprimee);
    ``image_rect_mm`` le rectangle utile derive du preset de marge
    (``page_templates.frame_image_rect_mm``), dans lequel l'image est posee
    selon ``letterbox_policy``. ``frame_filename`` est le nom de la convention
    2.3/3.1, a resoudre sous ``frames_dir`` du plan.
    """

    slot_index: int
    frame_timecode: str
    frame_filename: str
    zone_name: str
    zone_rect_mm: tuple[float, float, float, float]
    image_rect_mm: tuple[float, float, float, float]
    letterbox_policy: str


@dataclass(frozen=True)
class QRPagePlan:
    """QR de la page: payload valide, budget, geometrie et emprise physique.

    ``footprint_rect_mm`` inclut la zone de silence ISO (4 modules): c'est
    l'emprise blanche totale a garder libre, celle que le test global de
    non-chevauchement confronte aux autres elements.
    """

    payload: dict[str, Any]
    payload_text: str
    budget: PayloadBudgetReport
    module_side: int
    required_print_size_mm: float
    print_size_mm: float
    geometry_status: str
    scan_dpi: int
    footprint_rect_mm: tuple[float, float, float, float]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class SlotLabel:
    """Ligne de texte sous une zone de frame (rush + slot + timecode)."""

    text: str
    rect_mm: tuple[float, float, float, float]


@dataclass(frozen=True)
class TextBlock:
    """Un bloc de texte pret a imprimer: zone, taille de police, lignes.

    C'est le contrat exact du rendu (et de la previz 4.9): chaque ligne est
    ASCII, tient dans la largeur du bloc au modele ``CHAR_WIDTH_EM``, et la
    police ne descend jamais sous ``BODY_FONT_MIN_PT`` (AC 5/6 de 4.2).
    """

    name: str
    rect_mm: tuple[float, float, float, float]
    font_pt: float
    lines: tuple[str, ...]


@dataclass(frozen=True)
class PageTextPlan:
    """Contrat du texte lisible de la page (story 4.2 / EPIC4-ARB-8).

    ``zones_mm`` porte les emprises: ``header_left`` / ``header_right``
    (recalculees autour de l'emprise reelle du QR), ``footer_block`` (bloc
    d'identite) et ``footer_line`` (consigne de scan). ``blocks`` porte les
    lignes exactement imprimees: le bloc d'identite ``footer_block`` contient
    les identifiants canoniques **verbatim** (l'egalite a l'octet pres avec le
    payload QR et les noms de fichiers est le mecanisme de secours 4.6); les
    en-tetes portent des rappels eventuellement tronques avec marqueur
    visible. La date-heure n'est pas un champ du plan (EPIC4-ARB-8): le rendu
    l'ajoute au bloc ``footer_block``.
    """

    sheet_label: str
    project_id: str
    rush_id: str
    page_number_text: str
    fps_display: str
    scan_instruction: str
    technical_footer: str
    zones_mm: dict[str, tuple[float, float, float, float]]
    blocks: tuple[TextBlock, ...]
    slot_labels: tuple[SlotLabel, ...]
    #: Ou le **rendu** insere la ligne de date-heure (`EPIC4-ARB-8`): nom du bloc et
    #: rang dans ses lignes. La date n'est pas un champ du plan -- c'est ce qui garde le
    #: plan deterministe -- mais **sa place** en est un, et elle doit l'etre: elle
    #: valait `("footer_block", 4)` en disposition historique, ou les quatre lignes
    #: d'identite la precedent, et vaut `("footer_technical_1", 0)` quand l'identite
    #: passe en entete et que la date devient une ligne technique. Le rendu lisait
    #: jusqu'ici la constante `FOOTER_IDENTITY_LINE_COUNT`, donc il **decidait** de la
    #: place -- et une disposition ou l'identite n'est plus dans le pied lui aurait fait
    #: poser la date au milieu des lignes techniques, sans qu'aucune etape n'echoue.
    date_line_slot: tuple[str, int] = ("footer_block", FOOTER_IDENTITY_LINE_COUNT)


@dataclass(frozen=True)
class PagePlan:
    """Plan complet d'une page de planche."""

    page_index: int
    template_id: str
    frames: tuple[FrameSlotPlan, ...]
    qr: QRPagePlan
    markers: tuple[MarkerPlan, ...]
    patches: tuple[patch_presets.PlacedPatch, ...]
    text: PageTextPlan


@dataclass(frozen=True)
class LotComposition:
    """Plan complet du lot: le contrat que le rendu et la previz consomment."""

    project_id: str
    rush_id: str
    lot_id: str
    fps_target: float
    page_format: str
    orientation: str
    frames_per_page: int
    margin_preset: str
    template_id: str
    patch_preset_id: str
    #: Identifiant **deja resolu** de la compression de gamut appliquee aux
    #: frames. Source unique: le payload QR, le raster rendu et le manifest
    #: ecrit par 5.11 lisent tous les trois **cet** attribut. Une seconde
    #: resolution ailleurs rouvrirait la possibilite qu'ils divergent.
    gamut_map_id: str
    render_dpi: int
    scan_dpi: int
    frames_dir: str
    pdf_filename: str
    page_count: int
    pages: tuple[PagePlan, ...]
    warnings: tuple[str, ...]


# ---------------------------------------------------------------------------
# Resolution des parametres a vocabulaire ferme (AC 2) -- chaque refus nomme
# le vocabulaire.
# ---------------------------------------------------------------------------


def resolve_page_format(value: str | None) -> str:
    resolved = page_templates.DEFAULT_PAGE_FORMAT if value is None else str(value)
    if resolved not in page_templates.PAGE_FORMATS:
        raise ParameterVocabularyError(
            f"Format de page hors vocabulaire: '{resolved}'. Formats acceptes: "
            f"{', '.join(page_templates.PAGE_FORMATS)}."
        )
    return resolved


def resolve_orientation(value: str | None) -> str:
    resolved = page_templates.ORIENTATION_PORTRAIT if value is None else str(value)
    if resolved not in page_templates.ORIENTATIONS:
        raise ParameterVocabularyError(
            f"Orientation hors vocabulaire: '{resolved}'. Orientations acceptees: "
            f"{', '.join(page_templates.ORIENTATIONS)}."
        )
    return resolved


def _as_exact_int(value: Any) -> int | None:
    """Entier exact ou ``None``: jamais de troncature silencieuse.

    Le vocabulaire ferme de l'AC 2 vaut aussi pour les consommateurs API
    (previz 4.9): ``2.9`` ne devient jamais ``2``, ``True`` jamais ``1``
    (revue 4.1 du 2026-08-06).
    """
    if isinstance(value, bool):
        return None
    try:
        resolved = int(value)
    except (TypeError, ValueError):
        return None
    if resolved != value:
        return None
    return resolved


def resolve_frames_per_page(
    orientation: str, value: int | None, geometry_version: str | None = None
) -> int:
    """Resoudre ``--frames-par-page`` contre le vocabulaire **de la version**.

    Le vocabulaire depend de la geometrie depuis la story 5.18 (`EPIC5-ARB-62`): un
    cardinal dont la surface par frame ne progresse pas significativement par rapport au
    cardinal superieur sort du vocabulaire de la version **et de l'orientation** ou la
    mesure le constate (`EPIC5-ARB-64`), et reste resolvable ailleurs. Le refus doit donc
    **nommer le motif chiffre**, et non seulement la liste: « 6 n'est pas dans
    (1, 2, 3, 4, 8) » n'apprend rien a qui vient de composer un lot en 6f la semaine
    precedente.
    """
    if value is None:
        return page_templates.DEFAULT_FRAMES_PER_PAGE
    allowed = page_templates.frames_per_page_vocabulary(orientation, geometry_version)
    resolved = _as_exact_int(value)
    if resolved not in allowed:
        version = (page_templates.DEFAULT_GEOMETRY_VERSION
                   if geometry_version is None else geometry_version)
        # L'orientation est passee: le motif du retrait est celui de **cette**
        # orientation, et un cardinal retire ailleurs n'en produit aucun ici.
        retired = page_templates.retired_cardinal_reason(
            version, resolved, orientation)
        motive = f" Motif du retrait: {retired}." if retired else ""
        raise ParameterVocabularyError(
            f"Cardinal de frames par page hors vocabulaire: '{value}'. En "
            f"orientation {orientation} et en geometrie {version} les valeurs "
            f"acceptees sont: {', '.join(str(v) for v in allowed)} "
            f"(EPIC4-ARB-1).{motive}"
        )
    return resolved


def resolve_margin_preset(value: str | None) -> str:
    resolved = page_templates.DEFAULT_MARGIN_PRESET if value is None else str(value)
    if resolved not in page_templates.MARGIN_PRESETS_MM:
        presets = ", ".join(page_templates.MARGIN_PRESETS_MM)
        raise ParameterVocabularyError(
            f"Preset de marge hors vocabulaire: '{value}'. Presets acceptes "
            f"(en mm): {presets}. La marge est un preset discret du template "
            "(decision 4.4), jamais un flottant libre."
        )
    return resolved


def resolve_geometry_version(value: str | None) -> str:
    """Resoudre la version de geometrie de page: identifiant du registre, ou le defaut.

    **Pourquoi ce parametre existe** (story 5.15): le defaut a bascule sur la v2, et
    sans lui la v1 deviendrait non composable -- donc l'additivite de la story ne
    serait pas mesurable, et un lot deja imprime ne pourrait plus voir son plan
    reconstruit. Le vocabulaire est ferme, comme partout: un identifiant inconnu est
    refuse en nommant les versions connues, jamais un repli silencieux sur le defaut.
    Un repli produirait un `template_id` qui ment sur la geometrie imprimee, et le
    seul symptome serait une homographie fausse au scan, des mois plus tard.
    """
    if value is None:
        return page_templates.DEFAULT_GEOMETRY_VERSION
    text = str(value)
    if text in page_templates.GEOMETRY_VERSIONS:
        return text
    raise ParameterVocabularyError(
        f"Version de geometrie de page inconnue: {value!r}. Versions connues: "
        f"{', '.join(page_templates.GEOMETRY_VERSIONS)}. Defaut: "
        f"{page_templates.DEFAULT_GEOMETRY_VERSION}."
    )


def resolve_patch_preset(value: str | None) -> str:
    """Resoudre ``--nombre-patchs``: identifiant de preset 4.7 ou cardinal."""
    if value is None:
        return DEFAULT_PATCH_PRESET
    text = str(value)
    known = patch_presets.known_preset_ids()
    if text in known:
        return text
    try:
        cardinal = int(text)
    except ValueError:
        cardinal = None
    if cardinal is not None:
        matching = [
            preset_id
            for preset_id in known
            if len(patch_presets.get_patch_preset(preset_id).value_ids) == cardinal
        ]
        # Ambiguite refusee, pas subie (story 5.9, AC 10). La boucle rendait
        # le **premier** preset du registre, donc ce qui s'imprime dependait de
        # l'ordre d'un litteral. Les cardinaux livres restent uniques (9, 12,
        # 18), donc le cas n'est pas atteignable aujourd'hui -- raison de plus
        # pour le fermer maintenant, pendant qu'aucun comportement observable
        # n'en depend.
        if len(matching) > 1:
            raise ParameterVocabularyError(
                f"Cardinal de patchs ambigu: '{value}' correspond a plusieurs "
                f"presets ({', '.join(sorted(matching))}). Designez le preset par "
                "son identifiant. Laisser l'ordre du registre trancher ferait "
                "dependre ce qui s'imprime d'un detail d'ecriture."
            )
        if matching:
            return matching[0]
    cardinals = sorted(
        len(patch_presets.get_patch_preset(preset_id).value_ids) for preset_id in known
    )
    raise ParameterVocabularyError(
        f"Aucun preset de patchs ne correspond a '{value}'. Presets "
        f"disponibles (registre 4.7): {', '.join(known)} -- designables par "
        f"identifiant ou par cardinal de valeurs ({', '.join(str(c) for c in cardinals)})."
    )


def resolve_gamut_map(value: str | None) -> str:
    """Resoudre ``--gamut-map``: identifiant du registre, ou le defaut.

    **Difference deliberee avec `resolve_patch_preset`**: aucune resolution par
    cardinal ni par abreviation. La resolution par cardinal « premier gagnant
    sur l'ordre du dict » est un defaut deja consigne et ferme par 5.9; en
    recreer un jumeau ici serait d'autant plus grave que la valeur resolue est
    ensuite **imprimee dans le QR et persistee au manifest**.

    Un identifiant inconnu est refuse en nommant le vocabulaire, **jamais un
    repli silencieux sur l'identite**: un repli produirait un `gamut_map_id` qui
    ment sur la transformation appliquee, et le seul symptome serait une
    expansion fausse au scan, des mois plus tard.
    """
    if value is None:
        return DEFAULT_GAMUT_MAP
    text = str(value)
    if text in gamut_map.known_gamut_map_ids():
        return text
    raise ParameterVocabularyError(
        f"Compression de gamut inconnue: {value!r}. Identifiants connus: "
        f"{', '.join(gamut_map.known_gamut_map_ids())}. Defaut: "
        f"{DEFAULT_GAMUT_MAP}."
    )


def resolve_render_dpi(value: int | None) -> int:
    if value is None:
        return RENDER_DPI_DEFAULT
    resolved = _as_exact_int(value)
    if resolved is None or not RENDER_DPI_MIN <= resolved <= RENDER_DPI_MAX:
        raise ParameterVocabularyError(
            f"DPI de rendu invalide: '{value}'. Domaine accepte: entier de "
            f"{RENDER_DPI_MIN} (borne 4.3 des marqueurs) a {RENDER_DPI_MAX} "
            "(4x la consigne de scan, au-dela le raster QR devient "
            f"demesure); defaut et valeur recommandee {RENDER_DPI_DEFAULT} "
            "dpi. Le DPI de rendu rasterise les elements embarques dans le "
            f"PDF; la consigne de scan reste {qr_codes.QR_MIN_SCAN_DPI} dpi."
        )
    return resolved


# ---------------------------------------------------------------------------
# Lecture du contenu du lot depuis le manifest (AC 4)
# ---------------------------------------------------------------------------


def _find_entry(entries: Any, key: str, wanted: str) -> dict | None:
    for entry in entries or []:
        if isinstance(entry, Mapping) and entry.get(key) == wanted:
            return dict(entry)
    return None


def _require(value: Any, message: str) -> Any:
    if value is None:
        raise LotContentError(message)
    return value


def nombre_de_planches(frame_count: int, frames_per_page: int) -> int:
    """`ceil(frames / emplacements)`: **la** pagination d'un lot, une seule fois.

    **`page_count = ceil(frames / frames_par_page)`**, et rien de plus, **depuis la
    story 5.22** (`EPIC5-ARB-80`, decision 7): le lot ne porte plus de page de
    calibration inseree automatiquement, donc il n'y a plus de page imprimee a
    compter en dehors des planches d'images.

    Ce calcul est litteralement celui d'avant la story 5.16, et le retour n'est pas
    un revirement d'esthetique: la calibration devient **par chaine de scan** et non
    par lot, donc la page de calibration cesse d'appartenir a l'espace d'index d'un
    lot. Elle est generee **a la demande** par `compose_calibration_page_plan`, qui
    pose son propre `page_count = 1`.

    Ce que ce retrait ne change pas: un lot **imprime avant** cette story porte
    toujours sa page de calibration a l'index 0, son `page_count` la compte toujours,
    et le chemin de scan continue de la lire (`AC 10`). C'est la **composition** qui
    cesse de l'inserer, jamais la lecture qui cesse de l'accepter.

    **Pourquoi elle est publique depuis la story 11.4b.** Elle etait une expression
    posee au milieu de `compose_lot_plan`, donc illisible depuis le chemin de scan.
    Or `scan_corrections.modele_depuis_le_manifeste` doit deduire **exactement** le
    `page_count` que l'impression a pose, pour completer une planche muette dont le
    QR n'a rien rendu (`EPIC11-ARB-64`). La recopier la-bas en aurait fait une
    seconde redaction: elles coincideraient le jour de leur ecriture et divergeraient
    a la premiere evolution de la pagination, **sans qu'aucune etape n'echoue** --
    c'est la famille du finding 4.3, deja payee dans ce depot.

    `frames_per_page` vaut au moins 1: un gabarit a zero emplacement ne paginerait
    rien et la division par exces rendrait 0 planche pour n'importe quel nombre de
    frames, c'est-a-dire un lot qui s'imprime sur rien.
    """
    if not isinstance(frames_per_page, int) or isinstance(frames_per_page, bool):
        raise LotContentError(
            f"frames_per_page est un entier, recu {frames_per_page!r}.")
    if frames_per_page <= 0:
        raise LotContentError(
            f"frames_per_page vaut {frames_per_page}: une planche porte au moins "
            "un emplacement, sinon aucun nombre de frames ne se pagine.")
    if not isinstance(frame_count, int) or isinstance(frame_count, bool):
        raise LotContentError(
            f"frame_count est un entier, recu {frame_count!r}.")
    if frame_count < 0:
        raise LotContentError(
            f"frame_count vaut {frame_count}: un lot ne porte pas un nombre "
            "negatif de frames.")
    return (frame_count + frames_per_page - 1) // frames_per_page


def page_count_du_lot(
    manifest: Mapping[str, Any], lot_id: str, *, frames_per_page: int
) -> int:
    """Le `page_count` que ce lot **a fait imprimer**, relu depuis le manifeste.

    Meme chemin que l'impression, dans le meme ordre: la selection est
    **recalculee** depuis le manifeste (jamais un `glob`, jamais
    `expected_frame_count`), puis paginee par :func:`nombre_de_planches`. Lire un
    autre cardinal ici ferait deduire un `page_count` qui a l'air juste et qui
    n'est pas celui du QR imprime.

    Story 11.4b (`EPIC11-ARB-64`): c'est le seul champ des huit que le lot doit
    donner a une planche muette qui ne soit pas ecrit tel quel au manifeste. Il
    est **deduit**, et il l'est ici pour l'etre une seule fois.
    """
    lot = _find_entry(manifest.get("lots"), "lot_id", lot_id)
    if lot is None:
        known = ", ".join(
            str(entry.get("lot_id"))
            for entry in manifest.get("lots") or []
            if isinstance(entry, Mapping)
        ) or "(aucun)"
        raise LotContentError(
            f"Le lot '{lot_id}' n'existe pas dans le manifest. Lots "
            f"disponibles: {known}.")
    selection = _recompute_selection(manifest, lot)
    return nombre_de_planches(len(list(selection.frames)), frames_per_page)


def _recompute_selection(manifest: Mapping[str, Any], lot: Mapping[str, Any]):
    """Selection recalculee depuis le seul manifest, jamais un glob (AC 4).

    Delegue a `extraction_manifest.recompute_lot_selection` -- la meme
    implementation que le niveau 3 de `verify_extracted_lot`, repli v2.0
    compris -- pour qu'un lot declare conforme par la verification soit
    recalcule ici a l'identique (decision 2 du 2026-08-02: une seule
    implementation par convention; revue 4.1 du 2026-08-06).
    """
    selection, code = extraction_manifest.recompute_lot_selection(manifest, lot)
    if selection is not None:
        return selection
    if code == extraction_manifest.VERIFY_MANIFEST_INCOHERENT:
        raise LotContentError(
            "Manifest incoherent: le noyau de selection refuse les parametres "
            f"du lot '{lot.get('lot_id')}'. Verifier rushes[].fps_source_exact, "
            "lots[].fps_target_exact et lots[].source_frame_count."
        )
    raise LotContentError(
        f"Le manifest ne permet pas de recalculer la selection du lot "
        f"'{lot.get('lot_id')}' (constat {code}): il manque la cadence source "
        "du rush (rushes[].fps_source_exact), la cadence cible du lot "
        "(lots[].fps_target_exact) ou lots[].source_frame_count. makepdf "
        "n'imprime jamais depuis un simple listing de fichiers."
    )


# ---------------------------------------------------------------------------
# Typographie (story 4.2): modele de largeur, troncature marquee, affichages
# ---------------------------------------------------------------------------


def _require_body_font(font_pt: float) -> float:
    """Plancher typographique applique partout (AC 5/6 de 4.2, revue 4.2):
    une taille nulle divisait par zero, une taille negative rendait des
    capacites absurdes, et une taille sous le plancher violerait le contrat
    "jamais de reduction de police sous le minimum"."""
    if not isinstance(font_pt, (int, float)) or isinstance(font_pt, bool) or (
        font_pt < BODY_FONT_MIN_PT
    ):
        raise CompositionError(
            f"Taille de police invalide: {font_pt!r}. Plancher contractuel: "
            f"{BODY_FONT_MIN_PT:.0f} pt (AC 5/6 de la story 4.2), jamais de "
            "reduction en dessous."
        )
    return float(font_pt)


def text_width_mm(text: str, font_pt: float) -> float:
    """Largeur estimee d'une ligne au modele conservatif ``CHAR_WIDTH_EM``."""
    return len(text) * _require_body_font(font_pt) * CHAR_WIDTH_EM * 25.4 / 72.0


def line_leading_mm(font_pt: float) -> float:
    """Interligne du rendu pour ``font_pt`` (implementation unique, consommee
    par ``pdf_render`` -- revue 4.2: la formule vivait dans le rendu et la
    composition ne pouvait pas verifier la tenue verticale des blocs)."""
    return _require_body_font(font_pt) * 0.42 + 1.2


def _max_chars(width_mm: float, font_pt: float) -> int:
    char_width = _require_body_font(font_pt) * CHAR_WIDTH_EM * 25.4 / 72.0
    return max(0, int(width_mm / char_width + 1e-9))


def fit_text(value: str, width_mm: float, font_pt: float) -> str:
    """Ajuster ``value`` a la bande: verbatim si elle tient, sinon troncature
    avec marqueur visible et queue preservee (AC 6 de 4.2).

    La queue de ``_TRUNCATION_TAIL_CHARS`` caracteres est conservee parce que
    la fin d'un identifiant derive porte le suffixe de hachage discriminant
    (``io.naming.derive_short_id``). Jamais de reduction de police: la taille
    est celle de l'appelant, plancher ``BODY_FONT_MIN_PT`` (refus en deca).
    Le resultat tient TOUJOURS dans la bande (revue 4.2: la branche de repli
    forcait au moins 4 caracteres et debordait d'une bande plus etroite):
    sous ``len(TRUNCATION_MARKER) + 1`` caracteres de capacite, seule une
    partie du marqueur sort -- troncature visible, jamais un debordement.
    """
    capacity = _max_chars(width_mm, font_pt)
    if len(value) <= capacity:
        return value
    keep = capacity - len(TRUNCATION_MARKER) - _TRUNCATION_TAIL_CHARS
    if keep >= 1:
        return value[:keep] + TRUNCATION_MARKER + value[-_TRUNCATION_TAIL_CHARS:]
    if capacity > len(TRUNCATION_MARKER):
        return value[: capacity - len(TRUNCATION_MARKER)] + TRUNCATION_MARKER
    return TRUNCATION_MARKER[:capacity]


def format_fps_display(fps: float) -> str:
    """Forme humaine de la cadence pour l'impression (``12.5 im/s``).

    Conversion d'affichage (AC 3 de 4.2): la forme slug ``12p5`` reste
    reservee aux noms de fichiers (``io.naming.format_fps_short``), la donnee
    reste le nombre du manifest/payload.
    """
    return f"{float(fps):g} im/s"


def _require_verbatim(
    lines: list[str], rect: tuple[float, float, float, float], font_pt: float,
    what: str,
) -> None:
    """Refuser une ligne d'identite qui ne tient pas **verbatim** dans sa zone.

    AC 6 de la story 4.2: les identifiants canoniques s'impriment verbatim -- egalite a
    l'octet pres avec le payload QR et les noms de fichiers, c'est le mecanisme de
    secours 4.6 -- ou la combinaison est refusee. Jamais de troncature silencieuse, ni
    de police sous le plancher.

    Extrait en fonction par la story 5.18 parce que ces lignes vivent desormais dans
    **deux** blocs -- l'entete d'identite et le pied residuel -- et qu'une regle
    appliquee a l'un des deux seulement laisserait passer une troncature la ou elle
    casse l'egalite inter-canaux.
    """
    for line in lines:
        if text_width_mm(line, font_pt) > rect[2] + 1e-9:
            raise GeometryOverflowError(
                f"La ligne {what} '{line}' ne tient pas dans le bloc "
                f"({rect[2]:.0f} mm) a {font_pt:.0f} pt. Reduire le nombre de pages "
                "(--frames-par-page plus grand) ou raccourcir les identifiants du "
                "projet."
            )


def _pack_lines(parts: list[str], width_mm: float, font_pt: float, separator: str = " - ") -> tuple[str, ...]:
    """Regrouper des segments en lignes qui tiennent dans la bande (glouton,
    deterministe); un segment seul trop long est tronque avec marqueur."""
    lines: list[str] = []
    current = ""
    for part in parts:
        candidate = part if not current else current + separator + part
        if text_width_mm(candidate, font_pt) <= width_mm:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = fit_text(part, width_mm, font_pt)
    if current:
        lines.append(current)
    return tuple(lines)


# ---------------------------------------------------------------------------
# Le pied technique: dix renseignements, et de quoi les retaper (AC 6, 11.4b)
# ---------------------------------------------------------------------------

#: Premiere mention du pied technique: elle nomme **l'outil** qui a compose la
#: planche, pas un champ a retaper. C'est la seule mention qui ne soit pas un
#: couple ``cle=valeur``, avec la consigne de scan qui ferme la liste.
#:
#: **Elle passe de 27 a 11 caracteres, et ce n'est pas de la cosmetique**: c'est
#: la mention qui decide si les dix renseignements sont robustes ou tenus a la
#: rangee pres. Mesure dans la colonne bornante (55,188 mm a 8 pt), sur la
#: configuration la plus chargee du depot:
#:
#: * sous ``"Mixed Media Utility makepdf"``, le pied rend **7** lignes pour 7 de
#:   capacite -- il tient, avec **zero** jeu --, et un `target_colorspace` de
#:   **12** caracteres (``rec2020-2020``, ``bt2100-hlg2``...) le fait deborder,
#:   donc REFUSER la composition. Or cette valeur vient de `project.json`: elle
#:   n'est bornee par aucun registre;
#: * sous ``"MMU makepdf"``, il rend **6** lignes et ne deborde pour aucune
#:   longueur d'espace cible, jusqu'a 39 caracteres au moins -- bien au-dela de
#:   la longueur ou la mention cesse de tenir verbatim dans sa colonne, donc de
#:   celle ou le constat :data:`PIED_TECHNIQUE_TRONQUE` se pose.
#:
#: Raccourcir la provenance est donc ce qui achete la marge, et c'est le seul
#: endroit ou la prendre: les huit autres mentions sont des valeurs de contrat.
PIED_PROVENANCE = "MMU makepdf"

#: La provenance **gelee** avec la geometrie v1, pour la meme raison que
#: :data:`PIED_CLES_V1`: le document de reference du `baseline_commit` la porte
#: mot pour mot.
PIED_PROVENANCE_V1 = "Mixed Media Utility makepdf"

#: Les huit renseignements ``cle=valeur`` du pied technique, **dans l'ordre
#: imprime** (`EPIC11-ARB-87`, arbitrage d'Egan du 2026-08-30: « Le pied de page
#: est purement technique. Pas oblige d'avoir une mise en page elegante. [...] le
#: but etant qu'une pile totalement denuee de QR puisse etre decodee avec entree
#: manuelle »).
#:
#: **Pourquoi des cles courtes, et ce que la mesure a vraiment dit.** La mesure
#: du lot S4 (`EPIC11-ARB-84`) avait conclu que les dix renseignements NE
#: TIENNENT PAS: 12 configurations sur 24 debordaient. Cette mesure portait sur
#: les cles **longues** (``timecode_base_fps=``, ``target_colorspace=``...), qui
#: rendent 9 lignes dans la colonne bornante de 55,188 mm. Les memes dix
#: renseignements sous des cles courtes en rendent **6** -- exactement ce que les
#: **six** mentions d'avant occupaient. Ce n'est donc pas la mise sur deux lignes
#: qui debloque l'AC 6, c'est le raccourcissement des cles, et aucune zone de
#: dessin n'est touchee.
#:
#: **Les quatre derniers ferment les huit champs neutres du lot.** Le pied en
#: portait deja quatre (`project_id` et `rush_id` au bloc d'identite,
#: `fps_target` a l'entete, `patch_preset_id` ici); les quatre ajoutes sont
#: exactement le complement de :data:`scan_corrections.CHAMPS_NEUTRES_DU_LOT`,
#: c'est-a-dire ce qu'une operatrice ne peut PAS lire ailleurs sur le papier.
#: C'est le sens litteral de « decodee avec entree manuelle ».
PIED_CHAMPS: tuple[str, ...] = (
    "aruco_dictionary",
    "template_id",
    "patch_preset_id",
    "schema_version",
    "timecode_base_fps",
    "target_colorspace",
    "gamut_map_id",
    "page_count",
)

#: La seule cle du pied qui ne se lise **pas** dans
#: :data:`io.payload.PAYLOAD_SHORT_KEYS`: le dictionnaire ArUco n'est pas un
#: champ de charge utile. Il est imprime pour qu'on sache quel detecteur monter,
#: pas pour etre retape dans un formulaire de completion.
PIED_CLE_HORS_PAYLOAD: Mapping[str, str] = MappingProxyType({
    "aruco_dictionary": "dict",
})

#: Les cles **imprimees**, derivees et jamais reecrites.
#:
#: **Sept des huit se lisent dans `PAYLOAD_SHORT_KEYS`, et c'est le geste qui
#: compte ici.** Le depot avait deja, depuis la story 5.17, un vocabulaire court
#: pour exactement ces champs -- celui que le QR emploie. En ecrire un second
#: pour le papier aurait fait porter a la **meme feuille** deux noms courts pour
#: le meme champ (`tcb=` au pied, `tbf` dans le QR), c'est-a-dire une seconde
#: redaction du meme vocabulaire, famille du finding 4.3. La frontiere
#: `test_the_table_is_the_only_place_where_a_short_key_is_written` l'a d'ailleurs
#: refuse en clair: `tcs` etait deja pris, et son motif est le bon -- « deux
#: tables qui divergent produiraient un QR ecrit dans une forme et relu dans une
#: autre ».
#:
#: Le pied existe pour retaper **ce que le QR aurait porte**. Qu'il le nomme
#: comme le QR le nomme n'est donc pas une economie de code, c'est ce qui
#: dispense l'operatrice d'une table de correspondance.
PIED_CLES_COURTES: Mapping[str, str] = MappingProxyType({
    champ: PIED_CLE_HORS_PAYLOAD.get(champ)
           or payload_io.PAYLOAD_SHORT_KEYS[champ]
    for champ in PIED_CHAMPS
})

#: Les cles **historiques**, gelees avec la geometrie v1 -- quatre mentions, pas
#: huit. Elles ne sont pas une variante de style: la v1 est une geometrie
#: **figee**, et `test_a_v1_lot_is_byte_for_byte_what_it_was_before_the_story`
#: compare un lot v1 a un document produit sur l'arbre du `baseline_commit`. Y
#: appliquer le pied neuf ferait bouger des planches deja imprimees, ce que
#: l'AC 6.4 refuse explicitement (« cela ne vaut que pour les planches imprimees
#: **apres** ce changement »).
#:
#: Elles sont ecrites en toutes lettres parce qu'elles sont **gelees**: les
#: deriver d'une table vivante ferait bouger un jour ce qui ne doit plus bouger.
PIED_CLES_V1: Mapping[str, str] = MappingProxyType({
    "aruco_dictionary": "dict",
    "template_id": "template",
    "patch_preset_id": "patchs",
    "schema_version": "schema-payload",
})

#: Les quatre renseignements qu'`EPIC11-ARB-65` ajoute. Ils se **deduisent** de
#: l'ecart entre les deux tables plutot que d'etre reecrits: une cinquieme
#: mention ajoutee a :data:`PIED_CLES_COURTES` entre ici toute seule, et une
#: mention qui reviendrait au pied gele en sortirait toute seule.
PIED_CHAMPS_AJOUTES: tuple[str, ...] = tuple(
    nom for nom in PIED_CHAMPS if nom not in PIED_CLES_V1
)


def pied_technique_parts(
    *, geometry_version: str, valeurs: Mapping[str, Any],
) -> list[str]:
    """Les mentions du pied technique, dans l'ordre imprime.

    **Une seule redaction du pied**, pour les deux geometries: la table des cles
    change, jamais la source des valeurs. Ecrire la liste deux fois -- une v1,
    une v2 -- en aurait fait deux redactions qui coincideraient le jour de leur
    ecriture et divergeraient a la premiere evolution d'un champ, sans qu'aucune
    etape n'echoue: c'est la famille du finding 4.3, deja payee ici.

    Chaque valeur est **passee** par l'appelant, qui la tient de son contrat
    (`_lot_identity` pour la base de timecode et l'espace cible, le registre des
    gamuts pour la G, :func:`nombre_de_planches` pour le cardinal de planches).
    Aucune n'est ecrite ici: un litteral local reimprimerait la valeur d'hier sur
    la planche d'aujourd'hui, et rien ne le dirait (AC 6.1).

    Un champ absent de ``valeurs`` est **refuse nommement** plutot qu'imprime
    vide: une planche qui porterait ``tcs=`` sans espace cible est precisement la
    planche qu'une saisie manuelle ne peut pas completer.
    """
    gele = geometry_version == page_templates.GEOMETRY_V1.version
    cles = PIED_CLES_V1 if gele else PIED_CLES_COURTES
    manquants = [nom for nom in cles if valeurs.get(nom) in (None, "")]
    if manquants:
        raise LotContentError(
            "Pied technique: les renseignements "
            f"{', '.join(sorted(manquants))} sont absents ou vides. Le pied "
            "existe pour qu'une planche muette soit retapee a la main "
            "(EPIC11-ARB-65): une mention vide y est un faux succes."
        )
    parts = [PIED_PROVENANCE_V1 if gele else PIED_PROVENANCE]
    # L'ordre imprime est celui de `PIED_CLES_COURTES`, y compris pour le pied
    # gele -- qui n'en garde que quatre mentions. Deux ordres differents feraient
    # deux pieds a relire au lieu d'un.
    parts.extend(f"{cles[nom]}={valeurs[nom]}"
                 for nom in PIED_CHAMPS if nom in cles)
    parts.append(f"scan {qr_codes.QR_MIN_SCAN_DPI} dpi")
    return parts


#: Constat porte au plan quand une mention du pied technique ne tient pas
#: verbatim dans sa bande. Meme forme que `GEOMETRIE_QR_DEGRADEE`: un constat
#: **nomme**, remonte au plan, jamais un ajustement muet.
PIED_TECHNIQUE_TRONQUE = "PIED_TECHNIQUE_TRONQUE"


def mentions_tronquees(
    parts: list[str], width_mm: float, font_pt: float,
) -> tuple[str, ...]:
    """Les mentions ``cle=valeur`` que la bande ne peut pas porter **verbatim**.

    `_pack_lines` tronque avec marqueur visible un segment plus large que la
    bande. C'est le bon geste pour de la prose et c'est un demi-geste pour un
    ``cle=valeur`` que quelqu'un doit retaper: ``tcs=rec7...`` se lit, ne se
    saisit pas. L'AC 6.2 dit ce qu'il faut en faire, et le mot qui compte est
    *muette*: « l'ecart est **remonte** plutot que resolu par une troncature
    **muette** ». Cette fonction rend l'ecart; l'appelant le remonte au plan.

    **Ce n'est deliberement PAS un refus**, et le motif est mesure: le depot
    accepte aujourd'hui un `target_colorspace` de 40 caracteres
    (`test_over_nominal_budget_prints_with_structured_warning`), qu'aucune borne
    de contrat n'interdit puisqu'il vient de `project.json`. Refuser la
    composition sur une mention de pied ferait refuser des lots qui s'impriment
    aujourd'hui, pour un champ que le QR porte **toujours en entier**. Le pied
    est un secours, pas le canal principal: son ecart se signale.

    **Et rien ici ne touche une zone de dessin**: aucune police n'est reduite,
    aucune zone n'est retrecie, aucun repli geometrique n'est tente. Les zones du
    pied sont fixees par le gabarit, et la geometrie deduite des marqueurs en
    depend -- c'est l'assurance donnee a Egan, et elle se mesure.

    La provenance et la consigne de scan en sont exclues: ce sont les deux
    mentions qui ne sont pas des couples ``cle=valeur``, donc de la prose dont
    aucune saisie ne depend.
    """
    return tuple(
        part for part in parts
        if "=" in part and text_width_mm(part, font_pt) > width_mm + 1e-9
    )


# ---------------------------------------------------------------------------
# Geometrie QR et texte par page
# ---------------------------------------------------------------------------


def _qr_band_mm(spec: page_templates.TemplateSpec) -> tuple[float, float, float, float]:
    """Bande du QR **sur le bord que le gabarit lui a retenu**.

    Les bornes se lisent dans `spec.geometry` et non dans les constantes du module:
    la bande est bornee par le silence des marqueurs de coin, donc une version
    de geometrie aux marqueurs resserres l'ouvre plus large. La lire ailleurs
    ferait composer une page `v2` avec la bande de `v1` -- silencieusement, et le
    refus d'emprise du QR ci-dessous porterait sur la mauvaise largeur.

    Depuis la story 5.18 le bord porteur est **calcule** par gabarit et porte par le
    spec: cette fonction n'est plus « la bande haute », c'est « la bande du QR ».
    """
    return page_templates.qr_band_mm(spec)


def _qr_footprint_rect(
    spec: page_templates.TemplateSpec, plan: page_payload.PagePayloadPlan
) -> tuple[float, float, float, float]:
    """Emprise physique du QR (symbole + silence ISO), centree dans **sa** bande;
    refus explicite si elle deborde (jamais un retrecissement).

    L'abscisse du centre depend du bord porteur, et ce n'est pas de la cosmetique:

    * au bord **haut** l'emprise est centree sur la page, comme depuis la story 4.1 --
      c'est ce qui garde une planche v1 identique au dixieme de millimetre;
    * au bord **bas** elle est **collee a droite** de la bande, parce que le pied de
      page occupe le meme espace et doit se poser a cote d'elle. Centrer le QR y
      couperait le pied en deux colonnes de 55 mm, ou un identifiant canonique de
      48 caracteres ne tient pas au plancher de 8 pt;
    * sur un **flanc** la bande est deja le carre de l'emprise reservee, donc le
      centrage y est exact dans les deux dimensions.
    """
    module_side = plan.module_side
    footprint_side = plan.print_size_mm * (
        module_side + 2 * qr_codes.QUIET_ZONE_MODULES
    ) / module_side
    band_x, band_y, band_w, band_h = _qr_band_mm(spec)
    reserved_x, _y, reserved_w, _h = page_templates.qr_reserved_zone_mm(spec)
    center_x = reserved_x + reserved_w / 2.0
    center_y = band_y + band_h / 2.0
    rect = (
        center_x - footprint_side / 2.0,
        center_y - footprint_side / 2.0,
        footprint_side,
        footprint_side,
    )
    if (
        rect[0] < band_x - 1e-9
        or rect[1] < band_y - 1e-9
        or rect[0] + rect[2] > band_x + band_w + 1e-9
        or rect[1] + rect[3] > band_y + band_h + 1e-9
    ):
        raise GeometryOverflowError(
            f"L'emprise du QR ({footprint_side:.1f} mm silence compris, payload "
            f"de {plan.budget.size_bytes} octets) deborde la bande haute du "
            f"template ({band_w:.0f} x {band_h:.0f} mm). Reduire "
            "--frames-par-page pour alleger le payload de page."
        )
    return rect


def _footer_zones_mm(
    spec: page_templates.TemplateSpec,
) -> dict[str, tuple[float, float, float, float]]:
    """Zones du pied de page: **derivees de `spec.geometry`** (story 5.15, AC 4).

    La derivation vit dans `page_templates` -- c'est une propriete de la geometrie de
    page, et `patch_presets` en a besoin pour ses zones reservees sans pouvoir importer
    ce module. Ce delegue reste le point d'appel de la composition.
    """
    return page_templates.footer_zones_mm(spec)


def _header_zones_mm(
    spec: page_templates.TemplateSpec, qr_rect: tuple[float, float, float, float]
) -> dict[str, tuple[float, float, float, float]]:
    """Zones de texte d'en-tete, recalculees autour de l'emprise reelle du QR
    (un QR agrandi hors budget nominal reduit les en-tetes, jamais l'inverse).

    L'ordonnee et la hauteur sont derivees de la bande haute avec un retrait
    (`_TEXT_HEADER_INSET_MM`) et non plus ecrites en litteral: sous la v2 la bande
    haute ne fait plus 50 mm mais 38,8 mm, et un en-tete de 40 mm pose a y = 10
    descendrait dans la bande de frames.

    **Deux dispositions, et le retrait n'appartient qu'a la premiere** (story 5.18).
    Le retrait de 5 mm reproduit les deux litteraux de la v1 (y = 10, hauteur = 40) et
    n'a pas d'autre raison d'etre; l'appliquer a l'entete d'identite mangerait 10 des
    18 mm de bande haute que la v2 laisse quand son QR est ailleurs, et ferait donc
    refuser un entete de deux lignes a 14 pt qui, lui, tient. L'entete d'identite prend
    donc la bande **telle quelle**: elle est deja retiree de la marge d'encre en haut et
    de la garde de bande en bas.
    """
    band_x, band_y, band_w, band_h = page_templates.header_band_mm(spec)
    if spec.geometry.identity_in_header:
        zones: dict[str, tuple[float, float, float, float]] = {}
        if band_h <= 0:
            return zones
        width = band_w
        if spec.qr_edge == page_templates.QR_EDGE_TOP:
            # Le QR partage la bande haute: l'entete se pose a sa gauche, jamais
            # par-dessus. Les deux moities sont egales (emprise centree), donc en
            # choisir une est un choix de lisibilite, pas de place.
            width = qr_rect[0] - _TEXT_GAP_MM - band_x
        if width <= 0:
            return zones
        zones["header_identity"] = (band_x, band_y, width, band_h)
        return zones
    header_y = band_y + _TEXT_HEADER_INSET_MM
    header_height = band_h - 2 * _TEXT_HEADER_INSET_MM
    zones: dict[str, tuple[float, float, float, float]] = {}
    if header_height <= 0:
        return zones
    left_width = qr_rect[0] - _TEXT_GAP_MM - band_x
    if left_width > 0:
        zones["header_left"] = (band_x, header_y, left_width, header_height)
    right_x = qr_rect[0] + qr_rect[2] + _TEXT_GAP_MM
    right_width = band_x + band_w - right_x
    if right_width > 0:
        zones["header_right"] = (right_x, header_y, right_width, header_height)
    return zones


#: `date_line_slot` d'une page qui ne porte **pas** de ligne de date (story 5.16).
#:
#: Le rendu insere la date dans le bloc que le **plan** nomme (`EPIC4-ARB-8`); un nom
#: qu'aucun bloc ne porte veut donc dire « pas de date sur cette page ». C'est le cas de
#: la page de calibration, et c'est **mesure et non un oubli**: son entete d'identite
#: dispose d'une bande de 12 mm (une rangee de grille), ou deux lignes a 8 pt en
#: consomment 9,12. Une troisieme ligne en exigerait 13,68, donc une seconde rangee de
#: grille -- qui coute 16 cellules en paysage et ferait tomber la capacite du treillis a
#: 119 quand il en demande 130.
#:
#: Ce que la page perd et ne perd pas: elle n'imprime ni la date de rendu, ni le pied
#: technique, ni la consigne de scan. Elle imprime son `lot_id`, sa pagination, sa
#: cadence -- les deux lignes qu'un operateur lit sur une pile -- et son QR, qui porte
#: l'integralite de ce que la relecture demande, version de schema comprise.
NO_DATE_LINE_SLOT: tuple[str, int] = ("", -1)


#: Les mentions **fixes** de la page de calibration, verbatim (story 5.23, correction
#: d'Egan du 2026-08-18). Elles sont ici et nulle part ailleurs: une phrase recopiee
#: dans un test ou dans l'aide de la CLI serait une seconde redaction, et c'est
#: exactement le genre de texte qui derive sans que rien ne le dise.
CALIBRATION_SHEET_MENTION = "Page de calibration"
CALIBRATION_USAGE_MENTION = (
    "\u00c0 g\u00e9n\u00e9rer une fois et \u00e0 scanner pour toute cha\u00eene "
    "de scan existante : scanner, format, r\u00e9glages, r\u00e9solution."
)

#: Prefixes des deux mentions variables. Ils sont **imprimes** parce que la feuille se
#: lit seule: « hp envy 4520 tiff 600 dpi auto corr off » pose nu sur une page ne dit
#: pas ce qu'il designe, et cette feuille est justement celle qu'un operateur retrouve
#: des mois plus tard dans une pile.
CALIBRATION_CHAIN_PREFIX = "Cha\u00eene de scan : "
CALIBRATION_COMMENT_PREFIX = "Commentaire : "

#: Prefixe de la date de generation, **imprimee et rien d'autre** (Egan, 2026-08-18):
#: « une feuille de calibration se retrouve dans une pile six mois plus tard: sans
#: date, on ne sait pas laquelle est la plus recente ».
#:
#: Elle n'entre **ni dans le QR, ni dans le condensat du nom de fichier**, et ce n'est
#: pas une precaution de style: `io.naming` interdit l'horodate dans tout ce qui est
#: condense ou compare, parce que deux generations de la **meme** page produiraient
#: alors deux identites. La feuille reimprimee cesserait d'etre la meme feuille --
#: pour le nom de fichier comme pour le `chain_id` -- et le determinisme que tout le
#: dispositif de reconstruction suppose tomberait. Une frontiere negative l'epingle.
CALIBRATION_DATE_PREFIX = "G\u00e9n\u00e9r\u00e9e le "

#: Separateur entre deux mentions sur une meme ligne. Le meme que `_pack_lines`, et
#: c'est voulu: deux separateurs differents sur la meme feuille se lisent comme deux
#: niveaux de structure alors qu'il n'y en a qu'un.
_HEADER_SEGMENT_SEPARATOR = " - "

#: Longueur maximale du commentaire libre, en caracteres.
#:
#: Il ne va **pas** dans le QR (correction d'Egan du 2026-08-18: c'est de la prose pour
#: le lecteur humain de la feuille), donc il ne coute rien en octets -- sa seule borne
#: est la place imprimee, et il la partage avec le libelle de chaine: c'est le
#: **couple** qui est confronte aux 5 lignes que le portrait finance, jamais l'un des
#: deux seul. Voir `io.payload.SCAN_CHAIN_LABEL_MAX_LENGTH` pour la derivation
#: complete; le couple retenu est (96, 72), et un test montre que (104, 72) et
#: (96, 80) debordent tous les deux.
#:
#: **Le commentaire reste dans l'entete, il n'est pas descendu en pied de page**, et
#: c'est contraire a ce qu'Egan proposait (« il peut etre en bas de page si besoin pour
#: la place ! »). Le releve dit que le pied couterait de la place au lieu d'en rendre:
#: la grille finance 21 cellules de mobilier, soit 2 rangees en portrait, et deux
#: rangees **contigues** portent 5 lignes quand une rangee d'entete plus une rangee de
#: pied n'en portent que 4 -- chaque bande perd l'espacement inter-pastilles a son
#: bord. Le detail du calcul est dans `_calibration_header_lines`.
SCAN_CHAIN_COMMENT_MAX_LENGTH = 72


def _validate_calibration_comment(comment: str | None) -> str | None:
    """Valider le commentaire libre de la page, ou lever.

    Il est **facultatif** et il n'entre nulle part dans le QR (correction d'Egan du
    2026-08-18): c'est de la prose destinee au lecteur humain de la feuille. Sa seule
    borne est donc la place imprimee, et elle est mesuree avec celle du libelle -- voir
    :data:`SCAN_CHAIN_COMMENT_MAX_LENGTH`.

    Un commentaire vide ou blanc est rendu `None` et non conserve: une mention
    « Commentaire : » suivie de rien consommerait une ligne d'entete -- donc,
    indirectement, des cellules du treillis -- pour n'imprimer aucune information.
    """
    if comment is None:
        return None
    if not isinstance(comment, str):
        raise ParameterVocabularyError(
            f"Commentaire de page de calibration invalide: {comment!r}. Attendu: une "
            "chaine de caracteres."
        )
    comment = comment.strip()
    if not comment:
        return None
    if len(comment) > SCAN_CHAIN_COMMENT_MAX_LENGTH:
        raise ParameterVocabularyError(
            f"Commentaire de page de calibration de {len(comment)} caracteres, pour un "
            f"maximum de {SCAN_CHAIN_COMMENT_MAX_LENGTH}. Il s'imprime **verbatim** "
            "dans la bande d'entete, dont chaque rangee se paie en cellules reprises "
            "au treillis: au-dela, la seule autre issue serait de le tronquer, et une "
            "mention tronquee sur une feuille imprimee est indetectable apres coup."
        )
    return comment


def _wrap_verbatim(segments: list[str], width_mm: float, font_pt: float) -> list[str]:
    """Repartir ``segments`` en lignes qui tiennent, **sans jamais tronquer**.

    Trois proprietes, et chacune a coute une redaction ratee avant d'etre ecrite.

    **1. Aucune troncature.** `_pack_lines` tronque un segment trop long avec un
    marqueur. C'est le bon geste pour un pied technique, ou l'information tronquee
    existe ailleurs (le QR la porte). Ce n'est pas le bon geste ici: le **commentaire
    libre** de la page n'existe nulle part ailleurs -- ni dans le QR, ni dans un
    manifest --, donc une troncature l'effacerait definitivement, et sur une feuille
    imprimee c'est indetectable apres coup. Un segment plus long que la bande est donc
    **replie** mot a mot, et un mot plus long que la bande est **coupe** et continue a
    la ligne suivante: un libelle saisi sans aucune espace reste imprime en entier.

    **2. Une mention qui tient dans une ligne n'est jamais coupee.** Chaque segment est
    d'abord considere comme un **bloc insecable**; il n'est eclate en mots que s'il est
    a lui seul plus long que la bande. Sur un flot de mots -- la premiere redaction --
    l'entete imprimait « ... - Page de » puis « calibration - A generer ... »: la
    mention centrale de la feuille coupee par une fin de ligne. Exacte au caractere,
    illisible a l'usage, et c'est ce qu'un imprime ne pardonne pas.

    **3. Les blocs se groupent quand meme.** Un repli qui ouvrirait une ligne par
    segment serait lisible mais couteux: le pire cas passait de 5 a 6 lignes, donc
    d'une bande d'entete que le portrait finance a une qu'il ne finance pas. Les blocs
    sont donc empiles gloutonnement, separes par `_HEADER_SEGMENT_SEPARATOR`, et les
    mots d'un segment eclate continuent de s'empiler sur la meme ligne que le bloc qui
    precede.

    C'est la conjonction de 2 et 3 qui borne les longueurs maximales du libelle et du
    commentaire: elles sont choisies pour que leurs blocs restent **plus courts que la
    bande**, donc insecables (voir `io.payload.SCAN_CHAIN_LABEL_MAX_LENGTH`).
    """
    capacity = _max_chars(width_mm, font_pt)
    if capacity < 1:
        raise GeometryOverflowError(
            f"Bande d'entete de {width_mm:.1f} mm inexploitable a {font_pt:.0f} pt: "
            "aucun caractere n'y tient."
        )
    # Un segment qui tient dans la bande est un **jeton insecable**; sinon il entre
    # dans le flot par ses mots. C'est la seule decision de cette fonction: tout le
    # reste est un empilement glouton.
    #
    # Chaque jeton porte le liant qui le precede: `_HEADER_SEGMENT_SEPARATOR` quand il
    # ouvre une mention, une simple espace quand il continue une mention eclatee. Le
    # liant est porte par le jeton et non decide a l'empilement, sinon la distinction
    # « nouvelle mention / suite de mention » se reconstruirait par une comparaison de
    # chaines, c'est-a-dire par une devinette.
    tokens: list[tuple[str, str]] = []
    for segment in segments:
        if len(segment) <= capacity:
            tokens.append((_HEADER_SEGMENT_SEPARATOR, segment))
            continue
        for position, word in enumerate(segment.split(" ")):
            tokens.append((_HEADER_SEGMENT_SEPARATOR if position == 0 else " ", word))
    lines: list[str] = []
    current = ""
    for joiner, token in tokens:
        while len(token) > capacity:
            if current:
                lines.append(current)
                current = ""
            lines.append(token[:capacity])
            token = token[capacity:]
            joiner = ""
        if not current:
            current = token
            continue
        candidate = f"{current}{joiner}{token}"
        if len(candidate) <= capacity:
            current = candidate
        else:
            lines.append(current)
            current = token
    if current:
        lines.append(current)
    return lines


def _calibration_header_lines(
    *,
    orientation: str,
    project_id: str,
    scan_chain_label: str,
    comment: str | None,
    generated_on: date,
    width_mm: float,
    font_pt: float,
) -> list[str]:
    """Les mentions de la page de calibration, reparties en lignes.

    Ordre d'Egan (2026-08-18), et il n'est pas indifferent: le **projet**, la **chaine
    de scan**, la mention « page de calibration », la consigne d'usage, la **date de
    generation**, puis le commentaire libre s'il est fourni.

    **Tout tient dans l'entete, y compris le commentaire, et c'est une mesure et non un
    gout.** Egan a propose de descendre le commentaire en pied de page « si besoin pour
    la place »; le releve dit que ce serait en perdre. La grille ne finance que **21
    cellules** de mobilier hors treillis et hors QR, soit **2 rangees** en portrait et
    **1** en paysage -- et deux rangees *contigues* portent plus de texte que deux
    rangees separees, chaque bande perdant l'espacement inter-pastilles a son bord:

        entete 2 rangees + aucun pied  ->  27 mm  ->  **5 lignes**
        entete 1 rangee  + pied 1      ->  12 + 12 mm  ->  2 + 2 = **4 lignes**

    Un pied de page coute donc une ligne au lieu d'en rendre une. La contrainte
    qu'Egan voulait lever est reelle, mais le levier propose la resserre.

    Ce qui n'y figure plus, et c'est le fond de la correction: le `lot_id`, le rush, la
    pagination « page 1/1 » et la cadence. Les trois derniers etaient **faux au sens
    propre** sur cette feuille -- elle sert toute une chaine de scan, elle n'a qu'une
    page, et elle ne porte aucune frame donc aucune cadence. Le QR avait deja ete
    epure (AC 8bis); c'est l'imprime qui l'est ici.

    Le refus quand le texte deborde le budget de l'orientation est **chiffre** et il
    nomme les deux issues reelles. Il n'y a pas de troisieme issue: rogner la police
    sous son plancher est interdit par le contrat 4.2, et tronquer une mention sur une
    feuille imprimee est indetectable apres coup.
    """
    segments = [project_id, f"{CALIBRATION_CHAIN_PREFIX}{scan_chain_label}",
                CALIBRATION_SHEET_MENTION, CALIBRATION_USAGE_MENTION,
                f"{CALIBRATION_DATE_PREFIX}{generated_on.isoformat()}"]
    if comment:
        segments.append(f"{CALIBRATION_COMMENT_PREFIX}{comment}")
    lines = _wrap_verbatim(segments, width_mm, font_pt)
    budget = page_templates.calibration_header_line_count(orientation)
    if len(lines) > budget:
        raise GeometryOverflowError(
            f"Les mentions de la page de calibration exigent {len(lines)} lignes de "
            f"{_max_chars(width_mm, font_pt)} caracteres a {font_pt:.0f} pt, pour les "
            f"{budget} que la bande d'entete peut financer en {orientation}. Une "
            "rangee d'entete de plus se paie en cellules reprises au treillis, qui en "
            "exige deja "
            f"{patch_presets.calibration_lattice_patch_count()}. Deux issues, et "
            "aucune n'est une troncature: raccourcir le libelle de chaine ou le "
            "commentaire, ou composer en "
            f"{page_templates.ORIENTATION_PORTRAIT}, qui finance "
            f"{page_templates.calibration_header_line_count(page_templates.ORIENTATION_PORTRAIT)} "
            "lignes."
        )
    return lines


def _calibration_qr_rect(
    spec: page_templates.TemplateSpec,
    grid: page_templates.CalibrationGrid,
    plan: page_payload.PagePayloadPlan,
) -> tuple[float, float, float, float]:
    """Emprise physique du QR d'une page de calibration, centree dans **son bloc**.

    Le bloc est celui que la grille reserve -- `qr_cells` cellules de cote, sous
    l'entete, au bord gauche -- et il est dimensionne sur l'emprise **majorante** du
    symbole. Centrer l'emprise reelle dedans est donc toujours possible; le refus
    ci-dessous n'est pas decoratif pour autant, c'est ce qui fait que le jour ou la
    borne majorante bougerait sans que la grille suive, la page serait refusee au lieu
    d'imprimer un symbole par-dessus la premiere pastille du treillis.

    **Le refus mord desormais sur ce qu'il annonce** (bloquant B3 de la revue de 5.16). Il
    ne comparait l'emprise qu'au **bloc** -- 42,0 mm apres le `ceil` de la grille -- alors
    que son message parle du **majorant** qui a dimensionne ce bloc: il aurait fallu
    descendre a 38 modules pour le declencher, et le jour nomme par ce docstring est arrive
    sans qu'il dise un mot. L'emprise reelle atteignait 39,912 mm pour un majorant annonce a
    39,624, sur 30 des 90 configurations livrees, et le `ceil` du bloc absorbait l'ecart: la
    marge etait **accidentelle** et non demontree, ce qui est exactement ce que cette
    constante existe pour eviter.

    Les deux comparaisons sont donc faites, dans cet ordre: le majorant d'abord, parce que
    c'est lui qui est cense borner, puis le bloc, qui est la consequence physique. Un
    depassement du majorant **sans** depassement du bloc est precisement l'etat que cette
    story a produit -- silencieux, et faux.
    """
    module_side = plan.module_side
    footprint_side = plan.print_size_mm * (
        module_side + 2 * qr_codes.QUIET_ZONE_MODULES
    ) / module_side
    bound = page_templates.calibration_qr_footprint_bound_mm()
    block_x, block_y, block_w, block_h = grid.qr_zone_mm()
    if footprint_side > bound + 1e-9:
        raise GeometryOverflowError(
            f"L'emprise du QR de la page de calibration ({footprint_side:.3f} mm "
            f"silence compris, {module_side} modules, payload de "
            f"{plan.budget.size_bytes} octets) depasse le majorant de {bound:.3f} mm sur "
            f"lequel la grille du treillis dimensionne son bloc de QR, sur "
            f"'{spec.template_id}'. Le bloc peut encore l'absorber -- il vaut "
            f"{block_w:.1f} mm apres arrondi a la cellule -- mais cette marge serait un "
            "effet de l'arrondi et non une garantie: le majorant a bouge sans que le "
            f"domaine de modules suive. Domaine declare: plancher "
            f"{page_templates.QR_CALIBRATION_MIN_MODULE_SIDE} modules pour cette page, "
            f"{page_templates.QR_MIN_MODULE_SIDE} pour une planche d'images."
        )
    rect = (
        block_x + (block_w - footprint_side) / 2.0,
        block_y + (block_h - footprint_side) / 2.0,
        footprint_side,
        footprint_side,
    )
    if rect[0] < block_x - 1e-9 or rect[1] < block_y - 1e-9:
        raise GeometryOverflowError(
            f"L'emprise du QR de la page de calibration ({footprint_side:.1f} mm "
            f"silence compris, payload de {plan.budget.size_bytes} octets) deborde le "
            f"bloc de {block_w:.1f} mm que la grille du treillis lui reserve sur "
            f"'{spec.template_id}'. Ce bloc est dimensionne sur l'emprise majorante du "
            f"symbole ({bound:.3f} mm): un debordement veut dire que cette borne a bouge "
            "sans que la grille suive."
        )
    return rect


def _calibration_page_plan(
    *,
    spec: page_templates.TemplateSpec,
    project_id: str,
    scan_chain_label: str,
    comment: str | None,
    generated_on: date,
    patch_preset_id: str,
    target_colorspace: str,
    gamut_map_id: str,
    render_dpi: int,
    markers: tuple[MarkerPlan, ...],
) -> tuple[PagePlan, tuple[str, ...]]:
    """Plan de la **page de calibration** du lot: `page_index = 0`, aucune frame.

    Elle est composee ici et non par la boucle des planches d'images parce qu'elle n'a
    en commun avec elles que ses quatre marqueurs de coin: pas de zone de dessin, pas
    d'emplacement, pas de pied de page, une grille de pastilles de 12 mm au lieu d'une
    colonne de 6, et un QR pose dans cette grille au lieu d'une bande de page. La
    factoriser aurait demande une boucle a deux regimes, ce qui est la forme ou une
    permutation de role passe inapercue.

    Ce qu'elle partage en revanche, et ce n'est pas negociable: les **trois identifiants
    de niveau lot**. `template_id`, `patch_preset_id` et `page_count` sont ceux des
    planches d'images, faute de quoi l'invariant d'identite de lot la refuserait a la
    reconstruction -- et le `patch_preset_id` qu'elle declare n'est **pas** celui de ses
    propres pastilles, qui se derivent de son role.
    """
    template_id = spec.template_id
    grid = spec.geometry.calibration_grid(
        spec.orientation, patch_presets.CALIBRATION_PATCH_SIZE_MM)
    # **Deux jeux sur cette page depuis la story 5.23** (`EPIC5-ARB-82`, AC 1): son
    # treillis, sur lequel la correction s'ajuste, et le **bandeau de temoins** du
    # lot, porte par le mecanisme de bordure existant -- exactement le meme preset,
    # aux memes colonnes laterales, que sur une planche d'images. C'est ce qui rend la
    # divergence mesurable brute a brute: sans lui les deux feuilles n'ont aucun
    # identifiant de valeur en commun.
    #
    # L'ordre de concatenation n'est pas indifferent: le treillis d'abord, comme
    # avant, pour que les lecteurs qui indexent positionnellement le debut de la liste
    # lisent la meme chose qu'avant la story.
    patches = (patch_presets.resolve_calibration_page_patches(template_id)
               + patch_presets.resolve_calibration_page_witnesses(
                   template_id, patch_preset_id))
    payload_plan = page_payload.plan_page_payload(
        # **Aucune identite de projet ni de lot**, et ce sont des absences, pas des
        # valeurs: le
        # contrat 2.3 retire les cinq champs du payload sous le role `c`
        # (`io.payload.CALIBRATION_ABSENT_FIELDS`). Les cinq sentinelles ci-dessous
        # ne sont donc jamais ecrites nulle part -- elles n'existent que parce que la
        # jonction garde la signature commune aux deux roles.
        project_id=CALIBRATION_NO_PROJECT,
        rush_id=CALIBRATION_NO_RUSH,
        lot_id=CALIBRATION_NO_LOT,
        page_index=CALIBRATION_PAGE_INDEX,
        page_count=CALIBRATION_ONLY_PAGE_COUNT,
        fps_target=CALIBRATION_NO_FPS,
        timecode_base_fps=CALIBRATION_NO_TIMECODE_BASE_FPS,
        # Correction d'Egan du 2026-08-18: le libelle de chaine entre dans le QR (le
        # commentaire libre, non). C'est ce qui permettra a `scan ... calibrate` de le
        # relire depuis la feuille au lieu de le faire ressaisir.
        scan_chain_label=scan_chain_label,
        template_id=template_id,
        patch_preset_id=patch_preset_id,
        target_colorspace=target_colorspace,
        gamut_map_id=gamut_map_id,
        # Aucun emplacement: c'est le role qui l'autorise, et la garde reste stricte
        # pour une planche d'images.
        slots=[],
        page_role=page_roles.PAGE_ROLE_CALIBRATION,
    )
    if payload_plan.geometry_status == qr_codes.GEOMETRY_UNUSABLE:
        version = qr_codes.symbol_version(payload_plan.module_side)
        # Les deux branches de la planche d'images, avec le meme partage de cause -- et
        # une phrase de plus qui n'a de sens que sur cette page: son payload ne porte
        # **aucun** emplacement, donc c'est le plus leger du lot, donc `--frames-par-page`
        # n'y peut rien. Rendre ici le message des planches conseillerait un geste sans
        # effet, ce qui est exactement le defaut que le majeur M9 de la revue de 5.17 a
        # ferme sur l'autre branche.
        if version in qr_codes.QR_BANNED_SYMBOL_VERSIONS:
            raise GeometryOverflowError(
                f"Page de calibration ({CALIBRATION_PAGE_INDEX + 1}/{CALIBRATION_ONLY_PAGE_COUNT}): le "
                f"QR encoderait sur la version {version} du symbole "
                f"({payload_plan.module_side} modules), que le detecteur de production "
                "ne decode a AUCUNE taille imprimee (mesure de la story 5.17, cinq "
                "charges utiles distinctes). Imprimer plus grand n'y change rien. Et "
                "--frames-par-page n'y change rien non plus: cette page ne porte aucun "
                "emplacement, son payload est deja le plus leger du lot. La charge "
                "utile a deplacer est celle des identifiants du projet."
            )
        raise GeometryOverflowError(
            f"Page de calibration ({CALIBRATION_PAGE_INDEX + 1}/{CALIBRATION_ONLY_PAGE_COUNT}): "
            f"geometrie QR inutilisable (version {version} du symbole, "
            f"{payload_plan.module_side} modules, "
            f"{payload_plan.print_size_mm:.1f} mm a {payload_plan.scan_dpi} dpi de "
            "scan). Cette page ne porte aucun emplacement: son payload est le plus "
            "leger du lot, donc un refus ici vient des identifiants du projet et non "
            "du cardinal de frames."
        )
    render_px_per_module = qr_codes.pixels_per_module(
        payload_plan.module_side, payload_plan.print_size_mm, render_dpi
    )
    if render_px_per_module < qr_codes.MIN_PIXELS_PER_MODULE_RELIABLE:
        raise GeometryOverflowError(
            f"--dpi {render_dpi} rasterise le QR de la page de calibration a "
            f"{render_px_per_module:.1f} px/module dans le PDF, sous le seuil fiable "
            f"de {qr_codes.MIN_PIXELS_PER_MODULE_RELIABLE:.0f} px/module (4.6). "
            f"Augmenter --dpi (defaut {RENDER_DPI_DEFAULT})."
        )
    qr_rect = _calibration_qr_rect(spec, grid, payload_plan)
    warnings = list(payload_plan.warnings)
    if payload_plan.geometry_status == qr_codes.GEOMETRY_DEGRADED:
        warnings.append(
            f"GEOMETRIE_QR_DEGRADEE: {payload_plan.print_size_mm:.1f} mm a "
            f"{payload_plan.scan_dpi} dpi de scan, sous la classe la plus eprouvee du "
            "banc 4.6 (arbitrage 4.5-Q2 / EPIC4-ARB-2)."
        )
    qr_plan = QRPagePlan(
        payload=payload_plan.payload,
        payload_text=payload_plan.payload_text,
        budget=payload_plan.budget,
        module_side=payload_plan.module_side,
        required_print_size_mm=payload_plan.required_print_size_mm,
        print_size_mm=payload_plan.print_size_mm,
        geometry_status=payload_plan.geometry_status,
        scan_dpi=payload_plan.scan_dpi,
        footprint_rect_mm=qr_rect,
        warnings=tuple(warnings),
    )
    header_rect = grid.header_zone_mm()
    # **Ce que la feuille imprime, et ce qu'elle n'imprime plus** (story 5.23,
    # correction d'Egan du 2026-08-18). L'entete portait `lot_id`, « page 1/1 » et une
    # cadence: les trois sont faux sur cette feuille -- elle sert toute une chaine de
    # scan, elle n'a qu'une page, elle ne porte aucune frame donc aucune cadence.
    header_lines = _calibration_header_lines(
        orientation=spec.orientation,
        project_id=project_id,
        scan_chain_label=scan_chain_label,
        comment=comment,
        generated_on=generated_on,
        width_mm=header_rect[2],
        font_pt=BODY_FONT_MIN_PT,
    )
    # Les lignes sont exigees **verbatim**. `_wrap_verbatim` les a deja construites
    # pour tenir, donc cette garde ne peut plus mordre par ce chemin: elle reste parce
    # qu'elle est le contrat 4.2 et non une consequence du repartiteur -- un futur
    # producteur de lignes qui l'oublierait se ferait refuser ici plutot que
    # d'imprimer une mention coupee.
    _require_verbatim(header_lines, header_rect, BODY_FONT_MIN_PT,
                      "d'entete de page de calibration")
    text = PageTextPlan(
        # `sheet_label` n'est **pas imprime** sur cette page (le seul bloc de texte est
        # l'entete d'identite): il nomme la feuille pour les consommateurs de plan. Il
        # ne peut donc plus etre `<lot>_pNNN`, cette feuille n'appartenant a aucun lot.
        sheet_label=f"{project_id}_calibration",
        project_id=project_id,
        rush_id=CALIBRATION_NO_RUSH,
        page_number_text="",
        fps_display="",
        scan_instruction=f"Scanner a {qr_codes.QR_MIN_SCAN_DPI} dpi minimum",
        technical_footer="",
        zones_mm={"header_identity": header_rect},
        blocks=(
            TextBlock(name="header_identity", rect_mm=header_rect,
                      font_pt=BODY_FONT_MIN_PT, lines=tuple(header_lines)),
        ),
        slot_labels=(),
        date_line_slot=NO_DATE_LINE_SLOT,
    )
    needed = len(header_lines) * line_leading_mm(BODY_FONT_MIN_PT)
    if needed > header_rect[3] + 1e-9:
        raise GeometryOverflowError(
            f"L'entete de la page de calibration ({len(header_lines)} ligne(s) a "
            f"{BODY_FONT_MIN_PT:.0f} pt) exige {needed:.1f} mm pour "
            f"{header_rect[3]:.1f} mm disponibles. La bande d'entete vaut une rangee de "
            "grille: elle ne s'agrandit qu'en reprenant des cellules au treillis."
        )
    return (
        PagePlan(
            page_index=CALIBRATION_PAGE_INDEX,
            template_id=template_id,
            frames=(),
            qr=qr_plan,
            markers=markers,
            patches=patches,
            text=text,
        ),
        tuple(warnings),
    )


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------


def _lot_identity(manifest: Mapping[str, Any], lot_id: str) -> tuple:
    """L'identite de niveau lot lue au manifest, **une seule redaction**.

    Rend `(lot, project_id, rush_id, fps_target, timecode_base_fps, frames_dir,
    target_colorspace)`.

    Extrait de `compose_lot_plan` par la story 5.22, parce que la composition de
    la page de calibration seule (`compose_calibration_page_plan`) a besoin des
    **memes** champs et des **memes** refus: deux redactions divergeraient, et le
    premier ecart utile serait un message qui envoie l'operateur chercher au
    mauvais endroit. Aucun refus n'est modifie ici, ils sont deplaces au
    caractere.
    """
    lot = _find_entry(manifest.get("lots"), "lot_id", lot_id)
    if lot is None:
        known = ", ".join(
            str(entry.get("lot_id"))
            for entry in manifest.get("lots") or []
            if isinstance(entry, Mapping)
        ) or "(aucun)"
        raise LotContentError(
            f"Le lot '{lot_id}' n'existe pas dans le manifest. Lots "
            f"disponibles: {known}. Verifier --rush/--fps ou --lot."
        )

    project_id = _require(
        manifest.get("project_id"),
        "Le manifest ne porte pas de project_id: impossible de composer.",
    )
    rush_id = _require(
        lot.get("rush_id"),
        f"Le lot '{lot_id}' ne declare pas son rush_id dans le manifest.",
    )
    fps_target = _require(
        lot.get("fps_target"),
        f"Le lot '{lot_id}' ne porte pas lots[].fps_target dans le manifest.",
    )
    try:
        fps_target = float(fps_target)
    except (TypeError, ValueError) as exc:
        # Revue 4.2: un fps_target non numerique (chaine slug...) traversait
        # jusqu'a l'affichage en ValueError brute; le chemin CLI est protege
        # par le schema v2 mais l'API (previz 4.9) ne l'est pas.
        raise LotContentError(
            f"lots[].fps_target du lot '{lot_id}' n'est pas un nombre: "
            f"{lot.get('fps_target')!r}."
        ) from exc
    # Story 2.7 (EPIC7-ARB-56, payload 2.1): la cadence SOURCE du rush, meme
    # forme de refus que ses cinq voisins ci-dessus. Un lot qui ne la porte pas
    # -- lot reconstruit d'un scan 2.0, anterieur a cette story, ou d'une
    # extraction anterieure a la story qui a fait ecrire le champ -- n'est pas
    # imprimable en 2.1: le motif dit quoi faire (re-extraire ou completer le
    # manifest) plutot que d'inventer une valeur. Chaine **verbatim**, jamais
    # convertie: `fps_target` passe par `float()` juste au-dessus parce que
    # c'est une cadence CIBLE de confort d'affichage; celle-ci est la cadence
    # SOURCE exacte que `codec_profiles.exact_frame_rate` a deja produite en
    # `num/den`, et un aller-retour float la ferait perdre.
    timecode_base_fps = _require(
        lot.get("timecode_base_fps"),
        f"Le lot '{lot_id}' ne porte pas lots[].timecode_base_fps dans le "
        "manifest: cette planche ne peut pas etre imprimee en payload 2.1 "
        "sans sa cadence source. Re-extraire le lot, ou completer "
        "manuellement lots[].timecode_base_fps dans project.json ('num/den', "
        "denominateur explicite).",
    )
    if not isinstance(timecode_base_fps, str) or not timecode_base_fps:
        raise LotContentError(
            f"lots[].timecode_base_fps du lot '{lot_id}' n'est pas une chaine "
            f"non vide: {lot.get('timecode_base_fps')!r}."
        )
    frames_dir = _require(
        lot.get("frames_dir"),
        f"Le lot '{lot_id}' ne declare pas lots[].frames_dir dans le manifest.",
    )
    target_colorspace = (manifest.get("color") or {}).get("target_colorspace")
    if not target_colorspace:
        raise LotContentError(
            "color.target_colorspace est absent du manifest: le payload QR "
            "exige un espace couleur cible non vide (contrat 2.3). Renseigner "
            "color.target_colorspace dans project.json avant makepdf "
            "(constat METADONNEES_A_RENSEIGNER_AVANT_ENCODE)."
        )
    return (
        lot, project_id, rush_id, fps_target, timecode_base_fps, frames_dir,
        target_colorspace,
    )


#: `page_count` d'une page de calibration composee **seule** (story 5.22). Elle
#: n'appartient plus a l'espace d'index d'un lot -- la calibration est par
#: chaine de scan --, donc elle est a elle seule tout ce qu'il y a a paginer.
CALIBRATION_ONLY_PAGE_COUNT = 1

#: Les cinq identites que la page de calibration **ne porte pas**, sous la forme que
#: la jonction `page_payload` attend (story 5.23, plus `timecode_base_fps` par la
#: story 2.7). Elles ne sont jamais ecrites: le contrat 2.3 retire les cinq champs du
#: payload sous le role `c` (`io.payload.CALIBRATION_ABSENT_FIELDS`). Elles existent
#: parce que la jonction garde une signature commune aux deux roles, et elles sont
#: **vides plutot que plausibles**: une valeur plausible qui fuirait quelque part
#: serait indetectable, une valeur vide se fait refuser par le premier consommateur
#: qui la lirait.
CALIBRATION_NO_PROJECT = ""
CALIBRATION_NO_RUSH = ""
CALIBRATION_NO_LOT = ""
CALIBRATION_NO_FPS = 0.0
#: Story 2.7: sentinelle chaine, vide comme ses trois voisines textuelles --
#: `CALIBRATION_NO_FPS` reste un nombre parce que `fps_target` en est un;
#: `timecode_base_fps`, lui, est une chaine des le contrat (forme `num/den`).
CALIBRATION_NO_TIMECODE_BASE_FPS = ""


@dataclass(frozen=True)
class _ResolvedParameters:
    """Les parametres de composition **resolus une seule fois** (story 5.22).

    Les deux points d'entree de composition -- `compose_lot_plan` et
    `compose_calibration_page_plan` -- resolvent **exactement** le meme
    vocabulaire, et c'est structurel: la page de calibration doit declarer dans
    son QR le meme `template_id` que les planches du lot, sinon `scan calibrate`
    resout un autre treillis et echantillonne les pastilles a cote.

    Le regroupement n'est donc pas une economie de lignes, c'est le maintien
    d'une propriete que le depot verifie par AST: **une seule** resolution de
    chaque registre dans tout le module (`resolve_gamut_map` en tete, story
    5.10 AC 7). Deux blocs de resolution recopies auraient rendu exprimable le
    desaccord que cette propriete existe pour interdire.

    L'ordre de resolution est celui d'avant la story, au caractere: la version
    de geometrie **avant** le cardinal de frames, parce que depuis 5.18 le
    vocabulaire des cardinaux depend de la version (`EPIC5-ARB-62`).
    """

    page_format: str
    orientation: str
    geometry_version: str
    frames_per_page: int
    margin_preset: str
    patch_preset_id: str
    gamut_map_id: str
    render_dpi: int
    spec: page_templates.TemplateSpec

    @property
    def template_id(self) -> str:
        return self.spec.template_id


def _resolve_parameters(
    *,
    orientation: str | None,
    frames_per_page: int | None,
    margin_preset: str | None,
    patch_preset: str | None,
    # `gamut_map` et non `gamut_map_id`, comme `patch_preset` en face de
    # `patch_preset_id`: c'est la valeur **brute** de l'option, avant resolution.
    # La convention de nommage du module distingue les deux, et elle le fait ici
    # pour une raison verifiee par test: le suffixe `_id` designe la valeur
    # resolue, et une frontiere AST compte les points qui l'emettent
    # (`test_makepdf_emits_exactly_the_identity_gamut_map`).
    gamut_map: str | None,
    render_dpi: int | None,
    page_format: str | None,
    geometry_version: str | None,
) -> _ResolvedParameters:
    """Resoudre le vocabulaire de composition. Voir :class:`_ResolvedParameters`."""
    page_format = resolve_page_format(page_format)
    orientation = resolve_orientation(orientation)
    # La version de geometrie se resout **avant** le cardinal de frames: depuis la story
    # 5.18 le vocabulaire des cardinaux depend de la version (`EPIC5-ARB-62`), donc
    # valider le cardinal contre le vocabulaire du defaut refuserait 6f en v1 -- une
    # geometrie qui le porte encore -- ou l'accepterait en v2, qui ne le resout plus.
    geometry_version = resolve_geometry_version(geometry_version)
    frames_per_page = resolve_frames_per_page(
        orientation, frames_per_page, geometry_version)
    margin_preset = resolve_margin_preset(margin_preset)
    patch_preset_id = resolve_patch_preset(patch_preset)
    # Resolution **une seule fois**, ici: l'attribut de plan porte ensuite
    # l'identifiant deja resolu, et ni le rendu ni 5.11 ne le re-resolvent.
    gamut_map_id = resolve_gamut_map(gamut_map)
    render_dpi = resolve_render_dpi(render_dpi)
    return _ResolvedParameters(
        page_format=page_format,
        orientation=orientation,
        geometry_version=geometry_version,
        frames_per_page=frames_per_page,
        margin_preset=margin_preset,
        patch_preset_id=patch_preset_id,
        gamut_map_id=gamut_map_id,
        render_dpi=render_dpi,
        spec=page_templates.template_for(
            orientation, frames_per_page, margin_preset, geometry_version),
    )


def compose_calibration_page_plan(
    *,
    manifest: Mapping[str, Any],
    scan_chain_label: str,
    comment: str | None = None,
    generated_on: date | None = None,
    orientation: str | None = None,
    frames_per_page: int | None = None,
    margin_preset: str | None = None,
    patch_preset: str | None = None,
    gamut_map_id: str | None = None,
    render_dpi: int | None = None,
    page_format: str | None = None,
    geometry_version: str | None = None,
) -> LotComposition:
    """Composer la **page de calibration seule**, a la demande (story 5.22, AC 8).

    `EPIC5-ARB-80` decision 7: la page n'est plus inseree a l'index 0 de chaque lot,
    elle est generee explicitement -- une fois par **chaine de scan**, puis scannee par
    `scan calibrate`, qui en tire le profil consigne dans le projet.

    Le plan rendu est un `LotComposition` d'**une** page et non un type nouveau, et ce
    choix est ce qui rend la story petite: `pdf_render.render_lot_pdf` le consomme sans
    une ligne de plus, et la garde de coherence de compression
    (`_assert_declared_gamut_map_matches`) s'y applique telle quelle.

    Aucun lot: le gabarit se resout autrement (story 5.23)
    ------------------------------------------------------
    La signature de 5.22 exigeait un `lot_id`. Elle ne l'exige plus, et le motif est
    d'ordre de travail: **une page de calibration se genere avant tout lot**, avant
    toute extraction -- c'est precisement ce que la calibration par chaine rend
    possible, et l'exiger l'interdirait.

    Le lot ne fournissait, en fait, que deux choses, et **aucune des deux n'etait le
    gabarit**:

    * l'identite (`rush_id`, `lot_id`, `fps_target`), que l'AC 8bis vient justement de
      retirer de cette feuille -- elle sert toute une chaine, pas un lot;
    * `frames_dir`, dont cette page n'a aucun usage: elle ne porte pas une frame.

    **Le gabarit, lui, ne venait jamais du lot**: il est resolu par
    `_resolve_parameters`, qui ne lit pas le manifest -- ce sont les options de
    composition (`--orientation`, `--frames-par-page`, `--marge`, `--geometrie`,
    `--format`) et leurs defauts de registre, exactement les memes resolveurs que
    `compose_lot_plan`. Passer un lot n'y changeait rien; le croire necessaire etait
    une lecture erronee du couplage.

    Rien ne se desaccorde pour autant, et c'est verifiable: `scan ... calibrate` resout
    le treillis depuis le `template_id` que **cette feuille declare dans son propre
    QR**. La coherence est donc interne a la feuille, la ou elle etait auparavant
    tenue par un lot dont la page ne fait plus partie.

    Du manifest, il ne reste donc a lire que `color.target_colorspace`, qui est de
    niveau **projet** et non de niveau lot.

    `page_count` vaut `CALIBRATION_ONLY_PAGE_COUNT` (1) et `page_index` vaut
    `CALIBRATION_PAGE_INDEX` (0): la page est autoportante.
    """
    resolved = _resolve_parameters(
        orientation=orientation, frames_per_page=frames_per_page,
        margin_preset=margin_preset, patch_preset=patch_preset,
        gamut_map=gamut_map_id, render_dpi=render_dpi,
        page_format=page_format, geometry_version=geometry_version)
    spec = resolved.spec
    template_id = resolved.template_id
    patch_preset_id = resolved.patch_preset_id
    gamut_map_id = resolved.gamut_map_id
    render_dpi = resolved.render_dpi

    # Le libelle est valide **ici**, avant toute geometrie: c'est le seul champ que
    # l'operateur saisit librement, donc le seul dont le refus doit lui parvenir avant
    # qu'il n'ait attendu une composition complete. La validation est celle du contrat
    # 2.3, jamais une seconde redaction locale.
    # Le libelle est **rogne une fois, ici**, avant tout usage: il est imprime, il
    # voyage dans le QR et il nomme le fichier, et une espace de bord qui survivrait
    # dans l'un des trois ferait diverger les trois formes de la meme chaine -- donc
    # deux fichiers pour une seule chaine, au premier copier-coller de l'operateur.
    if isinstance(scan_chain_label, str):
        scan_chain_label = scan_chain_label.strip()
    payload_io.validate_scan_chain_label(scan_chain_label)
    comment = _validate_calibration_comment(comment)
    # La date est **injectable** et non lue au fond de la composition: un plan compose
    # deux fois doit etre identique deux fois, et une horloge appelee en profondeur
    # rendrait la composition non reproductible -- donc intestable, et pas seulement
    # inelegante. Le defaut est pris ici, au seul endroit qui a le droit de connaitre
    # l'heure.
    if generated_on is None:
        generated_on = datetime.now(timezone.utc).date()

    project_id = _require(
        manifest.get("project_id"),
        "Le manifest ne porte pas de project_id: impossible de composer.",
    )
    target_colorspace = (manifest.get("color") or {}).get("target_colorspace")
    if not target_colorspace:
        raise LotContentError(
            "color.target_colorspace est absent du manifest: le payload QR "
            "exige un espace couleur cible non vide (contrat 2.3). Renseigner "
            "color.target_colorspace dans project.json avant makepdf "
            "(constat METADONNEES_A_RENSEIGNER_AVANT_ENCODE)."
        )

    # **Le refus geometrique est ici, et il est un refus et non un avertissement.**
    # Sous la v1, dont le degagement de coin vaut 60 mm, la grille du treillis tombe a
    # 57 cellules pour 130 pastilles: la page n'est pas composable. Maintenant que la
    # page **est** le produit demande, un avertissement rendrait un PDF vide en
    # annoncant un succes: c'est le faux succes que ce depot refuse partout.
    refusal = patch_presets.calibration_page_refusal(template_id)
    if refusal is not None:
        raise GeometryOverflowError(f"{WARNING_NO_CALIBRATION_PAGE}: {refusal}")

    marker_centers = page_templates.corner_marker_centers_mm(spec)
    markers = tuple(
        MarkerPlan(
            marker_id=marker_id,
            center_x_mm=marker_centers[marker_id][0],
            center_y_mm=marker_centers[marker_id][1],
            size_mm=spec.geometry.marker_size_mm,
        )
        for marker_id in layout.PRINTED_MARKER_IDS
    )
    page, warnings = _calibration_page_plan(
        spec=spec,
        project_id=project_id,
        scan_chain_label=scan_chain_label,
        comment=comment,
        generated_on=generated_on,
        patch_preset_id=patch_preset_id,
        target_colorspace=target_colorspace,
        gamut_map_id=gamut_map_id,
        render_dpi=render_dpi,
        markers=markers,
    )
    return LotComposition(
        project_id=project_id,
        # Les trois identites de lot sont **vides**: cette feuille n'appartient a aucun
        # lot. Elles restent des attributs du contrat de plan, que `pdf_render` ne lit
        # pas sur cette page -- et un consommateur qui les lirait quand meme se ferait
        # refuser par sa propre garde de non-vacuite plutot que d'associer la feuille a
        # un lot invente.
        rush_id=CALIBRATION_NO_RUSH,
        lot_id=CALIBRATION_NO_LOT,
        fps_target=CALIBRATION_NO_FPS,
        page_format=resolved.page_format,
        orientation=resolved.orientation,
        frames_per_page=resolved.frames_per_page,
        margin_preset=resolved.margin_preset,
        template_id=template_id,
        patch_preset_id=patch_preset_id,
        gamut_map_id=gamut_map_id,
        render_dpi=render_dpi,
        scan_dpi=qr_codes.QR_MIN_SCAN_DPI,
        # Le dossier de frames **du projet** et non celui d'un lot: cette page n'en
        # ouvre aucun -- elle ne porte pas une frame --, mais le champ est de niveau lot
        # dans le contrat de plan et y poser une chaine vide ferait resoudre
        # `project_dir / ""` au rendu.
        frames_dir=project_layout.FRAMES_DIRNAME,
        pdf_filename=naming.build_calibration_pdf_filename(
            project_id, scan_chain_label),
        page_count=CALIBRATION_ONLY_PAGE_COUNT,
        pages=(page,),
        warnings=tuple(
            f"page de calibration: {warning}" for warning in warnings),
    )


def _inventaire_de_planches(
    manifest: Mapping[str, Any] | None, lot_id: str
) -> list[Mapping[str, Any]]:
    """Les entrees de `lots[].sheets_pdfs` du lot vise, ou une liste vide.

    Rend une liste vide plutot que de lever sur un manifeste absent ou
    anterieur a cette story : le champ est ADDITIF, et son absence signifie
    « aucun tirage declare », pas « manifeste invalide ».
    """
    for lot in (manifest or {}).get("lots") or []:
        if isinstance(lot, Mapping) and lot.get("lot_id") == lot_id:
            return [e for e in (lot.get("sheets_pdfs") or []) if isinstance(e, Mapping)]
    return []


def sheets_version_watermark(
    manifest: Mapping[str, Any] | None, lot_id: str, project_dir: Any = None,
    *, project_id: str | None = None, rush_id: str | None = None,
) -> int:
    """Le plus haut rang de tirage JAMAIS employe pour ce lot (`EPIC11-ARB-92`).

    **Un rang se CONSOMME, il ne se libere pas** (Egan, 2026-08-31 : « il ne
    faut pas rendre le rang, la v2 a ete consommee par la v3 qui se trouve
    apres »). Retirer l'entree du tirage 2 alors que le 3 existe ne rend pas
    le 2 : le tirage suivant sera le 4. Sans cela, deux planches PAPIER
    differentes porteraient toutes deux « v2 » -- exactement la confusion que
    le versionnage existe pour empecher, et qu'aucun fichier ne peut plus
    rattraper une fois l'encre seche.

    **Et la regle est la MEME pour les cinq objets versionnables**
    (`EPIC11-ARB-108`, Egan : « Il n'y a pas de mecanisme different par
    objet »). Ce commentaire a longtemps affirme l'inverse -- « c'est une
    divergence assumee avec les lots et les masters, qui rendent le TROU » --
    et il etait deja faux quand il a ete ecrit : les deux resolveurs passaient
    par `version_ranks.prochain_rang` dans le meme diff. Il a fallu la couche
    3 d'une revue pour le voir, ce qu'aucune relecture n'avait fait.

    La ligne d'eau se lit au manifeste ; a defaut (manifeste anterieur a cet
    arbitrage) elle se DEDUIT du plus haut rang declare, et le disque est
    consulte en plus, jamais a la place : un fichier present que le manifeste
    ignore a bien consomme son rang.
    """
    declaree = None
    for lot in (manifest or {}).get("lots") or []:
        if isinstance(lot, Mapping) and lot.get("lot_id") == lot_id:
            declaree = lot.get("sheets_version_watermark")
            break
    rangs = {r for r, _ in _rangs_declares(manifest, lot_id)}
    if project_dir is not None and project_id and rush_id:
        rangs |= _rangs_sur_le_disque(project_dir, project_id, rush_id, lot_id)
    # Le calcul vit dans `io.version_ranks`, ecrit UNE fois pour les trois
    # objets versionnables du depot: trois copies seraient trois verites.
    return version_ranks.ligne_d_eau(declaree, rangs)


def _rangs_declares(
    manifest: Mapping[str, Any] | None, lot_id: str
) -> list[tuple[int, Mapping[str, Any]]]:
    """(rang, entree) pour chaque tirage declare a l'inventaire du lot."""
    rangs: list[tuple[int, Mapping[str, Any]]] = []
    for entree in _inventaire_de_planches(manifest, lot_id):
        valeur = entree.get("version_rank")
        rang = valeur if isinstance(valeur, int) and not isinstance(valeur, bool) else 1
        rangs.append((rang, entree))
    return rangs


def _rangs_sur_le_disque(
    project_dir: Any, project_id: str, rush_id: str, lot_id: str
) -> set[int]:
    """Les rangs dont le FICHIER est present, meme absents du manifeste.

    Un tirage ecrit avant cet arbitrage, ou copie a la main, a bel et bien
    consomme son rang : l'ignorer ferait ecrire le tirage suivant par-dessus.

    **Le balayage porte sur TOUTES les mises en page, et c'est un correctif**
    (`EPIC11-ARB-175`, consequence 2). Depuis `EPIC11-ARB-171` le nom porte la
    mise en page ; une enumeration qui n'en connaitrait qu'une ne verrait pas
    les tirages des autres formes, **sous-estimerait la ligne d'eau**, et
    re-attribuerait un rang deja consomme -- deux feuilles PAPIER de formes
    differentes portant le meme « tirage N », exactement ce qu'`EPIC11-ARB-92`
    interdit.

    **La route est choisie, et l'autre est ecartee nommement** (AC 2.11c). Les
    tirages DECLARES se lisent a `lots[].sheets_pdfs[].path` (`EPIC11-ARB-90`),
    qui porte le chemin reellement ecrit et ne demande aucune reconstruction :
    c'est `_rangs_declares`, et elle n'a rien a changer. Cette fonction-ci ne
    couvre que le cas qu'elle seule couvre -- un fichier present que le
    manifeste ignore --, donc c'est elle seule qui paie le balayage. **Parser
    les noms presents** au lieu de les reconstruire est ecarte : ce serait
    re-deriver une convention dont `io/naming.py` est proprietaire.

    Cout : `(1 + len(known_template_ids())) x 99` constructions de chaine, et
    **zero I/O supplementaire** -- le dossier n'est liste qu'une fois.

    **La limite est dite plutot que tue** (AC 2.11e) : l'ensemble balaye est
    celui du registre d'AUJOURD'HUI. Un cardinal retire demain sortirait du
    registre, et les planches deja imprimees sous cette forme redeviendraient
    invisibles ici -- c'est le risque que `build_template_id` documente deja.
    L'attenuation est la route ci-dessus : un tirage declare au manifeste ne
    depend pas du registre. Routee en dette.
    """
    # **LES DEUX RACINES**, `EPIC11-ARB-225`. Ce balayage est un LECTEUR, pas
    # un ecrivain : il mesure quels rangs sont deja CONSOMMES. N'interroger que
    # `planches/` sur un projet ancien sous-estimerait la ligne d'eau et
    # re-attribuerait un rang deja imprime -- deux feuilles PAPIER portant le
    # meme « tirage N », ce qu'`EPIC11-ARB-92` interdit et qu'aucun fichier ne
    # rattrape une fois l'encre seche. C'est le defaut `E2-1`, au mot pres.
    racines = project_layout.racines_de_planches(project_dir)
    presents: set[str] = set()
    for dossier in racines:
        if not dossier.is_dir():
            continue
        presents |= {chemin.name for chemin in dossier.iterdir() if chemin.is_file()}
    if not presents:
        return set()
    rangs: set[int] = set()
    # `None` en tete: la forme d'AVANT `EPIC11-ARB-171` (`..._planches.pdf`).
    # Aucun fichier deja ecrit n'est renomme, donc un tirage pose sous
    # l'ancienne convention a consomme son rang et doit continuer de le dire.
    for gabarit in (None, *page_templates.known_template_ids()):
        for rang in [1, *range(naming.VERSION_RANK_MIN, naming.VERSION_RANK_MAX + 1)]:
            version_rank = None if rang == 1 else rang
            try:
                if gabarit is None:
                    nom = naming.legacy_sheets_pdf_filename(
                        project_id, rush_id, lot_id, version_rank=version_rank)
                else:
                    nom = naming.build_sheets_pdf_filename(
                        project_id, rush_id, lot_id,
                        version_rank=version_rank, template_id=gabarit)
            except naming.NamingError:
                # **TRANCHE, pas herite** (AC 2.11d). Le `break` d'origine
                # sortait de la boucle unique ; imbrique sous une boucle de
                # gabarits il change de sens, et il fallait choisir. Il coupe
                # la FORME COURANTE, jamais le balayage entier : le refus du
                # nommage ne depend pas du rang (identifiants vides, gabarit
                # que le registre ne resout pas), donc insister sur les 98
                # rangs suivants de cette forme ne rendrait rien -- mais faire
                # disparaitre les tirages des 63 AUTRES formes ferait
                # re-attribuer un rang, c'est-a-dire produirait le defaut que
                # cette fonction vient de fermer.
                break
            if nom in presents:
                rangs.add(rang)
    return rangs


def resolve_sheets_version_rank(
    project_dir: Any,
    *,
    project_id: str,
    rush_id: str,
    lot_id: str,
    manifest: Mapping[str, Any] | None = None,
) -> int:
    """Le rang du PROCHAIN tirage : la ligne d'eau plus un (`EPIC11-ARB-92`).

    Ce n'est plus « le premier rang libre ». La redaction d'origine rendait le
    TROU, sur le modele des lots -- et Egan l'a corrige : un rang consomme ne
    se rend pas, sans quoi deux tirages papier porteraient le meme numero.
    Retirer le tirage 2 quand le 3 existe laisse donc le prochain a 4.

    Le seul chemin qui fait redescendre la ligne d'eau est le retrait du
    DERNIER tirage a date, sur demande explicite -- voir
    `project_maintenance._retirer_un_tirage`.
    """
    if not _rangs_declares(manifest, lot_id) and not _rangs_sur_le_disque(
            project_dir, project_id, rush_id, lot_id):
        # Aucun tirage, jamais : le prochain est l'ORIGINE, pas une version.
        aucune = not any(
            isinstance(l, Mapping) and l.get("lot_id") == lot_id
            and isinstance(l.get("sheets_version_watermark"), int)
            for l in (manifest or {}).get("lots") or []
        )
        if aucune:
            return 1
    ligne = sheets_version_watermark(
        manifest, lot_id, project_dir, project_id=project_id, rush_id=rush_id)
    rang = version_ranks.prochain_rang(ligne)
    if rang > naming.VERSION_RANK_MAX:
        raise LotContentError(version_ranks.refus_de_rangs_epuises(
            "planches", lot_id,
            "Deux issues: retirer la DERNIERE planche en liberant son rang "
            "(`mmu project remove --lot <id> --planche --version <n> "
            "--liberer-le-rang`, "
            "qui rend d'un coup toute la queue devenue libre), ou ecraser "
            "sciemment une planche existante (--overwrite).",
        ))
    return rang


def compose_lot_plan(
    *,
    manifest: Mapping[str, Any],
    lot_id: str,
    orientation: str | None = None,
    frames_per_page: int | None = None,
    margin_preset: str | None = None,
    patch_preset: str | None = None,
    gamut_map_id: str | None = None,
    render_dpi: int | None = None,
    page_format: str | None = None,
    geometry_version: str | None = None,
    version_rank: int | None = None,
) -> LotComposition:
    """Composer le plan complet du lot ``lot_id`` (voir docstring de module).

    ``version_rank`` est le rang de version de la PLANCHE (`EPIC11-ARB-91`).
    Il se propage a **trois** endroits, et les trois sont necessaires : le nom
    du fichier PDF, l'etiquette IMPRIMEE en en-tete, et le payload QR. Le
    premier protege le disque ; les deux autres protegent la feuille une fois
    qu'elle a quitte le disque -- ce qu'aucun nom de fichier ne peut faire.

    Les parametres sont valides en premier (vocabulaire ferme, AC 2), le
    contenu du lot ensuite (manifest + selection recalculee, AC 4), la
    geometrie page par page en dernier (AC 3, 5, 6). Les erreurs de budget
    (``PayloadBudgetExceeded``) et de validation 2.3 traversent sans
    maquillage.
    """
    # Resolution du vocabulaire **une seule fois**, et par le meme chemin que la
    # composition de la page de calibration seule (story 5.22): voir
    # `_ResolvedParameters`.
    resolved = _resolve_parameters(
        orientation=orientation, frames_per_page=frames_per_page,
        margin_preset=margin_preset, patch_preset=patch_preset,
        gamut_map=gamut_map_id, render_dpi=render_dpi,
        page_format=page_format, geometry_version=geometry_version)
    page_format = resolved.page_format
    orientation = resolved.orientation
    geometry_version = resolved.geometry_version
    frames_per_page = resolved.frames_per_page
    margin_preset = resolved.margin_preset
    patch_preset_id = resolved.patch_preset_id
    gamut_map_id = resolved.gamut_map_id
    render_dpi = resolved.render_dpi
    spec = resolved.spec
    template_id = resolved.template_id
    # Resolution 4.7 en amont de toute pagination: un couple template x preset
    # sans placement explicite est refuse ici (UndefinedPlacementError).
    patches = patch_presets.resolve_patch_layout(template_id, patch_preset_id)

    (
        lot, project_id, rush_id, fps_target, timecode_base_fps, frames_dir,
        target_colorspace,
    ) = _lot_identity(manifest, lot_id)

    selection = _recompute_selection(manifest, lot)
    frames = list(selection.frames)  # ordre output_rank, contrat 3.2

    #: La formule vit dans :func:`nombre_de_planches` depuis la story 11.4b : le
    #: scan doit deduire le meme `page_count` pour completer une planche muette
    #: (`EPIC11-ARB-64`), et deux redactions de la meme pagination divergeraient
    #: sans qu'aucune etape n'echoue -- le symptome serait un `page_count` faux
    #: dans le payload reconstitue d'une planche, donc un refus de completude sur
    #: un lot complet.
    page_count = nombre_de_planches(len(frames), frames_per_page)
    marker_centers = page_templates.corner_marker_centers_mm(spec)
    markers = tuple(
        MarkerPlan(
            marker_id=marker_id,
            center_x_mm=marker_centers[marker_id][0],
            center_y_mm=marker_centers[marker_id][1],
            # Taille **du spec** et non de `layout`: les centres viennent deja de la
            # geometrie du template, et imprimer un symbole d'une autre taille que
            # celle que le scan reconstruit rendrait la page illisible sans erreur.
            size_mm=spec.geometry.marker_size_mm,
        )
        for marker_id in layout.PRINTED_MARKER_IDS
    )
    footer_zones = _footer_zones_mm(spec)
    scan_instruction = f"Scanner a {qr_codes.QR_MIN_SCAN_DPI} dpi minimum"
    fps_display = format_fps_display(fps_target)
    # Pied de page technique: chaque renseignement derive des constantes et
    # contrats reels (aruco_dictionary_name, registres, PAYLOAD_SCHEMA_VERSION du
    # contrat 2.3, `_lot_identity`, `nombre_de_planches`) -- jamais un litteral
    # local (finding 4.3, AC 6.1 de la 11.4b).
    #
    # **`timecode_base_fps` s'imprime VERBATIM**, telle que `_lot_identity` l'a
    # lue sur `lots[].timecode_base_fps`: c'est une **fraction exacte**
    # (`'25/1'`, `'24000/1001'`) et non un flottant. La convertir en cadence
    # d'affichage serait doublement faux -- `format_fps_display` refuse la chaine
    # avec un `ValueError`, et sur un rush NTSC `24000/1001` et `23,976` ne sont
    # pas le meme nombre. Ce pied existe pour etre retape a la main
    # (`EPIC11-ARB-65`): c'est la valeur du contrat qui s'y imprime, jamais une
    # projection d'affichage.
    #
    # **`page_count` est le CARDINAL de planches du lot**, pas un rang de page:
    # le pied est identique sur toutes les planches du lot. La pagination
    # « N/M », elle, vit a l'entete (`page_number_text`).
    technical_parts = pied_technique_parts(
        geometry_version=geometry_version,
        valeurs={
            "aruco_dictionary": layout.aruco_dictionary_name(),
            "template_id": template_id,
            "patch_preset_id": patch_preset_id,
            "schema_version": PAYLOAD_SCHEMA_VERSION,
            "timecode_base_fps": timecode_base_fps,
            "target_colorspace": target_colorspace,
            "gamut_map_id": gamut_map_id,
            "page_count": page_count,
        },
    )
    # Largeur bornante du pied: la colonne technique quand le gabarit en pose
    # (v2), le bloc entier sinon. C'est la meme largeur que `_pack_lines`
    # recevra plus bas, et elle ne depend pas de la page -- `_header_zones_mm`
    # n'ajoute aucune zone technique.
    _technical_zone_names = [name for name in page_templates.FOOTER_TECHNICAL_ZONE_NAMES
                             if name in footer_zones]
    _technical_width_mm = (footer_zones[_technical_zone_names[0]][2]
                           if _technical_zone_names else footer_zones["footer_block"][2])
    technical_footer = " - ".join(technical_parts)

    pages: list[PagePlan] = []
    lot_warnings: list[str] = []
    if geometry_version != page_templates.GEOMETRY_V1.version:
        # Le pied **gele** de la v1 en est exempt: il ne porte aucun des quatre
        # renseignements que l'AC 6 ajoute, et sa mention `template=...` se
        # tronque depuis toujours -- signaler cela retroactivement ferait parler
        # une geometrie que rien ne doit plus faire bouger.
        for mention in mentions_tronquees(
                technical_parts, _technical_width_mm, BODY_FONT_MIN_PT):
            lot_warnings.append(
                f"{PIED_TECHNIQUE_TRONQUE}: la mention '{mention}' "
                f"({len(mention)} caracteres) ne tient pas verbatim dans la "
                f"colonne technique du pied ({_technical_width_mm:.1f} mm a "
                f"{BODY_FONT_MIN_PT:.0f} pt). Elle s'imprime tronquee avec "
                f"'{TRUNCATION_MARKER}' et ne peut donc PAS etre retapee depuis "
                "la planche quand le QR est illisible (EPIC11-ARB-65). Le QR la "
                "porte toujours en entier; raccourcir la valeur au manifest la "
                "rendrait relisible au papier."
            )

    # **Le lot ne contient que des planches d'images** depuis la story 5.22: le rang de
    # `chunk` et le `page_index` coincident donc a nouveau, comme avant 5.16. Le decalage
    # d'un cran qu'introduisait la page de calibration inseree en tete n'existe plus, et
    # avec lui disparait le regime ou les confondre imprimait les frames de la premiere
    # planche sur la seconde en silence.
    for page_index in range(page_count):
        chunk = frames[page_index * frames_per_page : (page_index + 1) * frames_per_page]
        slots = [
            {"slot_index": frame.output_rank, "frame_timecode": frame.frame_timecode}
            for frame in chunk
        ]
        payload_plan = page_payload.plan_page_payload(
            project_id=project_id,
            rush_id=rush_id,
            lot_id=lot_id,
            page_index=page_index,
            page_count=page_count,
            fps_target=fps_target,
            # Story 2.7 (EPIC7-ARB-56): chaine verbatim, jamais recalculee --
            # celle que `_lot_identity` a lue sur `lots[].timecode_base_fps`.
            timecode_base_fps=timecode_base_fps,
            template_id=template_id,
            patch_preset_id=patch_preset_id,
            target_colorspace=target_colorspace,
            # **Source unique** (story 5.10, AC 7): la meme valeur part au
            # QR, sert a resoudre la `G` appliquee au raster, et sera lue
            # telle quelle par 5.11 pour le manifest. Trois consommateurs,
            # une resolution -- sinon trois occasions de diverger, pour un
            # defaut dont le symptome est **nul** a l'impression.
            gamut_map_id=gamut_map_id,
            slots=slots,
            # Role **explicite** et non laisse au defaut (story 5.16): les deux
            # producteurs de payload de ce module se lisent alors cote a cote, et une
            # permutation des deux roles se voit. Un defaut implicite d'un cote et une
            # valeur explicite de l'autre rendrait la paire illisible.
            page_role=page_roles.PAGE_ROLE_IMAGES,
            # TROISIEME porteur du rang, et le seul que la MACHINE relit
            # (`EPIC11-ARB-91`). Le nom de fichier sert au disque, l'etiquette
            # imprimee sert a l'oeil, et celui-ci sert au scan : sans lui, une
            # planche v2 scannee se reconcilierait sur le lot sans que rien ne
            # dise de quel tirage elle vient.
            version_rank=version_rank,
        )
        if payload_plan.geometry_status == qr_codes.GEOMETRY_UNUSABLE:
            version = qr_codes.symbol_version(payload_plan.module_side)
            if version in qr_codes.QR_BANNED_SYMBOL_VERSIONS:
                # **La cause est la version du symbole, pas la taille imprimee**
                # (majeur M9 de la revue de 5.17). Le motif ne nommait que les
                # millimetres et le dpi -- les deux grandeurs qui, pour une version
                # bannie, sont precisement hors de cause -- et le premier reflexe
                # qu'il inspirait, imprimer plus grand, est sans effet: le detecteur
                # de production ne decode pas cette version, a aucune taille.
                #
                # Le domaine imprimable est de plus **non monotone**, consequence
                # directe et assumee du bannissement d'une version unique: la bande
                # d'octets qui encode sur la version bannie est refusee alors que la
                # suivante est acceptee, si bien qu'**ajouter** des emplacements peut
                # rendre une page composable. Le conseil « reduire » etait donc le
                # seul des deux a etre donne, et il n'est pas toujours le bon.
                # **Les DEUX leviers, pas seulement celui qui marche ici**
                # (`EPIC11-ARB-110`, sur remarque d'Egan). Ce message ne
                # nommait que `--frames-par-page`, qui debloque effectivement
                # -- mais il taisait la CAUSE, qui est la longueur des
                # identifiants du projet. Le message de la page de calibration
                # la nommait deja, parce que cette page n'a aucun emplacement
                # et que le cardinal n'y peut rien ; sur la planche d'images,
                # l'operateur lisait donc un levier sans jamais apprendre
                # pourquoi il en avait besoin.
                raise GeometryOverflowError(
                    f"Page {page_index + 1}/{page_count}: le QR encoderait sur la "
                    f"version {version} du symbole ({payload_plan.module_side} "
                    "modules), que le detecteur de production ne decode a AUCUNE "
                    "taille imprimee (mesure de la story 5.17, cinq charges utiles "
                    "distinctes). Imprimer plus grand n'y change rien: c'est la "
                    "charge utile qu'il faut deplacer hors de cette version. "
                    "DEUX leviers: changer --frames-par-page (le domaine n'est "
                    "pas monotone -- selon le payload, un cardinal plus GRAND "
                    "peut y suffire aussi bien qu'un plus petit), ou raccourcir "
                    "les identifiants du projet, qui pesent chacun leur longueur "
                    "dans chaque QR de chaque planche."
                )
            raise GeometryOverflowError(
                f"Page {page_index + 1}/{page_count}: geometrie QR inutilisable "
                f"({payload_plan.print_size_mm:.1f} mm a {payload_plan.scan_dpi} "
                "dpi de scan). Reduire --frames-par-page."
            )
        render_px_per_module = qr_codes.pixels_per_module(
            payload_plan.module_side, payload_plan.print_size_mm, render_dpi
        )
        if render_px_per_module < qr_codes.MIN_PIXELS_PER_MODULE_RELIABLE:
            raise GeometryOverflowError(
                f"--dpi {render_dpi} rasterise le QR de la page "
                f"{page_index + 1}/{page_count} a {render_px_per_module:.1f} "
                "px/module dans le PDF, sous le seuil fiable de "
                f"{qr_codes.MIN_PIXELS_PER_MODULE_RELIABLE:.0f} px/module "
                f"(4.6). Augmenter --dpi (defaut {RENDER_DPI_DEFAULT})."
            )

        qr_warnings = list(payload_plan.warnings)
        if payload_plan.geometry_status == qr_codes.GEOMETRY_DEGRADED:
            qr_warnings.append(
                f"GEOMETRIE_QR_DEGRADEE: {payload_plan.print_size_mm:.1f} mm a "
                f"{payload_plan.scan_dpi} dpi de scan, sous la classe la plus "
                "eprouvee du banc 4.6 (arbitrage 4.5-Q2 / EPIC4-ARB-2)."
            )
        qr_rect = _qr_footprint_rect(spec, payload_plan)
        qr_plan = QRPagePlan(
            payload=payload_plan.payload,
            payload_text=payload_plan.payload_text,
            budget=payload_plan.budget,
            module_side=payload_plan.module_side,
            required_print_size_mm=payload_plan.required_print_size_mm,
            print_size_mm=payload_plan.print_size_mm,
            geometry_status=payload_plan.geometry_status,
            scan_dpi=payload_plan.scan_dpi,
            footprint_rect_mm=qr_rect,
            warnings=tuple(qr_warnings),
        )
        for warning in qr_warnings:
            lot_warnings.append(f"page {page_index + 1}/{page_count}: {warning}")

        slot_plans: list[FrameSlotPlan] = []
        slot_labels: list[SlotLabel] = []
        for zone, frame in zip(spec.frame_zones_mm, chunk):
            zone_rect = (zone["x"], zone["y"], zone["width"], zone["height"])
            slot_plans.append(
                FrameSlotPlan(
                    slot_index=frame.output_rank,
                    frame_timecode=frame.frame_timecode,
                    frame_filename=naming.build_extracted_frame_filename(
                        rush_id, fps_target, frame.frame_timecode
                    ),
                    zone_name=zone["name"],
                    zone_rect_mm=zone_rect,
                    image_rect_mm=page_templates.frame_image_rect_mm(zone, spec.margin_mm),
                    letterbox_policy=LETTERBOX_POLICY,
                )
            )
            # Etiquette de slot (AC 1 de 4.2): le coeur s<NN> + timecode est
            # LA redondance de secours du mapping slot -> timecode (trou
            # releve par la revue 4.6) -- il reste toujours entier; seul le
            # rappel de rush se tronque avec marqueur quand la zone est
            # etroite, ou s'omet si plus rien ne tient.
            core = f"s{frame.output_rank:02d} tc {frame.frame_timecode}"
            rush_room_mm = (
                zone["width"]
                - text_width_mm(core + " ", BODY_FONT_MIN_PT)
            )
            if _max_chars(rush_room_mm, BODY_FONT_MIN_PT) >= len(TRUNCATION_MARKER) + 1:
                label_text = f"{fit_text(rush_id, rush_room_mm, BODY_FONT_MIN_PT)} {core}"
            else:
                label_text = core
            slot_labels.append(
                SlotLabel(
                    text=label_text,
                    rect_mm=(
                        zone["x"],
                        zone["y"] + zone["height"] + _SLOT_LABEL_OFFSET_MM,
                        zone["width"],
                        _SLOT_LABEL_HEIGHT_MM,
                    ),
                )
            )

        zones_mm = dict(footer_zones)
        zones_mm.update(_header_zones_mm(spec, qr_rect))
        # Le rang de version ENTRE DANS L'ETIQUETTE IMPRIMEE (`EPIC11-ARB-91`).
        #
        # C'est la piece sans laquelle versionner une planche ne servirait a
        # rien : le nom du fichier PDF protege le disque, mais **une planche
        # imprimee a quitte le disque**. Deux tirages du meme lot poses cote a
        # cote sur un bureau sont visuellement identiques ; seul ce fragment
        # les distingue a l'oeil.
        #
        # Meme forme que dans le nom du fichier, et c'est delibere : l'operateur
        # qui compare la feuille au PDF lit LE MEME fragment aux deux endroits,
        # au lieu d'avoir a traduire « version 2 » en `_v2`.
        sheet_label = f"{lot_id}_p{page_index + 1:03d}"
        if version_rank is not None:
            sheet_label = f"{sheet_label}{naming.format_version_suffix(version_rank)}"
        page_number_text = f"page {page_index + 1}/{page_count}"

        # Blocs typographies (story 4.2): le bloc d'identite porte les
        # identifiants canoniques VERBATIM (egalite a l'octet pres avec le
        # payload QR et les noms de fichiers -- mecanisme de secours 4.6);
        # les en-tetes portent des rappels eventuellement tronques avec
        # marqueur visible (AC 6). "page N/M" et la cadence tiennent le rang
        # >= IDENTITY_FONT_MIN_PT dans l'en-tete.
        blocks: list[TextBlock] = []
        if "header_left" in zones_mm:
            rect = zones_mm["header_left"]
            # Forme compacte "N/M" en en-tete (revue 4.2: "page 100/250" a
            # 10 pt depassait la bande de ~24 mm et perdait le denominateur
            # des la page 100); la forme longue "page N/M" vit dans le bloc
            # d'identite. Base un a l'affichage, comme partout.
            blocks.append(
                TextBlock(
                    name="header_left",
                    rect_mm=rect,
                    font_pt=IDENTITY_FONT_MIN_PT,
                    lines=tuple(
                        fit_text(line, rect[2], IDENTITY_FONT_MIN_PT)
                        for line in (f"{page_index + 1}/{page_count}", fps_display)
                    ),
                )
            )
        if "header_right" in zones_mm:
            rect = zones_mm["header_right"]
            # lot_id + numero de page sur deux lignes (revue 4.2: tronquer
            # sheet_label = lot + _pNNN consommait la queue de hachage
            # discriminante du lot; separer les deux preserve `-<hash>`).
            blocks.append(
                TextBlock(
                    name="header_right",
                    rect_mm=rect,
                    font_pt=BODY_FONT_MIN_PT,
                    lines=(
                        fit_text(lot_id, rect[2], BODY_FONT_MIN_PT),
                        fit_text(f"p{page_index + 1:03d}", rect[2], BODY_FONT_MIN_PT),
                    ),
                )
            )
        footer_rect = zones_mm["footer_block"]
        if "header_identity" in zones_mm:
            # Disposition d'`EPIC5-ARB-63`: le nom du lot sur la premiere ligne, la
            # pagination et la cadence sur la seconde, a HEADER_IDENTITY_FONT_PT. Ce
            # sont les deux lignes qu'un operateur lit sur une pile de planches posee
            # sur une table, et leur lisibilite est une exigence fonctionnelle.
            header_rect = zones_mm["header_identity"]
            # LE RANG DOIT ETRE TYPOGRAPHIE, pas seulement pose sur le plan.
            #
            # Defaut trouve en revue, et il vidait la story de son sens: le
            # rang etait ajoute a `sheet_label`, or `sheet_label` n'est PLUS
            # imprime depuis la geometrie v2 -- qui est le DEFAUT. Deux
            # tirages du meme lot sortis de l'imprimante etaient donc
            # typographiquement identiques, c'est-a-dire exactement ce que ce
            # rang existe pour empecher. Le test ne pouvait pas le voir: il
            # assertait sur l'attribut Python, jamais sur un bloc de texte.
            ligne_pagination = f"{page_number_text} - {fps_display}"
            if version_rank is not None:
                # MEME FORME que dans le nom du fichier et que sur l'etiquette
                # de la geometrie v1 (`_v2`), et non ` - v2`. Deux formes
                # imprimees du meme fait seraient deux verites
                # (`EPIC5-ARB-78`) -- et surtout, l'operateur qui compare la
                # feuille au PDF doit lire LE MEME fragment aux deux endroits
                # plutot que d'avoir a traduire l'une en l'autre.
                # Sur la ligne de PAGINATION, jamais accrochee au `lot_id` de
                # la ligne 1 : celle-la doit rester VERBATIM pour le mecanisme
                # de secours 4.6, qui relit les identifiants imprimes quand le
                # QR ne se decode pas. Un `lot_id` augmente d'un suffixe ferait
                # relire un lot qui n'existe pas.
                #
                # Le mot `tirage` porte le fragment plutot que de le coller a
                # l'unite : `5 im/s_v2` se lit mal et invite a lire « im/s_v2 »
                # comme une cadence.
                ligne_pagination = (
                    f"{ligne_pagination} - tirage"
                    f"{naming.format_version_suffix(version_rank)}")
            header_lines = [lot_id, ligne_pagination]
            _require_verbatim(header_lines, header_rect,
                              page_templates.HEADER_IDENTITY_FONT_PT, "d'entete")
            blocks.append(
                TextBlock(
                    name="header_identity",
                    rect_mm=header_rect,
                    font_pt=page_templates.HEADER_IDENTITY_FONT_PT,
                    lines=tuple(header_lines),
                )
            )
            # Le pied ne garde que les deux identifiants que l'arbitrage ne nomme pas et
            # que le mecanisme de secours 4.6 exige verbatim. `sheet_label` n'en est pas:
            # ses deux composants -- le lot et le numero de page -- sont **tous les deux**
            # en entete, ligne 1 et ligne 2.
            identity_lines = [project_id, rush_id]
        else:
            identity_lines = [sheet_label, project_id, rush_id,
                              f"{page_number_text} - {fps_display}"]
        _require_verbatim(identity_lines, footer_rect, BODY_FONT_MIN_PT, "d'identite")
        technical_zones = [
            name for name in page_templates.FOOTER_TECHNICAL_ZONE_NAMES
            if name in zones_mm
        ]
        if technical_zones:
            # Technique sur deux colonnes (`EPIC5-ARB-63`), remplies colonne par colonne
            # et **date d'abord**: le rang de la date est declare au plan, jamais decide
            # par le rendu.
            column_width = zones_mm[technical_zones[0]][2]
            packed = _pack_lines(technical_parts, column_width, BODY_FONT_MIN_PT)
            rows = -(-(len(packed) + 1) // len(technical_zones))  # exces, date comprise
            date_slot = (technical_zones[0], 0)
            columns: list[list[str]] = [[] for _name in technical_zones]
            remaining = list(packed)
            for index, _name in enumerate(technical_zones):
                room = rows - 1 if index == 0 else rows
                columns[index] = remaining[:room]
                remaining = remaining[room:]
            if remaining:
                # Ne peut pas arriver par arithmetique (`rows` est un arrondi par exces
                # sur toutes les colonnes), mais le silence serait une ligne technique
                # **perdue**, et l'AC 5 interdit d'en supprimer aucune.
                raise GeometryOverflowError(
                    f"{len(remaining)} ligne(s) technique(s) ne tiennent dans aucune "
                    f"colonne du pied de page ({len(technical_zones)} colonnes de "
                    f"{rows} rangees): {remaining}."
                )
            blocks.append(
                TextBlock(name="footer_block", rect_mm=footer_rect,
                          font_pt=BODY_FONT_MIN_PT, lines=tuple(identity_lines))
            )
            for name, lines in zip(technical_zones, columns):
                blocks.append(
                    TextBlock(name=name, rect_mm=zones_mm[name],
                              font_pt=BODY_FONT_MIN_PT, lines=tuple(lines))
                )
        else:
            date_slot = ("footer_block", len(identity_lines))
            blocks.append(
                TextBlock(
                    name="footer_block",
                    rect_mm=footer_rect,
                    font_pt=BODY_FONT_MIN_PT,
                    lines=tuple(identity_lines)
                    + _pack_lines(technical_parts, footer_rect[2], BODY_FONT_MIN_PT),
                )
            )
        line_rect = zones_mm["footer_line"]
        blocks.append(
            TextBlock(
                name="footer_line",
                rect_mm=line_rect,
                font_pt=BODY_FONT_MIN_PT,
                lines=(fit_text(scan_instruction, line_rect[2], BODY_FONT_MIN_PT),),
            )
        )
        # Tenue verticale (revue 4.2: "ca tenait par chance, pas par contrat"):
        # chaque bloc doit loger toutes ses lignes -- plus la ligne de
        # date-heure que le rendu ajoute (EPIC4-ARB-8) -- dans la hauteur de sa
        # zone, a l'interligne du rendu. Le bloc qui recoit la date est celui que le
        # plan **declare**, et non plus le bloc d'identite par convention: la compter
        # au mauvais endroit reserverait une ligne dans une zone qui n'en a pas besoin
        # et pas dans celle ou le rendu ecrit vraiment.
        for block in blocks:
            line_count = len(block.lines)
            if block.name == date_slot[0]:
                line_count += 1  # ligne "genere le ..." inseree au rendu
            needed = line_count * line_leading_mm(block.font_pt)
            if needed > block.rect_mm[3] + 1e-9:
                raise GeometryOverflowError(
                    f"Le bloc de texte '{block.name}' ({line_count} ligne(s) a "
                    f"{block.font_pt:.0f} pt) exige {needed:.1f} mm pour "
                    f"{block.rect_mm[3]:.1f} mm disponibles. Raccourcir les "
                    "identifiants ou reduire le contenu technique."
                )

        text = PageTextPlan(
            sheet_label=sheet_label,
            project_id=project_id,
            rush_id=rush_id,
            page_number_text=page_number_text,
            fps_display=fps_display,
            scan_instruction=scan_instruction,
            technical_footer=technical_footer,
            zones_mm=zones_mm,
            blocks=tuple(blocks),
            slot_labels=tuple(slot_labels),
            date_line_slot=date_slot,
        )
        pages.append(
            PagePlan(
                page_index=page_index,
                template_id=template_id,
                frames=tuple(slot_plans),
                qr=qr_plan,
                markers=markers,
                patches=patches,
                text=text,
            )
        )

    # **Aucune insertion de page de calibration ici** (story 5.22, `EPIC5-ARB-80`
    # decision 7). Le geste est devenu explicite: `compose_calibration_page_plan` rend la
    # page seule, a la demande, une fois par **chaine de scan** et non une fois par lot.
    #
    # Ce n'est pas un retrait de fonctionnalite mais un deplacement de proprietaire, et le
    # motif est mesure: inserer la page dans chaque lot faisait ajuster la correction a la
    # volee sur **chaque** scan, si bien qu'une feuille reposee autrement derivait au-dela
    # du seuil `color-divergence-1` et etait refusee -- alors que la chaine et le scanner
    # etaient les memes. C'est exactement le refus que subissaient les trois captures de
    # `projects/chendj-mat/scans/`.

    return LotComposition(
        project_id=project_id,
        rush_id=rush_id,
        lot_id=lot_id,
        fps_target=float(fps_target),
        page_format=page_format,
        orientation=orientation,
        frames_per_page=frames_per_page,
        margin_preset=margin_preset,
        template_id=template_id,
        patch_preset_id=patch_preset_id,
        gamut_map_id=gamut_map_id,
        render_dpi=render_dpi,
        scan_dpi=qr_codes.QR_MIN_SCAN_DPI,
        frames_dir=str(frames_dir),
        pdf_filename=naming.build_sheets_pdf_filename(
            project_id, rush_id, lot_id, version_rank=version_rank,
            # Le `template_id` DEJA resolu par `_resolve_parameters`, jamais un
            # second calcul : le nom suit le gabarit qui a produit les pages
            # (`EPIC11-ARB-171`, AC 2.9a).
            template_id=template_id),
        page_count=page_count,
        pages=tuple(pages),
        warnings=tuple(lot_warnings),
    )
