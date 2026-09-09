"""Tests de la persistance manifest de l'extraction (story 3.4).

Couvre les AC 1 a 16 sans aucun binaire externe: rien dans cette story ne
lance de sous-processus (Piege 12). Contient aussi les tests des deux helpers
ajoutes a `io/naming.py` (`build_lot_id`, `build_extracted_frame_filename`),
pour ne modifier aucun fichier de test existant.
"""

from __future__ import annotations

import json
import sys
from fractions import Fraction
from pathlib import Path

import pytest
from jsonschema.exceptions import ValidationError


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility.codec_profiles import exact_frame_rate, validate_timecode
from mixed_media_utility.frame_selection import (
    ROUNDING_POLICY_ID,
    WARNING_SOURCE_FRAME_COUNT_ESTIMATED,
    FrameSelection,
    SelectedFrame,
    select_source_frames,
)
from mixed_media_utility.io import extraction_manifest
from mixed_media_utility.io.extraction_manifest import (
    CONFIRMATION_FIELDS,
    EXTRACTION_ARTIFACT_FIELDS,
    EXTRACTION_LOT_FIELDS,
    EXTRACTION_LOT_STATE,
    EXTRACTION_OUTPUT_BIT_DEPTH,
    EXTRACTION_ROOT_FIELDS,
    EXTRACTION_RUSH_FIELDS,
    EXTRACTION_VIDEO_FIELDS,
    FRAME_DIGEST_PREFIX,
    MANIFEST_FILENAME,
    NON_IDEMPOTENT_FIELDS,
    SOURCE_REPORT_RUSH_FIELDS,
    VERIFY_FRAME_COUNT_MISMATCH,
    VERIFY_FRAMES_DIR_ABSENT,
    VERIFY_LOT_ABSENT,
    VERIFY_MISSING_FRAMES,
    VERIFY_NONCONFORMING_NAMES,
    VERIFY_SELECTION_NOT_RECOMPUTED,
    VERIFY_SOURCE_COUNT_NOT_EXACT,
    VERIFY_UNEXPECTED_FRAMES,
    ExtractionPersistenceError,
    ExtractionRecord,
    LegacyManifestError,
    LotIdentityMismatchError,
    LotStateConflictError,
    ManifestWriteError,
    build_extraction_manifest,
    compute_frame_timecodes_digest,
    persist_extraction,
    verify_extracted_lot,
)
from mixed_media_utility.io.manifest import validate_manifest
from mixed_media_utility.io.naming import (
    BOUNDS_SUFFIX_LENGTH,
    CANONICAL_ID_MAX_LENGTH,
    NamingError,
    bounds_suffix,
    build_extracted_frame_filename,
    build_frame_filename,
    build_lot_id,
    normalize_identifier,
)
from mixed_media_utility.io import project_layout
from mixed_media_utility.io.project_layout import FRAMES_DIRNAME, rush_dir_slug


# --------------------------------------------------------------------------
# Fabriques
# --------------------------------------------------------------------------

TAGGED_SOURCE_FIELDS = {
    "source_codec": "prores",
    "source_pix_fmt": "yuv422p10le",
    "source_bit_depth": 10,
    "source_sample_aspect_ratio": "1:1",
    "source_color_primaries": "bt709",
    "source_color_trc": "bt709",
    "source_colorspace": "bt709",
    "source_color_range": "tv",
}

UNTAGGED_SOURCE_FIELDS = {key: None for key in SOURCE_REPORT_RUSH_FIELDS}


def make_selection(
    fps_source=30, fps_target=4, source_frame_count=100, **kwargs
) -> FrameSelection:
    return select_source_frames(
        fps_source=fps_source,
        fps_target=fps_target,
        source_frame_count=source_frame_count,
        **kwargs,
    )


#: Sentinelle du parametre `rush_source_path` de `make_record`: distincte de
#: `None`, qui reste une valeur explicite legitime (voir sa docstring). Sans
#: elle, un defaut litteral unique referencerait toujours "rush-001.mov" quel
#: que soit le `rush_id` demande, et deux rushs fabriques par defaut dans le
#: meme test porteraient alors le MEME `source_path` -- exactement le
#: remplissage uniforme que la regle des fabriques du depot interdit.
_SOURCE_PATH_NON_PRECISE = object()


def make_record(
    selection: FrameSelection | None = None,
    *,
    fps_source: float = 30.0,
    fps_target: float = 4.0,
    rush_id: str = "rush-001",
    project_id: str = "proj-001",
    lot_id: str | None = None,
    frames_dir_relative: str | None = None,
    rush_source_name: str = "rush-001.mov",
    rush_source_path: str | None = _SOURCE_PATH_NON_PRECISE,
    source_fields=None,
    confirmation_mode: str = "non_interactif",
    unknown_color_accepted: bool = False,
    confirmed_at: str = "2026-08-04T09:30:00Z",
    source_width: int = 1920,
    source_height: int = 1080,
) -> ExtractionRecord:
    selection = selection if selection is not None else make_selection()
    lot_id = lot_id if lot_id is not None else build_lot_id(rush_id, fps_target)
    if frames_dir_relative is None:
        frames_dir_relative = f"{FRAMES_DIRNAME}/{rush_dir_slug(rush_id, fps_target)}"
    if rush_source_path is _SOURCE_PATH_NON_PRECISE:
        # Derive du nom de source, jamais d'un litteral fixe: deux rushs
        # fabriques dans le meme test restent distinguables par defaut.
        rush_source_path = f"/videos/{rush_source_name}"
    return ExtractionRecord(
        project_id=project_id,
        rush_id=rush_id,
        rush_source_name=rush_source_name,
        rush_source_path=rush_source_path,
        lot_id=lot_id,
        frames_dir_relative=frames_dir_relative,
        selection=selection,
        fps_source=fps_source,
        fps_target=fps_target,
        source_width=source_width,
        source_height=source_height,
        source_fields=dict(TAGGED_SOURCE_FIELDS if source_fields is None else source_fields),
        confirmation_mode=confirmation_mode,
        unknown_color_accepted=unknown_color_accepted,
        confirmed_at=confirmed_at,
    )


def write_lot_frames(project_dir: Path, record: ExtractionRecord) -> Path:
    """Ecrire sur disque les fichiers que la story 3.1 aurait ecrits."""
    frames_path = project_dir / record.frames_dir_relative
    frames_path.mkdir(parents=True, exist_ok=True)
    for frame in record.selection.frames:
        name = build_extracted_frame_filename(
            record.rush_id, record.fps_target, frame.frame_timecode
        )
        (frames_path / name).write_bytes(b"tiff")
    return frames_path


def lot_of(manifest: dict, lot_id: str) -> dict:
    return next(lot for lot in manifest["lots"] if lot["lot_id"] == lot_id)


# --------------------------------------------------------------------------
# Helpers de nommage ajoutes a io/naming.py (AC 5, et contrat 3.1)
# --------------------------------------------------------------------------


def test_build_lot_id_integer_rate() -> None:
    assert build_lot_id("rush-001", 24.0) == "rush-001_24"
    assert build_lot_id("rush-001", 24) == "rush-001_24"


def test_build_lot_id_fractional_rate_never_carries_a_dot() -> None:
    lot_id = build_lot_id("rush-001", 12.5)

    assert lot_id == "rush-001_12p5"
    assert "." not in lot_id


@pytest.mark.parametrize("fps_target", [1, 4, 12, 24, 25, 30, 12.5, 7.5, 2.5])
def test_build_lot_id_matches_the_schema_identifier_pattern(fps_target) -> None:
    import re

    assert re.fullmatch(r"[A-Za-z0-9_-]+", build_lot_id("rush-001", fps_target))


def test_build_lot_id_derives_a_short_form_for_a_long_rush_id() -> None:
    long_rush_id = "r" * (CANONICAL_ID_MAX_LENGTH + 10)

    lot_id = build_lot_id(long_rush_id, 24)

    assert len(lot_id) == CANONICAL_ID_MAX_LENGTH
    assert lot_id == build_lot_id(long_rush_id, 24)  # deterministe


def test_build_lot_id_rejects_an_identifier_the_schema_would_refuse() -> None:
    with pytest.raises(NamingError):
        build_lot_id("rush 001", 24)
    with pytest.raises(NamingError):
        build_lot_id("", 24)


def test_build_lot_id_agrees_with_the_rush_directory_slug() -> None:
    # Depuis ARB-3 les deux consomment `format_fps_short`: le nom du dossier de
    # lot et l'identifiant de lot ne peuvent plus diverger.
    for fps in (24, 12.5):
        assert build_lot_id("rush-001", fps) == rush_dir_slug("rush-001", fps)


# --------------------------------------------------------------------------
# Story 3.7 -- identite d'un lot borne (AC 6)
# --------------------------------------------------------------------------


def test_bounds_suffix_is_absent_when_no_bound_is_given() -> None:
    assert bounds_suffix(None, None) is None


@pytest.mark.parametrize(
    "bornes",
    [
        ("15:34:30:00", "15:34:50:00"),
        ("15:34:30:00", None),
        (None, "15:34:50:00"),
    ],
)
def test_bounds_suffix_is_a_fixed_length_hex_digest(bornes) -> None:
    import re

    suffix = bounds_suffix(*bornes)

    assert len(suffix) == BOUNDS_SUFFIX_LENGTH
    assert re.fullmatch(r"[0-9a-f]+", suffix)
    assert re.fullmatch(r"[A-Za-z0-9_-]+", suffix)
    assert suffix == bounds_suffix(*bornes)  # deterministe


def test_bounds_suffix_distinguishes_the_in_bound_from_the_out_bound() -> None:
    """Un `derive_short_id` rendrait la meme chaine brute des deux cotes."""
    assert bounds_suffix("15:34:30:00", None) != bounds_suffix(None, "15:34:30:00")


def test_a_short_rush_id_never_leaks_a_colon_into_the_lot_id() -> None:
    """Defaut dependant des donnees ferme: `derive_short_id` n'est pas un hacheur.

    Sous 48 caracteres il rend son entree **inchangee**, donc les deux-points
    du timecode auraient traverse sur un nom de rush court et pas sur un nom
    long -- une casse invisible a un test par echantillonnage.
    """
    import re

    lot_id = build_lot_id(
        "r", 3, source_in_timecode="15:34:30:00", source_out_timecode="15:34:50:00"
    )

    assert ":" not in lot_id
    assert re.fullmatch(r"[A-Za-z0-9_-]+", lot_id)


def test_an_excerpt_and_a_full_extraction_never_share_a_lot_id_nor_a_directory(
    tmp_path,
) -> None:
    complet = build_lot_id("rush-001", 3)
    extrait = build_lot_id(
        "rush-001", 3, source_in_timecode="15:34:30:00", source_out_timecode="15:34:50:00"
    )

    assert complet == "rush-001_3"
    assert extrait != complet
    assert extrait.startswith("rush-001_3-")

    dossier_complet = project_layout.extract_frames_dir(tmp_path, "rush-001", 3)
    dossier_extrait = project_layout.extract_frames_dir(
        tmp_path,
        "rush-001",
        3,
        source_in_timecode="15:34:30:00",
        source_out_timecode="15:34:50:00",
    )

    assert dossier_extrait != dossier_complet


def test_two_distinct_excerpts_never_share_a_lot_id_nor_a_directory(tmp_path) -> None:
    premier = dict(source_in_timecode="15:34:30:00", source_out_timecode="15:34:50:00")
    second = dict(source_in_timecode="15:35:30:00", source_out_timecode="15:35:50:00")

    assert build_lot_id("rush-001", 3, **premier) != build_lot_id("rush-001", 3, **second)
    assert project_layout.extract_frames_dir(tmp_path, "rush-001", 3, **premier) != (
        project_layout.extract_frames_dir(tmp_path, "rush-001", 3, **second)
    )
    assert project_layout.scan_frames_dir(tmp_path, "rush-001", 3, **premier) != (
        project_layout.scan_frames_dir(tmp_path, "rush-001", 3, **second)
    )


@pytest.mark.parametrize(
    "bornes",
    [
        {},
        dict(source_in_timecode="15:34:30:00", source_out_timecode="15:34:50:00"),
        dict(source_in_timecode="15:34:30:00"),
        dict(source_out_timecode="15:34:50:00"),
    ],
)
def test_a_bounded_lot_id_still_agrees_with_its_directory_slug(bornes) -> None:
    """ARB-3: les deux ne peuvent jamais diverger, bornes comprises."""
    assert build_lot_id("rush-001", 12.5, **bornes) == rush_dir_slug(
        "rush-001", 12.5, **bornes
    )


def test_ensure_project_layout_recreates_the_bounded_lot_directory(tmp_path) -> None:
    """`_iter_rush_fps_pairs` lit les bornes dans `lots[]`, sinon il recreerait
    le dossier **non borne** d'un lot borne (question ouverte 1)."""
    manifest = {
        "lots": [
            {
                "lot_id": "rush-001_3-deadbeef",
                "rush_id": "rush-001",
                "fps_target": 3,
                "source_in_timecode": "15:34:30:00",
                "source_out_timecode": "15:34:50:00",
            }
        ]
    }

    project_layout.ensure_project_layout(tmp_path, manifest)

    attendu = project_layout.extract_frames_dir(
        tmp_path,
        "rush-001",
        3,
        source_in_timecode="15:34:30:00",
        source_out_timecode="15:34:50:00",
    )
    assert attendu.is_dir()
    assert not project_layout.extract_frames_dir(tmp_path, "rush-001", 3).exists()


def test_the_lot_identity_guard_accepts_a_bounded_lot(tmp_path) -> None:
    """AC 6 / piege 1: la garde doit recevoir les memes bornes que 3.1.

    Sinon la garde qui protege contre un `lot_id` incoherent devient elle-meme
    la source de l'incoherence et refuse **tout** lot borne.
    """
    bornes = dict(source_in_timecode="00:00:00:10", source_out_timecode="00:00:02:00")
    selection = make_selection(**bornes)
    record = make_record(
        selection,
        lot_id=build_lot_id("rush-001", 4.0, **bornes),
        frames_dir_relative=f"{FRAMES_DIRNAME}/{rush_dir_slug('rush-001', 4.0, **bornes)}",
    )

    manifest = build_extraction_manifest(None, record)

    assert manifest["lots"][0]["lot_id"].startswith("rush-001_4-")


def test_the_lot_identity_guard_refuses_an_unbounded_id_for_a_bounded_lot() -> None:
    bornes = dict(source_in_timecode="00:00:00:10", source_out_timecode="00:00:02:00")
    record = make_record(make_selection(**bornes), lot_id=build_lot_id("rush-001", 4.0))

    with pytest.raises(LotIdentityMismatchError):
        build_extraction_manifest(None, record)


def test_build_extracted_frame_filename_convention() -> None:
    assert (
        build_extracted_frame_filename("rush-001", 12.5, "00:00:03:07")
        == "rush-001_12p5_00-00-03-07.tiff"
    )


def test_build_extracted_frame_filename_is_not_build_frame_filename() -> None:
    # `build_frame_filename` reste strictement intacte: c'est la chaine
    # PDF/scan et elle exige un `page_index` inexistant a l'extraction.
    with pytest.raises(TypeError):
        build_frame_filename(
            project_id="p", rush_id="r", lot_id="l", frame_timecode="00:00:00:00", fps_target=24
        )


# --------------------------------------------------------------------------
# AC 1 -- emplacement des champs
# --------------------------------------------------------------------------


def test_ac1_no_field_is_written_outside_the_persistence_table() -> None:
    manifest = build_extraction_manifest(None, make_record())

    assert set(manifest) <= set(EXTRACTION_ROOT_FIELDS)
    assert set(manifest["rushes"][0]) <= set(EXTRACTION_RUSH_FIELDS)
    assert set(manifest["lots"][0]) <= set(EXTRACTION_LOT_FIELDS)
    assert set(manifest["video"]) <= set(EXTRACTION_VIDEO_FIELDS)
    assert set(manifest["artifacts"]) <= set(EXTRACTION_ARTIFACT_FIELDS)
    assert set(manifest["lots"][0]["confirmation"]) == set(CONFIRMATION_FIELDS)
    assert manifest["color"] == {}
    assert manifest["reconstruction"] == {}


def test_ac1_resolution_source_keeps_its_epic_2_name() -> None:
    """Le nom est fige; seul son porteur change en v2.1 (video -> rushes[])."""
    manifest = build_extraction_manifest(None, make_record())

    assert manifest["rushes"][0]["resolution_source"] == {"width": 1920, "height": 1080}
    assert "source_resolution" not in manifest["rushes"][0]
    assert "resolution_source" not in manifest["video"]


def test_ac1_artifacts_frames_dir_comes_from_the_layout_constant() -> None:
    manifest = build_extraction_manifest(None, make_record())

    assert manifest["artifacts"]["frames_dir"] == FRAMES_DIRNAME


# --------------------------------------------------------------------------
# AC 2 -- aucune valeur inventee, absence encodee positivement
# --------------------------------------------------------------------------


def test_ac2_untagged_source_writes_no_color_field_and_lists_every_absence(tmp_path) -> None:
    record = make_record(source_fields=UNTAGGED_SOURCE_FIELDS)
    result = persist_extraction(tmp_path, record)

    rush = result.manifest["rushes"][0]
    for field in SOURCE_REPORT_RUSH_FIELDS:
        assert field not in rush
    assert rush["source_metadata_absent_fields"] == sorted(SOURCE_REPORT_RUSH_FIELDS)
    # Manifest valide malgre l'absence totale de tag couleur.
    validate_manifest(result.manifest_path)


def test_ac2_absent_fields_use_the_exact_rush_key_names_and_are_sorted() -> None:
    fields = dict(TAGGED_SOURCE_FIELDS)
    fields["source_color_primaries"] = None
    fields["source_codec"] = None

    manifest = build_extraction_manifest(None, make_record(source_fields=fields))

    assert manifest["rushes"][0]["source_metadata_absent_fields"] == [
        "source_codec",
        "source_color_primaries",
    ]


def _iter_manifest_values(node):
    """Parcourt les VALEURS du manifest, sans jamais regarder les noms de cles.

    Inspecter la forme serialisee entiere donnerait un faux positif sur
    `unknown_color_accepted`, nom de champ legitime impose par la story 3.3
    (decision 5 du 2026-08-03), dont le nom contient la sentinelle recherchee.
    """
    if isinstance(node, dict):
        for value in node.values():
            yield from _iter_manifest_values(value)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_manifest_values(item)
    else:
        yield node


def test_ac2_no_default_value_is_ever_substituted() -> None:
    manifest = build_extraction_manifest(
        None, make_record(source_fields=UNTAGGED_SOURCE_FIELDS)
    )

    values = list(_iter_manifest_values(manifest))
    string_values = [value for value in values if isinstance(value, str)]

    # Aucune sentinelle substituee a la place d'une donnee source absente:
    # un champ non renseigne sort du manifest et est liste dans
    # `rushes[].source_metadata_absent_fields`, il n'y entre jamais comble.
    for sentinel in ("bt709", "unknown", "unspecified", "reserved", "N/A"):
        assert sentinel not in string_values

    # Aucun `None` persiste non plus: il serait serialise en `null`, que le
    # schema etendu refuse (voir le test suivant).
    assert None not in values


def test_ac2_null_is_refused_by_the_extended_schema(tmp_path) -> None:
    # C'est la declaration TYPEE des proprietes `source_*` qui rend le `null`
    # refusable. En v2.1 elles vivent sous `rushes[]`, en
    # `additionalProperties: false`, ce qui renforce encore la garde.
    manifest = build_extraction_manifest(None, make_record())
    manifest["rushes"][0]["source_bit_depth"] = None
    path = tmp_path / MANIFEST_FILENAME
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValidationError):
        validate_manifest(path)


def test_ac2_unknown_sentinel_passes_the_schema_so_the_guard_is_upstream(tmp_path) -> None:
    # Documente la limite volontaire: le garde-fou du sentinel est la
    # normalisation de la story 3.3, jamais le schema.
    manifest = build_extraction_manifest(None, make_record())
    manifest["rushes"][0]["source_colorspace"] = "unknown"
    path = tmp_path / MANIFEST_FILENAME
    path.write_text(json.dumps(manifest), encoding="utf-8")

    validate_manifest(path)


# --------------------------------------------------------------------------
# AC 3 -- collision source_bit_depth verrouillee
# --------------------------------------------------------------------------


def test_ac3_color_source_bit_depth_is_left_untouched(tmp_path) -> None:
    existing = build_extraction_manifest(None, make_record())
    existing["color"] = {"target_colorspace": "rec709", "source_bit_depth": 8}
    (tmp_path / MANIFEST_FILENAME).write_text(json.dumps(existing), encoding="utf-8")

    fields = dict(TAGGED_SOURCE_FIELDS)
    fields["source_bit_depth"] = 12
    result = persist_extraction(tmp_path, make_record(source_fields=fields))

    reread = json.loads((tmp_path / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    assert reread["color"]["source_bit_depth"] == 8
    assert reread["color"]["target_colorspace"] == "rec709"
    assert reread["rushes"][0]["source_bit_depth"] == 12
    assert result.manifest["color"]["source_bit_depth"] == 8


def test_ac3_a_ten_bit_rush_is_persisted_verbatim() -> None:
    # `color_pipeline.mvp_color_manifest_fragment` refuse toute valeur hors
    # (8, 16); `rushes[].source_bit_depth` n'a pas ce domaine.
    fields = dict(TAGGED_SOURCE_FIELDS)
    fields["source_bit_depth"] = 10

    manifest = build_extraction_manifest(None, make_record(source_fields=fields))

    assert manifest["rushes"][0]["source_bit_depth"] == 10
    assert "source_bit_depth" not in manifest["color"]


def test_ac3_output_bit_depth_is_a_module_constant_not_the_source_depth() -> None:
    fields = dict(TAGGED_SOURCE_FIELDS)
    fields["source_bit_depth"] = 8

    manifest = build_extraction_manifest(None, make_record(source_fields=fields))

    assert manifest["lots"][0]["output_bit_depth"] == EXTRACTION_OUTPUT_BIT_DEPTH == 16
    assert manifest["rushes"][0]["source_bit_depth"] == 8


# --------------------------------------------------------------------------
# AC 5 -- convention de lot_id
# --------------------------------------------------------------------------


def test_ac5_mismatching_lot_id_fails_instead_of_writing_one_of_the_two(tmp_path) -> None:
    record = make_record(lot_id="un-autre-lot")

    with pytest.raises(LotIdentityMismatchError):
        build_extraction_manifest(None, record)
    with pytest.raises(LotIdentityMismatchError):
        persist_extraction(tmp_path, record)
    assert not (tmp_path / MANIFEST_FILENAME).exists()


def test_ac5_a_lot_cannot_be_reattached_to_another_rush(tmp_path) -> None:
    first = make_record()
    persist_extraction(tmp_path, first)
    existing = json.loads((tmp_path / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    existing["lots"][0]["rush_id"] = "rush-002"

    with pytest.raises(LotIdentityMismatchError):
        build_extraction_manifest(existing, first)


# --------------------------------------------------------------------------
# AC 6 -- declaration du lot et transition d'etat
# --------------------------------------------------------------------------


def test_ac6_lot_is_declared_in_extraction_state() -> None:
    manifest = build_extraction_manifest(None, make_record())

    assert manifest["lots"][0]["state"] == EXTRACTION_LOT_STATE == "extraction"


def test_ac6_a_preexisting_lot_without_state_is_accepted() -> None:
    record = make_record()
    existing = build_extraction_manifest(None, record)
    existing["lots"][0].pop("state")

    manifest = build_extraction_manifest(existing, record)

    assert manifest["lots"][0]["state"] == "extraction"


def test_ac6_extraction_to_extraction_is_accepted() -> None:
    record = make_record()
    existing = build_extraction_manifest(None, record)

    manifest = build_extraction_manifest(existing, record)

    assert manifest["lots"][0]["state"] == "extraction"
    assert len(manifest["lots"]) == 1


@pytest.mark.parametrize("advanced_state", ["pdf", "scan", "reconstruction", "encode"])
def test_ac6_an_advanced_lot_cannot_be_re_extracted(tmp_path, advanced_state) -> None:
    record = make_record()
    persist_extraction(tmp_path, record)
    manifest_path = tmp_path / MANIFEST_FILENAME
    existing = json.loads(manifest_path.read_text(encoding="utf-8"))
    existing["lots"][0]["state"] = advanced_state
    manifest_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    before = manifest_path.read_bytes()

    with pytest.raises(LotStateConflictError) as excinfo:
        persist_extraction(tmp_path, record)

    message = str(excinfo.value)
    assert advanced_state in message
    assert "Issues" in message
    # Aucune ecriture partielle.
    assert manifest_path.read_bytes() == before
    assert not list(tmp_path.glob(f".{MANIFEST_FILENAME}.*"))


# --------------------------------------------------------------------------
# AC 7 -- cardinal attendu non recompte
# --------------------------------------------------------------------------


def test_ac7_expected_frame_count_comes_from_the_selection_not_from_disk(tmp_path) -> None:
    record = make_record()
    write_lot_frames(tmp_path, record)
    # Un lot tronque sur disque ne doit pas modifier le cardinal declare.
    frames_path = tmp_path / record.frames_dir_relative
    next(iter(sorted(frames_path.iterdir()))).unlink()

    result = persist_extraction(tmp_path, record)

    lot = lot_of(result.manifest, record.lot_id)
    assert lot["expected_frame_count"] == record.selection.expected_frame_count == 14
    assert result.verification.observed_frame_count == 13
    assert VERIFY_FRAME_COUNT_MISMATCH in result.verification.findings


def test_ac7_selection_fields_are_redistributed_verbatim() -> None:
    selection = make_selection(source_frame_count_is_exact=False)
    manifest = build_extraction_manifest(None, make_record(selection))
    lot = manifest["lots"][0]

    assert lot["source_frame_count"] == selection.source_frame_count
    assert lot["source_frame_count_is_exact"] is False
    assert lot["source_tail_frames"] == selection.source_tail_frames
    assert lot["rounding_policy"] == ROUNDING_POLICY_ID
    assert lot["selection_warnings"] == list(selection.warnings)
    assert WARNING_SOURCE_FRAME_COUNT_ESTIMATED in lot["selection_warnings"]


def test_ac7_estimated_cardinal_leaves_its_reserve_in_the_manifest(tmp_path) -> None:
    record = make_record(make_selection(source_frame_count_is_exact=False))
    write_lot_frames(tmp_path, record)

    result = persist_extraction(tmp_path, record)

    lot = lot_of(result.manifest, record.lot_id)
    assert lot["source_frame_count_is_exact"] is False
    assert "SOURCE_FRAME_COUNT_ESTIMATED" in lot["selection_warnings"]
    assert VERIFY_SOURCE_COUNT_NOT_EXACT in result.verification.findings
    # Reserve informative: elle ne rend pas le lot non conforme.
    assert result.verification.ok


# --------------------------------------------------------------------------
# AC 8 -- base de timecode non devinable
# --------------------------------------------------------------------------


def test_ac8_timecode_base_and_base_fps_come_from_the_selection() -> None:
    manifest = build_extraction_manifest(None, make_record())
    lot = manifest["lots"][0]

    assert lot["timecode_base"] == "source"
    assert lot["timecode_base_fps"] == "30/1"  # denominateur toujours explicite
    assert lot["timecode_base_fps"] != "30"


@pytest.mark.parametrize("base", ["source", "target"])
def test_ac8_both_timecode_bases_traverse_persistence_unchanged(base) -> None:
    reference = make_selection()
    selection = FrameSelection(
        frames=reference.frames,
        fps_source=reference.fps_source,
        fps_target=reference.fps_target,
        source_frame_count=reference.source_frame_count,
        source_frame_count_is_exact=reference.source_frame_count_is_exact,
        expected_frame_count=reference.expected_frame_count,
        source_tail_frames=reference.source_tail_frames,
        rounding_policy=reference.rounding_policy,
        timecode_base=base,
        timecode_base_fps=reference.timecode_base_fps,
        source_start_timecode=reference.source_start_timecode,
        warnings=reference.warnings,
    )

    manifest = build_extraction_manifest(None, make_record(selection))

    assert manifest["lots"][0]["timecode_base"] == base


def test_ac8_fps_source_is_always_persisted() -> None:
    manifest = build_extraction_manifest(None, make_record())

    assert manifest["rushes"][0]["fps_source"] == 30.0
    assert manifest["rushes"][0]["fps_source_exact"] == "30/1"


def test_ac8_every_lot_timecode_validates_against_the_persisted_base_fps() -> None:
    record = make_record()
    manifest = build_extraction_manifest(None, record)
    base_fps = manifest["lots"][0]["timecode_base_fps"]

    # Aucune inference: `validate_timecode` accepte directement "num/den".
    for frame in record.selection.frames:
        validate_timecode(frame.frame_timecode, base_fps)

    # Et le meme timecode valide contre `fps_target` serait rejete: c'est
    # exactement l'ambiguite que `timecode_base_fps` supprime.
    with pytest.raises(ValueError):
        validate_timecode(
            manifest["lots"][0]["last_frame_timecode"], manifest["lots"][0]["fps_target"]
        )


def test_ac8_source_start_timecode_is_read_in_the_selection() -> None:
    selection = make_selection(source_start_timecode="01:00:00:12")

    manifest = build_extraction_manifest(None, make_record(selection))

    assert manifest["rushes"][0]["source_start_timecode"] == "01:00:00:12"
    assert manifest["lots"][0]["first_frame_timecode"] == "01:00:00:12"


def test_ac8_absent_start_timecode_is_omitted() -> None:
    manifest = build_extraction_manifest(None, make_record())

    assert "source_start_timecode" not in manifest["rushes"][0]


# --------------------------------------------------------------------------
# AC 9 -- cadences: valeur typee et valeur exacte
# --------------------------------------------------------------------------


def test_ac9_typed_and_exact_rates_are_both_persisted() -> None:
    manifest = build_extraction_manifest(None, make_record())

    assert manifest["rushes"][0]["fps_source"] == 30.0
    assert manifest["lots"][0]["fps_target"] == 4.0
    assert manifest["rushes"][0]["fps_source_exact"] == exact_frame_rate(30.0)
    assert manifest["lots"][0]["fps_target_exact"] == exact_frame_rate(4.0)


def test_ac9_divergent_typed_and_exact_rates_fail_explicitly() -> None:
    selection = make_selection(fps_source=30, fps_target=4)
    record = make_record(selection, fps_source=25.0)

    with pytest.raises(ExtractionPersistenceError) as excinfo:
        build_extraction_manifest(None, record)

    assert "incoherente" in str(excinfo.value)


@pytest.mark.parametrize(
    "fps_source,fps_target",
    [(24, 24), (25, 12.5)],
)
def test_ac9_fps_target_is_exactly_what_the_qr_payload_carries(fps_source, fps_target) -> None:
    # `io.reconstruction._check_manifest_conflicts` compare par egalite stricte.
    selection = make_selection(
        fps_source=fps_source, fps_target=fps_target, source_frame_count=50
    )
    record = make_record(
        selection, fps_source=float(fps_source), fps_target=float(fps_target)
    )

    manifest = build_extraction_manifest(None, record)

    assert manifest["lots"][0]["fps_target"] == float(fps_target)
    assert Fraction(manifest["lots"][0]["fps_target_exact"]) == selection.fps_target


# --------------------------------------------------------------------------
# AC 10 -- creation, mise a jour, refus de migration
# --------------------------------------------------------------------------


def test_ac10_creates_a_complete_v2_manifest_when_none_exists(tmp_path) -> None:
    result = persist_extraction(tmp_path, make_record())

    manifest = json.loads((tmp_path / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    for key in ("schema_version", "project_id", "rushes", "lots", "artifacts", "color", "video", "reconstruction"):
        assert key in manifest
    assert manifest["schema_version"] == "2.1"
    assert manifest["color"] == {}
    assert manifest["video"] == {}
    assert manifest["reconstruction"] == {}
    assert result.manifest_path == tmp_path / MANIFEST_FILENAME


def test_ac10_merges_without_losing_other_sections_lots_or_rushes(tmp_path) -> None:
    record = make_record()
    existing = build_extraction_manifest(None, record)
    existing["created"] = "2020-01-01T00:00:00Z"
    existing["color"] = {"target_colorspace": "rec709"}
    existing["reconstruction"] = {"template_id": "template-a4-16x9"}
    existing["rushes"].append({"rush_id": "rush-002", "source_path": "inputs/rush-002.mov"})
    existing["lots"].append({"lot_id": "rush-002_24", "rush_id": "rush-002", "state": "scan"})
    (tmp_path / MANIFEST_FILENAME).write_text(json.dumps(existing), encoding="utf-8")

    result = persist_extraction(tmp_path, record)

    manifest = result.manifest
    assert manifest["created"] == "2020-01-01T00:00:00Z"
    assert manifest["color"] == {"target_colorspace": "rec709"}
    assert manifest["reconstruction"] == {"template_id": "template-a4-16x9"}
    assert lot_of(manifest, "rush-002_24")["state"] == "scan"
    other_rush = next(r for r in manifest["rushes"] if r["rush_id"] == "rush-002")
    assert other_rush["source_path"] == "inputs/rush-002.mov"


def test_ac10_a_legacy_manifest_is_refused_without_any_write(tmp_path) -> None:
    legacy = {"id": "poc", "meta": {"video": {"resolution_source": {"width": 1920, "height": 1080}}}}
    manifest_path = tmp_path / MANIFEST_FILENAME
    manifest_path.write_text(json.dumps(legacy), encoding="utf-8")

    with pytest.raises(LegacyManifestError) as excinfo:
        persist_extraction(tmp_path, make_record())

    assert "migration" in str(excinfo.value)
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == legacy


def test_ac10_an_unsupported_schema_version_is_refused(tmp_path) -> None:
    existing = build_extraction_manifest(None, make_record())
    existing["schema_version"] = "3.0"

    with pytest.raises(LegacyManifestError):
        build_extraction_manifest(existing, make_record())


def test_ac10_a_foreign_project_id_is_refused(tmp_path) -> None:
    existing = build_extraction_manifest(None, make_record(project_id="proj-001"))

    with pytest.raises(ExtractionPersistenceError):
        build_extraction_manifest(existing, make_record(project_id="proj-002"))


# --------------------------------------------------------------------------
# AC 11 -- ecriture sure
# --------------------------------------------------------------------------


def test_ac11_an_invalid_manifest_leaves_the_previous_one_strictly_intact(
    tmp_path, monkeypatch
) -> None:
    record = make_record()
    persist_extraction(tmp_path, record)
    manifest_path = tmp_path / MANIFEST_FILENAME
    before = manifest_path.read_bytes()

    monkeypatch.setattr(
        extraction_manifest,
        "build_extraction_manifest",
        lambda existing, rec: {"schema_version": "2.0", "project_id": "x"},
    )

    with pytest.raises(ManifestWriteError):
        persist_extraction(tmp_path, record)

    assert manifest_path.read_bytes() == before
    assert [p.name for p in tmp_path.iterdir() if p.is_file()] == [MANIFEST_FILENAME]


def test_ac11_no_temporary_file_survives_a_failed_write(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        extraction_manifest,
        "build_extraction_manifest",
        lambda existing, rec: {"schema_version": "2.0"},
    )

    with pytest.raises(ManifestWriteError):
        persist_extraction(tmp_path, make_record())

    assert list(tmp_path.iterdir()) == []


def test_ac11_an_absolute_path_is_caught_before_replacement(tmp_path, monkeypatch) -> None:
    """`lots[].frames_dir`, pas `rushes[].source_path` (story 2.8,
    EPIC7-ARB-41): ce dernier est desormais la SEULE exception nommee a
    l'invariant de portabilite -- voir les tests dedies dans
    `test_manifest.py`."""
    record = make_record()
    valid = build_extraction_manifest(None, record)
    persist_extraction(tmp_path, record)
    before = (tmp_path / MANIFEST_FILENAME).read_bytes()

    def poisoned(existing, rec):
        broken = json.loads(json.dumps(valid))
        broken["lots"][0]["frames_dir"] = "/absolu/frames/rush-001_4"
        return broken

    monkeypatch.setattr(extraction_manifest, "build_extraction_manifest", poisoned)

    with pytest.raises(ManifestWriteError):
        persist_extraction(tmp_path, record)

    assert (tmp_path / MANIFEST_FILENAME).read_bytes() == before


# --------------------------------------------------------------------------
# AC 12 -- chemins relatifs POSIX
# --------------------------------------------------------------------------


def test_ac12_windows_separators_are_normalized_to_posix() -> None:
    # `_check_no_absolute_paths` n'attrape PAS `frames\rush-001_4`.
    record = make_record(frames_dir_relative="frames\\rush-001_4")

    manifest = build_extraction_manifest(None, record)

    assert manifest["lots"][0]["frames_dir"] == "frames/rush-001_4"
    assert "\\" not in manifest["lots"][0]["frames_dir"]


@pytest.mark.parametrize(
    "absolute",
    ["/srv/projets/frames/rush-001_4", "C:\\projets\\frames\\rush-001_4", "\\\\host\\share\\f"],
)
def test_ac12_absolute_lot_directories_are_refused(absolute) -> None:
    with pytest.raises(ExtractionPersistenceError):
        build_extraction_manifest(None, make_record(frames_dir_relative=absolute))


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("/media/disque/rush 001.mov", "rush 001.mov"),
        ("C:\\Rushes\\Tournage\\prise-eleve.mov", "prise-eleve.mov"),
        ("inputs/prise_ete_2026_cle.mov", "prise_ete_2026_cle.mov"),
        ("dossier/" + "n" * 180 + ".mov", "n" * 180 + ".mov"),
        ("/tmp/prise-\u00e9t\u00e9-\u4eac\u90fd.mov", "prise-\u00e9t\u00e9-\u4eac\u90fd.mov"),
    ],
)
def test_ac12_source_name_is_always_a_base_name(raw, expected) -> None:
    manifest = build_extraction_manifest(None, make_record(rush_source_name=raw))

    source_name = manifest["rushes"][0]["source_name"]
    assert source_name == expected
    assert "/" not in source_name and "\\" not in source_name


def test_ac12_unicode_and_spaced_lot_directory_survives_validation(tmp_path) -> None:
    record = make_record(frames_dir_relative="frames/rush \u00e9t\u00e9 001_4")
    write_lot_frames(tmp_path, record)

    result = persist_extraction(tmp_path, record)

    assert lot_of(result.manifest, record.lot_id)["frames_dir"] == "frames/rush \u00e9t\u00e9 001_4"
    validate_manifest(result.manifest_path)


# --------------------------------------------------------------------------
# AC 13 -- idempotence et re-extraction
# --------------------------------------------------------------------------


def _strip_non_idempotent(manifest: dict) -> dict:
    stripped = json.loads(json.dumps(manifest))
    stripped.pop("created", None)
    for lot in stripped.get("lots", []):
        lot.get("confirmation", {}).pop("confirmed_at", None)
    return stripped


def test_ac13_two_consecutive_runs_produce_an_identical_document(tmp_path) -> None:
    record_a = make_record(confirmed_at="2026-08-04T09:30:00Z")
    record_b = make_record(confirmed_at="2026-08-04T11:45:00Z")

    first = persist_extraction(tmp_path, record_a)
    first_bytes = (tmp_path / MANIFEST_FILENAME).read_bytes()
    second = persist_extraction(tmp_path, record_b)
    second_bytes = (tmp_path / MANIFEST_FILENAME).read_bytes()

    assert first_bytes != second_bytes  # seul confirmed_at a bouge
    assert _strip_non_idempotent(first.manifest) == _strip_non_idempotent(second.manifest)
    assert NON_IDEMPOTENT_FIELDS == ("created", "lots[].confirmation.confirmed_at")


def test_ac13_identical_inputs_are_byte_for_byte_identical(tmp_path) -> None:
    record = make_record()

    persist_extraction(tmp_path, record)
    first = (tmp_path / MANIFEST_FILENAME).read_bytes()
    persist_extraction(tmp_path, record)

    assert (tmp_path / MANIFEST_FILENAME).read_bytes() == first


def test_ac13_no_duplicate_lot_or_rush(tmp_path) -> None:
    record = make_record()

    for _ in range(3):
        result = persist_extraction(tmp_path, record)

    assert [lot["lot_id"] for lot in result.manifest["lots"]] == [record.lot_id]
    assert [rush["rush_id"] for rush in result.manifest["rushes"]] == [record.rush_id]


# --------------------------------------------------------------------------
# Story 2.8 (AC 1) -- persistance de rushes[].source_path
# --------------------------------------------------------------------------


def test_extraction_persists_absolute_source_path(tmp_path) -> None:
    """`extract` ecrit rushes[].source_path (chemin absolu resolu), et le
    manifest reste valide -- la SEULE exception a l'invariant de portabilite
    v2 (EPIC7-ARB-41)."""
    record = make_record(rush_source_path="/mnt/rushes/rush-001.mov")

    result = persist_extraction(tmp_path, record)

    assert result.manifest["rushes"][0]["source_path"] == "/mnt/rushes/rush-001.mov"
    validate_manifest(result.manifest_path)  # ne doit pas lever


def test_reextraction_from_a_different_path_replaces_source_path(tmp_path) -> None:
    """Une re-extraction du meme rush depuis un chemin different remplace la
    valeur, sans toucher aux autres champs du rush (AC 1)."""
    first = make_record(rush_source_path="/mnt/rushes/rush-001.mov")
    persist_extraction(tmp_path, first)

    second = make_record(rush_source_path="/mnt/rushes-archive/rush-001-copie.mov")
    result = persist_extraction(tmp_path, second)

    rush = result.manifest["rushes"][0]
    assert rush["source_path"] == "/mnt/rushes-archive/rush-001-copie.mov"
    # Aucun autre champ du rush n'a bouge entre les deux extractions.
    assert rush["source_name"] == "rush-001.mov"
    assert rush["fps_source"] == 30.0


def test_manifest_written_before_this_story_reads_without_source_path(tmp_path) -> None:
    """Un manifest v2.1 anterieur, sans `source_path`, reste lisible et valide
    (AC 3): le champ est optionnel et n'est jamais exige en lecture."""
    record = make_record(rush_source_path=None)

    result = persist_extraction(tmp_path, record)

    assert "source_path" not in result.manifest["rushes"][0]
    validate_manifest(result.manifest_path)  # ne doit pas lever


def test_ac13_a_second_rush_is_appended_not_merged(tmp_path) -> None:
    persist_extraction(tmp_path, make_record())
    second = make_record(
        make_selection(fps_source=25, fps_target=5, source_frame_count=100),
        fps_source=25.0,
        fps_target=5.0,
        rush_id="rush-002",
        rush_source_name="rush-002.mov",
    )

    result = persist_extraction(tmp_path, second)

    assert {r["rush_id"] for r in result.manifest["rushes"]} == {"rush-001", "rush-002"}
    assert {lot["lot_id"] for lot in result.manifest["lots"]} == {"rush-001_4", "rush-002_5"}


# --------------------------------------------------------------------------
# AC 14 -- trace de confirmation persistee
# --------------------------------------------------------------------------


def test_ac14_confirmation_block_carries_exactly_three_fields() -> None:
    record = make_record(
        confirmation_mode="interactif",
        unknown_color_accepted=True,
        confirmed_at="2026-08-04T09:30:00Z",
    )

    confirmation = build_extraction_manifest(None, record)["lots"][0]["confirmation"]

    assert confirmation == {
        "mode": "interactif",
        "unknown_color_accepted": True,
        "confirmed_at": "2026-08-04T09:30:00Z",
    }
    assert "granted" not in confirmation
    assert "unknown_color_fields" not in confirmation


def test_ac14_confirmed_at_pattern_is_enforced_by_the_schema(tmp_path) -> None:
    # `format: "date-time"` n'est verifie par aucune dependance de ce depot:
    # seul un `pattern` explicite garantit la forme.
    manifest = build_extraction_manifest(None, make_record())
    manifest["lots"][0]["confirmation"]["confirmed_at"] = "pas-une-date"
    path = tmp_path / MANIFEST_FILENAME
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValidationError):
        validate_manifest(path)


def test_ac14_an_unknown_confirmation_mode_is_refused() -> None:
    with pytest.raises(ExtractionPersistenceError):
        build_extraction_manifest(None, make_record(confirmation_mode="silencieux"))


def test_ac14_absent_fields_are_not_duplicated_in_the_confirmation_block() -> None:
    manifest = build_extraction_manifest(
        None, make_record(source_fields=UNTAGGED_SOURCE_FIELDS)
    )

    confirmation = manifest["lots"][0]["confirmation"]
    assert set(confirmation) == set(CONFIRMATION_FIELDS)
    assert manifest["rushes"][0]["source_metadata_absent_fields"]


# --------------------------------------------------------------------------
# AC 15 -- verifiabilite par un tiers
# --------------------------------------------------------------------------


def test_ac15_a_complete_lot_verifies(tmp_path) -> None:
    record = make_record()
    write_lot_frames(tmp_path, record)

    result = persist_extraction(tmp_path, record)
    report = result.verification

    assert report.ok
    assert report.observed_frame_count == report.expected_frame_count == 14
    assert report.missing_frames == ()
    assert report.unexpected_files == ()
    assert report.nonconforming_files == ()
    assert report.selection_recomputed is True
    assert report.digest_matches is True


def test_ac15_report_carries_only_stable_codes(tmp_path) -> None:
    record = make_record()
    write_lot_frames(tmp_path, record)
    result = persist_extraction(tmp_path, record)

    assert set(result.verification.findings) <= set(extraction_manifest.VERIFICATION_CODES)


def test_ac15_missing_extra_and_nonconforming_files_are_reported_separately(tmp_path) -> None:
    record = make_record()
    frames_path = write_lot_frames(tmp_path, record)
    result = persist_extraction(tmp_path, record)
    manifest = result.manifest

    sorted(frames_path.iterdir())[0].unlink()  # une manquante
    (frames_path / build_extracted_frame_filename("rush-001", 4.0, "23:59:59:29")).write_bytes(b"x")
    (frames_path / "notes.txt").write_bytes(b"x")

    report = verify_extracted_lot(tmp_path, manifest, record.lot_id)

    assert len(report.missing_frames) == 1
    assert report.unexpected_files == ("rush-001_4_23-59-59-29.tiff",)
    assert report.nonconforming_files == ("notes.txt",)
    assert VERIFY_MISSING_FRAMES in report.findings
    assert VERIFY_UNEXPECTED_FRAMES in report.findings
    assert VERIFY_NONCONFORMING_NAMES in report.findings
    assert not report.ok


def test_ac15_a_missing_lot_directory_is_reported(tmp_path) -> None:
    record = make_record()
    result = persist_extraction(tmp_path, record)

    report = verify_extracted_lot(tmp_path, result.manifest, record.lot_id)

    assert VERIFY_FRAMES_DIR_ABSENT in report.findings
    assert not report.ok


def test_ac15_an_unknown_lot_is_reported(tmp_path) -> None:
    result = persist_extraction(tmp_path, make_record())

    report = verify_extracted_lot(tmp_path, result.manifest, "lot-inconnu")

    assert report.findings == (VERIFY_LOT_ABSENT,)
    assert not report.ok


def test_ac15_level_three_is_flagged_when_not_executable(tmp_path) -> None:
    record = make_record()
    write_lot_frames(tmp_path, record)
    result = persist_extraction(tmp_path, record)
    crippled = json.loads(json.dumps(result.manifest))
    lot_of(crippled, record.lot_id).pop("source_frame_count")

    report = verify_extracted_lot(tmp_path, crippled, record.lot_id)

    assert report.selection_recomputed is False
    assert report.digest_matches is None
    assert VERIFY_SELECTION_NOT_RECOMPUTED in report.findings


def test_ac15_a_self_contradicting_manifest_is_blocking_not_informational(tmp_path) -> None:
    """Revue 2026-08-05: un document qui se contredit n'est pas un document illisible.

    Tous les parametres du recalcul sont presents, mais le noyau de selection
    les refuse (cadence source inferieure a la cadence cible). Avant le
    correctif, l'exception etait avalee et rendue comme `None`, ce qui
    desactivait d'un coup la comparaison d'empreinte **et** le calcul des noms
    attendus: `missing_frames` et `unexpected_files` restaient vides par
    construction et le lot ressortait conforme.
    """
    record = make_record()
    write_lot_frames(tmp_path, record)
    result = persist_extraction(tmp_path, record)
    tampered = json.loads(json.dumps(result.manifest))
    tampered["rushes"][0]["fps_source"] = 2
    tampered["rushes"][0].pop("fps_source_exact", None)

    report = verify_extracted_lot(tmp_path, tampered, record.lot_id)

    assert extraction_manifest.VERIFY_MANIFEST_INCOHERENT in report.findings
    assert VERIFY_SELECTION_NOT_RECOMPUTED not in report.findings
    assert report.ok is False


def test_ac15_a_missing_parameter_stays_informational(tmp_path) -> None:
    """Le pendant du test precedent: l'absence n'est pas la contradiction."""
    record = make_record()
    write_lot_frames(tmp_path, record)
    result = persist_extraction(tmp_path, record)
    crippled = json.loads(json.dumps(result.manifest))
    lot_of(crippled, record.lot_id).pop("source_frame_count")

    report = verify_extracted_lot(tmp_path, crippled, record.lot_id)

    assert VERIFY_SELECTION_NOT_RECOMPUTED in report.findings
    assert extraction_manifest.VERIFY_MANIFEST_INCOHERENT not in report.findings
    assert report.ok is True


def test_ac15_a_v2_1_manifest_never_falls_back_on_the_project_wide_rate(tmp_path) -> None:
    """Revue 2026-08-05: le defaut v2.0 ne doit pas rester atteignable en lecture.

    Un `video.fps_target` residuel dans un manifest v2.1 ne doit jamais servir
    de repli pour un lot: c'est la cadence unique par projet que la v2.1
    existe pour supprimer.
    """
    record = make_record()
    write_lot_frames(tmp_path, record)
    result = persist_extraction(tmp_path, record)
    forged = json.loads(json.dumps(result.manifest))
    lot_of(forged, record.lot_id).pop("fps_target")
    lot_of(forged, record.lot_id).pop("fps_target_exact", None)
    forged["video"]["fps_target"] = 99

    report = verify_extracted_lot(tmp_path, forged, record.lot_id)

    assert VERIFY_SELECTION_NOT_RECOMPUTED in report.findings
    assert report.selection_recomputed is False


def test_ac15_a_tampered_digest_is_detected(tmp_path) -> None:
    record = make_record()
    write_lot_frames(tmp_path, record)
    result = persist_extraction(tmp_path, record)
    tampered = json.loads(json.dumps(result.manifest))
    lot_of(tampered, record.lot_id)["frame_timecodes_digest"] = f"{FRAME_DIGEST_PREFIX}:" + "0" * 64

    report = verify_extracted_lot(tmp_path, tampered, record.lot_id)

    assert report.digest_matches is False
    assert extraction_manifest.VERIFY_DIGEST_MISMATCH in report.findings


def test_ac15_pending_encode_metadata_is_signalled_not_failed(tmp_path) -> None:
    record = make_record()
    write_lot_frames(tmp_path, record)

    report = persist_extraction(tmp_path, record).verification

    assert extraction_manifest.VERIFY_COMPLETENESS_PENDING in report.findings
    assert report.ok


def test_ac15_verification_never_touches_the_manifest(tmp_path) -> None:
    record = make_record()
    write_lot_frames(tmp_path, record)
    result = persist_extraction(tmp_path, record)
    before = (tmp_path / MANIFEST_FILENAME).read_bytes()
    snapshot = json.loads(json.dumps(result.manifest))

    verify_extracted_lot(tmp_path, result.manifest, record.lot_id)

    assert (tmp_path / MANIFEST_FILENAME).read_bytes() == before
    assert result.manifest == snapshot


# --------------------------------------------------------------------------
# AC 16 -- empreinte de selection
# --------------------------------------------------------------------------


def test_ac16_digest_shape() -> None:
    digest = compute_frame_timecodes_digest(make_selection())

    assert digest.startswith(f"{FRAME_DIGEST_PREFIX}:")
    payload = digest.split(":", 1)[1]
    assert len(payload) == 64
    assert set(payload) <= set("0123456789abcdef")


def test_ac16_digest_is_locked_on_a_reference_vector() -> None:
    # Vecteur `30 -> 4 fps, 100 frames` de la table de reference de la story
    # 3.2 (N = 14, dernier indice 97, tail 2).
    selection = make_selection(fps_source=30, fps_target=4, source_frame_count=100)

    assert compute_frame_timecodes_digest(selection) == (
        "sha256-v1:bda90a95ceda1741bd980ef124779498492e32b57b1509a2c34bd2b8656ec2a5"
    )


def test_ac16_digest_header_reads_directly_from_the_manifest() -> None:
    import hashlib

    selection = make_selection()
    manifest = build_extraction_manifest(None, make_record(selection))
    lot = manifest["lots"][0]

    header = f"{lot['rounding_policy']}|{lot['timecode_base']}|{lot['timecode_base_fps']}"
    lines = [f"{f.output_rank:08d}:{f.frame_timecode}" for f in selection.frames]
    recomputed = "sha256-v1:" + hashlib.sha256(
        "\n".join([header] + lines).encode("utf-8")
    ).hexdigest()

    assert recomputed == lot["frame_timecodes_digest"]


def test_ac16_a_single_changed_timecode_changes_the_digest() -> None:
    reference = make_selection()
    frames = list(reference.frames)
    frames[3] = SelectedFrame(
        output_rank=frames[3].output_rank,
        source_index=frames[3].source_index,
        frame_timecode="12:00:00:00",
    )
    altered = FrameSelection(
        frames=tuple(frames),
        fps_source=reference.fps_source,
        fps_target=reference.fps_target,
        source_frame_count=reference.source_frame_count,
        source_frame_count_is_exact=reference.source_frame_count_is_exact,
        expected_frame_count=reference.expected_frame_count,
        source_tail_frames=reference.source_tail_frames,
        rounding_policy=reference.rounding_policy,
        timecode_base=reference.timecode_base,
        timecode_base_fps=reference.timecode_base_fps,
        source_start_timecode=reference.source_start_timecode,
        warnings=reference.warnings,
    )

    assert compute_frame_timecodes_digest(altered) != compute_frame_timecodes_digest(reference)


@pytest.mark.parametrize(
    "field,value",
    [
        ("rounding_policy", "une-autre-politique-v9"),
        ("timecode_base", "target"),
        ("timecode_base_fps", Fraction(25)),
    ],
)
def test_ac16_policy_base_and_base_fps_all_change_the_digest(field, value) -> None:
    reference = make_selection()
    altered = FrameSelection(
        frames=reference.frames,
        fps_source=reference.fps_source,
        fps_target=reference.fps_target,
        source_frame_count=reference.source_frame_count,
        source_frame_count_is_exact=reference.source_frame_count_is_exact,
        expected_frame_count=reference.expected_frame_count,
        source_tail_frames=reference.source_tail_frames,
        rounding_policy=value if field == "rounding_policy" else reference.rounding_policy,
        timecode_base=value if field == "timecode_base" else reference.timecode_base,
        timecode_base_fps=value if field == "timecode_base_fps" else reference.timecode_base_fps,
        source_start_timecode=reference.source_start_timecode,
        warnings=reference.warnings,
    )

    assert compute_frame_timecodes_digest(altered) != compute_frame_timecodes_digest(reference)


def test_ac16_digest_never_uses_the_str_fraction_form() -> None:
    # `str(Fraction(30))` rend "30"; l'en-tete doit porter "30/1".
    import hashlib

    selection = make_selection()
    wrong_header = f"{selection.rounding_policy}|{selection.timecode_base}|{selection.timecode_base_fps}"
    lines = [f"{f.output_rank:08d}:{f.frame_timecode}" for f in selection.frames]
    wrong = "sha256-v1:" + hashlib.sha256(
        "\n".join([wrong_header] + lines).encode("utf-8")
    ).hexdigest()

    assert str(selection.timecode_base_fps) == "30"
    assert compute_frame_timecodes_digest(selection) != wrong


# --------------------------------------------------------------------------
# Gardes diverses
# --------------------------------------------------------------------------


def test_expected_frame_count_below_one_is_refused_before_any_write(tmp_path) -> None:
    reference = make_selection()
    empty = FrameSelection(
        frames=reference.frames,
        fps_source=reference.fps_source,
        fps_target=reference.fps_target,
        source_frame_count=reference.source_frame_count,
        source_frame_count_is_exact=reference.source_frame_count_is_exact,
        expected_frame_count=0,
        source_tail_frames=reference.source_tail_frames,
        rounding_policy=reference.rounding_policy,
        timecode_base=reference.timecode_base,
        timecode_base_fps=reference.timecode_base_fps,
        source_start_timecode=reference.source_start_timecode,
        warnings=reference.warnings,
    )

    with pytest.raises(ExtractionPersistenceError):
        persist_extraction(tmp_path, make_record(empty))
    assert not (tmp_path / MANIFEST_FILENAME).exists()


def test_a_non_positive_resolution_is_refused() -> None:
    with pytest.raises(ExtractionPersistenceError):
        build_extraction_manifest(None, make_record(source_width=0))


def test_build_extraction_manifest_does_no_io(tmp_path, monkeypatch) -> None:
    # Couche pure: aucun fichier cree par la fusion elle-meme.
    build_extraction_manifest(None, make_record())

    assert list(tmp_path.iterdir()) == []


# --------------------------------------------------------------------------
# Restructuration v2.1 -- un porteur par donnee (decisions-2026-08-04.md)
# --------------------------------------------------------------------------


def test_v2_1_extraction_never_writes_anything_into_video() -> None:
    """`video` ne porte plus que la cible d'encodage, que 3.4 n'ecrit pas."""
    manifest = build_extraction_manifest(None, make_record())

    assert manifest["video"] == {}
    assert EXTRACTION_VIDEO_FIELDS == ()


def test_v2_1_an_existing_video_section_is_copied_verbatim() -> None:
    existing = build_extraction_manifest(None, make_record())
    existing["video"] = {"codec_target": "prores"}

    merged = build_extraction_manifest(existing, make_record())

    assert merged["video"] == {"codec_target": "prores"}


def test_v2_1_two_target_rates_of_one_rush_coexist(tmp_path) -> None:
    """Le defaut corrige: chaque lot garde sa cadence et reste verifiable."""
    for fps_target in (4.0, 2.0):
        record = make_record(
            make_selection(fps_target=fps_target), fps_target=fps_target
        )
        write_lot_frames(tmp_path, record)
        result = persist_extraction(tmp_path, record)
        assert result.verification.ok, result.verification.findings

    manifest = json.loads((tmp_path / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    assert len(manifest["rushes"]) == 1
    assert sorted(lot["fps_target"] for lot in manifest["lots"]) == [2.0, 4.0]

    for lot_id in ("rush-001_4", "rush-001_2"):
        verification = verify_extracted_lot(tmp_path, manifest, lot_id)
        assert verification.ok, (lot_id, verification.findings)
        assert verification.digest_matches is True


def test_v2_1_three_target_rates_of_one_rush_all_verify(tmp_path) -> None:
    """Le scenario reel: 3, 5 et 12,5 im/s sur un meme rush."""
    for fps_target in (3.0, 5.0, 12.5):
        record = make_record(
            make_selection(fps_target=fps_target), fps_target=fps_target
        )
        write_lot_frames(tmp_path, record)
        persist_extraction(tmp_path, record)

    manifest = json.loads((tmp_path / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    assert len(manifest["lots"]) == 3

    for fps_target in (3.0, 5.0, 12.5):
        lot_id = build_lot_id("rush-001", fps_target)
        verification = verify_extracted_lot(tmp_path, manifest, lot_id)
        assert verification.ok, (lot_id, verification.findings)
        assert lot_of(manifest, lot_id)["fps_target"] == fps_target


def test_v2_1_two_rushes_keep_their_own_source_rate(tmp_path) -> None:
    for rush_id, fps_source in (("rush-001", 30.0), ("rush-002", 25.0)):
        record = make_record(
            make_selection(fps_source=fps_source, fps_target=5.0),
            rush_id=rush_id,
            rush_source_name=f"{rush_id}.mov",
            fps_source=fps_source,
            fps_target=5.0,
        )
        write_lot_frames(tmp_path, record)
        persist_extraction(tmp_path, record)

    manifest = json.loads((tmp_path / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    assert {rush["rush_id"]: rush["fps_source"] for rush in manifest["rushes"]} == {
        "rush-001": 30.0,
        "rush-002": 25.0,
    }
    for rush_id in ("rush-001", "rush-002"):
        verification = verify_extracted_lot(
            tmp_path, manifest, build_lot_id(rush_id, 5.0)
        )
        assert verification.ok, (rush_id, verification.findings)


def test_v2_1_verification_reads_the_target_rate_of_the_lot_not_of_the_project(
    tmp_path,
) -> None:
    """Reproduction directe de l'ancien defaut, sur le seul module de 3.4."""
    first = make_record(make_selection(fps_target=4.0), fps_target=4.0)
    write_lot_frames(tmp_path, first)
    persist_extraction(tmp_path, first)

    second = make_record(make_selection(fps_target=2.0), fps_target=2.0)
    write_lot_frames(tmp_path, second)
    persist_extraction(tmp_path, second)

    manifest = json.loads((tmp_path / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    verification = verify_extracted_lot(tmp_path, manifest, "rush-001_4")

    # Aucun constat bloquant: seul reste l'informatif « metadonnees a
    # renseigner avant encode », qui ne depend pas de la cadence.
    assert verification.blocking_findings == ()
    assert verification.missing_frames == ()
    assert verification.nonconforming_files == ()
    assert verification.digest_matches is True


# --- Migration v2.0 -> v2.1 ---------------------------------------------------


def _as_v2_0(manifest: dict) -> dict:
    """Retro-convertir un manifest v2.1 vers la forme v2.0 qu'ecrivait l'outil."""
    legacy = json.loads(json.dumps(manifest))
    legacy["schema_version"] = "2.0"
    video = dict(legacy.get("video") or {})
    rush = legacy["rushes"][0]
    # `source_frame_count` et `source_frame_count_is_exact` sont **retires**
    # sans etre reverses dans `video`: la v2.0 ne les y a jamais portes (son
    # schema les declare sur `lots[]`, et `video` y est ferme). Les y mettre
    # fabriquerait un manifeste v2.0 impossible, et la migration mesuree ici
    # cesserait de mesurer un cas reel. Ils sont arrives sur `rushes[]` par la
    # note 5 de la relecture d'Egan du 2026-09-01.
    for field in list(rush):
        if field in ("rush_id", "source_name", "source_path"):
            continue
        if field in ("source_frame_count", "source_frame_count_is_exact"):
            rush.pop(field)
            continue
        video[field] = rush.pop(field)
    for lot in legacy["lots"]:
        for field in ("fps_target", "fps_target_exact"):
            if field in lot:
                video[field] = lot.pop(field)
    legacy["video"] = video
    return legacy


def test_a_v2_0_manifest_is_migrated_in_memory_not_refused(tmp_path) -> None:
    record = make_record()
    write_lot_frames(tmp_path, record)
    legacy = _as_v2_0(build_extraction_manifest(None, record))

    merged = build_extraction_manifest(legacy, record)

    assert merged["schema_version"] == "2.1"
    assert merged["rushes"][0]["fps_source"] == 30.0
    assert merged["rushes"][0]["resolution_source"] == {"width": 1920, "height": 1080}
    assert merged["lots"][0]["fps_target"] == 4.0
    assert merged["video"] == {}


def test_migration_preserves_the_encode_target_of_the_project() -> None:
    legacy = _as_v2_0(build_extraction_manifest(None, make_record()))
    legacy["video"]["codec_target"] = "prores"

    merged = build_extraction_manifest(legacy, make_record())

    assert merged["video"] == {"codec_target": "prores"}


def test_migration_then_second_rate_leaves_both_lots_verifiable(tmp_path) -> None:
    first = make_record()
    write_lot_frames(tmp_path, first)
    legacy = _as_v2_0(build_extraction_manifest(None, first))
    (tmp_path / MANIFEST_FILENAME).write_text(json.dumps(legacy), encoding="utf-8")

    second = make_record(make_selection(fps_target=2.0), fps_target=2.0)
    write_lot_frames(tmp_path, second)
    result = persist_extraction(tmp_path, second)

    assert result.manifest["schema_version"] == "2.1"
    for lot_id in ("rush-001_4", "rush-001_2"):
        verification = verify_extracted_lot(tmp_path, result.manifest, lot_id)
        assert verification.ok, (lot_id, verification.findings)


def test_an_unknown_schema_version_is_still_refused_without_writing(tmp_path) -> None:
    existing = build_extraction_manifest(None, make_record())
    existing["schema_version"] = "9.9"
    (tmp_path / MANIFEST_FILENAME).write_text(json.dumps(existing), encoding="utf-8")
    before = (tmp_path / MANIFEST_FILENAME).read_text(encoding="utf-8")

    with pytest.raises(LegacyManifestError):
        persist_extraction(tmp_path, make_record())

    assert (tmp_path / MANIFEST_FILENAME).read_text(encoding="utf-8") == before


# --------------------------------------------------------------------------
# Revue du 2026-08-05
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "frames_dir",
    [
        "../frames/rush-001_4",
        "frames/../../ailleurs/rush-001_4",
        "frames\\..\\..\\ailleurs",
    ],
)
def test_un_dossier_de_lot_ne_peut_pas_remonter_hors_du_projet(tmp_path, frames_dir) -> None:
    """Un chemin relatif remontant est aussi destructeur qu'un chemin absolu.

    La garde amont ne refusait que l'absolu: le lot pouvait vivre hors du
    dossier projet, etre declare conforme, et ne pas suivre le transfert du
    projet.
    """
    record = make_record(frames_dir_relative=frames_dir)

    with pytest.raises(ExtractionPersistenceError, match="interieur du dossier projet"):
        persist_extraction(tmp_path, record)


def test_un_dossier_de_lot_nomme_deux_points_reste_accepte(tmp_path) -> None:
    """La garde porte sur la remontee, pas sur la sous-chaine `..`."""
    record = make_record(frames_dir_relative="frames/rush..001_4")
    write_lot_frames(tmp_path, record)

    result = persist_extraction(tmp_path, record)

    assert lot_of(result.manifest, record.lot_id)["frames_dir"] == "frames/rush..001_4"


def test_un_project_json_tronque_echoue_dans_la_hierarchie_du_module(tmp_path) -> None:
    """Une coupure pendant l'ecriture ne doit pas rendre une trace Python.

    `json.JSONDecodeError` echappait a `ExtractionPersistenceError`, la seule
    hierarchie que la CLI capture: l'operateur recevait une trace au lieu d'un
    message actionnable, sur un cas de panne parfaitement ordinaire.
    """
    record = make_record()
    write_lot_frames(tmp_path, record)
    (tmp_path / MANIFEST_FILENAME).write_text('{"schema_version": "2.1", "lo', encoding="utf-8")

    with pytest.raises(ExtractionPersistenceError, match="n'est pas un JSON valide"):
        persist_extraction(tmp_path, record)


def test_le_project_json_tronque_est_laisse_intact(tmp_path) -> None:
    record = make_record()
    write_lot_frames(tmp_path, record)
    tronque = '{"schema_version": "2.1", "lo'
    (tmp_path / MANIFEST_FILENAME).write_text(tronque, encoding="utf-8")

    with pytest.raises(ExtractionPersistenceError):
        persist_extraction(tmp_path, record)

    assert (tmp_path / MANIFEST_FILENAME).read_text(encoding="utf-8") == tronque
    assert not list(tmp_path.glob("*.tmp"))


def test_ac15_le_controle_de_nom_ne_reecrit_plus_le_motif_localement() -> None:
    """AC 15: la convention de nommage n'a qu'une implementation.

    Le module ne doit contenir aucune reconstruction locale du prefixe ni du
    motif de timecode: la lecture appartient a `io.naming`.
    """
    source = Path(extraction_manifest.__file__).read_text(encoding="utf-8")

    assert "read_extracted_frame_timecode" in source
    assert 'f"{derive_short_id(' not in source
    assert r"\d{2}-\d{2}-\d{2}-\d{2}" not in source


# --------------------------------------------------------------------------
# ARB-8: migration d'un ancien projet ambigu
# --------------------------------------------------------------------------


def _manifest_v2_0(*, rushes, lots) -> dict:
    return {
        "schema_version": "2.0",
        "project_id": "proj-001",
        "created": "2026-08-01T10:00:00Z",
        "rushes": rushes,
        "lots": lots,
        "artifacts": {},
        "color": {},
        "video": {
            "fps_source": 30.0,
            "fps_target": 2.0,
            "resolution_source": {"width": 1920, "height": 1080},
            "source_codec": "prores",
            "source_metadata_absent_fields": [],
        },
        "reconstruction": {},
    }


def test_arb8_un_ancien_projet_simple_est_migre_sans_perte() -> None:
    """Un seul rush, un seul lot: la replication est certaine, elle a lieu."""
    ancien = _manifest_v2_0(
        rushes=[{"rush_id": "rush-001"}],
        lots=[{"lot_id": "rush-001_2", "rush_id": "rush-001"}],
    )

    migre = extraction_manifest._migrate_v2_0(ancien)

    assert migre["schema_version"] == "2.1"
    assert migre["rushes"][0]["fps_source"] == 30.0
    assert migre["lots"][0]["fps_target"] == 2.0


def test_arb8_un_ancien_projet_ambigu_ne_fabrique_aucune_valeur() -> None:
    """Plusieurs lots: la v2.0 avait deja perdu l'information, on ne l'invente pas.

    Recopier la cadence unique du projet attribuait a `rushA_4` une cadence de
    2, contredisant son propre identifiant, et la verification le declarait
    corrompu alors que ses fichiers etaient intacts.
    """
    ancien = _manifest_v2_0(
        rushes=[{"rush_id": "rushA"}, {"rush_id": "rushB"}],
        lots=[
            {"lot_id": "rushA_4", "rush_id": "rushA"},
            {"lot_id": "rushA_2", "rush_id": "rushA"},
        ],
    )

    migre = extraction_manifest._migrate_v2_0(ancien)

    assert migre["schema_version"] == "2.1"
    for lot in migre["lots"]:
        assert "fps_target" not in lot, (
            "aucune cadence cible ne doit etre attribuee a un lot que le "
            "document v2.0 ne decrivait pas individuellement"
        )
    for rush in migre["rushes"]:
        assert "fps_source" not in rush
        assert "source_metadata_absent_fields" not in rush, (
            "affirmer « la source declarait tout » sur un rush jamais sonde "
            "est exactement ce que ce projet s'interdit"
        )


def test_migration_v2_0_transports_an_absolute_source_path_unmodified() -> None:
    """Story 2.8, AC 1 (frontiere): `_migrate_v2_0` copie chaque entree de
    rush par `dict(rush)` -- un `source_path` absolu present au manifest
    v2.0 traverse la migration tel quel, ni refuse ni modifie."""
    ancien = _manifest_v2_0(
        rushes=[{"rush_id": "rush-001", "source_path": "/mnt/rushes/rush-001.mov"}],
        lots=[{"lot_id": "rush-001_2", "rush_id": "rush-001"}],
    )

    migre = extraction_manifest._migrate_v2_0(ancien)

    assert migre["rushes"][0]["source_path"] == "/mnt/rushes/rush-001.mov"


def test_arb8_un_lot_migre_sans_cadence_est_dit_non_recalculable_pas_corrompu(tmp_path) -> None:
    """La consequence utile de l'arbitrage, vue depuis la verification."""
    ancien = _manifest_v2_0(
        rushes=[{"rush_id": "rushA"}, {"rush_id": "rushB"}],
        lots=[
            {"lot_id": "rushA_4", "rush_id": "rushA", "frames_dir": "frames/rushA_4"},
            {"lot_id": "rushA_2", "rush_id": "rushA", "frames_dir": "frames/rushA_2"},
        ],
    )
    migre = extraction_manifest._migrate_v2_0(ancien)
    (tmp_path / "frames" / "rushA_4").mkdir(parents=True)

    rapport = verify_extracted_lot(tmp_path, migre, "rushA_4")

    assert VERIFY_SELECTION_NOT_RECOMPUTED in rapport.findings
    assert extraction_manifest.VERIFY_NONCONFORMING_NAMES not in rapport.findings


# --------------------------------------------------------------------------
# Revue 3.7 -- ARB-3 tenu quelle que soit la longueur du nom de rush
# --------------------------------------------------------------------------


@pytest.mark.parametrize("longueur", [8, 30, 37, 38, 39, 44, 46, 47, 48])
def test_l_accord_arb3_ne_depend_pas_de_la_longueur_du_nom_de_rush(longueur) -> None:
    """Revue du 2026-08-06: le test d'accord n'echantillonnait que `rush-001`.

    Huit caracteres, alors que `normalize_identifier` en autorise 48 et qu'un
    nom de fichier camera en fait couramment 40. L'accord tenait par chance de
    la donnee: `build_lot_id` raccourcit son fragment a 48 caracteres,
    `rush_dir_slug` non, et le condensat de bornes en ajoute 9. Soit les deux
    concordent, soit l'extraction est refusee -- jamais un lot dont
    l'identifiant et le dossier se contredisent.
    """
    rush_id = normalize_identifier("R" * longueur, label="test")
    bornes = {
        "source_in_timecode": "00:00:01:00",
        "source_out_timecode": "00:00:02:00",
    }
    try:
        lot_id = build_lot_id(rush_id, 5, **bornes)
    except NamingError as refus:
        assert "renommer" in str(refus).lower()
        assert rush_id in str(refus)
        return
    assert lot_id == rush_dir_slug(rush_id, 5, **bornes)


@pytest.mark.parametrize("longueur", [8, 30, 44, 46, 47, 48])
def test_le_chemin_non_borne_n_est_pas_touche_par_le_refus(longueur) -> None:
    """Le refus ne vise que les extractions bornees.

    Le seuil de divergence du chemin **non borne** (47 caracteres) preexiste a
    la story 3.7 et n'est pas de son ressort: le durcir ici changerait le
    comportement d'extractions deja livrees.
    """
    rush_id = normalize_identifier("R" * longueur, label="test")
    build_lot_id(rush_id, 5)  # ne leve pas


def test_un_nom_de_rush_de_camera_ordinaire_est_refuse_avec_un_motif_lisible() -> None:
    """Le cas mesure a la revue, avec un vrai nom de fichier de tournage."""
    rush_id = normalize_identifier(
        "A005_C012_20260806_TOURNAGE_PLATEAU_PRISE_04", label="test"
    )
    assert len(rush_id) == 44

    build_lot_id(rush_id, 5)  # complet: accepte, inchange

    with pytest.raises(NamingError) as refus:
        build_lot_id(
            rush_id,
            5,
            source_in_timecode="00:00:01:00",
            source_out_timecode="00:00:02:00",
        )
    message = str(refus.value)
    assert "renommer" in message.lower()
    assert "38" in message or "trop long" in message.lower()
