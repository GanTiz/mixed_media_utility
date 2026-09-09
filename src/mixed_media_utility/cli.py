#!/usr/bin/env python3
"""CLI minimal pour Mixed Media Utility (squelette).
Usage: mixed-media-util <command> [options]
"""
import argparse
import contextlib
import dataclasses
import hashlib
import json
import logging
import os
import shutil
import signal
import sys
import tempfile
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

import cv2
import numpy as np
from jsonschema.exceptions import ValidationError

from mixed_media_utility import (
    __version__,
    cadence_previz,
    codec_profiles,
    color_calibration,
    color_metrics,
    color_pipeline,
    declaration_de_rush,
    encode as encode_module,
    encode_master,
    extraction,
    ffmpeg_utils,
    gamut_map,
    layout,
    makepdf as makepdf_core,
    page_roles,
    page_templates,
    patch_presets,
    pdf_composition,
    pdf_render,
    previz_common,
    qr_codes,
    relink,
    scan_calibrate,
    scan_crop,
    scan_detect,
    scan_detection,
    scan_ingest,
    scan_output_frames,
    scan_chain,
    scan_previz,
    scan_sorting,
    scan_write,
    source_confirmation,
    video_metadata,
)
from mixed_media_utility.detection import aruco as aruco_detection
from mixed_media_utility.frame_selection import FrameSelectionError
from mixed_media_utility.io import (
    calibration_profile,
    encode_manifest,
    extraction_manifest,
    naming,
    pdf_manifest,
    profile_designation,
    project_layout,
    reconstruction,
    scan_manifest,
)
from mixed_media_utility.io import payload as payload_io
from mixed_media_utility.io.extraction_manifest import (
    ExtractionPersistenceError,
    _atomic_write,
    _load_existing_manifest,
)
from mixed_media_utility.io.manifest import LOT_STATES, load_manifest, validate_lot_state_transition, validate_manifest
from mixed_media_utility.io.naming import NamingError
from mixed_media_utility.io.payload import (
    PayloadBudgetExceeded,
    PayloadValidationError,
    parse_payload,
)
from mixed_media_utility.io.reconstruction import ReconstructionError, reconstruct_project_manifest
from mixed_media_utility.page_payload import NonCanonicalIdentifierError

# Story 2.2 MVP: pas de correction colorimetrique active, seul un espace couleur
# cible no-op est declare (voir ARCHITECTURE_DETAILED.md sections 8 et 11).
MVP_TARGET_COLORSPACE = "rec709"

# `DEFAULT_TARGET_COLORSPACE` a emigre dans `mixed_media_utility.makepdf` avec la
# fonction qui l'ecrit (story 11.7, lot B). Elle y porte son motif d'origine, mot
# pour mot. `MVP_TARGET_COLORSPACE` ci-dessus, lui, reste ici : il est le defaut
# du chemin POC legacy, que cette decision n'a jamais touche.

#: `--cc {on|off}` sur la commande `scan`. `EPIC5-ARB-78`, 2026-08-13.
#:
#: Le nom du drapeau et son vocabulaire vivent **ici**, dans le module qui possede la
#: commande, et non dans `color_calibration`: contrairement a `DIVERGENCE_BYPASS_FLAG`, ce
#: drapeau ne contourne aucune garde et n'est nomme par aucun message de refus de la
#: couche couleur -- il ne fait que decider si le resultat d'un calcul est applique. Ce
#: que la couche couleur possede, elle, est le **motif** ecrit au manifest
#: (`color_calibration.NOT_APPLIED_OPERATOR_OPT_OUT`), qui est du vocabulaire de document.
#:
#: Les deux valeurs sont des constantes plutot que des litteraux repetes: elles
#: apparaissent a quatre endroits (l'option, son defaut, la lecture dans `scan_command`,
#: le message de journal), et c'est exactement le cardinal a partir duquel une faute de
#: frappe passe inapercue de trois cotes sur quatre.
#: **Les valeurs vivent dans `scan_write` depuis la story 11.4b**, lues ici:
#: les messages de journal de la sequence d'ecriture les nomment, et une
#: interface a interdiction d'importer `cli.py` (`EPIC11-ARB-67`). Meme geste
#: que `extraction.CODES_DE_SORTIE` (`EPIC11-ARB-75`): une valeur, un endroit.
CC_FLAG = scan_write.CC_FLAG
CC_ON = scan_write.CC_ON
CC_OFF = scan_write.CC_OFF

#: Nom de l'option par laquelle **l'operateur designe le profil** applique a un scan
#: (story 5.23, AC 12, `EPIC5-ARB-83`). Declaree ici, avec `CC_FLAG` et pour le meme
#: motif: c'est un nom de geste en ligne de commande, pas du vocabulaire de document, et
#: il apparait a plus d'un endroit -- l'option de `scan`, celle de la commande de profil
#: par defaut, leur aide, et l'avertissement qui les cite quand aucun profil n'est
#: designe.
#:
#: **Elle remplace `--charger-profil-de-calibration` de la story 5.22**, et ce n'est pas
#: un renommage de confort: l'ancienne option consignait un profil externe **sous
#: l'identite de chaine derivee du scan**, et refusait le fichier dont le `chain_id`
#: differait. Cette comparaison etait le dernier appariement automatique, celui-la meme
#: que `EPIC5-ARB-83` supprime -- deux scanners aux tags absents rendant le meme
#: `chain_id`, elle acceptait le mauvais profil et refusait le bon. Garder les deux noms
#: cote a cote aurait laisse dans le parseur un second geste pour la meme intention,
#: c'est-a-dire le reste inerte que l'AC 13 vient de retirer ailleurs. `argparse` refuse
#: l'ancien nom bruyamment (`unrecognized arguments`, code de sortie 2), donc aucun
#: script ne continue en silence avec un comportement change; l'option n'a par ailleurs
#: jamais quitte cette branche de developpement.
PROFILE_FLAG = scan_write.PROFILE_FLAG  # valeur au coeur, cf. `CC_FLAG`

#: Nom de la commande **dediee et separee** qui pose le profil par defaut d'un projet
#: (`EPIC5-ARB-83`, decision 2: « jamais un effet de bord d'un scan »). Le nom suit la
#: forme verbe-nom des sous-commandes existantes (`extract-frames`,
#: `apply-calibration`) et transcrit les mots d'Egan (« `mmu set default profile` »),
#: dont l'arbitrage precise qu'ils ne figent pas le nom exact.
SET_DEFAULT_PROFILE_COMMAND = scan_write.SET_DEFAULT_PROFILE_COMMAND  # valeur au coeur

#: Nom de la sous-commande de relink (story 2.8, `EPIC7-ARB-41`). Constante
#: pour la meme raison que `SET_DEFAULT_PROFILE_COMMAND`: un seul litteral
#: greppable pour le sous-parseur, plutot qu'une chaine repetee.
RELINK_COMMAND = 'relink'

#: Nom de la commande d'ecriture depuis un document de detection (story 5.26,
#: question ouverte 1 -- proposition appliquee). Commande de **premier
#: niveau**, modele `relink` et `set-default-profile` (deux precedents de
#: commandes qui operent sur l'etat persiste d'un projet), et non une
#: sous-commande de `scan`: le parseur `scan` exige `--scan` et `--dpi` avant
#: toute sous-commande (refus fige par
#: `test_calibrate_garde_le_refus_d_un_dpi_manquant`), or l'ecriture n'a ni
#: source a ingerer ni dpi a declarer -- les deux vivent dans le document. Un
#: `--scan` requis-mais-ignore serait le « reste inerte » refuse le 2026-08-17.
SCAN_WRITE_COMMAND = 'scan-write'

#: Story 5.23, AC 8quater. Les deux options par lesquelles l'operateur **nomme** ce que
#: `scan calibrate` produit. Elles sont declarees sur la **sous-commande** et non sur
#: `scan`: un `scan --nom ...` qui serait accepte puis ignore serait le reste inerte que
#: l'AC 13 vient de retirer ailleurs dans cette meme story. Elles ne sont declarees
#: qu'une fois -- le defaut d'un sous-parseur ecrase la valeur analysee par son parent
#: quand une option est declaree des deux cotes, defaut mesure le 2026-08-17.
PROFILE_NAME_FLAG = '--nom'
PROFILE_COMMENT_FLAG = '--commentaire'

#: Nom de la sous-commande qui calibre une chaine de scan (`scan ... calibrate`).
#: Constante depuis `EPIC5-ARB-92`, pour la meme raison que `CC_FLAG` et
#: `SET_DEFAULT_PROFILE_COMMAND`: elle apparait desormais a trois endroits -- le
#: sous-parseur, l'invite de bascule et son journal --, et l'invite qui nommerait un
#: geste que le parseur n'accepte pas enverrait l'operateur taper une commande
#: inexistante.
SCAN_CALIBRATE_SUBCOMMAND = scan_calibrate.SCAN_CALIBRATE_SUBCOMMAND

#: Story 5.25. Meme convention que `SCAN_CALIBRATE_SUBCOMMAND` juste au-dessus:
#: sous-commande de `scan`, jamais un drapeau sur le parent -- le motif deja
#: refuse le 2026-08-17 pour `--nom`.
SCAN_DETECT_SUBCOMMAND = scan_detect.SCAN_DETECT_SUBCOMMAND


# `_apply_default_target_colorspace` a emigre avec le corps qui l'appelle : elle
# est `makepdf.appliquer_l_espace_couleur_par_defaut`, et la constante qu'elle
# ecrit l'a suivie (`makepdf.DEFAULT_TARGET_COLORSPACE`). Ses deux seuls
# appelants etaient `makepdf` et sa page de calibration ; la laisser ici aurait
# oblige la TUI a importer `cli` pour obtenir le meme defaut, ce qui lui est
# interdit.


def extract_frames(args):
    print(f"[TODO] Extraire frames depuis: {args.input} → {args.outdir}")

def apply_calibration(args):
    print(f"[TODO] Appliquer calibration depuis: {args.profile} sur {args.scanned}")

class PocInputError(RuntimeError):
    """Raised for user-facing input/prerequisite errors during the POC run."""


# `outputs` n'est plus une chaine litterale ici: la constante d'arborescence est
# nommee une seule fois dans le depot (story 6.1, AC 12), comme
# `SCAN_FRAMES_DIRNAME` l'exige deja pour sa voisine.
#
# **Story 11.14, meme geste pour les frames extraites** (`EPIC11-ARB-220`) : le
# dossier s'appelle `extract-frames/`, « en symetrie avec la commande `extract`
# qui les produit », et le nom d'avant (`LEGACY_FRAMES_DIRNAME`) est desormais
# RECONNU mais **jamais ecrit** -- patron `LEGACY_SOURCES_DIRNAME`, deja en
# place juste a cote. Le litteral `"frames"` qui vivait ici etait le dernier
# endroit de `cli.py` a composer ce nom a la main.
#
# `inputs` reste litteral et reste ecrit par ce chemin POC, alors qu'il est
# `LEGACY_SOURCES_DIRNAME` par ailleurs : ce n'est pas un objet du vocabulaire
# d'Egan et la story 11.14 ne le tranche pas. L'ecart est nomme plutot que tu.
PROJECT_SUBDIRS = (
    "inputs",
    project_layout.EXTRACT_FRAMES_DIRNAME,
    # `EPIC11-ARB-225` : le dossier des planches, par la CONSTANTE comme ses
    # deux voisins. Le litteral qui vivait ici etait le seul des trois a ne pas
    # suivre le coeur, donc le seul que le renommage aurait laisse en arriere.
    project_layout.PLANCHES_DIRNAME,
    "detection",
    project_layout.OUTPUTS_DIRNAME,
    "logs",
)


def _create_project_layout(project_dir: Path) -> None:
    for sub in PROJECT_SUBDIRS:
        (project_dir / sub).mkdir(parents=True, exist_ok=True)
    # Additive: also ensure the v2 base arborescence (story 2.5) alongside the
    # legacy POC subdirs above, without changing their existing behavior.
    project_layout.ensure_project_layout(project_dir)


def _configure_poc_logger(project_dir: Path) -> logging.Logger:
    logger = logging.getLogger(f"mixed_media_utility.poc_run.{project_dir.resolve()}")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    log_path = project_dir / "logs" / "poc_run.log"
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console_handler)

    return logger


def _close_logger_handlers(logger: logging.Logger) -> None:
    """Fermer proprement tous les handlers du logger."""
    for handler in logger.handlers[:]:
        handler.flush()
        handler.close()
        logger.removeHandler(handler)


def _handle_poc_failure(logger: logging.Logger, exc: Exception, exit_code: int) -> int:
    message = str(exc)
    logger.error(message)
    print(f"Erreur: {message}", file=sys.stderr)
    return exit_code


# Aspect ratio forced by the printable sheet's 16:9 frame zones (see layout.py).
FRAME_ZONE_ASPECT_RATIO = 16 / 9
# Relative tolerance applied when comparing a source video's ratio to 16:9.
FRAME_ZONE_ASPECT_TOLERANCE = 0.02


def _probe_video_metadata(video_path: Path) -> tuple[float, float, float]:
    """Return (width, height, fps) read from the source video via OpenCV.

    fps defaults to 0.0 when the backend cannot report it; callers treat 0.0 as
    "unknown" rather than failing, since fps_source is informative metadata
    and not required for the POC roundtrip to succeed (story 2.2, AC3).
    """
    capture = cv2.VideoCapture(str(video_path))
    try:
        width = capture.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = capture.get(cv2.CAP_PROP_FRAME_HEIGHT)
        fps = capture.get(cv2.CAP_PROP_FPS)
    finally:
        capture.release()
    return width, height, fps


def _validate_video_ratio(video_path: Path) -> tuple[float, float, float]:
    """Raise PocInputError if the source video resolution is not close to 16:9.

    The MVP patch sheet only supports 16:9 frame zones (e.g. 1920x1080), so an
    incompatible source ratio must fail early with an actionable message.
    Returns the full (width, height, fps) probe result so callers never have to
    reopen the video for the fps they already paid to read.
    """
    width, height, fps = _probe_video_metadata(video_path)

    if not width or not height:
        raise PocInputError(
            f"Impossible de lire la resolution de la video source: {video_path}"
        )

    ratio = width / height
    tolerance = FRAME_ZONE_ASPECT_RATIO * FRAME_ZONE_ASPECT_TOLERANCE
    if abs(ratio - FRAME_ZONE_ASPECT_RATIO) > tolerance:
        raise PocInputError(
            f"Ratio video source incompatible avec le slice 16:9 (detecte {width:.0f}x{height:.0f}, "
            f"ratio {ratio:.3f}). Ce POC attend une source proche de 16:9 (ex: 1920x1080)."
        )

    return width, height, fps


def _select_sheet_frames(frame_paths: list[Path]) -> list[Path]:
    """Return the first 2 extracted frames used for the patch sheet.

    Raises PocInputError if fewer than 2 usable frames were extracted.
    """
    required = len(layout.FRAME_ZONES_MM)
    if len(frame_paths) < required:
        raise PocInputError(
            f"Frames utilisables insuffisantes: {len(frame_paths)} extraite(s), {required} requises "
            "pour la planche. Ajustez --fps ou fournissez une video plus longue."
        )
    return frame_paths[:required]


def _build_sheet_manifest(
    project_dir: Path,
    args,
    video_copy: Path,
    sheet_frames: list[Path],
    source_width: float,
    source_height: float,
    source_fps: float,
) -> dict:
    created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "id": project_dir.resolve().name or "poc-project",
        "created": created,
        # La CLE `frames` NE BOUGE PAS (`EPIC11-ARB-221`: renommer une cle
        # casserait la lecture des projets deja sur disque, et aucune commande
        # de conversion n'existe). Seule la VALEUR suit le dossier reellement
        # ecrit par `_create_project_layout`.
        "inputs": {"raw": "inputs/",
                   "frames": f"{project_layout.EXTRACT_FRAMES_DIRNAME}/"},
        "calibration": "calib/camera_params.json",
        "artifacts": "outputs/",
        "meta": {
            "dpi_print": args.dpi,
            "fps_extract": args.fps,
            "video_source": f"inputs/{video_copy.name}",
            "sheet_frames": [
                frame_path.relative_to(project_dir).as_posix() for frame_path in sheet_frames
            ],
            # Story 2.2: metadonnees techniques et etat de lot, forme transitoire
            # sous `meta` tant que le POC ecrit un manifest legacy (voir
            # io/manifest.py CRITICAL_TECHNICAL_FIELDS / LOT_STATES).
            "video": {
                "resolution_source": {"width": int(source_width), "height": int(source_height)},
                "fps_source": source_fps or None,
                "fps_target": args.fps,
                "codec_target": None,
            },
            "color": {"target_colorspace": MVP_TARGET_COLORSPACE},
            "lot": {"state": "pdf", "expected_frame_count": len(sheet_frames)},
        },
    }


def poc_build_sheet(args):
    """Extract frames from a source video and compose the printable patch sheet PDF."""
    project_dir = Path(args.project)
    _create_project_layout(project_dir)
    logger = _configure_poc_logger(project_dir)

    try:
        logger.info("Demarrage de poc build-sheet pour le projet %s", project_dir)
        video_path = Path(args.video)

        if not video_path.is_file():
            raise PocInputError(f"Fichier video introuvable: {video_path}")
        if args.fps <= 0:
            raise PocInputError(f"Parametre --fps invalide: {args.fps}. Attendu un nombre strictement positif.")
        if args.dpi <= 0:
            raise PocInputError(f"Parametre --dpi invalide: {args.dpi}. Attendu un entier strictement positif.")

        source_width, source_height, source_fps = _validate_video_ratio(video_path)

        ffmpeg_utils.ensure_ffmpeg_available()

        inputs_dir = project_dir / "inputs"
        video_copy = inputs_dir / video_path.name
        shutil.copy2(video_path, video_copy)

        frames_dir = project_dir / project_layout.EXTRACT_FRAMES_DIRNAME
        frame_paths = ffmpeg_utils.extract_frames(video_copy, frames_dir, args.fps)
        logger.info("%d frames extraites dans %s", len(frame_paths), frames_dir)

        sheet_frames = _select_sheet_frames(frame_paths)
        logger.info("Frames retenues pour la planche: %s", [p.name for p in sheet_frames])

        # **Le POC continue d'ecrire ou il ecrivait** (`EPIC11-ARB-225` est
        # muet sur ce site ; question consignee en dette le 2026-09-06). Il
        # passe par `LEGACY_PATCHES_DIRNAME` plutot que par un litteral pour
        # que l'INTENTION se lise : ce n'est pas un dossier oublie par le
        # renommage, c'est le nom d'avant, employe sciemment sur un chemin que
        # la POC est seule a emprunter.
        patch_sheet_path = (
            project_dir / project_layout.LEGACY_PATCHES_DIRNAME
            / "patch_sheet.pdf")
        layout.generate_patch_sheet_pdf(patch_sheet_path, frame_paths=sheet_frames)
        logger.info("Gabarit PDF genere avec frames composees: %s", patch_sheet_path)

        manifest_path = project_dir / "project.json"
        manifest = _build_sheet_manifest(
            project_dir, args, video_copy, sheet_frames, source_width, source_height, source_fps
        )
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        validate_manifest(manifest_path)
        logger.info("Manifest ecrit et valide: %s", manifest_path)

        print(f"poc build-sheet termine avec succes. Planche: {patch_sheet_path}")
        return 0

    except PocInputError as exc:
        return _handle_poc_failure(logger, exc, 1)
    except ffmpeg_utils.FfmpegNotFoundError as exc:
        return _handle_poc_failure(logger, exc, 2)
    except ffmpeg_utils.FrameExtractionError as exc:
        return _handle_poc_failure(logger, exc, 1)
    except ValidationError as exc:
        return _handle_poc_failure(logger, exc, 1)
    finally:
        _close_logger_handlers(logger)


UNKNOWN_SCAN_FORMAT = "unknown"


def _scan_input_format(scan_copy: Path) -> str:
    """Format du scan *declare par le nom du fichier*, jamais une chaine vide.

    Ce n'est deliberement pas le format decode: `cv2.imread` sniffe le contenu
    et lit sans se soucier de l'extension, si bien qu'un JPEG nomme `.png`
    ressort ici comme `png`. Le champ dit ce que le fichier pretend etre, ce qui
    est l'information utile pour retrouver l'origine d'un lot. La nouvelle
    chaine de scan (story 5.1) mesurera le format sur la donnee elle-meme; le
    POC ne le fait pas et ne doit pas laisser croire le contraire.

    Un scan sans extension n'a aucun format declare: `unknown` le dit, la
    chaine vide le tairait — et `color_pipeline.mvp_color_manifest_fragment`
    refuse justement la chaine vide pour ce meme champ (`color_pipeline.py:99`).
    """
    return scan_copy.suffix.lower().lstrip(".") or UNKNOWN_SCAN_FORMAT


def _scan_color_meta(scan_frames: list[dict], scan_copy: Path) -> dict:
    """Build the `meta.color` depth fragment of the legacy POC manifest.

    Every value comes from what `extract_scan_frames` reported actually writing,
    never from a constant restated here: that divergence between the manifest
    and the artefact on disk is the defect the 5.5 review closed by making
    `export_frame_tiff16` return a dict.

    `mvp_color_manifest_fragment` is deliberately *not* used: it requires
    `target_color_primaries`, `target_color_trc` and `patch_preset_id`, which
    the POC does not own -- inventing them would add a lie to the manifest
    instead of removing one. The POC writes a legacy manifest whose `meta` is a
    free object, so no schema change is involved.
    """
    def unique(field: str) -> int | str:
        values = {frame[field] for frame in scan_frames}
        if len(values) != 1:
            raise PocInputError(
                f"Frames rescanees incoherentes sur '{field}': {sorted(values)}. "
                "Toutes proviennent de la meme page redressee et doivent partager "
                "la meme profondeur et le meme format."
            )
        return values.pop()

    return {
        "scan_input_format": _scan_input_format(scan_copy),
        # 8 ou 16: un scan 8 bits monte en 16 bits ne peuple que 256 des 65536
        # niveaux. Seul ce champ permet, apres coup, de distinguer un vrai
        # 16 bits d'un 16 bits gonfle -- distinction critique pour l'expansion
        # de gamut, qui amplifie le pas de quantification par 1/k.
        "source_bit_depth": unique("source_bit_depth"),
        "output_bit_depth": unique("output_bit_depth"),
        "output_format": unique("output_format"),
    }


def poc_process_scan(args):
    """Detect the patch sheet in a scan, deskew it and re-extract the 2 scanned frames."""
    project_dir = Path(args.project)
    _create_project_layout(project_dir)
    logger = _configure_poc_logger(project_dir)

    try:
        logger.info("Demarrage de poc process-scan pour le projet %s", project_dir)
        scan_path = Path(args.scan)

        if not scan_path.is_file():
            raise PocInputError(f"Fichier scan introuvable: {scan_path}")
        if args.dpi <= 0:
            raise PocInputError(f"Parametre --dpi invalide: {args.dpi}. Attendu un entier strictement positif.")

        manifest_path = project_dir / "project.json"
        if not manifest_path.is_file():
            raise PocInputError(
                f"project.json introuvable dans {project_dir}. Executez d'abord 'poc build-sheet'."
            )

        inputs_dir = project_dir / "inputs"
        scan_copy = inputs_dir / scan_path.name
        shutil.copy2(scan_path, scan_copy)

        # IMREAD_UNCHANGED, et non le IMREAD_COLOR implicite d'un `imread` nu:
        # sans ce flag un TIFF 16 bits est ramene a 8 bits des l'ingestion
        # (mesure: 0,4000,8000 -> 0,16,31) et l'alpha est perdu, silencieusement.
        # Meme motif que `pdf_render.load_frame_image_for_print`. Corollaire
        # constate et non compense: contrairement a `imread` nu, ce flag
        # n'applique pas l'orientation EXIF; la geometrie de page y survit, les
        # coins etant apparies par ID de marqueur, mais les centres ecrits dans
        # `detection/markers.json` restent exprimes dans le repere du fichier.
        scan_image = cv2.imread(str(scan_copy), cv2.IMREAD_UNCHANGED)
        if scan_image is None:
            raise PocInputError(f"Impossible de lire l'image scan: {scan_copy}")

        # `dpi=args.dpi`, la meme valeur que celle qui sert ensuite a
        # l'homographie: c'est elle qui donne la taille du module imprime, donc
        # le dimensionnement du seuillage adaptatif (voir `detection/aruco.py`).
        corners, ids = aruco_detection.detect_markers(scan_image, dpi=args.dpi)
        scan_relative_path = scan_copy.relative_to(project_dir).as_posix()
        markers_doc = aruco_detection.build_markers_document(scan_relative_path, corners, ids)

        markers_path = project_dir / "detection" / "markers.json"
        markers_path.write_text(json.dumps(markers_doc, indent=2), encoding="utf-8")
        logger.info("markers.json ecrit: %s", markers_path)

        homography, width_px, height_px = aruco_detection.compute_page_homography(markers_doc, args.dpi)
        warped_page = aruco_detection.warp_page(scan_image, homography, width_px, height_px)

        outputs_dir = project_layout.outputs_dir(project_dir)
        scan_frames = aruco_detection.extract_scan_frames(warped_page, args.dpi, outputs_dir)
        scan_color_meta = _scan_color_meta(scan_frames, scan_copy)
        logger.info(
            "%d frames rescanees extraites vers %s (%s %d bits, source %d bits)",
            len(scan_frames),
            outputs_dir,
            scan_color_meta["output_format"],
            scan_color_meta["output_bit_depth"],
            scan_color_meta["source_bit_depth"],
        )

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest.setdefault("meta", {})
        manifest["meta"]["dpi_print"] = args.dpi
        manifest["meta"]["scan_source"] = f"inputs/{scan_copy.name}"
        # `meta` est un objet libre dans le schema legacy: rien n'empeche un
        # manifest ecrit a la main de porter `color` sous une autre forme qu'un
        # objet. Le dire plutot que de laisser passer un `AttributeError` nu.
        color_meta = manifest["meta"].setdefault("color", {})
        if not isinstance(color_meta, dict):
            raise PocInputError(
                f"`meta.color` du manifest doit etre un objet, trouve: "
                f"{type(color_meta).__name__}. Corrigez {manifest_path} avant de rejouer."
            )
        color_meta.update(scan_color_meta)

        # Story 2.2: faire avancer l'etat de lot transitoire (extraction/pdf ->
        # scan) sans casser les manifests ecrits avant cette story (etat absent).
        lot_meta = manifest["meta"].setdefault("lot", {})
        validate_lot_state_transition(lot_meta.get("state"), "scan")
        lot_meta["state"] = "scan"

        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        validate_manifest(manifest_path)
        logger.info("Manifest mis a jour et valide: %s", manifest_path)

        print(f"poc process-scan termine avec succes. Frames rescanees: {outputs_dir}")
        return 0

    except PocInputError as exc:
        return _handle_poc_failure(logger, exc, 1)
    except aruco_detection.UnsupportedScanDepthError as exc:
        # `IMREAD_UNCHANGED` rend desormais du float32 (TIFF 32 bits, .hdr,
        # .pfm) ou de l'int32 la ou `imread` nu rendait `None` ou de l'uint8
        # converti en silence. Sans cette clause, le refus sortirait en
        # assertion `cv2.error` nue au lieu d'un message actionnable.
        return _handle_poc_failure(logger, exc, 1)
    except aruco_detection.PageGeometryError as exc:
        # Base class: covers missing corners, duplicated corner IDs and degenerate
        # corner geometry. All three mean the page cannot be deskewed reliably.
        return _handle_poc_failure(logger, exc, 1)
    except aruco_detection.ScanFrameExtractionError as exc:
        return _handle_poc_failure(logger, exc, 1)
    except ValidationError as exc:
        return _handle_poc_failure(logger, exc, 1)
    finally:
        _close_logger_handlers(logger)


def poc_reconstruct_project(args):
    """Rebuild a coherent project.json from decoded page payloads (Story 2.6).

    Payloads mirror the minimal reconstructive contract described in
    ARCHITECTURE_DETAILED.md sections 3/6 (QR is not yet integrated, so
    callers pass already-decoded JSON payload files, e.g. synthetic fixtures
    or, later, a real QR decoder's output).

    Le fichier attendu est **le texte que porte le QR**, tel quel (bloquant B2 de la
    revue de 5.17): schema `2.0`, cles courtes, la sortie exacte d'un decodeur. Il est
    donc lu par `parse_payload` -- le **meme** chemin que le scan -- et non par un
    `json.loads` nu.

    Motif, et il etait mesure: la commande lisait un `json.loads` nu, donc exigeait un
    document a cles **longues** portant `2.0`, c'est-a-dire exactement celui que
    `parse_payload` refuse comme perime. Aucune entree ne satisfaisait les deux cotes a
    la fois, et le texte reel d'une planche `2.0` ressortait ici en `exit 1` avec
    **les douze champs annonces manquants** alors qu'aucun ne manquait -- mot pour mot
    le mode d'echec que `PayloadSchemaVersionRefused` existe pour eliminer sur le
    chemin voisin.
    """
    project_dir = Path(args.project)
    _create_project_layout(project_dir)
    logger = _configure_poc_logger(project_dir)

    try:
        logger.info("Demarrage de reconstruct-project pour le projet %s", project_dir)
        page_payloads = []
        for payload_path_str in args.payloads:
            payload_path = Path(payload_path_str)
            if not payload_path.is_file():
                raise PocInputError(f"Fichier payload introuvable: {payload_path}")
            try:
                # `parse_payload` rend le dictionnaire a cles **longues** que
                # `reconstruct_project_manifest` consomme: la projection est son
                # travail, et la refaire ici ferait deux lecteurs a faire divarier.
                page_payloads.append(
                    parse_payload(payload_path.read_text(encoding="utf-8"))
                )
            except PayloadValidationError as exc:
                # Le motif de `parse_payload` est deja une phrase pour l'operateur --
                # « planche perimee, a reimprimer » ou « QR etranger, aucun tirage en
                # cause » --, et c'est tout l'objet de l'AC 3. On le transporte
                # verbatim plutot que de le resumer.
                raise PocInputError(
                    f"Payload de page refuse ({payload_path}): {exc}"
                ) from exc

        existing_manifest = None
        if args.manifest:
            manifest_arg_path = Path(args.manifest)
            if not manifest_arg_path.is_file():
                raise PocInputError(f"Manifest local introuvable: {manifest_arg_path}")
            try:
                existing_manifest = json.loads(manifest_arg_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise PocInputError(f"Manifest local JSON invalide ({manifest_arg_path}): {exc}") from exc

        manifest = reconstruct_project_manifest(page_payloads, existing_manifest=existing_manifest)

        manifest_path = project_dir / "project.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        validate_manifest(manifest_path)
        logger.info("Manifest reconstruit et valide: %s", manifest_path)

        status = manifest["reconstruction"]["status"]
        print(f"reconstruct-project termine avec succes (statut: {status}). Manifest: {manifest_path}")
        return 0

    except PocInputError as exc:
        return _handle_poc_failure(logger, exc, 1)
    except ReconstructionError as exc:
        return _handle_poc_failure(logger, exc, 1)
    except ValidationError as exc:
        return _handle_poc_failure(logger, exc, 1)
    finally:
        _close_logger_handlers(logger)


def _configure_extract_logger(project_dir: Path) -> logging.Logger:
    """Logger de la commande `extract`, dont elle est proprietaire.

    Meme motif que `_configure_poc_logger` (fichier sous `logs/` + console),
    mais journal distinct: la story 3.3 journalise son rapport de metadonnees
    source et sa decision de confirmation **dans ce logger** et n'en cree
    aucun.
    """
    logger = logging.getLogger(f"mixed_media_utility.extract.{project_dir.resolve()}")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    log_path = project_dir / project_layout.LOGS_DIRNAME / "extract.log"
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console_handler)

    return logger


def _configure_scan_logger(project_dir: Path) -> logging.Logger:
    """Logger de la commande `scan`, dont elle est proprietaire.

    Meme motif que `_configure_extract_logger`: fichier sous `logs/` plus
    console, journal distinct par commande. Un journal partage melangerait le
    rapport d'ingestion a celui d'extraction, alors que les deux commandes sont
    executees par des operateurs differents, sur des postes differents.
    """
    logger = logging.getLogger(f"mixed_media_utility.scan.{project_dir.resolve()}")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    log_path = project_dir / project_layout.LOGS_DIRNAME / "scan.log"
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console_handler)

    return logger


def _stdin_is_interactive() -> bool:
    """L'entree standard est-elle un terminal ?

    Isole en fonction pour une seule raison, et elle est la moitie de l'AC 5: c'est le
    **seul** predicat qui separe « poser une question a un humain » de « bloquer un
    script ». Un `sys.stdin.isatty()` ecrit en ligne dans la commande serait impossible a
    substituer proprement dans les deux tests que l'AC exige -- celui du terminal et celui
    du pipe --, et le regime non teste serait alors precisement celui qui pend.

    Un `sys.stdin` a `None` (interpreteur lance sans entree, service) ou un objet dont
    `isatty` leve sont traites comme **non interactifs**: la seule reponse sure a « je ne
    sais pas si quelqu'un est la » est de ne pas attendre de reponse.
    """
    flux = getattr(sys, "stdin", None)
    if flux is None:
        return False
    try:
        return bool(flux.isatty())
    except (ValueError, OSError):
        return False


def _ask_apply_correction(logger) -> bool:
    """Poser l'invite `Y/N` d'application de la correction. AC 5 de 5.23.

    **Elle n'est appelee que depuis un terminal interactif**, et l'appelant est le seul a
    en decider: c'est ce qui garde `_stdin_is_interactive` testable seule.

    Le defaut est **appliquer**, y compris sur une entree vide (l'operateur qui frappe
    Entree) et sur une fin de flux: `EPIC5-ARB-82` decision 6, « le geste par defaut est
    celui qui sert l'utilisateur, le geste explicite est celui qui s'en ecarte ». Toute
    reponse commencant par `n` garde le brut; tout le reste applique. On ne boucle pas
    sur une reponse incomprise -- une invite qui insiste est un cran de plus vers l'invite
    qui bloque.
    """
    print(
        "Appliquer la correction couleur aux frames de ce lot ? [Y/n] "
        f"(non = livrer le scan brut, equivalent a {color_calibration.RAW_OUTPUT_FLAG})",
        end=" ",
    )
    try:
        reponse = input().strip().lower()
    except EOFError:
        reponse = ""
    if reponse.startswith("n"):
        logger.info(
            "Invite: l'operateur a repondu non, le lot est livre brut (motif '%s').",
            color_calibration.NOT_APPLIED_OPERATOR_OPT_OUT)
        return False
    return True


def _ask_overwrite_profile(chaine_occupante: str, radical: str) -> bool:
    """Poser l'invite `Y/N` d'ecrasement d'un profil homonyme. `EPIC5-ARB-99`, geste 3.

    Mots d'Egan, verbatim: « message "un profil porte deja ce nom. Voulez-vous
    l'ecraser ?" Y/N) en cas de non on ajoute une empreinte differenciante. »

    **Le texte de la question n'est pas ecrit ici**: il descend de
    `io.calibration_profile.COLLISION_PROMPT`, parce que ce module est le seul a savoir
    qu'il y a collision et la CLI la seule a savoir s'il y a quelqu'un pour repondre.
    Une seconde redaction de la phrase divergerait de celle que le module documente.

    **Le defaut est `N`, et c'est l'inverse des deux autres invites de ce fichier.**
    L'AC 5 et la bascule de `EPIC5-ARB-92` appliquent par defaut, parce que le geste par
    defaut y est celui qui sert l'operateur; ici le geste par defaut est celui qui **ne
    detruit rien**. Une entree vide, une fin de flux ou une reponse incomprise gardent
    donc les deux profils, sous deux noms que rien ne confond -- exactement ce que la
    branche hors terminal fait deja. Repondre `Y` est un geste explicite: c'est le seul
    chemin du depot par lequel un profil mesure est perdu.

    Elle n'est appelee que derriere `_stdin_is_interactive`, et l'appelant en decide:
    c'est ce qui garde le predicat testable seul, et c'est deja paye deux fois dans ce
    fichier.
    """
    print(calibration_profile.COLLISION_PROMPT.format(
        stem=radical, chaine=chaine_occupante), "[y/N]", end=" ")
    try:
        reponse = input().strip().lower()
    except EOFError:
        reponse = ""
    return reponse.startswith("y") or reponse.startswith("o")


def _confirmation_d_ecrasement_de_profil():
    """L'invite d'ecrasement **si et seulement si** il y a un terminal. `EPIC5-ARB-99`.

    Rend `None` hors terminal, ce qui est la valeur que `write_profile` interprete
    comme « personne pour repondre »: le profil entrant y prend alors une empreinte
    differenciante, jamais l'ecrasement. C'est le regime des scripts, de la CI et de ces
    4900 tests, et c'est celui que la note d'Egan ne couvrait pas.

    Ecrite en fonction, et non en ternaire sur chacun des trois sites d'appel: trois
    redactions de la meme condition divergeraient, et le site oublie serait celui ou
    l'invite ne se poserait jamais -- une invite qu'on croit posee est pire qu'une
    invite absente.
    """
    return _ask_overwrite_profile if _stdin_is_interactive() else None


def _bascule_en_calibration_demandee(payloads, logger, *,
                                     planches_muettes: int = 0) -> bool:
    """Faut-il traiter cette pile comme un `scan ... calibrate` ? (`EPIC5-ARB-92`)

    Trois conditions, dans cet ordre, et l'ordre est la moitie du sujet:

    0. **aucune feuille de la pile n'est restee muette.** Une feuille dont le QR n'a
       rien livre est une planche dont on ne connait pas encore l'identite, jamais une
       feuille absente: la compter pour rien faisait basculer en mode calibration une
       pile qui portait N planches d'images. Mesure du regime ferme ici -- N planches a
       QR illisible plus une page de calibration: hors terminal la bascule avait lieu
       **sans invite**, aucune frame n'etait ecrite, et la commande rendait **0**. Un
       scan qui n'ecrit rien et rend un succes est le pire des deux mondes; et en
       terminal, l'invite affirmait « cette pile ne porte aucune planche d'images »,
       ce qui etait faux de N feuilles. Le chemin savait deja distinguer « page presente
       mais non identifiee » (`if not identified:` plus haut, qui le dit et rend 0 sans
       rien ecrire); ce predicat ne le savait pas;
    1. la pile ne porte **que** des pages sans identite de lot -- predicat de
       `io.reconstruction`, qui possede la partition et decide aussi le refus;
    2. **et seulement alors** l'operateur est consulte.

    Ce court-circuit est ce qui tient les deux frontieres negatives de ce lot: aucune
    question n'est posee sur une pile de planches d'images -- le regime nominal du scan
    ne voit pas passer une invite de plus --, ni sur une pile **mixte**, qui reste
    refusee (`EPIC5-ARB-86`). Une invite posee la deviendrait une invite qu'on apprend a
    expedier sans lire.

    Ecrite comme fonction, et non en ligne dans `scan_command`: les deux frontieres se
    verifient alors sans monter un scan complet, ce que le budget de l'AC 9 exclut.
    """
    if planches_muettes:
        # **On le dit, et on ne bascule pas.** Le silence etait le defaut: la pile
        # repart sur le chemin de scan de lot, ou elle rencontre le refus nomme qui
        # designe la feuille en cause -- donc un code de sortie non nul, et un journal
        # qui porte les deux faits (les feuilles muettes, puis le refus).
        logger.warning(
            "%d feuille(s) de cette pile n'ont pas livre leur QR: ce sont des planches "
            "dont l'identite est inconnue, pas des feuilles absentes. La bascule en "
            "mode calibration (%s) n'est donc ni proposee ni prise -- elle consignerait "
            "un profil sans ecrire une seule frame. Rescannez les feuilles muettes, ou "
            "scannez la page de calibration dans une passe separee.",
            planches_muettes, SCAN_CALIBRATE_SUBCOMMAND)
        return False
    if not reconstruction.pile_sans_planche_d_images(list(payloads)):
        return False
    return _accepter_la_bascule_en_calibration(logger)


def _accepter_la_bascule_en_calibration(logger) -> bool:
    """Poser l'invite `Y/N` de bascule en mode calibration. `EPIC5-ARB-92`.

    Mandat d'Egan, verbatim: « un lot qui ne possede qu'une page de calibration doit
    etre accepte avec la commande de calibration ! Sans la commande de calibration on
    doit etre invite (Y/N) a passer en mode calibration. » Refuser cette pile revenait a
    refuser le regime nominal du livrable de la story 5.23, dont l'objet est de rendre
    la page de calibration autonome de tout rush, lot, cadence et projet
    (`EPIC5-ARB-82`).

    **Meme forme que l'AC 5**, et volontairement: la garde d'interactivite est
    `_stdin_is_interactive` -- la seule du depot -- et l'invite n'est posee que derriere
    elle. Un `input()` inconditionnel leve `EOFError` sous pytest et bloque
    indefiniment sous `cron`; c'est deja paye deux fois dans ce fichier.

    **Hors terminal, on bascule** (`EPIC5-ARB-92`, et c'est la decision de fond de ce
    lot). C'est la seule interpretation possible d'une pile qui ne contient que des
    pages de calibration, et l'AC 5 a deja tranche dans ce sens: « faire la chose utile
    plutot qu'echouer ». Un refus hors terminal rendrait la commande inutilisable en
    script pour le seul regime qu'elle sert.

    Le `N` explicite, lui, **ne bascule pas**: la commande retombe alors sur le refus
    nomme `REFUS_PILE_SANS_PLANCHE`, qui dit deja quelle feuille est en cause et quel
    est le geste. Un operateur qui repond non affirme que sa pile devait porter des
    planches d'images -- il en manque, et c'est ce que le refus lui apprend.
    """
    if not _stdin_is_interactive():
        logger.info(
            "Pile de pages de calibration seules, hors terminal: bascule en mode "
            "calibration sans invite. Le profil de la chaine est consigne comme si "
            "`%s` avait ete passe.",
            SCAN_CALIBRATE_SUBCOMMAND)
        return True
    print(
        "Cette pile ne porte aucune planche d'images, seulement des pages de "
        f"calibration. Passer en mode calibration ({SCAN_CALIBRATE_SUBCOMMAND}) et "
        "consigner le profil de la chaine ? [Y/n]",
        end=" ",
    )
    try:
        reponse = input().strip().lower()
    except EOFError:
        reponse = ""
    if reponse.startswith("n"):
        logger.info(
            "Invite: l'operateur a refuse la bascule en mode calibration. La pile est "
            "traitee comme un scan de lot, donc refusee faute de planche d'images.")
        return False
    return True


#: **La derive de l'identite de chaine a suivi `calibrate` au coeur** (story
#: 11.6, lot B, `EPIC11-ARB-129`). Le nom local est un **alias, jamais une
#: copie**: une seconde redaction de la recette divergerait de la premiere, et
#: le symptome serait un profil que plus aucun scan ne retrouve. Il reste ici
#: parce que les bancs du depot exercent ce geste par `cli._derive_chain_id`.
_derive_chain_id = scan_calibrate.derive_chain_id


# ---------------------------------------------------------------------------
# La moitie AVAL du scan, **deplacee** dans le module de coeur `scan_write`
# (story 11.4b, lot S1, `EPIC11-ARB-67`).
#
# Correction designee, recadrage, avertissements page par page, refus prealable
# d'`EPIC5-ARB-34`, frames, manifest: le corps entier vit desormais dans
# `scan_write.py`, comme la moitie AMONT vit dans `scan_detect.py` depuis la
# story 7.3. Motif, verbatim de `tui/palier_projet.py:9-12`: « Ce module appelle
# `io/`, jamais `cli.py`. Les fonctions de `cli.py` impriment sur `stderr` et
# rendent un code retour: les appeler depuis une TUI enverrait des lignes dans
# le terminal **sous** l'ecran dessine, et rendrait un entier la ou l'interface
# a besoin d'un document ou d'un refus nomme. »
#
# Les noms locaux ci-dessous sont **des alias, jamais des copies**: une seconde
# redaction du recadrage ou de l'appariement des calibrations divergerait de la
# premiere, et l'ecart ne se verrait que sur les TIFF produits. Ils restent ici
# parce que `_consigner_le_profil_de_chaine` (`scan ... calibrate`) appelle
# encore `_fit_lot_correction`, et parce que les bancs du depot substituent ou
# exercent ces gestes par `cli.<nom>`.
# ---------------------------------------------------------------------------

_avertir_sur_une_page = scan_write._avertir_sur_une_page
_page_identifier = scan_write._page_identifier
_resolve_designated_correction = scan_write._resolve_designated_correction
_declared_calibration_pages = scan_write._declared_calibration_pages
_read_calibration_pages = scan_write._read_calibration_pages
_fit_lot_correction = scan_write._fit_lot_correction
_scanned_pages_for_output = scan_write._scanned_pages_for_output


def _designated_profile_source(args, project_dir: Path, logger) -> tuple:
    """Le profil que l'operateur a designe, et **par quel geste**. AC 12.

    Story 11.4b, lot S1: la precedence elle-meme (`--profil` l'emporte sur le
    defaut du projet) a suivi le corps dans `scan_write`, ou la 11.5 doit
    pouvoir la lire sans importer `cli.py`. Ce qui reste ici est la seule
    chose qui appartienne a un terminal: la lecture de l'objet `args`.
    """
    return scan_write.profil_designe_du_projet(
        project_dir, logger, profil_explicite=getattr(args, "profil", None))


def _print_scan_persistence(logger, persisted) -> None:
    """Dire ou en est **le lot**, et pas seulement ce que la passe a fait.

    Les deux verdicts sont portes chacun par qui peut le dire (EPIC5-ARB-32):
    le rapport de 5.6 dit ce que cette passe a ecrit, le manifest dit ou en est
    le lot. La question que l'operateur se pose reellement -- « ce lot est-il
    fini ? » -- n'a de reponse que dans le second.
    """
    logger.info("Manifest ecrit et valide: %s", persisted.manifest_path)
    logger.info(
        "Lot %s: etat %s, %d frame(s) reconstruite(s), %d de remplacement, "
        "attendu %s -- lot %s",
        persisted.lot_id,
        persisted.state_written,
        persisted.reconstructed_frame_count,
        persisted.synthetic_frame_count,
        "indetermine"
        if persisted.expected_frame_count is None
        else persisted.expected_frame_count,
        "complet" if persisted.lot_complete else "incomplet",
    )
    for code in persisted.findings:
        logger.info("Constat de persistance: %s", code)



def scan_detect_command(args):
    """Enveloppeur de `scan_detect.run_scan_detect` (story 7.3, AC 2a).

    **L'orchestration a quitte cette fonction** (`EPIC7-ARB-64`): ingestion,
    detection, tri et ecriture des documents vivent desormais dans le module de
    coeur `scan_detect`, appele **en processus** par cette commande comme par la
    GUI de l'Epic 7. Ce qui reste ici est ce qui appartient a un terminal, et
    rien d'autre: la mise en place du journal, la traduction des exceptions du
    coeur en messages imprimes, et les codes de sortie.

    Ce qui n'a pas change, et que deux tests d'equivalence mesurent
    (`tests/unit/test_scan_detect_noyau.py`): le document ecrit (octet pour
    octet hors horodatage), les messages imprimes, et les codes de sortie:

    * `0` succes -- y compris quand aucune planche n'a livre son QR (aucun
      document ecrit: aucune identite de lot n'est connue, l'ingestion, elle,
      a eu lieu), et quand la pile ne porte que des page(s) de calibration
      (meme motif: une page de calibration ne porte aucune identite de lot,
      constat renvoyant a `scan ... calibrate`, aucune invite, aucun document);
    * `1` erreur d'ingestion, de detection, de construction du document, ou
      refus avant ecriture (`scan_manifest.check_scan_conflicts`, dont la
      pile mixte -- une page de calibration lue avec des planches d'images,
      `REFUS_PILE_MIXTE`);
    * `130` interruption clavier (`AR2`, meme modele que `scan_command`).

    Les motifs imprimes sont ceux du coeur, VERBATIM (`str(exc)`): cette
    fonction n'en compose aucun, elle les prefixe. C'est le meme texte que la
    carte de tache de la GUI affiche -- deux lecteurs, une seule redaction (P9).
    """
    project_dir = Path(args.project)
    project_layout.ensure_project_layout(project_dir)
    logger = _configure_scan_logger(project_dir)
    logger.info("Demarrage de scan detect pour le projet %s", project_dir)

    try:
        try:
            issue = scan_detect.run_scan_detect(
                project_dir, args.scan, dpi=args.dpi,
                ingest_slug=args.lot_slug, logger=logger,
                # Story 11.4e, lot D. `--nouvelle-version` est declaree sur le
                # parseur PARENT `scan` et etait acceptee ici **sans un mot**
                # par argparse, pour n'etre jamais lue: une option INERTE, sur
                # l'objet meme qu'`EPIC11-ARB-104` cite en exemple. La
                # frontiere de `test_scan_detect_nouvelle_version.py` interdit
                # desormais qu'une option heritee reste ignoree.
                nouvelle_version=args.nouvelle_version,
                # Le manifeste porte la ligne d'eau des rangs de scan. Lu ICI
                # et non plus haut, et TOLERANT a son absence: `detect`
                # s'execute aussi sur un projet dont le `project.json` n'est
                # pas encore ecrit. Sans lui, un rang dont le dossier a ete
                # supprime serait rendu par defaut (`EPIC11-ARB-92`, point 3).
                manifest_du_projet=_manifeste_du_projet_si_present(project_dir),
            )
        except _REFUS_DU_COEUR_SUR_DETECT as exc:
            # Le motif est celui du coeur, prefixe et jamais reecrit. Le
            # journal, lui, porte deja la phase: elle est ecrite par le module
            # de coeur, au moment ou le refus tombe.
            print(f"Erreur: {exc}", file=sys.stderr)
            return 1
    except KeyboardInterrupt:
        # AR2 (AC 5): memes gardes que `scan_command`. Cette commande n'ecrit
        # ni frame ni manifest sur aucun chemin -- ce n'est donc jamais ce
        # qu'il faut relire apres une interruption. Le document de detection,
        # lui, peut avoir ete ecrit ou non selon l'instant de l'interruption;
        # quand il l'a ete, c'est par remplacement atomique (`os.replace`),
        # donc jamais dans un etat partiel.
        print(
            "\nInterruption clavier: scan detect arrete. Ni frame ni manifest "
            "n'etaient en jeu sur ce chemin. Le document de detection, s'il a "
            "ete ecrit, l'a ete par remplacement atomique (aucun document "
            "partiel ne peut rester en place): relire le dossier "
            "scans/<slug d'ingestion>/detections/ du projet pour savoir s'il "
            "existe."
        )
        return 130
    except OSError as exc:
        return _handle_poc_failure(
            logger,
            OSError(
                f"Erreur d'acces disque pendant scan detect: {exc}. Verifier "
                "l'espace disponible et les droits d'ecriture sur le dossier "
                "projet."
            ),
            1,
        )
    finally:
        _close_logger_handlers(logger)

    print(_compte_rendu_de_detect(issue))
    return 0


#: Les refus que le coeur leve sur le chemin `scan detect`, et que cet
#: enveloppeur convertit -- **tous au meme code de sortie et au meme prefixe**.
#: La liste est celle de l'AC 2a de 7.3: aucun n'est mis en forme par le coeur.
#:
#: **C'est un alias, jamais une copie, depuis la story 11.6 (lot B)**: la table
#: est publiee par `scan_detect`, comme `scan_write` publie sa
#: `CODES_DE_SORTIE`. Elle etait redigee deux fois -- ici et dans
#: `tui.atelier_scan_detection` --, ce que le lot C de la 11.5 a paye faute
#: d'une table publiee.
_REFUS_DU_COEUR_SUR_DETECT = scan_detect.REFUS_DU_COEUR


def _compte_rendu_de_detect(issue) -> str:
    """Le compte rendu imprime d'une passe qui a abouti, mot pour mot.

    Quatre issues, quatre phrases -- exactement celles d'avant l'extraction. La
    redaction vit ICI et pas dans le coeur: une phrase de terminal n'est pas un
    fait, et le coeur ne rend que des faits (`ScanDetectOutcome`).
    """
    report = issue.report
    if issue.motif_d_arret == scan_detect.ARRET_AUCUNE_PLANCHE_IDENTIFIEE:
        return (
            f"scan detect termine: {len(report.pages)} page(s) ingeree(s) "
            f"dans {report.scans_dir}, aucune identifiee. Aucun document "
            "de detection ecrit."
        )
    if issue.motif_d_arret == scan_detect.ARRET_PILE_DE_CALIBRATION_SEULE:
        return (
            "scan detect termine: pile de calibration seule, aucune "
            f"identite de lot. Consignez-la avec 'scan ... "
            f"{SCAN_CALIBRATE_SUBCOMMAND}'. Aucun document ecrit."
        )
    if issue.partition is not None:
        partition = issue.partition
        return (
            f"scan detect termine: tri par QR sur {len(report.pages)} page(s), "
            f"{len(issue.documents)} document(s) de detection ecrit(s) "
            f"({len(partition.reliquat)} page(s) au reliquat, "
            f"{len(partition.hors_perimetre)} hors perimetre). "
            f"Rapport de tri: {issue.rapport_de_tri}"
        )
    return (
        f"scan detect termine avec succes. {len(report.pages)} page(s) dans "
        f"{report.scans_dir}, {issue.pages_identifiees} identifiee(s). Document de "
        f"detection: {issue.document_path}."
    )



def _ecrire_le_lot_detecte(project_dir, logger, args, report, detection,
                           payloads, overwrite, dpi_geometrie, dpi_manifest,
                           corrections=None):
    """Enveloppeur de `scan_write.ecrire_le_lot_detecte` (story 11.4b, lot S1).

    **La sequence d'ecriture a quitte cette fonction** (`EPIC11-ARB-67`):
    correction designee, recadrage, avertissements, refus prealable
    (`check_scan_conflicts`), frames, manifest et trace du profil designe
    vivent desormais dans le module de coeur `scan_write`, appele **en
    processus** par cette commande comme par une interface. Ce qui reste ici
    est ce qui appartient a un terminal, et rien d'autre: la lecture de l'objet
    `args`, les deux invites `Y/N`, la traduction des exceptions du coeur en
    messages imprimes, et le code de sortie.

    C'est le meme geste que la story 7.3 a fait pour la moitie AMONT
    (`scan_detect_command` / `run_scan_detect`), et le meme que la story 5.26
    avait deja fait ici en tirant ce corps hors de `scan_command`: **corps
    deplace, jamais reecrit** -- une seule redaction du geste. Une seconde
    redaction divergerait, et l'ecart ne se verrait que sur les TIFF produits.

    **Les trois regimes de l'invite de correction sont preserves ICI**, avec
    leur comportement observable inchange (AC 2.2):

    1. drapeau explicite (`--cc off`, `--garder-le-scan-brut`): la decision est
       deja prise, elle descend en booleen et aucune invite n'est posee;
    2. hors terminal interactif (script, CI, pipe, cron): le rappel passe vaut
       `None`, donc **aucune invite** et le defaut est appliquer. Une invite qui
       bloque un script est une panne, pas une precaution;
    3. en terminal interactif seulement: le rappel est `_ask_apply_correction`,
       et son defaut est encore appliquer.

    Le predicat d'interactivite est evalue ici plutot qu'au fond de la
    sequence, et c'est sans effet observable: il ne lit que `sys.stdin`, et le
    coeur n'appelle le rappel que dans le regime ou l'ancienne condition
    `apply_correction and _stdin_is_interactive()` etait vraie. Ce que ce
    deplacement ferme, lui, est reel: **le coeur ne lit jamais `stdin`**, donc
    aucune interface a boucle d'evenements ne peut plus geler dessus
    (`EPIC7-ARB-106`, paye cote GUI avec `QMessageBox.exec()`).

    Les gardes AR2 (`KeyboardInterrupt`, `OSError`) restent chez les appelants:
    chaque commande porte son propre message d'interruption et reformule
    l'acces disque. `KeyboardInterrupt` derive de `BaseException` et n'est donc
    pas vue par le `except Exception` ci-dessous; `OSError` n'est pas dans
    `scan_write.CODES_DE_SORTIE` et **remonte** telle quelle.

    `corrections` est le document de detection **brut** portant la couche
    `manual_corrections`, ou `None` (story 11.4b, lot S3). Seul
    `scan_write_command` en a un: `scan` ecrit dans la foulee de sa propre
    detection, sans document. Aucune commande de la CLI ne sait POSER une
    correction -- c'est l'interface qui les pose --, donc aucun parcours CLI
    existant ne change de comportement.

    Rend le code de sortie de la commande: `0` succes, `1` refus, et depuis la
    story 11.4c (lot V2, AC 9) `scan_write.CODE_SUCCES_PARTIEL` quand le lot a
    ete ecrit sans etre celui qui etait promis -- un lot declare incomplet, ou
    porteur de frames de remplacement. Le verdict n'est pas calcule ici: il est
    **lu** sur l'inventaire que le coeur rend et que cette fonction vient
    d'imprimer.
    """
    try:
        issue = scan_write.ecrire_le_lot_detecte(
            project_dir, report, detection, payloads,
            dpi_geometrie=dpi_geometrie, dpi_manifest=dpi_manifest,
            overwrite=overwrite,
            # **La couche `manual_corrections` du document** (story 11.4b, lot
            # S3, AC 4). Seul `scan write` en a une a passer: elle vit dans le
            # document de detection, que `scan` ne produit pas -- il ecrit dans
            # la foulee de sa propre detection, en memoire. `None` des deux
            # cotes ne change rien, et aucune commande de la CLI ne sait poser
            # une correction: c'est l'interface qui les pose (GUI de l'Epic 7,
            # TUI de la 11.5), et c'est ici qu'elles cessent d'etre ignorees.
            corrections_manuelles=corrections,
            **_options_d_ecriture_du_terminal(args, project_dir, logger))
    except Exception as exc:
        code = _refus_du_coeur_a_l_ecriture(exc)
        if code is None:
            # Ce que la table ne nomme pas n'etait pas attrape ici non plus: un
            # bug de programmation remonte, et l'`OSError` va se faire
            # reformuler par la garde AR2 de la commande appelante.
            raise
        return code
    return _conclure_l_ecriture(logger, issue)


def _options_d_ecriture_du_terminal(args, project_dir: Path, logger) -> dict:
    """Ce qu'un TERMINAL apporte a une passe d'ecriture, et rien d'autre.

    Story 11.6, lot B: ces valeurs etaient ecrites en clair dans
    `_ecrire_le_lot_detecte`, seul appelant du coeur a l'epoque. Depuis que
    `scan_write_command` appelle `scan_write.ecrire_depuis_le_document`, il y
    en a **deux**, et deux lectures divergentes du meme `args` produiraient
    deux passes qui ne font pas la meme chose sur le meme lot -- exactement le
    defaut que la 11.4b a ferme d'un cran plus bas.

    Rien ici n'est une decision: c'est la traduction de l'objet `args` argparse
    et du predicat d'interactivite en parametres nommes du coeur.

    **Les trois regimes de l'invite de correction sont preserves ICI**, avec
    leur comportement observable inchange (AC 2.2 de la 11.4b):

    1. drapeau explicite (`--cc off`, `--garder-le-scan-brut`): la decision est
       deja prise, elle descend en booleen et aucune invite n'est posee;
    2. hors terminal interactif (script, CI, pipe, cron): le rappel passe vaut
       `None`, donc **aucune invite** et le defaut est appliquer. Une invite qui
       bloque un script est une panne, pas une precaution;
    3. en terminal interactif seulement: le rappel est `_ask_apply_correction`,
       et son defaut est encore appliquer.
    """
    profil_designe, origine_du_profil = _designated_profile_source(
        args, project_dir, logger)
    return dict(
        logger=logger,
        # `--cc off` (`EPIC5-ARB-78`): la correction est **ajustee quand
        # meme** -- c'est ce qui permet au document de dire qu'il y en avait
        # une -- et n'est simplement pas appliquee. Le drapeau est lu ici,
        # une fois, et descend en booleen: deux lectures de `args` a deux
        # etages laisseraient la porte a deux lectures divergentes du meme
        # choix.
        appliquer_la_correction=(
            getattr(args, "color_correction", CC_ON) == CC_ON),
        # **Le refus est le geste explicite** (`EPIC5-ARB-82` decision 6,
        # AC 5 de 5.23): l'operateur qui l'a tape a deja repondu, donc
        # aucune invite ne lui est posee.
        livrer_brut=bool(getattr(args, "keep_raw", False)),
        divergence_bypass=bool(getattr(args, "divergence_bypass", False)),
        profil_designe=profil_designe,
        origine_du_profil=origine_du_profil,
        # `--nouvelle-version` protege les DEUX sorties de la passe
        # (`EPIC11-ARB-104`/`-94`) : le dossier de scan et les frames
        # rescannees. Un seul drapeau pour une seule intention.
        #
        # Liaison du 2026-09-01 : `main` lisait ces deux valeurs **en clair**
        # dans `_ecrire_le_lot_detecte`, seul appelant du coeur de son cote.
        # Le lot B de la 11.6 en a fait deux -- `scan` et `scan-write` --, et
        # c'est precisement le motif pour lequel cette fonction existe : deux
        # lectures divergentes du meme `args` feraient deux passes qui ne
        # protegent pas les memes sorties sur le meme lot.
        nouvelle_version=getattr(args, "nouvelle_version", False),
        manifest_du_projet=_manifeste_du_projet_si_present(project_dir),
        # Regime 3 et lui seul. Hors terminal, `None`: « personne pour
        # repondre », et le coeur applique -- exactement le regime 2.
        demander_l_application_de_la_correction=(
            (lambda: _ask_apply_correction(logger))
            if _stdin_is_interactive() else None),
        # La valeur passee est le predicat d'interactivite, jamais l'invite
        # nue: la passer nue ferait poser un `input()` sous `cron`
        # (`EPIC5-ARB-99`).
        confirmer_l_ecrasement=_confirmation_d_ecrasement_de_profil(),
    )


def _refus_du_coeur_a_l_ecriture(exc: BaseException):
    """Imprimer un refus du coeur et rendre son code, ou `None` s'il est inconnu.

    Le motif est celui du coeur, prefixe et jamais reecrit. Le journal, lui,
    porte deja la phase: elle est ecrite par `scan_write`, au moment ou le
    refus tombe. `None` veut dire « la table ne nomme pas cette exception »:
    l'appelant la **relaie** au lieu de la deguiser en refus metier.
    """
    code = scan_write.code_de_sortie(exc)
    if code is None:
        return None
    print(f"Erreur: {exc}", file=sys.stderr)
    return code


def _conclure_l_ecriture(logger, issue) -> int:
    """Imprimer ce que la passe a produit, et rendre son code de sortie.

    Story 11.6, lot B: extrait de `_ecrire_le_lot_detecte`, dont c'etait la
    seconde moitie, pour que les **deux** voies d'ecriture -- `scan` et
    `scan-write` -- rendent le meme compte rendu. Une seconde redaction de ces
    quatre phrases divergerait, et l'operateur lirait deux verdicts differents
    sur le meme lot selon la commande tapee.

    Rend le code de sortie: `0` succes, et depuis la story 11.4c (lot V2,
    AC 9) `scan_write.CODE_SUCCES_PARTIEL` quand le lot a ete ecrit sans etre
    celui qui etait promis -- un lot declare incomplet, ou porteur de frames de
    remplacement. Le verdict n'est pas calcule ici: il est **lu** sur
    l'inventaire que le coeur rend et que cette fonction vient d'imprimer.
    """
    report = issue.rapport
    persisted = issue.persisted
    _print_scan_persistence(logger, persisted)
    # **Le pont de la story 11.4c (lot V2, AC 9)**: l'inventaire que cette
    # commande vient d'imprimer -- avertissements d'ecriture puis constats de
    # persistance -- decide desormais du code de sortie. Rien n'est recalcule
    # ici: le verdict est celui du coeur, lu sur l'objet rendu (F6 de la fiche
    # 11.4c: « toutes les donnees du verdict sont sur place, il n'y a rien a
    # recalculer, seulement a decider »).
    inventaire = scan_write.inventaire_de_l_ecriture(issue)
    degradations = scan_write.motifs_de_degradation(inventaire)
    code = scan_write.code_de_sortie_de_l_ecriture(inventaire)
    # **La phrase cesse de dire « succes » quand le code est degrade** (AC 9.5).
    # Elle dit exactement la meme mesure -- memes cardinaux, meme verdict de
    # completude, meme chemin de manifest --, sous un verbe qui ne ment pas, et
    # elle nomme les motifs qui ont degrade le code pour que la lecture humaine
    # et la lecture par script disent la meme chose.
    tete = (
        "scan termine avec succes."
        if code == scan_write.CODE_SUCCES else
        f"scan termine SANS livrer le lot promis ({', '.join(degradations)})."
    )
    print(
        f"{tete} {len(report.pages)} page(s) dans "
        f"{report.scans_dir}; lot {persisted.lot_id} "
        f"{'complet' if persisted.lot_complete else 'incomplet'} "
        f"({persisted.reconstructed_frame_count} frame(s) reconstruite(s), "
        f"{persisted.synthetic_frame_count} de remplacement). "
        f"Manifest: {persisted.manifest_path}"
    )
    return code


# ---------------------------------------------------------------------------
# Le regime de vrac (story 5.24) -- declenche par l'ABSENCE de `--lot-slug`
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Les gestes de scan **partages** avec `scan_detect` (story 7.3, AC 2a).
#
# Ils ont ete DEPLACES dans le module de coeur `scan_detect`, qui est le point
# d'appel unique de la detection -- pas recopies: une seconde redaction de
# l'ecriture atomique ou du tri divergerait de la premiere. Les noms locaux
# ci-dessous restent ceux qu'utilise le chemin `scan` d'un bloc, qui n'est pas
# touche par cette story.
# ---------------------------------------------------------------------------

TRI_DOCUMENT_FILENAME = scan_detect.TRI_DOCUMENT_FILENAME
SOURCE_DIGEST_PREFIX = scan_detect.SOURCE_DIGEST_PREFIX
_write_json_document_atomically = scan_detect.ecrire_document_json_atomiquement
_condensat_du_fichier_source = scan_detect.condensat_du_fichier_source
_identite_du_projet_courant = scan_detect.identite_du_projet_courant
_journaliser_le_tri = scan_detect.journaliser_le_tri
_ecrire_le_rapport_de_tri = scan_detect.ecrire_le_rapport_de_tri
_pages_du_lot = scan_detect.pages_du_lot



def _le_vrac_est_demande(args) -> bool:
    """Le regime de vrac se declenche par l'**absence** de `--lot-slug`.

    `EPIC5-ARB-106`, et c'est la propriete qui rend ce choix sur: `ingest_slug`
    vaut deja `None` par defaut (`scan_ingest.py`, alimente par `args.lot_slug`),
    donc l'absence est un etat **legal aujourd'hui**. Les seules invocations dont
    le comportement change sont celles qui **echouent deja** -- pile multi-lots
    (`LotIdentityError`) et pile mixte (`REFUS_PILE_MIXTE`). Rien de ce qui
    marche ne casse.

    Aucun drapeau neuf n'est ajoute a `scan` pour le vrac -- ni `--vrac`, ni
    sous-commande: c'etait la recommandation ecartee, et un drapeau garde « au
    cas ou » recreerait deux gestes pour un seul comportement.
    """
    return getattr(args, "lot_slug", None) is None




def _consigner_les_pages_de_calibration_du_vrac(
        project_dir: Path, logger, args, report, detection_complete, partition):
    """Consigner **chaque** page de calibration trouvee dans le vrac (AC 7).

    Deux moities qui tiennent ensemble (`EPIC5-ARB-107`):

    1. **elle se consigne** -- la page produit exactement le profil que
       `scan ... calibrate` produirait de la meme feuille. Le corps est
       **appele** (`_consigner_le_profil_de_chaine`), jamais reecrit: il a ete
       extrait par `EPIC5-ARB-92` pour avoir plusieurs appelants sans qu'aucune
       voie n'ecrive un profil que l'autre n'ecrirait pas. Le vrac en est le
       **troisieme**;
    2. **elle ne s'applique pas** -- aucun lot n'est corrige par elle du seul
       fait qu'elle etait dans la pile. La correction d'un lot vient du profil
       **designe** (`--profil`, defaut au projet, `EPIC5-ARB-83`), et le profil
       qui vient d'etre cree n'est designe par rien.

    **Le nom du profil est celui que la feuille porte**, c'est-a-dire son
    `scan_chain_label` -- le seul champ que `io.payload.CALIBRATION_ONLY_FIELDS`
    exige d'elle, donc present et non vide par contrat. Ce choix repond a la
    question laissee ouverte a la redaction (« quel nom porte le profil cree
    quand le vrac tourne sans personne devant l'ecran ? ») sans poser **aucune**
    invite: poser N questions au milieu du tri de trois cents pages est un geste
    qu'aucune operatrice ne veut, et `--nom` n'existe de toute facon pas sur
    `scan`. Il fait mieux que le defaut derive de 5.23: deux pages de
    calibration d'une meme passe partagent le meme `chain_id` derive, donc le
    meme nom de fichier, donc le second **ecraserait** le premier -- ce que
    l'AC 7 interdit nommement. Le libelle, lui, vient de la feuille et les
    distingue.

    Une page inexploitable ne produit **aucun** profil, va au **reliquat avec
    son motif** et ne contamine le verdict d'aucun lot de la passe: son echec
    est local a sa propre consignation.
    """
    profils: list[scan_sorting.ProfilCree] = []
    echecs: list[scan_sorting.EntreeDeReliquat] = []
    # Revue de vague (couche 2): le nom du profil vient du libelle, donc deux
    # feuilles de la MEME passe au MEME libelle viseraient le meme fichier --
    # la seconde detruisait la premiere en silence, et le rapport annoncait
    # deux profils la ou un seul existait. La premiere gagne, la seconde va au
    # reliquat avec son motif (meme geste que l'AC 7 pour toute feuille qu'on
    # ne peut pas consigner): son echec reste local, aucun lot n'en depend.
    etiquettes_consignees: dict[str, Path] = {}
    for page_triee in partition.pages_de_calibration:
        detectee = next(
            page for page in detection_complete.pages
            if page.read_rank == page_triee.read_rank
        )
        feuille = dataclasses.replace(detection_complete, pages=(detectee,))
        etiquette = page_triee.scan_chain_label
        deja = etiquettes_consignees.get(etiquette)
        if deja is not None:
            logger.warning(
                "Deuxieme page de calibration au libelle '%s' dans cette passe "
                "(%s): elle n'est PAS consignee, car elle ecraserait le profil "
                "que la premiere vient d'ecrire (%s). Elle va au reliquat; "
                "renommez la chaine sur l'une des deux feuilles et rescannez "
                "si les deux sont voulues.",
                etiquette, page_triee.locator.source_path,
                deja.relative_to(project_dir).as_posix())
            echecs.append(scan_sorting.EntreeDeReliquat(
                read_rank=page_triee.read_rank,
                locator=page_triee.locator,
                motif=scan_sorting.RELIQUAT_CALIBRATION_LIBELLE_EN_DOUBLE,
                detail=(
                    f"chaine '{etiquette}': deja consignee dans cette passe par "
                    f"{deja.relative_to(project_dir).as_posix()}"),
            ))
            continue
        args_de_la_feuille = argparse.Namespace(**vars(args))
        args_de_la_feuille.nom = etiquette
        args_de_la_feuille.commentaire = (
            f"Profil consigne par le tri en vrac du scan '{report.ingest_slug}', "
            f"feuille {page_triee.locator.source_path} "
            f"(page {page_triee.locator.page_index}).")
        ecrits: list[Path] = []
        code = _consigner_le_profil_de_chaine(
            project_dir, report, feuille, args_de_la_feuille, logger,
            profils_ecrits=ecrits)
        if code == 0 and ecrits:
            etiquettes_consignees[etiquette] = ecrits[0]
            profils.append(scan_sorting.ProfilCree(
                chain_id=_derive_chain_id(report, args.scan, logger) or "",
                etiquette=etiquette,
                chemin_relatif=ecrits[0].relative_to(project_dir).as_posix(),
                locator=page_triee.locator,
            ))
            continue
        logger.warning(
            "Page de calibration inexploitable dans ce vrac (%s): aucun profil "
            "n'est consigne pour elle, et le verdict des lots de la passe n'en "
            "depend pas.", page_triee.locator.source_path)
        echecs.append(scan_sorting.EntreeDeReliquat(
            read_rank=page_triee.read_rank,
            locator=page_triee.locator,
            motif=scan_sorting.RELIQUAT_CALIBRATION_INEXPLOITABLE,
            detail=f"chaine '{etiquette}': profil non consigne",
        ))
    return profils, echecs


def _scanner_le_vrac(project_dir: Path, logger, args, report, overwrite,
                     scan_dpi, pages):
    """Trier le vrac par QR, puis ecrire **un lot a la fois** (AC 2, 4, 5, 6, 7, 10).

    Le tri s'insere **avant** `scan_detection._reconcile_lot`, jamais en
    rattrapage de son echec: c'est cette fonction-la qui refuse aujourd'hui deux
    identites de lot dans une passe, et reconstituer une partition depuis un
    message d'erreur serait une seconde lecture de la pile.

    Consequence directe sur l'AC 5: `check_scan_conflicts` n'est atteint que sur
    des piles **deja homogenes par lot** -- il est appele dans
    `_ecrire_le_lot_detecte`, une fois par lot trie. `REFUS_PILE_MIXTE` n'est ni
    supprime, ni elargi, ni affaibli: il garde le regime `--lot-slug` et **cesse
    d'etre atteint** sur le chemin qui trie, parce que le tri a retire la page de
    calibration du lot avant toute lecture d'identite.

    Les trois gestes que le chemin historique pose **avant** d'ecrire sont poses
    ici a l'identique, dans le meme ordre et avec les memes arguments -- c'est ce
    que l'AC 2bis appelle non-regression, et c'est mesure sur les valeurs
    produites, jamais sur un code de retour:

    * une passe dont aucune planche n'a livre son QR le dit et rend `0`;
    * la bascule `Y/N` d'`EPIC5-ARB-92` est proposee, **feuilles muettes
      comprises** (AC 6);
    * un `N` explicite fait retomber la pile sur `REFUS_PILE_SANS_PLANCHE`, qui
      nomme deja la feuille en cause et le geste.

    Rend le code de sortie de la commande.
    """
    for page in pages:
        if page.refusal_reason:
            logger.warning(
                "Feuille refusee (rang de lecture %s, %s): %s",
                page.read_rank, page.locator_source, page.refusal_reason)

    # Le rapport « complet » n'est **jamais reconcilie**: il ne peut donc pas
    # refuser un lot melange, ce qui est tout l'objet du tri. Il sert a deux
    # choses -- retrouver une page detectee par son rang, et porter la pile
    # entiere aux deux gestes historiques ci-dessous. La reconciliation, elle, a
    # lieu **par lot** plus bas, sur des piles deja homogenes.
    detection_complete = scan_detection.LotDetectionReport(
        ingest_slug=report.ingest_slug,
        scan_dpi=scan_dpi,
        ingest_declared_dpi=report.declared_dpi,
        pages=tuple(pages),
    )
    identifiees = [page for page in pages if page.payload is not None]
    payloads_identifies = tuple(page.payload for page in identifiees)
    planches_muettes = len(pages) - len(identifiees)

    # **Les trois gestes historiques passent AVANT le tri, et dans leur ordre.**
    # Aucun d'eux n'a besoin d'une partition -- ils portent sur des piles que le
    # vrac ne concerne pas --, et les poser apres le tri aurait exige une
    # identite de projet la ou il n'y a rien a ranger.
    if not identifiees:
        # Message et code de retour **inchanges** (AC 2bis): ni frame ni manifest
        # ne sont ecrits, l'ingestion, elle, a eu lieu. Aucun rapport de tri non
        # plus: rien n'a ete lu, donc il n'y a pas d'identite de projet a
        # laquelle comparer quoi que ce soit.
        logger.warning(
            "Aucune planche n'a livre son QR: ni frame ni manifest ne sont "
            "ecrits. L'ingestion, elle, a eu lieu."
        )
        print(
            f"scan termine: {len(report.pages)} page(s) ingeree(s) dans "
            f"{report.scans_dir}, aucune identifiee. Manifest inchange."
        )
        return 0

    # **AC 6, et c'est l'appel historique tel quel.** Une pile qui ne porte que
    # des pages de calibration bascule comme aujourd'hui -- invite `Y/N` en
    # terminal, bascule par defaut hors terminal --, et les feuilles muettes
    # comptent (condition 0 du predicat). La consignation automatique
    # d'`EPIC5-ARB-107` (AC 7) porte sur les piles qui **echouent** aujourd'hui,
    # la pile mixte et le vrac multi-lots, jamais sur celle-la.
    if _bascule_en_calibration_demandee(
            payloads_identifies, logger, planches_muettes=planches_muettes):
        return _consigner_le_profil_de_chaine(
            project_dir, report, detection_complete, args, logger)

    if reconstruction.pile_sans_planche_d_images(list(payloads_identifies)):
        # La bascule n'a pas eu lieu -- `N` explicite, ou feuilles muettes -- et
        # la pile ne porte aucune planche d'images. Elle repart sur le chemin de
        # lot et retombe sur `REFUS_PILE_SANS_PLANCHE`, qui nomme deja la feuille
        # en cause et le geste. Comportement **inchange**. Le predicat est celui
        # de `io.reconstruction`, qui possede la partition -- jamais une seconde
        # lecture ecrite ici (`EPIC5-ARB-92`).
        #
        # `EPIC5-ARB-112` (revue de vague, tranche par Egan le 2026-08-25) --
        # **le refus ne bouge pas, le rapport s'ecrit quand meme.** La couche 3
        # a montre que la clause de l'AC 6 « les N muettes vont au reliquat »
        # n'etait ni implementee ni testee : cette pile sortait avant le tri,
        # donc aucun `tri.json`, donc l'operateur savait que la passe avait
        # echoue mais pas **quelles** feuilles avaient resiste -- au moment
        # precis ou il en a le plus besoin, puisque tout a rate.
        #
        # Le geste est deliberement **additif** : meme message, meme code de
        # sortie, meme chemin d'ecriture ensuite. L'AC 2bis exige que ce chemin
        # reste inchange, et il l'est sur tout ce qui est observable -- un
        # fichier de rapport en plus, rien d'autre. Sans identite de projet on
        # ne trie pas (le tri la exige pour dire ce qui est hors perimetre) : on
        # le dit au journal plutot que d'inventer une identite.
        identite = _identite_du_projet_courant(project_dir, pages, logger)
        if identite is None:
            logger.info(
                "Pile sans planche d'images et sans identite de projet "
                "connue: aucun rapport de tri n'est ecrit (le tri exige "
                "l'identite du projet pour dire ce qui est hors perimetre). "
                "Le refus ci-dessous nomme la feuille en cause.")
        else:
            partition_du_refus = scan_sorting.trier_les_pages(
                pages, project_id_courant=identite)
            _ecrire_le_rapport_de_tri(
                project_dir, report, logger, partition_du_refus,
                profils_crees=(), project_id=identite)
        return _ecrire_le_lot_detecte(
            project_dir, logger, args, report, detection_complete,
            payloads_identifies, overwrite,
            dpi_geometrie=args.dpi, dpi_manifest=args.dpi)

    project_id = _identite_du_projet_courant(project_dir, pages, logger)
    if project_id is None:
        print(
            "Erreur: le tri par QR a besoin de l'identifiant du projet courant "
            "pour dire quelle feuille est hors perimetre. Ce projet n'a pas "
            "encore de manifest et cette passe n'en designe pas un seul. "
            "Scannez d'abord un lot d'un seul projet, ou passez --lot-slug "
            "pour promettre que cette pile est un lot unique.",
            file=sys.stderr)
        return 1

    partition = scan_sorting.trier_les_pages(pages, project_id_courant=project_id)

    if not partition.lots:
        # Rien a ranger: tout ce qui a ete lu est hors perimetre ou au reliquat.
        # Aucune ecriture de lot, et le rapport dit ou chercher.
        _journaliser_le_tri(logger, partition)
        chemin = _ecrire_le_rapport_de_tri(
            project_dir, report, logger, partition, (), project_id)
        print(
            f"scan termine: {len(report.pages)} page(s) ingeree(s) dans "
            f"{report.scans_dir}, aucune rangee sous un lot "
            f"({len(partition.reliquat)} au reliquat, "
            f"{len(partition.hors_perimetre)} hors perimetre). Manifest "
            f"inchange. Rapport de tri: {chemin}"
        )
        return 0

    pages_par_localisateur = {
        scan_sorting.Localisateur(page.locator_source, page.locator_page_index): page
        for page in pages
    }
    profils, echecs = _consigner_les_pages_de_calibration_du_vrac(
        project_dir, logger, args, report, detection_complete, partition)
    if echecs:
        partition = scan_sorting.avec_entrees_de_reliquat(partition, echecs)

    codes: list[int] = []
    for lot in partition.lots:
        pages_du_lot = _pages_du_lot(partition, lot, pages_par_localisateur)
        detection_du_lot = scan_detection.build_lot_report(
            pages_du_lot,
            ingest_slug=report.ingest_slug,
            scan_dpi=scan_dpi,
            ingest_declared_dpi=report.declared_dpi,
            ingested_count=len(pages_du_lot),
        )
        for code in detection_du_lot.warnings:
            logger.warning("Avertissement de detection (lot %s): %s",
                           lot.lot_id, code)
        payloads = tuple(
            page.payload for page in pages_du_lot if page.payload is not None)
        codes.append(_ecrire_le_lot_detecte(
            project_dir, logger, args, report, detection_du_lot, payloads,
            overwrite, dpi_geometrie=args.dpi, dpi_manifest=args.dpi))

    _journaliser_le_tri(logger, partition)
    chemin_du_rapport = _ecrire_le_rapport_de_tri(
        project_dir, report, logger, partition, profils, project_id)
    print(
        f"Tri par QR: {len(partition.lots)} lot(s) range(s), "
        f"{len(profils)} profil(s) de calibration consigne(s), "
        f"{len(partition.reliquat)} page(s) au reliquat, "
        f"{len(partition.hors_perimetre)} hors perimetre. "
        f"Rapport de tri: {chemin_du_rapport}"
    )
    return _code_agrege_du_vrac(codes)


def _code_agrege_du_vrac(codes) -> int:
    """Le code d'une passe de vrac, qui a ecrit **plusieurs** lots (AC 9).

    Trois rangs, du plus grave au moins grave: un refus l'emporte sur un succes
    partiel, qui l'emporte sur le succes. Sans ce rang intermediaire, un vrac
    dont un seul lot est a moitie en mires retomberait sur `1` -- « refuse,
    rien n'est ecrit » --, et l'operateur relancerait une passe la ou il doit
    rescanner une feuille.

    Le rang du refus est **volontairement large**: tout code qui n'est ni le
    succes ni le succes partiel y tombe, ce qui reproduit exactement le
    `1 if any(code != 0 ...)` d'avant sur toute valeur que la table des codes
    de sortie pourrait rendre demain.
    """
    codes = tuple(codes)
    if any(code not in (scan_write.CODE_SUCCES, scan_write.CODE_SUCCES_PARTIEL)
           for code in codes):
        return scan_write.CODE_ERREUR
    if any(code == scan_write.CODE_SUCCES_PARTIEL for code in codes):
        return scan_write.CODE_SUCCES_PARTIEL
    return scan_write.CODE_SUCCES


def _manifeste_du_projet_si_present(project_dir) -> dict | None:
    """Le `project.json` du projet, ou `None` s'il n'existe pas encore.

    Volontairement TOLERANT : `scan` s'execute sur des projets dont le
    manifeste n'est pas encore ecrit, et la seule chose qu'on y lit ici est la
    ligne d'eau des versions de scan -- une information dont l'absence signifie
    « aucune version employee », pas « projet invalide ».
    """
    chemin = Path(project_dir) / extraction_manifest.MANIFEST_FILENAME
    if not chemin.is_file():
        return None
    try:
        document = json.loads(chemin.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    return document if isinstance(document, dict) else None


def scan_command(args):
    """Ingerer un lot de planches scannees, ecrire ses frames et son manifest.

    Quatre etapes, chacune propriete d'une story et **appelee** ici, jamais
    reecrite: ingestion (5.1), detection geometrique (5.2), recadrage (5.3) et
    ecriture des frames (5.6), puis persistance au manifest (5.7).

    Ordre non negociable (EPIC5-ARB-34): tout ce qui peut se juger avant
    d'ecrire se juge avant d'ecrire. `check_scan_conflicts` s'intercale donc
    entre le recadrage -- qui ne touche pas au disque -- et l'ecriture des
    frames, la ou un refus est encore recuperable.

    Un lot dont aucune planche n'a livre son QR s'arrete apres la detection:
    il n'y a alors ni frame a ecrire -- le timecode vient du payload de sa
    propre page -- ni manifest a declarer. La commande le dit et rend `0`:
    l'ingestion, elle, a bien eu lieu et son rapport est ecrit.

    Codes de sortie ajoutes par `AR2` (story 5.25, revue du 2026-08-23): `130`
    sur interruption clavier, aucune trace Python -- chaque fichier ecrit par
    cette commande l'est par remplacement atomique (`os.replace`), donc aucun
    n'est laisse dans un etat partiel, mais plusieurs ecritures distinctes se
    succedent et l'interruption peut tomber entre deux d'entre elles; `1` sur
    `OSError` (disque plein, dossier non inscriptible), message actionnable
    via `_handle_poc_failure`, jamais une trace nue. Modele repris des quatre
    autres commandes ecrivantes (`extract`, `encode`, `makepdf`, `previz`).
    """
    project_dir = Path(args.project)
    # Creation du layout et ouverture du journal **avant** le `try`: un projet
    # dont le dossier `logs/` n'existe pas encore doit pouvoir journaliser son
    # propre echec (motif consigne en revue de 4.1).
    project_layout.ensure_project_layout(project_dir)
    logger = _configure_scan_logger(project_dir)
    logger.info("Demarrage de scan pour le projet %s", project_dir)

    try:
        try:
            report = scan_ingest.ingest_scan_lot(
                project_dir,
                args.scan,
                dpi=args.dpi,
                ingest_slug=args.lot_slug,
                nouvelle_version=getattr(args, "nouvelle_version", False),
                # Le manifeste porte la ligne d'eau des scans. Il est lu ICI et
                # non plus haut : `scan` s'execute aussi sur un projet dont le
                # `project.json` n'est pas encore ecrit, et exiger sa presence
                # ferait echouer une ingestion parfaitement legitime.
                manifest=_manifeste_du_projet_si_present(project_dir),
            )
        except scan_ingest.ScanIngestError as exc:
            logger.error("Echec de l'ingestion: %s", exc)
            print(f"Erreur: {exc}", file=sys.stderr)
            return 1

        # Le chemin se LIT du rapport, jamais reconstruit depuis le slug : les
        # deux divergent des qu'un fichier deja sous `<projet>/scans/` est
        # ingere en place (`EPIC7-ARB-88`, meme defaut que 5.1-C1-02).
        report_path = scan_ingest.ecrire_le_rapport(project_dir, report)

        logger.info(
            "%d page(s) ingeree(s) dans %s a %d dpi (slug d'ingestion: %s)",
            len(report.pages),
            report.scans_dir,
            report.declared_dpi,
            report.ingest_slug,
        )
        for code in report.warnings:
            logger.warning("Avertissement d'ingestion: %s", code)
        for name in report.skipped_files:
            logger.warning("Fichier illisible saute: %s", name)
        logger.info("Rapport d'ingestion ecrit: %s", report_path)

        overwrite = bool(getattr(args, "overwrite", False))
        try:
            # **Le tri s'insere ICI, avant `_reconcile_lot`** (story 5.24,
            # `EPIC7-ARB-63`). La detection est fendue en deux moities: la
            # moitie amont (`detect_pages`) lit les pages une par une et ne
            # refuse aucun melange, la moitie aval (`build_lot_report`)
            # reconcilie **une** pile homogene. Le chemin d'un lot promis --
            # `--lot-slug` passe -- appelle la composition des deux
            # (`detect_lot_pages`), donc son comportement est strictement
            # inchange, `LotIdentityError` comprise.
            scan_dpi, pages_detectees = scan_detection.detect_pages(
                project_dir, report, dpi=args.dpi)
        except scan_detection.ScanDetectionError as exc:
            logger.error("Echec de la detection: %s", exc)
            print(f"Erreur: {exc}", file=sys.stderr)
            return 1

        if _le_vrac_est_demande(args):
            # L'operateur n'a rien promis: le **tri par QR** decide
            # (`EPIC5-ARB-106`, AC 2bis). Aucun drapeau neuf ne le declenche.
            return _scanner_le_vrac(
                project_dir, logger, args, report, overwrite, scan_dpi,
                pages_detectees)

        # Regime `--lot-slug`: l'operateur **promet** « cette pile est un seul
        # lot ». La promesse est verifiee, et une pile mixte ou multi-lots reste
        # **refusee** -- comportement d'aujourd'hui, inchange.
        try:
            detection = scan_detection.build_lot_report(
                pages_detectees,
                ingest_slug=report.ingest_slug,
                scan_dpi=scan_dpi,
                ingest_declared_dpi=report.declared_dpi,
                ingested_count=len(report.pages),
            )
        except scan_detection.ScanDetectionError as exc:
            logger.error("Echec de la detection: %s", exc)
            print(f"Erreur: {exc}", file=sys.stderr)
            return 1

        for code in detection.warnings:
            logger.warning("Avertissement de detection: %s", code)
        # **Le motif de chaque refus de page est dit a l'operateur.** Il etait jusqu'ici
        # ecrit dans le rapport de detection et **jamais journalise**: une feuille refusee
        # pour son payload -- une page de calibration d'un tirage anterieur a la story 5.23,
        # refusee sans defaut de relecture par `EPIC5-ARB-90` -- disparaissait donc en
        # silence, et l'operateur ne lisait que la consequence (« aucune page de calibration
        # lue dans ce lot », ou « aucune identifiee ») sur une feuille qu'il avait bel et
        # bien posee sur la vitre. Le motif porte deja la phrase actionnable
        # (`io.payload.validate_payload` nomme la reimpression); il ne manquait que de
        # sortir.
        for page in detection.pages:
            if page.refusal_reason:
                logger.warning(
                    "Feuille refusee (rang de lecture %s, %s): %s",
                    page.read_rank, page.locator_source, page.refusal_reason)
        identified = [page for page in detection.pages if page.payload is not None]
        if not identified:
            logger.warning(
                "Aucune planche n'a livre son QR: ni frame ni manifest ne sont "
                "ecrits. L'ingestion, elle, a eu lieu."
            )
            print(
                f"scan termine: {len(report.pages)} page(s) ingeree(s) dans "
                f"{report.scans_dir}, aucune identifiee. Manifest inchange."
            )
            return 0

        payloads = tuple(page.payload for page in identified)
        # **La pile de pages de calibration seules est acceptee, pas refusee**
        # (`EPIC5-ARB-92`). Elle levait `REFUS_PILE_SANS_PLANCHE` plus bas, a
        # `check_scan_conflicts`, avec un message qui nommait pourtant le bon geste: c'etait
        # refuser le regime nominal du livrable de cette story, dont l'objet est justement de
        # rendre la page de calibration autonome de tout rush, lot, cadence et projet.
        # L'operateur est desormais **invite** a basculer en mode calibration.
        #
        # La question est posee **ici** et pas au refus, pour deux raisons de fond. La pile
        # est deja entierement connue -- les payloads sont lus --, donc rien n'oblige a faire
        # d'abord tout le travail d'un scan de lot pour decouvrir ensuite qu'il n'y avait pas
        # de lot; et la bascule doit passer par le meme ajustement que `calibrate`, ce qui
        # serait impossible apres qu'une correction a deja ete ajustee sur cette meme page
        # par le chemin du scan.
        #
        # Le predicat vient de `reconstruction`, qui **possede** la partition: c'est
        # litteralement la condition sous laquelle le refus tombe, jamais une seconde lecture
        # ecrite ici. Une pile mixte -- page de calibration **et** planches d'images -- rend
        # `False` et reste refusee (`EPIC5-ARB-86`, deux passes separees, question reportee a
        # la story de vrac); une pile de planches seules aussi, et aucune question n'y est
        # posee.
        #
        # Un `N` explicite ne bascule pas et ne court-circuite rien: la commande poursuit son
        # chemin de scan de lot et retombe sur `REFUS_PILE_SANS_PLANCHE`, qui nomme deja la
        # feuille en cause et le geste.
        #
        # **Les feuilles muettes comptent**, et c'est la condition 0 du predicat: une pile
        # de N planches a QR illisible plus une page de calibration lue n'est pas une pile
        # de calibration seule. Le cardinal est calcule ici, sur le rapport de detection,
        # parce que c'est le seul etage qui connait l'ecart entre ce qui a ete pose sur la
        # vitre et ce qui a livre son identite.
        if _bascule_en_calibration_demandee(
                payloads, logger,
                planches_muettes=len(detection.pages) - len(identified)):
            return _consigner_le_profil_de_chaine(
                project_dir, report, detection, args, logger)
        return _ecrire_le_lot_detecte(
            project_dir, logger, args, report, detection, payloads, overwrite,
            # Sur le chemin historique, les deux DPI sont le meme `--dpi`
            # declare par l'operateur (AC 1: sur un document de detection, ils
            # peuvent legitimement diverger et sont lus dans le document).
            dpi_geometrie=args.dpi, dpi_manifest=args.dpi)
    except KeyboardInterrupt:
        # AR2 (revue du 2026-08-23): seule des cinq commandes ecrivantes a ne pas
        # garder ce modele -- mesure au baseline, aucun `except KeyboardInterrupt`
        # ni `except OSError` entre `cli.py:1488` et `cli.py:2023`. Le motif est
        # celui de makepdf (`cli.py:3308`): l'ecriture des frames et celle du
        # manifest sont chacune basculees par `os.replace`, donc aucune des deux
        # ne peut laisser d'etat partiel visible -- mais plusieurs ecritures
        # atomiques distinctes se succedent dans cette commande (ingest.json,
        # frames, manifest, entree de profil designe), et l'interruption peut
        # tomber entre deux d'entre elles.
        print(
            "\nInterruption clavier: scan arrete. Chaque fichier ecrit (ingest.json, "
            "frames, manifest project.json) l'est par remplacement atomique: "
            "aucun d'entre eux ne peut rester dans un etat partiel. Relire "
            "logs/scan.log et project.json pour savoir jusqu'ou la commande "
            "est allee avant l'interruption."
        )
        return 130
    except OSError as exc:
        # Disque plein, projet en lecture seule, dossier `scans/`, `frames-scannees/`
        # ou `logs/` non inscriptible: memes pannes ordinaires que celles deja
        # traitees pour `extract`, `makepdf` et `encode` (revue du 2026-08-05).
        return _handle_poc_failure(
            logger,
            OSError(
                f"Erreur d'acces disque pendant scan: {exc}. Verifier l'espace "
                "disponible et les droits d'ecriture sur le dossier projet."
            ),
            1,
        )
    finally:
        _close_logger_handlers(logger)


def scan_write_command(args):
    """Ecrire frames et manifest depuis un document de detection persiste (5.26).

    Le second temps du scan en deux temps (FR6 + FR7): `scan detect` a produit
    un document `detected` (5.25), eventuellement dans un autre processus, un
    autre jour; cette commande le consomme **tel quel** -- rien n'est
    re-detecte, rien n'est re-ingere, aucun QR n'est relu.

    **Elle est un ENVELOPPEUR depuis la story 11.6 (lot B,
    `EPIC11-ARB-129`)**: la sequence entiere -- lecture du document, cinq refus
    nommes, condensat des octets de chaque source, annonce de completude,
    adaptateurs, refus du document a zero page identifiee, puis la moitie aval
    -- vit dans `scan_write.ecrire_depuis_le_document`. C'est le meme geste que
    la story 7.3 a fait pour la moitie AMONT (`scan_detect_command` /
    `run_scan_detect`) et que la 11.4b a fait pour la moitie AVAL: **corps
    deplace, jamais reecrit**. Ce qui reste ici est ce qui appartient a un
    terminal, et rien d'autre: la lecture de l'objet `args`, le `print` de
    l'annonce de completude, la traduction des exceptions du coeur en messages
    imprimes, les gardes `AR2` et le code de sortie.

    Ce que ce deplacement ferme, et c'est la raison de la story: le temps 2
    n'avait **aucun point d'entree de coeur**, si bien qu'une interface --
    qui a interdiction d'importer `cli.py` (`EPIC11-ARB-67`) -- aurait redige
    une **troisieme** lecture de document apres les deux de `gui/`.

    L'ordre des gardes (`EPIC5-ARB-34`, FR7) a voyage avec le corps et est
    mesure a l'arrivee: « un refus qui arrive apres une destruction n'est pas
    un refus ».

    Codes de sortie: `0` succes, `1` refus ou echec,
    `scan_write.CODE_SUCCES_PARTIEL` quand le lot ecrit n'est pas celui qui
    etait promis, `130` interruption clavier (`AR2`, gardes en derniere
    position, modele `scan_command`).
    """
    project_dir = Path(args.project)
    project_layout.ensure_project_layout(project_dir)
    logger = _configure_scan_logger(project_dir)
    logger.info("Demarrage de scan-write pour le projet %s", project_dir)

    try:
        try:
            issue = scan_write.ecrire_depuis_le_document(
                project_dir, Path(args.detection),
                overwrite=bool(getattr(args, "overwrite", False)),
                # L'annonce de completude est **rendue** par le coeur et
                # imprimee ici: une phrase de terminal n'est pas un fait. Le
                # rappel est ce qui garde l'ordre des lignes intact -- elle
                # sort avant la premiere frame, comme avant l'extraction.
                annoncer_la_completude=print,
                **_options_d_ecriture_du_terminal(args, project_dir, logger))
        except Exception as exc:
            code = _refus_du_coeur_a_l_ecriture(exc)
            if code is None:
                # Ce que la table ne nomme pas remonte: un bug de programmation
                # ne sort pas deguise en refus metier, et l'`OSError` va se
                # faire reformuler par la garde AR2 ci-dessous.
                raise
            return code
        return _conclure_l_ecriture(logger, issue)
    except KeyboardInterrupt:
        # AR2 (AC 6): meme modele que `scan_command`. Chaque fichier ecrit par
        # la moitie aval l'est par remplacement atomique (`os.replace`), donc
        # aucun ne peut rester dans un etat partiel -- mais plusieurs
        # ecritures atomiques distinctes se succedent (frames, manifest,
        # entree de profil designe) et l'interruption peut tomber entre deux.
        # Le document de detection, lui, n'est jamais touche par cette
        # commande.
        print(
            "\nInterruption clavier: scan-write arrete. Chaque fichier ecrit "
            "(frames, manifest project.json) l'est par remplacement "
            "atomique: aucun ne peut rester dans un etat partiel, mais "
            "l'interruption peut tomber entre deux ecritures. Relire "
            "logs/scan.log et project.json pour savoir jusqu'ou la commande "
            "est allee. Le document de detection, lui, est intact."
        )
        return 130
    except OSError as exc:
        return _handle_poc_failure(
            logger,
            OSError(
                f"Erreur d'acces disque pendant scan-write: {exc}. Verifier "
                "l'espace disponible et les droits d'ecriture sur le dossier "
                "projet."
            ),
            1,
        )
    finally:
        _close_logger_handlers(logger)



def _configure_default_profile_logger(project_dir: Path) -> logging.Logger:
    """Logger de la commande de profil par defaut, dont elle est proprietaire.

    Journal **distinct** de celui de `scan`, meme motif que partout ailleurs ici: poser
    le profil par defaut est un geste separe, fait a un autre moment que les scans qui
    s'en servent. Le melanger a `scan.log` rendrait illisible la question qui se pose
    quand un lot sort corrige de travers -- « quel profil ce projet a-t-il, et qui l'a
    pose ».
    """
    logger = logging.getLogger(
        f"mixed_media_utility.default_profile.{project_dir.resolve()}")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    log_path = project_dir / project_layout.LOGS_DIRNAME / "calibration-profile.log"
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console_handler)

    return logger


def set_default_profile_command(args):
    """Poser le profil de calibration **par defaut** d'un projet. Story 5.23, AC 12.

    `EPIC5-ARB-83`, decision 2: « un profil par defaut, au projet, evite de le repeter a
    chaque scan. **Commande dediee, geste explicite et separe -- jamais un effet de bord
    d'un scan.** » La separation est ce qui rend le defaut lisible: un scan qui poserait
    le defaut au passage ferait qu'un `--profil` tape une fois pour essayer resterait
    ensuite en vigueur sans que personne l'ait voulu, et le lot suivant sortirait
    corrige par un profil que son operateur n'a pas designe -- la meme classe de defaut
    que la derivation automatique, par une autre porte.

    Le profil designe est **verse au projet** (fichier + entree autoportante au
    manifest), et il peut venir de n'importe ou: **aucun refus lie au projet**
    (`EPIC5-ARB-82`).
    """
    project_dir = Path(args.project)
    project_layout.ensure_project_layout(project_dir)
    logger = _configure_default_profile_logger(project_dir)
    manifest_path = project_dir / extraction_manifest.MANIFEST_FILENAME
    if not manifest_path.is_file():
        # Ce refus ne porte **pas** sur la provenance du profil -- c'est la cible qui
        # n'est pas un projet. Le distinguo compte: un refus lie au projet du *profil*
        # est precisement ce que l'AC interdit.
        message = (
            f"Aucun manifest de projet dans {project_dir} ({manifest_path} absent): il "
            "n'y a pas de projet ou poser un profil par defaut. Lancez d'abord une "
            "extraction ou un scan sur ce dossier.")
        logger.error("%s", message)
        print(f"Erreur: {message}", file=sys.stderr)
        return 1
    try:
        document, chemin = profile_designation.import_designated_profile(
            project_dir, Path(args.profil), as_default=True,
            confirm_overwrite=_confirmation_d_ecrasement_de_profil())
    except (profile_designation.ProfileDesignationError, ExtractionPersistenceError,
            ValidationError, OSError) as exc:
        logger.error("%s", exc)
        print(f"Erreur: {exc}", file=sys.stderr)
        return 1
    finally:
        _close_logger_handlers(logger)

    logger.info(
        "Profil par defaut du projet pose: %s (chaine '%s', forme %s). Fichier du "
        "projet: %s. Les scans sans %s l'utiliseront.",
        args.profil, document["chain_id"], document["correction_form_id"], chemin,
        PROFILE_FLAG)
    print(
        f"Profil par defaut pose pour {project_dir}: chaine '{document['chain_id']}' "
        f"(forme {document['correction_form_id']}), consigne dans {chemin}.")
    return 0


def _configure_relink_logger(project_dir: Path) -> logging.Logger:
    """Logger de la commande `relink`, dont elle est proprietaire.

    Journal distinct des autres commandes (meme motif que
    `_configure_default_profile_logger`): retrouver un rush deplace est un
    geste separe, fait a un autre moment que l'extraction ou le scan.
    """
    logger = logging.getLogger(f"mixed_media_utility.relink.{project_dir.resolve()}")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    log_path = project_dir / project_layout.LOGS_DIRNAME / "relink.log"
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console_handler)

    return logger


def project_remove_command(args):
    """Supprimer proprement un lot ou un rush d'un projet (story 5.29).

    **La troisieme operation d'`EPIC11-ARB-89`, enfin atteignable.** Le
    mecanisme (`project_maintenance.remove_project_element`) etait ecrit et
    teste, mais aucune commande ne l'appelait : l'operateur restait devant le
    `git rm -r` a la main qui a detruit des frames non commitees le
    2026-08-27. Or l'arbitrage dit que sans la suppression, le versionnage
    n'est qu'une fuite -- une version de lot 4K a 12 im/s pese plus de 2 Go.

    **Apercu par defaut, jamais de suppression implicite.** Sans
    `--confirmer`, la commande n'ecrit rien : elle liste a plat ce qui serait
    supprime. C'est le mode `dry_run=True` du coeur, expose tel quel.

    **Le classement par nature a ete retire** (`EPIC11-ARB-199`, Egan le
    2026-09-03 : « le suivi par git n'est pas un sujet [...] il faut supprimer
    cette ligne ET cette logique du coeur »). L'apercu distinguait pointeur
    LFS, fichier local suivi par git et donnees non suivies, et concluait par
    un avertissement sur les fichiers qu'aucune sauvegarde ne rendrait. Depuis
    que les projets ne vivent plus dans un depot, tout fichier tombait dans la
    derniere categorie par construction : l'avertissement se declenchait
    TOUJOURS, alors que sa promesse ecrite etait « il n'apparait que quand
    c'est vrai ». Un avertissement qui ne discrimine plus rien n'avertit plus
    de rien.

    **Deux consentements empiles pour le dernier lot** (AC 11) :
    `--confirmer` ne suffit pas a vider un projet de son dernier lot ou de son
    dernier rush ; `--confirmer-dernier-lot` est exige en plus. Un seul
    drapeau qui couvrirait les deux ferait de la garde une formalite.

    Codes de sortie : `0` succes (apercu comme suppression) ; `1` refus
    (element inconnu, dernier lot sans confirmation, manifeste illisible,
    chemin sortant du dossier projet) ; `130` interruption clavier.
    """
    # `project_inventory` est importe ICI, a cote de `project_maintenance` et
    # pour la meme raison : c'est le seul appelant, et l'import differe evite
    # d'alourdir le demarrage de la CLI entiere. Il porte la TABLE des libelles
    # publiee (AC 1.3), lue plus bas plutot que recopiee.
    from . import project_inventory, project_maintenance

    try:
        rapport = project_maintenance.remove_project_element(
            Path(args.project),
            lot_id=args.lot,
            rush_id=args.rush,
            dry_run=not args.confirmer,
            confirmation_dernier_lot=args.confirmer_dernier_lot,
            avec_scans=args.avec_scans,
            planche=args.planche,
            liberer_le_rang=args.liberer_le_rang,
            master=args.master,
            profile=args.profile,
            resolution=args.resolution,
            scan=args.scan,
            lot_scanne=args.lot_scanne,
            frames_extraites=args.frames_extraites,
            version=args.version,
        )
    except project_maintenance.ProjectMaintenanceError as exc:
        print(f"Erreur: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrompu: aucune suppression n'a eu lieu.", file=sys.stderr)
        return 130
    except OSError as exc:
        print(f"Erreur: acces au projet impossible: {exc}", file=sys.stderr)
        return 1

    # Liste PLATE, dans l'ordre ou le coeur a construit la liste de fichiers
    # (`EPIC11-ARB-199`). L'entete est inchange : le cardinal et les chemins
    # restent lisibles, seule la classification par nature disparait.
    total = len(rapport.fichiers_a_supprimer)
    entete = "Apercu" if rapport.dry_run else "Supprime"
    print(f"{entete}: element {rapport.cible!r}, {total} fichier(s)")
    for chemin in rapport.fichiers_a_supprimer:
        print(f"    {chemin}")

    # Les annexes que la filiation designe mais qui ne sont PAS la. Benin le
    # plus souvent (lot jamais imprime, jamais encode) -- mais le PDF de
    # planches se retrouve par RECALCUL de son nom, si bien qu'un fichier
    # renomme a la main resterait sur le disque en silence. Le dire.
    # Le dossier de SCAN est nomme meme quand il n'est pas supprime: sans
    # cela, le consentement `--avec-scans` serait demande a l'aveugle.
    # TOUS les dossiers sont nommes, pas seulement le premier
    # (`EPIC11-ARB-109`): un lot rescanne depuis deux slugs en a deux, et n'en
    # nommer qu'un ferait consentir a une suppression dont l'operateur ne voit
    # pas la moitie.
    if rapport.dossiers_de_scan:
        nombre = len(rapport.dossiers_de_scan)
        pluriel = "s" if nombre > 1 else ""
        if rapport.scan_inclus:
            print(f"  Le{pluriel} {nombre} dossier{pluriel} de scan "
                  f"suivant{pluriel} {'sont' if nombre > 1 else 'est'} INCLUS:")
        else:
            print(
                f"  Note: le{pluriel} {nombre} dossier{pluriel} de scan "
                f"suivant{pluriel} {'sont' if nombre > 1 else 'est'} lie{pluriel} a "
                "cet element mais n'est PAS supprime. Il porte des planches "
                "papier numerisees -- les refaire demande de retrouver les "
                "feuilles et de repasser au scanner, la ou frames, masters et "
                "planches se refabriquent par calcul. Relancer avec "
                "--avec-scans pour l'inclure."
            )
        for dossier in rapport.dossiers_de_scan:
            print(f"    {dossier}")

    if rapport.fichiers_attendus_absents and getattr(args, "planche", False):
        # Cas DELIE, et il faut le nommer plutot que de le ranger avec les
        # absences ordinaires: l'entree part, le fichier reste quelque part.
        # **Ce bloc affirmait « le rang redevient disponible »** alors que le
        # bloc du rang, quelques lignes plus bas, disait « le rang reste
        # CONSOMME » -- deux phrases contradictoires sur le meme rang dans la
        # meme sortie (trouve en revue, couche 3). Le texte date d'avant
        # `EPIC11-ARB-92` et n'avait pas ete repris. Le deliement porte sur
        # l'ENTREE ; le sort du rang se dit une seule fois, plus bas.
        print(
            f"  Le fichier n'est pas a l'emplacement declare: son entree est "
            "DELIEE. Le fichier lui-meme (renomme ou deplace) occupe toujours "
            "le disque -- l'outil ne peut pas le reconnaitre, il ne le "
            "supprimera pas."
        )
        for chemin in rapport.fichiers_attendus_absents:
            print(f"    attendu ici: {chemin}")
    elif rapport.fichiers_attendus_absents:
        print(
            f"  Note: {len(rapport.fichiers_attendus_absents)} sortie(s) attendue(s) "
            "par filiation sont absentes du disque (jamais produites, deja "
            "supprimees, ou renommees a la main -- dans ce dernier cas elles "
            "resteront):"
        )
        for chemin in rapport.fichiers_attendus_absents:
            print(f"    {chemin}")

    # LE CHOIX DU RANG (`EPIC11-ARB-92`), pose seulement quand il se pose :
    # un tirage qui n'est pas le dernier a date n'ouvre aucun choix, son rang
    # est consomme.
    # Depuis `EPIC11-ARB-108` le choix se pose sur les CINQ objets versionnables,
    # pas sur les seuls tirages: `--lot` seul ouvre le meme choix. Le mot qui
    # nomme l'objet suit la cible.
    if getattr(args, "lot", None) is not None:
        # Le singulier ET le pluriel : « les jeu de framess posterieurs » est
        # ce que produisait un simple `objet + "s"` (trouve en revue, couche 1).
        #
        # **LES MOTS SONT LUS, PLUS REDIGES** (revue 11.14, couche 3, finding
        # `F2` ; AC 1.3, « chaque surface qui affiche une nature la LIT de cette
        # table »). Cet ecran-ci est celui ou la divergence etait deja
        # constatee : le coeur rendait « element 'L (lot scanne v2)' » et ces
        # quatre lignes repondaient « les jeux de frames scannees posterieurs »
        # -- deux mots pour un objet, dans la MEME sortie. `EPIC11-ARB-223`
        # tranche : « lot scanne », partout. Un libelle DERIVE de la table
        # suit le renommage tout seul ; un libelle recopie ne le suit jamais,
        # et c'est le mode de panne que l'AC 1.3 nomme.
        #
        # **`Q5` (planche / tirage) est FERMEE depuis `EPIC11-ARB-224`**, et
        # ce litteral avec elle. Egan, verbatim : « "--tirage" n'est pas un mot
        # de vocabulaire. C'est "planche". » Tant que l'option disait un mot et
        # la nature publiee un autre, les lier aurait tranche `Q5` en silence ;
        # elle est tranchee, donc le mot se LIT desormais de la table comme les
        # trois autres. Un litteral laisse ici remettrait deux mots pour un
        # objet dans le meme ecran -- le finding `F2`, exactement.
        objet, objets = project_inventory.libelles_de_nature(
            project_inventory.NATURE_LOT)
        for drapeau, nature in (
            ("planche", project_inventory.NATURE_PLANCHE),
            ("master", project_inventory.NATURE_MASTER),
            ("scan", project_inventory.NATURE_SCAN),
            # `--lot-scanne` vise le CONTENANT versionne -- un lot scanne --,
            # pas son contenu : c'est ce que le coeur nomme dans la meme
            # sortie (`_famille_du_lot_scanne`).
            ("lot_scanne", project_inventory.NATURE_LOT_SCANNE),
            # La cinquieme cible fine. Le mot se LIT de la table comme les
            # quatre autres (AC 1.3) : « jeu de frames extraites » recopie ici
            # serait le finding `F2` de la revue 11.14, deux mots pour un objet
            # dans la meme sortie.
            ("frames_extraites", project_inventory.NATURE_FRAMES_EXTRAITES),
        ):
            # **La TRUTHINESS, et non plus `is not None`** (`EPIC11-ARB-224`) :
            # trois de ces quatre cibles sont desormais des drapeaux nus, dont
            # la valeur au repos est `False` et non `None`. Un test `is not
            # None` les aurait crues toutes donnees, et le mot de la premiere
            # -- « planche » -- serait sorti pour les quatre.
            if not getattr(args, drapeau, None):
                continue
            objet, objets = project_inventory.libelles_de_nature(nature)
            break
        rang_vise = rapport.rang_vise
        if not rapport.rang_independant:
            # **Le seul objet de cette commande qui n'a pas de rang propre.**
            # Sans cette branche, la sortie retombait sur « le rang reste
            # CONSOMME: un {objet} posterieur existe » -- une phrase fausse de
            # bout en bout ici, puisqu'aucun objet posterieur n'existe et
            # qu'aucun rang n'est en jeu. « Aucun cas muet » ne veut pas dire
            # « une phrase quelconque » : il vaut mieux dire ce qui est.
            print(
                f"  Aucun rang propre pour: {objet}. Le dossier porte le rang "
                "du lot, qui reste declare -- ce retrait n'en consomme ni n'en "
                "rend aucun."
            )
        elif rapport.rang_libere and rapport.rangs_liberables:
            rendus = ", ".join(str(r) for r in rapport.rangs_liberables)
            print(f"  Rang(s) RENDU(S): {rendus}. Le prochain {objet} les reprendra.")
        elif rapport.rang_libere:
            # **Jamais une liste vide presentee comme un rendu** (revue, couches
            # 1 et 2). Rendre jusqu'a l'origine ne rend aucun rang de VERSION:
            # le prochain objet est l'origine, qui ne porte aucun fragment.
            print(
                f"  Rang(s) RENDU(S) jusqu'a l'ORIGINE: le prochain {objet} ne "
                "portera aucun fragment de version."
            )
        elif rapport.objet_en_queue and rapport.rangs_liberables:
            rendus = ", ".join(str(r) for r in rapport.rangs_liberables)
            suivant = max(rapport.rangs_liberables)
            print(
                f"  Ce {objet} est le DERNIER a date. Son rang reste CONSOMME par "
                f"defaut: le prochain {objet} sera le v{suivant + 1}. Pour rendre "
                f"le(s) rang(s) {rendus} -- le prochain {objet} serait alors le "
                f"v{min(rapport.rangs_liberables)} -- relancer avec "
                "--liberer-le-rang."
            )
        elif not rapport.objet_en_queue:
            print(
                f"  Le rang {rang_vise} reste CONSOMME: un {objet} posterieur "
                "existe, et deux versions ne peuvent pas porter le meme numero. "
                f"Il redeviendra liberable quand les {objets} posterieurs auront "
                "ete retires."
            )
        else:
            # **Aucun cas muet** (revue, couche 2, M4). Les trois branches
            # pouvaient etre fausses ensemble -- notamment sur une ligne d'eau
            # incoherente -- et la commande ne disait alors RIEN du rang.
            print(
                f"  Ce {objet} etait le DERNIER a date et son rang n'ouvre aucune "
                "liberation: la famille repart de l'origine."
            )

    if rapport.dry_run:
        print("Aucune ecriture. Relancer avec --confirmer pour supprimer.")
        return 0

    if rapport.fichiers_non_supprimes:
        # Le manifeste est deja a jour (ordre impose): le dire, plutot que de
        # laisser croire a un succes alors que des fichiers restent.
        print(
            f"Erreur: {len(rapport.fichiers_non_supprimes)} fichier(s) n'ont pas pu "
            "etre supprimes (droits, fichier verrouille). Le manifeste est a jour, "
            "mais ces fichiers occupent toujours le disque:",
            file=sys.stderr,
        )
        for chemin in rapport.fichiers_non_supprimes:
            print(f"    {chemin}", file=sys.stderr)
        return 1

    # Le compte rendu doit dire CE QUI a eu lieu. « retire du manifeste et du
    # disque » sur un element dont aucun fichier n'etait present est un petit
    # mensonge, et il porte sur le point exact que l'operateur verifie.
    if total:
        print(f"Element {rapport.cible!r} retire du manifeste et du disque.")
    else:
        print(
            f"Element {rapport.cible!r} retire du manifeste. Aucun fichier n'etait "
            "present a supprimer."
        )
    return 0


def _configure_add_rush_logger(project_dir: Path) -> logging.Logger:
    """Journal de `project add-rush`, dont elle est proprietaire.

    Meme forme que `_configure_extract_logger` -- un fichier sous `logs/` plus
    la console --, avec **une** difference, et elle est une AC : le fichier
    n'est attache que si `logs/` **existe deja**. Cette commande ne cree
    aucune arborescence.

    Deux motifs, et le second est mesure :

    * la revue du 2026-08-05 a paye ce defaut sur `extract` : l'arborescence
      projet et le journal etaient crees **avant** la validation, si bien que
      `--project /` creait reellement des dossiers a la racine du systeme avant
      d'echouer. Ici la validation vit **dans le coeur** -- c'est le refus
      `projet_sans_manifeste` -- et l'enveloppe n'a pas le droit de la rejouer
      pour savoir quand ouvrir un journal ;
    * l'AC 2.4 mesure qu'un rush deja declare **ne modifie rien** : inodes,
      `st_mtime_ns` et temoin depose dans le dossier projet. Un `logs/` cree au
      passage serait une modification, sur le chemin meme ou la story promet
      qu'il n'y en a aucune.

    La console, elle, est toujours branchee : un projet sans `logs/` reste
    lisible, il ne devient pas muet.
    """
    logger = logging.getLogger(
        f"mixed_media_utility.add_rush.{project_dir.resolve()}")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    dossier_de_journal = project_dir / project_layout.LOGS_DIRNAME
    if dossier_de_journal.is_dir():
        file_handler = logging.FileHandler(
            dossier_de_journal / "add-rush.log", encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console_handler)

    return logger


def _imprimer_le_refus_de_declaration(exc: BaseException, designation: str) -> None:
    """Imprimer un refus du coeur : son motif, le fichier designe, ses issues.

    Trois lignes, et aucune n'est redigee ici :

    * le **motif**, `str(exc)` verbatim et prefixe -- la redaction est celle du
      coeur, lue par la CLI comme par la TUI, donc les deux disent la meme
      chose sans qu'aucune ne recopie l'autre ;
    * le **fichier designe**, tel que l'operateur l'a tape (`EPIC11-ARB-153` :
      « les ecrans affichent le vrai nom du fichier, jamais l'identifiant
      derive »). Il est imprime sur **tous** les refus et non sur le seul ou il
      manque : une exception par motif serait une regle redigee dans
      l'enveloppe ;
    * les **issues**, lues sur l'exception -- qui les tient elle-meme de
      `declaration_de_rush.ISSUES_PAR_MOTIF`. Elles sont imprimees **toutes**
      et dans l'ordre : la table n'en porte qu'une par motif aujourd'hui
      (`EPIC11-ARB-147`, refus sec), et un `issues[0]` y serait invisible.

    `getattr` plutot qu'un attribut direct : les entrees non metier de la table
    du coeur (`OSError`, `ValidationError`) n'en portent aucune, et une issue
    fabriquee pour elles serait une phrase inventee par l'enveloppe.
    """
    print(f"Erreur: {exc}", file=sys.stderr)
    print(f"Fichier designe: {designation}", file=sys.stderr)
    for issue in getattr(exc, "issues", ()):
        print(f"Issue: {issue}", file=sys.stderr)


def _compte_rendu_d_add_rush(declaration, designation: str) -> str:
    """Le compte rendu d'une declaration qui a abouti, mot pour mot.

    La redaction vit **ici** et pas dans le coeur : une phrase de terminal
    n'est pas un fait, et `declarer_un_rush` ne rend que des faits
    (`DeclarationDeRush`). Le fichier est nomme tel que l'operateur l'a designe
    (`EPIC11-ARB-153`), l'identifiant derive etant dit a part -- il sert a
    retrouver le rush dans le manifeste, il ne le designe pas a l'ecran.

    La seconde phrase existe parce qu'`EPIC11-ARB-9` produit un **succes** et
    non un refus : deux rushes homonymes venus de deux dossiers differents sont
    deux rushes distincts, separes sans qu'aucune question soit posee. Le taire
    laisserait l'operateur devant un identifiant qu'il n'a pas demande.
    """
    lignes = [
        f"project add-rush termine: {designation} declare dans "
        f"{declaration.manifest_path}, sous l'identifiant {declaration.rush_id} "
        f"(cadence source {declaration.fps_source} im/s). Aucun lot n'a ete cree, "
        "aucune frame n'a ete ecrite."
    ]
    if declaration.homonymie_levee and declaration.separation_forcee:
        # `EPIC11-ARB-232` : l'operateur a tranche, pas l'outil. Le dire est la
        # moitie de l'arbitrage -- les quatre criteres coincidaient, et un
        # compte rendu qui parlerait de « rush homonyme » laisserait croire que
        # la machine a su les distinguer.
        lignes.append(
            f"Les quatre criteres d'identite coincidaient avec le rush "
            f"{declaration.rush_id_derive} deja declare, et --force-distinct a "
            f"ete pose: ce rush est declare SEPAREMENT sous l'identifiant "
            f"{declaration.rush_id}. Rien n'a ete ecrase."
        )
    elif declaration.homonymie_levee:
        lignes.append(
            f"Un rush homonyme etait deja declare et un critere technique les "
            f"separe: celui-ci vient du dossier "
            f"{declaration.source_parent}, il porte donc l'identifiant "
            f"{declaration.rush_id} et non {declaration.rush_id_derive}. Rien "
            "n'a ete ecrase."
        )
    return "\n".join(lignes)


def project_add_rush_command(args):
    """Declarer un rush dans un projet ouvert, **sans l'extraire** (story 11.4e).

    `EPIC11-ARB-131`, verbatim d'Egan : « C'est un peu absurde de ne pouvoir
    extraire que ce qui est deja la et qui a donc deja ete extrait. » Le point
    d'entree de coeur est `declaration_de_rush.declarer_un_rush` (lot A) ; ce
    qui suit est **une surface de plus, jamais un appelant qui en fait plus**.

    Ce que cette fonction fait, et c'est tout ce qui appartient a un terminal :
    ouvrir un journal, imprimer ce que le coeur a juge, rendre un code de
    sortie. Elle ne derive aucun `rush_id`, ne leve aucune homonymie, ne
    qualifie aucune source et n'ecrit aucun manifeste -- chacun de ces gestes
    existe **une seule fois**, dans le coeur, et une seconde redaction
    divergerait sans que rien ne le dise (`EPIC11-ARB-146`).

    **Les codes de sortie ne sont pas ecrits ici.** Ils sont lus dans
    `declaration_de_rush.CODES_DE_SORTIE`, publiee par le lot A pour la raison
    exacte qui a fait naitre `extraction.CODES_DE_SORTIE` (`EPIC11-ARB-75`) et
    `scan_detect.REFUS_DU_COEUR` : la TUI doit rendre le **meme** code et a
    interdiction d'importer ce module (`EPIC11-ARB-67`). Le corps de cette
    fonction ne porte aucun litteral entier, et un banc le mesure.

    Deux entrees echappent a la table, et ce sont les deux memes que sur
    `extract` :

    * `KeyboardInterrupt`, qui derive de `BaseException` -- donc invisible au
      `except Exception` -- et porte son propre message, sans prefixe
      `Erreur:` ni trace. La garde `AR2` reste chez l'appelant, comme pour
      `scan_write.CODES_DE_SORTIE` : le code, lui, reste celui de la chaine et
      se lit sur `extraction.CODE_INTERRUPTION` ;
    * le filet `OSError`, seule entree dont le message est reformule -- disque
      plein ou projet en lecture seule sont des pannes ordinaires, et « No
      space left on device » nu n'est pas actionnable (revue du 2026-08-05).

    Ce que la table ne nomme pas **remonte** : un bug de programmation ne sort
    pas deguise en refus metier.

    **Aucune arborescence n'est creee**, et c'est une AC (2.4) : sur un rush
    deja declare, rien du dossier projet ne bouge -- ni le `project.json`, ni
    son contenu, ni un `logs/` qui serait apparu au passage.
    """
    project_dir = Path(args.project)
    logger = _configure_add_rush_logger(project_dir)
    logger.info("Demarrage de project add-rush pour le projet %s", project_dir)

    try:
        declaration = declaration_de_rush.declarer_un_rush(
            project_dir=project_dir,
            video_path=Path(args.video),
            logger=logger,
            # `EPIC11-ARB-232` : la seconde issue du refus de conflit, portee
            # au coeur telle quelle. L'enveloppe ne l'interprete pas.
            force_distinct=args.force_distinct,
        )
    except KeyboardInterrupt:
        print(
            "\nInterruption clavier: declaration arretee. Le manifest est "
            "inchange -- l'ecriture est atomique et arrive en dernier, apres "
            "toutes les gardes."
        )
        return extraction.CODE_INTERRUPTION
    except Exception as exc:
        correspondance = declaration_de_rush.correspondance_de_sortie(exc)
        if correspondance is None:
            raise
        classe, code = correspondance
        if classe is OSError:
            exc = OSError(
                f"Erreur d'acces disque pendant la declaration: {exc}. "
                "Verifier l'espace disponible et les droits d'ecriture sur le "
                "dossier projet."
            )
        logger.error("%s", exc)
        _imprimer_le_refus_de_declaration(exc, args.video)
        return code
    finally:
        _close_logger_handlers(logger)

    print(_compte_rendu_d_add_rush(declaration, args.video))
    return declaration_de_rush.CODE_SUCCES


def relink_command(args):
    """Remplacer le chemin du rush source d'un projet (story 2.8, AC 2).

    Gabarit repris de `set_default_profile_command`: commande dediee et
    separee, geste de premiere classe (`EPIC7-ARB-41`: « pouvoir le
    remplacer facilement »). Deux designations mutuellement exclusives,
    posees par argparse (`--video` designation manuelle, `--chercher`
    recherche recursive, `EPIC7-ARB-34`).

    Aucun `--force`: un critere d'identite verifiable qui echoue refuse le
    relink sans recours (Decisions d'ecriture de la story 2.8, point 3).

    Codes de sortie: `0` succes; `1` refus d'identite ou d'entree
    (`relink.RelinkError`, manifest absent, ecriture invalide); `2` reserve
    par argparse (aucune des deux designations, ou les deux a la fois);
    `130` interruption clavier (`AR2`, revue de 2.8: meme motif que `scan` et
    `scan detect`, story 5.25 -- corps existant enveloppe, jamais reordonne).
    """
    project_dir = Path(args.project)
    project_layout.ensure_project_layout(project_dir)
    logger = _configure_relink_logger(project_dir)
    try:
        manifest_path = project_dir / extraction_manifest.MANIFEST_FILENAME
        if not manifest_path.is_file():
            message = (
                f"Aucun manifest de projet dans {project_dir} ({manifest_path} absent): il "
                "n'y a pas de rush a relinker. Lancez d'abord une extraction sur ce dossier."
            )
            logger.error("%s", message)
            print(f"Erreur: {message}", file=sys.stderr)
            return 1

        manifest = _load_existing_manifest(manifest_path)
        try:
            rush_id = relink.resoudre_rush_id(manifest or {}, args.rush)
            reference = relink.charger_reference(manifest or {}, rush_id)
            if args.video is not None:
                avertissements = relink.verifier_designation_manuelle(
                    Path(args.video), reference=reference)
                for avertissement in avertissements:
                    logger.warning("%s", avertissement)
                    print(f"Avertissement: {avertissement}")
                chemin_resolu = str(Path(args.video).resolve())
            else:
                trouve = relink.rechercher_candidat(Path(args.chercher), reference=reference)
                chemin_resolu = str(trouve.resolve())
            nouveau_manifest = relink.appliquer_relink(manifest or {}, rush_id, chemin_resolu)
            _atomic_write(manifest_path, nouveau_manifest)
        except relink.RelinkError as exc:
            logger.error("%s", exc)
            print(f"Erreur: {exc}", file=sys.stderr)
            return 1
        except ExtractionPersistenceError as exc:
            return _handle_poc_failure(logger, exc, 1)

        logger.info(
            "Relink reussi: rush_id=%s, nouveau source_path=%s", rush_id, chemin_resolu)
        print(f"Relink reussi pour rush_id={rush_id!r}: {chemin_resolu}")
        return 0
    except KeyboardInterrupt:
        # AR2 (revue de 2.8, meme motif que `scan_command`/`scan_detect_command`,
        # story 5.25): aucune trace Python sur Ctrl+C. Le seul fichier ecrit par
        # cette commande (project.json) l'est par remplacement atomique
        # (`_atomic_write`), donc il ne peut jamais rester dans un etat partiel --
        # soit l'ancien manifest est toujours en place, soit le nouveau l'est.
        print(
            "\nInterruption clavier: relink arrete. Le manifest de projet est "
            "soit inchange, soit ecrit en entier (remplacement atomique): aucun "
            "etat partiel possible."
        )
        return 130
    except OSError as exc:
        # Disque plein, projet en lecture seule, dossier `logs/` non
        # inscriptible: memes pannes ordinaires que celles deja traitees pour
        # `extract`, `scan`, `makepdf` et `encode`.
        return _handle_poc_failure(
            logger,
            OSError(
                f"Erreur d'acces disque pendant relink: {exc}. Verifier l'espace "
                "disponible et les droits d'ecriture sur le dossier projet."
            ),
            1,
        )
    finally:
        _close_logger_handlers(logger)


def _demander_a_l_operateur(invite: str):
    """Poser une question a l'operateur, ou rendre `None` **hors terminal**.

    Story 5.23, AC 8quater. Le point dur de cette AC n'est pas la question, c'est ce
    qui se passe quand personne n'est la pour y repondre. `scan calibrate` tourne aussi
    sous script, en CI et dans 4800 tests: un `input()` inconditionnel y leve `EOFError`
    (pytest substitue une entree qui refuse la lecture) ou bloque indefiniment (un
    `cron` avec un tube ouvert). La question n'est donc posee **que** si l'entree
    standard est un terminal, et une fin de fichier vaut « pas de reponse » -- jamais
    une erreur de commande.
    """
    try:
        interactif = sys.stdin is not None and sys.stdin.isatty()
    except (AttributeError, ValueError):
        # Entree standard fermee ou substituee par un objet sans `isatty`: hors
        # terminal par construction.
        return None
    if not interactif:
        return None
    try:
        return input(invite)
    except EOFError:
        return None


def _nom_et_commentaire_du_profil(args, chain_id: str) -> tuple:
    """L'etiquette et le commentaire du profil, par option ou par question.

    Story 5.23, AC 8quater, mandat d'Egan: « On stockera bien les infos officielles mais
    on laissera l'utilisateur nommer les choses. »

    **Ce qui a ete tranche pour le mode non interactif**, et pourquoi. Trois regimes,
    un seul comportement par regime:

    * l'option est passee -> elle repond, et **aucune question n'est posee** meme sur un
      terminal. Un drapeau explicite qui declencherait quand meme une invite rendrait
      la commande impossible a scripter a moitie;
    * l'option est absente et l'entree standard est un terminal -> la question est
      posee. C'est le geste que decrit le mandat;
    * l'option est absente et l'entree standard **n'est pas** un terminal -> defaut
      silencieux, sans invite et sans refus. Le profil prend alors le nom de son
      `chain_id`, c'est-a-dire exactement ce que 5.22 ecrivait: un script existant ne
      change ni de comportement ni de nom de fichier.

    Le refus a ete ecarte pour ce troisieme regime: exiger `--nom` hors terminal ferait
    de l'etiquette une **obligation** la ou le mandat en fait un confort, et casserait
    tout appel existant de `scan calibrate` -- alors que le nom par defaut, lui, est
    parfaitement utilisable puisque c'est celui d'avant.
    """
    nom = getattr(args, 'nom', None)
    if nom is None:
        nom = _demander_a_l_operateur(
            f"Nom du profil de calibration [defaut: {chain_id}] : ")
    commentaire = getattr(args, 'commentaire', None)
    if commentaire is None:
        commentaire = _demander_a_l_operateur("Commentaire (facultatif) : ")
    return (nom or "").strip(), (commentaire or "").strip()


def scan_calibrate_command(args):
    """Calibrer une chaine de scan depuis une page de calibration (story 5.22).

    Consigner la correction de la chaine dans `versions/calibration/`, une fois par
    chaine (AC 1, 2, 4): la page de calibration d'une planche scannee sur cette chaine
    est ajustee **une seule fois**, et les lots de la chaine reutilisent le profil sans
    re-ajustement.

    **Elle est un ENVELOPPEUR depuis la story 11.6 (lot B,
    `EPIC11-ARB-129`)**: ingestion, detection, derive de l'identite de chaine,
    ajustement et ecriture du profil vivent dans le module de coeur
    `scan_calibrate`, appele **en processus** par cette commande comme par une
    interface -- la TUI sert `calibrate` depuis le menu d'atelier
    (`EPIC11-ARB-28`) et a interdiction d'importer `cli.py`
    (`EPIC11-ARB-67`). Ce qui reste ici est ce qui appartient a un terminal:
    la lecture de l'objet `args`, les deux invites de nommage, la traduction
    des refus du coeur en messages imprimes, le compte rendu et le code de
    sortie.

    **Le nom du fichier n'est plus `<chain_id>.json`** depuis l'AC 8quater de la story
    5.23: c'est le slug de l'etiquette donnee par l'operateur, et le `chain_id` sinon
    (`io.calibration_profile.write_profile`). Le dire ici, et dans l'aide du
    sous-parseur, n'est pas cosmetique -- un operateur envoye chercher un fichier qui
    porte un autre nom conclut que la commande n'a rien ecrit. Et « les lots de la
    chaine reutilisent » ne veut plus dire « automatiquement »: depuis
    `EPIC5-ARB-83` la reutilisation est un geste (`--profil`, ou le profil par defaut
    du projet), jamais un appariement de `chain_id`.

    Le geste est explicite: `calibrate` ajuste, et **rien d'autre ne calibre
    une chaine**. Un echec d'ajustement ou une page de calibration absente
    rend `1` sans ecrire de profil -- jamais un profil partiel ou un defaut
    invente, c'est le pendant, a l'echelle de la chaine, de la politique des
    plans `versions/` de 5.12 (le contenu existe ou il n'existe pas).

    L'identite de la chaine est **derivee** des parametres reels du scan, et rien ne la
    surcharge: le drapeau qui le permettait a ete retire par la story 5.23 (AC 13,
    `EPIC5-ARB-88`). Depuis `EPIC5-ARB-83`, l'operateur designe le profil lui-meme,
    donc le `chain_id` n'apparie plus rien -- il **nomme** ce que cette commande
    produit, et une derivation deterministe le nomme sans que deux saisies puissent
    diverger.
    """
    project_dir = Path(args.project)
    project_layout.ensure_project_layout(project_dir)
    logger = _configure_scan_logger(project_dir)
    logger.info("Demarrage de la calibration de chaine pour le projet %s", project_dir)

    try:
        try:
            consigne = scan_calibrate.calibrer_la_chaine(
                project_dir, args.scan, dpi=args.dpi, logger=logger,
                **_options_de_calibration_du_terminal(args))
        except Exception as exc:
            code = _refus_du_coeur_a_la_calibration(exc)
            if code is None:
                raise
            return code
        print(_compte_rendu_de_calibration(project_dir, consigne))
        _traiter_la_chaine_deja_calibree(project_dir, consigne, logger)
        return scan_calibrate.CODE_SUCCES
    finally:
        # Liaison du 2026-09-01. `main` a pose cette fermeture des handlers
        # (`a190fb0`) sur TOUTES les commandes ; le lot B de la 11.6 a, du meme
        # cote, vide le corps de celle-ci au profit de `scan_calibrate`. Les
        # deux tiennent, et le `finally` doit envelopper le corps DEPLACE :
        # laisse sur l'ancien corps, il serait parti avec lui, et le journal de
        # scan de cette commande resterait ouvert -- ce que la mesure de `main`
        # ferme precisement.
        _close_logger_handlers(logger)


def _options_de_calibration_du_terminal(args) -> dict:
    """Ce qu'un TERMINAL apporte a une passe de calibration, et rien d'autre.

    Story 11.6, lot B: les deux rappels sont lus **ici** parce que le coeur ne
    lit jamais `stdin` (`EPIC7-ARB-106`), et une seule fois parce qu'il y a
    desormais deux voies -- la sous-commande et la bascule de `scan`.
    """
    return dict(
        # L'invite de nommage est posee par le coeur **au moment ou elle
        # l'etait**: apres le dernier refus, jamais avant. Ce qui est cable ici
        # est la question, pas le moment.
        demander_le_nom_et_le_commentaire=(
            lambda chain_id: _nom_et_commentaire_du_profil(args, chain_id)),
        # La valeur passee est le predicat d'interactivite, jamais l'invite
        # nue: la passer nue ferait poser un `input()` sous `cron`
        # (`EPIC5-ARB-99`).
        confirmer_l_ecrasement=_confirmation_d_ecrasement_de_profil(),
    )


def _refus_du_coeur_a_la_calibration(exc: BaseException):
    """Imprimer un refus de `calibrate` et rendre son code, ou `None` si inconnu.

    Le motif est celui du coeur, prefixe et jamais reecrit. Le journal, lui,
    porte deja la phase: elle est ecrite par `scan_calibrate`, au moment ou le
    refus tombe.
    """
    code = scan_calibrate.code_de_sortie(exc)
    if code is None:
        return None
    print(f"Erreur: {exc}", file=sys.stderr)
    return code


#: L'avertissement d'`EPIC11-ARB-261` au terminal, **au singulier**.
PHRASE_CHAINE_DEJA_CALIBREE = (
    "Attention: la chaine '{chaine}' portait deja le profil '{autre}'. "
    "Cette passe vient donc d'en ecrire un SECOND, et l'ancien ne sera "
    "designe par personne."
)

#: La meme, **au pluriel** -- deux redactions et non une avec un `(s)`, comme
#: la TUI le fait deja pour le meme fait (`DESIGN.md` ecarte le pluriel
#: postiche). Le cas pluriel existe pour de vrai : deux libelles differents sur
#: la meme chaine avant que ce chemin n'existe, c'est-a-dire le regime des
#: projets d'aujourd'hui.
PHRASE_CHAINE_DEJA_CALIBREE_PLURIEL = (
    "Attention: la chaine '{chaine}' portait deja {cardinal} autres profils "
    "({autres}). Cette passe vient donc d'en ecrire un de PLUS, et les anciens "
    "ne seront designes par personne."
)

#: Les deux issues, dites en toutes lettres. Aucune n'est preselectionnee au
#: hasard : « garder les deux » est le defaut, parce que c'est celle qui
#: n'ecrit rien -- meme regle que la collision (`EPIC5-ARB-99`, « hors
#: terminal, le defaut est l'empreinte, jamais l'ecrasement »).
INVITE_CHAINE_DEJA_CALIBREE = (
    "Retirer le ou les anciens profils de cette chaine ? [y/N] "
    "(non = garder les deux, rien n'est retire)"
)

#: Ce qu'un script lit a la place de l'invite. Il n'y a **pas** de blocage sec
#: (`EPIC11-ARB-89`) : la passe a abouti, le profil neuf est ecrit, et la
#: seconde issue est nommee avec la commande qui la joue.
PHRASE_HORS_TERMINAL_CHAINE_DEJA_CALIBREE = (
    "Les deux profils sont conserves (aucun terminal pour trancher). Pour "
    "retirer l'ancien, supprimez son fichier, ou relancez cette commande "
    "depuis un terminal."
)

#: Ce qu'un OPERATEUR lit quand il a repondu non. Il sait deja comment
#: retirer l'ancien -- il vient de refuser --, donc la phrase ne le lui
#: reapprend pas.
PHRASE_CONSERVATION_DES_DEUX = "Les deux profils sont conserves."


def _phrase_de_la_chaine_deja_calibree(consigne) -> str:
    """L'avertissement, au singulier ou au pluriel selon ce qui a ete releve."""
    autres = list(consigne.autres_profils)
    if len(autres) == 1:
        return PHRASE_CHAINE_DEJA_CALIBREE.format(
            chaine=consigne.chain_id, autre=autres[0].name)
    return PHRASE_CHAINE_DEJA_CALIBREE_PLURIEL.format(
        chaine=consigne.chain_id, cardinal=len(autres),
        autres=", ".join(autre.name for autre in autres))


def _retrait_des_anciens_profils_demande(en_terminal: bool) -> bool:
    """Poser l'invite `y/N` d'`EPIC11-ARB-261`, **et seulement en terminal**.

    Le predicat est **passe** plutot que relu (:func:`_stdin_is_interactive`,
    le meme que les deux autres invites de ce module) : la seule reponse sure a « je ne sais pas
    si quelqu'un est la » est de ne rien retirer. Le defaut est donc « garder
    les deux », qui est l'issue qui n'ecrit rien -- et on ne boucle pas sur une
    reponse incomprise, une invite qui insiste etant un cran de plus vers
    l'invite qui bloque.
    """
    if not en_terminal:
        return False
    print(INVITE_CHAINE_DEJA_CALIBREE, end=" ")
    try:
        reponse = input().strip().lower()
    except EOFError:
        reponse = ""
    return reponse.startswith(("y", "o"))


def _traiter_la_chaine_deja_calibree(project_dir: Path, consigne,
                                     logger) -> None:
    """La moitie TERMINAL d'`EPIC11-ARB-261`, et elle manquait entierement.

    Le balayage inverse etait ecrit, la TUI le servait, et
    `mmu scan ... calibrate` ecrivait un second profil **sans un mot** : c'est
    le retour de terrain d'Egan, ferme a l'ecran et laisse ouvert au terminal.

    **Deux issues, jamais un blocage sec** (`EPIC11-ARB-89`). L'avertissement
    sort dans tous les cas -- c'est lui qui ferme le « sans un mot » --, et le
    retrait ne se declenche que sur un `y` frappe a la main. Hors terminal,
    aucune destruction et une phrase qui nomme la seconde issue.

    **L'ecran monte APRES l'ecriture, ici comme la-bas** : le profil mesure est
    a l'abri quoi qu'il arrive, c'est le sort de l'ANCIEN qui se tranche.

    Ne rend rien et ne change **aucun** code de sortie : la passe a abouti, et
    ce qui se joue ici est un menage propose, pas une condition de succes.
    """
    autres = list(consigne.autres_profils)
    if not autres:
        return
    print(_phrase_de_la_chaine_deja_calibree(consigne), file=sys.stderr)
    # Le predicat se lit **une fois** : deux lectures pourraient diverger entre
    # l'invite et la phrase de repli, et la phrase serait alors celle de l'autre
    # regime -- un script qui lirait « les deux profils sont conserves » sans
    # savoir comment retirer l'ancien.
    en_terminal = _stdin_is_interactive()
    if not _retrait_des_anciens_profils_demande(en_terminal):
        print(PHRASE_CONSERVATION_DES_DEUX if en_terminal
              else PHRASE_HORS_TERMINAL_CHAINE_DEJA_CALIBREE, file=sys.stderr)
        return
    retrait = scan_calibrate.retirer_les_profils_de_la_chaine(
        project_dir, autres,
        chemin_garde=Path(consigne.profile_path),
        document_garde=consigne.document)
    for chemin, motif in retrait.resistants:
        # Le motif systeme voyage **verbatim** : « Permission denied » dit a
        # l'operateur quoi faire, « retrait impossible » ne dit rien. Et ce qui
        # n'a PAS eu lieu se dit avant ce qui a eu lieu, sans quoi il lit
        # « 2 profils retires » et rate le troisieme qui est reste.
        print(f"Profil non retire ({chemin.name}): {motif}", file=sys.stderr)
    print(f"{len(retrait.retires)} ancien(s) profil(s) de cette chaine "
          f"retire(s).", file=sys.stderr)
    if retrait.defaut_suivi:
        print("Le profil par defaut du projet suit le remplacement.",
              file=sys.stderr)
    logger.info(
        "EPIC11-ARB-261: %d ancien(s) profil(s) retire(s), %d resistant(s), "
        "defaut suivi: %s.",
        len(retrait.retires), len(retrait.resistants), retrait.defaut_suivi)


def _compte_rendu_de_calibration(project_dir: Path, consigne) -> str:
    """Le compte rendu imprime d'une calibration qui a abouti, mot pour mot.

    La redaction vit ICI et pas dans le coeur: une phrase de terminal n'est pas
    un fait, et le coeur ne rend que des faits (:class:`ProfilDeChaineConsigne`,
    meme partage que `ScanDetectOutcome`).
    """
    lot_correction = consigne.lot_correction
    # **Dire si la divergence brute sera mesurable, et le dire ici** (correction du
    # 2026-08-18): une page sans bandeau de temoins produit un profil parfaitement
    # utilisable dont la divergence brute restera non mesuree a chaque scan ulterieur, et
    # le seul moment ou l'operateur peut y remedier -- reimprimer la page de calibration
    # avec le bandeau -- est celui-ci. Un silence ici est un `raw_divergence` nul des mois
    # plus tard, sans que rien n'ait jamais dit pourquoi.
    temoins = (
        f"{len(lot_correction.witness_raw_bgr)} pastille(s) temoin mesuree(s) brutes y "
        "sont consignees: l'ecart brut a brut sera mesure sur les planches de cette "
        "chaine."
        if lot_correction.witness_raw_bgr else
        "Aucune pastille temoin n'a ete mesuree sur cette page (bandeau non imprime ou "
        "illisible): l'ecart brut a brut ne sera pas mesurable sur les planches de "
        "cette chaine."
    )
    # **Le geste suivant est nomme, parce qu'il n'est plus automatique** (story 5.23,
    # AC 12, `EPIC5-ARB-83`). Cette phrase disait « les lots de cette chaine la
    # reutiliseront », ce qui etait vrai tant que le scan appariait un profil par
    # `chain_id`. Depuis que l'operateur designe, elle est **fausse** -- et fausse de la
    # pire facon: elle promet un enchainement qui n'a pas lieu, si bien que le lot
    # suivant sort brut pendant que l'operateur croit sa chaine calibree. Le seul moment
    # ou il peut apprendre le geste est celui-ci, et le message porte le chemin exact
    # qu'il aura a designer.
    # **Le nom que l'operateur a donne est rendu, tel qu'il l'a ecrit** (AC 8quater):
    # c'est le seul moment ou il peut verifier que le fichier porte bien son nom plutot
    # que l'identite technique de sa chaine, et le chemin ci-dessous est celui qu'il
    # aura a designer.
    nomme = (f" Etiquette: '{consigne.etiquette}'." if consigne.etiquette else "")
    return (
        f"calibration ecrite pour la chaine '{consigne.chain_id}':{nomme} "
        f"correction de la page "
        f"{lot_correction.source_page_id} consignee dans {consigne.profile_path}. "
        f"{temoins} "
        f"Elle ne s'appliquera qu'aux scans qui la **designent**: passez "
        f"`{PROFILE_FLAG} {consigne.profile_path}` a chaque scan, ou posez-la une fois "
        f"pour toutes avec `{SET_DEFAULT_PROFILE_COMMAND} --project {project_dir} "
        f"{PROFILE_FLAG} {consigne.profile_path}`. Aucun profil n'est choisi "
        "automatiquement."
    )


def _consigner_le_profil_de_chaine(project_dir: Path, report, detection, args,
                                   logger, *, profils_ecrits: list | None = None) -> int:
    """Enveloppeur de `scan_calibrate.consigner_le_profil_de_chaine`.

    **Le corps a quitte cette fonction** (story 11.6, lot B, `EPIC11-ARB-129`):
    derive de l'identite de chaine, ajustement de la page, composition et
    ecriture du profil vivent desormais dans le module de coeur
    `scan_calibrate`, appele **en processus** par cette commande comme par une
    interface. Ce qui reste ici est ce qui appartient a un terminal: la lecture
    de l'objet `args`, les invites, la traduction des refus en messages
    imprimes, le compte rendu et le code de sortie. **Corps deplace, jamais
    reecrit** -- une seconde redaction ecrirait un jour un profil que l'autre
    voie n'ecrirait pas.

    `profils_ecrits`, ajoute par la story 5.24, est un **collecteur optionnel**:
    quand il est fourni, le chemin du profil reellement ecrit y est ajoute. Le
    vrac en a besoin parce que son rapport de tri doit **nommer** chaque profil
    cree par la passe (AC 10) -- et la valeur de retour de cette fonction est un
    code de sortie de CLI, qui ne peut pas la porter.

    Elle a **deux appelants** depuis `EPIC5-ARB-92`: la sous-commande explicite,
    et la bascule que `scan_command` propose a l'operateur quand sa pile ne
    porte que des pages de calibration. L'extraction est ce qui rend la bascule
    fidele: elle ne reimplemente rien, elle **appelle** ce que `calibrate` fait,
    si bien qu'aucune des deux voies ne peut ecrire un profil que l'autre
    n'ecrirait pas.

    Ce que l'extraction ne fait pas: re-ingerer ni re-detecter. La bascule est
    proposee apres l'ingestion et la detection de `scan`, qui sont exactement
    les memes gestes -- deleguer a `scan_calibrate_command` aurait copie une
    seconde fois le scan sur le disque, sous un autre slug quand `--lot-slug`
    est passe.
    """
    try:
        consigne = scan_calibrate.consigner_le_profil_de_chaine(
            project_dir, report, detection,
            dpi=args.dpi, scan_locator=args.scan, logger=logger,
            **_options_de_calibration_du_terminal(args))
    except Exception as exc:
        code = _refus_du_coeur_a_la_calibration(exc)
        if code is None:
            raise
        return code
    if profils_ecrits is not None:
        profils_ecrits.append(consigne.profile_path)
    print(_compte_rendu_de_calibration(project_dir, consigne))
    # **La bascule avertit comme la sous-commande** (`EPIC5-ARB-92` : « aucune
    # des deux voies ne peut ecrire un profil que l'autre n'ecrirait pas »).
    # Poser l'avertissement sur une seule des deux rouvrirait le defaut
    # d'`EPIC11-ARB-261` par l'autre porte, et par celle-la meme qu'Egan
    # emprunte -- un `scan` dont la pile ne porte qu'une mire.
    _traiter_la_chaine_deja_calibree(project_dir, consigne, logger)
    return scan_calibrate.CODE_SUCCES


def extract_command(args):
    """Produire un lot de frames TIFF deterministe depuis un rush (story 3.1).

    Codes de sortie, dont `extract` est proprietaire: ils ne sont plus ecrits
    ici. Depuis la story 11.4 (`EPIC11-ARB-75`), la table exception -> code de
    sortie vit dans `extraction.CODES_DE_SORTIE` et les cinq codes dans
    `extraction.CODE_*`, parce que la TUI a besoin des **memes** codes et a
    interdiction d'importer ce module. Cette fonction se contente de la lire;
    la pile d'`except` nommee qu'elle remplace est reproduite a l'identique,
    ordre compris, par la table elle-meme.

    Deux entrees restent traitees a part ici, et ce sont les deux seules dont
    l'appelant fait autre chose qu'imprimer l'exception:

    * `KeyboardInterrupt`, qui n'emprunte pas `_handle_poc_failure` -- aucun
      prefixe `Erreur:`, aucune trace Python -- et derive de `BaseException`,
      donc n'est pas attrapee par le `except Exception` ci-dessous;
    * le filet `OSError`, dont le message est reformule.

    Ce que la table ne nomme pas **remonte**: un bug de programmation ne sort
    pas deguise en refus metier.

    `main()` renvoie deja `2` quand aucune sous-commande n'est fournie: la
    valeur n'est donc pas surchargee d'un second sens ici.
    """
    project_dir = Path(args.project)
    if project_dir.exists() and not project_dir.is_dir():
        print(f"Erreur: Le chemin projet n'est pas un dossier: {project_dir}", file=sys.stderr)
        return extraction.CODE_ERREUR

    # Valider **avant** de creer quoi que ce soit: l'arborescence projet et le
    # journal etaient crees d'abord, donc `--project /` creait reellement des
    # dossiers a la racine du systeme avant d'echouer (revue du 2026-08-05).
    try:
        extraction.validate_extraction_inputs(project_dir, Path(args.video), args.fps)
    except extraction.ExtractionInputError as exc:
        print(f"Erreur: {exc}", file=sys.stderr)
        return extraction.code_de_sortie(exc)

    project_layout.ensure_project_layout(project_dir)
    logger = _configure_extract_logger(project_dir)
    logger.info("Demarrage de extract pour le projet %s", project_dir)

    try:
        outcome = extraction.run_extraction(
            project_dir=project_dir,
            video_path=Path(args.video),
            fps_target=args.fps,
            # Bornes passees telles quelles au noyau (story 3.7, AC 5): aucune
            # regle de bornage n'est reimplementee ici. Le noyau ne peut les
            # juger qu'une fois le cardinal reel de la source connu, donc apres
            # le probe -- valider ici sur une intuition de forme donnerait un
            # second jeu de messages, divergent du premier.
            source_in_timecode=args.in_timecode,
            source_out_timecode=args.out_timecode,
            overwrite=args.overwrite,
            nouvelle_version=args.nouvelle_version,
            ecrasement_conscient=args.ecrasement_conscient,
            consent_granted=args.yes,
            unknown_color_accepted=args.accept_unknown_color,
            logger=logger,
            in_stream=sys.stdin,
            out_stream=sys.stdout,
        )
    except KeyboardInterrupt:
        # Aucune trace Python sur Ctrl+C. `previz` traitait deja le cas
        # proprement quelques dizaines de lignes plus bas dans ce meme
        # fichier; `extract`, la commande qui ecrit, ne le faisait pas
        # (revue du 2026-08-05). Le lot partiel reste dans le dossier
        # temporaire cache, donc distinguable d'un lot complet, et aucun
        # manifest n'a ete ecrit.
        #
        # Attrapee a part parce qu'elle derive de `BaseException`: le
        # `except Exception` ci-dessous ne la verrait pas, et l'attraper avec
        # lui reviendrait a imprimer `Erreur:` sur un geste deliberement pose
        # par l'operateur.
        print(
            "\nInterruption clavier: extraction arretee. Aucun lot n'a ete "
            "declare, le manifest est inchange."
        )
        return extraction.CODE_INTERRUPTION
    except Exception as exc:
        # `EPIC11-ARB-75`: la pile d'`except` nommee qui vivait ici est
        # devenue `extraction.CODES_DE_SORTIE`, lue aussi par la TUI, qui a
        # interdiction d'importer ce module et doit rendre le meme code.
        # L'ordre de la table **est** celui des anciens `except`, et la
        # recherche rend la premiere entree qui correspond: le comportement
        # est identique, y compris quand deux entrees attraperaient la meme
        # exception.
        correspondance = extraction.correspondance_de_sortie(exc)
        if correspondance is None:
            # Ce que la table ne nomme pas n'a jamais ete attrape ici: un bug
            # de programmation remonte, il ne sort pas deguise en refus metier
            # avec un code d'erreur ordinaire.
            raise
        classe, code = correspondance
        if classe is OSError:
            # Disque plein, projet en lecture seule, `logs/` ou
            # `extract-frames/` non
            # inscriptible: des pannes ordinaires qui remontaient en trace
            # Python devant l'operateur (revue du 2026-08-05). C'est la seule
            # entree dont le message est reformule, et c'est pourquoi
            # l'appelant a besoin de savoir **quelle** entree a repondu, pas
            # seulement de son code.
            exc = OSError(
                f"Erreur d'acces disque pendant l'extraction: {exc}. "
                "Verifier l'espace disponible et les droits d'ecriture sur le "
                "dossier projet."
            )
        return _handle_poc_failure(logger, exc, code)
    finally:
        # `main` a pose cette fermeture des handlers (`a190fb0`) sur TOUTES les
        # commandes ; la vague 3 a remplace la pile d'`except` de cette
        # commande-ci par la table d'`EPIC11-ARB-75`. Les deux tiennent : la
        # table decide du CODE, le `finally` ferme le journal quoi qu'il
        # arrive. C'est le seul conflit reel de la liaison du coeur.
        _close_logger_handlers(logger)

    if not outcome.granted:
        print(outcome.message)
        return extraction.CODE_REFUS

    print(
        f"extract termine avec succes. {outcome.written_frame_count} frame(s) TIFF "
        f"{outcome.output_bit_depth} bits dans {outcome.frames_dir_relative} "
        f"(lot {outcome.lot_id})."
    )
    if not _print_extraction_verification(outcome):
        # ARB-7 (`decisions-2026-08-05.md`): un auto-controle negatif fait
        # echouer la commande. Les fichiers restent sur le disque -- les
        # effacer detruirait l'information de diagnostic -- mais le code de
        # sortie dit l'echec, et le message propose la reprise.
        return extraction.CODE_ERREUR
    return extraction.CODE_SUCCES


def _print_extraction_verification(outcome) -> None:
    """Afficher le rapport d'auto-controle produit juste apres l'ecriture.

    La persistance verifie le lot qu'elle vient d'ecrire (story 3.4, AC 15) et
    remonte son rapport, mais personne ne le lisait: un lot ampute de trois
    images sur quatorze etait ecrit, le manifest le declarait complet, le
    controle le detectait, et la commande se terminait par « extract termine
    avec succes ». C'est le mode de defaillance meme que l'AC 15 existe pour
    fermer (revue du 2026-08-05).

    Rend `True` si le lot est conforme. Depuis ARB-7
    (`decisions-2026-08-05.md`), un `False` fait echouer la commande: Egan a
    tranche qu'un lot connu incomplet ne doit pas sortir comme un succes.
    """
    persisted = getattr(outcome, "persisted", None)
    verification = getattr(persisted, "verification", None)
    if verification is None:
        return True

    if not verification.ok:
        print(
            "\nATTENTION: l'auto-controle du lot qui vient d'etre ecrit signale "
            "un probleme. Le lot est sur le disque mais il n'est PAS conforme a "
            "ce que le manifest declare."
        )
        for code in verification.findings:
            print(f"  - {code}")
        if verification.missing_frames:
            print(f"  frame(s) manquante(s): {len(verification.missing_frames)}")
        if verification.unexpected_files:
            print(f"  fichier(s) surnumeraire(s): {len(verification.unexpected_files)}")
        if verification.nonconforming_files:
            print(f"  fichier(s) au nom non conforme: {len(verification.nonconforming_files)}")
        print(
            "  Les fichiers sont conserves pour diagnostic. Pour reprendre: "
            "relancer la meme commande avec --overwrite, ou verifier le dossier "
            "de lot avant de le transmettre."
        )
        return False

    informational = [
        code
        for code in verification.findings
        if code in extraction_manifest.INFORMATIONAL_VERIFICATION_CODES
    ]
    if informational:
        print("Auto-controle: lot conforme, avec les reserves suivantes.")
        for code in informational:
            print(f"  - {code}")
    return True


def _configure_makepdf_logger(project_dir: Path) -> logging.Logger:
    """Logger de la commande `makepdf`: relais vers la recette du coeur.

    La recette elle-meme a emigre dans `makepdf.ouvrir_le_journal` (story 11.7,
    lot B) : une interface qui appelle le coeur doit obtenir **le meme** journal
    -- meme fichier, meme format, meme handler console -- sans avoir a importer
    `cli`, ce qui lui est interdit. Ce relais reste pour que les deux appelants
    de cette fonction dans ce fichier n'aient pas a la nommer autrement.
    """
    return makepdf_core.ouvrir_le_journal(project_dir)


def _configure_encode_logger(project_dir: Path) -> logging.Logger:
    """Logger de la commande `encode`: relais vers la recette du coeur.

    La recette elle-meme a emigre dans `encode_master.ouvrir_le_journal`
    (story 11.8, lot B1) : une interface qui appelle le coeur doit obtenir **le
    meme** journal -- meme fichier, meme format, meme absence de handler console
    -- sans avoir a importer `cli`, ce qui lui est interdit. Meme geste que
    `_configure_makepdf_logger` au lot B de la 11.7.
    """
    return encode_master.ouvrir_le_journal(project_dir)


#: `SIGTERM` recu pendant l'encodage. La classe a emigre dans
#: `encode_master.TerminaisonDemandee` avec la sequence qu'elle interrompt : la
#: TUI a le meme besoin et ne peut pas importer `cli`. Ce nom reste un **alias**,
#: pas une seconde classe -- deux classes distinctes feraient qu'un `except` de
#: l'un ne verrait pas l'autre, et le contrat `143` tomberait en silence d'un
#: cote sur deux.
_EncodeTerminated = encode_master.TerminaisonDemandee

#: Meme geste pour le contexte qui installe le gestionnaire : il voyage avec la
#: sequence qu'il protege, et ce nom en est l'alias.
_terminate_kills_the_encoder = encode_master.le_signal_tue_l_encodeur


def _encode_confirmation(consent_granted: bool, in_stream, out_stream) -> tuple[bool, str]:
    """Recueillir l'accord avant d'encoder, sur le motif de `extract` (3.3).

    Mode non interactif: **aucune** lecture de `in_stream` n'est tentee. Une
    commande en CI ne doit jamais se bloquer sur une entree qui ne viendra pas
    -- `input()` sur un `stdin` ouvert mais vide bloque indefiniment. Le drapeau
    de consentement force le mode non interactif, puisque c'est le canal
    d'acquittement qui est designe, pas la nature du terminal.
    """
    if consent_granted:
        return True, "Consentement d'encodage accorde par --yes."
    if not source_confirmation.detect_interactive(in_stream, out_stream):
        return False, (
            "Encodage non lance: consentement absent en mode non interactif. "
            "Passer --yes pour donner l'accord sans terminal interactif."
        )
    out_stream.write("Lancer l'encodage ? [o/N] ")
    out_stream.flush()
    try:
        raw = in_stream.readline()
    except (EOFError, KeyboardInterrupt, OSError, ValueError):
        return False, "Encodage non lance: saisie interrompue. Aucun fichier n'a ete ecrit."
    if str(raw).strip().lower() in ("o", "oui", "y", "yes"):
        return True, "Consentement d'encodage accorde."
    return False, "Encodage non lance. Aucun fichier n'a ete ecrit."


def _parse_cadence_source(value: str) -> str:
    """Type argparse de `--cadence-source`: decimal ou `'num/den'` (story 6.6).

    Transmise **telle quelle** (jamais convertie en `float` ici) a
    `encode.resolve_source_rate` -> `codec_profiles.exact_frame_rate`, qui
    accepte deja les deux formes. C'est deliberement le meme geste que la
    story 3.8 pour `--fps`: convertir en `float` avant de transmettre
    reintroduirait le piege qu'elle mesure -- `8.333333` (6 decimales) retombe
    sur une fraction proche mais **differente** de `25/3`, alors que la chaine
    `'25/3'` passee telle quelle est exacte par construction.

    **Renforce apres la revue en trois couches** (Edge Case Hunter, finding 5):
    `float`/`Fraction` acceptent syntaxiquement `"nan"`, `"inf"`, `"-25/3"`,
    que `codec_profiles.exact_frame_rate` refuse de toute facon -- mais
    plusieurs appels plus loin, sous un code moins precis
    (`CADENCE_DE_LOT_INEXPLOITABLE`) que le message specifique a `--cadence-source`
    qu'on peut rendre ici, a l'endroit ou l'erreur a reellement ete faite.
    """
    try:
        parsed = Fraction(value) if "/" in value else float(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise argparse.ArgumentTypeError(
            f"--cadence-source invalide: {value!r} (decimal, ex. 12.5, ou "
            f"'num/den', ex. 25/3, attendu): {exc}"
        ) from exc
    if isinstance(parsed, float) and (parsed != parsed or parsed in (float("inf"), float("-inf"))):
        raise argparse.ArgumentTypeError(
            f"--cadence-source invalide: {value!r} (doit etre fini)"
        )
    if parsed <= 0:
        raise argparse.ArgumentTypeError(
            f"--cadence-source invalide: {value!r} (doit etre strictement positif)"
        )
    return value


def encode_command(args):
    """Reconstruire un master video depuis les frames scannees d'un lot (6.1).

    **ENVELOPPE depuis la story 11.8, lot B1 (AC 2.1).** La sequence -- gardes
    d'ouverture, validation du manifest, decision, recapitulatif, consentement,
    balayage des residus, encodage sous le filet de `SIGTERM`, verification
    technique, bascule et declaration au manifest -- a ete **deplacee** dans
    `mixed_media_utility.encode_master`, sans etre reecrite. Ce qui reste ici est
    ce qu'une CLI possede en propre: la lecture d'`args`, le journal de la
    commande, les phrases imprimees et le code de sortie.

    Motif du deplacement: la TUI a interdiction d'importer `cli` (frontiere de
    la 11.4b), et l'atelier Exports n'avait donc **rien a appeler**. Meme geste
    qu'`EPIC11-ARB-129` pour le temps 2 du Scan, deja fait trois fois sur cette
    chaine (`scan_detect.run_scan_detect`, `scan_write.ecrire_depuis_le_document`,
    `makepdf.generer_les_planches_du_lot`).

    **La table exception -> code de sortie n'est plus ecrite ici**: elle est LUE
    dans `encode_master.CODES_DE_SORTIE`, sur le modele d'`extract`
    (`EPIC11-ARB-75`). Une exception **hors table** remonte comme avant, au lieu
    d'etre deguisee en refus metier.

    Codes de sortie, alignes sur le contrat d'`extract` sans en inventer:

    * `0` succes;
    * `1` **tout refus en amont**, sans qu'aucun fichier ait ete ecrit; echec en
      cours d'encodage, temporaire supprime et master precedent intact;
      verification technique en echec, fichier d'attente **conserve** pour
      diagnostic et master precedent intact (AC 13);
    * `2` prerequis externe absent -- ffmpeg sans l'encodeur du profil, ffprobe
      introuvable: la meme classe de panne que celle dont `extract` fait un `2`;
    * `3` refus de confirmation (motif de la story 3.3): rien n'a echoue,
      l'operateur a simplement dit non;
    * `130` interruption clavier, avec le dossier ou chercher le fichier
      d'attente laisse par la fabrique; `143` arret demande par signal.

    **Elle ecrit le manifest depuis la story 6.5**, et l'ancienne mention « cette
    commande n'ecrit pas le manifest » -- vraie tant que 6.1 etait seule livree
    (`EPIC6-ARB-4`) -- est amendee ici, exactement comme la story 5.11 a du
    amender la docstring de `makepdf`. Ce que 6.5 ajoute au contrat de sortie:

    * la persistance est appelee **apres** le retour d'`execute_plan`, donc
      apres son `os.replace`: le master porte alors son nom final;
    * son refus est un `1` **de plus**, d'une nature particuliere: le master est
      ecrit et **reste sur le disque** pour diagnostic, le `project.json`
      precedent est intact, et le message propose la reprise. C'est la
      transposition d'`ARB-7` d'`extract` et de l'AC 10 de la story 5.11. La
      capture est volontairement large -- `ExtractionPersistenceError`, racine de
      la hierarchie de la story 3.4 -- et non la seule
      `EncodePersistenceError`: la fenetre entre la decision et l'ecriture rend
      reellement `ExtractionPersistenceError` **nue** (un `project.json` tronque
      par un ecrivain concurrent), `LegacyManifestError` et `ManifestWriteError`,
      dont aucune n'est une `EncodePersistenceError`. Resserrer la capture
      rendrait une trace Python a l'operateur **apres** que la video a ete
      encodee; un test parametre pose des refus **reellement leves par ce
      chemin** pour l'interdire;
    * une **interruption clavier pendant la persistance** rend `130` avec son
      message, comme celle qui frappe pendant l'encodage. Sans cette capture,
      c'est le seul point du chemin `encode` qui rendait une trace Python nue,
      alors que la docstring annonce un contrat `130`. Le `project.json` reste
      intact -- `_atomic_write` deroule son `except BaseException` et ne laisse
      aucun temporaire --, mais le master, lui, est ecrit et non declare: c'est
      cela que le message doit dire;
    * **aucun controle de persistance n'est ajoute avant l'encodage**, et c'est
      une mesure. Les quatre refus que la persistance peut opposer sans dependre
      de l'encodage sont deja opposes en amont, **avant le moindre octet
      encode** -- mais pas tous par la meme garde, et l'enonce inverse a ete
      corrige en revue:

      - `lots[].state` hors vocabulaire, `schema_version` inconnue et manifest
        legacy sont refuses par le `validate_manifest` que le coeur appelle en
        tete de sa sequence, avant meme `plan_encode`;
      - un document **v2.0 authentique**, lui, **traverse** `validate_manifest`
        sans un mot (le schema v2.0 le declare valide, c'est son role); c'est
        `plan_encode` qui le refuse, faute d'`output_frames_dir` sur le lot
        (`DOSSIER_DE_LOT_NON_DECLARE`) -- un champ que le schema v2.0 ne connait
        pas. Ce que `validate_manifest` refuse en annoncant « 2.0 », c'est un
        document v2.1 **re-etiquete**, qui n'est pas le meme objet.

      Dans les deux cas rien n'est encode, et un second controle n'aurait ferme
      aucun chemin: il aurait double une garde tenue en donnant l'illusion d'en
      tenir une autre.
    """
    project_dir = Path(args.project)
    # Les deux gardes d'ouverture sont jouees ICI, avant le journal, parce
    # qu'elles le precedent dans le corps d'origine: `--project <inexistant>`
    # n'a jamais cree ni arborescence, ni `logs/encode.log`. Le coeur les rejoue
    # pour son propre compte -- une fonction de coeur ne fait pas confiance a son
    # appelant --, et les rejouer ne coute qu'un `is_dir` et un `is_file`.
    try:
        encode_master.refuser_l_ouverture_du_projet(project_dir)
    except encode_master.RefusDOuvertureDuProjet as exc:
        print(f"Erreur: {exc}", file=sys.stderr)
        return encode_master.CODE_ERREUR

    project_layout.ensure_project_layout(project_dir)
    logger = _configure_encode_logger(project_dir)
    logger.info("Demarrage de encode pour le projet %s", project_dir)

    # **Le journal se ferme a la fin de la COMMANDE, jamais au milieu**
    # (liaison du 2026-09-01). `main` avait pose ce `finally` sur le seul bloc
    # d'ENCODAGE (`a190fb0`), si bien que tout ce qui suivait -- « Master
    # ecrit », la declaration au manifest et ses constats -- partait dans des
    # handlers deja fermes : `logs/encode.log` s'arretait net apres le dernier
    # constat de la passe, et quatre bancs d'integration le mesuraient. Le
    # `finally` enveloppe donc le corps ENTIER, ce qui est aussi ce que
    # `a190fb0` voulait -- fermer les handlers de CHAQUE commande.
    try:
        try:
            master = encode_master.encoder_le_master_du_lot(
                project_dir,
                lot_id=args.lot,
                profile_id=args.profile,
                resolution=args.resolution,
                overwrite=args.overwrite,
                nouvelle_version=args.nouvelle_version,
                accept_incomplete=args.accept_incomplete_lot,
                cadence_source_override=args.cadence_source,
                logger=logger,
                annoncer_le_recapitulatif=print,
                confirmer_l_encodage=lambda: _encode_confirmation(
                    args.yes, sys.stdin, sys.stdout),
                annoncer_le_master=_print_encoded_master,
            )
        except encode_master.EncodageNonConsenti as exc:
            # Le message vient du rappel de consentement, verbatim: c'est lui
            # qui distingue les trois motifs de refus. Il est deja journalise
            # par le coeur, la ou le corps d'origine le journalisait.
            print(str(exc))
            return encode_master.CODE_REFUS
        except encode_master.EncodageInterrompu as exc:
            # Le message dit ce que la phase a laisse sur le disque, et seule la
            # sequence le sait: il est compose par elle et journalise par elle.
            print(str(exc))
            return exc.code_de_sortie
        except ExtractionPersistenceError as exc:
            # Le point final et le retour a la ligne ne sont pas cosmetiques: le
            # message enveloppe vient d'un module partage et se termine parfois par
            # un conseil generique herite de la story 3.4 (« repartir d'un dossier
            # projet vierge ») qui, **ici**, jetterait le projet. Sans separateur,
            # les deux phrases se collaient et le mauvais conseil precedait
            # immediatement le bon. La reprise ci-dessous prime, et le dit.
            #
            # Le chemin du master vient de l'**exception** (`master_path`, pose
            # par le coeur au moment de l'echec) et non d'une variable de cette
            # fonction: depuis le deplacement, l'enveloppe n'a jamais le
            # resultat en main sur ce chemin, et le recomposer serait re-deriver
            # une convention qu'`io.naming` possede.
            message = (
                f"{str(exc).rstrip().rstrip('.')}.\n"
                "  Le master est ecrit et conserve pour diagnostic: "
                f"{getattr(exc, 'master_path', None)}\n"
                f"  Le {extraction_manifest.MANIFEST_FILENAME} precedent est intact.\n"
                "  Reprise (elle prime sur tout conseil generique ci-dessus): "
                "corriger la cause nommee, puis relancer la meme commande avec "
                "--overwrite -- elle reencodera le master et le declarera. Le master "
                "present n'est pas declare tant que cela n'a pas eu lieu."
            )
            logger.error(message)
            print(f"Erreur: {message}", file=sys.stderr)
            return encode_master.CODE_ERREUR
        except Exception as exc:
            # La table est LUE, jamais retapee. Une exception qu'elle ne nomme
            # pas **remonte**: la deguiser en `1` ferait passer un defaut de
            # programmation pour un refus opposable a l'operateur.
            code = encode_master.code_de_sortie(exc)
            if code is None:
                raise
            return _handle_poc_failure(logger, exc, code)

        persisted = master.persisted
        print(
            f"Manifest mis a jour: {persisted.manifest_path} "
            f"(lots[{persisted.lot_id}].state={persisted.state_written}, master "
            f"{persisted.master_path})"
        )
        for code in persisted.findings:
            print(f"  Constat: {code}")
        return encode_master.CODE_SUCCES
    finally:
        _close_logger_handlers(logger)


def _print_encoded_master(result) -> None:
    """Dire ce que l'encodage vient d'ecrire, **avant** la declaration au manifest.

    Sa position est l'observable, pas un detail de mise en page: le corps
    d'origine imprimait ces quatre familles de lignes entre le retour
    d'`execute_plan` et l'appel a `persist_encode`. Une declaration qui echoue
    ensuite laisse donc « Master ecrit » a l'ecran -- et c'est exactement ce
    qu'il faut, puisque le fichier, lui, est bien la.

    C'est le rappel `annoncer_le_master` du point d'entree de coeur: le module
    n'imprime rien lui-meme, il dit **quand** il y a quelque chose a dire.
    """
    print(f"Master ecrit: {result.outcome.output_path}")
    print(
        f"  {result.outcome.frame_count} frames a {result.outcome.frame_rate} im/s, "
        f"{result.outcome.encoded_size[0]}x{result.outcome.encoded_size[1]}, "
        f"{result.outcome.pix_fmt}"
    )
    print(
        "  Description d'encodage: "
        f"{json.dumps(result.manifest_fields, sort_keys=True)}"
    )
    for code in result.findings:
        print(f"  Constat: {code}")


def _print_pdf_persistence(logger, persisted) -> None:
    """Dire ce qui a ete declare au manifest, et nommer les constats.

    Les deux constats de la story 5.11 sont **informatifs**, jamais des
    erreurs: la commande a reussi dans les deux cas. Les taire ferait de la
    conservation d'etat et du remplacement d'un identifiant deja persiste deux
    effets invisibles -- exactement le mode de defaillance que l'auto-controle
    d'`extract` existe pour fermer.
    """
    resume = (
        f"Lot {persisted.lot_id} declare au manifest "
        f"({persisted.manifest_path.name}): etat {persisted.state_written}, "
        f"template {_lot_field(persisted, 'template_id')}, "
        f"patchs {_lot_field(persisted, 'patch_preset_id')}, "
        f"compression {_lot_field(persisted, 'gamut_map_id')}."
    )
    # Les trois autres ecrivains de manifest de ce fichier journalisent leur
    # ecriture; celui-ci ne le faisait pas, et `logs/makepdf.log` restait muet
    # sur le chemin nominal (revue 5.11, couche 1).
    logger.info(resume)
    print(resume)
    if pdf_manifest.PDF_STATE_CONSERVED in persisted.findings:
        message = (
            f"{pdf_manifest.PDF_STATE_CONSERVED}: le lot etait deja en "
            f"'{persisted.state_written}', un etat posterieur a 'pdf'. Son etat "
            "est conserve tel quel -- reimprimer une planche n'invalide aucun "
            "artefact aval."
        )
        logger.info(message)
        print(message)
    if pdf_manifest.PDF_IDENTIFIER_DIVERGES in persisted.findings:
        message = (
            f"{pdf_manifest.PDF_IDENTIFIER_DIVERGES}: "
            f"{', '.join(persisted.diverging_fields)} differai(en)t de la valeur "
            "deja persistee. Le manifest decrit desormais le dernier PDF "
            "produit, et le manifest seul: les planches tirees avant cette "
            "impression portent l'ancienne valeur dans leur QR, et rien ne la "
            "conserve. Detruire les tirages perimes, ou les scanner avant de "
            "reimprimer."
        )
        logger.warning(message)
        print(message)


def _lot_field(persisted, field: str) -> str:
    """Relire un champ du lot dans le manifest **effectivement ecrit**."""
    for lot in persisted.manifest.get("lots") or []:
        if isinstance(lot, dict) and lot.get("lot_id") == persisted.lot_id:
            return str(lot.get(field))
    return "?"


# `_lot_designation_error` a emigre avec le corps qui l'appelle : c'est
# `makepdf.motif_de_designation_du_lot(lot, rush, fps)`, qui prend trois valeurs
# nommees au lieu d'un objet `args` -- une interface n'en a pas.


def makepdf_command(args):
    """Produire le PDF de planches imprimables d'un lot (story 4.1).

    **ENVELOPPE depuis la story 11.7, lot B (tache B5).** Le corps -- gardes,
    resolution du `lot_id`, conformite, rang de tirage, composition, detection
    de conflit, rendu, declaration au manifest -- a ete **deplace** dans
    `mixed_media_utility.makepdf`, sans etre reecrit. Ce qui reste ici est ce
    qu'une CLI possede en propre: le journal de la commande, les phrases
    imprimees et le code de sortie.

    Motif du deplacement: la TUI a interdiction d'importer `cli` (frontiere de
    la 11.4b), et l'atelier Pdf n'avait donc **rien a appeler**. Meme geste
    qu'`EPIC11-ARB-129` pour le temps 2 du Scan, deja fait deux fois sur cette
    chaine (`scan_detect.run_scan_detect`, `scan_write.ecrire_le_lot_detecte`).

    Codes de sortie, alignes sur le contrat de `extract` sans en inventer:

    * `0` succes;
    * `1` erreur d'entree ou de traitement (vocabulaire refuse, lot non
      conforme, budget QR depasse, geometrie impossible, ecriture);
    * `2` non utilise: makepdf n'a aucun prerequis externe (reportlab et
      OpenCV sont des dependances du paquet, pas des outils systeme);
    * `3` non utilise: l'arbitrage EPIC4-ARB-2 (4.5-Q2) a tranche
      "avertissement structure sans consentement" pour le hors budget
      nominal -- il n'existe donc aucun consentement a refuser;
    * `130` interruption clavier propre (aucun PDF partiel ne reste en
      place, ecriture atomique).

    Depuis la story 5.11 (EPIC5-ARB-20), la commande **declare au manifest**
    ce qu'elle vient de produire, et rien d'autre: `lots[].state = "pdf"`,
    `template_id`, `patch_preset_id` et `gamut_map_id` du lot vise. C'est le
    declenchement prevu par EPIC4-ARB-4, dont l'ecart avec la matrice 2.4
    n'etait assume que « tant que le scan n'en a pas besoin ». Elle ne touche
    ni les frames, ni aucune autre section du manifest, ni rien d'autre que
    le PDF sous `planches/` et son journal. Un echec de cette declaration fait
    **echouer la commande** (`1`) alors meme que le PDF est ecrit: le PDF
    reste sur disque pour diagnostic et le `project.json` precedent est
    strictement intact.
    """
    project_dir = Path(args.project)
    # Les trois gardes d'ouverture sont jouees ICI, avant le journal, parce
    # qu'elles le precedent dans le corps d'origine: `--project <inexistant>`
    # n'a jamais cree ni arborescence, ni `logs/makepdf.log`. Le coeur les
    # rejoue pour son propre compte -- une fonction de coeur ne fait pas
    # confiance a son appelant --, et les rejouer ne coute que deux `is_dir`.
    try:
        makepdf_core.refuser_l_ouverture_du_projet(
            project_dir, lot=args.lot, rush=args.rush, fps=args.fps)
    except makepdf_core.RefusDeMakepdf as exc:
        print(f"Erreur: {exc}", file=sys.stderr)
        return 1

    project_layout.ensure_project_layout(project_dir)
    logger = _configure_makepdf_logger(project_dir)
    logger.info("Demarrage de makepdf pour le projet %s", project_dir)

    try:
        resultat = makepdf_core.generer_les_planches_du_lot(
            project_dir,
            lot=args.lot,
            rush=args.rush,
            fps=args.fps,
            orientation=args.orientation,
            frames_per_page=args.frames_par_page,
            margin_preset=args.marge,
            patch_preset=args.nombre_patchs,
            gamut_map_id=args.gamut_map,
            render_dpi=args.dpi,
            page_format=args.format,
            geometry_version=args.geometrie,
            overwrite=getattr(args, "overwrite", False),
            logger=logger,
        )
        plan = resultat.plan
        print(
            f"makepdf termine avec succes. {plan.page_count} page(s) "
            f"({plan.frames_per_page} frame(s) par page, template "
            f"{plan.template_id}, patchs {plan.patch_preset_id}) dans "
            f"{resultat.output_path}."
        )
        if plan.warnings:
            print(f"{len(plan.warnings)} avertissement(s) structurel(s), "
                  "voir ci-dessus.")
        _print_pdf_persistence(logger, resultat.persisted)
        print(f"Consigne de numerisation: scanner a {plan.scan_dpi} dpi minimum.")
        return 0
    except makepdf_core.LotNonConforme as exc:
        # Le refus porte des FAITS, jamais la phrase composee: c'est ici, et
        # ici seulement, qu'ils deviennent des lignes de terminal. La
        # distinction entre « lot absent » et « lot non conforme » se lit sur
        # le CODE de verification (`exc.lot_absent`), jamais sur un bout de
        # message -- les deux reprises different, re-extraire ne servant a rien
        # quand le lot n'est pas declare (revue 5.11, couche 3).
        print(f"Erreur: {exc}", file=sys.stderr)
        for code in exc.verification.blocking_findings:
            print(f"  - {code}", file=sys.stderr)
        if exc.lot_absent:
            print(f"  Lots disponibles dans le manifest: {exc.lots_disponibles}",
                  file=sys.stderr)
        else:
            print(
                "  Le lot sur disque ne correspond plus a ce que le manifest "
                "declare: re-extraire (extract --overwrite) avant makepdf.",
                file=sys.stderr,
            )
        return 1
    except makepdf_core.RefusDeMakepdf as exc:
        # Le conflit de sortie, et tout refus nomme de ce module qui n'a pas de
        # mise en forme propre. Il n'emprunte PAS `_handle_poc_failure`: le
        # corps d'origine ne journalisait pas ce refus, et le faire ajouterait
        # une ligne a `logs/makepdf.log` que le dossier d'identite verrait.
        print(f"Erreur: {exc}", file=sys.stderr)
        return 1
    except pdf_composition.CompositionError as exc:
        return _handle_poc_failure(logger, exc, 1)
    except (PayloadBudgetExceeded, PayloadValidationError, NonCanonicalIdentifierError) as exc:
        return _handle_poc_failure(logger, exc, 1)
    except (qr_codes.QRPayloadTooLarge, qr_codes.QRRenderError) as exc:
        return _handle_poc_failure(logger, exc, 1)
    except pdf_render.PdfRenderError as exc:
        return _handle_poc_failure(logger, exc, 1)
    except ExtractionPersistenceError as exc:
        # ARB-7 d'`extract` transpose a l'impression (story 5.11): PDF ecrit,
        # manifest non ecrit = **echec**. Effacer le PDF detruirait de
        # l'information de diagnostic, et le declarer reussi laisserait un lot
        # imprime que le manifest ignore -- exactement l'ecart que la story
        # ferme.
        #
        # L'erreur remonte **telle quelle**, sans re-emballage (AC 2): la
        # reconstruire dans la classe de base aplatissait la hierarchie que le
        # module vient de creer et perdait le chainage. La consigne de reprise
        # est imprimee a cote, et elle **depend du cas**: relancer avec
        # `--overwrite` ne leve rien quand le lot a disparu de `lots[]`
        # (revue 5.11, couche 3).
        #
        # Le chemin du PDF vient de l'exception (`pdf_path`, pose par le coeur
        # au moment de l'echec) et non d'une variable de cette fonction: depuis
        # le deplacement, l'enveloppe n'a jamais eu `output_path` en main sur ce
        # chemin, et le recomposer serait re-deriver une convention que
        # `io.naming` possede.
        print(
            f"Le PDF {getattr(exc, 'pdf_path', None)} a bien ete ecrit et reste en place; seule "
            "la declaration au manifest a echoue.",
            file=sys.stderr,
        )
        if isinstance(exc, pdf_manifest.PdfLotAbsentError):
            print(
                "  Reprise: le lot vise n'est plus dans le manifest. Relancer "
                "makepdf ne changera rien tant qu'il n'y est pas -- verifier "
                "le project.json, ou re-extraire le lot.",
                file=sys.stderr,
            )
        else:
            print(
                "  Reprise: une fois la cause levee, relancer makepdf "
                "--overwrite pour declarer le lot au manifest.",
                file=sys.stderr,
            )
        return _handle_poc_failure(logger, exc, 1)
    except NamingError as exc:
        return _handle_poc_failure(logger, exc, 1)
    except ValidationError as exc:
        return _handle_poc_failure(logger, exc, 1)
    except json.JSONDecodeError as exc:
        return _handle_poc_failure(
            logger,
            ValueError(
                f"project.json n'est pas un JSON valide ({exc}). Le manifest "
                "est corrompu ou a ete edite a la main: le reparer ou "
                "re-extraire le lot."
            ),
            1,
        )
    except (
        page_templates.UnknownTemplateError,
        patch_presets.UnknownPatchPresetError,
        patch_presets.UndefinedPlacementError,
    ) as exc:
        # Registres 4.7/4.1: erreurs metier actionnables, jamais une trace
        # Python. Enumerees par classe -- un `except ValueError` large
        # deguisait les bugs internes en erreurs operateur (revue 4.1 du
        # 2026-08-06).
        return _handle_poc_failure(logger, exc, 1)
    except KeyboardInterrupt:
        # Amende par la story 5.11: « le manifest est inchange » etait vrai
        # tant que la commande n'ecrivait rien; ce n'est plus une promesse
        # tenable une fois le point de declaration franchi. Ce qui reste vrai,
        # et qui est ce qui compte pour l'operateur, c'est qu'aucune des deux
        # ecritures ne laisse d'etat partiel: le PDF et le manifest sont
        # chacun bascules par `os.replace`.
        print(
            "\nInterruption clavier: makepdf arrete. Ni PDF partiel ni manifest "
            "partiel n'ont ete mis en place (les deux ecritures sont atomiques). "
            "Selon l'instant de l'interruption, le lot peut avoir ete declare au "
            "manifest ou non: relire project.json pour le savoir."
        )
        return 130
    except OSError as exc:
        return _handle_poc_failure(
            logger,
            OSError(
                f"Erreur d'acces disque pendant makepdf: {exc}. Verifier "
                "l'espace disponible et les droits d'ecriture sur le dossier "
                "projet."
            ),
            1,
        )
    finally:
        _close_logger_handlers(logger)


def makepdf_calibration_page_command(args):
    """Generer la **page de calibration seule**, a la demande (story 5.22, AC 8).

    **ENVELOPPE depuis la story 11.7, lot B (tache B5).** Le corps est
    `makepdf.generer_la_page_de_calibration`, deplace et non reecrit; motif et
    contrat complets dans le docstring de ce module.

    Codes de sortie: ceux de `makepdf`, sans en inventer -- `0` succes, `1`
    erreur d'entree ou de traitement, `130` interruption clavier.
    """
    project_dir = Path(args.project)
    try:
        makepdf_core.refuser_l_ouverture_de_la_mire(project_dir)
    except makepdf_core.RefusDeMakepdf as exc:
        print(f"Erreur: {exc}", file=sys.stderr)
        return 1

    project_layout.ensure_project_layout(project_dir)
    logger = _configure_makepdf_logger(project_dir)
    logger.info(
        "Demarrage de la generation de page de calibration pour le projet %s",
        project_dir,
    )

    try:
        resultat = makepdf_core.generer_la_page_de_calibration(
            project_dir,
            scan_chain_label=args.chaine,
            comment=args.commentaire,
            orientation=args.orientation,
            frames_per_page=args.frames_par_page,
            margin_preset=args.marge,
            patch_preset=args.nombre_patchs,
            gamut_map_id=args.gamut_map,
            render_dpi=args.dpi,
            page_format=args.format,
            geometry_version=args.geometrie,
            overwrite=args.overwrite,
            logger=logger,
        )
        output_path, plan = resultat.output_path, resultat.plan
    except makepdf_core.RefusDeMakepdf as exc:
        print(f"Erreur: {exc}", file=sys.stderr)
        return 1
    except pdf_composition.CompositionError as exc:
        return _handle_poc_failure(logger, exc, 1)
    except (PayloadBudgetExceeded, PayloadValidationError, NonCanonicalIdentifierError) as exc:
        return _handle_poc_failure(logger, exc, 1)
    except (qr_codes.QRPayloadTooLarge, qr_codes.QRRenderError) as exc:
        return _handle_poc_failure(logger, exc, 1)
    except pdf_render.PdfRenderError as exc:
        return _handle_poc_failure(logger, exc, 1)
    except NamingError as exc:
        return _handle_poc_failure(logger, exc, 1)
    except ValidationError as exc:
        return _handle_poc_failure(logger, exc, 1)
    except json.JSONDecodeError as exc:
        return _handle_poc_failure(
            logger,
            ValueError(
                f"project.json n'est pas un JSON valide ({exc}). Le manifest "
                "est corrompu ou a ete edite a la main: le reparer ou "
                "re-extraire le lot."
            ),
            1,
        )
    except (
        page_templates.UnknownTemplateError,
        patch_presets.UnknownPatchPresetError,
        patch_presets.UndefinedPlacementError,
    ) as exc:
        return _handle_poc_failure(logger, exc, 1)
    except KeyboardInterrupt:
        print(
            "\nInterruption clavier: la generation de page de calibration est "
            "arretee. Aucun PDF partiel n'a ete mis en place (ecriture atomique) "
            "et le manifest n'est jamais touche par cette commande."
        )
        return 130
    except OSError as exc:
        return _handle_poc_failure(
            logger,
            OSError(
                f"Erreur d'acces disque pendant la generation de la page de "
                f"calibration: {exc}. Verifier l'espace disponible et les droits "
                "d'ecriture sur le dossier projet."
            ),
            1,
        )
    finally:
        _close_logger_handlers(logger)

    # **Cette ligne part dans un logger deja ferme, et c'est l'etat du depot,
    # pas un effet du deplacement.** Le `finally` ci-dessus a retire les
    # handlers: `logs/makepdf.log` ne porte donc rien sur le chemin nominal de
    # la mire. C'est le defaut exact que la liaison de la vague 3 a corrige
    # pour `makepdf` (voir le commentaire de `generer_les_planches_du_lot`) et
    # qui vit encore ici. Il n'est PAS corrige dans ce lot: le corriger
    # changerait un observable que le dossier d'identite de la tache B1 mesure,
    # et le lot B a pour contrat de n'en changer aucun. La correction se
    # demande a part, avec sa mesure.
    logger.info("Page de calibration ecrite: %s", output_path)
    print(
        f"page de calibration ecrite: {output_path} (chaine \"{args.chaine}\", "
        f"template {plan.template_id}, a scanner a {plan.scan_dpi} dpi minimum). "
        "Imprimez-la, scannez-la, puis lancez `scan ... calibrate` pour consigner "
        "le profil de la chaine."
    )
    if plan.warnings:
        print(f"{len(plan.warnings)} avertissement(s) structurel(s), voir ci-dessus.")
    return 0


def _configure_previz_logger() -> logging.Logger:
    """Logger de la commande `previz`: console uniquement, jamais de fichier.

    Aucun `FileHandler`, aucun dossier `logs/`, aucune arborescence projet:
    cette commande ne connait pas la notion de projet et n'ecrit nulle part
    (story 3.6, AC 1 et AC 8).
    """
    logger = logging.getLogger("mixed_media_utility.previz")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console_handler)
    return logger


def previz_command(args):
    """Previsualiser un rush a plusieurs cadences reduites, sans rien extraire.

    Codes de sortie, alignes sur `extract` (story 3.1) sans en inventer de
    nouveau:

    * `0` succes -- y compris quand le temps reel n'a pas ete tenu: un ecart
      mesure et rapporte n'est pas un echec;
    * `1` erreur d'entree ou de traitement;
    * `2` prerequis externe absent (`ffprobe` introuvable, aucun affichage
      disponible, OpenCV compile sans interface).

    Le code `3` n'est **pas** utilise: il n'y a rien a consentir ici.
    """
    logger = _configure_previz_logger()

    try:
        if not args.no_display:
            cadence_previz.ensure_display_available()

        session = cadence_previz.prepare_previz(
            video_path=Path(args.video),
            fps_targets=list(args.fps),
            # Story 3.7: les memes bornes que `extract`, passees au meme noyau.
            # A ne pas confondre avec `--start` / `--duration` juste en dessous:
            # celles-ci restreignent ce qui est **joue**, celles-la ce qui est
            # **retenu**.
            source_in_timecode=args.in_timecode,
            source_out_timecode=args.out_timecode,
            start_seconds=args.start,
            duration_seconds=args.duration,
            logger=logger,
        )

        sink = (
            cadence_previz.NullSink()
            if args.no_display
            else cadence_previz.CvWindowSink()
        )
        result = cadence_previz.play_cadences(
            session,
            sink=sink,
            height=args.height,
            memory_budget_mb=args.memory_budget_mb,
            on_late=args.on_late,
            logger=logger,
        )
    except cadence_previz.DisplayUnavailableError as exc:
        return _handle_poc_failure(logger, exc, 2)
    except extraction.ExtractionInputError as exc:
        return _handle_poc_failure(logger, exc, 1)
    except FrameSelectionError as exc:
        return _handle_poc_failure(logger, exc, 1)
    except video_metadata.FfprobeNotFoundError as exc:
        return _handle_poc_failure(logger, exc, 2)
    except video_metadata.FfprobeError as exc:
        return _handle_poc_failure(logger, exc, 1)
    except KeyboardInterrupt:
        # Aucune trace Python sur Ctrl+C: la session est deja liberee par le
        # `finally` du lecteur, et rien n'a jamais ete ecrit.
        print("\nInterruption clavier: previz arretee, aucun fichier ecrit.")
        return 0
    finally:
        _close_logger_handlers(logger)

    print()
    for report in result.reports:
        for line in cadence_previz.format_report_lines(report):
            print(line)
    if result.interrupted:
        # Ne qualifier de partiels que les rapports qui le sont reellement: la
        # formulation precedente marquait PARTIEL(S) des rapports complets, et
        # attribuait au clavier une interruption qui pouvait venir d'un flux
        # tronque (revue du 2026-08-05).
        partiels = [
            f"{report.fps_target:g} im/s" for report in result.reports if report.partiel
        ]
        if partiels:
            print(
                "Lecture interrompue avant la fin. Rapport(s) partiel(s): "
                + ", ".join(partiels)
                + ". Aucun fichier n'a ete ecrit."
            )
        else:
            print(
                "Lecture interrompue apres la derniere cadence: les rapports "
                "ci-dessus sont complets. Aucun fichier n'a ete ecrit."
            )
    print(
        f"previz terminee. {result.decoded_frames} frame(s) decodee(s), "
        f"{result.cache_hits} servie(s) par le cache memoire. "
        "Aucun fichier ecrit, aucun lot cree, aucune extraction declenchee."
    )
    return 0


def _aide_nombre_patchs() -> str:
    """Aide de `--nombre-patchs`, **entierement derivee du registre**.

    Quatre elements, aucun ecrit a la main: les identifiants connus, leurs cardinaux, le
    defaut, et -- c'est le correctif du bloquant B4 de la revue de 5.16 -- les presets qui
    portent les **sentinelles de gamut**, plus l'orientation ou l'un d'eux ne se compose
    pas. Le second volet est ce qui rend l'aide utile: nommer les deux presets a
    sentinelles sans dire que `patches-18-v2` est refuse en paysage v2 y renverrait
    l'operateur, et son refus lui proposerait `--geometrie v1`.

    La phrase de refus est derivee de `unplaceable_couples()`, donc elle disparait d'elle
    meme le jour ou le couple disparait -- ce que le point de `deferred-work.md` sur
    `paysage x patches-18-v2` attend.
    """
    presets = patch_presets.known_preset_ids()
    cardinaux = ", ".join(
        str(len(patch_presets.get_patch_preset(pid).value_ids)) for pid in presets
    )
    sentinelles = patch_presets.gamut_sentinel_preset_ids()
    aide = (
        f"Preset de patchs de calibration, par identifiant ({', '.join(presets)}) "
        f"ou par cardinal ({cardinaux}); defaut "
        f"{pdf_composition.DEFAULT_PATCH_PRESET}."
    )
    if sentinelles:
        aide += (
            f" Sentinelles de gamut, requises par le verdict d'ecretage: "
            f"{', '.join(sentinelles)}."
        )
    refus = [
        (preset_id, version, orientation)
        for version, orientation, preset_id in patch_presets.unplaceable_couples()
        if preset_id in sentinelles
    ]
    for preset_id, version, orientation in refus:
        aide += (
            f" {preset_id} n'est pas composable en {orientation} {version}: "
            f"prendre un autre preset a sentinelles plutot que de changer de geometrie."
        )
    return aide


# **`allow_abbrev=False` sur TOUS les parseurs de la CLI, sans exception par
# commande** (`EPIC11-ARB-248`, Egan le 2026-09-06, verbatim : « Porter
# `allow_abbrev=False` aux seize »). Ce qui suit vaut pour le parseur racine
# comme pour les dix-huit sous-parseurs : un sous-parseur **n'herite pas** du
# drapeau de son parent, c'est ce que le mutant `M19` du lot B de la 11.4e
# avait mesure sur `project remove`.
#
# **Le recensement, lu du parseur CONSTRUIT et non d'un grep** (2026-09-06) :
# dix-neuf parseurs en tout, trois portaient deja le drapeau (racine,
# `project remove`, `project add-rush`), **seize** ne le portaient pas. Le
# chiffre du registre (`Q18`) est confirme au parseur pres.
#
# **Pourquoi aux seize et pas aux quatre commandes ecrivantes.** Un reglage par
# objet est exactement ce qu'`EPIC11-ARB-108` interdit -- « il n'y a pas de
# mecanisme different par objet » --, et le laisser sur `previz` ou `poc`
# garderait vivante la surface que le drapeau existe pour fermer : `argparse`
# resout tout prefixe non ambigu, donc `--vers` atteint `--version` et `--for`
# atteint `--force`, et cette surface **grandit a chaque drapeau ajoute**
# plutot que de rester ce qu'elle est aujourd'hui.
#
# **Ce que ca coute, dit plutot que tu** : c'est un **retrait pur**, meme geste
# qu'`EPIC11-ARB-220` -- aucune abreviation n'est plus acceptee, sans alias ni
# message de transition, donc un script d'operateur qui s'appuyait sur une
# abreviation recoit desormais un refus NOMME (code 2) au lieu d'un resultat
# plausible. Une seule abreviation etait mesuree comme reellement atteignable
# et elle etait inscrite en dette : `mmu makepdf --frames` resolvait vers
# `--frames-par-page`, qui prend une VALEUR. Cette dette est FERMEE ici.
#
# **La frontiere qui empeche le dix-septieme**, parce qu'aucun test positif ne
# verrait revenir un parseur permissif, vit dans
# `tests/unit/test_suppression_element_de_projet.py` :
# `test_TOUT_parseur_de_la_CLI_refuse_les_ABREVIATIONS`. Elle lit l'attribut
# REEL sur le parseur construit, jamais le source -- un grep se contourne par
# une variable.
def main(argv=None):
    parser = argparse.ArgumentParser(
        prog='mixed-media-util',
        description='Mixed Media Utility — extraction, gabarits et calibration',
        allow_abbrev=False
    )
    parser.add_argument('--version', action='version', version=__version__)
    sub = parser.add_subparsers(dest='command')

    # Story 4.1: les stubs `gen-gabarit`, `extract-frames` et `apply-calibration`
    # (handlers vides depuis le squelette initial) sont retires au profit des
    # commandes reelles `makepdf`, `extract` et `scan calibrate`.
    p4 = sub.add_parser(
        'encode',
        allow_abbrev=False,
        help="Reconstruire un master video depuis les frames scannees d'un lot "
             "(outputs/<lot>_mmu_<profil>.<conteneur>)",
    )
    p4.add_argument('--project', required=True, help='Dossier projet existant (contient project.json)')
    p4.add_argument('--lot', required=True, help='lot_id du lot scanne a encoder')
    # Vocabulaire **derive** du catalogue: ajouter un profil a
    # `codec_profiles.PROFILES` suffit a l'exposer. Les anciennes valeurs
    # ('prores', 'h264', 'hevc') n'etaient aucune un identifiant valide, et les
    # deux profils DNxHR etaient de ce fait inaccessibles.
    p4.add_argument(
        '--profile',
        choices=sorted(codec_profiles.PROFILES),
        default=codec_profiles.DEFAULT_PROFILE_ID,
        help=f"Profil d'encodage (defaut {codec_profiles.DEFAULT_PROFILE_ID}, "
             "master mezzanine acte par l'architecture)",
    )
    # Pas de `choices=` argparse: le registre admet aussi une resolution
    # personnalisee, et son message de refus est plus actionnable que celui
    # d'argparse (meme motif que les vocabulaires de `makepdf`).
    p4.add_argument(
        '--resolution',
        default=None,
        help="Resolution du master: identifiant du registre "
             f"({', '.join(encode_module.known_resolution_ids())}), "
             f"'{encode_module.NATIVE_RESOLUTION_KEYWORD}' pour la geometrie des "
             "frames scannees, ou <largeur>x<hauteur>; defaut "
             f"{encode_module.DEFAULT_RESOLUTION_ID}",
    )
    p4.add_argument(
        '--overwrite',
        action='store_true',
        help="Remplacer un master deja present sous outputs/ (jamais implicite)",
    )
    # Story 11.8 (`EPIC11-ARB-89` / `EPIC11-ARB-91`), sur le modele litteral
    # d'`extract` ci-dessous. **Cette option etait NOMMEE par le refus de
    # `check_output_destination` et n'existait pas** : un operateur qui suivait
    # le conseil du refus recevait `unrecognized arguments: --nouvelle-version`,
    # c'est-a-dire un blocage sec deguise dont la seule autre issue etait la
    # destruction -- exactement ce qu'`EPIC11-ARB-89` interdit. Le refus nomme
    # est rendu par le coeur (`encode.plan_encode`) et non par argparse, comme
    # pour `extract` : la TUI, qui n'a pas le droit d'importer `cli`, doit le
    # recevoir elle aussi.
    p4.add_argument(
        '--nouvelle-version',
        dest='nouvelle_version',
        action='store_true',
        help="Sur un master deja present: en ecrire une nouvelle version "
             "(suffixe _v2, _v3, ... apres le profil et la resolution) plutot "
             "que de refuser. Le master present reste intact. Incompatible "
             "avec --overwrite",
    )
    p4.add_argument(
        '--yes', '-y',
        dest='yes',
        action='store_true',
        help="Consentement d'encodage, pour un usage sans terminal interactif",
    )
    p4.add_argument(
        '--accept-incomplete-lot',
        dest='accept_incomplete_lot',
        action='store_true',
        help="Encoder un lot definitivement incomplet (planche perdue, jamais "
             "rescannee). Le recapitulatif declare alors l'incompletude; aucun "
             "trou n'est jamais comble par repetition de l'image precedente",
    )
    p4.add_argument(
        '--cadence-source',
        dest='cadence_source',
        type=_parse_cadence_source,
        default=None,
        help="Cadence source du rush (decimal ou 'num/den'), requise "
             "uniquement si le lot ne la porte pas deja (planche imprimee en "
             "payload 2.0, avant la story 2.7, ou manifest reconstruit d'une "
             "source qui ne l'ecrit pas -- un lot ne du scan d'une planche "
             "2.1 la porte desormais). Jamais un repli automatique sur la "
             "cadence cible. Si le lot porte deja sa propre cadence source, "
             "cette option PRIME sur elle (avertissement structure au "
             "recapitulatif nommant les deux valeurs): le papier ne se met "
             "pas a jour, c'est le seul moyen de corriger a l'encodage une "
             "cadence source fausse imprimee sur une planche",
    )
    p4.set_defaults(func=encode_command)

    # Story 3.1. Le stub historique `extract-frames` ci-dessus est laisse
    # strictement intact (aucun test ne le couvre, et le retirer serait un
    # changement de surface hors du perimetre additif de cette story).
    p7 = sub.add_parser(
        'extract',
        allow_abbrev=False,
        help="Extraire un lot de frames TIFF deterministe depuis un rush "
             f"({project_layout.EXTRACT_FRAMES_DIRNAME}/<rush>_<fps>/)",
    )
    p7.add_argument('--project', required=True, help='Dossier projet cible (cree si absent)')
    p7.add_argument('--video', required=True, help='Fichier video source (rush)')
    p7.add_argument('--fps', type=float, required=True, help='Cadence cible, en images par seconde')
    p7.add_argument(
        '--overwrite',
        action='store_true',
        help="Remplacer un lot deja present dans le dossier de lot (jamais implicite)",
    )
    # Story 5.29 (`EPIC11-ARB-89`). Les deux issues du refus de transition
    # d'etat: creer une nouvelle version (ce lot-ci reste intact), ou ecraser
    # sciemment ce lot en place. Mutuellement exclusifs (refus nomme si les
    # deux sont passes -- `extraction.run_extraction`).
    p7.add_argument(
        '--nouvelle-version',
        dest='nouvelle_version',
        action='store_true',
        help="Sur un lot deja passe au-dela de l'etat 'extraction': creer une "
             "nouvelle version de ce lot (suffixe _v2, _v3, ...) plutot que de "
             "refuser. Le lot existant reste intact",
    )
    p7.add_argument(
        '--ecrasement-conscient',
        dest='ecrasement_conscient',
        action='store_true',
        help="Sur un lot deja passe au-dela de l'etat 'extraction': l'ecraser "
             "SCIEMMENT en place plutot que de refuser. Exige --yes (le "
             "consentement general). Incompatible avec --nouvelle-version",
    )
    p7.add_argument(
        '--yes', '-y',
        dest='yes',
        action='store_true',
        help="Consentement general d'extraction, pour un usage sans terminal interactif",
    )
    p7.add_argument(
        '--accept-unknown-color',
        dest='accept_unknown_color',
        action='store_true',
        help="Consentement supplementaire quand la colorimetrie source est absente ou incomplete",
    )
    # Story 3.7. `dest=` n'est pas une coquetterie de style: `in` est un
    # mot-cle Python, donc `args.in` est une SyntaxError et argparse rangerait
    # la valeur sous un attribut illisible autrement que par `vars()`.
    # Aucun defaut: une borne absente doit rester absente (AC 14).
    p7.add_argument(
        '--in',
        dest='in_timecode',
        default=None,
        metavar='TIMECODE',
        help="Borne d'entree de l'extrait, en timecode source hh:mm:ss:ff tel "
             "qu'affiche par previz et par les noms de fichiers (celui du rush, "
             "pas un decalage depuis son debut). Sans cette option, l'extraction "
             "part de la premiere image du rush",
    )
    p7.add_argument(
        '--out',
        dest='out_timecode',
        default=None,
        metavar='TIMECODE',
        help="Borne de sortie de l'extrait, meme base de temps que --in et "
             "incluse dans l'extrait. Les deux bornes sont independantes: "
             "l'une peut etre donnee sans l'autre",
    )
    p7.set_defaults(func=extract_command)

    # Story 5.1. Commande de premier rang, au meme rang qu'`extract` et
    # `makepdf` -- et non une extension de `poc process-scan`, qui reste intact
    # avec son manifest legacy et son `--dpi` par defaut a 300. Les deux chemins
    # coexistent.
    p8 = sub.add_parser(
        'scan',
        allow_abbrev=False,
        help="Ingerer un lot de pages scannees (dossier d'images, image unique "
             "ou PDF multipage) et le normaliser en un jeu de pages ordonne",
    )
    p8.add_argument('--project', required=True, help='Dossier projet cible (cree si absent)')
    p8.add_argument(
        '--scan',
        required=True,
        help="Dossier d'images, image unique (png/jpg/tiff) ou document PDF multipage",
    )
    # Pas de defaut, contrairement au POC: un DPI faux fausse toute la geometrie
    # aval sans erreur visible (risque R8, scanner en auto-fit). Sur un PDF il
    # pilote en plus le rendu -- c'est la seule source du facteur d'echelle.
    p8.add_argument(
        '--dpi',
        type=int,
        required=True,
        help="Resolution de scan declaree, en points par pouce. Obligatoire: "
             "elle n'est jamais devinee, et sur un PDF elle pilote le rendu",
    )
    p8.add_argument(
        '--nouvelle-version',
        action='store_true',
        dest='nouvelle_version',
        help="Ingerer un scan VOISIN au lieu de refuser quand le slug porte "
             "deja un contenu different (EPIC11-ARB-104). Le rang entre dans le "
             "nom du dossier (`scans/<slug>_v2/`). Scenario type: on reprend une "
             "planche imprimee, on y ajoute une retouche, on rescanne -- le "
             "contenu a change, l'identite non, et il n'y a aucune raison "
             "d'inventer un nom pour cela.",
    )
    p8.add_argument(
        '--lot-slug',
        dest='lot_slug',
        default=None,
        help="Nom du dossier de lot sous scans/. C'est un slug operateur, pas "
             "un lot_id: l'identite metier du lot est portee par le QR et n'est "
             "connue qu'au decodage (story 5.2)",
    )
    # Un seul drapeau pour les deux ecritures, parce que c'est une seule
    # intention d'operateur: ecraser un fichier de sortie existant
    # (EPIC5-ARB-18, par fichier et non par dossier) et assumer au manifest
    # qu'une vraie frame redevienne une frame de remplacement (story 5.7,
    # AC 10). Il ne leve **aucun** conflit d'identifiant d'impression: celui-la
    # dit qu'on scanne la planche d'un autre lot, et un second drapeau ne le
    # rendrait pas vrai.
    p8.add_argument(
        '--overwrite',
        action='store_true',
        help="Reecrire les frames de sortie deja presentes et assumer au "
             "manifest la perte d'une frame reelle redevenue frame de "
             "remplacement. Ne leve aucun refus de planche etrangere",
    )
    # Story 5.16, AC 15 (`EPIC5-ARB-57`). **Le nom du drapeau vient du module qui
    # possede le contournement**, jamais d'un litteral recopie ici: un second nom
    # divergerait du message de refus qui l'annonce a l'operateur, et le refus serait
    # alors une impasse -- il nommerait une option qui n'existe pas.
    #
    # Trois proprietes que ce drapeau doit avoir, et qui sont celles de l'arbitrage:
    # il est **explicite** (jamais un repli automatique), il ne **regle** aucun seuil
    # (`--seuil`, `--tolerance` sont exclus par une frontiere negative testee), et il ne
    # **re-ajuste** rien -- il fait appliquer la correction de la page de calibration
    # telle quelle. Un troisieme regime de correction n'existe pas.
    # `EPIC5-ARB-78`, 2026-08-13. **Un interrupteur, pas un reglage**: `on`/`off` et rien
    # d'autre. C'est la contrainte litterale de l'arbitrage -- « on ne bloque rien a cause
    # d'un seuil etc. On informe. Si le resultat est rate l'utilisateur peut relancer la
    # commande avec un flag --cc off » --, et elle vaut aussi contre la tentation
    # symetrique: aucune option de reglage numerique a cote. Le vocabulaire est ferme par
    # `choices`, donc `--cc oui` est refuse par argparse et non interprete.
    #
    # **L'aide elle-meme ne prononce aucun mot de reglage**, et ce n'est pas une coquetterie
    # de redaction: la frontiere negative de l'AC 16 de 5.16
    # (`test_the_flag_and_its_help_contain_no_setting_word`) balaie toute l'aide de `scan`,
    # pas seulement le nom des drapeaux. Une premiere redaction disait « aucun seuil ne s'y
    # regle » -- vrai sur le fond, et refuse a juste titre: l'operateur lit l'aide, pas
    # l'intention, et y voir le mot suffit a suggerer qu'il existe un cadran quelque part.
    #
    # Le defaut est `on` parce que c'est le comportement d'avant ce drapeau: une option
    # nouvelle ne change pas ce que fait une commande deja tapee.
    p8.add_argument(
        CC_FLAG,
        dest='color_correction',
        choices=(CC_ON, CC_OFF),
        default=CC_ON,
        help="Appliquer ou non aux frames la correction couleur du lot (defaut "
             f"'{CC_ON}'). A '{CC_OFF}', la correction est **quand meme ajustee** sur la "
             "page de calibration et le manifest la mesure, mais elle n'est posee sur "
             "aucun pixel: les frames sortent non corrigees, et l'entree de la page de "
             f"calibration porte le motif '"
             f"{color_calibration.NOT_APPLIED_OPERATOR_OPT_OUT}' -- distinct du repli "
             "automatique d'une page de calibration illisible, qui reste la seule voie "
             "involontaire. Deux valeurs et rien d'autre: la correction ne s'applique "
             "pas a moitie",
    )
    p8.add_argument(
        color_calibration.DIVERGENCE_BYPASS_FLAG,
        dest='divergence_bypass',
        action='store_true',
        help="Marquer explicitement qu'une planche divergente doit recevoir la "
             "correction telle quelle. **Depuis la story 5.23 elle la recoit de toute "
             "facon** (`EPIC5-ARB-82`): la divergence n'a plus aucun pouvoir de refus, "
             "donc ce drapeau n'ouvre plus rien. Il est conserve parce qu'un script "
             "ecrit sous 5.22 le passe, et qu'une commande qui refuserait soudain une "
             "option connue casserait ce script pour rien; il continue d'inscrire au "
             "manifest la trace du contournement et l'ecart qui l'a motive",
    )
    # **Le refus est desormais le geste explicite** (`EPIC5-ARB-82` decision 6, AC 5 de
    # 5.23). Le nom du drapeau est lu sur le module qui possede la decision, jamais
    # recopie ici: deux redactions du meme nom divergent, et l'aide finirait par annoncer
    # une option que le code ne reconnait plus.
    p8.add_argument(
        color_calibration.RAW_OUTPUT_FLAG,
        dest='keep_raw',
        action='store_true',
        # **Le mot « seuil » est interdit dans cette aide**, frontiere negative de l'AC 16
        # de 5.16 balayee sur `scan --help` par `test_calibration_provenance_wiring`.
        # Une premiere redaction disait « on ne choisit pas un seuil » -- une phrase qui
        # interdit le reglage, mais qui le nomme, donc qui invite a le chercher. La
        # frontiere porte sur le texte que l'operateur lit, pas sur l'intention.
        help="Livrer le lot **brut**, sans poser la correction sur les pixels, et sans "
             "qu'aucune invite ne soit posee. C'est le geste explicite qui s'ecarte du "
             "defaut: depuis la story 5.23 la correction s'applique par defaut, quel "
             "que soit l'ecart mesure entre la feuille de calibration et les planches. "
             "Aucun reglage numerique n'est expose et il n'en existera pas: on refuse "
             "une correction, on ne la dose pas",
    )
    # **L'option qui nommait la chaine a la main a ete retiree** (story 5.23, AC 13,
    # `EPIC5-ARB-88`). Elle n'est **pas** remplacee par un refus nomme: le seul moyen de
    # produire un message de retrait serait de la redeclarer ici avec une action qui
    # echoue, c'est-a-dire de garder dans le parseur exactement le reste inerte que cette
    # AC supprime. `argparse` refuse deja bruyamment -- `unrecognized arguments`, code de
    # sortie 2 --, donc aucun script ne continue en silence avec un comportement change.
    # L'option n'a par ailleurs vecu qu'une journee (introduite le 2026-08-17, retiree le
    # 2026-08-18), sur une branche de developpement, sans version publiee ni mention dans
    # `docs/`.
    #
    # **C'est ici que l'operateur designe son profil** (story 5.23, AC 12,
    # `EPIC5-ARB-83`). Une seule option pour un seul geste: `--profil` a remplace
    # `--charger-profil-de-calibration`, dont la semantique -- consigner sous l'identite
    # derivee du scan, refuser un `chain_id` divergent -- portait le dernier appariement
    # automatique. Les garder toutes les deux aurait laisse dans le parseur deux gestes
    # pour la meme intention.
    p8.add_argument(
        PROFILE_FLAG,
        dest='profil',
        default=None,
        metavar='FICHIER',
        help="Chemin du profil de calibration a appliquer a ce scan. Le fichier est "
             "valide, applique tel quel, puis **verse au projet courant** (fichier de "
             "profil et entree de manifest). Il peut vivre **hors** du projet: une page "
             "et un profil appartiennent a une chaine de scan, pas a un projet, et "
             "aucun refus n'est leve pour cette raison. Sans cette option, le profil "
             f"par defaut du projet est utilise (`{SET_DEFAULT_PROFILE_COMMAND}`); sans "
             "defaut non plus, le lot est livre **brut** avec un avertissement -- aucun "
             "profil n'est choisi a votre place",
    )
    p8.set_defaults(func=scan_command)

    # Story 5.22, AC 1, 2 et 4. La sous-commande **porte** les arguments du
    # parent (`--project`, `--scan`, `--dpi` restent obligatoires avant elle,
    # pour que `scan --project p --scan s` garde son refus `--dpi` manquant):
    # le geste est `scan --project P --scan S --dpi D calibrate`.
    #
    # Elle ne redeclare **aucune** option du parent, et c'est deliberé: toute option
    # redeclaree ici sur un `dest` du parent ecraserait la valeur du parent par son
    # propre defaut. C'est mesure (2026-08-17): les defauts du sous-parseur sont
    # appliques **apres** l'analyse du parent, donc une option declaree des deux cotes
    # voyait la valeur saisie par l'operateur ecrasee par `None`, sans un mot.
    #
    # Story 5.23, AC 8quater: `--nom` et `--commentaire` s'y ajoutent, et ne tombent
    # **pas** dans ce piege -- leurs `dest` (`nom`, `commentaire`) n'existent pas sur le
    # parent, donc aucun defaut de sous-parseur n'ecrase quoi que ce soit. Elles sont
    # ici et pas sur `scan` parce qu'elles ne veulent rien dire pour un scan de lot:
    # declarees sur le parent, `scan --nom x` serait accepte puis ignore, c'est-a-dire
    # le reste inerte que l'AC 13 retire ailleurs dans cette meme story.
    scan_calibrate = p8.add_subparsers(dest='scan_subcommand')
    p8_calibrate = scan_calibrate.add_parser(
        SCAN_CALIBRATE_SUBCOMMAND,
        allow_abbrev=False,
        help="Calibrer la chaine de scan d'une page de calibration: ajuster la "
             f"correction et la consigner sous versions/calibration/, sous le nom que "
             f"vous donnez au profil ({PROFILE_NAME_FLAG}) -- l'identite de la chaine "
             f"reste ecrite dans le document. Le profil s'applique ensuite aux lots "
             f"par {PROFILE_FLAG} ou par `{SET_DEFAULT_PROFILE_COMMAND}`, jamais par un "
             f"appariement automatique",
    )
    # **Le nom du fichier appartient a l'operateur** (AC 8quater, `EPIC5-ARB-83`
    # geste 3). Sans l'option, la question est posee sur un terminal et le `chain_id`
    # sert de defaut silencieux ailleurs -- voir `_nom_et_commentaire_du_profil`.
    p8_calibrate.add_argument(
        PROFILE_NAME_FLAG,
        dest='nom',
        default=None,
        metavar='NOM',
        help="Nom sous lequel lire ce profil (ex: 'scanner maison default tiff'). Le "
             "fichier en prend un slug; l'identite officielle de la chaine reste "
             "ecrite dans le document. Sans cette option, la question est posee sur un "
             "terminal, et le nom derive de la chaine est pris ailleurs",
    )
    p8_calibrate.add_argument(
        PROFILE_COMMENT_FLAG,
        dest='commentaire',
        default=None,
        metavar='TEXTE',
        help="Commentaire libre attache au profil, destine a se relire au survol dans "
             "la GUI. Facultatif: son absence n'est pas un refus",
    )
    p8_calibrate.set_defaults(func=scan_calibrate_command)

    # Story 5.25, AC 1: meme motif exactement que `calibrate` juste au-dessus --
    # sous-commande du meme sous-parseur, portant les arguments du parent
    # (`--project`, `--scan`, `--dpi`, `--lot-slug`), aucune option redeclaree.
    # Le geste est `scan --project P --scan S --dpi D detect`.
    p8_detect = scan_calibrate.add_parser(
        SCAN_DETECT_SUBCOMMAND,
        allow_abbrev=False,
        help="Detecter un lot scanne et ecrire son document de detection "
             "(geometries, zones, payloads decodes, statuts, provenance), un "
             "fichier par detection sous scans/<slug>/detections/. N'ecrit "
             "aucune frame et ne touche pas au manifest: c'est le point "
             "d'arret pour juger la detection avant d'ecrire un seul TIFF",
    )
    p8_detect.set_defaults(func=scan_detect_command)

    # Story 4.1. `--rush` porte le rush_id canonique du manifest (extract n'a
    # pas de --rush: il derive le rush du fichier video); le couple
    # --rush/--fps resout lot_id via io.naming.build_lot_id, --lot le porte
    # directement. Vocabulaires fermes valides par pdf_composition (les refus
    # nomment le vocabulaire): pas de `choices=` argparse, pour que le message
    # d'erreur reste celui, actionnable, du registre.
    # Story 5.23, AC 12 (`EPIC5-ARB-83`, decision 2). **Commande dediee et separee**,
    # au premier niveau: le profil par defaut est une propriete du **projet**, pas un
    # reglage de la commande `scan`. La declarer sous `scan` en ferait un geste qu'on
    # tape en scannant, c'est-a-dire, a une distraction pres, l'effet de bord que
    # l'arbitrage interdit mot pour mot.
    p11 = sub.add_parser(
        SET_DEFAULT_PROFILE_COMMAND,
        allow_abbrev=False,
        help="Poser le profil de calibration par defaut d'un projet, utilise par les "
             f"scans qui ne passent pas {PROFILE_FLAG}",
    )
    p11.add_argument('--project', required=True,
                     help='Dossier projet existant (contient project.json)')
    # **Le meme nom d'option que sur `scan`**, et il est lu sur la meme constante: deux
    # redactions du meme nom divergent, et l'operateur apprendrait deux mots pour
    # designer la meme chose.
    p11.add_argument(
        PROFILE_FLAG,
        dest='profil',
        required=True,
        metavar='FICHIER',
        help="Chemin du profil de calibration a poser par defaut. Il peut vivre hors "
             "du projet: il y est verse (fichier de profil et entree de manifest), sans "
             "aucun refus lie au projet d'ou il vient",
    )
    p11.set_defaults(func=set_default_profile_command)

    # Story 5.29 (`EPIC11-ARB-89`, troisieme operation). Sous-commande plutot
    # qu'une commande plate: `project` est le porte-nom naturel des gestes de
    # maintenance d'arborescence, et d'autres suivront (l'entree de
    # `deferred-work.md` en nomme deja un troisieme, `--scan`).
    p13 = sub.add_parser(
        'project',
        allow_abbrev=False,
        help="Gestes de maintenance sur un projet (supprimer un lot ou un rush)",
    )
    p13_sub = p13.add_subparsers(dest='project_action', required=True)
    # **`allow_abbrev=False`, et ce n'est pas de la ceinture-bretelles**
    # (story 11.14, lot C, `EPIC11-ARB-220`). Le nom neuf de l'option de frames
    # PROLONGE le nom retire (`--frames` -> `--frames-scannees`), or `argparse`
    # accepte par defaut toute abreviation non ambigue : sans ce drapeau,
    # `--frames 2` restait accepte en silence et **supprimait**, ce qui vide le
    # « retrait pur » de son sens. Le precedent ecrit en tete de ce fichier
    # (`--charger-profil-de-calibration`) affirme que « `argparse` refuse
    # l'ancien nom bruyamment, donc aucun script ne continue en silence » :
    # cette affirmation cesse d'etre vraie des que le nom neuf prolonge
    # l'ancien, et c'est le cas ici. Le parseur racine porte deja le meme
    # drapeau (`main`, `allow_abbrev=False`) ; un sous-parseur ne l'herite pas.
    p13_remove = p13_sub.add_parser(
        'remove',
        allow_abbrev=False,
        help="Supprimer proprement un lot ou un rush: met a jour project.json ET "
             "retire ses fichiers. Apercu par defaut, ecrit seulement avec --confirmer",
    )
    p13_remove.add_argument('--project', required=True,
                            help='Dossier projet existant (contient project.json)')
    p13_cible = p13_remove.add_mutually_exclusive_group(required=True)
    p13_cible.add_argument('--lot', help="lot_id a supprimer, tel qu'ecrit au manifest")
    p13_cible.add_argument(
        '--rush',
        help="rush_id a supprimer. Refuse s'il porte encore des lots: aucune "
             "suppression en cascade, les lots se retirent un par un d'abord",
    )
    p13_remove.add_argument(
        '--confirmer',
        action='store_true',
        help="Effectuer reellement la suppression. Sans ce drapeau, la commande "
             "n'ecrit rien et se contente d'afficher ce qui serait supprime",
    )
    # **On designe un objet par les ARGUMENTS QUI L'ONT PRODUIT**
    # (`EPIC11-ARB-224`, Egan le 2026-09-05 : « il faudrait aussi une coherence
    # entre la commande remove et les commandes qui produisent les objets
    # correspondants. Avec les memes arguments qui ont servi a les generer pour
    # les identifier. »), plus `--version` pour le rang. AUCUN chemin, jamais :
    # l'emplacement est au manifeste, c'est lui qui le sait, et le demander a
    # l'operateur serait lui demander de recalculer ce que l'outil a ecrit.
    #
    # Un lot ne portant qu'une famille de planches et qu'une famille de lots
    # scannes, ces deux cibles-la n'ont rien a designer de plus : drapeaux nus.
    p13_remove.add_argument(
        '--planche',
        action='store_true',
        help="Retirer UNE SEULE planche du lot (exige --lot), au lieu du lot "
             "entier. C'est l'objet que produit `makepdf`. Le rang se donne par "
             "--version; sans lui, c'est la planche d'ORIGINE. Son fichier part "
             "s'il est la, et son entree au manifeste part TOUJOURS: c'est la "
             "meme dissociation que pour un rush dont le fichier source est sur "
             "un disque debranche. Sert notamment a delier une planche renommee "
             "a la main, dont l'entree occuperait sinon son rang definitivement "
             "(EPIC11-ARB-90).",
    )
    # Les trois cibles fines qu'`EPIC11-ARB-111` a AJOUTEES -- un compte
    # historique, pas celui de l'ensemble courant, qui en porte cinq.
    # Elles ferment la lacune que la
    # revue du 2026-08-31 avait nommee : les refus d'epuisement de rang
    # proposaient de « supprimer le DERNIER master / scan / jeu en liberant son
    # rang », et aucune commande ne savait le faire -- seul `--lot` existait, et
    # il emporte le lot entier.
    p13_remove.add_argument(
        '--master',
        action='store_true',
        help="Retirer UN SEUL master du lot (exige --lot), au lieu du lot "
             "entier. Il se designe par les arguments qui l'ont produit avec "
             "`encode`: --profile (exige), --resolution (seulement si le lot "
             "en porte deux au meme profil) et --version pour le rang. Aucun "
             "chemin: l'emplacement est au manifeste. Accepte "
             "--liberer-le-rang.",
    )
    # **Les MEMES `choices`, lus du MEME catalogue que ceux d'`encode`**, et
    # c'est le point : un vocabulaire derive du catalogue a un endroit et
    # recopie a l'autre est le defaut exact que la story 11.14 ferme ailleurs.
    # Pas de `default=` ici, contrairement a `encode`: un defaut ferait viser
    # le profil mezzanine a l'operateur qui a seulement oublie de le dire, et
    # detruirait une sortie qu'il ne visait pas.
    p13_remove.add_argument(
        '--profile',
        choices=sorted(codec_profiles.PROFILES),
        default=None,
        help="Profil d'encodage du master vise, tel qu'il a ete donne a "
             "`encode`. Exige avec --master: un lot porte legitimement "
             "plusieurs masters a des profils differents, et aucun n'est le "
             "defaut de cette commande.",
    )
    # Pas de `choices=` argparse, meme motif que sur `encode`: le registre
    # admet aussi une resolution personnalisee, et le refus de cette commande
    # est plus actionnable -- il NOMME les resolutions que le lot declare.
    p13_remove.add_argument(
        '--resolution',
        default=None,
        help="Resolution du master vise, telle qu'elle a ete donnee a "
             "`encode`. N'est EXIGEE que lorsqu'elle leve une ambiguite -- un "
             "lot qui porte deux resolutions du meme profil au meme rang; le "
             "refus nomme alors celles qui sont declarees. La resolution par "
             f"defaut ({encode_module.DEFAULT_RESOLUTION_ID}) se designe par "
             "son identifiant, et ne porte aucun segment dans le nom.",
    )
    p13_remove.add_argument(
        '--scan',
        metavar='SLUG-DE-FAMILLE',
        help="Retirer UN SEUL dossier de scan du lot (exige --lot), au lieu du "
             "lot entier. Le slug est le nom du dossier sous `scans/` PRIVE de "
             "son fragment de version: c'est la FAMILLE, et le rang se donne "
             "par --version (sans lui, le scan d'ORIGINE). Contrairement a "
             "--avec-scans, qui accompagne la suppression du lot, celui-ci "
             "vise le scan SEUL et laisse le lot en place. Accepte "
             "--liberer-le-rang.",
    )
    # Story 11.14 (`EPIC11-ARB-214`, `-220`, `-223`) : `--frames` designait les
    # frames **rescannees** alors que `frames` est le mot du contenu d'un LOT
    # -- c'est l'ambiguite exacte qu'Egan a nommee, et elle vivait sur une
    # interface. Le nom neuf a d'abord ete `--frames-scannees`, puis
    # `--lot-scanne` : ce que cette cible retire est le CONTENANT versionne, et
    # `EPIC11-ARB-223` a tranche « lot scanne, partout ». **Retrait pur, ni
    # alias ni refus special** : « On retire personne ne connait l'outil,
    # personne ne fera l'erreur. Attention a bien modifier les aides ! ». La
    # forme en TIRETS suit les sept autres options litterales du depot
    # (`--garder-le-scan-brut`, `--avec-scans`...) : un souligne unique se
    # lirait comme une faute plutot que comme un choix.
    p13_remove.add_argument(
        '--lot-scanne',
        dest='lot_scanne',
        action='store_true',
        help="Retirer UN SEUL lot scanne du lot (exige --lot), au "
             "lieu du lot entier. Le rang se donne par --version et porte sur "
             "la PASSE de scan (EPIC11-ARB-105), distinct du rang du lot qui "
             "vit deja dans son identifiant: sans --version c'est la passe "
             "d'ORIGINE, --version 2 et au-dela visent les rescans. La passe "
             "d'origine est donc visable, et c'est voulu -- un lot scanne "
             "d'origine est une sortie comme une autre, et le refuser "
             "laisserait sans issue qui veut le jeter. Accepte --liberer-le-rang.",
    )
    # Retour de terrain d'Egan du 2026-09-06 : « on ne peut pas retirer d'un
    # projet un jeu de frames extraites sans emporter autre chose ». Le nom
    # porte `extraites` plutot que `frames` seul, et ce n'est pas une
    # precaution de style : `--frames` est un nom RETIRE (`EPIC11-ARB-220`), et
    # `frames` seul ne dit pas de quel objet il parle -- l'ambiguite exacte que
    # la story 11.14 a passe un lot entier a vider.
    p13_remove.add_argument(
        '--frames-extraites',
        dest='frames_extraites',
        action='store_true',
        help="Retirer LE jeu de frames extraites du lot (exige --lot), au lieu "
             "du lot entier: le lot reste declare, ses masters, ses planches "
             "et ses scans restent en place. N'accepte ni --version ni "
             "--liberer-le-rang, et les refuse en le DISANT: un jeu de frames "
             "extraites n'a pas de rang propre, son dossier porte celui du lot "
             "(EPIC11-ARB-221). Viser une autre version, c'est nommer un autre "
             "lot (--lot <id>_v<rang>).",
    )
    # **`--version` ne se dispute PAS avec le `--version` du parseur racine**,
    # et c'est mesure plutot que suppose (`EPIC11-ARB-224`) : `argparse` resout
    # les options du sous-parseur en premier, si bien que `mmu --version` rend
    # toujours la version de l'outil et `mmu project remove --version 2` le
    # rang. Les formes degenerees rendent une erreur NOMMEE (code 2), jamais
    # une action silencieuse.
    p13_remove.add_argument(
        '--version',
        type=int,
        metavar='RANG',
        help="Le RANG de la version visee par la cible fine (--planche, "
             "--lot-scanne, --scan, --master). Un objet se designe par les "
             "arguments qui l'ont PRODUIT, celui-ci porte la version: c'est la "
             "meme syntaxe pour tous les objets du projet (EPIC11-ARB-224). "
             "Sans lui, la cible "
             "est le rang d'ORIGINE, qui ne porte aucun fragment "
             "(EPIC11-ARB-88). Il se lie a la cible fine comme "
             "--liberer-le-rang le fait deja; sans cible fine il est REFUSE, "
             "le rang d'un lot vivant dans son lot_id.",
    )
    p13_remove.add_argument(
        '--liberer-le-rang',
        action='store_true',
        dest='liberer_le_rang',
        help="Rendre le rang de l'objet retire, au lieu de le laisser CONSOMME "
             "(EPIC11-ARB-92). Porte sur le LOT (--lot seul) comme sur un "
             "planche (--lot --planche --version <rang>), le mecanisme etant "
             "le meme pour tous les "
             "objets versionnables (EPIC11-ARB-108). N'est possible que sur le "
             "DERNIER a date: un rang consomme par un objet posterieur ne se "
             "rend pas, sinon deux sorties porteraient le meme numero. Peut "
             "liberer PLUSIEURS rangs d'un coup quand des rangs anterieurs "
             "avaient ete retires sans l'etre. Sur un --rush, il est REFUSE "
             "nommement plutot qu'ignore: un rush n'a pas de rang de version.",
    )
    p13_remove.add_argument(
        '--avec-scans',
        action='store_true',
        dest='avec_scans',
        help="Inclure le dossier de scan lie a cet element (EPIC11-ARB-90). "
             "Consentement SEPARE de --confirmer, et pour une raison de nature: "
             "frames, masters et planches se refabriquent par calcul, un scan "
             "porte des planches papier numerisees et demande un passage au "
             "scanner. Le dossier est nomme dans l'apercu meme sans ce drapeau.",
    )
    p13_remove.add_argument(
        '--confirmer-dernier-lot',
        dest='confirmer_dernier_lot',
        action='store_true',
        help="Consentement SUPPLEMENTAIRE, exige pour vider un projet de son "
             "dernier lot ou de son dernier rush. Distinct de --confirmer: un seul "
             "drapeau pour les deux ferait de cette garde une formalite",
    )
    p13_remove.set_defaults(func=project_remove_command)

    # **Story 11.4e (`EPIC11-ARB-131`), la premiere des « autres » sous-commandes
    # que le commentaire de `project` annoncait.** Verbatim d'Egan, 2026-09-01 :
    # « C'est un peu absurde de ne pouvoir extraire que ce qui est deja la et
    # qui a donc deja ete extrait. » Avant elle, `rushes[]` n'etait ecrit que
    # par `persist_extraction`, qui exige un `ExtractionRecord` complet : un
    # rush n'entrait dans un projet qu'en etant EXTRAIT.
    #
    # **Trois options, et trois exactement.** Aucune option de cadence : la
    # declaration n'extrait rien, et une cadence cible acceptee puis ignoree
    # serait le « reste inerte » que le depot retire depuis le 2026-08-17.
    # Aucune option de nom non plus : le `rush_id` est DERIVE du nom de fichier
    # (`EPIC11-ARB-146`), jamais choisi.
    #
    # **`--force-distinct` est la troisieme, posee le 2026-09-05**
    # (`EPIC11-ARB-232`, formule par Egan). Le commentaire d'avant disait « et
    # aucun drapeau de contournement : declarer deux fois le meme rush est un
    # refus SEC (`EPIC11-ARB-147`) ». `EPIC11-ARB-231` a supersede ce point :
    # le refus porte TROIS issues, et la seconde -- « c'est un autre rush, le
    # declarer separement » -- n'a pas d'ecran en ligne de commande, donc elle
    # y prend la forme d'un drapeau explicite. Ce n'est PAS un contournement
    # d'ecrasement : il n'ecrase rien, il declare une SECONDE entree.
    # `--overwrite` a ete ecarte nommement par l'arbitrage -- il dit
    # « ecraser » et ferait ici l'inverse.
    #
    # **`allow_abbrev=False`, comme son frere `remove`** (porte le 2026-09-05,
    # sur mesure de coherence de grammaire demandee par `EPIC11-ARB-224`). Le
    # commentaire de `remove` ci-dessus le dit deja : « le parseur racine porte
    # deja le meme drapeau (`main`, `allow_abbrev=False`) ; un sous-parseur ne
    # l'herite pas. » Sans ce drapeau, `mmu project add-rush --pro P --v V`
    # etait ACCEPTE alors que `mmu project remove --pro P` etait refuse -- deux
    # sous-commandes du meme parseur `project`, deux grammaires. Mesure :
    # `test_B1_aucune_abreviation_d_option_n_est_acceptee`.
    #
    # Le motif d'`EPIC11-ARB-220` mord ici a retardement plutot qu'aujourd'hui :
    # aucune des deux options ne prolonge un nom retire pour l'instant, mais
    # c'est precisement ce que l'acceptation d'une abreviation rend invisible --
    # elle ne se paie qu'au renommage suivant, quand il est trop tard pour que
    # « argparse refuse l'ancien nom bruyamment » soit encore vrai.
    p13_add_rush = p13_sub.add_parser(
        'add-rush',
        allow_abbrev=False,
        help="Declarer un rush dans un projet ouvert SANS l'extraire: ajoute "
             "son entree a rushes[] du project.json et rien d'autre (aucun lot, "
             "aucune frame, ffmpeg jamais appele)",
    )
    p13_add_rush.add_argument('--project', required=True,
                              help='Dossier projet existant (contient project.json)')
    p13_add_rush.add_argument(
        '--video',
        required=True,
        help="Fichier video a declarer. Son identifiant est DERIVE de son nom "
             "(EPIC11-ARB-146), jamais choisi; deux rushes homonymes que les "
             "criteres techniques separent sont distingues par un suffixe de "
             "RANG -- prise01, puis prise01-2, prise01-3 (EPIC11-ARB-9 pour la "
             "levee, EPIC11-ARB-233 pour la forme du suffixe), sans question "
             "posee. Une cadence "
             "source inconnue ou inverifiable REFUSE la declaration "
             "(EPIC11-ARB-145): un rush declare sur une cadence fausse "
             "produirait des lots faux",
    )
    p13_add_rush.add_argument(
        '--force-distinct',
        action='store_true',
        help="Declarer un SECOND rush alors que les quatre criteres d'identite "
             "coincident avec un rush deja declare (nom, duree, cadence, "
             "timecode initial). Le cas reel: deux cameras jam-synchronisees, "
             "cartes formatees pareil, prise01.mov sur les deux "
             "(EPIC11-ARB-232). L'identifiant du second est leve par un rang "
             "-- prise01-2, puis prise01-3 au troisieme homonyme "
             "(EPIC11-ARB-233); rien n'est jamais ecrase et le drapeau ne "
             "bloque jamais tant que les 98 rangs ne sont pas consommes",
    )
    p13_add_rush.set_defaults(func=project_add_rush_command)

    # Story 2.8 (AC 2, `EPIC7-ARB-41`): « pouvoir le remplacer facilement » --
    # commande dediee, geste de premiere classe, gabarit repris de
    # `set-default-profile` ci-dessus.
    p12 = sub.add_parser(
        RELINK_COMMAND,
        allow_abbrev=False,
        help="Remplacer le chemin du rush source d'un projet (fichier deplace, "
             "renomme, archive), par designation manuelle ou par recherche",
    )
    p12.add_argument('--project', required=True,
                      help='Dossier projet existant (contient project.json)')
    p12.add_argument(
        '--rush',
        help="rush_id canonique tel qu'enregistre dans le manifest. Omissible si le "
             "projet ne porte qu'un seul rush",
    )
    p12_designation = p12.add_mutually_exclusive_group(required=True)
    p12_designation.add_argument(
        '--video',
        help="Fichier a designer manuellement comme nouveau chemin du rush. "
             "L'operateur est l'autorite de cette designation: un critere d'identite "
             "verifiable qui echoue refuse le relink, mais aucun critere verifiable "
             "ne le contourne jamais silencieusement",
    )
    p12_designation.add_argument(
        '--chercher',
        help="Dossier a parcourir recursivement pour retrouver le rush par ses trois "
             "criteres d'identite (nom, duree, timecode de depart). Refuse si l'une "
             "des trois references manque au manifest: la recherche ne devine jamais",
    )
    p12.set_defaults(func=relink_command)

    # Story 5.26 (FR7, `EPIC7-ARB-49`): le SECOND TEMPS du scan -- l'ecriture
    # des TIFF depuis un document de detection deja persiste par `scan detect`.
    #
    # **Commande de premier niveau, pas une sous-commande de `scan`** (question
    # ouverte 1 de la fiche, tranchee): le parent `scan` declare `--scan` et
    # `--dpi` en requis, et ce refus est fige par un test. Une sous-commande les
    # trainerait donc en requis-mais-ignores -- exactement le « reste inerte »
    # que le depot refuse depuis le 2026-08-17. Les deux valeurs vivent dans le
    # document; les redemander serait leur donner deux sources de verite.
    # Gabarit repris de `relink` ci-dessus.
    p13 = sub.add_parser(
        SCAN_WRITE_COMMAND,
        allow_abbrev=False,
        help="Ecrire les frames d'un lot a partir d'un document de detection "
             "produit par `scan detect`, sans relancer la detection",
    )
    p13.add_argument('--project', required=True,
                     help='Dossier projet existant (contient project.json)')
    p13.add_argument(
        '--detection',
        required=True,
        metavar='FICHIER',
        help="Document de detection a consommer, tel qu'ecrit par `scan detect` "
             "sous `scans/<ingest>/detections/`. Il est lu tel quel: cette "
             "commande ne redetecte jamais rien",
    )
    # **Les options d'ecriture sont celles de `scan`, lues sur les MEMES
    # constantes** (AC de la fiche): les deux voies ecrivent les memes artefacts,
    # donc un drapeau qui divergerait ferait diverger le resultat.
    p13.add_argument(
        '--overwrite',
        action='store_true',
        help="Reecrire les frames de sortie deja presentes et assumer au "
             "manifest la perte d'une frame reelle redevenue frame de "
             "remplacement. Ne leve aucun refus de planche etrangere",
    )
    p13.add_argument(
        CC_FLAG,
        dest='color_correction',
        choices=(CC_ON, CC_OFF),
        default=CC_ON,
        help="Appliquer ou non aux frames la correction couleur du lot (defaut "
             f"'{CC_ON}'). Meme regime que `scan`: a '{CC_OFF}' la correction est "
             "quand meme ajustee et mesuree au manifest, mais posee sur aucun "
             "pixel",
    )
    p13.add_argument(
        color_calibration.DIVERGENCE_BYPASS_FLAG,
        dest='divergence_bypass',
        action='store_true',
        help="Marquer explicitement qu'une planche divergente doit recevoir la "
             "correction telle quelle. Depuis la story 5.23 elle la recoit de "
             "toute facon (`EPIC5-ARB-82`); le drapeau inscrit la trace du "
             "contournement au manifest",
    )
    p13.add_argument(
        color_calibration.RAW_OUTPUT_FLAG,
        dest='keep_raw',
        action='store_true',
        # Meme frontiere negative que sur `scan` (AC 16 de 5.16): le mot qui
        # nommerait un reglage numerique est interdit dans cette aide -- une
        # phrase qui interdit le reglage mais le nomme invite a le chercher.
        help="Livrer le lot **brut**, sans poser la correction sur les pixels, "
             "et sans qu'aucune invite ne soit posee. C'est le geste explicite "
             "qui s'ecarte du defaut: on refuse une correction, on ne la dose pas",
    )
    p13.add_argument(
        PROFILE_FLAG,
        dest='profil',
        default=None,
        metavar='FICHIER',
        help="Chemin du profil de calibration a appliquer a cette ecriture. Meme "
             "regime que `scan`: valide, applique tel quel, puis verse au projet "
             f"courant. Sans cette option, le profil par defaut du projet est "
             f"utilise (`{SET_DEFAULT_PROFILE_COMMAND}`); sans defaut non plus, le "
             "lot est livre brut avec un avertissement",
    )
    p13.set_defaults(func=scan_write_command)

    p9 = sub.add_parser(
        'makepdf',
        allow_abbrev=False,
        help="Generer le PDF de planches imprimables d'un lot extrait "
             "(frames, marqueurs ArUco, QR de page, patchs de calibration)",
    )
    p9.add_argument('--project', required=True, help='Dossier projet existant (contient project.json)')
    p9.add_argument('--rush', help='rush_id canonique tel qu\'enregistre dans le manifest')
    p9.add_argument('--fps', type=float, help='Cadence cible du lot, en images par seconde (avec --rush)')
    p9.add_argument('--lot', help='lot_id direct (alternative au couple --rush/--fps)')
    p9.add_argument('--format', default=None, help='Format de page (vocabulaire: A4)')
    p9.add_argument('--orientation', default=None, help='Orientation de page (portrait ou paysage, defaut portrait)')
    # Aide **derivee du registre**, jamais enumeree a la main (`EPIC5-ARB-64`, passe de
    # correction du 2026-08-12): le vocabulaire depend desormais de l'orientation **et**
    # de la version, et l'enumeration ecrite ici annoncait encore `6` dans les deux
    # orientations -- juste en paysage, faux en portrait depuis que la v2 est le defaut.
    # Un cardinal retire d'une orientation disparait maintenant de l'aide sans qu'on y
    # pense, comme pour `--geometrie` et `--nombre-patchs`.
    _vocabulaire_frames = "; ".join(
        f"{orientation}: "
        + ", ".join(
            str(cardinal) for cardinal in page_templates.frames_per_page_vocabulary(
                orientation)
        )
        for orientation in page_templates.ORIENTATIONS
    )
    p9.add_argument(
        '--frames-par-page',
        dest='frames_par_page',
        type=int,
        default=None,
        help=(
            f"Frames par page en geometrie {page_templates.DEFAULT_GEOMETRY_VERSION} "
            f"({_vocabulaire_frames}); defaut "
            f"{page_templates.DEFAULT_FRAMES_PER_PAGE}. Le vocabulaire depend de la "
            "geometrie et de l'orientation: un refus nomme le motif chiffre du retrait "
            "et le cardinal a employer a la place."
        ),
    )
    p9.add_argument(
        '--marge',
        default=None,
        help='Preset discret de marge de recadrage en mm (0, 2 ou 5; defaut 0)',
    )
    # Story 5.15, passe de correction du 2026-08-11: `compose_lot_plan` acceptait
    # `geometry_version` sans qu'aucun chemin operateur ne le porte, si bien que la
    # version **non par defaut** etait inatteignable autrement qu'en Python. Ce n'est
    # pas une commodite: sous la v2 le couple `paysage x patches-18-v2` n'a aucun
    # placement (151 mm de couloir lateral pour 159 exiges -- 154 etait le chiffre
    # d'avant le recalcul de `_derived_row_capacity`, qui oubliait l'espacement de
    # tete), donc sans ce drapeau une combinaison que la CLI accepte encore
    # echouerait sans issue. Aide **derivee du
    # registre** comme celle de `--nombre-patchs`, jamais enumeree a la main: une
    # version ajoutee au registre apparait dans l'aide sans qu'on y pense.
    p9.add_argument(
        '--geometrie',
        default=None,
        help=(
            "Version de geometrie de page, par identifiant ("
            + ", ".join(page_templates.GEOMETRY_VERSIONS)
            + f"); defaut {page_templates.DEFAULT_GEOMETRY_VERSION}. La version est "
            "portee par le template_id de la planche et relue au scan: elle n'est "
            "donc jamais devinee, et une planche imprimee reste redressable. La v2 "
            "resserre la page (marqueurs de 15 mm, marge de 8 mm, pastilles de "
            "6 mm); ses valeurs sont arretees par la passe de design de la story "
            "5.18 (EPIC5-ARB-61), et toute evolution passera par une v3 plutot que "
            "par une redefinition de la v2."
        ),
    )
    p9.add_argument(
        '--dpi',
        type=int,
        default=None,
        help='DPI de rasterisation des elements embarques dans le PDF (defaut 600; '
             'distinct de la consigne de scan, qui reste 600 dpi)',
    )
    p9.add_argument(
        '--nombre-patchs',
        dest='nombre_patchs',
        default=None,
        # L'aide est **derivee du registre**, jamais enumeree a la main: elle
        # annoncait `patches-9-v1` et `patches-12-v1` alors que `patches-18-v2`
        # etait deja accepte par `resolve_patch_preset` depuis la story 5.9.
        # Consequence reelle, constatee le 2026-08-10: le seul preset qui porte
        # les sentinelles de gamut -- donc le seul sur lequel le verdict
        # d'ecretage de 5.4b soit calculable -- etait invisible a l'operateur.
        #
        # **La phrase des sentinelles est derivee elle aussi depuis la passe de
        # correction de 5.16** (bloquant B4): elle etait ecrite en dur -- « seul
        # patches-18-v2 porte les sentinelles » -- et 5.16 l'a rendue fausse en
        # livrant `patches-14-v3`, qui porte ses huit sentinelles. Fausse dans le
        # sens le plus couteux: `patches-18-v2` est refuse sur les quinze gabarits
        # paysage v2, et son refus propose alors `--geometrie v1`, c'est-a-dire de
        # renoncer a toute la surface gagnee par 5.15 et 5.18, quand la bonne
        # reponse est le preset que 5.16 vient de livrer. Un litteral au milieu
        # d'une aide derivee vieillit sans que rien ne le dise.
        help=_aide_nombre_patchs(),
    )
    p9.add_argument(
        '--gamut-map',
        dest='gamut_map',
        default=None,
        help="Compression de gamut appliquee aux frames, par identifiant "
             f"({', '.join(gamut_map.known_gamut_map_ids())}); defaut "
             f"{pdf_composition.DEFAULT_GAMUT_MAP} (aucune compression). "
             "La compression reelle s'active explicitement: la decompression "
             "G^-1 est post-MVP (story 5.4b), donc un defaut comprimant "
             "produirait des exports delaves que rien ne redresse. Aucun "
             "parametre numerique n'est expose: les parametres d'une "
             "compression vivent dans le registre versionne, sinon une planche "
             "imprimee n'est plus resolvable depuis son seul identifiant.",
    )
    p9.add_argument(
        '--overwrite',
        action='store_true',
        help='Remplacer un PDF deja present sous planches/ (jamais implicite)',
    )
    p9.add_argument(
        '--nouvelle-version',
        action='store_true',
        dest='nouvelle_version',
        help="Reponse au conflit residuel: imprimer un tirage VOISIN au lieu "
             "d'ecraser celui deja present (EPIC11-ARB-91). Le rang apparait "
             "dans le nom du PDF, sur la planche elle-meme (en-tete) et dans "
             "son QR: une feuille imprimee a quitte le disque, et un nom de "
             "fichier ne la distingue plus d'un autre tirage une fois sur le "
             "bureau. Depuis EPIC11-ARB-175 le rang avance a CHAQUE tirage, "
             "que ce drapeau soit passe ou non: il est donc sans effet dans le "
             "cas nominal, jamais refuse.",
    )
    p9.set_defaults(func=makepdf_command)

    # Story 5.22, AC 8. Meme pattern que `scan calibrate` (et que `poc` avant
    # lui): un `add_subparsers` **non requis** sur le parser existant, donc
    # `makepdf --project P --lot L` garde exactement son comportement -- la
    # sous-commande s'ajoute, elle ne s'interpose pas.
    #
    # Toutes les options de geometrie sont portees par le parent et donc
    # partagees: c'est le point, pas une economie. La page de calibration doit
    # declarer dans son QR le **meme** `template_id` que les planches du lot,
    # sinon `scan calibrate` resout un autre treillis et echantillonne les
    # pastilles a cote. Un jeu d'options duplique sur la sous-commande aurait
    # rendu ce desaccord exprimable.
    makepdf_sub = p9.add_subparsers(dest='makepdf_subcommand')
    p9_calibration = makepdf_sub.add_parser(
        'calibration-page',
        allow_abbrev=False,
        help="Generer la page de calibration d'une chaine de scan, a la demande: "
             "elle s'imprime, se scanne une fois, et `scan ... calibrate` en tire "
             "le profil de la chaine. Elle n'est plus inseree automatiquement dans "
             "chaque lot (EPIC5-ARB-80), et elle ne demande ni rush, ni lot, ni "
             "cadence (story 5.23): elle se genere AVANT toute extraction",
    )
    # **Obligatoire, et c'est le seul argument de cette sous-commande.** Une page de
    # calibration anonyme ne se distinguerait pas d'une autre: un projet en porte
    # autant que de chaines de scan, et c'est le libelle qui les separe -- sur la
    # feuille, dans le nom du fichier et, depuis le 2026-08-18, dans le QR.
    p9_calibration.add_argument(
        '--chaine',
        dest='chaine',
        required=True,
        metavar='LIBELLE',
        help="Nom de la chaine de scan, tel que l'operateur la designe: scanner, "
             "format, resolution, reglages. Exemple: \"hp envy 4520 tiff 600 dpi "
             "auto corr off\". Verbeux assume, "
             f"{payload_io.SCAN_CHAIN_LABEL_MAX_LENGTH} caracteres au maximum "
             "(il s'imprime verbatim sur la feuille et voyage dans son QR)",
    )
    p9_calibration.add_argument(
        '--commentaire',
        dest='commentaire',
        default=None,
        metavar='TEXTE',
        help="Commentaire libre sur la chaine, imprime sur la feuille "
             f"({pdf_composition.SCAN_CHAIN_COMMENT_MAX_LENGTH} caracteres au "
             "maximum). Facultatif. Il n'entre PAS dans le QR: c'est de la prose "
             "destinee au lecteur humain de la feuille",
    )
    p9_calibration.set_defaults(func=makepdf_calibration_page_command)

    # Story 3.6. Aucun `--project`: cette commande ne connait pas la notion de
    # projet, ne cree aucune arborescence, n'ouvre aucun journal sous `logs/`
    # et n'ecrit aucun manifest.
    #
    # **Nomme `p10` et non `p8` reutilise** (finding de la deuxieme passe de revue,
    # `EPIC5-ARB-78`, 2026-08-14): `p8` designe deja le sous-parseur `scan` juste
    # au-dessus (ou `--cc` est pose, ~ligne 2444-2528). Le reutiliser ici pour `previz`
    # etait legal -- Python n'y voit qu'une reassignation locale -- mais un futur ajout
    # d'option qui viserait `scan` en pensant que `p8` designe encore ce parseur
    # atterrirait silencieusement sur `previz`. Le renommage local ferme ce risque sans
    # rien changer au comportement.
    p10 = sub.add_parser(
        'previz',
        allow_abbrev=False,
        help="Previsualiser un rush a une ou plusieurs cadences reduites, sans rien extraire",
    )
    p10.add_argument('--video', required=True, help='Fichier video source (rush)')
    p10.add_argument(
        '--fps',
        type=float,
        action='append',
        required=True,
        help="Cadence cible a previsualiser, en images par seconde (repetable: "
             "--fps 3 --fps 5 --fps 12.5 compare trois cadences en une session)",
    )
    p10.add_argument(
        '--height',
        type=int,
        default=cadence_previz.DEFAULT_PREVIEW_HEIGHT,
        help="Hauteur d'affichage en pixels, posee avant la lecture "
             f"(defaut: {cadence_previz.DEFAULT_PREVIEW_HEIGHT})",
    )
    # Story 3.7. Memes options et memes `dest=` que sur `extract`: c'est la
    # meme fenetre, calculee par le meme noyau. A distinguer de --start /
    # --duration juste apres, qui ne changent jamais ce qui est retenu.
    p10.add_argument(
        '--in',
        dest='in_timecode',
        default=None,
        metavar='TIMECODE',
        help="Borne d'entree de l'extrait previsualise, en timecode source "
             "hh:mm:ss:ff. Change quelles images sont RETENUES, exactement comme "
             "le --in de la commande extract",
    )
    p10.add_argument(
        '--out',
        dest='out_timecode',
        default=None,
        metavar='TIMECODE',
        help="Borne de sortie de l'extrait previsualise, meme base de temps que "
             "--in et incluse dans l'extrait",
    )
    p10.add_argument(
        '--start',
        type=float,
        default=None,
        help="Debut de la plage previsualisee, en secondes depuis le debut du rush. "
             "Ne change PAS quelles images sont retenues (c'est le role de --in / "
             "--out): seule la plage jouee dans cette session est restreinte",
    )
    p10.add_argument(
        '--duration',
        type=float,
        default=None,
        help='Duree de la plage previsualisee, en secondes',
    )
    p10.add_argument(
        '--on-late',
        dest='on_late',
        choices=list(cadence_previz.ON_LATE_POLICIES),
        default=cadence_previz.ON_LATE_REPORT,
        help="Comportement en cas de retard: 'report' presente toutes les frames "
             "retenues et chiffre l'ecart (defaut), 'skip' omet les frames deja en "
             "retard pour preserver le tempo percu et le declare",
    )
    p10.add_argument(
        '--memory-budget-mb',
        dest='memory_budget_mb',
        type=float,
        default=cadence_previz.DEFAULT_MEMORY_BUDGET_MB,
        help="Budget memoire du cache de frames decodees, en Mio "
             f"(defaut: {cadence_previz.DEFAULT_MEMORY_BUDGET_MB})",
    )
    p10.add_argument(
        '--no-display',
        dest='no_display',
        action='store_true',
        help="Cadencer et mesurer sans ouvrir de fenetre (integration continue, "
             "machine sans affichage)",
    )
    p10.set_defaults(func=previz_command)

    p5 = sub.add_parser('poc', allow_abbrev=False,
                        help='Orchestration POC de bout en bout')
    poc_sub = p5.add_subparsers(dest='poc_command')

    p5_build_sheet = poc_sub.add_parser(
        'build-sheet',
        allow_abbrev=False,
        help="Extraire les frames d'une video et generer la planche PDF imprimable (2 frames, cibles ArUco)",
    )
    p5_build_sheet.add_argument('--project', required=True, help='Dossier projet cible')
    p5_build_sheet.add_argument('--video', required=True, help='Fichier video source (16:9, ex: 1920x1080)')
    p5_build_sheet.add_argument('--fps', type=float, default=2.0, help='FPS pour l’extraction de frames')
    p5_build_sheet.add_argument('--dpi', type=int, default=300, help='DPI cible pour le gabarit imprimable')
    p5_build_sheet.set_defaults(func=poc_build_sheet)

    p5_process_scan = poc_sub.add_parser(
        'process-scan',
        allow_abbrev=False,
        help="Detecter, redresser et decouper un scan de la planche imprimee (2 frames rescanees)",
    )
    p5_process_scan.add_argument('--project', required=True, help='Dossier projet cible')
    p5_process_scan.add_argument('--scan', required=True, help='Fichier scan image (png/jpg/tiff, 8 ou 16 bits)')
    p5_process_scan.add_argument('--dpi', type=int, default=300, help='DPI cible pour la detection et le deskew')
    p5_process_scan.set_defaults(func=poc_process_scan)

    p6 = sub.add_parser(
        'reconstruct-project',
        allow_abbrev=False,
        help="Reconstruire un projet local depuis des payloads de page decodes (QR) et un manifest partiel optionnel",
    )
    p6.add_argument('--project', required=True, help='Dossier projet cible (cree si absent)')
    p6.add_argument(
        '--payload',
        dest='payloads',
        action='append',
        required=True,
        help='Fichier contenant le texte exact du QR d une page: schema 2.0, cles '
             'courtes, tel qu un decodeur le rend (repetable, un par page disponible)',
    )
    p6.add_argument('--manifest', help='Manifest local partiel existant (project.json), optionnel')
    p6.set_defaults(func=poc_reconstruct_project)

    args = parser.parse_args(argv)
    if not hasattr(args, 'func'):
        parser.print_help()
        return 2
    return args.func(args)

if __name__ == '__main__':
    sys.exit(main())
