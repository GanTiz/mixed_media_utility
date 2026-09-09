"""Detection geometrique des pages scannees (story 5.2).

Cette story fait passer la detection du POC de l'Epic 1 au contrat de l'Epic 4.
Le chemin POC ne connait que `layout`: **une** page A4 portrait et deux zones en
dur. Le registre `page_templates` en connait 33, dont des paysages 297x210. La
detection du POC est donc fausse pour 30 gabarits sur 33, silencieusement --
seules les trois variantes de marge du portrait 2 zones partagent la geometrie
de page de `layout`.

Ce module resout la geometrie depuis le `template_id` **que la page porte
elle-meme**, dans son QR. Il s'arrete au niveau page: localiser les zones, pas
les decouper au plus juste (5.3), pas les nommer ni les exporter (5.6), pas
ecrire de manifest (5.7). Son livrable est un document de detection que ces
quatre stories consomment, et aucune d'elles ne redetecte.

Pourquoi la geometrie ne peut pas venir d'ailleurs que du template
------------------------------------------------------------------
En paysage, `layout.page_size_px` rend toujours 210x297 et
`layout.corner_marker_centers_mm` est calcule sur ces memes constantes: l'espace
de destination de l'homographie serait transpose, et la page redressee fausse
sans qu'aucune erreur ne se leve. C'est le defaut central que cette story ferme,
et le test bloquant porte sur un template paysage.

Ce que le module mesure, et qui ne se voit pas autrement
--------------------------------------------------------
Les quatre centres de coin sont a des positions **connues en millimetres**. Leurs
positions detectees donnent donc l'echelle reellement observee par axe. C'est la
seule facon d'attraper le risque R8 -- une imprimante en « ajuster a la page » ou
un scanner en auto-fit produisent une geometrie fausse qui ne leve rien: les
frames sortent, decalees, et personne ne le sait avant de regarder le resultat.

Le rang de lecture n'est jamais le `page_index`
-----------------------------------------------
Le rang vient de l'ordre d'ingestion (story 5.1); le `page_index` est declare
par le QR. Les confronter est le travail de ce module, et c'est la **seule**
detection de lot incomplet de toute la chaine scan (risque R12): une page
manquante, une page en double ou deux lots melanges sur la meme vitre ne se
voient nulle part ailleurs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np

from . import layout, page_templates, progression, qr_codes, scan_ingest
from .detection import aruco as aruco_detection
from .extraction_previz import FINGERPRINT_PREFIX, canonical_json, fingerprint_of
from .io import payload as payload_io
from .numeric_guards import is_strict_int

#: Tolerance d'ecart d'echelle et d'aspect, au-dela de laquelle la page est
#: signalee (EPIC5-ARB-10, option « a »).
#:
#: **Valeur provisoire, a recalibrer au premier pilote papier reel.** Aucune
#: mesure terrain n'existe: comme tous les seuils de ce depot -- ArUco, QR,
#: retrait d'echantillonnage -- celui-ci est synthetique, et le pilote reel reste
#: du sur les deux orientations. 2 % represente environ 4 mm sur la diagonale
#: d'une A4, soit un ordre de grandeur au-dessus du bruit de detection d'un
#: centre de marqueur et bien en dessous d'un « ajuster a la page » d'imprimante,
#: qui deforme typiquement de 3 a 6 %.
#:
#: Le seuil porte sur **deux** ecarts distincts parce qu'ils n'ont pas la meme
#: cause terrain: une mise a l'echelle homogene vient de l'impression, une
#: divergence entre axes vient du scanner ou d'une page non plane.
SCALE_WARNING_TOLERANCE = 0.02

#: Vocabulaire **ferme** des avertissements de detection. Distinct de celui de
#: l'ingestion (5.1): melanger les deux ferait un vocabulaire dont plus personne
#: ne saurait quelle etape l'emet.
SCAN_DETECTION_WARNING_CODES: tuple[str, ...] = (
    "TEMPLATE_FROM_MANIFEST_NOT_QR",
    "PAGE_WITHOUT_QR_SYMBOL",
    "FOREIGN_MARKER_DETECTED",
    "PAGE_SCALE_OUT_OF_TOLERANCE",
    "PAGE_ASPECT_OUT_OF_TOLERANCE",
    "INGEST_SLUG_DIFFERS_FROM_LOT_ID",
    "PAGE_COUNT_DIFFERS_FROM_INGESTED",
    "PAGE_COUNT_INCONSISTENT_ACROSS_PAGES",
    "PAGE_INDEX_MISSING",
    "PAGE_INDEX_DUPLICATED",
    "PAGE_INDEX_OUT_OF_RANGE",
    "SCAN_DPI_DIFFERS_FROM_INGESTED",
)

#: Statuts fermes d'une page detectee.
PAGE_OK = "ok"
PAGE_REFUSED = "refused"
PAGE_STATUSES: tuple[str, ...] = (PAGE_OK, PAGE_REFUSED)

#: Statut porte par une page refusee **avant** que le QR ait pu etre lu: fichier
#: illisible, DPI invalide. Emprunter `DECODE_UNREADABLE` dirait « un symbole a
#: ete detecte sans pouvoir etre lu », ce qui est faux et envoie l'operateur
#: inspecter un QR qui n'a jamais ete cherche (defaut trouve par les trois
#: couches de revue de 5.2).
QR_NOT_ATTEMPTED = "not_attempted"

#: Vocabulaire ferme du champ `qr_status` du document: les quatre statuts de
#: `qr_codes` plus le sentinelle ci-dessus.
PAGE_QR_STATUSES: tuple[str, ...] = (
    qr_codes.DECODE_OK,
    qr_codes.DECODE_NO_SYMBOL,
    qr_codes.DECODE_UNREADABLE,
    qr_codes.DECODE_MULTIPLE,
    QR_NOT_ATTEMPTED,
)

#: Precision d'arrondi des flottants du document, **declaree** plutot que
#: litterale (question ouverte 3 de la story): un consommateur qui compare deux
#: documents doit pouvoir citer la precision a laquelle ils sont comparables.
DOCUMENT_FLOAT_PRECISION = 9


class ScanDetectionError(RuntimeError):
    """Base attrapable de tous les echecs durs de detection."""


class LotIdentityError(ScanDetectionError):
    """Les pages du lot ne parlent pas du meme lot.

    Deux planches de projets ou de lots differents sur la meme vitre. Choisir
    l'une des deux identites serait fabriquer un lot qui n'a jamais existe.
    """


class PageDetectionRefused(ScanDetectionError):
    """Une page ne peut pas etre exploitee, avec son motif nomme.

    Levee et rattrapee **par page**: une page en echec n'interrompt pas les
    autres (AC 7), son motif est porte au rapport et le lot continue.

    Porte le `qr_status` observe **au moment du refus** quand il est connu: sans
    lui, le document publiait `detected_but_unreadable` pour toute page refusee,
    y compris celles dont le QR avait parfaitement decode et celles dont le
    fichier n'avait meme pas pu etre ouvert.
    """

    def __init__(self, message: str, *, qr_status: str | None = None) -> None:
        super().__init__(message)
        self.qr_status = qr_status


class PageGeometryRefused(PageDetectionRefused, aruco_detection.PageGeometryError):
    """Refus dont la cause est **geometrique**: coins manquants, doubles, degeneres.

    Herite de la hierarchie geometrique existante (`detection.aruco`) plutot que
    d'en redefinir une parallele: les Dev Notes de la story posent « erreurs
    existantes a reutiliser, jamais a redefinir », et `PageGeometryError` derive
    de `ValueError` la ou `ScanDetectionError` derive de `RuntimeError`. Sans ce
    rattachement, un appelant qui attrape la base geometrique documentee -- le
    motif de `cli.py` -- ne rattraperait rien du nouveau chemin.
    """


# --------------------------------------------------------------------------
# Refus nommes (story 5.27, `EPIC7-ARB-66`)
# --------------------------------------------------------------------------
#
# Gabarit copie de `relink.REFUS_*` et de `io.reconstruction._refus_de_pile`,
# les deux precedents du depot, et ils sont d'accord: le motif voyage sur un
# **code enumere** porte par l'exception, jamais dans le texte du message.
#
# Ce que ce vocabulaire ferme, precisement: `refusal_reason` ne portait qu'une
# **phrase francaise**. Un ecran ne peut ni brancher dessus ni la traduire, et
# `qr_status` est un champ separe -- si bien qu'une planche perimee sort
# `qr_status: ok`, avec une identite lisible, `status: refused`, et se retrouve
# indistinguable d'un refus de geometrie pour qui ne lit que les champs
# structures. Le code repond a « pourquoi », la phrase repond a « quoi dire a
# l'operateur »; les deux sont publies, cote a cote, et la phrase ne bouge pas.
#
# Le code est **valide a l'emission** (`validate_refusal_code`, ci-dessous) et
# **transporte verbatim a la relecture** du document de previz: refuser tout un
# scan parce qu'une version ulterieure du logiciel a ajoute un code rendrait
# illisible un document entier pour un champ purement informatif (voir la
# discipline de lecture de `scan_previz`).

#: --- refus leves par ce module ---
REFUS_ECHELLE_NON_FINIE = "echelle-non-finie"
REFUS_ECHELLE_NON_POSITIVE = "echelle-non-positive"
REFUS_DPI_DE_SCAN_INVALIDE = "dpi-de-scan-invalide"
REFUS_TEMPLATE_ID_INVALIDE = "template-id-invalide"
REFUS_MARQUEUR_MAL_FORME = "marqueur-mal-forme"
REFUS_MARQUEUR_ID_INVALIDE = "marqueur-id-invalide"
REFUS_MARQUEUR_CENTRE_INVALIDE = "marqueur-centre-invalide"
REFUS_COINS_EN_DOUBLE = "coins-aruco-en-double"
REFUS_COINS_MANQUANTS = "coins-aruco-manquants"
REFUS_PAGE_EN_MIROIR = "page-en-miroir"
REFUS_HOMOGRAPHIE_INCALCULABLE = "homographie-incalculable"
#: Un code pour une **cause terrain**, pas un code par ligne: les trois gardes
#: de degenerescence des coins (`_assert_convex_quadrilateral`, `_measure_scale`,
#: `_similarity_residual_px`) constatent le meme fait observable -- deux centres
#: de coin confondus -- et l'operateur les traite de la meme facon. Leur donner
#: trois codes ferait croire a trois pannes distinctes.
REFUS_COINS_DEGENERES = "coins-degeneres"
REFUS_QUADRILATERE_NON_CONVEXE = "quadrilatere-non-convexe"
REFUS_PLUSIEURS_QR = "plusieurs-qr-dans-le-champ"
REFUS_QR_SANS_MANIFEST = "qr-inexploitable-sans-manifest"
#: Refus de **lot**, pas de page: il emporte la pile entiere et n'atteint donc
#: aucun document. Son code voyage sur l'exception, a cote de
#: `identities_by_read_rank`, pour la meme raison que cet attribut existe.
REFUS_PLUSIEURS_LOTS = "plusieurs-lots-sur-la-vitre"

#: --- refus TRADUITS au site de rattrapage de `_detect_one_page` ---
#:
#: Ces exceptions sont levees par `io.payload`, `page_templates` et
#: `scan_ingest`, jamais ici. Elles sont traduites **au rattrapage** plutot
#: qu'amendees a la source: l'enumeration reste entiere dans un seul module et
#: les trois autres restent hors du diff.
REFUS_PLANCHE_PERIMEE = "planche-perimee"
REFUS_PAYLOAD_SANS_VERSION = "payload-sans-version"
REFUS_PAYLOAD_INVALIDE = "payload-invalide"
REFUS_TEMPLATE_INCONNU = "template-inconnu"
REFUS_PAGE_ILLISIBLE = "page-illisible"
#: Repli **explicite** du mapping etranger: une exception d'une famille
#: rattrapee qui ne correspond a aucune entree. Il dit qu'il est generique
#: plutot que de se faire passer pour une cause precise, et il existe pour
#: qu'aucun chemin de refus ne publie `None` -- une page refusee sans code
#: serait indistinguable d'un document ecrit avant cette story.
REFUS_NON_CLASSE = "refus-non-classe"

#: Vocabulaire **ferme** des codes de refus. Distinct de
#: `SCAN_DETECTION_WARNING_CODES`: un avertissement accompagne une page acceptee,
#: un code de refus explique une page qui ne l'est pas.
SCAN_REFUSAL_CODES: tuple[str, ...] = (
    REFUS_ECHELLE_NON_FINIE,
    REFUS_ECHELLE_NON_POSITIVE,
    REFUS_DPI_DE_SCAN_INVALIDE,
    REFUS_TEMPLATE_ID_INVALIDE,
    REFUS_MARQUEUR_MAL_FORME,
    REFUS_MARQUEUR_ID_INVALIDE,
    REFUS_MARQUEUR_CENTRE_INVALIDE,
    REFUS_COINS_EN_DOUBLE,
    REFUS_COINS_MANQUANTS,
    REFUS_PAGE_EN_MIROIR,
    REFUS_HOMOGRAPHIE_INCALCULABLE,
    REFUS_COINS_DEGENERES,
    REFUS_QUADRILATERE_NON_CONVEXE,
    REFUS_PLUSIEURS_QR,
    REFUS_QR_SANS_MANIFEST,
    REFUS_PLUSIEURS_LOTS,
    REFUS_PLANCHE_PERIMEE,
    REFUS_PAYLOAD_SANS_VERSION,
    REFUS_PAYLOAD_INVALIDE,
    REFUS_TEMPLATE_INCONNU,
    REFUS_PAGE_ILLISIBLE,
    REFUS_NON_CLASSE,
)


def validate_warning_code(code: str) -> str:
    if code not in SCAN_DETECTION_WARNING_CODES:
        raise ValueError(
            f"Code d'avertissement de detection inconnu: {code!r}. Vocabulaire "
            f"ferme: {', '.join(SCAN_DETECTION_WARNING_CODES)}."
        )
    return code


def validate_refusal_code(code: str) -> str:
    """Garde du vocabulaire, **a l'emission**.

    Meme gabarit que `validate_warning_code`, et le `ValueError` nu est
    volontaire: demander un code qui n'existe pas est un defaut de
    programmation de l'appelant, pas un refus de planche. Aucune page n'est en
    cause, et un `ScanDetectionError` ici serait rattrape par page comme si une
    feuille etait en faute.
    """
    if code not in SCAN_REFUSAL_CODES:
        raise ValueError(
            f"Code de refus de detection inconnu: {code!r}. Vocabulaire "
            f"ferme: {', '.join(SCAN_REFUSAL_CODES)}."
        )
    return code


def _refus(
    code: str,
    message: str,
    *,
    classe: type[ScanDetectionError] = ScanDetectionError,
    **attributs: object,
) -> ScanDetectionError:
    """Fabriquer un refus nomme: un code enumere, une phrase, des attributs.

    `classe` choisit la branche de la hierarchie (`PageGeometryRefused` pour une
    cause geometrique, `LotIdentityError` pour un refus de lot). Les attributs
    supplementaires -- `qr_status`, `identities_by_read_rank` -- sont poses
    apres construction plutot que passes au constructeur, ce qui laisse la
    fabrique indifferente aux signatures des quatre classes.

    Passer par elle est **exige et mesure**: un test d'enumeration parcourt
    l'arbre syntaxique de ce module et echoue si un `raise` d'un refus la
    contourne, y compris pour un site ajoute plus tard.
    """
    validate_refusal_code(code)
    erreur = classe(message)
    erreur.refusal_code = code
    for nom, valeur in attributs.items():
        setattr(erreur, nom, valeur)
    return erreur


#: Traduction des exceptions **etrangeres** rattrapees par `_detect_one_page`,
#: du plus specifique au plus general.
#:
#: **L'ordre est porteur, et c'est le piege le plus cher de cette story.**
#: `PayloadSchemaVersionRefused` (la planche perimee) et `PayloadVersionMissing`
#: sont des **sous-classes** de `PayloadValidationError`. Trois formes fautives,
#: toutes plausibles: un `mapping[type(error)]` ne matche aucune sous-classe et
#: fait tout tomber au repli; une chaine d'`isinstance` qui teste la base en
#: premier fait **disparaitre** la planche perimee dans « payload invalide »; un
#: `dict` parcouru dans l'ordre d'insertion avec la base ecrite avant ses filles
#: a le meme effet, en moins visible. Aucune des trois ne casse un test qui
#: n'assert que « un code est pose »; l'ordre est donc verifie mecaniquement par
#: un test (une famille ne peut pas etre ecrite apres une de ses sous-classes).
_REFUS_ETRANGERS: tuple[tuple[type[BaseException], str], ...] = (
    (payload_io.PayloadSchemaVersionRefused, REFUS_PLANCHE_PERIMEE),
    (payload_io.PayloadVersionMissing, REFUS_PAYLOAD_SANS_VERSION),
    (payload_io.PayloadValidationError, REFUS_PAYLOAD_INVALIDE),
    (page_templates.UnknownTemplateError, REFUS_TEMPLATE_INCONNU),
    (scan_ingest.ScanIngestError, REFUS_PAGE_ILLISIBLE),
)


def _code_de_refus_etranger(error: BaseException) -> str:
    """Le code d'une exception levee hors de ce module et convertie en refus.

    Rend **toujours** un code, jamais `None`: sur un chemin de refus, l'absence
    de code est reservee aux documents ecrits avant cette story.
    """
    for famille, code in _REFUS_ETRANGERS:
        if isinstance(error, famille):
            return code
    return REFUS_NON_CLASSE


@dataclass(frozen=True)
class PageScaleMeasurement:
    """Echelle reellement observee sur la page, par axe.

    ``scale_x`` / ``scale_y`` sont des rapports de **distances entre centres de
    coin**, pas d'etendues de boite englobante. La distinction n'est pas
    cosmetique: une etendue `max - min` n'est pas invariante par rotation, si
    bien qu'une page parfaite simplement posee de travers de 0,73 degre sortait
    a plus de 2 % d'ecart -- et qu'un retrait reel de 3,2 % etait masque par
    1,22 degre de biais dans l'autre sens. Le seul instrument du risque R8
    mesurait l'inclinaison. Une distance, elle, ne bouge pas quand la feuille
    pivote.

    ``residual_px`` mesure ce que l'echelle et l'aspect ne disent pas: l'ecart,
    en pixels de la page redressee, entre les quatre coins detectes et la
    **meilleure similitude** (rotation + echelle uniforme + translation) des
    coins attendus. Ce n'est volontairement **pas** un residu de reprojection
    par l'homographie: avec quatre correspondances, `cv2.findHomography` resout
    le systeme exactement et ce residu-la vaut zero par construction -- mesure
    sur 300 quadrilateres fortement deformes, il valait 0.000000 partout. Le
    residu de similitude, lui, croit avec la perspective, la non-planeite de la
    feuille et tout appariement de coins errone.

    Il reste **publie sans seuil**: EPIC5-ARB-10 ne tranche que l'echelle et
    l'aspect, et lui en inventer un ici serait poser un chiffre que personne n'a
    mesure.
    """

    scale_x: float
    scale_y: float
    residual_px: float

    def __post_init__(self) -> None:
        # Un `inf` ou un `NaN` traverse `round()` sans obstacle, ne declenche
        # aucun avertissement (`nan > seuil` est faux) et ne casse qu'a la
        # serialisation, `canonical_json` interdisant les non-finis -- soit un
        # `ValueError` nu, hors hierarchie, apres que tout le lot a ete detecte.
        # Meme recette que `io/payload` pour `fps_target` (revue 4.5).
        for name, value in (
            ("scale_x", self.scale_x),
            ("scale_y", self.scale_y),
            ("residual_px", self.residual_px),
        ):
            if not math.isfinite(value):
                raise _refus(
                    REFUS_ECHELLE_NON_FINIE,
                    f"Mesure d'echelle non finie: {name}={value!r}. Une page dont "
                    "la geometrie est indeterminee doit etre refusee, pas publiee.",
                )
        if self.scale_x <= 0 or self.scale_y <= 0:
            raise _refus(
                REFUS_ECHELLE_NON_POSITIVE,
                f"Echelle non strictement positive: scale_x={self.scale_x!r}, "
                f"scale_y={self.scale_y!r}.",
            )

    @property
    def scale_error(self) -> float:
        return max(abs(self.scale_x - 1.0), abs(self.scale_y - 1.0))

    @property
    def aspect_error(self) -> float:
        return abs(self.scale_x / self.scale_y - 1.0)

    def as_document(self) -> dict:
        return {
            "scale_x": round(self.scale_x, 6),
            "scale_y": round(self.scale_y, 6),
            "scale_error": round(self.scale_error, 6),
            "aspect_error": round(self.aspect_error, 6),
            "residual_px": round(self.residual_px, 4),
        }


@dataclass(frozen=True)
class ForeignMarker:
    """Un marqueur detecte qui n'est pas un coin de cette page.

    Ignore pour la geometrie **et** signale: il vient d'ailleurs (planche
    voisine, gabarit d'une future version), et le taire priverait l'operateur du
    seul indice qu'il a deux planches sur la vitre.
    """

    marker_id: int
    role: str

    def as_document(self) -> dict:
        return {"marker_id": self.marker_id, "role": self.role}


@dataclass(frozen=True)
class DetectedPage:
    """Une page du lot, apres decodage et resolution de geometrie."""

    read_rank: int
    status: str
    locator_source: str
    locator_page_index: int | None
    qr_status: str
    template_id: str | None = None
    template_source: str | None = None
    project_id: str | None = None
    rush_id: str | None = None
    lot_id: str | None = None
    page_index: int | None = None
    page_count: int | None = None
    gamut_map_id: str | None = None
    corner_centers: tuple[tuple[int, float, float], ...] = ()
    foreign_markers: tuple[ForeignMarker, ...] = ()
    homography: tuple[float, ...] | None = None
    page_size_px: tuple[int, int] | None = None
    scale: PageScaleMeasurement | None = None
    frame_zones_mm: tuple[dict, ...] = ()
    frame_zones_px: tuple[dict, ...] = ()
    warnings: tuple[str, ...] = ()
    refusal_reason: str | None = None
    #: Code de refus **enumere** (story 5.27), a cote de la phrase francaise que
    #: `refusal_reason` continue de porter inchangee. Additif et a defaut `None`:
    #: une page acceptee n'en porte aucun, et un document ecrit avant cette story
    #: n'en portera jamais -- le repli du lecteur d'ecran (7.4) est permanent.
    #: L'un des `SCAN_REFUSAL_CODES`, valide a l'emission par `_refus`.
    refusal_code: str | None = None
    #: Payload QR **decode** de la page, tel que `io.payload.parse_payload` l'a
    #: rendu, ou `None` quand le QR n'a rien livre. Ajout de la story 5.7, qui
    #: cable l'orchestration: le document de detection ne porte ni `fps_target`
    #: ni les `slots`, donc ni la cadence ni les timecodes, et les stories 5.6
    #: et 5.7 vivent des deux (point H4 des arbitrages). Des deux voies
    #: ouvertes -- « 5.2 elargit son document » ou « la commande conserve les
    #: payloads decodes entre les etapes » --, c'est la seconde qui est prise:
    #: le champ vit sur l'objet en memoire et **n'entre pas** dans
    #: `as_document()`, donc ni au document de detection ni a son empreinte.
    #: Redecoder le QR une seconde fois cote orchestrateur aurait donne deux
    #: lectures possiblement divergentes de la meme planche.
    payload: dict | None = None

    def as_document(self) -> dict:
        return {
            "read_rank": self.read_rank,
            "status": self.status,
            "locator": {
                "source_path": self.locator_source,
                "page_index": self.locator_page_index,
            },
            "qr_status": self.qr_status,
            "template_id": self.template_id,
            "template_source": self.template_source,
            "project_id": self.project_id,
            "rush_id": self.rush_id,
            "lot_id": self.lot_id,
            "page_index": self.page_index,
            "page_count": self.page_count,
            "gamut_map_id": self.gamut_map_id,
            "corner_centers": [
                {"marker_id": mid, "x": round(x, 4), "y": round(y, 4)}
                for mid, x, y in self.corner_centers
            ],
            "foreign_markers": [marker.as_document() for marker in self.foreign_markers],
            "homography": (
                None
                if self.homography is None
                else [round(v, DOCUMENT_FLOAT_PRECISION) for v in self.homography]
            ),
            "page_size_px": (
                None if self.page_size_px is None else list(self.page_size_px)
            ),
            "scale": None if self.scale is None else self.scale.as_document(),
            "frame_zones_mm": [dict(zone) for zone in self.frame_zones_mm],
            "frame_zones_px": [dict(zone) for zone in self.frame_zones_px],
            "warnings": list(self.warnings),
            "refusal_reason": self.refusal_reason,
            # Le code **a cote** de la phrase, jamais a sa place: la cle est
            # celle que `gui.lecture_detection.CLE_CODE_DE_REFUS` nomme deja
            # (story 7.4, livree avant ce producteur).
            "refusal_code": self.refusal_code,
        }


@dataclass(frozen=True)
class LotDetectionReport:
    """Le document que 5.3, 5.6, 5.7 et 5.8 consomment. Aucun pixel."""

    ingest_slug: str
    scan_dpi: int
    pages: tuple[DetectedPage, ...]
    warnings: tuple[str, ...] = ()
    #: DPI declare a l'ingestion, porte au document meme quand la detection en a
    #: recu un autre: sans lui, aucun consommateur aval ne peut voir la
    #: divergence apres coup.
    ingest_declared_dpi: int | None = None

    @property
    def detected_pages(self) -> tuple[DetectedPage, ...]:
        return tuple(page for page in self.pages if page.status == PAGE_OK)

    def as_document(self) -> dict:
        return {
            "ingest_slug": self.ingest_slug,
            "scan_dpi": self.scan_dpi,
            "ingest_declared_dpi": self.ingest_declared_dpi,
            "page_count": len(self.pages),
            "detected_page_count": len(self.detected_pages),
            "warnings": list(self.warnings),
            "pages": [page.as_document() for page in self.pages],
        }


# --- geometrie de page, resolue depuis le template -------------------------


def _validate_scan_dpi(dpi: object) -> int:
    """Garde de DPI unique du module, plafond compris.

    Le plafond vient de `scan_ingest.MAX_SCAN_DPI` -- une seule valeur pour
    l'ingestion et la detection. Sans lui, un entier Python arbitrairement grand
    franchit la garde de positivite puis leve un `OverflowError` nu dans la
    conversion en flottant, qui emporte tout le lot.
    """
    if (
        not is_strict_int(dpi)
        or dpi <= 0
        or dpi > scan_ingest.MAX_SCAN_DPI
    ):
        raise _refus(
            REFUS_DPI_DE_SCAN_INVALIDE,
            f"DPI de scan invalide: {dpi!r}. Un entier de 1 a "
            f"{scan_ingest.MAX_SCAN_DPI} est attendu.",
        )
    return dpi


def resolve_page_geometry(template_id: str, dpi: int) -> dict:
    """Resoudre la geometrie complete d'une page depuis son `template_id`.

    Un `template_id` inconnu leve `UnknownTemplateError`: jamais de geometrie
    devinee, jamais de repli sur `layout.FRAME_ZONES_MM` -- un repli
    produirait deux zones portrait sur une page paysage a huit zones, et le
    resultat *aurait l'air* d'un succes.

    Convention de quantification de `frame_zones_px`, a lire avant de consommer
    ce champ: l'origine et la **taille** de chaque zone sont arrondies
    separement (`round(x*k)` et `round(w*k)`), si bien que `x + width` en pixels
    peut differer d'un pixel du meme bord recalcule depuis les millimetres --
    mesure: 54 zones sur 135 a 600 ppp. Le consommateur ne doit donc pas
    recalculer un bord depuis les millimetres et le comparer a celui-ci. Le choix
    est **volontairement** celui qui rend des tailles identiques entre zones de
    meme dimension, propriete dont l'encodage video (Epic 6) a besoin; la
    convention de bornes de tranche, elle, appartient a la story 5.3, qui est la
    premiere a decouper.
    """
    _validate_scan_dpi(dpi)
    if not isinstance(template_id, str):
        raise _refus(
            REFUS_TEMPLATE_ID_INVALIDE,
            f"Identifiant de template invalide: {template_id!r}. Une chaine est "
            "attendue -- un `template_id` non hachable ne leve pas "
            "`UnknownTemplateError` mais un `TypeError` nu.",
        )
    spec = page_templates.get_template(template_id)
    width_px, height_px = page_templates.page_size_px(spec, dpi)
    zones_px = []
    for zone in spec.frame_zones_mm:
        x_px, y_px = page_templates.mm_to_px(zone["x"], zone["y"], dpi)
        w_px, _ = page_templates.mm_to_px(zone["width"], 0, dpi)
        _, h_px = page_templates.mm_to_px(0, zone["height"], dpi)
        zones_px.append(
            {"name": zone["name"], "x": x_px, "y": y_px, "width": w_px, "height": h_px}
        )
    return {
        "spec": spec,
        "page_size_px": (width_px, height_px),
        "corner_centers_mm": page_templates.corner_marker_centers_mm(spec),
        "frame_zones_mm": tuple(dict(zone) for zone in spec.frame_zones_mm),
        "frame_zones_px": tuple(zones_px),
    }


def _partition_markers(markers: list[dict]) -> tuple[dict[int, dict], list[ForeignMarker]]:
    """Separer les coins exploitables des marqueurs etrangers.

    Premier consommateur en production de `layout.marker_role`, dont la
    politique est deja statuee normativement dans le bloc de contrat de
    `layout.py`: cette story l'applique, elle ne la re-arbitre pas.

    Un doublon d'ID de plage reservee produit lui aussi son avertissement --
    la garde de doublon du chemin POC ne regarde que les IDs de coin.
    """
    corners: dict[int, dict] = {}
    foreign: list[ForeignMarker] = []
    seen_foreign: set[int] = set()
    for marker in markers:
        _assert_marker_shape(marker)
        marker_id = marker["id"]
        role = layout.marker_role(marker_id)
        if role == layout.CORNER_ROLE:
            corners.setdefault(marker_id, marker)
            continue
        if marker_id not in seen_foreign:
            seen_foreign.add(marker_id)
            foreign.append(ForeignMarker(marker_id, role))
    return corners, sorted(foreign, key=lambda m: m.marker_id)


def _assert_marker_shape(marker: object) -> None:
    """Refuser un marqueur mal forme avec le refus nomme du module.

    `compute_template_homography` et `_partition_markers` sont publiques et la
    story en fait le point d'entree geometrique des stories suivantes. Sans
    cette garde, un dictionnaire sans `id` ou dont `center` n'a pas deux
    coordonnees leve un `KeyError` ou un `ValueError` numpy -- hors du tuple de
    rattrapage par page, donc emportant tout le lot.
    """
    if not isinstance(marker, dict) or "id" not in marker or "center" not in marker:
        raise _refus(
            REFUS_MARQUEUR_MAL_FORME,
            f"Marqueur mal forme: {marker!r}. Les cles 'id' et 'center' sont attendues.",
            classe=PageGeometryRefused,
        )
    if not is_strict_int(marker["id"]):
        raise _refus(
            REFUS_MARQUEUR_ID_INVALIDE,
            f"Identifiant de marqueur invalide: {marker['id']!r}. Un entier est attendu.",
            classe=PageGeometryRefused,
        )
    center = marker["center"]
    if (
        not isinstance(center, (tuple, list))
        or len(center) != 2
        or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in center)
    ):
        raise _refus(
            REFUS_MARQUEUR_CENTRE_INVALIDE,
            f"Centre de marqueur invalide pour l'ID {marker['id']}: {center!r}. "
            "Deux coordonnees finies sont attendues.",
            classe=PageGeometryRefused,
        )


def compute_template_homography(
    markers: list[dict], geometry: dict, dpi: int
) -> tuple[np.ndarray, PageScaleMeasurement]:
    """Homographie de la page **de ce template**, et l'echelle observee.

    La destination vient de `corner_marker_centers_mm` du `TemplateSpec`, pas de
    `layout`: c'est ce qui rend le paysage correct.
    """
    corners, _foreign = _partition_markers(markers)
    duplicated = sorted(
        {
            marker["id"]
            for marker in markers
            if marker["id"] in layout.CORNER_MARKER_IDS
            and sum(1 for other in markers if other["id"] == marker["id"]) > 1
        }
    )
    if duplicated:
        raise _refus(
            REFUS_COINS_EN_DOUBLE,
            f"Marqueurs ArUco de coin en double: {duplicated}. L'assignation des "
            "coins est ambigue (deuxieme planche sur la vitre ?).",
            classe=PageGeometryRefused,
        )

    missing = [mid for mid in layout.CORNER_MARKER_IDS if mid not in corners]
    if len(layout.CORNER_MARKER_IDS) - len(missing) < layout.MIN_CORNER_MARKERS_REQUIRED:
        raise _refus(
            REFUS_COINS_MANQUANTS,
            f"Marqueurs ArUco de coin manquants: {missing}. IDs attendus: "
            f"{list(layout.CORNER_MARKER_IDS)}.",
            classe=PageGeometryRefused,
        )

    source = np.array(
        [corners[mid]["center"] for mid in layout.CORNER_MARKER_IDS], dtype=np.float32
    )
    _assert_convex_quadrilateral(source)

    centers_mm = geometry["corner_centers_mm"]
    destination = np.array(
        [page_templates.mm_to_px(*centers_mm[mid], dpi) for mid in layout.CORNER_MARKER_IDS],
        dtype=np.float32,
    )
    # Une page en miroir donne une homographie de determinant negatif, un residu
    # nul et une echelle de 1,0: rien ne la distingue d'une page saine, et 5.3 la
    # decouperait retournee. `cv2.aruco` ne reconnait pas un symbole miroir, donc
    # le cas ne vient pas du chemin reel -- il viendrait d'une correction
    # d'orientation appliquee en amont. Le refus coute une ligne.
    if _signed_area(source) * _signed_area(destination) < 0:
        raise _refus(
            REFUS_PAGE_EN_MIROIR,
            "Les marqueurs de coin sont en disposition miroir: la page a ete "
            "retournee. La redresser produirait des frames inversees sans erreur.",
            classe=PageGeometryRefused,
        )

    homography, _mask = cv2.findHomography(source, destination)
    if homography is None:
        raise _refus(
            REFUS_HOMOGRAPHIE_INCALCULABLE,
            "Impossible de calculer l'homographie de page a partir des marqueurs detectes.",
            classe=PageGeometryRefused,
        )
    return homography, _measure_scale(source, destination)


def _assert_convex_quadrilateral(points: np.ndarray) -> None:
    """Refuser une disposition de coins qui rend l'homographie sans signification.

    `cv2.findHomography` rend une matrice de rang deficient -- sans jamais rendre
    `None` -- quand trois des quatre points sont quasi colineaires: page pliee,
    prise de vue tres rasante. Meme critere que le chemin POC, applique ici sur
    la geometrie du template.
    """
    array = np.asarray(points, dtype=np.float64)
    sines = []
    for index in range(4):
        previous = array[index - 1] - array[index - 2]
        following = array[index] - array[index - 1]
        norm = np.linalg.norm(previous) * np.linalg.norm(following)
        if norm == 0:
            raise _refus(
                REFUS_COINS_DEGENERES,
                "Deux marqueurs de coin confondus: la geometrie de page est degeneree.",
                classe=PageGeometryRefused,
            )
        # Produit vectoriel scalaire ecrit explicitement: `np.cross` sur des
        # vecteurs 2D est deprecie depuis numpy 2.0, et la formule tient sur
        # une ligne.
        cross = previous[0] * following[1] - previous[1] * following[0]
        sines.append(float(cross) / norm)
    same_way = all(s > 0 for s in sines) or all(s < 0 for s in sines)
    if not same_way or min(abs(s) for s in sines) < layout.MIN_CORNER_QUAD_SIN:
        raise _refus(
            REFUS_QUADRILATERE_NON_CONVEXE,
            "Les marqueurs de coin ne forment pas un quadrilatere convexe utilisable "
            "(page pliee, prise de vue rasante, ou marqueur parasite).",
            classe=PageGeometryRefused,
        )


#: Les quatre coins, dans l'ordre de `layout.CORNER_MARKER_IDS`, forment le
#: quadrilatere 0 -> 1 -> 2 -> 3. Les paires ci-dessous sont ses deux cotes
#: « largeur » et ses deux cotes « hauteur »: c'est sur elles que l'echelle se
#: mesure, parce qu'une longueur de cote ne change pas quand la page pivote.
_WIDTH_EDGES: tuple[tuple[int, int], ...] = ((0, 1), (3, 2))
_HEIGHT_EDGES: tuple[tuple[int, int], ...] = ((0, 3), (1, 2))


def _mean_edge_length(points: np.ndarray, edges: tuple[tuple[int, int], ...]) -> float:
    lengths = [float(np.linalg.norm(points[b] - points[a])) for a, b in edges]
    return sum(lengths) / len(lengths)


def _measure_scale(source: np.ndarray, destination: np.ndarray) -> PageScaleMeasurement:
    """Mesurer l'echelle observee par axe, et l'ecart a la similitude la plus proche.

    L'echelle se lit sur les **distances entre centres de coin** -- la longueur
    moyenne des deux cotes « largeur » rapportee a la meme longueur attendue,
    idem en hauteur. Un scanner en auto-fit deforme typiquement un seul axe,
    d'ou la mesure separee; et une page posee de travers ne change aucune de ces
    longueurs, d'ou l'invariance par rotation que la premiere version n'avait pas.
    """
    expected_x = _mean_edge_length(destination, _WIDTH_EDGES)
    expected_y = _mean_edge_length(destination, _HEIGHT_EDGES)
    observed_x = _mean_edge_length(source, _WIDTH_EDGES)
    observed_y = _mean_edge_length(source, _HEIGHT_EDGES)
    if not (expected_x > 0 and expected_y > 0 and observed_x > 0 and observed_y > 0):
        raise _refus(
            REFUS_COINS_DEGENERES,
            "Distance entre centres de coin nulle: la geometrie de page est degeneree.",
            classe=PageGeometryRefused,
        )
    return PageScaleMeasurement(
        observed_x / expected_x,
        observed_y / expected_y,
        _similarity_residual_px(source, destination),
    )


def _similarity_residual_px(source: np.ndarray, destination: np.ndarray) -> float:
    """Ecart des coins detectes a la meilleure similitude des coins attendus.

    Ajustement de Umeyama, ecrit a la main plutot que via
    `cv2.estimateAffinePartial2D`: celui-ci echantillonne (RANSAC par defaut) et
    le document doit etre reproductible octet pour octet d'une detection a
    l'autre. La similitude est contrainte a **preserver l'orientation**, faute de
    quoi une page en miroir s'ajusterait parfaitement et rendrait un residu nul.
    """
    src = np.asarray(source, dtype=np.float64)
    dst = np.asarray(destination, dtype=np.float64)
    count = len(src)
    centred_src = src - src.mean(axis=0)
    centred_dst = dst - dst.mean(axis=0)
    variance = float((centred_src**2).sum()) / count
    if variance <= 0:
        raise _refus(
            REFUS_COINS_DEGENERES,
            "Coins detectes confondus: aucune similitude n'est ajustable.",
            classe=PageGeometryRefused,
        )
    covariance = centred_dst.T @ centred_src / count
    unitary, singular, transposed = np.linalg.svd(covariance)
    correction = np.eye(2)
    if np.linalg.det(unitary) * np.linalg.det(transposed) < 0:
        correction[1, 1] = -1.0
    rotation = unitary @ correction @ transposed
    scale = float((singular * np.diag(correction)).sum()) / variance
    fitted = centred_src @ rotation.T * scale + dst.mean(axis=0)
    return float(np.sqrt(((fitted - dst) ** 2).sum(axis=1)).max())


def _signed_area(points: np.ndarray) -> float:
    array = np.asarray(points, dtype=np.float64)
    rolled = np.roll(array, -1, axis=0)
    return float((array[:, 0] * rolled[:, 1] - rolled[:, 0] * array[:, 1]).sum()) / 2.0


def _scale_warnings(scale: PageScaleMeasurement) -> list[str]:
    warnings: list[str] = []
    if scale.scale_error > SCALE_WARNING_TOLERANCE:
        warnings.append("PAGE_SCALE_OUT_OF_TOLERANCE")
    if scale.aspect_error > SCALE_WARNING_TOLERANCE:
        warnings.append("PAGE_ASPECT_OUT_OF_TOLERANCE")
    return warnings


# --- identite de page: QR, puis manifest, puis refus -----------------------


def resolve_page_identity(
    image: np.ndarray, *, manifest_template_id: str | None = None
) -> tuple[dict | None, str, str | None, list[str]]:
    """Decoder le QR d'une page et en tirer son identite.

    Rend ``(payload, qr_status, template_source, warnings)``. Les quatre statuts
    fermes du decodage sont traites et **jamais confondus**: `DECODE_MULTIPLE`
    -- deux QR dans le champ, donc deux planches sur la vitre -- est un refus de
    page, pas un choix arbitraire du premier symbole. C'est la meme faute que la
    garde de marqueurs de coin en double sanctionne.

    Fallback borne: si le QR est illisible **et** qu'un manifest local declare le
    lot, le `template_id` peut en etre repris, la page portant alors
    `TEMPLATE_FROM_MANIFEST_NOT_QR`. Sans manifest, la page est refusee -- jamais
    de `template_id` par defaut, jamais de detection « au juge » du nombre de
    zones depuis l'image.

    Le statut reel du decodage est **toujours** rendu, y compris quand la page
    est ensuite refusee pour une autre cause: c'est le champ que 5.7 et 5.8
    consomment pour trier les refus, et un statut emprunte a une autre etape y
    envoie l'operateur inspecter un QR qui va bien.

    `DECODE_NO_SYMBOL` porte son propre avertissement (`PAGE_WITHOUT_QR_SYMBOL`)
    et n'est pas confondu avec `DECODE_UNREADABLE`: « symbole abime » dit que la
    feuille est bien une planche du dispositif, « aucun symbole » ne le dit pas.
    Le repli couvre les deux -- un QR arrache est un cas terrain -- mais le
    document ne les melange jamais.
    """
    # `_resilient`: le detecteur par defaut n'est pas garanti a 100% (son propre
    # commentaire de choix le dit -- 208/270 a 35 mm sur le banc), et un scan reel
    # l'a mesure en echec la ou l'autre moteur decodait sans detour. Le second essai
    # ne coute rien sur le chemin heureux et ne peut jamais rendre pire.
    result = qr_codes.decode_qr_image_resilient(image)
    if result.status == qr_codes.DECODE_OK:
        # --- Story 5.17: le seul endroit de la production ou une planche perimee
        # est reconnue pour ce qu'elle est.
        #
        # Le symbole se decode -- l'encre et l'optique vont bien -- et c'est
        # `parse_payload` qui tranche sur la version. Depuis le passage du schema a
        # `2.0` (`EPIC5-ARB-60`, aucun lecteur bi-format), les planches deja imprimees
        # du depot (le lot de reference `TEST_FILE_12p5`, les planches de saturation,
        # les cibles de mesure) portent du `1.0` et sont donc **refusees ici**, avec un
        # motif qui nomme les deux versions et dit qu'il faut reimprimer. Le refus
        # remonte en `refusal_reason` de la page (voir `_detect_one_page`): l'operateur
        # lit une phrase, pas une trace d'exception. C'est assume, c'est une decision,
        # et c'est ce commentaire qui empeche de la relire comme une panne.
        try:
            payload = payload_io.parse_payload(result.text)
        except payload_io.PayloadValidationError as error:
            # **Le refus transporte le statut observe** (bloquant B1 de la revue de
            # 5.17). Sans ces deux lignes le refus sortait de cette fonction avant que
            # `_detect_one_page` n'ait pose `observed["qr_status"]`, si bien qu'une
            # planche perimee -- dont le QR a decode, et bien decode -- se publiait
            # `not_attempted`: le contraire de la definition de ce statut, et le
            # symetrique exact du defaut ferme par 5.2. L'identite encore lisible du
            # document, elle, voyage deja avec l'exception depuis `parse_payload`.
            error.qr_status = result.status
            raise
        return payload, result.status, "qr", []
    if result.status == qr_codes.DECODE_MULTIPLE:
        raise _refus(
            REFUS_PLUSIEURS_QR,
            "Plusieurs QR dans le champ de la page: deux planches sur la vitre. "
            "Choisir le premier symbole fabriquerait un lot qui n'a jamais existe.",
            classe=PageDetectionRefused,
            qr_status=result.status,
        )
    if manifest_template_id is None:
        raise _refus(
            REFUS_QR_SANS_MANIFEST,
            f"QR inexploitable ({result.status}) et aucun manifest local ne declare "
            "ce lot: le template de la page est indeterminable. Un template par "
            "defaut produirait une geometrie fausse d'apparence valide.",
            classe=PageDetectionRefused,
            qr_status=result.status,
        )
    warnings = ["TEMPLATE_FROM_MANIFEST_NOT_QR"]
    if result.status == qr_codes.DECODE_NO_SYMBOL:
        warnings.append("PAGE_WITHOUT_QR_SYMBOL")
    return None, result.status, "manifest", warnings


def manifest_template_id(project_dir: str | Path, lot_id: str | None) -> str | None:
    """Lire `reconstruction.template_id` d'un manifest local, s'il declare ce lot.

    Le champ est de **niveau projet**, pas de niveau lot: le lot vise doit donc
    d'abord figurer dans `lots[]` par son `lot_id`, faute de quoi rien ne
    garantit que ce `template_id` soit le sien.

    Un `lot_id` est **toujours** exigible, y compris quand le QR est illisible:
    l'ingestion (5.1) en fournit un, son `ingest_slug`. La premiere version
    retombait, dans ce cas, sur une heuristique de cardinalite (« un manifest a
    un seul lot fait foi ») qui n'est pas la regle de l'AC 5 et qui acceptait
    sans un mot le template d'un lot etranger: une page portrait a deux zones
    ressortait `status=ok` avec quatre zones paysage. Le slug d'ingestion est
    l'identite dont on dispose sans le QR -- c'est deja celle que la
    reconciliation confronte au `lot_id` decode -- et il rend la regle de l'AC 5
    applicable dans le seul cas ou le repli sert.

    La fonction promet de rendre `None` quand le manifest ne peut pas servir:
    cette promesse vaut aussi pour sa **forme**. `load_manifest` est un
    `json.load` nu, sans validation de schema; un `lots` qui serait une liste de
    chaines levait un `AttributeError` non rattrape, qui emportait tout le lot.
    """
    from .io.manifest import load_manifest

    manifest_path = Path(project_dir) / "project.json"
    if not manifest_path.is_file() or lot_id is None:
        return None
    try:
        manifest = load_manifest(manifest_path)
    except Exception:
        return None
    if not isinstance(manifest, dict):
        return None
    reconstruction = manifest.get("reconstruction")
    if not isinstance(reconstruction, dict):
        return None
    template_id = reconstruction.get("template_id")
    # Le champ est contractuellement une chaine cote payload; un dict ou une
    # liste rendus tels quels levent `TypeError: unhashable type` dans le
    # registre, la ou une chaine inconnue leve le refus nomme.
    if not isinstance(template_id, str) or not template_id:
        return None
    lots = manifest.get("lots")
    if not isinstance(lots, list):
        return None
    if not any(isinstance(lot, dict) and lot.get("lot_id") == lot_id for lot in lots):
        return None
    return template_id


# --- orchestration multipage et reconciliation ------------------------------


def _reconcile_lot(
    pages: list[DetectedPage], *, ingest_slug: str, ingested_count: int
) -> list[str]:
    """Confronter ce que le lot declare a ce qui a ete ingere.

    C'est la **seule** detection de lot incomplet de toute la chaine scan
    (risque R12): une page manquante, une page en double ou deux lots melanges
    sur la meme vitre ne se voient nulle part ailleurs. Une divergence de slug,
    elle, n'est qu'un avertissement -- un dossier mal nomme est un cas terrain
    banal, pas une raison de refuser un lot.
    """
    # Une page **refusee mais identifiee** compte: la feuille est bien la, son
    # QR a decode, elle est seulement inexploitable. L'exclure faisait signaler
    # `PAGE_INDEX_MISSING` -- « il manque une page » -- pour une page presente.
    identified = [page for page in pages if page.lot_id]
    if not identified:
        return []

    identities = {(p.project_id, p.rush_id, p.lot_id) for p in identified}
    if len(identities) > 1:
        # Les identites par rang de lecture, en attribut structure: c'est
        # exactement ce dont l'operateur a besoin pour trier les feuilles, et
        # une chaine de message ne se lit pas par une GUI. Le code de refus
        # (5.27) est du meme raisonnement, generalise a tous les sites du
        # module: il voyage sur l'exception, a cote de cet attribut. Ce refus-ci
        # emporte le lot entier, donc il n'atteint aucun document -- c'est
        # pourquoi son code n'a pas d'autre porteur que l'exception.
        raise _refus(
            REFUS_PLUSIEURS_LOTS,
            "Plusieurs lots sur le meme jeu de pages: "
            f"{sorted(str(identity) for identity in identities)}. Choisir l'une "
            "de ces identites fabriquerait un lot qui n'a jamais existe.",
            classe=LotIdentityError,
            identities_by_read_rank=tuple(
                (page.read_rank, page.project_id, page.rush_id, page.lot_id)
                for page in sorted(identified, key=lambda p: p.read_rank)
            ),
        )

    warnings: list[str] = []
    lot_id = identified[0].lot_id
    if lot_id != ingest_slug:
        warnings.append("INGEST_SLUG_DIFFERS_FROM_LOT_ID")

    declared_counts = {p.page_count for p in identified if p.page_count is not None}
    if len(declared_counts) > 1:
        # Deux pages du meme lot qui n'annoncent pas le meme nombre de pages,
        # c'est deux tirages melanges -- exactement le risque R12. La premiere
        # version faisait retomber la reference a `None`, ce qui **sautait les
        # trois controles d'un coup**: un lot annoncant 2 et 7 pages, avec un
        # index a 5, sortait sans un avertissement. On signale la contradiction
        # et on poursuit sur la borne la plus large, pour qu'un index aberrant
        # reste visible.
        warnings.append("PAGE_COUNT_INCONSISTENT_ACROSS_PAGES")
    declared = max(declared_counts) if declared_counts else None
    if declared is not None and declared != ingested_count:
        warnings.append("PAGE_COUNT_DIFFERS_FROM_INGESTED")

    indexes = [p.page_index for p in identified if p.page_index is not None]
    if declared is not None:
        if any(index < 0 or index >= declared for index in indexes):
            warnings.append("PAGE_INDEX_OUT_OF_RANGE")
        if set(range(declared)) - set(indexes):
            warnings.append("PAGE_INDEX_MISSING")
    if len(indexes) != len(set(indexes)):
        warnings.append("PAGE_INDEX_DUPLICATED")
    return warnings


def detect_pages(
    project_dir: str | Path,
    ingest_report: scan_ingest.ScanIngestReport,
    *,
    dpi: int | None = None,
    rappel_progression=None,
) -> tuple[int, tuple[DetectedPage, ...]]:
    """La moitie **amont** de :func:`detect_lot_pages`: une page apres l'autre.

    Extraite par la story 5.24 (`EPIC7-ARB-63`), et pour une raison qui est
    l'ossature de cette story: le refus multi-lots ne vit pas dans la CLI mais
    **ici**, dans :func:`_reconcile_lot`, qui leve `LotIdentityError` des que
    deux identites de lot coexistent. Le tri par QR doit donc s'inserer
    **avant** elle -- jamais en rattrapage de son echec, ce qui reviendrait a
    reconstituer une partition depuis un message d'erreur.

    Rend `(dpi de detection, pages)`. Aucune reconciliation, donc **aucun refus
    de lot melange**: c'est a l'appelant de decider si la pile est un lot promis
    (il appelle alors :func:`detect_lot_pages`, inchangee) ou un vrac a trier.

    Les pixels viennent du **point d'entree publie par l'ingestion**
    (`load_page_array`), jamais d'un `cv2.imread` local: c'est le quatrieme
    point du contrat de jonction de 5.1, sans lequel le defaut de lecture du
    chemin POC se reintroduirait ici, avec un ordre de canaux et une profondeur
    decides une seconde fois.

    Une page en echec **n'interrompt pas** les autres: son motif est porte au
    rapport et le lot continue.

    `rappel_progression` est **optionnel** (`AR3`, story 5.28, rebranche ici
    par la story 11.4b lot S5, AC 9.2) : sans lui, **rien ne change** -- memes
    pages, meme dpi rendu, memes refus. Avec lui, il recoit un jalon
    `(faites, total)` **par page reellement detectee**, ou `total` vaut le
    nombre de pages ingerees -- un cardinal de sequence, exact par
    construction. Le canal est celui du depot (`progression.EmetteurProgression`)
    et **aucun second mecanisme** n'est redige ici : le rappel n'est jamais
    appele directement, il n'est jamais teste ni enveloppe, il est **passe** a
    l'emetteur, qui possede a lui seul la monotonie, l'absence de doublon et
    l'absorption des defaillances (`EPIC7-ARB-79`).

    Les jalons sont emis **dans** la boucle et jamais avant : le refus de dpi
    ci-dessous precede l'ouverture du canal, et un refus ne doit produire
    aucune progression.
    """
    project_dir = Path(project_dir)
    scan_dpi = ingest_report.declared_dpi if dpi is None else dpi
    # Le refus dur **precede** l'ouverture du canal, comme dans
    # `write_lot_output_frames` : un lot refuse ne produit aucun jalon, sans
    # quoi l'ecran afficherait une tache qui a commence alors que rien n'a ete
    # detecte.
    _validate_scan_dpi(scan_dpi)
    emetteur = progression.EmetteurProgression(
        rappel_progression, len(ingest_report.pages))
    pages: list[DetectedPage] = []
    for ingested in ingest_report.pages:
        pages.append(_detect_one_page(
            project_dir, ingested, scan_dpi,
            ingest_slug=ingest_report.ingest_slug,
        ))
        # Un jalon **apres** la detection, jamais avant : le numerateur est
        # litteralement le nombre de pages dont le verdict est deja tombe.
        emetteur.emettre(len(pages))
    return scan_dpi, tuple(pages)


def build_lot_report(
    pages: Iterable[DetectedPage],
    *,
    ingest_slug: str,
    scan_dpi: int,
    ingest_declared_dpi: int,
    ingested_count: int,
) -> LotDetectionReport:
    """La moitie **aval**: reconcilier **une** pile homogene par lot et l'assembler.

    Extraite avec :func:`detect_pages` par la story 5.24. Le corps est celui de
    :func:`detect_lot_pages`, **deplace et non reecrit**: une seconde redaction
    de la reconciliation ecrirait un jour deux verdicts differents de la meme
    pile, et c'est precisement la seule detection du risque R12 de toute la
    chaine scan.

    `ingested_count` est le nombre de pages ingerees **pour ce lot**. Sur le
    chemin d'un lot promis c'est le cardinal de la passe entiere ; sur un vrac
    trie, c'est le cardinal des pages que le tri a attribuees a ce lot -- une
    page qu'aucun lot ne reclame ne peut pas etre comptee dans le cardinal
    attendu de tous.
    """
    pages = tuple(pages)
    lot_warnings = _reconcile_lot(
        list(pages), ingest_slug=ingest_slug, ingested_count=ingested_count,
    )
    if scan_dpi != ingest_declared_dpi:
        # Le symptome existe deja (`PAGE_SCALE_OUT_OF_TOLERANCE`) mais il porte
        # le nom d'une **autre** cause: l'operateur lit « la page a ete mise a
        # l'echelle » alors que c'est le parametre passe a la detection qui
        # differe du scan. Sur un lot mixte le diagnostic est pire encore: la
        # redefinition est juste pour les pages de PDF, rasterisees a ce DPI, et
        # fausse pour les pages-fichiers, dont les pixels sont ceux du fichier.
        lot_warnings.append("SCAN_DPI_DIFFERS_FROM_INGESTED")
    return LotDetectionReport(
        ingest_slug=ingest_slug,
        scan_dpi=scan_dpi,
        ingest_declared_dpi=ingest_declared_dpi,
        pages=pages,
        warnings=tuple(validate_warning_code(code) for code in lot_warnings),
    )


def detect_lot_pages(
    project_dir: str | Path,
    ingest_report: scan_ingest.ScanIngestReport,
    *,
    dpi: int | None = None,
    rappel_progression=None,
) -> LotDetectionReport:
    """Detecter toutes les pages d'un lot ingere. **Contrat inchange.**

    La composition des deux moities ci-dessus, et rien d'autre: c'est le chemin
    d'un lot **promis** -- une pile, un lot --, qui refuse toujours deux
    identites de lot melangees (`LotIdentityError`). La story 5.24 n'y touche
    ``rappel_progression`` est **passe** a :func:`detect_pages` et rien de plus
    (story 11.4e, AC 9.1) : ce relais n'appelle pas le rappel, ne le teste pas
    et ne l'enveloppe pas. Un second mecanisme ici diviserait en deux la
    propriete que `progression.EmetteurProgression` possede seul -- monotonie,
    absence de doublon, absorption des defaillances (`EPIC7-ARB-79`).

    pas: le regime de vrac passe par :func:`detect_pages`, jamais par une
    variante de cette fonction-ci.
    """
    scan_dpi, pages = detect_pages(project_dir, ingest_report, dpi=dpi,
                                   rappel_progression=rappel_progression)
    return build_lot_report(
        pages,
        ingest_slug=ingest_report.ingest_slug,
        scan_dpi=scan_dpi,
        ingest_declared_dpi=ingest_report.declared_dpi,
        ingested_count=len(ingest_report.pages),
    )


def _detect_one_page(
    project_dir: Path,
    ingested: scan_ingest.IngestedPage,
    dpi: int,
    *,
    ingest_slug: str,
) -> DetectedPage:
    """Detecter une page, ou la refuser en nommant le motif.

    Le statut de decodage et l'identite deja lue sont conserves jusqu'au refus:
    une page dont le QR a parfaitement decode mais dont un coin manque doit
    sortir avec son `qr_status` reel et son `lot_id`, sans quoi la
    reconciliation la compte comme absente et signale un
    `PAGE_INDEX_MISSING` mensonger.

    Cela vaut aussi -- et c'est le bloquant B1 de la revue de 5.17 -- quand le refus
    vient du **payload lui-meme**: une planche perimee (`1.0`) est refusee par
    `parse_payload`, donc avant que `observed` n'ait ete pose. Son statut et son
    identite arrivent alors **portes par l'exception** (`qr_status` et
    `readable_identity`), et c'est la seule voie possible: le payload n'etant pas
    relisible, il n'y a rien a poser dans `observed`.
    """
    base = {
        "read_rank": ingested.read_rank,
        "locator_source": ingested.locator.source_path,
        "locator_page_index": ingested.locator.page_index,
    }
    observed: dict = {"qr_status": QR_NOT_ATTEMPTED, "payload": None}
    try:
        image = scan_ingest.load_page_array(project_dir, ingested.locator, dpi=dpi)
        # Le repli est resolu **pour le lot que l'on croit scanner**: sans QR,
        # le slug d'ingestion est la seule identite disponible, et c'est elle
        # que la reconciliation confronte deja au `lot_id` decode.
        fallback = manifest_template_id(project_dir, ingest_slug)
        payload, qr_status, template_source, warnings = resolve_page_identity(
            image, manifest_template_id=fallback
        )
        observed["qr_status"] = qr_status
        observed["payload"] = payload
        template_id = fallback if payload is None else payload["template_id"]

        geometry = resolve_page_geometry(template_id, dpi)
        # Une seule detection de marqueurs par page: elle coute un balayage de
        # l'image entiere, et la refaire pour la partition puis pour
        # l'homographie doublerait le temps d'un lot sans rien apporter.
        markers = _detect_markers_document(image, dpi)["images"][0]["markers"]
        corners, foreign = _partition_markers(markers)
        if foreign:
            warnings.append("FOREIGN_MARKER_DETECTED")
        homography, scale = compute_template_homography(markers, geometry, dpi)
        warnings.extend(_scale_warnings(scale))

        return DetectedPage(
            status=PAGE_OK,
            qr_status=qr_status,
            template_id=template_id,
            template_source=template_source,
            # `project_id` a rejoint les champs absents le 2026-08-18 (precision
            # d'Egan): une page de calibration appartient a une **chaine de scan**, pas
            # a un projet -- celle du projet A doit se lire sans refus dans le projet
            # B. `.get()` pour la meme raison que les trois suivants.
            project_id=None if payload is None else payload.get("project_id"),
            # `rush_id`, `lot_id` et `fps_target` sont **absents par contrat** du
            # payload d'une page de calibration (story 5.23, AC 8bis): cette
            # feuille sert toute une chaine de scan, pas un lot. Un acces nu
            # levait ici une `KeyError` que rien ne nommait -- la page etait
            # illisible sans qu'aucun message ne dise pourquoi.
            #
            # `.get()` et non un branchement sur le role: la clause repond a la
            # question posee -- « ce payload porte-t-il ce champ ? » -- alors que
            # lire le role redemanderait a `payload_io` ce qu'il a deja tranche en
            # validant. Et la validation garantit deja qu'un payload de planche
            # d'images les porte tous les trois, donc ce `.get()` ne peut pas
            # masquer un payload tronque: il aurait ete refuse en amont.
            rush_id=None if payload is None else payload.get("rush_id"),
            lot_id=None if payload is None else payload.get("lot_id"),
            page_index=None if payload is None else payload["page_index"],
            page_count=None if payload is None else payload["page_count"],
            gamut_map_id=None if payload is None else payload["gamut_map_id"],
            corner_centers=tuple(
                (mid, float(corners[mid]["center"][0]), float(corners[mid]["center"][1]))
                for mid in sorted(corners)
            ),
            foreign_markers=tuple(foreign),
            homography=tuple(float(v) for v in np.asarray(homography).ravel()),
            page_size_px=geometry["page_size_px"],
            scale=scale,
            frame_zones_mm=geometry["frame_zones_mm"],
            frame_zones_px=geometry["frame_zones_px"],
            warnings=tuple(validate_warning_code(code) for code in warnings),
            payload=payload,
            **base,
        )
    except (ScanDetectionError, page_templates.UnknownTemplateError,
            payload_io.PayloadValidationError, scan_ingest.ScanIngestError) as error:
        refused_payload = observed["payload"]
        qr_status = getattr(error, "qr_status", None) or observed["qr_status"]
        # Le code de refus emprunte **exactement le meme chemin** que le statut
        # de decodage juste au-dessus: porte par l'exception quand elle vient de
        # ce module, traduit ici quand elle vient d'ailleurs. Les trois familles
        # etrangeres rattrapees par ce `except` ne connaissent pas le vocabulaire
        # du module et n'ont pas a le connaitre -- les amender a la source
        # eparpillerait l'enumeration dans quatre modules.
        refusal_code = getattr(error, "refusal_code", None)
        if refusal_code is None:
            refusal_code = _code_de_refus_etranger(error)
        # Trois provenances possibles de l'identite d'une page refusee, dans cet
        # ordre: le payload deja relu (refus survenu apres le decodage), puis
        # l'identite que le refus du payload transporte (planche perimee ou champ
        # abime), puis rien. Le second cas est celui du bloquant B1: une feuille
        # presente et nommee ne doit pas sortir anonyme de la detection, sans quoi
        # `_reconcile_lot` -- seule detection du risque R12 -- ne la voit pas.
        if refused_payload is not None:
            # **`.get` et non un acces nu** (constate le 2026-08-18 en elargissant
            # `CALIBRATION_ABSENT_FIELDS`): `IDENTITY_FIELDS` porte `rush_id` et
            # `lot_id`, que le payload d'une page de calibration n'a pas depuis
            # l'AC 8bis. Un acces nu levait donc une `KeyError` **hors du bloc de
            # capture** des qu'une page de calibration etait refusee apres decodage --
            # une feuille inexploitable faisait tomber la detection entiere au lieu de
            # sortir nommee. Le defaut etait deja livre; il est ferme ici parce que
            # c'est le chemin de lecture de cette feuille.
            identity = {field: refused_payload.get(field)
                        for field in payload_io.IDENTITY_FIELDS}
        else:
            identity = dict(getattr(error, "readable_identity", None) or {})
        return DetectedPage(
            status=PAGE_REFUSED,
            qr_status=qr_status,
            project_id=identity.get("project_id"),
            rush_id=identity.get("rush_id"),
            lot_id=identity.get("lot_id"),
            page_index=identity.get("page_index"),
            page_count=identity.get("page_count"),
            refusal_reason=str(error),
            refusal_code=refusal_code,
            payload=refused_payload,
            **base,
        )


def _detect_markers_document(image: np.ndarray, dpi: int) -> dict:
    """Detecter les marqueurs d'une page, dans la forme du document POC.

    La detection elle-meme est celle de `detection/aruco`, importee: c'est la
    geometrie de page qui change dans cette story, pas la facon de trouver un
    marqueur.

    Le `dpi` transmis est **celui de la detection** (`scan_dpi`), pas celui
    declare par l'ingestion quand les deux divergent: le seuillage doit etre
    dimensionne sur les pixels reellement lus, qui sont ceux de la
    rasterisation a ce DPI. C'est la meme valeur que celle passee a
    `resolve_page_geometry` et a `compute_template_homography`, pour la meme
    raison.
    """
    corners, ids = aruco_detection.detect_markers(image, dpi=dpi)
    return aruco_detection.build_markers_document("page", corners, ids)


def report_document(report: LotDetectionReport) -> dict:
    """Document canonique, empreinte comprise.

    L'empreinte est calculee **sans les coefficients d'homographie** (question
    ouverte 3 de la story): ce sont les seuls flottants du document dont la
    valeur depend de l'implementation de `cv2.findHomography`, donc de la
    version d'OpenCV installee. Les y laisser rendrait l'empreinte
    non-reproductible d'une machine a l'autre, ce qui lui oterait sa seule
    fonction. Les coefficients restent **publies**, ils ne sont simplement pas
    signes.
    """
    document = report.as_document()
    signed = dict(document)
    signed["pages"] = [
        {key: value for key, value in page.items() if key != "homography"}
        for page in document["pages"]
    ]
    document["fingerprint"] = fingerprint_of(signed)
    return document


def report_json(report: LotDetectionReport) -> str:
    """Serialisation canonique: deux detections rendent le meme texte.

    Helpers de canonicalisation importes de `extraction_previz`, jamais
    recopies -- deux recettes qui divergent est le defaut corrige en revue 3.5.
    """
    return canonical_json(report_document(report))


__all__ = [
    "DOCUMENT_FLOAT_PRECISION",
    "FINGERPRINT_PREFIX",
    "PAGE_OK",
    "PAGE_QR_STATUSES",
    "PAGE_REFUSED",
    "PAGE_STATUSES",
    "QR_NOT_ATTEMPTED",
    "SCALE_WARNING_TOLERANCE",
    "SCAN_DETECTION_WARNING_CODES",
    "SCAN_REFUSAL_CODES",
    "DetectedPage",
    "ForeignMarker",
    "LotDetectionReport",
    "LotIdentityError",
    "build_lot_report",
    "detect_pages",
    "PageDetectionRefused",
    "PageGeometryRefused",
    "PageScaleMeasurement",
    "ScanDetectionError",
    "compute_template_homography",
    "detect_lot_pages",
    "report_document",
    "report_json",
    "manifest_template_id",
    "resolve_page_geometry",
    "resolve_page_identity",
    "validate_refusal_code",
    "validate_warning_code",
]
