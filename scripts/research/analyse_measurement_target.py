"""Analyse du scan de la cible de mesure terrain.

Consomme le scan de la planche produite par `build_measurement_target.py` et son
descripteur JSON, et rend les mesures des chantiers 5, 8, 9, 10 et 11
d'`EPIC5-ARB-43`. Banc de recherche, hors production.

    PYTHONPATH=src python3 scripts/research/analyse_measurement_target.py \\
        --scan srcs/Document_2026-08-10_141458_Taille_Patches_Degrades.pdf \\
        --descriptor _bmad-output/test-artifacts/cible-de-mesure/cible_de_mesure.json

Deux regimes de lecture, et ils ne se melangent pas
---------------------------------------------------
* les **marqueurs et les QR** sont lus sur le **scan brut**, au DPI declare,
  exactement comme le chemin de production les lit. Les mesurer sur une page
  redressee mesurerait le reechantillonnage du redressement en plus du papier,
  et la reponse servirait a dimensionner un marqueur imprime;
* les **pastilles et les degrades** sont lus sur la page **redressee**, parce
  qu'il faut les localiser au millimetre depuis le descripteur.

Le descripteur est la seule source des positions: rien n'est cherche par
detection de contour ni devine. Une planche imprimee a une echelle autre que
100 % rend donc des mesures fausses **sans lever d'erreur**, et c'est pourquoi la
consigne d'impression est ecrite sur la planche elle-meme.
"""

# --- Story 5.17: rien de perdu ici, et pourquoi ------------------------------
#
# Les quatre QR de la cible de mesure ne portent **pas** le payload de production:
# `build_measurement_target.py` fabrique une charge utile de synthese
# (`{"cible": ..., "bourrage": ...}`) dont le seul role est d'atteindre une longueur
# realiste. Le passage du schema de payload a `2.0` (story 5.17, `EPIC5-ARB-60`) ne les
# touche donc pas, et il n'y a **rien a reimprimer** de ce cote: ce banc compare le
# texte decode a celui du descripteur, sans jamais le parser.
#
# Consequence a connaitre quand meme: si ce texte etait un jour passe a
# `io.payload.parse_payload`, il serait refuse -- et avec le bon verdict, celui d'un QR
# etranger sans cle de version, pas celui d'une planche perimee.

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, "src")

from mixed_media_utility import layout, qr_codes, scan_ingest  # noqa: E402
from mixed_media_utility.detection import aruco as aruco_detection  # noqa: E402

DPI = 600
PROJ = Path("projects/projet_demo")


def _px(x_mm: float, y_mm: float) -> tuple[int, int]:
    return layout.mm_to_px(x_mm, y_mm, DPI)


def _rectified(image: np.ndarray) -> np.ndarray:
    """Redresser par les quatre coins de production, comme une planche reelle."""
    corners, ids = aruco_detection.detect_markers(image, dpi=DPI)
    document = aruco_detection.build_markers_document("cible", corners, ids)
    homography, width_px, height_px = aruco_detection.compute_page_homography(document, DPI)
    return aruco_detection.warp_page(image, homography, width_px, height_px)


def _sample_mm(page: np.ndarray, x_mm: float, y_mm: float, w_mm: float, h_mm: float) -> np.ndarray:
    x0, y0 = _px(x_mm, y_mm)
    x1, y1 = _px(x_mm + w_mm, y_mm + h_mm)
    return page[y0:y1, x0:x1]


def analyse_markers(raw: np.ndarray, elements: list[dict]) -> None:
    """Chantier 5: quelles tailles et quelles zones de silence survivent au papier."""
    corners, ids = aruco_detection.detect_markers(raw, dpi=DPI)
    found = set() if ids is None else {int(i) for i in ids.flatten()}

    sizes = [e for e in elements if e["kind"] == "marker_size_probe"]
    if sizes:
        print("\nCHANTIER 5a -- TAILLE DE MARQUEUR (zone de silence large et constante)")
        for probe in sorted(sizes, key=lambda e: -e["size_mm"]):
            state = "detecte" if probe["marker_id"] in found else "PERDU"
            print(f"  {probe['size_mm']:5.1f} mm  id {probe['marker_id']:3d}  {state}")
        survivors = [e["size_mm"] for e in sizes if e["marker_id"] in found]
        if survivors:
            print(f"  -> plus petite taille detectee: {min(survivors):g} mm "
                  f"(production: {layout.MARKER_SIZE_MM:g} mm)")

    zones = [e for e in elements if e["kind"] == "quiet_zone_probe"]
    if zones:
        print("\nCHANTIER 5b -- ZONE DE SILENCE (marqueur de taille constante)")
        for probe in sorted(zones, key=lambda e: -e["quiet_zone_mm"]):
            state = "detecte" if probe["marker_id"] in found else "PERDU"
            print(f"  d = {probe['quiet_zone_mm']:4.1f} mm  id {probe['marker_id']:3d}  {state}")
        survivors = [e["quiet_zone_mm"] for e in zones if e["marker_id"] in found]
        if survivors:
            print(f"  -> plus petite zone de silence tenue: {min(survivors):g} mm "
                  f"(production: {layout.MARKER_QUIET_ZONE_MM:g} mm)")


def analyse_qr(raw: np.ndarray, elements: list[dict]) -> None:
    """Chantier 11: le QR peut-il descendre de 35 a 31,5 mm ?

    Decode sur une **decoupe genereuse** du scan brut autour de la position
    nominale, et non sur la page entiere: `detectAndDecodeMulti` rendrait
    `DECODE_MULTIPLE` avec quatre symboles dans le champ, ce qui est le refus de
    page de 5.2 et ne dirait rien de la taille.
    """
    probes = [e for e in elements if e["kind"] == "qr_probe"]
    if not probes:
        return
    print("\nCHANTIER 11 -- TAILLE DE QR")
    margin_mm = 8.0
    for probe in sorted(probes, key=lambda e: -e["size_mm"]):
        crop = _sample_mm(
            raw,
            probe["x_mm"] - margin_mm, probe["y_mm"] - margin_mm,
            probe["size_mm"] + 2 * margin_mm, probe["size_mm"] + 2 * margin_mm,
        )
        result = qr_codes.decode_qr_image(crop)
        ok = result.ok and result.text == probe["payload_text"]
        state = "DECODE" if ok else f"echec ({result.status})"
        print(f"  {probe['size_mm']:5.1f} mm  {probe['pixels_per_module_at_600dpi']:5.2f} px/module"
              f"  {state}")
    decoded = [
        p["size_mm"] for p in probes
        if qr_codes.decode_qr_image(_sample_mm(
            raw, p["x_mm"] - margin_mm, p["y_mm"] - margin_mm,
            p["size_mm"] + 2 * margin_mm, p["size_mm"] + 2 * margin_mm)).ok
    ]
    if decoded:
        print(f"  -> plus petite taille decodee: {min(decoded):g} mm "
              f"(cible de production: {qr_codes.QR_PRINT_SIZE_TARGET_MM:g} mm)")


def analyse_patches(page: np.ndarray, elements: list[dict]) -> None:
    """Chantier 10: a partir de quelle taille la mesure d'une pastille derape.

    Le critere n'est pas « la pastille est visible » mais « sa mesure est
    stable »: on compare la valeur lue au centre a la valeur de reference, et on
    regarde a partir de quelle taille l'ecart decroche. Le retrait
    d'echantillonnage est proportionnel a la taille, faute de quoi une pastille
    de 3 mm n'aurait plus rien a echantillonner.
    """
    probes = [e for e in elements if e["kind"] == "patch_size_probe"]
    if not probes:
        return
    print("\nCHANTIER 10 -- TAILLE DE PASTILLE (ecart a la reference, canaux RGB)")
    inset_ratio = 0.25
    by_value: dict[str, list[tuple[float, np.ndarray]]] = {}
    for probe in probes:
        inset = probe["size_mm"] * inset_ratio
        sample = _sample_mm(
            page,
            probe["x_mm"] + inset, probe["y_mm"] + inset,
            probe["size_mm"] - 2 * inset, probe["size_mm"] - 2 * inset,
        )
        if sample.size == 0:
            continue
        measured = sample.reshape(-1, 3).mean(axis=0)[::-1]  # BGR -> RGB
        by_value.setdefault(probe["value_id"], []).append((probe["size_mm"], measured))

    for value_id, rows in by_value.items():
        reference = np.array(
            next(p["reference_rgb"] for p in probes if p["value_id"] == value_id), float)
        print(f"  {value_id}  reference RGB {tuple(int(v) for v in reference)}")
        baseline = None
        for size_mm, measured in sorted(rows, key=lambda r: -r[0]):
            if baseline is None:
                baseline = measured
            drift = float(np.abs(measured - baseline).max())
            print(f"    {size_mm:5.1f} mm  mesure {tuple(int(v) for v in measured)}"
                  f"  ecart max au plus grand: {drift:5.1f}/255")


def analyse_tone_wedge(page: np.ndarray, elements: list[dict]) -> None:
    """La courbe de transfert du couple imprimante+scanner, en aplats.

    C'est le **temoin** du diagnostic du 2026-08-10 sur la bande `0-255`: les
    memes valeurs source y sont portees en aplats de 12 mm, sur la meme feuille
    et au meme passage que la rampe. Un aplat et une rampe qui portent la meme
    valeur source doivent se lire pareil; s'ils divergent, ce qui les distingue
    n'est pas l'encre mais la **frequence spatiale**, donc un traitement d'image.

    La monotonie est verifiee explicitement: une courbe de transfert non
    monotone rendrait toute lecture de rampe ininterpretable, et il vaut mieux
    l'apprendre ici que le deduire d'un contouring aberrant.
    """
    steps = sorted(
        (e for e in elements if e["kind"] == "tone_wedge_step"), key=lambda e: e["level_8bit"])
    if not steps:
        return
    print("\nECHELLE DE TONS -- courbe de transfert (aplats, temoin des rampes)")
    inset = 3.0
    readings: list[tuple[int, float]] = []
    for step in steps:
        sample = _sample_mm(
            page, step["x_mm"] + inset, step["y_mm"] + inset,
            step["size_mm"] - 2 * inset, step["size_mm"] - 2 * inset)
        if sample.size == 0:
            continue
        readings.append((int(step["level_8bit"]), float(sample.mean())))
    print("  source " + " ".join(f"{level:4d}" for level, _ in readings))
    print("  scan   " + " ".join(f"{value:4.0f}" for _, value in readings))
    faults = [
        (readings[i - 1][0], readings[i][0])
        for i in range(1, len(readings))
        if readings[i][1] < readings[i - 1][1] - 1.0
    ]
    if faults:
        print(f"  -> NON MONOTONE entre {faults}: lecture de rampe non interpretable.")
    else:
        low, high = readings[0][1], readings[-1][1]
        print(f"  -> monotone, plancher {low:.0f}, plafond {high:.0f}, "
              f"amplitude utile {high - low:.0f}/255")


def analyse_production_patches(page: np.ndarray, elements: list[dict]) -> None:
    """Valeurs lues des pastilles de production, pour l'ecretage et le chantier 10.

    Les repetitions restent **distinctes** et sont affichees separement: c'est
    d'elles que sort le bruit de mesure, et une moyenne les rendrait invisibles
    (regle des fabriques, `CLAUDE.md`).
    """
    patches = [e for e in elements
               if e["kind"] in ("production_patch", "intermediate_sentinel")]
    if not patches:
        return
    print("\nPASTILLES DE PRODUCTION ET SENTINELLES (valeur lue par pastille)")
    inset = 3.0
    by_value: dict[str, list[np.ndarray]] = {}
    reference: dict[str, tuple] = {}
    for patch in patches:
        sample = _sample_mm(
            page, patch["x_mm"] + inset, patch["y_mm"] + inset,
            patch["size_mm"] - 2 * inset, patch["size_mm"] - 2 * inset)
        if sample.size == 0:
            continue
        by_value.setdefault(patch["value_id"], []).append(
            sample.reshape(-1, 3).mean(axis=0)[::-1])  # BGR -> RGB
        reference[patch["value_id"]] = tuple(patch["reference_rgb"])
    for value_id in sorted(by_value):
        rows = " | ".join(
            "(" + ", ".join(f"{v:3.0f}" for v in row) + ")" for row in by_value[value_id])
        print(f"  {value_id:16s} ref {str(reference[value_id]):16s} lu {rows}")
    _sentinel_verdict(by_value)


def _sentinel_verdict(by_value: dict[str, list[np.ndarray]]) -> None:
    """Verdict d'ecretage, meme recette que le banc de production.

    `SENTINEL_CHAINS`, le facteur de discrimination et le dE76 sont **importes**
    du banc de production et non recopies: deux recettes de verdict qui divergent
    est le defaut ferme en revue de 3.5, et il n'y a aucune raison qu'un verdict
    d'ecretage depende du banc qui le prononce.

    Le seuil vient du bruit **mesure** entre repetitions de la meme valeur, pas
    d'une constante posee: sans lui, « ces deux niveaux se ressemblent » ne
    voudrait rien dire.
    """
    from patch_delta_e_field_measurement import (
        SENTINEL_CHAINS, SENTINEL_DISCRIMINATION_FACTOR, de76)

    # `de76` du banc de production travaille en sRGB encode sur 0..1; les
    # echantillons d'ici sont sur 0..255. Sans cette normalisation le verdict
    # sort en centaines de dE76 -- symptome vu et corrige le 2026-08-10.
    by_value = {vid: [np.asarray(r, float) / 255.0 for r in rows]
                for vid, rows in by_value.items()}
    spreads = [
        float(de76(rows[0], rows[i]))
        for rows in by_value.values() if len(rows) > 1
        for i in range(1, len(rows))
    ]
    if not spreads:
        print("  -> ecretage INDETERMINE: aucune valeur repetee, pas de bruit mesurable.")
        return
    noise = float(np.median(spreads))
    threshold = SENTINEL_DISCRIMINATION_FACTOR * noise
    print(f"\n  ECRETAGE -- bruit inter-repetition median {noise:.2f} dE76, "
          f"seuil {threshold:.2f} ({SENTINEL_DISCRIMINATION_FACTOR:g} x le bruit)")
    means = {vid: np.mean(rows, axis=0) for vid, rows in by_value.items()}
    for axis, chain in SENTINEL_CHAINS.items():
        if any(vid not in means for vid in chain):
            print(f"    {axis:6s} INDETERMINE (valeurs absentes de la planche)")
            continue
        gaps = [(a, b, float(de76(means[a], means[b]))) for a, b in zip(chain, chain[1:])]
        clipped = [g for g in gaps if g[2] <= threshold]
        detail = ", ".join(f"{a}->{b} {gap:.2f}" for a, b, gap in gaps)
        verdict = "ECRETE" if clipped else "pas d'ecretage detecte"
        print(f"    {axis:6s} {verdict:22s} ({detail})")


def analyse_ramps(page: np.ndarray, elements: list[dict]) -> None:
    """Chantiers 8 et 9: le tramage supprime-t-il le contouring, sur papier ?

    **La metrique de la premiere version etait fausse, et de facon instructive.**
    Elle mesurait l'ecart type de `profil - lissage(1,7 mm)`, c'est-a-dire la part
    HAUTE frequence: or les plateaux de la rampe 96-128 font 170/32 = 5,3 mm, donc
    ce lissage les traverse a peine et la grandeur mesuree etait le **grain du
    scanner**, pas le contouring. Elle rendait des rapports de 0,90 a 1,33 entre
    tronque et trame -- du bruit -- et aurait fait conclure a tort que le tramage
    ne sert a rien.

    Ce que le tramage fait reellement: il ne reduit pas l'erreur totale, il la
    **deplace du bas vers le haut du spectre**. Une marche est visible parce
    qu'elle est correlee sur plusieurs millimetres; un grain de meme amplitude est
    invisible.

    **La deuxieme version etait fausse aussi, et pour une raison qu'il faut
    garder.** Elle mesurait le residu du profil a une **droite**, en supposant que
    la rampe scannee soit lineaire puisqu'elle est lineaire a l'impression. Elle ne
    l'est pas: le papier et le scanner y appliquent leur courbe de transfert, et
    ce residu-la est donc domine par cette courbe (mesure: 5,9 unites sur la rampe
    pleine echelle, quand une marche de 1 LSB en vaut ~1). Le nombre grandissait
    avec la non-linearite de l'imprimante, pas avec le contouring.

    La mesure juste est **spectrale**, parce que l'escalier a une frequence
    **connue**: un plateau par marche de 8 bits, soit `largeur / (haut - bas)`
    millimetres. Trois composantes, separees par ou elles vivent dans le spectre:

    * la **courbe de transfert** -- tres basse frequence, retiree par un lissage
      large (4 plateaux);
    * le **contouring** -- l'energie a la frequence du plateau et a son premier
      harmonique. C'est ce que le tramage doit faire chuter;
    * le **grain** -- tout le reste. Il peut monter, et c'est le principe meme du
      tramage: echanger une erreur visible contre une erreur invisible.
    """
    probes = [e for e in elements if e["kind"] == "gradient_ramp"]
    if not probes:
        return
    print("\nCHANTIERS 8 et 9 -- DEGRADES: contouring, tronque vs trame")
    results: dict[tuple[str, str], dict] = {}
    for probe in probes:
        band = _sample_mm(page, probe["x_mm"], probe["y_mm"],
                          probe["width_mm"], probe["height_mm"])
        if band.size == 0:
            continue
        # Profil = moyenne des lignes sur le canal vert (le plus proche de la
        # luminance et le moins bruite des trois sur un scanner RVB).
        profile = band[:, :, 1].astype(np.float64).mean(axis=0)
        px_per_mm = DPI / 25.4

        # Largeur nominale d'un plateau: la rampe couvre `high - low` marches de
        # 8 bits sur toute sa largeur. C'est elle qui dimensionne le lissage, et
        # non une constante -- une fenetre plus courte que le plateau mesurerait
        # le grain, ce qui est exactement l'erreur corrigee ici.
        steps = max(1, abs(probe["high_8bit"] - probe["low_8bit"]))
        plateau_mm = probe["width_mm"] / steps
        window_px = max(3, int(round(plateau_mm * px_per_mm * 2.0)) | 1)

        # Retrait de la courbe de transfert: lissage sur 4 plateaux, donc bien plus
        # large que l'escalier, qui y survit intact.
        trend_px = max(3, int(round(plateau_mm * px_per_mm * 4.0)) | 1)
        trend = np.convolve(profile, np.ones(trend_px) / trend_px, mode="same")
        margin = trend_px
        residual = (profile - trend)[margin:-margin]
        if residual.size < 64:
            continue

        window = np.hanning(residual.size)
        spectrum = np.abs(np.fft.rfft(residual * window)) * 2.0 / window.sum()
        freqs = np.fft.rfftfreq(residual.size, d=1.0)  # cycles par pixel
        plateau_freq = 1.0 / (plateau_mm * px_per_mm)

        def band_energy(centre: float, width_ratio: float = 0.25) -> float:
            low, high = centre * (1 - width_ratio), centre * (1 + width_ratio)
            selected = (freqs >= low) & (freqs <= high)
            return float(np.sqrt((spectrum[selected] ** 2).sum())) if selected.any() else 0.0

        contouring = band_energy(plateau_freq) + band_energy(2 * plateau_freq)
        # Grain: tout ce qui est au-dela de deux fois la frequence du plateau,
        # hors des bandes comptees comme contouring.
        far = freqs > 2.5 * plateau_freq
        grain = float(np.sqrt((spectrum[far] ** 2).sum())) if far.any() else 0.0
        results[(probe["span"], probe["quantisation"])] = {
            "levels": int(np.unique(np.round(profile)).size),
            "plateau_mm": plateau_mm,
            "window_mm": trend_px / px_per_mm,
            "contouring": contouring,
            "grain": grain,
        }

    print(f"  {'amplitude':10s} {'quantif':9s} {'plateau':>9s} {'fenetre':>9s} "
          f"{'contouring':>11s} {'grain':>7s}")
    for span in dict.fromkeys(p["span"] for p in probes):
        for mode in ("tronque", "trame"):
            row = results.get((span, mode))
            if row is None:
                continue
            print(f"  {span:10s} {mode:9s} {row['plateau_mm']:6.2f} mm "
                  f"{row['window_mm']:6.2f} mm {row['contouring']:11.3f} {row['grain']:7.3f}")
        trunc, dither = results.get((span, "tronque")), results.get((span, "trame"))
        if trunc and dither:
            ratio = trunc["contouring"] / dither["contouring"] if dither["contouring"] else float("inf")
            verdict = ("le tramage REDUIT le contouring" if ratio > 1.2
                       else "aucun effet mesurable" if ratio > 0.83
                       else "le tramage AGGRAVE le contouring")
            print(f"  {'':10s} -> contouring divise par {ratio:.2f} ({verdict}), "
                  f"grain x{dither['grain'] / trunc['grain']:.2f}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--scan", help="Scan PDF multipage de la cible, relatif au projet")
    source.add_argument(
        "--scan-pages", nargs="+",
        help="Une page-fichier image par page de la cible, dans l'ordre du descripteur")
    parser.add_argument("--descriptor", required=True, help="Descripteur JSON de la cible")
    args = parser.parse_args(argv)

    descriptor = json.loads(Path(args.descriptor).read_text(encoding="utf-8"))
    if descriptor["render_dpi"] != DPI:
        print(f"Attention: cible fabriquee a {descriptor['render_dpi']} ppp, lue a {DPI}.")

    if args.scan_pages is not None and len(args.scan_pages) != len(descriptor["pages"]):
        # Un decalage silencieux mesurerait les elements d'une page sur une
        # autre et rendrait des chiffres plausibles: on refuse au lieu de deviner.
        print(f"Le descripteur declare {len(descriptor['pages'])} pages, "
              f"{len(args.scan_pages)} page-fichiers fournies.")
        return 2

    for page_spec in descriptor["pages"]:
        rank = page_spec["page_index"]
        elements = page_spec["elements"]
        print(f"\n{'=' * 78}\nPAGE {rank + 1}")
        if args.scan_pages is None:
            locator = scan_ingest.PageLocator(args.scan, rank)
        else:
            # Page-fichier: `page_index` vaut None, l'ordre des chemins fait foi.
            locator = scan_ingest.PageLocator(args.scan_pages[rank], None)
        raw = scan_ingest.load_page_array(PROJ, locator, dpi=DPI)
        corners, ids = aruco_detection.detect_markers(raw, dpi=DPI)
        found = set() if ids is None else {int(i) for i in ids.flatten()}
        missing = sorted(set(layout.CORNER_MARKER_IDS) - found)
        if missing:
            print(f"  coins manquants {missing}: page non redressable, elements non mesures.")
            continue

        analyse_markers(raw, elements)
        analyse_qr(raw, elements)
        page = _rectified(raw)
        analyse_patches(page, elements)
        analyse_tone_wedge(page, elements)
        analyse_production_patches(page, elements)
        analyse_ramps(page, elements)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
