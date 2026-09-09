from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from jsonschema.exceptions import ValidationError


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility.io.manifest import (
    LOT_STATES,
    validate_lot_state_transition,
    validate_manifest,
    validate_manifest_completeness,
)


def test_validate_manifest_accepts_example_project() -> None:
    manifest_path = REPO_ROOT / "tests" / "fixtures" / "example_manifests" / "project.json"

    manifest = validate_manifest(manifest_path)

    assert manifest["id"] == "example-001"


def test_validate_manifest_raises_for_missing_required_field(tmp_path: Path) -> None:
    manifest_path = tmp_path / "invalid-project.json"
    manifest_path.write_text(
        json.dumps(
            {
                "id": "example-001",
                "created": "2026-07-14T00:00:00Z",
                "inputs": {"raw": "inputs/", "frames": "frames/"},
                "artifacts": "outputs/",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="calibration"):
        validate_manifest(manifest_path)


def _valid_v2_manifest() -> dict:
    return {
        "schema_version": "2.0",
        "project_id": "example-001",
        "created": "2026-07-21T00:00:00Z",
        "rushes": [{"rush_id": "rush-001", "source_path": "inputs/rush-001.mp4"}],
        "lots": [{"lot_id": "lot-001", "rush_id": "rush-001", "state": "extraction"}],
        "artifacts": {"frames_dir": "frames/", "outputs_dir": "outputs/"},
        "color": {"target_colorspace": "rec709"},
        "video": {"fps_source": 24.0, "fps_target": 24.0},
        "reconstruction": {"template_id": "template-a4-16x9", "patch_preset_id": "patch-preset-mvp"},
    }


def _write_manifest(path: Path, manifest: dict) -> Path:
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_validate_manifest_accepts_v2_example_project() -> None:
    manifest_path = REPO_ROOT / "tests" / "fixtures" / "example_manifests" / "project.v2.json"

    manifest = validate_manifest(manifest_path)

    assert manifest["schema_version"] == "2.1"
    assert manifest["project_id"] == "example-001"


def test_validate_manifest_v2_rejects_absolute_path(tmp_path: Path) -> None:
    """`artifacts.frames_dir`, pas `rushes[].source_path` (story 2.8,
    EPIC7-ARB-41): ce dernier est desormais la SEULE exception nommee a
    l'invariant de portabilite, voir `test_manifest.py` plus bas pour les
    tests dedies a cette exception."""
    manifest = _valid_v2_manifest()
    manifest["artifacts"]["frames_dir"] = "/absolute/frames"
    manifest_path = _write_manifest(tmp_path / "v2-absolute-path.json", manifest)

    with pytest.raises(ValidationError, match="absolute path"):
        validate_manifest(manifest_path)


def test_validate_manifest_v2_rejects_windows_absolute_path(tmp_path: Path) -> None:
    manifest = _valid_v2_manifest()
    manifest["artifacts"]["frames_dir"] = "C:\\projects\\example\\frames"
    manifest_path = _write_manifest(tmp_path / "v2-windows-absolute-path.json", manifest)

    with pytest.raises(ValidationError, match="absolute path"):
        validate_manifest(manifest_path)


def test_validate_manifest_v2_rejects_missing_identifier(tmp_path: Path) -> None:
    manifest = _valid_v2_manifest()
    del manifest["project_id"]
    manifest_path = _write_manifest(tmp_path / "v2-missing-id.json", manifest)

    with pytest.raises(ValidationError, match="project_id"):
        validate_manifest(manifest_path)


def test_validate_manifest_v2_rejects_invalid_identifier(tmp_path: Path) -> None:
    manifest = _valid_v2_manifest()
    manifest["project_id"] = "invalid id with spaces"
    manifest_path = _write_manifest(tmp_path / "v2-invalid-id.json", manifest)

    with pytest.raises(ValidationError, match="project_id"):
        validate_manifest(manifest_path)


def test_validate_manifest_v2_rejects_invalid_schema_version(tmp_path: Path) -> None:
    manifest = _valid_v2_manifest()
    manifest["schema_version"] = "1.0"
    manifest_path = _write_manifest(tmp_path / "v2-invalid-schema-version.json", manifest)

    with pytest.raises(ValidationError, match="schema_version"):
        validate_manifest(manifest_path)


def test_validate_manifest_legacy_example_still_valid_after_v2_introduction() -> None:
    manifest_path = REPO_ROOT / "tests" / "fixtures" / "example_manifests" / "project.json"

    manifest = validate_manifest(manifest_path)

    assert manifest["id"] == "example-001"
    assert "schema_version" not in manifest


# --- Story 2.2: metadonnees techniques et etats de lot -----------------------------


def _valid_v2_manifest_with_technical_metadata() -> dict:
    manifest = _valid_v2_manifest()
    manifest["video"]["resolution_source"] = {"width": 1920, "height": 1080}
    manifest["video"]["codec_target"] = "prores"
    manifest["lots"][0]["expected_frame_count"] = 48
    return manifest


def test_validate_manifest_v2_accepts_full_technical_metadata(tmp_path: Path) -> None:
    manifest = _valid_v2_manifest_with_technical_metadata()
    manifest_path = _write_manifest(tmp_path / "v2-full-technical-metadata.json", manifest)

    validated = validate_manifest(manifest_path)

    assert validated["video"]["resolution_source"] == {"width": 1920, "height": 1080}
    assert validated["video"]["codec_target"] == "prores"
    assert validated["lots"][0]["expected_frame_count"] == 48


def test_validate_manifest_v2_rejects_non_integer_resolution_source(tmp_path: Path) -> None:
    manifest = _valid_v2_manifest_with_technical_metadata()
    manifest["video"]["resolution_source"]["width"] = "1920"
    manifest_path = _write_manifest(tmp_path / "v2-invalid-resolution-source.json", manifest)

    with pytest.raises(ValidationError, match="resolution_source"):
        validate_manifest(manifest_path)


def test_validate_manifest_v2_rejects_incomplete_resolution_source(tmp_path: Path) -> None:
    manifest = _valid_v2_manifest_with_technical_metadata()
    del manifest["video"]["resolution_source"]["height"]
    manifest_path = _write_manifest(tmp_path / "v2-incomplete-resolution-source.json", manifest)

    with pytest.raises(ValidationError, match="height"):
        validate_manifest(manifest_path)


def test_validate_manifest_v2_rejects_non_positive_expected_frame_count(tmp_path: Path) -> None:
    manifest = _valid_v2_manifest_with_technical_metadata()
    manifest["lots"][0]["expected_frame_count"] = 0
    manifest_path = _write_manifest(tmp_path / "v2-invalid-expected-frame-count.json", manifest)

    with pytest.raises(ValidationError, match="expected_frame_count"):
        validate_manifest(manifest_path)


def test_validate_manifest_completeness_accepts_full_manifest() -> None:
    manifest = _valid_v2_manifest_with_technical_metadata()

    validate_manifest_completeness(manifest)  # must not raise


def test_validate_manifest_completeness_rejects_missing_resolution_source() -> None:
    manifest = _valid_v2_manifest_with_technical_metadata()
    del manifest["video"]["resolution_source"]

    with pytest.raises(ValidationError, match="video.resolution_source"):
        validate_manifest_completeness(manifest)


def test_validate_manifest_completeness_rejects_missing_codec_target() -> None:
    manifest = _valid_v2_manifest_with_technical_metadata()
    del manifest["video"]["codec_target"]

    with pytest.raises(ValidationError, match="video.codec_target"):
        validate_manifest_completeness(manifest)


def test_validate_manifest_completeness_rejects_missing_target_colorspace() -> None:
    manifest = _valid_v2_manifest_with_technical_metadata()
    del manifest["color"]["target_colorspace"]

    with pytest.raises(ValidationError, match="color.target_colorspace"):
        validate_manifest_completeness(manifest)


def test_validate_manifest_completeness_rejects_missing_lot_expected_frame_count() -> None:
    manifest = _valid_v2_manifest_with_technical_metadata()
    del manifest["lots"][0]["expected_frame_count"]

    with pytest.raises(ValidationError, match="expected_frame_count"):
        validate_manifest_completeness(manifest)


def test_validate_manifest_completeness_rejects_missing_lot_state() -> None:
    manifest = _valid_v2_manifest_with_technical_metadata()
    del manifest["lots"][0]["state"]

    with pytest.raises(ValidationError, match="state"):
        validate_manifest_completeness(manifest)


def test_lot_states_order_matches_schema_enum() -> None:
    assert LOT_STATES == ("extraction", "pdf", "scan", "reconstruction", "encode")


@pytest.mark.parametrize(
    ("current_state", "new_state"),
    [
        (None, "extraction"),
        (None, "pdf"),
        ("extraction", "extraction"),
        ("extraction", "pdf"),
        ("pdf", "reconstruction"),
        ("reconstruction", "encode"),
    ],
)
def test_validate_lot_state_transition_accepts_forward_or_same_progression(
    current_state: str | None, new_state: str
) -> None:
    validate_lot_state_transition(current_state, new_state)  # must not raise


def test_validate_lot_state_transition_rejects_backward_transition() -> None:
    with pytest.raises(ValidationError, match="invalide"):
        validate_lot_state_transition("reconstruction", "pdf")


def test_validate_lot_state_transition_rejects_unknown_new_state() -> None:
    with pytest.raises(ValidationError, match="inconnu"):
        validate_lot_state_transition("extraction", "not-a-state")


def test_validate_lot_state_transition_rejects_unknown_current_state() -> None:
    with pytest.raises(ValidationError, match="inconnu"):
        validate_lot_state_transition("not-a-state", "extraction")

# --- Restructuration v2.1: un porteur par donnee (decisions-2026-08-04.md) ---------


def _valid_v2_1_manifest() -> dict:
    """Manifest v2.1 minimal: la source sur le rush, la cadence cible sur le lot."""
    return {
        "schema_version": "2.1",
        "project_id": "example-001",
        "created": "2026-08-04T00:00:00Z",
        "rushes": [
            {
                "rush_id": "rush-001",
                "source_name": "rush-001.mov",
                "fps_source": 30.0,
                "fps_source_exact": "30/1",
                "resolution_source": {"width": 1920, "height": 1080},
            }
        ],
        "lots": [
            {
                "lot_id": "rush-001_5",
                "rush_id": "rush-001",
                "state": "extraction",
                "fps_target": 5.0,
                "fps_target_exact": "5/1",
                "expected_frame_count": 17,
            },
            {
                "lot_id": "rush-001_12p5",
                "rush_id": "rush-001",
                "state": "extraction",
                "fps_target": 12.5,
                "fps_target_exact": "25/2",
                "expected_frame_count": 42,
            },
        ],
        "artifacts": {"frames_dir": "frames/"},
        "color": {"target_colorspace": "rec709"},
        "video": {"codec_target": "prores"},
        "reconstruction": {},
    }


def test_validate_manifest_accepts_two_target_rates_for_one_rush(tmp_path: Path) -> None:
    manifest_path = _write_manifest(tmp_path / "v2-1-two-rates.json", _valid_v2_1_manifest())

    validated = validate_manifest(manifest_path)

    assert [lot["fps_target"] for lot in validated["lots"]] == [5.0, 12.5]


def test_validate_manifest_v2_1_refuses_a_target_rate_at_project_level(tmp_path: Path) -> None:
    """La cadence cible n'a qu'un porteur: la tolerer dans `video` recreerait
    la section unique par projet qui invalidait le premier lot."""
    manifest = _valid_v2_1_manifest()
    manifest["video"]["fps_target"] = 5.0
    manifest_path = _write_manifest(tmp_path / "v2-1-project-fps-target.json", manifest)

    with pytest.raises(ValidationError, match="video"):
        validate_manifest(manifest_path)


@pytest.mark.parametrize(
    "field",
    ["fps_source", "fps_source_exact", "resolution_source", "source_codec", "source_bit_depth"],
)
def test_validate_manifest_v2_1_refuses_source_fields_at_project_level(
    tmp_path: Path, field: str
) -> None:
    manifest = _valid_v2_1_manifest()
    manifest["video"][field] = 1 if field == "source_bit_depth" else "x"
    manifest_path = _write_manifest(tmp_path / f"v2-1-project-{field}.json", manifest)

    with pytest.raises(ValidationError, match="video"):
        validate_manifest(manifest_path)


def test_validate_manifest_still_accepts_the_frozen_v2_0_example() -> None:
    """Compatibilite ascendante: un manifest deja ecrit en v2.0 reste lisible,
    valide contre son propre schema fige, exactement comme la v1 legacy."""
    manifest_path = REPO_ROOT / "tests" / "fixtures" / "example_manifests" / "project.v2-0.json"

    manifest = validate_manifest(manifest_path)

    assert manifest["schema_version"] == "2.0"
    assert manifest["video"]["fps_target"] == 24.0


def test_validate_manifest_refuses_an_unknown_schema_version(tmp_path: Path) -> None:
    manifest = _valid_v2_1_manifest()
    manifest["schema_version"] = "9.9"
    manifest_path = _write_manifest(tmp_path / "v9-9.json", manifest)

    with pytest.raises(ValidationError, match="schema_version"):
        validate_manifest(manifest_path)


def test_completeness_of_a_v2_1_manifest_is_judged_on_the_real_carriers() -> None:
    manifest = _valid_v2_1_manifest()
    for lot in manifest["lots"]:
        lot.setdefault("state", "extraction")

    validate_manifest_completeness(manifest)  # must not raise


def test_completeness_of_a_v2_1_manifest_rejects_a_rush_without_source_rate() -> None:
    manifest = _valid_v2_1_manifest()
    del manifest["rushes"][0]["fps_source"]

    with pytest.raises(ValidationError, match=r"rushes\[rush-001\].fps_source"):
        validate_manifest_completeness(manifest)


def test_completeness_of_a_v2_1_manifest_rejects_a_lot_without_target_rate() -> None:
    manifest = _valid_v2_1_manifest()
    del manifest["lots"][1]["fps_target"]

    with pytest.raises(ValidationError, match=r"lots\[rush-001_12p5\].fps_target"):
        validate_manifest_completeness(manifest)


# --- Story 2.8: exception nommee EPIC7-ARB-41 (rushes[].source_path) --------------
#
# Decision produit d'Egan, verbatim: « Dans le projet ! Mais remplacable ! ».
# `rushes[].source_path` devient la SEULE exception a l'invariant "aucun
# chemin absolu au manifest": tout le reste du contrat de portabilite v2 reste
# inchange (regle des fabriques non applicable ici, un seul champ concerne).


def test_champs_exemptes_chemin_absolu_a_un_seul_element() -> None:
    from mixed_media_utility.io.manifest import CHAMPS_EXEMPTES_CHEMIN_ABSOLU

    assert CHAMPS_EXEMPTES_CHEMIN_ABSOLU == ("rushes[].source_path",)


def test_validate_manifest_v2_1_accepts_absolute_source_path(tmp_path: Path) -> None:
    manifest = _valid_v2_1_manifest()
    manifest["rushes"][0]["source_path"] = "/mnt/rushes/rush-001.mov"
    manifest_path = _write_manifest(tmp_path / "v2-1-absolute-source-path.json", manifest)

    validated = validate_manifest(manifest_path)

    assert validated["rushes"][0]["source_path"] == "/mnt/rushes/rush-001.mov"


def test_validate_manifest_v2_1_still_rejects_absolute_lots_frames_dir(tmp_path: Path) -> None:
    """Frontiere de l'exception (AC 1): ailleurs qu'a `rushes[].source_path`,
    un chemin absolu reste refuse."""
    manifest = _valid_v2_1_manifest()
    manifest["lots"][0]["frames_dir"] = "/absolute/frames"
    manifest_path = _write_manifest(tmp_path / "v2-1-absolute-lot-frames-dir.json", manifest)

    with pytest.raises(ValidationError, match="absolute path"):
        validate_manifest(manifest_path)


def test_validate_manifest_v2_1_still_rejects_absolute_source_name(tmp_path: Path) -> None:
    """`source_name` refuse deja tout slash au niveau du schema (contrainte
    "nom de base, jamais un chemin", story 3.4): l'exception de l'AC 1 ne
    l'atteint donc meme pas, la garde de portabilite generique. Toujours
    refuse, message different (localisation `rushes[].source_name`)."""
    manifest = _valid_v2_1_manifest()
    manifest["rushes"][0]["source_name"] = "/absolute/rush-001.mov"
    manifest_path = _write_manifest(tmp_path / "v2-1-absolute-source-name.json", manifest)

    with pytest.raises(ValidationError, match=r"rushes\.0\.source_name"):
        validate_manifest(manifest_path)


def test_validate_manifest_v2_1_still_rejects_absolute_artifacts_frames_dir(
    tmp_path: Path,
) -> None:
    manifest = _valid_v2_1_manifest()
    manifest["artifacts"]["frames_dir"] = "/absolute/frames"
    manifest_path = _write_manifest(tmp_path / "v2-1-absolute-artifacts-dir.json", manifest)

    with pytest.raises(ValidationError, match="absolute path"):
        validate_manifest(manifest_path)


def test_project_schema_marks_epic7_arb_41_exactly_once_on_source_path() -> None:
    """Grep de frontiere exige par l'AC 1 de la story 2.8: le marqueur
    EPIC7-ARB-41 n'apparait qu'une fois dans le schema v2.1, sur la
    description de `rushes[].source_path` -- aucun autre champ ne porte
    l'exception."""
    schema_path = REPO_ROOT / "src" / "mixed_media_utility" / "specs" / "project.schema.json"
    schema_text = schema_path.read_text(encoding="utf-8")

    assert schema_text.count("EPIC7-ARB-41") == 1

    schema = json.loads(schema_text)
    description = schema["properties"]["rushes"]["items"]["properties"]["source_path"][
        "description"
    ]
    assert "EPIC7-ARB-41" in description


def test_manifest_written_before_this_story_is_delinke_chemin_absent(tmp_path: Path) -> None:
    """AC 3: un manifest v2.1 anterieur, sans `source_path`, reste lisible et
    complet (le champ n'est jamais exige en lecture), et son statut de
    liaison est `DELINKE_CHEMIN_ABSENT` -- jamais une erreur."""
    from mixed_media_utility import relink

    manifest = _valid_v2_1_manifest()
    assert "source_path" not in manifest["rushes"][0]
    manifest_path = _write_manifest(tmp_path / "v2-1-sans-source-path.json", manifest)

    validated = validate_manifest(manifest_path)
    validate_manifest_completeness(validated)  # ne doit pas lever

    assert relink.statut_de_liaison(validated["rushes"][0]) == relink.DELINKE_CHEMIN_ABSENT
