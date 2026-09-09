"""Deterministic layout definitions for the printable ArUco patch sheet.

This module owns the single source of truth for:
- page geometry (A4, millimeters, top-left/y-down convention),
- the 4 corner ArUco marker positions used for page registration,
- the frame zones extracted after deskew,
- PDF rendering via reportlab,
- millimeter <-> pixel conversions shared with the detection module.

All coordinates in this module use a "page frame" with origin at the top-left
corner of the page, x increasing to the right, y increasing downward (matching
how scanned raster images are naturally represented). This frame is converted
to reportlab's bottom-left/y-up coordinate system only at draw time.
"""

from __future__ import annotations

from pathlib import Path

import cv2
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdfcanvas

# Seule dependance interne de ce module, dans son propre bloc: elle etait
# inseree au milieu des imports tiers, ou elle se lisait comme l'un d'eux. La
# dependance va dans **ce** sens et jamais dans l'autre -- `page_templates` est
# verrouille pur par test, et un import en retour etablirait un cycle qui
# ferait tirer cv2 et reportlab a `patch_presets`.
from . import page_templates

# ArUco dictionary imposed for this POC slice.
ARUCO_DICTIONARY = cv2.aruco.DICT_6X6_250

# Page geometry (millimeters), A4 portrait.
PAGE_WIDTH_MM = 210.0
PAGE_HEIGHT_MM = 297.0

# Corner marker geometry.
MARKER_SIZE_MM = 30.0
MARKER_MARGIN_MM = 15.0

# Inner quiet zone around each printed marker (story 4.7). MARKER_MARGIN_MM
# above is the page-edge -> marker distance; nothing constrained the *inner*
# side until patches started sharing the page. The 4.3 rectified measurement
# showed detection breaking from ~24% contamination of the white silence
# margin -- well before occlusion of the symbol itself -- so any ink (patch,
# text, QR) must stay out of this band on all four sides of every marker.
MARKER_QUIET_ZONE_MM = 15.0

# Physical printer margin (EPIC4-ARB-6): no ink within 5 mm of the physical
# page edge. Shared by the patch registry (4.7) and the page composition
# (4.1) -- read it from here, never restate the number.
PRINTER_MARGIN_MM = 5.0

# IDs expected for the 4 corner markers, mapped: top-left, top-right,
# bottom-right, bottom-left.
CORNER_MARKER_IDS = (0, 1, 2, 3)

# --- ArUco role strategy (story 4.3) --------------------------------------
#
# ArUco markers are reserved for the geometric role: page registration
# (corners), plus optional discrete roles for template/slot identification.
# They never carry rich business metadata (timecode, fps, patch count, rush
# name, ...): that data lives exclusively in the manifest and the QR payload
# (see ARCHITECTURE_DETAILED.md section 7).
#
# ID ranges are reserved (non-overlapping) within DICT_6X6_250 (IDs 0..249)
# so future roles can be added without colliding with the corner IDs already
# baked into printed sheets:
#   - CORNER_MARKER_IDS (0..3): mandatory page-registration corners.
#   - TEMPLATE_VARIANT_ID_RANGE (10..19): optional single marker identifying
#     which PDF template/layout variant a page uses, if a page ever needs to
#     self-describe its template outside of the QR payload (e.g. a purely
#     visual/manual fallback). Not used by the POC baseline.
#   - SLOT_MARKER_ID_RANGE (20..49): optional discrete markers identifying
#     an individual frame zone ("slot"), reserved for future templates with
#     more than 2 frame zones per page or non-fixed zone layouts. Not used
#     by the POC baseline, which relies on the fixed FRAME_ZONES_MM order.
TEMPLATE_VARIANT_ID_RANGE = range(10, 20)
SLOT_MARKER_ID_RANGE = range(20, 50)

# IDs outside the three ranges above (4..9 and 50..249) are deliberately left
# unassigned: they are reserved for future roles and must not be printed. A
# marker carrying one of them on a scan comes from somewhere else (another
# project's sheet, a neighbouring page in frame) and must be treated as foreign
# rather than silently accepted -- see marker_role().
CORNER_ROLE = "corner"
TEMPLATE_VARIANT_ROLE = "template_variant"
SLOT_ROLE = "slot"
UNASSIGNED_ROLE = "unassigned"

# --- ArUco ID encoding decision (story 4.4, EPIC4-ARB-5) -------------------
#
# Decision: ArUco/QR split. ArUco IDs encode NOTHING beyond their reserved
# role; every candidate payload examined by story 4.4 stays out of the IDs:
#   - frame index: a lot carries up to 1000 frames (ARB-10) and slot_index is
#     lot-scoped (ARCHITECTURE_DETAILED.md section 3.1) -- no 250-ID dictionary
#     can carry it, and the QR payload already transports the full
#     slot_index -> frame_timecode mapping (io/payload.py, story 2.3);
#   - discrete margin: lives in the QR payload as a template preset
#     (template_id), per the explicit architecture interdiction (section 7 +
#     responsibility matrix section 5: margin column says "Non" for ArUco);
#   - patch count: a property of patch_preset_id, resolved by the 4.7 registry,
#     transported by the QR payload only.
#
# MVP printing policy: only the 4 corner markers are printed --
# PRINTED_MARKER_IDS below is consumed by generate_patch_sheet_pdf and must
# stay the single point of truth for what ends up on paper. The reserved
# ranges (TEMPLATE_VARIANT_ID_RANGE, SLOT_MARKER_ID_RANGE) stay dormant: no
# producer, no consumer, kept only so already-printed sheets can never collide
# with a future role extension.
#
# Scan-side detection policy for story 5.2 (decided here so 5.2 does not
# re-arbitrate). This block is the NORMATIVE copy of the policy: the dated
# notes in ARCHITECTURE.md and ARCHITECTURE_DETAILED.md section 7 summarize it
# and defer here on any divergence.
#   - corner IDs (role "corner"): mandatory, MIN_CORNER_MARKERS_REQUIRED
#     applies, duplicates raise AmbiguousMarkersError;
#   - reserved-range IDs (roles "template_variant" / "slot"): not expected on
#     MVP sheets; if detected, ignore for geometry and surface a warning
#     naming the ID and role (a neighbouring sheet or a future-template sheet
#     is in frame) -- never feed them into the homography;
#   - unassigned IDs (role "unassigned"): foreign markers; same treatment as
#     reserved-range IDs (ignore for geometry, warn);
#   - "expected but missing" only applies to corners on MVP sheets (raising
#     MissingMarkersError); no reserved-range marker is ever expected today,
#     so the story that first activates a reserved range must also decide what
#     its absence means -- that branch is deliberately NOT decided here.
PRINTED_MARKER_IDS = CORNER_MARKER_IDS


def aruco_dictionary_name() -> str:
    """Human-readable name of ARUCO_DICTIONARY, derived rather than hardcoded.

    Printed on the sheet footer: a hardcoded literal would silently lie on paper
    if ARUCO_DICTIONARY ever changed, and mislead the diagnosis at rescan time.
    """
    for name in dir(cv2.aruco):
        if name.startswith("DICT_") and getattr(cv2.aruco, name) == ARUCO_DICTIONARY:
            return name
    return f"DICT_ID_{ARUCO_DICTIONARY}"


def marker_role(marker_id: int) -> str:
    """Return the reserved role of ``marker_id``.

    Single point of truth for the ID-range strategy of story 4.3: consumers must
    call this rather than re-implementing the range boundaries, so that adding a
    role later cannot leave a stale copy behind.
    """
    if marker_id in CORNER_MARKER_IDS:
        return CORNER_ROLE
    if marker_id in TEMPLATE_VARIANT_ID_RANGE:
        return TEMPLATE_VARIANT_ROLE
    if marker_id in SLOT_MARKER_ID_RANGE:
        return SLOT_ROLE
    return UNASSIGNED_ROLE

# Detection policy if one or more corner markers are missing from a scan.
# MVP policy: all 4 corners are mandatory; the homography cannot be safely
# computed from fewer than 4 points without introducing untested affine
# fallbacks, so any missing corner raises MissingMarkersError (see
# detection/aruco.py). This is a deliberate MVP restriction, not a bug: a
# 3-corner affine fallback is an explicit non-goal until proven necessary.
# This constant is read by detection.aruco.compute_page_homography -- changing it
# changes the runtime policy.
MIN_CORNER_MARKERS_REQUIRED = 4

# Having 4 corner markers is necessary but NOT sufficient: cv2.findHomography
# returns a rank-deficient matrix (without ever returning None) when three of the
# four centers are near-collinear, e.g. a folded page or a very grazing capture
# angle. That matrix warps to a plausible-looking but meaningless page, which is
# a silent-corruption failure mode. detection.aruco therefore also checks that
# the 4 centers form a simple convex quadrilateral.
#
# The check uses the sine of the turn angle at each vertex (cross product of
# consecutive edges normalised by their lengths), which is scale- and
# dpi-independent. Measured on the reference fixture: ~0.9995 on all 4 vertices,
# and still ~0.999 under strong perspective; the degenerate collinear case
# measures exactly 0.0. The threshold below is therefore deliberately permissive
# and only rejects genuine degeneracy.
MIN_CORNER_QUAD_SIN = 0.05

# Frame zones, defined relative to the redressed page (top-left origin,
# y-down), not relative to the raw scanned image. Each zone is forced to a
# 16:9 aspect ratio (140.0 / 78.75 == 16 / 9 exactly) so that 1920x1080 source
# frames can be placed edge-to-edge without any internal margin.
FRAME_ZONES_MM = [
    {"name": "frame_zone_1", "x": 35.0, "y": 60.0, "width": 140.0, "height": 78.75},
    {"name": "frame_zone_2", "x": 35.0, "y": 148.75, "width": 140.0, "height": 78.75},
]


def corner_marker_centers_mm() -> dict[int, tuple[float, float]]:
    """Return the center position (x_mm, y_mm) of each corner marker, keyed by id."""
    half = MARKER_SIZE_MM / 2
    return {
        0: (MARKER_MARGIN_MM + half, MARKER_MARGIN_MM + half),
        1: (PAGE_WIDTH_MM - MARKER_MARGIN_MM - half, MARKER_MARGIN_MM + half),
        2: (PAGE_WIDTH_MM - MARKER_MARGIN_MM - half, PAGE_HEIGHT_MM - MARKER_MARGIN_MM - half),
        3: (MARKER_MARGIN_MM + half, PAGE_HEIGHT_MM - MARKER_MARGIN_MM - half),
    }


def mm_to_px(x_mm: float, y_mm: float, dpi: int) -> tuple[int, int]:
    """Convert a (x_mm, y_mm) point in the page frame to pixel coordinates at ``dpi``.

    Delegue a `page_templates.mm_to_px` depuis la story 5.2: la recette est
    unique dans le depot, et elle vit cote registre **pur** pour que le chemin
    de detection du scan puisse convertir des millimetres sans importer ce
    module, qui tire cv2. La fonction reste exportee ici parce que
    `pdf_render` et ses tests la consomment, et qu'aucun test existant ne se
    modifie. Une seconde implementation ferait diverger l'arrondi entre
    impression et scan, ce qui decalerait chaque crop d'un pixel a chaque bord
    sans jamais lever d'erreur.
    """
    return page_templates.mm_to_px(x_mm, y_mm, dpi)


def page_size_px(dpi: int) -> tuple[int, int]:
    """Return (width_px, height_px) of the full canonical page at ``dpi``."""
    return mm_to_px(PAGE_WIDTH_MM, PAGE_HEIGHT_MM, dpi)


def generate_aruco_marker_image(marker_id: int, size_px: int = 400):
    """Generate a single ArUco marker raster (grayscale numpy array) for ``marker_id``."""
    dictionary = cv2.aruco.getPredefinedDictionary(ARUCO_DICTIONARY)
    return cv2.aruco.generateImageMarker(dictionary, marker_id, size_px)


def _mm_to_pdf_point(x_mm: float, y_mm: float) -> tuple[float, float]:
    """Convert a page-frame point (top-left origin, y-down) to reportlab points
    (bottom-left origin, y-up)."""
    return x_mm * mm, (PAGE_HEIGHT_MM - y_mm) * mm


def generate_patch_sheet_pdf(
    output_path: str | Path,
    frame_paths: list[str | Path] | None = None,
    project_meta: dict | None = None,
) -> Path:
    """Render the printable A4 patch sheet PDF with 4 corner ArUco markers and the
    frame zones, and write it to ``output_path``.

    If ``frame_paths`` is provided, it must contain exactly ``len(FRAME_ZONES_MM)``
    image paths; each frame is drawn stretched to fill its zone rectangle exactly
    (edge-to-edge, no internal margin), matching the forced 16:9 zone geometry.
    If omitted, only the empty zone outlines are drawn.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if frame_paths is not None and len(frame_paths) != len(FRAME_ZONES_MM):
        raise ValueError(
            f"generate_patch_sheet_pdf attend exactement {len(FRAME_ZONES_MM)} frame(s), "
            f"{len(frame_paths)} fournie(s)."
        )

    canvas = pdfcanvas.Canvas(str(output_path), pagesize=A4)

    centers_mm = corner_marker_centers_mm()
    half = MARKER_SIZE_MM / 2
    # PRINTED_MARKER_IDS is the printing policy (story 4.4): iterating the
    # centers dict directly would bypass it and let the policy rot unused.
    for marker_id in PRINTED_MARKER_IDS:
        if marker_id not in centers_mm:
            raise ValueError(
                f"Le marqueur ArUco {marker_id} figure dans PRINTED_MARKER_IDS mais "
                "n'a pas de position physique dans corner_marker_centers_mm(): "
                "la politique d'impression et la geometrie des centres ont diverge."
            )
        cx, cy = centers_mm[marker_id]
        marker_array = generate_aruco_marker_image(marker_id)
        marker_image = ImageReader(Image.fromarray(marker_array))
        x_pt, y_pt = _mm_to_pdf_point(cx - half, cy + half)
        canvas.drawImage(
            marker_image,
            x_pt,
            y_pt,
            width=MARKER_SIZE_MM * mm,
            height=MARKER_SIZE_MM * mm,
        )

    for index, zone in enumerate(FRAME_ZONES_MM):
        x_pt, y_pt = _mm_to_pdf_point(zone["x"], zone["y"] + zone["height"])
        width_pt = zone["width"] * mm
        height_pt = zone["height"] * mm

        if frame_paths is not None:
            frame_image = ImageReader(str(frame_paths[index]))
            canvas.drawImage(
                frame_image,
                x_pt,
                y_pt,
                width=width_pt,
                height=height_pt,
                preserveAspectRatio=False,
            )

        canvas.rect(x_pt, y_pt, width_pt, height_pt)

    canvas.setFont("Helvetica", 8)
    meta_text = f"Mixed Media Utility - POC patch sheet - dict={aruco_dictionary_name()}"
    if project_meta:
        meta_text += f" - {project_meta}"
    canvas.drawString(MARKER_MARGIN_MM * mm, 5 * mm, meta_text)

    canvas.showPage()
    canvas.save()
    return output_path
