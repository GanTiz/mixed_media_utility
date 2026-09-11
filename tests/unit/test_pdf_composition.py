"""Tests de la composition pure des planches PDF (story 4.1).

La composition calcule le plan de page complet (zones de frames, QR, ArUco,
patchs, texte) sans aucune ecriture ni reportlab. Le registre de templates
(`page_templates`) est le resolveur `template_id -> geometrie` que le contrat
4.5 exige; la grille de zones est calculee par couple orientation x cardinal
(EPIC4-ARB-1), 16:9 exact, jamais d'etirement anisotrope.

Le non-chevauchement est verifie globalement (frames + marqueurs + QR +
patchs + texte), symetriquement au test 4.7 -- contre les constantes reelles
de `layout.py`, jamais des valeurs recopiees.
"""

from __future__ import annotations

import ast
import dataclasses
import sys
from datetime import date
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from reportlab.lib.units import mm

from mixed_media_utility import (
    layout,
    page_templates,
    patch_presets,
    pdf_composition,
    pdf_render,
    qr_codes,
)
from mixed_media_utility.io import naming
from mixed_media_utility.io import payload as payload_io
from mixed_media_utility.io.payload import (
    ALERT_BUDGET_BYTES,
    NOMINAL_BUDGET_BYTES,
    PayloadBudgetExceeded,
    parse_payload,
)
from mixed_media_utility import page_payload
from mixed_media_utility.page_payload import WARNING_OVER_NOMINAL_BUDGET

COMPOSITION_PATH = REPO_ROOT / "src" / "mixed_media_utility" / "pdf_composition.py"
TEMPLATES_PATH = REPO_ROOT / "src" / "mixed_media_utility" / "page_templates.py"


# ---------------------------------------------------------------------------
# Fixture manifest pur (aucun disque): rush 25 im/s, lot 5 im/s, 50 frames
# sources -> 10 frames extraites.
# ---------------------------------------------------------------------------


def make_manifest(
    *,
    project_id: str = "proj-a",
    rush_id: str = "rush-001",
    fps_source: float = 25.0,
    fps_target: float = 5.0,
    source_frame_count: int = 50,
    target_colorspace: str | None = "rec709",
    # Story 2.7 (payload 2.1, EPIC7-ARB-56): la cadence SOURCE du rush, deja
    # ecrite par l'extraction reelle sur ce meme champ -- defaut derive de
    # `fps_source`, meme recette que `fps_source_exact` juste en dessous.
    timecode_base_fps: str | None = None,
) -> dict:
    lot_id = naming.build_lot_id(rush_id, fps_target)
    if timecode_base_fps is None:
        timecode_base_fps = f"{int(fps_source)}/1"
    manifest = {
        "schema_version": "2.1",
        "project_id": project_id,
        "created": "2026-08-06T00:00:00Z",
        "rushes": [
            {
                "rush_id": rush_id,
                "source_name": f"{rush_id}.mov",
                "fps_source": fps_source,
                "fps_source_exact": f"{int(fps_source)}/1",
                "resolution_source": {"width": 1920, "height": 1080},
            }
        ],
        "lots": [
            {
                "lot_id": lot_id,
                "rush_id": rush_id,
                "state": "extraction",
                "fps_target": fps_target,
                "fps_target_exact": f"{int(fps_target)}/1",
                "timecode_base_fps": timecode_base_fps,
                "expected_frame_count": source_frame_count
                * int(fps_target)
                // int(fps_source),
                "frames_dir": f"frames/{naming.derive_short_id(rush_id)}_"
                f"{naming.format_fps_short(fps_target)}",
                "source_frame_count": source_frame_count,
                "source_frame_count_is_exact": True,
                "rounding_policy": "floor",
            }
        ],
        "artifacts": {"frames_dir": "frames"},
        "color": {},
        "video": {},
        "reconstruction": {},
    }
    if target_colorspace is not None:
        manifest["color"]["target_colorspace"] = target_colorspace
    return manifest


def compose(manifest=None, **kwargs):
    manifest = manifest if manifest is not None else make_manifest()
    lot_id = kwargs.pop("lot_id", manifest["lots"][0]["lot_id"])
    return pdf_composition.compose_lot_plan(manifest=manifest, lot_id=lot_id, **kwargs)


#: Libelle de chaine et date de generation des fabriques de ce fichier.
#:
#: **Deux chaines distinguables** sont posees plutot qu'une, regle des fabriques: le
#: nom du fichier et le QR portent tous deux le libelle depuis 5.23, donc une fabrique
#: mono-chaine rendrait invisible un nom de fichier qui ignorerait le libelle. La date
#: est **figee**: la composition doit etre reproductible, et une horloge dans une
#: fabrique rendrait un plan different a chaque execution.
CHAINE_DE_TEST = "hp envy 4520 tiff 600 dpi auto corr off"
AUTRE_CHAINE_DE_TEST = "epson v600 tiff 48 bits 1200 dpi corr auto off"
DATE_DE_TEST = date(2026, 8, 18)


def compose_calibration(manifest=None, **kwargs):
    """Le plan de la **page de calibration seule**, generee a la demande (story 5.22).

    Contrepartie de `compose` depuis que la page n'est plus inseree dans le lot
    (`EPIC5-ARB-80`, decision 7): tout test qui parle de la page de calibration la
    compose **explicitement** au lieu de la pecher dans `plan.pages`. C'est le geste que
    l'operateur fait desormais, donc c'est celui que les tests doivent faire.
    """
    manifest = manifest if manifest is not None else make_manifest()
    # AMENDE PAR 5.23 (2026-08-18): plus de `lot_id`. Une page de calibration se genere
    # **avant tout lot**, elle sert toute une chaine de scan, et son gabarit n'a jamais
    # ete resolu par le lot. Le libelle de chaine, lui, devient obligatoire: une page
    # anonyme ne se distinguerait pas d'une autre.
    kwargs.pop("lot_id", None)
    kwargs.setdefault("scan_chain_label", CHAINE_DE_TEST)
    kwargs.setdefault("generated_on", DATE_DE_TEST)
    return pdf_composition.compose_calibration_page_plan(manifest=manifest, **kwargs)


def images_pages(plan):
    """Les **planches d'images** d'un plan de lot.

    Depuis la story 5.22 (`EPIC5-ARB-80`, decision 7), un plan de lot ne porte **plus
    que** des planches d'images: la page de calibration n'est plus inseree a l'index 0,
    elle est generee a la demande par `compose_calibration_page_plan`. Ce filtre est donc
    aujourd'hui l'identite sur un plan de lot.

    **Il est conserve, et ce n'est pas de la dette**: il porte l'invariant « une planche
    d'images porte au moins une frame », que la story 5.16 avait rendu invisible en
    melangeant les deux natures de page dans la meme suite. Un plan de lot dont une page
    ressortirait sans frame passerait aujourd'hui inapercu si les tests iteraient
    `plan.pages` -- ici, il fait chuter le cardinal, et c'est ce que les tests de
    pagination asservissent.
    """
    return [page for page in plan.pages if page.frames]


def calibration_page(plan):
    """La page de calibration d'un plan **de page de calibration** (story 5.22).

    Le plan rendu par `compose_calibration_page_plan` porte exactement une page, sans
    frame. La fonction garde sa forme defensive d'avant la story: elle refuse d'en
    trouver deux, et rend `None` quand il n'y en a aucune -- c'est ce qui fait echouer,
    plutot que passer silencieusement, un test qui l'appellerait sur un plan de lot.
    """
    pages = [page for page in plan.pages if not page.frames]
    assert len(pages) <= 1, "un plan porte au plus une page de calibration"
    return pages[0] if pages else None


def rects_overlap(a, b) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


# ---------------------------------------------------------------------------
# AC 2: registre de templates, vocabulaire ferme, grilles calculees
# ---------------------------------------------------------------------------


def test_template_vocabulary_follows_arb_1() -> None:
    assert page_templates.FRAMES_PER_PAGE_VOCABULARY["portrait"] == (1, 2, 3, 4, 6, 8)
    assert page_templates.FRAMES_PER_PAGE_VOCABULARY["paysage"] == (1, 2, 4, 6, 8)
    assert page_templates.DEFAULT_FRAMES_PER_PAGE == 2
    assert page_templates.PAGE_FORMATS == ("A4",)
    margins = len(page_templates.MARGIN_PRESETS_MM)
    # Une version de geometrie **ajoute** des identifiants et n'en redefinit aucun
    # (story 5.15). Depuis la story 5.18 elle peut aussi en **retirer**: un cardinal
    # dont le gain par frame est negligeable sort du vocabulaire de la version ou la
    # mesure le constate (`EPIC5-ARB-62`), et de celle-la seulement. Le cardinal
    # d'identifiants se compte donc **par version**, jamais globalement -- un total
    # ecrit en `couples x marges x versions` masquerait exactement ce retrait.
    versions = len(page_templates.GEOMETRY_VERSIONS)
    assert versions >= 2
    expected = 0
    for version in page_templates.GEOMETRY_VERSIONS:
        couples = sum(
            len(page_templates.frames_per_page_vocabulary(orientation, version))
            for orientation in page_templates.ORIENTATIONS
        )
        per_version = [t for t in page_templates.known_template_ids()
                       if t.endswith(f"-{version}")]
        assert len(per_version) == couples * margins, version
        expected += couples * margins
    assert len(page_templates.known_template_ids()) == expected
    # Et le retrait est bien un **retrait**: la v1 porte les 11 gabarits historiques, la
    # v2 en porte **un** de moins -- le 6f **portrait** seul, le 6f paysage etant reste
    # offert par `EPIC5-ARB-64` (il rend +81,9 % de surface par frame de plus que le 8f,
    # c'est-a-dire l'inverse d'un barreau degenere). Le chiffre etait 9 entre la story
    # 5.18 et cet amendement.
    assert sum(len(page_templates.frames_per_page_vocabulary(o, "v1"))
               for o in page_templates.ORIENTATIONS) == 11
    assert sum(len(page_templates.frames_per_page_vocabulary(o, "v2"))
               for o in page_templates.ORIENTATIONS) == 10
    assert page_templates.frames_per_page_vocabulary("portrait", "v2") == (1, 2, 3, 4, 8)
    assert page_templates.frames_per_page_vocabulary("paysage", "v2") == (1, 2, 4, 6, 8)


def test_portrait_2f_template_id_is_the_historic_47_identifier() -> None:
    # L'identifiant historique est un identifiant **v1**, et le defaut a bascule sur la
    # v2 a la livraison de la passe de design (story 5.18, AC 11): l'appel sans version
    # ne rend donc plus l'identifiant historique. Ce qui doit rester vrai dans les deux
    # regimes, et ce que ce test verrouille, c'est que la version **nommee** decide
    # seule -- un identifiant v2 ne redefinit jamais l'identifiant historique, il
    # s'ajoute a cote, et l'historique reste resolvable pour toujours.
    template_id = page_templates.build_template_id(
        "portrait", 2, page_templates.DEFAULT_MARGIN_PRESET, "v1"
    )
    assert template_id == patch_presets.TEMPLATE_A4_PORTRAIT_2F
    assert template_id == page_templates.TEMPLATE_A4_PORTRAIT_2F
    assert page_templates.get_template(template_id).geometry_version == "v1"
    default_id = page_templates.build_template_id(
        "portrait", 2, page_templates.DEFAULT_MARGIN_PRESET
    )
    assert default_id == "tpl-a4-portrait-2f-v2"
    assert default_id != template_id
    # Et l'historique reste resolvable apres la bascule: c'est la seule facon de
    # rescanner une planche imprimee avant elle.
    assert page_templates.get_template(template_id).template_id == template_id
    tightened_id = page_templates.build_template_id(
        "portrait", 2, page_templates.DEFAULT_MARGIN_PRESET, "v2"
    )
    assert tightened_id == "tpl-a4-portrait-2f-v2"
    assert tightened_id != template_id


def test_template_ids_are_canonical_and_versioned() -> None:
    suffixes = set()
    for template_id in page_templates.known_template_ids():
        assert naming.normalize_identifier(template_id) == template_id
        version = page_templates.get_template(template_id).geometry_version
        # Le suffixe **est** la version resolue: un identifiant dont le suffixe et la
        # geometrie divergeraient serait le pire des deux mondes -- il aurait l'air
        # versionne et resoudrait autre chose.
        assert template_id.endswith(f"-{version}"), template_id
        assert version in page_templates.GEOMETRY_VERSIONS
        suffixes.add(version)
    assert suffixes == set(page_templates.GEOMETRY_VERSIONS)


def test_portrait_2f_zones_match_layout_exactly() -> None:
    # La geometrie eprouvee (4.3/4.6) reste la source de verite: le template
    # historique doit rendre exactement les zones de layout.py.
    spec = page_templates.get_template(page_templates.TEMPLATE_A4_PORTRAIT_2F)
    assert spec.page_width_mm == layout.PAGE_WIDTH_MM
    assert spec.page_height_mm == layout.PAGE_HEIGHT_MM
    assert len(spec.frame_zones_mm) == len(layout.FRAME_ZONES_MM)
    for zone, reference in zip(spec.frame_zones_mm, layout.FRAME_ZONES_MM):
        assert zone["name"] == reference["name"]
        for key in ("x", "y", "width", "height"):
            assert abs(zone[key] - reference[key]) < 1e-9, (zone["name"], key)


def test_paysage_page_dimensions_are_swapped_a4() -> None:
    spec = page_templates.get_template(
        page_templates.build_template_id("paysage", 2, "0")
    )
    assert spec.page_width_mm == layout.PAGE_HEIGHT_MM
    assert spec.page_height_mm == layout.PAGE_WIDTH_MM


def test_portrait_corner_centers_match_layout() -> None:
    spec = page_templates.get_template(page_templates.TEMPLATE_A4_PORTRAIT_2F)
    assert page_templates.corner_marker_centers_mm(spec) == layout.corner_marker_centers_mm()


def test_marker_geometry_constants_mirror_layout() -> None:
    # page_templates est pur (pas d'import de layout, qui tire cv2): ses
    # constantes miroir doivent rester identiques aux constantes normatives.
    assert page_templates.MARKER_SIZE_MM == layout.MARKER_SIZE_MM
    assert page_templates.MARKER_MARGIN_MM == layout.MARKER_MARGIN_MM
    assert page_templates.MARKER_QUIET_ZONE_MM == layout.MARKER_QUIET_ZONE_MM
    assert page_templates.PRINTER_MARGIN_MM == layout.PRINTER_MARGIN_MM
    assert page_templates.A4_SHORT_SIDE_MM == layout.PAGE_WIDTH_MM
    assert page_templates.A4_LONG_SIDE_MM == layout.PAGE_HEIGHT_MM


def test_every_template_grid_is_exact_16_9_inside_the_frame_band() -> None:
    for template_id in page_templates.known_template_ids():
        spec = page_templates.get_template(template_id)
        assert len(spec.frame_zones_mm) == spec.frames_per_page
        # La bande **du gabarit**: depuis la v2 elle depend aussi du cardinal (le
        # placement des temoins se mesure), donc la recalculer par orientation seule
        # confronterait les zones a une autre bande que celle qui les a produites.
        band = spec.frame_band_mm
        rects = []
        for zone in spec.frame_zones_mm:
            # 16:9 exact, jamais d'etirement anisotrope (EPIC4-ARB-1).
            assert abs(zone["width"] * 9 - zone["height"] * 16) < 1e-6, template_id
            assert zone["x"] >= band["x"] - 1e-9
            assert zone["y"] >= band["y"] - 1e-9
            assert zone["x"] + zone["width"] <= band["x"] + band["width"] + 1e-9
            assert zone["y"] + zone["height"] <= band["y"] + band["height"] + 1e-9
            rects.append((zone["x"], zone["y"], zone["width"], zone["height"]))
        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                assert not rects_overlap(rects[i], rects[j]), template_id


def test_grid_shapes_maximize_drawing_surface() -> None:
    # Verification par points de controle des grilles calculees (EPIC4-ARB-1).
    def zone_width(orientation, cardinal, version="v1"):
        spec = page_templates.get_template(
            page_templates.build_template_id(orientation, cardinal, "0", version)
        )
        return spec.frame_zones_mm[0]["width"]

    # Points de controle de la **v1**, nommee explicitement: ces largeurs sont celles
    # des planches deja imprimees, et la story 5.15 les epingle en dur par ailleurs.
    assert abs(zone_width("portrait", 2) - 140.0) < 1e-9
    assert abs(zone_width("portrait", 4) - 65.0) < 1e-9
    assert zone_width("portrait", 3) > 80.0  # colonne unique, pas une grille 2x2
    assert zone_width("paysage", 1) > 150.0
    assert zone_width("paysage", 8) > 40.0
    # La v2 elargit toutes les zones -- c'est l'objet du resserrement -- et la
    # comparaison porte sur les deux versions pour que le test ne devienne pas muet
    # sur la geometrie effectivement livree par defaut.
    for orientation, cardinal in (("portrait", 2), ("paysage", 8)):
        assert zone_width(orientation, cardinal, "v2") > zone_width(
            orientation, cardinal, "v1"), (orientation, cardinal)


def test_frame_zones_do_not_depend_on_margin_preset() -> None:
    # La marge est un recadrage interieur (5.3): la zone imprimee est
    # identique, seule la surface utile de l'image change.
    for orientation, cardinal in (("portrait", 2), ("paysage", 4)):
        zones = [
            page_templates.get_template(
                page_templates.build_template_id(orientation, cardinal, margin)
            ).frame_zones_mm
            for margin in page_templates.MARGIN_PRESETS_MM
        ]
        assert zones[0] == zones[1] == zones[2]


def test_frame_image_rect_is_inset_16_9_and_centered() -> None:
    zone = {"name": "z", "x": 35.0, "y": 60.0, "width": 140.0, "height": 78.75}
    full = page_templates.frame_image_rect_mm(zone, 0.0)
    assert full == (35.0, 60.0, 140.0, 78.75)

    inset = page_templates.frame_image_rect_mm(zone, 2.0)
    x, y, w, h = inset
    assert abs(w * 9 - h * 16) < 1e-9
    assert x >= zone["x"] + 2.0 - 1e-9 and y >= zone["y"] + 2.0 - 1e-9
    assert x + w <= zone["x"] + zone["width"] - 2.0 + 1e-9
    assert y + h <= zone["y"] + zone["height"] - 2.0 + 1e-9
    # Centre conserve.
    assert abs((x + w / 2) - (zone["x"] + zone["width"] / 2)) < 1e-9
    assert abs((y + h / 2) - (zone["y"] + zone["height"] / 2)) < 1e-9


def test_unknown_template_is_an_explicit_error() -> None:
    with pytest.raises(page_templates.UnknownTemplateError) as excinfo:
        page_templates.get_template("tpl-a4-portrait-99f-v1")
    assert "tpl-a4-portrait-99f-v1" in str(excinfo.value)


# ---------------------------------------------------------------------------
# AC 2: vocabulaire CLI ferme, chaque refus teste
# ---------------------------------------------------------------------------


def test_invalid_frames_per_page_is_refused_naming_the_vocabulary() -> None:
    with pytest.raises(pdf_composition.ParameterVocabularyError) as excinfo:
        compose(orientation="portrait", frames_per_page=5)
    message = str(excinfo.value)
    assert "5" in message
    for allowed in (1, 2, 3, 4, 8):
        assert str(allowed) in message
    # Le vocabulaire annonce est celui de la **version composee**, jamais l'union: en v2
    # le cardinal 6 est retire, et l'annoncer comme accepte enverrait l'operateur
    # composer un `template_id` qui n'existe pas.
    assert "geometrie v2" in message
    assert " 6" not in message.replace("EPIC4-ARB-1", "")
    # En v1 il reste dans le vocabulaire annonce.
    with pytest.raises(pdf_composition.ParameterVocabularyError) as v1_refus:
        compose(orientation="portrait", frames_per_page=5, geometry_version="v1")
    assert "6" in str(v1_refus.value)


def test_frames_per_page_3_is_refused_in_paysage_only() -> None:
    # Vocabulaire dependant de l'orientation (EPIC4-ARB-1).
    compose(orientation="portrait", frames_per_page=3)
    with pytest.raises(pdf_composition.ParameterVocabularyError):
        compose(orientation="paysage", frames_per_page=3)


def test_invalid_orientation_and_format_are_refused() -> None:
    with pytest.raises(pdf_composition.ParameterVocabularyError):
        compose(orientation="inverse")
    with pytest.raises(pdf_composition.ParameterVocabularyError):
        compose(page_format="A3")


def test_invalid_margin_preset_is_refused_naming_the_presets() -> None:
    with pytest.raises(pdf_composition.ParameterVocabularyError) as excinfo:
        compose(margin_preset="3.5")
    message = str(excinfo.value)
    for preset in page_templates.MARGIN_PRESETS_MM:
        assert preset in message


def test_patch_preset_resolves_by_cardinal_or_id() -> None:
    by_cardinal = compose(patch_preset="9")
    assert by_cardinal.patch_preset_id == "patches-9-v1"
    by_id = compose(patch_preset="patches-12-v1")
    assert by_id.patch_preset_id == "patches-12-v1"


def test_unknown_patch_preset_is_refused_naming_available_presets() -> None:
    with pytest.raises(pdf_composition.ParameterVocabularyError) as excinfo:
        compose(patch_preset="7")
    message = str(excinfo.value)
    for preset_id in patch_presets.known_preset_ids():
        assert preset_id in message


def test_render_dpi_low_bound_is_refused() -> None:
    with pytest.raises(pdf_composition.ParameterVocabularyError):
        compose(render_dpi=100)


def test_render_dpi_that_starves_the_qr_raster_is_refused() -> None:
    # ~8 px/module minimum dans le PDF (Dev Notes DPI): 300 dpi rasterise le
    # QR nominal sous ce seuil, le refus nomme --dpi.
    with pytest.raises(pdf_composition.GeometryOverflowError) as excinfo:
        compose(render_dpi=300)
    assert "--dpi" in str(excinfo.value)


# ---------------------------------------------------------------------------
# AC 3 / AC 4: plan de page complet, pagination, contenu du manifest
# ---------------------------------------------------------------------------


def test_default_composition_paginates_at_2_frames_per_page() -> None:
    plan = compose()
    assert plan.frames_per_page == 2
    # **5 a nouveau depuis la story 5.22**, apres le 6 de 5.16: le lot ne porte plus de
    # page de calibration inseree a l'index 0 (`EPIC5-ARB-80`, decision 7), donc
    # `page_count` redevient `ceil(frames / frames_par_page)` et rien de plus. Ce n'est
    # pas un revirement d'esthetique: la calibration devient **par chaine de scan**, donc
    # la page cesse d'appartenir a l'espace d'index d'un lot.
    assert plan.page_count == 5
    assert len(plan.pages) == 5
    # Les index restent en base zero et continus.
    for page_index, page in enumerate(plan.pages):
        assert page.page_index == page_index  # base zero (convention 3.1)
    # **Frontiere negative de l'AC 8**: plus aucune page sans frame dans un plan de lot.
    # C'est ce qui distingue « la page n'est plus inseree » de « la page est inseree mais
    # les tests ne la regardent plus ».
    assert calibration_page(plan) is None
    assert len(images_pages(plan)) == 5
    for page in images_pages(plan):
        assert len(page.frames) == 2


def test_last_page_carries_the_remainder_never_an_empty_page() -> None:
    plan = compose(frames_per_page=4)
    # ceil(10 / 4) depuis la story 5.22 (c'etait 1 + ceil(...) entre 5.16 et 5.22).
    assert plan.page_count == 3
    assert [len(page.frames) for page in images_pages(plan)] == [4, 4, 2]

    exact = compose(frames_per_page=2)
    assert [len(page.frames) for page in images_pages(exact)] == [2, 2, 2, 2, 2]
    for page in images_pages(exact):
        assert page.frames  # jamais de PLANCHE sans frame
    # **Toutes** les pages du lot portent des frames depuis la story 5.22, et c'est
    # desormais la forme forte de la meme propriete: entre 5.16 et 5.22, `plan.pages`
    # contenait une page legitimement sans frame (la page de calibration), donc un plan
    # de lot qui aurait sorti une planche vide se confondait avec elle. Le filtre n'est
    # plus une excuse: une page sans frame dans un plan de lot est un defaut, point.
    assert images_pages(exact) == list(exact.pages)
    # La page de calibration, elle, n'en porte aucune, et c'est son role -- pas une page
    # vide. Elle se compose maintenant a la demande.
    assert calibration_page(compose_calibration()).frames == ()


def test_slots_follow_output_rank_and_lot_scoped_slot_index() -> None:
    plan = compose(frames_per_page=4)
    seen = []
    for page in plan.pages:
        for slot in page.frames:
            seen.append(slot.slot_index)
    assert seen == list(range(10))  # continu a l'echelle du lot, jamais remis a zero


def test_frame_filenames_come_from_the_naming_convention_never_a_glob() -> None:
    manifest = make_manifest()
    plan = compose(manifest)
    lot = manifest["lots"][0]
    for page in plan.pages:
        for slot in page.frames:
            expected = naming.build_extracted_frame_filename(
                plan.rush_id, lot["fps_target"], slot.frame_timecode
            )
            assert slot.frame_filename == expected
    assert plan.frames_dir == lot["frames_dir"]


def test_unknown_lot_is_refused_listing_available_lots() -> None:
    manifest = make_manifest()
    with pytest.raises(pdf_composition.LotContentError) as excinfo:
        compose(manifest, lot_id="lot-inconnu")
    message = str(excinfo.value)
    assert "lot-inconnu" in message
    assert manifest["lots"][0]["lot_id"] in message


def test_missing_target_colorspace_blocks_with_actionable_message() -> None:
    manifest = make_manifest(target_colorspace=None)
    with pytest.raises(pdf_composition.LotContentError) as excinfo:
        compose(manifest)
    message = str(excinfo.value)
    assert "target_colorspace" in message
    assert "manifest" in message.lower()


def test_missing_selection_parameter_is_refused_never_guessed() -> None:
    manifest = make_manifest()
    del manifest["lots"][0]["source_frame_count"]
    with pytest.raises(pdf_composition.LotContentError):
        compose(manifest)


def test_missing_timecode_base_fps_blocks_with_actionable_message() -> None:
    """Story 2.7 (AC 3), frontiere negative: un lot sans cadence source n'est
    pas imprimable en 2.1 -- refus nomme, jamais une valeur devinee.
    """
    manifest = make_manifest()
    del manifest["lots"][0]["timecode_base_fps"]
    with pytest.raises(pdf_composition.LotContentError) as excinfo:
        compose(manifest)
    message = str(excinfo.value)
    assert "timecode_base_fps" in message
    assert manifest["lots"][0]["lot_id"] in message


def test_selection_recompute_is_the_verification_implementation() -> None:
    # Revue 4.1 du 2026-08-06: la composition delegue le recalcul a
    # `extraction_manifest.recompute_lot_selection` (implementation unique,
    # decision 2 du 2026-08-02). Un manifest v2.0 dont la cadence source et le
    # timecode de depart vivent dans la section projet est recalcule avec le
    # meme repli que `verify_extracted_lot` -- jamais une divergence detectee
    # en plein rendu.
    manifest = make_manifest()
    rush = manifest["rushes"][0]
    manifest["schema_version"] = "2.0"
    manifest["video"] = {
        "fps_source": rush.pop("fps_source"),
        "fps_source_exact": rush.pop("fps_source_exact"),
        "source_start_timecode": "01:00:00:00",
    }
    plan = compose(manifest)
    # Le repli v2.0 est bien applique: timecodes decales du depart projet. La premiere
    # **planche d'images**, et non `pages[0]`, qui est la page de calibration depuis la
    # story 5.16 et ne porte aucun emplacement.
    assert images_pages(plan)[0].frames[0].frame_timecode.startswith("01:")

    # Le repli reste conditionne au schema_version declare: un manifest v2.1
    # sans cadence source au niveau du rush est refuse, jamais approxime.
    manifest_v21 = make_manifest()
    rush_v21 = manifest_v21["rushes"][0]
    manifest_v21["video"] = {
        "fps_source": rush_v21.pop("fps_source"),
        "fps_source_exact": rush_v21.pop("fps_source_exact"),
    }
    with pytest.raises(pdf_composition.LotContentError):
        compose(manifest_v21)


def test_numeric_parameters_reject_non_integral_values() -> None:
    # Vocabulaire ferme aussi pour les consommateurs API (previz 4.9): jamais
    # de troncature silencieuse 2.9 -> 2, True -> 1, 300.7 -> 300.
    with pytest.raises(pdf_composition.ParameterVocabularyError):
        pdf_composition.resolve_frames_per_page("portrait", 2.9)
    with pytest.raises(pdf_composition.ParameterVocabularyError):
        pdf_composition.resolve_frames_per_page("portrait", True)
    assert pdf_composition.resolve_frames_per_page("portrait", 2.0) == 2
    with pytest.raises(pdf_composition.ParameterVocabularyError):
        pdf_composition.resolve_render_dpi(300.7)
    with pytest.raises(pdf_composition.ParameterVocabularyError):
        pdf_composition.resolve_render_dpi(True)


def test_render_dpi_domain_is_a_closed_interval() -> None:
    # Borne haute (revue 4.1): un DPI demesure produirait un raster QR de
    # dizaines de milliers de pixels au lieu d'un refus de vocabulaire.
    assert pdf_composition.resolve_render_dpi(pdf_composition.RENDER_DPI_MIN) == 150
    assert pdf_composition.resolve_render_dpi(pdf_composition.RENDER_DPI_MAX) == 2400
    for bad in (149, 2401, 100000):
        with pytest.raises(pdf_composition.ParameterVocabularyError) as excinfo:
            pdf_composition.resolve_render_dpi(bad)
        assert str(pdf_composition.RENDER_DPI_MAX) in str(excinfo.value)


def _payload_plan_for(template_id: str, *, print_size_mm: float | None = None):
    """Plan de payload **reel** pour `template_id`, taille imprimee forcee au besoin.

    La taille imprimee est le seul champ force, et jamais la geometrie: `module_side`,
    le payload et son budget restent ceux que produit `plan_page_payload`. C'est
    necessaire pour atteindre la garde de debordement -- aucune charge utile legale ne
    la declenche (le plafond dur de 768 octets s'arrete a 109 modules, et la bande v2
    vaut exactement le majorant d'emprise) -- et c'est suffisant, parce que la garde
    existe pour un **changement de geometrie**, pas pour un payload hors domaine.
    """
    plan = page_payload.plan_page_payload(
        project_id="proj-a", rush_id="rush-001",
        lot_id=naming.build_lot_id("rush-001", 5.0),
        page_index=0, page_count=2, fps_target=5.0,
        timecode_base_fps="25/1",
        template_id=template_id, patch_preset_id="patches-12-v1",
        target_colorspace="rec709", gamut_map_id="gamut-map-none-1",
        slots=[{"slot_index": 0, "frame_timecode": "00:00:00:00"},
               {"slot_index": 1, "frame_timecode": "00:00:00:05"}],
    )
    if print_size_mm is None:
        return plan
    return dataclasses.replace(plan, print_size_mm=print_size_mm)


def test_a_qr_taller_than_the_band_is_refused_even_when_it_fits_in_width() -> None:
    """Le refus de debordement **vertical** de l'emprise du QR, exerce.

    Survivant M46 de la revue 5.15: rien dans la suite ne faisait mordre les deux
    comparaisons verticales de `_qr_footprint_rect`, alors que **c'est la hauteur, et
    non la largeur, qui est la dimension mordante** -- en v1 paysage la bande haute
    fait 177 mm de large pour 50 mm de haut, et en v2 sa hauteur vaut *exactement* le
    majorant d'emprise reserve.

    Le cas est construit pour que seule la hauteur morde: emprise de 60 mm, soit moins
    que les 177 mm de large et plus que les 50 mm de haut. Son symetrique -- la taille
    imprimee nominale, qui ne doit rien lever -- est verifie dans le meme test: sans
    lui, un refus devenu inconditionnel passerait aussi.
    """
    template_id = page_templates.build_template_id("paysage", 2, "0", "v1")
    spec = page_templates.get_template(template_id)
    _band_x, _band_y, band_w, band_h = pdf_composition._qr_band_mm(spec)
    assert (band_w, band_h) == (177.0, 50.0), (band_w, band_h)

    # (1) Le regime nominal traverse sans un mot, et l'emprise tient dans la bande.
    nominal = _payload_plan_for(template_id)
    rect = pdf_composition._qr_footprint_rect(spec, nominal)
    assert rect[3] < band_h

    # (2) Une emprise de 60 mm: elle tient en largeur, elle ne tient pas en hauteur.
    module_side = nominal.module_side
    target_footprint_mm = 60.0
    forced = _payload_plan_for(
        template_id,
        print_size_mm=target_footprint_mm * module_side
        / (module_side + 2 * qr_codes.QUIET_ZONE_MODULES),
    )
    footprint_mm = forced.print_size_mm * (
        module_side + 2 * qr_codes.QUIET_ZONE_MODULES) / module_side
    assert footprint_mm == pytest.approx(target_footprint_mm)
    assert footprint_mm < band_w, footprint_mm      # la largeur ne mord pas
    assert footprint_mm > band_h, footprint_mm      # la hauteur, oui

    with pytest.raises(pdf_composition.GeometryOverflowError) as excinfo:
        pdf_composition._qr_footprint_rect(spec, forced)
    message = str(excinfo.value)
    # Le refus nomme l'emprise, la bande et une sortie actionnable -- jamais un
    # retrecissement silencieux du symbole.
    assert f"{footprint_mm:.1f}" in message
    assert f"{band_h:.0f}" in message
    assert "--frames-par-page" in message


def test_page_payloads_are_valid_and_reparseable() -> None:
    plan = compose()
    for page in plan.pages:
        payload = parse_payload(page.qr.payload_text)
        assert payload == page.qr.payload
        assert payload["page_index"] == page.page_index
        assert payload["page_count"] == plan.page_count
        assert payload["template_id"] == plan.template_id
        assert payload["patch_preset_id"] == plan.patch_preset_id
        assert [slot["slot_index"] for slot in payload["slots"]] == [
            frame.slot_index for frame in page.frames
        ]


def test_composition_is_deterministic() -> None:
    first = compose(frames_per_page=4, patch_preset="9")
    second = compose(frames_per_page=4, patch_preset="9")
    assert first == second


def test_pdf_filename_follows_the_arb_3_convention() -> None:
    plan = compose()
    assert plan.pdf_filename == naming.build_sheets_pdf_filename(
        plan.project_id, plan.rush_id, plan.lot_id, template_id=plan.template_id
    )
    # Le mot `planches` a disparu au profit de la mise en page
    # (`EPIC11-ARB-171`) : le nom porte desormais le gabarit du plan, et le
    # controle le DERIVE du plan plutot que de recopier une forme.
    assert plan.pdf_filename.endswith(
        f"_{plan.frames_per_page}f-{plan.orientation[:3]}.pdf")
    assert "planches" not in plan.pdf_filename
    assert plan.lot_id in plan.pdf_filename


# ---------------------------------------------------------------------------
# AC 5: QR valide avant impression, deux DPI distincts
# ---------------------------------------------------------------------------


def test_qr_geometry_uses_the_scan_dpi_not_the_render_dpi() -> None:
    plan = compose(render_dpi=1200)
    assert plan.scan_dpi == 600  # qr_codes.QR_MIN_SCAN_DPI, consigne de scan
    assert plan.render_dpi == 1200
    for page in plan.pages:
        assert page.qr.scan_dpi == 600
        assert page.qr.geometry_status == "reliable"
        assert page.qr.print_size_mm >= 35.0


def test_over_nominal_budget_prints_with_structured_warning() -> None:
    """EPIC4-ARB-2: entre 512 et 768 octets la page s'imprime, avertissement structure.

    **Fixture durcie par la story 5.17** (cles courtes, `EPIC5-ARB-60`): a 6 frames et
    identifiants de 48 caracteres la page pesait 700 octets, elle en pese 473 et tient
    desormais sous le budget nominal. Il faut donc le cardinal maximal du registre **et**
    un espace de couleur long pour depasser encore 512 -- ce qui est en soi la mesure du
    gain: le regime « hors budget nominal » est devenu difficile a atteindre.

    Le titre a perdu son « larger qr »: a 97 modules la taille cible de 35 mm suffit,
    donc le QR n'est plus agrandi. L'invariant qui reste, et qui etait le vrai sujet,
    est que la taille imprimee couvre toujours la taille requise.
    """
    manifest = make_manifest(
        project_id="p" * 48, rush_id="r" * 48, target_colorspace="x" * 40)
    plan = compose(manifest, frames_per_page=8)
    over_pages = [
        page for page in plan.pages if page.qr.budget.size_bytes > NOMINAL_BUDGET_BYTES
    ]
    assert over_pages, "fixture must exceed the nominal budget"
    for page in over_pages:
        assert any(WARNING_OVER_NOMINAL_BUDGET in w for w in page.qr.warnings)
        assert page.qr.print_size_mm >= page.qr.required_print_size_mm
    assert any(WARNING_OVER_NOMINAL_BUDGET in w for w in plan.warnings)


def test_no_composable_lot_can_reach_the_hard_payload_ceiling_any_more() -> None:
    """Le plafond dur est sorti du domaine atteignable, et le transport reste teste.

    Avant la story 5.17, ce meme lot -- cinq champs a leur longueur maximale et 8 frames
    par page -- levait `PayloadBudgetExceeded` depuis `compose_lot_plan`, et le test
    verifiait que l'exception d'`io.payload` **traverse** le module de composition sans
    etre avalee ni maquillee (piege 1 de la story 4.5).

    Sous les cles courtes, la page la plus lourde qu'un gabarit du registre puisse
    composer pese 563 octets: le plafond de 768 n'est plus atteignable par aucun lot,
    puisque les gabarits s'arretent a 8 frames. La propriete de transport reste donc
    verifiee, mais en abaissant le plafond a une valeur que le domaine atteint -- et non
    en fabriquant un lot impossible, qui aurait fait croire que le regime existe encore.
    """
    manifest = make_manifest(
        project_id="p" * 48,
        rush_id="r" * 48,
        target_colorspace="x" * 40,
        source_frame_count=80,
        fps_source=10.0,
        fps_target=1.0,
    )
    plan = compose(manifest, frames_per_page=8)
    pire = max(page.qr.budget.size_bytes for page in plan.pages)
    # **585 depuis la story 2.7** (572 + 13 octets du champ `timecode_base_fps`: en-tete
    # de 9 octets + longueur 4 de la valeur "10/1", derivee de `fps_source=10.0` par
    # `make_manifest`). 572 valait depuis la story 5.16 (563 + les 9 octets du champ de
    # role). Le plafond dur de 768 reste hors du domaine atteignable: les gabarits
    # s'arretent a 8 frames.
    assert pire == 585, pire
    # La page de calibration est bien la page la plus **legere**, et de loin: elle ne
    # porte aucun emplacement. C'est ce qui rend son refus de geometrie QR diagnostiquable
    # a part -- `--frames-par-page` n'y peut rien.
    #
    # **Composee a la demande depuis la story 5.22** et non plus pechee dans le plan du
    # lot: la comparaison de budget reste exactement la meme mesure, sur le meme manifest
    # et le meme gabarit, et c'est bien ce que la propriete demande. Son payload est meme
    # marginalement plus leger qu'avant, `page_count` valant 1 chez elle.
    calibration = calibration_page(compose_calibration(manifest, frames_per_page=8))
    assert calibration is not None
    assert calibration.qr.budget.size_bytes < min(
        page.qr.budget.size_bytes for page in images_pages(plan))
    assert pire < payload_io.ALERT_BUDGET_BYTES

    # Le transport, mesure sur un plafond que le domaine atteint.
    import pytest as _pytest

    with _pytest.MonkeyPatch.context() as patch:
        patch.setattr(payload_io, "ALERT_BUDGET_BYTES", pire - 1)
        with pytest.raises(PayloadBudgetExceeded) as excinfo:
            compose(manifest, frames_per_page=8)
    assert str(pire - 1) in str(excinfo.value)


# ---------------------------------------------------------------------------
# AC 3 / AC 6: non-chevauchement global et marqueurs 4.3/4.4
# ---------------------------------------------------------------------------


def _page_ink_rects(plan, page):
    spec = page_templates.get_template(plan.template_id)
    rects = []
    for slot in page.frames:
        rects.append(("frame", slot.zone_rect_mm))
    # Taille et silence lus sur la geometrie **du gabarit** depuis la story 5.15: les
    # constantes du module sont celles de la v1, et les employer sur une page v2
    # transportait une emprise de marqueur de 60 mm la ou le symbole et son silence
    # n'en occupent que 25 -- donc un debordement de marge d'encre imaginaire.
    quiet = spec.geometry.marker_quiet_zone_mm
    half = spec.geometry.marker_size_mm / 2
    for marker in page.markers:
        side = spec.geometry.marker_size_mm + 2 * quiet
        rects.append(
            (
                "marker",
                (marker.center_x_mm - half - quiet, marker.center_y_mm - half - quiet, side, side),
            )
        )
    rects.append(("qr", page.qr.footprint_rect_mm))
    for patch in page.patches:
        rects.append(("patch", (patch.x_mm, patch.y_mm, patch.size_mm, patch.size_mm)))
    for name, rect in page.text.zones_mm.items():
        rects.append((f"text:{name}", rect))
    for label in page.text.slot_labels:
        rects.append(("slot-label", label.rect_mm))
    return spec, rects


# EPIC4-ARB-1: la promesse est "chaque template genere" -- la parametrisation
# couvre donc tous les couples orientation x cardinal x preset de marge, pour
# les deux presets de patchs livres (revue 4.1 du 2026-08-06), et non un
# echantillon.
_ALL_TEMPLATE_COUPLES = [
    (orientation, frames_per_page)
    for orientation in page_templates.ORIENTATIONS
    for frames_per_page in page_templates.FRAMES_PER_PAGE_VOCABULARY[orientation]
]


# `patches-18-v2` ajoute par la story 5.9. C'est le **seul** test qui confronte
# les pastilles aux emprises reelles -- QR agrandi compris, etiquettes de slot
# comprises -- et c'est justement le preset le plus serre: il divise par trois
# l'ecart minimal face aux zones de frames et aux etiquettes, lesquelles ne sont
# couvertes par aucune zone reservee de `patch_presets`. Sans ce parametre, la
# propriete restait vraie mais plus personne ne la regardait (revue 5.9-C2-1).
# Etendu aux **deux** versions de geometrie par la story 5.15 (AC 8 et 9): la
# parametrisation couvre donc 11 gabarits x 3 marges x 3 presets x 2 versions. Sans le
# facteur de version, la bascule du defaut aurait rendu la v1 invisible a ce test le
# jour meme ou elle cesse d'etre composee par defaut -- alors que c'est la version des
# planches deja imprimees.
@pytest.mark.parametrize("geometry_version", sorted(page_templates.GEOMETRY_VERSIONS))
@pytest.mark.parametrize("margin_preset", sorted(page_templates.MARGIN_PRESETS_MM))
@pytest.mark.parametrize("patch_preset", ["patches-9-v1", "patches-12-v1", "patches-18-v2"])
@pytest.mark.parametrize("orientation,frames_per_page", _ALL_TEMPLATE_COUPLES)
def test_no_overlap_between_any_printed_elements(
    orientation, frames_per_page, patch_preset, margin_preset, geometry_version
) -> None:
    # **L'orientation est passee** (`EPIC5-ARB-64`): le retrait porte par orientation, et
    # sans elle ce balayage attendait un refus en paysage pour un cardinal qui n'y est
    # retire de rien -- exactement le genre d'attente qu'un cardinal reoffert transforme
    # en faux positif.
    retired = page_templates.retired_cardinal_reason(
        geometry_version, frames_per_page, orientation)
    if retired is not None:
        # Cardinal retire du vocabulaire de cette version **et de cette orientation**
        # (`EPIC5-ARB-62`, `EPIC5-ARB-64`): verifie ici plutot que saute, exactement comme
        # un couple infaisable. Le refus doit **nommer le motif chiffre** -- le gain par
        # frame et le cout en papier -- et non seulement la liste des cardinaux acceptes.
        with pytest.raises(pdf_composition.ParameterVocabularyError) as refus:
            compose(
                orientation=orientation,
                frames_per_page=frames_per_page,
                patch_preset=patch_preset,
                margin_preset=margin_preset,
                geometry_version=geometry_version,
            )
        assert "+0,0 %" in str(refus.value)
        assert "33 % de papier" in str(refus.value)
        return
    unplaceable = (geometry_version, orientation, patch_preset) in (
        patch_presets._PLACEMENT_UNPLACEABLE
    )
    if unplaceable:
        # Un couple geometriquement infaisable est **refuse**, pas approxime: le
        # verifier ici plutot que le sauter garde la parametrisation exhaustive et
        # transforme la lacune en propriete testee.
        with pytest.raises(patch_presets.UndefinedPlacementError):
            compose(
                orientation=orientation,
                frames_per_page=frames_per_page,
                patch_preset=patch_preset,
                margin_preset=margin_preset,
                geometry_version=geometry_version,
            )
        return
    plan = compose(
        orientation=orientation,
        frames_per_page=frames_per_page,
        patch_preset=patch_preset,
        margin_preset=margin_preset,
        geometry_version=geometry_version,
    )
    for page in plan.pages:
        spec, rects = _page_ink_rects(plan, page)
        margin = page_templates.PRINTER_MARGIN_MM
        for index, (name, rect) in enumerate(rects):
            x, y, w, h = rect
            if name == "marker":
                # L'emprise transportee inclut la zone de silence (blanche,
                # jusqu'au bord); la marge physique s'applique a l'encre du
                # symbole seul.
                quiet = spec.geometry.marker_quiet_zone_mm
                x, y, w, h = x + quiet, y + quiet, w - 2 * quiet, h - 2 * quiet
            assert x >= margin - 1e-9, (name, rect)
            assert y >= margin - 1e-9, (name, rect)
            assert x + w <= spec.page_width_mm - margin + 1e-9, (name, rect)
            assert y + h <= spec.page_height_mm - margin + 1e-9, (name, rect)
            x, y, w, h = rect
            for other_name, other_rect in rects[index + 1 :]:
                # La quiet zone d'un marqueur est une zone de silence, pas de
                # l'encre: deux emprises de marqueurs peuvent se toucher, rien
                # d'autre ne peut les recouvrir.
                if name == "marker" and other_name == "marker":
                    continue
                assert not rects_overlap(rect, other_rect), (
                    plan.template_id, name, other_name, rect, other_rect
                )


def test_markers_are_the_four_corners_only() -> None:
    for orientation in ("portrait", "paysage"):
        plan = compose(orientation=orientation)
        spec = page_templates.get_template(plan.template_id)
        expected_centers = page_templates.corner_marker_centers_mm(spec)
        for page in plan.pages:
            assert tuple(marker.marker_id for marker in page.markers) == layout.PRINTED_MARKER_IDS
            for marker in page.markers:
                # Taille de la geometrie **du gabarit**: la constante de `layout` est
                # celle de la v1, et un symbole imprime a une autre taille que celle
                # que le scan reconstruit rendrait la page illisible sans erreur.
                assert marker.size_mm == spec.geometry.marker_size_mm
                assert (marker.center_x_mm, marker.center_y_mm) == expected_centers[
                    marker.marker_id
                ]


def test_patches_come_from_the_47_registry_resolution() -> None:
    plan = compose(patch_preset="patches-9-v1")
    expected = patch_presets.resolve_patch_layout(plan.template_id, "patches-9-v1")
    for page in images_pages(plan):
        assert page.patches == expected
    # La page de calibration ne resout **pas** un preset: son jeu de pastilles est derive
    # de son role (story 5.16, AC 3). Le verifier reste indispensable, et depuis la story
    # 5.22 il se verifie sur la page **composee a la demande**: c'est la seule facon de
    # l'obtenir, et la propriete est inchangee -- `patch_preset_id` ne decrit pas ce qui
    # est imprime sur la page de calibration, meme quand elle porte le meme.
    #
    # **Amende par la story 5.23** (`EPIC5-ARB-82`, AC 1): la page de calibration porte
    # desormais DEUX jeux -- son treillis, toujours derive de son role, ET le bandeau de
    # temoins du lot, pose par le mecanisme de bordure existant depuis le **meme** preset
    # que les planches d'images. La propriete de 5.16 n'est pas relachee, elle est
    # precisee: le preset ne decrit toujours pas le treillis, il decrit maintenant le
    # bandeau -- et l'egalite reste **exacte**, jamais une inclusion.
    calibration = compose_calibration(patch_preset="patches-9-v1")
    assert calibration.patch_preset_id == "patches-9-v1"
    assert calibration_page(calibration).patches == (
        patch_presets.resolve_calibration_page_patches(calibration.template_id)
        + patch_presets.resolve_calibration_page_witnesses(
            calibration.template_id, "patches-9-v1"))
    # Cardinal verifie par **egalite**, jamais par borne (AC 1): une page qui porterait
    # moins de pastilles que son treillis plus son bandeau imprimerait moins qu'elle ne
    # declare, et une inegalite ne le verrait pas.
    assert len(calibration_page(calibration).patches) == (
        patch_presets.calibration_page_patch_count("patches-9-v1"))


# ---------------------------------------------------------------------------
# Texte (contrat 4.2 / EPIC4-ARB-8) et purete du module
# ---------------------------------------------------------------------------


def test_text_plan_carries_the_arb_8_identity_block() -> None:
    plan = compose()
    # **Les trois premieres proprietes valent pour TOUTES les pages imprimees**, page de
    # calibration comprise: l'etiquette de feuille, la pagination et le projet nomment la
    # page, et une page qui ne se nomme pas ne se rattache plus a son lot. Le pied
    # technique, lui, n'appartient qu'aux planches d'images (story 5.16): la page de
    # calibration n'a pas de pied de page, sa bande d'entete valant une rangee de grille.
    for page in plan.pages:
        text = page.text
        assert plan.lot_id in text.sheet_label
        assert f"p{page.page_index + 1:03d}" in text.sheet_label  # base un a l'affichage
        assert text.page_number_text == f"page {page.page_index + 1}/{plan.page_count}"
        assert text.project_id == plan.project_id
    for page in images_pages(plan):
        text = page.text
        assert "600" in text.scan_instruction  # derive de QR_MIN_SCAN_DPI
        assert "DICT_6X6_250" in text.technical_footer  # derive, jamais un litteral
        assert plan.template_id in text.technical_footer
        for label, slot in zip(text.slot_labels, page.frames):
            assert slot.frame_timecode in label.text
            assert plan.rush_id in label.text
        # La date-heure est imprimee au rendu (EPIC4-ARB-8) mais jamais dans
        # le plan: le determinisme contractuel porte sur le plan.
        assert "datetime" not in text.zones_mm or isinstance(
            text.zones_mm["datetime"], tuple
        )


def test_text_is_ascii_only() -> None:
    plan = compose()
    for page in plan.pages:
        text = page.text
        for value in (
            text.sheet_label,
            text.page_number_text,
            text.scan_instruction,
            text.technical_footer,
        ):
            value.encode("ascii")
        for label in text.slot_labels:
            label.text.encode("ascii")


def test_composition_module_never_imports_reportlab_or_writes() -> None:
    for path in (COMPOSITION_PATH, TEMPLATES_PATH):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] != "reportlab", path.name
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] != "reportlab", path.name


def test_page_templates_module_is_pure() -> None:
    # patch_presets (pur) importe page_templates: il ne doit tirer ni cv2 ni
    # layout, sinon la purete 4.7 est cassee par transitivite.
    tree = ast.parse(TEMPLATES_PATH.read_text(encoding="utf-8"), filename=str(TEMPLATES_PATH))
    forbidden = {"cv2", "PIL", "reportlab", "numpy", "layout"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in forbidden, alias.name
        if isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[-1] not in forbidden, node.module
        # Les alias sont controles sur **toutes** les formes d'`ImportFrom`, pas
        # seulement les relatives: `from mixed_media_utility import layout`
        # passait les deux controles precedents. Correctif reporte depuis
        # `test_patch_presets.py`, ou la revue 4.7 avait deja ferme ce trou --
        # la story 5.2 est celle qui rend le cycle possible (elle cree la
        # dependance `layout -> page_templates`), et deux copies d'un meme garde
        # dont une seule a recu le correctif est le motif que ce depot combat.
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                assert alias.name not in forbidden, alias.name


# ---------------------------------------------------------------------------
# Story 4.2: contrat du texte lisible (blocs typographies, egalite
# inter-canaux, conversions d'affichage, degrade explicite)
# ---------------------------------------------------------------------------


def test_typography_floors_are_constants_and_respected() -> None:
    # AC 5: tailles minimales definies comme constantes, jamais contournees.
    assert pdf_composition.TEXT_FONT_NAME == "Helvetica"
    assert pdf_composition.BODY_FONT_MIN_PT >= 8.0
    assert pdf_composition.IDENTITY_FONT_MIN_PT >= 10.0
    plan = compose()
    for page in plan.pages:
        for block in page.text.blocks:
            assert block.font_pt >= pdf_composition.BODY_FONT_MIN_PT, block.name


def test_text_blocks_carry_the_exact_printed_lines_inside_their_zones() -> None:
    # Les blocs sont le contrat exact du rendu (et de la previz 4.9): lignes
    # ASCII, posees dans les zones du plan, chaque ligne tenant dans sa bande
    # au modele de largeur conservatif.
    plan = compose()
    for page in plan.pages:
        zone_names = set(page.text.zones_mm)
        for block in page.text.blocks:
            assert block.name in zone_names
            assert block.rect_mm == page.text.zones_mm[block.name]
            width_mm = block.rect_mm[2]
            for line in block.lines:
                line.encode("ascii")
                assert pdf_composition.text_width_mm(line, block.font_pt) <= width_mm + 1e-6, (
                    block.name, line
                )


@pytest.mark.parametrize("geometry_version", sorted(page_templates.GEOMETRY_VERSIONS))
def test_identity_block_prints_canonical_identifiers_verbatim_at_the_48_boundary(
        geometry_version) -> None:
    # AC 2: egalite stricte inter-canaux a la borne exacte de 48 caracteres --
    # le texte imprime, le payload QR et le nom de fichier portent le meme
    # octet-a-octet.
    #
    # **Parametre par version depuis la story 5.18**, et la propriete est verifiee
    # ailleurs que sur un seul bloc: l'identite s'imprime en deux endroits sous la v2
    # (le nom du lot en entete a 14 pt, `project_id` et `rush_id` au pied), et un test
    # qui ne regarderait que `footer_block` declarerait l'egalite inter-canaux tenue
    # alors que le lot n'y est plus. Ce qui compte est que les trois identifiants
    # canoniques soient sur la planche **verbatim**, pas dans quel bloc.
    project_id = "p" * 48
    rush_id = "r" * 48
    manifest = make_manifest(project_id=project_id, rush_id=rush_id)
    plan = compose(manifest, geometry_version=geometry_version)
    lot_id = plan.lot_id
    assert len(lot_id) == 48
    identity_blocks = {"footer_block", "header_identity"}
    # Les **planches d'images**: l'egalite inter-canoniques des trois identifiants porte
    # sur elles. La page de calibration n'imprime que son `lot_id` et sa pagination --
    # deux lignes dans une bande d'une rangee de grille -- et le verbatim de son `lot_id`
    # est verifie a part plus bas, parce que c'est par lui qu'elle se rattache a son lot.
    for page in images_pages(plan):
        blocks = [b for b in page.text.blocks if b.name in identity_blocks]
        assert blocks, page.text.zones_mm
        joined = "\n".join(line for block in blocks for line in block.lines)
        assert project_id in joined
        assert rush_id in joined
        assert lot_id in joined
        # Et aucune de ces lignes n'est tronquee: le marqueur de troncature dans un bloc
        # d'identite signerait la rupture de l'egalite inter-canaux.
        assert pdf_composition.TRUNCATION_MARKER not in joined
        # Les memes valeurs, a l'octet pres, que le payload QR...
        assert page.qr.payload["project_id"] == project_id
        assert page.qr.payload["rush_id"] == rush_id
        # ... et que la derive utilisee par les noms de fichiers (identite
        # pour un id canonique <= 48).
        assert naming.derive_short_id(rush_id) == rush_id
    calibration = calibration_page(plan)
    if calibration is not None:
        entete = [b for b in calibration.text.blocks if b.name == "header_identity"]
        assert entete, calibration.text.zones_mm
        lignes = "\n".join(line for block in entete for line in block.lines)
        # Verbatim, et **non tronque**: c'est le mecanisme de secours 4.6, et une page de
        # calibration dont le `lot_id` serait tronque ne se rattacherait plus a son lot
        # autrement que par son QR.
        assert lot_id in lignes
        assert pdf_composition.TRUNCATION_MARKER not in lignes
        assert calibration.qr.payload["lot_id"] == lot_id
        for slot in page.frames:
            assert slot.frame_filename.startswith(rush_id)


def test_display_conversions_happen_only_in_display_strings() -> None:
    # AC 3: base un uniquement a l'affichage, timecode forme selection.
    plan = compose()
    assert plan.pages[0].page_index == 0
    first = plan.pages[0].text
    # **`pages[0]` est a nouveau la premiere planche d'images depuis la story 5.22**, et
    # elle est la page 1 sur 5: le decalage d'un cran qu'imposait la page de calibration
    # inseree en tete (5.16) a disparu avec elle.
    assert first.page_number_text == "page 1/5"
    assert images_pages(plan)[0].text.page_number_text == "page 1/5"
    # La page de calibration composee a la demande, elle, est la page 1 **sur 1**: elle
    # est autoportante, elle ne compte pas les planches d'un lot auquel elle
    # n'appartient plus.
    # AMENDE PAR 5.23 (2026-08-18): la page de calibration n'affiche plus **aucune**
    # pagination. « page 1/1 » sur une feuille seule n'informe de rien -- c'est l'une
    # des trois mentions qu'Egan a fait retirer, avec le rush et la cadence --, et le
    # `page_count` de son payload reste a 1 pour autant: le champ decrit la feuille,
    # l'affichage decrivait un lot auquel elle n'appartient plus.
    assert calibration_page(compose_calibration()).text.page_number_text == ""
    assert calibration_page(compose_calibration()).qr.payload["page_count"] == 1
    assert first.fps_display == "5 im/s"
    for label in first.slot_labels:
        assert ":" in label.text  # hh:mm:ss:ff, jamais hh-mm-ss-ff
        assert "-" not in label.text.split("tc ")[-1]


def test_fps_display_keeps_fractional_rates_readable() -> None:
    manifest = make_manifest(fps_source=25.0, fps_target=12.5)
    manifest["lots"][0]["fps_target_exact"] = "25/2"
    plan = compose(manifest)
    assert plan.pages[0].text.fps_display == "12.5 im/s"


def test_slot_labels_always_keep_slot_and_timecode_intact() -> None:
    # AC 6 aux bornes: zone la plus etroite du vocabulaire (paysage 8) avec un
    # rush de 48 caracteres -- le coeur s<NN> + timecode reste entier, seul le
    # rappel de rush est tronque avec marqueur visible.
    manifest = make_manifest(rush_id="r" * 48)
    plan = compose(manifest, orientation="paysage", frames_per_page=8)
    for page in plan.pages:
        for label, slot in zip(page.text.slot_labels, page.frames):
            assert f"s{slot.slot_index:02d}" in label.text
            assert slot.frame_timecode in label.text
            assert pdf_composition.text_width_mm(
                label.text, pdf_composition.BODY_FONT_MIN_PT
            ) <= label.rect_mm[2] + 1e-6
            assert pdf_composition.TRUNCATION_MARKER in label.text


def test_fit_text_truncates_with_visible_marker_and_preserved_tail() -> None:
    # AC 6: jamais de reduction de police sous le minimum, jamais de
    # chevauchement silencieux -- troncature marquee, queue preservee (la fin
    # d'un id derive porte le suffixe de hachage discriminant).
    value = "a" * 40 + "-deadbeef"
    fitted = pdf_composition.fit_text(value, 40.0, pdf_composition.BODY_FONT_MIN_PT)
    assert fitted != value
    assert pdf_composition.TRUNCATION_MARKER in fitted
    assert fitted.endswith("-deadbeef")
    assert pdf_composition.text_width_mm(
        fitted, pdf_composition.BODY_FONT_MIN_PT
    ) <= 40.0 + 1e-6

    untouched = pdf_composition.fit_text("court", 40.0, pdf_composition.BODY_FONT_MIN_PT)
    assert untouched == "court"


def test_technical_footer_carries_the_payload_schema_version() -> None:
    # AC 1: pied de page technique complete par la version du schema de
    # payload -- derivee du contrat 2.3, jamais un litteral local.
    from mixed_media_utility.io.payload import PAYLOAD_SCHEMA_VERSION

    plan = compose()
    # Les **planches d'images**: la page de calibration ne porte pas de pied technique
    # (story 5.16), et elle porte la version de schema la ou elle compte vraiment -- dans
    # son QR, que la relecture lit.
    for page in images_pages(plan):
        assert PAYLOAD_SCHEMA_VERSION in page.text.technical_footer
        assert "DICT_6X6_250" in page.text.technical_footer
        assert plan.template_id in page.text.technical_footer
        assert plan.patch_preset_id in page.text.technical_footer
    # La page de calibration, composee a la demande depuis la story 5.22: toujours pas de
    # pied technique (sa bande d'entete vaut une rangee de grille), et la version de
    # schema toujours la ou elle compte -- dans son QR, que la relecture lit.
    calibration = calibration_page(compose_calibration())
    assert calibration.text.technical_footer == ""
    assert calibration.qr.payload["schema_version"] == PAYLOAD_SCHEMA_VERSION


# ---------------------------------------------------------------------------
# AC 6 de la story 11.4b: les dix renseignements du pied technique
# (`EPIC11-ARB-65`, debloque par `EPIC11-ARB-87`)
# ---------------------------------------------------------------------------


def mentions_du_pied(page) -> tuple[str, ...]:
    """Les mentions du pied technique **dans l'ordre imprime**, relues sur les blocs.

    On lit les **blocs**, jamais `text.technical_footer`. C'est la lecon du mutant
    `M21` du lot S6: cette chaine est un reste d'avant la disposition a colonnes,
    plus personne ne l'imprime, et les bancs qui la relisaient mesuraient donc une
    chaine que le papier ne porte pas. Le pied vraiment imprime se lit dans les
    colonnes techniques, colonne par colonne, ligne par ligne.
    """
    blocs = {bloc.name: bloc for bloc in page.text.blocks}
    lignes = [ligne for nom in page_templates.FOOTER_TECHNICAL_ZONE_NAMES
              if nom in blocs for ligne in blocs[nom].lines]
    if not lignes:
        # Disposition historique (v1): la technique vit dans le bloc de pied, apres
        # les lignes d'identite.
        lignes = list(blocs["footer_block"].lines[
            page_templates.FOOTER_IDENTITY_LINE_COUNT:])
    return tuple(mention for ligne in lignes for mention in ligne.split(" - "))


def test_le_pied_technique_porte_les_dix_renseignements_dans_l_ordre() -> None:
    """**AC 6.3**: le pied **produit** porte les dix parts, dans l'ordre.

    Les cles sont ecrites **en toutes lettres** ici, et c'est delibere: elles sont
    un contrat avec l'operatrice qui retape une planche muette, exactement comme un
    nom de fichier en est un. Les deriver de `PIED_CLES_COURTES` ferait de ce banc
    une tautologie -- il rougirait pour un renommage et se tairait pour le meme
    renommage fait des deux cotes. C'est le mutant `M21` du lot S6 et le `M20` du
    lot J, tous deux payes cette semaine.

    Les **valeurs**, elles, viennent des contrats et jamais d'un litteral: c'est
    l'autre moitie, et `test_chaque_mention_du_pied_suit_sa_source` la mesure en
    faisant varier les sources.
    """
    plan = compose()
    page = images_pages(plan)[0]
    mentions = mentions_du_pied(page)
    assert len(mentions) == 10, mentions
    cles = tuple(mention.split("=", 1)[0] for mention in mentions)
    assert cles == (
        "MMU makepdf",          # provenance, seule mention sans `=`
        "dict",                 # dictionnaire ArUco -- la seule hors payload
        "tid",                  # gabarit de page
        "ppi",                  # preset de pastilles
        "sv",                   # version du schema de payload
        "tbf",                  # base de timecode, fraction EXACTE
        "tcs",                  # espace de couleur cible
        "gmi",                  # projection de gamut
        "pc",                   # cardinal de planches du lot
        f"scan {qr_codes.QR_MIN_SCAN_DPI} dpi",   # consigne, sans `=` non plus
    ), mentions
    # **Sept des huit cles sont celles du QR**, et le banc le dit sur la table
    # plutot que de le laisser deviner : le pied existe pour retaper ce que le QR
    # aurait porte, donc il le nomme comme le QR le nomme. Un second vocabulaire
    # court sur la meme feuille serait une seconde redaction (finding 4.3), et la
    # frontiere `test_the_table_is_the_only_place_where_a_short_key_is_written`
    # le refuse d'ailleurs en clair.
    du_payload = {cle for champ, cle in pdf_composition.PIED_CLES_COURTES.items()
                  if payload_io.PAYLOAD_SHORT_KEYS.get(champ) == cle}
    assert du_payload == set(cles[1:-1]) - {"dict"}, du_payload
    assert set(pdf_composition.PIED_CLE_HORS_PAYLOAD) == {"aruco_dictionary"}
    # Et les valeurs sont celles du plan compose, pas celles d'un litteral d'ici.
    valeurs = dict(mention.split("=", 1) for mention in mentions if "=" in mention)
    assert valeurs["dict"] == layout.aruco_dictionary_name()
    assert valeurs["tid"] == plan.template_id
    assert valeurs["ppi"] == plan.patch_preset_id
    assert valeurs["sv"] == payload_io.PAYLOAD_SCHEMA_VERSION
    assert valeurs["gmi"] == plan.gamut_map_id
    assert valeurs["pc"] == str(plan.page_count)
    # **`np` est un CARDINAL de lot, pas un rang de page**: le pied est le meme sur
    # toutes les planches. Une pagination `N/M` glissee ici se verrait deux fois --
    # par la divergence entre planches et par le slash, qu'aucune mention ne porte
    # en dehors de la base de timecode.
    assert len(images_pages(plan)) >= 2
    assert len({mentions_du_pied(p) for p in images_pages(plan)}) == 1


def test_le_pied_technique_imprime_la_base_de_timecode_VERBATIM() -> None:
    """La base de timecode est une **fraction exacte**, et elle s'imprime telle quelle.

    `lots[].timecode_base_fps` vaut `'25/1'` ou `'24000/1001'`; ce n'est pas un
    flottant, et `format_fps_display` la refuse par un `ValueError`. Le convertir
    serait doublement faux: le pied existe pour etre **retape a la main**
    (`EPIC11-ARB-65`), et sur un rush NTSC `24000/1001` et `23,976` ne sont pas le
    meme nombre -- une frame de derive toutes les 1000.

    Les deux volets sont necessaires: la fraction NTSC prouve que rien n'arrondit,
    la fraction entiere prouve que rien ne re-formate non plus (`'25/1'` reste
    `'25/1'` et ne devient pas `'25'`).
    """
    for fraction in ("24000/1001", "25/1"):
        manifest = make_manifest(timecode_base_fps=fraction)
        page = images_pages(compose(manifest))[0]
        valeurs = dict(mention.split("=", 1)
                       for mention in mentions_du_pied(page) if "=" in mention)
        assert valeurs["tbf"] == fraction, mentions_du_pied(page)
        # Et c'est bien la valeur du manifest, relue a la source, pas une constante.
        assert valeurs["tbf"] == manifest["lots"][0]["timecode_base_fps"]
    # Le volet symetrique, qui dit pourquoi le verbatim n'est pas une preference:
    # la fonction d'affichage des cadences REFUSE cette chaine. Un jour ou l'autre
    # quelqu'un voudra "harmoniser" les deux, et ce banc lui repondra.
    with pytest.raises(ValueError):
        pdf_composition.format_fps_display("24000/1001")


def test_chaque_mention_du_pied_suit_sa_source() -> None:
    """**AC 6.1**: chaque renseignement est derive de son contrat, jamais d'un litteral.

    Le geste qui mesure cela n'est pas de comparer une valeur a une valeur: c'est de
    faire **varier la source** et de verifier que l'imprime suit. Une mention devenue
    constante locale reste egale a elle-meme quand la source bouge -- c'est le
    finding 4.3, deja paye ici.

    **Regle des fabriques, points 2 et 2 bis**: chaque source prend **trois** valeurs
    deux a deux distinctes et la cible est au **milieu** -- ni premiere ni derniere.
    Une fabrique a deux valeurs dont la cible est en seconde position la place aussi
    en derniere, et les deux formes y sont indiscernables.

    Et la mesure est **exacte** des deux cotes: on verifie que la mention visee suit,
    ET que l'ensemble des mentions qui divergent vaut **exactement** {cette
    mention-la}. Une assertion positive seule laisserait passer une source qui
    contaminerait une autre mention au passage.
    """
    def pied(**kwargs) -> dict[str, str]:
        manifest = kwargs.pop("manifest", None) or make_manifest()
        page = images_pages(compose(manifest, **kwargs))[0]
        return dict(mention.split("=", 1)
                    for mention in mentions_du_pied(page) if "=" in mention)

    def confronter(cle: str, pieds: list[dict[str, str]], attendus: list[str],
                   aussi: set[str] = frozenset()) -> None:
        for imprime, attendu in zip(pieds, attendus):
            assert imprime[cle] == attendu, (cle, imprime, attendu)
        # L'ensemble des cles qui divergent entre la cible et chacune des deux autres
        # est **exactement** {cle} -- augmente des divergences que le levier entraine
        # par construction, nommees une par une par l'appelant. Une source qui
        # deborderait sur une autre mention -- ou une mention qui suivrait la mauvaise
        # source -- se verrait ici, et un `aussi` trop large se verrait aussi: les
        # cles qu'il nomme doivent VRAIMENT diverger.
        cible = pieds[1]
        for autre in (pieds[0], pieds[2]):
            divergentes = {nom for nom in cible if cible[nom] != autre[nom]}
            assert divergentes == {cle} | set(aussi), (
                cle, divergentes, cible, autre)

    # -- `tcb`: la base de timecode du LOT, au manifest ------------------------
    bases = ["24/1", "24000/1001", "30000/1001"]
    confronter("tbf", [pied(manifest=make_manifest(timecode_base_fps=base))
                       for base in bases], bases)

    # -- `tcs`: l'espace de couleur cible, au manifest (`color.`) --------------
    espaces = ["rec709", "rec2020", "p3d65"]
    confronter("tcs", [pied(manifest=make_manifest(target_colorspace=espace))
                       for espace in espaces], espaces)

    # -- `pt`: le preset de pastilles, au registre -----------------------------
    presets = ["patches-9-v1", "patches-14-v3", "patches-18-v2"]
    confronter("ppi", [pied(patch_preset=preset) for preset in presets], presets)

    # -- `gam`: la projection de gamut, au registre ----------------------------
    # **Exception assumee a « trois valeurs deux a deux distinctes »**: le registre
    # du depot n'en porte que deux (`gamut-map-none-1`, `gamut-map-lin-1`). La
    # propriete qui compte -- la cible differe des autres et n'est pas en premiere
    # position -- est tenue par l'encadrement, et un troisieme regime invente ne
    # mesurerait qu'un registre qui n'existe pas.
    gamuts = ["gamut-map-none-1", "gamut-map-lin-1", "gamut-map-none-1"]
    confronter("gmi", [pied(gamut_map_id=g) for g in gamuts], gamuts)

    # -- `np`: le cardinal de planches, DEDUIT de la selection recalculee -------
    # Il ne se pilote par aucun parametre de vocabulaire: il se deduit du nombre de
    # frames et du cardinal d'emplacements. Les trois regimes ont ete choisis pour
    # que la cible **ne tombe pas juste** (10 frames pour 4 emplacements font 3
    # planches, pas 2) -- un `floor` deguise en `ceil` s'y verrait.
    cardinaux = [2, 4, 1]
    attendus = ["5", "3", "10"]
    # Le cardinal d'emplacements deplace **deux** mentions et pas une: il entre aussi
    # dans le nom du gabarit (`tpl-a4-portrait-4f-v2`). C'est nomme plutot que
    # neutralise -- une divergence qu'on ne sait pas expliquer est un defaut, pas un
    # detail --, et `aussi` est verifie: `tpl` doit vraiment diverger.
    confronter("pc", [pied(frames_per_page=cardinal) for cardinal in cardinaux],
               attendus, aussi={pdf_composition.PIED_CLES_COURTES["template_id"]})
    # Le volet qui ferme la porte de derriere: la mention suit la **selection**, et
    # non le `expected_frame_count` declare au manifest.
    moitie = make_manifest(source_frame_count=25)
    assert moitie["lots"][0]["expected_frame_count"] == 5
    assert pied(manifest=moitie, frames_per_page=2)["pc"] == "3"


def test_les_quatre_ajouts_completent_exactement_les_champs_neutres_du_lot() -> None:
    """**Pourquoi ces quatre-la et pas d'autres** (`EPIC11-ARB-65`).

    Egan: « le but etant qu'une pile totalement denuee de QR puisse etre decodee
    avec entree manuelle ». Ce que la saisie manuelle ne peut pas deviner est
    enumere par `scan_corrections.CHAMPS_NEUTRES_DU_LOT`, et le papier en portait
    deja quatre: `project_id` et `rush_id` au bloc d'identite, `fps_target` a
    l'entete, `patch_preset_id` au pied technique. Les quatre ajoutes sont donc
    **exactement** le complement -- ni un de moins, ce qui laisserait une pile
    incompletable, ni un de plus, qui serait de la place prise sans motif.

    L'egalite est **exacte** et non une inclusion: un cinquieme champ neutre ajoute
    au contrat de scan sans etre imprime ferait rougir ce banc, et c'est
    precisement ce qu'on veut qu'il dise.
    """
    from mixed_media_utility.scan_corrections import CHAMPS_NEUTRES_DU_LOT

    plan = compose()
    page = images_pages(plan)[0]
    mentions = mentions_du_pied(page)
    valeurs = dict(mention.split("=", 1) for mention in mentions if "=" in mention)

    # Ce que le papier porte **ailleurs** qu'au pied technique, releve sur la page
    # composee et non declare ici.
    blocs = {bloc.name: bloc for bloc in page.text.blocks}
    ailleurs = "\n".join(
        ligne for nom, bloc in blocs.items()
        if nom not in page_templates.FOOTER_TECHNICAL_ZONE_NAMES
        for ligne in bloc.lines
    )
    deja_sur_le_papier = {
        "project_id": plan.project_id in ailleurs,
        "rush_id": plan.rush_id in ailleurs,
        "fps_target": page.text.fps_display in ailleurs,
        "patch_preset_id": True,   # au pied technique depuis la story 4.2
    }
    assert all(deja_sur_le_papier.values()), deja_sur_le_papier

    attendus = set(CHAMPS_NEUTRES_DU_LOT) - set(deja_sur_le_papier)
    assert set(pdf_composition.PIED_CHAMPS_AJOUTES) == attendus, (
        pdf_composition.PIED_CHAMPS_AJOUTES, attendus)
    # Et les quatre sont bien **imprimes**, sous leurs cles, avec la valeur du plan.
    for champ in pdf_composition.PIED_CHAMPS_AJOUTES:
        assert pdf_composition.PIED_CLES_COURTES[champ] in valeurs, (champ, valeurs)
    # Les huit champs neutres sont donc tous relisables sur la planche: c'est la
    # phrase d'Egan, mesuree, et c'est ce que la 11.5 cablera.
    assert set(CHAMPS_NEUTRES_DU_LOT) == (
        set(deja_sur_le_papier) | set(pdf_composition.PIED_CHAMPS_AJOUTES))


def test_le_pied_gele_de_la_v1_diverge_exactement_des_quatre_ajouts() -> None:
    """**AC 6.4**: la reserve porte sur les planches imprimees **apres** ce changement.

    La v1 est une geometrie **figee** -- des planches sont deja imprimees avec --,
    donc son pied garde ses six mentions et ses cles historiques. Ce banc mesure
    l'ecart entre les deux pieds, et il le mesure **exactement** plutot que
    positivement: « la v2 porte les quatre ajouts » laisserait passer toute
    divergence supplementaire, et c'est le second des deux pieges nommes dans
    CLAUDE.md (« une assertion positive laisse passer toute divergence
    supplementaire »).

    L'attendu n'est pas une liste reecrite a la main: il est **projete** du pied
    gele vers le pied courant par la seule table des cles, exactement comme
    `test_a_v1_lot_is_byte_for_byte_what_it_was_before_the_story` projette les
    charges utiles d'epoque par `PAYLOAD_SHORT_KEYS`.
    """
    manifest = make_manifest()
    gele = images_pages(compose(manifest, geometry_version="v1"))[0]
    courant = images_pages(compose(manifest, geometry_version="v2"))[0]

    def couples(page) -> dict[str, str]:
        return dict(mention.split("=", 1)
                    for mention in mentions_du_pied(page) if "=" in mention)

    couples_geles, couples_courants = couples(gele), couples(courant)
    assert len(couples_geles) == len(pdf_composition.PIED_CLES_V1)
    assert len(couples_courants) == len(pdf_composition.PIED_CLES_COURTES)

    # Projection du pied gele vers le pied courant: meme champ, cle renommee.
    projete = {
        pdf_composition.PIED_CLES_COURTES[champ]: couples_geles[cle_gelee]
        for champ, cle_gelee in pdf_composition.PIED_CLES_V1.items()
    }
    ajoutes = {pdf_composition.PIED_CLES_COURTES[champ]
               for champ in pdf_composition.PIED_CHAMPS_AJOUTES}
    # Ce qui ne figure pas dans la projection est **exactement** les quatre ajouts.
    assert set(couples_courants) - set(projete) == ajoutes
    assert set(projete) - set(couples_courants) == set()
    # Et sur les quatre champs communs, seule la mention `tpl` differe -- elle porte
    # la version de geometrie dans son nom, par construction.
    divergentes = {cle for cle in projete if projete[cle] != couples_courants[cle]}
    assert divergentes == {pdf_composition.PIED_CLES_COURTES["template_id"]}, (
        projete, couples_courants)
    gabarit = pdf_composition.PIED_CLES_COURTES["template_id"]
    assert projete[gabarit].replace("-v1", "") == couples_courants[
        gabarit].replace("-v2", "")


def test_aucune_relecture_du_depot_n_exige_les_quatre_champs_imprimes() -> None:
    """**AC 6.4, la moitie structurelle**: une planche d'AVANT reste relisible.

    La reserve « cela ne vaut que pour les planches imprimees apres » n'a de sens
    que si aucune relecture n'a besoin de ce que le pied porte. Le volet
    comportemental seul ne le dirait pas -- il ne voit que le chemin qu'il deroule,
    piege deja paye par le lot S1 --, donc la mesure est **structurelle**: aucun
    module du chemin de scan ne lit le texte de la planche.

    Ce que la relecture lit est le **QR**, et une planche muette se complete par le
    modele du lot (`scan_corrections.modele_depuis_le_manifeste`), jamais par le
    pied imprime. Le pied est le secours de derniere main, pour un humain.
    """
    lecteurs = sorted(
        chemin for motif in ("scan_*.py", "detection/*.py")
        for chemin in (REPO_ROOT / "src" / "mixed_media_utility").glob(motif)
    )
    assert len(lecteurs) >= 3, lecteurs
    #: Les noms que porte le PRODUCTEUR du pied: aucun lecteur ne doit les citer.
    NOMS_DU_PIED = ("technical_footer", "PIED_CLES_COURTES", "PIED_CLES_V1",
                    "PIED_PROVENANCE", "pied_technique_parts")
    #: Le releveur des bancs. Il n'a aucune raison d'exister dans `src/`, donc il
    #: n'entre pas dans le volet symetrique -- l'y mettre le ferait echouer pour
    #: une raison qui n'a rien a voir avec la frontiere.
    RELEVEUR = "mentions_du_pied"
    for chemin in lecteurs:
        texte = chemin.read_text(encoding="utf-8")
        for nom in (*NOMS_DU_PIED, RELEVEUR):
            assert nom not in texte, (chemin.name, nom)
    # Volet symetrique, sans quoi la frontiere pourrait balayer des fichiers ou le
    # nom n'a aucune chance d'apparaitre: le producteur, lui, les porte tous.
    producteur = COMPOSITION_PATH.read_text(encoding="utf-8")
    for nom in NOMS_DU_PIED:
        assert nom in producteur, nom


def test_une_mention_du_pied_trop_longue_est_signalee_et_jamais_muette() -> None:
    """**AC 6.2**: l'ecart est **remonte**, jamais resolu par une troncature muette.

    Le mot qui commande est *muette*. `_pack_lines` tronque avec un marqueur visible
    une mention plus large que la colonne -- c'est le bon geste pour de la prose et
    un demi-geste pour un `cle=valeur` que quelqu'un doit retaper. Le constat
    `PIED_TECHNIQUE_TRONQUE` est l'autre moitie: il nomme la mention, sa longueur et
    la largeur disponible, et il dit ce qui est perdu (la saisie manuelle de ce
    champ-la), pas seulement qu'il s'est passe quelque chose.

    **Ce n'est deliberement pas un refus**, et le motif est mesure: le
    `target_colorspace` vient de `project.json`, aucun registre ne le borne, et le
    depot compose aujourd'hui des lots dont il fait 40 caracteres. Refuser ferait
    refuser des planches qui s'impriment -- pour un champ que le QR porte toujours
    en entier.

    Les deux volets sont necessaires. Sans le symetrique, un constat pose sur
    **toute** composition serait vert de la meme facon.
    """
    long_espace = "espace-de-couleur-tres-long-a-retaper"
    plan = compose(make_manifest(target_colorspace=long_espace))
    constats = [w for w in plan.warnings
                if w.startswith(pdf_composition.PIED_TECHNIQUE_TRONQUE)]
    assert len(constats) == 1, plan.warnings
    constat = constats[0]
    # Le constat nomme la mention **entiere**, pas sa version tronquee: un motif qui
    # se tronquerait lui-meme serait le meme defaut, deplace.
    assert f"tcs={long_espace}" in constat, constat
    assert pdf_composition.TRUNCATION_MARKER in constat, constat
    assert "retapee" in constat, constat
    # Et la planche s'imprime quand meme, avec la mention tronquee **visiblement**.
    mentions = mentions_du_pied(images_pages(plan)[0])
    tronquee = [m for m in mentions if m.startswith("tcs=")]
    assert len(tronquee) == 1, mentions
    assert pdf_composition.TRUNCATION_MARKER in tronquee[0], tronquee
    assert tronquee[0] != f"tcs={long_espace}"
    # Le QR, lui, la porte **en entier**: c'est ce qui fait que le constat est un
    # constat et non un refus.
    assert images_pages(plan)[0].qr.payload_text.count(long_espace) == 1

    # -- volet symetrique: un espace de couleur ordinaire ne produit aucun constat --
    ordinaire = compose(make_manifest(target_colorspace="rec709"))
    assert not [w for w in ordinaire.warnings
                if w.startswith(pdf_composition.PIED_TECHNIQUE_TRONQUE)]
    assert all(pdf_composition.TRUNCATION_MARKER not in mention
               for mention in mentions_du_pied(images_pages(ordinaire)[0]))


def test_un_renseignement_absent_du_pied_est_REFUSE_et_jamais_imprime_vide() -> None:
    """La garde du point d'entree **public**, exercee a l'unite (mutant `M17`).

    `pied_technique_parts` est publique depuis cette story, donc sa garde ne
    protege pas seulement `compose_lot_plan` -- qui, lui, ne peut pas l'atteindre
    (`_lot_identity` refuse deja un `timecode_base_fps` ou un
    `color.target_colorspace` absent, et les quatre autres valeurs viennent de
    registres). Elle protege l'appelant a venir, et c'est **la** qu'elle se
    mesure : la campagne d'injection du lot L a vu le mutant qui la neutralise
    survivre a la composition entiere, precisement parce qu'aucun lot reel ne la
    fait mordre.

    Une planche qui porterait `tcs=` sans valeur est exactement la planche qu'une
    saisie manuelle ne peut pas completer : le refus est le seul comportement
    juste, et il **nomme** le champ.

    **Les huit champs sont eprouves, pas un.** Une garde posee sur un seul
    d'entre eux -- ou sur le premier de la table -- serait verte sur un test qui
    n'en essaie qu'un, et c'est la faute que la regle des fabriques nomme.
    """
    complet = {
        "aruco_dictionary": "DICT_6X6_250",
        "template_id": "tpl-a4-portrait-2f-v2",
        "patch_preset_id": "patches-17-v4",
        "schema_version": "2.1",
        "timecode_base_fps": "24000/1001",
        "target_colorspace": "rec709",
        "gamut_map_id": "gamut-map-none-1",
        "page_count": 7,
    }
    assert set(complet) == set(pdf_composition.PIED_CLES_COURTES)
    # Volet symetrique: complet, la fabrique rend ses dix mentions sans broncher.
    nominal = pdf_composition.pied_technique_parts(
        geometry_version="v2", valeurs=complet)
    assert len(nominal) == len(pdf_composition.PIED_CLES_COURTES) + 2

    for champ in complet:
        for absent in ({**complet, champ: None}, {**complet, champ: ""},
                       {cle: v for cle, v in complet.items() if cle != champ}):
            with pytest.raises(pdf_composition.LotContentError) as excinfo:
                pdf_composition.pied_technique_parts(
                    geometry_version="v2", valeurs=absent)
            # Le refus NOMME le champ manquant: un motif generique ferait
            # chercher lequel des huit, sur une planche qu'on n'a pas sous les
            # yeux.
            assert champ in str(excinfo.value), (champ, str(excinfo.value))
            assert "retapee a la main" in str(excinfo.value)

    # Le pied **gele** n'exige que ses quatre champs, et c'est la moitie qui dit
    # que la garde suit la TABLE et non une liste ecrite a cote: les quatre
    # ajouts absents ne le font pas refuser.
    quatre = {cle: complet[cle] for cle in pdf_composition.PIED_CLES_V1}
    assert pdf_composition.pied_technique_parts(
        geometry_version=page_templates.GEOMETRY_V1.version, valeurs=quatre)
    with pytest.raises(pdf_composition.LotContentError):
        pdf_composition.pied_technique_parts(
            geometry_version=page_templates.GEOMETRY_V1.version,
            valeurs={**quatre, "template_id": ""})


def test_aucune_mention_du_pied_GELE_ne_peut_deborder_et_l_arithmetique_le_dit():
    """**Equivalence demontree** (mutant `M15`), et la demonstration est ecrite.

    Le mutant etend a la geometrie **v1** le constat de troncature que la
    production reserve aux geometries non gelees, et il **survit**. J'ai cherche
    a le tuer avant de conclure : il ne peut pas l'etre, parce que la branche
    qu'il ouvre est **vide** -- aucune mention du pied gele ne peut deborder.

    La demonstration, et elle tient parce que les **quatre** valeurs du pied gele
    sont bornees par des registres et non par un manifest :

    * le pied v1 le plus etroit du depot fait **90 mm** (litteral historique), et
      les 22 gabarits v1 sont a cette largeur ou plus ;
    * la mention la plus large que ces quatre valeurs puissent former --
      `template=` suivi du `template_id` v1 le plus long -- fait **55,9 mm** au
      plancher typographique.

    55,9 < 90 : la marge est de 34 mm, soit vingt caracteres. Le constat serait
    donc calcule pour rien sur la v1, et l'y calculer ou non est **inobservable**.
    Ce n'est pas un trou de test, c'est une equivalence.

    Ce que ce banc garde en revanche, et c'est son interet : la **premisse**. Un
    registre qui gagnerait un preset de pastilles ou un gabarit au nom beaucoup
    plus long ferait tomber l'inegalite ici, et l'equivalence serait a
    reexaminer -- ce qui est exactement le service qu'on attend d'elle.
    """
    from mixed_media_utility.io.payload import PAYLOAD_SCHEMA_VERSION

    gabarits, largeurs = [], []
    for orientation in page_templates.ORIENTATIONS:
        for cardinal in range(1, 25):
            for marge in ("0", "5"):
                try:
                    spec = page_templates.template_for(
                        orientation, cardinal, marge, "v1")
                except Exception:
                    continue
                zones = page_templates.footer_zones_mm(spec)
                colonnes = [nom for nom in page_templates.FOOTER_TECHNICAL_ZONE_NAMES
                            if nom in zones]
                largeurs.append(zones[colonnes[0]][2] if colonnes
                                else zones["footer_block"][2])
                gabarits.append(spec.template_id)
    assert len(gabarits) >= 20, gabarits

    # Les quatre valeurs du pied gele, chacune a son maximum de registre. Aucune
    # ne vient d'un manifest -- c'est ce qui rend la borne opposable.
    pire = {
        "aruco_dictionary": layout.aruco_dictionary_name(),
        "template_id": max(gabarits, key=len),
        "patch_preset_id": max(patch_presets._PRESETS, key=len),
        "schema_version": PAYLOAD_SCHEMA_VERSION,
    }
    mentions = pdf_composition.pied_technique_parts(
        geometry_version=page_templates.GEOMETRY_V1.version, valeurs=pire)
    la_plus_large = max(
        pdf_composition.text_width_mm(mention, pdf_composition.BODY_FONT_MIN_PT)
        for mention in mentions if "=" in mention)
    assert la_plus_large < min(largeurs), (la_plus_large, min(largeurs))
    # Et la conclusion, posee sur le producteur reel plutot que sur le modele :
    # sur cette pire combinaison, rien ne deborde.
    assert pdf_composition.mentions_tronquees(
        mentions, min(largeurs), pdf_composition.BODY_FONT_MIN_PT) == ()


def test_real_lot_composition_satisfies_the_previz_protocol() -> None:
    # Revue 4.9: `pdf_previz` consomme le plan en typage structurel et son
    # test unitaire n'utilise que des SimpleNamespace -- un renommage de champ
    # dans le plan ne cassait que chez le premier consommateur reel, en
    # AttributeError brute, tous tests verts. Ici, la confrontation reelle:
    # le vrai LotComposition traverse build_pdf_previz sans erreur et la
    # projection reflete le plan champ par champ.
    from mixed_media_utility import extraction_previz, pdf_previz

    plan = compose()
    images = images_pages(plan)
    document = pdf_previz.build_pdf_previz(
        plan=plan,
        generated_at_utc="2026-08-07T00:00:00Z",
        expected_frame_count=len(images[0].frames) * len(images),
        selection_fingerprint=extraction_previz.fingerprint_of({"real": 1}),
    )
    assert document.pdf_filename == plan.pdf_filename
    # La previz projette **toutes** les pages imprimees, page de calibration comprise:
    # elle sert a verifier ce qui sortira de l'imprimante, et une page absente de
    # l'apercu serait precisement la page qu'on n'aurait pas relue.
    assert len(document.pages) == plan.page_count == len(plan.pages)
    # La confrontation champ par champ porte sur la premiere **planche d'images**: c'est
    # elle qui porte des zones de dessin et des etiquettes d'emplacement.
    rang = plan.pages.index(images[0])
    first_plan_page = images[0]
    first_previz_page = document.pages[rang]
    assert len(first_previz_page.frame_zones) == len(first_plan_page.frames)
    zone = first_previz_page.frame_zones[0]
    slot = first_plan_page.frames[0]
    assert (zone.x_mm, zone.y_mm, zone.w_mm, zone.h_mm) == slot.zone_rect_mm
    assert (
        zone.image_x_mm, zone.image_y_mm, zone.image_w_mm, zone.image_h_mm
    ) == slot.image_rect_mm
    assert zone.letterbox_policy == slot.letterbox_policy
    assert first_previz_page.qr.symbol_size_mm == first_plan_page.qr.print_size_mm
    assert len(first_previz_page.aruco_markers) == len(first_plan_page.markers)
    assert first_previz_page.aruco_markers[0].center_x_mm == (
        first_plan_page.markers[0].center_x_mm
    )
    assert len(first_previz_page.patches) == len(first_plan_page.patches)
    assert first_previz_page.patches[0].rgb == first_plan_page.patches[0].rgb
    assert len(first_previz_page.slot_labels) == len(first_plan_page.text.slot_labels)
    # Et la forme normative se serialise sans objet Python residuel.
    import json

    json.dumps(pdf_previz.pdf_previz_to_json_dict(document))


# --- Story 5.9: preset sentinelle, ambiguite de cardinal, cadre imprime -----


def test_sentinel_preset_resolves_by_id_and_by_cardinal() -> None:
    assert pdf_composition.resolve_patch_preset("patches-18-v2") == "patches-18-v2"
    assert pdf_composition.resolve_patch_preset("18") == "patches-18-v2"
    assert pdf_composition.resolve_patch_preset(18) == "patches-18-v2"


def test_le_defaut_est_le_preset_temoin_et_il_porte_ses_sentinelles() -> None:
    """`EPIC5-ARB-67`: le defaut passe a `patches-14-v3`, **globalement**.

    Ce que ce test verrouille n'est pas le litteral mais la **propriete** qui a motive
    l'arbitrage: le preset compose par defaut doit rendre le verdict d'ecretage
    calculable. Sous l'ancien defaut `patches-12-v1`, `sentinel_chains` rendait un jeu
    **vide** -- le defaut produisait la seule configuration ou la calibration ne peut pas
    fonctionner (bloquant B2 de la couche 3 de la revue de 5.16).

    Le defaut est **global** et non conditionnel a la version de geometrie: le preset est
    place sur les 63 gabarits du registre, donc un defaut unique suffit, et un defaut
    conditionnel aurait cree une seconde regle a maintenir au menage d'`EPIC5-ARB-66`.
    """
    from mixed_media_utility import patch_presets

    #
    # **Amende par la story 5.23** (`EPIC5-ARB-82`): le defaut passe a `patches-17-v4`,
    # meme jeu plus les trois secondaires. La propriete verrouillee par ce test ne change
    # pas d'un mot -- le defaut doit rendre le verdict d'ecretage calculable et etre
    # composable partout --, et les assertions qui la portent ci-dessous sont conservees
    # telles quelles: c'est bien elles, et non le litteral, qui motivaient l'arbitrage.
    assert pdf_composition.DEFAULT_PATCH_PRESET == "patches-17-v4"
    assert pdf_composition.resolve_patch_preset(None) == "patches-17-v4"
    # La propriete, derivee du registre: le defaut porte les sentinelles de gamut.
    assert pdf_composition.DEFAULT_PATCH_PRESET in (
        patch_presets.gamut_sentinel_preset_ids())
    # Et il est composable partout, ce qui est la condition d'un defaut **global**:
    # `patches-18-v2`, l'autre preset a sentinelles, ne l'est pas en paysage v2.
    refuses = {
        preset_id
        for _version, _orientation, preset_id in patch_presets.unplaceable_couples()
    }
    assert pdf_composition.DEFAULT_PATCH_PRESET not in refuses
    assert "patches-18-v2" in refuses


def test_unknown_cardinal_names_every_available_cardinal() -> None:
    with pytest.raises(pdf_composition.ParameterVocabularyError) as excinfo:
        pdf_composition.resolve_patch_preset("7")
    message = str(excinfo.value)
    # Les cardinaux sont enumeres **dynamiquement**: le litteral « (9, 12) »
    # aurait menti des l'arrivee du troisieme preset.
    for cardinal in ("9", "12", "18", "17"):
        assert cardinal in message


def test_ambiguous_cardinal_is_refused_instead_of_letting_dict_order_decide() -> None:
    # AC 10, finding deja consigne au backlog: la resolution par cardinal
    # rendait le **premier** preset du registre. Les cardinaux livres restent
    # uniques (9, 12, 18), donc le cas n'est pas atteignable a l'execution --
    # raison de plus pour le fermer maintenant, pendant qu'aucun comportement
    # observable n'en depend. Le doublon est donc injecte pour le test.
    twin = patch_presets.PatchPreset(
        preset_id="patches-12-v9",
        values_version="patch-values-1",
        value_ids=patch_presets.get_patch_preset("patches-12-v1").value_ids,
        repetition=2,
    )
    patch_presets._PRESETS["patches-12-v9"] = twin
    try:
        with pytest.raises(pdf_composition.ParameterVocabularyError) as excinfo:
            pdf_composition.resolve_patch_preset("12")
        message = str(excinfo.value)
        assert "ambigu" in message
        assert "patches-12-v1" in message and "patches-12-v9" in message
        # Designer par identifiant reste possible et non ambigu.
        assert pdf_composition.resolve_patch_preset("patches-12-v1") == "patches-12-v1"
    finally:
        del patch_presets._PRESETS["patches-12-v9"]


def test_printed_frame_path_stays_strictly_inside_the_patch() -> None:
    """Le trait occupe exactement [0, frame_mm] depuis chaque bord (AC 5).

    reportlab centre le trait sur le chemin: un rectangle trace sur l'emprise
    deborderait d'une demi-epaisseur et mangerait l'espacement inter-pastilles.
    Le depot ne rasterise pas ses PDF, donc sans ce test un cadre pose au
    mauvais endroit ne serait visible nulle part.
    """
    placed = patch_presets.resolve_patch_layout(
        patch_presets.TEMPLATE_A4_PORTRAIT_2F, "patches-18-v2"
    )
    framed = [patch for patch in placed if patch.frame_mm]
    assert framed, "la sentinelle blanche doit porter un cadre"

    for patch in framed:
        x_mm, y_mm, side_mm = pdf_render.patch_frame_path_mm(patch)
        half = patch.frame_mm / 2.0
        # Bord exterieur du trait: exactement le bord du patch.
        assert x_mm - half == pytest.approx(patch.x_mm)
        assert y_mm - half == pytest.approx(patch.y_mm)
        assert x_mm + side_mm + half == pytest.approx(patch.x_mm + patch.size_mm)
        assert y_mm + side_mm + half == pytest.approx(patch.y_mm + patch.size_mm)
        # Bord interieur du trait: a frame_mm du bord du patch, donc trois
        # millimetres au moins avant le carre echantillonne.
        inner = x_mm + half
        assert inner - patch.x_mm == pytest.approx(patch.frame_mm)
        assert patch.frame_mm < patch_presets.SAMPLING_INSET_MM


def test_makepdf_emits_exactly_the_identity_gamut_map(tmp_path) -> None:
    """Mutant survivant en revue (5.9-C1-2): la seule valeur reellement emise
    en production n'etait verifiee nulle part.

    La remplacer par `gamut-map-perceptual-1` ne cassait rien -- et une planche
    aurait alors declare une compression jamais appliquee, que le scan aurait
    tente de decomprimer. `makepdf` n'applique aucune compression au MVP:
    l'identite est la seule valeur juste, et elle doit etre epinglee au point
    d'emission, pas seulement dans le contrat du payload.
    """
    assert pdf_composition.DEFAULT_GAMUT_MAP == "gamut-map-none-1"
    assert pdf_composition.payload_io.GAMUT_MAP_IDENTITY == "gamut-map-none-1"

    # AMENDE PAR LA STORY 5.10 (AC 6 et 7). L'intention du test ne change pas
    # -- « la seule valeur reellement emise en production est verifiee » --
    # mais la forme le devait: 5.9 emettait la constante d'identite en dur, ce
    # qui etait juste tant qu'aucune compression n'existait. Depuis 5.10,
    # `makepdf` peut en appliquer une, et l'emission doit venir de la variable
    # locale **resolue une seule fois**, pas d'un litteral -- c'est precisement
    # cette source unique qui garantit que le QR ne ment pas sur la `G`
    # appliquee au raster. Le test verifie donc desormais que les deux points
    # d'emission (payload et plan) portent **la meme variable**, et que le
    # defaut de cette variable reste l'identite.
    source = ast.parse(
        (REPO_ROOT / "src" / "mixed_media_utility" / "pdf_composition.py").read_text(
            encoding="utf-8"
        )
    )
    emitted = [
        node
        for node in ast.walk(source)
        if isinstance(node, ast.keyword) and node.arg == "gamut_map_id"
    ]
    # **6 depuis la story 5.22**, apres le 4 de 5.16. Le detail, parce qu'un cardinal nu
    # ne se re-verifie pas: les deux producteurs de payload (planche d'images et page de
    # calibration), les deux plans rendus (`LotComposition` du lot et de la page de
    # calibration seule), le champ resolu de `_ResolvedParameters`, et le passage de
    # `compose_calibration_page_plan` a `_calibration_page_plan`.
    #
    # La propriete que ce test protege ne change pas et compte davantage a chaque point
    # ajoute: chacun porte la **variable resolue une seule fois**, jamais un litteral,
    # sans quoi le QR d'une page mentirait sur la `G` appliquee a son raster. Les points
    # de simple transport comptent donc autant que les points d'emission -- un transport
    # qui glisserait un litteral est exactement le defaut vise.
    #
    # Le cardinal est asserte pour que l'ajout d'un point oblige a passer ici: c'est le
    # seul endroit du depot ou cette regle se verifie.
    assert len(emitted) == 6, "les deux payloads, les deux plans, le champ resolu, le transport"
    # Le nom est **le meme** aux six points, y compris entre les deux fonctions de
    # composition: c'est ce qui rend la resolution unique ci-dessous suffisante. La valeur
    # **brute** de l'option, elle, s'appelle `gamut_map` (comme `patch_preset` en face de
    # `patch_preset_id`), donc elle n'est jamais comptee ici -- et c'est voulu: le suffixe
    # `_id` est ce qui distingue « resolu » de « tel que l'operateur l'a tape ».
    for keyword in emitted:
        assert isinstance(keyword.value, ast.Name), ast.dump(keyword.value)
        assert keyword.value.id == "gamut_map_id", ast.dump(keyword.value)
    # ... et cette variable est le resultat d'une resolution unique.
    resolutions = [
        node
        for node in ast.walk(source)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "resolve_gamut_map"
    ]
    assert len(resolutions) == 1, "une seule resolution dans tout le module"

    # Et de bout en bout: sans option, le defaut est l'identite sur toutes les
    # pages -- l'AST ne dit rien de la valeur reellement emise.
    plan = compose()
    assert plan.gamut_map_id == "gamut-map-none-1"
    for page in plan.pages:
        assert page.qr.payload["gamut_map_id"] == plan.gamut_map_id


def test_sampling_geometry_constants_are_pinned_to_their_arbitrated_values() -> None:
    """Mutant survivant en revue (5.9-C1-3): la geometrie d'echantillonnage
    n'etait epinglee que par des relations, pas par des valeurs.

    `test_sampled_squares_stay_clear_of_every_printed_edge` verifie
    `sx1 - patch.x_mm == inset` alors que `sx1` vaut `patch.x_mm + inset`:
    tautologique. Le seul lien reel etait `inset - frame == 2.0`, que le couple
    `inset=5.5 / frame=3.5` satisfait aussi -- et le carre echantillonne tombait
    alors de 6,0 a 1,0 mm, soit 24 px a 600 dpi au lieu de 142, sans qu'un seul
    test ne bronche.

    Les trois chiffres sont arbitres (EPIC5-ARB-17(a)) et se lisent comme tels.
    Le plancher en pixels est la raison d'etre du chiffre: en dessous, la
    moyenne par pastille n'a plus de sens statistique.
    """
    assert patch_presets.SAMPLING_INSET_MM == 3.0
    assert patch_presets.SAMPLED_SIDE_MM == 6.0
    assert patch_presets.PATCH_FRAME_MM == 1.0

    # Plancher exploitable: meme au premier repli documente (retrait porte a
    # 4,0 mm), le carre doit rester mesurable a la resolution de scan minimale.
    scan_dpi = qr_codes.QR_MIN_SCAN_DPI
    sampled_px = patch_presets.SAMPLED_SIDE_MM / 25.4 * scan_dpi
    assert sampled_px >= 100, f"{sampled_px:.0f} px de cote a {scan_dpi} dpi"
    fallback_side_mm = patch_presets.PATCH_SIZE_MM - 2 * 4.0
    assert fallback_side_mm / 25.4 * scan_dpi >= 90, "le premier repli doit rester exploitable"


def test_the_sentinel_column_geometry_is_pinned_including_its_two_tangencies() -> None:
    """Les deux tangences du preset sentinelle sont des choix, pas des accidents.

    (1) La premiere colonne est posee **exactement** sur `PRINTER_MARGIN_MM`:
    36 pastilles ne tiennent pas autrement, et « aucune encre a moins de 5 mm
    du bord » est respecte par 5,0. C'est sur en binaire.
    (2) La colonne droite paysage a ete **ecartee** de la bande de frames
    (249 -> 252) parce que ce bord-la vaut `249.00000000000003`: une tangence a
    une valeur issue d'une division par trois ne l'est pas.
    Ce test epingle les deux faits ensemble, pour qu'on ne lise pas la premiere
    comme un oubli de la seconde.
    """
    assert patch_presets._SENTINEL_PORTRAIT_COLUMNS_X_MM == (5.0, 19.0, 177.0, 191.0)
    assert patch_presets._SENTINEL_PAYSAGE_COLUMNS_X_MM == (5.0, 19.0, 33.0, 252.0, 266.0, 280.0)
    assert patch_presets._SENTINEL_PORTRAIT_ROWS * len(
        patch_presets._SENTINEL_PORTRAIT_COLUMNS_X_MM
    ) == patch_presets.MAX_PATCHES_PER_PAGE
    assert patch_presets._SENTINEL_PAYSAGE_ROWS * len(
        patch_presets._SENTINEL_PAYSAGE_COLUMNS_X_MM
    ) == patch_presets.MAX_PATCHES_PER_PAGE

    # (1) Tangence exacte, cote marge d'imprimante.
    assert patch_presets._SENTINEL_PORTRAIT_COLUMNS_X_MM[0] == layout.PRINTER_MARGIN_MM
    # (2) Ecart reel, cote bande de frames: la mesure qui l'impose.
    # Bande de la **v1**: ce sont les colonnes litterales de la v1 qui sont epinglees
    # ici, et c'est son bord de bande a 249.00000000000003 qui impose l'ecart.
    paysage_band = page_templates.frame_band_mm(page_templates.ORIENTATION_PAYSAGE, "v1")
    band_right_edge = paysage_band["x"] + paysage_band["width"]
    assert patch_presets._SENTINEL_PAYSAGE_COLUMNS_X_MM[3] - band_right_edge >= 2.0


def test_the_sentinel_reading_chains_stay_contiguous_in_every_column() -> None:
    """`_ORDER_18` n'etait epingle par rien (revue: mutant coupant une chaine,
    suite verte).

    La contiguite est declaree « une contrainte a tenir en reordonnant »: les
    trois niveaux d'une meme chaine se lisent comme une rampe sur la planche, et
    un ecretage grossier devient visible sans instrument. Une chaine coupee
    entre deux colonnes perd cette lisibilite en silence.
    """
    chains = (
        ("primary-red", "sentinel-red-1", "sentinel-red-2"),
        ("primary-green", "sentinel-green-1", "sentinel-green-2"),
        ("primary-blue", "sentinel-blue-1", "sentinel-blue-2"),
        ("neutral-020", "sentinel-black-1"),
        ("neutral-245", "sentinel-white-1"),
    )
    order = patch_presets._ORDER_18
    assert len(order) == 18 and len(set(order)) == 18

    for chain in chains:
        positions = [order.index(value_id) for value_id in chain]
        assert positions == sorted(positions), chain
        assert positions[-1] - positions[0] == len(chain) - 1, (chain, positions)

    # Et la decoupe en colonnes ne coupe aucune chaine.
    for columns in (patch_presets._SENTINEL_PORTRAIT_COLUMNS, patch_presets._SENTINEL_PAYSAGE_COLUMNS):
        assert tuple(v for column in columns for v in column) == order
        for chain in chains:
            owners = {
                index for index, column in enumerate(columns) if set(chain) & set(column)
            }
            assert len(owners) == 1, (chain, owners)


def test_the_white_sentinel_frame_is_actually_stroked_by_the_renderer() -> None:
    """Le trace du cadre n'etait appele par aucun test (revue: mutant
    supprimant le bloc `if patch.frame_mm`, suite verte).

    Le depot ne rasterise pas ses PDF, mais un faux canvas suffit a prouver que
    l'instruction de trace part, avec la bonne epaisseur et au bon endroit.
    Sans cela, la sentinelle blanche serait invisible sur la planche et rien ne
    le dirait.
    """

    class RecordingCanvas:
        def __init__(self) -> None:
            self.rects: list[tuple] = []
            self.line_widths: list[float] = []

        def rect(self, x, y, width, height, stroke=0, fill=1):
            self.rects.append((x, y, width, height, stroke, fill))

        def setLineWidth(self, width):  # noqa: N802 - API reportlab
            self.line_widths.append(width)

        def setFillColorRGB(self, *_args):  # noqa: N802
            pass

        def setStrokeColorRGB(self, *_args):  # noqa: N802
            pass

    placed = patch_presets.resolve_patch_layout(
        patch_presets.TEMPLATE_A4_PORTRAIT_2F, "patches-18-v2"
    )
    framed = next(patch for patch in placed if patch.frame_mm)

    canvas = RecordingCanvas()
    pdf_render.draw_patch(canvas, framed, page_height_mm=297.0)

    stroked = [entry for entry in canvas.rects if entry[4]]
    filled = [entry for entry in canvas.rects if entry[5]]
    assert len(filled) == 1, "la pastille elle-meme est remplie"
    assert len(stroked) == 1, "et son cadre est trace"
    assert canvas.line_widths == [framed.frame_mm * mm]
    # Le chemin du cadre est rentre d'une demi-epaisseur: le trait tombe alors
    # exactement dans l'emprise.
    assert stroked[0][2] == pytest.approx((framed.size_mm - framed.frame_mm) * mm)

    # Une pastille ordinaire ne trace aucun cadre.
    plain = next(patch for patch in placed if not patch.frame_mm)
    canvas = RecordingCanvas()
    pdf_render.draw_patch(canvas, plain, page_height_mm=297.0)
    assert [entry for entry in canvas.rects if entry[4]] == []
    assert canvas.line_widths == []


# --- Derivation de la bande de frames (chantier du 2026-08-10) ----------------

def test_frame_bands_are_derived_and_match_the_historical_literals() -> None:
    """Non-regression **valeur par valeur** contre les litteraux d'avant la derivation.

    Le `template_id` est un contrat de geometrie, pas une etiquette: si la derivation
    deplacait une bande d'un dixieme de millimetre, toute planche deja imprimee
    cesserait d'etre decoupee au bon endroit, sans qu'aucune erreur soit levee. La
    comparaison porte sur `_HISTORICAL_FRAME_BANDS_MM`, **fige dans le fichier**, et non
    sur un recalcul: comparer la derivation a elle-meme ne verrouillerait rien.
    """
    for orientation, historical in page_templates._HISTORICAL_FRAME_BANDS_MM.items():
        derived = page_templates.GEOMETRY_V1.frame_band_mm(orientation)
        assert set(derived) == set(historical)
        for key, value in historical.items():
            assert derived[key] == pytest.approx(value, abs=1e-12), (
                f"{orientation}.{key}: derive {derived[key]} contre historique {value}")


def test_patch_geometry_constants_mirror_patch_presets() -> None:
    """`patch_presets` importe ce registre, donc le registre ne peut pas l'importer.

    Meme motif que `test_marker_geometry_constants_mirror_layout`. Sans ce verrou, la
    bande de frames serait calculee sur une taille de pastille perimee et se
    decalerait **silencieusement** au premier changement de `patch_presets`.
    """
    from mixed_media_utility import patch_presets

    assert page_templates.PATCH_SIZE_MM == patch_presets.PATCH_SIZE_MM
    assert page_templates.PATCH_SPACING_MM == patch_presets.PATCH_SPACING_MM


@pytest.mark.parametrize("field, value, moves, wider", [
    # Les trois termes du degagement de coin: on les REDUIT, la bande grandit.
    ("marker_size_mm", 15.0, "height", True),
    ("marker_margin_mm", 8.0, "height", True),
    ("marker_quiet_zone_mm", 5.0, "height", True),
    # Geometrie des pastilles: une pastille plus petite ou posee plus pres du bord
    # rend de la largeur...
    ("patch_size_mm", 6.0, "width", True),
    ("printer_margin_mm", 2.0, "width", True),
    # ...mais un ECART plus grand elargit le bloc, donc RETRECIT la bande. Le sens est
    # verifie explicitement plutot que « la bande bouge »: un test qui n'exigerait qu'un
    # mouvement passerait avec une derivation dont un signe est inverse.
    ("patch_spacing_mm", 3.0, "width", False),
])
def test_each_constituent_actually_moves_the_band(field, value, moves, wider) -> None:
    """**Le test qui distingue « derive » de « a l'air derive ».**

    Avant le 2026-08-10, la bande etait ecrite en litteral: reduire la taille des
    marqueurs ne reduisait aucune marge, et rien ne le signalait. Une derivation qui
    lirait une valeur figee a l'import aurait exactement le meme defaut tout en
    paraissant correcte -- c'est arrive une fois pendant l'ecriture, sur une constante
    de degagement calculee au chargement du module.

    Chaque constituant est donc verifie individuellement, et sur la dimension qu'il est
    cense porter: les trois termes du degagement de coin bornent la **hauteur**, la
    geometrie des pastilles borne la **largeur**. La variante est construite par
    `dataclasses.replace` et non par monkeypatch d'une constante du module: depuis le
    2026-08-11 la geometrie est un objet fige porte par le `template_id`, et une
    constante du module changee a l'execution ne doit precisement plus rien deplacer
    (c'est l'objet du test suivant).
    """
    before = page_templates.GEOMETRY_V1.frame_band_mm(page_templates.ORIENTATION_PORTRAIT)
    variant = dataclasses.replace(page_templates.GEOMETRY_V1, **{field: value})
    after = variant.frame_band_mm(page_templates.ORIENTATION_PORTRAIT)
    if wider:
        assert after[moves] > before[moves], (
            f"{field} = {value} devrait elargir la bande en {moves}: "
            f"{before[moves]} -> {after[moves]}")
    else:
        assert after[moves] < before[moves], (
            f"{field} = {value} devrait retrecir la bande en {moves}: "
            f"{before[moves]} -> {after[moves]}")
    # Et il ne doit PAS bouger l'autre dimension: un constituant qui deplacerait les
    # deux melangerait deux leviers et rendrait l'optimisation non attribuable.
    other = "width" if moves == "height" else "height"
    assert after[other] == pytest.approx(before[other])


def test_the_registry_is_not_perturbed_by_a_late_constant_change(monkeypatch) -> None:
    """Le registre est calcule **a l'import**, et c'est voulu.

    Changer une constante du module a l'execution ne doit PAS deplacer les gabarits
    deja resolus: un `template_id` designe une geometrie figee, et un registre mutable
    rendrait deux executions du meme code non comparables. Depuis le 2026-08-11 la
    garantie est structurelle et non plus circonstancielle -- `GEOMETRY_V1` a copie les
    constantes a l'import -- mais elle reste verrouillee ici: c'est la propriete dont
    depend la lisibilite d'une planche imprimee avant un resserrement.
    """
    spec_before = page_templates.get_template(page_templates.TEMPLATE_A4_PORTRAIT_2F)
    monkeypatch.setattr(page_templates, "MARKER_SIZE_MM", 10.0)
    spec_after = page_templates.get_template(page_templates.TEMPLATE_A4_PORTRAIT_2F)
    assert spec_before.frame_zones_mm == spec_after.frame_zones_mm
    assert spec_after.geometry.marker_size_mm == 30.0


# --- Geometrie versionnee portee par le template_id (chantier du 2026-08-11) ---

@pytest.fixture()
def tightened_geometry(monkeypatch):
    """Enregistrer une version de geometrie resserree, le temps d'un test.

    Reproduit ce que fera l'etape 2 du chantier: **ajouter** une version, jamais
    redefinir v1. Le registre etant calcule a l'import, la fixture le reconstruit.
    """
    geometry = dataclasses.replace(
        page_templates.GEOMETRY_V1,
        version="vtest",
        marker_size_mm=15.0,
        marker_margin_mm=8.0,
        marker_quiet_zone_mm=5.0,
        printer_margin_mm=3.0,
    )
    versions = types.MappingProxyType(
        {**page_templates.GEOMETRY_VERSIONS, geometry.version: geometry}
    )
    monkeypatch.setattr(page_templates, "GEOMETRY_VERSIONS", versions)
    monkeypatch.setattr(page_templates, "_REGISTRY", page_templates._build_registry())
    return geometry


def test_a_new_geometry_version_adds_templates_and_redefines_none(
        tightened_geometry) -> None:
    """Le contrat de l'en-tete 4.1, enfin verrouille.

    « Toute modification de geometrie est un nouvel identifiant, jamais une
    redefinition silencieuse »: la promesse existait depuis la story 4.1, mais le
    suffixe `-v1` etait une chaine ecrite en dur et la geometrie se lisait dans les
    constantes globales. Reduire les marqueurs -- l'objet du chantier -- redefinissait
    donc les 33 gabarits d'un coup, dont ceux de planches deja imprimees et pas encore
    scannees.
    """
    v1_spec = page_templates.get_template(page_templates.TEMPLATE_A4_PORTRAIT_2F)
    assert v1_spec.geometry_version == "v1"
    # v1 est intact au millimetre pres, malgre la version ajoutee.
    for orientation, historical in page_templates._HISTORICAL_FRAME_BANDS_MM.items():
        band = page_templates.frame_band_mm(orientation, "v1")
        for key, value in historical.items():
            assert band[key] == pytest.approx(value, abs=1e-12)
    # Et la nouvelle version a bien ses propres identifiants, resolubles.
    new_id = page_templates.build_template_id("portrait", 2, "0", "vtest")
    assert new_id == "tpl-a4-portrait-2f-vtest"
    assert new_id != page_templates.TEMPLATE_A4_PORTRAIT_2F
    new_spec = page_templates.get_template(new_id)
    assert new_spec.geometry_version == "vtest"
    # La bande resserree rend de la place: c'est tout l'objet du chantier.
    assert new_spec.frame_zones_mm[0]["height"] > v1_spec.frame_zones_mm[0]["height"]


def test_an_unknown_geometry_version_is_refused_and_never_guessed() -> None:
    """Meme regle que pour un `template_id` inconnu (contrat 4.5).

    Refuse a la **fabrication** de l'identifiant et non seulement a sa resolution:
    sinon `build_template_id` rendrait une chaine d'apparence normale que
    `get_template` rejetterait ensuite sans nommer la cause.
    """
    with pytest.raises(page_templates.UnknownTemplateError, match="vtest"):
        page_templates.build_template_id("portrait", 2, "0", "vtest")
    with pytest.raises(page_templates.UnknownTemplateError, match="v99"):
        page_templates.get_geometry("v99")


@pytest.mark.parametrize("consumer", ["corners", "qr_band", "printed_marker_size"])
def test_every_geometry_consumer_reads_the_spec_and_not_the_module(
        tightened_geometry, consumer) -> None:
    """**Le test qui distingue une geometrie versionnee d'une facade.**

    Une version portee par le `template_id` mais dont les consommateurs continuent de
    lire les constantes globales ne protege rien: la page `vtest` serait composee avec
    les marqueurs de `v1`, et le scan chercherait les coins la ou ils ne sont pas.
    C'est le meme defaut que la « derivation » a moitie fausse trouvee la veille, une
    couche plus haut -- donc verifie consommateur par consommateur.
    """
    v1_spec = page_templates.get_template(page_templates.TEMPLATE_A4_PORTRAIT_2F)
    new_spec = page_templates.get_template(
        page_templates.build_template_id("portrait", 2, "0", "vtest")
    )
    if consumer == "corners":
        # Marqueur plus petit et pose plus pres du bord: le centre se rapproche.
        v1_near = page_templates.corner_marker_centers_mm(v1_spec)[0]
        new_near = page_templates.corner_marker_centers_mm(new_spec)[0]
        assert new_near[0] < v1_near[0] and new_near[1] < v1_near[1]
    elif consumer == "qr_band":
        # Silence de coin plus court: la bande haute s'ouvre plus large et plus haut.
        v1_band = pdf_composition._qr_band_mm(v1_spec)
        new_band = pdf_composition._qr_band_mm(new_spec)
        assert new_band[0] < v1_band[0]
        assert new_band[2] > v1_band[2]
        assert new_band[1] < v1_band[1]
    else:
        assert tightened_geometry.marker_size_mm != page_templates.MARKER_SIZE_MM
        assert new_spec.geometry.marker_size_mm == tightened_geometry.marker_size_mm


@pytest.mark.parametrize("orientation", list(page_templates.ORIENTATIONS))
def test_the_footer_zones_follow_the_geometry_of_every_registered_version(
        orientation) -> None:
    """Le pied de page suit la geometrie de **chaque** version enregistree (5.15, AC 4).

    Ce test etait un verrou a declenchement differe: `_footer_zones_mm` rendait deux
    litteraux par orientation, qui coincidaient avec le degagement de coin de la v1
    (x = 60, largeur = page - 2 x 60), si bien que rien ne distinguait « derive » de
    « recopie ». Il a fait ce qu'on lui demandait: il est tombe au premier ajout de
    version, et la derivation a suivi.

    **Ce qu'il a fallu corriger dans son enonce, et c'est une mesure.** Sa troisieme
    assertion exigeait que le bloc ouvre *sous* le silence des marqueurs du bas
    (y >= page - degagement). Vraie en v1, ou 69,5 mm de bord bas logent un bloc de
    45 mm; **impossible** sous la v2, dont le degagement de coin (28 mm) est plus petit
    que ce que le texte exige (36,5 mm de bloc, plus la consigne de scan et la bande
    des etiquettes de slot). Le bord bas y est borne par le **texte**, pas par les
    marqueurs -- c'est le `max` d'`EPIC5-ARB-56` point 1. L'invariant reel, qui vaut
    pour les deux versions, est celui verifie ci-dessous: la pile de pied de page est
    entierement **hors de la bande de frames** et dans la zone imprimable.
    """
    for geometry in page_templates.GEOMETRY_VERSIONS.values():
        spec = page_templates.template_for(orientation, 2, "0", geometry.version)
        clearance = geometry.corner_clearance_mm()
        zones = pdf_composition._footer_zones_mm(spec)
        band = spec.frame_band_mm
        band_bottom = band["y"] + band["height"]
        # **Largeur attendue: ce que le pied peut occuper, QR compris s'il est la.**
        # Depuis la story 5.18 le QR peut prendre le bord bas, et il s'y pose **a cote**
        # du pied de page. Exiger la pleine largeur ferait donc soit tomber ce test,
        # soit -- pire -- passer sur un pied qui recouvre le QR. La borne verifiee reste
        # une egalite, pas une inegalite: le pied prend tout ce qui reste, ni plus ni
        # moins.
        available = spec.page_width_mm - 2 * clearance
        if spec.qr_edge == page_templates.QR_EDGE_BOTTOM:
            available -= (page_templates.qr_footprint_bound_mm()
                          + page_templates.TEXT_GAP_MM)
        for name in ("footer_block", "footer_line"):
            x, y, width, height = zones[name]
            assert x == pytest.approx(clearance), (
                f"{geometry.version}/{orientation}/{name}: le pied de page ouvre a "
                f"x = {x} alors que le silence des marqueurs s'arrete a {clearance}.")
            assert width == pytest.approx(available)
            # Hors de la bande de frames, et de la bande d'etiquettes qui la suit.
            assert y >= band_bottom + page_templates.SLOT_LABEL_STRIP_MM - 1e-9, (
                geometry.version, orientation, name)
            # Dans la zone imprimable.
            assert y + height <= (
                spec.page_height_mm - geometry.printer_margin_mm + 1e-9)
        # Les deux zones ne se recouvrent pas, et la consigne de scan est **sous** le
        # bloc d'identite: leur ordre est une propriete de lecture de la planche.
        assert not rects_overlap(zones["footer_block"], zones["footer_line"])
        assert zones["footer_line"][1] > zones["footer_block"][1]


def test_a_geometry_version_without_patch_placements_fails_loudly() -> None:
    """Les pastilles, elles, ne peuvent pas deriver en silence -- et c'est acquis.

    `patch_presets` place ses colonnes par couple (template_id, preset_id) avec des
    abscisses litterales. Un `template_id` d'une version non encore placee n'a donc
    aucune entree, et la resolution leve `UndefinedPlacementError` au lieu de rendre
    les colonnes de v1. C'est la propriete qui rend l'ajout d'une version sur, et non
    un hasard du registre: elle est verrouillee ici pour qu'un futur repli sur un
    placement par defaut soit refuse par les tests.
    """
    unplaced = "tpl-a4-portrait-2f-vtest"
    assert unplaced not in patch_presets._covered_template_ids()
    with pytest.raises(patch_presets.UndefinedPlacementError):
        patch_presets.resolve_patch_layout(unplaced, "patches-12-v1")


def test_the_v1_qr_band_is_unchanged_by_its_derivation() -> None:
    """Non-regression valeur par valeur des deux nombres qui etaient en litteral.

    `_TOP_BAND_Y_MM = 5` et `_TOP_BAND_HEIGHT_MM = 50` sont devenus des derivees de la
    geometrie du spec; a geometrie v1 ils doivent redonner exactement 5 et 50, sans
    quoi l'emprise du QR de toute planche deja imprimee serait jugee contre une autre
    bande que celle qui a servi a la composer.
    """
    for template_id in (page_templates.TEMPLATE_A4_PORTRAIT_2F,
                        "tpl-a4-paysage-4f-v1"):
        spec = page_templates.get_template(template_id)
        _, y, _, height = pdf_composition._qr_band_mm(spec)
        assert y == pytest.approx(5.0)
        assert height == pytest.approx(50.0)


def test_a_banned_symbol_version_names_the_version_and_not_the_millimetres(
    monkeypatch,
) -> None:
    """Le refus nomme la **cause reelle** (majeur M9 de la revue de 5.17).

    Le motif ne nommait que la taille imprimee et le dpi de scan -- les deux grandeurs
    qui, pour une version de symbole bannie, sont precisement hors de cause. Le premier
    reflexe qu'il inspire, imprimer plus grand, est sans effet: `check_print_geometry`
    le dit dans sa propre docstring, mais l'operateur ne lit pas les docstrings, il lit
    le message.

    Le ban est **deplace** sur la version que la page nominale atteint, plutot que de
    fabriquer un payload assez lourd pour tomber sur la 22: le vocabulaire des cardinaux
    ne l'atteint plus (c'est l'AC 5 de la story), et la branche resterait donc
    inatteignable par une page composable. C'est la garde qu'on exerce ici, pas la
    frontiere.
    """
    # La premiere **planche d'images**, et non `pages[0]`: celle-la est la page de
    # calibration depuis la story 5.16, dont le payload est le plus leger du lot donc le
    # symbole le plus petit. Bannir sa version ferait refuser la page de calibration et
    # non la planche, et c'est le refus de la planche qu'on eprouve ici -- celui dont
    # `--frames-par-page` est la sortie.
    module_side = images_pages(compose())[0].qr.module_side
    version = qr_codes.symbol_version(module_side)
    monkeypatch.setattr(qr_codes, "QR_BANNED_SYMBOL_VERSIONS", frozenset({version}))

    with pytest.raises(pdf_composition.GeometryOverflowError) as excinfo:
        compose()
    message = str(excinfo.value)
    assert f"version {version}" in message, message
    assert f"{module_side} modules" in message, message
    # La cause nommee, et l'action qui n'en est pas une.
    assert "AUCUNE taille imprimee" in message, message
    assert "Imprimer plus grand n'y change rien" in message, message
    assert "--frames-par-page" in message, message
    # Le domaine non monotone est dit: reduire n'est pas toujours la bonne sortie.
    assert "monotone" in message, message
    # Et il ne nomme plus les millimetres de la taille imprimee, qui sont hors de cause.
    assert "mm a" not in message, message


def test_an_unusable_ratio_keeps_naming_the_print_size_and_the_dpi(monkeypatch) -> None:
    """L'autre branche du refus reste celle qu'elle etait: la garde s'ajoute, elle ne
    remplace pas.

    Un verdict `unusable` **hors** version bannie a bien pour cause les px/module, et
    son motif doit continuer de nommer les millimetres et le dpi. Sans ce test, un
    correctif de message qui aurait avale les deux cas aurait passe le precedent.
    """
    monkeypatch.setattr(qr_codes, "QR_BANNED_SYMBOL_VERSIONS", frozenset())
    monkeypatch.setattr(
        qr_codes, "MIN_PIXELS_PER_MODULE_DEGRADED", 10_000.0)
    monkeypatch.setattr(
        qr_codes, "MIN_PIXELS_PER_MODULE_RELIABLE", 20_000.0)
    with pytest.raises(pdf_composition.GeometryOverflowError) as excinfo:
        compose()
    message = str(excinfo.value)
    assert "geometrie QR inutilisable" in message, message
    assert "dpi de scan" in message, message
    assert "Reduire --frames-par-page" in message, message


# ---------------------------------------------------------------------------
# Passe de correction de la story 5.18 -- les dix survivants de la campagne de
# cloture (`scripts/archive/mutation/campagne_5_18.py`).
#
# Chacun etait un test manquant, aucun n'etait un defaut de geometrie. Ils sont
# groupes par mecanisme, comme la revue les a groupes: l'entete et le QR du bord
# haut (`F08`), la troncature silencieuse d'identifiant (`F09`, `G12`), la perte
# d'une ligne technique (`G13`), la place de la date (`H01`, `H02`), et la
# derivation de bande du QR de flanc (`K07`, `K10`, `K11`, `K12`).
# ---------------------------------------------------------------------------


def _top_edge_spec(orientation="portrait", cardinal=2):
    """Gabarit v2 dont le QR est **au bord haut**, construit et non trouve.

    Aucun gabarit livre ne met le QR au bord haut -- c'est demontre ailleurs, le bord bas
    etant toujours au moins aussi bon. La percussion entre l'entete d'identite et le QR
    ne se voit donc que sur un gabarit **construit**, ce qui est exactement le motif du
    gabarit a 60 pt qui prouve la comparaison des bords: sans lui, la branche du partage
    de bande haute n'est jamais exercee.
    """
    spec = page_templates.template_for(orientation, cardinal, "0", "v2")
    assert spec.qr_edge != page_templates.QR_EDGE_TOP, "le livre ne met plus le QR en haut"
    return dataclasses.replace(spec, qr_edge=page_templates.QR_EDGE_TOP)


def test_the_identity_header_never_covers_the_qr_when_the_qr_takes_the_top_band() -> None:
    """**`F08`, le plus important des dix survivants de la campagne de cloture.**

    La story 5.18 introduit **et** l'entete d'identite **et** le choix du bord porteur du
    QR: ce sont les deux elements nouveaux qui peuvent se percuter, et rien ne le testait.
    Le mutant `F08` (« l'entete d'identite recouvre le QR quand celui-ci est au bord
    haut ») neutralise la branche qui retrecit l'entete a la moitie gauche de la bande et
    **survivait** a toute la suite -- parce qu'aucun gabarit livre ne met le QR au bord
    haut, donc la branche n'est jamais empruntee par le registre.

    Consequence reelle du mutant, si un gabarit y revenait: l'entete de deux lignes a
    14 pt s'imprimerait **par-dessus** le symbole, dont la zone de silence ISO doit rester
    blanche. Un QR recouvert de texte ne decode plus, et aucune etape n'echouerait.

    Le test exerce donc les deux branches sur un gabarit construit, et il verifie les deux
    sens: quand le QR prend le bord haut l'entete est **strictement a sa gauche**, et
    quand il est ailleurs l'entete prend la bande **entiere**.
    """
    spec_haut = _top_edge_spec()
    qr_rect = page_templates.qr_reserved_zone_mm(spec_haut)
    band = page_templates.header_band_mm(spec_haut)
    zones = pdf_composition._header_zones_mm(spec_haut, qr_rect)
    assert "header_identity" in zones, zones
    header = zones["header_identity"]
    # L'entete ne recouvre pas le QR, et pas d'un cheveu: le test mesure le
    # **chevauchement** des deux rectangles, pas seulement leurs abscisses de depart.
    assert not rects_overlap(header, qr_rect), (header, qr_rect)
    # Il est bien a **gauche** de l'emprise, avec l'ecart de texte, et non simplement
    # retreci d'un cote quelconque.
    assert header[0] == pytest.approx(band[0])
    assert header[0] + header[2] == pytest.approx(
        qr_rect[0] - pdf_composition._TEXT_GAP_MM)
    assert header[2] < band[2], (header, band)
    # Et la branche symetrique: le QR ailleurs, l'entete prend toute la bande haute. Sans
    # ce second volet, un mutant qui retrecirait l'entete **toujours** passerait.
    spec_bas = page_templates.template_for("portrait", 2, "0", "v2")
    assert spec_bas.qr_edge != page_templates.QR_EDGE_TOP
    zones_bas = pdf_composition._header_zones_mm(
        spec_bas, page_templates.qr_reserved_zone_mm(spec_bas))
    assert zones_bas["header_identity"][2] == pytest.approx(
        page_templates.header_band_mm(spec_bas)[2])
    assert zones_bas["header_identity"][2] > header[2]


@pytest.mark.parametrize("bloc", ["entete", "pied"])
def test_an_identity_line_that_does_not_fit_is_refused_never_truncated(bloc) -> None:
    """**`F09` et `G12`**: une ligne d'identite qui ne tient pas est **refusee**.

    Les deux mutants remplacent `_require_verbatim` par un `fit_text` -- la ligne est
    **tronquee** au lieu de faire echouer la composition -- et les deux **survivaient**.
    C'est le mode d'echec le plus grave de cette famille: l'egalite inter-canaux des
    identifiants canoniques (payload QR, noms de fichiers, texte imprime a l'octet pres)
    est un contrat de la story 4.2, et c'est le mecanisme de secours 4.6 qui en depend. Un
    identifiant tronque en silence casse le secours **sans** casser la planche, donc le
    defaut ne se voit qu'au moment ou l'on en a besoin.

    Les deux blocs sont eprouves separement parce que `_require_verbatim` a justement ete
    extraite en fonction pour eux deux (story 5.18): une regle appliquee a l'un des deux
    seulement laisserait passer une troncature la ou elle casse le contrat.

    **Le levier est le corps de police et non la longueur de l'identifiant, et c'est
    force**: un identifiant du manifest passe par `derive_short_id` des sa creation, donc
    il est **plafonne a 48 caracteres canoniques** -- 48 caracteres tiennent dans les deux
    zones, et un identifiant plus long est refuse bien avant la composition, par le
    manifest. La propriete testee (« refusee, jamais tronquee ») ne depend pas de la raison
    pour laquelle la ligne ne tient pas, et le corps de police est le seul levier qui rend
    la branche atteignable. C'est le meme geste que le gabarit construit a 60 pt qui prouve
    la comparaison des bords porteurs.
    """
    # Un `project_id` a la **longueur canonique maximale** (48 caracteres): c'est le pire
    # cas legal, et il tient encore au plancher de 8 pt dans les 112 mm du pied residuel.
    project_id = "p" + "z" * 46 + "9"
    assert len(project_id) == 48
    manifest = make_manifest(project_id=project_id)
    nominal = compose(manifest=manifest, geometry_version="v2")
    # Les deux lignes de l'entete et les deux du pied residuel, telles que la production
    # les compose au corps reel: c'est a elles que le refus doit se referer.
    page = images_pages(nominal)[0]
    lignes = {
        "entete": next(b.lines for b in page.text.blocks if b.name == "header_identity"),
        "pied": next(b.lines for b in page.text.blocks if b.name == "footer_block"),
    }[bloc]
    assert lignes
    monkey = pytest.MonkeyPatch()
    try:
        if bloc == "entete":
            # L'entete d'identite porte le lot et la pagination a
            # `HEADER_IDENTITY_FONT_PT`; a 60 pt ses lignes ne tiennent plus.
            monkey.setattr(page_templates, "HEADER_IDENTITY_FONT_PT", 60.0)
        else:
            # Le pied residuel porte les identifiants au **plancher** typographique. Le
            # plancher lui-meme est deplace a 12 pt, ce qui garde `_require_body_font`
            # satisfaite pour l'entete a 14 pt et fait deborder un identifiant de 48
            # caracteres des 112 mm du pied.
            monkey.setattr(pdf_composition, "BODY_FONT_MIN_PT", 12.0)
        with pytest.raises(pdf_composition.GeometryOverflowError) as excinfo:
            compose(manifest=manifest, geometry_version="v2")
    finally:
        monkey.undo()
    message = str(excinfo.value)
    # Le refus nomme la ligne, sa zone et sa contrainte, et il ne parle pas de
    # troncature: c'est ce qui distingue un refus d'un ajustement silencieux.
    assert "ne tient pas dans le bloc" in message, message
    assert pdf_composition.TRUNCATION_MARKER not in message, message
    # Et il nomme **quel** bloc: une regle appliquee au mauvais des deux blocs se verrait.
    attendu = "d'entete" if bloc == "entete" else "d'identite"
    assert attendu in message, (attendu, message)
    # La ligne qui deborde est citee **entiere**, et c'est l'une de celles que la
    # production compose dans ce bloc: un refus qui tronquerait jusque dans son propre
    # motif serait le meme defaut, deplace.
    citees = [ligne for ligne in lignes if f"'{ligne}'" in message]
    assert citees, (lignes, message)
    # Et au corps reel, la composition **reussit** avec le meme manifest: le refus vient
    # du levier et non d'un residu. Sans ce second volet, un mutant qui refuserait
    # toujours passerait -- et l'identifiant de 48 caracteres s'imprime bien verbatim.
    assert project_id in lignes or bloc == "entete"


def test_no_technical_line_can_fit_in_no_column_and_the_arithmetic_says_why() -> None:
    """**`G13`: equivalence demontree**, et la demonstration est ecrite.

    Le mutant neutralise la garde `if remaining:` -- les lignes qui ne tiennent dans
    aucune colonne sont silencieusement jetees -- et il **survit**. J'ai cherche a le tuer
    par un test avant de conclure, et la garde est **inatteignable par arithmetique**, pour
    toute valeur des parametres. Ce n'est donc pas un trou de test: c'est une equivalence,
    et elle se demontre plutot que se declarer.

    La demonstration, avec `L = len(packed)` lignes a placer et `n` colonnes:

        rows     = ceil((L + 1) / n)
        capacite = n * rows - 1        (la premiere colonne reserve la rangee de la date)
                 >= n * (L + 1) / n - 1
                 = L

    La capacite est donc **toujours** superieure ou egale au nombre de lignes, et
    `remaining` est vide quel que soit le packing. Le seul levier qui pourrait la rendre
    mordante serait de decorreler `rows` de `L` -- ce que le mutant `G15` fait deja, et
    `G15` **meurt**.

    Le test verrouille les deux bouts de la demonstration: l'inegalite sur tout un domaine
    de `(L, n)`, et l'egalite du packing reel a ce que la production distribue sur **chaque**
    gabarit. Si un changement futur decorrelait les deux, l'inegalite tomberait ici et la
    garde redeviendrait mordante -- ce qui est exactement le service qu'on attend d'elle.
    """
    # --- Bout 1: l'inegalite, sur un domaine large de (lignes, colonnes) -------------
    for colonnes in range(1, 6):
        for lignes in range(0, 40):
            rows = -(-(lignes + 1) // colonnes)
            capacite = colonnes * rows - 1
            assert capacite >= lignes, (colonnes, lignes, rows, capacite)
    # --- Bout 2: le packing reel, gabarit par gabarit, distribue tout ----------------
    #
    # Mesure sur la production et non sur un modele: c'est `_pack_lines` qui decide `L`,
    # et c'est la largeur de colonne du gabarit qui decide `_pack_lines`.
    colonnes_reelles = len(page_templates.FOOTER_TECHNICAL_ZONE_NAMES)
    assert colonnes_reelles >= 2
    for orientation, cardinal in _ALL_TEMPLATE_COUPLES:
        if page_templates.retired_cardinal_reason("v2", cardinal, orientation):
            continue
        plan = compose(orientation=orientation, frames_per_page=cardinal,
                       geometry_version="v2")
        page = images_pages(plan)[0]
        techniques = [b for b in page.text.blocks
                      if b.name in page_templates.FOOTER_TECHNICAL_ZONE_NAMES]
        assert len(techniques) == colonnes_reelles, (orientation, cardinal)
        posees = sum(len(b.lines) for b in techniques)
        # Toutes les lignes packees sont posees: aucune n'est perdue en route. Les
        # segments se relisent sur `technical_footer`, qui est leur jointure par
        # `_pack_lines.separator` -- la meme separation, pas une seconde convention.
        largeur = techniques[0].rect_mm[2]
        segments = page.text.technical_footer.split(" - ")
        packed = pdf_composition._pack_lines(
            segments, largeur, techniques[0].font_pt)
        assert posees == len(packed), (orientation, cardinal, posees, len(packed))
        # Et la capacite calculee couvre bien ce packing, avec la rangee de la date
        # reservee dans la premiere colonne.
        rows = -(-(len(packed) + 1) // colonnes_reelles)
        assert colonnes_reelles * rows - 1 >= len(packed), (orientation, cardinal)


def test_the_slot_label_is_set_back_from_its_zone_by_the_declared_offset() -> None:
    """**`Q06`**: le retrait de l'etiquette sous sa zone est **derive**, pas pose.

    La **valeur** du retrait etait tenue (`Q05`, offset 1 -> 2, meurt), mais son **emploi**
    ne l'etait pas: le mutant `Q06` retire `_SLOT_LABEL_OFFSET_MM` de l'expression de
    placement, l'etiquette devient **tangente** au bord bas de sa zone -- donc collee au
    contour trace sur cette frontiere -- et rien ne le voyait. La suite ne mesure que les
    chevauchements, et une tangence n'en est pas un.

    Le test porte sur le plan **compose**, pas sur une reconstruction: c'est le rectangle
    que le rendu emploie. Et il asserte la propriete (« strictement en retrait ») **et** sa
    valeur derivee, dans cet ordre -- la propriete est ce qui compte, la valeur est ce qui
    empeche un retrait symbolique de 1e-9.
    """
    for version in sorted(page_templates.GEOMETRY_VERSIONS):
        plan = compose(geometry_version=version)
        page = images_pages(plan)[0]
        assert page.text.slot_labels
        assert len(page.text.slot_labels) == len(page.frames)
        for slot, label in zip(page.frames, page.text.slot_labels):
            zone_bas = slot.zone_rect_mm[1] + slot.zone_rect_mm[3]
            # **Strictement** en retrait: l'etiquette ne touche pas la frontiere de la
            # zone, sur laquelle `pdf_render` trace le contour.
            assert label.rect_mm[1] > zone_bas, (version, slot.zone_name)
            # Et le retrait est exactement celui que la constante declare.
            assert label.rect_mm[1] - zone_bas == pytest.approx(
                pdf_composition._SLOT_LABEL_OFFSET_MM, abs=1e-9), (
                    version, slot.zone_name)
            assert pdf_composition._SLOT_LABEL_OFFSET_MM > 0.0
            # L'etiquette reste dans la bande d'abscisses de sa zone: un retrait pose sur
            # le mauvais axe passerait les deux assertions ci-dessus.
            assert label.rect_mm[0] == pytest.approx(slot.zone_rect_mm[0])
            assert label.rect_mm[2] == pytest.approx(slot.zone_rect_mm[2])
