"""Tests de la story 5.11: persistance de `makepdf` au manifest.

Aucune fixture de manifest ecrite a la main: le document d'entree est toujours
produit par `build_extraction_manifest` **reel** (action item 3 de la retro de
l'Epic 4), et le plan par `compose_lot_plan` **reel**. Un `SimpleNamespace` ne
capture pas la forme que le vrai producteur emet, et c'est exactement le motif
qui a fait ajouter des tests d'integration a posteriori en revue 4.9.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest
from jsonschema.exceptions import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import cli, pdf_composition
from mixed_media_utility.frame_selection import select_source_frames
from mixed_media_utility.io import naming, pdf_manifest, project_layout
from mixed_media_utility.io.extraction_manifest import (
    ExtractionPersistenceError,
    ExtractionRecord,
    ManifestWriteError,
    build_extraction_manifest,
)
from mixed_media_utility.io.manifest import LOT_STATES, validate_manifest

PROJECT_ID = "proj-pdfmanifest"
RUSH_ID = "rush-001"
FPS_SOURCE = 25.0
FPS_TARGET = 5.0
SOURCE_FRAME_COUNT = 50  # -> 10 frames extraites


# ---------------------------------------------------------------------------
# Fixtures: le vrai producteur, jamais un dict ecrit a la main
# ---------------------------------------------------------------------------


def _frames_dir_relative(fps_target: float = FPS_TARGET) -> str:
    return (
        f"{project_layout.FRAMES_DIRNAME}/"
        f"{project_layout.rush_dir_slug(RUSH_ID, fps_target)}"
    )


def _extraction_record(fps_target: float = FPS_TARGET) -> ExtractionRecord:
    """Enregistrement d'extraction reel, coherent avec `build_lot_id`.

    Le `lot_id` n'est jamais fabrique a la main: `build_extraction_manifest`
    le recalcule et refuse un enregistrement dont les deux recettes divergent.
    """
    selection = select_source_frames(
        fps_source=FPS_SOURCE,
        fps_target=fps_target,
        source_frame_count=SOURCE_FRAME_COUNT,
    )
    return ExtractionRecord(
        project_id=PROJECT_ID,
        rush_id=RUSH_ID,
        rush_source_name=f"{RUSH_ID}.mov",
        lot_id=naming.build_lot_id(RUSH_ID, fps_target),
        frames_dir_relative=_frames_dir_relative(fps_target),
        selection=selection,
        fps_source=FPS_SOURCE,
        fps_target=fps_target,
        source_width=1920,
        source_height=1080,
        source_fields={},
        confirmation_mode="non_interactif",
        unknown_color_accepted=True,
        confirmed_at="2026-08-08T00:00:00Z",
    )


@pytest.fixture()
def lot_id() -> str:
    return naming.build_lot_id(RUSH_ID, FPS_TARGET)


@pytest.fixture()
def manifest(lot_id: str) -> dict:
    """Manifest v2.1 produit par la story 3.4, sans aucune retouche."""
    document = build_extraction_manifest(None, _extraction_record())
    document["color"]["target_colorspace"] = "rec709"
    return document


@pytest.fixture()
def record(lot_id: str) -> pdf_manifest.PdfRecord:
    return pdf_manifest.PdfRecord(
        lot_id=lot_id,
        template_id="grid-2x3-16x9-a4-portrait",
        patch_preset_id="patches-12-v1",
        gamut_map_id="gamut-map-none-1",
    )


@pytest.fixture()
def project_with_lot(tmp_path: Path, lot_id: str, manifest: dict) -> dict:
    """Projet reel sur disque: manifest 3.4 + TIFF nommes par la convention."""
    project_dir = tmp_path / "projet"
    project_layout.ensure_project_layout(project_dir)
    (project_dir / "project.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    frames_path = project_dir / Path(_frames_dir_relative())
    frames_path.mkdir(parents=True, exist_ok=True)
    selection = select_source_frames(
        fps_source=FPS_SOURCE,
        fps_target=FPS_TARGET,
        source_frame_count=SOURCE_FRAME_COUNT,
    )
    rng = np.random.default_rng(11)
    for frame in selection.frames:
        name = naming.build_extracted_frame_filename(
            RUSH_ID, FPS_TARGET, frame.frame_timecode
        )
        image = rng.integers(0, 65535, size=(108, 192, 3), dtype=np.uint16)
        assert cv2.imwrite(str(frames_path / name), image)

    return {"project_dir": project_dir, "lot_id": lot_id, "manifest": manifest}


def _lot_of(document: dict, lot_id: str) -> dict:
    return next(
        lot
        for lot in document["lots"]
        if isinstance(lot, dict) and lot.get("lot_id") == lot_id
    )


# ---------------------------------------------------------------------------
# AC 1: quatre donnees, un emplacement unique chacune
# ---------------------------------------------------------------------------


def test_the_persistence_table_names_exactly_the_four_written_fields() -> None:
    # **Cinquieme champ depuis `EPIC11-ARB-90`** : `sheets_pdfs`, l'inventaire
    # des PDF produits. La table est epinglee VALEUR PAR VALEUR, et c'est ce
    # qui fait que ce test DIT qu'un champ est arrive au lieu de le suivre en
    # silence -- il vient de le dire.
    assert pdf_manifest.PDF_LOT_FIELDS == (
        "state",
        "template_id",
        "patch_preset_id",
        "gamut_map_id",
        "sheets_pdfs",
        "sheets_version_watermark",
    )
    # `state` ne vient pas du plan: il est le seul champ pose par la garde.
    # Enonce en dur -- et non derive de `PDF_LOT_FIELDS` par un filtre, ce qui
    # etait tautologique: la table filtree suivait la constante quoi qu'elle
    # devienne (revue 5.11, couche 3; meme motif que sur 5.9).
    assert pdf_manifest.PDF_IDENTIFIER_FIELDS == (
        "template_id",
        "patch_preset_id",
        "gamut_map_id",
    )


def test_the_vocabulary_of_findings_is_closed_and_verbatim() -> None:
    """Les codes sont lus par l'operateur et grepes dans les journaux: les
    renommer en silence casse un contrat que rien d'autre ne verifie."""
    assert pdf_manifest.PDF_STATE_CONSERVED == "ETAT_DE_LOT_CONSERVE"
    assert pdf_manifest.PDF_IDENTIFIER_DIVERGES == "IDENTIFIANT_D_IMPRESSION_DIVERGENT"
    assert pdf_manifest.PDF_PERSISTENCE_CODES == (
        pdf_manifest.PDF_STATE_CONSERVED,
        pdf_manifest.PDF_IDENTIFIER_DIVERGES,
    )
    assert pdf_manifest.PDF_LOT_STATE == "pdf"


def test_the_merge_touches_only_the_four_fields_of_the_target_lot(
    manifest: dict, record: pdf_manifest.PdfRecord, lot_id: str
) -> None:
    before = json.loads(json.dumps(manifest))

    merged = pdf_manifest.build_pdf_manifest(manifest, record).manifest

    lot_before = _lot_of(before, lot_id)
    lot_after = _lot_of(merged, lot_id)
    changed = {
        key
        for key in set(lot_before) | set(lot_after)
        if lot_before.get(key) != lot_after.get(key)
    }
    # `sheets_pdfs` n'est PAS de la partie ici, et c'est la propriete :
    # ce record ne porte aucun `pdf_path`, donc l'inventaire n'est pas
    # touche. Un appelant plus ancien -- ou un chemin indisponible -- ne
    # doit ni ecrire une entree vide, ni EFFACER l'inventaire existant.
    assert changed == {"state", "template_id", "patch_preset_id",
                       "gamut_map_id"}

    # Toute section hors `lots` est recopiee telle quelle, champ par champ.
    for section in set(before) | set(merged):
        if section == "lots":
            continue
        assert merged.get(section) == before.get(section), section


def test_no_generation_timestamp_no_pdf_filename_no_page_count(
    manifest: dict, record: pdf_manifest.PdfRecord, lot_id: str
) -> None:
    merged = pdf_manifest.build_pdf_manifest(manifest, record).manifest
    lot = _lot_of(merged, lot_id)
    for forbidden in ("generated_at", "pdf_filename", "page_count", "pdf_path"):
        assert forbidden not in lot
    assert "patches_dir" not in (merged.get("artifacts") or {})


def test_the_merge_does_not_mutate_the_document_it_received(
    manifest: dict, record: pdf_manifest.PdfRecord, lot_id: str
) -> None:
    snapshot = json.dumps(manifest, sort_keys=True)
    pdf_manifest.build_pdf_manifest(manifest, record)
    assert json.dumps(manifest, sort_keys=True) == snapshot


# ---------------------------------------------------------------------------
# AC 3 / AC 4: `pdf` recoit son premier producteur v2, la garde est le seul juge
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("current", [None, "extraction", "pdf"])
def test_accepted_transitions_write_the_pdf_state(
    manifest: dict, record: pdf_manifest.PdfRecord, lot_id: str, current
) -> None:
    lot = _lot_of(manifest, lot_id)
    if current is None:
        lot.pop("state", None)
    else:
        lot["state"] = current

    merge = pdf_manifest.build_pdf_manifest(manifest, record)

    assert merge.state_written == "pdf"
    assert _lot_of(merge.manifest, lot_id)["state"] == "pdf"
    assert merge.findings == ()


@pytest.mark.parametrize("current", ["scan", "reconstruction", "encode"])
def test_downstream_states_are_conserved_without_error(
    manifest: dict, record: pdf_manifest.PdfRecord, lot_id: str, current: str
) -> None:
    """Reimprimer une planche perdue pour un lot deja scanne est nominal."""
    _lot_of(manifest, lot_id)["state"] = current

    merge = pdf_manifest.build_pdf_manifest(manifest, record)

    assert merge.state_written == current
    assert _lot_of(merge.manifest, lot_id)["state"] == current
    assert pdf_manifest.PDF_STATE_CONSERVED in merge.findings
    # ... et les trois identifiants sont bien ecrits malgre le refus d'etat:
    # ils decrivent le dernier PDF reellement produit.
    for field in pdf_manifest.PDF_IDENTIFIER_FIELDS:
        assert _lot_of(merge.manifest, lot_id)[field] == getattr(record, field)


def test_the_pdf_state_sits_between_extraction_and_scan() -> None:
    """La regle d'ordre vit dans `LOT_STATES`, pas dans une copie locale."""
    assert LOT_STATES.index("extraction") < LOT_STATES.index(pdf_manifest.PDF_LOT_STATE)
    assert LOT_STATES.index(pdf_manifest.PDF_LOT_STATE) < LOT_STATES.index("scan")


def test_the_guard_is_really_consulted_and_not_reimplemented(
    manifest: dict,
    record: pdf_manifest.PdfRecord,
    lot_id: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Aucune comparaison d'index n'est reecrite dans le module.

    Si la garde etait doublee par un test local sur `LOT_STATES`, neutraliser
    `validate_lot_state_transition` ne changerait rien -- et le lot passerait
    quand meme en `pdf`.
    """

    def refuse_tout(current, new):
        raise ValidationError("garde neutralisee pour le test")

    monkeypatch.setattr(pdf_manifest, "validate_lot_state_transition", refuse_tout)
    _lot_of(manifest, lot_id)["state"] = "extraction"

    merge = pdf_manifest.build_pdf_manifest(manifest, record)

    assert merge.state_written == "extraction"
    assert pdf_manifest.PDF_STATE_CONSERVED in merge.findings


# ---------------------------------------------------------------------------
# AC 5: regenerer un PDF ne fait jamais desapprendre le manifest
# ---------------------------------------------------------------------------


def test_a_rich_manifest_loses_nothing(
    manifest: dict, record: pdf_manifest.PdfRecord, lot_id: str
) -> None:
    """Deuxieme lot, deuxieme rush, sections annexes: rien n'est perdu."""
    second = build_extraction_manifest(manifest, _extraction_record(10.0))
    # Le document est enrichi de ce que les autres chaines y ecrivent, pour
    # que la non-perte porte sur des sections reellement peuplees.
    second.setdefault("artifacts", {})["outputs_dir"] = "outputs"
    second["video"]["codec_target"] = "prores_422"
    second["reconstruction"] = {"template_id": "grid-2x3-16x9-a4-portrait"}
    before = json.loads(json.dumps(second))

    merged = pdf_manifest.build_pdf_manifest(second, record).manifest

    assert merged["created"] == before["created"]
    assert merged["rushes"] == before["rushes"]
    assert merged["artifacts"] == before["artifacts"]
    assert merged["video"] == before["video"]
    assert merged["color"] == before["color"]
    assert merged["reconstruction"] == before["reconstruction"]
    assert len(merged["lots"]) == len(before["lots"])
    # Le lot non vise est intact, octet a octet.
    untouched = [lot for lot in merged["lots"] if lot["lot_id"] != lot_id]
    untouched_before = [lot for lot in before["lots"] if lot["lot_id"] != lot_id]
    assert untouched == untouched_before


def test_an_absent_lot_fails_without_writing_anything(
    manifest: dict, record: pdf_manifest.PdfRecord
) -> None:
    absent = pdf_manifest.PdfRecord(
        lot_id="lot-qui-n-existe-pas",
        template_id=record.template_id,
        patch_preset_id=record.patch_preset_id,
        gamut_map_id=record.gamut_map_id,
    )
    with pytest.raises(pdf_manifest.PdfLotAbsentError) as excinfo:
        pdf_manifest.build_pdf_manifest(manifest, absent)
    assert "lot-qui-n-existe-pas" in str(excinfo.value)


def test_the_lot_absent_error_stays_in_the_persistence_hierarchy() -> None:
    assert issubclass(pdf_manifest.PdfLotAbsentError, ExtractionPersistenceError)
    assert issubclass(pdf_manifest.PdfManifestAbsentError, ExtractionPersistenceError)


@pytest.mark.parametrize(
    "document",
    [
        {"schema_version": "2.1"},  # aucune cle `lots`
        {"lots": None},
        {"lots": {}},
        {"lots": "rush-001_5"},
        {"lots": []},
    ],
)
def test_a_manifest_without_a_usable_lot_list_fails_without_writing(
    record: pdf_manifest.PdfRecord, document: dict
) -> None:
    """Gardes defensives de `_find_lot`: chacune est exercee, aucune ne repose
    sur la seule bonne volonte du producteur amont."""
    with pytest.raises(pdf_manifest.PdfLotAbsentError):
        pdf_manifest.build_pdf_manifest(document, record)


def test_a_non_dict_entry_in_the_lot_list_is_stepped_over(
    manifest: dict, record: pdf_manifest.PdfRecord, lot_id: str
) -> None:
    """Une entree parasite ne doit ni faire tomber la fusion, ni detourner la
    recherche du bon lot."""
    manifest["lots"].insert(0, "pas-un-dict")
    manifest["lots"].insert(1, None)

    merge = pdf_manifest.build_pdf_manifest(manifest, record)

    assert _lot_of(merge.manifest, lot_id)["state"] == "pdf"
    assert merge.manifest["lots"][0] == "pas-un-dict"


@pytest.mark.parametrize("document", [42, "x", [1, 2], None])
def test_a_manifest_that_is_not_a_json_object_fails_in_the_hierarchy(
    record: pdf_manifest.PdfRecord, document
) -> None:
    """Un `project.json` valant `42` est un JSON valide et un manifest absurde.

    Sans garde, `dict(existing)` levait une `TypeError` **nue**, hors de la
    hierarchie que la CLI capture -- trace Python devant l'operateur (revue
    5.11, couche 2).
    """
    with pytest.raises(pdf_manifest.PdfManifestAbsentError):
        pdf_manifest.build_pdf_manifest(document, record)


def test_a_diverging_identifier_on_a_scanned_lot_is_declared(
    manifest: dict, record: pdf_manifest.PdfRecord, lot_id: str
) -> None:
    lot = _lot_of(manifest, lot_id)
    lot["state"] = "scan"
    lot["patch_preset_id"] = "patches-9-v1"

    merge = pdf_manifest.build_pdf_manifest(manifest, record)

    assert merge.diverging_fields == ("patch_preset_id",)
    assert pdf_manifest.PDF_IDENTIFIER_DIVERGES in merge.findings
    # La nouvelle valeur est ecrite: le champ decrit le dernier PDF produit.
    assert _lot_of(merge.manifest, lot_id)["patch_preset_id"] == record.patch_preset_id


def test_a_first_print_declares_no_divergence(
    manifest: dict, record: pdf_manifest.PdfRecord
) -> None:
    merge = pdf_manifest.build_pdf_manifest(manifest, record)
    assert merge.diverging_fields == ()
    assert merge.findings == ()


@pytest.mark.parametrize(
    "current", ["pdf", "scan", "reconstruction", "encode"]
)
def test_a_reprint_with_other_parameters_is_declared_in_every_state(
    manifest: dict, record: pdf_manifest.PdfRecord, lot_id: str, current: str
) -> None:
    """Amendement de l'AC 5, trouve independamment par les trois couches.

    La story restreignait le constat aux lots « au-dela de `pdf` ». C'etait
    taire le cas qui le justifie le plus: un lot en etat `pdf` est precisement
    celui dont on sait que des planches sont imprimees et **pas encore
    numerisees**. Les reimprimer autrement met en circulation deux jeux de
    planches dont les QR se contredisent.
    """
    lot = _lot_of(manifest, lot_id)
    lot["state"] = current
    lot["gamut_map_id"] = "gamut-map-lin-1"

    merge = pdf_manifest.build_pdf_manifest(manifest, record)

    assert merge.diverging_fields == ("gamut_map_id",)
    assert pdf_manifest.PDF_IDENTIFIER_DIVERGES in merge.findings


@pytest.mark.parametrize(
    "current", [None, "extraction", "pdf", "scan", "reconstruction", "encode"]
)
def test_the_divergence_code_and_the_field_list_never_disagree(
    manifest: dict, record: pdf_manifest.PdfRecord, lot_id: str, current
) -> None:
    """Le code et la liste sont deux faces du meme constat: l'un sans l'autre
    donne soit une alerte sans contenu, soit un contenu sans alerte."""
    lot = _lot_of(manifest, lot_id)
    if current is None:
        lot.pop("state", None)
    else:
        lot["state"] = current
    lot["patch_preset_id"] = "patches-9-v1"

    merge = pdf_manifest.build_pdf_manifest(manifest, record)

    assert (merge.diverging_fields != ()) == (
        pdf_manifest.PDF_IDENTIFIER_DIVERGES in merge.findings
    )
    assert set(merge.findings) <= set(pdf_manifest.PDF_PERSISTENCE_CODES)


def test_a_reprint_with_identical_parameters_declares_no_divergence(
    manifest: dict, record: pdf_manifest.PdfRecord, lot_id: str
) -> None:
    lot = _lot_of(manifest, lot_id)
    lot["state"] = "scan"
    for field in pdf_manifest.PDF_IDENTIFIER_FIELDS:
        lot[field] = getattr(record, field)

    merge = pdf_manifest.build_pdf_manifest(manifest, record)

    assert merge.diverging_fields == ()
    assert merge.findings == (pdf_manifest.PDF_STATE_CONSERVED,)


# ---------------------------------------------------------------------------
# AC 6: idempotence octet a octet
# ---------------------------------------------------------------------------


def test_no_field_is_non_idempotent() -> None:
    assert pdf_manifest.PDF_NON_IDEMPOTENT_FIELDS == ()


def test_two_identical_persistences_leave_the_file_byte_for_byte_identical(
    tmp_path: Path, manifest: dict, record: pdf_manifest.PdfRecord
) -> None:
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    (project_dir / "project.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    pdf_manifest.persist_pdf_generation(project_dir, record)
    first = (project_dir / "project.json").read_bytes()
    pdf_manifest.persist_pdf_generation(project_dir, record)
    second = (project_dir / "project.json").read_bytes()

    assert first == second


# ---------------------------------------------------------------------------
# AC 2: ecriture atomique, validee AVANT bascule
# ---------------------------------------------------------------------------


def test_a_refused_manifest_leaves_the_previous_file_strictly_intact(
    tmp_path: Path, manifest: dict, lot_id: str
) -> None:
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    manifest_path = project_dir / "project.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    before = manifest_path.read_bytes()

    # `minLength: 1` sur les trois proprietes: une chaine vide fait echouer la
    # validation du temporaire, donc `_atomic_write`, donc la persistance.
    invalide = pdf_manifest.PdfRecord(
        lot_id=lot_id,
        template_id="",
        patch_preset_id="patches-12-v1",
        gamut_map_id="gamut-map-none-1",
    )
    with pytest.raises(ManifestWriteError):
        pdf_manifest.persist_pdf_generation(project_dir, invalide)

    assert manifest_path.read_bytes() == before
    residus = [p.name for p in project_dir.iterdir() if p.name != "project.json"]
    assert residus == []


def test_a_missing_manifest_fails_without_creating_one(
    tmp_path: Path, record: pdf_manifest.PdfRecord
) -> None:
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    with pytest.raises(pdf_manifest.PdfManifestAbsentError):
        pdf_manifest.persist_pdf_generation(project_dir, record)
    assert not (project_dir / "project.json").exists()


def test_a_truncated_manifest_fails_in_the_module_hierarchy(
    tmp_path: Path, record: pdf_manifest.PdfRecord
) -> None:
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    (project_dir / "project.json").write_text('{"schema_version"', encoding="utf-8")
    with pytest.raises(ExtractionPersistenceError):
        pdf_manifest.persist_pdf_generation(project_dir, record)


def test_the_module_reuses_the_writers_of_story_3_4_instead_of_copying_them() -> None:
    """Aucune seconde version de l'ecriture atomique dans le depot."""
    from mixed_media_utility.io import extraction_manifest

    assert pdf_manifest._atomic_write is extraction_manifest._atomic_write
    assert pdf_manifest._load_existing_manifest is extraction_manifest._load_existing_manifest
    source = Path(pdf_manifest.__file__).read_text(encoding="utf-8")
    assert "os.replace" not in source
    assert "json.dumps" not in source
    assert "NamedTemporaryFile" not in source


# ---------------------------------------------------------------------------
# AC 8: les trois champs sont types au schema
# ---------------------------------------------------------------------------


def test_the_three_fields_are_declared_in_the_lot_schema(
    tmp_path: Path, manifest: dict, record: pdf_manifest.PdfRecord, lot_id: str
) -> None:
    merged = pdf_manifest.build_pdf_manifest(manifest, record).manifest
    path = tmp_path / "project.json"
    path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    validate_manifest(path)  # ne leve pas


def test_an_undeclared_lot_field_is_refused_by_the_schema(
    tmp_path: Path, manifest: dict, lot_id: str
) -> None:
    """`lots[].items` est en `additionalProperties: false`: c'est ce qui rend
    la declaration au schema bloquante et non cosmetique."""
    _lot_of(manifest, lot_id)["gamut_map_id_typo"] = "gamut-map-none-1"
    path = tmp_path / "project.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    with pytest.raises(ValidationError):
        validate_manifest(path)


@pytest.mark.parametrize(
    "field", ["template_id", "patch_preset_id", "gamut_map_id"]
)
def test_an_empty_identifier_is_refused_by_the_schema(
    tmp_path: Path, manifest: dict, lot_id: str, field: str
) -> None:
    _lot_of(manifest, lot_id)[field] = ""
    path = tmp_path / "project.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    with pytest.raises(ValidationError):
        validate_manifest(path)


def test_the_three_fields_live_on_the_lot_and_not_in_reconstruction(
    manifest: dict, record: pdf_manifest.PdfRecord, lot_id: str
) -> None:
    """`reconstruction` est unique par document: y loger une donnee de lot
    rejouerait le defaut que la v2.1 a corrige."""
    merged = pdf_manifest.build_pdf_manifest(manifest, record).manifest
    assert "gamut_map_id" not in (merged.get("reconstruction") or {})
    assert _lot_of(merged, lot_id)["gamut_map_id"] == record.gamut_map_id


# ---------------------------------------------------------------------------
# AC 7: source unique, plan -> manifest -> payload QR
# ---------------------------------------------------------------------------


def test_the_record_reads_the_plan_without_resolving_anything_again(
    project_with_lot: dict,
) -> None:
    plan = pdf_composition.compose_lot_plan(
        manifest=project_with_lot["manifest"],
        lot_id=project_with_lot["lot_id"],
        gamut_map_id="gamut-map-lin-1",
    )
    record = pdf_manifest.PdfRecord.from_plan(plan)
    assert record.lot_id == plan.lot_id
    assert record.template_id == plan.template_id
    assert record.patch_preset_id == plan.patch_preset_id
    assert record.gamut_map_id == plan.gamut_map_id


def test_the_record_carries_the_lot_id_verbatim_never_normalised() -> None:
    """Un `rush_id` capitalise doit traverser sans normalisation.

    `build_lot_id` preserve la casse (`CAM-A_5`): la moindre normalisation dans
    le chemin de persistance ferait ecrire un `lot_id` introuvable dans
    `lots[]`, donc un `PdfLotAbsentError` sur un lot qui existe.
    """

    class _PlanFactice:
        lot_id = naming.build_lot_id("CAM-A", 5.0)
        template_id = "tpl-a4-portrait-2f-v1"
        patch_preset_id = "patches-12-v1"
        gamut_map_id = "gamut-map-none-1"

    assert _PlanFactice.lot_id == "CAM-A_5"
    assert pdf_manifest.PdfRecord.from_plan(_PlanFactice).lot_id == "CAM-A_5"


def test_no_second_resolution_in_the_persistence_module() -> None:
    source = Path(pdf_manifest.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "resolve_gamut_map(",
        "resolve_patch_preset(",
        "get_template(",
        "build_lot_id(",
    ):
        assert forbidden not in source, forbidden


def test_the_persisted_identifiers_match_the_plan_and_every_qr_payload(
    project_with_lot: dict,
) -> None:
    """Coherence de bout en bout sur un lot reellement compose et rendu."""
    project_dir = project_with_lot["project_dir"]
    assert (
        cli.main(
            [
                "makepdf",
                "--project",
                str(project_dir),
                "--rush",
                RUSH_ID,
                "--fps",
                "5",
                "--gamut-map",
                "gamut-map-lin-1",
            ]
        )
        == 0
    )

    document = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    lot = _lot_of(document, project_with_lot["lot_id"])
    plan = pdf_composition.compose_lot_plan(
        manifest=project_with_lot["manifest"],
        lot_id=project_with_lot["lot_id"],
        gamut_map_id="gamut-map-lin-1",
    )

    assert lot["gamut_map_id"] == plan.gamut_map_id
    assert lot["template_id"] == plan.template_id
    assert lot["patch_preset_id"] == plan.patch_preset_id
    for page in plan.pages:
        assert page.qr.payload["gamut_map_id"] == lot["gamut_map_id"]


def test_a_substituted_identifier_in_the_persistence_path_breaks_the_coherence(
    project_with_lot: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mutation exigee par l'AC 7: substituer la valeur au seul chemin de
    persistance doit faire echouer le test de coherence precedent."""
    reel = pdf_manifest.PdfRecord.from_plan

    def mutant(plan, **extra):
        # `**extra` transporte les mots-cles additifs de `from_plan`
        # (`pdf_path`, `version_rank` depuis `EPIC11-ARB-90/91`) : ce mutant
        # substitue UN identifiant, il ne doit pas amputer le reste du record
        # au passage -- sans quoi il mesurerait sa propre amputation.
        vrai = reel(plan, **extra)
        return pdf_manifest.PdfRecord(
            lot_id=vrai.lot_id,
            template_id=vrai.template_id,
            patch_preset_id=vrai.patch_preset_id,
            gamut_map_id="gamut-map-none-1",
            pdf_path=vrai.pdf_path,
            version_rank=vrai.version_rank,
        )

    monkeypatch.setattr(pdf_manifest.PdfRecord, "from_plan", staticmethod(mutant))

    project_dir = project_with_lot["project_dir"]
    assert (
        cli.main(
            [
                "makepdf",
                "--project",
                str(project_dir),
                "--rush",
                RUSH_ID,
                "--fps",
                "5",
                "--gamut-map",
                "gamut-map-lin-1",
            ]
        )
        == 0
    )

    document = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    lot = _lot_of(document, project_with_lot["lot_id"])
    plan = pdf_composition.compose_lot_plan(
        manifest=project_with_lot["manifest"],
        lot_id=project_with_lot["lot_id"],
        gamut_map_id="gamut-map-lin-1",
    )
    assert lot["gamut_map_id"] != plan.gamut_map_id
    assert lot["gamut_map_id"] != plan.pages[0].qr.payload["gamut_map_id"]


# ---------------------------------------------------------------------------
# AC 10: le chemin CLI
# ---------------------------------------------------------------------------


def test_makepdf_declares_the_lot_at_the_manifest(project_with_lot: dict) -> None:
    project_dir = project_with_lot["project_dir"]
    before = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))

    assert (
        cli.main(
            ["makepdf", "--project", str(project_dir), "--rush", RUSH_ID, "--fps", "5"]
        )
        == 0
    )

    after = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    lot_before = _lot_of(before, project_with_lot["lot_id"])
    lot_after = _lot_of(after, project_with_lot["lot_id"])
    changed = {
        key
        for key in set(lot_before) | set(lot_after)
        if lot_before.get(key) != lot_after.get(key)
    }
    assert changed == {"state", "template_id", "patch_preset_id", "gamut_map_id",
                       "sheets_pdfs", "sheets_version_watermark"}
    assert lot_after["state"] == "pdf"


def test_a_persistence_failure_fails_the_command_and_keeps_the_pdf(
    project_with_lot: dict, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """ARB-7 transpose: PDF ecrit, manifest non ecrit = echec (`1`)."""
    project_dir = project_with_lot["project_dir"]
    before = (project_dir / "project.json").read_bytes()

    def refuse(project_dir_arg, record_arg):
        raise ManifestWriteError(
            "Manifest invalide, rien n'a ete ecrit. Le project.json precedent "
            "est intact"
        )

    monkeypatch.setattr(pdf_manifest, "persist_pdf_generation", refuse)

    code = cli.main(
        ["makepdf", "--project", str(project_dir), "--rush", RUSH_ID, "--fps", "5"]
    )

    assert code == 1
    assert (project_dir / "project.json").read_bytes() == before
    pdfs = list((project_dir / project_layout.PLANCHES_DIRNAME).glob("*.pdf"))
    assert len(pdfs) == 1  # le PDF reste sur disque pour diagnostic
    sortie = capsys.readouterr()
    assert "project.json" in (sortie.err + sortie.out)


def _set_lot(project_dir: Path, lot_id: str, **fields) -> None:
    """Poser des valeurs sur le lot du `project.json` reel, avant la commande."""
    path = project_dir / "project.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    _lot_of(document, lot_id).update(fields)
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")


def _journal(project_dir: Path) -> str:
    return (project_dir / project_layout.LOGS_DIRNAME / "makepdf.log").read_text(
        encoding="utf-8"
    )


def test_the_nominal_run_names_what_it_declared_on_stdout_and_in_the_journal(
    project_with_lot: dict, capsys
) -> None:
    """La restitution entiere pouvait disparaitre sans qu'un test ne tombe
    (revue 5.11, couches 1 et 3: cinq mutants survivants d'affilee)."""
    project_dir = project_with_lot["project_dir"]

    assert (
        cli.main(
            ["makepdf", "--project", str(project_dir), "--rush", RUSH_ID, "--fps", "5"]
        )
        == 0
    )

    sortie = capsys.readouterr().out
    assert "declare au manifest" in sortie
    document = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    lot = _lot_of(document, project_with_lot["lot_id"])
    # Les valeurs affichees sont celles **ecrites**, jamais un point
    # d'interrogation ni les valeurs du plan lues ailleurs.
    for field in pdf_manifest.PDF_IDENTIFIER_FIELDS:
        assert lot[field] in sortie
    assert "?" not in sortie.split("declare au manifest")[1].split("\n")[0]
    assert "declare au manifest" in _journal(project_dir)


def test_a_conserved_state_is_named_on_stdout_and_logged_as_information(
    project_with_lot: dict, capsys
) -> None:
    project_dir = project_with_lot["project_dir"]
    _set_lot(project_dir, project_with_lot["lot_id"], state="scan")

    assert (
        cli.main(
            ["makepdf", "--project", str(project_dir), "--rush", RUSH_ID, "--fps", "5"]
        )
        == 0
    )

    sortie = capsys.readouterr().out
    assert pdf_manifest.PDF_STATE_CONSERVED in sortie
    journal = _journal(project_dir)
    assert f"[INFO] {pdf_manifest.PDF_STATE_CONSERVED}" in journal
    document = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    assert _lot_of(document, project_with_lot["lot_id"])["state"] == "scan"


def test_a_diverging_identifier_is_named_and_logged_as_a_warning(
    project_with_lot: dict, capsys
) -> None:
    """Le niveau compte: une divergence n'est pas une information de routine,
    c'est le signal que des planches en circulation ne disent plus la verite."""
    project_dir = project_with_lot["project_dir"]
    _set_lot(
        project_dir,
        project_with_lot["lot_id"],
        state="scan",
        gamut_map_id="gamut-map-lin-1",
    )

    assert (
        cli.main(
            ["makepdf", "--project", str(project_dir), "--rush", RUSH_ID, "--fps", "5"]
        )
        == 0
    )

    sortie = capsys.readouterr().out
    assert pdf_manifest.PDF_IDENTIFIER_DIVERGES in sortie
    assert "gamut_map_id" in sortie
    assert f"[WARNING] {pdf_manifest.PDF_IDENTIFIER_DIVERGES}" in _journal(
        project_dir
    )


def test_the_returned_object_reports_the_state_actually_written(
    tmp_path: Path, manifest: dict, record: pdf_manifest.PdfRecord, lot_id: str
) -> None:
    """`state_written` ne peut pas etre fige sur `pdf`, et les constats ne
    peuvent pas etre systematiquement vides."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    _lot_of(manifest, lot_id)["state"] = "scan"
    _lot_of(manifest, lot_id)["template_id"] = "un-autre-gabarit"
    (project_dir / "project.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    persisted = pdf_manifest.persist_pdf_generation(project_dir, record)

    assert persisted.state_written == "scan"
    assert persisted.findings == (
        pdf_manifest.PDF_STATE_CONSERVED,
        pdf_manifest.PDF_IDENTIFIER_DIVERGES,
    )
    assert persisted.diverging_fields == ("template_id",)


def test_the_returned_manifest_is_the_one_on_disk(
    tmp_path: Path, manifest: dict, record: pdf_manifest.PdfRecord
) -> None:
    """Rendre le document d'**avant** fusion serait indetectable autrement, et
    ferait mentir tout appelant qui relit l'objet plutot que le fichier."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    (project_dir / "project.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    persisted = pdf_manifest.persist_pdf_generation(project_dir, record)

    assert persisted.manifest == json.loads(
        (project_dir / "project.json").read_text(encoding="utf-8")
    )


def test_an_unwritable_project_dir_fails_in_the_hierarchy_not_as_a_bare_oserror(
    tmp_path: Path,
    manifest: dict,
    record: pdf_manifest.PdfRecord,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`_atomic_write` ouvre son temporaire **avant** son propre `try`: un
    dossier projet non inscriptible ou un quota atteint remontait en `OSError`
    nue, hors de la hierarchie que la CLI capture (revue 5.11, couche 2).

    La panne est simulee a la source (`NamedTemporaryFile`) plutot que par un
    `chmod`: la suite tourne en root dans l'environnement de reference, et root
    traverse les permissions POSIX -- un dossier en lecture seule y « reussit »
    l'ecriture, ce qui rendrait ce test faussement vert. Le correctif de fond
    appartient au module de la story 3.4 et reste transverse (consigne au
    `deferred-work.md`); ici on verifie que l'erreur arrive dans la bonne
    famille et que rien n'est ecrit.
    """
    from mixed_media_utility.io import extraction_manifest

    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    manifest_path = project_dir / "project.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    before = manifest_path.read_bytes()

    def disque_plein(*args, **kwargs):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(
        extraction_manifest.tempfile, "NamedTemporaryFile", disque_plein
    )

    with pytest.raises(ExtractionPersistenceError) as excinfo:
        pdf_manifest.persist_pdf_generation(project_dir, record)

    assert "intact" in str(excinfo.value)
    assert manifest_path.read_bytes() == before
    assert [p.name for p in project_dir.iterdir()] == ["project.json"]


def test_a_lot_declared_pdf_can_no_longer_be_re_extracted(
    project_with_lot: dict,
) -> None:
    """Consequence de la story, verifiee et assumee (revue 5.11, couche 1).

    `LotStateConflictError` de la story 3.4 anticipait explicitement l'etat
    `pdf` -- « un lot deja passe en pdf porte des artefacts aval » -- mais
    aucun producteur ne posait cet etat, donc la branche etait inatteignable.
    Elle l'est desormais: re-extraire un lot dont les planches sont imprimees
    reecrirait les frames **sous** ces planches. Le refus est le comportement
    voulu, pas une regression; ce test existe pour qu'un changement de cette
    regle soit un choix et non un accident.
    """
    from mixed_media_utility.io.extraction_manifest import LotStateConflictError

    project_dir = project_with_lot["project_dir"]
    assert (
        cli.main(
            ["makepdf", "--project", str(project_dir), "--rush", RUSH_ID, "--fps", "5"]
        )
        == 0
    )

    from mixed_media_utility.io import extraction_manifest

    with pytest.raises(LotStateConflictError):
        extraction_manifest.persist_extraction(
            project_dir, _extraction_record()
        )


def test_the_command_docstring_no_longer_claims_it_never_writes_the_manifest() -> None:
    """EPIC4-ARB-4 est desormais ferme: la garde d'origine doit etre amendee."""
    docstring = cli.makepdf_command.__doc__ or ""
    assert "ne modifie jamais le manifest" not in docstring


def test_the_keyboard_interrupt_message_no_longer_promises_an_intact_manifest() -> None:
    source = Path(cli.__file__).read_text(encoding="utf-8")
    assert (
        "Aucun PDF partiel n'a ete mis en place, le manifest est inchange"
        not in source
    )


def _manifeste_avec_inventaire(manifest, lot_id, entrees):
    """Manifeste reel dont le lot vise porte deja un inventaire de tirages."""
    import copy
    document = copy.deepcopy(manifest)
    lot = next(l for l in document["lots"] if l["lot_id"] == lot_id)
    lot["sheets_pdfs"] = list(entrees)
    return document


def test_reimprimer_UN_tirage_conserve_les_AUTRES(
        manifest: dict, lot_id: str, record: pdf_manifest.PdfRecord) -> None:
    """**Mutant survivant de la campagne**, et la propriete centrale de
    l'inventaire.

    Remplacer la fusion appariee par un ecrasement (`inventaire = []`) passait
    la totalite du banc : rien ne verifiait que reimprimer le tirage 2 laisse
    les entrees des tirages 1 et 3 en place. Or c'est exactement ce que cet
    inventaire existe pour tenir -- et la trace perdue n'est pas re-derivable
    des lors qu'un fichier a ete renomme, ce qui est le cas meme qu'il couvre.

    Regle des fabriques appliquee a la liste que le code PARCOURT : trois
    entrees distinguables, **la cible au milieu**. Une fabrique a une seule
    entree ne distinguerait pas une fusion d'un ecrasement.
    """
    from dataclasses import replace

    document = _manifeste_avec_inventaire(manifest, lot_id, [
        {"path": "planches/a_planches.pdf"},
        {"path": "planches/b_planches_v2.pdf", "version_rank": 2},   # la cible
        {"path": "planches/c_planches_v3.pdf", "version_rank": 3},
    ])
    reimpression = replace(
        record, pdf_path="planches/b_planches_v2.pdf", version_rank=2)

    fusion = pdf_manifest.build_pdf_manifest(document, reimpression)

    apres = next(l for l in fusion.manifest["lots"] if l["lot_id"] == lot_id)
    chemins = [e["path"] for e in apres["sheets_pdfs"]]
    assert chemins == [
        "planches/a_planches.pdf",
        "planches/b_planches_v2.pdf",
        "planches/c_planches_v3.pdf",
    ], f"les autres tirages ont ete perdus: {chemins}"
    # L'entree visee est REMPLACEE, pas doublee.
    assert chemins.count("planches/b_planches_v2.pdf") == 1


def test_l_inventaire_est_TRIE_par_chemin_et_non_par_ordre_d_impression(
        manifest: dict, lot_id: str, record: pdf_manifest.PdfRecord) -> None:
    """`sort_keys` canonise les mappings et PAS les tableaux : un ordre
    d'insertion porterait l'ordre chronologique des impressions, c'est-a-dire
    un signal d'horloge dans un document dont l'idempotence est verifiee octet
    a octet (meme motif qu'`encoded_masters`, story 6.5)."""
    from dataclasses import replace

    document = _manifeste_avec_inventaire(manifest, lot_id, [
        {"path": "planches/zzz_planches_v9.pdf", "version_rank": 9},
    ])
    fusion = pdf_manifest.build_pdf_manifest(
        document, replace(record, pdf_path="planches/aaa_planches.pdf"))

    apres = next(l for l in fusion.manifest["lots"] if l["lot_id"] == lot_id)
    chemins = [e["path"] for e in apres["sheets_pdfs"]]
    assert chemins == sorted(chemins), (
        f"l'inventaire porte l'ordre d'impression, pas l'ordre des chemins: {chemins}"
    )


# ---------------------------------------------------------------------------
# `EPIC11-ARB-92` -- LA LIGNE D'EAU MONTE, elle ne redescend jamais ici.
#
# Le mutant `max(ligne, rang_ecrit)` -> `rang_ecrit` a survecu a DEUX campagnes
# (couches 1 et 3 de la revue du 2026-08-31), et il a ensuite disparu de la
# table de traitement des findings sans etre ferme ni verse en dette. C'est la
# propriete la plus centrale de tout ce mecanisme -- la seule memoire qui
# empeche deux planches PAPIER de porter le meme numero une fois l'encre
# seche -- et rien ne la mesurait.
#
# Cause de la survie : aucun test ne persistait deux fois un rang DECROISSANT.
# Tous les tests de ligne d'eau injectaient la valeur a la main dans un dict
# puis verifiaient qu'elle etait relue.
# ---------------------------------------------------------------------------


def _rang_persiste(project_dir: Path, lot_id: str) -> object:
    lot = _lot_of(
        json.loads((project_dir / "project.json").read_text(encoding="utf-8")),
        lot_id)
    return lot.get(pdf_manifest.SHEETS_WATERMARK_FIELD)


def test_persister_un_rang_PLUS_BAS_ne_fait_pas_REDESCENDRE_la_ligne_d_eau(
    tmp_path: Path, manifest: dict, lot_id: str
) -> None:
    """Le regime reel : reimprimer un tirage ANCIEN apres un plus recent.

    Scenario : imprimer v1, v2, v3 ; retirer le tirage 3 sans liberer son rang
    (la ligne reste a 3) ; puis reimprimer le tirage 2 sous --overwrite. Si la
    ligne redescendait a 2, le tirage suivant reprendrait le numero 3 -- deja
    sec sur une feuille.
    """
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    (project_dir / "project.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")

    def imprimer(rang: int | None):
        # Le chemin est INDISPENSABLE : la ligne d'eau ne monte qu'avec
        # l'inventaire, et un `PdfRecord` sans `pdf_path` n'ecrit rien du tout.
        # C'est ce qui a fait echouer la premiere redaction de ce test.
        fragment = "" if rang is None else f"_v{rang}"
        return pdf_manifest.persist_pdf_generation(
            project_dir,
            pdf_manifest.PdfRecord(
                lot_id=lot_id,
                template_id="grid-2x3-16x9-a4-portrait",
                patch_preset_id="patches-12-v1",
                gamut_map_id="gamut-map-none-1",
                version_rank=rang,
                pdf_path=f"planches/{lot_id}_planches{fragment}.pdf",
            ),
        )

    imprimer(None)
    imprimer(2)
    imprimer(3)
    assert _rang_persiste(project_dir, lot_id) == 3

    # Reimpression d'un rang PLUS BAS : la ligne ne bouge pas.
    imprimer(2)
    assert _rang_persiste(project_dir, lot_id) == 3, (
        "la ligne d'eau a REDESCENDU: le prochain tirage reprendrait un numero "
        "deja imprime sur une feuille."
    )
    # Et le retour a l'origine ne la fait pas redescendre non plus.
    imprimer(None)
    assert _rang_persiste(project_dir, lot_id) == 3


def test_la_ligne_d_eau_MONTE_quand_le_rang_persiste_est_plus_haut(
    tmp_path: Path, manifest: dict, lot_id: str
) -> None:
    """Controle negatif : une ligne qui ne monterait jamais serait aussi fausse.

    Sans lui, `lot[champ] = ligne` -- c'est-a-dire ignorer le rang ecrit --
    passerait le test precedent.
    """
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    (project_dir / "project.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    for rang, attendu in ((None, 1), (2, 2), (5, 5)):
        fragment = "" if rang is None else f"_v{rang}"
        pdf_manifest.persist_pdf_generation(
            project_dir,
            pdf_manifest.PdfRecord(
                lot_id=lot_id,
                template_id="grid-2x3-16x9-a4-portrait",
                patch_preset_id="patches-12-v1",
                gamut_map_id="gamut-map-none-1",
                version_rank=rang,
                pdf_path=f"planches/{lot_id}_planches{fragment}.pdf",
            ),
        )
        assert _rang_persiste(project_dir, lot_id) == attendu
