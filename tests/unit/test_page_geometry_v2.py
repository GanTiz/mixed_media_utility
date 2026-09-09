"""Geometrie de page resserree GEOMETRY_V2 (story 5.15).

Ce fichier porte les tests de la story 5.15 -- l'ajout d'une seconde version de
geometrie de page a cote de `GEOMETRY_V1`, sans en redefinir aucun identifiant.
Les tests anterieurs de geometrie vivent dans `test_pdf_composition.py`; ceux
d'ici sont ceux dont la raison d'etre est la **coexistence** des deux versions.

Le premier test du fichier est le filet de la story: il epingle `GEOMETRY_V1`
champ par champ, en dur. Il n'a aucune autre raison d'etre que de casser si
quiconque edite la v1 -- y compris involontairement, en croyant ne toucher qu'a
la v2.
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import (  # noqa: E402
    page_payload,
    page_roles,
    page_templates,
    patch_presets,
    pdf_composition,
    qr_codes,
)

PORTRAIT = page_templates.ORIENTATION_PORTRAIT
PAYSAGE = page_templates.ORIENTATION_PAYSAGE

def gabarits(geometry_version: str) -> tuple[tuple[str, int], ...]:
    """Les gabarits `(orientation, cardinal)` **d'une version**.

    Depuis la story 5.18 le vocabulaire depend de la version (`EPIC5-ARB-62`): la v1
    porte ses 11 gabarits historiques, la v2 en porte 9 -- le cardinal 6 en est sorti.
    Une parametrisation ecrite sur le vocabulaire global demanderait a la v2 des
    `template_id` qu'elle ne resout plus, et le test lirait « refus » la ou il croit
    mesurer une geometrie.
    """
    return tuple(
        (orientation, cardinal)
        for orientation in page_templates.ORIENTATIONS
        for cardinal in page_templates.frames_per_page_vocabulary(
            orientation, geometry_version)
    )


#: Les 11 gabarits de la v1 et les 9 de la v2.
GABARITS_V1 = gabarits("v1")
GABARITS_V2 = gabarits("v2")
#: Alias historique: les gabarits de la v1, ceux que les tests de non-regression de la
#: v1 balayent.
GABARITS = GABARITS_V1


def rects_overlap(a, b) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


# ---------------------------------------------------------------------------
# AC 1: GEOMETRY_V1 epinglee en dur, et intacte
# ---------------------------------------------------------------------------

#: Les champs de `GEOMETRY_V1`, **en dur**. Aucune valeur n'est ici recalculee ni
#: lue depuis une constante du module: ce tableau est une copie manuelle, et c'est
#: exactement ce qui lui donne son pouvoir. Comparer la v1 a une expression qui la
#: reconstruit ne verrouillerait rien -- c'est le meme argument que
#: `_HISTORICAL_FRAME_BANDS_MM`.
_V1_FIELDS_PINNED = {
    "version": "v1",
    "marker_size_mm": 30.0,
    "marker_margin_mm": 15.0,
    "marker_quiet_zone_mm": 15.0,
    "printer_margin_mm": 5.0,
    "patch_size_mm": 12.0,
    "patch_spacing_mm": 2.0,
    "patch_columns_per_side": {PORTRAIT: 2, PAYSAGE: 3},
    "patch_to_band_gap_mm": {PORTRAIT: 4.0, PAYSAGE: 3.0},
    "bottom_extra_clearance_mm": {PORTRAIT: 9.5, PAYSAGE: 2.0},
    # Ajoute par la story 5.15. `None` = les pastilles vont aux colonnes laterales
    # **sans exception**, donc la bande de la v1 ne depend d'aucun cardinal et reste
    # celle des planches deja imprimees.
    "border_witness_count": None,
    # Les trois champs ajoutes par la story 5.18. Leur valeur v1 est celle du
    # **defaut** du champ, et c'est la propriete qui fait tenir l'AC 1: la declaration
    # de `GEOMETRY_V1` n'a pas ete editee du tout, donc aucun de ces trois champs n'a
    # pu deplacer la v1 par inadvertance. Ils sont neanmoins epingles ici en dur --
    # comparer la v1 a `dataclasses.fields(...).default` ne verrouillerait rien, ce
    # serait la comparer a elle-meme.
    "frame_grid_gap_mm": 10.0,
    "qr_bearing_edge": "haut",
    "identity_in_header": False,
}

#: Les quatre nombres de la bande de frames de la v1, par orientation, en dur.
_V1_BANDS_PINNED = {
    PORTRAIT: {"x": 35.0, "y": 60.0, "width": 140.0, "height": 167.5},
    PAYSAGE: {"x": 48.0, "y": 60.0, "width": 201.0, "height": 88.0},
}


def test_geometry_v1_is_pinned_field_by_field() -> None:
    """**Le filet de la story 5.15.** Il casse si quiconque edite la v1.

    Une planche imprimee sous `tpl-a4-portrait-2f-v1` doit rester redressable a
    l'identique apres l'ajout de la v2: c'est la seule protection contre le scenario
    ou un lot deja imprime devient illisible. Le suffixe `-v1` d'un `template_id` ne
    vaut que si les constituants derriere lui ne bougent jamais.

    L'egalite des **noms** de champs est verifiee elle aussi: un champ ajoute a
    `PageGeometry` sans etre epingle ici ferait passer ce test tout en laissant la v1
    porter une valeur que personne ne regarde.
    """
    geometry = page_templates.GEOMETRY_V1
    names = {field.name for field in dataclasses.fields(geometry)}
    assert names == set(_V1_FIELDS_PINNED), (
        "Un champ de PageGeometry n'est pas epingle: ajouter sa valeur v1 dans "
        "_V1_FIELDS_PINNED, en dur, apres avoir verifie qu'elle ne deplace rien."
    )
    for name, expected in _V1_FIELDS_PINNED.items():
        actual = getattr(geometry, name)
        if isinstance(expected, dict):
            assert dict(actual) == expected, name
        else:
            assert actual == expected, name


@pytest.mark.parametrize("orientation", list(page_templates.ORIENTATIONS))
def test_geometry_v1_frame_band_is_pinned(orientation) -> None:
    """Les quatre nombres de la bande, en dur, pour les deux orientations.

    Ils sont **derives** des constituants depuis le 2026-08-10; les epingler en dur
    est la seule facon de verifier que la derivation ne les a pas deplaces d'un
    dixieme de millimetre, ce qui decouperait toute planche deja imprimee au mauvais
    endroit sans lever d'erreur.
    """
    band = page_templates.GEOMETRY_V1.frame_band_mm(orientation)
    assert set(band) == set(_V1_BANDS_PINNED[orientation])
    for key, value in _V1_BANDS_PINNED[orientation].items():
        assert band[key] == pytest.approx(value, abs=1e-12), key


#: Zones de frames de la v1, en dur, pour les 11 gabarits: le premier et le dernier
#: rectangle de chaque grille, plus la forme de la grille. Deux zones et non une:
#: une fabrique qui ne verifierait qu'un seul element rendrait invisible toute erreur
#: d'appariement (regle des fabriques du depot), et sur une grille c'est exactement
#: l'inversion colonnes/rangees qui passerait.
_V1_ZONES_PINNED = {
    (PORTRAIT, 1): ((1, 1), (35.0, 104.375, 140.0, 78.75),
                    (35.0, 104.375, 140.0, 78.75)),
    (PORTRAIT, 2): ((1, 2), (35.0, 60.0, 140.0, 78.75),
                    (35.0, 148.75, 140.0, 78.75)),
    (PORTRAIT, 3): ((1, 3), (61.2962962962963, 60.0, 87.4074074074074, 49.166666666666664),
                    (61.2962962962963, 178.33333333333331, 87.4074074074074,
                     49.166666666666664)),
    (PORTRAIT, 4): ((2, 2), (35.0, 102.1875, 65.0, 36.5625),
                    (110.0, 148.75, 65.0, 36.5625)),
    (PORTRAIT, 6): ((2, 3), (35.0, 78.90625, 65.0, 36.5625),
                    (110.0, 172.03125, 65.0, 36.5625)),
    (PORTRAIT, 8): ((2, 4), (38.888888888888886, 60.0, 61.111111111111114, 34.375),
                    (110.0, 193.125, 61.111111111111114, 34.375)),
    (PAYSAGE, 1): ((1, 1), (70.27777777777777, 60.0, 156.44444444444446, 88.0),
                   (70.27777777777777, 60.0, 156.44444444444446, 88.0)),
    (PAYSAGE, 2): ((2, 1), (48.0, 77.140625, 95.5, 53.71875),
                   (153.5, 77.140625, 95.5, 53.71875)),
    (PAYSAGE, 4): ((2, 2), (74.16666666666667, 60.0, 69.33333333333333, 39.0),
                   (153.5, 109.0, 69.33333333333333, 39.0)),
    (PAYSAGE, 6): ((3, 2), (48.0, 65.0625, 60.333333333333336, 33.9375),
                   (188.66666666666669, 109.0, 60.333333333333336, 33.9375)),
    (PAYSAGE, 8): ((4, 2), (48.0, 74.953125, 42.75, 24.046875),
                   (206.25, 109.0, 42.75, 24.046875)),
}


@pytest.mark.parametrize("orientation,cardinal", GABARITS_V1)
def test_v1_template_ids_still_resolve_to_the_same_zones(orientation, cardinal) -> None:
    """Les 11 gabarits v1 confrontes a des valeurs epinglees (AC 1).

    Le `template_id` est un contrat de geometrie: un lot imprime sous `-v1` et scanne
    apres cette story doit retrouver ses zones au millimetre. Le test porte sur les
    **trois** presets de marge, qui partagent la geometrie de page et ne changent que
    le recadrage interieur.
    """
    shape, first, last = _V1_ZONES_PINNED[(orientation, cardinal)]
    for margin_preset in sorted(page_templates.MARGIN_PRESETS_MM):
        spec = page_templates.template_for(orientation, cardinal, margin_preset, "v1")
        assert spec.template_id.endswith("-v1")
        assert (spec.grid_columns, spec.grid_rows) == shape, spec.template_id
        zones = spec.frame_zones_mm
        assert len(zones) == cardinal
        for zone, expected in ((zones[0], first), (zones[-1], last)):
            got = (zone["x"], zone["y"], zone["width"], zone["height"])
            assert got == pytest.approx(expected, abs=1e-9), (spec.template_id, zone["name"])


# ---------------------------------------------------------------------------
# AC 2: les identifiants v2 coexistent avec les v1, sans en redefinir aucun
# ---------------------------------------------------------------------------


def test_the_two_versions_share_no_template_id_and_cover_the_same_vocabulary() -> None:
    """« Ajouter une version ajoute des identifiants et n'en redefinit aucun. »

    Le test porte sur les **ensembles** et non sur un representant: un identifiant
    partage entre deux versions serait exactement le scenario ou une planche imprimee
    devient illisible, et il ne se verrait sur aucun cas particulier bien choisi.

    **Amende par la story 5.18**: une version peut aussi **retirer** un cardinal de son
    vocabulaire (`EPIC5-ARB-62`). Le vocabulaire de la v2 n'est donc plus celui de la
    v1; ce qui reste vrai, et ce qui compte, est qu'il en soit un **sous-ensemble
    strict** et que la difference soit exactement le cardinal retire -- une version qui
    ajouterait un gabarit inconnu de la v1 serait un autre changement, et il ne doit pas
    passer inapercu ici.

    **Amende une seconde fois par `EPIC5-ARB-64`**: le retrait porte **par orientation**,
    donc la difference n'est plus « le cardinal 6 dans les deux orientations » mais
    « le cardinal 6 en **portrait seulement** ». La difference est calculee depuis la
    table de retrait plutot que reecrite: c'est la seule facon qu'un retrait ajoute
    ailleurs tombe ici au lieu d'y etre recopie.
    """
    by_version: dict[str, set[str]] = {}
    for template_id in page_templates.known_template_ids():
        version = page_templates.get_template(template_id).geometry_version
        by_version.setdefault(version, set()).add(template_id)
    assert set(by_version) == set(page_templates.GEOMETRY_VERSIONS)
    assert "v1" in by_version and "v2" in by_version
    assert by_version["v1"].isdisjoint(by_version["v2"])
    strip = lambda ids, suffix: {i[: -len(suffix)] for i in ids}  # noqa: E731
    v1_bare, v2_bare = strip(by_version["v1"], "-v1"), strip(by_version["v2"], "-v2")
    assert v2_bare < v1_bare
    assert {bare for bare in v1_bare - v2_bare} == {
        f"tpl-a4-{orientation}-{cardinal}f{'' if margin == '0' else f'-m{margin}'}"
        for orientation in page_templates.ORIENTATIONS
        for cardinal in page_templates.FRAMES_PER_PAGE_VOCABULARY[orientation]
        if cardinal not in page_templates.frames_per_page_vocabulary(orientation, "v2")
        for margin in page_templates.MARGIN_PRESETS_MM
    }
    # Et la difference est bien celle d'`EPIC5-ARB-64`: le 6f portrait seulement. Ecrit
    # en dur ici, une fois, parce que c'est la decision produit et non une derivation.
    assert v1_bare - v2_bare == {
        f"tpl-a4-portrait-6f{'' if margin == '0' else f'-m{margin}'}"
        for margin in page_templates.MARGIN_PRESETS_MM
    }
    for orientation, cardinal in GABARITS_V2:
        for margin_preset in page_templates.MARGIN_PRESETS_MM:
            v1_id = page_templates.build_template_id(
                orientation, cardinal, margin_preset, "v1")
            v2_id = page_templates.build_template_id(
                orientation, cardinal, margin_preset, "v2")
            assert v1_id != v2_id
            assert v1_id.endswith("-v1") and v2_id.endswith("-v2")
            # Et la v2 rend bien une autre geometrie: un suffixe qui ne changerait
            # aucune zone serait un versionnement decoratif.
            assert (page_templates.get_template(v1_id).frame_zones_mm
                    != page_templates.get_template(v2_id).frame_zones_mm)


# ---------------------------------------------------------------------------
# AC 3: le bord porteur du QR est un max, et l'emprise du QR est MESUREE
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("orientation", list(page_templates.ORIENTATIONS))
def test_the_qr_bearing_edge_is_the_max_of_corner_clearance_and_qr_need(
        orientation) -> None:
    """Les quatre bords ne descendent pas ensemble (AC 3 de 5.15, AC 3 de 5.18).

    Trois bords suivent les marqueurs, le quatrieme suit le QR. Sous la v1 le degagement
    de coin (60 mm) domine l'exigence du QR (49,6), donc le `max` y est **transparent**
    -- et c'est cette transparence qui prouve que la v1 n'a pas bouge.

    Sous la v2 le bord porteur est **calcule**, et le `max` se lit sur le bord retenu:
    le QR y prend le bord bas dans la plupart des gabarits, ou il pousse le degagement a
    exactement son exigence, tandis que le bord haut retombe au degagement de coin.
    """
    v1, v2 = page_templates.GEOMETRY_V1, page_templates.GEOMETRY_V2
    assert v2.corner_clearance_mm() == 28.0
    assert v1.corner_clearance_mm() == 60.0
    qr_need = page_templates.qr_footprint_bound_mm() + 5.0 + 5.0
    assert v2.qr_edge_clearance_mm() == pytest.approx(qr_need)
    assert qr_need > v2.corner_clearance_mm()
    # v2, QR au bord haut: le bord haut vaut exactement l'exigence du QR.
    top_edges = v2.band_edges_mm(orientation, page_templates.QR_EDGE_TOP)
    assert top_edges["top"] == pytest.approx(qr_need)
    # v2, QR au bord bas: le bord haut retombe au degagement de coin -- c'est ce que la
    # mesure appelle « les 21,6 mm liberes » -- et le bas paie l'exigence du QR.
    bottom_edges = v2.band_edges_mm(orientation, page_templates.QR_EDGE_BOTTOM)
    assert bottom_edges["top"] == pytest.approx(v2.corner_clearance_mm())
    assert bottom_edges["bottom"] == pytest.approx(qr_need)
    assert top_edges["top"] - bottom_edges["top"] == pytest.approx(
        qr_need - v2.corner_clearance_mm())
    # v1: le degagement de coin domine, le bord haut reste a 60 mm.
    assert page_templates.frame_band_mm(orientation, "v1")["y"] == pytest.approx(60.0)
    assert qr_need < v1.corner_clearance_mm()


@pytest.mark.parametrize("orientation", list(page_templates.ORIENTATIONS))
def test_the_qr_on_a_flank_is_a_sum_with_the_patch_column_never_a_max(
        orientation) -> None:
    """**L'erreur de banc de la section 8.6, fermee cote production** (AC 3).

    Le banc ecrivait, pour un bord lateral, `left = max(bloc de pastilles + ecart,
    degagement du QR)`. Les deux grandeurs ne portent pas sur le meme espace: le bloc de
    pastilles occupe 5,0 a 11,0 mm et le QR aurait occupe 5,0 a 44,6 -- **les deux se
    chevauchaient**, et le banc rapportait une surface que la production n'aurait
    jamais pu composer.

    Le `max` est le bon modele pour deux **exigences** qui se disputent le meme espace
    (le degagement de coin et celui du QR au bord haut); il est faux pour deux
    **elements** qui doivent tenir cote a cote. Le test verifie les deux formes a la
    fois, et **sur les deux variantes de placement des temoins**: la variante
    « rangees haut/bas » ouvre sa bande au silence des marqueurs et le banc ne la
    modelisait pas du tout, donc elle aurait pose sa bande par-dessus le QR d'un flanc.
    """
    v2 = page_templates.GEOMETRY_V2
    lateral = (v2.patch_block_end_mm(orientation)
               + v2.patch_to_band_gap_mm[orientation])
    footprint = page_templates.qr_footprint_bound_mm()
    # **Le degagement du flanc se calcule** (releve d'Egan du 2026-08-12): il vaut la
    # somme quand la colonne de pastilles remplit le couloir, et seulement `marge d'encre
    # + emprise + garde` quand il reste sous elle la hauteur libre d'une emprise. Les
    # deux branches sont exercees par
    # `test_the_flank_clearance_is_computed_on_the_real_free_height`; ici on verifie que
    # celle qui s'applique est bien celle que la hauteur libre designe.
    expected = v2.qr_flank_clearance_mm(orientation)
    edges = v2.band_edges_mm(orientation, page_templates.QR_EDGE_LEFT)
    assert edges["left"] == pytest.approx(expected)
    assert edges["right"] == pytest.approx(lateral)
    if v2.lateral_free_height_mm(orientation) >= footprint:
        assert expected == pytest.approx(
            v2.printer_margin_mm + footprint + page_templates.TOP_BAND_GUARD_MM)
    else:
        # Une somme, pas un max: la difference est exactement l'emprise plus la garde.
        assert expected - lateral == pytest.approx(
            footprint + page_templates.TOP_BAND_GUARD_MM)
        assert expected > max(lateral, v2.qr_edge_clearance_mm())
    # Le flanc droit est le miroir exact du gauche.
    mirrored = v2.band_edges_mm(orientation, page_templates.QR_EDGE_RIGHT)
    assert mirrored["right"] == pytest.approx(edges["left"])
    assert mirrored["left"] == pytest.approx(edges["right"])
    # Et **les deux** candidats de bande reculent: la variante haut/bas ouvre au
    # silence des marqueurs (28 mm), qui est en deca de l'emprise du QR.
    for placement, band in v2.frame_band_candidates(
            orientation, page_templates.QR_EDGE_LEFT):
        assert band["x"] >= expected - 1e-9, placement
    # Sans QR sur ce flanc, la variante haut/bas ouvre bien plus tot: sans quoi
    # l'assertion precedente serait vraie sans rien dire.
    borders = dict(v2.frame_band_candidates(
        orientation, page_templates.QR_EDGE_BOTTOM))[
            page_templates.WITNESS_PLACEMENT_BORDERS]
    assert borders["x"] == pytest.approx(v2.corner_clearance_mm())
    assert borders["x"] < expected


def test_the_reserved_qr_footprint_bounds_every_real_payload() -> None:
    """**Le piege du facteur trois, ferme par la mesure** (AC 3).

    `place_witness_patches.qr_floor_mm()` a annonce 23,9 mm le 2026-08-11 matin, faux
    d'un facteur trois: le nombre de modules etait pose a la main (33 au lieu de 73 a
    109 reels) et le plancher physique confondu avec la taille imprimee. La taille se
    **mesure sur le payload serialise**, jamais sur une constante -- c'est deja la
    regle explicite de `plan_page_payload`.

    Ce test balaye donc de vrais payloads -- identifiants courts, nominaux et longs,
    tous les cardinaux, les trois presets de pastilles -- et confronte l'emprise
    reellement planifiee au majorant reserve. Il verifie **aussi** les deux extremites
    en modules: si un payload sortait de [73, 109], le majorant serait calcule aux
    mauvais points et pourrait etre depasse sans que rien d'autre ne le dise.
    """
    bound = page_templates.qr_footprint_bound_mm()
    seen_modules = set()
    worst = 0.0
    identifier_sets = (
        ("a", "b", "c"),
        ("projet_demo", "planche_4f_heteroclite", "planche_4f_heteroclite_4"),
        ("p" * 40, "r" * 40, "l" * 40),
    )
    for ids in identifier_sets:
        for preset in patch_presets.known_preset_ids():
            for cardinal in (1, 2, 3, 4, 6, 8, 10):
                try:
                    plan = page_payload.plan_page_payload(
                        project_id=ids[0], rush_id=ids[1], lot_id=ids[2],
                        page_index=0, page_count=999, fps_target=23.976,
                        timecode_base_fps="30000/1001",
                        template_id="tpl-a4-portrait-2f-v2",
                        patch_preset_id=preset, target_colorspace="bt709",
                        gamut_map_id="gamut-map-none-1",
                        slots=[{"slot_index": i, "frame_timecode": "12:34:56:12"}
                               for i in range(cardinal)],
                    )
                except Exception:  # budget depasse: la page est refusee ailleurs
                    continue
                seen_modules.add(plan.module_side)
                footprint = plan.print_size_mm * (
                    plan.module_side + 2 * qr_codes.QUIET_ZONE_MODULES
                ) / plan.module_side
                worst = max(worst, footprint)
                assert footprint <= bound + 1e-9, (ids[0], preset, cardinal, footprint)
    assert seen_modules, "aucun payload planifie: le balayage ne mesure rien"
    assert min(seen_modules) >= page_templates.QR_MIN_MODULE_SIDE
    assert max(seen_modules) <= page_templates.QR_MAX_MODULE_SIDE

    # --- Le cardinal **0**, avec le role de calibration (bloquant B3) -------------------
    #
    # C'est l'ajout d'une valeur dans cette boucle, et c'est ce qui aurait rendu le defaut
    # visible: le balayage partait du cardinal 1, donc le payload le plus **leger** de la
    # chaine -- une page sans emplacement -- n'etait mesure nulle part. Il sort de 0,288 mm
    # le majorant des planches, l'emprise etant en U.
    calibration_bound = page_templates.calibration_qr_footprint_bound_mm()
    calibration_modules = set()
    calibration_worst = 0.0
    for ids in identifier_sets:
        for preset in patch_presets.known_preset_ids():
            plan = page_payload.plan_page_payload(
                project_id=ids[0], rush_id=ids[1], lot_id=ids[2],
                page_index=0, page_count=999, fps_target=23.976,
                timecode_base_fps="",
                template_id="tpl-a4-portrait-2f-v2",
                patch_preset_id=preset, target_colorspace="bt709",
                gamut_map_id="gamut-map-none-1", slots=[],
                page_role=page_roles.PAGE_ROLE_CALIBRATION,
                # AMENDE PAR 5.23 (2026-08-18): le libelle de chaine est **obligatoire**
                # sous le role `c`, donc le payload le plus leger de la chaine est celui
                # d'un libelle d'**un** caractere. Rien n'interdit a un operateur de
                # nommer sa chaine `a`: c'est bien le plancher du domaine reel.
                #
                # Consequence a garder sous les yeux: le balayage sur `identifier_sets`
                # ne fait plus varier ce payload d'un octet, `project_id` ayant rejoint
                # les champs absents du role `c`. Il est conserve tel quel parce que
                # c'est **cette invariance** qui doit se voir -- `min == max` sur le
                # domaine --, et non parce qu'il balaye encore quelque chose.
                scan_chain_label="x",
            )
            calibration_modules.add(plan.module_side)
            footprint = plan.print_size_mm * (
                plan.module_side + 2 * qr_codes.QUIET_ZONE_MODULES
            ) / plan.module_side
            calibration_worst = max(calibration_worst, footprint)
            assert footprint <= calibration_bound + 1e-9, (ids[0], preset, footprint)
    assert min(calibration_modules) == page_templates.QR_CALIBRATION_MIN_MODULE_SIDE
    # Le domaine est desormais un **singleton** sur ce gabarit: les identifiants du
    # projet ne pesent plus sur le payload du role `c`. Une future divergence entre le
    # plancher et le maximum voudrait dire qu'un champ de niveau projet est revenu.
    assert min(calibration_modules) == max(calibration_modules), sorted(
        calibration_modules)
    # Et le majorant des planches ne borne **pas** cette page: c'est la mesure qui a
    # manque, et sans elle la marge de la page etait un effet du `ceil` du bloc.
    assert calibration_worst > bound + 1e-9, (calibration_worst, bound)
    # Le majorant est **atteint**, a moins d'un millimetre et demi pres: une
    # reservation trois fois trop grande passerait ce test sans rien garantir.
    assert bound - worst < 1.5, (bound, worst)
    # Et il est trois fois plus grand que le chiffre faux du matin.
    assert bound > 3 * 12.0


def test_the_calibration_qr_refusal_bites_on_the_bound_and_not_only_on_the_block() -> None:
    """**Bloquant B3, troisieme piece**: le refus mord sur ce qu'il annonce.

    Le refus de `_calibration_qr_rect` porte un docstring qui dit mot pour mot qu'il existe
    pour « le jour ou la borne majorante bougerait sans que la grille suive ». Ce jour est
    arrive -- l'emprise reelle a atteint 39,912 mm pour un majorant annonce a 39,624 -- et
    le refus ne s'est pas declenche: il comparait l'emprise au **bloc** (42,0 mm apres le
    `ceil` de la grille) et non au majorant. Il aurait fallu descendre a 38 modules.

    Le test construit l'evenement que le refus annonce attraper: un majorant abaisse sous
    l'emprise reelle, la grille inchangee. La comparaison au bloc, seule, laisserait passer
    -- et c'est verifie dans le meme test, sans quoi on ne saurait pas que le refus vient de
    la bonne comparaison.
    """
    from mixed_media_utility import patch_presets as pp

    spec = page_templates.get_template("tpl-a4-portrait-2f-v2")
    grid = spec.geometry.calibration_grid(
        spec.orientation, pp.CALIBRATION_PATCH_SIZE_MM)
    plan = page_payload.plan_page_payload(
        project_id="a", rush_id="b", lot_id="c",
        page_index=0, page_count=6, fps_target=24.0, timecode_base_fps="",
        template_id=spec.template_id, patch_preset_id="patches-14-v3",
        target_colorspace="b", gamut_map_id="gamut-map-none-1", slots=[],
        page_role=page_roles.PAGE_ROLE_CALIBRATION,
        # AMENDE PAR 5.23: obligatoire sous ce role (voir le test precedent).
        scan_chain_label="x",
    )
    emprise = plan.print_size_mm * (
        plan.module_side + 2 * qr_codes.QUIET_ZONE_MODULES) / plan.module_side
    _x, _y, block_w, _h = grid.qr_zone_mm()
    # L'etat livre: l'emprise tient dans le bloc **et** sous le majorant. Les deux
    # comparaisons passent, donc rien n'est refuse -- c'est le cas nominal.
    assert emprise <= block_w
    assert emprise <= page_templates.calibration_qr_footprint_bound_mm() + 1e-9
    pdf_composition._calibration_qr_rect(spec, grid, plan)

    # L'evenement que le refus annonce attraper: le majorant descend sous l'emprise reelle,
    # la grille ne suit pas. Le bloc l'absorbe encore -- c'est justement ce qui rendait le
    # refus muet -- donc seul un refus compare au **majorant** peut mordre.
    with pytest.MonkeyPatch.context() as monkey:
        monkey.setattr(page_templates, "calibration_qr_footprint_bound_mm",
                       lambda: emprise - 0.1)
        assert emprise <= block_w, "le bloc absorbe encore: c'est la moitie du defaut"
        with pytest.raises(pdf_composition.GeometryOverflowError) as refus:
            pdf_composition._calibration_qr_rect(spec, grid, plan)
    message = str(refus.value)
    assert f"{emprise:.3f}" in message, message
    assert "majorant" in message
    # Le message nomme les **deux** planchers de modules, celui de cette page et celui des
    # planches: c'est ce qui empeche de corriger en abaissant le mauvais.
    assert str(page_templates.QR_CALIBRATION_MIN_MODULE_SIDE) in message
    assert str(page_templates.QR_MIN_MODULE_SIDE) in message


def test_the_qr_footprint_is_u_shaped_so_the_worst_case_is_at_an_extremity() -> None:
    """Pourquoi le majorant se calcule aux deux extremites et non au cardinal 8.

    Le banc de recherche dimensionnait sur le cardinal 8 « parce que c'est le payload
    le plus lourd ». Mesure: l'emprise **decroit** tant que la taille imprimee est
    plafonnee a la cible (le silence ISO, compte en modules, pese relativement plus
    quand il y en a moins) puis **croit** quand la taille suit le plancher de
    lisibilite. Reserver l'emprise du cardinal 8 aurait fait refuser les pages legeres.
    """
    low = page_templates.QR_MIN_MODULE_SIDE
    high = page_templates.QR_MAX_MODULE_SIDE
    # Les bornes sont **lues** et non recopiees: la story 5.17 a deplace le plancher
    # de 73 a 61 modules, et un test qui epinglait 73 aurait mesure l'ancien domaine
    # en restant vert sur le nouveau.
    footprints = {n: page_templates.qr_footprint_mm(n) for n in range(low, high + 1, 2)}
    minimum = min(footprints, key=footprints.get)
    assert low < minimum < high, minimum
    assert footprints[low] > footprints[minimum]
    assert footprints[high] > footprints[minimum]
    # Le milieu du domaine n'est le pire cas d'aucune des deux branches.
    assert page_templates.qr_footprint_mm(
        low + 2 * ((high - low) // 4)) < page_templates.qr_footprint_bound_mm()
    assert page_templates.qr_footprint_bound_mm() == max(
        page_templates.qr_footprint_mm(low), page_templates.qr_footprint_mm(high))


def test_the_qr_and_typographic_mirrors_match_their_normative_modules() -> None:
    """Les miroirs de `qr_codes` et de `pdf_composition`, verrouilles egaux.

    `page_templates` est pur: il ne peut importer ni `qr_codes` (cv2) ni
    `pdf_composition` (qui l'importe). Sans ce verrou, la bande haute serait reservee
    sur une cible de QR perimee et le pied de page sur un interligne perime -- dans les
    deux cas en silence, et dans les deux cas d'un ou deux millimetres, donc invisible
    a l'oeil sur un rendu.
    """
    assert page_templates.QR_PRINT_SIZE_TARGET_MM == qr_codes.QR_PRINT_SIZE_TARGET_MM
    assert page_templates.QR_QUIET_ZONE_MODULES == qr_codes.QUIET_ZONE_MODULES
    assert page_templates.QR_MIN_SCAN_DPI == qr_codes.QR_MIN_SCAN_DPI
    assert page_templates.QR_MIN_PIXELS_PER_MODULE == (
        qr_codes.MIN_PIXELS_PER_MODULE_RELIABLE)
    # Le plancher de taille imprimee, recalcule par le module normatif.
    for module_side in (page_templates.QR_MIN_MODULE_SIDE, 85, 105,
                        page_templates.QR_MAX_MODULE_SIDE):
        expected = max(qr_codes.QR_PRINT_SIZE_TARGET_MM,
                       qr_codes.required_print_size_mm(module_side))
        got = page_templates.qr_footprint_mm(module_side) * module_side / (
            module_side + 2 * qr_codes.QUIET_ZONE_MODULES)
        assert got == pytest.approx(expected), module_side
    assert page_templates.BODY_FONT_MIN_PT == pdf_composition.BODY_FONT_MIN_PT
    assert page_templates.body_line_leading_mm() == pdf_composition.line_leading_mm(
        pdf_composition.BODY_FONT_MIN_PT)
    assert page_templates.TOP_BAND_GUARD_MM == pdf_composition._TOP_BAND_GUARD_MM
    assert page_templates.FOOTER_IDENTITY_LINE_COUNT == (
        pdf_composition.FOOTER_IDENTITY_LINE_COUNT)
    assert page_templates.SLOT_LABEL_STRIP_MM == (
        pdf_composition._SLOT_LABEL_OFFSET_MM + pdf_composition._SLOT_LABEL_HEIGHT_MM)


# ---------------------------------------------------------------------------
# AC 4: le pied de page est fonction de la geometrie (test anti-facade)
# ---------------------------------------------------------------------------

#: Les quatre nombres de chaque zone de pied de page de la v1, **en dur**: la
#: non-regression exigee par l'AC 4. Ces valeurs ne se reconstruisent depuis aucun
#: constituant (voir `page_templates._LEGACY_FOOTER_ZONES_MM`), et une planche v1
#: recomposee doit porter son texte au meme endroit.
_V1_FOOTER_ZONES_PINNED = {
    PORTRAIT: {"footer_block": (60.0, 240.0, 90.0, 45.0),
               "footer_line": (60.0, 286.0, 90.0, 6.0)},
    PAYSAGE: {"footer_block": (60.0, 154.0, 177.0, 42.0),
              "footer_line": (60.0, 198.0, 177.0, 6.0)},
}


@pytest.mark.parametrize("orientation", list(page_templates.ORIENTATIONS))
def test_the_v1_footer_zones_are_unchanged_by_their_derivation(orientation) -> None:
    for cardinal in page_templates.FRAMES_PER_PAGE_VOCABULARY[orientation]:
        spec = page_templates.template_for(orientation, cardinal, "0", "v1")
        zones = pdf_composition._footer_zones_mm(spec)
        assert set(zones) == set(_V1_FOOTER_ZONES_PINNED[orientation])
        for name, expected in _V1_FOOTER_ZONES_PINNED[orientation].items():
            assert zones[name] == pytest.approx(expected, abs=1e-12), (name, cardinal)


@pytest.mark.parametrize("field,value", [
    ("marker_margin_mm", 12.0),
    ("marker_size_mm", 20.0),
    ("marker_quiet_zone_mm", 9.0),
    ("printer_margin_mm", 7.0),
])
def test_mutating_a_constituent_moves_the_footer_zones(field, value) -> None:
    """**Le test qui distingue « derive » de « a l'air derive »** (AC 4).

    `_footer_zones_mm` rendait deux litteraux figes par orientation. Une derivation
    qui lirait une valeur figee, ou qui n'utiliserait qu'un seul des constituants,
    aurait le meme defaut tout en paraissant correcte. Chaque constituant est donc
    verifie **individuellement**: le test echoue si l'un des trois termes du
    degagement de coin, ou la marge d'encre, n'a aucun effet sur les zones.

    Il tourne sur la v2 parce que la v1 garde ses litteraux historiques: c'est la
    version **derivee** qu'il faut eprouver, et l'exiger de la v1 reviendrait a
    demander que les planches deja imprimees bougent.
    """
    reference = page_templates.get_template("tpl-a4-portrait-2f-v2")
    variant_geometry = dataclasses.replace(reference.geometry, **{field: value})
    variant = dataclasses.replace(
        reference,
        geometry=variant_geometry,
        frame_band=variant_geometry.frame_band_mm(reference.orientation, 2),
    )
    before = pdf_composition._footer_zones_mm(reference)
    after = pdf_composition._footer_zones_mm(variant)
    moved = {name for name in before if before[name] != after[name]}
    assert moved == set(before), (
        f"{field} = {value} ne deplace pas {set(before) - moved}: la zone est ecrite "
        "en litteral ou la derivation ignore ce constituant.")
    if field == "printer_margin_mm":
        # La marge d'encre pousse la pile vers le haut, elle n'en change pas la largeur.
        assert after["footer_line"][1] < before["footer_line"][1]
        assert after["footer_block"][2] == pytest.approx(before["footer_block"][2])
    else:
        # Les trois termes du degagement de coin ouvrent ou ferment la largeur.
        assert after["footer_block"][2] != pytest.approx(before["footer_block"][2])


def test_the_footer_block_height_is_what_the_text_needs_never_a_constant() -> None:
    """La hauteur du bloc est derivee du **texte**, pas d'une constante additive.

    Ce que le bloc doit loger est enumere, et **la liste depend de la disposition**
    depuis la story 5.18:

    * disposition historique (v1): 4 lignes d'identite (contrat 4.2), la ligne de
      date-heure que le rendu insere (EPIC4-ARB-8), et le budget de lignes techniques;
    * identite en entete (v2): les deux identifiants residuels et les rangees
      techniques, date fondue dedans.

    **Ce test ne confronte pas le budget au contenu** -- il re-derive la meme somme, et
    la revue de 5.15 a releve qu'il ne peut donc pas voir un ecart entre la reservation
    et ce que `_pack_lines` produit vraiment. Cette confrontation-la est le test
    suivant, `test_the_technical_line_budget_is_confronted_to_the_real_packing`.
    """
    geometry = page_templates.GEOMETRY_V2
    v1 = page_templates.GEOMETRY_V1
    leading = page_templates.body_line_leading_mm()
    v1_lines = (page_templates.FOOTER_IDENTITY_LINE_COUNT
                + page_templates.FOOTER_DATE_LINE_COUNT
                + page_templates.FOOTER_TECHNICAL_LINE_BUDGET)
    v2_lines = (page_templates.FOOTER_RESIDUAL_IDENTITY_LINE_COUNT
                + page_templates.FOOTER_TECHNICAL_ROW_BUDGET)
    assert v1.footer_block_height_mm() == pytest.approx(v1_lines * leading)
    assert geometry.footer_block_height_mm() == pytest.approx(v2_lines * leading)
    # Une hauteur qui ne dependrait pas de l'interligne serait une constante deguisee.
    assert geometry.footer_block_height_mm() > 4 * leading
    # **Le pied s'allege, et c'est le levier de la story**: deux lignes de moins que la
    # disposition historique, soit 9,12 mm rendus au bord bas.
    assert v1_lines - v2_lines == 2
    assert (v1.footer_block_height_mm() - geometry.footer_block_height_mm()
            == pytest.approx(2 * leading))
    # Le degagement du bas reste un `max`, pas une somme, et il est transparent en v1:
    # ses 69,5 mm couvrent largement les 54,48 que sa pile exige.
    assert (v1.corner_clearance_mm() + v1.bottom_extra_clearance_mm[PORTRAIT]
            > v1.bottom_text_clearance_mm())
    # En v2 en revanche c'est le texte qui borne le bord bas... tant que le QR n'y est
    # pas. Des qu'il y va, c'est lui, et le pied cesse totalement de borner la
    # geometrie -- ce que demande `EPIC5-ARB-63` mot pour mot.
    assert (geometry.corner_clearance_mm()
            + geometry.bottom_extra_clearance_mm[PORTRAIT]
            < geometry.bottom_text_clearance_mm())
    assert geometry.bottom_text_clearance_mm() < geometry.qr_edge_clearance_mm()


def test_a_technical_line_added_to_the_footer_costs_nothing_where_the_qr_bears_it():
    """**« Une donnee technique ne doit jamais etre bloquante »**, mesure (AC 5).

    C'est l'exigence d'`EPIC5-ARB-63` prise au mot, et elle est verifiable: sur les
    gabarits dont le QR prend le bord bas, le degagement du bord bas vaut l'exigence du
    QR, qui **domine** celle du pied. On peut donc ajouter des rangees techniques
    jusqu'a saturer cette marge sans retirer un millimetre a la zone de dessin.

    Le test mesure la marge en rangees entieres et verifie qu'elle est **strictement
    positive** -- sans quoi l'arbitrage serait tenu par accident, a la rangee pres.
    """
    geometry = page_templates.GEOMETRY_V2
    leading = page_templates.body_line_leading_mm()
    slack_mm = geometry.qr_edge_clearance_mm() - geometry.bottom_text_clearance_mm()
    assert slack_mm == pytest.approx(4.264, abs=1e-3)
    # Moins d'une rangee de jeu, et c'est le chiffre a garder sous les yeux: la
    # disposition livree est **au plus pres** de ce que le QR masque. Une septieme
    # rangee de pied (une ligne technique de plus que le budget) redeviendrait
    # bloquante, sur tous les gabarits a QR bas a la fois.
    assert 0 < slack_mm < leading
    # Et la propriete se lit sur la bande composee: une rangee technique de plus ne
    # deplace **aucune** zone des gabarits dont le QR est au bord bas.
    crowded = dataclasses.replace(geometry)
    for orientation, cardinal in GABARITS_V2:
        spec = page_templates.template_for(orientation, cardinal, "0", "v2")
        if spec.qr_edge != page_templates.QR_EDGE_BOTTOM:
            continue
        edges = crowded.band_edges_mm(orientation, page_templates.QR_EDGE_BOTTOM)
        assert edges["bottom"] == pytest.approx(geometry.qr_edge_clearance_mm())


#: Frames que `_composition_manifest` declare. Nomme parce que la pagination du lot
#: -- `ceil(frames / emplacements)` -- se relit au pied technique depuis la story
#: 11.4b, et qu'un banc qui la recalcule doit partir du meme cardinal que la fixture.
FRAMES_DU_MANIFESTE = 10


def _composition_manifest() -> tuple[dict, str]:
    """Manifest minimal suffisant pour composer un lot, sans aucun disque."""
    from mixed_media_utility.io import naming

    lot_id = naming.build_lot_id("rush-001", 5.0)
    manifest = {
        "schema_version": "2.1",
        "project_id": "proj-pied-de-page",
        "created": "2026-08-11T00:00:00Z",
        "rushes": [{
            "rush_id": "rush-001", "source_name": "rush-001.mov",
            "fps_source": 25.0, "fps_source_exact": "25/1",
            "resolution_source": {"width": 1920, "height": 1080},
        }],
        "lots": [{
            "lot_id": lot_id, "rush_id": "rush-001", "state": "extraction",
            "fps_target": 5.0, "fps_target_exact": "5/1",
            # Story 2.7 (payload 2.1): requis par `_lot_identity` pour composer.
            "timecode_base_fps": "25/1",
            "expected_frame_count": FRAMES_DU_MANIFESTE,
            "frames_dir": f"frames/{naming.derive_short_id('rush-001')}_"
                          f"{naming.format_fps_short(5.0)}",
            "source_frame_count": 50, "source_frame_count_is_exact": True,
            "rounding_policy": "floor",
        }],
        "artifacts": {"frames_dir": "frames"},
        "color": {"target_colorspace": "rec709"},
        "video": {}, "reconstruction": {},
    }
    return manifest, lot_id


#: Lignes que le pied de page technique occupe **reellement**, mesurees sur le chemin de
#: production (`_pack_lines` sur les six segments reels d'un lot compose), par
#: (version, orientation, preset de marge). La marge est un axe parce qu'elle allonge le
#: `template_id` -- donc le segment `template=...` -- et c'est ce qui fait passer la v1
#: portrait de 3 a 4 lignes.
#:
#: **Ce tableau existe parce que la mesure citee en commentaire de
#: `FOOTER_TECHNICAL_LINE_BUDGET` ne se reproduisait pas** (revue 5.15, couche 2): elle
#: annoncait 3 lignes a 90 mm, la production en rend 4 sur 12 des 33 gabarits v1, et
#: **aucun test ne confrontait la reservation au packing**. Les deux mutants du budget
#: mouraient par un test de surface epinglee, donc par accident.
_TECHNICAL_LINES_PACKED = {
    # v1: bloc de 90 mm en portrait (litteral historique), 177 en paysage.
    ("v1", PORTRAIT, "0"): 3,
    ("v1", PORTRAIT, "5"): 4,
    ("v1", PAYSAGE, "0"): 2,
    ("v1", PAYSAGE, "5"): 2,
    # v2 depuis la story 5.18: deux **colonnes** techniques, dans un pied lui-meme
    # retreci par le QR du bord bas -- 55,2 mm de colonne en portrait, 98,7 en paysage.
    # Le nombre de lignes double par rapport a une colonne unique, et le nombre de
    # **rangees** ne bouge pas: c'est la mesure qui dit que le repli sur deux colonnes
    # n'achete rien, contre le +1,2 % que le banc lui pretait.
    ("v2", PORTRAIT, "0"): 6,
    ("v2", PORTRAIT, "5"): 6,
    ("v2", PAYSAGE, "0"): 3,
    ("v2", PAYSAGE, "5"): 4,
}
#
# **Remesure de la story 11.4b, lot L (AC 6, `EPIC11-ARB-87`)**: le pied technique
# passe de six a **dix** renseignements, sous des cles courtes. Le chiffre qui compte
# est celui du **portrait**, la colonne bornante de 55,188 mm: il ne bouge pas -- 6
# lignes avant, 6 lignes apres. Dix renseignements tiennent exactement dans la place
# que six occupaient, et c'est le raccourcissement des cles qui l'achete, pas une
# rangee de plus ni un millimetre pris a une zone de dessin.
#
# Une seule case bouge, `(v2, PAYSAGE, "5")`, de 3 a 4 lignes -- et par la cause que
# ce tableau nomme deja: la marge allonge le `template_id` de trois caracteres
# (`tpl-a4-paysage-2f-m5-v2`), ce qui suffit desormais a rompre une ligne dans les
# 98,688 mm de la colonne paysage. La meme configuration a marge 0 reste a 3.

#: Rangees que le pied technique **occupe** vraiment, date comprise, par (version,
#: orientation, marge). A confronter au budget reserve: c'est le seul chiffre qui dit
#: si la reservation est juste, trop grande ou deja saturee.
#:
#: **La marge est un axe depuis la story 11.4b**, comme elle l'est depuis toujours
#: pour `_TECHNICAL_LINES_PACKED`, et pour la meme cause: elle allonge le
#: `template_id`. Avec dix renseignements au lieu de six, cet allongement fait
#: basculer une rangee en paysage (2 a marge 0, **3** a marge 5). La clef a deux
#: termes confondait les deux regimes et n'aurait pu epingler qu'un seul des deux.
_TECHNICAL_ROWS_USED = {
    ("v2", PORTRAIT, "0"): 4,
    ("v2", PORTRAIT, "5"): 4,
    ("v2", PAYSAGE, "0"): 2,
    ("v2", PAYSAGE, "5"): 3,
}

#: Jeu de la pile de pied de page, en **lignes**, par version. Il n'est pas de la meme
#: nature des deux cotes, et c'est le fait que la mesure a etabli:
#:
#: * en **v2** la hauteur du bloc est derivee du budget, donc le jeu vaut exactement
#:   `budget - packing reel` -- une ligne en portrait, deux en paysage. Un segment
#:   technique de plus consomme la derniere ligne du portrait; deux de plus font lever
#:   `GeometryOverflowError` sur les 18 gabarits v2 portrait a la fois;
#: * en **v1** la hauteur est un litteral (45 mm en portrait, 42 en paysage) que le
#:   budget ne gouverne pas: le jeu y est de 3,96 mm en portrait, soit **moins d'une
#:   ligne**, pour un packing reel de 4 lignes techniques. La v1 n'a donc aucune marge
#:   supplementaire malgre son bloc plus haut -- elle a un bloc plus etroit.
#:
#: **Remesure de la 11.4b, lot L**: le portrait ne bouge pas (jeu nul, deja sature
#: avant la story), le paysage perd une rangee de jeu **a marge 5 seulement** --
#: meme cause que ci-dessus, le `template_id` allonge. D'ou l'axe de marge ici aussi.
_FOOTER_SLACK_LINES = {
    ("v2", PORTRAIT, "0"): 0,
    ("v2", PORTRAIT, "5"): 0,
    ("v2", PAYSAGE, "0"): 2,
    ("v2", PAYSAGE, "5"): 1,
}

#: Segments techniques que l'on peut **ajouter** avant que le pied ne deborde, par
#: (version, orientation, marge), mesure en les ajoutant vraiment. Zero rangee de jeu
#: en portrait ne veut pas dire zero marge: deux colonnes absorbent une ligne de plus
#: dans les memes quatre rangees. C'est ce chiffre-la, et pas le jeu en rangees, qui dit
#: ce qu'une ligne technique de plus couterait -- et il est **tres asymetrique**: une
#: seule en portrait, huit en paysage, ou la colonne fait 98,7 mm au lieu de 55,2. Un
#: segment de plus dans le pied technique doit donc etre chiffre en **portrait**, la ou
#: il est le plus cher, et jamais en paysage.
#:
#: **Remesure de la 11.4b, lot L, et c'est le chiffre a retenir de l'AC 6**: en
#: portrait il vaut **1 avant comme apres**. Les quatre renseignements ajoutes n'ont
#: donc rien coute la ou le pied est le plus cher -- ils ont ete finances par le
#: raccourcissement des cles et par celui de la mention de provenance, pas par une
#: rangee supplementaire. En paysage il passe de 9 a 8 (marge 0) et a 7 (marge 5).
_TECHNICAL_SEGMENTS_BEFORE_OVERFLOW = {
    ("v2", PORTRAIT, "0"): 1,
    ("v2", PORTRAIT, "5"): 1,
    ("v2", PAYSAGE, "0"): 8,
    ("v2", PAYSAGE, "5"): 7,
}

#: Jeu reel, en millimetres, des versions a pied de page **litteral** (la v1). Epingle
#: parce que c'est la seule facon de voir que le cas le plus charge -- portrait, marge
#: 5, donc 4 lignes techniques -- ne dispose que de **3,96 mm**, soit moins d'une ligne
#: de 4,56: une septieme ligne technique ferait lever le refus de tenue verticale sur
#: 12 des 33 gabarits v1.
_FOOTER_LITERAL_SLACK_MM = {
    ("v1", PORTRAIT, "0"): 8.52,
    ("v1", PORTRAIT, "5"): 3.96,
    ("v1", PAYSAGE, "0"): 10.08,
    ("v1", PAYSAGE, "5"): 10.08,
}


@pytest.mark.parametrize("geometry_version,orientation,margin_preset",
                         sorted(_TECHNICAL_LINES_PACKED))
def test_the_technical_line_budget_is_confronted_to_the_real_packing(
        geometry_version: str, orientation: str, margin_preset: str,
        monkeypatch) -> None:
    """`FOOTER_TECHNICAL_LINE_BUDGET` contre ce que la composition pose vraiment.

    Le budget est une **reservation**: il ne peut pas etre derive dans un module qui
    ignore tout du lot, donc il doit etre confronte au contenu par un test -- et il ne
    l'etait par aucun. Le test compose un lot reel et compte les lignes que
    `_pack_lines` produit, puis verifie trois choses que la reservation seule ne dit
    pas: le nombre de lignes posees, que la zone les loge (avec la ligne de date-heure
    que le rendu ajoute), et **le jeu qui reste**, epingle en lignes.

    C'est ce dernier chiffre qui fait mourir les mutants du budget pour la bonne
    raison: a 2 il n'y a plus de jeu du tout en v2 portrait, a 4 il y en a deux fois
    trop. Avant, les deux mouraient par une surface epinglee ailleurs.
    """
    manifest, lot_id = _composition_manifest()
    plan = pdf_composition.compose_lot_plan(
        manifest=manifest, lot_id=lot_id, orientation=orientation,
        frames_per_page=2, margin_preset=margin_preset,
        geometry_version=geometry_version,
    )
    blocks = {b.name: b for b in _images_pages(plan)[0].text.blocks}
    leading = page_templates.body_line_leading_mm()
    date_block, date_index = _images_pages(plan)[0].text.date_line_slot
    technical = [blocks[name] for name in page_templates.FOOTER_TECHNICAL_ZONE_NAMES
                 if name in blocks]
    if technical:
        # Disposition « identite en entete »: la technique vit dans ses colonnes, et le
        # bloc de pied ne porte plus que les identifiants residuels.
        packed = sum(len(block.lines) for block in technical)
        assert len(blocks["footer_block"].lines) == (
            page_templates.FOOTER_RESIDUAL_IDENTITY_LINE_COUNT)
        assert date_block == page_templates.FOOTER_TECHNICAL_ZONE_NAMES[0]
        assert date_index == 0
        rows_used = max(
            len(block.lines) + (1 if block.name == date_block else 0)
            for block in technical
        )
        assert rows_used == _TECHNICAL_ROWS_USED[
            (geometry_version, orientation, margin_preset)], (
            plan.template_id, [block.lines for block in technical])
        assert rows_used <= page_templates.FOOTER_TECHNICAL_ROW_BUDGET
        for block in technical:
            lines = len(block.lines) + (1 if block.name == date_block else 0)
            assert lines * leading <= block.rect_mm[3] + 1e-9, block.name
        slack_rows = page_templates.FOOTER_TECHNICAL_ROW_BUDGET - rows_used
        assert slack_rows == _FOOTER_SLACK_LINES[
            (geometry_version, orientation, margin_preset)]
        assert packed == _TECHNICAL_LINES_PACKED[
            (geometry_version, orientation, margin_preset)], (
                plan.template_id, [block.lines for block in technical])
        # **Combien de segments de plus tiendraient**, mesure en les ajoutant: c'est le
        # chiffre qui manque au jeu en rangees quand il vaut zero.
        _assert_technical_segments_before_overflow(
            monkeypatch, manifest, lot_id, orientation, margin_preset,
            geometry_version,
            _TECHNICAL_SEGMENTS_BEFORE_OVERFLOW[
                (geometry_version, orientation, margin_preset)])
        return
    block = blocks["footer_block"]
    packed = len(block.lines) - page_templates.FOOTER_IDENTITY_LINE_COUNT
    assert packed == _TECHNICAL_LINES_PACKED[
        (geometry_version, orientation, margin_preset)], (plan.template_id, block.lines)

    # La zone loge ce qui y est pose, plus la ligne de date-heure ajoutee au rendu.
    needed = (len(block.lines) + page_templates.FOOTER_DATE_LINE_COUNT) * leading
    available = block.rect_mm[3]
    assert needed <= available + 1e-9, (plan.template_id, needed, available)
    assert (date_block, date_index) == (
        "footer_block", page_templates.FOOTER_IDENTITY_LINE_COUNT)

    slack_lines = _FOOTER_SLACK_LINES.get(
        (geometry_version, orientation, margin_preset))
    if slack_lines is not None:
        # Version a pied de page **derive** sans colonnes: le jeu est exactement ce que
        # le budget reserve en trop, et il se compte en lignes entieres.
        assert page_templates.FOOTER_TECHNICAL_LINE_BUDGET - packed == slack_lines
        assert available - needed == pytest.approx(slack_lines * leading, abs=1e-9)
    else:
        # Version a pied de page **litteral**: le budget ne gouverne pas la hauteur, et
        # le jeu reel s'y epingle en millimetres. Le nommer ici evite de croire que la
        # v1 dispose d'une reserve parce que son bloc est plus haut: son cas le plus
        # charge n'a pas une ligne d'avance.
        slack_mm = _FOOTER_LITERAL_SLACK_MM[
            (geometry_version, orientation, margin_preset)]
        assert available - needed == pytest.approx(slack_mm, abs=0.01), (
            plan.template_id, available, needed)
        assert min(_FOOTER_LITERAL_SLACK_MM.values()) < leading


def _assert_technical_segments_before_overflow(
        monkeypatch, manifest, lot_id, orientation, margin_preset, geometry_version,
        expected: int) -> None:
    """Combien de segments techniques de plus le pied absorbe, **mesure en les posant**.

    Le budget est une reservation; le test appelant la confronte au packing reel, et
    cette fonction-ci ferme le dernier trou: quand le jeu en **rangees** vaut zero, il
    reste malgre tout de la place dans les colonnes, et rien ne le dirait. Le seul
    instrument honnete est d'ajouter des segments jusqu'au refus et de compter.

    Les segments sont ajoutes en enveloppant `_pack_lines`, donc **tout le reste du
    chemin de production est celui de la production**: la largeur de colonne, la
    repartition entre colonnes, la garde de tenue verticale.
    """
    real_pack = pdf_composition._pack_lines
    extras: list[str] = []

    def packed_with_extras(parts, width_mm, font_pt, separator=" - "):
        return real_pack(list(parts) + extras, width_mm, font_pt, separator)

    monkeypatch.setattr(pdf_composition, "_pack_lines", packed_with_extras)
    for count in range(expected + 2):
        extras[:] = [f"diagnostic{index}=xxxxxxxxxx" for index in range(count)]
        try:
            pdf_composition.compose_lot_plan(
                manifest=manifest, lot_id=lot_id, orientation=orientation,
                frames_per_page=2, margin_preset=margin_preset,
                geometry_version=geometry_version)
        except pdf_composition.GeometryOverflowError:
            assert count == expected + 1, (
                f"{geometry_version}/{orientation}: le pied deborde des {count} "
                f"segment(s) supplementaire(s), {expected} etaient attendus")
            monkeypatch.undo()
            return
    monkeypatch.undo()
    raise AssertionError(
        f"{geometry_version}/{orientation}: {expected + 1} segments de plus ne font "
        "pas deborder le pied -- la reservation est plus large qu'annonce")


def test_the_reserved_technical_budget_covers_every_derived_gabarit() -> None:
    """Le budget borne le packing de **toutes** les versions qu'il gouverne.

    Le test precedent mesure quatre axes; celui-ci ferme la porte de derriere: si une
    version future ouvrait un bloc plus etroit que 90 mm, son packing depasserait le
    budget et la reservation deviendrait fausse en silence (le refus de tenue verticale
    ne parlerait qu'au premier lot dont les identifiants sont longs).
    """
    manifest, lot_id = _composition_manifest()
    worst = {}
    for version in page_templates.GEOMETRY_VERSIONS:
        geometry = page_templates.get_geometry(version)
        for orientation in page_templates.ORIENTATIONS:
            plan = pdf_composition.compose_lot_plan(
                manifest=manifest, lot_id=lot_id, orientation=orientation,
                frames_per_page=2, margin_preset="5", geometry_version=version,
            )
            blocks = {b.name: b for b in _images_pages(plan)[0].text.blocks}
            date_block, _index = _images_pages(plan)[0].text.date_line_slot
            technical = [blocks[name]
                         for name in page_templates.FOOTER_TECHNICAL_ZONE_NAMES
                         if name in blocks]
            derived = geometry.footer_block_height_mm()
            if technical:
                # Disposition a colonnes: ce que le budget gouverne est le nombre de
                # **rangees** d'une colonne, date comprise -- pas le nombre de lignes
                # posees, qui se repartit sur les colonnes.
                rows = max(len(block.lines) + (1 if block.name == date_block else 0)
                           for block in technical)
                total = (blocks["footer_block"].rect_mm[3]
                         + sum(block.rect_mm[3] for block in technical[:1]))
                if total == pytest.approx(derived):
                    worst[(version, orientation)] = rows
                continue
            block = blocks["footer_block"]
            packed = len(block.lines) - page_templates.FOOTER_IDENTITY_LINE_COUNT
            if block.rect_mm[3] == pytest.approx(derived):
                worst[(version, orientation)] = packed
    assert worst, "aucun gabarit a pied de page derive: le budget ne gouverne rien"
    assert max(worst.values()) <= page_templates.FOOTER_TECHNICAL_ROW_BUDGET
    # Et la valeur retenue est celle que la mesure impose: le pire packing des versions
    # derivees, **sature**. Le budget de la disposition a colonnes n'a pas de rangee de
    # jeu, et c'est un fait a garder sous les yeux plutot qu'a corriger: une rangee de
    # plus porterait la pile de pied a 49,92 mm quand l'emprise du QR en reserve 49,62,
    # donc le pied redeviendrait **bloquant** sur tous les gabarits a QR bas a la fois.
    # Le jeu reel est mesure en segments par
    # `test_the_technical_line_budget_is_confronted_to_the_real_packing`.
    assert page_templates.FOOTER_TECHNICAL_ROW_BUDGET == max(worst.values())


# ---------------------------------------------------------------------------
# AC 5: le placement des temoins est CALCULE, jamais deduit
# ---------------------------------------------------------------------------


def _drawing_area(geometry, orientation, cardinal, band=None) -> float:
    """Surface de dessin d'une bande, **aux pas de grille de cette geometrie**.

    Les deux pas sont passes explicitement: le pas horizontal est un champ de la version
    depuis la story 5.18 et le pas vertical en est derive (il porte l'etiquette
    d'emplacement). Laisser les defauts de `_drawing_area_mm2` mesurerait la v2 au pas
    de la v1, donc une surface que la production ne compose pas.
    """
    band = band if band is not None else geometry.frame_band_mm(orientation, cardinal)
    return page_templates._drawing_area_mm2(
        band, cardinal, geometry.frame_grid_gap_mm, geometry.frame_grid_row_gap_mm())


@pytest.mark.parametrize("orientation,cardinal", GABARITS_V2)
def test_the_retained_witness_placement_is_the_largest_of_the_two(
        orientation, cardinal) -> None:
    """Les deux placements sont composes, le plus grand rendu est retenu (AC 5).

    Interdiction explicite de choisir depuis la seule dimension limitante: mesure a
    l'appui, cette heuristique a fait chuter un cardinal de +122 % a +67 %
    (`EPIC5-ARB-55`). La dimension limitante dit ce qui borne la zone *avant* le
    deplacement; elle ne dit rien du cout du deplacement lui-meme.
    """
    geometry = page_templates.GEOMETRY_V2
    # **Les candidats sont le produit des deux axes** depuis la story 5.18: quatre bords
    # porteurs du QR x deux placements de temoins. Les comparer separement rendrait un
    # optimum local, et le test doit donc regarder le produit -- huit candidats, pas
    # deux.
    candidates = geometry._candidates(orientation)
    assert len(candidates) == 8, "la v2 compose 4 bords x 2 placements"
    for qr_edge in page_templates.QR_EDGES:
        names = [placement for edge, placement, _band in candidates
                 if edge == qr_edge]
        assert names == [page_templates.WITNESS_PLACEMENT_SIDES,
                         page_templates.WITNESS_PLACEMENT_BORDERS], qr_edge
    retained = _drawing_area(geometry, orientation, cardinal)
    for _edge, name, band in candidates:
        assert retained >= _drawing_area(geometry, orientation, cardinal, band) - 1e-9, (
            name, orientation, cardinal)
    # Le gabarit du registre porte le placement retenu **et le bord retenu**, et sa
    # bande est celle qui a produit ses zones: un spec qui porterait l'un et les zones
    # de l'autre serait indetectable autrement.
    spec = page_templates.template_for(orientation, cardinal, "0", "v2")
    assert spec.witness_placement == geometry.witness_placement(orientation, cardinal)
    assert spec.qr_edge == geometry.qr_edge(orientation, cardinal)
    assert spec.frame_band_mm == geometry.frame_band_mm(orientation, cardinal)


def test_under_the_registered_v2_the_lateral_columns_win_on_every_gabarit() -> None:
    """**Mesure, et elle contredit l'AC 5 de la story sur un point.**

    L'AC demandait qu'« au moins un gabarit choisisse chaque placement ». C'est
    mesurable, et c'est faux pour la v2 telle qu'elle est retenue: avec une colonne de
    temoins par cote, les colonnes laterales ne coutent que 10 mm de largeur par cote,
    la ou les rangees haut/bas coutent 10 mm de **hauteur** en haut et en bas -- et la
    hauteur est la dimension rare sur les onze gabarits. Les cotes gagnent donc partout,
    de 12 % a 37 %.

    Ce fait est epingle ici plutot que corrige: il dit que la comparaison de l'AC 5 est
    reelle mais **a sens unique** sur cette geometrie, et donc que le test precedent ne
    prouverait pas a lui seul que la comparaison a lieu. C'est le test suivant qui la
    prouve, sur une geometrie ou l'autre branche gagne.
    """
    geometry = page_templates.GEOMETRY_V2
    for orientation, cardinal in GABARITS_V2:
        assert geometry.witness_placement(orientation, cardinal) == (
            page_templates.WITNESS_PLACEMENT_SIDES), (orientation, cardinal)


def test_both_witness_placements_are_reachable_by_the_comparison() -> None:
    """La comparaison peut retenir **l'une ou l'autre** branche (AC 5).

    Sans ce test, remplacer tout le calcul par « rendre les cotes » passerait la suite
    entiere: aucun gabarit livre ne choisit les rangees haut/bas. La geometrie
    construite ici n'est pas arbitraire -- elle pousse le seul parametre qui rend les
    colonnes cheres (six colonnes de temoins par cote, soit 51 mm de bord mange) et
    reduit le nombre de temoins a poser, exactement le regime ou la regle d'Egan
    (« les temoins vont sur les bords qui ne portent pas la dimension limitante »)
    devient gagnante.
    """
    import types

    crowded = dataclasses.replace(
        page_templates.GEOMETRY_V2,
        patch_columns_per_side=types.MappingProxyType({PORTRAIT: 6, PAYSAGE: 6}),
        border_witness_count=4,
    )
    chosen = {
        (orientation, cardinal): crowded.witness_placement(orientation, cardinal)
        for orientation, cardinal in GABARITS_V2
    }
    assert page_templates.WITNESS_PLACEMENT_BORDERS in chosen.values(), chosen
    assert page_templates.WITNESS_PLACEMENT_SIDES in chosen.values(), chosen
    # Et dans les deux sens: la branche retenue rend bien plus que l'autre, **a bord de
    # QR egal**. Comparer contre les candidats de tous les bords confondus melangerait
    # les deux axes et rendrait l'assertion fausse pour une bonne raison.
    for (orientation, cardinal), placement in chosen.items():
        edge = crowded.qr_edge(orientation, cardinal)
        areas = {
            name: _drawing_area(crowded, orientation, cardinal, band)
            for name, band in crowded.frame_band_candidates(orientation, edge)
        }
        assert areas[placement] == max(areas.values()), (orientation, cardinal)


def test_a_version_without_border_witnesses_never_depends_on_the_cardinal() -> None:
    """La v1 pose ses pastilles aux cotes **sans exception**, et sa bande le montre.

    Deux proprietes en une: sa bande est identique pour tous les cardinaux (donc
    l'ajout du calcul de placement ne l'a pas rendue cardinal-dependante), et elle
    reste calculable **sans** cardinal -- ce que la v2 refuse explicitement, parce
    qu'une bande rendue sans cardinal y serait une bande devinee.
    """
    v1 = page_templates.GEOMETRY_V1
    for orientation in page_templates.ORIENTATIONS:
        reference = v1.frame_band_mm(orientation)
        for cardinal in page_templates.FRAMES_PER_PAGE_VOCABULARY[orientation]:
            assert v1.frame_band_mm(orientation, cardinal) == reference
        assert len(v1.frame_band_candidates(orientation)) == 1
        with pytest.raises(page_templates.UnknownTemplateError, match="cardinal"):
            page_templates.GEOMETRY_V2.frame_band_mm(orientation)


# ---------------------------------------------------------------------------
# AC 6 et 7: surface gagnee et orientation retenue, epinglees
# ---------------------------------------------------------------------------

#: Surface de dessin **re-mesuree sur la geometrie livree par la passe de design**, par
#: gabarit, en mm2. Les 9 gabarits de la v2, pas un echantillon.
#:
#: **Ces valeurs sont celles que `compose_lot_plan` rend, pas celles du banc** (AC 7 de
#: la story 5.18). Cinq des six cibles du banc tombent a l'identique -- 31 153 (1f
#: paysage), 38 088 (2f portrait), 29 757 (4f paysage), 36 856 (8f portrait) et le
#: 6f portrait de 27 642 mesure hors registre. Deux ecarts, tous deux expliques avant
#: d'etre epingles:
#:
#: * **4f paysage: 28 844 contre 29 757 (-3,1 %)**. Cause **unique**, et mesuree en la
#:   retirant: le pas de grille **vertical**. Le banc modelisait un pas unique de 3 mm; le
#:   pas vertical vaut 5 mm parce qu'il porte l'etiquette d'emplacement de la rangee du
#:   dessus (voir `PageGeometry.frame_grid_row_gap_mm`). A 3 mm, ce gabarit rend
#:   **exactement** la cible;
#: * **3f portrait: 27 047 contre 32 726 (-17,4 %)**. Trois causes cumulatives, chacune
#:   mesuree en la retirant -- 27 047 livre, 28 069 au pas vertical de 3 mm, 30 133 avec en
#:   plus un pied de 2 rangees, et les 2 593 mm2 qui restent sont le
#:   `bottom_extra_clearance_mm` de 9,5 mm que le modele du banc ignorait (`max(coin, pied)`
#:   au lieu de `max(coin + supplement, pied)`). Le pied reserve 6 rangees contre 2 dans le
#:   banc, lequel divisait un budget de 3 lignes **fixe** par le nombre de colonnes alors
#:   que le packing depend de la largeur de colonne. C'est le seul gabarit dont le bord bas
#:   n'est masque ni par l'emprise du QR ni par le pied, donc le seul ou ces trois termes
#:   se voient.
#: **`EPIC5-ARB-64`, 2026-08-12: le 6f paysage revient au registre**, le retrait du
#: cardinal 6 ne portant plus que sur le portrait. Sa surface est celle qui etait epinglee
#: hors registre (26 334,4 mm2) -- elle ne change pas, seul son statut change: elle etait
#: mesuree sur la geometrie faute de gabarit, elle est desormais confrontee aux zones que
#: `compose_lot_plan` compose, comme les neuf autres. Le registre v2 passe de 27 a 30
#: `template_id` (3 presets de marge x 1 gabarit).
_V2_AREAS_MM2 = {
    (PORTRAIT, 1): 19044.0, (PORTRAIT, 2): 38088.0, (PORTRAIT, 3): 27047.1,
    (PORTRAIT, 4): 19347.0, (PORTRAIT, 8): 36856.1,
    (PAYSAGE, 1): 31152.7, (PAYSAGE, 2): 20200.5, (PAYSAGE, 4): 28843.8,
    (PAYSAGE, 6): 26334.4, (PAYSAGE, 8): 19306.1,
}

#: Surface de dessin du cardinal **retire** du vocabulaire de la v2, mesuree sur la
#: geometrie et non sur un `template_id` -- il n'y en a plus. Elle est epinglee parce
#: que c'est elle qui **justifie** le retrait (AC 13): sans elle, le verdict
#: « 8f -> 6f ne progresse pas » reposerait sur un chiffre que plus rien ne regarde.
#:
#: **`EPIC5-ARB-64`: il n'en reste qu'un.** Le 6f paysage est revenu au registre, donc sa
#: surface est epinglee avec les autres dans `_V2_AREAS_MM2`. Ce qui reste hors registre
#: est le 6f **portrait**, celui dont le +0,0 % justifie le retrait.
_V2_RETIRED_AREAS_MM2 = {(PORTRAIT, 6): 27642.1}

#: Surface de dessin de la production (v1), meilleure orientation, par cardinal.
#: Les six valeurs de reference de la story, verifiees et inchangees.
_V1_BEST_AREAS_MM2 = {1: 13767, 2: 22050, 3: 12893, 4: 10816, 6: 14259, 8: 16806}

#: Gain mesure a la meilleure orientation, par cardinal et par nombre de colonnes de
#: temoins. **Ces chiffres remplacent ceux de l'AC 6 de la story**, mesures sur un banc
#: qui ne posait aucun texte: le pied de page reel exige 54,5 mm au bord bas la ou le
#: banc en modelisait 37,5 (portrait) et 30 (paysage), et le majorant d'emprise du QR
#: vaut 39,6 mm et non 38,3. Les deux ecarts retirent de la hauteur de bande, donc du
#: gain. Le detail de l'arithmetique est dans la story, section AC 6.
_V2_GAIN_PCT = {
    1: {1: 126.3, 2: 126.3},
    2: {1: 72.7, 2: 40.6},
    3: {1: 109.8, 2: 109.8},
    4: {1: 166.7, 2: 166.7},
    8: {1: 119.3, 2: 77.9},
}

#: Orientation qui maximise la surface, par cardinal. **La meme sous les deux
#: geometries**: ni le resserrement de 5.15 ni la passe de design de 5.18 ne l'inversent,
#: alors que la passe deplace le bord porteur du QR et change les deux pas de grille.
_BEST_ORIENTATION_BY_CARDINAL = {
    1: PAYSAGE, 2: PORTRAIT, 3: PORTRAIT, 4: PAYSAGE, 6: PORTRAIT, 8: PORTRAIT,
}


@pytest.mark.parametrize("orientation,cardinal", GABARITS_V2)
def test_the_v2_drawing_area_is_pinned_gabarit_by_gabarit(orientation, cardinal) -> None:
    area = _drawing_area(page_templates.GEOMETRY_V2, orientation, cardinal)
    assert area == pytest.approx(_V2_AREAS_MM2[(orientation, cardinal)], abs=0.1)
    # Et elle est strictement superieure a celle de la v1: c'est l'objet de la story.
    assert area > _drawing_area(page_templates.GEOMETRY_V1, orientation, cardinal)
    # **La surface epinglee est celle que la PRODUCTION compose**, pas celle qu'un
    # modele calcule: elle est confrontee a la somme des zones du gabarit du registre.
    # Sans cette confrontation, les valeurs ci-dessus mesureraient `frame_band_mm` et
    # `_grid_shape` -- soit exactement les deux fonctions dont on veut savoir si elles
    # sont bien celles que `compose_lot_plan` emprunte.
    spec = page_templates.template_for(orientation, cardinal, "0", "v2")
    composed = sum(zone["width"] * zone["height"] for zone in spec.frame_zones_mm)
    assert composed == pytest.approx(area, abs=1e-6)


@pytest.mark.parametrize("orientation,cardinal", sorted(_V2_RETIRED_AREAS_MM2))
def test_the_retired_cardinal_area_is_pinned_on_the_geometry(orientation, cardinal):
    """La surface du cardinal retire, epinglee **hors registre** (AC 7 et 13).

    Elle n'a plus de `template_id`, donc elle ne se mesure plus par un gabarit -- mais
    c'est elle qui justifie le retrait, et un chiffre que plus rien ne regarde est un
    chiffre qui devient faux. Le test la mesure la ou elle existe encore: sur la
    geometrie, par la meme bande et la meme partition que la production.
    """
    geometry = page_templates.GEOMETRY_V2
    area = _drawing_area(geometry, orientation, cardinal)
    assert area == pytest.approx(_V2_RETIRED_AREAS_MM2[(orientation, cardinal)], abs=0.1)
    # Et le `template_id` correspondant, lui, est bien refuse.
    with pytest.raises(page_templates.UnknownTemplateError, match="retire"):
        page_templates.build_template_id(orientation, cardinal, "0", "v2")


@pytest.mark.parametrize("columns", [1, 2])
@pytest.mark.parametrize("cardinal", sorted(_V2_GAIN_PCT))
def test_the_surface_gain_is_pinned_per_cardinal_and_column_count(
        cardinal, columns) -> None:
    """Les deux tableaux de l'AC 6, epingles: 5.16 choisira la ligne.

    Le nombre de colonnes de temoins n'est pas libre -- il est impose par le jeu de
    pastilles retenu (28 pastilles -> 1 colonne, `EPIC5-ARB-57`). La story epingle les
    deux pour que le choix de 5.16 n'ait pas a re-mesurer.
    """
    import types

    geometry = page_templates.GEOMETRY_V2
    if columns != 1:
        geometry = dataclasses.replace(
            geometry,
            patch_columns_per_side=types.MappingProxyType(
                {PORTRAIT: columns, PAYSAGE: columns}),
        )
    reference = max(
        _drawing_area(page_templates.GEOMETRY_V1, orientation, cardinal)
        for orientation in page_templates.ORIENTATIONS
        if cardinal in page_templates.FRAMES_PER_PAGE_VOCABULARY[orientation]
    )
    assert reference == pytest.approx(_V1_BEST_AREAS_MM2[cardinal], abs=1.0)
    best = max(
        _drawing_area(geometry, orientation, cardinal)
        for orientation in page_templates.ORIENTATIONS
        if cardinal in page_templates.FRAMES_PER_PAGE_VOCABULARY[orientation]
    )
    gain = (best - reference) / reference * 100.0
    assert gain == pytest.approx(_V2_GAIN_PCT[cardinal][columns], abs=0.2), (
        cardinal, columns, gain)
    # Le gain reste franchement positif sur les six cardinaux: c'est la promesse.
    assert gain > 30.0


@pytest.mark.parametrize("cardinal", sorted(_BEST_ORIENTATION_BY_CARDINAL))
def test_the_best_orientation_per_cardinal_is_the_same_under_both_geometries(
        cardinal) -> None:
    """L'orientation retenue ne change pas (AC 7).

    Sans ce test, un futur ajustement de constituant pourrait retourner un cardinal en
    silence et changer le gabarit livre -- une planche paysage la ou l'operateur en
    attend une portrait, pour un gain de quelques mm2.
    """
    expected = _BEST_ORIENTATION_BY_CARDINAL[cardinal]
    for version in ("v1", "v2"):
        geometry = page_templates.get_geometry(version)
        areas = {
            orientation: _drawing_area(geometry, orientation, cardinal)
            for orientation in page_templates.ORIENTATIONS
            if cardinal in page_templates.FRAMES_PER_PAGE_VOCABULARY[orientation]
        }
        winner = max(areas, key=areas.get)
        assert winner == expected, (version, cardinal, areas)
        if len(areas) > 1:
            # L'ecart doit etre franc: une egalite a 1 mm2 rendrait le verdict
            # dependant du dernier chiffre binaire.
            ordered = sorted(areas.values(), reverse=True)
            assert ordered[0] - ordered[1] > 1.0, (version, cardinal, areas)


# ---------------------------------------------------------------------------
# AC 8: aucun element ne sort de la limite d'encre, sur les 11 gabarits v2
# ---------------------------------------------------------------------------


def _images_pages(plan):
    """Les **planches d'images** d'un plan de lot, sans sa page de calibration.

    Depuis la story 5.16 (`EPIC5-ARB-54`), `plan.pages` porte toutes les pages imprimees
    et la premiere est la page de calibration du lot quand la geometrie peut la porter.
    Les tests de ce fichier parlent de la mise en page des **planches** -- pied de page,
    entete d'identite a 14 pt, pied technique sur deux colonnes -- et la page de
    calibration n'en porte aucun: son entete tient dans une rangee de grille et elle n'a
    pas de pied. Ce ne sont pas des lacunes, c'est son role (voir
    `pdf_composition.NO_DATE_LINE_SLOT`).
    """
    return [page for page in plan.pages if page.frames]


def _constituent_rects(spec, preset_id):
    """Emprises de tous les constituants d'un gabarit, calculees depuis sa geometrie.

    Complementaire du test de plan de page de `test_pdf_composition`, qui part d'un lot
    reellement compose: ici aucune donnee de lot n'intervient, donc les 11 gabarits x
    3 presets sont couverts sans qu'un manifest doive exister -- et l'emprise du QR est
    celle **reservee** (le majorant), pas celle d'un payload particulier.
    """
    geometry = spec.geometry
    rects = [(zone["name"], (zone["x"], zone["y"], zone["width"], zone["height"]))
             for zone in spec.frame_zones_mm]
    for marker_id, (cx, cy) in page_templates.corner_marker_centers_mm(spec).items():
        half = geometry.marker_size_mm / 2
        rects.append((f"marker-{marker_id}", (cx - half, cy - half,
                                              geometry.marker_size_mm,
                                              geometry.marker_size_mm)))
    # L'emprise du QR est celle **reservee**, posee la ou le gabarit met son QR: la
    # recette est celle de la production, jamais un centrage recopie ici. C'est le
    # cas que le test global ne couvrait pas avant la story 5.18 -- le QR sur un flanc,
    # a cote de la colonne de pastilles, et le QR au bord bas, a cote du pied de page.
    qr_x, band_y, footprint, _band_h = page_templates.qr_reserved_zone_mm(spec)
    rects.append(("qr", (qr_x, band_y, footprint, footprint)))
    for index, patch in enumerate(patch_presets.resolve_patch_layout(
            spec.template_id, preset_id)):
        rects.append((f"patch-{index}", (patch.x_mm, patch.y_mm,
                                         patch.size_mm, patch.size_mm)))
    for name, rect in page_templates.footer_zones_mm(spec).items():
        rects.append((name, rect))
    # Les zones d'en-tete comptent comme les autres: l'entete d'identite est un texte
    # imprime, et c'est precisement le constituant que la story 5.18 ajoute a la page.
    for name, rect in pdf_composition._header_zones_mm(
            spec, (qr_x, band_y, footprint, footprint)).items():
        rects.append((name, rect))
    return rects


@pytest.mark.parametrize("preset_id", sorted(patch_presets.known_preset_ids()))
@pytest.mark.parametrize("orientation,cardinal", GABARITS_V2)
def test_no_v2_constituent_leaves_the_printable_rectangle(
        orientation, cardinal, preset_id) -> None:
    """AC 8, sur les 11 gabarits et les trois presets -- pas un echantillon.

    Sous la v2 le bord exterieur d'un marqueur est a 8 mm du bord physique, soit 3 mm
    sous `PRINTER_MARGIN_MM`. Le tirage reel du 2026-08-11 dit que ces 8 mm nominaux
    atterrissent a 6,9 mm (derive d'echelle de +1,07 %) et que l'encre sort jusqu'a
    2,0 mm: la marge tient avec un facteur superieur a trois.
    """
    if ("v2", orientation, preset_id) in patch_presets._PLACEMENT_UNPLACEABLE:
        pytest.skip("couple sans placement, refuse et verifie ailleurs")
    spec = page_templates.template_for(orientation, cardinal, "0", "v2")
    margin = spec.geometry.printer_margin_mm
    for name, (x, y, width, height) in _constituent_rects(spec, preset_id):
        assert x >= margin - 1e-9, (name, x)
        assert y >= margin - 1e-9, (name, y)
        assert x + width <= spec.page_width_mm - margin + 1e-9, (name, x + width)
        assert y + height <= spec.page_height_mm - margin + 1e-9, (name, y + height)
    # Et la marge est reellement mordue par les marqueurs: si aucun constituant
    # n'approchait la limite, le test ne mesurerait rien.
    closest = min(
        min(x, y, spec.page_width_mm - x - width, spec.page_height_mm - y - height)
        for _name, (x, y, width, height) in _constituent_rects(spec, preset_id)
    )
    assert margin - 1e-9 <= closest <= margin + 3.1, closest


@pytest.mark.parametrize("preset_id", sorted(patch_presets.known_preset_ids()))
@pytest.mark.parametrize("orientation,cardinal", GABARITS_V2)
def test_no_two_v2_constituents_overlap(orientation, cardinal, preset_id) -> None:
    """AC 9, cote geometrie pure (le pendant sur plan compose vit dans 4.1).

    Motif: en fabriquant la feuille de test des bords, deux reperes de limite d'encre
    sont tombes dans l'emprise de trois pastilles temoins -- invisible au rendu reduit,
    et un element recouvert rend un verdict sur autre chose que lui-meme.
    """
    if ("v2", orientation, preset_id) in patch_presets._PLACEMENT_UNPLACEABLE:
        pytest.skip("couple sans placement, refuse et verifie ailleurs")
    spec = page_templates.template_for(orientation, cardinal, "0", "v2")
    rects = _constituent_rects(spec, preset_id)
    for index, (name, rect) in enumerate(rects):
        for other_name, other in rects[index + 1:]:
            assert not rects_overlap(rect, other), (
                spec.template_id, preset_id, name, other_name, rect, other)


@pytest.mark.parametrize("orientation,cardinal", GABARITS_V2)
def test_the_v2_marker_quiet_zones_stay_free_of_every_other_constituent(
        orientation, cardinal) -> None:
    """Le silence des marqueurs est du blanc, et il n'est pas negociable.

    Verifie separement de l'emprise: le silence peut sortir de la limite d'encre (il
    n'y a pas d'encre) mais rien d'autre ne peut y entrer, sans quoi la detection des
    coins tombe -- c'est le mecanisme du seul echec de detection du tirage du
    2026-08-11, un trait de 0,3 mm non declare traversant une sonde.
    """
    spec = page_templates.template_for(orientation, cardinal, "0", "v2")
    geometry = spec.geometry
    quiet_rects = []
    for cx, cy in page_templates.corner_marker_centers_mm(spec).values():
        half = geometry.marker_size_mm / 2 + geometry.marker_quiet_zone_mm
        quiet_rects.append((cx - half, cy - half, 2 * half, 2 * half))
    for name, rect in _constituent_rects(spec, "patches-12-v1"):
        if name.startswith("marker-"):
            continue
        for quiet in quiet_rects:
            assert not rects_overlap(rect, quiet), (spec.template_id, name, rect, quiet)


# ---------------------------------------------------------------------------
# AC 10: le chemin de scan lit la geometrie du template_id, sans exception
# ---------------------------------------------------------------------------

_SCAN_DPI = 300


def _synthesize_page(spec, preset_id: str, dpi: int = _SCAN_DPI):
    """Rendre un raster de page depuis la geometrie: marqueurs et pastilles.

    Assez pour le chemin de detection (les quatre coins) et pour l'echantillonnage
    (les pastilles, chacune posee a sa **vraie** position et remplie de son gris).
    Les pastilles portent des gris **distincts** -- la regle des fabriques du depot:
    un remplissage uniforme rendrait invisible toute erreur d'appariement, et c'est
    exactement l'erreur qu'un croisement de geometries produit.
    """
    import cv2
    import numpy as np

    from mixed_media_utility import layout

    width_px, height_px = page_templates.mm_to_px(
        spec.page_width_mm, spec.page_height_mm, dpi)
    canvas = np.full((height_px, width_px), 255, dtype=np.uint8)
    for marker_id, (cx, cy) in page_templates.corner_marker_centers_mm(spec).items():
        half = spec.geometry.marker_size_mm / 2
        x0, y0 = page_templates.mm_to_px(cx - half, cy - half, dpi)
        side_px = page_templates.mm_to_px(
            spec.geometry.marker_size_mm, spec.geometry.marker_size_mm, dpi)[0]
        canvas[y0:y0 + side_px, x0:x0 + side_px] = layout.generate_aruco_marker_image(
            marker_id, side_px)
    expected = []
    for patch in patch_presets.resolve_patch_layout(spec.template_id, preset_id):
        x0, y0 = page_templates.mm_to_px(patch.x_mm, patch.y_mm, dpi)
        x1, y1 = page_templates.mm_to_px(
            patch.x_mm + patch.size_mm, patch.y_mm + patch.size_mm, dpi)
        gray = int(round(sum(patch.rgb) / 3))
        canvas[y0:y1, x0:x1] = gray
        expected.append((patch, gray))
    assert len({gray for _patch, gray in expected}) >= 2, (
        "fabrique degeneree: des pastilles indistinguables rendraient invisible "
        "toute erreur d'appariement")
    del cv2  # importe pour verifier la disponibilite du redressement
    return canvas, expected


def _sample_patch_centres(canvas, homography, spec, expected, dpi: int = _SCAN_DPI):
    """Redresser la page et lire le centre de chaque pastille attendue."""
    import cv2
    import numpy as np

    size_px = page_templates.page_size_px(spec, dpi)
    warped = cv2.warpPerspective(canvas, homography, size_px)
    read = []
    for patch, gray in expected:
        cx = patch.x_mm + patch.size_mm / 2
        cy = patch.y_mm + patch.size_mm / 2
        px, py = page_templates.mm_to_px(cx, cy, dpi)
        read.append((gray, int(np.median(warped[py - 2:py + 3, px - 2:px + 3]))))
    return read


@pytest.mark.parametrize("geometry_version", ["v1", "v2"])
def test_the_scan_path_reads_the_geometry_of_the_template_id(geometry_version) -> None:
    """Bout en bout: une planche composee dans une version se relit dans la sienne.

    `resolve_page_geometry` ne prend **que** le `template_id`: la propriete a verifier
    est donc qu'il en resolve la geometrie complete, marqueurs de coin compris, et que
    l'homographie qui en decoule pose les pastilles au bon endroit.
    """
    from mixed_media_utility import scan_detection
    from mixed_media_utility.detection import aruco as aruco_detection
    import numpy as np

    spec = page_templates.template_for(PORTRAIT, 2, "0", geometry_version)
    canvas, expected = _synthesize_page(spec, "patches-12-v1")
    geometry = scan_detection.resolve_page_geometry(spec.template_id, _SCAN_DPI)
    assert geometry["spec"].geometry_version == geometry_version
    assert geometry["corner_centers_mm"] == page_templates.corner_marker_centers_mm(spec)
    _corners, ids = aruco_detection.detect_markers(canvas, dpi=_SCAN_DPI)
    detected = {int(v) for v in np.array(ids).ravel()} if ids is not None else set()
    assert set(range(4)) <= detected, detected
    markers = _detected_markers(canvas)
    homography, scale = scan_detection.compute_template_homography(
        markers, geometry, _SCAN_DPI)
    # Echelle de 1: la page synthetique est a l'echelle de sa propre geometrie.
    assert scale.scale_error < scan_detection.SCALE_WARNING_TOLERANCE
    assert scan_detection._scale_warnings(scale) == []
    for wanted, read in _sample_patch_centres(canvas, homography, spec, expected):
        assert abs(read - wanted) <= 2, (wanted, read)


def _detected_markers(canvas, dpi: int = _SCAN_DPI):
    """Marqueurs au format attendu par `compute_template_homography`."""
    import numpy as np

    from mixed_media_utility.detection import aruco as aruco_detection

    corners, ids = aruco_detection.detect_markers(canvas, dpi=dpi)
    markers = []
    for quad, marker_id in zip(corners, np.array(ids).ravel()):
        points = np.asarray(quad).reshape(-1, 2)
        markers.append({"id": int(marker_id),
                        "center": (float(points[:, 0].mean()),
                                   float(points[:, 1].mean()))})
    return markers


def test_a_v1_sheet_read_with_the_v2_geometry_fails_loudly() -> None:
    """**Le defaut reel du 2026-08-11, transpose au chemin de production.**

    `--template` etait une constante de module dans deux bancs, donc une planche
    pouvait etre lue avec la geometrie d'une autre. Ce cas ne doit **jamais** rendre des
    chiffres plausibles sur les mauvaises pastilles: la mesure d'echelle de la page
    l'attrape, parce que la distance entre centres de coin differe de 16 % entre les
    deux versions (150 mm en v1, 179 mm en v2).

    Ce que le test epingle, et la reserve qui va avec: le signal existe et il est
    **nomme** (`PAGE_SCALE_OUT_OF_TOLERANCE`, 8 fois la tolerance), mais il reste un
    avertissement et non un refus. Le porter au refus demande un seuil, donc une
    mesure et un arbitrage produit: verse au `deferred-work.md` plutot que tranche ici.
    """
    from mixed_media_utility import scan_detection

    printed = page_templates.template_for(PORTRAIT, 2, "0", "v1")
    canvas, expected = _synthesize_page(printed, "patches-12-v1")
    markers = _detected_markers(canvas)

    wrong = scan_detection.resolve_page_geometry("tpl-a4-portrait-2f-v2", _SCAN_DPI)
    homography, scale = scan_detection.compute_template_homography(
        markers, wrong, _SCAN_DPI)
    # (1) Le signal, nomme et hors de toute nuance de mesure.
    assert scale.scale_error > 8 * scan_detection.SCALE_WARNING_TOLERANCE, scale
    assert "PAGE_SCALE_OUT_OF_TOLERANCE" in scan_detection._scale_warnings(scale)
    # (2) Et surtout: les chiffres qui sortiraient ne sont pas plausibles. Les
    # pastilles de la v2 sont lues ailleurs que la ou la v1 les a imprimees, donc au
    # moins l'une des valeurs lues s'ecarte franchement de la valeur attendue.
    wrong_spec = wrong["spec"]
    read = _sample_patch_centres(
        canvas, homography, wrong_spec,
        [(patch, gray) for patch, gray in zip(
            patch_presets.resolve_patch_layout(wrong_spec.template_id, "patches-12-v1"),
            [gray for _patch, gray in expected])])
    assert any(abs(value - wanted) > 20 for wanted, value in read), read
    # (3) La bonne geometrie, elle, ne declenche rien: le signal discrimine.
    right = scan_detection.resolve_page_geometry(printed.template_id, _SCAN_DPI)
    _homography, right_scale = scan_detection.compute_template_homography(
        markers, right, _SCAN_DPI)
    assert scan_detection._scale_warnings(right_scale) == []


# ---------------------------------------------------------------------------
# AC 11: la bascule du defaut est **differee**, et le scenario agressif n'est
# pas enregistre
# ---------------------------------------------------------------------------


def test_the_default_geometry_version_is_v2_and_cites_what_the_switch_settles() -> None:
    """La valeur **et** les motifs qui la tiennent (AC 11 de 5.18).

    La passe de correction de 5.15 avait ramene le defaut a la v1 en nommant trois faits
    qui exigeaient d'attendre la passe de design. Cette story est cette passe, et elle
    bascule le defaut: le test exige donc que le commentaire de la constante reprenne
    **les trois** faits et dise ce qu'il en est de chacun -- deux sont leves, un est un
    risque assume, et lequel doit etre ecrit.

    Une constante de defaut qui bouge sans trace de sa cause est exactement ce qu'une
    session ulterieure ne saura pas re-justifier. Ce n'est pas de la cosmetique: c'est le
    seul lien entre la valeur livree et ce qui la justifie, et il n'existe nulle part
    ailleurs dans le code.
    """
    assert page_templates.DEFAULT_GEOMETRY_VERSION == "v2"
    assert page_templates.DEFAULT_GEOMETRY_VERSION == page_templates.GEOMETRY_V2.version
    source = (REPO_ROOT / "src" / "mixed_media_utility" / "page_templates.py").read_text(
        encoding="utf-8")
    head, _, tail = source.partition("DEFAULT_GEOMETRY_VERSION = ")
    assert tail, "la constante a change de forme"
    # **La citation est le bloc de commentaire contigu de la constante, pas une fenetre
    # de N caracteres** (passe de correction du 2026-08-12): la fenetre de 3 500
    # caracteres qui etait ecrite ici a fait tomber ce test au premier allongement du
    # commentaire, en poussant le premier fait hors du champ. La longueur du bloc n'est
    # pas la propriete testee -- son contenu l'est -- donc elle se derive.
    block = []
    for line in reversed(head.rstrip("\n").splitlines()):
        if not line.startswith("#:"):
            break
        block.append(line)
    citation = "\n".join(reversed(block))
    assert len(block) > 20, "le bloc de commentaire de la constante a disparu"
    for expected in (
            # (1) la regression mesuree: le couple reste refuse, mais il est enumere et
            # le drapeau qui le rend composable en v1 reste cable.
            "patches-18-v2", "--geometrie v1",
            # (2) l'arbitrage qui rouvrait les valeurs, et la fenetre qui se ferme.
            "EPIC5-ARB-61", "v3",
            # (3) le seuillage ArUco: **nomme comme risque assume**, avec la raison pour
            # laquelle il ne se tranche pas sur fixture de synthese.
            "MARKER_SIZE_MM", "30 mm", "15 mm", "risque assume",
            "fixture de synthese",
            # Et la mesure de tirage, qui n'est pas remise en cause.
            "Agressif_TEST_2026-08-11_174937",
            "analyse-2026-08-11-scan-des-bords",
            "5,0 mm", "2,0 mm", "4 sur 4"):
        assert expected in citation, expected
    # La reserve d'echantillonnage versee au `deferred-work.md` par 5.15 est nommee elle
    # aussi: l'AC 11 demande de dire **lequel des deux points** est assume et lequel doit
    # etre ferme avant, donc les deux doivent etre cites.
    assert "1,5 mm" in citation


def test_the_v1_geometry_stays_composable_after_the_default_switch() -> None:
    """La regression de 5.15 reste levee **apres** la bascule (AC 11).

    C'est le test de la regression que les trois couches de revue avaient trouvee: le
    couple `paysage x patches-18-v2` composait en v1 et echouait en v2. Il echoue
    toujours en v2 -- c'est une impossibilite geometrique enumeree, pas un defaut -- mais
    la bascule du defaut ne doit pas le rendre **inatteignable**: `--geometrie v1` le
    compose encore, et c'est la seule raison pour laquelle le drapeau existe.
    """
    manifest, lot_id = _composition_manifest()
    plan = pdf_composition.compose_lot_plan(
        manifest=manifest, lot_id=lot_id, orientation=PAYSAGE, frames_per_page=2,
        patch_preset="patches-18-v2", geometry_version="v1")
    assert plan.template_id.endswith("-v1")
    assert plan.patch_preset_id == "patches-18-v2"
    assert len(_images_pages(plan)[0].patches) == 36
    # Et sans le drapeau, le defaut etant la v2, le meme couple est refuse en nommant sa
    # cause -- jamais approxime.
    with pytest.raises(patch_presets.UndefinedPlacementError) as refus:
        pdf_composition.compose_lot_plan(
            manifest=manifest, lot_id=lot_id, orientation=PAYSAGE, frames_per_page=2,
            patch_preset="patches-18-v2")
    assert "patches-18-v2" in str(refus.value)
    # Le balayage complet, dans les deux sens: aucune combinaison composable en v2 ne
    # doit avoir cesse de l'etre en v1. La bascule **ajoute** un defaut, elle ne retire
    # aucun chemin.
    for orientation in page_templates.ORIENTATIONS:
        for preset_id in patch_presets.known_preset_ids():
            composable = {}
            for version in ("v1", "v2"):
                cardinals = page_templates.frames_per_page_vocabulary(
                    orientation, version)
                try:
                    pdf_composition.compose_lot_plan(
                        manifest=manifest, lot_id=lot_id, orientation=orientation,
                        frames_per_page=cardinals[0], patch_preset=preset_id,
                        geometry_version=version)
                    composable[version] = True
                except pdf_composition.CompositionError:
                    composable[version] = False
                except patch_presets.UndefinedPlacementError:
                    composable[version] = False
            if composable["v2"]:
                assert composable["v1"], (orientation, preset_id)


@pytest.mark.parametrize("field,aggressive", [
    ("marker_size_mm", 10.0),
    ("marker_margin_mm", 5.0),
    ("marker_quiet_zone_mm", 3.0),
])
def test_no_registered_geometry_carries_the_aggressive_scenario(field, aggressive) -> None:
    """AC de frontiere **negatif**: le scenario agressif n'est pas enregistre.

    Mesure du tirage: sous l'agressif le bord exterieur d'un marqueur de coin, a
    5,0 mm nominal, atterrit a 3,9 mm reels (derive d'echelle de +1,07 %) et son
    silence nominal de 3 mm tombe a 1,9 mm effectif. Ce n'est pas une marge, c'est une
    tolerance de fabrication -- et la feuille de bords ne l'a pas eprouve. Il ne doit
    donc **pas** etre ajoute au registre au motif que la v2 a reussi.

    Le test porte sur les trois dimensions separement plutot que sur le triplet: une
    version qui n'en reprendrait qu'une seule serait deja hors du domaine mesure.
    """
    for version, geometry in page_templates.GEOMETRY_VERSIONS.items():
        assert getattr(geometry, field) != aggressive, (version, field)
    # Et le degagement de coin de l'agressif (18 mm) n'est atteint par aucune version.
    for version, geometry in page_templates.GEOMETRY_VERSIONS.items():
        assert geometry.corner_clearance_mm() > 18.0, version


def test_the_registry_carries_exactly_the_two_arbitrated_versions() -> None:
    """Deux versions, nommees. Une troisieme n'arrive pas par effet de bord.

    `patch_presets` enumere localement les versions qu'il place: une version ajoutee au
    registre de gabarits sans y etre ajoutee ici resoudrait des `template_id` que la
    resolution de pastilles refuserait -- bruyamment, ce qui est le comportement voulu,
    mais le present test le dit avant qu'une planche soit imprimee.
    """
    assert set(page_templates.GEOMETRY_VERSIONS) == {"v1", "v2"}
    assert set(patch_presets._PLACEMENT_COVERED_GEOMETRY_VERSIONS) == set(
        page_templates.GEOMETRY_VERSIONS)


# ---------------------------------------------------------------------------
# AC 12: additivite MESUREE, pas declaree
# ---------------------------------------------------------------------------

_BASELINE_DOCUMENT = (
    REPO_ROOT / "tests" / "fixtures" / "additivite-5-15" / "lot-v1-au-baseline.json"
)


def _v1_lot_document() -> str:
    """Tout ce qu'un lot v1 produit, sous forme comparable octet a octet.

    Manifest fusionne, charges utiles QR **serialisees**, zones de frames, pastilles,
    zones et blocs de texte, marqueurs. Le document est volontairement large: la story
    5.9 s'etait declaree « purement additive » et son AC 12 avait mesure ce que la
    phrase coutait vraiment, sur un perimetre plus etroit que celui-la.
    """
    import json

    from mixed_media_utility.io import naming, pdf_manifest

    lot_id = naming.build_lot_id("rush-001", 5.0)
    existing = {
        "schema_version": "2.1",
        "project_id": "proj-additivite",
        "created": "2026-08-11T00:00:00Z",
        "rushes": [{
            "rush_id": "rush-001", "source_name": "rush-001.mov",
            "fps_source": 25.0, "fps_source_exact": "25/1",
            "resolution_source": {"width": 1920, "height": 1080},
        }],
        "lots": [{
            "lot_id": lot_id, "rush_id": "rush-001", "state": "extraction",
            "fps_target": 5.0, "fps_target_exact": "5/1",
            # Story 2.7 (payload 2.1): requis par `_lot_identity` pour composer.
            "timecode_base_fps": "25/1",
            "expected_frame_count": 10,
            "frames_dir": f"frames/{naming.derive_short_id('rush-001')}_"
                          f"{naming.format_fps_short(5.0)}",
            "source_frame_count": 50, "source_frame_count_is_exact": True,
            "rounding_policy": "floor",
        }],
        "artifacts": {"frames_dir": "frames"},
        "color": {"target_colorspace": "rec709"},
        "video": {}, "reconstruction": {},
    }
    # Le preset est **demande explicitement** depuis `EPIC5-ARB-67`, qui fait passer
    # `DEFAULT_PATCH_PRESET` a `patches-14-v3`. Sans cela ce document comparerait deux
    # choses a la fois -- la geometrie v1, que la story ne touche pas, et le jeu de
    # pastilles, qu'un arbitrage produit vient de changer volontairement -- et le
    # verdict d'additivite serait illisible. Le preset de l'instantane de reference est
    # celui qui etait alors le defaut; le fait que le defaut ait bouge est mesure ailleurs
    # (`test_makepdf_default_sheet_carries_the_witness_preset_and_its_sentinels`), sur le
    # producteur reel et dans les deux versions de geometrie.
    plan = pdf_composition.compose_lot_plan(
        manifest=existing, lot_id=lot_id, geometry_version="v1",
        patch_preset="patches-12-v1")
    merge = pdf_manifest.build_pdf_manifest(
        existing, pdf_manifest.PdfRecord.from_plan(plan))
    document = {
        "manifest": merge.manifest,
        "state_written": merge.state_written,
        "findings": list(merge.findings),
        "template_id": plan.template_id,
        "pdf_filename": plan.pdf_filename,
        "page_count": plan.page_count,
        "payloads": [page.qr.payload_text for page in plan.pages],
        "zones": [[slot.zone_rect_mm for slot in page.frames] for page in plan.pages],
        "patches": [
            [(p.value_id, p.x_mm, p.y_mm, p.size_mm, p.frame_mm) for p in page.patches]
            for page in plan.pages
        ],
        "text_zones": [
            {name: list(rect) for name, rect in sorted(page.text.zones_mm.items())}
            for page in plan.pages
        ],
        "blocks": [
            [(b.name, list(b.rect_mm), b.font_pt, list(b.lines))
             for b in page.text.blocks]
            for page in plan.pages
        ],
        "markers": [
            [(m.marker_id, m.center_x_mm, m.center_y_mm, m.size_mm)
             for m in page.markers]
            for page in plan.pages
        ],
    }
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=True)


def test_a_v1_lot_is_byte_for_byte_what_it_was_before_the_story() -> None:
    """**Additivite mesuree, pas declaree** (AC 12).

    Le document de reference a ete produit par le meme code, execute sur l'arbre du
    `baseline_commit` (4ae4eb2) via un `git worktree`, et non recopie a la main. C'est
    ce qui fait que ce test compare l'avant et l'apres et non l'apres a lui-meme.

    Pour le regenerer apres un changement **intentionnel** de la v1 -- ce qui devrait
    n'arriver jamais: sortir l'arbre du baseline, executer cette meme fonction dessus,
    et remplacer le fichier de reference. Si l'operation parait necessaire pour une
    story qui n'est pas censee toucher la v1, c'est le changement qu'il faut revoir,
    pas le fichier.

    **Reconciliation avec la story 5.17** (cles courtes du payload, `EPIC5-ARB-60`).
    Trois des dix rubriques de ce document changent, et **aucune des trois n'est un
    manifest**: le `manifest` fusionne, les zones de frames, les pastilles, les
    marqueurs, le `template_id`, le nom de fichier et la pagination restent identiques a
    l'octet. Ce qui bouge, et pourquoi:

    * `payloads` -- c'est l'objet de la story. L'ecart est mesure a part et **plus
      severement** qu'une egalite: il doit etre exactement le renommage par la table
      unique plus le passage de version, pas un champ, pas une valeur, pas un
      emplacement de plus ou de moins;
    * `text_zones` et `blocks` -- les deux colonnes d'en-tete de la bande haute
      **retrecissent de 0,43 mm chacune**, et la ligne technique du pied de page
      imprime `schema-payload=2.0`. La cause du retrecissement est contre-intuitive et
      c'est la lecon a garder: un payload **plus leger** encode sur **moins** de
      modules, et le silence ISO se comptant en modules, il pese relativement **plus**
      -- donc l'emprise imprimee du QR **grandit** a taille de symbole constante
      (35 mm, plafonnee par la cible de 4.6), et les deux colonnes qui l'encadrent
      perdent exactement ce qu'elle gagne.

    Cette derniere egalite est verifiee ici, en re-encodant l'ancienne charge utile pour
    en relire le nombre de modules: aucun des deux nombres n'est ecrit a la main.

    **Deux rubriques ont quitte cette liste depuis, et le paragraphe ci-dessus
    est donc a lire a sa date.** Le `manifest` fusionne bouge depuis la
    story 2.7, et le **nom de fichier** depuis `EPIC7-ARB-91` (2026-08-27) puis
    `EPIC11-ARB-171` (2026-09-02) : chacune porte sa declaration et sa mesure
    separee dans le corps du test, ci-dessous. Ce sont des changements de
    **nommage** et de **schema de manifest**, jamais de geometrie -- la v1
    dessinee sur le papier (zones de frames, pastilles, blocs de texte,
    marqueurs, pagination, `template_id`) reste comparee a l'octet, et c'est
    la promesse que ce test porte. Le fichier de reference n'a jamais ete
    regenere.
    """
    import json

    from mixed_media_utility.io import naming, payload as payload_io

    #: Les trois rubriques que la story 5.17 change, chacune verifiee separement plus
    #: bas. Le reste, `manifest` compris, est compare a l'octet -- sauf `manifest`
    #: lui-meme depuis la story 2.7, qui y ajoute un champ (voir plus bas).
    change_par_5_17 = ("payloads", "text_zones", "blocks")
    #: **Story 2.7** (`EPIC7-ARB-56`): `_lot_identity` exige desormais
    #: `lots[].timecode_base_fps` en entree de `compose_lot_plan`, donc le manifest
    #: **fusionne** (`merge.manifest`) le porte lui aussi -- `pdf_manifest` reporte les
    #: champs de lot non touches par la composition. La baseline gelee de 5.15 ne
    #: portait pas ce champ (il n'existait pas): la rubrique `manifest` rejoint donc
    #: les rubriques mouvantes, et l'ecart est verifie a part, exactement comme pour
    #: `payloads`.
    change_par_2_7 = ("manifest",)
    #: La rubrique `pdf_filename`, que **deux** arbitrages de nommage ont
    #: bougee depuis que la baseline a ete gelee. Elle rejoint les rubriques
    #: mouvantes, et son ecart est verifie a part -- **plus severement qu'une
    #: egalite** : ce doit etre exactement ces deux changements-la, defaits l'un
    #: apres l'autre, ni un caractere de plus ni un de moins.
    #:
    #: * **`EPIC7-ARB-91`** (2026-08-27) : le nom cesse de repeter le `rush_id`,
    #:   que le `lot_id` porte deja par construction
    #:   (`build_lot_id` = `<rush_id>_<cadence>`) ;
    #: * **`EPIC11-ARB-171`** (2026-09-02, retour A4 d'Egan) : la place du mot
    #:   `planches` porte desormais la **mise en page** (`<Nf-ori>`). Le mot ne
    #:   portait aucune information -- tout ce dossier est des planches -- alors
    #:   que deux mises en page du MEME lot rendaient le meme nom. La baseline
    #:   gelee porte donc `<projet>_rush-001_rush-001_5_planches.pdf` la ou la
    #:   production ecrit desormais `<projet>_rush-001_5_2f-por.pdf`.
    #:
    #: **La geometrie v1 n'est pas touchee, et c'est mesure ici meme** : le
    #: `template_id`, la pagination, les zones, les pastilles, les marqueurs et
    #: le manifest passent tous par `invariant` ci-dessous, donc sont compares a
    #: l'octet. Le nom de fichier est la SEULE rubrique que ces deux arbitrages
    #: deplacent, et c'est ce que la reconstruction en deux temps etablit.
    change_par_le_nommage_des_tirages = ("pdf_filename",)

    def invariant(text: str) -> str:
        """Le document prive des rubriques mouvantes, sous la meme forme exacte."""
        document = json.loads(text)
        for rubrique in (*change_par_5_17, *change_par_2_7,
                         *change_par_le_nommage_des_tirages):
            del document[rubrique]
        return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=True)

    expected_text = _BASELINE_DOCUMENT.read_text(encoding="utf-8")
    produced_text = _v1_lot_document()
    assert invariant(produced_text) == invariant(expected_text)

    expected = json.loads(expected_text)
    produced = json.loads(produced_text)
    # -- 0. le manifest fusionne: exactement l'ajout de `timecode_base_fps` ----
    expected_manifest_with_new_field = json.loads(json.dumps(expected["manifest"]))
    for lot in expected_manifest_with_new_field["lots"]:
        lot["timecode_base_fps"] = "25/1"
    assert produced["manifest"] == expected_manifest_with_new_field
    # Et c'est bien la **seule** difference: retirer le champ ajoute rend les deux
    # manifests identiques a l'octet.
    produced_manifest_without_new_field = json.loads(json.dumps(produced["manifest"]))
    for lot in produced_manifest_without_new_field["lots"]:
        del lot["timecode_base_fps"]
    assert produced_manifest_without_new_field == expected["manifest"]

    # -- 0 bis. le nom du PDF : exactement les DEUX changements declares ------
    # `EPIC7-ARB-91` puis `EPIC11-ARB-171`. On ne compare pas a une chaine
    # ecrite ici -- ce serait recopier la convention et le test ne dirait plus
    # rien d'elle. On RECONSTRUIT l'ancien nom depuis le nouveau, en defaisant
    # les deux changements l'un apres l'autre, et on exige l'egalite avec la
    # baseline gelee. Une convention qui changerait autre chose que ces deux
    # segments -- ou l'un des deux d'une autre facon -- echouerait ici.
    lot_du_document = produced["manifest"]["lots"][0]
    rush_du_lot = lot_du_document["rush_id"]
    projet = expected["pdf_filename"].split("_" + rush_du_lot, 1)[0]
    # (1) `EPIC11-ARB-171` : la mise en page reprend la place du mot `planches`.
    #     Ni le fragment ni le mot ne sont ecrits ici -- le premier est DERIVE
    #     du `template_id` du plan par la fonction meme qui le compose, le
    #     second est lu a la constante qui le porte (`naming.LEGACY_SHEETS_MARKER`,
    #     dans `io/naming.py`). Et le `template_id` d'ou sort le fragment est
    #     compare a l'octet par `invariant` ci-dessus : la mise en page de la
    #     geometrie v1 n'a donc pas bouge, seul son ECRITURE dans le nom a bouge.
    fragment_de_mise_en_page = naming.sheets_layout_fragment(produced["template_id"])
    sans_mise_en_page = produced["pdf_filename"].replace(
        f"_{fragment_de_mise_en_page}.pdf", f"_{naming.LEGACY_SHEETS_MARKER}.pdf", 1
    )
    assert sans_mise_en_page != produced["pdf_filename"], (
        "le nom produit ne porte pas le fragment de mise en page attendu "
        f"({fragment_de_mise_en_page!r}) : {produced['pdf_filename']!r}. Sans "
        "ce constat, la reconstruction ci-dessous serait un `replace` sans "
        "effet et le test comparerait autre chose que ce qu'il croit.")
    # (2) `EPIC7-ARB-91` : le segment `rush_id` redondant, reinsere.
    reconstruit = sans_mise_en_page.replace(
        f"{projet}_", f"{projet}_{rush_du_lot}_", 1
    )
    assert reconstruit == expected["pdf_filename"], (
        produced["pdf_filename"], expected["pdf_filename"]
    )
    # Et le nom **raccourcit** : un renommage neutre en octets ne serait pas
    # celui que les deux arbitrages demandent, et cette assertion le dirait.
    # `EPIC11-ARB-171` le dit nommement pour sa part (« le nom n'a pas grandi »).
    assert len(produced["pdf_filename"]) < len(expected["pdf_filename"])
    # Le rush reste LISIBLE du nom, une seule fois : c'est ce qui fait que le
    # contrat de reconstruction de la story 2.3 tient malgre le raccourcissement.
    assert produced["pdf_filename"].count(rush_du_lot) == 1
    # Et le mot `planches` a bien QUITTE le nom produit -- volet symetrique du
    # constat (1) : sans lui, un nom qui porterait les deux formes a la fois
    # passerait les assertions ci-dessus.
    assert naming.LEGACY_SHEETS_MARKER not in produced["pdf_filename"]

    # -- 1. les charges utiles: exactement le renommage ------------------------
    before, after = expected["payloads"], produced["payloads"]
    assert len(before) == len(after) >= 2, (len(before), len(after))
    for old_text, new_text in zip(before, after):
        old = json.loads(old_text)
        # **`"1.0"` reste un litteral ici, deliberement.** La fixture est une baseline
        # **gelee** (story 5.15): son `schema_version` historique n'a jamais ete relu
        # depuis la constante de production, qui a change de sens deux fois depuis
        # (5.17: cles courtes, "2.0"; 2.7, `EPIC7-ARB-56`: retrait de la branche de
        # lecture 1.0, plus aucune constante ne le nomme). Ce document d'epoque ne
        # bouge pas -- CLAUDE.md, regle des fixtures gelees -- et ce test le dit.
        assert old["schema_version"] == "1.0"
        old["schema_version"] = payload_io.PAYLOAD_SCHEMA_VERSION
        projected = {payload_io.PAYLOAD_SHORT_KEYS[key]: value
                     for key, value in old.items()}
        projected[payload_io.PAYLOAD_SHORT_KEYS["slots"]] = [
            {payload_io.PAYLOAD_SHORT_KEYS[key]: value for key, value in slot.items()}
            for slot in old["slots"]
        ]
        # **Reconciliation avec les stories 5.16 (role de page) et 2.7 (cadence
        # source, `EPIC7-ARB-56`): le contrat gagne deux champs scalaires depuis la
        # baseline gelee, chacun ajoute ici explicitement plutot que de relacher
        # l'egalite en inclusion -- c'est l'egalite exacte qui fait que ce test dirait
        # « un champ de plus est arrive », et un lot de planches d'images les porte
        # sur **toutes** ses pages, page 0 comprise: la page de calibration est
        # composee a part et n'entre pas dans ce document de reference.
        projected[payload_io.PAYLOAD_SHORT_KEYS["page_role"]] = payload_io.PAGE_ROLE_IMAGES
        projected[payload_io.PAYLOAD_SHORT_KEYS["timecode_base_fps"]] = "25/1"
        assert json.loads(new_text) == projected
        # Le renommage **allege**: un renommage neutre en octets ne serait pas celui
        # que la story livre, et cette assertion le dirait.
        assert len(new_text) < len(old_text), (len(new_text), len(old_text))

    # -- 2. l'emprise du QR grandit, et de combien ------------------------------
    modules_avant = int(qr_codes.encode_qr_image(before[0]).shape[0])
    modules_apres = int(qr_codes.encode_qr_image(after[0]).shape[0])
    assert modules_apres < modules_avant, (modules_avant, modules_apres)
    croissance = (page_templates.qr_footprint_mm(modules_apres)
                  - page_templates.qr_footprint_mm(modules_avant))
    assert croissance > 0, croissance

    # -- 3. les deux colonnes d'en-tete perdent exactement cela ----------------
    for index, (zones_avant, zones_apres) in enumerate(
        zip(expected["text_zones"], produced["text_zones"])
    ):
        bougees = {nom for nom in zones_avant if zones_avant[nom] != zones_apres[nom]}
        assert bougees == {"header_left", "header_right"}, (index, bougees)
        perdu = 0.0
        for nom in ("header_left", "header_right"):
            avant, apres = zones_avant[nom], zones_apres[nom]
            assert avant[1] == apres[1] and avant[3] == apres[3], (nom, avant, apres)
            perdu += avant[2] - apres[2]
        assert perdu == pytest.approx(croissance, abs=1e-9), (index, perdu, croissance)
        # Symetrie: la colonne droite recule d'exactement ce qu'elle perd en largeur.
        assert (zones_apres["header_right"][0] - zones_avant["header_right"][0]
                == pytest.approx(zones_avant["header_right"][2]
                                 - zones_apres["header_right"][2], abs=1e-9))

    # -- 4. les blocs de texte: memes rectangles que les zones, et une seule ligne
    #       de contenu changee, celle qui imprime la version du schema ----------
    for index, (blocs_avant, blocs_apres) in enumerate(
        zip(expected["blocks"], produced["blocks"])
    ):
        assert [bloc[0] for bloc in blocs_avant] == [bloc[0] for bloc in blocs_apres]
        for avant, apres in zip(blocs_avant, blocs_apres):
            nom, rect_avant, police_avant, lignes_avant = avant
            _, rect_apres, police_apres, lignes_apres = apres
            assert police_avant == police_apres, nom
            if nom not in ("header_left", "header_right"):
                assert rect_avant == rect_apres, (index, nom)
            differentes = [(a, b) for a, b in zip(lignes_avant, lignes_apres) if a != b]
            assert len(lignes_avant) == len(lignes_apres), (index, nom)
            for ancienne, nouvelle in differentes:
                # `"1.0"` litteral: meme motif que ci-dessus, la ligne technique de la
                # baseline gelee l'imprimait avant que la story 5.17 ne bouge la
                # constante -- ce document d'epoque ne bouge pas.
                assert ancienne.replace(
                    "schema-payload=1.0",
                    f"schema-payload={payload_io.PAYLOAD_SCHEMA_VERSION}",
                ) == nouvelle, (index, nom, ancienne, nouvelle)


def test_the_baseline_document_really_describes_a_v1_lot() -> None:
    """Garde contre un fichier de reference vide ou devenu decoratif.

    Un fichier de reference qui ne contiendrait plus la geometrie v1 ferait passer le
    test precedent tout en ne mesurant plus rien -- c'est la panne la plus probable
    d'une comparaison a un fichier.
    """
    import json

    document = json.loads(_BASELINE_DOCUMENT.read_text(encoding="utf-8"))
    assert document["template_id"] == "tpl-a4-portrait-2f-v1"
    assert document["page_count"] >= 2, "un lot d'une page ne teste pas la pagination"
    assert all("tpl-a4-portrait-2f-v1" in payload for payload in document["payloads"])
    # Les colonnes de pastilles de la v1, et sa taille de pastille.
    xs = {entry[1] for page in document["patches"] for entry in page}
    assert xs == {14.0, 184.0}
    assert {entry[3] for page in document["patches"] for entry in page} == {12.0}
    # Les zones de pied de page litterales de la v1.
    assert document["text_zones"][0]["footer_block"] == [60.0, 240.0, 90.0, 45.0]
    # Deux pages au moins, avec des charges utiles **distinctes**: un document dont
    # toutes les pages seraient identiques ne verrouillerait pas la pagination.
    assert len(set(document["payloads"])) == len(document["payloads"])


# ---------------------------------------------------------------------------
# Fermeture des survivants de la campagne de mutation `campagne_5_15.py`
#
# Six survivants a la premiere passe, dont deux equivalents demontres (voir le
# fichier de campagne). Les quatre reels avaient la meme cause: la variante
# « rangees haut/bas » n'etant retenue par aucun gabarit livre, **rien ne la
# regardait** -- ni sa bande, ni son encombrement, ni le fait que le registre porte
# le placement reellement retenu. Un survivant de cette famille est exactement le
# defaut que la regle des fabriques du depot decrit: un seul cas observe rend
# invisible toute erreur de selection.
# ---------------------------------------------------------------------------

#: Les **huit** bandes candidates de chaque gabarit v2, en dur: quatre bords porteurs du
#: QR x deux placements de temoins. Celles qui ne sont pas retenues sont epinglees elles
#: aussi -- sans elles, ni le cardinal de temoins de bord, ni l'arrondi du nombre de
#: rangees, ni le cout d'un bord non retenu n'ont d'effet observable (mutants `A07` et
#: `F01` de la campagne 5.15, et toute la famille du bord porteur pour 5.18).
_V2_CANDIDATE_BANDS = {
    (PORTRAIT, page_templates.QR_EDGE_BOTTOM): {
        page_templates.WITNESS_PLACEMENT_SIDES:
            {"x": 13.0, "y": 28.0, "width": 184.0, "height": 219.376},
        page_templates.WITNESS_PLACEMENT_BORDERS:
            {"x": 28.0, "y": 36.0, "width": 154.0, "height": 203.376},
    },
    (PORTRAIT, page_templates.QR_EDGE_TOP): {
        page_templates.WITNESS_PLACEMENT_SIDES:
            {"x": 13.0, "y": 49.624, "width": 184.0, "height": 202.016},
        page_templates.WITNESS_PLACEMENT_BORDERS:
            {"x": 28.0, "y": 57.624, "width": 154.0, "height": 186.016},
    },
    # Portrait: le QR de flanc se **colle** a la marge d'encre, sous la colonne de
    # pastilles (79 mm de hauteur libre), donc le flanc coute 49,62 mm et non 57,62.
    (PORTRAIT, page_templates.QR_EDGE_LEFT): {
        page_templates.WITNESS_PLACEMENT_SIDES:
            {"x": 49.624, "y": 28.0, "width": 147.376, "height": 223.64},
        page_templates.WITNESS_PLACEMENT_BORDERS:
            {"x": 49.624, "y": 36.0, "width": 132.376, "height": 207.64},
    },
    (PORTRAIT, page_templates.QR_EDGE_RIGHT): {
        page_templates.WITNESS_PLACEMENT_SIDES:
            {"x": 13.0, "y": 28.0, "width": 147.376, "height": 223.64},
        page_templates.WITNESS_PLACEMENT_BORDERS:
            {"x": 28.0, "y": 36.0, "width": 132.376, "height": 207.64},
    },
    (PAYSAGE, page_templates.QR_EDGE_BOTTOM): {
        page_templates.WITNESS_PLACEMENT_SIDES:
            {"x": 13.0, "y": 28.0, "width": 271.0, "height": 132.376},
        page_templates.WITNESS_PLACEMENT_BORDERS:
            {"x": 28.0, "y": 36.0, "width": 241.0, "height": 116.376},
    },
    (PAYSAGE, page_templates.QR_EDGE_TOP): {
        page_templates.WITNESS_PLACEMENT_SIDES:
            {"x": 13.0, "y": 49.624, "width": 271.0, "height": 115.016},
        page_templates.WITNESS_PLACEMENT_BORDERS:
            {"x": 28.0, "y": 57.624, "width": 241.0, "height": 99.016},
    },
    (PAYSAGE, page_templates.QR_EDGE_LEFT): {
        page_templates.WITNESS_PLACEMENT_SIDES:
            {"x": 57.624, "y": 28.0, "width": 226.376, "height": 136.64},
        page_templates.WITNESS_PLACEMENT_BORDERS:
            {"x": 57.624, "y": 36.0, "width": 211.376, "height": 120.64},
    },
    (PAYSAGE, page_templates.QR_EDGE_RIGHT): {
        page_templates.WITNESS_PLACEMENT_SIDES:
            {"x": 13.0, "y": 28.0, "width": 226.376, "height": 136.64},
        page_templates.WITNESS_PLACEMENT_BORDERS:
            {"x": 28.0, "y": 36.0, "width": 211.376, "height": 120.64},
    },
}


@pytest.mark.parametrize("qr_edge", list(page_templates.QR_EDGES))
@pytest.mark.parametrize("orientation", list(page_templates.ORIENTATIONS))
def test_both_v2_candidate_bands_are_pinned(orientation, qr_edge) -> None:
    """Les huit candidats, pas seulement le retenu.

    L'encombrement de la variante haut/bas est `une rangee de 6 mm + 2 mm d'ecart a la
    bande` -- soit 8 mm par bord, en haut **et** en bas, pour les 14 temoins de chaque
    bord (28 au total, `EPIC5-ARB-57`). Le pinner rend observable ce que le candidat
    retenu masque: le cardinal de temoins, l'arrondi du nombre de rangees, la largeur
    rendue par l'ouverture au silence des marqueurs, et **le cout de chacun des quatre
    bords**.
    """
    candidates = dict(page_templates.GEOMETRY_V2.frame_band_candidates(
        orientation, qr_edge))
    expected_bands = _V2_CANDIDATE_BANDS[(orientation, qr_edge)]
    assert set(candidates) == set(expected_bands)
    for placement, expected in expected_bands.items():
        for key, value in expected.items():
            assert candidates[placement][key] == pytest.approx(value, abs=1e-3), (
                placement, key)
    # Une rangee suffit pour 14 temoins par bord: la variante coute 8 mm par bord en
    # portrait (6 de pastille + 2 d'ecart a la bande) et non 17 (deux rangees).
    sides = candidates[page_templates.WITNESS_PLACEMENT_SIDES]
    borders = candidates[page_templates.WITNESS_PLACEMENT_BORDERS]
    strip = borders["y"] - sides["y"]
    gap = page_templates.GEOMETRY_V2.patch_to_band_gap_mm[orientation]
    assert strip == pytest.approx(page_templates.GEOMETRY_V2.patch_size_mm + gap)


#: (orientation, temoins au total) -> rangees attendues par bord. Les emplacements par
#: rangee valent 17 en portrait (154 mm de bande utile) et 27 en paysage (241 mm), au
#: pas de 9 mm avec un ecart de 3 mm en fin de rangee -- c'est cet ecart final qui fait
#: la difference entre 26 et 27 en paysage, et le cas `108` est choisi pour qu'il
#: **change le nombre de rangees**: 54 temoins par bord tiennent en 2 rangees de 27 et
#: en 3 rangees de 26.
_BORDER_ROWS = {
    (PORTRAIT, 2): 1, (PORTRAIT, 28): 1, (PORTRAIT, 60): 2, (PORTRAIT, 120): 4,
    (PAYSAGE, 28): 1, (PAYSAGE, 108): 2, (PAYSAGE, 110): 3,
}


@pytest.mark.parametrize("orientation", list(page_templates.ORIENTATIONS))
def test_the_border_variant_row_capacity_counts_the_end_gap(orientation) -> None:
    """La capacite d'une rangee compte l'ecart de fin, et ca change le compte.

    `per_row = (largeur + ecart) // (pastille + ecart)`: la derniere pastille d'une
    rangee n'est suivie d'aucun ecart, donc l'oublier **sous-estime** la capacite --
    26 au lieu de 27 en paysage. Le cas est choisi pour que la sous-estimation change
    le nombre de rangees, faute de quoi elle serait invisible.
    """
    geometry = page_templates.GEOMETRY_V2
    page_width, _height = page_templates.page_size_mm(orientation)
    available = page_width - 2 * geometry.corner_clearance_mm()
    step = geometry.patch_size_mm + geometry.patch_spacing_mm
    per_row = int((available + geometry.patch_spacing_mm) // step)
    assert per_row == {PORTRAIT: 17, PAYSAGE: 27}[orientation], (orientation, per_row)
    # Sans l'ecart de fin, la capacite serait plus petite en paysage: c'est ce que la
    # formule ne doit pas faire.
    assert int(available // step) == {PORTRAIT: 17, PAYSAGE: 26}[orientation]
    for (candidate_orientation, count), rows in _BORDER_ROWS.items():
        if candidate_orientation != orientation:
            continue
        variant = dataclasses.replace(geometry, border_witness_count=count)
        band = dict(variant.frame_band_candidates(
            orientation, page_templates.QR_EDGE_BOTTOM))[
                page_templates.WITNESS_PLACEMENT_BORDERS]
        strip = (rows * geometry.patch_size_mm
                 + (rows - 1) * geometry.patch_spacing_mm
                 + geometry.patch_to_band_gap_mm[orientation])
        top = geometry.band_edges_mm(orientation, page_templates.QR_EDGE_BOTTOM)["top"]
        assert band["y"] - top == pytest.approx(strip), (orientation, count, rows)


def test_the_border_variant_row_count_follows_the_witness_cardinal() -> None:
    """Le cardinal de temoins et l'arrondi du nombre de rangees sont observables.

    28 temoins tiennent en **une** rangee par bord (17 emplacements par rangee en
    portrait); 60 en demandent deux, 400 en demandent tant que la bande s'effondre.
    Un arrondi par defaut au lieu d'un arrondi par exces rendrait zero rangee pour
    14 temoins -- donc une bande plus grande que ce que les pastilles laissent, et
    une planche ou les temoins recouvriraient le dessin.
    """
    geometry = page_templates.GEOMETRY_V2
    gap = geometry.patch_to_band_gap_mm[PORTRAIT]
    top = geometry.band_edges_mm(PORTRAIT, page_templates.QR_EDGE_BOTTOM)["top"]
    #: (temoins au total, rangees attendues par bord). 17 emplacements par rangee en
    #: portrait: 28 temoins -> 14 par bord -> une rangee; 60 -> 30 -> deux; 120 -> 60
    #: -> quatre. Les paliers sont choisis pour que le **nombre de rangees** change,
    #: sans quoi le test ne mesurerait que la formule d'une seule rangee.
    expected_rows = {2: 1, 28: 1, 60: 2, 120: 4}
    heights = {}
    for count, rows in expected_rows.items():
        variant = dataclasses.replace(geometry, border_witness_count=count)
        band = dict(variant.frame_band_candidates(
            PORTRAIT, page_templates.QR_EDGE_BOTTOM))[
                page_templates.WITNESS_PLACEMENT_BORDERS]
        heights[count] = band["height"]
        strip = (rows * geometry.patch_size_mm
                 + (rows - 1) * geometry.patch_spacing_mm + gap)
        assert band["y"] - top == pytest.approx(strip), (count, rows)
    # Plus de rangees, moins de bande -- et une rangee est exigee des le premier
    # temoin: un arrondi par defaut rendrait zero rangee pour 14 temoins par bord.
    assert heights[28] > heights[60] > heights[120]
    assert heights[2] == heights[28]
    assert heights[28] < page_templates.GEOMETRY_V2.frame_band_mm(
        PORTRAIT, 2)["height"]


def test_a_geometry_whose_border_variant_collapses_still_resolves(tightened) -> None:
    """Un candidat qui ne laisse aucune grille ne doit **pas** gagner.

    Mutant `E07`: rendre `+inf` au lieu de `0` quand aucune grille ne tient dans une
    bande ferait retenir le candidat le plus **impossible**. Aucun gabarit livre
    n'atteint ce cas -- d'ou le survivant -- donc il se construit: 600 temoins sur les
    bords effondrent la bande a une hauteur negative, **quel que soit le bord porteur
    du QR** (le cardinal est monte de 400 a 600 par la story 5.18: la passe de design
    rend la bande plus haute de 21,6 mm, donc 400 temoins n'y suffisaient plus).
    """
    geometry = dataclasses.replace(
        page_templates.GEOMETRY_V2, border_witness_count=600)
    for orientation in page_templates.ORIENTATIONS:
        for qr_edge in page_templates.QR_EDGES:
            borders = dict(geometry.frame_band_candidates(orientation, qr_edge))[
                page_templates.WITNESS_PLACEMENT_BORDERS]
            assert borders["height"] < 0, (orientation, qr_edge)
            assert page_templates._drawing_area_mm2(borders, 2) == 0.0
        assert geometry.witness_placement(orientation, 2) == (
            page_templates.WITNESS_PLACEMENT_SIDES)
        retained_edge = geometry.qr_edge(orientation, 2)
        assert geometry.frame_band_mm(orientation, 2) == dict(
            geometry.frame_band_candidates(orientation, retained_edge))[
                page_templates.WITNESS_PLACEMENT_SIDES]


def test_a_geometry_whose_two_candidates_collapse_is_refused() -> None:
    """Aucun placement composable: refus explicite, jamais une bande negative rendue."""
    # Dix-huit colonnes de temoins par cote effondrent la bande laterale des **quatre**
    # bords: le degagement calcule d'un flanc ne depend pas du nombre de colonnes (le QR
    # se colle a la marge d'encre sous la colonne), donc c'est le flanc **oppose** qui
    # doit manger la page pour que tous les candidats tombent. A douze colonnes, le
    # candidat « QR a gauche » laissait encore 48 mm de bande et le refus ne se
    # declenchait pas -- exactement le genre de premisse qu'un test doit verifier plutot
    # que supposer, et que l'assertion ci-dessous verifie.
    geometry = dataclasses.replace(
        page_templates.GEOMETRY_V2,
        patch_columns_per_side={PORTRAIT: 18, PAYSAGE: 18},
        border_witness_count=600,
    )
    for qr_edge in page_templates.QR_EDGES:
        for placement, band in geometry.frame_band_candidates(PORTRAIT, qr_edge):
            assert band["width"] <= 0 or band["height"] <= 0, (qr_edge, placement, band)
    with pytest.raises(page_templates.UnknownTemplateError, match="candidat de bande"):
        geometry.frame_band_mm(PORTRAIT, 2)


@pytest.fixture()
def tightened(monkeypatch):
    """Enregistrer une geometrie ou la variante haut/bas **gagne**, le temps d'un test.

    Le registre etant calcule a l'import, la fixture le reconstruit -- meme motif que
    la fixture `tightened_geometry` de `test_pdf_composition`. Douze colonnes de
    temoins par cote rendent la bande laterale negative, donc les rangees haut/bas
    gagnent: c'est le seul regime ou le `TemplateSpec` peut porter l'autre placement.
    """
    geometry = dataclasses.replace(
        page_templates.GEOMETRY_V2,
        version="vborders",
        patch_columns_per_side={PORTRAIT: 12, PAYSAGE: 12},
    )
    versions = dict(page_templates.GEOMETRY_VERSIONS)
    versions[geometry.version] = geometry
    monkeypatch.setattr(page_templates, "GEOMETRY_VERSIONS", versions)
    monkeypatch.setattr(page_templates, "_REGISTRY", page_templates._build_registry())
    return geometry


def test_the_registry_carries_the_placement_it_really_retained(tightened) -> None:
    """Mutant `E10`: le `TemplateSpec` porte le placement **calcule**, pas une constante.

    Tous les gabarits livres retenant les cotes, un `witness_placement` ecrit en dur a
    « cotes » est indistinguable -- jusqu'a ce qu'une geometrie retienne l'autre
    branche. Le test verifie alors les deux ensemble: le nom porte **et** la bande qui
    a produit les zones.
    """
    spec = page_templates.template_for(PORTRAIT, 2, "0", "vborders")
    assert spec.witness_placement == page_templates.WITNESS_PLACEMENT_BORDERS
    expected = dict(tightened.frame_band_candidates(PORTRAIT, spec.qr_edge))[
        page_templates.WITNESS_PLACEMENT_BORDERS]
    assert spec.frame_band_mm == expected
    # Les zones sont bien dans cette bande, et non dans celle des cotes.
    for zone in spec.frame_zones_mm:
        assert zone["x"] >= expected["x"] - 1e-9
        assert zone["x"] + zone["width"] <= expected["x"] + expected["width"] + 1e-9
    # Et la bande d'en-tete est lue sur cette meme bande (cablage, mutant `M02`): elle
    # se mesure au-dessus de l'ouverture de la bande de frames **retenue**, pas de celle
    # des cotes. La bande du QR, elle, peut etre ailleurs depuis la story 5.18 -- ce
    # gabarit-ci retient d'ailleurs un autre bord que le haut, ce que le test verifie
    # plutot que de le supposer.
    _band_x, _band_y, _band_w, band_h = page_templates.header_band_mm(spec)
    assert band_h == pytest.approx(
        expected["y"] - spec.geometry.printer_margin_mm
        - page_templates.TOP_BAND_GUARD_MM)
    assert spec.qr_edge in page_templates.QR_EDGES
    qr_x, qr_y, qr_w, qr_h = page_templates.qr_reserved_zone_mm(spec)
    assert qr_w == pytest.approx(page_templates.qr_footprint_bound_mm())
    assert qr_h > 0


#: Zones d'en-tete de la v1, **en dur**: elles etaient deux litteraux (y = 10, hauteur
#: 40) et sont derivees de la bande haute depuis la story 5.15. En v1 la derivation doit
#: redonner exactement ces nombres, sans quoi le texte d'en-tete d'une planche v1
#: recomposee changerait de place.
_V1_HEADER_Y_MM = 10.0
_V1_HEADER_HEIGHT_MM = 40.0


@pytest.mark.parametrize("orientation", list(page_templates.ORIENTATIONS))
def test_the_v1_header_zones_are_unchanged_by_their_derivation(orientation) -> None:
    """Non-regression des deux nombres d'en-tete, et sens de la derivation sous la v2.

    La bande haute de la v1 ouvre a 5 mm sur 50 mm de haut: un retrait de 5 mm de
    chaque cote redonne 10 et 40. Sous la v2 la bande ne fait plus que 38,8 mm, donc un
    en-tete de 40 mm pose a y = 10 descendrait **dans** la bande de frames -- c'est ce
    qu'un retrait applique d'un seul cote, ou nul, ferait reapparaitre.
    """
    spec_v1 = page_templates.template_for(orientation, 2, "0", "v1")
    qr_rect = (spec_v1.page_width_mm / 2 - 20.0, 10.0, 40.0, 40.0)
    zones = pdf_composition._header_zones_mm(spec_v1, qr_rect)
    assert set(zones) == {"header_left", "header_right"}
    for name, rect in zones.items():
        assert rect[1] == pytest.approx(_V1_HEADER_Y_MM), name
        assert rect[3] == pytest.approx(_V1_HEADER_HEIGHT_MM), name
    spec_v2 = page_templates.template_for(orientation, 2, "0", "v2")
    band_y, band_h = page_templates.qr_band_mm(spec_v2)[1], page_templates.qr_band_mm(
        spec_v2)[3]
    footprint = page_templates.qr_footprint_bound_mm()
    v2_rect = (spec_v2.page_width_mm / 2 - footprint / 2, band_y, footprint, footprint)
    v2_zones = pdf_composition._header_zones_mm(spec_v2, v2_rect)
    for name, rect in v2_zones.items():
        # Entierement au-dessus de l'ouverture de la bande de frames.
        assert rect[1] + rect[3] <= spec_v2.frame_band_mm["y"] + 1e-9, name
        assert rect[3] < _V1_HEADER_HEIGHT_MM, name


def test_an_unknown_geometry_version_is_refused_by_the_composition() -> None:
    """Vocabulaire ferme, comme pour tous les autres parametres de composition.

    Un repli silencieux sur le defaut produirait un `template_id` qui **ment** sur la
    geometrie imprimee, et le seul symptome serait une homographie fausse au scan, des
    mois plus tard. C'est le meme motif que le refus de `resolve_gamut_map`.
    """
    assert pdf_composition.resolve_geometry_version(None) == (
        page_templates.DEFAULT_GEOMETRY_VERSION)
    assert pdf_composition.resolve_geometry_version("v1") == "v1"
    with pytest.raises(pdf_composition.ParameterVocabularyError, match="v99"):
        pdf_composition.resolve_geometry_version("v99")
    # Et le refus nomme les versions connues, pour que l'operateur sache quoi ecrire.
    with pytest.raises(pdf_composition.ParameterVocabularyError, match="v1, v2"):
        pdf_composition.resolve_geometry_version("prudent")


def test_the_band_carried_by_a_spec_cannot_be_mutated_from_outside() -> None:
    """Copie defensive, verifiee en **mutant** la valeur rendue.

    Les zones internes de `patch_presets.reserved_zones_mm` etaient partagees entre
    tous les gabarits d'une orientation, et une mutation par un appelant corrompait le
    registre pour tout le processus. La bande portee par un `TemplateSpec` est exposee
    par une copie pour la meme raison; un test qui se contenterait de comparer les
    valeurs ne verrait pas la difference entre une copie et un alias.
    """
    spec = page_templates.get_template("tpl-a4-portrait-2f-v2")
    band = spec.frame_band_mm
    band["y"] = -1000.0
    assert page_templates.get_template("tpl-a4-portrait-2f-v2").frame_band_mm["y"] == (
        pytest.approx(spec.geometry.band_edges_mm(PORTRAIT, spec.qr_edge)["top"]))
    assert spec.frame_band_mm["y"] > 0


@pytest.mark.parametrize("template_id", ["tpl-a4-portrait-2f-v1", "tpl-a4-portrait-2f-v2"])
def test_the_zones_carried_by_a_spec_cannot_be_mutated_from_outside(
        template_id: str) -> None:
    """Meme garde que pour la bande, sur les zones de dessin (revue 5.15, couche 2).

    L'asymetrie etait visible: la story posait la copie defensive sur `frame_band` et
    laissait `frame_zones_mm` exposer des `dict` nus partages par tout le processus. Ces
    zones-la sont pourtant celles que **tous** les consommateurs lisent -- composition,
    recadrage au scan, resolution de geometrie -- donc une corruption s'y propage a
    l'impression comme a la relecture, et pour la duree du programme.

    Les deux versions sont parametrees parce que la v1 est la geometrie des planches
    deja imprimees: c'est elle qu'une corruption rendrait irrecuperable.
    """
    spec = page_templates.get_template(template_id)
    zones = spec.frame_zones_mm
    reference = zones[0]["width"]
    assert reference > 0

    zones[0]["width"] = -999.0
    zones[0]["nouvelle-cle"] = 1.0

    fresh = page_templates.get_template(template_id).frame_zones_mm
    assert fresh[0]["width"] == pytest.approx(reference)
    assert "nouvelle-cle" not in fresh[0]
    # Et deux lectures successives ne partagent pas les memes dicts: sans cela, la
    # premiere mutation aurait suffi et ce test passerait pour la mauvaise raison.
    assert spec.frame_zones_mm[0] is not spec.frame_zones_mm[0]


def test_the_derived_footer_stack_keeps_a_real_gap_between_its_two_zones() -> None:
    """L'ecart bloc / consigne est reel, et il est **compte** au bord bas.

    Mutant survivant `H05`: le supprimer rend les deux zones tangentes -- non
    chevauchantes, donc invisibles a un test de non-chevauchement -- et fait mentir le
    degagement du bas d'un millimetre. Deux textes tangents a 8 pt se lisent comme un
    seul bloc a l'impression, et la pile ne tiendrait plus dans ce qu'elle declare.

    **La pile a trois etages depuis la story 5.18**, et le test les mesure tous les
    trois: les identifiants residuels, les colonnes techniques posees juste dessous
    (contigues, meme interligne, meme bloc de lecture) et la consigne de scan separee par
    l'ecart. La somme des hauteurs doit valoir exactement la hauteur de bloc que la
    geometrie declare -- sinon le degagement du bord bas annonce autre chose que ce
    qu'il loge.
    """
    for orientation in page_templates.ORIENTATIONS:
        spec = page_templates.template_for(orientation, 2, "0", "v2")
        zones = page_templates.footer_zones_mm(spec)
        block_x, block_y, _block_w, block_h = zones["footer_block"]
        line_x, line_y, _line_w, line_h = zones["footer_line"]
        assert block_x == line_x
        technical = [zones[name]
                     for name in page_templates.FOOTER_TECHNICAL_ZONE_NAMES]
        # Les colonnes techniques sont contigues au bloc d'identite, cote a cote entre
        # elles, et toutes a la meme ordonnee.
        assert {rect[1] for rect in technical} == {block_y + block_h}
        for rect in technical:
            assert rect[3] == pytest.approx(
                page_templates.FOOTER_TECHNICAL_ROW_BUDGET
                * page_templates.body_line_leading_mm())
        for left, right in zip(technical, technical[1:]):
            assert right[0] - (left[0] + left[2]) == pytest.approx(
                page_templates.TEXT_GAP_MM)
        technical_height = technical[0][3]
        assert block_h + technical_height == pytest.approx(
            spec.geometry.footer_block_height_mm())
        gap = line_y - (block_y + block_h + technical_height)
        assert gap == pytest.approx(page_templates.FOOTER_STACK_GAP_MM)
        assert gap > 0
        # Et la pile complete tient exactement dans le degagement declare: marge
        # d'encre + consigne + ecart + bloc + ecart + bande d'etiquettes.
        clearance = spec.geometry.bottom_text_clearance_mm()
        stack = (spec.page_height_mm - block_y + page_templates.FOOTER_STACK_GAP_MM
                 + page_templates.SLOT_LABEL_STRIP_MM)
        assert stack == pytest.approx(clearance)
        assert line_y + line_h == pytest.approx(
            spec.page_height_mm - spec.geometry.printer_margin_mm)


def test_a_header_inset_wider_than_the_band_yields_no_zone_at_all(monkeypatch) -> None:
    """Mutant survivant `I04`: une hauteur d'en-tete negative doit rendre **rien**.

    La garde n'est pas atteignable par les geometries enregistrees -- la bande haute
    vaut au moins l'emprise reservee du QR, donc 38,8 mm -- mais elle protege d'un
    retrait mal choisi, et c'est cela qui se teste: un rectangle de hauteur negative
    transporte jusqu'au rendu y dessinerait un bloc de texte a l'envers, et le test
    global de non-chevauchement ne verrait rien (un rectangle de hauteur negative ne
    recouvre personne).

    **Le test porte sur la v1 depuis la story 5.18**, et pas par commodite: le retrait
    d'en-tete n'existe que pour reproduire les deux litteraux de la v1 (y = 10, hauteur
    40), et l'entete d'identite de la v2 prend la bande telle quelle -- lui appliquer le
    retrait mangerait 10 des 18 mm de bande haute et ferait refuser un entete qui tient.
    La garde qu'on eprouve ici est donc celle de la disposition qui l'emploie.
    """
    spec = page_templates.template_for(PORTRAIT, 2, "0", "v1")
    assert not spec.geometry.identity_in_header
    band_h = page_templates.header_band_mm(spec)[3]
    monkeypatch.setattr(pdf_composition, "_TEXT_HEADER_INSET_MM", band_h / 2 + 1.0)
    footprint = page_templates.qr_footprint_bound_mm()
    qr_rect = (spec.page_width_mm / 2 - footprint / 2, 5.0, footprint, footprint)
    assert pdf_composition._header_zones_mm(spec, qr_rect) == {}
    # Et la disposition « identite en entete » n'a **pas** de garde a retrait, parce
    # qu'elle n'a pas de retrait: sa garde est la hauteur de bande elle-meme.
    v2 = page_templates.template_for(PORTRAIT, 2, "0", "v2")
    zones = pdf_composition._header_zones_mm(
        v2, page_templates.qr_reserved_zone_mm(v2))
    assert set(zones) == {"header_identity"}
    assert zones["header_identity"][3] == pytest.approx(
        page_templates.header_band_mm(v2)[3])


def test_the_derived_patch_columns_mirror_each_other() -> None:
    """Mutant survivant `K04`: la colonne droite est le **miroir** de la gauche.

    Avec une seule colonne par cote -- le cas de la v2 livree -- `reversed(range(1))`
    et `range(1)` rendent la meme sequence, donc l'inversion est invisible: c'est un
    equivalent **pour cette geometrie seulement**. Des deux colonnes par cote, elle
    inverse l'ordre interieur/exterieur et rapproche les deux copies d'une valeur, ce
    qui vide de son sens la moyenne par page (les deux copies doivent etre aux
    extremites opposees de la feuille, a plus de 100 mm).
    """
    from mixed_media_utility import patch_presets as pp

    for columns in (1, 2, 3):
        geometry = dataclasses.replace(
            page_templates.GEOMETRY_V2,
            patch_columns_per_side={PORTRAIT: columns, PAYSAGE: columns},
        )
        xs = pp._derived_columns_x_mm(geometry, PORTRAIT, 210.0)
        assert len(xs) == 2 * columns
        step = geometry.patch_size_mm + geometry.patch_spacing_mm
        left, right = xs[:columns], xs[columns:]
        # Croissantes a gauche, croissantes a droite, et symetriques deux a deux.
        assert list(left) == sorted(left)
        assert list(right) == sorted(right)
        for index in range(columns):
            mirrored = 210.0 - left[index] - geometry.patch_size_mm
            assert right[columns - 1 - index] == pytest.approx(mirrored), (
                columns, index)
        assert left[0] == pytest.approx(geometry.printer_margin_mm)
        if columns > 1:
            assert left[1] - left[0] == pytest.approx(step)


@pytest.mark.parametrize("orientation,capacity", [(PORTRAIT, 26), (PAYSAGE, 17)])
def test_the_derived_row_capacity_is_bounded_by_both_quiet_zones(
        orientation, capacity) -> None:
    """La capacite d'une colonne laterale, epinglee, et sa borne du bas.

    Mutant survivant `K06`: ne borner la capacite que par le haut la fait passer de 17
    a 19 rangees en paysage -- assez pour que `patches-18-v2` **paraisse** placable la
    ou ses deux dernieres pastilles tomberaient dans le silence du marqueur du bas,
    donc sur la detection des coins. Aucun placement livre ne bouge pour autant, d'ou
    le survivant: la capacite se verifie donc directement, avec le chiffre.
    """
    from mixed_media_utility import patch_presets as pp

    geometry = page_templates.GEOMETRY_V2
    assert pp._derived_row_capacity(geometry, orientation) == capacity
    # Le chiffre est bien la borne: une rangee de plus sortirait du couloir libre.
    _page_width, page_height = page_templates.page_size_mm(orientation)
    first = pp._derived_first_row_y_mm(geometry)
    step = geometry.patch_size_mm + geometry.patch_spacing_mm
    last_bottom = first + (capacity - 1) * step + geometry.patch_size_mm
    limit = page_height - geometry.corner_clearance_mm()
    assert last_bottom <= limit + 1e-9, (orientation, last_bottom, limit)
    assert last_bottom + step > limit, (orientation, "la capacite n'est pas maximale")
    # Et c'est cette borne qui rend `patches-18-v2` infaisable en paysage: 18 rangees.
    if orientation == PAYSAGE:
        assert capacity < 18
        assert ("v2", orientation, "patches-18-v2") in pp._PLACEMENT_UNPLACEABLE
    else:
        assert capacity >= 18


def test_a_preset_that_exceeds_the_row_capacity_is_not_placed() -> None:
    """Mutant survivant `K07`: le depassement de capacite rend `None`, pas un placement.

    C'est la garde qui **fabrique** la liste des couples infaisables: sans elle, un
    preset de 18 valeurs par cote recevrait en paysage v2 un placement de 18 rangees
    dans un couloir qui en tient 17, donc deux pastilles dans le silence du marqueur du
    bas. Le couple etant enumere comme infaisable, la garde n'est plus atteinte par la
    construction du registre -- d'ou le survivant -- et se teste donc directement.
    """
    from mixed_media_utility import patch_presets as pp

    geometry = page_templates.GEOMETRY_V2
    # 18 valeurs par cote en paysage: 18 rangees pour 17 possibles -> refus.
    assert pp._derived_placement(geometry, PAYSAGE, 297.0, pp._ORDER_18) is None
    # Les deux presets qui tiennent, eux, rendent un placement complet.
    for order in (pp._ORDER_9, pp._ORDER_12):
        placement = pp._derived_placement(geometry, PAYSAGE, 297.0, order)
        assert placement is not None
        assert len(placement) == 2 * len(order)
    # Et en portrait le couloir est assez long pour les 18.
    portrait = pp._derived_placement(geometry, PORTRAIT, 210.0, pp._ORDER_18)
    assert portrait is not None and len(portrait) == 36


def test_a_missing_derivable_placement_is_refused_at_import_not_skipped(
        monkeypatch) -> None:
    """Mutant survivant `L03`: un placement non derivable **refuse**, jamais saute.

    La garde transforme un trou de registre en erreur de programmation immediate: un
    couple saute en silence deviendrait un `UndefinedPlacementError` a l'execution, sur
    une machine d'operateur, pour une combinaison que la CLI expose. Elle n'est plus
    atteignable une fois les couples infaisables enumeres -- d'ou le survivant -- donc
    le test vide l'enumeration et exige que la construction echoue.
    """
    from mixed_media_utility import patch_presets as pp

    monkeypatch.setattr(pp, "_PLACEMENT_UNPLACEABLE", ())
    with pytest.raises(pp.PatchPresetGeometryError, match="patches-18-v2"):
        pp._build_placements()
    # Et avec l'enumeration reelle, la construction passe: la garde ne se declenche
    # pas sur le registre livre.
    monkeypatch.undo()
    assert pp._build_placements()


def test_the_witness_cardinal_is_the_one_the_arbitrage_retained() -> None:
    """`WITNESS_PATCH_COUNT_V2` est un contrat avec la story 5.16, pas un reglage.

    Mutant survivant `A07`: le ramener de 28 a 18 ne deplace **aucune** bande, les deux
    tenant en une rangee par bord -- c'est donc la valeur elle-meme qu'il faut epingler,
    avec sa provenance. 14 valeurs en double replicat (`EPIC5-ARB-57`): 8 sentinelles,
    les tetes `neutral-020` / `neutral-245`, les trois primaires, et un neutre median.
    Le doublement n'est pas du confort: une valeur vue une seule fois n'a pas de
    dispersion, donc la garde de divergence de 5.16 serait aveugle.
    """
    #
    # **Amende par la story 5.23** (`EPIC5-ARB-82`, AC 1): 17 valeurs en double
    # replicat. Les trois secondaires reviennent parce que la divergence se mesure
    # desormais entre deux feuilles **imprimees**, et qu'une derive d'encre cyan ou
    # magenta ne se voit pas sur un jeu RVB + neutres. Le doublement, lui, ne bouge pas
    # et pour la meme raison qu'en 5.16.
    assert page_templates.WITNESS_PATCH_COUNT_V2 == 34
    assert page_templates.WITNESS_PATCH_COUNT_V2 == 17 * 2
    assert page_templates.GEOMETRY_V2.border_witness_count == (
        page_templates.WITNESS_PATCH_COUNT_V2)
    # Et il tient sur une seule rangee par bord dans les deux orientations: c'est ce
    # qui rend la variante haut/bas comparable a 10 mm de bord pres.
    for orientation in page_templates.ORIENTATIONS:
        page_width, _height = page_templates.page_size_mm(orientation)
        available = page_width - 2 * page_templates.GEOMETRY_V2.corner_clearance_mm()
        step = (page_templates.GEOMETRY_V2.patch_size_mm
                + page_templates.GEOMETRY_V2.patch_spacing_mm)
        per_row = int((available + page_templates.GEOMETRY_V2.patch_spacing_mm) // step)
        assert page_templates.WITNESS_PATCH_COUNT_V2 // 2 <= per_row, orientation


def test_the_witness_cardinal_change_prints_the_same_image_sheets() -> None:
    """Passer le cardinal de 28 a 34 ne **redefinit pas** la geometrie v2.

    **Le test etait tautologique et ne mesurait rien** (finding 12 du triage de 5.23,
    corrige le 2026-08-19). Il construisait la variante par
    `dataclasses.replace(reference, border_witness_count=34)` alors que la reference
    **vaut deja 34** depuis que la story 5.23 l'y a portee: les deux objets etaient egaux,
    et les trois assertions ci-dessous comparaient trente fois un objet a lui-meme. La
    frontiere que la story revendique -- l'inertie du **28**, c'est-a-dire du cardinal
    d'avant, seul cas ou toucher un constituant fige de la v2 est admissible -- n'etait
    mesuree nulle part. La variante porte donc le **28**, et le sens de la comparaison est
    celui du titre: ce qui s'imprimait a 28 s'imprime encore.

    Frontiere exigee par la story 5.23: `border_witness_count` est un constituant fige de
    la v2, et le depot interdit toute redefinition silencieuse d'une version -- une
    planche deja imprimee serait alors scannee avec une homographie fausse, sans qu'aucune
    etape n'echoue. Le changement est donc admissible **seulement** si rien de ce qui
    s'imprime ne bouge, et cela se mesure gabarit par gabarit au lieu de s'affirmer.

    Le mecanisme, pour que la prochaine session n'ait pas a le redecouvrir: ce cardinal ne
    dimensionne que la variante « rangees haut/bas » du placement des temoins, que
    `_best_candidate` met en concurrence avec la variante « cotes » **par surface de
    dessin**. Aucun gabarit v2 ne retient la variante haut/bas a 28, et l'augmenter ne
    peut que l'epaissir, donc la desavantager davantage.

    Les deux bouts sont epingles: la variante retenue est identique (volet d'inertie),
    **et** un cardinal absurde deplace bien quelque chose (volet de mordant) -- sans lui,
    ce test passerait aussi si le champ etait purement ignore.
    """
    reference = page_templates.GEOMETRY_V2
    # Le cardinal **d'avant** la story 5.23, et non celui de la reference: `replace` avec
    # la valeur courante rend un objet egal, donc un test qui ne mesure rien.
    assert reference.border_witness_count == 34
    ancien_cardinal = dataclasses.replace(reference, border_witness_count=28)
    assert ancien_cardinal != reference
    couverts = 0
    for template_id in page_templates.known_template_ids():
        spec = page_templates.get_template(template_id)
        if spec.geometry_version != "v2":
            continue
        couverts += 1
        orientation, cardinal = spec.orientation, spec.frames_per_page
        assert (ancien_cardinal.frame_band_mm(orientation, cardinal)
                == reference.frame_band_mm(orientation, cardinal)), template_id
        assert (ancien_cardinal.witness_placement(orientation, cardinal)
                == reference.witness_placement(orientation, cardinal)), template_id
        assert (ancien_cardinal.qr_edge(orientation, cardinal)
                == reference.qr_edge(orientation, cardinal)), template_id
        # **Et les deux candidats, pas seulement celui qui gagne.** Les trois assertions
        # ci-dessus portent sur le placement **retenu**, et la variante haut/bas ne l'est
        # sur aucun gabarit v2: comparer les seuls verdicts laisse donc le cardinal
        # dominer sans jamais etre mesure -- aucune mutation de son dimensionnement ne
        # les deplace. Les candidats, eux, sont la ou le cardinal agit reellement: 14
        # comme 17 temoins par bord tiennent en **une** rangee, et c'est cette marge-la
        # que l'inertie du 28 revendique. Mutant tue par ce volet et par lui seul:
        # `per_row` reduit, qui fait passer 14 a deux rangees et 17 a trois.
        assert (ancien_cardinal.frame_band_candidates(orientation, spec.qr_edge)
                == reference.frame_band_candidates(
                    orientation, spec.qr_edge)), template_id
    assert couverts == 30, couverts

    # Volet de mordant: a 600 temoins la variante haut/bas devient inutilisable et la
    # bande change -- donc le champ n'est pas ignore, il est **domine**.
    absurde = dataclasses.replace(reference, border_witness_count=600)
    portrait_4f = page_templates.get_template("tpl-a4-portrait-4f-v2")
    candidats_reference = reference.frame_band_candidates(
        portrait_4f.orientation, portrait_4f.qr_edge)
    candidats_absurdes = absurde.frame_band_candidates(
        portrait_4f.orientation, portrait_4f.qr_edge)
    assert candidats_reference != candidats_absurdes


@pytest.mark.parametrize("width,height", [(30.0, 25.0), (20.0, 15.0)])
def test_a_band_too_small_for_a_grid_measures_zero_not_infinity(width, height) -> None:
    """Mutant survivant `E07`: aucune grille ne tient -> surface **nulle**.

    La fonction compare deux placements candidats, dont l'un peut ne rien laisser de
    composable; elle rend donc `0.0` la ou `_grid_shape` refuse. Rendre `+inf` ferait
    retenir le candidat le plus **impossible** -- et le refus explicite, qui ne se
    declenche que si les deux candidats rendent zero, ne se declencherait jamais.

    La bande est ici positive dans les deux dimensions et pourtant trop petite: c'est
    le seul regime qui atteint le refus de `_grid_shape` (une bande de dimension
    negative est deja arretee un cran plus haut). Les deux cas mesures: 8 zones 16:9
    au pas de 10 mm ne tiennent dans aucune partition de 30 x 25 mm.
    """
    band = {"x": 0.0, "y": 0.0, "width": width, "height": height}
    with pytest.raises(page_templates.UnknownTemplateError):
        page_templates._grid_shape(width, height, 8)
    assert page_templates._drawing_area_mm2(band, 8) == 0.0
    # Et une bande composable gagne toujours contre elle, quel que soit l'ordre.
    good = page_templates.GEOMETRY_V2.frame_band_mm(PORTRAIT, 8)
    assert page_templates._drawing_area_mm2(good, 8) > 0.0
    assert max(
        page_templates._drawing_area_mm2(candidate, 8) for candidate in (band, good)
    ) == page_templates._drawing_area_mm2(good, 8)


# ---------------------------------------------------------------------------
# Story 5.18 -- la passe de design de la v2
#
# Les tests ci-dessous sont ceux dont la raison d'etre est la passe elle-meme:
# la selection du bord porteur du QR et sa regle de departage, la gratuite de
# l'entete d'identite, la justification du pas de grille, et la reevaluation du
# vocabulaire des cardinaux.
# ---------------------------------------------------------------------------


def test_at_least_one_gabarit_retains_each_edge_the_measurement_designates() -> None:
    """Le bord porteur est **calcule**, et la mesure designe deux bords (AC 3).

    L'AC exige qu'au moins un gabarit retienne chacun des bords que la mesure designe --
    `bas` et `gauche` au minimum. Le premier est le cas general et le second l'exception,
    et l'exception est le seul cardinal **limite en hauteur**: trois zones 16:9 empilees
    n'utilisent que 129 des 139 mm de largeur qui restent apres le degagement du flanc,
    donc payer 44,6 mm de largeur pour rendre 21,6 mm de hauteur y est rentable. Sur les
    autres, la largeur est la dimension rare et le flanc est perdant.
    """
    retained = {}
    for orientation, cardinal in GABARITS_V2:
        spec = page_templates.template_for(orientation, cardinal, "0", "v2")
        retained[(orientation, cardinal)] = spec.qr_edge
    assert page_templates.QR_EDGE_BOTTOM in retained.values(), retained
    assert page_templates.QR_EDGE_LEFT in retained.values(), retained
    # Et le bord retenu est bien celui qui rend le plus: la comparaison, pas une
    # heuristique. Un mutant « rendre toujours le bas » passerait sans cette boucle.
    for (orientation, cardinal), edge in retained.items():
        geometry = page_templates.GEOMETRY_V2
        areas = {}
        for candidate_edge in page_templates.QR_EDGES:
            areas[candidate_edge] = max(
                _drawing_area(geometry, orientation, cardinal, band)
                for _placement, band in geometry.frame_band_candidates(
                    orientation, candidate_edge)
            )
        assert areas[edge] == pytest.approx(max(areas.values()), abs=1e-6), (
            orientation, cardinal, areas)
    # Les cardinaux qui partent sur un flanc sont ceux que la mesure designe, et ils sont
    # **deux**: `3f` et `4f` en portrait, tous deux au bord gauche. Si un troisieme s'y
    # mettait -- ou si l'un des deux en sortait -- c'est que la geometrie a change de
    # regime et le tableau de surfaces de l'AC 7 ne serait plus celui-la.
    #
    # **Ce commentaire disait « et un seul », une ligne au-dessus d'un `assert` sur deux
    # couples** (corrige le 2026-08-12, B3 de la revue de 5.18). Le defaut n'etait pas
    # dans l'assertion, qui etait juste, mais dans la phrase qui la decrit -- et c'est
    # celle-la qu'une prochaine session lit avant de decider si le second couple est une
    # anomalie a corriger.
    flanks = {key for key, edge in retained.items()
              if edge in (page_templates.QR_EDGE_LEFT, page_templates.QR_EDGE_RIGHT)}
    assert flanks == {(PORTRAIT, 3), (PORTRAIT, 4)}, flanks
    assert len(flanks) == 2, flanks
    # 3f portrait est le gabarit dont la mesure parle, et c'est **lui** qui gagne le plus
    # au flanc: +21,3 % sur le banc, et un ecart franc en production.
    geometry = page_templates.GEOMETRY_V2
    flank = max(_drawing_area(geometry, PORTRAIT, 3, band)
                for _p, band in geometry.frame_band_candidates(
                    PORTRAIT, page_templates.QR_EDGE_LEFT))
    horizontal = max(_drawing_area(geometry, PORTRAIT, 3, band)
                     for _p, band in geometry.frame_band_candidates(
                         PORTRAIT, page_templates.QR_EDGE_BOTTOM))
    assert flank / horizontal - 1 > 0.02, (flank, horizontal)
    # Et l'ecart ne vient PAS de la largeur rendue par le degagement calcule du flanc:
    # 3f est borne en **hauteur**, donc la largeur supplementaire lui est inutilisable.
    # C'est ce que le releve d'Egan du 2026-08-12 a mesure, et c'est ce qui interdit de
    # presenter la correction du flanc comme un gain de surface.
    wider = dict(page_templates.GEOMETRY_V2.frame_band_candidates(
        PORTRAIT, page_templates.QR_EDGE_LEFT))[
            page_templates.WITNESS_PLACEMENT_SIDES]
    narrower = dict(wider, x=wider["x"] + 8.0, width=wider["width"] - 8.0)
    assert _drawing_area(geometry, PORTRAIT, 3, narrower) == pytest.approx(
        _drawing_area(geometry, PORTRAIT, 3, wider), abs=1e-6)


def test_a_constructed_gabarit_where_the_top_edge_wins_proves_the_comparison() -> None:
    """**La comparaison a lieu**, et elle peut retenir un autre bord (AC 3).

    Aucun gabarit livre ne met le QR au bord haut, et c'est demontrable plutot
    qu'accidentel: le bord bas paie `max(coin + supplement, pied)` et le bord haut
    `max(coin, entete)`; le premier etant toujours superieur ou egal, y poser le QR est
    toujours au moins aussi bon. Un mutant « rendre toujours le bas » passerait donc
    **toute** la suite -- c'est le defaut `M25` / `M33` du depot, transpose a une
    selection de bord.

    La geometrie construite ici renverse l'inegalite par le seul chemin qui existe: un
    entete d'identite si haut que le bord haut devient le plus cher des deux. Le QR y est
    alors gratuit **au bord haut**, et le calcul doit le voir.
    """
    monkey = pytest.MonkeyPatch()
    try:
        # 60 pt: il faut depasser l'exigence du QR (49,62 mm) et non seulement le
        # degagement de coin, sinon le bord haut reste borne par le QR lui-meme et le
        # test ne renverse rien -- verifie par l'assertion qui suit.
        monkey.setattr(page_templates, "HEADER_IDENTITY_FONT_PT", 60.0)
        geometry = page_templates.GEOMETRY_V2
        edges = geometry.band_edges_mm(PORTRAIT, page_templates.QR_EDGE_TOP)
        assert edges["top"] > geometry.qr_edge_clearance_mm(), (
            "l'entete construit doit dominer l'exigence du QR, sinon le test ne "
            "renverse rien")
        chosen = {cardinal: geometry.qr_edge(PORTRAIT, cardinal)
                  for cardinal in page_templates.frames_per_page_vocabulary(
                      PORTRAIT, "v2")}
        assert page_templates.QR_EDGE_TOP in chosen.values(), chosen
    finally:
        monkey.undo()
    # Et l'entete revenu a son corps reel, plus aucun gabarit ne retient le haut: la
    # bascule vient bien du parametre et non d'un residu.
    assert page_templates.HEADER_IDENTITY_FONT_PT == 14.0
    assert page_templates.QR_EDGE_TOP not in {
        page_templates.GEOMETRY_V2.qr_edge(orientation, cardinal)
        for orientation, cardinal in GABARITS_V2
    }


def test_the_computed_qr_edge_helps_strictly_more_than_one_gabarit() -> None:
    """**Verrou du bloquant B1**: l'apport du bord porteur calcule, mesure et non cite.

    L'AC 3 s'etait requalifiee elle-meme -- « elle vaut +3,0 % au total, elle n'aide qu'un
    seul cardinal, elle ne doit pas etre presentee comme le coeur de la passe » -- et
    l'AC 5 declarait le pied de page « LE levier, +27,7 points ». **Les deux enonces sont
    inverses**, et la cause est connue: la requalification etait mesuree sur un banc qui
    posait un pied de **2 rangees** la ou la production en reserve **6**. Plus le pied est
    haut, plus le bord bas est cher a occuper par du texte, donc plus il est rentable d'y
    poser le QR a la place -- le couplage joue **en faveur** de l'AC 3.

    **Le risque que ce test ferme, et il est concret**: en l'etat, une prochaine session
    lit « +3,0 %, un seul cardinal » et supprime le mecanisme en croyant retirer un levier
    mort. Rien ne l'en empechait.

    **Le test calcule les deux geometries et ne recopie aucun pourcentage** -- c'est la
    lecon de la journee, et elle vaut contre ce test aussi: un chiffre epingle ici
    derierait au premier changement de constituant, et c'est exactement comment les six
    chiffres du « plancher de verification » sont devenus faux. Ce qui est asserte est donc
    une propriete de **forme**: le bord calcule ne perd jamais, il gagne strictement sur
    plus d'un gabarit, et son apport cumule est franc.
    """
    livre = page_templates.GEOMETRY_V2
    # Le comportement d'avant l'AC 3: le QR au bord haut, sans exception. C'est la seule
    # difference entre les deux geometries -- tout le reste, pied compris, est celui de la
    # production, ce qui est precisement ce que le banc n'avait pas fait.
    force_haut = dataclasses.replace(livre, qr_bearing_edge=page_templates.QR_EDGE_TOP)
    assert livre.qr_bearing_edge is None
    assert force_haut.qr_bearing_edge == page_templates.QR_EDGE_TOP
    aides = []
    for orientation, cardinal in GABARITS_V2:
        calcule = _drawing_area(livre, orientation, cardinal)
        au_haut = _drawing_area(force_haut, orientation, cardinal)
        # Le bord calcule est le **maximum** sur les quatre bords, donc il ne peut jamais
        # rendre moins que l'un d'eux en particulier. Un mutant qui inverserait la
        # comparaison tomberait ici avant de tomber sur le compte.
        assert calcule >= au_haut - 1e-9, (orientation, cardinal, calcule, au_haut)
        if calcule > au_haut + 1e-6:
            aides.append((orientation, cardinal))
    # **Strictement plus d'un gabarit aide**: c'est ce que l'AC 3 retractee niait, et c'est
    # la propriete qui interdit de lire ce mecanisme comme un supplement peu couteux.
    assert len(aides) > 1, aides
    # Et il en aide la **majorite**, ce qui est une borne plus forte que « plus d'un » et
    # reste une propriete de forme. Une geometrie ou le bord calcule n'aiderait que deux
    # gabarits sur dix serait un autre regime, et il doit se voir.
    assert len(aides) * 2 > len(GABARITS_V2), (aides, len(GABARITS_V2))
    # L'apport cumule est franc -- pas 3 %. Le seuil est bas et rond a dessein: il n'est
    # pas une mesure, c'est une borne qui separe « levier de premier rang » de
    # « supplement negligeable », et elle est loin de la valeur mesuree.
    cumule_calcule = sum(_drawing_area(livre, o, c) for o, c in GABARITS_V2)
    cumule_au_haut = sum(_drawing_area(force_haut, o, c) for o, c in GABARITS_V2)
    assert cumule_calcule / cumule_au_haut - 1 > 0.10, (
        cumule_calcule, cumule_au_haut)
    # Le gabarit le mieux aide gagne beaucoup plus qu'un supplement: la aussi une borne,
    # pas une mesure.
    meilleur = max(
        _drawing_area(livre, o, c) / _drawing_area(force_haut, o, c) - 1
        for o, c in GABARITS_V2
    )
    assert meilleur > 0.25, meilleur


#: Les deux leviers du « plancher de verification » de l'AC 7, tels que l'AC les nomme:
#: pas de grille a 3 mm et ecart pastilles/bande a 2 mm. Ils sont poses sur la **v1**,
#: c'est-a-dire sur la geometrie d'avant la passe, et rien d'autre n'y est change.
_PLANCHER_LEVIERS = {
    "ecart": {"patch_to_band_gap_mm": {PORTRAIT: 2.0, PAYSAGE: 2.0}},
    "pas": {"frame_grid_gap_mm": page_templates.FRAME_GRID_GAP_V2_MM},
}


def _plancher_geometry(*leviers: str):
    """Geometrie v1 avec les leviers nommes, et **rien d'autre**."""
    import types

    changes: dict = {}
    for levier in leviers:
        for field, value in _PLANCHER_LEVIERS[levier].items():
            changes[field] = (types.MappingProxyType(value)
                              if isinstance(value, dict) else value)
    return dataclasses.replace(page_templates.GEOMETRY_V1, **changes)


def test_the_two_model_free_levers_are_computed_not_cited() -> None:
    """**Verrou du bloquant B2**: le plancher de verification se CALCULE.

    L'AC 7 posait six litteraux (« +7,8 % (2f), +16,9 % (3f), +15,1 % (4f), +13,4 % (6f),
    +27,4 % (8f) et +0,0 % (1f) ») et en faisait son critere de falsification: « si
    l'implementation ne retrouve pas ces six chiffres, le defaut est dans
    l'implementation ». **Quatre des six ne se reproduisent pas**, et l'argument decisif
    ne depend d'aucune convention: au cardinal 1 il n'y a aucun ecart **inter-frames**,
    donc le pas de grille ne peut rien y changer -- annoncer +0,0 % au 1f nie donc le
    second levier que la meme phrase revendique.

    Le plancher est donc **retire et remplace par ce test**, qui asserte le **signe** et
    l'**ordre** au lieu de six litteraux. Un plancher calcule ne peut pas deriver de ce
    que la production rend; six litteraux, si.

    **Regime nomme, parce qu'un chiffre sans son regime n'est pas une mesure** (lecon des
    revues de 5.17 et de 5.18, quatre fois): retrait isole depuis la **v1 nue**, couple par
    couple (orientation, cardinal) du vocabulaire v1 -- les onze, pas une « meilleure
    orientation » qui cacherait une orientation derriere l'autre --, chaque levier seul
    puis les deux ensemble.
    """
    v1 = page_templates.GEOMETRY_V1
    ecart = _plancher_geometry("ecart")
    pas = _plancher_geometry("pas")
    deux = _plancher_geometry("ecart", "pas")
    # Les deux leviers sont bien ceux que l'AC nomme, et **eux seuls**: une geometrie de
    # reference qui aurait bouge un troisieme champ ne mesurerait plus le plancher.
    for variante in (ecart, pas, deux):
        for field in dataclasses.fields(page_templates.PageGeometry):
            touche = field.name in {"patch_to_band_gap_mm", "frame_grid_gap_mm"}
            egal = getattr(variante, field.name) == getattr(v1, field.name)
            assert egal or touche, field.name
    couples = sorted(GABARITS_V1)
    assert len(couples) == 11, couples
    gains: dict[tuple[str, int], dict[str, float]] = {}
    for orientation, cardinal in couples:
        base = _drawing_area(v1, orientation, cardinal)
        gains[(orientation, cardinal)] = {
            nom: _drawing_area(variante, orientation, cardinal) / base - 1
            for nom, variante in (("ecart", ecart), ("pas", pas), ("deux", deux))
        }
    # --- SIGNE: aucun des deux leviers ne coute de la surface, nulle part -------------
    for couple, mesure in gains.items():
        for nom, gain in mesure.items():
            assert gain >= -1e-9, (couple, nom, gain)
        # Et le couple ne detruit pas ce que chaque levier rend seul.
        assert mesure["deux"] >= max(mesure["ecart"], mesure["pas"]) - 1e-9, couple
    # Le plancher est un plancher: les deux leviers ensemble rendent strictement de la
    # surface sur la majorite des couples.
    strictement = [c for c, m in gains.items() if m["deux"] > 1e-9]
    assert len(strictement) * 2 > len(couples), strictement
    # --- ATTRIBUTION au cardinal 1: le fait qui ne depend d'aucune convention ---------
    #
    # Une zone unique n'a **aucun** ecart inter-frames, donc le pas de grille ne peut rien
    # y changer -- exactement l'argument qui a fait retirer le plancher. Mesure a
    # l'egalite exacte, pas a une tolerance: c'est une identite, pas une approximation.
    for orientation in page_templates.ORIENTATIONS:
        assert _drawing_area(pas, orientation, 1) == _drawing_area(v1, orientation, 1)
        assert (_drawing_area(deux, orientation, 1)
                == _drawing_area(ecart, orientation, 1))
        assert gains[(orientation, 1)]["pas"] == 0.0, orientation
    # --- ORDRE: le pas de grille rend d'autant plus que la grille est dense -----------
    #
    # Dans chaque orientation, le cardinal le plus dense gagne **strictement** le plus.
    # C'est la forme de l'ordre, et elle est vraie dans les deux orientations.
    for orientation in page_templates.ORIENTATIONS:
        par_cardinal = {c: gains[(o, c)]["deux"]
                        for (o, c) in couples if o == orientation}
        dense = max(par_cardinal)
        assert par_cardinal[dense] == max(par_cardinal.values()), orientation
        for cardinal, gain in par_cardinal.items():
            assert cardinal == dense or gain < par_cardinal[dense] - 1e-9, (
                orientation, cardinal)
    # --- Et l'ensemble des couples que le PAS de grille laisse froids, calcule --------
    #
    # C'est le contenu falsifiable que les six litteraux voulaient porter, et il tient
    # dans un ensemble plutot que dans des pourcentages: le pas de grille ne rend rien
    # exactement la ou la grille n'a pas d'ecart dans la direction qu'il ouvre. Deux
    # familles, et la seconde est celle que la story avait manquee:
    #
    # * les cardinaux 1 -- une seule cellule, aucun ecart inter-frames;
    # * `portrait 2f` -- 1 colonne x 2 rangees, mais la bande est bornee en **largeur**
    #   (cellule 140 x 78,75, soit 16:9), donc les 5 mm que le pas vertical rend restent
    #   du mou et ne deviennent pas de la surface. C'est pour cela que la phrase « tout
    #   cardinal a plusieurs rangees gagne strictement plus que le cardinal 1 » est
    #   fausse: en portrait, 2f gagne exactement autant que 1f.
    inertes = {c for c, m in gains.items() if m["pas"] == 0.0}
    assert inertes == {(PORTRAIT, 1), (PAYSAGE, 1), (PORTRAIT, 2)}, inertes


#: Candidats construits pour exercer la regle de departage, **dans le desordre**: la
#: cible est en troisieme position, jamais en premiere. Un `find` fautif qui rendrait le
#: premier element ne se demasque pas autrement (regle des fabriques du depot, defauts
#: `M25` et `M33`, quatre fois rencontres ici).
#:
#: Les quatre premiers candidats ont **la meme surface** a 1/100 de mm2: c'est le regime
#: de 6f et 8f, bornes en largeur, ou le bord porteur ne change rien. Le cinquieme est
#: strictement meilleur et doit gagner malgre sa derniere position.
def _tie_candidates(area_mm2: float, heights: dict) -> tuple:
    return tuple(
        (edge, placement, {"x": 0.0, "y": 0.0,
                           "width": area_mm2 / height, "height": height})
        for edge, placement, height in heights
    )


def test_the_tie_break_rule_is_written_and_exercised_on_a_built_tie() -> None:
    """**La regle de departage, exercee sur une egalite construite** (AC 3).

    6f et 8f sont bornes en largeur: leur surface est identique au bord haut et au bord
    bas, et le banc de recherche rapportait `haut` pour 6f **par simple ordre de
    boucle**. Une egalite se departage par une regle ecrite, et cette regle doit etre
    testee la ou l'egalite existe -- donc sur des candidats construits, puisqu'aucun
    gabarit livre n'a d'egalite parfaite entre deux bords de meme hauteur de bande.

    Les trois criteres sont exerces separement: la surface, puis la hauteur de bande a
    surface egale, puis l'ordre des bords a hauteur egale.
    """
    geometry = page_templates.GEOMETRY_V2
    key = geometry._ranking_key
    sides = page_templates.WITNESS_PLACEMENT_SIDES
    borders = page_templates.WITNESS_PLACEMENT_BORDERS
    band = {"x": 0.0, "y": 0.0, "width": 100.0, "height": 50.0}
    taller = {"x": 0.0, "y": 0.0, "width": 100.0, "height": 60.0}

    # (0) **L'ordre est epingle en litteral, pas relu depuis la constante.** Survivant
    # `C04` de la campagne: permuter `bas` et `haut` dans `QR_EDGES` ne fait echouer aucun
    # test qui derive son attendu de cette meme constante -- l'assertion devient
    # tautologique. Et aucun gabarit livre ne l'exerce: les egalites bas/haut se
    # departagent sur la hauteur de bande, un cran plus haut. L'ordre est un **choix
    # ecrit**, il s'epingle donc comme une valeur, avec sa raison.
    assert page_templates.QR_EDGES == ("bas", "haut", "gauche", "droit")
    assert page_templates.QR_EDGES[0] == page_templates.QR_EDGE_BOTTOM, (
        "le bord bas vient en tete parce qu'il est celui que le pied de page paie deja: "
        "un choix par defaut doit etre le moins cher, pas le premier qui vient")

    # (1) La surface passe avant tout: une bande plus haute mais moins dessinante perd.
    assert key(page_templates.QR_EDGE_TOP, sides, taller, 100.0) > key(
        page_templates.QR_EDGE_LEFT, borders, band, 200.0)
    # (2) A surface egale, la bande la plus haute gagne -- quel que soit le bord.
    assert key(page_templates.QR_EDGE_LEFT, sides, taller, 100.0) < key(
        page_templates.QR_EDGE_BOTTOM, sides, band, 100.0)
    # (3) A surface **et** hauteur egales, l'ordre `bas, haut, gauche, droit` tranche,
    # puis les cotes avant les rangees haut/bas. Les clefs doivent etre **strictement**
    # croissantes, et pas seulement non decroissantes: c'est ce que le survivant `C08` de
    # la campagne a montre. Un critere de bord retire de la clef rend les quatre bords
    # **egaux**, et la selection retombe alors sur l'ordre d'iteration des candidats --
    # qui se trouve etre le meme ordre, donc le verdict ne bouge pas. C'est exactement le
    # defaut que l'AC 3 nomme (« le banc a rapporte `haut` pour 6f par simple ordre de
    # boucle »): la regle doit etre l'arbitre, jamais la boucle, et une comparaison non
    # stricte ne distingue pas les deux.
    ordered = [key(edge, sides, band, 100.0) for edge in page_templates.QR_EDGES]
    assert ordered == sorted(ordered)
    for lower, higher in zip(ordered, ordered[1:]):
        assert lower < higher, (
            "deux bords rendent la meme clef de tri: leur depart se joue alors sur "
            "l'ordre d'iteration des candidats et non sur la regle ecrite")
    assert len(set(ordered)) == len(page_templates.QR_EDGES)
    assert key(page_templates.QR_EDGE_BOTTOM, sides, band, 100.0) < key(
        page_templates.QR_EDGE_BOTTOM, borders, band, 100.0)
    # (4) Les deux arrondis sont ce qui **fait exister** l'egalite: deux surfaces
    # distantes de 1e-13 doivent se departager par la hauteur, et deux hauteurs distantes
    # de 1e-9 par l'ordre des bords -- jamais par le dernier chiffre binaire. Les deux
    # cotes d'une page sont symetriques, donc leurs bandes sortent de divisions
    # differentes et se retrouvent a 1e-13 l'une de l'autre: sans arrondi, c'est ce bruit
    # qui trancherait (survivant `C06`).
    assert key(page_templates.QR_EDGE_BOTTOM, sides, band, 100.0) == key(
        page_templates.QR_EDGE_BOTTOM, sides, band, 100.0 + 1e-13)
    assert key(page_templates.QR_EDGE_TOP, sides, taller, 100.0) < key(
        page_templates.QR_EDGE_BOTTOM, sides, band, 100.0 + 1e-13)
    jittered = dict(band, height=band["height"] + 1e-9)
    assert key(page_templates.QR_EDGE_LEFT, sides, jittered, 100.0) == key(
        page_templates.QR_EDGE_LEFT, sides, band, 100.0)
    # ... et c'est bien l'ordre des bords qui tranche alors, pas le bruit: le bord le plus
    # haut dans l'ordre gagne meme si sa bande est infinitesimalement plus basse.
    assert key(page_templates.QR_EDGE_BOTTOM, sides, band, 100.0) < key(
        page_templates.QR_EDGE_TOP, sides, jittered, 100.0)

    # (5) Et le vainqueur d'une liste **desordonnee** est bien celui que la regle
    # designe, la cible n'etant ni en premiere ni en derniere position.
    candidates = (
        (page_templates.QR_EDGE_LEFT, sides, dict(band)),
        (page_templates.QR_EDGE_TOP, borders, dict(band)),
        (page_templates.QR_EDGE_BOTTOM, sides, dict(taller)),   # <- la cible
        (page_templates.QR_EDGE_RIGHT, sides, dict(band)),
    )
    ranked = sorted(candidates, key=lambda item: key(item[0], item[1], item[2], 100.0))
    assert ranked[0] == candidates[2]


def test_an_unknown_qr_edge_is_refused_naming_the_vocabulary() -> None:
    """Vocabulaire ferme, comme partout ailleurs dans le registre (AC 3).

    Survivant `B09` de la campagne: la garde n'est atteignable par aucun appelant du depot
    -- les bords viennent tous de `QR_EDGES` -- donc rien ne la regardait. Elle protege
    d'un appel a la main (un banc de recherche, une session de diagnostic) et surtout
    d'une faute de frappe dans une future version de geometrie: un bord inconnu tomberait
    sinon dans la branche `else`, celle du flanc **droit**, et rendrait une bande d'appa-
    rence normale pour un bord que personne n'a demande.
    """
    geometry = page_templates.GEOMETRY_V2
    for unknown in ("diagonal", "top", "BAS", "", "gauche-droit"):
        with pytest.raises(page_templates.UnknownTemplateError, match="Bord porteur"):
            geometry.band_edges_mm(PORTRAIT, unknown)
        with pytest.raises(page_templates.UnknownTemplateError):
            geometry.frame_band_candidates(PORTRAIT, unknown)
    # Et le refus nomme le vocabulaire, pour que l'appelant sache quoi ecrire.
    with pytest.raises(page_templates.UnknownTemplateError) as refus:
        geometry.band_edges_mm(PAYSAGE, "diagonal")
    for edge in page_templates.QR_EDGES:
        assert edge in str(refus.value)
    # Les quatre bords connus, eux, passent: sans quoi la garde serait trop large.
    for edge in page_templates.QR_EDGES:
        assert set(geometry.band_edges_mm(PORTRAIT, edge)) == {
            "top", "bottom", "left", "right"}


def test_reading_the_qr_edge_of_a_geometry_that_fixes_it_never_compares() -> None:
    """La v1 garde son QR au bord haut **sans exception**, et c'est necessaire (AC 1).

    Sous la v1 le degagement de coin (60 mm) domine l'exigence du QR (49,6): le haut et
    le bas y rendent donc la **meme** surface, et une comparaison y trancherait par sa
    regle de departage -- qui prefere le bas. Une planche v1 deja imprimee verrait alors
    son QR change de bord a la recomposition, sans qu'aucune etape n'echoue.
    """
    v1 = page_templates.GEOMETRY_V1
    assert v1.qr_bearing_edge == page_templates.QR_EDGE_TOP
    assert v1.qr_edge_candidates() == (page_templates.QR_EDGE_TOP,)
    for orientation in page_templates.ORIENTATIONS:
        assert v1.qr_edge(orientation) == page_templates.QR_EDGE_TOP
        assert v1.qr_edge(orientation, 2) == page_templates.QR_EDGE_TOP
        # Et l'egalite est reelle: c'est bien la regle de departage qui aurait tranche.
        top = _drawing_area(v1, orientation, 2, dict(v1.frame_band_candidates(
            orientation, page_templates.QR_EDGE_TOP))[
                page_templates.WITNESS_PLACEMENT_SIDES])
        bottom = _drawing_area(v1, orientation, 2, dict(v1.frame_band_candidates(
            orientation, page_templates.QR_EDGE_BOTTOM))[
                page_templates.WITNESS_PLACEMENT_SIDES])
        assert top == pytest.approx(bottom), orientation
    for template_id in page_templates.known_template_ids():
        spec = page_templates.get_template(template_id)
        if spec.geometry_version == "v1":
            assert spec.qr_edge == page_templates.QR_EDGE_TOP, template_id


@pytest.mark.parametrize("font_pt", [8.0, 10.0, 12.0, 14.0, 18.0])
def test_the_identity_header_costs_no_drawing_area_up_to_18_pt(font_pt) -> None:
    """**« Cela ne coute RIEN », rendu falsifiable** (AC 4).

    C'est ce test qui fait la difference entre une mesure et une affirmation: il balaye le
    corps de police de l'entete de 8 a 18 pt et exige que **aucune** zone de dessin ne
    bouge, sur les neuf gabarits de la v2. Sans lui, « l'entete est gratuit » est une
    phrase.

    Cause, mesuree: le bord haut n'est jamais borne par l'entete. Il est borne soit par
    le degagement de coin (28 mm), soit par le QR (49,6 mm) quand celui-ci y va, et une
    pile de deux lignes reste sous le premier des deux jusqu'a bien plus de 18 pt --
    23,52 mm a 18 pt. La tension qu'`EPIC5-ARB-63` posait n'existe pas dans ce domaine.
    """
    reference = {
        (orientation, cardinal): _drawing_area(
            page_templates.GEOMETRY_V2, orientation, cardinal)
        for orientation, cardinal in GABARITS_V2
    }
    monkey = pytest.MonkeyPatch()
    try:
        monkey.setattr(page_templates, "HEADER_IDENTITY_FONT_PT", font_pt)
        # La pile exigee grandit bien avec le corps -- sinon le balayage ne balaye rien.
        stack = page_templates.GEOMETRY_V2.header_identity_clearance_mm()
        assert stack == pytest.approx(
            5.0 + 2 * (font_pt * 0.42 + 1.2) + page_templates.TOP_BAND_GUARD_MM)
        assert stack <= page_templates.GEOMETRY_V2.corner_clearance_mm()
        for (orientation, cardinal), area in reference.items():
            assert _drawing_area(
                page_templates.GEOMETRY_V2, orientation, cardinal) == pytest.approx(
                    area, abs=1e-9), (orientation, cardinal, font_pt)
    finally:
        monkey.undo()


def test_the_header_height_is_derived_from_the_font_never_a_literal() -> None:
    """La hauteur d'entete est **derivee**, jamais un litteral (AC 4).

    Deux dependances, verifiees separement: le corps de police et le nombre de lignes.
    Une hauteur qui ne dependrait que de l'une des deux passerait un test qui ne varie
    que l'autre -- c'est le meme motif que le test anti-facade du pied de page.
    """
    geometry = page_templates.GEOMETRY_V2
    monkey = pytest.MonkeyPatch()
    try:
        reference = geometry.header_identity_clearance_mm()
        monkey.setattr(page_templates, "HEADER_IDENTITY_FONT_PT", 20.0)
        bigger_font = geometry.header_identity_clearance_mm()
        monkey.undo()
        monkey.setattr(page_templates, "HEADER_IDENTITY_LINE_COUNT", 3)
        more_lines = geometry.header_identity_clearance_mm()
    finally:
        monkey.undo()
    assert bigger_font > reference
    assert more_lines > reference
    # Et la derivation est exactement celle du rendu: deux lignes a l'interligne du
    # corps, plus la marge d'encre et la garde de bande.
    assert reference == pytest.approx(
        page_templates.GEOMETRY_V2.printer_margin_mm
        + page_templates.HEADER_IDENTITY_LINE_COUNT
        * pdf_composition.line_leading_mm(page_templates.HEADER_IDENTITY_FONT_PT)
        + page_templates.TOP_BAND_GUARD_MM)
    # L'interligne du miroir est **affine**, jamais proportionnel: la distinction ne se
    # voit qu'hors du corps nominal, et le banc de la passe s'y est trompe de 0,90 mm par
    # ligne a 14 pt.
    assert page_templates.body_line_leading_mm(14.0) == pytest.approx(7.08)
    assert page_templates.body_line_leading_mm(14.0) != pytest.approx(
        page_templates.body_line_leading_mm(8.0) * 14.0 / 8.0)


def test_the_header_identity_carries_the_lot_name_and_the_pagination() -> None:
    """Ce que l'entete porte, et a quel corps (AC 4, `EPIC5-ARB-63`).

    « Le nom du lot (rushes / cadence / version) et les numerotations de page doivent
    rester tres lisibles, en entete de page, avec une police plus grosse. » Le test
    verifie les trois: le contenu des deux lignes, le corps, et le fait que le pied ne
    porte plus ces lignes-la.
    """
    manifest, lot_id = _composition_manifest()
    plan = pdf_composition.compose_lot_plan(
        manifest=manifest, lot_id=lot_id, orientation=PORTRAIT, frames_per_page=2)
    page = _images_pages(plan)[0]
    blocks = {block.name: block for block in page.text.blocks}
    header = blocks["header_identity"]
    assert header.font_pt == page_templates.HEADER_IDENTITY_FONT_PT
    assert header.font_pt > pdf_composition.BODY_FONT_MIN_PT
    assert len(header.lines) == page_templates.HEADER_IDENTITY_LINE_COUNT
    # Ligne 1: le nom du lot, verbatim -- il porte le rush et la cadence.
    assert header.lines[0] == lot_id
    # Ligne 2: la pagination et la cadence.
    assert page.text.page_number_text in header.lines[1]
    assert page.text.fps_display in header.lines[1]
    # Le pied ne porte plus ces deux lignes: il ne garde que les identifiants residuels.
    footer = blocks["footer_block"]
    assert footer.lines == (plan.project_id, plan.rush_id)
    assert lot_id not in "\n".join(footer.lines)
    assert page.text.page_number_text not in "\n".join(footer.lines)
    # Et les anciennes zones d'en-tete ont disparu au profit de l'entete d'identite: une
    # planche qui porterait les deux aurait deux fois la meme information a deux corps.
    assert "header_left" not in blocks and "header_right" not in blocks


def test_the_footer_layout_is_the_same_for_every_cardinal() -> None:
    """**Une seule mise en page de pied, uniforme** (AC 5), et la frontiere negative.

    Le balayage retenait d'abord trois mises en page differentes selon le cardinal, ce qui
    serait etrange sur papier: la meme information disposee autrement selon le nombre de
    frames. La mesure a montre que la plus legere rend, cardinal par cardinal, exactement
    la meme surface que l'optimum par cardinal.

    Le test est donc un **test de frontiere negatif**: ni le nombre de lignes du pied, ni
    le nombre de colonnes, ni le nombre de lignes techniques posees ne doivent dependre
    du cardinal. Seule la **largeur** des zones en depend, et par une seule cause nommee:
    le bord porteur du QR, qui retrecit le pied quand il prend le bord bas.
    """
    manifest, lot_id = _composition_manifest()
    shapes = {}
    for orientation, cardinal in GABARITS_V2:
        plan = pdf_composition.compose_lot_plan(
            manifest=manifest, lot_id=lot_id, orientation=orientation,
            frames_per_page=cardinal)
        page = _images_pages(plan)[0]
        blocks = {block.name: block for block in page.text.blocks}
        technical = [name for name in page_templates.FOOTER_TECHNICAL_ZONE_NAMES
                     if name in blocks]
        shapes[(orientation, cardinal)] = (
            tuple(sorted(blocks)),
            len(blocks["footer_block"].lines),
            len(technical),
            page.text.date_line_slot,
            tuple(rect[3] for rect in (blocks[name].rect_mm for name in technical)),
        )
    # La **forme** du pied est la meme pour tous les cardinaux, dans les deux
    # orientations: memes zones, meme nombre de lignes d'identite, meme nombre de
    # colonnes, meme place de la date, memes hauteurs.
    assert len(set(shapes.values())) == 1, shapes
    # Seule la **largeur** depend du cardinal, et par une cause unique et nommee: le
    # bord porteur du QR, qui retrecit le pied quand il prend le bord bas. Deux largeurs
    # au total, pas une par cardinal.
    widths = {}
    for orientation, cardinal in GABARITS_V2:
        spec = page_templates.template_for(orientation, cardinal, "0", "v2")
        zones = page_templates.footer_zones_mm(spec)
        widths.setdefault(orientation, {}).setdefault(
            spec.qr_edge, set()).add(round(zones["footer_block"][2], 6))
    for orientation, per_edge in widths.items():
        for edge, distinct in per_edge.items():
            assert len(distinct) == 1, (orientation, edge, distinct)
        full = page_templates.page_size_mm(orientation)[0] - 2 * (
            page_templates.GEOMETRY_V2.corner_clearance_mm())
        for edge, distinct in per_edge.items():
            width = next(iter(distinct))
            if edge == page_templates.QR_EDGE_BOTTOM:
                assert width == pytest.approx(
                    full - page_templates.qr_footprint_bound_mm()
                    - page_templates.TEXT_GAP_MM)
            else:
                assert width == pytest.approx(full)
    # **Le contenu technique ne depend pas du cardinal non plus** (frontiere negative de
    # l'AC 5). Ce bloc comparait autrefois le pied de la v2 a celui de la **v1**, ce qui
    # etait une facon de dire « aucune mention n'a disparu » sans reecrire la liste.
    # Depuis la story 11.4b (AC 6, `EPIC11-ARB-87`) les deux pieds divergent
    # **volontairement** -- la v2 porte dix mentions, la v1 gele les six d'origine --,
    # donc l'egalite ne veut plus rien dire. Ce qui se mesure ici est ce que le bloc
    # mesurait vraiment: la **meme** liste de mentions pour tous les cardinaux, dans les
    # deux orientations, cardinal par cardinal.
    #
    # C'est une egalite entre deux compositions **reelles**, jamais une liste reecrite a
    # la main: reecrire le pied dans l'attendu en ferait une seconde redaction du meme
    # contenu, et un test qui deriverait son attendu de la fonction testee ne mesurerait
    # rien du tout. Ce que la divergence v1/v2 doit valoir, elle, se mesure a part et
    # **exactement** (`test_le_pied_gele_de_la_v1_diverge_exactement_des_quatre_ajouts`).
    mentions_par_cardinal = {}
    for orientation, cardinal in GABARITS_V2:
        derived = pdf_composition.compose_lot_plan(
            manifest=manifest, lot_id=lot_id, orientation=orientation,
            frames_per_page=cardinal)
        blocks = {block.name: block for block in _images_pages(derived)[0].text.blocks}
        technical_lines = [
            line for name in page_templates.FOOTER_TECHNICAL_ZONE_NAMES
            if name in blocks for line in blocks[name].lines
        ]
        mentions = sorted(part for line in technical_lines
                          for part in line.split(" - "))
        # **Deux** mentions dependent du cardinal par construction, et ce sont les deux
        # seules qui en aient le droit: le `template_id`, qui porte le cardinal dans son
        # nom (`...-2f-...`), et le cardinal de planches, qui est `ceil(frames /
        # emplacements)`. Les neutraliser est ce qui rend la comparaison possible, et les
        # confronter separement est ce qui empeche de les neutraliser trop largement --
        # une pagination glissee au pied, par exemple, se verrait ici.
        cle_gabarit = pdf_composition.PIED_CLES_COURTES["template_id"]
        cle_planches = pdf_composition.PIED_CLES_COURTES["page_count"]
        variables = tuple(m for m in mentions
                          if m.startswith((f"{cle_gabarit}=", f"{cle_planches}=")))
        assert len(variables) == 2, mentions
        par_cle = {m.split("=", 1)[0]: m.split("=", 1)[1] for m in variables}
        assert par_cle[cle_planches] == str(-(-FRAMES_DU_MANIFESTE // cardinal)), (
            orientation, cardinal, variables)
        assert f"-{cardinal}f-" in par_cle[cle_gabarit], (
            orientation, cardinal, variables)
        fixes = tuple(m for m in mentions if m not in variables)
        mentions_par_cardinal.setdefault(orientation, {})[cardinal] = fixes
        # Et aucune mention n'est perdue en route: le pied compte la provenance, les
        # huit couples `cle=valeur` et la consigne de scan.
        assert len(mentions) == len(pdf_composition.PIED_CLES_COURTES) + 2, (
            orientation, cardinal, mentions)
        # **Le pied est le meme sur TOUTES les planches du lot**, `np=` compris: c'est
        # un cardinal de lot et non un rang de page. Un `np=` qui se mettrait a compter
        # les pages ferait diverger la derniere planche de la premiere.
        pieds = set()
        for page in _images_pages(derived):
            par_page = {b.name: b for b in page.text.blocks}
            pieds.add(tuple(
                line for name in page_templates.FOOTER_TECHNICAL_ZONE_NAMES
                if name in par_page for line in par_page[name].lines))
        assert len(_images_pages(derived)) >= 2, cardinal
        assert len(pieds) == 1, (orientation, cardinal, pieds)
    for orientation, par_cardinal in mentions_par_cardinal.items():
        assert len(set(par_cardinal.values())) == 1, (orientation, par_cardinal)


def _empreinte_de_dessin(plan) -> tuple:
    """Tout ce qu'un scan reconstruit d'une planche, sous forme comparable.

    Les marqueurs de coin **et** ce que leur homographie encadre: zones de frames,
    pastilles, emprise du QR, et les rectangles de toutes les zones de texte. Le
    contenu textuel n'y entre pas -- c'est precisement ce qui a le droit de changer.
    """
    return tuple(
        (
            tuple((m.marker_id, m.center_x_mm, m.center_y_mm, m.size_mm)
                  for m in page.markers),
            tuple(slot.zone_rect_mm for slot in page.frames),
            tuple((p.value_id, p.x_mm, p.y_mm, p.size_mm) for p in page.patches),
            page.qr.footprint_rect_mm,
            page.qr.print_size_mm,
            tuple(sorted(page.text.zones_mm.items())),
            tuple((b.name, b.rect_mm, b.font_pt) for b in page.text.blocks),
        )
        for page in _images_pages(plan)
    )


def test_le_pied_technique_ne_peut_deplacer_aucune_zone_de_dessin(monkeypatch) -> None:
    """**L'assurance donnee a Egan, mesuree** (AC 6.2, story 11.4b).

    Egan a autorise a revoir la mise en page des informations du pied, **jamais** a
    reduire les zones de dessin: la geometrie que le scan deduit des marqueurs en
    depend, et une planche dont le cadre bouge d'un millimetre est une planche dont
    toutes les frames sortent decalees, sans qu'aucune etape n'echoue.

    Le contrat du module le dit deja -- « une combinaison qui ne tient pas
    geometriquement est **refusee**, jamais reduite en silence » --, mais rien ne le
    mesurait sur le **contenu du pied**. Ce banc charge le pied jusqu'au refus et
    verifie qu'a chaque cran, l'empreinte de dessin est identique **a l'octet**:
    memes marqueurs, memes zones de frames, memes pastilles, meme emprise de QR,
    memes rectangles de zones et de blocs. La seule issue est le refus.

    Le pied se charge en enveloppant `_pack_lines`, donc tout le reste du chemin est
    celui de la production: largeur de colonne, repartition, garde de tenue
    verticale.
    """
    manifest, lot_id = _composition_manifest()
    reference = _empreinte_de_dessin(pdf_composition.compose_lot_plan(
        manifest=manifest, lot_id=lot_id, orientation=PORTRAIT, frames_per_page=2))
    real_pack = pdf_composition._pack_lines
    extras: list[str] = []

    def packed_with_extras(parts, width_mm, font_pt, separator=" - "):
        return real_pack(list(parts) + extras, width_mm, font_pt, separator)

    monkeypatch.setattr(pdf_composition, "_pack_lines", packed_with_extras)
    refuse = None
    for count in range(0, 12):
        extras[:] = [f"diagnostic{index}=xxxxxxxxxxxxxxxxxxxx" for index in range(count)]
        try:
            charge = pdf_composition.compose_lot_plan(
                manifest=manifest, lot_id=lot_id, orientation=PORTRAIT,
                frames_per_page=2)
        except pdf_composition.GeometryOverflowError:
            refuse = count
            break
        assert _empreinte_de_dessin(charge) == reference, count
    monkeypatch.undo()
    # Le refus arrive, et il arrive **avant** la fin de la boucle: un pied qu'on peut
    # charger indefiniment sans refus serait un pied qui rogne quelque part.
    assert refuse is not None and refuse > 0, refuse
    # Et le volet symetrique, sans lequel ce banc serait vrai pour un module qui ne
    # composerait rien: allege du pied, l'empreinte est la meme aussi. Ce qui bouge
    # avec le contenu du pied, ce sont les **lignes**, jamais les rectangles.
    gele = pdf_composition.compose_lot_plan(
        manifest=manifest, lot_id=lot_id, orientation=PORTRAIT, frames_per_page=2,
        geometry_version="v1")
    lignes_v1 = {b.name: b.lines for b in _images_pages(gele)[0].text.blocks}
    lignes_v2 = {b.name: b.lines
                 for b in _images_pages(pdf_composition.compose_lot_plan(
                     manifest=manifest, lot_id=lot_id, orientation=PORTRAIT,
                     frames_per_page=2))[0].text.blocks}
    assert lignes_v1 != lignes_v2


@pytest.mark.parametrize("orientation,cardinal", GABARITS_V2)
def test_the_row_gap_hosts_the_slot_label_of_the_row_above(orientation, cardinal):
    """**Ce que le pas de grille protege, mesure a l'execution** (AC 8).

    Aucune justification n'etait documentee pour les 10 mm historiques (« celui du
    template historique »), donc 3 mm ne devait pas en avoir davantage. La recherche a
    trouve une contrainte, et elle est **verticale**: le plan pose sous chaque zone une
    etiquette d'emplacement de `SLOT_LABEL_STRIP_MM` de haut, **hors** de la zone. Le
    degagement du bord bas loge celle de la derniere rangee; entre deux rangees, il n'y a
    que le pas de grille pour la loger.

    Pose a 3 mm, le pas faisait donc atterrir l'etiquette d'une rangee **dans la zone de
    dessin de la suivante** -- 66 combinaisons du test global de non-chevauchement de la
    story 5.15. Le pas vertical vaut donc au moins la bande d'etiquette, et il la vaut
    par derivation de la constante qui la nomme.
    """
    spec = page_templates.template_for(orientation, cardinal, "0", "v2")
    geometry = spec.geometry
    assert geometry.frame_grid_row_gap_mm() == pytest.approx(
        page_templates.SLOT_LABEL_STRIP_MM)
    assert geometry.frame_grid_row_gap_mm() > geometry.frame_grid_gap_mm
    zones = spec.frame_zones_mm
    for index, zone in enumerate(zones):
        label = (zone["x"], zone["y"] + zone["height"] + pdf_composition._SLOT_LABEL_OFFSET_MM,
                 zone["width"], pdf_composition._SLOT_LABEL_HEIGHT_MM)
        for other in zones[index + 1:]:
            other_rect = (other["x"], other["y"], other["width"], other["height"])
            assert not rects_overlap(label, other_rect), (spec.template_id, index)
        # L'etiquette est **tangente** a la rangee suivante, jamais chevauchante: le
        # rendu pose la ligne de base a 0,5 mm du bas de la bande, donc l'encre s'arrete
        # 0,5 mm au-dessus de la frontiere.
        below = [other for other in zones
                 if other["y"] > zone["y"] + zone["height"] - 1e-9
                 and abs(other["x"] - zone["x"]) < 1e-9]
        if below:
            nearest = min(below, key=lambda item: item["y"])
            assert nearest["y"] == pytest.approx(label[1] + label[3], abs=1e-9)


def test_the_bottom_extra_clearance_is_inert_at_its_delivered_value() -> None:
    """**`bottom_extra_clearance_mm` est inerte a sa valeur livree, et il fonctionne.**

    Trouve trois fois independamment par la revue de 5.18 (M2 de la couche 1, F5 des
    constats, implique par le M-4 de la couche 2), et le commentaire du champ affirmait
    l'inverse: qu'il est « la borne du bord bas des que le QR n'y est pas », et que cela
    coute « 6,4 % sur le seul cardinal qui envoie le QR sur un flanc ». Le mecanisme est
    arithmetique -- le `max` du bord bas a trois termes et `bottom_text_clearance_mm()`
    (45,36 mm) domine `coin + extra` (37,5 en portrait, 30,0 en paysage) dans les **deux**
    orientations -- donc le retirer entierement ne rend pas un millimetre carre, et la
    decomposition qui lui attribuait -8,6 % du 3f etait impossible.

    **Le test a deux volets, et le second est indispensable.** Sans lui il passerait aussi
    si le champ etait purement **ignore** par la production, ce qui est un tout autre
    defaut: un champ ignore se retire, un champ domine se documente ou s'asserte. Le
    mutant `Z01` de la campagne de la couche 1 (« supplement ramene a zero dans les deux
    orientations ») survivait faute de ce test.
    """
    import types

    livre = page_templates.GEOMETRY_V2
    reference = {(o, c): _drawing_area(livre, o, c) for o, c in GABARITS_V2}

    def variante(valeur: float):
        return dataclasses.replace(
            livre,
            bottom_extra_clearance_mm=types.MappingProxyType(
                {PORTRAIT: valeur, PAYSAGE: valeur}),
        )

    # --- Volet 1: a sa valeur livree, le champ ne change AUCUNE surface --------------
    #
    # Mesure a l'egalite exacte contre 0,0: c'est une identite (le terme est domine dans
    # le `max`), pas une approximation.
    assert livre.bottom_extra_clearance_mm[PORTRAIT] > 0.0
    assert livre.bottom_extra_clearance_mm[PAYSAGE] > 0.0
    nul = variante(0.0)
    for orientation, cardinal in GABARITS_V2:
        assert _drawing_area(nul, orientation, cardinal) == reference[
            (orientation, cardinal)], (orientation, cardinal)
    # Et la cause est nommee, pas seulement constatee: le pied de page domine
    # `coin + extra` dans les deux orientations.
    for orientation in page_templates.ORIENTATIONS:
        assert (livre.corner_clearance_mm()
                + livre.bottom_extra_clearance_mm[orientation]
                < livre.bottom_text_clearance_mm()), orientation
    # --- Volet 2: le champ FONCTIONNE -- a 20 mm il mord ------------------------------
    #
    # Sans ce volet, le volet 1 passerait aussi si la production ignorait le champ.
    mordant = variante(20.0)
    mord = {(o, c) for o, c in GABARITS_V2
            if _drawing_area(mordant, o, c) < reference[(o, c)] - 1e-9}
    assert mord, "le champ serait purement ignore par la production"
    # Ce sont les gabarits dont le bord bas n'est masque ni par l'emprise du QR ni par le
    # pied: les deux qui envoient le QR sur un flanc. Ecrit en ensemble plutot qu'en
    # pourcentages, pour la meme raison que le plancher de l'AC 7 a ete retire.
    assert mord == {(PORTRAIT, 3), (PORTRAIT, 4)}, mord
    # Et la dose fait l'effet: a 40 mm il mord plus largement encore.
    large = {(o, c) for o, c in GABARITS_V2
             if _drawing_area(variante(40.0), o, c) < reference[(o, c)] - 1e-9}
    assert mord < large, (mord, large)


def test_the_qr_footprint_bound_takes_the_floor_branch_when_the_domain_moves() -> None:
    """**La branche « plancher » du majorant d'emprise, exercee** (M5, mutant `P03`).

    `qr_footprint_bound_mm` rend `max(emprise(plancher), emprise(plafond))` et son
    docstring consacre trente lignes a expliquer que l'emprise est **en U**, donc que le
    maximum est a l'une des deux extremites. Sur le domaine livre c'est le **plafond** qui
    gagne, et de 0,034 mm seulement (39,624 mm a 109 modules contre 39,590 a 61). La
    branche « plancher » est donc **morte sur tout le domaine livre**, et le mutant `P03`
    (« le majorant ne regarde que le plafond ») survivait, tandis que son symetrique `P02`
    mourait: l'asymetrie **est** la mesure.

    Ce n'est pas un defaut -- le `max` est la bonne forme, et la seule qui reste juste si
    le domaine bouge -- mais la propriete est a 0,034 mm de changer de branche, et rien ne
    l'exercait dans l'autre sens. Le jour ou les cles du payload raccourcissent d'un cran
    (57 modules), la valeur du majorant change sans qu'un seul test ne parle de cette
    bascule.

    Le test construit donc un domaine ou le **plancher gagne**, sur le modele du gabarit
    construit a 60 pt qui prouve la comparaison des bords. Le domaine est choisi par le
    calcul du point de bascule, pas au tatonnement.
    """
    # Le point de bascule se calcule, et le test le recalcule plutot que de le citer.
    plafond = page_templates.qr_footprint_mm(page_templates.QR_MAX_MODULE_SIDE)
    bascule = (2 * page_templates.QR_QUIET_ZONE_MODULES
               * page_templates.QR_PRINT_SIZE_TARGET_MM
               / (plafond - page_templates.QR_PRINT_SIZE_TARGET_MM))
    # Sur le domaine livre le plancher est **au-dessus** du point de bascule, donc c'est le
    # plafond qui gouverne. C'est l'etat de fait, mesure ailleurs; on le reverifie ici
    # parce que c'est lui qui rend le domaine construit ci-dessous non trivial.
    assert page_templates.QR_MIN_MODULE_SIDE > bascule
    assert page_templates.qr_footprint_bound_mm() == pytest.approx(plafond)
    # Un domaine ou le plancher descend **sous** le point de bascule: le module le plus
    # petit y rend l'emprise la plus grande, parce que le silence ISO -- compte en
    # modules -- pese relativement plus quand il y en a moins.
    plancher_construit = int(bascule) - 3
    assert plancher_construit < bascule
    monkey = pytest.MonkeyPatch()
    try:
        monkey.setattr(page_templates, "QR_MIN_MODULE_SIDE", plancher_construit)
        monkey.setattr(page_templates, "QR_MAX_MODULE_SIDE",
                       page_templates.QR_MIN_MODULE_SIDE + 4)
        bas = page_templates.qr_footprint_mm(page_templates.QR_MIN_MODULE_SIDE)
        haut = page_templates.qr_footprint_mm(page_templates.QR_MAX_MODULE_SIDE)
        # Le domaine construit renverse bien l'inegalite -- sinon le test n'exerce rien,
        # et c'est exactement le piege du gabarit a 60 pt.
        assert bas > haut, (bas, haut)
        assert page_templates.qr_footprint_bound_mm() == pytest.approx(bas)
        assert page_templates.qr_footprint_bound_mm() > haut
    finally:
        monkey.undo()
    # Et le domaine reel est revenu: la bascule vient du parametre, pas d'un residu.
    assert page_templates.QR_MIN_MODULE_SIDE > bascule
    assert page_templates.qr_footprint_bound_mm() == pytest.approx(plafond)


def test_the_grid_gap_is_a_field_and_the_two_versions_differ_by_it() -> None:
    """Le pas de grille est un **champ**, et la v1 ne bouge pas (AC 2).

    Il etait une constante de module, donc la meme pour toutes les versions: la v1 ne
    pouvait pas garder 10 mm si la v2 en voulait 3. Le test verifie les deux sens -- les
    deux versions rendent des zones differentes pour le meme cardinal, et la v1 rend
    **exactement** ce qu'elle rendait.
    """
    v1, v2 = page_templates.GEOMETRY_V1, page_templates.GEOMETRY_V2
    assert v1.frame_grid_gap_mm == 10.0
    assert v2.frame_grid_gap_mm == 3.0
    assert v1.frame_grid_gap_mm == page_templates.FRAME_GRID_GAP_MM
    assert v2.frame_grid_gap_mm == page_templates.FRAME_GRID_GAP_V2_MM
    # La v1 est transparente a la derivation du pas vertical: son pas domine la bande
    # d'etiquette, donc le `max` y rend 10.
    assert v1.frame_grid_row_gap_mm() == 10.0
    # Le pas est bien ce qui separe deux rangees, dans les deux versions -- mesure sur
    # les zones composees et non sur le champ.
    for version, expected in (("v1", 10.0), ("v2", 5.0)):
        spec = page_templates.template_for(PORTRAIT, 2, "0", version)
        first, second = spec.frame_zones_mm
        assert second["y"] - (first["y"] + first["height"]) == pytest.approx(expected)
    # Et deux colonnes sont separees par le pas **horizontal**, qui differe du vertical
    # en v2: c'est la seule facon de voir que le pas est anisotrope.
    spec = page_templates.template_for(PORTRAIT, 8, "0", "v2")
    zones = spec.frame_zones_mm
    assert spec.grid_columns == 2 and spec.grid_rows == 4
    assert zones[1]["x"] - (zones[0]["x"] + zones[0]["width"]) == pytest.approx(3.0)
    assert zones[2]["y"] - (zones[0]["y"] + zones[0]["height"]) == pytest.approx(5.0)


def test_no_scan_path_step_reads_the_frame_grid_gap() -> None:
    """La justification **negative** du pas de grille (AC 8).

    Le pas ne protege ni une marge de coupe (aucune planche n'est decoupee: le dispositif
    scanne la planche entiere et recadre par homographie) ni une tolerance de detection
    au scan. Le second point se verifie, et c'est ce que fait ce test: le recadrage d'une
    zone se derive du `template_id` et des quatre marqueurs de coin, jamais de la
    frontiere entre deux zones -- donc **aucun** module du chemin de scan ne lit ce pas.

    Un grep, et c'est assume: la propriete est une absence de dependance, et une absence
    ne se mesure pas en exercant du code.
    """
    import re

    source_dir = REPO_ROOT / "src" / "mixed_media_utility"
    scan_modules = sorted(
        path for path in source_dir.rglob("*.py")
        if path.name.startswith("scan_") or path.parent.name == "detection"
    )
    assert len(scan_modules) >= 5, scan_modules
    pattern = re.compile(r"frame_grid_(row_)?gap|FRAME_GRID_GAP")
    for path in scan_modules:
        assert not pattern.search(path.read_text(encoding="utf-8")), path


#: Surface **par frame** de chaque cardinal sur la geometrie optimisee, et le barreau
#: qu'il forme avec le cardinal superieur (`EPIC5-ARB-62`, AC 13). Mesure sur la
#: geometrie livree, cardinal retire compris -- c'est la seule facon de justifier son
#: retrait.
_PER_FRAME_MM2 = {1: 31152.7, 2: 19044.0, 3: 9015.7, 4: 7211.0, 6: 4607.0, 8: 4607.0}

#: Les cinq barreaux, en pourcentage de gain de surface par frame. Le seuil retenu par
#: `EPIC5-ARB-62` est **15 %**, et la separation est nette: le seul barreau sous le seuil
#: vaut 0,0 %, le suivant 25,0 %.
_RUNG_GAIN_PCT = {(8, 6): 0.0, (6, 4): 56.5, (4, 3): 25.0, (3, 2): 111.2, (2, 1): 63.6}

#: Seuil de « significativement » (`EPIC5-ARB-62`, arbitrage produit).
_DEGENERATE_RUNG_THRESHOLD_PCT = 15.0

#: Les neuf barreaux du vocabulaire, **evalues par orientation** et non sur le `max`
#: (`EPIC5-ARB-64`, tableau de l'arbitrage). C'est cette table qui interdit de croire
#: qu'on peut generaliser le critere de retrait sans mesurer sa **cascade**: par
#: orientation, le portrait porte **trois** barreaux degeneres et le paysage aucun, et
#: retirer les trois cascade (le 6f retire, `8f -> 4f` vaut +4,99 % et reste degenere,
#: donc 4f part aussi et le vocabulaire portrait tombe a `2, 3, 8`).
#:
#: Elle est distincte de `_RUNG_GAIN_PCT`, qui est la table de **detection** -- le `max`
#: sur les orientations, convention inchangee par `EPIC5-ARB-64`. Les deux tables mesurent
#: la meme geometrie sous deux regimes, et c'est pour cela que les deux sont ecrites: un
#: seul chiffre par barreau ferait croire que le regime ne compte pas, ce qui est
#: exactement l'erreur que les revues de 5.17 et de 5.18 ont trouvee quatre fois.
_RUNG_GAIN_PCT_BY_ORIENTATION = {
    PORTRAIT: {(8, 6): 0.00, (6, 4): 4.99, (4, 3): 86.40, (3, 2): 111.23,
               (2, 1): 0.00},
    PAYSAGE: {(8, 6): 81.87, (6, 4): 64.29, (4, 2): 40.07, (2, 1): 208.44},
}

#: Le seul cardinal que la v2 retire, et **de quelle orientation** (`EPIC5-ARB-64`).
#: Ecrit en dur parce que c'est la decision produit; tout le reste est calcule.
_RETIRED_BY_ORIENTATION = {PORTRAIT: {6}, PAYSAGE: set()}


def test_the_rung_gains_the_operator_reads_are_the_ones_the_geometry_renders() -> None:
    """**Le motif imprime a l'operateur cite les gains que la geometrie rend** (M1).

    La revue de 5.18 a trouve deux chiffres faux dans le motif de refus du cardinal 6 --
    « les autres barreaux valant de +46 % a +75 % » pour un intervalle reel de +25,0 a
    +111,2, et « ou 4 pour +61,5 % par frame » pour un barreau a +56,5 % -- a vingt
    lignes d'une table de tests qui portait les valeurs justes. Les mutants `R01` et
    `R02` de la campagne changeaient chacun l'un de ces chiffres et **survivaient**: le
    test du refus ne regardait que les deux chiffres qui, eux, etaient justes.

    Le motif est donc **derive** de `page_templates.RUNG_GAIN_PCT_V2` depuis la passe de
    correction, et ce test ferme la boucle par les deux bouts:

    1. la table de production est **la meme** que celle des tests, qui est elle-meme
       confrontee a la geometrie composee par
       `test_the_cardinal_vocabulary_is_re_evaluated_on_the_optimised_geometry`. Une
       valeur fausse en production tombe donc ici, et une valeur fausse dans les deux
       tables tombe sur la geometrie;
    2. chaque grandeur citee par le motif est **retrouvee dans le message**, valeur
       comprise -- pas seulement le fragment `"4 pour"`.
    """
    assert dict(page_templates.RUNG_GAIN_PCT_V2) == _RUNG_GAIN_PCT
    assert (page_templates.DEGENERATE_RUNG_THRESHOLD_PCT
            == _DEGENERATE_RUNG_THRESHOLD_PCT)
    message = page_templates.retired_cardinal_reason("v2", 6)
    assert message is not None
    # Le barreau degenere, le barreau de repli, et l'intervalle des autres barreaux:
    # les trois grandeurs, avec leur **valeur**.
    others = [gain for rung, gain in _RUNG_GAIN_PCT.items() if rung != (8, 6)]
    for expected in (_RUNG_GAIN_PCT[(8, 6)], _RUNG_GAIN_PCT[(6, 4)],
                     min(others), max(others)):
        rendered = f"+{expected:.1f} %".replace(".", ",")
        assert rendered in message, (rendered, message)
    # Et les valeurs fausses que la revue a trouvees ne sont plus dans le message. Une
    # frontiere negative, parce que c'est exactement ce qu'un litteral y avait remis.
    for stale in ("+61,5 %", "+46 %", "+75 %"):
        assert stale not in message, (stale, message)
    # Le conseil de repli nomme bien le cardinal dont il cite le gain: sans cette
    # assertion, un motif qui conseillerait 3 en citant le gain du barreau `6 -> 4`
    # passerait.
    assert f"ou 4 pour +{_RUNG_GAIN_PCT[(6, 4)]:.1f} %".replace(".", ",") in message


def test_the_cardinal_vocabulary_is_re_evaluated_on_the_optimised_geometry() -> None:
    """**Le barreau degenere a change de place** (AC 13, `EPIC5-ARB-62`).

    Sur la v2 telle que 5.15 la livrait, le barreau degenere etait `6f -> 4f` (+0,6 %
    pour 50 % de papier en plus). Sur la geometrie optimisee c'est `8f -> 6f`: 6f et 8f y
    sont tous deux bornes en **largeur** sur deux colonnes, donc leur zone est identique
    et leur surface par frame aussi. Appliquer la regle avant la passe aurait retire 4f,
    desormais un barreau sain, et laisse 6f, qui ne sert a rien.

    Les deux clauses d'`EPIC5-ARB-62` sont donc verifiees ici: la regle s'evalue sur la
    geometrie **optimisee**, et sur des planches toutes optimisees -- sinon le critere
    recompense la negligence.
    """
    geometry = page_templates.GEOMETRY_V2
    per_frame = {}
    for cardinal in sorted(_PER_FRAME_MM2):
        best = max(
            _drawing_area(geometry, orientation, cardinal)
            for orientation in page_templates.ORIENTATIONS
            if cardinal in page_templates.FRAMES_PER_PAGE_VOCABULARY[orientation]
        )
        per_frame[cardinal] = best / cardinal
        assert per_frame[cardinal] == pytest.approx(
            _PER_FRAME_MM2[cardinal], abs=0.5), cardinal
    # La suite par frame reste strictement decroissante en cardinal, **sauf** sur le
    # barreau degenere ou elle est plate: c'est l'invariant qu'Egan enonce, et c'est son
    # cas d'egalite qui declenche le retrait.
    ordered = sorted(per_frame, reverse=True)
    degenerate = []
    for high, low in zip(ordered, ordered[1:]):
        gain = per_frame[low] / per_frame[high] - 1
        assert gain == pytest.approx(_RUNG_GAIN_PCT[(high, low)] / 100.0, abs=0.005), (
            high, low, gain)
        if gain * 100.0 < _DEGENERATE_RUNG_THRESHOLD_PCT:
            degenerate.append(low)
    assert degenerate == [6], degenerate
    # La separation est nette: le seuil peut bouger dans tout l'intervalle propose par
    # l'arbitrage (10 a 20 %) sans changer le verdict.
    for threshold in (10.0, 15.0, 20.0):
        below = [low for high, low in zip(ordered, ordered[1:])
                 if (per_frame[low] / per_frame[high] - 1) * 100.0 < threshold]
        assert below == [6], (threshold, below)
    # Et c'est bien 6f qui est retire du vocabulaire de la v2, pas 4f.
    assert page_templates.retired_cardinal_reason("v2", 6) is not None
    assert page_templates.retired_cardinal_reason("v2", 4) is None
    # --- `EPIC5-ARB-64`: la PORTEE du retrait, mesuree par orientation ---------------
    #
    # La detection ci-dessus ne change pas. Ce qui suit mesure, orientation par
    # orientation, ce que le critere y verrait -- et c'est ce qui justifie que le retrait
    # ne porte que sur le portrait, **sans** que la detection y passe.
    flagged: dict[str, list[int]] = {}
    for name in page_templates.ORIENTATIONS:
        cards = sorted(page_templates.FRAMES_PER_PAGE_VOCABULARY[name], reverse=True)
        per_orientation = {
            cardinal: _drawing_area(geometry, name, cardinal) / cardinal
            for cardinal in cards
        }
        expected_rungs = _RUNG_GAIN_PCT_BY_ORIENTATION[name]
        assert set(zip(cards, cards[1:])) == set(expected_rungs), name
        flagged[name] = []
        for high, low in zip(cards, cards[1:]):
            gain = (per_orientation[low] / per_orientation[high] - 1) * 100.0
            assert gain == pytest.approx(expected_rungs[(high, low)], abs=0.02), (
                name, high, low, gain)
            if gain < _DEGENERATE_RUNG_THRESHOLD_PCT:
                flagged[name].append(low)
    # Le portrait porte **trois** barreaux degeneres, le paysage aucun: c'est la mesure
    # qui a fait ecarter « le critere s'evalue par orientation » comme formulation de
    # l'amendement, et sans elle la prochaine passe la reprendrait.
    assert flagged == {PORTRAIT: [6, 4, 1], PAYSAGE: []}, flagged
    # Et la cascade se mesure aussi: le 6f retire, le barreau au-dessus du 4f portrait
    # devient `8f -> 4f` et reste sous le seuil. Le vocabulaire portrait tomberait a
    # `2, 3, 8`.
    portrait_per_frame = {
        cardinal: _drawing_area(geometry, PORTRAIT, cardinal) / cardinal
        for cardinal in page_templates.FRAMES_PER_PAGE_VOCABULARY[PORTRAIT]
    }
    cascade = (portrait_per_frame[4] / portrait_per_frame[8] - 1) * 100.0
    assert cascade < _DEGENERATE_RUNG_THRESHOLD_PCT, cascade
    assert cascade == pytest.approx(4.99, abs=0.02), cascade
    # **Ce que la v2 retire vraiment**: le 6 en portrait, rien en paysage. Le 6f paysage
    # rend +81,9 % de surface par frame de plus que le 8f -- c'est le meilleur barreau
    # sous 4f, l'inverse d'un barreau degenere.
    for name in page_templates.ORIENTATIONS:
        offered = set(page_templates.frames_per_page_vocabulary(name, "v2"))
        base = set(page_templates.FRAMES_PER_PAGE_VOCABULARY[name])
        assert base - offered == _RETIRED_BY_ORIENTATION[name], name
        for cardinal in sorted(base):
            reason = page_templates.retired_cardinal_reason("v2", cardinal, name)
            assert (reason is not None) is (
                cardinal in _RETIRED_BY_ORIENTATION[name]), (name, cardinal)
    assert 6 in page_templates.frames_per_page_vocabulary(PAYSAGE, "v2")
    assert 6 not in page_templates.frames_per_page_vocabulary(PORTRAIT, "v2")


@pytest.mark.parametrize("orientation", list(page_templates.ORIENTATIONS))
def test_the_retired_cardinal_is_refused_in_v2_with_a_named_motive(orientation) -> None:
    """Le refus **nomme le motif chiffre**, et la v1 reste resolvable (AC 13).

    Retirer un cardinal du vocabulaire n'est pas neutre: les `template_id` qui le portent
    cessent d'etre resolvables, et l'AC 1 interdit d'y toucher en v1. Le refus doit donc
    dire pourquoi -- le gain par frame **et** le cout en papier -- sinon un operateur qui
    composait en 6f la semaine precedente ne peut pas savoir quoi faire.

    **Le test est parametre sur les deux orientations et les traite differemment**
    (`EPIC5-ARB-64`): en portrait le 6f est refuse avec son motif, en paysage il **compose
    normalement**. Les deux branches sont ecrites plutot que l'orientation paysage sautee,
    parce que c'est l'asymetrie elle-meme qui est la decision produit -- un test qui ne
    regarderait que le portrait passerait aussi si le 6f paysage disparaissait a nouveau.
    """
    # La v1 reste resolvable dans les deux orientations, et son gabarit 6f rend exactement
    # ce qu'il rendait: c'est l'AC 1, et elle ne depend pas de l'orientation.
    v1_id = page_templates.build_template_id(orientation, 6, "0", "v1")
    assert page_templates.get_template(v1_id).frames_per_page == 6
    assert (orientation, 6) in GABARITS_V1
    if 6 not in _RETIRED_BY_ORIENTATION[orientation]:
        # Paysage: le 6f est offert, donc rien n'est refuse -- ni au registre, ni au
        # chemin operateur, et le gabarit v2 est bien distinct du gabarit v1.
        v2_id = page_templates.build_template_id(orientation, 6, "0", "v2")
        assert page_templates.get_template(v2_id).frames_per_page == 6
        assert (orientation, 6) in GABARITS_V2
        assert page_templates.get_template(v2_id).frame_zones_mm != (
            page_templates.get_template(v1_id).frame_zones_mm)
        assert pdf_composition.resolve_frames_per_page(orientation, 6, "v2") == 6
        return
    with pytest.raises(page_templates.UnknownTemplateError) as refus:
        page_templates.build_template_id(orientation, 6, "0", "v2")
    message = str(refus.value)
    assert "+0,0 %" in message
    assert "33 % de papier" in message
    assert "EPIC5-ARB-62" in message
    assert "15 %" in message
    # Le motif porte son **orientation**, et il dit que le cardinal reste offert dans
    # l'autre: la phrase « 6f et 8f sont bornes en largeur sur deux colonnes » est vraie
    # ici et fausse en paysage (M1, troisieme point), donc elle doit etre lue avec son
    # orientation ou pas du tout.
    assert orientation in message
    assert "reste offert en paysage" in message
    # Le motif propose une issue: le cardinal a employer a la place, dans les deux sens
    # -- **avec la valeur** du gain, et pas seulement le fragment `"4 pour"`. C'est ce
    # que les mutants `R01` et `R02` traversaient (revue de 5.18, M1).
    assert "Utiliser 8" in message
    assert f"4 pour +{_RUNG_GAIN_PCT[(6, 4)]:.1f} %".replace(".", ",") in message
    others = [gain for rung, gain in _RUNG_GAIN_PCT.items() if rung != (8, 6)]
    assert f"de +{min(others):.1f} % a +{max(others):.1f} %".replace(".", ",") in message
    assert (orientation, 6) not in GABARITS_V2
    # Et le refus traverse jusqu'au chemin operateur, en nommant le meme motif.
    manifest, lot_id = _composition_manifest()
    with pytest.raises(pdf_composition.ParameterVocabularyError) as compose_refus:
        pdf_composition.compose_lot_plan(
            manifest=manifest, lot_id=lot_id, orientation=orientation,
            frames_per_page=6)
    assert "33 % de papier" in str(compose_refus.value)


def test_the_qr_footprint_bound_names_which_branch_of_the_max_governs() -> None:
    """**Quelle branche du `max` gouverne**, nommee et mesuree (AC 7bis).

    Le majorant d'emprise du QR est a 0,034 mm de changer de branche, et un payload plus
    **leger** ferait **grandir** l'emprise: sous le regime plafonne par la cible de
    35 mm, moins il y a de modules, plus le silence ISO -- compte en modules -- pese
    relativement. La story 5.18 ne touche pas a la taille du QR, donc le raisonnement en
    U de la docstring reste vrai; mais sans ce test, la prochaine session lirait une
    docstring sur une forme dont plus rien ne dit laquelle des deux extremites gagne.

    Le test nomme donc la branche gouvernante et l'ecart qui la separe de l'autre, et il
    verifie que le domaine effectif de la story est bien celui-la.
    """
    low = page_templates.qr_footprint_mm(page_templates.QR_MIN_MODULE_SIDE)
    high = page_templates.qr_footprint_mm(page_templates.QR_MAX_MODULE_SIDE)
    bound = page_templates.qr_footprint_bound_mm()
    # C'est l'extremite **haute** qui gouverne, et de 0,034 mm seulement.
    assert bound == pytest.approx(high)
    assert bound > low
    assert high - low == pytest.approx(0.034, abs=0.001)
    # Le regime de chaque extremite est nomme: plafonne par la cible en bas, suivant le
    # plancher de lisibilite en haut.
    floor_low = (page_templates.QR_MIN_PIXELS_PER_MODULE
                 * page_templates.QR_MIN_MODULE_SIDE
                 / page_templates.QR_MIN_SCAN_DPI * 25.4)
    floor_high = (page_templates.QR_MIN_PIXELS_PER_MODULE
                  * page_templates.QR_MAX_MODULE_SIDE
                  / page_templates.QR_MIN_SCAN_DPI * 25.4)
    assert floor_low < page_templates.QR_PRINT_SIZE_TARGET_MM
    assert floor_high > page_templates.QR_PRINT_SIZE_TARGET_MM
    # Et le point de bascule se calcule: l'emprise plafonnee vaut celle du plafond a
    # 60,55 modules, donc le plancher passerait devant des qu'il descendrait a 57.
    bascule = (2 * page_templates.QR_QUIET_ZONE_MODULES
               * page_templates.QR_PRINT_SIZE_TARGET_MM
               / (high - page_templates.QR_PRINT_SIZE_TARGET_MM))
    assert bascule == pytest.approx(60.55, abs=0.05)
    assert page_templates.QR_MIN_MODULE_SIDE > bascule
    assert page_templates.qr_footprint_mm(57) > bound
    # La story 5.18 ne rouvre pas la taille imprimee: la cible de 4.6 est intacte, donc
    # le regime en U l'est aussi. Un test de frontiere negatif, parce que c'est ce qui
    # ferait tomber le raisonnement de la docstring sans qu'elle bouge.
    assert page_templates.QR_PRINT_SIZE_TARGET_MM == 35.0
    assert page_templates.QR_MIN_PIXELS_PER_MODULE == 8.0


@pytest.mark.parametrize("orientation,free_mm,flush", [
    # Portrait: 79 mm de hauteur libre sous une colonne pleine -- l'emprise (39,6 mm) y
    # tient largement, donc le QR se colle a la marge d'encre.
    (PORTRAIT, 79.0, True),
    # Paysage: 1 mm. Le QR ne peut pas descendre sous la colonne, il se range a cote.
    (PAYSAGE, 1.0, False),
])
def test_the_flank_clearance_is_computed_on_the_real_free_height(
        orientation, free_mm, flush) -> None:
    """**Le degagement d'un flanc se CALCULE**, et les deux branches sont exercees.

    Releve d'Egan du 2026-08-12, et la conclusion intuitive etait fausse dans les deux
    sens. La colonne de pastilles occupe 6 mm de large mais **pas toute la hauteur** du
    couloir lateral: sous elle il reste de la place, et un QR de flanc peut s'y coller a
    la marge d'encre. Le banc de recherche s'est trompe deux fois de suite sur ce meme
    point -- d'abord un `max` qui faisait chevaucher le QR et la colonne (section 8.6),
    puis un empilement horizontal qui reserve 8 mm pour rien la ou la hauteur libre
    suffit.

    Les deux orientations couvrent les deux branches, et ce n'est pas un hasard
    exploitable: c'est la hauteur de page qui les separe, et le test epingle la hauteur
    libre de chacune pour que la bascule d'une branche a l'autre se voie.

    **Et cette correction ne rend aucune surface de dessin**: le seul cardinal qui envoie
    le QR sur un flanc est borne en hauteur, donc les 8 mm de largeur recuperes lui sont
    inutilisables. C'est une correction de justesse -- la reservation etait fausse -- et
    elle ne doit pas etre presentee comme une amelioration. Le test le verifie aussi,
    parce que c'est precisement le genre de gain auquel on croit sans mesurer.
    """
    geometry = page_templates.GEOMETRY_V2
    footprint = page_templates.qr_footprint_bound_mm()
    free = geometry.lateral_free_height_mm(orientation)
    assert free == pytest.approx(free_mm, abs=0.05), orientation
    assert (free >= footprint) is flush, (orientation, free, footprint)
    lateral = (geometry.patch_block_end_mm(orientation)
               + geometry.patch_to_band_gap_mm[orientation])
    collee = geometry.printer_margin_mm + footprint + page_templates.TOP_BAND_GUARD_MM
    a_cote = lateral + footprint + page_templates.TOP_BAND_GUARD_MM
    assert a_cote - collee == pytest.approx(lateral - geometry.printer_margin_mm)
    assert a_cote - collee == pytest.approx(8.0)
    expected = collee if flush else a_cote
    assert geometry.qr_flank_clearance_mm(orientation) == pytest.approx(expected)
    for qr_edge in (page_templates.QR_EDGE_LEFT, page_templates.QR_EDGE_RIGHT):
        edges = geometry.band_edges_mm(orientation, qr_edge)
        side = "left" if qr_edge == page_templates.QR_EDGE_LEFT else "right"
        assert edges[side] == pytest.approx(expected)


@pytest.mark.parametrize("orientation", list(page_templates.ORIENTATIONS))
def test_the_flank_qr_never_meets_a_patch_of_any_preset(orientation) -> None:
    """La reservation du flanc, **confrontee aux placements reels** de tous les presets.

    La hauteur libre est calculee sur `min(PATCH_MAX_ROWS_PER_SIDE, capacite du
    couloir)`: le module de geometrie ignore tout des presets, donc il **reserve** et un
    test confronte -- exactement le motif du budget de lignes techniques du pied de page.

    Ce que la confrontation doit dire: quel que soit le preset place, aucune pastille
    n'entre dans l'emprise reservee au QR de flanc. C'est le seul enonce qui protege du
    scenario ou le QR s'imprime par-dessus une pastille, et il n'est pas verifiable sur
    la geometrie seule.
    """
    geometry = page_templates.GEOMETRY_V2
    footprint = page_templates.qr_footprint_bound_mm()
    for cardinal in page_templates.frames_per_page_vocabulary(orientation, "v2"):
        for qr_edge in (page_templates.QR_EDGE_LEFT, page_templates.QR_EDGE_RIGHT):
            spec = dataclasses.replace(
                page_templates.template_for(orientation, cardinal, "0", "v2"),
                qr_edge=qr_edge)
            reserved = page_templates.qr_reserved_zone_mm(spec)
            assert reserved[2] == pytest.approx(footprint)
            for preset_id in patch_presets.known_preset_ids():
                if ("v2", orientation, preset_id) in patch_presets._PLACEMENT_UNPLACEABLE:
                    continue
                for patch in patch_presets.resolve_patch_layout(
                        spec.template_id, preset_id):
                    rect = (patch.x_mm, patch.y_mm, patch.size_mm, patch.size_mm)
                    assert not rects_overlap(reserved, rect), (
                        orientation, cardinal, qr_edge, preset_id, rect, reserved)
    # Et la borne de rangees est bien le miroir du preset le plus riche par cote: un
    # miroir perime reserverait la hauteur libre d'une colonne plus courte que la reelle.
    orders = (patch_presets._ORDER_9, patch_presets._ORDER_12, patch_presets._ORDER_18)
    assert page_templates.PATCH_MAX_ROWS_PER_SIDE == max(
        len(order) for order in orders)


def test_the_lateral_row_capacity_has_a_single_implementation() -> None:
    """Une seule recette de couloir lateral, lue par ses deux consommateurs.

    La capacite de rangees et l'ordonnee de la premiere rangee vivaient dans
    `patch_presets`; elles decident desormais aussi si un QR de flanc a de la place sous
    la colonne, donc elles ont demenage dans `PageGeometry` et `patch_presets` y delegue.
    Deux recettes divergeraient au premier changement, et le symptome serait un QR
    imprime par-dessus des pastilles.
    """
    from mixed_media_utility import patch_presets as pp

    for version, geometry in page_templates.GEOMETRY_VERSIONS.items():
        assert pp._derived_first_row_y_mm(geometry) == (
            geometry.lateral_first_row_y_mm()), version
        for orientation in page_templates.ORIENTATIONS:
            assert pp._derived_row_capacity(geometry, orientation) == (
                geometry.lateral_row_capacity(orientation)), (version, orientation)


#: La declaration de `GEOMETRY_V1`, **caractere par caractere**, telle qu'elle est au
#: `baseline_commit` de la story 5.18. Ce n'est pas une redondance du premier test du
#: fichier: celui-la epingle les **valeurs** que la v1 porte a l'execution, celui-ci
#: epingle le **texte** qui les declare.
#:
#: L'AC 1 demande qu'« un grep de `GEOMETRY_V1` dans le diff de `page_templates.py` rende
#: zero ». Prise au mot la formulation est intenable -- la constante de defaut de version
#: cite `GEOMETRY_V1` et l'AC 11 exige de la changer -- mais ce qu'elle protege se teste
#: exactement: le bloc de declaration ne bouge pas d'un caractere. C'est ce qui rend
#: **verifiable** le choix de donner aux trois champs ajoutes par la passe un defaut egal
#: au comportement historique, plutot que de les passer a la v1.
_V1_DECLARATION = '''GEOMETRY_V1 = PageGeometry(
    version="v1",
    marker_size_mm=MARKER_SIZE_MM,
    marker_margin_mm=MARKER_MARGIN_MM,
    marker_quiet_zone_mm=MARKER_QUIET_ZONE_MM,
    printer_margin_mm=PRINTER_MARGIN_MM,
    patch_size_mm=PATCH_SIZE_MM,
    patch_spacing_mm=PATCH_SPACING_MM,
    patch_columns_per_side=MappingProxyType(
        {ORIENTATION_PORTRAIT: 2, ORIENTATION_PAYSAGE: 3}
    ),
    patch_to_band_gap_mm=MappingProxyType(
        {ORIENTATION_PORTRAIT: 4.0, ORIENTATION_PAYSAGE: 3.0}
    ),
    bottom_extra_clearance_mm=MappingProxyType(
        {ORIENTATION_PORTRAIT: 9.5, ORIENTATION_PAYSAGE: 2.0}
    ),
)
'''


def test_the_v1_declaration_is_untouched_character_for_character() -> None:
    """**Le filet de l'AC 1, dans sa forme testable.**

    La v1 ne se redefinit pas, et la passe de design lui ajoute pourtant trois champs.
    Ce qui rend les deux compatibles est un choix: les trois champs ont un **defaut** egal
    au comportement historique, donc la declaration de la v1 n'a pas eu a etre editee.

    Ce test epingle ce choix a l'endroit ou il se voit -- le texte source. Un futur
    developpeur qui passerait explicitement `frame_grid_gap_mm=10.0` a la v1 ne changerait
    aucune valeur et casserait pourtant ce test: c'est voulu, parce qu'il aurait alors
    rouvert la porte que le defaut ferme.
    """
    source = (REPO_ROOT / "src" / "mixed_media_utility" / "page_templates.py").read_text(
        encoding="utf-8")
    assert _V1_DECLARATION in source, (
        "la declaration de GEOMETRY_V1 a ete editee: la v1 est la geometrie des planches "
        "deja imprimees, et un champ ajoute a PageGeometry doit lui arriver par un "
        "DEFAUT, jamais par une ligne de sa declaration.")
    # Et les trois champs de la passe n'y figurent pas: c'est le defaut qui les porte.
    for field in ("frame_grid_gap_mm", "qr_bearing_edge", "identity_in_header"):
        assert field not in _V1_DECLARATION, field
        # ... mais ils sont bien des champs, et la v1 en porte la valeur historique.
        assert hasattr(page_templates.GEOMETRY_V1, field), field


def test_the_candidate_measure_uses_the_gaps_the_grid_will_really_use() -> None:
    """La surface qui **choisit** est celle que la grille produira (survivant `E09`).

    Le choix d'un candidat se fait sur une surface, et cette surface doit etre calculee aux
    **deux** pas de la version -- l'horizontal et le vertical derive. Mesurer au seul pas
    horizontal ne change le verdict d'aucun gabarit livre, donc rien ne le regardait: la
    geometrie livree ne compte que deux rangees au plus la ou l'ecart entre les deux pas se
    paie, et le classement reste le meme en etant uniformement faux.

    C'est le defaut « un candidat choisi sur une fiction »: la geometrie construite ici est
    celle ou la fiction **change le gagnant**. Trois colonnes de temoins par cote et un pas
    horizontal de 1 mm rendent le pas vertical (5 mm, la bande d'etiquette) quatre fois plus
    cher que l'horizontal; la variante « rangees haut/bas » paie alors sa hauteur au vrai
    prix et le bord bas cesse de gagner. Mesure des deux verdicts:

    * aux deux pas (le juste): bord **bas**, rangees **haut/bas**;
    * au seul pas horizontal (le mutant): bord **gauche**, colonnes **laterales**.
    """
    import types

    geometry = dataclasses.replace(
        page_templates.GEOMETRY_V2,
        patch_columns_per_side=types.MappingProxyType({PORTRAIT: 3, PAYSAGE: 3}),
        border_witness_count=8,
        frame_grid_gap_mm=1.0,
    )
    # La geometrie construite exerce bien l'ecart entre les deux pas.
    assert geometry.frame_grid_gap_mm == 1.0
    assert geometry.frame_grid_row_gap_mm() == page_templates.SLOT_LABEL_STRIP_MM

    def verdict(row_gap):
        best = None
        for qr_edge, placement, band in geometry._candidates(PAYSAGE):
            area = page_templates._drawing_area_mm2(
                band, 2, geometry.frame_grid_gap_mm, row_gap)
            if area <= 0:
                continue
            key = geometry._ranking_key(qr_edge, placement, band, area)
            if best is None or key < best[0]:
                best = (key, qr_edge, placement)
        return best[1], best[2]

    juste = verdict(geometry.frame_grid_row_gap_mm())
    fiction = verdict(geometry.frame_grid_gap_mm)
    assert juste == (page_templates.QR_EDGE_BOTTOM,
                     page_templates.WITNESS_PLACEMENT_BORDERS)
    assert fiction == (page_templates.QR_EDGE_LEFT,
                       page_templates.WITNESS_PLACEMENT_SIDES)
    assert juste != fiction, "la geometrie construite n'exerce plus la divergence"
    # Et c'est le **juste** que la production retient: le candidat est choisi sur la
    # surface que sa grille rendra vraiment.
    assert (geometry.qr_edge(PAYSAGE, 2), geometry.witness_placement(PAYSAGE, 2)) == juste


# ---------------------------------------------------------------------------
# Passe de correction de la story 5.18 -- la famille `K` de la campagne de
# cloture: la derivation de bande du QR de flanc. Quatre survivants sur le
# meme mecanisme (`K07`, `K10`, `K11`, `K12`), et c'est celui sur lequel Egan
# avait demande de la vigilance -- le QR colle au bord.
# ---------------------------------------------------------------------------


def test_a_flank_qr_with_room_below_the_patch_column_is_flush_to_the_ink_margin():
    """**`K11` et `K12`**: la bande collee d'un flanc est posee **sur la marge d'encre**.

    Les deux gabarits livres qui envoient le QR sur un flanc -- `3f` et `4f` portrait --
    prennent la branche « collee »: la hauteur libre sous la colonne de pastilles (79 mm)
    depasse l'emprise reservee (39,6 mm), donc le QR descend **sous** la colonne et partage
    sa bande d'abscisses, colle a la marge d'encre.

    Les deux mutants deplacent cette bande et **survivaient**:

    * `K11` neutralise la branche (`if free >= footprint:` -> `if False:`), donc le QR se
      range **a cote** de la colonne au lieu de dessous;
    * `K12` decale l'abscisse de 8 mm, donc le QR n'est plus colle a la marge.

    Aucun des deux ne produit de chevauchement -- l'abscisse decalee tombe apres la colonne
    de pastilles, et la surface de dessin ne depend pas de cette bande (elle se derive de
    `band_edges_mm`) -- donc rien ne les voyait. Ce qui est perdu est la **place**: 8 mm de
    largeur de page pour rien, et une reservation qui n'est plus celle que le placement des
    pastilles suppose.

    Le test asserte la propriete par sa **derivation** et non par un litteral: l'abscisse
    est exactement la marge d'encre, et l'ordonnee est dans la hauteur libre sous la
    colonne.
    """
    geometry = page_templates.GEOMETRY_V2
    flancs = [(orientation, cardinal) for orientation, cardinal in GABARITS_V2
              if geometry.qr_edge(orientation, cardinal) in (
                  page_templates.QR_EDGE_LEFT, page_templates.QR_EDGE_RIGHT)]
    assert flancs, "aucun gabarit livre n'envoie le QR sur un flanc"
    footprint = page_templates.qr_footprint_bound_mm()
    for orientation, cardinal in flancs:
        spec = page_templates.template_for(orientation, cardinal, "0", "v2")
        free = geometry.lateral_free_height_mm(orientation)
        # La branche empruntee est bien la branche « collee »: si elle ne l'etait pas, les
        # assertions qui suivent testeraient l'autre branche sans le dire.
        assert free >= footprint, (orientation, cardinal, free, footprint)
        x, y, largeur, hauteur = page_templates.qr_band_mm(spec)
        assert (largeur, hauteur) == pytest.approx((footprint, footprint))
        # **Collee a la marge d'encre**, et du bon cote.
        if spec.qr_edge == page_templates.QR_EDGE_LEFT:
            assert x == pytest.approx(geometry.printer_margin_mm), (orientation, cardinal)
        else:
            assert x == pytest.approx(
                spec.page_width_mm - geometry.printer_margin_mm - footprint)
        # Et elle est **sous** la colonne de pastilles, dans la hauteur libre: c'est ce qui
        # autorise a partager la bande d'abscisses de la colonne.
        haut_libre = spec.page_height_mm - geometry.corner_clearance_mm() - free
        assert y >= haut_libre - 1e-9, (orientation, cardinal, y, haut_libre)
        assert y + hauteur <= (
            spec.page_height_mm - geometry.corner_clearance_mm() + 1e-9)
        # La bande partage bien la bande d'abscisses de la colonne de pastilles -- c'est la
        # propriete que `K11` defait en la rangeant a cote.
        assert x < geometry.patch_block_end_mm(orientation) or (
            spec.qr_edge == page_templates.QR_EDGE_RIGHT)


def test_a_flank_qr_without_room_below_keeps_the_gap_to_the_patch_column() -> None:
    """**`K07`**: la bande rangee a cote d'un flanc compte l'ecart a la colonne.

    Le mutant oublie `patch_to_band_gap_mm` dans l'abscisse de la branche « a cote » et
    **survivait**: aucun gabarit livre n'emprunte cette branche. Elle n'est atteinte que
    quand la hauteur libre sous la colonne ne suffit pas -- le paysage, ou elle vaut 1 mm --
    et aucun gabarit paysage n'envoie le QR sur un flanc.

    Le test construit donc le gabarit, comme celui a 60 pt qui prouve la comparaison des
    bords: sans construction, cette branche entiere n'est exercee par rien, et un QR pose
    **sur** la colonne de pastilles ne se verrait qu'a l'impression.
    """
    geometry = page_templates.GEOMETRY_V2
    footprint = page_templates.qr_footprint_bound_mm()
    free = geometry.lateral_free_height_mm(PAYSAGE)
    # La branche visee est bien celle du paysage: la hauteur libre n'y suffit pas.
    assert free < footprint, (free, footprint)
    for edge in (page_templates.QR_EDGE_LEFT, page_templates.QR_EDGE_RIGHT):
        spec = dataclasses.replace(
            page_templates.template_for(PAYSAGE, 4, "0", "v2"), qr_edge=edge)
        x, y, largeur, hauteur = page_templates.qr_band_mm(spec)
        assert (largeur, hauteur) == pytest.approx((footprint, footprint))
        # L'ecart a la colonne est **compte**, et il l'est par derivation: l'offset vaut la
        # fin du bloc de pastilles **plus** l'ecart pastilles/bande.
        offset = (geometry.patch_block_end_mm(PAYSAGE)
                  + geometry.patch_to_band_gap_mm[PAYSAGE])
        assert offset > geometry.patch_block_end_mm(PAYSAGE), "l'ecart doit etre non nul"
        if edge == page_templates.QR_EDGE_LEFT:
            assert x == pytest.approx(offset)
            # Et la consequence concrete: la bande ne mord pas la colonne de pastilles.
            assert x >= geometry.patch_block_end_mm(PAYSAGE) + 1e-9
        else:
            assert x == pytest.approx(spec.page_width_mm - offset - footprint)
            assert x + footprint <= (
                spec.page_width_mm - geometry.patch_block_end_mm(PAYSAGE) - 1e-9)
        # L'ordonnee est centree dans le couloir laisse libre par les silences de coin: la
        # bande ne court pas tout le flanc, sinon elle mordrait les rangees de temoins de
        # la variante haut/bas.
        clearance = geometry.corner_clearance_mm()
        assert y == pytest.approx(
            clearance + (spec.page_height_mm - 2 * clearance - footprint) / 2.0)
