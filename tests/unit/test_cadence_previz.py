"""Tests de la previsualisation multi-cadences (story 3.6).

Deux niveaux, tous deux exiges par l'AC 10.

* **Niveau 1, sans aucun affichage ni binaire.** Le lecteur ecrit dans un
  `sink` injectable et lit une horloge injectee: l'echeancier, les metriques,
  les codes, la politique de retard, le cache et la navigation entre cadences
  sont verifies de facon **deterministe**, sans le moindre pixel et sans
  ffmpeg. C'est la que vit l'essentiel de la couverture.
* **Niveau 2, affichage reel sur ecran virtuel**, marque `skipif` sur absence
  de `Xvfb` ou de `ffmpeg`, sur le modele de `tests/unit/test_ffmpeg_utils.py`
  et `tests/unit/test_poc_run.py`. Il verifie ce que le niveau 1 ne peut pas
  voir: une fenetre s'ouvre, et l'image affichee correspond a une frame
  **retenue** par la selection et jamais a une frame ecartee. C'est ce niveau
  qui interdit qu'un lecteur qui n'affiche rien passe les tests.
"""

from __future__ import annotations

import ast
import os
import shutil
import signal
import subprocess
import sys
import time
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import cadence_previz, cli, extraction, video_metadata
from mixed_media_utility.cadence_previz import (
    CACHE_EVICTED,
    DECODE_TRUNCATED,
    DEFAULT_MEMORY_BUDGET_MB,
    DEFAULT_PREVIEW_HEIGHT,
    DISPLAY_UNAVAILABLE,
    FINAL_DRIFT_RATIO_THRESHOLD,
    FRAMES_SKIPPED,
    KEY_LOOP,
    KEY_NEXT,
    KEY_PREVIOUS,
    KEY_QUIT,
    KEY_REPLAY,
    LATE_FRAME_RATE_THRESHOLD,
    CvWindowSink,
    LATE_FRAME_TOLERANCE_S,
    ON_LATE_REPORT,
    ON_LATE_SKIP,
    PLAYBACK_WARNING_CODES,
    REALTIME_NOT_HELD,
    DisplayUnavailableError,
    FrameCache,
    FrameObservation,
    NullSink,
    RecordingSink,
    SequentialFrameReader,
    build_playback_report,
    build_schedule,
    OVERLAY_LOOP_OFF,
    OVERLAY_LOOP_ON,
    OVERLAY_RATE_TOLERANCE,
    PresentedFrame,
    compute_current_rate,
    format_overlay,
    format_report_lines,
    play_cadences,
    prepare_previz,
    restrict_schedule,
    should_present,
)
from mixed_media_utility.extraction import ExtractionInputError
from mixed_media_utility.frame_selection import select_source_frames
from mixed_media_utility.io import project_layout
from mixed_media_utility.io.naming import (
    build_extracted_frame_filename,
    normalize_identifier,
)

MODULE_PATH = REPO_ROOT / "src" / "mixed_media_utility" / "cadence_previz.py"

requires_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe binaries not available on PATH",
)

# La garde du niveau 2 a TROIS prerequis, pas deux -- le troisieme a ete cree
# par `EPIC11-ARB-253` (2026-09-06, passage a `opencv-python-headless`) et la
# garde ne l'a pas suivi. Trouve par le run de CI 34198324696 sur le depot
# public, ou `test_a_real_window_...` a rendu, apres 172 verts :
#
#   DISPLAY_UNAVAILABLE: cette compilation d'OpenCV n'expose aucune interface
#   graphique (roue 'headless').
#
# Ce n'est PAS un test qu'on ecarte pour verdir : la capacite est reellement
# absente d'une installation conforme aux declarations du depot, et le produit
# la refuse EXPRES, avec un diagnostic et deux issues -- refus deja mesure au
# niveau 1 par `test_...DISPLAY_UNAVAILABLE...`. Un banc qui exige une roue
# que le produit ne declare plus mesure l'environnement de son auteur, pas le
# produit : ici, `opencv-contrib-python` que porte le conteneur de
# developpement, et que la CI n'a pas.
#
# La CAPACITE est lue par le detecteur DU PRODUIT plutot que redevinee ici :
# `hasattr(cv2, "imshow")` rend `True` meme sur une roue headless -- c'est ce
# que le docstring de `cadence_previz._opencv_sait_afficher` releve --, seule
# la ligne `GUI:` de `getBuildInformation()` distingue les deux.
requires_xvfb = pytest.mark.skipif(
    shutil.which("Xvfb") is None
    or shutil.which("ffmpeg") is None
    or not cadence_previz._opencv_sait_afficher(),
    reason="Xvfb, ffmpeg, or a GUI-capable OpenCV build not available",
)


# --------------------------------------------------------------------------
# Outillage de test: horloge, capture et sink, tous injectes
# --------------------------------------------------------------------------


class FakeClock:
    """Horloge monotone simulee: aucun test de cadencement ne dort reellement."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = float(start)

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        if seconds > 0:
            self.now += float(seconds)


class FakeCapture:
    """Substitut de `cv2.VideoCapture`: sequentiel, et rien d'autre.

    Il n'expose deliberement **ni** `set`, **ni** `get`: un module qui
    tenterait de se positionner par `CAP_PROP_POS_FRAMES` ou de lire
    `CAP_PROP_FRAME_COUNT` echouerait ici bruyamment.
    """

    def __init__(self, frames, *, clock=None, decode_cost_s: float = 0.0) -> None:
        self._frames = frames
        self._clock = clock
        self._decode_cost_s = decode_cost_s
        self.position = 0
        self.released = False

    def isOpened(self) -> bool:  # noqa: N802 (nom impose par l'API OpenCV)
        return True

    def read(self):
        if self._clock is not None and self._decode_cost_s:
            self._clock.advance(self._decode_cost_s)
        if self.position >= len(self._frames):
            return False, None
        image = self._frames[self.position]
        self.position += 1
        return True, image

    def release(self) -> None:
        self.released = True


def make_frames(count: int):
    """Rush synthetique en memoire: chaque frame porte son propre rang.

    `int32` plutot que `uint8`: le rang doit rester lisible tel quel au-dela de
    255, sans quoi deux frames distantes deviendraient indiscernables et le
    test de jonction ne prouverait plus rien.
    """
    return [np.full((6, 8, 3), index, dtype=np.int32) for index in range(count)]


def value_of(image) -> int:
    return int(image[0, 0, 0])


class CountingSink(RecordingSink):
    """`RecordingSink` qui releve le compteur de decodages a chaque frame."""

    def __init__(self, reader, **kwargs) -> None:
        super().__init__(**kwargs)
        self._reader = reader
        self.read_counts: list[int] = []

    def present(self, image, presentation) -> None:
        super().present(image, presentation)
        self.read_counts.append(self._reader.read_count)


def make_session(
    *,
    fps_source=25,
    fps_targets=(5,),
    source_frame_count=50,
    start_seconds=None,
    duration_seconds=None,
    source_in_timecode=None,
    source_out_timecode=None,
) -> cadence_previz.PrevizSession:
    """Session fabriquee sans probe: le noyau de lecture ne connait que ceci."""
    selections = tuple(
        select_source_frames(
            fps_source=fps_source,
            fps_target=fps_target,
            source_frame_count=source_frame_count,
            source_in_timecode=source_in_timecode,
            source_out_timecode=source_out_timecode,
        )
        for fps_target in fps_targets
    )
    schedules = tuple(
        restrict_schedule(
            build_schedule(selection),
            start_seconds=start_seconds,
            duration_seconds=duration_seconds,
        )
        for selection in selections
    )
    return cadence_previz.PrevizSession(
        video_path=Path("rush-de-test.mov"),
        fps_source=Fraction(fps_source),
        source_frame_count=source_frame_count,
        source_frame_count_is_exact=True,
        start_timecode=None,
        stream_duration_seconds=None,
        fps_targets=tuple(float(value) for value in fps_targets),
        selections=selections,
        schedules=schedules,
    )


def probe_fixture(
    *, r_frame_rate="25/1", nb_frames="50", duration="2.0", **overrides
) -> dict:
    stream = {
        "codec_type": "video",
        "codec_name": "h264",
        "pix_fmt": "yuv420p",
        "width": 320,
        "height": 180,
        "r_frame_rate": r_frame_rate,
        "avg_frame_rate": r_frame_rate,
        "nb_frames": nb_frames,
        "duration": duration,
    }
    stream.update(overrides)
    return {"streams": [stream], "format": {"tags": {}}}


# --------------------------------------------------------------------------
# AC 4: echeancier pur, sans horloge et sans affichage
# --------------------------------------------------------------------------


def test_schedule_uses_the_source_time_base_not_the_target_one():
    """La duree previsualisee est celle du rush, pas celle de la cadence cible.

    50 frames a 25 im/s durent 2 s. Vues a 5 im/s, les 10 frames retenues
    doivent s'etaler sur ces memes 2 s (saccade), et non sur 10/5 = 2 s par
    coincidence: le vecteur a 3 im/s ci-dessous le distingue sans ambiguite.
    """
    selection = select_source_frames(
        fps_source=25, fps_target=5, source_frame_count=50
    )
    schedule = build_schedule(selection)

    assert [frame.source_index for frame in schedule] == [
        0, 5, 10, 15, 20, 25, 30, 35, 40, 45
    ]
    assert [frame.t_theo_s for frame in schedule] == pytest.approx(
        [0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6, 1.8]
    )


def test_schedule_of_a_non_divisible_target_keeps_the_source_base():
    selection = select_source_frames(
        fps_source=25, fps_target=3, source_frame_count=50
    )
    schedule = build_schedule(selection)

    assert [frame.source_index for frame in schedule] == [
        0, 8, 16, 25, 33, 41
    ]
    # 8 / 25 = 0,32 s: l'instant vient de l'indice SOURCE, jamais de 1/3 s.
    assert schedule[1].t_theo_s == pytest.approx(0.32)
    assert schedule[-1].t_theo_s == pytest.approx(41 / 25)


def test_schedule_carries_the_timecode_of_story_3_2_verbatim():
    selection = select_source_frames(
        fps_source=25, fps_target=12.5, source_frame_count=50
    )
    schedule = build_schedule(selection)
    assert [frame.frame_timecode for frame in schedule] == [
        frame.frame_timecode for frame in selection
    ]


def test_schedule_is_pure_and_repeatable():
    selection = select_source_frames(
        fps_source=30, fps_target=12.5, source_frame_count=90
    )
    assert build_schedule(selection) == build_schedule(selection)


def test_restrict_schedule_keeps_the_indices_of_the_whole_rush():
    """Question ouverte 1: la fenetre restreint l'affichage, jamais la selection."""
    selection = select_source_frames(
        fps_source=25, fps_target=5, source_frame_count=50
    )
    schedule = build_schedule(selection)
    window = restrict_schedule(schedule, start_seconds=0.5, duration_seconds=0.6)

    assert [frame.source_index for frame in window] == [15, 20, 25]
    # Les indices sont ceux du rush entier; seuls les instants sont rebases.
    assert [frame.output_rank for frame in window] == [3, 4, 5]
    assert window[0].t_theo_s == pytest.approx(0.0)
    assert window[-1].t_theo_s == pytest.approx(0.4)


def test_priming_cost_is_measured_apart_and_never_counted_as_lateness():
    """Atteindre la frame 100 impose d'en decoder cent: ce n'est pas un retard.

    La lecture etant sequentielle et sans positionnement par index, une fenetre
    `--start` paie le decodage de tout ce qui la precede. Compter ce cout comme
    du retard de cadencement rendrait toute fenetre structurellement « en
    retard » et masquerait la seule chose que la mesure doit dire: la cadence
    a-t-elle ete TENUE une fois la lecture lancee.
    """
    session = make_session(
        fps_source=25,
        fps_targets=(5,),
        source_frame_count=250,
        start_seconds=4.0,
        duration_seconds=1.0,
    )
    clock = FakeClock()
    sink = RecordingSink(sleeper=clock.advance, keys=[KEY_QUIT])

    result = play_cadences(
        session,
        sink=sink,
        height=None,
        clock=clock,
        capture_factory=lambda: FakeCapture(
            make_frames(250), clock=clock, decode_cost_s=0.01
        ),
    )

    report = result.reports[0]
    assert sink.presented[0].source_index == 100
    # 101 lectures a 10 ms avant la premiere image affichee.
    assert report.amorcage_s == pytest.approx(1.01, abs=0.02)
    assert report.retard_max_s < 0.02
    assert report.temps_reel_tenu is True


def test_restrict_schedule_refuses_negative_start_and_null_duration():
    schedule = build_schedule(
        select_source_frames(fps_source=25, fps_target=5, source_frame_count=50)
    )
    with pytest.raises(extraction.ExtractionInputError):
        restrict_schedule(schedule, start_seconds=-1.0)
    with pytest.raises(extraction.ExtractionInputError):
        restrict_schedule(schedule, duration_seconds=0.0)


# --------------------------------------------------------------------------
# AC 2: la sequence presentee est exactement celle que `extract` retiendrait
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fps_source, fps_target, source_frame_count",
    [
        (25, 3, 250),
        (25, 5, 250),
        (25, 12.5, 250),
        (30, 12.5, 300),
        (24, 3, 96),
        (50, 5, 500),
    ],
)
def test_presented_indices_equal_select_source_frames(
    fps_source, fps_target, source_frame_count
):
    """Test de jonction: comparaison element par element, jamais un echantillon."""
    expected = [
        frame.source_index
        for frame in select_source_frames(
            fps_source=fps_source,
            fps_target=fps_target,
            source_frame_count=source_frame_count,
        )
    ]
    session = make_session(
        fps_source=fps_source,
        fps_targets=(fps_target,),
        source_frame_count=source_frame_count,
    )
    clock = FakeClock()
    sink = RecordingSink(sleeper=clock.advance, keys=[KEY_QUIT])
    frames = make_frames(source_frame_count)

    play_cadences(
        session,
        sink=sink,
        height=None,
        clock=clock,
        capture_factory=lambda: FakeCapture(frames, clock=clock),
    )

    assert list(sink.source_indices) == expected
    # Et ce sont bien les images de ces rangs, pas des voisines.
    assert [value_of(image) for image in sink.images] == [
        value_of(frames[index]) for index in expected
    ]


def _module_tree() -> ast.Module:
    return ast.parse(MODULE_PATH.read_text(encoding="utf-8"), filename=str(MODULE_PATH))


def _docstring_constants(tree: ast.Module) -> set:
    """Identite des noeuds qui sont des docstrings, et non du code.

    Sans cette distinction, un module qui **documente** un interdit ("ne jamais
    employer CAP_PROP_POS_FRAMES") echouerait au test qui verifie qu'il ne
    l'emploie pas: la documentation d'une regle serait punie comme sa
    violation.
    """
    marked = set()
    containers = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    for node in ast.walk(tree):
        if not isinstance(node, containers):
            continue
        body = getattr(node, "body", [])
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            marked.add(id(body[0].value))
    return marked


def module_identifiers() -> set:
    """Tous les identifiants **de code** du module, docstrings exclues."""
    tree = _module_tree()
    names: set = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.keyword) and node.arg:
            names.add(node.arg)
        elif isinstance(node, ast.Import):
            names.update(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
            names.update(alias.asname or alias.name for alias in node.names)
    return names


def module_attribute_names() -> set:
    """Uniquement les attributs appeles ou lus (`objet.nom`)."""
    return {
        node.attr
        for node in ast.walk(_module_tree())
        if isinstance(node, ast.Attribute)
    }


def module_string_constants() -> list:
    tree = _module_tree()
    docstrings = _docstring_constants(tree)
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


def test_module_never_reads_the_frame_count_from_opencv():
    """AC 2, Piege 1: `CAP_PROP_FRAME_COUNT` produirait une autre selection."""
    assert "CAP_PROP_FRAME_COUNT" not in module_identifiers()
    assert not any("CAP_PROP" in text for text in module_string_constants())


def test_module_never_seeks_by_frame_index():
    """AC 3, Piege 2: le positionnement par index atterrit sur une image cle."""
    identifiers = module_identifiers()
    assert "CAP_PROP_POS_FRAMES" not in identifiers
    assert "CAP_PROP_POS_MSEC" not in identifiers
    # `capture.set(...)` est la seule facon de positionner une `VideoCapture`:
    # l'absence de cet appel verrouille l'interdit quelle que soit la propriete
    # employee.
    assert "set" not in module_attribute_names()


def test_module_does_not_reimplement_any_sampling_rule():
    """Aucun arrondi de cadence ne vit dans ce module: il consomme la 3.2."""
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    called = {
        node.func.attr if isinstance(node.func, ast.Attribute) else
        getattr(node.func, "id", "")
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    assert "select_source_frames" in called
    assert "qualify_source" in called
    assert "resolve_source_frame_count" in called
    # Les primitives d'arrondi de cadence sont celles de la story 3.2.
    assert {"floor", "ceil"} & called == set()


def test_module_does_not_call_the_naming_guard_of_extract():
    """`check_fps_form_consistency` est une garde de nommage: la previz ne nomme rien."""
    assert "check_fps_form_consistency" not in module_identifiers()


# --------------------------------------------------------------------------
# AC 5: mesure de l'ecart au temps reel, fonction pure
# --------------------------------------------------------------------------


def observations(pairs):
    return [
        FrameObservation(
            output_rank=rank, source_index=rank * 5, t_theo_s=theo, t_real_s=real
        )
        for rank, (theo, real) in enumerate(pairs)
    ]


def test_report_on_a_perfectly_held_playback():
    report = build_playback_report(
        observations([(0.0, 0.0), (0.2, 0.2), (0.4, 0.4), (0.6, 0.6)]),
        fps_target=5,
        frames_attendues=4,
        duree_nominale_s=0.6,
    )

    assert report.frames_presentees == 4
    assert report.frames_attendues == 4
    assert report.retard_max_s == pytest.approx(0.0)
    assert report.derive_finale_s == pytest.approx(0.0)
    assert report.taux_frames_en_retard == 0.0
    assert report.temps_reel_tenu is True
    assert report.warnings == ()


def test_report_measures_lateness_against_the_absolute_deadline():
    """Piege 4: un ecart d'intervalle a intervalle masquerait la derive lente."""
    # Intervalles reguliers de 0,21 s pour une echeance de 0,20 s: chaque
    # intervalle a l'air bon, la derive finale vaut pourtant 40 ms.
    pairs = [(0.2 * rank, 0.21 * rank) for rank in range(5)]
    report = build_playback_report(
        observations(pairs), fps_target=5, frames_attendues=5, duree_nominale_s=0.8
    )

    assert report.derive_finale_s == pytest.approx(0.04)
    assert report.retard_max_s == pytest.approx(0.04)
    assert report.temps_reel_tenu is False
    assert REALTIME_NOT_HELD in report.warnings


def test_report_late_frame_threshold_is_independent_of_the_target_rate():
    """Un retard de 25 ms est en retard a 3 im/s comme a 12,5 im/s."""
    pairs = [(0.0, 0.0), (1.0, 1.025)]
    for fps_target in (3, 12.5):
        report = build_playback_report(
            observations(pairs),
            fps_target=fps_target,
            frames_attendues=2,
            duree_nominale_s=1.0,
        )
        assert report.taux_frames_en_retard == pytest.approx(0.5)
        assert report.retard_max_s == pytest.approx(0.025)


def test_report_tolerates_a_lateness_below_the_threshold():
    pairs = [(0.2 * rank, 0.2 * rank + 0.010) for rank in range(20)]
    report = build_playback_report(
        observations(pairs), fps_target=5, frames_attendues=20, duree_nominale_s=3.8
    )
    assert report.taux_frames_en_retard == 0.0
    # 10 ms de derive pour 3,8 s nominales: sous les 2 % (76 ms).
    assert report.temps_reel_tenu is True


def test_report_percentiles_and_median_on_a_hand_made_series():
    pairs = [(0.0, 0.0)] + [
        (0.2 * rank, 0.2 * rank + value)
        for rank, value in enumerate(
            [0.001, 0.002, 0.003, 0.004, 0.005, 0.006, 0.007, 0.008, 0.500], start=1
        )
    ]
    report = build_playback_report(
        observations(pairs), fps_target=5, frames_attendues=10, duree_nominale_s=1.8
    )
    assert report.retard_max_s == pytest.approx(0.5)
    # 10 valeurs: mediane = moyenne des 5e et 6e (0,004 et 0,005).
    assert report.retard_median_s == pytest.approx(0.0045)
    # p95 par rang le plus proche sur 10 valeurs: ceil(9,5) = 10e valeur.
    assert report.retard_p95_s == pytest.approx(0.5)
    assert report.taux_frames_en_retard == pytest.approx(0.1)


def test_report_drift_threshold_is_two_percent_of_the_nominal_duration():
    # 100 s nominales, derive de 1,9 s: sous les 2 %. Aucune frame en retard.
    pairs = [(0.0, 0.0), (100.0, 101.9)]
    report = build_playback_report(
        observations(pairs), fps_target=1, frames_attendues=2, duree_nominale_s=100.0
    )
    assert report.taux_frames_en_retard == pytest.approx(0.5)
    assert report.temps_reel_tenu is False  # le taux, lui, depasse 1 %

    long_pairs = [(rank, rank) for rank in range(200)]
    long_pairs[-1] = (199.0, 199.0 + FINAL_DRIFT_RATIO_THRESHOLD * 199.0 + 1.0)
    report = build_playback_report(
        observations(long_pairs),
        fps_target=1,
        frames_attendues=200,
        duree_nominale_s=199.0,
    )
    assert report.taux_frames_en_retard <= LATE_FRAME_RATE_THRESHOLD
    assert report.temps_reel_tenu is False  # ... et la, c'est la derive


def test_report_of_an_empty_playback_is_not_declared_held():
    report = build_playback_report(
        [], fps_target=5, frames_attendues=12, duree_nominale_s=2.2
    )
    assert report.frames_presentees == 0
    assert report.temps_reel_tenu is False
    assert REALTIME_NOT_HELD in report.warnings


def test_report_effective_rate_is_measured_not_declared():
    pairs = [(0.2 * rank, 0.4 * rank) for rank in range(6)]
    report = build_playback_report(
        observations(pairs), fps_target=5, frames_attendues=6, duree_nominale_s=1.0
    )
    # 6 frames en 2,0 s, soit 5 intervalles: 2,5 im/s reelles pour 5 demandees.
    assert report.cadence_effective == pytest.approx(2.5)


def test_effective_rate_is_undefined_below_two_frames():
    """Une frame ne definit aucun intervalle: la cadence n'est pas inventee."""
    report = build_playback_report(
        observations([(0.0, 0.0)]),
        fps_target=3,
        frames_attendues=1,
        duree_nominale_s=0.0,
    )
    # Sous deux frames la cadence n'est pas definie: `None`, jamais `0.0`,
    # qui se lirait comme une mesure (revue du 2026-08-05).
    assert report.cadence_effective is None


def test_warning_codes_are_emitted_in_canonical_order_without_duplicate():
    report = build_playback_report(
        observations([(0.0, 0.0), (0.2, 0.9)]),
        fps_target=5,
        frames_attendues=4,
        duree_nominale_s=0.6,
        frames_omises=2,
        extra_warnings=(CACHE_EVICTED, DECODE_TRUNCATED, CACHE_EVICTED),
    )
    assert report.warnings == (
        REALTIME_NOT_HELD, FRAMES_SKIPPED, DECODE_TRUNCATED, CACHE_EVICTED
    )
    assert set(report.warnings) <= set(PLAYBACK_WARNING_CODES)


def test_report_lines_are_ascii_without_accent():
    report = build_playback_report(
        observations([(0.0, 0.0), (0.2, 0.5)]),
        fps_target=12.5,
        frames_attendues=2,
        duree_nominale_s=0.2,
        frames_omises=1,
    )
    text = "\n".join(format_report_lines(report))
    assert text.isascii()
    assert "PAS la selection complete" in text


# --------------------------------------------------------------------------
# AC 6: politique de retard, aucune frame sautee en silence
# --------------------------------------------------------------------------


def test_report_policy_never_omits_a_frame():
    assert should_present(t_theo_s=1.0, elapsed_s=99.0, on_late=ON_LATE_REPORT) is True


def test_skip_policy_omits_only_frames_whose_deadline_is_past():
    assert should_present(t_theo_s=1.0, elapsed_s=1.0, on_late=ON_LATE_SKIP) is True
    assert should_present(
        t_theo_s=1.0, elapsed_s=1.0 + LATE_FRAME_TOLERANCE_S / 2, on_late=ON_LATE_SKIP
    ) is True
    assert should_present(
        t_theo_s=1.0, elapsed_s=1.0 + LATE_FRAME_TOLERANCE_S * 2, on_late=ON_LATE_SKIP
    ) is False
    assert should_present(t_theo_s=1.0, elapsed_s=1.5, on_late=ON_LATE_SKIP) is False


def test_unknown_late_policy_is_refused():
    with pytest.raises(extraction.ExtractionInputError):
        should_present(t_theo_s=0.0, elapsed_s=0.0, on_late="ignore")


def _late_playback(on_late):
    """Lecture ou chaque frame coute 0,5 s a presenter, pour une echeance de 0,2 s."""
    session = make_session(fps_source=25, fps_targets=(5,), source_frame_count=50)
    clock = FakeClock()
    sink = RecordingSink(
        sleeper=clock.advance,
        keys=[KEY_QUIT],
        delays={rank: 0.5 for rank in range(10)},
    )
    result = play_cadences(
        session,
        sink=sink,
        height=None,
        on_late=on_late,
        clock=clock,
        capture_factory=lambda: FakeCapture(make_frames(50), clock=clock),
    )
    return result.reports[0], sink


def test_default_policy_presents_every_selected_frame_and_reports_the_gap():
    report, sink = _late_playback(ON_LATE_REPORT)

    assert report.frames_presentees == report.frames_attendues == 10
    assert report.frames_omises == 0
    assert REALTIME_NOT_HELD in report.warnings
    assert FRAMES_SKIPPED not in report.warnings
    # La lecture s'allonge: 10 frames a 0,5 s au lieu de 1,8 s nominales.
    assert report.duree_reelle_s > report.duree_nominale_s
    assert report.temps_reel_tenu is False
    assert len(sink.presented) == 10


def test_skip_policy_omits_frames_and_says_so():
    report, sink = _late_playback(ON_LATE_SKIP)

    assert report.frames_omises > 0
    assert report.frames_presentees + report.frames_omises == report.frames_attendues
    assert FRAMES_SKIPPED in report.warnings
    assert len(sink.presented) == report.frames_presentees


def test_overlay_stays_minimal_when_frames_are_omitted():
    """AC 6: le compte de frames omises tient dans le rapport, pas a l'ecran.

    L'incrustation reste la meme ligne de trois zones quoi qu'il arrive: sur
    specification d'Egan, un compteur annexe qui apparait en cours de lecture
    deplacerait le regard au moment ou il doit rester sur l'image.
    """
    report, sink = _late_playback(ON_LATE_SKIP)
    overlays = [format_overlay(item) for item in sink.presented]
    assert all("omise" not in overlay.rate for overlay in overlays)
    assert all(
        "omise" not in overlay.left and "omise" not in overlay.right
        for overlay in overlays
    )
    assert report.frames_omises > 0
    assert f"{report.frames_omises}" in "\n".join(format_report_lines(report))


def test_a_measured_gap_is_not_a_failure(tmp_path, monkeypatch, capsys):
    """Dans les deux modes, le code de sortie reste 0."""
    video = tmp_path / "rush.mp4"
    video.write_bytes(b"fake")
    monkeypatch.setattr(
        video_metadata, "probe_media", lambda *args, **kwargs: probe_fixture()
    )
    monkeypatch.setattr(
        cadence_previz,
        "SequentialFrameReader",
        lambda *args, **kwargs: _FakeReader(make_frames(50)),
    )
    monkeypatch.setattr(cadence_previz, "CvWindowSink", lambda **kwargs: NullSink(
        sleeper=lambda seconds: None
    ))

    for on_late in (ON_LATE_REPORT, ON_LATE_SKIP):
        code = cli.main(
            [
                "previz", "--video", str(video), "--fps", "5",
                "--on-late", on_late, "--no-display",
            ]
        )
        assert code == 0
    capsys.readouterr()


class _FakeReader:
    """Lecteur de frames en memoire, pour les tests de CLI sans binaire."""

    def __init__(self, frames) -> None:
        self._frames = frames
        self.read_count = 0
        self.open_count = 1
        self.truncated = False

    def frame_at(self, source_index):
        self.read_count += 1
        if source_index >= len(self._frames):
            return None
        return self._frames[source_index]

    def close(self) -> None:
        return None


# --------------------------------------------------------------------------
# AC 7: plusieurs cadences dans une session, cache memoire borne
# --------------------------------------------------------------------------


def test_a_single_session_prepares_every_cadence_before_the_first_frame():
    session = make_session(fps_targets=(3, 5, 12.5), source_frame_count=250)
    assert len(session.selections) == 3
    assert len(session.schedules) == 3
    for fps_target, selection in zip(session.fps_targets, session.selections):
        assert float(selection.fps_target) == pytest.approx(fps_target)


def test_second_pass_at_the_same_cadence_decodes_strictly_less():
    session = make_session(fps_source=25, fps_targets=(5,), source_frame_count=50)
    clock = FakeClock()
    frames = make_frames(50)
    reader = SequentialFrameReader(
        session.video_path, height=None, capture_factory=lambda: FakeCapture(frames)
    )
    sink = CountingSink(
        reader, sleeper=clock.advance, keys=[KEY_REPLAY, KEY_QUIT]
    )

    result = play_cadences(session, sink=sink, height=None, clock=clock, reader=reader)

    assert len(result.reports) == 2
    first = sink.presented[:10]
    second = sink.presented[10:]
    # Sequence identique, element par element.
    assert [item.source_index for item in first] == [
        item.source_index for item in second
    ]
    decodes_first = sink.read_counts[9]
    decodes_second = sink.read_counts[19] - sink.read_counts[9]
    assert decodes_second < decodes_first
    assert decodes_second == 0
    assert result.cache_hits >= 10


def test_two_cadences_share_the_frames_they_have_in_common():
    """A 25 im/s, 12,5 et 5 partagent une frame source sur deux."""
    session = make_session(fps_source=25, fps_targets=(12.5, 5), source_frame_count=50)
    clock = FakeClock()
    sink = RecordingSink(sleeper=clock.advance, keys=[KEY_NEXT, KEY_QUIT])

    result = play_cadences(
        session,
        sink=sink,
        height=None,
        clock=clock,
        capture_factory=lambda: FakeCapture(make_frames(50)),
    )

    assert len(result.reports) == 2
    # Les indices de la passe a 5 im/s deja vus a 12,5 im/s sont servis par le
    # cache: 0, 10, 20, 30, 40.
    assert result.cache_hits >= 5


def test_navigation_moves_between_cadences_without_reopening_the_file():
    session = make_session(fps_source=25, fps_targets=(3, 5), source_frame_count=50)
    clock = FakeClock()
    frames = make_frames(50)
    opens = {"count": 0}

    def factory():
        opens["count"] += 1
        return FakeCapture(frames)

    reader = SequentialFrameReader(
        session.video_path, height=None, capture_factory=factory
    )
    sink = RecordingSink(
        sleeper=clock.advance, keys=[KEY_NEXT, KEY_PREVIOUS, KEY_QUIT]
    )

    result = play_cadences(session, sink=sink, height=None, clock=clock, reader=reader)

    assert [round(report.fps_target, 3) for report in result.reports] == [3.0, 5.0, 3.0]
    # Le retour a 3 im/s est integralement servi par le cache: aucune
    # reouverture supplementaire n'est necessaire.
    assert opens["count"] <= 2


def test_quit_key_ends_the_session_immediately():
    session = make_session(fps_targets=(3, 5, 12.5), source_frame_count=50)
    clock = FakeClock()
    sink = RecordingSink(sleeper=clock.advance, keys=[KEY_QUIT])
    result = play_cadences(
        session,
        sink=sink,
        height=None,
        clock=clock,
        capture_factory=lambda: FakeCapture(make_frames(50)),
    )
    assert len(result.reports) == 1


def test_non_interactive_sink_plays_every_cadence_once():
    session = make_session(fps_targets=(3, 5, 12.5), source_frame_count=50)
    clock = FakeClock()
    sink = NullSink(sleeper=clock.advance)
    result = play_cadences(
        session,
        sink=sink,
        height=None,
        clock=clock,
        capture_factory=lambda: FakeCapture(make_frames(50)),
    )
    assert len(result.reports) == 3


def test_cache_evicts_in_lru_order_and_never_alters_the_sequence():
    cache = FrameCache(budget_bytes=3 * make_frames(1)[0].nbytes)
    frames = make_frames(4)
    for index, frame in enumerate(frames):
        cache.put(index, frame)

    assert 0 not in cache  # le plus ancien est parti
    assert 3 in cache
    assert cache.evictions == 1
    assert cache.used_bytes <= cache.budget_bytes


def test_cache_miss_redecodes_and_the_presented_sequence_is_unchanged():
    """Le cache est une optimisation, jamais une condition de justesse."""
    session = make_session(fps_source=25, fps_targets=(5,), source_frame_count=50)
    expected = [frame.source_index for frame in session.schedules[0]]

    sequences = []
    for budget_mb in (0.000001, 512):
        clock = FakeClock()
        sink = RecordingSink(sleeper=clock.advance, keys=[KEY_QUIT])
        play_cadences(
            session,
            sink=sink,
            height=None,
            memory_budget_mb=budget_mb,
            clock=clock,
            capture_factory=lambda: FakeCapture(make_frames(50)),
        )
        sequences.append(list(sink.source_indices))

    assert sequences[0] == sequences[1] == expected


def test_eviction_is_reported_by_its_code():
    session = make_session(fps_source=25, fps_targets=(5,), source_frame_count=50)
    clock = FakeClock()
    sink = RecordingSink(sleeper=clock.advance, keys=[KEY_QUIT])
    result = play_cadences(
        session,
        sink=sink,
        height=None,
        memory_budget_mb=0.000001,
        clock=clock,
        capture_factory=lambda: FakeCapture(make_frames(50)),
    )
    assert CACHE_EVICTED in result.reports[0].warnings


def test_reader_never_goes_backwards_without_reopening():
    frames = make_frames(20)
    opens = {"count": 0}

    def factory():
        opens["count"] += 1
        return FakeCapture(frames)

    reader = SequentialFrameReader(
        Path("rush.mov"), height=None, capture_factory=factory
    )
    assert value_of(reader.frame_at(5)) == value_of(frames[5])
    assert reader.read_count == 6
    assert value_of(reader.frame_at(9)) == value_of(frames[9])
    assert reader.read_count == 10
    # Retour en arriere: reouverture, jamais un positionnement par index.
    assert value_of(reader.frame_at(2)) == value_of(frames[2])
    assert opens["count"] == 2
    reader.close()


def test_reader_reports_a_truncated_stream_instead_of_pretending():
    session = make_session(fps_source=25, fps_targets=(5,), source_frame_count=50)
    clock = FakeClock()
    sink = RecordingSink(sleeper=clock.advance, keys=[KEY_QUIT])
    # Le flux ne rend que 22 frames alors que le cardinal en annonce 50.
    result = play_cadences(
        session,
        sink=sink,
        height=None,
        clock=clock,
        capture_factory=lambda: FakeCapture(make_frames(22)),
    )
    report = result.reports[0]
    assert DECODE_TRUNCATED in report.warnings
    assert report.partiel is True
    assert report.frames_presentees < report.frames_attendues


# --------------------------------------------------------------------------
# AC 8: rien n'est ecrit nulle part, y compris sur interruption
# --------------------------------------------------------------------------

FORBIDDEN_CALL_NAMES = {
    "open", "print", "input", "exec", "eval",
    "write_text", "write_bytes", "touch", "mkdir", "makedirs", "rename",
    "unlink", "rmtree", "remove", "removedirs", "symlink_to", "hardlink_to",
    "mkstemp", "mkdtemp", "NamedTemporaryFile", "TemporaryDirectory",
    "TemporaryFile", "SpooledTemporaryFile",
    "imwrite", "imencode", "VideoWriter",
    "ensure_project_layout", "persist_extraction", "run_extraction",
    "confirm_source_metadata", "render_source_report", "detect_interactive",
    "FileHandler",
}

FORBIDDEN_MODULES = {
    "tempfile", "shutil", "json", "jsonschema", "sqlite3", "pickle", "csv",
    "PySide6", "PyQt5", "PyQt6", "tkinter", "wx", "kivy", "PIL", "reportlab",
    "ffmpeg", "subprocess",
}

ALLOWED_ABSOLUTE_IMPORTS = {
    "__future__", "logging", "os", "statistics", "sys", "time",
    "dataclasses", "fractions", "pathlib", "typing", "cv2",
}

ALLOWED_RELATIVE_IMPORTS = {
    # ARB-12: la previz appelle la meme garde et le meme message que `extract`.
    "codec_profiles",
    "",
    "extraction",
    "video_metadata",
    "frame_selection",
    "numeric_guards",
}


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


def test_module_references_no_forbidden_module():
    referenced = set()
    for node in ast.walk(_module_tree()):
        if isinstance(node, ast.Import):
            referenced.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level:
            referenced.add((node.module or "").split(".")[0])
    assert referenced & FORBIDDEN_MODULES == set()


def test_module_calls_no_write_primitive():
    """AC 8 (a): aucune ecriture possible, verifiee sur l'arbre syntaxique."""
    offenders = []
    for node in ast.walk(_module_tree()):
        if isinstance(node, ast.Call):
            func = node.func
            name = (
                func.id if isinstance(func, ast.Name)
                else func.attr if isinstance(func, ast.Attribute)
                else ""
            )
            if name in FORBIDDEN_CALL_NAMES:
                offenders.append((name, node.lineno))
    assert offenders == []


def test_module_never_touches_the_io_package_nor_the_manifest():
    for node in ast.walk(_module_tree()):
        if isinstance(node, ast.ImportFrom) and node.level:
            assert not (node.module or "").startswith("io")
    identifiers = module_identifiers()
    assert "extraction_manifest" not in identifiers
    assert "project_layout" not in identifiers
    assert "extraction_previz" not in identifiers
    assert not any("project.json" in text for text in module_string_constants())


def test_module_exposes_no_authorizing_function():
    """AC 9: une previz n'autorise rien, et son API ne peut pas le laisser croire."""
    public_names = [
        node.name
        for node in _module_tree().body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and not node.name.startswith("_")
    ]
    assert set(public_names) <= set(cadence_previz.__all__)
    banned_prefixes = (
        "confirm", "approve", "authorize", "grant", "persist", "save", "write",
        "extract", "trigger", "commit",
    )
    for name in public_names + list(cadence_previz.__all__):
        assert not name.lower().startswith(banned_prefixes), name


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
        # AJOUTE PAR LA STORY 8.10, et porte ici au triage de la revue 8.12 le
        # 2026-09-08 -- il aurait du l'etre dans le meme mouvement. `pyyaml`
        # entre dans `requirements.txt` parce que
        # `tests/unit/test_politique_lfs.py` lit les workflows sur le YAML
        # ANALYSE et que sa lecture ne doit plus pouvoir SAUTER : elle gardait,
        # derriere un `importorskip`, la politique dont l'oubli a sature le
        # quota LFS de 10 Go en deux jours.
        #
        # Ce n'est donc PAS une preemption d'Epic 7, ce que cette frontiere
        # existe pour attraper -- c'est une dependance de BANC, ajoutee
        # deliberement et documentee a sa ligne. L'ensemble epingle se deplace
        # DELIBEREMENT, jamais par accommodation d'un rouge.
        "pyyaml",
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
        # stricte ; l'intention et la docstring sont intactes (meme geste que
        # l'amendement 5.1 ci-dessus et la reconciliation de
        # test_scan_previz.py par la story 5.26).
        "pyside6-essentials",
        "pytest-qt",
        # Reconciliation 5.x/11.0 (2026-08-28) : `textual` est l'ajout
        # MANDATE par la story 11.0 (socle TUI, AC 6.2 le specifie nommement,
        # epingle par serie majeure comme les autres lignes). Meme regime que
        # `pyside6` / `pytest-qt` en 2026-08-24 : l'ensemble reste epingle en
        # egalite STRICTE, pour que toute dependance future non mandatee
        # continue de faire rougir ce test. Le module previz de cette fiche
        # n'importe toujours aucun des trois (verrou AST de purete ci-dessus).
        "textual",
    }


def tree_fingerprint(root: Path) -> dict:
    return {
        str(path.relative_to(root)): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in sorted(root.rglob("*"))
    }


@pytest.fixture
def witness_tree(tmp_path, monkeypatch):
    """Un dossier courant et un dossier projet temoin, photographies avant/apres."""
    work_dir = tmp_path / "cwd"
    work_dir.mkdir()
    project_dir = tmp_path / "projet-temoin"
    (project_dir / project_layout.EXTRACT_FRAMES_DIRNAME).mkdir(parents=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")
    monkeypatch.chdir(work_dir)
    return work_dir, project_dir


def test_a_full_session_writes_nothing_anywhere(witness_tree):
    work_dir, project_dir = witness_tree
    before = (tree_fingerprint(work_dir), tree_fingerprint(project_dir))

    session = make_session(fps_targets=(3, 5, 12.5), source_frame_count=50)
    clock = FakeClock()
    sink = RecordingSink(sleeper=clock.advance, keys=[KEY_NEXT, KEY_NEXT, KEY_QUIT])
    play_cadences(
        session,
        sink=sink,
        height=None,
        clock=clock,
        capture_factory=lambda: FakeCapture(make_frames(50)),
    )

    assert (tree_fingerprint(work_dir), tree_fingerprint(project_dir)) == before


def _interrompre_le_processus_courant() -> None:
    """Delivrer au processus courant l'interruption que l'AC 8 (c) exige.

    Sur POSIX, `os.kill(os.getpid(), SIGINT)` fait exactement ce que la touche
    d'interruption fait : le gestionnaire de signal de CPython leve
    `KeyboardInterrupt` a la prochaine frontiere de bytecode.

    **Sur Windows, la meme ligne TUE le processus.** `os.kill` n'y accepte que
    `CTRL_C_EVENT` et `CTRL_BREAK_EVENT` ; pour tout autre numero de signal il
    appelle `TerminateProcess(handle, sig)`, ce qui termine le processus avec
    le numero du signal pour code de sortie. Mesure sur cette machine : le
    sous-processus meurt en rendant `2`, sans une ligne sur la sortie standard.

    Consequence pour ce depot, jusqu'au 2026-08-27 : ce test **abattait
    l'executeur de tests**. `pytest` mourait au milieu de
    `tests/unit/test_cadence_previz.py`, sans resume, sans decompte, sans
    aucune indication de la cause -- et **la suite complete ne pouvait donc
    jamais aller au bout sous Windows**. Ce n'etait pas une famille d'echecs
    de plus : c'etait l'impossibilite de mesurer quoi que ce soit.

    Ce que ce test veut mesurer -- que la session s'arrete proprement, rende un
    rapport partiel et n'ecrive rien -- est exactement ce qu'un
    `KeyboardInterrupt` leve dans la boucle produit, puisque c'est ce que le
    gestionnaire de SIGINT de CPython leve lui-meme. Le signal REEL est donc
    conserve la ou il est fidele, et son effet observable est produit
    directement la ou il ne l'est pas.
    """
    if hasattr(signal, "SIGINT") and os.name != "nt":
        os.kill(os.getpid(), signal.SIGINT)
        return
    raise KeyboardInterrupt


def test_a_session_interrupted_by_sigint_writes_nothing_and_reports_partially(
    witness_tree,
):
    """AC 8 (c): SIGINT reel, rapport partiel, empreinte inchangee, aucune trace."""
    work_dir, project_dir = witness_tree
    before = (tree_fingerprint(work_dir), tree_fingerprint(project_dir))

    session = make_session(fps_source=25, fps_targets=(5,), source_frame_count=50)
    clock = FakeClock()
    captures = []

    def factory():
        capture = FakeCapture(make_frames(50))
        captures.append(capture)
        return capture

    class SigintSink(RecordingSink):
        def present(self, image, presentation):
            super().present(image, presentation)
            if presentation.output_rank == 4:
                _interrompre_le_processus_courant()

    sink = SigintSink(sleeper=clock.advance, keys=[KEY_QUIT])
    reader = SequentialFrameReader(
        session.video_path, height=None, capture_factory=factory
    )

    result = play_cadences(session, sink=sink, height=None, clock=clock, reader=reader)

    assert result.interrupted is True
    assert result.reports[0].partiel is True
    assert result.reports[0].frames_presentees < result.reports[0].frames_attendues
    # La capture et la fenetre sont liberees dans un `finally`.
    assert all(capture.released for capture in captures)
    assert sink.closed is True
    assert (tree_fingerprint(work_dir), tree_fingerprint(project_dir)) == before


def test_the_cli_interrupted_by_sigint_shows_no_python_traceback(
    tmp_path, monkeypatch, capsys
):
    video = tmp_path / "rush.mp4"
    video.write_bytes(b"fake")
    monkeypatch.setattr(
        video_metadata, "probe_media", lambda *args, **kwargs: probe_fixture()
    )

    def interrupting_prepare(**kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(cadence_previz, "prepare_previz", interrupting_prepare)

    code = cli.main(["previz", "--video", str(video), "--fps", "5", "--no-display"])
    captured = capsys.readouterr()

    assert code == 0
    assert "Traceback" not in captured.out + captured.err
    assert "aucun fichier ecrit" in captured.out.lower()


# --------------------------------------------------------------------------
# AC 1 et AC 9: surface CLI, codes de sortie, refus d'entrees
# --------------------------------------------------------------------------


def test_previz_refuses_a_project_option():
    """Cette commande ne connait pas la notion de projet."""
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["previz", "--project", "demo", "--video", "x.mov", "--fps", "5"])
    assert excinfo.value.code == 2


def test_missing_video_is_refused_before_any_reading(tmp_path, capsys):
    code = cli.main(
        ["previz", "--video", str(tmp_path / "absent.mov"), "--fps", "5",
         "--no-display"]
    )
    assert code == 1
    assert "introuvable" in capsys.readouterr().err


@pytest.mark.parametrize("fps", ["0", "-3"])
def test_non_positive_target_rate_is_refused(tmp_path, fps, capsys):
    video = tmp_path / "rush.mp4"
    video.write_bytes(b"fake")
    code = cli.main(
        ["previz", "--video", str(video), "--fps", fps, "--no-display"]
    )
    assert code == 1
    assert "strictement positif" in capsys.readouterr().err


def test_target_rate_above_source_rate_is_refused(tmp_path, monkeypatch, capsys):
    video = tmp_path / "rush.mp4"
    video.write_bytes(b"fake")
    monkeypatch.setattr(
        video_metadata, "probe_media", lambda *args, **kwargs: probe_fixture()
    )
    code = cli.main(
        ["previz", "--video", str(video), "--fps", "50", "--no-display"]
    )
    assert code == 1
    assert "sur-echantillonnage" in capsys.readouterr().err.lower()


def test_vfr_source_is_refused_with_the_very_message_of_extract(
    tmp_path, monkeypatch, capsys
):
    """AC 9: memes gardes, donc memes messages que `extract`."""
    video = tmp_path / "rush.mp4"
    video.write_bytes(b"fake")
    probe = probe_fixture(avg_frame_rate="20/1")
    monkeypatch.setattr(
        video_metadata, "probe_media", lambda *args, **kwargs: probe
    )

    with pytest.raises(extraction.ExtractionInputError) as expected:
        extraction.qualify_source(probe)

    code = cli.main(["previz", "--video", str(video), "--fps", "5", "--no-display"])
    captured = capsys.readouterr()

    assert code == 1
    assert str(expected.value) in captured.err


def test_missing_ffprobe_is_a_prerequisite_failure(tmp_path, monkeypatch, capsys):
    video = tmp_path / "rush.mp4"
    video.write_bytes(b"fake")

    def missing(*args, **kwargs):
        raise video_metadata.FfprobeNotFoundError("Binaire ffprobe introuvable")

    monkeypatch.setattr(video_metadata, "probe_media", missing)
    code = cli.main(["previz", "--video", str(video), "--fps", "5", "--no-display"])
    assert code == 2
    assert "ffprobe" in capsys.readouterr().err


def test_absent_display_is_a_prerequisite_failure(tmp_path, monkeypatch, capsys):
    video = tmp_path / "rush.mp4"
    video.write_bytes(b"fake")
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setattr(sys, "platform", "linux")

    code = cli.main(["previz", "--video", str(video), "--fps", "5"])
    captured = capsys.readouterr()

    assert code == 2
    assert DISPLAY_UNAVAILABLE in captured.err
    assert "cv2.error" not in captured.err


def test_display_detection_refuses_without_display_variable():
    with pytest.raises(DisplayUnavailableError):
        cadence_previz.ensure_display_available(environ={}, platform="linux")


def test_previz_never_creates_a_project_tree(tmp_path, monkeypatch, capsys):
    """AC 1: aucune arborescence, aucun `logs/`, aucun manifest."""
    work_dir = tmp_path / "cwd"
    work_dir.mkdir()
    monkeypatch.chdir(work_dir)
    video = tmp_path / "rush.mp4"
    video.write_bytes(b"fake")
    monkeypatch.setattr(
        video_metadata, "probe_media", lambda *args, **kwargs: probe_fixture()
    )
    monkeypatch.setattr(
        cadence_previz,
        "SequentialFrameReader",
        lambda *args, **kwargs: _FakeReader(make_frames(50)),
    )

    code = cli.main(
        ["previz", "--video", str(video), "--fps", "5", "--fps", "12.5",
         "--no-display"]
    )
    captured = capsys.readouterr()

    assert code == 0
    assert list(work_dir.rglob("*")) == []
    assert not (tmp_path / "logs").exists()
    assert "Aucun fichier ecrit" in captured.out


def test_cli_prints_a_report_per_cadence(tmp_path, monkeypatch, capsys):
    video = tmp_path / "rush.mp4"
    video.write_bytes(b"fake")
    monkeypatch.setattr(
        video_metadata, "probe_media", lambda *args, **kwargs: probe_fixture()
    )
    monkeypatch.setattr(
        cadence_previz,
        "SequentialFrameReader",
        lambda *args, **kwargs: _FakeReader(make_frames(50)),
    )

    code = cli.main(
        ["previz", "--video", str(video), "--fps", "5", "--fps", "12.5",
         "--no-display"]
    )
    out = capsys.readouterr().out

    assert code == 0
    assert "Cadence 5 im/s" in out
    assert "Cadence 12.5 im/s" in out
    assert out.isascii()


def test_no_file_handler_is_ever_attached_to_the_previz_logger():
    import logging

    logger = cli._configure_previz_logger()
    assert logger.handlers
    assert not any(
        isinstance(handler, logging.FileHandler) for handler in logger.handlers
    )


def test_defaults_are_the_ones_announced_by_the_story():
    assert DEFAULT_PREVIEW_HEIGHT == 540
    assert DEFAULT_MEMORY_BUDGET_MB > 0
    assert LATE_FRAME_TOLERANCE_S == 0.020
    assert LATE_FRAME_RATE_THRESHOLD == 0.01
    assert FINAL_DRIFT_RATIO_THRESHOLD == 0.02


# --------------------------------------------------------------------------
# Niveau 2: integration reelle (ffmpeg, OpenCV, Xvfb)
# --------------------------------------------------------------------------

SYNTHETIC_FRAME_COUNT = 50
SYNTHETIC_FPS = 25
SYNTHETIC_BASE = 10
SYNTHETIC_STEP = 4


def synthetic_value(index: int, *, base=SYNTHETIC_BASE, step=SYNTHETIC_STEP) -> int:
    return base + step * index


def build_synthetic_rush(
    directory: Path,
    *,
    frame_count=SYNTHETIC_FRAME_COUNT,
    fps=SYNTHETIC_FPS,
    base=SYNTHETIC_BASE,
    step=SYNTHETIC_STEP,
) -> Path:
    """Rush dont chaque frame porte une valeur de gris **distincte et exacte**.

    Codec `ffv1` en RGB, et non H.264: mesure faite ici, un H.264 dit
    « lossless » (`-qp 0 -pix_fmt yuv444p`) decale les valeurs de +/- 1 par la
    conversion de plage YUV, ce qui rendrait deux frames voisines
    indiscernables. Un test d'identite de frames ne peut pas reposer sur un
    codec qui deplace les valeurs.

    Conteneur `mov` et non `mkv`: depuis ARB-6 (`decisions-2026-08-05.md`), un
    conteneur qui ne declare ni la duree du flux ni son nombre d'images est
    refuse par `extract`, faute de pouvoir corroborer la cadence. Matroska est
    dans ce cas (mesure: `duration=N/A`, `nb_frames=N/A`), `mov` non
    (`duration=2.000000`, `nb_frames=50`). C'est la consequence assumee de
    l'arbitrage, et elle vaut aussi pour les rushs de test.
    """
    frames_dir = directory / "src-frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    import cv2

    for index in range(frame_count):
        image = np.full(
            (180, 320, 3), synthetic_value(index, base=base, step=step), dtype=np.uint8
        )
        cv2.imwrite(str(frames_dir / f"f_{index:04d}.png"), image)

    video_path = directory / "rush-synthetique.mov"
    command = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-framerate", str(fps),
        "-i", str(frames_dir / "f_%04d.png"),
        "-c:v", "ffv1", "-pix_fmt", "gbrp",
        str(video_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return video_path


@requires_ffmpeg
def test_opencv_sequential_index_matches_the_ffmpeg_select_index(tmp_path):
    """AC 3: l'hypothese porteuse de la voie retenue est verifiee, pas supposee."""
    import cv2

    video_path = build_synthetic_rush(tmp_path)
    probed = [0, 8, 16, 25, 33, 41]

    # 1. ce que ffmpeg -vf select rend pour ces indices.
    ffmpeg_values = []
    for index in probed:
        output = tmp_path / f"ffmpeg_{index}.png"
        command = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(video_path),
            "-vf", f"select=eq(n\\,{index})",
            "-frames:v", "1", "-update", "1",
            str(output),
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        ffmpeg_values.append(int(cv2.imread(str(output))[90, 160, 0]))

    # 2. ce que la lecture sequentielle d'OpenCV rend aux memes rangs.
    reader = SequentialFrameReader(video_path, height=None)
    opencv_values = [int(reader.frame_at(index)[90, 160, 0]) for index in probed]
    reader.close()

    assert opencv_values == ffmpeg_values
    # ... et ce sont bien les valeurs attendues, pas deux fois la meme erreur.
    assert opencv_values == [synthetic_value(index) for index in probed]


@requires_ffmpeg
def test_previz_and_extract_designate_the_same_images(tmp_path):
    """AC 2, bout en bout: memes timecodes que les fichiers ecrits par `extract`."""
    video_path = build_synthetic_rush(tmp_path)
    project_dir = tmp_path / "projet"

    code = cli.main(
        ["extract", "--project", str(project_dir), "--video", str(video_path),
         "--fps", "5", "--yes", "--accept-unknown-color"]
    )
    assert code == 0

    written = sorted(
        project_layout.extract_frames_dir_from_slug(
            project_dir, f"{video_path.stem}_5").glob("*.tif*")
    )
    assert written

    session = prepare_previz(video_path=video_path, fps_targets=[5.0])
    rush_id = normalize_identifier(video_path.stem, label="le nom du fichier source")
    previz_names = [
        build_extracted_frame_filename(rush_id, 5, frame.frame_timecode)
        for frame in session.schedules[0]
    ]

    # Les images designees par la previz sont exactement les fichiers ecrits.
    assert sorted(previz_names) == sorted(path.name for path in written)


@requires_ffmpeg
def test_previz_consumes_the_same_source_cardinal_as_extract(tmp_path):
    video_path = build_synthetic_rush(tmp_path)
    probe = video_metadata.probe_media(str(video_path))
    qualification = extraction.qualify_source(probe)
    expected_count, expected_exact = extraction.resolve_source_frame_count(
        video_path, qualification
    )

    session = prepare_previz(video_path=video_path, fps_targets=[3.0, 5.0, 12.5])

    assert session.source_frame_count == expected_count
    assert session.source_frame_count_is_exact is expected_exact
    assert session.fps_source == qualification.fps_source


@requires_ffmpeg
def test_no_display_playback_measures_real_time_on_a_real_rush(tmp_path):
    """Le chemin `--no-display` cadence reellement et mesure vraiment."""
    video_path = build_synthetic_rush(tmp_path)
    session = prepare_previz(video_path=video_path, fps_targets=[5.0])
    sink = NullSink()

    started = time.monotonic()
    result = play_cadences(session, sink=sink, height=DEFAULT_PREVIEW_HEIGHT)
    elapsed = time.monotonic() - started

    report = result.reports[0]
    assert report.frames_presentees == report.frames_attendues == 10
    # 50 frames a 25 im/s: la previz dure la duree du rush, pas 10/5 s de plus.
    assert elapsed == pytest.approx(report.duree_nominale_s, abs=0.6)
    assert report.temps_reel_tenu is True
    assert report.warnings == ()


def _start_xvfb() -> tuple[subprocess.Popen, str]:
    """Demarrer un Xvfb sur le premier numero d'ecran libre, et attendre qu'il reponde.

    Un numero d'ecran fige rendait ce test dependant de l'ordre et du rythme
    des executions: deux lancements rapproches se disputaient `:91`, le second
    capturait l'ecran du premier en train de s'eteindre, et l'echec ressemblait
    a une regression d'affichage (revue du 2026-08-05).
    """
    for number in range(91, 100):
        display = f":{number}"
        socket_path = Path("/tmp/.X11-unix") / f"X{number}"
        if socket_path.exists():
            continue
        process = subprocess.Popen(
            ["Xvfb", display, "-screen", "0", "1280x720x24"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            if socket_path.exists():
                return process, display
            if process.poll() is not None:
                break
            time.sleep(0.1)
        process.terminate()
        process.wait(timeout=10)
    raise AssertionError("aucun ecran Xvfb disponible entre :91 et :99")


def _dominant_non_black_value(image) -> int | None:
    """Valeur de gris la plus frequente hors fond noir, ou `None` si l'ecran est vide."""
    import numpy as _np

    non_black = image[image[:, :, 0] > 4]
    if non_black.size == 0:
        return None
    values, counts = _np.unique(non_black[:, 0], return_counts=True)
    return int(values[int(_np.argmax(counts))])


def _capture_display(display: str, output: Path) -> None:
    command = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "x11grab", "-video_size", "1280x720", "-i", f"{display}.0",
        "-frames:v", "1", "-update", "1", str(output),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@requires_xvfb
def test_a_real_window_shows_a_retained_frame_and_never_a_discarded_one(tmp_path):
    """AC 10, niveau 2: un lecteur qui n'affiche rien ne peut pas passer ce test."""
    import cv2

    # 100 frames a 10 im/s: dix secondes de lecture, largement de quoi capturer
    # l'ecran pendant que la fenetre affiche une frame retenue.
    frame_count, fps_source, base, step = 100, 10, 10, 2
    video_path = build_synthetic_rush(
        tmp_path, frame_count=frame_count, fps=fps_source, base=base, step=step
    )
    xvfb, display = _start_xvfb()
    previz = None
    previz_stderr = b""
    try:
        environment = dict(os.environ)
        environment["DISPLAY"] = display
        environment["PYTHONPATH"] = str(REPO_ROOT / "src")
        # Ce test mesure une **vraie fenetre** sur un vrai serveur X: il en
        # capture l'ecran avec `ffmpeg -f x11grab`. Un `QT_QPA_PLATFORM`
        # herite de l'appelant le contredit — et la recette documentee de la
        # suite complete exporte precisement `QT_QPA_PLATFORM=offscreen`.
        # Concretement, la previz mourait au demarrage sur « Could not find
        # the Qt platform plugin "offscreen" » (le repertoire de plugins Qt
        # embarque par cv2 masque celui de PySide6 et ne contient que `xcb`),
        # rendant ce test rouge en permanence des qu'on suivait la recette.
        # On retire donc la variable pour le sous-processus plutot que de la
        # subir: le serveur X de `_start_xvfb` est la, `xcb` est le bon
        # plugin. Ne pas remplacer par `= "xcb"`: si un jour l'appelant
        # tourne sans serveur X, l'absence de la variable laisse Qt echouer
        # avec un diagnostic exact, et `requires_xvfb` a deja saute le test.
        environment.pop("QT_QPA_PLATFORM", None)
        previz = subprocess.Popen(
            [
                sys.executable, "-m", "mixed_media_utility.cli", "previz",
                "--video", str(video_path), "--fps", "3", "--height", "360",
            ],
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        # Attendre que la fenetre ait reellement rendu, plutot qu'une duree
        # fixe: le demarrage de la previz comprend un `ffprobe -count_frames`
        # dont le cout depend de la charge de la machine. Un `sleep` calibre
        # sur une machine au repos rendait ce test intermittent des que la
        # suite complete tournait a cote (revue du 2026-08-05).
        # Toutes les valeurs qu'une frame du rush synthetique peut porter. Le
        # predicat d'attente doit reconnaitre **une frame**, et non « des
        # pixels non noirs »: le fond de fenetre Qt (valeur 239) satisfaisait
        # l'ancien seuil, si bien que le test pouvait capturer une fenetre
        # vide et conclure a une regression d'affichage (revue du 2026-08-05).
        toutes_les_frames = {
            synthetic_value(index, base=base, step=step) for index in range(frame_count)
        }

        capture_path = tmp_path / "capture.png"
        image = None
        displayed = None
        died = False
        deadline = time.monotonic() + 20.0
        while time.monotonic() < deadline:
            if previz.poll() is not None:
                died = True
                break
            _capture_display(display, capture_path)
            candidate = cv2.imread(str(capture_path))
            if candidate is not None:
                dominante = _dominant_non_black_value(candidate)
                if dominante in toutes_les_frames:
                    image = candidate
                    displayed = dominante
                    break
            time.sleep(0.25)
    finally:
        if previz is not None:
            previz.terminate()
            # Le journal de la previz est la seule explication disponible si la
            # fenetre ne rend rien: un echec muet ici serait indiagnosticable.
            previz_stderr = previz.communicate(timeout=10)[1] or b""
        xvfb.terminate()
        xvfb.wait(timeout=10)

    diagnostic = previz_stderr.decode(errors="replace")[-2000:]
    assert not died, f"la previz s'est arretee avant d'avoir rendu:\n{diagnostic}"
    assert image is not None and displayed is not None, (
        "aucune frame du rush n'a ete vue a l'ecran en 20 s "
        f"(fenetre vide ou previz muette):\n{diagnostic}"
    )

    retained = {
        synthetic_value(frame.source_index, base=base, step=step)
        for frame in select_source_frames(
            fps_source=fps_source, fps_target=3, source_frame_count=frame_count
        )
    }
    discarded = {
        synthetic_value(index, base=base, step=step) for index in range(frame_count)
    } - retained

    # L'assertion utile n'est pas « la capture n'est pas noire »: c'est que
    # l'image affichee est une frame RETENUE et jamais une frame ecartee.
    assert displayed in retained, (
        f"la valeur affichee ({displayed}) ne correspond a aucune frame retenue"
    )
    assert displayed not in discarded


# --------------------------------------------------------------------------
# Incrustation (revue du 2026-08-05): l'element specifie directement par le
# porteur de projet n'avait aucun test propre.
# --------------------------------------------------------------------------


def _presentation(*, window_position, t_real_s, fps_target=3.0, **overrides):
    champs = dict(
        fps_target=fps_target,
        output_rank=window_position,
        window_position=window_position,
        frames_attendues=30,
        source_index=window_position * 10,
        source_frame_count=500,
        lot_total_frames=30,
        frame_timecode="00:00:03:15",
        t_theo_s=window_position / fps_target,
        t_real_s=t_real_s,
        frames_omises=0,
    )
    champs.update(overrides)
    return PresentedFrame(**champs)


@pytest.mark.parametrize("position", [1, 2, 5, 10, 29])
def test_une_lecture_parfaitement_tenue_affiche_exactement_la_cadence_cible(position):
    """La cadence lue compte des intervalles, pas des frames.

    `t_real_s` part de la presentation de la **premiere** frame, donc n+1
    frames couvrent n intervalles. Diviser par le nombre de frames affichait
    `6.0/3` sur une lecture parfaitement tenue a 3 im/s, puis `4.5/3`, et ne
    s'approchait de 3 qu'asymptotiquement.
    """
    overlay = format_overlay(_presentation(window_position=position, t_real_s=position / 3.0))

    assert overlay.rate == "3/3 im/s"
    assert overlay.rate_on_target is True


@pytest.mark.parametrize("position", [1, 5, 29])
def test_une_lecture_deux_fois_trop_lente_est_dite_et_montree_en_rouge(position):
    overlay = format_overlay(_presentation(window_position=position, t_real_s=position / 1.5))

    assert overlay.rate == "1.5/3 im/s"
    assert overlay.rate_on_target is False


def test_la_premiere_image_n_affiche_aucune_cadence_inventee():
    """Aucun intervalle ecoule: la place est tenue par un tiret, pas par la cible.

    Afficher `3/3` presenterait comme une mesure ce qui n'en est pas une.
    """
    overlay = format_overlay(_presentation(window_position=0, t_real_s=0.0))

    assert overlay.rate == "-/3 im/s"
    assert overlay.rate_on_target is True


def test_la_cadence_affichee_ne_depasse_jamais_une_decimale():
    """Une ligne trop longue sort du champ sur une source etroite."""
    overlay = format_overlay(
        _presentation(window_position=41, t_real_s=3.28, fps_target=12.5)
    )

    partie_lue = overlay.rate.split("/")[0]
    assert len(partie_lue.split(".")[-1]) <= 1 or "." not in partie_lue
    assert overlay.rate.endswith("/12.5 im/s")


def test_les_deux_echelles_de_l_incrustation_ne_sont_jamais_melangees():
    """`idx X/Y` porte sur le rush source; le groupe de droite sur le lot."""
    overlay = format_overlay(
        _presentation(
            window_position=11,
            t_real_s=11 / 3.0,
            output_rank=11,
            source_index=87,
            source_frame_count=500,
            lot_total_frames=30,
        )
    )

    assert overlay.left == "00:00:03:15  idx 87/500"
    # Rang affiche en base un pour un lecteur humain, total du lot a droite.
    assert overlay.right == "12/30"


def test_le_bruit_d_horloge_ne_fait_pas_clignoter_la_couleur():
    """Quelques millisecondes de gigue ne sont pas un retard."""
    gigue = format_overlay(
        _presentation(window_position=30, t_real_s=10.0 + LATE_FRAME_TOLERANCE_S / 2)
    )

    assert gigue.rate_on_target is True


def test_la_couleur_ne_peut_pas_dire_le_contraire_du_rapport():
    """Revue du 2026-08-05: l'ecran restait vert sur une passe NON TENUE.

    La cadence affichee est une moyenne **cumulee**: elle lisse les a-coups,
    donc elle pouvait rester au-dessus du seuil pendant que le rapport
    comptait la frame comme en retard. Sur un rush 4K mesure par la revue,
    223 des 227 images capturees a l'ecran etaient vertes alors que le rapport
    concluait `temps reel NON TENU`. L'ecran est ce qui arbitre: il ne peut pas
    dire le contraire du rapport, donc le retard courant est juge avec la meme
    tolerance que `build_playback_report`.
    """
    # Cadence moyenne parfaite, mais cette image-la arrive franchement en
    # retard: c'est exactement le cas que la moyenne cumulee masquait.
    en_retard = _presentation(window_position=30, t_real_s=10.0, t_theo_s=10.0 - 0.113)

    overlay = format_overlay(en_retard)

    assert en_retard.lateness_s > LATE_FRAME_TOLERANCE_S
    assert overlay.rate_on_target is False


def test_l_incrustation_mesure_les_images_montrees_pas_les_echeances():
    """`--on-late skip`: `window_position` avance aussi sur les images omises.

    L'ecran annoncait `5/5 im/s` pendant que quatre images sur dix seulement
    etaient montrees: l'incrustation mesurait le programme, pas la lecture.
    """
    # Dix echeances ecoulees, six images omises: quatre intervalles montres.
    overlay = format_overlay(
        _presentation(
            window_position=10,
            t_real_s=10 / 5.0,
            fps_target=5.0,
            frames_omises=6,
        )
    )

    assert overlay.rate == "2/5 im/s"
    assert overlay.rate_on_target is False


def test_sauter_des_frames_ne_fait_pas_disparaitre_le_constat_de_non_tenue():
    """Revue du 2026-08-05: le mode `skip` effacait ce qu'il devait declencher.

    Une frame n'est omise que parce que son echeance est deja depassee. Ne
    rapporter le taux de retard qu'aux seules frames **presentees** revenait
    donc a supprimer la preuve en meme temps que le symptome: plus la lecture
    etait en retard, plus elle sautait de frames, et plus le verdict paraissait
    bon. A l'extreme, une frame presentee sur cent-cinquante donnait
    `temps reel : tenu`.
    """
    report, _ = _late_playback(ON_LATE_SKIP)

    assert report.frames_omises > 0
    assert report.temps_reel_tenu is False, (
        "une passe qui a du sauter des frames pour tenir l'horloge n'a "
        "precisement pas tenu la cadence"
    )
    assert REALTIME_NOT_HELD in report.warnings


def test_les_deux_politiques_de_retard_rendent_le_meme_verdict():
    """`--on-late` change ce qui est montre, jamais la verite sur la tenue."""
    rapport_skip, _ = _late_playback(ON_LATE_SKIP)
    rapport_report, _ = _late_playback(ON_LATE_REPORT)

    assert rapport_report.temps_reel_tenu is False
    assert rapport_skip.temps_reel_tenu == rapport_report.temps_reel_tenu
    assert REALTIME_NOT_HELD in rapport_skip.warnings
    assert REALTIME_NOT_HELD in rapport_report.warnings


def test_une_lecture_tenue_sans_omission_reste_tenue():
    """Le pendant: le correctif ne doit pas rendre le verdict pessimiste."""
    observations = [
        FrameObservation(output_rank=rank, source_index=rank * 10, t_theo_s=rank / 3, t_real_s=rank / 3)
        for rank in range(30)
    ]

    report = build_playback_report(
        observations,
        fps_target=3.0,
        frames_attendues=30,
        duree_nominale_s=10.0,
        frames_omises=0,
    )

    assert report.temps_reel_tenu is True
    assert REALTIME_NOT_HELD not in report.warnings


def test_l_incrustation_tient_dans_une_source_portrait():
    """Revue du 2026-08-05: le groupe de droite etait dessine hors champ.

    Sur une source portrait, la fleche restait centree et le rang dans le lot
    comme l'indicateur de tenue sortaient de l'image: l'information la plus
    utile disparaissait silencieusement.
    """
    import numpy as _np

    sink = CvWindowSink()
    presentation = _presentation(window_position=11, t_real_s=11 / 3.0)
    overlay = format_overlay(presentation)

    for largeur in (304, 320, 480, 1920):
        canvas = _np.zeros((540, largeur, 3), dtype=_np.uint8)
        dessine = sink._draw_overlay(canvas, presentation)

        assert dessine.shape == canvas.shape
        # La fin de la ligne (fleche + rang + cadence) doit rentrer.
        fin_de_ligne = (
            sink._ARROW_HALF_LENGTH * 2
            + sink._GROUP_GAP
            + sink._text_width(overlay.right)
            + sink._GROUP_GAP
            + sink._text_width(overlay.rate)
            + sink._MARGIN
        )
        assert fin_de_ligne <= largeur, (
            f"l'incrustation deborde d'une source de {largeur} px de large"
        )


def test_previz_et_extract_refusent_le_sur_echantillonnage_du_meme_mot(tmp_path):
    """ARB-12: le meme refus doit se lire de la meme facon dans les deux commandes."""
    from mixed_media_utility import extraction as extraction_module

    attendu = extraction_module.upsampling_refusal_message(30.0, Fraction(25))
    faux_rush = tmp_path / "rush.mov"
    faux_rush.write_bytes(b"peu importe: le probe est fourni")

    with pytest.raises(ExtractionInputError) as previz_exc:
        prepare_previz(
            video_path=faux_rush,
            fps_targets=[30.0],
            probe={
                "streams": [
                    {
                        "codec_type": "video",
                        "r_frame_rate": "25/1",
                        "avg_frame_rate": "25/1",
                        "duration": "4.0",
                        "nb_frames": "100",
                        "width": 320,
                        "height": 180,
                    }
                ],
                "format": {"tags": {}},
            },
        )

    assert str(previz_exc.value) == attendu


# --------------------------------------------------------------------------
# Story 3.7 -- bornes de timecode sur previz (AC 12, 13)
# --------------------------------------------------------------------------


PREVIZ_BORNE_IN = "00:00:01:00"   # index 30 a 30 im/s
PREVIZ_BORNE_OUT = "00:00:02:29"  # index 89: fenetre de 60 images


def _probe_borne() -> dict:
    """Probe minimal, 30 im/s sur 100 images: aucun binaire requis."""
    return {
        "streams": [
            {
                "codec_type": "video",
                "r_frame_rate": "30/1",
                "avg_frame_rate": "30/1",
                "duration": "3.333333",
                "nb_frames": "100",
                "width": 320,
                "height": 180,
            }
        ],
        "format": {"tags": {}},
    }


@pytest.fixture
def faux_rush(tmp_path) -> Path:
    chemin = tmp_path / "rush.mov"
    chemin.write_bytes(b"peu importe: le probe est fourni")
    return chemin


def test_previz_restreint_la_selection_par_les_memes_bornes_que_extract(faux_rush):
    """AC 12: le meme noyau, les memes parametres, aucune reimplementation."""
    session = prepare_previz(
        video_path=faux_rush,
        fps_targets=[5.0],
        probe=_probe_borne(),
        source_in_timecode=PREVIZ_BORNE_IN,
        source_out_timecode=PREVIZ_BORNE_OUT,
    )

    attendue = select_source_frames(
        fps_source=Fraction(30),
        fps_target=5.0,
        source_frame_count=100,
        source_in_timecode=PREVIZ_BORNE_IN,
        source_out_timecode=PREVIZ_BORNE_OUT,
        source_duration_seconds=3.333333,
    )
    assert session.selections[0].frames == attendue.frames
    assert [frame.source_index for frame in session.schedules[0]] == [
        frame.source_index for frame in attendue.frames
    ]


def test_les_bornes_et_la_fenetre_d_affichage_ne_font_pas_la_meme_chose(faux_rush):
    """AC 12, point non negociable: deux paires d'options, deux effets.

    `--start` / `--duration` choisissent ce qui est **joue** parmi les frames
    retenues; `--in` / `--out` choisissent ce qui est **retenu**. Les confondre
    montrerait a l'operateur des images que `extract` ne lui donnera jamais.
    """
    entiere = prepare_previz(
        video_path=faux_rush, fps_targets=[5.0], probe=_probe_borne()
    )
    affichage = prepare_previz(
        video_path=faux_rush,
        fps_targets=[5.0],
        probe=_probe_borne(),
        start_seconds=1.0,
        duration_seconds=1.0,
    )
    bornee = prepare_previz(
        video_path=faux_rush,
        fps_targets=[5.0],
        probe=_probe_borne(),
        source_in_timecode=PREVIZ_BORNE_IN,
        source_out_timecode=PREVIZ_BORNE_OUT,
    )

    # --start / --duration ne touchent pas a la selection, seulement a l'echeancier.
    assert affichage.selections[0].frames == entiere.selections[0].frames
    assert len(affichage.schedules[0]) < len(entiere.schedules[0])

    # --in / --out touchent la selection elle-meme.
    assert bornee.selections[0].frames != entiere.selections[0].frames
    assert bornee.selections[0].expected_frame_count < entiere.selections[0].expected_frame_count
    assert bornee.schedules[0][0].source_index == 30


def test_les_deux_paires_d_options_sont_combinables(faux_rush):
    """Une fenetre d'affichage a l'interieur d'un extrait reste licite."""
    session = prepare_previz(
        video_path=faux_rush,
        fps_targets=[5.0],
        probe=_probe_borne(),
        source_in_timecode=PREVIZ_BORNE_IN,
        source_out_timecode=PREVIZ_BORNE_OUT,
        start_seconds=1.5,
    )

    bornee_seule = prepare_previz(
        video_path=faux_rush,
        fps_targets=[5.0],
        probe=_probe_borne(),
        source_in_timecode=PREVIZ_BORNE_IN,
        source_out_timecode=PREVIZ_BORNE_OUT,
    )

    # La selection reste celle de l'extrait; seul l'echeancier est raccourci.
    assert session.selections[0].frames == bornee_seule.selections[0].frames
    assert len(session.schedules[0]) < len(bornee_seule.schedules[0])
    # `--start` se lit sur la ligne de temps du **rush**, pas sur celle de
    # l'extrait: 1,5 s a 30 im/s, c'est l'index 45 du fichier. Les instants de
    # presentation, eux, sont rebases a zero par `restrict_schedule` pour que
    # la lecture demarre sans ecran fixe -- ce sont les `source_index`, jamais
    # les `t_theo_s` rebases, qui temoignent de la ligne de temps d'origine.
    assert all(frame.source_index >= 45 for frame in session.schedules[0])
    assert session.schedules[0][0].t_theo_s == 0.0


def test_une_borne_invalide_est_refusee_par_previz_comme_par_extract(faux_rush):
    """AC 12: le refus vient du noyau, donc il est le meme des deux cotes.

    Meme classe et meme texte, sans que `previz` ne l'enrobe ni ne le
    reformule: `cli.py` mappe deja `FrameSelectionError` sur le code 1 pour les
    deux commandes.
    """
    from mixed_media_utility.frame_selection import InvalidBoundsError

    with pytest.raises(InvalidBoundsError) as previz_exc:
        prepare_previz(
            video_path=faux_rush,
            fps_targets=[5.0],
            probe=_probe_borne(),
            source_out_timecode="00:01:00:00",
        )

    with pytest.raises(InvalidBoundsError) as noyau_exc:
        select_source_frames(
            fps_source=Fraction(30),
            fps_target=5.0,
            source_frame_count=100,
            source_out_timecode="00:01:00:00",
        )

    assert str(previz_exc.value) == str(noyau_exc.value)


def test_l_incrustation_situe_la_frame_dans_le_rush_entier_meme_sur_un_extrait(
    faux_rush,
):
    """AC 13: `idx X/Y` reste le repere du rush, jamais celui de l'extrait.

    Decision explicite de la story: un operateur qui borne un extrait garde son
    repere de position dans le rush d'origine. Compter sur la fenetre lui
    ferait lire `idx 1/12` sur une image qui est la trentieme du rush.
    """
    session = prepare_previz(
        video_path=faux_rush,
        fps_targets=[5.0],
        probe=_probe_borne(),
        source_in_timecode=PREVIZ_BORNE_IN,
        source_out_timecode=PREVIZ_BORNE_OUT,
    )

    assert session.source_frame_count == 100, (
        "le cardinal reste celui du fichier, jamais celui de la fenetre"
    )

    premiere = session.schedules[0][0]
    overlay = format_overlay(
        _presentation(
            window_position=1,
            t_real_s=0.2,
            fps_target=5.0,
            output_rank=premiere.output_rank,
            source_index=premiere.source_index,
            source_frame_count=session.source_frame_count,
            lot_total_frames=session.selections[0].expected_frame_count,
            frame_timecode=premiere.frame_timecode,
        )
    )

    assert "idx 30/100" in overlay.left
    assert premiere.frame_timecode in overlay.left


def test_previz_sans_borne_est_inchangee(faux_rush):
    """AC 14: le chemin non borne ne bouge pas d'un pouce."""
    sans_argument = prepare_previz(
        video_path=faux_rush, fps_targets=[5.0], probe=_probe_borne()
    )
    avec_none = prepare_previz(
        video_path=faux_rush,
        fps_targets=[5.0],
        probe=_probe_borne(),
        source_in_timecode=None,
        source_out_timecode=None,
    )

    assert sans_argument.selections[0].frames == avec_none.selections[0].frames
    assert sans_argument.selections[0].frames == select_source_frames(
        fps_source=Fraction(30),
        fps_target=5.0,
        source_frame_count=100,
        source_duration_seconds=3.333333,
    ).frames


def test_la_ligne_de_commande_previz_transmet_les_bornes(faux_rush, monkeypatch):
    """AC 12 depuis le parseur: memes `dest=` que sur `extract`."""
    recus = {}

    def capture(**kwargs):
        recus.update(kwargs)
        raise ExtractionInputError("interruption volontaire du test")

    monkeypatch.setattr(cadence_previz, "prepare_previz", capture)

    code = cli.main(
        [
            "previz",
            "--video", str(faux_rush),
            "--fps", "5",
            "--no-display",
            "--in", PREVIZ_BORNE_IN,
            "--out", PREVIZ_BORNE_OUT,
        ]
    )

    assert code == 1
    assert recus["source_in_timecode"] == PREVIZ_BORNE_IN
    assert recus["source_out_timecode"] == PREVIZ_BORNE_OUT


def test_la_ligne_de_commande_previz_n_invente_aucune_borne(faux_rush, monkeypatch):
    recus = {}

    def capture(**kwargs):
        recus.update(kwargs)
        raise ExtractionInputError("interruption volontaire du test")

    monkeypatch.setattr(cadence_previz, "prepare_previz", capture)
    cli.main(["previz", "--video", str(faux_rush), "--fps", "5", "--no-display"])

    assert recus["source_in_timecode"] is None
    assert recus["source_out_timecode"] is None


@requires_ffmpeg
def test_previz_and_extract_designate_the_same_images_when_bounded(tmp_path):
    """AC 12: le test de jonction de la story 3.6, etendu a un extrait.

    Memes bornes des deux cotes sur le meme rush: les fichiers ecrits par
    `extract` et les images designees par `previz` doivent coincider image pour
    image. C'est le seul test qui echouerait si l'une des deux commandes
    calculait sa fenetre pour son compte.
    """
    video_path = build_synthetic_rush(tmp_path)
    project_dir = tmp_path / "projet"
    borne_in, borne_out = "00:00:00:10", "00:00:01:14"  # index 10 a 39, 25 im/s

    code = cli.main(
        ["extract", "--project", str(project_dir), "--video", str(video_path),
         "--fps", "5", "--yes", "--accept-unknown-color",
         "--in", borne_in, "--out", borne_out]
    )
    assert code == 0

    lots = [
        chemin
        for racine in project_layout.racines_de_frames_extraites(project_dir)
        for chemin in racine.iterdir()
        if chemin.is_dir()
    ]
    assert len(lots) == 1
    written = sorted(lots[0].glob("*.tif*"))
    assert written

    session = prepare_previz(
        video_path=video_path,
        fps_targets=[5.0],
        source_in_timecode=borne_in,
        source_out_timecode=borne_out,
    )
    rush_id = normalize_identifier(video_path.stem, label="le nom du fichier source")
    previz_names = [
        build_extracted_frame_filename(rush_id, 5, frame.frame_timecode)
        for frame in session.schedules[0]
    ]

    assert sorted(previz_names) == sorted(path.name for path in written)
    assert len(written) < SYNTHETIC_FRAME_COUNT // 5 + 1, (
        "un extrait doit compter moins d'images que le rush entier a la meme cadence"
    )


def test_une_fenetre_d_affichage_vide_dit_laquelle_des_deux_paires_est_en_cause(
    faux_rush,
):
    """Deux causes distinctes ne peuvent pas partager un seul diagnostic.

    Une plage `--start` vide sur un extrait n'a pas la meme cause qu'une plage
    vide sur le rush entier. Annoncer « la selection porte sur le rush entier »
    a un operateur qui vient de borner son extrait l'enverrait chercher son
    erreur du mauvais cote.
    """
    with pytest.raises(ExtractionInputError) as sur_extrait:
        prepare_previz(
            video_path=faux_rush,
            fps_targets=[5.0],
            probe=_probe_borne(),
            source_in_timecode=PREVIZ_BORNE_IN,
            source_out_timecode=PREVIZ_BORNE_OUT,
            start_seconds=3.2,
        )

    with pytest.raises(ExtractionInputError) as sur_rush_entier:
        prepare_previz(
            video_path=faux_rush,
            fps_targets=[5.0],
            probe=_probe_borne(),
            start_seconds=3.4,
        )

    assert "deja bornee a l'extrait" in str(sur_extrait.value)
    assert PREVIZ_BORNE_IN in str(sur_extrait.value)
    assert PREVIZ_BORNE_OUT in str(sur_extrait.value)
    assert "porte sur le rush entier" in str(sur_rush_entier.value)
    assert "deja bornee" not in str(sur_rush_entier.value)


def test_le_diagnostic_de_fenetre_vide_nomme_la_borne_reellement_fournie(faux_rush):
    """Une seule borne fournie ne doit pas en inventer une seconde."""
    with pytest.raises(ExtractionInputError) as exc:
        prepare_previz(
            video_path=faux_rush,
            fps_targets=[5.0],
            probe=_probe_borne(),
            source_in_timecode=PREVIZ_BORNE_IN,
            # 3,25 s: au-dela de la derniere frame retenue (index 96, t = 3,2 s)
            # sans sortir du rush, qui dure 3,33 s.
            start_seconds=3.25,
        )

    message = str(exc.value)
    assert f"{PREVIZ_BORNE_IN} -> fin du rush" in message


def test_l_incrustation_d_un_extrait_situe_bien_la_frame_dans_le_rush_joue():
    """AC 13, verrou reel: la valeur doit venir du code, pas du test.

    Revue du 2026-08-06. Le premier test de cet AC fabriquait lui-meme le
    `PresentedFrame` qu'il verifiait, en lui passant `session.source_frame_count`
    de sa propre main: il ne touchait jamais `_play_one_pass`, seul endroit ou
    ce cardinal est reellement choisi. L'auditeur a inverse cette ligne en
    `expected_frame_count` -- exactement la confusion que l'AC interdit -- et
    la suite complete est restee verte. Celui-ci passe par la lecture reelle.
    """
    session = make_session(
        fps_source=25,
        fps_targets=(5,),
        source_frame_count=500,
        source_in_timecode="00:00:04:00",   # index 100
        source_out_timecode="00:00:13:24",  # index 349
    )
    assert session.selections[0].expected_frame_count == 50

    clock = FakeClock()
    sink = RecordingSink(sleeper=clock.advance, keys=[KEY_QUIT])
    play_cadences(
        session,
        sink=sink,
        height=None,
        clock=clock,
        capture_factory=lambda: FakeCapture(make_frames(500), clock=clock),
    )

    premiere = sink.presented[0]
    assert premiere.source_index == 100
    assert premiere.source_frame_count == 500, (
        "le denominateur de `idx X/Y` est le cardinal du FICHIER, jamais celui "
        "de l'extrait: un operateur qui borne garde son repere dans le rush"
    )
    assert premiere.lot_total_frames == 50, "le groupe de droite, lui, dit le lot"
    assert format_overlay(premiere).left.endswith("idx 100/500")


def test_le_cardinal_affiche_ne_peut_pas_etre_celui_du_lot():
    """Le pendant du precedent: les deux echelles restent distinctes.

    Sur cet extrait, `expected_frame_count` (50) et `source_frame_count` (500)
    different d'un facteur dix. Une confusion entre les deux ne peut donc pas
    passer inapercue.
    """
    session = make_session(
        fps_source=25,
        fps_targets=(5,),
        source_frame_count=500,
        source_in_timecode="00:00:04:00",
        source_out_timecode="00:00:13:24",
    )
    clock = FakeClock()
    sink = RecordingSink(sleeper=clock.advance, keys=[KEY_QUIT])
    play_cadences(
        session,
        sink=sink,
        height=None,
        clock=clock,
        capture_factory=lambda: FakeCapture(make_frames(500), clock=clock),
    )

    for presentation in sink.presented:
        assert presentation.source_frame_count != presentation.lot_total_frames
        assert presentation.source_index >= 100


# --------------------------------------------------------------------------
# Story 11.4, lot K2 -- la lecture en boucle, et le temoin qui la dit
#
# Defaut trouve par Egan en testant le produit a la main le 2026-08-30: sur la
# fenetre de previz, `L` -- annonce comme « lecture en boucle » par la legende
# de l'atelier Extraction -- ne bouclait rien. Ce n'etait pas un probleme de
# casse: AUCUNE touche de boucle n'existait, et aucune notion de boucle non
# plus. La ligne d'aide annoncait une fonction jamais ecrite.
#
# Ce que `l` faisait REELLEMENT avant ce lot, et c'est pire que rien: comme
# toute touche non liee, elle tombait dans la branche par defaut de
# `play_cadences` et faisait avancer d'une cadence, exactement comme `n`.
# --------------------------------------------------------------------------


class SinkAvecTouchesEnVol(RecordingSink):
    """`RecordingSink` qui rend une touche PENDANT la passe, pas seulement au bout.

    `RecordingSink` ne sait rendre des touches que par `wait_for_key`,
    c'est-a-dire ENTRE deux passes. La bascule de boucle, elle, s'appuie au
    milieu de la lecture -- c'est meme la seule facon de couper une boucle deja
    lancee. Sans ce sink, aucun banc n'atteint le geste qu'Egan fait avec son
    doigt.

    Deux echeanciers, et ils ne mesurent pas la meme chose:

    * ``au_sondage`` -- la touche est rendue par ``poll_key``, c'est-a-dire
      APRES que l'attente de l'echeance est allee a son terme. C'est le regime
      nominal;
    * ``pendant_l_attente`` -- la touche est rendue par ``wait`` lui-meme, a
      mi-attente, comme le fait ``cv2.waitKey`` quand une touche arrive avant
      l'echeance. C'est le SEUL regime ou la reprise d'attente de
      ``_play_one_pass`` se voit: sans elle, l'image serait presentee en
      avance.

    Les deux sont indexes par le nombre d'images DEJA presentees dans la
    session, passes confondues: c'est la seule echelle que le sink observe, la
    passe ne se presentant pas a lui. Chaque entree ne sert qu'une fois
    (``pop``), sans quoi une reprise d'attente relirait la meme touche a
    l'infini.
    """

    #: Une boucle ARMEE et jamais coupee ne rend pas la main a `wait_for_key`:
    #: une regression -- ou un banc mal ecrit -- ne produit alors pas un echec
    #: mais une session sans fin, indiscernable d'une lenteur pour qui lit un
    #: rapport de banc. Ce plafond la transforme en echec NOMME. Il est large:
    #: le corpus le plus gourmand de cette section presente 41 images.
    PLAFOND_D_IMAGES = 200

    def __init__(self, *, au_sondage=None, pendant_l_attente=None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._au_sondage = dict(au_sondage or {})
        self._pendant_l_attente = dict(pendant_l_attente or {})

    def present(self, image, presentation) -> None:
        if len(self.presented) >= self.PLAFOND_D_IMAGES:
            raise AssertionError(
                f"plus de {self.PLAFOND_D_IMAGES} images presentees: la session "
                "reboucle sans jamais rendre la main au clavier"
            )
        super().present(image, presentation)

    def wait(self, seconds):
        touche = self._pendant_l_attente.pop(len(self.presented), None)
        if touche is None:
            return super().wait(seconds)
        if seconds > 0:
            self._sleeper(seconds / 2)
        return touche

    def poll_key(self):
        return self._au_sondage.pop(len(self.presented), None)


class _LecteurBorne(_FakeReader):
    """`_FakeReader` qui LEVE au-dela d'un nombre de lectures.

    Une regression de la garde « une passe qui n'a rien montre ne reboucle
    pas » ne produit pas un echec: elle produit une boucle infinie, qu'un banc
    ne peut pas distinguer d'une lenteur. La borne la transforme en echec
    immediat et NOMME.
    """

    def __init__(self, frames, *, plafond: int) -> None:
        super().__init__(frames)
        self._plafond = plafond

    def frame_at(self, source_index):
        if self.read_count >= self._plafond:
            raise AssertionError(
                f"plus de {self._plafond} acquisitions: la session reboucle sans "
                "jamais rendre la main au clavier"
            )
        return super().frame_at(source_index)


def _session_a_trois_cadences() -> cadence_previz.PrevizSession:
    """Trois cadences distinguables, et la CIBLE des tests est celle DU MILIEU.

    Regle des fabriques, point 2 et point 2 bis. Deux cadences ne suffisent
    pas: la seconde y est aussi la DERNIERE, et les deux fautes de terminaison
    de boucle -- « rejouer, c'est en fait avancer sur la derniere » et « le
    dernier tour ne compte pas » -- y sont indiscernables. Les trois cadences
    ont des cardinaux distincts (6, 10, 25 images retenues sur 50 sources), si
    bien qu'une passe rejouee ne peut pas passer pour une autre.
    """
    return make_session(fps_source=25, fps_targets=(3, 5, 12.5), source_frame_count=50)


def _jouer(session, sink, *, clock=None, reader=None):
    """Jouer une session sur un lecteur BORNE, toujours.

    Une regression de boucle ne se manifeste pas par un echec mais par une
    session qui ne finit jamais -- indiscernable d'une lenteur pour qui lit un
    rapport de banc. Le plafond la transforme en echec nomme. Il est large: le
    corpus le plus gourmand de cette section acquiert moins de cinquante
    images.
    """
    horloge = clock or FakeClock()
    return play_cadences(
        session,
        sink=sink,
        height=None,
        clock=horloge,
        reader=reader or _LecteurBorne(make_frames(50), plafond=400),
    )


def _cadences_jouees(resultat) -> list:
    return [round(report.fps_target, 3) for report in resultat.reports]


def test_la_touche_de_boucle_existe_et_c_est_la_LETTRE_NUE():
    """Consigne d'Egan du 2026-08-30, recopiee verbatim:

    « **La touche liee est la lettre NUE**, pas `maj+lettre` : `ord("l")`,
    jamais `ord("L")`. Egan a ete clair -- l'affichage se fait en majuscule
    pour la lisibilite, la touche liee est la minuscule. »

    Les deux moities comptent. `KEY_LOOP == ord("l")` seul laisserait passer un
    second liage de `ord("L")` « au cas ou »; c'est nommement ce que la
    consigne refuse sans motif ecrit en face.
    """
    assert KEY_LOOP == ord("l") == 108
    assert KEY_LOOP != ord("L")
    # `cv2.waitKey` masque a 8 bits sans normaliser la casse: les deux codes
    # sont distincts jusque dans le sink.
    assert ord("L") == 76
    # Aucune collision avec les quatre touches deja liees.
    assert len({KEY_LOOP, KEY_NEXT, KEY_PREVIOUS, KEY_REPLAY, KEY_QUIT}) == 5
    # Et le module n'en lie qu'une seule forme. La mesure porte sur les
    # constantes de CODE, docstrings exclues (`module_string_constants`): un
    # module qui EXPLIQUE pourquoi il ne lie pas `ord("L")` ne doit pas etre
    # puni comme un module qui le lie -- c'est le meme piege que les gardes de
    # `CAP_PROP_POS_FRAMES` plus haut dans ce fichier.
    assert "L" not in module_string_constants()
    assert "l" in module_string_constants(), (
        "la lettre minuscule doit etre liee, en code et pas seulement en prose"
    )


def test_L_MAJUSCULE_n_arme_AUCUNE_boucle():
    """Le volet symetrique du precedent, mesure sur le comportement.

    `L` majuscule garde le comportement qu'elle a toujours eu -- celui de
    n'importe quelle touche non liee: elle passe a la cadence suivante. Ce
    n'est pas un oubli, c'est l'etat que la consigne demande.
    """
    sink = SinkAvecTouchesEnVol(
        sleeper=FakeClock().advance,
        keys=[KEY_NEXT, KEY_QUIT],
        au_sondage={9: ord("L")},
    )
    resultat = _jouer(_session_a_trois_cadences(), sink)

    assert _cadences_jouees(resultat) == [3.0, 5.0], (
        "`L` majuscule a arme une boucle: la consigne lie la lettre NUE"
    )
    assert not any(image.loop_active for image in sink.presented)


def test_la_boucle_REJOUE_la_cadence_courante_au_lieu_de_passer_a_la_suivante():
    """Le defaut d'Egan, ferme: `l` boucle pour de vrai.

    La cible est la cadence DU MILIEU. Sur la premiere, « rejouer » et « rester
    la ou l'on est » sont indiscernables; sur la derniere, « rejouer » et
    « sortir de la boucle des cadences » le sont aussi.
    """
    sink = SinkAvecTouchesEnVol(
        sleeper=FakeClock().advance,
        keys=[KEY_NEXT, KEY_QUIT],
        # Passe 1 (3 im/s) = 6 images, passe 2 (5 im/s) = 10. On arme la boucle
        # a la 4e image de la passe 2, on la coupe pendant le rejeu.
        au_sondage={9: KEY_LOOP, 20: KEY_LOOP},
    )
    resultat = _jouer(_session_a_trois_cadences(), sink)

    assert _cadences_jouees(resultat) == [3.0, 5.0, 5.0], (
        "la passe a 5 im/s doit repartir sur elle-meme, pas ceder a 12,5"
    )
    # Et le rejeu est une passe ENTIERE, pas un moignon.
    assert resultat.reports[2].frames_attendues == resultat.reports[1].frames_attendues
    assert resultat.reports[2].frames_presentees == 10


def test_la_boucle_s_arme_AUSSI_en_FIN_de_passe_sans_manger_une_touche_de_plus():
    """`l` presse quand la passe est finie arme la boucle ET relance aussitot.

    La bascule VAUT la reponse. Si `l` en fin de passe se contentait d'armer
    puis redemandait une touche, l'operateur devrait appuyer deux fois pour un
    seul geste -- et la seconde frappe serait invisible dans la legende.
    """
    sink = SinkAvecTouchesEnVol(
        sleeper=FakeClock().advance,
        keys=[KEY_NEXT, KEY_LOOP, KEY_QUIT],
        au_sondage={20: KEY_LOOP},
    )
    resultat = _jouer(_session_a_trois_cadences(), sink)

    assert _cadences_jouees(resultat) == [3.0, 5.0, 5.0]


def test_la_bascule_COUPE_la_boucle_et_la_session_reprend_son_cours():
    """Une bascule qui ne bascule qu'une fois est un verrou, pas une bascule."""
    sink = SinkAvecTouchesEnVol(
        sleeper=FakeClock().advance,
        keys=[KEY_NEXT, KEY_QUIT],
        au_sondage={9: KEY_LOOP, 20: KEY_LOOP},
    )
    _jouer(_session_a_trois_cadences(), sink)

    etats = [image.loop_active for image in sink.presented]
    # Passe 1 (6 images) coupee, puis 5 im/s: coupee jusqu'a la 4e image,
    # armee ensuite, et coupee de nouveau au milieu du rejeu.
    assert etats[:6] == [False] * 6
    assert etats[6:9] == [False, False, False]
    assert etats[9:16] == [True] * 7
    assert True in etats and False in etats[16:], (
        "la seconde frappe n'a pas coupe la boucle"
    )


def test_q_sort_d_une_boucle_ARMEE():
    """Une boucle dont on ne sort pas n'est pas une fonction, c'est un piege."""
    sink = SinkAvecTouchesEnVol(
        sleeper=FakeClock().advance,
        keys=[KEY_NEXT],
        au_sondage={9: KEY_LOOP, 20: KEY_QUIT},
    )
    resultat = _jouer(_session_a_trois_cadences(), sink)

    assert _cadences_jouees(resultat) == [3.0, 5.0, 5.0]
    # `q` a coupe le rejeu en cours: la troisieme passe est partielle.
    assert resultat.reports[2].partiel is True
    assert resultat.reports[2].frames_presentees < 10


def test_la_bascule_en_vol_n_INTERROMPT_pas_la_passe():
    """`l` bascule un etat; elle ne clot pas la passe comme `n`, `p`, `r` ou `q`."""
    sink = SinkAvecTouchesEnVol(
        sleeper=FakeClock().advance,
        keys=[KEY_QUIT],
        # Armee a la 3e image, coupee a la 5e: la passe en compte 6, et la
        # boucle est donc rendue COUPEE a la fin -- sans quoi le banc
        # rebouclerait indefiniment, ce qui est la preuve que la boucle marche
        # mais pas un test.
        au_sondage={2: KEY_LOOP, 4: KEY_LOOP},
    )
    session = make_session(fps_source=25, fps_targets=(3,), source_frame_count=50)
    resultat = _jouer(session, sink)

    assert [image.loop_active for image in sink.presented] == [
        False, False, True, True, False, False
    ]

    rapport = resultat.reports[0]
    assert rapport.frames_presentees == rapport.frames_attendues == 6
    assert rapport.partiel is False, (
        "une bascule de boucle a ete comptee comme une sortie volontaire"
    )


def test_la_bascule_en_vol_ne_presente_pas_l_image_EN_AVANCE():
    """`sink.wait` rend la main DES la premiere touche: l'attente doit reprendre.

    C'est la seule chose que la bascule pouvait casser dans ce module: sans
    reprise, l'image en cours serait montree a mi-echeance, et la mesure du
    temps reel -- l'unique livrable de la commande -- deviendrait fausse pile
    au moment ou l'operateur touche le clavier.
    """
    horloge = FakeClock()
    sink = SinkAvecTouchesEnVol(
        sleeper=horloge.advance,
        keys=[KEY_QUIT],
        pendant_l_attente={3: KEY_LOOP},
        # Coupee apres la mesure: la passe doit finir COUPEE pour que le banc
        # finisse tout court.
        au_sondage={6: KEY_LOOP},
    )
    session = make_session(fps_source=25, fps_targets=(5,), source_frame_count=50)
    _jouer(session, sink, clock=horloge)

    basculee = sink.presented[3]
    assert basculee.loop_active is True, "la touche n'a pas ete lue pendant l'attente"
    assert basculee.t_real_s == pytest.approx(basculee.t_theo_s, abs=1e-9), (
        "l'image de la bascule est arrivee en avance: l'attente n'a pas repris"
    )
    # Et l'echeance etant absolue, la suivante n'a pas derive non plus.
    assert sink.presented[4].t_real_s == pytest.approx(
        sink.presented[4].t_theo_s, abs=1e-9
    )


def test_une_passe_qui_n_a_RIEN_montre_ne_reboucle_pas_a_vide():
    """Un flux tronque des la premiere image n'appelle jamais `poll_key`.

    Rebouclee, une telle passe ne laisserait a l'operateur aucune occasion
    d'appuyer sur quoi que ce soit. Le lecteur borne transforme la regression
    -- une boucle infinie -- en echec nomme.
    """
    lecteur = _LecteurBorne([], plafond=12)
    sink = RecordingSink(sleeper=FakeClock().advance, keys=[KEY_LOOP, KEY_QUIT])

    resultat = _jouer(_session_a_trois_cadences(), sink, reader=lecteur)

    # `l` a arme la boucle, mais la passe n'ayant rien montre, la main est
    # rendue au clavier et la session avance jusqu'au `q`.
    assert len(resultat.reports) == 2
    assert all(report.frames_presentees == 0 for report in resultat.reports)


# --------------------------------------------------------------------------
# Le temoin: une bascule sans temoin est un etat cache (demande nommement par
# Egan, 2026-08-30)
# --------------------------------------------------------------------------


def test_l_incrustation_DIT_l_etat_de_la_boucle_dans_LES_DEUX_SENS():
    """Les deux etats ont un libelle. Aucun n'est le silence."""
    coupee = format_overlay(_presentation(window_position=11, t_real_s=11 / 3.0))
    armee = format_overlay(
        _presentation(window_position=11, t_real_s=11 / 3.0, loop_active=True)
    )

    assert coupee.loop == OVERLAY_LOOP_OFF == "boucle off"
    assert armee.loop == OVERLAY_LOOP_ON == "boucle on"
    assert coupee.loop != armee.loop
    assert coupee.loop and armee.loop, "un temoin vide n'est pas un temoin"
    # Convention du module: incrustation ASCII, sans accent.
    for libelle in (OVERLAY_LOOP_ON, OVERLAY_LOOP_OFF):
        assert libelle.isascii()


def test_le_temoin_est_REELLEMENT_DESSINE_dans_la_fenetre():
    """`format_overlay` peut dire vrai et le rendu ne rien peindre.

    La mesure porte donc sur les PIXELS: les deux etats doivent produire deux
    images differentes, a toutes les largeurs du corpus.
    """
    import numpy as _np

    sink = CvWindowSink()
    for largeur in (304, 320, 480, 720, 960, 1920):
        canvas = _np.zeros((540, largeur, 3), dtype=_np.uint8)
        coupee = sink._draw_overlay(
            canvas, _presentation(window_position=11, t_real_s=11 / 3.0)
        )
        armee = sink._draw_overlay(
            canvas,
            _presentation(window_position=11, t_real_s=11 / 3.0, loop_active=True),
        )
        assert not _np.array_equal(coupee, armee), (
            f"a {largeur} px de large, les deux etats de boucle sont dessines "
            "a l'identique: le temoin n'existe pas a l'ecran"
        )


def test_le_temoin_de_boucle_reste_DANS_l_image_a_TOUTE_largeur():
    """Un temoin dessine hors champ ne temoigne de rien.

    Pose au fil du texte, `boucle off` commencait a 518 px sur une source de
    480 px de large: invisible, sans que rien ne le dise. C'est le defaut que
    la revue du 2026-08-05 avait deja paye sur le groupe de droite, et il ne se
    voit qu'en regardant OU les pixels tombent.
    """
    import numpy as _np

    sink = CvWindowSink()
    for largeur in (304, 320, 480, 720, 960, 1920):
        canvas = _np.zeros((540, largeur, 3), dtype=_np.uint8)
        coupee = sink._draw_overlay(
            canvas, _presentation(window_position=11, t_real_s=11 / 3.0)
        )
        armee = sink._draw_overlay(
            canvas,
            _presentation(window_position=11, t_real_s=11 / 3.0, loop_active=True),
        )
        colonnes = _np.argwhere(coupee != armee)[:, 1]
        assert colonnes.size > 0
        assert 0 <= int(colonnes.min()), largeur
        assert int(colonnes.max()) < largeur, (
            f"le temoin deborde d'une source de {largeur} px de large"
        )


def test_la_fin_de_ligne_TEMOIN_COMPRIS_tient_dans_une_source_portrait():
    """Le pendant de `test_l_incrustation_tient_dans_une_source_portrait`.

    Le temoin entre dans le budget du groupe de droite. Les deux libelles sont
    mesures a 90 px et 92 px pour un budget de 98 px sur la source la plus
    etroite du depot: `boucle ON` (94) passait, `boucle OFF` (102) sortait --
    c'est ce qui a decide de la casse des deux mots, et le test le fige.
    """
    sink = CvWindowSink()
    for loop_active in (False, True):
        overlay = format_overlay(
            _presentation(
                window_position=11, t_real_s=11 / 3.0, loop_active=loop_active
            )
        )
        fin_de_ligne = (
            sink._ARROW_HALF_LENGTH * 2
            + sink._GROUP_GAP
            + sink._text_width(overlay.right)
            + sink._GROUP_GAP
            + sink._text_width(overlay.rate)
            + sink._GROUP_GAP
            + sink._text_width(overlay.loop)
            + sink._MARGIN
        )
        assert fin_de_ligne <= 304, (
            f"{overlay.loop!r} pousse la fin de ligne a {fin_de_ligne} px, hors "
            "d'une source portrait de 304 px"
        )


# --------------------------------------------------------------------------
# Ce qui NE change pas: le parcours `mmu previz`
# --------------------------------------------------------------------------


def test_la_boucle_est_COUPEE_par_defaut_et_le_parcours_CLI_est_INCHANGE():
    """Aucune touche de boucle: la session est celle d'avant, image par image.

    Mesure sur les DEUX regimes de sink -- non interactif (`--no-display`,
    donc toute session d'integration continue) et interactif -- et sur la
    sequence d'indices sources, pas sur un compte.
    """
    attendue = [
        frame.source_index
        for cadence in (3, 5, 12.5)
        for frame in select_source_frames(
            fps_source=25, fps_target=cadence, source_frame_count=50
        ).frames
    ]

    muet = NullSink(sleeper=FakeClock().advance)
    _jouer(_session_a_trois_cadences(), muet)
    assert [image.source_index for image in muet.presented] == attendue
    assert not any(image.loop_active for image in muet.presented)

    bavard = RecordingSink(
        sleeper=FakeClock().advance, keys=[KEY_NEXT, KEY_NEXT, KEY_QUIT]
    )
    resultat = _jouer(_session_a_trois_cadences(), bavard)
    assert [image.source_index for image in bavard.presented] == attendue
    assert _cadences_jouees(resultat) == [3.0, 5.0, 12.5]
    assert not any(image.loop_active for image in bavard.presented)
    # Et l'incrustation le DIT, sur chaque image.
    assert {format_overlay(image).loop for image in bavard.presented} == {
        OVERLAY_LOOP_OFF
    }


@pytest.mark.parametrize(
    "touche, attendu, annonce",
    [
        (KEY_NEXT, [3.0, 5.0], "n suivante"),
        (KEY_PREVIOUS, [3.0, 3.0], "p precedente"),
        (KEY_REPLAY, [3.0, 3.0], "r relire"),
    ],
)
def test_les_TROIS_AUTRES_touches_font_ce_que_la_legende_annonce(
    touche, attendu, annonce
):
    """Une fausse promesse trouvee vaut la peine de verifier ses voisines.

    Elles tiennent toutes les trois. Une reserve mesuree, qui n'est pas un
    defaut mais explique le defaut d'a cote: `n` n'a pas de branche a elle --
    c'est la branche PAR DEFAUT de `play_cadences` qui avance. Toute touche non
    liee avancait donc comme `n`, `l` la premiere. C'est exactement ce qui
    faisait qu'un raccourci annonce et jamais ecrit n'etait pas inerte mais
    trompeur.
    """
    sink = RecordingSink(sleeper=FakeClock().advance, keys=[touche, KEY_QUIT])
    resultat = _jouer(_session_a_trois_cadences(), sink)

    assert _cadences_jouees(resultat) == attendu, annonce


def test_l_avance_PAR_DEFAUT_ne_couvre_plus_la_touche_de_boucle():
    """Le volet symetrique de la reserve ci-dessus, et la regression a interdire.

    Avant ce lot, `l` en fin de passe avancait d'une cadence, comme `n`. C'est
    le comportement exact qu'une reintroduction de la branche par defaut
    ramenerait, et il est ici mesure a l'envers: la SECONDE passe doit etre la
    premiere cadence rejouee, jamais la suivante.
    """
    sink = SinkAvecTouchesEnVol(
        sleeper=FakeClock().advance,
        keys=[KEY_LOOP],
        # Passe 1 a 3 im/s = 6 images; on coupe court au troisieme tour du
        # rejeu, sans quoi la boucle -- qui fonctionne -- ne finirait pas.
        au_sondage={8: KEY_QUIT},
    )
    resultat = _jouer(_session_a_trois_cadences(), sink)

    assert _cadences_jouees(resultat) == [3.0, 3.0], (
        "`l` a avance d'une cadence: elle est retombee dans la branche par defaut"
    )
    # Une touche restee non liee, elle, avance toujours: la branche par defaut
    # n'a pas disparu, c'est `l` qui en est sortie.
    autre = RecordingSink(sleeper=FakeClock().advance, keys=[ord("z"), KEY_QUIT])
    assert _cadences_jouees(_jouer(_session_a_trois_cadences(), autre)) == [3.0, 5.0]


# --------------------------------------------------------------------------
# Lot K2, reprise du survivant `M17` de la campagne d'injection
#
# `M17` -- le temoin retire du budget du groupe de droite -- a SURVECU au
# premier tour. Il disait vrai : le temoin etait pose au fil du texte puis
# borne au bord droit, si bien qu'il venait se peindre PAR-DESSUS la cadence
# des que la ligne serrait, et aucun banc ne mesurait autre chose que « il est
# dans l'image ». Le trace pose desormais les trois elements depuis un SEUL
# point d'ancrage borne, et la geometrie est extraite pour etre mesurable.
# --------------------------------------------------------------------------


#: Le corpus de largeurs, de la source portrait la plus etroite du depot
#: (9:16 rendu a `DEFAULT_PREVIEW_HEIGHT`) a l'UHD. Aucune n'est declaree
#: « rentre » ou « ne rentre pas » ici : le critere est CALCULE ci-dessous.
#: Une liste figee l'aurait ete sur la longueur d'un timecode -- piege paye en
#: ecrivant ce banc, ou `idx 87/500` et `idx 110/500` ne basculent pas a la
#: meme largeur.
LARGEURS_DU_CORPUS = [304, 320, 400, 440, 480, 520, 560, 640, 720, 960, 1920]


def _la_ligne_rentre(sink, overlay, largeur) -> bool:
    """La ligne ENTIERE tient-elle dans cette largeur ?

    Marge + zone gauche + creux + fleche + creux + groupe de droite + marge.
    """
    return (
        sink._MARGIN
        + sink._text_width(overlay.left)
        + sink._GROUP_GAP
        + 2 * sink._ARROW_HALF_LENGTH
        + sink._GROUP_GAP
        + sink._largeur_du_groupe_de_droite(overlay)
        + sink._MARGIN
    ) <= largeur


def _geometrie(sink, overlay, largeur, center_x):
    left_end_x = sink._MARGIN + sink._text_width(overlay.left) + sink._GROUP_GAP
    return sink._positions_du_groupe_de_droite(
        overlay, largeur, left_end_x, center_x
    )


def _toutes_les_positions_de_fleche(sink, overlay, largeur):
    """Toutes les abscisses de fleche que le trace peut produire, pas « la » bonne.

    Recalculer le centrage dans le banc en ferait une tautologie : le mutant
    changerait les deux cotes de l'egalite a la fois, mode de panne paye par le
    mutant `M20` du lot J. La propriete mesuree ici -- le temoin ne mord pas la
    cadence -- ne depend PAS du centrage, donc on la mesure sur toute la plage.
    """
    left_end_x = sink._MARGIN + sink._text_width(overlay.left) + sink._GROUP_GAP
    depart = left_end_x + sink._ARROW_HALF_LENGTH
    return range(depart, max(depart + 1, largeur), 7)


@pytest.mark.parametrize("loop_active", [False, True])
def test_le_temoin_ne_se_peint_JAMAIS_par_dessus_la_cadence(loop_active):
    """Un temoin illisible ne vaut pas mieux qu'un temoin hors champ.

    Mesure du survivant `M17` : le temoin etait pose au fil du texte puis borne
    au bord droit, sans que le groupe recule pour lui. A 520 px de large, la
    cadence finissait a 428 px et le temoin commencait a 414 : les deux etaient
    « dans l'image » -- tout ce que le banc mesurait -- et l'un etait ecrit sur
    l'autre.
    """
    sink = CvWindowSink()
    overlay = format_overlay(
        _presentation(window_position=11, t_real_s=11 / 3.0, loop_active=loop_active)
    )

    mesurees = 0
    for largeur in LARGEURS_DU_CORPUS:
        if not _la_ligne_rentre(sink, overlay, largeur):
            continue
        mesurees += 1
        for center_x in _toutes_les_positions_de_fleche(sink, overlay, largeur):
            _rang, x_cadence, x_temoin = _geometrie(sink, overlay, largeur, center_x)
            fin_de_la_cadence = x_cadence + sink._text_width(overlay.rate)
            assert x_temoin >= fin_de_la_cadence + sink._GROUP_GAP, (
                f"a {largeur} px et fleche en {center_x}, le temoin commence en "
                f"{x_temoin} alors que la cadence finit en {fin_de_la_cadence}"
            )
            assert x_temoin + sink._text_width(overlay.loop) <= (
                largeur - sink._MARGIN
            )

    assert mesurees >= 4, (
        "le corpus ne mesure plus rien : aucune largeur ou la ligne rentre"
    )


@pytest.mark.parametrize("loop_active", [False, True])
def test_le_corpus_porte_AUSSI_des_largeurs_ou_la_ligne_ne_rentre_pas(loop_active):
    """Volet symetrique du precedent : son `continue` doit avoir de quoi sauter.

    Sans cette mesure, un corpus qui ne porterait plus que des sources larges
    rendrait le test ci-dessus vert sans jamais approcher le regime serre -- et
    c'est precisement le regime ou `M17` mordait.
    """
    sink = CvWindowSink()
    overlay = format_overlay(
        _presentation(window_position=11, t_real_s=11 / 3.0, loop_active=loop_active)
    )

    trop_etroites = [
        largeur
        for largeur in LARGEURS_DU_CORPUS
        if not _la_ligne_rentre(sink, overlay, largeur)
    ]
    assert len(trop_etroites) >= 3, trop_etroites


@pytest.mark.parametrize("loop_active", [False, True])
def test_le_temoin_reste_DANS_l_image_meme_quand_la_ligne_ne_rentre_pas(loop_active):
    """Sur une source trop etroite, le lot ne promet plus qu'une chose -- et il
    la tient : le temoin ne sort pas de l'image.

    Le debordement de la ligne y est ANTERIEUR au temoin -- il touche deja le
    rang dans le lot et la cadence (revue du 2026-08-05) -- et le lot K2 ne le
    corrige pas ; il promet de ne pas en ajouter un de plus.
    """
    sink = CvWindowSink()
    overlay = format_overlay(
        _presentation(window_position=11, t_real_s=11 / 3.0, loop_active=loop_active)
    )

    for largeur in LARGEURS_DU_CORPUS:
        for center_x in _toutes_les_positions_de_fleche(sink, overlay, largeur):
            _rang, _cadence, x_temoin = _geometrie(sink, overlay, largeur, center_x)
            assert x_temoin >= sink._MARGIN, largeur
            assert x_temoin + sink._text_width(overlay.loop) <= (
                largeur - sink._MARGIN
            ), largeur


def test_la_largeur_du_groupe_de_droite_a_UNE_seule_redaction():
    """Elle sert deux fois -- reculer la fleche, borner l'ancrage -- et le lot J
    a deja paye ce que coutent deux redactions du meme calcul.

    La mesure est une egalite : la largeur rendue vaut exactement la somme des
    trois textes et de leurs deux creux, temoin COMPRIS.
    """
    sink = CvWindowSink()
    overlay = format_overlay(
        _presentation(window_position=11, t_real_s=11 / 3.0, loop_active=True)
    )

    assert sink._largeur_du_groupe_de_droite(overlay) == (
        sink._text_width(overlay.right)
        + sink._GROUP_GAP
        + sink._text_width(overlay.rate)
        + sink._GROUP_GAP
        + sink._text_width(overlay.loop)
    )
    # Et le temoin y pese vraiment : l'oublier retire sa largeur entiere.
    assert sink._largeur_du_groupe_de_droite(overlay) - sink._text_width(
        overlay.loop
    ) - sink._GROUP_GAP == (
        sink._text_width(overlay.right)
        + sink._GROUP_GAP
        + sink._text_width(overlay.rate)
    )


# ---------------------------------------------------------------------------
# Le garde << cette roue d'OpenCV sait-elle afficher ? >>
# ---------------------------------------------------------------------------


class _CvDeSynthese:
    """Un faux `cv2` qui ne porte QUE ce que le garde a le droit de regarder."""

    def __init__(self, information):
        self._information = information

    def getBuildInformation(self):
        if self._information is None:
            raise RuntimeError("cette roue ne rend pas d'information de build")
        return self._information

    # `imshow` est TOUJOURS present, y compris sur une roue headless : c'est
    # tout le sujet de ce bloc de bancs.
    def imshow(self, *_a, **_k):  # pragma: no cover - jamais appele ici
        raise AssertionError("le garde ne doit jamais APPELER imshow")


_ENTETE = "General configuration for OpenCV 5.0.0\n  Other third-party:\n"


@pytest.mark.parametrize("ligne_gui, attendu", [
    ("  GUI:                           NONE", False),
    ("  GUI:                           GTK+ 3.x", True),
    ("  GUI:                           COCOA", True),
    ("  GUI:                           WIN32UI", True),
    ("  GUI:                           QT5", True),
    ("  GUI:", False),
])
def test_le_garde_lit_la_CAPACITE_et_non_la_presence(monkeypatch, ligne_gui, attendu):
    """Le garde doit repondre sur la ligne `GUI:` du rapport de compilation.

    **Ce banc ferme un defaut reel, mesure le 2026-09-06.** Le garde d'origine
    testait `hasattr(cv2, "imshow")`. Or `hasattr` rend **True** sur la roue
    headless -- le symbole existe, c'est l'appel qui leve
    `cv2.error: The function is not implemented`. Le garde ne s'est donc jamais
    declenche, et le refus lisible qu'il devait produire n'a jamais existe :
    l'utilisateur recevait une erreur OpenCV brute a la place.

    Le faux `cv2` ci-dessus porte `imshow`, exactement comme la vraie roue
    headless : un garde revenu a `hasattr` rendrait `True` sur les six cas et
    ce banc rougirait sur le premier.
    """
    monkeypatch.setattr(cadence_previz, "cv2", _CvDeSynthese(_ENTETE + ligne_gui))
    assert cadence_previz._opencv_sait_afficher() is attendu


def test_le_garde_est_PERMISSIF_quand_l_information_manque(monkeypatch):
    """Sans ligne `GUI:` exploitable, on laisse passer -- et c'est deliberé.

    Un faux refus retire a l'utilisateur une fonctionnalite qui marche ; un faux
    passage retombe sur le refus suivant, qui est deja ecrit et lisible. Les
    deux erreurs ne coutent donc pas la meme chose, et le repli penche du cote
    le moins cher.
    """
    assert cadence_previz._opencv_sait_afficher.__doc__
    monkeypatch.setattr(cadence_previz, "cv2", _CvDeSynthese(_ENTETE + "  Parallel: TBB"))
    assert cadence_previz._opencv_sait_afficher() is True
    monkeypatch.setattr(cadence_previz, "cv2", _CvDeSynthese(None))
    assert cadence_previz._opencv_sait_afficher() is True


def test_une_roue_headless_REFUSE_en_nommant_les_deux_issues(monkeypatch):
    """Le refus doit porter le code, et deux issues -- jamais un blocage sec.

    `EPIC11-ARB-89` : « toujours proposer au moins deux issues ». Ici : mesurer
    sans fenetre, ou remplacer la roue. La commande de remplacement est ecrite
    en entier parce qu'elle n'est pas devinable -- `opencv-python` REMPLACE
    `opencv-python-headless` au lieu de s'y ajouter, les deux publiant le meme
    module `cv2`.
    """
    monkeypatch.setattr(cadence_previz, "cv2", _CvDeSynthese(_ENTETE + "  GUI: NONE"))
    with pytest.raises(cadence_previz.DisplayUnavailableError) as refus:
        cadence_previz.ensure_display_available(
            environ={"DISPLAY": ":0"}, platform="darwin")
    rendu = str(refus.value)
    assert DISPLAY_UNAVAILABLE in rendu
    assert "headless" in rendu
    assert "pipx inject --force mmu-tui opencv-python" in rendu
    assert "libGL" in rendu


# --------------------------------------------------------------------------
# La garde du niveau 2 nomme ses TROIS prerequis (2026-09-08).
#
# Trouve par le run de CI 34198324696, le premier a jouer ce banc sur une
# machine qui n'est pas un conteneur de developpement. La garde en nommait
# deux -- `Xvfb` et `ffmpeg` -- et le troisieme, une roue OpenCV capable
# d'afficher, est ne le 2026-09-06 avec `EPIC11-ARB-253` sans que la garde le
# suive. Meme famille que « un module porte sans sa mesure », et meme famille
# que la regle CLAUDE.md « une garde fait VARIER le drapeau dont elle depend » :
# ici le drapeau existait, la garde ne le lisait pas.
#
# Mesure des deux sens, faite avant de poser ce banc : avec la roue
# `opencv-contrib-python` du conteneur, 138 verts, le test de fenetre JOUE ;
# avec `getBuildInformation()` force a `GUI: NONE`, 137 verts et 1 SAUTE, en
# nommant son motif. Un seul test change d'etat, et c'est le bon.
# --------------------------------------------------------------------------


def test_la_garde_du_niveau_2_consulte_bien_la_CAPACITE_d_affichage():
    """Les trois prerequis sont nommes dans la condition, pas deux.

    Le detecteur est celui DU PRODUIT : redevine ici, il divergerait --
    `hasattr(cv2, "imshow")` rend `True` sur une roue headless, ce que les
    bancs voisins de ce fichier mesurent deja.
    """
    source = Path(__file__).read_text(encoding="utf-8")
    debut = source.index("requires_xvfb = pytest.mark.skipif(")
    condition = source[debut:source.index(")\n", debut)]

    manquants = [attendu for attendu in ("Xvfb", "ffmpeg", "_opencv_sait_afficher")
                 if attendu not in condition]

    assert not manquants, (
        "La garde du niveau 2 ne nomme pas : " + ", ".join(manquants)
        + ".\nSans la capacite d'affichage, le test de fenetre reelle ROUGIT "
        "sur toute installation conforme aux declarations du depot "
        "(`opencv-python-headless` depuis EPIC11-ARB-253) au lieu de sauter.")
