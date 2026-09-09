"""Tests de l'ingestion de lots de scan (story 5.1).

Aucune fixture binaire versionnee: les images sont fabriquees par `numpy` +
`cv2.imwrite` et les PDF par `reportlab`, deja au `requirements.txt`. Aucun test
n'a besoin de ffmpeg.

Le fil conducteur est qu'une ingestion ne doit jamais **supposer** ce qu'elle
lit. Trois choses se mesurent sur la donnee et se verifient donc par relecture,
jamais par la valeur de retour du code sous test : la profondeur de bits, l'ordre
des pages et l'ordre des canaux.
"""

from __future__ import annotations

import json
import sys
import unicodedata
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdfcanvas

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import cli, qr_codes, scan_ingest
from mixed_media_utility.io import project_layout

MODULE_PATH = REPO_ROOT / "src" / "mixed_media_utility" / "scan_ingest.py"


# --- fabriques -------------------------------------------------------------


def write_image(path: Path, *, value: int, dtype=np.uint8, size=(40, 60)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    assert cv2.imwrite(str(path), np.full((*size, 3), value, dtype=dtype))
    return path


def write_pdf(path: Path, *, pages: int = 2, sizes=None, lossy: bool = False) -> Path:
    """PDF de test. `sizes` permet de melanger deliberement deux formats."""
    sizes = sizes or [A4] * pages
    canvas = pdfcanvas.Canvas(str(path), pagesize=sizes[0])
    for index, size in enumerate(sizes):
        canvas.setPageSize(size)
        if lossy and index == 0:
            photo = path.parent / "photo.jpg"
            Image.fromarray(
                np.random.default_rng(0).integers(0, 255, (120, 160, 3), dtype=np.uint8)
            ).save(photo, quality=60)
            canvas.drawImage(ImageReader(str(photo)), 50, 400, width=300, height=225)
        else:
            # Rectangle ROUGE pur: temoin asymetrique de l'ordre des canaux.
            canvas.setFillColorRGB(1, 0, 0)
            canvas.rect(100, 400, 300, 300, stroke=0, fill=1)
        canvas.showPage()
    canvas.save()
    return path


@pytest.fixture
def project(tmp_path: Path) -> Path:
    project_dir = tmp_path / "projet"
    project_layout.ensure_project_layout(project_dir)
    return project_dir


# --- AC 3: ordre deterministe ----------------------------------------------


def test_folder_pages_are_ordered_by_normalised_name(project: Path, tmp_path: Path) -> None:
    """Deux pieges reunis: la casse et la forme Unicode.

    Un scanner Windows ecrit `PAGE_02.TIF`, un autre `page_02.tif`; et un `e`
    accentue s'ecrit NFC sur un systeme, NFD sur un autre — deux chaines
    d'octets differentes pour le meme nom affiche. Sans normalisation, deux
    machines rendraient deux ordres, et le rang de lecture cesserait d'etre
    reproductible.
    """
    folder = tmp_path / "brut"
    for name in (
        "PAGE_02.TIF",
        "page_01.tif",
        unicodedata.normalize("NFD", "pagé_03.png"),
        "page_10.tif",
    ):
        write_image(folder / name, value=10)

    report = scan_ingest.ingest_scan_lot(project, folder, dpi=600)
    names = [Path(page.locator.source_path).name for page in report.pages]
    assert [unicodedata.normalize("NFC", n).casefold() for n in names] == [
        "page_01.tif",
        "page_02.tif",
        "page_10.tif",
        "pagé_03.png",
    ]
    # Le rang de lecture est contigu et part de zero.
    assert [page.read_rank for page in report.pages] == [0, 1, 2, 3]


def test_read_rank_is_not_the_business_page_index(project: Path, tmp_path: Path) -> None:
    # Piege 2: l'operateur peut scanner dans le desordre ou renommer. Le rang de
    # lecture est un ordre de fichiers; `page_index` est declare par le QR, et sa
    # reconciliation appartient a 5.2. Rien ici ne doit s'appeler `page_index`
    # au sens metier.
    folder = tmp_path / "desordre"
    write_image(folder / "zzz.tif", value=10)
    write_image(folder / "aaa.tif", value=20)
    report = scan_ingest.ingest_scan_lot(project, folder, dpi=600)
    document = report.as_document()
    assert "page_index" not in document
    assert all("page_index" not in page for page in document["pages"])
    # Il n'existe que dans le localisateur, ou il designe un index **de PDF**.
    assert all(page["locator"]["page_index"] is None for page in document["pages"])


# --- AC 4: profondeur constatee, jamais fabriquee ---------------------------


def test_a_16_bit_tiff_is_declared_16_bit(project: Path, tmp_path: Path) -> None:
    """Le test que `cv2.imread` nu ferait echouer.

    C'est le defaut exact de `cli.py:278`, corrige par la story 5.0 sur le
    chemin POC: sans `IMREAD_UNCHANGED`, la page ressortirait declaree 8 bits.
    """
    folder = tmp_path / "brut"
    write_image(folder / "p16.tif", value=4000, dtype=np.uint16)
    report = scan_ingest.ingest_scan_lot(project, folder, dpi=600)
    assert [page.source_bit_depth for page in report.pages] == [16]

    # Verification par relecture des pixels via le point d'entree publie, pas
    # par la valeur declaree: c'est la seule preuve honnete.
    array = scan_ingest.load_page_array(project, report.pages[0].locator, dpi=600)
    assert array.dtype == np.uint16
    assert int(array[0, 0, 0]) == 4000


def test_an_8_bit_page_is_never_promoted_to_16_bits(project: Path, tmp_path: Path) -> None:
    # Piege 4: le `x257` fabrique un 16 bits dont 256 niveaux sur 65536 sont
    # peuples. A l'ingestion on **constate**; la montee appartient a l'export
    # de la story 5.6.
    folder = tmp_path / "brut"
    write_image(folder / "p8.png", value=120)
    report = scan_ingest.ingest_scan_lot(project, folder, dpi=600)
    assert report.pages[0].source_bit_depth == 8
    assert scan_ingest.load_page_array(project, report.pages[0].locator, dpi=600).dtype == np.uint8


def test_mixed_bit_depths_are_reported(project: Path, tmp_path: Path) -> None:
    folder = tmp_path / "brut"
    write_image(folder / "a.tif", value=120)
    write_image(folder / "b.tif", value=4000, dtype=np.uint16)
    report = scan_ingest.ingest_scan_lot(project, folder, dpi=600)
    assert "MIXED_BIT_DEPTHS" in report.warnings


# --- AC 7: le DPI est declare, mesure, confronte — jamais devine ------------


def test_dpi_is_mandatory_and_refused_when_degenerate(project: Path, tmp_path: Path) -> None:
    folder = tmp_path / "brut"
    write_image(folder / "a.tif", value=10)
    for bad in (0, -1, True, 1.5, None, "600"):
        with pytest.raises(scan_ingest.InvalidScanDpiError):
            scan_ingest.ingest_scan_lot(project, folder, dpi=bad)
    # `True` est un `int` en Python: sans la garde bool-avant-int il vaudrait 1.
    assert scan_ingest.validate_scan_dpi(600) == 600


def test_a_dpi_below_the_qr_minimum_warns_without_blocking(project: Path, tmp_path: Path) -> None:
    # Non bloquant: la decision de refus appartient au decodage QR de 5.2.
    folder = tmp_path / "brut"
    write_image(folder / "a.tif", value=10)
    report = scan_ingest.ingest_scan_lot(project, folder, dpi=qr_codes.QR_MIN_SCAN_DPI - 1)
    assert "DPI_BELOW_QR_MINIMUM" in report.warnings
    assert report.pages


def test_the_declared_dpi_is_never_replaced_by_the_measured_one(
    project: Path, tmp_path: Path
) -> None:
    """Un scanner en auto-fit ment: la mesure informe, elle ne se substitue pas."""
    folder = tmp_path / "brut"
    path = folder / "a.png"
    write_image(path, value=10)
    Image.open(path).save(path, dpi=(72, 72))

    report = scan_ingest.ingest_scan_lot(project, folder, dpi=600)
    assert report.declared_dpi == 600
    # Tolerance large a dessein: le PNG stocke sa resolution en pixels par
    # **metre**, en entier, donc 72 dpi ressort a 72,009. Epingler la valeur
    # exacte ferait echouer le test sur un detail de format, pas sur le
    # comportement teste.
    assert report.measured_dpi == pytest.approx(72.0, abs=0.1)
    assert "DPI_DECLARED_DIFFERS_FROM_FILE" in report.warnings


# --- AC 10: echec explicite, jamais de faux succes --------------------------


def test_an_empty_folder_is_a_hard_failure(project: Path, tmp_path: Path) -> None:
    folder = tmp_path / "vide"
    folder.mkdir()
    with pytest.raises(scan_ingest.EmptyScanLotError):
        scan_ingest.ingest_scan_lot(project, folder, dpi=600)


def test_non_image_files_are_ignored_without_being_counted(
    project: Path, tmp_path: Path
) -> None:
    # Le compteur compte des **pages**, pas des entrees de repertoire (defaut
    # `observed_frame_count` consigne en revue de 3.4).
    folder = tmp_path / "brut"
    write_image(folder / "a.tif", value=10)
    (folder / ".DS_Store").write_bytes(b"x")
    (folder / "Thumbs.db").write_bytes(b"x")
    (folder / "notes.md").write_text("hors perimetre", encoding="utf-8")
    (folder / "sous-dossier").mkdir()

    report = scan_ingest.ingest_scan_lot(project, folder, dpi=600)
    assert len(report.pages) == 1
    assert report.skipped_files == ()
    assert "UNREADABLE_FILE_SKIPPED" not in report.warnings


def test_one_unreadable_file_is_skipped_by_name_and_the_lot_survives(
    project: Path, tmp_path: Path
) -> None:
    folder = tmp_path / "brut"
    write_image(folder / "bonne.tif", value=10)
    (folder / "cassee.tif").write_bytes(b"ceci n'est pas une image")

    report = scan_ingest.ingest_scan_lot(project, folder, dpi=600)
    assert len(report.pages) == 1
    assert report.skipped_files == ("cassee.tif",)
    assert "UNREADABLE_FILE_SKIPPED" in report.warnings


def test_a_folder_where_nothing_is_readable_is_a_hard_failure(
    project: Path, tmp_path: Path
) -> None:
    folder = tmp_path / "brut"
    folder.mkdir()
    (folder / "a.tif").write_bytes(b"x")
    (folder / "b.tif").write_bytes(b"y")
    with pytest.raises(scan_ingest.EmptyScanLotError):
        scan_ingest.ingest_scan_lot(project, folder, dpi=600)


def test_an_unsupported_input_shape_is_refused(project: Path, tmp_path: Path) -> None:
    odd = tmp_path / "lot.zip"
    odd.write_bytes(b"PK\x03\x04")
    with pytest.raises(scan_ingest.UnsupportedScanInputError):
        scan_ingest.ingest_scan_lot(project, odd, dpi=600)
    with pytest.raises(scan_ingest.UnsupportedScanInputError):
        scan_ingest.ingest_scan_lot(project, tmp_path / "absent", dpi=600)


def test_every_hard_failure_shares_one_catchable_base(project: Path, tmp_path: Path) -> None:
    for error in (
        scan_ingest.UnsupportedScanInputError,
        scan_ingest.EmptyScanLotError,
        scan_ingest.InvalidScanDpiError,
        scan_ingest.PdfIngestError,
    ):
        assert issubclass(error, scan_ingest.ScanIngestError)


# --- AC 2 / 3 / 4: la forme PDF ---------------------------------------------


def test_a_pdf_ingests_its_pages_in_document_order(project: Path, tmp_path: Path) -> None:
    pdf = write_pdf(tmp_path / "lot.pdf", pages=3)
    report = scan_ingest.ingest_scan_lot(project, pdf, dpi=150)
    assert [page.read_rank for page in report.pages] == [0, 1, 2]
    assert [page.locator.page_index for page in report.pages] == [0, 1, 2]
    assert all(page.scan_input_format == "pdf" for page in report.pages)


def test_two_ingestions_of_the_same_pdf_are_byte_identical(
    project: Path, tmp_path: Path
) -> None:
    # L'ordre d'un PDF ne depend d'aucun tri de systeme de fichiers: c'est
    # precisement ce que ce test doit constater.
    pdf = write_pdf(tmp_path / "lot.pdf", pages=3)
    first = scan_ingest.report_json(scan_ingest.ingest_scan_lot(project, pdf, dpi=150))
    second = scan_ingest.report_json(scan_ingest.ingest_scan_lot(project, pdf, dpi=150))
    assert first == second


def test_a_pdf_page_is_declared_eight_bits_and_says_why(project: Path, tmp_path: Path) -> None:
    """PDFium rasterise exclusivement en 8 bits, y compris sur un PDF 16 bits.

    L'honnetete consiste a le dire plutot qu'a revendiquer 16: un lot ingere en
    PDF entre degrade dans l'aller-retour de gamut, et c'est un avertissement,
    pas un refus.
    """
    pdf = write_pdf(tmp_path / "lot.pdf", pages=1)
    report = scan_ingest.ingest_scan_lot(project, pdf, dpi=150)
    page = report.pages[0]
    assert page.source_bit_depth == 8
    assert "PDF_RASTERIZED_AT_8_BITS" in page.warnings
    assert scan_ingest.load_page_array(project, page.locator, dpi=150).dtype == np.uint8


def test_a_rendered_pdf_page_comes_out_in_bgr(project: Path, tmp_path: Path) -> None:
    """Piege 8: PDFium rend deja du BGR.

    Le reflexe acquis sur Pillow est d'ajouter un `cvtColor(..., RGB2BGR)`, qui
    inverserait ici rouge et bleu — et `validate_bgr_input` ne peut pas le voir.
    Le test porte sur les **valeurs de canaux** d'un pixel relu, jamais sur les
    arguments passes a `render`.
    """
    pdf = write_pdf(tmp_path / "rouge.pdf", pages=1)
    report = scan_ingest.ingest_scan_lot(project, pdf, dpi=150)
    array = scan_ingest.load_page_array(project, report.pages[0].locator, dpi=150)
    height, width = array.shape[:2]
    blue, green, red = (int(v) for v in array[int(height * 0.35), int(width * 0.35)])
    assert red > 200 and blue < 50, f"attendu un rouge, relu B={blue} G={green} R={red}"


def test_a_pdf_mixing_page_sizes_is_reported(project: Path, tmp_path: Path) -> None:
    # A DPI constant, deux tailles de canevas donnent deux tailles de pixels.
    # Sans la taille de canevas au rapport, l'avertissement serait illisible.
    pdf = write_pdf(tmp_path / "mixte.pdf", sizes=[A4, letter])
    report = scan_ingest.ingest_scan_lot(project, pdf, dpi=150)
    assert "MIXED_PAGE_DIMENSIONS" in report.warnings
    assert len({(p.width_px, p.height_px) for p in report.pages}) == 2
    assert len({p.canvas_size_pt for p in report.pages}) == 2
    assert all(p.canvas_size_pt is not None for p in report.pages)


def test_a_pdf_embedding_a_jpeg_is_reported(project: Path, tmp_path: Path) -> None:
    # Beaucoup de pilotes de scanner ecrivent un PDF dont chaque page n'est
    # qu'un JPEG encapsule: le rendu parait propre et porte des artefacts de
    # blocs que la mesure des patchs prendrait pour du signal.
    pdf = write_pdf(tmp_path / "jpeg.pdf", pages=1, lossy=True)
    report = scan_ingest.ingest_scan_lot(project, pdf, dpi=150)
    assert "PDF_EMBEDS_LOSSY_IMAGE" in report.pages[0].warnings


def test_a_corrupt_pdf_is_a_hard_failure(project: Path, tmp_path: Path) -> None:
    broken = tmp_path / "casse.pdf"
    broken.write_bytes(b"%PDF-1.4 mais pas vraiment")
    with pytest.raises(scan_ingest.PdfIngestError):
        scan_ingest.ingest_scan_lot(project, broken, dpi=150)


def test_the_dpi_drives_the_pdf_render_scale(project: Path, tmp_path: Path) -> None:
    # `--dpi` est la seule source du facteur d'echelle: jamais un DPI devine, ni
    # la resolution native d'une image embarquee.
    pdf = write_pdf(tmp_path / "lot.pdf", pages=1)
    low = scan_ingest.ingest_scan_lot(project, pdf, dpi=100)
    high = scan_ingest.ingest_scan_lot(project, pdf, dpi=200)
    assert high.pages[0].width_px == pytest.approx(2 * low.pages[0].width_px, abs=2)


# --- AC 8: le localisateur et son aller-retour ------------------------------


@pytest.mark.parametrize("shape", ["dossier", "pdf"])
def test_the_locator_round_trips_to_the_pixels_the_report_announces(
    project: Path, tmp_path: Path, shape: str
) -> None:
    """La jonction posee a 5.2: elle obtient ses pixels par ici, jamais par un
    `cv2.imread` local.

    C'est la raison pour laquelle la signature prend un **localisateur** et non
    un chemin: une signature par chemin rendrait la forme PDF inaccessible et la
    ferait re-implementer ailleurs, avec un ordre de canaux et une profondeur
    decides une seconde fois.
    """
    if shape == "dossier":
        source = tmp_path / "brut"
        write_image(source / "a.tif", value=4000, dtype=np.uint16)
    else:
        source = write_pdf(tmp_path / "lot.pdf", pages=2)

    report = scan_ingest.ingest_scan_lot(project, source, dpi=150)
    for page in report.pages:
        array = scan_ingest.load_page_array(project, page.locator, dpi=report.declared_dpi)
        assert array.shape[1] == page.width_px
        assert array.shape[0] == page.height_px
        assert scan_ingest._channels_of(array) == page.channels
        assert scan_ingest._bit_depth_of(array) == page.source_bit_depth


def test_a_pdf_locator_carries_an_index_and_a_file_locator_does_not(
    project: Path, tmp_path: Path
) -> None:
    folder = tmp_path / "brut"
    write_image(folder / "a.tif", value=10)
    from_folder = scan_ingest.ingest_scan_lot(project, folder, dpi=600)
    assert from_folder.pages[0].locator.page_index is None

    pdf = write_pdf(tmp_path / "lot.pdf", pages=2)
    from_pdf = scan_ingest.ingest_scan_lot(project, pdf, dpi=150)
    assert [p.locator.page_index for p in from_pdf.pages] == [0, 1]
    assert len({p.locator.source_path for p in from_pdf.pages}) == 1


# --- AC 8: rapport canonique, fige en dur -----------------------------------


def test_the_report_document_shape_is_pinned(project: Path, tmp_path: Path) -> None:
    """Tout renommage de champ casse ce test, et c'est le but.

    Le rapport est le contrat que 5.2, 5.6 et 5.8 consomment; un champ renomme
    en silence les casserait toutes les trois, mais seulement a l'execution.
    """
    folder = tmp_path / "brut"
    write_image(folder / "a.tif", value=10)
    document = scan_ingest.report_document(
        scan_ingest.ingest_scan_lot(project, folder, dpi=600)
    )
    assert set(document) == {
        "ingest_slug",
        "scans_dir",
        "declared_dpi",
        "measured_dpi",
        "page_count",
        "skipped_file_count",
        "skipped_files",
        "warnings",
        "pages",
        "fingerprint",
    }
    assert set(document["pages"][0]) == {
        "read_rank",
        "locator",
        "scan_input_format",
        "source_bit_depth",
        "width_px",
        "height_px",
        "channels",
        "canvas_size_pt",
        "warnings",
    }
    assert set(document["pages"][0]["locator"]) == {"source_path", "page_index"}
    assert document["fingerprint"].startswith(scan_ingest.FINGERPRINT_PREFIX)


def test_the_report_carries_no_absolute_path(project: Path, tmp_path: Path) -> None:
    folder = tmp_path / "brut"
    write_image(folder / "a.tif", value=10)
    text = scan_ingest.report_json(scan_ingest.ingest_scan_lot(project, folder, dpi=600))
    assert str(tmp_path) not in text
    assert not any(
        Path(page["locator"]["source_path"]).is_absolute()
        for page in json.loads(text)["pages"]
    )


# --- AC 9: vocabulaire ferme ------------------------------------------------


def test_an_unknown_warning_code_is_refused() -> None:
    with pytest.raises(ValueError):
        scan_ingest.validate_warning_code("DPI_UN_PEU_BIZARRE")
    for code in scan_ingest.SCAN_INGEST_WARNING_CODES:
        assert scan_ingest.validate_warning_code(code) == code


def test_the_warning_vocabulary_covers_what_the_story_names() -> None:
    assert set(scan_ingest.SCAN_INGEST_WARNING_CODES) == {
        "DPI_BELOW_QR_MINIMUM",
        "DPI_DECLARED_DIFFERS_FROM_FILE",
        "DPI_NOT_MEASURABLE",
        "MIXED_PAGE_DIMENSIONS",
        "MIXED_BIT_DEPTHS",
        "UNREADABLE_FILE_SKIPPED",
        "PDF_RASTERIZED_AT_8_BITS",
        "PDF_EMBEDS_LOSSY_IMAGE",
    }


# --- AC 5 / 6: emplacement canonique et slug operateur ----------------------


def test_an_external_folder_is_copied_under_scans_and_the_copy_prevails(
    project: Path, tmp_path: Path
) -> None:
    folder = tmp_path / "cle-usb"
    write_image(folder / "a.tif", value=10)
    report = scan_ingest.ingest_scan_lot(project, folder, dpi=600)
    assert report.scans_dir == "scans/cle-usb"
    assert (project / "scans" / "cle-usb" / "a.tif").is_file()
    assert report.pages[0].locator.source_path.startswith("scans/")


def test_a_folder_already_under_scans_is_ingested_in_place(
    project: Path, tmp_path: Path
) -> None:
    folder = project / "scans" / "lot-a"
    write_image(folder / "a.tif", value=10)
    before = sorted(p.name for p in folder.iterdir())
    report = scan_ingest.ingest_scan_lot(project, folder, dpi=600)
    assert sorted(p.name for p in folder.iterdir()) == before
    assert report.scans_dir == "scans/lot-a"


def test_the_slug_is_an_operator_name_not_a_business_lot_id(
    project: Path, tmp_path: Path
) -> None:
    # Interdit: fabriquer un identifiant metier. Le `lot_id` est porte par le QR
    # et n'est connu qu'au decodage (story 5.2).
    folder = tmp_path / "peu-importe"
    write_image(folder / "a.tif", value=10)
    report = scan_ingest.ingest_scan_lot(project, folder, dpi=600, ingest_slug="lot-du-mardi")
    assert report.ingest_slug == "lot-du-mardi"
    assert "lot_id" not in report.as_document()
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "build_lot_id" not in source


# --- AC 11: frontieres verrouillees -----------------------------------------


def test_the_module_calls_nothing_that_belongs_to_a_downstream_story() -> None:
    """Un grep de ces symboles doit rendre zero.

    Chacun appartient a une autre story: detection (5.2), recadrage (5.3),
    export (5.6), manifest (5.7). Les voir apparaitre ici signifierait que la
    porte d'entree a commence a faire le travail de ce qu'elle alimente.
    """
    source = MODULE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "detect_markers",
        "compute_page_homography",
        "warp_page",
        "extract_scan_frames",
        "decode_qr_image",
        "export_frame_tiff16",
        "persist_extraction",
        "output-frames",
    ):
        assert forbidden not in source, forbidden


# --- Integration par la commande reelle -------------------------------------


def test_the_cli_ingests_and_writes_its_report(tmp_path: Path, capsys) -> None:
    folder = tmp_path / "lot-a"
    write_image(folder / "page_01.tif", value=10)
    write_image(folder / "page_02.tif", value=20)
    project_dir = tmp_path / "projet"

    assert cli.main(
        ["scan", "--project", str(project_dir), "--scan", str(folder), "--dpi", "600"]
    ) == 0

    report_path = project_dir / "scans" / "lot-a" / "ingest.json"
    assert report_path.is_file()
    document = json.loads(report_path.read_text(encoding="utf-8"))
    assert document["page_count"] == 2
    assert document["declared_dpi"] == 600
    assert (project_dir / "logs" / "scan.log").is_file()


def test_the_cli_refuses_a_degenerate_input_with_exit_code_one(tmp_path: Path) -> None:
    project_dir = tmp_path / "projet"
    empty = tmp_path / "vide"
    empty.mkdir()
    assert cli.main(
        ["scan", "--project", str(project_dir), "--scan", str(empty), "--dpi", "600"]
    ) == 1
    # Le journal existe malgre l'echec: le layout et le logger precedent le try.
    assert (project_dir / "logs" / "scan.log").is_file()


def test_the_poc_scan_path_and_the_new_command_coexist() -> None:
    """AC 1: `scan` n'est pas une extension de `poc process-scan`.

    Les deux chemins coexistent, et leur difference la plus visible est le DPI:
    le POC en a un par defaut a 300 (heritage assume), la nouvelle commande n'en
    a aucun. Si quelqu'un donnait un defaut a `scan`, ce test tomberait -- et
    c'est bien le point, un DPI devine fausse toute la geometrie aval en
    silence.
    """
    import argparse

    parser = argparse.ArgumentParser()
    # On reconstruit le parser par le chemin reel de la CLI plutot que d'en
    # inspecter le source: c'est le comportement qui compte.
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["scan", "--project", "p", "--scan", "s"])
    assert excinfo.value.code == 2, "--dpi doit etre obligatoire sur `scan`"

    # Le POC, lui, garde son defaut: la commande passe la validation d'argparse
    # sans `--dpi` (elle echouera plus loin, sur le projet inexistant).
    assert cli.main(["poc", "process-scan", "--project", "absent", "--scan", "absent"]) == 1


# --- Correctifs de la revue en trois couches --------------------------------
#
# Chaque test ci-dessous verrouille un finding nommement identifie. Les six
# premiers sont des defauts reels, les suivants des mutants qui survivaient.


def test_a_second_lot_never_inherits_the_pages_of_the_previous_one(
    project: Path, tmp_path: Path
) -> None:
    """5.1-C1-01, le bloquant: la decouverte se fait a la SOURCE.

    La premiere version copiait la source dans la destination puis **relisait la
    destination**: un residu d'un lot precedent y devenait une page du lot
    courant. Reproduit alors: une page a la source, trois au rapport, sans un
    avertissement. Un lot silencieusement faux est exactement le risque R12.
    """
    first = tmp_path / "lot"
    for name in ("p1.tif", "p2.tif", "p3.tif"):
        write_image(first / name, value=10)
    assert len(scan_ingest.ingest_scan_lot(project, first, dpi=600).pages) == 3

    # Meme slug, une seule page, contenu different: l'ecrasement est refuse...
    import shutil as _shutil

    _shutil.rmtree(first)
    write_image(first / "p1.tif", value=99)
    with pytest.raises(scan_ingest.UnsupportedScanInputError) as excinfo:
        scan_ingest.ingest_scan_lot(project, first, dpi=600)
    assert "contenu different" in str(excinfo.value)

    # ... et sous un autre slug, le lot ne compte qu'une page: aucun heritage.
    second = scan_ingest.ingest_scan_lot(project, first, dpi=600, ingest_slug="lot-bis")
    assert len(second.pages) == 1


def test_re_ingesting_the_same_scan_stays_idempotent(project: Path, tmp_path: Path) -> None:
    # La garde d'ecrasement ne doit mordre que sur un contenu **different**: un
    # operateur qui relance la commande apres une coupure ne doit pas avoir a
    # inventer un slug.
    folder = tmp_path / "lot"
    write_image(folder / "p1.tif", value=10)
    first = scan_ingest.ingest_scan_lot(project, folder, dpi=600)
    second = scan_ingest.ingest_scan_lot(project, folder, dpi=600)
    assert scan_ingest.report_json(first) == scan_ingest.report_json(second)


# `""` n'est pas dans la liste: une chaine vide est *falsy* et retombe donc sur
# le slug par defaut (le nom du dossier), ce qui est le comportement voulu — un
# `--lot-slug ""` vaut « pas de slug fourni », pas « slug invalide ».
@pytest.mark.parametrize(
    "slug", ["../../evade", "..", ".", "a/b", "x" * 200, "/absolu"]
)
def test_a_slug_can_never_escape_the_project(project: Path, tmp_path: Path, slug: str) -> None:
    """5.1-C1-03 / C2-1: `--lot-slug ../../evade` ecrivait hors du projet.

    Et la commande rendait **0** -- un succes annonce pour des fichiers deposes
    deux niveaux au-dessus du projet, `scans/` restant vide.
    """
    folder = tmp_path / "brut"
    write_image(folder / "a.tif", value=10)
    with pytest.raises(scan_ingest.UnsupportedScanInputError):
        scan_ingest.ingest_scan_lot(project, folder, dpi=600, ingest_slug=slug)
    assert not (project.parent.parent / "evade").exists()


def test_scans_dir_names_the_folder_actually_used(project: Path) -> None:
    """5.1-C1-02 / C2-4: `scans_dir` etait derive du slug, pas du dossier lu.

    Une ingestion en place sous `scans/<date>/<lot>/` produisait donc un
    `scans_dir` inexistant, et la CLI mourait sur une `FileNotFoundError` nue
    **apres** une ingestion pourtant reussie.
    """
    nested = project / "scans" / "2026-08-08" / "lot-c"
    write_image(nested / "p1.tif", value=10)
    report = scan_ingest.ingest_scan_lot(project, nested, dpi=600)
    assert report.scans_dir == "scans/2026-08-08/lot-c"
    assert (project / report.scans_dir).is_dir()


def test_the_inside_scans_guard_is_not_lexical(project: Path, tmp_path: Path) -> None:
    """5.1-C2-3: `relative_to` est purement lexical.

    Un dossier exterieur atteint par `scans/../..` lui paraissait deja sous
    `scans/` et etait donc ingere **sans copie**, contre l'AC 5 -- et
    `load_page_array` lisait alors des pixels hors du projet.
    """
    outside = tmp_path / "dehors"
    write_image(outside / "p1.tif", value=10)
    sneaky = project / "scans" / ".." / ".." / outside.name
    report = scan_ingest.ingest_scan_lot(project, sneaky, dpi=600, ingest_slug="lot-d")
    assert report.scans_dir == "scans/lot-d"
    for page in report.pages:
        assert (project / page.locator.source_path).is_file()


def test_the_dpi_of_a_pdf_is_measured_and_confronted(project: Path, tmp_path: Path) -> None:
    """5.1-C3-3 / C2-7: `measured_dpi` valait `None` en dur sur un PDF.

    Le faux succes que l'AC 7 decrit nommement etait donc indetectable: un
    `--dpi 600` sur une page dont l'image embarquee n'est qu'a 144 dpi produit
    une page de 600 dpi **nominaux** et de 144 dpi reels -- dimensions
    correctes, detail inexistant. C'est le risque R8, et il est d'autant plus
    vicieux sur un PDF que `--dpi` y pilote le rendu.
    """
    photo = tmp_path / "photo.jpg"
    Image.fromarray(
        np.random.default_rng(0).integers(0, 255, (200, 300, 3), dtype=np.uint8)
    ).save(photo)
    pdf = tmp_path / "scan.pdf"
    canvas = pdfcanvas.Canvas(str(pdf), pagesize=A4)
    canvas.drawImage(ImageReader(str(photo)), 50, 400, width=150, height=100)
    canvas.save()

    report = scan_ingest.ingest_scan_lot(project, pdf, dpi=600)
    assert report.measured_dpi is not None
    assert report.measured_dpi < 600
    assert "DPI_DECLARED_DIFFERS_FROM_FILE" in report.warnings


def test_the_dpi_is_measured_on_every_page_not_only_the_first(
    project: Path, tmp_path: Path
) -> None:
    # 5.1-C2-6: la mesure portait sur le seul premier fichier trie -- parfois
    # celui qui sera ensuite saute comme illisible.
    folder = tmp_path / "brut"
    for name, dpi in (("a.png", 600), ("b.png", 150)):
        path = write_image(folder / name, value=10)
        Image.open(path).save(path, dpi=(dpi, dpi))
    report = scan_ingest.ingest_scan_lot(project, folder, dpi=600)
    # La plus basse borne la finesse reellement disponible.
    assert report.measured_dpi == pytest.approx(150.0, abs=0.5)
    assert "DPI_DECLARED_DIFFERS_FROM_FILE" in report.warnings


def test_a_broken_symlink_is_skipped_by_name_not_silently_dropped(
    project: Path, tmp_path: Path
) -> None:
    """5.1-C2-5: un lien casse n'etait ni page, ni saut, ni compte, ni avertissement.

    `Path.is_file()` est faux sur un lien symbolique casse: le fichier
    disparaissait donc du lot **sans laisser de trace**, ce qui est le faux
    succes R12 exact -- l'operateur croit avoir ingere une page qui n'existe pas.
    """
    folder = tmp_path / "liens"
    write_image(folder / "ok.tif", value=10)
    (folder / "page_01.tif").symlink_to(tmp_path / "inexistant.tif")

    report = scan_ingest.ingest_scan_lot(project, folder, dpi=600)
    assert len(report.pages) == 1
    assert report.skipped_files == ("page_01.tif",)
    assert "UNREADABLE_FILE_SKIPPED" in report.warnings


# --- Mutants qui survivaient -------------------------------------------------


def test_the_pdf_scale_constant_is_pinned_to_the_pdf_user_space() -> None:
    """Mutant survivant: `PDF_POINTS_PER_INCH` pouvait passer de 72 a 96.

    Le contrat le plus porteur de la forme PDF -- `scale = dpi / 72` -- n'etait
    verrouille par aucun test, et une echelle fausse de 33 % ne se voit pas sur
    une page isolee: elle se verra au recadrage, quatre stories plus loin.
    72 points par pouce est l'espace utilisateur PDF, ce n'est pas un reglage.
    """
    assert scan_ingest.PDF_POINTS_PER_INCH == 72.0


def test_a_pdf_page_renders_at_the_size_the_declared_dpi_implies(
    project: Path, tmp_path: Path
) -> None:
    # Verification par les dimensions **mesurees**, pas par la constante: une
    # page A4 (595,3 x 841,9 pt) a 300 dpi fait 2480 x 3508 px a un pixel pres.
    pdf = write_pdf(tmp_path / "a4.pdf", pages=1)
    report = scan_ingest.ingest_scan_lot(project, pdf, dpi=300)
    page = report.pages[0]
    assert page.width_px == pytest.approx(round(210 / 25.4 * 300), abs=2)
    assert page.height_px == pytest.approx(round(297 / 25.4 * 300), abs=2)


def test_load_page_array_returns_the_requested_page_not_always_the_first(
    project: Path, tmp_path: Path
) -> None:
    """Mutant survivant: `load_page_array` pouvait rendre toujours la page 0.

    Il faut donc des pages **distinguables**: deux tailles differentes suffisent,
    et c'est plus robuste qu'une comparaison de pixels sur un rendu.
    """
    pdf = write_pdf(tmp_path / "mixte.pdf", sizes=[A4, letter])
    report = scan_ingest.ingest_scan_lot(project, pdf, dpi=100)
    shapes = [
        scan_ingest.load_page_array(project, page.locator, dpi=100).shape[:2]
        for page in report.pages
    ]
    assert shapes[0] != shapes[1]
    for page, shape in zip(report.pages, shapes):
        assert shape == (page.height_px, page.width_px)


def test_the_ingestion_copies_and_never_moves_the_operator_files(
    project: Path, tmp_path: Path
) -> None:
    """Mutant survivant: `shutil.copy2` pouvait devenir `shutil.move`.

    La commande aurait alors **vide le dossier source de l'operateur** sans
    qu'un seul test ne tombe. Le scan est la donnee de quelqu'un d'autre.
    """
    folder = tmp_path / "cle-usb"
    write_image(folder / "p1.tif", value=10)
    write_image(folder / "p2.tif", value=20)
    before = sorted(path.name for path in folder.iterdir())

    scan_ingest.ingest_scan_lot(project, folder, dpi=600)

    assert sorted(path.name for path in folder.iterdir()) == before
    assert (folder / "p1.tif").is_file()


def test_the_unicode_normalisation_is_what_makes_the_order_stable(
    project: Path, tmp_path: Path
) -> None:
    """Mutant survivant: retirer la normalisation NFC ne cassait rien.

    Il faut des noms dont l'ordre **change** selon qu'on normalise ou non. Un
    `e` accentue s'ecrit U+00E9 (233) en NFC, et `e` (101) suivi d'un accent
    combinant en NFD. Face a `zulu` (`z` = 122), les deux formes trient donc a
    l'oppose: le nom decompose passe **avant** zulu en comparaison brute, et
    **apres** une fois normalise. C'est exactement la divergence entre deux
    machines que la normalisation supprime — et un lot dont l'ordre depend du
    systeme de fichiers est un lot dont le rang de lecture ne veut rien dire.
    """
    folder = tmp_path / "brut"
    decomposed = unicodedata.normalize("NFD", "éclair.tif")
    write_image(folder / decomposed, value=10)
    write_image(folder / "zulu.tif", value=20)

    # Temoin de la premisse: sans normalisation, l'ordre serait l'autre. Si ce
    # jour-la le systeme de fichiers normalisait les noms a l'ecriture, ce
    # temoin tomberait et signalerait que le test ne prouve plus rien.
    assert sorted([decomposed, "zulu.tif"]) == [decomposed, "zulu.tif"]

    report = scan_ingest.ingest_scan_lot(project, folder, dpi=600)
    names = [
        unicodedata.normalize("NFC", Path(p.locator.source_path).name)
        for p in report.pages
    ]
    assert names == ["zulu.tif", "éclair.tif"], (
        "avec normalisation NFC, le nom accentue trie apres zulu; l'ordre inverse "
        "signalerait que la normalisation a disparu"
    )


def test_the_rendered_pdf_array_owns_its_data(project: Path, tmp_path: Path) -> None:
    """Mutant survivant: le `copy=True` du rendu PDF.

    Motif rectifie apres verification: la vue ne pointe pas sur de la memoire
    liberee -- pypdfium2 attache son finalizer au buffer, que la vue retient par
    `.base`. La copie reste voulue pour trois raisons independantes de la
    version: detacher le tableau d'un detail d'implementation tiers, le rendre
    contigu et proprietaire comme le reste du depot le suppose, et ne pas
    retenir tout un tampon de page par lot.
    """
    pdf = write_pdf(tmp_path / "lot.pdf", pages=1)
    report = scan_ingest.ingest_scan_lot(project, pdf, dpi=100)
    array = scan_ingest.load_page_array(project, report.pages[0].locator, dpi=100)
    assert array.flags["OWNDATA"]
    assert array.base is None


def test_the_report_uses_the_shared_canonicalisation(project: Path, tmp_path: Path) -> None:
    # Mutant survivant: la canonicalisation importee pouvait etre remplacee par
    # un `json.dumps` local. Deux recettes qui divergent sont le defaut corrige
    # en revue de 3.5 — et l'empreinte cesserait d'etre comparable entre modules.
    from mixed_media_utility import extraction_previz

    folder = tmp_path / "brut"
    write_image(folder / "a.tif", value=10)
    report = scan_ingest.ingest_scan_lot(project, folder, dpi=600)
    document = scan_ingest.report_document(report)
    assert scan_ingest.report_json(report) == extraction_previz.canonical_json(document)
    assert document["fingerprint"] == extraction_previz.fingerprint_of(
        {k: v for k, v in document.items() if k != "fingerprint"}
    )


# --- Cas nommement exiges par l'AC 12 et absents ----------------------------


def test_an_encrypted_pdf_is_a_hard_failure(project: Path, tmp_path: Path) -> None:
    pdf = tmp_path / "chiffre.pdf"
    canvas = pdfcanvas.Canvas(str(pdf), pagesize=A4)
    canvas.setEncrypt("motdepasse")
    canvas.drawString(100, 700, "secret")
    canvas.save()
    with pytest.raises(scan_ingest.PdfIngestError):
        scan_ingest.ingest_scan_lot(project, pdf, dpi=150)


def test_a_pdf_without_any_page_is_a_hard_failure(project: Path, tmp_path: Path) -> None:
    # Une sequence vide rendue en succes serait le faux succes R12.
    pdf = tmp_path / "vide.pdf"
    pdf.write_bytes(
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Count 0/Kids[]>>endobj\n"
        b"trailer<</Root 1 0 R>>\n%%EOF\n"
    )
    with pytest.raises(scan_ingest.ScanIngestError):
        scan_ingest.ingest_scan_lot(project, pdf, dpi=150)


def test_a_rotated_pdf_page_renders_whole(project: Path, tmp_path: Path) -> None:
    """Une page `/Rotate` n'est pas tronquee — verifie plutot que suppose.

    Une revue avait signale 70,7 % de pixels utiles sur une page pivotee. La
    mesure refaite montre que le chiffre venait d'un rectangle de test
    dimensionne sur l'autre orientation (595/842 = 0,7067), pas du rendu:
    pypdfium2 rend `get_size()` deja tourne et rasterise la page entiere. Le
    test fige ce constat, pour qu'une regression de la dependance se voie.
    """
    import pypdfium2 as pdfium

    pdf = tmp_path / "rot.pdf"
    canvas = pdfcanvas.Canvas(str(pdf), pagesize=A4)
    canvas.setFillColorRGB(1, 0, 0)
    canvas.rect(0, 0, A4[0], A4[1], stroke=0, fill=1)
    canvas.save()
    document = pdfium.PdfDocument(pdf)
    document[0].set_rotation(90)
    document.save(str(tmp_path / "rot90.pdf"))
    document.close()

    report = scan_ingest.ingest_scan_lot(project, tmp_path / "rot90.pdf", dpi=100)
    array = scan_ingest.load_page_array(project, report.pages[0].locator, dpi=100)
    red_ratio = ((array[..., 2] > 200) & (array[..., 0] < 50)).mean()
    assert red_ratio > 0.99, f"page pivotee rasterisee a {red_ratio:.1%} seulement"
    # Le canevas rapporte est le canevas **tourne**, coherent avec les pixels.
    page = report.pages[0]
    assert (page.width_px > page.height_px) == (
        page.canvas_size_pt[0] > page.canvas_size_pt[1]
    )
