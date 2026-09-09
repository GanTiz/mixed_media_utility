# -*- coding: utf-8 -*-
"""Les conditions limites du retrait d'un jeu de frames extraites.

**Ce banc est ne d'une campagne de mutation**, couche 2 de la revue de la
vague 2 de l'Epic 11 (2026-09-07). Il ne double aucun test de
`test_suppression_des_frames_extraites.py` : il joue exactement les regimes
que ce banc-la ne visite pas, et que deux mutants ont traverses vivants.

Les deux mutants, et ce qu'ils coutaient :

* `_retirer_un_objet_versionne`, branche d'EXECUTION,
  `rang_independant=famille.rang_independant` -> `rang_independant=True`.
  **SURVIVANT** sur les 39 tests du banc d'origine. Les deux gardes qui
  mesurent ce champ -- `test_le_rapport_dit_que_cet_objet_n_a_PAS_de_rang_
  propre` et `test_le_drapeau_du_rang_VARIE_dans_les_deux_sens` -- appellent
  toutes deux `remove_project_element` **sans** `dry_run=False`, donc elles ne
  visitent que la branche d'APERCU, qui porte le champ correctement. Cout
  mesure, `--frames-extraites --confirmer` sous le mutant :

      Le rang 1 reste CONSOMME: un frames extraites posterieur existe, et
      deux versions ne peuvent pas porter le meme numero.

  c'est-a-dire mot pour mot la phrase que le commit de la vague dit avoir
  fermee (« une phrase fausse de bout en bout ici, puisqu'aucun objet
  posterieur n'existe ») -- rouverte sur le seul chemin qui DETRUIT ;
* `_retirer_un_objet_versionne`, `if liberer_le_rang and not
  famille.rang_independant:` -> `if False:`. **SURVIVANT** aussi : le refus
  jumeau pose dans `remove_project_element` tombe en amont, si bien que le
  second appelant du texte partage n'est jamais atteint par l'API publique.
  La levee reste une garde de profondeur pour un appelant direct ; ce banc la
  mesure la ou elle vit.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from mixed_media_utility.io import project_layout
from mixed_media_utility.project_maintenance import (
    ProjectMaintenanceError,
    _famille_des_frames_extraites,
    _retirer_un_objet_versionne,
    remove_project_element,
)

RACINE = project_layout.EXTRACT_FRAMES_DIRNAME


# ---------------------------------------------------------------------------
# La fabrique : DEUX lots distinguables, la cible en QUEUE.
# ---------------------------------------------------------------------------


def _lot(lot_id: str, cardinal: int) -> dict:
    """Un lot dont les frames portent son nom : une permutation se voit."""
    return {
        "lot_id": lot_id, "rush_id": "rush-a", "state": "extraction",
        "fps_target": 12.5, "frames_dir": f"{RACINE}/{lot_id}",
        "expected_frame_count": cardinal,
        "first_frame_timecode": "00:00:00:00", "output_bit_depth": 16,
    }


def _projet(tmp_path):
    """Deux lots de cardinaux DIFFERENTS ; la cible de ce banc est en QUEUE.

    Le banc d'origine place sa cible au milieu et joue les deux bords ; celui-ci
    vise la queue, qui est le bord ou un balayage tronque ne se demasque pas.
    """
    manifest = {
        "schema_version": "2.1", "project_id": "projet",
        "rushes": [{"rush_id": "rush-a"}],
        "lots": [_lot("rush-a_24", 2), _lot("rush-a_5", 3)],
    }
    projet = tmp_path / "projet"
    projet.mkdir()
    (projet / "project.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    for entree in manifest["lots"]:
        dossier = projet / entree["frames_dir"]
        dossier.mkdir(parents=True)
        for numero in range(entree["expected_frame_count"]):
            (dossier / f"{entree['lot_id']}_{numero:04d}.tiff").write_bytes(
                f"{entree['lot_id']}-{numero}".encode())
    return projet


def _manifeste(projet) -> dict:
    return json.loads((projet / "project.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Le champ `rang_independant` sur la branche qui ECRIT.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("dry_run", [True, False])
def test_le_rang_non_INDEPENDANT_survit_a_l_EXECUTION_pas_seulement_a_l_apercu(
        tmp_path, dry_run):
    """Le drapeau varie ici sur le MODE, pas sur sa valeur.

    Les deux branches de `_retirer_un_objet_versionne` construisent leur
    rapport separement : mesurer l'apercu ne dit rien de l'execution, et c'est
    par la que le mutant est passe. Le meme cas est joue dans les deux modes,
    sur la cible en QUEUE du manifeste.
    """
    projet = _projet(tmp_path)
    rapport = remove_project_element(
        projet, lot_id="rush-a_5", frames_extraites=True, dry_run=dry_run)
    assert rapport.dry_run is dry_run
    assert rapport.rang_independant is False, (
        "le jeu de frames extraites n'a pas de rang propre, quel que soit le "
        "mode")
    assert rapport.objet_en_queue is False
    assert rapport.rangs_liberables == ()


def test_le_volet_POSITIF_du_meme_champ_a_l_EXECUTION(tmp_path):
    """Sans lui, un `rang_independant` cable a `False` passerait ci-dessus.

    Le LOT SCANNE, lui, porte un rang propre -- et c'est le meme mode
    d'ecriture, la meme fonction, le meme rapport.
    """
    projet = _projet(tmp_path)
    scannees = projet / project_layout.SCAN_FRAMES_DIRNAME / "rush-a_5"
    scannees.mkdir(parents=True)
    (scannees / "s.tiff").write_bytes(b"scan")
    rapport = remove_project_element(
        projet, lot_id="rush-a_5", lot_scanne=True, dry_run=False)
    assert rapport.supprime is True
    assert rapport.rang_independant is True


def test_cli_CONFIRMER_dit_qu_aucun_rang_n_est_en_jeu(tmp_path):
    """La sortie du chemin qui DETRUIT, mesuree pour elle-meme.

    Le banc d'origine mesure cette phrase sur l'apercu et ne mesure, sur
    `--confirmer`, que l'etat du disque et du manifeste. C'est exactement
    l'ecart par lequel le mutant est passe : sous lui, cette commande imprime
    « Le rang 1 reste CONSOMME: un frames extraites posterieur existe » sur un
    projet qui n'a aucun objet posterieur.

    La frontiere est jouee dans les DEUX sens -- la phrase juste presente, la
    phrase fausse absente --, sans quoi elle resterait verte sur une sortie qui
    dirait les deux.
    """
    projet = _projet(tmp_path)
    resultat = subprocess.run(
        [sys.executable, "-m", "mixed_media_utility.cli", "project", "remove",
         "--project", str(projet), "--lot", "rush-a_5", "--frames-extraites",
         "--confirmer"],
        capture_output=True, text=True,
        env={"PYTHONPATH": "src", "PATH": "/usr/bin:/bin"})
    assert resultat.returncode == 0, resultat.stderr
    assert "Aucun rang propre pour: frames extraites" in resultat.stdout
    assert "reste CONSOMME" not in resultat.stdout, (
        "aucun objet posterieur n'existe : cette phrase est fausse ici")
    assert "DERNIER a date" not in resultat.stdout
    assert not (projet / RACINE / "rush-a_5").exists()


# ---------------------------------------------------------------------------
# Le refus de rang chez le SECOND appelant du texte partage.
# ---------------------------------------------------------------------------


def test_le_refus_de_rang_MORD_AUSSI_dans_la_regle_de_retrait(tmp_path):
    """Le second appelant de `_refus_de_rang_non_independant`, mesure chez lui.

    `remove_project_element` refuse `liberer_le_rang` sur cette cible bien en
    amont, donc la garde jumelle posee dans `_retirer_un_objet_versionne` n'est
    atteinte par aucun chemin public -- un mutant qui la remplace par `if
    False:` traverse les 39 tests du banc d'origine sans une rougeur. Elle
    n'est pas morte pour autant : elle protege l'appelant direct, et c'est de
    la que ce banc l'appelle.

    Le volet NEGATIF compte autant : sans lui, un refus inconditionnel passerait
    ce test tout en fermant le retrait nominal.
    """
    projet = _projet(tmp_path)
    manifest = _manifeste(projet)
    lot = manifest["lots"][1]
    famille = _famille_des_frames_extraites(projet, manifest, lot)

    with pytest.raises(ProjectMaintenanceError) as erreur:
        _retirer_un_objet_versionne(
            projet, projet / "project.json", manifest, famille,
            dry_run=False, liberer_le_rang=True)
    message = str(erreur.value)
    assert "rang PROPRE" in message
    assert "Deux issues" in message
    assert "liberer_le_rang=" in message
    assert sorted(p.name for p in (projet / RACINE / "rush-a_5").iterdir())

    # Le volet SANS demande de rang : la meme famille part normalement.
    rapport = _retirer_un_objet_versionne(
        projet, projet / "project.json", manifest, famille,
        dry_run=False, liberer_le_rang=False)
    assert rapport.supprime is True
    assert rapport.rang_independant is False
