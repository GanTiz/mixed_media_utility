from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from jsonschema.exceptions import ValidationError

from mixed_media_utility.io import payload as payload_io
from mixed_media_utility.io.manifest import validate_manifest
from mixed_media_utility.io.reconstruction import (
    ReconstructionError,
    reconstruct_project_manifest,
)


def _page(page_index: int, page_count: int = 2, slot_index: int | None = None) -> dict:
    """Build a decoded page payload fixture (base zero, cf. ARCHITECTURE_DETAILED 3.1).

    `schema_version` is the QR *payload* contract version (story 2.3), not the
    manifest schema version. See `test_payload_reconstruction_roundtrip.py`
    for the same scenarios driven through the real `build_page_payload`.

    La version est **lue au contrat** et non ecrite en litteral depuis la story 5.17,
    qui l'a portee de `1.0` a `2.0`: une fixture qui epinglait `"1.0"` decrivait une
    planche que le lecteur refuse, donc ne testait plus la reconstruction mais le
    refus de version.
    """
    if slot_index is None:
        slot_index = page_index
    return {
        "schema_version": payload_io.PAYLOAD_SCHEMA_VERSION,
        "project_id": "example-001",
        "rush_id": "rush-001",
        "lot_id": "lot-001",
        "page_index": page_index,
        "page_count": page_count,
        # Story 5.16: le role de page. La fixture porte celui d'une **planche
        # d'images**, qui est le regime strict de la garde d'emplacements -- c'est le
        # regime que tous les scenarios de ce fichier decrivent. La page de calibration
        # a son propre fichier de tests (`test_calibration_page_geometry.py`), et pour
        # une raison de methode: melanger les deux roles dans cette fixture rendrait
        # muets les scenarios de refus d'emplacement, qui sont la moitie de ce fichier.
        "page_role": payload_io.PAGE_ROLE_IMAGES,
        "fps_target": 24.0,
        # Story 2.7 (payload 2.1, EPIC7-ARB-56): la cadence SOURCE du rush.
        "timecode_base_fps": "25/1",
        "template_id": "template-a4-16x9",
        "patch_preset_id": "patch-preset-mvp",
        "target_colorspace": "rec709",
        "gamut_map_id": "gamut-map-none-1",
        "slots": [{"slot_index": slot_index, "frame_timecode": f"00:00:0{slot_index}:00"}],
    }


def _full_payloads() -> list[dict]:
    return [_page(0), _page(1)]


# --- AC1 / AC4: full reconstruction -----------------------------------------------------------


def test_reconstruct_full_project_from_all_pages() -> None:
    manifest = reconstruct_project_manifest(_full_payloads())

    assert manifest["schema_version"] == "2.1"
    assert manifest["project_id"] == "example-001"
    assert manifest["rushes"] == [{"rush_id": "rush-001"}]
    # v2.1: la cadence cible appartient au lot, pas au projet.
    assert manifest["lots"] == [
        {
            "lot_id": "lot-001",
            "rush_id": "rush-001",
            "state": "reconstruction",
            "fps_target": 24.0,
            "timecode_base_fps": "25/1",
        }
    ]
    assert manifest["video"] == {}
    assert manifest["color"]["target_colorspace"] == "rec709"
    assert manifest["reconstruction"]["status"] == "complete"
    assert "missing_pages" not in manifest["reconstruction"]
    assert manifest["reconstruction"]["slots"] == [
        {"slot_index": 0, "frame_timecode": "00:00:00:00"},
        {"slot_index": 1, "frame_timecode": "00:00:01:00"},
    ]


def test_reconstruct_emits_the_manifest_schema_version_not_the_payload_one() -> None:
    """A payload declares the payload contract version; the manifest declares its own.

    **Depuis la story 2.7, les deux constantes valent numeriquement la meme chaine
    `"2.1"`, par pure coincidence**: `PAYLOAD_SCHEMA_VERSION` (contrat QR, story 2.3)
    et `CURRENT_SCHEMA_VERSION`/`MANIFEST_SCHEMA_VERSION` (schema de manifest, story
    2.1) sont deux artefacts **independants**, versionnes separement -- la premiere
    valait deja `"2.0"` avant que la seconde ne devienne `"2.1"`. La propriete que ce
    test mesure n'est donc plus l'inegalite numerique (qui ne tiendrait qu'a une
    coincidence de calendrier) mais l'**independance des deux constantes**: le manifest
    emet `reconstruction.MANIFEST_SCHEMA_VERSION`, jamais une valeur lue sur le
    payload.
    """
    from mixed_media_utility.io import reconstruction as reconstruction_module

    manifest = reconstruct_project_manifest(_full_payloads())

    assert _full_payloads()[0]["schema_version"] == payload_io.PAYLOAD_SCHEMA_VERSION
    assert manifest["schema_version"] == reconstruction_module.MANIFEST_SCHEMA_VERSION
    # Et le manifest emet **la constante de manifest**, jamais celle du payload lue en
    # aval: `reconstruction.py` suit `MANIFEST_SCHEMA_VERSION = CURRENT_SCHEMA_VERSION`
    # (io/manifest.py, story 2.1), une derivation independante de
    # `SUPPORTED_PAYLOAD_SCHEMA_VERSION = PAYLOAD_SCHEMA_VERSION` (contrat 2.3), meme si
    # les deux valent numeriquement la meme chaine aujourd'hui.
    assert reconstruction_module.SUPPORTED_PAYLOAD_SCHEMA_VERSION == payload_io.PAYLOAD_SCHEMA_VERSION


def test_reconstruct_full_project_ignores_input_order() -> None:
    forward = reconstruct_project_manifest([_page(0), _page(1)])
    backward = reconstruct_project_manifest([_page(1), _page(0)])

    assert forward == backward


def test_reconstruct_full_project_dedupes_identical_duplicate_pages() -> None:
    manifest = reconstruct_project_manifest([_page(0), _page(1), _page(0)])

    assert manifest["reconstruction"]["status"] == "complete"
    assert len(manifest["reconstruction"]["slots"]) == 2


# --- AC1 / AC4: acceptable partial reconstruction ----------------------------------------------


def test_reconstruct_partial_project_from_incomplete_page_set() -> None:
    manifest = reconstruct_project_manifest([_page(0)])

    assert manifest["reconstruction"]["status"] == "partial"
    assert manifest["reconstruction"]["missing_pages"] == [1]
    assert manifest["lots"][0]["state"] == "reconstruction"
    assert manifest["reconstruction"]["slots"] == [{"slot_index": 0, "frame_timecode": "00:00:00:00"}]


def test_reconstruct_partial_project_merges_source_path_from_existing_manifest() -> None:
    existing_manifest = {
        "schema_version": "2.0",
        "project_id": "example-001",
        "rushes": [{"rush_id": "rush-001", "source_path": "inputs/rush-001.mp4"}],
    }

    manifest = reconstruct_project_manifest([_page(0)], existing_manifest=existing_manifest)

    assert manifest["rushes"] == [{"rush_id": "rush-001", "source_path": "inputs/rush-001.mp4"}]


# --- AC3: canonical identifier stability -------------------------------------------------------


def test_reconstruct_project_is_deterministic_across_independent_runs() -> None:
    payloads_run_a = _full_payloads()
    payloads_run_b = list(reversed(copy.deepcopy(_full_payloads())))

    manifest_a = reconstruct_project_manifest(payloads_run_a)
    manifest_b = reconstruct_project_manifest(payloads_run_b)

    assert manifest_a == manifest_b
    assert manifest_a["project_id"] == manifest_b["project_id"]
    assert manifest_a["lots"][0]["lot_id"] == manifest_b["lots"][0]["lot_id"]
    assert manifest_a["rushes"][0]["rush_id"] == manifest_b["rushes"][0]["rush_id"]


# --- AC2 / AC4: explicit failure on missing/conflicting critical data --------------------------


def test_reconstruct_raises_on_empty_payload_list() -> None:
    with pytest.raises(ReconstructionError, match="aucun payload"):
        reconstruct_project_manifest([])


def test_reconstruct_raises_on_missing_critical_field() -> None:
    payload = _page(0)
    del payload["project_id"]

    with pytest.raises(ReconstructionError, match="project_id"):
        reconstruct_project_manifest([payload])


def test_reconstruct_raises_on_missing_target_colorspace() -> None:
    payload = _page(0)
    del payload["target_colorspace"]

    with pytest.raises(ReconstructionError, match="target_colorspace"):
        reconstruct_project_manifest([payload])


def test_reconstruct_raises_on_missing_slots() -> None:
    payload = _page(0)
    payload["slots"] = []

    with pytest.raises(ReconstructionError, match="slots"):
        reconstruct_project_manifest([payload])


def test_reconstruct_raises_on_incomplete_slot() -> None:
    payload = _page(0)
    del payload["slots"][0]["frame_timecode"]

    with pytest.raises(ReconstructionError, match="frame_timecode"):
        reconstruct_project_manifest([payload])


def test_reconstruct_raises_on_conflicting_project_id_between_pages() -> None:
    page_one = _page(0)
    page_two = _page(1)
    page_two["project_id"] = "other-project"

    with pytest.raises(ReconstructionError, match="project_id"):
        reconstruct_project_manifest([page_one, page_two])


def test_reconstruct_raises_on_conflicting_target_colorspace_between_pages() -> None:
    page_one = _page(0)
    page_two = _page(1)
    page_two["target_colorspace"] = "rec2020"

    with pytest.raises(ReconstructionError, match="target_colorspace"):
        reconstruct_project_manifest([page_one, page_two])


def test_reconstruct_raises_on_conflicting_page_count_between_pages() -> None:
    page_one = _page(0, page_count=2)
    page_two = _page(1, page_count=3)

    with pytest.raises(ReconstructionError, match="page_count"):
        reconstruct_project_manifest([page_one, page_two])


def test_reconstruct_raises_on_conflicting_duplicate_page_index() -> None:
    page_one = _page(0, slot_index=1)
    page_one_conflict = _page(0, slot_index=9)

    with pytest.raises(ReconstructionError, match="page_index"):
        reconstruct_project_manifest([page_one, page_one_conflict])


def test_reconstruct_raises_on_page_index_out_of_declared_range() -> None:
    """With `page_count = 1`, only `page_index = 0` is legal (base zero)."""
    page_zero = _page(0, page_count=1)
    page_out_of_range = _page(1, page_count=1)

    with pytest.raises(ReconstructionError, match="hors bornes"):
        reconstruct_project_manifest([page_zero, page_out_of_range])


def test_reconstruct_raises_on_duplicate_slot_index() -> None:
    page_one = _page(0, slot_index=1)
    page_two = _page(1, slot_index=1)

    with pytest.raises(ReconstructionError, match="slot_index"):
        reconstruct_project_manifest([page_one, page_two])


def test_reconstruct_raises_on_unsupported_payload_schema_version() -> None:
    page_one = _page(0)
    page_one["schema_version"] = "9.9"
    page_two = _page(1)
    page_two["schema_version"] = "9.9"

    with pytest.raises(ReconstructionError, match="schema_version"):
        reconstruct_project_manifest([page_one, page_two])


def test_reconstruct_rejects_a_manifest_version_used_as_a_payload_version() -> None:
    """Guards the exact confusion that broke the 2.3 -> 2.6 chain.

    **La version de confusion a change deux fois.** Ce test opposait `"2.0"`, version
    de manifest, a un payload en `1.0` -- puis, depuis 5.17, `"2.1"` (version de
    manifest courante depuis le 2026-08-04) a un payload en `2.0`. **Depuis la story
    2.7 (payload 2.1, `EPIC7-ARB-56`), les deux valent numeriquement la meme chaine
    `"2.1"`**: pure coincidence de calendrier entre deux artefacts independants, deja
    anticipee comme un risque de confusion (`deferred-work.md`). La confusion que ce
    test garde ne se demontre donc plus avec la version de manifest courante telle
    quelle, qui est devenue une version de payload licite par coincidence -- le
    mecanisme reste exerce avec une valeur qui en est distincte par construction,
    jamais devinee.
    """
    from mixed_media_utility.io.manifest import CURRENT_SCHEMA_VERSION

    confondue = CURRENT_SCHEMA_VERSION
    if confondue == payload_io.PAYLOAD_SCHEMA_VERSION:
        confondue = f"{confondue}-manifest"
    assert confondue != payload_io.PAYLOAD_SCHEMA_VERSION
    page_one = _page(0)
    page_one["schema_version"] = confondue
    page_two = _page(1)
    page_two["schema_version"] = confondue

    with pytest.raises(ReconstructionError, match="schema_version"):
        reconstruct_project_manifest([page_one, page_two])


def test_reconstruct_raises_on_conflict_with_existing_manifest_project_id() -> None:
    existing_manifest = {"project_id": "other-project", "rushes": []}

    with pytest.raises(ReconstructionError, match="project_id"):
        reconstruct_project_manifest(_full_payloads(), existing_manifest=existing_manifest)


def test_reconstruct_raises_on_conflict_with_existing_manifest_fps_target() -> None:
    existing_manifest = {"project_id": "example-001", "rushes": [], "video": {"fps_target": 30.0}}

    with pytest.raises(ReconstructionError, match="fps_target"):
        reconstruct_project_manifest(_full_payloads(), existing_manifest=existing_manifest)


def test_reconstruct_preserves_absolute_source_path_from_existing_manifest() -> None:
    """Renversement de la garde par la story 2.8 (AC 1, EPIC7-ARB-41): un
    `source_path` absolu au manifest local n'est plus un motif de refus, il
    est **preserve verbatim**. Avant cette story, cette meme entree levait
    `ReconstructionError` (« les chemins doivent rester relatifs au projet
    local »): le chemin d'une autre machine est un chemin mort, donc un rush
    delinke (AC 3), jamais un motif de refus de lecture."""
    existing_manifest = {
        "project_id": "example-001",
        "rushes": [{"rush_id": "rush-001", "source_path": "C:\\projects\\example\\rush-001.mp4"}],
    }

    manifest = reconstruct_project_manifest(_full_payloads(), existing_manifest=existing_manifest)

    rushes = {rush["rush_id"]: rush for rush in manifest["rushes"]}
    assert rushes["rush-001"]["source_path"] == "C:\\projects\\example\\rush-001.mp4"


# --- v2.1: plusieurs rushs et plusieurs cadences par projet ------------------------


def test_reconstruct_accepts_a_local_manifest_holding_another_rush() -> None:
    """Un projet porte plusieurs rushs (decisions-2026-08-04.md): la presence
    d'un autre rush dans le manifest local n'est plus un conflit."""
    existing_manifest = {
        "project_id": "example-001",
        "rushes": [
            {"rush_id": "rush-002", "source_path": "inputs/rush-002.mp4"},
            {"rush_id": "rush-001"},
        ],
    }

    manifest = reconstruct_project_manifest(_full_payloads(), existing_manifest=existing_manifest)

    # L'autre rush est **conserve**: reconstruire un lot ne dit rien des autres
    # rushs du projet, et `cli.py` reecrit `project.json` en place.
    rushes = {rush["rush_id"]: rush for rush in manifest["rushes"]}
    assert set(rushes) == {"rush-001", "rush-002"}
    assert rushes["rush-002"]["source_path"] == "inputs/rush-002.mp4"
    assert manifest["lots"][-1]["rush_id"] == "rush-001"


def test_reconstruct_accepts_a_local_manifest_holding_another_target_rate() -> None:
    """Un autre lot du meme rush a une autre cadence est le cas nominal."""
    existing_manifest = {
        "project_id": "example-001",
        "rushes": [{"rush_id": "rush-001"}],
        "lots": [
            {"lot_id": "lot-002", "rush_id": "rush-001", "fps_target": 12.5},
        ],
    }

    manifest = reconstruct_project_manifest(_full_payloads(), existing_manifest=existing_manifest)

    # Les deux cadences coexistent. Verrouiller `lots[0]` sur une liste que le
    # code reduisait a un seul element revenait a verrouiller la perte de
    # l'autre lot (revue du 2026-08-05).
    lots = {lot["lot_id"]: lot for lot in manifest["lots"]}
    assert lots["lot-002"]["fps_target"] == 12.5
    assert lots["lot-001"]["fps_target"] == 24.0


def test_reconstruct_never_discards_what_a_previous_extraction_wrote() -> None:
    """La reconstruction d'un lot ne detruit pas les autres lots du projet.

    `cli.py` reecrit `project.json` en place: un manifest reconstruit mono-lot
    effacait donc, sans un mot, les empreintes de selection et les cardinaux
    attendus de tous les autres lots -- exactement ce que l'Epic 2 avait mis en
    place pour qu'un tiers puisse verifier un lot recu (revue du 2026-08-05).
    """
    existing_manifest = {
        "schema_version": "2.1",
        "project_id": "example-001",
        "rushes": [
            {"rush_id": "rush-001", "fps_source": 30.0},
            {"rush_id": "rush-002", "fps_source": 25.0},
        ],
        "lots": [
            {
                "lot_id": "lot-042",
                "rush_id": "rush-002",
                "fps_target": 5.0,
                "expected_frame_count": 60,
                "frame_timecodes_digest": "sha256-v1:" + "a" * 64,
            },
        ],
    }

    manifest = reconstruct_project_manifest(
        _full_payloads(), existing_manifest=existing_manifest
    )

    survivant = next(lot for lot in manifest["lots"] if lot["lot_id"] == "lot-042")
    assert survivant["expected_frame_count"] == 60
    assert survivant["frame_timecodes_digest"] == "sha256-v1:" + "a" * 64
    # Le rush du lot survivant, et sa cadence source, survivent aussi.
    rushes = {rush["rush_id"]: rush for rush in manifest["rushes"]}
    assert rushes["rush-002"]["fps_source"] == 25.0
    assert rushes["rush-001"]["fps_source"] == 30.0


def test_reconstruct_raises_when_the_same_lot_declares_another_target_rate() -> None:
    existing_manifest = {
        "project_id": "example-001",
        "rushes": [{"rush_id": "rush-001"}],
        "lots": [{"lot_id": "lot-001", "rush_id": "rush-001", "fps_target": 30.0}],
    }

    with pytest.raises(ReconstructionError, match="fps_target"):
        reconstruct_project_manifest(_full_payloads(), existing_manifest=existing_manifest)


# --- Story 5.9: gamut_map_id traverse jusqu'au manifest, et il est type ------


def test_gamut_map_id_reaches_the_reconstructed_manifest() -> None:
    """La propagation n'etait couverte par aucun test (revue 5.9-C1-5).

    Deux mutants survivaient, dont la suppression pure et simple du champ dans
    `reconstruction_meta`: le champ disparaissait du manifest sans qu'un test
    ne bronche, alors que l'equivalent existe pour `target_colorspace`. Or
    c'est precisement ce champ que la story 5.7 confrontera a ce que
    l'impression a persiste -- la garde du risque R12.
    """
    manifest = reconstruct_project_manifest(_full_payloads())
    assert manifest["reconstruction"]["gamut_map_id"] == "gamut-map-none-1"


def test_a_malformed_gamut_map_id_cannot_reach_a_valid_manifest(tmp_path: Path) -> None:
    """Le schema de manifest doit typer le champ (revue 5.9-C2-2).

    `reconstruction` porte `additionalProperties: true`: sans entree dediee, un
    manifest reconstruit portant `gamut_map_id: 42` etait **valide au schema**
    et s'ecrivait sur disque, alors que les temoins `template_id: 42` et
    `patch_preset_id: 42` etaient refuses. Un manifest valide portant une valeur
    inexploitable est pire qu'un manifest refuse: personne ne le rattrape.
    """
    manifest = reconstruct_project_manifest(_full_payloads())
    manifest_path = tmp_path / "project.json"

    for bad in (42, ["gamut-map-none-1"], "N IMPORTE QUOI", "", "gamut-map-" + "a" * 20 + "-1"):
        manifest["reconstruction"]["gamut_map_id"] = bad
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        with pytest.raises(ValidationError):
            validate_manifest(manifest_path)

    # Le temoin positif: la valeur legitime passe.
    manifest["reconstruction"]["gamut_map_id"] = "gamut-map-none-1"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    assert validate_manifest(manifest_path)
