from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility.io.metadata_matrix import (
    Channel,
    MetadataMatrixViolation,
    Responsibility,
    canonical_channel,
    get_cell,
    is_allowed,
    known_fields,
    validate_assignment,
)


def test_known_fields_cover_reconstruction_contract() -> None:
    fields = known_fields()

    for expected in (
        "schema_version",
        "project_id",
        "rush_id",
        "lot_id",
        "page_index",
        "page_count",
        "slot_index",
        "frame_timecode",
        "fps_target",
        "template_id",
        "patch_preset_id",
    ):
        assert expected in fields


def test_every_field_has_a_cell_for_every_channel() -> None:
    fields = known_fields()

    for field in fields:
        for channel in Channel:
            # Should not raise - every (field, channel) pair is documented.
            is_allowed(field, channel)


@pytest.mark.parametrize(
    ("field", "channel"),
    [
        ("schema_version", Channel.FILENAME),
        ("schema_version", Channel.ARUCO),
        ("lot_id", Channel.ARUCO),
        ("patch_preset_id", Channel.FILENAME),
        ("patch_preset_id", Channel.ARUCO),
        ("page_calibration_results", Channel.FILENAME),
    ],
)
def test_forbidden_combinations_are_not_allowed(field: str, channel: Channel) -> None:
    assert is_allowed(field, channel) is False


@pytest.mark.parametrize(
    ("field", "channel"),
    [
        ("schema_version", Channel.MANIFEST),
        ("schema_version", Channel.QR),
        ("project_id", Channel.MANIFEST),
        ("project_id", Channel.FILENAME),
        ("slot_index", Channel.ARUCO),
        ("template_id", Channel.ARUCO),
    ],
)
def test_allowed_combinations(field: str, channel: Channel) -> None:
    assert is_allowed(field, channel) is True


@pytest.mark.parametrize(
    ("field", "expected_channel"),
    [
        ("schema_version", Channel.MANIFEST),
        ("project_id", Channel.MANIFEST),
        ("rush_id", Channel.MANIFEST),
        ("lot_id", Channel.MANIFEST),
        ("page_index", Channel.MANIFEST),
        ("page_count", Channel.MANIFEST),
        ("slot_index", Channel.MANIFEST),
        ("frame_timecode", Channel.MANIFEST),
        ("fps_target", Channel.MANIFEST),
        ("template_id", Channel.MANIFEST),
        ("patch_preset_id", Channel.MANIFEST),
        ("codec_target_profile", Channel.MANIFEST),
    ],
)
def test_canonical_channel_matches_priority_order(field: str, expected_channel: Channel) -> None:
    assert canonical_channel(field) == expected_channel


def test_aruco_is_never_the_canonical_channel() -> None:
    for field in known_fields():
        assert canonical_channel(field) != Channel.ARUCO


def test_source_provenance_paths_has_no_canonical_channel() -> None:
    # Optional/non-canonical by design: provenance must never become the
    # single source of truth for reconstruction (ARCHITECTURE_DETAILED.md #3).
    assert canonical_channel("source_provenance_paths") is None


def test_validate_assignment_accepts_canonical_placement() -> None:
    # Should not raise.
    validate_assignment({"project_id": [Channel.MANIFEST, Channel.QR]})


def test_validate_assignment_rejects_forbidden_channel() -> None:
    with pytest.raises(MetadataMatrixViolation) as exc_info:
        validate_assignment({"schema_version": [Channel.FILENAME]})

    message = str(exc_info.value)
    assert "schema_version" in message
    assert "filename" in message


def test_validate_assignment_rejects_unknown_field() -> None:
    with pytest.raises(MetadataMatrixViolation, match="unknown"):
        validate_assignment({"totally_unknown_field": [Channel.MANIFEST]})


def test_validate_assignment_collects_all_violations() -> None:
    with pytest.raises(MetadataMatrixViolation) as exc_info:
        validate_assignment(
            {
                "schema_version": [Channel.FILENAME],
                "patch_preset_id": [Channel.ARUCO],
            }
        )

    message = str(exc_info.value)
    assert "schema_version" in message
    assert "patch_preset_id" in message


def test_responsibility_enum_values_are_stable() -> None:
    assert {member.value for member in Responsibility} == {"required", "optional", "forbidden"}


def test_matrix_fields_are_consistent_with_v2_schema_required_properties() -> None:
    schema_path = REPO_ROOT / "src" / "mixed_media_utility" / "specs" / "project.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    assert set(schema["required"]) <= set(known_fields()) | {
        "rushes",
        "lots",
        "artifacts",
        "color",
        "video",
        "reconstruction",
    }
    # Top-level scalar contract fields must be canonically manifest-owned.
    assert canonical_channel("schema_version") == Channel.MANIFEST
    assert canonical_channel("project_id") == Channel.MANIFEST

    lot_item_schema = schema["properties"]["lots"]["items"]
    for required_field in lot_item_schema["required"]:
        assert canonical_channel(required_field) == Channel.MANIFEST


# --- Story 5.9: gamut_map_id entre a la matrice de responsabilite -----------


def test_gamut_map_id_has_its_row_with_the_patch_preset_profile() -> None:
    """Sans cette ligne, un champ voyage dans un canal jamais autorise (AC 14).

    La cellule QR est `required` **sans condition ni note**: le champ etant
    obligatoire au payload (EPIC5-ARB-13), il n'existe aucune planche qui en
    soit depourvue, donc aucun cas ou l'exigence ferait declarer non conforme
    une planche legitime. C'est ce qui rend la ligne triviale et la calque
    exactement sur celle de `patch_preset_id`.
    """
    assert "gamut_map_id" in known_fields()
    for channel in Channel:
        cell = get_cell("gamut_map_id", channel)
        reference = get_cell("patch_preset_id", channel)
        assert cell.responsibility == reference.responsibility, channel
        assert cell.note == reference.note == "", channel


def test_gamut_map_id_is_forbidden_in_the_filename_and_the_video_container() -> None:
    assert get_cell("gamut_map_id", Channel.MANIFEST).responsibility is Responsibility.REQUIRED
    assert get_cell("gamut_map_id", Channel.QR).responsibility is Responsibility.REQUIRED
    for channel in (Channel.FILENAME, Channel.ARUCO, Channel.VIDEO_CONTAINER):
        assert get_cell("gamut_map_id", channel).responsibility is Responsibility.FORBIDDEN, channel
    # Canal canonique: le manifest, comme pour patch_preset_id.
    assert canonical_channel("gamut_map_id") is Channel.MANIFEST
