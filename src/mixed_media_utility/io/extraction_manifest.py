"""Persistance manifest de l'extraction (story 3.4).

Perimetre
---------
Ce module est le **contrat de persistance** de la chaine d'extraction: il
prend ce que les stories 3.1 (identite, dossier de lot), 3.2
(``frame_selection.FrameSelection``) et 3.3
(``source_confirmation``) ont produit, et l'ecrit dans le manifest v2 du
projet, a un emplacement unique et documente pour chaque donnee (voir
``EXTRACTION_*_FIELDS`` et la Table de persistance de la story).

Un porteur par donnee (schema v2.1, ``decisions-2026-08-04.md``)
---------------------------------------------------------------
Un projet porte **plusieurs rushs**, et chaque rush peut donner lieu a
**plusieurs cadences d'extraction**. Le placement en decoule et n'est pas
negociable:

* tout ce qui decrit la **source** (cadence source, resolution, codec, format
  de pixel, profondeur, colorimetrie, timecode de depart) vit dans
  ``rushes[]``: ces valeurs ne varient pas d'un lot a l'autre, mais varient
  d'un rush a l'autre;
* la **cadence cible** vit dans ``lots[]`` (``fps_target``,
  ``fps_target_exact``): c'est ce qui distingue par definition deux lots d'un
  meme rush;
* ``video`` ne garde que la cible d'**encodage** (``codec_target``, Epic 6) et
  n'est plus ecrite du tout par ce module.

En v2.0, ces donnees vivaient dans une section ``video`` **unique par
projet** alors que ``rushes`` et ``lots`` sont des listes: extraire un meme
rush vers deux cadences ecrasait ``video.fps_target``, et
``verify_extracted_lot`` declarait alors le **premier** lot non conforme alors
que ses fichiers etaient intacts. Un manifest v2.0 rencontre ici est migre en
memoire vers la v2.1 avant fusion (voir ``build_extraction_manifest``).

Il est **le dernier maillon**: il consomme, il ne redefinit rien en amont.
En particulier il ne re-probe rien, ne recompte aucun fichier sur disque
pour remplacer ``expected_frame_count`` (un lot tronque se declarerait
complet), et ne **re-normalise pas** les sentinelles ffprobe (``unknown``,
``unspecified``, ``reserved``, ``N/A``): cette normalisation a deja eu lieu
dans la story 3.3, la refaire ici creerait deux verites.

Surface publique volontairement reduite (Piege 10): ``persist_extraction``,
``build_extraction_manifest``, ``verify_extracted_lot`` et
``compute_frame_timecodes_digest``. **Aucun** ecrivain de manifest generique
n'est expose: le perimetre est l'extraction, pas l'ecriture de n'importe
quoi dans ``project.json``.

Regle de partage ``source_bit_depth`` (verrouillee, AC 3)
--------------------------------------------------------
Deux grandeurs homonymes coexistent dans le manifest et ne doivent
**jamais** etre fusionnees:

* ``rushes[].source_bit_depth`` -- profondeur de bits declaree du **rush**
  (story 3.3). 10 et 12 bits y sont le cas nominal (ProRes).
* ``color.source_bit_depth`` -- profondeur d'un **scan** recu
  (``color_pipeline.COLOR_MANIFEST_FIELDS``), dont
  ``color_pipeline.mvp_color_manifest_fragment`` **refuse toute valeur hors
  ``(8, 16)``**.

Les fusionner ne produirait pas seulement un ecrasement, mais une valeur
que le chemin couleur juge illegale. Ce module **n'ecrit, ne lit et
n'efface aucune cle de ``color``**: si la section existe deja, elle est
recopiee telle quelle. ``lots[].output_bit_depth`` est une troisieme
grandeur encore distincte: la profondeur des TIFF **ecrits**, normalisee a
16 bits quelle que soit la source (``decisions-2026-08-03.md``, decision 4).

Absence encodee positivement (AC 2)
-----------------------------------
Un champ source non renseigne (``None`` cote 3.3) est **omis**: jamais
``null``, jamais ``"unknown"``, jamais une valeur par defaut (``bt709``,
``8`` bits, ``tv``). L'ensemble trie des omissions est ecrit dans
``rushes[].source_metadata_absent_fields``, pour qu'un tiers distingue « la
source n'etait pas taguee » de « une version anterieure de l'outil ne notait
pas ce champ ».

Le schema attrape le ``null`` -- et depuis la v2.1 il l'attrape par
construction, ``rushes[]`` etant en ``additionalProperties: false`` avec
chaque propriete ``source_*`` typee. Il n'attrape **pas** ``"unknown"``,
chaine non vide parfaitement valide, qui serait ensuite relue comme une
colorimetrie declaree: le garde-fou du sentinel est la normalisation de 3.3,
pas le schema.

Une seule forme de serialisation de cadence
-------------------------------------------
``codec_profiles.exact_frame_rate``, et elle seule, dans tout le module:
``rushes[].fps_source_exact``, ``lots[].fps_target_exact``,
``lots[].timecode_base_fps`` **et** l'en-tete de l'empreinte de selection.
Elle rend ``"30/1"``, denominateur toujours explicite. Ni ``str(Fraction)``
(qui rendrait ``"30"``), ni ``f"{fps}"``, ni un flottant: une autre recette
produirait une empreinte differente pour la meme selection (question ouverte
10 de la story).

Trace de confirmation dans le manifest (AC 14)
----------------------------------------------
``lots[].confirmation`` porte ``mode``, ``unknown_color_accepted`` et
``confirmed_at``. Justification de l'emplacement: ``logs/`` **n'est pas
transporte avec un lot**, donc la seule trace de consentement qui survit au
transfert doit vivre dans le manifest. Le bloc ne porte jamais de nom
d'utilisateur, de machine ni de chemin. ``confirmed_at`` est le champ que la
story 3.3 nomme ``timestamp_utc`` dans son bloc de decision: c'est un
renommage a la frontiere du manifest, assume, pas deux horodatages. Le
``granted`` de 3.3 n'est pas persiste -- la persistance n'a lieu que sur
accord, un ``granted: false`` serait un etat inatteignable.

Ce qu'un tiers peut verifier (AC 15)
------------------------------------
* **Niveau 1 -- manifest seul, sans outil.** Cardinal attendu, cadences
  typees et exactes, resolution source, codec, format de pixel, profondeur,
  colorimetrie declaree, liste des champs absents, base de timecode et sa
  cadence, politique d'arrondi, avertissements de selection, trace de
  confirmation. Il juge si le lot repond a son besoin **avant** de l'ouvrir.
* **Niveau 2 -- manifest + dossier de lot, sans outil.** Nombre de fichiers
  contre ``expected_frame_count``, conformite de chaque nom a la convention
  ``<rush>_<fps-court>_<timecode>.tiff``, absence de fichier etranger.
* **Niveau 3 -- manifest + dossier + ``mixed_media_utility`` installe.**
  Recalcul de la selection depuis ``rushes[].fps_source_exact``,
  ``lots[].fps_target_exact``, ``lots[].source_frame_count`` et
  ``lots[].rounding_policy``, compare a ``frame_timecodes_digest``. Chaque lot
  est recalcule avec **sa** cadence cible et celle de **son** rush: trois lots
  du meme rush a 3, 5 et 12,5 im/s se verifient donc independamment.

Ce qu'il **ne peut pas** verifier, et qu'il ne faut pas promettre: que les
pixels correspondent au rush (aucune empreinte de contenu n'est persistee);
que le cardinal source etait exact (si ``source_frame_count_is_exact`` est
``false``, le manifest signale la reserve, il ne la leve pas); que la
colorimetrie declaree est vraie (elle est **recopiee**, jamais mesuree).

``io.manifest.validate_manifest_completeness`` n'est **pas** un critere de
succes ici: elle exige ``video.codec_target`` (decide a l'encode, Epic 6) et
``color.target_colorspace`` (cible d'encodage, pas une propriete du rush).
Un projet fraichement extrait ne la satisfait pas, et c'est correct; le
rapport de verification signale l'ecart sans le transformer en echec.

Appelant
--------
``persist_extraction`` est appele par la commande ``extract`` (story 3.1),
juste apres l'ecriture reussie des TIFF (``decisions-2026-08-03.md``,
decision 1 / ARB-1). Cette story ne modifie pas ``cli.py``.

Convention d'ecriture: messages en francais **sans accents**, comme
``io/manifest.py``, ``codec_profiles.py`` et ``source_confirmation.py``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Mapping

from jsonschema.exceptions import ValidationError

from ..codec_profiles import exact_frame_rate
from ..frame_selection import FrameSelection, select_source_frames
from ..numeric_guards import is_strict_int
from . import version_ranks
from .manifest import (
    CURRENT_SCHEMA_VERSION,
    LOT_STATES,
    load_manifest,
    validate_lot_state_transition,
    validate_manifest,
)
from .naming import (
    VERSION_RANK_MAX,
    VERSION_RANK_MIN,
    build_extracted_frame_filename,
    build_lot_id,
    derive_short_id,
    format_fps_short,
    read_extracted_frame_timecode,
)
from .project_layout import FRAMES_DIRNAME

__all__ = [
    "MANIFEST_FILENAME",
    "MANIFEST_SCHEMA_VERSION",
    "MIGRATABLE_SCHEMA_VERSIONS",
    "EXTRACTION_LOT_STATE",
    "EXTRACTION_OUTPUT_BIT_DEPTH",
    "FRAME_DIGEST_PREFIX",
    "EXTRACTION_ROOT_FIELDS",
    "EXTRACTION_RUSH_FIELDS",
    "EXTRACTION_LOT_FIELDS",
    "EXTRACTION_VIDEO_FIELDS",
    "SOURCE_REPORT_RUSH_FIELDS",
    "EXTRACTION_ARTIFACT_FIELDS",
    "CONFIRMATION_FIELDS",
    "NON_IDEMPOTENT_FIELDS",
    "VERIFICATION_CODES",
    "INFORMATIONAL_VERIFICATION_CODES",
    "ExtractionPersistenceError",
    "LegacyManifestError",
    "LotStateConflictError",
    "LotIdentityMismatchError",
    "ManifestWriteError",
    "ExtractionRecord",
    "RushRecord",
    "LotVerification",
    "PersistedExtraction",
    "PersistedRushDeclaration",
    "compute_frame_timecodes_digest",
    "build_extraction_manifest",
    "verify_extracted_lot",
    "persist_extraction",
    "rush_record_de_l_extraction",
    "build_rush_declaration_manifest",
    "persist_rush_declaration",
    "validate_extraction_state_transition",
    "resolve_version_rank",
    "message_avertissement_ecrasement",
]


# --------------------------------------------------------------------------
# Constantes de contrat
# --------------------------------------------------------------------------

MANIFEST_FILENAME = "project.json"

#: Version du contrat ecrite par ce module, lue dans `io.manifest` pour qu'un
#: seul litteral existe dans le depot. La v2.1 replace la source sur le rush et
#: la cadence cible sur le lot (`decisions-2026-08-04.md`).
MANIFEST_SCHEMA_VERSION = CURRENT_SCHEMA_VERSION

#: Versions anterieures qu'une extraction sait **migrer en memoire** avant de
#: fusionner. La migration est deterministe parce qu'un manifest v2.0 ne porte
#: par construction qu'une seule cadence source et une seule cadence cible pour
#: tout le projet: elles se repliquent sans ambiguite sur chaque rush et sur
#: chaque lot. Rien n'est devine.
MIGRATABLE_SCHEMA_VERSIONS: tuple[str, ...] = ("2.0",)

#: Etat de lot pose par cette story, exclusivement via
#: `io.manifest.validate_lot_state_transition`.
EXTRACTION_LOT_STATE = "extraction"

from mixed_media_utility.constants import OUTPUT_BIT_DEPTH as EXTRACTION_OUTPUT_BIT_DEPTH

#: Prefixe d'algorithme de l'empreinte de selection. Il vit **dans la
#: valeur**, pas dans un champ separe, pour qu'un futur changement
#: d'algorithme reste lisible sans ajouter de champ au schema.
FRAME_DIGEST_PREFIX = "sha256-v1"

#: Les huit cles requises du manifest v2, plus `created`.
EXTRACTION_ROOT_FIELDS: tuple[str, ...] = (
    "schema_version",
    "project_id",
    "created",
    "rushes",
    "lots",
    "artifacts",
    "color",
    "video",
    "reconstruction",
)

#: Emplacement unique de chaque donnee ecrite par cette story. Toute donnee
#: absente de ces tables n'est pas ecrite (AC 1).
#:
#: Depuis la v2.1, le rush porte tout ce qui decrit la source: la cadence
#: source ne varie pas selon le lot extrait, mais elle varie d'un rush a
#: l'autre.
EXTRACTION_RUSH_FIELDS: tuple[str, ...] = (
    "rush_id",
    "source_name",
    "source_parent",
    # Story 2.8, AC 1 (EPIC7-ARB-41): seule exception nommee a l'invariant
    # "aucun chemin absolu au manifest" (io.manifest.CHAMPS_EXEMPTES_CHEMIN_ABSOLU).
    "source_path",
    "fps_source",
    "fps_source_exact",
    "resolution_source",
    "source_codec",
    "source_pix_fmt",
    "source_bit_depth",
    "source_sample_aspect_ratio",
    "source_color_primaries",
    "source_color_trc",
    "source_colorspace",
    "source_color_range",
    "source_start_timecode",
    # Note 5 de la relecture d'Egan du 2026-09-01: la **duree** est un critere
    # d'identite du rush, et elle ne vivait que sur le lot -- donc nulle part
    # pour un rush declare et pas encore extrait. Cardinal de frames, jamais
    # secondes de flux (voir `_build_rush_entry`).
    "source_frame_count",
    "source_frame_count_is_exact",
    "source_metadata_absent_fields",
)

EXTRACTION_LOT_FIELDS: tuple[str, ...] = (
    "lot_id",
    "rush_id",
    "state",
    "fps_target",
    "fps_target_exact",
    "expected_frame_count",
    "frames_dir",
    "source_frame_count",
    "source_frame_count_is_exact",
    "source_tail_frames",
    "rounding_policy",
    "timecode_base",
    "timecode_base_fps",
    "first_frame_timecode",
    "last_frame_timecode",
    "frame_timecodes_digest",
    "selection_warnings",
    "output_bit_depth",
    "confirmation",
    # Story 3.7: l'intention de bornage, a cote de sa consequence. Omis quand
    # absent (jamais `null`), donc un lot non borne reste indiscernable d'un
    # lot ecrit avant cette story.
    "source_in_timecode",
    "source_out_timecode",
)

#: Vide depuis la v2.1, et c'est le contrat: l'extraction n'ecrit **rien**
#: dans `video`. La section ne porte plus que la cible d'encodage
#: (`codec_target`, Epic 6) et le schema v2.1 lui interdit explicitement les
#: cles de source et de cadence cible. La constante est conservee, exportee et
#: verifiee par test: elle documente une interdiction, pas un oubli.
EXTRACTION_VIDEO_FIELDS: tuple[str, ...] = ()

EXTRACTION_ARTIFACT_FIELDS: tuple[str, ...] = ("frames_dir",)

#: Les trois champs, et seulement eux, du bloc de confirmation.
CONFIRMATION_FIELDS: tuple[str, ...] = ("mode", "unknown_color_accepted", "confirmed_at")

#: Champs par lesquels deux executions consecutives avec les memes entrees
#: peuvent legitimement differer (AC 13). Chemins pointes, `lots[]` designant
#: n'importe quel lot. `created` ne differe qu'a la premiere creation.
NON_IDEMPOTENT_FIELDS: tuple[str, ...] = (
    "created",
    "lots[].confirmation.confirmed_at",
)

#: Champs `rushes[].source_*` alimentes par le rapport de la story 3.3, dans
#: l'ordre de sa table `SOURCE_FIELD_SPECS`. Le vocabulaire de
#: `rushes[].source_metadata_absent_fields` est exactement cet ensemble: ce
#: sont les noms de cle `rushes[].*` **exacts** (`source_color_primaries`,
#: jamais `color_primaries`).
SOURCE_REPORT_RUSH_FIELDS: tuple[str, ...] = (
    "source_codec",
    "source_pix_fmt",
    "source_bit_depth",
    "source_sample_aspect_ratio",
    "source_color_primaries",
    "source_color_trc",
    "source_colorspace",
    "source_color_range",
)


# --------------------------------------------------------------------------
# Codes de constat de la verification (stables, sans prose)
# --------------------------------------------------------------------------

VERIFY_LOT_ABSENT = "LOT_ABSENT_DU_MANIFEST"
VERIFY_FRAMES_DIR_ABSENT = "DOSSIER_DE_LOT_ABSENT"
VERIFY_FRAMES_DIR_NOT_DECLARED = "DOSSIER_DE_LOT_NON_DECLARE"
VERIFY_FRAME_COUNT_MISMATCH = "CARDINAL_DE_FICHIERS_DIVERGENT"
VERIFY_MISSING_FRAMES = "FRAMES_MANQUANTES"
VERIFY_UNEXPECTED_FRAMES = "FRAMES_SURNUMERAIRES"
VERIFY_NONCONFORMING_NAMES = "NOMS_NON_CONFORMES"
VERIFY_DIGEST_MISMATCH = "EMPREINTE_DE_SELECTION_DIVERGENTE"
VERIFY_DIGEST_ABSENT = "EMPREINTE_DE_SELECTION_ABSENTE"
VERIFY_SELECTION_NOT_RECOMPUTED = "SELECTION_NON_RECALCULEE"
VERIFY_MANIFEST_INCOHERENT = "MANIFEST_INCOHERENT"
VERIFY_SOURCE_COUNT_NOT_EXACT = "CARDINAL_SOURCE_NON_EXACT"
VERIFY_COMPLETENESS_PENDING = "METADONNEES_A_RENSEIGNER_AVANT_ENCODE"

VERIFICATION_CODES: tuple[str, ...] = (
    VERIFY_LOT_ABSENT,
    VERIFY_FRAMES_DIR_ABSENT,
    VERIFY_FRAMES_DIR_NOT_DECLARED,
    VERIFY_FRAME_COUNT_MISMATCH,
    VERIFY_MISSING_FRAMES,
    VERIFY_UNEXPECTED_FRAMES,
    VERIFY_NONCONFORMING_NAMES,
    VERIFY_DIGEST_MISMATCH,
    VERIFY_DIGEST_ABSENT,
    VERIFY_SELECTION_NOT_RECOMPUTED,
    VERIFY_MANIFEST_INCOHERENT,
    VERIFY_SOURCE_COUNT_NOT_EXACT,
    VERIFY_COMPLETENESS_PENDING,
)

#: Constats **informatifs**: ils ne rendent pas le lot non conforme.
#:
#: * `SELECTION_NON_RECALCULEE`: le niveau 3 n'etait pas atteignable **faute
#:   d'un parametre dans le manifest**; il est explicitement signale, jamais
#:   silencieusement saute. A ne pas confondre avec `MANIFEST_INCOHERENT`,
#:   qui est bloquant: la ou le premier dit « je n'ai pas pu verifier », le
#:   second dit « le document se contredit ».
#: * `CARDINAL_SOURCE_NON_EXACT`: reserve opposable heritee de 3.2. Elle est
#:   remontee telle quelle et **jamais presentee comme une garantie** (question
#:   ouverte 11 de la story: le drapeau a une valeur par defaut optimiste en
#:   amont et aucun AC ne le contractualise).
#: * `METADONNEES_A_RENSEIGNER_AVANT_ENCODE`: `video.codec_target` et
#:   `color.target_colorspace`, qui n'appartiennent pas a l'extraction.
INFORMATIONAL_VERIFICATION_CODES: tuple[str, ...] = (
    VERIFY_SELECTION_NOT_RECOMPUTED,
    VERIFY_SOURCE_COUNT_NOT_EXACT,
    VERIFY_COMPLETENESS_PENDING,
)

#: Champs que `io.manifest.validate_manifest_completeness` exige et que
#: l'extraction ne peut pas renseigner: ils sont signales, pas echoues.
COMPLETENESS_PENDING_FIELDS: tuple[tuple[str, str], ...] = (
    ("video", "codec_target"),
    ("color", "target_colorspace"),
)



# --------------------------------------------------------------------------
# Hierarchie d'exceptions
# --------------------------------------------------------------------------


class ExtractionPersistenceError(ValueError):
    """Racine de toutes les erreurs de persistance d'extraction.

    Derive de ``ValueError`` pour rester capturable par un appelant
    generique; un appelant informe capture cette classe unique. Aucune de ces
    erreurs ne laisse d'ecriture partielle sur disque.
    """


class LegacyManifestError(ExtractionPersistenceError):
    """``project.json`` present mais sans ``schema_version`` v2.

    C'est le manifest legacy du POC (story 1.1, cle ``id``, metadonnees sous
    ``meta.*``). Aucune migration automatique n'est faite, et aucune ecriture
    n'a lieu.
    """


class LotStateConflictError(ExtractionPersistenceError):
    """Le lot vise ne peut pas revenir a l'etat ``extraction``.

    Un lot deja passe en ``pdf``, ``scan``, ``reconstruction`` ou ``encode``
    porte des artefacts aval (PDF imprime, scans, payloads QR deja emis) dont
    les timecodes et le cardinal ne correspondraient plus aux frames sur
    disque. Ne jamais contourner en forcant ``state`` a la main ni en
    supprimant le lot pour le recreer.
    """


class LotIdentityMismatchError(ExtractionPersistenceError):
    """Le ``lot_id`` recu ne correspond pas a celui recalcule, ou au rush.

    Plutot que d'ecrire l'un des deux identifiants, la persistance echoue.
    """


class ManifestWriteError(ExtractionPersistenceError):
    """L'ecriture atomique a echoue (validation ou I/O).

    Le ``project.json`` precedent est reste **strictement intact** et aucun
    fichier temporaire ne subsiste.
    """


# --------------------------------------------------------------------------
# Objet d'entree, API figee (construit par 3.1)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ExtractionRecord:
    """Tout ce que la persistance a besoin de savoir, et rien de plus.

    Assemble par la story 3.1, seul point ou les trois sorties de 3.1, 3.2 et
    3.3 se rencontrent. Aucune I/O n'a lieu dans la construction de cet objet,
    et aucune valeur n'y est re-derivee (pas de second probe, pas de seconde
    normalisation de nom).

    ``source_start_timecode`` n'est volontairement **pas** un champ: il vit
    dans ``selection.source_start_timecode``, ou la story 3.2 le rediffuse
    precisement pour cet usage. Idem pour ``source_frame_count_is_exact``.
    Les dupliquer ici recreerait les deux verites que la rediffusion existe
    pour eviter.

    ``fps_source`` / ``fps_target`` y figurent en revanche, parce que le
    schema v2 type ``video.fps_source`` / ``fps_target`` en ``number`` et que
    ``FrameSelection`` ne porte que des ``Fraction``; d'ou la garde de
    coherence typee / exacte de l'AC 9.

    ``output_bit_depth`` n'y figure pas non plus: c'est la constante
    ``EXTRACTION_OUTPUT_BIT_DEPTH``, jamais une valeur transportee.
    """

    # identite (3.1)
    project_id: str  # normalise, pattern ^[A-Za-z0-9_-]+$
    rush_id: str  # normalise, pattern ^[A-Za-z0-9_-]+$
    rush_source_name: str  # nom de base du fichier source, jamais un chemin
    lot_id: str  # doit egaler build_lot_id(rush_id, fps_target)
    frames_dir_relative: str  # relatif au projet, POSIX, ex. "frames/rush-001_24"

    # selection (3.2), consommee telle quelle
    selection: FrameSelection

    # source (3.1 probe + 3.3 rapport)
    fps_source: float
    fps_target: float
    source_width: int
    source_height: int
    source_fields: Mapping[str, "str | int | None"]

    # confirmation (3.3)
    confirmation_mode: str  # "interactif" | "non_interactif"
    unknown_color_accepted: bool
    confirmed_at: str  # RFC3339 UTC, = timestamp_utc du bloc de decision de 3.3

    #: Nom du dossier contenant le rush source (ARB-9,
    #: `decisions-2026-08-05.md`). **Nom seul, jamais un chemin**: il distingue
    #: deux rushs homonymes (`A-CAM/prise01.mov` et `B-CAM/prise01.mov`) sans
    #: nommer ni machine ni utilisateur, donc sans casser la portabilite que
    #: tout l'Epic 2 existe pour garantir. Optionnel: un rush pose a la racine
    #: n'en a pas d'utile.
    rush_source_parent: str | None = None

    #: Chemin absolu resolu (liens et relatif deja resolus) du fichier passe a
    #: `--video`, au moment de l'extraction (story 2.8, AC 1, `EPIC7-ARB-41`).
    #: C'est l'unique exception nommee a l'invariant de portabilite du
    #: manifest v2 (`io.manifest.CHAMPS_EXEMPTES_CHEMIN_ABSOLU`): elle sert le
    #: relink, jamais la reconstruction sur machine tierce. `None` signifie
    #: "cet appelant n'a rien a dire sur le chemin" -- le champ `source_path`
    #: existant, s'il y en a un, est alors conserve tel quel (fusion sans
    #: perte, meme regime que le reste de l'entree de rush); ce n'est **pas**
    #: le regime d'un rush relie: `extraction.run_extraction` renseigne
    #: toujours ce champ en pratique, la valeur par defaut n'existe que pour
    #: ne pas casser les appelants de test qui construisent l'enregistrement
    #: sans s'interesser au relink.
    rush_source_path: str | None = None

    #: Rang de version et lot d'origine (story 5.29, `EPIC11-ARB-89`). Les
    #: deux sont poses dans le meme mouvement, ou aucun des deux: un lot de
    #: version porte les deux, un lot de rang 1 (ou tout lot d'avant cette
    #: story) n'en porte aucun. `None` -> champ absent du manifest (AC 4),
    #: jamais une valeur par defaut ecrite (`version_rank: 1` creerait un
    #: second porteur de « ce lot n'a pas de base_lot_id »).
    version_rank: int | None = None
    base_lot_id: str | None = None

    #: Trouve en revue (Blind Hunter) : le contournement du refus de
    #: transition d'etat n'existait qu'au site AMONT (`extraction.py`,
    #: avant ffmpeg) ; ce SECOND site -- la persistance, ici -- porte SA
    #: PROPRE garde et la levait quand meme, faisant echouer toute extraction
    #: `ecrasement_conscient=True` reussie a l'amont. Transporte par
    #: `ExtractionRecord` pour que les deux sites lisent la MEME intention,
    #: sans reintroduire la duplication de redaction qu'`EPIC5-ARB-78`
    #: interdit deja (une seule phrase de refus, un seul contournement).
    ecrasement_conscient: bool = False


@dataclass(frozen=True)
class RushRecord:
    """Tout ce que l'entree ``rushes[]`` a besoin de savoir, et rien de plus.

    **Introduit par la story 11.4e (lot A)**, parce que declarer un rush sans
    l'extraire (`EPIC11-ARB-131`) ecrit cette entree alors qu'il n'existe ni
    lot, ni cadence cible, ni selection, ni confirmation -- c'est-a-dire cinq
    des champs obligatoires d'``ExtractionRecord``. Le choix etait entre
    fabriquer un enregistrement d'extraction de facade (un ``lot_id`` invente
    pour la commodite d'un appel, qui aurait pu atteindre le manifeste) et
    nommer le sous-ensemble que ``_build_rush_entry`` lit reellement. C'est le
    second, et ``rush_record_de_l_extraction`` en est l'unique projection
    depuis une extraction: le vocabulaire de la source n'a donc toujours qu'une
    seule redaction.

    ``source_start_timecode`` est un champ ici alors qu'``ExtractionRecord``
    refuse de le porter -- et ce n'est pas une contradiction: l'argument de ce
    refus est qu'il vit deja dans ``selection.source_start_timecode`` et que le
    dupliquer y creerait deux verites. Une declaration n'a pas de selection: il
    n'y a rien a dupliquer, et il faut bien le porter quelque part.
    """

    rush_id: str  # normalise, pattern ^[A-Za-z0-9_-]+$
    source_name: str  # nom de base du fichier source, jamais un chemin
    fps_source: float
    source_width: int
    source_height: int
    source_fields: Mapping[str, "str | int | None"]

    #: Timecode de depart de la source, ou ``None``. Verbatim du probe (ou de
    #: la selection qui l'a rediffuse), jamais recalcule.
    source_start_timecode: str | None = None

    #: Nom du dossier contenant le rush source (ARB-9). **Nom seul, jamais un
    #: chemin.**
    source_parent: str | None = None

    #: Chemin absolu resolu du fichier source (story 2.8, `EPIC7-ARB-41`).
    #: ``None`` signifie "cet appelant n'a rien a dire sur le chemin": le champ
    #: existant est alors conserve tel quel.
    source_path: str | None = None

    #: **Reconciliation de la liaison du 2026-09-05.** Le cardinal de frames de
    #: la source, en images et jamais en secondes de flux. Il n'etait pas dans
    #: la premiere redaction de ce ``RushRecord``, ecrite sur une branche qui
    #: avait diverge avant ``d244c307`` : depuis ce commit, la **duree** est un
    #: critere d'identite du rush (note 5 de la relecture d'Egan du 2026-09-01)
    #: et ``_build_rush_entry`` l'ecrit. Sans ce champ ici, la fonction lisait
    #: un ``selection`` que ``RushRecord`` ne porte pas -- une ``NameError`` sur
    #: **toute** extraction, pas seulement sur une declaration.
    #:
    #: ``None`` est une **absence**, pas un zero : c'est le regime d'une
    #: declaration dont le conteneur ne corrobore pas son ``nb_frames``
    #: (`extraction.cardinal_corrobore`). Le critere est alors **non
    #: verifiable** au sens de ``CriteresIdentiteRush.declares``, jamais
    #: divergent -- exactement la doctrine que la note 5 pose pour les
    #: manifestes anterieurs.
    source_frame_count: int | None = None

    #: Le cardinal ci-dessus est-il un comptage, ou une estimation ? Il **voyage
    #: avec le cardinal et jamais tout seul** : ``None`` quand le cardinal est
    #: absent, sans quoi le manifeste porterait un drapeau qui ne qualifie rien.
    source_frame_count_is_exact: bool | None = None


@dataclass(frozen=True)
class PersistedRushDeclaration:
    """Resultat de ``persist_rush_declaration``."""

    manifest_path: Path
    rush_id: str
    manifest: Mapping[str, Any]


@dataclass(frozen=True)
class LotVerification:
    """Rapport de verification d'un lot par un tiers (AC 15).

    Gelee, sans prose: ``findings`` ne porte que des codes de
    ``VERIFICATION_CODES``. La traduction utilisateur appartient a la surface
    CLI (story 3.1).

    ``selection_recomputed`` dit explicitement si le niveau 3 a pu etre
    execute; quand il ne l'a pas ete, le constat ``SELECTION_NON_RECALCULEE``
    est emis, jamais un saut silencieux.
    """

    lot_id: str
    frames_dir: str | None
    expected_frame_count: int | None
    observed_frame_count: int | None
    missing_frames: tuple[str, ...]
    unexpected_files: tuple[str, ...]
    nonconforming_files: tuple[str, ...]
    selection_recomputed: bool
    digest_matches: bool | None
    findings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        """Vrai quand aucun constat bloquant n'a ete emis."""
        return not self.blocking_findings

    @property
    def blocking_findings(self) -> tuple[str, ...]:
        return tuple(
            code for code in self.findings if code not in INFORMATIONAL_VERIFICATION_CODES
        )


@dataclass(frozen=True)
class PersistedExtraction:
    """Resultat de ``persist_extraction``."""

    manifest_path: Path
    lot_id: str
    manifest: dict[str, Any]
    verification: LotVerification


# --------------------------------------------------------------------------
# Helpers de serialisation
# --------------------------------------------------------------------------


def _utc_now_rfc3339() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _exact(fps: Any) -> str:
    """Seule serialisation de cadence du module (AC 8, 9, 16).

    Rend ``"num/den"`` avec denominateur toujours explicite (``"30/1"``,
    jamais ``"30"``). Aucun ``str(Fraction)``, aucun ``f"{fps}"``, aucun
    flottant, nulle part ailleurs dans ce fichier.
    """
    return exact_frame_rate(fps)


def _relative_posix(value: Any, label: str) -> str:
    """Chemin relatif serialise en POSIX, ou echec explicite (AC 12, Piege 5).

    ``io.manifest._check_no_absolute_paths`` attrape ``/...`` et ``C:\\...``
    mais **pas** ``frames\\rush-001_24``, un chemin relatif a separateurs
    Windows qui casse la portabilite sans declencher aucune garde. La
    conversion des antislashs a donc lieu ici, avant toute serialisation.
    """
    raw = str(value)
    if not raw:
        raise ExtractionPersistenceError(f"{label} ne peut pas etre vide")
    normalized = raw.replace("\\", "/")
    if PurePosixPath(normalized).is_absolute() or PureWindowsPath(raw).is_absolute():
        raise ExtractionPersistenceError(
            f"{label} doit etre relatif au dossier projet, pas absolu: {value!r}. "
            "Le contrat v2 interdit tout chemin absolu, pour qu'un lot reste "
            "reconstructible sur une machine tierce"
        )
    # Un chemin relatif remontant hors du projet est aussi destructeur qu'un
    # chemin absolu, et aucune garde amont ne l'attrapait: le lot vivait hors
    # du dossier projet, la verification le declarait conforme, et transferer
    # le seul dossier projet ne le transportait pas.
    if ".." in PurePosixPath(normalized).parts:
        raise ExtractionPersistenceError(
            f"{label} doit rester a l'interieur du dossier projet: {value!r} "
            "remonte au-dessus de la racine du projet. Un lot situe hors du "
            "projet ne suit pas le transfert du projet"
        )
    return PurePosixPath(normalized).as_posix()


def _base_name(value: Any, label: str) -> str:
    """Nom de base, jamais un chemin (AC 12).

    ``Path(...).name`` seul ne suffit pas: sous POSIX,
    ``Path("C:\\rushes\\a.mov").name`` rend la chaine entiere. La forme
    Windows est donc normalisee avant.
    """
    raw = str(value)
    if not raw:
        raise ExtractionPersistenceError(f"{label} ne peut pas etre vide")
    name = PurePosixPath(raw.replace("\\", "/")).name
    if not name:
        raise ExtractionPersistenceError(
            f"{label} doit etre un nom de fichier, recu {value!r}"
        )
    return name


# --------------------------------------------------------------------------
# Empreinte de selection (AC 16)
# --------------------------------------------------------------------------


def compute_frame_timecodes_digest(selection: FrameSelection) -> str:
    """Empreinte ``"sha256-v1:<64 hex>"`` de la selection.

    Forme canonique (normative, story 3.4 / Dev Notes)::

        base_fps  = codec_profiles.exact_frame_rate(selection.timecode_base_fps)
        en-tete   = f"{rounding_policy}|{timecode_base}|{base_fps}"
        lignes    = [f"{frame.output_rank:08d}:{frame.frame_timecode}" ...]
        canonique = "\\n".join([en-tete] + lignes)

    ``base_fps`` est **la meme chaine** que celle ecrite dans
    ``lots[].timecode_base_fps``: l'en-tete se lit donc directement dans le
    manifest et un tiers recalcule l'empreinte sans deviner la recette. Une
    empreinte calculee sur ``str(Fraction)`` (``"30"``) donnerait une valeur
    differente pour la meme selection.

    ``output_rank`` est **base zero** (contrat 3.2, aligne sur
    ``ARCHITECTURE_DETAILED.md`` section 3.1). La largeur fixe de huit
    chiffres evite qu'un tri lexicographique et un tri numerique divergent.

    L'empreinte change si un timecode change, si l'ordre change, si la
    politique d'arrondi change ou si la base de timecode change.
    ``hashlib`` uniquement, jamais le ``hash()`` randomise de Python.
    """
    header = "|".join(
        (
            str(selection.rounding_policy),
            str(selection.timecode_base),
            _exact(selection.timecode_base_fps),
        )
    )
    lines = [
        f"{frame.output_rank:08d}:{frame.frame_timecode}" for frame in selection.frames
    ]
    canonical = "\n".join([header] + lines)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"{FRAME_DIGEST_PREFIX}:{digest}"


# --------------------------------------------------------------------------
# Couche pure de fusion
# --------------------------------------------------------------------------


def _check_record(record: ExtractionRecord) -> None:
    """Gardes d'entree, toutes anterieures a la moindre ecriture."""
    if not isinstance(record, ExtractionRecord):
        raise ExtractionPersistenceError(
            f"record doit etre un ExtractionRecord, recu {type(record).__name__}"
        )

    selection = record.selection

    # AC 5: une seule implementation de la convention de lot_id, des deux
    # cotes. La garde n'a de valeur que parce que 3.1 appelle la meme
    # fonction, pas une copie.
    # Les bornes viennent de la selection, verbatim: c'est la meme valeur que
    # celle passee a `build_lot_id` par 3.1, sans quoi cette garde refuserait
    # toute extraction bornee (piege 1 de la story 3.7).
    # Story 5.29 (`EPIC11-ARB-89`): `version_rank` entre dans le recalcul
    # exactement comme les bornes -- omettre ce mot-cle recalculerait le
    # `lot_id` du lot d'ORIGINE et ferait echouer cette garde pour tout lot
    # versionne, alors que le lot_id recu est correct.
    recomputed = build_lot_id(
        record.rush_id,
        record.fps_target,
        source_in_timecode=selection.source_in_timecode,
        source_out_timecode=selection.source_out_timecode,
        version_rank=record.version_rank,
    )
    if record.lot_id != recomputed:
        raise LotIdentityMismatchError(
            f"lot_id incoherent: recu {record.lot_id!r}, recalcule {recomputed!r} "
            f"depuis rush_id={record.rush_id!r}, fps_target={record.fps_target!r}, "
            f"version_rank={record.version_rank!r} et "
            f"les bornes de la selection ({selection.source_in_timecode!r} -> "
            f"{selection.source_out_timecode!r}). "
            "La persistance refuse d'ecrire l'un des deux: appeler "
            "io.naming.build_lot_id des deux cotes"
        )

    # Story 5.29 (`EPIC11-ARB-89`), AC 4: `version_rank` et `base_lot_id` se
    # posent ENSEMBLE ou pas du tout -- l'un sans l'autre est un manifeste
    # qui dirait « ceci est une version » sans dire de quoi, ou l'inverse.
    if (record.version_rank is None) != (record.base_lot_id is None):
        raise ExtractionPersistenceError(
            f"version_rank={record.version_rank!r} et base_lot_id={record.base_lot_id!r} "
            "incoherents: les deux se posent ensemble, ou aucun des deux. Un lot "
            "versionne sans lot d'origine nomme, ou un lot d'origine nomme sans etre "
            "versionne, sont deux manifestes qui mentent"
        )
    if record.base_lot_id is not None:
        lot_origine = build_lot_id(
            record.rush_id,
            record.fps_target,
            source_in_timecode=selection.source_in_timecode,
            source_out_timecode=selection.source_out_timecode,
        )
        if record.base_lot_id != lot_origine:
            raise LotIdentityMismatchError(
                f"base_lot_id incoherent: recu {record.base_lot_id!r}, le lot "
                f"d'origine (rang 1) de ce rush et cette cadence est {lot_origine!r}. "
                "La persistance refuse d'ecrire un lot de version qui pretend "
                "deriver d'un autre lot que le sien"
            )

    # AC 9: interdiction d'ecrire un couple typee / exacte incoherent.
    for label, typed, exact_value in (
        ("source", record.fps_source, selection.fps_source),
        ("cible", record.fps_target, selection.fps_target),
    ):
        if Fraction(_exact(typed)) != exact_value:
            raise ExtractionPersistenceError(
                f"Cadence {label} incoherente entre l'objet d'extraction et la "
                f"selection: {typed!r} donne {_exact(typed)} alors que la selection "
                f"porte {exact_value}. Ecrire les deux produirait un manifest dont la "
                "valeur typee et la valeur exacte se contredisent"
            )

    # Piege 9: le schema impose `minimum: 1`. Echouer ici plutot qu'apres
    # l'extraction, a la validation.
    if int(selection.expected_frame_count) < 1:
        raise ExtractionPersistenceError(
            "expected_frame_count doit valoir au moins 1, recu "
            f"{selection.expected_frame_count!r}: une selection vide ne se persiste pas"
        )

    if record.confirmation_mode not in ("interactif", "non_interactif"):
        raise ExtractionPersistenceError(
            f"confirmation_mode inconnu: {record.confirmation_mode!r}. Valeurs "
            "attendues: interactif, non_interactif"
        )

    for label, value in (
        ("source_width", record.source_width),
        ("source_height", record.source_height),
    ):
        if not is_strict_int(value) or value <= 0:
            raise ExtractionPersistenceError(
                f"{label} doit etre un entier strictement positif, recu {value!r}"
            )


def rush_record_de_l_extraction(record: ExtractionRecord) -> RushRecord:
    """Projeter un ``ExtractionRecord`` sur ce que ``rushes[]`` consomme.

    **Le seul endroit ou l'on dit quels champs d'une extraction decrivent la
    SOURCE.** ``source_start_timecode`` est lu dans la selection, ou la story
    3.2 le rediffuse verbatim et ou ses consommateurs le lisent depuis toujours
    -- jamais recalcule ici.
    """
    return RushRecord(
        rush_id=record.rush_id,
        source_name=record.rush_source_name,
        fps_source=record.fps_source,
        source_width=record.source_width,
        source_height=record.source_height,
        source_fields=record.source_fields,
        source_start_timecode=record.selection.source_start_timecode,
        source_parent=record.rush_source_parent,
        source_path=record.rush_source_path,
        # Une extraction connait TOUJOURS son cardinal: la selection ne se
        # calcule pas sans lui (`resolve_source_frame_count` leve plutot que
        # de le deviner). Le regime `None` ci-dessous est donc celui de la
        # seule declaration, jamais celui d'une extraction.
        source_frame_count=int(record.selection.source_frame_count),
        source_frame_count_is_exact=bool(
            record.selection.source_frame_count_is_exact
        ),
    )


def _build_rush_entry(existing: Mapping[str, Any] | None, record: RushRecord) -> dict:
    """Entree ``rushes[]``: fusion sans perte, absence encodee positivement.

    Porte depuis la v2.1 tout ce qui decrit la **source**. Deux lots du meme
    rush a des cadences differentes reecrivent donc ici les memes valeurs,
    ce qui est sans effet: la cadence source ne depend pas de la cadence
    cible. Rien de ce qui varie avec la cadence cible n'a le droit d'entrer
    dans cette entree.

    **Prend un ``RushRecord`` et non un ``ExtractionRecord`` depuis la story
    11.4e (lot A)**: une declaration de rush (`EPIC11-ARB-131`) ecrit cette
    entree sans qu'il existe ni lot, ni cadence cible, ni selection. Lui faire
    fabriquer un ``ExtractionRecord`` de facade aurait mis dans le manifeste
    un ``lot_id`` et une selection inventes pour la seule commodite d'un appel;
    la projection, elle, ne perd rien et n'invente rien.
    """
    rush = dict(existing or {})

    rush["rush_id"] = record.rush_id
    rush["source_name"] = _base_name(record.source_name, "rushes[].source_name")
    if record.source_parent:
        rush["source_parent"] = _base_name(
            record.source_parent, "rushes[].source_parent"
        )
    # Story 2.8 (AC 1): re-extraire remplace la valeur -- le geste d'extraction
    # est une designation du fichier par l'operateur, au meme titre qu'un
    # relink manuel (`EPIC7-ARB-41`). `None` ne l'ecrase pas: c'est le regime
    # d'un appelant qui ne s'exprime pas sur le chemin (fabriques de test
    # anterieures a cette story), jamais celui d'une extraction reelle.
    if record.source_path is not None:
        rush["source_path"] = record.source_path

    rush["fps_source"] = record.fps_source
    rush["fps_source_exact"] = _exact(record.fps_source)
    # Piege 13: `resolution_source` n'est JAMAIS renomme en
    # `source_resolution`. Il est cite litteralement par
    # `io.manifest.CRITICAL_TECHNICAL_FIELDS`; coherence de nommage <
    # contrat clos. Seul son porteur change en v2.1: video -> rushes[].
    rush["resolution_source"] = {
        "width": int(record.source_width),
        "height": int(record.source_height),
    }

    absent: list[str] = []
    for field in SOURCE_REPORT_RUSH_FIELDS:
        value = record.source_fields.get(field)
        if value is None:
            # Omission stricte: jamais `null`, jamais une valeur par defaut.
            rush.pop(field, None)
            absent.append(field)
            continue
        rush[field] = value

    # `source_start_timecode` vient de la selection (3.2), pas du rapport
    # source (3.3): il n'entre donc pas dans le vocabulaire de
    # `source_metadata_absent_fields`, dont la story fige la liste sur les
    # champs du rapport. Son absence reste lisible par omission du champ.
    start_timecode = record.source_start_timecode
    if start_timecode is None:
        rush.pop("source_start_timecode", None)
    else:
        rush["source_start_timecode"] = str(start_timecode)

    # Note 5 de la relecture d'Egan du 2026-09-01: « les criteres : duree,
    # base, timecode initial -- a ajouter a la comparaison ET a stocker ».
    #
    # La **duree** est la seule des trois qui manquait vraiment. Elle ne
    # vivait que sur `lots[].source_frame_count`, et un rush declare et pas
    # encore extrait n'a **aucun lot**: le critere etait donc inatteignable au
    # moment exact ou la comparaison doit se faire.
    #
    # Elle se stocke en **cardinal de frames**, jamais en secondes de flux:
    # c'est le vocabulaire de `lots[].source_frame_count` et de
    # `relink.CRITERES_IDENTITE_RELINK`, et c'est le cardinal qui commande une
    # extraction -- deux flux dont les durees flottantes different a la
    # troisieme decimale portent le meme cardinal et produisent le meme lot.
    #
    # Le drapeau d'exactitude voyage avec le cardinal et jamais tout seul:
    # `resolve_source_frame_count` peut ne rendre qu'une estimation, et la
    # stocker sans le dire ferait passer un lot potentiellement tronque pour
    # un lot mesure.
    #
    # Les **deux autres** criteres etaient deja la, et c'est mesure:
    # `source_start_timecode` ci-dessus porte le timecode initial, et la
    # **base de timecode** est `fps_source_exact` -- `frame_selection` pose
    # `timecode_base = "source"` et `timecode_base_fps = fps_source_exact`,
    # donc la base **est** la cadence source. Aucun champ de plus n'est ecrit
    # ici: la meme valeur sous deux noms dans un meme manifeste ouvrirait une
    # divergence que rien ne mesurerait. L'egalite, elle, est mesuree
    # (`tests/unit/test_identite_rush.py`, section C.7).
    #
    # **Omission stricte quand le cardinal est absent** (liaison du
    # 2026-09-05, story 11.4e lot A). Une declaration de rush n'a pas de
    # selection et ne paie pas le `-count_frames` de l'extraction (AC 1.5 :
    # `ffprobe` appele exactement une fois) : quand le conteneur ne corrobore
    # pas son `nb_frames`, elle n'a **rien a dire** sur la duree. Ecrire `0`
    # affirmerait un flux vide, et ecrire une estimation la ferait DIVERGER du
    # comptage exact qu'une extraction ulterieure poserait -- c'est-a-dire
    # fabriquer un faux conflit d'identite sur le critere que la note 5 vient
    # d'ajouter. L'omission, elle, rend le critere **non verifiable**, ce que
    # `CriteresIdentiteRush.declares` sait deja lire.
    #
    # Le drapeau part **avec** le cardinal : un `source_frame_count_is_exact`
    # seul ne qualifierait rien.
    cardinal = record.source_frame_count
    if cardinal is None:
        rush.pop("source_frame_count", None)
        rush.pop("source_frame_count_is_exact", None)
    else:
        rush["source_frame_count"] = int(cardinal)
        rush["source_frame_count_is_exact"] = bool(record.source_frame_count_is_exact)

    rush["source_metadata_absent_fields"] = sorted(absent)
    return rush


def _build_lot(existing: Mapping[str, Any] | None, record: ExtractionRecord) -> dict:
    """Entree ``lots[]`` du lot extrait, mise a jour en place."""
    selection = record.selection
    lot = dict(existing or {})

    lot["lot_id"] = record.lot_id
    lot["rush_id"] = record.rush_id
    lot["state"] = EXTRACTION_LOT_STATE
    # v2.1: la cadence cible appartient au lot. C'est elle, et elle seule, qui
    # distingue deux lots d'un meme rush; la porter au niveau projet rendait le
    # premier lot invalide des qu'un second etait ecrit.
    lot["fps_target"] = record.fps_target
    lot["fps_target_exact"] = _exact(record.fps_target)
    # AC 7: valeur de la selection, jamais un comptage de fichiers sur disque.
    lot["expected_frame_count"] = int(selection.expected_frame_count)
    lot["frames_dir"] = _relative_posix(record.frames_dir_relative, "lots[].frames_dir")
    lot["source_frame_count"] = int(selection.source_frame_count)
    lot["source_frame_count_is_exact"] = bool(selection.source_frame_count_is_exact)
    lot["source_tail_frames"] = int(selection.source_tail_frames)
    lot["rounding_policy"] = str(selection.rounding_policy)
    # AC 8: base et cadence de base lues dans la selection, jamais deduites
    # d'un nom de dossier, d'un nom de fichier ni de fps_target.
    lot["timecode_base"] = str(selection.timecode_base)
    lot["timecode_base_fps"] = _exact(selection.timecode_base_fps)
    lot["first_frame_timecode"] = selection.frames[0].frame_timecode
    lot["last_frame_timecode"] = selection.frames[-1].frame_timecode
    lot["frame_timecodes_digest"] = compute_frame_timecodes_digest(selection)
    lot["selection_warnings"] = list(selection.warnings)
    lot["output_bit_depth"] = EXTRACTION_OUTPUT_BIT_DEPTH
    # Story 3.7, AC 8: les bornes viennent de la selection, verbatim -- jamais
    # recalculees depuis les timecodes de premiere et derniere frame, qui ne
    # disent que ce qui a ete retenu, pas ce qui a ete demande. Meme mecanisme
    # d'omission stricte que `source_start_timecode` sur `rushes[]`, applique
    # ici a `lots[]`: la borne est une propriete du lot, pas de la source.
    for field, value in (
        ("source_in_timecode", selection.source_in_timecode),
        ("source_out_timecode", selection.source_out_timecode),
    ):
        if value is None:
            lot.pop(field, None)
        else:
            lot[field] = str(value)
    lot["confirmation"] = {
        "mode": record.confirmation_mode,
        "unknown_color_accepted": bool(record.unknown_color_accepted),
        "confirmed_at": record.confirmed_at,
    }
    # **Un ecrasement conscient PURGE l'aval du lot** (revue Opus finale).
    # Sans cela, `_build_lot` partant de `dict(existing)`, un lot ramene de
    # `encode` a `extraction` gardait `output_frames_dir`,
    # `reconstructed_frame_count`, `synthetic_frames` et `encoded_masters` du
    # cycle PRECEDENT. Mesure : `encode` lit `lots[].output_frames_dir` et
    # aurait encode les images rescannees de l'ancien cycle comme master de la
    # nouvelle extraction, sans rien detecter -- les cardinaux coincident par
    # construction (meme source, meme cadence). L'avertissement AC 7 dit a
    # l'operateur que les artefacts aval « ne correspondront plus » : le
    # manifeste doit cesser de les declarer, sinon il ment juste apres que
    # l'outil a promis le contraire.
    if record.ecrasement_conscient:
        for champ_aval in (
            "output_frames_dir",
            "reconstructed_frame_count",
            "synthetic_frame_count",
            "synthetic_frames",
            "encoded_masters",
            "color_calibration_status",
        ):
            lot.pop(champ_aval, None)
    # Story 5.29 (`EPIC11-ARB-89`), AC 4: additifs, poses ou omis ENSEMBLE --
    # meme regime d'omission stricte que les bornes ci-dessus. Un lot de rang
    # 1 (ou tout lot ecrit avant cette story) ne porte ni l'un ni l'autre.
    for field, value in (
        ("version_rank", record.version_rank),
        ("base_lot_id", record.base_lot_id),
    ):
        if value is None:
            lot.pop(field, None)
        else:
            lot[field] = value
    return lot


def message_avertissement_ecrasement(lot_id: Any, current_state: str | None) -> str:
    """Le texte de l'avertissement qui precede un ecrasement conscient (AC 7).

    **Rendu, jamais imprime.** C'est le contrat que la fiche annonce aux trois
    surfaces : la CLI le journalise, la TUI l'affichera dans un panneau, la GUI
    dans une boite de dialogue -- chacune a sa facon, mais toutes le MEME
    texte. Le laisser au fond d'un `logger.warning` le rendait inconsommable
    par un ecran, et le reformuler trois fois serait exactement la divergence
    qu'`EPIC5-ARB-78` interdit (« deux emplacements pour le meme fait, ce sont
    deux verites »).

    Il **nomme l'etat courant** : la premiere redaction ne citait que le
    `lot_id`, si bien que l'operateur lisait « ce lot va etre ecrase » sans
    savoir s'il ecrasait un lot deja imprime ou un lot deja scanne -- soit
    precisement l'information qui rend le consentement conscient.
    """
    return (
        f"Ecrasement conscient du lot {lot_id!r}, actuellement en etat "
        f"{current_state!r}. Les artefacts aval deja produits pour ce lot (PDF "
        "imprime, scans, payloads QR emis) ne correspondront plus a ce qui sera "
        "ecrit: leurs timecodes et leur cardinal renverront a des frames "
        "remplacees. Cette extraction a ete demandee avec un consentement "
        "explicite; aucune autre confirmation ne sera demandee."
    )


def validate_extraction_state_transition(
    lot_id: Any, current_state: str | None
) -> None:
    """Juger si ``lot_id``, actuellement en ``current_state``, peut repasser en
    ``extraction`` -- et lever ``LotStateConflictError`` sinon.

    **Une seule redaction, deux sites d'appel** (story 11.4c, lot V1). Le refus
    est desormais prononce a **deux** endroits: ici, depuis
    ``build_extraction_manifest`` (etape 6 de ``run_extraction``, la
    persistance), et depuis ``extraction.run_extraction`` elle-meme, **avant**
    l'appel a ffmpeg (`EPIC11-ARB-83`). Recopier le message du second cote
    aurait pose « deux emplacements pour le meme fait, [donc] deux verites »
    (`EPIC5-ARB-78`): la phrase, l'exception et la machine a etats vivent donc
    ici, et l'amont ne fait que les appeler.

    **Aucune machine a etats n'est reimplementee**: le jugement est delegue tel
    quel a ``io.manifest.validate_lot_state_transition``, seul juge, et le
    motif qu'elle rend est recopie entre parentheses dans le message.

    ``current_state`` a ``None`` -- lot inconnu du manifeste, ou lot preexistant
    qui ne porte pas ``state`` -- est un cas **accepte**, pas un conflit:
    ``validate_lot_state_transition`` le documente explicitement.

    **La story 5.29 (`EPIC11-ARB-89`) y ajoute la TROISIEME issue**, comme
    l'annoncait deja le commentaire de la story 11.4c (AC 2.1, « c'est V3 qui
    en ajoutera une troisieme ») : les deux premieres restent **mot pour
    mot**, la nouvelle nomme le mecanisme de versionnage et d'ecrasement
    conscient de cette story --
    ``run_extraction(nouvelle_version=True)`` ou
    ``run_extraction(ecrasement_conscient=True, consent_granted=True)``.
    C'est `extraction.run_extraction` qui, cote amont, choisit d'honorer
    cette troisieme issue en contournant cet appel plutot que de le laisser
    lever -- cette fonction-ci ne connait que le refus et ses issues, jamais
    le contournement lui-meme.
    """
    try:
        validate_lot_state_transition(current_state, EXTRACTION_LOT_STATE)
    except ValidationError as error:
        raise LotStateConflictError(
            f"Le lot {lot_id!r} est en etat {current_state!r} et ne peut pas "
            f"repasser en {EXTRACTION_LOT_STATE!r} ({error.message}). Une re-extraction "
            "invaliderait les artefacts aval deja produits (PDF imprime, scans, "
            "payloads QR emis), dont les timecodes et le cardinal ne correspondraient "
            "plus aux frames sur disque. Issues: extraire vers une autre cadence cible "
            "(donc un autre lot_id), ou nettoyer ce lot a la main. Ou encore, depuis la "
            "story 5.29: creer une nouvelle version de ce lot "
            "(--nouvelle-version / run_extraction(nouvelle_version=True)) -- ce lot-ci "
            "reste intact -- ou l'ecraser SCIEMMENT, apres avertissement explicite "
            "(--ecrasement-conscient / "
            "run_extraction(ecrasement_conscient=True, consent_granted=True)). Aucune "
            f"ecriture n'a eu lieu. Etats connus, dans l'ordre: {', '.join(LOT_STATES)}"
        ) from error


def _manifeste_de_base(
    existing: Mapping[str, Any] | None, project_id: str
) -> dict[str, Any]:
    """Le manifeste v2.1 sur lequel une fusion va s'appliquer, ou un refus.

    **Extrait de ``build_extraction_manifest`` par la story 11.4e (lot A)**,
    sans changement de comportement: la declaration d'un rush fusionne dans le
    meme manifeste, avec les memes refus de version de schema et la meme garde
    d'identite de projet. Deux redactions de ces trois gardes auraient diverge
    au premier ajustement de contrat.

    * ``existing is None`` -> creation d'un manifest v2 complet;
    * sans ``schema_version`` -> ``LegacyManifestError``, aucune migration;
    * v2.0 -> migration **en memoire** vers la v2.1;
    * ``project_id`` different -> ``ExtractionPersistenceError``.
    """
    if existing is None:
        return {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "project_id": project_id,
            "created": _utc_now_rfc3339(),
            "rushes": [],
            "lots": [],
            "artifacts": {},
            "color": {},
            "video": {},
            "reconstruction": {},
        }

    if "schema_version" not in existing:
        raise LegacyManifestError(
            "Le project.json present ne porte pas de 'schema_version': c'est un "
            "manifest legacy (POC story 1.1). Aucune migration automatique n'est "
            "faite et aucune ecriture n'a eu lieu. Utiliser un dossier projet "
            "distinct, ou migrer le manifest manuellement vers le contrat v2"
        )
    declared_version = existing["schema_version"]
    if declared_version not in (MANIFEST_SCHEMA_VERSION,) + MIGRATABLE_SCHEMA_VERSIONS:
        raise LegacyManifestError(
            f"schema_version {declared_version!r} non supportee "
            f"(attendu {MANIFEST_SCHEMA_VERSION!r}, ou "
            f"{', '.join(MIGRATABLE_SCHEMA_VERSIONS)} migrable). Aucune migration "
            "automatique n'est faite et aucune ecriture n'a eu lieu"
        )
    manifest = json.loads(json.dumps(existing))
    if declared_version != MANIFEST_SCHEMA_VERSION:
        manifest = _migrate_v2_0(manifest)

    existing_project_id = manifest.get("project_id")
    if existing_project_id and existing_project_id != project_id:
        raise ExtractionPersistenceError(
            f"project_id incoherent: le manifest declare {existing_project_id!r} et "
            f"l'extraction {project_id!r}. La persistance refuse de reecrire "
            "l'identite d'un projet existant"
        )
    manifest["project_id"] = project_id
    manifest.setdefault("created", _utc_now_rfc3339())
    return manifest


def build_extraction_manifest(
    existing: Mapping[str, Any] | None, record: ExtractionRecord
) -> dict[str, Any]:
    """Fusionner ``record`` dans ``existing`` et rendre le manifest v2 complet.

    **Couche pure**: aucune I/O, aucun acces disque, aucune horloge sinon
    ``created`` a la premiere creation. C'est ``persist_extraction`` qui lit
    et ecrit.

    * ``existing is None`` -> creation d'un manifest v2 complet (les huit cles
      requises, ``color`` et ``reconstruction`` a ``{}``).
    * ``existing`` sans ``schema_version`` -> ``LegacyManifestError``, aucune
      tentative de migration (manifest legacy POC, story 1.1).
    * ``existing`` en v2.0 -> **migration en memoire** vers la v2.1 avant
      fusion (``_migrate_v2_0``), jamais un refus: un manifest v2.0 ne porte
      par construction qu'une cadence source et une cadence cible pour tout le
      projet, donc leur replacement sur chaque rush et sur chaque lot est
      deterministe et sans perte.
    * ``existing`` v2.1 -> fusion **sans perte**: aucune section non possedee
      par cette story n'est reecrite, aucun autre lot ni rush n'est modifie,
      ``created`` est preserve. En particulier ``color`` est recopiee telle
      quelle, y compris ``color.source_bit_depth`` (AC 3).

    Mise a jour **en place** par ``rush_id`` et par ``lot_id``, jamais
    d'``append`` aveugle: deux executions ne produisent pas de doublon. Deux
    lots du meme rush a des cadences differentes sont en revanche deux entrees
    distinctes de ``lots[]``, qui coexistent sans s'invalider.
    """
    _check_record(record)
    manifest = _manifeste_de_base(existing, record.project_id)

    # --- rushes: mise a jour en place par rush_id ---------------------------
    rushes = list(manifest.get("rushes") or [])
    for index, rush in enumerate(rushes):
        if rush.get("rush_id") == record.rush_id:
            rushes[index] = _build_rush_entry(rush, rush_record_de_l_extraction(record))
            break
    else:
        rushes.append(_build_rush_entry(None, rush_record_de_l_extraction(record)))
    manifest["rushes"] = rushes

    # --- lots: transition d'etat puis mise a jour en place par lot_id -------
    lots = list(manifest.get("lots") or [])
    target_index = None
    for index, lot in enumerate(lots):
        if lot.get("lot_id") == record.lot_id:
            target_index = index
            break

    existing_lot = lots[target_index] if target_index is not None else None
    if existing_lot is not None:
        declared_rush = existing_lot.get("rush_id")
        if declared_rush and declared_rush != record.rush_id:
            raise LotIdentityMismatchError(
                f"Le lot {record.lot_id!r} est deja rattache au rush "
                f"{declared_rush!r} et ne peut pas etre reattribue a "
                f"{record.rush_id!r}"
            )
    # `state` n'est pas dans le `required` du schema: un lot preexistant qui
    # ne le porte pas donne `current = None`, cas explicitement accepte par
    # `validate_lot_state_transition`. `extraction -> extraction` est accepte
    # aussi (la comparaison est un `<` d'index), et c'est la condition meme de
    # l'idempotence de l'AC 13.
    current_state = existing_lot.get("state") if existing_lot else None
    # Story 5.29 (`EPIC11-ARB-89`), AC 6: le contournement conscient vaut ICI
    # aussi -- meme intention que le site amont d'`extraction.run_extraction`,
    # jamais une redaction seconde du refus (`EPIC5-ARB-78`).
    try:
        validate_extraction_state_transition(record.lot_id, current_state)
    except LotStateConflictError:
        if not record.ecrasement_conscient:
            raise

    new_lot = _build_lot(existing_lot, record)
    if target_index is None:
        lots.append(new_lot)
    else:
        lots[target_index] = new_lot
    manifest["lots"] = lots

    # --- artifacts / video --------------------------------------------------
    artifacts = dict(manifest.get("artifacts") or {})
    # Ancrage d'arborescence depuis la constante, jamais un litteral.
    artifacts["frames_dir"] = PurePosixPath(FRAMES_DIRNAME).as_posix()
    manifest["artifacts"] = artifacts

    # `video`, `color` et `reconstruction` sont recopiees telles quelles: cette
    # story n'ecrit, ne lit et n'efface aucune de leurs cles (AC 3). Depuis la
    # v2.1, `video` est dans ce cas: elle ne porte plus que la cible d'encodage.
    manifest.setdefault("video", {})
    manifest.setdefault("color", {})
    manifest.setdefault("reconstruction", {})

    return manifest


# --------------------------------------------------------------------------
# Migration v2.0 -> v2.1
# --------------------------------------------------------------------------


def _migrate_v2_0(manifest: dict[str, Any]) -> dict[str, Any]:
    """Replacer les champs de la section ``video`` unique sur leurs porteurs.

    Deterministe et sans perte: un manifest v2.0 ne declare **qu'une** cadence
    source, **qu'une** cadence cible et **qu'une** description de source pour
    tout le projet. Elles se repliquent donc sur chaque rush et sur chaque lot
    sans qu'aucune valeur ne soit devinee ni arbitree. Les cles de ``video``
    qui n'ont pas de porteur (``codec_target`` et toute cle inconnue) restent
    ou elles sont.

    La migration a lieu **en memoire seulement**: le ``project.json`` sur
    disque n'est reecrit qu'a l'ecriture atomique, et seulement si toute la
    persistance reussit.
    """
    video = dict(manifest.get("video") or {})

    fps_source = video.pop("fps_source", None)
    fps_source_exact = video.pop("fps_source_exact", None)
    fps_target = video.pop("fps_target", None)
    fps_target_exact = video.pop("fps_target_exact", None)
    resolution_source = video.pop("resolution_source", None)
    source_values = {
        field: video.pop(field)
        for field in SOURCE_REPORT_RUSH_FIELDS
        + ("source_start_timecode", "source_metadata_absent_fields")
        if field in video
    }

    # ARB-8 (`decisions-2026-08-05.md`): la replication n'a lieu que lorsqu'elle
    # est **certaine**, c'est-a-dire quand le document ne decrit qu'un seul rush
    # et qu'un seul lot. Au-dela, la v2.0 avait deja perdu l'information: y
    # recopier la valeur unique du projet fabriquait une description de source
    # pour un rush jamais sonde, et attribuait a chaque lot une cadence qui
    # contredit son propre identifiant -- au point que la verification declarait
    # corrompu un lot dont les fichiers etaient intacts.
    rush_entries = list(manifest.get("rushes") or [])
    lot_entries = list(manifest.get("lots") or [])
    replication_certaine = len(rush_entries) <= 1 and len(lot_entries) <= 1

    rushes = []
    for rush in rush_entries:
        migrated = dict(rush)
        if not replication_certaine:
            rushes.append(migrated)
            continue
        if fps_source is not None:
            migrated.setdefault("fps_source", fps_source)
        if fps_source_exact is not None:
            migrated.setdefault("fps_source_exact", fps_source_exact)
        if resolution_source is not None:
            migrated.setdefault("resolution_source", resolution_source)
        for field, value in source_values.items():
            migrated.setdefault(field, value)
        rushes.append(migrated)

    lots = []
    for lot in lot_entries:
        migrated_lot = dict(lot)
        if not replication_certaine:
            lots.append(migrated_lot)
            continue
        if fps_target is not None:
            migrated_lot.setdefault("fps_target", fps_target)
        if fps_target_exact is not None:
            migrated_lot.setdefault("fps_target_exact", fps_target_exact)
        lots.append(migrated_lot)

    migrated_manifest = dict(manifest)
    migrated_manifest["schema_version"] = MANIFEST_SCHEMA_VERSION
    migrated_manifest["rushes"] = rushes
    migrated_manifest["lots"] = lots
    migrated_manifest["video"] = video
    return migrated_manifest


# --------------------------------------------------------------------------
# Verification par un tiers (AC 15)
# --------------------------------------------------------------------------


def resolve_version_rank(
    manifest: Mapping[str, Any],
    rush_id: str,
    fps_target: float | int,
    *,
    source_in_timecode: str | None = None,
    source_out_timecode: str | None = None,
    fps_short_name: str | None = None,
) -> int:
    """Rendre le premier rang de version LIBRE pour ce lot de base (story 5.29, AC 2).

    Le rang se lit au MANIFESTE, jamais au nom: chaque entree de ``lots[]``
    dont ``base_lot_id`` egale l'identifiant du lot d'ORIGINE (rang 1, sans
    fragment de version -- ``build_lot_id`` avec ``version_rank=None``) porte
    son propre ``version_rank``.

    **UN RANG SE CONSOMME, il ne se reutilise pas** (`EPIC11-ARB-92`, Egan
    2026-08-31). Cette fonction rendait le TROU: creer la version 4 puis
    supprimer la version 2 rendait 2. Egan l'a corrige, et etendu aux trois
    objets versionnables du depot: le trou reste un trou, le suivant est le 5.
    Le calcul vit dans `io.version_ranks`, ecrit une fois pour les trois --
    trois copies seraient trois verites (`EPIC5-ARB-78`).

    Aucune I/O: pure lecture de ``manifest["lots"]``, la meme collection que
    ``_find_lot`` parcourt.
    """
    base_id = build_lot_id(
        rush_id,
        fps_target,
        source_in_timecode=source_in_timecode,
        source_out_timecode=source_out_timecode,
        fps_short_name=fps_short_name,
    )
    rangs_pris = rangs_employes_de_la_famille(manifest, base_id)
    lignes = manifest.get(LOT_WATERMARKS_FIELD)
    declaree = lignes.get(base_id) if isinstance(lignes, Mapping) else None
    rang = version_ranks.prochain_rang(
        version_ranks.ligne_d_eau(declaree, rangs_pris))
    # Borne haute avec une issue NOMMEE (revue Opus finale). Sans elle, un lot
    # dont les rangs 2..99 sont tous pris rendait 100, et l'erreur venait plus
    # tard de `format_version_suffix` sous la forme « rang hors bornes », un
    # message qui parle du rang 1 dans une situation qui n'a rien a voir et
    # n'offre aucune sortie -- un blocage sec, ce qu'`EPIC11-ARB-89` interdit.
    if rang > VERSION_RANK_MAX:
        raise ExtractionPersistenceError(version_ranks.refus_de_rangs_epuises(
            "lot", base_id,
            # Le DRAPEAU est nomme, pas seulement la commande (trouve en
            # revue, couche 3) : sans lui `project remove --lot` garde le rang
            # consomme, donc le geste conseille n'aurait rien debloque.
            "Deux issues: supprimer la DERNIERE version en liberant son rang "
            "(`mmu project remove --lot <id> --liberer-le-rang --confirmer`, "
            "qui rend d'un coup toute la queue devenue libre), ou ecraser "
            "sciemment une version existante (--ecrasement-conscient avec "
            "--yes).",
        ))
    return rang


#: Ligne d'eau des versions de lot, de niveau PROJET (`EPIC11-ARB-92`).
#: Contrairement aux planches et aux masters, les versions d'un lot sont des
#: entrees SOEURS de `lots[]` : ranger leur ligne d'eau dans l'entree d'origine
#: la ferait disparaitre avec elle, alors que ses versions peuvent survivre.
LOT_WATERMARKS_FIELD = "lot_version_watermarks"


def rangs_employes_de_la_famille(
    manifest: Mapping[str, Any], base_lot_id: str
) -> set[int]:
    """Les rangs de version encore DECLARES pour cette famille de lot.

    Le rang se lit a `lots[].version_rank`, jamais au nom (`EPIC5-ARB-3`).
    L'origine (rang 1) n'en porte pas : son absence le dit.
    """
    rangs: set[int] = set()
    for lot in manifest.get("lots") or []:
        if not isinstance(lot, Mapping):
            continue
        if lot.get("lot_id") == base_lot_id:
            rangs.add(version_ranks.RANG_ORIGINE)
            continue
        if lot.get("base_lot_id") != base_lot_id:
            continue
        rang = lot.get("version_rank")
        if isinstance(rang, int) and not isinstance(rang, bool):
            rangs.add(rang)
    return rangs


def _find_lot(manifest: Mapping[str, Any], lot_id: str) -> dict | None:
    for lot in manifest.get("lots") or []:
        if isinstance(lot, Mapping) and lot.get("lot_id") == lot_id:
            return dict(lot)
    return None


def _find_rush(manifest: Mapping[str, Any], rush_id: Any) -> dict:
    """Entree ``rushes[]`` du rush du lot, ou ``{}`` si elle n'existe pas."""
    for rush in manifest.get("rushes") or []:
        if isinstance(rush, Mapping) and rush.get("rush_id") == rush_id:
            return dict(rush)
    return {}


def _lot_fps_target(manifest: Mapping[str, Any], lot: Mapping[str, Any]) -> Any:
    """Cadence cible **de ce lot**, avec repli v2.0 sur la section projet.

    C'est le point exact ou la v2.0 se trompait: elle n'avait qu'une cadence
    cible pour tout le projet, donc verifier un lot revenait a le recalculer
    avec la cadence du dernier lot ecrit. Le repli n'est conserve que pour
    relire un manifest v2.0 non migre, et il est **conditionne au
    `schema_version` declare**: applique a un manifest v2.1, il rouvrirait en
    lecture le defaut que la v2.1 ferme en ecriture.
    """
    fps_target = lot.get("fps_target")
    if fps_target is not None:
        return fps_target
    if manifest.get("schema_version") not in MIGRATABLE_SCHEMA_VERSIONS:
        return None
    return (manifest.get("video") or {}).get("fps_target")


def _recompute_selection(
    manifest: Mapping[str, Any], lot: Mapping[str, Any]
) -> tuple[FrameSelection | None, str | None]:
    """Niveau 3: recalcul de la selection depuis le seul manifest.

    Chaque lot est recalcule avec **sa** cadence cible et avec la cadence
    source de **son** rush. Rend ``(None, code)`` -- jamais une approximation
    -- des qu'un parametre de recalcul manque ou que le recalcul echoue.

    Le code rendu distingue deux situations que le manifest ne permet pas de
    confondre, et que la premiere version de cette fonction confondait en
    avalant toute exception:

    * ``SELECTION_NON_RECALCULEE``: un parametre du recalcul est **absent** du
      manifest. Constat informatif, il ne rend pas le lot non conforme.
    * ``MANIFEST_INCOHERENT``: les parametres sont tous presents mais le
      noyau de selection les **refuse**. Un manifest qui se contredit
      lui-meme n'est pas un manifest qu'on n'a pas su relire: c'est un
      constat **bloquant**. Sans cette distinction, editer
      ``rushes[].fps_source`` de 30 a 2 suffisait a desactiver d'un coup la
      comparaison d'empreinte **et** le controle des noms de fichiers, et le
      lot ressortait ``ok=True``.
    """
    is_v2_0 = manifest.get("schema_version") in MIGRATABLE_SCHEMA_VERSIONS
    # Repli v2.0 sur la section projet: reserve a un manifest qui se declare
    # en v2.0. L'appliquer a un manifest v2.1 rendrait le defaut d'origine --
    # une cadence unique pour tout le projet -- de nouveau atteignable en
    # lecture, sur le chemin meme que la v2.1 existe pour fermer.
    video = manifest.get("video") or {} if is_v2_0 else {}
    rush = _find_rush(manifest, lot.get("rush_id"))
    fps_source = (
        rush.get("fps_source_exact")
        or rush.get("fps_source")
        or video.get("fps_source_exact")
        or video.get("fps_source")
    )
    fps_target_typed = _lot_fps_target(manifest, lot)
    fps_target = lot.get("fps_target_exact") or fps_target_typed
    if fps_target is None:
        fps_target = video.get("fps_target_exact")
    source_frame_count = lot.get("source_frame_count")
    if fps_source is None or fps_target is None or source_frame_count is None:
        return None, VERIFY_SELECTION_NOT_RECOMPUTED

    start_timecode = rush.get("source_start_timecode")
    if start_timecode is None:
        start_timecode = video.get("source_start_timecode")

    # Story 3.7, AC 9: les bornes sont une propriete du **lot**, relues comme
    # `source_start_timecode` l'est sur le rush. Les omettre ici reconstruirait
    # la selection du rush entier et ferait ressortir tout lot borne comme non
    # conforme chez le tiers -- c'est-a-dire exactement l'inverse de ce que la
    # persistance existe pour garantir.
    in_timecode = lot.get("source_in_timecode")
    out_timecode = lot.get("source_out_timecode")

    try:
        selection = select_source_frames(
            fps_source=fps_source,
            fps_target=fps_target,
            source_frame_count=int(source_frame_count),
            source_start_timecode=start_timecode,
            source_in_timecode=in_timecode,
            source_out_timecode=out_timecode,
            source_frame_count_is_exact=bool(
                lot.get("source_frame_count_is_exact", True)
            ),
        )
    except Exception:
        # Tous les parametres etaient la et le noyau les a refuses: le
        # document se contredit. Le constat est remonte, jamais l'exception.
        return None, VERIFY_MANIFEST_INCOHERENT
    return selection, None


def recompute_lot_selection(
    manifest: Mapping[str, Any], lot: Mapping[str, Any]
) -> tuple[FrameSelection | None, str | None]:
    """Selection recalculee d'un lot: **implementation unique** du depot.

    Expose le recalcul que `verify_extracted_lot` applique en niveau 3 --
    repli v2.0 conditionne au `schema_version` inclus -- pour que les autres
    consommateurs (makepdf via `pdf_composition`, revue 4.1 du 2026-08-06)
    recalculent exactement la meme selection au lieu d'en reecrire une copie
    divergente (`decisions-2026-08-02.md`, decision 2).

    Rend ``(selection, None)`` ou ``(None, code)`` avec les memes codes que la
    verification: `VERIFY_SELECTION_NOT_RECOMPUTED` (parametre absent) ou
    `VERIFY_MANIFEST_INCOHERENT` (parametres presents mais refuses).
    """
    return _recompute_selection(manifest, lot)


def verify_extracted_lot(
    project_dir: str | Path, manifest: Mapping[str, Any], lot_id: str
) -> LotVerification:
    """Verifier un lot extrait, sans le rush ni le poste d'origine.

    Ne lance **aucun** sous-processus, ne lit **aucun** pixel et ne touche
    **jamais** au manifest: elle constate.

    Le controle des noms **appelle** ``io.naming.build_extracted_frame_filename``
    et ne reimplemente jamais le motif ``<rush>_<fps-court>_<timecode>.tiff``
    en local: une seconde ecriture de la convention divergerait au premier
    ajustement de la story 3.1 (``decisions-2026-08-02.md``, decision 2).

    Trois niveaux, cumulatifs (voir la docstring du module): niveau 1 sur le
    manifest seul, niveau 2 sur le dossier de lot, niveau 3 par recalcul de la
    selection quand la chaine outil est disponible.

    Chaque lot est verifie **independamment**: sa cadence cible est lue dans
    ``lots[].fps_target`` et la cadence de sa source dans
    ``rushes[].fps_source``, jamais dans une section projet partagee. Trois
    lots du meme rush a 3, 5 et 12,5 im/s se verifient donc chacun comme
    conforme, sans qu'aucun n'invalide les autres.
    """
    project_dir = Path(project_dir)
    findings: list[str] = []

    lot = _find_lot(manifest, lot_id)
    if lot is None:
        return LotVerification(
            lot_id=lot_id,
            frames_dir=None,
            expected_frame_count=None,
            observed_frame_count=None,
            missing_frames=(),
            unexpected_files=(),
            nonconforming_files=(),
            selection_recomputed=False,
            digest_matches=None,
            findings=(VERIFY_LOT_ABSENT,),
        )

    # --- niveau 1: manifest seul -------------------------------------------
    if lot.get("source_frame_count_is_exact") is False:
        findings.append(VERIFY_SOURCE_COUNT_NOT_EXACT)
    for section, field in COMPLETENESS_PENDING_FIELDS:
        if field not in (manifest.get(section) or {}):
            findings.append(VERIFY_COMPLETENESS_PENDING)
            break

    expected_frame_count = lot.get("expected_frame_count")
    persisted_digest = lot.get("frame_timecodes_digest")
    if not persisted_digest:
        findings.append(VERIFY_DIGEST_ABSENT)

    # --- niveau 3 (avant le 2: il fournit les noms attendus) ---------------
    selection, selection_finding = _recompute_selection(manifest, lot)
    digest_matches: bool | None = None
    if selection_finding is not None:
        findings.append(selection_finding)
    if selection is not None:
        if persisted_digest:
            digest_matches = compute_frame_timecodes_digest(selection) == persisted_digest
            if not digest_matches:
                findings.append(VERIFY_DIGEST_MISMATCH)

    # --- niveau 2: dossier de lot ------------------------------------------
    frames_dir_relative = lot.get("frames_dir")
    if not frames_dir_relative:
        findings.append(VERIFY_FRAMES_DIR_NOT_DECLARED)
        return LotVerification(
            lot_id=lot_id,
            frames_dir=None,
            expected_frame_count=expected_frame_count,
            observed_frame_count=None,
            missing_frames=(),
            unexpected_files=(),
            nonconforming_files=(),
            selection_recomputed=selection is not None,
            digest_matches=digest_matches,
            findings=tuple(findings),
        )

    frames_path = project_dir / PurePosixPath(str(frames_dir_relative))
    if not frames_path.is_dir():
        findings.append(VERIFY_FRAMES_DIR_ABSENT)
        return LotVerification(
            lot_id=lot_id,
            frames_dir=str(frames_dir_relative),
            expected_frame_count=expected_frame_count,
            observed_frame_count=None,
            missing_frames=(),
            unexpected_files=(),
            nonconforming_files=(),
            selection_recomputed=selection is not None,
            digest_matches=digest_matches,
            findings=tuple(findings),
        )

    entries = sorted(entry.name for entry in frames_path.iterdir())
    observed_frame_count = len(entries)

    rush_id = str(lot.get("rush_id") or "")
    fps_target = _lot_fps_target(manifest, lot)

    expected_names: set[str] | None = None
    if selection is not None and rush_id and fps_target is not None:
        expected_names = {
            build_extracted_frame_filename(rush_id, fps_target, frame.frame_timecode)
            for frame in selection.frames
        }

    conforming: set[str] = set()
    nonconforming: list[str] = []
    for name in entries:
        if rush_id and fps_target is not None and _is_conforming_frame_name(
            name, rush_id, fps_target
        ):
            conforming.add(name)
        else:
            nonconforming.append(name)

    missing: list[str] = []
    unexpected: list[str] = []
    if expected_names is not None:
        missing = sorted(expected_names - conforming)
        unexpected = sorted(conforming - expected_names)

    if missing:
        findings.append(VERIFY_MISSING_FRAMES)
    if unexpected:
        findings.append(VERIFY_UNEXPECTED_FRAMES)
    if nonconforming:
        findings.append(VERIFY_NONCONFORMING_NAMES)
    if expected_frame_count is not None and observed_frame_count != expected_frame_count:
        findings.append(VERIFY_FRAME_COUNT_MISMATCH)

    return LotVerification(
        lot_id=lot_id,
        frames_dir=str(frames_dir_relative),
        expected_frame_count=expected_frame_count,
        observed_frame_count=observed_frame_count,
        missing_frames=tuple(missing),
        unexpected_files=tuple(unexpected),
        nonconforming_files=tuple(nonconforming),
        selection_recomputed=selection is not None,
        digest_matches=digest_matches,
        findings=tuple(findings),
    )


def _is_conforming_frame_name(name: str, rush_id: str, fps_target: Any) -> bool:
    """Le nom respecte-t-il la convention de frame extraite de la story 3.1 ?

    Le motif n'est **jamais** reecrit ici, ni pour construire le nom ni pour le
    relire: la lecture appartient a ``io.naming.read_extracted_frame_timecode``
    et la construction a ``build_extracted_frame_filename``. La conformite est
    l'egalite du nom reconstruit avec le nom lu. Reconstruire le prefixe en
    local -- ce que faisait la premiere version -- etait une seconde ecriture
    de la convention, exactement ce que l'AC 15 interdit.
    """
    try:
        timecode = read_extracted_frame_timecode(name)
        return build_extracted_frame_filename(rush_id, fps_target, timecode) == name
    except Exception:
        return False


# --------------------------------------------------------------------------
# Couche de persistance
# --------------------------------------------------------------------------


def _serialize(manifest: Mapping[str, Any]) -> str:
    """Serialisation JSON deterministe (Piege 7).

    ``sort_keys=True`` rend l'idempotence verifiable **octet a octet**: un
    ``json.dumps`` dont l'ordre des cles depend de l'ordre d'insertion la
    rendrait dependante du chemin de code.
    """
    return json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def _atomic_write(manifest_path: Path, manifest: Mapping[str, Any]) -> None:
    """Temporaire dans le dossier projet, validation, puis ``os.replace``.

    Ordre non negociable (AC 11, Piege 2): ``io.manifest.validate_manifest``
    prend un **chemin**, donc valider impose d'ecrire d'abord. Ecrire dans le
    vrai ``project.json`` puis valider -- ce que fait ``reconstruct-project``
    dans ``cli.py``, acceptable la ou le manifest est reconstruit de zero sur
    un projet vierge -- ecraserait ici un manifest valide par un manifest
    invalide. Un echec laisse le ``project.json`` precedent **strictement
    intact** et ne laisse aucun temporaire.

    Le temporaire vit dans le dossier projet, jamais dans ``/tmp``:
    ``os.replace`` n'est atomique qu'a l'interieur d'un meme systeme de
    fichiers.
    """
    payload = _serialize(manifest)
    project_dir = manifest_path.parent
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=project_dir,
        prefix=f".{manifest_path.name}.",
        suffix=".tmp",
        delete=False,
    )
    temp_path = Path(handle.name)
    try:
        with handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        validate_manifest(temp_path)
    except ValidationError as error:
        temp_path.unlink(missing_ok=True)
        raise ManifestWriteError(
            f"Manifest d'extraction invalide, rien n'a ete ecrit: {error}. Le "
            f"{manifest_path.name} precedent est intact"
        ) from error
    except OSError as error:
        temp_path.unlink(missing_ok=True)
        raise ManifestWriteError(
            f"Ecriture du manifest impossible: {error}. Le {manifest_path.name} "
            "precedent est intact"
        ) from error
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise

    try:
        os.replace(temp_path, manifest_path)
    except OSError as error:
        temp_path.unlink(missing_ok=True)
        raise ManifestWriteError(
            f"Remplacement atomique du manifest impossible: {error}. Le "
            f"{manifest_path.name} precedent est intact"
        ) from error


def _load_existing_manifest(manifest_path: Path) -> dict | None:
    """Relire le `project.json` present, ou echouer dans la hierarchie du module.

    Un `project.json` tronque -- coupure de courant, disque plein, copie
    interrompue -- levait une `json.JSONDecodeError` nue, hors de la hierarchie
    `ExtractionPersistenceError` que la CLI capture: l'operateur recevait une
    trace Python au lieu d'un message actionnable, sur un cas de panne
    parfaitement ordinaire.
    """
    if not manifest_path.is_file():
        return None
    try:
        return load_manifest(manifest_path)
    except json.JSONDecodeError as exc:
        raise ExtractionPersistenceError(
            f"Le fichier {manifest_path} n'est pas un JSON valide ({exc}). "
            "Aucune ecriture n'a eu lieu. Restaurer une copie saine du "
            "project.json, ou repartir d'un dossier projet vierge"
        ) from exc
    except OSError as exc:
        raise ExtractionPersistenceError(
            f"Le fichier {manifest_path} n'a pas pu etre lu ({exc}). "
            "Aucune ecriture n'a eu lieu"
        ) from exc


def persist_extraction(
    project_dir: str | Path, record: ExtractionRecord
) -> PersistedExtraction:
    """Ecrire l'extraction dans ``<project_dir>/project.json`` et se relire.

    Point d'entree unique de la persistance d'extraction. Appele par la
    commande ``extract`` (story 3.1) juste apres l'ecriture reussie des TIFF
    (``decisions-2026-08-03.md``, decision 1 / ARB-1); cette story ne modifie
    pas ``cli.py``.

    Sequence: lecture du manifest existant s'il y en a un, fusion pure
    (``build_extraction_manifest``), ecriture atomique validee
    (``_atomic_write``), puis auto-controle par ``verify_extracted_lot``,
    dont le rapport est remonte a l'appelant.

    Toute erreur laisse le ``project.json`` precedent strictement intact.
    """
    project_dir = Path(project_dir)
    manifest_path = project_dir / MANIFEST_FILENAME

    existing = _load_existing_manifest(manifest_path)
    manifest = build_extraction_manifest(existing, record)

    project_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write(manifest_path, manifest)

    verification = verify_extracted_lot(project_dir, manifest, record.lot_id)
    return PersistedExtraction(
        manifest_path=manifest_path,
        lot_id=record.lot_id,
        manifest=manifest,
        verification=verification,
    )


def build_rush_declaration_manifest(
    existing: Mapping[str, Any] | None, project_id: str, record: RushRecord
) -> dict[str, Any]:
    """Fusionner ``record`` dans ``rushes[]`` **et rien d'autre** (story 11.4e).

    **Couche pure**: aucune I/O, aucun acces disque. Meme fusion en place par
    ``rush_id`` que ``build_extraction_manifest``, meme entree produite par le
    meme ``_build_rush_entry`` -- l'entree d'un rush declare puis extrait est
    donc, champ pour champ, celle du meme rush extrait directement (AC 1.3).

    ``lots[]`` n'est **pas** touche, et c'est la moitie du contrat: declarer
    n'extrait pas (`EPIC11-ARB-131`). Aucune section non possedee par cette
    story n'est reecrite.
    """
    manifest = _manifeste_de_base(existing, project_id)

    rushes = list(manifest.get("rushes") or [])
    for index, rush in enumerate(rushes):
        if rush.get("rush_id") == record.rush_id:
            rushes[index] = _build_rush_entry(rush, record)
            break
    else:
        rushes.append(_build_rush_entry(None, record))
    manifest["rushes"] = rushes
    return manifest


def persist_rush_declaration(
    project_dir: str | Path, project_id: str, record: RushRecord
) -> PersistedRushDeclaration:
    """Ecrire la declaration d'un rush dans ``<project_dir>/project.json``.

    Meme sequence et **meme ecriture atomique validee** que
    ``persist_extraction``: lecture du manifest existant, fusion pure,
    ``_atomic_write`` (temporaire dans le dossier projet, validation au schema,
    puis ``os.replace``). Toute erreur laisse le ``project.json`` precedent
    strictement intact et ne laisse aucun temporaire.

    Pas d'auto-controle par ``verify_extracted_lot``: il verifie un **lot**, et
    une declaration n'en cree aucun. Le controle qui vaut ici est celui que
    ``_atomic_write`` fait deja -- le manifeste ecrit valide le schema, ou rien
    n'est ecrit.
    """
    project_dir = Path(project_dir)
    manifest_path = project_dir / MANIFEST_FILENAME

    existing = _load_existing_manifest(manifest_path)
    manifest = build_rush_declaration_manifest(existing, project_id, record)

    _atomic_write(manifest_path, manifest)
    return PersistedRushDeclaration(
        manifest_path=manifest_path,
        rush_id=record.rush_id,
        manifest=manifest,
    )
