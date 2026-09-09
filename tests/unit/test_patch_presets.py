"""Tests du registre de presets de patchs de calibration (story 4.7).

Le registre est l'unique resolveur de `patch_preset_id`: presets versionnes
references sur la table de valeurs 4.8, placement deterministe par couple
template x preset, non-chevauchement geometrique verifie contre les
constantes reelles de `layout.py` (jamais des valeurs recopiees).
"""

from __future__ import annotations

import ast
import dataclasses
import math
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import (
    color_calibration,
    layout,
    page_templates,
    patch_presets,
    patch_values,
)

MODULE_PATH = REPO_ROOT / "src" / "mixed_media_utility" / "patch_presets.py"

IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def rects_overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def patch_rect(patch) -> tuple[float, float, float, float]:
    return (patch.x_mm, patch.y_mm, patch.size_mm, patch.size_mm)


def marker_forbidden_rects(template_id: str) -> list[tuple[float, float, float, float]]:
    """Emprise des marqueurs de coin + leur quiet zone interieure, calculee
    depuis les constantes reelles de layout (jamais recopiees). Les centres
    viennent du registre de templates 4.1, dont l'egalite avec
    `layout.corner_marker_centers_mm` est verrouillee par ailleurs
    (test_pdf_composition)."""
    spec = page_templates.get_template(template_id)
    # Taille et silence lus sur la geometrie **du template** depuis la story 5.15: les
    # constantes de `layout` sont celles de la v1, et les employer sur un gabarit v2
    # interdisait un carre de 60 mm la ou le marqueur et son silence n'en occupent que
    # 25 -- donc un test qui echouait sur une pastille pourtant licite. L'egalite de ces
    # constituants avec `layout` pour la v1 reste verrouillee ailleurs
    # (test_marker_geometry_constants_mirror_layout).
    half = spec.geometry.marker_size_mm / 2
    quiet = spec.geometry.marker_quiet_zone_mm
    rects = []
    for cx, cy in page_templates.corner_marker_centers_mm(spec).values():
        side = spec.geometry.marker_size_mm + 2 * quiet
        rects.append((cx - half - quiet, cy - half - quiet, side, side))
    return rects


# --- AC 1: registre versionne, unique resolveur ------------------------------


def test_shipped_presets_follow_the_arbitrated_cardinals() -> None:
    # EPIC4-ARB-6: deux presets livres, patches-9-v1 (9 valeurs x 2 = 18) et
    # patches-12-v1 (12 x 2 = 24); le preset degrade single n'est pas retenu.
    #
    # Amende par la story 5.9 (AC 8): un troisieme preset arrive,
    # `patches-18-v2` (18 x 2 = 36), et l'egalite exacte sur
    # `known_preset_ids()` casse mecaniquement. L'egalite est **conservee**
    # plutot que relachee en inclusion: c'est elle qui fait de l'ajout d'un
    # preset une decision explicite et non un effet de bord.
    #
    # Amende une seconde fois par la story 5.16 (AC 6 et 7): un **quatrieme** preset
    # arrive, `patches-14-v3` (14 x 2 = 28), le jeu temoin d'une planche d'images
    # depuis que la correction s'ajuste sur une page de calibration dediee. Motif de
    # l'amendement, et non de son relachement: l'egalite exacte est precisement ce
    # qui a rendu cet ajout visible ici plutot que quelque part au fond du registre
    # de placements.
    #
    # Amende une troisieme fois par la story 5.23 (AC 1, `EPIC5-ARB-82`): un
    # **cinquieme** preset arrive, `patches-17-v4` (17 x 2 = 34), le jeu temoin elargi
    # aux trois secondaires, porte a l'identique par la planche d'images **et** par la
    # page de calibration. Meme motif d'amendement que les deux precedents: l'egalite
    # exacte est ce qui rend l'ajout visible ici.
    assert set(patch_presets.known_preset_ids()) == {
        "patches-9-v1",
        "patches-12-v1",
        "patches-18-v2",
        "patches-14-v3",
        "patches-17-v4",
    }
    nine = patch_presets.get_patch_preset("patches-9-v1")
    twelve = patch_presets.get_patch_preset("patches-12-v1")
    eighteen = patch_presets.get_patch_preset("patches-18-v2")
    fourteen = patch_presets.get_patch_preset("patches-14-v3")
    seventeen = patch_presets.get_patch_preset("patches-17-v4")
    assert len(nine.value_ids) == 9
    assert len(twelve.value_ids) == 12
    assert len(eighteen.value_ids) == 18
    assert len(fourteen.value_ids) == 14
    assert len(seventeen.value_ids) == 17
    assert nine.repetition == 2
    assert twelve.repetition == 2
    assert eighteen.repetition == 2
    assert fourteen.repetition == 2
    assert seventeen.repetition == 2
    assert not nine.single and not twelve.single and not eighteen.single
    assert not fourteen.single and not seventeen.single
    # Les cardinaux restent **uniques**: `resolve_patch_preset` resout
    # `--nombre-patchs` par cardinal, et deux presets partageant un cardinal
    # feraient dependre ce qui s'imprime de l'ordre d'un litteral.
    cardinals = [len(patch_presets.get_patch_preset(pid).value_ids)
                 for pid in patch_presets.known_preset_ids()]
    assert sorted(cardinals) == [9, 12, 14, 17, 18]
    assert len(cardinals) == len(set(cardinals))


def test_preset_ids_are_schema_conformant() -> None:
    for preset_id in patch_presets.known_preset_ids():
        assert IDENTIFIER_PATTERN.match(preset_id), preset_id


def test_unknown_preset_is_an_explicit_business_error() -> None:
    with pytest.raises(patch_presets.UnknownPatchPresetError) as excinfo:
        patch_presets.get_patch_preset("patches-999-v9")
    message = str(excinfo.value)
    assert "patches-999-v9" in message
    for known in patch_presets.known_preset_ids():
        assert known in message


def test_presets_reference_an_existing_values_table_version() -> None:
    # AC 7: la version de table referencee doit exister dans le registre 4.8.
    for preset_id in patch_presets.known_preset_ids():
        preset = patch_presets.get_patch_preset(preset_id)
        assert preset.values_version in patch_values.known_versions()
        table = patch_values.get_patch_values_table(preset.values_version)
        for value_id in preset.value_ids:
            table.get(value_id)  # leve si inconnu


def test_shipped_presets_pin_their_table_version_literally() -> None:
    # Revue 4.8 (confirmee par trois relecteurs independants): la liaison
    # preset -> version de table est FIGEE a la creation du preset. Si elle
    # suivait ACTIVE_PATCH_VALUES_VERSION, publier une table v2 et basculer
    # l'alias rebrancherait les planches deja imprimees sur d'autres valeurs
    # (edition en place interdite par le versionnement 4.8). Ce test casse si
    # quelqu'un remplace le litteral par l'alias actif ET change l'alias --
    # et documente l'exigence: nouvelles valeurs => nouveaux presets v2.
    assert patch_presets.get_patch_preset("patches-9-v1").values_version == "patch-values-1"
    assert patch_presets.get_patch_preset("patches-12-v1").values_version == "patch-values-1"
    # Story 5.9: c'est cette ligne qui rend visible en revue que la bascule
    # d'alias (`ACTIVE_PATCH_VALUES_VERSION` -> "patch-values-2") ne rebranche
    # rien. Les deux presets ci-dessus restent sur la v1 alors que la table
    # active est la v2, et le nouveau preset epingle la v2 en litteral lui aussi.
    assert patch_presets.get_patch_preset("patches-18-v2").values_version == "patch-values-2"
    assert patch_values.ACTIVE_PATCH_VALUES_VERSION == "patch-values-2"


def test_registry_is_immutable() -> None:
    preset = patch_presets.get_patch_preset("patches-9-v1")
    assert isinstance(preset.value_ids, tuple)
    with pytest.raises(Exception):
        preset.repetition = 1  # type: ignore[misc]


# --- AC 2: minimum 9, repetition >= 2, positions eloignees -------------------


def test_every_preset_has_at_least_nine_distinct_values() -> None:
    for preset_id in patch_presets.known_preset_ids():
        preset = patch_presets.get_patch_preset(preset_id)
        assert len(set(preset.value_ids)) >= 9
        assert len(preset.value_ids) == len(set(preset.value_ids))


def test_each_value_appears_exactly_repetition_times_on_the_page() -> None:
    for template_id, preset_id in patch_presets.defined_couples():
        preset = patch_presets.get_patch_preset(preset_id)
        placed = patch_presets.resolve_patch_layout(template_id, preset_id)
        counts: dict[str, int] = {}
        for patch in placed:
            counts[patch.value_id] = counts.get(patch.value_id, 0) + 1
        assert set(counts) == set(preset.value_ids)
        if not preset.single:
            for value_id, count in counts.items():
                assert count == preset.repetition, (value_id, count)


def test_duplicate_patches_are_far_apart() -> None:
    # La moyenne des patchs identiques n'a de sens que si la repetition
    # capture la non-uniformite d'eclairage: doublons eloignes (piege 1).
    minimum_distance_mm = 100.0
    for template_id, preset_id in patch_presets.defined_couples():
        placed = patch_presets.resolve_patch_layout(template_id, preset_id)
        by_value: dict[str, list] = {}
        for patch in placed:
            by_value.setdefault(patch.value_id, []).append(patch)
        for value_id, patches in by_value.items():
            for i in range(len(patches)):
                for j in range(i + 1, len(patches)):
                    dx = patches[i].x_mm - patches[j].x_mm
                    dy = patches[i].y_mm - patches[j].y_mm
                    assert math.hypot(dx, dy) >= minimum_distance_mm, (
                        template_id, preset_id, value_id
                    )


def test_physical_patch_count_never_exceeds_the_arbitrated_maximum() -> None:
    # EPIC4-ARB-6: maximum 24 pastilles physiques par page, **amende a 36 par
    # EPIC5-ARB-14** (story 5.9). Le nouveau chiffre est mesure et non choisi:
    # colonnes de 12 mm au pas de 14 dans les bandes laterales libres, portrait
    # 48 emplacements, paysage 36 — le minimum des deux est le plafond commun.
    #
    # Le plafond est atteint **exactement** par `patches-18-v2` (18 x 2 = 36),
    # sans une cellule libre: toute valeur ajoutee a la v2 fera tomber la garde
    # d'execution de `resolve_patch_layout`, pas un test de style.
    assert patch_presets.MAX_PATCHES_PER_PAGE == 36
    saturating = [
        (t, p) for t, p in patch_presets.defined_couples()
        if len(patch_presets.resolve_patch_layout(t, p)) == patch_presets.MAX_PATCHES_PER_PAGE
    ]
    assert saturating, "le preset sentinelle doit saturer le plafond, sinon le chiffre ment"
    assert {p for _, p in saturating} == {"patches-18-v2"}
    for template_id, preset_id in patch_presets.defined_couples():
        placed = patch_presets.resolve_patch_layout(template_id, preset_id)
        assert len(placed) <= patch_presets.MAX_PATCHES_PER_PAGE


# --- AC 3: placement deterministe par couple template x preset ---------------


def test_resolution_is_deterministic() -> None:
    for template_id, preset_id in patch_presets.defined_couples():
        first = patch_presets.resolve_patch_layout(template_id, preset_id)
        second = patch_presets.resolve_patch_layout(template_id, preset_id)
        assert first == second


#: Colonne par colonne, la sequence de valeurs telle qu'elle est **imprimee** sur les
#: gabarits v1 -- une abscisse, puis les identifiants du haut vers le bas. C'est
#: l'appariement `valeur -> (colonne, rangee)`, epingle en litteral et non recalcule:
#: comparer la derivation a elle-meme ne verrouillerait rien.
#:
#: **Pourquoi ce tableau existe** (revue de la story 5.15, quatrieme occurrence de la
#: regle des fabriques du depot): le mutant miroir de `_sentinel_placement`
#: (`sequences[index % half]` remplace par son symetrique) deplace **les 36 pastilles**
#: de `portrait x patches-18-v2` en v1 -- chaque valeur change de colonne -- et 24 des
#: 36 en paysage, sans qu'aucun test de la suite elargie ne bronche, **y compris** la
#: fixture d'additivite octet pour octet. Raison exacte: tous les tests de placement
#: n'assertent que des proprietes **invariantes par permutation** (cardinal par valeur,
#: ensemble des valeurs, ecart minimal entre les deux copies, non-chevauchement), et
#: l'ecart minimal survit a la permutation (172 mm en portrait, 247 en paysage, tres
#: au-dela du seuil de 100 mm). Le code est juste; c'est l'appariement valeur ->
#: colonne qui n'etait verifie par rien.
#:
#: La v1 est la geometrie des planches **deja imprimees**: une permutation y serait
#: irrattrapable, la calibration lisant chaque valeur sur la pastille d'une autre.
_V1_COLUMN_SEQUENCES: dict[tuple[str, str], dict[float, tuple[str, ...]]] = {
    # Portrait, deux colonnes: la colonne de droite reprend la sequence **a l'envers**
    # (heritage de `_two_column_placement`), ce qui est precisement le genre de detail
    # qu'une propriete invariante par permutation ne peut pas voir.
    ("portrait", "patches-9-v1"): {
        14.0: ("neutral-020", "primary-red", "neutral-065", "primary-green",
               "neutral-110", "primary-blue", "neutral-200", "secondary-yellow",
               "neutral-245"),
        184.0: ("neutral-245", "secondary-yellow", "neutral-200", "primary-blue",
                "neutral-110", "primary-green", "neutral-065", "primary-red",
                "neutral-020"),
    },
    ("portrait", "patches-12-v1"): {
        14.0: ("neutral-020", "primary-red", "neutral-065", "primary-green",
               "neutral-110", "primary-blue", "neutral-155", "secondary-cyan",
               "neutral-200", "secondary-magenta", "neutral-245",
               "secondary-yellow"),
        184.0: ("secondary-yellow", "neutral-245", "secondary-magenta",
                "neutral-200", "secondary-cyan", "neutral-155", "primary-blue",
                "neutral-110", "primary-green", "neutral-065", "primary-red",
                "neutral-020"),
    },
    # Quatre colonnes, deux sequences distinctes reprises de chaque cote: c'est le
    # couple ou le mutant miroir deplace toutes les pastilles.
    ("portrait", "patches-18-v2"): {
        5.0: ("neutral-020", "sentinel-black-1", "neutral-110", "primary-red",
              "sentinel-red-1", "sentinel-red-2", "primary-green",
              "sentinel-green-1", "sentinel-green-2"),
        19.0: ("primary-blue", "sentinel-blue-1", "sentinel-blue-2",
               "secondary-cyan", "secondary-magenta", "secondary-yellow",
               "neutral-200", "neutral-245", "sentinel-white-1"),
        177.0: ("neutral-020", "sentinel-black-1", "neutral-110", "primary-red",
                "sentinel-red-1", "sentinel-red-2", "primary-green",
                "sentinel-green-1", "sentinel-green-2"),
        191.0: ("primary-blue", "sentinel-blue-1", "sentinel-blue-2",
                "secondary-cyan", "secondary-magenta", "secondary-yellow",
                "neutral-200", "neutral-245", "sentinel-white-1"),
    },
    ("paysage", "patches-9-v1"): {
        14.0: ("neutral-020", "primary-red", "neutral-065", "primary-green",
               "neutral-110"),
        30.0: ("primary-blue", "neutral-200", "secondary-yellow", "neutral-245"),
        255.0: ("primary-blue", "neutral-200", "secondary-yellow", "neutral-245"),
        271.0: ("neutral-020", "primary-red", "neutral-065", "primary-green",
                "neutral-110"),
    },
    ("paysage", "patches-12-v1"): {
        14.0: ("neutral-020", "primary-red", "neutral-065", "primary-green",
               "neutral-110", "primary-blue"),
        30.0: ("secondary-cyan", "neutral-155", "secondary-magenta", "neutral-200",
               "secondary-yellow", "neutral-245"),
        255.0: ("secondary-cyan", "neutral-155", "secondary-magenta", "neutral-200",
                "secondary-yellow", "neutral-245"),
        271.0: ("neutral-020", "primary-red", "neutral-065", "primary-green",
                "neutral-110", "primary-blue"),
    },
    ("paysage", "patches-18-v2"): {
        5.0: ("neutral-020", "sentinel-black-1", "neutral-110", "primary-red",
              "sentinel-red-1", "sentinel-red-2"),
        19.0: ("primary-green", "sentinel-green-1", "sentinel-green-2",
               "primary-blue", "sentinel-blue-1", "sentinel-blue-2"),
        33.0: ("secondary-cyan", "secondary-magenta", "secondary-yellow",
               "neutral-200", "neutral-245", "sentinel-white-1"),
        252.0: ("neutral-020", "sentinel-black-1", "neutral-110", "primary-red",
                "sentinel-red-1", "sentinel-red-2"),
        266.0: ("primary-green", "sentinel-green-1", "sentinel-green-2",
                "primary-blue", "sentinel-blue-1", "sentinel-blue-2"),
        280.0: ("secondary-cyan", "secondary-magenta", "secondary-yellow",
                "neutral-200", "neutral-245", "sentinel-white-1"),
    },
}


@pytest.mark.parametrize("orientation,preset_id", sorted(_V1_COLUMN_SEQUENCES))
def test_each_value_is_printed_at_its_own_column_and_row(
        orientation: str, preset_id: str) -> None:
    """La **position** de chaque valeur, pas une propriete invariante par permutation.

    Le placement est lu sur le producteur reel (`resolve_patch_layout`) et confronte au
    tableau litteral ci-dessus, colonne par colonne et rangee par rangee. Une
    permutation des sequences entre colonnes, un miroir gauche-droite, une rangee
    decalee ou un `divmod` inverse font echouer ce test en nommant la colonne.
    """
    template_id = page_templates.build_template_id(orientation, 2, "0", "v1")
    placed = patch_presets.resolve_patch_layout(template_id, preset_id)

    columns: dict[float, list[tuple[float, str]]] = {}
    for patch in placed:
        columns.setdefault(patch.x_mm, []).append((patch.y_mm, patch.value_id))
    got = {
        x_mm: tuple(value_id for _y, value_id in sorted(rows))
        for x_mm, rows in columns.items()
    }
    assert got == _V1_COLUMN_SEQUENCES[(orientation, preset_id)], template_id
    # Garde anti-vacuite: le tableau doit distinguer au moins deux colonnes portant des
    # sequences **differentes**, sinon l'egalite ci-dessus serait vraie sous n'importe
    # quelle permutation -- c'est exactement le defaut que ce test ferme.
    distinct = {sequence for sequence in got.values()}
    assert len(got) >= 2 and len(distinct) >= 2, got


@pytest.mark.parametrize("columns_per_side,order_name,served_columns", [
    # 12 colonnes par cote pour 9 valeurs: une seule rangee, donc **trois** colonnes
    # servies par cote et neuf vides -- mesure de la revue (24 colonnes reservees, 18
    # servies). Refus.
    (12, "_ORDER_9", None),
    # 4 colonnes pour 9 valeurs: 3 rangees, la quatrieme colonne est vide. Refus aussi,
    # bien que les valeurs « rentrent »: la quatrieme colonne a deja ete payee en
    # surface de dessin.
    (4, "_ORDER_9", None),
    # 3 colonnes pour 9 valeurs: 3 rangees, toutes les colonnes servies. Accepte -- et
    # c'est le symetrique qui prouve que la garde n'est pas devenue inconditionnelle.
    (3, "_ORDER_9", 6),
    # Le regime livre: une colonne par cote, 18 valeurs.
    (1, "_ORDER_18", 2),
])
def test_a_derived_geometry_that_reserves_a_column_without_filling_it_is_refused(
        columns_per_side: int, order_name: str, served_columns: int | None) -> None:
    """La garde de degenerescence remplace une garde **morte** (revue 5.15, couche 2).

    Celle qui vivait ici -- « la somme des tranches differe du cardinal de l'ordre » --
    ne se declenchait jamais: la division par exces garantit que les tranches couvrent
    toute la sequence, et la retirer laissait la suite entiere verte. La degenerescence
    que sa forme suggerait, elle, existait sans etre refusee: des colonnes reservees
    qui ne recoivent aucune pastille, alors que `patch_block_end_mm` a deja rentre le
    bord de la bande de dessin pour toutes les colonnes du cote.

    Inatteignable par les deux versions enregistrees (une colonne par cote en v2), donc
    le test **construit** la geometrie -- c'est le seul angle par lequel une garde de
    ce genre se verifie avant qu'une version future ne la rencontre.
    """
    geometry = dataclasses.replace(
        page_templates.GEOMETRY_V2,
        patch_columns_per_side={"portrait": columns_per_side,
                                "paysage": columns_per_side},
    )
    order = getattr(patch_presets, order_name)
    placement = patch_presets._derived_placement(geometry, "portrait", 210.0, order)

    if served_columns is None:
        assert placement is None, placement
        return
    assert placement is not None
    # Toutes les colonnes reservees sont servies, et toutes les valeurs sont posees.
    reserved = patch_presets._derived_columns_x_mm(geometry, "portrait", 210.0)
    assert len(reserved) == served_columns
    assert {x_mm for _value, x_mm, _y in placement} == set(reserved)
    assert len(placement) == 2 * len(order)


def test_every_derived_couple_serves_every_column_it_reserves() -> None:
    """La meme propriete, lue sur le registre livre plutot que sur une construction.

    Une colonne reservee et vide serait invisible autrement: elle ne chevauche rien,
    elle ne sort d'aucune marge, et elle ne fait mentir aucun cardinal de valeur.
    """
    for template_id, preset_id in patch_presets.defined_couples():
        spec = page_templates.get_template(template_id)
        if spec.geometry_version == "v1":
            continue  # colonnes litterales, hors du chemin derive
        reserved = patch_presets._derived_columns_x_mm(
            spec.geometry, spec.orientation, spec.page_width_mm)
        placed = patch_presets.resolve_patch_layout(template_id, preset_id)
        assert {patch.x_mm for patch in placed} == set(reserved), (
            template_id, preset_id)


def test_the_sentinel_placement_pairs_each_column_with_its_own_sequence() -> None:
    """`_sentinel_placement` seul, sur une fabrique a deux sequences distinguables.

    Regle des fabriques du depot: une fabrique qui ne produit qu'un element (ici: une
    seule sequence, ou deux sequences de meme contenu) rend invisible toute erreur
    d'appariement. La cible est donc posee **ailleurs qu'en premiere position** -- c'est
    la colonne d'indice 1, et son symetrique d'indice 3, qui doivent porter la seconde
    sequence.

    Le test est ecrit sur la fonction et non sur le registre parce que c'est elle qui
    porte l'appariement `index % half`: les deux angles sont utiles, celui du registre
    dit ce qui est imprime, celui-ci dit pourquoi.
    """
    columns_x_mm = (5.0, 19.0, 177.0, 191.0)
    sequences = (("gauche-haut", "gauche-bas"), ("cible-haut", "cible-bas"))

    placement = patch_presets._sentinel_placement(
        columns_x_mm, sequences, first_y_mm=30.0, step_mm=14.0
    )

    assert placement == (
        ("gauche-haut", 5.0, 30.0),
        ("gauche-bas", 5.0, 44.0),
        ("cible-haut", 19.0, 30.0),
        ("cible-bas", 19.0, 44.0),
        ("gauche-haut", 177.0, 30.0),
        ("gauche-bas", 177.0, 44.0),
        ("cible-haut", 191.0, 30.0),
        ("cible-bas", 191.0, 44.0),
    )


def test_undefined_couple_is_an_explicit_error_never_an_interpolation() -> None:
    # Piege 5: un template futur (autre format de page) ne se deduit pas par
    # rotation ni interpolation. Les couples A4 portrait ET paysage sont
    # desormais definis (story 4.1): le couple temoin est hors registre.
    with pytest.raises(patch_presets.UndefinedPlacementError) as excinfo:
        patch_presets.resolve_patch_layout("tpl-a3-paysage-4f-v1", "patches-9-v1")
    assert "tpl-a3-paysage-4f-v1" in str(excinfo.value)


def test_every_known_template_has_its_placeable_presets_defined() -> None:
    """Story 4.1: chaque template du registre doit resoudre les presets livres --
    sinon un vocabulaire CLI expose une combinaison qui echoue toujours.

    **Amende par la story 5.15**: un couple peut desormais etre *geometriquement*
    infaisable, et il est alors enumere explicitement dans `_PLACEMENT_UNPLACEABLE`
    avec son chiffre. L'ensemble des manquants est epingle **exactement** ici: le test
    echoue si la liste grandit en silence (une version future qui ne placerait plus un
    preset) comme si elle rapetisse (un couple redevenu placable sans que la liste
    suive). Un `assert in couples` seul aurait laisse passer le premier cas.
    """
    couples = set(patch_presets.defined_couples())
    missing = set()
    for template_id in page_templates.known_template_ids():
        for preset_id in patch_presets.known_preset_ids():
            if (template_id, preset_id) not in couples:
                missing.add((template_id, preset_id))
    # Le vocabulaire est lu **par version** (story 5.18): la v2 ne resout plus le
    # cardinal 6, donc l'attendu construit sur le vocabulaire global reclamerait des
    # `template_id` qui n'existent pas -- et `build_template_id` les refuserait.
    expected_missing = {
        (page_templates.build_template_id(orientation, cardinal, margin, version),
         preset_id)
        for version, orientation, preset_id in patch_presets._PLACEMENT_UNPLACEABLE
        for cardinal in page_templates.frames_per_page_vocabulary(orientation, version)
        for margin in page_templates.MARGIN_PRESETS_MM
    }
    assert missing == expected_missing
    # Le seul manquant connu, nomme: le preset sentinelle en paysage resserre.
    assert all(t.startswith("tpl-a4-paysage-") and t.endswith("-v2")
               and p == "patches-18-v2" for t, p in missing)
    # **15 depuis `EPIC5-ARB-64`** (2026-08-12): le retrait du cardinal 6 ne porte plus
    # que sur le **portrait**, donc le paysage v2 retrouve ses cinq cardinaux (1, 2, 4, 6,
    # 8) et le couple `paysage x patches-18-v2` en compte cinq par preset de marge. Le
    # chiffre etait 12 entre la story 5.18 et cet amendement, et 15 avant elle.
    assert len(missing) == 15
    assert len(missing) == len(
        page_templates.frames_per_page_vocabulary("paysage", "v2")
    ) * len(page_templates.MARGIN_PRESETS_MM)
    # Et le refus nomme la cause, plutot que de rendre les colonnes d'une autre
    # version.
    template_id, preset_id = sorted(missing)[0]
    with pytest.raises(patch_presets.UndefinedPlacementError) as excinfo:
        patch_presets.resolve_patch_layout(template_id, preset_id)
    assert preset_id in str(excinfo.value)


def test_couples_are_defined_for_the_existing_template() -> None:
    couples = patch_presets.defined_couples()
    assert (patch_presets.TEMPLATE_A4_PORTRAIT_2F, "patches-9-v1") in couples
    assert (patch_presets.TEMPLATE_A4_PORTRAIT_2F, "patches-12-v1") in couples
    assert IDENTIFIER_PATTERN.match(patch_presets.TEMPLATE_A4_PORTRAIT_2F)


# --- AC 4: non-chevauchement et zones de silence, contre layout reel ---------


def test_no_patch_overlaps_frames_markers_reserved_zones_or_page_margin() -> None:
    # Verifie chaque couple du registre contre la geometrie de SON template
    # (zones de frames calculees par le registre 4.1, marqueurs, zones
    # reservees): un couple ajoute sans re-verification geometrique fait
    # echouer la suite (le test parcourt le registre).
    for template_id, preset_id in patch_presets.defined_couples():
        spec = page_templates.get_template(template_id)
        template_forbidden = [
            (zone["x"], zone["y"], zone["width"], zone["height"])
            for zone in spec.frame_zones_mm
        ]
        template_forbidden.extend(marker_forbidden_rects(template_id))
        reserved = patch_presets.reserved_zones_mm(template_id)
        assert reserved, template_id  # QR + texte reserves, jamais vide
        template_forbidden.extend(
            (zone["x"], zone["y"], zone["width"], zone["height"]) for zone in reserved
        )
        placed = patch_presets.resolve_patch_layout(template_id, preset_id)
        rects = [patch_rect(patch) for patch in placed]

        for index, rect in enumerate(rects):
            x, y, w, h = rect
            # Marge physique d'imprimante (EPIC4-ARB-6: aucune encre a moins
            # de 5 mm du bord), constante partagee lue depuis layout.
            assert x >= layout.PRINTER_MARGIN_MM
            assert y >= layout.PRINTER_MARGIN_MM
            assert x + w <= spec.page_width_mm - layout.PRINTER_MARGIN_MM
            assert y + h <= spec.page_height_mm - layout.PRINTER_MARGIN_MM
            for zone_rect in template_forbidden:
                assert not rects_overlap(rect, zone_rect), (
                    template_id, preset_id, index, zone_rect
                )
            for other_index in range(index + 1, len(rects)):
                assert not rects_overlap(rect, rects[other_index]), (
                    template_id, preset_id, index, other_index
                )


def test_sampled_squares_stay_clear_of_every_printed_edge() -> None:
    """Garantie geometrique d'echantillonnage (story 5.9, AC 9 second bloc).

    **Ce test remplace `test_no_two_adjacent_saturated_patches_in_any_couple`**,
    qui verifiait qu'aucune paire de pastilles saturees ne partage un bord
    (piege 3 de la story 4.7, precaution contre la bave d'encre). Cette
    interdiction categorique est **amendee par EPIC5-ARB-17(a)**: la bave
    contamine la frontiere entre deux pastilles, jamais leur centre, et la
    protection passe donc du **placement** a la **geometrie d'echantillonnage**
    -- l'idiome des gammes de controle industrielles, qui posent leurs
    pastilles bord a bord parce que le spectrophotometre lit le centre.

    Deux raisons de l'avoir remplace plutot que garde en plus. (1) Il faisait
    doublon avec un contrat ecrit **apres** lui: la story de calibration
    exigeait deja une marge d'echantillonnage interieure, sans chiffre — le
    chiffre est desormais ici. (2) Son predicat de separateur etait couple au
    **nommage** (`value_id.startswith("neutral-")`) et n'aurait reconnu ni
    `sentinel-black-1` ni `sentinel-white-1`, pourtant achromatiques.

    Condition de retour, pour qu'un futur lecteur n'ait pas a la redecouvrir:
    si le premier pilote papier mesure une bave superieure a
    `SAMPLING_INSET_MM` sur le cas le pire (rouge pur RVB, donc deux encres
    superposees, voisin d'une autre chromie), le premier repli est d'augmenter
    ce retrait; le retour a l'alternance n'est que le troisieme, et il
    imposerait de revenir aussi sur la configuration de `patch-values-2`
    (12 valeurs chromatiques contre 9 places par le damier).
    """
    assert patch_presets.SAMPLED_SIDE_MM == (
        patch_presets.PATCH_SIZE_MM - 2 * patch_presets.SAMPLING_INSET_MM)
    assert patch_presets.SAMPLED_SIDE_MM > 0

    for template_id, preset_id in patch_presets.defined_couples():
        placed = patch_presets.resolve_patch_layout(template_id, preset_id)
        # Retrait et cote **reels** de la pastille de ce gabarit, rendus par la
        # fonction de production (`color_calibration.sampled_square_mm`) et non
        # re-derives ici: depuis la story 5.15 une pastille peut faire 6 mm, et le
        # retrait suit proportionnellement. Recopier la derivation dans le test
        # laisserait passer une divergence entre les deux.
        inset, side = color_calibration.sampled_square_mm(
            page_templates.get_template(template_id).geometry.patch_size_mm)
        assert side > 0, (template_id, preset_id)
        for index, patch in enumerate(placed):
            # Le carre echantillonne, centre sur l'emprise imprimee.
            sx1 = patch.x_mm + inset
            sy1 = patch.y_mm + inset
            sx2 = sx1 + side
            sy2 = sy1 + side

            # (a) Contre son PROPRE bord: la distance vaut exactement l'inset.
            # C'est la contrainte mordante, celle qui fixe le chiffre.
            assert sx1 - patch.x_mm == pytest.approx(inset), (template_id, preset_id, index)
            assert (patch.x_mm + patch.size_mm) - sx2 == pytest.approx(inset)
            assert sy1 - patch.y_mm == pytest.approx(inset)
            assert (patch.y_mm + patch.size_mm) - sy2 == pytest.approx(inset)

            # (b) Contre le bord de TOUTE autre pastille de la page: au moins
            # inset + PATCH_SPACING_MM, l'espacement etant deja garanti par
            # test_patches_keep_the_minimum_printing_gap.
            for other in placed[index + 1 :]:
                ox1, oy1 = other.x_mm, other.y_mm
                ox2, oy2 = ox1 + other.size_mm, oy1 + other.size_mm
                # Distance de rectangle a rectangle (0 s'ils se recouvrent).
                dx = max(ox1 - sx2, sx1 - ox2, 0.0)
                dy = max(oy1 - sy2, sy1 - oy2, 0.0)
                distance = math.hypot(dx, dy) if (dx and dy) else max(dx, dy)
                spacing = page_templates.get_template(
                    template_id).geometry.patch_spacing_mm
                assert distance >= inset + spacing - 1e-9, (
                    template_id, preset_id, patch.value_id, other.value_id, distance,
                )


def test_the_white_sentinel_frame_is_inside_the_patch_and_outside_the_sampled_square() -> None:
    """Deux inclusions chiffrees, pas supposees (story 5.9, AC 5).

    Un patch (255,255,255) est une absence d'encre: sans cadre il n'existe ni
    pour l'oeil ni pour l'echantillonnage. Mais un cadre **exterieur**
    mangerait `PATCH_SPACING_MM` et ferait tomber la garantie d'espacement
    d'impression. Il est donc interieur, et le carre echantillonne doit lui
    rester interieur a son tour.
    """
    frame = patch_presets.PATCH_FRAME_MM
    inset = patch_presets.SAMPLING_INSET_MM
    assert 0 < frame < inset, "le cadre doit tenir dans le retrait d'echantillonnage"
    # Marge entre le bord interieur du cadre et le carre echantillonne, sur la
    # pastille de 12 mm de la v1: le chiffre historique de la story 5.9.
    assert inset - frame == pytest.approx(2.0)

    framed_seen = 0
    for template_id, preset_id in patch_presets.defined_couples():
        placed = patch_presets.resolve_patch_layout(template_id, preset_id)
        # Depuis la story 5.15 la pastille peut faire 6 mm: le retrait suit
        # proportionnellement, donc les deux inclusions se verifient contre le
        # retrait REEL de ce gabarit et non contre celui de la v1. La marge du
        # cadre au carre echantillonne tombe alors a 0,5 mm (6 mm de pastille:
        # retrait 1,5, cadre 1,0) -- serre, mais strictement positif, et
        # l'inclusion reste vraie.
        real_inset, real_side = color_calibration.sampled_square_mm(
            page_templates.get_template(template_id).geometry.patch_size_mm)
        for patch in placed:
            if not patch.frame_mm:
                continue
            framed_seen += 1
            assert patch.value_id == "sentinel-white-1", patch.value_id
            assert patch.frame_mm == frame
            # Le cadre est trace a l'interieur de l'emprise: il n'empiete pas
            # sur l'espacement inter-pastilles.
            assert patch.frame_mm * 2 < patch.size_mm
            # ...et le carre echantillonne reste interieur au cadre.
            assert real_inset > patch.frame_mm, (template_id, preset_id)
            assert real_side + 2 * patch.frame_mm < patch.size_mm

    # Aucune autre pastille n'en porte, et **tout** preset qui porte la sentinelle
    # blanche en porte deux par page (repetition 2) sur chacun des gabarits ou il est
    # place. Le compte attendu est **derive** du contenu des presets depuis la story
    # 5.16, et non plus epingle sur le seul `patches-18-v2`: le preset temoin
    # `patches-14-v3` porte la meme sentinelle, donc un compte fonde sur un nom de
    # preset devenait faux au premier preset ajoute -- alors que la propriete verifiee
    # (« le cadre est decide par la valeur, jamais par le preset ») ne parle d'aucun
    # nom.
    framed_couples = [
        1 for template_id, preset_id in patch_presets.defined_couples()
        if any(
            patch_values.requires_printed_frame(
                patch_values.get_patch_values_table(
                    patch_presets.get_patch_preset(preset_id).values_version
                ).get(value_id)
            )
            for value_id in patch_presets.get_patch_preset(preset_id).value_ids
        )
    ]
    assert framed_seen == 2 * len(framed_couples)
    # Les deux presets qui portent la sentinelle blanche, et leurs gabarits: 33 v1 +
    # 15 v2 portrait pour `patches-18-v2` (paysage v2 ne le place pas), 33 v1 + 30 v2
    # pour `patches-14-v3`, qui tient dans les deux orientations -- c'est precisement
    # ce que la story 5.16 achete.
    #
    # **Amende par la story 5.23**: un TROISIEME preset porte la sentinelle blanche,
    # `patches-17-v4`, place lui aussi sur les 33 gabarits de la v1 et les 30 de la v2
    # -- ses 17 rangees par cote tiennent dans les deux orientations, le paysage v2 a
    # une rangee pres (capacite laterale exactement 17).
    assert framed_seen == 2 * ((33 + 15) + (33 + 30) + (33 + 30))

    # Le cadre est decide par la valeur, pas par le preset: le predicat vit
    # dans patch_values, seul point de verite des triplets.
    table = patch_values.get_patch_values_table("patch-values-2")
    framed_values = [v.value_id for v in table.values if patch_values.requires_printed_frame(v)]
    assert framed_values == ["sentinel-white-1"]


@pytest.mark.parametrize("patch_size_mm,inset_mm,side_mm,pixels_at_600dpi,frame_gap_mm", [
    # La pastille de 12 mm: les chiffres historiques de la story 5.9, ceux que le
    # commentaire de `SAMPLING_INSET_MM` donne en premier.
    (12.0, 3.0, 6.0, 142, 2.0),
    # La pastille de 6 mm d'une geometrie resserree: **tous** les chiffres changent,
    # proportionnellement, et trois enonces du commentaire s'y inversaient avant la
    # passe de correction de 5.15 (le retrait valait « 1,5 fois l'espacement », il en
    # vaut 0,5; le carre « ~142 px », il en fait 71; la garde du cadre 2,0 mm, elle
    # tombe a 0,5). Les epingler ici est ce qui empeche le commentaire de redevenir
    # faux en silence: aucun autre test ne compare ces valeurs a des litteraux -- ils
    # derivent tous l'attendu de la fonction de production elle-meme.
    (6.0, 1.5, 3.0, 71, 0.5),
])
def test_the_sampling_geometry_of_each_patch_size_is_pinned_in_absolute_terms(
        patch_size_mm: float, inset_mm: float, side_mm: float,
        pixels_at_600dpi: int, frame_gap_mm: float) -> None:
    """Les chiffres du commentaire de `SAMPLING_INSET_MM`, confrontes a la production.

    Aucun **plancher absolu** n'est pose sur le cote du carre echantillonne, et ce test
    n'en pose pas non plus: un plancher est un seuil, un seuil se mesure sur du papier
    (bave reelle sur un rouge pur voisin d'une autre chromie), et le poser au jugement
    serait le defaut d'`EPIC5-ARB-52`. Le point est verse au `deferred-work.md`. Ce que
    ce test tient, c'est que les chiffres ecrits dans le module sont ceux que la
    production rend -- sur les deux tailles de pastille du depot, pas seulement sur
    celle du defaut.
    """
    inset, side = color_calibration.sampled_square_mm(patch_size_mm)
    assert inset == pytest.approx(inset_mm)
    assert side == pytest.approx(side_mm)
    assert round(side / 25.4 * 600) == pixels_at_600dpi
    # Garde entre le cadre imprime de la sentinelle blanche et le carre mesure.
    assert inset - patch_presets.PATCH_FRAME_MM == pytest.approx(frame_gap_mm)
    assert inset - patch_presets.PATCH_FRAME_MM > 0, (
        "le cadre imprime mordrait le carre mesure")
    # Le rapport au pas de pastille de la geometrie qui porte cette taille: c'est
    # l'enonce qui s'inversait (1,5 fois l'espacement en v1, 0,5 fois en v2).
    geometry = next(
        g for g in page_templates.GEOMETRY_VERSIONS.values()
        if g.patch_size_mm == patch_size_mm
    )
    expected_ratio = 1.5 if patch_size_mm == 12.0 else 0.5
    assert inset / geometry.patch_spacing_mm == pytest.approx(expected_ratio)


def test_no_patch_in_a_shipped_preset_ever_carries_a_frame() -> None:
    # « Purement additif »: `PlacedPatch.frame_mm` a un defaut neutre et aucun
    # preset anterieur a 5.9 ne change de rendu.
    #
    # Story 5.16: l'exclusion porte desormais sur les presets **sentinelles** -- ceux
    # qui referencent `patch-values-2` ou `-3`, donc la sentinelle blanche -- et non
    # sur le seul `patches-18-v2`. Ce que ce test verrouille est la non-regression des
    # presets **anterieurs a 5.9**, et cette propriete ne parle pas du nombre de
    # presets livres depuis: la nommer par une liste noire la faisait tomber au
    # premier ajout.
    for template_id, preset_id in patch_presets.defined_couples():
        # `patches-17-v4` rejoint la liste a la story 5.23, pour la meme raison que
        # les deux autres: il epingle `patch-values-4`, donc la sentinelle blanche.
        if preset_id in ("patches-18-v2", "patches-14-v3", "patches-17-v4"):
            continue
        for patch in patch_presets.resolve_patch_layout(template_id, preset_id):
            assert patch.frame_mm == 0.0, (template_id, preset_id, patch.value_id)


def test_reserved_zones_cover_qr_and_text() -> None:
    # Portrait ET paysage (revue 4.7: seul le template historique etait
    # couvert, une edition des zones paysage passait la suite).
    for template_id in (
        patch_presets.TEMPLATE_A4_PORTRAIT_2F,
        page_templates.build_template_id("paysage", 2, "0"),
    ):
        reserved = patch_presets.reserved_zones_mm(template_id)
        names = {zone["name"] for zone in reserved}
        assert any("qr" in name for name in names), template_id
        assert any("text" in name or "footer" in name for name in names), template_id
        # La bande QR reserve au moins la cible 4.6 (35 mm) plus sa quiet zone.
        qr_zone = next(zone for zone in reserved if "qr" in zone["name"])
        assert qr_zone["width"] >= 35.0, template_id
        assert qr_zone["height"] >= 35.0, template_id


def test_reserved_zones_refuse_unknown_templates_and_return_copies() -> None:
    # Revue 4.7: `.get(..., ())` rendait une liste vide silencieuse pour un
    # template mal orthographie, et les dicts internes etaient partages entre
    # tous les templates d'une orientation (mutation par un appelant =
    # corruption du registre pour tout le processus).
    with pytest.raises(patch_presets.UndefinedPlacementError):
        patch_presets.reserved_zones_mm("tpl-a3-paysage-4f-v1")
    first = patch_presets.reserved_zones_mm(patch_presets.TEMPLATE_A4_PORTRAIT_2F)
    first[0]["x"] = 999.0
    second = patch_presets.reserved_zones_mm(patch_presets.TEMPLATE_A4_PORTRAIT_2F)
    assert second[0]["x"] != 999.0


def test_patches_keep_the_minimum_printing_gap() -> None:
    # PATCH_SPACING_MM est consigne comme contrainte d'impression (revue 4.7:
    # seul le non-chevauchement strict etait teste, un ecart de 0 mm passait).
    # Deux pastilles doivent etre separees d'au moins l'espacement sur au
    # moins un axe.
    spacing = patch_presets.PATCH_SPACING_MM
    for template_id, preset_id in patch_presets.defined_couples():
        placed = patch_presets.resolve_patch_layout(template_id, preset_id)
        for i in range(len(placed)):
            for j in range(i + 1, len(placed)):
                a, b = placed[i], placed[j]
                gap_x = max(b.x_mm - (a.x_mm + a.size_mm), a.x_mm - (b.x_mm + b.size_mm))
                gap_y = max(b.y_mm - (a.y_mm + a.size_mm), a.y_mm - (b.y_mm + b.size_mm))
                assert max(gap_x, gap_y) >= spacing - 1e-9, (
                    template_id, preset_id, i, j
                )


def test_resolution_enforces_repetition_and_the_arb_6_ceiling() -> None:
    # Revue 4.7: repetition et plafond de pastilles ne vivaient que dans les
    # tests; ils sont desormais confrontes a l'execution par
    # resolve_patch_layout (un placement incoherent avec son preset refuse).
    # Le plafond vaut 36 depuis EPIC5-ARB-14 (story 5.9), et il est atteint
    # exactement par `patches-18-v2`.
    broken = patch_presets.PatchPreset(
        preset_id="patches-9-v1",
        values_version="patch-values-1",
        value_ids=patch_presets.get_patch_preset("patches-9-v1").value_ids,
        repetition=3,
    )
    original = patch_presets._PRESETS["patches-9-v1"]
    patch_presets._PRESETS["patches-9-v1"] = broken
    try:
        with pytest.raises(patch_presets.UndefinedPlacementError) as excinfo:
            patch_presets.resolve_patch_layout(
                patch_presets.TEMPLATE_A4_PORTRAIT_2F, "patches-9-v1"
            )
        assert "repetition" in str(excinfo.value)
    finally:
        patch_presets._PRESETS["patches-9-v1"] = original


def test_marker_quiet_zone_constant_exists_and_matches_the_43_measurement() -> None:
    # La story 4.7 cree la constante manquante: MARKER_MARGIN_MM est la
    # distance bord-de-page -> marqueur, pas la marge de silence interieure.
    assert layout.MARKER_QUIET_ZONE_MM == 15.0
    assert layout.PRINTER_MARGIN_MM == 5.0


# --- AC 5: taille de patch dimensionnee et consignee -------------------------


def test_patch_size_is_a_registry_constant_within_the_instructed_range() -> None:
    assert 10.0 <= patch_presets.PATCH_SIZE_MM <= 15.0
    assert patch_presets.PATCH_SPACING_MM > 0
    # Depuis la story 5.15 la taille imprimee est celle de la **geometrie du
    # gabarit** et non la constante du module: une version resserree pose des
    # pastilles de 6 mm, et c'est cette taille qui a servi a calculer sa bande de
    # frames. Le test verifie donc l'egalite avec la geometrie -- et qu'au moins deux
    # tailles distinctes existent au registre, sinon il ne prouverait rien de plus
    # que la version qu'il lit.
    seen = set()
    for template_id, preset_id in patch_presets.defined_couples():
        geometry = page_templates.get_template(template_id).geometry
        for patch in patch_presets.resolve_patch_layout(template_id, preset_id):
            assert patch.size_mm == geometry.patch_size_mm, (template_id, preset_id)
        seen.add(geometry.patch_size_mm)
    assert len(seen) >= 2, seen
    assert patch_presets.PATCH_SIZE_MM in seen


# --- AC 6: consommable sans copie, valeurs lues depuis la table 4.8 ----------


def test_resolution_returns_values_read_from_the_table_never_stored() -> None:
    # Amende par la story 5.9 (AC 2b). Le test lisait les triplets dans
    # `active_table()` alors qu'il resout un preset epingle sur la v1: tant
    # qu'il n'existait qu'une table, les deux coincidaient. La bascule d'alias
    # revele ce couplage latent — `active_table().get("neutral-065")` leve
    # desormais `UnknownPatchValueError`, la v2 ayant reduit l'axe neutre.
    #
    # La bonne table est celle **que le preset epingle**, ce que
    # `resolve_patch_layout` fait deja de son cote. Ce n'est pas une
    # regression: c'est le test qui prenait un raccourci que la seconde table
    # rend faux. Verifie sur les deux presets et donc sur les deux versions.
    for preset_id in ("patches-12-v1", "patches-9-v1"):
        preset = patch_presets.get_patch_preset(preset_id)
        table = patch_values.get_patch_values_table(preset.values_version)
        placed = patch_presets.resolve_patch_layout(
            patch_presets.TEMPLATE_A4_PORTRAIT_2F, preset_id
        )
        assert placed
        for patch in placed:
            assert patch.rgb == table.get(patch.value_id).rgb


def test_module_is_pure_and_does_not_import_the_rendering_stack() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"), filename=str(MODULE_PATH))
    # layout importe cv2: le registre doit rester pur, le test geometrique
    # confronte layout de son cote. Revue 4.7: les formes absolues
    # (`import mixed_media_utility.layout`, `from mixed_media_utility import
    # layout`) contournaient le garde -- les alias sont controles sur TOUTES
    # les formes d'import, pas seulement les relatives.
    forbidden = {"cv2", "PIL", "reportlab", "numpy", "layout"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for segment in alias.name.split("."):
                    assert segment not in forbidden, alias.name
        if isinstance(node, ast.ImportFrom):
            for segment in (node.module or "").split("."):
                assert segment not in forbidden, node.module
            for alias in node.names:
                assert alias.name not in forbidden, alias.name


def test_registry_stores_no_color_triplet() -> None:
    # Piege 4: dupliquer les triplets sRGB dans les presets recree le motif
    # "deux sources de verite". Le registre ne reference que des identifiants.
    preset = patch_presets.get_patch_preset("patches-12-v1")
    assert not hasattr(preset, "rgb")
    for value_id in preset.value_ids:
        assert isinstance(value_id, str)


# --- Story 5.9, AC 15: « purement additif » verifie plutot qu'affirme -------
#
# Empreintes des 66 couples (template x preset) tels qu'ils resolvaient AVANT
# la story 5.9, relevees sur l'arbre 16f35db (dernier commit avant cette
# story) et non recopiees a la main.
# Chaque empreinte couvre, dans l'ordre du placement, le quintuplet
# (value_id, rgb, x_mm, y_mm, size_mm) de chaque pastille: un triplet qui
# change, une pastille qui se deplace d'un dixieme de millimetre ou un ordre
# de colonne inverse font tomber le test.
#
# Ce que ce test protege exactement: l'invariant 2 d'EPIC5-ARB-14, « les deux
# presets livres conservent exactement leurs placements ». Le preset sentinelle
# repose sa propre geometrie de colonnes precisement pour que ce soit vrai.
PLACEMENT_FINGERPRINTS_BEFORE_5_9 = (
    ("patches-12-v1", "tpl-a4-paysage-1f-m2-v1", "3c564307a9e2c32a"),
    ("patches-9-v1", "tpl-a4-paysage-1f-m2-v1", "b27f193168ef3663"),
    ("patches-12-v1", "tpl-a4-paysage-1f-m5-v1", "3c564307a9e2c32a"),
    ("patches-9-v1", "tpl-a4-paysage-1f-m5-v1", "b27f193168ef3663"),
    ("patches-12-v1", "tpl-a4-paysage-1f-v1", "3c564307a9e2c32a"),
    ("patches-9-v1", "tpl-a4-paysage-1f-v1", "b27f193168ef3663"),
    ("patches-12-v1", "tpl-a4-paysage-2f-m2-v1", "3c564307a9e2c32a"),
    ("patches-9-v1", "tpl-a4-paysage-2f-m2-v1", "b27f193168ef3663"),
    ("patches-12-v1", "tpl-a4-paysage-2f-m5-v1", "3c564307a9e2c32a"),
    ("patches-9-v1", "tpl-a4-paysage-2f-m5-v1", "b27f193168ef3663"),
    ("patches-12-v1", "tpl-a4-paysage-2f-v1", "3c564307a9e2c32a"),
    ("patches-9-v1", "tpl-a4-paysage-2f-v1", "b27f193168ef3663"),
    ("patches-12-v1", "tpl-a4-paysage-4f-m2-v1", "3c564307a9e2c32a"),
    ("patches-9-v1", "tpl-a4-paysage-4f-m2-v1", "b27f193168ef3663"),
    ("patches-12-v1", "tpl-a4-paysage-4f-m5-v1", "3c564307a9e2c32a"),
    ("patches-9-v1", "tpl-a4-paysage-4f-m5-v1", "b27f193168ef3663"),
    ("patches-12-v1", "tpl-a4-paysage-4f-v1", "3c564307a9e2c32a"),
    ("patches-9-v1", "tpl-a4-paysage-4f-v1", "b27f193168ef3663"),
    ("patches-12-v1", "tpl-a4-paysage-6f-m2-v1", "3c564307a9e2c32a"),
    ("patches-9-v1", "tpl-a4-paysage-6f-m2-v1", "b27f193168ef3663"),
    ("patches-12-v1", "tpl-a4-paysage-6f-m5-v1", "3c564307a9e2c32a"),
    ("patches-9-v1", "tpl-a4-paysage-6f-m5-v1", "b27f193168ef3663"),
    ("patches-12-v1", "tpl-a4-paysage-6f-v1", "3c564307a9e2c32a"),
    ("patches-9-v1", "tpl-a4-paysage-6f-v1", "b27f193168ef3663"),
    ("patches-12-v1", "tpl-a4-paysage-8f-m2-v1", "3c564307a9e2c32a"),
    ("patches-9-v1", "tpl-a4-paysage-8f-m2-v1", "b27f193168ef3663"),
    ("patches-12-v1", "tpl-a4-paysage-8f-m5-v1", "3c564307a9e2c32a"),
    ("patches-9-v1", "tpl-a4-paysage-8f-m5-v1", "b27f193168ef3663"),
    ("patches-12-v1", "tpl-a4-paysage-8f-v1", "3c564307a9e2c32a"),
    ("patches-9-v1", "tpl-a4-paysage-8f-v1", "b27f193168ef3663"),
    ("patches-12-v1", "tpl-a4-portrait-1f-m2-v1", "982ed8da2a4af012"),
    ("patches-9-v1", "tpl-a4-portrait-1f-m2-v1", "64ed8fc77304029f"),
    ("patches-12-v1", "tpl-a4-portrait-1f-m5-v1", "982ed8da2a4af012"),
    ("patches-9-v1", "tpl-a4-portrait-1f-m5-v1", "64ed8fc77304029f"),
    ("patches-12-v1", "tpl-a4-portrait-1f-v1", "982ed8da2a4af012"),
    ("patches-9-v1", "tpl-a4-portrait-1f-v1", "64ed8fc77304029f"),
    ("patches-12-v1", "tpl-a4-portrait-2f-m2-v1", "982ed8da2a4af012"),
    ("patches-9-v1", "tpl-a4-portrait-2f-m2-v1", "64ed8fc77304029f"),
    ("patches-12-v1", "tpl-a4-portrait-2f-m5-v1", "982ed8da2a4af012"),
    ("patches-9-v1", "tpl-a4-portrait-2f-m5-v1", "64ed8fc77304029f"),
    ("patches-12-v1", "tpl-a4-portrait-2f-v1", "982ed8da2a4af012"),
    ("patches-9-v1", "tpl-a4-portrait-2f-v1", "64ed8fc77304029f"),
    ("patches-12-v1", "tpl-a4-portrait-3f-m2-v1", "982ed8da2a4af012"),
    ("patches-9-v1", "tpl-a4-portrait-3f-m2-v1", "64ed8fc77304029f"),
    ("patches-12-v1", "tpl-a4-portrait-3f-m5-v1", "982ed8da2a4af012"),
    ("patches-9-v1", "tpl-a4-portrait-3f-m5-v1", "64ed8fc77304029f"),
    ("patches-12-v1", "tpl-a4-portrait-3f-v1", "982ed8da2a4af012"),
    ("patches-9-v1", "tpl-a4-portrait-3f-v1", "64ed8fc77304029f"),
    ("patches-12-v1", "tpl-a4-portrait-4f-m2-v1", "982ed8da2a4af012"),
    ("patches-9-v1", "tpl-a4-portrait-4f-m2-v1", "64ed8fc77304029f"),
    ("patches-12-v1", "tpl-a4-portrait-4f-m5-v1", "982ed8da2a4af012"),
    ("patches-9-v1", "tpl-a4-portrait-4f-m5-v1", "64ed8fc77304029f"),
    ("patches-12-v1", "tpl-a4-portrait-4f-v1", "982ed8da2a4af012"),
    ("patches-9-v1", "tpl-a4-portrait-4f-v1", "64ed8fc77304029f"),
    ("patches-12-v1", "tpl-a4-portrait-6f-m2-v1", "982ed8da2a4af012"),
    ("patches-9-v1", "tpl-a4-portrait-6f-m2-v1", "64ed8fc77304029f"),
    ("patches-12-v1", "tpl-a4-portrait-6f-m5-v1", "982ed8da2a4af012"),
    ("patches-9-v1", "tpl-a4-portrait-6f-m5-v1", "64ed8fc77304029f"),
    ("patches-12-v1", "tpl-a4-portrait-6f-v1", "982ed8da2a4af012"),
    ("patches-9-v1", "tpl-a4-portrait-6f-v1", "64ed8fc77304029f"),
    ("patches-12-v1", "tpl-a4-portrait-8f-m2-v1", "982ed8da2a4af012"),
    ("patches-9-v1", "tpl-a4-portrait-8f-m2-v1", "64ed8fc77304029f"),
    ("patches-12-v1", "tpl-a4-portrait-8f-m5-v1", "982ed8da2a4af012"),
    ("patches-9-v1", "tpl-a4-portrait-8f-m5-v1", "64ed8fc77304029f"),
    ("patches-12-v1", "tpl-a4-portrait-8f-v1", "982ed8da2a4af012"),
    ("patches-9-v1", "tpl-a4-portrait-8f-v1", "64ed8fc77304029f"),
)


def test_shipped_presets_resolve_exactly_as_before_story_5_9() -> None:
    import hashlib

    assert len(PLACEMENT_FINGERPRINTS_BEFORE_5_9) == 66
    for preset_id, template_id, fingerprint in PLACEMENT_FINGERPRINTS_BEFORE_5_9:
        placed = patch_presets.resolve_patch_layout(template_id, preset_id)
        data = [(p.value_id, p.rgb, p.x_mm, p.y_mm, p.size_mm) for p in placed]
        observed = hashlib.sha256(repr(data).encode()).hexdigest()[:16]
        assert observed == fingerprint, (preset_id, template_id)


def test_the_new_preset_added_couples_without_removing_any() -> None:
    couples = set(patch_presets.defined_couples())
    before = {(t, p) for p, t, _ in PLACEMENT_FINGERPRINTS_BEFORE_5_9}
    assert before <= couples
    # 99 couples avant la story 5.15 (33 gabarits x 3 presets), **174 depuis
    # `EPIC5-ARB-64`**: la v2 ajoute **30** gabarits (10 couples orientation x cardinal --
    # le cardinal 6 n'etant sorti que du vocabulaire **portrait**) x 3 presets, moins les
    # 15 couples paysage x `patches-18-v2` qu'elle ne peut pas placer (18 rangees de 6 mm
    # au pas de 9 exigent 159 mm pour 151 disponibles dans le couloir lateral). Aucun
    # couple v1 ne disparait, ce que verifie l'inclusion ci-dessus -- et c'est la
    # propriete qui compte: retirer un cardinal du vocabulaire d'une version et d'une
    # orientation ne retire rien aux autres.
    #
    # Historique du chiffre, pour que la prochaine session sache le relire: 168 entre la
    # story 5.18 et l'amendement (27 gabarits, 12 couples infaisables), puis 174.
    #
    # **237 depuis la story 5.16**, qui ajoute un quatrieme preset (`patches-14-v3`)
    # place sur les 33 gabarits de la v1 **et** les 30 de la v2: 4 presets x 63
    # gabarits, moins les 15 couples paysage x `patches-18-v2` infaisables. Le preset
    # temoin est le seul des quatre a tenir dans les **deux** orientations de la v2,
    # et c'est exactement ce que la story achete -- voir
    # `test_the_witness_preset_makes_the_v2_landscape_composable`.
    #
    # **300 depuis la story 5.23**, qui ajoute un cinquieme preset (`patches-17-v4`),
    # place lui aussi sur les 33 gabarits de la v1 et les 30 de la v2: 5 presets x 63
    # gabarits, moins les 15 couples paysage x `patches-18-v2` toujours infaisables.
    assert len(couples) == 5 * (33 + 30) - 15
    assert len(couples) == 300
    assert len([1 for t, _ in couples if t.endswith("-v1")]) == 5 * 33
    # 5.23: deux fois 33 couples v1 nouveaux (les presets `patches-14-v3` et
    # `patches-17-v4`, tous deux absents de l'empreinte d'avant 5.9) et 5 x 30 - 15
    # couples v2.
    assert len(couples - before) == 33 + (5 * 30 - 15) + 33 + 33


def test_the_reserved_header_band_follows_the_top_band_never_the_qr() -> None:
    """**`K10`**: la bande d'entete des zones reservees suit **le haut**, pas le QR.

    Le mutant lit `qr_band_mm(spec)` la ou la production lit `header_band_mm(spec)`, donc
    la zone de texte d'entete reservee **suit le QR** au lieu de rester en haut de page. Il
    **survivait** a toute la suite: les zones reservees bornent le placement des pastilles,
    et deplacer une zone de texte vers le bord bas ou un flanc ne cree pas de conflit avec
    les colonnes laterales -- donc rien n'echoue. Ce qui est perdu est la reservation
    elle-meme: la bande haute, ou l'entete s'imprime vraiment, cesse d'etre protegee, et
    une reservation fausse est pire qu'absente parce qu'elle a l'air d'une garde.

    Le test est **discriminant par construction**: il verifie d'abord que les deux bandes
    different sur les gabarits livres (le QR n'est jamais au bord haut), puis que la zone
    reservee est bien celle du **haut**. Sans le premier volet, l'assertion serait vide sur
    un gabarit ou les deux coincident.
    """
    v2_templates = [t for t in page_templates.known_template_ids() if t.endswith("-v2")]
    assert v2_templates
    vus = 0
    for template_id in v2_templates:
        spec = page_templates.get_template(template_id)
        haute = page_templates.header_band_mm(spec)
        bande_qr = page_templates.qr_band_mm(spec)
        # Aucun gabarit livre ne met le QR au bord haut, donc les deux bandes different
        # partout: c'est ce qui rend l'assertion suivante mordante.
        assert spec.qr_edge != page_templates.QR_EDGE_TOP, template_id
        assert tuple(bande_qr) != tuple(haute), template_id
        zones = {zone["name"]: zone for zone in patch_presets.reserved_zones_mm(template_id)}
        # Quand le QR n'est pas en haut, la bande haute est libre sur toute sa largeur et
        # porte une zone unique `text_header`.
        assert "text_header" in zones, (template_id, sorted(zones))
        assert "text_header_left" not in zones and "text_header_right" not in zones
        entete = zones["text_header"]
        assert (entete["x"], entete["y"], entete["width"], entete["height"]) == pytest.approx(
            tuple(haute)), template_id
        # Et la zone du QR, elle, suit bien le QR: les deux reservations ne se confondent
        # pas, ce qui est exactement ce que le mutant fait.
        qr_zone = zones["qr_zone"]
        assert (qr_zone["x"], qr_zone["y"]) != pytest.approx((entete["x"], entete["y"])), (
            template_id)
        vus += 1
    assert vus == len(v2_templates)


# ---------------------------------------------------------------------------
# Story 5.23 (AC 1, `EPIC5-ARB-82`) : le meme bandeau de temoins sur TOUTES les
# feuilles, secondaires comprises
# ---------------------------------------------------------------------------


def _gabarits_v2() -> tuple[str, ...]:
    """Les gabarits qui portent une page de calibration: la v2, et elle seule.

    Enumeres par une propriete (`calibration_page_refusal` ne refuse pas) plutot que par
    une liste: une version ajoutee au registre entrerait alors dans le balayage au lieu
    d'etre oubliee.
    """
    return tuple(
        template_id
        for template_id in page_templates.known_template_ids()
        if patch_presets.calibration_page_refusal(template_id) is None
    )


def test_le_preset_temoin_elargi_porte_les_quatorze_valeurs_plus_les_secondaires():
    """AC 1 (b): `patches-17-v4` = `patches-14-v3` + cyan, magenta, jaune.

    L'inclusion est verifiee par **egalite d'ensembles**, jamais par cardinal: deux jeux
    de dix-sept valeurs peuvent differer sans que 17 == 17 ne le voie.
    """
    ancien = patch_presets.get_patch_preset("patches-14-v3")
    nouveau = patch_presets.get_patch_preset("patches-17-v4")
    secondaires = {"secondary-cyan", "secondary-magenta", "secondary-yellow"}
    assert set(nouveau.value_ids) == set(ancien.value_ids) | secondaires
    assert len(nouveau.value_ids) == len(set(nouveau.value_ids)) == 17
    assert nouveau.repetition == ancien.repetition == 2

    # Les triplets ne sont pas inventes: ce sont ceux de la table **active**, ou les
    # trois secondaires existent depuis `patch-values-1`.
    active = patch_values.active_table()
    table = patch_values.get_patch_values_table(nouveau.values_version)
    for value_id in sorted(secondaires):
        assert table.get(value_id).rgb == active.get(value_id).rgb
        assert table.get(value_id).role == patch_values.ROLE_SECONDARY


def test_patches_14_v3_reste_enregistre_et_inchange_par_la_story_5_23():
    """AC 1, frontiere negative: un nouveau jeu est un **nouveau** preset.

    Rebrancher un preset existant sur de nouvelles valeurs est l'edition en place que le
    versionnement de 4.8 existe pour interdire: une planche deja imprimee declare ses
    valeurs transitivement par son `patch_preset_id`.
    """
    ancien = patch_presets.get_patch_preset("patches-14-v3")
    assert ancien.values_version == "patch-values-3"
    assert ancien.value_ids == (
        "primary-red", "sentinel-red-1", "sentinel-red-2",
        "primary-green", "sentinel-green-1", "sentinel-green-2",
        "neutral-065",
        "primary-blue", "sentinel-blue-1", "sentinel-blue-2",
        "neutral-020", "sentinel-black-1",
        "neutral-245", "sentinel-white-1",
    )
    # Et aucune secondaire n'y est entree par la bande.
    assert not {"secondary-cyan", "secondary-magenta", "secondary-yellow"} & set(
        ancien.value_ids)
    # La table qu'il epingle est intacte elle aussi: la v4 est une **quatrieme** entree,
    # pas une reecriture de la troisieme.
    v3 = patch_values.get_patch_values_table("patch-values-3")
    assert len(v3.values) == 14
    assert patch_values.get_patch_values_table("patch-values-4") is not v3


def test_la_page_de_calibration_et_la_planche_portent_le_meme_jeu_de_temoins():
    """AC 1, test d'identite du jeu: **memes triplets**, jamais une egalite de nom.

    C'est la propriete qui rend la mesure brute a brute calculable: avant cette story,
    les deux feuilles n'avaient **aucun** identifiant de valeur en commun (65 valeurs de
    treillis contre 14 temoins) et un seul triplet RGB commun.
    """
    preset_id = "patches-17-v4"
    for template_id in _gabarits_v2():
        planche = patch_presets.resolve_patch_layout(template_id, preset_id)
        page = patch_presets.resolve_calibration_page_witnesses(template_id, preset_id)
        # Le meme jeu de couleurs, valeur par valeur, et les memes cardinaux par valeur.
        planche_par_valeur: dict[str, list[tuple[int, int, int]]] = {}
        page_par_valeur: dict[str, list[tuple[int, int, int]]] = {}
        for source, cible in ((planche, planche_par_valeur), (page, page_par_valeur)):
            for patch in source:
                cible.setdefault(patch.value_id, []).append(patch.rgb)
        assert planche_par_valeur == page_par_valeur, template_id
        # ...et ces triplets sont bien ceux de la table, pas une copie locale.
        table = patch_values.get_patch_values_table(
            patch_presets.get_patch_preset(preset_id).values_version)
        for value_id, triplets in sorted(page_par_valeur.items()):
            assert set(triplets) == {table.get(value_id).rgb}, (template_id, value_id)
    # ...et la table epinglee par le preset ne diverge pas de la table **active** la ou
    # les deux portent la meme valeur: la v4 reprend les objets `PatchValue` de la v1 par
    # reference, jamais par recopie de triplet, et c'est ce que cette egalite verifie.
    # (`neutral-065` n'est pas dans la table active, qui reduit son axe neutre a quatre
    # niveaux -- l'intersection est donc calculee, pas supposee.)
    active = patch_values.active_table()
    commun = set(table.value_ids()) & set(active.value_ids())
    assert len(commun) >= 13, sorted(commun)
    for value_id in sorted(commun):
        assert table.get(value_id) is active.get(value_id), value_id


def test_le_bandeau_de_la_page_de_calibration_s_ajoute_au_treillis_sans_deborder():
    """AC 1, tests de composition et de capacite -- cardinaux par **egalite**.

    Le test echoue si l'ajout deborde, et les trois plafonds sont confrontes: le bandeau
    contre `MAX_PATCHES_PER_PAGE`, le treillis contre la capacite de la grille, et le
    bandeau contre la capacite d'une colonne laterale. Une page qui deborde
    silencieusement imprime moins qu'elle ne declare.
    """
    preset_id = "patches-17-v4"
    preset = patch_presets.get_patch_preset(preset_id)
    cardinal_bandeau = len(preset.value_ids) * preset.repetition
    assert cardinal_bandeau == 34
    assert cardinal_bandeau <= patch_presets.MAX_PATCHES_PER_PAGE == 36
    # Le compte que l'AC revendique, derive et non recopie: 28 pastilles occupees
    # aujourd'hui, 8 places libres, 6 prises par les trois secondaires en double.
    ancien = patch_presets.get_patch_preset("patches-14-v3")
    assert (patch_presets.MAX_PATCHES_PER_PAGE
            - len(ancien.value_ids) * ancien.repetition) == 8
    assert cardinal_bandeau - len(ancien.value_ids) * ancien.repetition == 6

    for template_id in _gabarits_v2():
        spec = page_templates.get_template(template_id)
        treillis = patch_presets.resolve_calibration_page_patches(template_id)
        bandeau = patch_presets.resolve_calibration_page_witnesses(
            template_id, preset_id)
        assert len(bandeau) == cardinal_bandeau, template_id
        assert (len(treillis) + len(bandeau)
                == patch_presets.calibration_page_patch_count(preset_id)), template_id
        # Le treillis tient dans le plafond de sa grille -- que le bandeau ne consomme
        # pas, puisqu'il vit hors de la grille (verifie ci-dessous).
        assert len(treillis) <= patch_presets.patch_ceiling_for(
            template_id, patch_presets.PAGE_ROLE_CALIBRATION), template_id
        # Et le bandeau tient dans les colonnes laterales de ce gabarit.
        capacite = spec.geometry.lateral_row_capacity(spec.orientation)
        par_cote = cardinal_bandeau // 2
        colonnes = spec.geometry.patch_columns_per_side[spec.orientation]
        assert -(-par_cote // colonnes) <= capacite, (template_id, capacite)


def test_le_bandeau_de_la_page_de_calibration_ne_recouvre_jamais_son_treillis():
    """AC 1, capacite: deux pastilles superposees se mesurent comme une seule.

    Epingle par ses deux bouts: aucune emprise ne se croise sur les gabarits livres, et
    une geometrie ou elles se croiseraient est **refusee** au lieu d'etre imprimee.
    """
    preset_id = "patches-17-v4"
    for template_id in _gabarits_v2():
        treillis = patch_presets.resolve_calibration_page_patches(template_id)
        bandeau = patch_presets.resolve_calibration_page_witnesses(
            template_id, preset_id)
        emprises_treillis = [
            (patch.x_mm, patch.y_mm, patch.size_mm, patch.size_mm)
            for patch in treillis
        ]
        for temoin in bandeau:
            rect = (temoin.x_mm, temoin.y_mm, temoin.size_mm, temoin.size_mm)
            assert not any(rects_overlap(rect, autre) for autre in emprises_treillis), (
                template_id, temoin.value_id)


def test_la_garde_de_recouvrement_treillis_bandeau_mord_par_ses_quatre_frontieres(
        monkeypatch):
    """Finding 13 du triage de 5.23: la garde etait **debranchable sans consequence**.

    Mesure de la couche 2, 2026-08-19: `if False and overlaps_x and overlaps_y:` laissait
    **100 tests verts**. Le volet de mordant qui pretendait la couvrir assertait
    `rects_overlap` sur une grille reconstruite **dans le test**, jamais celle que la
    fonction de production recalcule -- il prouvait donc que deux rectangles ecrits a la
    main se croisent, pas que la garde refuse.

    Ce que ce test change: la grille est injectee **dans la fonction de production**, par
    la seule chose que la garde lit (`PageGeometry.calibration_grid`), et c'est le refus de
    `resolve_calibration_page_witnesses` qui est mesure. Le reste de la geometrie est
    intact -- seule l'origine bouge --, donc la capacite et le plafond de role ne bougent
    pas et le refus mesure est bien celui du recouvrement, pas celui de la capacite.

    **Les quatre frontieres sont prises des deux cotes**, tangence exacte comprise. La
    garde protege contre « deux valeurs mesurees comme une seule » -- famille appariement
    de collection, chemin fragile du depot --, et une frontiere fausse d'un cote y coute
    soit une page imprimee avec deux pastilles superposees, soit un gabarit sain refuse:
    la tangence exacte **ne recouvre pas**, un dixieme de millimetre au-dela recouvre.
    """
    preset_id = "patches-17-v4"
    template_id = _gabarits_v2()[0]
    spec = page_templates.get_template(template_id)
    vraie = spec.geometry.calibration_grid(
        spec.orientation,
        patch_presets.patch_size_mm_for(
            template_id, patch_presets.PAGE_ROLE_CALIBRATION))
    bandeau = patch_presets.resolve_calibration_page_witnesses(template_id, preset_id)
    # Emprise reelle du bandeau, **derivee** de la pose et non recopiee.
    x_min = min(patch.x_mm for patch in bandeau)
    x_max = max(patch.x_mm + patch.size_mm for patch in bandeau)
    y_min = min(patch.y_mm for patch in bandeau)
    y_max = max(patch.y_mm + patch.size_mm for patch in bandeau)
    largeur = vraie.columns * vraie.step_mm - vraie.spacing_mm
    hauteur = vraie.rows * vraie.step_mm - vraie.spacing_mm

    def _grille_a(origine_x: float, origine_y: float):
        deplacee = dataclasses.replace(
            vraie, origin_x_mm=origine_x, origin_y_mm=origine_y)
        monkeypatch.setattr(
            type(spec.geometry), "calibration_grid",
            lambda self, orientation, patch_size_mm: deplacee)

    def _refuse(origine_x: float, origine_y: float) -> str | None:
        _grille_a(origine_x, origine_y)
        try:
            patch_presets.resolve_calibration_page_witnesses(template_id, preset_id)
        except patch_presets.UndefinedPlacementError as refus:
            return str(refus)
        return None

    # Un dixieme de millimetre: assez pour franchir la frontiere, trop peu pour que le
    # verdict tienne a autre chose qu'a elle.
    pas = 0.1
    tangences = {
        "grille finissant exactement au bord gauche du bandeau":
            (x_min - largeur, 0.0),
        "grille commencant exactement au bord droit du bandeau":
            (x_max, 0.0),
        "grille finissant exactement au bord haut du bandeau":
            (0.0, y_min - hauteur),
        "grille commencant exactement au bord bas du bandeau":
            (0.0, y_max),
    }
    for nom, (origine_x, origine_y) in tangences.items():
        assert _refuse(origine_x, origine_y) is None, (
            f"tangence refusee a tort: {nom}. Une frontiere large ici refuserait des "
            "gabarits sains, dont ceux que le depot livre.")

    mordants = {
        "par la gauche": (x_min - largeur + pas, 0.0),
        "par la droite": (x_max - pas, 0.0),
        "par le haut": (0.0, y_min - hauteur + pas),
        "par le bas": (0.0, y_max - pas),
    }
    for nom, (origine_x, origine_y) in mordants.items():
        message = _refuse(origine_x, origine_y)
        assert message is not None, (
            f"la garde n'a pas mordu {nom}: elle est debranchable sans consequence, ce "
            "qui est exactement le finding que ce test ferme")
        # Et elle nomme **quel** temoin tombe dans la grille: un refus anonyme ne dit pas
        # quelle pastille se superpose a quelle autre.
        assert any(patch.value_id in message for patch in bandeau), (nom, message)
        assert template_id in message and preset_id in message, (nom, message)


def test_le_bandeau_de_la_page_de_calibration_est_refuse_la_ou_la_page_l_est():
    """Le meme refus, au meme endroit: une page v1 ne porte pas de bandeau non plus."""
    v1 = next(
        template_id for template_id in page_templates.known_template_ids()
        if patch_presets.calibration_page_refusal(template_id) is not None
    )
    with pytest.raises(patch_presets.UndefinedPlacementError):
        patch_presets.resolve_calibration_page_witnesses(v1, "patches-17-v4")


# ---------------------------------------------------------------------------
# Story 5.23, AC 1 -- le defaut du bandeau de temoins, epingle **vite**
# ---------------------------------------------------------------------------


def test_le_preset_temoin_par_defaut_est_celui_de_la_story_5_23_et_porte_ses_secondaires():
    """AC 1 de 5.23: `DEFAULT_PATCH_PRESET` vaut `patches-17-v4`, secondaires comprises.

    **Ce test existe parce que le mutant correspondant survivait a tout lot court**
    (`EPIC5-ARB-100`, injection par AC du 2026-08-19). Remettre `DEFAULT_PATCH_PRESET` a
    `patches-14-v3` -- c'est-a-dire **annuler la decision 3 de `EPIC5-ARB-82`** -- n'etait
    tue que par deux tests de `test_makepdf_command.py`, fichier qui coute **38 s**: ni le
    lot de 251 tests de la story ni celui de 500 ne les contenait. La propriete est ici
    reduite a ce qui se mesure sans composer un PDF, donc en quelques millisecondes.

    Les trois secondaires sont exigees **nommement** et non par un role present au moins
    une fois: sinon une seule des trois suffirait a passer, alors que c'est precisement le
    trio qui rend visible une derive d'encre CMJ entre deux feuilles imprimees.

    Le temoin negatif porte sur `patches-14-v3`, le preset que le mutant restaure: sans
    lui, ce test resterait vert sur un depot ou les deux presets seraient devenus
    identiques, et il ne mesurerait plus rien.
    """
    from mixed_media_utility import pdf_composition

    assert pdf_composition.DEFAULT_PATCH_PRESET == "patches-17-v4"
    defaut = patch_presets.get_patch_preset(pdf_composition.DEFAULT_PATCH_PRESET)
    assert defaut.values_version == "patch-values-4"
    assert len(defaut.value_ids) == 17
    assert defaut.repetition == 2
    assert len(defaut.value_ids) * defaut.repetition == 34
    secondaires = {"secondary-cyan", "secondary-magenta", "secondary-yellow"}
    assert secondaires <= set(defaut.value_ids)
    table = patch_values.get_patch_values_table(defaut.values_version)
    assert {value_id for value_id in defaut.value_ids
            if table.get(value_id).role == patch_values.ROLE_SECONDARY} == secondaires

    # Temoin negatif: le preset que le mutant restaure porte 14 valeurs, 28 pastilles, et
    # **aucune** secondaire. Il reste enregistre et inchange (AC 1, versionnement).
    ancien = patch_presets.get_patch_preset("patches-14-v3")
    assert len(ancien.value_ids) == 14
    assert len(ancien.value_ids) * ancien.repetition == 28
    assert secondaires.isdisjoint(ancien.value_ids)
