from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import cli, ffmpeg_utils
from mixed_media_utility.io import project_layout
from mixed_media_utility.io.manifest import validate_manifest


FIXTURE_SCAN = REPO_ROOT / "tests" / "fixtures" / "aruco" / "simple_scan.png"

requires_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None,
    reason="ffmpeg binary not available on PATH",
)


def _generate_synthetic_video(path: Path, size: str = "128x72", fps: int = 10, duration: int = 2) -> Path:
    command = [
        "ffmpeg",
        "-y",
        "-f", "lavfi",
        "-i", f"color=c=blue:s={size}:d={duration}:r={fps}",
        str(path),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return path


@pytest.fixture
def synthetic_video(tmp_path: Path) -> Path:
    # 128x72 is exactly 16:9 (matches the forced patch sheet frame zone ratio).
    return _generate_synthetic_video(tmp_path / "synthetic_source.mp4")


@pytest.fixture
def non_16x9_video(tmp_path: Path) -> Path:
    return _generate_synthetic_video(tmp_path / "synthetic_square.mp4", size="64x64")


class _FakeCapture:
    def __init__(self, width: float, height: float) -> None:
        self._width = width
        self._height = height

    def get(self, prop_id):
        if prop_id == cv2.CAP_PROP_FRAME_WIDTH:
            return self._width
        if prop_id == cv2.CAP_PROP_FRAME_HEIGHT:
            return self._height
        return 0

    def release(self):
        pass


def _build_sheet(project_dir: Path, video: Path, fps: str = "2", dpi: str = "150") -> int:
    return cli.main(
        [
            "poc", "build-sheet",
            "--project", str(project_dir),
            "--video", str(video),
            "--fps", fps,
            "--dpi", dpi,
        ]
    )


def _process_scan(project_dir: Path, scan: Path, dpi: str = "150") -> int:
    return cli.main(
        [
            "poc", "process-scan",
            "--project", str(project_dir),
            "--scan", str(scan),
            "--dpi", dpi,
        ]
    )


@requires_ffmpeg
def test_poc_roundtrip_build_sheet_then_process_scan(tmp_path: Path, synthetic_video: Path) -> None:
    project_dir = tmp_path / "poc_project"

    build_exit_code = _build_sheet(project_dir, synthetic_video)
    assert build_exit_code == 0

    # `EPIC11-ARB-225` : la liste du POC suit le renommage...
    for subdir in ("inputs", project_layout.EXTRACT_FRAMES_DIRNAME, "planches",
                   "detection", "outputs", "logs"):
        assert (project_dir / subdir).is_dir()

    # Story 2.5: the v2 base arborescence is also ensured alongside the
    # legacy POC subdirs above (additive, no regression on the POC baseline).
    assert (project_dir / "scans").is_dir()

    frame_files = sorted(
        (project_dir / project_layout.EXTRACT_FRAMES_DIRNAME).glob("frame_*.png"))
    assert len(frame_files) >= 2

    # ... mais le chemin de la planche du POC, lui, reste sous le nom d'avant :
    # `EPIC11-ARB-225` est muet sur ce site, et la sortie conservatrice est que
    # le POC continue d'ecrire ou il ecrivait (question en dette, 2026-09-06).
    patch_sheet = project_dir / "patches" / "patch_sheet.pdf"
    assert patch_sheet.is_file()
    assert patch_sheet.stat().st_size > 0

    manifest_path = project_dir / "project.json"
    assert manifest_path.is_file()
    manifest = validate_manifest(manifest_path)
    assert manifest["meta"]["dpi_print"] == 150
    assert manifest["meta"]["fps_extract"] == 2.0
    assert manifest["meta"]["video_source"] == "inputs/synthetic_source.mp4"
    # La CLE `sheet_frames` est GELEE (`EPIC11-ARB-221`) ; ses VALEURS sont des
    # chemins, donc elles portent le nom neuf. Un chemin se renomme, une cle de
    # document non.
    dossier = project_layout.EXTRACT_FRAMES_DIRNAME
    assert manifest["meta"]["sheet_frames"] == [
        f"{dossier}/frame_0001.png", f"{dossier}/frame_0002.png"]
    assert "scan_source" not in manifest["meta"]

    # Story 2.2: metadonnees techniques et etat de lot transitoires.
    assert manifest["meta"]["video"]["resolution_source"] == {"width": 128, "height": 72}
    assert manifest["meta"]["video"]["fps_target"] == 2.0
    assert manifest["meta"]["color"]["target_colorspace"] == "rec709"
    assert manifest["meta"]["lot"] == {"state": "pdf", "expected_frame_count": 2}

    process_exit_code = _process_scan(project_dir, FIXTURE_SCAN)
    assert process_exit_code == 0

    markers_path = project_dir / "detection" / "markers.json"
    assert markers_path.is_file()
    markers_doc = json.loads(markers_path.read_text(encoding="utf-8"))
    detected_ids = {marker["id"] for marker in markers_doc["images"][0]["markers"]}
    assert detected_ids == {0, 1, 2, 3}

    # Story 5.0: le chemin scan n'ecrit plus de PNG 8 bits, mais du TIFF 16 bits.
    scan_frames = sorted((project_dir / "outputs").glob("scan_frame_*.tiff"))
    assert len(scan_frames) == 2
    assert [frame.name for frame in scan_frames] == ["scan_frame_0001.tiff", "scan_frame_0002.tiff"]
    assert not list((project_dir / "outputs").glob("scan_frame_*.png"))

    log_path = project_dir / "logs" / "poc_run.log"
    assert log_path.is_file()
    assert log_path.stat().st_size > 0

    final_manifest = validate_manifest(manifest_path)
    assert final_manifest["meta"]["scan_source"] == "inputs/simple_scan.png"
    assert final_manifest["meta"]["video_source"] == "inputs/synthetic_source.mp4"
    assert final_manifest["meta"]["lot"]["state"] == "scan"


def test_poc_build_sheet_fails_with_actionable_message_for_missing_video(tmp_path: Path) -> None:
    project_dir = tmp_path / "poc_project_missing_video"
    missing_video = tmp_path / "does_not_exist.mp4"

    exit_code = _build_sheet(project_dir, missing_video)

    assert exit_code == 1
    log_path = project_dir / "logs" / "poc_run.log"
    assert log_path.is_file()
    assert "introuvable" in log_path.read_text(encoding="utf-8")


def test_poc_process_scan_fails_with_actionable_message_for_missing_scan(tmp_path: Path) -> None:
    project_dir = tmp_path / "poc_project_missing_scan"
    project_dir.mkdir(parents=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")
    missing_scan = tmp_path / "does_not_exist.png"

    exit_code = _process_scan(project_dir, missing_scan)

    assert exit_code == 1
    log_path = project_dir / "logs" / "poc_run.log"
    assert log_path.is_file()
    assert "scan introuvable" in log_path.read_text(encoding="utf-8")


def test_poc_process_scan_fails_when_project_json_missing(tmp_path: Path) -> None:
    project_dir = tmp_path / "poc_project_no_manifest"

    exit_code = _process_scan(project_dir, FIXTURE_SCAN)

    assert exit_code == 1
    log_path = project_dir / "logs" / "poc_run.log"
    assert log_path.is_file()
    assert "build-sheet" in log_path.read_text(encoding="utf-8")


def test_poc_build_sheet_fails_with_exit_code_2_when_ffmpeg_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_dir = tmp_path / "poc_project_missing_ffmpeg"
    fake_video = tmp_path / "fake_video.mp4"
    fake_video.write_bytes(b"not-a-real-video")

    monkeypatch.setattr(cli.cv2, "VideoCapture", lambda *_: _FakeCapture(1920, 1080))
    monkeypatch.setattr(ffmpeg_utils.shutil, "which", lambda binary: None)

    exit_code = _build_sheet(project_dir, fake_video)

    assert exit_code == 2
    log_path = project_dir / "logs" / "poc_run.log"
    assert log_path.is_file()
    assert "ffmpeg" in log_path.read_text(encoding="utf-8")


@requires_ffmpeg
def test_poc_process_scan_fails_with_actionable_message_when_markers_missing(
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "poc_project_missing_markers"
    project_dir.mkdir(parents=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")
    blank_scan = tmp_path / "blank_scan.png"
    cv2.imwrite(str(blank_scan), np.zeros((200, 200, 3), dtype=np.uint8))

    exit_code = _process_scan(project_dir, blank_scan)

    assert exit_code == 1
    log_path = project_dir / "logs" / "poc_run.log"
    assert log_path.is_file()
    assert "marqueurs" in log_path.read_text(encoding="utf-8").lower()


@pytest.mark.parametrize("invalid_fps", ["0", "-1"])
def test_poc_build_sheet_fails_with_actionable_message_for_invalid_fps(
    tmp_path: Path, invalid_fps: str
) -> None:
    project_dir = tmp_path / "poc_project_invalid_fps"
    fake_video = tmp_path / "fake_video.mp4"
    fake_video.write_bytes(b"not-a-real-video")

    exit_code = _build_sheet(project_dir, fake_video, fps=invalid_fps)

    assert exit_code == 1
    log_path = project_dir / "logs" / "poc_run.log"
    assert log_path.is_file()
    assert "--fps" in log_path.read_text(encoding="utf-8")


@pytest.mark.parametrize("invalid_dpi", ["0", "-1"])
def test_poc_build_sheet_fails_with_actionable_message_for_invalid_dpi(
    tmp_path: Path, invalid_dpi: str
) -> None:
    project_dir = tmp_path / "poc_project_invalid_dpi"
    fake_video = tmp_path / "fake_video.mp4"
    fake_video.write_bytes(b"not-a-real-video")

    exit_code = _build_sheet(project_dir, fake_video, dpi=invalid_dpi)

    assert exit_code == 1
    log_path = project_dir / "logs" / "poc_run.log"
    assert log_path.is_file()
    assert "--dpi" in log_path.read_text(encoding="utf-8")


@pytest.mark.parametrize("invalid_dpi", ["0", "-1"])
def test_poc_process_scan_fails_with_actionable_message_for_invalid_dpi(
    tmp_path: Path, invalid_dpi: str
) -> None:
    project_dir = tmp_path / "poc_project_process_invalid_dpi"
    project_dir.mkdir(parents=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")

    exit_code = _process_scan(project_dir, FIXTURE_SCAN, dpi=invalid_dpi)

    assert exit_code == 1
    log_path = project_dir / "logs" / "poc_run.log"
    assert log_path.is_file()
    assert "--dpi" in log_path.read_text(encoding="utf-8")


@requires_ffmpeg
def test_poc_build_sheet_fails_for_non_16x9_video_ratio(tmp_path: Path, non_16x9_video: Path) -> None:
    project_dir = tmp_path / "poc_project_bad_ratio"

    exit_code = _build_sheet(project_dir, non_16x9_video)

    assert exit_code == 1
    log_path = project_dir / "logs" / "poc_run.log"
    assert log_path.is_file()
    assert "16:9" in log_path.read_text(encoding="utf-8")


def test_select_sheet_frames_raises_when_fewer_than_2_frames_available(tmp_path: Path) -> None:
    single_frame = tmp_path / "frame_0001.png"
    single_frame.write_bytes(b"not-a-real-png")

    with pytest.raises(cli.PocInputError, match="Frames utilisables insuffisantes"):
        cli._select_sheet_frames([single_frame])


@requires_ffmpeg
def test_poc_build_sheet_fails_when_fewer_than_2_frames_extracted(
    tmp_path: Path, synthetic_video: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_dir = tmp_path / "poc_project_too_few_frames"
    monkeypatch.setattr(cli, "_select_sheet_frames", lambda frame_paths: (_ for _ in ()).throw(
        cli.PocInputError("Frames utilisables insuffisantes: 1 extraite(s), 2 requises pour la planche.")
    ))

    exit_code = _build_sheet(project_dir, synthetic_video)

    assert exit_code == 1
    log_path = project_dir / "logs" / "poc_run.log"
    assert log_path.is_file()
    assert "frames utilisables" in log_path.read_text(encoding="utf-8").lower()
