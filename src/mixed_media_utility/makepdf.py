# -*- coding: utf-8 -*-
"""Le point d'entree de COEUR de `makepdf` -- les planches d'un lot, et la mire.

Story 11.7, lot B (taches B2, B3 et B5), AC 2.1 a 2.5. Ce module porte le corps
que `cli.makepdf_command` et `cli.makepdf_calibration_page_command`
orchestraient jusqu'ici : gardes de projet et de manifest, resolution du
`lot_id`, conformite du lot, resolution du rang de tirage, composition,
detection de conflit, journal de compression, rendu, declaration au manifest.

**Pourquoi il existe.** L'atelier Pdf de la TUI n'a, aujourd'hui, **rien a
appeler** : `makepdf_command` porte la sequence entiere dans son propre corps,
prend un objet `args` argparse, imprime sur `stderr` et rend un entier -- et la
TUI a **interdiction d'importer `cli`** (frontiere de la 11.4b, mesuree par
`tests/unit/tui/test_frontiere_cli.py`). C'est mot pour mot le motif
d'`EPIC11-ARB-129` pour le temps 2 du Scan, et le geste qui y repond a deja ete
fait deux fois sur cette chaine : `scan_detect.run_scan_detect` (5.26 / 7.3)
puis `scan_write.ecrire_le_lot_detecte` (11.4b, lot S1). Ce module est le
troisieme, et il suit le meme patron.

**Le contrat, en une phrase** : il ne met en forme aucun message pour un
terminal et ne rend aucun code de retour -- il **leve** les refus nommes
(:data:`REFUS_NOMMES`) et les exceptions du coeur **inchangees**, et rend un
:class:`PlanchesDuLot` ou une :class:`PageDeCalibration` sur le chemin qui
aboutit. `cli.makepdf_command` et `cli.makepdf_calibration_page_command` en
deviennent des **enveloppes** : memes codes de sortie (`0`, `1`, `130`), memes
messages imprimes, meme `logs/makepdf.log`, memes artefacts.

**Le corps a ete DEPLACE, jamais reecrit** (AC 2.2). C'est le geste que la 5.26
puis la 11.4b ont deja fait deux fois sur la chaine du Scan, et le motif est
mesurable : une seconde redaction divergerait, et l'ecart ne se verrait que sur
les PDF produits. La mesure du deplacement est le dossier d'identite de la
tache B1 (`tests/unit/test_makepdf_noyau.py`, references
`tests/fixtures/identite-makepdf-*.json`) : trente-sept invocations reelles de
`cli.main`, comparees ligne a ligne a un releve joue avant le deplacement, et
l'ensemble des scenarios qui divergent doit y etre **vide**.

**L'ordre des gardes a voyage avec le corps, et il est mesure** (AC 2.4) --
`ORDRE_DES_GARDES` le nomme, et le banc mesure les couples ou deux gardes
pourraient parler : « un refus qui arrive apres une destruction n'est pas un
refus ».

**Ce module ne lit JAMAIS `stdin`** et n'imprime jamais. Sous `textual`, `stdin`
appartient a la boucle d'evenements et un appel bloquant y gele l'interface
entiere (`EPIC7-ARB-106`) ; une ligne imprimee, elle, tombe **sous** l'ecran
dessine. Une frontiere AST mesure les deux interdits (AC 2.7).

**Il n'a pas de parametre `nouvelle_version`, et c'est un fait mesure plutot
qu'un oubli.** Depuis le lot B0 bis (`EPIC11-ARB-175`), le rang se resout
**inconditionnellement** et `--nouvelle-version` n'est plus qu'une reponse au
conflit residuel -- que le rang qui avance rend inatteignable. Le corps deplace
ici ne lit donc plus ce drapeau nulle part. Lui rendre un parametre serait une
surface morte : declaree, relayee, jamais lue -- exactement le defaut que la
revue du 2026-08-31 a trouve sur quatre des cinq champs de ligne d'eau du
depot.

Ce module est du **coeur** : il n'importe ni `cli`, ni `gui/`, ni `tui/`.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from jsonschema.exceptions import ValidationError

from . import page_templates, patch_presets, pdf_composition, pdf_render, qr_codes
from .io import (
    extraction_manifest,
    naming,
    pdf_manifest,
    project_layout,
    scan_manifest,
    version_ranks,
)
from .io.extraction_manifest import (
    ExtractionPersistenceError,
    _atomic_write,
    _load_existing_manifest,
)
from .io.manifest import validate_manifest
from .io.naming import NamingError
from .io.payload import PayloadBudgetExceeded, PayloadValidationError
from .page_payload import NonCanonicalIdentifierError

# 2026-08-13, demande directe d'Egan (deplace de `cli` avec le corps qui le
# lit) : `color.target_colorspace` est deja classe non-MVP au niveau produit, et
# son absence ne doit plus faire refuser `makepdf`. La valeur ecrite est celle
# que le depot emploie partout ailleurs ; elle n'est pas recopiee de `cli`, elle
# y a ete **retiree** au profit de celle-ci.
DEFAULT_TARGET_COLORSPACE = "bt709"


# ---------------------------------------------------------------------------
# Les refus NOMMES (AC 2.3) -- un motif par famille, jamais un bout de phrase
# ---------------------------------------------------------------------------

#: Motifs de refus. Ils vivent **a cote** du message et ne le remplacent pas :
#: le message est ce qu'un terminal imprime mot pour mot (`Erreur: <message>`),
#: le motif est ce qu'une interface teste sans lire de phrase. Nommer un refus
#: en cherchant un bout de phrase est exactement ce qui casse a la premiere
#: reformulation (motif de `scan_write.RefusDuDocumentDeDetection`).
MOTIF_PROJET_INEXISTANT = "PROJET_INEXISTANT"
MOTIF_MANIFEST_ABSENT = "MANIFEST_ABSENT"
MOTIF_DESIGNATION_DU_LOT = "DESIGNATION_DU_LOT"
MOTIF_LOT_NON_CONFORME = "LOT_NON_CONFORME"
MOTIF_CONFLIT_DE_SORTIE = "CONFLIT_DE_SORTIE"

#: L'ensemble **ferme** des motifs. Le banc mesure que l'ensemble atteignable
#: est exactement celui-ci -- pas une inclusion.
MOTIFS_DE_REFUS: tuple[str, ...] = (
    MOTIF_PROJET_INEXISTANT,
    MOTIF_MANIFEST_ABSENT,
    MOTIF_DESIGNATION_DU_LOT,
    MOTIF_LOT_NON_CONFORME,
    MOTIF_CONFLIT_DE_SORTIE,
)


class RefusDeMakepdf(ValueError):
    """Un refus **nomme** de `makepdf` : rien n'a ete ecrit.

    Elle derive de `ValueError` comme `ScanDetectError` et
    `RefusDuDocumentDeDetection`, et elle entre dans :data:`CODES_DE_SORTIE` au
    meme code `1` que les autres refus du coeur : l'enveloppeur de la CLI ne la
    traite pas a part.

    Le message est **positionnel**, le motif est **nomme et facultatif** : une
    exception de la table qui exigerait deux arguments sortirait du parcours que
    le dossier d'identite construit pour mesurer que le prefixe `Erreur: ` vaut
    pour **toutes** les familles, y compris celles qu'aucun refus reel
    n'atteint.
    """

    def __init__(self, message: str, *, motif: str | None = None):
        super().__init__(message)
        #: L'un de :data:`MOTIFS_DE_REFUS`, ou `None` pour une instance
        #: fabriquee hors de ce module.
        self.motif = motif


class LotNonConforme(RefusDeMakepdf):
    """Le lot sur disque ne correspond plus a ce que le manifest declare.

    Elle porte les **faits** que l'appelant met en forme -- les constats
    bloquants dans leur ordre, la liste des lots du manifest quand le lot vise
    en est absent --, jamais la phrase composee. Deux interfaces disent alors la
    meme chose sans qu'aucune ne recopie l'autre.
    """

    def __init__(self, message: str, *, lot_id: str, verification,
                 lots_disponibles: str, motif: str = MOTIF_LOT_NON_CONFORME):
        super().__init__(message, motif=motif)
        self.lot_id = lot_id
        #: Le resultat de `extraction_manifest.verify_extracted_lot`, verbatim.
        self.verification = verification
        #: Les lots du manifest, deja joints -- lu **une fois**, au moment ou le
        #: manifest est en main. Le recalculer dans l'enveloppe demanderait de
        #: lui repasser le manifest entier pour composer une phrase.
        self.lots_disponibles = lots_disponibles

    @property
    def lot_absent(self) -> bool:
        """Le lot est-il absent du manifest, plutot que non conforme ?

        Les deux refus ne proposent pas la meme reprise -- re-extraire ne sert a
        rien quand le lot n'est pas declare --, et la distinction se lit sur le
        **code** de verification, jamais sur un bout de message.
        """
        return (extraction_manifest.VERIFY_LOT_ABSENT
                in self.verification.findings)


class ConflitDeSortie(RefusDeMakepdf):
    """Le fichier vise existe deja et aucune issue n'a ete choisie.

    Elle porte le chemin **reellement vise**, celui qui vient d'etre compose --
    jamais recompose par l'appelant, qui n'aurait alors aucune garantie de viser
    le meme fichier.
    """

    def __init__(self, message: str, *, output_path: Path,
                 motif: str = MOTIF_CONFLIT_DE_SORTIE):
        super().__init__(message, motif=motif)
        self.output_path = output_path


#: L'ensemble **EXACT** des refus que les deux points d'entree peuvent lever
#: (AC 2.3), classes de ce module **et** classes du coeur qui traversent le
#: corps deplace. C'est un ensemble ferme, pas une inclusion : un `except` de
#: l'enveloppe qui ne figurerait pas ici serait un refus que la TUI ne saurait
#: pas nommer, et une entree d'ici qu'aucun `raise` n'atteint serait une
#: promesse vide.
#:
#: Les deux familles que le corps ne peut PAS lever bien qu'elles soient
#: nommees par l'AC 2.3, et le dire vaut mieux que le taire : les **rangs
#: epuises** (`VERSION_RANK_MAX`) sortent en `NamingError`, et l'**echec de
#: declaration au manifest** en `ExtractionPersistenceError` -- ses deux
#: sous-classes `PdfPersistenceError` et `PdfLotAbsentError` sont dans la table
#: par leur base, et l'enveloppe les distingue par `isinstance`.
REFUS_NOMMES: tuple[type[BaseException], ...] = (
    RefusDeMakepdf,
    pdf_composition.CompositionError,
    PayloadBudgetExceeded,
    PayloadValidationError,
    NonCanonicalIdentifierError,
    qr_codes.QRPayloadTooLarge,
    qr_codes.QRRenderError,
    pdf_render.PdfRenderError,
    ExtractionPersistenceError,
    NamingError,
    ValidationError,
    json.JSONDecodeError,
    page_templates.UnknownTemplateError,
    patch_presets.UnknownPatchPresetError,
    patch_presets.UndefinedPlacementError,
    OSError,
)

#: L'ordre des gardes, **declare** (AC 2.4). « Un refus qui arrive apres une
#: destruction n'est pas un refus » : c'est l'invariant d'`EPIC5-ARB-34`,
#: transpose de l'ecriture du scan a l'impression. La declaration ne mesure
#: rien a elle seule -- le banc mesure les couples ou deux gardes pourraient
#: parler, et verifie **laquelle** parle.
ORDRE_DES_GARDES: tuple[str, ...] = (
    "projet",
    "manifest",
    "designation_du_lot",
    "conformite_du_lot",
    "rang_de_version",
    "composition",
    "conflit_de_sortie",
    "rendu",
    "declaration_au_manifest",
)


# ---------------------------------------------------------------------------
# Ce que les deux points d'entree rendent -- des faits, jamais des phrases
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PlanchesDuLot:
    """Ce que la generation des planches d'un lot a produit.

    Aucun message compose n'y entre : l'enveloppeur de la CLI redige les siens a
    partir de ces faits, la TUI redige les siens a partir des memes faits, et les
    deux disent donc la meme chose sans qu'aucune ne recopie l'autre.
    """

    #: Le `LotComposition` de `compose_lot_plan`, verbatim. Il porte
    #: `page_count`, `frames_per_page`, `template_id`, `patch_preset_id`,
    #: `gamut_map_id`, `pdf_filename`, `scan_dpi`, `warnings` et `pages`.
    plan: object
    #: Le chemin **reellement ecrit**, jamais recompose (`EPIC11-ARB-90`).
    output_path: Path
    #: Le resultat de `pdf_manifest.persist_pdf_generation`.
    persisted: object
    #: Le rang du tirage, ou `None` au rang 1 -- ou le nom n'ecrit aucun
    #: fragment et ou le payload omet strictement le champ (`EPIC11-ARB-91`).
    version_rank: int | None
    #: Les constats **informatifs** de `verify_extracted_lot`, dans leur ordre.
    reserves_informatives: tuple[str, ...] = ()
    #: L'espace couleur cible ecrit au manifest par defaut, ou `None`.
    espace_couleur_par_defaut: str | None = None
    #: Le rang du tirage d'ORIGINE, **transporte** depuis `io.version_ranks`
    #: (`EPIC11-ARB-181`). Voir :class:`TirageDejaLa` pour le motif : c'est le
    #: meme, et le champ voyage sur les deux objets que le coeur rend a un
    #: ecran plutot que sur un canal a part.
    rang_origine: int = version_ranks.RANG_ORIGINE


@dataclass(frozen=True)
class PageDeCalibration:
    """Ce que la generation de la page de calibration a produit."""

    plan: object
    output_path: Path
    espace_couleur_par_defaut: str | None = None


# ---------------------------------------------------------------------------
# Ce qu'une interface doit savoir AVANT d'ecrire -- lecture seule
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TirageDejaLa:
    """Ce que le coeur sait des tirages d'un lot **avant** qu'on en ecrive un.

    Deux nombres et rien d'autre de calcule : celui du tirage le plus recent, et
    celui que la prochaine passe emploierait. Ils viennent tous deux de
    `pdf_composition`, jamais d'un comptage refait ailleurs.

    **Pourquoi ce point d'entree existe, et il se mesure plutot qu'il ne se
    suppose.** L'ecran de conflit de l'atelier Pdf (`E5-3b` / `E5-3c`) doit
    afficher ces deux nombres **avant** la confirmation (`EPIC11-ARB-172`), et
    la TUI a interdiction de les calculer : la frontiere
    `test_aucun_module_de_la_TUI_ne_CALCULE_un_rang` compte a zero, sur tout
    `src/mixed_media_utility/tui/`, les noms des fonctions de `pdf_composition`
    qui les produisent. Sans ce relais, l'ecran ne serait joignable par aucun
    parcours -- ce qui est exactement l'etat dans lequel le lot G l'a livre.

    **Il n'ECRIT rien, et c'est ce qui le rend sur** (AC 7.7, arbitrage neuf E de
    la fiche 11.7 : « seule l'ecriture consomme un rang »). Lire cet etat,
    l'afficher puis annuler laisse le manifeste et le disque intacts ; un banc le
    mesure aux inodes et au `st_mtime_ns`, jamais par un condensat.
    """

    lot_id: str
    #: Le rush du lot, tel que le manifeste le declare. `None` quand le lot est
    #: absent du document -- l'appelant le verra a `absent`.
    rush_id: str | None
    #: Le rang du tirage le plus recent, ou **zero** quand ce lot n'a jamais ete
    #: imprime. Zero et non `None` : c'est un cardinal de tirages consommes, et
    #: `if etat.present` se lit alors sans garde.
    present: int
    #: Le rang que la prochaine passe emploierait si elle n'ecrasait rien.
    a_ecrire: int
    #: L'entree d'inventaire du tirage le plus recent, ou `None`. Elle porte le
    #: chemin **reellement ecrit** (`EPIC11-ARB-90`), que l'interface affiche.
    entree: dict | None = None
    #: Les rangs de ce lot qu'un scan a vus passer (`EPIC11-ARB-176`).
    scannes: tuple[int, ...] = ()
    #: Le texte du refus quand les rangs sont epuises, sinon `None`. Il est
    #: **relaye tel quel** : le formuler ici en ferait une seconde redaction du
    #: refus que `io.version_ranks` possede.
    refus: str | None = None
    #: Vrai quand le manifeste ne declare pas ce lot. L'appelant refuse alors,
    #: il ne devine pas un etat.
    absent: bool = False
    #: Le rang du tirage d'ORIGINE, **transporte** depuis `io.version_ranks`
    #: (`EPIC11-ARB-181`, tranche par Egan le 2026-09-02).
    #:
    #: **Pourquoi le coeur le donne au lieu de laisser l'ecran le savoir.** La
    #: valeur vit dans `io/version_ranks.py`, le module qui porte seul toute la
    #: regle des rangs (`EPIC11-ARB-108`). La TUI la recopiait **quatre fois en
    #: litteral**, et les deux frontieres qui devraient attraper une recopie
    #: comptent des **noms** : un `1` leur est structurellement invisible. Le
    #: geste evident -- nommer la constante -- etait par ailleurs interdit, la
    #: frontiere de la story 11.6 defendant a la TUI de nommer ce module. Les
    #: deux regles se contredisaient, et aucun document ne le disait.
    #:
    #: Le transport les reconcilie **sans en amender aucune** : la TUI ne nomme
    #: pas la constante et ne la recopie pas, elle l'**affiche** -- exactement
    #: ce qu'`EPIC11-ARB-92` exige deja du rang d'un tirage existant.
    #:
    #: Il se pose sur cet objet-ci parce que c'est celui que le coeur **rend
    #: deja** a l'ecran : ce n'est pas un second canal, c'est un champ de plus
    #: sur celui qui existe.
    rang_origine: int = version_ranks.RANG_ORIGINE

    @property
    def deja_imprime(self) -> bool:
        """Vrai quand au moins un tirage de ce lot existe.

        C'est **la** condition qui monte l'ecran de conflit, et elle se lit d'un
        seul champ : un lot jamais imprime n'a rien a trancher, et lui montrer un
        ecran de conflit serait un ecran sans objet.
        """
        return self.present >= 1


def etat_des_tirages(project_dir, *, lot_ids,
                     manifest=None) -> tuple[TirageDejaLa, ...]:
    """L'etat des tirages de chaque lot demande, **dans l'ordre demande**.

    :param project_dir: le dossier du projet ouvert.
    :param lot_ids: les `lot_id` a interroger, dans l'ordre du plan de la passe.
    :param manifest: le manifeste **deja lu**, ou `None` pour le relire ici. Une
        interface qui l'a sous la main ne paie donc pas une seconde lecture, et
        surtout ne juge pas sur un document different de celui qu'elle affiche.

    **L'ordre rendu est celui recu**, jamais un tri : l'appelant apparie les deux
    listes par position, et un tri silencieux ici ecrirait l'etat d'un lot sur un
    autre -- la classe de defaut que ce depot a deja payee trois fois (mutants
    `M33` de la 5.6, `M25` de la 5.7, cinq survivants de la 5.8).

    **La boucle va jusqu'au bout.** Un lot absent du manifeste, ou dont les rangs
    sont epuises, rend une entree qui le **dit** et la passe continue : sortir a
    la premiere anomalie ferait disparaitre l'etat des lots suivants en silence,
    et c'est ce qu'un mutant `continue` -> `break` produit.

    Aucune ecriture, aucun refus leve : les deux anomalies voyagent dans les
    champs `absent` et `refus`. Un appelant qui veut refuser le fait avec ce
    qu'il lit ; une lecture qui leverait obligerait l'interface a envelopper
    chaque lot d'un `try`, et le premier oubli ferait tomber l'atelier.
    """
    project_dir = Path(project_dir)
    if manifest is None:
        manifest = _manifeste_lu_sans_lever(project_dir)
    lots = {l.get("lot_id"): l for l in (manifest or {}).get("lots") or []
            if isinstance(l, dict)}
    project_id = (manifest or {}).get("project_id")

    etats: list[TirageDejaLa] = []
    for lot_id in lot_ids:
        lot = lots.get(lot_id)
        if lot is None:
            etats.append(TirageDejaLa(lot_id=lot_id, rush_id=None, present=0,
                                      a_ecrire=0, absent=True))
            continue
        rush_id = lot.get("rush_id")
        etats.append(_etat_d_un_lot(project_dir, manifest, lot,
                                    lot_id=lot_id, rush_id=rush_id,
                                    project_id=project_id))
    return tuple(etats)


def _manifeste_lu_sans_lever(project_dir: Path):
    """Le manifeste du projet, ou `None` -- une LECTURE ne refuse pas.

    Cette fonction est consultee avant toute ecriture, souvent pour dessiner un
    ecran : un projet sans manifeste, ou dont le manifeste est illisible, doit
    rendre « je ne sais rien » et laisser le refus aux gardes du point d'entree
    qui ecrit. C'est ce que `refuser_l_ouverture_du_projet` fait deja, au moment
    ou il faut le faire.
    """
    chemin = project_dir / extraction_manifest.MANIFEST_FILENAME
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _etat_d_un_lot(project_dir: Path, manifest, lot, *, lot_id, rush_id,
                   project_id) -> TirageDejaLa:
    """L'etat d'un seul lot. Les deux rangs viennent de `pdf_composition`."""
    scannes = tuple(sorted(
        rang for rang in (lot.get(scan_manifest.SCANNED_VERSION_RANKS_FIELD)
                          or [])
        if isinstance(rang, int) and not isinstance(rang, bool)))
    try:
        a_ecrire = pdf_composition.resolve_sheets_version_rank(
            project_dir, project_id=project_id, rush_id=rush_id,
            lot_id=lot_id, manifest=manifest)
    except pdf_composition.LotContentError as refus:
        # Les rangs sont epuises. Le texte du coeur voyage **tel quel** :
        # `EcranRangsEpuises` l'affiche sans le reformuler, et le present reste
        # lisible pour que l'ecran sache de quel tirage il parle.
        present = pdf_composition.sheets_version_watermark(
            manifest, lot_id, project_dir,
            project_id=project_id, rush_id=rush_id)
        return TirageDejaLa(lot_id=lot_id, rush_id=rush_id, present=present,
                            a_ecrire=present,
                            entree=_entree_du_rang(lot, present),
                            scannes=scannes, refus=str(refus))
    if a_ecrire < naming.VERSION_RANK_MIN:
        # **« Aucun tirage, jamais : le prochain est l'ORIGINE. »** Cette garde
        # vit deja dans `resolve_sheets_version_rank`, et c'est SA reponse qu'on
        # lit ici plutot que de la reecrire : la ligne d'eau, elle, rend le rang
        # d'origine meme quand rien n'a jamais ete ecrit, si bien que la lire
        # seule ferait passer un lot jamais imprime pour un lot deja imprime --
        # et lui montrerait un ecran de conflit sans objet.
        return TirageDejaLa(lot_id=lot_id, rush_id=rush_id, present=0,
                            a_ecrire=a_ecrire, scannes=scannes)
    present = pdf_composition.sheets_version_watermark(
        manifest, lot_id, project_dir,
        project_id=project_id, rush_id=rush_id)
    return TirageDejaLa(lot_id=lot_id, rush_id=rush_id, present=present,
                        a_ecrire=a_ecrire,
                        entree=_entree_du_rang(lot, present),
                        scannes=scannes)


def _entree_du_rang(lot, rang: int) -> dict | None:
    """L'entree d'inventaire du tirage de `rang`, ou `None`.

    Le tirage d'origine **n'ecrit pas** son rang a l'inventaire
    (`EPIC11-ARB-91`) : une entree sans champ vaut donc le premier, et c'est ce
    que la lecture traduit ici plutot que dans l'interface -- « faire cette
    jonction dans un ecran serait la convention en deux exemplaires ».

    La boucle va jusqu'au bout de l'inventaire, et la cible n'y est ni la
    premiere ni la derniere des que le lot a trois tirages : c'est la position
    qu'un banc doit lui donner.
    """
    if rang < 1:
        return None
    for entree in lot.get(pdf_manifest.SHEETS_INVENTORY_FIELD) or []:
        if not isinstance(entree, dict):
            continue
        declare = entree.get("version_rank")
        declare = (declare if isinstance(declare, int)
                   and not isinstance(declare, bool) else 1)
        if declare == rang:
            return entree
    return None


# ---------------------------------------------------------------------------
# Le journal -- une seule recette, celle qui vivait dans `cli`
# ---------------------------------------------------------------------------

def ouvrir_le_journal(project_dir: Path) -> logging.Logger:
    """Logger de `makepdf`: `logs/makepdf.log` + console (AC 8 de la 4.1).

    Deplace de `cli._configure_makepdf_logger`, qui n'en est plus qu'un relais :
    une seconde recette de journalisation divergerait au premier reglage change,
    et c'est la trace DURABLE que la revue 5.11 avait deja trouvee muette une
    fois.
    """
    logger = logging.getLogger(f"mixed_media_utility.makepdf.{project_dir.resolve()}")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    log_path = project_dir / project_layout.LOGS_DIRNAME / "makepdf.log"
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console_handler)

    return logger


def _journal(logger: logging.Logger | None) -> logging.Logger:
    """Le journal de la passe, ou celui du module quand l'appelant n'en donne pas.

    Le PARAMETRE ne change aucun comportement observable -- ni le PDF ecrit, ni
    les exceptions levees, ni le manifest : meme contrat que le `logger` de
    `scan_detect.run_scan_detect`.
    """
    return logger if logger is not None else logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Les gardes d'ouverture -- AVANT tout journal, comme dans le corps d'origine
# ---------------------------------------------------------------------------

def motif_de_designation_du_lot(lot, rush, fps) -> str | None:
    """Le lot est-il designe correctement ? Rend le motif de refus, ou `None`.

    Extrait de `makepdf_command` par la story 5.22 : la generation de la page de
    calibration a la demande designait son lot **exactement** de la meme facon,
    et les deux refus doivent porter le meme vocabulaire. Deux redactions
    auraient diverge au premier ajout, et l'operateur aurait lu deux fois deux
    phrases differentes pour la meme faute.
    """
    designation_par_rush = rush is not None or fps is not None
    if lot and designation_par_rush:
        return ("designer le lot soit par --lot, soit par le couple "
                "--rush/--fps, jamais les deux.")
    if not lot and (rush is None or fps is None):
        return ("designer le lot a imprimer avec --rush <rush_id> et "
                "--fps <cadence cible>, ou directement avec --lot <lot_id>.")
    return None


def refuser_l_ouverture_du_projet(project_dir: Path, *, lot=None, rush=None,
                                  fps=None) -> Path:
    """Les trois gardes qui precedent **toute** ouverture de journal.

    Elles precedent le journal dans le corps d'origine, et ce n'est pas un
    detail de mise en page : `mmu makepdf --project <inexistant>` n'a jamais
    cree ni arborescence, ni `logs/makepdf.log`. Les garder ici, avant
    `ensure_project_layout`, est ce qui preserve cette propriete -- le dossier
    d'identite la mesure sur quatre scenarios.

    Rend le chemin du manifest, qui est ce que la suite consomme.
    """
    if not project_dir.is_dir():
        raise RefusDeMakepdf(
            f"Le dossier projet n'existe pas: {project_dir}. makepdf "
            "opere sur un projet existant (cree par extract), il n'en cree pas.",
            motif=MOTIF_PROJET_INEXISTANT,
        )
    manifest_path = project_dir / extraction_manifest.MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise RefusDeMakepdf(
            f"Aucun manifest {extraction_manifest.MANIFEST_FILENAME} dans "
            f"{project_dir}. Extraire un lot d'abord (commande extract).",
            motif=MOTIF_MANIFEST_ABSENT,
        )
    motif = motif_de_designation_du_lot(lot, rush, fps)
    if motif is not None:
        raise RefusDeMakepdf(motif, motif=MOTIF_DESIGNATION_DU_LOT)
    return manifest_path


def refuser_l_ouverture_de_la_mire(project_dir: Path) -> Path:
    """Les deux gardes de la page de calibration.

    **Deux et non trois** : la mire ne designe aucun lot (story 5.23, elle se
    genere avant toute extraction). Et ses deux messages ne sont pas ceux des
    planches -- ils nomment ce que la mire, elle, vient chercher dans le projet
    (son espace couleur cible). Les fondre en un seul jeu changerait deux
    phrases que l'operateur lit aujourd'hui.
    """
    if not project_dir.is_dir():
        raise RefusDeMakepdf(
            f"Le dossier projet n'existe pas: {project_dir}. La page de "
            "calibration se genere dans un projet existant (cree par extract).",
            motif=MOTIF_PROJET_INEXISTANT,
        )
    manifest_path = project_dir / extraction_manifest.MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise RefusDeMakepdf(
            f"Aucun manifest {extraction_manifest.MANIFEST_FILENAME} dans "
            f"{project_dir}. La page de calibration se range dans un projet et lit "
            "son espace couleur cible: creer le projet d'abord (commande extract).",
            motif=MOTIF_MANIFEST_ABSENT,
        )
    return manifest_path


def appliquer_l_espace_couleur_par_defaut(project_dir: Path) -> str | None:
    """Renseigner `color.target_colorspace` au manifest s'il est absent.

    Ne touche **jamais** une valeur deja presente, quelle qu'elle soit: c'est
    le choix explicite d'un operateur, jamais ecrase par un defaut. Rend la
    valeur ecrite si une ecriture a eu lieu, `None` sinon (rien a faire, ou pas
    de manifest lisible -- les gardes d'ouverture ont deja verifie sa presence
    avant que cette fonction ne soit appelee, donc ce second cas ne devrait pas
    se produire en pratique).

    Reutilise `_atomic_write`/`_load_existing_manifest` d'`extraction_manifest`
    plutot que d'en ecrire une seconde version -- meme principe que celui
    documente dans `io/pdf_manifest.py` (« Reprendre, ne pas copier »).
    """
    manifest_path = project_dir / extraction_manifest.MANIFEST_FILENAME
    existing = _load_existing_manifest(manifest_path)
    if existing is None:
        return None
    color = existing.get("color") or {}
    if "target_colorspace" in color:
        return None
    manifest = json.loads(json.dumps(existing))
    color = dict(manifest.get("color") or {})
    color["target_colorspace"] = DEFAULT_TARGET_COLORSPACE
    manifest["color"] = color
    _atomic_write(manifest_path, manifest)
    return DEFAULT_TARGET_COLORSPACE


# ---------------------------------------------------------------------------
# Le point d'entree des PLANCHES d'un lot
# ---------------------------------------------------------------------------

def generer_les_planches_du_lot(
    project_dir,
    *,
    lot=None,
    rush=None,
    fps=None,
    orientation=None,
    frames_per_page=None,
    margin_preset=None,
    patch_preset=None,
    gamut_map_id=None,
    render_dpi=None,
    page_format=None,
    geometry_version=None,
    overwrite=False,
    logger=None,
    rappel_progression=None,
    generated_at=None,
) -> PlanchesDuLot:
    """Composer, ecrire et declarer les planches d'un lot -- et **lever** ce qui refuse.

    :param project_dir: le dossier projet ouvert.
    :param lot: le `lot_id` canonique, ou `None` -- le couple `rush`/`fps` le
        resout alors par la convention unique `io.naming.build_lot_id`. Les deux
        designations sont exclusives, et leur refus est
        :func:`motif_de_designation_du_lot`.
    :param overwrite: viser le tirage **existant** au lieu du voisin
        (`EPIC11-ARB-89`, `EPIC11-ARB-104`).
    :param logger: journal de la passe. Optionnel : la CLI passe le sien
        (`logs/makepdf.log`), une interface n'en passe aucun et le journal du
        module suffit. Le PARAMETRE ne change aucun comportement observable.
    :param rappel_progression: le canal de progression du **rendu** (AC 2.6,
        lot B4, deja livre et gele). Il descend **tel quel** a
        `pdf_render.render_lot_pdf`, qui l'ouvre dans un
        `progression.EmetteurProgression` : un jalon par page reellement
        ecrite, `total` valant `plan.page_count`, aucun jalon avant la premiere
        page. **Aucun second mecanisme** n'est redige ici.

        `AR3` : il est OPTIONNEL et son absence ne change **rien** a
        l'observable -- meme PDF, memes exceptions, meme journal. C'est le seul
        parametre neuf de ce deplacement, et c'est le cablage que la tache B5
        demandait : le canal etait livre par le lot B4 et branche nulle part.
    :param generated_at: l'instant **imprime** sur chaque planche. Pris ici par
        defaut, et non au fond de la composition : il ne va ni dans le QR ni
        dans le nom du fichier.
    :raises RefusDeMakepdf: projet inexistant, manifest absent, designation de
        lot fautive, lot non conforme, conflit de sortie.

    Les autres refus -- vocabulaire, geometrie, budget QR, nommage, schema,
    persistance -- traversent **inchanges** : les deguiser en refus de ce module
    aplatirait la hierarchie que chaque module a construite et perdrait le
    chainage.
    """
    project_dir = Path(project_dir)
    manifest_path = refuser_l_ouverture_du_projet(
        project_dir, lot=lot, rush=rush, fps=fps)

    project_layout.ensure_project_layout(project_dir)
    logger = _journal(logger)

    # Validation complete (schema v2 + garde anti-chemins-absolus): makepdf
    # consomme lots[].frames_dir pour lire des fichiers, un manifest non
    # valide ne doit jamais atteindre la composition ni le rendu (revue
    # 4.1 du 2026-08-06).
    manifest = validate_manifest(manifest_path)
    defaulted_colorspace = appliquer_l_espace_couleur_par_defaut(project_dir)
    if defaulted_colorspace is not None:
        logger.info(
            "color.target_colorspace absent du manifest: defaut '%s' "
            "applique et persiste dans project.json.",
            defaulted_colorspace,
        )
        manifest = validate_manifest(manifest_path)
    if lot:
        lot_id = lot
    else:
        # `rush` porte le rush_id canonique du manifest (pas un chemin de
        # fichier video comme extract): le couple resout lot_id via la
        # convention unique io.naming.build_lot_id.
        lot_id = naming.build_lot_id(rush, fps)

    verification = extraction_manifest.verify_extracted_lot(
        project_dir, manifest, lot_id
    )
    if not verification.ok:
        logger.error(
            "Lot %s non conforme: %s", lot_id, ", ".join(verification.blocking_findings)
        )
        lots_disponibles = ", ".join(
            str(l.get("lot_id"))
            for l in manifest.get("lots") or []
            if isinstance(l, dict)
        ) or "(aucun)"
        raise LotNonConforme(
            f"le lot '{lot_id}' n'est pas imprimable en l'etat. "
            "Constats bloquants:",
            lot_id=lot_id,
            verification=verification,
            lots_disponibles=lots_disponibles,
        )
    informational = [
        code
        for code in verification.findings
        if code in extraction_manifest.INFORMATIONAL_VERIFICATION_CODES
    ]
    for code in informational:
        logger.info("Reserve informative sur le lot %s: %s", lot_id, code)

    # Le rang de version se resout AVANT la composition (`EPIC11-ARB-91`):
    # il entre dans le nom du fichier, dans l'etiquette imprimee et dans le
    # payload QR, donc il doit etre connu au moment ou le plan se construit
    # -- l'ajouter apres coup ferait diverger les trois porteurs.
    #
    # **ET IL SE RESOUT INCONDITIONNELLEMENT** (mesure du 2026-09-02,
    # `mesure-2026-09-02-rebond-de-coeur-arb-171.md`). Le calcul vivait
    # derriere `if args.nouvelle_version`, trente-sept lignes au-dessus de
    # la detection de conflit qui, seule, poussait l'operateur a passer ce
    # drapeau. Les deux etaient separes dans le code et COUPLES par le
    # parcours. Des que le nom porte la mise en page (`EPIC11-ARB-171`),
    # relancer le meme lot dans une autre forme ne declenche plus de
    # conflit -- c'est ce qu'`EPIC11-ARB-175` veut --, donc plus personne
    # ne passait le drapeau, donc le rang n'etait plus calcule : le PDF
    # sortait sans fragment `_vN` et `rang_ecrit = record.version_rank or 1`
    # declarait au manifeste un **tirage 1** que l'en-tete imprime et le QR
    # recopiaient, sur un lot qui en etait a son quatrieme. C'est le
    # mensonge sur papier qu'`EPIC11-ARB-92` existe pour interdire, et il
    # serait ne d'une modification qui, prise isolement, a l'air correcte.
    rush_id = next(
        (l.get("rush_id") for l in manifest.get("lots") or []
         if isinstance(l, dict) and l.get("lot_id") == lot_id),
        None,
    )
    rang_de_version = pdf_composition.resolve_sheets_version_rank(
        project_dir,
        project_id=manifest.get("project_id"),
        rush_id=rush_id,
        lot_id=lot_id,
        manifest=manifest,
    )
    if overwrite:
        # **`--overwrite` vise le tirage EXISTANT, pas son voisin**
        # (`EPIC11-ARB-89`, verbatim d'Egan : « toujours permettre une
        # reecriture plutot qu'un blocage sec [...] la rigueur de l'outil
        # ne doit pas empecher une ecriture destructive CONSCIENTE » ; et
        # `EPIC11-ARB-104` : « Tout doit etre versionnable OU ecrase », le
        # OU exigeant que les DEUX branches existent).
        #
        # Sans cette ligne, le decouplage ci-dessus rendrait le drapeau
        # INERTE : le rang avancant a chaque passe, le nom serait toujours
        # neuf et `--overwrite` n'aurait plus rien a ecraser. La branche
        # destructive d'`EPIC11-ARB-104` disparaitrait en silence, et le
        # message de refus qui prescrit `--overwrite` prescrirait un
        # drapeau sans effet. C'est aussi ce qui donne son sens a « une
        # reponse au conflit residuel, meme nom et meme forme » : le seul
        # chemin qui reproduit un nom deja pris est celui-ci.
        #
        # La ligne d'eau se LIT, elle ne se deduit pas de `rang - 1` : le
        # calcul vit dans `io.version_ranks` et une seconde copie serait
        # une seconde verite (`EPIC11-ARB-108`).
        ligne_d_eau = pdf_composition.sheets_version_watermark(
            manifest, lot_id, project_dir,
            project_id=manifest.get("project_id"), rush_id=rush_id)
        if ligne_d_eau >= 1:
            rang_de_version = ligne_d_eau
    if rang_de_version == 1:
        # Aucun tirage jamais: le rang 1 n'ecrit aucun fragment, et le
        # payload OMET strictement le champ (`EPIC11-ARB-91`). La garde
        # qui rend ce 1 vit deja dans `resolve_sheets_version_rank`
        # (« aucun tirage, jamais : le prochain est l'ORIGINE ») et n'est
        # pas reecrite ici -- ceci n'en est que la traduction en absence de
        # fragment.
        #
        # **Ce repli devient le comportement NOMINAL**, et c'est l'effet de
        # bord assume du decouplage : `--nouvelle-version` sur un lot
        # jamais imprime reste sans effet plutot que refuse. Le drapeau
        # cesse d'etre la condition du calcul pour n'etre plus qu'une
        # reponse au conflit residuel -- meme lot, meme mise en page, meme
        # rang --, cas que le rang qui avance rend desormais rare.
        rang_de_version = None

    plan = pdf_composition.compose_lot_plan(
        manifest=manifest,
        lot_id=lot_id,
        orientation=orientation,
        frames_per_page=frames_per_page,
        margin_preset=margin_preset,
        patch_preset=patch_preset,
        gamut_map_id=gamut_map_id,
        render_dpi=render_dpi,
        page_format=page_format,
        geometry_version=geometry_version,
        version_rank=rang_de_version,
    )

    # `EPIC11-ARB-225` : `planches/` pour toute planche neuve, et le dossier
    # d'avant si CE fichier y est deja -- sans quoi le refus d'ecrasement
    # juste en dessous serait muet sur un projet ancien et rendrait un
    # doublon la ou l'operateur a consenti a un remplacement.
    output_path = project_layout.chemin_de_planche(project_dir, plan.pdf_filename)
    if output_path.exists() and not overwrite:
        # TROIS issues, jamais une seule (`EPIC11-ARB-89`). La redaction
        # d'origine ne proposait que `--overwrite` -- la destruction comme
        # unique sortie --, et c'etait l'une des deux dettes de `makepdf`
        # recensees par la frontiere de conformite. Ce qui bloquait sa
        # levee etait de savoir si la convention `_v2` se transposait a une
        # planche ; `EPIC11-ARB-91` l'a tranche, en ajoutant les deux
        # porteurs qu'un nom de fichier ne remplace pas : l'etiquette
        # imprimee et le payload QR.
        #
        # **Ce refus est DEFENSIF depuis le lot B0 bis** : le rang avancant a
        # chaque passe, le nom vise est toujours neuf et aucun parcours
        # d'operateur n'y mene plus. Il reste ici parce qu'un fichier pose a
        # la main sous ce nom, lui, y menerait -- et parce qu'un refus retire
        # est un refus que plus personne ne remet quand la condition revient.
        raise ConflitDeSortie(
            f"{output_path} existe deja. Trois issues: relancer avec "
            "--nouvelle-version pour imprimer un tirage voisin sans toucher a "
            "celui-ci (son rang apparaitra sur la planche ET dans son QR); "
            "relancer avec --overwrite pour le remplacer sciemment; ou "
            "supprimer ce qui est devenu inutile "
            "(`mmu project remove --lot <id>`, qui retire le lot et ses "
            "planches).",
            output_path=output_path,
        )

    for warning in plan.warnings:
        logger.warning(warning)

    # La compression appliquee est **nommee au journal**, et une compression
    # non triviale porte sa reserve: `G^-1` n'est pas implementee (story
    # 5.4b), donc une planche comprimee produit aujourd'hui des exports
    # delaves que rien ne redresse. Le taire ferait de cette option un
    # piege silencieux pour qui la decouvre dans l'aide.
    logger.info("compression de gamut: %s", plan.gamut_map_id)
    if plan.gamut_map_id != pdf_composition.DEFAULT_GAMUT_MAP:
        logger.warning(
            "COMPRESSION_SANS_EXPANSION: les frames sont comprimees par %s, "
            "et aucune etape du scan ne les decomprime encore (l'expansion "
            "appartient a la story 5.4b). Les images reconstruites depuis "
            "ces planches seront delavees tant que G^-1 n'est pas livree.",
            plan.gamut_map_id,
        )

    if generated_at is None:
        generated_at = datetime.now(timezone.utc)
    pdf_render.render_lot_pdf(plan, project_dir, output_path,
                              generated_at=generated_at,
                              rappel_progression=rappel_progression)

    # Story 5.11: la declaration au manifest vient **apres** l'ecriture
    # reussie du PDF, jamais avant -- motif exact de `persist_extraction`,
    # appelee apres l'ecriture reussie des TIFF. Un manifest qui declarerait
    # `state: "pdf"` alors que le rendu a echoue decrirait une planche que
    # personne n'a. Les valeurs sont lues du plan deja utilise pour le QR
    # et le rendu: aucune seconde resolution.
    try:
        persisted = pdf_manifest.persist_pdf_generation(
            project_dir,
            pdf_manifest.PdfRecord.from_plan(
            plan,
                # Le chemin REELLEMENT ecrit, pas un chemin recompose
                # (`EPIC11-ARB-90`) : c'est `output_path` qui vient de servir
                # a `render_lot_pdf` deux lignes plus haut. Sans cela, la
                # suppression retrouvait la planche en recalculant son nom et
                # le resolveur de rang comptait les tirages sur le disque --
                # un PDF renomme a la main echappait aux deux.
                pdf_path=output_path.relative_to(project_dir).as_posix(),
                version_rank=rang_de_version,
            ),
        )
    except ExtractionPersistenceError as exc:
        # **Le chemin du PDF voyage avec l'echec**, et l'exception remonte
        # ensuite **telle quelle** -- `raise` nu, meme objet, chainage intact
        # (AC 2.3 : « les refus nommes voyagent avec le corps »).
        #
        # Sans cet attribut, l'appelant n'aurait aucun moyen de nommer le
        # fichier qui EST sur le disque : la ligne « Le PDF ... a bien ete
        # ecrit et reste en place » lisait jusqu'ici une variable locale de
        # `makepdf_command`, que l'enveloppe n'a plus. Le recomposer de son
        # cote serait re-deriver une convention que `io.naming` possede, et
        # une planche renommee a la main echapperait a la phrase.
        exc.pdf_path = output_path
        raise

    # **Le compte rendu de succes vit DANS le corps, et c'est un correctif**
    # (liaison de la vague 3, 2026-08-30). Il vivait apres, et `main` a pose
    # `finally: _close_logger_handlers` (`a190fb0`) : la fermeture s'executait
    # donc AVANT ce `logger.info`, qui partait dans un logger sans aucun
    # handler et **disparaissait en silence** de `logs/makepdf.log`.
    #
    # Il existe precisement parce qu'une revue avait constate que ce journal
    # « restait muet sur le chemin nominal » (revue 5.11, couche 1) : la
    # fermeture le re-rendait muet. `stdout` gardait la ligne -- elle y est
    # aussi imprimee par l'enveloppe --, donc l'operateur voyait ; c'est la
    # trace DURABLE qui etait perdue, celle qu'on relit apres coup.
    #
    # Trouve par le dossier d'identite de la story 11.4b, qui compare 42
    # invocations reelles ligne a ligne. Aucune relecture ne l'aurait vu :
    # le `finally` est correct, le bloc de succes est correct, seul leur
    # ORDRE ne l'etait pas. **C'est aussi ce qui fixe la frontiere de ce
    # deplacement** : le journal est ferme par l'enveloppe, apres que le
    # corps a fini d'ecrire dedans.
    logger.info("PDF ecrit: %s (%d page(s))", output_path, plan.page_count)
    return PlanchesDuLot(
        plan=plan,
        output_path=output_path,
        persisted=persisted,
        version_rank=rang_de_version,
        reserves_informatives=tuple(informational),
        espace_couleur_par_defaut=defaulted_colorspace,
    )


# ---------------------------------------------------------------------------
# Le point d'entree de la PAGE DE CALIBRATION
# ---------------------------------------------------------------------------

def generer_la_page_de_calibration(
    project_dir,
    *,
    scan_chain_label,
    comment=None,
    orientation=None,
    frames_per_page=None,
    margin_preset=None,
    patch_preset=None,
    gamut_map_id=None,
    render_dpi=None,
    page_format=None,
    geometry_version=None,
    overwrite=False,
    logger=None,
    rappel_progression=None,
    generated_at=None,
    generated_on=None,
) -> PageDeCalibration:
    """Composer et ecrire la **page de calibration seule** (story 5.22, AC 8).

    `EPIC5-ARB-80` decision 7 retire l'insertion automatique de cette page a
    l'index 0 de chaque lot: elle se genere maintenant explicitement, s'imprime,
    se scanne une fois, et `scan calibrate` en tire le profil de la **chaine**.

    Trois differences avec les planches, et chacune a un motif:

    * **le manifest n'est pas touche**. `lots[].state = "pdf"` declare que les
      **planches** du lot sont imprimees (story 5.11, `EPIC5-ARB-20`); le
      declarer ici mentirait sur un lot dont aucune planche n'existe encore. La
      page de calibration n'appartient d'ailleurs a aucun lot: elle appartient a
      une chaine de scan, et son domicile est le fichier de profil que
      `scan calibrate` ecrit sous `versions/`;
    * **le lot n'est pas verifie** par `verify_extracted_lot`. Cette page ne
      porte aucune frame, donc l'etat des TIFF sur disque est hors de cause:
      exiger un lot conforme empecherait de generer la page de calibration
      **avant** d'avoir extrait quoi que ce soit, ce qui est precisement l'ordre
      de travail que la calibration par chaine rend possible;
    * **le refus geometrique est un refus**, la ou le lot n'avait qu'un
      avertissement (voir `compose_calibration_page_plan`).

    **Ni rush, ni fps, ni lot** (story 5.23): une page de calibration se genere
    **avant tout lot**, avant toute extraction. Le gabarit ne venait d'ailleurs
    jamais du lot -- il se resout depuis les options de geometrie, qui ne lisent
    pas le manifest.

    Un seul argument est **exige**: `scan_chain_label`. Une page anonyme ne se
    distinguerait pas d'une autre, et un projet en porte desormais autant que de
    chaines.

    :param generated_on: la date **imprimee** sur la feuille, celle du geste.
        Prise ici et pas au fond de la composition: elle ne va ni dans le QR ni
        dans le nom du fichier, donc regenerer la meme page demain rend le meme
        QR et le meme nom.
    """
    project_dir = Path(project_dir)
    manifest_path = refuser_l_ouverture_de_la_mire(project_dir)

    project_layout.ensure_project_layout(project_dir)
    logger = _journal(logger)

    manifest = validate_manifest(manifest_path)
    defaulted_colorspace = appliquer_l_espace_couleur_par_defaut(project_dir)
    if defaulted_colorspace is not None:
        logger.info(
            "color.target_colorspace absent du manifest: defaut '%s' "
            "applique et persiste dans project.json.",
            defaulted_colorspace,
        )
        manifest = validate_manifest(manifest_path)
    if generated_on is None:
        generated_on = datetime.now(timezone.utc).date()
    plan = pdf_composition.compose_calibration_page_plan(
        manifest=manifest,
        scan_chain_label=scan_chain_label,
        comment=comment,
        generated_on=generated_on,
        orientation=orientation,
        frames_per_page=frames_per_page,
        margin_preset=margin_preset,
        patch_preset=patch_preset,
        gamut_map_id=gamut_map_id,
        render_dpi=render_dpi,
        page_format=page_format,
        geometry_version=geometry_version,
    )
    # `EPIC11-ARB-225` : `planches/` pour toute planche neuve, et le dossier
    # d'avant si CE fichier y est deja -- sans quoi le refus d'ecrasement
    # juste en dessous serait muet sur un projet ancien et rendrait un
    # doublon la ou l'operateur a consenti a un remplacement.
    output_path = project_layout.chemin_de_planche(project_dir, plan.pdf_filename)
    if output_path.exists() and not overwrite:
        # TROIS issues, dont UNE NON DESTRUCTIVE (`EPIC11-ARB-89`).
        #
        # La premiere redaction n'en offrait que deux, toutes deux
        # destructrices, au motif que « deux tirages de la meme chaine sont
        # le meme document ». **Ce motif etait faux, et mesurable comme
        # tel** : `build_calibration_pdf_filename` ne prend que le projet
        # et le libelle de chaine, alors que HUIT parametres de geometrie
        # font varier la page sans entrer dans son nom (`--orientation`,
        # `--frames-par-page`, `--marge`, `--nombre-patchs`, `--gamut-map`,
        # `--dpi`, `--format`, `--geometrie`), plus `--commentaire`. Deux
        # pages de la meme chaine a `--nombre-patchs` differents sont deux
        # documents DIFFERENTS sous le meme nom.
        #
        # La troisieme issue etait donc disponible et gratuite : le libelle
        # de chaine entre dans le nom, en changer donne un fichier voisin
        # sans toucher a l'existant. C'est la sortie non destructive
        # qu'`EPIC11-ARB-89` demande en premier.
        #
        # Un rang de version reste hors sujet ici, et pour une raison qui
        # tient, elle : la page ne declare ni rush, ni lot, ni cadence
        # (`EPIC5-ARB-82`, story 5.23) -- elle sert toute une chaine --,
        # donc elle n'a pas de lot dont numeroter les tirages.
        raise ConflitDeSortie(
            f"{output_path} existe deja. Trois issues: donner un autre "
            "--chaine, qui entre dans le nom et laisse ce fichier intact (la "
            "geometrie, le nombre de patchs et le commentaire, eux, n'entrent "
            "PAS dans le nom: deux pages de la meme chaine reglees differemment "
            "se disputeraient ce fichier); relancer avec --overwrite pour le "
            "remplacer sciemment; ou supprimer ce fichier.",
            output_path=output_path,
        )
    for warning in plan.warnings:
        logger.warning(warning)
    if generated_at is None:
        generated_at = datetime.now(timezone.utc)
    pdf_render.render_lot_pdf(
        plan, project_dir, output_path,
        generated_at=generated_at,
        rappel_progression=rappel_progression,
    )
    return PageDeCalibration(
        plan=plan,
        output_path=output_path,
        espace_couleur_par_defaut=defaulted_colorspace,
    )
