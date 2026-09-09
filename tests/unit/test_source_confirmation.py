"""Tests de la story 3.3 (rapport de metadonnees source + confirmation).

Entierement sur fixtures JSON ffprobe: aucun binaire externe, aucun `skipif`.
Si un test de cette story avait besoin de ffmpeg/ffprobe, c'est que le
decoupage en trois couches aurait ete rate.
"""

from __future__ import annotations

import ast
import io
import json
import logging
import subprocess
import sys
from dataclasses import dataclass, replace
from fractions import Fraction
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import source_confirmation
from mixed_media_utility.source_confirmation import (
    ConfirmationResult,
    SourceReportError,
    build_source_report,
    confirm_source_metadata,
    detect_interactive,
    render_confirmation_question,
    render_source_report,
    source_report_to_json_dict,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures_source_confirmation"


def probe(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# Bouchon du contrat FrameSelection (story 3.2, developpee en parallele).
# Cette story code contre le contrat ecrit, jamais contre son implementation.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class StubFrame:
    output_rank: int
    source_index: int
    frame_timecode: str


@dataclass(frozen=True)
class StubSelection:
    frames: tuple
    expected_frame_count: int
    source_tail_frames: int = 0
    warnings: tuple = ()
    timecode_base: str = "source"
    timecode_base_fps: Fraction = Fraction(24, 1)


@dataclass(frozen=True)
class StubSelectionBornee(StubSelection):
    """Selection bornee (story 3.7), stub **distinct** du stub d'origine.

    Revue du 2026-08-06: ajouter les deux champs a `StubSelection` rendait 53
    tests anterieurs a cette story dependants d'un attribut qu'ils
    n'employaient pas, ce que l'AC 14 interdit. `build_source_report` lit
    desormais les bornes par `getattr` avec repli, donc le stub d'origine
    repasse tel quel et seuls les tests de bornage se dotent des deux champs.
    """

    source_in_timecode: str | None = None
    source_out_timecode: str | None = None


def make_selection(
    count: int = 3,
    *,
    tail: int = 2,
    warnings: tuple = (),
    expected: int | None = None,
    base_fps: Fraction = Fraction(24, 1),
) -> StubSelection:
    frames = tuple(
        StubFrame(output_rank=n, source_index=n * 6, frame_timecode=f"01:00:0{n}:00")
        for n in range(count)
    )
    return StubSelection(
        frames=frames,
        expected_frame_count=count if expected is None else expected,
        source_tail_frames=tail,
        warnings=warnings,
        timecode_base_fps=base_fps,
    )


def build(name: str = "prores_hq_no_color_range", **kwargs):
    params = {
        "fps_target": 4,
        "selection": make_selection(),
        "batch_dir_relative": "frames/rush_4",
    }
    params.update(kwargs)
    return build_source_report(probe(name), **params)


class Answering:
    """Flux d'entree bouchonne: rend une reponse, ou leve."""

    def __init__(self, answer: str | None = None, *, raises: BaseException | None = None,
                 tty: bool = True) -> None:
        self._answer = answer
        self._raises = raises
        self._tty = tty
        self.read_count = 0

    def readline(self) -> str:
        self.read_count += 1
        if self._raises is not None:
            raise self._raises
        return self._answer

    def isatty(self) -> bool:
        return self._tty


class ExplodingStream:
    """Flux d'entree qui echoue si on le lit: verrouille l'AC 7.

    `input()` sur un stdin ouvert mais vide bloque indefiniment en CI; le mode
    non interactif ne doit jamais atteindre la ligne de lecture.
    """

    def readline(self) -> str:
        raise AssertionError("le flux d'entree a ete lu en mode non interactif")

    def read(self, *args) -> str:
        raise AssertionError("le flux d'entree a ete lu en mode non interactif")

    def isatty(self) -> bool:
        return False


# --------------------------------------------------------------------------
# Couche 1 -- construction du rapport
# --------------------------------------------------------------------------


def test_fully_tagged_source_needs_no_color_escalation() -> None:
    report = build("dnxhr_hq_fully_tagged", fps_target=5)
    assert report.color_triplet_status == source_confirmation.COLOR_TRIPLET_STATUS_COMPLETE
    assert report.requires_unknown_color_consent is False
    assert report.color_range_missing is False
    assert report.absent_fields == ()
    assert report.source_fields["source_color_primaries"] == "bt709"
    assert report.source_fields["source_bit_depth"] == 10
    assert report.fps_source_exact == "25/1"
    assert report.fps_target_exact == "5/1"


def test_prores_without_color_range_warns_but_does_not_escalate() -> None:
    """Mesure story 6.3: ProRes n'emet aucune plage, c'est le master du projet."""
    report = build("prores_hq_no_color_range")
    assert report.color_triplet_status == source_confirmation.COLOR_TRIPLET_STATUS_COMPLETE
    assert report.color_range_missing is True
    assert report.requires_unknown_color_consent is False
    assert report.absent_fields == ("source_color_range",)
    text = render_source_report(report)
    assert "color_range" in text
    assert "AVERTISSEMENT: colorimetrie source incomplete" not in text


def test_untagged_source_reports_absence_and_escalates() -> None:
    report = build("prores_untagged")
    assert report.color_triplet_status == source_confirmation.COLOR_TRIPLET_STATUS_ABSENT
    assert report.requires_unknown_color_consent is True
    assert report.absent_fields == (
        "source_color_primaries",
        "source_color_range",
        "source_color_trc",
        "source_colorspace",
    )
    for key in ("source_color_primaries", "source_color_trc", "source_colorspace"):
        assert report.source_fields[key] is None


def test_no_default_colorimetry_is_ever_substituted() -> None:
    """`bt709` n'est jamais ecrit a la place d'un champ vide, ni affiche."""
    report = build("prores_untagged")
    assert "bt709" not in json.dumps(source_report_to_json_dict(report))
    assert "bt709" not in render_source_report(report)


def test_single_color_flag_gives_partial_status() -> None:
    report = build("h264_single_color_flag", fps_target=6)
    assert report.color_triplet_status == source_confirmation.COLOR_TRIPLET_STATUS_PARTIAL
    assert report.requires_unknown_color_consent is True
    assert report.color_range_missing is False
    assert report.source_fields["source_colorspace"] == "bt709"
    assert report.absent_fields == ("source_color_primaries", "source_color_trc")


def test_literal_unknown_strings_normalize_like_a_missing_key() -> None:
    report = build("literal_unknown_strings")
    for key in (
        "source_color_primaries",
        "source_color_trc",
        "source_colorspace",
        "source_color_range",
        "source_sample_aspect_ratio",
    ):
        assert report.source_fields[key] is None, key
    assert report.display_aspect_ratio is None
    assert report.color_triplet_status == source_confirmation.COLOR_TRIPLET_STATUS_ABSENT
    # bits_per_raw_sample vaut la chaine vide: la profondeur vient de pix_fmt.
    assert report.source_fields["source_bit_depth"] == 8
    assert report.bit_depth_origin == "pix_fmt"


def test_anamorphic_sar_reports_both_resolutions() -> None:
    report = build("dvcpro_hd_anamorphic", fps_target=5)
    assert report.resolution_source == {"width": 1440, "height": 1080}
    assert report.display_resolution == {"width": 1920, "height": 1080}
    assert report.is_anamorphic is True
    assert report.source_fields["source_sample_aspect_ratio"] == "4:3"
    text = render_source_report(report)
    assert "1440 x 1080" in text
    assert "1920 x 1080" in text
    assert "SAR anamorphique" in text


def test_absent_sample_aspect_ratio_never_claims_a_display_resolution() -> None:
    """Revue: sans SAR, supposer des pixels carres substitue un 1:1 par defaut.

    AC 3 interdit toute valeur par defaut, et le Piege 4 demande precisement que
    l'anamorphose ne soit jamais masquee. La resolution de stockage, elle, reste
    affichee: c'est celle des TIFF qui seront ecrits.
    """
    report = build("literal_unknown_strings")  # sample_aspect_ratio == "0:1"
    assert report.source_fields["source_sample_aspect_ratio"] is None
    assert report.is_anamorphic is False
    text = render_source_report(report)
    display_line = next(
        line for line in text.splitlines() if "Resolution d'affichage" in line
    )
    assert source_confirmation.ABSENT_VALUE_LABEL in display_line
    assert "720 x 576" not in display_line
    assert "720 x 576" in text  # la resolution de stockage reste annoncee


def test_indeterminate_bit_depth_does_not_name_a_key_that_gave_nothing() -> None:
    """Revue AC 1: la cle nommee doit etre celle d'ou la valeur provient."""
    document = probe("prores_untagged")
    document["streams"][0]["pix_fmt"] = "unknown"
    report = build_source_report(
        document,
        fps_target=4,
        selection=make_selection(),
        batch_dir_relative="frames/rush_4",
    )
    assert report.bit_depth_origin is None
    depth_line = next(
        line for line in render_source_report(report).splitlines()
        if "Profondeur de bits" in line
    )
    assert "sans conclusion" in depth_line
    assert source_confirmation.INDETERMINATE_BIT_DEPTH_LABEL in depth_line


def test_unusable_timecode_base_rate_is_translated_not_leaked() -> None:
    """Revue: un timecode affiche porte toujours sa base (Piege 14).

    `FrameSelectionLike` est un Protocol structurel: une base de cadence
    inexploitable doit sortir en `SourceReportError` (code 1 cote 3.1), jamais
    en trace Python devant un operateur.
    """
    selection = StubSelection(
        frames=(),
        expected_frame_count=0,
        timecode_base_fps=Fraction(0, 1),
    )
    with pytest.raises(SourceReportError) as excinfo:
        build(selection=selection)
    assert "Cadence de base du timecode" in str(excinfo.value)


def test_square_pixels_are_not_flagged_anamorphic() -> None:
    report = build("prores_hq_no_color_range")
    assert report.is_anamorphic is False
    assert report.display_resolution == report.resolution_source
    assert "SAR anamorphique" not in render_source_report(report)


def test_bit_depth_prefers_bits_per_raw_sample() -> None:
    report = build("prores_hq_no_color_range")
    assert report.source_fields["source_bit_depth"] == 10
    assert report.bit_depth_origin == "bits_per_raw_sample"


def test_bit_depth_falls_back_on_pix_fmt_suffix() -> None:
    report = build("prores_untagged")  # pas de bits_per_raw_sample
    assert report.source_fields["source_bit_depth"] == 10
    assert report.bit_depth_origin == "pix_fmt"


def test_bit_depth_is_indeterminate_and_never_assumed_to_be_eight() -> None:
    document = probe("prores_untagged")
    document["streams"][0]["pix_fmt"] = "unknown"
    report = build_source_report(
        document,
        fps_target=4,
        selection=make_selection(),
        batch_dir_relative="frames/rush_4",
    )
    assert report.source_fields["source_bit_depth"] is None
    assert report.bit_depth_origin is None
    assert "source_bit_depth" in report.absent_fields
    assert source_confirmation.INDETERMINATE_BIT_DEPTH_LABEL in render_source_report(report)


def test_eight_bit_planar_pix_fmt_is_deduced() -> None:
    report = build("h264_single_color_flag", fps_target=6)  # yuv420p
    assert report.source_fields["source_bit_depth"] == 8
    assert report.bit_depth_origin == "pix_fmt"


def test_missing_resolution_is_blocking() -> None:
    with pytest.raises(SourceReportError) as excinfo:
        build("missing_resolution")
    assert "Resolution source inexploitable" in str(excinfo.value)


def test_no_video_stream_is_translated_not_leaked() -> None:
    from mixed_media_utility.video_metadata import FfprobeError

    with pytest.raises(SourceReportError) as excinfo:
        build("audio_only_no_video_stream")
    assert not isinstance(excinfo.value, FfprobeError)
    assert "Aucun flux video" in str(excinfo.value)


def test_absolute_batch_dir_is_refused() -> None:
    for absolute in ("/tmp/projet/frames/rush_4", r"C:\projet\frames\rush_4"):
        with pytest.raises(SourceReportError):
            build(batch_dir_relative=absolute)


def test_batch_dir_is_normalized_to_posix() -> None:
    report = build(batch_dir_relative=Path("frames") / "rush_4")
    assert report.batch_dir_relative == "frames/rush_4"


def test_timecode_is_found_at_format_level_too() -> None:
    """MXF pose le timecode au niveau format, pas sur le flux video."""
    assert build("dvcpro_hd_anamorphic", fps_target=5).source_start_timecode == "02:00:00:00"
    assert build("prores_hq_no_color_range").source_start_timecode == "01:00:00:00"
    assert build("prores_untagged").source_start_timecode is None


def test_selection_values_are_taken_verbatim_never_recomputed() -> None:
    """expected_frame_count n'est ni un len() local ni un comptage disque."""
    selection = make_selection(count=3, tail=7, expected=240)
    report = build(selection=selection)
    assert report.expected_frame_count == 240
    assert report.source_tail_frames == 7
    assert report.first_frame_timecode == "01:00:00:00"
    assert report.last_frame_timecode == "01:00:02:00"


def test_empty_selection_has_no_timecode_range() -> None:
    selection = StubSelection(frames=(), expected_frame_count=0)
    report = build(selection=selection)
    assert report.first_frame_timecode is None
    assert report.last_frame_timecode is None
    assert report.disk_upper_bound_bytes == 0


def test_disk_upper_bound_is_an_uncompressed_upper_bound() -> None:
    report = build(selection=make_selection(count=3, expected=240))
    assert report.disk_upper_bound_bytes == 1920 * 1080 * 3 * 2 * 240
    assert "borne haute non compressee" in render_source_report(report)


def test_no_subprocess_is_ever_launched(monkeypatch) -> None:
    def explode(*args, **kwargs):
        raise AssertionError("la story 3.3 ne doit lancer aucun sous-processus")

    monkeypatch.setattr(subprocess, "run", explode)
    monkeypatch.setattr(subprocess, "Popen", explode)
    monkeypatch.setattr(subprocess, "check_output", explode)

    report = build("prores_untagged")
    render_source_report(report)
    source_report_to_json_dict(report)
    confirm_source_metadata(
        report,
        interactive=False,
        consent_granted=True,
        unknown_color_accepted=True,
        out_stream=io.StringIO(),
        in_stream=ExplodingStream(),
    )


def test_module_stays_pure_of_process_and_file_access() -> None:
    """Analyse AST du module: ni subprocess, ni open/print/input, ni ffprobe."""
    tree = ast.parse((REPO_ROOT / "src/mixed_media_utility/source_confirmation.py").read_text("utf-8"))
    forbidden_calls = {"open", "print", "input", "exec", "eval", "compile"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in forbidden_calls, node.func.id
        if isinstance(node, ast.Attribute):
            # `read_technical_metadata` (matrice figee 6.3, 9 champs) ne donne
            # ni sample_aspect_ratio ni bits_per_raw_sample: insuffisant ici, et
            # elle re-probe. `probe_media` non plus: le dict vient de 3.1.
            assert node.attr not in (
                "run",
                "Popen",
                "check_output",
                "probe_media",
                "read_technical_metadata",
            )
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [alias.name for alias in node.names]
            assert "subprocess" not in names
            assert "shutil" not in names
            assert getattr(node, "module", None) != "subprocess"


def test_frame_selection_is_never_imported_at_runtime() -> None:
    """La story 3.2 est developpee en parallele: contrat, pas dependance."""
    tree = ast.parse((REPO_ROOT / "src/mixed_media_utility/source_confirmation.py").read_text("utf-8"))
    for node in tree.body:  # niveau module uniquement, hors bloc TYPE_CHECKING
        if isinstance(node, ast.ImportFrom):
            assert node.module != "frame_selection"
        if isinstance(node, ast.Import):
            assert all("frame_selection" not in alias.name for alias in node.names)


# --------------------------------------------------------------------------
# Couche 1bis -- forme JSON canonique (contrat vers 3.5)
# --------------------------------------------------------------------------


def test_json_dict_is_pure_json_and_deterministic() -> None:
    first = source_report_to_json_dict(build("prores_untagged"))
    second = source_report_to_json_dict(build("prores_untagged"))
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)

    def check(value) -> None:
        assert isinstance(value, (dict, list, str, int, float, bool, type(None))), type(value)
        if isinstance(value, dict):
            for key, item in value.items():
                assert isinstance(key, str)
                check(item)
        elif isinstance(value, list):
            for item in value:
                check(item)

    check(first)


def test_json_dict_carries_exact_rational_frame_rates() -> None:
    document = source_report_to_json_dict(build("prores_hq_no_color_range", fps_target=23.976))
    assert document["fps_source_exact"] == "24/1"
    assert document["fps_target_exact"] == "24000/1001"
    assert document["timecode"]["base"] == "source"
    assert document["timecode"]["base_fps_exact"] == "24/1"


def test_json_dict_exposes_the_video_key_names_persisted_by_story_3_4() -> None:
    document = source_report_to_json_dict(build("prores_untagged"))
    assert set(document["source_fields"]) == {
        "source_codec",
        "source_pix_fmt",
        "source_bit_depth",
        "source_sample_aspect_ratio",
        "source_color_primaries",
        "source_color_trc",
        "source_colorspace",
        "source_color_range",
    }
    assert document["resolution_source"] == {"width": 1920, "height": 1080}
    assert document["source_metadata_absent_fields"] == [
        "source_color_primaries",
        "source_color_range",
        "source_color_trc",
        "source_colorspace",
    ]
    assert "source_start_timecode" not in document["source_fields"]


def test_report_never_carries_an_absolute_path() -> None:
    serialized = json.dumps(source_report_to_json_dict(build()))
    assert str(REPO_ROOT) not in serialized
    assert serialized.count("/") >= 1  # le chemin relatif est bien la


# --------------------------------------------------------------------------
# Couche 2 -- rendu
# --------------------------------------------------------------------------


def test_render_is_ascii_only() -> None:
    """Convention des modules recents: francais sans accents (console cp1252)."""
    for name in (
        "dnxhr_hq_fully_tagged",
        "prores_hq_no_color_range",
        "prores_untagged",
        "h264_single_color_flag",
        "dvcpro_hd_anamorphic",
        "literal_unknown_strings",
    ):
        report = build(name, fps_target=4, selection=make_selection(warnings=("NON_DIVISIBLE_RATES",)))
        text = render_source_report(report) + render_confirmation_question(report)
        assert text.isascii(), name


def test_render_names_the_probe_key_of_each_value() -> None:
    text = render_source_report(build("dnxhr_hq_fully_tagged", fps_target=5))
    for probe_key in (
        "codec_name",
        "pix_fmt",
        "bits_per_raw_sample",
        "sample_aspect_ratio",
        "display_aspect_ratio",
        "color_primaries",
        "color_transfer",
        "color_space",
        "color_range",
        "r_frame_rate",
    ):
        assert probe_key in text, probe_key


def test_render_shows_selection_cardinal_tail_and_timecode_range() -> None:
    report = build(selection=make_selection(count=3, tail=5, expected=42))
    text = render_source_report(report)
    assert "expected_frame_count" in text
    assert "42" in text
    assert "Frames source non retenues en fin de rush" in text
    assert "5" in text
    assert "01:00:00:00 (base source, cadence 24/1)" in text
    assert "01:00:02:00 (base source, cadence 24/1)" in text


def test_every_displayed_timecode_carries_its_base() -> None:
    report = build(selection=make_selection(base_fps=Fraction(30000, 1001)))
    text = render_source_report(report)
    for line in text.splitlines():
        if "01:00:" in line:
            assert "base source, cadence 30000/1001" in line


def test_absent_values_are_labelled_not_blank() -> None:
    text = render_source_report(build("prores_untagged"))
    assert source_confirmation.ABSENT_VALUE_LABEL in text
    assert "Champs source non renseignes: source_color_primaries" in text


def test_selection_warning_codes_are_translated() -> None:
    report = build(selection=make_selection(warnings=("SOURCE_FRAME_COUNT_ESTIMATED",)))
    text = render_source_report(report)
    assert "[SOURCE_FRAME_COUNT_ESTIMATED]" in text
    assert "ESTIMATION" in text
    assert "tronque" in text


def test_unknown_warning_code_does_not_crash_the_render() -> None:
    report = build(selection=make_selection(warnings=("CODE_INVENTE_PAR_UNE_VERSION_FUTURE",)))
    text = render_source_report(report)
    assert "[CODE_INVENTE_PAR_UNE_VERSION_FUTURE]" in text


def test_color_warning_block_sits_just_above_the_question() -> None:
    report = build("prores_untagged")
    text = render_source_report(report)
    assert "AVERTISSEMENT: colorimetrie source incomplete" in text
    warning_position = text.index("AVERTISSEMENT: colorimetrie source incomplete")
    assert warning_position > text.index("Frames qui seront extraites")
    assert "colorimetrie source incomplete" in render_confirmation_question(report)


def test_question_defaults_to_no() -> None:
    assert render_confirmation_question(build()).rstrip().endswith("[o/N]")


# --------------------------------------------------------------------------
# Couche 3 -- interaction
# --------------------------------------------------------------------------


def test_interactive_answer_yes_grants() -> None:
    report = build("dnxhr_hq_fully_tagged", fps_target=5)
    out, in_stream = io.StringIO(), Answering("o\n")
    result = confirm_source_metadata(
        report, interactive=True, out_stream=out, in_stream=in_stream
    )
    assert result.granted is True
    assert result.mode == "interactif"
    assert result.unknown_color_accepted is False
    assert in_stream.read_count == 1
    assert "Confirmer l'extraction" in out.getvalue()


def test_interactive_answer_no_refuses() -> None:
    result = confirm_source_metadata(
        build(), interactive=True, out_stream=io.StringIO(), in_stream=Answering("non\n")
    )
    assert result.granted is False
    assert result.mode == "interactif"


def test_interactive_empty_answer_is_a_refusal() -> None:
    result = confirm_source_metadata(
        build(), interactive=True, out_stream=io.StringIO(), in_stream=Answering("\n")
    )
    assert result.granted is False


def test_interactive_eof_error_is_an_ordinary_refusal() -> None:
    result = confirm_source_metadata(
        build(),
        interactive=True,
        out_stream=io.StringIO(),
        in_stream=Answering(raises=EOFError()),
    )
    assert result.granted is False
    assert "Erreur" not in result.message


def test_interactive_keyboard_interrupt_is_an_ordinary_refusal() -> None:
    result = confirm_source_metadata(
        build(),
        interactive=True,
        out_stream=io.StringIO(),
        in_stream=Answering(raises=KeyboardInterrupt()),
    )
    assert result.granted is False


def test_interactive_end_of_stream_is_a_refusal() -> None:
    result = confirm_source_metadata(
        build(), interactive=True, out_stream=io.StringIO(), in_stream=Answering("")
    )
    assert result.granted is False


def test_interactive_single_question_accepts_unknown_colorimetry() -> None:
    """AC 4: une seule question, et un accord positionne le drapeau a true."""
    report = build("prores_untagged")
    out = io.StringIO()
    result = confirm_source_metadata(
        report, interactive=True, out_stream=out, in_stream=Answering("oui\n")
    )
    assert result.granted is True
    assert result.unknown_color_accepted is True
    assert out.getvalue().count("[o/N]") == 1


def test_non_interactive_without_consent_never_reads_the_input_stream() -> None:
    result = confirm_source_metadata(
        build("dnxhr_hq_fully_tagged", fps_target=5),
        interactive=False,
        consent_granted=False,
        out_stream=io.StringIO(),
        in_stream=ExplodingStream(),
    )
    assert result.granted is False
    assert result.mode == "non_interactif"
    assert source_confirmation.CONSENT_OPTION_HINT in result.message


def test_non_interactive_with_consent_still_emits_the_full_report() -> None:
    report = build("dnxhr_hq_fully_tagged", fps_target=5)
    out = io.StringIO()
    result = confirm_source_metadata(
        report,
        interactive=False,
        consent_granted=True,
        out_stream=out,
        in_stream=ExplodingStream(),
    )
    assert result.granted is True
    assert out.getvalue().startswith(render_source_report(report))
    assert "[o/N]" not in out.getvalue()


def test_non_interactive_escalation_needs_both_consents() -> None:
    report = build("prores_untagged")
    refused = confirm_source_metadata(
        report,
        interactive=False,
        consent_granted=True,
        unknown_color_accepted=False,
        out_stream=io.StringIO(),
        in_stream=ExplodingStream(),
    )
    assert refused.granted is False
    assert source_confirmation.UNKNOWN_COLOR_OPTION_HINT in refused.message
    assert refused.unknown_color_accepted is False

    granted = confirm_source_metadata(
        report,
        interactive=False,
        consent_granted=True,
        unknown_color_accepted=True,
        out_stream=io.StringIO(),
        in_stream=ExplodingStream(),
    )
    assert granted.granted is True
    assert granted.unknown_color_accepted is True


def test_non_interactive_refusal_without_consent_lists_both_options_on_escalation() -> None:
    result = confirm_source_metadata(
        build("prores_untagged"),
        interactive=False,
        consent_granted=False,
        out_stream=io.StringIO(),
        in_stream=ExplodingStream(),
    )
    assert source_confirmation.CONSENT_OPTION_HINT in result.message
    assert source_confirmation.UNKNOWN_COLOR_OPTION_HINT in result.message


def test_partial_triplet_escalates_but_missing_range_alone_does_not() -> None:
    """Verrou de l'AC 4: color_range seul n'escalade jamais."""
    prores = confirm_source_metadata(
        build("prores_hq_no_color_range"),
        interactive=False,
        consent_granted=True,
        unknown_color_accepted=False,
        out_stream=io.StringIO(),
        in_stream=ExplodingStream(),
    )
    assert prores.granted is True

    partial = confirm_source_metadata(
        build("h264_single_color_flag", fps_target=6),
        interactive=False,
        consent_granted=True,
        unknown_color_accepted=False,
        out_stream=io.StringIO(),
        in_stream=ExplodingStream(),
    )
    assert partial.granted is False


def test_confirmation_block_carries_exactly_the_three_persisted_names() -> None:
    result = confirm_source_metadata(
        build("prores_untagged"),
        interactive=False,
        consent_granted=True,
        unknown_color_accepted=True,
        out_stream=io.StringIO(),
        in_stream=ExplodingStream(),
    )
    block = result.confirmation_block()
    assert set(block) == {"mode", "unknown_color_accepted", "confirmed_at"}
    assert block["mode"] == "non_interactif"
    assert block["unknown_color_accepted"] is True
    assert "granted" not in block
    # Piege 8 de la story 3.4: une seule liste de champs absents, hors du bloc.
    assert "unknown_color_fields" not in block
    assert result.absent_fields == build("prores_untagged").absent_fields


def test_confirmed_at_is_rfc3339_utc_and_always_present() -> None:
    from datetime import datetime

    for granted in (True, False):
        result = confirm_source_metadata(
            build("dnxhr_hq_fully_tagged", fps_target=5),
            interactive=False,
            consent_granted=granted,
            out_stream=io.StringIO(),
            in_stream=ExplodingStream(),
        )
        assert datetime.strptime(result.confirmed_at, "%Y-%m-%dT%H:%M:%SZ")


def test_refusal_logs_both_the_report_and_the_decision(caplog) -> None:
    logger = logging.getLogger("test.source_confirmation.refusal")
    with caplog.at_level(logging.INFO, logger=logger.name):
        result = confirm_source_metadata(
            build("prores_untagged"),
            interactive=True,
            logger=logger,
            out_stream=io.StringIO(),
            in_stream=Answering("n\n"),
        )
    assert result.granted is False
    text = caplog.text
    assert "expected_frame_count" in text  # le rapport
    assert "Decision de confirmation" in text  # la decision
    assert "source_color_primaries" in text
    # Piege 11: un refus n'est pas une erreur.
    assert not [record for record in caplog.records if record.levelno >= logging.ERROR]
    assert "Erreur:" not in text
    assert any(record.levelno == logging.WARNING for record in caplog.records)


def test_granted_decision_is_logged_at_info(caplog) -> None:
    logger = logging.getLogger("test.source_confirmation.granted")
    with caplog.at_level(logging.INFO, logger=logger.name):
        confirm_source_metadata(
            build("dnxhr_hq_fully_tagged", fps_target=5),
            interactive=False,
            consent_granted=True,
            logger=logger,
            out_stream=io.StringIO(),
            in_stream=ExplodingStream(),
        )
    assert not [record for record in caplog.records if record.levelno > logging.INFO]


def test_refusal_creates_no_batch_directory(tmp_path) -> None:
    batch = tmp_path / "frames" / "rush_4"
    report = build(batch_dir_relative="frames/rush_4")
    result = confirm_source_metadata(
        report,
        interactive=True,
        out_stream=io.StringIO(),
        in_stream=Answering("\n"),
    )
    assert result.granted is False
    assert not batch.exists()
    assert list(tmp_path.iterdir()) == []


def test_refusal_invokes_no_ffmpeg_command_builder(monkeypatch) -> None:
    """AC 9: la confirmation s'intercale AVANT la construction de la commande."""
    from mixed_media_utility import codec_profiles, ffmpeg_utils

    def explode(*args, **kwargs):
        raise AssertionError("aucun appel ffmpeg ne doit avoir lieu sur refus")

    monkeypatch.setattr(codec_profiles, "build_encode_command", explode)
    monkeypatch.setattr(ffmpeg_utils, "extract_frames", explode)

    result = confirm_source_metadata(
        build("prores_untagged"),
        interactive=False,
        consent_granted=True,
        unknown_color_accepted=False,
        out_stream=io.StringIO(),
        in_stream=ExplodingStream(),
    )
    assert result.granted is False


def test_confirmation_result_is_frozen() -> None:
    result = confirm_source_metadata(
        build(), interactive=True, out_stream=io.StringIO(), in_stream=Answering("o\n")
    )
    assert isinstance(result, ConfirmationResult)
    with pytest.raises(Exception):
        replace(result, granted=False).granted = True  # type: ignore[misc]


# --------------------------------------------------------------------------
# Helper pur detect_interactive
# --------------------------------------------------------------------------


class _Stream:
    def __init__(self, tty: bool) -> None:
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


class _NoIsatty:
    """Objet sans methode isatty: non interactif, jamais une AttributeError."""


class _BrokenIsatty:
    def isatty(self):
        raise ValueError("I/O operation on closed file")


@pytest.mark.parametrize(
    "in_stream, out_stream, expected",
    [
        (_Stream(True), _Stream(True), True),
        (_Stream(True), _Stream(False), False),
        (_Stream(False), _Stream(True), False),
        (_Stream(False), _Stream(False), False),
        (None, _Stream(True), False),
        (_Stream(True), None, False),
        (None, None, False),
        (_NoIsatty(), _Stream(True), False),
        (_Stream(True), _NoIsatty(), False),
        (_BrokenIsatty(), _Stream(True), False),
    ],
)
def test_detect_interactive(in_stream, out_stream, expected) -> None:
    assert detect_interactive(in_stream, out_stream) is expected


def test_detect_interactive_is_pure() -> None:
    """Aucun acces a sys.stdin: les flux sont injectes, jamais substitues."""
    calls = []

    class Counting:
        def isatty(self) -> bool:
            calls.append(1)
            return True

    assert detect_interactive(Counting(), Counting()) is True
    assert len(calls) == 2


def test_policy_constant_is_the_single_escalation_rule() -> None:
    """ARB-5, tranche le 2026-08-03: deux consentements, definitivement."""
    assert source_confirmation.REQUIRE_SEPARATE_UNKNOWN_COLOR_CONSENT is True


# --------------------------------------------------------------------------
# Story 3.7, AC 10 -- l'intention avant la consequence
# --------------------------------------------------------------------------


def test_les_bornes_sont_annoncees_avant_le_nombre_d_images() -> None:
    """AC 10: un operateur qui a demande un extrait doit voir un extrait.

    Sans cet affichage, la seule trace du bornage dans le rapport serait un
    `expected_frame_count` plus petit que prevu -- indiscernable d'une erreur
    de cadence. L'ordre est normatif: l'intention, puis sa consequence.
    """
    selection = make_selection()
    report = build(
        selection=StubSelectionBornee(
            frames=selection.frames,
            expected_frame_count=selection.expected_frame_count,
            source_tail_frames=selection.source_tail_frames,
            source_in_timecode="01:00:05:00",
            source_out_timecode="01:00:25:00",
        )
    )
    assert report.source_in_timecode == "01:00:05:00"
    assert report.source_out_timecode == "01:00:25:00"

    lignes = render_source_report(report).splitlines()
    rang_in = next(i for i, l in enumerate(lignes) if "01:00:05:00" in l)
    rang_out = next(i for i, l in enumerate(lignes) if "01:00:25:00" in l)
    rang_compte = next(
        i for i, l in enumerate(lignes) if "expected_frame_count" in l
    )
    assert rang_in < rang_out < rang_compte


def test_une_extraction_non_bornee_n_annonce_aucune_borne() -> None:
    """AC 14: le rapport d'une extraction complete est inchange.

    Afficher « borne d'entree: absente » sur toutes les extractions
    ajouterait deux lignes de bruit a un rapport que l'operateur relit a
    chaque lancement, pour dire qu'il n'a rien demande de particulier.
    """
    report = build()
    assert report.source_in_timecode is None
    assert report.source_out_timecode is None

    texte = render_source_report(report)
    assert "Borne d'entree" not in texte
    assert "Borne de sortie" not in texte


def test_une_seule_borne_n_affiche_que_celle_la() -> None:
    selection = make_selection()
    report = build(
        selection=StubSelectionBornee(
            frames=selection.frames,
            expected_frame_count=selection.expected_frame_count,
            source_out_timecode="01:00:25:00",
        )
    )
    texte = render_source_report(report)
    assert "Borne d'entree" not in texte
    assert "Borne de sortie" in texte


def test_les_bornes_entrent_dans_la_forme_json_du_rapport() -> None:
    """La forme serialisee du rapport est ce qui part au journal (AC 12 de 3.3).

    Un rapport dont le texte console dit « extrait » et dont la trace JSON dit
    « rush entier » serait pire que pas de trace du tout.
    """
    selection = make_selection()
    report = build(
        selection=StubSelectionBornee(
            frames=selection.frames,
            expected_frame_count=selection.expected_frame_count,
            source_in_timecode="01:00:05:00",
            source_out_timecode="01:00:25:00",
        )
    )
    document = source_confirmation.source_report_to_json_dict(report)
    assert document["timecode"]["bound_in"] == "01:00:05:00"
    assert document["timecode"]["bound_out"] == "01:00:25:00"
    json.dumps(document, sort_keys=True)


def test_la_forme_json_d_un_lot_non_borne_est_celle_d_avant_la_story_3_7() -> None:
    """AC 14: ce document alimente `fingerprints.source_report` (story 3.5).

    Ecrire `bound_in: null` en permanence deplacait donc l'empreinte de toutes
    les extractions, y compris non bornees -- et ecrivait `null` la ou la
    regle du projet est d'omettre (revue du 2026-08-06).
    """
    document = source_confirmation.source_report_to_json_dict(build())
    assert "bound_in" not in document["timecode"]
    assert "bound_out" not in document["timecode"]
    assert set(document["timecode"]) == {
        "base",
        "base_fps_exact",
        "first_frame",
        "last_frame",
        "start",
    }


def test_une_selection_sans_attribut_de_borne_produit_encore_un_rapport() -> None:
    """Le Protocol reste structurel: un appelant d'avant la 3.7 passe encore."""
    report = build(selection=make_selection())
    assert report.source_in_timecode is None
    assert not hasattr(make_selection(), "source_in_timecode")
