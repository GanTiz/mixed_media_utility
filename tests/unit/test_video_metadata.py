from __future__ import annotations

import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import codec_profiles, video_metadata
from mixed_media_utility.io import metadata_matrix

requires_ffmpeg_tools = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe binaries not available on PATH",
)


@pytest.fixture(scope="module")
def frames(tmp_path_factory) -> list[Path]:
    """Rend la sequence d'entree comme une **liste ordonnee de chemins**.

    Story 6.0, AC 3: la fabrique ne prend plus un motif ``frame_%04d.png``,
    qui n'atteint aucun fichier produit par la chaine v2. ``testsrc`` anime sa
    mire, donc les frames rendues sont deux a deux distinguables -- une
    permutation d'ordre ne passerait pas inapercue (regle des fabriques du
    CLAUDE.md).
    """
    directory = tmp_path_factory.mktemp("frames")
    result = subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i",
         "testsrc=size=320x180:rate=24:duration=0.5", str(directory / "frame_%04d.png")],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    paths = sorted(directory.glob("frame_*.png"))
    assert len(paths) > 1, paths
    return paths


def encode(frames: list[Path], tmp_path: Path, profile_id: str, **kwargs) -> Path:
    profile = codec_profiles.get_profile(profile_id)
    output = tmp_path / f"{profile_id}.{profile.container}"
    codec_profiles.run_encode(
        profile_id, frames, kwargs.pop("fps", 24.0), output, **kwargs
    )
    return output


# --- matrice: coherence avec le catalogue de profils -----------------------


def test_matrix_is_derived_from_the_profile_catalog() -> None:
    # The tuple of profile ids used to be retyped eight times: renaming a
    # profile in story 6.2 silently marked every field unsupported here, with
    # no red test.
    for field, entry in video_metadata.TECHNICAL_METADATA_MATRIX.items():
        assert set(entry["supported_profiles"]) <= set(codec_profiles.PROFILES), field
        # reliability used to exist on the `timecode` row only, so any generic
        # consumer raised KeyError on seven rows out of eight.
        assert set(entry["reliability"]) == set(codec_profiles.PROFILES), field


@requires_ffmpeg_tools
@pytest.mark.parametrize("profile_id", sorted(codec_profiles.PROFILES))
def test_probe_codec_name_is_what_ffprobe_actually_reports(profile_id, frames, tmp_path) -> None:
    # Without this field the `codec` check -- which verify_technical_metadata
    # makes mandatory -- is unanswerable outside the test suite.
    profile = codec_profiles.get_profile(profile_id)
    actual = video_metadata.read_technical_metadata(str(encode(frames, tmp_path, profile_id)))
    assert actual["codec"] == profile.probe_codec_name
    assert profile.manifest_fields()["probe_codec_name"] == profile.probe_codec_name


def test_matrix_covers_the_fields_the_epic_requires() -> None:
    assert {"codec", "resolution", "frame_rate", "pixel_format", "colorspace",
            "color_range", "timecode"} <= set(video_metadata.TECHNICAL_METADATA_MATRIX)
    # time_base is imposed by the muxer (1/12288 at 24 fps, 1/24 in MXF):
    # verifying it proves nothing about what we asked for.
    assert "time_base" not in video_metadata.TECHNICAL_METADATA_MATRIX
    assert "time_base" in video_metadata.MUXER_IMPOSED_FIELDS


def test_timecode_entry_has_no_internal_contradiction() -> None:
    # Excluding MP4 from `reinjectable_for` while giving it a `best_effort`
    # reliability made two opposite implementations both "conformant": one
    # would never write a timecode on delivery derivatives, the other always.
    entry = video_metadata.TECHNICAL_METADATA_MATRIX["timecode"]
    assert set(entry["supported_profiles"]) == set(codec_profiles.PROFILES)
    assert entry["reliability"]["prores_hq"] == "reliable"
    assert entry["reliability"]["h264_delivery"] == "best_effort"


def test_manifest_only_fields_agree_with_the_authoritative_matrix() -> None:
    # story 2.4 classifies project_id/rush_id/lot_id as OPTIONAL in the video
    # container; declaring them "never reliable" here contradicted it.
    assert {"project_id", "rush_id"} <= set(video_metadata.CONTAINER_OPTIONAL_BUSINESS_FIELDS)
    for field in video_metadata.CONTAINER_OPTIONAL_BUSINESS_FIELDS:
        assert metadata_matrix.is_allowed(field, metadata_matrix.Channel.VIDEO_CONTAINER)
    for field in video_metadata.MANIFEST_ONLY_FIELDS:
        assert field not in video_metadata.CONTAINER_OPTIONAL_BUSINESS_FIELDS


# --- cadence: la corruption NTSC ------------------------------------------


@pytest.mark.parametrize(
    "fps, expected",
    [
        (24.0, "24/1"), (25, "25/1"), (30.0, "30/1"),
        (23.976, "24000/1001"), (29.97, "30000/1001"), (59.94, "60000/1001"),
        ("24000/1001", "24000/1001"), (Fraction(24000, 1001), "24000/1001"),
    ],
)
def test_rounded_ntsc_rates_are_snapped_back_to_their_exact_ratio(fps, expected) -> None:
    # str(23.976) handed to ffmpeg yields 2997/125 instead of 24000/1001: a
    # master with a non-standard time base that drifts in edit.
    assert codec_profiles.exact_frame_rate(fps) == expected


@pytest.mark.parametrize("fps", [0, -24, 0.0, float("nan"), float("inf"), float("-inf")])
def test_unusable_frame_rates_are_rejected_as_valueerror(fps) -> None:
    # inf escaped as OverflowError, which is not a ValueError, so a caller
    # written against the documented contract crashed on a corrupt manifest fps.
    with pytest.raises(ValueError):
        codec_profiles.exact_frame_rate(fps)


def test_encode_command_carries_the_exact_rational_rate() -> None:
    command = codec_profiles.build_encode_command("prores_hq", "liste.txt", 23.976, "o.mov")
    assert "23.976" not in command
    assert command.count("24000/1001") == 2


# --- timecode: les cas que ffmpeg accepte en silence ----------------------


@pytest.mark.parametrize(
    "timecode",
    ["01:00:00:24", "24:00:00:00", "01:60:00:00", "01:00:60:00",
     "01:00:00;00", "abc", "", "1:00:00:00"],
)
def test_invalid_timecodes_are_rejected_before_encoding(timecode: str) -> None:
    # Measured at 24 fps, rc=0 in every case: `01:00:00:24` is rewritten to
    # `01:00:01:00` (one second off the manifest mapping) and the others
    # produce a master with no tmcd track at all.
    with pytest.raises(ValueError):
        codec_profiles.validate_timecode(timecode, 24.0)


def test_drop_frame_is_accepted_on_ntsc_rates_only() -> None:
    assert codec_profiles.validate_timecode("01:00:00;00", 29.97) == "01:00:00;00"
    with pytest.raises(ValueError):
        codec_profiles.validate_timecode("01:00:00;00", 25.0)


def test_empty_container_tag_is_rejected_rather_than_silently_dropped() -> None:
    with pytest.raises(ValueError):
        codec_profiles.build_encode_command(
            "prores_hq", "liste.txt", 24.0, "o.mov", container_tags={"comment": ""}
        )


def test_custom_tags_request_the_movflag_that_keeps_them() -> None:
    # mov/mp4 muxers silently delete non-standard keys without it.
    command = codec_profiles.build_encode_command(
        "prores_hq", "liste.txt", 24.0, "o.mov", container_tags={"rush_id": "R42"}
    )
    assert "-metadata" in command and "rush_id=R42" in command
    assert "use_metadata_tags" in command


# --- verification: les faux positifs et faux negatifs ---------------------


def test_verification_request_must_not_be_vacuous() -> None:
    # verify(..., {}) returned {} and all({}) is True: a full pass without a
    # single field read.
    with pytest.raises(video_metadata.MetadataVerificationError):
        video_metadata.verify_technical_metadata("whatever.mov", {})
    with pytest.raises(video_metadata.MetadataVerificationError):
        video_metadata.verify_technical_metadata("whatever.mov", {"codec": "prores"})


def test_unknown_field_is_rejected_instead_of_passing_on_none() -> None:
    # {"totally_made_up": None} used to report ok: True.
    with pytest.raises(video_metadata.MetadataVerificationError):
        video_metadata.verify_technical_metadata(
            "whatever.mov", {"totally_made_up": None}, require_mandatory=False
        )
    with pytest.raises(video_metadata.MetadataVerificationError):
        video_metadata.supported_profiles("totally_made_up")


def test_ffprobe_absence_is_explicit() -> None:
    with pytest.raises(video_metadata.FfprobeNotFoundError):
        video_metadata.probe_media("whatever.mov", ffprobe_bin="not-a-real-ffprobe-binary")


@requires_ffmpeg_tools
def test_ffprobe_failure_keeps_the_reason(tmp_path: Path) -> None:
    # check=True raised CalledProcessError, whose message drops the captured
    # stderr — the only thing that says why.
    empty = tmp_path / "empty.mov"
    empty.write_bytes(b"")
    with pytest.raises(video_metadata.FfprobeError):
        video_metadata.probe_media(str(empty))
    with pytest.raises(video_metadata.FfprobeError):
        video_metadata.probe_media(str(tmp_path / "absent.mov"))


# --- verification sur encodages reels -------------------------------------


@requires_ffmpeg_tools
@pytest.mark.parametrize("profile_id", sorted(codec_profiles.PROFILES))
def test_every_profile_verifies_against_its_own_declaration(profile_id, frames, tmp_path) -> None:
    # The old suite covered 1 profile out of 7 and 2 fields out of 8, and its
    # four other tests re-read the constants declared just above them.
    profile = codec_profiles.get_profile(profile_id)
    output = encode(frames, tmp_path, profile_id)

    report = video_metadata.verify_technical_metadata(
        str(output),
        {
            # `codec` is mandatory to verify, and ffprobe reports the *codec*
            # (prores, h264) while the profile carries the *encoder*
            # (prores_ks, libx264). The mapping used to live only in this
            # test, so a production caller passing profile.vcodec got
            # ok=False on a conformant master.
            "codec": profile.probe_codec_name,
            "resolution": "320x180",
            "frame_rate": 24.0,
            "pixel_format": profile.pix_fmt,
            "colorspace": profile.colorspace,
            # **Les deux champs qui cassent, et ils manquaient ici** (ajoutes le
            # 2026-09-06). Ce banc encodait bien les 7 profils, mais il ne
            # demandait que `colorspace` -- or c'est le seul des trois que
            # FFmpeg 8 pose encore depuis les options CLI. Il serait donc reste
            # **vert** sur les masters mal tagues remontes du terrain, pendant
            # que la demande de production, elle, les refusait.
            "color_primaries": profile.colorspace,
            "color_transfer": profile.colorspace,
        },
    )
    for field, entry in report.items():
        assert entry["ok"], f"{profile_id}/{field}: {entry}"
    # Frontiere de non-vacuite: les deux champs ajoutes doivent avoir ete
    # **lus**, pas seulement declares conformes par absence des deux cotes.
    assert report["color_primaries"]["actual"] == profile.colorspace
    assert report["color_transfer"]["actual"] == profile.colorspace


@requires_ffmpeg_tools
def test_frame_rate_accepts_the_forms_a_manifest_actually_stores(frames, tmp_path) -> None:
    # Measured on a real 24 fps file: expected=24, 24.0 and "24" all reported
    # ok=False; only "24/1" passed.
    output = encode(frames, tmp_path, "prores_hq")
    for expected in (24, 24.0, "24", "24/1", Fraction(24, 1)):
        report = video_metadata.verify_technical_metadata(
            str(output), {"frame_rate": expected}, require_mandatory=False
        )
        assert report["frame_rate"]["ok"], expected


@requires_ffmpeg_tools
def test_ntsc_encode_lands_on_the_standard_time_base(frames, tmp_path) -> None:
    output = encode(frames, tmp_path, "prores_hq", fps=23.976)
    actual = video_metadata.read_technical_metadata(str(output))["frame_rate"]
    assert Fraction(actual) == Fraction(24000, 1001)


@requires_ffmpeg_tools
def test_timecode_is_actually_reinjected_and_read_back(frames, tmp_path) -> None:
    # The story is named "reinjection" but shipped read-only helpers: no code
    # path wrote a timecode, so every master left without one.
    output = encode(frames, tmp_path, "prores_hq", timecode="01:00:00:00")
    report = video_metadata.verify_technical_metadata(
        str(output), {"timecode": "01:00:00:00"}, require_mandatory=False
    )
    assert report["timecode"]["ok"], report


@requires_ffmpeg_tools
def test_timecode_is_read_back_from_mp4_derivatives_too(frames, tmp_path) -> None:
    output = encode(frames, tmp_path, "h264_delivery", timecode="01:00:00:00")
    assert video_metadata.read_technical_metadata(str(output))["timecode"] == "01:00:00:00"


@requires_ffmpeg_tools
def test_missing_timecode_is_reported_absent_not_merely_unequal(frames, tmp_path) -> None:
    # tags.timecode was read with a flat .get() on a nested dict, on a v:0
    # selection that cannot see a tmcd data stream: 100% false negative.
    output = encode(frames, tmp_path, "prores_hq")
    report = video_metadata.verify_technical_metadata(
        str(output), {"timecode": None}, require_mandatory=False
    )
    assert report["timecode"]["ok"] and report["timecode"]["actual"] is None


@requires_ffmpeg_tools
def test_presence_mismatch_is_refused_in_both_directions(frames, tmp_path) -> None:
    """La garde de presence refuse les deux desaccords asymetriques.

    Mutant `I04` de la campagne 6.1, seul survivant de la passe de 61: remplacer
    le `return expected is None and actual is None` par `return True` laissait la
    suite entiere verte. Motif: le seul test de presence confrontait `None` a
    `None`, c'est-a-dire le cas ou la garde rend **vrai**. Les deux cas ou elle
    doit rendre **faux** -- un seul des deux cotes absent -- n'etaient exerces
    nulle part, si bien qu'une garde toujours vraie passait inapercue.

    Meme famille que `H02`: une assertion qui ne visite que la branche positive
    d'une condition ne pinne pas la condition, elle pinne une constante.
    """
    # Deux masters DISTINCTS, l'un tague et l'autre non: une garde qui rendrait
    # le meme verdict sur les deux ne se demasque pas autrement (regle des
    # fabriques du CLAUDE.md).
    avec_timecode = encode(frames, tmp_path / "avec", "prores_hq", timecode="01:00:00:00")
    sans_timecode = encode(frames, tmp_path / "sans", "prores_hq")

    # Sens 1 -- attendu absent, reellement present. `codec` est place AVANT le
    # champ vise pour qu'un appariement positionnel fautif se voie.
    rapport = video_metadata.verify_technical_metadata(
        str(avec_timecode),
        {"codec": "prores", "timecode": None},
        require_mandatory=False,
    )
    assert rapport["codec"]["ok"], "le champ temoin doit rester tenu"
    assert not rapport["timecode"]["ok"]
    assert rapport["timecode"]["actual"] == "01:00:00:00"

    # Sens 2 -- attendu present, reellement absent.
    rapport = video_metadata.verify_technical_metadata(
        str(sans_timecode),
        {"codec": "prores", "timecode": "01:00:00:00"},
        require_mandatory=False,
    )
    assert rapport["codec"]["ok"], "le champ temoin doit rester tenu"
    assert not rapport["timecode"]["ok"]
    assert rapport["timecode"]["actual"] is None


@requires_ffmpeg_tools
def test_prores_needs_all_three_color_flags(frames, tmp_path) -> None:
    # The central empirical discovery of the story, never covered by a test.
    output = tmp_path / "one_flag.mov"
    # Story 6.0, AC 3: la sequence passe par une liste `concat`, et la cadence
    # d'entree par `-r` -- l'option de cadence d'image n'existe pas sur ce
    # demuxeur.
    list_path = tmp_path / "one_flag.concat"
    list_path.write_text(
        "".join(codec_profiles.format_concat_entry(frame.resolve()) for frame in frames),
        encoding="utf-8",
    )
    result = subprocess.run(
        ["ffmpeg", "-y", "-r", "24", "-f", "concat", "-safe", "0", "-i", str(list_path),
         "-c:v", "prores_ks", "-pix_fmt", "yuv422p10le", "-profile:v", "3",
         "-colorspace", "bt709", str(output)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    partial = video_metadata.read_technical_metadata(str(output))
    assert partial["color_primaries"] is None and partial["color_transfer"] is None

    full = video_metadata.read_technical_metadata(str(encode(frames, tmp_path, "prores_hq")))
    assert full["color_primaries"] == "bt709" and full["color_transfer"] == "bt709"


@requires_ffmpeg_tools
@pytest.mark.parametrize("profile_id", sorted(codec_profiles.PROFILES))
def test_les_trois_champs_couleur_sont_poses_sur_les_sept_profils(
    profile_id, frames, tmp_path
) -> None:
    """Generalisation du banc ci-dessus, qui ne portait que sur `prores_hq`.

    C'etait le **seul** banc du depot a confronter les trois champs couleur a un
    fichier reellement encode, et le seul qui aurait rougi sous FFmpeg 8 -- sur
    un profil sur sept. Or la regression du 2026-09-06 atteint les **sept**:
    `h264_delivery` compris, ce que le verbatim d'Egan (« un prores ou un
    DNxHD ») masquait, et qui excluait a tort la piste « profils
    intermediaires ».

    Ce banc ne peut pas faire varier la version de ffmpeg -- c'est le drapeau
    non varie de ce lot, et aucun banc ordinaire ne le peut. Ce qu'il tient, en
    revanche, c'est que la demande porte sur les trois champs et sur tous les
    profils: le jour ou une version renverse encore l'arbitrage, elle rougit
    ici plutot que chez Egan.
    """
    profile = codec_profiles.get_profile(profile_id)
    actual = video_metadata.read_technical_metadata(
        str(encode(frames, tmp_path, profile_id))
    )
    assert actual["colorspace"] == profile.colorspace, actual
    assert actual["color_primaries"] == profile.colorspace, actual
    assert actual["color_transfer"] == profile.colorspace, actual


@requires_ffmpeg_tools
def test_container_tags_survive_the_mov_muxer(frames, tmp_path) -> None:
    output = encode(frames, tmp_path, "prores_hq", container_tags={"rush_id": "R42"})
    probe = video_metadata.probe_media(str(output))
    assert probe["format"]["tags"].get("rush_id") == "R42"


@requires_ffmpeg_tools
def test_color_range_gap_on_prores_is_the_documented_one(frames, tmp_path) -> None:
    # Guards the known full/legal signalling gap: if ffmpeg starts tagging
    # ProRes, this test turns red and the matrix note must be revisited.
    prores = video_metadata.read_technical_metadata(str(encode(frames, tmp_path, "prores_hq")))
    delivery = video_metadata.read_technical_metadata(
        str(encode(frames, tmp_path, "h264_delivery"))
    )
    assert prores["color_range"] is None
    assert delivery["color_range"] == "tv"
    assert "prores_hq" not in video_metadata.supported_profiles("color_range")
