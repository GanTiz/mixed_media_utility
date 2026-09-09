"""Story 5.0: le chemin scan du POC ne tronque plus silencieusement a 8 bits.

Ces tests portent l'invariant de la story: aucune troncature de profondeur,
aucune perte d'alpha, aucune montee en profondeur non declaree entre le fichier
scan lu et les frames rescannees ecrites.

Trois pieges structurent le fichier et expliquent sa forme:

1. **Croire le retour de la fonction.** Toute verification de profondeur passe
   par une relecture du fichier avec ``IMREAD_UNCHANGED``, jamais par la valeur
   rendue par le code sous test -- c'est precisement ce que l'ancien
   ``cv2.imread(str(frame_path))`` du test d'aruco ne faisait pas.
2. **La fixture 16 bits fabriquee en multipliant un 8 bits par 257.** Une image
   dont toutes les valeurs sont des multiples de 257 traverse le defaut *sans
   dommage detectable*: ``imread`` sans flag ramene ``v`` a ``round(v/257)``,
   puis l'export la remonte par ``x257`` -- identite exacte sur ces valeurs. La
   fixture doit donc porter, dans les zones de frame, des valeurs qui ne sont
   pas des multiples de 257 (voir ``ZONE_FILLS_BGR``).
3. **Le temoin neutre.** ``cv2.imwrite`` interprete toujours le tableau comme
   BGR et ``validate_bgr_input`` ne peut pas detecter une inversion R/B. Un
   temoin gris validerait un pipeline qui echange les canaux: les deux zones
   portent donc des dominantes opposees, bleue et rouge.

Le test principal passe par ``cli.main(["poc", "process-scan", ...])``, c'est-a-
dire par le vrai producteur, et non par un appel direct a
``extract_scan_frames`` (action item 3 de la retro Epic 4). Le manifest legacy
est ecrit a la main plutot que produit par ``poc build-sheet``, ce qui evite de
rendre ce test dependant de ffmpeg.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import cli, layout
from mixed_media_utility.detection import aruco as aruco_detection


FIXTURE_SCAN = REPO_ROOT / "tests" / "fixtures" / "aruco" / "simple_scan.png"

SCAN_DPI = 150

# Remplissages BGR des deux zones de frame de la fixture 16 bits.
#
# Aucune composante n'est un multiple de 257 (piege 2): 4000, 8000, 60000, 1000
# et 2000 ressortiraient respectivement a 4112, 7967, 59881, 1028 et 2056 apres
# un aller-retour par une lecture 8 bits, ecart largement au-dela du bruit
# d'interpolation. Note: `65535` -- cite en exemple dans la story -- est en
# revanche exactement `255 x 257`, donc invariant par la troncature; il ne peut
# pas servir de temoin et n'est pas utilise ici.
#
# Les dominantes sont opposees (zone 1 bleue, zone 2 rouge) pour qu'une
# inversion R/B soit detectee dans les deux sens (piege 3).
ZONE_FILLS_BGR = (
    (60000, 4000, 8000),  # zone 1: dominante bleue
    (1000, 2000, 60000),  # zone 2: dominante rouge, le temoin rouge de la story
)


def _upscale_to_uint16(image8: np.ndarray) -> np.ndarray:
    """Monter un 8 bits en 16 bits pour servir de support de fixture.

    Les marqueurs ArUco restent lisibles dans la vue 8 bits derivee, et les
    zones de frame sont ensuite repeintes avec des valeurs qui, elles, ne
    survivent pas a une troncature.
    """
    return image8.astype(np.uint16) * 257


def _zone_quads_in_scan_space(markers_document: dict, dpi: int) -> list[np.ndarray]:
    """Projeter chaque zone de frame de l'espace page vers l'espace scan.

    L'homographie rendue par ``compute_page_homography`` va du scan vers la page
    redressee; son inverse ramene donc un rectangle de zone dans le repere du
    fichier scan, ou la fixture peut le peindre.
    """
    homography, _width_px, _height_px = aruco_detection.compute_page_homography(
        markers_document, dpi
    )
    inverse = np.linalg.inv(homography)

    quads = []
    for zone in layout.FRAME_ZONES_MM:
        x_px, y_px = layout.mm_to_px(zone["x"], zone["y"], dpi)
        w_px, _ = layout.mm_to_px(zone["width"], 0, dpi)
        _, h_px = layout.mm_to_px(0, zone["height"], dpi)
        rectangle = np.array(
            [
                [[x_px, y_px]],
                [[x_px + w_px, y_px]],
                [[x_px + w_px, y_px + h_px]],
                [[x_px, y_px + h_px]],
            ],
            dtype=np.float32,
        )
        quad = cv2.perspectiveTransform(rectangle, inverse).reshape(-1, 2)
        quads.append(np.round(quad).astype(np.int32))
    return quads


def _build_scan16(destination: Path, *, channels: int = 3) -> Path:
    """Ecrire une fixture de scan TIFF 16 bits aux zones de frame repeintes.

    ``channels`` vaut 3 (BGR), 1 (gris) ou 4 (BGRA) pour couvrir les entrees que
    ``IMREAD_UNCHANGED`` peut desormais rendre la ou ``IMREAD_COLOR`` forcait
    tout en 3 canaux 8 bits.
    """
    base8 = cv2.imread(str(FIXTURE_SCAN))
    assert base8 is not None, f"Fixture scan introuvable ou illisible: {FIXTURE_SCAN}"

    corners, ids = aruco_detection.detect_markers(base8, dpi=SCAN_DPI)
    markers_document = aruco_detection.build_markers_document(
        "inputs/simple_scan.png", corners, ids
    )

    scan16 = _upscale_to_uint16(base8)
    for quad, fill in zip(_zone_quads_in_scan_space(markers_document, SCAN_DPI), ZONE_FILLS_BGR):
        cv2.fillConvexPoly(scan16, quad, fill)

    if channels == 1:
        # Moyenne des 3 canaux: garde les marqueurs contrastes et conserve des
        # valeurs non multiples de 257 dans les zones.
        scan16 = scan16.mean(axis=2).round().astype(np.uint16)
    elif channels == 4:
        alpha = np.full(scan16.shape[:2], 40000, dtype=np.uint16)
        scan16 = np.dstack([scan16, alpha])
    elif channels != 3:
        raise ValueError(f"Nombre de canaux non prevu par la fixture: {channels}")

    assert cv2.imwrite(str(destination), scan16), f"Ecriture de la fixture echouee: {destination}"
    return destination


def _write_legacy_manifest(project_dir: Path) -> Path:
    """Ecrire a la main le manifest legacy minimal attendu par `process-scan`.

    Passer par `poc build-sheet` exigerait ffmpeg et rendrait le test principal
    de la story skippable sur une machine sans binaire.
    """
    project_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = project_dir / "project.json"
    manifest_path.write_text(
        json.dumps(
            {
                "id": "poc-bit-depth",
                "created": "2026-08-07T00:00:00Z",
                "inputs": {"raw": "inputs", "frames": "frames"},
                "calibration": "calibration",
                "artifacts": "outputs",
                "meta": {
                    "color": {"target_colorspace": "rec709"},
                    "lot": {"state": "pdf", "expected_frame_count": 2},
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return manifest_path


def _run_process_scan(project_dir: Path, scan_path: Path) -> int:
    return cli.main(
        [
            "poc",
            "process-scan",
            "--project",
            str(project_dir),
            "--scan",
            str(scan_path),
            "--dpi",
            str(SCAN_DPI),
        ]
    )


def _center_patch(image: np.ndarray) -> np.ndarray:
    """Extraire le quart central d'une frame.

    Le warp interpole: les bords d'une zone se melangent au fond de la page. Le
    centre d'une zone uniformement remplie, lui, garde la valeur exacte.
    """
    height, width = image.shape[:2]
    return image[height // 3 : 2 * height // 3, width // 3 : 2 * width // 3]


@pytest.fixture
def scan16_project(tmp_path: Path) -> tuple[Path, Path]:
    project_dir = tmp_path / "projet"
    manifest_path = _write_legacy_manifest(project_dir)
    scan_path = _build_scan16(tmp_path / "scan16.tiff")
    return project_dir, manifest_path, scan_path


# --------------------------------------------------------------------------
# La fixture elle-meme est sous test: sans cette garde, le piege 2 rendrait
# tous les tests de profondeur ci-dessous vrais par accident.
# --------------------------------------------------------------------------


def test_fixture_fill_values_are_not_multiples_of_257() -> None:
    for fill in ZONE_FILLS_BGR:
        for component in fill:
            assert component % 257 != 0, (
                f"{component} est un multiple de 257: cette valeur traverse une "
                "troncature 8 bits sans dommage detectable et ne peut pas servir "
                "de temoin de profondeur."
            )


def test_fixture_scan_is_really_16_bit_with_non_truncatable_zones(tmp_path: Path) -> None:
    scan_path = _build_scan16(tmp_path / "scan16.tiff")
    reread = cv2.imread(str(scan_path), cv2.IMREAD_UNCHANGED)

    assert reread.dtype == np.uint16
    present = set(np.unique(reread).tolist())
    for fill in ZONE_FILLS_BGR:
        for component in fill:
            assert component in present, (
                f"La valeur temoin {component} n'a pas survecu a l'ecriture de la "
                "fixture: le test de profondeur qui s'appuie dessus serait vide."
            )


# --------------------------------------------------------------------------
# Non-regression de profondeur de bout en bout, par le vrai producteur.
# --------------------------------------------------------------------------


def test_process_scan_preserves_16_bit_depth_end_to_end(scan16_project) -> None:
    project_dir, _manifest_path, scan_path = scan16_project

    assert _run_process_scan(project_dir, scan_path) == 0

    frames = sorted((project_dir / "outputs").glob("scan_frame_*.tiff"))
    assert [frame.name for frame in frames] == [
        "scan_frame_0001.tiff",
        "scan_frame_0002.tiff",
    ]
    assert not list((project_dir / "outputs").glob("scan_frame_*.png"))

    for frame_path, expected_bgr in zip(frames, ZONE_FILLS_BGR):
        written = cv2.imread(str(frame_path), cv2.IMREAD_UNCHANGED)
        assert written is not None, f"Frame illisible: {frame_path}"
        assert written.dtype == np.uint16, (
            f"{frame_path.name} relu en {written.dtype}: la profondeur a ete "
            "tronquee quelque part sur le chemin scan."
        )

        centre = _center_patch(written)
        observed_bgr = tuple(int(value) for value in np.median(centre.reshape(-1, 3), axis=0))
        assert observed_bgr == expected_bgr, (
            f"{frame_path.name}: valeurs centrales {observed_bgr}, attendu "
            f"{expected_bgr}. Un aller-retour par 8 bits aurait rendu "
            f"{tuple(round(v / 257) * 257 for v in expected_bgr)}."
        )
        for component in observed_bgr:
            assert component % 257 != 0, (
                f"{frame_path.name}: la composante {component} est un multiple de "
                "257, signature d'une reduction a 8 bits suivie d'un x257."
            )


def test_process_scan_keeps_the_red_witness_red(scan16_project) -> None:
    """Temoin asymetrique: un temoin gris ne detecterait pas une inversion R/B."""
    project_dir, _manifest_path, scan_path = scan16_project

    assert _run_process_scan(project_dir, scan_path) == 0

    frames = sorted((project_dir / "outputs").glob("scan_frame_*.tiff"))
    blue_zone = _center_patch(cv2.imread(str(frames[0]), cv2.IMREAD_UNCHANGED))
    red_zone = _center_patch(cv2.imread(str(frames[1]), cv2.IMREAD_UNCHANGED))

    blue_b, _blue_g, blue_r = (int(v) for v in np.median(blue_zone.reshape(-1, 3), axis=0))
    red_b, _red_g, red_r = (int(v) for v in np.median(red_zone.reshape(-1, 3), axis=0))

    assert blue_b > 3 * blue_r, f"Zone 1 attendue bleue, relue B={blue_b} R={blue_r}"
    assert red_r > 3 * red_b, f"Zone 2 attendue rouge, relue B={red_b} R={red_r}"


def test_process_scan_writes_depth_fields_matching_the_files_on_disk(scan16_project) -> None:
    project_dir, manifest_path, scan_path = scan16_project

    assert _run_process_scan(project_dir, scan_path) == 0

    color_meta = json.loads(manifest_path.read_text(encoding="utf-8"))["meta"]["color"]
    assert color_meta["source_bit_depth"] == 16
    assert color_meta["output_bit_depth"] == 16
    assert color_meta["output_format"] == "tiff"
    assert color_meta["scan_input_format"] == "tiff"
    # Champ prealable, laisse intact par la story.
    assert color_meta["target_colorspace"] == "rec709"

    # Le manifest ne doit pas pouvoir diverger de l'artefact reel.
    for frame_path in sorted((project_dir / "outputs").glob("scan_frame_*.tiff")):
        written = cv2.imread(str(frame_path), cv2.IMREAD_UNCHANGED)
        assert written.dtype == np.uint16
        assert frame_path.suffix.lstrip(".") == color_meta["output_format"]


def test_process_scan_declares_an_8_bit_source_as_8_bit(tmp_path: Path) -> None:
    """Retablir le 16 bits n'est pas en fabriquer.

    Un scan 8 bits est monte a 16 bits (contrat d'acquisition), mais le manifest
    declare la source a 8: sans ce champ, un 16 bits gonfle -- 256 niveaux sur
    65536 -- serait indistinguable d'un vrai 16 bits, et l'expansion de gamut
    l'amplifierait en bandes visibles.
    """
    project_dir = tmp_path / "projet"
    manifest_path = _write_legacy_manifest(project_dir)

    assert _run_process_scan(project_dir, FIXTURE_SCAN) == 0

    color_meta = json.loads(manifest_path.read_text(encoding="utf-8"))["meta"]["color"]
    assert color_meta["source_bit_depth"] == 8
    assert color_meta["output_bit_depth"] == 16
    assert color_meta["scan_input_format"] == "png"

    for frame_path in sorted((project_dir / "outputs").glob("scan_frame_*.tiff")):
        written = cv2.imread(str(frame_path), cv2.IMREAD_UNCHANGED)
        assert written.dtype == np.uint16


def test_process_scan_still_refuses_an_unreadable_scan(tmp_path: Path) -> None:
    project_dir = tmp_path / "projet"
    _write_legacy_manifest(project_dir)
    broken_scan = tmp_path / "broken.tiff"
    broken_scan.write_bytes(b"ceci n'est pas une image")

    assert _run_process_scan(project_dir, broken_scan) == 1


# --------------------------------------------------------------------------
# Gris et alpha: `IMREAD_COLOR` les ecrasait, `IMREAD_UNCHANGED` les conserve.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("channels", [1, 4])
def test_process_scan_preserves_channel_cardinality(tmp_path: Path, channels: int) -> None:
    project_dir = tmp_path / f"projet-{channels}"
    _write_legacy_manifest(project_dir)
    scan_path = _build_scan16(tmp_path / f"scan16-{channels}.tiff", channels=channels)

    assert _run_process_scan(project_dir, scan_path) == 0

    frames = sorted((project_dir / "outputs").glob("scan_frame_*.tiff"))
    assert len(frames) == len(layout.FRAME_ZONES_MM)
    for frame_path in frames:
        written = cv2.imread(str(frame_path), cv2.IMREAD_UNCHANGED)
        assert written.dtype == np.uint16
        observed_channels = 1 if written.ndim == 2 else written.shape[2]
        assert observed_channels == channels, (
            f"{frame_path.name}: {observed_channels} canaux relus, {channels} attendus. "
            "Un scan gris doit rester gris, un scan avec alpha garder son alpha."
        )


def test_process_scan_keeps_the_alpha_channel_value(tmp_path: Path) -> None:
    project_dir = tmp_path / "projet-bgra"
    _write_legacy_manifest(project_dir)
    scan_path = _build_scan16(tmp_path / "scan16-bgra.tiff", channels=4)

    assert _run_process_scan(project_dir, scan_path) == 0

    frames = sorted((project_dir / "outputs").glob("scan_frame_*.tiff"))
    written = cv2.imread(str(frames[0]), cv2.IMREAD_UNCHANGED)
    alpha = _center_patch(written)[..., 3]
    assert int(np.median(alpha)) == 40000


def test_extract_scan_frames_refuses_an_unsupported_channel_count(tmp_path: Path) -> None:
    """Un cardinal de canaux non supporte est refuse, jamais converti en silence."""
    width_px, height_px = layout.page_size_px(SCAN_DPI)
    two_channel_page = np.zeros((height_px, width_px, 2), dtype=np.uint16)

    with pytest.raises(aruco_detection.ScanFrameExtractionError) as excinfo:
        aruco_detection.extract_scan_frames(two_channel_page, SCAN_DPI, tmp_path / "outputs")

    assert "canaux" in str(excinfo.value)


# --------------------------------------------------------------------------
# Vue de detection et rejeu.
# --------------------------------------------------------------------------


def test_detect_markers_accepts_a_16_bit_image_without_altering_it() -> None:
    """`cv2.aruco` refuse le 16 bits; la reduction reste locale a la detection."""
    base8 = cv2.imread(str(FIXTURE_SCAN))
    scan16 = _upscale_to_uint16(base8)
    before = scan16.copy()

    _corners, ids = aruco_detection.detect_markers(scan16, dpi=SCAN_DPI)

    assert ids is not None
    assert {int(marker_id) for marker_id in ids.flatten()} == set(layout.CORNER_MARKER_IDS)
    # La vue derivee ne remonte jamais dans le tableau porteur de pixels.
    assert scan16.dtype == np.uint16
    assert np.array_equal(scan16, before)


def test_detection_view_reduces_only_the_depth() -> None:
    scan16 = np.array([[[0, 4000, 60000]]], dtype=np.uint16)

    view = aruco_detection.as_detection_view(scan16)

    assert view.dtype == np.uint8
    assert view.shape == scan16.shape
    assert view.tolist() == [[[0, 4000 >> 8, 60000 >> 8]]]


@pytest.mark.parametrize("byte_order", ["<u2", ">u2"])
def test_detection_view_handles_both_byte_orders(byte_order: str) -> None:
    """Un scanner ecrivant en byte order `MM` produit du `>u2`.

    Le resultat est confronte a une valeur litterale attendue, et non a l'autre
    ordre d'octets: une comparaison entre les deux appels resterait verte meme
    si les deux etaient faux ensemble. `cv2.imread` ne rend jamais de tableau
    non natif, donc seul un appelant construisant son tableau a la main atteint
    la branche `>u2` — ce que fait `validate_bgr_input`, qui la traite aussi.
    """
    scan16 = np.array([[[0, 4000, 60000]]], dtype=byte_order)

    view = aruco_detection.as_detection_view(scan16)

    assert view.dtype == np.uint8
    assert view.tolist() == [[[0, 15, 234]]]


@pytest.mark.parametrize(
    "dtype",
    [np.float32, np.float64, np.int16, np.int32, np.uint32],
)
def test_detection_view_refuses_depths_cv2_aruco_cannot_take(dtype) -> None:
    """Refus explicite plutot qu'une assertion `cv2.error` nue.

    `IMREAD_UNCHANGED` elargit l'ensemble des profondeurs qui atteignent la
    detection: un TIFF 32 bits flottant, un `.hdr` ou un `.pfm` ressortent en
    `float32` la ou `cv2.imread` nu rendait `None` ou un `uint8` converti en
    silence. La politique est celle de `pdf_render.load_frame_image_for_print`:
    refuser, jamais convertir a la place de l'operateur.
    """
    with pytest.raises(aruco_detection.UnsupportedScanDepthError) as excinfo:
        aruco_detection.as_detection_view(np.zeros((4, 4, 3), dtype=dtype))

    assert str(np.dtype(dtype)) in str(excinfo.value)


def test_process_scan_refuses_a_floating_point_scan_with_an_actionable_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Regression du chemin d'erreur: code de sortie 1, pas de traceback.

    Avant la story, `cv2.imread` nu rendait `None` sur ce fichier et la CLI
    repondait « Impossible de lire l'image scan ». Il ne doit pas ressortir en
    assertion OpenCV maintenant que la lecture le decode reellement.
    """
    project_dir = tmp_path / "projet"
    _write_legacy_manifest(project_dir)
    float_scan = tmp_path / "scan32.tiff"
    base8 = cv2.imread(str(FIXTURE_SCAN))
    assert cv2.imwrite(str(float_scan), base8.astype(np.float32))
    assert cv2.imread(str(float_scan), cv2.IMREAD_UNCHANGED).dtype == np.float32

    assert _run_process_scan(project_dir, float_scan) == 1

    captured = capsys.readouterr()
    assert "Profondeur de pixel non geree" in captured.out + captured.err
    assert not list((project_dir / "outputs").glob("scan_frame_*"))


def test_extract_scan_frames_purges_stale_outputs_of_both_extensions(tmp_path: Path) -> None:
    """Un rejeu ne laisse aucun residu 8 bits a cote des TIFF.

    La casse compte: la garde d'ecriture de `color_pipeline` est insensible a la
    casse, donc un `scan_frame_0002.TIFF` a bel et bien pu etre ecrit par un run
    anterieur et doit etre purge comme les autres.
    """
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    stale = []
    for name in (
        "scan_frame_0001.png",
        "scan_frame_0009.tiff",
        "scan_frame_0010.PNG",
        "scan_frame_0011.TIFF",
        "scan_frame_0012.tif",
    ):
        path = output_dir / name
        path.write_bytes(b"residu")
        stale.append(path)
    preserved = output_dir / "autre_fichier.png"
    preserved.write_bytes(b"hors perimetre de purge")
    # Un sous-dossier portant un nom de sortie ne doit pas faire lever
    # `IsADirectoryError` a `unlink()`.
    stale_dir = output_dir / "scan_frame_0099.png"
    stale_dir.mkdir()

    width_px, height_px = layout.page_size_px(SCAN_DPI)
    page = np.full((height_px, width_px, 3), 4000, dtype=np.uint16)
    aruco_detection.extract_scan_frames(page, SCAN_DPI, output_dir)

    for path in stale:
        assert not path.exists(), f"{path.name} aurait du etre purge"
    assert preserved.exists()
    assert stale_dir.is_dir()
    assert sorted(path.name for path in output_dir.glob("scan_frame_*") if path.is_file()) == [
        "scan_frame_0001.tiff",
        "scan_frame_0002.tiff",
    ]


def test_scan_input_format_never_writes_an_empty_string(tmp_path: Path) -> None:
    """Un scan sans extension n'a aucun format declare: le dire, pas le taire.

    La chaine vide est refusee par `mvp_color_manifest_fragment` pour ce meme
    champ; l'ecrire ici ferait echouer un consommateur aval sur une valeur que
    le POC aurait produite en silence.
    """
    project_dir = tmp_path / "projet"
    manifest_path = _write_legacy_manifest(project_dir)
    extensionless = tmp_path / "scan_sans_extension"
    extensionless.write_bytes(FIXTURE_SCAN.read_bytes())

    assert _run_process_scan(project_dir, extensionless) == 0

    color_meta = json.loads(manifest_path.read_text(encoding="utf-8"))["meta"]["color"]
    assert color_meta["scan_input_format"] == cli.UNKNOWN_SCAN_FORMAT
    assert color_meta["scan_input_format"]


def test_process_scan_refuses_a_non_object_color_section(tmp_path: Path) -> None:
    """`meta` est libre dans le schema legacy: `meta.color` peut ne pas etre un objet."""
    project_dir = tmp_path / "projet"
    manifest_path = _write_legacy_manifest(project_dir)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["meta"]["color"] = "rec709"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    assert _run_process_scan(project_dir, FIXTURE_SCAN) == 1
