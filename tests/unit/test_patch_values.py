"""Tests de la table de valeurs theoriques des patchs (story 4.8).

La table est l'unique source de verite des valeurs imprimees: versionnee,
pure (aucune dependance image), bornee a l'espace declare (sRGB D65, 8 bits
par canal — EPIC4-ARB-7), et consommable par le registre de presets 4.7 sans
copie. Un test verrouille qu'aucune valeur theorique n'est definie ailleurs
que dans ce module.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import patch_values
from mixed_media_utility.io import payload as payload_io

MODULE_PATH = REPO_ROOT / "src" / "mixed_media_utility" / "patch_values.py"
SRC_ROOT = REPO_ROOT / "src" / "mixed_media_utility"

IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


# --- AC 1: table versionnee, unique source de verite -------------------------


def test_active_table_declares_its_own_version() -> None:
    table = patch_values.active_table()
    assert table.version == patch_values.ACTIVE_PATCH_VALUES_VERSION
    assert IDENTIFIER_PATTERN.fullmatch(table.version)
    # La version de la table est distincte du schema_version du manifest et
    # du payload (AC 1): un lecteur ne doit jamais pouvoir les confondre.
    # Le prefixe est impose a la construction (revue 4.8), donc TOUTE version
    # du registre est structurellement inconfondable, pas seulement l'active.
    from mixed_media_utility.io.manifest import CURRENT_SCHEMA_VERSION

    for version in patch_values.known_versions():
        assert version.startswith(patch_values.PATCH_VALUES_VERSION_PREFIX)
        assert version != payload_io.PAYLOAD_SCHEMA_VERSION
        assert version != CURRENT_SCHEMA_VERSION


def test_old_versions_stay_readable_for_already_printed_sheets() -> None:
    # EPIC4-ARB-7 (defaut adopte): une seule table active, les anciennes
    # conservees en lecture. En v1 le registre des versions contient au moins
    # la version active, resolvable par la meme API que les futures.
    assert patch_values.ACTIVE_PATCH_VALUES_VERSION in patch_values.known_versions()
    table = patch_values.get_patch_values_table(patch_values.ACTIVE_PATCH_VALUES_VERSION)
    assert table is patch_values.active_table()


def test_unknown_version_is_an_explicit_business_error() -> None:
    with pytest.raises(patch_values.UnknownPatchValuesVersionError) as excinfo:
        patch_values.get_patch_values_table("patch-values-999")
    message = str(excinfo.value)
    assert "patch-values-999" in message
    assert patch_values.ACTIVE_PATCH_VALUES_VERSION in message


def test_unknown_value_id_is_an_explicit_business_error() -> None:
    table = patch_values.active_table()
    with pytest.raises(patch_values.UnknownPatchValueError) as excinfo:
        table.get("valeur-inconnue")
    assert "valeur-inconnue" in str(excinfo.value)
    assert table.version in str(excinfo.value)


def test_table_is_immutable() -> None:
    # Une valeur theorique editee en place est une corruption silencieuse
    # differee (piege 2): toute modification passe par une nouvelle version.
    import dataclasses

    table = patch_values.active_table()
    assert isinstance(table.values, tuple)
    with pytest.raises(dataclasses.FrozenInstanceError):
        table.version = "autre"  # type: ignore[misc]
    first = table.values[0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        first.rgb = (0, 0, 0)  # type: ignore[misc]
    # Et le registre des versions lui-meme n'est pas editable en place
    # (revue 4.8: un dict nu laissait substituer la table active).
    with pytest.raises(TypeError):
        patch_values._TABLES_BY_VERSION["patch-values-1"] = table  # type: ignore[index]


def test_construction_guards_reject_invalid_values_and_tables() -> None:
    # Revue 4.8: les invariants n'etaient tenus que par les tests de la table
    # active; une table v2 archivee ou future y echappait entierement. Ils
    # sont desormais verifies a la construction.
    with pytest.raises(patch_values.PatchValuesIntegrityError):
        patch_values.PatchValue("bad", (300, -5, 4), patch_values.ROLE_PRIMARY)
    with pytest.raises(patch_values.PatchValuesIntegrityError):
        patch_values.PatchValue("bad", (True, 0, 0), patch_values.ROLE_PRIMARY)
    with pytest.raises(patch_values.PatchValuesIntegrityError):
        patch_values.PatchValue("bad", (1, 2), patch_values.ROLE_PRIMARY)  # type: ignore[arg-type]
    with pytest.raises(patch_values.PatchValuesIntegrityError):
        patch_values.PatchValue("bad", (1, 2, 3), "role-inconnu")

    ok = patch_values.PatchValue("ok-1", (1, 2, 3), patch_values.ROLE_PRIMARY)
    other = patch_values.PatchValue("ok-2", (4, 5, 6), patch_values.ROLE_PRIMARY)
    duplicate_id = patch_values.PatchValue("ok-1", (7, 8, 9), patch_values.ROLE_PRIMARY)
    duplicate_rgb = patch_values.PatchValue("ok-3", (1, 2, 3), patch_values.ROLE_PRIMARY)

    with pytest.raises(patch_values.PatchValuesIntegrityError):
        patch_values.PatchValuesTable("sans-prefixe", "sRGB", "D65", 8, (ok,))
    with pytest.raises(patch_values.PatchValuesIntegrityError):
        patch_values.PatchValuesTable("patch-values-9", "sRGB", "D65", 8, (ok, duplicate_id))
    with pytest.raises(patch_values.PatchValuesIntegrityError):
        patch_values.PatchValuesTable("patch-values-9", "sRGB", "D65", 8, (ok, duplicate_rgb))
    with pytest.raises(patch_values.PatchValuesIntegrityError):
        patch_values.PatchValuesTable("patch-values-9", "sRGB", "D65", 8, ())
    # Une table valide se construit toujours.
    patch_values.PatchValuesTable("patch-values-9", "sRGB", "D65", 8, (ok, other))


def test_unhashable_version_is_a_business_error_not_a_typeerror() -> None:
    with pytest.raises(patch_values.UnknownPatchValuesVersionError):
        patch_values.get_patch_values_table(["patch-values-1"])  # type: ignore[arg-type]


def test_every_known_version_satisfies_the_core_invariants() -> None:
    # Revue 4.8: quand une v2 deviendra active, la v1 archivee (toujours
    # resolvable, imprimee sur des planches reelles) doit garder les memes
    # invariants -- le balayage couvre toutes les versions du registre.
    for version in patch_values.known_versions():
        table = patch_values.get_patch_values_table(version)
        ids = [value.value_id for value in table.values]
        triplets = [value.rgb for value in table.values]
        assert len(ids) == len(set(ids)), version
        assert len(triplets) == len(set(triplets)), version
        for value in table.values:
            assert IDENTIFIER_PATTERN.fullmatch(value.value_id), (version, value.value_id)
            for channel in value.rgb:
                assert isinstance(channel, int) and not isinstance(channel, bool)
                assert 0 <= channel <= 255, (version, value.value_id)


# --- AC 2: espace de definition nomme, unique, enregistre dans la table -----


def test_definition_space_is_recorded_in_the_table_itself() -> None:
    table = patch_values.active_table()
    assert table.color_space == "sRGB"
    assert table.white_point == "D65"
    assert table.bits_per_channel == 8


# --- AC 6: valeurs bornees, typees, identifiants uniques ---------------------


def test_every_channel_is_a_bounded_8_bit_integer() -> None:
    table = patch_values.active_table()
    for value in table.values:
        assert isinstance(value.rgb, tuple) and len(value.rgb) == 3
        for channel in value.rgb:
            assert isinstance(channel, int) and not isinstance(channel, bool)
            assert 0 <= channel <= 255


def test_value_ids_are_unique_and_schema_conformant() -> None:
    table = patch_values.active_table()
    ids = [value.value_id for value in table.values]
    assert len(ids) == len(set(ids))
    for value_id in ids:
        # fullmatch (revue 4.8): `$` avec match acceptait un saut de ligne final.
        assert IDENTIFIER_PATTERN.fullmatch(value_id), value_id


def test_roles_belong_to_the_closed_set() -> None:
    # Amende par la story 5.9 (AC 1): le vocabulaire ferme gagne une quatrieme
    # constante, `gamut_sentinel`. L'ensemble en dur devient donc faux — et il
    # l'est inconditionnellement depuis que la table active est la v2
    # (EPIC5-ARB-21), qui porte les quatre roles.
    #
    # **Amende une seconde fois par la story 5.16 (AC 4)**: le vocabulaire gagne
    # `calibration_lattice`, et l'assertion unique d'origine confondait deux
    # ensembles qui cessent de coincider. Les roles qu'une **table** porte restent
    # les quatre; le cinquieme n'est imprime que sur la page de calibration
    # dediee, et `PatchValuesTable` refuse desormais une table qui le porterait.
    # Garder l'egalite unique aurait force a inscrire le treillis dans une table
    # pour rendre le test vert, c'est-a-dire a faire croire qu'une planche
    # d'images peut en porter.
    table = patch_values.active_table()
    table_roles = {
        patch_values.ROLE_NEUTRAL,
        patch_values.ROLE_PRIMARY,
        patch_values.ROLE_SECONDARY,
        patch_values.ROLE_GAMUT_SENTINEL,
    }
    assert {value.role for value in table.values} == table_roles
    assert set(patch_values._TABLE_ROLES) == table_roles
    # Le vocabulaire reste ferme: rien d'autre que le treillis ne s'y ajoute.
    assert set(patch_values._KNOWN_ROLES) == table_roles | {
        patch_values.ROLE_CALIBRATION_LATTICE}
    # Et aucune version enregistree ne porte le role de treillis: la separation
    # est structurelle, pas conventionnelle.
    for version in patch_values.known_versions():
        roles = {value.role
                 for value in patch_values.get_patch_values_table(version).values}
        assert patch_values.ROLE_CALIBRATION_LATTICE not in roles, version


def test_table_covers_the_arbitrated_preset_needs() -> None:
    # EPIC4-ARB-6 exigeait un axe neutre a 6 niveaux, et ce test l'encodait en
    # `>= 6`. **EPIC5-ARB-17(b) amende cet arbitrage**: l'axe neutre de la
    # table active passe a 4 niveaux pour financer les deux ancres
    # achromatiques dans le plafond de 36 pastilles. L'assouplissement de ce
    # seuil est le corollaire de test d'un amendement d'arbitrage, pas un
    # relachement de confort — d'ou l'assertion **exacte** ci-dessous plutot
    # qu'un `>= 4` qui laisserait de nouveau glisser le cardinal en silence.
    #
    # La v1 garde ses 6 niveaux et reste resolvable: c'est sur elle que
    # `patches-12-v1` continue de s'imprimer.
    active = patch_values.active_table()
    by_role: dict[str, int] = {}
    for value in active.values:
        by_role[value.role] = by_role.get(value.role, 0) + 1
    assert by_role.get(patch_values.ROLE_NEUTRAL, 0) == 4
    assert by_role.get(patch_values.ROLE_PRIMARY, 0) == 3
    assert by_role.get(patch_values.ROLE_SECONDARY, 0) == 3
    assert by_role.get(patch_values.ROLE_GAMUT_SENTINEL, 0) == 8

    legacy = patch_values.get_patch_values_table("patch-values-1")
    legacy_neutrals = [v for v in legacy.values if v.role == patch_values.ROLE_NEUTRAL]
    assert len(legacy_neutrals) == 6, "la v1 n'est pas amendee, elle est archivee telle quelle"


def test_neutral_axis_values_are_neutral_and_strictly_increasing() -> None:
    table = patch_values.active_table()
    neutrals = [value for value in table.values if value.role == patch_values.ROLE_NEUTRAL]
    levels = []
    for value in neutrals:
        red, green, blue = value.rgb
        assert red == green == blue, value.value_id
        levels.append(red)
    assert levels == sorted(levels)
    assert len(levels) == len(set(levels))


def test_no_pure_extremes_and_the_choice_is_documented() -> None:
    # Piege 3: 0/0/0 sature l'encrage, 255/255/255 est indiscernable du papier
    # nu. La v1 ancre l'axe neutre pres des extremes sans les toucher.
    #
    # Amende par la story 5.9 (AC 4): la regle n'est pas supprimee, elle est
    # **portee par le role**. Les deux extremes entrent dans la table active
    # comme sentinelles d'ecretage — c'est leur raison d'etre, instrumenter la
    # frontiere que les autres roles doivent eviter. L'interdiction reste donc
    # entiere sur les trois roles d'ajustement, et le test le verifie role par
    # role au lieu de balayer la table sans distinction.
    for version in patch_values.known_versions():
        table = patch_values.get_patch_values_table(version)
        for value in table.values:
            if value.role == patch_values.ROLE_GAMUT_SENTINEL:
                continue
            assert value.rgb != (0, 0, 0), f"{version}/{value.value_id}"
            assert value.rgb != (255, 255, 255), f"{version}/{value.value_id}"

    # La garde est posee a la construction, pas seulement sur les tables
    # livrees: un extreme pur declare avec un role d'ajustement est refuse.
    for role in (patch_values.ROLE_NEUTRAL, patch_values.ROLE_PRIMARY, patch_values.ROLE_SECONDARY):
        for extreme in ((0, 0, 0), (255, 255, 255)):
            with pytest.raises(patch_values.PatchValuesIntegrityError):
                patch_values.PatchValue("interdit", extreme, role)
    # ... et autorisee, elle, au seul role sentinelle.
    for extreme in ((0, 0, 0), (255, 255, 255)):
        patch_values.PatchValue("autorise", extreme, patch_values.ROLE_GAMUT_SENTINEL)

    doc = MODULE_PATH.read_text(encoding="utf-8")
    assert "papier nu" in doc
    assert "encrage" in doc
    # Les deux enonces doivent coexister par ecrit, sinon la prochaine revue en
    # supprimera un (piege 8 de la story 5.9).
    assert "ne se contredisent" in doc
    assert "porte par le role" in doc or "portee par le role" in doc


def test_rgb_triplets_are_unique() -> None:
    table = patch_values.active_table()
    triplets = [value.rgb for value in table.values]
    assert len(triplets) == len(set(triplets))


# --- AC 4: preconditions de la future LUT, chacune avec son garant ----------


def test_lut_preconditions_are_listed_with_their_guarantor() -> None:
    preconditions = patch_values.LUT_PRECONDITIONS
    assert len(preconditions) >= 6
    for precondition in preconditions:
        assert precondition.statement.strip()
        assert precondition.guarantor_story.strip()
        assert precondition.guarantor_module.strip()
        # ASCII partout (piege 5).
        precondition.statement.encode("ascii")
        precondition.guarantor_story.encode("ascii")
        precondition.guarantor_module.encode("ascii")


def test_calibration_status_precondition_names_the_writer_and_the_exclusions() -> None:
    # AC 4: color_calibration_status est porte par le fragment manifest de
    # color_pipeline (chemin extraction/scan); makepdf ne l'ecrit pas et il
    # n'entre jamais dans le payload QR.
    statements = " ".join(
        precondition.statement for precondition in patch_values.LUT_PRECONDITIONS
    )
    assert "color_calibration_status" in statements
    assert "makepdf" in statements
    assert "payload QR" in statements
    # Verite du code, par la surface publique (revue 4.8: le couplage au
    # membre prive _REQUIRED_SCALAR_FIELDS cassait au premier renommage
    # interne de payload.py): un payload reellement construit ne porte pas
    # le champ.
    built = payload_io.build_page_payload(
        project_id="p", rush_id="r", lot_id="l", page_index=0, page_count=1,
        fps_target=5.0, template_id="tpl-a4-portrait-2f-v1",
        timecode_base_fps="25/1",
        patch_preset_id="patches-12-v1", target_colorspace="rec709",
        gamut_map_id=payload_io.GAMUT_MAP_IDENTITY,
        slots=[{"slot_index": 0, "frame_timecode": "00:00:00:00"}],
    )
    assert "color_calibration_status" not in built
    # Et la precondition materiel bloquante pointe vers un symbole reel:
    # qr_codes.QR_MIN_SCAN_DPI existe et le nom est cite verbatim.
    from mixed_media_utility import qr_codes

    assert hasattr(qr_codes, "QR_MIN_SCAN_DPI")
    assert "QR_MIN_SCAN_DPI" in statements


def test_patch_space_is_never_confused_with_target_colorspace() -> None:
    # AC 3: l'espace des patchs decrit ce qui est imprime; target_colorspace
    # decrit la cible de reconstruction du rush. La table ne porte aucun champ
    # nomme target_colorspace, et la distinction est documentee.
    table = patch_values.active_table()
    assert not hasattr(table, "target_colorspace")
    doc = MODULE_PATH.read_text(encoding="utf-8")
    assert "target_colorspace" in doc
    assert "jamais" in doc


# --- AC 5 / AC 6: purete du module et unicite du point de verite -------------


def _module_tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_module_is_pure_data_with_no_image_dependency() -> None:
    # Revue 4.8: `from . import layout` (module=None) et les formes absolues
    # contournaient le garde -- toutes les formes d'import sont controlees, et
    # `layout` (qui tire cv2) est interdit aussi.
    tree = _module_tree(MODULE_PATH)
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


def test_deferred_color_decisions_are_named_not_implemented() -> None:
    # AC 5: pas de conversion active, pas d'ICC, pas de linearisation, pas de
    # DeltaE, pas de mesure spectrale — differes a 5.4 (decision 2026-08-02).
    # Le module nomme ces trous pour que 5.4 les retrouve.
    doc = MODULE_PATH.read_text(encoding="utf-8")
    for deferred in ("ICC", "linearisation", "DeltaE", "mesure spectrale", "conversion", "5.4"):
        assert deferred in doc, deferred
    # Et ne les implemente pas: aucune fonction de conversion dans le module.
    tree = _module_tree(MODULE_PATH)
    function_names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for forbidden_hint in ("linear", "lab", "delta_e", "convert", "to_xyz"):
        assert not any(forbidden_hint in name.lower() for name in function_names), (
            f"fonction de conversion couleur interdite ici (differee a 5.4): "
            f"{sorted(function_names)}"
        )


def test_no_theoretical_color_value_is_defined_outside_the_table() -> None:
    # AC 6: unicite du point de verite. Aucun triplet de la table ne doit
    # apparaitre comme constante dans un autre module de src/ (layout.py,
    # futur module de composition 4.1, registre 4.7...).
    #
    # Restreint par la story 5.9 (AC 4). Depuis que les deux extremes purs
    # entrent dans la table active comme sentinelles achromatiques, le scan
    # heurte des couleurs de **trace** OpenCV parfaitement legitimes —
    # `cadence_previz.py` dessine un contour de texte en `(0, 0, 0)` et un
    # bandeau en `(255, 255, 255)`. C'est un faux positif structurel: le noir
    # et le blanc purs sont des constantes de dessin universelles, et
    # l'invariant d'unicite du point de verite ne peut pas les revendiquer.
    #
    # Ce qui est exclu, ce sont **ces deux triplets et eux seuls**. Les six
    # sentinelles chromatiques restent scannees, comme les dix valeurs
    # d'ajustement: l'invariant de 4.8 reste entier sur tout ce qu'il peut
    # reellement garantir. Ne pas desarmer le test ni exclure un module —
    # ce serait rouvrir le motif « deux sources de verite » que 4.8 a paye
    # pour fermer (piege 12 de la story 5.9).
    # Le scan balaie **toutes** les versions du registre, pas seulement
    # l'active. Regression trouvee en revue (5.9-C1-4): pilote par
    # `active_table()`, il perdait `(65,65,65)` et `(155,155,155)` des la
    # bascule vers la v2 -- deux triplets pourtant toujours imprimes par
    # `patches-12-v1`, qui epingle la v1. Une planche reste interpretable tant
    # que sa version l'est: l'unicite du point de verite doit couvrir ce que
    # l'on imprime, pas ce qui est actif.
    universal_drawing_colors = {(0, 0, 0), (255, 255, 255)}
    known_triplets = set()
    for version in patch_values.known_versions():
        known_triplets |= {value.rgb for value in patch_values.get_patch_values_table(version).values}
    known_triplets -= universal_drawing_colors

    # Les deux triplets que la bascule avait fait sortir du perimetre.
    assert (65, 65, 65) in known_triplets
    assert (155, 155, 155) in known_triplets

    # Garde de la restriction elle-meme: seules des sentinelles achromatiques
    # sont retirees du scan, jamais une valeur d'ajustement.
    for version in patch_values.known_versions():
        table = patch_values.get_patch_values_table(version)
        for excluded in universal_drawing_colors:
            matching = [v for v in table.values if v.rgb == excluded]
            assert all(v.role == patch_values.ROLE_GAMUT_SENTINEL for v in matching), matching
        assert {v.rgb for v in table.adjustment_values()} <= known_triplets

    for path in sorted(SRC_ROOT.rglob("*.py")):
        if path == MODULE_PATH:
            continue
        tree = _module_tree(path)
        for node in ast.walk(tree):
            # Tuples ET listes (revue 4.8: `[190, 45, 45]` echappait au scan).
            if not isinstance(node, (ast.Tuple, ast.List)) or len(node.elts) != 3:
                continue
            elements = []
            for element in node.elts:
                if isinstance(element, ast.Constant) and isinstance(element.value, int):
                    elements.append(element.value)
            if len(elements) == 3 and tuple(elements) in known_triplets:
                raise AssertionError(
                    f"Triplet de valeur theorique duplique dans {path.name}: "
                    f"{tuple(elements)} — la table patch_values est le seul "
                    "point de verite."
                )


# --- Story 5.9: table patch-values-2 et patchs sentinelles de gamut ---------
#
# Mandat EPIC5-ARB-3, sur un constat mesure: l'enveloppe convexe des 12 patchs
# de la v1 couvre 17,8 % du cube RVB. Des patchs tous interieurs au gamut sont
# par construction incapables de mesurer l'ecretage du pilote CMJN.


V1_FROZEN_VALUES = (
    ("neutral-020", (20, 20, 20), patch_values.ROLE_NEUTRAL),
    ("neutral-065", (65, 65, 65), patch_values.ROLE_NEUTRAL),
    ("neutral-110", (110, 110, 110), patch_values.ROLE_NEUTRAL),
    ("neutral-155", (155, 155, 155), patch_values.ROLE_NEUTRAL),
    ("neutral-200", (200, 200, 200), patch_values.ROLE_NEUTRAL),
    ("neutral-245", (245, 245, 245), patch_values.ROLE_NEUTRAL),
    ("primary-red", (190, 45, 45), patch_values.ROLE_PRIMARY),
    ("primary-green", (55, 150, 70), patch_values.ROLE_PRIMARY),
    ("primary-blue", (45, 75, 160), patch_values.ROLE_PRIMARY),
    ("secondary-cyan", (60, 165, 175), patch_values.ROLE_SECONDARY),
    ("secondary-magenta", (175, 60, 150), patch_values.ROLE_SECONDARY),
    ("secondary-yellow", (220, 200, 60), patch_values.ROLE_SECONDARY),
)

# Les cinq chaines de lecture de l'AC 3, du niveau in-gamut vers le bord du
# cube. Les deux ancres achromatiques n'ont qu'un echelon: leur second niveau
# de lecture est leur voisin in-gamut, pas une seconde sentinelle.
SENTINEL_CHAINS = {
    "red": ("primary-red", "sentinel-red-1", "sentinel-red-2"),
    "green": ("primary-green", "sentinel-green-1", "sentinel-green-2"),
    "blue": ("primary-blue", "sentinel-blue-1", "sentinel-blue-2"),
    "black": ("neutral-020", "sentinel-black-1"),
    "white": ("neutral-245", "sentinel-white-1"),
}


def test_v1_stays_registered_and_frozen_value_for_value() -> None:
    # Piege 7: composer la v2 depuis les objets de la v1 est la bonne facon de
    # ne pas recopier les triplets, mais c'est aussi un canal d'edition en
    # place si personne n'epingle la v1. Ce test est cet epinglage.
    table = patch_values.get_patch_values_table("patch-values-1")
    assert table.version == "patch-values-1"
    assert tuple((v.value_id, v.rgb, v.role) for v in table.values) == V1_FROZEN_VALUES
    assert (table.color_space, table.white_point, table.bits_per_channel) == ("sRGB", "D65", 8)


def test_v1_version_is_a_literal_not_the_active_alias() -> None:
    # Piege 11: `_TABLE_V1` etait construite avec `version=
    # ACTIVE_PATCH_VALUES_VERSION`, et le registre est indexe par
    # `_TABLE_V1.version`. Basculer l'alias aurait **renomme** la v1, fait
    # collisionner les cles et rendu introuvable le "patch-values-1" que les
    # deux presets livres epinglent en litteral.
    #
    # **Amende par la story 5.16 (AC 6)**: une troisieme version est enregistree,
    # et l'alias actif **ne bascule pas** dessus — la v3 est le jeu *temoin* d'une
    # planche d'images, pas un jeu d'ajustement. Les deux premieres assertions
    # sont donc conservees telles quelles: ce sont elles qui portent le piege 11,
    # et la v3 ne les affaiblit pas.
    assert patch_values.ACTIVE_PATCH_VALUES_VERSION == "patch-values-2"
    assert patch_values._TABLE_V1.version == "patch-values-1"
    # **Amende par la story 5.23 (AC 1)**: une quatrieme version est enregistree
    # (`patch-values-4`, le jeu temoin elargi aux trois secondaires), et l'alias actif
    # **ne bascule pas** dessus non plus -- meme motif que pour la v3: elargir le jeu
    # temoin ne fait pas de lui le jeu sur lequel la correction s'ajuste. Les deux
    # assertions ci-dessus, qui portent le piege 11, sont conservees telles quelles.
    assert set(patch_values.known_versions()) == {
        "patch-values-1", "patch-values-2", "patch-values-3", "patch-values-4"}


def test_v2_is_registered_and_active() -> None:
    table = patch_values.get_patch_values_table("patch-values-2")
    assert patch_values.active_table() is table
    assert table.version == patch_values.ACTIVE_PATCH_VALUES_VERSION
    # 18 valeurs = 10 d'ajustement + 8 sentinelles, soit 36 pastilles a la
    # repetition 2: le plafond exact d'EPIC5-ARB-14, sans cellule libre.
    assert len(table.values) == 18


def test_v2_adjustment_set_is_a_proper_subset_of_v1() -> None:
    # AC 6, reformule par EPIC5-ARB-17(b). Ce n'est PAS une egalite: l'axe
    # neutre passe de 6 a 4 niveaux. Le sous-ensemble doit etre **propre** —
    # un sous-ensemble non propre signalerait qu'on a oublie de reduire l'axe
    # neutre — et la difference est nommee pour qu'un re-espacement silencieux
    # de l'axe neutre casse ce test.
    v1 = patch_values.get_patch_values_table("patch-values-1")
    v2 = patch_values.get_patch_values_table("patch-values-2")

    adjustment = set(v2.adjustment_values())
    assert adjustment < set(v1.values)
    dropped = {value.value_id for value in set(v1.values) - adjustment}
    assert dropped == {"neutral-065", "neutral-155"}

    # Reprises **par reference**, pas recopiees: recopier les triplets
    # recreerait la double source de verite que 4.7 et 4.8 ont paye a eviter.
    for value in v2.adjustment_values():
        assert value is v1.get(value.value_id)


def test_v2_is_not_a_superset_of_v1() -> None:
    # Enonce a ne pas confondre avec un abandon: la v1 reste enregistree et
    # `patches-12-v1` continue d'imprimer ses 12 valeurs. Mais quiconque lit
    # « v2 = v1 + sentinelles » se trompera (piege 10).
    v1 = patch_values.get_patch_values_table("patch-values-1")
    v2 = patch_values.get_patch_values_table("patch-values-2")
    assert not set(v1.values) <= set(v2.values)


@pytest.mark.parametrize("axis", sorted(SENTINEL_CHAINS))
def test_each_sentinel_chain_is_monotonic_per_channel(axis: str) -> None:
    # AC 3(a). Une chaine non monotone rendrait la regle de lecture
    # ininterpretable: « deux niveaux consecutifs indiscernables valent
    # ecretage » suppose que les niveaux progressent dans un seul sens.
    table = patch_values.active_table()
    chain = [table.get(value_id).rgb for value_id in SENTINEL_CHAINS[axis]]
    for channel_index, channel in enumerate(zip(*chain)):
        increasing = all(a <= b for a, b in zip(channel, channel[1:]))
        decreasing = all(a >= b for a, b in zip(channel, channel[1:]))
        assert increasing or decreasing, (axis, channel_index, channel)
    # Aucun palier: deux niveaux consecutifs identiques sur les trois canaux
    # seraient un ecretage fabrique par la table elle-meme.
    assert len(set(chain)) == len(chain)


def test_sentinel_chains_end_on_the_edge_of_the_rgb_cube() -> None:
    table = patch_values.active_table()
    assert table.get("sentinel-red-2").rgb == (255, 0, 0)
    assert table.get("sentinel-green-2").rgb == (0, 255, 0)
    assert table.get("sentinel-blue-2").rgb == (0, 0, 255)
    assert table.get("sentinel-black-1").rgb == (0, 0, 0)
    assert table.get("sentinel-white-1").rgb == (255, 255, 255)


def test_median_sentinels_sit_in_the_middle_of_their_unmeasured_band() -> None:
    # AC 3: les niveaux medians sont **calcules** (milieu de la bande non
    # mesuree, arrondi au multiple de 5), pas choisis a vue. Sans ce test,
    # rien n'empeche un futur ajustement « a l'oeil » de s'installer.
    #
    # L'assertion porte sur la **propriete** et non sur une formule d'arrondi:
    # les trois bandes ont une longueur impaire sur chaque canal, donc tous les
    # milieux tombent exactement sur un demi-multiple de 5 (222,5 / 22,5 /
    # 27,5 / 202,5 / 37,5 / 207,5 ...). Chaque canal est donc un **cas
    # d'egalite** entre les deux multiples de 5 voisins, tranche a la main dans
    # la story: 222,5 -> 225 mais 22,5 -> 20, 37,5 -> 40 mais 207,5 -> 205.
    # Aucune regle d'arrondi uniforme ne reproduit ces six choix, et en figer
    # une ici ferait echouer le test sur des valeurs pourtant conformes a
    # l'intention. Ce qui est verifiable et verifie: multiple de 5, et distance
    # au milieu exact inferieure ou egale a un demi-pas.
    table = patch_values.active_table()
    for in_gamut, median, pure in (
        ("primary-red", "sentinel-red-1", "sentinel-red-2"),
        ("primary-green", "sentinel-green-1", "sentinel-green-2"),
        ("primary-blue", "sentinel-blue-1", "sentinel-blue-2"),
    ):
        low = table.get(in_gamut).rgb
        high = table.get(pure).rgb
        observed = table.get(median).rgb
        for channel, (a, b, value) in enumerate(zip(low, high, observed)):
            midpoint = (a + b) / 2
            assert value % 5 == 0, (median, channel, value)
            assert abs(value - midpoint) <= 2.5, (median, channel, value, midpoint)
            # Strictement entre les deux bornes: une mediane confondue avec
            # l'une d'elles ne mesurerait plus rien.
            assert min(a, b) <= value <= max(a, b), (median, channel)


def test_sentinel_ids_follow_the_uniform_shape() -> None:
    table = patch_values.active_table()
    for value in table.sentinel_values():
        assert re.fullmatch(r"sentinel-[a-z]+-[0-9]+", value.value_id), value.value_id


def test_the_reading_rule_is_written_in_the_table_not_only_in_the_story() -> None:
    # AC 3(d): la regle doit etre reutilisable verbatim par 5.4b. Si elle ne
    # vit que dans le fichier de story, elle sera reinventee.
    doc = MODULE_PATH.read_text(encoding="utf-8")
    assert "indiscernables valent ecretage" in doc
    for value in patch_values.active_table().sentinel_values():
        assert value.note, f"{value.value_id} doit porter sa chaine de lecture"
        assert "chaine" in value.note


# --- AC 6: l'exclusion est imposee par le code, pas par la documentation ----


@pytest.mark.parametrize("version", sorted(patch_values.known_versions()))
def test_adjustment_and_sentinel_sets_never_intersect(version: str) -> None:
    table = patch_values.get_patch_values_table(version)
    assert set(table.adjustment_values()) & set(table.sentinel_values()) == set()
    # Ensemble, les deux recouvrent exactement la table: aucune valeur ne
    # tombe dans un troisieme panier silencieux.
    assert set(table.adjustment_values()) | set(table.sentinel_values()) == set(table.values)


def test_adjustment_and_sentinel_cardinals_per_version() -> None:
    v1 = patch_values.get_patch_values_table("patch-values-1")
    v2 = patch_values.get_patch_values_table("patch-values-2")
    assert (len(v1.adjustment_values()), len(v1.sentinel_values())) == (12, 0)
    assert (len(v2.adjustment_values()), len(v2.sentinel_values())) == (10, 8)


def test_presenting_a_sentinel_as_an_adjustment_value_is_refused() -> None:
    # Le piege central de la story: un point ecrete par construction, injecte
    # dans l'ajustement, tire toute la LUT — et le symptome est une correction
    # plausible, pas une erreur. D'ou une API qui **ne peut pas** rendre une
    # sentinelle, plutot qu'un filtre a poser.
    table = patch_values.active_table()
    with pytest.raises(patch_values.SentinelInAdjustmentSetError) as excinfo:
        patch_values.ensure_no_sentinel_in_adjustment_set(table.values)
    assert "sentinel-red-2" in str(excinfo.value)

    # Le jeu d'ajustement, lui, passe la meme garde.
    assert patch_values.ensure_no_sentinel_in_adjustment_set(table.adjustment_values())


def test_values_docstring_says_it_is_never_an_adjustment_set() -> None:
    """`values` reste l'enumeration brute: l'avertissement doit etre ecrit.

    Version precedente de ce test (trouvee tautologique en revue, 5.9-C3-1):
    elle assertait `"adjustment_values()" in doc`, chaine presente du seul fait
    de la definition de la methode. Elle passait donc a l'identique alors que
    l'avertissement n'existait pas. La chaine cherchee ici est la phrase
    elle-meme, et elle est ancree sur la declaration du champ.
    """
    doc = MODULE_PATH.read_text(encoding="utf-8")
    assert "jamais un jeu\n    #: d'ajustement" in doc, (
        "l'avertissement doit etre attache a la declaration de `values`"
    )
    # Et il doit rediriger vers les deux API qui, elles, sont sures.
    warning_start = doc.index("jamais un jeu")
    warning = doc[warning_start : warning_start + 900]
    assert "adjustment_values()" in warning
    assert "sentinel_values()" in warning


def test_the_eighth_lut_precondition_names_the_sentinel_exclusion() -> None:
    statements = [p.statement for p in patch_values.LUT_PRECONDITIONS]
    assert len(patch_values.LUT_PRECONDITIONS) == 8
    matching = [s for s in statements if "gamut_sentinel" in s]
    assert len(matching) == 1
    precondition = next(p for p in patch_values.LUT_PRECONDITIONS if "gamut_sentinel" in p.statement)
    assert "5.9" in precondition.guarantor_story
    assert "5.4" in precondition.guarantor_story
    assert precondition.guarantor_module == "patch_values.py"


# ---------------------------------------------------------------------------
# Dette heritee de la revue de la story 5.16, fermee par la story 5.19
# ---------------------------------------------------------------------------
#
# Deux mutants critiques de la classe « ordre d'iteration / appariement positionnel »
# (`politique-revue-et-mutation-testing.md`, section 4: zero survivant exige) restaient
# ouverts sur ce module, et ils y sont fermes ici plutot que dans une passe separee
# parce que la story 5.19 rouvre les memes fichiers -- fermer deux fois aurait paye deux
# fois la campagne.
#
# Les deux survivaient a **ce fichier**, qui est le lot que la campagne de 5.16 ciblait.
# `test_calibration_page_source.py` en tue une partie par ailleurs, mais un module dont
# la suite propre ne pinne pas son ordre d'iteration central n'est pas mesure: le jour
# ou ce consommateur bouge, la garde disparait sans qu'aucun test de ce module ne sonne.


def test_le_balayage_du_treillis_est_r_puis_g_puis_b_et_pas_l_inverse() -> None:
    """**Mutant `R07`**: le balayage devient B-G-R et rien ne le remarque.

    Le mutant ne change ni le **cardinal** du treillis, ni son **contenu** -- l'ensemble
    des 125 triplets est le meme --, seulement son **ordre**. Or l'ordre est ce dont
    depend la coincidence entre l'ordre lexicographique des identifiants et l'ordre du
    balayage, que la docstring revendique et que `aggregate_by_value` consomme. Un test
    d'ensembles ou de cardinal passe donc a l'identique, et c'est exactement ce qui est
    arrive.

    L'ancrage retenu est le plus court qui distingue les six ordres possibles: les
    `len(niveaux)` **premieres** valeurs partagent le meme rouge **et** le meme vert, et
    leurs bleus sont les niveaux dans l'ordre. Le bleu est donc la boucle la plus
    interne, le vert la mediane, le rouge l'externe -- une permutation quelconque des
    trois boucles casse au moins une des trois assertions.
    """
    niveaux = patch_values.CALIBRATION_LATTICE_LEVELS
    treillis = patch_values.calibration_lattice_values()
    assert len(treillis) == len(niveaux) ** 3
    assert len(niveaux) >= 2, "un treillis a un seul niveau ne distinguerait aucun ordre"

    tete = treillis[:len(niveaux)]
    assert {value.rgb[0] for value in tete} == {niveaux[0]}, "rouge = boucle externe"
    assert {value.rgb[1] for value in tete} == {niveaux[0]}, "vert = boucle mediane"
    assert [value.rgb[2] for value in tete] == list(niveaux), "bleu = boucle interne"

    # Second ancrage, sur la boucle mediane: apres un tour complet du bleu, c'est le
    # **vert** qui avance d'un cran et le rouge qui ne bouge pas. Sans lui, echanger le
    # rouge et le vert des deux boucles externes passerait les trois assertions
    # ci-dessus des que `niveaux[0]` est commun aux deux.
    suivante = treillis[len(niveaux)]
    assert suivante.rgb == (niveaux[0], niveaux[1], niveaux[0]), suivante.rgb

    # Et la propriete que le balayage existe pour tenir, verifiee de bout en bout:
    # l'ordre lexicographique des identifiants **est** l'ordre du balayage.
    identifiants = [value.value_id for value in treillis]
    assert identifiants == sorted(identifiants)


def test_le_triplet_du_treillis_est_pose_en_rgb_et_pas_dans_l_ordre_de_l_identifiant(
) -> None:
    """**Mutant `R08`**: le triplet se pose dans un autre ordre que celui de son identifiant.

    L'identifiant est **derive** du triplet (`_lattice_value_id`), donc les deux ne
    peuvent divergier que si la valeur posee sur `PatchValue.rgb` n'est pas celle passee
    a la derivation. Le mutant fait exactement cela -- `(blue, green, red)` sur le champ,
    `(red, green, blue)` dans le nom -- et le resultat est silencieux: le treillis garde
    son cardinal, ses identifiants restent tries, et chaque triplet du cube existe
    toujours quelque part dans la collection. Ce qui change est **l'appariement** entre
    un nom et une couleur, c'est-a-dire ce dont depend `lattice_adjustment_source` pour
    savoir quelle reference confronter a quelle mesure.

    La confrontation porte donc sur le **texte de l'identifiant** contre le tuple, et non
    sur l'un des deux seul. Elle n'est pas tautologique bien que le nom soit derive du
    tuple: c'est precisement la derivation qui est mise en doute.

    Le volet qui rend le test non vide: au moins une valeur du treillis a ses **trois**
    canaux distincts. Sur une valeur grise ou a deux canaux egaux, toute permutation est
    invisible -- et le treillis en porte beaucoup.
    """
    asymetriques = 0
    for value in patch_values.calibration_lattice_values():
        prefixe, rouge, vert, bleu = value.value_id.split("-")
        assert prefixe == "lattice"
        assert (int(rouge), int(vert), int(bleu)) == tuple(value.rgb), value.value_id
        if len(set(value.rgb)) == 3:
            asymetriques += 1
    assert asymetriques >= 1, (
        "aucune valeur a trois canaux distincts: une permutation R/B serait invisible "
        "et ce test serait vert et vide")

    # Et la permutation qui compte le plus -- R et B echanges -- est **observable**: la
    # valeur miroir d'un triplet asymetrique existe aussi dans le treillis, donc un
    # appariement inverse rendrait une couleur qui existe. C'est ce qui rend le defaut
    # silencieux, et c'est pourquoi il faut confronter le nom et non l'appartenance.
    par_id = {value.value_id: tuple(value.rgb)
              for value in patch_values.calibration_lattice_values()}
    niveaux = patch_values.CALIBRATION_LATTICE_LEVELS
    rouge, vert, bleu = niveaux[0], niveaux[1], niveaux[2]
    direct = f"lattice-{rouge:03d}-{vert:03d}-{bleu:03d}"
    miroir = f"lattice-{bleu:03d}-{vert:03d}-{rouge:03d}"
    assert par_id[direct] == (rouge, vert, bleu)
    assert par_id[miroir] == (bleu, vert, rouge)
    assert par_id[direct] != par_id[miroir]


# =============================================================================
# Story 5.20, AC 7 -- le plancher d'encrage couvre aussi le treillis normal
# =============================================================================
#
# Ecart de couverture, pas de regle: la garde des sondes d'ombre ne connait qu'un
# **prefixe d'identifiant**, et `lattice-008-008-008` n'a pas ce prefixe alors qu'il est
# soumis au meme plancher physique. Il n'etait filtre que par la saturation, qui est
# nulle sur un neutre et ne dit donc rien de sa clarte.


def test_le_plancher_d_encrage_se_lit_sur_la_clarte_et_jamais_sur_un_prefixe() -> None:
    """Le critere porte sur le **triplet**, ce qui le rend juste pour toute valeur.

    Un critere par prefixe aurait reconduit exactement le defaut qu'on ferme ici: il
    faudrait le rouvrir a la valeur suivante qui s'appelle autrement. Le test le verifie
    des deux cotes -- une valeur du treillis y entre sans prefixe de sonde, et une sonde
    d'ombre y entrerait aussi par son triplet si elle en portait un.
    """
    plancher = patch_values.SHADOW_FLOOR_8BIT
    assert patch_values.is_below_ink_floor((plancher, plancher, plancher)) is True
    assert patch_values.is_below_ink_floor((plancher + 1, 0, 0)) is False, (
        "un seul canal au-dessus du plancher rend la valeur discernable par ce canal")
    assert patch_values.is_below_ink_floor((0, 0, plancher + 1)) is False, (
        "et le canal qui sauve la valeur peut etre n'importe lequel des trois")
    # La comparaison est **large**: le plancher est le dernier niveau indiscernable,
    # pas le premier exploitable (mesure du 2026-08-10).
    assert patch_values.is_below_ink_floor((plancher - 1,) * 3) is True


def test_les_valeurs_sous_le_plancher_sont_derivees_et_non_enumerees() -> None:
    """`EPIC5-ARB-29`: un niveau ajoute sous le plancher y entrerait sans edition.

    Le test derive la liste attendue depuis les niveaux du treillis plutot que de
    recopier `lattice-008-008-008`: recopier l'identifiant ferait passer une
    implementation qui l'enumere en dur, c'est-a-dire celle que l'arbitrage interdit.
    """
    attendu = {
        value.value_id for value in patch_values.calibration_lattice_values()
        if max(value.rgb) <= patch_values.SHADOW_FLOOR_8BIT}
    assert set(patch_values.ink_floor_lattice_value_ids()) == attendu
    assert attendu, "aucune valeur sous le plancher: le test serait vide"
    # Sur les niveaux en vigueur il n'y en a qu'une, et c'est celle que l'AC nomme.
    assert attendu == {"lattice-008-008-008"}
    # Et elle n'est **pas** couverte par la garde des sondes d'ombre: c'est tout le
    # motif de l'AC 7, et cette frontiere doit rester verifiee.
    assert not any(value_id.startswith(patch_values.SHADOW_PROBE_ID_PREFIX)
                   for value_id in attendu)


def test_la_garde_du_plancher_refuse_et_rend_le_jeu_inchange_sinon() -> None:
    """Une garde qui refuse, pas un filtre a ne pas oublier -- meme motif de conception
    que `ensure_no_shadow_probe_in_adjustment_set`.

    La valeur fautive est placee **en troisieme position sur quatre**: une garde qui ne
    regarderait que la tete du jeu passerait un test dont la cible est en premier.
    """
    treillis = {value.value_id: value
                for value in patch_values.calibration_lattice_values()}
    saines = [treillis["lattice-068-068-068"], treillis["lattice-128-128-128"],
              treillis["lattice-188-188-188"], treillis["lattice-245-245-245"]]
    assert len({value.rgb for value in saines}) == 4, (
        "quatre valeurs distinguables: un remplissage uniforme rendrait invisible "
        "toute erreur d'appariement")
    assert patch_values.ensure_no_ink_floor_value_in_adjustment_set(saines) == \
        tuple(saines)

    fautive = list(saines)
    fautive.insert(2, treillis["lattice-008-008-008"])
    with pytest.raises(patch_values.InkFloorValueInAdjustmentSetError) as erreur:
        patch_values.ensure_no_ink_floor_value_in_adjustment_set(fautive)
    assert "lattice-008-008-008" in str(erreur.value)
    assert str(patch_values.SHADOW_FLOOR_8BIT) in str(erreur.value)


def test_le_plancher_d_encrage_ne_tronque_pas_les_mesures_fractionnaires() -> None:
    """Finding de revue de 5.20 (ferme le 2026-08-19): `int()` deplacait la frontiere.

    Le predicat lisait `max(int(channel) ...)`, donc `(20.9, 20.9, 20.9)` -- dont les
    trois canaux sont **au-dessus** d'un plancher de 20 -- etait juge sous le plancher.
    L'ecart va jusqu'a un code entier, et il ne se voit sur aucun triplet du treillis,
    qui est entier par construction: il mord sur une mesure agregee ou interpolee, c'est
    a dire sur ce qu'un appelant a en main quand il verifie un jeu construit ailleurs.

    Les valeurs sont ecrites **en litteral** et non derivees de `SHADOW_FLOOR_8BIT`: un
    test qui boucle sur la constante que le code lit ne dit plus rien du plancher.
    """
    # Le plancher en vigueur vaut 20, et le test le dit plutot que de le lire.
    assert patch_values.SHADOW_FLOOR_8BIT == 20

    # Sous le plancher, ou exactement dessus (comparaison large, mesure du 2026-08-10).
    assert patch_values.is_below_ink_floor((8, 8, 8)) is True
    assert patch_values.is_below_ink_floor((20, 20, 20)) is True
    assert patch_values.is_below_ink_floor((19.5, 19.5, 19.5)) is True
    assert patch_values.is_below_ink_floor((20.0, 20.0, 20.0)) is True

    # Au-dessus. C'est ici que la troncature mordait: 20,9 -> 20 -> « sous le plancher ».
    assert patch_values.is_below_ink_floor((20.9, 20.9, 20.9)) is False
    assert patch_values.is_below_ink_floor((20.1, 20.1, 20.1)) is False
    assert patch_values.is_below_ink_floor((21, 21, 21)) is False

    # Et l'asymetrie du predicat reste celle du canal le plus clair: un seul canal
    # au-dessus suffit a rendre la valeur discernable, meme fractionnaire.
    assert patch_values.is_below_ink_floor((20.5, 3, 3)) is False
    assert patch_values.is_below_ink_floor((3, 20.5, 3)) is False
    assert patch_values.is_below_ink_floor((3, 3, 20.5)) is False


def test_les_deux_gardes_de_plancher_sont_distinctes_et_ne_se_recouvrent_pas() -> None:
    """Deux familles sous le meme plancher physique, deux criteres, deux exceptions.

    Les confondre serait tentant et faux: la garde des sondes d'ombre travaille sur des
    **identifiants nus** (les sondes ne sont imprimees par aucune page, elles n'ont pas
    de triplet dans ce module), celle du plancher sur des **valeurs**. Aucune des deux
    ne peut donc remplacer l'autre.
    """
    assert not issubclass(patch_values.InkFloorValueInAdjustmentSetError,
                          patch_values.ShadowProbeInAdjustmentSetError)
    assert not issubclass(patch_values.ShadowProbeInAdjustmentSetError,
                          patch_values.InkFloorValueInAdjustmentSetError)
    # La garde des sondes ne voit rien d'anormal dans le point du treillis...
    assert patch_values.ensure_no_shadow_probe_in_adjustment_set(
        ("lattice-008-008-008",)) == ("lattice-008-008-008",)
    # ... et le plancher, lui, le refuse. C'est exactement l'ecart que l'AC 7 comble.
    treillis = {value.value_id: value
                for value in patch_values.calibration_lattice_values()}
    with pytest.raises(patch_values.InkFloorValueInAdjustmentSetError):
        patch_values.ensure_no_ink_floor_value_in_adjustment_set(
            [treillis["lattice-068-068-068"], treillis["lattice-008-008-008"]])


def test_le_treillis_imprime_ne_perd_aucune_pastille() -> None:
    """**Frontiere negative de l'AC 7**: le plancher exclut de l'ajustement, jamais de
    l'impression.

    `calibration_lattice_adjustment_values` place les pastilles de la page de
    calibration. Y appliquer le filtre retirerait une pastille de la grille, donc
    deplacerait toutes les suivantes -- et les pages deja tirees ne se reliraient plus
    aux positions ou elles ont ete imprimees. Une valeur imprimee et mesuree qu'on
    n'ajuste pas reste une valeur qu'on peut juger.
    """
    imprimees = {value.value_id
                 for value in patch_values.calibration_lattice_adjustment_values()}
    assert set(patch_values.ink_floor_lattice_value_ids()) <= imprimees
    # Le cardinal, epingle: c'est lui qui gouverne la geometrie de la planche.
    assert len(imprimees) == sum(
        1 for value in patch_values.calibration_lattice_values()
        if patch_values.lattice_saturation_8bit(value.rgb)
        <= patch_values.CALIBRATION_LATTICE_SATURATION_LIMIT_8BIT)
