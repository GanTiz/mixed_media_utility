"""Tests unitaires du contrat de donnees de previz d'extraction (story 3.5).

Aucun `skipif` sur ffmpeg, aucun binaire externe, aucun fichier lu ou ecrit:
le module teste est pur, ces tests doivent tourner partout (AC 1, AC 12).

Le detecteur de chemin absolu employe ici est **celui du projet**
(`io/manifest._iter_absolute_path_violations`), importe tel quel sous son nom
prive: cette story n'ajoute ni alias public ni second detecteur (Piege 8, et
`decisions-2026-08-02.md`).
"""

from __future__ import annotations

import ast
import json
import sys
from dataclasses import dataclass, replace
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import extraction_previz
from mixed_media_utility.extraction_previz import (
    ABSENT_THUMBNAIL,
    FINGERPRINT_PREFIX,
    LOT_INCOMPLETE,
    PREVIZ_KIND_EXTRACTION,
    PREVIZ_SCHEMA_VERSION,
    PREVIZ_STATE_EXTRACTED,
    PREVIZ_STATE_PLANNED,
    PREVIZ_STATES,
    PREVIZ_WARNING_CODES,
    SELECTION_FINGERPRINT_FIELDS,
    SOURCE_UNREADABLE,
    THUMBNAIL_DECODE_FAILED,
    THUMBNAIL_ORIGIN_EXTRACTED_FRAME,
    THUMBNAIL_ORIGIN_RUSH_DECODE,
    THUMBNAIL_ORIGINS,
    THUMBNAIL_STATE_ABSENT,
    THUMBNAIL_STATE_APPROXIMATE,
    THUMBNAIL_STATE_EXACT,
    THUMBNAIL_STATES,
    THUMBNAILS_APPROXIMATE_SEEK,
    THUMBNAILS_PARTIAL_BUDGET,
    THUMBNAILS_UNAVAILABLE_NO_FFMPEG,
    ExtractionPrevizError,
    ThumbnailRef,
    build_extraction_previz,
    canonical_json,
    fingerprint_of,
    previz_to_json_dict,
)
from mixed_media_utility.frame_selection import select_source_frames
from mixed_media_utility.io.manifest import _iter_absolute_path_violations
from mixed_media_utility.io import project_layout
from mixed_media_utility.source_confirmation import (
    SourceReport,
    build_source_report,
    source_report_to_json_dict,
)

MODULE_PATH = REPO_ROOT / "src" / "mixed_media_utility" / "extraction_previz.py"

GENERATED_AT = "2026-08-04T09:30:00Z"

#: Story 11.14, lot E1 -- le dossier des frames EXTRAITES, nomme par le module
#: qui le porte et non recompose ici. Ce banc n'etait pas rouge : rien dans le
#: chemin de la previz ne verifie qu'un dossier existe, donc ses vingt-deux
#: litteraux `frames/` continuaient de passer en decrivant un dossier que plus
#: aucune commande n'ecrit. Un banc vert sur le vocabulaire que la story RETIRE
#: est exactement ce que le lot D1 a trouve, et c'est un demi-contrat.
DOSSIER_DES_FRAMES = project_layout.EXTRACT_FRAMES_DIRNAME
BATCH_DIR = f"{DOSSIER_DES_FRAMES}/rush-001_1"


# --------------------------------------------------------------------------
# Entrees de reference: sorties reelles de 3.2 et 3.3, jamais reconstruites
# --------------------------------------------------------------------------


def _selection():
    """Vecteur de reference de la story 3.2: 30 -> 1 fps sur 100 frames."""
    return select_source_frames(
        fps_source=30, fps_target=1, source_frame_count=100
    )


def _probe(**stream_overrides: Any) -> dict:
    stream = {
        "codec_type": "video",
        "codec_name": "prores",
        "pix_fmt": "yuv422p10le",
        "width": 1920,
        "height": 1080,
        "r_frame_rate": "30/1",
        "color_range": "tv",
    }
    stream.update(stream_overrides)
    return {"streams": [stream], "format": {"tags": {}}}


def _report(selection=None, *, probe: dict | None = None) -> SourceReport:
    return build_source_report(
        probe if probe is not None else _probe(),
        fps_target=1,
        selection=selection if selection is not None else _selection(),
        batch_dir_relative=BATCH_DIR,
    )


def _build(**overrides: Any):
    selection = overrides.pop("selection", None)
    if selection is None:
        selection = _selection()
    kwargs: dict[str, Any] = {
        "selection": selection,
        "source_report": _report(selection),
        "project_id": "demo",
        "rush_id": "rush-001",
        "batch_dir_relative": BATCH_DIR,
        "generated_at_utc": GENERATED_AT,
    }
    kwargs.update(overrides)
    return build_extraction_previz(**kwargs)


# --------------------------------------------------------------------------
# Fixture canonique figee en dur (AC 12): tout renommage de champ la casse
# --------------------------------------------------------------------------

FROZEN_SUBJECT_JSON = (
    '{"batch_dir_relative":"' + BATCH_DIR + '",'
    '"expected_frame_count":4,'
    '"fps_source_exact":"30/1",'
    '"fps_target_exact":"1/1",'
    '"frames_present_count":null,'
    '"lot_id":null,'
    '"project_id":"demo",'
    '"rounding_policy":"floor-index-ceil-count-v1",'
    '"rush_id":"rush-001",'
    '"source_tail_frames":9,'
    '"timecode_base":"source",'
    '"timecode_base_fps_exact":"30/1"}'
)

FROZEN_FRAMES_JSON = (
    "["
    '{"frame_path_relative":null,"frame_timecode":"00:00:00:00","output_rank":0,'
    '"source_index":0,'
    '"thumbnail":{"decoded_source_index":null,"origin":null,"path_relative":null,'
    '"state":"absent"}},'
    '{"frame_path_relative":null,"frame_timecode":"00:00:01:00","output_rank":1,'
    '"source_index":30,'
    '"thumbnail":{"decoded_source_index":null,"origin":null,"path_relative":null,'
    '"state":"absent"}},'
    '{"frame_path_relative":null,"frame_timecode":"00:00:02:00","output_rank":2,'
    '"source_index":60,'
    '"thumbnail":{"decoded_source_index":null,"origin":null,"path_relative":null,'
    '"state":"absent"}},'
    '{"frame_path_relative":null,"frame_timecode":"00:00:03:00","output_rank":3,'
    '"source_index":90,'
    '"thumbnail":{"decoded_source_index":null,"origin":null,"path_relative":null,'
    '"state":"absent"}}'
    "]"
)

FROZEN_WARNINGS_JSON = '{"confirmation":[],"previz":[],"selection":[]}'

# Empreinte de selection du vecteur de reference: sha256 de la serialisation
# canonique des SEULES six entrees de decision de 3.2. Figee en dur: la
# recette d'empreinte ne peut plus changer sans que ce test le dise.
#     {"fps_source_exact":"30/1","fps_target_exact":"1/1",
#      "rounding_policy":"floor-index-ceil-count-v1","source_frame_count":100,
#      "source_start_timecode":null,"timecode_base":"source"}
FROZEN_SELECTION_FINGERPRINT = (
    "sha256-v1:7b8abdb6f78c61efab371ef32c065ea851b3ab76c81a0837a4467824d34a7c1e"
)


def test_canonical_document_matches_the_frozen_fixture():
    report = _report()
    previz = _build()
    document = previz_to_json_dict(previz)

    expected = {
        "previz_schema_version": "previz-1",
        "kind": "extraction",
        "state": "planned",
        "generated_at_utc": GENERATED_AT,
        "subject": {
            "project_id": "demo",
            "rush_id": "rush-001",
            "lot_id": None,
            "fps_source_exact": "30/1",
            "fps_target_exact": "1/1",
            "timecode_base": "source",
            "timecode_base_fps_exact": "30/1",
            "rounding_policy": "floor-index-ceil-count-v1",
            "batch_dir_relative": BATCH_DIR,
            "expected_frame_count": 4,
            "source_tail_frames": 9,
            "frames_present_count": None,
        },
        # La forme du rapport source appartient a la story 3.3 et n'est pas
        # redecrite ici: la redupliquer ferait de ce test un second contrat de
        # metadonnees source (Piege 1).
        "source_report": source_report_to_json_dict(report),
        "frames": [
            {
                "output_rank": 0,
                "source_index": 0,
                "frame_timecode": "00:00:00:00",
                "frame_path_relative": None,
                "thumbnail": {
                    "state": "absent",
                    "origin": None,
                    "path_relative": None,
                    "decoded_source_index": None,
                },
            },
            {
                "output_rank": 1,
                "source_index": 30,
                "frame_timecode": "00:00:01:00",
                "frame_path_relative": None,
                "thumbnail": {
                    "state": "absent",
                    "origin": None,
                    "path_relative": None,
                    "decoded_source_index": None,
                },
            },
            {
                "output_rank": 2,
                "source_index": 60,
                "frame_timecode": "00:00:02:00",
                "frame_path_relative": None,
                "thumbnail": {
                    "state": "absent",
                    "origin": None,
                    "path_relative": None,
                    "decoded_source_index": None,
                },
            },
            {
                "output_rank": 3,
                "source_index": 90,
                "frame_timecode": "00:00:03:00",
                "frame_path_relative": None,
                "thumbnail": {
                    "state": "absent",
                    "origin": None,
                    "path_relative": None,
                    "decoded_source_index": None,
                },
            },
        ],
        "warnings": {"selection": [], "confirmation": [], "previz": []},
        "fingerprints": {
            "selection": FROZEN_SELECTION_FINGERPRINT,
            "source_report": fingerprint_of(source_report_to_json_dict(report)),
            "source_signature": None,
        },
    }
    assert document == expected


def test_frozen_canonical_json_blocks():
    """Gel octet pour octet des blocs possedes par cette story."""
    document = previz_to_json_dict(_build())
    assert canonical_json(document["subject"]) == FROZEN_SUBJECT_JSON
    assert canonical_json(document["frames"]) == FROZEN_FRAMES_JSON
    assert canonical_json(document["warnings"]) == FROZEN_WARNINGS_JSON
    assert set(document) == {
        "previz_schema_version",
        "kind",
        "state",
        "generated_at_utc",
        "subject",
        "source_report",
        "frames",
        "warnings",
        "fingerprints",
    }


def test_envelope_constants_are_frozen():
    assert PREVIZ_SCHEMA_VERSION == "previz-1"
    assert PREVIZ_KIND_EXTRACTION == "extraction"
    assert PREVIZ_STATES == ("planned", "extracted")
    assert THUMBNAIL_STATES == ("absent", "exact", "approximate")
    assert THUMBNAIL_ORIGINS == (None, "rush_decode", "extracted_frame")
    assert PREVIZ_WARNING_CODES == (
        "LOT_INCOMPLETE",
        "THUMBNAILS_UNAVAILABLE_NO_FFMPEG",
        "THUMBNAILS_PARTIAL_BUDGET",
        "THUMBNAIL_DECODE_FAILED",
        "THUMBNAILS_APPROXIMATE_SEEK",
        "SOURCE_UNREADABLE",
    )
    assert SELECTION_FINGERPRINT_FIELDS == (
        "fps_source_exact",
        "fps_target_exact",
        "rounding_policy",
        "source_frame_count",
        # Entrees dans le contrat a la revue du 2026-08-06: les bornes decident
        # quelles images sortent, donc elles decident de la selection.
        "source_in_timecode",
        "source_out_timecode",
        "source_start_timecode",
        "timecode_base",
    )
    assert FINGERPRINT_PREFIX == "sha256-v1:"


# --------------------------------------------------------------------------
# Serialisation: JSON pur, deterministe, sans pixels
# --------------------------------------------------------------------------


def test_document_is_pure_json_and_round_trips():
    document = previz_to_json_dict(_build())
    text = json.dumps(document)
    assert json.loads(text) == document


def test_canonical_json_is_deterministic_across_builds():
    first = canonical_json(previz_to_json_dict(_build()))
    second = canonical_json(previz_to_json_dict(_build()))
    assert first == second
    # Aucun espace optionnel, cles triees, ASCII pur: la chaine est
    # reproductible d'un processus a l'autre.
    assert ", " not in first and '": ' not in first
    assert first.isascii()


def test_canonical_json_sorts_keys_whatever_the_insertion_order():
    assert canonical_json({"b": 1, "a": 2}) == canonical_json({"a": 2, "b": 1})
    assert canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'


def _leaves(value: Any):
    if isinstance(value, dict):
        for sub in value.values():
            yield from _leaves(sub)
    elif isinstance(value, list):
        for sub in value:
            yield from _leaves(sub)
    else:
        yield value


def test_document_carries_no_image_bytes_and_no_base64():
    document = previz_to_json_dict(
        _build(
            thumbnails={
                0: ThumbnailRef(
                    state=THUMBNAIL_STATE_EXACT,
                    origin=THUMBNAIL_ORIGIN_EXTRACTED_FRAME,
                    path_relative=f"{DOSSIER_DES_FRAMES}/rush-001_1/thumb_0.png",
                )
            }
        )
    )
    for leaf in _leaves(document):
        assert isinstance(leaf, (str, int, bool, type(None))), leaf
        assert not isinstance(leaf, bytes)
    # Le rapport source (story 3.3) est exclu: il porte legitimement
    # `disk_upper_bound_bytes`, qui est une taille, pas une charge utile.
    owned = {key: value for key, value in document.items() if key != "source_report"}
    text = canonical_json(owned)
    for banned in ("base64", "data:image", "image/png", "bytes", "pixels"):
        assert banned not in text


def test_every_frame_rate_is_an_explicit_rational_string():
    subject = previz_to_json_dict(_build())["subject"]
    for key in ("fps_source_exact", "fps_target_exact", "timecode_base_fps_exact"):
        value = subject[key]
        assert isinstance(value, str)
        numerator, separator, denominator = value.partition("/")
        assert separator == "/", key
        assert numerator.isdigit() and denominator.isdigit(), key
    # `str(Fraction(30))` rendrait "30": la forme sans denominateur explicite
    # produirait une empreinte differente de celle de la story 3.4.
    assert subject["fps_source_exact"] == "30/1"


def test_ntsc_rate_keeps_its_exact_ratio():
    selection = select_source_frames(
        fps_source="24000/1001", fps_target="24000/1001", source_frame_count=3
    )
    subject = previz_to_json_dict(
        _build(selection=selection, source_report=_report(selection))
    )["subject"]
    assert subject["fps_source_exact"] == "24000/1001"
    assert subject["timecode_base_fps_exact"] == "24000/1001"


# --------------------------------------------------------------------------
# Projection stricte (AC 2): valeurs sentinelles incoherentes, sorties verbatim
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class _SentinelFrame:
    output_rank: int
    source_index: int
    frame_timecode: str


@dataclass(frozen=True)
class _SentinelSelection:
    frames: tuple
    fps_source: Any
    fps_target: Any
    source_frame_count: int
    expected_frame_count: int
    source_tail_frames: int
    rounding_policy: str
    timecode_base: str
    timecode_base_fps: Any
    source_start_timecode: str | None
    warnings: tuple


def _sentinel_selection(**overrides: Any) -> _SentinelSelection:
    base = _SentinelSelection(
        frames=(
            _SentinelFrame(0, 999999, "77:77:77:77"),
            _SentinelFrame(5, 3, "00:00:00:01"),
        ),
        # Cible superieure a la source, cardinal sans rapport avec les frames,
        # tail negatif, base de timecode inventee: aucune de ces valeurs n'est
        # productible par la story 3.2. Elles ressortent pourtant telles
        # quelles, ce qui echouerait si ce module recalculait quoi que ce soit.
        fps_source=Fraction(7, 3),
        fps_target=Fraction(101, 7),
        source_frame_count=1234567,
        expected_frame_count=999,
        source_tail_frames=-42,
        rounding_policy="sentinelle-policy-v9",
        timecode_base="base-sentinelle",
        timecode_base_fps=Fraction(1, 3),
        source_start_timecode="99:99:99:99",
        warnings=("NON_DIVISIBLE_RATES", "SOURCE_FRAME_COUNT_ESTIMATED"),
    )
    return replace(base, **overrides)


def _sentinel_report(**overrides: Any) -> SourceReport:
    base = SourceReport(
        source_fields={
            "source_codec": "sentinelle-codec",
            "source_pix_fmt": "sentinelle-pixfmt",
            "source_bit_depth": 3,
            "source_sample_aspect_ratio": None,
            "source_color_primaries": None,
            "source_color_trc": None,
            "source_colorspace": None,
            "source_color_range": None,
        },
        resolution_source={"width": 7, "height": 11},
        display_resolution={"width": 13, "height": 17},
        is_anamorphic=True,
        display_aspect_ratio="19:23",
        bit_depth_origin="pix_fmt",
        fps_source_exact="29/5",
        fps_target_exact="31/7",
        source_start_timecode="88:88:88:88",
        timecode_base="base-sentinelle",
        timecode_base_fps_exact="37/11",
        first_frame_timecode="66:66:66:66",
        last_frame_timecode="55:55:55:55",
        expected_frame_count=4242,
        source_tail_frames=-7,
        selection_warnings=("NON_DIVISIBLE_RATES",),
        batch_dir_relative=f"{DOSSIER_DES_FRAMES}/sentinelle",
        disk_upper_bound_bytes=123456789,
        color_triplet_status="absent",
        requires_unknown_color_consent=True,
        color_range_missing=True,
        absent_fields=("source_color_primaries",),
    )
    return replace(base, **overrides)


def test_projection_transports_incoherent_sentinels_verbatim():
    selection = _sentinel_selection()
    report = _sentinel_report()
    document = previz_to_json_dict(
        build_extraction_previz(
            selection=selection,
            source_report=report,
            project_id="projet-sentinelle",
            rush_id="rush-sentinelle",
            batch_dir_relative=f"{DOSSIER_DES_FRAMES}/sentinelle",
            generated_at_utc=GENERATED_AT,
        )
    )

    subject = document["subject"]
    assert subject["fps_source_exact"] == "7/3"
    assert subject["fps_target_exact"] == "101/7"
    assert subject["timecode_base_fps_exact"] == "1/3"
    assert subject["timecode_base"] == "base-sentinelle"
    assert subject["rounding_policy"] == "sentinelle-policy-v9"
    # Ni recompte (2 frames pour un expected_frame_count de 999), ni corrige
    # (tail negatif), ni reconcilie (cible > source).
    assert subject["expected_frame_count"] == 999
    assert subject["source_tail_frames"] == -42
    assert len(document["frames"]) == 2

    # Les frames gardent leurs rangs non contigus et leurs timecodes
    # impossibles: aucun re-tri, aucune renumerotation, aucune validation de
    # timecode.
    assert [frame["output_rank"] for frame in document["frames"]] == [0, 5]
    assert [frame["source_index"] for frame in document["frames"]] == [999999, 3]
    assert document["frames"][0]["frame_timecode"] == "77:77:77:77"

    # Le rapport source est celui rendu par l'accesseur de la story 3.3, sans
    # aucune retouche.
    assert document["source_report"] == source_report_to_json_dict(report)
    assert document["source_report"]["fps_source_exact"] == "29/5"
    assert document["source_report"]["timecode"]["start"] == "88:88:88:88"


def test_source_start_timecode_is_never_validated_nor_converted():
    selection = _sentinel_selection()
    previz = build_extraction_previz(
        selection=selection,
        source_report=_sentinel_report(),
        project_id="p",
        rush_id="r",
        batch_dir_relative=f"{DOSSIER_DES_FRAMES}/p",
        generated_at_utc=GENERATED_AT,
    )
    # Le timecode de depart n'apparait pas dans le sujet (il vit dans le
    # rapport source) mais il entre dans l'empreinte de selection, verbatim.
    assert previz.fingerprints.selection == fingerprint_of(
        {
            "fps_source_exact": "7/3",
            "fps_target_exact": "101/7",
            "rounding_policy": "sentinelle-policy-v9",
            "source_frame_count": 1234567,
            "source_start_timecode": "99:99:99:99",
            "timecode_base": "base-sentinelle",
        }
    )


def test_project_id_and_lot_id_come_from_the_caller():
    previz = _build(project_id="autre-projet", lot_id="rush-001_1")
    assert previz.subject.project_id == "autre-projet"
    assert previz.subject.lot_id == "rush-001_1"
    # `lot_id` est possede par la story 3.4 et reste optionnel en `planned`.
    assert _build().subject.lot_id is None


# --------------------------------------------------------------------------
# Regimes planned / extracted (AC 7)
# --------------------------------------------------------------------------


def test_planned_is_the_default_regime_without_any_frame_path():
    document = previz_to_json_dict(_build())
    assert document["state"] == PREVIZ_STATE_PLANNED
    assert document["subject"]["frames_present_count"] is None
    assert all(frame["frame_path_relative"] is None for frame in document["frames"])


def test_planned_refuses_frames_present_count():
    with pytest.raises(ExtractionPrevizError, match="planned"):
        _build(frames_present_count=4)


def test_planned_refuses_frame_paths():
    with pytest.raises(ExtractionPrevizError, match="planned"):
        _build(frame_paths_relative={0: f"{DOSSIER_DES_FRAMES}/rush-001_1/f0.tiff"})


def test_extracted_requires_frames_present_count_from_the_caller():
    with pytest.raises(ExtractionPrevizError, match="frames_present_count"):
        _build(state=PREVIZ_STATE_EXTRACTED)


def test_extracted_carries_paths_and_a_caller_supplied_count():
    paths = {
        0: f"{DOSSIER_DES_FRAMES}/rush-001_1/rush-001_r0.tiff",
        1: f"{DOSSIER_DES_FRAMES}/rush-001_1/rush-001_r1.tiff",
    }
    document = previz_to_json_dict(
        _build(
            state=PREVIZ_STATE_EXTRACTED,
            frames_present_count=2,
            frame_paths_relative=paths,
        )
    )
    assert document["state"] == "extracted"
    assert document["subject"]["frames_present_count"] == 2
    # `expected_frame_count` continue de venir de la story 3.2 et jamais d'un
    # comptage: un lot partiel se declare partiel.
    assert document["subject"]["expected_frame_count"] == 4
    assert [frame["frame_path_relative"] for frame in document["frames"]] == [
        paths[0],
        paths[1],
        None,
        None,
    ]


def test_frames_present_count_is_never_recomputed_from_the_document():
    """Le module ne compte rien: il transporte ce que l'appelant lui donne.

    ARB-13 a change la borne haute: un document ne peut plus annoncer **plus**
    d'images presentes que la selection n'en retient, parce qu'il se
    contredirait lui-meme. En dessous du cardinal attendu, la valeur est
    transportee verbatim et le lot est declare incomplet.
    """
    document = previz_to_json_dict(
        _build(state=PREVIZ_STATE_EXTRACTED, frames_present_count=1)
    )

    assert document["subject"]["frames_present_count"] == 1
    assert document["subject"]["expected_frame_count"] == 4
    assert LOT_INCOMPLETE in document["warnings"]["previz"]


def test_un_lot_ne_peut_pas_porter_plus_d_images_que_la_selection():
    """ARB-13: 4 attendues et 4242 presentes etait accepte sans une objection."""
    with pytest.raises(ExtractionPrevizError, match="depasse le cardinal"):
        _build(state=PREVIZ_STATE_EXTRACTED, frames_present_count=4242)


def test_un_lot_complet_ne_porte_aucune_reserve_de_completude():
    document = previz_to_json_dict(
        _build(state=PREVIZ_STATE_EXTRACTED, frames_present_count=4)
    )

    assert LOT_INCOMPLETE not in document["warnings"]["previz"]


def test_un_lot_vide_est_declare_incomplet():
    document = previz_to_json_dict(
        _build(state=PREVIZ_STATE_EXTRACTED, frames_present_count=0)
    )

    assert LOT_INCOMPLETE in document["warnings"]["previz"]


def test_unknown_state_is_refused():
    with pytest.raises(ExtractionPrevizError, match="Etat de previz inconnu"):
        _build(state="en-cours")


def test_generated_at_must_be_utc_iso8601():
    for bad in ("2026-08-04 09:30:00", "2026-08-04T09:30:00+02:00", "hier", ""):
        with pytest.raises(ExtractionPrevizError):
            _build(generated_at_utc=bad)
    assert _build(generated_at_utc="2026-08-04T09:30:00.123456Z")


# --------------------------------------------------------------------------
# Vignettes (AC 6)
# --------------------------------------------------------------------------


def test_document_without_any_thumbnail_is_valid_and_complete():
    document = previz_to_json_dict(_build())
    assert len(document["frames"]) == 4
    for frame in document["frames"]:
        assert frame["thumbnail"] == {
            "state": "absent",
            "origin": None,
            "path_relative": None,
            "decoded_source_index": None,
        }
    assert document["warnings"]["previz"] == []


def test_exact_thumbnail_from_an_extracted_frame():
    document = previz_to_json_dict(
        _build(
            state=PREVIZ_STATE_EXTRACTED,
            frames_present_count=4,
            thumbnails={
                2: ThumbnailRef(
                    state=THUMBNAIL_STATE_EXACT,
                    origin=THUMBNAIL_ORIGIN_EXTRACTED_FRAME,
                    path_relative=f"{DOSSIER_DES_FRAMES}/rush-001_1/thumbs/r2.png",
                )
            },
        )
    )
    assert document["frames"][2]["thumbnail"] == {
        "state": "exact",
        "origin": "extracted_frame",
        "path_relative": f"{DOSSIER_DES_FRAMES}/rush-001_1/thumbs/r2.png",
        "decoded_source_index": None,
    }
    assert document["frames"][1]["thumbnail"]["state"] == "absent"


def test_approximate_thumbnail_declares_the_index_actually_decoded():
    document = previz_to_json_dict(
        _build(
            thumbnails={
                1: ThumbnailRef(
                    state=THUMBNAIL_STATE_APPROXIMATE,
                    origin=THUMBNAIL_ORIGIN_RUSH_DECODE,
                    path_relative=f"{DOSSIER_DES_FRAMES}/rush-001_1/thumbs/r1.png",
                    decoded_source_index=28,
                )
            },
            previz_warnings=[THUMBNAILS_APPROXIMATE_SEEK],
        )
    )
    thumbnail = document["frames"][1]["thumbnail"]
    assert thumbnail["state"] == "approximate"
    assert thumbnail["decoded_source_index"] == 28
    # Le rang demandait l'indice source 30, le decodeur a rendu 28: l'ecart est
    # visible, il n'est pas maquille en `exact`.
    assert document["frames"][1]["source_index"] == 30
    assert document["warnings"]["previz"] == ["THUMBNAILS_APPROXIMATE_SEEK"]


def test_approximate_thumbnail_without_decoded_index_is_refused():
    with pytest.raises(ExtractionPrevizError, match="decoded_source_index"):
        ThumbnailRef(
            state=THUMBNAIL_STATE_APPROXIMATE,
            origin=THUMBNAIL_ORIGIN_RUSH_DECODE,
            path_relative=f"{DOSSIER_DES_FRAMES}/rush-001_1/thumbs/r1.png",
        )


def test_decoded_index_is_refused_on_a_non_approximate_thumbnail():
    with pytest.raises(ExtractionPrevizError, match="decoded_source_index"):
        ThumbnailRef(state=THUMBNAIL_STATE_ABSENT, decoded_source_index=12)
    with pytest.raises(ExtractionPrevizError, match="decoded_source_index"):
        ThumbnailRef(
            state=THUMBNAIL_STATE_EXACT,
            origin=THUMBNAIL_ORIGIN_RUSH_DECODE,
            path_relative=f"{DOSSIER_DES_FRAMES}/rush-001_1/thumbs/r0.png",
            decoded_source_index=12,
        )


def test_a_thumbnail_declared_present_must_say_where_to_find_it():
    """Revue du 2026-08-05: la moitie miroir du vocabulaire de vignette.

    Le constructeur ne verrouillait qu'un seul couplage. Une vignette declaree
    exacte sans chemin est une presence affirmee sans localisation: le
    consommateur qui suit le document ne trouve rien.
    """
    for state in (THUMBNAIL_STATE_EXACT, THUMBNAIL_STATE_APPROXIMATE):
        with pytest.raises(ExtractionPrevizError, match="sans path_relative"):
            ThumbnailRef(
                state=state,
                origin=THUMBNAIL_ORIGIN_RUSH_DECODE,
                decoded_source_index=3 if state == THUMBNAIL_STATE_APPROXIMATE else None,
            )
    with pytest.raises(ExtractionPrevizError, match="sans origine"):
        ThumbnailRef(
            state=THUMBNAIL_STATE_EXACT,
            path_relative=f"{DOSSIER_DES_FRAMES}/rush-001_1/thumbs/r0.png",
        )


def test_a_thumbnail_declared_absent_carries_neither_path_nor_origin():
    """L'autre moitie: une vignette absente qui porte pourtant une image."""
    with pytest.raises(ExtractionPrevizError, match="absente portant un chemin"):
        ThumbnailRef(
            state=THUMBNAIL_STATE_ABSENT,
            path_relative=f"{DOSSIER_DES_FRAMES}/rush-001_1/thumbs/r0.png",
        )
    with pytest.raises(ExtractionPrevizError, match="absente portant une origine"):
        ThumbnailRef(
            state=THUMBNAIL_STATE_ABSENT,
            origin=THUMBNAIL_ORIGIN_EXTRACTED_FRAME,
        )


def test_unknown_thumbnail_vocabulary_is_refused():
    with pytest.raises(ExtractionPrevizError, match="Etat de vignette inconnu"):
        ThumbnailRef(state="peut-etre")
    with pytest.raises(ExtractionPrevizError, match="Origine de vignette inconnue"):
        ThumbnailRef(state=THUMBNAIL_STATE_EXACT, origin="capture-ecran")


def test_thumbnail_on_an_unknown_rank_is_refused():
    with pytest.raises(ExtractionPrevizError, match="rangs absents"):
        _build(thumbnails={99: ABSENT_THUMBNAIL})
    with pytest.raises(ExtractionPrevizError, match="rangs absents"):
        _build(
            state=PREVIZ_STATE_EXTRACTED,
            frames_present_count=1,
            frame_paths_relative={99: f"{DOSSIER_DES_FRAMES}/rush-001_1/f99.tiff"},
        )


# --------------------------------------------------------------------------
# Chemins (AC 5)
# --------------------------------------------------------------------------


def test_document_contains_no_absolute_path():
    document = previz_to_json_dict(
        _build(
            state=PREVIZ_STATE_EXTRACTED,
            frames_present_count=1,
            frame_paths_relative={0: f"{DOSSIER_DES_FRAMES}/rush-001_1/rush-001_r0.tiff"},
            thumbnails={
                0: ThumbnailRef(
                    state=THUMBNAIL_STATE_EXACT,
                    origin=THUMBNAIL_ORIGIN_EXTRACTED_FRAME,
                    path_relative=f"{DOSSIER_DES_FRAMES}/rush-001_1/thumbs/r0.png",
                )
            },
        )
    )
    assert _iter_absolute_path_violations(document) == []


@pytest.mark.parametrize(
    "absolute",
    ["/mnt/rushs/thumb.png", "C:\\rushs\\thumb.png", "\\\\serveur\\part\\thumb.png"],
)
def test_an_absolute_path_is_refused_on_every_channel(absolute):
    """AC 5 et AC 12: les chemins absolus sont **refuses**, pas seulement detectables.

    POSIX, lettre de lecteur Windows et UNC, sur les trois canaux de chemin du
    document. La version precedente de ce test construisait deliberement un
    document **valide** portant un chemin absolu, puis verifiait que le
    detecteur du projet saurait le reperer: elle prouvait la detection et
    verrouillait l'acceptation, alors que l'AC 5 exige le refus (revue du
    2026-08-05).

    Le module n'ecrit toujours pas son propre detecteur: il appelle
    `source_confirmation.normalize_relative_project_path`, la ou la story 3.3
    gardait deja le meme champ.
    """
    with pytest.raises(ExtractionPrevizError, match="pas absolu"):
        ThumbnailRef(
            state=THUMBNAIL_STATE_EXACT,
            origin=THUMBNAIL_ORIGIN_RUSH_DECODE,
            path_relative=absolute,
        )

    with pytest.raises(ExtractionPrevizError, match="pas absolu"):
        _build(batch_dir_relative=absolute)

    with pytest.raises(ExtractionPrevizError, match="pas absolu"):
        _build(
            state=PREVIZ_STATE_EXTRACTED,
            frames_present_count=4,
            frame_paths_relative={0: absolute},
        )


@pytest.mark.parametrize("remontant", ["../ailleurs/thumb.png", f"{DOSSIER_DES_FRAMES}/../../x.png"])
def test_a_path_climbing_out_of_the_project_is_refused(remontant):
    """Une remontee `..` place la cible hors de ce qu'un transfert emporte."""
    with pytest.raises(ExtractionPrevizError, match="interieur du dossier projet"):
        _build(batch_dir_relative=remontant)


def test_a_document_built_normally_carries_no_absolute_path():
    """Le detecteur du projet fait foi, et confirme sur un document reel."""
    document = previz_to_json_dict(
        _build(
            thumbnails={
                0: ThumbnailRef(
                    state=THUMBNAIL_STATE_EXACT,
                    origin=THUMBNAIL_ORIGIN_RUSH_DECODE,
                    path_relative=f"{DOSSIER_DES_FRAMES}/rush-001_1/thumbs/r0.png",
                )
            }
        )
    )

    assert _iter_absolute_path_violations(document) == []


def test_the_source_rush_path_is_not_a_field_of_the_contract():
    document = previz_to_json_dict(_build())
    text = canonical_json(document)
    for banned in ("source_path", "rush_path", "input_path", "video_path", ".mov"):
        assert banned not in text


# --------------------------------------------------------------------------
# Avertissements (AC 8, AC 9)
# --------------------------------------------------------------------------


def test_the_three_warning_families_stay_separate_and_verbatim():
    selection = select_source_frames(
        fps_source=30, fps_target=4, source_frame_count=100
    )
    document = previz_to_json_dict(
        _build(
            selection=selection,
            source_report=_report(selection),
            previz_warnings=[THUMBNAILS_UNAVAILABLE_NO_FFMPEG, SOURCE_UNREADABLE],
            confirmation_warnings=["CODE_HYPOTHETIQUE_DE_33"],
        )
    )
    assert document["warnings"] == {
        "selection": ["NON_DIVISIBLE_RATES"],
        "confirmation": ["CODE_HYPOTHETIQUE_DE_33"],
        "previz": ["THUMBNAILS_UNAVAILABLE_NO_FFMPEG", "SOURCE_UNREADABLE"],
    }
    assert list(selection.warnings) == document["warnings"]["selection"]


def test_confirmation_warnings_default_to_empty_and_are_never_fabricated():
    """La story 3.3 n'expose aucun code stable: le vide n'est pas comble."""
    document = previz_to_json_dict(_build())
    assert document["warnings"]["confirmation"] == []
    # La reserve colorimetrique se lit dans le rapport source, transporte
    # verbatim, jamais sous forme d'un code invente ici.
    assert document["source_report"]["color"]["triplet_status"] == "absent"
    assert document["source_report"]["color"]["requires_unknown_color_consent"] is True


def test_unknown_previz_warning_code_is_refused():
    with pytest.raises(ExtractionPrevizError, match="inconnu"):
        _build(previz_warnings=["THUMBNAILS_TOO_SLOW"])


def test_every_previz_warning_code_of_the_vocabulary_is_accepted():
    document = previz_to_json_dict(_build(previz_warnings=list(PREVIZ_WARNING_CODES)))
    assert document["warnings"]["previz"] == list(PREVIZ_WARNING_CODES)


def test_a_degraded_case_produces_a_valid_partial_document_not_an_exception():
    document = previz_to_json_dict(
        _build(previz_warnings=[THUMBNAIL_DECODE_FAILED, THUMBNAILS_PARTIAL_BUDGET])
    )
    assert document["previz_schema_version"] == "previz-1"
    assert len(document["frames"]) == 4
    assert document["warnings"]["previz"] == [
        "THUMBNAIL_DECODE_FAILED",
        "THUMBNAILS_PARTIAL_BUDGET",
    ]


def test_a_bare_string_is_not_a_warning_list():
    with pytest.raises(ExtractionPrevizError, match="sequence de codes"):
        _build(previz_warnings="SOURCE_UNREADABLE")


# --------------------------------------------------------------------------
# Empreintes de fraicheur (AC 10)
# --------------------------------------------------------------------------


def test_fingerprint_recipe_is_sha256_of_the_canonical_json():
    import hashlib

    payload = {"b": 2, "a": 1}
    expected = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    assert fingerprint_of(payload) == f"sha256-v1:{expected}"


def test_selection_fingerprint_covers_the_six_decision_inputs_only():
    selection = _selection()
    previz = _build(selection=selection, source_report=_report(selection))
    assert previz.fingerprints.selection == fingerprint_of(
        {
            "fps_source_exact": "30/1",
            "fps_target_exact": "1/1",
            "rounding_policy": selection.rounding_policy,
            "source_frame_count": 100,
            "source_start_timecode": None,
            "timecode_base": "source",
        }
    )
    assert previz.fingerprints.selection == FROZEN_SELECTION_FINGERPRINT


def test_adding_or_removing_a_thumbnail_changes_neither_fingerprint():
    without = _build()
    with_thumbnail = _build(
        thumbnails={
            0: ThumbnailRef(
                state=THUMBNAIL_STATE_APPROXIMATE,
                origin=THUMBNAIL_ORIGIN_RUSH_DECODE,
                path_relative=f"{DOSSIER_DES_FRAMES}/rush-001_1/thumbs/r0.png",
                decoded_source_index=0,
            )
        },
        previz_warnings=[THUMBNAILS_APPROXIMATE_SEEK],
    )
    assert with_thumbnail.fingerprints.selection == without.fingerprints.selection
    assert with_thumbnail.fingerprints.source_report == without.fingerprints.source_report
    # Le document, lui, a bien change: c'est l'empreinte qui est insensible,
    # pas la previz.
    assert previz_to_json_dict(with_thumbnail) != previz_to_json_dict(without)


def test_changing_fps_target_changes_the_selection_fingerprint():
    selection_a = select_source_frames(
        fps_source=30, fps_target=1, source_frame_count=100
    )
    selection_b = select_source_frames(
        fps_source=30, fps_target=4, source_frame_count=100
    )
    previz_a = _build(selection=selection_a, source_report=_report(selection_a))
    previz_b = _build(selection=selection_b, source_report=_report(selection_b))
    assert previz_a.fingerprints.selection != previz_b.fingerprints.selection


def test_changing_a_source_colour_field_changes_the_source_report_fingerprint():
    selection = _selection()
    untagged = _build(selection=selection, source_report=_report(selection))
    tagged = _build(
        selection=selection,
        source_report=_report(
            selection,
            probe=_probe(
                color_primaries="bt709", color_transfer="bt709", color_space="bt709"
            ),
        ),
    )
    assert tagged.fingerprints.source_report != untagged.fingerprints.source_report
    # ... et l'empreinte de selection, elle, ne bouge pas: les deux portees
    # sont distinctes.
    assert tagged.fingerprints.selection == untagged.fingerprints.selection


def test_source_report_fingerprint_uses_the_accessor_of_story_3_3():
    selection = _selection()
    report = _report(selection)
    previz = _build(selection=selection, source_report=report)
    assert previz.fingerprints.source_report == fingerprint_of(
        source_report_to_json_dict(report)
    )


def test_source_signature_is_transported_never_computed():
    assert _build().fingerprints.source_signature is None
    signature = "sha256-v1:0123456789abcdef"
    assert _build(source_signature=signature).fingerprints.source_signature == signature
    # Elle n'entre dans aucune des deux empreintes calculees.
    assert (
        _build(source_signature=signature).fingerprints.selection
        == _build().fingerprints.selection
    )


def test_fingerprints_carry_the_algorithm_version_prefix():
    previz = _build()
    assert previz.fingerprints.selection.startswith("sha256-v1:")
    assert previz.fingerprints.source_report.startswith("sha256-v1:")


# --------------------------------------------------------------------------
# Purete du module (AC 1) -- analyse AST, pas seulement les imports
# --------------------------------------------------------------------------

ALLOWED_ABSOLUTE_IMPORTS = {
    "__future__",
    # `copy` est de la bibliotheque standard et strictement pur: il sert a
    # rendre le rapport source par copie profonde, pour que le document dit
    # « gele » le soit reellement (revue du 2026-08-05). Il ne touche a aucune
    # entree-sortie, donc il ne dement pas l'AC 1.
    "copy",
    "dataclasses",
    "datetime",
    "hashlib",
    "json",
    "re",
    "typing",
}
# `previz_common` elargit la liste blanche a la story 5.8, et c'est la **seule**
# modification qu'elle apporte a cette suite. Motif: la note differee du
# 2026-08-06 (« jonction previz_common a ouvrir chez 3.5 ») designait
# nommement 5.8 ou 6.4 comme le moment d'extraire les helpers et la validation
# d'horodatage, « et mettre a jour la liste blanche des deux suites de tests
# dans la meme story ». Le module ajoute est de la meme famille et du meme
# standard de purete que celui-ci -- sa propre analyse AST vit dans
# `tests/unit/test_scan_previz.py`, sans quoi elargir ici reviendrait a ouvrir
# une porte que plus personne ne garde.
ALLOWED_RELATIVE_IMPORTS = {"codec_profiles", "previz_common", "source_confirmation"}
FORBIDDEN_CALL_NAMES = {"open", "print", "input", "exec", "eval"}


def _module_tree() -> ast.Module:
    return ast.parse(MODULE_PATH.read_text(encoding="utf-8"), filename=str(MODULE_PATH))


def test_module_imports_are_whitelisted():
    offenders = []
    for node in ast.walk(_module_tree()):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in ALLOWED_ABSOLUTE_IMPORTS:
                    offenders.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                if (node.module or "") not in ALLOWED_RELATIVE_IMPORTS:
                    offenders.append(f".{node.module}")
            elif (node.module or "") not in ALLOWED_ABSOLUTE_IMPORTS:
                offenders.append(node.module or "")
    assert offenders == []


def test_module_calls_no_io_primitive():
    """`open` et `print` sont des primitives: aucun import ne les trahit."""
    offenders = []
    for node in ast.walk(_module_tree()):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in FORBIDDEN_CALL_NAMES:
                offenders.append((func.id, node.lineno))
            if isinstance(func, ast.Attribute) and func.attr in FORBIDDEN_CALL_NAMES:
                offenders.append((func.attr, node.lineno))
    assert offenders == []


def test_module_references_no_forbidden_module():
    forbidden_modules = {
        "subprocess",
        "cv2",
        "PIL",
        "numpy",
        "pathlib",
        "argparse",
        "os",
        "sys",
        "shutil",
        "jsonschema",
        "requests",
        "tkinter",
        "PySide6",
        "PyQt5",
        "PyQt6",
        "wx",
        "kivy",
        "reportlab",
        "ffmpeg",
    }
    referenced = set()
    for node in ast.walk(_module_tree()):
        if isinstance(node, ast.Import):
            referenced.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level:
            referenced.add((node.module or "").split(".")[0])
    assert referenced & forbidden_modules == set()


def test_module_never_touches_the_manifest_or_the_io_package():
    for node in ast.walk(_module_tree()):
        if isinstance(node, ast.ImportFrom) and node.level:
            assert not (node.module or "").startswith("io")


def test_requirements_gain_no_dependency_from_this_story():
    """Une dependance ajoutee ici serait le signal d'une preemption d'Epic 7."""
    requirements = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
    packages = {
        line.split("==")[0].split(">=")[0].strip().lower()
        for line in requirements.splitlines()
        if line.strip() and not line.startswith("#")
    }
    assert packages == {
        "ffmpeg-python",
        # AJOUTE PAR LA STORY 8.10, et porte ici le 2026-09-09 -- il aurait du
        # l'etre dans le meme mouvement que les deux autres copies. Le defaut
        # est celui que ce depot nomme lui-meme : « un remede recopie a cinq
        # endroits diverge ». Cette frontiere existe en QUATRE exemplaires ; le
        # triage du 2026-09-08 n'en a corrige que DEUX, et la premiere CI
        # publique a rendu les deux autres rouges.
        #
        # `pyyaml` entre dans `requirements.txt` parce que
        # `tests/unit/test_politique_lfs.py` lit les workflows sur le YAML
        # ANALYSE et que sa lecture ne doit plus pouvoir SAUTER. Ce n'est donc
        # PAS une preemption d'Epic 7, ce que cette frontiere existe pour
        # attraper -- c'est une dependance de BANC, documentee a sa ligne.
        "pyyaml",
        # `EPIC11-ARB-253` / `-254` (2026-09-06) : deux RENOMMAGES, pas deux
        # ajouts, portes ici le 2026-09-07 par `5635d70a` qui a aligne
        # `requirements.txt` sur `pyproject.toml`.
        # `opencv-contrib-python` -> `opencv-python-headless` : les roues
        # non-headless lient leur binaire a douze bibliotheques systeme
        # graphiques absentes d'une machine vierge, et `import cv2` y echoue sur
        # `libGL.so.1` avant la premiere ligne du produit. Les 51 symboles
        # `cv2.*` employes par `src/` ont ete testes un a un contre la roue
        # non-contrib, aucun ne manque -- l'ArUco a quitte `contrib` pour
        # `objdetect` en 4.7.
        # `pyside6` -> `pyside6-essentials` : le metapaquet tirait 401 Mo
        # d'Addons (dont un Chromium complet pour QtWebEngine) qu'aucun fichier
        # du depot n'importe.
        # L'ensemble reste epingle en egalite STRICTE : une dependance
        # reellement AJOUTEE continue de faire rougir ce test.
        "opencv-python-headless",
        "numpy",
        "pillow",
        "reportlab",
        # Ajoutee par la story 5.1 (EPIC5-ARB-4): le PDF est une forme d'entree
        # de plein droit du scan, rasterisee par PDFium. Seul amendement de test
        # existant que cette story s'autorise, et il ne touche ni l'intention du
        # test -- une dependance ajoutee reste un signal -- ni sa docstring.
        "pypdfium2",
        "jsonschema",
        # Reconciliation 11/EPIC11-ARB-250 (2026-09-06) : `segno` est l'ajout
        # MANDATE par l'arbitrage qui sort l'ENCODAGE QR d'OpenCV. Meme regime
        # que `pyside6` / `pytest-qt` en 2026-08-24 et `textual` en 2026-08-28 :
        # l'ensemble reste epingle en egalite STRICTE, pour que toute dependance
        # future non mandatee continue de faire rougir ce test. Le module previz
        # de cette fiche n'importe pas `segno` (verrou AST de purete ci-dessus)
        # -- `qr_codes.py` est le seul module de `src/` a l'importer, et
        # `test_encodeur_qr_segno.py` le mesure.
        #
        # Le motif, parce qu'une reconciliation sans motif est une tolerance
        # muette : la ligne 4.10/4.11 d'OpenCV ENCODE un symbole malforme
        # au-dela de la version 7, illisible par tout lecteur. Le plancher de
        # version qui aurait ferme le defaut sortait macOS 12 x86_64 de la
        # compatibilite (4.10.0.84 est la derniere roue `macosx_12_0_x86_64`) ;
        # `segno` publie une roue `py3-none-any` et n'exclut personne.
        "segno",
        "pytest",
        # Reconciliation 7.0 (2026-08-24): pyside6 et pytest-qt sont les deux
        # ajouts MANDATES par la story 7.0 (socle GUI -- sa fiche les specifie
        # nommement, AC 1). L'Epic 7 n'est plus une preemption a interdire mais
        # un developpement en cours. L'ensemble reste epingle en egalite
        # stricte pour que toute dependance future non mandatee continue de
        # faire rougir ce test ; l'intention et la docstring sont intactes
        # (meme geste que l'amendement 5.1 ci-dessus, et que la reconciliation
        # deja faite dans test_scan_previz.py par la story 5.26).
        "pyside6-essentials",
        "pytest-qt",
        # Reconciliation 5.x/11.0 (2026-08-28) : `textual` est l'ajout
        # MANDATE par la story 11.0 (socle TUI, AC 6.2 le specifie nommement,
        # epingle par serie majeure comme les autres lignes). Meme regime que
        # `pyside6` / `pytest-qt` en 2026-08-24 : l'ensemble reste epingle en
        # egalite STRICTE, pour que toute dependance future non mandatee
        # continue de faire rougir ce test. Le module previz de cette fiche
        # n'importe toujours aucun des trois (verrou AST de purete ci-dessus).
        #
        # **Et ce jour est arrive** : la liaison du 2026-09-01 amene le paquet
        # `tui/` sur cette branche. La phrase precedente annoncait « ce banc
        # rougira si l'un vient sans l'autre » -- il a rougi, sur les trois
        # bancs previz a la fois, exactement comme elle le promettait. La ligne
        # revient donc, et `requirements.txt` la porte deja.
        "textual",
    }


# --------------------------------------------------------------------------
# Une previz n'autorise rien (AC 11)
# --------------------------------------------------------------------------

INTERACTION_LAYER_NAMES = {
    "confirm_source_metadata",
    "render_source_report",
    "render_confirmation_question",
    "detect_interactive",
    "ConfirmationResult",
}

LAUNCH_PREFIXES = (
    "run",
    "launch",
    "start",
    "execute",
    "confirm",
    "approve",
    "authorize",
    "trigger",
    "persist",
    "save",
    "write",
    "apply",
    "validate_",
)


def test_module_never_references_the_interaction_layer_of_story_3_3():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = _module_tree()
    referenced = {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    } | {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            referenced.update(alias.name for alias in node.names)
    assert referenced & INTERACTION_LAYER_NAMES == set()
    assert "confirm_source_metadata" not in source


def test_module_exposes_no_launch_function():
    public_names = [
        node.name
        for node in ast.walk(_module_tree())
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    ]
    assert set(public_names) <= set(extraction_previz.__all__)
    for name in public_names + list(extraction_previz.__all__):
        assert not name.lower().startswith(LAUNCH_PREFIXES), name


def test_document_carries_no_consent_and_no_trigger():
    document = previz_to_json_dict(_build())
    # Le rapport source est exclu de l'examen: il appartient a la story 3.3 et
    # est transporte verbatim. Ce qui est verifie ici, c'est que la previz
    # n'ajoute de son cote AUCUN champ exploitable comme un accord.
    owned = {key: value for key, value in document.items() if key != "source_report"}
    text = canonical_json(owned)
    for banned in (
        "granted",
        "consent",
        "confirmed_at",
        "unknown_color_accepted",
        "confirmation_mode",
    ):
        assert banned not in text
    assert "confirmation" not in set(document)
    # `requires_unknown_color_consent` vit dans le rapport source, ou il est un
    # CONSTAT de la story 3.3; la previz n'en fabrique aucun de son cote.
    assert (
        document["source_report"]["color"]["requires_unknown_color_consent"] is True
    )


# --------------------------------------------------------------------------
# Revue du 2026-08-05
# --------------------------------------------------------------------------


def test_muter_le_document_rendu_ne_touche_pas_le_previz_gele():
    """Le document dit « gele » doit l'etre reellement.

    `dict(...)` ne recopiait que le premier niveau: muter un sous-dict du
    document rendu mutait l'`ExtractionPreviz`, deux appels ne rendaient plus
    le meme JSON, et `fingerprints.source_report` ne correspondait plus a son
    propre contenu -- la panne exacte que les empreintes existent pour
    empecher.
    """
    previz = _build()
    premier = previz_to_json_dict(previz)

    for valeur in premier["source_report"].values():
        if isinstance(valeur, dict):
            valeur["intrus"] = "mutation"
            break
        if isinstance(valeur, list):
            valeur.append("mutation")
            break
    else:
        pytest.skip("le rapport source ne porte aucune structure imbriquee")

    second = previz_to_json_dict(previz)

    assert second != premier
    assert canonical_json(second["source_report"]) == canonical_json(
        source_report_to_json_dict(_report())
    )
    assert fingerprint_of(second["source_report"]) == second["fingerprints"][
        "source_report"
    ]


def test_deux_serialisations_successives_sont_identiques():
    """AC 4, vu depuis la sortie: la serialisation n'a aucun effet de bord."""
    previz = _build()

    assert canonical_json(previz_to_json_dict(previz)) == canonical_json(
        previz_to_json_dict(previz)
    )


@pytest.mark.parametrize("valeur", [float("nan"), float("inf"), float("-inf")])
def test_canonical_json_refuse_les_flottants_non_finis(valeur):
    """`NaN` et `Infinity` ne sont pas du JSON: aucun parseur strict ne les lit.

    Les emettre produirait un document illisible chez son destinataire, et une
    empreinte scellant une chaine invalide.
    """
    with pytest.raises(ValueError):
        canonical_json({"champ": valeur})


@pytest.mark.parametrize(
    "horodatage",
    [
        "2026-08-04T09:30:00Z\n",
        "2026-08-04T09:30:00Z ",
        "\n2026-08-04T09:30:00Z",
    ],
)
def test_un_horodatage_avec_du_bruit_est_refuse(horodatage):
    """`$` acceptait encore un saut de ligne final, qui entrait dans le document."""
    with pytest.raises(ExtractionPrevizError, match="generated_at_utc"):
        _build(generated_at_utc=horodatage)


@pytest.mark.parametrize(
    "horodatage",
    [
        "2026-02-30T09:30:00Z",  # le 30 fevrier n'existe pas
        "2026-13-01T09:30:00Z",  # mois 13
        "2026-08-04T25:00:00Z",  # heure 25
        "2026-08-04T09:61:00Z",  # minute 61
    ],
)
def test_un_horodatage_qui_ne_designe_aucun_instant_est_refuse(horodatage):
    """Le motif ne contraignait que la forme, pas l'existence de la date."""
    with pytest.raises(ExtractionPrevizError, match="aucun instant reel"):
        _build(generated_at_utc=horodatage)


def test_un_horodatage_avec_fraction_de_seconde_reste_accepte():
    previz = _build(generated_at_utc="2026-08-04T09:30:00.123456Z")

    assert previz.generated_at_utc == "2026-08-04T09:30:00.123456Z"


# --------------------------------------------------------------------------
# Revue 3.7 -- l'empreinte de selection doit distinguer deux extraits
# --------------------------------------------------------------------------


#: Empreinte d'une selection **non bornee**, mesuree avant que les bornes
#: n'entrent dans le calcul. Elle est figee ici et non recalculee: c'est le
#: seul moyen de prouver qu'etendre le contrat n'a pas deplace l'empreinte des
#: lots d'avant. Un test qui recalculerait la valeur attendue passerait quelle
#: que soit la formule.
EMPREINTE_NON_BORNEE_AVANT_3_7 = (
    "sha256-v1:b4d82806c6902bcc0153cda1c93ab06bf6c599ed4cdeb343fbb54286c6148a60"
)


def _selection_25_vers_5(**bornes):
    return select_source_frames(
        fps_source=25, fps_target=5, source_frame_count=1000, **bornes
    )


def _empreinte(selection):
    from mixed_media_utility.extraction_previz import _selection_fingerprint_payload

    return fingerprint_of(
        _selection_fingerprint_payload(
            selection, fps_source_exact="25/1", fps_target_exact="5/1"
        )
    )


def test_deux_extraits_distincts_n_ont_pas_la_meme_empreinte_de_selection():
    """Revue du 2026-08-06: trois selections disjointes, une seule empreinte.

    L'empreinte repond a la question « ce que je montre est-il encore ce qui
    sera produit ». Avant ce correctif elle repondait oui a tort: les bornes
    decident quelles images sortent, et elles n'entraient pas dans le calcul.
    """
    a = _selection_25_vers_5(
        source_in_timecode="00:00:01:00", source_out_timecode="00:00:10:24"
    )
    b = _selection_25_vers_5(
        source_in_timecode="00:00:20:00", source_out_timecode="00:00:29:24"
    )
    entier = _selection_25_vers_5()

    assert [f.source_index for f in a.frames] != [f.source_index for f in b.frames]
    assert len({_empreinte(a), _empreinte(b), _empreinte(entier)}) == 3


def test_une_seule_borne_deplacee_deplace_l_empreinte():
    a = _selection_25_vers_5(source_out_timecode="00:00:10:24")
    b = _selection_25_vers_5(source_out_timecode="00:00:10:23")
    assert _empreinte(a) != _empreinte(b)


def test_in_seul_et_out_seul_ne_condensent_pas_pareil():
    """Deux extraits opposes ne doivent pas se confondre par omission."""
    depuis = _selection_25_vers_5(source_in_timecode="00:00:10:00")
    jusqu_a = _selection_25_vers_5(source_out_timecode="00:00:10:00")
    assert _empreinte(depuis) != _empreinte(jusqu_a)


def test_l_empreinte_d_un_lot_non_borne_est_celle_d_avant_la_story_3_7():
    """AC 14: etendre le contrat ne doit pas deplacer les lots d'avant.

    Les deux champs sont **omis** quand absents, jamais ecrits a `null`: c'est
    la regle cardinale du projet, et c'est aussi ce qui garde cette empreinte
    identique au bit pres a celle d'avant l'extension.
    """
    assert _empreinte(_selection_25_vers_5()) == EMPREINTE_NON_BORNEE_AVANT_3_7


def test_le_payload_non_borne_ne_porte_aucune_cle_de_borne():
    from mixed_media_utility.extraction_previz import _selection_fingerprint_payload

    payload = _selection_fingerprint_payload(
        _selection_25_vers_5(), fps_source_exact="25/1", fps_target_exact="5/1"
    )
    assert "source_in_timecode" not in payload
    assert "source_out_timecode" not in payload


def test_une_selection_sans_attribut_de_borne_reste_condensable():
    """Le Protocol reste tolerant: un objet d'avant la 3.7 passe encore.

    `FrameSelectionLike` est structurel. Exiger les deux attributs romprait
    tout appelant anterieur sans qu'aucun typage ne le signale.
    """
    from mixed_media_utility.extraction_previz import _selection_fingerprint_payload

    payload = _selection_fingerprint_payload(
        _sentinel_selection(), fps_source_exact="7/3", fps_target_exact="101/7"
    )
    assert "source_in_timecode" not in payload
