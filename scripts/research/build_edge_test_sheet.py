"""Feuille de test des bords: la geometrie prudente a sa **vraie** position.

Origine : le dernier test qu'Egan a accepte d'imprimer. La feuille `candidat_gabarit`
du 2026-08-11 a valide la detection des marqueurs resserres 4/4 sur les deux pilotes de
scan -- mais sur des **pages virtuelles** encastrees au milieu de la feuille, a des
dizaines de millimetres de toute frontiere d'impression. Le montage etait necessaire
(un coin candidat a sa vraie position tombe dans l'emprise du coin de production et
l'ecrase), et sa limite etait consignee le jour meme :

> Ce qui est valide est « un marqueur de 15 mm avec 5 mm de silence est detecte ». Ce
> qui ne l'est pas est « un marqueur dont le bord exterieur est a 8 mm du bord physique
> s'imprime intact ».

Cette feuille teste la seconde affirmation, et **elle ne porte aucun coin de
production** : c'est ce qui libere les vraies positions. Consequence a assumer, elle
n'est pas redressable par le chemin de production tel quel -- ce n'est pas une planche,
c'est une eprouvette.

Ce qu'elle porte, et pourquoi chaque element est la
---------------------------------------------------
* **les quatre coins prudents a leur vraie position** (15 mm, marge 8 mm, ID 0-3) : le
  sujet du test. Leur bord exterieur est a 8 mm du bord physique, soit 3 mm de jeu sous
  la limite d'encre de 5 mm d'`EPIC4-ARB-6` ;
* **le QR a son emprise reelle** (38,3 mm silence ISO compris, le pire cardinal), pose
  dans la bande haute que la geometrie prudente laisse : le degagement du bord porteur
  est de 48,3 mm, chiffre mesure le 2026-08-11 apres correction d'une erreur de facteur
  trois. Il faut verifier qu'il se decode **a cette place et a cette taille** ;
* **les 18 pastilles temoins a 6 mm**, sur les bords haut et bas, a leur abscisse de
  production candidate : elles sont ce qui restera sur une planche d'images, et elles
  sont plus pres du bord que rien d'autre aujourd'hui ;
* **des sondes de reperage** (ID 60+) a des positions declarees, dont **quatre au plus
  pres des bords**. Sans coins de production, la seule facon de mesurer l'erreur de
  redressement est de confronter des points connus a leur position relue. Les sondes de
  bord sont celles qui mordent : une deformation de feuille est maximale aux
  extremites, et c'est exactement le regime que le montage a page virtuelle ne pouvait
  pas atteindre ;
* **des reperes de limite d'encre**, traits fins a exactement 5 mm de chaque bord.
  Ils repondent a une question qu'aucune mesure numerique ne peut poser : l'imprimante
  depose-t-elle vraiment de l'encre a 5 mm du bord, ou sa marge reelle est-elle plus
  large que ce qu'elle declare ? Si ces traits manquent sur le tirage, la limite de
  5 mm est optimiste et **tous** les scenarios resserres en dependent.

    PYTHONPATH=src:scripts/research python3 scripts/research/build_edge_test_sheet.py \\
        --pdf _bmad-output/test-artifacts/cible-de-mesure/test_bords_prudent.pdf \\
        --descriptor _bmad-output/test-artifacts/cible-de-mesure/test_bords_prudent.json

Banc de recherche, hors production.
"""

# --- Story 5.17: ce banc emet desormais du payload 2.0 ----------------------
#
# Il fabrique sa charge utile par `page_payload.plan_page_payload`, donc il suit la
# table de cles courtes de la story 5.17 (`EPIC5-ARB-60`) sans rien perdre et **sans
# une ligne a changer ici**. Deux consequences a connaitre:
#
# * une feuille refabriquee maintenant n'est plus comparable, symbole a symbole, a celle
#   imprimee le 2026-08-11 -- la seconde porte du 1.0. Le depouillement
#   (`analyse_edge_test_scan.py`) compare toujours au descripteur de **sa** fabrication,
#   donc les deux restent depouillables separement, jamais croisees;
# * le motif du choix du cardinal 6 ci-dessous a **change de nature**: sous le schema
#   2.0 le cardinal 8 ne donne plus 105 modules mais 85 (version 17), donc il n'est plus
#   dans le regime indecodable. Le choix du 6 est conserve tel quel pour ne pas invalider
#   la comparaison avec le tirage existant; une **reimpression** de l'eprouvette pourra
#   remonter au cardinal 8.

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, "src")
sys.path.insert(0, "scripts/research")

import cv2  # noqa: E402

from mixed_media_utility import layout, page_templates as pt, qr_codes  # noqa: E402
from build_measurement_target import (  # noqa: E402
    RENDER_DPI,
    TEST_MARKER_FIRST_ID,
    TargetLayoutError,
    _blank_page,
    _label,
    _paste_gray,
    _px,
    _side_px,
    write_pdf,
)
import optimise_page_layout as O  # noqa: E402
import render_page_templates as R  # noqa: E402

_INK = 0

#: Le scenario teste. « prudent » et non « agressif »: c'est celui recommande, et son
#: bord exterieur de marqueur garde 3 mm sous la limite d'encre. L'agressif l'atteint
#: exactement, et rien ne justifie de risquer la feuille sur les deux a la fois --
#: si le prudent echoue au bord, l'agressif est mort sans etre imprime.
SCENARIO = next(s for s in O.SCENARIOS
                if s.name.startswith("temoins seuls (1 colonne) + prudent"))

#: Orientation de l'eprouvette. Portrait: c'est l'orientation dont le bord long porte
#: le plus de deformation de feuille, donc le cas le plus severe pour les sondes de
#: bord. Le gradient mesure le 2026-08-11 sur `candidat_gabarit` allait deja dans ce
#: sens (coins bas a 0,14-0,17 mm contre 0,03-0,06 en haut).
ORIENTATION = pt.ORIENTATION_PORTRAIT

#: Taille des sondes de reperage. 10 mm: assez grand pour etre detecte de facon fiable
#: (le plancher mesure est 4 mm), assez petit pour se glisser a 6 mm d'un bord sans
#: toucher la limite d'encre.
PROBE_SIZE_MM = 10.0

#: Distance du bord physique aux sondes de bord. 6 mm place le bord exterieur de la
#: sonde **1 mm au-dela** de la limite d'encre de 5 mm: c'est volontaire et c'est le
#: point du test. Une sonde qui s'imprime intacte a 6 mm valide la marge; une sonde
#: rognee la refute, et le fait pour un element dont on se passe, pas pour un coin.
PROBE_EDGE_MARGIN_MM = 6.0

#: Reperes de limite d'encre: trait de 0,4 mm d'epaisseur, 20 mm de long, pose de
#: sorte que son bord exterieur soit exactement a PRINTER_MARGIN_MM du bord physique.
INK_MARK_THICKNESS_MM = 0.4
INK_MARK_LENGTH_MM = 20.0


def _rect_mm(page: np.ndarray, x_mm, y_mm, w_mm, h_mm) -> None:
    x0, y0 = _px(x_mm, y_mm)
    x1, y1 = _px(x_mm + w_mm, y_mm + h_mm)
    cv2.rectangle(page, (x0, y0), (x1, y1), (_INK, _INK, _INK), -1)


def _outline_mm(page: np.ndarray, x_mm, y_mm, w_mm, h_mm, thickness_mm=0.4) -> None:
    x0, y0 = _px(x_mm, y_mm)
    x1, y1 = _px(x_mm + w_mm, y_mm + h_mm)
    thickness = max(1, _side_px(thickness_mm))
    cv2.rectangle(page, (x0, y0), (x1, y1), (_INK, _INK, _INK), thickness)


def _assert_inside_page(box, page_w, page_h, what: str) -> None:
    """Refuser tout element qui sortirait de la feuille.

    Garde volontairement distincte de la limite d'encre: cette feuille pose
    **exprès** des elements au-dela de la limite de 5 mm (c'est son objet), mais rien
    ne doit sortir du papier -- un element hors page est rogne par le rasteriseur en
    silence, et son absence sur le tirage serait alors lue comme un echec
    d'impression au bord.
    """
    x0, y0, x1, y1 = box
    if x0 < 0 or y0 < 0 or x1 > page_w or y1 > page_h:
        raise TargetLayoutError(
            f"{what}: emprise ({x0:.1f},{y0:.1f})-({x1:.1f},{y1:.1f}) mm sort de la "
            f"feuille {page_w:g}x{page_h:g} mm. Un element hors page est rogne sans "
            "erreur, et son absence serait lue comme un echec d'impression."
        )


def _element_box(element: dict) -> tuple[float, float, float, float] | None:
    """Emprise **a garder libre** d'un element pose, ou ``None`` s'il n'en declare pas.

    Pour un marqueur, l'emprise rendue est **dilatee de sa zone de silence**, et non
    l'emprise du carre seul: de l'encre a 2 mm d'un coin qui declare 5 mm de silence ne
    teste plus 5 mm de silence, elle en teste 2, et le verdict porterait sur autre chose
    que ce qu'il annonce. L'emprise du QR contient deja son silence ISO.
    """
    if "x_mm" not in element or "y_mm" not in element:
        return None
    quiet = 0.0
    if element["kind"] in ("ink_limit_mark", "text_block"):
        w, h = element["width_mm"], element["height_mm"]
    elif element["kind"] == "qr":
        w = h = element["footprint_mm"]
    elif "size_mm" in element:
        w = h = element["size_mm"]
        quiet = float(element.get("quiet_zone_mm", 0.0))
    else:
        return None
    return (element["x_mm"] - quiet, element["y_mm"] - quiet,
            element["x_mm"] + w + quiet, element["y_mm"] + h + quiet)


def _free_windows(along: str, fixed_lo: float, fixed_hi: float,
                  span: float, elements: list[dict]) -> list[tuple[float, float]]:
    """Intervalles libres le long d'un bord, pour la bande ``[fixed_lo, fixed_hi]``.

    ``along`` vaut ``"x"`` (bord horizontal) ou ``"y"`` (bord vertical). Rend les
    intervalles de l'axe libre que rien d'occupe ne recoupe, dans la bande transverse
    donnee. Existe pour que la position des sondes soit **derivee** de ce qui est deja
    pose plutot qu'ecrite a la main: la premiere version posait la sonde du bord haut a
    l'abscisse du centre de la page, c'est-a-dire **entierement dans l'emprise du QR**,
    et rien ne l'a signale.
    """
    blocked: list[tuple[float, float]] = []
    for element in elements:
        box = _element_box(element)
        if box is None:
            continue
        x0, y0, x1, y1 = box
        transverse = (y0, y1) if along == "x" else (x0, x1)
        if transverse[0] >= fixed_hi or transverse[1] <= fixed_lo:
            continue  # hors de la bande du bord: n'obstrue pas
        blocked.append((x0, x1) if along == "x" else (y0, y1))

    blocked.sort()
    windows: list[tuple[float, float]] = []
    cursor = 0.0
    for lo, hi in blocked:
        if lo > cursor:
            windows.append((cursor, lo))
        cursor = max(cursor, hi)
    windows.append((cursor, span))
    return [(lo, hi) for lo, hi in windows if hi > lo]


def _largest_window_centre(windows, size_mm: float, what: str) -> float:
    """Centrer ``size_mm`` dans le plus grand intervalle libre, ou refuser."""
    usable = [(hi - lo, lo, hi) for lo, hi in windows if hi - lo >= size_mm]
    if not usable:
        raise TargetLayoutError(
            f"{what}: aucun intervalle libre de {size_mm:g} mm sur ce bord. "
            f"Intervalles disponibles: "
            f"{[(round(lo, 1), round(hi, 1)) for lo, hi in windows]}."
        )
    width, lo, hi = max(usable)
    return lo + (width - size_mm) / 2.0


def _assert_no_overlap(box, elements: list[dict], what: str) -> None:
    """Refuser un element qui recouvrirait un element deja pose.

    Garde ajoutee apres un defaut reel sur cette feuille meme: les deux reperes de
    limite d'encre lateraux tombaient dans l'emprise de trois pastilles temoins. Ce
    n'etait pas visible au rendu reduit et le tirage aurait rendu un verdict faux --
    un repere absent aurait ete confondu avec une pastille presente.
    """
    x0, y0, x1, y1 = box
    for element in elements:
        other = _element_box(element)
        if other is None:
            continue
        ox0, oy0, ox1, oy1 = other
        if x0 < ox1 and ox0 < x1 and y0 < oy1 and oy0 < y1:
            raise TargetLayoutError(
                f"{what}: emprise ({x0:.1f},{y0:.1f})-({x1:.1f},{y1:.1f}) mm recouvre "
                f"{element['kind']} ({ox0:.1f},{oy0:.1f})-({ox1:.1f},{oy1:.1f}). Un "
                "element recouvert rend un verdict sur autre chose que lui-meme."
            )


def build(page_w: float, page_h: float) -> tuple[np.ndarray, list[dict]]:
    page = _blank_page()
    elements: list[dict] = []

    # -- 1. Les quatre coins prudents, a leur vraie position ---------------------
    size = SCENARIO.marker_size_mm
    margin = SCENARIO.marker_margin_mm
    for corner, (x_mm, y_mm) in {
        0: (margin, margin),
        1: (page_w - margin - size, margin),
        2: (page_w - margin - size, page_h - margin - size),
        3: (margin, page_h - margin - size),
    }.items():
        box = (x_mm, y_mm, x_mm + size, y_mm + size)
        _assert_inside_page(box, page_w, page_h, f"coin prudent {corner}")
        _assert_no_overlap(box, elements, f"coin prudent {corner}")
        raster = layout.generate_aruco_marker_image(corner, _side_px(size))
        _paste_gray(page, raster, x_mm, y_mm, what=f"coin prudent {corner}")
        elements.append({
            "kind": "prudent_corner", "corner_index": corner, "marker_id": corner,
            "size_mm": size, "marker_margin_mm": margin,
            "quiet_zone_mm": SCENARIO.quiet_zone_mm,
            "x_mm": x_mm, "y_mm": y_mm,
            "centre_x_mm": x_mm + size / 2, "centre_y_mm": y_mm + size / 2,
        })

    # -- 2. Le QR, a son emprise reelle et a sa place -----------------------------
    # Emprise et position lues au banc, jamais reecrites: c'est le chiffre corrige du
    # 2026-08-11 (38,3 mm et non 13,9), et le recopier ici serait une divergence en
    # puissance.
    footprint = R.qr_footprint_mm()
    qr_x = (page_w - footprint) / 2.0
    qr_y = pt.PRINTER_MARGIN_MM
    _assert_inside_page((qr_x, qr_y, qr_x + footprint, qr_y + footprint),
                        page_w, page_h, "emprise QR")
    _assert_no_overlap((qr_x, qr_y, qr_x + footprint, qr_y + footprint),
                       elements, "emprise QR")
    # Payload du cardinal 6 et **non** du pire cardinal (8), a l'inverse de ce qui
    # dimensionne la bande. Motif mesure le 2026-08-11 en fabriquant cette feuille:
    # le payload a 8 slots (698 octets) encode sur **105 modules**, soit la version 22
    # du symbole, que `QRCodeDetectorAruco` -- le detecteur par defaut de production --
    # ne decode a AUCUNE taille imprimee, meme sur un rendu parfait. Les versions 21
    # (101 modules) et 23 (109) se decodent, donc ce n'est pas un plafond de
    # resolution: c'est la version 22 en propre. Voir
    # `analyse-2026-08-11-qr-version-22-indecodable.md`.
    #
    # Consequence pour cette feuille: imprimer un symbole indecodable ferait rendre un
    # verdict « QR illisible au bord » sur une feuille dont le QR est illisible **au
    # rendu**, donc un faux negatif sur le sujet du test. Le cardinal 6 donne 97
    # modules et 35,0 mm de symbole, soit 37,9 mm d'emprise contre 38,3 -- l'ecart de
    # 0,4 mm ne change rien a ce que la position au bord eprouve.
    plan = R.Q.qr_plan_for(6, "tpl-a4-portrait-2f-v1")
    symbol_mm = plan.print_size_mm
    # `render_for_print` pose le silence ISO lui-meme et gere l'echelle entiere par
    # module: recalculer la marge a la main ici reintroduirait exactement le defaut de
    # modules a largeur alternee que cette fonction existe pour eviter.
    native = qr_codes.encode_qr_image(plan.payload_text)
    raster = qr_codes.render_for_print(native, symbol_mm, RENDER_DPI)
    if raster.ndim == 3:
        raster = cv2.cvtColor(raster, cv2.COLOR_BGR2GRAY)
    _paste_gray(page, raster, qr_x, qr_y, what="QR")
    elements.append({
        "kind": "qr", "module_side": plan.module_side,
        "payload_bytes": plan.budget.size_bytes,
        "symbol_mm": symbol_mm, "footprint_mm": footprint,
        "x_mm": qr_x, "y_mm": qr_y,
        "payload_text": plan.payload_text,
    })

    # -- 3. Les 18 temoins a 6 mm, sur les bords haut et bas ----------------------
    reference = R.build(SCENARIO, ORIENTATION, 4, "haut")
    if reference is None:
        raise TargetLayoutError("le gabarit de reference ne se compose pas")
    patch_mm = SCENARIO.patch_size_mm
    for index, patch in enumerate(reference.patches):
        box = (patch["x"], patch["y"], patch["x"] + patch["w"], patch["y"] + patch["h"])
        _assert_inside_page(box, page_w, page_h, f"temoin {index}")
        _assert_no_overlap(box, elements, f"temoin {index}")
        _rect_mm(page, patch["x"], patch["y"], patch["w"], patch["h"])
        elements.append({
            "kind": "witness_patch", "index": index,
            "x_mm": patch["x"], "y_mm": patch["y"],
            "size_mm": patch["w"],
        })

    # -- 4. Reperes de limite d'encre ---------------------------------------------
    # Bord exterieur du trait exactement a PRINTER_MARGIN_MM du bord physique. Un
    # trait absent du tirage refute la limite de 5 mm, dont tous les scenarios
    # resserres dependent. Poses **avant** les sondes, pour que le calcul des
    # intervalles libres les prenne en compte.
    edge = pt.PRINTER_MARGIN_MM
    thickness = INK_MARK_THICKNESS_MM
    length = INK_MARK_LENGTH_MM
    # Ordonnee des reperes lateraux: **sous** la colonne de temoins, jamais a sa
    # hauteur. Premiere version a `page_h * 0.24`: les deux reperes tombaient dans
    # l'emprise de trois pastilles temoins (qui occupent x = 5 et 199 mm, y 48 a 126),
    # donc un trait absent au tirage serait devenu indiscernable d'une pastille
    # imprimee -- soit exactement le verdict que ce repere existe pour rendre.
    lateral_y = max(p["y"] + p["h"] for p in reference.patches) + 24.0
    marks = [
        ("haut", page_w * 0.24, edge, length, thickness),
        ("bas", page_w * 0.24, page_h - edge - thickness, length, thickness),
        ("gauche", edge, lateral_y, thickness, length),
        ("droit", page_w - edge - thickness, lateral_y, thickness, length),
    ]
    for label_text, x_mm, y_mm, w_mm, h_mm in marks:
        box = (x_mm, y_mm, x_mm + w_mm, y_mm + h_mm)
        _assert_inside_page(box, page_w, page_h, f"repere d'encre {label_text}")
        _assert_no_overlap(box, elements, f"repere d'encre {label_text}")
        _rect_mm(page, x_mm, y_mm, w_mm, h_mm)
        elements.append({
            "kind": "ink_limit_mark", "label": label_text,
            "x_mm": x_mm, "y_mm": y_mm, "width_mm": w_mm, "height_mm": h_mm,
            "distance_to_edge_mm": edge,
        })

    # -- 5. Texte, pose AVANT les sondes et **enregistre** comme element -----------
    # L'enregistrement n'est pas cosmetique: sans lui la garde anti-recouvrement a un
    # trou, et une sonde interieure pouvait tomber dans le bloc de texte sans que rien
    # ne le signale -- exactement le defaut que la sonde du bord haut a eu contre le QR.
    band = reference.band
    _outline_mm(page, band["x"], band["y"], band["width"], band["height"], 0.3)
    lines = [
        "TEST DES BORDS -- geometrie prudente a sa VRAIE position",
        "NE PAS passer a `scan`: cette feuille ne porte aucun coin de production.",
        f"Coins: {size:g} mm, marge {margin:g} mm (bord exterieur a {margin:g} mm du papier).",
        f"QR: {symbol_mm:.1f} mm symbole, {footprint:.1f} mm silence ISO compris.",
        f"Temoins: {len(reference.patches)} pastilles de {patch_mm:g} mm, colonnes a "
        f"{pt.PRINTER_MARGIN_MM:g} mm des bords.",
        f"Sondes de reperage {PROBE_SIZE_MM:g} mm: 4 a {PROBE_EDGE_MARGIN_MM:g} mm des bords "
        "(haut, bas, gauche, droit),",
        "2 a l'interieur comme temoins. Leurs positions exactes sont au descripteur JSON.",
        "Traits fins pres des bords = limite d'encre a 5 mm. S'ils manquent au tirage,",
        "la marge reelle de l'imprimante est plus large que declaree.",
        f"Scanner a {qr_codes.QR_MIN_SCAN_DPI} dpi, pilote TIFF, correction auto DESACTIVEE.",
    ]
    text_x = band["x"] + 6.0
    text_top = band["y"] + 14.0
    line_height = 7.0
    for index, line in enumerate(lines):
        _label(page, line, text_x, text_top + index * line_height)
    # Emprise du bloc, large par exces: la largeur est bornee par la bande entiere
    # plutot que mesuree ligne a ligne. Un exces rend la garde plus severe qu'il ne
    # faut, ce qui est le bon sens de l'erreur pour une garde.
    elements.append({
        "kind": "text_block",
        "x_mm": text_x - 2.0,
        "y_mm": text_top - line_height,
        "width_mm": band["width"] - 8.0,
        "height_mm": len(lines) * line_height + 2.0,
    })

    # -- 6. Sondes de reperage, dans les intervalles libres -----------------------
    # C'est l'ecart entre leur position declaree et leur position relue apres
    # redressement qui mesure l'erreur, donc elles doivent etre connues exactement,
    # etalees, et **libres** -- une sonde recouverte ne se detecte pas.
    #
    # Chaque abscisse (ou ordonnee) est **derivee**: le centre du plus grand intervalle
    # libre du bord, calcule contre tout ce qui est deja pose, silences de marqueur
    # compris. La premiere version ecrivait « au milieu du bord » pour la sonde du
    # haut, ce qui la posait **entierement dans l'emprise du QR**, et aucune garde ne
    # le voyait -- `_assert_no_overlap` n'etait cablee que sur les reperes d'encre.
    near = PROBE_EDGE_MARGIN_MM
    far = PROBE_SIZE_MM + near
    edge_probes = [
        ("bord haut", "x", near, page_w),
        ("bord bas", "x", page_h - far, page_w),
        ("bord gauche", "y", near, page_h),
        ("bord droit", "y", page_w - far, page_h),
    ]
    probe_positions: list[tuple[str, tuple[float, float]]] = []
    for label_text, along, fixed, span in edge_probes:
        windows = _free_windows(along, fixed, fixed + PROBE_SIZE_MM, span, elements)
        centre = _largest_window_centre(windows, PROBE_SIZE_MM, f"sonde {label_text}")
        probe_positions.append(
            (label_text, (centre, fixed) if along == "x" else (fixed, centre)))
    # Deux sondes internes, comme temoins: si elles sortent justes et les quatre
    # autres non, l'erreur est bien un effet de bord et pas un defaut global. Posees
    # sur la diagonale de la bande, aux tiers -- position arbitraire mais **verifiee**
    # libre par la garde, et non supposee telle.
    # Ordonnees prises **sous le bloc de texte**, pas sur la diagonale de la bande
    # entiere: la diagonale posait la premiere sonde au niveau des lignes de texte, et
    # rien ne l'interdisait avant que le bloc ne soit enregistre.
    band_ref = reference.band
    text_bottom = max(
        _element_box(e)[3] for e in elements if e["kind"] == "text_block")
    lower = (text_bottom + 8.0, band_ref["y"] + band_ref["height"] - PROBE_SIZE_MM - 4.0)
    for name, fx, fy in (("interieur gauche", 1 / 4, 1 / 3),
                         ("interieur droit", 3 / 4, 2 / 3)):
        probe_positions.append((name, (
            band_ref["x"] + band_ref["width"] * fx - PROBE_SIZE_MM / 2,
            lower[0] + (lower[1] - lower[0]) * fy)))

    marker_id = TEST_MARKER_FIRST_ID
    for label_text, (x_mm, y_mm) in probe_positions:
        box = (x_mm, y_mm, x_mm + PROBE_SIZE_MM, y_mm + PROBE_SIZE_MM)
        _assert_inside_page(box, page_w, page_h, f"sonde {label_text}")
        _assert_no_overlap(box, elements, f"sonde {label_text}")
        raster = layout.generate_aruco_marker_image(marker_id, _side_px(PROBE_SIZE_MM))
        _paste_gray(page, raster, x_mm, y_mm, what=f"sonde {label_text}")
        elements.append({
            "kind": "registration_probe", "label": label_text,
            "marker_id": marker_id, "size_mm": PROBE_SIZE_MM,
            "x_mm": x_mm, "y_mm": y_mm,
            "centre_x_mm": x_mm + PROBE_SIZE_MM / 2,
            "centre_y_mm": y_mm + PROBE_SIZE_MM / 2,
            "is_edge_probe": label_text.startswith("bord"),
        })
        marker_id += 1

    return page, elements


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pdf",
        default="_bmad-output/test-artifacts/cible-de-mesure/test_bords_prudent.pdf")
    parser.add_argument(
        "--descriptor",
        default="_bmad-output/test-artifacts/cible-de-mesure/test_bords_prudent.json")
    args = parser.parse_args(argv)

    page_w, page_h = pt.page_size_mm(ORIENTATION)
    page, elements = build(page_w, page_h)

    pdf_path = Path(args.pdf)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    write_pdf([page], pdf_path)

    descriptor = {
        "target": "test-bords-prudent",
        "page_size_mm": [page_w, page_h],
        "orientation": ORIENTATION,
        "render_dpi": RENDER_DPI,
        "scenario": {
            "name": SCENARIO.name,
            "marker_size_mm": SCENARIO.marker_size_mm,
            "marker_margin_mm": SCENARIO.marker_margin_mm,
            "quiet_zone_mm": SCENARIO.quiet_zone_mm,
            "patch_size_mm": SCENARIO.patch_size_mm,
        },
        "printer_margin_mm": pt.PRINTER_MARGIN_MM,
        "scan_dpi": qr_codes.QR_MIN_SCAN_DPI,
        "elements": elements,
    }
    Path(args.descriptor).write_text(
        json.dumps(descriptor, indent=2, ensure_ascii=False), encoding="utf-8")

    counts: dict[str, int] = {}
    for element in elements:
        counts[element["kind"]] = counts.get(element["kind"], 0) + 1
    print(f"ecrit {pdf_path} ({pdf_path.stat().st_size / 1024:.0f} Ko)")
    print(f"ecrit {args.descriptor}")
    for kind, count in sorted(counts.items()):
        print(f"  {kind:22s} {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
