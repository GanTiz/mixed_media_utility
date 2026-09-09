# -*- coding: utf-8 -*-
"""Ecriture d'un lot detecte -- la moitie AVAL du scan, au coeur.

Story 11.4b, lot S1 (`EPIC11-ARB-67`). Ce module porte le corps que
`cli._ecrire_le_lot_detecte` orchestrait jusqu'ici : correction designee,
recadrage, avertissements page par page, refus prealable
(`check_scan_conflicts`), ecriture des frames (5.6), manifest (5.7) et trace
du profil designe.

**Pourquoi il existe.** `scan_detect.run_scan_detect` est la moitie AMONT du
meme geste, extraite du CLI par la story 7.3 pour une raison qui vaut mot pour
mot ici : une interface branchee sur `cli.py` recevrait des lignes imprimees
sur `stderr` **sous** l'ecran dessine, et un entier la ou elle a besoin d'un
document ou d'un refus nomme (`tui/palier_projet.py:9-12`). La moitie aval
n'avait jamais fait ce voyage : elle prenait un objet `args` argparse,
imprimait, et rendait un code de sortie. Les deux moities du meme geste se
ressemblent desormais.

**Le contrat de ce module, en une phrase** : il ne met en forme aucun message
et ne rend aucun code de retour -- il **leve les exceptions du coeur,
inchangees** (`ScanIngestError`, `ScanOutputError`,
`ExtractionPersistenceError`, `ReconstructionError`, `ValidationError`) et
rend un :class:`EcritureDuLot` sur le chemin qui aboutit.
`cli._ecrire_le_lot_detecte` en devient un **enveloppeur** : memes codes de
sortie `0` / `1`, memes messages imprimes, memes artefacts.

**Il ne lit JAMAIS `stdin`** (AC 2.1). Les deux decisions qui se posaient a un
humain -- appliquer la correction, ecraser un profil homonyme -- entrent par
des parametres nommes : `demander_l_application_de_la_correction` et
`confirmer_l_ecrasement`. Sous `textual`, `stdin` appartient a la boucle
d'evenements et un appel bloquant y gele l'interface entiere : c'est la
regression exacte payee cote GUI avec `QMessageBox.exec()`
(`EPIC7-ARB-106`). Une frontiere AST mesure l'interdit sur ce fichier
(`tests/unit/tui/test_frontiere_cli.py`).

**L'ordre d'`EPIC5-ARB-34` a voyage avec le corps** : `check_scan_conflicts`
avant `write_lot_output_frames` avant `persist_scan` -- un refus qui arrive
apres une destruction n'est pas un refus. Il est mesure **a l'arrivee**, sur ce
fichier (`tests/unit/test_scan_manifest.py`).

**La couche `manual_corrections` y est CONSOMMEE** (story 11.4b, lot S3,
AC 4) : les identites saisies a la main completent les payloads et les quatre
coins ArUco reposes decident l'homographie de leur planche, avant tout le
reste. Jusqu'ici `scan_corrections` n'avait **aucun appelant de coeur** : une
correction posee etait ecrite au document puis ignoree, et l'operatrice voyait
un succes sans obtenir ses frames -- le risque R12 a la lettre.

Ce module est du **coeur** : il n'importe ni `cli`, ni `gui/`, ni `tui/`.
"""

import dataclasses
import json
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from jsonschema.exceptions import ValidationError

from . import (
    color_calibration,
    color_metrics,
    color_pipeline,
    page_roles,
    scan_corrections,
    scan_crop,
    scan_detect,
    scan_detection,
    scan_ingest,
    scan_output_frames,
    scan_previz,
)
from .io import (
    calibration_profile,
    encode_manifest,
    manifest as manifest_io,
    naming,
    payload as payload_io,
    profile_designation,
    scan_manifest,
)
from .io.extraction_manifest import MANIFEST_FILENAME, ExtractionPersistenceError
from .io.reconstruction import ReconstructionError

#: `--cc {on|off}` sur la commande `scan`, et `--profil` / `set-default-profile`.
#:
#: **Les valeurs vivent ici depuis la story 11.4b**, et `cli.py` les lit -- le
#: motif est celui d'`extraction.CODES_DE_SORTIE` (`EPIC11-ARB-75`) : les
#: messages de journal ecrits par ce module les nomment, et une interface a
#: interdiction d'importer `cli.py`. La prose qui explique **pourquoi** ces
#: gestes portent ces noms est restee dans `cli.py`, aupres des options qu'elle
#: decrit ; ce qui a bouge est la valeur, pour qu'il n'y en ait qu'une.
CC_FLAG = '--cc'
CC_ON = 'on'
CC_OFF = 'off'
PROFILE_FLAG = '--profil'
SET_DEFAULT_PROFILE_COMMAND = 'set-default-profile'


#: Les refus que ce module leve et que ses enveloppeurs convertissent -- **tous
#: au meme code de sortie `1` et au meme prefixe `Erreur: `**.
#:
#: Elle est ici et non dans `cli.py` pour la raison qui a fait naitre
#: `extraction.CODES_DE_SORTIE` (`EPIC11-ARB-75`) : la TUI doit rendre le meme
#: code retour et a interdiction d'importer `cli.py`. Dupliquer la table
#: laisserait deux verites au meme moment, et un test symetrique ne rougirait
#: qu'**apres** qu'on a diverge.
#:
#: `KeyboardInterrupt` et `OSError` n'y figurent pas, et c'est delibere : les
#: deux sont attrapees par les gardes `AR2` de `scan_command` et
#: `scan_write_command`, qui portent chacune leur propre message
#: d'interruption et reformulent l'acces disque. Les faire entrer ici
#: remplacerait ces deux messages par un `Erreur: ` generique.
CODE_SUCCES = 0
CODE_ERREUR = 1

#: **Le lot a ete ecrit, mais ce n'est pas ce qui etait promis** (story 11.4c,
#: lot V2, AC 9.1). Troisieme code de l'ecriture, distinct des cinq deja pris
#: par la chaine -- `0` succes, `1` refus, `2` prerequis absent, `3` refus
#: d'etat, `130` interruption (`extraction.py:150-154`) --, parce qu'il ne dit
#: ni l'un ni l'autre : quelque chose a bel et bien ete ecrit, et ce quelque
#: chose porte des mires ou un trou.
#:
#: **Ce que ce code corrige, mesure et non suppose.** Au `baseline_commit` de
#: la vague, une source illisible produisait quatre frames de mire sur huit,
#: annoncait `SYNTHETIC_FRAME_WRITTEN`, puis `FRAMES_SYNTHETIQUES_PRESENTES`
#: et `LOT_INCOMPLET` -- et rendait **`0`** (scenario `52_source_ILLISIBLE` du
#: dossier d'identite, `tests/fixtures/identite-scan-289f29d.json`). Rien
#: n'etait silencieux : la tracabilite etait **complete** a l'ecran comme au
#: manifeste, et l'elargir aurait ete le defaut (fait F7 de la fiche 11.4c).
#: Ce qui manquait est le **pont** entre l'inventaire que la commande produit
#: deja et le code qu'elle rend. Un humain lisait les deux moities de la
#: phrase ; un script, une integration continue, tout appelant qui ne regarde
#: que le code retour lisait un succes sur un lot a moitie fait.
#:
#: **C'est un changement de contrat CLI, et il est assume** (`Q3` de la fiche) :
#: un appelant qui teste `!= 0` voit desormais rouge sur un lot a mires -- ce
#: qui est le but --, un appelant qui teste `== 1` ne le voit pas. La valeur
#: distincte est ce qui garde separes « refuse, rien n'est ecrit » et « ecrit,
#: mais pas ce qui etait promis » : les confondre en `1` ferait relancer la
#: passe a qui devrait rescanner une feuille.
CODE_SUCCES_PARTIEL = 4

#: **L'inventaire d'avertissements de la passe, et son vocabulaire.** Les deux
#: moities sont deja fermees chacune de son cote et le restent : les onze
#: avertissements d'ecriture de la story 5.6
#: (`scan_output_frames.SCAN_OUTPUT_WARNING_CODES`, gardes par
#: `validate_warning_code`) et les huit constats de persistance de la 5.7
#: (`scan_manifest.SCAN_PERSISTENCE_CODES`, gardes par
#: `validate_persistence_code`). Elles sont **lues**, jamais recopiees : deux
#: redactions du meme vocabulaire divergeraient, et l'ecart ne se verrait que
#: sur un code de sortie devenu faux.
VOCABULAIRE_DE_L_INVENTAIRE: tuple[str, ...] = (
    scan_output_frames.SCAN_OUTPUT_WARNING_CODES
    + scan_manifest.SCAN_PERSISTENCE_CODES
)

#: **L'ensemble FERME des motifs qui degradent le code de sortie** (AC 9.2), et
#: il est exactement celui-ci -- ni « au moins ceux-la », ni « tous les
#: avertissements ». `CLAUDE.md`, 2026-08-30 : « une assertion positive laisse
#: passer toute divergence supplementaire. [...] « l'ensemble des chemins qui
#: divergent est **exactement** {X} » mesure l'exception ET son unicite. » Le
#: banc confronte donc cet ensemble a ce que le code consulte, par egalite
#: d'ensembles.
#:
#: Les deux motifs sont ceux de l'AC 9.3 : un lot **declare incomplet**, et la
#: presence de **frames de remplacement**. Les deux sont deja calcules au point
#: de decision -- ce sont les constats que `persist_scan` rend et que la
#: commande imprime deja --, donc rien n'est recalcule ici : ce module
#: **relaie** l'inventaire, il ne le rejuge pas. Le second n'est pas redondant
#: avec le premier bien qu'une mire interdise la completude
#: (`scan_manifest.py:1638-1641`) : c'est le manifeste qui pose ce lien, et un
#: jour ou il changerait, le code de sortie ne doit pas cesser de voir les
#: mires.
#:
#: **Ce qui n'y est PAS, et c'est aussi une AC** (9.4) :
#: `OUTPUT_FRAME_OVERWRITTEN` sous un `--overwrite` explicite. L'operateur a
#: demande l'ecrasement ; le rendre non nul casserait tout appelant legitime,
#: et le scenario `51b` du dossier d'identite garde son `0`. Les seize autres
#: codes du vocabulaire ci-dessus sont dans le meme cas : ils informent, ils ne
#: degradent pas.
MOTIFS_QUI_DEGRADENT_LE_CODE: frozenset[str] = frozenset({
    scan_manifest.SCAN_LOT_INCOMPLETE,
    scan_manifest.SCAN_SYNTHETIC_FRAMES_PRESENT,
})

#: **Les motifs de refus du DOCUMENT de detection, ensemble FERME et ORDONNE**
#: (story 11.6, lot B, `EPIC11-ARB-129`).
#:
#: Ils nomment les huit facons dont la moitie HAUTE du temps 2 -- lire un
#: document de detection persiste et le rendre consommable -- refuse avant
#: qu'une seule frame n'existe. Jusqu'a la story 11.6 ils vivaient dans
#: `cli.scan_write_command`, sans nom et sans table : un refus s'y ecrivait en
#: `print(..., file=sys.stderr)` puis `return 1`, ce qu'une interface ne peut
#: ni lire ni distinguer. La TUI a interdiction d'importer `cli.py`, donc elle
#: aurait redige une **troisieme** lecture du document apres les deux de
#: `gui/` -- la faute que ce depot paie a chaque fois (`EPIC11-ARB-108` :
#: « un mecanisme, un lieu »).
#:
#: **Pourquoi une table publiee et pas seulement des exceptions.** C'est la
#: dette que le lot C de la 11.5 a payee sur la moitie amont : `scan_detect`
#: ne publie aucune table de refus, donc la TUI a du en **rediger une seconde
#: copie**, fermee par un test d'egalite d'ensembles faute de mieux
#: (`deferred-work.md`, « `scan_detect` ne publie aucune table de refus »). Ici
#: la table **est** l'interface : un appelant nomme un refus en comparant
#: `motif` a l'une de ces constantes, jamais en relisant la phrase.
#:
#: **L'ordre du tuple est l'ordre des gardes** (`EPIC5-ARB-34` : « un refus qui
#: arrive apres une destruction n'est pas un refus »), et il est mesure comme
#: tel : lecture et refus du document, puis condensat de chaque source, puis
#: annonce de completude, puis le refus du document a zero page identifiee,
#: puis la moitie aval.
REFUS_DOCUMENT_INTROUVABLE = "document-introuvable"
REFUS_DOCUMENT_JSON_INVALIDE = "document-json-invalide"
REFUS_DOCUMENT_PAS_UNE_PREVIZ_DE_SCAN = "document-pas-une-previz-de-scan"
REFUS_DOCUMENT_ETAT_INATTENDU = "document-etat-inattendu"
REFUS_DOCUMENT_ANTERIEUR = "document-anterieur"
REFUS_SOURCE_MANQUANTE = "source-manquante"
REFUS_SOURCE_CONDENSAT_DIVERGENT = "source-condensat-divergent"
REFUS_DOCUMENT_SANS_PAGE_IDENTIFIEE = "document-sans-page-identifiee"

MOTIFS_DE_REFUS_DU_DOCUMENT: tuple[str, ...] = (
    REFUS_DOCUMENT_INTROUVABLE,
    REFUS_DOCUMENT_JSON_INVALIDE,
    REFUS_DOCUMENT_PAS_UNE_PREVIZ_DE_SCAN,
    REFUS_DOCUMENT_ETAT_INATTENDU,
    REFUS_DOCUMENT_ANTERIEUR,
    REFUS_SOURCE_MANQUANTE,
    REFUS_SOURCE_CONDENSAT_DIVERGENT,
    REFUS_DOCUMENT_SANS_PAGE_IDENTIFIEE,
)

#: Les cinq refus qui portent sur le DOCUMENT lui-meme, dans l'ordre des
#: gardes -- ceux que :func:`lire_le_document_de_detection` leve a lui seul.
#: Les trois autres demandent le dossier projet (les octets des sources, puis
#: les payloads), donc ils tombent plus loin dans la sequence.
MOTIFS_DE_REFUS_A_LA_LECTURE: tuple[str, ...] = MOTIFS_DE_REFUS_DU_DOCUMENT[:5]


class RefusDuDocumentDeDetection(ValueError):
    """Un refus **nomme** de la moitie haute du temps 2 : rien n'a ete ecrit.

    Elle porte son :attr:`motif` -- l'une des constantes de
    :data:`MOTIFS_DE_REFUS_DU_DOCUMENT` -- **a cote** de son message. Les deux
    ne se remplacent pas : le message est ce qu'un terminal imprime mot pour
    mot (`Erreur: <message>`, comme avant l'extraction), le motif est ce qu'une
    interface teste sans lire de phrase. Nommer un refus en cherchant un bout
    de phrase est exactement ce qui casse a la premiere reformulation.

    Elle derive de `ValueError` comme `ScanIngestError` et `ScanDetectError`,
    et elle entre dans :data:`CODES_DE_SORTIE` au meme code `1` que les autres
    refus du coeur : l'enveloppeur de la CLI ne la traite pas a part.

    **Le message est POSITIONNEL, le motif est NOMME et facultatif**, et ce
    n'est pas une commodite : le dossier d'identite du scan
    (`tests/unit/test_identite_du_scan.py`) construit **chaque** entree de
    :data:`CODES_DE_SORTIE` avec un seul message, pour mesurer que le code de
    sortie et le prefixe `Erreur: ` du baseline valent pour toutes les familles
    de la table -- y compris celles qu'aucun refus reel n'atteint. Une exception
    de cette table qui exigerait deux arguments sortirait ce parcours de la
    mesure, ce qui est exactement le survivant qui l'a fait ecrire. Tous les
    `raise` de ce module passent le motif ; un banc mesure que l'ensemble
    atteignable est **exactement** la table.
    """

    def __init__(self, message: str, *, motif: str | None = None):
        super().__init__(message)
        #: L'un de :data:`MOTIFS_DE_REFUS_DU_DOCUMENT`, ou `None` pour une
        #: instance fabriquee hors de ce module.
        self.motif = motif


CODES_DE_SORTIE: tuple[tuple[type[BaseException], int], ...] = (
    # **Story 11.4b, lot S3 (AC 4)** : la couche `manual_corrections` est
    # desormais consommee a l'ecriture, donc ses refus traversent ce point
    # d'entree. `CorrectionInvalide` derive de `ValueError` et `ValidationError`
    # de `jsonschema` : aucune des deux familles n'attrape l'autre, l'ordre
    # entre elles est donc indifferent -- ce qui n'est PAS le cas de
    # `IdentiteIncompletable`, qui est une **sous-classe** de
    # `CorrectionInvalide` et n'a pas d'entree a elle : la recherche rend la
    # premiere entree qui correspond, et les deux vont au meme code.
    # Sans cette entree, une identite incompletable sortait de `mmu scan write`
    # en trace Python nue au lieu du `Erreur: <motif>` + code `1` que
    # l'AC 4.5 exige (« refuse avant toute ecriture, **avec son motif** »).
    # **Story 11.6, lot B** : les huit refus nommes de la moitie HAUTE du
    # temps 2 (lecture du document de detection). Ils entrent au meme code `1`
    # que les autres refus du coeur -- avant l'extraction, `cli` les rendait
    # deja tous par `return 1` derriere un `Erreur: ` sur `stderr`.
    (RefusDuDocumentDeDetection, CODE_ERREUR),
    (scan_corrections.CorrectionInvalide, CODE_ERREUR),
    (scan_ingest.ScanIngestError, CODE_ERREUR),
    (scan_output_frames.ScanOutputError, CODE_ERREUR),
    (ExtractionPersistenceError, CODE_ERREUR),
    (ReconstructionError, CODE_ERREUR),
    (ValidationError, CODE_ERREUR),
)


def correspondance_de_sortie(
    exception: BaseException,
) -> tuple[type[BaseException], int] | None:
    """Rendre l'entree de :data:`CODES_DE_SORTIE` qui attrape `exception`.

    Rend `None` pour ce que la table ne nomme pas : l'appelant **relaie** alors
    l'exception au lieu de la deguiser en refus metier -- la pile d'`except`
    nommee qu'elle remplace ne les attrapait pas non plus, et un bug de
    programmation ne doit pas sortir en code d'erreur ordinaire.
    """
    for classe, code in CODES_DE_SORTIE:
        if isinstance(exception, classe):
            return classe, code
    return None


def code_de_sortie(exception: BaseException) -> int | None:
    """Le code de sortie de l'ecriture pour `exception`, ou `None` si inconnue."""
    correspondance = correspondance_de_sortie(exception)
    return None if correspondance is None else correspondance[1]


def inventaire_de_l_ecriture(ecriture: "EcritureDuLot") -> tuple[str, ...]:
    """L'inventaire complet de la passe, **dans l'ordre ou elle l'annonce**.

    Les avertissements d'ecriture d'abord (`Avertissement d'ecriture: <code>`,
    emis a la sortie des frames), les constats de persistance ensuite
    (`Constat de persistance: <code>`, emis apres le manifeste). C'est
    litteralement la suite de codes que l'operateur lit dans `logs/scan.log`,
    reunie en un seul objet -- rien n'est recalcule, rien n'est deduit.

    **Ce n'est pas un second inventaire** : les deux moities sont **relayees**
    telles quelles depuis les rapports de 5.6 et de 5.7. Une seconde redaction
    -- « recomptons les mires ici » -- serait la deuxieme verite
    qu'`EPIC5-ARB-78` interdit, et elle divergerait sans que rien ne le
    montre.
    """
    return tuple(ecriture.output.warnings) + tuple(ecriture.persisted.findings)


def motifs_de_degradation(inventaire) -> tuple[str, ...]:
    """Les motifs de `inventaire` qui degradent le code, dans l'ordre annonce.

    Rend un tuple et non un booleen : l'appelant doit pouvoir **nommer** ce qui
    a degrade son code de sortie dans la phrase qu'il imprime (AC 9.5). Un
    verdict nu obligerait a redecider ailleurs quel motif l'a produit, donc a
    ecrire une seconde fois l'ensemble ferme.
    """
    return tuple(code for code in inventaire
                 if code in MOTIFS_QUI_DEGRADENT_LE_CODE)


def code_de_sortie_de_l_ecriture(inventaire) -> int:
    """Le pont entre l'inventaire et le code de sortie (AC 9, story 11.4c).

    C'est **tout** le defaut D2/D3 de la fiche, et il tient en une ligne : la
    commande produisait deja l'inventaire, l'imprimait deja, l'ecrivait deja au
    manifeste -- et rendait `0` quand meme. Rien n'est ajoute a la tracabilite
    ici (fait F7 : elle est complete, l'elargir serait le defaut) ; ce qui est
    ajoute est le chemin qui va de l'un a l'autre.
    """
    return (CODE_SUCCES_PARTIEL if motifs_de_degradation(inventaire)
            else CODE_SUCCES)


class ConflitDeContenuDuLot(scan_manifest.ScanPersistenceError):
    """Ecraser des frames qu'un master video declare avoir consommees (AC 10).

    Sous-classe de la hierarchie de persistance de scan, donc attrapee par
    l'entree `ExtractionPersistenceError` de :data:`CODES_DE_SORTIE` et rendue
    au code `1` sans qu'aucune table n'ait a bouger : c'est un **refus**, et un
    refus n'ecrit rien.

    **Ce refus porte sur le CONTENU, jamais sur l'ordre des etats**, et la
    distinction n'est pas de style : `io/reconstruction._resolve_lot_state`
    (`:801-819`) pose verbatim que « reconstruire ou rescanner un lot deja
    passe en `reconstruction` ou en `encode` est le scenario nominal », que
    « cette fonction **n'abaisse jamais** un etat », et que « le seul echec dur
    reste le conflit de contenu, jamais l'ordre des etats ». Une garde d'etat
    posee ici defairait cette decision ; la garde posee ici lit l'inventaire
    `lots[].encoded_masters`, c'est-a-dire ce que l'aval a **reellement
    produit** depuis ces frames-la.
    """


def masters_declares_du_lot(project_dir, lot_id: str) -> tuple[dict, ...]:
    """Les masters que le manifeste declare avoir encodes depuis CE lot.

    Lecture par le **seul point d'entree public** du manifeste
    (`io.manifest.load_manifest`) : `_load_existing_manifest` et `_find_lot`
    sont prives a `io/extraction_manifest.py`, et les appeler d'ici ferait
    dependre le coeur du scan d'une frontiere que ce depot tient.

    Un projet vierge -- pas encore de `project.json` -- n'a evidemment aucun
    master : le cas nominal du premier scan passe par ici et ne doit rien
    couter. Le document, lui, a deja ete relu et refuse s'il etait corrompu par
    `check_scan_conflicts`, qui tombe **avant** cet appel.

    L'appariement se fait sur `lot_id`, jamais sur le rang : c'est le mutant
    `M25` de la story 5.7 -- « rendre le premier lot au lieu du lot vise » --,
    dont la consequence reelle etait d'ecrire les cardinaux sur le mauvais lot.
    Les fabriques du banc placent donc le lot vise **au milieu** de trois.
    """
    chemin = Path(project_dir) / MANIFEST_FILENAME
    if not chemin.is_file():
        return ()
    document = manifest_io.load_manifest(chemin)
    for lot in document.get("lots") or ():
        if not isinstance(lot, dict) or lot.get("lot_id") != lot_id:
            continue
        inventaire = lot.get(encode_manifest.MASTER_INVENTORY_FIELD) or ()
        # Tri par la **cle** de l'inventaire (`path`, unique par construction
        # puisque c'est un chemin de fichier) : le message nomme les masters
        # dans un ordre stable, et non dans l'ordre chronologique des
        # encodages, qui est un signal d'horloge.
        return tuple(sorted(
            (entree for entree in inventaire if isinstance(entree, dict)),
            key=lambda entree: str(
                entree.get(encode_manifest.MASTER_INVENTORY_KEY, "")),
        ))
    return ()


def refuser_le_conflit_de_contenu(project_dir, payloads, *, overwrite: bool,
                                  logger) -> None:
    """Refuser d'ecraser des frames qu'un master declare avoir consommees.

    AC 10.1 : le refus **nomme, avant d'ecrire**, ce qui serait detruit et
    quels masters le referencent. Il est pose apres `check_scan_conflicts` --
    donc apres que l'identite du lot a ete validee, et son unicite sur la pile
    -- et avant `write_lot_output_frames`, donc avant le premier octet ecrit.

    Il ne se declenche que sous `--overwrite` : sans le drapeau, une passe qui
    retomberait sur des frames existantes est **deja** refusee par la garde de
    reecriture de la story 5.6, et poser une seconde condition sur ce chemin
    ferait deux refus pour un seul fait.
    """
    if not overwrite:
        return
    # **Aucun acces indexe nu a un champ de payload**, et ce n'est pas du style
    # (story 5.23, AC 10, inventaire de `tests/unit/test_pile_mixte_refus.py`):
    # une page de calibration ne porte **pas** `lot_id`, et un
    # `payloads[0]["lot_id"]` y mourrait en `KeyError` nue -- la sixieme
    # occurrence de la meme famille en cinq corrections. Le cas est
    # structurellement ferme ici, `check_scan_conflicts` refusant plus haut une
    # pile sans planche d'images, mais le depot a cesse de parier sur
    # l'inatteignabilite : la lecture prend le **premier payload qui declare**
    # un lot, et une pile qui n'en declarerait aucun n'a par definition aucun
    # master a proteger.
    lot_id = next((declare for declare in
                   (payload.get("lot_id") for payload in payloads)
                   if declare), None)
    if lot_id is None:
        return
    masters = masters_declares_du_lot(project_dir, lot_id)
    if not masters:
        # **Le scenario nominal de `_resolve_lot_state`**, et il reste
        # ecrivable : un lot passe en `reconstruction` ou en `encode` sans
        # master declare est le « projet recree depuis des payloads, puis
        # planches scannees » que la docstring nomme. L'ordre des etats ne
        # refuse rien ici, et ce silence est mesure par un test.
        return
    noms = ", ".join(
        f"{entree.get(encode_manifest.MASTER_INVENTORY_KEY)} "
        f"({entree.get('frame_count')} frame(s))"
        for entree in masters)
    message = (
        f"Conflit de contenu sur le lot {lot_id}: {len(masters)} master(s) "
        f"video declarent avoir ete encodes depuis ses frames ({noms}), et "
        "cette passe les reecrirait. Ce refus porte sur le CONTENU du lot, "
        "jamais sur l'ordre de ses etats: un lot deja passe en "
        "'reconstruction' ou en 'encode' SANS master declare reste ecrivable, "
        "c'est le scenario nominal. Issues: retirer ces masters de "
        "l'inventaire puis reencoder depuis les nouvelles frames, ou scanner "
        "vers un autre lot. Aucune ecriture n'a eu lieu"
    )
    logger.error("Refus avant ecriture: %s", message)
    raise ConflitDeContenuDuLot(message)


@dataclass(frozen=True)
class EcritureDuLot:
    """Ce qu'une passe d'ecriture a **reellement** produit.

    Rendue par :func:`ecrire_le_lot_detecte` sur le seul chemin qui aboutit :
    les refus, eux, sont **leves**. Aucun champ n'est une phrase -- la
    redaction du compte rendu appartient a l'appelant, exactement comme
    `ScanDetectOutcome` ne porte aucune phrase de terminal.
    """

    #: Le `ScanPersistResult` de 5.7, verbatim : etat du lot, cardinaux, chemin
    #: du manifest, constats de persistance.
    persisted: object
    #: Le rapport d'ecriture de 5.6, verbatim : frames ecrites, dossier de
    #: sortie, frames de remplacement, avertissements.
    output: object
    #: La correction du lot telle qu'elle a ete **reellement** posee, `None`
    #: quand le lot n'en avait aucune. C'est l'objet qui porte le report du
    #: refus a l'invite (`correction_requested`, `EPIC5-ARB-78`).
    lot_correction: object | None
    #: La decision d'application telle qu'elle a ete **tranchee**, drapeau
    #: explicite et invite compris : ce que l'interface doit reafficher, jamais
    #: ce qui a ete demande au depart.
    correction_appliquee: bool
    #: Vrai quand la correction vient d'un profil **designe** et non d'une page
    #: de calibration presente dans le scan.
    profil_de_chaine_utilise: bool
    #: Le rapport d'ingestion que la passe a consomme, verbatim -- celui de
    #: 5.1 sur le chemin `scan`, l'adaptateur
    #: :class:`IngestionDuDocument` sur le chemin `scan-write`. Ajoute par la
    #: story 11.6 (lot B) parce que le compte rendu final le lit
    #: (`scans_dir`, `len(pages)`) et que, depuis que la moitie HAUTE vit au
    #: coeur, l'appelant ne le construit plus lui-meme. `None` seulement pour
    #: un objet fabrique a la main dans un banc.
    rapport: object | None = None


def _avertir_sur_une_page(logger, page_index: int, result, *, page_id: str) -> int:
    """Emettre les deux avertissements de la story 5.23 sur **une** page corrigee.

    Story 5.23, AC 4 (divergence brute au-dela du seuil) et AC 7 (degradation maximale).
    Les deux **avertissent sans rien empecher**: c'est la demande fondatrice d'Egan
    (`EPIC5-ARB-82`, decisions 4 et 7 -- « avertir, pas refuser »), et la moitie visible
    de cette demande est precisement qu'un avertissement **sorte**.

    **Extraite de la boucle de `scan_command` pour etre mesurable, et pour cette seule
    raison.** Les deux `if` etaient enterres dans une boucle qu'aucun test n'atteignait
    sans monter un scan complet: remplaces par `pass`, ils survivaient a l'injection --
    y compris sur `test_chain_profile_scan.py`, le seul lot qui relit `logs/scan.log`.
    Le **libelle** des deux messages etait epingle par les tests unitaires de
    `color_calibration`; leur **emission** ne l'etait par rien. Un message parfaitement
    redige qui n'est jamais ecrit vaut exactement l'absence de message.

    Rend le **nombre d'avertissements emis** (0, 1 ou 2). Le retour n'est pas consomme
    par l'appelant -- la boucle ne fait rien de ce compte -- et il est la pour que la
    propriete se mesure sans relire un fichier de journal: un `pass` a la place de l'un
    des deux `if` fait tomber ce compte, un `return 2` inconditionnel echoue sur les
    frontieres negatives. C'est le meme geste que `_stdin_is_interactive`, isole pour
    que le regime non teste ne soit pas justement celui qui pend.
    """
    emis = 0
    raw_divergence = result.raw_divergence
    if raw_divergence is not None and raw_divergence.exceeds:
        logger.warning(
            "Page %d: %s", page_index,
            color_calibration.raw_divergence_warning_message(raw_divergence))
        emis += 1
    acceptance = result.acceptance
    if acceptance is not None and color_metrics.max_degradation_exceeds(
            acceptance.max_degradation_de76):
        logger.warning(
            "Page %d: %s", page_index,
            color_calibration.max_degradation_warning_message(
                acceptance, page_id=page_id))
        emis += 1
    return emis


def _page_identifier(payload: dict) -> str:
    """Nommer **une page** du lot, de facon stable et lisible par l'operateur.

    Le payload ne porte pas d'identifiant de page: il porte un `lot_id` de niveau lot et
    un `page_index` de niveau page (`io.reconstruction._LOT_LEVEL_FIELDS`), et c'est leur
    couple qui designe une feuille sans ambiguite dans un projet a plusieurs lots.

    Ce nom voyage deux fois: dans le refus de divergence (« rescannez **cette** page »,
    `EPIC5-ARB-57`) et au manifest, comme `correction_source_page_id`. Un compteur local
    ou un rang de lecture ne conviendrait ni pour l'un ni pour l'autre: le rang change
    d'un scan a l'autre, et l'operateur ne l'a pas sous les yeux.
    """
    # Story 5.23 (AC 8ter): une **page de calibration** ne porte plus de `lot_id` --
    # elle sert une chaine de scan, pas un lot. L'acces nu levait ici une `KeyError`
    # hors de tout bloc de capture: `scan ... calibrate` mourait en traceback sur une
    # feuille parfaitement lisible. Quatrieme acces nu de cette famille, apres les
    # trois fermes en meme temps que l'epuration -- et le seul que la suite n'a pas
    # attrape, faute d'un test qui fasse passer une VRAIE page de calibration epuree
    # par ce chemin.
    #
    # Le repli nomme la chaine plutot que le lot: c'est ce que la feuille designe, et
    # `correction_source_page_id` doit rester lisible par l'operateur qui a la feuille
    # sous les yeux.
    lot_id = payload.get("lot_id")
    if lot_id is None:
        libelle = payload.get(payload_io.SCAN_CHAIN_LABEL_FIELD) or "chaine-inconnue"
        return f"{naming.normalize_identifier(libelle)}-p{payload['page_index']}"
    return f"{lot_id}-p{payload['page_index']}"


def _rectified_page(project_dir: Path, detected, dpi: int):
    """Relire les pixels d'une page detectee et rendre son raster **redresse**.

    Extrait de `_scanned_pages_for_output` pour que la page de calibration passe par le
    **meme** chemin que les planches d'images: deux redressages ecrits separement
    divergeraient, et la correction du lot serait alors ajustee sur une geometrie qui
    n'est pas celle qu'on corrige.

    Les pixels viennent du point d'entree publie par l'ingestion (`load_page_array`),
    jamais d'un `cv2.imread` local.
    """
    image = scan_ingest.load_page_array(
        project_dir,
        scan_ingest.PageLocator(
            source_path=detected.locator_source,
            page_index=detected.locator_page_index,
        ),
        dpi=dpi,
    )
    return scan_crop.warp_detected_page(
        image,
        np.asarray(detected.homography, dtype=float).reshape(3, 3),
        detected.page_size_px,
    )


def import_designated_profile(project_dir: Path, source: Path, logger, *,
                              confirm_overwrite=None) -> dict | None:
    """Valider le profil **designe par l'operateur** et le verser au projet courant.

    Story 5.23, AC 12 (`EPIC5-ARB-83`, decisions 1 et 6). C'est le remplacement de
    `_consign_external_profile` de la story 5.22, et le changement porte sur ce qui a
    **disparu**: l'ancienne version consignait le fichier sous l'identite de chaine
    **derivee de ce scan-ci**, et refusait tout profil dont le `chain_id` differait.
    Cette comparaison etait le dernier appariement automatique du chemin de scan. Elle
    est mesuree defaillante sur le materiel d'Egan -- tags scanner absents, deux
    scanners rendant `600-tiff-e2168f9b2b81` --, si bien qu'elle acceptait le mauvais
    profil et refusait le bon, dans les deux cas en silence.

    Ce qui la remplace n'est pas une comparaison meilleure: c'est **aucune
    comparaison**. Le profil designe est celui qui s'applique, il est ecrit sous **son
    propre** `chain_id` (un nom de fichier, pas une cle), et sa provenance est ecrite au
    manifest sans rien decider.

    **Aucun refus lie au projet** (`EPIC5-ARB-82`): un profil venu d'un autre projet est
    verse ici sans un mot sur son origine. Rend `None` -- apres l'avoir dit -- quand le
    fichier est illisible, refuse, ou non consignable; le lot suit alors le regime brut
    et le journal dit pourquoi.
    """
    try:
        # **`record=False`**: l'entree de manifest est reposee par l'appelant une fois
        # la passe persistee. Un projet neuf n'a pas encore de `project.json` ici, et
        # surtout un echec d'ecriture du manifest ne doit pas remonter jusqu'a tuer un
        # scan dont les frames sont extractibles (famille du bloquant `C2`, revue 5.22).
        document, chemin = profile_designation.import_designated_profile(
            project_dir, source, record=False,
            confirm_overwrite=confirm_overwrite)
    except profile_designation.ProfileDesignationError as exc:
        # **Jamais un repli** ici: ni sur un profil deja present dans le projet, ni sur
        # le premier fichier de `versions/calibration/`. Un profil designe qu'on ne
        # sait pas lire laisse le lot brut, ce que l'operateur voit et corrige; un
        # repli lui ferait croire que sa designation a ete honoree.
        logger.error(
            "%s Le lot est livre en brut; corrigez le fichier ou regenerez le profil "
            "avec `scan ... calibrate`.", exc)
        return None
    logger.info(
        "Profil designe applique et verse au projet: %s (chaine '%s', forme %s, ajuste "
        "sur la page %s, %d pastille(s) lue(s), %d retenue(s)). Fichier du projet: %s",
        source, document["chain_id"], document["correction_form_id"],
        document["source_page_id"], document["read_patch_count"],
        document["retained_patch_count"], chemin)
    return document


def profil_designe_du_projet(project_dir: Path, logger, *,
                             profil_explicite=None) -> tuple:
    """Le profil que l'operateur a designe, et **par quel geste**. AC 12.

    Precedence, et elle n'a qu'un sens possible: `--profil` l'emporte sur le defaut du
    projet. L'inverse rendrait le defaut irrevocable -- l'operateur aurait ecrit un
    chemin sur la ligne de commande et le projet en aurait applique un autre --, ce qui
    est exactement « la machine devine », avec un geste explicite ignore en prime.

    Rend le couple `(chemin, origine)`, ou `origine` est `None` quand rien n'est
    designe. La resolution du defaut passe par le **chemin ecrit dans l'entree de
    manifest**, jamais par une recomposition depuis le `chain_id`.
    """
    explicite = profil_explicite
    if explicite is not None:
        return Path(explicite), "designe en ligne de commande"
    par_defaut = profile_designation.default_profile_path(project_dir)
    if par_defaut is not None:
        return par_defaut, "pris au defaut du projet"
    return None, None


def _resolve_designated_correction(project_dir: Path, source, logger, *,
                                   correction_requested: bool,
                                   origine: str | None = None,
                                   confirm_overwrite=None):
    """La correction du profil **designe**, ou `None` avec l'avertissement de l'AC 12.

    Story 5.23, AC 12. Trois proprietes, et chacune ferme un chemin par lequel la
    machine se remettrait a deviner:

    * **rien n'est designe -> avertissement et lot livre en brut** (`EPIC5-ARB-83`,
      decision 5; Egan, note 8: « Oui bon comportement. Avertissement. »). Jamais un
      refus de commande, et surtout **jamais un repli** vers un profil trouve dans le
      projet: choisir a la place de l'operateur reintroduirait le defaut que cette
      story supprime, sous une forme plus difficile a voir que la derivation;
    * le profil designe est **applique tel quel**, quelle que soit la chaine qu'il
      declare et quel que soit le projet d'ou il vient;
    * le `chain_id` n'est **compare a rien** sur ce chemin. Il descend dans la
      correction (`chain_correction_from_document` le lit dans le document) comme
      identite et provenance, et il ne choisit plus rien.
    """
    if source is None:
        # **`EPIC5-ARB-103`: aucun profil par defaut au projet, ca se dit -- et le
        # message nomme le geste.** Mots d'Egan: « s'il n'y a pas de profil par defaut
        # au projet on devrait aussi le dire et proposer un scan brut ou inviter a
        # designer un profil par defaut ». L'avertissement existait deja
        # (`EPIC5-ARB-83` decision 5); ce qui manquait est qu'il pose le **choix**
        # plutot que de constater une absence. Il dit donc trois choses, dans cet
        # ordre: ce qui vient de se passer (le lot est livre brut, et c'est une issue
        # legitime, pas un echec), puis les deux gestes qui s'en ecartent, chacun avec
        # sa commande complete.
        #
        # **Le comportement ne change pas d'un cran** (`EPIC5-ARB-103`, et c'est la
        # moitie de la decision): jamais un refus, jamais un repli automatique vers un
        # profil trouve dans le projet. Seul le message s'enrichit. Un repli
        # reintroduirait ici, sous une forme plus difficile a voir que la derivation, le
        # defaut que `EPIC5-ARB-83` supprime.
        logger.warning(
            "Aucun profil de calibration designe pour ce scan, et ce projet n'en a "
            "aucun par defaut: le lot est livre **en brut** -- les frames sont ecrites "
            "telles quelles (correction non appliquee) et le manifest le declare. "
            "C'est une issue legitime, pas un echec. Trois suites possibles, au "
            "choix: (1) garder le scan brut, il n'y a rien a faire; (2) rescanner en "
            "designant le profil pour ce seul scan (`%s <fichier>`); (3) poser une fois "
            "pour toutes le profil par defaut du projet (`%s --project <projet> %s "
            "<fichier>`), que les scans suivants prendront sans rien taper. Aucun "
            "profil n'est choisi a votre place: un profil devine est exactement ce que "
            "cette version supprime.",
            PROFILE_FLAG, SET_DEFAULT_PROFILE_COMMAND, PROFILE_FLAG)
        return None
    if origine is not None:
        logger.info("Profil de calibration %s: %s", origine, source)
    document = import_designated_profile(
        project_dir, Path(source), logger,
        confirm_overwrite=confirm_overwrite)
    if document is None:
        return None
    return color_calibration.chain_correction_from_document(
        document, correction_requested=correction_requested)


def _declared_calibration_pages(report) -> list:
    """Les pages dont le payload **declare** le role de calibration, geometrie a part.

    `EPIC5-ARB-70`. La distinction avec `_read_calibration_pages` est ce que le code
    **sait**: ici le QR a livre son payload, donc le lot sait que cette feuille est sa
    page de calibration, meme s'il ne peut pas l'echantillonner. Une page de calibration
    dont le QR n'a rien livre, elle, n'apparait dans aucune des deux listes -- rien ne dit
    qu'elle en est une, et la declarer en echec serait inventer une information.
    """
    return [
        page for page in report.pages
        if page.payload is not None
        and page.payload["page_role"] == page_roles.PAGE_ROLE_CALIBRATION
    ]


def _read_calibration_pages(report) -> list:
    """Les pages de calibration **lues et redressables** du lot, dans l'ordre de lecture.

    Les quatre conditions sont reunies ici plutot que repetees a deux endroits: le role,
    le succes de la detection, la resolution de l'homographie et la presence d'un
    payload. Une page de calibration dont le QR n'a rien livre n'en est pas une du point
    de vue du lot -- rien ne dit qu'elle en est une --, et une dont l'homographie n'est
    pas resolue ne peut pas etre echantillonnee a des positions en millimetres.

    **Ne pas etre echantillonnable n'est pas etre absente** (`EPIC5-ARB-70`): les pages
    ecartees ici pour leur geometrie sont rattrapees par `_declared_calibration_pages`
    chez l'appelant, qui en fait un `failed` motive. Avant l'arbitrage, elles sortaient
    indistinguables d'un lot ou la feuille **manque** -- « aucune page de calibration
    lue » etait dit d'une page qui y etait, et l'operateur allait chercher une feuille
    absente au lieu de rescanner celle qui etait abimee.

    **Deux des quatre conditions sont le meme fait, et c'est demontre** -- les deux couches
    de la revue de la passe de correction en ont tire des conclusions opposees, l'une
    declarant les mutants equivalents et l'autre reclamant un epinglage par condition.
    `DetectedPage` n'a que **deux** sites de construction (`scan_detection._detect_one_page`,
    voie de succes et voie de refus): la premiere pose `status=PAGE_OK` **et** une
    homographie non nulle, la seconde `status=PAGE_REFUSED` et laisse l'homographie a son
    defaut `None`. Donc `status == PAGE_OK` <=> `homography is not None`, et aucun test ne
    peut distinguer le retrait de l'une du retrait de l'autre: reclamer cet epinglage-la
    serait reclamer un test impossible.

    Les deux conditions sont **conservees** parce qu'elles ne disent pas la meme chose au
    lecteur -- l'une est le vocabulaire de la detection, l'autre la precondition de
    `_rectified_page` -- et parce qu'un troisieme site de construction casserait
    l'equivalence en silence. Ce qui est epingle est donc l'**invariant** lui-meme, sur les
    deux voies du vrai detecteur:
    `test_scan_detection.py::test_l_invariant_page_ok_et_homographie_est_le_meme_fait`.
    """
    return [
        page for page in _declared_calibration_pages(report)
        if page.status == scan_detection.PAGE_OK
        and page.homography is not None
    ]


def _fit_lot_correction(project_dir: Path, report, dpi: int, *,
                        correction_requested: bool = True):
    """Ajuster la correction du lot sur sa page de calibration. **Une fois par lot.**

    Story 5.19, AC 1. Rend `None` quand le lot ne porte pas de page de calibration
    exploitee -- feuille absente du scan, QR illisible, geometrie non resolue --, et un
    `LotCorrection` sinon, y compris quand l'ajustement echoue: un echec porte son motif
    et son message, et il faut pouvoir les distinguer de « aucune page de calibration »
    (AC 4 et 8, `not_applied` contre `failed`).

    `correction_requested` (`--cc off`, `EPIC5-ARB-78`) est **transmis tel quel** a
    chaque `LotCorrection` construit ici, y compris sur un echec: c'est une decision de
    **lot**, connue avant meme que la page de calibration ne soit lue, et elle doit
    voyager avec l'objet qui represente le lot plutot que par un second parametre que
    `calibration_page_result` devrait recevoir a part (deuxieme passe de revue,
    2026-08-14).

    **Le balayage cherche la page par son role, jamais par son rang.** Le contrat de
    `page_roles` veut que la page de calibration porte `page_index = 0`, mais elle
    n'arrive pas forcement premiere au scanner -- l'operateur empile ses feuilles comme il
    veut, et le rang de lecture est ce que `read_rank` enregistre precisement parce qu'il
    ne coincide pas avec l'index. Prendre `report.pages[0]` marcherait sur toutes les
    piles bien rangees et corrigerait tout un lot avec le treillis d'une planche
    d'images sur les autres.

    Une **seconde** page de calibration dans le meme lot est un lot melange: on refuse
    plutot que de choisir, parce que choisir voudrait dire ajuster la correction du lot
    sur une feuille prise au hasard entre deux.
    """
    calibration_pages = _read_calibration_pages(report)
    if not calibration_pages:
        perdues = _declared_calibration_pages(report)
        if perdues:
            # `EPIC5-ARB-70`: le role est **connu** et la geometrie est perdue. Declarer
            # une absence serait mentir, et c'est la panne la plus probable des deux --
            # une feuille cornee, un marqueur d'angle abime. Le lot ressort donc `failed`
            # avec un motif du vocabulaire ferme et un geste qui nomme **cette** feuille,
            # comme le fait deja le cas symetrique ou les pastilles ne se lisent pas.
            source_page_id = _page_identifier(perdues[0].payload)
            return color_calibration.LotCorrection(
                source_page_id=source_page_id,
                template_id=perdues[0].payload["template_id"],
                failure_reason=color_calibration.FAILURE_PAGE_GEOMETRY_UNRESOLVED,
                failure_message=(
                    f"Page de calibration '{source_page_id}' presente mais non "
                    "redressable: sa geometrie n'a pas ete resolue (statut "
                    f"'{perdues[0].status}'). Aucune correction de lot n'a pu etre "
                    "ajustee, donc les frames sont ecrites telles quelles; rescannez "
                    "cette feuille -- les planches d'images de ce lot, elles, n'ont "
                    "rien a se reprocher."
                ),
                correction_requested=correction_requested,
            )
        return None
    if len(calibration_pages) > 1:
        raise scan_ingest.ScanIngestError(
            f"{len(calibration_pages)} pages de calibration lues dans ce lot "
            f"(index {sorted(page.payload['page_index'] for page in calibration_pages)}). "
            "Un lot porte **une** page de calibration: en choisir une ajusterait la "
            "correction de tout le lot sur une feuille prise au hasard entre deux. "
            "Verifiez que deux lots n'ont pas ete melanges dans le meme dossier de scan."
        )
    detected = calibration_pages[0]
    payload = detected.payload
    source_page_id = _page_identifier(payload)
    try:
        rectified = _rectified_page(project_dir, detected, dpi)
    except (scan_crop.ScanCropError, scan_ingest.ScanIngestError):
        # Une page de calibration dont les pixels ne se relisent pas est **illisible** au
        # sens de l'AC 9: le lot n'a pas de correction, et ce n'est pas une divergence.
        return color_calibration.LotCorrection(
            source_page_id=source_page_id,
            template_id=payload["template_id"],
            failure_reason=color_calibration.FAILURE_PATCHES_NOT_FOUND,
            failure_message=(
                f"Page de calibration '{source_page_id}' non relisable: son raster ne "
                "se redresse pas. Aucune correction de lot n'a pu etre ajustee, donc "
                "les planches de ce lot sont ecrites non corrigees et le declarent."
            ),
            correction_requested=correction_requested,
        )
    return color_calibration.fit_lot_correction_from_page(
        rectified,
        template_id=payload["template_id"],
        dpi=dpi,
        source_page_id=source_page_id,
        correction_requested=correction_requested,
        # **Le preset du lot, transmis pour le bandeau de temoins** (story 5.23, AC 2).
        # Il vient du payload et non d'une constante: `patch_preset_id` est un champ de
        # niveau lot, donc la page de calibration declare exactement celui de ses
        # planches -- c'est ce qui rend les deux jeux appariables par identifiant.
        patch_preset_id=payload["patch_preset_id"],
    )


def _scanned_pages_for_output(project_dir: Path, report, dpi: int, *,
                              lot_correction=None,
                              divergence_bypass: bool = False,
                              apply_correction: bool = True,
                              chain_id: str | None = None) -> tuple:
    """Transformer les pages detectees (5.2) en pages a ecrire (5.6).

    Rend le couple `(pages, calibrations)`, ou `calibrations` est la suite des couples
    ``(page_index, PageCalibration)`` des planches d'images confrontees a la correction
    du lot. Les deux sont rendus ensemble et non par deux passes, parce que les deux
    consomment le **meme** raster redresse: le calculer deux fois doublerait la lecture
    disque et le redressage de chaque planche du lot.

    `lot_correction` est la correction ajustee **une seule fois** sur la page de
    calibration (`_fit_lot_correction`). Quand elle est disponible, chaque planche
    d'images la recoit par `imported_profile` -- donc **aucune planche n'est ajustee sur
    ses propres pastilles**, ce qui est la clause centrale d'`EPIC5-ARB-57`. Quand elle
    ne l'est pas, aucune calibration n'est calculee du tout: le repli n'est pas
    « s'ajuster sur soi-meme », c'est « ne pas corriger et le declarer ».

    `apply_correction` porte le choix de l'operateur (`--cc off`, `EPIC5-ARB-78`) et il
    fait ici **exactement** ce que fait une correction indisponible: aucune planche n'est
    calibree, donc aucune n'est corrigee. Il ne se traduit surtout pas par « calibrer sans
    profil importe », qui ferait ajuster chaque planche sur ses propres pastilles --
    c'est-a-dire le re-ajustement par page qu'`EPIC5-ARB-57` interdit, reintroduit par la
    porte d'un drapeau cense ne rien appliquer du tout. Ce qui distingue les deux regimes
    n'est donc pas ce qui est fait aux pixels (rien, des deux cotes) mais ce qui est
    **declare**, et cela se joue sur l'entree de la page de calibration.

    La commande **conserve les payloads decodes entre les etapes** (point H4
    des arbitrages): ils viennent de `DetectedPage.payload`, pose au decodage,
    et ne sont jamais re-decodes ici -- deux lectures du meme QR pourraient
    diverger, et c'est l'appariement page <-> frames qui en paierait le prix.

    Trois natures de page, et elles ne se confondent pas:

    * page detectee: elle est redressee puis decoupee, et porte ses frames;
    * page **presente** dont la geometrie ou la decoupe a echoue: elle porte un
      motif du vocabulaire ferme de 5.6 et recevra des mires;
    * page dont le QR n'a rien livre: elle ne porte ni frame ni motif -- sans
      timecode il n'y a pas de frame a ecrire, mais un trou a declarer.

    Les pixels viennent du point d'entree publie par l'ingestion
    (`load_page_array`), jamais d'un `cv2.imread` local. Ils sont relus une
    seconde fois, la detection ne rendant pas les images: c'est un cout d'I/O
    assume, pas un second decodage de metadonnee.
    """
    pages = []
    calibrations: list[tuple[int, object]] = []
    for detected in report.pages:
        payload = detected.payload
        if payload is None:
            pages.append(scan_output_frames.ScannedPage(payload=None))
            continue
        if detected.status != scan_detection.PAGE_OK or detected.homography is None:
            pages.append(
                scan_output_frames.ScannedPage(
                    payload=payload, failure="page_detection_failed"
                )
            )
            continue
        if payload["page_role"] == page_roles.PAGE_ROLE_CALIBRATION:
            # **Quatrieme nature de page** (story 5.16): la page de calibration du lot.
            # Elle ne porte aucune frame, donc il n'y a rien a decouper -- et surtout
            # rien a remplacer. Sans cette branche, `build_page_crop_plan` refusait ses
            # `slots` vides, le refus etait rattrape en `frame_crop_failed`, et la page
            # recevait des **mires**: une page parfaitement lue serait declaree en echec
            # et son treillis remplace par des frames de synthese. C'est le faux echec
            # symetrique du faux succes que ce module combat partout ailleurs.
            #
            # Elle reste une page **presente** du lot: son payload part au manifest, donc
            # elle sort de `missing_pages` et son absence, elle, serait signalee.
            pages.append(
                scan_output_frames.ScannedPage(
                    payload=payload, crop_plan=None, frames=()
                )
            )
            continue
        try:
            warped = _rectified_page(project_dir, detected, dpi)
            plan = scan_crop.build_page_crop_plan(
                template_id=payload["template_id"], slots=payload["slots"], dpi=dpi
            )
            frames = tuple(scan_crop.crop_frames(warped, plan))
        except (scan_crop.ScanCropError, scan_ingest.ScanIngestError) as error:
            # Le motif est celui du vocabulaire ferme de 5.6, jamais la prose de
            # l'exception: une chaine libre glissee ici casserait le contrat de
            # marquage que 5.7 persiste.
            del error
            pages.append(
                scan_output_frames.ScannedPage(
                    payload=payload, failure="frame_crop_failed"
                )
            )
            continue
        if apply_correction and lot_correction is not None and lot_correction.available:
            # **La correction du lot, telle quelle** (`EPIC5-ARB-57`): `imported_profile`
            # est renseigne a chaque appel de ce chemin, et il n'y a aucune branche ou
            # une planche d'images s'ajusterait sur ses propres pastilles. Les pastilles
            # de la planche ne servent plus qu'a **verifier** -- residu, dispersion,
            # verdict d'ecretage et garde de divergence.
            calibrations.append((
                payload["page_index"],
                color_calibration.calibrate_page(
                    warped,
                    template_id=payload["template_id"],
                    patch_preset_id=payload["patch_preset_id"],
                    dpi=dpi,
                    page_id=_page_identifier(payload),
                    imported_profile=lot_correction.profile,
                    imported_source_page_id=lot_correction.source_page_id,
                    # **La provenance est nommee, jamais devinee** (story 5.22): le
                    # profil vient du fichier de la chaine ou d'une page de calibration
                    # presente dans le scan, et seul l'appelant le sait. `chain_id` est
                    # `None` dans le second cas, donc le defaut de `calibrate_page`
                    # -- la page de calibration -- reste celui d'avant la story.
                    imported_correction_source=(
                        color_calibration.CORRECTION_SOURCE_CHAIN_PROFILE
                        if chain_id is not None
                        else color_calibration.CORRECTION_SOURCE_CALIBRATION_PAGE),
                    imported_chain_id=chain_id,
                    divergence_bypass=divergence_bypass,
                    # **La moitie « page de calibration » de la mesure brute a brute**
                    # (story 5.23, AC 2). Les trois regimes -- feuille lue dans cette
                    # passe, profil de chaine portant ses temoins, profil sans temoins --
                    # sont tranches par `calibration_witness_raw_for_lot`, dans le module
                    # qui possede la politique de correction. La distinction « rien a
                    # comparer » (`None`) / « bandeau inexploitable » (mapping vide)
                    # voyage par le **type** et non par un parametre de plus, et dans
                    # aucun des deux cas ce n'est un « ecart nul »: un zero est la lecture
                    # de deux feuilles identiques.
                    calibration_witness_raw=(
                        color_calibration.calibration_witness_raw_for_lot(
                            lot_correction,
                            from_chain_profile=chain_id is not None)),
                ),
            ))
        pages.append(
            scan_output_frames.ScannedPage(
                payload=payload, crop_plan=plan, frames=frames
            )
        )
    return pages, tuple(calibrations)


def _scan_provenance(report) -> tuple:
    """Provenance de scan, page par page, telle que 5.2 l'a vue."""
    return tuple(
        scan_manifest.ScanPageProvenance(
            read_rank=page.read_rank,
            status=page.status,
            qr_status=page.qr_status,
            page_index=page.page_index,
            homography_status=(
                scan_manifest.HOMOGRAPHY_RESOLVED
                if page.homography is not None
                else scan_manifest.HOMOGRAPHY_UNRESOLVED
            ),
        )
        for page in report.pages
    )


# ---------------------------------------------------------------------------
# Story 11.4b, lot S3 (AC 4) -- la couche `manual_corrections` est CONSOMMEE
# ---------------------------------------------------------------------------
#
# **Le constat qui rend cette section necessaire** (fait F4 de la story) : la
# moitie aval recoit `payloads`, un tuple construit par ses trois appelants a
# partir des pages **decodees**. Une identite saisie a la main n'y entrait par
# aucun chemin : elle etait ecrite au document de detection par
# `poser_les_identites`, puis **ignoree**. L'operatrice voyait un succes et
# n'obtenait pas ses frames -- c'est litteralement le risque R12, un faux
# succes. Symetriquement, `poser_les_coins` ecrivait une geometrie corrigee que
# le recadrage ne relisait jamais.
#
# Ce que la consommation NE fait PAS : elle ne reecrit pas le document de
# detection et n'en resigne pas l'empreinte. `fingerprints.detection` continue
# de signer **ce que la machine a lu** (`EPIC7-ARB-95`) ; les corrections
# vivent a cote et decident ce qui est **ecrit**. C'est aussi pourquoi le motif
# de refus d'une planche dont les coins ont ete reposes reste inscrit sur elle :
# seul son `status` change, parce que c'est lui, et lui seul, que la moitie
# aval lit pour savoir si une page porte une geometrie exploitable.


def _modele_de_completion(payloads, lot_id: str, saisie: dict | None = None) -> dict:
    """Le payload **decode** d'une autre planche du MEME lot.

    `payload_depuis_l_identite` a besoin des huit champs neutres du lot
    (`scan_corrections.CHAMPS_NEUTRES_DU_LOT`) : l'operatrice ne les lit pas sur
    le papier -- ni la cadence cible, ni la base de timecode, ni le preset de
    pastilles, ni l'espace de sortie -- et le depot refuse de les deviner
    (`EPIC6-ARB-6`). Une pile mixte porte au moins une planche lue, et c'est
    elle qui dit ce que la muette ne dit pas.

    **L'appariement se fait par `lot_id`, jamais par position.** Rendre le
    premier payload venu completerait une planche avec les valeurs neutres d'un
    autre lot -- c'est-a-dire ecrire les frames d'une planche a la cadence d'une
    autre, sans un mot. C'est le mutant `M25` de la story 5.7, dont la
    consequence reelle etait d'ecrire les cardinaux sur le mauvais lot.
    Une page de calibration ne porte pas de `lot_id` (story 5.23, AC 8bis) :
    elle est donc naturellement ecartee par ce filtre, sans branche dediee.

    Le refus est **nomme** plutot que muet : sans planche lue du meme lot, rien
    sur la machine ne porte ces valeurs. C'est le regime 2 d'`EPIC11-ARB-64`,
    et la story 11.4b, lot S4 (AC 5) lui donnera sa seconde source -- le
    manifeste du projet -- sans changer ce contrat.

    **`saisie` est la TROISIEME source** (`EPIC11-ARB-106`, Egan 2026-08-31 :
    « si le lot n'est pas au manifeste il faut rentrer tous les champs
    manuellement »). Elle vient en DERNIER : une planche lue de la meme pile
    est toujours plus sure qu'une retranscription a la main. Sans elle, le
    refus ci-dessous n'offrait RIEN -- un blocage sec d'autant plus dur que la
    feuille, elle, porte l'information.
    """
    for payload in payloads:
        if payload.get("lot_id") == lot_id:
            return payload
    # TROISIEME SOURCE : la SAISIE (`EPIC11-ARB-106`). Elle vient en dernier et
    # jamais en premier -- une planche lue de la meme pile est toujours plus
    # sure qu'une retranscription a la main, et lui preferer la saisie ferait
    # entrer une faute de frappe la ou la machine avait la valeur exacte.
    if saisie is not None:
        modele = scan_corrections.modele_saisi(saisie)
        modele.setdefault("lot_id", lot_id)
        return modele
    raise scan_corrections.IdentiteIncompletable(
        f"aucune planche lue du lot {lot_id!r} dans cette pile: les valeurs "
        f"neutres du lot ({', '.join(scan_corrections.CHAMPS_NEUTRES_DU_LOT)}) "
        "ne se lisent pas sur le papier et ne se devinent pas. DEUX issues: "
        "scanner cette planche avec au moins une planche du meme lot dont le QR "
        "est lisible; ou fournir ces valeurs a la main -- elles sont TOUTES "
        "lisibles sur la planche imprimee (pied technique, bloc d'identite, "
        "en-tete). Le refus de deviner ne change pas: une saisie incomplete est "
        "refusee comme l'est une pile sans planche lue."
    )


def consommer_les_corrections_manuelles(detection, payloads, *, corrections,
                                        dpi: int, logger=None, saisie_du_lot=None):
    """Lire la couche `manual_corrections` et la faire entrer dans l'ecriture.

    Rend le couple `(detection, payloads)` que la suite de la sequence
    consomme. `corrections` est le **document de detection** portant la couche
    (n'importe quel objet JSON : c'est `scan_corrections` qui le verifie), ou
    `None` -- et `None` ne change **rien**, ce qui est le regime de tous les
    appelants d'aujourd'hui.

    Deux consommations, une par liste de la couche :

    * les **identites** (`poser_les_identites`) deviennent des payloads par
      `payload_depuis_l_identite`, et le tuple rendu les porte : une planche
      muette completee produit donc ses frames, ce que l'absence de payload lui
      interdisait (`_scanned_pages_for_output` rend une `ScannedPage` sans
      frame ni motif pour une page sans payload) ;
    * les **coins** (`poser_les_coins`) decident l'homographie de **leur**
      planche par `homographie_depuis_les_coins`, point unique du depot ou une
      correction devient de la geometrie -- l'interface la calcule pour montrer
      le resultat a l'ecran, l'ecriture la recalcule pour decouper les pixels,
      et une seconde redaction divergerait sans que rien ne le montre avant les
      TIFF produits.

    **Aucune correction posee ne peut etre silencieusement ignoree** (AC 4.3) :
    une correction qui nomme un rang de lecture absent de la pile, ou des coins
    poses sur une planche dont aucun gabarit n'est connu, sont **refuses** avec
    leur motif. Le silence serait le faux succes que cette story ferme.

    L'appariement se fait par `read_rank`, l'adresse que la couche emploie, et
    **jamais par position** : les rangs de lecture d'un lot trie ne sont pas
    contigus, et une correction appliquee a la mauvaise planche produit
    exactement le meme succes apparent.
    """
    logger = logging.getLogger(__name__) if logger is None else logger
    if corrections is None:
        return detection, payloads
    identites = scan_corrections.lire_les_identites(corrections)
    coins = scan_corrections.lire_les_coins(corrections)
    if not identites and not coins:
        # Un document sans couche, ou une couche vidée, rend le couple entre
        # tel quel -- le meme objet, pas une copie reconstruite : le regime sans
        # correction ne doit pas dependre d'une seconde redaction du tuple.
        return detection, payloads

    rangs_de_la_pile = {page.read_rank for page in detection.pages}
    orphelines = sorted((set(identites) | set(coins)) - rangs_de_la_pile)
    if orphelines:
        raise scan_corrections.CorrectionInvalide(
            f"corrections posees sur des planches absentes de cette pile "
            f"(rangs de lecture {orphelines}, presents "
            f"{sorted(rangs_de_la_pile)}): rien ne serait ecrit pour elles et "
            "l'ecriture se declarerait reussie. Le document de correction et "
            "la pile scannee ne sont pas ceux du meme passage."
        )

    pages = []
    for page in detection.pages:
        champs = {champ.name for champ in dataclasses.fields(page)}
        changements: dict = {}
        payload = page.payload
        identite = identites.get(page.read_rank)
        if identite is not None:
            if payload is not None:
                # La saisie d'une operatrice sur une planche qui avait pourtant
                # livre son QR n'est pas un cas impossible: c'est une identite
                # **affirmee par un humain**, et la garder pour soi la rendrait
                # inoperante la ou elle sert. Elle prime, et le journal le dit
                # -- « le jour ou un timecode est faux, il faut savoir qui l'a
                # dit » (`EPIC7-ARB-103`).
                logger.warning(
                    "Planche de rang de lecture %d: l'identite saisie a la "
                    "main remplace le payload decode de son QR.",
                    page.read_rank)
            payload = scan_corrections.payload_depuis_l_identite(
                identite,
                # **La TROISIEME source est enfin joignable** (`EPIC11-ARB-106`,
                # trouve en revue, couches 2 et 3). `_modele_de_completion`
                # l'acceptait depuis son ecriture, mais son unique appelant ne
                # la passait pas et aucun parametre ne la transportait: le
                # refus annoncait « ou fournir ces valeurs a la main », une
                # issue qu'aucun chemin de production ne savait executer. Le
                # message mentait donc a l'operateur, ce qui est pire que
                # l'ancien refus a une seule issue.
                modele=_modele_de_completion(
                    payloads, identite.lot_id, saisie=saisie_du_lot))
            changements["payload"] = payload
            if "page_index" in champs:
                changements["page_index"] = payload["page_index"]
            logger.info(
                "Correction manuelle consommee: la planche de rang de lecture "
                "%d recoit l'identite saisie (lot %s, planche %d, %d frame(s), "
                "provenance %s).",
                page.read_rank, identite.lot_id, identite.page_index,
                identite.frames_per_page, identite.provenance)
        quadrilateres = coins.get(page.read_rank)
        if quadrilateres is not None:
            if payload is None:
                raise scan_corrections.CorrectionInvalide(
                    f"coins corriges poses sur la planche de rang de lecture "
                    f"{page.read_rank}, dont aucun gabarit n'est connu: son QR "
                    "n'a rien livre et aucune identite n'a ete saisie pour "
                    "elle. Le redressement se calcule sur les coins NOMINAUX "
                    "du gabarit; sans lui, il n'y a pas de destination. "
                    "Saisissez l'identite de cette planche avant d'en corriger "
                    "la geometrie."
                )
            template_id = payload["template_id"]
            homographie, _echelle = scan_corrections.homographie_depuis_les_coins(
                quadrilateres, template_id=template_id, dpi=dpi)
            geometrie = scan_detection.resolve_page_geometry(template_id, dpi)
            changements["homography"] = tuple(
                float(valeur) for valeur in np.asarray(homographie).ravel())
            changements["page_size_px"] = geometrie["page_size_px"]
            # **Seul le `status` change**, et c'est ce que la moitie aval lit
            # pour savoir si une page porte une geometrie exploitable. Le motif
            # de refus, lui, reste inscrit sur la page: la correction ne reecrit
            # pas ce que la machine a lu, elle decide ce qui est ecrit
            # (`EPIC7-ARB-95`, meme doctrine que l'empreinte non resignee).
            changements["status"] = scan_detection.PAGE_OK
            logger.info(
                "Correction manuelle consommee: la planche de rang de lecture "
                "%d est redressee sur les quatre coins reposes a la main "
                "(gabarit %s, %d ppp).", page.read_rank, template_id, dpi)
        pages.append(
            dataclasses.replace(
                page, **{cle: valeur for cle, valeur in changements.items()
                         if cle in champs})
            if changements else page)
    pages = tuple(pages)
    # Le tuple de payloads est **rebati depuis les pages**, et c'est exactement
    # l'expression que les trois appelants ecrivent deja pour le composer
    # (`tuple(page.payload for page in <pages> if page.payload is not None)`):
    # une seconde redaction de l'appariement page <-> payload est precisement
    # ce qui ferait ecrire les frames d'une planche sous l'identite d'une autre.
    return (dataclasses.replace(detection, pages=pages),
            tuple(page.payload for page in pages if page.payload is not None))


def ecrire_le_lot_detecte(project_dir, report, detection, payloads, *,
                          dpi_geometrie, dpi_manifest,
                          overwrite=False,
                          logger=None,
                          appliquer_la_correction=True,
                          livrer_brut=False,
                          divergence_bypass=False,
                          profil_designe=None,
                          origine_du_profil=None,
                          corrections_manuelles=None,
                          rappel_progression=None,
                          demander_l_application_de_la_correction=None,
                          confirmer_l_ecrasement=None,
                          nouvelle_version=False,
                          manifest_du_projet=None,
                          saisie_du_lot=None) -> EcritureDuLot:
    """La moitie aval du chemin de scan: correction, recadrage, frames, manifest.

    Story 11.4b, lot S1 (`EPIC11-ARB-67`): corps **deplace** de
    `cli._ecrire_le_lot_detecte`, jamais reecrit -- meme geste que la story
    5.26 lui avait deja fait faire depuis `scan_command`. Ce qui a change, et
    rien d'autre: l'objet `args` argparse est devenu des parametres nommes,
    les quatre `print(..., file=sys.stderr)` sont devenus des `raise`, et le
    code de sortie est devenu un :class:`EcritureDuLot`.

    :param project_dir: le dossier projet ouvert.
    :param report: le rapport d'ingestion (ou son equivalent structurel lu
        d'un document de detection). Trois champs sont lus: `ingest_slug`,
        `scans_dir`, `pages`.
    :param detection: le rapport de detection du lot, ou son equivalent lu
        d'un document.
    :param payloads: les payloads des pages **identifiees** du lot, verbatim.
    :param dpi_geometrie: le DPI qui a decide l'homographie et les zones
        (`scan_dpi_detection` d'un document de detection). Le recadrage s'y
        rejoue.
    :param dpi_manifest: le DPI qui part au manifest comme `scan_dpi`
        (`scan_dpi_declared`). Les deux valent le `--dpi` declare sur le
        chemin `scan` d'un bloc, et divergent legitimement sur un document.
    :param overwrite: l'ecrasement demande, transmis tel quel a
        `check_scan_conflicts` et a `write_lot_output_frames`.
    :param logger: journal de la passe. Optionnel, comme sur
        `run_scan_detect`: la CLI passe le sien (`logs/scan.log`), une
        interface n'en passe aucun et le journal du module suffit. Le
        PARAMETRE ne change aucun comportement observable.
    :param appliquer_la_correction: la decision d'appliquer la correction
        couleur aux pixels (`--cc on|off`, `EPIC5-ARB-78`). La correction est
        **ajustee quand meme** quand il vaut faux -- c'est ce qui permet au
        manifest de dire qu'il y en avait une --, elle n'est simplement pas
        posee.
    :param livrer_brut: le refus explicite de l'operateur
        (`color_calibration.RAW_OUTPUT_FLAG`, `EPIC5-ARB-82` decision 6).
        Il rejoint `--cc off` sur le **meme** motif de manifest, et coupe
        l'invite: qui l'a tape a deja repondu.
    :param divergence_bypass: le contournement **demande** de la garde de
        divergence, confronte au contournement constate par 5.7.
    :param profil_designe: le chemin du profil de calibration designe, ou
        `None`. Il se resout avec :func:`profil_designe_du_projet`, qui
        possede la precedence `--profil` puis defaut du projet.
    :param origine_du_profil: par quel geste ce profil a ete designe, pour le
        journal. `None` quand rien n'est designe.
    :param corrections_manuelles: le **document de detection** portant la
        couche `manual_corrections` (`scan_corrections`), ou `None`. Les
        identites saisies completent les payloads et les coins reposes
        decident l'homographie de leur planche, **avant tout le reste** --
        voir :func:`consommer_les_corrections_manuelles`. `None` ne change
        rien, ce qui est le regime de tous les appelants qui n'en posent
        aucune.
    :param rappel_progression: le canal de progression de l'ECRITURE des
        frames (story 11.4b, lot S5, AC 9.1). Il descend tel quel a
        `scan_output_frames.write_lot_output_frames`, qui l'ouvre dans un
        `progression.EmetteurProgression` -- **aucun second mecanisme** n'est
        redige ici. Un jalon par frame reellement ecrite, `total` valant
        `len(planned)`, et **aucun jalon avant la premiere ecriture** : tous
        les refus durs de cette sequence -- consommation des corrections,
        recadrage, `check_scan_conflicts`, resolution du gabarit, refus
        d'ecrasement -- precedent la boucle, et un refus ne doit produire
        aucune progression (`EPIC7-ARB-79`, story 5.28).

        **`AR3` : il est OPTIONNEL et son absence ne change RIEN a
        l'observable** -- memes frames, meme manifest, memes exceptions. Ce
        n'est pas une clause de style : un rappel qui s'eteint en silence
        quand on lui passe le mauvais type n'est pas optionnel, il est casse.
        `EmetteurProgression.__init__` fait `rappel if callable(rappel) else
        None`, donc un objet non appelable part `actif is False`, sans lever et
        sans trace -- barre figee a `0/N`. Le defaut a ete paye cote extraction
        le 2026-08-30 (`SurfaceExecution.emetteur()` rendait un objet non
        appelable) et il valait un bloquant. Le banc mesure donc les **deux**
        regimes, et mesure que le canal est **actif** quand un rappel est
        fourni -- pas seulement qu'il ne plante pas.
    :param demander_l_application_de_la_correction: le **troisieme regime** de
        l'invite `Y/N`, et le seul qui pose une question a un humain. Appele
        sans argument, il rend un booleen. `None` -- le defaut -- veut dire
        « personne pour repondre »: aucune invite, et la correction est
        appliquee, ce qui est exactement le regime des scripts, de la CI et de
        cette suite de tests. **Ce module ne lit jamais `stdin` lui-meme**
        (AC 2.1): sous une boucle d'evenements, un appel bloquant sur `stdin`
        gele l'interface entiere (`EPIC7-ARB-106`, paye cote GUI avec
        `QMessageBox.exec()`).
    :param confirmer_l_ecrasement: meme forme, pour l'invite d'ecrasement d'un
        profil homonyme (`EPIC5-ARB-99`). `None` = personne pour repondre, et
        le profil entrant prend alors une empreinte differenciante plutot que
        d'ecraser.

    Rend un :class:`EcritureDuLot`. **Ne rend jamais de code de sortie et
    n'imprime rien**: les refus sont **leves** et la table qui les convertit
    en code de sortie est :data:`CODES_DE_SORTIE`, lue des deux cotes.

    Ce qui suit est le texte du premier deplacement, garde parce qu'il porte
    les invariants du geste et non sa geographie -- les numeros de ligne qu'il
    cite valent au baseline de la story 5.26, pas ici.

    Story 5.26 (AC 2): corps **deplace** de `scan_command` (`cli.py:1994-2402`
    au baseline), jamais reecrit -- une seule redaction du geste, appelee par
    `scan_command` ET par la commande d'ecriture (`scan-write`), sur le modele
    de `_consigner_le_profil_de_chaine`. Les trois seuls ecarts au corps
    d'origine sont les parametres de DPI: `dpi_geometrie` rejoue le recadrage
    au DPI qui a decide l'homographie et les zones (`scan_dpi_detection` d'un
    document de detection), `dpi_manifest` part au manifest comme `scan_dpi`
    (`scan_dpi_declared`) -- les deux valent `args.dpi` sur le chemin `scan`.

    L'ordre d'EPIC5-ARB-34 voyage avec le corps: `check_scan_conflicts` avant
    `write_lot_output_frames` avant `persist_scan` -- un refus qui arrive apres
    une destruction n'est pas un refus. `check_scan_conflicts` est reexecute
    ici meme quand `scan detect` l'a deja passe: le manifest a pu changer entre
    detect et write, et ce refus-la ne se juge qu'au moment de l'ecriture.

    Les gardes AR2 (`KeyboardInterrupt`, `OSError`) restent chez les
    appelants: chaque commande porte son propre message d'interruption, et une
    exception levee ici les traverse telle quelle.

    Le repli « page de calibration presente dans le scan »
    (`_fit_lot_correction`) ne peut jamais se satisfaire depuis un document de
    detection: une pile mixte est refusee par `scan detect` (patch 1 de 5.25)
    et une pile de calibration seule ne produit pas de document. Le chemin
    d'ecriture retombe donc naturellement sur profil designe / defaut projet /
    brut declare -- exactement comme un `scan` d'une pile homogene d'images.
    Aucune branche morte n'est ecrite pour ce cas: le producteur du document le
    rend impossible.
    """
    logger = logging.getLogger(__name__) if logger is None else logger
    # **La couche `manual_corrections` est consommee ICI, avant TOUT le reste**
    # (story 11.4b, lot S3, AC 4). La place n'est pas un detail de lecture:
    # c'est le premier geste de la sequence, donc **avant** la premiere ecriture
    # sur le disque -- l'import du profil designe, qui verse un fichier au
    # projet, est deja une ecriture. Une identite incompletable refuse donc
    # avant qu'un seul octet n'ait bouge (AC 4.5), ce qui est la meme doctrine
    # que l'ordre d'`EPIC5-ARB-34` plus bas: « un refus qui arrive apres une
    # destruction n'est pas un refus ».
    # **La saisie voyage DANS le document de corrections** (`EPIC11-ARB-106`,
    # trouve en revue de la vague 3). Le canal `saisie_du_lot` existait mais
    # aucun appelant de production ne le remplissait : le refus promettait donc
    # une issue qu'aucune interface ne savait executer. La saisie est de la
    # meme nature que les coins corriges -- posee par l'interface, consommee
    # par le coeur --, donc elle emprunte le meme chemin plutot que d'ouvrir
    # un second canal pour un meme geste.
    if saisie_du_lot is None and corrections_manuelles is not None:
        saisie_du_lot = scan_corrections.lire_la_saisie_du_lot(corrections_manuelles)
    detection, payloads = consommer_les_corrections_manuelles(
        detection, payloads, corrections=corrections_manuelles,
        # `EPIC11-ARB-106` : « si le lot n'est pas au manifeste il faut rentrer
        # tous les champs manuellement ». La saisie est la TROISIEME source du
        # modele, apres les planches lues du meme lot et le manifeste -- elle
        # vient donc en dernier, et ne sert que si les deux premieres sont
        # muettes.
        saisie_du_lot=saisie_du_lot,
        # Le dpi de la GEOMETRIE, celui qui a decide l'homographie et les zones:
        # les coins sont poses en pixels du scan lu a ce dpi-la, et le redresser
        # au dpi du manifest decalerait la page entiere quand les deux
        # divergent (chemin `scan write` d'un document).
        dpi=dpi_geometrie, logger=logger)
    # `--cc off` (`EPIC5-ARB-78`): la correction est **ajustee quand meme** -- c'est ce qui
    # permet au document de dire qu'il y en avait une -- et n'est simplement pas
    # appliquee. Le drapeau est lu ici, une fois, et descend en booleen: une commande qui
    # relirait `args` plus bas laisserait la porte a deux lectures divergentes du meme
    # choix.
    apply_correction = bool(appliquer_la_correction)
    # **Le refus est le geste explicite** (`EPIC5-ARB-82` decision 6, AC 5 de 5.23), et le
    # drapeau se lit **ici**, avant toute lecture: il ne depend d'aucune mesure, l'operateur
    # qui l'a tape a deja repondu. L'invite interactive, elle, est posee bien plus bas --
    # une fois su qu'il y a effectivement une correction a appliquer, faute de quoi la
    # commande demanderait a un humain de trancher sur une correction qui n'existe pas.
    #
    # Le refus rejoint `--cc off` sur le **meme** motif de manifest, et ce n'est pas une
    # economie de code: les deux disent litteralement la meme chose -- une correction
    # existait, l'operateur a demande qu'elle ne soit pas posee sur les pixels --, et leur
    # donner deux motifs distincts obligerait tout lecteur du manifest a apprendre que
    # deux valeurs signifient un seul fait.
    keep_raw = bool(livrer_brut)
    if apply_correction and keep_raw:
        logger.info(
            "Le lot est livre brut sur demande explicite (%s): aucune invite n'est "
            "posee et le manifest declarera le motif '%s'.",
            color_calibration.RAW_OUTPUT_FLAG,
            color_calibration.NOT_APPLIED_OPERATOR_OPT_OUT)
        apply_correction = False
    # **C'est l'operateur qui designe le profil** (story 5.23, AC 12,
    # `EPIC5-ARB-83`). La correction vient du profil designe -- par `--profil` sur cette
    # commande, ou a defaut par le profil pose au projet --, et **aucune planche de ce
    # lot n'est ajustee sur ses propres pastilles**.
    #
    # Ce que la story 5.22 faisait ici, et qui a disparu: elle **derivait** l'identite de
    # la chaine de scan puis lisait `versions/calibration/<chain_id>.json`. La derivation
    # est mesuree defaillante sur le materiel d'Egan (tags scanner absents, deux scanners
    # rendant le meme `600-tiff-e2168f9b2b81`), donc le mauvais profil s'appliquait en
    # silence. Le defaut n'est pas corrige, **il cesse d'etre possible**: rien sur ce
    # chemin ne compare plus un `chain_id` pour choisir un profil, et l'identite derivee
    # n'est meme plus calculee ici -- la calculer sans s'en servir serait le reste inerte
    # que l'AC 13 vient de retirer ailleurs. Elle reste utile a `scan calibrate`, pour
    # **nommer** ce que cette commande-la produit.
    lot_correction = _resolve_designated_correction(
        project_dir, profil_designe, logger,
        correction_requested=apply_correction,
        origine=origine_du_profil,
        # Le nom du mot-cle est celui de `profile_designation`, qui possede le
        # geste; celui du parametre public est francais parce qu'il est neuf.
        confirm_overwrite=confirmer_l_ecrasement)
    chain_profile_used = lot_correction is not None
    # La provenance ecrite au manifest est celle **du profil applique**, lue dans son
    # document, et jamais l'identite d'un scan: c'est le seul `chain_id` dont ce lot
    # puisse repondre.
    chain_id = lot_correction.chain_id if chain_profile_used else None
    if not chain_profile_used:
        # **Repli sur une page de calibration presente dans le scan** (`AC 10`): un lot
        # imprime avant cette story porte sa page a l'index 0, et l'abandon de
        # l'insertion automatique ne retire pas la **lecture** d'une page presente.
        #
        # L'ordre des deux est ce qui rend la frontiere negative de l'`AC 5` vraie: quand
        # la chaine a son profil, `_fit_lot_correction` n'est **pas atteint**, donc il n'y
        # a aucun chemin par lequel un ajustement a la volee pourrait revenir.
        try:
            lot_correction = _fit_lot_correction(
                project_dir, detection, dpi_geometrie, correction_requested=apply_correction)
        except scan_ingest.ScanIngestError as exc:
            # Le journal garde la PHASE (ce que l'exception seule ne dit pas),
            # et l'exception remonte INCHANGEE: c'est l'enveloppeur qui la met
            # en forme, et un motif recompose ici cesserait d'etre celui du
            # coeur (`EPIC7-ARB-64`, meme contrat que `run_scan_detect`).
            logger.error("Refus avant ecriture: %s", exc)
            raise
        if lot_correction is not None:
            logger.info(
                "Page de calibration lue dans le scan: la correction est ajustee sur "
                "elle (tirage anterieur au profil de chaine).")
    if lot_correction is None:
        # Le lot n'a **reellement** aucune page de calibration: soit la feuille manque du
        # scan, soit son QR n'a rien livre et rien ne dit qu'elle en etait une. Statut
        # `not_applied`, et le lot **reste exploitable** (AC 8). Refuser le lot entier
        # contredirait la clause centrale d'`EPIC5-ARB-57` -- une feuille manque, et
        # refuser ferait perdre les autres.
        #
        # Le message est reste **exactement** celui-ci, et c'est voulu: depuis
        # `EPIC5-ARB-70` il n'est plus dit d'une page presente dont la geometrie a echoue,
        # donc il redevient vrai a la lettre.
        logger.info(
            "Aucune page de calibration lue dans ce lot: les frames sont ecrites "
            "telles quelles et le manifest le declare (correction non appliquee)."
        )
    elif lot_correction.available:
        # **L'invite `Y/N` est posee ICI et nulle part ailleurs** (AC 5 de 5.23), c'est-a-dire
        # une fois su qu'il existe reellement une correction a appliquer. Posee plus haut,
        # elle aurait demande a un humain de trancher sur une correction que le lot n'a
        # pas -- une question dont aucune reponse ne change quoi que ce soit, et qui
        # apprend a repondre sans lire.
        #
        # Trois regimes, et l'ordre entre eux est ce qui empeche l'invite de bloquer un
        # script:
        #
        # 1. `--cc off` ou le drapeau explicite ont deja mis `apply_correction` a `False`
        #    plus haut: rien n'est demande, l'operateur a deja repondu;
        # 2. hors terminal interactif (script, CI, pipe, cron), **aucune invite** n'est
        #    posee et le defaut est appliquer. Une invite qui bloque un script est une
        #    panne, pas une precaution;
        # 3. en terminal interactif seulement, l'invite est posee -- et son defaut est
        #    encore appliquer.
        # **Le troisieme regime entre par un PARAMETRE** (story 11.4b, AC 2.1).
        # Le predicat d'interactivite et l'invite `Y/N` sont restes chez la CLI:
        # ce module ne lit jamais `stdin`, parce que sous une boucle
        # d'evenements un appel bloquant y gele l'interface entiere
        # (`EPIC7-ARB-106`). `None` vaut « personne pour repondre », donc le
        # regime 2 ci-dessus -- aucune invite, la correction est appliquee.
        if apply_correction and demander_l_application_de_la_correction is not None:
            apply_correction = bool(demander_l_application_de_la_correction())
            if not apply_correction:
                # **La demande de l'operateur redescend DANS l'objet de correction**, et
                # ce n'est pas une precaution: `calibration_page_result` lit
                # `correction_requested` sur lui pour ecrire le motif `--cc off` a
                # l'entree de la page de calibration (`EPIC5-ARB-78`, deuxieme passe de
                # revue: « deux emplacements pour le meme fait, ce sont deux verites »).
                # Sans cette ligne, un refus a l'invite laissait les frames non corrigees
                # -- ce qui est correct -- mais laissait le document dire qu'une
                # correction avait ete demandee, donc perdait le seul motif lisible.
                #
                # La correction elle-meme a deja ete ajustee, et elle le reste: c'est ce
                # qui permet au manifest de dire qu'il y en avait une.
                lot_correction = dataclasses.replace(
                    lot_correction, correction_requested=False)
        logger.info(
            "Correction du lot: %s %s (forme %s, %d pastille(s) lue(s), "
            "%d retenue(s)).",
            # **« designe » et non « de chaine reutilise »** (story 5.23, AC 12): rien
            # n'est reutilise par appariement, l'operateur a nomme ce profil. La
            # distinction n'est pas de style -- « reutilise » decrit un enchainement
            # automatique, et c'est celui que `EPIC5-ARB-83` supprime.
            "profil designe, ajuste sur" if chain_profile_used
            else "ajustee sur la page de calibration",
            lot_correction.source_page_id,
            lot_correction.correction_form_id,
            lot_correction.read_patch_count,
            lot_correction.retained_patch_count,
        )
        if not apply_correction:
            # Le message nomme le drapeau et **dit que la correction existait**: sans
            # cela, l'operateur qui relit son journal deux jours plus tard ne distingue
            # pas ce refus volontaire d'un lot ou la page de calibration a manque.
            logger.warning(
                "Correction disponible mais NON appliquee sur demande (%s %s): les "
                "frames sont ecrites telles quelles et le manifest declare le motif "
                "'%s'. Relancez sans ce drapeau pour appliquer la correction.",
                CC_FLAG, CC_OFF, color_calibration.NOT_APPLIED_OPERATOR_OPT_OUT,
            )
    else:
        # AC 9: une page de calibration **illisible** n'est pas une page **deviante**.
        # Le motif et le message sont ceux de la page de calibration, et ils ne parlent
        # pas de divergence: le geste a faire n'est pas le meme.
        logger.warning(
            "Page de calibration inexploitable (%s): %s",
            lot_correction.failure_reason,
            lot_correction.failure_message,
        )
    # Le recadrage n'ecrit rien: il rend des tableaux en memoire. C'est donc ici
    # -- une fois su quelles pages ont echoue a la geometrie, et **avant** le
    # premier appel d'ecriture -- que le refus prealable d'EPIC5-ARB-34 se
    # place. Un refus qui arrive apres une destruction n'est pas un refus,
    # c'est un constat de deces.
    pages, page_calibrations = _scanned_pages_for_output(
        project_dir, detection, dpi_geometrie,
        lot_correction=lot_correction,
        divergence_bypass=divergence_bypass,
        apply_correction=apply_correction,
        # La provenance descend **avec** la correction, jamais deduite plus bas: seul cet
        # etage sait si le profil vient du fichier de chaine ou d'une page du scan.
        chain_id=chain_id,
    )
    # Les profils **retenus**, page par page: `PageCalibration.profile` ne vaut autre
    # chose que `None` que lorsque la page est `applied`, donc une planche refusee --
    # divergente, mesures implausibles, metrique au-dela du plafond -- ecrit ses frames
    # **non corrigees** et le declare. « Ce qui n'a pas ete corrige est declare non
    # corrige. »
    page_profiles = tuple(
        (page_index, result.profile)
        for page_index, result in page_calibrations
        if result.profile is not None
    )
    # Le nom que l'operateur lit pour designer **une** feuille, par index de page. Il est
    # derive du payload par la meme fonction que partout ailleurs (`_page_identifier`) et
    # jamais recompose ici: l'avertissement de degradation de l'AC 7 nomme une feuille, et
    # deux facons de la nommer feraient chercher la mauvaise dans le manifest.
    page_ids = {
        payload["page_index"]: _page_identifier(payload) for payload in payloads}
    for page_index, result in page_calibrations:
        # **Le prefixe se decide sur `failure_reason`, jamais sur `failure_message`**
        # (revue 5.22, mesure du 2026-08-17 sur `projects/chendj-mat`, scan `scan-WIN`).
        #
        # Le tri precedent portait sur la seule presence d'un message, et depuis que la
        # divergence est passee du refus dur a l'avertissement chiffre
        # (`EPIC5-ARB-80` decision 5) une planche **livree** en porte un: le journal
        # ecrivait donc « Page 1 refusee: [...] et les frames de celle-ci sont ecrites
        # telles quelles ». Le prefixe contredisait la phrase qu'il introduisait, et
        # c'est le prefixe que l'operateur lit en premier -- il repartait rescanner une
        # feuille qui etait sur le disque, c'est-a-dire exactement la panne que la story
        # existe pour supprimer. Le mot que la story interdit dans le message etait
        # reintroduit par son enrobage.
        #
        # `failure_reason` est le champ qui distingue **structurellement** les deux
        # regimes (`_failed` contre `_not_applied_page`), et c'est le meme predicat que
        # celui sur lequel le manifest se lit: un echec porte le champ, une decision en
        # attente ne le porte pas.
        if result.failure_reason is not None:
            # Un vrai echec: rien n'a pu etre mesure ou ajuste sur cette feuille, et le
            # geste attendu **est** de la rescanner. « Refusee » est vrai ici, et le
            # motif du vocabulaire ferme accompagne desormais le message -- c'est lui
            # que le manifest porte, donc c'est par lui que le journal se recoupe.
            logger.warning(
                "Page %d refusee (%s): %s", page_index, result.failure_reason,
                result.failure_message or "aucun detail supplementaire.",
            )
        elif result.status != color_pipeline.APPLIED_STATUS:
            # **Livree, non corrigee.** Le motif vient de `not_applied_reason` et non de
            # `failure_reason`, qui vaut `None` ici par construction: l'ancienne
            # redaction l'affichait tel quel et ecrivait litteralement « (None) ».
            logger.warning(
                "Page %d livree non corrigee (%s): ses frames sont ecrites telles "
                "quelles et le manifest le declare.%s",
                page_index, result.not_applied_reason,
                f" {result.failure_message}" if result.failure_message else "",
            )
        # **Les deux avertissements de la story 5.23, et ils n'empechent rien** (AC 4 et
        # AC 7). Ils sont poses **apres** le tri echec / livree-non-corrigee ci-dessus et
        # non dedans, parce qu'ils ne portent pas sur le meme fait: ceux du dessus disent
        # pourquoi une page n'a pas de correction, ceux-ci disent ce qu'il faut savoir
        # d'une page qui **en a recu une**. Les mettre dans une branche `elif` les
        # rendrait muets exactement dans le regime nominal, qui est le seul ou ils ont
        # un sens.
        _avertir_sur_une_page(logger, page_index, result,
                              page_id=page_ids.get(page_index, ""))
    # La page de calibration declare **son** resultat, et il n'est ni celui du lot ni
    # celui d'une planche: sans lui, son entree de manifest reprenait le statut du lot,
    # donc elle se disait `applied` alors qu'aucun de ses pixels n'avait ete corrige --
    # ou `failed` parce qu'une **autre** feuille divergeait. Les deux envoient
    # l'operateur rescanner la mauvaise feuille (AC 9).
    #
    # Les deux suites restent separees, et c'est ce qui garde les cardinaux justes: le
    # statut du lot compte les **planches d'images** corrigeables, et la page de
    # calibration n'en est pas une -- elle ne porte aucune frame.
    #
    # Le balayage porte sur les pages **declarees** et non sur les seules redressables
    # (`EPIC5-ARB-70`): une page de calibration dont la geometrie est perdue est celle dont
    # le document doit nommer l'echec, sinon il ne reste dans tout l'artefact aucune trace
    # de la raison pour laquelle ce lot n'a pas de couleur -- le motif ne vivrait que dans
    # `logs/scan.log`. C'est aussi ce qui empeche `EPIC5-ARB-69` de faire disparaitre
    # l'information: les planches intactes restent `not_applied`, et la coupable se nomme.
    declared_calibrations = tuple(page_calibrations)
    for detected in _declared_calibration_pages(detection):
        # L'appariement se fait par **identifiant de page**, jamais par appartenance a la
        # liste: un lot ou une page de calibration est lisible et une autre perdue rendrait
        # sinon le resultat de la premiere sur l'entree de la seconde -- une provenance qui
        # designe une feuille n'ayant rien produit, c'est-a-dire la classe de defaut que
        # cette passe de correction ferme partout ailleurs.
        if lot_correction is None or (
                lot_correction.source_page_id != _page_identifier(detected.payload)):
            continue
        declared_calibrations += ((
            detected.payload["page_index"],
            color_calibration.calibration_page_result(
                lot_correction,
                patch_preset_id=detected.payload["patch_preset_id"],
                # `--cc off` se lit desormais sur `lot_correction.correction_requested`
                # (deuxieme passe de revue, `EPIC5-ARB-78`, 2026-08-14): un second
                # parametre ici aurait pu diverger du choix reellement transmis a
                # `_fit_lot_correction` plus haut -- deux emplacements pour le meme
                # fait, ce sont deux verites.
            ),
        ),)
    try:
        scan_manifest.check_scan_conflicts(
            project_dir,
            payloads,
            failed_page_indexes=tuple(
                page.payload["page_index"]
                for page in pages
                if page.payload is not None and page.failure is not None
            ),
            overwrite=overwrite,
            # `EPIC11-ARB-105` : une nouvelle version ecrit dans un dossier
            # neuf, donc la clause de degradation n'a rien a proteger.
            cible_neuve=bool(nouvelle_version),
        )
    except (ExtractionPersistenceError, ReconstructionError, ValidationError) as exc:
        logger.error("Refus avant ecriture: %s", exc)
        raise

    # **Le conflit de contenu de l'AC 10** (story 11.4c, lot V2), pose ici et
    # pas ailleurs: apres `check_scan_conflicts`, donc sur une pile dont
    # l'identite de lot est deja validee -- ce qui est ce qui rend
    # `payloads[0]["lot_id"]` lisible sans garde -- et avant
    # `write_lot_output_frames`, donc avant le premier octet ecrit. L'ordre
    # d'`EPIC5-ARB-34` vaut ici comme partout: un refus qui arrive apres une
    # destruction n'est pas un refus.
    refuser_le_conflit_de_contenu(
        project_dir, payloads, overwrite=overwrite, logger=logger)

    # Le statut de lot se **derive** de ce qui a reellement ete corrige, il n'est jamais
    # pose en litteral ici (AC 4): les quatre cas et leur motif vivent dans
    # `color_pipeline.derive_lot_calibration_status`.
    color_calibration_status = color_pipeline.derive_lot_calibration_status(
        # **Le nom du parametre est reste celui de 5.19, sa valeur est la meme, et ce
        # qu'il signifie s'est elargi** (story 5.22): il repond a « une source de
        # correction de niveau lot existe-t-elle ? », ce qui couvre desormais le profil
        # de chaine autant que la page de calibration presente dans le scan. Le
        # renommer traverserait `color_pipeline` et toute sa suite pour un fait que ce
        # commentaire suffit a porter -- et elargirait le perimetre de la story, ce que
        # `CLAUDE.md` interdit. La valeur transmise est inchangee dans les deux regimes.
        calibration_page_present=lot_correction is not None,
        lot_correction_available=lot_correction is not None and lot_correction.available,
        correctable_page_count=len(page_calibrations),
        corrected_page_count=len(page_profiles),
        # **Le cardinal des planches refusees a ete retire ici** (story 5.23, AC 13,
        # `EPIC5-ARB-88`). Il comptait les planches non corrigees sans qu'un echec ait eu
        # lieu, c'est-a-dire le regime de refus pour divergence de 5.22 -- et ce regime
        # n'existe plus depuis l'AC 3 de cette meme story. Le cardinal valait donc
        # structurellement zero: `page_calibrations` ne porte que des sorties de
        # `calibrate_page`, dont le seul retour sans `failure_reason` est celui ou
        # `acceptance.status` vaut `"applied"` -- litteral, depuis `EPIC5-ARB-78` -- donc
        # avec un `profile`. Un cardinal toujours nul presente comme un compte est l'un
        # des quatre pieges nommes du 2026-08-12.
        # Le choix de l'operateur descend jusqu'a la fonction qui **decide** le statut,
        # plutot que d'y arriver deguise en « aucune planche corrigeable »: les deux
        # rendent `not_applied`, et un seul des deux est vrai (`EPIC5-ARB-78`).
        correction_requested=apply_correction,
    )
    try:
        output = scan_output_frames.write_lot_output_frames(
            project_dir,
            pages,
            overwrite=overwrite,
            color_calibration_status=color_calibration_status,
            page_profiles=page_profiles,
            # Le canal descend **tel quel**, jamais enveloppe ni re-emis ici
            # (AC 9.1, AC 9.2 : « aucun second mecanisme »). C'est
            # `write_lot_output_frames` qui construit l'emetteur, et il ne
            # l'ouvre qu'une fois tous ses refus durs passes -- donc aucun
            # jalon avant la premiere ecriture. Le passer par un lambda ou par
            # un objet-facade serait la porte du defaut mesure le 2026-08-30 :
            # un rappel non appelable eteint le canal **en silence**.
            rappel_progression=rappel_progression,
            # `--nouvelle-version` versionne les DEUX objets que cette commande
            # produit (`EPIC11-ARB-104`/`-94`): le dossier de scan a
            # l'ingestion, et les frames rescannees ici. Un seul drapeau, parce
            # que l'intention de l'operateur est une seule -- « ne detruis pas
            # ce qui est la » -- et que la lui faire exprimer deux fois serait
            # une occasion de n'en protéger qu'une moitie.
            nouvelle_version=nouvelle_version,
            manifest=manifest_du_projet,
        )
    except scan_output_frames.ScanOutputError as exc:
        logger.error("Echec de l'ecriture des frames: %s", exc)
        raise

    logger.info(
        "Passe de sortie: %d frame(s) ecrite(s) dans %s, dont %d de remplacement",
        output.written_frame_count,
        output.output_dir,
        output.synthetic_frame_count,
    )
    for code in output.warnings:
        logger.warning("Avertissement d'ecriture: %s", code)

    try:
        persisted = scan_manifest.persist_scan(
            project_dir,
            scan_manifest.ScanRecord(
                page_payloads=payloads,
                output_report=output,
                scan_dpi=dpi_manifest,
                ingest_slug=report.ingest_slug,
                pages=_scan_provenance(detection),
                # Le fil de l'AC 10 de 5.16, enfin alimente: il attendait un appelant
                # depuis cette story-la. Chaque couple porte son `page_index` **a cote**
                # du resultat plutot que de le deviner par le rang de la sequence.
                page_calibrations=declared_calibrations,
                # La **demande** de l'operateur, portee jusqu'a la couche qui ecrit.
                # Elle ne s'inscrit pas au document -- le manifest decrit ce qui s'est
                # passe, pas ce qui a ete demande -- mais elle y est confrontee: un
                # contournement **constate** sans demande explicite est refuse, et c'est
                # ce qui rend l'AC 15 verifiable au lieu d'etre declarative.
                divergence_bypass_requested=bool(divergence_bypass),
            ),
        )
    except (ExtractionPersistenceError, ReconstructionError, ValidationError) as exc:
        # Le manifest precedent est strictement intact: l'ecriture atomique
        # valide son temporaire **avant** la bascule. Les frames, elles, sont
        # sur le disque -- c'est voulu, rien n'atteint le manifest tant que les
        # fichiers n'existent pas, et une relance les retrouve.
        logger.error("Echec de l'ecriture du manifest: %s", exc)
        raise

    # **L'entree autoportante du profil, reposee une fois le manifest ecrit** (AC 12,
    # `EPIC5-ARB-83` decision 4: « un profil = un fichier autoportant + une entree
    # autoportante au manifest »). Elle est ecrite **ici** et pas au moment de l'import
    # parce qu'un projet neuf n'a pas encore de `project.json` a cet instant-la: le
    # fichier de profil, lui, doit exister avant que la correction ne soit calculee.
    # L'ecriture est idempotente (remplacement par `chain_id`), donc la reposer sur un
    # projet qui avait deja son manifest ne cree pas de doublon.
    #
    # Elle est deliberement redondante avec le fichier: le manifest dit ce que le projet
    # a **reellement utilise** sans avoir a ouvrir le profil -- donc sans avoir a
    # l'avoir encore.
    if chain_profile_used and profil_designe is not None:
        try:
            # **Le chemin est celui que le document occupe reellement**, etiquette
            # comprise (AC 8quater). Le recomposer depuis le `chain_id` etait exact
            # tant que les deux coincidaient; depuis qu'un profil peut porter le nom
            # que son operateur lui a donne, l'entree de manifest pointerait sur un
            # fichier inexistant -- et le defaut du projet, qui se resout **par ce
            # chemin ecrit**, cesserait de se resoudre.
            document_designe = profile_designation.read_designated_document(
                profil_designe)
            profile_designation.record_designated_profile(
                project_dir,
                document_designe,
                project_path=calibration_profile.profile_path_for_document(
                    project_dir, document_designe),
                source=profil_designe)
        except (profile_designation.ProfileDesignationError,
                ExtractionPersistenceError, ValidationError, OSError) as exc:
            # Le lot est ecrit, le manifest est ecrit, les frames sont corrigees: perdre
            # tout cela parce que la **trace** du profil n'a pas pu s'ecrire serait
            # disproportionne. L'avertissement dit ce qui manque et comment le reposer.
            logger.warning(
                "Frames et manifest ecrits, mais la trace du profil designe n'a pas pu "
                "etre inscrite au manifest (%s). Reposez-la avec `%s --project %s %s "
                "%s`.", exc, SET_DEFAULT_PROFILE_COMMAND, project_dir, PROFILE_FLAG,
                profil_designe)
    # Le compte rendu imprime et le journal de persistance sont restes chez
    # l'enveloppeur: une phrase de terminal n'est pas un fait, et ce module ne
    # rend que des faits (meme partage que `ScanDetectOutcome`).
    return EcritureDuLot(
        persisted=persisted,
        output=output,
        lot_correction=lot_correction,
        # La decision TRANCHEE, invite comprise -- jamais celle qui est entree.
        correction_appliquee=apply_correction,
        profil_de_chaine_utilise=chain_profile_used,
        rapport=report,
    )


# ---------------------------------------------------------------------------
# La moitie HAUTE du temps 2 : d'un document de detection persiste aux objets
# que la moitie aval consomme (story 11.6, lot B, `EPIC11-ARB-129`).
#
# **Corps deplace de `cli.scan_write_command`, jamais reecrit** -- troisieme
# fois que ce geste est fait sur cette meme chaine : la story 5.26 l'a fait de
# `scan_command` vers `scan_write_command`, la 11.4b de `cli` vers ce module
# pour la moitie aval, celle-ci pour la moitie haute. Une seconde redaction
# divergerait, et l'ecart ne se verrait que sur les TIFF produits.
#
# Ce qui a change, et rien d'autre : l'objet `args` argparse est devenu des
# parametres nommes, les six `print(..., file=sys.stderr)` de
# `_refus_de_scan_write` sont devenus un `raise RefusDuDocumentDeDetection`
# **portant le meme message mot pour mot**, le `print(annonce)` de completude
# est devenu un rappel optionnel, et le code de sortie est devenu un
# `EcritureDuLot`.
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class PageDetecteeDuDocument:
    """Page detectee-like reconstruite depuis un document de detection (5.26).

    Adaptateur **structurel**: exactement les champs que la moitie aval
    consomme (`_scanned_pages_for_output`, `_rectified_page`,
    `_scan_provenance`, `_declared_calibration_pages`), remplis depuis le
    document seul -- acces direct aux champs du document, jamais un repli: un
    champ absent est tombe en refus nomme AVANT la construction de cet objet
    (lecteur de `scan_previz` + gardes de :func:`lire_le_document_de_detection`).
    Le `payload` est le verbatim du document (H4: jamais re-decode),
    l'appariement `read_rank`/`page_index` est transporte tel quel, jamais
    reconstruit par position.
    """

    read_rank: int
    status: str
    qr_status: str
    page_index: int | None
    payload: dict | None
    homography: tuple | None
    page_size_px: tuple | None
    locator_source: str
    locator_page_index: int | None


@dataclasses.dataclass(frozen=True)
class DetectionDuDocument:
    """Rapport de detection-like: ce que la moitie aval lit d'un rapport."""

    scan_dpi: int
    pages: tuple


@dataclasses.dataclass(frozen=True)
class IngestionDuDocument:
    """Rapport d'ingestion-like: les trois champs que la moitie aval lit
    (`ingest_slug` pour le manifest, `scans_dir` et `len(pages)` pour le
    compte rendu final)."""

    ingest_slug: str
    scans_dir: str
    pages: tuple


@dataclass(frozen=True)
class DocumentDeDetectionLu:
    """Ce qu'une lecture de document a produit -- des faits, jamais des phrases.

    Le **JSON brut est garde a cote de l'objet relu**, et ce n'est pas une
    redondance : la couche `manual_corrections` est ADDITIVE
    (`EPIC7-ARB-95`), donc invisible pour le lecteur de previz -- c'est meme
    la propriete qui la rend compatible avec lui. Elle se lit sur le JSON tel
    quel, par `scan_corrections`, qui possede seul ses refus. Reserialiser
    l'objet ferait passer le document par un aller-retour que personne n'a
    demande.
    """

    #: Le chemin d'ou le document a ete lu, verbatim.
    chemin: Path
    #: Le dictionnaire JSON tel quel, couche `manual_corrections` comprise.
    brut: dict
    #: L'objet relu par `scan_previz.scan_previz_from_json_dict`.
    document: object


def _refuser_le_document(logger, motif: str, message: str):
    """Lever un refus nomme de la moitie haute: journal, motif, zero ecriture.

    Meme forme que :func:`refuser_le_conflit_de_contenu` -- « Refus avant
    ecriture: » au journal puis un `raise` -- parce que c'est la meme
    promesse : ce refus tombe **avant** qu'une frame n'existe.
    """
    logger.error("Refus avant ecriture: %s", message)
    raise RefusDuDocumentDeDetection(message, motif=motif)


def lire_le_document_de_detection(document_path, *, logger=None):
    """Relire un document de detection persiste, ou **refuser nommement**.

    Les **cinq** refus de la lecture, dans l'ordre des gardes -- introuvable,
    JSON invalide, pas une previz de scan, etat autre que `detected`, document
    anterieur a la story 5.26. Chacun porte son motif
    (:data:`MOTIFS_DE_REFUS_A_LA_LECTURE`) et le message que la CLI imprimait
    deja mot pour mot.

    **Pourquoi cette fonction est publique et separee de l'ecriture.** Une
    interface a besoin de la lecture **sans** l'ecriture : montrer ce qu'un
    document dit est le temps 1, l'ecrire est le temps 2. `gui/` en porte deja
    deux redactions (`chargeur_detections.py`, `lecture_detection.py`) ; une
    troisieme dans `tui/` serait la faute que `EPIC11-ARB-108` nomme -- « un
    mecanisme, un lieu ».

    :param document_path: le chemin du document de detection.
    :param logger: journal de la passe. Optionnel : un journal muet est pose
        quand l'appelant n'en fournit pas, exactement comme
        :func:`ecrire_le_lot_detecte`.
    :returns: un :class:`DocumentDeDetectionLu`.
    :raises RefusDuDocumentDeDetection: l'un des cinq refus de la lecture.
    """
    logger = logger or logging.getLogger(__name__)
    document_path = Path(document_path)
    if not document_path.is_file():
        _refuser_le_document(logger, REFUS_DOCUMENT_INTROUVABLE, (
            f"Document de detection introuvable: {document_path}. "
            "Verifiez le chemin, ou produisez-en un avec "
            "`scan --project <projet> --scan <source> --dpi <dpi> "
            f"{scan_detect.SCAN_DETECT_SUBCOMMAND}`. Aucune frame n'a ete "
            "ecrite."))
    try:
        brut = json.loads(document_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        _refuser_le_document(logger, REFUS_DOCUMENT_JSON_INVALIDE, (
            f"Document de detection illisible (JSON invalide): "
            f"{document_path} ({exc}). Relancez `scan ... "
            f"{scan_detect.SCAN_DETECT_SUBCOMMAND}` pour en produire un neuf. "
            "Aucune frame n'a ete ecrite."))
    try:
        document = scan_previz.scan_previz_from_json_dict(brut)
    except scan_previz.ScanPrevizError as exc:
        _refuser_le_document(logger, REFUS_DOCUMENT_PAS_UNE_PREVIZ_DE_SCAN, (
            f"{document_path} n'est pas un document de detection "
            f"exploitable: {exc}. Relancez `scan ... "
            f"{scan_detect.SCAN_DETECT_SUBCOMMAND}` pour en produire un neuf. "
            "Aucune frame n'a ete ecrite."))
    if document.state != scan_previz.SCAN_PREVIZ_STATE_DETECTED:
        _refuser_le_document(logger, REFUS_DOCUMENT_ETAT_INATTENDU, (
            f"{document_path} porte l'etat '{document.state}': l'ecriture "
            f"ne consomme que l'etat "
            f"'{scan_previz.SCAN_PREVIZ_STATE_DETECTED}' (detection "
            "faite, aucune frame ecrite). Aucune frame n'a ete ecrite."))

    # Document anterieur a 5.26: sans payload verbatim ni condensat des
    # octets, l'ecriture ne peut ni retrouver les timecodes (le payload
    # n'est pas reconstituable: `timecode_base_fps` ne vit nulle part
    # ailleurs) ni verifier que les fichiers sources n'ont pas change.
    # Refus nomme, jamais une reconstitution devinee (NFR6: les formats
    # internes sont libres, la retrocompatibilite n'est pas due -- le
    # refus nomme, si).
    for page in document.pages:
        if page.source_digest is None or (
                page.page_index is not None and page.payload is None):
            _refuser_le_document(logger, REFUS_DOCUMENT_ANTERIEUR, (
                f"{document_path} est un document de detection anterieur "
                "a cette version (page de rang de lecture "
                f"{page.read_rank} sans payload verbatim ou sans "
                "condensat de fichier source): il ne porte pas de quoi "
                "ecrire sans re-detecter. Relancez `scan ... "
                f"{scan_detect.SCAN_DETECT_SUBCOMMAND}` pour produire un "
                "document complet. Aucune frame n'a ete ecrite."))
    return DocumentDeDetectionLu(
        chemin=document_path, brut=brut, document=document)


def verifier_les_condensats_des_sources(project_dir, document, *, logger=None):
    """Refuser si un fichier source a change depuis la detection (AC 3 de l'epic).

    Verification du condensat de CHAQUE source **avant toute ecriture** : un
    fichier remplace a dimensions egales depuis la detection est refuse
    nommement, page et fichier cites, avant qu'une seule frame n'existe. Un
    condensat par chemin: deux pages du meme PDF partagent le meme fichier.

    :raises RefusDuDocumentDeDetection: :data:`REFUS_SOURCE_MANQUANTE` ou
        :data:`REFUS_SOURCE_CONDENSAT_DIVERGENT`.
    """
    logger = logger or logging.getLogger(__name__)
    project_dir = Path(project_dir)
    condensats: dict[str, str] = {}
    for page in document.pages:
        source = project_dir / page.source_path_relative
        nom_de_page = (
            f"page de rang de lecture {page.read_rank}"
            + ("" if page.page_index is None
               else f" (page_index {page.page_index})"))
        if not source.is_file():
            _refuser_le_document(logger, REFUS_SOURCE_MANQUANTE, (
                f"Fichier source manquant pour la {nom_de_page}: "
                f"{page.source_path_relative} (attendu sous "
                f"{project_dir}). La copie ingeree a ete supprimee ou "
                "deplacee depuis la detection; relancez `scan ... "
                f"{scan_detect.SCAN_DETECT_SUBCOMMAND}` sur la source. "
                "Aucune frame n'a ete ecrite."))
        if page.source_path_relative not in condensats:
            condensats[page.source_path_relative] = (
                scan_detect.condensat_du_fichier_source(source))
        if condensats[page.source_path_relative] != page.source_digest:
            _refuser_le_document(logger, REFUS_SOURCE_CONDENSAT_DIVERGENT, (
                f"Document de detection perime: le fichier source de la "
                f"{nom_de_page} a change depuis la detection "
                f"({page.source_path_relative}: condensat "
                f"{condensats[page.source_path_relative]} contre "
                f"{page.source_digest} au document). Rien n'est applique "
                "en silence: relancez `scan ... "
                f"{scan_detect.SCAN_DETECT_SUBCOMMAND}` pour re-detecter "
                "l'etat actuel du scan. Aucune frame n'a ete ecrite."))


def annonce_de_completude(document) -> str:
    """La phrase de completude du lot, derivee du **document seul** (FR7, AC 4).

    Cardinal attendu des compteurs, index presents des pages. C'est une
    **annonce, jamais un refus**: un lot troue ecrit ses frames (et ses mires)
    comme la voie historique. Elle est rendue plutot qu'imprimee -- ce module
    ne met en forme aucun message de terminal, il rend le fait, et chaque
    appelant choisit ou il l'affiche.
    """
    presentes = sorted({
        page.page_index for page in document.pages
        if page.page_index is not None})
    attendu = document.counters.pages_expected
    if attendu is None:
        return (
            f"Completude du lot {document.subject.lot_id} avant "
            f"ecriture: {len(presentes)} page(s) identifiee(s), cardinal "
            "attendu indeterminable depuis le document.")
    manquantes = sorted(set(range(attendu)) - set(presentes))
    return (
        f"Completude du lot {document.subject.lot_id} avant "
        f"ecriture: {len(presentes)} page(s) identifiee(s) sur "
        f"{attendu} attendue(s)"
        + (", aucune manquante" if not manquantes else
           ", manquante(s) (page_index): "
           + ", ".join(str(index) for index in manquantes))
        + ".")


def objets_consommables_du_document(document) -> tuple:
    """Adapter un document relu en (rapport, detection, payloads).

    Appariement transporte **champ par champ** (`read_rank` ET `page_index`,
    jamais deduits l'un de l'autre), puis la MEME moitie aval que `scan` --
    une seule redaction (AC 2 de 5.26).
    """
    pages_detectees = tuple(
        PageDetecteeDuDocument(
            read_rank=page.read_rank,
            status=page.status,
            qr_status=page.qr_status,
            page_index=page.page_index,
            payload=None if page.payload is None else dict(page.payload),
            homography=page.homography,
            page_size_px=page.page_size_px,
            locator_source=page.source_path_relative,
            locator_page_index=page.source_page_index,
        )
        for page in document.pages
    )
    detection = DetectionDuDocument(
        scan_dpi=document.subject.scan_dpi_detection,
        pages=pages_detectees,
    )
    rapport = IngestionDuDocument(
        ingest_slug=document.subject.ingest_slug,
        scans_dir=document.subject.scans_dir_relative,
        pages=pages_detectees,
    )
    payloads = tuple(
        page.payload for page in pages_detectees if page.payload is not None)
    return rapport, detection, payloads


def ecrire_depuis_le_document(project_dir, document_path, *,
                              overwrite=False,
                              logger=None,
                              appliquer_la_correction=True,
                              livrer_brut=False,
                              divergence_bypass=False,
                              profil_designe=None,
                              origine_du_profil=None,
                              nouvelle_version=False,
                              manifest_du_projet=None,
                              rappel_progression=None,
                              annoncer_la_completude=None,
                              demander_l_application_de_la_correction=None,
                              confirmer_l_ecrasement=None) -> EcritureDuLot:
    """Le temps 2 du scan, d'un bout a l'autre: du document persiste aux frames.

    Story 11.6, lot B (`EPIC11-ARB-129`). C'est le **point d'entree de coeur du
    temps 2**, celui qui manquait : jusqu'ici la moitie haute vivait dans
    `cli.scan_write_command`, que la TUI a interdiction d'importer
    (`EPIC11-ARB-67`). `scan_write_command` en devient un **enveloppeur** :
    memes messages, memes codes de sortie, memes artefacts.

    **L'ordre des gardes est l'AC** (`EPIC5-ARB-34`, FR7) -- « un refus qui
    arrive apres une destruction n'est pas un refus » :

    1. lecture et refus du document -- introuvable, corrompu, pas une previz de
       scan, etat autre que `detected`, document anterieur a 5.26
       (:func:`lire_le_document_de_detection`);
    2. verification du **condensat des octets** de chaque fichier source
       (:func:`verifier_les_condensats_des_sources`);
    3. annonce de **completude** derivee du document seul
       (:func:`annonce_de_completude`) -- une annonce, jamais un refus;
    4. refus nomme si le document ne porte **aucune page identifiee**;
    5. la moitie aval (:func:`ecrire_le_lot_detecte`), qui reexecute
       `check_scan_conflicts` contre le manifest du moment de l'ecriture: la
       garantie que detect a donnee hier ne dit rien du manifest d'aujourd'hui.

    Les deux dpi sont lus **DANS le document** (AC 1), jamais d'une option qui
    pourrait diverger: la geometrie se rejoue au dpi qui a decide l'homographie
    et les zones (`scan_dpi_detection`), le manifest recoit le dpi declare a
    l'ingestion (`scan_dpi_declared`).

    Le document reste **intact** apres ecriture: ni modifie, ni supprime, ni
    double d'un document `reconstructed` -- l'etat du lot est porte par le
    manifest (`EPIC5-ARB-32`).

    :param annoncer_la_completude: rappel **optionnel** appele avec la phrase
        de completude, avant la moitie aval. Il vaut `None` par defaut et son
        absence ne change **rien** a l'observable (`AR3`, story 5.28): la
        phrase part au journal dans les deux cas. La CLI y passe `print`, une
        interface y passe sa ligne d'etat. Comme les deux autres rappels de ce
        module, il existe parce que **ce module ne lit ni n'ecrit jamais le
        terminal** -- sous une boucle d'evenements, une ligne imprimee tombe
        sous l'ecran dessine (`EPIC7-ARB-106`).
    :param overwrite: transmis **verbatim** a :func:`ecrire_le_lot_detecte`.
        La seconde issue d'`EPIC11-ARB-89` -- ecrire une nouvelle version
        plutot qu'ecraser -- est arrivee **a la liaison du 2026-09-01**, et
        elle est entree exactement comme cette page l'annoncait : deux
        parametres nommes de plus (`nouvelle_version`, `manifest_du_projet`)
        et deux lignes de plus dans la delegation ci-dessous, sans rien
        restructurer. C'est la seule raison pour laquelle cette fonction
        relaie les options une a une au lieu de les regrouper.
    :param nouvelle_version: transmis **verbatim** a
        :func:`ecrire_le_lot_detecte` (`EPIC11-ARB-104`). Le temps 2 protege
        donc les memes deux sorties que la voie `scan` : le dossier de scan
        et les frames rescannees.
    :param manifest_du_projet: le `project.json` deja lu, ou `None` -- la
        ligne d'eau des rangs de version. Relaye tel quel ; son absence
        signifie « aucune version employee », jamais « projet invalide ».

    Les autres parametres sont ceux de :func:`ecrire_le_lot_detecte` et lui
    sont relayes tels quels.

    :raises RefusDuDocumentDeDetection: l'un des huit refus nommes de la
        moitie haute.
    :returns: le :class:`EcritureDuLot` de la moitie aval.
    """
    logger = logger or logging.getLogger(__name__)
    project_dir = Path(project_dir)
    lu = lire_le_document_de_detection(document_path, logger=logger)
    document = lu.document
    verifier_les_condensats_des_sources(project_dir, document, logger=logger)

    annonce = annonce_de_completude(document)
    logger.info("%s", annonce)
    if annoncer_la_completude is not None:
        annoncer_la_completude(annonce)

    rapport, detection, payloads = objets_consommables_du_document(document)
    # Refus nomme pour un document a zero page identifiee (revue 5.26):
    # `scan_command` et `scan_detect_command` portent tous deux le
    # garde-fou « aucune planche n'a livre son QR », et cette commande ne
    # le refermait pas -- la boucle de refus des documents anterieurs a
    # 5.26, plus haut, laisse passer une page mutique (`page_index` et
    # `payload` tous deux `None`). Chemin mort aujourd'hui (`scan detect`
    # ne persiste jamais un tel document), mais un document edite a la
    # main ou produit par un futur appelant divergerait sinon en
    # silence: `ecrire_le_lot_detecte` recevrait des payloads vides.
    if not payloads:
        _refuser_le_document(
            logger, REFUS_DOCUMENT_SANS_PAGE_IDENTIFIEE, (
                f"{lu.chemin} ne porte aucune page identifiee (aucun "
                "payload): rien a ecrire depuis ce document. Relancez "
                f"`scan ... {scan_detect.SCAN_DETECT_SUBCOMMAND}` sur une "
                "pile dont au moins une planche a livre son QR. Aucune "
                "frame n'a ete ecrite."))
    return ecrire_le_lot_detecte(
        project_dir, rapport, detection, payloads,
        dpi_geometrie=document.subject.scan_dpi_detection,
        dpi_manifest=document.subject.scan_dpi_declared,
        overwrite=overwrite,
        logger=logger,
        appliquer_la_correction=appliquer_la_correction,
        livrer_brut=livrer_brut,
        divergence_bypass=divergence_bypass,
        profil_designe=profil_designe,
        origine_du_profil=origine_du_profil,
        nouvelle_version=nouvelle_version,
        manifest_du_projet=manifest_du_projet,
        # Le document **brut**, et non l'objet relu par `scan_previz`: la
        # couche `manual_corrections` est ADDITIVE (`EPIC7-ARB-95`), donc
        # invisible pour le lecteur de previz -- c'est meme la propriete qui
        # la rend compatible avec lui. Elle se lit sur le JSON tel quel, par
        # `scan_corrections`, qui possede seul ses refus.
        corrections_manuelles=lu.brut,
        rappel_progression=rappel_progression,
        demander_l_application_de_la_correction=(
            demander_l_application_de_la_correction),
        confirmer_l_ecrasement=confirmer_l_ecrasement,
    )
