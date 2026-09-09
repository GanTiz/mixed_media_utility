"""Color/image pipeline contract for the scan reconstruction path (story 5.5).

Two pipelines are documented here, matching ARCHITECTURE_DETAILED.md section 8:

- MVP no-op pipeline (this iteration): geometry only, no active color
  correction. Any readable scan format in, TIFF 16-bit out. Color-space
  information is carried in the *manifest only*: cv2.imwrite writes no ICC
  profile and no colorimetric TIFF tag, so the file itself is untagged (this
  was verified, and the earlier "carried through" wording was wrong).

Channel order: arrays are BGR, as produced by cv2.imread and by the geometric
deskew/crop pipeline. Passing an RGB array (e.g. straight from PIL) silently
swaps red and blue -- validate_bgr_input() cannot detect it, so callers must
convert before calling.
- Post-MVP pipeline (reserved, not implemented): patch-based 3x3 matrix +
  per-channel curves (or a small 3D LUT), gated behind an explicit
  calibration profile.

This module intentionally does not implement the post-MVP correction: it
only fixes the manifest fields that must exist now so the future correction
is not blocked later, plus the MVP no-op export and its explicit failure
mode when a (premature) calibration profile is supplied but invalid.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import cv2
import numpy as np

# Manifest fields that must be persisted from the MVP onward so the future
# color-correction story is not blocked by missing data later.
#
# `target_colorspace` is deliberately split into the 3 independent fields
# ffmpeg/ffprobe actually track (confirmed empirically in story 6.3: MOV/
# ProRes only reports a usable `color_space` when color_primaries, color_trc
# AND colorspace/matrix are all set together). Storing a single flat
# "colorspace" string in the manifest would force a lossy re-derivation of
# the other two at `encode` time; keeping all 3 avoids a field rename later.
COLOR_MANIFEST_FIELDS = (
    "target_color_primaries",  # e.g. "bt709" — declared target, not measured
    "target_color_trc",        # e.g. "bt709" transfer characteristics
    "target_colorspace",       # e.g. "bt709" matrix/colorspace tag
    "scan_input_format",       # original scan file format/extension as received
    "output_bit_depth",        # 16 for the MVP TIFF export
    "output_format",           # "tiff"
    "patch_preset_id",         # versioned patch set reference for future correction
    "color_calibration_status",  # one of CALIBRATION_STATUS_VALUES
    "source_bit_depth",        # 8 or 16: an 8-bit scan upscaled to 16 bits only
                               # populates 256 of 65536 levels, and the future
                               # correction must be able to tell the difference
)

from mixed_media_utility.constants import OUTPUT_BIT_DEPTH as MVP_OUTPUT_BIT_DEPTH
MVP_OUTPUT_FORMAT = "tiff"
NOT_APPLIED_STATUS = "not_applied"

# Closed set of allowed values for `color_calibration_status`, to keep the
# manifest field from becoming an ambiguous free-form string.
CALIBRATION_STATUS_VALUES = ("not_applied", "applied", "failed")

# Extensions cv2 maps to a real 16-bit TIFF encoder. Any other extension makes
# cv2.imwrite silently pick another encoder and fall back to 8 bits while still
# returning True, so the extension must be checked before writing.
TIFF_EXTENSIONS = (".tif", ".tiff")


class ColorCalibrationUnavailable(RuntimeError):
    """Raised when a caller requests active color calibration but no valid
    profile is available. The MVP never silently falls back to a partial or
    implicit correction: callers must handle this explicitly (typically by
    running the no-op pipeline instead)."""


def mvp_color_manifest_fragment(
    *,
    target_color_primaries: str,
    target_color_trc: str,
    target_colorspace: str,
    scan_input_format: str,
    patch_preset_id: str,
    source_bit_depth: int,
    color_calibration_status: str = NOT_APPLIED_STATUS,
) -> dict:
    """Return the manifest fragment for the MVP no-op color contract.

    Every value is validated here: this fragment is the contract other stories
    read, so an empty or None field would only surface much later (at `encode`
    time, as a literal `-color_trc null` passed to ffmpeg).
    """
    for name, value in (
        ("target_color_primaries", target_color_primaries),
        ("target_color_trc", target_color_trc),
        ("target_colorspace", target_colorspace),
        ("scan_input_format", scan_input_format),
        ("patch_preset_id", patch_preset_id),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Champ couleur '{name}' invalide (chaine non vide attendue): {value!r}")
    if source_bit_depth not in (8, 16):
        raise ValueError(f"source_bit_depth doit valoir 8 ou 16, recu: {source_bit_depth!r}")
    validate_calibration_status(color_calibration_status)
    return {
        "target_color_primaries": target_color_primaries,
        "target_color_trc": target_color_trc,
        "target_colorspace": target_colorspace,
        "scan_input_format": scan_input_format,
        "output_bit_depth": MVP_OUTPUT_BIT_DEPTH,
        "output_format": MVP_OUTPUT_FORMAT,
        "patch_preset_id": patch_preset_id,
        "color_calibration_status": color_calibration_status,
        "source_bit_depth": source_bit_depth,
    }


def validate_calibration_status(status: str) -> str:
    """Enforce the closed set of calibration statuses.

    The set was declared but never applied, so nothing stopped another writer
    from putting an arbitrary string in the manifest.
    """
    if status not in CALIBRATION_STATUS_VALUES:
        raise ValueError(
            f"color_calibration_status invalide: {status!r}. "
            f"Valeurs autorisees: {list(CALIBRATION_STATUS_VALUES)}."
        )
    return status


APPLIED_STATUS = "applied"
FAILED_STATUS = "failed"


def derive_lot_calibration_status(*, calibration_page_present: bool,
                                  lot_correction_available: bool,
                                  correctable_page_count: int,
                                  corrected_page_count: int,
                                  correction_requested: bool = True) -> str:
    """Le statut de calibration **du lot**, derive de ce qui a reellement ete corrige.

    Story 5.19, AC 4. La regle du depot ne bouge pas -- « ce qui n'a pas ete corrige est
    declare non corrige » -- et cette fonction est l'endroit unique ou elle se decide,
    pour que les trois valeurs du contrat 5.5 restent fermees et qu'aucun appelant ne
    pose un litteral.

    Les quatre cas, et pourquoi chacun rend ce qu'il rend:

    * **aucune page de calibration au scan** -> ``not_applied``. Rien n'a ete tente, donc
      rien n'a echoue: c'est le chemin non corrige, qui reste licite (`EPIC5-ARB-57` --
      refuser le lot ferait perdre les autres feuilles pour une seule qui manque);
    * **page de calibration presente mais illisible** -> ``failed``. Une correction a ete
      tentee a l'echelle du lot et n'a pas abouti, ce qui n'est pas la meme chose que ne
      pas l'avoir tentee: le distinguer est ce qui dit a l'operateur qu'un rescan de la
      page de calibration recupererait la couleur du lot;
    * **correction disponible, mais aucune planche corrigee** -> ``failed``. Toutes les
      planches ont echoue (mesures implausibles, jeu sous-determine, pastilles
      introuvables): declarer ``applied`` la ou aucun pixel n'a bouge serait le faux
      succes du risque R12 applique a la couleur;
    * **correction disponible et au moins une planche corrigee** -> ``applied``. Le champ
      est de niveau lot; la verite **par page** vit dans `page_calibration_results`, ou
      chaque planche porte son propre statut et son propre motif.

    ``correctable_page_count`` a zero -- un lot qui ne porte que sa page de calibration
    -- rend ``not_applied`` et non ``failed``: aucune frame n'existait a corriger, donc
    aucune correction n'a echoue.

    **Cette branche a deux chemins d'acces, un seul est ecrivable, et le second est
    atteint en production.** La premiere redaction de ce paragraphe affirmait un domaine
    « vide, et c'est mesure »: la mesure ne portait que sur le premier chemin et la
    conclusion a ete generalisee a tort (finding ``F2`` de la revue de la passe de
    correction). Les deux chemins:

    * **un lot ne portant que sa page de calibration** -- non ecrivable de bout en bout: la
      passe ajuste bien la correction sur ses 130 pastilles, ecrit zero frame, puis le
      manifest refuse sur un cardinal attendu de ``-4``. Ce refus n'est pas nomme, ce qui
      est un defaut distinct, consigne au ``deferred-work.md`` plutot que corrige ici --
      elargir le perimetre de 5.19 a la pagination serait ce que ``CLAUDE.md`` interdit ;
    * **une page de calibration intacte et toutes les planches d'images en echec de
      geometrie** -- ``page_calibrations`` est vide, puisqu'une planche en echec ne passe
      jamais par ``calibrate_page``, et la correction du lot est pourtant disponible. Ce
      chemin est banal (une pile de feuilles mal posee) et il sort en **code 0 avec son
      manifest**: mesure, pas suppose.

    La valeur rendue reste ``not_applied`` dans les deux cas, et pour la meme raison:
    aucun pixel n'a bouge. Ce que la branche n'est **pas**, c'est du code mort -- la
    supprimer ferait tomber le second chemin dans ``corrected_page_count <= 0`` donc dans
    ``failed``, qui dirait qu'une correction a echoue la ou il n'y avait aucune frame a
    corriger.

    **Cinquieme cas, ajoute par ``EPIC5-ARB-78`` (2026-08-13): l'operateur a demande
    ``--cc off``** -> ``not_applied``. Ce choix est teste avant les cas d'absence
    (pas de page de calibration / aucune frame corrigeable), mais apres l'echec de calcul reel.
    Le distinguer se fait par un champ separe (``not_applied_reason`` sur l'entree de
    page, ``color_calibration.NOT_APPLIED_OPERATOR_OPT_OUT``) et **jamais** par une
    quatrieme valeur de statut: le vocabulaire de ``color_calibration_status`` est ferme
    par le contrat 5.5 et lu par ``encode``, qui n'a pas a apprendre un mot de plus pour
    un fait qu'il traite deja -- ces frames-la ne sont pas corrigees.

    Sans ce cas explicite, la valeur rendue serait la bonne par accident: aucune planche
    ne serait calibree, donc ``correctable_page_count`` vaudrait zero, donc la branche
    « aucune frame a corriger » repondrait ``not_applied`` en disant une chose fausse --
    il y avait des planches a corriger, et l'operateur a dit non.

    **Sixieme cas, corrige a la deuxieme passe de revue d'``EPIC5-ARB-78``
    (2026-08-14): un echec de calcul reel passe desormais AVANT le choix de
    l'operateur dans l'ordre de decision.** Avant ce correctif, ``--cc off`` sur un lot
    dont la page de calibration est illisible ou degeneree (``lot_correction_available
    =False``) rendait ``not_applied`` au niveau du lot -- masquant un vrai ``failed``.
    Chaque entree de **page** portait deja le vrai motif (la page de calibration
    elle-meme se declare ``failed`` avec son motif, voir
    ``color_calibration.calibration_page_result``); seul le resume de **lot** etait
    plus silencieux qu'il ne devrait, parce que la fonction testait le choix de
    l'operateur avant l'echec de calcul. Un operateur qui relirait uniquement le champ
    de lot -- exactement ce que ce champ existe pour resumer -- verrait un choix
    delibere la ou il y avait une panne.
    """
    # **L'echec de calcul reel se teste en premier**, avant meme le choix de
    # l'operateur: une page de calibration presente mais dont la correction n'a pas pu
    # etre ajustee (illisible, degeneree, jeu sous-determine) est un fait qui s'est
    # produit independamment de ce que l'operateur a demande de faire du resultat.
    # `--cc off` ne peut porter que sur une correction qui existe; il ne peut pas
    # transformer une panne en absence de tentative.
    if calibration_page_present and not lot_correction_available:
        return FAILED_STATUS
    if not correction_requested:
        return NOT_APPLIED_STATUS
    if not calibration_page_present:
        return NOT_APPLIED_STATUS
    if correctable_page_count <= 0:
        return NOT_APPLIED_STATUS
    if corrected_page_count <= 0:
        # **La garde du cardinal des planches refusees a ete retiree ici** (story 5.23,
        # AC 13, `EPIC5-ARB-88`), en meme temps que le parametre qui la nourrissait.
        #
        # Elle datait de 5.22 (`EPIC5-ARB-80` decision 5), quand une planche divergente
        # etait livree en brut **sans qu'un echec ait eu lieu** et qu'un lot entierement
        # divergent devait sortir `not_applied` plutot que `failed`. L'AC 3 de la story
        # 5.23 a supprime ce regime: la correction s'applique quel que soit l'ecart, et
        # `calibrate_page` n'a plus aucune sortie sans profil **et** sans motif d'echec.
        # Le cardinal valait donc invariablement zero, la comparaison etait invariablement
        # fausse, et la branche `not_applied` invariablement morte -- une garde qu'aucune
        # entree ne franchit, presentee comme une garde, est l'un des quatre pieges
        # nommes du 2026-08-12.
        #
        # Arriver ici veut donc dire ce que la premiere redaction disait: au moins une
        # planche etait corrigeable, aucune ne l'a ete, et chacune porte son motif
        # d'echec.
        return FAILED_STATUS
    return APPLIED_STATUS


def validate_bgr_input(image: np.ndarray) -> np.ndarray:
    """Reject inputs that cv2.imwrite would mishandle or crash on.

    Returns the array normalised to native byte order. Without this, an empty
    crop (degenerate deskew), a 2- or 5-channel array, a big-endian uint16 scan
    (`>u2`, produced by scanners writing TIFF in `MM` byte order) or a plain
    None from a failed upstream read all surfaced as raw OpenCV assertions or
    AttributeError several frames away from the cause.
    """
    if not isinstance(image, np.ndarray):
        raise TypeError(f"Image attendue de type numpy.ndarray, recu: {type(image).__name__}")
    if image.size == 0 or min(image.shape[:2]) == 0:
        raise ValueError("Image vide: la decoupe geometrique amont a produit un rectangle degenere.")
    if image.ndim == 3 and image.shape[2] not in (1, 3, 4):
        raise ValueError(
            f"Nombre de canaux non supporte pour l'export TIFF16: {image.shape[2]} "
            "(1, 3 ou 4 attendus, en ordre BGR)."
        )
    if image.ndim not in (2, 3):
        raise ValueError(f"Image de dimension non supportee: {image.ndim}")
    # Byte-order-insensitive dtype check: `>u2` is valid 16-bit data.
    if image.dtype.kind == "u" and image.dtype.itemsize == 2:
        return image.astype(np.uint16, copy=False)
    if image.dtype == np.uint8:
        return image
    raise ValueError(f"Type d'image non supporte pour l'export TIFF16: {image.dtype}")


def source_bit_depth_of(image) -> int:
    """Profondeur du **scan source** deduite du type du tableau, chez son proprietaire.

    Finding `m4` de la revue de 5.19: la regle etait reecrite dans
    `scan_output_frames._corrected_frame`, parce que la correction requantifie en 16 bits
    et que l'export ne peut plus deduire apres coup. Les deux redactions coincidaient, mais
    la divergence de la premiere evolution aurait ete **silencieuse** et aurait porte sur
    un champ de manifest -- exactement l'argument que ce module applique dix lignes plus
    loin au statut `not_applied`. La regle vit donc ici et se lit de la.
    """
    return 8 if image.dtype == np.uint8 else 16


def export_frame_tiff16(image: np.ndarray, output_path: str) -> dict:
    """Export ``image`` (BGR, as produced by the geometric deskew/crop pipeline)
    as a 16-bit TIFF, with no active color correction (MVP no-op contract).

    8-bit input is scaled to the 16-bit range; input already at 16 bits per
    channel is written unchanged.

    Returns a dict with the path actually written and the *source* bit depth, so
    the caller can feed mvp_color_manifest_fragment() with what really happened
    rather than a hardcoded assumption.

    Raises ValueError if ``output_path`` is not a TIFF: cv2.imwrite picks its
    encoder from the extension, and on e.g. ".jpg" it silently falls back to
    8 bits *and still returns True* -- so the function would report success
    while writing a lossy 8-bit file under a name promising 16-bit TIFF.
    """
    image = validate_bgr_input(image)
    if not str(output_path).lower().endswith(TIFF_EXTENSIONS):
        raise ValueError(
            f"Extension de sortie invalide pour un TIFF 16 bits: {output_path}. "
            f"Attendu l'une de {list(TIFF_EXTENSIONS)}."
        )

    source_bit_depth = source_bit_depth_of(image)
    if image.dtype == np.uint8:
        image16 = (image.astype(np.uint16)) * 257  # 0..255 -> 0..65535
    else:
        image16 = image

    write_ok = cv2.imwrite(str(output_path), image16)
    if not write_ok:
        raise RuntimeError(f"Echec d'ecriture du TIFF 16 bits: {output_path}")
    return {
        "path": str(output_path),
        "source_bit_depth": source_bit_depth,
        "output_bit_depth": MVP_OUTPUT_BIT_DEPTH,
        "output_format": MVP_OUTPUT_FORMAT,
    }


@runtime_checkable
class CalibrationProfile(Protocol):
    """Ce qu'une correction couleur active doit offrir pour etre applicable.

    Protocole **structurel** et non classe de base: le profil concret vit dans
    `color_calibration` (story 5.4b), et ce module reste le contrat de normalisation
    de sortie. Un protocole evite de faire dependre le contrat de son
    implementation tout en gardant la verification possible a l'execution.
    """

    correction_id: str

    def apply_linear(self, linear):  # pragma: no cover - protocole
        ...


def apply_active_calibration(image, profile: CalibrationProfile | None):
    """Appliquer une correction couleur active a une image BGR.

    **Remplace `request_active_calibration`, qui levait inconditionnellement.** La
    revue de 5.5 l'avait qualifie sans detour: « un dev de la story 5.4 devrait
    supprimer la fonction et reecrire le contrat: ce n'est pas un hook, c'est une
    exception non branchee ». Le contrat est desormais reel -- un profil, une
    application -- et `ColorCalibrationUnavailable` est conservee pour le **seul** cas
    ou la calibration est reellement indisponible, c'est-a-dire quand aucun profil
    n'est fourni.

    Ce qui n'a pas change, et qui etait la seule chose juste dans l'ancienne version:
    un appelant n'obtient **jamais** une correction partielle silencieuse. Sans profil,
    on leve; avec un profil, on corrige entierement. « Ce qui n'a pas ete corrige est
    declare non corrige. »

    L'entree est validee par `validate_bgr_input`, donc l'ordre des canaux reste celui
    de tout le module: **BGR**.
    """
    from . import color_calibration

    # La valeur de retour est **consommee**, comme en `:175` et dans
    # `scan_ingest.py:404`. La jeter etait un finding majeur de la couche 2 le
    # 2026-08-11: `validate_bgr_input` normalise l'ordre des octets, et `np.dtype(">u2")`
    # -- ce qu'ecrit un scanner en ordre `MM` -- n'est **pas** egal a `np.uint16` sur une
    # machine petit-boutienne. L'echelle etait donc deduite a 255 au lieu de 65535 et le
    # scan saturait a blanc, en silence.
    image = validate_bgr_input(image)
    if profile is None:
        raise ColorCalibrationUnavailable(
            "Aucun profil de correction fourni: rien a appliquer. Une image non "
            "corrigee doit etre declaree non corrigee, jamais corrigee a demi."
        )
    if not hasattr(profile, "apply_linear"):
        raise ColorCalibrationUnavailable(
            f"Le profil fourni n'offre pas `apply_linear`: {type(profile).__name__}. "
            "Voir color_calibration.CorrectionProfile."
        )
    return color_calibration.apply_profile_to_image(image, profile)