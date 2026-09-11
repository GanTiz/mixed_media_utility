"""Ecriture des frames rescannees vers `output-frames/` (story 5.6).

Point de sortie de l'Epic 5 vers l'Epic 6. Ce module consomme les frames
decoupees par 5.3 et l'identite portee par le QR de chaque page, et ecrit des
fichiers sur disque sous
`output-frames/<slug-de-lot>/scan_<rush>_<fps>_<timecode>.tiff`, en TIFF 16
bits. Il n'ecrit pas le manifest (5.7), ne detecte pas (5.2), ne decoupe pas
(5.3), n'affiche rien (5.8) et ne calcule aucune correction couleur (5.4).

Le nom de fichier est le seul support d'identite
------------------------------------------------
Les fichiers de sortie **voyagent seuls**: l'operateur qui reconstruira la
video peut n'avoir recu que le dossier, sans manifest partage ni chemin local
commun. Tout ce qui identifie une frame doit donc etre reconstructible depuis
le payload QR de sa page: le dossier (AC 2) et le nom (AC 1). C'est la raison
pour laquelle aucun suffixe de desambiguisation n'est jamais invente ici -- un
timecode duplique est refuse (AC 4), jamais rattrape.

Ce que le QR permet de reconstruire, et ce qu'il ne permet pas
--------------------------------------------------------------
Le payload porte `rush_id`, `fps_target`, `lot_id`, `template_id`,
`page_index`, `page_count` et le mapping `slot_index -> frame_timecode`. Il ne
porte **ni** `source_in_timecode` **ni** `source_out_timecode`, dont depend
pourtant le nom de dossier d'un lot borne: la derivation passe donc par la
comparaison du `lot_id` recu au `lot_id` non borne recalcule
(`derive_lot_dir_slug`). Il ne porte pas non plus `rounding_policy`,
`timecode_base` ni `source_frame_count`: aucun timecode n'est donc
recalculable pour une page absente, ce qui borne la portee de la frame de
remplacement (EPIC5-ARB-8, voir `build_missing_frame_image`).

La frame de remplacement (EPIC5-ARB-8 et EPIC5-ARB-19)
-------------------------------------------------------
Une page **presente et decodee** dont la geometrie (5.2) ou la decoupe (5.3) a
echoue produit une frame de remplacement: damier achromatique portant
« FRAME MANQUANTE » et une seconde ligne `page <n>/<total> - <timecode>`. Elle
garde la continuite de sequence attendue par l'`encode` sans risquer d'etre
prise pour une image du film. Une page **absente** ou a QR illisible n'en
produit aucune -- son timecode est inconnu et l'inventer serait deviner: elle
reste un trou declare.

Le motif du damier et la recette d'incrustation de texte ne sont **pas**
importes de leur fichier d'origine (l'un est un script de recherche, l'autre
une methode privee liee a une fenetre d'affichage): c'est la **recette** qui
est reprise, avec la reference croisee ci-dessous pour que les deux ne
divergent pas en silence.

- damier: `scripts/archive/research/aruco_robustness_experiment.py`, corpus `damier`,
  mesure a 0 faux positif ArUco sur quatre dictionnaires
  (`_bmad-output/test-artifacts/aruco-robustness-results.md`);
- texte: `cadence_previz.CvWindowSink._draw_text` -- contour noir epais puis
  remplissage blanc fin, seule recette du depot dont la raison d'etre
  documentee est « lisible sur n'importe quel fond », exactement la contrainte
  d'un damier qui a des cellules noires **et** blanches. Ses constantes
  (`_FONT_SCALE = 0.7`, epaisseurs 4 et 1) sont calibrees pour une fenetre de
  la taille d'un ecran: elles sont **derivees** ici de la hauteur de frame, et
  non recopiees (piege 11 de la story).

Marquage synthetique
--------------------
Chaque entree du rapport porte `synthetic` (toujours present, y compris a
`false`) et, si et seulement si elle est synthetique, `synthetic_reason` d'un
vocabulaire ferme. Le lot porte `synthetic_frame_count`, et un lot qui en
compte n'est **jamais** declare complet. C'est le contrat que 5.7 (manifest) et
5.8 (previz) reprennent; il se pose ici, une seule fois.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from . import color_pipeline, page_roles, page_templates, progression, scan_crop
from .extraction_previz import FINGERPRINT_PREFIX, canonical_json, fingerprint_of
from .io import naming, payload as payload_io, project_layout, version_ranks
from .io.extraction_manifest import ExtractionPersistenceError, _relative_posix
from .io.manifest import _iter_absolute_path_violations
from .numeric_guards import is_strict_int

#: Vocabulaire **ferme** des motifs de frame de remplacement (AC 14). Les deux
#: motifs sont distinguables a ce niveau: le premier vient du document de
#: detection de 5.2 (page ingeree, QR lu, geometrie non resolue), le second du
#: plan de decoupe de 5.3 (zone degeneree ou hors page). Toute extension est un
#: ajout explicite, jamais une chaine libre glissee au passage (EPIC4-ARB-1).
SYNTHETIC_FRAME_REASONS: tuple[str, ...] = (
    "page_detection_failed",
    "frame_crop_failed",
)

#: Vocabulaire **ferme** des avertissements d'ecriture. Distinct de ceux de
#: l'ingestion (5.1), de la detection (5.2) et du recadrage (5.3): quatre
#: vocabulaires voisins fusionnes seraient quatre contrats melanges.
#:
#: `SYNTHETIC_FRAME_WRITTEN` est celui que la previz (5.8) **transporte** depuis
#: ce rapport, elle ne le deduit pas.
#:
#: Deux codes ont ete renommes a la passe de correction du 2026-08-08:
#:
#: - `PAGE_WITHOUT_PAYLOAD` -> `PAGE_QR_UNREADABLE`. Les deux nommaient le meme
#:   fait dans deux vocabulaires fermes voisins: 5.8 (son AC 9) declare
#:   `PAGE_QR_UNREADABLE` et exige que ses codes soient **transportes** depuis
#:   l'appelant. Deux noms auraient impose une table de traduction, c'est-a-dire
#:   exactement l'homonymie divergente que `SCAN_PREVIZ_WARNING_CODES` a ete
#:   nommee pour eviter. On reconcilie avant que 5.8 ne fige sa constante.
#: - `UNEXPECTED_FILE_IN_OUTPUT_DIR` -> `PREEXISTING_FRAME_IN_OUTPUT_DIR`. Un
#:   nom **conforme** appartient par construction a la convention de ce lot
#:   (il se reconstruit avec son `rush_id` et sa cadence): ce n'est donc jamais
#:   un fichier etranger, mais une frame acquise a une passe anterieure. Le
#:   code d'origine se declenchait sur le chemin nominal de la seconde passe
#:   complementaire -- et un code qui sonne sur le chemin nominal est un code
#:   qu'on apprend a ignorer.
SCAN_OUTPUT_WARNING_CODES: tuple[str, ...] = (
    "SYNTHETIC_FRAME_WRITTEN",
    "SYNTHETIC_FRAME_SHAPE_INDETERMINABLE",
    "EXPECTED_FRAME_COUNT_INDETERMINABLE",
    "HETEROGENEOUS_FRAME_SHAPES",
    "PAGE_MISSING_FROM_LOT",
    "PAGE_QR_UNREADABLE",
    "PAGE_SLOT_COUNT_BELOW_TEMPLATE",
    "OUTPUT_FRAME_OVERWRITTEN",
    "NONCONFORMING_FILE_IN_OUTPUT_DIR",
    "PREEXISTING_FRAME_IN_OUTPUT_DIR",
    "EXPECTED_FRAME_FILE_MISSING",
)

#: Texte de premiere ligne de la mire. **ASCII strict** (piege 8):
#: `cv2.putText` avec `FONT_HERSHEY_SIMPLEX` ne rend pas les caracteres
#: accentues -- ils sortent en glyphe vide. Ne pas l'enrichir d'un libelle
#: accentue.
MISSING_FRAME_TEXT = "FRAME MANQUANTE"

#: Valeur haute d'un canal 16 bits. Le damier et le remplissage du texte
#: utilisent les deux extremes (0 et cette valeur) et jamais un gris
#: intermediaire: le livrable final est une video, et un contraste median ne
#: survit pas au sous-echantillonnage chroma.
MAX_LEVEL_16BIT = 65535

#: Valeur haute d'un canal 8 bits, et facteur de promotion vers 16 bits.
#:
#: La mire se **construit** en 8 bits et se promeut en 16 a la derniere ligne.
#: Ce n'est pas un choix esthetique: `cv2.putText` n'accepte qu'un canevas
#: `CV_8U` (verifie sur OpenCV 5, assertion `img.depth() == CV_8U`), donc le
#: texte ne peut pas etre incruste directement dans un tableau 16 bits. La
#: promotion est la **meme recette** que celle de `color_pipeline` (`x257`), et
#: les deux niveaux extremes y restent exacts: 0 -> 0 et 255 -> 65535.
#:
#: La promotion a lieu **ici**, jamais en laissant `export_frame_tiff16` la
#: faire: recevoir un `uint8` lui ferait declarer `source_bit_depth: 8`,
#: c'est-a-dire un scan 8 bits qui n'existe pas (piege 9).
MAX_LEVEL_8BIT = 255
BIT_DEPTH_PROMOTION_FACTOR = 257

#: Nombre de rangees de cellules visees sur la hauteur de la frame. La taille
#: de cellule est **proportionnelle a la hauteur**, jamais une constante en
#: pixels: une zone de gabarit 8 frames/page mesure 166 px de haut a 300 ppp la
#: ou une zone 1 frame/page en mesure plus de dix fois plus, et un damier trop
#: fin moire apres sous-echantillonnage chroma a l'encodage.
CHECKER_ROWS = 6

#: Plancher de taille de cellule. En dessous, le damier n'est plus un motif
#: reconnaissable mais du bruit.
MIN_CHECKER_CELL_PX = 16

#: Nombre de canaux d'une frame de remplacement quand **aucune** frame reelle
#: du lot n'a pu etre observee. Le plan de decoupe de 5.3 declare un rectangle,
#: donc une hauteur et une largeur, mais pas un nombre de canaux; et la chaine
#: scan est en BGR trois canaux de bout en bout (`color_pipeline`). Ce n'est
#: donc pas un arbitrage a la volee sur la **forme** au sens de l'AC 13
#: (hauteur et largeur restent reprises, jamais devinees), c'est la seule
#: valeur que le plan ne porte pas.
DEFAULT_SYNTHETIC_CHANNELS = 3

# --- constantes de trace du texte, derivees et non recopiees ---------------
#
# Reference: `cadence_previz.CvWindowSink`, `_FONT_SCALE = 0.7` avec un contour
# d'epaisseur 4 et un remplissage d'epaisseur 1. Les trois valeurs ne sont
# utilisees ici que comme **point de reference d'une derivation**: a echelle
# 0.7 la derivation rend exactement 4 et 1, et en dessous elle reduit les deux
# epaisseurs en conservant leur rapport, avec un plancher de 1 px chacune.
# Garder 4 et 1 en constantes ferait avaler le remplissage par le contour des
# que le texte reduit (piege 11), et la seconde ligne -- plus longue donc plus
# petite -- tomberait la premiere.
_TEXT_FONT = cv2.FONT_HERSHEY_SIMPLEX
_REFERENCE_FONT_SCALE = 0.7
_REFERENCE_OUTLINE_THICKNESS = 4
_REFERENCE_FILL_THICKNESS = 1

#: Part de la largeur de frame que la **plus longue** des deux lignes occupe.
#: La largeur est mesuree par `cv2.getTextSize` avant trace, jamais estimee:
#: c'est ce qui interdit la troncature silencieuse.
_TEXT_WIDTH_RATIO = 0.86

#: Part de la hauteur de frame que le bloc des deux lignes occupe au plus.
#: Sans ce plafond, une frame tres large et peu haute recevrait un texte plus
#: haut qu'elle.
_TEXT_BLOCK_HEIGHT_RATIO = 0.45

#: Interligne, en fraction de la hauteur d'une ligne.
_TEXT_LINE_GAP_RATIO = 0.5


class ScanOutputError(RuntimeError):
    """Base attrapable des echecs propres a l'ecriture des frames de sortie."""


class LotInconsistencyError(ScanOutputError):
    """Les pages ne decrivent pas le meme lot.

    Ecrire quand meme melangerait deux lots dans un dossier unique, sous des
    noms qui ne diraient pas lequel est lequel.
    """


class DuplicateFrameTimecodeError(ScanOutputError):
    """Deux frames du lot produiraient le meme nom de fichier.

    Le nom ne porte que le rush, la cadence et le timecode: deux slots de pages
    differentes portant le meme `frame_timecode` s'ecraseraient en silence, et
    une frame serait perdue sans qu'aucun compteur ne bouge. Le payload impose
    l'unicite de `slot_index` **dans une page**, rien au niveau du lot.

    Ce n'est pas un conflit de nommage a rattraper: c'est le symptome d'un lot
    corrompu ou de deux lots melanges (risque R12).
    """


class OutputFrameExistsError(ScanOutputError):
    """Un fichier de sortie existe deja et `overwrite` n'a pas ete demande."""


class FrameShapeConflictError(ScanOutputError):
    """Deux formes divergentes coexistent la ou une seule est utilisable.

    L'`encode` de l'Epic 6 suppose une sequence de dimensions identiques: une
    frame de taille differente casse l'encodage aussi surement qu'un trou.
    Choisir l'une des deux formes serait un arbitrage a la volee.
    """


def validate_warning_code(code: str) -> str:
    if code not in SCAN_OUTPUT_WARNING_CODES:
        raise ValueError(
            f"Code d'avertissement d'ecriture inconnu: {code!r}. Vocabulaire "
            f"ferme: {', '.join(SCAN_OUTPUT_WARNING_CODES)}."
        )
    return code


def validate_synthetic_reason(reason: str) -> str:
    if reason not in SYNTHETIC_FRAME_REASONS:
        raise ValueError(
            f"Motif de frame synthetique inconnu: {reason!r}. Vocabulaire "
            f"ferme: {', '.join(SYNTHETIC_FRAME_REASONS)}."
        )
    return reason


# --- derivation du dossier de sortie depuis le QR seul (AC 2) ---------------


def derive_lot_dir_slug(*, rush_id: str, fps_target: float | int, lot_id: str) -> str:
    """Rendre le slug du dossier de sortie du lot, depuis le payload QR seul.

    Le probleme: `project_layout.rush_dir_slug` ajoute, pour un lot borne, le
    condensat de `naming.bounds_suffix(source_in_timecode, source_out_timecode)`
    -- or **aucune** de ces deux bornes n'est dans le payload QR. Le dossier
    serait donc introuvable au moment de l'`encode` si on tentait de le
    recalculer depuis les bornes.

    La derivation existe pourtant, par une invariante du depot:

    - on recalcule le `lot_id` **non borne** candidat,
      `derive_short_id(f"{rush_id}_{fps_short}")`;
    - si le `lot_id` recu lui est egal, le lot est non borne et le slug est
      `rush_dir_slug(rush_id, fps_target)` -- qui, lui, ne raccourcit pas: au
      dela de `CANONICAL_ID_MAX_LENGTH`, `lot_id` porte un derive court et le
      dossier le nom entier, et c'est le dossier qui fait foi;
    - sinon le lot est borne, et le `lot_id` **est** le slug, verbatim.

    La seconde branche tient parce que `naming.build_lot_id` **refuse a
    l'entree** toute extraction bornee dont l'identifiant complet depasse
    `CANONICAL_ID_MAX_LENGTH` (garde de la revue du 2026-08-06, arbitrage
    d'Egan option c): un `lot_id` borne n'est donc jamais raccourci, et vaut
    exactement `rush_dir_slug`. Cette invariante est verrouillee par un test
    nomme, qui dit que la reconstruction depuis le QR en depend -- sans quoi un
    assouplissement de la garde produirait des dossiers introuvables un an plus
    tard, sans qu'aucun test ne tombe.

    Les deux branches ne peuvent pas se confondre: un `lot_id` borne vaut
    `f"{rush_id}_{fps_short}-{condensat}"`, neuf caracteres de plus que le
    candidat non borne, et ne peut donc lui etre egal.

    Deux gardes ajoutees a la passe de correction du 2026-08-08
    -----------------------------------------------------------
    Le `lot_id` vient du **QR d'une feuille de papier**: une planche d'un autre
    outil, une version future du format ou un decodage corrompu peuvent y
    mettre n'importe quoi. Rendu verbatim comme slug, il devient un composant
    de chemin, et `Path(projet) / "output-frames" / "/tmp/x"` vaut `/tmp/x` --
    pathlib abandonne la partie gauche devant un composant absolu. Mesure a la
    revue: un TIFF 16 bits ecrit **hors du dossier projet** avant que le filet
    de publication ne se tende, et un `lot_id` portant un simple `/` accepte en
    silence sous une arborescence imbriquee ou l'`encode` ne cherchera jamais.

    1. Le `lot_id` passe par `naming.validate_manifest_identifier`, qui est
       l'implementation unique de la regle « identifiant canonique » du depot:
       le pattern `^[A-Za-z0-9_-]+$` exclut par construction `/`, `\\`, `..`,
       l'absolu et l'espace. Le module delegue la validation du payload a son
       autorite (`io.payload`), mais cette autorite ne controle sur `lot_id`
       qu'une chaine non vide: la delegation portait donc sur une garde qui
       n'existe pas.
    2. Dans la branche bornee, le `lot_id` doit **porter** le rush et la
       cadence du payload courant (`f"{rush_id}_{fps_short}-"`). La docstring
       affirmait deja cette forme; il s'agit de la verifier au lieu de la
       supposer. Sans elle, toute incoherence interne au payload entre
       `lot_id` et `fps_target` (ou `rush_id`) etait silencieusement traduite
       en « lot borne »: mesure a la revue, des frames nommees a 24 fps
       ecrites dans le dossier du lot 5 fps du meme rush, `complete: true`,
       zero avertissement -- le scenario que `LotInconsistencyError` decrit
       mot pour mot, atteint par un chemin que la garde ne couvrait pas.
    """
    if not isinstance(rush_id, str) or not rush_id:
        raise ScanOutputError(
            f"rush_id invalide pour la derivation du dossier de sortie: {rush_id!r}"
        )
    try:
        # LECTURE d'un identifiant deja imprime sur une planche : la borne
        # tolerante, pas celle de creation (`EPIC11-ARB-110`, revue vague 3).
        naming.validate_manifest_identifier(
            lot_id, label="lot_id du payload QR",
            longueur_max=naming.LEGACY_ID_MAX_LENGTH)
    except naming.NamingError as error:
        raise ScanOutputError(
            f"lot_id invalide pour la derivation du dossier de sortie: {error}. "
            "Le lot_id du QR devient un composant de chemin: un identifiant "
            "hors du pattern canonique ecrirait hors du dossier projet ou sous "
            "une arborescence imbriquee."
        ) from error
    fps_short = naming.format_fps_short(fps_target)
    candidate = naming.derive_short_id(f"{rush_id}_{fps_short}")
    if lot_id == candidate:
        return project_layout.rush_dir_slug(rush_id, fps_target)
    # **Le candidat de l'EPOQUE, pas seulement celui d'aujourd'hui** (trouve en
    # revue, couche 2, vague 3). `derive_short_id` raccourcit a la borne
    # COURANTE : un lot cree quand elle valait 64 porte un `lot_id` non
    # raccourci de 49 a 64 caracteres, que le recalcul d'aujourd'hui ne
    # retrouve plus. Sans cette seconde comparaison, la planche imprimee de ce
    # lot etait refusee « ne porte ni le rush ni la cadence » -- apres que
    # l'operatrice l'avait imprimee et passee au scanner, c'est-a-dire au pire
    # moment, et pour un lot que l'outil avait lui-meme nomme.
    if naming.LEGACY_ID_MAX_LENGTH > naming.CANONICAL_ID_MAX_LENGTH:
        ancien = naming.derive_short_id(
            f"{rush_id}_{fps_short}", max_length=naming.LEGACY_ID_MAX_LENGTH)
        if lot_id == ancien:
            return project_layout.rush_dir_slug(rush_id, fps_target)
    # Deux prefixes seulement, et chacun designe un axe de nommage qui
    # **interdit le raccourcissement** a `naming.build_lot_id` -- c'est ce qui
    # autorise a rendre le `lot_id` verbatim comme slug :
    #
    #   `-`   suffixe de bornes (story 3.7), refus de longueur a l'entree ;
    #   `_v`  rang de version (story 5.29), refus de longueur a l'entree aussi.
    #
    # **Le second manquait, et le circuit etait coupe** (revue Opus du
    # 2026-08-30) : une version 2 s'extrayait et s'imprimait, puis `scan` la
    # refusait avec un message qui accusait son `lot_id` d'etre malforme --
    # apres que l'operatrice avait imprime et passe les planches au scanner.
    # Le travail physique etait deja engage quand le defaut se revelait.
    prefixes = (f"{rush_id}_{fps_short}-", f"{rush_id}_{fps_short}_v")
    if not lot_id.startswith(prefixes):
        raise LotInconsistencyError(
            f"Le lot_id {lot_id!r} ne porte ni le rush {rush_id!r} ni la cadence "
            f"{fps_short!r} du payload, et ne vaut pas non plus le lot_id non "
            f"borne recalcule ({candidate!r}). Un lot borne vaut "
            f"'{rush_id}_{fps_short}-<condensat>' et un lot versionne "
            f"'{rush_id}_{fps_short}[-<condensat>]_v<rang>' par construction "
            "(`naming.build_lot_id`): un lot_id qui ne suit pas cette forme "
            "ferait ecrire ces frames dans le dossier d'un autre lot, sous des "
            "noms qui ne diraient pas lequel est lequel."
        )
    return lot_id


# --- la frame de remplacement (AC 13) ---------------------------------------


def build_checkerboard(height: int, width: int, cell_px: int) -> np.ndarray:
    """Damier achromatique `uint8`, aux deux niveaux extremes.

    Huit bits parce que le texte s'incruste ensuite dessus et que `cv2.putText`
    n'accepte pas d'autre profondeur; la promotion en 16 bits est la derniere
    etape de `build_missing_frame_image` (voir `BIT_DEPTH_PROMOTION_FACTOR`).

    Sept lignes de `numpy`, comme le corpus `damier` du banc de robustesse
    ArUco: il se genere a n'importe quelle taille -- donc valide pour les 33
    gabarits sans table de correspondance -- et n'ajoute aucun asset binaire a
    versionner. C'est aussi le seul motif candidat du depot dont l'interaction
    avec le detecteur soit **mesuree** (0 faux positif sur les quatre
    dictionnaires), ce qui compte le jour ou une video reconstruite repasse par
    la chaine d'impression.

    Achromatique **par choix**: il ne peut ainsi ni etre pris pour une
    reference de calibration, ni introduire d'ambiguite d'ordre de canaux
    (AC 6).
    """
    if not (is_strict_int(height) and is_strict_int(width) and is_strict_int(cell_px)):
        raise ScanOutputError(
            f"Dimensions de damier invalides: {height!r}x{width!r}, cellule "
            f"{cell_px!r}. Des entiers sont attendus (`True` est un `int`)."
        )
    if height <= 0 or width <= 0 or cell_px <= 0:
        raise ScanOutputError(
            f"Dimensions de damier non strictement positives: {height}x{width}, "
            f"cellule {cell_px}."
        )
    board = np.full((height, width), MAX_LEVEL_8BIT, dtype=np.uint8)
    for row in range(0, height, cell_px):
        for col in range(0, width, cell_px):
            if (row // cell_px + col // cell_px) % 2 == 0:
                board[row : row + cell_px, col : col + cell_px] = 0
    return board


def derive_checker_cell_px(height: int) -> int:
    """Taille de cellule du damier, proportionnelle a la hauteur de frame."""
    return max(MIN_CHECKER_CELL_PX, round(height / CHECKER_ROWS))


def derive_text_thicknesses(font_scale: float) -> tuple[int, int]:
    """Rendre `(epaisseur de contour, epaisseur de remplissage)` pour une echelle.

    Les **deux** epaisseurs se derivent de l'echelle, en conservant le rapport
    contour/remplissage de la recette de reference (4 pour 1 a l'echelle 0.7),
    avec un plancher de 1 px chacune. Deriver la seule echelle en gardant les
    epaisseurs de reference produirait, sur une zone 8 frames/page, un contour
    de 4 px autour d'un remplissage de 1 px: ce n'est plus du texte, c'est une
    tache, et c'est exactement le defaut que l'arbitrage veut eviter.

    C'est le contrat de l'AC 13, exprime en pixels **voulus**. Ce que le moteur
    de texte sait en faire est une autre question, traitee par `_text_pens`.
    """
    ratio = font_scale / _REFERENCE_FONT_SCALE
    outline = max(1, round(_REFERENCE_OUTLINE_THICKNESS * ratio))
    fill = max(1, round(_REFERENCE_FILL_THICKNESS * ratio))
    return outline, fill


#: Plafond de la sonde d'epaisseur. Au-dela, une plume de texte n'a plus de
#: sens: la reference du depot est a 4.
_THICKNESS_PROBE_LIMIT = 16

_measured_pen_cap: int | None = None


def measured_pen_cap() -> int:
    """Plus grande plume que le moteur de texte honore encore. **Mesuree.**

    OpenCV 5 a reecrit son moteur de texte (`drawing_text.cpp`) et ne rend plus
    que deux graisses de plume: `thickness` a 2, 4 ou 7 produit des pixels
    **strictement identiques** (mesure faite au developpement de cette story).
    La consequence est contre-intuitive et casse la recette de reference du
    depot: un contour demande a 4 et un remplissage demande a 2 sortent tous
    deux a 2, et le remplissage **avale entierement** le contour -- le texte
    devient blanc sans lisere, donc illisible sur les cellules blanches du
    damier. C'est le meme symptome que le piege 11 de la story, pour une cause
    que la story ne pouvait pas connaitre.

    Le plafond est donc mesure une fois par processus plutot que suppose: on
    trace un glyphe a plume croissante jusqu'a ce que le resultat cesse de
    changer. Sur une version d'OpenCV qui honore les plumes epaisses, la sonde
    rend `_THICKNESS_PROBE_LIMIT` et la derivation de `derive_text_thicknesses`
    s'applique telle quelle.
    """
    global _measured_pen_cap
    if _measured_pen_cap is not None:
        return _measured_pen_cap
    previous: bytes | None = None
    cap = 1
    for thickness in range(1, _THICKNESS_PROBE_LIMIT + 1):
        probe = np.full((160, 200), MAX_LEVEL_8BIT, dtype=np.uint8)
        cv2.putText(probe, "M", (40, 120), _TEXT_FONT, 3.0, 0, thickness, cv2.LINE_AA)
        rendered = probe.tobytes()
        if previous is not None and rendered == previous:
            break
        previous = rendered
        cap = thickness
    _measured_pen_cap = cap
    return cap


def _text_pens(font_scale: float) -> tuple[int, int, int]:
    """Traduire les epaisseurs voulues en `(plume de contour, rayon, plume de remplissage)`.

    Le `rayon` est la compensation: au-dela de la plume que le moteur honore,
    l'epaisseur de contour derivee se rattrape en repetant la passe de contour
    sur une couronne de huit decalages. Sans elle, un contour derive a 22 px
    sur une grande frame se rendrait a 2 px -- invisible a cote du glyphe.

    C'est la **couronne**, jamais un ecart de plume, qui protege le lisere
    ------------------------------------------------------------------------
    La version d'origine bornait le remplissage a `max(1, outline_pen - 1)`
    quand aucune couronne ne le protegeait, au motif qu'a plume egale le
    remplissage recouvre exactement le contour. Ce plafond est **du code
    mort**, verifie par balayage exhaustif des echelles de 0.001 a 20.000 au
    millieme, et sur trois plafonds de plume (2, celui d'OpenCV 5; 4, celui de
    la recette de reference; 16, celui d'un moteur qui honore les plumes
    epaisses): **zero** echelle ou il borne reellement le remplissage. La
    raison est arithmetique: `radius` ne vaut 0 que si `outline <= 3`, donc si
    `font_scale / 0.7 < 0.875`, donc si l'epaisseur de remplissage voulue vaut
    deja 1 -- il n'y a plus rien a borner. Il a ete retire plutot que teste:
    un test sur une branche inatteignable ne peut pas echouer.

    Le defaut qu'il pretendait fermer, lui, est reel et se ferme autrement: a
    `outline_pen == 1` (echelle sous ~0.2625, atteinte des 100 ppp sur la plus
    petite zone du vocabulaire), aucun plafond ne peut creer un ecart de plume
    puisque 1 est deja le plancher -- le remplissage blanc recouvre exactement
    le contour noir et la mire devient du texte blanc sur un damier a cellules
    blanches, c'est-a-dire invisible la ou elle doit se voir. Une couronne
    d'un pixel suffit a rendre le lisere, et c'est la seule chose qui le
    puisse: on la force donc.
    """
    cap = measured_pen_cap()
    outline, fill = derive_text_thicknesses(font_scale)
    outline_pen = max(1, min(outline, cap))
    radius = max(0, (outline - outline_pen) // 2)
    if outline_pen == 1 and radius == 0:
        radius = 1
    fill_pen = max(1, min(fill, cap))
    return outline_pen, radius, fill_pen


def _measure_line(text: str, font_scale: float, thickness: int) -> tuple[int, int]:
    (width, height), _baseline = cv2.getTextSize(
        text, _TEXT_FONT, font_scale, thickness
    )
    return width, height


def _painted_line_size(text: str, font_scale: float) -> tuple[int, int]:
    """Etendue reellement peinte d'une ligne, couronne de contour comprise."""
    outline_pen, radius, _fill_pen = _text_pens(font_scale)
    width, height = _measure_line(text, font_scale, outline_pen)
    return width + 2 * radius, height + 2 * radius


def _draw_outlined_line(
    canvas: np.ndarray, text: str, x: int, y: int, font_scale: float
) -> None:
    """Contour noir epais puis remplissage blanc fin, sur un canevas 8 bits.

    Recette de `cadence_previz.CvWindowSink._draw_text`, reprise pour sa raison
    d'etre -- lisible sur n'importe quel fond, donc sur des cellules noires
    **et** blanches -- et non pour ses constantes.
    """
    outline_pen, radius, fill_pen = _text_pens(font_scale)
    offsets = [(0, 0)]
    if radius:
        offsets += [
            (dx * radius, dy * radius)
            for dx in (-1, 0, 1)
            for dy in (-1, 0, 1)
            if (dx, dy) != (0, 0)
        ]
    for dx, dy in offsets:
        cv2.putText(
            canvas, text, (x + dx, y + dy), _TEXT_FONT, font_scale, 0,
            outline_pen, cv2.LINE_AA,
        )
    cv2.putText(
        canvas, text, (x, y), _TEXT_FONT, font_scale, MAX_LEVEL_8BIT,
        fill_pen, cv2.LINE_AA,
    )


def derive_text_scale(lines: tuple[str, ...], height: int, width: int) -> float:
    """Echelle de police faisant tenir la **plus longue** des lignes en largeur.

    La largeur des deux lignes est **mesuree** par `cv2.getTextSize` avant
    trace, jamais estimee: c'est ce qui interdit la troncature silencieuse. Et
    ce n'est pas « FRAME MANQUANTE » qui commande -- la seconde ligne
    (`page 12/40 - 00:00:12:14`) est plus longue, donc c'est elle qui fixe
    l'echelle (piege 11, corollaire).

    Un second plafond porte sur la hauteur: sans lui, une frame large et peu
    haute recevrait un bloc de texte plus haut qu'elle.

    La premiere estimation se fait a epaisseur unitaire, puis se corrige: le
    contour elargit le glyphe de quelques pixels, et l'ignorer ferait deborder
    la ligne la plus longue precisement sur les petites zones, ou la marge est
    la plus mince. La correction ne fait que **reduire** l'echelle, donc elle
    converge.
    """
    if not lines:
        raise ScanOutputError("Aucune ligne de texte a poser sur la mire.")
    measured = [_measure_line(line, 1.0, 1) for line in lines]
    widest = max(size[0] for size in measured)
    line_height = max(size[1] for size in measured)
    if widest <= 0 or line_height <= 0:
        raise ScanOutputError(
            f"Lignes de texte non mesurables pour la mire: {lines!r}."
        )
    block_height = line_height * len(lines) + line_height * _TEXT_LINE_GAP_RATIO * (
        len(lines) - 1
    )
    available_width = width * _TEXT_WIDTH_RATIO
    scale = min(available_width / widest, height * _TEXT_BLOCK_HEIGHT_RATIO / block_height)

    for _ in range(8):
        painted = max(_painted_line_size(line, scale)[0] for line in lines)
        if painted <= available_width or painted <= 0:
            break
        scale *= available_width / painted
    return scale


def missing_frame_second_line(
    *, page_index: int, page_count: int, frame_timecode: str
) -> str:
    """Seconde ligne de la mire: `page <n>/<total> - <timecode>` (EPIC5-ARB-19).

    Trois points, tous portes par le payload **deja decode de la page en
    echec** -- rien n'est lu au manifest, rien n'est recalcule:

    - le rang de page part de **1**, comme sur la planche imprimee, qui porte
      deja `page {page_index + 1}/{page_count}`. Afficher le `page_index` brut,
      indexe a partir de 0, ferait lire « page 1 » a l'ecran pour la feuille
      marquee « page 2 » sur le papier: un decalage d'une unite, invisible en
      test unitaire et couteux au diagnostic (piege 12);
    - le timecode est celui du payload, **verbatim, avec ses deux-points** --
      pas la forme assainie, qui appartient au nom de fichier. C'est la forme
      qu'un monteur lit dans sa timeline;
    - le separateur est un **tiret ASCII**, jamais un tiret cadratin (piege 8).

    Le `slot_index` n'est pas porte: le timecode identifie deja la frame de
    facon unique a l'echelle du lot (AC 4), et chaque caractere coute de la
    largeur sur la plus petite zone du vocabulaire de gabarits.
    """
    if not (is_strict_int(page_index) and is_strict_int(page_count)):
        raise ScanOutputError(
            f"Rang de page invalide pour la mire: page_index={page_index!r}, "
            f"page_count={page_count!r}. Des entiers sont attendus."
        )
    # La fonction est exportee dans `__all__`, donc appelable hors de
    # `write_lot_output_frames` ou `validate_payload` garde deja les bornes. Le
    # decalage d'une unite est protege (piege 12), la borne ne l'etait pas:
    # `page_index=-1, page_count=5` peignait « page 0/5 » et `page_index=5,
    # page_count=3` peignait « page 6/3 », dans des pixels qu'aucune machine ne
    # relit (revue du 2026-08-08, couche 2).
    if page_count < 1 or not (0 <= page_index < page_count):
        raise ScanOutputError(
            f"Rang de page hors bornes pour la mire: page_index={page_index}, "
            f"page_count={page_count}. Le contrat du payload est "
            "0 <= page_index < page_count."
        )
    if not isinstance(frame_timecode, str) or not frame_timecode:
        raise ScanOutputError(
            f"Timecode invalide pour la mire: {frame_timecode!r}."
        )
    return f"page {page_index + 1}/{page_count} - {frame_timecode}"


def build_missing_frame_image(
    *,
    shape: tuple[int, ...],
    page_index: int,
    page_count: int,
    frame_timecode: str,
) -> np.ndarray:
    """Construire la frame de remplacement d'un slot dont la page a echoue.

    `shape` est la forme **du lot**, reprise et jamais recalculee: hauteur,
    largeur et nombre de canaux viennent du plan de decoupe de 5.3 ou, a
    defaut, des frames reelles du meme lot. Aucune conversion millimetres ->
    pixels n'a lieu ici: elle appartient a 5.2 et 5.3 (AC 11).

    Le tableau est construit directement en `np.uint16`. Un damier en `uint8`
    ferait declarer par l'export un `source_bit_depth` de 8 -- c'est-a-dire un
    scan 8 bits qui n'existe pas: la profondeur du **scan** se mesure sur les
    pages ingerees, jamais sur une image generee (piege 9).

    Rendu **deterministe**: deux generations pour la meme forme **et la meme
    seconde ligne** rendent des octets identiques. Deux mires de meme taille
    mais de pages ou de timecodes differents different legitimement, la seconde
    ligne faisant entrer `page_index`, `page_count` et `frame_timecode` dans les
    pixels (EPIC5-ARB-19).
    """
    if len(shape) not in (2, 3):
        raise ScanOutputError(
            f"Forme de frame invalide pour la mire: {shape!r}. Deux ou trois "
            "dimensions sont attendues."
        )
    if not all(is_strict_int(value) for value in shape):
        raise ScanOutputError(
            f"Forme de frame invalide pour la mire: {shape!r}. Des entiers sont "
            "attendus (`True` est un `int`)."
        )
    height, width = shape[0], shape[1]
    channels = shape[2] if len(shape) == 3 else None
    if channels is not None and channels not in (1, 3, 4):
        raise ScanOutputError(
            f"Nombre de canaux non supporte pour la mire: {channels}. "
            "1, 3 ou 4 sont attendus, en ordre BGR."
        )

    canvas = build_checkerboard(height, width, derive_checker_cell_px(height))

    lines = (
        MISSING_FRAME_TEXT,
        missing_frame_second_line(
            page_index=page_index, page_count=page_count, frame_timecode=frame_timecode
        ),
    )
    font_scale = derive_text_scale(lines, height, width)

    # Le centrage se mesure sur l'etendue **peinte**, couronne de contour
    # comprise: c'est elle le trait le plus large des deux passes.
    sizes = [_painted_line_size(line, font_scale) for line in lines]
    line_height = max(size[1] for size in sizes)
    gap = line_height * _TEXT_LINE_GAP_RATIO
    block_height = line_height * len(lines) + gap * (len(lines) - 1)
    # `cv2.putText` prend la **ligne de base** du texte, pas son coin haut
    # gauche: le premier `y` est donc le bas de la premiere ligne.
    first_baseline = (height - block_height) / 2 + line_height

    for index, (line, (line_width, _)) in enumerate(zip(lines, sizes)):
        x = int(round((width - line_width) / 2))
        y = int(round(first_baseline + index * (line_height + gap)))
        _draw_outlined_line(canvas, line, x, y, font_scale)

    promoted = canvas.astype(np.uint16) * BIT_DEPTH_PROMOTION_FACTOR
    if channels is None:
        return promoted
    # Achromatique: les canaux sont identiques, donc l'ordre BGR est sans
    # objet et la mire ne peut pas introduire d'inversion rouge/bleu (AC 6).
    # Un quatrieme canal (alpha) est porte a l'opacite pleine.
    stacked = np.repeat(promoted[:, :, np.newaxis], channels, axis=2)
    if channels == 4:
        stacked[:, :, 3] = MAX_LEVEL_16BIT
    return np.ascontiguousarray(stacked)


# --- entrees et sorties du module -------------------------------------------


@dataclass(frozen=True)
class ScannedPage:
    """Une page du lot, telle que la chaine scan la remet a l'ecriture.

    `payload` est le payload QR **deja decode** de la page (5.2). Il vaut
    `None` pour une page ingeree dont le QR est illisible: elle ne produit
    alors rien du tout -- ni frame reelle, ni frame de remplacement -- et reste
    un trou declare, faute de timecode (AC 13, condition d'ecriture).

    `crop_plan` est le plan de decoupe de 5.3, `frames` les tableaux decoupes,
    dans l'ordre des `slots` du payload. `failure`, s'il est renseigne, nomme
    dans le vocabulaire ferme le motif pour lequel **toute** la page est en
    echec: ses slots recoivent alors une frame de remplacement. Les deux
    granularites de 5.2 et 5.3 sont bien celles-la -- une homographie non
    resolue ou un plan de decoupe refuse portent sur la page entiere, pas sur
    un slot isole.

    `locator` est une trace facultative (chemin source, rang de lecture)
    fournie par l'appelant. Elle n'est **pas** publiee au rapport aujourd'hui:
    la docstring d'origine annoncait « que le rapport recopie telle quelle pour
    le diagnostic », ce qui etait faux (revue couche 3 -- une docstring qui
    decrit un comportement inexistant est une affirmation fausse dans le code
    de production). Le champ est conserve parce que le besoin, lui, est reel:
    une page a QR illisible est comptee (`unidentified_page_count`) et jamais
    nommee. Le cabler au rapport suppose de decider ce qu'un chemin local
    devient dans un document qui interdit les chemins absolus (AC 10) et que
    5.7 persistera -- c'est un arbitrage, pas un oubli.
    """

    payload: dict | None
    crop_plan: scan_crop.PageCropPlan | None = None
    frames: tuple[np.ndarray, ...] | None = None
    failure: str | None = None
    locator: str | None = None


@dataclass(frozen=True)
class OutputFrame:
    """Une entree du rapport: une frame ecrite, reelle ou de remplacement."""

    page_index: int
    slot_index: int
    frame_timecode: str
    filename: str
    path: str
    synthetic: bool
    source_bit_depth: int
    output_bit_depth: int
    output_format: str
    overwritten: bool
    synthetic_reason: str | None = None

    def as_document(self) -> dict:
        """Document de la frame.

        `synthetic` est **toujours** present, y compris a `false`: un champ
        absent se relit « vraie frame » par defaut, precisement le faux positif
        silencieux qu'EPIC5-ARB-8 ecarte. `synthetic_reason` est present **si
        et seulement si** `synthetic` vaut `true` -- jamais `null`.
        """
        document = {
            "page_index": self.page_index,
            "slot_index": self.slot_index,
            "frame_timecode": self.frame_timecode,
            "filename": self.filename,
            "path": self.path,
            "synthetic": self.synthetic,
            "source_bit_depth": self.source_bit_depth,
            "output_bit_depth": self.output_bit_depth,
            "output_format": self.output_format,
            "overwritten": self.overwritten,
        }
        if self.synthetic:
            document["synthetic_reason"] = self.synthetic_reason
        return document


@dataclass(frozen=True)
class LotOutputReport:
    """Le rapport que 5.7 (manifest) et 5.8 (previz) consomment. Aucun pixel.

    Trois cardinaux, et pas un de moins (AC 7): `expected_frame_count` -- ou
    `None` quand il est **indeterminable** --, `written_frame_count` et
    `synthetic_frame_count`.

    `complete` est un verdict de **passe**, pas de dossier: `written_frame_count`
    compte ce que cette passe a ecrit. Cinq conditions **necessaires**, toutes
    des interdits de faux succes (risque R12):

    1. le cardinal attendu est determinable;
    2. l'ecrit lui est egal;
    3. aucune frame synthetique n'a ete ecrite -- le fichier existe, mais
       l'image du film, non;
    4. aucun fichier compte a l'ecriture n'est absent du dossier;
    5. aucune page du lot ne manque, et **les formes ecrites sont homogenes**.
       Le module pose lui-meme l'equivalence « forme divergente = trou »
       (`FrameShapeConflictError`: « une frame de taille differente casse
       l'encodage aussi surement qu'un trou »); il ne l'appliquait que quand
       une mire devait etre posee, si bien qu'un lot inencodable par l'Epic 6
       pouvait sortir `complete: true`. Et un rapport qui nomme une page
       manquante dans `missing_pages` ne doit structurellement pas pouvoir dire
       « complet » dans le meme document.

    `observed_frame_count` est un quatrieme compteur, de nature differente: il
    compte les **fichiers** conformes et non vides presents dans le dossier
    apres la passe. Une seconde passe complementaire ecrit peu et observe
    beaucoup.
    """

    lot_id: str
    rush_id: str
    fps_target: float
    project_id: str
    template_id: str
    gamut_map_id: str
    target_colorspace: str
    patch_preset_id: str
    color_calibration_status: str
    output_dir: str
    page_count: int
    expected_frame_count: int | None
    written_frame_count: int
    synthetic_frame_count: int
    observed_frame_count: int
    complete: bool
    frames: tuple[OutputFrame, ...] = ()
    source_bit_depths: tuple[int, ...] = ()
    output_bit_depth: int | None = None
    output_format: str | None = None
    missing_pages: tuple[int, ...] = ()
    unidentified_page_count: int = 0
    shape_indeterminable_pages: tuple[int, ...] = ()
    missing_frames: tuple[str, ...] = ()
    unwritten_frame_timecodes: tuple[str, ...] = ()
    nonconforming_files: tuple[str, ...] = ()
    preexisting_frames: tuple[str, ...] = ()
    overwritten_files: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def synthetic_frames(self) -> tuple[OutputFrame, ...]:
        """Les frames de remplacement ecrites, nommees.

        C'est le **seul** moyen de cibler une seconde passe de scan: 5.6 ne
        sait pas, en regardant le dossier, quel fichier est synthetique -- le
        nom est identique par construction et `cv2.imwrite` n'ecrit aucun tag
        (EPIC5-ARB-18).
        """
        return tuple(frame for frame in self.frames if frame.synthetic)

    def as_document(self) -> dict:
        return {
            "lot_id": self.lot_id,
            "rush_id": self.rush_id,
            "fps_target": self.fps_target,
            "project_id": self.project_id,
            "template_id": self.template_id,
            "gamut_map_id": self.gamut_map_id,
            "target_colorspace": self.target_colorspace,
            "patch_preset_id": self.patch_preset_id,
            "color_calibration_status": self.color_calibration_status,
            "output_dir": self.output_dir,
            "page_count": self.page_count,
            "expected_frame_count": self.expected_frame_count,
            "written_frame_count": self.written_frame_count,
            "synthetic_frame_count": self.synthetic_frame_count,
            "observed_frame_count": self.observed_frame_count,
            "complete": self.complete,
            "source_bit_depths": list(self.source_bit_depths),
            "output_bit_depth": self.output_bit_depth,
            "output_format": self.output_format,
            "missing_pages": list(self.missing_pages),
            "unidentified_page_count": self.unidentified_page_count,
            "shape_indeterminable_pages": list(self.shape_indeterminable_pages),
            "missing_frames": list(self.missing_frames),
            "unwritten_frame_timecodes": list(self.unwritten_frame_timecodes),
            "nonconforming_files": list(self.nonconforming_files),
            "preexisting_frames": list(self.preexisting_frames),
            "overwritten_files": list(self.overwritten_files),
            "warnings": list(self.warnings),
            "frames": [frame.as_document() for frame in self.frames],
        }


# --- planification: tout ce qui peut echouer, avant le premier octet ecrit ---


@dataclass(frozen=True)
class _PlannedFrame:
    """Une ecriture prevue. Interne: le rapport publie `OutputFrame`."""

    page_index: int
    slot_index: int
    frame_timecode: str
    filename: str
    image: np.ndarray | None
    synthetic: bool
    synthetic_reason: str | None
    #: Profondeur du **scan source**, quand elle ne se deduit plus du tableau porte.
    #: `None` veut dire « demande-la a l'export », qui la lit du dtype: c'est le cas de
    #: toute frame non corrigee, donc le comportement d'avant la story 5.19 est celui
    #: qui reste quand personne ne renseigne le champ.
    source_bit_depth: int | None = None


def _lot_identity(pages: tuple[ScannedPage, ...]) -> dict:
    """Extraire l'identite du lot des payloads, ou refuser leur divergence.

    Les champs confrontes sont ceux de **niveau lot**: les laisser diverger
    ferait ecrire deux lots dans un dossier unique, sous des noms qui ne
    diraient pas lequel est lequel. 5.2 reconcilie deja le lot, mais son
    rapport n'a pas a etre la seule garde d'un module qui ecrit sur le disque
    de l'operateur.
    """
    if not pages:
        raise LotInconsistencyError(
            "Aucune page du lot ne porte de payload decode: le dossier de "
            "sortie, le nom des fichiers et le cardinal attendu sont tous "
            "indeterminables. Rien n'est ecrit."
        )
    fields = (
        "project_id",
        "rush_id",
        "lot_id",
        "fps_target",
        "template_id",
        "patch_preset_id",
        "target_colorspace",
        "gamut_map_id",
        "page_count",
    )
    identity: dict = {}
    for field in fields:
        # **Seules les pages qui portent le champ le declarent** (story 5.23,
        # 2026-08-18). Une page de calibration ne porte ni projet, ni rush, ni lot, ni
        # cadence: elle sert toute une chaine de scan et non un lot
        # (`io.payload.CALIBRATION_ABSENT_FIELDS`). Un acces nu levait ici une
        # `KeyError` des qu'une page de calibration restait dans la pile posee sur la
        # vitre -- ce qui est le cas nominal, pas un accident --, et le scan entier
        # mourait en traceback alors que les frames etaient parfaitement extractibles.
        #
        # Le filtre est pose sur la **presence du champ** et non sur le role: la
        # question a laquelle cette boucle repond est « qui declare ce champ ? », et la
        # validation garantit deja qu'une planche d'images les declare tous. Le filtre
        # ne peut donc pas masquer un payload tronque, qui aurait ete refuse en amont.
        contributeurs = [page for page in pages if field in page.payload]
        if not contributeurs:
            raise LotInconsistencyError(
                f"Aucune page du lot ne declare '{field}': la pile ne porte que des "
                "pages de calibration, qui ne decrivent aucun lot. Le dossier de "
                "sortie et le nom des fichiers sont indeterminables, rien n'est ecrit."
            )
        values = {page.payload[field] for page in contributeurs}
        if len(values) > 1:
            raise LotInconsistencyError(
                f"Les pages ne declarent pas le meme '{field}': "
                f"{sorted(str(value) for value in values)}. Deux lots melanges "
                "s'ecriraient dans un dossier unique, sous des noms qui ne "
                "diraient pas lequel est lequel."
            )
        identity[field] = values.pop()

    # Le rang de page, confronte a l'**echelle du lot** (revue du 2026-08-08,
    # couche 2, bloquante 1). `validate_payload` ne garantit que
    # `0 <= page_index < page_count`, page par page: deux pages du meme lot
    # pouvaient porter le meme rang sans que rien ne bouge.
    #
    # Le chemin est reel et n'a rien d'exotique: `build_lot_id` ne depend **ni
    # de la selection ni des timecodes**, si bien que deux tirages successifs du
    # meme rush a la meme cadence -- le second apres correction du choix des
    # frames, a cardinal egal -- produisent le meme `lot_id`, le meme
    # `page_count` et le meme `template_id`. Des planches des deux tirages
    # melangees dans le meme bac de scan etaient indiscernables pour la garde
    # nommee « deux lots melanges ».
    #
    # Mesure a la revue, les deux faux succes que cela produisait: un lot dont
    # la page 0 n'a jamais ete scannee sortait `complete: true` avec
    # `missing_pages=(0,)` **dans le meme document**; et deux tirages melanges
    # sortaient `complete: true` sans un seul avertissement. Un rang duplique
    # ne se rattrape pas -- il rend meme le cardinal attendu dependant de
    # l'ordre d'arrivee des planches -- c'est donc un refus dur, au meme titre
    # qu'un `page_count` divergent.
    seen_indexes: dict[int, int] = {}
    for position, page in enumerate(pages):
        page_index = page.payload["page_index"]
        if page_index in seen_indexes:
            raise LotInconsistencyError(
                f"Deux pages du lot declarent le meme page_index {page_index}: "
                f"pages {seen_indexes[page_index]} et {position} de la sequence "
                "recue. Le rang de page est unique dans un lot; un doublon "
                "signale deux tirages du meme rush melanges dans le meme bac de "
                "scan -- que `lot_id`, `page_count` et `template_id` ne "
                "distinguent pas, aucun d'eux ne dependant de la selection. "
                "Ecrire quand meme declarerait complet un lot ampute."
            )
        seen_indexes[page_index] = position
    return identity


def _carries_frames(page: ScannedPage) -> bool:
    """Cette page porte-t-elle des emplacements de frames, par son **role**?

    Une page de role calibration n'en porte aucun, par contrat, et ce n'est pas une
    planche creuse: c'est une page dont la raison d'etre est de porter le treillis de
    mesure (story 5.16, `EPIC5-ARB-54`). Les deux derivations ci-dessous doivent donc la
    **retirer** de leurs hypotheses de pagination, et non lui appliquer celles des
    planches d'images.

    Le defaut est le role d'images, comme a la relecture d'un payload
    (`io.payload.REREAD_DEFAULTS`): une planche imprimee avant le champ de role est une
    planche d'images, il n'en existait pas d'autre. Le defaut est ici le regime
    **conservateur** -- il fait compter la page comme pleine, donc surestimer, ce qui
    refuse un lot au lieu de le declarer faussement complet.
    """
    if page.payload is None:
        return False
    role = page.payload.get("page_role", page_roles.PAGE_ROLE_IMAGES)
    return role != page_roles.PAGE_ROLE_CALIBRATION


def _expected_frame_count(
    pages: tuple[ScannedPage, ...], *, template_id: str, page_count: int
) -> int | None:
    """Cardinal attendu du lot, ou `None` s'il est indeterminable.

    **Ce n'est pas la somme des slots des pages recues**: une page absente
    n'apporte pas ses slots, et l'additionner a zero declarerait un lot tronque
    comme complet (risque R12).

    Il se derive du `template_id`, champ de niveau lot, dont
    `page_templates.get_template(...).frames_per_page` donne le cardinal d'une
    page pleine, et de la pagination en place, qui remplit les pages dans
    l'ordre et ne laisse partielle que la **derniere**:
    `(pages porteuses de frames - 1) * frames_per_page + len(slots de la derniere page)`.

    Une page intermediaire manquante compte donc pour `frames_per_page`. Si la
    **derniere** page manque, le total est indeterminable et le rapport le
    declare -- jamais devine.

    **Les pages de role calibration sont retirees du compte** (bloquant B1 de la revue de
    5.16, corrige a sa passe de correction). La story fait passer `page_count` de
    `ceil(frames / fpp)` a `1 + ceil(...)`: la page de calibration est comptee, elle est a
    l'index 0, elle n'est jamais la derniere, et elle porte **zero** emplacement. Elle
    violait donc les deux hypotheses de cette derivation, qui surestimait le cardinal
    attendu d'exactement `frames_per_page`.

    **Le regime ou ce defaut mord est celui ou aucun cardinal anterieur n'existe.** Sur le
    chemin nominal `extract -> makepdf -> scan`, `io.scan_manifest._resolve_expected_frame_count`
    **conserve** le cardinal du manifest -- venu de l'extraction, qui a compte de vraies
    frames -- contre celui du scan, donc le nombre faux ne s'ecrivait pas et le lot sortait
    complet. Le regime sans cardinal anterieur est celui du **projet reconstruit depuis des
    planches seules** (story 2.6): la valeur du scan y est ecrite telle quelle, donc le lot
    etait declare incomplet de facon permanente, et c'est le cas ou l'on a le moins de
    recours puisqu'aucune mesure anterieure n'existe pour rattraper l'erreur.

    Residu assume, et il est du meme signe que l'hypothese existante: une page de
    calibration **absente** du scan n'est pas distinguable d'une planche d'images absente,
    donc elle compte pour `frames_per_page`. Le cardinal est alors surestime -- jamais
    sous-estime, donc aucun faux succes -- et le lot porte de toute facon
    `PAGE_MISSING_FROM_LOT` et ne peut pas etre declare complet. Le role n'est lu que sur
    les pages **recues**, ce qui garde cette derivation independante de toute constante
    qui pourrait bouger apres l'impression.
    """
    frames_per_page = page_templates.get_template(template_id).frames_per_page
    last_index = page_count - 1
    calibration_pages = sum(
        1 for page in pages if page.payload is not None and not _carries_frames(page))
    images_pages = page_count - calibration_pages
    for page in pages:
        if page.payload is not None and page.payload["page_index"] == last_index:
            return (images_pages - 1) * frames_per_page + len(page.payload["slots"])
    return None


def _underfilled_pages(
    pages: tuple[ScannedPage, ...], *, page_count: int, template_id: str
) -> tuple[int, ...]:
    """Pages non-dernieres portant moins de slots que leur gabarit.

    C'est le pendant doux du refus de `_plan_lot_writes`: la pagination remplit
    les pages dans l'ordre et ne laisse partielle que la **derniere**, et tout
    le cardinal attendu de l'AC 7 repose sur cette hypothese. Une page
    intermediaire creuse ne fait pas ecrire de faux fichier -- elle produit un
    faux **echec** (`expected` trop grand, lot jamais declare complet) -- donc
    elle s'avertit au lieu de se refuser. L'hypothese doit etre eprouvee la ou
    elle est utilisee.

    **Une page de role calibration n'est pas une page creuse** (bloquant B1). Elle porte
    zero emplacement par contrat, et l'avertir revenait a accuser d'etre creuse la page
    dont depend toute la correction du lot -- un diagnostic faux, sur la page nominale du
    regime que la story 5.16 installe.
    """
    frames_per_page = page_templates.get_template(template_id).frames_per_page
    last_index = page_count - 1
    return tuple(
        page.payload["page_index"]
        for page in pages
        if page.payload is not None
        and _carries_frames(page)
        and page.payload["page_index"] != last_index
        and len(page.payload["slots"]) < frames_per_page
    )


def _page_frame_shape(page: ScannedPage, slot_index: int) -> tuple[int, ...] | None:
    """Forme declaree par le plan de decoupe pour ce slot, si elle existe."""
    if page.crop_plan is None:
        return None
    for planned in page.crop_plan.frames:
        if planned.slot_index == slot_index:
            return (planned.height_px, planned.width_px)
    return None


def _observed_shapes(pages: tuple[ScannedPage, ...]) -> set[tuple[int, ...]]:
    """Formes des frames reelles du lot, telles qu'elles seront ecrites."""
    shapes: set[tuple[int, ...]] = set()
    for page in pages:
        for image in page.frames or ():
            if isinstance(image, np.ndarray):
                shapes.add(tuple(int(value) for value in image.shape))
    return shapes


def _resolve_synthetic_shape(
    page: ScannedPage,
    slot_index: int,
    observed: set[tuple[int, ...]],
) -> tuple[int, ...] | None:
    """Forme d'une frame de remplacement: reprise, jamais recalculee.

    Source, dans cet ordre: le plan de decoupe de 5.3, sinon la forme observee
    des frames reelles du meme lot dans la meme passe. Si le lot n'offre ni
    l'un ni l'autre, la forme est **indeterminable**: rien n'est ecrit et le
    rapport le declare -- meme doctrine que le cardinal indeterminable, on ne
    choisit pas une taille par defaut.
    """
    if len(observed) > 1:
        raise FrameShapeConflictError(
            f"Formes de frames divergentes dans le meme lot: "
            f"{sorted(observed)}. Une frame de remplacement ne peut pas etre "
            "arbitree entre deux formes: une sequence heterogene est deja un "
            "echec d'encodage."
        )
    observed_shape = next(iter(observed), None)
    planned_shape = _page_frame_shape(page, slot_index)

    if planned_shape is None:
        if observed_shape is None:
            return None
        return observed_shape
    if observed_shape is not None and observed_shape[:2] != planned_shape[:2]:
        raise FrameShapeConflictError(
            f"Le plan de decoupe annonce {planned_shape[1]}x{planned_shape[0]} px "
            f"pour le slot {slot_index} la ou les frames reelles du lot mesurent "
            f"{observed_shape[1]}x{observed_shape[0]} px. Choisir l'une des deux "
            "serait un arbitrage a la volee."
        )
    if observed_shape is None:
        # Le plan declare un rectangle, donc une hauteur et une largeur, mais
        # pas un nombre de canaux: c'est la seule valeur qu'il ne porte pas.
        return (planned_shape[0], planned_shape[1], DEFAULT_SYNTHETIC_CHANNELS)
    if len(observed_shape) == 2:
        # Scan en niveaux de gris: les frames reelles sont a deux dimensions,
        # la mire doit l'etre aussi.
        return planned_shape
    return (planned_shape[0], planned_shape[1], observed_shape[2])


def _validated_real_frame(
    image, *, page_index: int, slot_index: int
) -> np.ndarray:
    """Passer une frame reelle a la garde d'export, **en planification**.

    La validation vivait dans la boucle d'ecriture (`export_frame_tiff16` la
    fait en tete), c'est-a-dire **apres** le premier octet ecrit -- contre
    l'engagement que le module porte trois fois, en en-tete et en docstring.
    Mesure a la revue (couche 2, majeure 1): un lot de 3 pages x 2 slots dont
    la sixieme frame est en `float32`, vide `(0,0,3)`, `None`, `int16`, a 2 ou
    5 canaux laissait **cinq** fichiers sur le disque, sans rapport qui les
    nomme, et bloquait la relance sur `OutputFrameExistsError` -- la seule
    issue restante etant `--overwrite`, qui autorise du meme geste a ecraser
    les frames deja acquises.

    La garde est celle de `color_pipeline`, appelee et jamais reecrite: c'est
    exactement la forme qui sera ecrite. Son `ValueError`/`TypeError` est
    retraduit dans la hierarchie du module en nommant la page et le slot --
    aucune des deux n'appartenait a `ScanOutputError`, si bien qu'un appelant
    de la chaine scan qui rattrape la hierarchie du module se prenait le
    plantage brut.
    """
    try:
        return color_pipeline.validate_bgr_input(image)
    except (TypeError, ValueError) as error:
        raise ScanOutputError(
            f"Page {page_index}, slot {slot_index}: la frame decoupee n'est pas "
            f"exportable en TIFF 16 bits ({error}). Rien n'a ete ecrit: le refus "
            "precede le premier octet, pour qu'une decoupe partiellement "
            "degeneree ne laisse pas un dossier a demi rempli que la relance ne "
            "pourrait reparer qu'avec --overwrite."
        ) from error


def _corrected_frame(image, profile, *, page_index: int, slot_index: int):
    """Appliquer la correction couleur du lot a une frame, et rendre du 16 bits.

    Story 5.19, AC 3: c'est **le** point ou la correction touche les pixels. Elle
    n'existait nulle part -- `write_lot_output_frames` recevait le *statut* de
    calibration et aucun profil, donc il ne pouvait rien corriger, et la correction de
    5.16 restait calculable et jamais appliquee.

    Rend `(image 16 bits, profondeur du scan source)`. Les deux valeurs sont rendues
    ensemble parce que la seconde **ne se deduit plus** de la premiere: la correction
    travaille en flottant, donc son resultat est requantifie sur 16 bits quelle que soit
    la profondeur d'entree, et laisser `export_frame_tiff16` deduire la profondeur du
    tableau qu'il recoit ferait declarer `source_bit_depth: 16` sur un scan 8 bits. Le
    champ dit ce que **le scan** portait -- « un scan 8 bits eleve a 16 bits ne peuple
    que 256 des 65536 niveaux » (`color_pipeline.COLOR_MANIFEST_FIELDS`) --, donc c'est
    la valeur d'avant correction qui est vraie.

    La requantification est en 16 bits et non dans le type d'entree: un aller-retour par
    l'uint8 replierait la correction sur les 256 niveaux du scan, ce qui reintroduirait
    l'erreur d'arrondi que la story 5.0 a passe une story a retirer de ce chemin.

    Le refus des frames qui ne portent pas trois canaux est **ici**, avant la premiere
    ecriture: la correction est une matrice 3x3 sur des triplets BGR, donc une frame
    monochrome ou a canal alpha ne se corrige pas -- et la deviner corrigee serait pire
    que la refuser. `color_pipeline` decrit la chaine comme BGR trois canaux de bout en
    bout, donc ce refus n'est pas atteint par le chemin nominal.
    """
    array = np.asarray(image)
    if array.ndim != 3 or array.shape[2] != 3:
        raise ScanOutputError(
            f"Page {page_index}, slot {slot_index}: la correction couleur active "
            f"demande une frame BGR a trois canaux, recue de forme {array.shape}. "
            "Rien n'a ete ecrit: une correction est une matrice 3x3 sur des triplets, "
            "et l'appliquer a autre chose reviendrait a deviner quels canaux elle "
            "corrige."
        )
    # La regle de profondeur est **lue chez son proprietaire** et non reecrite ici
    # (finding `m4` de la revue): les deux redactions coincidaient, et leur divergence
    # future aurait ete silencieuse sur un champ de manifest.
    source_bit_depth = color_pipeline.source_bit_depth_of(array)
    try:
        corrected = color_pipeline.apply_active_calibration(array, profile)
    except (color_pipeline.ColorCalibrationUnavailable, TypeError, ValueError) as error:
        raise ScanOutputError(
            f"Page {page_index}, slot {slot_index}: la correction couleur du lot n'a "
            f"pas pu etre appliquee ({error}). Rien n'a ete ecrit: une frame a demi "
            "corrigee serait indistinguable d'une frame corrigee."
        ) from error
    values = np.clip(np.asarray(corrected, dtype=np.float64), 0.0, 1.0)
    return (np.rint(values * MAX_LEVEL_16BIT).astype(np.uint16), source_bit_depth)


def _plan_lot_writes(
    pages: tuple[ScannedPage, ...],
    *,
    rush_id: str,
    fps_target: float,
    frames_per_page: int,
    page_profiles: dict | None = None,
) -> tuple[list[_PlannedFrame], list[int], list[str]]:
    """Construire la liste des ecritures, mire comprise. Rien n'est ecrit ici.

    Tout ce qui peut echouer -- gabarit inconnu, forme conflictuelle, frame
    inexportable, page trop remplie, timecode duplique, nom non constructible
    -- se decide **avant** le premier octet ecrit, pour qu'un refus ne laisse
    jamais un dossier a demi rempli.

    Rend aussi les timecodes des slots **planifies et non ecrits**: ils sont
    connus (ils viennent du payload decode de leur propre page) et l'AC 8 exige
    de nommer « pages absentes, timecodes absents ».

    `page_profiles` associe un `page_index` a la correction couleur retenue **pour cette
    page** (story 5.19). La correction s'applique donc **en planification**, comme tout
    ce qui peut echouer: une frame incorrigible refuse avant le premier octet plutot que
    de laisser un dossier a demi corrige, ou pire, un dossier ou l'on ne sait plus quelle
    frame porte la correction.
    """
    profiles = dict(page_profiles or {})
    observed = _observed_shapes(pages)
    planned: list[_PlannedFrame] = []
    shape_indeterminable: list[int] = []
    unwritten_timecodes: list[str] = []

    for page in pages:
        if page.payload is None:
            continue
        page_index = page.payload["page_index"]
        page_count = page.payload["page_count"]
        slots = page.payload["slots"]
        synthetic = page.failure is not None

        # Le cardinal attendu de l'AC 7 pose que la pagination remplit les pages
        # dans l'ordre et ne laisse partielle que la derniere. L'hypothese etait
        # ecrite, jamais verifiee: mesure a la revue (couche 2, moyenne 5), une
        # repartition 3/1/2 sur un gabarit 2 frames/page rendait `expected == 6`,
        # `written == 6` et `complete: true` -- deux incoherences de sens
        # contraire qui s'annulent, sur un lot dont la structure contredit son
        # propre gabarit. Un exces est un refus dur; un manque sur une page
        # non-derniere est un avertissement (le lot reste ecrivable).
        if len(slots) > frames_per_page:
            raise LotInconsistencyError(
                f"La page {page_index} declare {len(slots)} slots la ou son "
                f"gabarit n'en porte que {frames_per_page}. La pagination "
                "remplit les pages dans l'ordre et ne laisse partielle que la "
                "derniere: une page trop remplie contredit le gabarit du lot, "
                "et son exces compenserait le manque d'une autre page jusqu'a "
                "faire declarer complet un lot qui ne l'est pas."
            )

        for position, slot in enumerate(slots):
            slot_index = slot["slot_index"]
            frame_timecode = slot["frame_timecode"]
            filename = naming.build_scan_frame_filename(
                rush_id, fps_target, frame_timecode
            )
            if not synthetic:
                image = page.frames[position]
                image = _validated_real_frame(
                    image, page_index=page_index, slot_index=slot_index
                )
                # La correction ne s'applique qu'aux **frames reelles**, et l'ordre est
                # celui-la: la garde d'export d'abord (c'est elle qui normalise l'ordre
                # des octets d'un scan grand-boutien), la correction ensuite. Une mire de
                # remplacement n'est jamais corrigee -- elle n'est pas le contenu source
                # et elle est achromatique par construction, ce que la garde de coherence
                # du manifest de 5.7 tient deja pour incompatible avec `applied`.
                source_bit_depth: int | None = None
                profile = profiles.get(page_index)
                if profile is not None:
                    image, source_bit_depth = _corrected_frame(
                        image, profile, page_index=page_index, slot_index=slot_index
                    )
                planned.append(
                    _PlannedFrame(
                        page_index=page_index,
                        slot_index=slot_index,
                        frame_timecode=frame_timecode,
                        filename=filename,
                        image=image,
                        synthetic=False,
                        synthetic_reason=None,
                        source_bit_depth=source_bit_depth,
                    )
                )
                continue

            shape = _resolve_synthetic_shape(page, slot_index, observed)
            if shape is None:
                if page_index not in shape_indeterminable:
                    shape_indeterminable.append(page_index)
                # Le timecode de ce slot est **connu** -- il vient du payload
                # decode de sa propre page -- et rien ne sera ecrit pour lui:
                # c'est le seul cas ou l'AC 8 (« timecodes absents ») porte sur
                # une information que le module possede (revue couche 3).
                unwritten_timecodes.append(frame_timecode)
                continue
            planned.append(
                _PlannedFrame(
                    page_index=page_index,
                    slot_index=slot_index,
                    frame_timecode=frame_timecode,
                    filename=filename,
                    image=build_missing_frame_image(
                        shape=shape,
                        page_index=page_index,
                        page_count=page_count,
                        frame_timecode=frame_timecode,
                    ),
                    synthetic=True,
                    synthetic_reason=page.failure,
                )
            )

    _assert_unique_filenames(planned)
    # Les frames reelles d'abord: la forme d'une mire peut se lire sur elles,
    # et un dossier a demi rempli doit l'etre de vraies frames avant de l'etre
    # de bouche-trous.
    planned.sort(key=lambda frame: (frame.synthetic, frame.page_index, frame.slot_index))
    return planned, sorted(shape_indeterminable), sorted(unwritten_timecodes)


def _assert_unique_filenames(planned: list[_PlannedFrame]) -> None:
    """Refuser deux frames du lot qui produiraient le meme nom (AC 4).

    La confrontation porte sur le **nom de fichier**, pas sur le timecode brut:
    c'est le nom qui provoque l'ecrasement, et deux timecodes distincts peuvent
    l'engendrer -- `00:00:01:00` et `00;00;01;00`, formes non drop-frame et
    drop-frame, s'assainissent en `00-00-01-00` toutes les deux.
    """
    by_name: dict[str, _PlannedFrame] = {}
    for frame in planned:
        previous = by_name.get(frame.filename)
        if previous is not None:
            raise DuplicateFrameTimecodeError(
                f"Deux frames du lot produiraient le fichier {frame.filename!r}: "
                f"page {previous.page_index} slot {previous.slot_index} "
                f"(timecode {previous.frame_timecode!r}) et page "
                f"{frame.page_index} slot {frame.slot_index} (timecode "
                f"{frame.frame_timecode!r}). Aucun suffixe de desambiguisation "
                "n'est invente: un doublon de timecode signale un lot corrompu "
                "ou deux lots melanges, pas un cas a rattraper."
            )
        by_name[frame.filename] = frame


def _assert_writable(
    output_dir: Path, planned: list[_PlannedFrame], *, overwrite: bool
) -> set[str]:
    """Refuser d'ecraser sans `--overwrite`, et nommer ce qui serait ecrase.

    Regle **uniforme** tranchee par EPIC5-ARB-18: ecraser un fichier existant
    demande `--overwrite`, qu'il soit synthetique ou non. 5.6 ne peut pas
    savoir depuis le disque qu'un fichier est synthetique -- le nom est
    identique par construction et `cv2.imwrite` n'ecrit aucun tag --, et le
    savoir imposerait de lire le manifest depuis une etape qui ne le lit pas.

    Le controle porte sur les fichiers **effectivement vises**, jamais sur la
    seule presence de contenu dans le dossier: une seconde passe qui apporte les
    pages manquantes d'un lot deja partiellement ecrit ne detruit rien et n'a
    donc pas a reclamer un drapeau qui, lui, autoriserait aussi a ecraser les
    frames deja acquises.

    Aucune suppression prealable, jamais: le motif du POC, qui efface les
    `scan_frame_*` preexistants avant d'ecrire, est un rejeu destructif
    silencieux sur des donnees que l'operateur peut avoir mis des heures a
    produire.
    """
    existing = {
        frame.filename
        for frame in planned
        if (output_dir / frame.filename).exists()
    }
    if existing and not overwrite:
        # TROIS issues (`EPIC11-ARB-89` / `EPIC11-ARB-105`). La redaction
        # d'origine n'en offrait qu'UNE -- `--overwrite`, donc la destruction
        # comme seule sortie -- et le scenario d'Egan la rend insuffisante: on
        # rescanne le meme lot avec un profil de calibration ameliore, et on
        # veut pouvoir COMPARER les deux sorties, pas remplacer l'ancienne.
        raise OutputFrameExistsError(
            f"{len(existing)} fichier(s) de sortie existent deja dans "
            f"{output_dir.name}: {sorted(existing)[:5]}"
            f"{' ...' if len(existing) > 5 else ''}. Rien n'a ete ecrit. "
            "Trois issues: relancer avec --nouvelle-version pour ecrire un jeu "
            "VOISIN sans toucher a celui-ci (le rang entre dans le nom du "
            "dossier, ce qui permet de comparer deux profils de calibration); "
            "relancer avec --overwrite pour les reecrire; ou supprimer ce lot "
            "(`mmu project remove --lot <id>`). Consequence a connaitre: "
            "--overwrite autorise du meme geste a ecraser les vraies frames "
            "deja ecrites; le rapport nomme les frames synthetiques, seul moyen "
            "de cibler une seconde passe sur les seuls bouche-trous."
        )
    return existing


# --- verification du dossier de sortie (AC 7) -------------------------------


def is_conforming_scan_frame_name(name: str, rush_id: str, fps_target: float) -> bool:
    """Le nom respecte-t-il la convention de frame rescannee de l'AC 1 ?

    Le motif n'est **jamais** reecrit ici, ni pour construire le nom ni pour le
    relire: la conformite est l'egalite du nom reconstruit avec le nom lu. C'est
    le pendant exact de `io.extraction_manifest._is_conforming_frame_name` cote
    `frames/`, et reconstruire le prefixe en local serait une seconde ecriture
    de la convention.
    """
    try:
        timecode = naming.read_scan_frame_timecode(name)
        return naming.build_scan_frame_filename(rush_id, fps_target, timecode) == name
    except Exception:
        return False


def _verify_output_dir(
    output_dir: Path, expected_names: set[str], *, rush_id: str, fps_target: float
) -> dict:
    """Confronter le dossier ecrit a ce qu'il devait contenir.

    Le compteur compte des **fichiers**, pas des entrees de repertoire: un
    sous-dossier n'est pas une frame (defaut deja consigne en revue de 3.4).

    Un fichier de **taille nulle** n'est pas une frame non plus, meme sous un
    nom conforme: mesure en revue (couche 2, moyenne 1), un fichier de 0 octet
    depose dans le dossier faisait monter `observed_frame_count` sans
    apparaitre ni dans les manquants ni dans les non conformes. Il tombe donc
    dans `nonconforming_files`, ou il se voit. L'ecriture n'etant pas atomique,
    c'est aussi la forme la plus courante d'artefact d'une passe interrompue.

    Un nom **conforme** appartient par construction a la convention de ce lot:
    il se reconstruit avec son `rush_id` et sa cadence. Un conforme que la
    passe courante n'a pas ecrit est donc une frame **preexistante** de ce lot,
    jamais un fichier etranger -- d'ou `preexisting_frames` et non
    « inattendus ».
    """
    entries = sorted(entry.name for entry in output_dir.iterdir() if entry.is_file())
    conforming: set[str] = set()
    nonconforming: list[str] = []
    for name in entries:
        if (
            is_conforming_scan_frame_name(name, rush_id, fps_target)
            and (output_dir / name).stat().st_size > 0
        ):
            conforming.add(name)
        else:
            nonconforming.append(name)
    return {
        "observed_frame_count": len(conforming),
        "missing_frames": tuple(sorted(expected_names - conforming)),
        "preexisting_frames": tuple(sorted(conforming - expected_names)),
        "nonconforming_files": tuple(nonconforming),
    }


# --- l'ecriture ------------------------------------------------------------


def _validate_pages(pages) -> tuple[tuple[ScannedPage, ...], int]:
    """Rendre les pages identifiees et le nombre de pages sans payload.

    Une page sans payload -- QR illisible, feuille arrachee -- n'est pas une
    erreur: c'est un trou, et il se declare. Elle ne peut simplement porter
    aucune ecriture, sa propre page etant la seule a porter ses timecodes.
    """
    if not isinstance(pages, (list, tuple)) or not pages:
        raise ScanOutputError(
            f"Pages de lot invalides: {pages!r}. Une sequence non vide de "
            "`ScannedPage` est attendue."
        )
    validated: list[ScannedPage] = []
    unidentified = 0
    for position, page in enumerate(pages):
        if not isinstance(page, ScannedPage):
            raise ScanOutputError(
                f"Page {position} invalide: {type(page).__name__}. Une "
                "`ScannedPage` est attendue."
            )
        if page.failure is not None:
            validate_synthetic_reason(page.failure)
        if page.payload is None:
            if page.failure is not None:
                raise ScanOutputError(
                    f"Page {position}: un motif de frame de remplacement "
                    f"({page.failure!r}) est declare sans payload decode. Le nom "
                    "de fichier et la seconde ligne de la mire se construisent "
                    "tous deux sur le timecode du payload de sa propre page: "
                    "sans lui, il n'y a pas de frame a ecrire mais un trou a "
                    "declarer."
                )
            unidentified += 1
            continue
        # Le payload est repasse a son autorite (`io.payload`), jamais
        # re-valide champ par champ ici: un payload prive de `gamut_map_id` est
        # refuse en amont, pas rattrape par une branche locale.
        payload_io.validate_payload(page.payload)
        slots = page.payload["slots"]
        # ... a une regle pres, que l'autorite ne porte pas encore: la **forme
        # canonique** du timecode (revue du 2026-08-08, couche 2, majeure 4).
        # `naming.validate_frame_timecode` existe et dit mot pour mot pourquoi:
        # « un payload QR portant la forme fichier hh-mm-ss-ff casserait le
        # recoupement QR <-> nom de fichier sans aucune erreur ». Elle n'etait
        # appelee nulle part. Les deux modes d'echec sont mesures:
        #
        # - `00:00:00:120` (cadence > 99 i/s) construit un nom que le lecteur
        #   refuse: le module ecrivait deux fichiers puis les declarait, dans le
        #   meme rapport, « non conformes » **et** « manquants »;
        # - `00-00-00-00` (deja la forme fichier) etait accepte et produisait le
        #   **meme nom** que le `00:00:00:00` canonique, `complete: true` --
        #   l'identite d'un fichier qui voyage seul changeait de forme en
        #   silence.
        #
        # La regle manquerait a tous les consommateurs du payload, pas
        # seulement a 5.6: la faire descendre dans `io.payload` est le bon
        # geste, mais il sort du perimetre de cette story (AC 11: « ne touche
        # pas io/payload.py »). Elle est donc appelee ici, a cote de son
        # autorite, jamais reecrite.
        for index, slot in enumerate(slots):
            try:
                naming.validate_frame_timecode(
                    slot["frame_timecode"],
                    label=f"slots[{index}].frame_timecode de la page {position}",
                )
            except naming.NamingError as error:
                raise ScanOutputError(
                    f"{error} Le nom de fichier est le seul support d'identite "
                    "d'une frame qui voyage seule: un timecode hors contrat 3.2 "
                    "produirait un nom que le lecteur de l'AC 1 ne relit pas, ou "
                    "un nom identique a celui d'un autre timecode."
                ) from error
        if page.failure is None:
            frames = page.frames
            if frames is None:
                raise ScanOutputError(
                    f"Page {position} (page_index "
                    f"{page.payload['page_index']}): aucune frame decoupee et "
                    "aucun motif d'echec. Une page sans l'un ni l'autre ne dit "
                    "pas si elle a reussi ou echoue."
                )
            if len(frames) != len(slots):
                raise ScanOutputError(
                    f"Page {position} (page_index "
                    f"{page.payload['page_index']}): {len(frames)} frames "
                    f"decoupees pour {len(slots)} slots declares. L'appariement "
                    "slot <-> frame est positionnel; un decalage graverait le "
                    "timecode d'une frame dans le nom d'une autre."
                )
        validated.append(page)
    return tuple(validated), unidentified


def _validated_page_profiles(pages: tuple[ScannedPage, ...], page_profiles) -> dict:
    """Rendre {page_index: profil} apres avoir refuse tout appariement douteux.

    Story 5.19. Les profils arrivent en **couples ``(page_index, profil)``** et non dans
    une sequence parallele aux pages, pour la meme raison que `ScanRecord` porte ses
    resultats de calibration ainsi: deviner l'index par le rang de la sequence est
    exactement l'appariement positionnel qui a coute six regressions a ce depot (mutants
    `M33`, `M25`). Un profil pose sur la mauvaise page corrigerait des pixels avec la
    correction d'une autre feuille -- et le resultat serait **plausible**, donc invisible.

    Trois refus, tous des erreurs d'appariement et jamais des donnees a ignorer:

    1. un profil pour une page que le lot ne declare pas -- le symetrique exact de la
       garde de `_build_calibration_results`, et la meme forme du risque R12;
    2. deux profils pour la meme page -- l'ordre de lecture deciderait lequel corrige;
    3. un objet qui n'offre pas `apply_linear` -- decouvert ici plutot que frame par
       frame, a mi-dossier.
    """
    if isinstance(page_profiles, dict):
        entries = tuple(page_profiles.items())
    else:
        entries = tuple(page_profiles or ())
    declared = {page.payload["page_index"] for page in pages}
    profiles: dict = {}
    for entry in entries:
        if not isinstance(entry, tuple) or len(entry) != 2:
            raise ScanOutputError(
                "Chaque profil de correction est un couple (page_index, profil), recu "
                f"{entry!r}."
            )
        page_index, profile = entry
        if not is_strict_int(page_index) or page_index < 0:
            raise ScanOutputError(
                f"page_index de profil invalide: {page_index!r}. Un entier base zero "
                "est attendu, et jamais un booleen."
            )
        if page_index in profiles:
            raise ScanOutputError(
                f"Deux profils de correction declarent le meme page_index {page_index}. "
                "Une page a **une** correction: en accepter deux laisserait l'ordre de "
                "lecture decider laquelle touche les pixels."
            )
        if page_index not in declared:
            raise ScanOutputError(
                f"Profil de correction pour une page absente du lot: {page_index}. "
                f"Pages declarees: {sorted(declared)}. Rien n'a ete ecrit: un profil "
                "mal apparie corrigerait une feuille avec la correction d'une autre, et "
                "le resultat serait plausible."
            )
        if profile is None or not hasattr(profile, "apply_linear"):
            raise ScanOutputError(
                f"Profil de correction de la page {page_index} inutilisable: "
                f"{type(profile).__name__} n'offre pas `apply_linear`. Voir "
                "color_calibration.CorrectionProfile."
            )
        profiles[page_index] = profile
    return profiles


#: Ligne d'eau des versions de frames rescannees, de niveau LOT.
OUTPUT_FRAMES_WATERMARK_FIELD = "output_frames_version_watermark"


def _nom_de_rang(slug: str, rang: int) -> str:
    """Le nom de dossier que porterait le rang `rang` de la famille `slug`.

    Ecrit une seule fois parce que la correction du 2026-09-04 lui donne DEUX
    lecteurs -- le balayage des rangs consommes et le controle de
    disponibilite du nom retenu -- et que deux compositions du meme nom sont
    deux verites, donc deux occasions de diverger. `EPIC11-ARB-88` : le rang
    d'origine ne porte AUCUN fragment, son absence le dit.
    """
    if rang == version_ranks.RANG_ORIGINE:
        return slug
    return f"{slug}{naming.format_version_suffix(rang)}"


def resolve_output_frames_version_rank(
    project_dir, lot_id: str, slug: str, manifest=None
) -> int:
    """Le rang du PROCHAIN jeu de frames rescannees de ce lot.

    `EPIC11-ARB-105`. Cinquieme objet a passer sur `io.version_ranks`, et la
    regle y est la meme qu'ailleurs : un rang se CONSOMME, il ne se rend qu'en
    queue et sur demande.

    Le disque est consulte en PLUS du manifeste, jamais a la place : un dossier
    `output-frames/<slug>_vN` present que le manifeste ignore -- ecrit avant cet
    arbitrage, ou depose a la main -- a bel et bien consomme son rang.
    """
    declaree = None
    for lot in (manifest or {}).get("lots") or []:
        if isinstance(lot, dict) and lot.get("lot_id") == lot_id:
            declaree = lot.get(OUTPUT_FRAMES_WATERMARK_FIELD)
            break
    # **Les dossiers d'AUTRES lots ne comptent pas dans cette famille**
    # (trouve en revue, couche 2, sur le chemin NOMINAL). Le slug des frames
    # d'un lot est son `lot_id`, et un lot versionne porte deja son rang dans
    # son identifiant : `output-frames/rush-001_12p5_v2` est le dossier du LOT
    # v2, pas le rescan v2 du lot d'origine. Le balayage de noms les
    # confondait, si bien qu'un lot d'origine JAMAIS rescanne partait au rang 3
    # des lors que son lot v2 avait ete scanne une fois.
    #
    # La famille se lit donc au manifeste -- la meme source que la ligne d'eau
    # -- et le disque n'est consulte que pour ce qu'il ajoute.
    autres_slugs = {
        lot.get("lot_id") for lot in ((manifest or {}).get("lots") or [])
        if isinstance(lot, dict) and lot.get("lot_id") != lot_id
    }
    # **Les DEUX racines, et c'est un defaut de perte de donnees qui l'exige**
    # (finding `E2-1` de la revue du 2026-09-04). Cette fonction lisait la
    # seule racine `project_layout.OUTPUT_FRAMES_DIRNAME`, qui est depuis la
    # story 11.14 un ALIAS du nom neuf : sur un projet d'avant, les rangs deja
    # consommes sous `output-frames/` devenaient donc **invisibles**, la
    # fonction rendait un rang **deja pris**, et le rescan suivant ecrasait des
    # frames existantes -- un ecrasement NON CONSCIENT, que `EPIC11-ARB-104` et
    # `EPIC11-ARB-105` interdisent l'un comme l'autre.
    #
    # Les quatre autres lecteurs de frames scannees de `src/` passaient deja
    # par `racines_de_frames_scannees` ; celui-ci etait le seul a ne pas le
    # faire, et c'est precisement le regime ou l'asymetrie coute le plus cher.
    rangs: set[int] = set()
    for racine in project_layout.racines_de_frames_scannees(project_dir):
        if not racine.is_dir():
            continue
        presents = {chemin.name for chemin in racine.iterdir() if chemin.is_dir()}
        for rang in [version_ranks.RANG_ORIGINE,
                     *range(naming.VERSION_RANK_MIN, naming.VERSION_RANK_MAX + 1)]:
            if _nom_de_rang(slug, rang) in presents \
                    and _nom_de_rang(slug, rang) not in autres_slugs:
                rangs.add(rang)
    if not rangs and not isinstance(declaree, int):
        rang = version_ranks.RANG_ORIGINE
    else:
        rang = version_ranks.prochain_rang(
            version_ranks.ligne_d_eau(declaree, rangs))
    # **COMPTER un rang et POUVOIR L'EMPLOYER sont deux questions, et n'en
    # poser qu'une melangeait DEUX LOTS dans un seul dossier** (revue 11.14,
    # couche 1, mesure bout en bout).
    #
    # L'exclusion `autres_slugs` ci-dessus est juste et reste : le dossier du
    # LOT v2 n'est pas le rescan v2 du lot d'origine, et l'y compter faisait
    # partir a 3 un lot jamais rescanne. Mais elle ne repondait qu'a « ce rang
    # a-t-il ete consomme par MA famille ? ». Restait « le NOM de ce rang
    # est-il libre ? » -- et il ne l'est pas : le rang entre dans le nom du
    # dossier (`EPIC11-ARB-88`), et `rush-001_5_v2` est simultanement le rang 2
    # du lot `rush-001_5` et l'identifiant du LOT v2.
    #
    # Mesure du defaut, deux lots du meme rush ecrits puis le lot d'ORIGINE
    # rescanne avec `--nouvelle-version` (le manifeste est passe, comme le fait
    # `scan_write.py`) :
    #
    #     rang rendu pour le lot d'origine : 2
    #     frames-scannees/rush-001_5_v2 -> 4 fichiers, LES DEUX LOTS MELANGES
    #
    # Aucun refus, aucun avertissement -- et `encode.py` lit ce dossier tel
    # quel, donc le master du LOT v2 se fabrique sur les frames de deux lots
    # differents : la classe R12, que ce module existe pour fermer. Sans le
    # manifeste, la meme passe rendait 3 et n'ecrasait rien : c'est l'exclusion
    # seule qui produisait le defaut, ce qui la designe sans ambiguite.
    #
    # Le remede ne retire pas l'exclusion -- il la COMPLETE. Un rang dont le
    # nom appartient a un autre lot est INDISPONIBLE : on avance, comme
    # `prochain_rang` avance deja sur un trou (« le trou reste un trou »). Le
    # cas qui a fait poser l'exclusion reste vert : lot v2 seul present, lot
    # d'origine jamais rescanne, le nom du rang 1 est `rush-001_5` et il
    # n'appartient a personne d'autre -- rang 1, inchange.
    while rang <= naming.VERSION_RANK_MAX and _nom_de_rang(slug, rang) in autres_slugs:
        rang += 1
    if rang > naming.VERSION_RANK_MAX:
        raise ScanOutputError(version_ranks.refus_de_rangs_epuises(
            "frames scannees", lot_id,
            # Meme correction que pour les scans : aucune commande ne
            # supprime un jeu de frames scannees seul, et un refus qui nomme
            # une sortie inexistante est un blocage sec deguise.
            # Le geste FIN existe depuis `EPIC11-ARB-111`.
            #
            # **Le drapeau cite ici a ete RENOMME par le lot C de la story
            # 11.14** (`--frames` -> `--frames-scannees`, `EPIC11-ARB-220`,
            # retrait pur). Ce module etant hors du perimetre de ce lot, le
            # refus a continue de citer `--frames` pendant deux commits : un
            # drapeau qui n'existe plus, donc exactement le blocage sec
            # deguise que le commentaire ci-dessus dit eviter. C'est
            # `test_conformite_sorties_nommees.py` qui l'a rougi, pas une
            # relecture -- et c'est pour ce genre d'ecart que cette frontiere
            # existe.
            "Deux issues: supprimer le DERNIER lot scanne en liberant son "
            "rang (`mmu project remove --lot <id> --lot-scanne --version "
            "<rang> --liberer-le-rang --confirmer`, qui ne retire que ce lot "
            "scanne), ou ecraser sciemment un lot scanne existant "
            "(--overwrite).",
        ))
    return rang


def write_lot_output_frames(
    project_dir: str | Path,
    pages,
    *,
    overwrite: bool = False,
    color_calibration_status: str = color_pipeline.NOT_APPLIED_STATUS,
    page_profiles=(),
    rappel_progression=None,
    nouvelle_version: bool = False,
    manifest=None,
) -> LotOutputReport:
    """Ecrire les frames d'un lot scanne sous `output-frames/<slug>/`.

    Un lot **incomplet est ecrit et declare incomplet**, jamais refuse en bloc
    ni declare complet: il est normal qu'une page manque a la premiere passe de
    scan. Le seul faux pas interdit est le faux succes (risque R12).

    Les refus durs -- lot melange, timecode duplique, forme conflictuelle,
    fichier existant sans `overwrite` -- sont tous leves **avant** la premiere
    ecriture, pour qu'un refus ne laisse jamais un dossier a demi rempli.

    `color_calibration_status` est **transporte**, jamais calcule: la
    correction couleur appartient a 5.4, et son statut de lot se derive par
    `color_pipeline.derive_lot_calibration_status`.

    `page_profiles` porte la correction retenue **par page** (story 5.19, AC 3), en
    couples ``(page_index, profil)``. C'est ce qui manquait pour que la correction touche
    les pixels: ce module recevait le statut et aucun profil, donc il declarait une
    correction qu'il ne pouvait pas appliquer. Vide -- son defaut --, rien ne change: le
    chemin non corrige reste celui de tout lot dont la page de calibration manque ou est
    illisible, et l'AC 12 exige qu'il rende le meme document qu'avant, octet a octet.

    `rappel_progression` est **optionnel** (`AR3`, story 5.28) : sans lui, rien ne
    change. Avec lui, il recoit un jalon `(faites, total)` **par frame reellement
    ecrite**, ou `total` vaut `len(planned)` -- un cardinal de liste, exact par
    construction. Les jalons sont emis **dans** la boucle d'ecriture et jamais
    avant : tous les refus durs precedent cette boucle, et un refus ne doit donc
    produire aucune progression. Le canal est observationnel (`EPIC7-ARB-79`) : un
    rappel qui leve est absorbe et journalise une seule fois, tandis que les refus
    durs ci-dessus traversent intacts, texte compris.
    """
    if not isinstance(overwrite, bool):
        raise ScanOutputError(
            f"`overwrite` doit etre un booleen, recu {overwrite!r}."
        )
    color_pipeline.validate_calibration_status(color_calibration_status)

    project_dir = Path(project_dir)
    validated, unidentified = _validate_pages(pages)

    identity = _lot_identity(validated)
    rush_id = identity["rush_id"]
    fps_target = identity["fps_target"]
    slug = derive_lot_dir_slug(
        rush_id=rush_id, fps_target=fps_target, lot_id=identity["lot_id"]
    )
    # LES FRAMES RESCANNEES SONT VERSIONNABLES (`EPIC11-ARB-105`, Egan
    # 2026-08-31). Scenario : on rescanne le MEME lot avec un profil de
    # calibration ameliore -- le contenu des frames change, l'identite du lot
    # non. Sans rang, la seule issue etait `--overwrite`, qui detruit la sortie
    # du profil precedent et interdit de comparer les deux.
    #
    # Le rang est celui des FRAMES, distinct de celui du LOT : un lot versionne
    # porte deja son rang dans son `slug`, et ce rang-ci compte les rescans du
    # meme lot.
    rang_de_version = None
    if nouvelle_version:
        rang = resolve_output_frames_version_rank(
            project_dir, identity["lot_id"], slug, manifest)
        rang_de_version = None if rang == version_ranks.RANG_ORIGINE else rang
    output_dir = project_layout.scan_frames_dir_from_slug(
        project_dir,
        slug if rang_de_version is None
        else f"{slug}{naming.format_version_suffix(rang_de_version)}",
    )

    # Le gabarit se **resout** avant toute ecriture. `template_id` est un champ
    # du payload QR et `validate_payload` n'en exige qu'une chaine non vide: le
    # registre n'etait consulte qu'au calcul du cardinal attendu, donc apres la
    # boucle d'ecriture. Mesure en revue: une planche portant un `template_id`
    # retire du vocabulaire ecrivait ses six frames puis levait une
    # `UnknownTemplateError` venue d'un troisieme module, sans rapport -- un
    # dossier entierement rempli mais orphelin, et une relance bloquee sans
    # `--overwrite`. Le cardinal peut continuer d'etre calcule plus tard; c'est
    # la **resolution** qui doit preceder l'ecriture.
    try:
        template = page_templates.get_template(identity["template_id"])
    except page_templates.UnknownTemplateError as error:
        raise ScanOutputError(
            f"{error} Rien n'a ete ecrit: le gabarit se resout avant la premiere "
            "ecriture, sans quoi un lot entier atterrit sur le disque de "
            "l'operateur sous un rapport qui n'existe pas."
        ) from error

    planned, shape_indeterminable, unwritten_timecodes = _plan_lot_writes(
        validated,
        rush_id=rush_id,
        fps_target=fps_target,
        frames_per_page=template.frames_per_page,
        page_profiles=_validated_page_profiles(validated, page_profiles),
    )
    # Le refus d'ecrasement precede la creation du dossier: un refus ne laisse
    # ainsi aucune trace, pas meme un dossier vide.
    overwritten = _assert_writable(output_dir, planned, overwrite=overwrite)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        # `output-frames/<slug>` existant en tant que **fichier** sortait en
        # `FileExistsError` nu: la hierarchie du module ne couvrait aucun echec
        # venant du systeme de fichiers, alors que le module *est* celui qui
        # ecrit sur le disque (revue couche 2, moyenne 3).
        raise ScanOutputError(
            f"Dossier de sortie {output_dir} non creable: {error}. Rien n'a ete "
            "ecrit."
        ) from error

    # Le canal ne s'ouvre qu'ICI, une fois tous les refus durs passes: un lot
    # refuse ne doit produire aucun jalon, sans quoi l'ecran afficherait une
    # tache qui a commence alors que rien n'a ete ecrit.
    emetteur = progression.EmetteurProgression(rappel_progression, len(planned))

    frames: list[OutputFrame] = []
    for entry in planned:
        target = output_dir / entry.filename
        # `export_frame_tiff16` **rend** la profondeur et le format reellement
        # ecrits: ils ne sont jamais reecrits en dur a cote de l'appel, ce qui
        # est le defaut « manifest et artefact reel peuvent diverger » ferme en
        # revue de 5.5. Aucune conversion d'espace de couleur ni d'ordre de
        # canaux n'a lieu: la chaine est en BGR de bout en bout.
        try:
            exported = color_pipeline.export_frame_tiff16(entry.image, str(target))
        except (OSError, cv2.error, RuntimeError) as error:
            # Disque plein, nom trop long, octet NUL dans le chemin, dossier
            # portant le nom d'une frame: tous sortaient hors de la hierarchie
            # du module. Le fichier vise est nomme -- c'est lui qu'il faudra
            # aller regarder, l'ecriture n'etant pas atomique.
            if isinstance(error, ScanOutputError):
                raise
            raise ScanOutputError(
                f"Echec d'ecriture de {entry.filename} dans {output_dir}: "
                f"{error}. Les frames deja ecrites de cette passe restent sur "
                "le disque; le fichier vise peut etre tronque."
            ) from error
        frames.append(
            OutputFrame(
                page_index=entry.page_index,
                slot_index=entry.slot_index,
                frame_timecode=entry.frame_timecode,
                filename=entry.filename,
                path=_project_relative_posix(target, project_dir),
                synthetic=entry.synthetic,
                synthetic_reason=entry.synthetic_reason,
                # La profondeur **du scan** prime sur celle que l'export deduit du
                # tableau: une frame corrigee arrive requantifiee sur 16 bits, donc
                # l'export ne peut plus voir qu'elle venait d'un scan 8 bits (story
                # 5.19). Elle n'est renseignee que la, si bien que le chemin non corrige
                # continue de lire l'export, comme avant.
                source_bit_depth=(
                    exported["source_bit_depth"] if entry.source_bit_depth is None
                    else entry.source_bit_depth
                ),
                output_bit_depth=exported["output_bit_depth"],
                output_format=exported["output_format"],
                overwritten=entry.filename in overwritten,
            )
        )
        # Un jalon **apres** l'ecriture, jamais avant: le numerateur est
        # litteralement le nombre de fichiers deja sur le disque.
        emetteur.emettre(len(frames))

    report = _build_report(
        project_dir=project_dir,
        output_dir=output_dir,
        identity=identity,
        pages=validated,
        frames=tuple(frames),
        shape_indeterminable=tuple(shape_indeterminable),
        unwritten_timecodes=tuple(unwritten_timecodes),
        unidentified_page_count=unidentified,
        overwritten=overwritten,
        color_calibration_status=color_calibration_status,
    )
    _assert_no_absolute_path(report)
    return report


def _project_relative_posix(path: Path, project_dir: Path) -> str:
    """Chemin relatif au dossier projet, en separateurs POSIX.

    La conversion et les refus sont ceux de `io.extraction_manifest`, importes:
    ils attrapent aussi ce que le detecteur de chemins absolus laisse passer --
    antislashs relatifs et remontees `..`. L'exception est retraduite dans la
    hierarchie du module, un appelant de la chaine scan n'ayant aucune raison
    de rattraper une erreur de persistance d'extraction.
    """
    try:
        relative = path.relative_to(project_dir)
    except ValueError as error:
        raise ScanOutputError(
            f"Le fichier ecrit {path} n'est pas sous le dossier projet "
            f"{project_dir}: aucun chemin relatif n'est publiable."
        ) from error
    try:
        return _relative_posix(relative, "chemin de frame de sortie")
    except ExtractionPersistenceError as error:
        raise ScanOutputError(str(error)) from error


def _assert_no_absolute_path(report: LotOutputReport) -> None:
    """Filet final: aucun chemin absolu dans l'artefact produit (AC 10).

    Le detecteur est celui du depot, **importe** et jamais reecrit: une seconde
    ecriture du motif divergerait au premier ajustement.
    """
    violations = _iter_absolute_path_violations(report.as_document())
    if violations:
        raise ScanOutputError(
            f"Chemin absolu dans le rapport de sortie a '{violations[0]}'. Le "
            "contrat v2 interdit tout chemin absolu, pour qu'un lot reste "
            "reconstructible sur une machine tierce."
        )


def _build_report(
    *,
    project_dir: Path,
    output_dir: Path,
    identity: dict,
    pages: tuple[ScannedPage, ...],
    frames: tuple[OutputFrame, ...],
    shape_indeterminable: tuple[int, ...],
    unwritten_timecodes: tuple[str, ...],
    unidentified_page_count: int,
    overwritten: set[str],
    color_calibration_status: str,
) -> LotOutputReport:
    rush_id = identity["rush_id"]
    fps_target = identity["fps_target"]
    page_count = identity["page_count"]

    expected = _expected_frame_count(
        pages, template_id=identity["template_id"], page_count=page_count
    )
    verification = _verify_output_dir(
        output_dir,
        {frame.filename for frame in frames},
        rush_id=rush_id,
        fps_target=fps_target,
    )

    seen_pages = {page.payload["page_index"] for page in pages}
    missing_pages = tuple(
        index for index in range(page_count) if index not in seen_pages
    )
    synthetic_count = sum(1 for frame in frames if frame.synthetic)

    # Trois conditions **necessaires** (AC 7), plus trois interdits de faux
    # succes ajoutes en revue: un fichier compte a l'ecriture mais absent du
    # dossier, une page du lot jamais vue, et une sequence de formes
    # heterogenes -- que le module tient lui-meme pour l'equivalent d'un trou
    # des lors qu'une mire doit etre posee. Le faux succes est le seul faux pas
    # interdit (R12), et un rapport ne doit pas pouvoir se contredire dans le
    # meme document.
    complete = (
        expected is not None
        and len(frames) == expected
        and synthetic_count == 0
        and not verification["missing_frames"]
        and not missing_pages
        and len(_observed_shapes(pages)) <= 1
    )

    warnings: list[str] = []
    if synthetic_count:
        warnings.append("SYNTHETIC_FRAME_WRITTEN")
    if shape_indeterminable:
        warnings.append("SYNTHETIC_FRAME_SHAPE_INDETERMINABLE")
    if expected is None:
        warnings.append("EXPECTED_FRAME_COUNT_INDETERMINABLE")
    if len(_observed_shapes(pages)) > 1:
        warnings.append("HETEROGENEOUS_FRAME_SHAPES")
    if missing_pages:
        warnings.append("PAGE_MISSING_FROM_LOT")
    if unidentified_page_count:
        warnings.append("PAGE_QR_UNREADABLE")
    if _underfilled_pages(pages, page_count=page_count, template_id=identity["template_id"]):
        warnings.append("PAGE_SLOT_COUNT_BELOW_TEMPLATE")
    if overwritten:
        warnings.append("OUTPUT_FRAME_OVERWRITTEN")
    if verification["nonconforming_files"]:
        warnings.append("NONCONFORMING_FILE_IN_OUTPUT_DIR")
    if verification["preexisting_frames"]:
        warnings.append("PREEXISTING_FRAME_IN_OUTPUT_DIR")
    if verification["missing_frames"]:
        warnings.append("EXPECTED_FRAME_FILE_MISSING")

    # La profondeur du **scan** se mesure sur les pages ingerees, jamais sur les
    # frames generees: une frame synthetique n'entre dans aucune statistique de
    # profondeur ni de couleur (piege 9).
    source_depths = sorted(
        {frame.source_bit_depth for frame in frames if not frame.synthetic}
    )
    output_depths = {frame.output_bit_depth for frame in frames}
    output_formats = {frame.output_format for frame in frames}

    return LotOutputReport(
        lot_id=identity["lot_id"],
        rush_id=rush_id,
        fps_target=fps_target,
        project_id=identity["project_id"],
        template_id=identity["template_id"],
        gamut_map_id=identity["gamut_map_id"],
        target_colorspace=identity["target_colorspace"],
        patch_preset_id=identity["patch_preset_id"],
        color_calibration_status=color_calibration_status,
        output_dir=_project_relative_posix(output_dir, project_dir),
        page_count=page_count,
        expected_frame_count=expected,
        written_frame_count=len(frames),
        synthetic_frame_count=synthetic_count,
        observed_frame_count=verification["observed_frame_count"],
        complete=complete,
        frames=frames,
        source_bit_depths=tuple(source_depths),
        output_bit_depth=output_depths.pop() if len(output_depths) == 1 else None,
        output_format=output_formats.pop() if len(output_formats) == 1 else None,
        missing_pages=missing_pages,
        unidentified_page_count=unidentified_page_count,
        shape_indeterminable_pages=shape_indeterminable,
        missing_frames=verification["missing_frames"],
        unwritten_frame_timecodes=unwritten_timecodes,
        nonconforming_files=verification["nonconforming_files"],
        preexisting_frames=verification["preexisting_frames"],
        overwritten_files=tuple(sorted(overwritten)),
        warnings=tuple(validate_warning_code(code) for code in warnings),
    )


def report_document(report: LotOutputReport) -> dict:
    """Document canonique, empreinte comprise."""
    document = report.as_document()
    document["fingerprint"] = fingerprint_of(document)
    return document


def report_json(report: LotOutputReport) -> str:
    """Serialisation canonique: deux passes identiques rendent le meme texte.

    Helpers de canonicalisation importes d'`extraction_previz`, jamais recopies.
    """
    return canonical_json(report_document(report))


__all__ = [
    "CHECKER_ROWS",
    "DEFAULT_SYNTHETIC_CHANNELS",
    "BIT_DEPTH_PROMOTION_FACTOR",
    "FINGERPRINT_PREFIX",
    "MAX_LEVEL_8BIT",
    "MAX_LEVEL_16BIT",
    "MIN_CHECKER_CELL_PX",
    "MISSING_FRAME_TEXT",
    "SCAN_OUTPUT_WARNING_CODES",
    "SYNTHETIC_FRAME_REASONS",
    "DuplicateFrameTimecodeError",
    "FrameShapeConflictError",
    "LotInconsistencyError",
    "LotOutputReport",
    "OutputFrame",
    "OutputFrameExistsError",
    "ScanOutputError",
    "ScannedPage",
    "build_checkerboard",
    "build_missing_frame_image",
    "derive_checker_cell_px",
    "derive_lot_dir_slug",
    "derive_text_scale",
    "derive_text_thicknesses",
    "is_conforming_scan_frame_name",
    "measured_pen_cap",
    "missing_frame_second_line",
    "report_document",
    "report_json",
    "validate_synthetic_reason",
    "validate_warning_code",
    "write_lot_output_frames",
]
