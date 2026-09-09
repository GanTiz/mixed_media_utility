# -*- coding: utf-8 -*-
"""Orchestration de `scan detect` -- le **point d'appel unique** du coeur.

Story 7.3, AC 2a (`EPIC7-ARB-64`). Ce module porte le corps que
`cli.scan_detect_command` orchestrait jusqu'ici : ingestion (5.1), detection
(5.2), tri par QR quand aucun lot n'est promis (5.24), puis ecriture d'**un
document de detection par lot trouve** (5.25) et du rapport de tri.

**Pourquoi il existe.** La GUI de l'Epic 7 heberge le coeur EN PROCESSUS
(`EPIC7-ARB-46`) et il lui est interdit d'importer un sous-processus ou de
lire un flux du coeur (frontiere de la story 7.0). Le seul point d'entree qui
existait -- `scan_detect_command` -- convertit ses erreurs en **messages
imprimes** et en **codes de retour** : une interface branchee dessus n'aurait
aucun moyen d'obtenir le motif VERBATIM qu'exige FR4, et devrait le recopier,
ce que P9 interdit. L'extraction n'est donc pas cosmetique : sans elle il n'y
a rien a faire passer dans le canal du motif.

**Le contrat de ce module, en une phrase** : il ne met en forme aucun message
et ne rend aucun code de retour -- il **leve les exceptions du coeur,
inchangees** (`ScanIngestError`, `ScanDetectionError`, `ScanPrevizError`,
`ExtractionPersistenceError`, `ReconstructionError`, `ValidationError`,
`OSError`), et rend un :class:`ScanDetectOutcome` sur les chemins qui
aboutissent. `scan_detect_command` en devient un **enveloppeur** : memes codes
de sortie `0` / `1` / `130`, memes messages imprimes, meme document ecrit au
meme endroit -- deux tests d'equivalence le mesurent
(`tests/unit/test_scan_detect_noyau.py`).

Ce module est du **coeur** : il ne connait ni Qt, ni l'executeur de la GUI, et
il n'importe jamais `gui/`.
"""

import dataclasses
import hashlib
import json
import logging
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from jsonschema.exceptions import ValidationError

from . import (
    color_pipeline,
    page_roles,
    previz_common,
    scan_crop,
    scan_detection,
    scan_ingest,
    scan_output_frames,
    scan_previz,
    scan_sorting,
)
from .io import (
    extraction_manifest,
    project_layout,
    reconstruction,
    scan_manifest,
)
from .io.extraction_manifest import (
    ExtractionPersistenceError,
    _load_existing_manifest,
)
from .io.reconstruction import ReconstructionError

#: Nom du rapport d'ingestion de 5.1. Re-exporte de `scan_ingest`, qui en est
#: l'autorite depuis `EPIC7-ARB-88` : le nom ET l'endroit ou il s'ecrit se
#: decident au meme endroit, sans quoi l'un des deux derive (c'est exactement
#: ce qui est arrive ici).
INGEST_DOCUMENT_FILENAME = scan_ingest.INGEST_DOCUMENT_FILENAME

#: Nom du rapport de tri, ecrit **a cote** du rapport d'ingestion de 5.1
#: (`scans/<slug>/ingest.json`), jamais a sa place: deux documents, deux sujets
#: (AC 10 de 5.24). Le document de detection de 5.25 est un **troisieme**,
#: auquel aucun champ n'est ajoute pour le vrac (AC 13).
TRI_DOCUMENT_FILENAME = "tri.json"

#: Nom du dossier des documents de detection, sous `scans/<slug>/`.
DETECTIONS_DIRNAME = "detections"

#: Nom de la sous-commande qui produit un document de detection, tel qu'un
#: message le cite a l'operateur (`scan ... detect`).
#:
#: **La valeur vit ici depuis la story 11.6 (lot B)**, et `cli.py` la lit --
#: meme motif que `scan_write.CC_FLAG` et `PROFILE_FLAG` (`EPIC11-ARB-75`) :
#: les refus nommes de la moitie haute du temps 2, deplaces au coeur, renvoient
#: l'operateur vers cette sous-commande, et le coeur ne peut pas importer
#: `cli.py`. Recopier la chaine aurait laisse deux verites au meme moment.
SCAN_DETECT_SUBCOMMAND = 'detect'


def dossier_des_detections(lot_dir) -> Path:
    """`<dossier de lot>/detections/` -- implementation unique de ce chemin.

    Le parametre est le **dossier de lot**, jamais un slug. Les deux ne
    coincident pas toujours : un fichier deja range sous `<projet>/scans/<lot>/`
    est ingere en place, et le slug vaut alors le nom du FICHIER. Composer
    `scans/<slug>/detections/` dispersait donc les trois artefacts d'une meme
    passe -- `ingest.json` dans le vrai lot, `tri.json` et `detections/` dans
    un dossier fantome sans images ni rapport (mesure du 2026-08-27,
    `EPIC7-ARB-88`). Le dossier se lit de `scan_ingest.dossier_de_lot` apres
    coup, de `scan_ingest.dossier_de_lot_par_defaut` avant.
    """
    return Path(lot_dir) / DETECTIONS_DIRNAME


def documents_de_detection_existants(lot_dir) -> tuple[Path, ...]:
    """Les documents de detection deja ecrits dans ce lot, ordre deterministe.

    Sert a **poser la question** avant de detecter une seconde fois le meme
    fichier (`EPIC7-ARB-90`) : une interface qui veut savoir « une detection
    existe-t-elle deja ici ? » le demande ici plutot que de composer le chemin
    de son cote.
    """
    dossier = dossier_des_detections(lot_dir)
    if not dossier.is_dir():
        return ()
    return tuple(sorted(dossier.glob("*.json"), key=lambda chemin: chemin.name))


def _effacer_les_detections_existantes(lot_dir, logger) -> int:
    """Retirer les documents de detection du slug, et dire combien.

    Appele **uniquement** sous `remplacer_les_detections=True`, c'est-a-dire
    apres un « Oui » explicite de l'operatrice (`EPIC7-ARB-90`). L'invariant
    de 5.25 (« un fichier par detection, jamais d'ecrasement **silencieux** »)
    tient : ce qui change, c'est qu'un ecrasement **demande** devient possible.

    Un document qu'on n'arrive pas a retirer n'interrompt pas la passe : la
    detection qui suit ecrira le sien a cote, et le chutier montrera deux
    scans -- un desagrement, la ou echouer ici perdrait le travail de
    detection tout entier.
    """
    existants = documents_de_detection_existants(lot_dir)
    retires = 0
    for chemin in existants:
        try:
            chemin.unlink()
        except OSError as erreur:
            logger.warning(
                "Document de detection non remplacable: %s (%s)", chemin, erreur)
            continue
        retires += 1
    if retires:
        logger.info(
            "%d document(s) de detection remplace(s) dans %s.",
            retires, lot_dir)
    return retires


# ---------------------------------------------------------------------------
# Les deux arrets NON FAUTIFS de la commande (code de sortie `0`, aucun
# document ecrit). Ce ne sont pas des echecs : la passe a bien eu lieu, elle
# n'a simplement rien a consigner. Vocabulaire FERME -- une interface qui
# afficherait un motif hors de cette liste afficherait un motif invente.
# ---------------------------------------------------------------------------

#: Aucune planche n'a livre son QR : aucune identite de lot n'est connue, donc
#: aucun document ne peut etre construit. L'ingestion, elle, a eu lieu.
ARRET_AUCUNE_PLANCHE_IDENTIFIEE = "aucune-planche-identifiee"

#: La pile ne porte que des page(s) de calibration : elles ne portent aucune
#: identite de lot. Le geste qui les consigne est `scan ... calibrate`.
ARRET_PILE_DE_CALIBRATION_SEULE = "pile-de-calibration-seule"

MOTIFS_D_ARRET = (
    ARRET_AUCUNE_PLANCHE_IDENTIFIEE,
    ARRET_PILE_DE_CALIBRATION_SEULE,
)


class ScanDetectError(ValueError):
    """Refus propre au chemin `scan detect`, leve avec son message VERBATIM.

    Une seule occurrence aujourd'hui : le tri par QR a besoin de l'identifiant
    du projet courant pour dire quelle feuille est hors perimetre, et ce projet
    n'en a pas encore. C'est un refus du coeur comme un autre -- il **remonte**,
    il ne s'imprime pas ici.
    """


#: **Les refus que le coeur leve sur le chemin `scan detect`**, et que ses
#: enveloppeurs convertissent -- tous au meme code de sortie `1` et au meme
#: prefixe `Erreur: `. La liste est celle de l'AC 2a de la story 7.3 : aucun
#: n'est mis en forme par le coeur, tous **remontent**.
#:
#: **Elle est publiee ici depuis la story 11.6 (lot B)**, et c'est la fermeture
#: d'une dette nommee : `scan_write` publiait `CODES_DE_SORTIE`, `extraction`
#: sa table de correspondance, et `scan_detect` **rien**. Or la TUI ne peut pas
#: importer `cli` (`EPIC11-ARB-67`), donc pour nommer les refus du coeur a
#: l'ecran le lot C de la 11.5 a du **rediger une seconde copie du
#: vocabulaire**, fermee faute de mieux par un test d'egalite d'ensembles
#: (`deferred-work.md`, « `scan_detect` ne publie aucune table de refus »).
#: Deux copies d'une meme regle divergent au premier ajustement ; il n'y en a
#: plus qu'une, et ses **deux** appelants la lisent -- `cli` et
#: `tui.atelier_scan_detection`. C'est le geste que `EPIC11-ARB-108` applique
#: partout ailleurs : un mecanisme, un lieu.
#:
#: `KeyboardInterrupt` et `OSError` n'y figurent pas, et c'est delibere : les
#: deux sont attrapees par la garde `AR2` de `scan_detect_command`, qui porte
#: son propre message d'interruption et reformule l'acces disque.
REFUS_DU_COEUR: tuple[type[BaseException], ...] = (
    scan_ingest.ScanIngestError,
    scan_detection.ScanDetectionError,
    scan_previz.ScanPrevizError,
    ScanDetectError,
    ExtractionPersistenceError,
    ReconstructionError,
    ValidationError,
)


@dataclass(frozen=True)
class ScanDetectOutcome:
    """Ce que la passe a produit -- des faits, jamais des phrases.

    Aucun message compose n'y entre : l'enveloppeur de la CLI redige les siens
    a partir de ces faits, la GUI redige les siens a partir des memes faits, et
    les deux disent donc la meme chose sans qu'aucune ne recopie l'autre.

    `documents` porte **un chemin par lot trouve** (regime de vrac, 5.24) ou le
    chemin unique du lot promis par `ingest_slug`. Il est vide sur les deux
    arrets non fautifs, que `motif_d_arret` nomme alors.
    """

    #: Le `ScanIngestReport` de 5.1, verbatim.
    report: object
    #: Chemin du rapport d'ingestion ecrit (`scans/<slug>/ingest.json`).
    rapport_d_ingestion: Path
    #: Un chemin de document de detection **par lot trouve**, dans l'ordre du tri.
    documents: tuple = ()
    #: Nombre de pages ayant livre leur QR.
    pages_identifiees: int = 0
    #: L'un de :data:`MOTIFS_D_ARRET`, ou `None` quand la passe a produit.
    motif_d_arret: str | None = None
    #: La partition du tri (regime de vrac uniquement), ou `None`.
    partition: object | None = None
    #: Chemin du rapport de tri (regime de vrac uniquement), ou `None`.
    rapport_de_tri: Path | None = None

    @property
    def document_path(self) -> Path | None:
        """Le premier document ecrit, ou `None` -- forme demandee par l'AC 2a.

        Une passe de vrac en produit plusieurs : `documents` reste la source de
        verite, et cet accesseur n'est qu'une commodite pour les appelants qui
        n'en attendent qu'un (regime `--lot-slug`).
        """
        return self.documents[0] if self.documents else None


def run_scan_detect(project_dir, scan_path, *, dpi, ingest_slug=None,
                    logger=None, rappel_progression=None,
                    remplacer_les_detections=False, adopter=False,
                    nouvelle_version=False,
                    manifest_du_projet=None) -> ScanDetectOutcome:
    """Ingerer, detecter, trier, ecrire -- et **lever** ce qui refuse.

    :param project_dir: le dossier projet ouvert.
    :param scan_path: ce que `scan_ingest.ingest_scan_lot` accepte, **passe
        tel quel** : un dossier d'images, un PDF, une image seule (story 5.1),
        ou une **sequence de chemins de fichiers** -- une selection multiple,
        qui fait UN lot (`EPIC7-ARB-88`). Aucune coercition ici : c'est
        l'ingestion qui distingue les quatre formes, et elle seule.
    :param dpi: le dpi de numerisation, **obligatoire et sans defaut**
        (`EPIC7-ARB-44`) : aucun appelant n'en invente un, pas plus la GUI que
        la CLI.
    :param ingest_slug: quand il est donne, l'appelant **promet** que la pile
        est un lot unique, et la promesse est verifiee comme avant (une pile
        multi-lots reste refusee par `LotIdentityError`). Quand il vaut `None`,
        le tri par QR de 5.24 s'insere avant la reconciliation et la passe ecrit
        **un document par lot trouve** (`EPIC5-ARB-106`, `EPIC7-ARB-63`).
    :param logger: journal de la passe. Optionnel : la CLI passe le sien
        (`scans/<projet>/logs`), la GUI n'en passe aucun et le journal du module
        suffit. Le PARAMETRE ne change aucun comportement observable -- ni le
        document ecrit, ni les exceptions levees.
    :param rappel_progression: le canal de progression de la **detection**
        (story 11.4b, lot S5, AC 9.2). Il descend tel quel a
        `scan_detection.detect_pages`, qui l'ouvre dans un
        `progression.EmetteurProgression` : un jalon par page detectee, `total`
        valant le nombre de pages ingerees. **Aucun second mecanisme** n'est
        redige ici ni la-bas -- c'est le canal du depot, celui que l'ecriture
        emploie deja (`EPIC7-ARB-79`, story 5.28).

        **`AR3` : il est OPTIONNEL et son absence ne change RIEN a
        l'observable** -- memes documents ecrits, memes exceptions, meme
        journal. Le mesurer sur les deux regimes n'est pas une formalite : un
        rappel non appelable part `actif is False` **sans lever et sans
        trace**, barre figee a `0/N` (defaut paye cote extraction le
        2026-08-30). Le banc mesure donc aussi que le canal est **actif** quand
        un rappel est fourni.

        La progression ne couvre **que** la detection, jamais l'ingestion qui
        la precede : le contrat de l'emetteur exige un `total` **exact par
        construction**, et le nombre de pages n'est connu qu'une fois
        l'ingestion faite. Un total devine sur le nombre de fichiers designes
        serait faux des qu'une page est illisible et sautee, ou des que le lot
        entre par un PDF.
    :param remplacer_les_detections: quand il vaut vrai, les documents de
        detection deja ecrits pour ce slug sont **retires** avant que la passe
        n'ecrive le sien (`EPIC7-ARB-90`). Faux par defaut : aucun appelant
        existant ne change de comportement, et l'invariant de 5.25 (« jamais
        d'ecrasement **silencieux** ») tient -- ce qui devient possible, c'est
        un ecrasement **demande**. Le retrait n'a lieu qu'apres une ingestion
        reussie, jamais avant : une detection qui echoue a l'ingestion ne doit
        pas laisser le lot sans aucune detection.
    :param nouvelle_version: transmis **verbatim** a
        :func:`scan_ingest.ingest_scan_lot` (`EPIC11-ARB-104`). Il ingere dans
        un dossier VOISIN -- `scans/<slug>_v2/` -- au lieu de refuser ou
        d'ecraser quand le slug porte deja un contenu different.

        **Il manquait, et l'option de la CLI existait deja** (story 11.4e,
        lot D). `--nouvelle-version` est declaree sur le parseur PARENT `scan`,
        dont `detect` est un sous-parseur qui ne redeclare aucune option :
        argparse l'acceptait donc sans un mot, `scan_detect_command` ne la
        lisait jamais, et cette fonction n'avait aucun parametre pour la
        porter. L'operateur croyait demander une nouvelle version et n'obtenait
        rien, en silence -- sur l'objet meme qu'`EPIC11-ARB-104` cite en
        exemple (« On me dit que le scan existe deja ! Pourtant j'ai modifie
        quelque chose. »).

        **Aucune regle de rang n'est ecrite ici** (`EPIC11-ARB-108`) : le rang
        se resout dans `scan_ingest.resolve_scan_version_rank`, qui appelle
        `io.version_ranks`. Ce module ne fait que relayer le drapeau.
    :param manifest_du_projet: le `project.json` deja lu, ou `None` -- il porte
        la **ligne d'eau** des rangs de scan (`scan_version_watermarks`).
        Relaye tel quel a l'ingestion, meme parametre et meme role que sur
        `scan_write.ecrire_depuis_le_document`.

        Sans lui, le rang ne se resoudrait que sur les dossiers PRESENTS, et un
        rang dont le dossier a ete supprime serait rendu **par defaut et sans
        demande** -- l'inverse exact du point 3 d'`EPIC11-ARB-92`. Son absence
        signifie « aucune version employee », jamais « projet invalide » : ce
        chemin s'execute aussi sur un projet dont le manifeste n'est pas encore
        ecrit.

    Rend un :class:`ScanDetectOutcome`. Ne rend jamais de code de sortie et
    n'imprime rien.
    """
    logger = logging.getLogger(__name__) if logger is None else logger
    project_dir = Path(project_dir)
    # `scan_path` est passe TEL QUEL a l'ingestion. Le coercer en `Path` ici
    # detruisait la quatrieme forme d'entree (`EPIC7-ARB-88`) : une selection
    # de plusieurs fichiers arrive sous forme de sequence, et `Path(tuple)`
    # leve un `TypeError` nu -- pas une erreur du coeur, pas un motif lisible,
    # juste un message Python affiche sur la carte de tache. Le geste exact
    # d'Egan (glisser plusieurs TIFF, saisir le dpi, cliquer Detecter)
    # echouait donc encore, en remplacant le `[Errno 2]` par un `TypeError`.
    # `ingest_scan_lot` sait distinguer les quatre formes ; c'est son travail,
    # et il est le seul endroit ou cette distinction doit vivre.
    project_layout.ensure_project_layout(project_dir)

    try:
        report = scan_ingest.ingest_scan_lot(
            project_dir, scan_path, dpi=dpi, ingest_slug=ingest_slug,
            nouvelle_version=nouvelle_version, manifest=manifest_du_projet,
        )
    except scan_ingest.ScanIngestError as exc:
        # Le journal garde la PHASE (ce que l'exception seule ne dit pas), et
        # l'exception remonte inchangee : c'est l'enveloppeur qui la met en
        # forme, c'est la carte de tache qui l'affiche.
        logger.error("Echec de l'ingestion: %s", exc)
        raise

    # Identique a `scan` (AC 1, test 1): meme chemin, meme forme, pour que
    # l'operateur retrouve `ingest.json` a l'endroit habituel qu'il ait
    # lance `scan` ou `scan detect`. Le chemin se LIT du rapport
    # (`scan_ingest.chemin_du_rapport`) et n'est plus reconstruit depuis le
    # slug : les deux divergent des qu'un fichier deja sous `<projet>/scans/`
    # est ingere en place, et le dossier reconstruit n'existe alors pas
    # (`[Errno 2]`, `EPIC7-ARB-88`).
    rapport_d_ingestion = scan_ingest.ecrire_le_rapport(project_dir, report)
    if remplacer_les_detections:
        # APRES l'ingestion, jamais avant : si l'ingestion echoue, le lot garde
        # la detection qu'il avait. Le slug retenu est celui du RAPPORT, pas
        # l'argument -- c'est lui qui nomme le dossier reellement employe.
        _effacer_les_detections_existantes(
            scan_ingest.dossier_de_lot(project_dir, report), logger)
    logger.info(
        "%d page(s) ingeree(s) dans %s a %d dpi (slug d'ingestion: %s)",
        len(report.pages), report.scans_dir, report.declared_dpi,
        report.ingest_slug,
    )
    for code in report.warnings:
        logger.warning("Avertissement d'ingestion: %s", code)
    for name in report.skipped_files:
        logger.warning("Fichier illisible saute: %s", name)
    logger.info("Rapport d'ingestion ecrit: %s", rapport_d_ingestion)

    try:
        # **Le tri s'insere ICI, avant `_reconcile_lot`** (`EPIC7-ARB-63`),
        # exactement comme sur `scan` d'un bloc: l'absence d'`ingest_slug` a le
        # meme sens sur les deux chemins et y declenche le meme tri.
        scan_dpi, pages_detectees = scan_detection.detect_pages(
            project_dir, report, dpi=dpi,
            # Le canal descend **tel quel**, jamais enveloppe : l'envelopper
            # dans un objet non appelable est exactement le defaut qui eteint
            # un canal en silence (mesure le 2026-08-30, cote extraction).
            rappel_progression=rappel_progression)
    except scan_detection.ScanDetectionError as exc:
        logger.error("Echec de la detection: %s", exc)
        raise

    if ingest_slug is None:
        return _detecter_le_vrac(
            project_dir, logger, dpi, report, rapport_d_ingestion,
            scan_dpi, pages_detectees, adopter=adopter)
    return _detecter_le_lot_promis(
        project_dir, logger, dpi, report, rapport_d_ingestion,
        scan_dpi, pages_detectees)


def _detecter_le_lot_promis(project_dir: Path, logger, dpi, report,
                            rapport_d_ingestion, scan_dpi,
                            pages_detectees) -> ScanDetectOutcome:
    """Regime `ingest_slug`: l'appelant **promet** un lot unique.

    La promesse est verifiee, et une pile multi-lots reste refusee par
    `LotIdentityError` -- comportement d'avant l'extraction, inchange.
    """
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
        raise

    for code in detection.warnings:
        logger.warning("Avertissement de detection: %s", code)
    for page in detection.pages:
        if page.refusal_reason:
            logger.warning(
                "Feuille refusee (rang de lecture %s, %s): %s",
                page.read_rank, page.locator_source, page.refusal_reason)

    identified = [page for page in detection.pages if page.payload is not None]
    if not identified:
        logger.warning(
            "Aucune planche n'a livre son QR: aucun document de detection "
            "ne peut etre construit (aucune identite de lot connue). "
            "L'ingestion, elle, a eu lieu."
        )
        return ScanDetectOutcome(
            report=report,
            rapport_d_ingestion=rapport_d_ingestion,
            documents=(),
            pages_identifiees=0,
            motif_d_arret=ARRET_AUCUNE_PLANCHE_IDENTIFIEE,
        )

    payloads = tuple(page.payload for page in identified)
    if reconstruction.pile_sans_planche_d_images(list(payloads)):
        # Une pile de calibration seule ne peut ni se consigner (`detect`
        # n'ajuste ni n'ecrit aucun profil) ni construire de document (une page
        # de calibration ne porte aucune identite de lot).
        logger.info(
            "Cette pile ne porte que des page(s) de calibration: aucune "
            "identite de lot, donc aucun document de detection ne peut "
            "etre construit."
        )
        return ScanDetectOutcome(
            report=report,
            rapport_d_ingestion=rapport_d_ingestion,
            documents=(),
            pages_identifiees=len(identified),
            motif_d_arret=ARRET_PILE_DE_CALIBRATION_SEULE,
        )

    document_path = ecrire_le_document_de_detection(
        project_dir, logger, dpi, report, detection, identified)
    return ScanDetectOutcome(
        report=report,
        rapport_d_ingestion=rapport_d_ingestion,
        documents=(document_path,),
        pages_identifiees=len(identified),
        motif_d_arret=None,
    )


def _detecter_le_vrac(project_dir: Path, logger, dpi, report,
                      rapport_d_ingestion, scan_dpi, pages,
                      *, adopter: bool = False) -> "ScanDetectOutcome":
    """Trier le vrac au **temps 1** du scan, puis ecrire **un document par lot**.

    Ajoutee le 2026-08-25 par `EPIC7-ARB-63`. `--lot-slug` est porte par le
    parser **parent** `scan`, donc partage par `scan ... detect`: l'absence y a
    exactement le meme sens que sur `scan` d'un bloc, et elle y declenche le
    **meme** tri -- la meme fonction du coeur, appelee depuis un second endroit,
    jamais un second mecanisme.

    Le refus multi-lots vit dans la **detection** elle-meme
    (`scan_detection._reconcile_lot`): le tri s'insere donc **avant** elle,
    jamais en rattrapage de son echec. C'est la meme insertion que sur `scan`,
    au meme endroit du pipeline.

    Le contrat de 5.25 est **inchange** (AC 13): chaque document garde sa forme
    et son etat `detected`, et **aucun champ ne lui est ajoute** pour le vrac --
    le rapport de tri est un document **separe**. `scan-write` (5.26) consomme
    toujours **un** document et n'apprend rien du vrac.

    Les deux constats historiques de `detect` -- aucune planche identifiee, pile
    de calibration seule -- sont poses ici a l'identique et **avant** le tri:
    aucun d'eux n'a besoin d'une partition, et les poser apres aurait exige une
    identite de projet la ou il n'y a rien a ranger.
    """
    for page in pages:
        if page.refusal_reason:
            logger.warning(
                "Feuille refusee (rang de lecture %s, %s): %s",
                page.read_rank, page.locator_source, page.refusal_reason)

    identifiees = [page for page in pages if page.payload is not None]
    if not identifiees:
        logger.warning(
            "Aucune planche n'a livre son QR: aucun document de detection "
            "ne peut etre construit (aucune identite de lot connue). "
            "L'ingestion, elle, a eu lieu."
        )
        return ScanDetectOutcome(
            report=report,
            rapport_d_ingestion=rapport_d_ingestion,
            documents=(),
            pages_identifiees=0,
            motif_d_arret=ARRET_AUCUNE_PLANCHE_IDENTIFIEE,
        )

    payloads_identifies = tuple(page.payload for page in identifiees)
    if reconstruction.pile_sans_planche_d_images(list(payloads_identifies)):
        logger.info(
            "Cette pile ne porte que des page(s) de calibration: aucune "
            "identite de lot, donc aucun document de detection ne peut "
            "etre construit."
        )
        return ScanDetectOutcome(
            report=report,
            rapport_d_ingestion=rapport_d_ingestion,
            documents=(),
            pages_identifiees=len(identifiees),
            motif_d_arret=ARRET_PILE_DE_CALIBRATION_SEULE,
        )

    project_id = identite_du_projet_courant(project_dir, pages, logger)
    if project_id is None:
        # **Un refus, leve et jamais mis en forme ici** (`EPIC7-ARB-64`) : la
        # phrase est celle que la CLI imprimait, mot pour mot, et c'est son
        # enveloppeur qui la prefixe comme toute autre exception du coeur.
        raise ScanDetectError(
            "le tri par QR a besoin de l'identifiant du projet courant "
            "pour dire quelle feuille est hors perimetre. Ce projet n'a pas "
            "encore de manifest et cette passe n'en designe pas un seul. "
            "Scannez d'abord un lot d'un seul projet, ou passez --lot-slug "
            "pour promettre que cette pile est un lot unique.")

    # **Les lots deja adoptes ne repartent pas hors perimetre** (`EPIC7-ARB-101`).
    # Le papier continue de declarer son projet d'origine et le declarera
    # toujours : sans cette correspondance, il faudrait re-adopter le meme lot a
    # chaque passe de scan. Elle est lue au manifest du projet, seul lieu ou
    # l'adoption est enregistree, et vaut vide sur tout projet qui n'a rien
    # adopte -- c'est-a-dire sur le chemin d'avant, a l'objet pres.
    # **L'adoption a lieu ICI, AVANT le tri** (`EPIC7-ARB-101`), et l'ordre est
    # le point : c'est le tri qui range une planche etrangere hors perimetre, et
    # une pile entierement etrangere ne produit alors AUCUN lot -- donc aucun
    # document, donc aucune garde plus loin ou se rattraper. Adopter apres lui
    # n'aurait rien a adopter.
    #
    # L'adoption ecrit l'origine au manifest ; `lots_adoptes_du_projet` le relit
    # juste apres, si bien que le tri voit ces lots comme siens. Les passes
    # SUIVANTES n'ont plus rien a demander : la trace est au manifest, et c'est
    # tout le motif de l'avoir posee la.
    if adopter:
        _adopter_les_planches_etrangeres(
            project_dir, logger,
            [page.payload for page in pages if page.payload is not None])
    adoptes = lots_adoptes_du_projet(project_dir, logger)
    partition = scan_sorting.trier_les_pages(
        pages, project_id_courant=project_id, lots_adoptes=adoptes)

    pages_par_localisateur = {
        scan_sorting.Localisateur(page.locator_source, page.locator_page_index): page
        for page in pages
    }

    # **Aucun profil n'est consigne ici**, et c'est la frontiere de la commande:
    # `detect` n'ajuste ni n'ecrit aucun profil (contrat de 5.25, mur 3). Une
    # page de calibration trouvee dans le vrac est **routee et nommee** au
    # rapport de tri; sa consignation appartient au chemin `scan` d'un bloc et a
    # `scan ... calibrate`.
    documents: list[Path] = []
    for lot in partition.lots:
        pages_de_ce_lot = pages_du_lot(partition, lot, pages_par_localisateur)
        detection_du_lot = scan_detection.build_lot_report(
            pages_de_ce_lot,
            ingest_slug=report.ingest_slug,
            scan_dpi=scan_dpi,
            ingest_declared_dpi=report.declared_dpi,
            ingested_count=len(pages_de_ce_lot),
        )
        for code in detection_du_lot.warnings:
            logger.warning("Avertissement de detection (lot %s): %s",
                           lot.lot_id, code)
        identifiees_du_lot = [
            page for page in detection_du_lot.pages if page.payload is not None]
        # **Le rapport d'ingestion est restreint aux pages de ce lot**, et ce
        # n'est pas cosmetique: `scan_previz.build_scan_previz` **refuse** un
        # document dont une page ingeree serait absente -- « une page ingeree et
        # jamais detectee est exactement ce qu'une interface doit montrer ». La
        # garde est juste, et elle s'applique **par document**: chaque document
        # decrit un lot, donc son ingestion est celle de ses pages. Sur une pile
        # mono-lot, cette restriction rend l'ingestion entiere (voir
        # `pages_du_lot`), donc le document est identique a celui d'avant.
        rangs_du_lot = {page.read_rank for page in pages_de_ce_lot}
        report_du_lot = dataclasses.replace(
            report,
            pages=tuple(page for page in report.pages
                        if page.read_rank in rangs_du_lot),
        )
        document_path = ecrire_le_document_de_detection(
            project_dir, logger, dpi, report_du_lot, detection_du_lot,
            identifiees_du_lot)
        documents.append(document_path)

    journaliser_le_tri(logger, partition)
    chemin_du_rapport = ecrire_le_rapport_de_tri(
        project_dir, report, logger, partition, (), project_id)
    return ScanDetectOutcome(
        report=report,
        rapport_d_ingestion=rapport_d_ingestion,
        documents=tuple(documents),
        pages_identifiees=len(identifiees),
        motif_d_arret=None,
        partition=partition,
        rapport_de_tri=chemin_du_rapport,
    )


def ecrire_le_document_de_detection(project_dir: Path, logger, dpi, report,
                                    detection, identified) -> Path:
    """Construire et ecrire **un** document de detection, pour **une** pile homogene.

    Corps **extrait** de `scan_detect_command` par la story 5.24
    (`EPIC7-ARB-63`), jamais reecrit: le regime de vrac ecrit un document **par
    lot trouve**, et une seconde redaction du document divergerait de la
    premiere -- exactement ce qu'`EPIC5-ARB-92` a evite sur la consignation de
    profil. Deux appelants, une seule redaction.

    Le contrat de 5.25 est **inchange** (AC 13): le document garde sa forme et
    son etat `detected`, et **aucun champ ne lui est ajoute** pour le vrac. Le
    rapport de tri est un document **separe**.

    `identified` est la sous-liste des pages de `detection` qui ont livre un
    payload. Elle est passee plutot que recalculee: l'appelant l'a deja, et deux
    lectures de « qu'est-ce qu'une page identifiee » divergeraient un jour.

    Rend le chemin du document ecrit. Une pile refusee avant ecriture ne rend
    rien : elle **leve** l'exception du coeur, inchangee (`EPIC7-ARB-64`).
    """
    # Les payloads de cette pile, derives d'`identified` et non passes a part:
    # deux listes qui doivent rester en correspondance sont deux occasions de
    # les desapparier, et c'est le defaut central que cette story evite partout.
    payloads = tuple(page.payload for page in identified)
    # Refus de la pile mixte (revue de 5.25, meme geste que `scan_command`,
    # `cli.py:2200`): une page de calibration lue dans la meme passe que des
    # planches d'images ne porte aucune identite de lot (AC 10,
    # `EPIC5-ARB-85`/`-86`), et `detect_lot_pages` ne la refuse pas d'elle-
    # meme -- `_reconcile_lot` n'attrape que le multi-lot, pas le melange
    # calibration/images. Sans ce refus, l'identite se lisait sur la
    # premiere planche d'images venue et la page de calibration traversait
    # le document comme une page ordinaire, sans zone ni identite decodee.
    # `check_scan_conflicts` fait bien plus que ce seul refus (rattachement
    # de lot, identifiants d'impression, cardinal de pages face a un
    # manifest existant), et c'est voulu: c'est **le meme appel** que
    # `scan_command`, jamais une reinvention qui ne verrait que la pile
    # mixte. Rien de tout cela n'ecrit -- la fonction ne fait que lire et
    # refuser -- donc l'invariant « detect ne touche pas au manifest »
    # tient: aucune ecriture n'a lieu, ici comme partout ailleurs sur ce
    # chemin. `failed_page_indexes` reste vide et `overwrite` a `False`:
    # cette commande n'ecrit aucune frame, donc la clause de degradation
    # planifiee (mires sur de vraies frames) ne peut jamais s'y appliquer.
    try:
        scan_manifest.check_scan_conflicts(
            project_dir, payloads, failed_page_indexes=(), overwrite=False,
        )
    except (ExtractionPersistenceError, ReconstructionError, ValidationError) as exc:
        # **Le refus REMONTE, il ne se met pas en forme ici** (`EPIC7-ARB-64`,
        # story 7.3 AC 2a) : l'exception du coeur traverse ce module telle
        # quelle, avec son message VERBATIM. C'est l'enveloppeur de la CLI qui
        # l'imprime et rend `1`, et c'est la carte de tache de la GUI qui
        # l'affiche -- toutes deux LISENT le meme texte, aucune ne le recopie
        # (P9). Le journal, lui, garde la phase ou le refus est tombe.
        logger.error("Refus avant ecriture: %s", exc)
        raise

    # L'identite du lot se lit sur n'importe quelle planche d'images
    # identifiee (gardee homogene en amont par `LotIdentityError`, dans
    # `detect_lot_pages`, et par le refus de pile mixte ci-dessus): une
    # page de calibration presente dans une pile mixte n'en porte pas
    # (`project_id`/`rush_id`/`lot_id` absents de son payload), donc elle
    # est explicitement ecartee ici plutot que laissee provoquer un
    # `KeyError`.
    identity = next(payload for payload in payloads if payload.get("lot_id"))

    crop_plans: dict[int, object] = {}
    for page in detection.pages:
        payload = page.payload
        if (
            payload is None
            or page.status != scan_detection.PAGE_OK
            or page.homography is None
            or payload.get("page_role") == page_roles.PAGE_ROLE_CALIBRATION
        ):
            # Page sans plan: elle sort du document **sans zone**
            # (`_frame_zones` de `scan_previz` le prevoit), jamais une
            # panne de la commande -- une page de calibration, une page
            # dont le QR n'a rien livre ou dont la geometrie a echoue n'a
            # simplement rien a decouper.
            continue
        try:
            crop_plans[page.read_rank] = scan_crop.build_page_crop_plan(
                template_id=payload["template_id"],
                slots=payload["slots"],
                dpi=dpi,
            )
        except scan_crop.ScanCropError as exc:
            logger.warning(
                "Page %s: plan de decoupe indisponible (%s), montree sans "
                "zone dans le document.", page.read_rank, exc)

    # Statuts de calibration en regime `detected` (Dev Notes): aucune
    # correction n'a tourne quand `detect` s'arrete, donc chaque page
    # identifiee est versee `not_applied` -- explicitement, plutot que
    # d'omettre le mapping et laisser le document ne rien dire. Le
    # verdict d'ecretage, lui, est omis: jamais un verdict negatif sur
    # une mesure jamais faite.
    calibration_status = {
        page.read_rank: color_pipeline.NOT_APPLIED_STATUS for page in identified
    }

    # Cardinal de planches **attendu**: la regle est ecrite une seule fois,
    # dans `cardinal_de_planches_attendu` ci-dessous, et c'est cette meme
    # fonction que les surfaces relisent (`EPIC7-ARB-73`). Ce qui est verse
    # ici au document est donc, par construction, ce qu'une interface
    # calculerait -- la divergence mesuree le 2026-08-25 entre les deux
    # surfaces de la GUI venait precisement de deux redactions de cette
    # meme regle.
    pages_expected_count = cardinal_de_planches_attendu(identified)

    # Les deux champs additifs de 5.26, verses a la construction (AC 3):
    #
    # * `page_payloads` -- le payload decode **verbatim** de chaque page
    #   identifiee (H4 etendu a la frontiere de processus: il n'est jamais
    #   re-decode, et `timecode_base_fps` n'est reconstituable depuis rien
    #   d'autre). Une page muette n'en a pas et n'en recoit pas;
    # * `source_digests` -- le condensat des octets de la copie ingeree de
    #   **chaque** page (identifiee ou non): c'est lui que `scan-write`
    #   confronte avant d'ecrire, pour refuser un fichier remplace a
    #   dimensions egales. Deux pages du meme PDF partagent le meme
    #   fichier, donc le meme condensat -- calcule une fois par chemin.
    condensats_par_chemin: dict[str, str] = {}
    source_digests: dict[int, str] = {}
    for page in detection.pages:
        chemin = page.locator_source
        if chemin not in condensats_par_chemin:
            condensats_par_chemin[chemin] = condensat_du_fichier_source(
                project_dir / chemin)
        source_digests[page.read_rank] = condensats_par_chemin[chemin]
    page_payloads = {
        page.read_rank: page.payload for page in detection.pages
        if page.payload is not None
    }

    generated_at_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        document = scan_previz.build_scan_previz(
            ingest=report,
            detection=detection,
            crop_plans=crop_plans,
            page_payloads=page_payloads,
            source_digests=source_digests,
            state=scan_previz.SCAN_PREVIZ_STATE_DETECTED,
            generated_at_utc=generated_at_utc,
            project_id=identity["project_id"],
            rush_id=identity["rush_id"],
            lot_id=identity["lot_id"],
            template_id=identity["template_id"],
            gamut_map_id=identity["gamut_map_id"],
            fps_target=identity.get("fps_target"),
            target_colorspace=identity.get("target_colorspace"),
            patch_preset_id=identity.get("patch_preset_id"),
            pages_expected_count=pages_expected_count,
            calibration_status=calibration_status,
            # Les cinq vocabulaires fermes, verses par l'appelant (AC 3):
            # le controle de vocabulaire passe alors du temps de test au
            # temps de construction.
            ingest_warning_vocabulary=scan_ingest.SCAN_INGEST_WARNING_CODES,
            detection_warning_vocabulary=scan_detection.SCAN_DETECTION_WARNING_CODES,
            output_warning_vocabulary=scan_output_frames.SCAN_OUTPUT_WARNING_CODES,
            synthetic_reason_vocabulary=scan_output_frames.SYNTHETIC_FRAME_REASONS,
            calibration_status_vocabulary=color_pipeline.CALIBRATION_STATUS_VALUES,
        )
    except scan_previz.ScanPrevizError as exc:
        logger.error(
            "Echec de construction du document de detection: %s", exc)
        raise

    document_text = previz_common.canonical_json(
        scan_previz.scan_previz_to_json_dict(document))
    document_path = _chemin_unique_de_document(
        scan_ingest.dossier_de_lot(project_dir, report), generated_at_utc)
    ecrire_document_json_atomiquement(document_path, document_text)
    logger.info("Document de detection ecrit: %s", document_path)
    return document_path


def _adopter_les_planches_etrangeres(project_dir: Path, logger,
                                     payloads) -> dict[str, str]:
    """Inscrire au manifest l'origine des lots etrangers de cette pile.

    « C'est comme si j'avais ajoute le rush dans le projet, extrait dans le
    projet, genere la planche dans le projet puis scanne. » (`EPIC7-ARB-101`.)

    Quatre proprietes, et chacune repond a un piege :

    1. **elle a lieu AVANT toute garde.** C'est `check_scan_conflicts` qui
       refusait la planche etrangere, bien avant le tri : une adoption posee
       apres lui n'aurait jamais ete atteinte ;
    2. **le manifest du projet est ENRICHI, jamais reecrit.** Il est passe a
       `reconstruct_project_manifest` comme `existing_manifest`, si bien que
       `_merge_entries` complete l'entree de meme identifiant au lieu de la
       remplacer et que `_preserve_head_sections` rend `artifacts`, `color`,
       `video` et `created` -- les mesures que le scan ne pourra jamais refaire,
       le rush n'etant pas sur cette machine ;
    3. **un lot a la fois**, parce qu'un manifest reconstruit decrit UN lot :
       `_check_lot_consistency` refuse une pile qui en melange ;
    4. **un echec n'arrete pas la passe.** Un lot qu'on ne peut pas adopter est
       journalise et laisse tel quel : la garde suivante le refusera avec son
       propre message, et l'operateur lit ce qui a manque plutot que de perdre
       les lots adoptables avec lui.

    Le document de detection, lui, garde le payload **verbatim** : il dit ce que
    le papier dit, y compris son projet d'origine. C'est le manifest qui porte
    la decision, et c'est pour cela qu'elle tient d'une passe a l'autre.

    Rend les origines inscrites, par `lot_id`. Vide quand rien n'a pu l'etre.
    """
    manifest_path = project_dir / extraction_manifest.MANIFEST_FILENAME
    if not manifest_path.exists():
        logger.warning(
            "Adoption impossible: ce projet n'a pas encore de manifest, donc "
            "pas d'identite d'accueil. Detectez d'abord un lot de ce projet, "
            "ou reconstruisez-le.")
        return {}
    try:
        manifest = _load_existing_manifest(manifest_path)
    except (ExtractionPersistenceError, ValidationError, OSError) as exc:
        logger.error("Adoption impossible: manifest de projet illisible: %s", exc)
        return {}
    projet_d_accueil = (manifest or {}).get("project_id")
    if not projet_d_accueil:
        logger.warning(
            "Adoption impossible: le manifest de ce projet ne declare aucune "
            "identite de projet.")
        return {}

    # Groupees par lot, et **seulement les etrangeres** : une pile deja du
    # projet traverse cette fonction sans que rien ne soit ecrit.
    par_lot: dict[str, list[dict]] = {}
    for payload in payloads:
        lot_id = payload.get("lot_id")
        projet = payload.get("project_id")
        if lot_id is None or projet is None or projet == projet_d_accueil:
            continue
        par_lot.setdefault(lot_id, []).append(dict(payload))

    # **Ce que la reconstruction ne sait pas refaire est RENDU au document.**
    # `reconstruct_project_manifest` repose `artifacts` et `video` vides et ne
    # produit pas `created` : ecrire son resultat tel quel perdrait
    # `artifacts.frames_dir`, `video.codec_target` et la date de creation du
    # projet, sans un mot. Le rush n'est pas sur cette machine, ces mesures ne
    # seront jamais refaites. C'est exactement le piege que `persist_scan` ferme
    # de son cote, et on appelle SA fonction plutot que d'en ecrire une seconde.
    #
    # Defaut trouve en verifiant l'adoption sur le projet reel, pas en relecture.
    avant_adoption = dict(manifest or {})
    origines: dict[str, str] = {}
    for lot_id, du_lot in sorted(par_lot.items()):
        try:
            adoptes, origines_du_lot = reconstruction.adopter_les_payloads(
                du_lot, project_id_cible=projet_d_accueil)
            manifest = reconstruction.reconstruct_project_manifest(
                adoptes, manifest, lot_state=scan_manifest.SCAN_LOT_STATE,
                origin=reconstruction.ORIGIN_SCAN,
                origines_adoptees=origines_du_lot)
            scan_manifest.preserver_les_sections_de_tete(
                manifest, avant_adoption)
        except reconstruction.ReconstructionError as exc:
            logger.warning(
                "Lot %s non adopte: %s Ses planches restent etrangeres a ce "
                "projet.", lot_id, exc)
            continue
        origines.update(origines_du_lot)
        for lot, origine in sorted(origines_du_lot.items()):
            logger.info("Lot adopte dans ce projet: %s (origine: projet %s)",
                        lot, origine)

    if origines:
        ecrire_document_json_atomiquement(
            manifest_path, json.dumps(manifest, indent=2))
    return origines


def lots_adoptes_du_projet(project_dir: Path, logger) -> dict[str, str]:
    """Les lots adoptes par ce projet, lus a son manifest (`EPIC7-ARB-101`).

    Vide quand le projet n'a pas encore de manifest, quand il n'a rien adopte,
    ou quand son manifest est illisible -- ce dernier cas etant deja signale par
    :func:`identite_du_projet_courant`, qui refuse la passe entiere : le
    redire ici n'ajouterait qu'un second message sur la meme cause.
    """
    manifest_path = project_dir / extraction_manifest.MANIFEST_FILENAME
    if not manifest_path.exists():
        return {}
    try:
        declare = _load_existing_manifest(manifest_path)
    except (ExtractionPersistenceError, ValidationError, OSError):
        return {}
    adoptes = scan_sorting.lots_adoptes_du_manifest(declare or {})
    if adoptes:
        logger.info(
            "Lots adoptes par ce projet: %s",
            ", ".join(f"{lot} (de {origine})"
                      for lot, origine in sorted(adoptes.items())),
        )
    return adoptes


def identite_du_projet_courant(project_dir: Path, pages, logger) -> str | None:
    """L'identifiant du projet courant, **lu au manifest** et jamais derive.

    C'est lui que le controle de perimetre de l'AC 4 compare au `project_id` du
    QR de chaque planche. Il ne se derive ni du nom du dossier, ni d'un slug
    operateur: les deux mentiraient le jour ou l'un des deux serait renomme.

    **Un projet sans manifest n'a pas encore d'identite**, et c'est un etat
    legal: `persist_scan` l'ecrit depuis les payloads de la premiere passe. Dans
    ce cas seulement, l'identite est celle que les planches declarent -- a
    condition qu'elles n'en declarent qu'**une**. Si le vrac en porte plusieurs
    sur un projet neuf, aucune n'est « chez elle » plutot qu'une autre : la
    commande refuse en les nommant, plutot que d'en elire une au hasard.
    """
    manifest_path = project_dir / extraction_manifest.MANIFEST_FILENAME
    if manifest_path.exists():
        try:
            declare = _load_existing_manifest(manifest_path)
        except (ExtractionPersistenceError, ValidationError, OSError) as exc:
            logger.error("Manifest de projet illisible: %s", exc)
            return None
        identite = (declare or {}).get("project_id")
        if identite:
            return str(identite)
    # Revue de vague (couche 3): le predicat « qu'est-ce qu'une page de
    # calibration » appartient au module de tri, qui le possede. Ce site le
    # redigeait une seconde fois, en negatif -- si le premier change (par
    # exemple pour traiter un payload sans role), les deux divergent en
    # silence. On APPELLE le predicat plutot que de le recopier: c'est l'AC 1
    # (« le tri est une fonction du coeur ») appliquee a sa propre lecture.
    declarees = sorted({
        page.payload.get("project_id")
        for page in pages
        if page.payload is not None
        and not scan_sorting.est_une_page_de_calibration(page.payload)
        and page.payload.get("project_id")
    })
    if len(declarees) == 1:
        logger.info(
            "Projet sans manifest: l'identite du projet est celle que les "
            "planches de cette passe declarent (%s).", declarees[0])
        return declarees[0]
    if not declarees:
        return None
    logger.error(
        "Ce projet n'a pas encore de manifest et le vrac declare %d projets "
        "differents (%s): aucun n'est le projet courant plutot qu'un autre.",
        len(declarees), ", ".join(declarees))
    return None


def journaliser_le_tri(logger, partition) -> None:
    """Dire les quatre classes, et **les quatre**, pas seulement les lots.

    `EPIC5-ARB-39` (5.8): un rapport dont le hors-perimetre serait vide alors
    que la passe en a produit passerait un compte rendu qui ne regarde que les
    lots.
    """
    logger.info(
        "Tri par QR: %d lot(s), %d page(s) de calibration, %d au reliquat, "
        "%d hors perimetre (%d page(s) au total).",
        len(partition.lots), len(partition.pages_de_calibration),
        len(partition.reliquat), len(partition.hors_perimetre),
        partition.cardinal_total)
    for lot in partition.lots:
        logger.info(
            "  lot %s (rush %s, projet %s): %d page(s)",
            lot.lot_id, lot.rush_id, lot.project_id, len(lot.pages))
    for entree in partition.reliquat:
        logger.warning(
            "  reliquat: %s page %s -- %s%s",
            entree.locator.source_path, entree.locator.page_index,
            entree.motif, f" ({entree.detail})" if entree.detail else "")
    for entree in partition.hors_perimetre:
        # **Le refus dit deux choses, et la seconde est la moitie de la
        # decision** (`EPIC5-ARB-105`): son motif, et le projet a utiliser -- lu
        # dans le `project_id` du QR de la page, qui le porte. L'operateur ne
        # doit pas avoir a le deviner.
        logger.warning(
            "  hors perimetre: %s page %s -- %s. Projet a utiliser pour cette "
            "feuille: %s",
            entree.locator.source_path, entree.locator.page_index,
            entree.motif, entree.projet_a_utiliser)


def ecrire_le_rapport_de_tri(project_dir: Path, report, logger, partition,
                              profils_crees, project_id: str) -> Path:
    """Ecrire le rapport de tri **a cote** du rapport d'ingestion (AC 10).

    Le rapport d'ingestion de 5.1 n'est ni modifie ni remplace, et le document
    de detection de 5.25 ne recoit aucun champ pour le vrac (AC 13): le rapport
    de tri est un document **separe**, que la CLI affiche et que la zone tampon
    de l'Epic 7 consommera.
    """
    rapport = scan_sorting.RapportDeTri(
        ingest_slug=report.ingest_slug,
        project_id=project_id,
        partition=partition,
        profils_crees=tuple(profils_crees),
    )
    # Le dossier de lot REEL, jamais recompose depuis le slug : le rapport de
    # tri doit vivre « a cote du rapport d'ingestion » (AC 10), et un chemin
    # reconstruit l'envoyait dans un autre dossier des que l'ingestion avait
    # lieu en place (`EPIC7-ARB-88`).
    chemin = scan_ingest.dossier_de_lot(project_dir, report) / TRI_DOCUMENT_FILENAME
    ecrire_document_json_atomiquement(
        chemin,
        previz_common.canonical_json(scan_sorting.rapport_to_json_dict(rapport)))
    logger.info("Rapport de tri ecrit: %s", chemin)
    return chemin


# ---------------------------------------------------------------------------
# Completude d'un lot -- UNE seule derivation, et elle vit ICI (EPIC7-ARB-73)
# ---------------------------------------------------------------------------
#
# Le 2026-08-25, deux surfaces de la GUI se contredisaient sur le MEME document
# reel (`tests/fixtures/detection-scan-reelle/detect-ok-et-refus.json`):
# `modele_chutier._completude_du_document` rendait `('complet', ())` quand
# `scan_jugement.badge_de_completude` rendait `incomplet`. Trois causes
# independantes, toutes fermees ici, et fermees a UN SEUL endroit:
#
# 1. le **cardinal attendu** avait deux sources -- `counters.pages_expected`
#    (qui EXCLUT les pages de calibration) contre un `max(page_count)` sur
#    TOUTES les pages. Il n'y a plus qu'une regle, et c'est
#    `cardinal_de_planches_attendu`: c'est elle que la construction du document
#    appelle pour ecrire le compteur, et elle que la lecture rappelle quand le
#    compteur manque;
# 2. l'**origine des `page_index`** etait OBSERVEE d'un cote (`0 if 0 in
#    presents else 1`) et fixee a zero de l'autre. Elle vaut zero, et rien
#    d'autre: `pdf_composition` l'ecrit litteralement (« `page_index` **base
#    zero** »), `page_roles.CALIBRATION_PAGE_INDEX` vaut `0`, et aucun
#    producteur du depot n'ecrit du 1-based. L'heuristique n'accommodait donc
#    aucun producteur reel: sur un lot dont la planche `0` manque, elle
#    nommait manquante une planche qui n'existe pas ET taisait celle qui
#    manque vraiment;
# 3. ce que la completude mesure a l'etape `detected` est **les planches du
#    lot**, jamais les frames. Aucune zone ne porte de `frame_path_relative`
#    avant la story d'ecriture, et l'exiger rendait le verdict CONSTANT a
#    `incomplet` sur le seul etat que la chaine produise aujourd'hui.
#
# Ce module est du coeur: il ne connait ni Qt ni `gui/`. Les surfaces LISENT
# ces trois noms et ce verdict; aucune ne les recalcule.

#: Les trois etats de la FAMILLE 1 des signes (« que manque-t-il dans ce
#: lot ? »). Le vocabulaire vit au coeur pour qu'il n'y ait pas deux listes a
#: tenir a jour -- `gui.modele_chutier` les re-expose sous ses propres noms.
COMPLETUDE_COMPLET = "complet"
COMPLETUDE_COMPLET_AVEC_MIRES = "complet-avec-mires"
COMPLETUDE_INCOMPLET = "incomplet"

#: Les trois, dans l'ordre du plus complet au moins complet.
COMPLETUDES = (
    COMPLETUDE_COMPLET,
    COMPLETUDE_COMPLET_AVEC_MIRES,
    COMPLETUDE_INCOMPLET,
)

#: L'origine des `page_index` d'un lot. **Zero**, ecrit ici une fois pour
#: qu'aucune surface n'ait a la deviner (cause 2 ci-dessus).
ORIGINE_DES_PAGE_INDEX = 0


def cardinal_de_planches_attendu(pages) -> int | None:
    """Le nombre de planches qu'un lot declare, lu de ses pages et d'elles seules.

    Meme lecture que `_reconcile_lot` (`scan_detection.py`): le plus grand
    `page_count` declare. Deux planches d'un meme lot ne declarent pas des
    cardinaux differents, mais si elles le faisaient, en prendre le minimum
    masquerait un trou.

    **L'exclusion des pages de calibration est ecrite ici, et nulle part
    ailleurs** (revue de 5.25, puis `EPIC7-ARB-73`): une page de calibration
    n'appartient a aucun lot -- son `page_count` compte la feuille de mires
    elle-meme -- et son entree dans ce `max()` gonflerait le cardinal du lot
    d'une planche fantome.

    `pages` accepte indifferemment des pages de detection (5.2) et des pages
    de document (`scan_previz.ScanPrevizPage`): les deux portent `page_count`
    et `payload`, et c'est tout ce qui est lu. Un payload absent -- une page
    muette, ou un document anterieur a 5.26 -- n'est jamais une page de
    calibration au sens du tri: il n'a rien declare.

    Rend `None` quand aucune planche ne declare de cardinal: on n'invente pas
    un attendu la ou aucune source n'en porte.
    """
    declares = {
        page.page_count
        for page in pages
        if page.page_count is not None
        and (page.payload or {}).get("page_role")
        != page_roles.PAGE_ROLE_CALIBRATION
    }
    return max(declares) if declares else None


def _cardinal_attendu_du_document(document) -> int | None:
    """Le cardinal attendu **publie** par un document, ou, a defaut, sa regle.

    `counters.pages_expected` est la valeur que la construction a ecrite avec
    `cardinal_de_planches_attendu`: la lire est donc LIRE, jamais recalculer.
    Le repli n'est pas une seconde regle -- c'est la **meme fonction**,
    appliquee aux pages du document quand le compteur est absent (document
    tronque, fixture qui ne le pose pas).
    """
    if document.counters.pages_expected is not None:
        return document.counters.pages_expected
    return cardinal_de_planches_attendu(document.pages)


def completude_des_planches(documents) -> tuple[str | None, tuple[int, ...]]:
    """La completude d'un lot: son etat et **les planches qui lui manquent**.

    Ce qui est mesure ici, sous ce nom, ce sont **les planches du lot** -- ce
    que le QR declare face a ce que le scan a livre --, jamais les frames
    ecrites: a l'etape `detected`, aucune ne l'est encore.

    Plusieurs documents du meme lot s'additionnent (story 5.14, plusieurs
    scans de la meme planche): une planche presente dans l'un est presente.

    Rend `(etat, planches_manquantes)`:

    * sans document, `(None, ())` -- aucune source, aucun verdict;
    * cardinal attendu indeterminable, ou deux documents qui se contredisent:
      `(COMPLETUDE_INCOMPLET, ())`. Une contradiction ne se lit jamais comme
      une garantie, et on refuse de NOMMER des manquantes derivees de l'un des
      deux cardinaux (`EPIC5-ARB-32`);
    * une mire de remplacement rend `COMPLETUDE_COMPLET_AVEC_MIRES`: le
      fichier existe, l'image du film non. Elle ne se rencontre que sur un
      document deja reconstruit -- a l'etape `detected` aucune zone ne porte
      de frame, donc aucune n'est synthetique.
    """
    documents = tuple(documents)
    if not documents:
        return None, ()
    attendus = {
        cardinal
        for cardinal in (
            _cardinal_attendu_du_document(document) for document in documents)
        if cardinal is not None
    }
    if len(attendus) != 1:
        return COMPLETUDE_INCOMPLET, ()
    (attendu,) = attendus
    presents = {
        page.page_index
        for document in documents
        for page in document.pages
        if page.page_index is not None
    }
    manquantes = tuple(
        index
        for index in range(
            ORIGINE_DES_PAGE_INDEX, ORIGINE_DES_PAGE_INDEX + attendu)
        if index not in presents
    )
    if manquantes:
        return COMPLETUDE_INCOMPLET, manquantes
    mires = any(
        zone.synthetic
        for document in documents
        for page in document.pages
        for zone in page.frame_zones
    )
    return (
        COMPLETUDE_COMPLET_AVEC_MIRES if mires else COMPLETUDE_COMPLET), ()


def _cle_de_planche_du_lot(page):
    """La cle d'ordre d'une page dans le document de son lot (`EPIC7-ARB-77`).

    Le **numero de planche declare par le QR** d'abord ; le rang de lecture
    ne departage que les ex aequo. Une page dont le QR n'a pas livre d'index
    n'a pas de numero de planche : elle passe **apres** toutes celles qui en
    ont un, plutot que de s'inserer arbitrairement entre deux.

    Meme regle que `gui.scan_jugement._cle_de_planche`, et c'est voulu : la
    galerie garde son tri local parce qu'un tri est **idempotent** -- retrier
    une liste deja triee ne rend jamais un ordre different, donc les deux ne
    peuvent pas se contredire. C'est ce qui distingue ce cas de la double
    derivation de la completude (`EPIC7-ARB-73`), ou deux calculs rendaient
    deux verdicts opposes.
    """
    index = page.page_index
    return (1, 0, page.read_rank) if index is None else (0, index, page.read_rank)


def pages_du_lot(partition, lot, pages_par_localisateur) -> tuple:
    """Les pages detectees d'un lot, **dans l'ordre des planches** (`page_index`).

    Deux choses tiennent ici, et elles sont independantes.

    **L'ordre est celui que le QR declare** (`EPIC7-ARB-77`, tranche par Egan le
    2026-08-26 : « on range les pages selon l'ordre indique dans le QR »).
    L'operatrice raisonne en **numeros de planche**, jamais en ordre de passage
    au scanner, et c'est le meme ordre pour **toutes** les surfaces.

    *Ce que cette regle remplace, et pourquoi.* Cette fonction triait par
    `read_rank` -- l'ordre physique de la passe. La revue de vague 3 a mesure la
    consequence : le chutier, qui ne trie rien et affiche l'ordre du document,
    montrait les planches `[2, 1, 0]` la ou la galerie montrait `[0, 1, 2]`.
    Deux surfaces, un lot, deux ordres. `EPIC7-ARB-76` avait d'abord fait trier
    la galerie ; `EPIC7-ARB-77` remonte la regle **ici**, a la source, pour que
    les deux surfaces cessent de pouvoir diverger -- meme geste que
    `EPIC7-ARB-73` sur la completude.

    *Ce que ce changement n'a PAS casse, verifie avant de le faire.* La
    docstring d'avant affirmait que « la moitie aval (`provenance`, `frames`,
    `manifest`) est ecrite contre cet ordre depuis 5.2 ». C'est une intention de
    redaction, pas un couplage : le balayage des consommateurs ne trouve **aucun**
    acces positionnel a `document["pages"]` -- tous iterent --, et chaque page
    porte `read_rank` **et** `page_index`, jamais deduits l'un de l'autre. Rien
    n'est donc perdu par ce tri: le rang de lecture reste lisible sur chaque
    page, il cesse seulement d'ordonner la liste.

    **Une page sans numero de planche passe en queue.** Le QR ne l'a pas
    livree, elle ne peut pas se ranger entre deux planches numerotees. Le tri
    est **stable**, et departage a rang de lecture egal: deux scans de la MEME
    planche (story 5.14) et les pages sans index gardent entre eux leur ordre de
    lecture.

    Le tri du vrac, lui, ordonne par contenu -- c'est ce qui rend sa partition
    insensible aux permutations. Melanger les deux ordres resterait
    l'appariement positionnel que cette story existe pour eviter: ce qui est
    tranche ici est l'ordre de la LISTE, jamais l'appariement d'une page avec
    ses valeurs.

    **Une feuille MUETTE rejoint le lot quand il est le seul**, et cette regle
    n'est pas une commodite: c'est ce que `_reconcile_lot` dit deja d'elle --
    « une planche dont on ne connait pas encore l'identite, jamais une feuille
    absente ». Quand la passe ne porte qu'un lot, cette planche est
    necessairement la sienne, et l'y compter est ce qui rend le regime de vrac
    **strictement non regressif** sur une pile mono-lot (AC 2bis). Des qu'il y a
    deux lots, plus rien ne dit de qui elle est: aucun ne la reclame.

    **Muette, et rien d'autre.** Une entree de reliquat qui porte un payload --
    une page de calibration inexploitable (AC 7), une planche a l'identite de lot
    incomplete -- n'est pas une feuille dont l'identite est inconnue: on sait ce
    qu'elle est, et on sait qu'elle n'appartient a aucun lot. L'absorber ferait
    entrer une page de calibration dans la pile d'un lot, donc lui ferait
    rencontrer `REFUS_PILE_MIXTE` -- c'est-a-dire exactement le refus que le tri
    existe pour ne plus atteindre. Defaut mesure a la reecriture des tests de la
    classe B, sur le regime « feuille de calibration monochrome ».
    """
    pages = [pages_par_localisateur[page.locator] for page in lot.pages]
    if len(partition.lots) == 1:
        pages.extend(
            page for page in (
                pages_par_localisateur[entree.locator]
                for entree in partition.reliquat)
            if page.payload is None
        )
    return tuple(sorted(pages, key=_cle_de_planche_du_lot))


def _nom_du_document_de_detection(generated_at_utc: str) -> str:
    """Nom de base du document de detection, derive de son horodatage (story 5.25).

    `generated_at_utc` compacte (sans ':' ni '-') donne un nom lisible et
    deterministe: deux constructions du meme instant produisent le meme nom, ce
    qui est precisement ce que `_chemin_unique_de_document` doit encore
    departager en cas de collision.
    """
    compact = generated_at_utc.replace(":", "").replace("-", "")
    return f"detect-{compact}.json"


def _chemin_unique_de_document(lot_dir, generated_at_utc: str) -> Path:
    """Un fichier PAR detection (AC 2): jamais d'ecrasement silencieux.

    Le document vit sous `<dossier de lot>/detections/`, a cote d'`ingest.json`
    (qui, lui, reste a la racine du meme dossier) et jamais a sa place. Le
    dossier est celui que l'ingestion a REELLEMENT peuple : le recomposer
    depuis le slug expediait les detections dans un dossier sans images
    (`EPIC7-ARB-88`). Une collision de nom -- deux detections dans la meme seconde --
    recoit un suffixe `-2`, `-3`, ... plutot que d'ecraser le fichier existant.

    Le nom est reserve par **creation exclusive** (`os.O_CREAT | os.O_EXCL`,
    revue de 5.25), jamais par un test `exists()` suivi d'une ecriture
    ulterieure: entre le test et l'ecriture, un second processus pouvait
    choisir exactement le meme candidat -- la fenetre que le docstring
    ci-dessus promet pourtant fermee. La creation exclusive est atomique du
    point de vue du systeme de fichiers: sur collision elle leve
    `FileExistsError` plutot que de reussir en silence, donc deux appels
    concurrents ne peuvent jamais rendre le meme chemin. Le fichier reserve
    ici reste vide -- c'est `ecrire_document_json_atomiquement` qui pose le
    contenu, par le meme `os.replace` qu'avant: la garantie d'unicite du NOM
    est exclusive, celle du CONTENU reste l'ecriture atomique deja en place.
    """
    detections_dir = dossier_des_detections(lot_dir)
    detections_dir.mkdir(parents=True, exist_ok=True)
    base_name = _nom_du_document_de_detection(generated_at_utc)
    candidate = detections_dir / base_name
    suffix = 2
    while True:
        try:
            descripteur = os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            stem = base_name[: -len(".json")]
            candidate = detections_dir / f"{stem}-{suffix}.json"
            suffix += 1
            continue
        os.close(descripteur)
        return candidate


#: Prefixe du condensat des octets d'un fichier source (story 5.26, AC 3 de
#: l'epic: « condensat du fichier source dans le document »). Il nomme
#: l'algorithme pour que le champ reste comparable le jour ou un second
#: algorithme existerait; distinct du prefixe `sha256-v1:` de `previz_common`,
#: qui scelle un objet JSON canonique et non des octets bruts -- deux recettes
#: qui partagent un prefixe seraient comparees a tort.
SOURCE_DIGEST_PREFIX = "sha256:"


def condensat_du_fichier_source(path: Path) -> str:
    """Condensat sha256 des **octets** du fichier, prefixe par l'algorithme.

    `ingested_pages_digest` scelle la forme (dimensions, profondeur, chemins);
    celui-ci scelle le **contenu**: un fichier remplace a dimensions egales
    change ce condensat et lui seul. Lecture par blocs pour ne pas charger un
    PDF ou un TIFF entier en memoire.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for bloc in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(bloc)
    return f"{SOURCE_DIGEST_PREFIX}{digest.hexdigest()}"


def ecrire_document_json_atomiquement(path: Path, text: str) -> None:
    """Ecriture atomique (`os.replace`), convention du depot (makepdf, manifest).

    Le temporaire vit dans le **meme** dossier que la cible: `os.replace` n'est
    atomique qu'a l'interieur d'un meme systeme de fichiers. Contrairement a
    `io.extraction_manifest._atomic_write`, aucune revalidation de schema
    n'est faite ici -- le document a deja ete valide a la construction, par
    `build_scan_previz` lui-meme (`ScanPrevizError` sur toute forme invalide).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent,
        prefix=f".{path.name}.", suffix=".tmp", delete=False,
    )
    temp_path = Path(handle.name)
    try:
        with handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise
