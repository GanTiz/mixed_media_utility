"""Metadata responsibility matrix (story 2.4).

Encodes, as executable Python, the responsibility matrix defined in
`docs/guide-developpeur/ARCHITECTURE_DETAILED.md` section 5:
for each critical piece of reconstruction data, which channel (manifest,
filename, QR payload, ArUco markers, final video container) is allowed to
carry it, and which channel is its single canonical source of truth.

This module is the executable counterpart of the narrative matrix so that
code and tests can detect a field placed in a channel that the architecture
forbids (AC 3 & 4), instead of relying on the docs staying in sync by hand.

Canonical channel resolution follows the source-of-truth priority order from
ARCHITECTURE_DETAILED.md section 2: manifest v2 > QR payload > filename >
final video container. ArUco markers are excluded from that ranking on
purpose: per section 7, ArUco is reserved for geometry/discrete roles and
must never become the primary reconstruction channel for metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Channel(str, Enum):
    """Physical channels a piece of metadata can travel through."""

    MANIFEST = "manifest"
    FILENAME = "filename"
    QR = "qr"
    ARUCO = "aruco"
    VIDEO_CONTAINER = "video_container"


class Responsibility(str, Enum):
    """Whether a channel may carry a given data item."""

    REQUIRED = "required"
    OPTIONAL = "optional"
    FORBIDDEN = "forbidden"


@dataclass(frozen=True)
class MatrixCell:
    """One (field, channel) entry of the responsibility matrix."""

    responsibility: Responsibility
    note: str = ""


# Channels ordered by source-of-truth priority (highest first). Used to
# derive the single canonical channel for a field. ArUco is intentionally
# absent: it must never be picked as canonical (see module docstring).
_CANONICAL_PRIORITY: tuple[Channel, ...] = (
    Channel.MANIFEST,
    Channel.QR,
    Channel.FILENAME,
    Channel.VIDEO_CONTAINER,
)

_REQ = Responsibility.REQUIRED
_OPT = Responsibility.OPTIONAL
_FORBIDDEN = Responsibility.FORBIDDEN


def _row(
    manifest: Responsibility,
    filename: Responsibility,
    qr: Responsibility,
    aruco: Responsibility,
    video: Responsibility,
    *,
    manifest_note: str = "",
    filename_note: str = "",
    qr_note: str = "",
    aruco_note: str = "",
    video_note: str = "",
) -> dict[Channel, MatrixCell]:
    return {
        Channel.MANIFEST: MatrixCell(manifest, manifest_note),
        Channel.FILENAME: MatrixCell(filename, filename_note),
        Channel.QR: MatrixCell(qr, qr_note),
        Channel.ARUCO: MatrixCell(aruco, aruco_note),
        Channel.VIDEO_CONTAINER: MatrixCell(video, video_note),
    }


# Transcription of ARCHITECTURE_DETAILED.md section 5, one row per critical
# data item. `page_index` / `page_count` and `resolution source /
# colorimetrie source` are split into two fields each for a stable per-field
# API.
METADATA_MATRIX: dict[str, dict[Channel, MatrixCell]] = {
    "schema_version": _row(_REQ, _FORBIDDEN, _REQ, _FORBIDDEN, _FORBIDDEN),
    "project_id": _row(
        _REQ, _REQ, _REQ, _FORBIDDEN, _OPT,
        filename_note="version courte",
    ),
    "rush_id": _row(_REQ, _REQ, _REQ, _FORBIDDEN, _OPT),
    "lot_id": _row(_REQ, _REQ, _REQ, _FORBIDDEN, _FORBIDDEN),
    "page_index": _row(_REQ, _REQ, _REQ, _FORBIDDEN, _FORBIDDEN),
    "page_count": _row(_REQ, _REQ, _REQ, _FORBIDDEN, _FORBIDDEN),
    "slot_index": _row(
        # ArUco is a conditional permission ("Oui, si discret seulement"), not a
        # requirement: transcribing it as REQUIRED contradicted both the
        # narrative matrix and the story 4.4 decision (EPIC4-ARB-5) that MVP
        # ArUco IDs encode nothing -- the slot range stays reserved and dormant.
        _REQ, _OPT, _REQ, _OPT, _FORBIDDEN,
        aruco_note="discret seulement",
    ),
    "frame_timecode": _row(_REQ, _REQ, _REQ, _FORBIDDEN, _OPT),
    "fps_target": _row(
        _REQ, _REQ, _REQ, _FORBIDDEN, _REQ,
        filename_note="forme courte",
    ),
    "template_id": _row(
        _REQ, _OPT, _REQ, _OPT, _FORBIDDEN,
        aruco_note="si utile",
    ),
    "patch_preset_id": _row(_REQ, _FORBIDDEN, _REQ, _FORBIDDEN, _FORBIDDEN),
    # Story 5.9. Profil identique a `patch_preset_id`, et la cellule QR est
    # `_REQ` **sans condition ni note**: le champ etant obligatoire au payload
    # (EPIC5-ARB-13), il n'existe aucune planche qui en soit depourvue, donc
    # aucun cas ou `_REQ` ferait declarer non conforme une planche legitime.
    # Sans cette ligne, un champ voyagerait dans un canal que l'architecture
    # n'a jamais autorise.
    "gamut_map_id": _row(_REQ, _FORBIDDEN, _REQ, _FORBIDDEN, _FORBIDDEN),
    "layout_margin_params": _row(
        _REQ, _FORBIDDEN, _REQ, _FORBIDDEN, _FORBIDDEN,
        qr_note="sous forme d'ID de preset",
    ),
    "marker_geometry": _row(
        _REQ, _FORBIDDEN, _FORBIDDEN, _REQ, _FORBIDDEN,
        manifest_note="template",
        aruco_note="par detection visuelle",
    ),
    "source_resolution_colorimetry": _row(
        _REQ, _FORBIDDEN, _FORBIDDEN, _FORBIDDEN, _OPT,
        video_note="partiel",
    ),
    "page_calibration_results": _row(_REQ, _FORBIDDEN, _FORBIDDEN, _FORBIDDEN, _FORBIDDEN),
    "frame_page_checksum": _row(
        _REQ, _OPT, _OPT, _FORBIDDEN, _FORBIDDEN,
        qr_note="court",
    ),
    "codec_target_profile": _row(_REQ, _OPT, _FORBIDDEN, _FORBIDDEN, _REQ),
    "source_provenance_paths": _row(
        _OPT, _FORBIDDEN, _FORBIDDEN, _FORBIDDEN, _FORBIDDEN,
        manifest_note="non canonique",
    ),
}


class MetadataMatrixViolation(ValueError):
    """Raised when a field/channel assignment contradicts the matrix."""


def known_fields() -> tuple[str, ...]:
    """Return every critical data item documented in the matrix."""

    return tuple(METADATA_MATRIX.keys())


def get_cell(data_field: str, channel: Channel) -> MatrixCell:
    """Return the matrix cell for a (field, channel) pair.

    Raises KeyError if `data_field` is not part of the documented matrix.
    """

    try:
        row = METADATA_MATRIX[data_field]
    except KeyError as exc:
        raise KeyError(f"Unknown metadata field: '{data_field}'") from exc
    return row[channel]


def is_allowed(data_field: str, channel: Channel) -> bool:
    """Return whether `channel` may carry `data_field` at all."""

    return get_cell(data_field, channel).responsibility != Responsibility.FORBIDDEN


def canonical_channel(data_field: str) -> Channel | None:
    """Return the single canonical (source-of-truth) channel for a field.

    Follows the priority order manifest > QR > filename > video container
    (ARCHITECTURE_DETAILED.md section 2). Returns None if no channel is
    REQUIRED for this field (e.g. purely optional/non-canonical data such as
    `source_provenance_paths`).
    """

    row = METADATA_MATRIX[data_field]
    for channel in _CANONICAL_PRIORITY:
        if row[channel].responsibility == Responsibility.REQUIRED:
            return channel
    return None


@dataclass
class _Violation:
    data_field: str
    channel: Channel | None
    reason: str


def validate_assignment(
    assignment: dict[str, list[Channel]],
) -> None:
    """Validate that no field is placed in a channel the matrix forbids.

    `assignment` maps a data field name to the list of channels a caller
    intends to store it in. Raises `MetadataMatrixViolation` describing
    every violation found (unknown fields and forbidden placements).
    """

    violations: list[_Violation] = []

    for data_field, channels in assignment.items():
        if data_field not in METADATA_MATRIX:
            violations.append(
                _Violation(data_field, None, f"unknown metadata field '{data_field}'")
            )
            continue

        for channel in channels:
            if not is_allowed(data_field, channel):
                violations.append(
                    _Violation(
                        data_field,
                        channel,
                        f"field '{data_field}' is not allowed in channel '{channel.value}'",
                    )
                )

    if violations:
        message = "; ".join(violation.reason for violation in violations)
        raise MetadataMatrixViolation(message)
