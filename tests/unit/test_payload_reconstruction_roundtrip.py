"""End-to-end contract test across stories 2.3 and 2.6.

Stories 2.3 (`io/payload.py`) and 2.6 (`io/reconstruction.py`) were developed on
parallel branches and each validated against its own locally-built fixtures, so
neither test suite ever crossed the boundary between them. That gap hid two
contract breaks: divergent `page_index` bases and a `target_colorspace` dropped
during reconstruction.

This module closes the gap by exercising the real third-party path end to end:

    build_page_payload -> serialize_payload -> parse_payload
                       -> reconstruct_project_manifest

Every payload here MUST be produced by `build_page_payload`, never hand-written.
A fixture built by hand can silently encode the wrong convention, which is
precisely how the original defect survived 173 green tests.

Story 5.7 extends this harness by one segment rather than opening a second one
(AC 13): la chaine de scan ne s'arrete plus a `reconstruct_project_manifest`,
elle continue jusqu'au `project.json` ecrit sur disque.

    ... -> write_lot_output_frames -> persist_scan -> project.json

Ce prolongement est le seul endroit du depot ou le manifest de scan est produit
depuis un payload **reellement passe par sa forme QR serialisee**: un champ
perdu au passage du QR -- `gamut_map_id`, `patch_preset_id`, un `slot_index` --
ne se verrait nulle part ailleurs, chacun des deux modules etant vert sur ses
propres fixtures. Les tests de fusion, de conflit et de cumul vivent dans
`tests/unit/test_scan_manifest.py`; ce qui vit ici, et uniquement ici, est la
traversee de la frontiere.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import scan_crop, scan_output_frames
from mixed_media_utility.io import scan_manifest
from mixed_media_utility.io.manifest import validate_manifest
from mixed_media_utility.io.naming import build_frame_filename, build_lot_id
from mixed_media_utility.io.payload import (
    build_page_payload,
    parse_payload,
    serialize_payload,
)
from mixed_media_utility.io.reconstruction import (
    ReconstructionError,
    reconstruct_project_manifest,
)

TARGET_COLORSPACE = "rec709"


def _payload(page_index: int, page_count: int = 2) -> dict:
    """Build a real story-2.3 payload for `page_index` (base zero, cf. section 3.1)."""
    return build_page_payload(
        project_id="example-001",
        rush_id="rush-001",
        lot_id="lot-001",
        page_index=page_index,
        page_count=page_count,
        fps_target=24.0,
        timecode_base_fps="25/1",
        template_id="template-a4-16x9",
        patch_preset_id="patch-preset-mvp",
        target_colorspace=TARGET_COLORSPACE,
        gamut_map_id="gamut-map-none-1",
        slots=[{"slot_index": page_index, "frame_timecode": f"00:00:0{page_index}:00"}],
    )


def _through_qr(payload: dict) -> dict:
    """Round-trip a payload through its serialized QR form, as a scan would."""
    return parse_payload(serialize_payload(payload))


# --- The boundary itself: a 2.3 payload must be reconstructible by 2.6 -------------------------


def test_first_page_payload_is_accepted_by_reconstruction() -> None:
    """The very first page (`page_index = 0`) must not be rejected as out of bounds."""
    manifest = reconstruct_project_manifest([_through_qr(_payload(0, page_count=1))])

    assert manifest["reconstruction"]["status"] == "complete"


def test_full_lot_round_trips_from_payloads_to_manifest() -> None:
    payloads = [_through_qr(_payload(index)) for index in range(2)]

    manifest = reconstruct_project_manifest(payloads)

    assert manifest["schema_version"] == "2.1"
    assert manifest["project_id"] == "example-001"
    assert manifest["reconstruction"]["status"] == "complete"
    assert "missing_pages" not in manifest["reconstruction"]
    assert manifest["reconstruction"]["slots"] == [
        {"slot_index": 0, "frame_timecode": "00:00:00:00"},
        {"slot_index": 1, "frame_timecode": "00:00:01:00"},
    ]


def test_partial_lot_reports_missing_pages_in_payload_index_space() -> None:
    """`missing_pages` must speak the same base-zero language as `page_index`."""
    manifest = reconstruct_project_manifest([_through_qr(_payload(0))])

    assert manifest["reconstruction"]["status"] == "partial"
    assert manifest["reconstruction"]["missing_pages"] == [1]


def test_every_declared_page_index_is_within_reconstruction_bounds() -> None:
    """No index legal for `build_page_payload` may be rejected by reconstruction."""
    page_count = 5
    payloads = [_through_qr(_payload(index, page_count=page_count)) for index in range(page_count)]

    manifest = reconstruct_project_manifest(payloads)

    assert manifest["reconstruction"]["status"] == "complete"
    assert len(manifest["reconstruction"]["slots"]) == page_count


# --- target_colorspace must survive the trip ---------------------------------------------------


def test_target_colorspace_is_propagated_to_the_reconstructed_manifest() -> None:
    """The only colorimetric field a third party can recover must not be dropped."""
    payloads = [_through_qr(_payload(index)) for index in range(2)]

    manifest = reconstruct_project_manifest(payloads)

    assert manifest["color"]["target_colorspace"] == TARGET_COLORSPACE


def test_conflicting_target_colorspace_between_pages_fails_explicitly() -> None:
    page_zero = _through_qr(_payload(0))
    page_one = _through_qr(_payload(1))
    page_one["target_colorspace"] = "rec2020"

    with pytest.raises(ReconstructionError, match="target_colorspace"):
        reconstruct_project_manifest([page_zero, page_one])


def test_reconstruction_rejects_a_payload_missing_target_colorspace() -> None:
    payload = _through_qr(_payload(0, page_count=1))
    del payload["target_colorspace"]

    with pytest.raises(ReconstructionError, match="target_colorspace"):
        reconstruct_project_manifest([payload])


# --- Naming stays aligned with the same convention ---------------------------------------------


def test_filename_human_numbering_is_derived_from_the_same_base_zero_index() -> None:
    """Filenames may display base-one page numbers, but only as a rendering step."""
    payload = _payload(0)

    filename = build_frame_filename(
        project_id=payload["project_id"],
        rush_id=payload["rush_id"],
        lot_id=payload["lot_id"],
        page_index=payload["page_index"],
        frame_timecode=payload["slots"][0]["frame_timecode"],
        fps_target=payload["fps_target"],
        slot_index=payload["slots"][0]["slot_index"],
    )

    assert "_p001_" in filename


# --- Story 5.7: le segment suivant, jusqu'au project.json ecrit ---------------------------------


SCAN_TEMPLATE_ID = "tpl-a4-portrait-2f-v1"
SCAN_DPI_RENDER = 100


def _scan_payload(
    page_index: int,
    page_count: int = 2,
    *,
    fps_target: float = 24.0,
    timecode_base_fps: str = "25/1",
) -> dict:
    """Payload d'une planche du gabarit reellement utilise par la chaine scan.

    `_payload` ci-dessus porte un `template_id` que le registre de gabarits ne
    connait pas: il suffit a la reconstruction, qui ne resout aucun gabarit,
    mais pas a l'ecriture des frames, qui en derive le cardinal attendu et la
    geometrie de decoupe. Le payload reste construit par `build_page_payload`.

    `fps_target`/`timecode_base_fps` sont parametrables depuis la story 2.7 :
    le lot_id derive de `fps_target` (`build_lot_id`), donc deux appels a des
    cadences cibles differentes produisent deux lots distincts du **meme**
    rush -- le cas nominal v2.1 (« deux tirages du meme rush ») que le test
    des deux lots ci-dessous exerce.
    """
    return build_page_payload(
        project_id="example-001",
        rush_id="rush-001",
        lot_id=build_lot_id("rush-001", fps_target),
        page_index=page_index,
        page_count=page_count,
        fps_target=fps_target,
        timecode_base_fps=timecode_base_fps,
        template_id=SCAN_TEMPLATE_ID,
        patch_preset_id="patch-values-2",
        target_colorspace=TARGET_COLORSPACE,
        gamut_map_id="gamut-map-none-1",
        slots=[
            {
                "slot_index": page_index * 2 + offset,
                "frame_timecode": f"00:00:{page_index * 2 + offset:02d}:00",
            }
            for offset in range(2)
        ],
    )


def _scanned_page(payload: dict) -> scan_output_frames.ScannedPage:
    """Page remise a 5.6, geometrie issue du **vrai** plan de decoupe de 5.3."""
    plan = scan_crop.build_page_crop_plan(
        template_id=payload["template_id"],
        slots=payload["slots"],
        dpi=SCAN_DPI_RENDER,
    )
    frames = tuple(
        np.full((frame.height_px, frame.width_px, 3), 4096 + 137 * frame.slot_index, np.uint16)
        for frame in plan.frames
    )
    return scan_output_frames.ScannedPage(payload=payload, crop_plan=plan, frames=frames)


def test_a_qr_round_tripped_lot_reaches_a_valid_manifest_on_disk(tmp_path) -> None:
    """La traversee complete: QR serialise -> frames ecrites -> project.json.

    Aucun maillon n'est simule. Un champ que la serialisation QR perdrait
    ferait echouer ce test, et lui seul: `test_scan_manifest.py` part de
    payloads non serialises, `test_payload.py` ne connait pas le manifest.
    """
    payloads = [_through_qr(_scan_payload(index)) for index in range(2)]
    project_dir = tmp_path / "projet"
    project_dir.mkdir()

    report = scan_output_frames.write_lot_output_frames(
        project_dir, [_scanned_page(payload) for payload in payloads]
    )
    persisted = scan_manifest.persist_scan(
        project_dir,
        scan_manifest.ScanRecord(
            page_payloads=tuple(payloads),
            output_report=report,
            scan_dpi=600,
            ingest_slug="lot-a",
        ),
    )

    document = validate_manifest(persisted.manifest_path)
    lot = next(entry for entry in document["lots"] if entry["lot_id"] == payloads[0]["lot_id"])
    assert lot["state"] == "scan"
    assert lot["fps_target"] == 24.0
    assert lot["reconstructed_frame_count"] == 4
    assert lot["synthetic_frame_count"] == 0
    assert lot["expected_frame_count"] == 4
    assert document["reconstruction"]["origin"] == "scan"
    assert document["reconstruction"]["status"] == "complete"
    assert document["color"]["target_colorspace"] == TARGET_COLORSPACE


def test_every_lot_level_field_of_the_qr_survives_as_far_as_the_manifest(tmp_path) -> None:
    """Les champs de niveau lot du payload se retrouvent **nommes** au manifest.

    C'est le test qui attrape un renommage: `gamut_map_id` et `patch_preset_id`
    sont precisement ceux que la story 5.7 confronte a ce que l'impression a
    persiste, et un champ perdu au passage du QR rendrait la confrontation
    silencieusement inoperante.
    """
    payloads = [_through_qr(_scan_payload(index)) for index in range(2)]
    project_dir = tmp_path / "projet"
    project_dir.mkdir()

    report = scan_output_frames.write_lot_output_frames(
        project_dir, [_scanned_page(payload) for payload in payloads]
    )
    persisted = scan_manifest.persist_scan(
        project_dir,
        scan_manifest.ScanRecord(
            page_payloads=tuple(payloads),
            output_report=report,
            scan_dpi=600,
            ingest_slug="lot-a",
        ),
    )

    section = persisted.manifest["reconstruction"]
    for field_name in ("template_id", "patch_preset_id", "gamut_map_id"):
        assert section[field_name] == payloads[0][field_name], field_name
    assert section["lot_id"] == payloads[0]["lot_id"]
    assert section["page_count"] == payloads[0]["page_count"]
    assert [slot["slot_index"] for slot in section["slots"]] == [0, 1, 2, 3]
    assert [slot["frame_timecode"] for slot in section["slots"]] == [
        slot["frame_timecode"] for payload in payloads for slot in payload["slots"]
    ]
    assert all(slot["synthetic"] is False for slot in section["slots"])


def test_a_partial_qr_round_tripped_lot_is_written_and_declared_partial(tmp_path) -> None:
    """Jamais de faux succes de bout en bout: le lot partiel s'ecrit et se dit."""
    payloads = [_through_qr(_scan_payload(0))]
    project_dir = tmp_path / "projet"
    project_dir.mkdir()

    report = scan_output_frames.write_lot_output_frames(
        project_dir, [_scanned_page(payload) for payload in payloads]
    )
    persisted = scan_manifest.persist_scan(
        project_dir,
        scan_manifest.ScanRecord(
            page_payloads=tuple(payloads),
            output_report=report,
            scan_dpi=600,
            ingest_slug="lot-a",
        ),
    )

    document = validate_manifest(persisted.manifest_path)
    assert document["reconstruction"]["status"] == "partial"
    assert document["reconstruction"]["missing_pages"] == [1]
    assert not persisted.lot_complete
    # La derniere page manque: le cardinal attendu est indeterminable, et il
    # n'est donc pas ecrit -- jamais devine.
    assert "expected_frame_count" not in document["lots"][0]


# --- Story 2.7, AC 3: le terrain du mutant M25 -- deux lots, deux cadences source ----------------


def test_two_lots_of_the_same_rush_keep_their_own_source_cadence_target_lot_second(
    tmp_path,
) -> None:
    """Le cas nominal v2.1 lui-meme, litteralement le risque R12.

    **Regle des fabriques** (CLAUDE.md, point durci apres le mutant `M25` de la story
    5.7 -- l'appariement de lot etait invisible tant que la cible restait le premier
    lot d'une liste): deux tirages du **meme rush**, a deux cadences cible (donc deux
    `lot_id`) et surtout deux cadences **source** distinguables (`timecode_base_fps`,
    l'axe que cette story ajoute) ; le lot vise -- celui dont on verifie la valeur --
    est scanne et rejoint le manifest en **seconde position**, jamais en premiere.

    Chaque passe de scan est reelle et sequentielle sur le **meme** `project_dir` :
    `persist_scan` relit le `project.json` deja ecrit par la premiere passe comme
    manifest existant (c'est le mecanisme meme de la confrontation AC 3), exactement
    le geste d'un operateur qui scanne deux tirages du meme rush l'un apres l'autre.
    Un appariement par lot fautif (ex.: toujours confronter/ecrire sur `lots[0]`) ne se
    verrait sur aucun test a un seul lot -- c'est pourquoi il ne s'est jamais vu avant
    `M25`, et pourquoi ce test existe pour cette story-ci en propre.
    """

    def _scan_une_passe(project_dir, *, fps_target: float, timecode_base_fps: str):
        payloads = [
            _through_qr(_scan_payload(
                index, fps_target=fps_target, timecode_base_fps=timecode_base_fps))
            for index in range(2)
        ]
        report = scan_output_frames.write_lot_output_frames(
            project_dir, [_scanned_page(payload) for payload in payloads]
        )
        return scan_manifest.persist_scan(
            project_dir,
            scan_manifest.ScanRecord(
                page_payloads=tuple(payloads),
                output_report=report,
                scan_dpi=600,
                ingest_slug=f"lot-{fps_target}",
            ),
        )

    project_dir = tmp_path / "projet"
    project_dir.mkdir()

    # Premiere passe: le lot temoin, place en PREMIERE position par construction (il
    # est scanne en premier). Ce n'est pas le lot que ce test verifie.
    _scan_une_passe(project_dir, fps_target=24.0, timecode_base_fps="25/1")

    # Deuxieme passe: le lot VISE, meme rush, cadence cible ET cadence source toutes
    # deux distinguables du lot temoin -- rejoint le manifest en seconde position.
    lot_vise_id = build_lot_id("rush-001", 12.5)
    persisted = _scan_une_passe(project_dir, fps_target=12.5, timecode_base_fps="30000/1001")

    document = validate_manifest(persisted.manifest_path)
    lots = document["lots"]
    assert len(lots) == 2, lots
    # Le lot vise est bien en seconde position dans le manifest final -- le fait meme
    # que la regle des fabriques exige de mesurer, pas seulement d'esperer.
    assert lots[1]["lot_id"] == lot_vise_id, lots

    par_lot_id = {lot["lot_id"]: lot for lot in lots}
    # La valeur relue est celle DU lot vise, pas celle du lot temoin scanne avant lui.
    assert par_lot_id[lot_vise_id]["timecode_base_fps"] == "30000/1001", par_lot_id
    # Temoin negatif: le premier lot garde SA propre valeur -- si l'appariement etait
    # fautif (ex.: `lots[0]` ecrase par toute passe suivante), les deux vaudraient
    # "30000/1001" et l'assertion precedente serait vraie par accident.
    autre_lot_id = build_lot_id("rush-001", 24.0)
    assert par_lot_id[autre_lot_id]["timecode_base_fps"] == "25/1", par_lot_id


def test_a_third_pass_diverging_from_the_targeted_lot_is_refused_by_that_lot_alone(
    tmp_path,
) -> None:
    """Le pendant negatif : la confrontation vise le BON lot parmi plusieurs.

    Meme montage a deux lots que le test ci-dessus, meme lot vise en seconde
    position ; une nouvelle serie de payloads rescanne ce lot vise avec une
    cadence source qui diverge de celle deja persistee. Le refus doit nommer
    **ce** lot -- un appariement fautif confronterait la nouvelle valeur au
    premier lot (dont la cadence source, `"25/1"`, ne diverge PAS de la valeur
    temoin ci-dessous) et laisserait passer silencieusement l'ecrasement.

    La confrontation elle-meme (`_check_manifest_conflicts`, via
    `reconstruct_project_manifest`) est exercee directement sur le manifest deja
    ecrit par les deux passes du test precedent, sans repasser par l'ecriture des
    frames (garde de non-ecrasement d'`OutputFrameExistsError`, hors sujet ici :
    ce test mesure la confrontation de cadence, pas la garde de fichiers).
    """
    def _scan_une_passe(project_dir, *, fps_target: float, timecode_base_fps: str):
        payloads = [
            _through_qr(_scan_payload(
                index, fps_target=fps_target, timecode_base_fps=timecode_base_fps))
            for index in range(2)
        ]
        report = scan_output_frames.write_lot_output_frames(
            project_dir, [_scanned_page(payload) for payload in payloads]
        )
        return scan_manifest.persist_scan(
            project_dir,
            scan_manifest.ScanRecord(
                page_payloads=tuple(payloads),
                output_report=report,
                scan_dpi=600,
                ingest_slug=f"lot-{fps_target}",
            ),
        )

    project_dir = tmp_path / "projet"
    project_dir.mkdir()

    _scan_une_passe(project_dir, fps_target=24.0, timecode_base_fps="25/1")
    _scan_une_passe(project_dir, fps_target=12.5, timecode_base_fps="30000/1001")

    manifest_existant = validate_manifest(project_dir / "project.json")
    lot_vise_id = build_lot_id("rush-001", 12.5)

    # Nouvelle serie de payloads pour le lot vise, cadence source divergente.
    payloads_divergents = [
        _through_qr(_scan_payload(index, fps_target=12.5, timecode_base_fps="24/1"))
        for index in range(2)
    ]
    with pytest.raises(ReconstructionError) as capture:
        reconstruct_project_manifest(payloads_divergents, existing_manifest=manifest_existant)

    message = str(capture.value)
    assert lot_vise_id in message, message
    assert "30000/1001" in message, message
    assert "24/1" in message, message
    # Le manifest sur disque n'a pas ete touche par le refus (mesure sur le fichier).
    document = validate_manifest(project_dir / "project.json")
    par_lot_id = {lot["lot_id"]: lot for lot in document["lots"]}
    assert par_lot_id[lot_vise_id]["timecode_base_fps"] == "30000/1001"
