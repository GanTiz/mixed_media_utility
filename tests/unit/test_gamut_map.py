"""Tests du registre de compressions de gamut (story 5.10).

Le test qui vaut plus que tous les autres est l'**aller-retour a trois
niveaux** (AC 3): exactitude mathematique sur le domaine reel, aller-retour
quantifie sur la grille 8 bits reellement imprimable, et couverture des bornes
`0` et `1` -- la ou l'ecretage a lieu, precisement.

Deux enonces de monotonie coexistent et ne doivent jamais etre confondus: sur
le domaine reel `G` est **strictement** monotone; sur la grille 8 bits la
stricte monotonie est **mathematiquement impossible** des que `k < 1` (256
codes d'entree vers moins de 256 codes de sortie: principe des tiroirs). Un dev
qui testerait la stricte monotonie sur `uint8`, la verrait echouer et
« corrigerait » en ramenant `k` a 1 supprimerait la story sans que rien ne le
signale.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import gamut_map
from mixed_media_utility.io import payload as payload_io

MODULE_PATH = REPO_ROOT / "src" / "mixed_media_utility" / "gamut_map.py"
DENSE = np.linspace(0.0, 1.0, 65536)


def every_map():
    return [gamut_map.get_gamut_map(name) for name in gamut_map.known_gamut_map_ids()]


# --- AC 1: un registre versionne, pur et non substituable --------------------


def test_the_module_is_pure() -> None:
    """Motif du test de purete du depot: aucune dependance image, aucune I/O.

    Le module applique une transformation a des tableaux, donc `numpy` est
    autorise -- et lui seul.
    """
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"), filename=str(MODULE_PATH))
    forbidden = {"cv2", "PIL", "reportlab", "matplotlib", "os", "shutil", "pathlib"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in forbidden, alias.name
        if isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0] not in forbidden, node.module
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                assert alias.name not in forbidden, alias.name
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"open", "print"}, node.func.id


def test_the_registry_cannot_be_substituted_at_runtime() -> None:
    # Un dict nu laisserait remplacer une transformation a l'execution et
    # contournerait tout le versionnement -- une planche imprimee ne serait
    # plus resolvable depuis son seul identifiant.
    with pytest.raises(TypeError):
        gamut_map.GAMUT_MAPS["gamut-map-none-1"] = None
    with pytest.raises(TypeError):
        del gamut_map.GAMUT_MAPS["gamut-map-none-1"]


def test_the_identity_is_a_first_class_value_and_the_mvp_default() -> None:
    """L'identite n'est pas un cas degrade: elle **declare** qu'aucune
    compression n'a ete appliquee, ce qui est une information vraie et utile a
    l'expansion. Et c'est le defaut du MVP (EPIC5-ARB-15)."""
    identity = gamut_map.get_gamut_map(gamut_map.GAMUT_MAP_IDENTITY)
    assert identity.is_identity
    assert gamut_map.DEFAULT_GAMUT_MAP == gamut_map.GAMUT_MAP_IDENTITY
    assert gamut_map.known_gamut_map_ids()[0] == gamut_map.GAMUT_MAP_IDENTITY
    assert identity.factor == 1.0


def test_an_unknown_identifier_names_the_vocabulary() -> None:
    with pytest.raises(gamut_map.UnknownGamutMapError) as excinfo:
        gamut_map.get_gamut_map("gamut-map-perceptual-1")
    message = str(excinfo.value)
    for known in gamut_map.known_gamut_map_ids():
        assert known in message


@pytest.mark.parametrize("bad", [None, 42, ["gamut-map-none-1"], {}, ""])
def test_a_non_identifier_is_refused_not_crashed(bad) -> None:
    with pytest.raises(gamut_map.UnknownGamutMapError):
        gamut_map.get_gamut_map(bad)


def test_the_identifier_contract_is_the_one_of_story_59() -> None:
    """Une seule borne pour une meme donnee.

    5.9 a pose `GAMUT_MAP_ID_PREFIX`, `GAMUT_MAP_ID_MAX_LENGTH` et le motif;
    cette story les **consomme** au lieu d'en redeclarer une plus etroite, ce
    qui serait la double source de verite que tout l'Epic evite.
    """
    assert gamut_map.GAMUT_MAP_ID_PREFIX is payload_io.GAMUT_MAP_ID_PREFIX
    assert gamut_map.GAMUT_MAP_ID_MAX_LENGTH is payload_io.GAMUT_MAP_ID_MAX_LENGTH
    for entry in every_map():
        payload_io.validate_gamut_map_id(entry.gamut_map_id)
        assert entry.gamut_map_id.startswith(gamut_map.GAMUT_MAP_ID_PREFIX)


def test_the_shipped_identifiers_stay_under_the_budget_measured_by_59() -> None:
    """Tant que les identifiants livres restent sous 16 caracteres, les mesures
    de budget et de geometrie QR de 5.9 valent **inchangees, comme pire cas**.

    Le fragment JSON coute `18 + longueur`. A 24 caracteres -- la borne
    contractuelle -- il couterait 42 octets et rouvrirait ces mesures.
    """
    for entry in every_map():
        assert len(entry.gamut_map_id) <= 16, (
            f"{entry.gamut_map_id} depasse 16 caracteres: les mesures de budget "
            "de 5.9 doivent etre refaites avant de l'enregistrer"
        )


# --- AC 1 / AC 9: les gardes de construction ---------------------------------


def _entry(**overrides):
    fields = {
        "gamut_map_id": "gamut-map-test-1",
        "low": 0.1,
        "high": 0.9,
        "round_trip_tolerance_codes": 0.63,
        "collision_count_8bit": 52,
        "description": "essai",
    }
    fields.update(overrides)
    return gamut_map.GamutMap(**fields)


def test_a_valid_entry_is_constructible() -> None:
    assert _entry().factor == pytest.approx(0.8)


@pytest.mark.parametrize(
    "overrides",
    [
        {"gamut_map_id": "lin-1"},                    # prefixe absent
        {"gamut_map_id": "gamut-map-" + "x" * 20},    # trop long
        {"gamut_map_id": "gamut-map-LIN-1"},          # majuscules
        {"low": -0.1},
        {"high": 1.5},
        {"low": 0.9, "high": 0.9},                    # pas strictement monotone
        {"low": 0.9, "high": 0.1},                    # inverse
        {"low": 0.0, "high": 0.4},                    # k = 0.4 < 0.5
        {"low": True, "high": 0.9},                   # bool est un int
        {"round_trip_tolerance_codes": -1.0},
        {"round_trip_tolerance_codes": True},
        {"collision_count_8bit": -1},
        {"collision_count_8bit": True},
        {"collision_count_8bit": 2.0},
    ],
)
def test_a_malformed_entry_is_refused_at_construction(overrides) -> None:
    with pytest.raises(gamut_map.GamutMapError):
        _entry(**overrides)


def test_the_compression_factor_floor_is_declared_with_its_motive() -> None:
    """`k = 0.5` double deja le bruit du scanner **et** le pas de
    quantification au retour: en dessous, l'expansion amplifierait plus de
    bruit qu'elle ne recupere d'information."""
    assert gamut_map.MIN_COMPRESSION_FACTOR == 0.5
    _entry(low=0.25, high=0.75)  # k = 0.5 exactement: accepte
    with pytest.raises(gamut_map.GamutMapError) as excinfo:
        _entry(low=0.25, high=0.74)  # k = 0.49: refuse
    assert "plancher" in str(excinfo.value)


def test_every_shipped_entry_declares_its_own_cost() -> None:
    # Les tests des AC 2 et 3 **lisent** ces valeurs au lieu de les recopier:
    # enregistrer une compression plus agressive ne doit pas pouvoir passer
    # sous une tolerance ecrite pour une autre.
    for entry in every_map():
        assert entry.factor >= gamut_map.MIN_COMPRESSION_FACTOR
        assert entry.round_trip_tolerance_codes >= 0
        assert entry.collision_count_8bit >= 0
        assert entry.description


# --- AC 2: les deux enonces de monotonie -------------------------------------


@pytest.mark.parametrize("entry", every_map(), ids=lambda e: e.gamut_map_id)
def test_g_is_strictly_monotonic_on_the_real_domain(entry) -> None:
    """Enonce (a): **aucune** egalite toleree, sur 65536 echantillons.

    Un plateau, c'est plusieurs valeurs sources sur la meme sortie: la perte
    plusieurs-vers-un que `G` existe pour supprimer.
    """
    compressed = entry.compress(DENSE)
    assert np.all(np.diff(compressed) > 0), entry.gamut_map_id
    assert compressed[0] == pytest.approx(entry.low)
    assert compressed[-1] == pytest.approx(entry.high)


@pytest.mark.parametrize("entry", every_map(), ids=lambda e: e.gamut_map_id)
def test_g_is_only_weakly_monotonic_on_the_printable_8_bit_grid(entry) -> None:
    """Enonce (b): la stricte monotonie y est **impossible** des que `k < 1`.

    256 codes d'entree vers moins de 256 codes de sortie: principe des tiroirs.
    Le cardinal de collisions est **borne et declare** par l'entree, et c'est
    lui qu'on verifie -- pas une absence de collision qui serait un mensonge.
    """
    codes = np.arange(256, dtype=np.uint8).reshape(1, 256)
    printed = entry.to_print_8bit(codes)[0].astype(int)
    assert np.all(np.diff(printed) >= 0), "monotonie large exigee"
    collisions = 256 - len(np.unique(printed))
    assert collisions == entry.collision_count_8bit, (
        f"{entry.gamut_map_id}: {collisions} collisions mesurees pour "
        f"{entry.collision_count_8bit} declarees"
    )
    if entry.is_identity:
        assert collisions == 0
    else:
        assert collisions > 0, "une compression sans collision n'en est pas une"


def test_the_module_explains_what_distinguishes_g_from_clipping() -> None:
    # L'ecretage concentre une perte **non bornee** aux extremites; la
    # quantification repartit une perte **bornee par 1/k**. Sans cette phrase,
    # un lecteur conclut que `G` echange une perte contre une autre.
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "non bornee" in source and "bornee par" in source


# --- AC 3: l'aller-retour, aux trois niveaux ---------------------------------


@pytest.mark.parametrize("entry", every_map(), ids=lambda e: e.gamut_map_id)
def test_round_trip_is_mathematically_exact(entry) -> None:
    """Niveau (i): `expand(compress(x)) == x` a 1e-9 pres, identite comprise."""
    assert np.abs(entry.expand(entry.compress(DENSE)) - DENSE).max() < 1e-9


@pytest.mark.parametrize("entry", every_map(), ids=lambda e: e.gamut_map_id)
def test_round_trip_stays_within_the_declared_tolerance_once_quantised(entry) -> None:
    """Niveau (ii): sur les 256 codes reellement imprimables.

    La tolerance est **portee par l'entree de registre**, jamais recopiee ici:
    c'est ce qui fait qu'enregistrer une compression plus agressive ne peut pas
    passer sous une tolerance ecrite pour une autre.
    """
    source_codes = np.arange(256)
    printed = entry.to_print_8bit(source_codes.astype(np.uint8).reshape(1, 256))[0]
    recovered = entry.expand(printed.astype(np.float64) / 255.0) * 255.0
    error = np.abs(recovered - source_codes)
    assert error.max() <= entry.round_trip_tolerance_codes, (
        f"{entry.gamut_map_id}: {error.max():.4f} > "
        f"{entry.round_trip_tolerance_codes}"
    )
    # Apres re-arrondi, l'ecart tient dans un code.
    assert np.abs(np.rint(recovered) - source_codes).max() <= 1


@pytest.mark.parametrize("entry", every_map(), ids=lambda e: e.gamut_map_id)
def test_the_domain_covers_the_bounds_where_clipping_happens(entry) -> None:
    """Niveau (iii): `0` et `255` inclus, jamais un echantillonnage du milieu.

    Les bornes sont precisement la ou l'ecretage a lieu -- les tester au milieu
    du domaine reviendrait a ne pas tester `G` du tout.
    """
    assert DENSE[0] == 0.0 and DENSE[-1] == 1.0
    extremes = entry.to_print_8bit(np.array([[0, 255]], dtype=np.uint8))[0]
    if entry.is_identity:
        assert list(extremes) == [0, 255]
    else:
        # Le contenu sort des deux zones d'ecretage par canal.
        assert extremes[0] > 0, "le noir doit quitter la saturation d'encrage"
        assert extremes[1] < 255, "le blanc doit quitter le papier nu"


def test_the_linear_entry_has_the_cost_the_story_measured() -> None:
    # Chiffres a figer: ils justifient le choix de la forme, et un glissement
    # silencieux les rendrait faux dans la documentation.
    linear = gamut_map.get_gamut_map("gamut-map-lin-1")
    assert (linear.low, linear.high) == (0.06, 0.94)
    assert linear.factor == pytest.approx(0.88)
    assert 1.0 / linear.factor == pytest.approx(1.136, abs=0.001)
    printed = linear.to_print_8bit(np.arange(256, dtype=np.uint8).reshape(1, 256))[0]
    assert (int(printed.min()), int(printed.max())) == (15, 240)
    assert len(np.unique(printed)) == 226


# --- AC 4 / AC 10: quantification unique, identite bit-exacte ----------------


@pytest.mark.parametrize("shape", [(9, 7), (9, 7, 3), (9, 7, 4)])
@pytest.mark.parametrize("dtype", [np.uint8, np.uint16])
def test_the_identity_is_bit_exact_with_the_original_contract(shape, dtype) -> None:
    """L'ancrage de non-regression le plus sur d'une restructuration qui touche
    le seul chemin de pixels du PDF: la troncature `>> 8` d'origine, bit pour
    bit, sur le chemin **nominal** du MVP."""
    top = 256 if dtype is np.uint8 else 65536
    array = np.random.default_rng(510).integers(0, top, size=shape, dtype=dtype)
    identity = gamut_map.get_gamut_map(gamut_map.GAMUT_MAP_IDENTITY)
    expected = array if dtype is np.uint8 else (array >> 8).astype(np.uint8)
    assert np.array_equal(identity.to_print_8bit(array), expected)


def test_the_compressed_path_rounds_to_nearest_not_truncates() -> None:
    """L'asymetrie de l'AC 9b, verifiee dans les deux sens.

    Une troncature sur le chemin comprime ajouterait un demi-code de biais
    systematique que `1/k` amplifierait au retour.
    """
    linear = gamut_map.get_gamut_map("gamut-map-lin-1")
    codes = np.arange(256, dtype=np.uint8).reshape(1, 256)
    printed = linear.to_print_8bit(codes)[0].astype(np.float64)
    exact = (linear.low + linear.factor * (np.arange(256) / 255.0)) * 255.0
    assert np.array_equal(printed, np.rint(exact))
    assert not np.array_equal(printed, np.floor(exact)), "troncature detectee"


def test_the_working_dtype_is_declared() -> None:
    # Un dtype flottant implicite casserait le determinisme contractuel selon
    # la plateforme.
    assert gamut_map.WORKING_DTYPE is np.float64
    linear = gamut_map.get_gamut_map("gamut-map-lin-1")
    assert linear.compress(np.zeros(3, dtype=np.uint8)).dtype == np.float64


@pytest.mark.parametrize("entry", every_map(), ids=lambda e: e.gamut_map_id)
def test_quantisation_is_deterministic(entry) -> None:
    array = np.random.default_rng(7).integers(0, 65536, size=(13, 11, 3), dtype=np.uint16)
    assert np.array_equal(entry.to_print_8bit(array), entry.to_print_8bit(array))


@pytest.mark.parametrize("bad", [np.zeros((3, 3), dtype=np.int16),
                                 np.zeros((3, 3), dtype=np.float32),
                                 np.zeros((3, 3), dtype=np.int32)])
def test_an_unsupported_depth_is_refused(bad) -> None:
    identity = gamut_map.get_gamut_map(gamut_map.GAMUT_MAP_IDENTITY)
    with pytest.raises(gamut_map.GamutMapError) as excinfo:
        identity.to_print_8bit(bad)
    assert "Profondeur" in str(excinfo.value)


@pytest.mark.parametrize("bad", [None, [0, 1, 2], "image", 3])
def test_a_non_array_is_refused(bad) -> None:
    identity = gamut_map.get_gamut_map(gamut_map.GAMUT_MAP_IDENTITY)
    with pytest.raises(gamut_map.GamutMapError):
        identity.to_print_8bit(bad)


def test_the_output_never_leaves_the_8_bit_range() -> None:
    # `np.clip` protege d'une entree de registre future dont `low`/`high`
    # sortiraient du domaine: la garde de construction l'interdit deja, mais un
    # depassement produirait ici un repliage silencieux du `uint8`.
    linear = gamut_map.get_gamut_map("gamut-map-lin-1")
    array = np.array([[0, 32768, 65535]], dtype=np.uint16)
    printed = linear.to_print_8bit(array)
    assert printed.dtype == np.uint8
    assert 0 <= int(printed.min()) and int(printed.max()) <= 255


# --- AC 13: la garde bool/int passe par le helper partage --------------------


def test_the_bool_guard_comes_from_the_shared_helper() -> None:
    """L'action item 2 de la retro Epic 4.

    La story annonce le helper « a creer »; il **existe** depuis la story 5.9
    (`numeric_guards`) et cinq modules le consomment. Cette story le reutilise
    au lieu d'ecrire une 26e copie inline du motif.
    """
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"), filename=str(MODULE_PATH))
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
        and node.module.endswith("numeric_guards")
        for alias in node.names
    }
    assert {"is_strict_int", "is_strict_number"} <= imported
    # Aucune copie inline du motif.
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "isinstance(" not in source.replace(
        "isinstance(array, np.ndarray)", ""
    ), "la garde de type numerique passe par le helper, pas par une copie"
