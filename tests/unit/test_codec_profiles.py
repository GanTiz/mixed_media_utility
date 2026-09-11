from __future__ import annotations

import dataclasses
import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import codec_profiles

requires_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None,
    reason="ffmpeg binary not available on PATH",
)
requires_ffmpeg_tools = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe binaries not available on PATH",
)

# ---------------------------------------------------------------------------
# Fabriques de sequences.
#
# Regle des fabriques du CLAUDE.md, appliquee sans exception ici: **toute
# fabrique de sequence produit au moins deux frames distinguables**. Une mire
# uniforme rendrait invisible une inversion d'ordre ou un appariement
# positionnel faux, et c'est precisement le defaut que trois campagnes de
# mutation ont trouve dans l'Epic 5. Les valeurs d'aplat sont donc toutes
# differentes, et un test au moins place la frame visee ailleurs qu'en
# premiere position.
# ---------------------------------------------------------------------------

#: Mire de mesure colorimetrique. Les couleurs **saturees** sont
#: indispensables: la derive BT.601/BT.709 est purement chromatique, donc
#: strictement invisible sur l'axe neutre. Blanc et gris sont conserves pour
#: verifier qu'ils sont **inchanges** par le correctif, pas qu'ils sont nuls.
PATCHES: tuple[tuple[str, tuple[int, int, int]], ...] = (
    ("rouge", (255, 0, 0)),
    ("vert", (0, 255, 0)),
    ("bleu", (0, 0, 255)),
    ("jaune", (255, 255, 0)),
    ("cyan", (0, 255, 255)),
    ("magenta", (255, 0, 255)),
    ("blanc", (255, 255, 255)),
    ("gris50", (128, 128, 128)),
)
MIRE_WIDTH, MIRE_HEIGHT = 320, 180
TAGS = ("-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709")


def write_tiff16(path: Path, array: np.ndarray, pix_fmt: str = "rgb48le") -> Path:
    """Ecrit un TIFF 16 bits par canal, le format que produit `extract`.

    Passe par ffmpeg parce que Pillow n'ecrit pas de RGB 48 bits: mesurer sur
    du 8 bits ne dirait rien de l'entree reelle de l'encodage.
    """
    png = path.with_suffix(".png")
    Image.fromarray(array).save(png)
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", str(png), "-pix_fmt", pix_fmt, "-c:v", "tiff", str(path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    png.unlink()
    return path


def make_sequence(directory: Path, values: tuple[int, ...] = (40, 120, 200),
                  size: tuple[int, int] = (320, 180)) -> list[Path]:
    """Rend une sequence d'aplats **tous differents**, jamais un remplissage uniforme."""
    assert len(set(values)) == len(values) >= 2, values
    width, height = size
    return [
        write_tiff16(directory / f"frame_{index}_{value}.tiff",
                     np.full((height, width, 3), value, dtype=np.uint8))
        for index, value in enumerate(values)
    ]


def make_timecoded_sequence(
    directory: Path, values: tuple[int, ...] = (40, 120, 200), lot: str = "LOT",
    size: tuple[int, int] = (320, 180), step: int = 5,
) -> list[Path]:
    """Rend une sequence nommee **comme la chaine v2 la nomme**.

    `extract` ecrit `<lot_id>_<hh-mm-ss-ff>.tiff` (verifie sur
    `projects/projet_demo/frames/TEST_FILE_5/`). C'est ce nommage, et lui seul,
    qui rend la garde d'ordre calculable: les quatre champs sont zero-remplis,
    donc leur comparaison lexicographique coincide avec l'ordre chronologique.

    Les aplats sont **tous differents**, comme partout ici: une permutation ne
    se voit que si les elements different.
    """
    assert len(set(values)) == len(values) >= 2, values
    width, height = size
    paths = []
    for index, value in enumerate(values):
        frames_field = index * step
        name = f"{lot}_00-00-{frames_field // 25:02d}-{frames_field % 25:02d}.tiff"
        paths.append(write_tiff16(directory / name,
                                  np.full((height, width, 3), value, dtype=np.uint8)))
    return paths


def decoded_frame_levels(video: Path, frame_count: int,
                         size: tuple[int, int] = (320, 180)) -> list[float]:
    """Decode **le master produit** et rend le niveau moyen de chaque frame.

    C'est le trou que la revue a nomme: aucun test ne decodait jamais un master
    sorti de `run_encode`, toutes les mesures de contenu passant par des
    commandes ffmpeg ecrites dans le test. Un `EncodeOutcome` de succes, un
    cardinal juste et une geometrie juste ne disent **rien** de l'ordre.
    """
    width, height = size
    decoded = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(video),
         "-f", "rawvideo", "-pix_fmt", "rgb48le", "-"],
        capture_output=True,
    )
    stride = width * height * 3 * 2
    assert len(decoded.stdout) == stride * frame_count, (
        len(decoded.stdout), stride, frame_count, decoded.stderr[-300:]
    )
    return [
        float(np.frombuffer(decoded.stdout[index * stride:(index + 1) * stride],
                            dtype="<u2").mean()) / 257.0
        for index in range(frame_count)
    ]


def make_mire(path: Path) -> Path:
    image = np.zeros((MIRE_HEIGHT, MIRE_WIDTH, 3), dtype=np.uint8)
    cell_w, cell_h = MIRE_WIDTH // 4, MIRE_HEIGHT // 2
    for index, (_name, rgb) in enumerate(PATCHES):
        row, column = divmod(index, 4)
        image[row * cell_h:(row + 1) * cell_h, column * cell_w:(column + 1) * cell_w] = rgb
    return write_tiff16(path, image)


def write_list(path: Path, frames: list[Path]) -> Path:
    path.write_text(
        "".join(codec_profiles.format_concat_entry(frame.resolve()) for frame in frames),
        encoding="utf-8",
    )
    return path


def ffprobe_field(path: Path, entries: str) -> list[str]:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", f"stream={entries}", "-of", "csv=p=0", "--", str(path)],
        capture_output=True, text=True,
    )
    return result.stdout.strip().split(",")


def patch_deltas(video: Path, frame_index: int = 1) -> dict[str, float]:
    """Decode le master en RGB 16 bits et rend l'ecart par patch, sur 255.

    ``frame_index`` vaut 1 par defaut: la mire est en **deuxieme** position
    dans la sequence, de sorte qu'un decodage qui lirait toujours la premiere
    frame mesurerait un aplat uni et ne verrait aucune derive.

    Le decodage est en 16 bits (`rgb48le`) et non en `rgb24`: la mesure de
    reference se joue au dixieme, un arrondi 8 bits l'ecraserait.
    """
    decoded = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(video),
         "-f", "rawvideo", "-pix_fmt", "rgb48le", "-"],
        capture_output=True,
    )
    assert decoded.stdout, decoded.stderr[-400:]
    stride = MIRE_WIDTH * MIRE_HEIGHT * 3 * 2
    start = frame_index * stride
    assert len(decoded.stdout) >= start + stride, (len(decoded.stdout), start)
    frame = np.frombuffer(
        decoded.stdout[start:start + stride], dtype="<u2"
    ).reshape(MIRE_HEIGHT, MIRE_WIDTH, 3).astype(float) / 257.0
    cell_w, cell_h = MIRE_WIDTH // 4, MIRE_HEIGHT // 2
    deltas: dict[str, float] = {}
    for index, (name, rgb) in enumerate(PATCHES):
        row, column = divmod(index, 4)
        y0, x0 = row * cell_h + cell_h // 4, column * cell_w + cell_w // 4
        block = frame[y0:y0 + cell_h // 2, x0:x0 + cell_w // 2].reshape(-1, 3).mean(axis=0)
        deltas[name] = max(abs(block[channel] - rgb[channel]) for channel in range(3))
    return deltas


@pytest.fixture(scope="module")
def mire_pair(tmp_path_factory) -> tuple[list[Path], Path]:
    """Deux frames dont **la seconde** porte la mire de mesure.

    La mire est deliberement en **deuxieme** position: un decodage qui lirait
    toujours la premiere frame passerait sinon inapercu.
    """
    directory = tmp_path_factory.mktemp("mire")
    plain = write_tiff16(directory / "plain.tiff",
                         np.full((MIRE_HEIGHT, MIRE_WIDTH, 3), 17, dtype=np.uint8))
    mire = make_mire(directory / "mire.tiff")
    return [plain, mire], write_list(directory / "mire.concat", [plain, mire])


# --- catalogue: tests d'origine de la story 6.2, inchanges -----------------


def test_default_profile_is_prores_hq() -> None:
    assert codec_profiles.DEFAULT_PROFILE_ID == "prores_hq"
    profile = codec_profiles.get_profile(codec_profiles.DEFAULT_PROFILE_ID)
    assert profile.category == "primary"
    assert profile.container == "mov"


def test_get_profile_raises_for_unknown_id() -> None:
    with pytest.raises(KeyError):
        codec_profiles.get_profile("not-a-real-profile")


def test_only_prores_hq_is_primary() -> None:
    primary_ids = [pid for pid, profile in codec_profiles.PROFILES.items() if profile.category == "primary"]
    assert primary_ids == ["prores_hq"]


def test_dnxhr_hq_uses_8bit_pix_fmt_not_10bit() -> None:
    # Regression guard (story 6.2): the dnxhd encoder's HQ profile only
    # supports 8-bit 4:2:2 (yuv422p). Requesting yuv422p10le on HQ fails at
    # encode time with "pixel format is incompatible with DNxHR LB/SQ/HQ
    # profile" (confirmed with a real ffmpeg 6.1.1 run). 10-bit is only valid
    # for the dnxhr_hqx/444 tiers.
    assert codec_profiles.get_profile("dnxhr_hq").pix_fmt == "yuv422p"
    assert codec_profiles.get_profile("dnxhr_hqx").pix_fmt == "yuv422p10le"


def test_ffmpeg_video_args_always_set_all_three_color_tags() -> None:
    for profile in codec_profiles.PROFILES.values():
        args = profile.ffmpeg_video_args()
        assert "-colorspace" in args
        assert "-color_primaries" in args
        assert "-color_trc" in args


def test_manifest_fields_shape() -> None:
    profile = codec_profiles.get_profile("prores_hq")
    fields = profile.manifest_fields()
    assert fields == {
        "codec": "prores_ks",
        # The encoder and the codec ffprobe reports back are different names;
        # the manifest carries both so a later verification can be answered.
        "probe_codec_name": "prores",
        "profile": "prores_hq",
        "container": "mov",
        "target_colorspace": "bt709",
        "category": "primary",
    }


# --- AC 1 / AC 2: taguer n'est pas convertir ------------------------------


def test_profile_video_args_carry_no_filter_chain() -> None:
    """AC 2: `ffmpeg_video_args` decrit un profil, pas un encodage.

    Elle ne connait ni la geometrie ni la chaine de filtres; celle-ci est
    construite par la fabrique, seul point du depot ou geometrie et profil se
    rencontrent.
    """
    for profile in codec_profiles.PROFILES.values():
        args = profile.ffmpeg_video_args()
        assert "-vf" not in args
        assert not any("scale=" in arg for arg in args), profile.profile_id


def test_filter_chain_carries_the_matrix_of_the_profile() -> None:
    for profile in codec_profiles.PROFILES.values():
        chain = codec_profiles.build_filter_chain(profile)
        # Depuis le 2026-09-06 la chaine porte aussi un maillon `setparams`, qui
        # marque les frames elles-memes: sous FFmpeg 8, `-color_primaries` et
        # `-color_trc` n'atteignent plus l'encodeur et c'est le seul geste qui
        # les pose encore (`FFMPEG_COLOR_TAGGING_MEASUREMENT`).
        assert chain == (
            f"scale=out_color_matrix={profile.colorspace}:out_range=tv,"
            + codec_profiles.build_setparams_link(profile.colorspace)
        )


def test_filter_chain_takes_the_geometry_only_from_its_parameter() -> None:
    """AC 2: le parametre de geometrie est le **seul** point qui autorise un
    redimensionnement, et son absence signifie "pas de redimensionnement"."""
    profile = codec_profiles.get_profile("prores_hq")
    assert "1920:1080" not in codec_profiles.build_filter_chain(profile)
    assert codec_profiles.build_filter_chain(profile, (1920, 1080)).startswith(
        "scale=1920:1080:"
    )


def test_unknown_colorspace_is_refused_before_swscale_says_conversion_failed() -> None:
    profile = dataclasses.replace(
        codec_profiles.get_profile("prores_hq"), profile_id="t_cs", colorspace="pas_une_matrice"
    )
    with pytest.raises(codec_profiles.EncodeConfigurationError, match="scale"):
        codec_profiles.build_filter_chain(profile)


@requires_ffmpeg_tools
def test_the_filter_chain_is_what_actually_moves_the_color(tmp_path, mire_pair) -> None:
    """AC 1 et AC 15: mesure colorimetrique, avec son cas negatif.

    Cas nominal, cas negatif "pas de filtre" (l'etat d'avant la story 6.0), et
    un troisieme cas dont **le sens a change le 2026-09-06** -- voir plus bas.

    Ce que ce banc mesure reste ce qu'il a toujours mesure: **taguer n'est pas
    convertir**. Seul le maillon `scale` deplace la couleur; aucun tag, ou qu'il
    soit pose, ne la deplace.
    """
    _frames, list_path = mire_pair
    profile = codec_profiles.get_profile("prores_hq")
    base = ["ffmpeg", "-y", "-r", "25", "-f", "concat", "-safe", "0", "-i", str(list_path)]
    chain = codec_profiles.build_filter_chain(profile)
    video_args = ["-c:v", profile.vcodec, "-pix_fmt", profile.pix_fmt, "-profile:v", "3"]

    outputs = {}
    for label, args in (
        ("sans_filtre", [*video_args, *TAGS]),
        ("filtre_et_tags", ["-vf", chain, *video_args, *TAGS]),
        ("filtre_sans_tags", ["-vf", chain, *video_args]),
    ):
        output = tmp_path / f"{label}.mov"
        result = subprocess.run([*base, *args, "-r", "25", str(output)],
                                capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        outputs[label] = output

    without = patch_deltas(outputs["sans_filtre"])
    with_chain = patch_deltas(outputs["filtre_et_tags"])
    untagged = patch_deltas(outputs["filtre_sans_tags"])

    saturated = [name for name, _rgb in PATCHES if name not in ("blanc", "gris50")]
    # Cas negatif 1: taguer sans convertir. Mesure du 2026-08-10, vert 40,33.
    assert max(without[name] for name in saturated) > 20.0, without
    # Cas nominal: la chaine ramene l'ecart sous 2/255 (mesure: 1,06 max).
    assert max(with_chain[name] for name in saturated) < 2.0, with_chain
    assert ffprobe_field(outputs["filtre_et_tags"], "color_space")[0] == "bt709"

    # **CE CAS A CHANGE DE SENS LE 2026-09-06, et le dire vaut mieux que de le
    # retirer.** Il portait: "le filtre seul ne suffit pas -- le fichier ne
    # declare plus rien (`color_space=unknown`) et l'ecart repart a 23/255".
    # La premiere moitie est devenue fausse: depuis que la chaine porte un
    # maillon `setparams`, elle tague **par elle-meme**, et c'est precisement
    # ce qui repare l'export sous FFmpeg 8 -- ou les options CLI de primaires
    # et de transfert n'atteignent plus l'encodeur. Mesure sous 6.1.1: les
    # trois champs sortent a `bt709` sans une seule option CLI.
    #
    # La seconde moitie, elle, tient toujours et c'est celle qui portait le
    # sens du cas: la chaine **convertit** aussi, donc l'ecart reste bas. Les
    # deux gestes ne sont donc plus "necessaires et independants" -- le filtre
    # suffit desormais aux deux roles --, mais les options CLI sont conservees
    # (elles ne coutent rien et ne contredisent jamais le maillon, les deux
    # derivant du meme champ de profil).
    assert ffprobe_field(outputs["filtre_sans_tags"], "color_space")[0] == "bt709"
    assert max(untagged[name] for name in saturated) < 2.0, untagged


@requires_ffmpeg_tools
def test_the_neutral_axis_is_unchanged_by_the_fix_and_is_not_zero(tmp_path, mire_pair) -> None:
    """AC 1: les neutres sont **inchanges**, pas nuls.

    Une AC ecrite sur "0 sur le blanc et le gris" produirait un test rouge
    avant comme apres: l'ecart residuel est un arrondi de plage legale
    8 -> 10 bits, independant du correctif. Le fait utile est l'invariance.
    """
    _frames, list_path = mire_pair
    profile = codec_profiles.get_profile("prores_hq")
    base = ["ffmpeg", "-y", "-r", "25", "-f", "concat", "-safe", "0", "-i", str(list_path)]
    video_args = ["-c:v", profile.vcodec, "-pix_fmt", profile.pix_fmt, "-profile:v", "3"]
    deltas = {}
    for label, args in (
        ("sans", [*video_args, *TAGS]),
        ("avec", ["-vf", codec_profiles.build_filter_chain(profile), *video_args, *TAGS]),
    ):
        output = tmp_path / f"neutre_{label}.mov"
        assert subprocess.run([*base, *args, "-r", "25", str(output)],
                              capture_output=True).returncode == 0
        deltas[label] = patch_deltas(output)
    for name in ("blanc", "gris50"):
        assert abs(deltas["sans"][name] - deltas["avec"][name]) < 0.05, (name, deltas)
        assert deltas["avec"][name] > 0.0, (name, deltas)
        assert deltas["avec"][name] < 2.0, (name, deltas)


# --- AC 3: la sequence d'entree ------------------------------------------


def test_the_input_rate_is_not_the_option_concat_refuses() -> None:
    """AC 3a: `-framerate` n'existe pas sur `concat`, la cadence passe en `-r`."""
    command = codec_profiles.build_encode_command("prores_hq", "l.concat", 25, "o.mov")
    assert "-framerate" not in command
    assert command[:2] == ["ffmpeg", "-n"]
    assert command[command.index("-i") - 3:command.index("-i")] == ["concat", "-safe", "0"]


def test_the_same_rate_is_posed_on_both_sides() -> None:
    """AC 4: le controle de cardinal ne vaut que si les deux cadences sont egales.

    Mesure: `-r 25` en entree et `-r 50` en sortie donnent `nb_frames=8` pour
    une liste de 4 -- le cardinal ne dirait plus rien de la troncature.
    """
    command = codec_profiles.build_encode_command("prores_hq", "l.concat", 12.5, "o.mov")
    rates = [command[index + 1] for index, token in enumerate(command) if token == "-r"]
    assert len(rates) == 2 and len(set(rates)) == 1, command


def test_concat_entries_are_absolute_and_escaped(tmp_path) -> None:
    """AC 3b et 3c: chemins absolus (ils se resolvent par rapport au fichier de
    liste) et apostrophes echappees (sinon l'encodage porte sur autre chose)."""
    entry = codec_profiles.format_concat_entry("/a/b/rush d'ete/f.tiff")
    assert entry == "file '/a/b/rush d'\\''ete/f.tiff'\n"
    with pytest.raises(codec_profiles.EncodeConfigurationError, match="saut de ligne"):
        codec_profiles.format_concat_entry("/a/b\nc.tiff")


@requires_ffmpeg_tools
def test_a_quoted_path_reaches_the_right_file(tmp_path) -> None:
    """Cas negatif de l'echappement: sans lui la liste designe un autre chemin."""
    directory = tmp_path / "rush d'ete"
    directory.mkdir()
    frames = make_sequence(directory, values=(30, 210))
    outcome = codec_profiles.run_encode("prores_hq", frames, 25, tmp_path / "m.mov")
    assert outcome.frame_count == 2
    naive = tmp_path / "naive.concat"
    naive.write_text("".join(f"file '{frame}'\n" for frame in frames), encoding="utf-8")
    result = subprocess.run(
        ["ffmpeg", "-y", "-r", "25", "-f", "concat", "-safe", "0", "-i", str(naive),
         "-c:v", "prores_ks", "-pix_fmt", "yuv422p10le", "-r", "25", str(tmp_path / "naive.mov")],
        capture_output=True, text=True,
    )
    assert result.returncode != 0, "sans echappement, l'apostrophe doit casser la liste"


def test_the_concat_list_file_survives_no_exit_path(tmp_path) -> None:
    """AC 3d: apres un chemin reussi **et** apres un chemin en erreur, aucun
    fichier de liste ne subsiste."""
    with codec_profiles.concat_list_file([tmp_path / "a.tiff"], tmp_path) as list_path:
        assert list_path.is_file()
        survivor = list_path
    assert not survivor.exists()

    with pytest.raises(RuntimeError):
        with codec_profiles.concat_list_file([tmp_path / "a.tiff"], tmp_path) as list_path:
            survivor = list_path
            raise RuntimeError("interruption")
    assert not survivor.exists()
    assert list(tmp_path.iterdir()) == []


def test_an_empty_sequence_is_refused_rather_than_handed_to_concat(tmp_path) -> None:
    """AC 3: `concat` repond `No files to concat` (rc=183), message opaque."""
    with pytest.raises(codec_profiles.EncodeConfigurationError, match="vide"):
        codec_profiles.run_encode("prores_hq", [], 25, tmp_path / "m.mov")
    with pytest.raises(codec_profiles.EncodeConfigurationError, match="vide"):
        with codec_profiles.concat_list_file([], tmp_path):
            pass


@requires_ffmpeg_tools
def test_a_single_frame_sequence_is_accepted(tmp_path) -> None:
    frames = make_sequence(tmp_path, values=(60, 190))
    outcome = codec_profiles.run_encode("prores_hq", [frames[1]], 25, tmp_path / "une.mov")
    assert outcome.frame_count == 1
    assert ffprobe_field(tmp_path / "une.mov", "nb_frames")[0] == "1"


# --- AC 4: le controle de cardinal ---------------------------------------


@requires_ffmpeg_tools
def test_concat_truncates_silently_and_only_the_cardinal_check_sees_it(tmp_path) -> None:
    """AC 4 et AC 15: le cas negatif prouve que la garde sert.

    Changer de demuxeur regle l'adressage des noms, **pas** la troncature:
    `concat` a exactement le meme mode de panne silencieux qu'`image2`.
    """
    frames = make_sequence(tmp_path, values=(35, 205))
    doomed = tmp_path / "doomed.tiff"
    doomed.write_bytes(frames[1].read_bytes())
    list_path = write_list(tmp_path / "trunc.concat", [frames[0], doomed])
    doomed.unlink()

    output = tmp_path / "tronque.mov"
    result = subprocess.run(
        ["ffmpeg", "-y", "-r", "25", "-f", "concat", "-safe", "0", "-i", str(list_path),
         "-c:v", "prores_ks", "-pix_fmt", "yuv422p10le", "-r", "25", str(output)],
        capture_output=True, text=True,
    )
    # Sans cette assertion, la garde ci-dessous paraitrait superflue.
    assert result.returncode == 0, result.stderr
    assert ffprobe_field(output, "nb_frames")[0] == "1"

    profile = codec_profiles.get_profile("prores_hq")
    with pytest.raises(codec_profiles.EncodeVerificationError, match="Cardinal"):
        codec_profiles.verify_encoded_output(output, profile=profile, expected_frames=2)
    # Cas negatif: sur le cardinal reel, la meme garde ne dit rien.
    assert codec_profiles.verify_encoded_output(
        output, profile=profile, expected_frames=1
    )[:2] == (320, 180)


@requires_ffmpeg_tools
def test_the_auto_negotiated_pixel_format_is_detected(tmp_path, monkeypatch) -> None:
    """AC 11: un `pix_fmt` incompatible est absorbe en silence par ffmpeg.

    Mesure: `prores_ks` avec `-pix_fmt yuv420p` sort en rc=0 et `yuv422p10le`,
    avec un simple `Incompatible pixel format ... auto-selecting format` sur
    stderr. Ce n'est **pas** un doublon: il se produit sans aucune option
    dupliquee.
    """
    profile = dataclasses.replace(
        codec_profiles.get_profile("prores_hq"), profile_id="t_autoneg", pix_fmt="yuv420p"
    )
    monkeypatch.setitem(codec_profiles.PROFILES, "t_autoneg", profile)
    frames = make_sequence(tmp_path, values=(45, 195))
    with pytest.raises(codec_profiles.EncodeVerificationError, match="auto-negocie"):
        codec_profiles.run_encode("t_autoneg", frames, 25, tmp_path / "auto.mov")
    # Cas negatif: le profil livre, lui, obtient bien ce qu'il demande.
    outcome = codec_profiles.run_encode("prores_hq", frames, 25, tmp_path / "ok.mov")
    assert outcome.pix_fmt == "yuv422p10le"


# --- AC 5: ne jamais detruire un master deja en place ---------------------


@requires_ffmpeg_tools
def test_the_destination_never_appears_on_the_ffmpeg_command_line(tmp_path, monkeypatch) -> None:
    """AC 5: ffmpeg tronque sa sortie **avant** d'ouvrir l'encodeur.

    La seule protection sure est que le chemin final ne soit jamais nomme:
    l'encodage vise un temporaire, la bascule se fait par `os.replace`. Le test
    intercepte la commande **reellement executee** par `run_encode`, plutot que
    d'asserter l'absence d'une valeur qui n'a jamais ete passee a la fonction.
    """
    frames = make_sequence(tmp_path, values=(41, 171))
    master = tmp_path / "sortie" / "master.mov"
    seen: list[list[str]] = []
    real_run = subprocess.run

    def spy(command, *args, **kwargs):
        if command and str(command[0]).endswith("ffmpeg"):
            seen.append(list(command))
        return real_run(command, *args, **kwargs)

    monkeypatch.setattr(codec_profiles.subprocess, "run", spy)
    codec_profiles.run_encode("prores_hq", frames, 25, master)
    assert seen, "aucune commande ffmpeg interceptee"
    for command in seen:
        assert str(master) not in command, command
        assert command[1] == "-n"
    assert master.is_file()


def test_the_temporary_keeps_the_container_extension_and_discriminates(tmp_path) -> None:
    """AC 5a et 5c: sans extension, ffmpeg ne choisit aucun muxer (echec a 100 %),
    et un nom fonde sur le seul PID ne separe pas deux encodages du meme processus.

    **La quatrieme assertion a ete REECRITE le 2026-09-07, pas retiree**, et le
    motif compte. Elle valait ``first.name.startswith(".master.mov.")``,
    c'est-a-dire qu'elle exigeait la DOUBLE extension -- ``master.mov`` suivi
    plus loin de ``.mov``. Or aucune AC ne la demande : 5a demande que le
    temporaire **garde** l'extension du conteneur, 5c qu'il discrimine plus que
    le PID, 5b qu'il vive a cote de la cible. Les trois assertions precedentes
    les couvrent deja toutes les trois.

    Ce que l'ancienne ligne epinglait en plus, c'etait une **forme**, et cette
    forme est exactement celle qu'Egan a signalee du terrain le 2026-09-06 :
    ``.TEST_FILE_7p5_mmu_dnxhr_hqx.mov.2624-0d2c0cbf1e1c.mov``. Le banc
    verrouillait donc le defaut : la couche 1 de la revue a mesure que corriger
    le producteur faisait rougir ce test, ce qui aurait fait lire le doublon
    comme delibere.

    Les assertions neuves mesurent la PROPRIETE plutot que la forme : le
    conteneur apparait **une seule fois**, le tronc vient du nom de la cible,
    le fichier est cache, et le balayage le reconnait encore -- ce dernier
    point etant le prix cache d'un renommage, et celui qu'il ne faut pas payer
    sans le mesurer.
    """
    target = tmp_path / "master.mov"
    first = codec_profiles._unique_sibling(target, ".mov")
    second = codec_profiles._unique_sibling(target, ".mov")
    assert first.suffix == ".mov" and second.suffix == ".mov"
    assert first.parent == target.parent  # AC 5b: meme systeme de fichiers
    assert first != second
    assert first.name.count(".mov") == 1, (
        "le conteneur apparait deux fois : c'est la forme que le terrain a"
        f" signalee comme illisible -- {first.name}")
    assert first.name.startswith(".master."), first.name
    assert codec_profiles._TEMP_NAME_RE.search(first.name), (
        "le balayage ne reconnait plus ce nom : un temporaire tue par SIGKILL"
        f" resterait orphelin pour toujours -- {first.name}")


def test_the_muxer_is_posed_explicitly() -> None:
    """AC 5a et corollaire de l'AC 6: le muxer etant connu, il est impose."""
    command = codec_profiles.build_encode_command("prores_hq", "l.concat", 25, "o.mov")
    assert command[-3:-1] == ["-f", "mov"]
    command = codec_profiles.build_encode_command("h264_delivery", "l.concat", 25, "o.mp4")
    assert command[-3:-1] == ["-f", "mp4"]


@requires_ffmpeg
def test_a_temporary_without_extension_and_without_muxer_fails_outright(tmp_path) -> None:
    """Cas negatif de l'AC 5a: les deux motifs de temporaire du depot echouent."""
    frames = make_sequence(tmp_path, values=(55, 185))
    list_path = write_list(tmp_path / "t.concat", frames)
    for name in (".out.mov.tmp-1234", ".out.mov.abc123.tmp"):
        result = subprocess.run(
            ["ffmpeg", "-y", "-r", "25", "-f", "concat", "-safe", "0", "-i", str(list_path),
             "-c:v", "prores_ks", "-pix_fmt", "yuv422p10le", "-r", "25", str(tmp_path / name)],
            capture_output=True, text=True,
        )
        assert result.returncode != 0
        assert "Unable to choose an output format" in result.stderr


@requires_ffmpeg_tools
def test_an_existing_master_is_not_overwritten_without_being_asked(tmp_path) -> None:
    """AC 5: `-y` cesse d'etre inconditionnel, l'ecrasement devient un parametre.

    Les deux cardinaux sont **differents** (3 puis 2) et le master de depart en
    porte un troisieme: c'est la seule facon d'ecrire ce test de sorte qu'il
    puisse echouer. La version precedente relancait sur `frames[:2]` d'une liste
    de deux elements vers un master qui valait deja `nb_frames=2` -- son
    assertion finale etait vraie **avant** le second appel, et un `run_encode`
    qui ne remplacerait jamais un master existant tout en rendant un
    `EncodeOutcome` de succes passait la suite entiere.
    """
    frames = make_sequence(tmp_path, values=(65, 175, 205))
    master = tmp_path / "sortie" / "master.mov"

    first = codec_profiles.run_encode("prores_hq", frames, 25, master)
    assert first.frame_count == 3
    assert ffprobe_field(master, "nb_frames")[0] == "3"
    reference = master.read_bytes()

    with pytest.raises(codec_profiles.MasterAlreadyExistsError, match="overwrite"):
        codec_profiles.run_encode("prores_hq", frames[:2], 25, master)
    # Refus: l'ancien master est intact **au bit pres**, cardinal compris.
    assert master.read_bytes() == reference
    assert ffprobe_field(master, "nb_frames")[0] == "3"

    # Ecrasement demande: le master change reellement de contenu.
    second = codec_profiles.run_encode("prores_hq", frames[:2], 25, master, overwrite=True)
    assert second.frame_count == 2
    assert ffprobe_field(master, "nb_frames")[0] == "2"
    assert master.read_bytes() != reference


def test_build_encode_command_closes_the_overwrite_hole_by_a_mechanism(tmp_path) -> None:
    """AC 5, couche 3 B2: la fonction est **publique** et posait `-y` en dur.

    La protection reposait sur une hypothese ecrite en commentaire -- "l'appelant
    vient de forger ce chemin, ce n'est jamais le master" -- deja violee dans le
    depot par `scripts/archive/research/codec_metadata_experiment.py`, qui lui passe un
    vrai chemin de sortie. Une hypothese ne se verifie pas: elle se remplace.
    """
    master = tmp_path / "master.mov"
    master.write_bytes(b"un master deja livre")
    with pytest.raises(codec_profiles.MasterAlreadyExistsError):
        codec_profiles.build_encode_command("prores_hq", "l.concat", 25, str(master))
    # Cas negatif 1: un chemin libre passe, et la commande porte `-n`, pas `-y`.
    command = codec_profiles.build_encode_command("prores_hq", "l.concat", 25,
                                                  str(tmp_path / "libre.mov"))
    assert "-y" not in command and command[1] == "-n"
    # Cas negatif 2: l'ecrasement demande explicitement retablit `-y`.
    forced = codec_profiles.build_encode_command("prores_hq", "l.concat", 25, str(master),
                                                 overwrite=True)
    assert forced[1] == "-y" and "-n" not in forced


@requires_ffmpeg_tools
def test_what_the_n_flag_really_does_and_why_it_is_not_enough(tmp_path) -> None:
    """Mesure du 2026-08-10, **non prevue** et elle change la conception.

    `-n` protege bien le fichier -- il reste intact, la ou `-y` le remplace --
    mais ffmpeg sort alors en **rc=0** avec `File ... already exists. Exiting.`
    Un appelant qui branche sur le code de retour croit donc avoir encode. `-n`
    est donc une ceinture, pas le mecanisme: le mecanisme est le refus **a la
    construction**, et un controle d'existence apres un rc nul le complete dans
    `run_encode`.
    """
    frames = make_sequence(tmp_path, values=(48, 168))
    list_path = write_list(tmp_path / "n.concat", frames)
    master = tmp_path / "n.mov"
    master.write_bytes(b"x" * 2048)
    tail = ["-r", "25", "-f", "concat", "-safe", "0", "-i", str(list_path),
            "-c:v", "prores_ks", "-pix_fmt", "yuv422p10le", "-r", "25", str(master)]

    refused = subprocess.run(["ffmpeg", "-n", *tail], capture_output=True, text=True)
    assert master.stat().st_size == 2048, "-n a laisse ecraser le fichier"
    assert "already exists" in refused.stderr
    assert refused.returncode == 0, "le rc de -n est nul, c'est le piege"

    accepted = subprocess.run(["ffmpeg", "-y", *tail], capture_output=True, text=True)
    assert accepted.returncode == 0
    assert master.stat().st_size != 2048


@requires_ffmpeg_tools
def test_a_zero_return_code_without_a_file_is_still_an_error(tmp_path, monkeypatch) -> None:
    """Corollaire du precedent: un rc nul ne prouve pas qu'un fichier existe.

    Sans ce controle, `run_encode` partirait sonder un fichier absent et
    leverait une erreur de `ffprobe`, hors de la hierarchie du module.
    """
    frames = make_sequence(tmp_path, values=(49, 169))
    real_run = subprocess.run
    # Le catalogue d'encodeurs se lit par `ffmpeg -encoders`, et
    # `available_encoders` est memoise (`functools.lru_cache`). Le double
    # ci-dessous interceptant TOUTE commande `ffmpeg`, il rendrait une sortie
    # vide a `ensure_encoder_available` et le test echouerait sur un
    # `EncoderUnavailableError` au lieu de mesurer ce qu'il vise.
    #
    # Ce test passait donc SEULEMENT quand un test anterieur avait deja
    # rechauffe le cache -- une reussite qui dependait de l'ORDRE
    # d'execution, et que la repartition de `pytest-xdist` peut changer sans
    # qu'aucune ligne de production ne bouge. Trouve le 2026-09-03 en jouant
    # ce fichier avec un banc de plus (story 6.7) : la meme liste de tests,
    # un fichier en plus, et ce test rougissait. Verifie sur le commit
    # anterieur a la story : rouge aussi, joue seul.
    codec_profiles.available_encoders.cache_clear()
    codec_profiles.available_encoders("ffmpeg")

    def silent_success(command, *args, **kwargs):
        if command and str(command[0]).endswith("ffmpeg"):
            return subprocess.CompletedProcess(command, 0, "", "File already exists. Exiting.")
        return real_run(command, *args, **kwargs)

    monkeypatch.setattr(codec_profiles.subprocess, "run", silent_success)
    with pytest.raises(codec_profiles.EncodeRunError, match="sans produire"):
        codec_profiles.run_encode("prores_hq", frames, 25, tmp_path / "fantome.mov")
    assert not (tmp_path / "fantome.mov").exists()


@requires_ffmpeg_tools
@pytest.mark.parametrize("mode", ["echec_ffmpeg", "echec_verification"])
def test_a_failed_encode_leaves_the_previous_master_intact_and_no_residue(
    tmp_path, monkeypatch, mode
) -> None:
    """AC 5 et AC 15: master preexistant **intact**, aucun temporaire ni fichier
    de liste residuel, sur les deux familles d'echec atteignables."""
    frames = make_sequence(tmp_path, values=(75, 165))
    destination = tmp_path / "sortie"
    master = destination / "master.mov"
    codec_profiles.run_encode("prores_hq", frames, 25, master)
    reference = master.read_bytes()

    base = codec_profiles.get_profile("prores_hq")
    if mode == "echec_ffmpeg":
        # `-profile:v 999` est hors de [-1..5]: ffmpeg sort en rc=222.
        broken = dataclasses.replace(base, profile_id="t_broken",
                                     extra_args=("-profile:v", "999"))
        expected = codec_profiles.EncodeRunError
    else:
        broken = dataclasses.replace(base, profile_id="t_broken", pix_fmt="yuv420p")
        expected = codec_profiles.EncodeVerificationError
    monkeypatch.setitem(codec_profiles.PROFILES, "t_broken", broken)

    with pytest.raises(expected):
        codec_profiles.run_encode("t_broken", frames, 25, master, overwrite=True)

    assert master.read_bytes() == reference
    assert sorted(path.name for path in destination.iterdir()) == ["master.mov"]


# --- AC 6: le conteneur est applique -------------------------------------


@requires_ffmpeg
def test_an_extension_contradicting_the_container_is_refused(tmp_path) -> None:
    """AC 6: mesure, `prores_hq -> m.mkv` et `h264_delivery -> deliv.mov`
    sortent tous deux en rc=0. Un master ProRes dans un `.mkv` est un fichier
    que la post-production refusera sans que rien ne l'ait signale."""
    with pytest.raises(codec_profiles.EncodeConfigurationError, match="mkv"):
        codec_profiles.build_encode_command("prores_hq", "l.concat", 25, "m.mkv")
    with pytest.raises(codec_profiles.EncodeConfigurationError, match="contradiction"):
        codec_profiles.build_encode_command("h264_delivery", "l.concat", 25, "deliv.mov")
    with pytest.raises(codec_profiles.EncodeConfigurationError, match="aucune"):
        codec_profiles.build_encode_command("prores_hq", "l.concat", 25, "sans_extension")
    # Cas negatif: l'extension conforme passe, en majuscules comprises.
    assert codec_profiles.build_encode_command("prores_hq", "l.concat", 25, "m.MOV")
    frames = make_sequence(tmp_path, values=(85, 155))
    with pytest.raises(codec_profiles.EncodeConfigurationError):
        codec_profiles.run_encode("prores_hq", frames, 25, tmp_path / "m.mkv")
    assert not (tmp_path / "m.mkv").exists()


@requires_ffmpeg
def test_ffmpeg_itself_accepts_the_contradiction_the_factory_refuses(tmp_path) -> None:
    """Cas negatif de l'AC 6: sans la garde, rien ne signale l'incoherence."""
    frames = make_sequence(tmp_path, values=(95, 145))
    list_path = write_list(tmp_path / "c.concat", frames)
    result = subprocess.run(
        ["ffmpeg", "-y", "-r", "25", "-f", "concat", "-safe", "0", "-i", str(list_path),
         "-c:v", "prores_ks", "-pix_fmt", "yuv422p10le", "-r", "25", str(tmp_path / "m.mkv")],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


# --- AC 7: les contraintes dimensionnelles, par encodeur -----------------


@pytest.mark.parametrize(
    "width, height, refused_by",
    [
        (320, 180, set()),
        # Les deux dimensions impaires: ProRes et DNxHR les acceptent, seule la
        # famille H.26x les refuse. Une regle par sous-echantillonnage se
        # tromperait ici.
        (321, 181, {"h264_delivery", "hevc_delivery"}),
        # Les deux dimensions **paires** et pourtant refusees par DNxHR: c'est
        # le cas qu'une regle de parite laisserait passer.
        (240, 120, {"dnxhr_hq", "dnxhr_hqx"}),
        (256, 120, set()),
        # Hauteur sous le plancher DNxHR, largeur conforme.
        (256, 110, {"dnxhr_hq", "dnxhr_hqx"}),
        # Le materiau reel du depot: tpl-a4-portrait-1f-v1 a 600 dpi.
        (3307, 1860, {"h264_delivery", "hevc_delivery"}),
        (240, 136, {"dnxhr_hq", "dnxhr_hqx"}),
        # Plancher libx265, mesure a 16 sur les deux dimensions.
        (14, 14, {"dnxhr_hq", "dnxhr_hqx", "hevc_delivery"}),
        (16, 16, {"dnxhr_hq", "dnxhr_hqx"}),
        # Les deux planchers de libx265 sont **independants**, et une seule
        # ligne 14x14 ne le montre pas: elle viole les deux a la fois, donc un
        # plancher abaisse sur un axe reste couvert par l'autre. Mesure du
        # 2026-08-10: 14x32 et 32x14 sortent tous deux en rc=234, 16x32 et
        # 32x16 en rc=0.
        (14, 32, {"dnxhr_hq", "dnxhr_hqx", "hevc_delivery"}),
        (32, 14, {"dnxhr_hq", "dnxhr_hqx", "hevc_delivery"}),
        (16, 32, {"dnxhr_hq", "dnxhr_hqx"}),
        # Meme raisonnement pour la parite de la famille H.26x: 321x181 viole
        # les deux axes a la fois. Mesure: 321x180 et 320x181 sortent en
        # rc=187 (libx264) et rc=183 (libx265).
        (321, 180, {"h264_delivery", "hevc_delivery"}),
        (320, 181, {"h264_delivery", "hevc_delivery"}),
    ],
)
def test_dimension_rules_are_per_encoder_not_per_subsampling(width, height, refused_by) -> None:
    actual = set()
    for profile_id, profile in codec_profiles.PROFILES.items():
        try:
            codec_profiles.check_target_dimensions(profile, width, height)
        except codec_profiles.EncodeConfigurationError:
            actual.add(profile_id)
    assert actual == refused_by, (width, height, actual)


@requires_ffmpeg
@pytest.mark.parametrize(
    "profile_id, width, height, encodes",
    [
        ("prores_hq", 321, 181, True),
        ("h264_delivery", 321, 181, False),
        ("hevc_delivery", 321, 181, False),
        ("dnxhr_hq", 240, 120, False),
        ("dnxhr_hq", 256, 120, True),
        ("dnxhr_hq", 256, 110, False),
        ("h264_delivery", 240, 120, True),
        # Un axe a la fois, pour que chaque plancher et chaque parite soit
        # confronte a ffmpeg **seul**.
        ("hevc_delivery", 14, 32, False),
        ("hevc_delivery", 32, 14, False),
        ("hevc_delivery", 16, 32, True),
        ("h264_delivery", 321, 180, False),
        ("h264_delivery", 320, 181, False),
    ],
)
def test_the_dimension_rules_agree_with_what_ffmpeg_really_does(
    tmp_path, profile_id, width, height, encodes
) -> None:
    """La garde est confrontee a l'encodeur, pas a elle-meme.

    Le verdict de la fabrique et le code de retour de ffmpeg doivent dire la
    meme chose: c'est la seule facon de prouver que la table de contraintes
    n'est pas une constante recopiee.
    """
    profile = codec_profiles.get_profile(profile_id)
    frames = make_sequence(tmp_path, values=(105, 135), size=(width, height))
    list_path = write_list(tmp_path / "d.concat", frames)
    result = subprocess.run(
        ["ffmpeg", "-y", "-r", "25", "-f", "concat", "-safe", "0", "-i", str(list_path),
         *profile.ffmpeg_video_args(), "-r", "25",
         str(tmp_path / f"d.{profile.container}")],
        capture_output=True, text=True,
    )
    assert (result.returncode == 0) is encodes, result.stderr[-400:]
    refused = False
    try:
        codec_profiles.check_target_dimensions(profile, width, height)
    except codec_profiles.EncodeConfigurationError:
        refused = True
    assert refused is not encodes


def test_the_refusal_names_the_nearest_conforming_geometry() -> None:
    """Question ouverte 2, tranchee: la valeur conforme est calculee **ici**."""
    with pytest.raises(codec_profiles.EncodeConfigurationError) as error:
        codec_profiles.check_target_dimensions(
            codec_profiles.get_profile("h264_delivery"), 3307, 1861
        )
    message = str(error.value)
    assert "libx264" in message and "h264_delivery" in message
    assert "largeur 3307 impaire" in message and "hauteur 1861 impaire" in message
    assert "3306x1860" in message

    with pytest.raises(codec_profiles.EncodeConfigurationError) as error:
        codec_profiles.check_target_dimensions(codec_profiles.get_profile("dnxhr_hq"), 240, 110)
    # Pour DNxHR ce n'est pas une parite mais un seuil: la valeur rendue est le
    # seuil, pas un arrondi -- et 241x111 serait accepte par l'encodeur.
    assert "256x120" in str(error.value)
    codec_profiles.check_target_dimensions(codec_profiles.get_profile("dnxhr_hq"), 257, 121)


def test_an_unmeasured_encoder_is_refused_rather_than_assumed_permissive() -> None:
    with pytest.raises(codec_profiles.EncodeConfigurationError, match="mesuree"):
        codec_profiles.dimension_rule("libsvtav1")


@requires_ffmpeg_tools
def test_the_target_geometry_is_applied_and_lifts_the_odd_dimension(tmp_path) -> None:
    """AC 2: 6.1 decide la valeur, 6.0 l'applique -- y compris quand elle rend
    conforme une entree que l'encodeur aurait refusee."""
    frames = make_sequence(tmp_path, values=(115, 125), size=(321, 181))
    with pytest.raises(codec_profiles.EncodeConfigurationError):
        codec_profiles.run_encode("h264_delivery", frames, 25, tmp_path / "brut.mp4")
    outcome = codec_profiles.run_encode(
        "h264_delivery", frames, 25, tmp_path / "cible.mp4", target_size=(320, 180)
    )
    assert outcome.source_size == (321, 181)
    assert outcome.encoded_size == (320, 180)
    assert ffprobe_field(tmp_path / "cible.mp4", "width,height") == ["320", "180"]


# --- AC 8: les formes heterogenes ----------------------------------------


@requires_ffmpeg_tools
def test_heterogeneous_shapes_are_refused_even_when_the_odd_one_is_not_first(tmp_path) -> None:
    """AC 8 et AC 15: la forme divergente est placee en **troisieme** position.

    C'est le seul montage qui demasque une garde ne sondant que la premiere
    frame -- et c'est exactement ce que fait ffmpeg: il fige la geometrie sur la
    premiere entree, redimensionne les suivantes en silence, et le controle de
    cardinal passe.
    """
    small = make_sequence(tmp_path, values=(20, 60, 100), size=(320, 180))
    large = write_tiff16(tmp_path / "large.tiff", np.full((181, 321, 3), 220, dtype=np.uint8))
    sequence = [small[0], small[1], large, small[2]]

    # Ce que ffmpeg fait tout seul, sans un mot.
    list_path = write_list(tmp_path / "het.concat", sequence)
    output = tmp_path / "het.mov"
    result = subprocess.run(
        ["ffmpeg", "-y", "-r", "25", "-f", "concat", "-safe", "0", "-i", str(list_path),
         "-c:v", "prores_ks", "-pix_fmt", "yuv422p10le", "-r", "25", str(output)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert ffprobe_field(output, "width,height") == ["320", "180"]
    assert ffprobe_field(output, "nb_frames")[0] == "4"  # cardinal conforme !

    with pytest.raises(codec_profiles.EncodeConfigurationError) as error:
        codec_profiles.ensure_uniform_frame_shapes(sequence)
    assert "320x180" in str(error.value) and "321x181" in str(error.value)
    with pytest.raises(codec_profiles.EncodeConfigurationError, match="heterogenes"):
        codec_profiles.run_encode("prores_hq", sequence, 25, tmp_path / "refus.mov")
    assert not (tmp_path / "refus.mov").exists()
    # Cas negatif: une sequence homogene passe.
    assert codec_profiles.ensure_uniform_frame_shapes(small) == (320, 180)


@requires_ffmpeg_tools
def test_an_unreadable_frame_is_named(tmp_path) -> None:
    with pytest.raises(codec_profiles.EncodeConfigurationError, match="illisible"):
        codec_profiles.probe_frame_size(tmp_path / "absente.tiff")


@requires_ffmpeg_tools
@pytest.mark.parametrize("pix_fmt, label", [("gray16le", "gris"), ("rgba64le", "alpha")])
def test_grayscale_and_rgba_inputs_encode_and_lose_their_extra_channel(
    tmp_path, pix_fmt, label
) -> None:
    """AC 15: entree en niveaux de gris et en RGBA.

    Mesure d'origine: l'alpha est detruit **sans aucun avertissement**. La
    fabrique ne l'invente pas non plus: elle encode, et le master sort dans le
    `pix_fmt` du profil. Le test verrouille le fait plutot que de le supposer.
    """
    channels = 1 if pix_fmt.startswith("gray") else 4
    shape = (180, 320) if channels == 1 else (180, 320, 4)
    array = np.full(shape, 140, dtype=np.uint8)
    if channels == 4:
        array[..., 3] = 128
        array[..., 0] = 255
    first = write_tiff16(tmp_path / f"{label}_1.tiff", array, pix_fmt=pix_fmt)
    second_source = np.full(shape, 60, dtype=np.uint8)
    if channels == 4:
        second_source[..., 3] = 200
    second = write_tiff16(tmp_path / f"{label}_2.tiff", second_source, pix_fmt=pix_fmt)

    outcome = codec_profiles.run_encode(
        "prores_hq", [first, second], 25, tmp_path / f"{label}.mov"
    )
    assert outcome.frame_count == 2
    assert outcome.pix_fmt == "yuv422p10le"


# --- AC 9: la disponibilite des encodeurs --------------------------------


@requires_ffmpeg
def test_encoder_availability_is_read_from_the_listing_not_from_a_return_code() -> None:
    """AC 9: `-h encoder=libnonexistent` rend **rc=0**.

    Une garde branchee sur le code de retour declarerait disponible tout
    encodeur, y compris inexistant -- le mode de panne silencieux que la story
    denonce ailleurs.
    """
    helper = subprocess.run(["ffmpeg", "-hide_banner", "-h", "encoder=libnonexistent"],
                            capture_output=True, text=True)
    assert helper.returncode == 0
    assert "is not recognized" in helper.stdout + helper.stderr

    encoders = codec_profiles.available_encoders()
    assert "libnonexistent" not in encoders
    for profile in codec_profiles.PROFILES.values():
        assert profile.vcodec in encoders, profile.profile_id


@requires_ffmpeg
def test_an_absent_encoder_is_refused_before_any_frame_is_read(tmp_path) -> None:
    absent = dataclasses.replace(
        codec_profiles.get_profile("prores_hq"), profile_id="t_absent", vcodec="libnonexistent"
    )
    with pytest.raises(codec_profiles.EncoderUnavailableError, match="libnonexistent"):
        codec_profiles.ensure_encoder_available(absent)
    # Cas negatif: le profil livre passe la meme garde.
    codec_profiles.ensure_encoder_available(codec_profiles.get_profile("prores_hq"))


def test_availability_and_usability_are_two_independent_guards() -> None:
    """AC 9: `dnxhd` figure dans `-encoders` et refuse pourtant 240x136."""
    profile = codec_profiles.get_profile("dnxhr_hq")
    codec_profiles.ensure_encoder_available(profile)
    with pytest.raises(codec_profiles.EncodeConfigurationError):
        codec_profiles.check_target_dimensions(profile, 240, 136)


def test_a_missing_ffmpeg_binary_is_named() -> None:
    with pytest.raises(codec_profiles.EncoderUnavailableError, match="introuvable"):
        codec_profiles.available_encoders("ffmpeg-qui-nexiste-pas")


# --- AC 10: decrire un encodage n'est pas decrire un profil ---------------


@requires_ffmpeg_tools
def test_the_encode_description_is_the_only_one_that_can_tell_two_rates_apart(
    tmp_path,
) -> None:
    """AC 10: `manifest_fields()` ne prend aucun argument et le dataclass est
    gele sans champ de cadence -- elle **ne peut pas** distinguer deux cadences.
    """
    frames = make_sequence(tmp_path, values=(25, 155))
    slow = codec_profiles.run_encode("prores_hq", frames, 12.5, tmp_path / "lent.mov")
    fast = codec_profiles.run_encode("prores_hq", frames, 25, tmp_path / "rapide.mov")

    profile = codec_profiles.get_profile("prores_hq")
    slow_fields = codec_profiles.encode_manifest_fields(slow)
    fast_fields = codec_profiles.encode_manifest_fields(fast)
    assert slow_fields != fast_fields
    assert (slow_fields["frame_rate"], fast_fields["frame_rate"]) == ("25/2", "25/1")
    assert slow_fields["frame_count"] == fast_fields["frame_count"] == 2
    assert slow_fields["filter_chain"] == (
        "scale=out_color_matrix=bt709:out_range=tv,"
        + codec_profiles.build_setparams_link("bt709")
    )
    assert slow_fields["output_path"].endswith("lent.mov")
    # La description d'encodage contient celle du profil, sans la remplacer.
    assert set(profile.manifest_fields()) <= set(slow_fields)


@requires_ffmpeg_tools
def test_the_encode_description_carries_the_target_geometry(tmp_path) -> None:
    frames = make_sequence(tmp_path, values=(35, 145), size=(322, 182))
    outcome = codec_profiles.run_encode(
        "prores_hq", frames, 25, tmp_path / "cible.mov", target_size=(160, 90)
    )
    fields = codec_profiles.encode_manifest_fields(outcome)
    assert fields["source_resolution"] == "322x182"
    assert fields["target_resolution"] == "160x90"
    assert fields["encoded_resolution"] == "160x90"
    assert fields["filter_chain"] == (
        "scale=160:90:out_color_matrix=bt709:out_range=tv,"
        + codec_profiles.build_setparams_link("bt709")
    )


# --- AC 11: les doublons d'options ---------------------------------------


def test_a_duplicated_option_is_refused_at_construction() -> None:
    """AC 11: ffmpeg retient le **dernier** (mesure), donc l'ordre actuel est
    le bon. Un doublon n'en reste pas moins le symptome d'un profil mal ecrit.
    """
    doubled = dataclasses.replace(
        codec_profiles.get_profile("prores_hq"), profile_id="t_double",
        extra_args=("-profile:v", "3", "-pix_fmt", "yuv420p"),
    )
    with pytest.raises(codec_profiles.EncodeConfigurationError, match="-pix_fmt"):
        codec_profiles._reject_duplicate_options(
            doubled.ffmpeg_video_args(), "les arguments video"
        )
    # Cas negatif: aucun profil livre ne porte de doublon.
    for profile in codec_profiles.PROFILES.values():
        codec_profiles._reject_duplicate_options(profile.ffmpeg_video_args(), profile.profile_id)


def test_the_duplicate_guard_runs_on_every_built_command(monkeypatch) -> None:
    doubled = dataclasses.replace(
        codec_profiles.get_profile("prores_hq"), profile_id="t_double2",
        extra_args=("-vendor", "apl0", "-vendor", "zzzz"),
    )
    monkeypatch.setitem(codec_profiles.PROFILES, "t_double2", doubled)
    with pytest.raises(codec_profiles.EncodeConfigurationError, match="-vendor"):
        codec_profiles.build_encode_command("t_double2", "l.concat", 25, "o.mov")


@requires_ffmpeg_tools
def test_ffmpeg_keeps_the_last_duplicate_not_the_first(tmp_path) -> None:
    """Le constat d'origine de la story 6.2 etait faux, et la garde en depend:
    si ffmpeg retenait le **premier**, `extra_args` en dernier ne pourrait rien
    surcharger et il faudrait inverser l'ordre d'emission."""
    frames = make_sequence(tmp_path, values=(45, 135))
    list_path = write_list(tmp_path / "dup.concat", frames)
    output = tmp_path / "dup.mp4"
    result = subprocess.run(
        ["ffmpeg", "-y", "-r", "25", "-f", "concat", "-safe", "0", "-i", str(list_path),
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-pix_fmt", "yuv444p",
         "-preset", "ultrafast", "-r", "25", str(output)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert ffprobe_field(output, "pix_fmt")[0] == "yuv444p"


def test_the_profile_emits_its_overrides_last() -> None:
    args = codec_profiles.get_profile("prores_hq").ffmpeg_video_args()
    assert args.index("-profile:v") > args.index("-c:v")


# --- AC 14: la base de validation du timecode ----------------------------


def test_timecode_to_frame_index_uses_the_ceiling_not_the_exact_rate() -> None:
    """Story 6.6, AC 3. Deux cadences de meme plafond rendent le meme index --
    seul `ceil(rate)` entre dans l'arithmetique hh:mm:ss:ff, jamais la partie
    fractionnaire.
    """
    assert codec_profiles.timecode_to_frame_index("00:00:00:00", 25) == 0
    assert codec_profiles.timecode_to_frame_index("00:00:01:00", 25) == 25
    assert codec_profiles.timecode_to_frame_index("00:00:00:12", 12.5) == 12
    assert codec_profiles.timecode_to_frame_index("00:00:01:00", 12.5) == 13
    assert codec_profiles.timecode_to_frame_index("00:00:01:00", 24.1) == \
        codec_profiles.timecode_to_frame_index("00:00:01:00", 24.9)
    assert codec_profiles.timecode_to_frame_index("01:02:03:04", 25) == \
        ((1 * 60 + 2) * 60 + 3) * 25 + 4


def test_timecode_to_frame_index_refuses_unreadable_and_drop_frame() -> None:
    with pytest.raises(codec_profiles.EncodeConfigurationError, match="illisible"):
        codec_profiles.timecode_to_frame_index("pas un timecode", 25)
    with pytest.raises(codec_profiles.EncodeConfigurationError, match="drop-frame"):
        codec_profiles.timecode_to_frame_index("00:00:00;04", 30)


def test_the_timecode_base_is_separate_from_the_encode_rate() -> None:
    """AC 14: reproduit sur le lot reel TEST_FILE_12p5 (`fps_target` 12.5,
    `timecode_base_fps` 25/1). `00:00:00:14` est parfaitement legal en base
    source et etait pourtant rejete par la fabrique.
    """
    with pytest.raises(ValueError, match="frames 14"):
        codec_profiles.build_encode_command(
            "prores_hq", "l.concat", 12.5, "o.mov", timecode="00:00:00:14"
        )
    command = codec_profiles.build_encode_command(
        "prores_hq", "l.concat", 12.5, "o.mov",
        timecode="00:00:00:14", timecode_base_fps=25,
    )
    assert command[command.index("-timecode") + 1] == "00:00:00:14"
    # La cadence d'encodage, elle, reste celle du lot.
    assert command[command.index("-timecode") - 1] == "25/2"


def test_validate_timecode_keeps_the_bound_the_ac_14_caller_was_missing() -> None:
    """AC 14: six modules importent `validate_timecode`, sa borne ne bouge pas.

    Enonce corrige le 2026-08-10. La revision 2 de la story ecrivait que
    `validate_timecode` n'etait "pas modifiee" et que "son comportement est
    correct -- c'est son appelant qui lui passait la mauvaise cadence". Le
    diagnostic de l'AC 14 tient, mais l'affirmation d'ensemble etait fausse: la
    fonction imposait aussi au champ `ff` une largeur de deux chiffres, que
    ffmpeg n'ecrit pas (voir la section sur la largeur d'ecriture, en fin de
    fichier). Ce qui reste vrai, et que ce test verrouille, c'est la **borne**
    `ff < ceil(cadence)`, seule en cause dans l'AC 14.
    """
    assert codec_profiles.validate_timecode("00:00:00:14", 25) == "00:00:00:14"
    with pytest.raises(ValueError, match="frames 14 >= 13"):
        codec_profiles.validate_timecode("00:00:00:14", 12.5)


@requires_ffmpeg_tools
def test_a_timecode_in_the_encode_base_reaches_the_master(tmp_path) -> None:
    from mixed_media_utility import video_metadata

    frames = make_sequence(tmp_path, values=(55, 125))
    outcome = codec_profiles.run_encode(
        "prores_hq", frames, 25, tmp_path / "tc.mov",
        timecode="00:00:00:14", timecode_base_fps=25,
    )
    assert outcome.timecode_base == "25/1"
    assert outcome.frame_rate == "25/1"
    report = video_metadata.verify_technical_metadata(
        str(tmp_path / "tc.mov"), {"timecode": "00:00:00:14"}, require_mandatory=False
    )
    assert report["timecode"]["ok"], report


@requires_ffmpeg_tools
def test_ffmpeg_rerenders_the_timecode_at_the_output_rate_and_the_lie_is_refused(
    tmp_path,
) -> None:
    """Mesure du 2026-08-10 **non prevue par la story**, et elle borne l'AC 14.

    Separer la base de validation de la cadence d'encodage rend un timecode de
    base source *acceptable* a la construction. Elle ne le rend pas *juste*
    dans le conteneur: ffmpeg convertit la chaine de `-timecode` en numero de
    frame et la re-rend **a la cadence de sortie**. `00:00:00:14` a 12,5 im/s
    ressort donc en `00:00:01:01`, avec rc=0 et sans un mot.

    Convertir la base est une decision de cadrage (story 6.1). Ce que fait
    cette story, c'est refuser de livrer un master qui ment.
    """
    frames = make_sequence(tmp_path, values=(65, 115))
    # La construction, elle, passe: c'est bien l'AC 14 qui est tenue.
    command = codec_profiles.build_encode_command(
        "prores_hq", "l.concat", 12.5, "o.mov",
        timecode="00:00:00:14", timecode_base_fps=25,
    )
    assert "00:00:00:14" in command

    # Ce que ffmpeg ecrit reellement, sans la garde.
    list_path = write_list(tmp_path / "tc.concat", frames)
    brut = tmp_path / "brut.mov"
    result = subprocess.run(
        ["ffmpeg", "-y", "-r", "25/2", "-f", "concat", "-safe", "0", "-i", str(list_path),
         "-c:v", "prores_ks", "-pix_fmt", "yuv422p10le", "-r", "25/2",
         "-timecode", "00:00:00:14", str(brut)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    from mixed_media_utility import video_metadata
    assert video_metadata.read_technical_metadata(str(brut))["timecode"] == "00:00:01:01"

    # Avec la garde: erreur typee, et aucun master livre.
    with pytest.raises(codec_profiles.EncodeVerificationError, match="00:00:01:01"):
        codec_profiles.run_encode(
            "prores_hq", frames, 12.5, tmp_path / "menteur.mov",
            timecode="00:00:00:14", timecode_base_fps=25,
        )
    assert not (tmp_path / "menteur.mov").exists()


# --- AC 13: les frontieres tenues ----------------------------------------


def test_no_ntsc_point_is_reopened_by_this_story() -> None:
    """AC 13, enonce mecanisable: le grep porte sur `codec_profiles.py` seul,
    et **aucune** decimale NTSC n'apparait dans la section ajoutee par 6.0.

    L'ajournement de la story 6.2 porte sur le NTSC (23.976 / 29.97 / 59.94,
    drop-frame, profils dedies) et reste valide.
    """
    source = (REPO_ROOT / "src" / "mixed_media_utility" / "codec_profiles.py").read_text(
        encoding="utf-8"
    )
    marker = "# Story 6.0 - fiabilisation de la fabrique de commande d'encodage."
    assert marker in source
    head, tail = source.split(marker, 1)
    for decimal in ("23.976", "29.97", "59.94", "47.952", "119.88", "24000, 1001"):
        assert decimal not in tail, decimal
    # Cas negatif: les occurrences preexistantes sont bien la, inchangees.
    assert "_EXACT_RATES" in head and "NTSC_RATES" in head
    assert "Fraction(24000, 1001): (23.976, 23.98)" in head
    assert "drop-frame" in head


def test_the_factory_knows_nothing_about_projects_lots_or_manifests() -> None:
    """AC 13: elle recoit une liste de chemins, un profil, une geometrie
    facultative. Elle n'ecrit aucun manifest et ne lit aucun projet."""
    source = (REPO_ROOT / "src" / "mixed_media_utility" / "codec_profiles.py").read_text(
        encoding="utf-8"
    )
    for forbidden in ("from .io", "from mixed_media_utility.io", "project.json",
                      "output-frames", "ExtractionManifest"):
        assert forbidden not in source, forbidden


# --- le chemin nominal complet -------------------------------------------


@requires_ffmpeg_tools
def test_the_nominal_chain_produces_a_master_that_matches_its_own_description(
    tmp_path,
) -> None:
    frames = make_sequence(tmp_path, values=(30, 190), size=(3307, 1860))
    outcome = codec_profiles.run_encode(
        "prores_hq", frames, 25, tmp_path / "sortie" / "master.mov",
        target_size=(1920, 1080), timecode="01:00:00:00",
        container_tags={"rush_id": "R42"},
    )
    assert outcome.frame_count == 2
    assert outcome.encoded_size == (1920, 1080)
    assert outcome.source_size == (3307, 1860)
    assert outcome.pix_fmt == "yuv422p10le"
    master = tmp_path / "sortie" / "master.mov"
    assert ffprobe_field(master, "width,height") == ["1920", "1080"]
    assert ffprobe_field(master, "nb_frames") == ["2"]
    assert ffprobe_field(master, "color_space") == ["bt709"]
    assert ffprobe_field(master, "pix_fmt") == ["yuv422p10le"]
    # Aucun residu: ni temporaire, ni fichier de liste.
    assert sorted(path.name for path in (tmp_path / "sortie").iterdir()) == ["master.mov"]


# ---------------------------------------------------------------------------
# Passe de correction apres la revue en trois couches (2026-08-10).
#
# Les quatre bloquants, les majeurs, et le cablage des gardes -- que les
# campagnes de mutation ont trouve teste **en isolation** et jamais a son point
# d'appel.
# ---------------------------------------------------------------------------


# --- l'ordre des frames livrees ------------------------------------------


@requires_ffmpeg_tools
def test_the_master_delivers_its_frames_in_the_order_they_were_given(tmp_path) -> None:
    """Bloquant 1: **le master produit est decode**, et son ordre confronte.

    Trois couches ont trouve le meme trou par trois chemins: mesure directe
    (quatre sequences sur les memes six frames -- nominale, melangee, inversee,
    six fois la meme -- toutes en `rc=0` avec `frame_count=6`), mutation
    (M48/M49/M102 survivants), et lecture. Aucune des quatre confrontations de
    `verify_encoded_output` -- cardinal, `pix_fmt`, geometrie, timecode -- ne
    depend de l'ordre.
    """
    frames = make_timecoded_sequence(tmp_path, values=(40, 120, 200))
    master = tmp_path / "sortie" / "ordre.mov"
    outcome = codec_profiles.run_encode("prores_hq", frames, 25, master)
    assert outcome.frame_count == 3

    levels = decoded_frame_levels(master, 3)
    for measured, expected in zip(levels, (40, 120, 200)):
        assert abs(measured - expected) < 3.0, levels
    # L'assertion qui compte: l'ordre, pas seulement l'ensemble.
    assert levels == sorted(levels), levels


@requires_ffmpeg_tools
def test_the_given_order_wins_even_when_it_is_not_the_alphabetical_one(tmp_path) -> None:
    """Cas negatif du precedent: un tri impose par la fabrique se verrait.

    La migration naturelle depuis l'ancien motif `%0Nd` est
    `glob.glob(dossier + '/*.tiff')`, qui rend l'ordre du **systeme de
    fichiers** (mesure: `05,03,04,06,01,02`). Une fabrique qui trierait
    d'autorite serait tout aussi fausse: c'est l'appelant qui decide.
    """
    bright = write_tiff16(tmp_path / "a_clair.tiff",
                          np.full((180, 320, 3), 210, dtype=np.uint8))
    dark = write_tiff16(tmp_path / "b_sombre.tiff",
                        np.full((180, 320, 3), 30, dtype=np.uint8))
    master = tmp_path / "antialpha.mov"
    # Ordre demande: sombre puis clair -- l'inverse de l'ordre alphabetique.
    codec_profiles.run_encode("prores_hq", [dark, bright], 25, master)
    levels = decoded_frame_levels(master, 2)
    assert levels[0] < levels[1], levels
    assert abs(levels[0] - 30) < 3.0 and abs(levels[1] - 210) < 3.0, levels


def test_a_sequence_that_goes_backwards_in_time_is_refused(tmp_path) -> None:
    """La garde de monotonie: les noms portent le timecode, elle est calculable."""
    names = [f"TEST_FILE_5_00-00-00-{value:02d}.tiff" for value in (0, 5, 10)]
    assert codec_profiles.ensure_frame_order(names) == ["00-00-00-00", "00-00-00-05",
                                                       "00-00-00-10"]
    with pytest.raises(codec_profiles.EncodeConfigurationError, match="non monotone"):
        codec_profiles.ensure_frame_order([names[0], names[2], names[1]])
    with pytest.raises(codec_profiles.EncodeConfigurationError, match="non monotone"):
        codec_profiles.ensure_frame_order(list(reversed(names)))
    # Sans timecode dans les noms, la garde n'est pas calculable et le dit.
    assert codec_profiles.ensure_frame_order(["frame_0001.png", "frame_0002.png"]) is None
    assert codec_profiles.frame_timecodes(["a_00-00-00-00.tiff", "sans.tiff"]) is None


@requires_ffmpeg_tools
def test_the_order_guard_is_wired_into_run_encode(tmp_path) -> None:
    frames = make_timecoded_sequence(tmp_path, values=(50, 150, 250))
    shuffled = [frames[2], frames[0], frames[1]]
    with pytest.raises(codec_profiles.EncodeConfigurationError, match="non monotone"):
        codec_profiles.run_encode("prores_hq", shuffled, 25, tmp_path / "melange.mov")
    assert not (tmp_path / "melange.mov").exists()


@requires_ffmpeg_tools
def test_a_held_frame_is_a_valid_sequence_not_a_defect(tmp_path) -> None:
    """Le "shoot on twos" du stop-motion: deux frames consecutives identiques.

    C'est la raison pour laquelle la garde d'ordre compare **sans strictitude**
    et le cardinal attendu n'est **jamais** deduplique. Un cardinal
    `len(set(frames))` refuserait ce master parfaitement legitime -- et le
    mutant qui le fait a survecu a la suite entiere.
    """
    frames = make_timecoded_sequence(tmp_path, values=(70, 180))
    held = [frames[0], frames[0], frames[1], frames[1]]
    outcome = codec_profiles.run_encode("prores_hq", held, 25, tmp_path / "tenue.mov")
    assert outcome.frame_count == 4
    assert ffprobe_field(tmp_path / "tenue.mov", "nb_frames")[0] == "4"
    levels = decoded_frame_levels(tmp_path / "tenue.mov", 4)
    assert abs(levels[0] - levels[1]) < 0.5 and abs(levels[2] - levels[3]) < 0.5, levels
    assert levels[0] < levels[2], levels


@requires_ffmpeg_tools
def test_relative_frame_paths_are_resolved_against_the_caller_not_the_list(
    tmp_path, monkeypatch
) -> None:
    """AC 3b, cas negatif: la liste vit dans le dossier de **destination**.

    Les chemins d'une liste `concat` se resolvent par rapport au fichier de
    liste. Des chemins relatifs recopies tels quels designeraient donc des
    fichiers inexistants -- ou, pire, d'autres fichiers.
    """
    source = tmp_path / "frames"
    source.mkdir()
    make_sequence(source, values=(58, 178))
    monkeypatch.chdir(tmp_path)
    relative = [Path("frames") / name for name in sorted(p.name for p in source.iterdir())]
    outcome = codec_profiles.run_encode("prores_hq", relative, 25, Path("sortie") / "m.mov")
    assert outcome.frame_count == 2
    assert (tmp_path / "sortie" / "m.mov").is_file()


# --- la matrice, derivee du profil et mesuree de bout en bout -------------


def test_the_matrix_emitted_is_the_one_of_the_profile_not_a_constant() -> None:
    """Bloquant 3: les 7 profils portent tous `bt709`, donc le test d'origine
    comparait `bt709` a `bt709`, sept fois -- et le mutant "valeur en dur"
    survivait a la suite entiere.

    La regle des fabriques du `CLAUDE.md`, appliquee a la constante centrale de
    la story: une fabrique qui ne produit qu'une seule valeur rend invisible
    toute erreur d'appariement.
    """
    profile = codec_profiles.get_profile("prores_hq")
    assert codec_profiles.build_filter_chain(profile).startswith(
        "scale=out_color_matrix=bt709:"
    )
    for matrix in sorted(codec_profiles.USABLE_COLOR_MATRICES - {"bt709"}):
        other = dataclasses.replace(profile, profile_id=f"t_{matrix}", colorspace=matrix)
        chain = codec_profiles.build_filter_chain(other)
        maillon = codec_profiles.build_setparams_link(matrix)
        assert chain == f"scale=out_color_matrix={matrix}:out_range=tv,{maillon}", chain
        # Le maillon `setparams` suit la meme valeur: une constante en dur y
        # ferait diverger le tag de la matrice reellement appliquee.
        assert "bt709" not in chain
        sized = codec_profiles.build_filter_chain(other, (160, 90))
        assert sized == f"scale=160:90:out_color_matrix={matrix}:out_range=tv,{maillon}"
        assert "bt709" not in sized


@requires_ffmpeg_tools
def test_the_matrix_of_a_derived_profile_reaches_the_master(tmp_path, monkeypatch) -> None:
    """La valeur choisie ci-dessus doit etre **reellement encodable**.

    C'est la ou la liste de matrices se lie au bloquant 3: asserter une chaine
    de filtres portant une valeur que ffmpeg refuse ne prouverait rien.
    """
    other = dataclasses.replace(
        codec_profiles.get_profile("prores_hq"), profile_id="t_170m", colorspace="smpte170m"
    )
    monkeypatch.setitem(codec_profiles.PROFILES, "t_170m", other)
    frames = make_sequence(tmp_path, values=(52, 162))
    outcome = codec_profiles.run_encode("t_170m", frames, 25, tmp_path / "m170.mov")
    assert outcome.filter_chain == (
        "scale=out_color_matrix=smpte170m:out_range=tv,"
        + codec_profiles.build_setparams_link("smpte170m")
    )
    assert ffprobe_field(tmp_path / "m170.mov", "color_space")[0] == "smpte170m"
    # Les trois champs suivent la matrice derivee, pas seulement la matrice:
    # c'est ce que le maillon `setparams` ajoute, et il porte la meme valeur.
    assert ffprobe_field(tmp_path / "m170.mov", "color_primaries")[0] == "smpte170m"
    assert ffprobe_field(tmp_path / "m170.mov", "color_transfer")[0] == "smpte170m"


@requires_ffmpeg_tools
@pytest.mark.parametrize("matrix", ["bt2020nc", "bt601", "bt470bg", "fcc", "bt2020"])
def test_the_matrix_vocabulary_is_the_one_measured_end_to_end(tmp_path, matrix) -> None:
    """Majeur 5: la liste laissait passer 5 valeurs sur 8, dont `bt2020nc` --
    c'est-a-dire **le cas fondateur** qu'elle etait censee fermer.

    Motif de l'erreur, remesure ici: la mesure d'origine ne portait que sur le
    filtre `scale`, qui accepte **tout** (les 15 candidats mesures rendent rc=0,
    `linear` et `iec61966-2-1` compris: swscale ignore en silence ce qu'il ne
    comprend pas). Le meme champ alimente pourtant les trois options de tag, au
    vocabulaire different. Chaque cas ci-dessous est confronte a ffmpeg.
    """
    profile = dataclasses.replace(
        codec_profiles.get_profile("prores_hq"), profile_id="t_bad", colorspace=matrix
    )
    with pytest.raises(codec_profiles.EncodeConfigurationError, match="inutilisable"):
        codec_profiles.build_filter_chain(profile)

    # Et ffmpeg, lui, echoue reellement: la garde n'est pas un exces de zele.
    frames = make_sequence(tmp_path, values=(53, 163))
    list_path = write_list(tmp_path / f"cs_{matrix}.concat", frames)
    result = subprocess.run(
        ["ffmpeg", "-y", "-r", "25", "-f", "concat", "-safe", "0", "-i", str(list_path),
         "-vf", f"scale=out_color_matrix={matrix}:out_range=tv",
         "-c:v", "prores_ks", "-pix_fmt", "yuv422p10le", "-profile:v", "3",
         "-colorspace", matrix, "-color_primaries", matrix, "-color_trc", matrix,
         "-r", "25", str(tmp_path / f"cs_{matrix}.mov")],
        capture_output=True, text=True,
    )
    assert result.returncode != 0, f"{matrix} passerait de bout en bout"


@requires_ffmpeg_tools
@pytest.mark.parametrize("matrix", sorted(["bt709", "smpte170m", "smpte240m"]))
def test_every_matrix_of_the_list_really_encodes(tmp_path, matrix) -> None:
    """Cas negatif du precedent: la liste n'est pas restreinte au point d'etre
    fausse dans l'autre sens. Les trois valeurs retenues encodent et se
    relisent."""
    assert matrix in codec_profiles.USABLE_COLOR_MATRICES
    profile = dataclasses.replace(
        codec_profiles.get_profile("prores_hq"), profile_id="t_ok", colorspace=matrix
    )
    frames = make_sequence(tmp_path, values=(54, 164))
    list_path = write_list(tmp_path / f"ok_{matrix}.concat", frames)
    output = tmp_path / f"ok_{matrix}.mov"
    result = subprocess.run(
        ["ffmpeg", "-y", "-r", "25", "-f", "concat", "-safe", "0", "-i", str(list_path),
         "-vf", codec_profiles.build_filter_chain(profile),
         *profile.ffmpeg_video_args(), "-r", "25", str(output)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr[-400:]
    assert ffprobe_field(output, "color_space")[0] == matrix


# --- la course entre deux encodages concurrents --------------------------


def test_the_output_path_is_reserved_atomically(tmp_path) -> None:
    """Bloquant 4: `exists()` puis `os.replace` est un TOCTOU.

    Mesure de la revue: quatre encodages concurrents en `overwrite=False` vers
    la meme cible rendent **quatre** succes, un seul master survit, et aucun
    appelant ne recoit `MasterAlreadyExistsError`.
    """
    target = tmp_path / "reserve.mov"
    codec_profiles._reserve_output_path(target)
    assert target.exists()
    with pytest.raises(codec_profiles.MasterAlreadyExistsError):
        codec_profiles._reserve_output_path(target)


@requires_ffmpeg_tools
def test_a_master_that_appears_during_the_encode_is_not_destroyed(tmp_path, monkeypatch) -> None:
    """La course, reproduite de facon deterministe.

    Le concurrent est simule en creant le master **entre** le refus courtois
    (`exists()`) et la reservation atomique: c'est exactement la fenetre que le
    TOCTOU ouvrait. Sans reservation, `run_engine` rendait un succes et
    `os.replace` detruisait le master de l'autre.
    """
    frames = make_sequence(tmp_path, values=(59, 169))
    master = tmp_path / "sortie" / "course.mov"
    real_guard = codec_profiles.ensure_encoder_available

    def concurrent(profile, ffmpeg_bin="ffmpeg"):
        master.parent.mkdir(parents=True, exist_ok=True)
        if not master.exists():
            master.write_bytes(b"le master de l'autre encodage")
        return real_guard(profile, ffmpeg_bin)

    monkeypatch.setattr(codec_profiles, "ensure_encoder_available", concurrent)
    with pytest.raises(codec_profiles.MasterAlreadyExistsError):
        codec_profiles.run_encode("prores_hq", frames, 25, master)
    assert master.read_bytes() == b"le master de l'autre encodage"


@requires_ffmpeg_tools
def test_the_reservation_leaves_nothing_behind_when_the_encode_fails(
    tmp_path, monkeypatch
) -> None:
    """Cas negatif de la reservation: elle ne doit pas devenir un residu.

    Le fichier vide pose par la reservation est retire par le `finally` -- il
    n'est jamais pose la ou un master existait, donc le retirer ne peut rien
    detruire.
    """
    frames = make_sequence(tmp_path, values=(61, 171))
    broken = dataclasses.replace(codec_profiles.get_profile("prores_hq"),
                                 profile_id="t_res", extra_args=("-profile:v", "999"))
    monkeypatch.setitem(codec_profiles.PROFILES, "t_res", broken)
    destination = tmp_path / "sortie"
    with pytest.raises(codec_profiles.EncodeRunError):
        codec_profiles.run_encode("t_res", frames, 25, destination / "rate.mov")
    assert list(destination.iterdir()) == []


# --- `-vf` en doublon, et les options qui appartiennent a la fabrique -----


def test_a_filter_chain_smuggled_in_extra_args_is_refused() -> None:
    """Majeur 6: `-vf` etait la seule option de sortie qu'un profil pouvait
    ecraser, et la seule dont l'ecrasement soit **silencieux**.

    Mesure: `-vf` en doublon sort en `rc=0`, `nb_frames=2`, `color_space=bt709`
    -- un master tague sans conversion, exactement le fichier a 40,33/255
    d'ecart que la story existe pour supprimer.
    """
    for option in ("-vf", "-filter:v", "-r", "-f", "-movflags", "-timecode"):
        smuggled = dataclasses.replace(
            codec_profiles.get_profile("prores_hq"), profile_id="t_vf",
            extra_args=("-profile:v", "3", option, "valeur"),
        )
        with pytest.raises(codec_profiles.EncodeConfigurationError, match="fabrique"):
            codec_profiles._reject_factory_owned_options(
                smuggled.ffmpeg_video_args(), "le profil t_vf"
            )
    # Cas negatif: aucun profil livre n'en porte.
    for profile in codec_profiles.PROFILES.values():
        codec_profiles._reject_factory_owned_options(profile.ffmpeg_video_args(),
                                                     profile.profile_id)


def test_the_factory_owned_guard_runs_on_every_built_command(monkeypatch) -> None:
    smuggled = dataclasses.replace(
        codec_profiles.get_profile("prores_hq"), profile_id="t_vf2",
        extra_args=("-profile:v", "3", "-vf", "scale=out_color_matrix=bt601"),
    )
    monkeypatch.setitem(codec_profiles.PROFILES, "t_vf2", smuggled)
    with pytest.raises(codec_profiles.EncodeConfigurationError, match="-vf"):
        codec_profiles.build_encode_command("t_vf2", "l.concat", 25, "o.mov")


@requires_ffmpeg_tools
def test_ffmpeg_really_keeps_the_second_filter_chain(tmp_path) -> None:
    """Cas negatif du precedent: sans la garde, le master sort **tague sans
    avoir ete converti**, et rien en aval ne le rattrape."""
    mire = make_mire(tmp_path / "mire.tiff")
    plain = write_tiff16(tmp_path / "plain.tiff",
                         np.full((MIRE_HEIGHT, MIRE_WIDTH, 3), 17, dtype=np.uint8))
    list_path = write_list(tmp_path / "vf.concat", [plain, mire])
    output = tmp_path / "vf.mov"
    result = subprocess.run(
        ["ffmpeg", "-y", "-r", "25", "-f", "concat", "-safe", "0", "-i", str(list_path),
         "-vf", "scale=out_color_matrix=bt709:out_range=tv",
         "-c:v", "prores_ks", "-pix_fmt", "yuv422p10le", "-profile:v", "3",
         "-vf", "null", *TAGS, "-r", "25", str(output)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr[-300:]
    assert ffprobe_field(output, "color_space")[0] == "bt709"
    deltas = patch_deltas(output)
    saturated = [name for name, _rgb in PATCHES if name not in ("blanc", "gris50")]
    assert max(deltas[name] for name in saturated) > 20.0, deltas


# --- les tags conteneur ---------------------------------------------------


@pytest.mark.parametrize(
    "tags, motif",
    [
        ({"": "valeur"}, "vide ou non textuelle"),
        ({"a=b": "valeur"}, "contenant '='"),
        ({" cle": "valeur"}, "mal formee"),
        ({"cle\n": "valeur"}, "mal formee"),
        ({42: "valeur"}, "vide ou non textuelle"),
        ({"lot_id": "A\nlot_id=FAUX"}, "saut de ligne"),
        ({"lot_id": ""}, "vide ou non textuel"),
    ],
)
def test_container_tag_keys_and_values_are_both_validated(tags, motif) -> None:
    """Majeur 7: la **valeur** etait controlee, la cle partait telle quelle.

    Mesures, toutes en `rc=0` et sans un mot: cle vide -> tag de cle vide; cle
    portant un `=` -> tag **scinde sur le premier `=`**, relu `{'a': 'b=valeur'}`;
    valeur a saut de ligne -> **second tag forge** pour tout lecteur de la sortie
    plate de ffprobe.
    """
    with pytest.raises(codec_profiles.EncodeConfigurationError, match=motif):
        codec_profiles.check_container_tags(tags)
    with pytest.raises(codec_profiles.EncodeConfigurationError):
        codec_profiles.build_encode_command("prores_hq", "l.concat", 25, "o.mov",
                                            container_tags=tags)


def test_a_well_formed_tag_is_accepted() -> None:
    assert codec_profiles.check_container_tags({"rush_id": "R42"}) == {"rush_id": "R42"}
    assert codec_profiles.check_container_tags(None) == {}


@requires_ffmpeg_tools
def test_a_tag_the_muxer_silently_drops_is_caught_after_encoding(tmp_path) -> None:
    """Majeur 7, seconde moitie: **aucun tag n'etait verifie apres encodage**.

    Une cle que le muxer se reserve est ignoree meme avec
    `-movflags use_metadata_tags`: mesure, `encoder=SENTINELLE` relu `{}`,
    `rc=0`, aucun signal. Si le drapeau disparaissait, personne ne le verrait.
    """
    frames = make_sequence(tmp_path, values=(63, 173))
    with pytest.raises(codec_profiles.EncodeVerificationError, match="Tags conteneur"):
        codec_profiles.run_encode("prores_hq", frames, 25, tmp_path / "drop.mov",
                                  container_tags={"encoder": "SENTINELLE"})
    assert not (tmp_path / "drop.mov").exists()
    # Cas negatif: une cle ordinaire survit, et la meme garde ne dit rien.
    outcome = codec_profiles.run_encode("prores_hq", frames, 25, tmp_path / "ok.mov",
                                        container_tags={"rush_id": "R42"})
    assert outcome.frame_count == 2


@requires_ffmpeg_tools
def test_the_movflag_is_what_keeps_the_tags(tmp_path) -> None:
    """Cas negatif de la garde: sans le drapeau, la cle disparait en silence."""
    frames = make_sequence(tmp_path, values=(64, 174))
    list_path = write_list(tmp_path / "tag.concat", frames)
    output = tmp_path / "sans_flag.mov"
    result = subprocess.run(
        ["ffmpeg", "-y", "-r", "25", "-f", "concat", "-safe", "0", "-i", str(list_path),
         "-c:v", "prores_ks", "-pix_fmt", "yuv422p10le", "-profile:v", "3",
         "-metadata", "rush_id=R42", "-r", "25", str(output)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr[-300:]
    from mixed_media_utility import video_metadata
    probe = video_metadata.probe_media(str(output))
    assert "rush_id" not in (probe["format"].get("tags") or {})
    profile = codec_profiles.get_profile("prores_hq")
    with pytest.raises(codec_profiles.EncodeVerificationError, match="Tags conteneur"):
        codec_profiles.verify_encoded_output(output, profile=profile, expected_frames=2,
                                             expected_tags={"rush_id": "R42"})


# --- le nettoyage, la destination, les binaires --------------------------


@requires_ffmpeg_tools
def test_a_failing_cleanup_never_replaces_the_typed_error(tmp_path, monkeypatch) -> None:
    """Majeur 8: le `finally` pouvait lever et **remplacer** l'erreur typee.

    `_unique_sibling` ajoute 26 octets a un nom deja long; `NAME_MAX` vaut 255.
    Mesure: a 233 caracteres, l'`unlink` sort en `OSError [Errno 36]`, qui
    ecrase l'`EncodeRunError` -- et tout appelant ecrit en `except EncodeError`
    la manque. Le defaut est general: EPERM, systeme de fichiers en lecture
    seule, n'importe quel `unlink` en echec.
    """
    frames = make_sequence(tmp_path, values=(66, 176))
    broken = dataclasses.replace(codec_profiles.get_profile("prores_hq"),
                                 profile_id="t_clean", extra_args=("-profile:v", "999"))
    monkeypatch.setitem(codec_profiles.PROFILES, "t_clean", broken)
    real_unlink = Path.unlink

    def hostile(self, *args, **kwargs):
        if self.name.startswith("."):
            raise OSError(36, "File name too long")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", hostile)
    with pytest.raises(codec_profiles.EncodeRunError):
        codec_profiles.run_encode("t_clean", frames, 25, tmp_path / "s" / "m.mov")


@requires_ffmpeg_tools
def test_a_destination_that_is_a_directory_stays_in_the_hierarchy(tmp_path) -> None:
    """Majeur 8: une destination repertoire produisait un `IsADirectoryError` nu."""
    frames = make_sequence(tmp_path, values=(67, 177))
    directory = tmp_path / "master.mov"
    directory.mkdir()
    with pytest.raises(codec_profiles.EncodeConfigurationError, match="repertoire") as error:
        codec_profiles.run_encode("prores_hq", frames, 25, directory)
    assert isinstance(error.value, codec_profiles.EncodeError)
    assert directory.is_dir()


def test_a_broken_encoder_listing_is_refused_and_never_memorised(tmp_path) -> None:
    """Majeur 9: `returncode` etait ignore **et** le resultat mis en cache.

    Un `ffmpeg -encoders` tue (OOM, SIGPIPE, quota) qui a eu le temps d'ecrire
    sa ligne de separation rendait un ensemble **partiel**, accepte puis
    memorise par `lru_cache` pour toute la vie du processus: le diagnostic
    "encodeur absent du binaire" etait alors faux **et definitif**.
    """
    marker = tmp_path / "deja_appele"
    script = tmp_path / "ffmpeg-flaky"
    script.write_text(
        "#!/bin/sh\n"
        f"if [ -f {marker} ]; then\n"
        "  printf 'Encoders:\\n ------\\n V..... prores_ks description\\n"
        " V..... libx264 description\\n'\n"
        "  exit 0\n"
        "fi\n"
        f"touch {marker}\n"
        "printf 'Encoders:\\n ------\\n V..... a64multi description\\n'\n"
        "exit 137\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    codec_profiles.available_encoders.cache_clear()
    try:
        with pytest.raises(codec_profiles.EncoderUnavailableError, match="137"):
            codec_profiles.available_encoders(str(script))
        # Le refus n'est pas memorise: le second appel remesure et reussit.
        encoders = codec_profiles.available_encoders(str(script))
        assert "prores_ks" in encoders and "libx264" in encoders
    finally:
        codec_profiles.available_encoders.cache_clear()


def test_a_missing_ffprobe_stays_inside_the_error_hierarchy(tmp_path) -> None:
    """Majeur 11: le cas symetrique (ffmpeg absent) etait type, celui-ci non.

    `probe_frame_size` est atteinte **avant** `video_metadata` dans
    `run_encode`, donc c'est elle, et non `FfprobeNotFoundError`, qui repondait
    -- par un `FileNotFoundError` nu.
    """
    with pytest.raises(codec_profiles.ProbeUnavailableError) as error:
        codec_profiles.probe_frame_size(tmp_path / "f.tiff",
                                        ffprobe_bin="ffprobe-qui-nexiste-pas")
    assert isinstance(error.value, codec_profiles.EncodeError)
    with pytest.raises(codec_profiles.EncodeError):
        codec_profiles.ensure_uniform_frame_shapes([tmp_path / "f.tiff"],
                                                   ffprobe_bin="ffprobe-qui-nexiste-pas")


def test_hidden_residues_are_sweepable_and_the_sweep_is_selective(tmp_path) -> None:
    """Majeur 12: les residus de `SIGTERM`/`SIGKILL` sont des fichiers **caches**
    portant l'extension du conteneur.

    Le point cher: `Path.glob('*.mov')` **les matche** alors que `glob.glob` ne
    les matche pas, et le depot emploie `Path.glob`/`iterdir` partout. Pour tout
    inventaire du depot, un temporaire perime est donc un master.
    """
    master = tmp_path / "master.mov"
    master.write_bytes(b"master")
    residue = codec_profiles._unique_sibling(master, ".mov")
    residue.write_bytes(b"master partiel")
    liste = codec_profiles._unique_sibling(tmp_path / "frames", ".mmuconcat")
    liste.write_text("file '/x'\n", encoding="utf-8")
    etranger = tmp_path / ".dotfile.mov"
    etranger.write_bytes(b"pas a nous")

    # Le constat qui rend le balayage necessaire.
    assert residue in set(tmp_path.glob("*.mov"))

    removed = codec_profiles.sweep_encode_residues(tmp_path, max_age_seconds=0)
    assert set(removed) == {residue, liste}
    assert master.is_file() and etranger.is_file()
    assert not residue.exists() and not liste.exists()
    # Cas negatif: un residu recent appartient peut-etre a un encodage en cours.
    fresh = codec_profiles._unique_sibling(master, ".mov")
    fresh.write_bytes(b"en cours")
    assert codec_profiles.sweep_encode_residues(tmp_path) == []
    assert fresh.is_file()
    assert codec_profiles.sweep_encode_residues(tmp_path / "absent") == []


# --- la geometrie: types, et l'invariant des regles ----------------------


@pytest.mark.parametrize("size", [(320.0, 180.0), (320.6, 180.4), (True, True),
                                  ("320", "180"), (320, None)])
def test_a_non_integral_geometry_is_refused_at_construction(size) -> None:
    """Majeur 10: `(320.0, 180.0)` **reussissait** et persistait
    `target_resolution = "320.0x180.0"` -- aucune confrontation aval ne matchera
    jamais `"320x180"`. Le module garde pourtant les types partout ailleurs."""
    profile = codec_profiles.get_profile("prores_hq")
    with pytest.raises(codec_profiles.EncodeConfigurationError, match="non entiere"):
        codec_profiles.check_target_dimensions(profile, *size)
    with pytest.raises(codec_profiles.EncodeConfigurationError):
        codec_profiles.build_encode_command("prores_hq", "l.concat", 25, "o.mov",
                                            target_size=size)


def test_a_malformed_target_size_is_named() -> None:
    with pytest.raises(codec_profiles.EncodeConfigurationError, match="mal formee"):
        codec_profiles.build_encode_command("prores_hq", "l.concat", 25, "o.mov",
                                            target_size=(320, 180, 24))
    with pytest.raises(codec_profiles.EncodeConfigurationError, match="mal formee"):
        codec_profiles.build_filter_chain(codec_profiles.get_profile("prores_hq"), 320)


def test_a_dimension_rule_cannot_contradict_its_own_floor() -> None:
    """La branche `value + 1` de `_nearest_dimension` etait du **code mort**
    prouve par balayage exhaustif: elle exigeait un plancher impair avec parite
    exigee, et aucune des quatre regles du catalogue ne combine les deux.

    Un mutant equivalent se retire, il ne se teste pas (`CLAUDE.md`). La branche
    est donc partie, et la condition qu'elle couvrait est devenue un invariant
    verifiable -- celui-ci.
    """
    with pytest.raises(ValueError, match="min_width=3 impair"):
        codec_profiles.DimensionRule(even_width=True, even_height=False,
                                     min_width=3, min_height=2)
    with pytest.raises(ValueError, match="min_height=121 impair"):
        codec_profiles.DimensionRule(even_width=False, even_height=True,
                                     min_width=2, min_height=121)
    for vcodec, rule in codec_profiles.ENCODER_DIMENSION_RULES.items():
        near_w, near_h = rule.nearest(rule.min_width + 1, rule.min_height + 1)
        assert near_w >= rule.min_width and near_h >= rule.min_height, vcodec


def test_a_string_passed_for_a_sequence_is_refused(tmp_path) -> None:
    """Une `str` est une `Sequence` de caracteres: `frames='frames/f01.tiff'`
    etait iteree caractere par caractere, et l'operateur lisait
    "Frame illisible: 'f'"."""
    with pytest.raises(codec_profiles.EncodeConfigurationError, match="Sequence d'entree"):
        codec_profiles.run_encode("prores_hq", "frames/f01.tiff", 25, tmp_path / "m.mov")
    with pytest.raises(codec_profiles.EncodeConfigurationError, match="Sequence d'entree"):
        codec_profiles.run_encode("prores_hq", tmp_path / "f01.tiff", 25, tmp_path / "m.mov")


# --- le cablage des gardes -----------------------------------------------


@requires_ffmpeg_tools
def test_every_guard_is_actually_called_by_run_encode(tmp_path, monkeypatch) -> None:
    """Les gardes etaient testees **en isolation**, jamais leur appel.

    Quatre mutants survivants disaient la meme chose: retirer
    `ensure_encoder_available` de `run_encode`, retirer `check_target_dimensions`
    de `build_encode_command`, retirer la confrontation de geometrie de
    `verify_encoded_output`, ecrire la liste `concat` dans le dossier des
    **frames** -- tout cela passait la suite entiere.
    """
    source = tmp_path / "src"
    source.mkdir()
    frames = make_sequence(source, values=(68, 178), size=(322, 182))
    destination = tmp_path / "sortie"
    master = destination / "m.mp4"

    calls: dict[str, list] = {"encoder": [], "dimensions": [], "verify": [],
                              "liste": [], "temp": []}
    real_encoder = codec_profiles.ensure_encoder_available
    real_dimensions = codec_profiles.check_target_dimensions
    real_verify = codec_profiles.verify_encoded_output
    real_list = codec_profiles.concat_list_file
    real_temp = codec_profiles._unique_sibling

    def spy_encoder(profile, ffmpeg_bin="ffmpeg"):
        calls["encoder"].append(profile.profile_id)
        return real_encoder(profile, ffmpeg_bin)

    def spy_dimensions(profile, width, height):
        calls["dimensions"].append((profile.profile_id, width, height))
        return real_dimensions(profile, width, height)

    def spy_verify(path, **kwargs):
        calls["verify"].append(kwargs)
        return real_verify(path, **kwargs)

    def spy_list(frame_paths, directory):
        calls["liste"].append(Path(directory))
        return real_list(frame_paths, directory)

    def spy_temp(target, suffix):
        calls["temp"].append(suffix)
        return real_temp(target, suffix)

    for name, spy in (("ensure_encoder_available", spy_encoder),
                      ("check_target_dimensions", spy_dimensions),
                      ("verify_encoded_output", spy_verify),
                      ("concat_list_file", spy_list),
                      ("_unique_sibling", spy_temp)):
        monkeypatch.setattr(codec_profiles, name, spy)

    codec_profiles.run_encode("h264_delivery", frames, 25, master, target_size=(320, 180))

    assert calls["encoder"] == ["h264_delivery"]
    # La geometrie confrontee est la geometrie **cible**, pas celle de la source.
    assert ("h264_delivery", 320, 180) in calls["dimensions"]
    assert calls["verify"] and calls["verify"][0]["expected_size"] == (320, 180)
    assert calls["verify"][0]["expected_frames"] == 2
    # La liste vit dans le dossier de destination, pas dans celui des frames.
    assert calls["liste"] == [destination]
    assert destination.resolve() != source.resolve()
    # Le temporaire porte l'extension du conteneur du profil, pas `.mov` en dur.
    assert ".mp4" in calls["temp"]


def test_the_dimension_guard_is_wired_into_build_encode_command(monkeypatch) -> None:
    with pytest.raises(codec_profiles.EncodeConfigurationError, match="refusee"):
        codec_profiles.build_encode_command("h264_delivery", "l.concat", 25, "o.mp4",
                                            target_size=(321, 181))

    def explode(profile, width, height):
        raise codec_profiles.EncodeConfigurationError("sentinelle de cablage")

    monkeypatch.setattr(codec_profiles, "check_target_dimensions", explode)
    with pytest.raises(codec_profiles.EncodeConfigurationError, match="sentinelle"):
        codec_profiles.build_encode_command("prores_hq", "l.concat", 25, "o.mov",
                                            target_size=(320, 180))


@requires_ffmpeg_tools
def test_the_geometry_confrontation_really_refuses_a_divergent_master(tmp_path) -> None:
    """Cas negatif du cablage: la confrontation de geometrie doit savoir refuser."""
    frames = make_sequence(tmp_path, values=(69, 179))
    master = tmp_path / "geo.mov"
    codec_profiles.run_encode("prores_hq", frames, 25, master)
    profile = codec_profiles.get_profile("prores_hq")
    with pytest.raises(codec_profiles.EncodeVerificationError, match="Geometrie"):
        codec_profiles.verify_encoded_output(master, profile=profile, expected_frames=2,
                                             expected_size=(1920, 1080))
    assert codec_profiles.verify_encoded_output(
        master, profile=profile, expected_frames=2, expected_size=(320, 180)
    )[:2] == (320, 180)


@requires_ffmpeg_tools
def test_the_encoder_guard_is_wired_into_run_encode(tmp_path, monkeypatch) -> None:
    frames = make_sequence(tmp_path, values=(71, 181))
    monkeypatch.setattr(codec_profiles, "available_encoders",
                        lambda ffmpeg_bin="ffmpeg": frozenset({"libx264"}))
    with pytest.raises(codec_profiles.EncoderUnavailableError, match="prores_ks"):
        codec_profiles.run_encode("prores_hq", frames, 25, tmp_path / "absent.mov")
    assert not (tmp_path / "absent.mov").exists()


# --- les valeurs qui coincidaient sur toutes les fixtures ----------------


@requires_ffmpeg_tools
def test_the_timecode_base_and_the_encode_rate_do_not_coincide(tmp_path) -> None:
    """L'unique test de `timecode_base` avait `fps=25` **et**
    `timecode_base_fps=25`: les deux valeurs coincidaient, donc trois mutants
    qui rendaient l'une pour l'autre survivaient.

    Ici les deux different et l'encodage **reussit**: `00:00:00:07` en base 25
    est legal, et ffmpeg le re-rend a 12,5 im/s en `00:00:00:07` (mesure).
    """
    frames = make_sequence(tmp_path, values=(72, 182))
    outcome = codec_profiles.run_encode(
        "prores_hq", frames, 12.5, tmp_path / "base.mov",
        timecode="00:00:00:07", timecode_base_fps=25,
    )
    assert outcome.frame_rate == "25/2"
    assert outcome.timecode_base == "25/1"
    assert outcome.frame_rate != outcome.timecode_base
    fields = codec_profiles.encode_manifest_fields(outcome)
    assert (fields["frame_rate"], fields["timecode_base"]) == ("25/2", "25/1")
    # Sans timecode, la base n'est pas inventee.
    plain = codec_profiles.run_encode("prores_hq", frames, 12.5, tmp_path / "sans.mov")
    assert plain.timecode is None and plain.timecode_base is None


def test_the_timecode_base_of_the_command_is_not_the_encode_rate() -> None:
    """Meme coincidence, cote `build_encode_command`."""
    command = codec_profiles.build_encode_command(
        "prores_hq", "l.concat", 12.5, "o.mov",
        timecode="00:00:00:14", timecode_base_fps=25,
    )
    assert command[command.index("-timecode") + 1] == "00:00:00:14"
    # A la cadence d'encodage seule, ce timecode serait refuse.
    with pytest.raises(ValueError):
        codec_profiles.build_encode_command("prores_hq", "l.concat", 12.5, "o.mov",
                                            timecode="00:00:00:14")


@requires_ffmpeg_tools
def test_the_container_of_the_profile_is_not_frozen_on_mov(tmp_path) -> None:
    """Seul `prores_hq` (mov) etait exerce de bout en bout: un `container` fige
    sur `"mov"` survivait."""
    frames = make_sequence(tmp_path, values=(73, 183))
    outcome = codec_profiles.run_encode("h264_delivery", frames, 25, tmp_path / "d.mp4")
    assert codec_profiles.encode_manifest_fields(outcome)["container"] == "mp4"
    assert codec_profiles.check_output_extension(
        codec_profiles.get_profile("h264_delivery"), "d.mp4") == "mp4"
    assert codec_profiles.check_output_extension(
        codec_profiles.get_profile("prores_hq"), "m.mov") == "mov"
    assert ffprobe_field(tmp_path / "d.mp4", "codec_name")[0] == "h264"


# --- ce que la campagne de cloture a trouve encore decouvert --------------


def fake_ffmpeg(tmp_path: Path, listing: str, returncode: int = 0,
                name: str = "ffmpeg-faux") -> str:
    """Rend un faux ffmpeg qui emet ``listing`` puis sort avec ``returncode``.

    Le vrai binaire ne permet pas de sonder les frontieres de l'analyse: son
    listing est fixe. Or c'est l'analyse qui decide qu'un encodeur est absent,
    et un ensemble partiel produit un diagnostic faux -- "compilation
    incomplete" -- sur un binaire complet.
    """
    script = tmp_path / name
    script.write_text(
        "#!/usr/bin/env python3\nimport sys\n"
        f"sys.stdout.write({listing!r})\nsys.exit({returncode})\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return str(script)


def test_the_encoder_listing_body_starts_after_the_dashed_line(tmp_path) -> None:
    """Le corps du listing commence apres une ligne **entierement** de tirets.

    Reconnaitre "une ligne qui commence par un tiret" suffit sur le ffmpeg de
    reference -- son en-tete n'en contient pas -- et casse des qu'un build en
    emet une (avertissement de depreciation, legende localisee): la legende
    passe alors pour le corps et `=` devient un nom d'encodeur. L'ensemble rendu
    est **partiel et faux**, et c'est lui qui declare un encodeur absent.
    """
    listing = (
        "Encoders:\n"
        " -threads is deprecated, use -filter_threads\n"
        " V..... = Video\n"
        " A..... = Audio\n"
        " ------\n"
        " V....D prores_ks Apple ProRes\n"
        " V....D libx264 H.264 / AVC\n"
    )
    codec_profiles.available_encoders.cache_clear()
    try:
        encoders = codec_profiles.available_encoders(fake_ffmpeg(tmp_path, listing))
        assert encoders == frozenset({"prores_ks", "libx264"}), sorted(encoders)

        # Sans ligne de separation, on ne sait pas ou commence le corps: la
        # tolerance rendrait un ensemble vide, donc un refus generalise
        # indiagnosticable. Le refus explicite est la seule reponse honnete.
        sans_separateur = fake_ffmpeg(
            tmp_path,
            "Encoders:\n V..... = Video\n V....D prores_ks Apple ProRes\n",
            name="ffmpeg-sans-separateur",
        )
        with pytest.raises(codec_profiles.EncoderUnavailableError, match="separation"):
            codec_profiles.available_encoders(sans_separateur)
    finally:
        codec_profiles.available_encoders.cache_clear()


def test_the_concat_list_carries_an_extension_proper_to_this_module(tmp_path) -> None:
    """Le fichier de liste vit dans le dossier de **destination**, aux cotes des
    masters, et il survit a un `SIGKILL` (mesure).

    Son extension est donc ce qui permet a un inventaire -- et au balayage de
    `sweep_encode_residues` -- de le reconnaitre pour ce qu'il est. Une
    extension banale le rendrait indistinguable d'un fichier de l'operateur, et
    un balayage qui l'emporterait detruirait des donnees.
    """
    with codec_profiles.concat_list_file([tmp_path / "a.tiff"], tmp_path) as list_path:
        assert list_path.is_file()
        suffix = list_path.suffix
        name = list_path.name
    assert suffix not in {"", ".txt", ".log", ".json", ".csv", ".lst", ".ini",
                          ".tiff", ".png", ".mov", ".mp4"}, suffix
    assert name.startswith("."), name  # cache: il n'encombre pas le dossier livre
    assert codec_profiles._TEMP_NAME_RE.search(name) is not None, name


def test_the_reservation_survives_a_stale_read_of_the_filesystem(
    tmp_path, monkeypatch
) -> None:
    """Ce qui distingue une reservation atomique d'un `exists()` suivi d'une
    creation, c'est **exactement** le cas ou l'etat lu est perime.

    Une course ne se teste pas par une course -- un test de concurrence est
    flaky par nature et peut passer sur une implementation fausse. Elle se teste
    en rendant la lecture perimee de facon deterministe: `exists()` rend `False`
    alors que le master de l'autre encodage est deja la. Une reservation qui
    consulte l'etat avant d'agir passe outre et rend la main a un appelant qui
    ecrasera le master; `O_CREAT | O_EXCL` echoue, parce que la creation **est**
    le test.
    """
    master = tmp_path / "perime.mov"
    master.write_bytes(b"le master de l'autre encodage")
    monkeypatch.setattr(Path, "exists", lambda self: False)
    with pytest.raises(codec_profiles.MasterAlreadyExistsError):
        codec_profiles._reserve_output_path(master)
    assert master.read_bytes() == b"le master de l'autre encodage"


# --- correction du 2026-08-10: la largeur d'ecriture du champ `ff` --------
#
# Defaut trouve par la revue de la story 6.1 et corrige ici. ffmpeg n'ecrit pas
# le champ `ff` du timecode sur une largeur fixe: il l'ecrit sur
# `len(str(ceil(cadence) - 1))` chiffres. `validate_timecode` n'acceptait que
# deux chiffres et `verify_encoded_output` confrontait des **chaines**: hors de
# la fenetre `11 <= ceil(cadence) <= 100`, un master parfaitement juste etait
# declare non conforme. Les cadences reelles de ce depot sont 1, 5, 10, 12,5 et
# 15 im/s -- trois sur cinq sont hors fenetre.

#: Cadences mesurees, avec la largeur d'ecriture du champ `ff` **relue d'un
#: encodage reel** (ffmpeg 6.1.1-3ubuntu5, ProRes en MOV, ffprobe). Les cinq
#: premieres sont les cadences reelles du projet, les trois dernieres bornent
#: la fenetre par le haut. Aucune ligne n'est inferee: chacune est rejouee par
#: `test_ffmpeg_writes_the_frame_field_at_the_width_of_its_own_ceiling`.
#:
#: Regle des fabriques du CLAUDE.md: la table n'est pas un remplissage uniforme
#: -- les trois largeurs 1, 2 et 3 y figurent, et la ligne de largeur 3, la
#: seule qu'aucune ecriture a deux chiffres ne couvre, est **en derniere
#: position**: un parcours qui s'arreterait a la premiere ligne, ou qui lirait
#: toujours la meme, ne la verrait pas.
TIMECODE_WIDTH_CASES: tuple[tuple[str, int, int], ...] = (
    #  cadence,   ceil, largeur du champ `ff` relue
    ("1/1", 1, 1),
    ("5/1", 5, 1),
    ("10/1", 10, 1),
    ("25/2", 13, 2),
    ("15/1", 15, 2),
    ("25/1", 25, 2),
    ("100/1", 100, 2),
    ("120/1", 120, 3),
)


def make_field_variants(reference: str = "01:02:03:04") -> list[tuple[str, str]]:
    """Rend des timecodes qui different de `reference` par **un seul champ**.

    Regle des fabriques du CLAUDE.md, appliquee au seul endroit ou elle mord
    ici: la reference porte quatre champs **tous differents** (`01:02:03:04` et
    non `00:00:00:00`), sinon une confrontation qui lirait `hh` a la place de
    `mm` -- ou qui oublierait purement et simplement un champ -- resterait
    invisible. Un champ est modifie a la fois, et le champ `ff`, celui dont
    cette correction relache l'ecriture, est **en derniere position**: une
    comparaison qui s'arreterait au premier champ divergent le manquerait.

    Rend une liste de `(nom du champ, timecode)`, dans l'ordre `hh`, `mm`, `ss`,
    `ff`, plus la variante drop-frame.
    """
    hours, minutes, seconds, frames = (int(part) for part in reference.split(":"))
    variants = [
        ("hh", f"{hours + 10:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"),
        ("mm", f"{hours:02d}:{minutes + 10:02d}:{seconds:02d}:{frames:02d}"),
        ("ss", f"{hours:02d}:{minutes:02d}:{seconds + 10:02d}:{frames:02d}"),
        ("ff", f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames + 10:02d}"),
        ("drop", f"{hours:02d}:{minutes:02d}:{seconds:02d};{frames:02d}"),
    ]
    assert len({value for _name, value in variants}) == len(variants) >= 2, variants
    assert reference not in {value for _name, value in variants}
    return variants


def encode_with_timecode(directory: Path, rate: str, timecode: str,
                         name: str = "tc.mov") -> Path:
    """Encode un master reel a `rate` en lui posant `-timecode`.

    Passe deliberement par ffmpeg **directement** et non par `run_encode`: ce
    helper sert a mesurer ce qu'ffmpeg ecrit, y compris dans les cas ou
    `run_encode` refuse. Deux frames distinguables, jamais un aplat uniforme.
    """
    frames = make_sequence(directory, values=(45, 135), size=(64, 64))
    list_path = write_list(directory / "seq.concat", frames)
    master = directory / name
    result = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-r", rate, "-f", "concat", "-safe", "0",
         "-i", str(list_path), "-c:v", "prores_ks", "-pix_fmt", "yuv422p10le",
         "-r", rate, "-timecode", timecode, str(master)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    return master


def probed_timecode(master: Path) -> str | None:
    from mixed_media_utility import video_metadata

    return video_metadata._find_timecode(video_metadata.probe_media(str(master)))


@requires_ffmpeg_tools
@pytest.mark.parametrize("rate,ceiling,width", TIMECODE_WIDTH_CASES)
def test_ffmpeg_writes_the_frame_field_at_the_width_of_its_own_ceiling(
    tmp_path, rate: str, ceiling: int, width: int
) -> None:
    """La mesure qui fonde toute cette correction, rejouee et non citee.

    Pour chaque cadence: `ff` est pose a sa valeur **maximale legale**
    (`ceil - 1`), ecrit sur deux chiffres comme le fait tout le depot, et le
    master relu porte le champ sur `len(str(ceil - 1))` chiffres. `hh`, `mm` et
    `ss` restent, eux, sur deux chiffres a toutes les cadences.
    """
    assert codec_profiles.timecode_frame_field_width(rate) == width
    demande = f"01:02:03:{ceiling - 1:02d}"
    relu = probed_timecode(encode_with_timecode(tmp_path, rate, demande))
    assert relu is not None
    champ = relu.split(":")[-1]
    assert len(champ) == width, (rate, demande, relu)
    assert int(champ) == ceiling - 1, (rate, demande, relu)
    assert relu.split(":")[:3] == ["01", "02", "03"], (rate, demande, relu)
    # Le point de la correction: meme image, deux ecritures.
    assert codec_profiles.timecodes_equivalent(relu, demande), (rate, demande, relu)

    # Meme mesure sur `ff = 0`, legal a **toutes** les cadences et ecrit sur
    # deux chiffres a la demande: c'est le montage qui isole la largeur de la
    # valeur. La confrontation par chaine ne tient alors que dans la fenetre
    # `11 <= ceil <= 100`, ou ffmpeg ecrit lui aussi sur deux chiffres.
    zero = "01:02:03:00"
    relu_zero = probed_timecode(encode_with_timecode(tmp_path, rate, zero, "zero.mov"))
    assert len(relu_zero.split(":")[-1]) == width, (rate, zero, relu_zero)
    assert codec_profiles.timecodes_equivalent(relu_zero, zero), (rate, relu_zero)
    assert (relu_zero == zero) is (width == 2), (rate, zero, relu_zero)


@requires_ffmpeg_tools
@pytest.mark.parametrize("rate,ceiling,_width", TIMECODE_WIDTH_CASES)
def test_the_frame_field_upper_bound_is_the_ceiling_and_ffmpeg_normalises_beyond(
    tmp_path, rate: str, ceiling: int, _width: int
) -> None:
    """La borne haute n'est pas relachee, et son refus n'est pas gratuit.

    `ff == ceil(cadence)` est refuse a la construction; mesure a l'appui, ffmpeg
    l'absorbe dans la seconde suivante sans un mot -- un master decale d'une
    seconde par rapport au manifest.
    """
    illegal = f"01:02:03:{ceiling:02d}"
    with pytest.raises(ValueError, match=f"frames {ceiling} >= {ceiling}"):
        codec_profiles.validate_timecode(illegal, rate)
    relu = probed_timecode(encode_with_timecode(tmp_path, rate, illegal))
    assert codec_profiles.timecode_position(relu).seconds == 4, (rate, illegal, relu)
    assert codec_profiles.timecode_position(relu).frames == 0, (rate, illegal, relu)
    assert not codec_profiles.timecodes_equivalent(relu, illegal)


@pytest.mark.parametrize("rate,ceiling,width", TIMECODE_WIDTH_CASES)
def test_validate_timecode_accepts_the_width_ffmpeg_writes(
    rate: str, ceiling: int, width: int
) -> None:
    """Les deux ecritures d'une meme image passent, a chacune des cadences."""
    value = ceiling - 1
    ffmpeg_form = f"01:02:03:{value:0{width}d}"
    smpte_form = f"01:02:03:{value:02d}"
    assert codec_profiles.validate_timecode(ffmpeg_form, rate) == ffmpeg_form
    assert codec_profiles.validate_timecode(smpte_form, rate) == smpte_form
    assert codec_profiles.timecodes_equivalent(ffmpeg_form, smpte_form)


def test_the_measured_cadence_table_is_not_a_uniform_filling() -> None:
    """Garde de la table elle-meme, regle des fabriques du `CLAUDE.md`.

    Une table dont toutes les lignes attendraient la meme largeur rendrait
    invisible aussi bien un calcul de largeur fige qu'un parcours qui lirait
    toujours la meme ligne. Les trois largeurs y sont, chaque cadence est
    unique, et la largeur 3 est en derniere position.
    """
    rates = [rate for rate, _ceiling, _width in TIMECODE_WIDTH_CASES]
    widths = [width for _rate, _ceiling, width in TIMECODE_WIDTH_CASES]
    assert len(set(rates)) == len(rates) >= 2
    assert set(widths) == {1, 2, 3}
    assert widths[-1] == 3 and widths[0] != 3
    for rate, ceiling, _width in TIMECODE_WIDTH_CASES:
        assert -(-Fraction(rate).numerator // Fraction(rate).denominator) == ceiling


def test_the_frame_field_width_is_read_off_the_ceiling_not_off_the_rate() -> None:
    """`ceil` et non la cadence: a 12,5 im/s la borne est 13, pas 12.

    Cas negatif indispensable, sans quoi une largeur calculee sur
    `int(cadence)` passerait: `len(str(12))` et `len(str(13))` valent tous deux
    2. Ce sont les cadences NTSC qui separent les deux formules -- `ceil` de
    29,97 vaut 30 -- et 120 im/s qui separe 2 de 3 chiffres.
    """
    assert codec_profiles.timecode_frame_field_width(29.97) == 2
    assert codec_profiles.timecode_frame_field_width("30000/1001") == 2
    assert codec_profiles.timecode_frame_field_width(119.88) == 3
    assert codec_profiles.timecode_frame_field_width(99) == 2
    assert codec_profiles.timecode_frame_field_width(100) == 2
    assert codec_profiles.timecode_frame_field_width(101) == 3
    # La borne basse: a 1 im/s, `ff` ne peut valoir que 0, sur un chiffre.
    assert codec_profiles.timecode_frame_field_width(1) == 1
    # La cadence est validee par `exact_frame_rate` et par lui seul: une
    # cadence nulle, negative ou booleenne est refusee avant tout calcul de
    # largeur. Sans ces cas, une largeur calculee sur un `Fraction(fps)` brut
    # rendrait 2 sur une cadence de -5 im/s au lieu de refuser.
    for absurde in (0, -5, -0.5, "0/1", "-24/1"):
        with pytest.raises(ValueError):
            codec_profiles.timecode_frame_field_width(absurde)
    with pytest.raises(TypeError):
        codec_profiles.timecode_frame_field_width(True)
    with pytest.raises(TypeError):
        codec_profiles.timecode_frame_field_width(None)


def test_a_frame_field_written_wider_than_plausible_is_refused() -> None:
    """La porte ne s'ouvre pas sur un remplissage arbitraire.

    La largeur admise va de 1 a `max(2, largeur d'ffmpeg)`: la forme canonique
    SMPTE et celle qu'ffmpeg ecrit reellement. Trois chiffres sont donc admis a
    120 im/s et refuses a 25 -- aucun producteur ne les ecrit a cette cadence,
    et les voir signale une chaine de formatage cassee.
    """
    # `ff = 0` est legal a **toutes** les cadences: seule la largeur est en
    # cause ici, jamais la valeur -- sans quoi la borne `ff < ceil` refuserait
    # la premiere et le test ne prouverait rien des cadences basses.
    assert codec_profiles.validate_timecode("00:00:00:000", 120) == "00:00:00:000"
    assert codec_profiles.validate_timecode("00:00:00:004", 120) == "00:00:00:004"
    for rate in ("1/1", "5/1", "10/1", "25/2", "15/1", "25/1", "100/1"):
        with pytest.raises(ValueError, match="ecrit sur 3 chiffres"):
            codec_profiles.validate_timecode("00:00:00:000", rate)
    with pytest.raises(ValueError, match="ecrit sur 4 chiffres"):
        codec_profiles.validate_timecode("00:00:00:0000", 120)
    # Et les champs `hh`, `mm`, `ss` gardent leurs deux chiffres exactement.
    for invalide in ("1:02:03:04", "01:2:03:04", "01:02:3:04",
                     "001:02:03:04", "01:002:03:04", "01:02:003:04"):
        with pytest.raises(ValueError, match="Timecode invalide"):
            codec_profiles.validate_timecode(invalide, 25)


def test_validate_timecode_still_refuses_everything_it_refused() -> None:
    """Le temoin de non-regression de la porte, aux cinq cadences reelles.

    Aucune des formes ci-dessous n'est devenue acceptable par la relache de la
    largeur d'ecriture.
    """
    for rate in ("1/1", "5/1", "10/1", "25/2", "15/1"):
        limit = -(-Fraction(rate).numerator // Fraction(rate).denominator)
        with pytest.raises(ValueError, match="Timecode invalide"):
            codec_profiles.validate_timecode("abc", rate)
        with pytest.raises(ValueError, match="Timecode invalide"):
            codec_profiles.validate_timecode("", rate)
        with pytest.raises(ValueError, match="Timecode invalide"):
            codec_profiles.validate_timecode("00:00:00:", rate)
        with pytest.raises(ValueError, match="Timecode invalide"):
            codec_profiles.validate_timecode("00:00:00", rate)
        with pytest.raises(ValueError, match="hors bornes"):
            codec_profiles.validate_timecode(f"24:00:00:{limit - 1:02d}", rate)
        with pytest.raises(ValueError, match="hors bornes"):
            codec_profiles.validate_timecode(f"00:60:00:{limit - 1:02d}", rate)
        with pytest.raises(ValueError, match="hors bornes"):
            codec_profiles.validate_timecode(f"00:00:60:{limit - 1:02d}", rate)
        with pytest.raises(ValueError, match="frames"):
            codec_profiles.validate_timecode(f"00:00:00:{limit:02d}", rate)
        with pytest.raises(ValueError, match="Drop-frame"):
            codec_profiles.validate_timecode(f"00:00:00;{limit - 1:02d}", rate)
        # Le refus de type est **le sien**, avec sa valeur nommee, et non le
        # `TypeError` que `re.match` leverait de toute facon: sans cette
        # assertion, retirer la garde de type ne se verrait pas.
        for pas_une_chaine in (None, 3600, b"00:00:00:04", 25.0, ["00:00:00:04"]):
            with pytest.raises(TypeError, match="doit etre une chaine"):
                codec_profiles.validate_timecode(pas_une_chaine, rate)
    # Le drop-frame reste accepte la ou il a un sens, et lui seul. C'est aussi
    # ce qui atteste que la cadence passe par `exact_frame_rate`: sur un
    # `Fraction(29.97)` brut, la cadence ne serait pas dans `NTSC_RATES` et ce
    # timecode parfaitement legal serait refuse.
    assert codec_profiles.validate_timecode("00:00:00;04", 29.97) == "00:00:00;04"
    # La cadence est refusee par `exact_frame_rate`, avec **sa** famille
    # d'exceptions, avant que la moindre borne ne soit calculee. Sans ces cas,
    # une cadence booleenne serait silencieusement lue comme 1 im/s et une
    # cadence negative rendrait une borne absurde au lieu de lever -- c'est le
    # defaut `T11` du calcul de largeur, transpose a la porte elle-meme.
    for absurde in (0, -5, -0.5, "0/1", "-24/1"):
        with pytest.raises(ValueError):
            codec_profiles.validate_timecode("00:00:00:00", absurde)
    for mal_typee in (True, None, [25]):
        with pytest.raises(TypeError):
            codec_profiles.validate_timecode("00:00:00:00", mal_typee)


def test_the_refusals_stay_inside_the_documented_exception_family() -> None:
    """`ValueError` et `TypeError`, jamais autre chose sur une entree de forme.

    Le depot a deja paye un `ZeroDivisionError` hors famille sur
    `exact_frame_rate("24/0")`; la relache de la largeur ne doit pas en ouvrir
    un second par le champ `ff`. Un champ de mille chiffres est refuse par la
    grammaire, pas par `int()`.
    """
    for value in ("00:00:00:" + "0" * 1000, "00:00:00:" + "9" * 1000,
                  "00:00:00:-1", "00:00:00:+4", "00:00:00: 4", "00:00:00:4 ",
                  "00:00:00:4.0", "00:00:00:04\n"):
        with pytest.raises(ValueError, match="Timecode invalide"):
            codec_profiles.validate_timecode(value, 25)
        assert codec_profiles.timecode_position(value) is None, value


def test_only_the_frame_field_width_is_absorbed_by_the_comparison() -> None:
    """Un vrai desaccord reste un desaccord, champ par champ.

    C'est la contre-epreuve de la correction: si la confrontation etait devenue
    tolerante plutot qu'independante de la largeur, ces cinq variantes -- une
    par champ, `ff` en derniere position -- passeraient.
    """
    reference = "01:02:03:04"
    variants = make_field_variants(reference)
    assert [name for name, _ in variants] == ["hh", "mm", "ss", "ff", "drop"]
    for name, variant in variants:
        assert not codec_profiles.timecodes_equivalent(variant, reference), name
        assert not codec_profiles.timecodes_equivalent(reference, variant), name
    # Seule la largeur d'ecriture est absorbee, et sur le champ `ff` seul: les
    # trois ecritures de la meme image sont equivalentes a la reference et
    # entre elles.
    ecritures = [f"01:02:03:{4:0{width}d}" for width in (1, 2, 3)]
    assert ecritures == ["01:02:03:4", "01:02:03:04", "01:02:03:004"]
    for ecriture in ecritures:
        assert codec_profiles.timecodes_equivalent(ecriture, reference), ecriture
        for autre in ecritures:
            assert codec_profiles.timecodes_equivalent(ecriture, autre)


def test_the_position_is_the_five_fields_and_nothing_else() -> None:
    """`TimecodePosition` porte l'image designee, pas l'ecriture.

    Deux ecritures de la meme image rendent une position **egale**; deux images
    differentes rendent des positions differentes, y compris quand elles ne
    different que par le drapeau drop-frame.
    """
    position = codec_profiles.timecode_position("01:02:03:04")
    assert (position.hours, position.minutes, position.seconds) == (1, 2, 3)
    assert (position.frames, position.drop_frame) == (4, False)
    assert codec_profiles.timecode_position("01:02:03:4") == position
    assert codec_profiles.timecode_position("01:02:03:004") == position
    assert codec_profiles.timecode_position("01:02:03;04") != position
    assert codec_profiles.timecode_position("01:02:03;04").drop_frame is True
    # Un champ lu a la place d'un autre se voit: les quatre valeurs different.
    assert len({position.hours, position.minutes, position.seconds,
                position.frames}) == 4


def test_an_unreadable_timecode_is_equivalent_to_nothing() -> None:
    """Y compris a lui-meme: "aucun des deux n'est lisible" n'est pas "la meme
    image". Un master sans `tmcd` doit etre refuse, pas assimile a une absence
    attendue."""
    for illisible in (None, "", "N/A", 4, b"00:00:00:04", "00:00:00", object()):
        assert codec_profiles.timecode_position(illisible) is None, illisible
        assert not codec_profiles.timecodes_equivalent(illisible, "00:00:00:04")
        assert not codec_profiles.timecodes_equivalent("00:00:00:04", illisible)
        assert not codec_profiles.timecodes_equivalent(illisible, illisible)


@requires_ffmpeg_tools
@pytest.mark.parametrize("rate,ceiling,width", TIMECODE_WIDTH_CASES)
def test_a_master_at_any_of_these_cadences_is_no_longer_declared_non_conforming(
    tmp_path, rate: str, ceiling: int, width: int
) -> None:
    """Le defaut corrige, de bout en bout par `run_encode`.

    Avant la correction, ces encodages sortaient en `EncodeVerificationError`
    hors de la fenetre `11 <= ceil <= 100` -- soit a 1, 5, 10 et 120 im/s, dont
    trois des cinq cadences reelles du projet. Le master etait pourtant juste.
    """
    frames = make_sequence(tmp_path, values=(55, 145), size=(64, 64))
    demande = f"01:02:03:{ceiling - 1:02d}"
    master = tmp_path / f"master_{rate.replace('/', '-')}.mov"
    outcome = codec_profiles.run_encode(
        "prores_hq", frames, rate, master, timecode=demande,
    )
    assert outcome.timecode == demande
    assert master.is_file()
    relu = probed_timecode(master)
    assert len(relu.split(":")[-1]) == width, (rate, relu)
    assert codec_profiles.timecodes_equivalent(relu, demande), (rate, relu)


@requires_ffmpeg_tools
def test_a_real_disagreement_is_still_refused_at_a_width_one_cadence(tmp_path) -> None:
    """La contre-epreuve du test precedent, a la cadence ou la largeur differe.

    A 5 im/s le master relu porte `00:00:00:4` la ou `00:00:00:04` a ete
    demande: c'est la meme image. Un timecode **voisin d'une seule frame**, lui,
    reste refuse -- la tolerance porte sur l'ecriture, pas sur la valeur.
    """
    frames = make_sequence(tmp_path, values=(65, 155), size=(64, 64))
    master = tmp_path / "cinq.mov"
    codec_profiles.run_encode("prores_hq", frames, "5/1", master, timecode="00:00:00:04")
    assert probed_timecode(master) == "00:00:00:4"
    profile = codec_profiles.get_profile("prores_hq")
    # La meme image, une autre ecriture: accepte.
    codec_profiles.verify_encoded_output(
        master, profile=profile, expected_frames=2, expected_timecode="00:00:00:04",
    )
    codec_profiles.verify_encoded_output(
        master, profile=profile, expected_frames=2, expected_timecode="00:00:00:4",
    )
    # Une image voisine, et chacun des autres champs: refuse.
    for voisin in ("00:00:00:03", "00:00:00:3", "00:00:01:04", "00:01:00:04",
                   "01:00:00:04", "00:00:00;04"):
        with pytest.raises(codec_profiles.EncodeVerificationError, match="Timecode"):
            codec_profiles.verify_encoded_output(
                master, profile=profile, expected_frames=2,
                expected_timecode=voisin,
            )


@requires_ffmpeg_tools
@pytest.mark.parametrize("rate,ceiling,width", TIMECODE_WIDTH_CASES)
def test_a_real_disagreement_is_still_refused_at_every_cadence(
    tmp_path, rate: str, ceiling: int, width: int
) -> None:
    """Le risque du correctif, mesure aux **huit** cadences et non a une seule.

    Le test precedent montre qu'un master juste n'est plus refuse; celui-ci
    montre que la porte est devenue **agnostique a la largeur** et non
    **tolerante**. La distinction ne se mesure qu'en confrontant, a chaque
    cadence, un desaccord reel: une confrontation relachee -- comparaison
    tronquee aux `hh:mm:ss`, `startswith`, egalite sur un seul champ -- passerait
    encore la contre-epreuve a 5 im/s, qui ne l'exerce que sur le champ `ff`.

    Le master est encode par `run_encode`, donc par le chemin de production, et
    le timecode est **relu a ffprobe**: aucune ligne de ce test n'est inferee de
    la table, chacune la rejoue.
    """
    frames = make_sequence(tmp_path, values=(85, 175), size=(64, 64))
    master = tmp_path / f"desaccord_{rate.replace('/', '-')}.mov"
    demande = f"01:02:03:{ceiling - 1:02d}"
    codec_profiles.run_encode("prores_hq", frames, rate, master, timecode=demande)
    profile = codec_profiles.get_profile("prores_hq")
    relu = probed_timecode(master)
    # La largeur relue est bien celle de la cadence, et la valeur est intacte:
    # sans cette ligne, le reste du test tiendrait aussi sur un master muet.
    assert relu == f"01:02:03:{ceiling - 1:0{width}d}", (rate, relu)

    # La meme image, dans les deux ecritures qui circulent reellement dans la
    # chaine (celle demandee et celle qu'ffmpeg ecrit): acceptee.
    for ecriture in (demande, relu):
        codec_profiles.verify_encoded_output(
            master, profile=profile, expected_frames=2, expected_timecode=ecriture,
        )

    # Un desaccord sur **chacun** des cinq champs -- `ff` en avant-derniere
    # position, le drapeau drop-frame en derniere -- est refuse a toutes les
    # cadences. Aucune de ces variantes n'est une autre ecriture de la meme
    # image: toutes designent une autre image, ou une autre timeline.
    variantes = make_field_variants(demande)
    assert [nom for nom, _valeur in variantes] == ["hh", "mm", "ss", "ff", "drop"]
    for nom, variante in variantes:
        assert not codec_profiles.timecodes_equivalent(variante, relu), (rate, nom)
        with pytest.raises(codec_profiles.EncodeVerificationError, match="Timecode"):
            codec_profiles.verify_encoded_output(
                master, profile=profile, expected_frames=2,
                expected_timecode=variante,
            )

    # Le desaccord le plus fin qui existe: l'image **voisine d'une seule frame**,
    # ecrite aussi bien sur deux chiffres que sur la largeur d'ffmpeg -- c'est le
    # montage qui separe "absorber la largeur" de "absorber la valeur". A 1 im/s
    # le champ ne peut que monter, `ff = 0` etant deja son minimum.
    voisin = ceiling - 2 if ceiling >= 2 else 1
    for gabarit in {2, width}:
        proche = f"01:02:03:{voisin:0{gabarit}d}"
        assert not codec_profiles.timecodes_equivalent(proche, relu), (rate, proche)
        with pytest.raises(codec_profiles.EncodeVerificationError, match="Timecode"):
            codec_profiles.verify_encoded_output(
                master, profile=profile, expected_frames=2, expected_timecode=proche,
            )


@requires_ffmpeg_tools
def test_a_master_without_any_timecode_is_refused_and_not_read_as_a_match(
    tmp_path,
) -> None:
    """Le mode de panne que `timecodes_equivalent(None, None) is False` ferme.

    Un master encode sans `-timecode` ne porte aucun `tmcd`: confronte a un
    timecode attendu, il doit etre refuse.
    """
    frames = make_sequence(tmp_path, values=(75, 165), size=(64, 64))
    master = tmp_path / "sans_tc.mov"
    codec_profiles.run_encode("prores_hq", frames, "5/1", master)
    assert probed_timecode(master) is None
    with pytest.raises(codec_profiles.EncodeVerificationError, match="Timecode obtenu"):
        codec_profiles.verify_encoded_output(
            master, profile=codec_profiles.get_profile("prores_hq"),
            expected_frames=2, expected_timecode="00:00:00:00",
        )
