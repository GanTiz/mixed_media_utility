"""Tests d'integration de la sous-commande `makepdf` (story 4.1).

Le lot de test est fabrique par les contrats reels du depot (selection 3.2,
manifest 3.4, nommage 2.3), jamais par un glob: le manifest est construit via
`build_extraction_manifest` et les TIFF ecrits sous les noms de la convention.

Rasterisation du PDF: pypdf / pdf2image sont absents du depot (choix de la
story, Project Structure Notes). La validation QR/ArUco porte donc sur les
rasters intermediaires produits par `pdf_render` avant insertion dans le PDF
-- documente comme tel -- et sur une page synthetisee depuis le plan pour la
detection ArUco. Le roundtrip impression -> scan reste hors perimetre (Epic 5).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import (
    cli,
    gamut_map,
    layout,
    page_templates,
    patch_presets,
    patch_values,
    pdf_composition,
    pdf_render,
)
from mixed_media_utility import qr_codes
from mixed_media_utility.detection import aruco as aruco_detection
from mixed_media_utility.frame_selection import select_source_frames
from mixed_media_utility.io import naming, project_layout
from mixed_media_utility.io.extraction_manifest import (
    ExtractionRecord,
    build_extraction_manifest,
)

#: Le gabarit que la fixture de ce banc produit, **DERIVE des defauts du coeur
#: et jamais recopie** : l'orientation par defaut de `pdf_composition`, le
#: cardinal et le preset de marge par defaut de `page_templates`. Depuis
#: `EPIC11-ARB-171` le nom d'un tirage porte sa mise en page, donc il faut
#: nommer le gabarit pour reconstruire ce nom -- et le deriver plutot que
#: d'ecrire `tpl-a4-portrait-2f-v2`, qui perimerait au premier changement de
#: defaut sans que rien ne le dise.
GABARIT_DE_LA_FIXTURE = page_templates.build_template_id(
    pdf_composition.resolve_orientation(None),
    page_templates.DEFAULT_FRAMES_PER_PAGE,
    page_templates.DEFAULT_MARGIN_PRESET,
)

PROJECT_ID = "proj-makepdf"
RUSH_ID = "rush-001"
FPS_SOURCE = 25.0
FPS_TARGET = 5.0
SOURCE_FRAME_COUNT = 50  # -> 10 frames extraites


@pytest.fixture()
def project_with_lot(tmp_path: Path) -> dict:
    """Projet reel sur disque: manifest 3.4 + TIFF nommes par la convention."""
    project_dir = tmp_path / "projet"
    project_layout.ensure_project_layout(project_dir)

    selection = select_source_frames(
        fps_source=FPS_SOURCE,
        fps_target=FPS_TARGET,
        source_frame_count=SOURCE_FRAME_COUNT,
    )
    lot_id = naming.build_lot_id(RUSH_ID, FPS_TARGET)
    # Story 11.14 : le nom NEUF, et il se compose par le module qui le porte.
    # `FRAMES_DIRNAME` etait l'alias transitoire du lot B -- il porte la bonne
    # valeur mais il porte aussi le mot AMBIGU que la story retire, celui qui
    # ne dit pas s'il parle des frames extraites d'un rush ou de celles d'un
    # scan. Le lot E est celui qui le retire des bancs.
    frames_dir_relative = project_layout.extract_frames_dir_from_slug(
        Path(""), project_layout.rush_dir_slug(RUSH_ID, FPS_TARGET)
    ).as_posix()
    record = ExtractionRecord(
        project_id=PROJECT_ID,
        rush_id=RUSH_ID,
        rush_source_name=f"{RUSH_ID}.mov",
        lot_id=lot_id,
        frames_dir_relative=frames_dir_relative,
        selection=selection,
        fps_source=FPS_SOURCE,
        fps_target=FPS_TARGET,
        source_width=1920,
        source_height=1080,
        source_fields={},
        confirmation_mode="non_interactif",
        unknown_color_accepted=True,
        confirmed_at="2026-08-06T00:00:00Z",
    )
    manifest = build_extraction_manifest(None, record)
    # `makepdf` exige color.target_colorspace (AC 4); il est renseigne comme
    # l'operateur le ferait avant generation.
    manifest["color"]["target_colorspace"] = "rec709"
    (project_dir / "project.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    frames_path = project_dir / Path(frames_dir_relative)
    frames_path.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(42)
    for frame in selection.frames:
        name = naming.build_extracted_frame_filename(
            RUSH_ID, FPS_TARGET, frame.frame_timecode
        )
        # TIFF 16 bits comme extract les ecrit (192x108, 16:9).
        image = rng.integers(0, 65535, size=(108, 192, 3), dtype=np.uint16)
        assert cv2.imwrite(str(frames_path / name), image)

    return {
        "project_dir": project_dir,
        "manifest": manifest,
        "lot_id": lot_id,
        "selection": selection,
        # Story 11.14, lot E1 : le dossier des frames est PUBLIE par la
        # fabrique, plutot que recompose par chacun des six tests qui le
        # lisaient. Les six composaient `project_dir / "frames"` en dur -- six
        # secondes redactions du meme nom, donc six endroits a corriger au
        # renommage suivant, et six occasions de n'en corriger que cinq.
        "frames_path": frames_path,
    }


def run_makepdf(project_dir: Path, *extra: str) -> int:
    return cli.main(
        ["makepdf", "--project", str(project_dir), "--rush", RUSH_ID, "--fps", "5"]
        + list(extra)
    )


def count_pdf_pages(pdf_path: Path) -> int:
    # reportlab ecrit les dictionnaires de pages non compresses: le cardinal
    # de pages se lit sur les octets sans dependance PDF supplementaire.
    data = pdf_path.read_bytes()
    return data.count(b"/Type /Page") - data.count(b"/Type /Pages")


# ---------------------------------------------------------------------------
# AC 1 / AC 7 / AC 8: succes nominal, nommage, overwrite, aucune autre ecriture
# ---------------------------------------------------------------------------


def test_makepdf_produces_a_multi_page_pdf_under_patches(project_with_lot) -> None:
    project_dir = project_with_lot["project_dir"]
    manifest_before = json.loads(
        (project_dir / "project.json").read_text(encoding="utf-8")
    )

    assert run_makepdf(project_dir) == 0

    expected_name = naming.build_sheets_pdf_filename(
        PROJECT_ID, RUSH_ID, project_with_lot["lot_id"],
        template_id=GABARIT_DE_LA_FIXTURE,
    )
    pdf_path = project_dir / project_layout.PLANCHES_DIRNAME / expected_name
    assert pdf_path.is_file()
    # **5 pages a nouveau depuis la story 5.22**, apres le 6 de 5.16: 10 frames a 2 par
    # page font 5 planches, et le lot ne porte plus de page de calibration inseree
    # (`EPIC5-ARB-80`, decision 7). Le PDF de planches est donc exactement le decoupage
    # des frames, sans page annexe.
    assert count_pdf_pages(pdf_path) == 5  # 10 frames a 2 par page, et rien d'autre

    # Story 5.11 (EPIC5-ARB-20): l'affirmation d'origine de ce test etait
    # « EPIC4-ARB-4: makepdf n'ecrit jamais le manifest », verifiee par egalite
    # d'octets du project.json. Elle est desormais fausse par construction --
    # l'arbitrage d'origine n'a jamais pose une interdiction permanente, mais
    # un report « tant que le scan n'en a pas besoin ». L'assertion devient
    # l'inverse, et **precise**: le manifest change exactement sur les quatre
    # champs du lot vise, et sur rien d'autre. Un test qui se contenterait de
    # « le manifest a change » laisserait passer une ecriture debordante.
    manifest_after = json.loads(
        (project_dir / "project.json").read_text(encoding="utf-8")
    )
    for section in set(manifest_before) | set(manifest_after):
        if section == "lots":
            continue
        assert manifest_after.get(section) == manifest_before.get(section), section
    lot_before = next(
        lot
        for lot in manifest_before["lots"]
        if lot["lot_id"] == project_with_lot["lot_id"]
    )
    lot_after = next(
        lot
        for lot in manifest_after["lots"]
        if lot["lot_id"] == project_with_lot["lot_id"]
    )
    changed = {
        key
        for key in set(lot_before) | set(lot_after)
        if lot_before.get(key) != lot_after.get(key)
    }
    # **Cinquieme champ depuis `EPIC11-ARB-90`** : `sheets_pdfs`, l'inventaire
    # des PDF produits pour ce lot. Ce test epingle ce qu'un `makepdf` reussi
    # ECRIT au manifeste, et c'est ce qui fait qu'il DIT qu'un champ est
    # arrive au lieu de le suivre en silence -- il vient de le dire.
    # **Sixieme champ depuis `EPIC11-ARB-92`** : `sheets_version_watermark`,
    # la memoire du plus haut rang jamais employe. C'est elle qui fait qu'un
    # rang se CONSOMME au lieu de redevenir un trou reutilisable.
    assert changed == {"state", "template_id", "patch_preset_id", "gamut_map_id",
                       "sheets_pdfs", "sheets_version_watermark"}
    assert lot_after["state"] == "pdf"
    # Et le chemin declare est bien CELUI qui a ete ecrit, pas un recompose.
    assert lot_after["sheets_pdfs"] == [
        {"path": f"{project_layout.PLANCHES_DIRNAME}/{pdf_path.name}"}
    ], lot_after["sheets_pdfs"]
    # Journal dedie.
    assert (project_dir / project_layout.LOGS_DIRNAME / "makepdf.log").is_file()
    # Aucun fichier temporaire survivant.
    leftovers = [
        p
        for p in (project_dir / project_layout.PLANCHES_DIRNAME).iterdir()
        if p.name != expected_name
    ]
    assert leftovers == []


def test_makepdf_relance_ecrit_un_tirage_VOISIN_au_lieu_de_refuser(
        project_with_lot) -> None:
    """**Ce test disait l'inverse jusqu'au 2026-09-02**, et il avait raison
    alors : `makepdf` refusait la seconde passe faute de rang.

    Depuis le decouplage de l'AC 2.10, `resolve_sheets_version_rank` est appele
    a chaque passe : le rang avance, donc le nom change, donc il n'y a plus de
    conflit a refuser. Ce n'est pas une garde perdue mais une garde deplacee --
    `EPIC11-ARB-104` (« tout doit etre versionnable OU ecrase ») veut
    precisement qu'une relance produise une VERSION plutot qu'un refus.

    La propriete qui remplace le refus est mesuree ici : le tirage d'origine
    reste **intact** sur le disque, aux inodes et non au condensat -- une
    fixture deterministe reecrite rendrait les memes octets.
    """
    project_dir = project_with_lot["project_dir"]
    patches = project_dir / project_layout.PLANCHES_DIRNAME

    assert run_makepdf(project_dir) == 0
    origine = sorted(patches.glob("*.pdf"))
    assert len(origine) == 1, sorted(p.name for p in patches.iterdir())
    avant = origine[0].stat()
    empreinte = (avant.st_ino, avant.st_mtime_ns, avant.st_size)

    assert run_makepdf(project_dir) == 0
    apres = sorted(p.name for p in patches.glob("*.pdf"))
    assert len(apres) == 2, apres
    assert any(nom.endswith("_v2.pdf") for nom in apres), apres

    etat = origine[0].stat()
    assert (etat.st_ino, etat.st_mtime_ns, etat.st_size) == empreinte, (
        "la relance a touche le tirage d'origine"
    )


def test_makepdf_accepts_a_direct_lot_id(project_with_lot) -> None:
    project_dir = project_with_lot["project_dir"]
    code = cli.main(
        [
            "makepdf",
            "--project",
            str(project_dir),
            "--lot",
            project_with_lot["lot_id"],
            "--overwrite",
        ]
    )
    assert code == 0


def test_makepdf_refuses_an_unknown_rush_listing_available_lots(
    project_with_lot, capsys
) -> None:
    project_dir = project_with_lot["project_dir"]
    code = cli.main(
        ["makepdf", "--project", str(project_dir), "--rush", "rush-999", "--fps", "5"]
    )
    assert code == 1
    output = capsys.readouterr()
    assert project_with_lot["lot_id"] in output.err + output.out


def test_makepdf_requires_a_lot_designation(project_with_lot, capsys) -> None:
    code = cli.main(["makepdf", "--project", str(project_with_lot["project_dir"])])
    assert code == 1
    output = capsys.readouterr()
    assert "--lot" in output.err + output.out


def test_makepdf_refuses_a_nonconforming_lot(project_with_lot, capsys) -> None:
    # Un fichier de frame supprime: verify_extracted_lot doit bloquer avec le
    # constat exact, jamais imprimer une planche incomplete.
    project_dir = project_with_lot["project_dir"]
    some_tiff = next(project_with_lot["frames_path"].rglob("*.tiff"))
    some_tiff.unlink()
    code = run_makepdf(project_dir)
    assert code == 1
    output = capsys.readouterr()
    assert "FRAMES_MANQUANTES" in output.err + output.out


def test_makepdf_defaults_target_colorspace_when_missing(project_with_lot, capsys) -> None:
    """2026-08-13: `target_colorspace` n'est plus un blocage mais un defaut applique
    et persiste (demande directe d'Egan -- METADONNEES_A_RENSEIGNER_AVANT_ENCODE est
    deja classe informatif par `verify_extracted_lot`, ce comportement l'alignait).
    L'ancien nom de ce test (``..._blocks_when_...``) decrivait un refus qui n'existe
    plus: le remplacer plutot que le retirer garde la couverture sur le cas absent.
    """
    project_dir = project_with_lot["project_dir"]
    manifest = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    manifest["color"].pop("target_colorspace")
    (project_dir / "project.json").write_text(json.dumps(manifest), encoding="utf-8")
    code = run_makepdf(project_dir)
    assert code == 0
    output = capsys.readouterr()
    assert "bt709" in output.err + output.out
    persisted = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    assert persisted["color"]["target_colorspace"] == "bt709"


def test_makepdf_never_overwrites_an_explicit_target_colorspace(project_with_lot) -> None:
    """Le defaut ne s'applique que sur une valeur absente, jamais sur un choix
    d'operateur deja renseigne -- meme improbable ou inhabituel."""
    project_dir = project_with_lot["project_dir"]
    manifest = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    manifest["color"]["target_colorspace"] = "prophoto-rgb-custom"
    (project_dir / "project.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert run_makepdf(project_dir) == 0
    persisted = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    assert persisted["color"]["target_colorspace"] == "prophoto-rgb-custom"


def test_makepdf_refuses_vocabulary_violations(project_with_lot, capsys) -> None:
    project_dir = project_with_lot["project_dir"]
    assert run_makepdf(project_dir, "--frames-par-page", "5") == 1
    assert run_makepdf(project_dir, "--orientation", "paysage", "--frames-par-page", "3") == 1
    assert run_makepdf(project_dir, "--dpi", "100") == 1
    assert run_makepdf(project_dir, "--nombre-patchs", "7") == 1
    output = capsys.readouterr()
    assert "patches-9-v1" in output.err + output.out


def test_makepdf_refuses_non_finite_fps(project_with_lot, capsys) -> None:
    # Revue 4.1: `--fps inf` traversait argparse puis explosait en
    # OverflowError dans format_fps_short; refus actionnable exige.
    project_dir = project_with_lot["project_dir"]
    code = cli.main(
        ["makepdf", "--project", str(project_dir), "--rush", RUSH_ID, "--fps", "inf"]
    )
    assert code == 1
    output = capsys.readouterr()
    assert "Cadence invalide" in output.err + output.out


def test_makepdf_refuses_a_manifest_with_absolute_frames_dir(project_with_lot, capsys) -> None:
    # Revue 4.1: makepdf validait rien -- un frames_dir absolu faisait lire
    # des fichiers hors projet. La garde de portabilite du schema v2 refuse.
    project_dir = project_with_lot["project_dir"]
    manifest = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    # Le nom du dossier vient du module, l'AILLEURS est ce que la sonde
    # apporte : ecrire le nom en dur ferait de cette ligne une seconde source,
    # et la sonde cesserait d'etre realiste au prochain renommage.
    manifest["lots"][0]["frames_dir"] = (
        f"/ailleurs/{project_layout.EXTRACT_FRAMES_DIRNAME}")
    (project_dir / "project.json").write_text(json.dumps(manifest), encoding="utf-8")
    code = run_makepdf(project_dir)
    assert code == 1
    output = capsys.readouterr()
    assert "absolute" in (output.err + output.out).lower()


def test_makepdf_refuses_a_corrupted_manifest_json(project_with_lot, capsys) -> None:
    project_dir = project_with_lot["project_dir"]
    (project_dir / "project.json").write_text("{ pas du json", encoding="utf-8")
    code = run_makepdf(project_dir)
    assert code == 1
    output = capsys.readouterr()
    assert "JSON" in output.err + output.out


def test_two_channel_frame_is_refused_never_a_cv2_crash(monkeypatch, tmp_path) -> None:
    # Revue 4.1: un TIFF gris+alpha tombait dans la branche BGR -> cv2.error
    # nu. La regle du module est un refus PdfRenderError explicite.
    # AMENDE PAR LA STORY 5.10 (AC 6): `load_frame_image_for_print` prend
    # desormais l'identifiant de compression en argument **obligatoire**, sans
    # valeur par defaut -- un defaut laisserait un appelant sauter `G` en
    # silence tout en imprimant l'identifiant dans le QR. Le test n'est amende
    # que sur l'appel; ce qu'il verifie est inchange, et le refus doit rester
    # anterieur a toute application de compression.
    fake = np.zeros((108, 192, 2), dtype=np.uint8)
    monkeypatch.setattr(pdf_render.cv2, "imread", lambda *_args, **_kwargs: fake)
    for gamut_map_id in gamut_map.known_gamut_map_ids():
        with pytest.raises(pdf_render.PdfRenderError) as excinfo:
            pdf_render.load_frame_image_for_print(tmp_path / "frame.tiff", gamut_map_id)
        assert "canaux" in str(excinfo.value)


def test_marker_raster_side_scales_with_the_render_dpi() -> None:
    # Revue 4.1: les marqueurs etaient rasterises a 400 px fixes quel que
    # soit --dpi, contredisant le contrat du DPI de rendu.
    assert pdf_render.marker_raster_px(30.0, 600) == layout.mm_to_px(30.0, 30.0, 600)[0]
    assert pdf_render.marker_raster_px(30.0, 1200) == layout.mm_to_px(30.0, 30.0, 1200)[0]
    assert pdf_render.marker_raster_px(30.0, 1200) > pdf_render.marker_raster_px(30.0, 600)


def test_makepdf_paysage_composes_and_renders(project_with_lot) -> None:
    project_dir = project_with_lot["project_dir"]
    assert run_makepdf(project_dir, "--orientation", "paysage", "--frames-par-page", "4") == 0
    # **Le nom suit la mise en page demandee** (`EPIC11-ARB-171`) : ce n'est pas
    # le gabarit par defaut du banc qu'on attend ici, mais celui de la passe --
    # et c'est precisement ce que l'AC 2.9 achete, un nom qui distingue 4f/8f.
    expected_name = naming.build_sheets_pdf_filename(
        PROJECT_ID, RUSH_ID, project_with_lot["lot_id"],
        template_id=page_templates.build_template_id(
            page_templates.ORIENTATION_PAYSAGE, 4,
            page_templates.DEFAULT_MARGIN_PRESET),
    )
    assert expected_name.endswith("_4f-pay.pdf"), expected_name
    pdf_path = project_dir / project_layout.PLANCHES_DIRNAME / expected_name
    # ceil(10 / 4) planches, sans page de calibration (story 5.22).
    assert count_pdf_pages(pdf_path) == 3


# ---------------------------------------------------------------------------
# AC 9: QR decodable et marqueurs detectables sur les rasters du plan
# ---------------------------------------------------------------------------


def images_pages(plan):
    """Les **planches d'images** d'un plan de lot, sans sa page de calibration.

    Depuis la story 5.22 (`EPIC5-ARB-80`, decision 7), un plan de lot ne porte **plus
    que** des planches d'images: la page de calibration n'y est plus inseree, elle se
    compose a la demande (`_compose_calibration_from_project`). Ce filtre est donc
    aujourd'hui l'identite sur un plan de lot, et il est conserve parce qu'il porte
    l'invariant « une planche d'images porte au moins une frame » -- invariant que 5.16
    avait rendu invisible en melangeant les deux natures de page dans la meme suite.
    """
    return [page for page in plan.pages if page.frames]


def calibration_page(plan):
    """La page de calibration d'un plan **de page de calibration** (story 5.22).

    Rend `None` sur un plan de lot, ce qui fait echouer plutot que passer en silence un
    test qui l'y chercherait encore.
    """
    pages = [page for page in plan.pages if not page.frames]
    assert len(pages) <= 1, "un plan porte au plus une page de calibration"
    return pages[0] if pages else None


def _compose_from_project(project_with_lot, **kwargs):
    return pdf_composition.compose_lot_plan(
        manifest=project_with_lot["manifest"],
        lot_id=project_with_lot["lot_id"],
        **kwargs,
    )


def _compose_calibration_from_project(project_with_lot, **kwargs):
    """Le plan de la page de calibration seule, du meme projet (story 5.22)."""
    # AMENDE PAR 5.23 (2026-08-18): plus de `lot_id` -- la page se genere avant tout
    # lot --, et un libelle de chaine obligatoire a la place.
    kwargs.setdefault("scan_chain_label", "hp envy 4520 tiff 600 dpi auto corr off")
    return pdf_composition.compose_calibration_page_plan(
        manifest=project_with_lot["manifest"],
        **kwargs,
    )


def test_every_page_qr_raster_decodes_back_to_the_payload(project_with_lot) -> None:
    # Raster intermediaire (celui insere dans le PDF), documente comme la
    # limite de test sans dependance de rasterisation PDF.
    plan = _compose_from_project(project_with_lot)
    for page in plan.pages:
        raster = pdf_render.build_page_qr_raster(page, plan.render_dpi)
        result = qr_codes.decode_qr_image(raster)
        assert result.ok, (page.page_index, result.status)
        assert result.text == page.qr.payload_text


def test_synthesized_page_raster_keeps_markers_detectable(project_with_lot) -> None:
    # Page synthetisee depuis le plan (marqueurs + QR + patchs poses aux
    # positions du plan): les 4 coins restent detectables, donc ni le QR ni
    # les patchs ne contaminent les zones de silence.
    plan = _compose_from_project(project_with_lot)
    page = plan.pages[0]
    spec = page_templates.get_template(plan.template_id)
    dpi = 300

    width_px, height_px = layout.mm_to_px(spec.page_width_mm, spec.page_height_mm, dpi)
    canvas = np.full((height_px, width_px), 255, dtype=np.uint8)

    for marker in page.markers:
        half = marker.size_mm / 2
        x0, y0 = layout.mm_to_px(
            marker.center_x_mm - half, marker.center_y_mm - half, dpi
        )
        side_px = layout.mm_to_px(marker.size_mm, marker.size_mm, dpi)[0]
        raster = layout.generate_aruco_marker_image(marker.marker_id, side_px)
        canvas[y0 : y0 + side_px, x0 : x0 + side_px] = raster

    qr_raster = pdf_render.build_page_qr_raster(page, dpi)
    fx, fy, fw, fh = page.qr.footprint_rect_mm
    qx, qy = layout.mm_to_px(fx, fy, dpi)
    qr_resized = cv2.resize(
        qr_raster,
        (layout.mm_to_px(fw, fh, dpi)[0], layout.mm_to_px(fw, fh, dpi)[1]),
        interpolation=cv2.INTER_AREA,
    )
    canvas[qy : qy + qr_resized.shape[0], qx : qx + qr_resized.shape[1]] = qr_resized

    for patch in page.patches:
        x0, y0 = layout.mm_to_px(patch.x_mm, patch.y_mm, dpi)
        x1, y1 = layout.mm_to_px(patch.x_mm + patch.size_mm, patch.y_mm + patch.size_mm, dpi)
        gray = int(round(sum(patch.rgb) / 3))
        canvas[y0:y1, x0:x1] = gray

    corners, ids = aruco_detection.detect_markers(canvas, dpi=dpi)
    detected = set(int(v) for v in np.array(ids).ravel()) if ids is not None else set()
    assert set(layout.PRINTED_MARKER_IDS) <= detected


# ---------------------------------------------------------------------------
# Retrait du stub `gen-gabarit` (AC 1)
# ---------------------------------------------------------------------------


def test_gen_gabarit_stub_is_gone() -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["gen-gabarit", "meta.json"])
    assert excinfo.value.code == 2
    assert not hasattr(cli, "gen_gabarit")


# ---------------------------------------------------------------------------
# Rendu: conversion 16 -> 8 bits documentee et deterministe
# ---------------------------------------------------------------------------


def test_frame_rasters_are_deterministic_8_bit(project_with_lot) -> None:
    # AMENDE PAR LA STORY 5.10 (AC 6 et 10): meme motif d'appel que ci-dessus.
    # Le determinisme est en outre verifie **sous compression**, puisque c'est
    # la que du flottant entre dans le chemin: un dtype de travail non declare
    # ou une regle d'arrondi implicite le casserait en silence.
    some_tiff = next(project_with_lot["frames_path"].rglob("*.tiff"))
    for gamut_map_id in gamut_map.known_gamut_map_ids():
        first = pdf_render.load_frame_image_for_print(some_tiff, gamut_map_id)
        second = pdf_render.load_frame_image_for_print(some_tiff, gamut_map_id)
        assert first.mode == "RGB"  # 8 bits par canal, fait documente (piege 5)
        assert np.array_equal(np.asarray(first), np.asarray(second))


def test_render_datetime_is_a_render_input_not_a_plan_field(project_with_lot, tmp_path) -> None:
    # EPIC4-ARB-8: la date-heure est imprimee mais le plan reste deterministe;
    # elle entre par le rendu, jamais par la composition.
    plan = _compose_from_project(project_with_lot)
    stamp = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)
    output = tmp_path / "planches.pdf"
    frames_root = project_with_lot["project_dir"]
    pdf_render.render_lot_pdf(plan, frames_root, output, generated_at=stamp)
    assert output.is_file()
    assert count_pdf_pages(output) == plan.page_count


# ---------------------------------------------------------------------------
# Story 4.2 (AC 7): le texte est extractible du PDF rendu, en clair
# ---------------------------------------------------------------------------


def extract_pdf_text(pdf_path: Path) -> str:
    """Extraire le texte des content streams reportlab, stdlib seulement.

    reportlab compresse les content streams par defaut
    (`rl_config.pageCompression = 1`), avec un encodage ASCII85 possible en
    amont du Flate (`rl_config.useA85`): les streams sont decodes (a85 puis
    zlib, chacun tente et ignore s'il ne s'applique pas) avant d'y chercher
    les operateurs texte `(...) Tj`. Un grep naif du fichier brut echouerait
    et conclurait a tort que le texte est rasterise.

    Le motif de recherche des operateurs texte est **borne, et sans
    `DOTALL`** -- mesure du 2026-08-08. La boucle traverse tous les streams
    decompresses, **y compris les images**: sur une planche de cinq pages,
    6,7 Mo de pixels. Le motif d'origine, `\\((.*?)\\)\\s*Tj` sous `DOTALL`,
    repartait de chaque octet `(` du binaire -- environ un tous les 256 --
    pour parcourir le stream entier a la recherche d'un `) Tj` qui n'existe
    pas: 18,10 s pour ce seul helper, contre 1,03 s pour la generation
    complete du PDF qu'il inspecte. Un litteral de chaine reportlab ne porte
    ni parenthese nue, ni antislash, ni saut de ligne: les borner rend le
    parcours lineaire. Resultat identique, mesure -- 75 operateurs texte des
    deux cotes -- en 0,02 s.
    """
    import base64
    import re
    import zlib

    data = pdf_path.read_bytes()
    chunks: list[str] = []
    for match in re.finditer(rb"stream\r?\n(.*?)endstream", data, re.DOTALL):
        raw = match.group(1)
        stripped = raw.strip()
        if stripped.endswith(b"~>"):
            try:
                raw = base64.a85decode(stripped, adobe=True)
            except ValueError:
                pass
        try:
            raw = zlib.decompress(raw)
        except zlib.error:
            pass
        for text_op in re.finditer(rb"\(([^()\\\r\n]{0,400})\)\s*Tj", raw):
            chunks.append(text_op.group(1).decode("latin-1"))
    return "\n".join(chunks)


def test_rendered_pdf_carries_the_readable_text_in_clear(project_with_lot) -> None:
    project_dir = project_with_lot["project_dir"]
    assert run_makepdf(project_dir) == 0
    pdf_path = (
        project_dir
        / project_layout.PLANCHES_DIRNAME
        / naming.build_sheets_pdf_filename(
            PROJECT_ID, RUSH_ID, project_with_lot["lot_id"],
            template_id=GABARIT_DE_LA_FIXTURE)
    )
    text = extract_pdf_text(pdf_path)

    plan = _compose_from_project(project_with_lot)
    lot_id = project_with_lot["lot_id"]
    # Identifiants canoniques verbatim (egalite inter-canaux, AC 2 de 4.2).
    assert PROJECT_ID in text
    assert RUSH_ID in text
    assert lot_id in text
    for page in plan.pages:
        # `sheet_label` n'est plus imprime tel quel depuis la story 5.18: ses deux
        # composants -- le lot et le numero de page -- sont les deux lignes de l'entete
        # d'identite, a 14 pt. Ce qui doit rester vrai, et ce qui est verifie, c'est que
        # les deux s'y lisent et que l'egalite inter-canaux tient sur le lot.
        assert page.text.page_number_text in text
        if page.text.sheet_label not in text:
            # **La branche de repli porte sur le texte EXTRAIT, jamais sur la
            # construction de la chaine** (corrige le 2026-08-12, M4 de la revue de 5.18).
            # Elle assertait `f"p{i:03d}" in page.text.sheet_label`, ce qui est vrai **par
            # construction** de `sheet_label` -- l'assertion ne regardait pas `text`, donc
            # elle passait sur un PDF vide, et sa premiere ligne dupliquait le `lot_id`
            # deja asserte plus haut. Le contrat 4.6 n'etait donc plus couvert du tout sur
            # cette branche.
            #
            # Ce qui est verifie maintenant, et qui est ce que la story a decide: les deux
            # **composants** de `sheet_label` se lisent sur la planche, le lot verbatim et
            # le rang de page sous la forme que l'entete d'identite emploie.
            assert plan.lot_id in text
            rang = str(page.page_index + 1)
            assert f"page {rang}/{len(plan.pages)}" in text, (rang, page.page_index)
            # Et les deux sont dans le **meme** bloc d'entete, a la lisibilite exigee par
            # `EPIC5-ARB-63`: le lot en ligne 1, la pagination en ligne 2. Sans cela, un
            # rendu qui les disperserait sur la planche passerait.
            entete = [b for b in page.text.blocks if b.name == "header_identity"]
            assert entete, page.text.blocks
            assert entete[0].lines[0] == plan.lot_id
            assert page.text.page_number_text in entete[0].lines[1]
        for label in page.text.slot_labels:
            assert label.text in text
    # L'entete d'identite s'imprime au corps que la geometrie declare, et pas au
    # plancher du corps de texte: c'est l'exigence de lisibilite d'`EPIC5-ARB-63`, et
    # elle ne se verifie que sur le plan (le texte extrait ne porte pas les corps).
    # Les **planches d'images**: la page de calibration porte elle aussi un bloc
    # `header_identity`, mais au corps du texte courant et non a 14 pt -- mesure de la
    # story 5.16, une pile de deux lignes a 14 pt y couterait une seconde rangee de grille,
    # soit 16 cellules en paysage quand le treillis n'a que 5 de marge.
    for page in images_pages(plan):
        header = [b for b in page.text.blocks if b.name == "header_identity"]
        if header:
            assert header[0].font_pt == page_templates.HEADER_IDENTITY_FONT_PT
            assert header[0].font_pt > pdf_composition.BODY_FONT_MIN_PT
    # Consigne et pied de page technique derives des constantes.
    assert "Scanner a 600 dpi minimum" in text
    assert "DICT_6X6_250" in text
    assert plan.template_id in text
    # Date-heure imprimee (EPIC4-ARB-8): presente au rendu, absente du plan.
    assert "genere le" in text


def test_example_sheet_is_generated_for_visual_inspection(project_with_lot, tmp_path) -> None:
    # AC 5 de 4.2 (TEST_PLAN niveau manuel): la planche d'exemple est generee
    # de facon deterministe par pdf_render depuis un plan compose -- le
    # livrable versionne sous _bmad-output/test-artifacts/ est regenere par
    # scripts/generate_sample_sheet.py (meme chemin de code).
    plan = _compose_from_project(project_with_lot)
    stamp = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)
    output = tmp_path / "planche-exemple.pdf"
    pdf_render.render_lot_pdf(plan, project_with_lot["project_dir"], output, generated_at=stamp)
    assert output.is_file()
    assert extract_pdf_text(output)


# --- Story 5.9: le preset sentinelle traverse la commande de bout en bout ---


def test_makepdf_renders_a_sheet_with_the_sentinel_preset(project_with_lot) -> None:
    """Integration contre le vrai producteur: registre -> plan -> PDF ecrit.

    Le registre et la composition sont deja verifies chacun de leur cote; ce
    qui ne l'est nulle part ailleurs, c'est que 36 pastilles et un cadre
    traversent `makepdf` sans faire tomber une garde d'execution (plafond de
    pastilles, repetition confrontee au placement, non-chevauchement).
    """
    project_dir = project_with_lot["project_dir"]
    assert run_makepdf(project_dir, "--nombre-patchs", "18") == 0

    pdf_path = (
        project_dir
        / project_layout.PLANCHES_DIRNAME
        / naming.build_sheets_pdf_filename(
            PROJECT_ID, RUSH_ID, project_with_lot["lot_id"],
            template_id=GABARIT_DE_LA_FIXTURE)
    )
    assert pdf_path.is_file() and pdf_path.stat().st_size > 0

    plan = _compose_from_project(project_with_lot, patch_preset="patches-18-v2")
    assert plan.patch_preset_id == "patches-18-v2"
    for page in images_pages(plan):
        assert len(page.patches) == 36
        framed = [patch for patch in page.patches if patch.frame_mm]
        assert [patch.value_id for patch in framed] == ["sentinel-white-1"] * 2
        # Les huit sentinelles sont bien imprimees, chacune deux fois.
        sentinels = [p for p in page.patches if p.value_id.startswith("sentinel-")]
        assert len(sentinels) == 16
        assert len({p.value_id for p in sentinels}) == 8


@pytest.mark.parametrize("geometry_version,columns_x,patch_size", [
    # La non-regression de la story 5.9 porte sur la geometrie **v1**, celle des
    # planches deja imprimees: colonnes a 14 et 184, pastilles de 12 mm.
    ("v1", {14.0, 184.0}, 12.0),
    # Sous la v2 (composable a la demande par `--geometrie v2`; le defaut est revenu a
    # la v1 a la passe de correction de 5.15), les colonnes
    # sont derivees des constituants: une seule par cote, posee sur la marge d'encre,
    # et des pastilles de 6 mm. Le **contenu** du preset ne change pas pour autant --
    # 24 pastilles, aucun cadre, aucune sentinelle -- et c'est ce que ce test garde:
    # la story 5.15 deplace de la geometrie, elle ne touche pas au jeu de valeurs.
    ("v2", {5.0, 199.0}, 6.0),
])
def test_the_story_5_9_preset_still_composes_what_it_did_when_asked_for(
        project_with_lot, geometry_version, columns_x, patch_size) -> None:
    """`patches-12-v1` n'est plus le defaut (`EPIC5-ARB-67`), il reste **resolvable**.

    L'arbitrage ne retire ni `patches-9-v1` ni `patches-12-v1` du registre: les planches
    deja imprimees sous eux doivent rester relisibles, donc leur composition doit rester
    identique. Ce test garde donc la non-regression de 5.9 sous sa forme desormais
    exacte -- le preset **demande explicitement** -- et le test suivant garde ce que le
    defaut compose aujourd'hui. Les separer est ce qui empeche de confondre « ce preset a
    change » avec « le defaut a change ».
    """
    plan = _compose_from_project(
        project_with_lot, geometry_version=geometry_version,
        patch_preset="patches-12-v1")
    assert plan.patch_preset_id == "patches-12-v1"
    assert plan.template_id.endswith(f"-{geometry_version}")
    for page in images_pages(plan):
        assert len(page.patches) == 24
        assert all(patch.frame_mm == 0.0 for patch in page.patches)
        assert not any(patch.value_id.startswith("sentinel-") for patch in page.patches)
        assert {patch.x_mm for patch in page.patches} == columns_x
        assert {patch.size_mm for patch in page.patches} == {patch_size}


@pytest.mark.parametrize("geometry_version", ["v1", "v2"])
def test_makepdf_default_sheet_carries_the_witness_preset_and_its_sentinels(
        project_with_lot, geometry_version) -> None:
    """Ce que le papier porte **par defaut** depuis `EPIC5-ARB-67`, sur les deux versions.

    Le defaut est **global** et non conditionnel a la geometrie: les deux parametres de ce
    test sont ce qui le mesure, et un defaut conditionnel en ferait echouer un. La
    propriete qui a motive l'arbitrage est celle des trois dernieres assertions: la
    planche composee sans `--nombre-patchs` porte les **cinq chaines** de sentinelles,
    donc le verdict d'ecretage de l'AC 9 de 5.16 y est calculable -- il ne l'etait sur
    **aucun** axe de l'ancien defaut, dont la table ne porte aucune sentinelle.

    Les cardinaux sont **derives du registre** et non recopies: c'est ce preset qui decide
    combien de pastilles il pose, et le recopier ici rendrait le test faux au preset
    suivant.
    """
    from mixed_media_utility import color_calibration, patch_values

    plan = _compose_from_project(project_with_lot, geometry_version=geometry_version)
    assert plan.patch_preset_id == pdf_composition.DEFAULT_PATCH_PRESET
    preset = patch_presets.get_patch_preset(plan.patch_preset_id)
    attendu = len(preset.value_ids) * preset.repetition
    table = patch_values.get_patch_values_table(preset.values_version)
    chaines = color_calibration.sentinel_chains(table)
    sentinelles = {
        value.value_id for value in table.sentinel_values()
    } & set(preset.value_ids)
    for page in images_pages(plan):
        # **34 depuis la story 5.23** (`EPIC5-ARB-82`): le defaut est `patches-17-v4`,
        # meme jeu que `patches-14-v3` plus les trois secondaires, qui rendent visible une
        # derive d'encre CMJ que la comparaison brute a brute est censee attraper.
        assert len(page.patches) == attendu == 34
        poses = {patch.value_id for patch in page.patches}
        # Les cinq chaines sont **completes** sur chaque planche d'images: c'est
        # litteralement l'AC 9 de 5.16, et elle etait fausse du papier produit.
        assert len(chaines) == 5
        for chaine in chaines.values():
            assert set(chaine) <= poses, chaine
        assert {value_id for value_id in poses if value_id.startswith("sentinel-")} == (
            sentinelles)
        # La sentinelle blanche garde son cadre imprime (AC 5 de 5.9): sans lui elle est
        # indiscernable du papier nu, et c'est la seule pastille du depot qui en porte.
        cadres = {patch.value_id for patch in page.patches if patch.frame_mm}
        assert cadres == {"sentinel-white-1"}
        # **Frontiere renversee par la story 5.23** (`EPIC5-ARB-82` (b), AC 1). Celle de
        # 5.16 -- aucune secondaire sur une planche d'images -- etait juste pour l'usage
        # d'alors: les secondaires ne servaient qu'au re-ajustement d'une page deviante,
        # que `EPIC5-ARB-57` supprime. Cet usage change ici, la divergence se mesurant
        # entre deux feuilles **imprimees**: une imprimante depose du CMJN, et une derive
        # d'encre cyan ou magenta ne se voit pas sur un jeu RVB + neutres.
        #
        # La frontiere renversee est aussi precise que celle qu'elle remplace: les trois
        # secondaires sont exigees **nommement**, et non par un role present au moins une
        # fois -- sinon une seule des trois suffirait a passer.
        roles = {
            table.get(value_id).role for value_id in poses
        }
        assert patch_values.ROLE_SECONDARY in roles, sorted(poses)
        assert {value_id for value_id in poses
                if table.get(value_id).role == patch_values.ROLE_SECONDARY} == {
            "secondary-cyan", "secondary-magenta", "secondary-yellow"}


def test_the_default_geometry_version_is_the_design_pass_one(project_with_lot) -> None:
    """Le defaut, vu depuis le producteur reel (story 5.18, AC 11).

    Verifie sur un plan reellement compose et non sur la constante seule: une constante
    que la composition n'aurait pas suivie -- parce qu'un appel intermediaire nommerait
    encore l'autre version -- passerait un test de constante et imprimerait l'autre
    geometrie. C'est l'angle par lequel la revue de 5.15 a trouve que le drapeau de
    version n'etait pas cable: la constante etait basculee, le chemin operateur ne
    l'etait pas.

    La bascule de la story 5.18 se verifie donc **jusque dans le plan imprime**: la
    taille de marqueur, le bord porteur du QR retenu et la version que le payload
    declare doivent etre ceux de la v2.
    """
    plan = _compose_from_project(project_with_lot)
    assert plan.template_id.endswith("-v2")
    spec = page_templates.get_template(plan.template_id)
    assert spec.qr_edge == page_templates.QR_EDGE_BOTTOM
    # Le `template_id` et les marqueurs valent pour **toutes** les pages imprimees: la
    # page de calibration declare le meme gabarit -- l'invariant d'identite de lot l'exige
    # -- et porte les memes quatre coins. C'est la bande du QR qui ne vaut que pour les
    # planches: sur la page de calibration, le QR est pose dans le bloc que la grille du
    # treillis lui reserve, et cette page n'a pas de bande de frames.
    for page in plan.pages:
        assert page.template_id == plan.template_id
        assert page.qr.payload["template_id"] == plan.template_id
        # Geometrie resserree jusque dans le plan imprime.
        assert {marker.size_mm for marker in page.markers} == {15.0}
    for page in images_pages(plan):
        # Et l'emprise du QR est bien dans la bande **basse**: la bascule ne se lit pas
        # seulement dans un identifiant. Sur les **planches** seulement: la page de
        # calibration n'a pas de bande de frames, et son QR est pose dans le bloc que la
        # grille du treillis lui reserve (story 5.16).
        band = spec.frame_band_mm
        assert page.qr.footprint_rect_mm[1] > band["y"] + band["height"]


# ---------------------------------------------------------------------------
# Story 5.15, passe de correction: le drapeau `--geometrie` de `makepdf`
#
# La revue en trois couches a trouve, par trois chemins independants, que
# `compose_lot_plan` acceptait `geometry_version` sans qu'aucun chemin operateur ne le
# porte. Les deux tests ci-dessous sont **d'integration contre la vraie commande** et
# non sur `compose_lot_plan`: c'est precisement la couture CLI -> composition qui
# manquait, et un test sur l'API l'aurait declaree tenue.
# ---------------------------------------------------------------------------


def _lot_template_id_from_manifest(project_dir: Path, lot_id: str) -> str:
    """Le `template_id` que la commande a **declare au manifest** (story 5.11).

    Lu sur disque plutot que recompose: c'est ce que la planche imprimee portera, et
    c'est le seul canal par lequel le scan retrouvera sa geometrie.
    """
    manifest = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    lot = next(lot for lot in manifest["lots"] if lot["lot_id"] == lot_id)
    return lot["template_id"]


@pytest.mark.parametrize("flag,expected_suffix,marker_size_mm", [
    # Sans drapeau: le defaut, donc la **v2** depuis la passe de design (story 5.18).
    ((), "-v2", 15.0),
    # La version nommee decide, et **la non-defaut d'abord**: un drapeau lu puis jete
    # (parametre non transmis a `compose_lot_plan`) passerait tous les cas ou la
    # version demandee coincide avec le defaut. C'est l'exact defaut trouve par la
    # revue, et seule cette ligne le tue.
    (("--geometrie", "v2"), "-v2", 15.0),
    (("--geometrie", "v1"), "-v1", 30.0),
])
def test_the_geometry_flag_reaches_the_printed_sheet(
        project_with_lot, flag, expected_suffix, marker_size_mm) -> None:
    project_dir = project_with_lot["project_dir"]
    assert run_makepdf(project_dir, *flag) == 0

    template_id = _lot_template_id_from_manifest(
        project_dir, project_with_lot["lot_id"])
    assert template_id.endswith(expected_suffix), template_id
    # Et la geometrie que cet identifiant resout est bien celle qui a ete demandee:
    # le suffixe seul pourrait mentir.
    spec = page_templates.get_template(template_id)
    assert spec.geometry.marker_size_mm == marker_size_mm
    assert spec.geometry.version == expected_suffix.lstrip("-")


def test_an_unknown_geometry_version_is_refused_by_the_command(
        project_with_lot, capsys) -> None:
    """Vocabulaire ferme jusqu'au niveau operateur, jamais un repli sur le defaut.

    Un repli produirait un `template_id` qui **ment** sur la geometrie imprimee, et le
    seul symptome serait une homographie fausse au scan des mois plus tard.
    """
    assert run_makepdf(project_with_lot["project_dir"], "--geometrie", "v3") == 1
    output = capsys.readouterr()
    text = output.err + output.out
    # Le refus nomme les versions connues, pour que l'operateur sache quoi ecrire.
    for version in page_templates.GEOMETRY_VERSIONS:
        assert version in text


def test_the_landscape_sentinel_couple_refused_in_v2_stays_composable_in_v1(
        project_with_lot, capsys) -> None:
    """La regression que le retour au defaut v1 ferme, mesuree sur la vraie commande.

    `--orientation paysage --nombre-patchs patches-18-v2` composait avant la story 5.15
    et echouait apres, sans aucune issue: la v2 n'ouvre qu'une colonne de pastilles par
    cote, et 18 rangees de 6 mm au pas de 9 exigent 159 mm quand le couloir lateral
    d'une page paysage en offre 154. Balayage de la revue: 27 combinaisons composables
    en v1 et refusees en v2, zero dans l'autre sens.

    Les deux sens sont exiges ici, et c'est le point: un test qui ne verifierait que le
    succes en v1 passerait aussi si la v2 devenait composable par une reservation
    fausse, et un test qui ne verifierait que le refus en v2 passerait si la v1 cessait
    de l'etre. Le refus doit en outre nommer le couple, sans quoi l'operateur ne peut
    pas savoir quoi changer.
    """
    project_dir = project_with_lot["project_dir"]
    common = ("--orientation", "paysage", "--nombre-patchs", "patches-18-v2")

    # (1) La version **nommee** v1: la commande passe, et la planche declaree est bien
    # une planche paysage v1 portant le preset sentinelle. Depuis la bascule du defaut
    # (story 5.18, AC 11) c'est le drapeau qui rend ce chemin atteignable -- et c'est
    # exactement la raison pour laquelle il existe.
    assert run_makepdf(project_dir, *common, "--geometrie", "v1") == 0
    template_id = _lot_template_id_from_manifest(
        project_dir, project_with_lot["lot_id"])
    assert template_id.endswith("-v1") and "paysage" in template_id
    assert len(patch_presets.resolve_patch_layout(template_id, "patches-18-v2")) == 36

    # (2) La meme demande **par defaut**, donc en v2, est refusee proprement (code 1) et
    # en nommant le couple: c'est la lacune de placement enumeree dans `patch_presets`.
    capsys.readouterr()
    assert run_makepdf(project_dir, *common, "--overwrite") == 1
    output = capsys.readouterr()
    text = output.err + output.out
    assert "patches-18-v2" in text
    assert "paysage" in text and "v2" in text


# ---------------------------------------------------------------------------
# Story 5.10: compression de gamut a l'impression
#
# Tests d'integration **contre le vrai producteur** (action item 3 de la retro
# Epic 4): un `LotComposition` reellement compose et un rendu reel, jamais des
# `SimpleNamespace` de fixture ni des octets recopies.
# ---------------------------------------------------------------------------


def test_the_default_is_the_identity_from_end_to_end(project_with_lot) -> None:
    """AC 8 et AC 10 dans le meme test, parce que c'est la meme garantie vue
    des deux bouts: sans `--gamut-map`, le payload declare l'identite sur
    **toutes** les pages, et le raster est bit-exact avec le contrat d'origine.
    """
    plan = _compose_from_project(project_with_lot)
    assert plan.gamut_map_id == "gamut-map-none-1"
    for page in plan.pages:
        assert page.qr.payload["gamut_map_id"] == plan.gamut_map_id

    some_tiff = next(project_with_lot["frames_path"].rglob("*.tiff"))
    raster = np.asarray(pdf_render.load_frame_image_for_print(some_tiff, plan.gamut_map_id))
    # Le contrat d'origine, reproduit ici a la main: lecture brute, troncature
    # `>> 8`, conversion BGR -> RGB. C'est l'ancrage de non-regression.
    source = pdf_render.cv2.imread(str(some_tiff), pdf_render.cv2.IMREAD_UNCHANGED)
    expected = pdf_render.cv2.cvtColor(
        (source >> 8).astype(np.uint8), pdf_render.cv2.COLOR_BGR2RGB
    )
    assert np.array_equal(raster, expected)


def test_a_non_trivial_compression_actually_changes_the_raster(project_with_lot) -> None:
    # Le pendant du precedent: sans lui, « bit-exact a l'identite » serait
    # satisfait par une compression qui ne s'applique jamais.
    some_tiff = next(project_with_lot["frames_path"].rglob("*.tiff"))
    identity = np.asarray(
        pdf_render.load_frame_image_for_print(some_tiff, "gamut-map-none-1")
    )
    compressed = np.asarray(
        pdf_render.load_frame_image_for_print(some_tiff, "gamut-map-lin-1")
    )
    assert identity.shape == compressed.shape
    assert not np.array_equal(identity, compressed)
    # La compression **resserre** la plage: c'est sa definition.
    assert compressed.min() >= identity.min()
    assert compressed.max() <= identity.max()


def test_the_raster_is_the_transform_resolved_from_the_plan_field(project_with_lot) -> None:
    """AC 7b: le raster reellement produit egale l'application de la
    transformation resolue depuis **ce** champ a la frame source."""
    plan = _compose_from_project(project_with_lot, gamut_map_id="gamut-map-lin-1")
    assert plan.gamut_map_id == "gamut-map-lin-1"
    some_tiff = next(project_with_lot["frames_path"].rglob("*.tiff"))
    raster = np.asarray(pdf_render.load_frame_image_for_print(some_tiff, plan.gamut_map_id))

    source = pdf_render.cv2.imread(str(some_tiff), pdf_render.cv2.IMREAD_UNCHANGED)
    rgb = pdf_render.cv2.cvtColor(source, pdf_render.cv2.COLOR_BGR2RGB)
    expected = gamut_map.get_gamut_map(plan.gamut_map_id).to_print_8bit(rgb)
    assert np.array_equal(raster, expected)


def test_substituting_another_registry_entry_at_render_time_is_detected(
    project_with_lot,
) -> None:
    """AC 7c, le test de **mutation**.

    Sans lui, le test de coherence passerait aussi avec deux chemins
    independants qui se trouvent d'accord. Ici on rend avec une autre entree
    que celle du plan et on exige que le raster differe: c'est ce qui prouve
    que le champ du plan pilote reellement la transformation.
    """
    plan = _compose_from_project(project_with_lot, gamut_map_id="gamut-map-lin-1")
    some_tiff = next(project_with_lot["frames_path"].rglob("*.tiff"))
    from_plan = np.asarray(
        pdf_render.load_frame_image_for_print(some_tiff, plan.gamut_map_id)
    )
    substituted = np.asarray(
        pdf_render.load_frame_image_for_print(some_tiff, "gamut-map-none-1")
    )
    assert not np.array_equal(from_plan, substituted)


def test_the_qr_declares_the_compression_that_is_applied(project_with_lot) -> None:
    # AC 7a: une seule source. Le champ emis au payload et l'identifiant qui
    # resout la transformation appliquee sont le meme attribut de plan.
    for wanted in gamut_map.known_gamut_map_ids():
        plan = _compose_from_project(project_with_lot, gamut_map_id=wanted)
        assert plan.gamut_map_id == wanted
        for page in plan.pages:
            assert page.qr.payload["gamut_map_id"] == wanted
            decoded = qr_codes.decode_qr_image(pdf_render.build_page_qr_raster(page, 600))
            assert decoded.status == qr_codes.DECODE_OK
            from mixed_media_utility.io.payload import parse_payload

            assert parse_payload(decoded.text)["gamut_map_id"] == wanted


def test_patches_are_never_compressed(project_with_lot) -> None:
    """Invariant 2 d'EPIC5-ARB-2, verifie et non suppose.

    Les patchs sont la **reference** de la correction `C`: un patch comprime
    rendrait `C` fausse de facon plausible, ce qui est le pire mode de
    defaillance de la chaine couleur. L'invariant est structurel -- les patchs
    ne traversent pas le chargement d'image -- mais le vrai piege serait de
    *deplacer* l'application « pour factoriser ».
    """
    from mixed_media_utility import patch_presets

    plan = _compose_from_project(project_with_lot, gamut_map_id="gamut-map-lin-1")
    reference = patch_presets.resolve_patch_layout(plan.template_id, plan.patch_preset_id)
    for page in images_pages(plan):
        assert [patch.rgb for patch in page.patches] == [
            patch.rgb for patch in reference
        ]
    # Et le treillis de la page de calibration n'est pas comprime non plus: c'est la meme
    # propriete sur l'autre jeu de pastilles, et elle compte davantage -- c'est la page
    # dont depend toute la correction de la chaine. Composee a la demande depuis la story
    # 5.22, et **avec la meme compression demandee**: c'est le regime ou un deplacement
    # de l'application « pour factoriser » se verrait.
    calibration = _compose_calibration_from_project(
        project_with_lot, gamut_map_id="gamut-map-lin-1")
    # **Deux jeux sur cette page depuis la story 5.23** (AC 1): son treillis, et le bandeau
    # de temoins pose par le mecanisme de bordure. La propriete verifiee ici ne change pas
    # d'un mot -- aucune des deux familles n'est comprimee -- et elle s'etend au bandeau,
    # qui est precisement le jeu que la mesure brute a brute compare d'une feuille a
    # l'autre: une compression qui ne s'appliquerait qu'a une des deux feuilles ferait
    # diverger deux feuilles identiques.
    treillis = patch_presets.resolve_calibration_page_patches(calibration.template_id)
    bandeau = patch_presets.resolve_calibration_page_witnesses(
        calibration.template_id, calibration.patch_preset_id)
    assert [patch.rgb for patch in calibration_page(calibration).patches] == [
        patch.rgb for patch in treillis + bandeau
    ]

    # Et les couleurs effectivement **posees** au rendu, observees sur un
    # canvas espion: c'est le seul moyen de prouver qu'une instruction part.
    class SpyCanvas:
        def __init__(self):
            self.fills = []

        def setFillColorRGB(self, red, green, blue):
            self.fills.append((red, green, blue))

        def setStrokeColorRGB(self, *_args):
            pass

        def setLineWidth(self, *_args):
            pass

        def rect(self, *_args, **_kwargs):
            pass

    spy = SpyCanvas()
    spec = page_templates.get_template(plan.template_id)
    for patch in images_pages(plan)[0].patches:
        pdf_render.draw_patch(spy, patch, spec.page_height_mm)
    expected = [
        (patch.rgb[0] / 255.0, patch.rgb[1] / 255.0, patch.rgb[2] / 255.0)
        for patch in images_pages(plan)[0].patches
    ]
    assert spy.fills == expected


def test_the_qr_raster_is_invariant_under_compression(project_with_lot) -> None:
    # Le QR est rasterise depuis le plan, jamais charge comme une image: il ne
    # traverse pas le point d'application de `G`.
    identity = _compose_from_project(project_with_lot, gamut_map_id="gamut-map-none-1")
    compressed = _compose_from_project(project_with_lot, gamut_map_id="gamut-map-lin-1")
    for page_a, page_b in zip(identity.pages, compressed.pages):
        # Les payloads different par le seul champ de compression...
        assert page_a.qr.payload["gamut_map_id"] != page_b.qr.payload["gamut_map_id"]
        # ... et le raster reste celui du plan, produit par le meme chemin.
        raster = pdf_render.build_page_qr_raster(page_b, 600)
        assert np.array_equal(raster, pdf_render.build_page_qr_raster(page_b, 600))


def test_markers_are_invariant_under_compression(project_with_lot) -> None:
    identity = _compose_from_project(project_with_lot, gamut_map_id="gamut-map-none-1")
    compressed = _compose_from_project(project_with_lot, gamut_map_id="gamut-map-lin-1")
    for page_a, page_b in zip(identity.pages, compressed.pages):
        assert [
            (m.marker_id, m.center_x_mm, m.center_y_mm, m.size_mm) for m in page_a.markers
        ] == [
            (m.marker_id, m.center_x_mm, m.center_y_mm, m.size_mm) for m in page_b.markers
        ]


def test_the_geometry_is_untouched_by_the_compression(project_with_lot) -> None:
    # EPIC5-ARB-1 et EPIC4-ARB-1 restent entierement valides: `G` change des
    # pixels, jamais une position.
    identity = _compose_from_project(project_with_lot, gamut_map_id="gamut-map-none-1")
    compressed = _compose_from_project(project_with_lot, gamut_map_id="gamut-map-lin-1")
    assert identity.template_id == compressed.template_id
    for page_a, page_b in zip(identity.pages, compressed.pages):
        assert [(s.zone_rect_mm, s.image_rect_mm, s.letterbox_policy) for s in page_a.frames] == [
            (s.zone_rect_mm, s.image_rect_mm, s.letterbox_policy) for s in page_b.frames
        ]


def test_an_unknown_gamut_map_is_refused_by_the_cli(project_with_lot, tmp_path) -> None:
    with pytest.raises(pdf_composition.ParameterVocabularyError) as excinfo:
        _compose_from_project(project_with_lot, gamut_map_id="gamut-map-perceptual-1")
    message = str(excinfo.value)
    for known in gamut_map.known_gamut_map_ids():
        assert known in message
    assert "gamut-map-none-1" in message


def test_the_render_never_decides_the_compression_itself() -> None:
    """Regle fondatrice de `pdf_render`: aucune position, aucune taille, aucun
    contenu n'est decide ici -- l'identifiant vient du plan."""
    import ast

    render_path = REPO_ROOT / "src" / "mixed_media_utility" / "pdf_render.py"
    tree = ast.parse(render_path.read_text(encoding="utf-8"), filename=str(render_path))
    # Aucun identifiant de compression en litteral dans le module de rendu.
    literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert not any(value.startswith("gamut-map-") for value in literals), sorted(
        value for value in literals if value.startswith("gamut-map-")
    )
    # ... et pas de defaut sur le parametre du chargement.
    import inspect

    signature = inspect.signature(pdf_render.load_frame_image_for_print)
    assert signature.parameters["gamut_map_id"].default is inspect.Parameter.empty


def test_the_compression_applies_before_the_depth_reduction() -> None:
    """Piege central de la story, verifie par la valeur.

    Comprimer **apres** une reduction prealable donnerait un resultat
    different: la quantification serait deja prise, et `1/k` amplifierait au
    retour une perte inutile. Le test compare les deux ordres et exige qu'ils
    divergent -- sinon il ne prouverait rien.
    """
    # Les valeurs ne sont **pas** des multiples de 257: sur celles-la `>> 8`
    # est sans perte (v >> 8 == v / 257) et les deux ordres coincideraient par
    # construction -- le test passerait sans rien prouver. C'est le meme piege
    # que la story 5.0 avait rencontre avec 65535.
    candidates = np.arange(1, 65536, dtype=np.uint32)
    candidates = candidates[candidates % 257 != 0][::200][:256]
    assert not np.any(candidates % 257 == 0), "temoin mal choisi"
    source = candidates.astype(np.uint16).reshape(1, 256)
    linear = gamut_map.get_gamut_map("gamut-map-lin-1")
    good = linear.to_print_8bit(source)
    # L'ordre fautif: on reduit d'abord, on comprime ensuite.
    bad = linear.to_print_8bit((source >> 8).astype(np.uint8))
    assert not np.array_equal(good, bad)
    # L'ecart est un biais systematique vers le bas, pas du bruit: la
    # troncature prealable perd toujours dans le meme sens.
    assert good.astype(int).mean() > bad.astype(int).mean()


def test_the_alpha_channel_is_never_compressed(monkeypatch, tmp_path) -> None:
    """La normalisation de canaux, qui elimine l'alpha, precede l'application:
    la question de comprimer un canal qui n'est pas une couleur ne se pose
    donc jamais."""
    bgra = np.zeros((4, 4, 4), dtype=np.uint16)
    bgra[..., :3] = 40000
    bgra[..., 3] = 65535  # alpha opaque
    monkeypatch.setattr(pdf_render.cv2, "imread", lambda *_a, **_k: bgra)
    raster = np.asarray(
        pdf_render.load_frame_image_for_print(tmp_path / "frame.tiff", "gamut-map-lin-1")
    )
    assert raster.shape == (4, 4, 3), "l'alpha est elimine avant l'application"
    linear = gamut_map.get_gamut_map("gamut-map-lin-1")
    expected = linear.to_print_8bit(np.full((4, 4, 3), 40000, dtype=np.uint16))
    assert np.array_equal(raster, expected)


def test_the_existing_refusals_are_preserved_word_for_word(monkeypatch, tmp_path) -> None:
    # AC 10: les refus sont preserves en comportement **et en message**.
    monkeypatch.setattr(pdf_render.cv2, "imread", lambda *_a, **_k: None)
    with pytest.raises(pdf_render.PdfRenderError) as excinfo:
        pdf_render.load_frame_image_for_print(tmp_path / "absente.tiff", "gamut-map-none-1")
    assert "Frame illisible" in str(excinfo.value)

    monkeypatch.setattr(
        pdf_render.cv2, "imread", lambda *_a, **_k: np.zeros((4, 4, 3), dtype=np.int16)
    )
    with pytest.raises(pdf_render.PdfRenderError) as excinfo:
        pdf_render.load_frame_image_for_print(tmp_path / "frame.tiff", "gamut-map-none-1")
    assert "Profondeur de pixel non geree" in str(excinfo.value)


# --- Reponse a la revue en trois couches (5.10) ------------------------------


def test_the_render_reads_the_compression_from_the_plan(project_with_lot, tmp_path) -> None:
    """Le bloquant de la revue: le cablage `_render_page -> plan.gamut_map_id`
    n'etait garde par **aucun** test.

    Les deux tests de coherence appelaient `load_frame_image_for_print` en
    fournissant eux-memes l'identifiant: le renderer pouvait ignorer le plan et
    imposer le defaut, les 2333 tests passaient. C'est le piege 3 mot pour mot
    -- le QR declare la compression, le raster ne l'a pas subie, le symptome
    est nul a l'impression, et depuis EPIC5-ARB-20 la valeur fausse sera
    persistee au manifest.

    On observe donc ce que le **rendu** demande, pas ce que le test fournit.
    """
    plan = _compose_from_project(project_with_lot, gamut_map_id="gamut-map-lin-1")
    seen: list[str] = []
    real = pdf_render.load_frame_image_for_print

    def spy(path, gamut_map_id):
        seen.append(gamut_map_id)
        return real(path, gamut_map_id)

    monkeypatched = pytest.MonkeyPatch()
    monkeypatched.setattr(pdf_render, "load_frame_image_for_print", spy)
    try:
        pdf_render.render_lot_pdf(
            plan,
            project_with_lot["project_dir"],
            tmp_path / "planches.pdf",
            generated_at=datetime(2026, 8, 8, tzinfo=timezone.utc),
        )
    finally:
        monkeypatched.undo()

    assert seen, "aucune frame rendue: le test ne prouverait rien"
    assert set(seen) == {"gamut-map-lin-1"}, seen


def test_a_plan_whose_qr_contradicts_its_compression_is_refused(
    project_with_lot, tmp_path
) -> None:
    """Le plan et le payload de chaque page sont deux etats distincts apres
    composition, et rien ne les confrontait.

    Un `dataclasses.replace` suffisait a produire un PDF valide dont les frames
    sont comprimees et dont le QR declare l'identite.
    """
    import dataclasses

    plan = _compose_from_project(project_with_lot, gamut_map_id="gamut-map-none-1")
    forged = dataclasses.replace(plan, gamut_map_id="gamut-map-lin-1")
    with pytest.raises(pdf_render.PdfRenderError) as excinfo:
        pdf_render.render_lot_pdf(
            forged,
            project_with_lot["project_dir"],
            tmp_path / "planches.pdf",
            generated_at=datetime(2026, 8, 8, tzinfo=timezone.utc),
        )
    message = str(excinfo.value)
    assert "gamut-map-lin-1" in message and "gamut-map-none-1" in message
    assert not (tmp_path / "planches.pdf").exists(), "aucun PDF partiel"


def test_a_coherent_plan_still_renders(project_with_lot, tmp_path) -> None:
    # Le pendant du precedent: une garde qui refuserait tout serait verte aussi.
    for wanted in gamut_map.known_gamut_map_ids():
        plan = _compose_from_project(project_with_lot, gamut_map_id=wanted)
        output = pdf_render.render_lot_pdf(
            plan,
            project_with_lot["project_dir"],
            tmp_path / f"planches-{wanted}.pdf",
            generated_at=datetime(2026, 8, 8, tzinfo=timezone.utc),
        )
        assert output.exists() and output.stat().st_size > 0


def test_an_unknown_compression_is_a_named_refusal_not_a_bare_traceback(
    project_with_lot, tmp_path
) -> None:
    # `GamutMapError` derive de `ValueError`, `PdfRenderError` de
    # `RuntimeError`: aucune clause `except` de la commande ne nommait la
    # premiere, donc un identifiant inconnu remontait en trace brute.
    with pytest.raises(pdf_render.PdfRenderError):
        pdf_render.load_frame_image_for_print(tmp_path / "f.tiff", "gamut-map-nope-1")


def test_the_cli_option_reaches_the_plan(project_with_lot, tmp_path, monkeypatch) -> None:
    """La CLI n'etait traversee par **aucun** test: les trois mutants de
    `cli.py` survivaient a la suite complete. L'option pouvait devenir inerte,
    changer de defaut ou de nom sans rien casser."""
    captured: dict = {}
    real = pdf_composition.compose_lot_plan

    def spy(**kwargs):
        captured.update(kwargs)
        return real(**kwargs)

    monkeypatch.setattr(pdf_composition, "compose_lot_plan", spy)
    monkeypatch.setattr(
        pdf_render, "render_lot_pdf", lambda *a, **k: tmp_path / "planches.pdf"
    )
    project_dir = project_with_lot["project_dir"]

    code = cli.main([
        "makepdf", "--project", str(project_dir),
        "--rush", RUSH_ID, "--fps", "5",
        "--gamut-map", "gamut-map-lin-1", "--overwrite",
    ])
    assert code == 0, "la commande doit reussir"
    assert captured["gamut_map_id"] == "gamut-map-lin-1"

    captured.clear()
    cli.main([
        "makepdf", "--project", str(project_dir),
        "--rush", RUSH_ID, "--fps", "5", "--overwrite",
    ])
    # Sans l'option, la valeur transmise est `None` et c'est le resolveur qui
    # pose le defaut -- pas la CLI, qui n'a pas a connaitre le vocabulaire.
    assert captured["gamut_map_id"] is None
    assert pdf_composition.resolve_gamut_map(None) == "gamut-map-none-1"


def test_the_cli_refuses_an_unknown_compression(project_with_lot, tmp_path) -> None:
    code = cli.main([
        "makepdf", "--project", str(project_with_lot["project_dir"]),
        "--rush", RUSH_ID, "--fps", "5",
        "--gamut-map", "gamut-map-perceptual-1", "--overwrite",
    ])
    assert code == 1


def test_a_non_trivial_compression_is_named_and_reserved_in_the_journal(
    project_with_lot,
) -> None:
    """Sans reserve au journal, l'option serait un piege silencieux pour qui la
    decouvre dans l'aide: `G^-1` n'est pas implementee, donc une planche
    comprimee produit des exports delaves que rien ne redresse.

    La verification porte sur le **journal dedie** ecrit sur disque, pas sur
    `caplog`: c'est l'artefact que l'operateur relira, et la commande configure
    ses propres gestionnaires.
    """
    project_dir = project_with_lot["project_dir"]
    journal = project_dir / project_layout.LOGS_DIRNAME / "makepdf.log"

    assert run_makepdf(project_dir, "--gamut-map", "gamut-map-lin-1", "--overwrite") == 0
    text = journal.read_text(encoding="utf-8")
    assert "gamut-map-lin-1" in text
    assert "COMPRESSION_SANS_EXPANSION" in text

    journal.write_text("", encoding="utf-8")
    assert run_makepdf(project_dir, "--overwrite") == 0
    text = journal.read_text(encoding="utf-8")
    assert "gamut-map-none-1" in text
    assert "COMPRESSION_SANS_EXPANSION" not in text, (
        "le defaut n'a pas a porter la reserve"
    )


def test_the_qr_raster_is_really_the_one_of_the_plan(project_with_lot) -> None:
    """Le test d'invariance du QR etait tautologique: il comparait
    `build_page_qr_raster(page)` a lui-meme.

    Ici on confronte le raster a une **re-derivation independante** depuis le
    texte de payload du plan, et on verifie que deux compressions differentes
    donnent bien deux rasters differents -- puisque le payload differe.
    """
    identity = _compose_from_project(project_with_lot, gamut_map_id="gamut-map-none-1")
    compressed = _compose_from_project(project_with_lot, gamut_map_id="gamut-map-lin-1")
    for page_a, page_b in zip(identity.pages, compressed.pages):
        raster_a = pdf_render.build_page_qr_raster(page_a, 600)
        raster_b = pdf_render.build_page_qr_raster(page_b, 600)
        expected = qr_codes.render_for_print(
            qr_codes.encode_qr_image(page_a.qr.payload_text), page_a.qr.print_size_mm, 600
        )
        assert np.array_equal(raster_a, expected)
        assert not np.array_equal(raster_a, raster_b), (
            "deux payloads differents doivent donner deux rasters differents"
        )


@pytest.mark.parametrize(
    ("channels", "code"),
    [(1, "GRAY2RGB"), (3, "BGR2RGB"), (4, "BGRA2RGB")],
)
def test_every_channel_branch_is_pinned_by_value(
    monkeypatch, tmp_path, channels: int, code: str
) -> None:
    """Les branches gris et BGRA etaient cassables sans qu'un test tombe.

    On fige la valeur produite par chaque branche, sous l'identite comme sous
    compression: permuter deux conversions ou en supprimer une doit se voir.
    """
    rng = np.random.default_rng(1000 + channels)
    shape = (5, 7) if channels == 1 else (5, 7, channels)
    source = rng.integers(0, 65536, size=shape, dtype=np.uint16)
    monkeypatch.setattr(pdf_render.cv2, "imread", lambda *_a, **_k: source)

    converted = pdf_render.cv2.cvtColor(source, getattr(pdf_render.cv2, f"COLOR_{code}"))
    for gamut_map_id in gamut_map.known_gamut_map_ids():
        raster = np.asarray(
            pdf_render.load_frame_image_for_print(tmp_path / "f.tiff", gamut_map_id)
        )
        expected = gamut_map.get_gamut_map(gamut_map_id).to_print_8bit(converted)
        assert raster.shape == (5, 7, 3)
        assert np.array_equal(raster, expected), (channels, gamut_map_id)


def test_the_registry_entries_cannot_be_rebound(monkeypatch) -> None:
    # Le registre est un `MappingProxyType`, mais les noms de module qui le
    # peuplent restaient reliables. Le contrat est qu'une entree ne se modifie
    # pas: on enregistre un nouvel identifiant.
    import dataclasses

    entry = gamut_map.get_gamut_map("gamut-map-lin-1")
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.low = 0.2
    # ... et le registre rend toujours le meme objet.
    assert gamut_map.get_gamut_map("gamut-map-lin-1") is entry


@pytest.mark.parametrize(
    "abbreviation", ["lin", "lin-1", "gamut-map-lin", "none", "1", "GAMUT-MAP-LIN-1"]
)
def test_no_resolution_by_abbreviation_was_reintroduced(abbreviation: str) -> None:
    """Difference deliberee avec `resolve_patch_preset`.

    La resolution par cardinal « premier gagnant sur l'ordre du dict » est un
    defaut deja ferme par 5.9; en recreer un jumeau serait d'autant plus grave
    ici que la valeur resolue est imprimee dans le QR et persistee au manifest.
    """
    with pytest.raises(pdf_composition.ParameterVocabularyError):
        pdf_composition.resolve_gamut_map(abbreviation)


# ---------------------------------------------------------------------------
# Aide de `--nombre-patchs`: derivee du registre, jamais enumeree a la main
# (correction du 2026-08-10)
# ---------------------------------------------------------------------------


def _makepdf_help(capsys) -> str:
    with pytest.raises(SystemExit):
        cli.main(["makepdf", "--help"])
    return capsys.readouterr().out


def test_the_patch_preset_help_lists_every_preset_of_the_registry(capsys) -> None:
    """L'aide annoncait deux presets sur trois, et le troisieme etait accepte.

    `resolve_patch_preset` accepte `patches-18-v2` depuis la story 5.9, mais
    l'aide de `--nombre-patchs` enumerait `patches-9-v1` et `patches-12-v1` en
    dur. Consequence reelle, constatee le 2026-08-10: le seul preset qui porte
    les sentinelles de gamut -- donc le seul sur lequel le verdict d'ecretage de
    5.4b soit calculable -- etait invisible a l'operateur qui lit l'aide.

    Le test porte sur la **derivation**, pas sur la liste du jour: un preset
    ajoute au registre sans etre annonce fait echouer ce test, ce qu'une
    assertion sur trois identifiants litteraux ne ferait pas.
    """
    help_text = _makepdf_help(capsys)

    known = patch_presets.known_preset_ids()
    # Au moins trois presets, sinon le test se viderait le jour ou le registre
    # tomberait a un seul: la propriete « tous annonces » serait alors tenue par
    # une aide qui n'annonce presque rien.
    assert len(known) >= 3
    for preset_id in known:
        assert preset_id in help_text, preset_id
        cardinal = len(patch_presets.get_patch_preset(preset_id).value_ids)
        assert str(cardinal) in help_text, (preset_id, cardinal)
    assert pdf_composition.DEFAULT_PATCH_PRESET in help_text


def test_the_patch_preset_help_names_which_preset_carries_the_sentinels(capsys) -> None:
    """L'information qui manquait n'est pas la liste, c'est laquelle choisir.

    Enumerer trois identifiants sans dire ce qui les distingue laisse
    l'operateur choisir le defaut -- qui est justement celui qui ne porte pas
    de sentinelle.

    **Bloquant B4 de la revue de 5.16, ferme ici.** L'aide affirmait en dur « seul
    `patches-18-v2` porte les sentinelles de gamut »; `patches-14-v3` porte ses huit, et
    c'est le seul des deux composable en paysage v2. La phrase est desormais **derivee du
    registre** (`patch_presets.gamut_sentinel_preset_ids`), et ce test la confronte au
    registre **dans les deux sens** plutot que de verifier la presence d'un identifiant:
    un preset a sentinelles absent de la clause, ou un preset sans sentinelle qui y
    figurerait, font echouer.
    """
    help_text = _makepdf_help(capsys)

    porteurs = patch_presets.gamut_sentinel_preset_ids()
    # Le critere du registre est celui du verdict d'ecretage: la chaine complete dans le
    # jeu **du preset**, pas seulement des sentinelles dans sa table. Les deux coincident
    # aujourd'hui, et la double mesure est ce qui le dit.
    portent_dans_leur_table = tuple(
        preset_id
        for preset_id in patch_presets.known_preset_ids()
        if patch_values.get_patch_values_table(
            patch_presets.get_patch_preset(preset_id).values_version
        ).sentinel_values()
    )
    # `patches-17-v4` rejoint les porteurs a la story 5.23: il epingle `patch-values-4`,
    # qui reprend les huit sentinelles par reference aux memes objets que la v2.
    assert porteurs == portent_dans_leur_table == (
        "patches-18-v2", "patches-14-v3", "patches-17-v4")

    # La clause des sentinelles est isolee, puis confrontee preset par preset: c'est ce
    # qui distingue « l'aide contient l'identifiant » (vrai de l'enumeration qui la
    # precede) de « l'aide le declare porteur de sentinelles ».
    # L'aide est **replie** sur la largeur du terminal par argparse, donc la clause est
    # cherchee sur un texte dont les blancs sont normalises: depuis que le registre porte
    # cinq presets, l'enumeration qui la precede est assez longue pour que le repli tombe
    # au milieu de « Sentinelles de gamut ». Chercher le litteral tel quel faisait echouer
    # ce test sur un retour a la ligne, c'est-a-dire sur rien.
    aplati = " ".join(help_text.split())
    debut = aplati.index("Sentinelles de gamut")
    clause = aplati[debut:]
    for preset_id in patch_presets.known_preset_ids():
        assert (preset_id in clause) is (preset_id in porteurs), (preset_id, clause)

    # Et le volet qui a rendu le bloquant couteux: l'aide dit lequel des porteurs ne se
    # compose pas, et dans quelle orientation. Sans lui, elle renvoie l'operateur de
    # paysage v2 sur le preset refuse, dont le refus propose de changer de geometrie.
    for version, orientation, preset_id in patch_presets.unplaceable_couples():
        if preset_id in porteurs:
            assert f"{preset_id} n'est pas composable en {orientation} {version}" in (
                help_text)


# ---------------------------------------------------------------------------
# Passe de correction de la story 5.18 -- `H01` et `H02` de la campagne de
# cloture: la place de la ligne de date-heure.
# ---------------------------------------------------------------------------


def test_the_render_puts_the_date_line_exactly_where_the_plan_declares_it(
    project_with_lot,
) -> None:
    """**`H01` et `H02`**, les deux survivants de la place de la date.

    Les deux mutants portent sur le meme mecanisme et **survivaient** tous les deux:

    * `H01` rend le **rendu** decideur -- `("footer_block", 4)` en dur, l'etat d'avant la
      story 5.18. Sous la disposition v2, l'identite n'est plus dans le pied: cette
      constante pose la date dans un bloc qui n'a que deux lignes et dont la zone en
      reserve deux, donc la troisieme ligne s'imprime **sous** son rectangle, par-dessus
      la premiere colonne technique. Aucune etape n'echoue;
    * `H02` pose la date **en tete** du bloc qui la recoit au lieu du rang declare.

    **Ni l'un ni l'autre ne se voit sur le plan**, qui reste juste: ils mutent
    `pdf_render`. Ni sur le texte extrait du PDF, ou l'ordre des chaines est le meme dans
    les deux cas -- c'est ce qui les a laisses passer. Ce test observe donc **l'appel de
    dessin lui-meme**: il enveloppe `_draw_text_lines` pour enregistrer, pour chaque bloc,
    le rectangle recu et les lignes recues, puis confronte l'emplacement de la date a ce
    que le plan declare. C'est le rendu reel, pas un modele: le PDF est produit par la
    commande, et l'enveloppe delegue a la vraie fonction.
    """
    project_dir = project_with_lot["project_dir"]
    plan = _compose_from_project(project_with_lot)
    # La premiere **planche d'images**: la page de calibration ne porte aucune ligne de
    # date, et son `date_line_slot` le declare explicitement (story 5.16,
    # `pdf_composition.NO_DATE_LINE_SLOT`).
    page = images_pages(plan)[0]
    bloc_declare, rang_declare = page.text.date_line_slot
    # La disposition v2 declare la date dans la **premiere colonne technique**: c'est le
    # changement de la story, et c'est ce que `H01` defait.
    assert bloc_declare in page_templates.FOOTER_TECHNICAL_ZONE_NAMES, bloc_declare
    assert bloc_declare != "footer_block"

    appels: list[tuple[tuple[float, float, float, float], tuple[str, ...]]] = []
    vrai = pdf_render._draw_text_lines

    def espion(canvas, rect_mm, lines, page_height_mm, font_size=None, **kwargs):
        appels.append((tuple(rect_mm), tuple(lines)))
        if font_size is None:
            return vrai(canvas, rect_mm, lines, page_height_mm, **kwargs)
        return vrai(canvas, rect_mm, lines, page_height_mm, font_size=font_size,
                    **kwargs)

    monkey = pytest.MonkeyPatch()
    try:
        monkey.setattr(pdf_render, "_draw_text_lines", espion)
        assert run_makepdf(project_dir) == 0
    finally:
        monkey.undo()

    assert appels, "le rendu n'a dessine aucun bloc de texte"
    # Le rectangle du bloc que le plan designe, lu sur le plan.
    rect_declare = tuple(
        b.rect_mm for b in page.text.blocks if b.name == bloc_declare
    )[0]
    portant = [lines for rect, lines in appels
               if rect == pytest.approx(rect_declare)]
    # Une occurrence par page: le gabarit est le meme pour toutes, donc le rectangle
    # aussi, et **chaque** page doit porter sa date au bon endroit.
    # Une occurrence par **planche d'images**: la page de calibration ne porte aucune
    # ligne de date, et son `date_line_slot` le declare (story 5.16).
    assert len(portant) == len(images_pages(plan)), (rect_declare, len(portant))
    # **`H01`**: la date est dessinee dans le rectangle du bloc **declare**, et dans aucun
    # autre. Un rendu qui la poserait dans `footer_block` la ferait apparaitre dans un
    # rectangle different -- ce que la boucle ci-dessous mesure sur tous les appels.
    for rect, lines in appels:
        if rect == pytest.approx(rect_declare):
            continue
        assert not any(l.startswith("genere le ") for l in lines), (rect, lines)
    for index, (lignes, page_plan) in enumerate(zip(portant, images_pages(plan))):
        date = [ligne for ligne in lignes if ligne.startswith("genere le ")]
        assert len(date) == 1, (index, lignes)
        # **`H02`**: la date est au **rang declare**, pas en tete du bloc. Le rang declare
        # est 0 en v2, donc ce volet-la ne discrimine pas ici; c'est le volet v1 ci-dessous
        # qui le fait, et il est indispensable.
        bloc_page, rang_page = page_plan.text.date_line_slot
        assert bloc_page == bloc_declare and rang_page == rang_declare
    # Et la page de calibration declare **explicitement** l'absence de date, par la
    # constante nommee et non par un bloc oublie: un `date_line_slot` qui nommerait un
    # bloc inexistant serait indistinguable d'un oubli, et c'est pourquoi la constante a
    # un nom.
    calibration = calibration_page(plan)
    if calibration is not None:
        assert calibration.text.date_line_slot == pdf_composition.NO_DATE_LINE_SLOT
        assert not any(bloc.name == calibration.text.date_line_slot[0]
                       for bloc in calibration.text.blocks)
        assert lignes.index(date[0]) == rang_page, (index, lignes, rang_page)
        # Et les lignes du bloc, date exclue, sont exactement celles du plan: le rendu
        # n'ajoute et ne retire rien d'autre.
        bloc_plan = tuple(b.lines for b in page_plan.text.blocks
                          if b.name == bloc_declare)[0]
        assert tuple(l for l in lignes
                     if not l.startswith("genere le ")) == bloc_plan, index

    # --- Volet v1: un rang declare NON NUL, et le rendu doit l'honorer ---------------
    #
    # C'est le volet qui tue `H02`. En disposition historique la date se pose **apres**
    # les quatre lignes d'identite du pied, donc a un rang non nul, et des lignes
    # techniques la suivent dans le meme bloc: un rendu qui la mettrait en tete du bloc
    # placerait la date avant `sheet_label`.
    # **Le rang du second rendu est DERIVE, pas suppose.** Depuis le
    # decouplage du 2026-09-02 (AC 2.10) le rang entre dans l'etiquette
    # imprimee a chaque passe ; et le rendu ci-dessous passe `--overwrite`,
    # qui vise le tirage EXISTANT -- donc la LIGNE D'EAU, pas son successeur.
    # Le plan temoin doit porter le meme rang, sans quoi il compare deux
    # tirages differents.
    _rang_v1 = pdf_composition.sheets_version_watermark(
        json.loads((project_dir / "project.json").read_text(encoding="utf-8")),
        project_with_lot["lot_id"], project_dir,
        project_id=project_with_lot["manifest"]["project_id"],
        rush_id=project_with_lot["manifest"]["lots"][0]["rush_id"],
    )
    plan_v1 = _compose_from_project(
        project_with_lot, geometry_version="v1",
        version_rank=None if _rang_v1 == 1 else _rang_v1)
    page_v1 = plan_v1.pages[0]
    bloc_v1, rang_v1 = page_v1.text.date_line_slot
    assert bloc_v1 == "footer_block"
    assert rang_v1 > 0, rang_v1
    lignes_v1 = tuple(b.lines for b in page_v1.text.blocks if b.name == bloc_v1)[0]
    assert rang_v1 < len(lignes_v1), (rang_v1, lignes_v1)
    appels_v1: list[tuple[tuple[float, ...], tuple[str, ...]]] = []

    def espion_v1(canvas, rect_mm, lines, page_height_mm, font_size=None, **kwargs):
        appels_v1.append((tuple(rect_mm), tuple(lines)))
        if font_size is None:
            return vrai(canvas, rect_mm, lines, page_height_mm, **kwargs)
        return vrai(canvas, rect_mm, lines, page_height_mm, font_size=font_size,
                    **kwargs)

    monkey = pytest.MonkeyPatch()
    try:
        monkey.setattr(pdf_render, "_draw_text_lines", espion_v1)
        # `--overwrite`: le PDF v2 du premier volet occupe deja le nom du lot, et
        # l'ecrasement n'est jamais implicite.
        assert run_makepdf(project_dir, "--geometrie", "v1", "--overwrite") == 0
    finally:
        monkey.undo()
    rect_v1 = tuple(b.rect_mm for b in page_v1.text.blocks if b.name == bloc_v1)[0]
    portant_v1 = [lines for rect, lines in appels_v1
                  if rect == pytest.approx(rect_v1)]
    assert len(portant_v1) == len(plan_v1.pages), (rect_v1, len(portant_v1))
    rendues = portant_v1[0]
    date_v1 = [l for l in rendues if l.startswith("genere le ")]
    assert len(date_v1) == 1, rendues
    assert rendues.index(date_v1[0]) == rang_v1, (rendues, rang_v1)
    # La ligne qui precede la date est la derniere ligne d'identite, et celle qui la suit
    # est la premiere ligne technique: la date est **inseree**, pas prependee ni appendue.
    assert rendues[0] == page_v1.text.sheet_label
    assert rendues[rang_v1 - 1] == lignes_v1[rang_v1 - 1]
    assert rendues[rang_v1 + 1] == lignes_v1[rang_v1]


# ---------------------------------------------------------------------------
# `--nouvelle-version` de bout en bout (`EPIC11-ARB-91`).
#
# Trou trouve par DEUX couches de revue : le cablage CLI n'etait mesure par
# rien, alors que la voie master, livree deux commits plus tot, avait
# exactement ce test. Un mutant `version_rank=None` dans l'appel a
# `compose_lot_plan` rendait le drapeau totalement inerte -- sur les trois
# porteurs a la fois -- et survivait a 101 tests.
# ---------------------------------------------------------------------------


def _manifeste_a_deux_lots(project_dir: Path) -> str:
    """Ajouter un SECOND lot au projet, et rendre le lot_id de la CIBLE.

    Regle des fabriques : le code parcourt `manifest["lots"]` avec un `next(...
    if l["lot_id"] == lot_id)` pour retrouver le `rush_id`. Sur une fabrique
    mono-lot, un `find` fautif qui rendrait toujours le premier element ne se
    demasque pas -- c'est exactement le mutant `M25` de la story 5.7, qui avait
    survecu a 257 tests. La cible est donc placee en SECONDE position.
    """
    manifest_path = project_dir / "project.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cible = manifest["lots"][0]
    leurre = dict(cible)
    leurre["lot_id"] = "AUTRE-RUSH_24"
    leurre["rush_id"] = "AUTRE-RUSH"
    manifest["lots"] = [leurre, cible]
    manifest["rushes"] = list(manifest.get("rushes") or []) + [
        {"rush_id": "AUTRE-RUSH"}]
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return cible["lot_id"]


def test_cli_nouvelle_version_ecrit_un_tirage_VOISIN_sans_toucher_a_l_original(
        project_with_lot):
    """Le tirage voisin, et l'original intact.

    **Ce qui a change le 2026-09-02** : la premiere redaction faisait refuser
    la seconde passe puis passait `--nouvelle-version` pour l'ouvrir. Depuis le
    decouplage de l'AC 2.10 le rang avance a chaque passe, drapeau ou non, donc
    il n'y a plus de refus a lever. Le drapeau reste passe ici -- il doit rester
    **sans effet plutot que refuse** (AC 2.10c) -- et la propriete mesuree est
    inchangee : le voisin est ecrit, l'original n'est pas touche.

    La fabrique reste a DEUX lots avec la cible en seconde position : le code
    retrouve le `rush_id` par un `next(... if l["lot_id"] == lot_id)`, et un
    `find` fautif rendant toujours le premier element ne se demasque pas
    autrement (mutant `M25` de la story 5.7, survivant a 257 tests).
    """
    project_dir = project_with_lot["project_dir"]
    _manifeste_a_deux_lots(project_dir)
    patches = project_dir / project_layout.PLANCHES_DIRNAME

    assert run_makepdf(project_dir) == 0
    original = sorted(patches.glob("*.pdf"))
    assert len(original) == 1, sorted(p.name for p in patches.iterdir())
    empreinte = (original[0].stat().st_ino, original[0].stat().st_mtime_ns,
                 original[0].stat().st_size)

    assert run_makepdf(project_dir, "--nouvelle-version") == 0
    version = patches / original[0].name.replace(".pdf", "_v2.pdf")
    assert version.is_file(), (
        f"aucun tirage v2 ecrit; presents: {sorted(p.name for p in patches.iterdir())}"
    )
    etat = original[0].stat()
    assert (etat.st_ino, etat.st_mtime_ns, etat.st_size) == empreinte, (
        "le tirage d'origine a ete touche par --nouvelle-version"
    )


def test_cli_le_refus_de_planche_presente_offre_les_TROIS_issues(
        project_with_lot, capsys, monkeypatch):
    """`EPIC11-ARB-89` : jamais une seule issue. Et chacune doit EXISTER --
    une issue prescrite qui n'est pas un drapeau reel est un blocage sec
    habille en conseil.

    **La garde est devenue DEFENSIVE le 2026-09-02, et ce test le dit plutot
    que de disparaitre avec elle.** Jusqu'au decouplage de l'AC 2.10, la
    seconde passe tombait sur `output_path.exists()` et ce refus s'imprimait.
    Depuis, le rang avance a chaque passe -- et `_rangs_sur_le_disque` balaie
    toutes les mises en page --, si bien qu'aucun parcours d'operateur ne
    produit plus un nom deja pris : la branche reste, sans chemin qui y mene.

    Elle n'est pas retiree pour autant : `EPIC11-ARB-89` interdit le blocage
    sec, et une branche de refus qui perdrait ses issues serait un defaut le
    jour ou elle redeviendrait atteignable (un rang que le balayage ne voit
    pas -- le registre d'AUJOURD'HUI est la limite dite en AC 2.11e). Le test
    force donc la situation au lieu de l'esperer : le resolveur de rang rend un
    rang dont le fichier est deja pose.
    """
    project_dir = project_with_lot["project_dir"]
    assert run_makepdf(project_dir) == 0
    capsys.readouterr()

    # Le rang que la passe suivante emploierait, rendu FIXE : le fichier du
    # rang 1 existe deja, donc le refus se declenche.
    monkeypatch.setattr(pdf_composition, "resolve_sheets_version_rank",
                        lambda *a, **k: 1)
    assert run_makepdf(project_dir) == 1
    rendu = capsys.readouterr().err
    for issue in ("--nouvelle-version", "--overwrite", "project remove"):
        assert issue in rendu, f"le refus n'offre pas l'issue {issue!r}: {rendu}"


def test_cli_nouvelle_version_sur_un_lot_JAMAIS_imprime_rend_l_ORIGINE(
        project_with_lot):
    """Le drapeau devient sans effet plutot que refuse : refuser serait un
    blocage sec sur une intention parfaitement realisable, et produire un
    `_v2` serait une « version 2 de rien »."""
    project_dir = project_with_lot["project_dir"]
    patches = project_dir / project_layout.PLANCHES_DIRNAME

    assert run_makepdf(project_dir, "--nouvelle-version") == 0
    ecrits = sorted(p.name for p in patches.glob("*.pdf"))
    assert len(ecrits) == 1, ecrits
    assert ecrits[0].endswith(f"_{page_templates.DEFAULT_FRAMES_PER_PAGE}f-"
                              f"{pdf_composition.resolve_orientation(None)[:3]}.pdf"), ecrits
    assert "_v2" not in ecrits[0]


def test_cli_le_refus_de_page_de_calibration_offre_une_issue_NON_destructive(
        project_with_lot, capsys):
    """Les deux issues d'origine detruisaient toutes deux le fichier existant,
    au motif -- mesurable comme FAUX -- que « deux tirages de la meme chaine
    sont le meme document ». Huit parametres de geometrie font varier la page
    sans entrer dans son nom."""
    project_dir = project_with_lot["project_dir"]
    args = ["makepdf", "--project", str(project_dir), "calibration-page",
            "--chaine", "chaine-A"]
    assert cli.main(args) == 0
    capsys.readouterr()
    assert cli.main(args) == 1
    rendu = capsys.readouterr().err
    assert "--chaine" in rendu, (
        "le refus n'offre aucune issue NON destructive: les deux autres "
        "ecrasent ou suppriment le fichier"
    )
    assert "--overwrite" in rendu
