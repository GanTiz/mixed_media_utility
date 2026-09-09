"""Project manifest loading and validation utilities.

Story 2.1 introduces the v2 "autoportant" manifest contract (schema_version,
project_id, rushes, lots, artifacts, color, video, reconstruction) alongside a
transitional legacy schema so the existing POC baseline (story 1.1) keeps
working while callers migrate. A manifest is validated against the v2 schema
when it carries a `schema_version` field, and against the legacy schema
otherwise. See ARCHITECTURE_DETAILED.md section 4 for the target contract.

Story 2.2 adds the technical metadata and lot state machine on top of that
contract: `validate_manifest_completeness` checks presence of the critical
technical fields (resolution source, source/target frame rate, target color
space, target codec, expected frame count and lot state), and
`validate_lot_state_transition` enforces that a lot's state only moves forward
through `LOT_STATES`.

The 2026-08-04 arbitration (`decisions-2026-08-04.md`) adds a **second**
version to that same dispatch, for exactly the same transitional reason: v2.1
moves everything describing the source into `rushes[]` and the target frame
rate into `lots[]`, because `video` was a single per-project section while
`rushes` and `lots` are lists. Manifests already written as `"2.0"` keep
validating against the frozen `project.schema.v2-0.json`, just like v1
manifests keep validating against `project.schema.legacy.json`. No manifest is
ever migrated on disk by this module: `validate_manifest` reads, it never
writes.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator, FormatChecker
from jsonschema.exceptions import ValidationError


#: Les schemas sont une DONNEE DU PAQUET, resolue relativement au module qui
#: les lit -- jamais depuis la racine du depot.
#:
#: Cette ligne valait `Path(__file__).resolve().parents[3] / "_bmad-output" /
#: "specs"` jusqu'au 2026-09-07. Depuis un clone, `parents[3]` tombe sur la
#: racine et tout marchait ; depuis un `site-packages`, il tombe sur
#: `lib/python3.x/` et la validation levait un `FileNotFoundError`. Mesure sur
#: une roue construite et installee dans un venv neuf : ZERO fichier `.json`
#: embarque sur 88, et `validate_manifest` en echec. Les 18 000 tests de la
#: suite ne l'ont jamais vu parce qu'ils tournent tous depuis le depot.
#:
#: `parents[1]` vaut le paquet `mixed_media_utility` -- vrai dans un clone
#: comme dans un `site-packages`, ce qui est exactement la propriete qui
#: manquait.
_SPECS = Path(__file__).resolve().parents[1] / "specs"
DEFAULT_SCHEMA_PATH = _SPECS / "project.schema.json"
SCHEMA_V2_0_PATH = _SPECS / "project.schema.v2-0.json"
LEGACY_SCHEMA_PATH = _SPECS / "project.schema.legacy.json"

# Version du contrat courant, celle qu'ecrivent les producteurs de manifest de
# ce depot (io/extraction_manifest.py, io/reconstruction.py).
CURRENT_SCHEMA_VERSION = "2.1"

# Versions encore lisibles, chacune contre son propre fichier de schema. Une
# version absente de cette table est refusee explicitement plutot que validee
# contre le contrat courant, ce qui produirait un diagnostic trompeur.
SCHEMA_PATHS_BY_VERSION: dict[str, Path] = {
    "2.0": SCHEMA_V2_0_PATH,
    "2.1": DEFAULT_SCHEMA_PATH,
}

# Schemas versionnes (par opposition au schema legacy v1): ce sont eux qui
# declenchent la garde de portabilite `_check_no_absolute_paths`.
_VERSIONED_SCHEMA_PATHS = frozenset(SCHEMA_PATHS_BY_VERSION.values())

# Matches POSIX absolute paths (/...), Windows drive-letter paths (C:\... or
# C:/...) and UNC paths (\\host\share). The canonical v2 contract forbids
# absolute paths so a manifest can be reconstructed on a third-party machine.
_ABSOLUTE_PATH_PATTERN = re.compile(r"^(?:/|[A-Za-z]:[\\/]|\\\\)")

# Story 2.8 (EPIC7-ARB-41, decision produit d'Egan verbatim: « Dans le projet !
# Mais remplacable ! »): le chemin du rush source vit desormais dans le
# manifest pour permettre le relink, ce qui leve l'invariant de portabilite
# "aucun chemin absolu au manifest" -- **pour ce champ, et seulement pour
# lui**. Un tuple d'un seul element pour que la frontiere reste un litteral
# greppable plutot qu'une condition dispersee dans le marcheur. N'ajouter un
# second element ici que sur un nouvel arbitrage produit explicite: chaque
# champ ajoute reouvre un peu plus le contrat de reconstruction sur machine
# tierce que tout l'Epic 2 existe pour garantir.
CHAMPS_EXEMPTES_CHEMIN_ABSOLU: tuple[str, ...] = ("rushes[].source_path",)

# Un indice de liste numerique (`rushes[3]`) ne doit pas empecher de
# reconnaitre le champ exempte: on le normalise en `rushes[]` avant de
# comparer a `CHAMPS_EXEMPTES_CHEMIN_ABSOLU`.
_LIST_INDEX_PATTERN = re.compile(r"\[\d+\]")


def _canonical_field_location(location: str) -> str:
    """Remplacer chaque indice de liste par `[]` pour comparer a un gabarit de champ."""
    return _LIST_INDEX_PATTERN.sub("[]", location)


# Story 2.2: machine a etats minimale des lots. L'ordre est celui du pipeline
# de reconstruction (voir ARCHITECTURE_DETAILED.md section 4 et 9); il fait
# aussi foi pour l'enum `lots[].state` du schema v2.
LOT_STATES: tuple[str, ...] = ("extraction", "pdf", "scan", "reconstruction", "encode")

# Story 2.2 (AC1): table des champs techniques du manifest v2, obligatoires ou
# optionnels au sens de `validate_manifest_completeness`. Le schema JSON garde
# ces champs optionnels au niveau structurel pour ne pas casser les manifests
# v2 en cours d'ecriture par d'autres stories; cette table documente le sous-
# ensemble considere critique pour verifier la completude d'un lot.
CRITICAL_TECHNICAL_FIELDS: tuple[tuple[str, str], ...] = (
    ("video", "resolution_source"),
    ("video", "fps_source"),
    ("video", "fps_target"),
    ("video", "codec_target"),
    ("color", "target_colorspace"),
)
CRITICAL_LOT_FIELDS: tuple[str, ...] = ("expected_frame_count", "state")

# Meme table, replacee sur les porteurs reels par la restructuration v2.1
# (`decisions-2026-08-04.md`): la source appartient au rush, la cadence cible
# au lot, `video` ne garde que la cible d'encodage. La table v2.0 ci-dessus
# n'est pas modifiee: elle reste le critere des manifests v2.0.
CRITICAL_PROJECT_FIELDS_V2_1: tuple[tuple[str, str], ...] = (
    ("video", "codec_target"),
    ("color", "target_colorspace"),
)
CRITICAL_RUSH_FIELDS_V2_1: tuple[str, ...] = ("fps_source", "resolution_source")
CRITICAL_LOT_FIELDS_V2_1: tuple[str, ...] = (
    "expected_frame_count",
    "state",
    "fps_target",
)
OPTIONAL_TECHNICAL_FIELDS: tuple[tuple[str, str], ...] = (
    ("reconstruction", "template_id"),
    ("reconstruction", "patch_preset_id"),
    ("artifacts", "frames_dir"),
    ("artifacts", "outputs_dir"),
)


def _load_schema(schema_path: Path) -> dict[str, Any]:
    with schema_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_manifest(path: str | Path) -> dict[str, Any]:
    manifest_path = Path(path)
    with manifest_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _iter_absolute_path_violations(value: Any, location: str = "") -> list[str]:
    """Return dotted locations of any string in `value` that looks like an absolute path.

    Story 2.8: un champ liste dans `CHAMPS_EXEMPTES_CHEMIN_ABSOLU`
    (`rushes[].source_path`, EPIC7-ARB-41) n'est jamais remonte comme
    violation, meme s'il ressemble a un chemin absolu -- c'est precisement ce
    qu'il doit porter.
    """
    violations: list[str] = []
    if isinstance(value, str):
        if (
            _ABSOLUTE_PATH_PATTERN.match(value)
            and _canonical_field_location(location) not in CHAMPS_EXEMPTES_CHEMIN_ABSOLU
        ):
            violations.append(location or "<root>")
    elif isinstance(value, dict):
        for key, sub_value in value.items():
            sub_location = f"{location}.{key}" if location else str(key)
            violations.extend(_iter_absolute_path_violations(sub_value, sub_location))
    elif isinstance(value, list):
        for index, sub_value in enumerate(value):
            sub_location = f"{location}[{index}]"
            violations.extend(_iter_absolute_path_violations(sub_value, sub_location))
    return violations


def _check_no_absolute_paths(manifest: dict[str, Any]) -> None:
    """Raise ValidationError if the v2 manifest contains any absolute path.

    Centralizes a portability invariant that JSON Schema alone expresses
    poorly across arbitrary nested fields (story 2.1, AC 2 & 3).
    """
    violations = _iter_absolute_path_violations(manifest)
    if violations:
        location = violations[0]
        raise ValidationError(
            f"Invalid manifest at '{location}': absolute paths are not allowed in the "
            "v2 contract; use paths relative to the project directory."
        )


def validate_manifest(
    path: str | Path,
    schema_path: str | Path | None = None,
) -> dict[str, Any]:
    manifest = load_manifest(path)
    if schema_path is not None:
        resolved_schema_path = Path(schema_path)
    elif "schema_version" in manifest:
        # Dispatch par version depuis la restructuration v2.1: chaque version
        # encore lisible a son propre fichier de schema (story 2.1 pour la
        # bascule v1 -> v2, `decisions-2026-08-04.md` pour v2.0 -> v2.1).
        declared_version = manifest["schema_version"]
        try:
            resolved_schema_path = SCHEMA_PATHS_BY_VERSION[declared_version]
        except (KeyError, TypeError) as error:
            known = ", ".join(sorted(SCHEMA_PATHS_BY_VERSION))
            raise ValidationError(
                f"Invalid manifest at 'schema_version': {declared_version!r} is not a "
                f"supported manifest schema_version (known: {known})."
            ) from error
    else:
        # Transitional compatibility: manifests without schema_version are
        # still validated against the legacy v1 contract (story 1.1 baseline).
        resolved_schema_path = LEGACY_SCHEMA_PATH

    schema = _load_schema(resolved_schema_path)
    validator = Draft7Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(manifest), key=lambda error: list(error.path))
    if errors:
        first_error = errors[0]
        location = ".".join(str(part) for part in first_error.path)
        detail = f" at '{location}'" if location else ""
        raise ValidationError(f"Invalid manifest{detail}: {first_error.message}")

    if resolved_schema_path in _VERSIONED_SCHEMA_PATHS:
        _check_no_absolute_paths(manifest)

    return manifest


def validate_manifest_completeness(manifest: dict[str, Any]) -> None:
    """Raise ValidationError if a v2 manifest is missing critical technical metadata.

    This is a stricter, opt-in check layered on top of `validate_manifest`'s JSON
    Schema validation (story 2.2, AC1 & AC4): resolution source, source/target
    frame rate, target color space and target codec, plus each lot's expected
    frame count and progress state. These fields stay optional at the schema
    level (see `project.schema.json`) so v2 manifests written by other in-flight
    stories keep validating; callers that need the full completeness guarantee
    (e.g. before a final encode) should call this function explicitly.

    The check follows the manifest's own `schema_version`: a v2.0 manifest is
    judged on `video.*` as before, a v2.1 manifest on the carriers that
    actually own each datum since `decisions-2026-08-04.md` (source on the
    rush, target frame rate on the lot). Judging a v2.1 manifest on the v2.0
    table would demand fields the v2.1 schema forbids in `video`.
    """
    if manifest.get("schema_version") == CURRENT_SCHEMA_VERSION:
        _validate_completeness_v2_1(manifest)
        return

    for section, field in CRITICAL_TECHNICAL_FIELDS:
        if field not in manifest.get(section, {}):
            raise ValidationError(
                f"Metadonnee technique critique manquante: '{section}.{field}'."
            )

    for index, lot in enumerate(manifest.get("lots", [])):
        for field in CRITICAL_LOT_FIELDS:
            if field not in lot:
                lot_ref = lot.get("lot_id", index)
                raise ValidationError(
                    f"Metadonnee de lot critique manquante: 'lots[{lot_ref}].{field}'."
                )


def _validate_completeness_v2_1(manifest: dict[str, Any]) -> None:
    """Completude d'un manifest v2.1, champ par champ sur son porteur reel."""
    for section, field in CRITICAL_PROJECT_FIELDS_V2_1:
        if field not in manifest.get(section, {}):
            raise ValidationError(
                f"Metadonnee technique critique manquante: '{section}.{field}'."
            )

    for index, rush in enumerate(manifest.get("rushes", [])):
        for field in CRITICAL_RUSH_FIELDS_V2_1:
            if field not in rush:
                rush_ref = rush.get("rush_id", index)
                raise ValidationError(
                    f"Metadonnee de rush critique manquante: 'rushes[{rush_ref}].{field}'."
                )

    for index, lot in enumerate(manifest.get("lots", [])):
        for field in CRITICAL_LOT_FIELDS_V2_1:
            if field not in lot:
                lot_ref = lot.get("lot_id", index)
                raise ValidationError(
                    f"Metadonnee de lot critique manquante: 'lots[{lot_ref}].{field}'."
                )


def validate_lot_state_transition(current_state: str | None, new_state: str) -> None:
    """Raise ValidationError if `new_state` is not a valid progression from `current_state`.

    States follow the minimal lot state machine defined for story 2.2:
    extraction -> pdf -> scan -> reconstruction -> encode. Backward transitions
    are rejected to avoid silently losing progress information. Staying on the
    same state or skipping ahead is accepted: some commands complete more than
    one conceptual stage in a single step (e.g. the POC `build-sheet` command
    covers both extraction and pdf generation).
    """
    if new_state not in LOT_STATES:
        raise ValidationError(
            f"Etat de lot inconnu: '{new_state}'. Valeurs attendues: {', '.join(LOT_STATES)}."
        )
    if current_state is None:
        return
    if current_state not in LOT_STATES:
        raise ValidationError(
            f"Etat de lot courant inconnu: '{current_state}'. Valeurs attendues: {', '.join(LOT_STATES)}."
        )
    if LOT_STATES.index(new_state) < LOT_STATES.index(current_state):
        raise ValidationError(
            f"Transition d'etat de lot invalide: '{current_state}' -> '{new_state}' "
            "(retour en arriere non autorise)."
        )