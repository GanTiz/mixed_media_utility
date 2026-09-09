"""Tests de la commande `extract` (story 3.1).

Deux familles, volontairement separees:

* tests **purs**, sans aucun binaire externe: derivation d'identifiant, garde
  de forme de cadence, qualification VFR sur fixtures JSON ffprobe,
  construction de la commande ffmpeg, mapping des codes de sortie. Tout ce qui
  peut etre teste sans binaire l'est: si la couverture utile exigeait un
  binaire, c'est que la separation entre construction de commande et execution
  aurait ete ratee (Piege 10 de la story).
* tests d'**integration** marques `skipif`, sur le modele de
  `tests/unit/test_ffmpeg_utils.py` et `tests/unit/test_poc_run.py`. Ils
  fabriquent leur propre rush avec ffmpeg (`testsrc`) plutot que d'exiger un
  fichier fourni, et ils verifient la chaine reelle: TIFF ecrits, noms,
  profondeur, manifest.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import sys
from fractions import Fraction
from types import SimpleNamespace
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import (
    cli,
    extraction,
    ffmpeg_utils,
    progression,
    source_confirmation,
    video_metadata,
)
from mixed_media_utility.codec_profiles import validate_timecode
from mixed_media_utility.frame_selection import select_source_frames
from mixed_media_utility.io import project_layout
from mixed_media_utility.io.manifest import validate_manifest
from mixed_media_utility.io.extraction_manifest import (
    EXTRACTION_OUTPUT_BIT_DEPTH,
    MANIFEST_FILENAME,
    NON_IDEMPOTENT_FIELDS,
    VERIFY_MISSING_FRAMES,
    VERIFY_SOURCE_COUNT_NOT_EXACT,
    LotVerification,
    verify_extracted_lot,
)
from mixed_media_utility.io.naming import (
    CANONICAL_ID_MAX_LENGTH,
    NamingError,
    build_extracted_frame_filename,
    build_lot_id,
    format_fps_short,
    normalize_identifier,
)


requires_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe binaries not available on PATH",
)


# --------------------------------------------------------------------------
# Fixtures JSON ffprobe (aucun binaire requis)
# --------------------------------------------------------------------------


def make_probe(
    *,
    r_frame_rate: str | None = "30/1",
    avg_frame_rate: str | None = "30/1",
    nb_frames: str | None = "100",
    duration: str | None = "3.333333",
    width: int = 64,
    height: int = 36,
    pix_fmt: str = "yuv420p",
    tagged_color: bool = True,
    start_timecode: str | None = None,
    video_stream: bool = True,
) -> dict:
    streams = []
    if video_stream:
        stream: dict = {
            "codec_type": "video",
            "codec_name": "h264",
            "width": width,
            "height": height,
            "pix_fmt": pix_fmt,
            "bits_per_raw_sample": "8",
            "sample_aspect_ratio": "1:1",
        }
        if r_frame_rate is not None:
            stream["r_frame_rate"] = r_frame_rate
        if avg_frame_rate is not None:
            stream["avg_frame_rate"] = avg_frame_rate
        if nb_frames is not None:
            stream["nb_frames"] = nb_frames
        if duration is not None:
            stream["duration"] = duration
        if tagged_color:
            stream.update(
                {
                    "color_primaries": "bt709",
                    "color_transfer": "bt709",
                    "color_space": "bt709",
                    "color_range": "tv",
                }
            )
        if start_timecode is not None:
            stream["tags"] = {"timecode": start_timecode}
        streams.append(stream)
    return {"streams": streams, "format": {"duration": duration or "0"}}


# --------------------------------------------------------------------------
# AC 2 -- derivation deterministe de `rush_id`
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("rush-001", "rush-001"),
        ("Mon Rush #1", "Mon-Rush-1"),
        ("MonRush", "MonRush"),
        ("mon_rush_2", "mon_rush_2"),
        ("  espaces  ", "espaces"),
        ("a...b", "a-b"),
        ("Rush(01)[final]", "Rush-01-final"),
    ],
)
def test_normalize_identifier_cleans_dirty_names(raw, expected):
    assert normalize_identifier(raw) == expected


def test_normalize_identifier_strips_accents_deterministically():
    # NFKD + retrait des marques combinantes: la valeur doit etre identique
    # sur Windows, macOS et Linux (risque R2).
    assert normalize_identifier("Café Eté") == "Cafe-Ete"
    assert normalize_identifier("Café Été") == "Cafe-Ete"
    # Les deux formes Unicode (precomposee et decomposee) convergent.
    assert normalize_identifier("Café") == normalize_identifier("Café")


def test_normalize_identifier_preserves_case():
    assert normalize_identifier("RushABC") == "RushABC"


def test_normalize_identifier_result_always_matches_schema_pattern():
    import re

    pattern = re.compile(r"^[A-Za-z0-9_-]+$")
    for raw in ["Mon Rush #1", "Café", "a" * 80, "rush.001", "éèê"]:
        assert pattern.match(normalize_identifier(raw)), raw


def test_normalize_identifier_shortens_long_names_after_normalization():
    raw = "Un nom de rush volontairement tres long qui depasse la limite canonique"
    result = normalize_identifier(raw)
    assert len(result) <= CANONICAL_ID_MAX_LENGTH
    # `derive_short_id` recopie son prefixe verbatim: normaliser APRES elle
    # laisserait passer les espaces du nom d'origine (AC 2, ordre impose).
    assert " " not in result


def test_normalize_identifier_is_deterministic_across_calls():
    raw = "Un nom de rush volontairement tres long qui depasse la limite canonique"
    assert normalize_identifier(raw) == normalize_identifier(raw)


@pytest.mark.parametrize("raw", ["###", "...", "   ", "!!!", "日本語"])
def test_normalize_identifier_rejects_names_with_no_usable_character(raw):
    with pytest.raises(NamingError) as excinfo:
        normalize_identifier(raw, label="le nom du fichier source")
    message = str(excinfo.value)
    # Message actionnable, jamais le "Cannot derive a short id from an empty
    # value" de `derive_short_id` sur une chaine vide.
    assert "empty value" not in message
    assert "Renommer" in message


def test_normalize_identifier_collisions_are_accepted_and_documented():
    # Comportement retenu au MVP (question ouverte 7): la normalisation est une
    # fonction pure du nom, donc deux noms distincts peuvent converger. Le
    # determinisme inter-machine, objectif de l'AC 2, l'impose.
    assert normalize_identifier("Mon Rush") == normalize_identifier("Mon-Rush")


# --------------------------------------------------------------------------
# AC 5 -- garde de forme du fps entre dossier et nom de fichier
# --------------------------------------------------------------------------


@pytest.mark.parametrize("fps", [24, 25, 30, 24.0, 48])
def test_fps_forms_agree_on_integer_rates(fps):
    assert extraction.check_fps_form_consistency("rush-001", fps) == format_fps_short(fps)


def test_fps_forms_agree_on_fractional_rate_after_arb3():
    """12.5 im/s doit passer de bout en bout (decision 2 du 2026-08-03).

    Avant l'alignement de `project_layout.rush_dir_slug` sur
    `naming.format_fps_short` (commit ARB-3), le dossier rendait `rush_12.5`
    et le fichier `12p5`: la garde refusait la cadence, rendant injoignable une
    capacite que la story 3.2 supporte et teste. La garde ne doit plus se
    declencher.
    """
    assert extraction.check_fps_form_consistency("rush-001", 12.5) == "12p5"
    assert project_layout.rush_dir_slug("rush-001", 12.5) == "rush-001_12p5"
    assert build_extracted_frame_filename("rush-001", 12.5, "00:00:00:00") == (
        "rush-001_12p5_00-00-00-00.tiff"
    )


def test_une_extraction_bornee_franchit_la_garde_de_forme(monkeypatch):
    """AC 7 de la story 3.7: sans quoi la garde refuse tout extrait.

    Elle retire le prefixe `<rush_id>_` du slug et compare le reste a
    `format_fps_short`. Avec le suffixe de bornes, elle comparerait
    `3-a1b2c3d4` a `3` et leverait une `ExtractionInputError` avant meme le
    probe, sur un motif sans rapport avec la demande de l'operateur.
    """
    assert (
        extraction.check_fps_form_consistency(
            "rush-001",
            3,
            source_in_timecode="15:34:30:00",
            source_out_timecode="15:34:50:00",
        )
        == "3"
    )
    assert (
        extraction.check_fps_form_consistency(
            "rush-001", 12.5, source_in_timecode="15:34:30:00"
        )
        == "12p5"
    )


def test_la_garde_de_forme_reste_armee_sur_un_lot_borne(monkeypatch):
    """Le filet reste un filet: un extrait ne doit pas le desarmer."""
    monkeypatch.setattr(
        extraction.project_layout,
        "rush_dir_slug",
        lambda rush_id, fps, **bornes: f"{rush_id}_{fps}-deadbeef",
    )
    with pytest.raises(extraction.ExtractionInputError):
        extraction.check_fps_form_consistency(
            "rush-001",
            12.5,
            source_in_timecode="15:34:30:00",
            source_out_timecode="15:34:50:00",
        )


def test_fps_form_guard_still_refuses_a_divergence(monkeypatch):
    """Le filet de securite doit rester arme, pas seulement present."""
    monkeypatch.setattr(
        extraction.project_layout, "rush_dir_slug", lambda rush_id, fps: f"{rush_id}_{fps}"
    )
    with pytest.raises(extraction.ExtractionInputError) as excinfo:
        extraction.check_fps_form_consistency("rush-001", 12.5)
    message = str(excinfo.value)
    assert "12.5" in message and "12p5" in message


# --------------------------------------------------------------------------
# AC 8 -- refus VFR / cadence indeterminee, sur fixtures JSON
# --------------------------------------------------------------------------


def test_qualify_source_accepts_a_clean_cfr_source():
    qualification = extraction.qualify_source(make_probe())
    assert qualification.fps_source == Fraction(30, 1)
    assert qualification.declared_frame_count == 100
    assert qualification.stream_duration_seconds == pytest.approx(3.333333)


@pytest.mark.parametrize("rate", ["0/0", None, "", "0/1"])
def test_qualify_source_refuses_indeterminate_frame_rate(rate):
    with pytest.raises(extraction.ExtractionInputError) as excinfo:
        extraction.qualify_source(make_probe(r_frame_rate=rate))
    assert "Cadence source indeterminee" in str(excinfo.value)


def test_qualify_source_refuses_variable_frame_rate():
    # 30 nominal contre 24 en moyenne: 20 % d'ecart, tres au-dela du seuil.
    with pytest.raises(extraction.ExtractionInputError) as excinfo:
        extraction.qualify_source(make_probe(r_frame_rate="30/1", avg_frame_rate="24/1"))
    message = str(excinfo.value)
    assert "cadence variable" in message.lower()


def test_qualify_source_tolerates_deviation_below_threshold():
    # 0.5 % d'ecart: sous le seuil de 1 %, accepte.
    qualification = extraction.qualify_source(
        make_probe(r_frame_rate="1000/1", avg_frame_rate="995/1")
    )
    assert qualification.fps_source == Fraction(1000, 1)


def test_vfr_tolerance_is_a_named_constant():
    assert extraction.VFR_RELATIVE_TOLERANCE == 0.01


def test_qualify_source_uses_r_frame_rate_never_avg():
    qualification = extraction.qualify_source(
        make_probe(r_frame_rate="1000/1", avg_frame_rate="999/1")
    )
    assert qualification.fps_source == Fraction(1000, 1)


def test_qualify_source_refuses_a_file_without_video_stream():
    with pytest.raises(extraction.ExtractionInputError):
        extraction.qualify_source(make_probe(video_stream=False))


def test_qualify_source_finds_timecode_at_format_level():
    # MXF n'expose le timecode qu'au niveau format; Matroska met la cle en
    # majuscules. `_find_timecode` couvre les trois emplacements.
    probe = make_probe()
    probe["format"]["tags"] = {"TIMECODE": "01:00:00:00"}
    assert extraction.qualify_source(probe).start_timecode == "01:00:00:00"


# --------------------------------------------------------------------------
# Piege 8 -- provenance du cardinal source
# --------------------------------------------------------------------------


def test_frame_count_uses_nb_frames_when_it_matches_duration(monkeypatch):
    monkeypatch.setattr(
        extraction, "count_frames_exact", lambda *a, **k: pytest.fail("ne doit pas etre appele")
    )
    qualification = extraction.qualify_source(make_probe())
    assert extraction.resolve_source_frame_count("x.mov", qualification) == (100, True)


def test_frame_count_falls_back_to_count_frames_when_nb_frames_disagrees(monkeypatch):
    calls = []

    def fake_count(video_path, *, ffprobe_bin="ffprobe"):
        calls.append(video_path)
        return 250

    monkeypatch.setattr(extraction, "count_frames_exact", fake_count)
    # nb_frames ment (100) alors que la duree implique 300 frames.
    qualification = extraction.qualify_source(make_probe(nb_frames="100", duration="10.0"))
    assert extraction.resolve_source_frame_count("x.mov", qualification) == (250, True)
    assert calls, "le comptage exact doit etre paye quand nb_frames ne recoupe pas"


def test_frame_count_declares_an_estimation_rather_than_guessing(monkeypatch):
    monkeypatch.setattr(extraction, "count_frames_exact", lambda *a, **k: None)
    qualification = extraction.qualify_source(make_probe(nb_frames=None, duration="10.0"))
    count, is_exact = extraction.resolve_source_frame_count("x.mov", qualification)
    assert count == 300
    # Un cardinal estime est declare tel quel: le noyau emet alors
    # SOURCE_FRAME_COUNT_ESTIMATED plutot que de laisser croire a un comptage.
    assert is_exact is False


def test_estimated_frame_count_propagates_the_warning_code(monkeypatch):
    monkeypatch.setattr(extraction, "count_frames_exact", lambda *a, **k: None)
    qualification = extraction.qualify_source(make_probe(nb_frames=None, duration="10.0"))
    count, is_exact = extraction.resolve_source_frame_count("x.mov", qualification)
    selection = select_source_frames(
        fps_source=qualification.fps_source,
        fps_target=4,
        source_frame_count=count,
        source_frame_count_is_exact=is_exact,
    )
    assert "SOURCE_FRAME_COUNT_ESTIMATED" in selection.warnings


# --------------------------------------------------------------------------
# Piege 9 -- base de timecode source, jamais cible
# --------------------------------------------------------------------------


def test_timecode_is_expressed_in_source_base_not_target_base():
    """Test de jonction exige par la story (precedent `page_index` 2.3/2.6).

    Un rush 30 fps extrait vers 4 fps produit `00:00:03:07` sur son dernier
    rang. Valider ce timecode contre la cadence **cible** leve (`07 >= 4`);
    contre la cadence **source**, il passe. C'est exactement l'erreur que le
    nom de fichier invite a commettre, puisqu'il porte `fps_target` juste a
    cote du timecode.
    """
    selection = select_source_frames(fps_source=30, fps_target=4, source_frame_count=100)
    assert selection.timecode_base == "source"
    assert selection.timecode_base_fps == Fraction(30, 1)

    last = selection[-1]
    assert last.source_index == 97
    assert last.frame_timecode == "00:00:03:07"

    # Contre la base source: valide.
    validate_timecode(last.frame_timecode, selection.timecode_base_fps)
    # Contre la cadence cible: leve. Aucune validation de 3.1 ne doit passer
    # par la.
    with pytest.raises(ValueError):
        validate_timecode(last.frame_timecode, selection.fps_target)


# --------------------------------------------------------------------------
# AC 6 / AC 10 -- construction de la commande ffmpeg
# --------------------------------------------------------------------------


def test_select_expression_escapes_commas():
    # Dans un filtergraph la virgule separe les filtres: `eq(n,0)` serait lu
    # comme le filtre `select` suivi d'un filtre `0)` inexistant.
    assert ffmpeg_utils.build_select_expression([0, 7]) == r"eq(n\,0)+eq(n\,7)"


def test_selection_command_never_uses_the_resampling_filter():
    command = ffmpeg_utils.build_frame_selection_command(
        "ffmpeg", "rush.mov", [0, 7], "out/tmp_%08d.tiff", 0
    )
    joined = " ".join(command)
    assert "fps=" not in joined, "-vf fps= duplique des frames et est proscrit ici"


def test_selection_command_puts_select_first_in_the_filter_chain():
    command = ffmpeg_utils.build_frame_selection_command(
        "ffmpeg", "rush.mov", [0, 7], "out/tmp_%08d.tiff", 0
    )
    filtergraph = command[command.index("-vf") + 1]
    # `n` compte les frames entrees dans le filtre: tout filtre place avant
    # `select` ferait porter la selection sur une autre sequence.
    assert filtergraph.startswith("select=")


def test_selection_command_declares_passthrough_after_input():
    command = ffmpeg_utils.build_frame_selection_command(
        "ffmpeg", "rush.mov", [0, 7], "out/tmp_%08d.tiff", 0
    )
    assert ffmpeg_utils.FPS_MODE_OPTION in command
    assert command[command.index(ffmpeg_utils.FPS_MODE_OPTION) + 1] == "passthrough"
    # Option de SORTIE: apres l'entree, avant le motif de sortie.
    assert command.index("-i") < command.index(ffmpeg_utils.FPS_MODE_OPTION)
    assert command.index(ffmpeg_utils.FPS_MODE_OPTION) < len(command) - 1


def test_selection_command_forces_16_bit_rgb_pixel_format():
    command = ffmpeg_utils.build_frame_selection_command(
        "ffmpeg", "rush.mov", [0], "out/tmp_%08d.tiff", 0
    )
    assert command[command.index("-pix_fmt") + 1] == "rgb48le"
    assert ffmpeg_utils.EXTRACT_OUTPUT_BIT_DEPTH == 16


def test_selection_command_sets_start_number_explicitly():
    command = ffmpeg_utils.build_frame_selection_command(
        "ffmpeg", "rush.mov", [0], "out/tmp_%08d.tiff", 42
    )
    # Le muxer image2 numerote a partir de 1 sans cette option.
    assert command[command.index("-start_number") + 1] == "42"


def test_selection_command_exact_shape_is_locked():
    command = ffmpeg_utils.build_frame_selection_command(
        "/usr/bin/ffmpeg", "rush.mov", [0, 7], "out/tmp_%08d.tiff", 0
    )
    assert command == [
        "/usr/bin/ffmpeg",
        "-hide_banner",
        "-nostdin",
        "-y",
        "-i", "rush.mov",
        "-vf", r"select=eq(n\,0)+eq(n\,7)",
        "-fps_mode", "passthrough",
        "-pix_fmt", "rgb48le",
        "-c:v", "tiff",
        "-an",
        "-start_number", "0",
        "out/tmp_%08d.tiff",
    ]


def test_large_selection_is_split_into_several_invocations():
    # Piege 4: une expression `select` de plusieurs milliers de termes depasse
    # la longueur de ligne de commande de l'OS (Windows, ~32 Ko).
    indices = list(range(0, 10000, 2))
    chunks = ffmpeg_utils.plan_selection_chunks(indices)
    assert len(chunks) > 1
    assert sum(len(chunk) for _, chunk in chunks) == len(indices)
    # Les rangs de depart sont contigus et servent directement de -start_number.
    assert [start for start, _ in chunks] == list(
        range(0, len(indices), ffmpeg_utils.MAX_SELECT_TERMS_PER_INVOCATION)
    )
    # Aucune commande ne depasse une longueur raisonnable.
    for start, chunk in chunks:
        command = ffmpeg_utils.build_frame_selection_command(
            "ffmpeg", "rush.mov", chunk, "out/tmp_%08d.tiff", start
        )
        assert sum(len(part) for part in command) < 30000


def test_temp_frame_names_survive_field_widening_beyond_9999():
    # `%04d` n'aurait pas tronque mais elargi le champ, cassant tout tri
    # lexicographique. Les noms sont ici CALCULES, jamais retrouves par glob.
    assert ffmpeg_utils.temp_frame_path("d", 0).name == "mmu_extract_00000000.tiff"
    assert ffmpeg_utils.temp_frame_path("d", 12345).name == "mmu_extract_00012345.tiff"
    assert ffmpeg_utils.temp_frame_path("d", 123456789).name == "mmu_extract_123456789.tiff"


def test_extract_selected_frames_refuses_a_non_increasing_selection(tmp_path):
    video = tmp_path / "rush.mov"
    video.write_bytes(b"not a real video")
    with pytest.raises(ffmpeg_utils.FrameExtractionError):
        ffmpeg_utils.extract_selected_frames(video, tmp_path / "out", [5, 3])


def test_legacy_poc_extract_frames_is_untouched():
    """Baseline story 1.1: signature et defauts inchanges."""
    import inspect

    signature = inspect.signature(ffmpeg_utils.extract_frames)
    assert signature.parameters["filename_pattern"].default == "frame_%04d.png"
    assert signature.parameters["ffmpeg_binary"].default == "ffmpeg"
    assert list(signature.parameters) == [
        "video_path", "output_dir", "fps", "ffmpeg_binary", "filename_pattern",
    ]


# --------------------------------------------------------------------------
# Chemin complet, ffmpeg simule (logique de renommage, comptage, persistance)
# --------------------------------------------------------------------------


@pytest.fixture
def fake_ffmpeg(monkeypatch):
    """Remplace l'execution ffmpeg par l'ecriture des fichiers temporaires."""

    def fake_extract(
        video_path, temp_dir, source_indices, *, ffmpeg_binary="ffmpeg",
        rappel_progression=None, **kwargs,
    ):
        temp_dir = Path(temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)
        # Le bouchon EMET, comme le vrai (story 5.28) : sans cela, un test qui
        # passe un rappel a `run_extraction` ne mesure aucune ligne de la story
        # -- le rappel etait avale par `**kwargs` et la liste de jalons du test
        # restait une variable morte (revue de vague 2 bis, BH-7). Sans rappel,
        # l'emetteur est inactif et rien ne change pour les autres tests.
        emetteur = progression.EmetteurProgression(
            rappel_progression, len(list(source_indices))
        )
        paths = []
        for rank, _ in enumerate(source_indices):
            path = ffmpeg_utils.temp_frame_path(temp_dir, rank)
            path.write_bytes(b"fake tiff")
            paths.append(path)
            emetteur.emettre(len(paths))
        return paths

    monkeypatch.setattr(extraction.ffmpeg_utils, "extract_selected_frames", fake_extract)
    monkeypatch.setattr(extraction.ffmpeg_utils, "ensure_ffmpeg_available", lambda b="ffmpeg": "/x/ffmpeg")
    return fake_extract


@pytest.fixture
def fake_probe(monkeypatch):
    def install(probe: dict) -> None:
        monkeypatch.setattr(
            extraction.video_metadata, "probe_media", lambda path, **kwargs: probe
        )

    install(make_probe())
    return install


def _run_cli(tmp_path, video, fps, *extra):
    return cli.main(
        ["extract", "--project", str(tmp_path / "proj"), "--video", str(video), "--fps", str(fps)]
        + list(extra)
    )


@pytest.fixture
def rush(tmp_path):
    path = tmp_path / "rush-001.mov"
    path.write_bytes(b"fake source")
    return path


def test_full_run_writes_named_frames_and_manifest(tmp_path, rush, fake_probe, fake_ffmpeg):
    code = _run_cli(tmp_path, rush, 4, "--yes")
    assert code == 0

    project = tmp_path / "proj"
    frames_dir = project_layout.extract_frames_dir_from_slug(project, "rush-001_4")
    written = sorted(p.name for p in frames_dir.iterdir())

    selection = select_source_frames(fps_source=30, fps_target=4, source_frame_count=100)
    expected = sorted(
        build_extracted_frame_filename("rush-001", 4, frame.frame_timecode)
        for frame in selection
    )
    assert written == expected
    assert len(written) == selection.expected_frame_count

    manifest = json.loads((project / "project.json").read_text(encoding="utf-8"))
    lot = manifest["lots"][0]
    assert lot["state"] == "extraction"
    assert lot["expected_frame_count"] == selection.expected_frame_count
    assert lot["frames_dir"] == f"{project_layout.EXTRACT_FRAMES_DIRNAME}/rush-001_4"
    assert lot["timecode_base"] == "source"
    assert lot["timecode_base_fps"] == "30/1"
    assert lot["output_bit_depth"] == EXTRACTION_OUTPUT_BIT_DEPTH
    assert manifest["rushes"][0]["rush_id"] == "rush-001"
    # v2.1: la source appartient au rush, la cadence cible appartient au lot.
    assert manifest["rushes"][0]["fps_source"] == 30.0
    assert lot["fps_target"] == 4.0
    assert lot["fps_target_exact"] == "4/1"
    assert manifest["video"] == {}

    verification = verify_extracted_lot(project, manifest, lot["lot_id"])
    assert verification.ok, verification.findings
    assert verification.observed_frame_count == selection.expected_frame_count


# ---------------------------------------------------------------------------
# Story 11.14, lot E1 -- le VOLET SYMETRIQUE : `EPIC11-ARB-222`
# ---------------------------------------------------------------------------
#
# « Un projet existant ne se convertit pas. » L'ancien dossier `frames/` reste
# lu INDEFINIMENT, il n'est simplement plus jamais ecrit. Une suite qui
# n'exercerait que la forme NEUVE aurait donc cesse de mesurer la moitie du
# contrat -- et ce n'est pas une hypothese : le lot D1 a trouve l'inverse
# exact, une suite entierement verte sur la forme que la story RETIRE, sans
# jouer une seule fois celle qu'elle POSE.
#
# Les deux mesures ci-dessous sont ecrites ensemble parce qu'elles ne se
# suffisent pas : la premiere dit que l'ancien nom est reconnu, la seconde que
# le neuf est bien celui qu'on ECRIT quand rien ne preexiste. Prise seule, l'une
# serait satisfaite par un code qui ecrirait toujours a l'ancien nom, l'autre
# par un code qui ignorerait l'ancien.


def test_un_projet_a_L_ANCIEN_NOM_de_dossier_reste_ECRIT_dedans(
    tmp_path, rush, fake_probe, fake_ffmpeg
):
    """`EPIC11-ARB-222` de bout en bout : par la CLI, pas par le seul module.

    Le dossier d'avant est pose **avant** l'extraction, comme un projet deja sur
    un disque le porterait. La commande doit ecrire son lot DEDANS, et surtout
    ne pas fabriquer un second dossier au nom neuf : un lot scinde entre deux
    racines serait a moitie invisible pour `encode`, ce que la docstring de
    `_dossier_de_lot` nomme explicitement.
    """
    projet = tmp_path / "proj"
    ancien = projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-001_4"
    ancien.mkdir(parents=True)

    assert _run_cli(tmp_path, rush, 4, "--yes") == 0

    ecrites = sorted(chemin.name for chemin in ancien.iterdir() if chemin.is_file())
    assert ecrites, "le lot n'a pas ete ecrit dans le dossier deja present"
    selection = select_source_frames(
        fps_source=30, fps_target=4, source_frame_count=100)
    assert ecrites == sorted(
        build_extracted_frame_filename("rush-001", 4, frame.frame_timecode)
        for frame in selection
    )

    # ... et AUCUN second dossier au nom neuf pour le meme lot. C'est la moitie
    # qui compte : sans elle, un code qui ecrirait des deux cotes passerait.
    neuf = projet / project_layout.EXTRACT_FRAMES_DIRNAME / "rush-001_4"
    assert not neuf.exists(), (
        f"le lot est scinde entre deux racines : {neuf} a ete cree alors que "
        f"{ancien} existait deja"
    )

    # Le manifeste, lui, declare le chemin REELLEMENT ecrit -- pas le nom neuf
    # par principe. Un manifeste qui mentirait sur l'emplacement ferait echouer
    # `verify_extracted_lot` bien plus loin, sur un lot pourtant intact.
    manifest = json.loads((projet / "project.json").read_text(encoding="utf-8"))
    lot = manifest["lots"][0]
    assert lot["frames_dir"] == (
        f"{project_layout.LEGACY_FRAMES_DIRNAME}/rush-001_4")
    verification = verify_extracted_lot(projet, manifest, lot["lot_id"])
    assert verification.ok, verification.findings


def test_l_ancien_nom_n_est_JAMAIS_ecrit_quand_il_n_existe_PAS(
    tmp_path, rush, fake_probe, fake_ffmpeg
):
    """Volet symetrique du precedent : reconnu en lecture, jamais en ecriture.

    Sans lui, le test ci-dessus serait satisfait par un produit qui ecrirait
    **toujours** a l'ancien nom -- c'est-a-dire par un renommage qui n'aurait
    pas eu lieu.
    """
    assert _run_cli(tmp_path, rush, 4, "--yes") == 0
    projet = tmp_path / "proj"
    assert (projet / project_layout.EXTRACT_FRAMES_DIRNAME / "rush-001_4").is_dir()
    assert not (projet / project_layout.LEGACY_FRAMES_DIRNAME).exists(), (
        "le nom d'avant a ete ECRIT : `EPIC11-ARB-222` ne le fait que "
        "RECONNAITRE"
    )


def test_DEUX_lots_dont_UN_SEUL_porte_l_ancien_nom_vont_CHACUN_au_sien(
    tmp_path, rush, fake_probe, fake_ffmpeg
):
    """La resolution est faite PAR LOT, jamais par racine.

    C'est la propriete que la docstring de `_dossier_de_lot` revendique, et
    aucune fabrique mono-lot ne peut la mesurer : avec un seul lot, « par lot »
    et « par racine » rendent le meme resultat. Deux lots **distinguables** --
    cadences differentes, donc slugs differents -- et un seul des deux
    preexistant a l'ancien nom : le fautif ferait porter le nom d'avant au lot
    NEUF simplement parce qu'un lot ancien vit dans le meme projet.

    La cible est en **queue** de la sequence des deux extractions, position que
    la regle des fabriques (point 4, 2026-09-03) exige au meme titre que la
    tete : un balayage tronque ne se demasque pas autrement.
    """
    projet = tmp_path / "proj"
    (projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-001_4").mkdir(parents=True)

    assert _run_cli(tmp_path, rush, 4, "--yes") == 0
    assert _run_cli(tmp_path, rush, 5, "--yes") == 0

    # Le lot deja present : a l'ancien nom, et pas au neuf.
    assert any((projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-001_4"
                ).iterdir())
    assert not (projet / project_layout.EXTRACT_FRAMES_DIRNAME
                / "rush-001_4").exists()
    # Le lot neuf : au nom neuf, et pas a l'ancien.
    assert any((projet / project_layout.EXTRACT_FRAMES_DIRNAME / "rush-001_5"
                ).iterdir())
    assert not (projet / project_layout.LEGACY_FRAMES_DIRNAME
                / "rush-001_5").exists(), (
        "le lot NEUF a ete ecrit au nom d'avant parce qu'un lot ancien vit "
        "dans le meme projet : la resolution s'est faite par racine, pas par lot"
    )

    # Les deux racines sont vues comme telles, et dans l'ordre voulu : la
    # neuve d'abord. Un parcours qui n'en verrait qu'une ne compterait qu'un lot.
    racines = project_layout.racines_de_frames_extraites(projet)
    assert racines == (
        projet / project_layout.EXTRACT_FRAMES_DIRNAME,
        projet / project_layout.LEGACY_FRAMES_DIRNAME,
    )
    lots = sorted(
        chemin.name for racine in racines for chemin in racine.iterdir()
        if chemin.is_dir()
    )
    assert lots == ["rush-001_4", "rush-001_5"]


def test_no_temporary_file_survives_the_run(tmp_path, rush, fake_probe, fake_ffmpeg):
    assert _run_cli(tmp_path, rush, 4, "--yes") == 0
    frames_dir = project_layout.extract_frames_dir_from_slug(tmp_path / "proj", "rush-001_4")
    assert not (frames_dir / ffmpeg_utils.EXTRACT_TEMP_DIRNAME).exists()
    assert all(p.suffix == ".tiff" for p in frames_dir.iterdir())


def test_fractional_target_rate_runs_end_to_end(tmp_path, rush, fake_probe, fake_ffmpeg):
    """12.5 im/s de bout en bout (decision 2 du 2026-08-03, ARB-3)."""
    assert _run_cli(tmp_path, rush, 12.5, "--yes") == 0
    frames_dir = project_layout.extract_frames_dir_from_slug(tmp_path / "proj", "rush-001_12p5")
    assert frames_dir.is_dir()
    names = sorted(p.name for p in frames_dir.iterdir())
    assert names[0].startswith("rush-001_12p5_")
    manifest = json.loads((tmp_path / "proj" / "project.json").read_text(encoding="utf-8"))
    assert manifest["lots"][0]["frames_dir"] == f"{project_layout.EXTRACT_FRAMES_DIRNAME}/rush-001_12p5"
    assert manifest["lots"][0]["fps_target"] == 12.5
    assert manifest["lots"][0]["fps_target_exact"] == "25/2"


def test_count_mismatch_fails_loudly_rather_than_declaring_success(
    tmp_path, rush, fake_probe, monkeypatch
):
    """AC 6: un lot tronque est une erreur, jamais un succes partiel."""

    def truncating_extract(video_path, temp_dir, source_indices, **kwargs):
        # ffmpeg n'ecrit pas de fichier pour un indice au-dela de la fin du
        # flux, et ne renvoie aucun code d'erreur: la garde de compte est la
        # seule detection possible.
        raise ffmpeg_utils.FrameExtractionError("ffmpeg n'a ecrit que 3 fichier(s) sur les 14")

    monkeypatch.setattr(extraction.ffmpeg_utils, "extract_selected_frames", truncating_extract)
    monkeypatch.setattr(extraction.ffmpeg_utils, "ensure_ffmpeg_available", lambda b="ffmpeg": "/x/ffmpeg")

    assert _run_cli(tmp_path, rush, 4, "--yes") == 1
    assert not (tmp_path / "proj" / "project.json").exists()


def test_persistence_happens_after_tiff_writing(tmp_path, rush, fake_probe, fake_ffmpeg):
    """ARB-1: `extract` porte l'appel a `persist_extraction` lui-meme."""
    assert _run_cli(tmp_path, rush, 4, "--yes") == 0
    manifest_path = tmp_path / "proj" / "project.json"
    assert manifest_path.is_file(), "une extraction reussie doit laisser une trace manifest"


# --------------------------------------------------------------------------
# AC 9 / codes de sortie
# --------------------------------------------------------------------------


def _lot_by_id(manifest: dict, lot_id: str) -> dict:
    for lot in manifest["lots"]:
        if lot["lot_id"] == lot_id:
            return lot
    raise AssertionError(f"lot {lot_id!r} absent du manifest: {manifest['lots']}")


def test_second_target_rate_in_one_project_keeps_both_lots_verifiable(
    tmp_path, rush, fake_probe, fake_ffmpeg
):
    """Deux cadences cibles pour un meme rush coexistent (2026-08-04).

    Ancien comportement, verrouille jusqu'a la restructuration v2.1: `video`
    etait une section unique alors que `lots[]` est une liste, donc une
    seconde cadence cible ecrasait `video.fps_target` et le premier lot
    devenait non verifiable bien que ses fichiers soient intacts. La cadence
    cible appartient desormais au lot: chacun des deux lots se verifie
    independamment comme conforme.
    """
    assert _run_cli(tmp_path, rush, 4, "--yes") == 0
    assert _run_cli(tmp_path, rush, 2, "--yes") == 0

    project = tmp_path / "proj"
    manifest = json.loads((project / "project.json").read_text(encoding="utf-8"))

    # Un seul rush, deux lots, aucune cadence au niveau projet.
    assert [rush_entry["rush_id"] for rush_entry in manifest["rushes"]] == ["rush-001"]
    assert manifest["rushes"][0]["fps_source"] == 30.0
    assert sorted(lot["lot_id"] for lot in manifest["lots"]) == ["rush-001_2", "rush-001_4"]
    assert "fps_target" not in manifest["video"]

    for target in (4, 2):
        lot_id = f"rush-001_{target}"
        expected = select_source_frames(
            fps_source=30, fps_target=target, source_frame_count=100
        ).expected_frame_count
        slug = project_layout.rush_dir_slug("rush-001", target)
        assert len(list(project_layout.extract_frames_dir_from_slug(project, slug).iterdir())) == expected

        lot = _lot_by_id(manifest, lot_id)
        assert lot["fps_target"] == float(target)
        assert lot["expected_frame_count"] == expected

        verification = verify_extracted_lot(project, manifest, lot_id)
        assert verification.ok, (lot_id, verification.findings)
        assert verification.digest_matches is True
        assert verification.observed_frame_count == expected


def test_three_target_rates_on_one_rush_all_verify(tmp_path, rush, fake_probe, fake_ffmpeg):
    """Le scenario reel d'Egan: comparer 3, 5 et 12,5 im/s dans un seul projet."""
    for target in (3, 5, 12.5):
        assert _run_cli(tmp_path, rush, target, "--yes") == 0

    project = tmp_path / "proj"
    manifest = json.loads((project / "project.json").read_text(encoding="utf-8"))

    assert len(manifest["rushes"]) == 1
    assert len(manifest["lots"]) == 3
    assert sorted(lot["fps_target"] for lot in manifest["lots"]) == [3.0, 5.0, 12.5]

    for target in (3, 5, 12.5):
        lot_id = build_lot_id("rush-001", target)
        verification = verify_extracted_lot(project, manifest, lot_id)
        assert verification.ok, (lot_id, verification.findings)
        assert verification.digest_matches is True
        assert verification.expected_frame_count == select_source_frames(
            fps_source=30, fps_target=target, source_frame_count=100
        ).expected_frame_count

    # Chaque lot a bien son propre dossier, aucun n'ecrase l'autre.
    slugs = sorted(entry.name for entry in (project / project_layout.EXTRACT_FRAMES_DIRNAME).iterdir())
    assert slugs == ["rush-001_12p5", "rush-001_3", "rush-001_5"]


def test_two_distinct_rushes_in_one_project_keep_their_own_source_rate(
    tmp_path, rush, fake_probe, fake_ffmpeg, monkeypatch
):
    """Un projet porte plusieurs rushs, chacun avec sa propre cadence source."""
    second_rush = tmp_path / "rush-002.mov"
    second_rush.write_bytes(b"fake source")

    assert _run_cli(tmp_path, rush, 5, "--yes") == 0

    # Le second rush est a 25 im/s, pas 30: la cadence source ne peut donc pas
    # vivre au niveau projet sans se contredire d'un rush a l'autre.
    fake_probe(make_probe(r_frame_rate="25/1", avg_frame_rate="25/1", nb_frames="100", duration="4.0"))
    assert _run_cli(tmp_path, second_rush, 5, "--yes") == 0

    project = tmp_path / "proj"
    manifest = json.loads((project / "project.json").read_text(encoding="utf-8"))

    rates = {entry["rush_id"]: entry["fps_source"] for entry in manifest["rushes"]}
    assert rates == {"rush-001": 30.0, "rush-002": 25.0}
    assert {entry["rush_id"]: entry["fps_source_exact"] for entry in manifest["rushes"]} == {
        "rush-001": "30/1",
        "rush-002": "25/1",
    }

    for rush_id in ("rush-001", "rush-002"):
        lot_id = build_lot_id(rush_id, 5)
        verification = verify_extracted_lot(project, manifest, lot_id)
        assert verification.ok, (lot_id, verification.findings)
        assert verification.digest_matches is True


def test_a_v2_0_manifest_is_migrated_before_a_second_rate_is_added(
    tmp_path, rush, fake_probe, fake_ffmpeg
):
    """Compatibilite: un projet ecrit en v2.0 accepte une seconde cadence.

    La migration replace `video.fps_source` / `video.fps_target` sur le rush et
    sur le lot; les deux lots se verifient ensuite independamment.
    """
    assert _run_cli(tmp_path, rush, 4, "--yes") == 0

    project = tmp_path / "proj"
    manifest_path = project / "project.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Retro-conversion vers la forme v2.0 telle qu'une version anterieure de
    # l'outil l'aurait ecrite.
    rush_entry = manifest["rushes"][0]
    lot = manifest["lots"][0]
    legacy_video = {
        "fps_source": rush_entry.pop("fps_source"),
        "fps_source_exact": rush_entry.pop("fps_source_exact"),
        "resolution_source": rush_entry.pop("resolution_source"),
        "fps_target": lot.pop("fps_target"),
        "fps_target_exact": lot.pop("fps_target_exact"),
    }
    for field in list(rush_entry):
        # `source_path` (story 2.8) reste sur le rush meme en v2.0: le schema
        # v2.0 le declare deja directement sous `rushes[].source_path`
        # (vestige du contrat v1), il n'a jamais ete un champ de `video`.
        if field.startswith("source_") and field not in ("source_name", "source_path"):
            legacy_video[field] = rush_entry.pop(field)
    manifest["schema_version"] = "2.0"
    manifest["video"] = legacy_video
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert _run_cli(tmp_path, rush, 2, "--yes") == 0

    migrated = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert migrated["schema_version"] == "2.1"
    assert "fps_target" not in migrated["video"]
    assert migrated["rushes"][0]["fps_source"] == 30.0
    assert {lot["fps_target"] for lot in migrated["lots"]} == {4.0, 2.0}
    for lot_id in ("rush-001_4", "rush-001_2"):
        verification = verify_extracted_lot(project, migrated, lot_id)
        assert verification.ok, (lot_id, verification.findings)


def test_refusal_returns_3_without_error_prefix(tmp_path, rush, fake_probe, fake_ffmpeg, capsys):
    # Mode non interactif sans --yes: consentement absent.
    code = _run_cli(tmp_path, rush, 4)
    assert code == 3
    captured = capsys.readouterr()
    assert "Erreur:" not in captured.err
    assert not project_layout.extract_frames_dir_from_slug(tmp_path / "proj", "rush-001_4").exists(), (
        "un refus ne cree aucun dossier de lot"
    )


def test_unknown_colorimetry_requires_a_second_consent(tmp_path, rush, fake_probe, fake_ffmpeg):
    """ARB-5: deux consentements, definitivement."""
    fake_probe(make_probe(tagged_color=False))
    assert _run_cli(tmp_path, rush, 4, "--yes") == 3
    assert _run_cli(tmp_path, rush, 4, "--yes", "--accept-unknown-color") == 0


def test_existing_lot_is_never_erased_implicitly(tmp_path, rush, fake_probe, fake_ffmpeg):
    assert _run_cli(tmp_path, rush, 4, "--yes") == 0
    assert _run_cli(tmp_path, rush, 4, "--yes") == 1
    assert _run_cli(tmp_path, rush, 4, "--yes", "--overwrite") == 0


def test_missing_video_returns_1(tmp_path, fake_probe, fake_ffmpeg):
    assert _run_cli(tmp_path, tmp_path / "absent.mov", 4, "--yes") == 1


@pytest.mark.parametrize("fps", [0, -5])
def test_non_positive_fps_returns_1(tmp_path, rush, fps, fake_probe, fake_ffmpeg):
    assert _run_cli(tmp_path, rush, fps, "--yes") == 1


def test_target_above_source_rate_returns_1(tmp_path, rush, fake_probe, fake_ffmpeg):
    assert _run_cli(tmp_path, rush, 60, "--yes") == 1


def test_vfr_source_returns_1(tmp_path, rush, fake_probe, fake_ffmpeg):
    fake_probe(make_probe(r_frame_rate="30/1", avg_frame_rate="24/1"))
    assert _run_cli(tmp_path, rush, 4, "--yes") == 1


def test_unusable_rush_name_returns_1(tmp_path, fake_probe, fake_ffmpeg):
    bad = tmp_path / "###.mov"
    bad.write_bytes(b"x")
    assert _run_cli(tmp_path, bad, 4, "--yes") == 1


def test_missing_ffmpeg_returns_2(tmp_path, rush, fake_probe, monkeypatch):
    def boom(binary="ffmpeg"):
        raise ffmpeg_utils.FfmpegNotFoundError("Binaire ffmpeg introuvable dans le PATH")

    monkeypatch.setattr(extraction.ffmpeg_utils, "ensure_ffmpeg_available", boom)
    assert _run_cli(tmp_path, rush, 4, "--yes") == 2


def test_missing_ffprobe_returns_2(tmp_path, rush, monkeypatch):
    monkeypatch.setattr(extraction.ffmpeg_utils, "ensure_ffmpeg_available", lambda b="ffmpeg": "/x")

    def boom(path, **kwargs):
        raise video_metadata.FfprobeNotFoundError("Binaire ffprobe introuvable dans le PATH")

    monkeypatch.setattr(extraction.video_metadata, "probe_media", boom)
    # `cli.py` ne mappait que FfmpegNotFoundError avant cette story.
    assert _run_cli(tmp_path, rush, 4, "--yes") == 2


def test_frame_selection_errors_map_to_1_never_a_traceback(tmp_path, rush, fake_probe, fake_ffmpeg):
    # Source vide -> EmptySourceError, sous FrameSelectionError(ValueError).
    fake_probe(make_probe(nb_frames="0", duration="0.001"))
    assert _run_cli(tmp_path, rush, 4, "--yes") in (1,)


def test_no_subcommand_still_returns_2():
    """AC 9: `2` garde son sens existant, il n'est pas surcharge."""
    assert cli.main([]) == 2


def test_extract_logger_writes_its_own_file(tmp_path, rush, fake_probe, fake_ffmpeg):
    assert _run_cli(tmp_path, rush, 4, "--yes") == 0
    log_path = tmp_path / "proj" / "logs" / "extract.log"
    assert log_path.is_file()
    content = log_path.read_text(encoding="utf-8")
    # La story 3.3 journalise son rapport dans CE logger.
    assert "Confirmation avant extraction" in content
    assert "Decision de confirmation" in content


# --------------------------------------------------------------------------
# Integration reelle (ffmpeg requis)
# --------------------------------------------------------------------------


def _make_test_rush(path: Path, *, rate: int = 30, duration: int = 4, size: str = "64x36") -> Path:
    """Fabriquer un rush de test avec ffmpeg lui-meme (`testsrc`).

    Preferable a un fichier fourni: le test reste autonome, et `testsrc` produit
    des images differentes a chaque frame, ce qui rend une duplication visible.
    """
    command = [
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"testsrc=size={size}:rate={rate}:duration={duration}",
        "-pix_fmt", "yuv420p",
        str(path),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return path


@pytest.fixture
def real_rush(tmp_path):
    return _make_test_rush(tmp_path / "rush-001.mp4")


@requires_ffmpeg
def test_integration_probe_qualifies_a_real_cfr_rush(real_rush):
    probe = video_metadata.probe_media(str(real_rush))
    qualification = extraction.qualify_source(probe)
    assert qualification.fps_source == Fraction(30, 1)
    count, is_exact = extraction.resolve_source_frame_count(real_rush, qualification)
    assert count == 120
    assert is_exact is True


@requires_ffmpeg
def test_integration_extract_writes_exactly_the_selected_frames(tmp_path, real_rush):
    project = tmp_path / "proj"
    code = cli.main(
        ["extract", "--project", str(project), "--video", str(real_rush), "--fps", "4", "--yes", "--accept-unknown-color"]
    )
    assert code == 0

    frames_dir = project_layout.extract_frames_dir_from_slug(project, "rush-001_4")
    files = sorted(frames_dir.iterdir())
    selection = select_source_frames(fps_source=30, fps_target=4, source_frame_count=120)

    # AC 6: une frame source retenue = exactement un fichier.
    assert len(files) == len(selection) == selection.expected_frame_count
    expected_names = sorted(
        build_extracted_frame_filename("rush-001", 4, frame.frame_timecode)
        for frame in selection
    )
    assert [f.name for f in files] == expected_names
    assert all(f.stat().st_size > 0 for f in files)


@requires_ffmpeg
def test_integration_written_tiff_are_really_16_bit_rgb(tmp_path, real_rush):
    project = tmp_path / "proj"
    assert cli.main(
        ["extract", "--project", str(project), "--video", str(real_rush), "--fps", "2", "--yes", "--accept-unknown-color"]
    ) == 0

    frames_dir = project_layout.extract_frames_dir_from_slug(project, "rush-001_2")
    first = sorted(frames_dir.iterdir())[0]
    probe = video_metadata.probe_media(str(first))
    stream = video_metadata._video_stream(probe)
    # ARB-4: normalisation systematique en 16 bits, meme depuis une source
    # 8 bits (`yuv420p` ici). Ce n'est pas un gain de qualite: la source
    # n'avait que 8 bits d'information, elle est seulement representee plus
    # largement.
    assert stream["pix_fmt"] == "rgb48le"
    # Mesure: ffprobe n'emet PAS `bits_per_raw_sample` sur un flux TIFF. La
    # profondeur se lit donc par la deduction du depot, celle-la meme que la
    # story 3.3 applique au rush.
    assert "bits_per_raw_sample" not in stream
    depth, origin = source_confirmation._deduce_bit_depth(stream)
    assert depth == EXTRACTION_OUTPUT_BIT_DEPTH
    assert origin == "pix_fmt"

    # La source, elle, reste declaree a 8 bits: les deux grandeurs coexistent
    # sans se confondre.
    source_stream = video_metadata._video_stream(video_metadata.probe_media(str(real_rush)))
    assert source_stream["pix_fmt"] == "yuv420p"


@requires_ffmpeg
def test_integration_no_duplicate_frames_are_produced(tmp_path, real_rush):
    """`testsrc` change a chaque frame: deux fichiers identiques = duplication."""
    import hashlib

    project = tmp_path / "proj"
    assert cli.main(
        ["extract", "--project", str(project), "--video", str(real_rush), "--fps", "5", "--yes", "--accept-unknown-color"]
    ) == 0

    frames_dir = project_layout.extract_frames_dir_from_slug(project, "rush-001_5")
    digests = [
        hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(frames_dir.iterdir())
    ]
    assert len(set(digests)) == len(digests), "aucune frame ne doit etre dupliquee"


@requires_ffmpeg
def test_integration_manifest_is_written_and_verifies(tmp_path, real_rush):
    project = tmp_path / "proj"
    assert cli.main(
        ["extract", "--project", str(project), "--video", str(real_rush), "--fps", "4", "--yes", "--accept-unknown-color"]
    ) == 0

    manifest = json.loads((project / "project.json").read_text(encoding="utf-8"))
    lot = manifest["lots"][0]
    verification = verify_extracted_lot(project, manifest, lot["lot_id"])
    assert verification.ok, verification.findings
    assert verification.digest_matches is True
    assert verification.selection_recomputed is True
    assert lot["output_bit_depth"] == 16
    assert lot["timecode_base"] == "source"


@requires_ffmpeg
def test_integration_extract_persists_absolute_resolved_source_path(tmp_path, real_rush):
    """Story 2.8, AC 1: `extract` ecrit rushes[].source_path, chemin absolu
    resolu du fichier passe a --video, et `validate_manifest` passe."""
    project = tmp_path / "proj"
    assert cli.main(
        ["extract", "--project", str(project), "--video", str(real_rush), "--fps", "4", "--yes", "--accept-unknown-color"]
    ) == 0

    manifest = json.loads((project / "project.json").read_text(encoding="utf-8"))
    source_path = manifest["rushes"][0]["source_path"]
    assert source_path == str(real_rush.resolve())
    assert Path(source_path).is_absolute()
    validate_manifest(project / "project.json")  # ne doit pas lever


@requires_ffmpeg
def test_integration_reextraction_from_a_moved_copy_replaces_source_path(tmp_path, real_rush):
    """Une re-extraction du meme rush depuis un chemin different remplace la
    valeur (AC 1) -- gabarit d'un rush deplace puis re-extrait.

    Le dossier parent garde le MEME nom (`footage`) a deux emplacements
    absolus distincts: c'est ce qui garde le rush_id inchange (ARB-9 ne
    desambiguise que sur un nom de dossier parent DIFFERENT), pour isoler la
    seule chose que ce test verifie -- le remplacement de `source_path`.
    """
    original = tmp_path / "footage" / "rush-001.mp4"
    original.parent.mkdir(parents=True)
    _make_test_rush(original)
    project = tmp_path / "proj"
    assert cli.main(
        ["extract", "--project", str(project), "--video", str(original), "--fps", "4", "--yes", "--accept-unknown-color"]
    ) == 0

    moved = tmp_path / "archive" / "footage" / "rush-001.mp4"
    moved.parent.mkdir(parents=True)
    shutil.copy(original, moved)
    assert cli.main(
        ["extract", "--project", str(project), "--video", str(moved), "--fps", "4",
         "--overwrite", "--yes", "--accept-unknown-color"]
    ) == 0

    manifest = json.loads((project / "project.json").read_text(encoding="utf-8"))
    assert len(manifest["rushes"]) == 1  # meme rush_id, pas de desambiguisation
    assert manifest["rushes"][0]["source_path"] == str(moved.resolve())


@requires_ffmpeg
def test_integration_fractional_target_rate_really_works(tmp_path, real_rush):
    """12.5 im/s de bout en bout, sur un vrai binaire (decision 2, ARB-3)."""
    project = tmp_path / "proj"
    assert cli.main(
        ["extract", "--project", str(project), "--video", str(real_rush), "--fps", "12.5", "--yes", "--accept-unknown-color"]
    ) == 0

    frames_dir = project_layout.extract_frames_dir_from_slug(project, "rush-001_12p5")
    files = sorted(frames_dir.iterdir())
    selection = select_source_frames(fps_source=30, fps_target=12.5, source_frame_count=120)
    assert len(files) == selection.expected_frame_count
    assert files[0].name.startswith("rush-001_12p5_")


@requires_ffmpeg
def test_integration_refusal_writes_nothing_at_all(tmp_path, real_rush):
    project = tmp_path / "proj"
    # Sans --yes et sans TTY: refus.
    assert cli.main(
        ["extract", "--project", str(project), "--video", str(real_rush), "--fps", "4"]
    ) == 3
    assert not project_layout.extract_frames_dir_from_slug(project, "rush-001_4").exists()
    assert not (project / "project.json").exists()


@requires_ffmpeg
def test_integration_large_selection_crosses_the_chunk_boundary(tmp_path):
    """Verifie le decoupage en plusieurs invocations sur un cas reel."""
    rush = _make_test_rush(tmp_path / "long-rush.mp4", rate=30, duration=4, size="32x18")
    temp_dir = tmp_path / "tmp"
    indices = list(range(0, 120))
    paths = ffmpeg_utils.extract_selected_frames(
        rush, temp_dir, indices, max_select_terms=25
    )
    assert len(paths) == len(indices)
    assert all(path.is_file() for path in paths)
    # Les noms sont calcules, jamais retrouves par glob + sorted.
    assert paths[0].name == "mmu_extract_00000000.tiff"
    assert paths[-1].name == "mmu_extract_00000119.tiff"


@requires_ffmpeg
def test_integration_poc_baseline_still_green(tmp_path):
    """La baseline story 1.1 n'est pas affectee par ce chemin neuf."""
    rush = _make_test_rush(tmp_path / "poc.mp4", rate=10, duration=2, size="128x72")
    frames = ffmpeg_utils.extract_frames(rush, tmp_path / "poc-frames", 2)
    assert frames
    assert all(f.suffix == ".png" for f in frames)


# --------------------------------------------------------------------------
# Revue du 2026-08-05: le rapport d'auto-controle doit etre visible
# --------------------------------------------------------------------------


def _outcome_with(verification):
    """Objet minimal portant le rapport, comme `ExtractionOutcome` le fait."""
    return SimpleNamespace(persisted=SimpleNamespace(verification=verification))


def _verification(*, ok_findings=(), missing=(), nonconforming=()):
    return LotVerification(
        lot_id="rush-001_4",
        frames_dir=f"{project_layout.EXTRACT_FRAMES_DIRNAME}/rush-001_4",
        expected_frame_count=14,
        observed_frame_count=14 - len(missing),
        missing_frames=tuple(missing),
        unexpected_files=(),
        nonconforming_files=tuple(nonconforming),
        selection_recomputed=True,
        digest_matches=True,
        findings=tuple(ok_findings),
    )


def test_un_auto_controle_negatif_fait_echouer_la_commande(tmp_path, rush, fake_probe, fake_ffmpeg):
    """ARB-7: un lot connu incomplet ne sort pas comme un succes.

    Les fichiers restent sur le disque -- les effacer detruirait
    l'information de diagnostic -- mais le code de sortie dit l'echec.
    """
    fake_probe(make_probe())
    assert _run_cli(tmp_path, rush, 4, "--yes") == 0

    frames_dir = project_layout.extract_frames_dir_from_slug(tmp_path / "proj", "rush-001_4")
    victimes = sorted(frames_dir.iterdir())[:3]
    for victime in victimes:
        victime.unlink()

    # Re-verifier le lot ampute par le chemin nominal de la commande.
    from mixed_media_utility.io.manifest import load_manifest
    from mixed_media_utility.io.extraction_manifest import verify_extracted_lot

    manifest = load_manifest(tmp_path / "proj" / "project.json")
    rapport = verify_extracted_lot(tmp_path / "proj", manifest, "rush-001_4")
    assert rapport.ok is False

    sortie = cli._print_extraction_verification(_outcome_with(rapport))
    assert sortie is False, "un lot non conforme doit faire echouer la commande"


def test_un_lot_ampute_ne_sort_plus_de_extract_comme_un_succes_muet(capsys):
    """La persistance detectait le probleme et personne ne l'affichait.

    Un lot ampute de trois images sur quatorze etait ecrit, le manifest le
    declarait complet, l'auto-controle le detectait, et la commande se
    terminait sur « extract termine avec succes » sans un mot de plus.
    """
    verification = _verification(
        ok_findings=(VERIFY_MISSING_FRAMES,),
        missing=("a.tiff", "b.tiff", "c.tiff"),
    )
    assert verification.ok is False

    cli._print_extraction_verification(_outcome_with(verification))

    sortie = capsys.readouterr().out
    assert "ATTENTION" in sortie
    assert VERIFY_MISSING_FRAMES in sortie
    assert "3" in sortie
    assert "n'est PAS conforme" in sortie
    assert "--overwrite" in sortie, "le message doit proposer la reprise"


def test_un_lot_conforme_n_affiche_aucune_alerte(capsys):
    cli._print_extraction_verification(_outcome_with(_verification()))

    assert capsys.readouterr().out == ""


def test_une_reserve_informative_est_dite_sans_etre_presentee_comme_un_echec(capsys):
    """`CARDINAL_SOURCE_NON_EXACT` ne rend pas le lot non conforme, mais se dit."""
    verification = _verification(ok_findings=(VERIFY_SOURCE_COUNT_NOT_EXACT,))
    assert verification.ok is True

    cli._print_extraction_verification(_outcome_with(verification))

    sortie = capsys.readouterr().out
    assert "ATTENTION" not in sortie
    assert VERIFY_SOURCE_COUNT_NOT_EXACT in sortie
    assert "lot conforme" in sortie


def test_l_absence_de_rapport_n_est_pas_une_erreur(capsys):
    cli._print_extraction_verification(SimpleNamespace(persisted=None))
    cli._print_extraction_verification(SimpleNamespace())

    assert capsys.readouterr().out == ""


def test_a_failed_overwrite_leaves_the_previous_lot_intact(
    tmp_path, rush, fake_probe, fake_ffmpeg, monkeypatch
):
    """Revue du 2026-08-05: `--overwrite` detruisait avant de savoir s'il pouvait remplacer.

    Le nettoyage du lot precedent avait lieu **avant** l'appel a ffmpeg. Un
    echec d'extraction laissait donc un dossier de lot vide pendant que le
    manifest continuait de declarer le lot complet: le manifest mentait sur un
    lot inexistant, soit exactement le mode de defaillance que l'AC 6 existe
    pour fermer.
    """
    assert _run_cli(tmp_path, rush, 4, "--yes") == 0
    frames_dir = project_layout.extract_frames_dir_from_slug(tmp_path / "proj", "rush-001_4")
    avant = sorted(path.name for path in frames_dir.iterdir() if path.is_file())
    assert avant, "le premier lot doit exister"

    def echec(*args, **kwargs):
        raise ffmpeg_utils.FrameExtractionError("ffmpeg a echoue en cours d'extraction")

    monkeypatch.setattr(ffmpeg_utils, "extract_selected_frames", echec)

    assert _run_cli(tmp_path, rush, 4, "--yes", "--overwrite") == 1

    apres = sorted(path.name for path in frames_dir.iterdir() if path.is_file())
    assert apres == avant, (
        "un remplacement qui echoue ne doit pas detruire le lot valide qu'il "
        "pretendait remplacer"
    )


def test_a_successful_overwrite_still_replaces_the_previous_lot(
    tmp_path, rush, fake_probe, fake_ffmpeg
):
    """Le pendant du test precedent: le remplacement reussi remplace bien."""
    assert _run_cli(tmp_path, rush, 4, "--yes") == 0
    frames_dir = project_layout.extract_frames_dir_from_slug(tmp_path / "proj", "rush-001_4")
    intrus = frames_dir / "rush-001_4_99-99-99-99.tiff"
    intrus.write_bytes(b"lot precedent")

    assert _run_cli(tmp_path, rush, 4, "--yes", "--overwrite") == 0

    assert not intrus.exists(), "le lot precedent doit avoir ete retire"
    assert not (frames_dir / ffmpeg_utils.EXTRACT_TEMP_DIRNAME).exists()


def test_no_directory_is_created_before_the_inputs_are_validated(tmp_path, fake_probe, fake_ffmpeg):
    """Revue du 2026-08-05: l'arborescence etait creee avant toute validation.

    `extract --project <dossier> --video <absent>` creait `frames/`, `logs/`,
    `planches/` et le reste, puis echouait. Avec `--project /`, ces dossiers
    etaient reellement crees a la racine du systeme.
    """
    projet = tmp_path / "proj"

    assert _run_cli(tmp_path, tmp_path / "absent.mov", 4, "--yes") == 1

    assert not projet.exists(), (
        "aucun dossier ne doit etre cree tant que les entrees ne sont pas validees"
    )


@pytest.mark.parametrize("fps", [0, -5, float("nan"), float("inf")])
def test_an_invalid_fps_creates_nothing_either(tmp_path, rush, fps, fake_probe, fake_ffmpeg):
    assert _run_cli(tmp_path, rush, fps, "--yes") == 1
    assert not (tmp_path / "proj").exists()


def _journal(tmp_path) -> str:
    """Contenu du journal de `extract`, ou le logger de la commande ecrit.

    `_configure_extract_logger` coupe la propagation, donc `caplog` ne voit
    rien: le journal du projet est la trace reelle.
    """
    return (tmp_path / "proj" / project_layout.LOGS_DIRNAME / "extract.log").read_text(
        encoding="utf-8"
    )


def test_une_cadence_non_corroborable_est_refusee(
    tmp_path, rush, fake_probe, fake_ffmpeg, monkeypatch
):
    """ARB-6: un conteneur qui ne permet aucun recoupement fait echouer extract.

    Un conteneur qui ne declare ni la duree du flux ni son nombre d'images
    neutralise les deux garde-fous contre une cadence variable d'un coup.
    Reproduit sur Matroska avant l'arbitrage: la commande rendait un succes et
    le manifest declarait une cadence fausse. Egan a tranche le refus, cout
    assume: il refuse aussi des rushs sains dont le conteneur est avare en
    metadonnees.
    """
    probe = make_probe()
    for stream in probe["streams"]:
        stream.pop("duration", None)
        stream.pop("nb_frames", None)
    fake_probe(probe)
    # Le conteneur ne declare rien: le cardinal ne peut venir que du comptage
    # exact, qui est justement le chemin emprunte sur un Matroska.
    monkeypatch.setattr(extraction, "count_frames_exact", lambda *a, **k: 100)

    assert _run_cli(tmp_path, rush, 4, "--yes") == 1

    journal = _journal(tmp_path)
    assert "inverifiable" in journal
    assert "reencoder" in journal.lower(), "le message doit proposer la sortie"
    assert not project_layout.extract_frames_dir_from_slug(tmp_path / "proj", "rush-001_4").exists(), (
        "un refus ne cree aucun dossier de lot"
    )


def test_une_cadence_corroborable_passe_sans_obstacle(
    tmp_path, rush, fake_probe, fake_ffmpeg
):
    """Le pendant: le refus ne doit pas devenir un obstacle permanent."""
    fake_probe(make_probe())

    assert _run_cli(tmp_path, rush, 4, "--yes") == 0

    assert "inverifiable" not in _journal(tmp_path)


def test_la_qualification_dit_si_la_cadence_est_corroborable():
    """Propriete pure, verifiee sur les deux formes de corroboration."""
    base = dict(fps_source=Fraction(25), start_timecode=None, avg_frame_rate=Fraction(25))

    par_la_duree = extraction.SourceQualification(
        stream_duration_seconds=4.0, declared_frame_count=None, **base
    )
    par_le_cardinal = extraction.SourceQualification(
        stream_duration_seconds=None, declared_frame_count=100, **base
    )
    aveugle = extraction.SourceQualification(
        stream_duration_seconds=None, declared_frame_count=None, **base
    )

    assert par_la_duree.cadence_corroboree is True
    assert par_le_cardinal.cadence_corroboree is True
    assert aveugle.cadence_corroboree is False


# --------------------------------------------------------------------------
# ARB-9: identite d'un rush par nom + dossier parent
# --------------------------------------------------------------------------


def test_arb9_deux_rushs_homonymes_ne_s_ecrasent_plus(tmp_path, fake_probe, fake_ffmpeg):
    """Cas de tournage multicamera: A-CAM/prise01.mov et B-CAM/prise01.mov.

    Ils etaient le **meme** rush pour l'outil: le second ecrasait le premier et
    le message d'erreur poussait vers --overwrite, c'est-a-dire vers la
    destruction. Rien au manifest ne permettait ensuite de savoir lequel des
    deux avait fourni les images.

    **La FORME du suffixe a change le 2026-09-05** (`EPIC11-ARB-233`) et
    l'assertion suit. Elle exigeait un identifiant finissant par `cam`, c'est-a
    -dire par le nom du dossier parent ; le suffixe est desormais un RANG
    (`prise01`, puis `prise01-2`), calcule par `io/version_ranks.py`. Ce que
    l'arbitrage ne change PAS sur ce chemin-ci, et le test le mesure toujours :
    `EPIC11-ARB-9` joue -- les deux rushs coexistent, aucun n'est ecrase --, et
    le dossier reste ecrit au manifeste sous `source_parent`, ou il nomme la
    provenance. Il a cesse d'etre le NOM, il n'a pas cesse d'etre une donnee.

    **Pourquoi ce chemin suit alors qu'`EPIC11-ARB-83` l'exempte du reste.**
    `run_extraction` ne peut pas sonder la source avant la transition d'etat du
    lot, donc le dossier y demeure le CRITERE de dernier recours
    (`extraction.CRITERE_DE_DERNIER_RECOURS`, regime `mesures is None`). Mais
    critere et nom sont deux roles : le laisser NOMMER par le dossier pendant
    que `project add-rush` nomme par le rang donnerait deux identifiants au meme
    rush selon la porte d'entree. La frontiere qui le tient est
    `test_rang_de_desambiguisation::test_D2_aucun_appelant_ne_passe_le_DOSSIER_
    a_la_levee_d_homonymie`.
    """
    fake_probe(make_probe())
    for camera in ("A-CAM", "B-CAM"):
        dossier = tmp_path / camera
        dossier.mkdir()
        (dossier / "prise01.mov").write_bytes(b"source " + camera.encode())

    assert _run_cli(tmp_path, tmp_path / "A-CAM" / "prise01.mov", 4, "--yes") == 0
    assert _run_cli(tmp_path, tmp_path / "B-CAM" / "prise01.mov", 4, "--yes") == 0

    manifest = json.loads((tmp_path / "proj" / "project.json").read_text())
    identifiants = sorted(rush["rush_id"] for rush in manifest["rushes"])

    assert len(identifiants) == 2, "les deux rushs doivent coexister"
    assert "prise01" in identifiants
    assert identifiants == ["prise01", "prise01-2"], (
        "le second doit etre desambigue par un RANG (EPIC11-ARB-233), et le "
        "premier doit rester intact sous son nom d'origine"
    )
    # Volet negatif de l'arbitrage : le nom du dossier ne figure dans AUCUN des
    # deux identifiants. Un `endswith('cam')` ne le dirait pas -- il serait vert
    # sur `prise01-B-CAM` comme sur `prise01-2`.
    for ident in identifiants:
        assert "cam" not in ident.lower(), ident
    dossiers = sorted(rush.get("source_parent") for rush in manifest["rushes"])
    assert dossiers == ["A-CAM", "B-CAM"]


def test_arb9_le_dossier_parent_est_un_nom_jamais_un_chemin(tmp_path, fake_probe, fake_ffmpeg):
    """`source_parent` reste un nom, jamais un chemin: le seul endroit du
    manifest ou un chemin machine apparait est `rushes[].source_path`
    (story 2.8, AC 1, EPIC7-ARB-41) -- SEULE exception nommee a la
    portabilite du projet, qui interdit partout ailleurs tout chemin absolu."""
    fake_probe(make_probe())
    dossier = tmp_path / "A-CAM"
    dossier.mkdir()
    rush = dossier / "prise01.mov"
    rush.write_bytes(b"source")

    assert _run_cli(tmp_path, rush, 4, "--yes") == 0

    manifest = json.loads((tmp_path / "proj" / "project.json").read_text())
    assert manifest["rushes"][0]["source_parent"] == "A-CAM"
    assert manifest["rushes"][0]["source_path"] == str(rush.resolve())

    sans_source_path = json.loads(json.dumps(manifest))
    del sans_source_path["rushes"][0]["source_path"]
    assert str(tmp_path) not in json.dumps(sans_source_path), (
        "aucun chemin machine dans le manifest hors de rushes[].source_path"
    )
    validate_manifest(tmp_path / "proj" / "project.json")


def test_arb9_le_meme_rush_reextrait_ne_se_dedouble_pas(tmp_path, fake_probe, fake_ffmpeg):
    """Le pendant: meme nom ET meme dossier, c'est bien le meme rush."""
    fake_probe(make_probe())
    dossier = tmp_path / "A-CAM"
    dossier.mkdir()
    rush = dossier / "prise01.mov"
    rush.write_bytes(b"source")

    assert _run_cli(tmp_path, rush, 4, "--yes") == 0
    assert _run_cli(tmp_path, rush, 2, "--yes") == 0

    manifest = json.loads((tmp_path / "proj" / "project.json").read_text())
    assert len(manifest["rushes"]) == 1
    assert len(manifest["lots"]) == 2, "deux cadences du meme rush"


# --------------------------------------------------------------------------
# Story 3.7 -- bornes de timecode sur la ligne de commande (AC 5, 10, 11)
# --------------------------------------------------------------------------


BORNE_IN = "00:00:01:00"   # index 30 a 30 im/s
BORNE_OUT = "00:00:02:29"  # index 89: fenetre de 60 images


def _selection_bornee(**kwargs):
    return select_source_frames(
        fps_source=30,
        fps_target=4,
        source_frame_count=100,
        source_in_timecode=BORNE_IN,
        source_out_timecode=BORNE_OUT,
        **kwargs,
    )


@pytest.fixture
def bornes_recues(monkeypatch):
    """Capturer les bornes telles qu'elles arrivent au noyau, jamais avant.

    Le seul point de mesure qui prouve quelque chose: entre `argparse` et
    `run_extraction`, c'est `extract_command` qui lit les attributs, et c'est
    la que le piege du mot-cle Python se refermerait.
    """
    recues = {}

    def capture(**kwargs):
        recues.update(kwargs)
        raise extraction.ExtractionInputError("interruption volontaire du test")

    monkeypatch.setattr(extraction, "run_extraction", capture)
    return recues


def test_l_option_in_est_atteignable_malgre_le_mot_cle_python(
    tmp_path, rush, fake_probe, bornes_recues
):
    """AC 5: `args.in` est une SyntaxError, donc `dest=` n'est pas optionnel.

    Sans `dest=`, `argparse` range la valeur sous l'attribut `in`, que
    `extract_command` ne peut pas lire: la commande leverait une
    `AttributeError` au lieu d'extraire, et la borne saisie serait perdue en
    silence si quelqu'un ajoutait un `getattr(args, 'in', None)` complaisant.
    """
    _run_cli(tmp_path, rush, 4, "--yes", "--in", BORNE_IN, "--out", BORNE_OUT)

    assert bornes_recues["source_in_timecode"] == BORNE_IN
    assert bornes_recues["source_out_timecode"] == BORNE_OUT


def test_les_bornes_sont_absentes_par_defaut(tmp_path, rush, fake_probe, bornes_recues):
    """AC 14: aucune valeur par defaut n'imite une borne."""
    _run_cli(tmp_path, rush, 4, "--yes")

    assert bornes_recues["source_in_timecode"] is None
    assert bornes_recues["source_out_timecode"] is None


def test_une_extraction_bornee_n_ecrit_que_la_fenetre_demandee(
    tmp_path, rush, fake_probe, fake_ffmpeg
):
    """AC 4 et 8 vus depuis la ligne de commande."""
    code = _run_cli(tmp_path, rush, 4, "--yes", "--in", BORNE_IN, "--out", BORNE_OUT)
    assert code == 0

    selection = _selection_bornee()
    assert selection.expected_frame_count == 8, "fenetre de 60 images, pas 100"

    project = tmp_path / "proj"
    manifest = json.loads((project / "project.json").read_text(encoding="utf-8"))
    lot = manifest["lots"][0]
    assert lot["source_in_timecode"] == BORNE_IN
    assert lot["source_out_timecode"] == BORNE_OUT
    assert lot["expected_frame_count"] == 8

    frames_dir = project / lot["frames_dir"]
    written = sorted(p.name for p in frames_dir.iterdir())
    assert written == sorted(
        build_extracted_frame_filename("rush-001", 4, frame.frame_timecode)
        for frame in selection
    )
    assert written[0] == "rush-001_4_00-00-01-00.tiff", (
        "la premiere image retenue est la borne d'entree elle-meme"
    )

    verification = verify_extracted_lot(project, manifest, lot["lot_id"])
    assert verification.ok, verification.findings


def test_un_extrait_n_ecrase_jamais_l_extraction_complete_du_meme_rush(
    tmp_path, rush, fake_probe, fake_ffmpeg
):
    """AC 6 de bout en bout: meme rush, meme cadence, deux lots distincts."""
    assert _run_cli(tmp_path, rush, 4, "--yes") == 0
    assert _run_cli(tmp_path, rush, 4, "--yes", "--in", BORNE_IN, "--out", BORNE_OUT) == 0

    project = tmp_path / "proj"
    manifest = json.loads((project / "project.json").read_text(encoding="utf-8"))
    assert len(manifest["rushes"]) == 1
    assert len(manifest["lots"]) == 2

    dossiers = {lot["frames_dir"] for lot in manifest["lots"]}
    assert len(dossiers) == 2, "deux lots ne partagent jamais un dossier"
    assert f"{project_layout.EXTRACT_FRAMES_DIRNAME}/rush-001_4" in dossiers

    for lot in manifest["lots"]:
        verification = verify_extracted_lot(project, manifest, lot["lot_id"])
        assert verification.ok, (lot["lot_id"], verification.findings)
    validate_manifest(project / "project.json")


def test_deux_extraits_distincts_du_meme_rush_coexistent(
    tmp_path, rush, fake_probe, fake_ffmpeg
):
    assert _run_cli(tmp_path, rush, 4, "--yes", "--in", BORNE_IN, "--out", BORNE_OUT) == 0
    assert _run_cli(
        tmp_path, rush, 4, "--yes", "--in", "00:00:00:00", "--out", "00:00:01:29"
    ) == 0

    manifest = json.loads(
        (tmp_path / "proj" / "project.json").read_text(encoding="utf-8")
    )
    assert len({lot["frames_dir"] for lot in manifest["lots"]}) == 2


def test_une_seule_borne_suffit(tmp_path, rush, fake_probe, fake_ffmpeg):
    """AC 1: `--out` seul borne le debut a l'index 0."""
    assert _run_cli(tmp_path, rush, 4, "--yes", "--out", "00:00:01:29") == 0

    manifest = json.loads(
        (tmp_path / "proj" / "project.json").read_text(encoding="utf-8")
    )
    lot = manifest["lots"][0]
    assert "source_in_timecode" not in lot
    assert lot["source_out_timecode"] == "00:00:01:29"
    assert lot["expected_frame_count"] == select_source_frames(
        fps_source=30,
        fps_target=4,
        source_frame_count=100,
        source_out_timecode="00:00:01:29",
    ).expected_frame_count


@pytest.mark.parametrize(
    "bornes,attendu",
    [
        (["--in", "00:00:02:00", "--out", "00:00:01:00"], "posterieure"),
        (["--out", "00:01:00:00"], "hors du rush"),
        (["--in", "pas-un-timecode"], "source_in_timecode"),
        (["--in", "00:00:01;00"], "source_in_timecode"),
    ],
    ids=["in-apres-out", "out-hors-du-rush", "malforme", "drop-frame"],
)
def test_une_borne_invalide_est_refusee_proprement(
    tmp_path, rush, fake_probe, fake_ffmpeg, capsys, bornes, attendu
):
    """AC 3 et 5: refus lisible, code 1, aucune trace Python, aucun lot."""
    code = _run_cli(tmp_path, rush, 4, "--yes", *bornes)
    assert code == 1

    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert attendu in captured.err
    # Story 11.14, lot E1 -- **ce temoin avait cesse de mesurer, et il etait
    # VERT.** Il composait `proj / "frames"` en dur ; le renommage du lot B a
    # fait que ce dossier n'existe plus jamais, si bien que le premier terme du
    # `or` etait vrai **par construction** : l'assertion serait restee verte
    # meme si un refus de borne avait ecrit un lot entier. C'est le mode de
    # panne que le lot D2 a nomme -- un vert coute plus cher qu'un rouge,
    # puisque rien ne le signale.
    #
    # La forme est donc renforcee sur les deux axes a la fois : on regarde les
    # DEUX racines (`EPIC11-ARB-222` : l'ancienne reste lue indefiniment, et un
    # lot ecrit la serait tout aussi fautif), et on cherche les **fichiers**
    # plutot que l'existence du dossier -- `ensure_project_layout` cree la
    # racine, donc « le dossier n'existe pas » ne dit rien du contenu.
    ecrits = [
        chemin
        for racine in project_layout.racines_de_frames_extraites(tmp_path / "proj")
        for chemin in racine.rglob("*")
        if chemin.is_file()
    ]
    assert ecrits == [], (
        f"une borne refusee ne laisse aucun lot derriere elle : {ecrits}"
    )


def test_le_refus_du_plafond_nomme_les_bornes(tmp_path, rush, fake_probe, fake_ffmpeg, capsys):
    """AC 11: le message doit dire comment s'en sortir, pas seulement que ca coince.

    30 im/s vers 30 im/s sur 20 000 images: 20 000 images seraient extraites,
    vingt fois le plafond.
    """
    fake_probe(make_probe(nb_frames="20000", duration="666.666667"))
    code = _run_cli(tmp_path, rush, 30, "--yes")
    assert code == 1

    message = capsys.readouterr().err
    assert "--in" in message and "--out" in message
    assert "1000" in message


def test_la_cadence_de_repli_annoncee_porte_sur_la_fenetre_deja_bornee(
    tmp_path, rush, fake_probe, fake_ffmpeg, capsys
):
    """AC 11, second volet: le denominateur est la fenetre, jamais le fichier.

    Un operateur ayant deja borne son extrait doit se voir conseiller une
    cadence qui fait rentrer **sa fenetre**. Avec `frame_count` au
    denominateur, le conseil serait ici quatre fois trop bas -- et suivi a la
    lettre, il produirait un lot inutilement pauvre.
    """
    fake_probe(make_probe(nb_frames="20000", duration="666.666667"))
    # Fenetre de 5000 images (indices 0 a 4999) sur un fichier de 20 000.
    code = _run_cli(tmp_path, rush, 30, "--yes", "--out", "00:02:46:19")
    assert code == 1

    message = capsys.readouterr().err
    conseillee = float(
        message.split("cadence d'au plus ")[1].split(" im/s")[0]
    )
    rentre = select_source_frames(
        fps_source=30,
        fps_target=conseillee,
        source_frame_count=20000,
        source_out_timecode="00:02:46:19",
    )
    assert rentre.expected_frame_count <= 1000
    assert conseillee > 1.5, (
        "avec 20 000 au denominateur au lieu de 5 000, le conseil tomberait a "
        "1.5 im/s: quatre fois trop bas"
    )


def test_le_rapport_de_confirmation_annonce_l_extrait_avant_son_compte(
    tmp_path, rush, fake_probe, fake_ffmpeg, capsys
):
    """AC 10 sur le chemin reel, du parseur jusqu'a l'ecran.

    Le test unitaire du rendu (`test_source_confirmation.py`) travaille sur une
    selection bouchonnee: il prouve l'ordre des lignes, pas que les bornes
    saisies sur la ligne de commande parviennent bien jusqu'a ce rendu.
    """
    assert _run_cli(tmp_path, rush, 4, "--yes", "--in", BORNE_IN, "--out", BORNE_OUT) == 0

    lignes = capsys.readouterr().out.splitlines()
    rang_in = next(i for i, l in enumerate(lignes) if "Borne d'entree" in l)
    rang_out = next(i for i, l in enumerate(lignes) if "Borne de sortie" in l)
    rang_compte = next(i for i, l in enumerate(lignes) if "expected_frame_count" in l)

    assert rang_in < rang_out < rang_compte
    assert BORNE_IN in lignes[rang_in]
    assert BORNE_OUT in lignes[rang_out]


def test_une_extraction_complete_n_annonce_aucune_borne(
    tmp_path, rush, fake_probe, fake_ffmpeg, capsys
):
    assert _run_cli(tmp_path, rush, 4, "--yes") == 0
    sortie = capsys.readouterr().out
    assert "Borne d'entree" not in sortie
    assert "Borne de sortie" not in sortie


def test_un_nom_de_rush_trop_long_pour_une_borne_est_refuse_avant_tout(
    tmp_path, fake_probe, fake_ffmpeg, capsys
):
    """Revue du 2026-08-06, arbitrage option c.

    Le refus doit atteindre l'operateur en clair, sortir en code 1, et ne rien
    laisser derriere lui: c'est tout l'interet de refuser plutot que d'ecrire
    un lot dont l'identifiant et le dossier se contredisent.
    """
    rush = tmp_path / "A005_C012_20260806_TOURNAGE_PLATEAU_PRISE_04.mov"
    rush.write_bytes(b"source")

    assert _run_cli(tmp_path, rush, 4, "--yes") == 0, "le rush entier passe"
    capsys.readouterr()

    code = _run_cli(tmp_path, rush, 4, "--yes", "--in", BORNE_IN, "--out", BORNE_OUT)
    assert code == 1

    erreur = capsys.readouterr().err
    assert "Traceback" not in erreur
    assert "renommer" in erreur.lower()
    dossiers = {p.name for p in (tmp_path / "proj" / project_layout.EXTRACT_FRAMES_DIRNAME).iterdir()}
    assert dossiers == {"A005_C012_20260806_TOURNAGE_PLATEAU_PRISE_04_4"}, (
        "aucun dossier de lot borne n'a ete cree"
    )


def test_la_garde_de_forme_refuse_un_slug_ampute_de_son_condensat(monkeypatch):
    """Revue du 2026-08-06: le filet avait une maille manquante.

    Il attrapait un condensat **faux**, mais laissait passer un condensat
    **absent** -- alors que c'est l'absence qui ferait qu'un extrait ecrase
    l'extraction complete, precisement la collision que l'AC 6 existe pour
    empecher. Un refactor futur qui oublierait le suffixe passait « conforme ».
    """
    from mixed_media_utility.io.naming import format_fps_short

    monkeypatch.setattr(
        extraction.project_layout,
        "rush_dir_slug",
        lambda rush_id, fps, **_: f"{rush_id}_{format_fps_short(fps)}",
    )
    with pytest.raises(extraction.ExtractionInputError) as refus:
        extraction.check_fps_form_consistency(
            "rush-001",
            5,
            source_in_timecode="00:00:01:00",
            source_out_timecode="00:00:02:00",
        )
    assert "condensat de bornes" in str(refus.value)


# ===========================================================================
# Story 5.28 -- `run_extraction` TRANSMET le rappel, et n'en calcule rien
# ===========================================================================


def test_run_extraction_transmet_le_rappel_a_l_extraction_ffmpeg(
    tmp_path, rush, fake_probe, monkeypatch
):
    """AC 4 et AC 8: le rappel traverse `run_extraction` tel quel.

    `run_extraction` ne calcule aucun temps: le seul point de mesure qui
    prouve quelque chose est ce que `extract_selected_frames` recoit.
    """
    recus = {}

    def extraction_espionne(video_path, temp_dir, source_indices, **kwargs):
        recus.update(kwargs)
        temp_dir = Path(temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)
        chemins = []
        for rang, _ in enumerate(source_indices):
            chemin = ffmpeg_utils.temp_frame_path(temp_dir, rang)
            chemin.write_bytes(b"fake tiff")
            chemins.append(chemin)
        return chemins

    monkeypatch.setattr(
        extraction.ffmpeg_utils, "extract_selected_frames", extraction_espionne
    )
    monkeypatch.setattr(
        extraction.ffmpeg_utils, "ensure_ffmpeg_available", lambda b="ffmpeg": "/x/ffmpeg"
    )

    def rappel(faites, total):
        pass

    extraction.run_extraction(
        project_dir=tmp_path / "proj",
        video_path=rush,
        fps_target=4,
        consent_granted=True,
        logger=logging.getLogger("test-5-28"),
        rappel_progression=rappel,
    )
    assert recus["rappel_progression"] is rappel


def test_sans_rappel_run_extraction_en_transmet_un_qui_vaut_None(
    tmp_path, rush, fake_probe, monkeypatch
):
    """AC 8 (`AR3`): le repli sans rappel est le comportement d'aujourd'hui."""
    recus = {}

    def extraction_espionne(video_path, temp_dir, source_indices, **kwargs):
        recus.update(kwargs)
        temp_dir = Path(temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)
        return [
            _ecrire_temporaire(temp_dir, rang) for rang, _ in enumerate(source_indices)
        ]

    monkeypatch.setattr(
        extraction.ffmpeg_utils, "extract_selected_frames", extraction_espionne
    )
    monkeypatch.setattr(
        extraction.ffmpeg_utils, "ensure_ffmpeg_available", lambda b="ffmpeg": "/x/ffmpeg"
    )
    extraction.run_extraction(
        project_dir=tmp_path / "proj",
        video_path=rush,
        fps_target=4,
        consent_granted=True,
        logger=logging.getLogger("test-5-28"),
    )
    assert recus["rappel_progression"] is None


def _ecrire_temporaire(temp_dir, rang):
    chemin = ffmpeg_utils.temp_frame_path(temp_dir, rang)
    chemin.write_bytes(b"fake tiff")
    return chemin


def test_la_cli_extract_ne_passe_aucun_rappel_de_progression(
    tmp_path, rush, fake_probe, bornes_recues
):
    """AC 8: la CLI ne change pas -- aucune option, aucun libelle, aucun rappel.

    Le point de mesure est le meme que celui des bornes: entre `argparse` et
    `run_extraction`, c'est `extract_command` qui compose l'appel.
    """
    _run_cli(tmp_path, rush, 4, "--yes")
    assert "rappel_progression" not in bornes_recues


def test_le_lot_extrait_est_identique_avec_et_sans_rappel(
    tmp_path, rush, fake_probe, fake_ffmpeg
):
    """AC 8 et AC 11: memes fichiers, memes noms, **meme manifest**.

    Deux projets distincts, meme rush, meme selection: la progression est
    observationnelle et ne touche a aucun artefact.

    Le manifest fait partie de la comparaison (revue de vague 2 bis, F9) :
    l'exclure par extension reduisait « meme rapport » a une egalite de chemin,
    alors que le pendant cote `scan write` compare le `LotOutputReport` entier.
    Seuls les deux champs que le coeur declare lui-meme non idempotents sont
    retires, **nommement**.

    Et les jalons sont assertes (BH-7) : une liste construite et jamais lue est
    un mensonge de banc.

    **L'assertion de jalons etait TAUTOLOGIQUE, et corrigee le 2026-09-06.**
    Elle disait `assert jalons` puis `jalons[-1] == (total, total)` : un coeur
    n'emettant QU'UN seul jalon, celui de la fin, passait ces deux lignes. Or
    c'est exactement le symptome remonte du terrain le jour meme -- « la barre
    de progression saute de 0 a 100. Pas eu l'impression de voir les frames
    progresser » --, et ce banc ne l'aurait pas vu. Ce qui distingue une
    progression d'une annonce de fin est le **palier intermediaire**, et rien
    d'autre : au moins un jalon `0 < faites < total`. Le modele est
    `Journal.paliers_intermediaires` de `tests/unit/test_ffmpeg_utils.py`, ou
    la propriete est nommee depuis la story 5.28.
    """
    jalons = []
    # Meme NOM de projet des deux cotes, parents differents : `project_id` est
    # derive du nom du dossier, et deux noms differents feraient diverger le
    # manifest pour une raison qui n'a rien a voir avec la progression.
    sans_dir = tmp_path / "passe-sans" / "projet"
    avec_dir = tmp_path / "passe-avec" / "projet"

    sans = extraction.run_extraction(
        project_dir=sans_dir,
        video_path=rush,
        fps_target=4,
        consent_granted=True,
        logger=logging.getLogger("test-5-28"),
    )
    avec = extraction.run_extraction(
        project_dir=avec_dir,
        video_path=rush,
        fps_target=4,
        consent_granted=True,
        logger=logging.getLogger("test-5-28"),
        rappel_progression=lambda faites, total: jalons.append((faites, total)),
    )

    assert sans.granted and avec.granted
    assert _empreinte_du_lot(sans_dir) == _empreinte_du_lot(avec_dir)
    assert sans.frames_dir_relative == avec.frames_dir_relative

    assert jalons, "aucun jalon recu: le rappel n'a traverse aucune ligne du coeur"
    faits = [faites for faites, _ in jalons]
    assert faits == sorted(faits)
    total = jalons[-1][1]
    paliers = [(faites, vu) for faites, vu in jalons if 0 < faites < vu]
    assert paliers, (
        "aucun palier INTERMEDIAIRE : le coeur n'a emis que l'annonce de fin,"
        " ce qui donne a l'operateur une barre qui saute de 0 a 100 --"
        f" jalons recus : {jalons}")
    assert jalons[-1] == (total, total)
    assert all(vu == total for _, vu in jalons)


def test_le_manifest_est_le_meme_avec_et_sans_rappel(
    tmp_path, rush, fake_probe, fake_ffmpeg
):
    """AC 11 (F9): « meme rapport » porte aussi sur le manifest.

    Le temoin de ce test est sa propre exclusion : `created` DOIT differer d'une
    passe a l'autre (c'est un horodatage a la seconde), sans quoi l'exclusion
    nommee ne mesurerait rien et le test passerait meme si le manifest etait
    ignore.
    """
    # Meme nom de projet des deux cotes : `project_id` en derive.
    for parent, rappel in (("passe-sans", None), ("passe-avec", lambda faites, total: None)):
        extraction.run_extraction(
            project_dir=tmp_path / parent / "projet",
            video_path=rush,
            fps_target=4,
            consent_granted=True,
            logger=logging.getLogger("test-5-28"),
            rappel_progression=rappel,
        )

    manifests = [
        json.loads(
            (tmp_path / parent / "projet" / MANIFEST_FILENAME).read_text(
                encoding="utf-8"
            )
        )
        for parent in ("passe-sans", "passe-avec")
    ]
    assert _sans_champs_volatils(manifests[0]) == _sans_champs_volatils(manifests[1])
    # Les champs retires sont bien les deux que le coeur declare, et pas une
    # extension entiere.
    assert NON_IDEMPOTENT_FIELDS == ("created", "lots[].confirmation.confirmed_at")
    assert "created" in manifests[0] and "created" in manifests[1]


def _sans_champs_volatils(document):
    """Le manifest prive des champs que le coeur declare non idempotents.

    La liste n'est pas reecrite ici : elle est lue dans
    `NON_IDEMPOTENT_FIELDS`, la ou le coeur la declare, pour qu'un champ
    volatil ajoute plus tard sans mise a jour du banc se voie.
    """
    copie = json.loads(json.dumps(document))
    for pointeur in NON_IDEMPOTENT_FIELDS:
        if pointeur == "created":
            copie.pop("created", None)
        elif pointeur == "lots[].confirmation.confirmed_at":
            for lot in copie.get("lots", []):
                lot.get("confirmation", {}).pop("confirmed_at", None)
        else:  # pragma: no cover -- garde-fou de vocabulaire
            raise AssertionError(
                f"champ non idempotent inconnu du banc: {pointeur}. La liste a "
                "bouge cote coeur et l'exclusion doit etre revue nommement."
            )
    return copie


def _empreinte_du_lot(project_dir: Path):
    """Chemins relatifs et contenu de tout ce que la passe a ecrit.

    Les `.json` sont **inclus** (F9), a ceci pres que le manifest est compare
    prive des champs que le coeur lui-meme declare non idempotents
    (`NON_IDEMPOTENT_FIELDS`) : un horodatage de creation differe legitimement
    d'une passe a l'autre. Exclure une extension entiere, en revanche, reduisait
    « meme rapport » a « memes noms de fichiers ».
    """
    if not project_dir.exists():
        return []
    empreinte = []
    for chemin in sorted(project_dir.rglob("*")):
        if not chemin.is_file():
            continue
        relatif = chemin.relative_to(project_dir).as_posix()
        if chemin.suffix == ".json":
            document = json.loads(chemin.read_text(encoding="utf-8"))
            contenu = json.dumps(
                _sans_champs_volatils(document), sort_keys=True
            ).encode("utf-8")
        else:
            contenu = chemin.read_bytes()
        empreinte.append((relatif, contenu))
    return sorted(empreinte)


# ---------------------------------------------------------------------------
# Story 5.29 (`EPIC11-ARB-89`) -- --nouvelle-version / --ecrasement-conscient
# exerces par argparse et cli.main(), pas par extraction.run_extraction()
# appele directement. Blind Hunter (revue) : un typo de dest= dans le
# cablage passait tous les tests qui n'appelaient que run_extraction().
# ---------------------------------------------------------------------------


def test_cli_nouvelle_version_de_bout_en_bout(tmp_path, rush, fake_probe, fake_ffmpeg):
    assert _run_cli(tmp_path, rush, 4, "--yes") == 0
    project = tmp_path / "proj"
    manifest_path = project / "project.json"

    # Fait passer le lot a un etat aval, a la main -- comme un `makepdf`
    # l'aurait fait.
    manifest = json.loads(manifest_path.read_text())
    manifest["lots"][0]["state"] = "pdf"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    code = _run_cli(tmp_path, rush, 4, "--yes", "--nouvelle-version")
    assert code == 0, "la nouvelle version doit reussir, le lot d'origine n'est pas touche"

    manifest_apres = json.loads(manifest_path.read_text())
    lot_ids = {l["lot_id"] for l in manifest_apres["lots"]}
    assert "rush-001_4" in lot_ids, "le lot d'origine est intact"
    assert "rush-001_4_v2" in lot_ids, "la nouvelle version a bien ete creee"
    version = next(l for l in manifest_apres["lots"] if l["lot_id"] == "rush-001_4_v2")
    assert version["version_rank"] == 2
    assert version["base_lot_id"] == "rush-001_4"
    assert project_layout.extract_frames_dir_from_slug(project, "rush-001_4_v2").is_dir()
    assert project_layout.extract_frames_dir_from_slug(project, "rush-001_4").is_dir(), "le dossier d'origine survit"


def test_cli_ecrasement_conscient_de_bout_en_bout(tmp_path, rush, fake_probe, fake_ffmpeg):
    assert _run_cli(tmp_path, rush, 4, "--yes") == 0
    project = tmp_path / "proj"
    manifest_path = project / "project.json"

    manifest = json.loads(manifest_path.read_text())
    manifest["lots"][0]["state"] = "scan"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    code = _run_cli(tmp_path, rush, 4, "--yes", "--ecrasement-conscient")
    assert code == 0, "l'ecrasement conscient doit reussir en place"

    manifest_apres = json.loads(manifest_path.read_text())
    assert len(manifest_apres["lots"]) == 1
    assert manifest_apres["lots"][0]["lot_id"] == "rush-001_4"
    assert manifest_apres["lots"][0]["state"] == "extraction", (
        "l'extraction reussie repasse le lot a extraction, comme un lot neuf"
    )


def test_cli_aucune_impasse_sur_un_dossier_de_version_orphelin(tmp_path, rush, fake_probe, fake_ffmpeg):
    """Blocage sec mesure par la CLI (revue Opus du 2026-08-30) : un dossier
    `_v2` residuel sans entree manifeste rendait `--nouvelle-version`
    definitivement inutilisable -- le refus prescrivait `--overwrite`, et
    `--overwrite` etait refuse."""
    assert _run_cli(tmp_path, rush, 4, "--yes") == 0
    project = tmp_path / "proj"
    orphelin = project_layout.extract_frames_dir_from_slug(project, "rush-001_4_v2")
    orphelin.mkdir(parents=True)
    (orphelin / "residu.tiff").write_bytes(b"residu")

    manifest_path = project / "project.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["lots"][0]["state"] = "pdf"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert _run_cli(tmp_path, rush, 4, "--yes", "--nouvelle-version") == 1, (
        "le dossier orphelin doit bien etre refuse par la garde AC 9"
    )
    assert _run_cli(tmp_path, rush, 4, "--yes", "--nouvelle-version", "--overwrite") == 0, (
        "BLOCAGE SEC : l'issue prescrite par le refus precedent est refusee a son tour"
    )
    assert not (orphelin / "residu.tiff").exists(), "le residu n'a pas ete remplace"
