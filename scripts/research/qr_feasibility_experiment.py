"""Reproducible synthetic feasibility bench for the per-page QR code (story 4.6).

This does NOT replace a real print/scan campaign (no printer/scanner in this
environment). It produces reproducible, quantitative evidence instead of
guesses -- but the 2026-08-02 review showed the first version measured its own
rendering artifacts, so the methodology was rebuilt:

1. **Production payload format.** Payloads are built with ``io.payload``
   (story 2.3), the schema actually printed by the product. The previous bench
   used a private, ~2.8x lighter schema, so every byte threshold it validated
   was measured on a payload the product never emits.
2. **Exact byte targets.** The old loop grew the slot list ``while size <
   target``, i.e. it stopped *after* overshooting: the "512" class was really
   529 bytes, "768" was 776. The nominal budget was never actually tested.
   Sizes are now padded to land exactly on the target.
3. **Integer pixels per module.** Rendering resized straight to a fractional
   px/module with ``INTER_NEAREST``, so modules alternated between n and n+1
   pixels and decode success depended on the fractional part rather than on
   the printed size (30 mm decoded, 40 mm did not, on a clean image).
   ``qr_codes.render_for_print`` now supersamples by an integer factor first.
4. **Degradation in physical units.** Blur was specified in pixels, so 600 dpi
   received half the physical blur of 300 dpi and "600 dpi is more robust"
   was a tautology of the model. Blur is now specified in millimetres on
   paper and converted per DPI.
5. **Quiet zone preserved under rotation.** ``warpAffine`` kept the canvas
   size, cutting the ISO/IEC 18004 quiet zone from 4 modules to ~1. The
   "harsh" column was measuring a standards violation. The canvas is now
   expanded to fit the rotated symbol.
6. **Repetitions and a seed.** Noise made each cell a coin flip reported as a
   boolean: 20 runs of one combination gave 13/20 and 2/20. Every cell is now
   repeated ``REPEATS`` times with a deterministic per-cell seed and reported
   as a success rate.
7. **Decoder as an explicit axis.** Thresholds obtained with
   ``QRCodeDetector`` are that decoder's thresholds; ``QRCodeDetectorAruco``
   decodes cases the classic one rejects. Both are measured.

Run: python scripts/research/qr_feasibility_experiment.py [output.md]
"""

# --- Story 5.17: ce banc suit la nouvelle table sans rien perdre ------------
#
# Il construit ses charges utiles par `io.payload.build_page_payload` et les serialise
# par `io.payload.serialize_payload`: il emet donc du `2.0` a cles courtes depuis la
# story 5.17 (`EPIC5-ARB-60`), et sa ligne de rapport « Schema de payload » le dira
# d'elle-meme.
#
# Ce que cela change a ses conclusions: **rien**. Ses classes de mesure sont des
# **cibles d'octets** exactes (512, 768...), et le nombre de modules d'un symbole ne
# depend que du nombre d'octets, jamais du nom des cles. Ce qui change est le nombre
# d'emplacements qu'il faut pour atteindre une cible donnee -- il en faut desormais plus,
# et le bourrage s'en charge.
#
# Ce banc ne lit aucune planche imprimee: il n'y a **rien a reimprimer** de son fait.

from __future__ import annotations

import argparse
import itertools
import platform
import sys
import zlib
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from mixed_media_utility import qr_codes  # noqa: E402
from mixed_media_utility.io import payload as payload_io  # noqa: E402

SEED = 20260803

ECC_LEVELS = {
    "M": cv2.QRCodeEncoder_CORRECT_LEVEL_M,
    "Q": cv2.QRCodeEncoder_CORRECT_LEVEL_Q,
    "H": cv2.QRCodeEncoder_CORRECT_LEVEL_H,
}

PAYLOAD_TARGETS_BYTES = [300, 512, 768]
PRINT_SIZES_MM = [25.0, 30.0, 35.0]
SCAN_DPI = [300, 600]
DETECTORS = [qr_codes.DETECTOR_CLASSIC, qr_codes.DETECTOR_ARUCO]
REPEATS = 5

# (label, blur_sigma_mm, noise_std, jpeg_quality, rotation_deg)
# blur is expressed on paper (mm) and converted to pixels per DPI, so the two
# scan resolutions receive the same *physical* degradation.
DEGRADATIONS = [
    ("none", 0.0, 0, 100, 0.0),
    ("mild", 0.05, 6, 80, 1.0),
    ("harsh", 0.10, 14, 55, 3.0),
]


def make_payload(target_bytes: int) -> str:
    """Build a production-schema payload serialized to exactly ``target_bytes``.

    The slot list is grown while it still fits, then ``patch_preset_id`` is
    padded with ASCII filler to land exactly on the target. Returns the
    serialized JSON text.
    """
    base = dict(
        project_id="demo-project-01",
        rush_id="rush-a1",
        lot_id="lot-0007",
        page_index=1,
        page_count=3,
        fps_target=24.0,
        template_id="tpl-a4-2f-v1",
        target_colorspace="bt709",
    )

    def serialized(slot_count: int, preset: str) -> str:
        slots = [
            {"slot_index": index, "frame_timecode": f"00:00:{index % 60:02d}:00"}
            for index in range(slot_count)
        ]
        return payload_io.serialize_payload(
            payload_io.build_page_payload(**base, patch_preset_id=preset, slots=slots)
        )

    preset = "patch-default-v1"
    floor = len(serialized(1, preset).encode("utf-8"))
    if target_bytes < floor:
        raise ValueError(
            f"Cible de {target_bytes} octets inatteignable: le payload minimal "
            f"(1 slot) pese deja {floor} octets."
        )

    slot_count = 1
    while len(serialized(slot_count + 1, preset).encode("utf-8")) <= target_bytes:
        slot_count += 1

    text = serialized(slot_count, preset)
    padding = target_bytes - len(text.encode("utf-8"))
    if padding:
        text = serialized(slot_count, preset + "x" * padding)
    actual = len(text.encode("utf-8"))
    if actual != target_bytes:
        raise AssertionError(f"Cible {target_bytes} non atteinte exactement: {actual}")
    return text


def slots_in(payload_text: str) -> int:
    return len(payload_io.parse_payload(payload_text)["slots"])


def apply_degradation(
    image: np.ndarray,
    *,
    blur_sigma_mm: float,
    noise_std: float,
    jpeg_quality: int,
    rotation_deg: float,
    dpi: int,
    rng: np.random.Generator,
) -> np.ndarray:
    result = image.copy()

    if rotation_deg:
        # Expand the canvas so the rotation never eats into the quiet zone.
        height, width = result.shape[:2]
        matrix = cv2.getRotationMatrix2D((width / 2, height / 2), rotation_deg, 1.0)
        cos, sin = abs(matrix[0, 0]), abs(matrix[0, 1])
        new_width = int(round(height * sin + width * cos))
        new_height = int(round(height * cos + width * sin))
        matrix[0, 2] += (new_width - width) / 2
        matrix[1, 2] += (new_height - height) / 2
        result = cv2.warpAffine(
            result, matrix, (new_width, new_height), borderValue=255, flags=cv2.INTER_LINEAR
        )

    if blur_sigma_mm > 0:
        sigma_px = blur_sigma_mm / 25.4 * dpi
        ksize = max(3, int(round(sigma_px * 3)) | 1)
        result = cv2.GaussianBlur(result, (ksize, ksize), sigma_px)

    if noise_std > 0:
        noise = rng.normal(0, noise_std, result.shape)
        result = np.clip(result.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    if jpeg_quality < 100:
        ok, encoded = cv2.imencode(".jpg", result, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
        if ok:
            result = cv2.imdecode(encoded, cv2.IMREAD_GRAYSCALE)

    return result


def run_experiment() -> list[dict]:
    results: list[dict] = []
    payloads = {target: make_payload(target) for target in PAYLOAD_TARGETS_BYTES}

    for target_bytes, ecc_name in itertools.product(PAYLOAD_TARGETS_BYTES, ECC_LEVELS):
        payload = payloads[target_bytes]
        try:
            native = qr_codes.encode_qr_image(payload, correction_level=ECC_LEVELS[ecc_name])
        except qr_codes.QRPayloadTooLarge as exc:
            results.append(
                {
                    "bytes": target_bytes, "slots": slots_in(payload), "ecc": ecc_name,
                    "modules": 0, "mm": None, "dpi": None, "px_per_module": 0.0,
                    "degradation": "-", "detector": "-", "successes": 0, "repeats": 0,
                    "note": f"non encodable: {exc}",
                }
            )
            continue
        module_side = native.shape[0]

        for size_mm, dpi in itertools.product(PRINT_SIZES_MM, SCAN_DPI):
            rendered = qr_codes.render_for_print(native, size_mm, dpi)
            ratio = qr_codes.pixels_per_module(module_side, size_mm, dpi)
            for label, blur_mm, noise, jpeg_q, rotation in DEGRADATIONS:
                for detector in DETECTORS:
                    successes = 0
                    for repeat in range(REPEATS):
                        # zlib.crc32, not hash(): Python's hash() is salted per
                        # process (PYTHONHASHSEED), so seeding from it would
                        # make the "reproducible" bench irreproducible.
                        cell_key = f"{SEED}|{target_bytes}|{ecc_name}|{size_mm}|{dpi}|{label}|{repeat}"
                        rng = np.random.default_rng(zlib.crc32(cell_key.encode("utf-8")))
                        degraded = apply_degradation(
                            rendered,
                            blur_sigma_mm=blur_mm, noise_std=noise, jpeg_quality=jpeg_q,
                            rotation_deg=rotation, dpi=dpi, rng=rng,
                        )
                        result = qr_codes.decode_qr_image(degraded, detector=detector)
                        successes += int(result.ok and result.text == payload)
                    results.append(
                        {
                            "bytes": target_bytes, "slots": slots_in(payload), "ecc": ecc_name,
                            "modules": module_side, "mm": size_mm, "dpi": dpi,
                            "px_per_module": ratio, "degradation": label, "detector": detector,
                            "successes": successes, "repeats": REPEATS, "note": "",
                        }
                    )
    return results


def render_report(results: list[dict]) -> str:
    lines: list[str] = []
    add = lines.append
    add("# Banc de faisabilite QR — story 4.6")
    add("")
    add("Genere par `scripts/research/qr_feasibility_experiment.py`. **Ne pas editer a la main.**")
    add("")
    add(f"- Date (UTC): {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    add(f"- OpenCV: {cv2.__version__}")
    add(f"- Python: {platform.python_version()} ({platform.system()})")
    add(f"- Graine: {SEED}, {REPEATS} tirages par cellule")
    add(f"- Schema de payload: `io.payload` v{payload_io.PAYLOAD_SCHEMA_VERSION} (format de production)")
    add("")
    add("## Payloads mesures")
    add("")
    add("| octets vises | octets reels | slots |")
    add("| --- | --- | --- |")
    for target in PAYLOAD_TARGETS_BYTES:
        rows = [r for r in results if r["bytes"] == target]
        add(f"| {target} | {target} | {rows[0]['slots'] if rows else '-'} |")
    add("")
    add("## Resultats")
    add("")
    add("| octets | ecc | modules | mm | dpi | px/module | degrad. | detecteur | succes |")
    add("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in results:
        if r["note"]:
            add(
                f"| {r['bytes']} | {r['ecc']} | - | - | - | - | - | - | {r['note']} |"
            )
            continue
        add(
            f"| {r['bytes']} | {r['ecc']} | {r['modules']} | {r['mm']:.0f} | {r['dpi']} | "
            f"{r['px_per_module']:.2f} | {r['degradation']} | {r['detector']} | "
            f"{r['successes']}/{r['repeats']} |"
        )

    measured = [r for r in results if not r["note"]]
    total = sum(r["repeats"] for r in measured)
    passed = sum(r["successes"] for r in measured)
    add("")
    add(f"**Total: {passed}/{total} decodages reussis sur {len(measured)} cellules.**")

    add("")
    add("## Succes en fonction des pixels par module (variable physique reelle)")
    add("")
    add("`size_mm` et `dpi` n'agissent que par leur produit; les regrouper par px/module")
    add("evite de conclure sur une taille alors que c'est la resolution qui varie.")
    add("")
    add("| px/module | degrad. | detecteur | succes |")
    add("| --- | --- | --- | --- |")
    buckets: dict[tuple[str, str, str], list[int]] = {}
    for r in measured:
        bucket = f"{np.floor(r['px_per_module']):.0f}-{np.floor(r['px_per_module']) + 1:.0f}"
        key = (bucket, r["degradation"], r["detector"])
        entry = buckets.setdefault(key, [0, 0])
        entry[0] += r["successes"]
        entry[1] += r["repeats"]
    for (bucket, degradation, detector), (successes, repeats) in sorted(buckets.items()):
        add(f"| {bucket} | {degradation} | {detector} | {successes}/{repeats} |")

    add("")
    add("## Succes par niveau de correction (a geometrie egale)")
    add("")
    add("| ecc | detecteur | succes |")
    add("| --- | --- | --- |")
    ecc_buckets: dict[tuple[str, str], list[int]] = {}
    for r in measured:
        entry = ecc_buckets.setdefault((r["ecc"], r["detector"]), [0, 0])
        entry[0] += r["successes"]
        entry[1] += r["repeats"]
    for (ecc, detector), (successes, repeats) in sorted(ecc_buckets.items()):
        add(f"| {ecc} | {detector} | {successes}/{repeats} |")

    add("")
    add("## Succes par taille imprimee (a payload et degradation confondus)")
    add("")
    add("| mm | detecteur | succes |")
    add("| --- | --- | --- |")
    mm_buckets: dict[tuple[float, str], list[int]] = {}
    for r in measured:
        entry = mm_buckets.setdefault((r["mm"], r["detector"]), [0, 0])
        entry[0] += r["successes"]
        entry[1] += r["repeats"]
    for (size_mm, detector), (successes, repeats) in sorted(mm_buckets.items()):
        add(f"| {size_mm:.0f} | {detector} | {successes}/{repeats} |")

    add("")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output",
        nargs="?",
        default=str(Path(__file__).resolve().parents[2] / "temp" / "qr_experiment_results.md"),
        help="Fichier markdown de resultats (UTF-8, LF).",
    )
    args = parser.parse_args()

    report = render_report(run_experiment())
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8", newline="\n")
    print(f"Resultats ecrits dans {output_path}")


if __name__ == "__main__":
    main()
