"""Tests du recadrage par la marge encodee (story 5.3).

Le test central est l'**aller-retour contre le vrai producteur** (AC 8): une
page synthetique est construite depuis le plan reel de `pdf_composition`, les
images temoin sont posees dans les `image_rect_mm` reels, la page transite par
la detection de 5.2, et les frames recuperees sont confrontees aux temoins. Les
valeurs attendues sont derivees des modules reels, jamais d'un
`SimpleNamespace` de fixture ni de constantes recopiees a la main -- c'est
l'action item 3 de la retro Epic 4, cette fois ecrit des la story initiale.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import (
    layout,
    page_templates,
    pdf_composition,
    scan_crop,
    scan_detection,
)
from mixed_media_utility.io import naming

MODULE_PATH = REPO_ROOT / "src" / "mixed_media_utility" / "scan_crop.py"
ARUCO_PATH = REPO_ROOT / "src" / "mixed_media_utility" / "detection" / "aruco.py"

DPI = 300
PORTRAIT_2F_M5 = "tpl-a4-portrait-2f-m5-v1"
PAYSAGE_4F_M2 = "tpl-a4-paysage-4f-m2-v1"
PORTRAIT_2F_M0 = "tpl-a4-portrait-2f-v1"


def slots_for(count: int, *, first: int = 1) -> list[dict]:
    return [
        {"slot_index": first + index, "frame_timecode": f"00:00:0{index}:00"}
        for index in range(count)
    ]


def plan_for(template_id: str, *, dpi: int = DPI, slots: list[dict] | None = None):
    spec = page_templates.get_template(template_id)
    return scan_crop.build_page_crop_plan(
        template_id=template_id,
        slots=slots if slots is not None else slots_for(spec.frames_per_page),
        dpi=dpi,
    )


# --- AC 1 / AC 4: le rectangle est resolu, jamais recalcule ------------------


@pytest.mark.parametrize("preset", ["0", "2", "5"])
@pytest.mark.parametrize("orientation", ["portrait", "paysage"])
def test_the_crop_rect_is_the_one_the_printer_used(orientation: str, preset: str) -> None:
    """Egalite **stricte** avec le rectangle de pose de `pdf_composition`.

    C'est la symetrie que la story existe pour garantir: la marge disparait
    parce qu'elle n'a jamais ete dans `image_rect_mm`, pas parce qu'on la
    retire une seconde fois.
    """
    frames_per_page = 2 if orientation == "portrait" else 4
    template_id = page_templates.build_template_id(orientation, frames_per_page, preset)
    plan = plan_for(template_id)
    spec = page_templates.get_template(template_id)

    for zone, frame in zip(spec.frame_zones_mm, plan.frames):
        # Le producteur d'impression, appele tel quel.
        expected = page_templates.frame_image_rect_mm(zone, spec.margin_mm)
        assert frame.image_rect_mm == expected
        assert frame.zone_rect_mm == (zone["x"], zone["y"], zone["width"], zone["height"])


@pytest.mark.parametrize("preset", ["0", "2", "5"])
@pytest.mark.parametrize(
    ("orientation", "frames_per_page"), [("portrait", 2), ("paysage", 4)]
)
def test_the_crop_rect_equals_the_real_composition_plan(
    orientation: str, frames_per_page: int, preset: str
) -> None:
    """Confrontation au **vrai** `FrameSlotPlan`, sur les six couples.

    `pdf_composition` stocke `image_rect_mm` dans chaque slot: c'est
    litteralement le rectangle que `pdf_render` remplit. Le balayage qui
    appelait `frame_image_rect_mm` des deux cotes ne prouvait rien -- il
    confrontait le code au meme appel que le code. Ici la reference est le plan
    d'impression, produit par un chemin entierement distinct.
    """
    composition = _compose(
        orientation=orientation, frames_per_page=frames_per_page, margin_preset=preset
    )
    page = _images_pages(composition)[0]
    plan = scan_crop.build_page_crop_plan(
        template_id=page.template_id,
        slots=[
            {"slot_index": slot.slot_index, "frame_timecode": slot.frame_timecode}
            for slot in page.frames
        ],
        dpi=DPI,
    )
    assert len(plan.frames) == len(page.frames)
    assert [frame.image_rect_mm for frame in plan.frames] == [
        slot.image_rect_mm for slot in page.frames
    ]
    assert [frame.zone_rect_mm for frame in plan.frames] == [
        slot.zone_rect_mm for slot in page.frames
    ]
    assert [frame.zone_name for frame in plan.frames] == [
        slot.zone_name for slot in page.frames
    ]


def test_a_hand_rolled_margin_removal_is_not_the_same_rectangle() -> None:
    """Le piege numero deux de la story, chiffre.

    « Retirer 5 mm de chaque cote » ne donne pas `image_rect_mm`: il manque
    l'inscription du plus grand 16:9 centre. L'ecart est franc -- et aucun test
    de « la marge a bien ete retiree » ne le verrait.
    """
    spec = page_templates.get_template(PORTRAIT_2F_M5)
    zone = spec.frame_zones_mm[0]
    naive = (
        zone["x"] + spec.margin_mm,
        zone["y"] + spec.margin_mm,
        zone["width"] - 2 * spec.margin_mm,
        zone["height"] - 2 * spec.margin_mm,
    )
    real = page_templates.frame_image_rect_mm(zone, spec.margin_mm)
    assert real != naive
    assert abs(real[0] - naive[0]) == pytest.approx(3.888, abs=0.01)
    # ~92 px de decalage a 600 ppp: un decalage franc, pas un bruit d'arrondi.
    assert abs(
        page_templates.mm_to_px(real[0], 0, 600)[0]
        - page_templates.mm_to_px(naive[0], 0, 600)[0]
    ) == 92


def test_no_public_entry_point_accepts_a_margin() -> None:
    """AC 4: la marge est resolue, jamais passee.

    Une marge en parametre pourrait contredire le template, et la contradiction
    serait silencieuse: le crop serait faux avec un plan d'apparence valide.
    """
    import inspect

    for name in scan_crop.__all__:
        attribute = getattr(scan_crop, name)
        if not callable(attribute) or isinstance(attribute, type):
            continue
        parameters = inspect.signature(attribute).parameters
        # « marge » aussi bien que « margin »: le depot impose le francais dans
        # le code nouveau, et un verrou qui ne grepe que l'anglais laisserait
        # passer exactement le parametre qu'un contributeur d'ici ecrirait.
        assert not any(
            "margin" in parameter or "marge" in parameter for parameter in parameters
        ), name


def test_the_margin_is_read_from_the_template_and_nowhere_else() -> None:
    """Verrou par AST, pas par sous-chaine.

    `assert "spec.margin_mm" in source` etait satisfait par la **docstring**
    seule: on pouvait supprimer l'unique usage reel et l'assertion tenait.
    """
    import ast

    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "MARGIN_PRESETS_MM" not in source
    assert "PRINTER_MARGIN_MM" not in source

    tree = ast.parse(source, filename=str(MODULE_PATH))
    reads_spec_margin = any(
        isinstance(node, ast.Attribute)
        and node.attr == "margin_mm"
        and isinstance(node.value, ast.Name)
        and node.value.id == "spec"
        for node in ast.walk(tree)
    )
    assert reads_spec_margin, "la marge doit etre lue sur le TemplateSpec resolu"
    # Aucune valeur de marge en dur: 0.0/2.0/5.0 ne doivent pas apparaitre
    # comme litteraux du module.
    literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, float)
    }
    assert not (literals & {2.0, 5.0}), sorted(literals)


# --- AC 3: les trois presets, dont celui qui ne discrimine pas ---------------


@pytest.mark.parametrize("preset", ["0", "2", "5"])
def test_every_margin_preset_is_covered(preset: str) -> None:
    template_id = page_templates.build_template_id("portrait", 2, preset)
    spec = page_templates.get_template(template_id)
    plan = plan_for(template_id)
    zone = spec.frame_zones_mm[0]
    image_rect = plan.frames[0].image_rect_mm

    if preset == "0":
        # **Cas non discriminant, annote comme tel**: toutes les zones du
        # registre sont deja 16:9 par construction, donc a marge nulle
        # `frame_image_rect_mm` rend exactement `zone_rect_mm`. Une
        # implementation qui decouperait `zone_rect_mm` passerait ici. C'est une
        # propriete du preset, pas un defaut du test -- d'ou les deux autres.
        assert image_rect == (zone["x"], zone["y"], zone["width"], zone["height"])
    else:
        assert image_rect != (zone["x"], zone["y"], zone["width"], zone["height"])
        assert image_rect[2] < zone["width"] and image_rect[3] < zone["height"]


def test_the_zero_preset_is_the_only_one_where_both_rects_coincide() -> None:
    # Le pendant du precedent, sur les 33 gabarits: si un preset non nul se
    # mettait a coincider, le test ci-dessus deviendrait vide sans le dire.
    for template_id in page_templates.known_template_ids():
        spec = page_templates.get_template(template_id)
        for zone in spec.frame_zones_mm:
            rect = page_templates.frame_image_rect_mm(zone, spec.margin_mm)
            coincide = rect == (zone["x"], zone["y"], zone["width"], zone["height"])
            assert coincide == (spec.margin_mm == 0.0), template_id


# --- AC 5: conversion, bornes, determinisme ----------------------------------


def test_the_conversion_uses_the_single_recipe(monkeypatch) -> None:
    # La delegation, pas l'egalite des valeurs: une copie conforme passerait.
    monkeypatch.setattr(page_templates, "mm_to_px", lambda x, y, dpi: (7, 11))
    assert scan_crop.crop_rect_px((1.0, 2.0, 3.0, 4.0), 300) == (7, 11, 7, 11)


@pytest.mark.parametrize("bad", [0, -300, True, 3.0, "300", 10**400, 20001])
def test_crop_rect_px_guards_its_own_dpi(bad) -> None:
    """La fonction est **publique**: elle ne peut pas compter sur l'appelant.

    Sans garde, `dpi=True` rendait `(1, 2, 4, 2)` et un DPI negatif des
    coordonnees negatives, que numpy lit « depuis la fin » -- une decoupe au
    mauvais endroit, de la bonne taille, sans erreur.
    """
    with pytest.raises(Exception) as excinfo:
        scan_crop.crop_rect_px((10.0, 20.0, 30.0, 40.0), bad)
    assert not isinstance(excinfo.value, AssertionError)


@pytest.mark.parametrize(
    "rect", [(1.0, 2.0, 3.0), (1.0, 2.0, 3.0, float("nan")), (1.0, 2.0, 3.0, "4")]
)
def test_crop_rect_px_refuses_a_malformed_rectangle(rect) -> None:
    with pytest.raises(scan_crop.ScanCropError):
        scan_crop.crop_rect_px(rect, DPI)


@pytest.mark.parametrize("size", [(0, 100), (100, 0), (-1, 100), (100.0, 100), (True, 100)])
def test_warping_refuses_a_page_size_that_is_not_a_page(size) -> None:
    """`cv2.warpPerspective` avec une taille nulle rend la **taille de l'image
    source**: la page sortirait d'apparence valide, et tout le lot avec."""
    with pytest.raises(scan_crop.ScanCropError):
        scan_crop.warp_detected_page(
            np.zeros((10, 10, 3), dtype=np.uint8), np.eye(3, dtype=np.float64), size
        )


def test_warping_uses_the_template_size_not_the_source_size() -> None:
    source = np.zeros((37, 41, 3), dtype=np.uint8)
    warped = scan_crop.warp_detected_page(source, np.eye(3, dtype=np.float64), (120, 90))
    assert warped.shape[:2] == (90, 120)


def test_the_margin_used_is_the_one_the_template_carries() -> None:
    # Le pendant du verrou AST: forcer la marge a zero dans l'appel donnerait
    # `zone_rect_mm`, donc un crop qui reprend marge et contour.
    spec = page_templates.get_template(PORTRAIT_2F_M5)
    zone = spec.frame_zones_mm[0]
    assert spec.margin_mm == 5.0
    assert plan_for(PORTRAIT_2F_M5).frames[0].image_rect_mm == (
        page_templates.frame_image_rect_mm(zone, spec.margin_mm)
    )
    assert plan_for(PORTRAIT_2F_M5).frames[0].image_rect_mm != (
        page_templates.frame_image_rect_mm(zone, 0.0)
    )


def test_the_slice_bounds_are_half_open_and_the_module_honours_them() -> None:
    """La convention se verifie sur ce que **le module** decoupe.

    La premiere version reproduisait la tranche a la main dans le test et
    n'appelait aucune fonction du module: elle prouvait que numpy fonctionne.
    Ici on peint le pixel juste apres le bord droit et juste apres le bord bas:
    une borne inclusive les ferait entrer dans le crop.
    """
    plan = plan_for(PORTRAIT_2F_M5)
    frame = plan.frames[0]
    page = np.zeros((plan.page_size_px[1], plan.page_size_px[0], 3), dtype=np.uint8)
    page[frame.crop_y_px:frame.crop_y_px + frame.height_px,
         frame.crop_x_px + frame.width_px] = 255
    page[frame.crop_y_px + frame.height_px,
         frame.crop_x_px:frame.crop_x_px + frame.width_px] = 255

    crop = scan_crop.crop_frames(page, plan)[0]
    assert crop.shape[:2] == (frame.height_px, frame.width_px)
    assert crop.max() == 0, "un bord exclusif ne doit pas ramasser le pixel suivant"


def test_the_crop_lands_byte_for_byte_on_the_planned_rectangle() -> None:
    """Verrou positionnel **exact**, sans homographie ni interpolation.

    L'aller-retour tolere une erreur sub-pixel (seuil 5,0 sur 255), si bien
    qu'un decalage systematique d'un pixel dans `crop_frames` y passait: le
    plancher de bruit est 3,48 et un pixel de decalage donne 3,47. Ici la page
    est deja canonique: la comparaison est exacte, et un pixel de decalage
    tombe.
    """
    plan = plan_for("tpl-a4-paysage-8f-m2-v1")
    generator = np.random.default_rng(20260808)
    page = generator.integers(
        0, 256, size=(plan.page_size_px[1], plan.page_size_px[0], 3), dtype=np.uint8
    )
    for frame, crop in zip(plan.frames, scan_crop.crop_frames(page, plan)):
        expected = page[
            frame.crop_y_px:frame.crop_y_px + frame.height_px,
            frame.crop_x_px:frame.crop_x_px + frame.width_px,
        ]
        assert np.array_equal(crop, expected)
        assert not np.array_equal(
            crop,
            page[
                frame.crop_y_px:frame.crop_y_px + frame.height_px,
                frame.crop_x_px + 1:frame.crop_x_px + 1 + frame.width_px,
            ],
        ), "un decalage d'un pixel doit etre discernable"


def test_the_crops_are_views_and_that_is_a_deliberate_choice() -> None:
    # Un lot de huit frames a 1200 ppp pese une centaine de mega-octets, et 5.6
    # les ecrit sans les modifier. Le choix se fige ici: si une story ulterieure
    # decide de copier, ce test doit tomber et le contrat etre relu.
    plan = plan_for(PORTRAIT_2F_M5)
    page = np.zeros((plan.page_size_px[1], plan.page_size_px[0], 3), dtype=np.uint8)
    crop = scan_crop.crop_frames(page, plan)[0]
    assert crop.base is page
    crop[0, 0] = 42
    assert page[plan.frames[0].crop_y_px, plan.frames[0].crop_x_px, 0] == 42


def test_the_bit_depth_of_the_scan_traverses_untouched() -> None:
    # Le chemin scan est en 16 bits depuis la story 5.0: une conversion
    # silencieuse ici annulerait tout ce qu'elle a pose.
    plan = plan_for(PORTRAIT_2F_M5)
    page = np.full(
        (plan.page_size_px[1], plan.page_size_px[0], 3), 65535, dtype=np.uint16
    )
    crop = scan_crop.crop_frames(page, plan)[0]
    assert crop.dtype == np.uint16 and crop.max() == 65535


@pytest.mark.parametrize("template_id", ["tpl-a4-portrait-8f-m5-v1", "tpl-a4-paysage-8f-m2-v1"])
@pytest.mark.parametrize("dpi", [300, 600, 1200])
def test_all_frames_of_a_page_have_identical_dimensions(template_id: str, dpi: int) -> None:
    """Propriete dont l'Epic 6 a besoin: une sequence d'images de dimensions
    variables est un echec d'encodage.

    Le gabarit a **huit** zones est le seul discriminant: sur un deux zones, les
    deux conventions d'arrondi coincident et le test passerait quelle que soit
    l'option retenue.
    """
    plan = plan_for(template_id, dpi=dpi)
    sizes = {(frame.width_px, frame.height_px) for frame in plan.frames}
    assert len(sizes) == 1, sorted(sizes)


def test_the_alternative_rounding_would_not_hold_that_property() -> None:
    """Mesure qui justifie la convention retenue, pas une intuition.

    Arrondir les deux bords independamment donne **quatre** tailles de frame
    differentes sur une page a huit zones a 600 ppp.
    """
    spec = page_templates.get_template("tpl-a4-portrait-8f-m5-v1")
    alternative = set()
    for zone in spec.frame_zones_mm:
        x_mm, y_mm, w_mm, h_mm = page_templates.frame_image_rect_mm(zone, spec.margin_mm)
        x0, y0 = page_templates.mm_to_px(x_mm, y_mm, 600)
        x1, y1 = page_templates.mm_to_px(x_mm + w_mm, y_mm + h_mm, 600)
        alternative.add((x1 - x0, y1 - y0))
    assert len(alternative) == 4
    assert len({(f.width_px, f.height_px) for f in plan_for("tpl-a4-portrait-8f-m5-v1", dpi=600).frames}) == 1


@pytest.mark.parametrize("dpi", [150, 300, 600, 1200])
def test_the_plan_is_deterministic_for_a_given_template_and_dpi(dpi: int) -> None:
    first = scan_crop.plan_json(plan_for(PAYSAGE_4F_M2, dpi=dpi))
    second = scan_crop.plan_json(plan_for(PAYSAGE_4F_M2, dpi=dpi))
    assert first == second
    assert json.loads(first)["dpi"] == dpi


def test_every_registered_template_produces_an_in_page_plan() -> None:
    # Les 33, a quatre resolutions: aucune zone vide, aucune hors page.
    for template_id in page_templates.known_template_ids():
        spec = page_templates.get_template(template_id)
        for dpi in (150, 300, 600, 1200):
            plan = scan_crop.build_page_crop_plan(
                template_id=template_id,
                slots=slots_for(spec.frames_per_page),
                dpi=dpi,
            )
            width_px, height_px = plan.page_size_px
            for frame in plan.frames:
                assert frame.width_px > 0 and frame.height_px > 0
                assert frame.crop_x_px >= 0 and frame.crop_y_px >= 0
                assert frame.crop_x_px + frame.width_px <= width_px
                assert frame.crop_y_px + frame.height_px <= height_px


# --- AC 6: une decoupe hors page est un echec explicite ----------------------


def test_a_crop_outside_the_page_is_refused_and_named() -> None:
    """`array[y0:y1, x0:x1]` hors bornes ne leve rien: il rend un tableau plus
    petit. La garde precede donc la decoupe."""
    plan = plan_for(PORTRAIT_2F_M5)
    shrunk = scan_crop.PageCropPlan(
        template_id=plan.template_id,
        dpi=plan.dpi,
        page_size_px=(plan.page_size_px[0] // 2, plan.page_size_px[1]),
        frames=plan.frames,
    )
    page = np.zeros((shrunk.page_size_px[1], shrunk.page_size_px[0], 3), dtype=np.uint8)
    with pytest.raises(scan_crop.CropOutOfPageError):
        scan_crop.crop_frames(page, shrunk)


@pytest.mark.parametrize(
    ("rect", "reason"),
    [
        ((-1, 10, 100, 100), "x negatif"),
        ((10, -1, 100, 100), "y negatif"),
        ((900, 10, 200, 100), "deborde a droite"),
        ((10, 900, 100, 200), "deborde en bas"),
        ((10, 10, 0, 100), "largeur nulle"),
        ((10, 10, 100, 0), "hauteur nulle"),
    ],
)
def test_the_in_page_guard_refuses_every_way_out(rect, reason: str) -> None:
    """La garde de l'AC 6, testee **directement**.

    Elle est inatteignable par le chemin nominal -- verifie sur 660 000 couples
    gabarit x DPI, aucun rectangle du registre ne sort de sa page -- si bien
    qu'on pouvait supprimer son corps et garder la suite verte. Inatteignable
    aujourd'hui ne veut pas dire inutile: elle protege le jour ou un gabarit,
    un preset ou un DPI change.
    """
    with pytest.raises(scan_crop.CropOutOfPageError) as excinfo:
        scan_crop._assert_inside_page(
            zone_name="frame_zone_1",
            rect_px=rect,
            page_size_px=(1000, 1000),
            template_id=PORTRAIT_2F_M5,
        )
    assert "frame_zone_1" in str(excinfo.value), reason


def test_the_in_page_guard_is_reached_by_the_plan_builder(monkeypatch) -> None:
    # Le pendant du precedent: la garde doit etre **cablee**, pas seulement
    # exister. On fait rendre au registre un rectangle hors page.
    monkeypatch.setattr(
        page_templates, "frame_image_rect_mm", lambda zone, margin: (0.0, 0.0, 1e6, 1e6)
    )
    with pytest.raises(scan_crop.CropOutOfPageError):
        plan_for(PORTRAIT_2F_M5)


def test_the_tolerance_widens_acceptance_it_does_not_narrow_it(monkeypatch) -> None:
    """`CROP_TOLERANCE_PX` doit etre **vivante**, et dans le bon sens.

    Le signe etait inverse: augmenter la « tolerance » refusait des rectangles
    parfaitement interieurs au lieu d'accepter ceux qui mordent d'un pixel --
    exactement le geste que la docstring annonce pour le pilote papier.
    """
    strict = dict(
        zone_name="frame_zone_1",
        rect_px=(0, 0, 1002, 1000),
        page_size_px=(1000, 1000),
        template_id=PORTRAIT_2F_M5,
    )
    with pytest.raises(scan_crop.CropOutOfPageError):
        scan_crop._assert_inside_page(**strict)

    monkeypatch.setattr(scan_crop, "CROP_TOLERANCE_PX", 5)
    scan_crop._assert_inside_page(**strict)  # accepte, ne leve pas
    # ... et un rectangle strictement interieur reste accepte, lui aussi.
    scan_crop._assert_inside_page(
        zone_name="frame_zone_1",
        rect_px=(10, 10, 100, 100),
        page_size_px=(1000, 1000),
        template_id=PORTRAIT_2F_M5,
    )


def test_a_warped_page_of_the_wrong_size_is_refused_before_slicing() -> None:
    plan = plan_for(PORTRAIT_2F_M5)
    page = np.zeros((plan.page_size_px[1] - 1, plan.page_size_px[0], 3), dtype=np.uint8)
    with pytest.raises(scan_crop.CropOutOfPageError) as excinfo:
        scan_crop.crop_frames(page, plan)
    assert "tronquees" in str(excinfo.value)


def test_a_crop_is_never_silently_truncated() -> None:
    # Le crop d'une page valide fait exactement la taille annoncee, pour toutes
    # les zones -- y compris la plus a droite et la plus en bas.
    plan = plan_for("tpl-a4-paysage-8f-m2-v1", dpi=DPI)
    page = np.zeros((plan.page_size_px[1], plan.page_size_px[0], 3), dtype=np.uint8)
    crops = scan_crop.crop_frames(page, plan)
    assert [c.shape[:2] for c in crops] == [
        (f.height_px, f.width_px) for f in plan.frames
    ]


@pytest.mark.parametrize("bad", [None, "page", 42, np.zeros(5)])
def test_a_non_page_input_is_refused_with_the_named_error(bad) -> None:
    with pytest.raises(scan_crop.ScanCropError):
        scan_crop.crop_frames(bad, plan_for(PORTRAIT_2F_M5))


# --- AC 9 / Dev Notes: slots du payload, jamais le nombre de zones -----------


def test_the_plan_is_built_on_the_payload_slots_not_on_the_zone_count() -> None:
    """Derniere page d'un lot: les zones excedentaires sont **vides** -- ni
    image, ni contour, du blanc de page. Les decouper fabriquerait des frames
    blanches sans slot correspondant."""
    plan = plan_for(PAYSAGE_4F_M2, slots=slots_for(2, first=9))
    assert len(plan.frames) == 2
    assert plan.unused_zones == ("frame_zone_3", "frame_zone_4")
    assert plan.warnings == ("ZONE_LEFT_UNUSED",)


def test_a_full_page_leaves_no_unused_zone() -> None:
    plan = plan_for(PAYSAGE_4F_M2)
    assert plan.unused_zones == () and plan.warnings == ()


def test_the_slot_index_is_read_from_the_payload_never_recomputed() -> None:
    """`slot_index` est continu a l'echelle du lot, jamais remis a zero par
    page: la forme `index_de_zone + 1` est juste sur la page 0 et fausse sur
    toutes les suivantes."""
    plan = plan_for(PAYSAGE_4F_M2, slots=slots_for(4, first=17))
    assert [frame.slot_index for frame in plan.frames] == [17, 18, 19, 20]


def test_slots_out_of_order_are_refused_not_paired_blindly() -> None:
    """Le defaut grave de la revue: l'appariement est **positionnel**.

    `io.payload.validate_payload` controle l'unicite des `slot_index` mais pas
    leur ordre: un payload aux slots inverses est donc valide, et chaque
    decoupe recevait l'etiquette et le timecode d'une **autre** frame -- sans
    exception, aux bonnes dimensions. C'est le couple que 5.6 grave dans le nom
    de fichier.
    """
    reversed_slots = list(reversed(slots_for(4, first=9)))
    with pytest.raises(scan_crop.SlotPlanError) as excinfo:
        plan_for(PAYSAGE_4F_M2, slots=reversed_slots)
    assert "consecutifs et croissants" in str(excinfo.value)


@pytest.mark.parametrize(
    "indexes",
    [
        [1, 3],          # un trou: une frame manquante entre deux zones voisines
        [2, 1],          # inversion locale
        [1, 1],          # doublon -- accepte par le payload, faux ici
        [5, 4],
    ],
)
def test_a_non_contiguous_slot_sequence_is_refused(indexes) -> None:
    slots = [{"slot_index": index, "frame_timecode": "00:00:01:00"} for index in indexes]
    with pytest.raises(scan_crop.SlotPlanError):
        plan_for(PORTRAIT_2F_M5, slots=slots)


def test_the_contiguity_invariant_is_the_producer_s_own() -> None:
    """L'invariant verifie n'est pas invente: c'est celui de `pdf_composition`.

    `slot_index` vaut `frame.output_rank`, qui parcourt
    `range(expected_frame_count)`, et une page en prend une tranche contigue.
    On le verifie sur le vrai plan plutot que sur la prose.
    """
    composition = _compose(orientation="paysage", frames_per_page=4, margin_preset="2")
    for page in _images_pages(composition):
        indexes = [slot.slot_index for slot in page.frames]
        assert indexes == list(range(indexes[0], indexes[0] + len(indexes)))
    # ... et le plan de decoupe accepte chacune de ces pages telle quelle.
    for page in _images_pages(composition):
        scan_crop.build_page_crop_plan(
            template_id=page.template_id,
            slots=[
                {"slot_index": slot.slot_index, "frame_timecode": slot.frame_timecode}
                for slot in page.frames
            ],
            dpi=DPI,
        )


def test_a_page_without_any_slot_is_refused() -> None:
    # Une planche sans frame n'est pas produite a l'impression: un plan vide
    # signale un payload tronque, pas une page legitime.
    with pytest.raises(scan_crop.SlotPlanError):
        plan_for(PORTRAIT_2F_M5, slots=[])


@pytest.mark.parametrize("timecode", [42, 1.5, ["00:00:01:00"], {}])
def test_a_malformed_timecode_is_refused(timecode) -> None:
    # Il est grave dans le nom de fichier par 5.6: un type inattendu y
    # produirait un nom absurde, pas une erreur.
    with pytest.raises(scan_crop.SlotPlanError):
        plan_for(PORTRAIT_2F_M5, slots=[{"slot_index": 1, "frame_timecode": timecode}])


def test_more_slots_than_zones_is_refused() -> None:
    with pytest.raises(scan_crop.SlotPlanError) as excinfo:
        plan_for(PORTRAIT_2F_M5, slots=slots_for(3))
    assert "2 zones" in str(excinfo.value)


@pytest.mark.parametrize(
    "slots",
    [
        [{"frame_timecode": "00:00:01:00"}],
        [{"slot_index": True}],
        [{"slot_index": 1.0}],
        [{"slot_index": "1"}],
        ["pas un slot"],
    ],
)
def test_a_malformed_slot_is_refused(slots) -> None:
    # Garde bool-avant-int (action item 2 de la retro Epic 4): `True` est un
    # `int`, et un `slot_index` a `True` produirait un nom de fichier absurde.
    with pytest.raises(scan_crop.SlotPlanError):
        plan_for(PORTRAIT_2F_M5, slots=slots)


def test_an_unknown_template_is_refused_not_guessed() -> None:
    with pytest.raises(page_templates.UnknownTemplateError):
        plan_for("tpl-inexistant-v9")


@pytest.mark.parametrize("bad", [0, -1, True, 3.0, 10**400])
def test_an_invalid_dpi_is_refused(bad) -> None:
    with pytest.raises(scan_detection.ScanDetectionError):
        plan_for(PORTRAIT_2F_M5, dpi=bad)


# --- AC 2 / AC 7 / AC 8: aller-retour contre le vrai producteur --------------


def _images_pages(composition):
    """Les **planches d'images** d'un plan de lot, sans sa page de calibration.

    Depuis la story 5.16 (`EPIC5-ARB-54`), `plan.pages` porte toutes les pages
    imprimees et la premiere est la page de calibration du lot. Ce fichier ne parle que
    de planches: la page de calibration ne porte aucune frame, donc aucun plan de
    decoupe -- `build_page_crop_plan` refuse d'ailleurs une liste d'emplacements vide,
    et c'est une garde qu'on ne relache pas ici. Le chemin de scan la reconnait par son
    **role** et ne lui demande rien (`cli._scanned_pages_for_output`).
    """
    return [page for page in composition.pages if page.frames]


def _compose(**kwargs):
    """Plan de lot reel, depuis un manifest minimal mais contractuel."""
    rush_id, fps_target = "rush-001", 5.0
    lot_id = naming.build_lot_id(rush_id, fps_target)
    manifest = {
        "schema_version": "2.1",
        "project_id": "proj-a",
        "created": "2026-08-08T00:00:00Z",
        "rushes": [
            {
                "rush_id": rush_id,
                "source_name": f"{rush_id}.mov",
                "fps_source": 25.0,
                "fps_source_exact": "25/1",
                "resolution_source": {"width": 1920, "height": 1080},
            }
        ],
        "lots": [
            {
                "lot_id": lot_id,
                "rush_id": rush_id,
                "state": "extraction",
                "fps_target": fps_target,
                "fps_target_exact": "5/1",
                # Story 2.7 (payload 2.1): requis par `_lot_identity` pour composer.
                "timecode_base_fps": "25/1",
                "expected_frame_count": 10,
                "frames_dir": f"frames/{naming.derive_short_id(rush_id)}_"
                f"{naming.format_fps_short(fps_target)}",
                "source_frame_count": 50,
                "source_frame_count_is_exact": True,
                "rounding_policy": "floor",
            }
        ],
        "artifacts": {"frames_dir": "frames"},
        "color": {"target_colorspace": "rec709"},
        "video": {},
        "reconstruction": {},
    }
    return pdf_composition.compose_lot_plan(manifest=manifest, lot_id=lot_id, **kwargs)


CONTOUR_BGR = (0, 0, 255)  # temoin de trait de contour: rouge pur


def _witness(width_px: int, height_px: int, seed: int) -> np.ndarray:
    """Image temoin deterministe, **basse frequence**, sans pixel de contour.

    Un bruit **par pixel** serait le pire signal possible ici: l'aller-retour
    passe par `warpPerspective`, dont l'interpolation bilineaire le detruit, et
    le test echouerait meme avec une decoupe parfaite (ecart moyen mesure: 40
    sur 255). Un signal uniforme, a l'inverse, ne verrouillerait aucune
    position. Il faut donc un motif qui survive au reechantillonnage **et** qui
    reagisse a la translation: degrade lineaire pour la position grossiere,
    damier a gros pas pour la position fine.

    Sensibilite mesuree (portrait 2 zones, preset 5, 300 ppp, ecart moyen sur
    255). **Deux bases distinctes**, que la premiere version melangeait dans un
    seul tableau -- et un tableau dont les lignes ne viennent pas de la meme
    mesure ne justifie aucun seuil:

    * *aller-retour reel*, decoupe parfaite, en passant par l'homographie:
      **3,48**. C'est le plancher de flou de reechantillonnage sur les aretes
      du damier, et rien ne descend en dessous.
    * *tranche directe* de la planche, sans homographie, pour isoler le seul
      effet du decalage:

      | Decalage | 0 px | 1 px | 2 px | 3 px | 92 px |
      | --- | --- | --- | --- | --- | --- |
      | ecart moyen | 0,0 | 3,5 | 7,0 | 10,5 | 26,1 |

    Le seuil est donc pose a **5,0**: il accepte le plancher de
    reechantillonnage (3,48) et l'erreur sub-pixel qui lui est indiscernable
    (1 px, 3,5), et refuse des **2 px** (7,0). Les 92 px de la derniere colonne
    sont l'erreur qu'un retrait de marge fait a la main produirait.

    Ce seuil ne verrouille donc **pas** le pixel pres: c'est le role de
    `test_the_crop_lands_byte_for_byte_on_the_planned_rectangle`, qui compare
    sans interpolation et ou un pixel de decalage tombe.

    Les coins portent des pastilles unies propres au slot: une frame attribuee
    au mauvais slot ne peut pas passer.
    """
    rows, columns = np.mgrid[0:height_px, 0:width_px]
    red = (columns * 150 // max(width_px - 1, 1)).astype(np.int16)
    green = (rows * 150 // max(height_px - 1, 1)).astype(np.int16)
    blue = np.full((height_px, width_px), (seed * 37) % 150, dtype=np.int16)
    checker = (((columns // 24) + (rows // 24)) % 2).astype(np.int16) * 90
    image = np.clip(np.dstack([blue, green, red]) + checker[..., None], 0, 180)
    image = image.astype(np.uint8)
    patch = max(min(width_px, height_px) // 8, 4)
    image[:patch, :patch] = (seed * 23 % 180, 60, 20)
    image[-patch:, -patch:] = (20, seed * 29 % 180, 60)
    return image


#: Ecart moyen tolere sur l'aller-retour, fixe par le tableau de `_witness`.
ROUND_TRIP_TOLERANCE = 5.0


def _print_page(page_plan, dpi: int, *, draw_contours: bool = True) -> np.ndarray:
    """Rendre une planche comme l'impression la pose: temoins dans les
    `image_rect_mm` **reels** du plan, contour trace sur `zone_rect_mm`."""
    spec = page_templates.get_template(page_plan.template_id)
    width_px, height_px = page_templates.page_size_px(spec, dpi)
    canvas = np.full((height_px, width_px, 3), 255, dtype=np.uint8)

    side, _ = page_templates.mm_to_px(layout.MARKER_SIZE_MM, 0, dpi)
    centers = page_templates.corner_marker_centers_mm(spec)
    for marker_id in layout.CORNER_MARKER_IDS:
        marker = layout.generate_aruco_marker_image(marker_id, side)
        cx, cy = page_templates.mm_to_px(*centers[marker_id], dpi)
        canvas[cy - side // 2:cy - side // 2 + side, cx - side // 2:cx - side // 2 + side] = (
            cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
        )

    witnesses = {}
    for slot in page_plan.frames:
        # **L'ordre de dessin est celui de `pdf_render`**: l'image d'abord
        # (`_draw_rect_image`, `pdf_render.py:211`), le contour de zone
        # ensuite (`canvas.rect`, `:223`). L'inverse -- ecrit dans la premiere
        # version -- laissait l'image recouvrir le trait la ou ils se
        # chevauchent, ce qui affaiblissait le test de non-presence du contour
        # exactement la ou il doit mordre.
        ix, iy, iw, ih = slot.image_rect_mm
        x0, y0 = page_templates.mm_to_px(ix, iy, dpi)
        w_px, _ = page_templates.mm_to_px(iw, 0, dpi)
        _, h_px = page_templates.mm_to_px(0, ih, dpi)
        witness = _witness(w_px, h_px, slot.slot_index)
        canvas[y0:y0 + h_px, x0:x0 + w_px] = witness
        witnesses[slot.slot_index] = witness
        if draw_contours:
            zx, zy, zw, zh = slot.zone_rect_mm
            zx0, zy0 = page_templates.mm_to_px(zx, zy, dpi)
            zx1, zy1 = page_templates.mm_to_px(zx + zw, zy + zh, dpi)
            cv2.rectangle(canvas, (zx0, zy0), (zx1 - 1, zy1 - 1), CONTOUR_BGR, 3)
    return canvas, witnesses


def _detect_and_crop(printed: np.ndarray, page_plan, dpi: int):
    """Faire transiter une planche par la detection de 5.2 puis la decoupe."""
    geometry = scan_detection.resolve_page_geometry(page_plan.template_id, dpi)
    markers = scan_detection._detect_markers_document(printed, dpi)["images"][0]["markers"]
    homography, _scale = scan_detection.compute_template_homography(markers, geometry, dpi)
    warped = scan_crop.warp_detected_page(printed, homography, geometry["page_size_px"])
    plan = scan_crop.build_page_crop_plan(
        template_id=page_plan.template_id,
        slots=[
            {"slot_index": slot.slot_index, "frame_timecode": slot.frame_timecode}
            for slot in page_plan.frames
        ],
        dpi=dpi,
    )
    return plan, scan_crop.crop_frames(warped, plan)


@pytest.mark.parametrize(
    ("orientation", "frames_per_page", "preset"),
    [("portrait", 2, "5"), ("paysage", 4, "2"), ("portrait", 1, "0")],
)
def test_a_printed_page_comes_back_as_the_images_that_were_printed(
    orientation: str, frames_per_page: int, preset: str
) -> None:
    """Le coeur de la story: aller-retour impression -> scan -> frames.

    Les temoins sont poses dans les `image_rect_mm` du plan **reel** de
    `pdf_composition`; les frames recuperees doivent etre ces temoins.
    """
    composition = _compose(
        orientation=orientation, frames_per_page=frames_per_page, margin_preset=preset
    )
    page_plan = _images_pages(composition)[0]
    printed, witnesses = _print_page(page_plan, DPI)
    plan, crops = _detect_and_crop(printed, page_plan, DPI)

    assert len(crops) == len(page_plan.frames)
    for frame, crop in zip(plan.frames, crops):
        witness = witnesses[frame.slot_index]
        assert crop.shape == witness.shape
        # La tolerance couvre le reechantillonnage de l'homographie, pas un
        # decalage de rectangle: elle refuse des 2 px (voir `_witness`).
        assert (
            np.abs(crop.astype(int) - witness.astype(int)).mean() < ROUND_TRIP_TOLERANCE
        )


def test_the_round_trip_test_would_catch_a_two_pixel_offset() -> None:
    """Sans ce test, la tolerance de l'aller-retour pourrait etre n'importe quoi.

    On decoupe volontairement a cote et on verifie que l'assertion tombe: c'est
    la seule facon de savoir que le seuil discrimine encore.
    """
    composition = _compose(orientation="portrait", frames_per_page=2, margin_preset="5")
    page_plan = _images_pages(composition)[0]
    printed, witnesses = _print_page(page_plan, DPI)
    plan, _crops = _detect_and_crop(printed, page_plan, DPI)
    frame = plan.frames[0]
    witness = witnesses[frame.slot_index]

    for offset, must_fail in ((0, False), (1, False), (2, True), (92, True)):
        shifted = printed[
            frame.crop_y_px:frame.crop_y_px + frame.height_px,
            frame.crop_x_px + offset:frame.crop_x_px + offset + frame.width_px,
        ]
        gap = float(np.abs(shifted.astype(int) - witness.astype(int)).mean())
        assert (gap >= ROUND_TRIP_TOLERANCE) is must_fail, (offset, gap)


@pytest.mark.parametrize("preset", ["2", "5"])
def test_the_zone_contour_never_enters_the_cropped_frame(preset: str) -> None:
    """Test bloquant de l'AC 2.

    `pdf_render` trace le contour sur `zone_rect_mm` et dessine l'image dans
    `image_rect_mm`: decouper `zone_rect_mm` ferait entrer **le trait** dans la
    frame, en plus de la marge.

    Ne porte que sur les presets `"2"` et `"5"`: au preset `"0"`,
    `frame_image_rect_mm` rend exactement `zone_rect_mm`, donc le trait est pose
    sur la frontiere meme de la decoupe et « aucun pixel temoin » ne peut pas y
    tenir. C'est une propriete du preset, pas un defaut d'implementation.
    """
    composition = _compose(orientation="portrait", frames_per_page=2, margin_preset=preset)
    page_plan = _images_pages(composition)[0]
    printed, _witnesses = _print_page(page_plan, DPI)
    _plan, crops = _detect_and_crop(printed, page_plan, DPI)

    for crop in crops:
        red = (crop[..., 2] > 220) & (crop[..., 0] < 60) & (crop[..., 1] < 60)
        assert not red.any(), f"{int(red.sum())} pixels de contour dans la frame"


def test_the_printed_page_really_carries_the_contour_witness() -> None:
    # Le pendant du test precedent: sans lui, « aucun pixel rouge » serait
    # satisfait par une page qui n'en a jamais porte.
    composition = _compose(orientation="portrait", frames_per_page=2, margin_preset="5")
    printed, _witnesses = _print_page(_images_pages(composition)[0], DPI)
    red = (printed[..., 2] > 220) & (printed[..., 0] < 60) & (printed[..., 1] < 60)
    assert red.sum() > 1000, "la planche temoin ne porte pas de contour"


def test_cropping_the_zone_instead_of_the_image_would_catch_the_contour() -> None:
    """La preuve que le test precedent discrimine vraiment.

    Si la decoupe portait sur `zone_rect_mm`, le trait entrerait: on le verifie
    en decoupant volontairement le mauvais rectangle.
    """
    composition = _compose(orientation="portrait", frames_per_page=2, margin_preset="5")
    page_plan = _images_pages(composition)[0]
    printed, _witnesses = _print_page(page_plan, DPI)
    slot = page_plan.frames[0]
    zx, zy, zw, zh = slot.zone_rect_mm
    x0, y0 = page_templates.mm_to_px(zx, zy, DPI)
    w_px, _ = page_templates.mm_to_px(zw, 0, DPI)
    _, h_px = page_templates.mm_to_px(0, zh, DPI)
    wrong = printed[y0:y0 + h_px, x0:x0 + w_px]
    red = (wrong[..., 2] > 220) & (wrong[..., 0] < 60) & (wrong[..., 1] < 60)
    assert red.any(), "le temoin de contour ne discrimine rien"


def test_letterbox_bands_survive_the_round_trip_untouched() -> None:
    """AC 7 / EPIC5-ARB-1: les bandes appartiennent a l'image, pas a la marge.

    Une zone 16:9 imprimee depuis un rush 4:3 contient des bandes, posees a
    l'impression **a l'interieur** de `image_rect_mm`. Cette story ne les
    detecte pas, ne resserre pas le rectangle et ne devine aucun ratio: la frame
    ressort avec ses bandes et ses dimensions inchangees.

    Le temoin est **blanc** et non noir: `drawImage` inscrit l'image dans la
    boite sans peindre de fond, donc les bandes ressortent au fond de page.
    """
    composition = _compose(orientation="portrait", frames_per_page=2, margin_preset="5")
    page_plan = _images_pages(composition)[0]
    spec = page_templates.get_template(page_plan.template_id)
    slot = page_plan.frames[0]

    printed, _witnesses = _print_page(page_plan, DPI, draw_contours=False)
    ix, iy, iw, ih = slot.image_rect_mm
    x0, y0 = page_templates.mm_to_px(ix, iy, DPI)
    w_px, _ = page_templates.mm_to_px(iw, 0, DPI)
    _, h_px = page_templates.mm_to_px(0, ih, DPI)
    # Un 4:3 inscrit dans la boite 16:9: bandes laterales au blanc de page.
    inner_w = int(round(h_px * 4 / 3))
    printed[y0:y0 + h_px, x0:x0 + w_px] = 255
    printed[y0:y0 + h_px, x0 + (w_px - inner_w) // 2:x0 + (w_px - inner_w) // 2 + inner_w] = (
        _witness(inner_w, h_px, 1)
    )

    plan, crops = _detect_and_crop(printed, page_plan, DPI)
    crop = crops[0]
    assert crop.shape[:2] == (plan.frames[0].height_px, plan.frames[0].width_px)
    # `abs=0.01` sur le rapport laissait passer +/- 4 px de hauteur: on fige la
    # dimension elle-meme, arrondi de la recette compris.
    assert crop.shape[1] == w_px and crop.shape[0] == h_px
    assert crop.shape[1] / crop.shape[0] == pytest.approx(16 / 9, abs=0.002), (
        "la frame doit rester 16:9, bandes comprises"
    )
    # Les bandes sont toujours la, au blanc de page.
    assert crop[crop.shape[0] // 2, 2].min() > 200
    assert crop[crop.shape[0] // 2, -3].min() > 200
    assert spec.margin_mm == 5.0


def test_the_module_never_inspects_the_pixels_to_choose_its_rectangle() -> None:
    """Le piege 5, ferme par AST plutot que par une liste de noms inventes.

    Interdire quatre identifiants qui n'existent nulle part dans le depot ne
    protege de rien. Ce qui protege, c'est qu'aucune fonction d'analyse
    d'image n'entre dans le module: un resserrement sur le contenu passerait
    forcement par l'une d'elles.
    """
    import ast

    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"), filename=str(MODULE_PATH))
    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    forbidden = {
        "threshold", "findContours", "boundingRect", "nonzero", "argwhere",
        "countNonZero", "inRange", "reduce", "any", "all", "mean", "std",
    }
    assert not (called & forbidden), sorted(called & forbidden)
    # Le rectangle ne depend que du template et du DPI: aucune fonction du
    # module ne prend la page en parametre pour decider ou couper.
    import inspect

    for name in ("crop_rect_px", "build_page_crop_plan"):
        parameters = inspect.signature(getattr(scan_crop, name)).parameters
        assert not any(
            candidate in parameters
            for candidate in ("image", "page", "warped_page", "pixels")
        ), name


# --- AC 10: le chemin POC reste intact ---------------------------------------


def test_the_poc_extraction_never_learned_about_margins() -> None:
    """`extract_scan_frames` decoupe `layout.FRAME_ZONES_MM` sans marge, et sa
    geometrie de zone est fausse pour 30 gabarits sur 33.

    « Juste ajouter la marge » y donnerait un crop faux avec une marge juste.
    La nouvelle decoupe coexiste sous un nom distinct.
    """
    source = ARUCO_PATH.read_text(encoding="utf-8")
    assert "frame_image_rect_mm" not in source
    assert "margin_mm" not in source
    assert "FRAME_ZONES_MM" in source, "le chemin POC garde sa geometrie d'origine"


def test_the_poc_extraction_signature_is_untouched() -> None:
    import hashlib
    import inspect

    from mixed_media_utility.detection import aruco as aruco_detection

    assert list(inspect.signature(aruco_detection.extract_scan_frames).parameters) == [
        "warped_page", "dpi", "output_dir",
    ]
    # Les noms de parametres ne verrouillent pas le corps: un `extract_scan_frames`
    # entierement reecrit les garderait. On fige donc l'empreinte du **source**
    # de la fonction, que 5.3 n'a aucune raison de toucher.
    digest = hashlib.sha256(
        inspect.getsource(aruco_detection.extract_scan_frames).encode("utf-8")
    ).hexdigest()
    assert digest == "04ffb7fc9abc2046d9b5ed19ed44b7c58202196806df5dbc2a8d127de9335399"


# --- AC 9: frontieres tenues --------------------------------------------------


def test_the_story_boundaries_are_locked_by_a_test() -> None:
    out_of_scope = (
        "export_frame_tiff16",          # 5.6: export
        "build_frame_filename",         # 5.6: nommage
        "build_extracted_frame_filename",
        "persist_extraction",           # 5.7
        "request_active_calibration",   # 5.4
        "apply_active_calibration",  # 5.4b: nouveau nom du meme contrat.
        # Les DEUX noms restent interdits ici. L'ancien parce qu'il ne doit
        # pas reapparaitre, le nouveau parce que la garde ne gardait plus rien
        # apres le renommage de la story 5.4b: un symbole absent du depot est
        # trivialement absent du module, et le test passait sans rien verifier.
        "reconstruct_project_manifest", # 5.7
    )
    source = MODULE_PATH.read_text(encoding="utf-8")
    present = [symbol for symbol in out_of_scope if symbol in source]
    assert present == [], f"symboles hors perimetre de 5.3: {present}"


def test_the_module_writes_nothing() -> None:
    """« N'ecrit aucun fichier » verrouille par AST, pas par un grep d'`imwrite`.

    Une ecriture reelle -- `open(..., "w")`, `Path.write_bytes`, un `savefig` --
    passait le grep. Ici on interdit toute la famille.
    """
    import ast

    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"), filename=str(MODULE_PATH))
    forbidden_names = {"open", "print"}
    forbidden_attributes = {
        "imwrite", "write", "write_text", "write_bytes", "writelines", "savefig",
        "mkdir", "unlink", "rename", "touch", "dump", "save", "tofile",
    }
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            assert node.func.id not in forbidden_names, node.func.id
        if isinstance(node.func, ast.Attribute):
            assert node.func.attr not in forbidden_attributes, node.func.attr
    # Et aucun import de module d'ecriture.
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert not (imported & {"shutil", "os", "tempfile"}), sorted(imported)


def test_the_plan_carries_no_pixel() -> None:
    text = scan_crop.plan_json(plan_for("tpl-a4-paysage-8f-m2-v1"))
    assert "base64" not in text and len(text) < 20000
    assert json.loads(text)["fingerprint"].startswith(scan_crop.FINGERPRINT_PREFIX)


@pytest.mark.parametrize(
    ("template_id", "dpi", "expected"),
    [
        (PORTRAIT_2F_M5, 600, (2887, 1624)),
        (PORTRAIT_2F_M0, 600, (3307, 1860)),
        ("tpl-a4-paysage-4f-v1", 600, (1638, 921)),
        ("tpl-a4-portrait-8f-m5-v1", 600, (1024, 576)),
        ("tpl-a4-paysage-8f-m2-v1", 600, (842, 474)),
        # 1444 et non 1443: la largeur est quantifiee **depuis les
        # millimetres** (122,222 mm -> 1443,7 -> 1444), pas en divisant la
        # valeur a 600 ppp par deux. La difference est precisement ce que ce
        # test verrouille.
        (PORTRAIT_2F_M5, 300, (1444, 812)),
    ],
)
def test_the_frame_dimensions_are_pinned_by_value(template_id, dpi, expected) -> None:
    """Rien n'etait fige par valeur: un mutant « +1 px au-dela de 500 ppp »
    survivait a la suite entiere.

    Ces couples sont recalculables a la main depuis le registre; les figer rend
    visible tout glissement d'arrondi, y compris celui qui ne se verrait a
    aucune resolution testee ailleurs.
    """
    plan = plan_for(template_id, dpi=dpi)
    assert (plan.frames[0].width_px, plan.frames[0].height_px) == expected


def test_the_crop_origin_is_pinned_by_value() -> None:
    # La taille seule ne verrouille pas la position: un decalage uniforme de
    # toutes les origines la laisserait intacte.
    plan = plan_for(PORTRAIT_2F_M5, dpi=600)
    assert [(f.crop_x_px, f.crop_y_px) for f in plan.frames] == [
        (1037, 1535), (1037, 3632),
    ]


def test_the_fingerprint_changes_when_the_plan_changes() -> None:
    """Le mutant « empreinte constante pour tous les plans » survivait.

    Une empreinte qui ne varie pas ne signe rien: c'est le seul verrou que
    5.6 et 5.8 auront pour dire que deux plans different.
    """
    reference = scan_crop.plan_document(plan_for(PORTRAIT_2F_M5))["fingerprint"]
    assert reference == scan_crop.plan_document(plan_for(PORTRAIT_2F_M5))["fingerprint"]
    for other in (
        plan_for(PORTRAIT_2F_M5, dpi=600),
        plan_for(PAYSAGE_4F_M2),
        plan_for(PORTRAIT_2F_M5, slots=slots_for(2, first=9)),
        plan_for(PORTRAIT_2F_M5, slots=slots_for(1)),
    ):
        assert scan_crop.plan_document(other)["fingerprint"] != reference


def test_the_document_publishes_the_image_rect_not_the_zone_rect() -> None:
    """Le mutant qui echange les deux dans la serialisation survivait.

    Le plan est ce que 5.6 et 5.8 consomment: publier `zone_rect_mm` sous le
    nom `image_rect_mm` leur ferait redecouper la marge et le contour.
    """
    spec = page_templates.get_template(PORTRAIT_2F_M5)
    zone = spec.frame_zones_mm[0]
    frame = scan_crop.plan_document(plan_for(PORTRAIT_2F_M5))["frames"][0]
    assert frame["image_rect_mm"] == [
        round(value, 6) for value in page_templates.frame_image_rect_mm(zone, spec.margin_mm)
    ]
    assert frame["zone_rect_mm"] == [zone["x"], zone["y"], zone["width"], zone["height"]]
    assert frame["image_rect_mm"] != frame["zone_rect_mm"]


def test_the_document_keeps_enough_decimals_to_be_reconstructible() -> None:
    # `image_rect_mm` porte des tiers de millimetre (43.888...): arrondir a une
    # decimale ferait perdre 0,04 mm, soit un pixel a 600 ppp -- et le mutant
    # qui le faisait survivait.
    frame = scan_crop.plan_document(plan_for(PORTRAIT_2F_M5))["frames"][0]
    assert frame["image_rect_mm"][0] == pytest.approx(43.888889, abs=1e-6)
    assert frame["image_rect_mm"][2] == pytest.approx(122.222222, abs=1e-6)


def test_the_document_frame_count_matches_the_frames_it_carries() -> None:
    document = scan_crop.plan_document(plan_for(PAYSAGE_4F_M2, slots=slots_for(3)))
    assert document["frame_count"] == len(document["frames"]) == 3


def test_the_plan_document_shape_is_pinned() -> None:
    # Ce plan est ce que 5.6 et 5.8 consommeront: un champ renomme en silence
    # les casserait toutes les deux, mais seulement a l'execution.
    document = scan_crop.plan_document(plan_for(PORTRAIT_2F_M5))
    assert set(document) == {
        "template_id", "dpi", "page_size_px", "frame_count", "unused_zones",
        "warnings", "frames", "fingerprint",
    }
    assert set(document["frames"][0]) == {
        "slot_index", "frame_timecode", "zone_name", "zone_rect_mm",
        "image_rect_mm", "crop_x_px", "crop_y_px", "width_px", "height_px",
    }


def test_an_unknown_warning_code_is_refused() -> None:
    with pytest.raises(ValueError):
        scan_crop.validate_warning_code("ZONE_UN_PEU_VIDE")
    for code in scan_crop.SCAN_CROP_WARNING_CODES:
        assert scan_crop.validate_warning_code(code) == code


def test_the_crop_vocabulary_is_distinct_from_its_neighbours() -> None:
    from mixed_media_utility import scan_ingest

    assert not (set(scan_crop.SCAN_CROP_WARNING_CODES) & set(scan_ingest.SCAN_INGEST_WARNING_CODES))
    assert not (
        set(scan_crop.SCAN_CROP_WARNING_CODES)
        & set(scan_detection.SCAN_DETECTION_WARNING_CODES)
    )


def test_the_crop_tolerance_is_declared_at_zero_with_its_motive() -> None:
    # Question ouverte 2: la constante existe pour que le pilote papier puisse
    # la calibrer, pas pour rester a zero par oubli.
    assert scan_crop.CROP_TOLERANCE_PX == 0
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "pilote papier" in source
