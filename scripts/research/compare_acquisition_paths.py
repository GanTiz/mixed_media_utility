"""Deux acquisitions de la **meme feuille**: le chemin PDF est-il redevenu propre ?

Origine: Egan pousse le 2026-08-11 deux versions de chaque planche -- « PDF avec le
pilote HP en desactivant la correction automatique ET tiff avec le pilote Windows ».

C'est exactement l'experience qui manquait. Le 2026-08-10, la comparaison
PDF/constructeur contre TIFF/natif avait montre que le pilote HP faisait du
traitement d'image: dégradés de basse frequence detruits, et surtout **blanc du
papier pousse a 255 la ou le pilote natif le laisse a 243**
(`analyse-2026-08-10-scan-tiff-pilote-natif.md`, sections 1 et 3). Trois verdicts
avaient du etre retires. La question restee ouverte etait: est-ce la *correction
automatique* du pilote, donc desactivable, ou le chemin PDF lui-meme (rasterisation
puis compression avec perte) ?

Le seul montage qui separe les deux est celui d'aujourd'hui: **une feuille physique,
deux acquisitions**. Tout ecart mesure entre elles est imputable a la chaine de
lecture, puisque l'encre est la meme -- ce qu'une comparaison entre deux tirages ne
permet jamais de conclure.

Ce que le banc mesure, et pourquoi chaque ligne
-----------------------------------------------
* **le blanc du papier** (`sentinel-white-1`, blanc non imprime cercle d'un cadre):
  c'etait la signature la plus nette du traitement HP. S'il lit 243 des deux cotes,
  l'ecretage du blanc a disparu;
* **le plancher de noir** (`sentinel-black-1`): l'autre bout de la dynamique;
* **la dynamique utile** entre ces deux bornes, en codes bruts;
* **chaque valeur du preset**, en dE76 d'une acquisition a l'autre. C'est la mesure
  qui decide: un ecart inferieur au bruit de la chaine rend les deux chemins
  interchangeables, un ecart superieur impose le TIFF;
* **le bruit de la chaine** lui-meme, lu sur les repetitions d'une meme valeur au
  sein d'une acquisition -- sans lui, l'ecart inter-acquisitions n'a pas d'echelle.

Le bruit est le **median** des ecarts entre repetitions, jamais la moyenne: une
pastille aberrante (poussiere, pli) gonflerait le seuil et masquerait precisement ce
qu'on cherche. Meme regle et meme motif qu'en `patch_delta_e_field_measurement.py`.

Lancer:

    PYTHONPATH=src python3 scripts/research/compare_acquisition_paths.py

Banc de recherche, hors production: rien ici ne definit de contrat.
"""

# --- Story 5.17: les acquisitions de ce banc portent du payload 1.0 ----------
#
# Les deux acquisitions comparees ici sont celles de planches v1 de `projet_demo`
# imprimees le 2026-08-11, dont le QR porte le schema de payload **1.0** (cles longues).
# Depuis la story 5.17 (`EPIC5-ARB-60`), le lecteur ne porte que le `2.0` et il n'existe
# **aucun lecteur bi-format**.
#
# Ce banc n'en est pas empeche: il n'appelle que `qr_codes.decode_qr_image` et se sert
# du seul fait que le symbole se decode ou non -- c'est-a-dire de ce que le chemin
# d'acquisition fait du QR, qui est son sujet. Mais le texte obtenu n'est plus
# exploitable: `io.payload.parse_payload` le refuse en nommant sa version, et la chaine
# de scan refusera ces planches. Pour les rescanner de bout en bout, il faut les
# **reimprimer**.
#
# Le piege a eviter en relisant ce banc: un `decoded.ok` vrai sur une planche 1.0 ne dit
# **pas** que la planche est exploitable. Il dit seulement que l'encre et l'optique vont
# bien.

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, "src")

from mixed_media_utility import (  # noqa: E402
    page_templates,
    patch_presets,
    qr_codes,
    scan_crop,
    scan_detection,
    scan_ingest,
)

DPI = 600
PROJ = Path("projects/projet_demo")

#: La planche couleur du 2026-08-11, dans ses deux acquisitions. Le template et le
#: preset sont ceux imprimes au pied de la planche, pas une supposition:
#: `template=tpl-a4-paysage-4f-v1 - patchs=patches-18-v2`.
TEMPLATE = "tpl-a4-paysage-4f-v1"
PRESET = "patches-18-v2"

#: `page_index` vaut None pour une page-fichier, l'index de page pour un PDF --
#: c'est le contrat de `PageLocator`, et c'est la seule difference de traitement
#: entre les deux sources. Tout le reste du chemin est identique, ce qui est la
#: condition pour imputer un ecart au format.
ACQUISITIONS = (
    ("PDF / pilote HP, correction auto desactivee", "srcs/4_patches_heteroclites.pdf", 0),
    ("TIFF / pilote Windows natif", "srcs/Numérisation_20260811.tiff", None),
)

#: Facteur applique au bruit median pour juger un ecart significatif. Repris tel
#: quel de `patch_delta_e_field_measurement.py` (`SENTINEL_DISCRIMINATION_FACTOR`)
#: pour que les deux bancs se lisent a la meme echelle: a 1 le seuil vaut le bruit
#: lui-meme, donc un ecart egal au bruit serait declare significatif une fois sur
#: deux.
SIGNIFICANCE_FACTOR = 2.0


def eotf(a):
    a = np.asarray(a, float)
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def lab(encoded):
    """Lab D65 depuis du sRGB encode, normalise [0, 1].

    Meme matrice et meme blanc de reference que `color_metrics.py`: un blanc
    different deplacerait toutes les distances, donc tous les seuils.
    """
    lin = eotf(encoded)
    m = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    r = (lin @ m.T) / np.array([0.95047, 1.0, 1.08883])
    eps, kappa = 216 / 24389, 24389 / 27
    f = np.where(r > eps, np.cbrt(r), (kappa * r + 16) / 116)
    return np.stack([116 * f[..., 1] - 16,
                     500 * (f[..., 0] - f[..., 1]),
                     200 * (f[..., 1] - f[..., 2])], -1)


def de76(a, b):
    return float(np.linalg.norm(lab(a) - lab(b), axis=-1))


def sample_acquisition(path: str, rank: int | None, layout):
    """Redresser une acquisition et echantillonner chaque pastille **placee**.

    Une entree par pastille et non par valeur: les repetitions restent distinctes,
    et c'est d'elles seules que sort le bruit de la chaine.
    """
    geometry = scan_detection.resolve_page_geometry(TEMPLATE, DPI)
    inset = patch_presets.SAMPLING_INSET_MM
    image = scan_ingest.load_page_array(PROJ, scan_ingest.PageLocator(path, rank), dpi=DPI)
    # Le QR est lu sur le scan **brut**, avant redressement, comme en production:
    # c'est la seule facon de savoir si le format d'acquisition ferme la porte des
    # l'entree. Le chantier 11 du 2026-08-10 avait conclu a un seuil de decodage
    # propre au chemin PDF -- il se verifie ici sur le QR de production.
    decoded = qr_codes.decode_qr_image(image)
    markers = scan_detection._detect_markers_document(image, DPI)["images"][0]["markers"]
    homography, scale = scan_detection.compute_template_homography(markers, geometry, DPI)
    warped = scan_crop.warp_detected_page(image, homography, geometry["page_size_px"])
    if warped.dtype == np.uint16:
        warped = (warped >> 8).astype(np.uint8)

    per_value: dict[str, list[np.ndarray]] = defaultdict(list)
    reference: dict[str, np.ndarray] = {}
    for patch in layout:
        x0, y0 = page_templates.mm_to_px(patch.x_mm + inset, patch.y_mm + inset, DPI)
        x1, y1 = page_templates.mm_to_px(
            patch.x_mm + patch.size_mm - inset, patch.y_mm + patch.size_mm - inset, DPI)
        sample = warped[y0:y1, x0:x1]
        if sample.size == 0:
            continue
        # BGR -> RGB, normalise: tout le reste du banc travaille en RGB [0, 1].
        per_value[patch.value_id].append(sample.reshape(-1, 3).mean(0)[::-1] / 255.0)
        reference[patch.value_id] = np.asarray(patch.rgb, float) / 255.0
    return {
        "markers": sorted(m["id"] for m in markers),
        "qr": (decoded.status, decoded.symbol_count, decoded.text),
        "scale": scale,
        "shape": image.shape,
        "per_value": {k: np.array(v) for k, v in per_value.items()},
        "reference": reference,
    }


def chain_noise_de76(per_value: dict[str, np.ndarray]) -> float:
    """Bruit de la chaine, lu sur les repetitions d'une meme valeur.

    Median des ecarts intra-valeur. Une valeur imprimee deux fois a deux endroits
    eloignes de la feuille borne ce que la chaine impression + scan +
    echantillonnage ne sait pas reproduire.
    """
    spreads = []
    for measures in per_value.values():
        if len(measures) < 2:
            continue
        spreads.extend(
            de76(measures[i], measures[j])
            for i in range(len(measures))
            for j in range(i + 1, len(measures))
        )
    return float(np.median(spreads)) if spreads else float("nan")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preset", default=PRESET, help="Preset de patchs de la planche")
    args = parser.parse_args()

    layout = patch_presets.resolve_patch_layout(TEMPLATE, args.preset)
    print(f"Planche {TEMPLATE} / {args.preset}: {len(layout)} pastilles placees")

    results = {}
    for label, path, rank in ACQUISITIONS:
        results[label] = sample_acquisition(path, rank, layout)
        r = results[label]
        n_rep = {len(v) for v in r["per_value"].values()}
        print(f"\n=== {label}")
        scale = r["scale"]
        print(f"    source {r['shape'][1]}x{r['shape'][0]} px, marqueurs {r['markers']}")
        print(f"    echelle x {scale.scale_x:.4f}, y {scale.scale_y:.4f}, "
              f"residu de similitude {scale.residual_px:.2f} px")
        print(f"    {len(r['per_value'])} valeurs, repetitions {sorted(n_rep)}, "
              f"bruit de chaine {chain_noise_de76(r['per_value']):.2f} dE76")
        status, count, text = r["qr"]
        try:
            lot = json.loads(text).get("lot_id", "?")
        except (json.JSONDecodeError, TypeError):
            lot = "illisible"
        print(f"    QR: {status}, {count} symbole(s), lot {lot}")

    labels = [label for label, _, _ in ACQUISITIONS]
    a, b = (results[label] for label in labels)

    # --- Les deux bornes de la dynamique, en codes bruts -----------------------
    # C'est ici que le traitement du pilote se voyait: 255 contre 243 sur le blanc.
    print("\n--- Bornes de la dynamique (codes bruts 0-255, moyenne des repetitions)")
    print(f"{'valeur':<20} {'source':>8} {labels[0][:26]:>28} {labels[1][:26]:>28}")
    for value_id in ("sentinel-white-1", "neutral-245", "neutral-020", "sentinel-black-1"):
        if value_id not in a["per_value"] or value_id not in b["per_value"]:
            continue
        src = a["reference"][value_id] * 255.0
        ma = a["per_value"][value_id].mean(0) * 255.0
        mb = b["per_value"][value_id].mean(0) * 255.0
        print(f"{value_id:<20} {src.mean():>8.0f} "
              f"{ma[0]:>8.1f} {ma[1]:>6.1f} {ma[2]:>6.1f}   "
              f"{mb[0]:>8.1f} {mb[1]:>6.1f} {mb[2]:>6.1f}")

    for label in labels:
        r = results[label]
        if "sentinel-white-1" in r["per_value"] and "sentinel-black-1" in r["per_value"]:
            white = r["per_value"]["sentinel-white-1"].mean() * 255.0
            black = r["per_value"]["sentinel-black-1"].mean() * 255.0
            print(f"    dynamique utile, {label}: {black:.1f} -> {white:.1f} "
                  f"= {white - black:.1f} codes")

    # --- L'ecart valeur par valeur, avec son echelle -------------------------
    noise = max(chain_noise_de76(a["per_value"]), chain_noise_de76(b["per_value"]))
    threshold = SIGNIFICANCE_FACTOR * noise
    print(f"\n--- Ecart entre les deux acquisitions, par valeur (dE76)")
    print(f"    bruit de chaine retenu {noise:.2f}, seuil de significativite "
          f"{SIGNIFICANCE_FACTOR} x bruit = {threshold:.2f}")
    rows = []
    for value_id in sorted(set(a["per_value"]) & set(b["per_value"])):
        gap = de76(a["per_value"][value_id].mean(0), b["per_value"][value_id].mean(0))
        ref = a["reference"][value_id]
        rows.append((gap, value_id,
                     de76(a["per_value"][value_id].mean(0), ref),
                     de76(b["per_value"][value_id].mean(0), ref)))
    rows.sort(reverse=True)
    print(f"\n{'valeur':<20} {'ecart PDF/TIFF':>15} {'a la source: PDF':>18} {'TIFF':>8}")
    for gap, value_id, da, db in rows:
        flag = " *" if gap > threshold else ""
        print(f"{value_id:<20} {gap:>15.2f} {da:>18.2f} {db:>8.2f}{flag}")
    gaps = np.array([row[0] for row in rows])
    print(f"\n    ecart median {np.median(gaps):.2f}, max {gaps.max():.2f}, "
          f"{int((gaps > threshold).sum())}/{len(gaps)} valeurs au-dela du seuil")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
