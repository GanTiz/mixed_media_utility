"""I/O helpers for Mixed Media Utility."""

from . import calibration_profile, project_layout
from .manifest import load_manifest, validate_manifest
from .naming import (
    CANONICAL_ID_MAX_LENGTH,
    NamingError,
    build_frame_filename,
    derive_short_id,
    format_fps_short,
    sanitize_timecode,
)
from .payload import (
    ALERT_BUDGET_BYTES,
    NOMINAL_BUDGET_BYTES,
    PAYLOAD_LONG_KEYS,
    PAYLOAD_SCHEMA_VERSION,
    PAYLOAD_SHORT_KEYS,
    PayloadBudgetExceeded,
    PayloadBudgetReport,
    PayloadSchemaVersionRefused,
    PayloadValidationError,
    PayloadVersionMissing,
    build_page_payload,
    check_payload_budget,
    parse_payload,
    serialize_payload,
    validate_payload,
)
from .reconstruction import ReconstructionError, reconstruct_project_manifest

__all__ = [
    "load_manifest",
    "validate_manifest",
    "project_layout",
    "calibration_profile",
    "PAYLOAD_SCHEMA_VERSION",
    # Story 5.17: la table de correspondance des cles courtes et le refus d'une planche
    # perimee font partie du contrat public -- un consommateur qui lit un QR doit pouvoir
    # distinguer « planche a reimprimer » de « QR etranger » sans importer un module prive.
    # La constante qui nommait le schema 1.0 remplace est retiree par la story 2.7, dans
    # le meme geste que la branche de lecture 1.0 qu'elle documentait (`EPIC7-ARB-56`):
    # plus aucun consommateur, interne ou public, n'en a l'usage. Nom deliberement non
    # cite ici, au litteral: le grep de frontiere de l'AC 4 exige zero occurrence.
    "PAYLOAD_SHORT_KEYS",
    "PAYLOAD_LONG_KEYS",
    "NOMINAL_BUDGET_BYTES",
    "ALERT_BUDGET_BYTES",
    "PayloadValidationError",
    "PayloadSchemaVersionRefused",
    "PayloadVersionMissing",
    "PayloadBudgetExceeded",
    "PayloadBudgetReport",
    "build_page_payload",
    "check_payload_budget",
    "parse_payload",
    "serialize_payload",
    "validate_payload",
    "CANONICAL_ID_MAX_LENGTH",
    "NamingError",
    "build_frame_filename",
    "derive_short_id",
    "format_fps_short",
    "sanitize_timecode",
    "ReconstructionError",
    "reconstruct_project_manifest",
]
