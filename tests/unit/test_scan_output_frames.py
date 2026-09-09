"""Tests de l'ecriture des frames rescannees vers `output-frames/` (story 5.6).

Deux exigences structurent ce fichier.

**Contre les vrais producteurs** (action item 3 de la retro Epic 4): les noms de
fichiers et les noms de dossiers attendus sont derives de `io.naming` et
`io.project_layout` reels, les formes de frames du plan de decoupe reel de
`scan_crop`, et les gabarits du registre reel de `page_templates`. Aucune chaine
recopiee a la main, aucun `SimpleNamespace` de fixture: deux morceaux du systeme
verts chacun sur ses propres fixtures et jamais confrontes sont exactement la
classe de defaut que la retro designe.

**Par relecture du fichier**: une valeur de retour ne prouve pas ce qui est sur
le disque. La profondeur 16 bits, l'ordre des canaux et le contenu de la mire se
verifient tous par `cv2.IMREAD_UNCHANGED`, jamais par le dict rendu par
l'export -- c'est precisement ce que le POC ne fait pas, et pourquoi il tronque
a 8 bits sans le savoir.
"""

from __future__ import annotations

import ast
import logging
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import (  # noqa: E402
    color_pipeline,
    page_roles,
    page_templates,
    scan_crop,
    scan_output_frames as sof,
)
from mixed_media_utility.io import naming, payload as payload_io, project_layout  # noqa: E402

MODULE_PATH = REPO_ROOT / "src" / "mixed_media_utility" / "scan_output_frames.py"

DPI = 300
RUSH = "rush-001"
FPS = 5.0
PORTRAIT_2F = "tpl-a4-portrait-2f-v1"
PORTRAIT_8F_M5 = "tpl-a4-portrait-8f-m5-v1"
PAYSAGE_8F_M5 = "tpl-a4-paysage-8f-m5-v1"

#: Bornes d'un lot borne, telles que l'extraction 3.7 les fournit.
IN_TC = "15:34:30:00"
OUT_TC = "15:34:50:00"


# --- fabriques: tout derive des vrais producteurs ---------------------------


def timecode(index: int) -> str:
    return f"{index // 3600:02d}:{index // 60 % 60:02d}:{index % 60:02d}:00"


def make_payload(
    *,
    page_index: int,
    page_count: int,
    first_slot: int,
    slot_count: int,
    template_id: str = PORTRAIT_2F,
    rush_id: str = RUSH,
    fps_target: float = FPS,
    lot_id: str | None = None,
    timecodes: list[str] | None = None,
) -> dict:
    """Payload QR reel, valide par `io.payload` et jamais bricole a la main."""
    slots = [
        {
            "slot_index": first_slot + index,
            "frame_timecode": (
                timecodes[index] if timecodes is not None else timecode(first_slot + index)
            ),
        }
        for index in range(slot_count)
    ]
    return payload_io.build_page_payload(
        project_id="projet-test",
        rush_id=rush_id,
        lot_id=lot_id if lot_id is not None else naming.build_lot_id(rush_id, fps_target),
        page_index=page_index,
        page_count=page_count,
        fps_target=fps_target,
        timecode_base_fps="25/1",
        template_id=template_id,
        patch_preset_id="patch-values-2",
        target_colorspace="bt709",
        gamut_map_id=payload_io.GAMUT_MAP_IDENTITY,
        slots=slots,
    )


def crop_plan_for(payload: dict, *, dpi: int = DPI) -> scan_crop.PageCropPlan:
    """Plan de decoupe du **vrai** module 5.3, jamais une forme recopiee."""
    return scan_crop.build_page_crop_plan(
        template_id=payload["template_id"], slots=payload["slots"], dpi=dpi
    )


#: Ecart entre deux temoins de slots voisins. Assez grand pour qu'aucune
#: confusion ne soit possible a la relecture, assez petit pour tenir en 16 bits
#: quel que soit le `slot_index` d'un lot reel.
SLOT_WITNESS_STEP = 137


def slot_witness(slot_index: int, *, fill: int = 4096) -> int:
    """Valeur de remplissage **propre a un slot**.

    Toutes les fabriques de pixels de ce fichier remplissaient une page d'une
    valeur uniforme, si bien qu'une **permutation** de l'appariement slot <->
    frame y etait litteralement invisible: le mutant qui inverse l'ordre
    (`page.frames[len(slots) - 1 - position]`) laissait les 165 tests du lot
    cible verts, alors qu'il grave le timecode d'une frame dans le nom d'une
    autre -- et le nom est le seul support d'identite d'un fichier qui voyage
    seul. C'est la famille « un test peut etre vert et vide » que ce depot a
    deja payee trois fois; elle se ferme en rendant chaque frame d'une page
    distinguable.
    """
    return fill + SLOT_WITNESS_STEP * slot_index


def crops_for(
    plan: scan_crop.PageCropPlan, *, channels: int = 3, fill: int = 4096
) -> tuple[np.ndarray, ...]:
    """Frames decoupees synthetiques, aux dimensions exactes du plan reel.

    Chaque frame porte le temoin de **son** slot: voir `slot_witness`.
    """
    frames = []
    for frame in plan.frames:
        shape = (frame.height_px, frame.width_px)
        array = np.full(
            shape if channels is None else shape + (channels,),
            slot_witness(frame.slot_index, fill=fill),
            np.uint16,
        )
        frames.append(array)
    return tuple(frames)


def full_page(payload: dict, *, dpi: int = DPI, channels: int = 3) -> sof.ScannedPage:
    plan = crop_plan_for(payload, dpi=dpi)
    return sof.ScannedPage(
        payload=payload, crop_plan=plan, frames=crops_for(plan, channels=channels)
    )


def failed_page(payload: dict, reason: str, *, dpi: int = DPI) -> sof.ScannedPage:
    return sof.ScannedPage(
        payload=payload, crop_plan=crop_plan_for(payload, dpi=dpi), failure=reason
    )


#: Gabarit v2, le seul regime qui porte une page de calibration. Deux frames par page,
#: comme `PORTRAIT_2F`, pour que la seule difference mesuree soit la page de calibration.
PORTRAIT_2F_V2 = "tpl-a4-portrait-2f-v2"


def calibration_payload(*, page_count: int, template_id: str = PORTRAIT_2F_V2) -> dict:
    """Payload de la **page de calibration** du lot: index 0, aucun emplacement.

    Par son vrai producteur, avec le role que `pdf_composition` lui pose. `slot_count = 0`
    n'est licite **que** sous ce role: la garde d'emplacements d'`io.payload` refuse une
    planche d'images vide, et c'est ce qui rend la fabrique impossible a se tromper.
    """
    return payload_io.build_page_payload(
        project_id="projet-test",
        rush_id=RUSH,
        lot_id=naming.build_lot_id(RUSH, FPS),
        page_index=page_roles.CALIBRATION_PAGE_INDEX,
        page_count=page_count,
        fps_target=FPS,
        timecode_base_fps="",
        template_id=template_id,
        patch_preset_id="patch-values-2",
        target_colorspace="bt709",
        gamut_map_id=payload_io.GAMUT_MAP_IDENTITY,
        slots=[],
        page_role=page_roles.PAGE_ROLE_CALIBRATION,
        # AMENDE PAR 5.23 (2026-08-18): le libelle de chaine est **obligatoire** sous ce
        # role -- une page de calibration anonyme ne se distinguerait pas d'une autre --
        # et **refuse** sous le role d'images, ce qui rend cette fabrique aussi
        # impossible a se tromper que `slot_count = 0` la rend deja.
        scan_chain_label="hp envy 4520 tiff 600 dpi auto corr off",
    )


def scanned_calibration_page(payload: dict) -> sof.ScannedPage:
    """La page de calibration telle que la chaine de scan la remet a 5.6.

    Exactement la forme que `cli._scanned_pages_for_output` construit pour elle: aucun
    plan de decoupe, aucune frame. C'est la quatrieme nature de page du chemin de scan,
    et elle est reconnue **par son role**.
    """
    return sof.ScannedPage(payload=payload, crop_plan=None, frames=())


def v2_lot_with_calibration_page(*, images_pages: int = 2) -> list[sof.ScannedPage]:
    """Un lot v2 **complet** de la forme nominale depuis 5.16.

    Une page de calibration a l'index 0 **plus** des planches d'images: c'est la forme que
    la story rend nominale, et aucun test ne la composait devant
    `write_lot_output_frames` -- c'est litteralement ce qui a laisse passer le bloquant
    B1. Deux planches d'images au minimum, et leurs emplacements sont distinguables: une
    fabrique mono-planche rendrait invisible toute erreur de position dans la pagination.
    """
    page_count = 1 + images_pages
    pages = [scanned_calibration_page(calibration_payload(page_count=page_count))]
    for rank in range(images_pages):
        payload = make_payload(
            page_index=1 + rank, page_count=page_count,
            first_slot=2 * rank, slot_count=2, template_id=PORTRAIT_2F_V2)
        pages.append(full_page(payload))
    return pages


def two_page_lot(**kwargs) -> tuple[dict, dict]:
    first = make_payload(page_index=0, page_count=2, first_slot=0, slot_count=2, **kwargs)
    second = make_payload(page_index=1, page_count=2, first_slot=2, slot_count=2, **kwargs)
    return first, second


def read_written(path: Path) -> np.ndarray:
    """Relecture **sans conversion**: la seule preuve de ce qui est sur le disque."""
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    assert image is not None, f"fichier illisible: {path}"
    return image


# --- AC 1: la convention de nom et son lecteur ------------------------------


@pytest.mark.parametrize(
    "rush_id, fps_target, frame_timecode",
    [
        ("rush-001", 5, "00:00:00:00"),
        ("rush-001", 24.0, "01:23:45:12"),
        ("rush-001", 12.5, "00:00:07:03"),
        ("rush-001", 23.976, "10:00:00:00"),
        ("A" * 80, 30, "00:00:01:00"),
        ("rush_avec_souligne", 60, "23:59:59:29"),
    ],
)
def test_the_scan_frame_name_round_trips(rush_id, fps_target, frame_timecode) -> None:
    """Tout nom construit se relit, et rend exactement le timecode d'origine."""
    name = naming.build_scan_frame_filename(rush_id, fps_target, frame_timecode)
    assert naming.read_scan_frame_timecode(name) == frame_timecode
    # Le contrat du lecteur s'arrete a la lecture: l'appartenance au lot se
    # verifie en reconstruisant, exactement comme cote `frames/`.
    assert (
        naming.build_scan_frame_filename(rush_id, fps_target, frame_timecode) == name
    )


def test_the_scan_frame_name_carries_the_prefix_and_the_extracted_shape() -> None:
    """Le nom est celui de `frames/`, prefixe -- pas une seconde recette."""
    scan_name = naming.build_scan_frame_filename(RUSH, FPS, "00:00:03:00")
    extracted_name = naming.build_extracted_frame_filename(RUSH, FPS, "00:00:03:00")
    assert scan_name == f"{naming.SCAN_FRAME_PREFIX}{extracted_name}"
    assert scan_name.endswith(naming.EXTRACTED_FRAME_SUFFIX)


def test_a_fractional_fps_never_puts_a_dot_in_the_name() -> None:
    """`12.5` rend `12p5`: un point violerait le pattern du schema v2 (piege 5)."""
    name = naming.build_scan_frame_filename(RUSH, 12.5, "00:00:00:00")
    assert "12p5" in name
    assert name.count(".") == 1  # le seul point est celui de l'extension
    assert name == f"scan_{RUSH}_12p5_00-00-00-00.tiff"


def test_a_long_rush_id_is_shortened_in_the_name_but_not_in_the_directory() -> None:
    """Comportement herite de `frames/`, reproduit tel quel et non corrige.

    `derive_short_id` s'applique au seul `rush_id` dans le nom de fichier; le
    slug de dossier, lui, porte le `rush_id` entier.
    """
    long_rush = "A" * (naming.CANONICAL_ID_MAX_LENGTH + 10)
    name = naming.build_scan_frame_filename(long_rush, FPS, "00:00:00:00")
    assert long_rush not in name
    assert naming.derive_short_id(long_rush) in name
    assert long_rush in project_layout.rush_dir_slug(long_rush, FPS)


@pytest.mark.parametrize(
    "name",
    [
        "rush-001_5_00-00-00-00.tiff",  # frame extraite: pas de prefixe scan_
        "scan_rush-001_5_00-00-00-00.png",  # mauvaise extension
        "scan_rush-001_5_00:00:00:00.tiff",  # timecode non assaini
        "scan_rush-001_5_0-0-0-0.tiff",  # timecode mal forme
        "scan_00-00-00-00.tiff",  # ni rush ni cadence
        "scan_rush-001_5_.tiff",
        ".tiff",
        "",
    ],
)
def test_a_nonconforming_name_is_refused_explicitly(name: str) -> None:
    with pytest.raises(naming.NamingError):
        naming.read_scan_frame_timecode(name)


def test_the_reader_refuses_an_extracted_frame_name() -> None:
    """Sans cette garde, la verification de dossier de l'AC 7 declarerait
    conforme un fichier de `frames/` egare dans `output-frames/`."""
    extracted = naming.build_extracted_frame_filename(RUSH, FPS, "00:00:00:00")
    with pytest.raises(naming.NamingError, match="prefixe"):
        naming.read_scan_frame_timecode(extracted)
    assert not sof.is_conforming_scan_frame_name(extracted, RUSH, FPS)


# --- AC 2 et AC 3: le dossier, derivable du QR seul -------------------------


def test_an_unbounded_lot_directory_is_derived_from_rush_and_fps() -> None:
    lot_id = naming.build_lot_id(RUSH, FPS)
    slug = sof.derive_lot_dir_slug(rush_id=RUSH, fps_target=FPS, lot_id=lot_id)
    assert slug == project_layout.rush_dir_slug(RUSH, FPS)


def test_a_bounded_lot_directory_is_the_lot_id_verbatim() -> None:
    """Les bornes ne sont pas dans le QR: le `lot_id` **est** le slug."""
    lot_id = naming.build_lot_id(
        RUSH, FPS, source_in_timecode=IN_TC, source_out_timecode=OUT_TC
    )
    slug = sof.derive_lot_dir_slug(rush_id=RUSH, fps_target=FPS, lot_id=lot_id)
    assert slug == project_layout.rush_dir_slug(
        RUSH, FPS, source_in_timecode=IN_TC, source_out_timecode=OUT_TC
    )
    assert slug == lot_id


def test_a_long_rush_id_unbounded_lot_still_resolves_to_the_full_directory() -> None:
    """Le `lot_id` est raccourci, le dossier non: c'est le dossier qui fait foi."""
    long_rush = "B" * (naming.CANONICAL_ID_MAX_LENGTH + 5)
    lot_id = naming.build_lot_id(long_rush, FPS)
    assert lot_id != project_layout.rush_dir_slug(long_rush, FPS)
    slug = sof.derive_lot_dir_slug(rush_id=long_rush, fps_target=FPS, lot_id=lot_id)
    assert slug == project_layout.rush_dir_slug(long_rush, FPS)


@pytest.mark.parametrize("fps_target", [5, 12.5, 23.976, 24.0, 60])
def test_the_directory_derivation_holds_at_every_target_rate(fps_target) -> None:
    lot_id = naming.build_lot_id(RUSH, fps_target)
    assert sof.derive_lot_dir_slug(
        rush_id=RUSH, fps_target=fps_target, lot_id=lot_id
    ) == project_layout.rush_dir_slug(RUSH, fps_target)


@pytest.mark.parametrize(
    "rush_id",
    [
        "r",
        "rush-001",
        "A005_C012_20260806_TOURNAGE",
        "x" * 30,
    ],
)
@pytest.mark.parametrize("fps_target", [5, 12.5, 23.976])
def test_a_bounded_lot_id_equals_its_directory_slug(rush_id, fps_target) -> None:
    """INVARIANTE VERROUILLEE (story 5.6, AC 3).

    La reconstruction du dossier de sortie depuis le QR seul (AC 2) repose
    entierement sur cette egalite: le payload QR ne porte **ni**
    `source_in_timecode` **ni** `source_out_timecode`, donc le seul moyen de
    retrouver le dossier d'un lot borne est de prendre son `lot_id` verbatim.

    L'egalite tient parce que `naming.build_lot_id` **refuse a l'entree** toute
    extraction bornee dont l'identifiant complet depasse
    `CANONICAL_ID_MAX_LENGTH` (revue du 2026-08-06, arbitrage d'Egan option c).
    Assouplir cette garde -- par exemple en raccourcissant aussi le nom de
    dossier, l'option ecartee a la revue -- ferait diverger les deux et
    produirait des dossiers de sortie **introuvables au moment de l'`encode`**,
    sans qu'aucune autre chose ne tombe. Si ce test echoue, ce n'est pas lui
    qu'il faut ajuster: c'est la story 5.6 qu'il faut rouvrir.
    """
    lot_id = naming.build_lot_id(
        rush_id, fps_target, source_in_timecode=IN_TC, source_out_timecode=OUT_TC
    )
    directory_slug = project_layout.rush_dir_slug(
        rush_id, fps_target, source_in_timecode=IN_TC, source_out_timecode=OUT_TC
    )
    assert lot_id == directory_slug, (
        "Un lot_id borne a cesse d'etre egal a son slug de dossier. La "
        "reconstruction du dossier de sortie depuis le QR de la story 5.6 en "
        "depend: le QR ne porte pas les bornes, et sans cette egalite un lot "
        "borne n'a plus aucun moyen de retrouver son dossier."
    )


@pytest.mark.parametrize("fps_target", [5, 12.5, 23.976])
def test_the_invariant_holds_right_up_to_the_refusal_boundary(fps_target) -> None:
    """L'egalite tient jusqu'au dernier caractere accepte, et pas au-dela.

    La longueur limite se **calcule** depuis les constantes de `io.naming`,
    jamais recopiee: c'est elle qui deplacerait l'invariante si elle bougeait.
    """
    fragment = f"{naming.format_fps_short(fps_target)}-{'0' * naming.BOUNDS_SUFFIX_LENGTH}"
    longest = naming.CANONICAL_ID_MAX_LENGTH - len(fragment) - 1
    rush_id = "y" * longest
    assert naming.build_lot_id(
        rush_id, fps_target, source_in_timecode=IN_TC, source_out_timecode=OUT_TC
    ) == project_layout.rush_dir_slug(
        rush_id, fps_target, source_in_timecode=IN_TC, source_out_timecode=OUT_TC
    )
    with pytest.raises(naming.NamingError, match="trop long"):
        naming.build_lot_id(
            "y" * (longest + 1), fps_target,
            source_in_timecode=IN_TC, source_out_timecode=OUT_TC,
        )


def test_the_output_directory_matches_the_real_project_layout(tmp_path: Path) -> None:
    """Integration: le dossier ecrit est celui que `project_layout` designe."""
    first, second = two_page_lot()
    report = sof.write_lot_output_frames(
        tmp_path, [full_page(first), full_page(second)]
    )
    expected = project_layout.scan_frames_dir(tmp_path, RUSH, FPS)
    assert expected.is_dir()
    assert report.output_dir == expected.relative_to(tmp_path).as_posix()


def test_a_bounded_lot_writes_into_the_bounded_directory(tmp_path: Path) -> None:
    lot_id = naming.build_lot_id(
        RUSH, FPS, source_in_timecode=IN_TC, source_out_timecode=OUT_TC
    )
    first, second = two_page_lot(lot_id=lot_id)
    sof.write_lot_output_frames(tmp_path, [full_page(first), full_page(second)])
    expected = project_layout.scan_frames_dir(
        tmp_path, RUSH, FPS, source_in_timecode=IN_TC, source_out_timecode=OUT_TC
    )
    assert expected.is_dir()
    assert len(list(expected.iterdir())) == 4


# --- AC 4: un timecode duplique n'est jamais ecrase -------------------------


def test_a_duplicated_timecode_across_pages_is_refused(tmp_path: Path) -> None:
    first = make_payload(
        page_index=0, page_count=2, first_slot=0, slot_count=2,
        timecodes=["00:00:00:00", "00:00:01:00"],
    )
    second = make_payload(
        page_index=1, page_count=2, first_slot=2, slot_count=2,
        timecodes=["00:00:01:00", "00:00:03:00"],
    )
    with pytest.raises(sof.DuplicateFrameTimecodeError) as error:
        sof.write_lot_output_frames(tmp_path, [full_page(first), full_page(second)])
    message = str(error.value)
    # Les **deux** pages en cause sont nommees.
    assert "page 0" in message and "page 1" in message
    assert "00:00:01:00" in message
    # Rien n'a ete ecrit: le refus precede la premiere ecriture.
    assert not (tmp_path / project_layout.OUTPUT_FRAMES_DIRNAME).exists()


@pytest.mark.parametrize(
    "bad_timecode",
    [
        "00;00;01;00",  # graphie drop-frame: s'assainirait en 00-00-01-00
        "00-00-01-00",  # deja la forme fichier: memes octets qu'un autre payload
        "00:00:00:120",  # cadence > 99 i/s: nom que le lecteur de l'AC 1 refuse
        "1:2:3:4",  # non complete
        "..",
    ],
)
def test_a_noncanonical_frame_timecode_is_refused_before_writing(
    tmp_path: Path, bad_timecode: str
) -> None:
    """La forme canonique 3.2 est exigee, par l'autorite du depot.

    `naming.validate_frame_timecode` existe et dit mot pour mot pourquoi -- « un
    payload QR portant la forme fichier hh-mm-ss-ff casserait le recoupement QR
    <-> nom de fichier sans aucune erreur » -- et n'etait appelee nulle part
    dans 5.6. Deux modes d'echec mesures en revue: un timecode a trois chiffres
    d'images faisait ecrire deux fichiers que le rapport declarait, dans le meme
    document, « non conformes » **et** « manquants »; et un timecode deja sous
    forme fichier produisait le **meme nom** que sa forme canonique, en
    `complete: true`.

    C'est le producteur reel des planches (`page_payload`) qui pose deja cette
    regle: 5.6 cesse simplement d'etre plus permissif que ce qui peut etre
    imprime.
    """
    payload = make_payload(
        page_index=0, page_count=1, first_slot=0, slot_count=2,
        timecodes=["00:00:00:00", bad_timecode],
    )
    with pytest.raises(sof.ScanOutputError, match="frame_timecode"):
        sof.write_lot_output_frames(tmp_path, [full_page(payload)])
    assert not (tmp_path / project_layout.OUTPUT_FRAMES_DIRNAME).exists()


def test_no_disambiguation_suffix_is_ever_invented(tmp_path: Path) -> None:
    """Le nom ecrit est **exactement** celui de la convention, sans suffixe."""
    first, second = two_page_lot()
    report = sof.write_lot_output_frames(
        tmp_path, [full_page(first), full_page(second)]
    )
    for frame in report.frames:
        assert frame.filename == naming.build_scan_frame_filename(
            RUSH, FPS, frame.frame_timecode
        )


# --- AC 5 et AC 6: 16 bits reels, BGR intact --------------------------------


def test_the_written_file_really_is_16_bit(tmp_path: Path) -> None:
    """Verification par **relecture**, jamais par la valeur de retour (piege 2)."""
    first, second = two_page_lot()
    report = sof.write_lot_output_frames(
        tmp_path, [full_page(first), full_page(second)]
    )
    for frame in report.frames:
        image = read_written(tmp_path / frame.path)
        assert image.dtype == np.uint16
        assert frame.output_bit_depth == color_pipeline.MVP_OUTPUT_BIT_DEPTH
        assert frame.output_format == color_pipeline.MVP_OUTPUT_FORMAT


def test_the_output_fields_come_from_the_export_and_not_from_a_literal() -> None:
    """Le module ne reecrit ni la profondeur ni le format a cote de l'appel.

    Defaut « manifest et artefact reel peuvent diverger », ferme en revue de
    5.5: `export_frame_tiff16` a change de type de retour pour cela.
    """
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assigned_literals = []
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg in (
            "output_bit_depth",
            "output_format",
        ):
            if isinstance(node.value, ast.Constant):
                assigned_literals.append(node.arg)
    assert assigned_literals == [], (
        f"Champs de sortie ecrits en dur: {assigned_literals}. Ils doivent venir "
        "du dict rendu par export_frame_tiff16."
    )


def test_an_8_bit_crop_is_promoted_and_its_source_depth_reported(tmp_path: Path) -> None:
    """La profondeur du **scan** remonte telle qu'elle a ete ingeree."""
    payload = make_payload(page_index=0, page_count=1, first_slot=0, slot_count=2)
    plan = crop_plan_for(payload)
    frames = tuple(
        np.full((frame.height_px, frame.width_px, 3), 200, np.uint8)
        for frame in plan.frames
    )
    report = sof.write_lot_output_frames(
        tmp_path, [sof.ScannedPage(payload=payload, crop_plan=plan, frames=frames)]
    )
    assert report.source_bit_depths == (8,)
    image = read_written(tmp_path / report.frames[0].path)
    assert image.dtype == np.uint16
    assert int(image.max()) == 200 * 257


def test_a_red_witness_comes_back_red(tmp_path: Path) -> None:
    """Temoin **asymetrique** (AC 6): un temoin neutre ne detecterait rien.

    `cv2.imwrite` interprete toujours le tableau comme du BGR: une conversion
    parasite quelque part dans la chaine ferait ressortir le rouge en bleu, et
    seule une couleur ou R et B different le montre.
    """
    payload = make_payload(page_index=0, page_count=1, first_slot=0, slot_count=2)
    plan = crop_plan_for(payload)
    frames = []
    for frame in plan.frames:
        array = np.zeros((frame.height_px, frame.width_px, 3), np.uint16)
        array[:, :, 2] = 65535  # canal R en ordre BGR
        frames.append(array)
    report = sof.write_lot_output_frames(
        tmp_path,
        [sof.ScannedPage(payload=payload, crop_plan=plan, frames=tuple(frames))],
    )
    image = read_written(tmp_path / report.frames[0].path)
    blue, green, red = image[0, 0]
    assert (int(blue), int(green), int(red)) == (0, 0, 65535)


# --- AC 7 et AC 8: cardinaux, completude, conformite ------------------------


def test_a_complete_lot_is_declared_complete(tmp_path: Path) -> None:
    first, second = two_page_lot()
    report = sof.write_lot_output_frames(
        tmp_path, [full_page(first), full_page(second)]
    )
    frames_per_page = page_templates.get_template(PORTRAIT_2F).frames_per_page
    assert report.expected_frame_count == 2 * frames_per_page
    assert report.written_frame_count == report.expected_frame_count
    assert report.synthetic_frame_count == 0
    assert report.complete is True
    assert report.warnings == ()


def test_a_missing_intermediate_page_counts_a_full_page_of_frames(tmp_path: Path) -> None:
    """Une page absente n'apporte pas ses slots: l'additionner a zero
    declarerait un lot tronque comme complet (risque R12)."""
    frames_per_page = page_templates.get_template(PORTRAIT_2F).frames_per_page
    first = make_payload(
        page_index=0, page_count=3, first_slot=0, slot_count=frames_per_page
    )
    last = make_payload(
        page_index=2, page_count=3, first_slot=2 * frames_per_page, slot_count=1
    )
    report = sof.write_lot_output_frames(tmp_path, [full_page(first), full_page(last)])
    assert report.expected_frame_count == 2 * frames_per_page + 1
    assert report.written_frame_count == frames_per_page + 1
    assert report.complete is False
    assert report.missing_pages == (1,)
    assert "PAGE_MISSING_FROM_LOT" in report.warnings


def test_a_missing_last_page_makes_the_expected_count_indeterminable(
    tmp_path: Path,
) -> None:
    """La derniere page est la seule qui peut etre partielle: sans elle, le
    total est indeterminable et le rapport le declare -- jamais devine."""
    first = make_payload(page_index=0, page_count=2, first_slot=0, slot_count=2)
    report = sof.write_lot_output_frames(tmp_path, [full_page(first)])
    assert report.expected_frame_count is None
    assert report.complete is False
    assert "EXPECTED_FRAME_COUNT_INDETERMINABLE" in report.warnings
    assert report.missing_pages == (1,)


def test_the_expected_count_comes_from_the_template_not_from_the_pages(
    tmp_path: Path,
) -> None:
    """Integration contre le registre reel: le cardinal d'une page pleine est
    `frames_per_page` du gabarit, champ de niveau lot."""
    spec = page_templates.get_template(PORTRAIT_8F_M5)
    first = make_payload(
        page_index=0, page_count=2, first_slot=0,
        slot_count=spec.frames_per_page, template_id=PORTRAIT_8F_M5,
    )
    last = make_payload(
        page_index=1, page_count=2, first_slot=spec.frames_per_page,
        slot_count=3, template_id=PORTRAIT_8F_M5,
    )
    report = sof.write_lot_output_frames(tmp_path, [full_page(first), full_page(last)])
    assert report.expected_frame_count == spec.frames_per_page + 3


def test_the_file_counter_counts_files_not_directory_entries(tmp_path: Path) -> None:
    """Un sous-dossier n'est pas une frame (defaut consigne en revue de 3.4)."""
    first, second = two_page_lot()
    report = sof.write_lot_output_frames(
        tmp_path, [full_page(first), full_page(second)]
    )
    output_dir = tmp_path / report.output_dir
    (output_dir / "un-sous-dossier").mkdir()
    verification = sof._verify_output_dir(
        output_dir, {frame.filename for frame in report.frames},
        rush_id=RUSH, fps_target=FPS,
    )
    assert verification["observed_frame_count"] == 4
    assert "un-sous-dossier" not in verification["nonconforming_files"]


def test_nonconforming_and_preexisting_files_are_named(tmp_path: Path) -> None:
    output_dir = project_layout.scan_frames_dir(tmp_path, RUSH, FPS)
    output_dir.mkdir(parents=True)
    (output_dir / "notes.txt").write_text("bruit", encoding="utf-8")
    # Une frame de ce lot acquise a une passe anterieure: son nom **se
    # reconstruit** avec le rush et la cadence du lot, elle lui appartient donc
    # -- ce n'est pas un fichier « inattendu » (renommage de la revue).
    surplus = naming.build_scan_frame_filename(RUSH, FPS, "23:59:59:00")
    (output_dir / surplus).write_bytes(b"des octets, pas un fichier vide")

    first, second = two_page_lot()
    report = sof.write_lot_output_frames(
        tmp_path, [full_page(first), full_page(second)]
    )
    assert report.nonconforming_files == ("notes.txt",)
    assert report.preexisting_frames == (surplus,)
    assert "NONCONFORMING_FILE_IN_OUTPUT_DIR" in report.warnings
    assert "PREEXISTING_FRAME_IN_OUTPUT_DIR" in report.warnings
    # Le lot reste complet -- toutes **ses** frames sont la -- mais le bruit du
    # dossier est nomme, jamais tu: l'AC 7 definit la completude par ses trois
    # cardinaux, et un fichier etranger ne retire aucune frame au lot.
    assert report.complete is True
    assert report.observed_frame_count == 5


def test_a_zero_byte_file_is_not_counted_as_an_observed_frame(tmp_path: Path) -> None:
    """Un fichier vide n'est pas une frame, meme sous un nom conforme.

    `observed_frame_count` sert precisement a mesurer une passe complementaire:
    un fichier de 0 octet -- forme la plus courante d'artefact d'une passe
    interrompue, l'ecriture n'etant pas atomique -- le faisait monter sans
    apparaitre ni dans les manquants ni dans les non conformes.
    """
    output_dir = project_layout.scan_frames_dir(tmp_path, RUSH, FPS)
    output_dir.mkdir(parents=True)
    tronquee = naming.build_scan_frame_filename(RUSH, FPS, "23:59:59:00")
    (output_dir / tronquee).write_bytes(b"")

    first, second = two_page_lot()
    report = sof.write_lot_output_frames(
        tmp_path, [full_page(first), full_page(second)]
    )
    assert report.observed_frame_count == 4
    assert tronquee in report.nonconforming_files
    assert tronquee not in report.preexisting_frames


def test_a_page_without_payload_is_a_declared_hole(tmp_path: Path) -> None:
    """QR illisible: aucune frame, ni reelle ni de remplacement (AC 13)."""
    first, second = two_page_lot()
    report = sof.write_lot_output_frames(
        tmp_path,
        [full_page(first), full_page(second), sof.ScannedPage(payload=None)],
    )
    assert report.unidentified_page_count == 1
    # Code aligne sur celui que 5.8 declare **transporter** depuis ce rapport
    # (son AC 9): deux noms auraient impose une table de traduction.
    assert "PAGE_QR_UNREADABLE" in report.warnings
    assert report.synthetic_frame_count == 0
    assert len(report.frames) == 4


def test_a_failure_reason_without_a_payload_is_refused(tmp_path: Path) -> None:
    """Sans timecode, il n'y a pas de frame a ecrire mais un trou a declarer."""
    with pytest.raises(sof.ScanOutputError, match="sans payload"):
        sof.write_lot_output_frames(
            tmp_path,
            [
                full_page(make_payload(
                    page_index=0, page_count=1, first_slot=0, slot_count=2
                )),
                sof.ScannedPage(payload=None, failure="page_detection_failed"),
            ],
        )


def test_pages_from_two_different_lots_are_refused(tmp_path: Path) -> None:
    first = make_payload(page_index=0, page_count=2, first_slot=0, slot_count=2)
    other = make_payload(
        page_index=1, page_count=2, first_slot=2, slot_count=2, rush_id="rush-002"
    )
    with pytest.raises(sof.LotInconsistencyError, match="rush_id"):
        sof.write_lot_output_frames(tmp_path, [full_page(first), full_page(other)])


# --- AC 9: politique d'ecriture ---------------------------------------------


def test_writing_over_an_existing_frame_is_refused_without_overwrite(
    tmp_path: Path,
) -> None:
    first, second = two_page_lot()
    sof.write_lot_output_frames(tmp_path, [full_page(first), full_page(second)])
    with pytest.raises(sof.OutputFrameExistsError) as error:
        sof.write_lot_output_frames(tmp_path, [full_page(first), full_page(second)])
    # Le message documente la consequence assumee d'EPIC5-ARB-18.
    assert "--overwrite" in str(error.value)


def test_nothing_is_deleted_before_writing(tmp_path: Path) -> None:
    """Contre-exemple explicite: le POC supprime les `scan_frame_*` preexistants.

    Ici les fichiers sont le livrable de l'operateur.
    """
    output_dir = project_layout.scan_frames_dir(tmp_path, RUSH, FPS)
    output_dir.mkdir(parents=True)
    precieux = output_dir / naming.build_scan_frame_filename(RUSH, FPS, "23:00:00:00")
    precieux.write_bytes(b"donnees precieuses")

    first, second = two_page_lot()
    sof.write_lot_output_frames(tmp_path, [full_page(first), full_page(second)])
    assert precieux.read_bytes() == b"donnees precieuses"


def test_a_complementary_second_pass_needs_no_flag(tmp_path: Path) -> None:
    """Seuls les fichiers **effectivement vises** declenchent le refus.

    Une seconde passe qui apporte la page manquante d'un lot deja partiellement
    ecrit ne detruit rien: lui reclamer `--overwrite` l'autoriserait du meme
    geste a ecraser les frames deja acquises (consequence nommee par
    EPIC5-ARB-18).
    """
    first, second = two_page_lot()
    sof.write_lot_output_frames(tmp_path, [full_page(first)])
    report = sof.write_lot_output_frames(tmp_path, [full_page(second)])
    assert report.overwritten_files == ()
    assert report.observed_frame_count == 4


def test_with_overwrite_only_the_rewritten_files_are_named(tmp_path: Path) -> None:
    first, second = two_page_lot()
    sof.write_lot_output_frames(tmp_path, [full_page(first)])
    report = sof.write_lot_output_frames(
        tmp_path, [full_page(first), full_page(second)], overwrite=True
    )
    rewritten = {
        naming.build_scan_frame_filename(RUSH, FPS, slot["frame_timecode"])
        for slot in first["slots"]
    }
    assert set(report.overwritten_files) == rewritten
    assert "OUTPUT_FRAME_OVERWRITTEN" in report.warnings
    assert {frame.filename for frame in report.frames if frame.overwritten} == rewritten


def test_a_synthetic_frame_follows_the_same_overwrite_policy(tmp_path: Path) -> None:
    """Aucune exception: 5.6 ne sait pas, depuis le disque, ce qui est synthetique."""
    first, second = two_page_lot()
    sof.write_lot_output_frames(
        tmp_path, [full_page(first), failed_page(second, "page_detection_failed")]
    )
    with pytest.raises(sof.OutputFrameExistsError):
        sof.write_lot_output_frames(tmp_path, [full_page(first), full_page(second)])


def test_the_report_names_the_synthetic_frames_to_target_a_second_pass(
    tmp_path: Path,
) -> None:
    first, second = two_page_lot()
    report = sof.write_lot_output_frames(
        tmp_path, [full_page(first), failed_page(second, "frame_crop_failed")]
    )
    named = {frame.filename for frame in report.synthetic_frames}
    assert named == {
        naming.build_scan_frame_filename(RUSH, FPS, slot["frame_timecode"])
        for slot in second["slots"]
    }


# --- AC 10: aucun chemin absolu ---------------------------------------------


def test_no_absolute_path_in_the_report(tmp_path: Path) -> None:
    first, second = two_page_lot()
    report = sof.write_lot_output_frames(
        tmp_path, [full_page(first), full_page(second)]
    )
    document = sof.report_document(report)
    from mixed_media_utility.io.manifest import _iter_absolute_path_violations

    assert _iter_absolute_path_violations(document) == []
    assert not report.output_dir.startswith("/")
    for frame in report.frames:
        assert not Path(frame.path).is_absolute()
        assert "\\" not in frame.path
        assert ".." not in Path(frame.path).parts
        assert (tmp_path / frame.path).is_file()


# --- AC 11: frontieres ------------------------------------------------------


def _called_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            target = node.func
            if isinstance(target, ast.Attribute):
                names.add(target.attr)
            elif isinstance(target, ast.Name):
                names.add(target.id)
    return names


@pytest.mark.parametrize(
    "forbidden",
    [
        "persist_extraction",
        "reconstruct_project_manifest",
        "compute_page_homography",
        "frame_image_rect_mm",
        "mm_to_px",
        "warp_detected_page",
        "detect_lot_pages",
        "crop_frames",
        "build_page_crop_plan",
    ],
)
def test_the_module_never_crosses_its_boundaries(forbidden: str) -> None:
    """La story ne detecte pas, ne decoupe pas, n'ecrit pas le manifest.

    La conversion millimetres -> pixels appartient a 5.2 et 5.3: la faire ici
    reintroduirait une seconde geometrie, silencieusement divergente.
    """
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    assert forbidden not in _called_names(tree)


def test_the_module_writes_no_manifest(tmp_path: Path) -> None:
    first, second = two_page_lot()
    sof.write_lot_output_frames(tmp_path, [full_page(first), full_page(second)])
    assert not (tmp_path / "project.json").exists()


def test_the_gamut_map_id_is_transported_verbatim(tmp_path: Path) -> None:
    """Transport **inconditionnel**: aucun `if`, aucun defaut, aucun `null`."""
    first, second = two_page_lot()
    report = sof.write_lot_output_frames(
        tmp_path, [full_page(first), full_page(second)]
    )
    assert report.gamut_map_id == first["gamut_map_id"]
    assert sof.report_document(report)["gamut_map_id"] == payload_io.GAMUT_MAP_IDENTITY


def test_a_payload_without_gamut_map_id_is_refused_upstream(tmp_path: Path) -> None:
    """La branche « champ absent » n'existe plus (EPIC5-ARB-13): le refus vient
    de `io.payload`, il n'est pas rattrape ici."""
    payload = make_payload(page_index=0, page_count=1, first_slot=0, slot_count=2)
    plan = crop_plan_for(payload)
    frames = crops_for(plan)
    del payload["gamut_map_id"]
    with pytest.raises(payload_io.PayloadValidationError, match="gamut_map_id"):
        sof.write_lot_output_frames(
            tmp_path, [sof.ScannedPage(payload=payload, crop_plan=plan, frames=frames)]
        )


def test_the_calibration_status_is_transported_not_computed(tmp_path: Path) -> None:
    first, second = two_page_lot()
    report = sof.write_lot_output_frames(
        tmp_path, [full_page(first), full_page(second)]
    )
    assert report.color_calibration_status == color_pipeline.NOT_APPLIED_STATUS
    with pytest.raises(ValueError):
        sof.write_lot_output_frames(
            tmp_path, [full_page(first)], color_calibration_status="peut-etre"
        )


# --- AC 13: la frame de remplacement ----------------------------------------


def smallest_zone_shape(template_id: str, *, dpi: int = DPI) -> tuple[int, int]:
    """Dimensions de la plus petite zone d'un gabarit, via le vrai plan 5.3."""
    spec = page_templates.get_template(template_id)
    payload = make_payload(
        page_index=0, page_count=1, first_slot=0,
        slot_count=spec.frames_per_page, template_id=template_id,
    )
    plan = crop_plan_for(payload, dpi=dpi)
    frame = min(plan.frames, key=lambda item: item.width_px * item.height_px)
    return frame.height_px, frame.width_px


def test_a_synthetic_frame_has_the_shape_and_depth_of_the_real_ones(
    tmp_path: Path,
) -> None:
    """Verifie **par relecture**: l'`encode` suppose une sequence homogene."""
    first, second = two_page_lot()
    report = sof.write_lot_output_frames(
        tmp_path, [full_page(first), failed_page(second, "page_detection_failed")]
    )
    shapes = {read_written(tmp_path / frame.path).shape for frame in report.frames}
    dtypes = {read_written(tmp_path / frame.path).dtype for frame in report.frames}
    assert len(shapes) == 1
    assert dtypes == {np.dtype(np.uint16)}


def test_a_synthetic_frame_reports_16_bit_source_depth(tmp_path: Path) -> None:
    """Piege 9: une mire en `uint8` ferait declarer un scan 8 bits qui n'existe pas.

    Et la profondeur du **scan** ne se mesure que sur les pages ingerees: une
    frame generee n'entre dans aucune statistique de profondeur.
    """
    first, second = two_page_lot()
    report = sof.write_lot_output_frames(
        tmp_path, [full_page(first), failed_page(second, "page_detection_failed")]
    )
    for frame in report.synthetic_frames:
        assert frame.source_bit_depth == 16
    assert report.source_bit_depths == (16,)


def test_the_synthetic_frame_is_neither_uniform_nor_black(tmp_path: Path) -> None:
    """Le test qui distingue la voie retenue d'EPIC5-ARB-8 de l'option (b).

    Une frame noire silencieuse serait indistinguable d'une vraie image noire du
    film: la mire porte deux niveaux tres separes, sur les trois canaux.
    """
    first, second = two_page_lot()
    report = sof.write_lot_output_frames(
        tmp_path, [full_page(first), failed_page(second, "page_detection_failed")]
    )
    for frame in report.synthetic_frames:
        image = read_written(tmp_path / frame.path)
        assert int(image.min()) == 0
        assert int(image.max()) == sof.MAX_LEVEL_16BIT
        # Achromatique: aucune ambiguite d'ordre de canaux possible (AC 6).
        assert np.array_equal(image[:, :, 0], image[:, :, 2])


def test_the_synthetic_frame_is_deterministic_for_the_same_second_line() -> None:
    shape = (166, 295, 3)
    left = sof.build_missing_frame_image(
        shape=shape, page_index=11, page_count=40, frame_timecode="00:00:12:14"
    )
    right = sof.build_missing_frame_image(
        shape=shape, page_index=11, page_count=40, frame_timecode="00:00:12:14"
    )
    assert left.tobytes() == right.tobytes()


@pytest.mark.parametrize(
    "page_index, page_count, frame_timecode",
    [
        (12, 40, "00:00:12:14"),
        (11, 41, "00:00:12:14"),
        (11, 40, "00:00:12:15"),
    ],
)
def test_a_different_second_line_gives_different_bytes(
    page_index, page_count, frame_timecode
) -> None:
    """Sans quoi la seconde ligne n'est pas tracee (EPIC5-ARB-19)."""
    shape = (166, 295, 3)
    reference = sof.build_missing_frame_image(
        shape=shape, page_index=11, page_count=40, frame_timecode="00:00:12:14"
    )
    other = sof.build_missing_frame_image(
        shape=shape, page_index=page_index, page_count=page_count,
        frame_timecode=frame_timecode,
    )
    assert reference.tobytes() != other.tobytes()


def test_the_second_line_shows_the_printed_page_rank_and_the_payload_timecode() -> None:
    """Rang a partir de 1 (piege 12), timecode verbatim avec ses `:`, tiret ASCII."""
    line = sof.missing_frame_second_line(
        page_index=11, page_count=40, frame_timecode="00:00:12:14"
    )
    assert line == "page 12/40 - 00:00:12:14"
    assert "00:00:12:14" in line
    assert "00-00-12-14" not in line
    assert line.isascii()
    assert "—" not in line and "–" not in line


def test_the_second_line_matches_the_printed_sheet_convention() -> None:
    """Meme convention que le bloc d'identite de la planche (`page n/total`)."""
    page_index, page_count = 1, 3
    assert sof.missing_frame_second_line(
        page_index=page_index, page_count=page_count, frame_timecode="00:00:00:00"
    ).startswith(f"page {page_index + 1}/{page_count}")


def test_the_missing_frame_text_is_ascii() -> None:
    """Piege 8: `FONT_HERSHEY_SIMPLEX` ne rend pas les caracteres accentues."""
    assert sof.MISSING_FRAME_TEXT.isascii()
    assert sof.MISSING_FRAME_TEXT == "FRAME MANQUANTE"


@pytest.mark.parametrize("dpi", [600, 300, 150, 100])
@pytest.mark.parametrize("template_id", [PORTRAIT_8F_M5, PAYSAGE_8F_M5])
def test_both_lines_fit_on_the_smallest_zone_of_the_vocabulary(template_id, dpi) -> None:
    """Non-regression sur les epaisseurs derivees de l'echelle (AC 12).

    La plus petite zone du vocabulaire, dans les **deux** orientations: les deux
    lignes tiennent en largeur mesuree par `cv2.getTextSize`, et le remplissage
    reste trace sur au moins un pixel -- ce que la recette d'origine, reprise
    avec ses constantes, ne garantit pas.

    **Parametre par la resolution**, pas seulement par le gabarit (revue du
    2026-08-08): la version figee a 300 ppp ne franchissait jamais le seuil sous
    lequel la plume de contour tombe a 1. En dessous de ce seuil -- atteint des
    100 ppp sur la plus petite zone, et `scan_ingest.validate_scan_dpi` n'impose
    qu'un plancher de 1 -- aucun ecart de plume n'est plus possible: le
    remplissage blanc recouvrait exactement le contour noir et la mire devenait
    du texte blanc sur des cellules blanches, c'est-a-dire invisible la ou elle
    doit se voir. Seule la couronne peut encore rendre le lisere; ce test est ce
    qui l'exige. Mesure avant correction a 100 ppp: **0 pixel** de lisere.
    """
    height, width = smallest_zone_shape(template_id, dpi=dpi)
    lines = (
        sof.MISSING_FRAME_TEXT,
        sof.missing_frame_second_line(
            page_index=11, page_count=40, frame_timecode="00:00:12:14"
        ),
    )
    scale = sof.derive_text_scale(lines, height, width)
    for line in lines:
        (measured_width, _height), _baseline = cv2.getTextSize(
            line, cv2.FONT_HERSHEY_SIMPLEX, scale, 1
        )
        assert measured_width <= width, f"{line!r} deborde de la zone {width}x{height}"

    image = sof.build_missing_frame_image(
        shape=(height, width), page_index=11, page_count=40,
        frame_timecode="00:00:12:14",
    )
    board = (
        sof.build_checkerboard(height, width, sof.derive_checker_cell_px(height))
        .astype(np.uint16)
        * sof.BIT_DEPTH_PROMOTION_FACTOR
    )
    painted = image != board
    assert painted.any(), "aucun texte n'a ete trace"
    # Aucune troncature: le texte peint reste strictement dans la frame.
    columns = np.where(painted.any(axis=0))[0]
    assert columns.min() >= 0 and columns.max() < width
    # Le remplissage blanc est visible **sur une cellule noire**, et le contour
    # noir **sur une cellule blanche**: c'est cela, « lisible sur n'importe
    # quel fond ».
    assert int(((board == 0) & (image == sof.MAX_LEVEL_16BIT)).sum()) >= 1
    assert int(((board == sof.MAX_LEVEL_16BIT) & (image == 0)).sum()) >= 1


@pytest.mark.parametrize("template_id", [PORTRAIT_8F_M5, PAYSAGE_8F_M5])
def test_the_derived_thicknesses_never_fall_below_one_pixel(template_id) -> None:
    height, width = smallest_zone_shape(template_id)
    lines = (
        sof.MISSING_FRAME_TEXT,
        sof.missing_frame_second_line(
            page_index=11, page_count=40, frame_timecode="00:00:12:14"
        ),
    )
    scale = sof.derive_text_scale(lines, height, width)
    outline, fill = sof.derive_text_thicknesses(scale)
    assert outline >= 1 and fill >= 1
    # Le rapport de la recette de reference est conserve dans la derivation.
    assert outline == max(1, round(4 * scale / 0.7))
    assert fill == max(1, round(1 * scale / 0.7))


def test_the_reference_scale_reproduces_the_reference_thicknesses() -> None:
    """A l'echelle d'origine, la derivation rend exactement 4 et 1."""
    assert sof.derive_text_thicknesses(0.7) == (4, 1)


def test_the_checker_cell_scales_with_the_frame_height() -> None:
    """Jamais une constante en pixels: un damier trop fin moire a l'encodage."""
    small = sof.derive_checker_cell_px(smallest_zone_shape(PAYSAGE_8F_M5)[0])
    large = sof.derive_checker_cell_px(3000)
    assert small >= sof.MIN_CHECKER_CELL_PX
    assert large > small


def test_a_synthetic_frame_takes_its_shape_from_the_crop_plan(tmp_path: Path) -> None:
    """Aucune frame reelle dans le lot: la forme vient du plan de 5.3."""
    first = make_payload(page_index=0, page_count=1, first_slot=0, slot_count=2)
    plan = crop_plan_for(first)
    report = sof.write_lot_output_frames(
        tmp_path,
        [sof.ScannedPage(payload=first, crop_plan=plan, failure="frame_crop_failed")],
    )
    assert report.synthetic_frame_count == 2
    for frame, planned in zip(report.frames, plan.frames):
        image = read_written(tmp_path / frame.path)
        assert image.shape == (
            planned.height_px, planned.width_px, sof.DEFAULT_SYNTHETIC_CHANNELS,
        )


def test_without_a_plan_a_synthetic_frame_takes_the_observed_shape(
    tmp_path: Path,
) -> None:
    first, second = two_page_lot()
    report = sof.write_lot_output_frames(
        tmp_path,
        [
            full_page(first),
            sof.ScannedPage(payload=second, failure="page_detection_failed"),
        ],
    )
    shapes = {read_written(tmp_path / frame.path).shape for frame in report.frames}
    assert len(shapes) == 1


def test_without_plan_nor_real_frame_the_shape_is_indeterminable(
    tmp_path: Path,
) -> None:
    """Rien n'est ecrit et le rapport le declare: on ne choisit pas une taille
    par defaut (meme doctrine que le cardinal indeterminable)."""
    payload = make_payload(page_index=0, page_count=1, first_slot=0, slot_count=2)
    report = sof.write_lot_output_frames(
        tmp_path, [sof.ScannedPage(payload=payload, failure="page_detection_failed")]
    )
    assert report.written_frame_count == 0
    assert report.frames == ()
    assert report.shape_indeterminable_pages == (0,)
    assert "SYNTHETIC_FRAME_SHAPE_INDETERMINABLE" in report.warnings
    assert report.complete is False


def test_a_plan_that_contradicts_the_real_frames_is_a_named_failure(
    tmp_path: Path,
) -> None:
    """Une sequence heterogene est deja un echec d'encodage: pas d'arbitrage
    a la volee entre deux formes."""
    first, second = two_page_lot()
    plan = crop_plan_for(first)
    mismatched = tuple(
        np.zeros((frame.height_px - 5, frame.width_px, 3), np.uint16)
        for frame in plan.frames
    )
    with pytest.raises(sof.FrameShapeConflictError, match="arbitrage a la volee"):
        sof.write_lot_output_frames(
            tmp_path,
            [
                sof.ScannedPage(payload=first, crop_plan=plan, frames=mismatched),
                failed_page(second, "page_detection_failed"),
            ],
        )
    assert not (tmp_path / project_layout.OUTPUT_FRAMES_DIRNAME).exists()


def test_two_divergent_observed_shapes_are_a_named_failure(tmp_path: Path) -> None:
    """Deux pages reelles de formes differentes, plus une mire a poser."""
    first = make_payload(page_index=0, page_count=3, first_slot=0, slot_count=2)
    second = make_payload(page_index=1, page_count=3, first_slot=2, slot_count=2)
    third = make_payload(page_index=2, page_count=3, first_slot=4, slot_count=2)
    other_plan = crop_plan_for(second)
    shrunk = tuple(
        np.zeros((frame.height_px - 7, frame.width_px - 7, 3), np.uint16)
        for frame in other_plan.frames
    )
    with pytest.raises(sof.FrameShapeConflictError, match="divergentes"):
        sof.write_lot_output_frames(
            tmp_path,
            [
                full_page(first),
                sof.ScannedPage(payload=second, frames=shrunk),
                sof.ScannedPage(payload=third, failure="page_detection_failed"),
            ],
        )
    assert not (tmp_path / project_layout.OUTPUT_FRAMES_DIRNAME).exists()


def test_divergent_shapes_without_any_mire_are_written_and_warned(
    tmp_path: Path,
) -> None:
    """Sans mire a poser, il n'y a rien a arbitrer: on ecrit ce qu'on a (AC 8)
    et on signale l'heterogeneite plutot que de refuser le lot en bloc."""
    first, second = two_page_lot()
    other_plan = crop_plan_for(second)
    shrunk = tuple(
        np.zeros((frame.height_px - 7, frame.width_px, 3), np.uint16)
        for frame in other_plan.frames
    )
    report = sof.write_lot_output_frames(
        tmp_path,
        [full_page(first), sof.ScannedPage(payload=second, frames=shrunk)],
    )
    assert "HETEROGENEOUS_FRAME_SHAPES" in report.warnings
    assert report.written_frame_count == 4
    # ... et le lot n'est **pas** complet: le module pose lui-meme l'equivalence
    # « forme divergente = trou » (`FrameShapeConflictError`), il ne l'appliquait
    # que quand une mire devait etre posee. Sans mire a poser, un lot que
    # l'`encode` de l'Epic 6 ne peut pas assembler sortait `complete: true` --
    # le seul faux pas que la story s'interdit (R12).
    assert report.complete is False
    # Les deux formes sont bien sur le disque: le lot est ecrit, pas refuse.
    assert len({read_written(tmp_path / f.path).shape for f in report.frames}) == 2


def test_an_absent_page_gets_no_replacement_frame(tmp_path: Path) -> None:
    """La continuite de sequence n'est retablie que sur les pages arrivees:
    inventer un timecode serait deviner (piege 10)."""
    first, _second = two_page_lot()
    report = sof.write_lot_output_frames(tmp_path, [full_page(first)])
    assert report.synthetic_frame_count == 0
    assert report.missing_pages == (1,)
    assert len(list((tmp_path / report.output_dir).iterdir())) == 2


# --- AC 14: le marquage synthetique -----------------------------------------


def test_synthetic_is_present_on_every_entry_including_false(tmp_path: Path) -> None:
    """Un champ absent se relit « vraie frame »: c'est le faux positif
    silencieux qu'EPIC5-ARB-8 ecarte."""
    first, second = two_page_lot()
    report = sof.write_lot_output_frames(
        tmp_path, [full_page(first), failed_page(second, "page_detection_failed")]
    )
    document = sof.report_document(report)
    assert len(document["frames"]) == 4
    for entry in document["frames"]:
        assert "synthetic" in entry
        assert isinstance(entry["synthetic"], bool)
    assert [entry["synthetic"] for entry in document["frames"]] == [
        False, False, True, True,
    ]


def test_synthetic_reason_is_present_if_and_only_if_synthetic(tmp_path: Path) -> None:
    first, second = two_page_lot()
    report = sof.write_lot_output_frames(
        tmp_path, [full_page(first), failed_page(second, "frame_crop_failed")]
    )
    for entry in sof.report_document(report)["frames"]:
        if entry["synthetic"]:
            assert entry["synthetic_reason"] == "frame_crop_failed"
            assert entry["synthetic_reason"] in sof.SYNTHETIC_FRAME_REASONS
        else:
            assert "synthetic_reason" not in entry


def test_the_synthetic_reason_vocabulary_is_closed() -> None:
    assert sof.SYNTHETIC_FRAME_REASONS == (
        "page_detection_failed",
        "frame_crop_failed",
    )
    for reason in sof.SYNTHETIC_FRAME_REASONS:
        assert sof.validate_synthetic_reason(reason) == reason
    with pytest.raises(ValueError):
        sof.validate_synthetic_reason("page_un_peu_ratee")


def test_an_unknown_failure_reason_is_refused(tmp_path: Path) -> None:
    payload = make_payload(page_index=0, page_count=1, first_slot=0, slot_count=2)
    with pytest.raises(ValueError, match="Motif de frame synthetique inconnu"):
        sof.write_lot_output_frames(
            tmp_path,
            [sof.ScannedPage(payload=payload, crop_plan=crop_plan_for(payload),
                             failure="scanner_casse")],
        )


def test_the_two_reasons_are_distinguishable_at_this_level(tmp_path: Path) -> None:
    """5.2 (geometrie non resolue) et 5.3 (zone degeneree) ne se confondent pas."""
    first, second = two_page_lot()
    report = sof.write_lot_output_frames(
        tmp_path,
        [
            failed_page(first, "page_detection_failed"),
            failed_page(second, "frame_crop_failed"),
        ],
    )
    reasons = {frame.page_index: frame.synthetic_reason for frame in report.frames}
    assert reasons == {0: "page_detection_failed", 1: "frame_crop_failed"}


def test_a_lot_carrying_a_synthetic_frame_is_never_complete(tmp_path: Path) -> None:
    """Meme a `ecrit == attendu`: le fichier existe, l'image du film non."""
    first, second = two_page_lot()
    report = sof.write_lot_output_frames(
        tmp_path, [full_page(first), failed_page(second, "page_detection_failed")]
    )
    assert report.written_frame_count == report.expected_frame_count
    assert report.synthetic_frame_count == 2
    assert report.complete is False
    assert "SYNTHETIC_FRAME_WRITTEN" in report.warnings


def test_the_lot_carries_the_synthetic_count_next_to_the_cardinals(
    tmp_path: Path,
) -> None:
    first, second = two_page_lot()
    report = sof.write_lot_output_frames(
        tmp_path, [full_page(first), failed_page(second, "page_detection_failed")]
    )
    document = sof.report_document(report)
    for field in (
        "expected_frame_count",
        "written_frame_count",
        "synthetic_frame_count",
    ):
        assert field in document
    assert document["synthetic_frame_count"] == 2


def test_the_warning_vocabulary_is_closed() -> None:
    assert "SYNTHETIC_FRAME_WRITTEN" in sof.SCAN_OUTPUT_WARNING_CODES
    for code in sof.SCAN_OUTPUT_WARNING_CODES:
        assert sof.validate_warning_code(code) == code
    with pytest.raises(ValueError):
        sof.validate_warning_code("PRESQUE_BON")


# --- le rapport lui-meme ----------------------------------------------------


def test_the_report_is_canonically_serialisable(tmp_path: Path) -> None:
    first, second = two_page_lot()
    report = sof.write_lot_output_frames(
        tmp_path, [full_page(first), full_page(second)]
    )
    text = sof.report_json(report)
    assert text == sof.report_json(report)
    assert sof.FINGERPRINT_PREFIX in text


def test_two_identical_passes_report_the_same_fingerprint(tmp_path: Path) -> None:
    first, second = two_page_lot()
    left = sof.report_document(
        sof.write_lot_output_frames(tmp_path, [full_page(first), full_page(second)])
    )
    other = tmp_path / "second-projet"
    right = sof.report_document(
        sof.write_lot_output_frames(other, [full_page(first), full_page(second)])
    )
    assert left["fingerprint"] == right["fingerprint"]


# --- gardes d'entree ---------------------------------------------------------


def test_an_empty_lot_is_refused(tmp_path: Path) -> None:
    with pytest.raises(sof.ScanOutputError):
        sof.write_lot_output_frames(tmp_path, [])


def test_a_lot_of_pages_without_any_payload_is_refused(tmp_path: Path) -> None:
    with pytest.raises(sof.LotInconsistencyError, match="Aucune page"):
        sof.write_lot_output_frames(tmp_path, [sof.ScannedPage(payload=None)])


def test_a_page_with_neither_frames_nor_failure_is_refused(tmp_path: Path) -> None:
    payload = make_payload(page_index=0, page_count=1, first_slot=0, slot_count=2)
    with pytest.raises(sof.ScanOutputError, match="aucun motif d'echec"):
        sof.write_lot_output_frames(tmp_path, [sof.ScannedPage(payload=payload)])


def test_a_frame_count_that_does_not_match_the_slots_is_refused(tmp_path: Path) -> None:
    """L'appariement slot <-> frame est positionnel: un decalage graverait le
    timecode d'une frame dans le nom d'une autre."""
    payload = make_payload(page_index=0, page_count=1, first_slot=0, slot_count=2)
    plan = crop_plan_for(payload)
    with pytest.raises(sof.ScanOutputError, match="slots declares"):
        sof.write_lot_output_frames(
            tmp_path,
            [sof.ScannedPage(payload=payload, crop_plan=plan,
                             frames=crops_for(plan)[:1])],
        )


@pytest.mark.parametrize("overwrite", [1, 0, "oui", None])
def test_overwrite_must_be_a_real_boolean(tmp_path: Path, overwrite) -> None:
    """Garde `bool`-avant-`int` (action item 2 de la retro Epic 4)."""
    payload = make_payload(page_index=0, page_count=1, first_slot=0, slot_count=2)
    with pytest.raises(sof.ScanOutputError, match="booleen"):
        sof.write_lot_output_frames(
            tmp_path, [full_page(payload)], overwrite=overwrite
        )


@pytest.mark.parametrize(
    "shape",
    [(10,), (10, 10, 2), (10, 10, 5), (True, 10, 3), (0, 10, 3), (10, 0, 3)],
)
def test_a_degenerate_shape_is_refused_for_the_mire(shape) -> None:
    with pytest.raises(sof.ScanOutputError):
        sof.build_missing_frame_image(
            shape=shape, page_index=0, page_count=1, frame_timecode="00:00:00:00"
        )


def test_the_module_uses_the_shared_numeric_guard() -> None:
    """Le helper partage existe depuis la story 5.9: aucune seconde garde
    `bool`-avant-`int` n'est ecrite ici."""
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "from .numeric_guards import" in source
    assert "isinstance(value, int) and not isinstance(value, bool)" not in source


# ============================================================================
# Passe de correction apres la revue en trois couches (2026-08-08)
#
# Chaque test de cette section ferme un defaut nomme par la revue ou un mutant
# survivant de la campagne. Le survivant ou le finding est cite: un test qui ne
# dit pas ce qu'il empeche redevient decoratif a la premiere refonte.
# ============================================================================


# --- l'appariement slot <-> frame (survivant M33) ---------------------------


def test_each_slot_is_written_from_its_own_frame(tmp_path: Path) -> None:
    """Le contenu ecrit sous un timecode est celui de **son** slot.

    Mutant M33 (`page.frames[len(slots) - 1 - position]`): il inversait
    l'appariement positionnel et laissait les 165 tests du lot cible verts,
    parce que toutes les fabriques remplissaient les frames d'une page d'une
    valeur uniforme. Le nom de fichier etant le seul support d'identite d'une
    frame qui voyage seule, la video reconstruite serait dans le desordre et
    rien dans le rapport ne le dirait.
    """
    first, second = two_page_lot()
    report = sof.write_lot_output_frames(
        tmp_path, [full_page(first), full_page(second)]
    )
    attendu = {
        slot["frame_timecode"]: slot_witness(slot["slot_index"])
        for payload in (first, second)
        for slot in payload["slots"]
    }
    assert len(set(attendu.values())) == len(attendu), "temoins non distinguables"
    for frame in report.frames:
        image = read_written(tmp_path / frame.path)
        assert int(image.min()) == int(image.max()) == attendu[frame.frame_timecode], (
            f"{frame.filename} porte le contenu d'un autre slot: l'appariement "
            "slot <-> frame est decale."
        )


# --- le rang de page a l'echelle du lot (couche 2, bloquante 1) -------------


def test_two_pages_with_the_same_page_index_are_refused(tmp_path: Path) -> None:
    """Deux tirages du meme rush melanges: `lot_id` ne les distingue pas.

    `build_lot_id` ne depend ni de la selection ni des timecodes: deux tirages
    successifs du meme rush a la meme cadence portent le meme `lot_id`, le meme
    `page_count` et le meme `template_id`. Mesure en revue: le lot sortait
    `complete: true`, sans un seul avertissement, sur une sequence dont une page
    entiere n'avait jamais ete scannee.
    """
    first = make_payload(page_index=0, page_count=2, first_slot=0, slot_count=2)
    doublon = make_payload(
        page_index=0, page_count=2, first_slot=2, slot_count=2,
    )
    with pytest.raises(sof.LotInconsistencyError, match="meme page_index"):
        sof.write_lot_output_frames(tmp_path, [full_page(first), full_page(doublon)])
    assert not (tmp_path / project_layout.OUTPUT_FRAMES_DIRNAME).exists()


def test_a_lot_that_names_a_missing_page_is_never_complete(tmp_path: Path) -> None:
    """Un rapport ne se contredit pas dans le meme document.

    `missing_pages` nommait la page 0 pendant que `complete` disait vrai: le
    cardinal ecrit egalait le cardinal attendu parce qu'une autre page etait
    presente en double. La condition est desormais structurelle.
    """
    first = make_payload(page_index=1, page_count=2, first_slot=2, slot_count=2)
    report = sof.write_lot_output_frames(tmp_path, [full_page(first)])
    assert report.missing_pages == (0,)
    assert report.complete is False


def test_a_report_that_names_a_missing_page_can_never_say_complete(
    tmp_path: Path, monkeypatch
) -> None:
    """La condition est la derniere ligne, et elle est exercee comme telle.

    Depuis que le rang de page est unique a l'echelle du lot et qu'une page ne
    peut plus porter plus de slots que son gabarit, le cardinal ecrit ne **peut**
    plus egaler le cardinal attendu quand une page manque: `not missing_pages`
    est donc une defense en profondeur, et une defense en profondeur non
    exercee est du code qu'une refonte supprime sans que rien ne sonne. On
    force la coincidence des deux cardinaux pour reproduire exactement l'etat
    que la condition surveille -- celui ou le rapport nommait la page 0 dans
    `missing_pages` en disant `complete: true` dans le meme document.
    """
    first = make_payload(page_index=1, page_count=2, first_slot=2, slot_count=2)
    monkeypatch.setattr(
        sof,
        "_expected_frame_count",
        lambda pages, *, template_id, page_count: 2,
    )
    report = sof.write_lot_output_frames(tmp_path, [full_page(first)])
    assert report.written_frame_count == report.expected_frame_count == 2
    assert report.synthetic_frame_count == 0
    assert report.missing_pages == (0,)
    assert report.complete is False


# --- le lot_id devenu composant de chemin (couche 1 F2/F3, couche 2 M3) -----


@pytest.mark.parametrize(
    "hostile",
    ["../../evade", "sous/dossier", "lot avec espaces", "/tmp/PWNED", "..", "a\\b"],
)
def test_a_lot_id_outside_the_canonical_pattern_is_refused(hostile: str) -> None:
    """Le `lot_id` vient d'un QR imprime sur du papier: il est valide.

    `naming.validate_manifest_identifier` est l'implementation unique de la
    regle « identifiant canonique » du depot et n'etait appelee nulle part ici.
    Mesure en revue: `../../evade` faisait ecrire un TIFF 16 bits **hors du
    dossier projet** avant que le filet de publication ne se tende, et
    `sous/dossier` passait en silence sous une arborescence ou l'`encode` ne
    cherche jamais.

    Le **motif** du refus est verifie, pas seulement son type: la garde de
    forme du lot borne refuserait aussi ces valeurs, avec un tout autre
    diagnostic, et un test qui se contente d'attraper `ScanOutputError`
    laisserait la validation d'identifiant disparaitre sans que rien ne sonne.
    """
    with pytest.raises(sof.ScanOutputError, match="composant de chemin"):
        sof.derive_lot_dir_slug(rush_id=RUSH, fps_target=FPS, lot_id=hostile)


def test_a_hostile_lot_id_writes_nothing_at_all(tmp_path: Path) -> None:
    """Bout en bout: pas un octet, ni dans le projet ni ailleurs."""
    payload = make_payload(page_index=0, page_count=1, first_slot=0, slot_count=2)
    payload["lot_id"] = "../../evade"
    plan = crop_plan_for(payload)
    with pytest.raises(sof.ScanOutputError):
        sof.write_lot_output_frames(
            tmp_path,
            [sof.ScannedPage(payload=payload, crop_plan=plan, frames=crops_for(plan))],
        )
    assert not (tmp_path / project_layout.OUTPUT_FRAMES_DIRNAME).exists()
    assert not (tmp_path.parent / "evade").exists()


def test_a_bounded_lot_id_must_carry_the_rush_and_the_fps_of_the_payload() -> None:
    """La branche « lot borne » recoupe le payload au lieu de le supposer.

    Mesure en revue: un `lot_id` bati a 5 fps dans un payload declarant 24 fps
    etait declare « borne » et servait de nom de dossier verbatim -- des frames
    nommees a 24 fps atterrissaient dans le dossier du lot 5 fps du meme rush,
    `complete: true`, zero avertissement. C'est le scenario que
    `LotInconsistencyError` decrit mot pour mot.
    """
    lot_a_5_fps = naming.build_lot_id(RUSH, 5)
    with pytest.raises(sof.LotInconsistencyError, match="ne porte ni le rush"):
        sof.derive_lot_dir_slug(rush_id=RUSH, fps_target=24.0, lot_id=lot_a_5_fps)
    # Un lot borne conforme, lui, passe: la garde verifie la forme, elle ne
    # l'interdit pas.
    borne = naming.build_lot_id(
        RUSH, 24.0, source_in_timecode=IN_TC, source_out_timecode=OUT_TC
    )
    assert sof.derive_lot_dir_slug(rush_id=RUSH, fps_target=24.0, lot_id=borne) == borne


def test_a_lot_id_of_another_rush_is_refused(tmp_path: Path) -> None:
    """Meme garde, bout en bout: rien n'est ecrit."""
    payload = make_payload(page_index=0, page_count=1, first_slot=0, slot_count=2)
    payload["lot_id"] = naming.build_lot_id("rush-002", FPS)
    plan = crop_plan_for(payload)
    with pytest.raises(sof.LotInconsistencyError):
        sof.write_lot_output_frames(
            tmp_path,
            [sof.ScannedPage(payload=payload, crop_plan=plan, frames=crops_for(plan))],
        )
    assert not (tmp_path / project_layout.OUTPUT_FRAMES_DIRNAME).exists()


@pytest.mark.parametrize(
    "slug", ["", None, ".", "..", "a/b", "../x", "/tmp/x", "C:\\x", "a\\b"]
)
def test_the_output_slug_must_be_a_single_relative_component(tmp_path: Path, slug) -> None:
    """Derniere garde avant la concatenation (survivant M11).

    `output_frames_dir_from_slug` est la seule fonction publique ajoutee a
    `io/project_layout.py` par la story et n'avait aucun test propre: neutraliser
    sa garde ne faisait rien tomber. Or `Path(projet) / "output-frames" /
    "/tmp/x"` vaut `/tmp/x`.
    """
    with pytest.raises(ValueError):
        project_layout.scan_frames_dir_from_slug(tmp_path, slug)


def test_a_legitimate_long_slug_is_still_accepted(tmp_path: Path) -> None:
    """La garde porte sur la **forme**, pas sur la longueur.

    Un `rush_id` de plus de 48 caracteres donne un slug de dossier plus long que
    l'identifiant canonique: c'est le comportement herite de `frames/` que
    l'AC 1 demande de reproduire tel quel.
    """
    long_rush = "B" * (naming.CANONICAL_ID_MAX_LENGTH + 5)
    slug = project_layout.rush_dir_slug(long_rush, FPS)
    assert project_layout.scan_frames_dir_from_slug(tmp_path, slug).name == slug


# --- tout ce qui peut echouer, avant le premier octet (couche 1 F4) ---------


def test_an_unknown_template_is_refused_before_the_first_byte(tmp_path: Path) -> None:
    """Le gabarit se **resout** avant l'ecriture, pas au calcul du cardinal.

    Mesure en revue: une planche portant un `template_id` retire du vocabulaire
    ecrivait ses six frames puis levait une `UnknownTemplateError` venue d'un
    troisieme module, sans rapport -- dossier entierement rempli mais orphelin,
    relance bloquee sans `--overwrite`.
    """
    payload = make_payload(page_index=0, page_count=1, first_slot=0, slot_count=2)
    plan = crop_plan_for(payload)
    frames = crops_for(plan)
    payload["template_id"] = "tpl-a4-portrait-2f-v0-retire"
    with pytest.raises(sof.ScanOutputError, match="Template inconnu"):
        sof.write_lot_output_frames(
            tmp_path, [sof.ScannedPage(payload=payload, crop_plan=plan, frames=frames)]
        )
    assert not (tmp_path / project_layout.OUTPUT_FRAMES_DIRNAME).exists()


@pytest.mark.parametrize(
    "fabrique",
    [
        lambda shape: np.zeros(shape, np.float32),
        lambda shape: np.zeros(shape, np.int16),
        lambda shape: np.zeros((0, 0, 3), np.uint16),
        lambda shape: np.zeros(shape[:2] + (5,), np.uint16),
        lambda shape: None,
    ],
    ids=["float32", "int16", "vide", "5-canaux", "None"],
)
def test_a_frame_the_export_refuses_is_refused_before_the_first_byte(
    tmp_path: Path, fabrique
) -> None:
    """La garde d'export est appelee **en planification**.

    Mesure en revue: sur un lot de 3 pages x 2 slots dont la sixieme frame est
    en defaut, **cinq** fichiers restaient sur le disque, l'exception
    n'appartenait pas a la hierarchie du module, et la relance corrigee se
    heurtait a `OutputFrameExistsError` -- la seule issue restante etant
    `--overwrite`, qui autorise du meme geste a ecraser les frames deja
    acquises.
    """
    first, second = two_page_lot()
    plan = crop_plan_for(second)
    frames = list(crops_for(plan))
    frames[-1] = fabrique(frames[-1].shape)
    with pytest.raises(sof.ScanOutputError, match="pas exportable"):
        sof.write_lot_output_frames(
            tmp_path,
            [
                full_page(first),
                sof.ScannedPage(payload=second, crop_plan=plan, frames=tuple(frames)),
            ],
        )
    assert not (tmp_path / project_layout.OUTPUT_FRAMES_DIRNAME).exists()


# --- la structure de page confrontee au gabarit (couche 2, moyenne 5) -------


def test_a_page_carrying_more_slots_than_its_template_is_refused(tmp_path: Path) -> None:
    """Un exces et un manque de sens contraire s'annulaient dans le cardinal.

    Mesure en revue sur un gabarit 2 frames/page: une repartition 3/1/2 rendait
    `expected == 6`, `written == 6` et `complete: true`, sur un lot dont la
    structure contredit son propre gabarit.
    """
    trop_remplie = make_payload(page_index=0, page_count=2, first_slot=0, slot_count=3)
    frames = tuple(np.zeros((40, 60, 3), np.uint16) for _ in range(3))
    with pytest.raises(sof.LotInconsistencyError, match="slots la ou son"):
        sof.write_lot_output_frames(
            tmp_path, [sof.ScannedPage(payload=trop_remplie, frames=frames)]
        )
    assert not (tmp_path / project_layout.OUTPUT_FRAMES_DIRNAME).exists()


def test_an_intermediate_page_below_its_template_is_warned(tmp_path: Path) -> None:
    """Le manque, lui, ne se refuse pas: il produit un faux **echec**, pas un
    faux succes. Il s'avertit donc, la ou l'hypothese est utilisee."""
    creuse = make_payload(page_index=0, page_count=2, first_slot=0, slot_count=1)
    derniere = make_payload(page_index=1, page_count=2, first_slot=1, slot_count=2)
    report = sof.write_lot_output_frames(
        tmp_path, [full_page(creuse), full_page(derniere)]
    )
    assert "PAGE_SLOT_COUNT_BELOW_TEMPLATE" in report.warnings
    assert report.complete is False


# --- Bloquant B1 de la revue de 5.16: la page de calibration n'est pas creuse ---


def test_a_v2_lot_with_its_calibration_page_is_complete_and_never_called_underfilled(
    tmp_path: Path,
) -> None:
    """**Bloquant B1 de la revue de 5.16**, ferme au niveau du rapport de 5.6.

    Deux mecanismes de ce module derivent le cardinal attendu en supposant que toute page
    non derniere porte `frames_per_page` emplacements. La story 5.16 fait passer
    `page_count` de `ceil(frames / fpp)` a `1 + ceil(...)`: la page de calibration est
    comptee, elle est a l'index 0, elle n'est jamais la derniere, et elle porte **zero**
    emplacement -- donc elle violait les deux hypotheses. Mesure d'avant correctif sur ce
    gabarit: `complete = False`, `expected = 6` pour 4 frames ecrites, et un
    `PAGE_SLOT_COUNT_BELOW_TEMPLATE` qui accusait d'etre creuse la page dont depend toute
    la correction du lot.

    Le temoin negatif est indispensable et il est juste en dessous: le **meme** lot
    d'images sans page de calibration rend le meme cardinal. C'est ce qui distingue « le
    correctif retire la page de calibration du compte » de « le correctif a change le
    compte ».
    """
    pages = v2_lot_with_calibration_page(images_pages=2)
    report = sof.write_lot_output_frames(tmp_path, pages)

    assert report.expected_frame_count == 4, report.expected_frame_count
    assert len(report.frames) == 4
    assert report.complete is True, report.warnings
    assert "PAGE_SLOT_COUNT_BELOW_TEMPLATE" not in report.warnings
    assert report.warnings == ()
    # La page de calibration est bien **dans** le lot passe a l'ecriture: sans cela le
    # test ne mesurerait rien.
    assert report.page_count == 3
    assert len(pages) == 3
    assert pages[0].payload["page_role"] == page_roles.PAGE_ROLE_CALIBRATION


def test_the_same_images_pages_without_a_calibration_page_expect_the_same_cardinal(
    tmp_path: Path,
) -> None:
    """Temoin negatif du test precedent: le compte ne depend pas de la page de calibration.

    Les memes deux planches d'images, seules, dans un lot de deux pages. Le cardinal
    attendu est le meme, et c'est la propriete qui dit que le correctif **retire la page du
    compte** au lieu de deplacer le compte.
    """
    premiere = make_payload(page_index=0, page_count=2, first_slot=0, slot_count=2,
                            template_id=PORTRAIT_2F_V2)
    seconde = make_payload(page_index=1, page_count=2, first_slot=2, slot_count=2,
                           template_id=PORTRAIT_2F_V2)
    report = sof.write_lot_output_frames(
        tmp_path, [full_page(premiere), full_page(seconde)])

    assert report.expected_frame_count == 4
    assert report.complete is True
    assert report.warnings == ()


def test_an_images_sheet_that_is_really_underfilled_is_still_warned_in_a_v2_lot(
    tmp_path: Path,
) -> None:
    """Frontiere symetrique: le correctif ne desarme pas l'avertissement.

    Un correctif qui aurait retire l'avertissement pour **toutes** les pages non
    dernieres, ou qui aurait cesse de le calculer, passerait les deux tests precedents. Ce
    lot porte une page de calibration **et** une planche d'images reellement creuse, et
    l'avertissement doit nommer la planche -- jamais la page de calibration.
    """
    calibration = calibration_payload(page_count=3)
    creuse = make_payload(page_index=1, page_count=3, first_slot=0, slot_count=1,
                          template_id=PORTRAIT_2F_V2)
    derniere = make_payload(page_index=2, page_count=3, first_slot=1, slot_count=2,
                            template_id=PORTRAIT_2F_V2)
    report = sof.write_lot_output_frames(
        tmp_path,
        [scanned_calibration_page(calibration), full_page(creuse), full_page(derniere)],
    )

    assert "PAGE_SLOT_COUNT_BELOW_TEMPLATE" in report.warnings
    assert report.complete is False
    # Et le cardinal attendu est celui des seules planches d'images: 2 pages x 2 frames.
    assert report.expected_frame_count == 4


# --- la conformite confrontee a un autre lot (survivants M07, M08, M02) -----


@pytest.mark.parametrize(
    "etranger",
    [
        ("rush-002", FPS),  # meme cadence, autre rush
        (RUSH, 24.0),  # meme rush, autre cadence
    ],
    ids=["autre-rush", "autre-cadence"],
)
def test_a_scan_frame_of_another_lot_is_never_conforming(
    tmp_path: Path, etranger
) -> None:
    """La conformite est la **reconstruction** du nom, pas son parsing.

    Mutants M07 (`return True`) et M08 (`return bool(timecode)`): tous deux
    survivaient parce qu'aucun test ne posait dans le dossier de sortie un
    fichier qui **se parse comme une frame de scan mais appartient a un autre
    lot**. C'est pourtant la seule chose qui distingue « frame de ce lot » de
    « frame de scan quelconque » -- et c'est le pendant de test du melange de
    deux cadences dans un dossier unique.
    """
    autre_rush, autre_fps = etranger
    output_dir = project_layout.scan_frames_dir(tmp_path, RUSH, FPS)
    output_dir.mkdir(parents=True)
    intrus = naming.build_scan_frame_filename(autre_rush, autre_fps, "00:00:09:00")
    (output_dir / intrus).write_bytes(b"une frame d'un autre lot")

    assert not sof.is_conforming_scan_frame_name(intrus, RUSH, FPS)

    first, second = two_page_lot()
    report = sof.write_lot_output_frames(
        tmp_path, [full_page(first), full_page(second)]
    )
    assert intrus in report.nonconforming_files
    assert intrus not in report.preexisting_frames
    assert report.observed_frame_count == 4


def test_a_file_counted_at_write_time_but_absent_from_the_dir_is_never_complete(
    tmp_path: Path, monkeypatch
) -> None:
    """Defense en profondeur, desormais exercee (survivant M02).

    `complete` exige `not missing_frames`; remplacer cette condition par `True`
    ne faisait tomber aucun test, faute de scenario produisant une frame comptee
    a l'ecriture et absente du dossier. La condition n'est pas decorative: un
    fichier compte mais absent apres coup est un faux succes (R12). On force
    donc le predicat de conformite a ignorer une frame, ce qui reproduit
    exactement l'etat que la condition surveille.
    """
    first, second = two_page_lot()
    reel = sof.is_conforming_scan_frame_name
    ignore = naming.build_scan_frame_filename(RUSH, FPS, second["slots"][-1]["frame_timecode"])

    def conformite_trouee(name, rush_id, fps_target):
        return False if name == ignore else reel(name, rush_id, fps_target)

    monkeypatch.setattr(sof, "is_conforming_scan_frame_name", conformite_trouee)
    report = sof.write_lot_output_frames(
        tmp_path, [full_page(first), full_page(second)]
    )
    assert report.written_frame_count == report.expected_frame_count
    assert report.missing_frames == (ignore,)
    assert "EXPECTED_FRAME_FILE_MISSING" in report.warnings
    assert report.complete is False


# --- le chemin quatre canaux et la profondeur source (M23, M30) -------------


def test_the_alpha_channel_of_a_four_channel_mire_is_opaque() -> None:
    """Branche de production nominale, jusque-la entierement intestee (M23).

    Ecrire l'opacite sur le canal 0 (bleu) au lieu du canal 3 ne faisait tomber
    aucun test: aucun lot du fichier n'avait quatre canaux. La mire sortirait
    bleue et transparente au lieu d'achromatique et opaque -- selon le lecteur,
    une mire qui ne se voit pas du tout.
    """
    image = sof.build_missing_frame_image(
        shape=(166, 295, 4), page_index=11, page_count=40,
        frame_timecode="00:00:12:14",
    )
    assert image.shape == (166, 295, 4)
    assert np.all(image[:, :, 3] == sof.MAX_LEVEL_16BIT), "alpha non opaque"
    # Les trois canaux de couleur restent achromatiques et portent le damier.
    assert np.array_equal(image[:, :, 0], image[:, :, 1])
    assert np.array_equal(image[:, :, 0], image[:, :, 2])
    assert int(image[:, :, 0].min()) == 0


def test_the_source_depth_never_counts_a_synthetic_frame(tmp_path: Path) -> None:
    """Piege 9, cote statistique (survivant M30).

    Le seul test de profondeur source portait sur un lot **sans aucune mire**:
    retirer le filtre `if not frame.synthetic` ne cassait rien. Le cas qui
    distingue les deux comportements est un lot **8 bits** portant **une mire**
    (donc 16 bits): il ferait declarer un scan 16 bits qui n'a jamais eu lieu.
    """
    first, second = two_page_lot()
    plan = crop_plan_for(first)
    frames = tuple(
        np.full((frame.height_px, frame.width_px, 3), 200, np.uint8)
        for frame in plan.frames
    )
    report = sof.write_lot_output_frames(
        tmp_path,
        [
            sof.ScannedPage(payload=first, crop_plan=plan, frames=frames),
            failed_page(second, "page_detection_failed"),
        ],
    )
    assert report.synthetic_frame_count == 2
    assert {frame.source_bit_depth for frame in report.synthetic_frames} == {16}
    assert report.source_bit_depths == (8,)


# --- les filets du rapport (survivants M35, M37) ----------------------------


def test_an_absolute_path_that_reaches_the_report_is_refused(
    tmp_path: Path, monkeypatch
) -> None:
    """Le filet final de l'AC 10, enfin exerce (survivant M35).

    Neutraliser `_assert_no_absolute_path` ne faisait rien tomber: c'est
    `_project_relative_posix` qui protege, et le filet n'a de valeur que pour ce
    qui lui echapperait -- un chemin absolu entrant dans le rapport par un autre
    champ. On simule exactement cela.
    """
    first, second = two_page_lot()
    monkeypatch.setattr(
        sof, "_project_relative_posix", lambda path, project_dir: f"/absolu/{path.name}"
    )
    with pytest.raises(sof.ScanOutputError, match="Chemin absolu"):
        sof.write_lot_output_frames(tmp_path, [full_page(first), full_page(second)])


def test_the_warning_vocabulary_is_checked_at_emission(
    tmp_path: Path, monkeypatch
) -> None:
    """La fermeture du vocabulaire est verifiee **sur le chemin qui la consomme**.

    Survivant M37: `test_the_warning_vocabulary_is_closed` eprouve
    `validate_warning_code` en direct, jamais le fait que `_build_report`
    l'applique. Remplacer l'emission par `tuple(warnings)` ne faisait rien
    tomber, et un code libre glisse dans `_build_report` ressortirait au rapport,
    transporte tel quel par 5.7 et 5.8 (EPIC4-ARB-1).
    """
    monkeypatch.setattr(
        sof,
        "SCAN_OUTPUT_WARNING_CODES",
        tuple(c for c in sof.SCAN_OUTPUT_WARNING_CODES if c != "PAGE_MISSING_FROM_LOT"),
    )
    first = make_payload(page_index=0, page_count=2, first_slot=0, slot_count=2)
    with pytest.raises(ValueError, match="Code d'avertissement d'ecriture inconnu"):
        sof.write_lot_output_frames(tmp_path, [full_page(first)])


# --- le lisere de la mire, et le plafond de plume mort (couche 1 F6, M27) ---


def test_the_crown_protects_the_outline_when_the_pen_floor_is_reached() -> None:
    """A plume 1, seule une couronne peut rendre le lisere.

    Le plafond `max(1, outline_pen - 1)` etait du **code mort** (balayage
    exhaustif des echelles de 0.001 a 20.000, sur trois plafonds de plume
    mesurables: zero echelle ou il borne le remplissage), et il ne pouvait de
    toute facon rien proteger a plume 1, ou 1 est deja le plancher. Il a ete
    retire et remplace par la couronne.
    """
    petite = 0.20  # sous le seuil ou l'epaisseur de contour voulue tombe a 1
    outline, fill = sof.derive_text_thicknesses(petite)
    assert (outline, fill) == (1, 1)
    outline_pen, radius, fill_pen = sof._text_pens(petite)
    assert outline_pen == 1 and fill_pen == 1
    assert radius >= 1, (
        "sans couronne, le remplissage blanc recouvre exactement le contour "
        "noir et la mire devient invisible sur les cellules blanches du damier"
    )


# --- gardes et diagnostics rendus exacts ------------------------------------


@pytest.mark.parametrize(
    "page_index, page_count", [(-1, 5), (5, 3), (3, 3), (0, 0)]
)
def test_the_second_line_refuses_a_page_rank_out_of_bounds(page_index, page_count) -> None:
    """`page 0/5` et `page 6/3` etaient peints sans un mot.

    La fonction est exportee, donc appelable hors de `write_lot_output_frames`
    ou `validate_payload` garde les bornes. Le decalage d'une unite etait
    protege (piege 12), la borne non -- dans des pixels qu'aucune machine ne
    relit.
    """
    with pytest.raises(sof.ScanOutputError, match="hors bornes|invalide"):
        sof.missing_frame_second_line(
            page_index=page_index, page_count=page_count,
            frame_timecode="00:00:00:00",
        )


def test_a_unicode_digit_never_passes_for_a_conforming_name() -> None:
    """`\\d` est Unicode en Python: un chiffre arabo-indien etait accepte.

    Le nom de fichier est le seul support d'identite d'une frame qui voyage
    seule: un caractere qu'aucun systeme de destination ne rend de la meme
    facon n'y a pas sa place.
    """
    exotique = "scan_rush-001_5_00-00-00-0\u0660.tiff"
    with pytest.raises(naming.NamingError):
        naming.read_scan_frame_timecode(exotique)
    assert not sof.is_conforming_scan_frame_name(exotique, RUSH, FPS)


def test_the_unwritten_timecodes_are_named(tmp_path: Path) -> None:
    """AC 8: « nommant precisement ce qui manque (pages absentes, timecodes
    absents) ».

    C'est le seul cas ou les timecodes manquants sont **connus** du module: une
    page presente et decodee, en echec, dont la forme est indeterminable. Ils
    etaient parfaitement disponibles dans le payload et n'apparaissaient nulle
    part.
    """
    payload = make_payload(page_index=0, page_count=1, first_slot=0, slot_count=2)
    report = sof.write_lot_output_frames(
        tmp_path, [sof.ScannedPage(payload=payload, failure="page_detection_failed")]
    )
    assert report.frames == ()
    assert report.shape_indeterminable_pages == (0,)
    assert report.unwritten_frame_timecodes == tuple(
        sorted(slot["frame_timecode"] for slot in payload["slots"])
    )
    assert sof.report_document(report)["unwritten_frame_timecodes"] == list(
        report.unwritten_frame_timecodes
    )


def test_a_filesystem_failure_stays_in_the_module_hierarchy(tmp_path: Path) -> None:
    """Le module *est* celui qui ecrit sur le disque: ses echecs lui appartiennent.

    `output-frames/<slug>` existant en tant que **fichier** sortait en
    `FileExistsError` nu, hors des cinq classes soigneusement documentees du
    module.
    """
    output_dir = project_layout.scan_frames_dir(tmp_path, RUSH, FPS)
    output_dir.parent.mkdir(parents=True)
    output_dir.write_text("pas un dossier", encoding="utf-8")
    first, second = two_page_lot()
    with pytest.raises(sof.ScanOutputError, match="non creable"):
        sof.write_lot_output_frames(tmp_path, [full_page(first), full_page(second)])


# ===========================================================================
# Story 5.28 -- le canal de progression sur le chemin `scan write`
#
# C'est le chemin que 7.6 consomme reellement (`EPIC7-ARB-79`) : son action
# principale « Extraire les TIFF » lance `scan write`, qui n'appelle jamais
# ffmpeg. La progression y est une boucle Python dont le cardinal est connu
# d'avance, et tous les refus durs la precedent.
# ===========================================================================


class JournalDeProgression:
    """Rappel de progression de test."""

    def __init__(self, leve: bool = False) -> None:
        self.jalons: list[tuple[int, int]] = []
        self.leve = leve

    def __call__(self, faites, total):
        self.jalons.append((faites, total))
        if self.leve:
            raise RuntimeError("rappel fautif fourni par l'appelant")


def empreinte_du_dossier(project_dir: Path):
    """Nom et octets de chaque frame ecrite -- l'artefact, rien d'autre."""
    racine = project_dir / project_layout.OUTPUT_FRAMES_DIRNAME
    if not racine.exists():
        return []
    return sorted(
        (chemin.relative_to(racine).as_posix(), chemin.read_bytes())
        for chemin in sorted(racine.rglob("*"))
        if chemin.is_file()
    )


def lot_de_pages(rush_id: str, nombre_de_pages: int) -> list:
    """Un lot de `nombre_de_pages` pages a deux emplacements chacune."""
    return [
        full_page(
            make_payload(
                page_index=index,
                page_count=nombre_de_pages,
                first_slot=2 * index,
                slot_count=2,
                rush_id=rush_id,
            )
        )
        for index in range(nombre_de_pages)
    ]


# --- AC 6: un jalon par frame ecrite, aucun avant la boucle -----------------


def test_scan_write_emet_un_jalon_par_frame_ecrite(tmp_path: Path) -> None:
    """AC 6: le nombre de jalons egale le nombre de frames ecrites."""
    journal = JournalDeProgression()
    pages = lot_de_pages(RUSH, 3)
    report = sof.write_lot_output_frames(
        tmp_path, pages, rappel_progression=journal
    )
    assert report.written_frame_count == 6
    assert journal.jalons == [(rang, 6) for rang in range(1, 7)]
    assert journal.jalons[-1] == (6, 6)


def test_le_fichier_compte_par_le_jalon_est_DEJA_sur_le_disque(tmp_path: Path) -> None:
    """AC 6 et AC 12 (F5, critique) : le numerateur ne ment jamais d'un fichier.

    « Aucun jalon avant l'ecriture » n'etait mesure que sur les **refus durs** :
    deux injections sur le chemin **nominal** -- un jalon en tete de boucle, un
    jalon juste apres la construction de l'emetteur -- passaient 196 tests sur
    196. Toute la famille « le numerateur ment d'un fichier » traversait le banc,
    et l'effet observable est la carte de 7.6 qui annonce « 6/6 » **avant** que
    la sixieme frame existe : si cette ecriture echoue, l'operatrice a vu 100 %
    puis une erreur, c'est-a-dire le faux succes qu'`EPIC7-ARB-79` et l'AC 12
    existent pour interdire.

    Le test compte donc les fichiers **au moment meme** de chaque jalon.
    """
    racine = tmp_path / project_layout.OUTPUT_FRAMES_DIRNAME
    constats: list[tuple[int, int, int]] = []

    def rappel_qui_regarde_le_disque(faites, total):
        presents = (
            sum(1 for chemin in racine.rglob("*") if chemin.is_file())
            if racine.exists()
            else 0
        )
        constats.append((faites, total, presents))

    report = sof.write_lot_output_frames(
        tmp_path, lot_de_pages(RUSH, 3),
        rappel_progression=rappel_qui_regarde_le_disque,
    )

    assert report.written_frame_count == 6
    assert constats, "aucun jalon : le test ne mesurerait rien"
    for faites, total, presents in constats:
        assert presents == faites, (
            f"jalon ({faites}/{total}) emis alors que {presents} fichier(s) "
            "seulement sont sur le disque : le numerateur ment"
        )
    assert [faites for faites, _, _ in constats] == [1, 2, 3, 4, 5, 6]


def test_scan_write_n_emet_aucun_jalon_avant_la_premiere_ecriture(
    tmp_path: Path,
) -> None:
    """AC 6: les refus durs precedent la boucle et ne progressent jamais.

    Un timecode duplique est refuse **avant** la premiere ecriture, « pour
    qu'un refus ne laisse jamais un dossier a demi rempli ». Une carte de tache
    qui verrait un jalon passer croirait qu'un travail a commence alors que
    rien n'a ete ecrit.
    """
    first = make_payload(
        page_index=0, page_count=2, first_slot=0, slot_count=2,
        timecodes=["00:00:00:00", "00:00:01:00"],
    )
    second = make_payload(
        page_index=1, page_count=2, first_slot=2, slot_count=2,
        timecodes=["00:00:01:00", "00:00:03:00"],
    )
    journal = JournalDeProgression()
    with pytest.raises(sof.DuplicateFrameTimecodeError):
        sof.write_lot_output_frames(
            tmp_path, [full_page(first), full_page(second)],
            rappel_progression=journal,
        )
    assert journal.jalons == []
    assert not (tmp_path / project_layout.OUTPUT_FRAMES_DIRNAME).exists()


def test_un_lot_melange_est_refuse_sans_aucun_jalon(tmp_path: Path) -> None:
    """AC 6 et AC 12: le refus dur traverse intact, rappel branche."""
    first = make_payload(page_index=0, page_count=2, first_slot=0, slot_count=2)
    other = make_payload(
        page_index=1, page_count=2, first_slot=2, slot_count=2, rush_id="rush-002"
    )
    journal = JournalDeProgression()
    with pytest.raises(sof.LotInconsistencyError, match="rush_id"):
        sof.write_lot_output_frames(
            tmp_path, [full_page(first), full_page(other)],
            rappel_progression=journal,
        )
    assert journal.jalons == []


def test_un_refus_d_ecrasement_ne_produit_aucun_jalon(tmp_path: Path) -> None:
    """AC 12: `OutputFrameExistsError` est levee a l'identique, texte compris."""
    pages = lot_de_pages(RUSH, 2)
    sof.write_lot_output_frames(tmp_path, pages)
    journal = JournalDeProgression()
    with pytest.raises(sof.OutputFrameExistsError) as capture:
        sof.write_lot_output_frames(tmp_path, pages, rappel_progression=journal)
    assert "--overwrite" in str(capture.value)
    assert journal.jalons == []


# --- AC 11: la progression ne casse jamais ce qu'elle observe ---------------


def test_un_rappel_qui_leve_ne_change_ni_les_frames_ni_le_rapport(
    tmp_path: Path, caplog
) -> None:
    """AC 11: memes fichiers, memes noms, meme rapport -- et un seul journal."""
    sans_dir = tmp_path / "sans"
    avec_dir = tmp_path / "avec"
    sans_dir.mkdir()
    avec_dir.mkdir()

    temoin = sof.write_lot_output_frames(sans_dir, lot_de_pages(RUSH, 3))
    journal = JournalDeProgression(leve=True)
    with caplog.at_level(logging.WARNING):
        mesure = sof.write_lot_output_frames(
            avec_dir, lot_de_pages(RUSH, 3), rappel_progression=journal
        )

    assert mesure == temoin
    assert empreinte_du_dossier(avec_dir) == empreinte_du_dossier(sans_dir)
    assert len(journal.jalons) == 6
    avertissements = [
        enregistrement for enregistrement in caplog.records
        if enregistrement.name == "mixed_media_utility.progression"
    ]
    assert len(avertissements) == 1, (
        f"{len(avertissements)} avertissements pour 6 jalons fautifs : un rappel "
        "fautif noierait le journal"
    )


def test_les_artefacts_de_scan_write_sont_identiques_avec_et_sans_rappel(
    tmp_path: Path,
) -> None:
    """AC 8 et AC 11: la progression est observationnelle, point."""
    sans_dir = tmp_path / "sans"
    avec_dir = tmp_path / "avec"
    sans_dir.mkdir()
    avec_dir.mkdir()

    temoin = sof.write_lot_output_frames(sans_dir, lot_de_pages(RUSH, 2))
    mesure = sof.write_lot_output_frames(
        avec_dir, lot_de_pages(RUSH, 2), rappel_progression=JournalDeProgression()
    )
    assert mesure == temoin
    assert empreinte_du_dossier(avec_dir) == empreinte_du_dossier(sans_dir)


def test_un_rappel_non_appelable_ne_fait_pas_echouer_l_ecriture(
    tmp_path: Path,
) -> None:
    """AC 11: une valeur aberrante desactive le canal, elle ne casse rien."""
    report = sof.write_lot_output_frames(
        tmp_path, lot_de_pages(RUSH, 2), rappel_progression="pas un rappel"
    )
    assert report.written_frame_count == 4


# --- AC 7: deux lots de cardinaux differents, cible en seconde position -----


LOTS_DE_PROGRESSION = [
    ("rush-court", 1),   # 1 page x 2 emplacements = 2 frames
    ("rush-vise", 3),    # 3 pages x 2 emplacements = 6 frames -- LA CIBLE
]


@pytest.fixture(params=["ordre-nominal", "permute"])
def deux_lots_scannes(request):
    """Deux lots de cardinaux DIFFERENTS ; la cible n'est pas la premiere.

    La variante permutee est ce qui donne sa valeur au point precedent : un
    emetteur qui rendrait toujours le total du **premier** lot, ou un
    denominateur fige d'un lot a l'autre, ne peut pas passer les deux ordres.
    """
    if request.param == "permute":
        return list(reversed(LOTS_DE_PROGRESSION))
    return list(LOTS_DE_PROGRESSION)


def test_chaque_lot_scanne_porte_son_propre_total(
    tmp_path: Path, deux_lots_scannes
) -> None:
    """AC 7: le denominateur suit le lot ecrit, jamais le premier vu."""
    cardinaux = {nom: 2 * pages for nom, pages in deux_lots_scannes}
    assert len(set(cardinaux.values())) == 2, (
        "la fabrique doit produire deux lots DISTINGUABLES"
    )

    totaux_observes = {}
    for nom, nombre_de_pages in deux_lots_scannes:
        journal = JournalDeProgression()
        report = sof.write_lot_output_frames(
            tmp_path, lot_de_pages(nom, nombre_de_pages),
            rappel_progression=journal,
        )
        attendu = cardinaux[nom]
        assert report.written_frame_count == attendu
        assert journal.jalons == [(rang, attendu) for rang in range(1, attendu + 1)]
        totaux_observes[nom] = {total for _, total in journal.jalons}

    assert totaux_observes["rush-vise"] == {cardinaux["rush-vise"]}
    assert totaux_observes["rush-court"] != totaux_observes["rush-vise"]
