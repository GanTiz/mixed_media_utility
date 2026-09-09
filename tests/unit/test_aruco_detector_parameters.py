"""Dimensionnement du seuillage adaptatif de la detection ArUco (2026-08-10).

Correction d'un defaut de terrain: la page 1 du lot `TEST_FILE_12p5` etait
refusee par `MissingMarkersError` (coin 2 absent) alors que son QR decodait
parfaitement et que les six autres pages du meme document passaient. La cause
n'etait ni le QR ni la qualite du scan, mais le jeu de fenetres de seuillage
propose par `cv2.aruco.DetectorParameters()`: voir le bloc de diagnostic chiffre
en tete de `detection/aruco.py`.

Deux familles de tests ici, et elles ne se remplacent pas:

* la **regression de terrain**, sur le raster reel qui echouait. C'est le seul
  test qui prouve que le defaut observe est ferme; une fixture de synthese ne le
  fait pas -- essayee, elle passe avec les parametres par defaut, son bord net
  suffisant a fermer le contour la ou un bord de scan reel ne suffit pas;
* les **proprietes du calcul de parametres**, qui verrouillent ce que le
  correctif promet: un balayage surensemble de celui d'OpenCV, un plafond jamais
  abaisse, une derivation depuis le dictionnaire et non une constante.
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import layout
from mixed_media_utility.detection import aruco as aruco_detection


#: Raster reel du coin qui echouait: marqueur 2 de la page 1 du lot
#: `TEST_FILE_12p5`, decoupe a 600 ppp avec sa marge de silence imprimee
#: (`MARKER_QUIET_ZONE_MM`) sur les quatre cotes. Conserve en niveaux de gris,
#: qui est ce que `cv2.aruco` binarise de toute facon.
FIELD_FIXTURE_PATH = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "aruco"
    / "corner_marker_2_600dpi_TEST_FILE_12p5_page1.png"
)
FIELD_FIXTURE_DPI = 600
FIELD_FIXTURE_MARKER_ID = 2


@pytest.fixture
def field_corner() -> np.ndarray:
    image = cv2.imread(str(FIELD_FIXTURE_PATH), cv2.IMREAD_UNCHANGED)
    assert image is not None, f"Fixture de terrain introuvable: {FIELD_FIXTURE_PATH}"
    return image


def _detected_ids(image: np.ndarray, parameters) -> set[int]:
    dictionary = cv2.aruco.getPredefinedDictionary(layout.ARUCO_DICTIONARY)
    detector = cv2.aruco.ArucoDetector(dictionary, parameters)
    _corners, ids, _rejected = detector.detectMarkers(
        aruco_detection.as_detection_view(image)
    )
    return set() if ids is None else {int(marker_id) for marker_id in ids.flatten()}


def _window_sizes(parameters) -> set[int]:
    """Fenetres que `cv2.aruco` balaye reellement pour ces parametres.

    Recopie la recette d'OpenCV (`winSizeMin + i * winSizeStep`, tant que le
    plafond n'est pas depasse) plutot que de comparer les trois attributs un a
    un: c'est l'ensemble des fenetres qui porte la propriete de surensemble, et
    trois attributs egaux deux a deux ne la disent pas.
    """
    sizes = set()
    size = int(parameters.adaptiveThreshWinSizeMin)
    step = int(parameters.adaptiveThreshWinSizeStep)
    while size <= int(parameters.adaptiveThreshWinSizeMax):
        sizes.add(size)
        size += step
    return sizes


# --- Regression de terrain ---------------------------------------------------


def test_the_field_corner_that_used_to_be_refused_is_detected(
    field_corner: np.ndarray,
) -> None:
    assert _detected_ids(
        field_corner, aruco_detection.detector_parameters(FIELD_FIXTURE_DPI)
    ) == {FIELD_FIXTURE_MARKER_ID}


def test_the_field_corner_is_still_missed_by_the_opencv_defaults(
    field_corner: np.ndarray,
) -> None:
    """Le test ci-dessus n'est pas tautologique: le defaut est reproductible.

    Sans cette assertion, un `detector_parameters` ramene aux valeurs d'OpenCV
    laisserait le test precedent vert si la fixture venait a etre remplacee par
    un raster facile. C'est ici que vit la preuve du defaut.
    """
    assert _detected_ids(field_corner, cv2.aruco.DetectorParameters()) == set()


@pytest.mark.parametrize(
    "corner",
    ["bas_droit", "haut_gauche", "haut_droit", "bas_gauche"],
)
def test_the_field_corner_is_detected_wherever_it_sits_in_the_page(
    field_corner: np.ndarray, corner: str
) -> None:
    """Le correctif ne depend pas de la position du marqueur dans le champ.

    Le raster reel est pose tour a tour aux quatre coins d'une page A4 a 600 ppp.
    Le premier cas parametre est **`bas_droit`**, la position que le marqueur
    occupait reellement, et non le coin haut-gauche: un correctif qui ne
    marcherait qu'a l'origine du canevas passerait autrement le premier cas et
    donnerait le sentiment que la serie est verte.
    """
    width_px, height_px = layout.page_size_px(FIELD_FIXTURE_DPI)
    height, width = field_corner.shape[:2]
    origins = {
        "haut_gauche": (0, 0),
        "haut_droit": (width_px - width, 0),
        "bas_droit": (width_px - width, height_px - height),
        "bas_gauche": (0, height_px - height),
    }
    x_px, y_px = origins[corner]
    page = np.full((height_px, width_px), 255, dtype=np.uint8)
    page[y_px : y_px + height, x_px : x_px + width] = field_corner

    assert _detected_ids(
        page, aruco_detection.detector_parameters(FIELD_FIXTURE_DPI)
    ) == {FIELD_FIXTURE_MARKER_ID}


# --- Proprietes du calcul de parametres --------------------------------------


def test_modules_per_side_is_derived_from_the_dictionary_not_written_down() -> None:
    dictionary = cv2.aruco.getPredefinedDictionary(layout.ARUCO_DICTIONARY)
    border_bits = int(cv2.aruco.DetectorParameters().markerBorderBits)

    assert aruco_detection.marker_modules_per_side() == (
        int(dictionary.markerSize) + 2 * border_bits
    )
    # Valeur attendue pour le dictionnaire impose aujourd'hui (DICT_6X6_250):
    # 6 modules de donnees plus une bordure de 1 module de chaque cote.
    assert aruco_detection.marker_modules_per_side() == 8


def test_module_size_scales_with_the_printed_size_and_the_dpi() -> None:
    expected_600 = (
        layout.MARKER_SIZE_MM / 25.4 * 600 / aruco_detection.marker_modules_per_side()
    )
    assert aruco_detection.marker_module_size_px(600) == pytest.approx(expected_600)
    # Grandeur physique: doubler le DPI double le module, et la valeur mesuree
    # sur la planche reelle est bien celle du diagnostic (~88,6 px a 600 ppp).
    assert aruco_detection.marker_module_size_px(1200) == pytest.approx(
        2 * expected_600
    )
    assert aruco_detection.marker_module_size_px(600) == pytest.approx(88.58, abs=0.01)


@pytest.mark.parametrize("dpi", [0, -600, True, 600.0, "600", None])
def test_module_size_refuses_anything_that_is_not_a_positive_int(dpi) -> None:
    # `True` est de la partie: `isinstance(True, int)` vaut `True` en Python, et
    # un `dpi=True` donnerait un module de 0,15 px, donc un plafond ramene a
    # celui d'OpenCV -- le defaut corrige ici, reintroduit en silence.
    with pytest.raises(ValueError):
        aruco_detection.marker_module_size_px(dpi)


def test_the_window_sweep_is_a_superset_of_the_opencv_sweep() -> None:
    """La propriete de non-regression annoncee par le correctif.

    Meme minimum, meme pas, plafond seulement releve: une page qui detectait
    avant detecte encore, puisque toutes les fenetres d'avant sont encore
    balayees. C'est cette propriete qui autorise a corriger la detection de
    toute la chaine scan sans re-mesurer chaque story qui en depend.
    """
    default = cv2.aruco.DetectorParameters()
    for dpi in (150, 300, 600, 1200):
        tuned = aruco_detection.detector_parameters(dpi)
        assert tuned.adaptiveThreshWinSizeMin == default.adaptiveThreshWinSizeMin
        assert tuned.adaptiveThreshWinSizeStep == default.adaptiveThreshWinSizeStep
        assert _window_sizes(tuned) >= _window_sizes(default), dpi


def test_the_ceiling_never_drops_below_the_opencv_ceiling() -> None:
    """Un marqueur trop petit garde exactement le comportement d'avant.

    A 150 ppp le module ne mesure que 22,1 px, soit moins que le plafond
    d'OpenCV: le calcul doit alors rendre le plafond d'OpenCV et non 21, sans
    quoi le correctif *retirerait* une fenetre a bas DPI.
    """
    default_max = int(cv2.aruco.DetectorParameters().adaptiveThreshWinSizeMax)
    assert aruco_detection.marker_module_size_px(150) < default_max
    assert (
        aruco_detection.detector_parameters(150).adaptiveThreshWinSizeMax == default_max
    )


def test_the_ceiling_stays_within_one_module_and_stays_odd() -> None:
    for dpi in (300, 600, 1200, 2400):
        ceiling = int(
            aruco_detection.detector_parameters(dpi).adaptiveThreshWinSizeMax
        )
        # Au-dela d'un module, la moyenne locale ferait entrer le module voisin;
        # `cv2.adaptiveThreshold` exige par ailleurs une fenetre impaire.
        assert ceiling <= aruco_detection.marker_module_size_px(dpi)
        assert ceiling % 2 == 1, (dpi, ceiling)
    # Valeur attendue au DPI nominal du chemin scan.
    assert aruco_detection.detector_parameters(600).adaptiveThreshWinSizeMax == 87


def test_only_the_ceiling_moves_relative_to_the_opencv_defaults() -> None:
    """Aucun autre parametre de detection n'est touche par le correctif.

    Le diagnostic designe une seule cause; deplacer d'autres reglages du meme
    geste rendrait impossible d'attribuer un changement de comportement futur.
    """
    default = cv2.aruco.DetectorParameters()
    tuned = aruco_detection.detector_parameters(600)
    moved = [
        name
        for name in dir(default)
        if not name.startswith("_")
        and not callable(getattr(default, name))
        and getattr(tuned, name) != getattr(default, name)
    ]
    assert moved == ["adaptiveThreshWinSizeMax"]


def test_detect_markers_requires_an_explicit_dpi() -> None:
    """Le DPI n'est pas defaultable, et c'est la garde qui le dit.

    Une valeur par defaut y reintroduirait le reglage qui refusait une page dont
    le QR decodait: un refus d'apparence geometrique pour une cause de
    binarisation. Tous les appelants en disposent.
    """
    image = np.full((64, 64), 255, dtype=np.uint8)
    with pytest.raises(TypeError):
        aruco_detection.detect_markers(image)
