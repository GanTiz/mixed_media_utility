from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import layout
from mixed_media_utility.detection import aruco as aruco_detection


FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "aruco" / "simple_scan.png"

# DPI de la fixture, celui que les tests d'homographie de ce fichier utilisent
# deja. Il est exige par `detect_markers` depuis la correction du 2026-08-10:
# c'est lui qui dimensionne le seuillage adaptatif sur le module imprime.
FIXTURE_DPI = 150


@pytest.fixture
def scan_image() -> np.ndarray:
    image = cv2.imread(str(FIXTURE_PATH))
    assert image is not None, f"Fixture scan introuvable ou illisible: {FIXTURE_PATH}"
    return image


def test_detect_markers_finds_expected_corner_ids(scan_image: np.ndarray) -> None:
    corners, ids = aruco_detection.detect_markers(scan_image, dpi=FIXTURE_DPI)

    assert ids is not None
    detected_ids = set(ids.flatten().tolist())
    # Superset, not equality: story 4.3 reserves ID ranges for optional template
    # and slot markers, so a future sheet may legitimately carry extra markers.
    # Asserting equality here would make that extension fail the test suite.
    assert detected_ids >= set(layout.CORNER_MARKER_IDS)
    assert all(layout.marker_role(i) != layout.UNASSIGNED_ROLE for i in detected_ids)
    assert len(corners) == len(ids)


def test_build_markers_document_structure(scan_image: np.ndarray) -> None:
    corners, ids = aruco_detection.detect_markers(scan_image, dpi=FIXTURE_DPI)

    document = aruco_detection.build_markers_document("inputs/simple_scan.png", corners, ids)

    assert list(document.keys()) == ["images"]
    assert len(document["images"]) == 1
    image_entry = document["images"][0]
    assert image_entry["path"] == "inputs/simple_scan.png"
    assert [marker["id"] for marker in image_entry["markers"]] == sorted(layout.CORNER_MARKER_IDS)
    for marker in image_entry["markers"]:
        assert len(marker["corners"]) == 4
        assert all(len(point) == 2 for point in marker["corners"])
        assert len(marker["center"]) == 2


def test_compute_page_homography_and_extract_scan_frames(tmp_path: Path, scan_image: np.ndarray) -> None:
    corners, ids = aruco_detection.detect_markers(scan_image, dpi=FIXTURE_DPI)
    document = aruco_detection.build_markers_document("inputs/simple_scan.png", corners, ids)

    dpi = 150
    homography, width_px, height_px = aruco_detection.compute_page_homography(document, dpi)
    assert homography.shape == (3, 3)
    assert (width_px, height_px) == layout.page_size_px(dpi)

    warped = aruco_detection.warp_page(scan_image, homography, width_px, height_px)
    assert warped.shape[:2] == (height_px, width_px)

    output_dir = tmp_path / "outputs"
    scan_frames = aruco_detection.extract_scan_frames(warped, dpi, output_dir)

    # Story 5.0: `extract_scan_frames` rend desormais un dict par frame (chemin
    # + profondeurs + format reellement ecrits), et non plus une liste de Path:
    # les champs de profondeur du manifest doivent venir de l'export lui-meme.
    assert len(scan_frames) == len(layout.FRAME_ZONES_MM)
    assert [Path(frame["path"]).name for frame in scan_frames] == [
        f"scan_frame_{index:04d}.tiff" for index in range(1, len(layout.FRAME_ZONES_MM) + 1)
    ]
    for frame in scan_frames:
        frame_path = Path(frame["path"])
        assert frame_path.is_file()
        # Relecture avec IMREAD_UNCHANGED: la version precedente de ce test
        # relisait sans flag, donc en 8 bits, et serait restee verte sur une
        # sortie tronquee -- le defaut sous test etait dans le test lui-meme.
        cropped = cv2.imread(str(frame_path), cv2.IMREAD_UNCHANGED)
        assert cropped is not None
        assert cropped.size > 0
        assert cropped.dtype == np.uint16
        assert frame["output_bit_depth"] == 16
        assert frame["output_format"] == "tiff"
        # La fixture est un PNG 8 bits: la source est bien declaree comme telle.
        assert frame["source_bit_depth"] == 8


def test_compute_page_homography_raises_when_markers_missing() -> None:
    empty_document = {"images": [{"path": "no-markers.png", "markers": []}]}

    with pytest.raises(aruco_detection.MissingMarkersError):
        aruco_detection.compute_page_homography(empty_document, dpi=150)


def test_compute_page_homography_raises_when_one_corner_missing() -> None:
    # MVP policy (story 4.3): all 4 corners are mandatory, no 3-corner
    # affine fallback. A single missing corner must still fail explicitly.
    partial_document = {
        "images": [
            {
                "path": "partial-scan.png",
                "markers": [
                    {"id": 0, "corners": [[0, 0], [1, 0], [1, 1], [0, 1]], "center": [0.5, 0.5]},
                    {"id": 1, "corners": [[9, 0], [10, 0], [10, 1], [9, 1]], "center": [9.5, 0.5]},
                    {"id": 2, "corners": [[9, 9], [10, 9], [10, 10], [9, 10]], "center": [9.5, 9.5]},
                ],
            }
        ]
    }

    with pytest.raises(aruco_detection.MissingMarkersError):
        aruco_detection.compute_page_homography(partial_document, dpi=150)


def test_compute_page_homography_ignores_foreign_markers(scan_image: np.ndarray) -> None:
    # Detection policy stated by story 4.4 (layout.py contract block, normative
    # copy): a reserved-range or unassigned marker detected on a scan is never
    # fed into the homography. The behaviour predates its test -- the 4.4
    # review found nothing locking it, so a refactor injecting every detected
    # center would have passed the suite. The warning half of the policy is
    # implemented by story 5.2 (see deferred-work.md).
    corners, ids = aruco_detection.detect_markers(scan_image, dpi=FIXTURE_DPI)
    document = aruco_detection.build_markers_document("inputs/simple_scan.png", corners, ids)
    reference, _, _ = aruco_detection.compute_page_homography(document, dpi=150)

    polluted = {
        "images": [
            {
                "path": document["images"][0]["path"],
                "markers": document["images"][0]["markers"]
                + [
                    # One reserved template-variant ID, one reserved slot ID and
                    # one unassigned ID, far from the true corners.
                    {"id": 10, "corners": [[5, 5]] * 4, "center": [5.0, 5.0]},
                    {"id": 25, "corners": [[9, 9]] * 4, "center": [9.0, 9.0]},
                    {"id": 5, "corners": [[3, 7]] * 4, "center": [3.0, 7.0]},
                ],
            }
        ]
    }
    polluted_homography, _, _ = aruco_detection.compute_page_homography(polluted, dpi=150)

    assert np.allclose(polluted_homography, reference)


def test_aruco_role_id_ranges_do_not_overlap() -> None:
    corner_ids = set(layout.CORNER_MARKER_IDS)
    template_ids = set(layout.TEMPLATE_VARIANT_ID_RANGE)
    slot_ids = set(layout.SLOT_MARKER_ID_RANGE)

    assert corner_ids.isdisjoint(template_ids)
    assert corner_ids.isdisjoint(slot_ids)
    assert template_ids.isdisjoint(slot_ids)


def test_aruco_role_id_ranges_fit_within_dictionary_size() -> None:
    # Derive the bound from the dictionary actually configured, so that switching
    # layout.ARUCO_DICTIONARY to a smaller dictionary (e.g. DICT_4X4_50) fails this
    # test instead of silently overflowing the reserved slot range.
    dictionary = cv2.aruco.getPredefinedDictionary(layout.ARUCO_DICTIONARY)
    dictionary_size = dictionary.bytesList.shape[0]

    max_reserved_id = max(
        max(layout.CORNER_MARKER_IDS),
        max(layout.TEMPLATE_VARIANT_ID_RANGE),
        max(layout.SLOT_MARKER_ID_RANGE),
    )
    assert max_reserved_id < dictionary_size


def test_min_corner_markers_required_governs_runtime_policy() -> None:
    # Behavioural counterpart to the constant: with one corner short of
    # MIN_CORNER_MARKERS_REQUIRED, compute_page_homography must refuse.
    corner_ids = list(layout.CORNER_MARKER_IDS)
    centers = [(100.0, 100.0), (700.0, 100.0), (700.0, 880.0), (100.0, 880.0)]
    kept = corner_ids[: layout.MIN_CORNER_MARKERS_REQUIRED - 1]

    document = _markers_document(
        [(marker_id, centers[index]) for index, marker_id in enumerate(corner_ids) if marker_id in kept]
    )

    with pytest.raises(aruco_detection.MissingMarkersError):
        aruco_detection.compute_page_homography(document, dpi=150)


def _markers_document(id_center_pairs) -> dict:
    return {
        "images": [
            {
                "path": "synthetic-scan.png",
                "markers": [
                    {
                        "id": marker_id,
                        "corners": [[0, 0], [1, 0], [1, 1], [0, 1]],
                        "center": [float(x), float(y)],
                    }
                    for marker_id, (x, y) in id_center_pairs
                ],
            }
        ]
    }


def test_compute_page_homography_accepts_strong_perspective() -> None:
    # Guard against the degeneracy check being too strict: a heavily skewed but
    # perfectly valid page must still be accepted.
    document = _markers_document(
        zip(layout.CORNER_MARKER_IDS, [(150, 100), (700, 140), (660, 880), (110, 830)])
    )

    homography, _width, _height = aruco_detection.compute_page_homography(document, dpi=150)

    assert homography.shape == (3, 3)


def test_compute_page_homography_rejects_collinear_corners() -> None:
    # Regression: cv2.findHomography returns a rank-deficient matrix (never None)
    # when 3 of the 4 centers are collinear -- a folded page or a grazing capture
    # angle. Left unguarded it warps to a plausible-looking but meaningless page.
    document = _markers_document(
        zip(layout.CORNER_MARKER_IDS, [(100, 100), (200, 100), (300, 100), (100, 900)])
    )

    with pytest.raises(aruco_detection.DegeneratePageGeometryError):
        aruco_detection.compute_page_homography(document, dpi=150)


def test_compute_page_homography_rejects_non_convex_corners() -> None:
    # A corner pulled inside the other three yields a self-intersecting quad:
    # the homography is computable but the corner assignment is wrong.
    document = _markers_document(
        zip(layout.CORNER_MARKER_IDS, [(400, 500), (700, 100), (700, 880), (100, 880)])
    )

    with pytest.raises(aruco_detection.DegeneratePageGeometryError):
        aruco_detection.compute_page_homography(document, dpi=150)


def test_compute_page_homography_rejects_duplicated_corner_ids() -> None:
    # Regression: markers_by_id was a dict comprehension, so a duplicated corner ID
    # silently overwrote the genuine corner (second sheet on the glass, neighbouring
    # page in frame) and the homography was computed on the wrong geometry.
    pairs = list(zip(layout.CORNER_MARKER_IDS, [(100, 100), (700, 100), (700, 880), (100, 880)]))
    pairs.append((layout.CORNER_MARKER_IDS[0], (400.0, 500.0)))
    document = _markers_document(pairs)

    with pytest.raises(aruco_detection.AmbiguousMarkersError):
        aruco_detection.compute_page_homography(document, dpi=150)


def test_page_geometry_errors_share_a_catchable_base() -> None:
    # The CLI catches PageGeometryError; every rejection reason must be covered.
    for error_type in (
        aruco_detection.MissingMarkersError,
        aruco_detection.AmbiguousMarkersError,
        aruco_detection.DegeneratePageGeometryError,
    ):
        assert issubclass(error_type, aruco_detection.PageGeometryError)


def test_marker_role_classifies_every_reserved_range() -> None:
    assert layout.marker_role(layout.CORNER_MARKER_IDS[0]) == layout.CORNER_ROLE
    assert layout.marker_role(min(layout.TEMPLATE_VARIANT_ID_RANGE)) == layout.TEMPLATE_VARIANT_ROLE
    assert layout.marker_role(max(layout.SLOT_MARKER_ID_RANGE)) == layout.SLOT_ROLE
    # The gaps left between the reserved ranges must be reported as foreign, not
    # silently accepted: a marker there comes from another sheet.
    assert layout.marker_role(5) == layout.UNASSIGNED_ROLE
    assert layout.marker_role(200) == layout.UNASSIGNED_ROLE


def test_aruco_dictionary_name_is_derived_not_hardcoded() -> None:
    # The sheet footer prints this name; it must follow ARUCO_DICTIONARY.
    assert layout.aruco_dictionary_name() == "DICT_6X6_250"
    assert cv2.aruco.__dict__[layout.aruco_dictionary_name()] == layout.ARUCO_DICTIONARY


def test_printed_marker_ids_are_exactly_the_corners() -> None:
    # Story 4.4 decision (EPIC4-ARB-5): the MVP prints the 4 corner markers and
    # nothing else. Template-variant and slot ranges stay reserved with no
    # producer; margin and layout identification live in the QR payload
    # (template_id preset), never in ArUco IDs.
    #
    # PRINTED_MARKER_IDS aliases CORNER_MARKER_IDS today, so the equality alone
    # would be tautological (4.4 review): the substantial invariants checked
    # below are what actually holds the printing policy together with the
    # detection policy and the physical centers.
    assert tuple(layout.PRINTED_MARKER_IDS) == tuple(layout.CORNER_MARKER_IDS)
    assert all(
        layout.marker_role(marker_id) == layout.CORNER_ROLE
        for marker_id in layout.PRINTED_MARKER_IDS
    )
    # Every printed ID must have a physical position: PRINTED_MARKER_IDS and
    # corner_marker_centers_mm() are two hand-maintained sources that nothing
    # couples at runtime except generate_patch_sheet_pdf's lookup.
    centers = layout.corner_marker_centers_mm()
    assert set(layout.PRINTED_MARKER_IDS) <= set(centers)
    # A sheet printed with fewer corner-role markers than the scan-side minimum
    # would be silently unrecoverable paper: the printing policy must satisfy
    # the detection policy it feeds.
    corner_count = sum(
        1
        for marker_id in layout.PRINTED_MARKER_IDS
        if layout.marker_role(marker_id) == layout.CORNER_ROLE
    )
    assert corner_count >= layout.MIN_CORNER_MARKERS_REQUIRED
    assert len(set(layout.PRINTED_MARKER_IDS)) == len(tuple(layout.PRINTED_MARKER_IDS))


def test_generate_patch_sheet_pdf_prints_only_the_printed_marker_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Behavioural counterpart of PRINTED_MARKER_IDS: the sheet generator must
    # consume the constant, so the printing policy cannot silently diverge from
    # it (the "dead constant" failure mode flagged by the 4.3 review).
    #
    # The constant is patched to a strict subset of the corner IDs: with the
    # full set, an implementation iterating corner_marker_centers_mm() directly
    # (bypassing the constant) would draw the same IDs and pass -- the 4.4
    # review proved it by mutation. Only a subset makes the test discriminate
    # actual consumption of PRINTED_MARKER_IDS.
    drawn: list[int] = []
    real_generator = layout.generate_aruco_marker_image

    def recording_generator(marker_id: int, *args, **kwargs):
        drawn.append(marker_id)
        return real_generator(marker_id, *args, **kwargs)

    monkeypatch.setattr(layout, "generate_aruco_marker_image", recording_generator)
    monkeypatch.setattr(layout, "PRINTED_MARKER_IDS", (0, 2))
    output = layout.generate_patch_sheet_pdf(tmp_path / "sheet.pdf")

    assert output.is_file()
    assert sorted(drawn) == [0, 2]


def test_generate_patch_sheet_pdf_rejects_a_printed_id_without_center(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A printed ID with no physical center must fail with an explicit French
    # ValueError, not a bare KeyError (4.4 review: the generator's only
    # legitimate future evolution -- printing one more marker -- crashed in the
    # worst possible way).
    monkeypatch.setattr(layout, "PRINTED_MARKER_IDS", (0, 1, 2, 10))
    with pytest.raises(ValueError, match="position physique"):
        layout.generate_patch_sheet_pdf(tmp_path / "sheet.pdf")
