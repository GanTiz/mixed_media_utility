"""Test de jonction de bout en bout de la persistance d'extraction (story 3.4, AC 17).

Exige nommement par l'AC 17 « par la lecon 2.3/2.6 »: deux stories dont les
contrats se sont averes divergents alors que chacune etait verte de son cote,
parce que chacune testait sa moitie de la couture avec sa propre idee de
l'autre. La parade est un test qui ne connait aucune des deux moities.

Trois regles, non negociables, qui font la valeur de ce fichier:

* **Aucune selection ecrite a la main.** Toute `FrameSelection` vient de la
  vraie `frame_selection.select_source_frames` (story 3.2). Un vecteur fige en
  dur dans ce fichier testerait la copie, pas la jonction.
* **Le manifest est relu depuis le disque.** La verification porte sur le
  document tel qu'un tiers le recevrait apres transfert, jamais sur le dict
  encore en memoire cote ecrivain -- c'est la seule facon de prouver que la
  serialisation ne perd rien.
* **Les vecteurs viennent de la table de reference de la story 3.2**, dont les
  cas limites (NTSC, cadence cible non entiere, source d'une seule frame).

Aucun binaire externe: la story 3.4 ne lance aucun sous-processus.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility.codec_profiles import exact_frame_rate, validate_timecode
from mixed_media_utility.frame_selection import select_source_frames
from mixed_media_utility.io.extraction_manifest import (
    MANIFEST_FILENAME,
    VERIFY_MANIFEST_INCOHERENT,
    VERIFY_MISSING_FRAMES,
    VERIFY_NONCONFORMING_NAMES,
    VERIFY_UNEXPECTED_FRAMES,
    ExtractionRecord,
    compute_frame_timecodes_digest,
    persist_extraction,
    verify_extracted_lot,
)
from mixed_media_utility.io.manifest import load_manifest
from mixed_media_utility.io.naming import build_extracted_frame_filename, build_lot_id
from mixed_media_utility.io.project_layout import FRAMES_DIRNAME, rush_dir_slug


#: Sous-ensemble de la table de reference des Dev Notes de la story 3.2.
#: `24000/1001 -> 24000/1001` et `25 -> 12.5` sont les deux lignes qui
#: exercent respectivement la cadence NTSC et la cadence cible non entiere,
#: c'est-a-dire les deux formes que la serialisation manifest peut abimer.
REFERENCE_VECTORS = [
    pytest.param(25, 5, 100, 20, id="25-vers-5"),
    pytest.param(30, 4, 100, 14, id="30-vers-4"),
    pytest.param(24, 10, 25, 11, id="24-vers-10-sans-queue"),
    pytest.param(25, 12.5, 50, 25, id="25-vers-12p5-cible-non-entiere"),
    pytest.param(12.5, 5, 50, 20, id="12p5-vers-5-source-non-entiere"),
    pytest.param(30, 1, 100, 4, id="30-vers-1"),
    pytest.param(25, 5, 1, 1, id="source-d-une-seule-frame"),
    pytest.param("24000/1001", "24000/1001", 5, 5, id="ntsc-identite"),
]

TAGGED_SOURCE_FIELDS = {
    "source_codec": "prores",
    "source_pix_fmt": "yuv422p10le",
    "source_bit_depth": 10,
    "source_sample_aspect_ratio": "1:1",
    "source_color_primaries": "bt709",
    "source_color_trc": "bt709",
    "source_colorspace": "bt709",
    "source_color_range": "tv",
}


def build_record(
    *,
    fps_source,
    fps_target,
    source_frame_count: int,
    rush_id: str = "rush-001",
    project_id: str = "proj-001",
    source_start_timecode: str | None = None,
    source_in_timecode: str | None = None,
    source_out_timecode: str | None = None,
) -> ExtractionRecord:
    """Construire l'enregistrement d'extraction depuis la **vraie** selection 3.2."""
    selection = select_source_frames(
        fps_source=fps_source,
        fps_target=fps_target,
        source_frame_count=source_frame_count,
        source_start_timecode=source_start_timecode,
        source_in_timecode=source_in_timecode,
        source_out_timecode=source_out_timecode,
    )
    fps_source_typed = float(selection.fps_source)
    fps_target_typed = float(selection.fps_target)
    bounds = {
        "source_in_timecode": source_in_timecode,
        "source_out_timecode": source_out_timecode,
    }
    return ExtractionRecord(
        project_id=project_id,
        rush_id=rush_id,
        rush_source_name=f"{rush_id}.mov",
        lot_id=build_lot_id(rush_id, fps_target_typed, **bounds),
        frames_dir_relative=(
            f"{FRAMES_DIRNAME}/{rush_dir_slug(rush_id, fps_target_typed, **bounds)}"
        ),
        selection=selection,
        fps_source=fps_source_typed,
        fps_target=fps_target_typed,
        source_width=1920,
        source_height=1080,
        source_fields=dict(TAGGED_SOURCE_FIELDS),
        confirmation_mode="non_interactif",
        unknown_color_accepted=False,
        confirmed_at="2026-08-05T09:30:00Z",
    )


def write_lot_frames(project_dir: Path, record: ExtractionRecord) -> Path:
    """Ecrire les fichiers que la story 3.1 aurait ecrits apres extraction."""
    frames_path = project_dir / record.frames_dir_relative
    frames_path.mkdir(parents=True, exist_ok=True)
    for frame in record.selection.frames:
        name = build_extracted_frame_filename(
            record.rush_id, record.fps_target, frame.frame_timecode
        )
        (frames_path / name).write_bytes(b"tiff")
    return frames_path


def reread(project_dir: Path) -> dict:
    """Relire le manifest **depuis le disque**, comme un tiers le recevrait."""
    return load_manifest(project_dir / MANIFEST_FILENAME)


def lot_of(manifest: dict, lot_id: str) -> dict:
    return next(lot for lot in manifest["lots"] if lot["lot_id"] == lot_id)


# --------------------------------------------------------------------------
# La jonction nominale, sur la table de reference de la story 3.2
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fps_source,fps_target,source_frame_count,expected", REFERENCE_VECTORS
)
def test_selection_persistence_relecture_verification(
    tmp_path, fps_source, fps_target, source_frame_count, expected
) -> None:
    """3.2 -> 3.4 -> disque -> verification, sans aucune valeur ecrite a la main."""
    record = build_record(
        fps_source=fps_source,
        fps_target=fps_target,
        source_frame_count=source_frame_count,
    )
    assert record.selection.expected_frame_count == expected

    write_lot_frames(tmp_path, record)
    persist_extraction(tmp_path, record)

    manifest = reread(tmp_path)
    report = verify_extracted_lot(tmp_path, manifest, record.lot_id)

    assert report.ok is True, report.findings
    assert report.selection_recomputed is True, (
        "le niveau 3 doit etre atteignable sur un manifest relu du disque: "
        "sinon la verification par un tiers se reduit a un comptage de fichiers"
    )
    assert report.digest_matches is True
    assert report.expected_frame_count == expected
    assert report.observed_frame_count == expected
    assert report.missing_frames == ()
    assert report.unexpected_files == ()
    assert report.nonconforming_files == ()


@pytest.mark.parametrize(
    "fps_source,fps_target,source_frame_count,expected", REFERENCE_VECTORS
)
def test_la_selection_recalculee_depuis_le_disque_est_la_selection_ecrite(
    tmp_path, fps_source, fps_target, source_frame_count, expected
) -> None:
    """L'empreinte relue du disque reproduit celle de la selection d'origine.

    C'est la propriete que l'AC 16 promet a un tiers: le document seul suffit a
    retrouver, au bit pres, quelles images auraient du etre extraites.
    """
    record = build_record(
        fps_source=fps_source,
        fps_target=fps_target,
        source_frame_count=source_frame_count,
    )
    write_lot_frames(tmp_path, record)
    persist_extraction(tmp_path, record)

    lot = lot_of(reread(tmp_path), record.lot_id)

    assert lot["frame_timecodes_digest"] == compute_frame_timecodes_digest(
        record.selection
    )
    assert lot["expected_frame_count"] == expected
    assert lot["source_frame_count"] == source_frame_count


@pytest.mark.parametrize(
    "fps_source,fps_target,source_frame_count,expected", REFERENCE_VECTORS
)
def test_les_timecodes_du_lot_sont_interpretables_sans_le_rush(
    tmp_path, fps_source, fps_target, source_frame_count, expected
) -> None:
    """Un tiers valide chaque timecode avec la seule base declaree (AC 8).

    Les noms de fichiers sur le disque et la base de temps du manifest doivent
    se relire ensemble, sans que rien ne soit deduit du nom de dossier.
    """
    record = build_record(
        fps_source=fps_source,
        fps_target=fps_target,
        source_frame_count=source_frame_count,
    )
    frames_path = write_lot_frames(tmp_path, record)
    persist_extraction(tmp_path, record)

    lot = lot_of(reread(tmp_path), record.lot_id)
    base_fps = lot["timecode_base_fps"]

    assert "/" in base_fps, "la base doit etre un rationnel explicite, jamais '30'"
    for frame in record.selection.frames:
        validate_timecode(frame.frame_timecode, base_fps)
    assert len(list(frames_path.iterdir())) == expected


# --------------------------------------------------------------------------
# Le cas qui a motive la restructuration du 2026-08-04
# --------------------------------------------------------------------------


def test_trois_cadences_du_meme_rush_se_verifient_toutes(tmp_path) -> None:
    """Le coeur de la v2.1, exerce de bout en bout et relu du disque.

    En v2.0 le premier lot devenait invalide des qu'un second etait ecrit: la
    cadence cible etait unique pour tout le projet. Ce test echouerait
    integralement sur l'ancien schema.
    """
    records = [
        build_record(fps_source=30, fps_target=fps_target, source_frame_count=300)
        for fps_target in (3, 5, 12.5)
    ]
    assert len({record.lot_id for record in records}) == 3

    for record in records:
        write_lot_frames(tmp_path, record)
        persist_extraction(tmp_path, record)

    manifest = reread(tmp_path)
    assert len(manifest["lots"]) == 3
    assert len(manifest["rushes"]) == 1, "un seul rush, trois lots"

    for record in records:
        report = verify_extracted_lot(tmp_path, manifest, record.lot_id)
        assert report.ok is True, (record.lot_id, report.findings)
        assert report.digest_matches is True
        assert report.expected_frame_count == record.selection.expected_frame_count


def test_deux_rushs_de_cadences_source_differentes_coexistent(tmp_path) -> None:
    """Deux rushs, deux cadences source, chacun verifie avec la sienne."""
    premier = build_record(
        fps_source=25, fps_target=5, source_frame_count=100, rush_id="rush-001"
    )
    second = build_record(
        fps_source="24000/1001", fps_target=4, source_frame_count=120, rush_id="rush-002"
    )

    for record in (premier, second):
        write_lot_frames(tmp_path, record)
        persist_extraction(tmp_path, record)

    manifest = reread(tmp_path)
    assert len(manifest["rushes"]) == 2
    assert len(manifest["lots"]) == 2

    for record in (premier, second):
        report = verify_extracted_lot(tmp_path, manifest, record.lot_id)
        assert report.ok is True, (record.rush_id, report.findings)
        assert report.digest_matches is True

    rushes = {rush["rush_id"]: rush for rush in manifest["rushes"]}
    assert rushes["rush-001"]["fps_source_exact"] == exact_frame_rate(25.0)
    assert rushes["rush-002"]["fps_source_exact"] == exact_frame_rate(24000 / 1001)


# --------------------------------------------------------------------------
# Ce que la jonction doit **refuser** de declarer conforme
# --------------------------------------------------------------------------


def test_un_lot_ampute_est_detecte_apres_relecture(tmp_path) -> None:
    """Le mode de defaillance que toute la story existe pour fermer."""
    record = build_record(fps_source=30, fps_target=4, source_frame_count=100)
    frames_path = write_lot_frames(tmp_path, record)
    persist_extraction(tmp_path, record)

    for victim in sorted(frames_path.iterdir())[:3]:
        victim.unlink()

    report = verify_extracted_lot(tmp_path, reread(tmp_path), record.lot_id)

    assert report.ok is False
    assert len(report.missing_frames) == 3
    assert VERIFY_MISSING_FRAMES in report.findings
    assert report.observed_frame_count == record.selection.expected_frame_count - 3


def test_une_frame_etrangere_est_detectee_apres_relecture(tmp_path) -> None:
    record = build_record(fps_source=30, fps_target=4, source_frame_count=100)
    frames_path = write_lot_frames(tmp_path, record)
    persist_extraction(tmp_path, record)
    (frames_path / "capture-hors-lot.tiff").write_bytes(b"tiff")

    report = verify_extracted_lot(tmp_path, reread(tmp_path), record.lot_id)

    assert report.ok is False
    assert report.nonconforming_files == ("capture-hors-lot.tiff",)
    assert VERIFY_NONCONFORMING_NAMES in report.findings


def test_une_frame_d_une_autre_cadence_est_surnumeraire(tmp_path) -> None:
    """Melanger deux lots du meme rush ne doit pas passer inapercu."""
    lot_trois = build_record(fps_source=30, fps_target=3, source_frame_count=300)
    lot_cinq = build_record(fps_source=30, fps_target=5, source_frame_count=300)
    frames_path = write_lot_frames(tmp_path, lot_trois)
    persist_extraction(tmp_path, lot_trois)

    intruse = build_extracted_frame_filename(
        lot_cinq.rush_id, lot_cinq.fps_target, lot_cinq.selection.frames[1].frame_timecode
    )
    (frames_path / intruse).write_bytes(b"tiff")

    report = verify_extracted_lot(tmp_path, reread(tmp_path), lot_trois.lot_id)

    assert report.ok is False
    assert intruse in report.nonconforming_files


def test_un_manifest_altere_sur_le_disque_ne_ressort_pas_conforme(tmp_path) -> None:
    """Le document et les fichiers doivent se contredire visiblement.

    Editer la cadence source dans le fichier relu doit produire un constat
    bloquant, pas un lot conforme.
    """
    record = build_record(fps_source=30, fps_target=4, source_frame_count=100)
    write_lot_frames(tmp_path, record)
    persist_extraction(tmp_path, record)

    manifest_path = tmp_path / MANIFEST_FILENAME
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    document["rushes"][0]["fps_source"] = 2
    document["rushes"][0].pop("fps_source_exact", None)
    manifest_path.write_text(json.dumps(document, indent=2), encoding="utf-8")

    report = verify_extracted_lot(tmp_path, reread(tmp_path), record.lot_id)

    assert report.ok is False
    assert VERIFY_MANIFEST_INCOHERENT in report.findings


def test_un_digest_altere_sur_le_disque_est_detecte(tmp_path) -> None:
    record = build_record(fps_source=25, fps_target=5, source_frame_count=100)
    write_lot_frames(tmp_path, record)
    persist_extraction(tmp_path, record)

    manifest_path = tmp_path / MANIFEST_FILENAME
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    lot_of(document, record.lot_id)["frame_timecodes_digest"] = "sha256-v1:" + "0" * 64
    manifest_path.write_text(json.dumps(document, indent=2), encoding="utf-8")

    report = verify_extracted_lot(tmp_path, reread(tmp_path), record.lot_id)

    assert report.ok is False
    assert report.digest_matches is False


# --------------------------------------------------------------------------
# Bornes de timecode (story 3.7): l'intention, pas seulement la consequence
# --------------------------------------------------------------------------


def test_un_lot_borne_se_verifie_depuis_le_seul_document(tmp_path) -> None:
    """AC 8 et 9: la fenetre demandee survit au transfert, et se recalcule.

    Sans la relecture des bornes par `_recompute_selection`, le niveau 3
    reconstruit la selection du **rush entier** et l'empreinte ne correspond
    plus: un lot parfaitement extrait ressortirait non conforme chez le tiers.
    """
    record = build_record(
        fps_source=25,
        fps_target=5,
        source_frame_count=100,
        source_in_timecode="00:00:01:00",
        source_out_timecode="00:00:02:24",
    )
    assert record.selection.expected_frame_count == 10, (
        "fenetre de 50 images a 25 im/s ramenee a 5 im/s"
    )

    write_lot_frames(tmp_path, record)
    persist_extraction(tmp_path, record)

    lot = lot_of(reread(tmp_path), record.lot_id)
    assert lot["source_in_timecode"] == "00:00:01:00"
    assert lot["source_out_timecode"] == "00:00:02:24"

    report = verify_extracted_lot(tmp_path, reread(tmp_path), record.lot_id)
    assert report.ok is True, report.findings
    assert report.selection_recomputed is True
    assert report.digest_matches is True
    assert report.expected_frame_count == 10


def test_un_lot_borne_sur_un_rush_time_of_day_se_verifie(tmp_path) -> None:
    """Le cas d'ARB-18: bornes lues a l'ecran, en timecode natif.

    C'est ici que l'oubli de la soustraction de `offset_frames` se verrait, du
    cote persistance cette fois: les bornes ecrites sont des timecodes source,
    pas des indices, et le tiers doit les reinterpreter avec le meme offset.
    """
    record = build_record(
        fps_source=25,
        fps_target=5,
        source_frame_count=500,
        source_start_timecode="15:34:17:20",
        source_in_timecode="15:34:20:00",
        source_out_timecode="15:34:29:24",
    )
    write_lot_frames(tmp_path, record)
    persist_extraction(tmp_path, record)

    manifest = reread(tmp_path)
    assert manifest["rushes"][0]["source_start_timecode"] == "15:34:17:20"

    report = verify_extracted_lot(tmp_path, manifest, record.lot_id)
    assert report.ok is True, report.findings
    assert report.selection_recomputed is True
    assert report.digest_matches is True
    assert record.selection.frames[0].frame_timecode == "15:34:20:00"


def test_une_seule_borne_est_persistee_quand_une_seule_est_fournie(tmp_path) -> None:
    """`--out` seul: la cle d'entree reste absente, jamais `null` (AC 8)."""
    record = build_record(
        fps_source=25,
        fps_target=5,
        source_frame_count=100,
        source_out_timecode="00:00:01:24",
    )
    write_lot_frames(tmp_path, record)
    persist_extraction(tmp_path, record)

    lot = lot_of(reread(tmp_path), record.lot_id)
    assert "source_in_timecode" not in lot
    assert lot["source_out_timecode"] == "00:00:01:24"

    report = verify_extracted_lot(tmp_path, reread(tmp_path), record.lot_id)
    assert report.ok is True, report.findings
    assert report.digest_matches is True


def test_un_lot_non_borne_reste_indiscernable_d_un_lot_d_avant_la_story(
    tmp_path,
) -> None:
    """AC 8, regle cardinale: omis quand absent, jamais `null`."""
    record = build_record(fps_source=25, fps_target=5, source_frame_count=100)
    write_lot_frames(tmp_path, record)
    persist_extraction(tmp_path, record)

    lot = lot_of(reread(tmp_path), record.lot_id)
    assert "source_in_timecode" not in lot
    assert "source_out_timecode" not in lot


def test_une_borne_deplacee_a_la_main_sur_le_disque_est_detectee(tmp_path) -> None:
    """Une borne encore valide mais differente doit contredire l'empreinte.

    Meme patron que `test_un_manifest_altere_sur_le_disque_ne_ressort_pas_conforme`:
    le document et les fichiers doivent se contredire visiblement.
    """
    record = build_record(
        fps_source=25,
        fps_target=5,
        source_frame_count=100,
        source_in_timecode="00:00:01:00",
        source_out_timecode="00:00:02:24",
    )
    write_lot_frames(tmp_path, record)
    persist_extraction(tmp_path, record)

    manifest_path = tmp_path / MANIFEST_FILENAME
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    lot_of(document, record.lot_id)["source_in_timecode"] = "00:00:01:10"
    manifest_path.write_text(json.dumps(document, indent=2), encoding="utf-8")

    report = verify_extracted_lot(tmp_path, reread(tmp_path), record.lot_id)

    assert report.ok is False
    assert report.digest_matches is False


def test_une_borne_hors_du_rush_altere_le_manifest_le_rend_incoherent(
    tmp_path,
) -> None:
    """Borne poussee au-dela du cardinal source: constat **bloquant** (3.4).

    Le noyau refuse la fenetre; ce refus ne doit ni etre avale en silence ni
    ressortir en `SELECTION_NON_RECALCULEE`, qui n'est qu'informatif.
    """
    record = build_record(
        fps_source=25,
        fps_target=5,
        source_frame_count=100,
        source_in_timecode="00:00:01:00",
        source_out_timecode="00:00:02:24",
    )
    write_lot_frames(tmp_path, record)
    persist_extraction(tmp_path, record)

    manifest_path = tmp_path / MANIFEST_FILENAME
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    lot_of(document, record.lot_id)["source_out_timecode"] = "00:01:00:00"
    manifest_path.write_text(json.dumps(document, indent=2), encoding="utf-8")

    report = verify_extracted_lot(tmp_path, reread(tmp_path), record.lot_id)

    assert report.ok is False
    assert VERIFY_MANIFEST_INCOHERENT in report.findings


def test_un_extrait_et_une_extraction_complete_coexistent_dans_le_document(
    tmp_path,
) -> None:
    """Deux lots du meme rush a la meme cadence, distingues par les seules bornes.

    C'est la raison d'etre de l'AC 6 vue depuis le document: sans le suffixe de
    bornes, le second `persist_extraction` ecraserait le premier lot au lieu de
    s'ajouter, et les deux pointeraient le meme dossier.
    """
    complet = build_record(fps_source=25, fps_target=5, source_frame_count=100)
    extrait = build_record(
        fps_source=25,
        fps_target=5,
        source_frame_count=100,
        source_in_timecode="00:00:01:00",
        source_out_timecode="00:00:02:24",
    )
    assert complet.lot_id != extrait.lot_id
    assert complet.frames_dir_relative != extrait.frames_dir_relative

    for record in (complet, extrait):
        write_lot_frames(tmp_path, record)
        persist_extraction(tmp_path, record)

    manifest = reread(tmp_path)
    assert len(manifest["lots"]) == 2
    assert len(manifest["rushes"]) == 1, "un seul rush, deux lots"

    for record in (complet, extrait):
        report = verify_extracted_lot(tmp_path, manifest, record.lot_id)
        assert report.ok is True, (record.lot_id, report.findings)


# --------------------------------------------------------------------------
# Idempotence, vue depuis le disque
# --------------------------------------------------------------------------


def test_deux_extractions_identiques_laissent_le_meme_document(tmp_path) -> None:
    record = build_record(fps_source=30, fps_target=4, source_frame_count=100)
    write_lot_frames(tmp_path, record)

    persist_extraction(tmp_path, record)
    premier = (tmp_path / MANIFEST_FILENAME).read_text(encoding="utf-8")
    persist_extraction(tmp_path, record)
    second = (tmp_path / MANIFEST_FILENAME).read_text(encoding="utf-8")

    assert premier == second, "octet a octet: `confirmed_at` est fige dans le record"
    assert len(reread(tmp_path)["lots"]) == 1
