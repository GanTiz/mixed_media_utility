"""Tests de la detection geometrique des pages scannees (story 5.2).

Documents de marqueurs **synthetiques** pour tous les cas geometriques: tester
une homographie ne demande aucune image, et fabriquer un scan realiste pour
chacun des 33 gabarits couterait cher sans rien prouver de plus.

La geometrie attendue est toujours derivee du **vrai** `page_templates`, jamais
d'un `SimpleNamespace` de fixture ni de valeurs recopiees a la main: c'est
l'action item 3 de la retro Epic 4, et c'est ce qui fait que ces tests
tomberaient si le registre changeait sous eux.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import layout, page_templates, scan_detection

MODULE_PATH = REPO_ROOT / "src" / "mixed_media_utility" / "scan_detection.py"

PORTRAIT_2F = page_templates.build_template_id("portrait", 2, "2")
PAYSAGE_4F = page_templates.build_template_id("paysage", 4, "2")
SCAN_DPI = 300


def markers_for(
    template_id: str,
    dpi: int,
    *,
    scale=(1.0, 1.0),
    extra=(),
    rotate_deg: float = 0.0,
) -> list[dict]:
    """Marqueurs de coin **exactement** aux positions nominales du template.

    `scale` deforme volontairement la page pour eprouver la mesure d'echelle:
    `(1.0, 1.0)` est une page parfaite, `(1.05, 1.05)` une mise a l'echelle
    homogene, `(1.0, 1.06)` un etirement sur un seul axe.

    `rotate_deg` incline la page autour de son centre, **sans la deformer**:
    c'est la feuille posee de travers sur la vitre. Une page inclinee n'est pas
    une page mise a l'echelle, et la premiere version de la mesure les
    confondait -- 0,73 degre suffisait a declencher l'alarme d'echelle.
    """
    spec = page_templates.get_template(template_id)
    centers = page_templates.corner_marker_centers_mm(spec)
    width_px, height_px = page_templates.page_size_px(spec, dpi)
    pivot = np.array([width_px / 2.0, height_px / 2.0])
    angle = np.deg2rad(rotate_deg)
    rotation = np.array(
        [[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]]
    )
    markers = []
    for marker_id in layout.CORNER_MARKER_IDS:
        x_px, y_px = page_templates.mm_to_px(*centers[marker_id], dpi)
        point = np.array([x_px * scale[0], y_px * scale[1]])
        point = rotation @ (point - pivot) + pivot
        markers.append({"id": marker_id, "center": [float(point[0]), float(point[1])]})
    markers.extend({"id": mid, "center": [10.0, 10.0]} for mid in extra)
    return markers


# --- AC 1 / AC 2: la geometrie vient du template, et le paysage est correct --


def test_page_geometry_comes_from_the_template_registry() -> None:
    geometry = scan_detection.resolve_page_geometry(PORTRAIT_2F, SCAN_DPI)
    spec = page_templates.get_template(PORTRAIT_2F)
    assert geometry["page_size_px"] == page_templates.mm_to_px(
        spec.page_width_mm, spec.page_height_mm, SCAN_DPI
    )
    assert len(geometry["frame_zones_px"]) == len(spec.frame_zones_mm)


def test_the_landscape_page_is_transposed_and_that_is_the_whole_point() -> None:
    """Le defaut central que cette story ferme.

    `layout.page_size_px` rend toujours 210x297, donc en paysage l'espace de
    destination de l'homographie etait transpose et la page redressee fausse --
    silencieusement, pour 30 gabarits sur 33.
    """
    portrait = scan_detection.resolve_page_geometry(PORTRAIT_2F, SCAN_DPI)
    paysage = scan_detection.resolve_page_geometry(PAYSAGE_4F, SCAN_DPI)

    assert portrait["page_size_px"] == tuple(reversed(paysage["page_size_px"]))
    assert paysage["page_size_px"][0] > paysage["page_size_px"][1]
    # L'ancien chemin aurait rendu la taille portrait pour les deux.
    assert paysage["page_size_px"] != layout.page_size_px(SCAN_DPI)


def test_every_registered_template_resolves_without_falling_back() -> None:
    # Les 33, pas seulement les trois ou l'ancien et le nouveau chemin
    # coincident par construction.
    for template_id in page_templates.known_template_ids():
        geometry = scan_detection.resolve_page_geometry(template_id, SCAN_DPI)
        spec = page_templates.get_template(template_id)
        assert len(geometry["frame_zones_px"]) == spec.frames_per_page
        for zone in geometry["frame_zones_px"]:
            assert zone["width"] > 0 and zone["height"] > 0


def test_an_unknown_template_is_an_explicit_failure() -> None:
    # Jamais de geometrie devinee: un repli sur `layout.FRAME_ZONES_MM` poserait
    # deux zones portrait sur une page paysage a huit zones, et le resultat
    # aurait l'air d'un succes.
    with pytest.raises(page_templates.UnknownTemplateError):
        scan_detection.resolve_page_geometry("tpl-inexistant-v9", SCAN_DPI)


def test_the_detection_module_never_reads_page_geometry_from_layout() -> None:
    """Le grep porte sur le **code executable**, pas sur la prose.

    Le module explique en toutes lettres pourquoi il ne se replie pas sur
    `layout.FRAME_ZONES_MM`; interdire la chaine partout obligerait a effacer
    l'explication pour satisfaire le test, ce qui appauvrirait le module sans
    rien proteger. L'AST ne voit que les attributs reellement lus.
    """
    import ast

    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"), filename=str(MODULE_PATH))
    accessed = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "layout"
    }
    # Ce qui depend de la page vient du TemplateSpec, jamais de `layout`.
    forbidden = {"FRAME_ZONES_MM", "page_size_px", "corner_marker_centers_mm",
                 "PAGE_WIDTH_MM", "PAGE_HEIGHT_MM"}
    assert not (accessed & forbidden), sorted(accessed & forbidden)
    # Les invariants, eux, restent bien chez `layout`.
    assert {"CORNER_MARKER_IDS", "marker_role", "MIN_CORNER_QUAD_SIN"} <= accessed


# --- AC 3: une seule recette de conversion mm -> px -------------------------


def test_there_is_exactly_one_mm_to_px_recipe(monkeypatch) -> None:
    """La **delegation**, pas l'egalite des valeurs.

    Une egalite de valeurs est satisfaite par n'importe quelle copie conforme:
    le mutant « seconde implementation identique dans `layout` » survivait a la
    suite entiere, alors que c'est litteralement la seconde copie que l'AC
    interdit. On remplace la recette du registre et on verifie que `layout`
    suit: seule une delegation reelle peut le faire.
    """
    monkeypatch.setattr(page_templates, "mm_to_px", lambda x, y, dpi: (-1, -1))
    assert layout.mm_to_px(35.0, 60.0, 600) == (-1, -1), (
        "layout.mm_to_px ne delegue pas: une seconde recette existe"
    )


def test_the_conversion_appears_only_once_in_the_source() -> None:
    # Deuxieme verrou, complementaire du precedent: la delegation pourrait etre
    # retablie tout en laissant une copie morte ailleurs dans `layout`.
    layout_source = (
        REPO_ROOT / "src" / "mixed_media_utility" / "layout.py"
    ).read_text(encoding="utf-8")
    assert "25.4" not in layout_source, (
        "la constante de conversion pouce/mm n'a plus rien a faire dans `layout`: "
        "la recette vit dans `page_templates`"
    )


def test_the_rounding_policy_is_pinned_by_values() -> None:
    """L'impression et le scan consomment la meme fonction.

    Un arrondi qui divergerait entre les deux decalerait chaque crop d'un pixel
    a chaque bord, sans jamais lever d'erreur. Les valeurs sont donc figees, et
    `78.75` est la hauteur reelle d'une zone de frame.
    """
    assert page_templates.mm_to_px(0.0, 0.0, 600) == (0, 0)
    assert page_templates.mm_to_px(25.4, 25.4, 600) == (600, 600)
    assert page_templates.mm_to_px(35.0, 60.0, 600) == (827, 1417)
    assert page_templates.mm_to_px(78.75, 78.75, 300) == (930, 930)
    assert page_templates.mm_to_px(210.0, 297.0, 600) == (4961, 7016)


# --- AC 6: le producteur d'avertissement « marqueur etranger » ---------------


@pytest.mark.parametrize(
    ("marker_id", "expected_role"),
    [(12, layout.TEMPLATE_VARIANT_ROLE), (25, layout.SLOT_ROLE), (200, layout.UNASSIGNED_ROLE)],
)
def test_a_foreign_marker_is_ignored_for_geometry_and_named(
    marker_id: int, expected_role: str
) -> None:
    """`marker_role` n'avait aucun appelant en production; c'est le premier.

    La politique est deja statuee normativement dans le bloc de contrat de
    `layout`: cette story l'applique, elle ne la re-arbitre pas.
    """
    markers = markers_for(PORTRAIT_2F, SCAN_DPI, extra=[marker_id])
    corners, foreign = scan_detection._partition_markers(markers)

    assert set(corners) == set(layout.CORNER_MARKER_IDS)
    assert [m.marker_id for m in foreign] == [marker_id]
    assert foreign[0].role == expected_role


def test_a_duplicated_reserved_id_is_also_reported() -> None:
    # La garde de doublon du chemin POC ne regarde que les IDs de coin: un
    # doublon de plage reservee y passait sans un mot.
    markers = markers_for(PORTRAIT_2F, SCAN_DPI, extra=[25, 25])
    _corners, foreign = scan_detection._partition_markers(markers)
    assert [m.marker_id for m in foreign] == [25], "signale une fois, pas deux"


def test_foreign_markers_are_reported_in_a_deterministic_order() -> None:
    """L'ordre de detection d'ArUco n'est pas l'ordre du document.

    Sans tri, deux detections de la meme page pourraient publier les memes
    marqueurs dans deux ordres, donc deux empreintes -- ce qui ruinerait la
    reproductibilite que l'AC 10 exige. Le mutant « tri retire » survivait: les
    tests existants n'avaient qu'un seul marqueur etranger.
    """
    markers = markers_for(PORTRAIT_2F, SCAN_DPI, extra=[200, 12, 25])
    _corners, foreign = scan_detection._partition_markers(markers)
    assert [m.marker_id for m in foreign] == [12, 25, 200]


def test_a_duplicated_corner_id_is_still_refused() -> None:
    markers = markers_for(PORTRAIT_2F, SCAN_DPI)
    markers.append(dict(markers[0]))
    geometry = scan_detection.resolve_page_geometry(PORTRAIT_2F, SCAN_DPI)
    with pytest.raises(scan_detection.PageDetectionRefused) as excinfo:
        scan_detection.compute_template_homography(markers, geometry, SCAN_DPI)
    assert "double" in str(excinfo.value)


@pytest.mark.parametrize("absent", [0, 1, 2, 3])
def test_missing_corners_are_refused_and_named(absent: int) -> None:
    """« Nomme » veut dire nomme.

    La premiere version aserait `"2" in str(erreur)`, ce que le message
    satisfait toujours: il se termine par `IDs attendus: [0, 1, 2, 3].`. Le test
    passait quel que soit le coin manquant -- meme famille que le test
    tautologique trouve sur 5.9.
    """
    markers = [m for m in markers_for(PORTRAIT_2F, SCAN_DPI) if m["id"] != absent]
    geometry = scan_detection.resolve_page_geometry(PORTRAIT_2F, SCAN_DPI)
    with pytest.raises(scan_detection.PageDetectionRefused) as excinfo:
        scan_detection.compute_template_homography(markers, geometry, SCAN_DPI)
    assert f"manquants: [{absent}]" in str(excinfo.value)


def test_a_geometric_refusal_is_catchable_as_a_page_geometry_error() -> None:
    """Les Dev Notes posent « erreurs existantes a reutiliser, jamais a redefinir ».

    `PageGeometryError` derive de `ValueError`, `ScanDetectionError` de
    `RuntimeError`: sans rattachement, un appelant qui attrape la base
    geometrique documentee ne rattraperait rien du nouveau chemin.
    """
    from mixed_media_utility.detection import aruco as aruco_detection

    markers = [m for m in markers_for(PORTRAIT_2F, SCAN_DPI) if m["id"] != 3]
    geometry = scan_detection.resolve_page_geometry(PORTRAIT_2F, SCAN_DPI)
    with pytest.raises(aruco_detection.PageGeometryError):
        scan_detection.compute_template_homography(markers, geometry, SCAN_DPI)
    with pytest.raises(scan_detection.ScanDetectionError):
        scan_detection.compute_template_homography(markers, geometry, SCAN_DPI)


def test_a_degenerate_corner_quad_is_refused() -> None:
    # Trois points quasi colineaires: `findHomography` rend une matrice de rang
    # deficient sans jamais rendre `None`.
    markers = [
        {"id": 0, "center": [100.0, 100.0]},
        {"id": 1, "center": [200.0, 100.0]},
        {"id": 2, "center": [300.0, 100.5]},
        {"id": 3, "center": [400.0, 101.0]},
    ]
    geometry = scan_detection.resolve_page_geometry(PORTRAIT_2F, SCAN_DPI)
    with pytest.raises(scan_detection.PageDetectionRefused):
        scan_detection.compute_template_homography(markers, geometry, SCAN_DPI)


# --- AC 9: la mise a l'echelle est mesuree, pas subie ------------------------


def test_the_scale_tolerance_is_pinned_so_a_recalibration_is_visible() -> None:
    # EPIC5-ARB-10. Une recalibration future doit etre un changement visible,
    # pas un glissement.
    assert scan_detection.SCALE_WARNING_TOLERANCE == 0.02
    doc = MODULE_PATH.read_text(encoding="utf-8")
    assert "provisoire" in doc and "pilote papier" in doc


@pytest.mark.parametrize("template_id", [PORTRAIT_2F, PAYSAGE_4F])
def test_a_nominal_page_emits_no_scale_warning(template_id: str) -> None:
    geometry = scan_detection.resolve_page_geometry(template_id, SCAN_DPI)
    _homography, scale = scan_detection.compute_template_homography(
        markers_for(template_id, SCAN_DPI), geometry, SCAN_DPI
    )
    assert scale.scale_error < scan_detection.SCALE_WARNING_TOLERANCE
    assert scale.aspect_error < scan_detection.SCALE_WARNING_TOLERANCE
    assert scan_detection._scale_warnings(scale) == []
    # Une page nominale se reprojette sur elle-meme, au bruit numerique pres.
    assert scale.residual_px < 1.0


def test_a_uniformly_rescaled_page_is_reported() -> None:
    """Le cas « ajuster a la page » d'une imprimante.

    Risque R8: la geometrie est fausse et rien ne leve -- les frames sortent,
    decalees, et personne ne le sait avant de regarder le resultat.
    """
    geometry = scan_detection.resolve_page_geometry(PORTRAIT_2F, SCAN_DPI)
    _homography, scale = scan_detection.compute_template_homography(
        markers_for(PORTRAIT_2F, SCAN_DPI, scale=(1.05, 1.05)), geometry, SCAN_DPI
    )
    warnings = scan_detection._scale_warnings(scale)
    assert "PAGE_SCALE_OUT_OF_TOLERANCE" in warnings
    # Homogene: les deux axes bougent ensemble, donc pas d'ecart d'aspect.
    assert "PAGE_ASPECT_OUT_OF_TOLERANCE" not in warnings
    assert scale.scale_error == pytest.approx(0.05, abs=0.01)


def test_a_page_stretched_on_one_axis_is_reported_as_an_aspect_error() -> None:
    # Le cas auto-fit de scanner, ou page non plane: les deux causes terrain
    # sont distinctes, d'ou deux codes.
    geometry = scan_detection.resolve_page_geometry(PORTRAIT_2F, SCAN_DPI)
    _homography, scale = scan_detection.compute_template_homography(
        markers_for(PORTRAIT_2F, SCAN_DPI, scale=(1.0, 1.06)), geometry, SCAN_DPI
    )
    warnings = scan_detection._scale_warnings(scale)
    # La liste **complete**: avec `min` au lieu de `max` dans `scale_error`, un
    # etirement mono-axe cesserait d'emettre le code d'echelle, et un test qui
    # n'assere que la presence du code d'aspect ne le verrait pas.
    assert warnings == ["PAGE_SCALE_OUT_OF_TOLERANCE", "PAGE_ASPECT_OUT_OF_TOLERANCE"]
    assert scale.aspect_error == pytest.approx(0.0566, abs=0.002)


def test_scale_error_reports_the_worst_axis_not_the_best() -> None:
    # `min` au lieu de `max` passait: le test d'echelle homogene bouge les deux
    # axes ensemble, donc max == min, et le test mono-axe ne regardait pas
    # l'ecart d'echelle.
    measurement = scan_detection.PageScaleMeasurement(1.0, 1.10, 0.0)
    assert measurement.scale_error == pytest.approx(0.10)


def test_the_reprojection_residual_is_published_without_a_threshold() -> None:
    # EPIC5-ARB-10 ne tranche que l'echelle et l'aspect: lui inventer un seuil
    # ici serait poser un chiffre que personne n'a mesure.
    geometry = scan_detection.resolve_page_geometry(PORTRAIT_2F, SCAN_DPI)
    _homography, scale = scan_detection.compute_template_homography(
        markers_for(PORTRAIT_2F, SCAN_DPI), geometry, SCAN_DPI
    )
    assert "residual_px" in scale.as_document()
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "RESIDUAL" not in source, "aucun code d'avertissement de residu"


# --- AC 9: la mesure ne doit pas confondre inclinaison et mise a l'echelle ---


@pytest.mark.parametrize("angle", [0.75, 2.0, 5.0, 45.0, -3.0])
@pytest.mark.parametrize("template_id", [PORTRAIT_2F, PAYSAGE_4F])
def test_a_page_laid_askew_is_not_read_as_a_rescaled_page(
    template_id: str, angle: float
) -> None:
    """Le defaut que les trois couches de revue ont trouve independamment.

    Mesurer l'etendue `max - min` par axe n'est pas invariant par rotation: une
    page geometriquement parfaite, simplement posee de travers de 0,73 degre,
    franchissait le seuil de 2 %. Le seul instrument du risque R8 criait au loup
    sur presque chaque scan reel -- la facon la plus sure de le faire ignorer.
    Une distance entre centres de coin, elle, ne bouge pas quand la page pivote.
    """
    geometry = scan_detection.resolve_page_geometry(template_id, SCAN_DPI)
    _homography, scale = scan_detection.compute_template_homography(
        markers_for(template_id, SCAN_DPI, rotate_deg=angle), geometry, SCAN_DPI
    )
    assert scale.scale_x == pytest.approx(1.0, abs=1e-4)
    assert scale.scale_y == pytest.approx(1.0, abs=1e-4)
    assert scan_detection._scale_warnings(scale) == []


def test_a_real_rescale_is_not_masked_by_a_skew() -> None:
    """L'autre sens de l'erreur, mesure par la revue: un retrait reel de 3,2 %
    -- au coeur de la bande 3-6 % que le seuil vise -- etait **entierement
    masque** par 1,22 degre de travers dans le bon sens."""
    geometry = scan_detection.resolve_page_geometry(PORTRAIT_2F, SCAN_DPI)
    _homography, scale = scan_detection.compute_template_homography(
        markers_for(PORTRAIT_2F, SCAN_DPI, scale=(0.968, 0.968), rotate_deg=-1.22),
        geometry,
        SCAN_DPI,
    )
    assert scale.scale_error == pytest.approx(0.032, abs=0.002)
    assert "PAGE_SCALE_OUT_OF_TOLERANCE" in scan_detection._scale_warnings(scale)


def test_the_residual_is_not_zero_by_construction() -> None:
    """Avec quatre correspondances, `findHomography` resout exactement.

    Le residu de reprojection valait donc zero sur 300 quadrilateres fortement
    deformes, et le mutant « `residual = 0.0` en dur » survivait. Le residu
    publie est celui de la meilleure **similitude**: nul pour une page saine a
    n'importe quelle rotation ou echelle, non nul des que la page se deforme.
    """
    geometry = scan_detection.resolve_page_geometry(PORTRAIT_2F, SCAN_DPI)

    _h, nominal = scan_detection.compute_template_homography(
        markers_for(PORTRAIT_2F, SCAN_DPI, rotate_deg=7.0, scale=(1.03, 1.03)),
        geometry,
        SCAN_DPI,
    )
    assert nominal.residual_px < 1.0, "une similitude reste une similitude"

    deformed = markers_for(PORTRAIT_2F, SCAN_DPI)
    deformed[1]["center"][0] += 40.0  # un seul coin deplace: perspective
    _h, measured = scan_detection.compute_template_homography(
        deformed, geometry, SCAN_DPI
    )
    assert measured.residual_px > 5.0, (
        "un coin deplace de 40 px doit se voir; un residu de reprojection, lui, "
        "resterait a zero"
    )


def test_a_mirrored_page_is_refused() -> None:
    # Determinant negatif, residu nul, echelle 1,0: rien ne la distingue d'une
    # page saine, et 5.3 la decouperait retournee.
    markers = markers_for(PORTRAIT_2F, SCAN_DPI)
    by_id = {m["id"]: m for m in markers}
    by_id[0]["center"], by_id[1]["center"] = by_id[1]["center"], by_id[0]["center"]
    by_id[3]["center"], by_id[2]["center"] = by_id[2]["center"], by_id[3]["center"]
    geometry = scan_detection.resolve_page_geometry(PORTRAIT_2F, SCAN_DPI)
    with pytest.raises(scan_detection.PageGeometryRefused) as excinfo:
        scan_detection.compute_template_homography(markers, geometry, SCAN_DPI)
    assert "miroir" in str(excinfo.value)


@pytest.mark.parametrize(
    "marker",
    [
        {"center": [1.0, 2.0]},
        {"id": 0},
        {"id": 0, "center": [1.0]},
        {"id": 0, "center": [1.0, 2.0, 3.0]},
        {"id": 0, "center": [float("nan"), 2.0]},
        {"id": True, "center": [1.0, 2.0]},
        "pas un marqueur",
    ],
)
def test_a_malformed_marker_is_refused_with_the_named_error(marker) -> None:
    # Sans garde, ces formes levent un `KeyError` ou un `ValueError` numpy, hors
    # du tuple de rattrapage par page: tout le lot est perdu pour une page.
    with pytest.raises(scan_detection.PageGeometryRefused):
        scan_detection._partition_markers([marker])


@pytest.mark.parametrize("bad", [0, -1, True, 3.0, "600", 10**400, 20001])
def test_an_absurd_dpi_is_refused_rather_than_overflowed(bad) -> None:
    """Un entier Python arbitrairement grand franchissait la garde de positivite
    puis levait un `OverflowError` nu dans la conversion en flottant -- pour une
    entree que la garde pretendait justement valider."""
    with pytest.raises(scan_detection.ScanDetectionError):
        scan_detection.resolve_page_geometry(PORTRAIT_2F, bad)


def test_the_dpi_ceiling_is_shared_with_the_ingestion() -> None:
    from mixed_media_utility import scan_ingest

    # Un seul plafond pour les deux etages: deux constantes egales aujourd'hui
    # divergent demain. La detection lit celle de l'ingestion, elle n'en a pas
    # une a elle -- ce qu'un mutant sur `MAX_SCAN_DPI` doit rendre visible ici.
    assert scan_ingest.MAX_SCAN_DPI == 20000
    with pytest.raises(scan_ingest.InvalidScanDpiError):
        scan_ingest.validate_scan_dpi(scan_ingest.MAX_SCAN_DPI + 1)
    assert scan_ingest.validate_scan_dpi(scan_ingest.MAX_SCAN_DPI) == 20000
    with pytest.raises(scan_detection.ScanDetectionError) as excinfo:
        scan_detection.resolve_page_geometry(PORTRAIT_2F, scan_ingest.MAX_SCAN_DPI + 1)
    assert str(scan_ingest.MAX_SCAN_DPI) in str(excinfo.value)


@pytest.mark.parametrize(
    "measurement",
    [(float("inf"), 1.0, 0.0), (1.0, float("nan"), 0.0), (1.0, 1.0, float("inf")),
     (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
)
def test_a_measurement_that_cannot_be_serialised_is_refused_where_it_is_born(
    measurement,
) -> None:
    """`nan > seuil` est **faux**: un NaN ne levait aucun avertissement, la page
    sortait `status=ok` avec une echelle indeterminee, et la serialisation
    cassait sur un `ValueError` nu -- hors hierarchie, apres que tout le lot a
    ete detecte. Meme recette que `io/payload` pour `fps_target` (revue 4.5)."""
    with pytest.raises(scan_detection.ScanDetectionError):
        scan_detection.PageScaleMeasurement(*measurement)


# --- AC 8: reconciliation ingestion / QR -------------------------------------


def _page(
    rank: int, *, lot_id="lot-0007", page_index=0, page_count=2, project_id="demo-project-01"
) -> scan_detection.DetectedPage:
    return scan_detection.DetectedPage(
        read_rank=rank,
        status=scan_detection.PAGE_OK,
        locator_source=f"scans/lot/p{rank}.tif",
        locator_page_index=None,
        qr_status="ok",
        template_id=PORTRAIT_2F,
        template_source="qr",
        project_id=project_id,
        rush_id="rush-a1",
        lot_id=lot_id,
        page_index=page_index,
        page_count=page_count,
    )


def test_a_slug_differing_from_the_lot_id_is_only_a_warning() -> None:
    # Un dossier mal nomme est un cas terrain banal, pas une raison de refuser.
    warnings = scan_detection._reconcile_lot(
        [_page(0, page_index=0), _page(1, page_index=1)],
        ingest_slug="scans-du-mardi",
        ingested_count=2,
    )
    assert "INGEST_SLUG_DIFFERS_FROM_LOT_ID" in warnings


def test_a_missing_page_index_is_named() -> None:
    # La seule detection de lot incomplet de toute la chaine scan (R12).
    warnings = scan_detection._reconcile_lot(
        [_page(0, page_index=0)], ingest_slug="lot-0007", ingested_count=1
    )
    assert "PAGE_INDEX_MISSING" in warnings
    assert "PAGE_COUNT_DIFFERS_FROM_INGESTED" in warnings


def test_a_duplicated_page_index_is_named() -> None:
    warnings = scan_detection._reconcile_lot(
        [_page(0, page_index=0), _page(1, page_index=0)],
        ingest_slug="lot-0007",
        ingested_count=2,
    )
    assert "PAGE_INDEX_DUPLICATED" in warnings


def test_a_page_index_out_of_range_is_named() -> None:
    warnings = scan_detection._reconcile_lot(
        [_page(0, page_index=0), _page(1, page_index=7)],
        ingest_slug="lot-0007",
        ingested_count=2,
    )
    assert "PAGE_INDEX_OUT_OF_RANGE" in warnings


def test_two_lots_on_the_same_glass_are_refused_not_arbitrated() -> None:
    """Choisir l'une des deux identites fabriquerait un lot qui n'a jamais existe."""
    with pytest.raises(scan_detection.LotIdentityError):
        scan_detection._reconcile_lot(
            [_page(0, lot_id="lot-0007"), _page(1, lot_id="lot-0008", page_index=1)],
            ingest_slug="lot-0007",
            ingested_count=2,
        )


def test_a_complete_lot_emits_no_reconciliation_warning() -> None:
    warnings = scan_detection._reconcile_lot(
        [_page(0, page_index=0), _page(1, page_index=1)],
        ingest_slug="lot-0007",
        ingested_count=2,
    )
    assert warnings == []


def test_inconsistent_page_counts_do_not_silence_the_index_checks() -> None:
    """Le cas que R12 vise, et sur lequel la premiere version etait muette.

    Une reference deduite par `pop() if len(counts) == 1 else None` retombait a
    `None` des que deux pages se contredisaient, ce qui **sautait les trois
    controles d'un coup**: un lot annoncant 2 et 7 pages, avec un index a 5,
    sortait avec `warnings: []`.
    """
    warnings = scan_detection._reconcile_lot(
        [
            _page(0, page_index=0, page_count=2),
            _page(1, page_index=5, page_count=7),
        ],
        ingest_slug="lot-0007",
        ingested_count=2,
    )
    assert "PAGE_COUNT_INCONSISTENT_ACROSS_PAGES" in warnings
    assert "PAGE_COUNT_DIFFERS_FROM_INGESTED" in warnings
    assert "PAGE_INDEX_MISSING" in warnings


def test_a_unanimous_page_count_is_not_reported_as_inconsistent() -> None:
    # Le pendant du precedent: le code ne doit pas s'allumer sur un lot sain,
    # sinon il devient du bruit et personne ne le lit.
    warnings = scan_detection._reconcile_lot(
        [_page(0, page_index=0), _page(1, page_index=1)],
        ingest_slug="lot-0007",
        ingested_count=2,
    )
    assert "PAGE_COUNT_INCONSISTENT_ACROSS_PAGES" not in warnings


def test_the_page_index_range_is_closed_on_its_upper_bound() -> None:
    # `index >= declared` et non `index > declared`: sur un lot de 2 pages, les
    # index legitimes sont 0 et 1. L'index 2 est hors plage, et un `>` le
    # laisserait passer.
    warnings = scan_detection._reconcile_lot(
        [_page(0, page_index=0), _page(1, page_index=2)],
        ingest_slug="lot-0007",
        ingested_count=2,
    )
    assert "PAGE_INDEX_OUT_OF_RANGE" in warnings


def test_a_refused_but_identified_page_still_counts_as_present() -> None:
    """Une page refusee pour raison **geometrique** est physiquement la.

    L'exclure de la reconciliation faisait signaler `PAGE_INDEX_MISSING` -- « il
    manque une page » -- pour une feuille presente, identifiee, et seulement
    inexploitable.
    """
    refused = scan_detection.DetectedPage(
        read_rank=1,
        status=scan_detection.PAGE_REFUSED,
        locator_source="scans/lot/p1.tif",
        locator_page_index=None,
        qr_status="decoded",
        project_id="demo-project-01",
        rush_id="rush-a1",
        lot_id="lot-0007",
        page_index=1,
        page_count=2,
        refusal_reason="Marqueurs ArUco de coin manquants: [3].",
    )
    warnings = scan_detection._reconcile_lot(
        [_page(0, page_index=0), refused], ingest_slug="lot-0007", ingested_count=2
    )
    assert warnings == []


def test_detected_pages_counts_only_the_exploitable_ones() -> None:
    refused = scan_detection.DetectedPage(
        read_rank=1,
        status=scan_detection.PAGE_REFUSED,
        locator_source="scans/lot/p1.tif",
        locator_page_index=None,
        qr_status=scan_detection.QR_NOT_ATTEMPTED,
    )
    report = scan_detection.LotDetectionReport(
        ingest_slug="lot-0007", scan_dpi=SCAN_DPI, pages=(_page(0), refused)
    )
    assert len(report.detected_pages) == 1
    assert report.as_document()["page_count"] == 2
    assert report.as_document()["detected_page_count"] == 1


# --- AC 10: document canonique ----------------------------------------------


def test_the_report_document_shape_is_pinned() -> None:
    # Ce document est ce que consomment 5.3, 5.6, 5.7 et 5.8: un champ renomme
    # en silence les casserait toutes les quatre, mais seulement a l'execution.
    report = scan_detection.LotDetectionReport(
        ingest_slug="lot-0007", scan_dpi=SCAN_DPI, pages=(_page(0),)
    )
    document = scan_detection.report_document(report)
    assert set(document) == {
        "ingest_slug", "scan_dpi", "ingest_declared_dpi", "page_count",
        "detected_page_count", "warnings", "pages", "fingerprint",
    }
    assert set(document["pages"][0]) == {
        "read_rank", "status", "locator", "qr_status", "template_id",
        "template_source", "project_id", "rush_id", "lot_id", "page_index",
        "page_count", "gamut_map_id", "corner_centers", "foreign_markers",
        "homography", "page_size_px", "scale", "frame_zones_mm",
        "frame_zones_px", "warnings", "refusal_reason",
        # Champ additif de la story 5.27: le code enumere **a cote** de la
        # phrase, jamais a sa place -- les deux sont publies.
        "refusal_code",
    }
    assert document["fingerprint"].startswith(scan_detection.FINGERPRINT_PREFIX)


def test_two_serialisations_of_the_same_report_are_byte_identical() -> None:
    report = scan_detection.LotDetectionReport(
        ingest_slug="lot-0007", scan_dpi=SCAN_DPI, pages=(_page(0), _page(1, page_index=1))
    )
    assert scan_detection.report_json(report) == scan_detection.report_json(report)
    assert json.loads(scan_detection.report_json(report))["page_count"] == 2


def test_the_report_carries_no_pixel() -> None:
    geometry = scan_detection.resolve_page_geometry(PAYSAGE_4F, SCAN_DPI)
    homography, scale = scan_detection.compute_template_homography(
        markers_for(PAYSAGE_4F, SCAN_DPI), geometry, SCAN_DPI
    )
    page = scan_detection.DetectedPage(
        read_rank=0, status=scan_detection.PAGE_OK,
        locator_source="scans/lot/p0.tif", locator_page_index=None, qr_status="ok",
        template_id=PAYSAGE_4F, template_source="qr",
        homography=tuple(float(v) for v in np.asarray(homography).ravel()),
        page_size_px=geometry["page_size_px"], scale=scale,
        frame_zones_mm=geometry["frame_zones_mm"], frame_zones_px=geometry["frame_zones_px"],
    )
    text = scan_detection.report_json(
        scan_detection.LotDetectionReport("lot", SCAN_DPI, (page,))
    )
    assert "base64" not in text
    assert len(text) < 20000, "un document de detection ne transporte pas d'image"


# --- AC 9 / AC 10: les zones resolues sont celles du vrai registre -----------


def test_the_resolved_zones_match_the_real_registry_not_a_fixture() -> None:
    """Integration contre le vrai producteur (action item 3 de la retro Epic 4)."""
    for template_id in (PORTRAIT_2F, PAYSAGE_4F):
        spec = page_templates.get_template(template_id)
        geometry = scan_detection.resolve_page_geometry(template_id, SCAN_DPI)
        for zone_mm, zone_px in zip(spec.frame_zones_mm, geometry["frame_zones_px"]):
            expected_x, expected_y = page_templates.mm_to_px(
                zone_mm["x"], zone_mm["y"], SCAN_DPI
            )
            expected_w, _ = page_templates.mm_to_px(zone_mm["width"], 0, SCAN_DPI)
            _, expected_h = page_templates.mm_to_px(0, zone_mm["height"], SCAN_DPI)
            assert (zone_px["x"], zone_px["y"]) == (expected_x, expected_y)
            # La largeur et la hauteur aussi: c'est **exactement** ce que 5.3 va
            # decouper, et le mutant qui les divise par deux passait.
            assert (zone_px["width"], zone_px["height"]) == (expected_w, expected_h)
            assert zone_px["name"] == zone_mm["name"]


def test_zones_of_the_same_size_get_the_same_pixel_size() -> None:
    """Propriete dont l'encodage video (Epic 6) a besoin.

    L'origine et la taille sont quantifiees separement, precisement pour que
    deux zones de meme dimension rendent des frames de meme taille. Arrondir les
    deux bords independamment donnait quatre tailles differentes sur une page a
    huit zones a 600 ppp.
    """
    for template_id in page_templates.known_template_ids():
        geometry = scan_detection.resolve_page_geometry(template_id, 600)
        sizes = {(zone["width"], zone["height"]) for zone in geometry["frame_zones_px"]}
        assert len(sizes) == 1, f"{template_id}: {sorted(sizes)}"


def test_the_homography_puts_the_zone_corners_where_the_template_says() -> None:
    """L'aller-retour que l'AC 2 exige, sur le gabarit qu'elle nomme.

    Comparer des tailles de page ne prouve pas ou une zone atterrit. Ici, une
    perspective « scanner » arbitraire est posee sur les quatre centres, le
    module retrouve l'homographie, et chaque coin de zone transite
    page -> scan -> page.
    """
    template_id = "tpl-a4-paysage-4f-v1"
    geometry = scan_detection.resolve_page_geometry(template_id, SCAN_DPI)
    spec = page_templates.get_template(template_id)
    centers = page_templates.corner_marker_centers_mm(spec)

    expected = np.array(
        [page_templates.mm_to_px(*centers[mid], SCAN_DPI) for mid in layout.CORNER_MARKER_IDS],
        dtype=np.float32,
    )
    # Perspective arbitraire mais deterministe: la page vue de biais.
    scanned = expected + np.array(
        [[13.0, -7.0], [-21.0, 4.0], [9.0, 17.0], [-5.0, -11.0]], dtype=np.float32
    )
    markers = [
        {"id": mid, "center": [float(x), float(y)]}
        for mid, (x, y) in zip(layout.CORNER_MARKER_IDS, scanned)
    ]
    homography, _scale = scan_detection.compute_template_homography(
        markers, geometry, SCAN_DPI
    )

    import cv2

    inverse = np.linalg.inv(homography)
    for zone in geometry["frame_zones_px"]:
        rectangle = np.array(
            [
                [[zone["x"], zone["y"]]],
                [[zone["x"] + zone["width"], zone["y"]]],
                [[zone["x"] + zone["width"], zone["y"] + zone["height"]]],
                [[zone["x"], zone["y"] + zone["height"]]],
            ],
            dtype=np.float32,
        )
        in_scan = cv2.perspectiveTransform(rectangle, inverse)
        back = cv2.perspectiveTransform(in_scan, homography).reshape(-1, 2)
        assert np.abs(back - rectangle.reshape(-1, 2)).max() < 0.01, zone["name"]


def test_the_fingerprint_ignores_the_homography_coefficients() -> None:
    """Question ouverte 3 de la story, tranchee ici.

    Les coefficients d'homographie sont les seuls flottants du document dont la
    valeur depend de l'implementation de `cv2.findHomography`, donc de la
    version d'OpenCV installee. Les signer rendrait l'empreinte
    non-reproductible d'une machine a l'autre, ce qui lui oterait sa fonction.
    Ils restent publies.
    """
    page = _page(0)
    with_h = scan_detection.report_document(
        scan_detection.LotDetectionReport("lot-0007", SCAN_DPI, (page,))
    )
    other = scan_detection.LotDetectionReport(
        "lot-0007",
        SCAN_DPI,
        (scan_detection.DetectedPage(**{**page.__dict__, "homography": (1.0, 0.0, 0.0)}),),
    )
    assert scan_detection.report_document(other)["fingerprint"] == with_h["fingerprint"]
    assert scan_detection.report_document(other)["pages"][0]["homography"] == [1.0, 0.0, 0.0]

    # ... mais tout autre champ change bien l'empreinte.
    moved = scan_detection.LotDetectionReport(
        "lot-0007",
        SCAN_DPI,
        (scan_detection.DetectedPage(**{**page.__dict__, "page_index": 9}),),
    )
    assert scan_detection.report_document(moved)["fingerprint"] != with_h["fingerprint"]


def test_the_document_float_precision_is_declared_not_literal() -> None:
    # Un consommateur qui compare deux documents doit pouvoir citer la precision
    # a laquelle ils sont comparables.
    assert scan_detection.DOCUMENT_FLOAT_PRECISION == 9


# --- AC 11: le chemin POC reste intact ---------------------------------------


def test_the_poc_signatures_are_untouched() -> None:
    import inspect

    from mixed_media_utility.detection import aruco as aruco_detection

    assert list(
        inspect.signature(aruco_detection.compute_page_homography).parameters
    ) == ["markers_doc", "dpi"]
    assert list(inspect.signature(aruco_detection.warp_page).parameters) == [
        "image", "homography", "width_px", "height_px",
    ]
    # La signature d'ENTREE de `extract_scan_frames` est verrouillee; son type
    # de retour a legitimement change sous la story 5.0.
    assert list(inspect.signature(aruco_detection.extract_scan_frames).parameters) == [
        "warped_page", "dpi", "output_dir",
    ]


def test_no_template_id_was_grafted_onto_the_poc_path() -> None:
    aruco_source = (
        REPO_ROOT / "src" / "mixed_media_utility" / "detection" / "aruco.py"
    ).read_text(encoding="utf-8")
    assert "template_id" not in aruco_source
    assert "page_templates" not in aruco_source


# --- AC 12: vocabulaire ferme -------------------------------------------------


def test_an_unknown_warning_code_is_refused() -> None:
    with pytest.raises(ValueError):
        scan_detection.validate_warning_code("PAGE_UN_PEU_DE_TRAVERS")
    for code in scan_detection.SCAN_DETECTION_WARNING_CODES:
        assert scan_detection.validate_warning_code(code) == code


def test_the_detection_vocabulary_is_distinct_from_the_ingestion_one() -> None:
    from mixed_media_utility import scan_ingest

    assert not (
        set(scan_detection.SCAN_DETECTION_WARNING_CODES)
        & set(scan_ingest.SCAN_INGEST_WARNING_CODES)
    ), "deux vocabulaires melanges: on ne saurait plus quelle etape emet quoi"


def test_the_story_boundaries_are_locked_by_a_test_not_by_prose() -> None:
    """Les Dev Notes exigent qu'un grep de ces symboles rende zero.

    Sans test, 5.3 pourra greffer un appel a `frame_image_rect_mm` ici sans que
    rien ne s'y oppose -- et le recadrage par la marge se retrouverait a cheval
    sur deux stories. Meme motif que les tests de purete du depot.
    """
    out_of_scope = (
        "frame_image_rect_mm",   # 5.3: recadrage par la marge
        "export_frame_tiff16",   # 5.6: export
        "build_frame_filename",  # 5.6: nommage
        "request_active_calibration",  # 5.4
        "apply_active_calibration",  # 5.4b: nouveau nom du meme contrat.
        # Les DEUX noms restent interdits ici. L'ancien parce qu'il ne doit
        # pas reapparaitre, le nouveau parce que la garde ne gardait plus rien
        # apres le renommage de la story 5.4b: un symbole absent du depot est
        # trivialement absent du module, et le test passait sans rien verifier.
        "persist_extraction",    # 5.7
        "reconstruct_project_manifest",  # 5.7
    )
    source = MODULE_PATH.read_text(encoding="utf-8")
    present = [symbol for symbol in out_of_scope if symbol in source]
    assert present == [], f"symboles hors perimetre de 5.2: {present}"


# --- AC 4 / AC 5 / AC 7: l'orchestration, contre de vraies pages -------------
#
# Ces tests font transiter des **images reelles** -- marqueurs ArUco rendus par
# `layout.generate_aruco_marker_image`, QR encode par `qr_codes` depuis un
# payload construit par `io.payload` -- par l'ingestion de 5.1 puis par
# `detect_lot_pages`. C'est le seul niveau ou les quatre statuts de decodage, le
# repli manifest et le multipage existent: les tests de fonctions pures les
# court-circuitent tous.


def _payload_for(template_id: str, **overrides) -> dict:
    from mixed_media_utility.io import payload as payload_io

    fields = {
        "project_id": "demo-project-01",
        "rush_id": "rush-a1",
        "lot_id": "lot-0007",
        "page_index": 0,
        "page_count": 1,
        "fps_target": 24.0,
        "timecode_base_fps": "25/1",
        "template_id": template_id,
        "patch_preset_id": "patchset-18-v1",
        "target_colorspace": "srgb",
        "gamut_map_id": payload_io.GAMUT_MAP_IDENTITY,
        "slots": [{"slot_index": 1, "frame_timecode": "00:00:01:00"}],
    }
    fields.update(overrides)
    return payload_io.build_page_payload(**fields)


def _render_page(
    template_id: str,
    payload: dict | None,
    *,
    dpi: int = SCAN_DPI,
    qr_copies: int = 1,
    drop_corner: int | None = None,
    extra_marker: int | None = None,
    qr_text: str | None = None,
) -> np.ndarray:
    """Une planche imprimee synthetique, rendue par les vrais producteurs.

    `qr_text` imprime un texte **litteral** au lieu de la serialisation de `payload`:
    c'est le seul moyen de fabriquer une planche d'un format que le producteur ne sait
    plus emettre -- une planche `1.0` a cles longues, par exemple, telle que celles
    deja imprimees du depot (story 5.17). Passer par `serialize_payload` donnerait un
    document a cles courtes portant `sv: "1.0"`, qui n'est pas ce qu'un tirage
    d'avant la story porte.
    """
    import cv2

    from mixed_media_utility import qr_codes
    from mixed_media_utility.io import payload as payload_io

    spec = page_templates.get_template(template_id)
    width, height = page_templates.page_size_px(spec, dpi)
    canvas = np.full((height, width, 3), 255, dtype=np.uint8)

    side, _ = page_templates.mm_to_px(layout.MARKER_SIZE_MM, 0, dpi)
    centers = page_templates.corner_marker_centers_mm(spec)
    placed = [mid for mid in layout.CORNER_MARKER_IDS if mid != drop_corner]
    for marker_id in placed:
        marker = layout.generate_aruco_marker_image(marker_id, side)
        cx, cy = page_templates.mm_to_px(*centers[marker_id], dpi)
        x0, y0 = cx - side // 2, cy - side // 2
        canvas[y0:y0 + side, x0:x0 + side] = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)

    if extra_marker is not None:
        marker = layout.generate_aruco_marker_image(extra_marker, side // 2)
        canvas[height // 2 - side // 2:height // 2, width // 4:width // 4 + side // 2] = (
            cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
        )

    if payload is not None or qr_text is not None:
        native = qr_codes.encode_qr_image(
            payload_io.serialize_payload(payload) if qr_text is None else qr_text
        )
        printed = qr_codes.render_for_print(native, qr_codes.QR_PRINT_SIZE_TARGET_MM, dpi)
        qh, qw = printed.shape[:2]
        for copy_index in range(qr_copies):
            y0 = (height - qh) // 2 + copy_index * (qh + 40)
            x0 = (width - qw) // 2
            canvas[y0:y0 + qh, x0:x0 + qw] = cv2.cvtColor(printed, cv2.COLOR_GRAY2BGR)
    return canvas


def _ingest(tmp_path: Path, pages: list[np.ndarray], *, slug="lot-0007", dpi=SCAN_DPI):
    """Ecrire les pages puis les ingerer par le **vrai** chemin de 5.1."""
    import cv2

    from mixed_media_utility import scan_ingest

    raw = tmp_path / "brut"
    raw.mkdir(exist_ok=True)
    for index, page in enumerate(pages):
        assert cv2.imwrite(str(raw / f"p{index:02d}.tif"), page)
    project_dir = tmp_path / "projet"
    project_dir.mkdir(exist_ok=True)
    report = scan_ingest.ingest_scan_lot(project_dir, raw, dpi=dpi, ingest_slug=slug)
    return project_dir, report


def _write_manifest(project_dir: Path, manifest: dict) -> None:
    (project_dir / "project.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )


def test_a_nominal_lot_is_detected_end_to_end(tmp_path: Path) -> None:
    project_dir, ingested = _ingest(
        tmp_path, [_render_page(PORTRAIT_2F, _payload_for(PORTRAIT_2F))]
    )
    report = scan_detection.detect_lot_pages(project_dir, ingested)

    assert len(report.detected_pages) == 1
    page = report.pages[0]
    assert page.status == scan_detection.PAGE_OK
    assert page.qr_status == "decoded"
    assert (page.template_id, page.template_source) == (PORTRAIT_2F, "qr")
    assert (page.lot_id, page.page_index) == ("lot-0007", 0)
    assert page.warnings == ()
    assert report.warnings == ()
    # Le quatrieme point du contrat de jonction: la geometrie resolue est bien
    # celle du template porte par la page.
    assert page.page_size_px == page_templates.page_size_px(
        page_templates.get_template(PORTRAIT_2F), SCAN_DPI
    )


def test_two_qr_symbols_refuse_the_page_and_the_status_says_multiple(
    tmp_path: Path,
) -> None:
    """Deux QR dans le champ, ce sont deux planches sur la vitre.

    Choisir le premier symbole fabriquerait un lot qui n'a jamais existe -- meme
    faute que la garde de marqueurs de coin en double sanctionne.
    """
    project_dir, ingested = _ingest(
        tmp_path, [_render_page(PORTRAIT_2F, _payload_for(PORTRAIT_2F), qr_copies=2)]
    )
    # Le manifest declare bien ce lot: si `DECODE_MULTIPLE` cessait d'etre un
    # refus, la page tomberait dans le repli et sortirait `status=ok`. Sans
    # manifest, le test passerait pour la mauvaise raison -- la page serait
    # refusee faute de substitut, pas parce qu'il y a deux symboles.
    _write_manifest(
        project_dir,
        {"reconstruction": {"template_id": PORTRAIT_2F}, "lots": [{"lot_id": "lot-0007"}]},
    )
    report = scan_detection.detect_lot_pages(project_dir, ingested)
    page = report.pages[0]
    assert page.status == scan_detection.PAGE_REFUSED
    assert page.qr_status == "multiple_symbols", (
        "un statut emprunte enverrait l'operateur inspecter un QR qui va bien"
    )
    assert page.template_id is None


def test_a_page_without_qr_borrows_the_template_of_its_own_lot(tmp_path: Path) -> None:
    project_dir, ingested = _ingest(tmp_path, [_render_page(PORTRAIT_2F, None)])
    _write_manifest(
        project_dir,
        {"reconstruction": {"template_id": PORTRAIT_2F}, "lots": [{"lot_id": "lot-0007"}]},
    )
    report = scan_detection.detect_lot_pages(project_dir, ingested)
    page = report.pages[0]
    assert page.status == scan_detection.PAGE_OK
    assert (page.template_id, page.template_source) == (PORTRAIT_2F, "manifest")
    assert page.qr_status == "no_symbol_detected"
    assert set(page.warnings) == {"TEMPLATE_FROM_MANIFEST_NOT_QR", "PAGE_WITHOUT_QR_SYMBOL"}


def test_a_manifest_that_does_not_declare_this_lot_is_not_a_substitute(
    tmp_path: Path,
) -> None:
    """La borne que l'AC 5 decrit, appliquee dans le seul cas ou elle sert.

    `reconstruction.template_id` est de niveau **projet**: sans verifier que le
    lot vise figure dans `lots[]`, un manifest mono-lot etranger faisait sortir
    une page portrait a deux zones en `status=ok` avec quatre zones paysage. Le
    slug d'ingestion est l'identite dont on dispose sans le QR.
    """
    project_dir, ingested = _ingest(tmp_path, [_render_page(PORTRAIT_2F, None)])
    _write_manifest(
        project_dir,
        {"reconstruction": {"template_id": PAYSAGE_4F}, "lots": [{"lot_id": "lot-9999"}]},
    )
    report = scan_detection.detect_lot_pages(project_dir, ingested)
    page = report.pages[0]
    assert page.status == scan_detection.PAGE_REFUSED
    assert page.template_id is None
    assert "indeterminable" in page.refusal_reason


def test_a_page_without_qr_and_without_manifest_is_refused(tmp_path: Path) -> None:
    # Jamais de `template_id` par defaut: une geometrie devinee aurait l'air
    # d'un succes.
    project_dir, ingested = _ingest(tmp_path, [_render_page(PORTRAIT_2F, None)])
    report = scan_detection.detect_lot_pages(project_dir, ingested)
    page = report.pages[0]
    assert page.status == scan_detection.PAGE_REFUSED
    assert page.qr_status == "no_symbol_detected"


@pytest.mark.parametrize(
    "manifest",
    [
        {"reconstruction": {"template_id": PORTRAIT_2F}, "lots": ["lot-0007"]},
        {"reconstruction": [PORTRAIT_2F], "lots": [{"lot_id": "lot-0007"}]},
        {"reconstruction": {"template_id": [PORTRAIT_2F]}, "lots": [{"lot_id": "lot-0007"}]},
        {"reconstruction": {"template_id": PORTRAIT_2F}, "lots": "lot-0007"},
        ["pas un objet"],
    ],
)
def test_a_manifest_of_unexpected_shape_never_takes_the_whole_lot_down(
    tmp_path: Path, manifest
) -> None:
    """`load_manifest` est un `json.load` nu, sans validation de schema.

    Un `lots` qui serait une liste de chaines levait un `AttributeError`, un
    `template_id` non hachable un `TypeError`: ni l'un ni l'autre n'est dans le
    tuple de rattrapage par page, donc **tout le lot** etait perdu -- y compris
    les pages qui n'avaient aucun probleme.
    """
    project_dir, ingested = _ingest(tmp_path, [_render_page(PORTRAIT_2F, None)])
    _write_manifest(project_dir, manifest)
    report = scan_detection.detect_lot_pages(project_dir, ingested)
    assert report.pages[0].status == scan_detection.PAGE_REFUSED
    assert scan_detection.manifest_template_id(project_dir, "lot-0007") is None


def test_a_decoded_page_refused_on_geometry_keeps_its_status_and_identity(
    tmp_path: Path,
) -> None:
    """Le cas le plus trompeur trouve en revue.

    QR parfaitement lisible, identite decodee, un coin manquant: le document
    publiait `qr_status=detected_but_unreadable`, `lot_id=None`. Le motif en
    prose disait la verite, le champ structure -- celui que 5.7 et 5.8
    consomment -- mentait.
    """
    payload = _payload_for(PORTRAIT_2F, page_index=1, page_count=2)
    project_dir, ingested = _ingest(
        tmp_path,
        [
            _render_page(PORTRAIT_2F, _payload_for(PORTRAIT_2F, page_count=2)),
            _render_page(PORTRAIT_2F, payload, drop_corner=2),
        ],
    )
    report = scan_detection.detect_lot_pages(project_dir, ingested)
    refused = report.pages[1]
    assert refused.status == scan_detection.PAGE_REFUSED
    assert refused.qr_status == "decoded"
    assert (refused.lot_id, refused.page_index) == ("lot-0007", 1)
    assert "manquants: [2]" in refused.refusal_reason
    # La page est physiquement la: le lot n'est pas incomplet.
    assert "PAGE_INDEX_MISSING" not in report.warnings


def test_one_failing_page_does_not_interrupt_the_others(tmp_path: Path) -> None:
    project_dir, ingested = _ingest(
        tmp_path,
        [
            _render_page(PORTRAIT_2F, _payload_for(PORTRAIT_2F, page_count=2)),
            _render_page(PORTRAIT_2F, None),
        ],
    )
    report = scan_detection.detect_lot_pages(project_dir, ingested)
    assert [page.status for page in report.pages] == [
        scan_detection.PAGE_OK, scan_detection.PAGE_REFUSED
    ]
    assert report.pages[1].qr_status == "no_symbol_detected"


def test_l_invariant_page_ok_et_homographie_est_le_meme_fait(tmp_path: Path) -> None:
    """`status == PAGE_OK` <=> `homography is not None`. Ce n'est pas un hasard.

    L'invariant est **utilise** par `cli._read_calibration_pages`, qui reunit les deux
    conditions, et les deux couches de la revue de la passe de correction de 5.19 en ont
    tire des conclusions opposees: l'une a demontre les deux mutants equivalents, l'autre a
    reclame un epinglage condition par condition. La seconde demandait un test impossible
    -- si les deux conditions sont le meme fait, rien ne peut distinguer le retrait de
    l'une du retrait de l'autre. Ce qui est epinglable, et epingle ici, c'est l'invariant.

    Il tient par **construction**: `_detect_one_page` n'a que deux sorties, et le test le
    verifie des deux cotes -- a l'execution sur les deux voies du vrai detecteur, puis sur
    la source, pour qu'un troisieme site de construction ne puisse pas apparaitre en
    silence. Sans ce second volet, le premier resterait vrai apres l'ajout d'un site
    fautif que le lot de ce test n'exerce pas.
    """
    project_dir, ingested = _ingest(
        tmp_path,
        [
            _render_page(PORTRAIT_2F, _payload_for(PORTRAIT_2F, page_count=2)),
            _render_page(PORTRAIT_2F, _payload_for(PORTRAIT_2F, page_index=1,
                                                  page_count=2), drop_corner=2),
        ],
    )
    report = scan_detection.detect_lot_pages(project_dir, ingested)
    # Les deux voies sont exercees, et dans cet ordre: une page saine, une page refusee
    # pour sa geometrie -- exactement le regime que la garde de la page de calibration
    # rencontre sur le terrain.
    assert [page.status for page in report.pages] == [
        scan_detection.PAGE_OK, scan_detection.PAGE_REFUSED]
    for page in report.pages:
        assert (page.status == scan_detection.PAGE_OK) == (page.homography is not None), (
            page.status, page.homography)

    import inspect

    source = inspect.getsource(scan_detection)
    assert source.count("DetectedPage(") == 2, (
        "un troisieme site de construction de DetectedPage casserait l'equivalence des "
        "deux conditions, et le mutant de `cli._read_calibration_pages` cesserait d'etre "
        "equivalent sans que rien ne le signale")


def test_a_foreign_marker_reaches_the_document_as_a_warning(tmp_path: Path) -> None:
    """L'AC 6 exige l'**emission** de l'avertissement, pas seulement son producteur.

    Les tests de `_partition_markers` verifient une liste; le mutant qui
    remplace l'`append` par un `pass` y survivait.
    """
    project_dir, ingested = _ingest(
        tmp_path,
        [_render_page(PORTRAIT_2F, _payload_for(PORTRAIT_2F), extra_marker=25)],
    )
    report = scan_detection.detect_lot_pages(project_dir, ingested)
    page = report.pages[0]
    assert page.status == scan_detection.PAGE_OK
    assert "FOREIGN_MARKER_DETECTED" in page.warnings
    assert [(m.marker_id, m.role) for m in page.foreign_markers] == [(25, layout.SLOT_ROLE)]


def test_two_detections_of_the_same_lot_render_the_same_document(tmp_path: Path) -> None:
    # L'AC 10 dit « deux **detections** », pas deux serialisations du meme objet
    # en memoire par une fonction pure.
    project_dir, ingested = _ingest(
        tmp_path, [_render_page(PORTRAIT_2F, _payload_for(PORTRAIT_2F))]
    )
    first = scan_detection.report_json(scan_detection.detect_lot_pages(project_dir, ingested))
    second = scan_detection.report_json(scan_detection.detect_lot_pages(project_dir, ingested))
    assert first == second


def test_the_pixels_come_from_the_ingestion_entry_point(
    tmp_path: Path, monkeypatch
) -> None:
    """Quatrieme point du contrat de jonction de 5.1.

    Un `cv2.imread` local reintroduirait ici le defaut de lecture du chemin POC,
    avec un ordre de canaux et une profondeur decides une seconde fois.
    """
    from mixed_media_utility import scan_ingest

    project_dir, ingested = _ingest(
        tmp_path, [_render_page(PORTRAIT_2F, _payload_for(PORTRAIT_2F))]
    )
    calls: list = []
    real = scan_ingest.load_page_array

    def spy(project, locator, *, dpi):
        calls.append((locator.source_path, dpi))
        return real(project, locator, dpi=dpi)

    monkeypatch.setattr(scan_ingest, "load_page_array", spy)
    scan_detection.detect_lot_pages(project_dir, ingested)
    assert len(calls) == 1 and calls[0][1] == SCAN_DPI


def test_a_detection_dpi_differing_from_the_ingested_one_is_named(
    tmp_path: Path,
) -> None:
    """Le symptome existait deja, sous le nom d'une **autre** cause.

    L'operateur lisait « la page a ete mise a l'echelle » la ou la vraie cause
    est « le dpi passe a la detection n'est pas celui du scan ».
    """
    project_dir, ingested = _ingest(
        tmp_path, [_render_page(PORTRAIT_2F, _payload_for(PORTRAIT_2F))]
    )
    report = scan_detection.detect_lot_pages(project_dir, ingested, dpi=600)
    assert "SCAN_DPI_DIFFERS_FROM_INGESTED" in report.warnings
    assert (report.scan_dpi, report.ingest_declared_dpi) == (600, SCAN_DPI)
    assert report.as_document()["ingest_declared_dpi"] == SCAN_DPI


# --- Story 5.27: le code de refus, contre le VRAI producteur ----------------
#
# Les tests unitaires du vocabulaire vivent dans
# `test_scan_detection_codes_de_refus.py`. Ceux-ci sont a leur place ici, et
# nulle part ailleurs: ils exigent une planche imprimee, un QR encode et
# l'ingestion de 5.1, c'est-a-dire les fabriques de ce fichier. Ce sont les
# seuls qui exercent le **mapping des exceptions etrangeres**, lequel ne vit
# qu'au site de rattrapage de `_detect_one_page`.


def _planche_a_version(tmp_path: Path, **champs) -> str:
    """Le texte QR d'une planche dont la version de schema n'est pas la notre.

    Meme chemin que `_future_version_sheet` de `test_payload_short_keys`: une
    planche a cles courtes, complete et valide, dont seule `sv` differe. C'est
    la seule facon de fabriquer aujourd'hui une planche que `parse_payload`
    refuse **apres** avoir decode -- le regime exact de la planche perimee `1.0`
    des tirages deja imprimes du depot.
    """
    from mixed_media_utility.io import payload as payload_io

    version = champs.pop("version", "9.9")
    payload = _payload_for(PORTRAIT_2F, **champs)
    court = json.loads(payload_io.serialize_payload(payload))
    if version is None:
        # Aucune cle de version: `PayloadVersionMissing`, l'autre sous-classe.
        court.pop("sv", None)
    else:
        court["sv"] = version
    return json.dumps(court, separators=(",", ":"))


def test_une_planche_perimee_sort_avec_son_code_propre(tmp_path: Path) -> None:
    """AC 4, contre le vrai producteur, et c'est le cas que 7.4 mesure.

    Une planche perimee sort `qr_status` **decode**, avec une identite lisible
    et `status=refused`: sans code, elle est litteralement indistinguable d'un
    refus de geometrie pour qui ne lit que les champs structures. La page visee
    est en **seconde** position, derriere un refus d'une autre famille -- un
    mapping qui rendrait toujours la premiere entree, ou toujours le repli
    generique, ne se demasque pas autrement.
    """
    from mixed_media_utility import qr_codes as qr

    geometrique = _render_page(
        PORTRAIT_2F, _payload_for(PORTRAIT_2F, page_count=2), drop_corner=2
    )
    perimee = _render_page(
        PORTRAIT_2F, None, qr_text=_planche_a_version(tmp_path, page_count=2)
    )
    project_dir, ingested = _ingest(tmp_path, [geometrique, perimee])
    report = scan_detection.detect_lot_pages(project_dir, ingested)

    premiere, seconde = report.pages
    assert premiere.status == seconde.status == scan_detection.PAGE_REFUSED
    # La planche perimee: son QR va parfaitement bien, son identite est lisible.
    assert seconde.qr_status == qr.DECODE_OK
    assert (seconde.project_id, seconde.lot_id) == ("demo-project-01", "lot-0007")
    assert seconde.refusal_code == scan_detection.REFUS_PLANCHE_PERIMEE
    # Le refus de geometrie, lui, porte le sien -- et ce n'est pas le meme.
    assert premiere.refusal_code == scan_detection.REFUS_COINS_MANQUANTS
    assert premiere.refusal_code != seconde.refusal_code
    # Les deux phrases francaises sont la, a cote, inchangees.
    assert "manquants: [2]" in premiere.refusal_reason
    assert "9.9" in seconde.refusal_reason
    # Et le code atteint le document, sous la cle que 7.4 nomme.
    document = scan_detection.report_document(report)
    assert [page["refusal_code"] for page in document["pages"]] == [
        scan_detection.REFUS_COINS_MANQUANTS,
        scan_detection.REFUS_PLANCHE_PERIMEE,
    ]


def test_une_planche_sans_cle_de_version_ne_porte_pas_le_code_de_la_perimee(
    tmp_path: Path,
) -> None:
    """AC 4, second volet: les **deux** sous-classes, assertees separement.

    La distinction est operationnelle et deja ecrite dans `io/payload`: une
    planche perimee se reimprime, un QR etranger (etiquette de colis, code d'un
    autre dispositif) se met a la poubelle. Un mapping qui les confondrait
    enverrait l'operateur reimprimer une planche qui n'a jamais existe.
    """
    sans_version = _render_page(
        PORTRAIT_2F, None, qr_text=_planche_a_version(tmp_path, version=None)
    )
    project_dir, ingested = _ingest(tmp_path, [sans_version])
    page = scan_detection.detect_lot_pages(project_dir, ingested).pages[0]
    assert page.status == scan_detection.PAGE_REFUSED
    assert page.refusal_code == scan_detection.REFUS_PAYLOAD_SANS_VERSION
    assert page.refusal_code != scan_detection.REFUS_PLANCHE_PERIMEE


def test_un_template_hors_registre_est_traduit_au_site_de_rattrapage(
    tmp_path: Path,
) -> None:
    """`UnknownTemplateError` est levee par `page_templates`, jamais ici: elle
    est traduite **au rattrapage**, ce qui garde l'enumeration entiere dans un
    seul module et laisse `page_templates` hors du diff."""
    payload = _payload_for(PORTRAIT_2F)
    payload["template_id"] = "tpl-qui-n-existe-pas"
    project_dir, ingested = _ingest(tmp_path, [_render_page(PORTRAIT_2F, payload)])
    page = scan_detection.detect_lot_pages(project_dir, ingested).pages[0]
    assert page.status == scan_detection.PAGE_REFUSED
    assert page.refusal_code == scan_detection.REFUS_TEMPLATE_INCONNU


def test_une_page_illisible_porte_le_code_de_l_ingestion(
    tmp_path: Path, monkeypatch
) -> None:
    """La troisieme famille etrangere: `load_page_array` refuse de rendre les
    pixels. Le refus n'a alors ni QR ni identite -- mais il a un code."""
    from mixed_media_utility import scan_ingest

    project_dir, ingested = _ingest(
        tmp_path, [_render_page(PORTRAIT_2F, _payload_for(PORTRAIT_2F))]
    )

    def refuser(*_args, **_kwargs):
        raise scan_ingest.PdfIngestError("page du PDF illisible")

    monkeypatch.setattr(scan_ingest, "load_page_array", refuser)
    page = scan_detection.detect_lot_pages(project_dir, ingested).pages[0]
    assert page.status == scan_detection.PAGE_REFUSED
    assert page.qr_status == scan_detection.QR_NOT_ATTEMPTED
    assert page.refusal_code == scan_detection.REFUS_PAGE_ILLISIBLE


def test_une_page_acceptee_ne_porte_aucun_code_de_refus(tmp_path: Path) -> None:
    """AC 7 sur le vrai chemin: `None`, jamais une chaine vide, jamais un code
    par defaut -- le symetrique du test precedent, et sans lui rien ne dit que
    le champ n'est pas rempli inconditionnellement."""
    project_dir, ingested = _ingest(
        tmp_path, [_render_page(PORTRAIT_2F, _payload_for(PORTRAIT_2F))]
    )
    page = scan_detection.detect_lot_pages(project_dir, ingested).pages[0]
    assert page.status == scan_detection.PAGE_OK
    assert page.refusal_code is None
    assert page.as_document()["refusal_code"] is None


def test_aucune_page_refusee_ne_sort_sans_code(tmp_path: Path) -> None:
    """L'invariant que le repli generique existe pour tenir: sur un chemin de
    refus, `refusal_code` n'est **jamais** `None`. Un lot de quatre pages
    refusees pour quatre causes de familles differentes, et les quatre codes
    sont distincts deux a deux."""
    pages = [
        _render_page(PORTRAIT_2F, _payload_for(PORTRAIT_2F, page_count=4),
                     drop_corner=2),
        _render_page(PORTRAIT_2F, None),
        _render_page(PORTRAIT_2F, None,
                     qr_text=_planche_a_version(tmp_path, page_count=4)),
        _render_page(PORTRAIT_2F, None,
                     qr_text=_planche_a_version(tmp_path, version=None)),
    ]
    project_dir, ingested = _ingest(tmp_path, pages)
    report = scan_detection.detect_lot_pages(project_dir, ingested)
    assert all(page.status == scan_detection.PAGE_REFUSED for page in report.pages)
    codes = [page.refusal_code for page in report.pages]
    assert all(code is not None for code in codes), codes
    assert all(code in scan_detection.SCAN_REFUSAL_CODES for code in codes), codes
    # Quatre causes de familles differentes, quatre codes differents: un mapping
    # qui replierait tout sur le generique passerait les assertions ci-dessus.
    assert len(set(codes)) == 4, codes
    assert scan_detection.REFUS_NON_CLASSE not in codes


def test_le_refus_de_lot_n_ecrit_aucun_document(tmp_path: Path) -> None:
    """AC 8: `LotIdentityError` emporte le lot, donc son code n'atteint **aucun**
    document -- il n'a d'autre porteur que l'exception, a cote de
    `identities_by_read_rank`. C'est le comportement d'aujourd'hui, et c'est
    lui que cette story fige."""
    mienne = _planche_a_version(tmp_path, page_count=2)
    etrangere = _planche_a_version(tmp_path, page_count=2, lot_id="lot-9999")
    pages = [
        _render_page(PORTRAIT_2F, None, qr_text=texte)
        for texte in (mienne, etrangere)
    ]
    project_dir, ingested = _ingest(tmp_path, pages)

    with pytest.raises(scan_detection.LotIdentityError) as excinfo:
        scan_detection.detect_lot_pages(project_dir, ingested)
    erreur = excinfo.value
    assert erreur.refusal_code == scan_detection.REFUS_PLUSIEURS_LOTS
    assert {identite[3] for identite in erreur.identities_by_read_rank} == {
        "lot-0007", "lot-9999"
    }
    # Aucun document: la moitie amont a bien produit ses pages, mais aucune
    # d'elles ne porte ce code -- le refus n'est pas un refus de page.
    _dpi, detectees = scan_detection.detect_pages(project_dir, ingested)
    assert all(
        page.refusal_code != scan_detection.REFUS_PLUSIEURS_LOTS
        for page in detectees
    )


def test_les_vocabulaires_existants_sont_inchanges_par_cette_story() -> None:
    """AC 10: cette story n'ajoute aucun etat, aucun statut, aucun
    avertissement aux vocabulaires existants -- elle en ouvre un nouveau, a
    cote, et n'en touche aucun."""
    assert scan_detection.PAGE_STATUSES == ("ok", "refused")
    assert scan_detection.PAGE_QR_STATUSES == (
        "decoded",
        "no_symbol_detected",
        "detected_but_unreadable",
        "multiple_symbols",
        "not_attempted",
    )
    assert scan_detection.SCAN_DETECTION_WARNING_CODES == (
        "TEMPLATE_FROM_MANIFEST_NOT_QR",
        "PAGE_WITHOUT_QR_SYMBOL",
        "FOREIGN_MARKER_DETECTED",
        "PAGE_SCALE_OUT_OF_TOLERANCE",
        "PAGE_ASPECT_OUT_OF_TOLERANCE",
        "INGEST_SLUG_DIFFERS_FROM_LOT_ID",
        "PAGE_COUNT_DIFFERS_FROM_INGESTED",
        "PAGE_COUNT_INCONSISTENT_ACROSS_PAGES",
        "PAGE_INDEX_MISSING",
        "PAGE_INDEX_DUPLICATED",
        "PAGE_INDEX_OUT_OF_RANGE",
        "SCAN_DPI_DIFFERS_FROM_INGESTED",
    )
    # Les deux vocabulaires sont **disjoints**: melanger un code de refus et un
    # code d'avertissement ferait un vocabulaire dont plus personne ne saurait
    # ce qu'il decrit.
    assert not set(scan_detection.SCAN_REFUSAL_CODES) & set(
        scan_detection.SCAN_DETECTION_WARNING_CODES
    )
