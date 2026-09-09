"""Minimal ArUco detection, page homography and deskewed frame extraction.

This module consumes the canonical layout defined in ``mixed_media_utility.layout``
so that the pixel destination space used to compute the page homography exactly
matches the physical positions of the corner markers and frame zones printed on
the patch sheet.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from mixed_media_utility import color_pipeline, layout
from mixed_media_utility.numeric_guards import is_strict_int

# Extension imposee aux frames rescannees depuis la story 5.0: le chemin scan
# n'ecrit plus de PNG 8 bits. Derivee de `color_pipeline`, non recopiee: une
# seconde ecriture litterale de "tiff" pourrait diverger de la garde
# `TIFF_EXTENSIONS` qui, elle, decide si l'ecriture est acceptee.
SCAN_FRAME_EXTENSION = f".{color_pipeline.MVP_OUTPUT_FORMAT}"

# Sorties purgees avant un rejeu, filtrees par suffixe et non par motif de glob:
# un glob est sensible a la casse, alors que la garde d'ecriture ne l'est pas
# (`color_pipeline.py:176`), et un `scan_frame_0001.PNG` echappait donc a la
# purge. Le `.png` reste de la partie: un residu ecrit par une version
# anterieure survivrait sinon a cote des `.tiff` et un consommateur par `glob`
# melangerait deux profondeurs.
SCAN_FRAME_GLOB = "scan_frame_*"
SCAN_FRAME_STALE_SUFFIXES = (".png",) + color_pipeline.TIFF_EXTENSIONS


class PageGeometryError(ValueError):
    """Base error for any condition that makes the page homography untrustworthy.

    Callers that simply want to reject a bad scan should catch this class; the
    subclasses below distinguish *why* the page was rejected.
    """


class MissingMarkersError(PageGeometryError):
    """Raised when the expected corner ArUco markers cannot all be found."""


class AmbiguousMarkersError(PageGeometryError):
    """Raised when a corner ArUco ID is detected more than once on the same page.

    Two markers carrying the same corner ID (a second sheet on the scanner glass,
    a neighbouring page in frame) make the corner assignment ambiguous. Silently
    keeping one of them would compute a homography on the wrong geometry, so the
    scan is rejected instead (story 4.3, TEST_PLAN 4.3 "politique si IDs
    incoherents").
    """


class DegeneratePageGeometryError(PageGeometryError):
    """Raised when the 4 corner markers do not form a usable convex quadrilateral.

    ``cv2.findHomography`` happily returns a rank-deficient matrix when three of
    the four source points are (near-)collinear -- a folded page or a very
    grazing capture angle. That matrix warps to a plausible-looking but
    geometrically meaningless page, so the degeneracy must be caught explicitly
    rather than trusted (story 4.3 review).
    """


class ScanFrameExtractionError(RuntimeError):
    """Raised when a rescanned frame zone cannot be cropped or written to disk."""


class UnsupportedScanDepthError(ValueError):
    """Raised when a scan carries a pixel depth the detection cannot be shown.

    Policy copied from ``pdf_render.load_frame_image_for_print`` (4.1 review):
    any depth other than 8 or 16 unsigned bits per channel is refused
    *explicitly* rather than converted in silence -- and, above all, rather than
    surfacing as a bare ``cv2.error`` assertion raised deep inside cv2.aruco,
    several frames away from the cause.

    This became reachable with story 5.0: reading with ``IMREAD_UNCHANGED``
    widens the set of dtypes that reach the detector. A plain ``cv2.imread``
    returned either ``None`` (32-bit TIFF) or a silently converted ``uint8``
    array (Radiance ``.hdr``, ``.pfm``); neither is an honest answer, but both
    were caught. Converting a float or signed scan here would mean choosing, on
    the operator's behalf, which input range becomes 0..65535 -- exactly the
    kind of undeclared decision the story removes.
    """


def as_detection_view(image: np.ndarray) -> np.ndarray:
    """Return the 8-bit view ``cv2.aruco`` requires, derived from ``image``.

    ``cv2.aruco`` refuses anything but ``CV_8UC1``/``CV_8UC3``/``CV_8UC4``: a
    16-bit array raises ``(-215) _in.type() == CV_8UC1 || ...``, in grayscale as
    well as in colour (measured on OpenCV 5.0.0). The reflex of converting the
    *whole* scan to 8 bits on the way in is exactly the truncation story 5.0
    removes, so the reduction is confined here: the returned array is a derived
    view used for detection only and is never written back into the array that
    carries the pixels.

    The reduction uses ``>> 8``, the conversion already documented and used by
    ``pdf_render.load_frame_image_for_print``; inventing a second recipe would
    be the divergence the 5.5 review closed. Any other depth is refused by
    ``UnsupportedScanDepthError`` -- the same module's policy, not the opposite
    one: letting a float32 array through would only move the refusal into a bare
    ``cv2.error`` assertion with no actionable message.
    """
    if not isinstance(image, np.ndarray):
        raise UnsupportedScanDepthError(
            f"Image de scan attendue de type numpy.ndarray, recu: {type(image).__name__}"
        )
    if image.dtype == np.uint8:
        return image
    if image.dtype.kind == "u" and image.dtype.itemsize == 2:
        # numpy shifts *values*, not bytes: `>> 8` is already correct on the
        # big-endian `>u2` a scanner writes in `MM` byte order. The astype()
        # that follows is what hands cv2 a native-order, contiguous uint8 array.
        return (image >> 8).astype(np.uint8)
    raise UnsupportedScanDepthError(
        f"Profondeur de pixel non geree pour la detection: {image.dtype}. "
        "Attendu 8 ou 16 bits non signes par canal (png/jpg/tiff). Un scan "
        "flottant (TIFF 32 bits, .hdr, .pfm) ou signe doit etre converti en "
        "amont: le convertir ici reviendrait a choisir a la place de "
        "l'operateur quelle plage d'entree devient 0-65535."
    )


# --- Seuillage adaptatif: dimensionne sur le module imprime ----------------
#
# Diagnostic du 2026-08-10, sur le lot `TEST_FILE_12p5` fourni par Egan: sa
# page 1 etait refusee (`MissingMarkersError`, coin 2 absent) alors que son QR
# decodait parfaitement -- un telephone y arrivait meme en filmant l'ecran -- et
# que les six autres pages du meme document passaient. La cause n'est donc ni le
# QR, ni la qualite du scan: c'est le **jeu de fenetres de seuillage** que
# `cv2.aruco.DetectorParameters()` propose par defaut.
#
# Le mecanisme est celui du seuillage adaptatif **a moyenne locale**, et il n'a
# rien d'optique. `cv2.aruco` binarise par `ADAPTIVE_THRESH_MEAN_C`: un pixel est
# de l'encre si sa valeur passe sous `moyenne_locale - C`, avec `C = 7` par
# defaut. Or a 600 ppp la bordure noire d'un marqueur de 30 mm est une bande de
# **un module, soit 87 px d'epaisseur**, quasi uniforme -- mesure sur le coin 2
# de la page fautive: encre a 67 d'ecart-type 6,7, papier a 255 d'ecart-type 0.
# Au coeur d'une bande aussi large, la moyenne locale **est** la valeur de
# l'encre: le pixel se compare a lui-meme moins 7, et c'est le bruit du scan
# (6,7, soit exactement l'ordre de `C`) qui decide seul de son classement. Une
# fenetre de W px ne binarise donc correctement qu'un lisere de ~W/2 px le long
# de chaque transition encre/papier, et le detecteur a besoin que ce lisere forme
# un contour **ferme** autour du marqueur.
#
# Mesure du 2026-08-10, coin 2 de la page fautive, part du coeur de la bande de
# bordure reconnue comme encre, et coins trouves sur la page entiere avec cette
# fenetre **unique** imposee:
#
#   fenetre |  3 |   13 |   23 |   33 |   43 |   63 |   87
#   --------|----|------|------|------|------|------|-----
#   coeur   | 5% |  18% |  19% |  24% |  29% |  40% |  53%
#   coins   | 0/4|  3/4 |  3/4 |  4/4 |  4/4 |  4/4 |  4/4
#
# Meme balayage a fenetre unique sur les dix pages scannees reelles du depot
# (7 pages de `TEST_FILE_12p5` + 3 pages de `rush_test_235_1920x817_25fps_5`):
#
#   fenetre |  3 |  13 |     23 | 33 .. 133
#   --------|----|-----|--------|----------
#   pages   |  0 | 2-4 | 3 ou 4 |         4
#
# Autrement dit **les trois fenetres par defaut sont toutes dans la zone
# fragile**: la chaine de scan tournait depuis le debut sur un coup de chance, et
# la page 1 de TEST_FILE est simplement la premiere a etre tombee du mauvais
# cote. Le plateau a 4/4 commence a 33 px, soit ~0,37 module, et tient jusqu'a
# 133 px, soit ~1,5 module.
#
# Corollaire de diagnostic, qui evite de chercher au mauvais endroit: augmenter
# `adaptiveThreshConstant` ne corrige **rien**. Au coeur de la bande la moyenne
# locale vaut la valeur de l'encre quelle que soit la constante; seule la
# **taille de la fenetre** fait entrer du papier dans la moyenne.
#
# Le correctif ne touche donc **que le plafond du balayage**, porte a la taille
# d'un module au DPI de detection. Deux proprietes sont tenues a dessein:
#
# * le jeu de fenetres reste un **surensemble** de celui d'OpenCV (meme minimum,
#   meme pas): une page qui detectait avant detecte encore, le correctif ne peut
#   qu'ajouter des candidats. Verifie sur les dix pages: aucun ID de coin ne
#   sort en double, donc aucune page ne bascule en `AmbiguousMarkersError`;
# * le plafond ne descend **jamais** sous celui d'OpenCV, donc un marqueur tres
#   petit (scan a bas DPI) garde exactement le comportement d'avant.
#
# Deux corollaires assumes:
#
# * la mesure de faisabilite de la story 4.4 (`temp/aruco_experiment_results.md`)
#   a ete produite avec les parametres **par defaut**. Ses seuils mm/ppp decrivent
#   donc ce reglage-la et pas le papier, et ils sous-estiment la robustesse
#   reelle -- d'autant que la faute grandit avec le DPI, ce qui inverse le sens de
#   lecture habituel de ce tableau (« plus de ppp, plus sur »). Ils ne sont pas
#   re-mesures ici: ce serait refaire la story, pas corriger le defaut;
# * deux autres correctifs mesures rendent aussi 10/10 sur les dix pages, et sont
#   ecartes plutot qu'ignores: detecter sur une vue sous-echantillonnee (demi ou
#   quart de resolution), et passer un passe-bas dimensionne sur le module avant
#   seuillage (k = module/3 ou module/6). Les deux deplacent les centres de coin
#   davantage -- jusqu'a 1,03 px contre 0,56 px pour le correctif retenu -- et le
#   centre de coin est l'entree de l'homographie de page. Consignes au
#   `deferred-work.md` comme voie de repli si un tirage futur defaisait encore le
#   balayage.


def marker_modules_per_side() -> int:
    """Nombre de modules sur un cote d'un marqueur imprime, bordure comprise.

    Derive du dictionnaire et de `markerBorderBits`, jamais ecrit en dur: un
    changement de `layout.ARUCO_DICTIONARY` (DICT_4X4 en compte 6, DICT_6X6 en
    compte 8) doit redimensionner le seuillage du meme geste. Une constante a 8
    recopiee ici serait juste aujourd'hui et fausse en silence le jour ou le
    dictionnaire change -- exactement le motif de `dictionary_name()`.
    """
    dictionary = cv2.aruco.getPredefinedDictionary(layout.ARUCO_DICTIONARY)
    border_bits = cv2.aruco.DetectorParameters().markerBorderBits
    return int(dictionary.markerSize) + 2 * int(border_bits)


def marker_module_size_px(dpi: int) -> float:
    """Cote d'un module de marqueur, en pixels, pour un scan a ``dpi``.

    C'est la seule grandeur qui relie la geometrie physique de la planche au
    reglage du seuillage: elle se lit en millimetres imprimes (`MARKER_SIZE_MM`)
    et se convertit au DPI de lecture, comme tout le reste du chemin scan.
    """
    if not is_strict_int(dpi) or dpi <= 0:
        raise ValueError(
            f"dpi invalide pour le dimensionnement du seuillage: {dpi!r}. "
            "Attendu un entier strictement positif."
        )
    return layout.MARKER_SIZE_MM / 25.4 * dpi / marker_modules_per_side()


def detector_parameters(dpi: int) -> cv2.aruco.DetectorParameters:
    """Parametres de detection dimensionnes sur la planche lue a ``dpi``.

    Seul `adaptiveThreshWinSizeMax` s'ecarte du defaut d'OpenCV, et jamais vers
    le bas: voir le commentaire de diagnostic ci-dessus pour la mesure qui le
    justifie. Le minimum et le pas restent ceux d'OpenCV pour que le balayage
    demeure un surensemble du sien.
    """
    parameters = cv2.aruco.DetectorParameters()
    # Plus grand impair inferieur ou egal a un module: `cv2.adaptiveThreshold`
    # exige une fenetre impaire, et depasser le module ferait entrer le module
    # voisin dans la moyenne locale.
    ceiling = int(marker_module_size_px(dpi))
    if ceiling % 2 == 0:
        ceiling -= 1
    parameters.adaptiveThreshWinSizeMax = max(
        int(parameters.adaptiveThreshWinSizeMax), ceiling
    )
    return parameters


def detect_markers(image: np.ndarray, *, dpi: int):
    """Detect ArUco markers in ``image`` using the dictionary imposed for this slice.

    ``image`` may carry any depth the scan path produces: detection runs on the
    8-bit view derived by ``as_detection_view`` while the caller keeps its
    full-depth array untouched. A depth outside 8/16 unsigned bits raises
    ``UnsupportedScanDepthError`` rather than a bare cv2 assertion.

    ``dpi`` est **exige** et non defaultable: c'est lui qui donne la taille du
    module imprime, donc le dimensionnement du seuillage adaptatif (voir le
    diagnostic ci-dessus). Une valeur par defaut y reintroduirait precisement le
    reglage qui refusait une page dont le QR decodait -- un refus d'apparence
    geometrique pour une cause de binarisation. Tous les appelants en disposent:
    le chemin POC le tient de `--dpi`, le chemin scan du rapport d'ingestion.

    Returns the ``(corners, ids)`` tuple as produced by cv2.aruco's detector.
    """
    dictionary = cv2.aruco.getPredefinedDictionary(layout.ARUCO_DICTIONARY)
    detector = cv2.aruco.ArucoDetector(dictionary, detector_parameters(dpi))
    corners, ids, _rejected = detector.detectMarkers(as_detection_view(image))
    return corners, ids


def build_markers_document(image_path: str | Path, corners, ids) -> dict:
    """Build the ``markers.json`` document structure for a single detected image."""
    markers = []
    if ids is not None:
        for marker_corners, marker_id in zip(corners, ids.flatten().tolist()):
            points = marker_corners.reshape(4, 2)
            center = points.mean(axis=0)
            markers.append(
                {
                    "id": int(marker_id),
                    "corners": [[float(x), float(y)] for x, y in points],
                    "center": [float(center[0]), float(center[1])],
                }
            )
    markers.sort(key=lambda marker: marker["id"])
    return {"images": [{"path": str(image_path), "markers": markers}]}


def compute_page_homography(markers_doc: dict, dpi: int) -> tuple[np.ndarray, int, int]:
    """Compute the homography mapping detected marker centers to the canonical
    (deskewed) page pixel space at ``dpi``.

    Raises MissingMarkersError if fewer than ``layout.MIN_CORNER_MARKERS_REQUIRED``
    corner markers are present, AmbiguousMarkersError if a corner ID appears more
    than once, and DegeneratePageGeometryError if the corners do not form a usable
    convex quadrilateral.
    """
    detected = markers_doc["images"][0]["markers"]

    duplicated = sorted(
        {
            marker["id"]
            for marker in detected
            if marker["id"] in layout.CORNER_MARKER_IDS
            and sum(1 for other in detected if other["id"] == marker["id"]) > 1
        }
    )
    if duplicated:
        raise AmbiguousMarkersError(
            f"Marqueurs ArUco de coin en double: {duplicated}. "
            "Un meme ID de coin est present plusieurs fois sur la page: "
            "l'assignation des coins est ambigue (deuxieme planche sur la vitre "
            "ou page voisine dans le champ ?)."
        )

    markers_by_id = {marker["id"]: marker for marker in detected}
    present = [marker_id for marker_id in layout.CORNER_MARKER_IDS if marker_id in markers_by_id]
    if len(present) < layout.MIN_CORNER_MARKERS_REQUIRED:
        missing = [
            marker_id for marker_id in layout.CORNER_MARKER_IDS if marker_id not in markers_by_id
        ]
        raise MissingMarkersError(
            f"Marqueurs ArUco de coin manquants: {missing}. "
            f"IDs attendus: {list(layout.CORNER_MARKER_IDS)} "
            f"(minimum requis: {layout.MIN_CORNER_MARKERS_REQUIRED})."
        )

    src_points = np.array(
        [markers_by_id[marker_id]["center"] for marker_id in layout.CORNER_MARKER_IDS],
        dtype=np.float32,
    )
    _assert_usable_corner_quadrilateral(src_points)

    centers_mm = layout.corner_marker_centers_mm()
    dst_points = np.array(
        [layout.mm_to_px(*centers_mm[marker_id], dpi) for marker_id in layout.CORNER_MARKER_IDS],
        dtype=np.float32,
    )

    homography, _ = cv2.findHomography(src_points, dst_points)
    if homography is None:
        raise MissingMarkersError(
            "Impossible de calculer l'homographie de page a partir des marqueurs detectes."
        )

    width_px, height_px = layout.page_size_px(dpi)
    return homography, width_px, height_px


def _assert_usable_corner_quadrilateral(src_points: np.ndarray) -> None:
    """Reject corner layouts that make the homography numerically meaningless.

    ``CORNER_MARKER_IDS`` are ordered around the page, so the 4 detected centers
    must form a simple convex quadrilateral. We check the turn taken at each
    vertex: the cross product of consecutive edges, normalised by the edge
    lengths, is the sine of the turn angle and is therefore scale- and
    dpi-independent. All four turns must go the same way (convex) and none may be
    close to zero (three collinear points).

    A healthy scan -- including one with strong perspective -- measures ~0.999 on
    every vertex, so ``layout.MIN_CORNER_QUAD_SIN`` is deliberately permissive and
    only fires on genuine degeneracy.
    """
    points = np.asarray(src_points, dtype=np.float64)
    sines = []
    for index in range(4):
        first = points[(index + 1) % 4] - points[index]
        second = points[(index + 2) % 4] - points[(index + 1) % 4]
        first_len = float(np.linalg.norm(first))
        second_len = float(np.linalg.norm(second))
        if first_len == 0.0 or second_len == 0.0:
            raise DegeneratePageGeometryError(
                "Deux marqueurs de coin partagent le meme centre: geometrie de page "
                "inexploitable."
            )
        cross = float(first[0] * second[1] - first[1] * second[0])
        sines.append(cross / (first_len * second_len))

    if min(abs(sine) for sine in sines) < layout.MIN_CORNER_QUAD_SIN:
        raise DegeneratePageGeometryError(
            "Marqueurs de coin quasi alignes: l'homographie de page serait degeneree "
            f"(sinus min {min(abs(s) for s in sines):.4f} < "
            f"{layout.MIN_CORNER_QUAD_SIN}). Page pliee ou angle de prise de vue trop "
            "rasant."
        )

    if not (all(sine > 0 for sine in sines) or all(sine < 0 for sine in sines)):
        raise DegeneratePageGeometryError(
            "Les marqueurs de coin ne forment pas un quadrilatere convexe: "
            "l'assignation des coins est incoherente (marqueur parasite ?)."
        )


def warp_page(image: np.ndarray, homography: np.ndarray, width_px: int, height_px: int) -> np.ndarray:
    """Warp ``image`` using ``homography`` into a canonical deskewed page raster."""
    return cv2.warpPerspective(image, homography, (width_px, height_px))


def extract_scan_frames(warped_page: np.ndarray, dpi: int, output_dir: str | Path) -> list[dict]:
    """Crop each deterministic frame zone from the deskewed page and save them as
    ``scan_frame_0001.tiff``, ``scan_frame_0002.tiff``, ... into ``output_dir``.

    Writing goes through ``color_pipeline.export_frame_tiff16``: the previous
    ``cv2.imwrite`` on a ``.png`` collapsed the page to 8 bits, which no later
    gamut expansion can undo (story 5.0, EPIC5-ARB-2).

    Returns one dict per frame, as produced by ``export_frame_tiff16``:
    ``{"path", "source_bit_depth", "output_bit_depth", "output_format"}``. The
    return type is deliberately no longer ``list[Path]``: every depth and format
    value written downstream must come from what the export actually did, never
    from a constant restated next to the call site (finding closed in the 5.5
    review). The input signature is unchanged.

    Raises ScanFrameExtractionError if a crop is empty, if the crop is not a
    shape the TIFF16 export accepts, or if writing a frame to disk fails, so the
    CLI never reports success with missing or empty output files.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for stale_frame in output_dir.glob(SCAN_FRAME_GLOB):
        # `is_file()` d'abord: un sous-dossier nomme `scan_frame_xxx.png` ferait
        # lever un `IsADirectoryError` nu a `unlink()`.
        if stale_frame.is_file() and stale_frame.suffix.lower() in SCAN_FRAME_STALE_SUFFIXES:
            stale_frame.unlink()

    exported_frames = []
    for index, zone in enumerate(layout.FRAME_ZONES_MM, start=1):
        x_px, y_px = layout.mm_to_px(zone["x"], zone["y"], dpi)
        w_px, _ = layout.mm_to_px(zone["width"], 0, dpi)
        _, h_px = layout.mm_to_px(0, zone["height"], dpi)
        crop = warped_page[y_px : y_px + h_px, x_px : x_px + w_px]
        if crop.size == 0:
            raise ScanFrameExtractionError(
                f"Zone de frame '{zone['name']}' vide apres decoupe: verifiez le dpi et le deskew."
            )
        frame_path = output_dir / f"scan_frame_{index:04d}{SCAN_FRAME_EXTENSION}"
        try:
            exported = color_pipeline.export_frame_tiff16(crop, frame_path)
        except (ValueError, RuntimeError) as exc:
            # `validate_bgr_input` refuses a 2- or 5-channel array explicitly
            # rather than converting it silently; surfacing it as the CLI's own
            # error class keeps that refusal actionable instead of a bare
            # traceback.
            raise ScanFrameExtractionError(
                f"Echec d'ecriture de la frame rescannee '{zone['name']}' "
                f"({frame_path}): {exc}"
            ) from exc
        if not frame_path.is_file():
            raise ScanFrameExtractionError(
                f"Echec d'ecriture de la frame rescannee: {frame_path}"
            )
        exported_frames.append(exported)
    return exported_frames
