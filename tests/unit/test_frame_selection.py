"""Tests unitaires de la selection deterministe des frames (story 3.2).

Aucun `skipif` sur ffmpeg: le module teste est pur, ces tests doivent
tourner partout, c'est tout l'interet de sa purete (AC 1, AC 14).
"""

from __future__ import annotations

import ast
import sys
from collections.abc import Sequence
from fractions import Fraction
from math import ceil, floor
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import frame_selection
from mixed_media_utility.codec_profiles import NTSC_RATES, validate_timecode
from mixed_media_utility.frame_selection import (
    MAX_EXPECTED_FRAME_COUNT,
    MAX_SOURCE_FRAME_RATE,
    ROUNDING_POLICY_ID,
    TIMECODE_BASE,
    WARNING_CODES,
    EmptySourceError,
    FrameSelection,
    FrameSelectionError,
    InconsistentSourceDurationError,
    InvalidBoundsError,
    InvalidFrameRateError,
    InvalidStartTimecodeError,
    SelectedFrame,
    SelectionTooLargeError,
    UpsamplingNotSupportedError,
    select_source_frames,
)

MODULE_PATH = REPO_ROOT / "src" / "mixed_media_utility" / "frame_selection.py"


# --------------------------------------------------------------------------
# Vecteurs de reference figes (Dev Notes de la story 3.2, verifies par calcul
# exact). Colonnes: fps_source, fps_target, frames source, N attendu,
# premiers indices, dernier indice, ecarts observes, tail, warnings attendus.
# --------------------------------------------------------------------------

REFERENCE_VECTORS = [
    (25, 25, 10, 10, [0, 1, 2, 3, 4], 9, {1}, 0, ()),
    (25, 5, 100, 20, [0, 5, 10, 15, 20], 95, {5}, 4, ()),
    (30, 4, 100, 14, [0, 7, 15, 22, 30, 37, 45], 97, {7, 8}, 2,
     ("NON_DIVISIBLE_RATES",)),
    (24, 10, 24, 10, [0, 2, 4, 7, 9, 12, 14, 16, 19, 21], 21, {2, 3}, 2,
     ("NON_DIVISIBLE_RATES",)),
    (24, 10, 25, 11, [0, 2, 4, 7, 9, 12, 14, 16, 19, 21, 24], 24, {2, 3}, 0,
     ("NON_DIVISIBLE_RATES",)),
    (25, 12.5, 50, 25, [0, 2, 4, 6, 8], 48, {2}, 1,
     ("NON_INTEGER_TARGET_RATE",)),
    (30, 12, 100, 40, [0, 2, 5, 7, 10, 12, 15, 17], 97, {2, 3}, 2,
     ("NON_DIVISIBLE_RATES",)),
    (12.5, 5, 50, 20, [0, 2, 5, 7, 10, 12, 15, 17, 20, 22], 47, {2, 3}, 2,
     ("NON_INTEGER_SOURCE_RATE", "NON_DIVISIBLE_RATES")),
    (30, 1, 100, 4, [0, 30, 60, 90], 90, {30}, 9, ()),
    (25, 5, 3, 1, [0], 0, set(), 2, ()),
    (25, 5, 1, 1, [0], 0, set(), 0, ()),
    ("24000/1001", "24000/1001", 5, 5, [0, 1, 2, 3, 4], 4, {1}, 0,
     ("NTSC_RATE_OUT_OF_SCOPE", "NON_INTEGER_SOURCE_RATE",
      "NON_INTEGER_TARGET_RATE")),
]

VECTOR_IDS = [
    f"{vector[0]}->{vector[1]}@{vector[2]}" for vector in REFERENCE_VECTORS
]


def _indices(selection: FrameSelection) -> list[int]:
    return [frame.source_index for frame in selection]


def _gaps(indices: list[int]) -> set[int]:
    return {indices[i + 1] - indices[i] for i in range(len(indices) - 1)}


@pytest.mark.parametrize(
    "fps_source,fps_target,frame_count,expected_n,first_indices,last_index,"
    "gaps,tail,warnings",
    REFERENCE_VECTORS,
    ids=VECTOR_IDS,
)
def test_reference_vectors(
    fps_source,
    fps_target,
    frame_count,
    expected_n,
    first_indices,
    last_index,
    gaps,
    tail,
    warnings,
):
    selection = select_source_frames(
        fps_source=fps_source,
        fps_target=fps_target,
        source_frame_count=frame_count,
    )
    indices = _indices(selection)

    assert selection.expected_frame_count == expected_n
    assert len(selection) == expected_n
    assert indices[: len(first_indices)] == first_indices
    assert indices[-1] == last_index
    assert _gaps(indices) == gaps
    assert selection.source_tail_frames == tail
    assert selection.warnings == warnings


@pytest.mark.parametrize(
    "fps_source,fps_target,frame_count,expected_n,first_indices,last_index,"
    "gaps,tail,warnings",
    REFERENCE_VECTORS,
    ids=VECTOR_IDS,
)
def test_reference_vectors_tail_formula(
    fps_source,
    fps_target,
    frame_count,
    expected_n,
    first_indices,
    last_index,
    gaps,
    tail,
    warnings,
):
    """AC 5: `source_tail_frames == source_frame_count - 1 - dernier index`."""
    selection = select_source_frames(
        fps_source=fps_source,
        fps_target=fps_target,
        source_frame_count=frame_count,
    )
    assert selection.source_tail_frames == frame_count - 1 - _indices(selection)[-1]


# --------------------------------------------------------------------------
# Proprietes (AC 3, AC 4) balayees sur tous les couples de cadences du tableau
# --------------------------------------------------------------------------

RATE_POOL = [
    1,
    4,
    5,
    10,
    12,
    Fraction(25, 2),
    24,
    25,
    30,
    Fraction(24000, 1001),
]

RATE_COUPLES = [
    (source, target)
    for source in RATE_POOL
    for target in RATE_POOL
    if Fraction(target) <= Fraction(source)
]

FRAME_COUNTS = [1, 2, 3, 7, 24, 25, 50, 100, 101]


@pytest.mark.parametrize("fps_source,fps_target", RATE_COUPLES)
@pytest.mark.parametrize("frame_count", FRAME_COUNTS)
def test_properties_over_every_rate_couple(fps_source, fps_target, frame_count):
    selection = select_source_frames(
        fps_source=fps_source,
        fps_target=fps_target,
        source_frame_count=frame_count,
    )
    indices = _indices(selection)
    step = Fraction(fps_source) / Fraction(fps_target)

    # N >= 1 des que source_frame_count >= 1, et N == len(frames)
    assert selection.expected_frame_count >= 1
    assert selection.expected_frame_count == len(indices)
    # N est exactement ceil(source_frame_count * fps_target / fps_source)
    assert selection.expected_frame_count == ceil(Fraction(frame_count) / step)

    # Strictement croissant, donc sans doublon
    assert all(b > a for a, b in zip(indices, indices[1:]))
    assert len(set(indices)) == len(indices)

    # Entierement contenu dans [0, source_frame_count - 1]
    assert indices[0] == 0
    assert indices[-1] <= frame_count - 1

    # Jitter borne a une frame: chaque ecart vaut floor(k) ou ceil(k)
    assert _gaps(indices) <= {floor(step), ceil(step)}

    # output_rank dense, base zero, dans l'ordre canonique
    assert [frame.output_rank for frame in selection] == list(range(len(indices)))

    # La formule generale, pas une reimplementation
    assert indices == [floor(step * n) for n in range(len(indices))]


@pytest.mark.parametrize(
    "fps_source,fps_target,frame_count,expected_n",
    [
        (25, 25, 10, 10),
        (25, 5, 100, 20),
        (30, 4, 100, 14),
        (24, 10, 24, 10),
        (30, 12, 100, 40),
        (25, Fraction(25, 2), 50, 25),
        (25, 5, 3, 1),
        (25, 5, 1, 1),
    ],
)
def test_rounding_policy_cardinal(fps_source, fps_target, frame_count, expected_n):
    """AC 3: cardinal = ceil(source_frame_count * fps_target / fps_source)."""
    selection = select_source_frames(
        fps_source=fps_source,
        fps_target=fps_target,
        source_frame_count=frame_count,
    )
    assert selection.expected_frame_count == expected_n
    assert selection.expected_frame_count >= 1


def test_identity_when_rates_are_equal():
    """AC 6: cible == source -> identite exacte, par la formule generale."""
    selection = select_source_frames(
        fps_source=25, fps_target=25, source_frame_count=10
    )
    assert _indices(selection) == list(range(10))
    assert selection.source_tail_frames == 0
    assert selection.expected_frame_count == 10


def test_rounding_policy_id_is_locked():
    """AC 2: changer la politique doit casser ce test, jamais passer en silence."""
    assert ROUNDING_POLICY_ID == "floor-index-ceil-count-v1"
    selection = select_source_frames(
        fps_source=30, fps_target=4, source_frame_count=100
    )
    assert selection.rounding_policy == ROUNDING_POLICY_ID
    # Verrou de comportement: la politique nommee est celle reellement appliquee.
    assert _indices(selection) == [
        0, 7, 15, 22, 30, 37, 45, 52, 60, 67, 75, 82, 90, 97
    ]


# --------------------------------------------------------------------------
# Erreurs (AC 6, 10, 13)
# --------------------------------------------------------------------------


def test_upsampling_is_rejected():
    with pytest.raises(UpsamplingNotSupportedError) as excinfo:
        select_source_frames(fps_source=24, fps_target=25, source_frame_count=10)
    message = str(excinfo.value)
    assert isinstance(excinfo.value, FrameSelectionError)
    # Message actionnable: il porte la cadence maximale admissible.
    assert "24" in message
    assert "maximale admissible" in message


def test_upsampling_detected_on_exact_ntsc_rate():
    """23.976 est strictement inferieure a 24: la garde doit le voir exactement."""
    with pytest.raises(UpsamplingNotSupportedError):
        select_source_frames(
            fps_source="24000/1001", fps_target=24, source_frame_count=10
        )


@pytest.mark.parametrize("frame_count", [0, -1, -100])
def test_empty_source_is_rejected(frame_count):
    with pytest.raises(EmptySourceError):
        select_source_frames(
            fps_source=25, fps_target=5, source_frame_count=frame_count
        )


@pytest.mark.parametrize("frame_count", [1.0, 10.5, "10", None, True, Fraction(10, 1)])
def test_non_integer_frame_count_is_rejected(frame_count):
    with pytest.raises(EmptySourceError):
        select_source_frames(
            fps_source=25, fps_target=5, source_frame_count=frame_count
        )


@pytest.mark.parametrize(
    "fps", [0, -25, float("nan"), float("inf"), float("-inf"), "abc", None, object()]
)
def test_invalid_source_rate_is_wrapped(fps):
    with pytest.raises(InvalidFrameRateError) as excinfo:
        select_source_frames(fps_source=fps, fps_target=1, source_frame_count=10)
    assert isinstance(excinfo.value, FrameSelectionError)
    assert excinfo.value.__cause__ is not None


@pytest.mark.parametrize("fps", [0, -5, float("nan"), float("inf"), "abc", None])
def test_invalid_target_rate_is_wrapped(fps):
    with pytest.raises(InvalidFrameRateError) as excinfo:
        select_source_frames(fps_source=25, fps_target=fps, source_frame_count=10)
    assert excinfo.value.__cause__ is not None


def test_consistent_duration_is_accepted():
    # 100 frames a 25 fps == 4.0 s exactement.
    selection = select_source_frames(
        fps_source=25,
        fps_target=5,
        source_frame_count=100,
        source_duration_seconds=4.0,
    )
    assert selection.expected_frame_count == 20


@pytest.mark.parametrize("duration", [4.02, 3.98, Fraction(101, 25), Fraction(99, 25)])
def test_duration_within_one_frame_is_accepted(duration):
    """Tolerance d'une frame exactement: 1/25 s = 0.04 s, bornes incluses."""
    selection = select_source_frames(
        fps_source=25,
        fps_target=5,
        source_frame_count=100,
        source_duration_seconds=duration,
    )
    assert selection.expected_frame_count == 20


@pytest.mark.parametrize("duration", [5.0, 3.0, 4.2])
def test_inconsistent_duration_is_rejected(duration):
    with pytest.raises(InconsistentSourceDurationError):
        select_source_frames(
            fps_source=25,
            fps_target=5,
            source_frame_count=100,
            source_duration_seconds=duration,
        )


@pytest.mark.parametrize("duration", [0, -1.0, float("nan"), float("inf"), "4.0", []])
def test_unusable_duration_is_rejected(duration):
    with pytest.raises(InconsistentSourceDurationError):
        select_source_frames(
            fps_source=25,
            fps_target=5,
            source_frame_count=100,
            source_duration_seconds=duration,
        )


@pytest.mark.parametrize(
    "timecode",
    ["01:00:00;00", "00:00:00;12"],
)
def test_drop_frame_start_timecode_is_rejected(timecode):
    with pytest.raises(InvalidStartTimecodeError) as excinfo:
        select_source_frames(
            fps_source=30,
            fps_target=5,
            source_frame_count=100,
            source_start_timecode=timecode,
        )
    assert "drop-frame" in str(excinfo.value)


def test_drop_frame_start_timecode_rejected_even_on_ntsc_rate():
    """`validate_timecode` tolere `;` en NTSC: ce noyau le refuse quand meme."""
    with pytest.raises(InvalidStartTimecodeError):
        select_source_frames(
            fps_source="30000/1001",
            fps_target="30000/1001",
            source_frame_count=5,
            source_start_timecode="01:00:00;00",
        )


@pytest.mark.parametrize(
    "timecode",
    ["", "abc", "1:00:00:00", "01:00:00", "24:00:00:00", "00:60:00:00",
     "00:00:60:00", "00:00:00:30", "00-00-00-00", 42],
)
def test_malformed_start_timecode_is_rejected(timecode):
    with pytest.raises(InvalidStartTimecodeError):
        select_source_frames(
            fps_source=30,
            fps_target=5,
            source_frame_count=100,
            source_start_timecode=timecode,
        )


@pytest.mark.parametrize("fps", ["0/0", "1/0", "25/0"])
def test_degenerate_rational_rate_is_wrapped(fps):
    """ffprobe emet litteralement `r_frame_rate = "0/0"` sur un flux sans cadence.

    Cette valeur remontait en `ZeroDivisionError` nue, hors de la hierarchie du
    module, alors que c'est exactement ce que la story 3.1 lui transmet.
    """
    with pytest.raises(InvalidFrameRateError) as excinfo:
        select_source_frames(fps_source=fps, fps_target=1, source_frame_count=10)
    assert isinstance(excinfo.value, FrameSelectionError)
    assert excinfo.value.__cause__ is not None

    with pytest.raises(InvalidFrameRateError):
        select_source_frames(fps_source=25, fps_target=fps, source_frame_count=10)


@pytest.mark.parametrize("fps_source", [61, 100, 120, 240, "120000/1001", 119.88])
def test_source_rate_above_the_product_cap_is_rejected(fps_source):
    """ARB-11: la cadence source est plafonnee a 60 i/s pour le MVP.

    La limite technique dure reste 100 -- au-dela, `ff` deborde les deux
    chiffres de hh:mm:ss:ff -- mais Egan a tranche le 2026-08-05 une limite
    produit plus basse: les rushs a haute cadence (ralentis) sont hors
    perimetre.
    """
    with pytest.raises(InvalidFrameRateError) as excinfo:
        select_source_frames(
            fps_source=fps_source, fps_target=1, source_frame_count=1200
        )
    assert isinstance(excinfo.value, FrameSelectionError)
    assert str(MAX_SOURCE_FRAME_RATE) in str(excinfo.value)


@pytest.mark.parametrize("fps_source", [25, 30, 48, 50, "60000/1001", 60])
def test_source_rate_up_to_the_product_cap_is_accepted(fps_source):
    """Borne incluse: 50p, 59.94p et 60p restent des cas nominaux.

    Le 59.94p (`60000/1001`) est une cadence de diffusion courante qu'Egan a
    explicitement demande de conserver: c'est ce qui a fait relever le plafond
    de 50 a 60, `ceil(60000/1001)` valant 60.
    """
    selection = select_source_frames(
        fps_source=fps_source, fps_target=fps_source, source_frame_count=150
    )
    for frame in selection:
        assert validate_timecode(
            frame.frame_timecode, selection.timecode_base_fps
        ) == frame.frame_timecode


@pytest.mark.parametrize("flag", [0, 1, None, "", "false", "no", [], Fraction(1)])
def test_non_boolean_exactness_flag_is_rejected(flag):
    """La table normative conditionne le code a `is False`, jamais a une coercition.

    Sens dangereux: `"false"` est une chaine non vide, donc vraie, et un cardinal
    estime serait rediffuse comme exact sans qu'aucun code ne le signale.
    """
    with pytest.raises(EmptySourceError):
        select_source_frames(
            fps_source=25,
            fps_target=5,
            source_frame_count=10,
            source_frame_count_is_exact=flag,
        )


@pytest.mark.parametrize("flag,expected", [(True, ()), (False, ("SOURCE_FRAME_COUNT_ESTIMATED",))])
def test_boolean_exactness_flag_matches_normative_table(flag, expected):
    selection = select_source_frames(
        fps_source=25,
        fps_target=5,
        source_frame_count=10,
        source_frame_count_is_exact=flag,
    )
    assert selection.warnings == expected
    assert selection.source_frame_count_is_exact is flag


def test_every_error_derives_from_frame_selection_error():
    for error_class in (
        InvalidFrameRateError,
        UpsamplingNotSupportedError,
        EmptySourceError,
        InconsistentSourceDurationError,
        InvalidStartTimecodeError,
    ):
        assert issubclass(error_class, FrameSelectionError)
    assert issubclass(FrameSelectionError, ValueError)


# --------------------------------------------------------------------------
# Timecodes (AC 8, AC 9)
# --------------------------------------------------------------------------


def test_timecode_of_index_97_at_30_fps():
    """97 // 30 = 3 s, 97 - 90 = 7 -> 00:00:03:07."""
    selection = select_source_frames(
        fps_source=30, fps_target=4, source_frame_count=100
    )
    last = selection[-1]
    assert last.source_index == 97
    assert last.frame_timecode == "00:00:03:07"


def test_timecode_of_index_97_with_one_hour_offset():
    """3600 * 30 = 108000, +97 = 108097, // 30 = 3603 s, reste 7 -> 01:00:03:07."""
    selection = select_source_frames(
        fps_source=30,
        fps_target=4,
        source_frame_count=100,
        source_start_timecode="01:00:00:00",
    )
    assert selection[-1].source_index == 97
    assert selection[-1].frame_timecode == "01:00:03:07"
    assert selection[0].frame_timecode == "01:00:00:00"


def test_timecode_wraps_at_24_hours():
    """Offset 23:59:59:29 a 30 fps, indice source 1 -> 00:00:00:00."""
    selection = select_source_frames(
        fps_source=30,
        fps_target=30,
        source_frame_count=3,
        source_start_timecode="23:59:59:29",
    )
    assert selection[0].frame_timecode == "23:59:59:29"
    assert selection[1].frame_timecode == "00:00:00:00"
    assert selection[2].frame_timecode == "00:00:00:01"


def test_every_emitted_timecode_validates_against_source_rate():
    for fps_source, fps_target, frame_count, *_ in REFERENCE_VECTORS:
        selection = select_source_frames(
            fps_source=fps_source,
            fps_target=fps_target,
            source_frame_count=frame_count,
            source_start_timecode="23:59:00:00",
        )
        for frame in selection:
            assert ";" not in frame.frame_timecode
            assert validate_timecode(
                frame.frame_timecode, selection.timecode_base_fps
            ) == frame.frame_timecode


def test_ff_field_is_counted_on_ceil_of_source_rate():
    """AC 8/9: la base du champ `ff` est ceil(fps_source), pas fps_source."""
    selection = select_source_frames(
        fps_source="24000/1001", fps_target="24000/1001", source_frame_count=48
    )
    # 24 frames a 23.976 -> le champ ff reboucle sur 24, pas sur 23.
    assert selection[23].frame_timecode == "00:00:00:23"
    assert selection[24].frame_timecode == "00:00:01:00"
    assert selection.timecode_base_fps == Fraction(24000, 1001)


def test_validating_against_target_rate_would_reject():
    """Piege 4: valider un timecode base source contre fps_target le rejette."""
    selection = select_source_frames(
        fps_source=30, fps_target=4, source_frame_count=100
    )
    assert selection[-1].frame_timecode == "00:00:03:07"
    with pytest.raises(ValueError):
        validate_timecode(selection[-1].frame_timecode, selection.fps_target)


def test_timecodes_are_strictly_increasing_without_wrap():
    selection = select_source_frames(
        fps_source=30, fps_target=4, source_frame_count=100
    )
    timecodes = [frame.frame_timecode for frame in selection]
    assert timecodes == sorted(timecodes)
    assert len(set(timecodes)) == len(timecodes)


# --------------------------------------------------------------------------
# Avertissements (AC 11)
# --------------------------------------------------------------------------


def test_warning_codes_canonical_order():
    assert WARNING_CODES == (
        "NTSC_RATE_OUT_OF_SCOPE",
        "NON_INTEGER_SOURCE_RATE",
        "NON_INTEGER_TARGET_RATE",
        "NON_DIVISIBLE_RATES",
        "SOURCE_FRAME_COUNT_ESTIMATED",
    )
    assert all(code.isascii() and code.isupper() for code in WARNING_CODES)


def test_warnings_are_ordered_and_deduplicated():
    selection = select_source_frames(
        fps_source="30000/1001",
        fps_target=Fraction(20000, 1001),
        source_frame_count=100,
        source_frame_count_is_exact=False,
    )
    assert selection.warnings == WARNING_CODES
    assert len(set(selection.warnings)) == len(selection.warnings)
    order = [WARNING_CODES.index(code) for code in selection.warnings]
    assert order == sorted(order)


def test_ntsc_identity_emits_three_codes_but_not_non_divisible():
    selection = select_source_frames(
        fps_source="24000/1001", fps_target="24000/1001", source_frame_count=5
    )
    assert selection.warnings == (
        "NTSC_RATE_OUT_OF_SCOPE",
        "NON_INTEGER_SOURCE_RATE",
        "NON_INTEGER_TARGET_RATE",
    )
    assert selection.fps_source in NTSC_RATES


def test_non_integer_target_rate_alone():
    selection = select_source_frames(
        fps_source=25, fps_target=12.5, source_frame_count=50
    )
    assert selection.warnings == ("NON_INTEGER_TARGET_RATE",)


def test_non_integer_source_rate_dissociated_from_target():
    """Seul vecteur qui dissocie les deux codes de cadence non entiere."""
    selection = select_source_frames(
        fps_source=12.5, fps_target=5, source_frame_count=50
    )
    assert selection.warnings == ("NON_INTEGER_SOURCE_RATE", "NON_DIVISIBLE_RATES")
    assert "NON_INTEGER_TARGET_RATE" not in selection.warnings


@pytest.mark.parametrize(
    "fps_source,fps_target", [(30, 4), (24, 10), (30, 12)]
)
def test_non_divisible_rates_alone(fps_source, fps_target):
    selection = select_source_frames(
        fps_source=fps_source, fps_target=fps_target, source_frame_count=100
    )
    assert selection.warnings == ("NON_DIVISIBLE_RATES",)


@pytest.mark.parametrize("fps_source,fps_target", [(25, 25), (25, 5), (30, 1)])
def test_no_warning_on_integer_divisible_rates(fps_source, fps_target):
    selection = select_source_frames(
        fps_source=fps_source, fps_target=fps_target, source_frame_count=100
    )
    assert selection.warnings == ()


def test_estimated_frame_count_emits_its_code_and_is_redistributed():
    selection = select_source_frames(
        fps_source=25,
        fps_target=5,
        source_frame_count=100,
        source_frame_count_is_exact=False,
    )
    assert selection.warnings == ("SOURCE_FRAME_COUNT_ESTIMATED",)
    assert selection.source_frame_count_is_exact is False


def test_ntsc_detection_uses_codec_profiles_constant():
    for rate in NTSC_RATES:
        if ceil(rate) > MAX_SOURCE_FRAME_RATE:
            # Au-dela du plafond produit (ARB-11), la cadence est refusee en
            # amont et n'atteint jamais la table des codes.
            with pytest.raises(InvalidFrameRateError):
                select_source_frames(
                    fps_source=rate, fps_target=rate, source_frame_count=3
                )
            continue
        selection = select_source_frames(
            fps_source=rate, fps_target=rate, source_frame_count=3
        )
        assert "NTSC_RATE_OUT_OF_SCOPE" in selection.warnings


# --------------------------------------------------------------------------
# Determinisme (AC 7)
# --------------------------------------------------------------------------


def test_three_ntsc_rate_forms_converge():
    """Aucun float n'a arbitre: les trois formes donnent la MEME selection."""
    from_float = select_source_frames(
        fps_source=23.976, fps_target=23.976, source_frame_count=200
    )
    from_string = select_source_frames(
        fps_source="24000/1001", fps_target="24000/1001", source_frame_count=200
    )
    from_fraction = select_source_frames(
        fps_source=Fraction(24000, 1001),
        fps_target=Fraction(24000, 1001),
        source_frame_count=200,
    )
    assert from_float == from_string == from_fraction
    assert from_float.fps_source == Fraction(24000, 1001)
    # Le recalage NTSC n'est pas une coincidence de flottant.
    assert from_float.fps_source != Fraction(2997, 125)


def test_repeated_calls_produce_equal_objects():
    kwargs = dict(
        fps_source=30,
        fps_target=4,
        source_frame_count=100,
        source_start_timecode="01:00:00:00",
        source_duration_seconds=10.0 / 3.0,
        source_frame_count_is_exact=False,
    )
    first = select_source_frames(**kwargs)
    second = select_source_frames(**kwargs)
    assert first == second
    assert first.frames == second.frames
    assert hash(first.frames) == hash(second.frames)


def test_mixed_rate_forms_produce_equal_selections():
    a = select_source_frames(fps_source=30, fps_target=4, source_frame_count=100)
    b = select_source_frames(
        fps_source="30/1", fps_target=Fraction(4), source_frame_count=100
    )
    c = select_source_frames(
        fps_source=30.0, fps_target=4.0, source_frame_count=100
    )
    assert a == b == c


# --------------------------------------------------------------------------
# Structure de sortie (AC 12)
# --------------------------------------------------------------------------


def test_selection_satisfies_sequence_protocol():
    selection = select_source_frames(
        fps_source=30, fps_target=4, source_frame_count=100
    )
    assert isinstance(selection, Sequence)
    assert len(selection) == 14
    assert selection[0] == SelectedFrame(0, 0, "00:00:00:00")
    assert selection[-1].source_index == 97
    assert [frame.output_rank for frame in selection] == list(range(14))
    assert list(selection) == list(selection.frames)
    assert selection[1:3] == selection.frames[1:3]


def test_dataclasses_are_frozen():
    selection = select_source_frames(
        fps_source=25, fps_target=5, source_frame_count=10
    )
    with pytest.raises(Exception):
        selection.expected_frame_count = 99
    with pytest.raises(Exception):
        selection.frames[0].source_index = 99


def test_output_contract_fields():
    selection = select_source_frames(
        fps_source=30,
        fps_target=12,
        source_frame_count=100,
        source_start_timecode="10:00:00:00",
        source_frame_count_is_exact=False,
    )
    assert selection.fps_source == Fraction(30)
    assert selection.fps_target == Fraction(12)
    assert selection.source_frame_count == 100
    assert selection.source_frame_count_is_exact is False
    assert selection.expected_frame_count == len(selection.frames)
    assert selection.source_tail_frames == 2
    assert selection.rounding_policy == ROUNDING_POLICY_ID
    assert selection.timecode_base == TIMECODE_BASE == "source"
    assert selection.timecode_base_fps == selection.fps_source
    assert isinstance(selection.timecode_base_fps, Fraction)
    assert selection.source_start_timecode == "10:00:00:00"
    assert isinstance(selection.warnings, tuple)


def test_start_timecode_is_redistributed_verbatim_when_absent():
    selection = select_source_frames(
        fps_source=25, fps_target=5, source_frame_count=10
    )
    assert selection.source_start_timecode is None
    assert selection.source_frame_count_is_exact is True


# --------------------------------------------------------------------------
# Purete du module (AC 1) — analyse AST, pas seulement les imports
# --------------------------------------------------------------------------

ALLOWED_ABSOLUTE_IMPORTS = {
    "__future__",
    "collections.abc",
    "dataclasses",
    "fractions",
    "math",
    "typing",
}
ALLOWED_RELATIVE_IMPORTS = {"codec_profiles", "numeric_guards"}
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


def test_module_has_no_forbidden_name_reference():
    forbidden_modules = {
        "subprocess",
        "cv2",
        "pathlib",
        "argparse",
        "os",
        "sys",
        "json",
        "shutil",
        "numpy",
        "jsonschema",
        "requests",
    }
    referenced = set()
    for node in ast.walk(_module_tree()):
        if isinstance(node, ast.Import):
            referenced.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level:
            referenced.add((node.module or "").split(".")[0])
    assert referenced & forbidden_modules == set()


def test_module_is_importable_without_external_binary():
    """Le module ne doit dependre d'aucun binaire externe pour s'importer."""
    assert frame_selection.TIMECODE_BASE == "source"
    assert callable(frame_selection.select_source_frames)


# --------------------------------------------------------------------------
# ARB-10: plafond en nombre d'images, pas en duree
# --------------------------------------------------------------------------


def test_un_lot_au_dessus_du_plafond_est_refuse():
    """Le plafond porte sur le nombre d'images extraites, pas sur la duree."""
    with pytest.raises(SelectionTooLargeError) as excinfo:
        select_source_frames(
            fps_source=25, fps_target=25, source_frame_count=MAX_EXPECTED_FRAME_COUNT + 1
        )

    message = str(excinfo.value)
    assert str(MAX_EXPECTED_FRAME_COUNT) in message
    assert "im/s" in message, "le message doit nommer la cadence qui ferait rentrer"
    assert isinstance(excinfo.value, FrameSelectionError)


def test_le_plafond_est_inclusif():
    selection = select_source_frames(
        fps_source=25, fps_target=25, source_frame_count=MAX_EXPECTED_FRAME_COUNT
    )

    assert selection.expected_frame_count == MAX_EXPECTED_FRAME_COUNT


def test_une_cadence_basse_fait_rentrer_un_rush_long():
    """La logique d'Egan: a 1 im/s on a plus de marge qu'a 25 im/s.

    Un rush de deux heures a 25 im/s (180 000 images source) depasse le plafond
    des 25 im/s, et rentre largement a 1 im/s.
    """
    with pytest.raises(SelectionTooLargeError):
        select_source_frames(fps_source=25, fps_target=25, source_frame_count=180_000)

    selection = select_source_frames(
        fps_source=25, fps_target=Fraction(1, 10), source_frame_count=180_000
    )

    assert selection.expected_frame_count == 720
    assert selection.expected_frame_count <= MAX_EXPECTED_FRAME_COUNT


def test_la_cadence_annoncee_par_le_message_fait_effectivement_rentrer():
    """Le message doit proposer une issue qui marche, pas une approximation."""
    with pytest.raises(SelectionTooLargeError) as excinfo:
        select_source_frames(fps_source=25, fps_target=25, source_frame_count=5000)

    import re

    cadence = float(re.search(r"au plus ([\d.]+) im/s", str(excinfo.value)).group(1))
    selection = select_source_frames(
        fps_source=25, fps_target=cadence, source_frame_count=5000
    )

    assert selection.expected_frame_count <= MAX_EXPECTED_FRAME_COUNT


# --------------------------------------------------------------------------
# Story 3.7: bornes de timecode d'entree et de sortie (AC 1 a 4, 11, 14)
# --------------------------------------------------------------------------


def test_les_bornes_derivent_de_frame_selection_error():
    assert issubclass(InvalidBoundsError, FrameSelectionError)
    assert issubclass(InvalidBoundsError, ValueError)
    assert "InvalidBoundsError" in frame_selection.__all__


def test_sans_borne_le_resultat_est_identique_a_aujourd_hui():
    """AC 14: le chemin non borne ne bouge pas, y compris passe explicitement."""
    reference = select_source_frames(
        fps_source=30, fps_target=4, source_frame_count=100
    )
    explicite = select_source_frames(
        fps_source=30,
        fps_target=4,
        source_frame_count=100,
        source_in_timecode=None,
        source_out_timecode=None,
    )

    assert explicite == reference
    assert reference.source_in_timecode is None
    assert reference.source_out_timecode is None
    # Vecteur de reference fige de la story 3.2, inchange.
    assert [frame.source_index for frame in reference][:7] == [0, 7, 15, 22, 30, 37, 45]
    assert reference.source_tail_frames == 2


def test_borne_d_entree_seule_borne_la_fin_au_dernier_index_du_rush():
    selection = select_source_frames(
        fps_source=25,
        fps_target=5,
        source_frame_count=100,
        source_in_timecode="00:00:02:00",
    )

    assert [frame.source_index for frame in selection] == [
        50, 55, 60, 65, 70, 75, 80, 85, 90, 95
    ]
    assert selection.expected_frame_count == 10
    # Piege 3: la formule de `source_tail_frames` ne change pas.
    assert selection.source_tail_frames == 100 - 1 - 95
    assert selection.source_in_timecode == "00:00:02:00"
    assert selection.source_out_timecode is None


def test_borne_de_sortie_seule_borne_le_debut_a_l_index_zero():
    selection = select_source_frames(
        fps_source=25,
        fps_target=5,
        source_frame_count=100,
        source_out_timecode="00:00:01:24",
    )

    assert [frame.source_index for frame in selection] == [
        0, 5, 10, 15, 20, 25, 30, 35, 40, 45
    ]
    assert selection.expected_frame_count == 10
    assert selection.source_tail_frames == 100 - 1 - 45
    assert selection.source_in_timecode is None
    assert selection.source_out_timecode == "00:00:01:24"


def test_les_deux_bornes_ensemble_definissent_la_fenetre():
    selection = select_source_frames(
        fps_source=25,
        fps_target=5,
        source_frame_count=100,
        source_in_timecode="00:00:02:00",
        source_out_timecode="00:00:02:24",
    )

    assert [frame.source_index for frame in selection] == [50, 55, 60, 65, 70]
    assert selection.expected_frame_count == 5
    assert selection.source_tail_frames == 100 - 1 - 70


def test_le_cardinal_de_la_fenetre_generalise_la_formule_actuelle():
    """`expected_frame_count = ceil((out - in + 1) / step)`, ceil compris."""
    selection = select_source_frames(
        fps_source=30,
        fps_target=4,
        source_frame_count=100,
        source_in_timecode="00:00:00:10",
        source_out_timecode="00:00:02:29",
    )

    step = Fraction(30, 4)
    in_index, out_index = 10, 89
    assert selection.expected_frame_count == ceil(Fraction(out_index - in_index + 1) / step)
    assert [frame.source_index for frame in selection] == [
        in_index + floor(step * rank) for rank in range(selection.expected_frame_count)
    ]


def test_la_borne_soustrait_l_offset_du_timecode_de_depart():
    """Piege 2: `--in 01:00:30:00` sur un rush a `01:00:00:00` borne a 30 s."""
    selection = select_source_frames(
        fps_source=25,
        fps_target=5,
        source_frame_count=1000,
        source_start_timecode="01:00:00:00",
        source_in_timecode="01:00:30:00",
    )

    assert selection.frames[0].source_index == 750
    assert selection.frames[0].frame_timecode == "01:00:30:00"


def test_une_borne_lue_a_l_ecran_reste_utilisable_apres_minuit():
    """AC 2: modulo un jour. Sans lui, l'indice serait negatif et refuse."""
    selection = select_source_frames(
        fps_source=25,
        fps_target=5,
        source_frame_count=20_000,
        source_start_timecode="23:50:00:00",
        source_in_timecode="00:02:00:00",
        source_out_timecode="00:02:10:00",
    )

    assert selection.frames[0].source_index == 18_000
    assert selection.frames[0].frame_timecode == "00:02:00:00"
    assert selection.frames[-1].source_index <= 18_250


def test_une_borne_de_sortie_hors_du_rush_est_refusee_en_nommant_le_timecode():
    with pytest.raises(InvalidBoundsError) as excinfo:
        select_source_frames(
            fps_source=25,
            fps_target=5,
            source_frame_count=100,
            source_out_timecode="00:00:10:00",
        )

    message = str(excinfo.value)
    assert "00:00:03:24" in message, "le dernier timecode valide doit etre nomme"
    assert "99" in message, "le dernier index valide doit etre nomme"


def test_une_borne_anterieure_au_debut_du_rush_rappelle_la_plage_couverte():
    """AC 3: pas d'indice negatif possible, donc pas de 'point anterieur'."""
    with pytest.raises(InvalidBoundsError) as excinfo:
        select_source_frames(
            fps_source=25,
            fps_target=5,
            source_frame_count=100,
            source_start_timecode="01:00:00:00",
            source_in_timecode="00:59:00:00",
        )

    message = str(excinfo.value)
    assert "01:00:00:00" in message
    assert "01:00:03:24" in message


def test_un_rush_sans_timecode_le_dit_dans_le_refus():
    with pytest.raises(InvalidBoundsError) as excinfo:
        select_source_frames(
            fps_source=25,
            fps_target=5,
            source_frame_count=100,
            source_out_timecode="00:00:10:00",
        )

    message = str(excinfo.value)
    assert "00:00:00:00" in message
    assert "timecode" in message


def test_une_borne_d_entree_posterieure_a_la_borne_de_sortie_est_refusee():
    with pytest.raises(InvalidBoundsError) as excinfo:
        select_source_frames(
            fps_source=25,
            fps_target=5,
            source_frame_count=100,
            source_in_timecode="00:00:03:00",
            source_out_timecode="00:00:01:00",
        )

    assert "00:00:03:00" in str(excinfo.value)
    assert "00:00:01:00" in str(excinfo.value)


@pytest.mark.parametrize("champ", ["source_in_timecode", "source_out_timecode"])
@pytest.mark.parametrize(
    "timecode",
    ["", "abc", "1:00:00:00", "01:00:00", "24:00:00:00", "00:60:00:00",
     "00:00:60:00", "00:00:00:30", "00-00-00-00", 42],
)
def test_une_borne_malformee_est_refusee_en_invalid_bounds(champ, timecode):
    with pytest.raises(InvalidBoundsError) as excinfo:
        select_source_frames(
            fps_source=25,
            fps_target=5,
            source_frame_count=100,
            **{champ: timecode},
        )

    assert not isinstance(excinfo.value, InvalidStartTimecodeError)
    assert champ in str(excinfo.value)


@pytest.mark.parametrize("champ", ["source_in_timecode", "source_out_timecode"])
@pytest.mark.parametrize("timecode", ["01:00:00;00", "00:00:00;12"])
def test_une_borne_drop_frame_est_refusee_en_invalid_bounds(champ, timecode):
    """ARB-19: le drop-frame se refuse, il ne se supporte pas."""
    with pytest.raises(InvalidBoundsError) as excinfo:
        select_source_frames(
            fps_source=25,
            fps_target=5,
            source_frame_count=100,
            **{champ: timecode},
        )

    assert not isinstance(excinfo.value, InvalidStartTimecodeError)
    assert "drop-frame" in str(excinfo.value)


def test_un_extrait_court_fait_rentrer_un_rush_long_a_cadence_elevee():
    """La raison d'etre de la story (ARB-10): borner plutot que ralentir."""
    with pytest.raises(SelectionTooLargeError):
        select_source_frames(fps_source=25, fps_target=25, source_frame_count=180_000)

    selection = select_source_frames(
        fps_source=25,
        fps_target=25,
        source_frame_count=180_000,
        source_in_timecode="00:00:10:00",
        source_out_timecode="00:00:49:24",
    )

    assert selection.expected_frame_count == 1000
    assert selection.expected_frame_count <= MAX_EXPECTED_FRAME_COUNT


def test_le_message_du_plafond_nomme_les_bornes():
    with pytest.raises(SelectionTooLargeError) as excinfo:
        select_source_frames(fps_source=25, fps_target=25, source_frame_count=5000)

    message = str(excinfo.value)
    assert "--in" in message
    assert "--out" in message


def test_la_cadence_annoncee_porte_sur_la_fenetre_et_non_sur_le_rush():
    """AC 11: le denominateur est `out_index - in_index + 1`, pas `frame_count`."""
    import re

    with pytest.raises(SelectionTooLargeError) as excinfo:
        select_source_frames(
            fps_source=25,
            fps_target=25,
            source_frame_count=180_000,
            source_in_timecode="00:00:10:00",
            source_out_timecode="00:03:29:24",
        )

    cadence = float(re.search(r"au plus ([\d.]+) im/s", str(excinfo.value)).group(1))
    # 5000 images de fenetre: 1000 * 25 / 5000 = 5 im/s, et surtout pas
    # 1000 * 25 / 180000 (0,139 im/s), dix fois trop bas.
    assert cadence > 1
    selection = select_source_frames(
        fps_source=25,
        fps_target=cadence,
        source_frame_count=180_000,
        source_in_timecode="00:00:10:00",
        source_out_timecode="00:03:29:24",
    )
    assert selection.expected_frame_count <= MAX_EXPECTED_FRAME_COUNT


def test_les_bornes_sont_rediffusees_verbatim():
    selection = select_source_frames(
        fps_source=25,
        fps_target=5,
        source_frame_count=100,
        source_in_timecode="00:00:00:00",
        source_out_timecode="00:00:03:24",
    )

    assert selection.source_in_timecode == "00:00:00:00"
    assert selection.source_out_timecode == "00:00:03:24"
    assert selection.expected_frame_count == 20


# --------------------------------------------------------------------------
# Revue du 2026-08-06 -- correctifs sur les messages et les gardes du bornage
# --------------------------------------------------------------------------


def _cadence_conseillee(message: str) -> float:
    return float(message.split("cadence d'au plus ")[1].split(" im/s")[0])


@pytest.mark.parametrize("fenetre", [1001, 1002, 1499, 2001, 3001, 5001, 5002, 7777])
def test_la_cadence_conseillee_fait_toujours_rentrer_la_fenetre(fenetre):
    """Revue: l'arrondi se faisait vers le haut, donc le conseil etait refuse.

    Mesure avant correctif: fenetre de 5001 images a 25 im/s -> « viser une
    cadence d'au plus 5 im/s », et 5 im/s produit 1001 images, donc le meme
    refus. Un balayage exhaustif avait trouve plus de trois mille fenetres
    dans ce cas. Le test d'origine n'echantillonnait que 5000, la seule valeur
    de la serie ou l'arrondi tombe du bon cote.
    """
    with pytest.raises(SelectionTooLargeError) as trop_gros:
        select_source_frames(
            fps_source=25, fps_target=25, source_frame_count=fenetre
        )

    conseillee = _cadence_conseillee(str(trop_gros.value))
    assert conseillee > 0

    rentre = select_source_frames(
        fps_source=25, fps_target=conseillee, source_frame_count=fenetre
    )
    assert rentre.expected_frame_count <= MAX_EXPECTED_FRAME_COUNT


def test_la_cadence_conseillee_rentre_aussi_sur_une_fenetre_bornee():
    """Le cas mesure par l'auditeur, bornes comprises."""
    with pytest.raises(SelectionTooLargeError) as trop_gros:
        select_source_frames(
            fps_source=24,
            fps_target=24,
            source_frame_count=20000,
            source_out_timecode="00:01:06:08",
        )

    conseillee = _cadence_conseillee(str(trop_gros.value))
    rentre = select_source_frames(
        fps_source=24,
        fps_target=conseillee,
        source_frame_count=20000,
        source_out_timecode="00:01:06:08",
    )
    assert rentre.expected_frame_count <= MAX_EXPECTED_FRAME_COUNT


def test_la_cadence_conseillee_reste_utilisable_sur_une_fenetre_enorme():
    """Elle ne doit jamais tomber a zero, ni a une valeur non extractible."""
    with pytest.raises(SelectionTooLargeError) as trop_gros:
        select_source_frames(
            fps_source=25, fps_target=25, source_frame_count=25 * 3600 * 5
        )

    conseillee = _cadence_conseillee(str(trop_gros.value))
    assert conseillee > 0
    rentre = select_source_frames(
        fps_source=25, fps_target=conseillee, source_frame_count=25 * 3600 * 5
    )
    assert rentre.expected_frame_count <= MAX_EXPECTED_FRAME_COUNT


def test_une_borne_d_entree_hors_du_rush_est_diagnostiquee_pour_ce_qu_elle_est():
    """Revue: le refus incriminait une borne de sortie jamais fournie.

    Il expliquait de surcroit le cas d'une borne **anterieure** au debut du
    rush, c'est-a-dire l'exact contraire de ce que l'operateur avait fait.
    """
    with pytest.raises(InvalidBoundsError) as refus:
        select_source_frames(
            fps_source=25,
            fps_target=5,
            source_frame_count=100,
            source_in_timecode="00:00:10:00",
        )

    message = str(refus.value)
    assert "source_in_timecode" in message
    assert "source_out_timecode" not in message, (
        "on ne reproche pas a l'operateur une option qu'il n'a pas passee"
    )
    assert "anterieure au debut du rush" not in message
    # AC 3: nommer le dernier index valide ET le dernier timecode valide.
    assert "99" in message and "00:00:03:24" in message


def test_le_rappel_du_rebouclage_ne_sort_que_lorsqu_il_explique_quelque_chose():
    """Une borne qui a reellement reboucle garde son explication."""
    with pytest.raises(InvalidBoundsError) as refus:
        select_source_frames(
            fps_source=25,
            fps_target=5,
            source_frame_count=100,
            source_start_timecode="00:00:10:00",
            source_in_timecode="00:00:05:00",
        )

    assert "reboucle a 24 h" in str(refus.value)


def test_un_refus_de_borne_sur_cardinal_estime_ne_l_enonce_pas_comme_un_fait():
    """Revue: le message etait identique au caractere pres, exact ou estime.

    L'operateur pouvait se voir refuser une borne pourtant valide, contre un
    nombre d'images que l'outil lui-meme ne fait qu'estimer, sans que rien ne
    le lui signale.
    """
    with pytest.raises(InvalidBoundsError) as estime:
        select_source_frames(
            fps_source=25,
            fps_target=5,
            source_frame_count=100,
            source_frame_count_is_exact=False,
            source_out_timecode="00:00:04:10",
        )
    with pytest.raises(InvalidBoundsError) as exact:
        select_source_frames(
            fps_source=25,
            fps_target=5,
            source_frame_count=100,
            source_frame_count_is_exact=True,
            source_out_timecode="00:00:04:10",
        )

    assert str(estime.value) != str(exact.value)
    assert "estim" in str(estime.value).lower()
    assert "estim" not in str(exact.value).lower()
