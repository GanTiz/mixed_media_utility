"""Cible de mesure terrain: une planche a imprimer, scanner, puis mesurer.

Elle repond en **une seule impression** aux quatre chantiers de
`analyse-2026-08-08-empreinte-disque-et-templates.md` qui n'avancent pas sans
papier (`EPIC5-ARB-43`):

* **chantier 5** -- taille de marqueur minimale et largeur de zone de silence
  minimale. C'est le plus gros gain identifie de l'analyse (+86 % de surface
  d'image), et il est entierement suspendu a une mesure que personne n'a faite;
* **chantier 8** -- mire de degrades. Le corpus de fixtures ne contient que des
  aplats: rien dans le depot ne permet aujourd'hui de constater ce que la chaine
  fait d'un degrade subtil, ce qui est nommement le risque R9 du `TEST_PLAN`;
* **chantier 9** -- tramage de la conversion 16 -> 8 bits. La planche porte les
  degrades **en double**, tronques et trames depuis la meme source 16 bits, cote
  a cote: c'est la comparaison qui decide, et elle n'existait pas;
* **chantier 10** -- taille de pastille minimale, qui commande le preset de
  placement resserre.

Elle repond aussi, en passant, au **chantier 11** (QR ramene de 35 a 31,5 mm):
quatre tailles imprimees, a decoder au scan.

Ce que cette planche **n'est pas**
----------------------------------
**Ce n'est pas une sortie de `makepdf`, et elle ne doit pas etre passee a
`scan`.** Elle ne porte ni payload de lot, ni `template_id`, ni frames: la
commande `scan` la refuserait, et elle aurait raison. Les marqueurs de test
portent des identifiants hors des plages reservees de la story 4.3, ce qui
declencherait `FOREIGN_MARKER_DETECTED` sur le chemin de production. C'est une
**cible de recherche**, analysee par un script dedie.

Ce qu'elle garantit pour etre analysable
----------------------------------------
Chaque page porte les **quatre marqueurs de coin de production** -- ID 0 a 3,
30 mm, aux positions de `layout.corner_marker_centers_mm()` -- pour que la page
scannee se redresse par `detection.aruco.compute_page_homography`, exactement
comme une planche reelle. Tout le reste est place en millimetres dans ce repere.

Et le script ecrit un **descripteur JSON** a cote du PDF: la position nominale en
millimetres et les parametres de **chaque** element. L'analyse lit donc les
positions au lieu de les deviner -- meme regle que la deuxieme precondition LUT
(« jamais a des positions devinees »).

Lancer:
    PYTHONPATH=src python3 scripts/research/build_measurement_target.py \
        --out temp/cible_de_mesure

Produit `<out>.pdf` (a imprimer) et `<out>.json` (a garder avec le scan).
"""

# --- Story 5.17: aucun effet sur cette cible --------------------------------
#
# La charge utile des quatre QR de cette planche est **de synthese** (voir
# `_qr_sizes`): `{"cible": ..., "bourrage": ...}`, dimensionnee a la longueur nominale
# mesuree par la story 4.6, et jamais le payload de production. Le passage du schema de
# payload a `2.0` (story 5.17, `EPIC5-ARB-60`) ne change donc ni cette planche, ni son
# descripteur, ni son depouillement. `NOMINAL_BUDGET_BYTES` est lu comme une longueur
# cible, pas comme un contrat de champs.

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as rl_canvas

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from mixed_media_utility import layout, patch_presets, patch_values, qr_codes  # noqa: E402

#: DPI de fabrication du raster. 600 est la consigne de scan du produit
#: (`qr_codes.QR_MIN_SCAN_DPI`): fabriquer plus fin ne servirait qu'a etre
#: reechantillonne par l'imprimante.
RENDER_DPI = 600

#: Identifiants des marqueurs de **test**. Hors des plages reservees de la story
#: 4.3 (coins 0-3, variantes 10-19, emplacements 20-49) a dessein: cette planche
#: ne doit pas pouvoir etre confondue avec une planche de production, et un
#: marqueur de test qui atterrirait sur le chemin de scan doit ressortir
#: `FOREIGN_MARKER_DETECTED` plutot que d'etre pris pour un coin.
TEST_MARKER_FIRST_ID = 60

#: Echelle de tailles de marqueur, en millimetres. 30 est la taille de
#: production: elle sert de temoin, et une mesure ou elle echouerait invaliderait
#: le tirage plutot que le produit.
MARKER_SIZES_MM = (30.0, 24.0, 20.0, 16.0, 13.0, 10.0)

#: Echelle de zones de silence, en millimetres, mesuree sur un marqueur de
#: taille fixe. 15 est la valeur de production (`layout.MARKER_QUIET_ZONE_MM`).
QUIET_ZONE_PROBE_MARKER_MM = 20.0
QUIET_ZONES_MM = (15.0, 10.0, 6.0, 3.0, 1.5)

#: Echelle de tailles de pastille. 12 est la taille de production
#: (`patch_presets.PATCH_SIZE_MM`), 6 est la cible du chantier 10.
PATCH_SIZES_MM = (12.0, 10.0, 8.0, 6.0, 5.0, 4.0, 3.0)

#: Deux valeurs seulement, et choisies: une neutre de milieu d'echelle, ou la
#: mesure est la plus stable, et une saturee, ou l'ecretage se voit. Mesurer les
#: dix-huit valeurs a sept tailles ne tiendrait pas sur la page et n'ajouterait
#: rien: la question du chantier 10 est « a partir de quelle taille la mesure
#: devient instable », pas « quelle couleur ».
PATCH_PROBE_VALUE_IDS = ("neutral-110", "primary-red")

#: Tailles de QR a eprouver. 35 est la cible de production
#: (`qr_codes.QR_PRINT_SIZE_TARGET_MM`), 31,5 la valeur que le chantier 11 veut
#: valider, 30 le repli documente, 25 un echec attendu qui borne la mesure.
QR_SIZES_MM = (35.0, 31.5, 30.0, 25.0)

#: Graine du tramage. Fixe et **documentee**: le tramage du chantier 9 doit etre
#: deterministe (point 1 de D.2, « graine derivee de donnees du plan, jamais
#: d'horloge »). Ici il n'y a pas de plan, donc la graine est une constante de ce
#: banc. Deux fabrications rendent alors le meme **raster**, ce qui est la
#: propriete qui compte pour comparer deux tirages. Attention: les **octets du
#: PDF**, eux, differeront -- reportlab y ecrit une `/CreationDate` et un `/ID`
#: aleatoire. Verifie le 2026-08-10: rasters identiques, PDF de tailles
#: differentes. Ne pas comparer deux cibles par le condensat de leur PDF.
DITHER_SEED = 20260810

_WHITE = 255
_INK = 0
_LABEL_SCALE = 0.9
_LABEL_THICKNESS = 2


def _blank_page() -> np.ndarray:
    width_px, height_px = layout.page_size_px(RENDER_DPI)
    return np.full((height_px, width_px, 3), _WHITE, dtype=np.uint8)


def _px(x_mm: float, y_mm: float) -> tuple[int, int]:
    return layout.mm_to_px(x_mm, y_mm, RENDER_DPI)


def _side_px(size_mm: float) -> int:
    return layout.mm_to_px(size_mm, size_mm, RENDER_DPI)[0]


#: Bande utile, en millimetres: sous les marqueurs de coin du haut et au-dessus
#: de ceux du bas. Derivee de `layout`, jamais ecrite en dur -- une cible qui
#: recouvrirait un coin ne pourrait plus etre redressee, et le symptome serait
#: une mesure fausse plutot qu'une erreur.
CONTENT_LEFT_MM = layout.MARKER_MARGIN_MM + 1.0
CONTENT_RIGHT_MM = layout.PAGE_WIDTH_MM - layout.MARKER_MARGIN_MM - 1.0
CONTENT_TOP_MM = layout.MARKER_MARGIN_MM + layout.MARKER_SIZE_MM + 8.0
CONTENT_BOTTOM_MM = (
    layout.PAGE_HEIGHT_MM - layout.MARKER_MARGIN_MM - layout.MARKER_SIZE_MM - 8.0
)


class TargetLayoutError(RuntimeError):
    """La cible ne tient pas dans la bande utile de la page.

    Levee **a la fabrication** plutot que laissee a un `ValueError` de
    diffusion numpy: le message nomme l'element et sa position, ce qu'un
    « could not broadcast input array » ne fait pas. Une cible de mesure qui
    deborderait silencieusement mesurerait le debordement.
    """


def _paste_gray(
    page: np.ndarray, raster: np.ndarray, x_mm: float, y_mm: float, *, what: str
) -> None:
    x_px, y_px = _px(x_mm, y_mm)
    if raster.ndim == 2:
        raster = cv2.cvtColor(raster, cv2.COLOR_GRAY2BGR)
    height, width = raster.shape[:2]
    page_h, page_w = page.shape[:2]
    if x_px < 0 or y_px < 0 or x_px + width > page_w or y_px + height > page_h:
        raise TargetLayoutError(
            f"{what} deborde la page: pose a ({x_mm:.1f}, {y_mm:.1f}) mm, "
            f"{width}x{height} px dans une page de {page_w}x{page_h} px."
        )
    page[y_px : y_px + height, x_px : x_px + width] = raster


def _label(page: np.ndarray, text: str, x_mm: float, y_mm: float) -> None:
    x_px, y_px = _px(x_mm, y_mm)
    cv2.putText(
        page, text, (x_px, y_px), cv2.FONT_HERSHEY_SIMPLEX,
        _LABEL_SCALE, (_INK, _INK, _INK), _LABEL_THICKNESS, cv2.LINE_AA,
    )


def _draw_corner_markers(page: np.ndarray, elements: list[dict]) -> None:
    """Les quatre marqueurs de coin de production, pour que la page se redresse.

    Positions et taille lues de `layout`, jamais reecrites: une cible dont les
    coins ne seraient pas exactement ceux de la production ne pourrait pas etre
    redressee par le code de production, et mesurerait alors le script au lieu de
    mesurer le papier.
    """
    half = layout.MARKER_SIZE_MM / 2
    side_px = _side_px(layout.MARKER_SIZE_MM)
    for marker_id, (cx_mm, cy_mm) in layout.corner_marker_centers_mm().items():
        raster = layout.generate_aruco_marker_image(marker_id, side_px)
        _paste_gray(page, raster, cx_mm - half, cy_mm - half, what=f"coin {marker_id}")
        elements.append({
            "kind": "corner_marker",
            "marker_id": marker_id,
            "size_mm": layout.MARKER_SIZE_MM,
            "x_mm": cx_mm - half,
            "y_mm": cy_mm - half,
        })


def _draw_marker_size_ladder(
    page: np.ndarray, elements: list[dict], next_id: int, y_mm: float
) -> tuple[int, float]:
    """Echelle de tailles, chacune avec une zone de silence large et constante.

    La zone de silence est tenue **genereuse et identique** pour toutes: sans
    cela, la taille et la marge varieraient ensemble et la mesure ne dirait
    laquelle des deux a fait echouer la detection. C'est la faute que la revue de
    4.3 avait relevee sur le premier banc synthetique (« mm et DPI etaient le
    meme axe »).
    """
    _label(page, "A. TAILLE DE MARQUEUR (zone de silence large et constante)", CONTENT_LEFT_MM, y_mm)
    y_mm += 7.0
    gap_mm = 10.0
    x_mm = CONTENT_LEFT_MM + 1.0
    row_top = y_mm
    row_height = max(MARKER_SIZES_MM) + 13.0
    for size_mm in MARKER_SIZES_MM:
        if x_mm + size_mm > CONTENT_RIGHT_MM:
            x_mm = CONTENT_LEFT_MM + 1.0
            row_top += row_height
        raster = layout.generate_aruco_marker_image(next_id, _side_px(size_mm))
        _paste_gray(page, raster, x_mm, row_top, what=f"marqueur de test {size_mm:g}mm")
        _label(page, f"{size_mm:g}mm", x_mm, row_top + max(MARKER_SIZES_MM) + 5.0)
        elements.append({
            "kind": "marker_size_probe",
            "marker_id": next_id,
            "size_mm": size_mm,
            "x_mm": x_mm,
            "y_mm": row_top,
            "quiet_zone_mm": gap_mm,
        })
        next_id += 1
        x_mm += size_mm + gap_mm
    return next_id, row_top + row_height


def _draw_quiet_zone_ladder(
    page: np.ndarray, elements: list[dict], next_id: int, y_mm: float
) -> tuple[int, float]:
    """Echelle de zones de silence, a taille de marqueur constante.

    L'encre qui empiete est une barre noire pleine posee sur **les quatre cotes**
    a la distance visee. Sur un seul cote, la mesure dirait « de ce cote-la »: la
    contamination reelle d'une planche dense vient de partout a la fois, et c'est
    ce que la marge de production protege.
    """
    _label(
        page,
        f"B. ZONE DE SILENCE (marqueur {QUIET_ZONE_PROBE_MARKER_MM:g}mm constant, encre a distance d)",
        CONTENT_LEFT_MM, y_mm,
    )
    y_mm += 7.0
    size_mm = QUIET_ZONE_PROBE_MARKER_MM
    # 4 mm et non un filet fin: la contamination que la marge de production
    # protege vient de pastilles de 12 mm de cote, pas d'un trait. Un filet
    # trop fin mesurerait une contamination que la planche reelle ne produit
    # jamais, et rendrait un seuil optimiste.
    bar_mm = 4.0
    x_mm = CONTENT_LEFT_MM + 1.0
    row_top = y_mm
    # Hauteur de rangee dimensionnee sur le **pire** cas (la plus large zone),
    # pour que toutes les cellules d'une rangee soient alignees.
    row_height = size_mm + 2 * (max(QUIET_ZONES_MM) + bar_mm) + 11.0
    for zone_mm in QUIET_ZONES_MM:
        cell_mm = size_mm + 2 * (zone_mm + bar_mm) + 6.0
        if x_mm + cell_mm > CONTENT_RIGHT_MM:
            x_mm = CONTENT_LEFT_MM + 1.0
            row_top += row_height
        # Le marqueur est centre dans sa cellule, la cellule etant dimensionnee
        # par la zone visee: c'est la zone qui varie, jamais la taille.
        marker_x = x_mm + zone_mm + bar_mm + 3.0
        marker_y = row_top + max(QUIET_ZONES_MM) + bar_mm
        raster = layout.generate_aruco_marker_image(next_id, _side_px(size_mm))
        _paste_gray(page, raster, marker_x, marker_y, what=f"sonde de zone d={zone_mm:g}mm")
        # Cadre d'encre a `zone_mm` du bord du marqueur, sur les quatre cotes.
        thickness_px = max(1, layout.mm_to_px(bar_mm, 0, RENDER_DPI)[0])
        x0, y0 = _px(marker_x - zone_mm - bar_mm / 2, marker_y - zone_mm - bar_mm / 2)
        x1, y1 = _px(
            marker_x + size_mm + zone_mm + bar_mm / 2,
            marker_y + size_mm + zone_mm + bar_mm / 2,
        )
        cv2.rectangle(page, (x0, y0), (x1, y1), (_INK, _INK, _INK), thickness_px)
        _label(page, f"d={zone_mm:g}", x_mm, row_top + row_height - 4.0)
        elements.append({
            "kind": "quiet_zone_probe",
            "marker_id": next_id,
            "size_mm": size_mm,
            "x_mm": marker_x,
            "y_mm": marker_y,
            "quiet_zone_mm": zone_mm,
            "ink_bar_mm": bar_mm,
        })
        next_id += 1
        x_mm += cell_mm
    return next_id, row_top + row_height


def _draw_qr_ladder(page: np.ndarray, elements: list[dict], y_mm: float,
                    sizes: tuple[float, ...] = QR_SIZES_MM) -> float:
    """Quatre tailles de QR, sur un payload de longueur realiste.

    Le payload est fabrique a la **longueur nominale mesuree** par la story 4.6
    (`NOMINAL_BUDGET_BYTES`), et non court: un QR court encode moins de modules,
    donc davantage de pixels par module a taille imprimee egale, et la mesure
    serait optimiste.
    """
    from mixed_media_utility.io.payload import NOMINAL_BUDGET_BYTES

    filler = "M" * (NOMINAL_BUDGET_BYTES - 40)
    payload = json.dumps({"cible": "mesure-2026-08-10", "bourrage": filler})
    native = qr_codes.encode_qr_image(payload)
    module_side = int(native.shape[0])
    _label(page, f"C. QR ({len(payload)} octets, {module_side} modules)", CONTENT_LEFT_MM, y_mm)
    y_mm += 7.0
    # Retour a la ligne, comme les echelles de marqueur: la v2 porte six tailles
    # et la premiere redaction, ecrite pour quatre, debordait de la page.
    cell_mm = max(sizes) + 6.0
    # 16 et non 18: sans retour a la ligne, `row_top + row_height` doit valoir
    # exactement l'ancien `y_mm + max(sizes) + 16.0`. La v1 a ete **imprimee et
    # scannee**, et son descripteur commite decrit ce tirage: ajouter le retour a
    # la ligne pour la v2 ne doit pas deplacer d'un millimetre ce qui suit
    # l'echelle QR sur la v1, sinon l'analyse du scan deja fait viserait a cote.
    # Verifie: descripteur v1 identique avant / apres.
    row_height = max(sizes) + 16.0
    x_mm, row_top = CONTENT_LEFT_MM + 1.0, y_mm
    for size_mm in sizes:
        if x_mm + cell_mm > CONTENT_RIGHT_MM:
            x_mm, row_top = CONTENT_LEFT_MM + 1.0, row_top + row_height
        raster = qr_codes.render_for_print(native, size_mm, RENDER_DPI)
        _paste_gray(page, raster, x_mm, row_top, what=f"QR {size_mm:g}mm")
        ratio = qr_codes.pixels_per_module(module_side, size_mm, RENDER_DPI)
        _label(page, f"{size_mm:g}mm", x_mm, row_top + max(sizes) + 6.0)
        _label(page, f"{ratio:.2f}px/mod", x_mm, row_top + max(sizes) + 11.0)
        elements.append({
            "kind": "qr_probe",
            "size_mm": size_mm,
            "x_mm": x_mm,
            "y_mm": row_top,
            "module_side": module_side,
            "payload_bytes": len(payload),
            "pixels_per_module_at_600dpi": ratio,
            "payload_text": payload,
        })
        x_mm += cell_mm
    return row_top + row_height


def _draw_patch_size_ladder(page: np.ndarray, elements: list[dict], y_mm: float) -> float:
    """Tailles de pastille decroissantes, valeurs lues de la table versionnee."""
    table = patch_values.active_table()
    _label(page, f"D. TAILLE DE PASTILLE (valeurs de {table.version})", CONTENT_LEFT_MM, y_mm)
    y_mm += 7.0
    for value_id in PATCH_PROBE_VALUE_IDS:
        rgb = table.get(value_id).rgb
        bgr = (int(rgb[2]), int(rgb[1]), int(rgb[0]))
        _label(page, value_id, CONTENT_LEFT_MM, y_mm + 5.0)
        x_mm = CONTENT_LEFT_MM + 38.0
        for size_mm in PATCH_SIZES_MM:
            x0, y0 = _px(x_mm, y_mm)
            x1, y1 = _px(x_mm + size_mm, y_mm + size_mm)
            cv2.rectangle(page, (x0, y0), (x1 - 1, y1 - 1), bgr, -1)
            _label(page, f"{size_mm:g}", x_mm, y_mm + max(PATCH_SIZES_MM) + 5.0)
            elements.append({
                "kind": "patch_size_probe",
                "value_id": value_id,
                "values_version": table.version,
                "reference_rgb": list(rgb),
                "size_mm": size_mm,
                "x_mm": x_mm,
                "y_mm": y_mm,
            })
            x_mm += size_mm + 6.0
        y_mm += max(PATCH_SIZES_MM) + 10.0
    return y_mm + 4.0


def _ramp16(width_px: int, low: int, high: int) -> np.ndarray:
    """Rampe horizontale 16 bits, lineaire en valeur codee."""
    return np.linspace(low * 257, high * 257, width_px, dtype=np.float64)


def _quantise_truncate(ramp16: np.ndarray) -> np.ndarray:
    """Ce que la chaine fait aujourd'hui: `>> 8` (`pdf_render.py:99-100`)."""
    return (ramp16.astype(np.uint16) >> 8).astype(np.uint8)


def _quantise_dither(ramp16: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Ce que le chantier 9 propose: TPDF de +/-1 LSB avant quantification.

    TPDF -- triangulaire, obtenu par la somme de deux uniformes -- et non un
    tramage ordonne (Bayer), qui laisse un motif regulier visible sur les
    aplats: la page en porte, et c'est le point 2 de D.2.
    """
    value_8bit = ramp16 / 257.0
    noise = rng.random(value_8bit.shape) - rng.random(value_8bit.shape)
    return np.clip(np.round(value_8bit + noise), 0, 255).astype(np.uint8)


def _draw_gradient_ramps(page: np.ndarray, elements: list[dict], y_mm: float) -> float:
    """Quatre bandes: deux amplitudes x (tronque, trame). C'est la comparaison.

    Les rampes sont **appariees**: meme source 16 bits, deux quantifications.
    Une seule bande ne dirait rien -- le contouring ne se juge pas dans l'absolu
    mais contre l'autre traitement, a l'oeil comme a la mesure.
    """
    _label(page, "E. DEGRADES: tronque (>>8) vs trame TPDF, meme source 16 bits", CONTENT_LEFT_MM, y_mm)
    y_mm += 7.0
    band_w_mm = CONTENT_RIGHT_MM - CONTENT_LEFT_MM - 2.0
    band_h_mm = 14.0
    width_px = layout.mm_to_px(band_w_mm, 0, RENDER_DPI)[0]
    height_px = layout.mm_to_px(0, band_h_mm, RENDER_DPI)[1]
    rng = np.random.default_rng(DITHER_SEED)
    # Trois amplitudes, et la troisieme n'est pas decorative: le contouring est
    # le plus visible dans les **ombres**, ou l'oeil discrimine le mieux et ou le
    # pas de quantification est relativement le plus grand. Une mesure qui ne
    # porterait que sur la pleine echelle et un milieu d'echelle conclurait au
    # mieux sur la moitie du probleme.
    for low, high, span_label in ((0, 255, "0-255"), (96, 128, "96-128"), (16, 48, "16-48")):
        ramp = _ramp16(width_px, low, high)
        for mode in ("tronque", "trame"):
            row = (
                _quantise_truncate(ramp) if mode == "tronque"
                else _quantise_dither(ramp, rng)
            )
            band = np.repeat(row[None, :], height_px, axis=0)
            _paste_gray(page, band, CONTENT_LEFT_MM + 1.0, y_mm,
                        what=f"degrade {span_label} {mode}")
            _label(page, f"{span_label} {mode}", CONTENT_LEFT_MM + 1.0, y_mm + band_h_mm + 5.0)
            elements.append({
                "kind": "gradient_ramp",
                "span": span_label,
                "low_8bit": low,
                "high_8bit": high,
                "quantisation": mode,
                "dither_seed": DITHER_SEED if mode == "trame" else None,
                "x_mm": CONTENT_LEFT_MM + 1.0,
                "y_mm": y_mm,
                "width_mm": band_w_mm,
                "height_mm": band_h_mm,
            })
            y_mm += band_h_mm + 8.0
        y_mm += 3.0
    return y_mm


def _footer(page: np.ndarray, page_number: int, page_count: int) -> None:
    _label(page, f"Cible de mesure terrain -- page {page_number}/{page_count} -- "
                 f"NE PAS passer a scan -- scanner a {qr_codes.QR_MIN_SCAN_DPI} dpi",
           CONTENT_LEFT_MM, CONTENT_BOTTOM_MM + 5.0)


#: Trois pages, et non deux. La premiere redaction en tenait deux et la
#: deuxieme debordait: les echelles de marqueur et de zone de silence occupent a
#: elles seules presque toute la bande utile d'une A4, la zone de silence de
#: production faisant 15 mm **de chaque cote** d'un marqueur. Une page par
#: famille de mesure coute deux feuilles de plus et rend chaque page lisible.
PAGE_COUNT = 3


def build_pages() -> tuple[list[np.ndarray], list[dict]]:
    """Trois pages, une par famille de mesure, chacune redressable seule.

    Chaque page porte ses quatre coins de production: une page perdue ou
    rescannee seule reste exploitable, ce qui n'est pas un detail sur une cible
    qu'un operateur manipule a la main.
    """
    pages: list[np.ndarray] = []
    descriptor: list[dict] = []
    next_id = TEST_MARKER_FIRST_ID

    # Page 1 -- marqueurs: taille, puis zone de silence.
    page = _blank_page()
    elements: list[dict] = []
    _draw_corner_markers(page, elements)
    next_id, y = _draw_marker_size_ladder(page, elements, next_id, CONTENT_TOP_MM)
    next_id, _y = _draw_quiet_zone_ladder(page, elements, next_id, y + 4.0)
    _footer(page, 1, PAGE_COUNT)
    pages.append(page)
    descriptor.append({"page_index": 0, "elements": elements})

    # Page 2 -- QR, puis tailles de pastille.
    page = _blank_page()
    elements = []
    _draw_corner_markers(page, elements)
    y = _draw_qr_ladder(page, elements, CONTENT_TOP_MM)
    _draw_patch_size_ladder(page, elements, y + 4.0)
    _footer(page, 2, PAGE_COUNT)
    pages.append(page)
    descriptor.append({"page_index": 1, "elements": elements})

    # Page 3 -- degrades appaires. Seule sur sa page: c'est la comparaison qui
    # se lit a l'oeil, et un voisinage charge la parasiterait.
    page = _blank_page()
    elements = []
    _draw_corner_markers(page, elements)
    _draw_gradient_ramps(page, elements, CONTENT_TOP_MM)
    _footer(page, 3, PAGE_COUNT)
    pages.append(page)
    descriptor.append({"page_index": 2, "elements": elements})

    return pages, descriptor


# ---------------------------------------------------------------------------
# Variante 2 -- corrige les deux limites de la v1 et anticipe quatre mesures
# ---------------------------------------------------------------------------
#
# La v1 a rendu ses mesures le 2026-08-10 (`analyse-2026-08-10-campagne-terrain.md`)
# et laisse deux trous, dont un est **ma faute**:
#
# * ses echelles de marqueur et de zone de silence **passent entierement**: elles
#   prouvent que la production est surdimensionnee, mais ne trouvent aucune
#   frontiere. La v2 descend a 4 mm et a 0 mm;
# * son echelle de tailles de pastille pose les tailles **par ordre decroissant
#   de gauche a droite**, donc taille et position en x sont parfaitement
#   correlees et la mesure ne peut pas les separer -- exactement la faute que la
#   regle des fabriques du `CLAUDE.md` decrit. La v2 **entrelace** l'ordre et
#   **repete chaque taille a deux positions eloignees**: la repetition donne en
#   plus le bruit propre a chaque taille.
#
# Et parce que c'est le dernier tirage disponible, elle anticipe trois mesures que
# rien ne permettrait de rattraper apres coup:
#
# * un **troisieme echantillon de dE76** -- les 18 valeurs de `patch-values-2` a
#   la taille de production, deux fois. `deferred-work.md` en demandait trois
#   tirages, il y en a deux;
# * des **echelons intermediaires** sur le vert et le bleu, dont le verdict
#   d'ecretage etait marginal (2,54 et 2,94 pour un seuil de 2,58);
# * une **echelle de tons a 16 marches**, qui dit si l'etage A d'`EPIC5-ARB-26`
#   -- un gain et un decalage par canal, six parametres -- suffit a decrire la
#   courbe de transfert du papier. Le residu de `neutral-110` a 7,22 dE76 sur la
#   planche de caracterisation suggere que non, et quatre points d'axe neutre ne
#   permettent pas de le savoir.

MARKER_SIZES_MM_V2 = (30.0, 20.0, 12.0, 8.0, 6.0, 5.0, 4.0)
QUIET_ZONES_MM_V2 = (15.0, 6.0, 3.0, 1.5, 1.0, 0.5, 0.0)
QR_SIZES_MM_V2 = (35.0, 31.5, 25.0, 22.0, 20.0, 18.0)

#: Ordre **entrelace** des tailles de pastille, et sa repetition en ordre
#: different. C'est le coeur du correctif: aucune taille ne garde le meme rang en
#: x d'une rangee a l'autre, donc un effet de position se separe d'un effet de
#: taille.
PATCH_SIZE_ORDER_A = (12.0, 4.0, 8.0, 3.0, 10.0, 5.0, 6.0)
PATCH_SIZE_ORDER_B = (6.0, 5.0, 10.0, 3.0, 8.0, 4.0, 12.0)

#: Echelons intermediaires vert et bleu, **valeurs de recherche** et non entrees
#: de table: elles ne sont pas dans `patch-values-2` et n'y entreront pas sans une
#: `patch-values-3`. Placees a mi-chemin des deux sentinelles de leur axe, la ou
#: la v1 mesurait 2,54 (vert) et 2,94 (bleu) -- de part et d'autre du seuil.
INTERMEDIATE_SENTINELS = (
    ("green-1b", (12, 230, 17)),
    ("blue-1b", (10, 20, 230)),
)

#: Echelle de tons: 16 marches de 0 a 255. Seize et non vingt-et-une pour tenir en
#: deux rangees de huit a la taille de production (12 mm), la taille etant ici une
#: variable a ne pas changer -- c'est la courbe qu'on mesure, pas la taille.
TONE_WEDGE_STEPS = 16


def _draw_marker_ladders_v2(
    page: np.ndarray, elements: list[dict], next_id: int, y_mm: float
) -> tuple[int, float]:
    """Les deux echelles de la v1, poussees jusqu'a la frontiere.

    `d = 0` est de la partie: l'encre touche le marqueur. C'est la borne
    inferieure absolue, et une mesure qui la passerait dirait que la zone de
    silence ne sert a rien -- resultat surprenant, donc a mesurer plutot qu'a
    supposer.
    """
    _label(page, "A. TAILLE DE MARQUEUR -- echelle poussee (v1: tout passait jusqu'a 10mm)",
           CONTENT_LEFT_MM, y_mm)
    y_mm += 7.0
    gap_mm = 10.0
    x_mm = CONTENT_LEFT_MM + 1.0
    row_top = y_mm
    row_height = max(MARKER_SIZES_MM_V2) + 13.0
    for size_mm in MARKER_SIZES_MM_V2:
        if x_mm + size_mm > CONTENT_RIGHT_MM:
            x_mm = CONTENT_LEFT_MM + 1.0
            row_top += row_height
        raster = layout.generate_aruco_marker_image(next_id, _side_px(size_mm))
        _paste_gray(page, raster, x_mm, row_top, what=f"marqueur v2 {size_mm:g}mm")
        _label(page, f"{size_mm:g}mm", x_mm, row_top + max(MARKER_SIZES_MM_V2) + 5.0)
        elements.append({
            "kind": "marker_size_probe", "marker_id": next_id, "size_mm": size_mm,
            "x_mm": x_mm, "y_mm": row_top, "quiet_zone_mm": gap_mm,
        })
        next_id += 1
        x_mm += size_mm + gap_mm
    y_mm = row_top + row_height

    _label(page, "B. ZONE DE SILENCE -- jusqu'a d=0 (v1: tout passait jusqu'a 1,5mm)",
           CONTENT_LEFT_MM, y_mm)
    y_mm += 7.0
    size_mm = QUIET_ZONE_PROBE_MARKER_MM
    bar_mm = 4.0
    x_mm = CONTENT_LEFT_MM + 1.0
    row_top = y_mm
    row_height = size_mm + 2 * (max(QUIET_ZONES_MM_V2) + bar_mm) + 11.0
    for zone_mm in QUIET_ZONES_MM_V2:
        cell_mm = size_mm + 2 * (zone_mm + bar_mm) + 6.0
        if x_mm + cell_mm > CONTENT_RIGHT_MM:
            x_mm = CONTENT_LEFT_MM + 1.0
            row_top += row_height
        marker_x = x_mm + zone_mm + bar_mm + 3.0
        marker_y = row_top + max(QUIET_ZONES_MM_V2) + bar_mm
        raster = layout.generate_aruco_marker_image(next_id, _side_px(size_mm))
        _paste_gray(page, raster, marker_x, marker_y, what=f"sonde v2 d={zone_mm:g}mm")
        thickness_px = max(1, layout.mm_to_px(bar_mm, 0, RENDER_DPI)[0])
        x0, y0 = _px(marker_x - zone_mm - bar_mm / 2, marker_y - zone_mm - bar_mm / 2)
        x1, y1 = _px(marker_x + size_mm + zone_mm + bar_mm / 2,
                     marker_y + size_mm + zone_mm + bar_mm / 2)
        cv2.rectangle(page, (x0, y0), (x1, y1), (_INK, _INK, _INK), thickness_px)
        _label(page, f"d={zone_mm:g}", x_mm, row_top + row_height - 4.0)
        elements.append({
            "kind": "quiet_zone_probe", "marker_id": next_id, "size_mm": size_mm,
            "x_mm": marker_x, "y_mm": marker_y, "quiet_zone_mm": zone_mm,
            "ink_bar_mm": bar_mm,
        })
        next_id += 1
        x_mm += cell_mm
    return next_id, row_top + row_height


def _draw_patch_size_ladder_v2(page: np.ndarray, elements: list[dict], y_mm: float) -> float:
    """Tailles **entrelacees**, chacune a deux positions eloignees.

    Deux rangees par valeur, d'ordres differents: la taille cesse d'etre une
    fonction de x. C'est ce qui permettra d'attribuer -- ou non -- l'ecart de
    26/255 mesure sur la v1 a la taille plutot qu'a la position.
    """
    table = patch_values.active_table()
    _label(page, "C. TAILLE DE PASTILLE -- ordres ENTRELACES, chaque taille deux fois",
           CONTENT_LEFT_MM, y_mm)
    y_mm += 7.0
    for value_id in PATCH_PROBE_VALUE_IDS:
        rgb = table.get(value_id).rgb
        bgr = (int(rgb[2]), int(rgb[1]), int(rgb[0]))
        for repeat, order in enumerate((PATCH_SIZE_ORDER_A, PATCH_SIZE_ORDER_B)):
            _label(page, f"{value_id} #{repeat + 1}", CONTENT_LEFT_MM, y_mm + 5.0)
            x_mm = CONTENT_LEFT_MM + 42.0
            for size_mm in order:
                x0, y0 = _px(x_mm, y_mm)
                x1, y1 = _px(x_mm + size_mm, y_mm + size_mm)
                if x1 > page.shape[1]:
                    raise TargetLayoutError(
                        f"pastille {value_id} {size_mm:g}mm hors page a x={x_mm:.1f}mm")
                cv2.rectangle(page, (x0, y0), (x1 - 1, y1 - 1), bgr, -1)
                _label(page, f"{size_mm:g}", x_mm, y_mm + max(PATCH_SIZES_MM) + 4.0)
                elements.append({
                    "kind": "patch_size_probe", "value_id": value_id,
                    "values_version": table.version, "reference_rgb": list(rgb),
                    "size_mm": size_mm, "x_mm": x_mm, "y_mm": y_mm, "repeat": repeat,
                })
                x_mm += size_mm + 6.0
            y_mm += max(PATCH_SIZES_MM) + 9.0
    return y_mm + 3.0


def _draw_production_patch_set(page: np.ndarray, elements: list[dict], y_mm: float) -> float:
    """Les 18 valeurs de `patch-values-2` a la taille de production, deux fois.

    But: faire de cette cible un **troisieme tirage** pour la calibration des
    seuils de `color-acceptance-1`, et un **second verdict d'ecretage**. La
    repetition n'est pas decorative -- c'est elle qui donne le bruit de mesure
    dont le seuil d'indiscernabilite est derive.
    """
    table = patch_values.active_table()
    values = list(table.adjustment_values()) + list(table.sentinel_values())
    _label(page, f"D. JEU COMPLET {table.version} a {patch_presets.PATCH_SIZE_MM:g}mm, deux fois "
                 f"({len(values)} valeurs) -- 3e tirage dE76 + 2e verdict d'ecretage",
           CONTENT_LEFT_MM, y_mm)
    y_mm += 7.0
    size_mm = patch_presets.PATCH_SIZE_MM
    step_mm = size_mm + 3.0
    per_row = int((CONTENT_RIGHT_MM - CONTENT_LEFT_MM - 2.0) // step_mm)
    for repeat in range(2):
        x_mm, row_top = CONTENT_LEFT_MM + 1.0, y_mm
        for index, value in enumerate(values):
            if index and index % per_row == 0:
                x_mm, row_top = CONTENT_LEFT_MM + 1.0, row_top + step_mm
            rgb = value.rgb
            x0, y0 = _px(x_mm, row_top)
            x1, y1 = _px(x_mm + size_mm, row_top + size_mm)
            cv2.rectangle(page, (x0, y0), (x1 - 1, y1 - 1),
                          (int(rgb[2]), int(rgb[1]), int(rgb[0])), -1)
            # La sentinelle blanche est indiscernable du papier: cadre interieur,
            # comme la story 5.9 l'impose a la production (son AC 5).
            if tuple(rgb) == (255, 255, 255):
                frame_px = max(1, layout.mm_to_px(1.0, 0, RENDER_DPI)[0])
                cv2.rectangle(page, (x0, y0), (x1 - 1, y1 - 1),
                              (_INK, _INK, _INK), frame_px)
            elements.append({
                "kind": "production_patch", "value_id": value.value_id,
                "values_version": table.version, "reference_rgb": list(rgb),
                "role": value.role, "size_mm": size_mm,
                "x_mm": x_mm, "y_mm": row_top, "repeat": repeat,
            })
            x_mm += step_mm
        y_mm = row_top + step_mm + 4.0

    _label(page, "E. ECHELONS INTERMEDIAIRES vert et bleu (valeurs de RECHERCHE, hors table)",
           CONTENT_LEFT_MM, y_mm)
    y_mm += 7.0
    x_mm = CONTENT_LEFT_MM + 1.0
    for name, rgb in INTERMEDIATE_SENTINELS:
        for repeat in range(2):
            x0, y0 = _px(x_mm, y_mm)
            x1, y1 = _px(x_mm + size_mm, y_mm + size_mm)
            cv2.rectangle(page, (x0, y0), (x1 - 1, y1 - 1),
                          (int(rgb[2]), int(rgb[1]), int(rgb[0])), -1)
            elements.append({
                "kind": "intermediate_sentinel", "value_id": name,
                "reference_rgb": list(rgb), "size_mm": size_mm,
                "x_mm": x_mm, "y_mm": y_mm, "repeat": repeat,
            })
            x_mm += step_mm
        x_mm += 6.0
    return y_mm + size_mm + 8.0


def _draw_tone_wedge(page: np.ndarray, elements: list[dict], y_mm: float) -> float:
    """Echelle de tons neutres: l'etage A a-t-il assez de parametres ?

    Seize marches a la taille de production. L'etage A d'`EPIC5-ARB-26` est un
    gain et un decalage par canal, ajustes sur **quatre** points d'axe neutre:
    cette echelle dit si une droite suffit a decrire la reponse du papier, ou s'il
    y faudrait une courbe. C'est une question sur la **forme** de la correction,
    et elle ne se tranche pas sans mesure.
    """
    _label(page, f"F. ECHELLE DE TONS -- {TONE_WEDGE_STEPS} marches neutres, "
                 "l'etage A (droite) suffit-il ?", CONTENT_LEFT_MM, y_mm)
    y_mm += 7.0
    size_mm = patch_presets.PATCH_SIZE_MM
    step_mm = size_mm + 3.0
    per_row = int((CONTENT_RIGHT_MM - CONTENT_LEFT_MM - 2.0) // step_mm)
    x_mm, row_top = CONTENT_LEFT_MM + 1.0, y_mm
    for index in range(TONE_WEDGE_STEPS):
        level = int(round(index * 255 / (TONE_WEDGE_STEPS - 1)))
        if index and index % per_row == 0:
            x_mm, row_top = CONTENT_LEFT_MM + 1.0, row_top + step_mm + 6.0
        x0, y0 = _px(x_mm, row_top)
        x1, y1 = _px(x_mm + size_mm, row_top + size_mm)
        cv2.rectangle(page, (x0, y0), (x1 - 1, y1 - 1), (level, level, level), -1)
        if level >= 250:
            frame_px = max(1, layout.mm_to_px(1.0, 0, RENDER_DPI)[0])
            cv2.rectangle(page, (x0, y0), (x1 - 1, y1 - 1), (_INK, _INK, _INK), frame_px)
        _label(page, f"{level}", x_mm, row_top + size_mm + 4.5)
        elements.append({
            "kind": "tone_wedge_step", "level_8bit": level, "size_mm": size_mm,
            "x_mm": x_mm, "y_mm": row_top,
        })
        x_mm += step_mm
    return row_top + step_mm + 8.0


PAGE_COUNT_V2 = 4


def build_pages_v2() -> tuple[list[np.ndarray], list[dict]]:
    pages: list[np.ndarray] = []
    descriptor: list[dict] = []
    next_id = TEST_MARKER_FIRST_ID

    page = _blank_page()
    elements: list[dict] = []
    _draw_corner_markers(page, elements)
    next_id, _y = _draw_marker_ladders_v2(page, elements, next_id, CONTENT_TOP_MM)
    _footer(page, 1, PAGE_COUNT_V2)
    pages.append(page)
    descriptor.append({"page_index": 0, "elements": elements})

    page = _blank_page()
    elements = []
    _draw_corner_markers(page, elements)
    y = _draw_qr_ladder(page, elements, CONTENT_TOP_MM, sizes=QR_SIZES_MM_V2)
    _draw_patch_size_ladder_v2(page, elements, y + 4.0)
    _footer(page, 2, PAGE_COUNT_V2)
    pages.append(page)
    descriptor.append({"page_index": 1, "elements": elements})

    page = _blank_page()
    elements = []
    _draw_corner_markers(page, elements)
    y = _draw_production_patch_set(page, elements, CONTENT_TOP_MM)
    _draw_tone_wedge(page, elements, y)
    _footer(page, 3, PAGE_COUNT_V2)
    pages.append(page)
    descriptor.append({"page_index": 2, "elements": elements})

    page = _blank_page()
    elements = []
    _draw_corner_markers(page, elements)
    _draw_gradient_ramps(page, elements, CONTENT_TOP_MM)
    _footer(page, 4, PAGE_COUNT_V2)
    pages.append(page)
    descriptor.append({"page_index": 3, "elements": elements})

    return pages, descriptor


def write_pdf(pages: list[np.ndarray], destination: Path) -> None:
    """Un raster pleine page par page, insere sans perte.

    PNG et non JPEG, et ce n'est pas un detail: une compression avec perte
    detruirait exactement ce que les bandes E mesurent. Le raster est fabrique a
    600 ppp et pose a la taille A4 exacte, donc sans reechantillonnage de notre
    cote.
    """
    temp_dir = destination.parent
    canvas = rl_canvas.Canvas(str(destination), pagesize=A4)
    written: list[Path] = []
    for index, page in enumerate(pages):
        png_path = temp_dir / f".{destination.stem}_p{index}.png"
        assert cv2.imwrite(str(png_path), page, [cv2.IMWRITE_PNG_COMPRESSION, 9])
        written.append(png_path)
        canvas.drawImage(str(png_path), 0, 0, width=A4[0], height=A4[1])
        canvas.showPage()
    canvas.save()
    for png_path in written:
        png_path.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", default="temp/cible_de_mesure",
        help="Chemin de sortie sans extension; produit <out>.pdf et <out>.json",
    )
    parser.add_argument(
        "--variant", type=int, choices=(1, 2), default=1,
        help="1: cible d'origine (3 pages, deja tiree le 2026-08-10); "
             "2: echelles poussees, tailles entrelacees, jeu complet et echelle de tons",
    )
    args = parser.parse_args(argv)

    base = Path(args.out)
    base.parent.mkdir(parents=True, exist_ok=True)
    pages, descriptor = build_pages_v2() if args.variant == 2 else build_pages()
    write_pdf(pages, base.with_suffix(".pdf"))
    base.with_suffix(".json").write_text(
        json.dumps(
            {
                "target": f"measurement-target-{args.variant}",
                "render_dpi": RENDER_DPI,
                "page_size_mm": [layout.PAGE_WIDTH_MM, layout.PAGE_HEIGHT_MM],
                "corner_marker_size_mm": layout.MARKER_SIZE_MM,
                "aruco_dictionary": layout.aruco_dictionary_name(),
                "scan_dpi_required": qr_codes.QR_MIN_SCAN_DPI,
                "pages": descriptor,
            },
            indent=1, sort_keys=True, ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )
    print(f"PDF ecrit: {base.with_suffix('.pdf')} ({len(pages)} pages)")
    print(f"Descripteur ecrit: {base.with_suffix('.json')}")
    print(f"Elements decrits: {sum(len(p['elements']) for p in descriptor)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
