from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import cli
from mixed_media_utility.io import payload as payload_io
from mixed_media_utility.io import project_layout
from mixed_media_utility.io.manifest import validate_manifest


def _write_payload(path: Path, payload: dict) -> Path:
    """Ecrire le fichier d'entree de `reconstruct-project`: **le texte du QR**.

    Depuis la story 5.17 et son bloquant B2, ce que la commande lit est la sortie d'un
    decodeur de QR -- schema `2.0`, cles courtes -- et non le dictionnaire a cles
    longues que le depot manipule en memoire. La fixture passe donc par
    `serialize_payload`, le **vrai** producteur du texte imprime, plutot que par un
    `json.dumps` du dictionnaire: un `json.dumps` nu ecrirait un document qu'aucun
    tirage ne porte et que le parseur refuse comme perime.
    """
    path.write_text(payload_io.serialize_payload(payload), encoding="utf-8")
    return path


def _page_payload(page_index: int, page_count: int = 2, slot_index: int | None = None) -> dict:
    """Decoded page payload fixture: base-zero `page_index`, payload-contract `schema_version`.

    Version **lue au contrat** depuis la story 5.17 (`1.0` -> `2.0`): un litteral y
    aurait decrit une planche que le lecteur refuse.
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
        # Story 5.16: role de page, celui d'une **planche d'images** -- le regime strict
        # de la garde d'emplacements, et celui que la sous-commande decrit. Un payload
        # relu par `reconstruct-project` traverse le vrai parseur, donc l'absence du
        # champ y est un refus et non une valeur devinee.
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


def _reconstruct(project_dir: Path, payload_paths: list[Path], manifest_path: Path | None = None) -> int:
    args = ["reconstruct-project", "--project", str(project_dir)]
    for payload_path in payload_paths:
        args += ["--payload", str(payload_path)]
    if manifest_path is not None:
        args += ["--manifest", str(manifest_path)]
    return cli.main(args)


def test_cli_reconstruct_project_full_set(tmp_path: Path) -> None:
    project_dir = tmp_path / "reconstructed_project"
    payload_one = _write_payload(tmp_path / "page1.json", _page_payload(0))
    payload_two = _write_payload(tmp_path / "page2.json", _page_payload(1))

    exit_code = _reconstruct(project_dir, [payload_one, payload_two])

    assert exit_code == 0
    manifest_path = project_dir / "project.json"
    assert manifest_path.is_file()
    manifest = validate_manifest(manifest_path)
    assert manifest["project_id"] == "example-001"
    assert manifest["reconstruction"]["status"] == "complete"

    for subdir in (project_layout.LEGACY_SOURCES_DIRNAME,
                   project_layout.EXTRACT_FRAMES_DIRNAME,
                   project_layout.PLANCHES_DIRNAME, "detection",
                   project_layout.OUTPUTS_DIRNAME,
                   project_layout.LOGS_DIRNAME):
        assert (project_dir / subdir).is_dir()


def test_cli_reconstruct_project_partial_set(tmp_path: Path) -> None:
    project_dir = tmp_path / "reconstructed_project_partial"
    payload_one = _write_payload(tmp_path / "page1.json", _page_payload(0))

    exit_code = _reconstruct(project_dir, [payload_one])

    assert exit_code == 0
    manifest = validate_manifest(project_dir / "project.json")
    assert manifest["reconstruction"]["status"] == "partial"
    assert manifest["reconstruction"]["missing_pages"] == [1]


def test_cli_reconstruct_project_is_deterministic_across_runs(tmp_path: Path) -> None:
    payload_one = _write_payload(tmp_path / "page1.json", _page_payload(0))
    payload_two = _write_payload(tmp_path / "page2.json", _page_payload(1))

    project_dir_a = tmp_path / "run_a"
    project_dir_b = tmp_path / "run_b"
    assert _reconstruct(project_dir_a, [payload_one, payload_two]) == 0
    assert _reconstruct(project_dir_b, [payload_two, payload_one]) == 0

    manifest_a = json.loads((project_dir_a / "project.json").read_text(encoding="utf-8"))
    manifest_b = json.loads((project_dir_b / "project.json").read_text(encoding="utf-8"))
    assert manifest_a == manifest_b


def test_cli_reconstruct_project_fails_explicitly_on_missing_payload_file(tmp_path: Path) -> None:
    project_dir = tmp_path / "reconstructed_project_missing_file"
    missing_payload = tmp_path / "does_not_exist.json"

    exit_code = _reconstruct(project_dir, [missing_payload])

    assert exit_code == 1
    assert not (project_dir / "project.json").exists()
    log_path = project_dir / project_layout.LOGS_DIRNAME / "poc_run.log"
    assert log_path.is_file()
    assert "introuvable" in log_path.read_text(encoding="utf-8")


def test_cli_reconstruct_project_fails_explicitly_on_conflicting_pages(tmp_path: Path) -> None:
    project_dir = tmp_path / "reconstructed_project_conflict"
    payload_one = _write_payload(tmp_path / "page1.json", _page_payload(0))
    conflicting_payload = _page_payload(1)
    conflicting_payload["project_id"] = "other-project"
    payload_two = _write_payload(tmp_path / "page2_conflict.json", conflicting_payload)

    exit_code = _reconstruct(project_dir, [payload_one, payload_two])

    assert exit_code == 1
    assert not (project_dir / "project.json").exists()
    log_path = project_dir / project_layout.LOGS_DIRNAME / "poc_run.log"
    assert log_path.is_file()
    assert "project_id" in log_path.read_text(encoding="utf-8")


def test_cli_reconstruct_project_merges_partial_local_manifest(tmp_path: Path) -> None:
    project_dir = tmp_path / "reconstructed_project_with_manifest"
    payload_one = _write_payload(tmp_path / "page1.json", _page_payload(0))
    existing_manifest_path = tmp_path / "partial_manifest.json"
    existing_manifest_path.write_text(
        json.dumps(
            {
                "project_id": "example-001",
                "rushes": [{"rush_id": "rush-001", "source_path": "inputs/rush-001.mp4"}],
            }
        ),
        encoding="utf-8",
    )

    exit_code = _reconstruct(project_dir, [payload_one], manifest_path=existing_manifest_path)

    assert exit_code == 0
    manifest = validate_manifest(project_dir / "project.json")
    assert manifest["rushes"] == [{"rush_id": "rush-001", "source_path": "inputs/rush-001.mp4"}]


def test_the_command_reads_exactly_what_a_qr_decoder_produces(tmp_path: Path) -> None:
    """Une **meme** entree satisfait la commande et `parse_payload` (bloquant B2, 5.17).

    C'est le critere de la correction, et il etait faux avant: la commande lisait un
    `json.loads` nu, donc exigeait des cles **longues** portant `2.0`, c'est-a-dire
    exactement le document que `parse_payload` refuse comme perime. Aucune entree ne
    satisfaisait les deux cotes, sur la seule commande dont le contrat d'entree est
    publie comme « la sortie d'un decodeur de QR ».

    Le texte est donc produit par le vrai producteur du papier, et il est confronte aux
    deux cotes: la commande l'accepte, et `parse_payload` le relit.
    """
    texte_du_qr = payload_io.serialize_payload(_page_payload(0, page_count=1))
    # Cote papier: ce sont bien des cles courtes, celles qui voyagent imprimees.
    assert set(json.loads(texte_du_qr)) <= set(payload_io.PAYLOAD_SHORT_KEYS.values())
    assert f'"sv":"{payload_io.PAYLOAD_SCHEMA_VERSION}"' in texte_du_qr
    # Cote parseur: la meme entree est relue sans refus.
    assert payload_io.parse_payload(texte_du_qr)["project_id"] == "example-001"

    payload_path = tmp_path / "page_du_qr.json"
    payload_path.write_text(texte_du_qr, encoding="utf-8")
    project_dir = tmp_path / "depuis_le_qr"
    assert _reconstruct(project_dir, [payload_path]) == 0
    manifest = validate_manifest(project_dir / "project.json")
    assert manifest["project_id"] == "example-001"
    assert manifest["reconstruction"]["status"] == "complete"


def test_a_stale_long_key_payload_file_is_refused_by_name_not_by_missing_fields(
    tmp_path: Path,
) -> None:
    """L'autre moitie du critere: le refus **nomme** la cause au lieu de la deguiser.

    **Sujet modifie par la story 2.7** (AC 4, `EPIC7-ARB-56`): jusqu'a cette story, le
    document a cles longues etait refuse comme **planche perimee** (« reimprimer »),
    et ce test verifiait que le motif n'accusait pas a tort une liste de champs
    manquants. Depuis le retrait de la branche de lecture 1.0, un tel document tombe
    dans le meme refus qu'un QR **etranger** (`PayloadVersionMissing`) -- la cle courte
    `sv` qu'il exige n'existe simplement pas sur un document a cles longues. Le mode
    d'echec elimine reste le meme (douze champs annonces absents alors qu'aucun ne
    manquait): c'est ce que ce test continue de verifier, avec le nouveau motif.
    """
    ancien = tmp_path / "cles_longues.json"
    ancien.write_text(json.dumps(_page_payload(0, page_count=1)), encoding="utf-8")
    project_dir = tmp_path / "refuse"

    assert _reconstruct(project_dir, [ancien]) == 1
    assert not (project_dir / "project.json").exists()
    journal = (project_dir / project_layout.LOGS_DIRNAME / "poc_run.log").read_text(encoding="utf-8")
    assert "etranger" in journal.lower(), journal
    assert "sv" in journal, journal
    # Et surtout: pas de liste de champs manquants sur un document qui les porte tous
    # (sous leurs noms longs).
    assert "manquant" not in journal.lower(), journal


def test_a_foreign_qr_text_is_refused_as_foreign_not_as_a_stale_sheet(
    tmp_path: Path,
) -> None:
    """Le partage operationnel des deux refus tient jusqu'a la CLI.

    Une planche perimee se reimprime, un QR etranger se met a la poubelle: confondre
    les deux enverrait reimprimer une planche qui n'a jamais existe. La commande etant
    desormais branchee sur `parse_payload`, elle herite de cette distinction -- ce test
    verifie qu'elle arrive bien jusqu'au journal.
    """
    etranger = tmp_path / "etiquette_de_colis.json"
    etranger.write_text('{"colis":"AB12","poids_kg":3}', encoding="utf-8")
    project_dir = tmp_path / "poubelle"

    assert _reconstruct(project_dir, [etranger]) == 1
    journal = (project_dir / project_layout.LOGS_DIRNAME / "poc_run.log").read_text(encoding="utf-8")
    assert "reimprim" not in journal.lower(), journal
    assert "aucun tirage n'est en cause" in journal, journal


def test_a_file_that_is_not_json_is_still_refused_with_its_path(tmp_path: Path) -> None:
    """Le refus d'un fichier illisible n'a pas disparu avec le `json.loads` nu.

    Il passe desormais par `parse_payload`, qui nomme la faute de syntaxe; le chemin du
    fichier reste dans le message, parce que l'operateur en passe plusieurs.
    """
    casse = tmp_path / "tronque.json"
    casse.write_text('{"sv":"2.0","pid":', encoding="utf-8")
    project_dir = tmp_path / "syntaxe"

    assert _reconstruct(project_dir, [casse]) == 1
    journal = (project_dir / project_layout.LOGS_DIRNAME / "poc_run.log").read_text(encoding="utf-8")
    assert "tronque.json" in journal, journal
    assert "JSON" in journal, journal
