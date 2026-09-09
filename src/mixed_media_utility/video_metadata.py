"""Technical video metadata reinjection/verification matrix (story 6.3).

The manifest stays the sole business source of truth (calibration, provenance,
full page/slot/timecode mapping, checksums, reconstruction history — see
ARCHITECTURE_DETAILED.md section 11, transcribed executably in
``io/metadata_matrix.py``). This module only covers the narrow set of
*technical* fields realistically preservable in the final video container,
plus the helpers to write them (``codec_profiles.build_encode_command``) and
read them back through ``ffprobe``.

ffmpeg/ffprobe version measured for this module: 6.1.1, re-measured against
8.1.2 on 2026-09-06. The behaviors below are muxer-specific, not permanent spec
facts, and are re-verified by real encode + ffprobe tests in
``tests/unit/test_video_metadata.py``:

**Cette declaration de version n'etait adossee a aucun releve d'execution, et
ca s'est paye.** Le 2026-09-06, un master produit sous FFmpeg 8 est sorti en
``color_space=bt709`` avec ``color_primaries`` et ``color_transfer`` non
renseignes -- ``-color_primaries`` et ``-color_trc`` n'atteignent plus
l'encodeur sur cette ligne-la. La garde de ce module a **eu raison** de le
refuser (le fichier etait reellement mal tague), mais son rapport ne nommait
aucune version, donc il ne designait pas la cause. Le correctif vit dans
``codec_profiles.build_setparams_link``, la mesure complete dans
``codec_profiles.FFMPEG_COLOR_TAGGING_MEASUREMENT``, et le releve de version
est porte au **rapport de refus** par ``codec_profiles.probe_tool_version``.

**Il ne va PAS au manifeste, et c'est delibere** (corrige le 2026-09-07, sur
finding de la couche 3 : ces lignes disaient l'inverse du code du meme commit).
``encode_manifest_fields`` est gelee a l'octet par le dossier d'identite
d'``encode``, qui rend la description de ``mmu encode`` verbatim : y poser une
valeur qui change de machine rendrait ce temoin de reproductibilite faux
partout ailleurs. Un agent qui lirait ici que le champ devrait y etre, et qui
l'ajouterait, ferait rougir onze scenarios d'identite.

- MOV/ProRes (``prores_ks``) only writes a usable ``colr`` atom when
  ``-colorspace``, ``-color_primaries`` and ``-color_trc`` are set *together*;
  ``-colorspace`` alone is silently insufficient, unlike libx264/libx265/dnxhd.
  ffprobe also omits "unknown" color fields from its JSON entirely rather than
  reporting them, so a naive ``.get()`` cannot tell "untagged" from "absent".
- ``-timecode`` writes a real ``tmcd`` data stream in MOV **and** MP4. Where
  it lands differs by container though: mov/mp4 expose it on the video
  stream's tags, MXF and Matroska only at format level (and Matroska
  upper-cases the key), so it must be looked up across all three locations.
- ProRes emits no ``color_range`` at all while DNxHR/H.264/H.265 emit ``tv``;
  the default mezzanine master therefore ships unsignalled, which is the
  classic full/legal shift on NLE import. Recorded here as a known gap.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from fractions import Fraction

from . import codec_profiles
from .codec_profiles import exact_frame_rate, validate_timecode  # re-exported
from .io import metadata_matrix as _metadata_matrix

__all__ = [
    "FfprobeNotFoundError",
    "FfprobeError",
    "MetadataVerificationError",
    "TECHNICAL_METADATA_MATRIX",
    "MANDATORY_TECHNICAL_FIELDS",
    "MANIFEST_ONLY_FIELDS",
    "MUXER_IMPOSED_FIELDS",
    "probe_media",
    "read_technical_metadata",
    "verify_technical_metadata",
    "supported_profiles",
    "exact_frame_rate",
    "validate_timecode",
]

FFPROBE_TIMEOUT_SECONDS = 60


class FfprobeNotFoundError(RuntimeError):
    """Raised when the ``ffprobe`` binary cannot be found on PATH."""


class FfprobeError(RuntimeError):
    """Raised when ``ffprobe`` fails on a file (missing, empty, corrupt, ...).

    Wraps ``CalledProcessError``, whose message drops the captured stderr and
    therefore says nothing about *why* the probe failed.
    """


class MetadataVerificationError(RuntimeError):
    """Raised when a verification request is itself invalid (unknown field,
    or a check that would pass without reading anything)."""


_ALL_PROFILES = tuple(codec_profiles.PROFILES)
_MOV_MASTERS = tuple(
    profile_id
    for profile_id, profile in codec_profiles.PROFILES.items()
    if profile.category == "primary" or profile.vcodec in ("prores_ks", "dnxhd")
)


def _entry(
    *,
    mode: str,
    probe_key: str,
    supported: tuple[str, ...] = _ALL_PROFILES,
    reliability: str = "reliable",
    comparison: str = "exact",
    note: str = "",
    **extra,
) -> dict:
    """Build one matrix row.

    ``reliability`` is filled for **every** profile of the catalog, and
    ``supported`` is derived from ``codec_profiles.PROFILES`` rather than
    retyped: the previous matrix hard-coded the profile tuple eight times and
    carried ``reliability`` on a single row, so adding a profile in story 6.2
    silently marked every field unsupported and generic code raised KeyError
    on seven rows out of eight.
    """
    unknown = set(supported) - set(_ALL_PROFILES)
    if unknown:
        raise AssertionError(f"Profils inconnus dans la matrice 6.3: {sorted(unknown)}")
    return {
        "mode": mode,
        "probe_key": probe_key,
        "supported_profiles": tuple(supported),
        "reliability": {
            profile_id: (reliability if profile_id in supported else "unsupported")
            for profile_id in _ALL_PROFILES
        },
        "comparison": comparison,
        "note": note,
        **extra,
    }


# Technical field -> how it reaches the container and how it is read back.
# "container-native": implicit stream property, not injected as a tag.
# "reinjectable": written by build_encode_command, read back with ffprobe.
TECHNICAL_METADATA_MATRIX: dict[str, dict] = {
    "codec": _entry(
        mode="container-native",
        probe_key="codec_name",
        note="Exige par l'epic et classe obligatoire par ARCHITECTURE_DETAILED §5.",
    ),
    "resolution": _entry(mode="container-native", probe_key="resolution"),
    "frame_rate": _entry(
        mode="container-native",
        probe_key="r_frame_rate",
        comparison="rational",
        note="ffprobe renvoie un rationnel; comparaison via Fraction, pas str().",
    ),
    "pixel_format": _entry(mode="container-native", probe_key="pix_fmt"),
    "color_primaries": _entry(
        mode="reinjectable", probe_key="color_primaries", requires_all_three_color_flags=True
    ),
    "color_transfer": _entry(
        mode="reinjectable", probe_key="color_transfer", requires_all_three_color_flags=True
    ),
    "colorspace": _entry(
        mode="reinjectable", probe_key="color_space", requires_all_three_color_flags=True
    ),
    "color_range": _entry(
        mode="container-native",
        probe_key="color_range",
        supported=tuple(p for p in _ALL_PROFILES if p not in ("prores_hq", "prores_422", "prores_lt")),
        note=(
            "Mesure: ProRes n'emet aucune signalisation de plage, DNxHR/H264/HEVC "
            "emettent 'tv'. Ecart full/legal a l'import NLE: connu, non corrige ici."
        ),
    ),
    "timecode": _entry(
        mode="reinjectable",
        probe_key="timecode",
        supported=_MOV_MASTERS,
        comparison="timecode",
        note=(
            "Ecrit par build_encode_command(timecode=...). ffmpeg cree un vrai flux "
            "tmcd en MOV comme en MP4, mais seul MOV+tmcd est la convention lue "
            "nativement par Premiere/Resolve/Avid; les derives MP4 restent "
            "'best_effort' (voir RELIABILITY_OVERRIDES) et ne doivent pas etre "
            "promis en doc utilisateur sans validation NLE reelle."
        ),
    ),
}

# The single place that says what "best effort" means, so a consumer filtering
# on supported_profiles and one reading reliability can no longer disagree:
# writing a timecode on an MP4 derivative is allowed and works in ffmpeg, it is
# only its third-party readability that is unproven.
TECHNICAL_METADATA_MATRIX["timecode"]["reliability"].update(
    {
        profile_id: "best_effort"
        for profile_id in _ALL_PROFILES
        if profile_id not in _MOV_MASTERS
    }
)
TECHNICAL_METADATA_MATRIX["timecode"]["supported_profiles"] = _ALL_PROFILES

# Fields whose absence from a verification request makes the result vacuous.
MANDATORY_TECHNICAL_FIELDS = ("codec", "resolution", "frame_rate", "pixel_format")

# Chosen by the muxer, not by us: 1/12288 at 24 fps, 1/12800 at 25 fps, 1/24 in
# MXF, with no link to the source. Verifying it proves nothing, so it is
# documented as out of scope instead of padding the matrix.
MUXER_IMPOSED_FIELDS = ("time_base",)

# Business fields that must never be *read back* from the container as truth.
# The classification is taken from io/metadata_matrix (story 2.4, the executable
# transcription of ARCHITECTURE_DETAILED §5) rather than re-invented: this
# module used to declare project_id/rush_id "never reliable" while the
# authoritative matrix classifies them OPTIONAL in the video container, and a
# test locked the contradiction in.
CONTAINER_OPTIONAL_BUSINESS_FIELDS = tuple(
    field
    for field in _metadata_matrix.known_fields()
    if _metadata_matrix.is_allowed(field, _metadata_matrix.Channel.VIDEO_CONTAINER)
    and _metadata_matrix.canonical_channel(field) is not _metadata_matrix.Channel.VIDEO_CONTAINER
)
MANIFEST_ONLY_FIELDS = (
    "calibration_results",
    "scan_provenance",
    "page_slot_timecode_mapping",
    "checksums",
    "local_reconstruction_history",
) + tuple(
    field
    for field in _metadata_matrix.known_fields()
    if not _metadata_matrix.is_allowed(field, _metadata_matrix.Channel.VIDEO_CONTAINER)
)


def supported_profiles(field: str) -> tuple[str, ...]:
    """Profiles for which ``field`` is supported, raising on an unknown field."""
    try:
        return TECHNICAL_METADATA_MATRIX[field]["supported_profiles"]
    except KeyError as exc:
        raise MetadataVerificationError(
            f"Champ technique inconnu: {field!r}. Champs connus: {sorted(TECHNICAL_METADATA_MATRIX)}"
        ) from exc


def probe_media(video_path: str, *, ffprobe_bin: str = "ffprobe") -> dict:
    """Return the full ffprobe JSON (``format`` + every ``stream``).

    Deliberately not restricted to ``-select_streams v:0`` with a frozen
    ``-show_entries`` list: that combination made the ``tmcd`` stream (a data
    stream), every format-level ``-metadata`` tag, and any field outside the
    list invisible — reported as ``ok: False`` on a perfectly conformant file.
    """
    if shutil.which(ffprobe_bin) is None:
        raise FfprobeNotFoundError(f"Binaire ffprobe introuvable dans le PATH: {ffprobe_bin!r}")

    try:
        result = subprocess.run(
            [
                ffprobe_bin,
                "-v", "error",
                "-show_streams",
                "-show_format",
                "-of", "json",
                "--",
                video_path,
            ],
            capture_output=True,
            # ffprobe emits UTF-8 JSON; text=True would decode it with the
            # locale encoding and blow up under LC_ALL=C or Windows cp1252.
            encoding="utf-8",
            errors="replace",
            timeout=FFPROBE_TIMEOUT_SECONDS,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise FfprobeError(
            f"ffprobe a echoue sur {video_path!r} (code {exc.returncode}): "
            f"{(exc.stderr or '').strip()}"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise FfprobeError(
            f"ffprobe n'a pas repondu en {FFPROBE_TIMEOUT_SECONDS}s sur {video_path!r}"
        ) from exc

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise FfprobeError(f"Sortie ffprobe illisible pour {video_path!r}: {exc}") from exc


def _video_stream(probe: dict) -> dict:
    for stream in probe.get("streams", []):
        if stream.get("codec_type") == "video":
            return stream
    raise FfprobeError("Aucun flux video dans la sortie ffprobe")


def _find_timecode(probe: dict) -> str | None:
    """Look up the timecode wherever the container puts it.

    mov/mp4 expose it on the video stream tags, MXF only at format level, and
    Matroska upper-cases the key. Reading only ``v:0`` tags returns "no
    timecode" for an MXF rush that carries ``01:00:00:00``, and the master
    then ships at ``00:00:00:00``.
    """
    sources = [stream.get("tags", {}) for stream in probe.get("streams", [])]
    sources.append(probe.get("format", {}).get("tags", {}))
    for tags in sources:
        for key, value in (tags or {}).items():
            if key.lower() == "timecode" and value:
                return value
    return None


def read_technical_metadata(video_path: str, *, ffprobe_bin: str = "ffprobe") -> dict:
    """Return every matrix field as actually present in ``video_path``.

    A field absent from the file maps to ``None`` (ffprobe omits "unknown"
    color fields entirely rather than reporting them).
    """
    probe = probe_media(video_path, ffprobe_bin=ffprobe_bin)
    stream = _video_stream(probe)

    values: dict[str, object] = {}
    for field, entry in TECHNICAL_METADATA_MATRIX.items():
        key = entry["probe_key"]
        if key == "resolution":
            width, height = stream.get("width"), stream.get("height")
            values[field] = f"{width}x{height}" if width and height else None
        elif key == "timecode":
            values[field] = _find_timecode(probe)
        else:
            values[field] = stream.get(key)
    return values


def _matches(field: str, expected: object, actual: object) -> bool:
    if expected is None or actual is None:
        # Presence is part of the contract: "expected None" means "must be
        # absent". The old str(actual) == str(expected) made {"anything": None}
        # pass on a field that does not exist at all.
        return expected is None and actual is None
    comparison = TECHNICAL_METADATA_MATRIX[field]["comparison"]
    if comparison == "rational":
        # ffprobe returns "24/1"; a manifest stores 24, 24.0 or "23.976".
        # Only "24/1" used to compare equal, so a conformant master was rejected.
        try:
            return Fraction(exact_frame_rate(expected)) == Fraction(str(actual))
        except (ValueError, ZeroDivisionError, TypeError):
            return False
    if comparison == "timecode":
        # Meme classe de defaut que `rational` ci-dessus, et corrigee le
        # 2026-08-10 pour la meme raison: la comparaison porte sur l'**image
        # designee**, jamais sur la chaine. ffmpeg ecrit le champ `ff` sur
        # `len(str(ceil(cadence) - 1))` chiffres (mesure de la story 6.0,
        # `codec_profiles.timecode_frame_field_width`), donc `00:00:00:0` relu
        # d'un master a 5 im/s **est** le `00:00:00:04` demande. Comparer les
        # chaines declarait non conforme un master parfaitement juste a 1, 5,
        # 10 et 120 im/s -- trois des cinq cadences reelles de ce depot.
        #
        # Ce site est le **second** de la chaine, distinct de celui que la
        # story 6.0 a corrige dans `codec_profiles.verify_encoded_output`: il
        # etait masque par l'abstention de la story 6.1, qui ne posait jamais
        # de timecode attendu hors de la fenetre `11 <= ceil(cadence) <= 100`.
        # Lever l'abstention l'a decouvert, et un master juste a 5 im/s sortait
        # alors en `VERIFICATION_TECHNIQUE_EN_ECHEC`.
        #
        # Ce qui est absorbe est la largeur d'ecriture, rien d'autre: un
        # timecode qui designe une autre image reste refuse, et un `tmcd`
        # absent l'est aussi (traite plus haut par la garde de presence).
        return codec_profiles.timecodes_equivalent(actual, expected)
    return str(actual) == str(expected)


def verify_technical_metadata(
    video_path: str,
    expected: dict,
    *,
    require_mandatory: bool = True,
    ffprobe_bin: str = "ffprobe",
) -> dict:
    """Verify technical fields of ``video_path`` against ``expected``.

    ``expected`` maps **matrix field names** (``codec``, ``frame_rate``,
    ``timecode``, ...) to their required value, or to ``None`` to assert the
    field is absent. Returns ``{field: {"expected", "actual", "ok"}}``.

    Raises ``MetadataVerificationError`` on an unknown field name, and — unless
    ``require_mandatory=False`` — when ``expected`` omits a mandatory field:
    an empty request used to return ``{}``, on which ``all(...)`` is ``True``,
    i.e. a full pass without a single field having been read.
    """
    unknown = sorted(set(expected) - set(TECHNICAL_METADATA_MATRIX))
    if unknown:
        raise MetadataVerificationError(
            f"Champs techniques inconnus: {unknown}. "
            f"Champs connus: {sorted(TECHNICAL_METADATA_MATRIX)}"
        )
    if require_mandatory:
        missing = [f for f in MANDATORY_TECHNICAL_FIELDS if f not in expected]
        if missing:
            raise MetadataVerificationError(
                f"Verification vide de sens: champs obligatoires absents de la demande: {missing}. "
                "Passer require_mandatory=False pour une verification volontairement partielle."
            )

    actual_values = read_technical_metadata(video_path, ffprobe_bin=ffprobe_bin)
    return {
        field: {
            "expected": expected_value,
            "actual": actual_values[field],
            "ok": _matches(field, expected_value, actual_values[field]),
        }
        for field, expected_value in expected.items()
    }
