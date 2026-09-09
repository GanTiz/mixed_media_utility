"""Contrat de donnees de previz de scan (story 5.8).

Troisieme previz jumelle, apres `extraction_previz` (3.5, `kind = "extraction"`)
et `pdf_previz` (4.9, `kind = "makepdf"`), avec `kind = "scan"`. Le livrable est
le **contrat de donnees**, pas une interface, pas un rendu: une GUI (Epic 7, et
en particulier sa story 7.4 « edition manuelle des detections ») consomme ce
document pour montrer « voici ce que le scan a detecte et ce qu'il produira »
sans redetecter une seule page.

Ce que ce module fait, et ce qu'il ne fait pas
----------------------------------------------
Il **projette**. Chaque valeur vient litteralement du rapport d'ingestion de
5.1, du document de detection de 5.2, du plan de decoupe de 5.3, des resultats
de calibration de 5.4b ou du rapport d'ecriture de 5.6. Aucune arithmetique de
geometrie, aucun calcul d'homographie, aucune resolution de template, aucune
regle de marge, aucune metrique couleur, aucun arrondi. Des entrees
incoherentes ressortent incoherentes et **verbatim** -- c'est teste par des
sentinelles volontairement fausses: si le module recalculait quoi que ce soit,
la sentinelle serait corrigee au lieu d'etre transportee.

Il ne recalcule pas non plus « pour verifier ». Controler ici qu'une zone tient
dans la page ou qu'un residu est acceptable ferait diverger la previz de ce que
la production fera -- le piege central que 3.5 et 3.6 ont evite.

Adressage: ce qui distingue cette previz de ses deux jumelles
-------------------------------------------------------------
La story 7.4 doit pouvoir dire « la zone 2 de la page 3 est mal placee, voici
le rectangle corrige ». Chaque element modifiable porte donc une **adresse
stable et explicite**, rendue dans le document sous la cle `address`:

* une page: :data:`PAGE_ADDRESS_FIELDS` -- `read_rank` **et** `page_index`;
* une zone de frame: :data:`FRAME_ZONE_ADDRESS_FIELDS` -- l'adresse de page
  plus `slot_index`;
* un marqueur, de coin ou etranger: :data:`MARKER_ADDRESS_FIELDS` -- l'adresse
  de page plus `marker_id`.

`read_rank` figure dans les trois parce qu'il est la **seule** cle toujours
presente: `page_index` vient du QR et vaut `None` des qu'il n'a rien livre,
c'est-a-dire exactement dans les cas qu'une interface d'edition doit pouvoir
adresser. Les deux ne se deduisent jamais l'un de l'autre (piege 3): une
interface doit pouvoir montrer « le 3e fichier du dossier declare etre la
page 1 », qui est l'information que 5.2 produit pour diagnostiquer un lot
melange.

Le document **n'autorise rien** pour autant (regle heritee de 3.5 et 3.6): pas
de champ de consentement, pas de declencheur, aucune fonction qui relance une
detection ou ecrit un fichier. Il rend l'edition **exprimable**; l'appliquer
appartient a l'Epic 7.

Aucun pixel
-----------
Ni page scannee, ni frame reconstruite, ni vignette: des **chemins relatifs**,
et l'Epic 7 ouvre le fichier. La question de la vignette se pose ici autrement
que chez 3.5, qui a d'ailleurs le seul mecanisme de la famille: la page scannee
**existe deja** comme fichier image sur le disque, contrairement a une frame de
rush qu'il fallait decoder. Aucun mecanisme de vignette n'est donc introduit,
comme 4.9 l'avait deja tranche; le jour ou il en faudrait un, c'est la forme de
3.5 (`THUMBNAIL_STATES`, `THUMBNAIL_ORIGINS` et leurs invariants croises) qui
serait reprise, jamais une seconde inventee.

Le rush source n'apparait jamais: il n'est pas cense exister sur la machine de
scan. Tous les chemins sont relatifs au dossier projet, en separateur POSIX,
produits par `source_confirmation.normalize_relative_project_path` via
`previz_common`. Ce module n'importe **jamais** `io/`: le detecteur de chemin
absolu existe deja (`io/manifest._iter_absolute_path_violations`) et c'est le
test qui l'importe, jamais le module.

Purete
------
Meme standard que ses deux jumelles, verrouille par le meme motif AST dans
`tests/unit/test_scan_previz.py`: aucun `subprocess`, `cv2`, `PIL`, `numpy`,
`reportlab`, aucune ecriture, aucun `open` / `print` / `input` / `exec` /
`eval` / `__import__` / `compile` (exemption `re.compile` en attribut), aucune
dependance nouvelle dans `requirements.txt`, aucun import d'une bibliotheque
d'interface. Consequence structurante: ce module n'importe **aucun** des cinq
producteurs qu'il projette -- `scan_ingest`, `scan_detection`,
`scan_output_frames` et `color_pipeline` tirent tous `cv2` ou `numpy`. Ils
entrent en typage structurel (`Protocol`), comme 4.9 consomme
`pdf_composition.LotComposition` et 3.5 `frame_selection.FrameSelection`.

Deux consequences, assumees et nommees
--------------------------------------
Cette purete a un prix, paye a deux endroits, et il vaut mieux l'ecrire que le
laisser decouvrir:

1. **`synthetic_reason` est transporte verbatim, sans controle de
   vocabulaire.** Le vocabulaire ferme est `scan_output_frames`.\
   `SYNTHETIC_FRAME_REASONS`, et il vit dans un module qui importe `cv2`. Le
   recopier ici en creerait un second, voisin et divergent -- exactement ce
   qu'ARB-14 a du resorber une fois et ce que le point H5.4 des arbitrages a
   ferme en renommant deux codes de 5.6 avant que cette story ne fige sa
   constante. Le controle appartient donc au producteur, qui le fait deja
   (`validate_synthetic_reason`), et le test de cette story confronte le
   transport au **vrai** tuple, importe cote test.
2. **Le statut de calibration est transporte verbatim, sans controle de
   vocabulaire non plus**, pour la meme raison: `CALIBRATION_STATUS_VALUES`
   vit dans `color_pipeline`, qui importe `cv2` et `numpy`.

Etats
-----
`detected` (detection faite, aucune frame ecrite) / `reconstructed` (frames
ecrites, chemins relatifs renseignes). L'etat est **specifique au kind**,
precedent pose par 4.9 (`rendered`), donc aucune jonction chez 3.5 n'est a
ouvrir pour cela. Premiere jumelle dont l'etat initial n'est pas `planned`, et
c'est voulu: sur le chemin scan, rien n'est *planifie* -- la detection a deja eu
lieu quand ce document existe.

Comme chez les deux jumelles: en `reconstructed`, toute donnee **constatee**
(frames ecrites, cardinal attendu, frames synthetiques) est fournie par
l'appelant, jamais mesuree ici.

Compteurs et completude du lot (EPIC5-ARB-32)
----------------------------------------------
Les trois cardinaux de frames sont des **parametres**, jamais lus dans le
rapport de 5.6 -- alors meme que ce rapport les porte. Ce n'est pas une
distraction: le `complete` et les compteurs de 5.6 sont un verdict de **passe**
(`written_frame_count` compte ce que *cette* passe a ecrit), tandis que le
verdict de **lot** appartient au manifest de 5.7, cumule sur toutes les passes
(EPIC5-ARB-32 clauses 1 et 2, EPIC5-ARB-33 pour l'algebre d'ensembles). Une
seconde passe complementaire ecrit peu et complete pourtant le lot. En laissant
l'appelant choisir les cardinaux qu'il verse ici, la previz peut dire ce que le
manifest dit; en les lisant dans le rapport, elle aurait dit « lot incomplet »
sur le lot que la passe vient de finir.

`LOT_INCOMPLETE` est deduit ici, et c'est la **seule** exception a la purete
d'emission (motif ARB-13, forme complete de 4.9). Sa regle est celle du
manifest, mot pour mot: un lot est complet si et seulement si son cardinal
attendu est determinable, que l'ecrit lui est egal **et** qu'aucune frame de
remplacement n'y figure. La confrontation des seuls cardinaux ne suffit pas
(EPIC5-ARB-32 clause 2 via 5.6): le fichier existe, l'image du film non. Une
previz qui ne regarderait que `ecrit == attendu` dirait « lot complet » la ou
le manifest dit « partiel » -- deux morceaux verts chacun sur ses fixtures et
jamais confrontes.

Tous les autres codes sont **transportes depuis l'appelant**, `SYNTHETIC_FRAME_
WRITTEN` compris: il se transporte depuis le rapport de 5.6, il ne se deduit
jamais de `synthetic_frame_count`. Creer une seconde exception a la purete
d'emission ouvrirait la porte aux suivantes.

Empreintes
----------
* `fingerprints.detection` -- les **entrees de decision de la detection**
  (:data:`DETECTION_FINGERPRINT_FIELDS`), et rien d'autre. Changer une entree
  change l'empreinte; regenerer a l'identique ne la change pas; ajouter ou
  retirer un avertissement ne la change pas.
* `fingerprints.selection` -- optionnelle, **transportee verbatim** depuis
  l'amont avec exigence de forme complete (`sha256-v1:` + 64 hexadecimaux),
  motif de 4.9 et regime optionnel de `source_signature` chez 3.5. Elle n'est
  jamais comparee a une empreinte d'une autre recette: 3.5 declare
  explicitement son empreinte de selection et le `frame_timecodes_digest` de
  3.4 non comparables malgre le prefixe partage.

`gamut_map_id` entre dans les champs d'empreinte **sans condition**. C'est le
trou exact que la story 5.10 avait trouve cote impression -- `COMPOSITION_
FINGERPRINT_FIELDS` ne le portait pas, si bien que changer `--gamut-map`
laissait l'empreinte inchangee et une previz perimee devenait indetectable. La
mecanique est identique ici: `gamut_map_id` decide de ce que la reconstruction
produira, deux lots identiques a `G` pres donnent des frames differentes. Le
champ est **toujours present** depuis EPIC5-ARB-13 (onzieme champ obligatoire
de `io/payload._REQUIRED_SCALAR_FIELDS`, refuse a l'absence par
`validate_payload`), donc son entree dans l'empreinte ne l'expose a aucune
instabilite d'omission, et **aucune branche « absent » n'est ecrite ici**.

En revanche le **verdict d'ecretage** et le drapeau `synthetic` n'entrent
**pas** dans l'empreinte: ce sont des constatations de mesure, au meme regime
que les avertissements. Une frame de remplacement ne change pas les entrees de
decision de la detection, elle en constate l'echec.

Deux champs conditionnels qui se ressemblent et ne suivent pas la meme regle
----------------------------------------------------------------------------
Ils voisinent dans le meme document, ce qui rend la confusion probable:

* **`synthetic`: inconditionnel des qu'une frame existe** (EPIC5-ARB-8). Des
  lors qu'un chemin de frame est present, le drapeau l'est aussi, **`false`
  compris**. Le regime « champ optionnel omis » ne s'y applique pas: un drapeau
  absent se lit « vraie frame », et l'interface montrerait alors une mire
  « FRAME MANQUANTE » comme un plan du film -- ce qui detruit exactement la
  valeur qu'EPIC5-ARB-8 cherchait a creer. `synthetic_reason` accompagne le
  drapeau **si et seulement si** il vaut `true`.
* **Verdict d'ecretage: conditionnel**, et pour une raison qui n'a rien a voir.
  Il ne depend d'aucun champ de payload mais des patchs sentinelles (5.9) et
  d'une calibration ayant reellement tourne (5.4b, post-MVP). Au MVP le statut
  vaut invariablement `not_applied` et **aucune mesure d'ecretage n'existe**:
  present, il passe verbatim; absent, il est **omis**, jamais `null`, et
  surtout jamais remplace par un verdict « pas d'ecretage ». Affirmer l'absence
  d'ecretage sur la foi d'une mesure jamais faite est le seul mensonge que ce
  document puisse commettre sur ce point. Le module ne deduit **jamais** le
  verdict du statut de calibration ni le statut du verdict: 5.4b les tient pour
  independants.

Frontiere Epic 5 / Epic 7
--------------------------
Identique a celle de 3.5, qui fait foi. **Appartient a ce module**: la forme du
document et sa derivation sans duplication depuis les modules de l'Epic 5.
**N'appartiennent jamais ici**: le framework, la mise en page d'ecran, la
navigation, le rendu visuel des pages scannees, le protocole d'appel, la
politique de cache -- et surtout **l'edition elle-meme**. L'AC de l'epic dit
« previz *editable* »: le mot decrit ce que l'interface fera, pas ce que ce
module fait.

Convention d'ecriture: messages en francais **sans accents**, comme le reste de
la famille, pour survivre a une console `cp1252`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

from .previz_common import (
    PREVIZ_SCHEMA_VERSION,
    envelope_head,
    exact_rate as _common_exact_rate,
    fingerprint_of,
    is_complete_fingerprint,
    normalize_generated_at_utc,
    optional_relative_path as _common_optional_relative_path,
    optional_text as _common_optional_text,
    require_int as _common_require_int,
    require_known_codes,
    require_number as _common_require_number,
    require_relative_path as _common_relative_path,
    require_text as _common_require_text,
)

__all__ = [
    "SCAN_PREVIZ_KIND",
    "SCAN_PREVIZ_STATE_DETECTED",
    "SCAN_PREVIZ_STATE_RECONSTRUCTED",
    "SCAN_PREVIZ_STATES",
    "CALIBRATION_FAILED",
    "DPI_BELOW_QR_MINIMUM",
    "FOREIGN_MARKER_DETECTED",
    "GAMUT_CLIPPING_DETECTED",
    "LOT_INCOMPLETE",
    "PAGE_ASPECT_OUT_OF_TOLERANCE",
    "PAGE_QR_UNREADABLE",
    "PAGE_SCALE_OUT_OF_TOLERANCE",
    "SYNTHETIC_FRAME_WRITTEN",
    "TEMPLATE_FROM_MANIFEST_NOT_QR",
    "SCAN_PREVIZ_WARNING_CODES",
    "DETECTION_FINGERPRINT_FIELDS",
    "INGESTED_PAGE_DIGEST_FIELDS",
    "ADDRESSABLE_ELEMENTS",
    "PAGE_ADDRESS_FIELDS",
    "FRAME_ZONE_ADDRESS_FIELDS",
    "MARKER_ADDRESS_FIELDS",
    "ScanPrevizError",
    "ScanPrevizSubject",
    "ScanPrevizCounters",
    "PrevizPageScale",
    "PrevizCornerMarker",
    "PrevizForeignMarker",
    "PrevizFrameZone",
    "PrevizPageCalibration",
    "ScanPrevizPage",
    "ScanPrevizWarnings",
    "ScanPrevizFingerprints",
    "ScanPreviz",
    "build_scan_previz",
    "scan_previz_to_json_dict",
    "scan_previz_from_json_dict",
]


# --------------------------------------------------------------------------
# Vocabulaire fige
# --------------------------------------------------------------------------

#: `kind` de la charge specifique de ce module (enveloppe `previz-1` de 3.5).
SCAN_PREVIZ_KIND = "scan"

#: Etats du document, **specifiques au kind** (precedent 4.9). `detected`: la
#: detection a eu lieu, aucune frame n'est ecrite. `reconstructed`: les frames
#: sont ecrites et leurs chemins relatifs renseignes.
#:
#: Les deux etats sont au niveau du **document**, jamais de la page: une page
#: peut etre detectee sans que ses frames soient ecrites, dans un lot par
#: ailleurs reconstruit, et ce detail se lit dans les compteurs, dans les
#: chemins de frame absents et dans les avertissements. Les deux jumelles ont
#: un etat de document unique; en introduire un par page ici creerait une
#: asymetrie a justifier.
SCAN_PREVIZ_STATE_DETECTED = "detected"
SCAN_PREVIZ_STATE_RECONSTRUCTED = "reconstructed"
SCAN_PREVIZ_STATES: tuple[str, ...] = (
    SCAN_PREVIZ_STATE_DETECTED,
    SCAN_PREVIZ_STATE_RECONSTRUCTED,
)

# --- vocabulaire FERME des avertissements ----------------------------------
#
# Nom de constante volontairement distinct de `PREVIZ_WARNING_CODES` (3.5) et
# de `PDF_PREVIZ_WARNING_CODES` (4.9): reproduire l'homonymie recreerait la
# divergence qu'ARB-14 a du resorber, et 4.9 a deja paye ce choix.
#
# **Regle d'orthographe, posee ici une fois.** Un code qui nomme un fait deja
# nomme par le vocabulaire ferme d'un producteur livre prend l'orthographe **du
# producteur**, au caractere pres. Deux orthographes pour le meme fait imposent
# une table de traduction chez l'appelant, c'est-a-dire le defaut que le point
# H5.4 des arbitrages a ferme en renommant deux codes de 5.6
# (`PAGE_WITHOUT_PAYLOAD` -> `PAGE_QR_UNREADABLE`,
# `UNEXPECTED_FILE_IN_OUTPUT_DIR` -> `PREEXISTING_FRAME_IN_OUTPUT_DIR`)
# **precisement parce que** cette story declarait les consommer. Deux ecarts a
# la redaction d'origine de l'AC 9 en decoulent, et ils sont nommes au Dev
# Agent Record: `FOREIGN_MARKERS_DETECTED` devient `FOREIGN_MARKER_DETECTED`
# (orthographe reelle de `scan_detection`), et `SCALE_MISMATCH_SUSPECTED` --
# qui n'existe chez aucun producteur -- se dedouble en les deux codes reels de
# 5.2, qui ne nomment pas le meme fait: une mise a l'echelle homogene vient de
# l'impression, une divergence entre axes vient du scanner ou d'une page non
# plane (`SCALE_WARNING_TOLERANCE`, EPIC5-ARB-10). Les fondre en un seul code
# aurait perdu l'information et ajoute la traduction.

#: La calibration active a echoue (5.4b, post-MVP). Aucun producteur au MVP,
#: ou le statut vaut invariablement `not_applied`.
CALIBRATION_FAILED = "CALIBRATION_FAILED"

#: 5.1 (`SCAN_INGEST_WARNING_CODES`).
DPI_BELOW_QR_MINIMUM = "DPI_BELOW_QR_MINIMUM"

#: 5.2 (`SCAN_DETECTION_WARNING_CODES`). Un marqueur venu d'ailleurs -- planche
#: voisine, gabarit d'une future version -- est le seul indice qu'il y a deux
#: planches sur la vitre.
FOREIGN_MARKER_DETECTED = "FOREIGN_MARKER_DETECTED"

#: EPIC5-ARB-3: les sentinelles d'une planche sont indiscernables entre elles,
#: un ecretage a eu lieu et l'information saturee est perdue. Elle doit etre
#: **vue** par l'operateur, pas seulement consignee. Producteur post-MVP
#: (mesure de 5.4b sur les patchs sentinelles de 5.9).
GAMUT_CLIPPING_DETECTED = "GAMUT_CLIPPING_DETECTED"

#: Deduit par ce module, **jamais** fourni par l'appelant. Seule exception a la
#: purete d'emission (ARB-13, forme complete de 4.9). Voir la docstring du
#: module pour la regle, qui est celle du manifest (EPIC5-ARB-32).
LOT_INCOMPLETE = "LOT_INCOMPLETE"

#: 5.2. Divergence entre axes: scanner ou page non plane.
PAGE_ASPECT_OUT_OF_TOLERANCE = "PAGE_ASPECT_OUT_OF_TOLERANCE"

#: 5.6 (`SCAN_OUTPUT_WARNING_CODES`), nom pose au point H5.4 des arbitrages.
PAGE_QR_UNREADABLE = "PAGE_QR_UNREADABLE"

#: 5.2. Mise a l'echelle homogene: l'impression.
PAGE_SCALE_OUT_OF_TOLERANCE = "PAGE_SCALE_OUT_OF_TOLERANCE"

#: 5.6, EPIC5-ARB-8: le lot porte au moins une frame de remplacement.
#: Information de premier plan qu'un operateur ne doit pas decouvrir en
#: depilant les pages une a une. **Transporte** depuis le rapport de 5.6,
#: jamais deduit du compteur `synthetic_frame_count`.
SYNTHETIC_FRAME_WRITTEN = "SYNTHETIC_FRAME_WRITTEN"

#: 5.2. Le `template_id` vient d'un manifest local et non du QR.
TEMPLATE_FROM_MANIFEST_NOT_QR = "TEMPLATE_FROM_MANIFEST_NOT_QR"

SCAN_PREVIZ_WARNING_CODES: tuple[str, ...] = (
    CALIBRATION_FAILED,
    DPI_BELOW_QR_MINIMUM,
    FOREIGN_MARKER_DETECTED,
    GAMUT_CLIPPING_DETECTED,
    LOT_INCOMPLETE,
    PAGE_ASPECT_OUT_OF_TOLERANCE,
    PAGE_QR_UNREADABLE,
    PAGE_SCALE_OUT_OF_TOLERANCE,
    SYNTHETIC_FRAME_WRITTEN,
    TEMPLATE_FROM_MANIFEST_NOT_QR,
)

#: Les **seules** entrees de decision de la detection qui entrent dans
#: `fingerprints.detection` (motif `SELECTION_FINGERPRINT_FIELDS` de 3.5 et
#: `COMPOSITION_FINGERPRINT_FIELDS` de 4.9). Y ajouter une constatation --
#: verdict d'ecretage, drapeau synthetique, avertissement -- rendrait
#: l'empreinte sensible a ce qui ne decide rien et signalerait des peremptions
#: imaginaires. Symetriquement, en omettre une entree de decision declarerait a
#: jour un scan qui ne l'est plus.
#:
#: `scan_dpi_detection` y figure depuis la revue de 5.8 (couche 2, majeur 1;
#: couche 3, AC 8). Il manquait, et c'etait le meme trou que 5.10 avait ferme
#: cote impression, un champ plus loin: le DPI **de detection** decide la taille
#: de page redressee, les centres de marqueurs, l'homographie, `frame_zones_px`
#: et le plan de decoupe qui en descend. Les deux DPI peuvent diverger -- 5.2
#: emet `SCAN_DPI_DIFFERS_FROM_INGESTED` precisement pour ca --, si bien que la
#: meme ingestion relue a 300 puis a 600 ppp rendait deux documents dont chaque
#: valeur geometrique differe **sous une empreinte identique**. La jumelle 4.9
#: fait entrer son `dpi` dans son propre `COMPOSITION_FINGERPRINT_FIELDS`.
DETECTION_FINGERPRINT_FIELDS: tuple[str, ...] = (
    "gamut_map_id",
    "ingested_pages_digest",
    "lot_id",
    "project_id",
    "rush_id",
    "scan_dpi_declared",
    "scan_dpi_detection",
    "template_id",
)

#: Ce qui entre dans `ingested_pages_digest`, page par page: l'identite et la
#: forme de chaque page lue, jamais ses avertissements. Deux ingestions du meme
#: lot rendent le meme condensat; une page ajoutee, retiree, relue a une autre
#: profondeur ou dans un autre ordre le change.
#:
#: **Provenance reelle, et elle est mixte** (revue 5.8, couche 1 F4, couche 2
#: finding 3c). Six champs viennent du rapport d'ingestion de 5.1 -- `read_rank`,
#: `width_px`, `height_px`, `channels`, `source_bit_depth`,
#: `scan_input_format`. Les deux autres, `source_path_relative` et
#: `source_page_index`, viennent du **locator du document de detection** (5.2,
#: `locator_source` / `locator_page_index`), que 5.2 recopie de 5.1. La premiere
#: redaction de cette constante annoncait « ce que 5.1 a lu » et le module ne
#: lisait aucun locator d'ingestion: c'etait faux sur deux champs sur huit, et
#: invisible parce que les deux sources coincident sur toutes les fixtures. Le
#: choix est **conserve** -- le document publie ces deux valeurs depuis 5.2, et
#: un condensat qui les prendrait ailleurs que le document lui-meme scellerait
#: autre chose que ce qu'il montre --, mais il est ecrit.
INGESTED_PAGE_DIGEST_FIELDS: tuple[str, ...] = (
    "channels",
    "height_px",
    "read_rank",
    "scan_input_format",
    "source_bit_depth",
    "source_page_index",
    "source_path_relative",
    "width_px",
)

# --- adressage stable des elements editables (frontiere avec 7.4) ----------

#: Les natures d'element que le document rend adressables. Le document
#: **n'autorise** aucune edition pour autant: il la rend exprimable.
ADDRESSABLE_ELEMENTS: tuple[str, ...] = (
    "page",
    "frame_zone",
    "corner_marker",
    "foreign_marker",
)

#: Adresse d'une page. `read_rank` et `page_index` sont **tous les deux**
#: presents et ne se deduisent jamais l'un de l'autre (piege 3).
PAGE_ADDRESS_FIELDS: tuple[str, ...] = ("read_rank", "page_index")

#: Adresse d'une zone de frame: celle de sa page, plus `slot_index`.
FRAME_ZONE_ADDRESS_FIELDS: tuple[str, ...] = ("read_rank", "page_index", "slot_index")

#: Adresse d'un marqueur, de coin ou etranger: celle de sa page, plus son ID.
MARKER_ADDRESS_FIELDS: tuple[str, ...] = ("read_rank", "page_index", "marker_id")

#: Date d'exemple citee dans le refus d'horodatage de ce module.
_GENERATED_AT_EXAMPLE = "2026-08-08T12:00:00Z"


class ScanPrevizError(ValueError):
    """Entree refusee a la construction du document.

    Derive de `ValueError` pour rester capturable par un appelant generique.
    Elle ne signale **jamais** un cas degrade (page refusee, QR illisible,
    frame de remplacement): ceux-la produisent un document valide et partiel,
    porte par les avertissements. Elle signale une entree qui rendrait le
    document lui-meme faux ou trompeur.
    """


# --------------------------------------------------------------------------
# Contrats consommes, en typage structurel (purete: aucun des producteurs
# n'est importable, ils tirent tous cv2 ou numpy)
# --------------------------------------------------------------------------


class IngestedPageLike(Protocol):
    """Sous-ensemble de `scan_ingest.IngestedPage` reellement lu.

    `locator` n'y figure **pas**, et ce n'est pas un oubli. Il y a ete declare
    jusqu'a la revue de 5.8, avec un sous-protocole `_PageLocatorLike`
    (`source_path`, `page_index`) que ce module n'a jamais lu: le chemin source
    et l'index de page d'une page viennent de `locator_source` et
    `locator_page_index` du document de **detection** (5.2), pas du rapport
    d'ingestion. Les trois couches de la revue ont trouve la meme chose, et la
    docstring de `ScanIngestReportLike` ci-dessous la dementait mot pour mot.
    """

    read_rank: int
    scan_input_format: str
    source_bit_depth: int
    width_px: int
    height_px: int
    channels: int


class ScanIngestReportLike(Protocol):
    """Sous-ensemble de `scan_ingest.ScanIngestReport` reellement lu.

    Ce module lit ces champs et **aucun autre**: un champ declare mais jamais
    lu trompe le fournisseur alternatif du protocole (revue 4.9).

    `warnings` y figure depuis la revue de 5.8, ou les trois couches ont trouve
    independamment le meme defaut: la famille etait lue par
    `getattr(ingest, "warnings", ())` **sans etre declaree**, si bien qu'un
    renommage de champ chez 5.1 ne levait rien et **vidait la famille en
    silence**. C'est nommement le mode de panne pour lequel l'AC 12 existe --
    « le premier consommateur reel aurait casse en silence sur un renommage de
    champ, tests tous verts ». L'attribut est desormais lu en direct, et son
    absence tombe dans la garde qui traduit `AttributeError` en
    `ScanPrevizError`.
    """

    ingest_slug: str
    scans_dir: str
    declared_dpi: int
    pages: Sequence[IngestedPageLike]
    warnings: Sequence[str]


class _ForeignMarkerLike(Protocol):
    marker_id: int
    role: str


class _PageScaleLike(Protocol):
    scale_x: float
    scale_y: float
    residual_px: float


class DetectedPageLike(Protocol):
    """Sous-ensemble de `scan_detection.DetectedPage` reellement lu.

    `payload` n'y figure pas: il n'entre pas dans `as_document()` chez 5.2 non
    plus, et tout ce qu'il porte d'utile ici est deja projete par les autres
    champs ou fourni par l'appelant.
    """

    read_rank: int
    status: str
    locator_source: str
    locator_page_index: int | None
    qr_status: str
    template_id: str | None
    template_source: str | None
    project_id: str | None
    rush_id: str | None
    lot_id: str | None
    page_index: int | None
    page_count: int | None
    gamut_map_id: str | None
    corner_centers: Sequence[Sequence[Any]]
    foreign_markers: Sequence[_ForeignMarkerLike]
    homography: Sequence[float] | None
    page_size_px: Sequence[int] | None
    scale: _PageScaleLike | None
    frame_zones_px: Sequence[Mapping[str, Any]]
    warnings: Sequence[str]
    refusal_reason: str | None
    #: Story 5.27. Lu **directement**, jamais par un `getattr` avec repli: un
    #: repli relirait « pas de code » chez un producteur qui aurait renomme le
    #: champ, et le mutant de renommage survivrait a l'integration (mesure de la
    #: revue de 5.25 sur `warnings.ingest`).
    refusal_code: str | None


class LotDetectionReportLike(Protocol):
    """Sous-ensemble de `scan_detection.LotDetectionReport` reellement lu."""

    scan_dpi: int
    pages: Sequence[DetectedPageLike]
    warnings: Sequence[str]


class FrameCropPlanLike(Protocol):
    """Sous-ensemble de `scan_crop.FrameCropPlan` reellement lu."""

    slot_index: int
    frame_timecode: str | None
    zone_name: str
    zone_rect_mm: Sequence[float]
    image_rect_mm: Sequence[float]
    crop_x_px: int
    crop_y_px: int
    width_px: int
    height_px: int


class PageCropPlanLike(Protocol):
    """Sous-ensemble de `scan_crop.PageCropPlan` reellement lu."""

    frames: Sequence[FrameCropPlanLike]


class OutputFrameLike(Protocol):
    """Sous-ensemble de `scan_output_frames.OutputFrame` reellement lu."""

    page_index: int
    slot_index: int
    path: str
    synthetic: bool
    synthetic_reason: str | None


class LotOutputReportLike(Protocol):
    """Sous-ensemble de `scan_output_frames.LotOutputReport` reellement lu.

    Les cardinaux du rapport n'y figurent **pas**, et c'est delibere: ils
    decrivent la passe, pas le lot (EPIC5-ARB-32). Ils sont fournis en
    parametres de `build_scan_previz`, ce qui laisse l'appelant verser ceux du
    manifest quand c'est le verdict de lot qu'il veut montrer.

    `warnings` y figure depuis la revue de 5.8, pour la meme raison que chez
    `ScanIngestReportLike`: la famille etait lue par `getattr` avec repli, donc
    un renommage chez 5.6 aurait vide `warnings.output` sans un mot --
    `SYNTHETIC_FRAME_WRITTEN` n'aurait plus jamais atteint l'operateur.
    """

    output_dir: str
    frames: Sequence[OutputFrameLike]
    warnings: Sequence[str]


# --------------------------------------------------------------------------
# Document
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ScanPrevizSubject:
    """Ce sur quoi porte la previz.

    L'identite du lot est **fournie par l'appelant**, jamais elue parmi les
    pages: choisir celle de la premiere page fabriquerait un lot qui n'a jamais
    existe -- c'est le motif meme de `scan_detection.LotIdentityError`, qui
    refuse un lot dont les pages ne parlent pas du meme lot.
    """

    project_id: str
    rush_id: str
    lot_id: str
    ingest_slug: str
    template_id: str
    gamut_map_id: str
    fps_target_exact: str | None
    target_colorspace: str | None
    patch_preset_id: str | None
    scan_dpi_declared: int
    scan_dpi_detection: int
    scans_dir_relative: str
    output_dir_relative: str | None


@dataclass(frozen=True)
class ScanPrevizCounters:
    """Un lot se lit d'abord par ses compteurs.

    `pages_present` est le cardinal de ce que **ce document porte**, pas une
    mesure du monde: il n'y a pas de comptage de fichiers ici. `pages_expected`
    et les trois cardinaux de frames sont fournis par l'appelant; les frames
    valent `None` en regime `detected`, ou rien n'est encore ecrit.

    `synthetic_frame_count` porte le nom que l'AC 4 lui donne, et **pas**
    `synthetic_frames`: ce nom-la est deja pris deux fois, et il y designe des
    deux cotes une **collection** -- `scan_output_frames.LotOutputReport.`
    `synthetic_frames` (un tuple d'`OutputFrame`) et `lots[].synthetic_frames`
    du manifest de 5.7 (la liste triee des noms de fichiers, EPIC5-ARB-33
    clause 1). Une interface qui lit le manifest et la previz du meme lot
    aurait vu le meme nom porter une liste d'un cote et un cardinal de l'autre:
    c'est exactement l'homonymie divergente qu'ARB-14 a du resorber, et la
    regle d'orthographe que ce module se pose a lui-meme pour les codes
    d'avertissement. Corrige a la revue de 5.8, pendant qu'aucun consommateur
    n'existe.
    """

    pages_present: int
    pages_expected: int | None
    frames_written: int | None
    frames_expected: int | None
    synthetic_frame_count: int | None


@dataclass(frozen=True)
class PrevizPageScale:
    """Echelle observee et residu, transportes verbatim de 5.2.

    **Aucun arrondi ici** (AC 3): la precision d'arrondi est celle declaree par
    le producteur (`scan_detection.DOCUMENT_FLOAT_PRECISION` pour l'homographie,
    arrondis propres de `PageScaleMeasurement.as_document`). Arrondir ici
    ferait diverger ce document de celui de 5.2 sur les memes mesures.
    """

    scale_x: float
    scale_y: float
    residual_px: float


@dataclass(frozen=True)
class PrevizCornerMarker:
    """Un marqueur de coin detecte, avec son centre en pixels de page."""

    marker_id: int
    center_x_px: float
    center_y_px: float


@dataclass(frozen=True)
class PrevizForeignMarker:
    """Un marqueur detecte qui n'est pas un coin de cette page, avec son role."""

    marker_id: int
    role: str


@dataclass(frozen=True)
class PrevizFrameZone:
    """Une zone de frame d'une page, et la frame qu'elle a produite.

    Deux rectangles, chacun en millimetres **et** en pixels de page redressee:
    `zone_*` est l'emprise de la zone du gabarit, `crop_*` le rectangle
    reellement decoupe. Les pixels de zone viennent de 5.2 (`frame_zones_px`),
    les pixels de decoupe de 5.3.

    Invariant du drapeau synthetique (EPIC5-ARB-8, piege 8): `synthetic` est
    renseigne **si et seulement si** `frame_path_relative` l'est, `False`
    compris; `synthetic_reason` **si et seulement si** `synthetic` vaut `True`.
    Le constructeur refuse toute autre combinaison.
    """

    slot_index: int
    frame_timecode: str | None
    zone_name: str
    zone_x_mm: float
    zone_y_mm: float
    zone_w_mm: float
    zone_h_mm: float
    crop_x_mm: float
    crop_y_mm: float
    crop_w_mm: float
    crop_h_mm: float
    crop_x_px: int
    crop_y_px: int
    crop_w_px: int
    crop_h_px: int
    zone_x_px: int | None = None
    zone_y_px: int | None = None
    zone_w_px: int | None = None
    zone_h_px: int | None = None
    frame_path_relative: str | None = None
    synthetic: bool | None = None
    synthetic_reason: str | None = None

    def __post_init__(self) -> None:
        if (self.frame_path_relative is None) != (self.synthetic is None):
            raise ScanPrevizError(
                "Le drapeau `synthetic` accompagne un chemin de frame, ni plus "
                "ni moins: il est present des qu'une frame l'est, `false` "
                "compris, et absent quand aucune frame n'a ete ecrite. Un "
                "drapeau omis se relit « vraie frame » et ferait passer une "
                "mire « FRAME MANQUANTE » pour un plan du film (EPIC5-ARB-8). "
                f"Recu frame_path_relative={self.frame_path_relative!r}, "
                f"synthetic={self.synthetic!r}"
            )
        if self.synthetic is not None and not isinstance(self.synthetic, bool):
            raise ScanPrevizError(
                f"synthetic doit etre un booleen, recu {self.synthetic!r}"
            )
        # Le rectangle de zone en pixels est rendu **en bloc** ou pas du tout:
        # `_zone_to_json_dict` ne conditionne son emission que sur `zone_x_px`,
        # donc une combinaison partielle publiait un rectangle a composantes
        # `null` (revue 5.8, couche 2, finding 8). Le chemin qui compte n'est
        # pas le builder -- les quatre valeurs y sortent du meme dict -- mais la
        # story 7.4, qui edite des zones et ne reconstruit pas forcement le
        # document par le builder.
        pixels = (self.zone_x_px, self.zone_y_px, self.zone_w_px, self.zone_h_px)
        if any(value is None for value in pixels) and any(
            value is not None for value in pixels
        ):
            raise ScanPrevizError(
                "Le rectangle de zone en pixels est present en entier ou "
                "absent en entier (x, y, width, height): une composante "
                "manquante publierait un rectangle a `null` que rien ne sait "
                f"placer. Recu {pixels!r}"
            )
        if (self.synthetic_reason is not None) != (self.synthetic is True):
            raise ScanPrevizError(
                "synthetic_reason est present si et seulement si `synthetic` "
                "vaut true, et jamais `null`: une vraie frame n'a pas de motif "
                "de remplacement, et une mire sans motif ne dit pas si le trou "
                "vient de la detection ou de la decoupe. Recu "
                f"synthetic={self.synthetic!r}, "
                f"synthetic_reason={self.synthetic_reason!r}"
            )


@dataclass(frozen=True)
class PrevizPageCalibration:
    """Etat de la correction couleur pour une page (5.4b).

    `status` est transporte verbatim -- au MVP il vaut invariablement
    `not_applied`, la calibration active etant post-MVP (EPIC5-ARB-5).

    `clipping_detected` est le **verdict d'ecretage** des patchs sentinelles
    (5.9), mesure par 5.4b. `None` signifie « rien n'a ete mesure », et il est
    alors **omis** du document rendu, jamais ecrit `null` et surtout jamais
    remplace par `false`. Les deux valeurs sont independantes: une correction
    peut converger proprement sur une planche par ailleurs ecretee, et ce
    module n'en deduit jamais l'une de l'autre.
    """

    status: str
    clipping_detected: bool | None = None


@dataclass(frozen=True)
class ScanPrevizPage:
    """Une page du lot, telle que le scan l'a lue, decodee et decoupee.

    Deux champs additifs depuis la story 5.26, tous deux a defaut `None` pour
    qu'un document anterieur (5.25) reste constructible et relisible -- il est
    alors **refuse nommement par le consommateur d'ecriture**, jamais devine:

    * `payload`: le payload decode **verbatim**, present si et seulement si la
      page est identifiee (meme discipline d'emission conditionnelle que le
      drapeau `synthetic`). C'est H4 etendu a la frontiere de processus: il
      n'est ni re-decode ni reconstitue -- `timecode_base_fps`, champ requis du
      payload 2.1, n'est projete nulle part ailleurs dans le document;
    * `source_digest`: condensat des **octets** du fichier source de la page
      (la copie ingeree a `source_path_relative`), fourni par l'appelant --
      ce module ne lit aucun fichier. `ingested_pages_digest` scelle la forme,
      celui-ci scelle le contenu; deux pages du meme PDF portent le meme
      condensat, et c'est exact.

    Aucun des deux n'entre dans `fingerprints.detection`
    (`DETECTION_FINGERPRINT_FIELDS` inchange): le condensat est verifie
    directement par l'ecriture, et le payload est une projection de ce que
    l'empreinte scelle deja.
    """

    read_rank: int
    page_index: int | None
    page_count: int | None
    status: str
    qr_status: str
    refusal_reason: str | None
    source_path_relative: str
    source_page_index: int | None
    scan_input_format: str
    source_bit_depth: int
    width_px: int
    height_px: int
    channels: int
    decoded_project_id: str | None
    decoded_rush_id: str | None
    decoded_lot_id: str | None
    decoded_gamut_map_id: str | None
    template_id: str | None
    template_source: str | None
    page_size_px: tuple[int, ...] | None
    homography: tuple[float, ...] | None
    scale: PrevizPageScale | None
    corner_markers: tuple[PrevizCornerMarker, ...]
    foreign_markers: tuple[PrevizForeignMarker, ...]
    frame_zones: tuple[PrevizFrameZone, ...]
    calibration: PrevizPageCalibration | None
    warnings: tuple[str, ...]
    payload: Mapping[str, Any] | None = None
    source_digest: str | None = None
    #: Code de refus **enumere** de la story 5.27, a cote de `refusal_reason`
    #: qui garde sa phrase francaise inchangee. Troisieme champ additif a defaut
    #: `None` de cette dataclass, sur le precedent ecrit ci-dessus: un document
    #: anterieur reste constructible et relisible, il rend simplement `None` --
    #: jamais une chaine vide, jamais un code par defaut. Il n'entre pas dans
    #: `fingerprints.detection` (`DETECTION_FINGERPRINT_FIELDS` inchange): un
    #: motif de refus ne decide rien de ce que l'empreinte scelle, et l'y faire
    #: entrer declarerait perimes tous les documents deja ecrits.
    #:
    #: Le vocabulaire du coeur (`scan_detection.SCAN_REFUSAL_CODES`) est valide
    #: **a l'emission**, jamais ici: ce champ est transporte verbatim, sur le
    #: modele de `fingerprints.selection`. Un document est relu par des versions
    #: differentes du logiciel -- c'est le sens meme de 5.26 --, et refuser tout
    #: un scan parce qu'une version ulterieure a ajoute un code le rendrait
    #: illisible pour un champ purement informatif.
    refusal_code: str | None = None


@dataclass(frozen=True)
class ScanPrevizWarnings:
    """Quatre familles distinctes, jamais fusionnees, jamais traduites.

    Motif des trois familles de 3.5. `ingest`, `detection` et `output`
    transportent verbatim les codes des vocabulaires fermes de 5.1, 5.2 et 5.6
    -- ce module n'en controle pas le vocabulaire, qui appartient a chaque
    producteur et vit dans un module impur. `previz` est la seule famille dont
    le vocabulaire est le sien (:data:`SCAN_PREVIZ_WARNING_CODES`), validee a
    la construction, dedoublonnee et triee.
    """

    ingest: tuple[str, ...] = ()
    detection: tuple[str, ...] = ()
    output: tuple[str, ...] = ()
    previz: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScanPrevizFingerprints:
    """De quoi detecter la peremption. Voir la docstring du module."""

    detection: str
    selection: str | None = None


@dataclass(frozen=True)
class ScanPreviz:
    """Document de previz de scan, fige et comparable.

    Confort de typage pour un consommateur in-process; la forme **normative**
    est le JSON rendu par :func:`scan_previz_to_json_dict`. Imposer l'objet
    Python comme seul contrat exclurait d'office un consommateur hors-processus
    ou distant, donc prejugerait de l'Epic 7.
    """

    previz_schema_version: str
    kind: str
    state: str
    generated_at_utc: str
    subject: ScanPrevizSubject
    counters: ScanPrevizCounters
    pages: tuple[ScanPrevizPage, ...]
    warnings: ScanPrevizWarnings
    fingerprints: ScanPrevizFingerprints


# --------------------------------------------------------------------------
# Gardes locales: la hierarchie de ce module par-dessus `previz_common`
# --------------------------------------------------------------------------


def _require_text(value: Any, label: str) -> str:
    return _common_require_text(value, label, error_type=ScanPrevizError)


def _optional_text(value: Any, label: str) -> str | None:
    return _common_optional_text(value, label, error_type=ScanPrevizError)


def _code_de_refus(value: Any, label: str) -> str | None:
    """Le code de refus enumere (story 5.27): **rien d'exploitable vaut absent**.

    Ce champ est le seul du document a ne jamais pouvoir rendre un scan
    illisible, et c'est une decision, pas un relachement: il est **purement
    informatif**. Il repond a « pourquoi cette page est refusee » pour un ecran
    qui veut brancher dessus ; la phrase francaise, elle, voyage a cote, dans
    `refusal_reason`, sous une garde entiere. Perdre le code coute un badge ;
    refuser le document coute la lecture de tout le scan.

    Vaut donc `None`, sans jamais lever:

    * la cle **absente** -- un document ecrit avant cette story n'en porte pas ;
    * `null` ;
    * la chaine **vide**, et la chaine **uniquement blanche** (`EC-9`).
      `require_text` ne fait aucun `strip`, si bien que `"   "` traversait et
      ressortait verbatim ; le consommateur `gui.lecture_detection` (7.4,
      `done`) partage exactement la meme condition et aurait affiche un badge
      de code vide -- « un code vide se lirait comme un code, ce qui est pire
      que pas de code », le motif que cette fonction cite elle-meme ;
    * toute valeur **non textuelle** -- un entier, une liste, un objet, un
      booleen (`BH-8`). C'est l'inversion d'une decision d'ecriture de la
      premiere version, et voici ce qui l'a renversee: mesure sur le document
      terrain `tests/fixtures/detection-scan-reelle/detect-ok-et-refus.json`,
      un `refusal_code: 42` faisait refuser **tout le document** a
      `gui.lecture_detection.depuis_json`. Avant 5.27 cette cle etait inconnue
      du coeur et l'ecran l'ignorait en silence : la story **durcissait** donc
      la lecture d'une story close, sur un champ informatif, ce qu'aucune AC
      n'a jamais demande. La discipline de lecture tranchee en 5.26 -- un
      document ne se refuse que sur ce qui le rend inexploitable -- vaut ici
      comme partout ailleurs.

    Ce qui n'est pas relache: le **vocabulaire**, ferme et valide **a
    l'emission** par `scan_detection.validate_refusal_code`. Un code inconnu ne
    peut pas naitre ici ; s'il arrive par un document tiers, il est transporte
    verbatim plutot que refuse, exactement comme le prevoit la discipline de
    lecture. La garde de forme reste entiere sur `refusal_reason`, qui, elle,
    porte le texte montre a l'operateur.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    return _optional_text(value, label)


def _require_int(value: Any, label: str) -> int:
    return _common_require_int(value, label, error_type=ScanPrevizError)


def _optional_int(value: Any, label: str) -> int | None:
    if value is None:
        return None
    return _require_int(value, label)


def _require_number(value: Any, label: str):
    return _common_require_number(value, label, error_type=ScanPrevizError)


def _relative_path(value: Any, label: str) -> str:
    return _common_relative_path(value, label, error_type=ScanPrevizError)


def _optional_relative_path(value: Any, label: str) -> str | None:
    return _common_optional_relative_path(value, label, error_type=ScanPrevizError)


def _exact_rate(fps: Any) -> str:
    return _common_exact_rate(fps, error_type=ScanPrevizError)


def _require_bool(value: Any, label: str) -> bool:
    """Booleen strict: ni coercition, ni `None`.

    Le module refuse ailleurs toute glissade de type avec insistance
    (`require_int` exclut `bool`, le verdict d'ecretage exige un vrai booleen,
    `PrevizFrameZone.__post_init__` porte sa propre garde). Le seul endroit qui
    coercait etait le drapeau synthetique, et c'etait le plus couteux des
    trois: `bool(None)` vaut `False`, donc un producteur qui **omet** le
    drapeau le voyait rendu « vraie frame » (revue 5.8, couche 2, finding 5).
    """
    if not isinstance(value, bool):
        raise ScanPrevizError(f"{label} doit etre un booleen, recu {value!r}")
    return value


def _require_cardinal(value: Any, label: str) -> int:
    """Cardinal positif ou nul."""
    count = _require_int(value, label)
    if count < 0:
        raise ScanPrevizError(
            f"{label} doit etre un cardinal positif ou nul, recu {value!r}"
        )
    return count


def _require_rect_mm(value: Any, label: str) -> tuple:
    """Rectangle `(x, y, largeur, hauteur)` en mm: 4 nombres, verbatim."""
    try:
        items = tuple(value)
    except TypeError as exc:
        raise ScanPrevizError(
            f"{label} doit etre un rectangle (x, y, w, h), recu {value!r}"
        ) from exc
    if len(items) != 4:
        raise ScanPrevizError(
            f"{label} doit porter exactement 4 composantes (x, y, w, h), "
            f"recu {value!r}"
        )
    return tuple(_require_number(item, f"{label}[{i}]") for i, item in enumerate(items))


def _codes(values: Any, label: str) -> tuple[str, ...]:
    """Sequence **ordonnee** de codes, jamais une chaine ni un ensemble.

    Deux refus, et pas un:

    * une chaine se decouperait en lettres et le document porterait des codes
      d'un caractere;
    * une collection **non ordonnee** (`set`, `frozenset`, generateur) casse la
      promesse centrale du module -- « la meme chaine octet pour octet d'un
      processus a l'autre ». L'ordre d'iteration d'un `set` Python depend de la
      graine de hachage du processus: mesure a la revue de 5.8 (couche 2,
      finding 7) sur quatre valeurs de `PYTHONHASHSEED`, la meme entree rendait
      quatre documents differents. Les trois familles amont sont transportees
      **verbatim**, donc dans l'ordre du producteur: c'est cet ordre qui doit
      exister. Refuser ici ne touche pas a la doctrine du transport verbatim,
      elle la rend tenable.
    """
    if values is None:
        return ()
    if isinstance(values, str):
        raise ScanPrevizError(
            f"{label} doit etre une sequence de codes, pas une chaine: {values!r}"
        )
    if not isinstance(values, Sequence):
        raise ScanPrevizError(
            f"{label} doit etre une sequence **ordonnee** de codes (liste ou "
            f"tuple), recu {type(values).__name__}: {values!r}. Une collection "
            "non ordonnee rendrait deux documents differents pour la meme "
            "entree d'un processus a l'autre"
        )
    received = tuple(values)
    return tuple(_require_text(code, f"Code de {label}") for code in received)


def _known_codes(
    codes: tuple[str, ...], vocabulary: Any, label: str
) -> tuple[str, ...]:
    """Confronter une famille amont au vocabulaire **verse par l'appelant**.

    Troisieme voie du dilemme que le Dev Agent Record posait (revue 5.8, couche
    3): les vocabulaires fermes des producteurs vivent dans des modules qui
    tirent `cv2`, donc ce module ne peut ni les importer (AC 11) ni les
    recopier (le second vocabulaire voisin qu'ARB-14 a du resorber). Mais
    `previz_common.require_known_codes` prend le vocabulaire **en argument**:
    l'appelant, qui importe deja les producteurs puisqu'il en recoit les
    rapports, peut donc le verser. Zero import nouveau, zero copie, zero
    divergence possible -- et le controle passe du temps de test au temps de
    construction, c'est-a-dire la ou il protege un vrai consommateur.

    Cela ne viole pas l'AC 4 (« jamais reinterprete ni traduit ici »): refuser
    un code hors vocabulaire ne reinterprete rien et ne traduit rien, ca
    refuse. Le regime par defaut (`None`) ne controle rien et preserve
    exactement le comportement d'origine pour un appelant qui ne veut pas
    payer.
    """
    if vocabulary is None:
        return codes
    known = _codes(vocabulary, f"{label} (vocabulaire)")
    return require_known_codes(
        codes,
        known,
        label=f"Code de {label} hors du vocabulaire verse par l'appelant",
        error_type=ScanPrevizError,
    )


def _known_value(value: Any, vocabulary: Any, label: str) -> Any:
    """Meme regime que :func:`_known_codes`, pour une valeur scalaire.

    Sert au `synthetic_reason` de 5.6 et au statut de calibration de 5.4b, qui
    ne sont pas des familles mais des valeurs uniques d'un vocabulaire ferme.
    """
    if vocabulary is None or value is None:
        return value
    _known_codes((value,), vocabulary, label)
    return value


def _previz_codes(values: Any) -> tuple[str, ...]:
    """Vocabulaire ferme de ce module: inconnu refuse, doublon refuse.

    `LOT_INCOMPLETE` est refuse **en entree** (motif 4.9): il est toujours
    deduit ici, et un code fourni pourrait contredire les compteurs du
    document. `SYNTHETIC_FRAME_WRITTEN`, lui, est **accepte** en entree: il se
    transporte depuis le rapport de 5.6 et ne se deduit jamais du compteur.
    """
    validated = _codes(values, "warnings.previz")
    require_known_codes(
        validated,
        SCAN_PREVIZ_WARNING_CODES,
        label="Code d'avertissement de previz de scan inconnu",
        error_type=ScanPrevizError,
    )
    if len(set(validated)) != len(validated):
        raise ScanPrevizError(
            f"warnings.previz porte un code duplique: {validated!r}. Le "
            "vocabulaire est ferme et chaque code se declare au plus une fois "
            "(deux documents semantiquement identiques doivent produire le "
            "meme JSON canonique)"
        )
    if LOT_INCOMPLETE in validated:
        raise ScanPrevizError(
            f"{LOT_INCOMPLETE} ne se fournit jamais: il est deduit ici de la "
            "confrontation du cardinal attendu, du cardinal ecrit et du nombre "
            "de frames de remplacement (EPIC5-ARB-32). Un code fourni pourrait "
            "contredire les compteurs du document"
        )
    return validated


# --------------------------------------------------------------------------
# Construction
# --------------------------------------------------------------------------


def build_scan_previz(
    *,
    ingest: ScanIngestReportLike,
    detection: LotDetectionReportLike,
    generated_at_utc: str,
    project_id: str,
    rush_id: str,
    lot_id: str,
    template_id: str,
    gamut_map_id: str,
    state: str = SCAN_PREVIZ_STATE_DETECTED,
    crop_plans: Mapping[int, PageCropPlanLike] | None = None,
    output_report: LotOutputReportLike | None = None,
    calibration_status: Mapping[int, str] | None = None,
    gamut_clipping: Mapping[int, bool] | None = None,
    fps_target: Any = None,
    target_colorspace: str | None = None,
    patch_preset_id: str | None = None,
    pages_expected_count: int | None = None,
    frames_written_count: int | None = None,
    frames_expected_count: int | None = None,
    synthetic_frame_count: int | None = None,
    page_payloads: Mapping[int, Mapping[str, Any]] | None = None,
    source_digests: Mapping[int, str] | None = None,
    previz_warnings: Sequence[str] = (),
    selection_fingerprint: str | None = None,
    ingest_warning_vocabulary: Sequence[str] | None = None,
    detection_warning_vocabulary: Sequence[str] | None = None,
    output_warning_vocabulary: Sequence[str] | None = None,
    synthetic_reason_vocabulary: Sequence[str] | None = None,
    calibration_status_vocabulary: Sequence[str] | None = None,
) -> ScanPreviz:
    """Projeter les sorties de 5.1 / 5.2 / 5.3 / 5.4b / 5.6 en document de previz.

    **Projection stricte**: rien n'est recalcule, rien n'est recompte, rien
    n'est reconcilie. Deux valeurs d'entree incoherentes entre elles ressortent
    telles quelles.

    Parameters
    ----------
    ingest:
        Rapport d'ingestion de 5.1. Ses pages sont indexees par `read_rank`
        pour renseigner le format et la profondeur de chaque page detectee.
    detection:
        Document de detection de 5.2. C'est **lui** qui donne l'ordre des pages
        du document: elles sont transportees dans son ordre, jamais re-triees.
    generated_at_utc:
        Horodatage UTC ISO 8601 suffixe `Z`, **fourni par l'appelant**: lire
        l'horloge ici rendrait le document non deterministe.
    project_id, rush_id, lot_id, template_id, gamut_map_id:
        Identite du lot, **fournie par l'appelant** et jamais elue parmi les
        pages. `gamut_map_id` est obligatoire et sans branche « absent »: le
        champ est le onzieme champ **obligatoire** du payload depuis
        EPIC5-ARB-13, un payload sans lui est invalide en amont et n'atteint
        jamais ce module. En coder une branche reintroduirait un chemin mort
        que la chaine ne peut plus produire.
    state:
        `detected` (aucune frame ecrite) ou `reconstructed`.
    crop_plans:
        `read_rank` -> plan de decoupe de 5.3. Un rang absent du mapping rend
        une page sans zone: une decoupe partielle se decrit, elle ne se devine
        pas. Un rang inconnu de la detection est refuse -- il serait
        silencieusement ignore.
    output_report:
        Rapport d'ecriture de 5.6, en regime `reconstructed` uniquement. Seuls
        son `output_dir` et ses `frames` sont lus: **pas ses cardinaux**, qui
        decrivent la passe et non le lot (EPIC5-ARB-32).
    calibration_status, gamut_clipping:
        `read_rank` -> statut de calibration de 5.4b, et `read_rank` -> verdict
        d'ecretage. Le second est **omis** quand il manque, jamais remplace par
        un verdict negatif. Aucun des deux ne se deduit de l'autre.
    fps_target, target_colorspace, patch_preset_id:
        Facultatifs, transportes tels quels (la cadence passe par la forme
        canonique unique `codec_profiles.exact_frame_rate`). `None` est la
        valeur normale d'un lot dont aucune page n'a decode.
    pages_expected_count:
        Cardinal de pages annonce par le lot, **fourni par l'appelant**. Il
        n'est **pas** confronte au nombre de pages presentes: un lot qui porte
        plus de pages qu'il n'en annonce est precisement le lot melange que ce
        document existe pour montrer, et le refuser detruirait le diagnostic.
    frames_written_count, frames_expected_count, synthetic_frame_count:
        Les trois cardinaux de frames, **fournis par l'appelant** en regime
        `reconstructed` et interdits en `detected`. Ils ne sont pas lus dans le
        rapport de 5.6: voir la section « Compteurs et completude du lot » de la
        docstring du module. Un cardinal ecrit superieur au cardinal attendu est
        refuse a la construction (ARB-13): le document se contredirait lui-meme.

        **Correspondance exacte avec les champs du manifest**, nommee ici parce
        que la revue de 5.8 (couche 3, AC 9) a montre que « la regle du manifest
        mot pour mot » ne suffit pas a la dire -- le mapping naturel est refuse
        a la construction:

        * `frames_written_count` = `lots[].reconstructed_frame_count`
          **plus** `lots[].synthetic_frame_count` du manifest, c'est-a-dire
          l'`observed_frame_count` de la passe (EPIC5-ARB-33: le total du
          dossier). Verser le seul `reconstructed_frame_count`, qui **exclut**
          les mires (`io/scan_manifest`: `reconstructed = observed - len(S)`),
          fait lever la garde `synthetic_frame_count > frames_written_count`
          des qu'un lot ne porte que des mires -- ici `frames_written` **inclut**
          les mires, « une frame de remplacement est une frame ecrite »;
        * `frames_expected_count` = `lots[].expected_frame_count`, `None` quand
          il est indeterminable;
        * `synthetic_frame_count` = `lots[].synthetic_frame_count`, c'est-a-dire
          `len(lots[].synthetic_frames)` (EPIC5-ARB-33, clause 1: la liste est
          le registre, l'entier son cardinal).

        Le **verdict** de completude est le meme dans les deux lectures (des que
        `synthetic > 0`, les deux formules disent incomplet); c'est le nombre
        **publie** qui differait, et c'est lui qu'une interface affiche a cote
        du manifest.
    page_payloads, source_digests:
        Champs additifs de la story 5.26, tous deux `read_rank` -> valeur et
        facultatifs (un document de 5.25 reste constructible sans eux).
        `page_payloads` transporte le payload decode **verbatim** -- fourni
        par l'appelant pour les seules pages identifiees, jamais re-decode ni
        reconstitue ici. `source_digests` transporte le condensat des octets
        du fichier source de chaque page, calcule par l'appelant: ce module ne
        lit aucun fichier. Un rang inconnu du document de detection est refuse
        (regle de `_mapping_by_rank`).
    previz_warnings:
        Codes **recus** de l'appelant, valides contre
        :data:`SCAN_PREVIZ_WARNING_CODES`. `LOT_INCOMPLETE` y est refuse (il est
        deduit); `SYNTHETIC_FRAME_WRITTEN` y est **accepte** (il se transporte).
    selection_fingerprint:
        Empreinte amont **transportee verbatim**, forme complete exigee.
        Optionnelle: aucun producteur du chemin scan n'en pose aujourd'hui, et
        en fabriquer une ici serait un calcul.
    ingest_warning_vocabulary, detection_warning_vocabulary,
    output_warning_vocabulary, synthetic_reason_vocabulary,
    calibration_status_vocabulary:
        Les **cinq** vocabulaires fermes que ce module transporte sans pouvoir
        les importer (ils vivent tous dans un module qui tire `cv2` ou `numpy`,
        cf. AC 11). L'appelant, qui importe deja les producteurs puisqu'il en
        recoit les rapports, peut les verser ici:
        `scan_ingest.SCAN_INGEST_WARNING_CODES`,
        `scan_detection.SCAN_DETECTION_WARNING_CODES`,
        `scan_output_frames.SCAN_OUTPUT_WARNING_CODES`,
        `scan_output_frames.SYNTHETIC_FRAME_REASONS` et
        `color_pipeline.CALIBRATION_STATUS_VALUES`. Le controle passe alors du
        temps de test au temps de construction. `None` (defaut) ne controle
        rien et preserve exactement le comportement d'origine.

        Les cinq sont traites **du meme regime**: le module transportait cinq
        vocabulaires non controles, pas deux (revue 5.8, couche 3), et en
        controler deux seulement aurait cree deux regimes voisins pour le meme
        probleme -- le defaut d'origine.

    Raises
    ------
    ScanPrevizError
        Etat inconnu, horodatage non conforme, code hors vocabulaire ou
        duplique, `LOT_INCOMPLETE` fourni, cardinal manquant ou interdit pour
        l'etat, cardinal ecrit superieur a l'attendu, chemin absolu, rang
        inconnu dans un mapping, page detectee absente du rapport d'ingestion
        ou l'inverse, drapeau synthetique incoherent avec son chemin de frame.
    """
    if state not in SCAN_PREVIZ_STATES:
        raise ScanPrevizError(
            f"Etat de previz inconnu: {state!r}. Vocabulaire ferme: "
            f"{', '.join(SCAN_PREVIZ_STATES)}"
        )
    generated = normalize_generated_at_utc(
        generated_at_utc, error_type=ScanPrevizError, example=_GENERATED_AT_EXAMPLE
    )
    caller_codes = _previz_codes(previz_warnings)

    fingerprint = _optional_text(selection_fingerprint, "selection_fingerprint")
    if fingerprint is not None and not is_complete_fingerprint(fingerprint):
        raise ScanPrevizError(
            "selection_fingerprint doit porter la recette de la famille sous "
            "forme complete (prefixe 'sha256-v1:' suivi de 64 hexadecimaux), "
            f"recu {selection_fingerprint!r}. Le frame_timecodes_digest de 3.4 "
            "est une recette distincte, non comparable: ne pas le transporter "
            "ici."
        )

    written, expected, synthetic_count, output_dir = _state_counters(
        state,
        output_report=output_report,
        frames_written_count=frames_written_count,
        frames_expected_count=frames_expected_count,
        synthetic_frame_count=synthetic_frame_count,
    )

    try:
        ingested_by_rank = _ingested_pages_by_rank(ingest)
        detected_pages = tuple(detection.pages)
        frames_by_address = _frames_by_address(output_report)
        # Les adresses de frame que les zones du document reclament reellement.
        # Ce qui reste est refuse plus bas: une frame ecrite que le document ne
        # montre nulle part serait comptee et invisible.
        claimed_addresses: dict[tuple[int, int], int] = {}
        pages = _project_pages(
            detected_pages,
            ingested_by_rank=ingested_by_rank,
            crop_plans=crop_plans,
            frames_by_address=frames_by_address,
            claimed_addresses=claimed_addresses,
            calibration_status=calibration_status,
            gamut_clipping=gamut_clipping,
            page_payloads=page_payloads,
            source_digests=source_digests,
            synthetic_reason_vocabulary=synthetic_reason_vocabulary,
            calibration_status_vocabulary=calibration_status_vocabulary,
        )
        _require_every_written_frame_is_shown(frames_by_address, claimed_addresses)
        subject = ScanPrevizSubject(
            project_id=_require_text(project_id, "project_id"),
            rush_id=_require_text(rush_id, "rush_id"),
            lot_id=_require_text(lot_id, "lot_id"),
            ingest_slug=_require_text(ingest.ingest_slug, "ingest.ingest_slug"),
            template_id=_require_text(template_id, "template_id"),
            gamut_map_id=_require_text(gamut_map_id, "gamut_map_id"),
            fps_target_exact=None if fps_target is None else _exact_rate(fps_target),
            target_colorspace=_optional_text(target_colorspace, "target_colorspace"),
            patch_preset_id=_optional_text(patch_preset_id, "patch_preset_id"),
            scan_dpi_declared=_require_int(ingest.declared_dpi, "ingest.declared_dpi"),
            scan_dpi_detection=_require_int(detection.scan_dpi, "detection.scan_dpi"),
            scans_dir_relative=_relative_path(ingest.scans_dir, "ingest.scans_dir"),
            output_dir_relative=output_dir,
        )
        # Acces **direct**, jamais `getattr` avec repli (revue 5.8, les trois
        # couches): un champ absent doit tomber dans la garde ci-dessous, pas
        # se relire « aucun avertissement ». La famille `detection` etait deja
        # dans ce regime, et l'ecart entre les trois familles etait le defaut.
        ingest_warnings = _known_codes(
            _codes(ingest.warnings, "warnings.ingest"),
            ingest_warning_vocabulary,
            "warnings.ingest",
        )
        detection_warnings = _known_codes(
            _codes(detection.warnings, "warnings.detection"),
            detection_warning_vocabulary,
            "warnings.detection",
        )
        output_warnings = _known_codes(
            _codes(
                () if output_report is None else output_report.warnings,
                "warnings.output",
            ),
            output_warning_vocabulary,
            "warnings.output",
        )
    except ScanPrevizError:
        raise
    except (AttributeError, IndexError, KeyError, TypeError) as exc:
        raise ScanPrevizError(
            f"Entree structurellement incomplete ou malformee: {exc}"
        ) from exc

    counters = ScanPrevizCounters(
        pages_present=len(pages),
        # Cardinal, comme les trois cardinaux de frames: un « nombre de pages
        # attendues » negatif n'a pas de sens et passait pourtant (revue 5.8,
        # couche 2, finding 6). Le refus de confronter `pages_expected` a
        # `pages_present` reste entier -- c'est le lot melange, et il ne dit
        # rien sur le signe.
        pages_expected=(
            None
            if pages_expected_count is None
            else _require_cardinal(pages_expected_count, "pages_expected_count")
        ),
        frames_written=written,
        frames_expected=expected,
        synthetic_frame_count=synthetic_count,
    )

    return ScanPreviz(
        previz_schema_version=PREVIZ_SCHEMA_VERSION,
        kind=SCAN_PREVIZ_KIND,
        state=state,
        generated_at_utc=generated,
        subject=subject,
        counters=counters,
        pages=pages,
        warnings=ScanPrevizWarnings(
            ingest=ingest_warnings,
            detection=detection_warnings,
            output=output_warnings,
            # Tri: forme canonique stable quel que soit l'ordre cote appelant.
            # Aucun doublon possible, `caller_codes` etant deduplique et ne
            # pouvant pas porter LOT_INCOMPLETE.
            previz=tuple(sorted(caller_codes + _completude_codes(state, counters))),
        ),
        fingerprints=ScanPrevizFingerprints(
            detection=fingerprint_of(
                _detection_fingerprint_payload(subject, pages)
            ),
            selection=fingerprint,
        ),
    )


def _state_counters(
    state: str,
    *,
    output_report: LotOutputReportLike | None,
    frames_written_count: Any,
    frames_expected_count: Any,
    synthetic_frame_count: Any,
) -> tuple[int | None, int | None, int | None, str | None]:
    """Ce que chaque etat exige et ce qu'il interdit.

    Motif commun aux deux jumelles: un compteur constate n'a pas de sens avant
    que quoi que ce soit ait ete ecrit, et il est obligatoire apres.
    """
    if state == SCAN_PREVIZ_STATE_RECONSTRUCTED:
        if output_report is None:
            raise ScanPrevizError(
                "output_report est obligatoire en regime 'reconstructed': les "
                "frames ecrites se localisent"
            )
        for label, value in (
            ("frames_written_count", frames_written_count),
            ("synthetic_frame_count", synthetic_frame_count),
        ):
            if value is None:
                raise ScanPrevizError(
                    f"{label} est obligatoire en regime 'reconstructed' et doit "
                    "etre fourni par l'appelant: ce module ne compte jamais les "
                    "fichiers presents sur disque"
                )
        written = _require_cardinal(frames_written_count, "frames_written_count")
        synthetic = _require_cardinal(synthetic_frame_count, "synthetic_frame_count")
        # `frames_expected_count` peut legitimement valoir None: 5.6 declare le
        # cardinal attendu **indeterminable** quand aucune page n'a livre de
        # payload exploitable. Un lot dont l'attendu est inconnu n'est jamais
        # declare complet -- c'est la lecture du manifest (EPIC5-ARB-32).
        expected = (
            None
            if frames_expected_count is None
            else _require_cardinal(frames_expected_count, "frames_expected_count")
        )
        if expected is not None and written > expected:
            raise ScanPrevizError(
                f"frames_written_count ({written}) depasse le cardinal attendu "
                f"({expected}): un lot ne peut pas porter plus de frames que le "
                "lot n'en attend. Ce document se contredirait lui-meme (ARB-13)"
            )
        if synthetic > written:
            raise ScanPrevizError(
                f"synthetic_frame_count ({synthetic}) depasse le nombre de "
                f"frames ecrites ({written}): une frame de remplacement est une "
                "frame ecrite. Ce document se contredirait lui-meme"
            )
        output_dir = _relative_path(output_report.output_dir, "output_report.output_dir")
        return written, expected, synthetic, output_dir

    if output_report is not None:
        raise ScanPrevizError(
            "output_report n'a pas de sens en regime 'detected': aucune frame "
            "n'est encore ecrite"
        )
    for label, value in (
        ("frames_written_count", frames_written_count),
        ("frames_expected_count", frames_expected_count),
        ("synthetic_frame_count", synthetic_frame_count),
    ):
        if value is not None:
            raise ScanPrevizError(
                f"{label} n'a pas de sens en regime 'detected': aucune frame "
                f"n'est encore ecrite, recu {value!r}"
            )
    return None, None, None, None


def _completude_codes(state: str, counters: ScanPrevizCounters) -> tuple[str, ...]:
    """Deduire `LOT_INCOMPLETE`, seule exception a la purete d'emission.

    Regle du manifest, mot pour mot (EPIC5-ARB-32 clause 2, toujours en vigueur
    apres EPIC5-ARB-33): un lot est complet **si et seulement si** son cardinal
    attendu est determinable, que l'ecrit lui est egal et qu'aucune frame de
    remplacement n'y figure. La troisieme condition est celle que l'egalite des
    cardinaux ne couvre pas: le fichier existe, l'image du film non.

    En regime `detected` la question ne se pose pas -- aucune frame n'est
    ecrite, et emettre le code y ferait dire « lot incomplet » a un document qui
    ne parle pas encore de frames.
    """
    if state != SCAN_PREVIZ_STATE_RECONSTRUCTED:
        return ()
    complete = (
        counters.frames_expected is not None
        and counters.frames_written == counters.frames_expected
        and counters.synthetic_frame_count == 0
    )
    return () if complete else (LOT_INCOMPLETE,)


def _ingested_pages_by_rank(
    ingest: ScanIngestReportLike,
) -> dict[int, IngestedPageLike]:
    """Indexer les pages de 5.1 par rang de lecture.

    Un doublon de rang est refuse: le document ne saurait pas laquelle des deux
    pages il decrit, et il n'a aucun moyen de trancher.
    """
    by_rank: dict[int, IngestedPageLike] = {}
    for page in ingest.pages:
        rank = _require_int(page.read_rank, "ingest.pages[].read_rank")
        if rank in by_rank:
            raise ScanPrevizError(
                f"Le rapport d'ingestion porte deux pages de rang de lecture "
                f"{rank}: le document ne saurait pas laquelle il decrit"
            )
        by_rank[rank] = page
    return by_rank


def _frames_by_address(
    output_report: LotOutputReportLike | None,
) -> dict[tuple[int, int], OutputFrameLike]:
    """Indexer les frames ecrites de 5.6 par `(page_index, slot_index)`.

    C'est un **index**, pas une jointure calculee: l'adresse d'une frame est
    deja portee par le rapport. Un doublon d'adresse est refuse -- deux frames
    pour la meme zone rendraient le chemin publie arbitraire.
    """
    if output_report is None:
        return {}
    frames: dict[tuple[int, int], OutputFrameLike] = {}
    for frame in output_report.frames:
        address = (
            _require_int(frame.page_index, "output_report.frames[].page_index"),
            _require_int(frame.slot_index, "output_report.frames[].slot_index"),
        )
        if address in frames:
            raise ScanPrevizError(
                f"Le rapport d'ecriture porte deux frames a l'adresse "
                f"{address}: le chemin publie pour cette zone serait arbitraire"
            )
        frames[address] = frame
    return frames


def _require_every_written_frame_is_shown(
    frames_by_address: Mapping[tuple[int, int], OutputFrameLike],
    claimed_addresses: Mapping[tuple[int, int], int],
) -> None:
    """Toute frame ecrite doit avoir une zone ou se poser, ou le document ment.

    Quatrieme garde de la famille, ajoutee a la revue de 5.8 (couche 1 F1,
    couche 2 finding 2). Les trois voisines refusent deja exactement ce mode
    d'echec et le nomment: un rang inconnu d'un mapping (« serait
    silencieusement ignore »), une page ingeree jamais detectee (« elles
    seraient silencieusement absentes de la previz »), deux frames a la meme
    adresse (« le chemin publie pour cette zone serait arbitraire »). Une frame
    ecrite dont l'adresse `(page_index, slot_index)` ne retrouve aucune zone
    tombait dans la meme famille et n'etait pas gardee: elle disparaissait du
    document alors que le cardinal `frames_written` verse par l'appelant, lui,
    la comptait.

    Deux manifestations mesurees, toutes deux reproduites a la revue:

    * un lot dont 2 frames sur 3 sont introuvables sortait **complet** et sans
      un mot -- une interface d'edition (7.4) montrait un lot complet a une
      frame;
    * une page refusee sans plan de decoupe faisait annoncer deux mires ecrites
      sans en montrer une seule, c'est-a-dire l'inverse exact d'EPIC5-ARB-8:
      « l'operateur doit voir la mire, pas seulement la lire dans un compteur ».

    Symetriquement, une frame reclamee par **deux** zones est refusee: c'est le
    lot melange (deux pages declarant le meme `page_index`) rendu en regime
    `reconstructed`, ou le meme fichier serait publie deux fois. Le diagnostic
    du lot melange n'est pas perdu pour autant -- il se lit entier en regime
    `detected`, ou aucune frame n'est encore ecrite.
    """
    orphans = sorted(
        address for address in frames_by_address if address not in claimed_addresses
    )
    if orphans:
        raise ScanPrevizError(
            f"Des frames ecrites n'ont aucune zone ou se poser (adresses "
            f"(page_index, slot_index) {orphans}): elles seraient comptees par "
            "les cardinaux et invisibles dans le document, et une mire perdue "
            "de cette facon serait annoncee sans jamais etre montrable "
            "(EPIC5-ARB-8)"
        )
    shared = sorted(
        address for address, count in claimed_addresses.items() if count > 1
    )
    if shared:
        raise ScanPrevizError(
            f"Des frames ecrites sont reclamees par plusieurs zones (adresses "
            f"(page_index, slot_index) {shared}): le meme fichier serait publie "
            "sur deux zones, et l'interface ne saurait pas laquelle il decrit. "
            "Le lot melange se diagnostique en regime 'detected', ou aucune "
            "frame n'est encore ecrite"
        )


def _project_pages(
    detected_pages: Sequence[DetectedPageLike],
    *,
    ingested_by_rank: Mapping[int, IngestedPageLike],
    crop_plans: Mapping[int, PageCropPlanLike] | None,
    frames_by_address: Mapping[tuple[int, int], OutputFrameLike],
    claimed_addresses: dict[tuple[int, int], int],
    calibration_status: Mapping[int, str] | None,
    gamut_clipping: Mapping[int, bool] | None,
    page_payloads: Mapping[int, Mapping[str, Any]] | None,
    source_digests: Mapping[int, str] | None,
    synthetic_reason_vocabulary: Any,
    calibration_status_vocabulary: Any,
) -> tuple[ScanPrevizPage, ...]:
    """Projeter chaque page dans l'ordre de 5.2, valeurs verbatim."""
    ranks = [
        _require_int(page.read_rank, "detection.pages[].read_rank")
        for page in detected_pages
    ]
    known = frozenset(ranks)
    if len(known) != len(ranks):
        raise ScanPrevizError(
            "Le document de detection porte deux pages du meme rang de lecture: "
            "les adresses de page ne seraient plus uniques"
        )
    missing = sorted(known - set(ingested_by_rank))
    if missing:
        raise ScanPrevizError(
            f"Des pages detectees sont absentes du rapport d'ingestion (rangs "
            f"{missing}): leur format et leur profondeur ne sont pas dans le "
            "document de detection, et ce module ne les reconstitue pas"
        )
    orphans = sorted(set(ingested_by_rank) - known)
    if orphans:
        raise ScanPrevizError(
            f"Des pages ingerees sont absentes du document de detection (rangs "
            f"{orphans}): elles seraient silencieusement absentes de la previz, "
            "alors qu'une page ingeree et jamais detectee est exactement ce "
            "qu'une interface doit montrer"
        )
    plans = _mapping_by_rank(crop_plans, known, "crop_plans")
    statuses = _mapping_by_rank(calibration_status, known, "calibration_status")
    clippings = _mapping_by_rank(gamut_clipping, known, "gamut_clipping")
    payloads = _mapping_by_rank(page_payloads, known, "page_payloads")
    digests = _mapping_by_rank(source_digests, known, "source_digests")

    pages: list[ScanPrevizPage] = []
    for page in detected_pages:
        rank = _require_int(page.read_rank, "detection.pages[].read_rank")
        ingested = ingested_by_rank[rank]
        page_index = _optional_int(page.page_index, f"pages[{rank}].page_index")
        pages.append(
            ScanPrevizPage(
                read_rank=rank,
                page_index=page_index,
                page_count=_optional_int(page.page_count, f"pages[{rank}].page_count"),
                status=_require_text(page.status, f"pages[{rank}].status"),
                qr_status=_require_text(page.qr_status, f"pages[{rank}].qr_status"),
                refusal_reason=_optional_text(
                    page.refusal_reason, f"pages[{rank}].refusal_reason"
                ),
                # Le code voyage a cote de la phrase, du coeur au document
                # (story 5.27): meme controle de forme, meme adresse d'erreur.
                refusal_code=_code_de_refus(
                    page.refusal_code, f"pages[{rank}].refusal_code"
                ),
                source_path_relative=_relative_path(
                    page.locator_source, f"pages[{rank}].locator_source"
                ),
                source_page_index=_optional_int(
                    page.locator_page_index, f"pages[{rank}].locator_page_index"
                ),
                scan_input_format=_require_text(
                    ingested.scan_input_format, f"pages[{rank}].scan_input_format"
                ),
                source_bit_depth=_require_int(
                    ingested.source_bit_depth, f"pages[{rank}].source_bit_depth"
                ),
                width_px=_require_int(ingested.width_px, f"pages[{rank}].width_px"),
                height_px=_require_int(ingested.height_px, f"pages[{rank}].height_px"),
                channels=_require_int(ingested.channels, f"pages[{rank}].channels"),
                decoded_project_id=_optional_text(
                    page.project_id, f"pages[{rank}].project_id"
                ),
                decoded_rush_id=_optional_text(page.rush_id, f"pages[{rank}].rush_id"),
                decoded_lot_id=_optional_text(page.lot_id, f"pages[{rank}].lot_id"),
                decoded_gamut_map_id=_optional_text(
                    page.gamut_map_id, f"pages[{rank}].gamut_map_id"
                ),
                template_id=_optional_text(
                    page.template_id, f"pages[{rank}].template_id"
                ),
                template_source=_optional_text(
                    page.template_source, f"pages[{rank}].template_source"
                ),
                page_size_px=_page_size_px(page.page_size_px, rank),
                homography=_homography(page.homography, rank),
                scale=_page_scale(page.scale, rank),
                corner_markers=_corner_markers(page.corner_centers, rank),
                foreign_markers=_foreign_markers(page.foreign_markers, rank),
                frame_zones=_frame_zones(
                    plans.get(rank),
                    zone_rects_px=_zone_rects_px(page.frame_zones_px, rank),
                    page_index=page_index,
                    frames_by_address=frames_by_address,
                    claimed_addresses=claimed_addresses,
                    rank=rank,
                    synthetic_reason_vocabulary=synthetic_reason_vocabulary,
                ),
                calibration=_page_calibration(
                    statuses.get(rank),
                    clippings.get(rank),
                    rank,
                    calibration_status_vocabulary=calibration_status_vocabulary,
                ),
                warnings=_codes(page.warnings, f"pages[{rank}].warnings"),
                payload=_page_payload(payloads.get(rank), rank, page_index),
                source_digest=(
                    None
                    if digests.get(rank) is None
                    else _require_text(
                        digests[rank], f"pages[{rank}].source_digest"
                    )
                ),
            )
        )
    return tuple(pages)


#: Champs du payload accedes **positionnellement** (`payload["..."]`, sans
#: `.get` ni capture) par la moitie aval de l'ecriture
#: (`_scanned_pages_for_output`, `_ecrire_le_lot_detecte`, `_page_identifier`
#: dans `cli.py`). Un mapping qui en omettrait un traverserait la
#: construction du document puis ferait echouer l'ecriture bien plus loin,
#: par une `KeyError` brute -- revue de 5.26, trouve independamment par le
#: Blind Hunter et l'Edge Case Hunter. Ce n'est PAS le schema complet du
#: payload (`io.payload._REQUIRED_SCALAR_FIELDS`, qui reste hors perimetre
#: AC 7): seuls les champs dont l'absence casserait nommement ce module.
_PAYLOAD_REQUIRED_FIELDS: tuple[str, ...] = (
    "page_index",
    "page_role",
    "template_id",
    "patch_preset_id",
    "slots",
)


def _page_payload(
    value: Any, rank: int, page_index: int | None
) -> Mapping[str, Any] | None:
    """Le payload decode d'une page, transporte **verbatim** (story 5.26).

    La nature de l'objet est controlee (un mapping), ainsi que la presence
    des champs de `_PAYLOAD_REQUIRED_FIELDS` -- le contenu de chacun n'est ni
    valide, ni complete, ni re-decode au-dela: le vocabulaire complet du
    payload appartient a `io/payload`, qui l'a deja valide au decodage (H4).
    Une chaine ou une liste glissee ici serait publiee sous un champ dit
    objet, donc refusee.

    `payload["page_index"]` doit en outre coincider avec le `page_index` de
    la page qui le porte (revue 5.26, Edge Case Hunter): un payload qui
    designerait une autre page que celle qui le transporte romprait
    l'appariement page <-> payload dont toute la moitie aval depend.
    """
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ScanPrevizError(
            f"pages[{rank}].payload doit etre le payload decode (objet), recu "
            f"{value!r}"
        )
    missing = [field for field in _PAYLOAD_REQUIRED_FIELDS if field not in value]
    if missing:
        raise ScanPrevizError(
            f"pages[{rank}].payload omet le(s) champ(s) requis "
            f"{missing}: l'ecriture y accede sans repli, une KeyError brute "
            "suivrait bien plus loin"
        )
    if value["page_index"] != page_index:
        raise ScanPrevizError(
            f"pages[{rank}].payload['page_index'] ({value['page_index']!r}) "
            f"contredit pages[{rank}].page_index ({page_index!r}): le "
            "payload transporte verbatim doit designer la meme page que "
            "l'adresse qui le porte"
        )
    return value


def _mapping_by_rank(
    values: Any, ranks: frozenset[int], label: str
) -> Mapping[int, Any]:
    """Mapping indexe par rang de lecture, dont aucune cle n'est ignoree.

    Motif de 3.5: un rang inconnu serait silencieusement ignore, et l'appelant
    croirait avoir fourni une donnee que le document ne porte pas.

    Les cles sont de vrais entiers, `bool` exclu. La garde d'appartenance seule
    ne suffit pas: `0.0 == 0` et les deux ont le meme hash, donc `{0.0: plan}`
    traversait `rank not in ranks` et le mapping repondait a `.get(0)` (revue
    5.8, couche 2, finding 13). Le refus de `{True: plan}` ne venait alors pas
    d'une garde de type mais du hasard de `frozenset({0})` qui ne contient pas
    `1` -- sur un lot de deux pages, `True` aurait vise la page de rang 1.
    """
    if values is None:
        return {}
    if not isinstance(values, Mapping):
        raise ScanPrevizError(
            f"{label} doit etre un mapping read_rank -> valeur, recu {values!r}"
        )
    for rank in values:
        _require_int(rank, f"{label}: cle de rang de lecture")
    unknown = sorted(rank for rank in values if rank not in ranks)
    if unknown:
        raise ScanPrevizError(
            f"{label} designe des rangs absents du document de detection: "
            f"{unknown}. Un rang inconnu serait silencieusement ignore"
        )
    return values


def _page_size_px(value: Any, rank: int) -> tuple[int, ...] | None:
    if value is None:
        return None
    items = tuple(value)
    if len(items) != 2:
        raise ScanPrevizError(
            f"pages[{rank}].page_size_px doit porter (largeur, hauteur), recu "
            f"{value!r}"
        )
    return tuple(
        _require_int(item, f"pages[{rank}].page_size_px[{i}]")
        for i, item in enumerate(items)
    )


def _homography(value: Any, rank: int) -> tuple[float, ...] | None:
    """Les neuf coefficients, transportes **verbatim**.

    Question ouverte 2 de la story: ce sont des flottants dont la
    reproductibilite bit-a-bit entre versions d'OpenCV n'est pas garantie. La
    reponse suit celle de 5.2 -- precision d'arrondi **declaree** par le
    producteur (`scan_detection.DOCUMENT_FLOAT_PRECISION`), et exclusion des
    champs d'empreinte. Arrondir ici serait un calcul, et un arrondi different
    de celui de 5.2 ferait diverger deux documents sur la meme detection.
    """
    if value is None:
        return None
    items = tuple(value)
    if len(items) != 9:
        raise ScanPrevizError(
            f"pages[{rank}].homography doit porter 9 coefficients, recu {value!r}"
        )
    return tuple(
        _require_number(item, f"pages[{rank}].homography[{i}]")
        for i, item in enumerate(items)
    )


def _page_scale(value: Any, rank: int) -> PrevizPageScale | None:
    if value is None:
        return None
    return PrevizPageScale(
        scale_x=_require_number(value.scale_x, f"pages[{rank}].scale.scale_x"),
        scale_y=_require_number(value.scale_y, f"pages[{rank}].scale.scale_y"),
        residual_px=_require_number(
            value.residual_px, f"pages[{rank}].scale.residual_px"
        ),
    )


def _corner_markers(values: Any, rank: int) -> tuple[PrevizCornerMarker, ...]:
    markers: list[PrevizCornerMarker] = []
    for position, corner in enumerate(values):
        items = tuple(corner)
        if len(items) != 3:
            raise ScanPrevizError(
                f"pages[{rank}].corner_centers[{position}] doit porter "
                f"(marker_id, x, y), recu {corner!r}"
            )
        markers.append(
            PrevizCornerMarker(
                marker_id=_require_int(
                    items[0], f"pages[{rank}].corner_centers[{position}].marker_id"
                ),
                center_x_px=_require_number(
                    items[1], f"pages[{rank}].corner_centers[{position}].x"
                ),
                center_y_px=_require_number(
                    items[2], f"pages[{rank}].corner_centers[{position}].y"
                ),
            )
        )
    return tuple(markers)


def _foreign_markers(values: Any, rank: int) -> tuple[PrevizForeignMarker, ...]:
    return tuple(
        PrevizForeignMarker(
            marker_id=_require_int(
                marker.marker_id, f"pages[{rank}].foreign_markers[].marker_id"
            ),
            role=_require_text(marker.role, f"pages[{rank}].foreign_markers[].role"),
        )
        for marker in values
    )


def _zone_rects_px(values: Any, rank: int) -> dict[str, Mapping[str, Any]]:
    """Indexer les rectangles de zone en pixels de 5.2 par nom de zone.

    Simple indexation d'un champ deja produit par 5.2, jamais un recalcul
    depuis les millimetres: la convention de quantification de `frame_zones_px`
    arrondit l'origine et la taille **separement**, si bien qu'un bord
    recalcule depuis les millimetres peut differer d'un pixel (mesure par 5.2:
    54 zones sur 135 a 600 ppp).

    Un doublon de nom est refuse, comme dans les deux autres index du fichier
    (`_ingested_pages_by_rank`, `_frames_by_address`): sans cette garde le
    dernier rectangle gagnait et le premier etait perdu sans un mot (revue 5.8,
    couche 1 F5, couche 2 finding 9). La source (`resolve_page_geometry`) derive
    les noms d'un gabarit et ne devrait pas produire de doublon -- mais le
    module accepte n'importe quel fournisseur du protocole, et c'est exactement
    l'argument qui a fait ajouter les deux autres gardes.
    """
    rects: dict[str, Mapping[str, Any]] = {}
    for zone in values:
        name = _require_text(zone["name"], f"pages[{rank}].frame_zones_px[].name")
        if name in rects:
            raise ScanPrevizError(
                f"pages[{rank}].frame_zones_px porte deux zones nommees "
                f"{name!r}: le rectangle publie pour cette zone serait "
                "arbitraire"
            )
        rects[name] = zone
    return rects


def _frame_zones(
    plan: PageCropPlanLike | None,
    *,
    zone_rects_px: Mapping[str, Mapping[str, Any]],
    page_index: int | None,
    frames_by_address: Mapping[tuple[int, int], OutputFrameLike],
    claimed_addresses: dict[tuple[int, int], int],
    rank: int,
    synthetic_reason_vocabulary: Any,
) -> tuple[PrevizFrameZone, ...]:
    """Projeter les zones d'une page depuis le plan de decoupe de 5.3.

    Une page sans plan (detection refusee, decoupe impossible) rend une page
    **sans zone**: elle manque, et le module ne la reconstitue pas. Les frames
    ecrites que cette page-la aurait dues porter ne disparaissent pas pour
    autant: elles restent non reclamees et
    :func:`_require_every_written_frame_is_shown` les refuse.

    `claimed_addresses` compte, par adresse `(page_index, slot_index)`, les
    zones qui reclament une frame ecrite. C'est un compteur et non un ensemble,
    parce que les deux anomalies se lisent dessus: zero reclamation pour une
    frame ecrite, et plus d'une reclamation pour la meme frame.
    """
    if plan is None:
        return ()
    zones: list[PrevizFrameZone] = []
    seen_slots: set[int] = set()
    for frame in plan.frames:
        slot_index = _require_int(
            frame.slot_index, f"pages[{rank}].crop_plan.frames[].slot_index"
        )
        # `(read_rank, page_index, slot_index)` est l'adresse la plus fine du
        # document -- celle par laquelle 7.4 dira « la zone 2 de la page 3 est
        # mal placee ». C'etait la seule des trois natures adressables dont
        # l'unicite n'etait pas gardee (revue 5.8, couche 2, finding 10), alors
        # que `_project_pages` refuse deux pages du meme rang au motif que
        # « les adresses de page ne seraient plus uniques ».
        if slot_index in seen_slots:
            raise ScanPrevizError(
                f"Le plan de decoupe de la page de rang {rank} porte deux "
                f"emplacements d'index {slot_index}: deux zones du document "
                "porteraient la meme adresse, et une correction de 7.4 ne "
                "saurait pas laquelle elle vise"
            )
        seen_slots.add(slot_index)
        label = f"pages[{rank}].slots[{slot_index}]"
        zone_rect = _require_rect_mm(frame.zone_rect_mm, f"{label}.zone_rect_mm")
        crop_rect = _require_rect_mm(frame.image_rect_mm, f"{label}.image_rect_mm")
        zone_name = _require_text(frame.zone_name, f"{label}.zone_name")
        zone_px = zone_rects_px.get(zone_name)
        written = None
        if page_index is not None:
            address = (page_index, slot_index)
            written = frames_by_address.get(address)
            if written is not None:
                claimed_addresses[address] = claimed_addresses.get(address, 0) + 1
        zones.append(
            PrevizFrameZone(
                slot_index=slot_index,
                frame_timecode=_optional_text(
                    frame.frame_timecode, f"{label}.frame_timecode"
                ),
                zone_name=zone_name,
                zone_x_mm=zone_rect[0],
                zone_y_mm=zone_rect[1],
                zone_w_mm=zone_rect[2],
                zone_h_mm=zone_rect[3],
                crop_x_mm=crop_rect[0],
                crop_y_mm=crop_rect[1],
                crop_w_mm=crop_rect[2],
                crop_h_mm=crop_rect[3],
                crop_x_px=_require_int(frame.crop_x_px, f"{label}.crop_x_px"),
                crop_y_px=_require_int(frame.crop_y_px, f"{label}.crop_y_px"),
                crop_w_px=_require_int(frame.width_px, f"{label}.width_px"),
                crop_h_px=_require_int(frame.height_px, f"{label}.height_px"),
                zone_x_px=(
                    None
                    if zone_px is None
                    else _require_int(zone_px["x"], f"{label}.zone_rect_px.x")
                ),
                zone_y_px=(
                    None
                    if zone_px is None
                    else _require_int(zone_px["y"], f"{label}.zone_rect_px.y")
                ),
                zone_w_px=(
                    None
                    if zone_px is None
                    else _require_int(zone_px["width"], f"{label}.zone_rect_px.width")
                ),
                zone_h_px=(
                    None
                    if zone_px is None
                    else _require_int(zone_px["height"], f"{label}.zone_rect_px.height")
                ),
                frame_path_relative=(
                    None
                    if written is None
                    else _relative_path(written.path, f"{label}.frame_path")
                ),
                # `synthetic` accompagne le chemin, `false` compris: c'est
                # l'invariant d'EPIC5-ARB-8, verrouille par `__post_init__`.
                #
                # `_require_bool` et non `bool(...)`: la coercition acceptait
                # tout et desamorcait la garde de `__post_init__` avant qu'elle
                # ne voie la valeur (revue 5.8, couche 2, finding 5). Le cas
                # couteux etait `synthetic=None` chez le producteur -- un
                # drapeau **omis** se rendait `false`, c'est-a-dire « vraie
                # frame », mot pour mot ce que le piege 8 interdit.
                synthetic=(
                    None
                    if written is None
                    else _require_bool(written.synthetic, f"{label}.synthetic")
                ),
                synthetic_reason=(
                    _known_value(
                        _require_text(
                            written.synthetic_reason, f"{label}.synthetic_reason"
                        ),
                        synthetic_reason_vocabulary,
                        f"{label}.synthetic_reason",
                    )
                    if written is not None and written.synthetic
                    else None
                ),
            )
        )
    return tuple(zones)


def _page_calibration(
    status: Any,
    clipping: Any,
    rank: int,
    *,
    calibration_status_vocabulary: Any = None,
) -> PrevizPageCalibration | None:
    """Etat de calibration d'une page, verdict d'ecretage compris s'il existe.

    Un verdict d'ecretage sans statut de calibration est refuse: le verdict
    appartient a la calibration, et le publier seul ferait croire qu'une mesure
    a eu lieu hors de tout cadre. L'inverse est normal -- c'est le regime du
    MVP, ou le statut vaut `not_applied` et ou rien n'est mesure.
    """
    if status is None:
        if clipping is not None:
            raise ScanPrevizError(
                f"pages[{rank}]: un verdict d'ecretage est fourni sans statut de "
                "calibration. Le verdict est une mesure de la calibration; le "
                "publier seul laisserait croire qu'une mesure a eu lieu hors de "
                "tout cadre"
            )
        return None
    if clipping is not None and not isinstance(clipping, bool):
        raise ScanPrevizError(
            f"pages[{rank}].gamut_clipping doit etre un booleen ou absent, recu "
            f"{clipping!r}"
        )
    return PrevizPageCalibration(
        status=_known_value(
            _require_text(status, f"pages[{rank}].calibration_status"),
            calibration_status_vocabulary,
            f"pages[{rank}].calibration_status",
        ),
        clipping_detected=clipping,
    )


def _detection_fingerprint_payload(
    subject: ScanPrevizSubject, pages: Sequence[ScanPrevizPage]
) -> dict[str, Any]:
    """Les entrees de decision de la detection, et rien d'autre.

    Ni les avertissements, ni le verdict d'ecretage, ni le drapeau synthetique:
    une empreinte sensible a une constatation signalerait des peremptions
    imaginaires. `gamut_map_id` y entre **sans condition** -- c'est le trou que
    5.10 avait trouve cote impression.
    """
    payload = {
        "gamut_map_id": subject.gamut_map_id,
        "ingested_pages_digest": fingerprint_of(
            [_ingested_page_digest_entry(page) for page in pages]
        ),
        "lot_id": subject.lot_id,
        "project_id": subject.project_id,
        "rush_id": subject.rush_id,
        "scan_dpi_declared": subject.scan_dpi_declared,
        "scan_dpi_detection": subject.scan_dpi_detection,
        "template_id": subject.template_id,
    }
    # Garde-fou de contrat, pas un calcul: le payload ne peut ni porter un champ
    # absent de la constante exportee, ni en omettre un.
    if tuple(sorted(payload)) != DETECTION_FINGERPRINT_FIELDS:
        raise ScanPrevizError(
            "Le payload d'empreinte de detection diverge de "
            f"DETECTION_FINGERPRINT_FIELDS (recu {sorted(payload)}, attendu "
            f"{list(DETECTION_FINGERPRINT_FIELDS)})"
        )
    return payload


def _ingested_page_digest_entry(page: ScanPrevizPage) -> dict[str, Any]:
    """Ce qu'une page apporte a `ingested_pages_digest`.

    Provenance **mixte** et assumee: six champs de 5.1, plus
    `source_path_relative` et `source_page_index` qui viennent du locator de
    5.2. Voir :data:`INGESTED_PAGE_DIGEST_FIELDS`. Les valeurs sont celles que
    le document **publie**, ce qui est la seule facon qu'une empreinte scelle
    ce qu'elle montre.
    """
    entry = {
        "channels": page.channels,
        "height_px": page.height_px,
        "read_rank": page.read_rank,
        "scan_input_format": page.scan_input_format,
        "source_bit_depth": page.source_bit_depth,
        "source_page_index": page.source_page_index,
        "source_path_relative": page.source_path_relative,
        "width_px": page.width_px,
    }
    if tuple(sorted(entry)) != INGESTED_PAGE_DIGEST_FIELDS:
        raise ScanPrevizError(
            "L'entree de condensat de page diverge de "
            f"INGESTED_PAGE_DIGEST_FIELDS (recu {sorted(entry)}, attendu "
            f"{list(INGESTED_PAGE_DIGEST_FIELDS)})"
        )
    return entry


# --------------------------------------------------------------------------
# Serialisation
# --------------------------------------------------------------------------


def _page_address(page: ScanPrevizPage) -> dict[str, Any]:
    return {"read_rank": page.read_rank, "page_index": page.page_index}


def _zone_to_json_dict(page: ScanPrevizPage, zone: PrevizFrameZone) -> dict[str, Any]:
    document: dict[str, Any] = {
        "address": {**_page_address(page), "slot_index": zone.slot_index},
        "slot_index": zone.slot_index,
        "frame_timecode": zone.frame_timecode,
        "zone_name": zone.zone_name,
        "zone_rect_mm": {
            "x": zone.zone_x_mm,
            "y": zone.zone_y_mm,
            "width": zone.zone_w_mm,
            "height": zone.zone_h_mm,
        },
        "crop_rect_mm": {
            "x": zone.crop_x_mm,
            "y": zone.crop_y_mm,
            "width": zone.crop_w_mm,
            "height": zone.crop_h_mm,
        },
        "crop_rect_px": {
            "x": zone.crop_x_px,
            "y": zone.crop_y_px,
            "width": zone.crop_w_px,
            "height": zone.crop_h_px,
        },
        "frame_path_relative": zone.frame_path_relative,
    }
    if zone.zone_x_px is not None:
        document["zone_rect_px"] = {
            "x": zone.zone_x_px,
            "y": zone.zone_y_px,
            "width": zone.zone_w_px,
            "height": zone.zone_h_px,
        }
    # Le drapeau accompagne le chemin, `false` compris (EPIC5-ARB-8, piege 8):
    # le regime « champ optionnel omis » ne s'y applique pas.
    if zone.synthetic is not None:
        document["synthetic"] = zone.synthetic
    if zone.synthetic_reason is not None:
        document["synthetic_reason"] = zone.synthetic_reason
    return document


def _calibration_to_json_dict(calibration: PrevizPageCalibration) -> dict[str, Any]:
    document: dict[str, Any] = {"status": calibration.status}
    # Verdict d'ecretage: present, il passe verbatim; absent, il est **omis**,
    # jamais `null` et surtout jamais remplace par un verdict negatif.
    if calibration.clipping_detected is not None:
        document["clipping_detected"] = calibration.clipping_detected
    return document


def _page_to_json_dict(page: ScanPrevizPage) -> dict[str, Any]:
    address = _page_address(page)
    document = {
        "address": address,
        "read_rank": page.read_rank,
        "page_index": page.page_index,
        "page_count": page.page_count,
        "status": page.status,
        "qr_status": page.qr_status,
        "refusal_reason": page.refusal_reason,
        # Emis **toujours**, `null` compris, exactement comme la phrase qu'il
        # accompagne (story 5.27) -- et non en emission conditionnelle comme
        # `payload` et `source_digest`: pour ces deux-la l'absence de la cle est
        # une valeur distincte de `null` (une page mutique omet, elle ne vide
        # pas), tandis qu'un code de refus n'a qu'une seule facon de manquer.
        # Le couple phrase + code se lit donc a la meme adresse, dans les deux
        # cas, sous la cle que `gui.lecture_detection.CLE_CODE_DE_REFUS` nomme.
        "refusal_code": page.refusal_code,
        "source": {
            "path_relative": page.source_path_relative,
            "page_index": page.source_page_index,
            "scan_input_format": page.scan_input_format,
            "source_bit_depth": page.source_bit_depth,
            "width_px": page.width_px,
            "height_px": page.height_px,
            "channels": page.channels,
        },
        "decoded_identity": {
            "project_id": page.decoded_project_id,
            "rush_id": page.decoded_rush_id,
            "lot_id": page.decoded_lot_id,
            "gamut_map_id": page.decoded_gamut_map_id,
        },
        "template_id": page.template_id,
        "template_source": page.template_source,
        "page_size_px": (
            None if page.page_size_px is None else list(page.page_size_px)
        ),
        "homography": (
            None if page.homography is None else list(page.homography)
        ),
        "scale": (
            None
            if page.scale is None
            else {
                "scale_x": page.scale.scale_x,
                "scale_y": page.scale.scale_y,
                "residual_px": page.scale.residual_px,
            }
        ),
        "corner_markers": [
            {
                "address": {**address, "marker_id": marker.marker_id},
                "marker_id": marker.marker_id,
                "center_x_px": marker.center_x_px,
                "center_y_px": marker.center_y_px,
            }
            for marker in page.corner_markers
        ],
        "foreign_markers": [
            {
                "address": {**address, "marker_id": marker.marker_id},
                "marker_id": marker.marker_id,
                "role": marker.role,
            }
            for marker in page.foreign_markers
        ],
        "frame_zones": [_zone_to_json_dict(page, zone) for zone in page.frame_zones],
        "calibration": (
            None
            if page.calibration is None
            else _calibration_to_json_dict(page.calibration)
        ),
        "warnings": list(page.warnings),
    }
    # Champs additifs de la story 5.26, emission **conditionnelle** (meme
    # discipline que le drapeau `synthetic` et le verdict d'ecretage): presents
    # quand ils existent, **omis** sinon -- jamais `null`. Un document de 5.25
    # rendu par ce module reste donc octet pour octet celui d'avant la story.
    if page.payload is not None:
        document["payload"] = page.payload
    if page.source_digest is not None:
        document["source_digest"] = page.source_digest
    return document


def scan_previz_to_json_dict(previz: ScanPreviz) -> dict[str, Any]:
    """Forme JSON **normative** du document, deterministe et serialisable.

    Nom volontairement distinct de `extraction_previz.previz_to_json_dict`, sur
    le motif de `pdf_previz.pdf_previz_to_json_dict`: l'homonymie est
    exactement ce qu'ARB-14 a du resorber une fois.

    Aucun objet Python non JSON, aucune `Fraction` nue, aucun octet d'image,
    aucun base64. Passer le resultat a `previz_common.canonical_json` produit la
    meme chaine octet pour octet d'un processus a l'autre.
    """
    return {
        **envelope_head(
            schema_version=previz.previz_schema_version,
            kind=previz.kind,
            state=previz.state,
            generated_at_utc=previz.generated_at_utc,
        ),
        "subject": {
            "project_id": previz.subject.project_id,
            "rush_id": previz.subject.rush_id,
            "lot_id": previz.subject.lot_id,
            "ingest_slug": previz.subject.ingest_slug,
            "template_id": previz.subject.template_id,
            "gamut_map_id": previz.subject.gamut_map_id,
            "fps_target_exact": previz.subject.fps_target_exact,
            "target_colorspace": previz.subject.target_colorspace,
            "patch_preset_id": previz.subject.patch_preset_id,
            "scan_dpi_declared": previz.subject.scan_dpi_declared,
            "scan_dpi_detection": previz.subject.scan_dpi_detection,
            "scans_dir_relative": previz.subject.scans_dir_relative,
            "output_dir_relative": previz.subject.output_dir_relative,
        },
        "counters": {
            "pages_present": previz.counters.pages_present,
            "pages_expected": previz.counters.pages_expected,
            "frames_written": previz.counters.frames_written,
            "frames_expected": previz.counters.frames_expected,
            "synthetic_frame_count": previz.counters.synthetic_frame_count,
        },
        "pages": [_page_to_json_dict(page) for page in previz.pages],
        "warnings": {
            "ingest": list(previz.warnings.ingest),
            "detection": list(previz.warnings.detection),
            "output": list(previz.warnings.output),
            "previz": list(previz.warnings.previz),
        },
        "fingerprints": {
            "detection": previz.fingerprints.detection,
            "selection": previz.fingerprints.selection,
        },
    }


# --------------------------------------------------------------------------
# Relecture (story 5.26): la forme normative dans les deux sens
# --------------------------------------------------------------------------
#
# `scan_previz_to_json_dict` rend la forme normative; ce lecteur la relit et
# **valide** ce que `build_scan_previz` valide a la construction -- il ne
# recalcule rien, ne complete rien, ne corrige rien. Deux valeurs incoherentes
# ressortent en `ScanPrevizError`, jamais en reparation: c'est toute la
# difference entre « document altere refuse » et « document altere devine ».
#
# Les cles inconnues sont ignorees (lecture par protocole, comme partout dans
# la famille); une cle **attendue** absente est un refus nomme -- l'acces est
# direct, jamais un `get` avec repli (revue 5.8: un repli relit « valeur par
# defaut » ce qui devait tomber en refus). Les champs a emission
# conditionnelle (`payload`, `source_digest`, `zone_rect_px`, `synthetic`,
# `synthetic_reason`, `clipping_detected`) sont les seuls dont l'absence est
# une valeur.
#
# `refusal_code` (story 5.27) est le seul cas d'une **troisieme** espece: ce
# module l'emet toujours, `null` compris, mais tolere son absence a la lecture
# parce qu'un document ecrit **avant** cette story ne peut pas le porter. La
# tolerance est donc bornee dans le passe, et non l'expression d'une valeur
# absente legitime chez un producteur a jour.


def _read_field(mapping: Any, key: str, label: str) -> Any:
    """Une cle attendue du document; son absence est un refus nomme."""
    if not isinstance(mapping, Mapping):
        raise ScanPrevizError(
            f"{label} doit etre un objet JSON, recu {mapping!r}"
        )
    if key not in mapping:
        raise ScanPrevizError(
            f"{label}: champ '{key}' absent du document. Ce fichier n'est pas "
            "un document de previz de scan complet"
        )
    return mapping[key]


def _read_sequence(value: Any, label: str) -> tuple:
    """Une liste JSON, jamais une chaine ni un objet."""
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ScanPrevizError(
            f"{label} doit etre une liste, recu {value!r}"
        )
    return tuple(value)


def _read_scale(value: Any, rank: int) -> PrevizPageScale | None:
    if value is None:
        return None
    label = f"pages[{rank}].scale"
    return PrevizPageScale(
        scale_x=_require_number(_read_field(value, "scale_x", label), f"{label}.scale_x"),
        scale_y=_require_number(_read_field(value, "scale_y", label), f"{label}.scale_y"),
        residual_px=_require_number(
            _read_field(value, "residual_px", label), f"{label}.residual_px"
        ),
    )


def _read_rect_px(value: Any, label: str) -> tuple[int, int, int, int]:
    return (
        _require_int(_read_field(value, "x", label), f"{label}.x"),
        _require_int(_read_field(value, "y", label), f"{label}.y"),
        _require_int(_read_field(value, "width", label), f"{label}.width"),
        _require_int(_read_field(value, "height", label), f"{label}.height"),
    )


def _read_rect_mm(value: Any, label: str) -> tuple:
    return (
        _require_number(_read_field(value, "x", label), f"{label}.x"),
        _require_number(_read_field(value, "y", label), f"{label}.y"),
        _require_number(_read_field(value, "width", label), f"{label}.width"),
        _require_number(_read_field(value, "height", label), f"{label}.height"),
    )


def _read_address(value: Any, expected: Mapping[str, Any], label: str) -> None:
    """L'adresse publiee doit redire les champs qu'elle duplique.

    L'adresse est la seule redondance du document (frontiere 7.4): une adresse
    qui contredirait les champs de son porteur enverrait une correction sur le
    mauvais element. Refus, jamais reparation.
    """
    for key, expected_value in expected.items():
        if _read_field(value, key, label) != expected_value:
            raise ScanPrevizError(
                f"{label} contredit son porteur: address.{key}="
                f"{value[key]!r} pour une valeur portee {expected_value!r}"
            )


def _read_frame_zone(value: Any, rank: int, page_index: Any) -> PrevizFrameZone:
    slot_index = _require_int(
        _read_field(value, "slot_index", f"pages[{rank}].frame_zones[]"),
        f"pages[{rank}].frame_zones[].slot_index",
    )
    label = f"pages[{rank}].slots[{slot_index}]"
    _read_address(
        _read_field(value, "address", label),
        {"read_rank": rank, "page_index": page_index, "slot_index": slot_index},
        f"{label}.address",
    )
    zone_rect = _read_rect_mm(_read_field(value, "zone_rect_mm", label), f"{label}.zone_rect_mm")
    crop_rect = _read_rect_mm(_read_field(value, "crop_rect_mm", label), f"{label}.crop_rect_mm")
    crop_px = _read_rect_px(_read_field(value, "crop_rect_px", label), f"{label}.crop_rect_px")
    # Emission conditionnelle: le rectangle de zone en pixels est present en
    # bloc ou absent en bloc -- la garde de `PrevizFrameZone.__post_init__`
    # revalide l'invariant sur ce que le fichier porte reellement.
    zone_px: tuple = (None, None, None, None)
    if "zone_rect_px" in value:
        zone_px = _read_rect_px(value["zone_rect_px"], f"{label}.zone_rect_px")
    return PrevizFrameZone(
        slot_index=slot_index,
        frame_timecode=_optional_text(
            _read_field(value, "frame_timecode", label), f"{label}.frame_timecode"
        ),
        zone_name=_require_text(
            _read_field(value, "zone_name", label), f"{label}.zone_name"
        ),
        zone_x_mm=zone_rect[0],
        zone_y_mm=zone_rect[1],
        zone_w_mm=zone_rect[2],
        zone_h_mm=zone_rect[3],
        crop_x_mm=crop_rect[0],
        crop_y_mm=crop_rect[1],
        crop_w_mm=crop_rect[2],
        crop_h_mm=crop_rect[3],
        crop_x_px=crop_px[0],
        crop_y_px=crop_px[1],
        crop_w_px=crop_px[2],
        crop_h_px=crop_px[3],
        zone_x_px=zone_px[0],
        zone_y_px=zone_px[1],
        zone_w_px=zone_px[2],
        zone_h_px=zone_px[3],
        frame_path_relative=_optional_relative_path(
            _read_field(value, "frame_path_relative", label),
            f"{label}.frame_path_relative",
        ),
        # `synthetic` et `synthetic_reason` sont a emission conditionnelle: leur
        # **absence** vaut `None`, et c'est `__post_init__` qui revalide la
        # coherence drapeau <-> chemin <-> motif (EPIC5-ARB-8) sur le fichier.
        synthetic=(
            _require_bool(value["synthetic"], f"{label}.synthetic")
            if "synthetic" in value
            else None
        ),
        synthetic_reason=(
            _require_text(value["synthetic_reason"], f"{label}.synthetic_reason")
            if "synthetic_reason" in value
            else None
        ),
    )


def _read_page(value: Any, position: int) -> ScanPrevizPage:
    rank = _require_int(
        _read_field(value, "read_rank", f"pages[{position}]"),
        f"pages[{position}].read_rank",
    )
    page_index = _optional_int(
        _read_field(value, "page_index", f"pages[{rank}]"), f"pages[{rank}].page_index"
    )
    _read_address(
        _read_field(value, "address", f"pages[{rank}]"),
        {"read_rank": rank, "page_index": page_index},
        f"pages[{rank}].address",
    )
    source = _read_field(value, "source", f"pages[{rank}]")
    source_label = f"pages[{rank}].source"
    identity = _read_field(value, "decoded_identity", f"pages[{rank}]")
    identity_label = f"pages[{rank}].decoded_identity"
    page_size = _read_field(value, "page_size_px", f"pages[{rank}]")
    homography = _read_field(value, "homography", f"pages[{rank}]")
    calibration_value = _read_field(value, "calibration", f"pages[{rank}]")
    calibration = None
    if calibration_value is not None:
        calibration = _page_calibration(
            _read_field(
                calibration_value, "status", f"pages[{rank}].calibration"
            ),
            calibration_value.get("clipping_detected"),
            rank,
        )
    # Asymetrie corrigee (revue 5.26): un `payload` explicitement `null` est
    # une CORRUPTION (une page mutique OMET la cle, elle ne la vide pas), pas
    # une absence -- symetrique du refus deja pose sur `source_digest` plus
    # bas dans ce meme constructeur.
    if "payload" in value and value["payload"] is None:
        raise ScanPrevizError(
            f"pages[{rank}].payload est explicitement null: une page non "
            "identifiee omet la cle, elle ne la vide pas -- corruption "
            "refusee"
        )
    _payload_champ = (
        _page_payload(value["payload"], rank, page_index)
        if "payload" in value
        else None
    )
    corner_markers = []
    for marker in _read_sequence(
        _read_field(value, "corner_markers", f"pages[{rank}]"),
        f"pages[{rank}].corner_markers",
    ):
        marker_label = f"pages[{rank}].corner_markers[]"
        marker_id = _require_int(
            _read_field(marker, "marker_id", marker_label), f"{marker_label}.marker_id"
        )
        _read_address(
            _read_field(marker, "address", marker_label),
            {"read_rank": rank, "page_index": page_index, "marker_id": marker_id},
            f"{marker_label}.address",
        )
        corner_markers.append(
            PrevizCornerMarker(
                marker_id=marker_id,
                center_x_px=_require_number(
                    _read_field(marker, "center_x_px", marker_label),
                    f"{marker_label}.center_x_px",
                ),
                center_y_px=_require_number(
                    _read_field(marker, "center_y_px", marker_label),
                    f"{marker_label}.center_y_px",
                ),
            )
        )
    foreign_markers = []
    for marker in _read_sequence(
        _read_field(value, "foreign_markers", f"pages[{rank}]"),
        f"pages[{rank}].foreign_markers",
    ):
        marker_label = f"pages[{rank}].foreign_markers[]"
        marker_id = _require_int(
            _read_field(marker, "marker_id", marker_label), f"{marker_label}.marker_id"
        )
        _read_address(
            _read_field(marker, "address", marker_label),
            {"read_rank": rank, "page_index": page_index, "marker_id": marker_id},
            f"{marker_label}.address",
        )
        foreign_markers.append(
            PrevizForeignMarker(
                marker_id=marker_id,
                role=_require_text(
                    _read_field(marker, "role", marker_label), f"{marker_label}.role"
                ),
            )
        )
    return ScanPrevizPage(
        read_rank=rank,
        page_index=page_index,
        page_count=_optional_int(
            _read_field(value, "page_count", f"pages[{rank}]"),
            f"pages[{rank}].page_count",
        ),
        status=_require_text(
            _read_field(value, "status", f"pages[{rank}]"), f"pages[{rank}].status"
        ),
        qr_status=_require_text(
            _read_field(value, "qr_status", f"pages[{rank}]"),
            f"pages[{rank}].qr_status",
        ),
        refusal_reason=_optional_text(
            _read_field(value, "refusal_reason", f"pages[{rank}]"),
            f"pages[{rank}].refusal_reason",
        ),
        # Story 5.27: cle **absente** -> `None`, et c'est une valeur -- celle
        # d'un document ecrit avant cette story, qui n'en portera jamais. Ce
        # module l'emet toujours, donc l'absence ne peut venir que de la.
        #
        # `_read_field` n'est **pas** l'idiome ici, et ce n'est pas un oubli:
        # il fait de l'absence d'une cle un refus nomme, ce qui est juste pour
        # les champs de structure et faux pour celui-ci. La verification que
        # `value` est bien un objet JSON est deja faite, plus haut, par les
        # `_read_field` des champs obligatoires de la meme page.
        #
        # Cle presente, `null` compris: transport verbatim, sans confrontation
        # au vocabulaire du coeur, et rien de ce qui arrive ici ne peut rendre
        # le document illisible (voir `_code_de_refus` pour le motif complet).
        refusal_code=_code_de_refus(
            value["refusal_code"] if "refusal_code" in value else None,
            f"pages[{rank}].refusal_code",
        ),
        source_path_relative=_relative_path(
            _read_field(source, "path_relative", source_label),
            f"{source_label}.path_relative",
        ),
        source_page_index=_optional_int(
            _read_field(source, "page_index", source_label),
            f"{source_label}.page_index",
        ),
        scan_input_format=_require_text(
            _read_field(source, "scan_input_format", source_label),
            f"{source_label}.scan_input_format",
        ),
        source_bit_depth=_require_int(
            _read_field(source, "source_bit_depth", source_label),
            f"{source_label}.source_bit_depth",
        ),
        width_px=_require_int(
            _read_field(source, "width_px", source_label), f"{source_label}.width_px"
        ),
        height_px=_require_int(
            _read_field(source, "height_px", source_label), f"{source_label}.height_px"
        ),
        channels=_require_int(
            _read_field(source, "channels", source_label), f"{source_label}.channels"
        ),
        decoded_project_id=_optional_text(
            _read_field(identity, "project_id", identity_label),
            f"{identity_label}.project_id",
        ),
        decoded_rush_id=_optional_text(
            _read_field(identity, "rush_id", identity_label),
            f"{identity_label}.rush_id",
        ),
        decoded_lot_id=_optional_text(
            _read_field(identity, "lot_id", identity_label),
            f"{identity_label}.lot_id",
        ),
        decoded_gamut_map_id=_optional_text(
            _read_field(identity, "gamut_map_id", identity_label),
            f"{identity_label}.gamut_map_id",
        ),
        template_id=_optional_text(
            _read_field(value, "template_id", f"pages[{rank}]"),
            f"pages[{rank}].template_id",
        ),
        template_source=_optional_text(
            _read_field(value, "template_source", f"pages[{rank}]"),
            f"pages[{rank}].template_source",
        ),
        page_size_px=(
            None
            if page_size is None
            else _page_size_px(
                _read_sequence(page_size, f"pages[{rank}].page_size_px"), rank
            )
        ),
        homography=(
            None
            if homography is None
            else _homography(
                _read_sequence(homography, f"pages[{rank}].homography"), rank
            )
        ),
        scale=_read_scale(_read_field(value, "scale", f"pages[{rank}]"), rank),
        corner_markers=tuple(corner_markers),
        foreign_markers=tuple(foreign_markers),
        frame_zones=tuple(
            _read_frame_zone(zone, rank, page_index)
            for zone in _read_sequence(
                _read_field(value, "frame_zones", f"pages[{rank}]"),
                f"pages[{rank}].frame_zones",
            )
        ),
        calibration=calibration,
        warnings=_codes(
            _read_sequence(
                _read_field(value, "warnings", f"pages[{rank}]"),
                f"pages[{rank}].warnings",
            ),
            f"pages[{rank}].warnings",
        ),
        # Emission conditionnelle (story 5.26): l'absence est une valeur --
        # celle d'un document anterieur ou d'une page non identifiee. Le refus
        # du document anterieur appartient au **consommateur d'ecriture**,
        # jamais au lecteur: la forme `previz-1` reste additive.
        #
        # Asymetrie corrigee (revue 5.26): un `payload` explicitement `null`
        # est une CORRUPTION -- une page mutique OMET la cle, elle ne la vide
        # pas -- alors que `value.get("payload")` confondait les deux et
        # laissait passer une corruption comme une page non identifiee
        # legitime. Meme discipline que `source_digest` juste en dessous:
        # cle absente -> `None`, cle presente et `null` -> refus nomme, cle
        # presente et objet -> valeur controlee (`_payload_champ`, ci-dessus).
        payload=_payload_champ,
        source_digest=(
            _require_text(value["source_digest"], f"pages[{rank}].source_digest")
            if "source_digest" in value
            else None
        ),
    )


def scan_previz_from_json_dict(document: Any) -> ScanPreviz:
    """Relire la forme JSON normative en document de previz de scan valide.

    Symetrique de :func:`scan_previz_to_json_dict` (story 5.26): la jumelle
    pure possede sa forme normative **dans les deux sens**. Le lecteur valide a
    la relecture ce que :func:`build_scan_previz` valide a la construction --
    types, vocabulaires, invariants d'etat, coherence des adresses et de la
    completude --, et ne recalcule ni ne repare **rien**: une valeur alteree
    est refusee (`ScanPrevizError`), jamais devinee.

    Aller-retour garanti: `build_scan_previz` -> `scan_previz_to_json_dict` ->
    `canonical_json` -> `json.loads` -> ce lecteur rend un objet **egal**
    (egalite structurelle des dataclasses gelees).

    Un document d'un autre `kind` (extraction, makepdf, encode) ou d'une autre
    version d'enveloppe est refuse nommement: ce lecteur ne lit que la jumelle
    scan sous `previz-1`.
    """
    if not isinstance(document, Mapping):
        raise ScanPrevizError(
            f"Le document doit etre un objet JSON, recu {type(document).__name__}"
        )
    schema_version = _read_field(document, "previz_schema_version", "document")
    if schema_version != PREVIZ_SCHEMA_VERSION:
        raise ScanPrevizError(
            f"Version d'enveloppe non lisible par ce lecteur: "
            f"{schema_version!r} (attendu {PREVIZ_SCHEMA_VERSION!r})"
        )
    kind = _read_field(document, "kind", "document")
    if kind != SCAN_PREVIZ_KIND:
        raise ScanPrevizError(
            f"Ce document n'est pas une previz de scan: kind={kind!r} "
            f"(attendu {SCAN_PREVIZ_KIND!r})"
        )
    state = _read_field(document, "state", "document")
    if state not in SCAN_PREVIZ_STATES:
        raise ScanPrevizError(
            f"Etat de previz inconnu: {state!r}. Vocabulaire ferme: "
            f"{', '.join(SCAN_PREVIZ_STATES)}"
        )
    generated = normalize_generated_at_utc(
        _read_field(document, "generated_at_utc", "document"),
        error_type=ScanPrevizError,
        example=_GENERATED_AT_EXAMPLE,
    )

    subject_value = _read_field(document, "subject", "document")
    subject = ScanPrevizSubject(
        project_id=_require_text(
            _read_field(subject_value, "project_id", "subject"), "subject.project_id"
        ),
        rush_id=_require_text(
            _read_field(subject_value, "rush_id", "subject"), "subject.rush_id"
        ),
        lot_id=_require_text(
            _read_field(subject_value, "lot_id", "subject"), "subject.lot_id"
        ),
        ingest_slug=_require_text(
            _read_field(subject_value, "ingest_slug", "subject"),
            "subject.ingest_slug",
        ),
        template_id=_require_text(
            _read_field(subject_value, "template_id", "subject"),
            "subject.template_id",
        ),
        gamut_map_id=_require_text(
            _read_field(subject_value, "gamut_map_id", "subject"),
            "subject.gamut_map_id",
        ),
        # Transport verbatim: la cadence a deja sa forme canonique unique
        # ("num/den"); la re-deriver ici serait un calcul.
        fps_target_exact=_optional_text(
            _read_field(subject_value, "fps_target_exact", "subject"),
            "subject.fps_target_exact",
        ),
        target_colorspace=_optional_text(
            _read_field(subject_value, "target_colorspace", "subject"),
            "subject.target_colorspace",
        ),
        patch_preset_id=_optional_text(
            _read_field(subject_value, "patch_preset_id", "subject"),
            "subject.patch_preset_id",
        ),
        scan_dpi_declared=_require_int(
            _read_field(subject_value, "scan_dpi_declared", "subject"),
            "subject.scan_dpi_declared",
        ),
        scan_dpi_detection=_require_int(
            _read_field(subject_value, "scan_dpi_detection", "subject"),
            "subject.scan_dpi_detection",
        ),
        scans_dir_relative=_relative_path(
            _read_field(subject_value, "scans_dir_relative", "subject"),
            "subject.scans_dir_relative",
        ),
        output_dir_relative=_optional_relative_path(
            _read_field(subject_value, "output_dir_relative", "subject"),
            "subject.output_dir_relative",
        ),
    )

    counters_value = _read_field(document, "counters", "document")
    counters = ScanPrevizCounters(
        pages_present=_require_cardinal(
            _read_field(counters_value, "pages_present", "counters"),
            "counters.pages_present",
        ),
        pages_expected=(
            None
            if _read_field(counters_value, "pages_expected", "counters") is None
            else _require_cardinal(
                counters_value["pages_expected"], "counters.pages_expected"
            )
        ),
        frames_written=(
            None
            if _read_field(counters_value, "frames_written", "counters") is None
            else _require_cardinal(
                counters_value["frames_written"], "counters.frames_written"
            )
        ),
        frames_expected=(
            None
            if _read_field(counters_value, "frames_expected", "counters") is None
            else _require_cardinal(
                counters_value["frames_expected"], "counters.frames_expected"
            )
        ),
        synthetic_frame_count=(
            None
            if _read_field(counters_value, "synthetic_frame_count", "counters")
            is None
            else _require_cardinal(
                counters_value["synthetic_frame_count"],
                "counters.synthetic_frame_count",
            )
        ),
    )
    # Les invariants d'etat de `_state_counters`, revalides sur ce que le
    # fichier porte: un `detected` a cardinaux de frames, ou un
    # `reconstructed` sans eux, est un document altere.
    if state == SCAN_PREVIZ_STATE_RECONSTRUCTED:
        for label, value in (
            ("frames_written", counters.frames_written),
            ("synthetic_frame_count", counters.synthetic_frame_count),
        ):
            if value is None:
                raise ScanPrevizError(
                    f"counters.{label} est obligatoire en regime "
                    "'reconstructed': ce document se contredit"
                )
        if subject.output_dir_relative is None:
            raise ScanPrevizError(
                "subject.output_dir_relative est obligatoire en regime "
                "'reconstructed': les frames ecrites se localisent"
            )
        if (
            counters.frames_expected is not None
            and counters.frames_written > counters.frames_expected
        ):
            raise ScanPrevizError(
                f"frames_written ({counters.frames_written}) depasse le "
                f"cardinal attendu ({counters.frames_expected}): ce document "
                "se contredit (ARB-13)"
            )
        if counters.synthetic_frame_count > counters.frames_written:
            raise ScanPrevizError(
                f"synthetic_frame_count ({counters.synthetic_frame_count}) "
                f"depasse le nombre de frames ecrites "
                f"({counters.frames_written}): ce document se contredit"
            )
    else:
        for label, value in (
            ("frames_written", counters.frames_written),
            ("frames_expected", counters.frames_expected),
            ("synthetic_frame_count", counters.synthetic_frame_count),
        ):
            if value is not None:
                raise ScanPrevizError(
                    f"counters.{label} n'a pas de sens en regime 'detected': "
                    "ce document se contredit"
                )
        if subject.output_dir_relative is not None:
            raise ScanPrevizError(
                "subject.output_dir_relative n'a pas de sens en regime "
                "'detected': aucune frame n'est encore ecrite"
            )

    pages = tuple(
        _read_page(page, position)
        for position, page in enumerate(
            _read_sequence(_read_field(document, "pages", "document"), "pages")
        )
    )
    ranks = [page.read_rank for page in pages]
    if len(set(ranks)) != len(ranks):
        raise ScanPrevizError(
            "Le document porte deux pages du meme rang de lecture: les "
            "adresses de page ne seraient plus uniques"
        )
    # Revue 5.26: `page_index` doit rester unique lui aussi. Deux pages du
    # meme `page_index` mais de `read_rank` distincts ne sont PAS attrapees
    # ci-dessus, et collisionneraient sur le meme nom de frame de sortie a
    # l'ecriture -- une page en ecraserait une autre en silence. `None` est
    # exclu du controle: plusieurs pages au QR non lu sont legitimement
    # muettes, sans que cela les rende indiscernables entre elles.
    page_indices = [page.page_index for page in pages if page.page_index is not None]
    if len(set(page_indices)) != len(page_indices):
        raise ScanPrevizError(
            "Le document porte deux pages du meme page_index: elles "
            "collisionneraient sur le meme nom de frame de sortie a "
            "l'ecriture"
        )
    if counters.pages_present != len(pages):
        raise ScanPrevizError(
            f"counters.pages_present ({counters.pages_present}) contredit le "
            f"nombre de pages du document ({len(pages)})"
        )

    warnings_value = _read_field(document, "warnings", "document")
    previz_codes = _codes(
        _read_sequence(
            _read_field(warnings_value, "previz", "warnings"), "warnings.previz"
        ),
        "warnings.previz",
    )
    require_known_codes(
        previz_codes,
        SCAN_PREVIZ_WARNING_CODES,
        label="Code d'avertissement de previz de scan inconnu",
        error_type=ScanPrevizError,
    )
    if len(set(previz_codes)) != len(previz_codes):
        raise ScanPrevizError(
            f"warnings.previz porte un code duplique: {previz_codes!r}"
        )
    # `LOT_INCOMPLETE` est deduit a la construction; a la relecture il doit
    # dire exactement ce que les compteurs disent -- ni present a tort, ni
    # absent a tort. Refus, jamais recalcul silencieux.
    expected_completude = _completude_codes(state, counters)
    if (LOT_INCOMPLETE in previz_codes) != (LOT_INCOMPLETE in expected_completude):
        raise ScanPrevizError(
            f"warnings.previz contredit les compteurs du document sur "
            f"{LOT_INCOMPLETE}: ce document se contredit (EPIC5-ARB-32)"
        )
    warnings = ScanPrevizWarnings(
        ingest=_codes(
            _read_sequence(
                _read_field(warnings_value, "ingest", "warnings"),
                "warnings.ingest",
            ),
            "warnings.ingest",
        ),
        detection=_codes(
            _read_sequence(
                _read_field(warnings_value, "detection", "warnings"),
                "warnings.detection",
            ),
            "warnings.detection",
        ),
        output=_codes(
            _read_sequence(
                _read_field(warnings_value, "output", "warnings"),
                "warnings.output",
            ),
            "warnings.output",
        ),
        previz=previz_codes,
    )

    fingerprints_value = _read_field(document, "fingerprints", "document")
    detection_fingerprint = _require_text(
        _read_field(fingerprints_value, "detection", "fingerprints"),
        "fingerprints.detection",
    )
    if not is_complete_fingerprint(detection_fingerprint):
        raise ScanPrevizError(
            "fingerprints.detection doit porter la recette de la famille sous "
            "forme complete (prefixe 'sha256-v1:' suivi de 64 hexadecimaux), "
            f"recu {detection_fingerprint!r}"
        )
    selection_fingerprint = _optional_text(
        _read_field(fingerprints_value, "selection", "fingerprints"),
        "fingerprints.selection",
    )
    if selection_fingerprint is not None and not is_complete_fingerprint(
        selection_fingerprint
    ):
        raise ScanPrevizError(
            "fingerprints.selection doit porter la recette de la famille sous "
            f"forme complete, recu {selection_fingerprint!r}"
        )

    return ScanPreviz(
        previz_schema_version=schema_version,
        kind=kind,
        state=state,
        generated_at_utc=generated,
        subject=subject,
        counters=counters,
        pages=pages,
        warnings=warnings,
        fingerprints=ScanPrevizFingerprints(
            detection=detection_fingerprint,
            selection=selection_fingerprint,
        ),
    )
