"""Le projet VIDE entre au contrat du coeur (story 7.1, AC 1, Task 1).

Motif, mesure au baseline : le schema v2.1 portait ``minItems: 1`` sur
``rushes`` et sur ``lots``, si bien qu'aucun ``project.json`` ne pouvait
exister avant la premiere extraction. L'AC (C) de l'epic exige pourtant que
« creer un projet ecrive le fichier de projet a la racine du dossier
designe » : la GUI doit donc pouvoir ecrire un projet sans rush ni lot, et
le coeur doit accepter ce qu'elle ecrit -- l'interface ne redefinit aucune
regle du coeur.

Ce fichier mesure les quatre chemins que ce relachement touche :

1. le schema v2.1 accepte un projet vide (et le refus de v2.0 est INCHANGE :
   la retrocompatibilite n'est pas exigee sur les formats, `EPIC7-ARB-51`,
   mais un schema fige ne se retouche pas pour autant) ;
2. une extraction dans un projet vide aboutit et laisse un manifest valide ;
3. une reconstruction (depot de scan, variante du Flow 2) dans un projet
   vide aboutit ;
4. ``validate_manifest_completeness`` -- opt-in, appelee avant un encode --
   garde un verdict lisible sur un projet vide.

**Regle des fabriques** (CLAUDE.md) : les scenarios d'extraction et de
reconstruction ne se contentent pas d'un unique lot. Ils en ecrivent DEUX,
distinguables (cadences cibles differentes, donc ``lot_id`` differents), et
la cible des assertions est celui de SECONDE position -- un chemin qui
rendrait toujours la premiere entree ne se demasquerait pas autrement.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from jsonschema.exceptions import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility.frame_selection import select_source_frames
from mixed_media_utility.io.extraction_manifest import (
    MANIFEST_FILENAME,
    ExtractionRecord,
    persist_extraction,
)
from mixed_media_utility.io.manifest import (
    CURRENT_SCHEMA_VERSION,
    load_manifest,
    validate_manifest,
    validate_manifest_completeness,
)
from mixed_media_utility.io.naming import build_lot_id
from mixed_media_utility.io.project_layout import FRAMES_DIRNAME, rush_dir_slug
from mixed_media_utility.io.naming import build_extracted_frame_filename
from mixed_media_utility.io.reconstruction import reconstruct_project_manifest
from mixed_media_utility.io import payload as payload_io


#: Champs de source tagges, repris de la fixture de reference de la story 3.4
#: (`test_extraction_persistence_roundtrip.py`) : ils ne sont pas le sujet ici,
#: ils sont ce qu'une extraction reelle porte.
CHAMPS_SOURCE_TAGGES = {
    "source_codec": "prores",
    "source_pix_fmt": "yuv422p10le",
    "source_bit_depth": 10,
    "source_sample_aspect_ratio": "1:1",
    "source_color_primaries": "bt709",
    "source_color_trc": "bt709",
    "source_colorspace": "bt709",
    "source_color_range": "tv",
}


def manifeste_de_projet_vide(project_id: str = "projet-vide") -> dict:
    """Le manifest minimal qu'une creation de projet ecrit : zero rush, zero lot.

    Les huit cles requises du schema v2.1 sont presentes, les quatre objets
    dans leur forme minimale valide. Rien de plus : ni ``artifacts.frames_dir``
    (le dossier nait de la commande qui ecrit dedans), ni cible d'encodage.
    """
    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "project_id": project_id,
        "created": "2026-08-25T09:00:00Z",
        "rushes": [],
        "lots": [],
        "artifacts": {},
        "color": {},
        "video": {},
        "reconstruction": {},
    }


def _ecrire(chemin: Path, manifeste: dict) -> Path:
    chemin.write_text(json.dumps(manifeste), encoding="utf-8")
    return chemin


# ---------------------------------------------------------------------------
# 1. Le schema
# ---------------------------------------------------------------------------


def test_le_schema_v2_1_accepte_un_projet_sans_rush_ni_lot(tmp_path: Path) -> None:
    chemin = _ecrire(tmp_path / MANIFEST_FILENAME, manifeste_de_projet_vide())

    manifeste = validate_manifest(chemin)

    assert manifeste["rushes"] == []
    assert manifeste["lots"] == []


def test_les_deux_listes_sont_relachees_et_pas_seulement_l_une(tmp_path: Path) -> None:
    """Volet symetrique : un projet a rush SANS lot, et un projet a lot SANS
    rush, passent tous les deux.

    Sans lui, un relachement pose sur ``rushes`` seul rendrait le test
    precedent rouge sans dire lequel des deux ``minItems`` a survecu -- et un
    relachement pose sur ``lots`` seul le rendrait vert par accident si la
    fixture ne portait qu'une des deux listes vides.
    """
    rush_seul = manifeste_de_projet_vide()
    rush_seul["rushes"] = [{"rush_id": "rush-001", "source_path": "srcs/rush-001.mov"}]
    lot_seul = manifeste_de_projet_vide()
    lot_seul["lots"] = [{"lot_id": "lot-001", "rush_id": "rush-001"}]

    assert validate_manifest(_ecrire(tmp_path / "a.json", rush_seul))["lots"] == []
    assert validate_manifest(_ecrire(tmp_path / "b.json", lot_seul))["rushes"] == []


def test_le_schema_v2_0_fige_refuse_toujours_un_projet_vide(tmp_path: Path) -> None:
    """Frontiere negative : le schema v2.0 est FIGE, il ne se relache pas.

    `EPIC7-ARB-51` abandonne la retrocompatibilite des formats ; il n'autorise
    pas a retoucher un contrat gele. Un manifest v2.0 vide reste refuse.
    """
    vide_v2_0 = manifeste_de_projet_vide()
    vide_v2_0["schema_version"] = "2.0"
    vide_v2_0["video"] = {"fps_source": 25.0, "fps_target": 12.5}
    chemin = _ecrire(tmp_path / MANIFEST_FILENAME, vide_v2_0)

    # Le premier defaut remonte est celui du chemin le plus petit ('lots'
    # avant 'rushes') : on nomme donc les DEUX refus, un par fixture, plutot
    # que de dependre de l'ordre de tri des erreurs.
    with pytest.raises(ValidationError, match="lots"):
        validate_manifest(chemin)

    lots_seuls_v2_0 = dict(vide_v2_0)
    lots_seuls_v2_0["lots"] = [
        {"lot_id": "lot-001", "rush_id": "rush-001", "state": "extraction"}
    ]
    with pytest.raises(ValidationError, match="rushes"):
        validate_manifest(_ecrire(tmp_path / "v2-0-rushes-vides.json", lots_seuls_v2_0))


# ---------------------------------------------------------------------------
# 2. Extraction dans un projet vide -- DEUX lots, cible en seconde position
# ---------------------------------------------------------------------------


def _enregistrement(*, fps_target, project_id: str, rush_id: str = "rush-001"):
    """Un ExtractionRecord bati sur la VRAIE selection de la story 3.2."""
    selection = select_source_frames(
        fps_source=25,
        fps_target=fps_target,
        source_frame_count=50,
    )
    fps_source_type = float(selection.fps_source)
    fps_target_type = float(selection.fps_target)
    return ExtractionRecord(
        project_id=project_id,
        rush_id=rush_id,
        rush_source_name=f"{rush_id}.mov",
        lot_id=build_lot_id(rush_id, fps_target_type),
        frames_dir_relative=(
            f"{FRAMES_DIRNAME}/{rush_dir_slug(rush_id, fps_target_type)}"
        ),
        selection=selection,
        fps_source=fps_source_type,
        fps_target=fps_target_type,
        source_width=1920,
        source_height=1080,
        source_fields=dict(CHAMPS_SOURCE_TAGGES),
        confirmation_mode="non_interactif",
        unknown_color_accepted=False,
        confirmed_at="2026-08-25T09:30:00Z",
    )


def _ecrire_les_frames(dossier_projet: Path, enregistrement) -> None:
    """Poser sur disque les TIFF que la commande `extract` aurait ecrits."""
    dossier = dossier_projet / enregistrement.frames_dir_relative
    dossier.mkdir(parents=True, exist_ok=True)
    for frame in enregistrement.selection.frames:
        nom = build_extracted_frame_filename(
            enregistrement.rush_id, enregistrement.fps_target, frame.frame_timecode
        )
        (dossier / nom).write_bytes(b"tiff")


def test_deux_extractions_aboutissent_dans_un_projet_vide(tmp_path: Path) -> None:
    """Le projet cree vide est un VRAI projet du coeur : on extrait dedans.

    Deux lots distinguables (cadences 5 et 12,5), et l'assertion porte sur le
    SECOND : un chemin qui rendrait toujours la premiere entree de ``lots``
    passerait un test mono-lot.
    """
    dossier = tmp_path / "Mon Projet"
    dossier.mkdir()
    _ecrire(dossier / MANIFEST_FILENAME, manifeste_de_projet_vide("projet-vide"))

    premier = _enregistrement(fps_target=5, project_id="projet-vide")
    second = _enregistrement(fps_target=12.5, project_id="projet-vide")
    assert premier.lot_id != second.lot_id, "fabrique mono-valeur : rien ne serait mesure"

    for enregistrement in (premier, second):
        _ecrire_les_frames(dossier, enregistrement)
        persist_extraction(dossier, enregistrement)

    manifeste = validate_manifest(dossier / MANIFEST_FILENAME)
    identifiants = [lot["lot_id"] for lot in manifeste["lots"]]
    assert identifiants == [premier.lot_id, second.lot_id]

    # La cible est en SECONDE position, et c'est elle qu'on interroge.
    vise = next(lot for lot in manifeste["lots"] if lot["lot_id"] == second.lot_id)
    assert vise["fps_target"] == pytest.approx(12.5)
    assert vise["rush_id"] == "rush-001"
    # `created` du projet vide survit a l'extraction : il n'est pas reecrit.
    assert manifeste["created"] == "2026-08-25T09:00:00Z"


def test_l_extraction_dans_un_projet_vide_conserve_l_identite_du_projet(
    tmp_path: Path,
) -> None:
    """Le ``project_id`` ecrit a la creation fait foi : une extraction qui en
    declare un autre est refusee, pas silencieusement reecrite."""
    dossier = tmp_path / "Mon Projet"
    dossier.mkdir()
    _ecrire(dossier / MANIFEST_FILENAME, manifeste_de_projet_vide("projet-vide"))

    intrus = _enregistrement(fps_target=5, project_id="un-autre-projet")
    _ecrire_les_frames(dossier, intrus)

    with pytest.raises(Exception, match="project_id"):
        persist_extraction(dossier, intrus)

    # Rien n'a bouge : le manifest vide est strictement intact.
    assert load_manifest(dossier / MANIFEST_FILENAME) == manifeste_de_projet_vide(
        "projet-vide"
    )


# ---------------------------------------------------------------------------
# 3. Reconstruction (depot de scan) dans un projet vide
# ---------------------------------------------------------------------------


def _page(page_index: int, page_count: int = 2, lot_id: str = "lot-001") -> dict:
    """Payload de planche d'images decode, calque sur la fixture de 2.3."""
    return {
        "schema_version": payload_io.PAYLOAD_SCHEMA_VERSION,
        "project_id": "projet-vide",
        "rush_id": "rush-001",
        "lot_id": lot_id,
        "page_index": page_index,
        "page_count": page_count,
        "page_role": payload_io.PAGE_ROLE_IMAGES,
        "fps_target": 24.0,
        "timecode_base_fps": "25/1",
        "template_id": "template-a4-16x9",
        "patch_preset_id": "patch-preset-mvp",
        "target_colorspace": "rec709",
        "gamut_map_id": "gamut-map-none-1",
        "slots": [
            {"slot_index": page_index, "frame_timecode": f"00:00:0{page_index}:00"}
        ],
    }


def test_une_reconstruction_aboutit_dans_un_projet_vide(tmp_path: Path) -> None:
    """Variante du Flow 2 : projet cree vide, puis depot de scans.

    Le manifest local vide ne declare AUCUN rush : la garde de conflit
    (``_check_manifest_conflicts``) ne doit donc rien refuser -- elle ne mord
    que quand le manifest declare des rushs dont aucun n'est celui des pages.
    """
    vide = manifeste_de_projet_vide("projet-vide")

    manifeste = reconstruct_project_manifest([_page(0), _page(1)], existing_manifest=vide)

    assert manifeste["project_id"] == "projet-vide"
    assert [rush["rush_id"] for rush in manifeste["rushes"]] == ["rush-001"]
    assert [lot["lot_id"] for lot in manifeste["lots"]] == ["lot-001"]
    # Le document reconstruit valide contre le coeur, comme tout autre.
    validate_manifest(_ecrire(tmp_path / MANIFEST_FILENAME, manifeste))


def test_une_reconstruction_dans_un_projet_vide_n_ecrase_aucun_lot_voisin(
    tmp_path: Path,
) -> None:
    """Regle des fabriques, volet reconstruction : le manifest de depart porte
    DEUX lots distinguables et la reconstruction vise le SECOND.

    Le premier lot doit survivre a l'operation, verbatim. Un ``_merge_entries``
    qui viserait toujours la premiere entree ecraserait le mauvais lot -- c'est
    litteralement le mutant M25 de la story 5.7.
    """
    depart = manifeste_de_projet_vide("projet-vide")
    depart["rushes"] = [{"rush_id": "rush-001", "source_path": "srcs/rush-001.mov"}]
    depart["lots"] = [
        {"lot_id": "lot-000", "rush_id": "rush-001", "fps_target": 5.0, "state": "pdf"},
        {"lot_id": "lot-001", "rush_id": "rush-001", "fps_target": 24.0, "state": "pdf"},
    ]

    manifeste = reconstruct_project_manifest(
        [_page(0), _page(1)], existing_manifest=depart
    )

    lots = {lot["lot_id"]: lot for lot in manifeste["lots"]}
    assert set(lots) == {"lot-000", "lot-001"}
    assert lots["lot-000"] == depart["lots"][0], "le lot voisin a ete touche"
    assert lots["lot-001"]["state"] == "reconstruction"


# ---------------------------------------------------------------------------
# 4. Completude : verdict lisible sur un projet vide
# ---------------------------------------------------------------------------


def test_la_completude_juge_les_sections_et_non_le_cardinal_des_listes() -> None:
    """``validate_manifest_completeness`` est opt-in (appelee avant un encode).

    Sur un projet vide, elle ne parle PAS de listes vides : elle nomme la
    premiere metadonnee de projet manquante. Les boucles sur ``rushes`` et
    ``lots`` ne tournent simplement pas -- ce qui est correct : il n'y a aucun
    rush ni lot a juger incomplet.
    """
    vide = manifeste_de_projet_vide()

    with pytest.raises(ValidationError, match="codec_target"):
        validate_manifest_completeness(vide)

    # Sections renseignees, listes toujours vides : plus rien a reprocher.
    vide["video"] = {"codec_target": "prores_ks"}
    vide["color"] = {"target_colorspace": "rec709"}
    validate_manifest_completeness(vide)
