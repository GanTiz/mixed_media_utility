"""Persistance au manifest de ce qu'une passe de scan vient de produire (story 5.7).

C'est la story qui ferme la promesse centrale du pivot d'architecture -- « le
projet doit etre reconstructible a l'identique a partir des fichiers eux-memes
et des metadonnees qu'ils embarquent » -- et elle porte le risque le plus grave
de l'Epic 5: **R12, une mauvaise association ecrite est pire qu'un refus**. Le
seul faux pas interdit est le **faux succes**: un lot partiel est ecrit et
declare partiel, jamais declare complet ni refuse en bloc.

Reprendre, ne pas copier
------------------------
Rien de ce qui existait n'est reecrit ici:

* ``io.reconstruction.reconstruct_project_manifest`` fait toute la validation
  des payloads (champs obligatoires, coherence inter-pages, version de payload,
  dedoublonnage par ``page_index``, bornes, unicite des ``slot_index``, fusion
  non destructive de ``rushes`` et ``lots``, refus d'un chemin absolu,
  validation finale contre le schema). Ce module l'**appelle**, avec l'etat de
  lot ``"scan"`` et l'origine ``"scan"``, et comble ce qu'elle ne peut pas
  savoir: ce qui s'est reellement passe sur le disque.
* ``io.extraction_manifest._atomic_write`` / ``_serialize`` /
  ``_load_existing_manifest`` / ``_relative_posix`` sont ceux de la story 3.4,
  importes tels quels. Il n'existe pas de seconde version de ces fonctions dans
  le depot et il ne doit pas en exister: le contre-exemple a ne pas reproduire
  est ``reconstruct-project`` (``cli.py``), qui ecrit **puis** valide -- tenable
  sur un projet vierge, intenable des lors qu'un manifest existant est enrichi.
* ``io.manifest.validate_lot_state_transition`` est le **seul** juge de l'ordre
  des etats de lot. Aucune comparaison d'etats n'est reecrite ici.
* ``scan_output_frames.SYNTHETIC_FRAME_REASONS`` et ``validate_synthetic_reason``
  sont ceux de la story 5.6, importes et jamais recopies ni etendus.

Enrichir ne fait jamais desapprendre
------------------------------------
Le scan connait **strictement moins** que le manifest d'origine: le QR ne porte
ni ``fps_source``, ni ``resolution_source``, ni aucun ``source_*``, ni
``rounding_policy``, ni ``timecode_base``, ni ``source_frame_count`` -- donc ni
``frame_timecodes_digest``, irrecalculable depuis un scan. Toute regle de fusion
qui traiterait les deux sources symetriquement serait fausse.

``_merge_entries`` protege deja les entrees de ``rushes[]`` et ``lots[]``. Le
trou etait ailleurs: ``reconstruct_project_manifest`` **reconstruit le document
de zero** et repose ``artifacts: {}``, ``video: {}`` et ``color`` reduit a
``target_colorspace``, en perdant ``created``. C'est ce niveau -- les sections de
tete -- que ``_preserve_head_sections`` ferme.

Limite de concurrence, heritee et declaree
------------------------------------------
Le depot n'a **aucun verrou** sur la sequence lecture-modification-ecriture du
manifest: deux ecritures simultanees et le dernier ecrivain gagne, en rendant
tous deux un succes. Le defaut est deja consigne (``deferred-work.md``, revues
3.1 et 3.4) et un troisieme ecrivain a ete ajoute par la story 5.11. Ce module
en ajoute un **quatrieme** -- un ``scan`` concurrent d'un ``extract`` ou d'un
``makepdf`` sur le meme projet. Il ne corrige pas: il faut une politique
globale, hors perimetre. Il refuse seulement de laisser la limite se
redecouvrir une cinquieme fois. Regle d'usage jusqu'a nouvel ordre: **une seule
commande ecrivant le manifest a la fois par projet**.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..numeric_guards import is_strict_int
from . import naming
from .extraction_manifest import (
    MANIFEST_FILENAME,
    MIGRATABLE_SCHEMA_VERSIONS,
    ExtractionPersistenceError,
    LegacyManifestError,
    _atomic_write,
    _load_existing_manifest,
    _migrate_v2_0,
    _relative_posix,
)
from .manifest import CURRENT_SCHEMA_VERSION, LOT_STATES
# Les bornes du rang se LISENT chez leurs proprietaires et ne se recopient
# jamais (`EPIC5-ARB-78`): `naming` possede le domaine, et `version_ranks`
# possede la regle -- « le systeme de versionnage est le meme PARTOUT pour
# tous les objets » (`EPIC11-ARB-108`).
from .naming import VERSION_RANK_MAX
# `EPIC11-ARB-176`: le SEUL point d'entree de la lecture du rang au QR
# (`EPIC11-ARB-91`), importe et jamais recopie.
from .payload import payload_version_rank
from .reconstruction import (
    ORIGIN_SCAN,
    ReconstructionError,
    _check_lot_consistency,
    _check_pile_homogene,
    _validate_page_payload,
    reconstruct_project_manifest,
)
from .version_ranks import RANG_ORIGINE

# --------------------------------------------------------------------------
# Table de persistance (normative)
# --------------------------------------------------------------------------

#: Etat pose par cette chaine, exclusivement via
#: `io.manifest.validate_lot_state_transition` (EPIC5-ARB-7, option « a »):
#: `scan` = « les planches de ce lot ont ete scannees et ses frames
#: reconstruites ». `reconstruction` reste a la sous-commande
#: `reconstruct-project`, qui porte deja ce nom. `"scan"` est connu de
#: `LOT_STATES` et de l'enum du schema depuis la story 2.2, mais n'avait
#: jusqu'ici de producteur que sur le chemin POC legacy (`meta.lot.state` d'un
#: document sans `schema_version` et sans `lots[]`): il en recoit ici son
#: premier sur `lots[].state` du contrat v2.
SCAN_LOT_STATE = "scan"

#: Ensemble des rangs de TIRAGE que ce lot a effectivement vus passer au scanner
#: (`EPIC11-ARB-176`, Egan le 2026-09-02). Nomme ici pour que l'atelier PDF le
#: lise plutot que de recopier le litteral.
#:
#: **C'est un champ DE PLUS, jamais un remplacement de `SCAN_LOT_STATE`**
#: (AC 7.11b). L'etat de lot dit « des planches de ce lot ont ete scannees » et
#: sert a la garde de transition ; celui-ci dit **lesquelles**. Sans lui,
#: l'interdit d'`EPIC11-ARB-174` -- « un tirage scanne ne peut pas etre
#: ecrase » -- refuserait d'ecraser un `v4` jamais imprime au seul motif que le
#: `v3` du meme lot a ete scanne : un blocage sec sur un objet innocent, ce
#: qu'`EPIC11-ARB-89` interdit.
#:
#: **Le rang 1 s'y ecrit EXPLICITEMENT**, a l'inverse de la charge utile QR
#: (`EPIC11-ARB-91`) et du nom de fichier, qui l'omettent tous deux. L'omission
#: y achete des octets sur du papier et un fragment de nom en moins ; ici elle
#: rendrait `[1]` indiscernable de la liste vide, c'est-a-dire « le tirage
#: d'origine a ete scanne » indiscernable de « aucun tirage ne l'a ete ». Trois
#: conventions pour le meme fait seraient de trop ; deux le sont deja, et
#: celle-ci est la seule ou l'omission couterait le sens.
SCANNED_VERSION_RANKS_FIELD = "scanned_version_ranks"

#: Valeur de `color_calibration_status` qui dit qu'une correction a **reellement** touche
#: des pixels (story 5.19). Nommee ici plutot qu'ecrite en litteral au point d'usage.
#:
#: Elle est **recopiee** de `color_pipeline.APPLIED_STATUS` et non importee, pour la
#: raison de couches que ce module tient partout: `io/` ne charge pas OpenCV a l'import, et
#: `color_pipeline` en depend. La recopie est donc forcee -- et son risque, la divergence
#: silencieuse des deux orthographes, est ferme par un test qui confronte les deux
#: constantes. C'est le meme montage que `ScanPageProvenance` emploie pour le vocabulaire
#: de 5.2, a ceci pres que celui-la peut se permettre un import tardif dans une methode.
CALIBRATION_APPLIED = "applied"

#: Meme montage, meme raison, pour le statut d'une page dont **rien n'a ete mesure**.
#: Il est devenu necessaire ici avec `EPIC5-ARB-69`: une page sans resultat de
#: calibration ne peut plus heriter du statut de son lot, donc ce module doit savoir
#: ecrire « on n'a rien mesure sur celle-ci » sans l'emprunter a personne.
CALIBRATION_NOT_APPLIED = "not_applied"

#: Champs de `lots[]` que `reconstruct_project_manifest` ecrit **avant** que ce
#: module n'intervienne. Ils sont nommes ici pour que `SCAN_LOT_FIELDS` puisse
#: se lire comme une table exhaustive de ce que la chaine de scan pose sur un
#: lot: la table voisine dit ce que ce module ecrit, celle-ci ce que la brique
#: qu'il appelle ecrit, et leur union est **tout** ce qu'un lot ne du scan
#: porte. Le constat qui a impose cette seconde table: `SCAN_LOT_FIELDS` se
#: declarait « contrat » alors que trois champs de plus atterrissaient sur
#: `lots[]` par le chemin de la reconstruction (revue couche 1, F7).
#:
#: **`timecode_base_fps` la rejoint par la story 2.7** (payload 2.1,
#: `EPIC7-ARB-56`): `reconstruct_project_manifest` l'ecrit desormais sur le lot,
#: au meme titre que `fps_target`, des que les payloads scannes le portent
#: (planche imprimee en 2.1).
RECONSTRUCTION_LOT_FIELDS: tuple[str, ...] = (
    "lot_id", "rush_id", "fps_target", "timecode_base_fps",
)

#: Emplacement unique de chaque donnee ecrite par ce module sur `lots[]`, sur
#: le motif de `PDF_LOT_FIELDS` (story 5.11). **Toute donnee absente de cette
#: table n'est pas ecrite** par ce module: la table est le contrat, pas un
#: resume du code, et un test la confronte au lot reellement produit.
SCAN_LOT_FIELDS: tuple[str, ...] = (
    "state",
    "output_frames_dir",
    "reconstructed_frame_count",
    "synthetic_frame_count",
    "synthetic_frames",
    "expected_frame_count",
    "template_id",
    "patch_preset_id",
    "gamut_map_id",
    # `EPIC5-ARB-68`. Ecrit **conditionnellement** -- voir
    # `_write_lot_calibration_status` --, ce que cette table autorise et n'impose pas:
    # elle dit ou une donnee est ecrite quand elle l'est, pas qu'elle l'est toujours.
    # Le lot d'un projet sans calibration ne le porte pas, et c'est ce qui tient le
    # filet de non-regression octet a octet de l'AC 12 de 5.19.
    "color_calibration_status",
    # `EPIC11-ARB-109`. Registre DURABLE par lot -- voir
    # `_fusionner_l_historique_de_reconstruction`.
    "reconstructions",
    # `EPIC11-ARB-176`. Ecrit a CHAQUE passe -- une passe de scan reussie porte
    # au moins un payload decode (`ScanRecord.__post_init__`), donc au moins un
    # rang. Voir `_apprendre_les_rangs_de_tirage_scannes`.
    SCANNED_VERSION_RANKS_FIELD,
)

#: Les trois identifiants poses a l'impression par la story 5.11 et portes par
#: le QR de la planche imprimee. En sortie de presse ils sont egaux **par
#: construction** (meme source unique, `5-11-...md`, son AC 7).
#:
#: EPIC5-ARB-34, repercussion sur l'AC 5: la chaine de scan les **ecrit** quand
#: ils sont absents et les **confronte** quand ils sont presents. Une garde qui
#: saute les champs absents ne garde rien, et un projet ne des planches seules
#: -- le cas central de cette story -- ne les porte pas: la garde etait donc
#: inerte precisement la ou elle doit mordre. Ecrire une valeur qu'aucun
#: manifest ne portait est un **apprentissage**, jamais un ecrasement (AC 4).
#: Ecrire n'est pas declarer: la story 5.11 reste seule proprietaire de leur
#: declaration au schema.
PRINTED_IDENTIFIER_FIELDS: tuple[str, ...] = (
    "template_id",
    "patch_preset_id",
    "gamut_map_id",
)

#: Vocabulaire ferme du statut de geometrie de page porte a la provenance de
#: scan. Deux valeurs, pas trois: une page dont la geometrie n'a pas ete tentee
#: est une page refusee avant l'homographie, et son `qr_status` le dit deja.
HOMOGRAPHY_RESOLVED = "resolved"
HOMOGRAPHY_UNRESOLVED = "unresolved"
HOMOGRAPHY_STATUSES: tuple[str, ...] = (HOMOGRAPHY_RESOLVED, HOMOGRAPHY_UNRESOLVED)

# --------------------------------------------------------------------------
# Constats, tous informatifs (un refus est une exception, jamais un code)
# --------------------------------------------------------------------------

#: La garde de transition a refuse `-> scan`: l'etat en place est conserve tel
#: quel et la commande reussit. Un lot deja en `reconstruction` ou en `encode`
#: ne « revient » pas en `scan` -- c'est le scenario nominal « projet recree
#: depuis des payloads, puis planches scannees », pas une erreur.
SCAN_STATE_CONSERVED = "ETAT_DE_LOT_CONSERVE"

#: Cette passe a remplace au moins une mire par une vraie frame. C'est un
#: **gain**: il se fait, sans drapeau supplementaire cote manifest (AC 10).
SCAN_SYNTHETIC_REPLACED_BY_REAL = "MIRE_REMPLACEE_PAR_UNE_VRAIE_FRAME"

#: Cette passe a ecrit une mire par-dessus une vraie frame. C'est une
#: **perte**, et elle n'a pu avoir lieu que parce que l'operateur a explicitement
#: leve le refus prealable avec `--overwrite` (EPIC5-ARB-34, clause 2). Une fois
#: les fichiers ecrits, le manifest enregistre le reel et ne refuse plus: un
#: manifest qui refuserait d'enregistrer la degradation continuerait de declarer
#: reelles des images qui n'existent plus (clause 3). Le fait est **nomme au
#: rapport**, jamais silencieux.
SCAN_REAL_FRAMES_DEGRADED = "VRAIES_FRAMES_REMPLACEES_PAR_DES_MIRES"

#: Le lot porte au moins une frame de remplacement. Le fichier existe, l'image
#: du film non: le verdict de completude est interdit, meme si aucune page ne
#: manque (EPIC5-ARB-8, AC 6).
SCAN_SYNTHETIC_FRAMES_PRESENT = "FRAMES_SYNTHETIQUES_PRESENTES"

#: Le lot n'est pas complet au sens des deux cardinaux. Dit explicitement pour
#: que « ce lot est-il fini ? » ait une reponse dans le compte rendu de la
#: commande, et pas seulement dans le manifest.
SCAN_LOT_INCOMPLETE = "LOT_INCOMPLET"

#: Le cardinal attendu est **indeterminable** (la derniere page manque, donc le
#: nombre de frames de la derniere planche est inconnu) **et** le manifest n'en
#: portait aucun. Il n'est alors pas ecrit, jamais devine ni remplace par un
#: autre cardinal. Quand le manifest en portait un, c'est `CARDINAL_ATTENDU_
#: CONSERVE` qui est emis: le cardinal est ecrit, donc « indeterminable » serait
#: faux dans la meme sortie.
SCAN_EXPECTED_FRAME_COUNT_INDETERMINABLE = "CARDINAL_ATTENDU_INDETERMINABLE"

#: Le manifest portait deja un cardinal attendu que le scan ne rededuit pas a
#: l'identique -- soit qu'il en deduise un autre, soit qu'il ne puisse pas le
#: deduire du tout. Celui du manifest est **conserve**: il vient de
#: l'extraction, qui a compte de vraies frames, la ou le scan ne compte que des
#: emplacements de planche. Ce qui a ete mesure une fois ne se desapprend pas.
SCAN_EXPECTED_FRAME_COUNT_CONSERVED = "CARDINAL_ATTENDU_CONSERVE"

#: Le projet porte d'autres lots que celui qui vient d'etre scanne. Constat
#: purement informatif: scanner un projet lot par lot est le cas nominal, et
#: les autres lots restent intacts (question ouverte 4 de la story).
SCAN_OTHER_LOTS_NOT_SCANNED = "AUTRES_LOTS_NON_SCANNES"

#: Vocabulaire complet des constats de ce module, tous informatifs.
SCAN_PERSISTENCE_CODES: tuple[str, ...] = (
    SCAN_STATE_CONSERVED,
    SCAN_SYNTHETIC_REPLACED_BY_REAL,
    SCAN_REAL_FRAMES_DEGRADED,
    SCAN_SYNTHETIC_FRAMES_PRESENT,
    SCAN_LOT_INCOMPLETE,
    SCAN_EXPECTED_FRAME_COUNT_INDETERMINABLE,
    SCAN_EXPECTED_FRAME_COUNT_CONSERVED,
    SCAN_OTHER_LOTS_NOT_SCANNED,
)


def validate_persistence_code(code: str) -> str:
    """Garde de vocabulaire: un constat hors table est un defaut, pas une prose."""
    if code not in SCAN_PERSISTENCE_CODES:
        raise ScanPersistenceError(
            f"Constat de persistance de scan inconnu: {code!r}. Vocabulaire "
            f"ferme: {', '.join(SCAN_PERSISTENCE_CODES)}."
        )
    return code


# --------------------------------------------------------------------------
# Hierarchie d'exceptions
# --------------------------------------------------------------------------


class ScanPersistenceError(ExtractionPersistenceError):
    """Racine des erreurs de persistance de scan.

    Sous-classe de la hierarchie de la story 3.4 pour que la CLI n'ait qu'un
    seul `except` a tenir. Aucune de ces erreurs ne laisse d'ecriture
    partielle: le `project.json` precedent reste **strictement intact**.
    """


class ScanManifestConflictError(ScanPersistenceError):
    """Le scan contredit ce que le manifest declare deja: refus nomme.

    C'est le coeur du risque R12. Un refus est toujours recuperable la ou une
    mauvaise association ecrite ne l'est pas, et **aucun `--overwrite` ne le
    leve**: le drapeau ne couvre que le rescan du *meme* lot (AC 10), jamais
    l'apport d'une planche etrangere au manifest d'un autre projet.
    """


class ScanFrameRegressionError(ScanPersistenceError):
    """Une frame reelle redeviendrait une frame de remplacement.

    Le mouvement inverse -- une mire remplacee par une vraie frame -- est un
    **gain** et se fait sans drapeau. Celui-ci est une **perte**: il exige un
    `--overwrite` explicite (AC 10).
    """


# --------------------------------------------------------------------------
# Objets d'entree, API figee
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ScanPageProvenance:
    """Ce qu'une planche a livre, telle que la detection (5.2) l'a vue.

    Provenance, pas mesure: ni residu d'homographie, ni facteur d'echelle. La
    question ouverte 2 de la story recommande de typer au schema ce dont le
    vocabulaire est deja ferme ailleurs et de laisser libres les champs de
    diagnostic encore instables -- ce sont exactement les quatre champs
    ci-dessous, tous a vocabulaire ferme, et rien de plus.
    """

    read_rank: int
    status: str
    qr_status: str
    page_index: int | None = None
    homography_status: str = HOMOGRAPHY_UNRESOLVED

    def __post_init__(self) -> None:
        # Import tardif: `scan_detection` tire OpenCV et la detection ArUco,
        # que `io/` n'a aucune raison de charger a l'import. Le vocabulaire est
        # neanmoins **celui de 5.2**, importe et jamais recopie -- deux
        # vocabulaires fermes voisins pour la meme chose, c'est une table de
        # traduction et une divergence au premier ajustement.
        from ..scan_detection import PAGE_QR_STATUSES, PAGE_STATUSES

        if not is_strict_int(self.read_rank) or self.read_rank < 0:
            raise ScanPersistenceError(
                f"read_rank invalide: {self.read_rank!r}. Un entier positif ou "
                "nul est attendu (`True` n'est pas un entier ici)."
            )
        if self.status not in PAGE_STATUSES:
            raise ScanPersistenceError(
                f"Statut de page inconnu: {self.status!r}. Vocabulaire ferme de "
                f"la story 5.2: {', '.join(PAGE_STATUSES)}."
            )
        if self.qr_status not in PAGE_QR_STATUSES:
            raise ScanPersistenceError(
                f"Statut de decodage QR inconnu: {self.qr_status!r}. Vocabulaire "
                f"ferme de la story 5.2: {', '.join(PAGE_QR_STATUSES)}."
            )
        if self.homography_status not in HOMOGRAPHY_STATUSES:
            raise ScanPersistenceError(
                f"Statut d'homographie inconnu: {self.homography_status!r}. "
                f"Vocabulaire ferme: {', '.join(HOMOGRAPHY_STATUSES)}."
            )
        if self.page_index is not None and (
            not is_strict_int(self.page_index) or self.page_index < 0
        ):
            raise ScanPersistenceError(
                f"page_index de provenance invalide: {self.page_index!r}. Un "
                "entier base zero, ou `None` quand le QR n'a rien livre."
            )

    def as_document(self) -> dict:
        return {
            "read_rank": self.read_rank,
            "page_index": self.page_index,
            "status": self.status,
            "qr_status": self.qr_status,
            "homography_status": self.homography_status,
        }


@dataclass(frozen=True)
class ScanRecord:
    """Ce qu'une passe de scan reussie declare au manifest.

    `page_payloads` sont les payloads QR **deja decodes** par 5.2 -- pas des
    fichiers JSON relus, pas des dicts ecrits a la main. `output_report` est le
    rapport de 5.6 tel quel, en typage structurel: le lier a la classe de 5.6
    ferait descendre OpenCV dans `io/`. Le prix de ce choix est un test
    d'integration contre le **vrai** producteur, sans quoi un renommage de
    champ passerait inapercu (action item 3 de la retro Epic 4).
    """

    page_payloads: tuple[dict, ...]
    output_report: Any
    scan_dpi: int
    ingest_slug: str
    pages: tuple[ScanPageProvenance, ...] = ()
    #: Resultats de calibration par page, **en typage structurel** comme
    #: `output_report`, et pour la meme raison: les lier a `color_calibration`
    #: ferait descendre OpenCV et numpy dans `io/`. Le prix de ce choix est le meme
    #: -- un test d'integration contre le **vrai** producteur, sans quoi un
    #: renommage de champ passerait inapercu.
    #:
    #: Story 5.16, AC 10: c'est ce fil qui fait remonter un `PageCalibration`
    #: jusqu'a `_build_calibration_results`. Sans lui, la forme de la provenance
    #: etait declaree et projetee par `color_calibration`, mais rien ne la portait
    #: au document -- et l'AC n'etait tenue qu'en intention.
    #:
    #: Chaque entree est un couple ``(page_index, resultat)``. L'index est **porte a
    #: cote** du resultat et non lu dedans, parce que `PageCalibration` n'en a pas:
    #: elle decrit une correction, pas une position dans un lot. Le deviner par le
    #: rang de la sequence serait exactement l'appariement positionnel qui a coute
    #: quatre regressions a ce depot (mutants `M33`, `M25`).
    page_calibrations: tuple[tuple[int, Any], ...] = ()
    #: L'operateur a-t-il **explicitement** demande le contournement de la garde de
    #: divergence (`color_calibration.DIVERGENCE_BYPASS_FLAG`)?
    #:
    #: Il ne s'inscrit pas au document: `EPIC5-ARB-57` veut que le manifest decrive
    #: **ce qui s'est passe**, pas ce qui a ete demande, et la moitie couleur a
    #: tranche dans ce sens (« le drapeau de contournement se declare sur le constat
    #: et non sur la demande »). Ce qu'il fait ici est l'exact symetrique, et c'est
    #: l'AC 15: un contournement **constate** ne peut pas etre inscrit si personne ne
    #: l'a demande. Sans cette confrontation, « explicite, jamais un repli
    #: automatique » resterait une phrase -- un repli automatique produirait
    #: exactement le meme document qu'une demande explicite.
    divergence_bypass_requested: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.page_payloads, (list, tuple)) or not self.page_payloads:
            raise ScanPersistenceError(
                "Aucun payload de page decode: il n'y a rien a declarer au "
                "manifest. Un lot dont aucune planche n'a livre son QR n'ecrit "
                "pas de manifest appauvri, il ne l'ecrit pas du tout."
            )
        if not is_strict_int(self.scan_dpi) or self.scan_dpi <= 0:
            raise ScanPersistenceError(
                f"DPI de scan invalide: {self.scan_dpi!r}. Un entier strictement "
                "positif est attendu, et jamais un booleen."
            )
        if not isinstance(self.ingest_slug, str) or not self.ingest_slug:
            raise ScanPersistenceError(
                f"Slug d'ingestion invalide: {self.ingest_slug!r}. Une chaine non "
                "vide est attendue."
            )
        if (
            "/" in self.ingest_slug
            or "\\" in self.ingest_slug
            or self.ingest_slug.strip() != self.ingest_slug
            or ".." in Path(self.ingest_slug).parts
        ):
            # Le depot a une regle explicite -- aucune chaine du manifest ne
            # remonte au-dessus du projet -- et ce champ s'y soustrayait: il
            # etait ecrit tel quel, sans passer par `_relative_posix` comme
            # `output_frames_dir`. Un slug est un **segment** de chemin, jamais
            # un chemin.
            raise ScanPersistenceError(
                f"Slug d'ingestion invalide: {self.ingest_slug!r}. C'est un "
                "**segment** de chemin -- le nom du dossier de lot sous "
                "`scans/` --, jamais un chemin: ni separateur, ni remontee "
                "`..`, ni espace de bordure."
            )
        for provenance in self.pages:
            if not isinstance(provenance, ScanPageProvenance):
                raise ScanPersistenceError(
                    "Chaque entree de provenance doit etre une "
                    f"`ScanPageProvenance`, recu {type(provenance).__name__}."
                )
        if not isinstance(self.divergence_bypass_requested, bool):
            raise ScanPersistenceError(
                "divergence_bypass_requested doit etre un booleen, recu "
                f"{self.divergence_bypass_requested!r}. C'est la trace d'une "
                "**demande** explicite de l'operateur, pas une valeur a deviner."
            )
        # Typage structurel, comme `output_report`: on exige les champs dont ce module
        # a besoin, jamais la classe. Un dictionnaire ou un `SimpleNamespace` de banc
        # passe donc, et un objet qui aurait perdu l'un de ces champs est refuse ici
        # plutot que decouvert plus loin en `AttributeError` sans rapport.
        vus: set[int] = set()
        for entree in self.page_calibrations:
            if not isinstance(entree, tuple) or len(entree) != 2:
                raise ScanPersistenceError(
                    "Chaque resultat de calibration est un couple "
                    f"(page_index, resultat), recu {entree!r}."
                )
            page_index, calibration = entree
            if not is_strict_int(page_index) or page_index < 0:
                raise ScanPersistenceError(
                    f"page_index de calibration invalide: {page_index!r}. Un entier "
                    "base zero est attendu, et jamais un booleen."
                )
            if page_index in vus:
                raise ScanPersistenceError(
                    f"Deux resultats de calibration declarent le meme page_index "
                    f"{page_index}. Une page a **une** correction (AC 5 de 5.4b): en "
                    "accepter deux laisserait l'ordre de lecture decider laquelle est "
                    "inscrite."
                )
            vus.add(page_index)
            for champ in _CALIBRATION_REQUIRED_ATTRIBUTES:
                if not hasattr(calibration, champ):
                    raise ScanPersistenceError(
                        f"Resultat de calibration incomplet: champ '{champ}' absent de "
                        f"{type(calibration).__name__}. Ce module consomme la forme "
                        "declaree par `color_calibration.PageCalibration` en typage "
                        "structurel, jamais la classe."
                    )


@dataclass(frozen=True)
class ScanManifestMerge:
    """Resultat de la fusion pure: le document et ce qu'il faut en dire."""

    manifest: dict
    lot_id: str
    state_written: str
    reconstructed_frame_count: int
    synthetic_frame_count: int
    expected_frame_count: int | None
    lot_complete: bool
    findings: tuple[str, ...] = ()


@dataclass(frozen=True)
class PersistedScan:
    """Resultat de la persistance: ce qui a ete ecrit, et ou."""

    manifest_path: Path
    lot_id: str
    manifest: dict
    state_written: str
    reconstructed_frame_count: int
    synthetic_frame_count: int
    expected_frame_count: int | None
    lot_complete: bool
    findings: tuple[str, ...] = ()


# --------------------------------------------------------------------------
# Lectures defensives du manifest deja present
# --------------------------------------------------------------------------


def _find_lot(manifest: Mapping[str, Any] | None, lot_id: Any) -> dict | None:
    """Entree de `lots[]` du lot vise, ou `None`.

    `None` est le cas nominal du premier scan d'un lot; ce module **cree** le
    lot, contrairement a la persistance d'impression (5.11) qui refuse un lot
    absent.
    """
    for lot in (manifest or {}).get("lots", []) or []:
        if isinstance(lot, dict) and lot.get("lot_id") == lot_id:
            return lot
    return None


def _prior_reconstruction(manifest: Mapping[str, Any] | None, lot_id: Any) -> dict | None:
    """Section `reconstruction` du document precedent **si elle decrit ce lot**.

    La section est unique par document et reecrite en entier a chaque
    reconstruction: le scan d'un second lot ecrase le detail par frame du
    premier. Sans `lot_id`, on ne peut pas savoir de quel lot elle parle -- et
    la deviner est exactement ce que la clause 4 d'EPIC5-ARB-32 interdit.
    """
    section = (manifest or {}).get("reconstruction")
    if not isinstance(section, dict):
        return None
    if section.get("lot_id") != lot_id:
        return None
    return section


RECONSTRUCTIONS_FIELD = "reconstructions"


def _fusionner_l_historique_de_reconstruction(
    lot: dict, existing_lot: Mapping[str, Any] | None,
    section: Mapping[str, Any], output_frames_dir: object,
) -> None:
    """Ajouter cette passe a l'historique DU LOT, sans jamais en perdre une.

    `EPIC11-ARB-109` (Egan, 2026-08-31 : « un historique par lot »). Il ferme
    exactement le defaut que `lots[].synthetic_frames` a deja ferme une fois
    (`EPIC5-ARB-33`) : la section `reconstruction` de tete est SINGULIERE et
    reecrite en entier a chaque passe, si bien qu'un lot reconstruit puis suivi
    d'un autre perdait la trace de son scan. La suppression par filiation
    rendait alors `None` et ne pouvait plus retrouver le dossier a supprimer --
    l'operateur retombait sur le `rm -rf` manuel, c'est-a-dire la fuite que
    `project remove` existe pour fermer.

    **La deduplication est PAR CONTENU, et c'est une contrainte dure, pas une
    commodite.** Aucune horodate n'entre dans une entree, pour le motif deja
    retenu par `EPIC4-ARB-8` puis par la section `scan` : une date rendrait
    deux passes identiques distinguables et interdirait l'idempotence octet a
    octet exigee par l'AC 10 de la story 5.7. Rejouer la meme passe doit rendre
    le meme document, et c'est la deduplication qui le tient.

    L'ordre est CHRONOLOGIQUE et jamais trie : il porte l'information « quelle
    passe a suivi laquelle », que le tri detruirait.
    """
    anterieures = [
        dict(entree)
        for entree in ((existing_lot or {}).get(RECONSTRUCTIONS_FIELD) or [])
        if isinstance(entree, Mapping)
    ]

    scan = section.get("scan")
    slug = scan.get("ingest_slug") if isinstance(scan, Mapping) else None
    if not isinstance(slug, str) or not slug:
        # Une passe sans slug n'a rien a offrir a la filiation. CONSERVER
        # l'historique anterieur plutot que de l'ecraser d'une entree vide:
        # perdre le passe serait le defaut meme que ce registre ferme.
        if anterieures:
            lot[RECONSTRUCTIONS_FIELD] = anterieures
        return

    entree = {"ingest_slug": slug}
    if isinstance(output_frames_dir, str) and output_frames_dir:
        entree["output_frames_dir"] = output_frames_dir
    for cle in ("origin", "status"):
        valeur = section.get(cle)
        if isinstance(valeur, str) and valeur:
            entree[cle] = valeur

    if entree not in anterieures:
        anterieures.append(entree)
    lot[RECONSTRUCTIONS_FIELD] = anterieures


def _prior_synthetic_names(lot: Mapping[str, Any] | None) -> set[str]:
    """Registre **durable** des mires du lot, lu du manifest precedent.

    `lots[].synthetic_frames` (EPIC5-ARB-33) remplace la lecture de
    `reconstruction.slots[].synthetic`: la section `reconstruction` est unique
    par document et reecrite en entier a chaque passe, si bien qu'ancrer une
    regle **durable** dessus la rendait aveugle des qu'un autre lot etait
    scanne entre deux passes. Le registre, lui, vit sur le lot et survit a tout.

    Un ensemble vide est le cas nominal du premier scan. Les entrees non
    textuelles sont ecartees plutot que de faire sortir une `TypeError` nue:
    cette lecture a lieu **avant** toute validation de schema sur le chemin de
    refus prealable (`check_scan_conflicts`), donc sur un document que
    l'operateur a pu editer a la main.
    """
    names = (lot or {}).get("synthetic_frames")
    if not isinstance(names, (list, tuple)):
        return set()
    return {name for name in names if isinstance(name, str) and name}


def _assert_mergeable(existing: Mapping[str, Any] | None) -> dict | None:
    """Refuser un document inenrichissable, et migrer la v2.0 en memoire.

    Point d'entree **unique** des deux chemins -- le refus prealable
    (`check_scan_conflicts`) et la fusion (`build_scan_manifest`) --, pour que
    la version de schema soit jugee **avant** la moindre ecriture de frame
    (EPIC5-ARB-34, clause 1) et non deux fois avec deux regles.

    Quatre refus et une migration:

    * ce qui n'est pas un objet JSON: un `project.json` qui contient `42` est
      un JSON valide et un manifest absurde;
    * le manifest legacy du POC (story 1.1, cle `id`, metadonnees sous
      `meta.*`), qui n'a ni `lots[]` ni `reconstruction`: l'enrichir
      fabriquerait un hybride qu'aucun des deux schemas ne decrit;
    * une `schema_version` **inconnue**, sur le modele exact de
      `build_extraction_manifest`: sans ce refus le document etait retrograde
      et son marqueur de version reecrit en `"2.1"` sans un mot -- l'inverse de
      la regle que ce module se donne (« enrichir ne fait jamais desapprendre »),
      applique au marqueur qui gouverne toutes les relectures ulterieures;
    * une section `rushes` ou `lots` mal formee: `_merge_entries` saute les
      entrees non conformes, si bien qu'un `lots` reduit a un objet, ou une
      entree reduite a une chaine, disparaissait **silencieusement** du
      document reecrit. C'est exactement la situation ou la promesse de
      non-perte compte le plus.

    La v2.0, elle, est **migree en memoire** (`_migrate_v2_0`) et jamais
    refusee: `io.manifest.SCHEMA_PATHS_BY_VERSION` la declare lisible, et
    `build_extraction_manifest` la migre deja. Sans cette migration, un projet
    v2.0 reel etait un chemin de panne **sans issue** -- la section `video` de
    la v2.0 est interdite par le contrat v2.1, donc toute relance echouait a
    l'identique, sur un message `jsonschema` brut portant sur une section que
    l'operateur n'avait pas touchee.
    """
    if existing is None:
        return None
    if not isinstance(existing, Mapping):
        raise ScanPersistenceError(
            "Le manifest lu n'est pas un objet JSON "
            f"({type(existing).__name__}): il ne peut porter ni `lots` ni "
            "`reconstruction`. Aucune ecriture n'a eu lieu. Restaurer une copie "
            "saine du project.json"
        )
    if "schema_version" not in existing:
        raise LegacyManifestError(
            f"Le {MANIFEST_FILENAME} present n'a pas de `schema_version`: c'est "
            "un manifest legacy du POC, qui ne porte ni `lots[]` ni "
            "`reconstruction`. Aucune migration automatique n'est faite et "
            "aucune ecriture n'a eu lieu"
        )
    declared = existing["schema_version"]
    if declared not in (CURRENT_SCHEMA_VERSION,) + MIGRATABLE_SCHEMA_VERSIONS:
        raise LegacyManifestError(
            f"schema_version {declared!r} non supportee (attendu "
            f"{CURRENT_SCHEMA_VERSION!r}, ou "
            f"{', '.join(MIGRATABLE_SCHEMA_VERSIONS)} migrable). Aucune "
            "migration automatique n'est faite et aucune ecriture n'a eu lieu"
        )
    for section in ("rushes", "lots"):
        entries = existing.get(section)
        if entries is None:
            continue
        if not isinstance(entries, list) or any(
            not isinstance(entry, dict) for entry in entries
        ):
            raise ScanPersistenceError(
                f"La section `{section}` du {MANIFEST_FILENAME} present est mal "
                "formee: une liste d'objets est attendue. L'enrichir la "
                "reecrirait en perdant ce qu'elle porte, ce qui est exactement "
                "ce que la regle « enrichir ne fait jamais desapprendre » "
                "interdit. Aucune ecriture n'a eu lieu. Restaurer une copie "
                "saine du project.json"
            )
    merged = copy.deepcopy(dict(existing))
    if declared != CURRENT_SCHEMA_VERSION:
        merged = _migrate_v2_0(merged)
    return merged


def _assert_known_lot_state(lot: Mapping[str, Any] | None) -> None:
    """Refuser un `lots[].state` hors vocabulaire **en nommant sa source**.

    La garde de transition rend l'etat courant tel quel quand elle refuse la
    transition, y compris lorsque le refus vient de « etat courant inconnu ».
    Cette chaine finissait alors dans le manifest reconstruit et se faisait
    attraper par le schema, avec un diagnostic qui accuse le document
    **produit** alors que la valeur fautive vient du document **relu** -- le
    contraire de ce que l'operateur doit corriger. Et le refus arrivait apres
    l'ecriture des frames.

    Une valeur **non textuelle** n'est pas un etat du tout et se lit « absent »,
    exactement comme `io.reconstruction._existing_lot_state` la lit: rien n'est
    desappris, la garde de transition accepte `None` sans condition, et les deux
    lectures du meme champ ne divergent pas.
    """
    if lot is None:
        return
    state = lot.get("state")
    if not isinstance(state, str) or state in LOT_STATES:
        return
    raise ScanManifestConflictError(
        f"Le {MANIFEST_FILENAME} present declare lots[{lot.get('lot_id')!r}]."
        f"state={state!r}, qui n'appartient pas au vocabulaire ferme des etats "
        f"de lot ({', '.join(LOT_STATES)}). La valeur fautive est dans le "
        "manifest relu, pas dans le document que le scan produirait: la "
        "corriger a la main est la seule issue. Aucune ecriture n'a eu lieu"
    )


# --------------------------------------------------------------------------
# Gardes de conflit (AC 5) -- le coeur du risque R12
# --------------------------------------------------------------------------


#: Le point H2 des arbitrages pose deux hypotheses -- planche **etrangere**
#: (identifiants discordants) et planche **perimee** (identifiants concordants,
#: parametres d'impression divergents) -- et le code sait deja laquelle des deux
#: s'applique quand il arrive ici: le lot a ete trouve **par son `lot_id`** et un
#: `project_id` divergent a deja ete refuse en amont par la garde reutilisee de
#: la reconstruction. Sur cette branche, le verdict est donc toujours « planche
#: perimee ». Enoncer les deux a egalite mettait du bruit sur le seul signal que
#: cette garde existe pour porter (revue couche 3, AC 5, reserve a).
_STALE_PLATE_HYPOTHESIS = (
    "Les identifiants de lot et de projet, eux, CONCORDENT -- c'est ce qui a "
    "permis de trouver ce lot, et un project_id divergent aurait deja ete "
    "refuse en amont. L'hypothese de la planche ETRANGERE (planche d'un autre "
    "lot, ou apportee au manifest d'un autre projet) est donc ecartee ici: il "
    "s'agit d'une planche PERIMEE, c'est-a-dire d'une impression anterieure du "
    "meme lot, reimprimee depuis avec d'autres parametres. Le refus reste la "
    "regle: il est toujours recuperable la ou une mauvaise association ecrite "
    "ne l'est pas, et aucun `--overwrite` ne le leve."
)


def _check_printed_identifiers(lot: Mapping[str, Any] | None, reference: Mapping[str, Any]) -> None:
    """Confronter le QR decode aux trois identifiants poses a l'impression.

    Depuis EPIC5-ARB-20, `lots[].template_id`, `lots[].patch_preset_id` et
    `lots[].gamut_map_id` sont ecrits **par l'impression** (story 5.11), avant
    meme qu'un scan existe: la comparaison porte donc sur ce que la chaine
    amont a produit, et le cas est atteignable des le premier scan d'un projet
    normal. Les trois valeurs sont posees a l'impression **et** portees par le
    QR de la planche imprimee, de la meme source unique: en sortie de presse
    elles sont egales par construction, et une inegalite au scan est un signal
    fort.

    Reciproquement, leur egalite est une **confirmation de bout en bout** de la
    chaine impression -> QR -> scan -> manifest, et c'est le seul controle du
    depot qui la ferme.

    Un champ **absent** n'est pas une divergence: c'est un lot ne des planches
    seules, ou imprime avant la story 5.11. La chaine de scan l'**apprend** au
    lieu de sauter la garde (EPIC5-ARB-34), et c'est `_learn_printed_identifiers`
    qui l'ecrit -- apres cette confrontation, jamais a sa place.
    """
    if lot is None:
        return
    for name in PRINTED_IDENTIFIER_FIELDS:
        if name not in lot:
            continue
        persisted = lot[name]
        decoded = reference[name]
        if persisted != decoded:
            raise ScanManifestConflictError(
                f"Conflit de scan sur '{name}' pour le lot "
                f"{reference['lot_id']!r}: le manifest declare "
                f"lots[{reference['lot_id']}].{name}={persisted!r} (pose a "
                f"l'impression) mais le QR de la planche scannee declare "
                f"{name}={decoded!r}. {_STALE_PLATE_HYPOTHESIS} Aucune "
                "ecriture n'a eu lieu"
            )


def _check_lot_attachment(lot: Mapping[str, Any] | None, reference: Mapping[str, Any]) -> None:
    """Refuser un `lot_id` deja rattache a un autre rush.

    C'est la forme la plus directe de R12: le meme identifiant de lot pointant
    sur deux rushs differents rend le projet aval indechiffrable, et l'ecrire
    est irrattrapable.
    """
    if lot is None:
        return
    persisted_rush = lot.get("rush_id")
    if persisted_rush is not None and persisted_rush != reference["rush_id"]:
        raise ScanManifestConflictError(
            f"Conflit de scan sur le rattachement du lot {reference['lot_id']!r}: "
            f"le manifest le rattache a rush_id={persisted_rush!r} mais le QR de "
            f"la planche scannee declare rush_id={reference['rush_id']!r}. La "
            "planche est etrangere a ce lot, ou le lot a ete rattache a un autre "
            "rush. Aucune ecriture n'a eu lieu"
        )


def _check_page_count(section: Mapping[str, Any] | None, reference: Mapping[str, Any]) -> None:
    """Refuser un `page_count` different de celui qu'une passe anterieure a declare.

    La comparaison n'a lieu que si la section `reconstruction` decrit **le meme
    lot**: unique par document, elle peut decrire un autre lot scanne
    entre-temps, et confronter deux lots l'un a l'autre inventerait un conflit.
    """
    if section is None:
        return
    persisted = section.get("page_count")
    if persisted is None or persisted == reference["page_count"]:
        return
    raise ScanManifestConflictError(
        f"Conflit de scan sur le nombre de pages du lot {reference['lot_id']!r}: "
        f"le manifest declare reconstruction.page_count={persisted!r} mais le QR "
        f"de la planche scannee declare page_count={reference['page_count']!r}. "
        f"{_STALE_PLATE_HYPOTHESIS} Aucune ecriture n'a eu lieu"
    )


# --------------------------------------------------------------------------
# Lecture du rapport de la story 5.6
# --------------------------------------------------------------------------


_REPORT_ATTRIBUTES: tuple[str, ...] = (
    "lot_id",
    "rush_id",
    "output_dir",
    "expected_frame_count",
    "synthetic_frame_count",
    "observed_frame_count",
    "overwritten_files",
    "preexisting_frames",
    "missing_frames",
    "frames",
    "color_calibration_status",
)

#: Champs du rapport de 5.6 dont ce module ne fait qu'iterer le contenu. Leur
#: presence est verifiee par `_REPORT_ATTRIBUTES`; leur **iterabilite** ne
#: l'etait pas, si bien qu'un `None` glisse a la place d'une des trois listes
#: sortait en `TypeError` nue -- hors de la hierarchie que la CLI capture, et
#: precisement le mode de panne que la docstring de `_read_report` revendique de
#: fermer (revue couche 2, mineure 3).
_REPORT_NAME_SEQUENCES: tuple[str, ...] = (
    "overwritten_files",
    "preexisting_frames",
    "missing_frames",
)


def _read_report(report: Any) -> dict:
    """Lire le rapport de 5.6 en typage structurel, ou echouer en le nommant.

    Un `getattr` manquant sortirait en `AttributeError` nue, hors de la
    hierarchie que la CLI capture -- exactement le mode de panne que la revue
    de 5.11 a ferme pour le manifest tronque.
    """
    missing = [name for name in _REPORT_ATTRIBUTES if not hasattr(report, name)]
    if missing:
        raise ScanPersistenceError(
            "Le rapport de sortie de frames ne porte pas les champs attendus "
            f"(manquants: {missing}). Aucune ecriture n'a eu lieu"
        )
    values = {name: getattr(report, name) for name in _REPORT_ATTRIBUTES}
    for name in ("synthetic_frame_count", "observed_frame_count"):
        if not is_strict_int(values[name]) or values[name] < 0:
            raise ScanPersistenceError(
                f"Cardinal '{name}' invalide au rapport de sortie: "
                f"{values[name]!r}. Un entier positif ou nul est attendu"
            )
    expected = values["expected_frame_count"]
    if expected is not None and (not is_strict_int(expected) or expected < 0):
        raise ScanPersistenceError(
            f"Cardinal attendu invalide au rapport de sortie: {expected!r}. Un "
            "entier positif ou nul, ou `None` quand il est indeterminable"
        )
    for name in _REPORT_NAME_SEQUENCES:
        entries = values[name]
        if not isinstance(entries, (list, tuple, set, frozenset)) or any(
            not isinstance(entry, str) for entry in entries
        ):
            raise ScanPersistenceError(
                f"Champ '{name}' invalide au rapport de sortie: {entries!r}. Une "
                "sequence de noms de fichiers est attendue"
            )
    if not isinstance(values["frames"], (list, tuple)):
        raise ScanPersistenceError(
            f"Champ 'frames' invalide au rapport de sortie: {values['frames']!r}. "
            "Une sequence d'entrees de frame est attendue"
        )
    for frame in values["frames"]:
        absent = [
            name
            for name in ("slot_index", "filename", "synthetic", "synthetic_reason")
            if not hasattr(frame, name)
        ]
        if absent:
            raise ScanPersistenceError(
                "Une frame du rapport de sortie ne porte pas les champs attendus "
                f"(manquants: {absent}). Aucune ecriture n'a eu lieu"
            )
        if not is_strict_int(frame.slot_index) or frame.slot_index < 0:
            raise ScanPersistenceError(
                f"slot_index invalide au rapport de sortie: {frame.slot_index!r}. "
                "Un entier base zero est attendu, et jamais un booleen"
            )
        if not isinstance(frame.filename, str) or not frame.filename:
            raise ScanPersistenceError(
                f"filename invalide au rapport de sortie: {frame.filename!r}. "
                "Le nom de fichier est l'identite sur laquelle le registre des "
                "mires est tenu (EPIC5-ARB-33): il ne peut pas etre vide"
            )
    return values


def _frames_by_slot(report_values: Mapping[str, Any]) -> dict[int, Any]:
    """Frames ecrites par **cette** passe, indexees par `slot_index`."""
    table: dict[int, Any] = {}
    for frame in report_values["frames"]:
        table[frame.slot_index] = frame
    return table


# --------------------------------------------------------------------------
# Regle de cumul (EPIC5-ARB-32, puis EPIC5-ARB-33)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class _Cardinals:
    """Les deux cardinaux du lot, et le registre dont ils sont derives."""

    reconstructed: int
    synthetic_frames: tuple[str, ...]
    findings: tuple[str, ...]

    @property
    def synthetic(self) -> int:
        """Cardinal du registre, calcule en **un seul endroit**.

        `synthetic_frame_count` vaut exactement `len(synthetic_frames)`: deux
        porteurs d'une meme verite, exception **deliberee** d'EPIC5-ARB-33 (la
        liste est le registre, l'entier son cardinal, et l'AC 7 exige qu'un lot
        portant des mires soit identifiable par une seule lecture d'entier). La
        contrepartie tenue ici: un seul point de calcul, et un test d'invariant
        qui interdit aux deux de diverger.
        """
        return len(self.synthetic_frames)


def _accumulate_cardinals(
    *,
    report_values: Mapping[str, Any],
    prior_synthetic_names: set[str],
) -> _Cardinals:
    """Cumuler la nature des frames du **lot** par algebre d'ensembles.

    EPIC5-ARB-33 remplace les clauses 3 et 4 d'EPIC5-ARB-32. Le cumul
    d'origine etait une arithmetique d'entiers -- « precedentes + ecrites -
    remplacees » --, et une addition ne sait pas qu'une mire reecrite a
    l'identique est *la meme* mire: relancer `scan --overwrite` sans rien
    changer sur un lot a 2 reelles / 2 mires le faisait passer a 0 / 4, en code
    `0` et avec le mot « succes ». La nature d'une frame est une propriete **de
    cette frame**: elle ne se cumule que par ensemble.

    En notant `S_prec` le registre `lots[].synthetic_frames` du manifest
    precedent (vide a defaut):

    * ``ecrites_reelles`` = les frames que cette passe a ecrites et qui portent
      l'image du film;
    * ``ecrites_mires`` = les frames de remplacement que cette passe a ecrites;
    * ``presentes`` = les fichiers conformes reellement presents dans le
      dossier apres la passe -- ce que cette passe a ecrit et qui n'a pas
      disparu, plus ce que le dossier portait deja
      (``preexisting_frames``). Invariant verifie ici et non suppose:
      ``len(presentes) == observed_frame_count``;
    * ``S`` = ``((S_prec - ecrites_reelles) | ecrites_mires) & presentes``.

    Chaque terme repond a un mode de panne mesure: l'intersection avec
    ``presentes`` elague les mires effacees du dossier hors de l'outil; la
    soustraction de ``ecrites_reelles`` est le gain de l'AC 10 -- une mire
    remplacee par une vraie frame cesse d'etre une mire, y compris quand un
    autre lot a ete scanne entre les deux passes; l'union avec ``ecrites_mires``
    est **idempotente par construction**, donc reecrire la meme mire ne la
    compte pas deux fois. Aucune notion de « remplacees » n'est plus
    necessaire, et aucune lecture de la section `reconstruction` non plus.

    Puis ``reconstructed = observed_frame_count - len(S)``, qui est un
    complement d'ensemble et ne peut donc etre ni negatif ni superieur au
    nombre de fichiers presents: le recadrage d'antan -- et le constat qui
    l'accompagnait -- n'ont plus de producteur et ont ete retires.
    """
    findings: list[str] = []
    observed = report_values["observed_frame_count"]
    written_real = {
        frame.filename for frame in report_values["frames"] if not frame.synthetic
    }
    written_synthetic = {
        frame.filename for frame in report_values["frames"] if frame.synthetic
    }
    missing = set(report_values["missing_frames"])
    present = (written_real | written_synthetic) - missing
    present |= set(report_values["preexisting_frames"])

    if len(present) != observed:
        # Le rapport de 5.6 est lu en typage structurel: cette egalite est une
        # propriete de son producteur, pas une hypothese sur son appelant. La
        # verifier ici est ce qui empeche un rapport incoherent de produire
        # deux cardinaux qui ne decrivent aucun dossier reel.
        raise ScanPersistenceError(
            "Rapport de sortie incoherent: il declare "
            f"observed_frame_count={observed} pour {len(present)} fichier(s) "
            "reellement nommes (frames ecrites non disparues, plus frames "
            "preexistantes). Les deux cardinaux du lot ne peuvent pas se "
            "deriver d'un dossier que le rapport decrit de deux facons"
        )

    synthetic = ((prior_synthetic_names - written_real) | written_synthetic) & present

    if prior_synthetic_names & written_real:
        findings.append(SCAN_SYNTHETIC_REPLACED_BY_REAL)
    # Une mire ecrite par-dessus un fichier qui existait et qui n'etait pas une
    # mire: c'est la degradation qu'EPIC5-ARB-34 fait refuser **avant**
    # l'ecriture. Si elle est arrivee jusqu'ici, l'operateur a leve le refus
    # avec `--overwrite`; le manifest enregistre alors le reel et le **nomme**.
    degraded = (written_synthetic & set(report_values["overwritten_files"])) - (
        prior_synthetic_names
    )
    if degraded:
        findings.append(SCAN_REAL_FRAMES_DEGRADED)

    return _Cardinals(
        reconstructed=observed - len(synthetic),
        synthetic_frames=tuple(sorted(synthetic)),
        findings=tuple(findings),
    )


# --------------------------------------------------------------------------
# Marquage des frames et declaration de completude
# --------------------------------------------------------------------------


def _scan_frame_filename(reference: Mapping[str, Any], frame_timecode: Any) -> str:
    """Nom de fichier de la frame d'un slot, par la recette **unique** du depot.

    `io.naming.build_scan_frame_filename` est la seule ecriture de la
    convention `scan_<rush>_<fps-court>_<timecode-assaini>.tiff`; la reconstruire
    ici en ferait une seconde, qui divergerait au premier ajustement. C'est ce
    nom -- et non l'index de slot -- qui fait l'identite d'une frame dans le
    registre durable des mires (EPIC5-ARB-33), parce que c'est ce que le dossier
    rend et ce que le rapport de 5.6 nomme.

    `NamingError` derive de `ValueError` et sortirait donc hors de la hierarchie
    que la CLI capture: on la ramene dans la bonne famille. Le cas est
    atteignable par un appelant direct de l'API, dont les payloads ne sont pas
    forcement passes par `io.payload`.
    """
    try:
        return naming.build_scan_frame_filename(
            reference["rush_id"], reference["fps_target"], frame_timecode
        )
    except naming.NamingError as error:
        raise ScanPersistenceError(
            f"Timecode de slot inexploitable ({frame_timecode!r}): {error}. Le "
            "nom de fichier est l'identite sur laquelle le registre des mires "
            "est tenu, et il ne se devine pas. Le manifest precedent est intact"
        ) from error


def _mark_slots(
    slots: list[dict],
    *,
    report_values: Mapping[str, Any],
    reference: Mapping[str, Any],
    synthetic_names: frozenset[str],
    prior_section: Mapping[str, Any] | None,
) -> None:
    """Poser `synthetic` sur **chaque** slot, et `synthetic_reason` sur les mires.

    `synthetic` est **explicite**, y compris a `false`: un champ absent se
    relit « vraie frame », le faux positif silencieux qu'EPIC5-ARB-8 ecarte.
    `synthetic_reason` est present **si et seulement si** `synthetic` vaut
    `true`, jamais `null`, jamais une chaine libre -- le vocabulaire ferme est
    celui **exporte par 5.6**, importe et jamais recopie ni etendu ici.

    La nature d'un slot ne se decide plus ici: elle se **lit** dans le registre
    que le cumul vient d'etablir (EPIC5-ARB-33), par le nom de fichier du slot.
    Un seul point de decision pour les deux porteurs -- le detail par frame et
    les deux cardinaux --, donc aucune facon pour eux de se contredire dans le
    meme document, ce qui etait le cas mesure en revue.

    Le **motif**, lui, n'est pas la nature: il vient de la frame que cette passe
    a ecrite, ou a defaut de ce que le document precedent declarait pour ce slot
    quand sa section decrit le meme lot. C'est la seule chose que le registre ne
    porte pas, et la seule lecture de `reconstruction.slots[]` qui subsiste.
    """
    from ..scan_output_frames import validate_synthetic_reason

    frames_by_slot = _frames_by_slot(report_values)
    for slot in slots:
        slot_index = slot["slot_index"]
        frame = frames_by_slot.get(slot_index)
        filename = _scan_frame_filename(reference, slot.get("frame_timecode"))
        synthetic = filename in synthetic_names
        if frame is not None and frame.synthetic:
            reason = frame.synthetic_reason
        else:
            reason = _prior_reason(prior_section, slot_index)
        # Les slots viennent d'etre construits par `reconstruct_project_manifest`
        # et ne portent que `slot_index` et `frame_timecode`: le motif ne s'ajoute
        # que sur cette branche, donc l'invariant « present si et seulement si
        # `synthetic` vaut `true` » tient par construction. La campagne de
        # mutation l'a montre en rendant un `slot.pop("synthetic_reason", None)`
        # prealable **inobservable** -- du code mort, retire plutot que teste.
        slot["synthetic"] = synthetic
        if synthetic:
            if reason is None:
                raise ScanPersistenceError(
                    f"Frame de remplacement sans motif au slot {slot_index}: le "
                    "marquage synthetique exige un motif du vocabulaire ferme de "
                    "la story 5.6. Le manifest precedent est intact"
                )
            try:
                slot["synthetic_reason"] = validate_synthetic_reason(reason)
            except ValueError as error:
                # `validate_synthetic_reason` leve un `ValueError` **nu**, et il
                # est appele ici sur une valeur relue du document precedent --
                # donc editable a la main -- et non sur une valeur produite par
                # la passe. La hierarchie du module promet a la CLI un seul
                # `except` a tenir: on l'y ramene, sans maquiller le motif.
                raise ScanPersistenceError(
                    f"Motif de frame de remplacement invalide au slot "
                    f"{slot_index}, relu du {MANIFEST_FILENAME} present: "
                    f"{error}. Le manifest precedent est intact"
                ) from error


def _prior_reason(section: Mapping[str, Any] | None, slot_index: int) -> str | None:
    """Motif de remplacement declare par le document precedent pour ce slot."""
    for slot in (section or {}).get("slots", []) or []:
        if isinstance(slot, dict) and slot.get("slot_index") == slot_index:
            reason = slot.get("synthetic_reason")
            return reason if isinstance(reason, str) else None
    return None


#: Champs qu'un resultat de calibration doit porter pour que ce module le projette.
#: **Typage structurel**, comme pour `output_report`: lier `io/` a
#: `color_calibration` ferait descendre numpy et OpenCV dans la couche de
#: persistance. Le prix assume est le meme -- un test d'integration contre le vrai
#: producteur, sinon un renommage de champ passe inapercu (action item 3 de la retro
#: Epic 4). L'enumeration est ce qui transforme ce prix en refus explicite.
_CALIBRATION_REQUIRED_ATTRIBUTES: tuple[str, ...] = (
    "status",
    "correction_source",
    "correction_source_page_id",
    "correction_form_id",
    "divergence",
    # `EPIC5-ARB-78`: depuis que le budget de distorsion est publie et non plus oppose a
    # la page, `correction_provenance_summary` lit cet attribut a chaque projection. Sans
    # lui dans l'enumeration, un resultat qui ne le porte pas leverait une `AttributeError`
    # au fond de la projection au lieu d'un refus nomme -- c'est exactement le prix que
    # cette enumeration existe pour transformer en refus explicite.
    "acceptance",
    # Meme motif, meme date, pour le meme finding de revue: `correction_provenance_summary`
    # lit aussi `not_applied_reason` (le choix `--cc off`, distinct d'un echec) a chaque
    # projection. Absent d'ici, il levait la meme `AttributeError` nue au fond de la
    # projection sur tout resultat qui ne le porterait pas -- deuxieme passe de revue,
    # 2026-08-14.
    "not_applied_reason",
    # **Troisieme et quatrieme occurrences du meme defaut, fermees le 2026-08-17** (revue
    # de la story 5.22, trouve independamment par les trois couches). `correction_chain_id`
    # et `failure_reason` sont lus en acces nu par `correction_provenance_summary` et
    # manquaient tous deux ici -- le second depuis 5.19, sans qu'aucune des trois passes
    # de revue precedentes ne le voie.
    #
    # Ce qui a fait durer le defaut n'est pas l'inattention: c'est que le test qui gardait
    # l'enumeration mesurait les champs **publies** par un fixture, et que ces trois-la
    # sont publies **sous condition** (`if result.<champ> is not None`). Un fixture qui
    # ne les porte pas ne les publie pas, donc le test ne les voyait pas manquer -- il
    # etait vert pour la raison meme qui rendait le defaut possible. Le garde-fou est
    # depuis **derive** de ce que la projection lit reellement, par lecture d'AST et non
    # par un fixture: `test_calibration_provenance_wiring.py`,
    # `test_lenumeration_couvre_tout_attribut_que_la_projection_lit`. Recopier une liste a
    # la main trois fois de suite et se tromper trois fois est un defaut de conception du
    # garde-fou, pas un oubli.
    "correction_chain_id",
    "failure_reason",
    # Le verdict relu du fichier de profil (bloquant `C2` de la meme revue), publie sous
    # sa cle propre par la projection: meme regime conditionnel que les trois ci-dessus,
    # donc meme exigence d'etre enumere ici.
    "chain_profile_acceptance",
    # L'ecart brut a brut de la story 5.23 (`EPIC5-ARB-82`), lu en acces nu par
    # `correction_provenance_summary` comme les six precedents. Enumere **dans la meme
    # story que son ajout** plutot qu'a la revue suivante: c'est la seule facon connue de
    # ne pas rejouer le defaut que ce bloc de commentaires documente quatre fois.
    "raw_divergence",
)


def _calibration_entry(calibration: Any) -> dict:
    """Projection manifest d'un resultat de calibration, **par son producteur**.

    La forme est celle que `color_calibration.correction_provenance_summary` declare,
    et elle est **appelee** plutot que recopiee: la story qui produit la donnee possede
    sa forme, celle qui possede le manifest en possede l'ecriture. Une seconde
    redaction ici divergerait a la premiere evolution du bloc de divergence, et le
    symptome serait un manifest qui decrit une correction avec les champs d'une autre.

    L'import est **local**: `io/` ne doit pas dependre de `color_calibration` a
    l'import, sans quoi la couche de persistance tirerait numpy et OpenCV. Le typage
    structurel de `ScanRecord` reste donc la regle, et cet appel n'a lieu que quand un
    resultat est reellement present.
    """
    from ..color_calibration import correction_provenance_summary

    return correction_provenance_summary(calibration)


#: Cle de la section `color` **niveau projet** qui liste les chaines de scan dont un
#: profil de calibration a reellement corrige au moins un lot de ce projet (story 5.22,
#: `EPIC5-ARB-81`). Le schema v2 declare `additionalProperties: true` sur cette section,
#: donc le champ s'y ajoute sans revision de version.
CALIBRATION_CHAINS_KEY = "calibration_chain_ids"


def _record_calibration_chains(color_section: dict,
                               page_calibrations: tuple[tuple[int, Any], ...]) -> None:
    """Consigner au projet les chaines qui l'ont **reellement** corrige. Story 5.22.

    Le champ est **une liste triee et monotone**, et chacun de ces trois mots repond a
    une objection:

    * **liste** et non valeur unique, parce qu'un projet peut porter des lots numerises
      sur plusieurs chaines -- deux scanners, ou le meme a deux reglages. Un champ
      scalaire aurait fait ecrire la derniere chaine par-dessus la precedente, et le
      projet aurait declare une seule chaine la ou deux ont servi;
    * **triee**, pour que deux projets ayant vu les memes chaines dans un ordre
      different rendent le meme document -- l'ordre de scan n'est pas une donnee;
    * **monotone**, meme regle que `color_calibration_status` juste au-dessus: la valeur
      transportee est celle d'**une passe**, et une passe connait un seul lot. L'ecrire
      par-dessus ferait desapprendre les chaines des lots deja scannes.

    Le champ est **derive des resultats de calibration deja recus**, jamais d'un
    parametre supplementaire de `ScanRecord`: un second emplacement pour le meme fait,
    ce sont deux verites, et celle-ci pourrait diverger de la provenance ecrite page par
    page. Une chaine n'y entre que si elle a corrige quelque chose -- un profil
    charge puis dont toutes les planches divergent n'a rien corrige et ne s'y inscrit
    pas, exactement comme le statut ne devient pas `applied`.
    """
    chaines = {
        resultat.correction_chain_id
        for _index, resultat in page_calibrations
        if getattr(resultat, "correction_chain_id", None) is not None
        and getattr(resultat, "profile", None) is not None
    }
    if not chaines:
        return
    connues = color_section.get(CALIBRATION_CHAINS_KEY)
    if isinstance(connues, list):
        chaines.update(str(valeur) for valeur in connues)
    color_section[CALIBRATION_CHAINS_KEY] = sorted(chaines)


def _build_calibration_results(
    slots: list[dict],
    *,
    page_payloads: tuple[dict, ...],
    page_calibrations: tuple[tuple[int, Any], ...] = (),
    divergence_bypass_requested: bool = False,
) -> list[dict]:
    """Resultats de calibration par page, dans la forme declaree par 5.4b.

    Ce module **transporte** les statuts, il n'en calcule aucun et n'invente ni
    metrique, ni dispersion, ni verdict d'ecretage. Ecrire
    `clipping: {detected: false}` sans avoir mesure serait affirmer « aucun
    ecretage detecte » la ou la verite est « rien n'a ete mesure » -- exactement
    le faux succes que R12 decrit, applique a la couleur.

    **Une entree ne porte que le statut que sa page a produit** (`EPIC5-ARB-69`).
    Le statut de lot passe en argument ne descend donc plus sur une page dont
    aucun resultat ne remonte: une telle page vaut `not_applied`, jamais
    `failed` et jamais `applied`. La revue de 5.19 a mesure les deux dommages de
    l'heritage, et ils sont symetriques:

    * une page de calibration illisible faisait declarer `failed` a deux
      planches **intactes**, sur lesquelles `calibrate_page` n'avait pas ete
      appele une seule fois, et sans motif: l'operateur allait rescanner les
      mauvaises feuilles. C'est le defaut que 5.19 avait ferme pour la page de
      calibration elle-meme, laisse ouvert dans son sens symetrique ;
    * une feuille cornee dans un lot corrige heritait de `applied` et faisait
      lever la garde de coherence ci-dessous -- huit frames sur le disque, aucun
      manifest, pour une seule feuille abimee.

    Regle de coherence tenue ici (AC 7 de 5.16): un resultat ne peut pas valoir
    `applied` pour une page qui n'a produit que des frames synthetiques, la mire
    n'etant pas le contenu source et etant achromatique par construction. Elle
    se confronte au statut **de la page**, seul statut que cette page a produit:
    confrontee au statut de lot, elle faisait lever un refus declenche par la
    panne d'une **autre** feuille, ce qui est le contraire de son objet.
    """
    calibrations = dict(page_calibrations)
    inconnues = sorted(
        index for index in calibrations
        if index not in {payload["page_index"] for payload in page_payloads}
    )
    if inconnues:
        # Un resultat de calibration pour une page que le lot ne declare pas est une
        # **erreur d'appariement**, pas une donnee a ignorer: l'inscrire ailleurs ou le
        # jeter en silence sont les deux facons de rendre le document faux. C'est la
        # forme que prend ici le risque R12, applique a la couleur.
        raise ScanPersistenceError(
            f"Resultat(s) de calibration pour des pages absentes du lot: {inconnues}. "
            f"Pages declarees: {sorted({p['page_index'] for p in page_payloads})}. Le "
            "manifest precedent est intact"
        )
    synthetic_by_slot = {slot["slot_index"]: slot["synthetic"] for slot in slots}
    # Dedoublonnage par `page_index`, comme `reconstruct_project_manifest` le
    # fait pour les payloads: sans lui, deux payloads identiques -- que la
    # fonction appelee accepte explicitement (« identical duplicates are fine
    # (idempotent rescans) ») -- produisaient deux entrees pour la meme page et
    # cassaient l'idempotence du document.
    unique_payloads = {payload["page_index"]: payload for payload in page_payloads}
    results: list[dict] = []
    for page_index in sorted(unique_payloads):
        payload = unique_payloads[page_index]
        page_slots = [slot["slot_index"] for slot in payload["slots"]]
        known = [index for index in page_slots if index in synthetic_by_slot]
        all_synthetic = bool(known) and all(synthetic_by_slot[index] for index in known)
        calibration = calibrations.get(page_index)
        # `EPIC5-ARB-69`: le statut de lot ne descend pas sur une page qui n'a rien
        # produit. Une page sans resultat vaut `not_applied` -- « on n'a rien mesure sur
        # celle-ci » --, ce qui est exactement ce que le document doit dire d'elle. Le
        # `failed` d'un lot vit au niveau du lot, avec son motif.
        page_status = (
            calibration.status if calibration is not None
            else CALIBRATION_NOT_APPLIED
        )
        if page_status == "applied" and all_synthetic:
            raise ScanPersistenceError(
                f"Resultat de calibration incoherent pour la page "
                f"{page_index}: le statut 'applied' est declare alors "
                "que toutes ses frames sont des mires de remplacement. Une mire "
                "n'est pas le contenu source et est achromatique par "
                "construction. Le manifest precedent est intact"
            )
        entry = {"page_index": page_index, "status": page_status}
        if calibration is not None:
            # Le statut de la page vient du **resultat**: c'est la calibration qui sait
            # si elle a ete appliquee.
            provenance = _calibration_entry(calibration)
            # Aucun champ nouveau ne **redefinit** un champ deja declare: le schema de
            # 5.7 ouvre `additionalProperties` sur ces entrees, ce qui autorise l'ajout
            # et non l'ecrasement. Un `status` reecrit par la provenance ferait dire au
            # document autre chose que ce que la page a produit.
            collisions = sorted(set(provenance) & set(entry) - {"status"})
            if collisions:
                raise ScanPersistenceError(
                    f"La provenance de correction de la page {page_index} redefinirait "
                    f"le(s) champ(s) deja declare(s) {collisions}. Le manifest "
                    "precedent est intact"
                )
            entry.update(provenance)
            _check_bypass_was_requested(
                page_index, calibration, divergence_bypass_requested)
        results.append(entry)
    return results


def _write_lot_calibration_status(
    lot: dict, existing_lot: Mapping[str, Any] | None, status: str, *,
    wrote_frames: bool,
) -> None:
    """Poser sur le **lot** le statut de correction que la passe a mesure sur lui.

    `EPIC5-ARB-68`. Le champ existe parce qu'`encode` produit un master **par lot** et
    lisait un champ de portee **projet**: sur le cas nominal de la v2.1 -- deux lots du
    meme rush a deux cadences, un seul avec sa page de calibration --, le master du lot
    **non corrige** s'annoncait « correction active appliquee aux pixels ». C'est le
    faux succes de R12, ecrit dans le seul endroit ou l'operateur le lit.

    Deux clauses, et la seconde est celle qui ferme le desapprentissage:

    * le champ n'est ecrit que s'il **dit quelque chose** (`applied` ou `failed`). Un lot
      qui n'a jamais eu de page de calibration ne gagne donc aucun champ, et c'est ce qui
      preserve le filet octet a octet de l'AC 12: le chemin non corrige rend le meme
      document qu'avant la story. Son absence se lit `not_applied`, cote lecteur ;
    * il est **corrige s'il existe deja**, y compris vers le bas. Une passe qui rescanne
      le meme lot sans sa page de calibration ecrase donc `applied` par `not_applied`, et
      le document cesse de mentir sur des frames qui viennent d'etre reecrites non
      corrigees.

    **Le champ decrit les pixels qui sont sur le disque, donc une passe qui n'ecrit aucune
    frame ne le touche pas** (finding `F1` de la revue de la passe de correction). La
    premiere redaction disait « une passe connait ce lot entierement »: c'etait faux, et
    mesure faux. Il suffit qu'aucune mire ne soit *formable* --
    `SYNTHETIC_FRAME_SHAPE_INDETERMINABLE`, c'est-a-dire quand **toutes** les planches du
    lot echouent a la geometrie -- pour qu'une passe ecrive zero fichier tout en declarant
    un statut. Le regime mesure: passe 1 nominale (huit frames corrigees, lot `applied`),
    puis passe 2 du meme lot avec deux planches cornees et sa page de calibration intacte
    -- zero frame ecrite, les huit frames de la passe 1 **octet pour octet** sur le
    disque, et le champ redescendait a `not_applied`. Le recapitulatif d'`encode` disait
    alors trois faussetes en une ligne, dont « le lot ne porte pas de page de calibration
    lue » d'une feuille qui etait la, lisible, et sur les 130 pastilles de laquelle la
    correction venait d'etre ajustee -- mot pour mot le dommage qu'`EPIC5-ARB-70` ferme.

    La condition porte sur les **deux** clauses et non sur la seule descente: une passe qui
    n'a rien ecrit n'a rien a dire des pixels, dans un sens comme dans l'autre.
    """
    if not wrote_frames:
        return
    if status != CALIBRATION_NOT_APPLIED:
        lot["color_calibration_status"] = status
        return
    if (existing_lot or {}).get("color_calibration_status") is not None:
        # Le champ existe, la passe a **reecrit les frames**, et elle a mesure qu'il n'y a
        # pas de correction: c'est une mesure, pas une ignorance, et elle doit descendre.
        lot["color_calibration_status"] = status


def _check_bypass_was_requested(
    page_index: int, calibration: Any, requested: bool
) -> None:
    """Un contournement **constate** exige une demande explicite. AC 15 de 5.16.

    C'est le symetrique de la regle que la moitie couleur a posee -- « le drapeau se
    declare sur le **constat** et non sur la demande »: le manifest decrit ce qui s'est
    passe, donc une page qu'on demande de contourner et qui ne diverge pas n'est pas
    marquee contournee. Ici on ferme l'autre cote, et sans lui l'AC 15 resterait une
    phrase: « explicite, jamais un repli automatique » n'est verifiable que si un repli
    **automatique** produit un document different d'une demande explicite. Sans cette
    garde, les deux produisent le meme.

    Le refus nomme **la page** et le drapeau, jamais le lot: `EPIC5-ARB-57` veut qu'une
    feuille se rescanne seule.
    """
    divergence = getattr(calibration, "divergence", None)
    if divergence is None or not getattr(divergence, "bypassed", False):
        return
    if requested:
        return
    from ..color_calibration import DIVERGENCE_BYPASS_FLAG

    raise ScanPersistenceError(
        f"La page {page_index} porte un contournement de la garde de divergence "
        f"(ecart mesure {getattr(divergence, 'excess_residual_de76', None)!r} dE76 "
        f"contre {getattr(divergence, 'threshold_de76', None)!r} enregistres) alors "
        f"que {DIVERGENCE_BYPASS_FLAG} n'a pas ete demande. Un contournement est un "
        "geste **explicite** de l'operateur et jamais un repli automatique: sans cette "
        "garde, les deux ecriraient le meme document. Le manifest precedent est intact"
    )


# --------------------------------------------------------------------------
# Preservation des sections de tete (AC 4)
# --------------------------------------------------------------------------

#: Sections que `reconstruct_project_manifest` repose vides ou reduites et qui
#: doivent survivre a un enrichissement. `rushes` et `lots` n'y figurent pas:
#: `_merge_entries` les protege deja, champ par champ.
_HEAD_SECTIONS: tuple[str, ...] = ("artifacts", "color", "video")


def preserver_les_sections_de_tete(manifest: dict,
                                   existing: Mapping[str, Any] | None) -> None:
    """Rendre au document ce que la reconstruction lui avait retire.

    **Publiee le 2026-08-28** (`EPIC7-ARB-101`) : l'adoption d'un lot etranger
    ecrit le manifest par `reconstruct_project_manifest` sans passer par
    `persist_scan`, et perdait donc exactement ce que cette fonction protege.
    Mesure sur le projet reel : `artifacts` et `video` ressortaient vides apres
    adoption. En ecrire une seconde version chez l'appelant aurait recree le
    defaut a chaque section ajoutee au contrat -- il n'y en a qu'une, et elle
    est ici.

    Le piege majeur ne se joue **pas** dans `_merge_entries`, qui fusionne deja
    champ par champ, mais dans les sections de tete que
    `reconstruct_project_manifest` repose vides: un enrichissement perdait sans
    un mot `artifacts.frames_dir`, `artifacts.outputs_dir`, `video.codec_target`,
    les huit autres champs de `color` et la cle racine `created`. Le rush n'est
    pas sur la machine: ces mesures ne seront jamais refaites.

    Asymetrie assumee, et c'est la regle de l'AC 4: le scan connait
    **strictement moins** que le manifest d'origine. Ce qu'il apporte prime sur
    la seule cle qu'il connait (`color.target_colorspace`), le reste de
    l'existant est conserve.
    """
    if not existing:
        return
    for section in _HEAD_SECTIONS:
        previous = existing.get(section)
        if not isinstance(previous, dict):
            continue
        manifest[section] = {**previous, **manifest.get(section, {})}
    # Toute cle de racine que la reconstruction ne produit pas -- `created`
    # aujourd'hui, et ce qu'une version ulterieure du contrat y ajoutera --
    # survit. Une cle inconnue du schema fera echouer la validation du
    # temporaire, ce qui est le comportement voulu: un echec nomme plutot
    # qu'une perte silencieuse.
    for key, value in existing.items():
        if key not in manifest:
            manifest[key] = copy.deepcopy(value)


#: L'ancien nom prive, conserve : il est cite par la docstring d'en-tete de ce
#: module et par des bancs. Un alias plutot qu'un second corps -- deux
#: redactions de cette preservation divergeraient, et la divergence se paierait
#: en mesures irrecuperables.
_preserve_head_sections = preserver_les_sections_de_tete


# --------------------------------------------------------------------------
# Couche pure de fusion
# --------------------------------------------------------------------------


def build_scan_manifest(
    existing: Mapping[str, Any] | None, record: ScanRecord
) -> ScanManifestMerge:
    """Fusion **pure**: aucune I/O, aucune horloge, aucun acces disque.

    Le decoupage est celui de `build_extraction_manifest` et de
    `build_pdf_manifest`, et pour la meme raison: l'idempotence octet a octet
    se teste sans toucher au disque. Aucune horodate n'entre au manifest par ce
    chemin -- elle rendrait deux passes identiques distinguables et fermerait
    la seule verification qui prouve qu'un rescan n'a rien detruit.

    **Cette couche ne refuse plus rien de ce qui est deja sur le disque**
    (EPIC5-ARB-34, clause 3). Le refus appartient a `check_scan_conflicts`, qui
    s'execute **avant** l'ecriture des frames, la ou il est encore recuperable.
    Une fois les fichiers ecrits, un manifest qui refuserait d'enregistrer une
    degradation mentirait sur l'etat du projet -- il continuerait de declarer
    reelles des images qui n'existent plus. Les conflits d'identite (AC 5) sont
    neanmoins reverifies ici, parce que cette fonction est publique et qu'un
    appelant direct n'est pas tenu de passer par la garde prealable: ce qu'ils
    protegent est une **mauvaise association ecrite**, pas un fichier detruit.
    """
    existing = _assert_mergeable(existing)

    payloads = list(record.page_payloads)
    report_values = _read_report(record.output_report)

    # La reconstruction fait toute la validation des payloads et rend le
    # document fusionne. Elle est **appelee**, jamais reecrite (AC 1), et rien
    # n'est ecrit sur disque avant `persist_scan`: un refus posterieur laisse
    # donc le `project.json` precedent strictement intact.
    manifest = reconstruct_project_manifest(
        payloads,
        existing_manifest=dict(existing) if existing else None,
        lot_state=SCAN_LOT_STATE,
        origin=ORIGIN_SCAN,
    )
    section = manifest["reconstruction"]
    lot_id = section["lot_id"]
    reference = _reference_from_section(section, _find_lot(manifest, lot_id))
    _assert_report_describes_the_same_lot(report_values, reference)

    existing_lot = _find_lot(existing, lot_id)
    prior_section = _prior_reconstruction(existing, lot_id)

    _check_lot_attachment(existing_lot, reference)
    _check_printed_identifiers(existing_lot, reference)
    _check_page_count(prior_section, reference)

    cardinals = _accumulate_cardinals(
        report_values=report_values,
        prior_synthetic_names=_prior_synthetic_names(existing_lot),
    )

    findings = list(cardinals.findings)

    _mark_slots(
        section["slots"],
        report_values=report_values,
        reference=reference,
        synthetic_names=frozenset(cardinals.synthetic_frames),
        prior_section=prior_section,
    )
    section["scan"] = {
        "scan_dpi": record.scan_dpi,
        "ingest_slug": record.ingest_slug,
        # Tri canonique: deux passes qui presentent les memes pages dans un
        # ordre different doivent rendre le **meme** document, sans quoi
        # l'idempotence octet a octet de l'AC 10 depend de l'ordre de lecture
        # du dossier -- c'est-a-dire du systeme de fichiers de l'operateur.
        "pages": [
            provenance.as_document()
            for provenance in sorted(
                record.pages,
                key=lambda item: (
                    item.read_rank,
                    -1 if item.page_index is None else item.page_index,
                ),
            )
        ],
    }
    section["page_calibration_results"] = _build_calibration_results(
        section["slots"],
        page_payloads=tuple(payloads),
        page_calibrations=tuple(record.page_calibrations),
        divergence_bypass_requested=record.divergence_bypass_requested,
    )

    # `status` n'est **abaisse** qu'apres coup, jamais releve: la reconstruction
    # le calcule sur les seules pages et ne connait pas les frames. Une page
    # presente dont la geometrie a echoue n'entre pas dans `missing_pages` et
    # produit pourtant une mire -- c'est le seul cas ou `missing_pages` vide ne
    # suffit pas (EPIC5-ARB-8, AC 6).
    if cardinals.synthetic > 0:
        section["status"] = "partial"
        findings.append(SCAN_SYNTHETIC_FRAMES_PRESENT)

    lot = _find_lot(manifest, lot_id)
    lot["output_frames_dir"] = _relative_posix(
        report_values["output_dir"], "output_frames_dir du lot"
    )
    # Un seul point de calcul pour les deux porteurs (EPIC5-ARB-33): le
    # cardinal est **derive** du registre a l'instant ou le registre est ecrit,
    # jamais recompte ailleurs.
    lot["synthetic_frames"] = list(cardinals.synthetic_frames)
    lot["synthetic_frame_count"] = len(lot["synthetic_frames"])
    lot["reconstructed_frame_count"] = cardinals.reconstructed
    # L'historique DURABLE du lot (`EPIC11-ARB-109`), pose au meme endroit que
    # les autres porteurs qui survivent au scan d'un AUTRE lot.
    _fusionner_l_historique_de_reconstruction(
        lot, existing_lot, section, lot.get("output_frames_dir"))
    _learn_printed_identifiers(lot, reference)
    # `EPIC11-ARB-176`: le chainon manquant. Les payloads sont ceux de CETTE
    # passe -- deja valides par `reconstruct_project_manifest` --, et c'est la
    # seule source du rang: ni le rapport de frames, ni le nom du dossier de
    # scan, ni l'etat de lot ne savent quel TIRAGE a ete pose sur la vitre.
    _apprendre_les_rangs_de_tirage_scannes(lot, payloads)

    expected, expected_findings = _resolve_expected_frame_count(
        existing_lot, report_values["expected_frame_count"]
    )
    findings.extend(expected_findings)
    if expected is not None:
        lot["expected_frame_count"] = expected

    preserver_les_sections_de_tete(manifest, existing)
    _write_lot_calibration_status(
        lot, existing_lot, report_values["color_calibration_status"],
        # « Cette passe a-t-elle ecrit au moins une frame de ce lot ? » se lit au rapport
        # de sortie et nulle part ailleurs: c'est lui qui sait ce qui est alle sur le
        # disque. Zero frame ecrite est un regime **atteignable** -- voir la docstring.
        wrote_frames=bool(report_values["frames"]),
    )
    # Le champ **projet** est monotone, et il est desormais *informatif*
    # (`EPIC5-ARB-68`): il dit « au moins un lot de ce projet porte une correction
    # active », ce qui est vrai, utile a la previz, et n'est plus lu par personne pour
    # decider ce qu'un master contient. C'est le champ **de lot** ecrit juste au-dessus
    # qu'`encode` lit.
    #
    # La monotonie reste la bonne regle *pour ce champ-la*: la valeur transportee est
    # celle d'une **passe**, et une passe connait un seul lot. L'ecrire par-dessus
    # faisait retomber a `not_applied` un projet dont un autre lot etait corrige, en
    # silence -- le desapprentissage que l'AC 4 interdit. Un `setdefault` nu, lui,
    # interdisait aussi l'**apprentissage**: il suffisait d'avoir scanne un premier lot
    # sans page de calibration pour figer le champ.
    #
    # Ce qui a change: la non-descente de ce champ n'est plus un mensonge sur un master,
    # parce que le libelle rendu a l'operateur ne s'y appuie plus.
    color_section = manifest.setdefault("color", {})
    if report_values["color_calibration_status"] == CALIBRATION_APPLIED:
        color_section["color_calibration_status"] = CALIBRATION_APPLIED
    else:
        color_section.setdefault(
            "color_calibration_status", report_values["color_calibration_status"]
        )
    _record_calibration_chains(color_section, record.page_calibrations)

    state_written = lot["state"]
    if state_written != SCAN_LOT_STATE:
        findings.append(SCAN_STATE_CONSERVED)

    lot_complete = expected is not None and (
        cardinals.reconstructed == expected and cardinals.synthetic == 0
    )
    if not lot_complete:
        findings.append(SCAN_LOT_INCOMPLETE)
    if _other_lots(manifest, lot_id):
        findings.append(SCAN_OTHER_LOTS_NOT_SCANNED)

    return ScanManifestMerge(
        manifest=manifest,
        lot_id=lot_id,
        state_written=state_written,
        reconstructed_frame_count=cardinals.reconstructed,
        synthetic_frame_count=len(lot["synthetic_frames"]),
        expected_frame_count=expected,
        lot_complete=lot_complete,
        findings=tuple(validate_persistence_code(code) for code in findings),
    )


def _reference_from_section(
    section: Mapping[str, Any], lot: Mapping[str, Any]
) -> dict:
    """Ce que les payloads decodes declarent du lot, en un seul objet.

    Les six valeurs viennent du QR et de lui seul: c'est **la planche** qui
    parle, et les gardes de l'AC 5 confrontent ce discours a ce que le manifest
    declare deja.
    """
    return {
        "lot_id": section["lot_id"],
        "rush_id": lot["rush_id"],
        "fps_target": lot["fps_target"],
        "page_count": section["page_count"],
        "template_id": section["template_id"],
        "patch_preset_id": section["patch_preset_id"],
        "gamut_map_id": section["gamut_map_id"],
    }


def _learn_printed_identifiers(lot: dict, reference: Mapping[str, Any]) -> None:
    """Ecrire les trois identifiants d'impression **absents**, jamais les reecrire.

    EPIC5-ARB-34, repercussion sur l'AC 5. Une garde qui saute les champs
    absents ne garde rien: sur un projet ne des planches seules -- le cas
    central de cette story --, `lots[]` ne portait aucun des trois, et la
    confrontation de `_check_printed_identifiers` ne pouvait structurellement
    pas se declencher. Deux tirages successifs du meme rush passaient alors
    l'un pour l'autre, ce que `_FOREIGN_PLATE_HYPOTHESIS` revendique de
    refuser.

    Ecrire une valeur qu'aucun manifest ne portait est un **apprentissage**:
    la valeur presente, elle, n'est jamais touchee -- la divergence a deja ete
    refusee plus haut, et « le QR fait foi » est precisement le geste qui
    detruit le seul signal de R12.
    """
    for name in PRINTED_IDENTIFIER_FIELDS:
        if name not in lot:
            lot[name] = reference[name]


def _apprendre_les_rangs_de_tirage_scannes(
    lot: dict, payloads: Sequence[Mapping[str, Any]]
) -> None:
    """Ajouter au lot les rangs de tirage LUS AU QR, sans jamais en retirer.

    Le chainon manquant d'`EPIC11-ARB-176`. Le rang traversait deja
    l'impression, le papier et le decodage -- `io.payload.VERSION_RANK_FIELD`
    l'ecrit, `io.payload.payload_version_rank` le relit -- et s'arretait juste
    avant d'etre **ecrit** : la mesure du 2026-09-02 a trouve ce lecteur sans
    aucun site d'appel dans `src/`. C'est ici qu'il en gagne un.

    **Union, jamais ecrasement**, sur le modele exact de
    `_learn_printed_identifiers` : ecrire un rang qu'aucun manifeste ne portait
    est un **apprentissage** ; retirer un rang deja declare serait un
    desapprentissage, et il aurait un effet precis -- rescanner le `v3` d'un lot
    dont le `v1` avait ete scanne rendrait le `v1` a nouveau ecrasable, alors
    que sa feuille est sur un bureau. C'est la regle que ce module tient
    partout : « enrichir ne fait jamais desapprendre ».

    **Trie et dedoublonne**, comme tout tableau que ce module ecrit : `sort_keys`
    canonise les mappings et pas les tableaux, si bien qu'un ordre d'insertion
    porterait l'ordre de lecture du scanner dans un document dont l'idempotence
    est verifiee octet a octet (story 5.7, AC 10).

    Le repli du rang illisible, pose explicitement (AC 7.11c)
    ---------------------------------------------------------
    La liste porte les rangs **effectivement lus**, et rien d'autre. Trois
    situations, que la convention « `v` absent vaut 1 » ne recouvre pas toutes :

    * **le QR ne s'est pas decode.** La page n'a produit aucun payload, donc
      elle n'entre pas dans `payloads` et ne contribue **aucun** rang -- surtout
      pas `1`. C'est la regle `None` n'est pas zero que le depot tient deja
      (`extraction.CriteresIdentiteRush` : « une duree absente stockee `0`
      affirmerait un flux vide la ou la source n'a rien dit »). Ecrire `1` ici
      affirmerait deux faussetes d'un coup : que le tirage d'origine a ete
      scanne -- donc qu'il n'est plus ecrasable alors qu'il n'a peut-etre jamais
      ete imprime -- et que le tirage dont la feuille venait reellement ne l'a
      pas ete. Le fait qu'une page n'ait pas livre son QR n'est pas perdu pour
      autant : il est deja ecrit, par page, en
      `reconstruction.scan.pages[].qr_status` ;
    * **le QR s'est decode, la charge utile ne porte pas le champ.** Elle
      contribue `1`, par `payload_version_rank`, et ce n'est pas un repli : avant
      `EPIC11-ARB-91` le rang n'existait pas, donc toute planche imprimee alors
      **est** le tirage d'origine. Verbatim d'Egan : « les anciens payloads qui
      ne portaient pas de version (2.1) sont tout de meme decodes avec v=1 ».
      C'est le seul cas ou le defaut du payload traverse jusqu'au manifeste, et
      il traverse parce qu'il mesure quelque chose ;
    * **le manifeste ne porte pas la cle.** Il a ete ecrit avant cette story :
      cela veut dire « on ne sait pas quel tirage a ete scanne », jamais « le
      rang 1 l'a ete ». C'est pourquoi la cle n'est **jamais ecrite vide** --
      une liste vide affirmerait « aucun tirage scanne » sur un lot dont l'etat
      dit `scan`, soit deux affirmations contradictoires dans le meme document.
      Le cas est d'ailleurs inatteignable par ce chemin : `ScanRecord` refuse
      une passe sans payload decode.

    **Ce que ce repli NE ferme pas, dit plutot que tu** : un chiffre qui bascule
    dans un QR imprime (`vr: 12` lu `102`) est ramene a `1` par
    `payload_version_rank` -- sa garde de bornes --, et ce module l'ecrit comme
    un vrai rang 1. Le distinguer demanderait une seconde lecture de la
    convention a ce site, ce que le point d'entree unique d'`EPIC11-ARB-91`
    proscrit nommement. C'est une limite declaree, portee en dette, pas un
    defaut silencieux.
    """
    lus: set[int] = set()
    for payload in payloads:
        # UN SEUL point d'entree de la lecture du rang (`EPIC11-ARB-91`) : un
        # `payload.get("version_rank") or 1` ecrit ici serait la convention en
        # deux exemplaires, donc deux occasions de diverger.
        lus.add(payload_version_rank(payload))

    deja = lot.get(SCANNED_VERSION_RANKS_FIELD)
    if isinstance(deja, (list, tuple)):
        for rang in deja:
            # Lecture defensive, comme partout dans ce module : ce qui n'est pas
            # un rang n'est pas une valeur par defaut, c'est une valeur qu'on ne
            # reecrit pas telle quelle dans un document qu'on s'apprete a
            # valider contre le schema.
            if is_strict_int(rang) and RANG_ORIGINE <= rang <= VERSION_RANK_MAX:
                lus.add(rang)

    lot[SCANNED_VERSION_RANKS_FIELD] = sorted(lus)


def _assert_report_describes_the_same_lot(
    report_values: Mapping[str, Any], reference: Mapping[str, Any]
) -> None:
    """Refuser un rapport de frames qui ne parle pas du lot des payloads.

    Les deux entrees viennent de la meme passe et concordent par construction.
    Le jour ou elles ne concordent plus, le manifest declarerait le dossier de
    sortie d'un lot sous l'identite d'un autre: une mauvaise association
    ecrite, et personne pour la rattraper.
    """
    for name in ("lot_id", "rush_id"):
        if report_values[name] != reference[name]:
            raise ScanManifestConflictError(
                f"Le rapport de frames declare {name}={report_values[name]!r} "
                f"mais les payloads decodes declarent {name}={reference[name]!r}. "
                "Les deux entrees d'une meme passe de scan doivent decrire le "
                "meme lot. Aucune ecriture n'a eu lieu"
            )


def _resolve_expected_frame_count(
    existing_lot: Mapping[str, Any] | None, scanned_expected: int | None
) -> tuple[int | None, list[str]]:
    """Cardinal attendu du lot: mesure, conserve, ou pas ecrit du tout.

    Trois cas, et aucun ne devine:

    * indeterminable (la **derniere** page manque, donc le nombre de frames de
      la derniere planche est inconnu): il n'est pas ecrit, jamais remplace par
      un autre cardinal;
    * deja persiste et different: la valeur du manifest est **conservee**. Elle
      vient de l'extraction, qui a compte de vraies frames, la ou le scan ne
      compte que des emplacements de planche -- ce qui a ete mesure une fois ne
      se desapprend pas (AC 4);
    * absent du manifest: le scan l'apporte, c'est le cas du projet reconstruit
      depuis des planches seules.
    """
    findings: list[str] = []
    persisted = (existing_lot or {}).get("expected_frame_count")
    persisted = persisted if is_strict_int(persisted) and persisted > 0 else None

    if scanned_expected is None:
        # Deux situations que le vocabulaire confondait: « le scan ne sait pas
        # et personne ne sait » (rien n'est ecrit) et « le scan ne sait pas mais
        # le manifest sait » (la valeur du manifest est conservee et reecrite).
        # Emettre `CARDINAL_ATTENDU_INDETERMINABLE` dans le second cas faisait
        # dire a la commande « attendu 4 » et « indeterminable » dans la meme
        # sortie, et rendait fausse la docstring de la constante.
        findings.append(
            SCAN_EXPECTED_FRAME_COUNT_INDETERMINABLE
            if persisted is None
            else SCAN_EXPECTED_FRAME_COUNT_CONSERVED
        )
        return persisted, findings
    if persisted is not None and persisted != scanned_expected:
        findings.append(SCAN_EXPECTED_FRAME_COUNT_CONSERVED)
        return persisted, findings
    return scanned_expected, findings


def _other_lots(manifest: Mapping[str, Any], lot_id: Any) -> list[str]:
    """Lots du projet que cette passe n'a pas scannes, pour information."""
    return [
        lot["lot_id"]
        for lot in manifest.get("lots", [])
        if isinstance(lot, dict) and lot.get("lot_id") != lot_id
    ]


# --------------------------------------------------------------------------
# Refus prealable: on refuse AVANT d'ecrire sur le disque (EPIC5-ARB-34)
# --------------------------------------------------------------------------


def _read_manifest_for_guard(project_dir: Path) -> dict | None:
    """Relire le `project.json` present pour les gardes, ou refuser nommement.

    `_load_existing_manifest` rend `None` aussi bien pour « fichier absent »
    que pour « fichier contenant `null` ». Les deux ne sont pas la meme chose:
    l'un est un projet vierge -- le cas central de cette story --, l'autre est
    un `project.json` corrompu, et l'ecraser en silence etait la seule des six
    formes de corruption a ne pas etre refusee.
    """
    manifest_path = project_dir / MANIFEST_FILENAME
    existing = _load_existing_manifest(manifest_path)
    if existing is None and manifest_path.is_file():
        raise ScanPersistenceError(
            f"Le {MANIFEST_FILENAME} present contient `null`: c'est un fichier "
            "corrompu, pas un projet vierge. L'ecraser reviendrait a perdre en "
            "silence ce qu'il portait. Aucune ecriture n'a eu lieu. Restaurer "
            "une copie saine du project.json"
        )
    return existing


def check_scan_conflicts(
    project_dir: str | Path,
    page_payloads,
    *,
    failed_page_indexes=(),
    overwrite: bool = False,
    cible_neuve: bool = False,
) -> None:
    """Refuser **avant** que la moindre frame ne soit ecrite (EPIC5-ARB-34).

    Le defaut mesure: la chaine decodait les QR, ecrivait les frames (5.6),
    **puis** confrontait les identifiants d'impression au manifest (5.7). Sur
    une planche perimee du **meme** lot -- l'une des deux hypotheses que le
    message de refus revendique nommement --, les noms de fichiers sont
    identiques par construction: avec `--overwrite`, les frames legitimes
    etaient donc detruites, puis la commande refusait en annonçant « aucune
    ecriture n'a eu lieu ». Le manifest etait bien intact; les images, non. Le
    refus protegeait la seule chose qui n'avait pas besoin de l'etre.

    Tout ce qui se juge sans le rapport de 5.6 se juge donc ici: la version de
    schema, la forme du document relu, l'etat de lot en place, les gardes
    reutilisees de la reconstruction (`project_id`, liste des rushs,
    `fps_target`), les trois identifiants d'impression, le rattachement de lot
    et le `page_count`.

    S'y ajoute la seule garde qui n'existait nulle part avant: `--overwrite`
    mis a part, **une passe qui remplacerait des vraies frames par des mires se
    refuse** (clause 2). Elle est decidable sans rien ecrire: `failed_page_indexes`
    dit quelles pages ont echoue a la geometrie ou a la decoupe, le registre
    `lots[].synthetic_frames` dit lesquelles des frames deja presentes sont des
    mires, et le dossier dit ce qui existe. C'est la, et la seulement, que
    l'asymetrie de l'AC 10 est realisable: apres l'ecriture, il n'y a plus de
    bonne raison de mentir.

    Ne rend rien: un refus est une exception, jamais un code.
    """
    from ..scan_output_frames import derive_lot_dir_slug

    from . import project_layout
    from .reconstruction import _check_manifest_conflicts

    if not isinstance(overwrite, bool):
        raise ScanPersistenceError(
            f"`overwrite` doit etre un booleen, recu {overwrite!r}."
        )
    payloads = list(page_payloads)
    if not payloads:
        raise ScanPersistenceError(
            "Aucun payload de page decode: il n'y a rien a confronter au "
            "manifest. Aucune ecriture n'a eu lieu"
        )
    project_dir = Path(project_dir)
    existing = _assert_mergeable(_read_manifest_for_guard(project_dir))

    for payload in payloads:
        _validate_page_payload(payload)
    # **Avant toute lecture de l'identite de lot** (story 5.23, AC 10, `EPIC5-ARB-85`):
    # une pile qui mele la page de calibration aux planches d'images ne porte pas une
    # identite de lot, elle en porte une et une absence. `_check_lot_consistency` lisait
    # les dix champs en acces nu sur la premiere page venue et mourait alors en
    # `KeyError` nue -- c'est-a-dire au seul endroit de la chaine de scan ou un refus est
    # encore gratuit, juste avant l'ecriture des frames, et sans rien dire a l'operateur.
    _check_pile_homogene(payloads)
    decoded = _check_lot_consistency(payloads)
    _check_manifest_conflicts(existing, decoded)

    lot_id = decoded["lot_id"]
    existing_lot = _find_lot(existing, lot_id)
    prior_section = _prior_reconstruction(existing, lot_id)

    _assert_known_lot_state(existing_lot)
    _check_lot_attachment(existing_lot, decoded)
    _check_printed_identifiers(existing_lot, decoded)
    _check_page_count(prior_section, decoded)

    output_dir = project_layout.scan_frames_dir_from_slug(
        project_dir,
        derive_lot_dir_slug(
            rush_id=decoded["rush_id"],
            fps_target=decoded["fps_target"],
            lot_id=lot_id,
        ),
    )
    if not cible_neuve:
        # **La garde et l'ecriture doivent viser le MEME dossier**
        # (trouve en revue, couche 3). Sous `--nouvelle-version`
        # (`EPIC11-ARB-105`), l'ecriture va dans `output-frames/<slug>_vN`
        # alors que ce recalcul rend `<slug>` : la garde inspectait la passe
        # PRECEDENTE. Une page qui echouait a la geometrie faisait alors lever
        # une regression pour des frames que la passe n'allait pas toucher, et
        # le refus ne proposait qu'une sortie -- « relancer avec --overwrite »,
        # c'est-a-dire l'issue destructrice que cet arbitrage a ete pris pour
        # supprimer.
        #
        # Une cible NEUVE n'a rien a degrader: il n'y a pas de frame a
        # remplacer par une mire dans un dossier qui n'existe pas encore.
        _check_planned_degradation(
            output_dir,
            payloads,
            reference=decoded,
            failed_page_indexes=failed_page_indexes,
            prior_synthetic_names=_prior_synthetic_names(existing_lot),
            overwrite=overwrite,
        )


def _check_planned_degradation(
    output_dir: Path,
    payloads: list,
    *,
    reference: Mapping[str, Any],
    failed_page_indexes,
    prior_synthetic_names: set[str],
    overwrite: bool,
) -> None:
    """Refuser une passe qui poserait une mire sur une vraie frame existante.

    Trois conditions **cumulees**, et c'est ce qui empeche le refus d'etre du
    bruit: la page a echoue, donc cette passe y ecrira une mire; le fichier
    correspondant **existe** deja, donc quelque chose sera detruit; et il n'est
    **pas** dans le registre des mires, donc ce qui sera detruit porte l'image
    du film. Une mire ecrite sur une mire, ou sur rien, ne se refuse pas.
    """
    failed = {index for index in failed_page_indexes}
    if not failed or not output_dir.is_dir():
        return
    at_risk: list[str] = []
    for payload in payloads:
        if payload["page_index"] not in failed:
            continue
        for slot in payload["slots"]:
            filename = _scan_frame_filename(reference, slot["frame_timecode"])
            if filename in prior_synthetic_names:
                continue
            if (output_dir / filename).is_file():
                at_risk.append(filename)
    if not at_risk or overwrite:
        return
    raise ScanFrameRegressionError(
        f"Regression de scan: la ou les frames {sorted(at_risk)} portent "
        "aujourd'hui l'image du film, et cette passe y ecrirait une frame de "
        "remplacement -- les planches correspondantes n'ont pas livre leur "
        "geometrie. Une perte ne s'ecrit pas sans le dire, et elle se refuse "
        "**avant** l'ecriture, pendant qu'elle est encore recuperable: "
        "relancer avec `--overwrite` pour l'assumer explicitement, le fait "
        "etant alors nomme au compte rendu. Aucune ecriture n'a eu lieu"
    )


# --------------------------------------------------------------------------
# Couche de persistance
# --------------------------------------------------------------------------


def persist_scan(project_dir: str | Path, record: ScanRecord) -> PersistedScan:
    """Ecrire la declaration de scan dans `<project_dir>/project.json`.

    Point d'entree unique. Appele par la commande `scan` **apres** l'ecriture
    reussie des frames, exactement comme `persist_extraction` l'est apres
    l'ecriture des TIFF et `persist_pdf_generation` apres le rendu du PDF:
    rien n'atteint le manifest tant que les fichiers n'existent pas. L'ordre
    inverse ouvrirait un piege -- un manifest qui declare `state: "scan"` et
    des cardinaux pour des frames que l'ecriture n'a pas produites.

    Sequence: relecture (`_load_existing_manifest`), fusion pure
    (`build_scan_manifest`), ecriture atomique validee (`_atomic_write`).
    Contrairement a `makepdf`, un `project.json` absent n'est **pas** une
    erreur: c'est le cas central de cette story -- un carton de planches
    imprimees et rien d'autre.

    Aucun `overwrite` ici, et c'est le point d'EPIC5-ARB-34: la persistance
    **enregistre le reel** et ne refuse jamais ce que le disque porte deja. Le
    drapeau appartient a `check_scan_conflicts`, qui s'execute avant que la
    moindre frame ne soit ecrite.

    Toute erreur laisse le `project.json` precedent **strictement intact** et
    ne laisse aucun temporaire.
    """
    project_dir = Path(project_dir)
    manifest_path = project_dir / MANIFEST_FILENAME

    existing = _read_manifest_for_guard(project_dir)
    merge = build_scan_manifest(existing, record)

    try:
        # `mkdir` **dans** le `try`: il etait juste au-dessus, si bien qu'un
        # `project_dir` qui est un fichier sortait en `FileExistsError` nue,
        # hors de la hierarchie que la CLI capture (revue couche 2, mineure 2).
        project_dir.mkdir(parents=True, exist_ok=True)
        _atomic_write(manifest_path, merge.manifest)
    except OSError as error:
        # `_atomic_write` ouvre son temporaire **avant** son propre `try`: un
        # dossier projet non inscriptible ou un quota atteint remonte donc en
        # `OSError` nue, hors de la hierarchie que la CLI capture. Le defaut
        # appartient au module de la story 3.4 et son correctif est transverse
        # (consigne au `deferred-work.md`); ici on ramene l'erreur dans la
        # bonne famille, sans la maquiller.
        raise ScanPersistenceError(
            f"Ecriture du manifest impossible: {error}. Le "
            f"{MANIFEST_FILENAME} precedent est intact"
        ) from error

    return PersistedScan(
        manifest_path=manifest_path,
        lot_id=merge.lot_id,
        manifest=merge.manifest,
        state_written=merge.state_written,
        reconstructed_frame_count=merge.reconstructed_frame_count,
        synthetic_frame_count=merge.synthetic_frame_count,
        expected_frame_count=merge.expected_frame_count,
        lot_complete=merge.lot_complete,
        findings=merge.findings,
    )


__all__ = [
    "HOMOGRAPHY_RESOLVED",
    "HOMOGRAPHY_STATUSES",
    "HOMOGRAPHY_UNRESOLVED",
    "LegacyManifestError",
    "PRINTED_IDENTIFIER_FIELDS",
    "PersistedScan",
    "RECONSTRUCTION_LOT_FIELDS",
    "SCAN_LOT_FIELDS",
    "SCAN_LOT_STATE",
    "SCANNED_VERSION_RANKS_FIELD",
    "SCAN_PERSISTENCE_CODES",
    "ScanFrameRegressionError",
    "ScanManifestConflictError",
    "ScanManifestMerge",
    "ScanPageProvenance",
    "ScanPersistenceError",
    "ScanRecord",
    "ReconstructionError",
    "build_scan_manifest",
    "check_scan_conflicts",
    "persist_scan",
    "validate_persistence_code",
]
