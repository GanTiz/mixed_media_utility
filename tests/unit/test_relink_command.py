"""Tests de la commande `relink` (story 2.8, AC 2).

Integration reelle (ffmpeg/ffprobe requis), sur le meme modele que
`test_extract_command.py`: un rush fabrique par `testsrc`, extrait une
premiere fois, puis "deplace" (copie a un autre chemin) pour verifier le
relink de bout en bout.
"""

from __future__ import annotations

import ast
import inspect
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import cli, relink
from mixed_media_utility.io import project_layout
from mixed_media_utility.io.extraction_manifest import MANIFEST_FILENAME
from mixed_media_utility.io.manifest import validate_manifest


requires_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe binaries not available on PATH",
)


def _make_rush(path: Path, *, rate: int = 30, duration: int = 4, size: str = "64x36") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"testsrc=size={size}:rate={rate}:duration={duration}",
        "-pix_fmt", "yuv420p",
        str(path),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return path


def _manifest(project: Path) -> dict:
    return json.loads((project / MANIFEST_FILENAME).read_text(encoding="utf-8"))


@pytest.fixture
def extracted_project(tmp_path):
    """Un projet avec un rush deja extrait -- gabarit de tous les tests relink."""
    rush = _make_rush(tmp_path / "source" / "rush-001.mov")
    project = tmp_path / "proj"
    assert cli.main(
        ["extract", "--project", str(project), "--video", str(rush), "--fps", "4",
         "--yes", "--accept-unknown-color"]
    ) == 0
    return project, rush


# --------------------------------------------------------------------------
# Nominal: designation manuelle et recherche
# --------------------------------------------------------------------------


@requires_ffmpeg
def test_relink_manuel_nominal_met_a_jour_le_chemin(tmp_path, extracted_project):
    project, rush = extracted_project
    moved = tmp_path / "archive" / "rush-001.mov"
    moved.parent.mkdir(parents=True)
    shutil.copy(rush, moved)

    assert cli.main(
        ["relink", "--project", str(project), "--rush", "rush-001", "--video", str(moved)]
    ) == 0

    manifest = _manifest(project)
    assert manifest["rushes"][0]["source_path"] == str(moved.resolve())
    validate_manifest(project / MANIFEST_FILENAME)  # ne doit pas lever


@requires_ffmpeg
def test_relink_par_recherche_nominal_sous_sous_dossier(tmp_path, extracted_project):
    project, rush = extracted_project
    dossier_recherche = tmp_path / "recherche"
    cible = dossier_recherche / "a" / "b" / "rush-001.mov"
    cible.parent.mkdir(parents=True)
    shutil.copy(rush, cible)

    assert cli.main(
        ["relink", "--project", str(project), "--rush", "rush-001",
         "--chercher", str(dossier_recherche)]
    ) == 0

    manifest = _manifest(project)
    assert manifest["rushes"][0]["source_path"] == str(cible.resolve())


@requires_ffmpeg
def test_relink_rush_omis_sur_un_seul_rush_passe(tmp_path, extracted_project):
    project, rush = extracted_project
    moved = tmp_path / "archive" / "rush-001.mov"
    moved.parent.mkdir(parents=True)
    shutil.copy(rush, moved)

    assert cli.main(["relink", "--project", str(project), "--video", str(moved)]) == 0

    manifest = _manifest(project)
    assert manifest["rushes"][0]["source_path"] == str(moved.resolve())


# --------------------------------------------------------------------------
# Frontiere: rien d'autre que source_path ne bouge (AC 2)
# --------------------------------------------------------------------------


@requires_ffmpeg
def test_relink_reussi_ne_modifie_aucun_autre_champ(tmp_path, extracted_project):
    project, rush = extracted_project
    before = _manifest(project)
    moved = tmp_path / "archive" / "rush-001.mov"
    moved.parent.mkdir(parents=True)
    shutil.copy(rush, moved)

    assert cli.main(
        ["relink", "--project", str(project), "--video", str(moved)]
    ) == 0

    after = _manifest(project)
    after["rushes"][0].pop("source_path")
    before["rushes"][0].pop("source_path", None)
    assert after == before


# --------------------------------------------------------------------------
# Conflits et refus (AC 2, EPIC7-ARB-34)
# --------------------------------------------------------------------------


@requires_ffmpeg
def test_relink_deux_candidats_refuse_et_manifest_intact(tmp_path, extracted_project):
    project, rush = extracted_project
    before_bytes = (project / MANIFEST_FILENAME).read_bytes()
    dossier = tmp_path / "recherche"
    for sous in ("a", "b"):
        cible = dossier / sous / "rush-001.mov"
        cible.parent.mkdir(parents=True)
        shutil.copy(rush, cible)

    assert cli.main(["relink", "--project", str(project), "--chercher", str(dossier)]) == 1
    assert (project / MANIFEST_FILENAME).read_bytes() == before_bytes


@requires_ffmpeg
def test_relink_zero_candidat_refuse(tmp_path, extracted_project):
    project, rush = extracted_project
    vide = tmp_path / "vide"
    vide.mkdir()

    assert cli.main(["relink", "--project", str(project), "--chercher", str(vide)]) == 1


@requires_ffmpeg
def test_relink_video_cardinal_hors_tolerance_refuse_avec_valeurs(
    tmp_path, extracted_project, capsys
) -> None:
    project, rush = extracted_project
    autre = tmp_path / "autre" / "rush-001.mov"
    autre.parent.mkdir(parents=True)
    _make_rush(autre, duration=2)  # cardinal source different (60 vs 120 frames)

    original_source_path = _manifest(project)["rushes"][0]["source_path"]

    assert cli.main(
        ["relink", "--project", str(project), "--video", str(autre)]
    ) == 1

    manifest = _manifest(project)
    assert manifest["rushes"][0]["source_path"] == original_source_path  # refus, rien ecrit
    sortie = capsys.readouterr().err
    assert "source_frame_count" in sortie


@requires_ffmpeg
def test_relink_video_fichier_texte_non_video_refuse_proprement(
    tmp_path, extracted_project, capsys
) -> None:
    """Patch 1 (revue de 2.8): `--video` vers un fichier texte non-video
    (le probe reel echoue avec `FfprobeError`) rend un refus nomme et propre,
    jamais une traceback brute a l'operateur."""
    project, rush = extracted_project
    texte = tmp_path / "pas-une-video.txt"
    texte.write_text("ceci n'est pas une video", encoding="utf-8")

    original_source_path = _manifest(project)["rushes"][0]["source_path"]

    assert cli.main(
        ["relink", "--project", str(project), "--video", str(texte)]
    ) == 1

    manifest = _manifest(project)
    assert manifest["rushes"][0]["source_path"] == original_source_path  # refus, rien ecrit
    sortie = capsys.readouterr()
    assert "Erreur" in sortie.err
    assert "Traceback" not in sortie.out
    assert "Traceback" not in sortie.err


@requires_ffmpeg
def test_relink_rush_id_inconnu_refuse(tmp_path, extracted_project):
    project, rush = extracted_project

    assert cli.main(
        ["relink", "--project", str(project), "--rush", "rush-inconnu", "--video", str(rush)]
    ) == 1


def test_relink_sans_manifest_refuse(tmp_path):
    projet_vierge = tmp_path / "vierge"

    assert cli.main(
        ["relink", "--project", str(projet_vierge), "--video", str(tmp_path / "x.mov")]
    ) == 1


def test_relink_video_et_chercher_mutuellement_exclusifs(tmp_path, capsys):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(
            ["relink", "--project", str(tmp_path), "--video", "a.mov",
             "--chercher", str(tmp_path)]
        )

    assert excinfo.value.code == 2
    assert "not allowed with argument" in capsys.readouterr().err


def test_relink_ni_video_ni_chercher_refuse_par_argparse(tmp_path, capsys):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["relink", "--project", str(tmp_path)])

    assert excinfo.value.code == 2
    assert "one of the arguments" in capsys.readouterr().err


# --------------------------------------------------------------------------
# Manifest ne du scan seul (AC 2, Decisions d'ecriture point 2)
# --------------------------------------------------------------------------


def _write_barren_manifest(project: Path, rush_id: str = "rush-001") -> None:
    """Manifest ne du scan seul: l'entree de rush est nue (`rush_id` seul),
    et le seul lot present n'a jamais ete extrait (ni `source_frame_count`
    ni aucun autre champ d'extraction) -- c'est ce qui rend les trois
    references d'identite non verifiables."""
    project_layout.ensure_project_layout(project)
    manifest = {
        "schema_version": "2.1",
        "project_id": "proj",
        "rushes": [{"rush_id": rush_id}],
        "lots": [{"lot_id": f"{rush_id}_scan", "rush_id": rush_id, "state": "scan"}],
        "artifacts": {},
        "color": {},
        "video": {},
        "reconstruction": {},
    }
    (project / MANIFEST_FILENAME).write_text(json.dumps(manifest), encoding="utf-8")


@requires_ffmpeg
def test_relink_chercher_refuse_sur_manifest_barren(tmp_path, extracted_project):
    project, rush = extracted_project
    _write_barren_manifest(project)

    assert cli.main(
        ["relink", "--project", str(project), "--chercher", str(tmp_path)]
    ) == 1


@requires_ffmpeg
def test_relink_video_accepte_avec_avertissement_sur_manifest_barren(
    tmp_path, extracted_project, capsys
) -> None:
    project, rush = extracted_project
    _write_barren_manifest(project)

    assert cli.main(
        ["relink", "--project", str(project), "--video", str(rush)]
    ) == 0

    manifest = _manifest(project)
    assert manifest["rushes"][0]["source_path"] == str(rush.resolve())
    sortie = capsys.readouterr().out
    assert "Avertissement" in sortie


# --------------------------------------------------------------------------
# Cardinaux divergents entre deux lots du meme rush (AC 2)
# --------------------------------------------------------------------------


@requires_ffmpeg
def test_relink_cardinaux_divergents_entre_lots_refuse(tmp_path, extracted_project):
    project, rush = extracted_project
    manifest = _manifest(project)
    lot_divergent = dict(manifest["lots"][0])
    lot_divergent["lot_id"] = "rush-001_2"
    lot_divergent["fps_target"] = 2.0
    lot_divergent["source_frame_count"] = manifest["lots"][0]["source_frame_count"] + 50
    manifest["lots"].append(lot_divergent)
    original_source_path = manifest["rushes"][0]["source_path"]
    (project / MANIFEST_FILENAME).write_text(json.dumps(manifest), encoding="utf-8")

    assert cli.main(
        ["relink", "--project", str(project), "--video", str(rush)]
    ) == 1
    assert _manifest(project)["rushes"][0]["source_path"] == original_source_path


# --------------------------------------------------------------------------
# AC 5 -- portabilite: projet copie sur une autre machine
# --------------------------------------------------------------------------


@requires_ffmpeg
def test_projet_copie_sur_une_autre_machine_devient_delinke_sans_rien_d_autre_changer(
    tmp_path, extracted_project
) -> None:
    """AC 5, test dedie: un projet copie sur une autre machine (simulee par
    un autre dossier racine, le `source_path` d'origine devenant mort)
    s'ouvre, son rush passe delinke, et RIEN d'autre ne change -- la
    validation rend exactement ce qu'elle rendait, et l'ouverture (ici: la
    simple lecture/validation du manifest copie, aucune commande n'ecrit au
    seul fait d'ouvrir) ne reecrit jamais `source_path` (`EPIC7-ARB-34`:
    seul le geste `relink` ecrit)."""
    project, rush = extracted_project

    # "Autre machine" = un autre dossier racine, SANS le rush d'origine:
    # seuls project.json et frames/ traversent, jamais source/. Le fichier
    # d'origine disparait pour de vrai: c'est ce qui rend le chemin absolu
    # mort, plutot que de simplement changer de racine sans le casser.
    machine_b = tmp_path / "machine-b"
    machine_b.mkdir()
    shutil.copytree(project, machine_b / "proj")
    copied_project = machine_b / "proj"
    rush.unlink()

    before_bytes = (copied_project / MANIFEST_FILENAME).read_bytes()
    before_manifest = _manifest(copied_project)

    # "S'ouvre": lecture et validation, exactement ce qu'un chargement de
    # projet fait -- aucune de ces fonctions n'ecrit.
    opened = validate_manifest(copied_project / MANIFEST_FILENAME)

    rush_entry = opened["rushes"][0]
    assert rush_entry["source_path"] == before_manifest["rushes"][0]["source_path"]
    assert relink.statut_de_liaison(rush_entry) == relink.DELINKE_CHEMIN_MORT

    # Rien d'autre n'a change: l'ouverture n'a pas touche au fichier, et le
    # projet source original n'a lui non plus pas ete affecte par la copie.
    after_bytes = (copied_project / MANIFEST_FILENAME).read_bytes()
    assert after_bytes == before_bytes
    assert _manifest(project) == before_manifest


# --------------------------------------------------------------------------
# Patch 2 (revue de 2.8) -- durcissement AR2, parite avec scan_command et
# scan_detect_command (story 5.25, meme vague)
# --------------------------------------------------------------------------


def test_relink_command_a_la_garde_ar2_en_derniere_position() -> None:
    """Frontiere negative de l'AC (parite AR2): le dernier statement de haut
    niveau du corps de `relink_command` est un `Try` dont les deux SEULS
    gestionnaires sont, dans l'ordre, `KeyboardInterrupt` puis `OSError` --
    rien insere entre les deux, aucun `except` metier deplace dans
    l'enrobage. Meme forme que le test dedie de `scan_command`
    (`test_scan_detect_command.py::test_les_gardes_ar2_sont_ajoutees_en_dernier_sans_reordonner_le_reste`)."""
    arbre = ast.parse(inspect.getsource(cli.relink_command))
    fonction = arbre.body[0]
    dernier = fonction.body[-1]
    assert isinstance(dernier, ast.Try), type(dernier)
    noms = [h.type.id for h in dernier.handlers]
    assert noms == ["KeyboardInterrupt", "OSError"], noms


def test_relink_keyboard_interrupt_rend_130_sans_trace(
    tmp_path, extracted_project, capsys, monkeypatch
) -> None:
    project, rush = extracted_project

    def _interrompt(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli.relink, "resoudre_rush_id", _interrompt)

    assert cli.main(["relink", "--project", str(project), "--video", str(rush)]) == 130
    sortie = capsys.readouterr()
    assert "Interruption clavier" in sortie.out
    assert "Traceback" not in sortie.out
    assert "Traceback" not in sortie.err


def test_relink_oserror_rend_1_avec_message_actionnable(
    tmp_path, extracted_project, capsys, monkeypatch
) -> None:
    project, rush = extracted_project

    def _echoue(*args, **kwargs):
        raise OSError("disque plein (mesure de test)")

    monkeypatch.setattr(cli.relink, "resoudre_rush_id", _echoue)

    assert cli.main(["relink", "--project", str(project), "--video", str(rush)]) == 1
    sortie = capsys.readouterr()
    assert "Erreur" in sortie.err
    assert "espace" in sortie.err.lower() or "disque" in sortie.err.lower()
    assert "Traceback" not in sortie.out
    assert "Traceback" not in sortie.err
