"""FFmpeg encode profile catalog for the `encode` step (story 6.2).

Centralizes the codec/profile/container choices in one place instead of the
CLI, so `cli.py`'s `encode` skeleton (and the future real implementation) can
select a profile by id and build both the FFmpeg command and the manifest
representation from the same source of truth.

Per ARCHITECTURE.md / ARCHITECTURE_DETAILED.md section 11-12:
- ProRes MOV is the default mezzanine master.
- DNxHR MOV and delivery derivatives (H.264/H.265) are secondary, explicit,
  never implicit.
- The manifest must be able to express codec, profile, container, target
  colorspace and encode constraints (this module's ``manifest_fields``).
"""

from __future__ import annotations

import contextlib
import functools
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

from . import progression
from .numeric_guards import is_strict_int, is_strict_number

_JOURNAL = logging.getLogger(__name__)

#: La cible de `-progress` quand le canal est ouvert. `pipe:1` est la sortie
#: **standard du sous-processus**, jamais celle du notre : `run_encode` la lit
#: par `Popen(stdout=PIPE)` et rien n'atteint le terminal.
#:
#: Elle vaut la sortie standard et non un fichier parce que le fichier
#: imposerait une scrutation a intervalle, la ou le tube donne les jalons a la
#: cadence de ffmpeg lui-meme -- et `stderr` allant, lui, dans un fichier, le
#: tube de sortie standard ne peut pas bloquer.
PROGRESS_TARGET_STDOUT = "pipe:1"

#: La SEULE cle du flux `-progress` que ce module lit, et la plus stable du
#: format. Tout le reste -- `out_time`, `speed`, `bitrate` -- est ignore.
PROGRESS_FRAME_KEY = "frame"


@dataclass(frozen=True)
class EncodeProfile:
    """A named, concrete FFmpeg encode profile."""

    profile_id: str
    category: str  # "primary" (mezzanine master) or "secondary" (delivery/alt)
    container: str  # file extension, e.g. "mov", "mp4"
    vcodec: str  # FFmpeg -c:v value (the *encoder*: prores_ks, libx264, ...)
    probe_codec_name: str  # what ffprobe reports back (prores, h264, ...)
    pix_fmt: str
    colorspace: str  # target colorspace tag, e.g. "bt709"
    extra_args: tuple[str, ...] = field(default_factory=tuple)
    notes: str = ""

    def ffmpeg_video_args(self) -> list[str]:
        """Return the FFmpeg video-encode arguments (without -i/input/-o/output).

        All three color tags (-colorspace, -color_primaries, -color_trc) are
        set explicitly and identically: story 6.2/6.3 experiments showed that
        prores_ks only reliably tags `color_space` in the output container
        when all three are set together — `-colorspace` alone is not enough
        for ProRes, even though it is sufficient for libx264/libx265/dnxhd.
        Setting all three everywhere keeps the profiles consistent and
        externally verifiable regardless of codec quirks.
        """
        args = [
            "-c:v", self.vcodec,
            "-pix_fmt", self.pix_fmt,
            "-colorspace", self.colorspace,
            "-color_primaries", self.colorspace,
            "-color_trc", self.colorspace,
        ]
        args.extend(self.extra_args)
        return args

    def manifest_fields(self) -> dict:
        """Return the manifest-ready representation of this profile."""
        return {
            "codec": self.vcodec,
            "probe_codec_name": self.probe_codec_name,
            "profile": self.profile_id,
            "container": self.container,
            "target_colorspace": self.colorspace,
            "category": self.category,
        }


# ProRes profile numbers for FFmpeg's prores_ks encoder:
# 0=proxy, 1=LT, 2=standard (422), 3=HQ, 4=4444, 5=4444XQ.
PROFILES: dict[str, EncodeProfile] = {
    "prores_hq": EncodeProfile(
        profile_id="prores_hq",
        category="primary",
        container="mov",
        vcodec="prores_ks",
        probe_codec_name="prores",
        pix_fmt="yuv422p10le",
        colorspace="bt709",
        extra_args=("-profile:v", "3", "-vendor", "apl0"),
        notes="Master mezzanine par defaut (ProRes 422 HQ). Choix retenu pour equilibrer qualite/poids.",
    ),
    "prores_422": EncodeProfile(
        profile_id="prores_422",
        category="secondary",
        container="mov",
        vcodec="prores_ks",
        probe_codec_name="prores",
        pix_fmt="yuv422p10le",
        colorspace="bt709",
        extra_args=("-profile:v", "2", "-vendor", "apl0"),
        notes="Variante ProRes 422 standard, plus legere que HQ, usage secondaire explicite.",
    ),
    "prores_lt": EncodeProfile(
        profile_id="prores_lt",
        category="secondary",
        container="mov",
        vcodec="prores_ks",
        probe_codec_name="prores",
        pix_fmt="yuv422p10le",
        colorspace="bt709",
        extra_args=("-profile:v", "1", "-vendor", "apl0"),
        notes="Variante ProRes LT, plus legere encore, reservee aux previews/echanges rapides.",
    ),
    "dnxhr_hq": EncodeProfile(
        profile_id="dnxhr_hq",
        category="secondary",
        container="mov",
        vcodec="dnxhd",
        probe_codec_name="dnxhd",
        pix_fmt="yuv422p",
        colorspace="bt709",
        extra_args=("-profile:v", "dnxhr_hq",),
        notes=(
            "Alternative DNxHR HQ pour cibles post-production non-Apple. "
            "8 bits/422 (yuv422p): confirme empiriquement (story 6.2) que le "
            "profil HQ standard de dnxhd/ffmpeg refuse yuv422p10le (reserve a "
            "HQX/444); ne pas changer ce pix_fmt sans re-tester."
        ),
    ),
    "dnxhr_hqx": EncodeProfile(
        profile_id="dnxhr_hqx",
        category="secondary",
        container="mov",
        vcodec="dnxhd",
        probe_codec_name="dnxhd",
        pix_fmt="yuv422p10le",
        colorspace="bt709",
        extra_args=("-profile:v", "dnxhr_hqx",),
        notes=(
            "Variante 10 bits/422 de DNxHR (profil Avid HQX), pour les cibles "
            "post-production qui exigent explicitement du 10 bits sans passer "
            "par ProRes. A utiliser plutot que de forcer yuv422p10le sur HQ."
        ),
    ),
    "h264_delivery": EncodeProfile(
        profile_id="h264_delivery",
        category="secondary",
        container="mp4",
        vcodec="libx264",
        probe_codec_name="h264",
        pix_fmt="yuv420p",
        colorspace="bt709",
        extra_args=("-crf", "18", "-preset", "slow"),
        notes="Derive de diffusion H.264, jamais utilise comme master.",
    ),
    "hevc_delivery": EncodeProfile(
        profile_id="hevc_delivery",
        category="secondary",
        container="mp4",
        vcodec="libx265",
        probe_codec_name="hevc",
        pix_fmt="yuv420p10le",
        colorspace="bt709",
        extra_args=("-crf", "20", "-preset", "slow"),
        notes="Derive de diffusion H.265, jamais utilise comme master.",
    ),
}

DEFAULT_PROFILE_ID = "prores_hq"


def get_profile(profile_id: str) -> EncodeProfile:
    """Return the ``EncodeProfile`` for ``profile_id``, raising ``KeyError``
    with the list of valid ids if unknown."""
    try:
        return PROFILES[profile_id]
    except KeyError as exc:
        raise KeyError(
            f"Profil d'encode inconnu: {profile_id!r}. Profils valides: {sorted(PROFILES)}"
        ) from exc


# Broadcast rates whose exact value is a ratio, keyed by the rounded decimal a
# manifest realistically stores. `str(23.976)` hands ffmpeg a decimal it turns
# into an arbitrary rational (2997/125 instead of 24000/1001), producing a
# master with a non-standard time base that drifts in edit and breaks timecode
# conformance. Only the full-precision float round-trips; the rounded one does
# not, and the rounded one is the nominal case.
_EXACT_RATES = {
    Fraction(24000, 1001): (23.976, 23.98),
    Fraction(30000, 1001): (29.97,),
    Fraction(60000, 1001): (59.94,),
    Fraction(48000, 1001): (47.952,),
    Fraction(120000, 1001): (119.88,),
}
NTSC_RATES = tuple(_EXACT_RATES)

# Le champ `ff` n'est **pas** de largeur fixe: ffmpeg l'ecrit sur
# `len(str(ceil(fps) - 1))` chiffres (voir `timecode_frame_field_width`). La
# borne haute de 9 chiffres n'a aucune valeur semantique -- c'est la borne
# semantique `ff < ceil(fps)` qui refuse, dans `validate_timecode`, avec un
# message qui nomme la cadence. Elle est la pour qu'une chaine absurde ne parte
# pas dans `int()`, dont CPython refuse les litteraux de plus de 4300 chiffres
# par une `ValueError` hors de la famille documentee ici.
#
# `\Z` et non `$`: en Python, `$` accepte un saut de ligne **final**, si bien
# que `"00:00:00:04\n"` passait la grammaire et repartait tel quel dans l'argv
# d'ffmpeg -- mesure du 2026-08-10, trou preexistant trouve en ecrivant le
# temoin de non-regression de cette porte. `\Z` ne colle qu'a la fin reelle.
_TIMECODE_RE = re.compile(r"^(\d{2}):(\d{2}):(\d{2})([:;])(\d{1,9})\Z")


def exact_frame_rate(fps: float | int | str | Fraction) -> str:
    """Return ``fps`` as an exact ``num/den`` string for FFmpeg.

    Accepts a rational string (``"24000/1001"``) verbatim, and snaps the
    rounded NTSC decimals a manifest stores (23.976, 29.97, ...) back onto
    their exact ratio instead of letting FFmpeg guess.
    """
    if isinstance(fps, str):
        value = Fraction(fps)
    elif isinstance(fps, Fraction):
        value = fps
    elif not is_strict_number(fps):
        raise TypeError(f"fps doit etre un nombre, une Fraction ou 'num/den': {fps!r}")
    else:
        # NaN raises ValueError and inf raises OverflowError out of Fraction,
        # the latter escaping a caller that catches ValueError as documented.
        # A corrupt manifest fps is exactly how one gets here.
        if fps != fps or fps in (float("inf"), float("-inf")):
            raise ValueError(f"fps non fini: {fps!r}")
        value = Fraction(fps).limit_denominator(1000000)
        for exact, rounded in _EXACT_RATES.items():
            if float(fps) in rounded or abs(float(fps) - float(exact)) < 1e-6:
                value = exact
                break
    if value <= 0:
        raise ValueError(f"fps doit etre strictement positif: {fps!r}")
    return f"{value.numerator}/{value.denominator}"


@dataclass(frozen=True)
class TimecodePosition:
    """L'image que **designe** un timecode SMPTE, largeur d'ecriture exclue.

    Deux timecodes designent la meme image si et seulement si leurs cinq champs
    coincident. La largeur sur laquelle ``ff`` est ecrit n'en fait
    volontairement pas partie: c'est tout l'objet de la correction du
    2026-08-10 (voir ``timecode_frame_field_width``). ``drop_frame`` en fait
    partie en revanche -- ``00:00:00;04`` et ``00:00:00:04`` sont deux
    timelines differentes, pas deux ecritures de la meme.
    """

    hours: int
    minutes: int
    seconds: int
    frames: int
    drop_frame: bool


#: Une journee de timecode, en secondes. `hh:mm:ss:ff` ne porte pas de jour :
#: au-dela de 23 h le compteur reboucle, et `validate_timecode` refuse tout ce
#: qui deborde. Un rush de vingt minutes demarrant a `23:50:00:00` en depend.
_SECONDS_PER_JOUR = 24 * 3600


def _frame_limit(rate: Fraction) -> int:
    """Borne stricte du champ ``ff`` a ``rate``: ``ceil(rate)``.

    C'est la convention d'ffmpeg, mesuree: a 12,5 im/s le champ compte jusqu'a
    12, et ``00:00:00:13`` est absorbe dans la seconde suivante.
    """
    return -(-rate.numerator // rate.denominator)  # ceil, for 23.976 -> 24


def timecode_frame_field_width(fps: float | int | str | Fraction) -> int:
    """Nombre de chiffres sur lequel ffmpeg **ecrit** le champ ``ff`` a ``fps``.

    Mesure du 2026-08-10 (ffmpeg 6.1.1-3ubuntu5, ProRes en MOV, ``tmcd`` relu a
    ffprobe), et non une inference: ffmpeg n'ecrit pas ``ff`` sur une largeur
    fixe, il l'ecrit sur ``len(str(ceil(fps) - 1))`` chiffres -- la largeur de
    la plus grande valeur que le champ puisse prendre a cette cadence.

    Pour un meme ``-timecode 00:00:00:04`` demande:

    | cadence | ceil | ``tmcd`` relu   |
    | ---     | ---  | ---             |
    | 5       | 5    | ``00:00:00:4``  |
    | 10      | 10   | ``00:00:00:4``  |
    | 12,5    | 13   | ``00:00:00:04`` |
    | 15      | 15   | ``00:00:00:04`` |
    | 25      | 25   | ``00:00:00:04`` |
    | 100     | 100  | ``00:00:00:04`` |
    | 120     | 120  | ``00:00:00:004``|

    Les champs ``hh``, ``mm`` et ``ss`` restent, eux, sur deux chiffres a toutes
    ces cadences. Hors de la fenetre ``11 <= ceil(fps) <= 100``, le timecode
    relu s'ecrit donc autrement que celui demande **sans que rien ne soit
    faux**, et les cadences reelles de ce depot (1, 5, 10, 12,5 et 15 im/s) sont
    majoritairement hors de cette fenetre.
    """
    return len(str(_frame_limit(Fraction(exact_frame_rate(fps))) - 1))


def timecode_position(value: object) -> TimecodePosition | None:
    """Decompose ``value`` en l'image qu'il designe, ou rend ``None``.

    Rend ``None`` -- jamais une exception -- sur tout ce qui n'est pas un
    timecode: ``None``, un entier, ``"N/A"``, une chaine vide. C'est la forme
    dont a besoin la relecture d'un fichier produit, ou l'absence de timecode
    est un resultat possible et non une panne du lecteur.

    La largeur du champ ``ff`` est **absorbee** ici: ``00:00:00:4``,
    ``00:00:00:04`` et ``00:00:00:004`` rendent la meme position. Aucune
    validation de cadence n'est faite -- ``timecode_position`` ne sait pas a
    quelle cadence le timecode se lit, c'est ``validate_timecode`` qui le sait.
    """
    if not isinstance(value, str):
        return None
    match = _TIMECODE_RE.match(value)
    if match is None:
        return None
    return _position_from_match(match)


def _position_from_match(match: re.Match) -> TimecodePosition:
    """Construit la position depuis un `match` de ``_TIMECODE_RE``.

    Point de decodage **unique**: `validate_timecode` a besoin du `match` pour
    mesurer la largeur d'ecriture, `timecode_position` n'a besoin que de la
    position. Les faire decoder deux fois la meme chaine ouvrirait deux
    conventions divergentes pour le meme format.
    """
    hours, minutes, seconds, separator, frames = match.groups()
    return TimecodePosition(
        hours=int(hours),
        minutes=int(minutes),
        seconds=int(seconds),
        frames=int(frames),
        drop_frame=separator == ";",
    )


def timecodes_equivalent(first: object, second: object) -> bool:
    """Dit si ``first`` et ``second`` designent la **meme image**.

    C'est la confrontation a faire entre un timecode demande et le timecode
    relu d'un master: comparer les deux chaines declare non conforme un master
    parfaitement juste des que ffmpeg n'ecrit pas ``ff`` sur deux chiffres.

    Un timecode absent ou illisible n'est equivalent a rien, pas meme a
    lui-meme: ``timecodes_equivalent(None, None)`` est ``False``. "Aucun des
    deux n'est lisible" n'est pas "les deux designent la meme image", et le
    seul appelant qui compte ici -- la verification du master -- doit refuser un
    conteneur sans ``tmcd`` au lieu de l'assimiler a une absence attendue.
    """
    left = timecode_position(first)
    return left is not None and left == timecode_position(second)


def timecode_to_frame_index(timecode: str, rate: float | int | str | Fraction) -> int:
    """Convertir ``timecode`` (``hh:mm:ss:ff``) en index absolu de frame a ``rate``.

    Arithmetique ``((h*60+m)*60+s)*nominal_fps+f``, ou ``nominal_fps =
    ceil(rate)`` -- la meme convention que ``timecode_frame_field_width`` et
    ``validate_timecode`` retiennent deja pour ce module. C'est aussi,
    formule pour formule, ce que ``frame_selection._timecode_to_frames``
    calcule de son cote -- prive a ce module distinct, non importable. Cette
    fonction existe pour que l'encodage (story 6.6) dispose de la meme
    arithmetique sans importer un prive d'un module qu'elle s'interdit
    d'ouvrir, et sans la dupliquer a l'aveugle.

    Seul le **plafond** de ``rate`` entre dans le calcul: deux cadences reelles
    de meme plafond (24 et 24,5, par exemple) rendent le meme index pour le
    meme timecode -- la notation ``hh:mm:ss:ff`` ne porte jamais la partie
    fractionnaire d'une cadence, seulement sa borne entiere sur le champ ``ff``.

    Leve ``EncodeConfigurationError`` sur un timecode illisible ou drop-frame:
    le drop-frame n'est jamais emis ni accepte par ce depot (meme refus que
    ``frame_selection._timecode_to_frames``).
    """
    position = timecode_position(timecode)
    if position is None:
        raise EncodeConfigurationError(
            f"Timecode illisible, forme hh:mm:ss:ff attendue: {timecode!r}"
        )
    if position.drop_frame:
        raise EncodeConfigurationError(
            f"Timecode drop-frame refuse: {timecode!r}. Le drop-frame n'est "
            "jamais emis ni accepte par ce depot."
        )
    nominal_fps = _frame_limit(Fraction(exact_frame_rate(rate)))
    return (
        (position.hours * 60 + position.minutes) * 60 + position.seconds
    ) * nominal_fps + position.frames


def frame_index_to_timecode(index: int, rate: float | int | str | Fraction) -> str:
    """L'inverse exact de :func:`timecode_to_frame_index` : index -> ``hh:mm:ss:ff``.

    **Elle est publiee ici, et pas ailleurs, pour n'exister qu'une fois.**
    L'arithmetique inverse vivait dans `frame_selection._format_timecode`,
    prive d'un module que le reste du depot s'interdit d'ouvrir -- c'est
    exactement le motif qui avait deja fait naitre
    :func:`timecode_to_frame_index` ici. La completion d'une identite saisie a
    la main (`EPIC7-ARB-103`) a besoin du meme calcul : sans point unique, ce
    serait une troisieme redaction, et trois arithmetiques de timecode
    divergent silencieusement -- l'ecart ne se voit que sur le nom des TIFF
    produits.

    **Le rebouclage a 24 h n'est pas optionnel** : `validate_timecode` leve
    « Timecode hors bornes » des ``hh > 23``, et un rush de vingt minutes
    demarrant a ``23:50:00:00`` deborde.

    Seul le **plafond** de ``rate`` entre dans le calcul, comme dans la
    fonction directe : la notation ``hh:mm:ss:ff`` ne porte jamais la partie
    fractionnaire d'une cadence.

    **Portee depuis la branche de l'Epic 7 le 2026-08-29**, ou elle etait ecrite
    mais **sans aucun test**. C'est ce qui a laisse `scan_corrections` etre
    recupere sans elle : le banc de ce module est vert a 72 sur 72 et ne touche
    jamais `payload_depuis_l_identite`, donc l'absence ne se voyait pas. Son
    banc est ecrit dans le meme mouvement que ce portage.
    """
    nominal_fps = _frame_limit(Fraction(exact_frame_rate(rate)))
    boucle = index % (_SECONDS_PER_JOUR * nominal_fps)
    frames = boucle % nominal_fps
    secondes_totales = boucle // nominal_fps
    secondes = secondes_totales % 60
    minutes = (secondes_totales // 60) % 60
    heures = secondes_totales // 3600
    return f"{heures:02d}:{minutes:02d}:{secondes:02d}:{frames:02d}"


def validate_timecode(timecode: str, fps: float | int | str | Fraction) -> str:
    """Validate an SMPTE timecode against ``fps``, returning it unchanged.

    FFmpeg accepts every invalid form below with ``rc=0``: ``01:00:00:24`` at
    24 fps is silently rewritten to ``01:00:01:00`` (a one-second offset from
    the manifest's page/slot mapping), while ``abc``, ``""`` and a drop-frame
    ``;`` on a non-NTSC rate simply produce a master with **no** ``tmcd``
    track at all. Only an explicit check catches those before encoding.

    Correction du 2026-08-10 -- **la largeur d'ecriture du champ ``ff`` n'est
    plus imposee**. La fonction n'acceptait qu'un champ de deux chiffres, si
    bien que le timecode relu d'un master a 5, 10 ou 120 im/s -- ecrit par
    ffmpeg sur une ou trois positions, voir ``timecode_frame_field_width`` --
    etait refuse alors qu'il est juste. Ce qui est refuse ne l'est pas moins
    pour autant: la borne ``ff < ceil(fps)`` est inchangee (``00:00:00:13`` a
    12,5 im/s reste illegal, et ffmpeg le normalise en ``00:00:01:00``), les
    champs ``hh``, ``mm`` et ``ss`` restent sur deux chiffres, et un
    remplissage arbitraire est refuse -- seules sont admises les largeurs
    plausibles a cette cadence, entre 1 et ``max(2, largeur d'ffmpeg)``: la
    forme canonique SMPTE sur deux chiffres, et celle qu'ffmpeg ecrit
    reellement. ``00:00:00:004`` est donc accepte a 120 im/s et refuse a 25.
    """
    if not isinstance(timecode, str):
        raise TypeError(f"timecode doit etre une chaine: {timecode!r}")
    match = _TIMECODE_RE.match(timecode)
    if match is None:
        raise ValueError(
            f"Timecode invalide: {timecode!r} (attendu hh:mm:ss:ff, ou hh:mm:ss;ff en drop-frame)"
        )
    position = _position_from_match(match)
    rate = Fraction(exact_frame_rate(fps))
    if position.hours > 23 or position.minutes > 59 or position.seconds > 59:
        raise ValueError(f"Timecode hors bornes: {timecode!r}")
    # ff must be < fps: ff == fps is the classic frame->TC off-by-one, and
    # ffmpeg absorbs it into the next second without a word.
    limit = _frame_limit(rate)
    if position.frames >= limit:
        raise ValueError(
            f"Timecode {timecode!r}: champ frames {position.frames} >= {limit} a {rate} fps"
        )
    # Largeur d'ecriture: la forme canonique SMPTE (deux chiffres) et celle
    # qu'ffmpeg ecrit a cette cadence sont les deux seules qui circulent dans la
    # chaine. Tolerer plus large ferait passer un `00:00:00:0000004`, qui ne
    # vient d'aucun producteur reel et signale une chaine de formatage cassee.
    field_width = len(match.group(5))
    max_width = max(2, len(str(limit - 1)))
    if field_width > max_width:
        raise ValueError(
            f"Timecode {timecode!r}: champ frames ecrit sur {field_width} chiffres, "
            f"au-dela des {max_width} chiffres plausibles a {rate} fps"
        )
    if position.drop_frame and rate not in NTSC_RATES:
        raise ValueError(
            f"Drop-frame ({timecode!r}) reserve aux cadences NTSC, pas {rate} fps"
        )
    return timecode


# ---------------------------------------------------------------------------
# Story 6.0 - fiabilisation de la fabrique de commande d'encodage.
#
# Tout ce qui suit est commente en francais (regle du CLAUDE.md du 2026-08-08)
# et les mesures citees ont ete rejouees le 2026-08-10 avec ffmpeg/ffprobe
# 6.1.1-3ubuntu5, par le banc `scripts/research/encode_robustness_bench.py`.
# ---------------------------------------------------------------------------


class EncodeError(Exception):
    """Racine des erreurs de la fabrique d'encodage (story 6.0)."""


class EncodeConfigurationError(EncodeError, ValueError):
    """Refus **a la construction**, avant qu'aucun octet ne soit ecrit.

    Herite de ``ValueError`` parce que c'est le contrat historique de
    ``build_encode_command`` (tag conteneur vide) et que six modules amont
    attrapent deja ``ValueError`` sur les entrees de cette famille.
    """


class EncoderUnavailableError(EncodeError):
    """L'encodeur du profil n'est pas compile dans le ffmpeg installe."""


class ProbeUnavailableError(EncodeError):
    """Le binaire ffprobe est introuvable ou inexecutable.

    Existe pour la meme raison que ``video_metadata.FfprobeNotFoundError``, dont
    elle est le pendant dans cette hierarchie: sans elle, ``probe_frame_size``
    -- atteinte **avant** ``video_metadata`` dans ``run_encode`` -- laissait
    remonter un ``FileNotFoundError`` nu, que tout appelant ecrit en
    ``except EncodeError`` manquait. Le cas symetrique (ffmpeg absent) etait
    deja type, celui-ci ne l'etait pas.
    """


class MasterAlreadyExistsError(EncodeError, FileExistsError):
    """Le chemin de sortie existe deja et l'ecrasement n'a pas ete demande."""


class EncodeRunError(EncodeError):
    """ffmpeg a rendu un code de retour non nul."""


class EncodeVerificationError(EncodeError):
    """Le fichier produit ne correspond pas a ce qui a ete demande.

    C'est le seul mode de panne de l'etape que rien en aval ne rattrape: une
    troncature silencieuse (`concat` rend `rc=0` avec `nb_frames=1` sur une
    liste de 2 dont un fichier a disparu, mesure) produit un master qui ment
    sur son propre contenu.
    """


#: Muxer ffmpeg associe a chaque conteneur du catalogue. Il sert deux fois:
#: pour refuser une extension qui contredit le profil (AC 6) et pour poser un
#: `-f` explicite sur le temporaire (AC 5a) -- ffmpeg deduit sinon le muxer de
#: l'extension et un nom de temporaire sans extension echoue a 100 %
#: (mesure: `Unable to choose an output format ... .out.mov.tmp-1234`, rc=234).
CONTAINER_MUXERS: dict[str, str] = {"mov": "mov", "mp4": "mp4"}

#: Valeurs de `EncodeProfile.colorspace` reellement utilisables **de bout en
#: bout**, remesurees le 2026-08-10.
#:
#: Correction d'une liste precedente qui portait huit valeurs et laissait passer
#: `bt2020nc`, c'est-a-dire le cas fondateur qu'elle etait censee fermer. Le
#: motif de l'erreur: la mesure d'origine ne portait que sur le filtre `scale`,
#: alors que le meme champ alimente **quatre** consommateurs au vocabulaire
#: different -- `out_color_matrix` d'une part, et les trois options de tag
#: `-colorspace` / `-color_primaries` / `-color_trc` d'autre part. Mesure des
#: quatre vocabulaires, sur 15 candidats:
#:
#: * `scale=out_color_matrix=<v>`: **les 15 rendent rc=0**, y compris `linear`
#:   ou `iec61966-2-1` qui ne sont pas des matrices. Le filtre ignore en silence
#:   ce qu'il ne comprend pas: il ne peut donc **rien** valider a lui seul;
#: * `-colorspace`: bt709, smpte170m, smpte240m, bt2020nc, bt2020_ncl, fcc,
#:   bt470bg, ycgco, smpte2085;
#: * `-color_primaries`: bt709, smpte170m, smpte240m, bt2020, bt470bg, bt470m;
#: * `-color_trc`: bt709, smpte170m, smpte240m, linear, iec61966-2-1.
#:
#: L'intersection -- et c'est elle qui compte, puisque les trois tags sont poses
#: **identiquement** depuis le meme champ -- est `{bt709, smpte170m, smpte240m}`.
#: Encodage complet de controle sur les 15 candidats: ces trois-la rendent
#: `rc=0` et se relisent tagues; les douze autres sortent en `rc=234`
#: (`Conversion failed!`), `bt2020nc` et `bt601` compris.
#:
#: Elargir cette liste demande donc de remesurer les **quatre** vocabulaires, ou
#: de dissocier la valeur de matrice de la valeur de tag dans `EncodeProfile` --
#: ce qui est une decision de catalogue, pas de fabrique.
#:
#: **CINQUIEME VOCABULAIRE depuis le 2026-09-06: `setparams`**, ajoute a la
#: chaine de filtres par `build_setparams_link`. Remesure faite avant de
#: toucher a cet ensemble, et elle ne le retrecit pas -- mais elle ne pouvait
#: pas etre supposee, les cinq vocabulaires ne coincidant pas:
#:
#: * `setparams=color_primaries`: bt709, bt470m, bt470bg, smpte170m, smpte240m,
#:   film, bt2020, smpte428, smpte431, smpte432, jedec-p22, ebu3213;
#: * `setparams=color_trc`: bt709, bt470m, bt470bg, smpte170m, smpte240m,
#:   linear, log100, log316, iec61966-2-4, bt1361e, iec61966-2-1, bt2020-10,
#:   bt2020-12, smpte2084, smpte428, arib-std-b67;
#: * `setparams=colorspace`: gbr, bt709, fcc, bt470bg, smpte170m, smpte240m,
#:   ycgco, bt2020nc, bt2020c, smpte2085, chroma-derived-nc, chroma-derived-c,
#:   ictcp.
#:
#: Leur intersection est `{bt709, bt470bg, smpte170m, smpte240m}`, qui
#: **contient** strictement l'ensemble ci-dessous: aucune des trois valeurs
#: retenues n'est perdue, et rien n'est elargi.
#:
#: Difference de nature avec `scale`, et elle est a l'avantage de `setparams`:
#: la ou `out_color_matrix` ignore en silence ce qu'il ne comprend pas -- donc
#: ne valide rien --, `setparams` **echoue franchement**. Mesure sous 6.1.1:
#: `bt2020nc`, `bt601`, `linear` et `iec61966-2-1` sortent en `rc=234`
#: (`Undefined constant or missing '(' in ...`), `bt470bg` rend `rc=0`. Le
#: cinquieme vocabulaire est donc une garde reelle, pas une declaration.
#:
#: Ecart 6.1.1 -> 8.1.2 releve le meme jour: `setparams` n'a **rien retire**, il
#: a seulement ajoute des valeurs (`vgamut`, `vlog`, `ycgco-re/ro`, `ipt-c2`) et
#: deux options (`chroma_location`, `alpha_mode`). Les trois valeurs retenues
#: sont donc acceptees sur les deux versions.
USABLE_COLOR_MATRICES: frozenset[str] = frozenset({"bt709", "smpte170m", "smpte240m"})

#: Compte rendu de la mesure du 2026-09-06 qui a motive `build_setparams_link`.
#: Il vit dans le code plutot que dans un document parce que c'est ici qu'on le
#: cherchera le jour ou une sixieme version renversera encore l'arbitrage.
#:
#: Point de depart: un master ProRes/DNxHD/H.264 produit chez Egan sortait en
#: `color_space=bt709` mais `color_primaries` et `color_transfer` **non
#: renseignes**, et la garde `verify_technical_metadata` le refusait -- a
#: raison, le fichier etait reellement mal tague.
#:
#: Deux binaires, meme argv, meme source de synthese, trois encodeurs
#: (`prores_ks` -profile:v 3, `dnxhd` -profile:v dnxhr_hqx, `libx264`). Les
#: colonnes donnent `color_space` / `color_primaries` / `color_transfer`, et le
#: verdict est identique sur les trois encodeurs:
#:
#: * `scale` + 3 options CLI (**etat du depot avant ce correctif**):
#:   6.1.1 -> bt709/bt709/bt709 ; 8.1.2 -> bt709/**unknown**/**unknown**;
#: * idem **sans** `-vf`:
#:   6.1.1 -> bt709/bt709/bt709 ; 8.1.2 -> bt709/**unknown**/**unknown**;
#: * `scale` + `setparams` + 3 options CLI (**apres correctif**):
#:   6.1.1 -> bt709/bt709/bt709 ; 8.1.2 -> bt709/bt709/bt709.
#:
#: **La deuxieme ligne renverse l'explication naturelle.** On a d'abord cru le
#: filtergraph responsable -- l'idee etant que `enc_open` derive desormais les
#: proprietes de l'encodeur depuis le buffersink et **ecrase** les options CLI.
#: La contre-epreuve la refute: retirer `-vf` ne ramene pas les primaires. Un
#: filtergraph implicite subsiste de toute facon (conversion de format), si bien
#: que ce regime ne prouvait rien a lui seul.
#:
#: Ce qu'un troisieme regime etablit, et qui donne la vraie cause: en posant
#: `setparams=smpte170m` **contre** des options CLI a `bt709`, 8.1.2 rend
#: `color_space=bt709` mais `color_primaries=smpte170m` et
#: `color_transfer=smpte170m`. Donc, sous FFmpeg 8:
#:
#: * `-colorspace` atteint encore l'encodeur et **gagne**;
#: * `-color_primaries` et `-color_trc` ne l'atteignent **plus du tout** -- ils
#:   ne sont pas arbitres, ils sont ignores. Seule la propriete portee par la
#:   frame compte.
#:
#: Sous 6.1.1 le meme regime rend `bt709` sur les trois champs: les options CLI
#: l'emportent partout. Les deux versions ne se contredisent donc jamais **tant
#: que les deux gestes portent la meme valeur**, ce que la fabrique garantit en
#: les derivant tous deux de `EncodeProfile.colorspace`.
#:
#: `color_range` reste absent en ProRes sur les deux versions: c'est l'ecart
#: connu de `video_metadata`, que ce correctif ne touche pas.
#:
#: NEUTRALITE SOUS 6.1.1, MESUREE AVANT DE LIVRER
#: ----------------------------------------------
#: Le risque de ce correctif est asymetrique: il repare un export impossible
#: sous FFmpeg 8, mais il ajoute un maillon de filtre sous 6.1.1 -- la version
#: de ce conteneur et de la CI -- ou il ne servait a rien.
#:
#: **Cette ligne disait « la version epinglee par `requirements.txt` », et
#: c'etait faux** (corrige le 2026-09-07, finding `C5` de la couche 2).
#: `requirements.txt` ne porte que `ffmpeg-python`, le paquet Python : **rien
#: dans le depot n'epingle le binaire ffmpeg**, ce que l'entree de
#: `deferred-work.md` du meme lot ecrivait correctement pendant que ce
#: commentaire ecrivait l'inverse. Un lecteur en concluait que FFmpeg 8 est
#: hors contrat -- c'est-a-dire exactement la conclusion que le lot laisse
#: ouverte comme arbitrage. Meme famille que les trois relectures fausses de
#: la borne d'identifiant : une valeur se lit a sa source, jamais dans une
#: prose voisine. Un maillon qui y
#: forcerait une conversion, une plage ou un refus echangerait un blocage
#: contre un autre. Mesure sur les **sept** profils, memes frames, chaine
#: d'avant contre chaine d'apres:
#:
#: * code de retour: identique (0) sur les sept;
#: * pixels decodes (condensat du flux `rgb48le` integral): **identiques** sur
#:   les sept -- le maillon ne convertit rien, il annote;
#: * poids du fichier: identique a l'octet pres sur les sept;
#: * `color_range`, `pix_fmt`, geometrie, cardinal: identiques sur les sept.
#:   ProRes reste sans `color_range`, comme avant.
#:
#: **Quatre profils rendent un fichier bit a bit identique** (les deux DNxHR,
#: h264, hevc). Les **trois ProRes** different, et il faut dire de quoi:
#: exactement **9 octets**, soit 3 frames x 3 champs, tous de `2`
#: (`UNSPECIFIED`) a `1` (`BT709`), aux offsets `icpf+18/19/20` de l'en-tete de
#: frame ProRes -- `color_primaries`, `transfer_characteristic`,
#: `matrix_coefficients`.
#:
#: Autrement dit, **avant ce correctif et deja sous 6.1.1, le bitstream ProRes
#: se declarait non tague** pendant que l'atome `colr` du conteneur, lui, etait
#: juste. `ffprobe` lisant l'atome, aucune garde du depot ne pouvait le voir;
#: un logiciel de montage qui lit l'en-tete de frame recevait « non specifie ».
#: C'est un defaut anterieur a la regression de FFmpeg 8, que le maillon ferme
#: au passage -- une amelioration stricte, pas une degradation, et la seule
#: difference locale que `tests/unit/test_tagage_colorimetrique.py` sache
#: attraper sous 6.1.1.
FFMPEG_COLOR_TAGGING_MEASUREMENT = (
    "2026-09-06, ffmpeg 6.1.1-3ubuntu5 et 8.1.2 (Lavf62.12.102/Lavc62.28.102): "
    "sous FFmpeg 8, -color_primaries et -color_trc n'atteignent plus l'encodeur; "
    "seul le maillon setparams de la chaine de filtres les pose encore."
)

#: Plage de sortie posee par la chaine de filtres (question ouverte 1 de la
#: story 6.0, tranchee `tv`). Motif mesure, et il est plus fort que la
#: convention: `prores_ks` **n'ecrit aucun `color_range`** dans le conteneur.
#: Avec `out_range=full`, le master est donc en pleine plage sans le dire, tout
#: decodeur le relit comme une plage legale, et le gris 50 % derive
#: (127,59 -> 129,91 mesure) pendant que les primaires saturees, elles,
#: ecretent et paraissent parfaites. `tv` rend l'aller-retour coherent avec ce
#: que le fichier declare (ecart max 1,06/255 sur la mire du banc).
OUTPUT_COLOR_RANGE = "tv"

#: Extension du fichier de liste `concat` temporaire.
_CONCAT_LIST_SUFFIX = ".mmuconcat"

#: Empreinte du nom de temporaire pose par ``_unique_sibling``: `<pid>-<12 hex>`
#: juste avant l'extension finale. Assez specifique pour qu'un balayage ne puisse
#: pas emporter un fichier cache qui ne vient pas de ce module.
_TEMP_NAME_RE = re.compile(r"\.\d+-[0-9a-f]{12}(\.[^.]+)?$")

#: Options que la fabrique pose elle-meme du cote **sortie** de la ligne de
#: commande. Un profil qui en emet une dans ses `extra_args` gagnerait l'arbitrage
#: (ffmpeg retient la derniere valeur) et remplacerait donc une decision de la
#: fabrique en silence. Le cas cher est `-vf`: un doublon de chaine de filtres
#: produit un master **tague `bt709` sans avoir subi la conversion**, c'est-a-dire
#: exactement le fichier a 40,33/255 d'ecart que cette story existe pour
#: supprimer, et rien en aval ne le rattrape.
_FACTORY_OWNED_OPTIONS: frozenset[str] = frozenset(
    {"-vf", "-filter:v", "-filter_complex", "-r", "-f", "-i", "-y", "-n",
     "-timecode", "-movflags", "-safe", "-metadata"}
)

#: Timecode porte par le **nom** des frames de la chaine v2: `extract` ecrit
#: `<lot_id>_<hh-mm-ss-ff>.tiff`, `scan` ecrit `scan_<lot_id>_<hh-mm-ss-ff>.tiff`
#: (verifie sur `projects/projet_demo/frames/TEST_FILE_5/`). Les quatre champs
#: sont zero-remplis, donc leur comparaison lexicographique **coincide** avec
#: l'ordre chronologique -- c'est ce qui rend la garde d'ordre calculable sans
#: relire les fichiers.
_FRAME_TIMECODE_RE = re.compile(r"(\d{2}-\d{2}-\d{2}-\d{2})$")


@dataclass(frozen=True)
class DimensionRule:
    """Contraintes dimensionnelles d'un encodeur, **mesurees** encodeur par
    encodeur -- jamais deduites d'une famille de sous-echantillonnage.

    La deduction par famille est fausse: `prores_ks` (4:2:2) et `dnxhd`
    (4:2:2) acceptent 321x181, et `dnxhd` refuse 240x120 dont les deux
    dimensions sont paires. Les valeurs ci-dessous viennent d'une matrice
    d'encodages reels du 2026-08-10.
    """

    even_width: bool
    even_height: bool
    min_width: int
    min_height: int

    def __post_init__(self) -> None:
        """Refuse une regle dont le plancher contredit la parite exigee.

        Invariant pose ici parce que ``_nearest_dimension`` en depend: une
        dimension impaire est ramenee vers le **bas**, et cette descente ne peut
        rester conforme que si le plancher est lui-meme pair. Une regle
        `min_width=3, even_width=True` rendrait 2, c'est-a-dire une valeur sous
        le plancher, presentee a l'operateur comme "la geometrie conforme la plus
        proche". La branche defensive qui traitait ce cas etait du **code mort**
        -- aucune des quatre regles du catalogue ne combine plancher impair et
        parite exigee, balayage exhaustif de 0 a 20000 sur les deux axes -- donc
        elle a ete retiree (un mutant equivalent se retire, il ne se teste pas)
        et remplacee par cet invariant, qui lui est verifiable.
        """
        if self.even_width and self.min_width % 2:
            raise ValueError(
                f"Regle dimensionnelle incoherente: min_width={self.min_width} impair "
                "avec parite de largeur exigee"
            )
        if self.even_height and self.min_height % 2:
            raise ValueError(
                f"Regle dimensionnelle incoherente: min_height={self.min_height} impair "
                "avec parite de hauteur exigee"
            )

    def violations(self, width: int, height: int) -> list[str]:
        """Rend la liste des contraintes violees, en clair et en ASCII."""
        problems: list[str] = []
        if width < self.min_width:
            problems.append(f"largeur {width} < minimum {self.min_width}")
        if height < self.min_height:
            problems.append(f"hauteur {height} < minimum {self.min_height}")
        if self.even_width and width % 2:
            problems.append(f"largeur {width} impaire (parite exigee)")
        if self.even_height and height % 2:
            problems.append(f"hauteur {height} impaire (parite exigee)")
        return problems

    def nearest(self, width: int, height: int) -> tuple[int, int]:
        """Rend la geometrie conforme la plus proche.

        Question ouverte 2 de la story, tranchee: la valeur conforme est
        **calculee ici et nulle part ailleurs**. La calculer aussi chez
        l'appelant est le motif de divergence que le depot a deja ferme trois
        fois. Pour une dimension impaire on **descend** d'un pixel: reduire ne
        fabrique aucun contenu, alors qu'agrandir inventerait une colonne. Pour
        un seuil (DNxHR) la valeur rendue est le seuil, pas un arrondi.
        """
        return (
            _nearest_dimension(width, self.min_width, self.even_width),
            _nearest_dimension(height, self.min_height, self.even_height),
        )


def _nearest_dimension(value: int, minimum: int, even: bool) -> int:
    """Ramene ``value`` sur la valeur conforme la plus proche.

    ``value - 1`` reste toujours ``>= minimum``: ``DimensionRule.__post_init__``
    garantit qu'un plancher assorti d'une parite est pair, et une ``value``
    impaire strictement superieure a un plancher pair vaut au moins
    ``minimum + 1``.
    """
    if value < minimum:
        return minimum
    if even and value % 2:
        # On descend d'un pixel: reduire ne fabrique aucun contenu, agrandir
        # inventerait une colonne, et les deux sont a distance 1.
        return value - 1
    return value


#: Contraintes reelles par encodeur. Matrice d'encodages du 2026-08-10, entree
#: TIFF 16 bits, deux frames distinctes:
#:
#: | dimensions | prores_ks | dnxhd | libx264 | libx265 |
#: | 320x180    | rc=0      | rc=0  | rc=0    | rc=0    |
#: | 321x181    | rc=0      | rc=0  | rc=187  | rc=183  |
#: | 240x120    | rc=0      | rc=234| rc=0    | rc=0    |
#: | 256x110    | rc=0      | rc=234| rc=0    | rc=0    |
#: | 3307x1860  | rc=0      | rc=0  | rc=187  | rc=183  |
#: | 16x16      | rc=0      | rc=234| rc=0    | rc=0    |
#: | 14x14      | rc=0      | rc=234| rc=0    | rc=234  |
#:
#: Deux plancher-minimums que la story n'avait pas mesures et qu'une regle de
#: seule parite laisserait passer: `dnxhd` exige **aussi** une hauteur >= 120
#: (256x110 sort en rc=234), et `libx265` exige les deux dimensions >= 16
#: (16x8, 8x16, 14x14 sortent en rc=234).
ENCODER_DIMENSION_RULES: dict[str, DimensionRule] = {
    "prores_ks": DimensionRule(even_width=False, even_height=False, min_width=1, min_height=1),
    "dnxhd": DimensionRule(even_width=False, even_height=False, min_width=256, min_height=120),
    "libx264": DimensionRule(even_width=True, even_height=True, min_width=2, min_height=2),
    "libx265": DimensionRule(even_width=True, even_height=True, min_width=16, min_height=16),
}


def dimension_rule(vcodec: str) -> DimensionRule:
    """Rend la regle dimensionnelle de ``vcodec``, ou leve si elle est inconnue.

    Refuser explicitement vaut mieux que retomber sur une regle permissive:
    un encodeur ajoute au catalogue sans mesure sortirait sinon en echec
    d'encodage apres avoir lu toutes les frames.
    """
    try:
        return ENCODER_DIMENSION_RULES[vcodec]
    except KeyError as exc:
        raise EncodeConfigurationError(
            f"Aucune contrainte dimensionnelle mesuree pour l'encodeur {vcodec!r}. "
            f"Encodeurs mesures: {sorted(ENCODER_DIMENSION_RULES)}"
        ) from exc


def _as_dimension(value: object, axis: str, profile: EncodeProfile) -> int:
    """Refuse une dimension non entiere, et rend l'entier.

    Le module garde les types partout ailleurs -- ``exact_frame_rate`` rejette
    explicitement ``bool``, ``validate_timecode`` exige une ``str`` -- et la
    geometrie etait la seule porte sans garde de type. Elle avait **trois**
    modes de panne mesures, dont le premier est le plus vicieux parce qu'il
    reussit:

    * ``(320.0, 180.0)`` passe, encode, et persiste
      ``target_resolution = "320.0x180.0"`` au manifest: aucune confrontation
      aval ne matchera jamais ``"320x180"``;
    * ``(320.6, 180.4)`` leve une ``EncodeVerificationError`` **apres**
      l'encodage complet, c'est-a-dire apres lecture de toutes les frames;
    * ``(True, True)`` produit ``scale=True:True`` et un ``rc=234`` opaque.
    """
    if not is_strict_int(value):
        raise EncodeConfigurationError(
            f"Geometrie cible non entiere pour le profil {profile.profile_id!r}: "
            f"{axis}={value!r} ({type(value).__name__}). La geometrie est une "
            "decision de la story 6.1, elle arrive ici en pixels entiers."
        )
    return value


def check_target_dimensions(profile: EncodeProfile, width: int, height: int) -> None:
    """Refuse **en amont** une geometrie que l'encodeur du profil rejette.

    Nomme la dimension fautive, le profil, la contrainte violee et la
    geometrie conforme la plus proche. Cette fabrique ne corrige pas: recadrer
    ou completer une image est une decision de cadrage, elle appartient a la
    story 6.1.
    """
    width = _as_dimension(width, "largeur", profile)
    height = _as_dimension(height, "hauteur", profile)
    if width <= 0 or height <= 0:
        raise EncodeConfigurationError(
            f"Geometrie cible invalide pour le profil {profile.profile_id!r}: {width}x{height}"
        )
    rule = dimension_rule(profile.vcodec)
    problems = rule.violations(width, height)
    if not problems:
        return
    near_w, near_h = rule.nearest(width, height)
    raise EncodeConfigurationError(
        f"Geometrie {width}x{height} refusee par l'encodeur {profile.vcodec!r} "
        f"du profil {profile.profile_id!r}: {'; '.join(problems)}. "
        f"Geometrie conforme la plus proche: {near_w}x{near_h}"
    )


def build_filter_chain(profile: EncodeProfile, target_size: tuple[int, int] | None = None) -> str:
    """Rend la chaine de filtres qui **applique** la matrice du profil.

    Taguer n'est pas convertir: `-colorspace bt709` decrit le flux, il ne
    pilote pas swscale, dont la matrice par defaut reste BT.601. Mesure du
    2026-08-10, aller-retour sur mire saturee: **ecart max 40,33/255** avec les
    tags seuls (vert 40,33, magenta 39,35), **1,06/255** avec cette chaine.

    Contre-epreuve, et elle justifie que les deux gestes coexistent: la meme
    chaine **sans** les trois tags donne `color_space=unknown` et un ecart de
    **23,00/255**. Les tags restent donc necessaires, ils sont emis par
    ``EncodeProfile.ffmpeg_video_args``.

    ``target_size`` est le **seul** point qui autorise un redimensionnement, et
    son absence signifie "pas de redimensionnement": la valeur est decidee
    par la story 6.1, appliquee ici.

    **Le maillon ``setparams`` n'est pas un doublon des trois options CLI: sous
    FFmpeg 8 il est le SEUL des deux gestes qui atteigne encore l'encodeur**
    (mesure du 2026-09-06, voir ``FFMPEG_COLOR_TAGGING_MEASUREMENT``). Les deux
    coexistent parce qu'ils portent la **meme** valeur -- celle du profil -- et
    qu'aucune version ne les voit donc se contredire.
    """
    if profile.colorspace not in USABLE_COLOR_MATRICES:
        raise EncodeConfigurationError(
            f"Colorspace {profile.colorspace!r} du profil {profile.profile_id!r} inutilisable: "
            "le filtre scale l'accepte peut-etre, mais les trois options de tag posees depuis "
            f"le meme champ ne l'acceptent pas toutes. Valeurs mesurees utilisables de bout en "
            f"bout: {sorted(USABLE_COLOR_MATRICES)}"
        )
    options = [f"out_color_matrix={profile.colorspace}", f"out_range={OUTPUT_COLOR_RANGE}"]
    if target_size is not None:
        width, height = _unpack_target_size(target_size)
        # Garde de **type** seulement: la conformite a l'encodeur est verifiee par
        # `check_target_dimensions`, appelee depuis `build_encode_command`. La poser
        # ici aussi rendrait cet appel-la invisible a toute mesure.
        width = _as_dimension(width, "largeur", profile)
        height = _as_dimension(height, "hauteur", profile)
        options = [str(width), str(height), *options]
    return "scale=" + ":".join(options) + "," + build_setparams_link(profile.colorspace)


def build_setparams_link(colorspace: str) -> str:
    """Rend le maillon ``setparams`` qui **marque les frames elles-memes**.

    Ce maillon existe pour une regression de terrain, et il faut garder la
    mesure sous la main parce qu'elle est contre-intuitive: sous FFmpeg 8, les
    options ``-color_primaries`` et ``-color_trc`` **n'atteignent plus
    l'encodeur du tout**. Elles ne sont ni ecrasees ni arbitrees: elles sont
    ignorees, et le master sort en ``bt709/unknown/unknown``. Seul
    ``-colorspace`` survit, ce qui explique la forme exacte du symptome.

    ``setparams`` pose la propriete sur la **frame**, c'est-a-dire du cote que
    FFmpeg 8 lit encore. Il existe depuis FFmpeg 4, donc il ne coute rien sous
    6.1.1, ou il est simplement redondant avec les options CLI.

    Voir ``FFMPEG_COLOR_TAGGING_MEASUREMENT`` pour le tableau des trois regimes
    mesures et les deux versions sous lesquelles ils l'ont ete.
    """
    return (
        f"setparams=color_primaries={colorspace}"
        f":color_trc={colorspace}"
        f":colorspace={colorspace}"
        f":range={OUTPUT_COLOR_RANGE}"
    )


def _unpack_target_size(target_size: object) -> tuple[int, int]:
    """Rend le couple ``(largeur, hauteur)``, en refusant toute autre forme."""
    try:
        width, height = target_size  # type: ignore[misc]
    except (TypeError, ValueError) as exc:
        raise EncodeConfigurationError(
            f"Geometrie cible mal formee: {target_size!r}, attendu un couple (largeur, hauteur)"
        ) from exc
    return width, height


@functools.lru_cache(maxsize=8)
def available_encoders(ffmpeg_bin: str = "ffmpeg") -> frozenset[str]:
    """Rend l'ensemble des encodeurs reellement compiles dans ``ffmpeg_bin``.

    Deux pieges mesures, et ils excluent les deux constatations les plus
    naturelles:

    * ``shutil.which("ffmpeg")`` rend un chemin **quels que soient** les
      encodeurs compiles: le motif de ``FfprobeNotFoundError`` ne se transpose
      pas;
    * ``ffmpeg -h encoder=libx265`` rend ``rc=0``, mais
      ``ffmpeg -h encoder=libnonexistent`` rend **aussi** ``rc=0``, avec le
      texte ``Codec 'libnonexistent' is not recognized by FFmpeg`` sur la
      sortie standard. Une garde branchee sur le code de retour declarerait
      disponible **tout** encodeur, y compris inexistant.

    D'ou l'analyse de la **sortie** de ``-encoders``, dont le corps commence
    apres une ligne de tirets et dont chaque ligne est
    ``<drapeaux> <nom> <description>``.

    **Le code de retour est lu, lui.** Le raisonnement ci-dessus vaut pour
    ``-h encoder=``, ou un ``rc=0`` ne prouve rien; il ne vaut pas pour
    ``-encoders``, ou un ``rc`` non nul prouve que le listing est incomplet. Un
    ``ffmpeg -encoders`` tue (OOM, SIGPIPE, quota) qui a eu le temps d'ecrire sa
    ligne de separation rendait sinon un ensemble **partiel**, accepte puis
    memorise par ``lru_cache`` pour toute la vie du processus -- et le
    diagnostic sorti de la, "encodeur absent du binaire", est faux **et
    definitif** alors que le binaire est complet. Lever plutot que rendre est
    aussi ce qui protege le cache: ``lru_cache`` ne memorise pas les exceptions,
    donc un appel suivant remesure.
    """
    if shutil.which(ffmpeg_bin) is None:
        raise EncoderUnavailableError(f"Binaire ffmpeg introuvable dans le PATH: {ffmpeg_bin!r}")
    try:
        result = subprocess.run(
            [ffmpeg_bin, "-hide_banner", "-encoders"],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        raise EncoderUnavailableError(
            f"Binaire ffmpeg inexecutable: {ffmpeg_bin!r} ({exc})"
        ) from exc
    if result.returncode != 0:
        raise EncoderUnavailableError(
            f"'{ffmpeg_bin} -encoders' a rendu le code {result.returncode}: le listing est "
            "incomplet et l'ensemble qu'on en tirerait accuserait a tort une compilation "
            f"partielle. {(result.stderr or '').strip()[-200:]}"
        )
    lines = (result.stdout or "").splitlines()
    separator = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped and set(stripped) == {"-"}:
            separator = index
            break
    if separator is None:
        # Sans la ligne de separation on ne sait pas ou commence le corps: une
        # tolerance ici rendrait un ensemble vide, donc "aucun encodeur
        # disponible", donc un refus generalise difficile a diagnostiquer.
        raise EncoderUnavailableError(
            f"Sortie de '{ffmpeg_bin} -encoders' illisible: aucune ligne de separation"
        )
    names = set()
    for line in lines[separator + 1:]:
        parts = line.split()
        if len(parts) >= 2:
            names.add(parts[1])
    return frozenset(names)


def ensure_encoder_available(profile: EncodeProfile, ffmpeg_bin: str = "ffmpeg") -> None:
    """Refuse avant lecture des frames si l'encodeur du profil est absent.

    Frontiere a garder en tete: "disponible" n'est pas "utilisable".
    ``dnxhd`` figure dans ``-encoders`` et refuse pourtant 240x136
    (``check_target_dimensions``). Les deux gardes sont independantes.
    """
    if profile.vcodec not in available_encoders(ffmpeg_bin):
        raise EncoderUnavailableError(
            f"Encodeur {profile.vcodec!r} du profil {profile.profile_id!r} absent de "
            f"{ffmpeg_bin!r}. Un ffmpeg systeme sans libx265 est le cas ordinaire."
        )


#: Ce que rend `probe_tool_version` quand la version n'a pas pu etre relevee.
#: **Une chaine, jamais une exception**: ce releve est consomme dans des chemins
#: d'erreur (le rapport de refus technique), et une sonde qui leve y remplacerait
#: l'erreur en cours par la sienne -- exactement le defaut que le `finally` de
#: `run_encode` documente deja pour `unlink`.
TOOL_VERSION_UNKNOWN = "version indeterminee"

#: Bibliotheques relevees en plus du numero de version. Ce sont celles
#: qu'affiche `ffmpeg -version` et celles qu'Egan a citees en rapportant la
#: regression du 2026-09-06 (`Lavf62.6.103` / `Lavc62.19.100`): c'est le
#: vocabulaire dans lequel une version de ffmpeg se nomme sur le terrain.
_TOOL_VERSION_LIBRARIES = ("libavcodec", "libavformat", "libavutil")

#: `ffmpeg version 6.1.1-3ubuntu5 Copyright ...`, `ffprobe version n8.1.2-50-g...`.
_TOOL_VERSION_RE = re.compile(r"^\w+ version (\S+)")

#: `libavutil      58. 29.100 / 58. 29.100` -- le nombre d'espaces apres les
#: points varie avec la largeur des champs (`61.  7.100` sur une version master),
#: donc il est absorbe plutot que compte.
_TOOL_LIBRARY_RE = re.compile(r"^(lib\w+)\s+(\d+)\.\s*(\d+)\.\s*(\d+)")


#: Versions deja relevees, par binaire. **Seuls les SUCCES y entrent**, et
#: c'est la difference qui compte -- voir le docstring de
#: `probe_tool_version`.
_VERSIONS_RELEVEES: dict[str, str] = {}


def probe_tool_version(binary: str) -> str:
    """Rend la version de `binary` (ffmpeg ou ffprobe), en une ligne lisible.

    **Pourquoi ce releve existe.** Le 2026-09-06, un master mal tague est
    remonte du terrain et le diagnostic a coute une soiree entiere, uniquement
    parce que rien -- ni le manifeste d'encodage, ni le rapport de refus -- ne
    disait sous **quelle version de ffmpeg** le fichier avait ete produit. La
    cause etait un renversement de comportement entre FFmpeg 6 et 8
    (`FFMPEG_COLOR_TAGGING_MEASUREMENT`), c'est-a-dire precisement le genre de
    fait qu'un numero de version rend immediat. Les deux en-tetes de module qui
    declarent « mesure sous 6.1.1 » n'etaient adosses a aucun releve
    d'execution: la version supposee et la version reelle pouvaient diverger
    sans que rien ne le dise.

    **Ce releve ne refuse rien, et c'est delibere.** Poser un plancher ou un
    plafond de version serait un arbitrage produit -- lequel, et pour qui? --
    qu'Egan n'a pas tranche et qui bloquerait son terrain sur-le-champ. La
    fonction releve, nomme et journalise; la question du plancher est consignee
    dans `deferred-work.md`.

    **Seuls les SUCCES sont memorises, et le module avait deja paye la lecon
    trente lignes plus haut** (corrige le 2026-09-07, finding `C2` de la couche
    1). Le premier jet posait un `lru_cache` sur une fonction qui **rend** un
    temoin d'echec au lieu de lever -- or `available_encoders` explique, sur
    mesure d'un incident reel, que « lever plutot que rendre est aussi ce qui
    protege le cache : `lru_cache` ne memorise pas les exceptions, donc un
    appel suivant remesure ». Cette sonde faisait exactement l'inverse des
    deux cotes.

    Le regime ou ca mord, et il est celui de l'Epic 11 : la TUI est un
    processus **long**. Une premiere sonde ratee -- `PATH` incomplet au
    demarrage, `ffmpeg` installe ensuite, binaire remplace -- estampillait
    « version indeterminee » sur **tous** les masters de la session,
    c'est-a-dire eteignait en silence le temoin que ce releve existe pour
    poser. Mesure : deuxieme appel avec le binaire desormais installe, toujours
    « version indeterminee », `hits=1`.

    Un echec n'est donc pas retenu : il coute une relance de `ffmpeg -version`
    au prochain appel, ce qui est le prix a payer pour qu'une panne transitoire
    ne devienne pas definitive.

    Rend `TOOL_VERSION_UNKNOWN` plutot que de lever sur binaire absent,
    inexecutable, en echec, **suspendu** ou a la sortie illisible: ce releve est
    un **temoin**, jamais une garde, et il est lu depuis des chemins d'erreur ou
    lever masquerait la panne qu'on cherche a decrire. La disponibilite reelle
    de ffmpeg, elle, est repondue par `available_encoders`, qui leve.
    """
    deja = _VERSIONS_RELEVEES.get(binary)
    if deja is not None:
        return deja
    if shutil.which(binary) is None:
        return TOOL_VERSION_UNKNOWN
    try:
        result = subprocess.run(
            [binary, "-version"],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            # **Le plafond est ce qui empeche le temoin de devenir la panne**
            # (pose le 2026-09-07, sur finding T6 de la couche 3). Sans lui, un
            # binaire qui suspend sur `-version` suspend l'encodage entier --
            # et, pire, il suspend le CHEMIN DE REFUS, c'est-a-dire le message
            # qui devait justement decrire la panne. Un releve qui se declare
            # « temoin, jamais garde » ne peut pas se permettre d'etre le seul
            # point du chemin capable de tout arreter.
            #
            # Cinq secondes: `ffmpeg -version` ne lit aucun media, n'ouvre
            # aucun peripherique et n'interroge aucun reseau -- il imprime des
            # constantes de compilation. Mesure dans ce conteneur: 40 ms. Le
            # plafond n'est donc pas une estimation de la duree normale, c'est
            # un ordre de grandeur au-dela duquel la commande ne travaille plus
            # mais attend quelque chose.
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return TOOL_VERSION_UNKNOWN
    if result.returncode != 0:
        return TOOL_VERSION_UNKNOWN
    version = _format_tool_version(result.stdout or "")
    if version != TOOL_VERSION_UNKNOWN:
        _VERSIONS_RELEVEES[binary] = version
    return version


def format_tool_provenance(encoder_version: str, prober_bin: str) -> str:
    """Rend `ffmpeg <version>, ffprobe <version>`, prete a citer dans un refus.

    **Cette fonction existe pour une frontiere du depot, pas par gout du
    factorisage.** `encode.py` est le module de DECISION: un banc negatif
    (`test_the_decision_module_builds_no_command_and_spawns_no_process`) lui
    interdit tout `subprocess` et **tout litteral contenant un nom de binaire
    d'encodage**, parce que l'un ou l'autre signerait le debordement sur la
    story 6.0. Ecrire `f"ffmpeg {...}"` la-bas fait rougir ce banc -- il l'a
    fait, le 2026-09-06.

    Le vocabulaire des binaires appartient donc a la fabrique, qui les lance
    deja. L'appelant recoit une chaine opaque et n'a rien a nommer.

    Les deux versions sont citees parce qu'elles peuvent differer et que
    l'ecart est lui-meme un diagnostic: ffmpeg **ecrit** le fichier, ffprobe le
    **relit**, et un refus technique met precisement les deux en cause.
    """
    return f"ffmpeg {encoder_version}, ffprobe {probe_tool_version(prober_bin)}"


def _format_tool_version(output: str) -> str:
    """Met en forme la sortie de `<outil> -version`.

    Rend par exemple
    `6.1.1-3ubuntu5 (libavcodec 60.31.102, libavformat 60.16.100, libavutil 58.29.100)`.

    Les bibliotheques sont rendues **dans l'ordre de `_TOOL_VERSION_LIBRARIES`**
    et non dans celui de la sortie: deux releves pris sur deux machines doivent
    se comparer a l'oeil, ce qu'un ordre dependant du binaire empecherait.
    """
    release = ""
    seen: dict[str, str] = {}
    for line in output.splitlines():
        stripped = line.strip()
        if not release:
            match = _TOOL_VERSION_RE.match(stripped)
            if match:
                release = match.group(1)
                continue
        library = _TOOL_LIBRARY_RE.match(stripped)
        if library and library.group(1) not in seen:
            seen[library.group(1)] = (
                f"{library.group(2)}.{library.group(3)}.{library.group(4)}"
            )
    if not release:
        # Un binaire qui rend rc=0 sans ligne de version n'est pas celui qu'on
        # croit: nommer une version inventee serait pire que d'avouer le trou.
        return TOOL_VERSION_UNKNOWN
    detail = ", ".join(
        f"{name} {seen[name]}" for name in _TOOL_VERSION_LIBRARIES if name in seen
    )
    return f"{release} ({detail})" if detail else release


def format_concat_entry(path: Path | str) -> str:
    """Rend la ligne ``file '...'`` d'un fichier de liste ``concat``.

    Le chemin est **absolu** (les chemins relatifs d'une liste `concat` se
    resolvent par rapport au **fichier de liste**, pas au repertoire courant:
    mesure, une liste ecrite ailleurs que dans le dossier des frames sort en
    ``Impossible to open 'rel/rel/sub/frame.tiff'``, rc=254) et **echappe**
    (``'`` -> ``'\\''``): sans echappement une apostrophe fait lire un chemin
    faux et l'encodage porte sur autre chose, en rendant rc=0.

    Passent, mesures: apostrophe, espace, ``%``, ``#``, crochets, guillemet,
    virgule, deux-points, contre-oblique. Seul un saut de ligne echoue
    franchement (rc=183), donc il est refuse ici.
    """
    text = str(path)
    if "\n" in text or "\r" in text:
        raise EncodeConfigurationError(
            f"Chemin de frame contenant un saut de ligne, inexprimable en liste concat: {text!r}"
        )
    escaped = text.replace("'", "'\\''")
    return f"file '{escaped}'\n"


def _unique_sibling(target: Path, suffix: str) -> Path:
    """Rend un nom temporaire, **dans le dossier de destination**.

    Trois exigences mesurees tiennent dans ce nom:

    * il vit a cote de la cible, parce que ``os.replace`` d'un ``/dev/shm``
      vers le depot rend ``OSError [Errno 18] Invalid cross-device link``;
    * il discrimine plus que le PID: ``os.getpid()`` seul ne separe pas deux
      encodages simultanes d'un **meme** processus vers la meme cible;
    * ``suffix`` est place en **dernier**, de sorte que le temporaire d'un
      master conserve l'extension du conteneur.

    **La double extension est retiree ici aussi** (2026-09-07, finding ``C4``
    de la couche 2 de la revue du lot de tagage). ``_staged_output_path`` avait
    ete corrige la veille, mais **pas ce producteur-ci** -- et c'est lui qui
    fuit reellement : ``concat_list_file`` documente qu'un ``SIGTERM`` ou un
    ``SIGKILL`` laisse un temporaire derriere lui (``rc=143`` et ``rc=137``
    mesures, un residu a chaque fois), la ou le fichier d'attente de
    ``execute_plan`` est conserve **volontairement** et nomme dans le refus.
    Autrement dit la moitie corrigee etait la moitie visible, et la moitie
    oubliee etait la moitie qui traine.

    Mesure : ``_unique_sibling(Path("m.mov"), ".mov")`` rendait
    ``.m.mov.10848-fcaa89f54c88.mov`` -- **la forme exacte** qu'Egan a
    signalee. Elle rend desormais ``.m.10848-fcaa89f54c88.mov``.

    Le tronc n'est raccourci que si le nom porte **deja** ce suffixe-la : le
    second appelant vise ``<dossier>/frames`` avec le suffixe de liste
    ``concat``, ou rien ne se repete et ou le nom ne bouge pas. Et
    ``_TEMP_NAME_RE`` reconnait les deux formes -- le balayage ne perd donc ni
    les residus d'aujourd'hui ni ceux qu'Egan a deja sur son disque, ce qui
    serait le prix cache d'un motif rétréci.
    """
    unique = f"{os.getpid()}-{uuid.uuid4().hex[:12]}"
    tronc = target.stem if suffix and target.suffix == suffix else target.name
    return target.parent / f".{tronc}.{unique}{suffix}"


@contextlib.contextmanager
def concat_list_file(frame_paths: Sequence[Path | str], directory: Path | str) -> Iterator[Path]:
    """Ecrit un fichier de liste ``concat`` et le supprime **sur tout chemin**.

    Portee exacte, et la formulation precedente ("reussite, echec ou
    interruption: aucun residu") etait trop large: le ``finally`` couvre la
    reussite, l'echec, toute exception et ``SIGINT`` (mesure: ``rc=130``, zero
    residu). Il ne couvre **ni ``SIGTERM`` ni ``SIGKILL``** -- mesure ``rc=143``
    et ``rc=137``, un fichier de liste **cache** subsiste a chaque fois -- parce
    qu'aucun ``finally`` de Python ne se deroule sur ces deux-la. C'est
    ``sweep_encode_residues`` qui repond de ce cas, et elle explique pourquoi il
    n'est pas benin.

    ``directory`` est le dossier de **destination** et non celui des frames:
    ce dernier est une sortie d'`extract`, inventoriee et potentiellement
    balayee par la chaine, ou un fichier etranger n'a rien a faire.

    Une liste **vide** est refusee ici plutot que laissee a `concat`, dont la
    reponse (``No files to concat``, rc=183) est opaque.
    """
    frames = list(frame_paths)
    if not frames:
        raise EncodeConfigurationError(
            "Sequence d'entree vide: rien a encoder (concat repondrait 'No files to concat')"
        )
    directory = Path(directory)
    list_path = _unique_sibling(directory / "frames", _CONCAT_LIST_SUFFIX)
    try:
        list_path.write_text(
            "".join(format_concat_entry(Path(frame).resolve()) for frame in frames),
            encoding="utf-8",
        )
        yield list_path
    finally:
        # Un `unlink` en echec ne doit pas remplacer l'erreur en cours: c'est le
        # meme motif que le `finally` de `run_encode`.
        with contextlib.suppress(OSError):
            list_path.unlink(missing_ok=True)


def probe_frame_size(frame_path: Path | str, *, ffprobe_bin: str = "ffprobe") -> tuple[int, int]:
    """Rend ``(largeur, hauteur)`` d'une frame d'entree, via ffprobe.

    L'absence du binaire est une ``ProbeUnavailableError``, jamais un
    ``FileNotFoundError`` nu: cette fonction est atteinte **avant**
    ``video_metadata`` dans ``run_encode``, et le cas symetrique (ffmpeg absent)
    est deja type. Sans cela, l'operateur lisait "toutes vos frames sont
    corrompues" pour un ffprobe manquant.
    """
    try:
        result = subprocess.run(
            [
                ffprobe_bin, "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height", "-of", "csv=p=0", "--", str(frame_path),
            ],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        raise ProbeUnavailableError(
            f"Binaire ffprobe introuvable ou inexecutable: {ffprobe_bin!r} ({exc})"
        ) from exc
    fields = (result.stdout or "").strip().split(",")
    if result.returncode != 0 or len(fields) < 2:
        raise EncodeConfigurationError(
            f"Frame illisible: {str(frame_path)!r} ({(result.stderr or '').strip()[-200:]})"
        )
    try:
        largeur, hauteur = int(fields[0]), int(fields[1])
    except ValueError as exc:
        raise EncodeConfigurationError(
            f"Dimensions illisibles pour {str(frame_path)!r}: {result.stdout!r}"
        ) from exc
    # **Une dimension nulle est une frame illisible, pas une geometrie**, et
    # ffprobe ne le dit PAS par son code de retour : mesure le 2026-09-06 sur
    # un TIFF a l'en-tete tronque, il ecrit `Invalid TIFF header` sur la sortie
    # d'erreur, rend `0,0` sur la sortie standard et sort en **rc=0**. La garde
    # ci-dessus ne mord donc pas, et le `(0, 0)` traversait
    # `ensure_uniform_frame_shapes` jusqu'a `encode._same_aspect_ratio`, ou
    # `Fraction(0, 0)` levait un `ZeroDivisionError` -- exception que
    # `plan_encode` ne convertit pas en `EncodeDecisionError`. En TUI, cela ne
    # produisait ni un refus ni une issue mais une **chute** de l'application,
    # et `E4-3b` (« ce master existe deja ») devenait inatteignable des qu'une
    # seule frame du lot etait tronquee. Le refus rejoint donc celui du rc!=0,
    # qui existe deja et que `plan_encode` sait rendre a l'operateur.
    if largeur <= 0 or hauteur <= 0:
        raise EncodeConfigurationError(
            f"Frame illisible: {str(frame_path)!r} -- ffprobe rend "
            f"{largeur}x{hauteur}, ce qui n'est pas une geometrie "
            f"({(result.stderr or '').strip()[-200:]})"
        )
    return largeur, hauteur


def ensure_uniform_frame_shapes(
    frame_paths: Sequence[Path | str],
    *,
    ffprobe_bin: str = "ffprobe",
    rappel_progression=None,
) -> tuple[int, int]:
    """Sonde **toutes** les entrees et refuse des formes heterogenes.

    Une garde qui ne sonderait que la premiere frame ne verrait jamais rien:
    mesure, une liste ``[320x180, 321x181]`` sort en rc=0, master en 320x180,
    ``nb_frames=2``; la liste inversee sort en 321x181. La geometrie est figee
    par la **premiere** entree, les suivantes sont redimensionnees en silence,
    le rapport d'aspect change, et le controle de cardinal passe (2 = 2).

    `rappel_progression` est **optionnel** (`AR3`, story 6.7): sans lui, rien
    ne change. Avec lui, il recoit un jalon `(faites, total)` **par frame
    reellement sondee**, ou `total` vaut `len(frames)` -- un cardinal de
    liste, exact par construction.

    **Pourquoi cette phase-ci et pas une autre.** Elle sonde chaque frame par
    un `subprocess.run` de ffprobe, soit ~76 ms par frame: sur un lot de
    plusieurs centaines d'images, c'est la phase la plus longue AVANT
    l'encodage lui-meme, et la seule dont le cardinal soit connu d'avance.

    Le canal est observationnel (`EPIC7-ARB-79`): un rappel qui leve est
    absorbe et journalise une seule fois, tandis que les pannes de sonde
    (`ProbeUnavailableError`, `EncodeConfigurationError`) traversent intactes,
    texte compris.
    """
    frames = list(frame_paths)
    if not frames:
        raise EncodeConfigurationError("Sequence d'entree vide: aucune forme a verifier")
    # Le canal ne s'ouvre qu'ICI, une fois le refus de sequence vide passe:
    # une sequence refusee ne doit produire aucun jalon, sans quoi l'ecran
    # afficherait une tache qui a commence alors que rien n'a ete sonde.
    emetteur = progression.EmetteurProgression(rappel_progression, len(frames))
    shapes: dict[tuple[int, int], list[str]] = {}
    for frame in frames:
        shape = probe_frame_size(frame, ffprobe_bin=ffprobe_bin)
        shapes.setdefault(shape, []).append(Path(frame).name)
        # Un jalon **apres** la sonde, et le numerateur est le cardinal REEL
        # de ce qui a ete sonde -- la somme des noms ranges par forme, jamais
        # un compteur de boucle qui divergerait sur une sonde en echec.
        emetteur.emettre(sum(len(noms) for noms in shapes.values()))
    if len(shapes) > 1:
        detail = "; ".join(
            f"{w}x{h}: {len(names)} frame(s), dont {names[0]}"
            for (w, h), names in sorted(shapes.items())
        )
        raise EncodeConfigurationError(
            f"Formes heterogenes dans la sequence d'entree ({detail}). "
            "ffmpeg fige la geometrie sur la premiere frame et redimensionne "
            "les suivantes en silence, sans que le cardinal ne bouge."
        )
    return next(iter(shapes))


def frame_timecodes(frame_paths: Sequence[Path | str]) -> list[str] | None:
    """Rend les timecodes portes par les **noms** des frames, ou ``None``.

    ``None`` signifie "la garde d'ordre n'est pas calculable sur cette
    sequence": il suffit qu'un seul nom ne porte pas de timecode. C'est le cas
    des fixtures de synthese et des artefacts du POC (`frame_0001.png`), jamais
    celui d'une sortie de `extract` ou de `scan`.
    """
    timecodes: list[str] = []
    for frame in frame_paths:
        match = _FRAME_TIMECODE_RE.search(Path(frame).stem)
        if match is None:
            return None
        timecodes.append(match.group(1))
    return timecodes


def ensure_frame_order(frame_paths: Sequence[Path | str]) -> list[str] | None:
    """Refuse une sequence dont les timecodes ne progressent pas.

    L'ancienne API prenait un motif ``frame_%04d.png``: **l'ordre etait impose
    par le demuxeur `image2`**. La nouvelle prend une ``Sequence`` et n'imposait
    plus rien, alors qu'aucune des quatre confrontations de
    ``verify_encoded_output`` -- cardinal, ``pix_fmt``, geometrie, timecode --
    ne depend de l'ordre. Mesure du 2026-08-10 sur les **memes** six frames:
    sequence nominale, melangee, inversee et six fois la meme frame sortent
    toutes en ``rc=0`` avec ``frame_count=6`` et un ``EncodeOutcome`` de
    succes. C'est le seul membre de la famille "un master qui ment sur son
    propre contenu" qui n'avait pas de garde, et la migration naturelle --
    ``glob.glob(dossier + "/*.tiff")`` -- rend l'ordre du **systeme de
    fichiers**, mesure ici comme `05,03,04,06,01,02`.

    La comparaison est **non stricte**, et c'est delibere: deux frames
    consecutives de meme timecode sont une **frame tenue** -- le "shoot on
    twos" du stop-motion, ou chaque dessin est expose deux fois -- et c'est une
    sequence parfaitement valide. Une garde stricte, comme un cardinal
    deduplique, refuserait un master legitime. Ce qui est refuse, c'est une
    **regression** de timecode: melange, inversion, concatenation de deux lots.

    Limite connue et assumee: une sequence qui franchirait `23:59:59:xx`
    reculerait legitimement et serait refusee. Le cas n'existe pas dans ce
    depot -- les lots sont des rushes, pas des journees continues -- et le refus
    serait bruyant, donc corrigible, la ou l'inversion silencieuse ne l'est pas.
    """
    timecodes = frame_timecodes(frame_paths)
    if timecodes is None:
        return None
    for index in range(1, len(timecodes)):
        if timecodes[index] < timecodes[index - 1]:
            previous, current = frame_paths[index - 1], frame_paths[index]
            raise EncodeConfigurationError(
                f"Ordre des frames non monotone entre {Path(previous).name!r} "
                f"({timecodes[index - 1]}) et {Path(current).name!r} ({timecodes[index]}): "
                "la sequence recule dans le temps. Un master melange ou inverse "
                "sort en rc=0 avec le bon cardinal, et rien en aval ne le rattrape."
            )
    return timecodes


def _normalize_frame_paths(frame_paths: Sequence[Path | str]) -> list[Path]:
    """Rend la sequence en ``Path``, en refusant une chaine passee pour une liste.

    Une ``str`` est une ``Sequence`` de caracteres: ``frames='frames/f01.tiff'``
    etait iteree **caractere par caractere**, et l'operateur lisait
    "Frame illisible: 'f'".
    """
    if isinstance(frame_paths, (str, bytes, Path)):
        raise EncodeConfigurationError(
            f"Sequence d'entree attendue (liste de chemins), recu {type(frame_paths).__name__}: "
            f"{frame_paths!r}. Un chemin unique s'ecrit [chemin]."
        )
    return [Path(frame) for frame in frame_paths]


def _reject_duplicate_options(args: Sequence[str], where: str) -> None:
    """Refuse un doublon d'option dans un bloc d'arguments.

    ffmpeg retient le **dernier** (mesure: ``-pix_fmt yuv420p -pix_fmt
    yuv444p`` sort en ``yuv444p``, ``-crf 51 -crf 10`` sort au poids de
    ``-crf 10``), donc l'ordre actuel -- ``extra_args`` en dernier -- est bien
    celui qui fait gagner l'override. Un doublon n'en reste pas moins le
    symptome d'un profil mal ecrit: on le dit au lieu de l'arbitrer.
    """
    seen: set[str] = set()
    for token in args:
        if not token.startswith("-") or token == "-":
            continue
        if token in seen:
            raise EncodeConfigurationError(
                f"Option {token!r} presente deux fois dans {where}: ffmpeg retiendrait "
                "la derniere valeur en silence. Corriger le profil plutot que l'arbitrer."
            )
        seen.add(token)


def _reject_factory_owned_options(args: Sequence[str], where: str) -> None:
    """Refuse une option que la fabrique pose elle-meme du cote sortie.

    ``_reject_duplicate_options`` ne voit qu'un bloc a la fois: un `-vf` place
    dans les ``extra_args`` d'un profil n'y est pas un doublon, et il en devient
    un dans la commande assemblee -- ou ffmpeg retient **le dernier**, donc
    celui du profil. Mesure: `-vf` en doublon sort en `rc=0`, `nb_frames=2`,
    `color_space=bt709`, c'est-a-dire un master **tague bt709 sans avoir subi
    la conversion**. `-r` et `-f` sont repris en main par le module, `-vf` ne
    l'etait pas: c'etait la seule option de sortie qu'un profil pouvait ecraser,
    et la seule dont l'ecrasement soit silencieux.
    """
    for token in args:
        if token in _FACTORY_OWNED_OPTIONS:
            raise EncodeConfigurationError(
                f"Option {token!r} posee par {where}: elle appartient a la fabrique, qui la "
                "pose elle-meme du cote sortie. ffmpeg retiendrait la derniere valeur, donc "
                "celle du profil, et un doublon de -vf produit un master tague sans conversion."
            )


def check_container_tags(container_tags: dict | None) -> dict[str, str]:
    """Valide les tags conteneur, **cle comprise**, et rend le dictionnaire.

    La valeur etait controlee, la cle partait telle quelle. Mesures du
    2026-08-10, toutes en ``rc=0`` et sans un mot:

    ``{'': 'valeur'}`` produit un tag de cle vide; ``{'a=b': 'valeur'}`` est
    **scinde sur le premier `=`** et relu ``{'a': 'b=valeur'}``; une valeur
    portant un saut de ligne forge un **second tag** pour tout consommateur
    lisant la sortie plate de ffprobe (``lot_id=A`` puis ``lot_id=FAUX``); et
    une cle reservee du muxer (``encoder``) est **silencieusement ignoree**, le
    muxer reecrivant la sienne.

    Le dernier cas n'est pas fermable a la construction -- la liste des cles que
    chaque muxer se reserve n'est pas publiee -- il l'est **apres** encodage par
    la confrontation de ``verify_encoded_output``, qui relit les tags du master.
    """
    tags = dict(container_tags or {})
    for key, value in tags.items():
        if not isinstance(key, str) or key == "":
            raise EncodeConfigurationError(
                f"Cle de tag conteneur vide ou non textuelle: {key!r}"
            )
        if "=" in key:
            raise EncodeConfigurationError(
                f"Cle de tag conteneur contenant '=': {key!r}. ffmpeg scinde "
                "'-metadata cle=valeur' sur le premier '=', le tag serait tronque en silence."
            )
        if key != key.strip() or any(character in key for character in "\n\r"):
            raise EncodeConfigurationError(
                f"Cle de tag conteneur mal formee (blancs de bord ou saut de ligne): {key!r}"
            )
        if not isinstance(value, str) or value == "":
            # Une valeur vide produit un fichier ou le tag est simplement absent,
            # rc=0, sans avertissement: indistinguable d'une reinjection ratee.
            raise EncodeConfigurationError(f"Tag conteneur {key!r} vide ou non textuel: {value!r}")
        if any(character in value for character in "\n\r"):
            raise EncodeConfigurationError(
                f"Valeur du tag conteneur {key!r} contenant un saut de ligne: {value!r}. "
                "Elle forgerait un second tag pour tout lecteur de la sortie plate de ffprobe."
            )
    return tags


def check_output_extension(profile: EncodeProfile, output_path: Path | str) -> str:
    """Refuse une extension qui contredit le conteneur du profil, et rend le muxer.

    ``profile.container`` n'etait consulte que pour decider de ``-movflags``:
    mesure, ``h264_delivery -> deliv.mov`` rend rc=0 et ``prores_hq -> m.mkv``
    rend rc=0. Un master ProRes dans un ``.mkv`` est un fichier que la
    post-production refusera sans que rien ne l'ait signale.
    """
    try:
        muxer = CONTAINER_MUXERS[profile.container]
    except KeyError as exc:
        raise EncodeConfigurationError(
            f"Conteneur {profile.container!r} du profil {profile.profile_id!r} sans muxer "
            f"declare. Conteneurs connus: {sorted(CONTAINER_MUXERS)}"
        ) from exc
    suffix = Path(output_path).suffix.lower().lstrip(".")
    if suffix != profile.container:
        raise EncodeConfigurationError(
            f"Extension {'.' + suffix if suffix else '(aucune)'} du chemin de sortie "
            f"{str(output_path)!r} en contradiction avec le conteneur "
            f"{profile.container!r} du profil {profile.profile_id!r}"
        )
    return muxer


def build_encode_command(
    profile_id: str,
    list_path: str,
    fps: float,
    output_path: str,
    *,
    target_size: tuple[int, int] | None = None,
    timecode: str | None = None,
    timecode_base_fps: float | int | str | Fraction | None = None,
    container_tags: dict[str, str] | None = None,
    overwrite: bool = False,
    ffmpeg_bin: str = "ffmpeg",
    progress_target: str | None = None,
) -> list[str]:
    """Rend l'argv ffmpeg complet encodant la sequence decrite par ``list_path``.

    ``list_path`` designe un fichier de liste ``concat`` (voir
    ``concat_list_file``), et non plus un motif ``frame_%04d.png``: aucun
    fichier produit par la chaine v2 n'est atteignable par un ``%0Nd``
    -- ``extract`` ecrit ``<lot_id>_<hh-mm-ss-ff>.tiff``, ``scan`` ecrit
    ``scan_<lot_id>_<hh-mm-ss-ff>.tiff``, timecodes en base source a pas non
    unitaire (mesure sur le dossier reel: ``Could find no file with path ...``).

    Trois points de la commande produite meritent d'etre lus:

    * la cadence d'entree est posee en ``-r`` et non en ``-framerate``:
      l'option ``framerate`` **n'existe pas** sur le demuxeur ``concat``
      (mesure: ``Option framerate not found. Error opening input file``);
    * la **meme** valeur est posee des deux cotes. Le controle de cardinal ne
      vaut que si elles sont egales: mesure, ``-r 25`` en entree et ``-r 50``
      en sortie donnent ``nb_frames=8`` pour une liste de 4;
    * ``timecode_base_fps`` separe la base de validation du timecode de la
      cadence d'encodage. Les lots de ce depot portent un timecode en base
      **source** (``frame_selection.py``), si bien qu'un timecode parfaitement
      legal -- ``00:00:00:14`` sur un lot ``fps_target 12.5`` /
      ``timecode_base_fps 25/1`` -- etait rejete par la fabrique.
      ``validate_timecode`` n'est pas modifiee: elle est canonique et partagee,
      et son comportement est correct -- c'est son appelant qui lui passait la
      mauvaise cadence. (Le compte de modules qui figurait ici a ete retire au
      finding ``P22`` de la revue de la story 6.7: il annoncait six, la mesure
      du 2026-09-03 en trouve deux qui l'importent par son nom. Un nombre
      CORRIGE se reperime; c'est la formulation perissable qui part, pas
      seulement sa valeur -- politique de revue, section 7.)

    Le chemin de sortie est confronte au conteneur du profil, et le muxer qui
    en decoule est pose explicitement en ``-f``: sans lui, un temporaire sans
    extension echoue a 100 %.

    **``overwrite`` est un mecanisme, pas un commentaire.** Cette fonction est
    publique, la story la cite partout, et un script du depot lui passait deja un
    **vrai** chemin de sortie (`scripts/research/codec_metadata_experiment.py`):
    l'hypothese "l'appelant vient de forger ce chemin, ce n'est jamais le
    master" etait donc **deja violee**, dans une story dont le sujet est
    precisement qu'une hypothese non verifiee detruit un master. Deux gestes,
    et non un: le chemin de sortie deja present est **refuse a la construction**
    (``MasterAlreadyExistsError``), et la commande porte ``-n`` -- ffmpeg refuse
    alors d'ecraser, code de retour non nul -- au lieu du ``-y`` inconditionnel.
    ``overwrite=True`` retablit ``-y`` et n'est plus une decision de l'argv mais
    de l'appelant.
    """
    profile = get_profile(profile_id)
    rate = exact_frame_rate(fps)
    muxer = check_output_extension(profile, output_path)
    if target_size is not None:
        check_target_dimensions(profile, *_unpack_target_size(target_size))
    filter_chain = build_filter_chain(profile, target_size)
    tags = check_container_tags(container_tags)

    video_args = profile.ffmpeg_video_args()
    _reject_duplicate_options(video_args, f"les arguments video du profil {profile_id!r}")
    _reject_factory_owned_options(video_args, f"le profil {profile_id!r}")

    if not overwrite and Path(output_path).exists():
        raise MasterAlreadyExistsError(
            f"Le chemin de sortie {str(output_path)!r} existe deja. La fabrique n'ecrase pas "
            "sans qu'on le lui demande: passer overwrite=True, ou viser un chemin libre."
        )
    command = [ffmpeg_bin, "-y" if overwrite else "-n"]
    if progress_target is not None:
        # `-progress` est une option **globale**: elle se pose ici, apres le
        # `-n`/`-y` et avant toute option d'entree, ce qui ne deplace aucun
        # des quatre elements dont la position est mesuree ailleurs -- `-r`
        # d'entree avant `-i`, `-f concat -safe 0` colles a `-i`, `-r` de
        # sortie egal a celui d'entree, `-f <muxer>` juste avant le chemin.
        #
        # `None` laisse l'argv rigoureusement identique a celui d'avant la
        # story 6.7: c'est le repli `AR3`, et il se mesure par egalite de
        # listes, pas par l'absence du seul mot `-progress`.
        command.extend(["-progress", str(progress_target)])
    command.extend([
        "-r", rate,
        "-f", "concat", "-safe", "0",
        "-i", str(list_path),
        "-vf", filter_chain,
    ])
    command.extend(video_args)
    command.extend(["-r", rate])
    if timecode is not None:
        base = fps if timecode_base_fps is None else timecode_base_fps
        command.extend(["-timecode", validate_timecode(timecode, base)])
    for key, value in tags.items():
        command.extend(["-metadata", f"{key}={value}"])
    if tags and profile.container in ("mov", "mp4"):
        # Non-standard keys (rush_id, lot_id, ...) are silently dropped by the
        # mov/mp4 muxers unless this flag is set. Measured: with it, they survive.
        command.append("-movflags")
        command.append("use_metadata_tags")
    command.extend(["-f", muxer, str(output_path)])
    return command


@dataclass(frozen=True)
class EncodeOutcome:
    """Contexte d'un encodage **effectue**, distinct de la description du profil.

    ``EncodeProfile.manifest_fields()`` decrit un profil et ne peut pas
    distinguer deux cadences: le dataclass est gele, il ne porte aucun champ de
    cadence et la methode ne prend aucun argument. Ce qui decrit un *encodage*
    -- cadence effective, geometrie cible, chaine de filtres reellement emise,
    chemin de sortie -- vit donc ici, et c'est ``encode_manifest_fields`` qui le
    rend. C'est cette fonction que la story 6.5 persistera.
    """

    profile_id: str
    output_path: str
    frame_count: int
    frame_rate: str
    source_size: tuple[int, int]
    target_size: tuple[int, int] | None
    encoded_size: tuple[int, int]
    filter_chain: str
    pix_fmt: str
    timecode: str | None = None
    timecode_base: str | None = None
    #: Version du ffmpeg qui a **reellement** produit ce fichier, relevee a
    #: l'encodage par `probe_tool_version`. Portee jusqu'au **rapport de
    #: refus** -- et deliberement PAS au manifeste, voir le commentaire
    #: d'`encode_manifest_fields` (corrige le 2026-09-07, finding `C5` : ce
    #: commentaire disait « jusqu'au manifeste » a dix lignes de celui qui dit
    #: l'inverse, dans le meme fichier) -- parce que
    #: le comportement de tagage colorimetrique differe entre FFmpeg 6 et 8
    #: (`FFMPEG_COLOR_TAGGING_MEASUREMENT`): sans elle, un master mal tague ne
    #: dit pas sous quoi il a ete fabrique, et le diagnostic recommence a zero.
    #: Vaut `TOOL_VERSION_UNKNOWN` si le releve a echoue -- jamais une exception.
    ffmpeg_version: str = TOOL_VERSION_UNKNOWN


def encode_manifest_fields(outcome: EncodeOutcome) -> dict:
    """Rend la description manifest d'un **encodage**, profil compris."""
    profile = get_profile(outcome.profile_id)
    fields = dict(profile.manifest_fields())
    fields.update(
        {
            "frame_rate": outcome.frame_rate,
            "frame_count": outcome.frame_count,
            "source_resolution": f"{outcome.source_size[0]}x{outcome.source_size[1]}",
            "target_resolution": (
                None if outcome.target_size is None
                else f"{outcome.target_size[0]}x{outcome.target_size[1]}"
            ),
            "encoded_resolution": f"{outcome.encoded_size[0]}x{outcome.encoded_size[1]}",
            "filter_chain": outcome.filter_chain,
            "pix_fmt": outcome.pix_fmt,
            "output_path": outcome.output_path,
            "timecode": outcome.timecode,
            "timecode_base": outcome.timecode_base,
        }
    )
    # **La version de ffmpeg n'entre PAS dans cette description, et c'est
    # mesure plutot que suppose** (2026-09-06). L'y mettre etait le geste
    # naturel -- un master est une mesure de comportement produit, donc il
    # devrait nommer l'outil qui l'a prise. Mais cette description est rendue
    # verbatim par `mmu encode`, et le dossier d'identite de
    # `tests/unit/test_encode_noyau.py` la gele a l'octet sur 25 invocations:
    # y poser une valeur qui **change d'une machine a l'autre** rendrait ce
    # temoin de reproductibilite faux partout ailleurs que sur la machine qui
    # l'a engendre. Le releve vit donc sur `EncodeOutcome.ffmpeg_version`, ou
    # tout appelant peut le lire, et il est nomme la ou il sert reellement au
    # diagnostic: le rapport de `VERIFICATION_TECHNIQUE_EN_ECHEC`.
    return fields


def verify_encoded_output(
    video_path: Path | str,
    *,
    profile: EncodeProfile,
    expected_frames: int,
    expected_size: tuple[int, int] | None = None,
    expected_timecode: str | None = None,
    expected_tags: dict[str, str] | None = None,
    ffprobe_bin: str = "ffprobe",
) -> tuple[int, int, str]:
    """Confronte le fichier produit a ce qui a ete demande.

    Rend ``(largeur, hauteur, pix_fmt)`` et leve ``EncodeVerificationError``
    sur toute divergence. Deux modes de panne silencieux sont vises:

    * **la troncature**. Changer de demuxeur regle l'adressage des noms, pas la
      troncature: mesure, une liste de 2 entrees dont la seconde a disparu du
      disque sort en ``rc=0`` avec ``nb_frames=1``, exactement comme
      ``image2``. Ce controle est la **seule** protection;
    * **l'auto-negociation du format de pixel**. Un ``pix_fmt`` incompatible
      est absorbe en silence: mesure, ``prores_ks`` avec ``-pix_fmt yuv420p``
      sort en ``rc=0``, ``yuv422p10le``, avec un simple ``Incompatible pixel
      format ... auto-selecting format`` sur stderr;
    * **la reinterpretation du timecode**. Mesure du 2026-08-10, non prevue par
      la story: ffmpeg ne recopie pas la chaine de ``-timecode``, il la
      convertit en numero de frame puis la re-rend **a la cadence de sortie**.
      ``-timecode 00:00:00:14`` a ``-r 25/2`` produit donc un master dont le
      ``tmcd`` vaut ``00:00:01:01``, avec ``rc=0`` et sans un mot. Separer la
      base de validation de la cadence d'encodage (AC 14) rend le timecode de
      base source *acceptable* a la construction, mais ne le rend pas *juste*
      dans le conteneur: la conversion de base est une decision qui appartient
      a la story 6.1. Ici, on refuse simplement de livrer un master qui ment.
      Correction du 2026-08-10: la confrontation porte sur l'**image designee**
      (``timecodes_equivalent``) et non sur la chaine, parce que ffmpeg ecrit
      ``ff`` sur ``len(str(ceil(cadence) - 1))`` chiffres et non sur deux --
      ``00:00:00:4`` a 5 im/s est le **meme** timecode que le ``00:00:00:04``
      demande. Comparer les chaines refusait un master juste a 1, 5, 10 et 120
      im/s, c'est-a-dire sur trois des cinq cadences reelles du projet.
    * **la disparition d'un tag conteneur**. Les cles non standard sont
      "silently dropped" par les muxers mov/mp4 sans ``-movflags
      use_metadata_tags``, et une cle que le muxer se reserve (mesure:
      ``encoder``) est ignoree **meme avec** le drapeau: relu ``{}``, ``rc=0``,
      aucun signal. Le drapeau etait pose sans que rien ne verifie qu'il serve:
      s'il disparaissait, personne ne le verrait.

    Une divergence est une **erreur typee**, jamais un avertissement.
    """
    # Import differe: `video_metadata` importe `codec_profiles` au chargement,
    # un import de module a module serait circulaire.
    from . import video_metadata

    probe = video_metadata.probe_media(str(video_path), ffprobe_bin=ffprobe_bin)
    stream = None
    for candidate in probe.get("streams", []):
        if candidate.get("codec_type") == "video":
            stream = candidate
            break
    if stream is None:
        raise EncodeVerificationError(f"Aucun flux video dans {str(video_path)!r}")

    # Un seul chemin de refus pour "absent" et "illisible": `int(None)` leve
    # deja `TypeError`, donc la branche `raw_count is None` qui precedait etait
    # **redondante** avec l'`except` qui la suivait -- seul le libelle changeait,
    # et aucun test ne pouvait les distinguer. Un mutant equivalent se retire.
    raw_count = stream.get("nb_frames")
    try:
        frame_count = int(raw_count)
    except (TypeError, ValueError) as exc:
        raise EncodeVerificationError(
            f"Cardinal absent ou illisible dans {str(video_path)!r}: {raw_count!r}. "
            "La troncature ne peut pas etre exclue."
        ) from exc
    if frame_count != expected_frames:
        raise EncodeVerificationError(
            f"Cardinal encode {frame_count} != cardinal attendu {expected_frames} pour "
            f"{str(video_path)!r}. ffmpeg a rendu un succes sur une sequence tronquee."
        )

    pix_fmt = stream.get("pix_fmt")
    if pix_fmt != profile.pix_fmt:
        raise EncodeVerificationError(
            f"Format de pixel obtenu {pix_fmt!r} != format demande {profile.pix_fmt!r} "
            f"pour le profil {profile.profile_id!r}: ffmpeg a auto-negocie en silence."
        )

    width, height = int(stream.get("width", 0)), int(stream.get("height", 0))
    if expected_size is not None and (width, height) != tuple(expected_size):
        raise EncodeVerificationError(
            f"Geometrie obtenue {width}x{height} != geometrie attendue "
            f"{expected_size[0]}x{expected_size[1]} pour {str(video_path)!r}"
        )

    if expected_timecode is not None:
        # On reprend la recherche canonique de `video_metadata` plutot que d'en
        # ecrire une seconde: mov/mp4 posent le timecode sur les tags d'un
        # flux, MXF au niveau format, Matroska en majuscules.
        actual_timecode = video_metadata._find_timecode(probe)
        # Confrontation sur l'**image designee**, pas sur la chaine. Correction
        # du 2026-08-10: ffmpeg n'ecrit pas `ff` sur une largeur fixe (voir
        # `timecode_frame_field_width`), si bien que comparer les chaines
        # declarait non conforme un master parfaitement juste des que
        # `ceil(cadence)` sortait de la fenetre 11..100 -- soit trois des cinq
        # cadences reelles de ce depot. Un vrai desaccord reste detecte: seule
        # la largeur d'ecriture est absorbee, les cinq champs sont compares.
        if not timecodes_equivalent(actual_timecode, expected_timecode):
            raise EncodeVerificationError(
                f"Timecode obtenu {actual_timecode!r} != timecode demande "
                f"{expected_timecode!r} pour {str(video_path)!r}: ffmpeg re-rend "
                "la valeur de -timecode a la cadence de sortie. Convertir le "
                "timecode dans la base du master est une decision de cadrage "
                "(story 6.1), pas une correction a faire ici. La comparaison "
                "porte sur l'image designee et non sur la chaine: une simple "
                "difference de largeur du champ frames n'est pas ce refus."
            )

    if expected_tags:
        written = (probe.get("format") or {}).get("tags") or {}
        divergent = {
            key: written.get(key)
            for key, value in expected_tags.items()
            if written.get(key) != value
        }
        if divergent:
            raise EncodeVerificationError(
                f"Tags conteneur absents ou divergents dans {str(video_path)!r}: "
                f"{divergent!r} au lieu de "
                f"{ {key: expected_tags[key] for key in divergent} !r}. "
                "Le muxer se reserve certaines cles et les ignore en silence."
            )
    return width, height, pix_fmt


def _reserve_output_path(output_path: Path) -> None:
    """Reserve **atomiquement** le chemin de sortie, ou refuse.

    ``Path.exists()`` suivi d'un ``os.replace`` est un TOCTOU, et il n'etait pas
    theorique: mesure du 2026-08-10, quatre ``run_encode`` concurrents en
    ``overwrite=False`` vers la meme cible rendent **quatre** ``EncodeOutcome``
    de succes, un seul master survit, et **aucun** appelant ne recoit
    ``MasterAlreadyExistsError``. Trois masters disparaissent avec un rapport de
    succes -- deux jobs sur la meme sortie, c'est la relance manuelle pendant un
    batch, situation que le `CLAUDE.md` decrit comme ordinaire.

    ``O_CREAT | O_EXCL`` ferme la fenetre: la creation et le test d'existence
    sont le meme appel systeme. Le fichier vide ainsi pose est ensuite ecrase par
    l'``os.replace`` final, et retire par le ``finally`` si l'encodage echoue.

    Ce qu'elle ne ferme pas, et il faut le dire: elle protege les appelants en
    ``overwrite=False`` les uns des autres. Un appelant en ``overwrite=True``
    ecrase par definition, et deux d'entre eux sur la meme cible restent une
    course -- gagnee par le dernier, ce qui est le contrat demande.
    """
    try:
        handle = os.open(output_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError as exc:
        raise MasterAlreadyExistsError(
            f"Le master {str(output_path)!r} existe deja. Relancer avec --overwrite "
            "pour l'ecraser explicitement."
        ) from exc
    except OSError as exc:
        raise EncodeConfigurationError(
            f"Chemin de sortie inutilisable: {str(output_path)!r} ({exc})"
        ) from exc
    os.close(handle)


def sweep_encode_residues(
    directory: Path | str, *, max_age_seconds: float = 86400.0
) -> list[Path]:
    """Retire les residus laisses par un encodage **tue**, et rend leur liste.

    Precision qui corrige deux docstrings de ce module: "reussite, echec ou
    interruption, aucun residu" est vrai pour une exception et pour ``SIGINT``
    (mesure: ``rc=130``, zero residu), et **faux pour ``SIGTERM``** -- le signal
    par defaut d'un ``kill``, d'un ``docker stop`` ou d'un ordonnanceur -- comme
    pour ``SIGKILL``: mesure ``rc=143`` et ``rc=137``, deux residus a chaque
    fois, un temporaire de master et un fichier de liste.

    Le point qui rend le balayage necessaire plutot que cosmetique: ces residus
    sont des fichiers **caches** portant l'extension du conteneur, invisibles a
    ``ls`` dans le dossier des masters, de la taille d'un master partiel -- et
    ``Path.glob('*.mov')`` **les matche** (mesure), la ou ``glob.glob`` ne les
    matche pas. Or le depot emploie ``Path.glob`` et ``iterdir`` partout
    (`ffmpeg_utils.py`, `extraction.py`, `detection/aruco.py`). Un temporaire
    perime est donc, pour tout inventaire du depot, un master.

    Le balayage n'est **pas** automatique: un temporaire vivant appartient a un
    autre encodage en cours. D'ou le seuil d'age, large par defaut (24 h), que
    l'appelant resserre s'il sait qu'aucun encodage ne tourne.
    """
    directory = Path(directory)
    if not directory.is_dir():
        return []
    cutoff = time.time() - max_age_seconds
    removed: list[Path] = []
    for candidate in directory.iterdir():
        if not candidate.name.startswith(".") or not candidate.is_file():
            continue
        if _TEMP_NAME_RE.search(candidate.name) is None:
            continue
        try:
            if candidate.stat().st_mtime > cutoff:
                continue
            candidate.unlink()
        except OSError:
            continue
        removed.append(candidate)
    return removed


def _compter_sur_le_flux(flux, emetteur) -> None:
    """Emettre un jalon par ligne ``frame=<n>`` du flux ``-progress``.

    **La lecture va toujours jusqu'au bout du flux**, meme quand elle cesse de
    comprendre ce qu'elle lit. Cesser de lire un tube qu'un sous-processus
    remplit encore le bloquerait des que le tampon est plein (64 Kio) -- c'est
    le defaut exact que le depot a deja paye sur ``stderr``, et il serait ici
    d'autant plus vicieux que le flux ``-progress`` d'un encodage de trente
    minutes pese quelque 700 Kio, soit dix fois la borne.

    **La tolerance au format n'est pas ici, elle est dans l'emetteur.**
    ``EmetteurProgression.emettre`` fait lui-meme ``int(faites)`` sous garde:
    ``N/A``, une valeur vide ou un flottant ne produisent aucun jalon et ne
    levent rien. Ce module ne reimplemente donc aucune conversion -- il passe
    la valeur telle qu'elle a ete lue.

    **Ce que l'absorption NE couvre PAS, et le mecanisme n'est pas ici.** Un
    arret demande -- ``SIGTERM`` par ``TerminaisonDemandee``, ``Ctrl-C`` par
    ``KeyboardInterrupt`` -- traverse intact, parce que les deux derivent de
    ``BaseException``: aucun ``except Exception``, ni celui-ci, ni celui du
    vidage, ni celui d'``EmetteurProgression.emettre`` en amont, ne les voit
    passer. C'est la seconde moitie d'``EPIC7-ARB-79``, et elle est tenue par
    une CLASSE DE BASE plutot que par une garde par site.

    La difference n'est pas theorique et elle a ete mesuree: une garde posee
    ici seule fermait ce site et laissait ouverte la fenetre du **rappel**, ou
    l'arret restait avale. Le motif complet, avec ses deux mesures, vit sur
    ``encode_master.TerminaisonDemandee``.
    """
    if flux is None:
        return
    try:
        for ligne in flux:
            cle, separateur, valeur = ligne.partition("=")
            if separateur and cle.strip() == PROGRESS_FRAME_KEY:
                emetteur.emettre(valeur.strip())
    except Exception:  # noqa: BLE001 -- l'observation ne casse jamais l'observe
        _JOURNAL.warning(
            "La lecture du flux de progression de ffmpeg a leve; les jalons "
            "sont abandonnes et l'encodage se poursuit.",
            exc_info=True,
        )
        # Vider le tube sans plus l'analyser: voir la docstring. L'absorption
        # est large -- si meme le vidage leve, le tube est rompu et il n'y a
        # plus rien a vider -- et elle s'arrete a la meme frontiere que
        # ci-dessus, sans avoir a la redire: un `SIGTERM` recu PENDANT le
        # vidage derive de `BaseException`, donc ce `suppress` ne le voit pas
        # plus que le `except` du dessus.
        with contextlib.suppress(Exception):
            for _ligne in flux:
                pass


def _executer_ffmpeg_en_comptant(command, *, emetteur=None) -> tuple[int, str]:
    """Executer ``command`` en comptant les frames que ffmpeg declare encodees.

    Rend ``(returncode, stderr)``. C'est la **couture** de la story 6.7: elle
    est appelable seule, donc mesurable avec un faux binaire lance par
    ``sys.executable``, sans vrai ffmpeg ni ``ensure_encoder_available``.
    Le modele litteral est ``ffmpeg_utils.run_with_written_file_progress``.

    **Deux branches.** Sans emetteur actif -- c'est-a-dire la ligne de
    commande, seul chemin en production aujourd'hui -- la couture reprend
    **exactement** le geste d'avant la story: ``subprocess.run(command,
    capture_output=True, encoding="utf-8", errors="replace")``. Le repli
    ``AR3`` n'acquiert ainsi aucune dependance neuve, en particulier pas au
    repertoire temporaire systeme, et l'argv qu'il recoit ne porte meme pas
    ``-progress``.

    **``stderr`` va dans un fichier, jamais dans un tube.** Deux tubes lus l'un
    apres l'autre se bloquent mutuellement: le processus attend qu'on lise
    celui qu'on ne lit pas. Le fichier supprime le tube, donc le blocage, et
    le texte relu est identique au caractere pres a celui que
    ``capture_output=True`` rend sur l'autre branche -- c'est ce qui permet aux
    deux ``EncodeRunError`` d'etre litteralement les memes des deux cotes.

    **Aucun plafond de duree, et c'est une AC.** Un master 4K prend
    legitimement des dizaines de minutes; un ``timeout`` introduit ici
    romprait un encodage valide. La sortie de boucle est l'EOF du flux de
    progression, que ffmpeg ferme en terminant.

    Aucun fil n'est cree: la lecture du flux **est** l'attente, et le
    ``finally`` garantit qu'aucun processus ne survit a l'appel, y compris
    apres une interruption clavier.
    """
    if emetteur is None or not emetteur.actif:
        resultat = subprocess.run(
            command, capture_output=True, encoding="utf-8", errors="replace"
        )
        return resultat.returncode, resultat.stderr or ""

    descripteur, stderr_path = tempfile.mkstemp(prefix="mmu_encode_", suffix=".stderr")
    os.close(descripteur)
    try:
        with open(stderr_path, "wb") as flux_erreur:
            processus = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=flux_erreur,
                encoding="utf-8",
                errors="replace",
            )
            try:
                _compter_sur_le_flux(processus.stdout, emetteur)
                processus.wait()
            finally:
                # Jamais de processus laisse vivant, meme si la lecture a ete
                # quittee par une exception (interruption clavier comprise).
                if processus.stdout is not None:
                    with contextlib.suppress(OSError, ValueError):
                        processus.stdout.close()
                if processus.poll() is None:
                    processus.kill()
                    processus.wait()
        return processus.returncode, Path(stderr_path).read_text(
            encoding="utf-8", errors="replace")
    finally:
        with contextlib.suppress(OSError):
            os.unlink(stderr_path)


def run_encode(
    profile_id: str,
    frame_paths: Sequence[Path | str],
    fps: float,
    output_path: Path | str,
    *,
    target_size: tuple[int, int] | None = None,
    timecode: str | None = None,
    timecode_base_fps: float | int | str | Fraction | None = None,
    container_tags: dict[str, str] | None = None,
    overwrite: bool = False,
    ffmpeg_bin: str = "ffmpeg",
    ffprobe_bin: str = "ffprobe",
    rappel_progression=None,
) -> EncodeOutcome:
    """Encode ``frame_paths`` vers ``output_path`` sans jamais detruire l'existant.

    ffmpeg tronque sa sortie **avant** d'ouvrir l'encodeur: mesure, un master
    valide de 11340 octets re-encode par une commande invalide vers le meme
    chemin sort en ``rc=187`` et laisse un master a **0 octet**. Le geste repris
    est celui du depot (``pdf_render``, ``io/extraction_manifest._atomic_write``):
    temporaire puis ``os.replace``, avec les corrections mesurees de la story --
    extension du conteneur conservee **et** ``-f`` explicite, temporaire dans le
    dossier de destination, nom plus discriminant que le PID, suppression en
    ``finally``.

    Le controle de cardinal porte sur le **temporaire, avant bascule**: sur le
    chemin final il leverait son erreur alors que le master tronque a deja
    ecrase le precedent, ce qui annulerait la protection dans le seul cas ou
    elle sert.

    Le cardinal attendu est ``len(frames)`` et **jamais** un cardinal deduplique:
    deux frames consecutives identiques sont une **frame tenue**, le "shoot on
    twos" du stop-motion, et une sequence parfaitement valide.

    Deux refus protegent la destination, et ils ne font pas double emploi: un
    ``exists()`` precoce, qui est une **courtoisie** -- il evite de sonder mille
    frames pour rien -- et une **reservation atomique** juste avant l'encodage,
    qui est la garantie. Seule la seconde ferme la course entre deux encodages
    concurrents.
    """
    profile = get_profile(profile_id)
    frames = _normalize_frame_paths(frame_paths)
    output_path = Path(output_path)
    check_output_extension(profile, output_path)
    if output_path.is_dir():
        raise EncodeConfigurationError(
            f"Le chemin de sortie {str(output_path)!r} est un repertoire: la bascule finale "
            "leverait un IsADirectoryError nu, hors de la hierarchie d'erreurs du module."
        )
    if output_path.exists() and not overwrite:
        # Refus courtois et **non atomique**: il epargne la sonde de toutes les
        # frames. La garantie, elle, est la reservation posee plus bas.
        #
        # UNE SEULE ISSUE, ET C'EST DELIBERE (arbitrage d'Egan, 2026-08-31).
        # Ce refus n'est pas un dialogue avec l'operateur: la commande a deja
        # verifie la destination a son entree et lui a propose TROIS issues
        # (`encode.check_output_destination`). Celui-ci ne se declenche que si
        # le fichier est apparu DEPUIS -- c'est-a-dire si un autre encodage
        # s'est glisse dans l'intervalle, parfois plusieurs minutes d'analyse.
        #
        # Dans ce cas la bonne reponse est « recommencez », et non un menu: le
        # rang de version resolu au debut de la commande n'est plus fiable,
        # puisque quelqu'un vient de le consommer. Lui donner trois issues
        # ferait proposer un rang qui pourrait etre pris a son tour.
        #
        # Ce commentaire existe pour qu'une revue future ne rouvre pas ce site
        # comme un oubli: il est recense dans `DETTES_CONNUES` de
        # `test_conformite_sorties_nommees.py`, et le motif de sa presence y
        # est desormais nomme.
        raise MasterAlreadyExistsError(
            f"Le master {str(output_path)!r} existe deja. Relancer avec --overwrite "
            "pour l'ecraser explicitement."
        )
    ensure_encoder_available(profile, ffmpeg_bin)

    # Refuse aussi la sequence vide: la garde vivait a trois endroits, dont deux
    # ne pouvaient jamais etre atteints en second. Un mutant equivalent se retire.
    # Le canal descend a la garde de forme, qui est la phase la plus longue
    # AVANT l'encodage lui-meme (~76 ms par frame, un ffprobe chacune) et la
    # seule dont le cardinal soit connu d'avance (story 6.7).
    source_size = ensure_uniform_frame_shapes(
        frames, ffprobe_bin=ffprobe_bin, rappel_progression=rappel_progression)
    ensure_frame_order(frames)
    encoded_size = (
        _unpack_target_size(target_size) if target_size is not None else source_size
    )
    check_target_dimensions(profile, *encoded_size)
    expected_tags = check_container_tags(container_tags)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    reserved = not overwrite
    if reserved:
        _reserve_output_path(output_path)
    replaced = False
    temp_output = _unique_sibling(output_path, f".{profile.container}")
    # UN SECOND emetteur, et non celui de la sonde de formes. Les deux phases
    # comptent chacune `len(frames)`: un emetteur partage ferait tomber en
    # silence tous les jalons de l'encodage -- ils seraient `<= dernier` --
    # et la barre se figerait pendant la phase longue. La barre est PAR ETAPE
    # dans le dessin de `E4-4`, donc le compteur repart, et c'est voulu.
    emetteur_encodage = progression.EmetteurProgression(
        rappel_progression, len(frames))
    try:
        with concat_list_file(frames, output_path.parent) as list_path:
            command = build_encode_command(
                profile_id,
                str(list_path),
                fps,
                str(temp_output),
                target_size=target_size,
                timecode=timecode,
                timecode_base_fps=timecode_base_fps,
                container_tags=container_tags,
                ffmpeg_bin=ffmpeg_bin,
                # L'argv du repli `AR3` reste celui d'avant la story, au
                # jeton pres: l'option n'apparait que si quelqu'un ecoute.
                progress_target=(PROGRESS_TARGET_STDOUT
                                 if emetteur_encodage.actif else None),
            )
            # Le processus est attendu DANS le `with`: le fichier de liste
            # `concat` doit vivre pendant toute la duree de l'encodage, et non
            # jusqu'au lancement seulement.
            returncode, stderr = _executer_ffmpeg_en_comptant(
                command, emetteur=emetteur_encodage)
        if returncode != 0:
            raise EncodeRunError(
                f"ffmpeg a echoue (code {returncode}) sur le profil {profile_id!r}: "
                f"{(stderr or '').strip()[-600:]}"
            )
        if not temp_output.exists():
            # Mesure du 2026-08-10, non prevue: `-n` devant un fichier deja
            # present rend **rc=0** ("File ... already exists. Exiting."), sans
            # rien encoder. Un code de retour nul ne prouve donc pas qu'un
            # fichier a ete produit, et sans ce controle la suite partirait
            # sonder un fichier absent -- en levant une erreur de `ffprobe`,
            # hors de la hierarchie de ce module.
            raise EncodeRunError(
                f"ffmpeg a rendu 0 sans produire {str(temp_output)!r} sur le profil "
                f"{profile_id!r}: {(stderr or '').strip()[-600:]}"
            )
        width, height, pix_fmt = verify_encoded_output(
            temp_output,
            profile=profile,
            expected_frames=len(frames),
            expected_size=encoded_size,
            expected_timecode=timecode,
            expected_tags=expected_tags,
            ffprobe_bin=ffprobe_bin,
        )
        os.replace(temp_output, output_path)
        replaced = True
    finally:
        # Le nettoyage ne doit **jamais** remplacer l'erreur typee en cours: un
        # `unlink` peut lever (ENAMETOOLONG mesure a partir de 233 caracteres de
        # nom, EPERM, systeme de fichiers en lecture seule), et l'OSError qui
        # remontait alors n'etait pas un `EncodeError` -- tout appelant ecrit en
        # `except EncodeError` la manquait.
        with contextlib.suppress(OSError):
            Path(temp_output).unlink(missing_ok=True)
        if reserved and not replaced:
            # La reservation est un fichier vide pose la ou il n'y avait rien:
            # la retirer ne peut donc pas detruire un master preexistant.
            with contextlib.suppress(OSError):
                output_path.unlink(missing_ok=True)

    base = fps if timecode_base_fps is None else timecode_base_fps
    return EncodeOutcome(
        profile_id=profile_id,
        output_path=str(output_path),
        frame_count=len(frames),
        frame_rate=exact_frame_rate(fps),
        source_size=source_size,
        target_size=None if target_size is None else tuple(target_size),
        encoded_size=(width, height),
        filter_chain=build_filter_chain(profile, target_size),
        pix_fmt=pix_fmt,
        timecode=timecode,
        timecode_base=None if timecode is None else exact_frame_rate(base),
        # Releve du binaire **qui vient d'encoder**, pas d'un `ffmpeg` du PATH
        # suppose: `ffmpeg_bin` est celui que `build_encode_command` a employe.
        ffmpeg_version=probe_tool_version(ffmpeg_bin),
    )
