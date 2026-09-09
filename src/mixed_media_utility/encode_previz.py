"""Contrat de donnees de previz d'encodage (story 6.4).

Quatrieme previz jumelle, apres `extraction_previz` (3.5, `kind = "extraction"`),
`pdf_previz` (4.9, `kind = "makepdf"`) et `scan_previz` (5.8, `kind = "scan"`),
avec `kind = "encode"`. Le livrable est le **contrat de donnees**, pas une
interface: une GUI (Epic 7) consomme ce document pour montrer « voici ce que
`encode` produira » sans re-decider quoi que ce soit et sans relancer un
encodage.

Ce que ce module fait, et ce qu'il ne fait pas
----------------------------------------------
Il **projette** ce que la story 6.1 a decide. Chaque valeur vient litteralement
d'`encode.EncodePlan` et de ses sous-structures (`TargetResolution`,
`TimecodePlan`, `CompletenessVerdict`), ou du catalogue technique de 2.4.
Aucune conversion de timecode, aucun comptage de fichiers, aucune sonde, aucun
appel a ffprobe, **aucune construction d'argv**, aucune verification croisee.
Des entrees incoherentes ressortent incoherentes et **verbatim** -- c'est teste
par des sentinelles volontairement fausses: si le module recalculait quoi que ce
soit, la sentinelle serait corrigee au lieu d'etre transportee.

Il ne recalcule pas non plus « pour verifier »: confronter ici le cardinal de la
sequence a `completeness.found` ferait diverger la previz de ce que la
production fera -- le piege central que 3.5, 4.9 et 5.8 ont evite.

**Exception nommee, et il n'y en a qu'une**: la forme canonique d'une cadence.
`extraction_previz` ouvre une section « Forme canonique d'une cadence -- une
seule, sans exception: `codec_profiles.exact_frame_rate` » juste apres avoir
ecrit « aucune arithmetique de cadence », et les trois jumelles l'appliquent
depuis un flottant. `previz_common.exact_rate` **calcule** (`29.97` rend
`30000/1001`, `12.5` rend `25/2`): sans cette reserve, un flottant entrerait
verbatim au document et **dans l'empreinte**, et deux recettes produiraient
deux empreintes pour la meme cadence. `EncodePlan` porte les deux formes
(`frame_rate` flottant et `exact_frame_rate` deja en `"num/den"`); c'est la
seconde qui entre ici, et l'exception reste due pour un appelant qui ne
fournirait que le flottant.

**Les deux chemins passent par la meme porte** -- correction de revue, sur une
mesure: `_require_text` seul laissait entrer `exact_frame_rate="30"`,
`"banane"`, `"25/0"` ou `"29.97"`, si bien que `build(exact_frame_rate="30")` et
`build(fps_target=30.0)` decrivaient la meme cadence sous **deux empreintes
differentes** -- exactement le scenario que le paragraphe ci-dessus dit vouloir
empecher. `exact_frame_rate` est donc contraint a la forme rationnelle
`num/den` **puis** ramene par `exact_rate`, qui est idempotent sur ce que 6.1
produit (`exact_rate("25/1")` rend `"25/1"`) et reduit `"50/2"` en `"25/1"`.
Symetriquement `fps_target` doit etre un **nombre**: `exact_frame_rate("29.97")`
rend `2997/100` la ou `exact_frame_rate(29.97)` rend `30000/1001`, parce que la
branche `str` du socle ne passe pas par le recalage NTSC. Cet ecart appartient a
`codec_profiles` et n'est pas resorbe ici; il est simplement rendu inatteignable
depuis ce module, une chaine decimale n'etant plus acceptee d'aucun cote.

Le vocabulaire de cette previz est FRANCOPHONE
-----------------------------------------------
Parce que son producteur l'est. La regle d'orthographe de la famille, posee par
5.8 (`scan_previz.py:294-296`), est: « un code qui nomme un fait deja nomme par
le vocabulaire ferme d'un producteur livre prend l'orthographe **du
producteur**, au caractere pres ». Les trois jumelles avaient toutes des
producteurs anglophones; celui-ci ne l'est pas. `encode.ENCODE_CODES` emet
`LOT_INCOMPLET`, `TIRAGES_MULTIPLES`, `CARDINAL_ATTENDU_INDETERMINABLE`,
`FRAMES_SYNTHETIQUES_PRESENTES`, `AUCUN_TIMECODE_REINJECTE` -- et un seul code
anglais, `HETEROGENEOUS_FRAME_SHAPES`, deja inconsistant chez son producteur.
Le vocabulaire d'ici reprend le sien, code pour code, ordre compris. Renommer un
code en le transportant serait un calcul, et le document contredirait la sortie
CLI que l'operateur vient de lire.

Les deux tuples sont declares **en litteraux** (motif de 5.8, qui n'importe pas
non plus les vocabulaires qu'elle transporte): le module n'importe jamais
`encode`, qui tire `subprocess` par transitivite. C'est le **test** qui importe
`encode` et confronte les deux tuples caractere par caractere -- precedent
explicite de la garde de chemin absolu, ou le test importe
`io/manifest._iter_absolute_path_violations` sans que le module le fasse.

Aucune deduction: la purete d'emission est **fermee** ici
---------------------------------------------------------
Les trois jumelles deduisent `LOT_INCOMPLETE`, seule exception a la purete
d'emission. Ici le producteur emet deja le fait, sous deux codes distincts
(`LOT_INCOMPLET` en refus, `LOT_INCOMPLET_ASSUME` en constat) et sous son
orthographe: deduire un `LOT_INCOMPLETE` anglophone poserait dans un seul et
meme document deux orthographes du meme fait. **Ce module n'emet aucun code**;
il n'y a donc pas de famille `previz` dans `warnings`, parce qu'un seau sans
emetteur possible est une branche morte -- et cet epic en a deja paye deux
(`TIMECODE_NON_REINJECTABLE_A_CETTE_CADENCE`, supprime faute d'emetteur, et la
branche `first_frame_timecode` absente, non productible).

Un seul producteur amont, donc un seul seau: `warnings.encode`. La forme
`{famille: [codes]}` est celle des trois jumelles et elle est conservee -- une
liste nue interdirait d'en ajouter un sans casser le contrat.

Etats
-----
`planned` (l'encodage est decide, rien n'est ecrit), `encoded` (le master
existe) et `refused` (6.1 a refuse, l'encodage n'aura pas lieu). Trois etats et
pas deux: un document a deux etats ne sait pas decrire un encodage **qui
n'aura pas lieu**, or c'est exactement ce qu'une interface a besoin de montrer,
et 6.1 refuse dans 25 cas nommes.

Un document `refused` ne porte **aucun** plan: aucune exception de refus de 6.1
ne transporte d'`EncodePlan`. Formulation corrigee en revue -- « elle ne
transporte qu'un code et un message » etait faux au caractere pres:
`EncodeVerificationRefused` (`encode.py:329-343`) est une sous-classe
d'`EncodeDecisionError` qui porte **en plus** le chemin du fichier conserve pour
diagnostic et son rapport de verification. Ce qu'aucune d'elles ne porte, et
c'est ce qui compte ici, c'est le **plan**. Les champs de decision sont donc
**omis** (regle du champ optionnel), et l'empreinte avec eux -- sceller un refus
reviendrait a sceller une constatation et a promettre une fraicheur que ce
document ne peut pas tenir.

Consequence assumee et consignee: trois refus au moins (`VERIFICATION_TECHNIQUE_
EN_ECHEC`, `INTERRUPTION_CLAVIER`, `ARRET_DEMANDE`) ne surviennent **jamais**
sans plan -- ils sont leves apres que 6.1 a montre le plan a l'operateur. Ce
document ne sait pas les montrer avec leur plan; l'interface en emet alors deux.
Rouvrir ce point demande de rouvrir la regle « un document `refused` ne porte
aucun plan », ce qui est un arbitrage et pas une correction de revue.

Aucun pixel, chemins relatifs seulement
----------------------------------------
Ni frame, ni master, ni vignette: des **chemins relatifs** au dossier projet,
et l'Epic 7 ouvre le fichier. `EncodePlan` porte des `Path` **absolus**
(`frame_paths`, `output_path`): les relativiser ici demanderait `pathlib` et
serait un calcul, donc c'est l'appelant qui verse des chemins relatifs. Le
module ne verifie jamais qu'un fichier existe -- ce serait une I/O.

Purete
------
Meme standard que ses trois jumelles, verrouille par le meme motif AST dans
`tests/unit/test_encode_previz.py`, socle compris: aucun `subprocess`, `cv2`,
`PIL`, `numpy`, `reportlab`, aucune ecriture, aucun `open` / `print` / `input` /
`exec` / `eval` / `__import__` / `compile` (exemption `re.compile` en attribut),
aucune dependance nouvelle, aucun import d'une bibliotheque d'interface.
Consequence structurante: ce module n'importe **ni** `encode`, **ni**
`io/encode_manifest`, **ni** aucun module `io/`. Les producteurs entrent en
typage structurel (`Protocol`), comme 5.8 consomme les cinq siens.

Erreurs: la canonicalisation n'honore aucun `error_type`
---------------------------------------------------------
Invariant du socle: « aucune fonction de ce module ne leve d'exception qui lui
soit propre; chaque garde recoit le type d'erreur de son appelant ». Il vaut
pour les **gardes**, pas pour `canonical_json` ni `fingerprint_of`. Mesure:

    canonical_json({"fps": nan})    -> ValueError « Out of range float values »
    canonical_json({"x": object()}) -> TypeError « not JSON serializable »
    canonical_json(cyclique)        -> ValueError « Circular reference detected »
    canonical_json(profondeur 3000) -> RecursionError

Un appelant qui attrape `EncodePrevizError` -- sous-classe de `ValueError`,
comme les trois ainees -- n'attrape pas un `ValueError` nu, encore moins un
`TypeError` ou un `RecursionError`. Le chemin est joignable: `container_tags`
est un **sous-dictionnaire transporte verbatim**, sans garde de valeur, et
`json.loads` accepte `NaN` a la lecture d'une sonde ffprobe sans que la valeur
soit jamais retypee. La construction canonicalise donc ce sous-dictionnaire
comme **garde** -- un document qu'on ne peut pas canonicaliser est inutilisable
chez son destinataire, et l'explosion arriverait loin de l'entree fautive --
et releve `(TypeError, ValueError, RecursionError)` en `EncodePrevizError`.

Empreinte de fraicheur
----------------------
`fingerprints.decision` porte les **entrees de decision** de l'encodage
(:data:`DECISION_FINGERPRINT_FIELDS`), et rien d'autre. Y ajouter une
constatation -- nombre de mires, verdict de completude, chemin du master,
fiabilite du timecode, estimation de taille, avertissements -- rendrait
l'empreinte sensible a ce qui ne decide rien et signalerait des peremptions
imaginaires. Symetriquement, en omettre une entree de decision declarerait a
jour un encodage qui ne l'est plus: c'est le precedent des bornes de 3.7,
« jugees nouvelles plutot que relues pour ce qu'elles sont ».

La **sequence** y entre par un sous-condensat a deux niveaux
(:data:`SEQUENCE_FRAME_DIGEST_FIELDS`), motif d'`ingested_pages_digest` de 5.8:
un tuple de noms de champs scalaires ne peut pas porter une collection, et
c'est le sous-condensat qui rend testable « une frame ajoutee, retiree, ou
**placee dans un autre ordre** change l'empreinte ».

Les empreintes de portees differentes ne sont **jamais comparables** malgre le
prefixe partage `sha256-v1:`.

Une previz n'autorise rien
--------------------------
Le document est **consultatif**. Il ne porte aucun consentement, aucun etat de
confirmation exploitable comme accord, aucun declencheur: il n'encode pas, ne
cree ni fichier ni entree de manifest, et ne porte pas la reponse au `--yes` de
6.1. `EncodePlan.overwrite` n'entre donc pas au document -- c'est un
consentement, et « overwrite » est un mot interdit du JSON canonique. Trois
tests verrouillent ces absences, sur le motif de 3.5.

Frontiere Epic 6 / Epic 7
--------------------------
Identique a celle de 3.5, qui fait foi. **Appartient a ce module**: la forme du
document et sa derivation sans duplication depuis 6.1. **N'appartiennent jamais
ici**: le framework, la mise en page, la navigation, le protocole d'appel, la
politique de cache -- et l'encodage lui-meme.

Convention d'ecriture: messages en francais **sans accents**, comme le reste de
la famille, pour survivre a une console `cp1252`.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

from .previz_common import (
    PREVIZ_SCHEMA_VERSION,
    PREVIZ_STATE_PLANNED,
    canonical_json,
    envelope_head,
    exact_rate as _common_exact_rate,
    fingerprint_of,
    normalize_generated_at_utc,
    optional_text as _common_optional_text,
    require_int as _common_require_int,
    require_known_codes,
    require_number as _common_require_number,
    require_relative_path as _common_relative_path,
    require_text as _common_require_text,
)

__all__ = [
    "ENCODE_PREVIZ_KIND",
    "ENCODE_PREVIZ_STATE_PLANNED",
    "ENCODE_PREVIZ_STATE_ENCODED",
    "ENCODE_PREVIZ_STATE_REFUSED",
    "ENCODE_PREVIZ_STATES",
    "RECONSTRUCTION_DECRIT_UN_AUTRE_LOT",
    "NOMS_NON_CONFORMES",
    "FICHIERS_VIDES_ECARTES",
    "FRAMES_SYNTHETIQUES_PRESENTES",
    "AUCUN_TIMECODE_REINJECTE",
    "TIMECODE_DE_DEPART_HORS_BASE_DU_MASTER",
    "TIMECODE_DE_DEPART_NON_CANONIQUE",
    "RATIO_D_ASPECT_MODIFIE",
    "COLORIMETRIE_PROJET_DIVERGENTE",
    "APPROXIMATION_SRGB_TAGUEE_REC709",
    "LOT_INCOMPLET_ASSUME",
    "RESIDUS_D_ENCODAGE_BALAYES",
    "ENCODE_PREVIZ_WARNING_CODES",
    "ENCODE_PREVIZ_REFUSAL_CODES",
    "DECISION_FINGERPRINT_FIELDS",
    "DECISION_FINGERPRINT_OPTIONAL_FIELDS",
    "SEQUENCE_FRAME_DIGEST_FIELDS",
    "EncodePrevizError",
    "TargetResolutionLike",
    "TimecodePlanLike",
    "CompletenessVerdictLike",
    "SequenceFrameLike",
    "EncodePrevizSubject",
    "PrevizResolution",
    "PrevizTimecode",
    "PrevizSequenceFrame",
    "PrevizCompleteness",
    "PrevizDiscarded",
    "EncodePrevizPlan",
    "EncodePrevizRefusal",
    "EncodePrevizWarnings",
    "EncodePrevizFingerprints",
    "EncodePreviz",
    "build_encode_previz",
    "encode_previz_to_json_dict",
]


# --------------------------------------------------------------------------
# Vocabulaire fige
# --------------------------------------------------------------------------

#: `kind` de la charge specifique de ce module (enveloppe `previz-1`).
ENCODE_PREVIZ_KIND = "encode"

#: Etats du document. `planned` est l'etat **generique** du socle; `encoded` est
#: specifique au kind, sur le motif `extraction -> extracted`,
#: `makepdf -> rendered`, `scan -> detected` / `reconstructed`.
#:
#: `refused` est le troisieme, et il n'a pas d'equivalent chez les jumelles: 6.1
#: refuse d'encoder dans 25 cas nommes (`encode.ENCODE_REFUSAL_CODES`), et un
#: document a deux etats ne sait pas decrire un encodage qui n'aura pas lieu. Le
#: cas n'est pas theorique -- sur `TIRAGES_MULTIPLES`, 6.1 refuse **et liste les
#: candidats**, donc le seul cas ou il existe des candidats ecartes est celui ou
#: il n'y a pas de lot retenu.
ENCODE_PREVIZ_STATE_PLANNED = PREVIZ_STATE_PLANNED
ENCODE_PREVIZ_STATE_ENCODED = "encoded"
ENCODE_PREVIZ_STATE_REFUSED = "refused"
ENCODE_PREVIZ_STATES: tuple[str, ...] = (
    ENCODE_PREVIZ_STATE_PLANNED,
    ENCODE_PREVIZ_STATE_ENCODED,
    ENCODE_PREVIZ_STATE_REFUSED,
)

# --- vocabulaire FERME des constats transportes ----------------------------
#
# Nom de constante volontairement distinct de `PREVIZ_WARNING_CODES` (3.5), de
# `PDF_PREVIZ_WARNING_CODES` (4.9) et de `SCAN_PREVIZ_WARNING_CODES` (5.8):
# reproduire l'homonymie recreerait la divergence qu'ARB-14 a du resorber.
#
# Orthographe: celle du producteur, au caractere pres. Chaque valeur ci-dessous
# est le miroir litteral d'une constante d'`encode.ENCODE_INFORMATIONAL_CODES`,
# et un test de la suite les confronte une par une -- ce module n'importe pas
# `encode`, qui tirerait `subprocess` par transitivite.

#: La section `reconstruction` du manifest decrit un **autre** lot que celui
#: vise. Information, jamais refus.
RECONSTRUCTION_DECRIT_UN_AUTRE_LOT = "RECONSTRUCTION_DECRIT_UN_AUTRE_LOT"

#: Des fichiers du dossier ne suivent pas la convention de nom du lot vise.
NOMS_NON_CONFORMES = "NOMS_NON_CONFORMES"

#: Des fichiers de **0 octet** au nom conforme ont ete ecartes de la sequence.
FICHIERS_VIDES_ECARTES = "FICHIERS_VIDES_ECARTES"

#: Le lot porte des mires de synthese, encodees telles quelles (EPIC6-ARB-3).
FRAMES_SYNTHETIQUES_PRESENTES = "FRAMES_SYNTHETIQUES_PRESENTES"

#: Le lot ne porte pas `timecode_base_fps`: aucun timecode n'est reinjecte.
AUCUN_TIMECODE_REINJECTE = "AUCUN_TIMECODE_REINJECTE"

#: Le depart est legal dans sa base source et n'existe pas dans celle du master.
TIMECODE_DE_DEPART_HORS_BASE_DU_MASTER = "TIMECODE_DE_DEPART_HORS_BASE_DU_MASTER"

#: Le depart retenu n'est pas celui de la premiere frame reellement presente.
TIMECODE_DE_DEPART_NON_CANONIQUE = "TIMECODE_DE_DEPART_NON_CANONIQUE"

#: La resolution demandee n'a pas le rapport d'aspect de la source.
RATIO_D_ASPECT_MODIFIE = "RATIO_D_ASPECT_MODIFIE"

#: `color.target_colorspace` du projet ne correspond pas au profil retenu.
COLORIMETRIE_PROJET_DIVERGENTE = "COLORIMETRIE_PROJET_DIVERGENTE"

#: Master tague `bt709` sur des valeurs de scanner, donc sRGB de fait (AC 16
#: de 6.1). Approximation assumee et nommee.
APPROXIMATION_SRGB_TAGUEE_REC709 = "APPROXIMATION_SRGB_TAGUEE_REC709"

#: Un lot troue est encode sur consentement explicite (EPIC6-ARB-3).
LOT_INCOMPLET_ASSUME = "LOT_INCOMPLET_ASSUME"

#: Des residus d'encodage tues ont ete balayes avant de commencer.
RESIDUS_D_ENCODAGE_BALAYES = "RESIDUS_D_ENCODAGE_BALAYES"

#: Les constats **informatifs** de 6.1, dans son ordre. Ils accompagnent un plan;
#: aucun n'arrete quoi que ce soit. Le module n'en emet **aucun**: il les
#: transporte et refuse tout code hors de ce tuple.
ENCODE_PREVIZ_WARNING_CODES: tuple[str, ...] = (
    RECONSTRUCTION_DECRIT_UN_AUTRE_LOT,
    NOMS_NON_CONFORMES,
    FICHIERS_VIDES_ECARTES,
    FRAMES_SYNTHETIQUES_PRESENTES,
    AUCUN_TIMECODE_REINJECTE,
    TIMECODE_DE_DEPART_HORS_BASE_DU_MASTER,
    TIMECODE_DE_DEPART_NON_CANONIQUE,
    RATIO_D_ASPECT_MODIFIE,
    COLORIMETRIE_PROJET_DIVERGENTE,
    APPROXIMATION_SRGB_TAGUEE_REC709,
    LOT_INCOMPLET_ASSUME,
    RESIDUS_D_ENCODAGE_BALAYES,
)

#: Les motifs de refus de 6.1 (`encode.ENCODE_REFUSAL_CODES`), dans son ordre.
#: **Vocabulaire distinct** de celui des constats, et disjoint de lui: un refus
#: remplace le plan, un constat l'accompagne. Les melanger dans un seul tuple
#: laisserait un document `planned` porter « MASTER_DEJA_PRESENT » en
#: avertissement, c'est-a-dire annoncer un encodage que 6.1 vient de refuser.
#:
#: Declares en litteraux comme ci-dessus, et confrontes par le test au tuple
#: reel. La liste de base est celle du 2026-08-11: `TIMECODE_NON_REINJECTABLE_A_
#: CETTE_CADENCE` n'y figure pas, il a ete **supprime** du vocabulaire de 6.1
#: faute d'emetteur possible. Les quatre derniers codes viennent de la story
#: 6.6 (2026-08-13): `CADENCE_SOURCE_MANQUANTE`/`CADENCE_SOURCE_REDONDANTE`
#: (AC 1bis), puis `MAINTIEN_DE_FRAME_NON_POSITIF`/`QUEUE_DE_LOT_INEXPLOITABLE`
#: (ajoutes apres la revue en trois couches, findings 1 et 3).
ENCODE_PREVIZ_REFUSAL_CODES: tuple[str, ...] = (
    "LOT_ABSENT_DU_MANIFEST",
    "ETAT_DE_LOT_INSUFFISANT",
    "CADENCE_DE_LOT_INEXPLOITABLE",
    "RUSH_ID_ABSENT_DU_LOT",
    "CHAMP_DE_MATRICE_SANS_VALEUR",
    "DOSSIER_DE_LOT_NON_DECLARE",
    "DOSSIER_DE_LOT_ABSENT",
    "DOSSIER_DE_LOT_VIDE",
    "TIRAGES_MULTIPLES",
    "HETEROGENEOUS_FRAME_SHAPES",
    "LOT_INCOMPLET",
    "CARDINAL_ATTENDU_INDETERMINABLE",
    "FRAMES_SURNUMERAIRES",
    "EMPREINTE_DE_SELECTION_DIVERGENTE",
    "BORNES_DE_LOT_DIVERGENTES",
    "TIMECODE_DECROISSANT",
    "TIMECODE_DE_DEPART_INCONVERTIBLE",
    "MASTER_DEJA_PRESENT",
    # Ajoute par `main` a `encode.ENCODE_REFUSAL_CODES` (`EPIC11-ARB-89`,
    # versionnage des masters) SANS son miroir ici -- alors que le commentaire
    # de `encode.py` l'exige nommement : « `encode_previz.py` porte un miroir
    # **litteral** de ce tuple, confronte caractere a caractere ». Trois bancs
    # rougissaient, dont celui qui mesure que les deux vocabulaires COUVRENT le
    # producteur. Repose a la liaison du 2026-09-01, a la position exacte du
    # producteur (18) : la confrontation porte sur l'ORDRE autant que sur les
    # membres.
    "RANGS_DE_MASTER_EPUISES",
    "DOSSIER_DE_SORTIE_EST_UN_FICHIER",
    "MASTER_EST_UN_REPERTOIRE",
    "DESTINATION_NON_INSCRIPTIBLE",
    "VERIFICATION_TECHNIQUE_EN_ECHEC",
    "INTERRUPTION_CLAVIER",
    "ARRET_DEMANDE",
    "RESOLUTION_INCONNUE",
    "CADENCE_SOURCE_MANQUANTE",
    "CADENCE_SOURCE_REDONDANTE",
    "MAINTIEN_DE_FRAME_NON_POSITIF",
    "QUEUE_DE_LOT_INEXPLOITABLE",
    # Story 11.8, AC 4.1 : la nouvelle version d'un master et son ecrasement
    # conscient demandes ENSEMBLE -- deux issues du meme conflit, jamais deux
    # a la fois. Pose ici DANS LE MEME DIFF que chez le producteur : c'est
    # exactement ce que la liaison du 2026-09-01 a du rattraper apres coup
    # pour `RANGS_DE_MASTER_EPUISES`, trois bancs rouges a la cle. (Le nom du
    # drapeau n'est pas ecrit : ce module ne porte aucun consentement, et un
    # banc mesure que son source ne le nomme pas.)
    "VERSION_ET_ECRASEMENT_COMBINES",
    # Story 6.8 (`EPIC11-ARB-190`) : la reconstruction DESIGNEE n'est aucune
    # des passes que le lot a connues. Pose ici DANS LE MEME DIFF que chez le
    # producteur, et a la meme position -- la confrontation porte sur l'ORDRE
    # autant que sur les membres.
    "RECONSTRUCTION_INCONNUE",
)

#: Les **seules** entrees de decision de l'encodage qui entrent dans
#: `fingerprints.decision` (motif `SELECTION_FINGERPRINT_FIELDS` de 3.5,
#: `COMPOSITION_FINGERPRINT_FIELDS` de 4.9, `DETECTION_FINGERPRINT_FIELDS` de
#: 5.8). Trie, comme chez les trois.
#:
#: `lot_state` y figure: 6.1 refuse d'encoder un lot en deca de `scan`, donc
#: l'etat decide que cet encodage ait lieu. Il n'etait pas prevu par la premiere
#: redaction de la story, et c'est exactement le motif de l'oubli des bornes de
#: 3.7 -- « jugees nouvelles plutot que relues pour ce qu'elles sont ».
#:
#: N'y entrent **pas**, et deux d'entre eux ont ete classes « entree de
#: decision » a tort en cours de redaction: le **chemin du master**, que 6.1
#: derive de `lot_id`, `profile_id`, du conteneur et du segment de resolution,
#: donc une consequence de valeurs deja presentes; la **fiabilite du timecode**,
#: propriete constante du catalogue indexee par `profile_id`. N'y entrent pas
#: non plus le nombre de mires, le verdict de completude, l'estimation de
#: taille, les fichiers ecartes, les bornes declarees, les avertissements, ni
#: `resolution.requested` / `.origin` / `.resolution_id`: deux demandes
#: differentes qui arretent la **meme** geometrie produisent le meme master,
#: et c'est la geometrie retenue qui decide.
DECISION_FINGERPRINT_FIELDS: tuple[str, ...] = (
    "fps_target_exact",
    "lot_id",
    "lot_state",
    "profile_id",
    "resolution_height_px",
    "resolution_width_px",
    "sequence_digest",
    "timecode_base_rate",
    "timecode_start",
)

#: Les deux champs d'empreinte qui peuvent manquer: `TimecodePlan.emitted` vaut
#: `None` des que le lot ne porte pas `timecode_base_fps` (lot ne du scan) ou
#: que le depart sort de la base du master, et `base_rate` l'accompagne. Ils sont
#: **omis** du payload -- jamais `None` -- pour la raison de 3.5: c'est la regle
#: cardinale du projet, et l'empreinte d'un lot sans timecode reste ainsi
#: rigoureusement identique a ce qu'elle serait si le champ n'existait pas.
DECISION_FINGERPRINT_OPTIONAL_FIELDS: tuple[str, ...] = (
    "timecode_base_rate",
    "timecode_start",
)

#: Ce qu'une frame apporte au sous-condensat de la sequence: son rang, son
#: chemin et son timecode. Deux sequences identiques rendent le meme condensat;
#: une frame ajoutee, retiree, renommee ou **placee dans un autre ordre** le
#: change -- le condensat porte sur une **liste**, pas sur un ensemble.
#:
#: Le drapeau `synthetic` n'y entre **pas**: une mire est une constatation de
#: l'echec de la reconstruction, au meme regime que le drapeau `synthetic` de
#: 5.8, qui est explicitement hors de son empreinte de detection. Le fichier
#: encode, lui, est deja designe par son chemin.
SEQUENCE_FRAME_DIGEST_FIELDS: tuple[str, ...] = (
    "frame_path_relative",
    "frame_timecode",
    "output_rank",
)

#: Date d'exemple citee dans le refus d'horodatage de ce module.
_GENERATED_AT_EXAMPLE = "2026-08-11T12:00:00Z"


class EncodePrevizError(ValueError):
    """Entree refusee a la construction du document.

    Derive de `ValueError` pour rester capturable par un appelant generique,
    comme ses trois ainees. Elle ne signale **jamais** un cas degrade -- lot
    troue, mires presentes, encodage refuse par 6.1: ceux-la produisent un
    document valide, porte par l'etat `refused` ou par les avertissements. Elle
    signale une entree qui rendrait le document lui-meme faux ou trompeur.
    """


# --------------------------------------------------------------------------
# Contrats consommes, en typage structurel (purete: `encode` tire `subprocess`
# par transitivite, donc aucun de ses types n'est importable ici)
# --------------------------------------------------------------------------


class TargetResolutionLike(Protocol):
    """Sous-ensemble d'`encode.TargetResolution` reellement lu.

    `size` vaut `None` pour une demande `native` **non arretee**; la geometrie
    definitive est celle de `settle_resolution`, et un `EncodePlan` n'en porte
    jamais d'autre. Une resolution non arretee est refusee ici: publier une
    geometrie inconnue serait publier un master dont personne ne connait la
    taille.
    """

    requested: str
    origin: str
    resolution_id: str | None
    size: Sequence[int] | None


class TimecodePlanLike(Protocol):
    """Sous-ensemble d'`encode.TimecodePlan` reellement lu.

    `findings` n'y figure pas, et ce n'est pas un oubli: 6.1 les verse deja dans
    `EncodePlan.findings`, et les lire des deux cotes les publierait deux fois.
    Un champ declare mais jamais lu trompe le fournisseur alternatif du
    protocole (revue 4.9).
    """

    emitted: str | None
    manifest_value: str | None
    base_rate: str | None


class CompletenessVerdictLike(Protocol):
    """Sous-ensemble d'`encode.CompletenessVerdict` reellement lu.

    `missing_pages` porte des **index de page**, jamais des timecodes: une page
    absente ne laisse aucun slot et « aucun timecode n'est donc recalculable
    pour une page absente » (`scan_output_frames.py:28-29`). Promettre les
    timecodes des frames manquantes est le piege que 6.1 a paye d'un bloquant.
    """

    expected: int | None
    found: int
    synthetic_present: Sequence[str]
    synthetic_missing: Sequence[str]
    missing_pages: Sequence[int]
    complete: bool


class SequenceFrameLike(Protocol):
    """Une frame de la sequence, telle que l'appelant la compose.

    6.1 ne porte pas d'objet par frame: `EncodePlan` a `frame_paths` (des `Path`
    **absolus**), `sequence_timecodes` et un registre de mires par **nom**. Les
    apparier ici demanderait de relativiser des chemins et de confronter des
    noms -- deux calculs. L'appelant, qui a le plan et le verdict, compose donc
    ces trois valeurs plus le rang; le module les transporte.

    `synthetic` est **inconditionnel** des qu'une frame existe, `false` compris:
    c'est l'exception d'EPIC5-ARB-8, reprise telle quelle. Un drapeau absent se
    relit « vraie frame », et l'interface montrerait une mire « FRAME
    MANQUANTE » comme un plan du film.
    """

    output_rank: int
    frame_path_relative: str
    frame_timecode: str
    synthetic: bool


# --------------------------------------------------------------------------
# Document
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class EncodePrevizSubject:
    """Ce sur quoi porte la previz, dans les trois etats.

    `lot_id` designe le lot **sur lequel ce document porte**: le lot retenu par
    6.1 en `planned` / `encoded`, et le lot **demande** en `refused`, puisque
    aucun n'a ete retenu. Les deux ne coincident pas toujours -- designer un lot
    d'extraction qui n'a qu'un seul tirage rend le lot du tirage.

    `profile_id` et `container` sont presents dans les trois etats: 6.1 resout le
    profil a sa premiere ligne, avant toute garde, donc ils sont connus meme
    quand tout le reste est refuse.
    """

    project_id: str
    lot_id: str
    profile_id: str
    container: str


@dataclass(frozen=True)
class PrevizResolution:
    """La geometrie arretee du master, et d'ou elle vient.

    `origin` a **quatre** valeurs chez 6.1 (`defaut`, `registre`, `native`,
    `personnalisee`) et n'est pas un booleen « vient du defaut »; elle est
    transportee verbatim, sans vocabulaire ferme ici -- le sien vit dans
    `encode`, et en recopier un second serait la divergence qu'ARB-14 a du
    resorber.

    `resolution_id` est **omis** quand la geometrie ne correspond a aucune
    entree du registre, jamais rendu `null`.
    """

    requested: str
    origin: str
    width_px: int
    height_px: int
    resolution_id: str | None = None


@dataclass(frozen=True)
class PrevizTimecode:
    """Le timecode de depart, sa base de validation et sa fiabilite.

    `reliability` est la **moitie donnees** d'une dette nommee depuis 6.3:
    `TECHNICAL_METADATA_MATRIX["timecode"]` porte une entree `reliability` par
    profil (`reliable` sur les masters MOV et DNxHR, `best_effort` sur les
    derives MP4), donc l'information est disponible en machine. Elle est
    transportee **verbatim** depuis le catalogue, fournie par l'appelant puisque
    ce module est pur, et c'est une **constatation**: propriete constante du
    catalogue indexee par `profile_id`, elle ne decide rien et n'entre pas dans
    l'empreinte. La faire remonter dans la doc **utilisateur** reste due par 6.1.

    Les trois autres champs sont **omis** quand ils manquent, jamais `null`:
    `emitted` vaut `None` dans deux cas nommes par 6.1 -- pas de
    `timecode_base_fps`, ou depart hors base du master.
    """

    reliability: str
    emitted: str | None = None
    manifest_value: str | None = None
    base_rate: str | None = None


@dataclass(frozen=True)
class PrevizSequenceFrame:
    """Une frame de la sequence encodee, dans l'ordre ou elle sera encodee."""

    output_rank: int
    frame_path_relative: str
    frame_timecode: str
    synthetic: bool


@dataclass(frozen=True)
class PrevizCompleteness:
    """Le verdict de lot de 6.1, transporte tel quel.

    `found` n'est **jamais** confronte au cardinal de la sequence: c'est le
    verdict du producteur, et le recalculer ici ferait diverger la previz de ce
    que la production fera. `expected` est **omis** quand il est indeterminable.

    Regle de precedence des mires, tranchee par 6.1: « le disque fait foi pour
    la presence, le manifest pour la nature ». Un nom au registre sans fichier
    est un **trou** (`synthetic_missing`), pas une mire.
    """

    found: int
    complete: bool
    missing_pages: tuple[int, ...] = ()
    synthetic_present: tuple[str, ...] = ()
    synthetic_missing: tuple[str, ...] = ()
    expected: int | None = None


@dataclass(frozen=True)
class PrevizDiscarded:
    """Ce que 6.1 a ecarte de la sequence, par nom de fichier.

    Deux familles distinctes et jamais fondues: un nom non conforme au lot vise,
    et un fichier de 0 octet -- artefact d'une passe interrompue, que 6.1 ecarte
    « quel que soit son nom ». Les compter comme des frames faisait passer un lot
    troue pour complet.
    """

    nonconforming_files: tuple[str, ...] = ()
    empty_files: tuple[str, ...] = ()


@dataclass(frozen=True)
class EncodePrevizPlan:
    """Ce que l'encodage produira, tel que 6.1 l'a decide.

    Present en `planned` et en `encoded`, **absent** en `refused`.
    `encoded_bytes` est le poids **reel** du master (`EncodeOutcome.
    encoded_size`), obligatoire en `encoded` et interdit ailleurs; il se lit en
    face d'`estimated_bytes`, qui est une **majoration** par le debit non
    compresse et jamais une promesse -- 6.1 le dit de sa propre docstring,
    « en ordre de grandeur explicitement approximatif et jamais optimiste ».
    """

    lot_state: str
    resolution: PrevizResolution
    source_width_px: int
    source_height_px: int
    fps_target_exact: str
    timecode: PrevizTimecode
    completeness: PrevizCompleteness
    sequence: tuple[PrevizSequenceFrame, ...]
    container_tags: Mapping[str, Any]
    master_path_relative: str
    estimated_bytes: int
    discarded: PrevizDiscarded = PrevizDiscarded()
    declared_first_frame_timecode: str | None = None
    declared_last_frame_timecode: str | None = None
    encoded_bytes: int | None = None


@dataclass(frozen=True)
class EncodePrevizRefusal:
    """Pourquoi l'encodage n'aura pas lieu.

    `code` vient du vocabulaire de refus de 6.1, transporte verbatim.
    `candidates` porte les lignes de `describe_lot_candidate` quand le refus les
    nomme (`TIRAGES_MULTIPLES`) -- c'est le seul cas ou des candidats ecartes
    existent, et c'est aussi celui ou aucun lot n'est retenu.
    """

    code: str
    candidates: tuple[str, ...] = ()


@dataclass(frozen=True)
class EncodePrevizWarnings:
    """Une seule famille, parce qu'il n'y a qu'un producteur amont.

    `encode` transporte verbatim les constats informatifs de 6.1, **dans leur
    ordre d'emission**, sans deduplication et sans tri: un code repete dit qu'un
    fait a ete constate deux fois, et 6.1 en emet plusieurs a la suite. La
    famille `previz` des trois jumelles n'existe pas ici: ce module ne deduit
    rien, donc elle serait toujours vide.
    """

    encode: tuple[str, ...] = ()


@dataclass(frozen=True)
class EncodePrevizFingerprints:
    """De quoi detecter la peremption. Voir la docstring du module."""

    decision: str


@dataclass(frozen=True)
class EncodePreviz:
    """Document de previz d'encodage, fige et comparable.

    Confort de typage pour un consommateur in-process; la forme **normative** est
    le JSON rendu par :func:`encode_previz_to_json_dict`.

    Le `__post_init__` porte le durcissement d'enveloppe que le `deferred-work`
    reclamait au socle et que cette story a tranche de tenir **ici** (voir le Dev
    Agent Record). Mesure du defaut, sur le socle inchange:

        envelope_head(kind=None, state=42, generated_at_utc=[],
                      schema_version="previz-1")
          -> {'previz_schema_version': 'previz-1', 'kind': None,
              'state': 42, 'generated_at_utc': []}

    et le JSON canonique de ce dictionnaire ne leve rien: le document ment sans
    un mot. Le chemin est joignable sans passer par le constructeur -- la story
    7.4 edite des documents et ne les reconstruit pas forcement par le builder,
    motif deja retenu pour `PrevizFrameZone.__post_init__` en 5.8.
    """

    previz_schema_version: str
    kind: str
    state: str
    generated_at_utc: str
    subject: EncodePrevizSubject
    warnings: EncodePrevizWarnings = EncodePrevizWarnings()
    plan: EncodePrevizPlan | None = None
    refusal: EncodePrevizRefusal | None = None
    fingerprints: EncodePrevizFingerprints | None = None

    def __post_init__(self) -> None:
        # `generated_at_utc` n'est **pas** dans cette liste, et c'est une
        # correction de revue: il recoit juste en dessous une garde strictement
        # plus forte (`normalize_generated_at_utc`, qui commence par le meme
        # « chaine non vide »). Le laisser ici aurait cree une redondance dont
        # aucun mutant ne peut sortir vivant sans mentir sur la couverture --
        # amputer la liste de ce champ ne changeait plus rien d'observable.
        for label, value in (
            ("previz_schema_version", self.previz_schema_version),
            ("kind", self.kind),
            ("state", self.state),
        ):
            if not isinstance(value, str) or not value:
                raise EncodePrevizError(
                    f"Champ d'enveloppe {label} vide ou d'un autre type que la "
                    f"chaine: {value!r}. `envelope_head` rend tel quel ce qu'on "
                    "lui donne et son JSON canonique ne leve rien, donc le "
                    "document mentirait sans un mot."
                )
        # Le champ de **fraicheur** est celui ou « mentir sans un mot » coute le
        # plus cher -- toute la comparaison a l'heure courante en depend -- et
        # c'est celui que la premiere ecriture du durcissement laissait passer:
        # `generated_at_utc="pasunedate"` etait accepte par le seul « chaine non
        # vide ». La garde du socle est pure et le builder l'appelle deja: la
        # rappeler ici est sans effet observable et ferme le chemin « document
        # edite hors builder » de 7.4.
        normalize_generated_at_utc(
            self.generated_at_utc,
            error_type=EncodePrevizError,
            example=_GENERATED_AT_EXAMPLE,
        )
        if self.kind != ENCODE_PREVIZ_KIND:
            raise EncodePrevizError(
                f"kind doit valoir {ENCODE_PREVIZ_KIND!r}, recu {self.kind!r}"
            )
        if not isinstance(self.subject, EncodePrevizSubject):
            raise EncodePrevizError(
                "subject doit etre un EncodePrevizSubject, recu "
                f"{type(self.subject).__name__}: {self.subject!r}. Sans lui le "
                "document explose a la serialisation, hors hierarchie."
            )
        if self.state not in ENCODE_PREVIZ_STATES:
            raise EncodePrevizError(
                f"Etat de previz inconnu: {self.state!r}. Vocabulaire ferme: "
                f"{', '.join(ENCODE_PREVIZ_STATES)}"
            )
        refused = self.state == ENCODE_PREVIZ_STATE_REFUSED
        if refused and self.refusal is None:
            raise EncodePrevizError(
                "Un document 'refused' porte le motif du refus: sans lui, il "
                "annonce qu'aucun encodage n'aura lieu sans dire pourquoi"
            )
        if not refused and self.refusal is not None:
            raise EncodePrevizError(
                f"Un motif de refus n'a de sens qu'en etat "
                f"{ENCODE_PREVIZ_STATE_REFUSED!r}, recu state={self.state!r}"
            )
        if self.refusal is not None:
            # Le vocabulaire ferme, sur le chemin direct comme sur celui du
            # builder: un document edite hors builder pouvait porter un code de
            # refus inconnu de 6.1, que l'interface aurait affiche tel quel.
            _refusal_code(self.refusal.code)
        if refused and self.plan is not None:
            raise EncodePrevizError(
                "Un document 'refused' ne porte aucun plan: 6.1 refuse par une "
                "exception qui ne transporte qu'un code et un message, jamais un "
                "EncodePlan. Publier un plan sous un refus annoncerait un "
                "encodage qui n'aura pas lieu"
            )
        if not refused and self.plan is None:
            raise EncodePrevizError(
                f"Un document {self.state!r} porte le plan de l'encodage: sans "
                "lui, il ne dit rien de ce qui sera produit"
            )
        # L'empreinte scelle les entrees de decision, qui vivent toutes dans le
        # plan: sans plan il n'y a rien a sceller, et une empreinte constante
        # ferait passer deux refus differents pour le meme document.
        if (self.fingerprints is None) == (self.plan is not None):
            raise EncodePrevizError(
                "L'empreinte de decision accompagne le plan, ni plus ni moins: "
                f"recu plan={'present' if self.plan else 'absent'}, "
                f"fingerprints={'presente' if self.fingerprints else 'absente'}"
            )
        if self.plan is not None:
            if not self.plan.sequence:
                raise EncodePrevizError(
                    "Un plan sans sequence n'annonce aucun encodage: 6.1 refuse "
                    "deja le cas (DOSSIER_DE_LOT_VIDE) avant d'avoir un plan, et "
                    "un document edite hors builder ne doit pas pouvoir le poser"
                )
            encoded = self.state == ENCODE_PREVIZ_STATE_ENCODED
            if encoded and self.plan.encoded_bytes is None:
                raise EncodePrevizError(
                    "encoded_bytes est obligatoire en etat "
                    f"{ENCODE_PREVIZ_STATE_ENCODED!r} et doit etre fourni par "
                    "l'appelant: ce module ne mesure jamais un fichier"
                )
            if not encoded and self.plan.encoded_bytes is not None:
                raise EncodePrevizError(
                    f"encoded_bytes n'a pas de sens en etat {self.state!r}: le "
                    "master n'existe pas encore, et en annoncer le poids serait "
                    "le seul mensonge que ce document puisse commettre ici"
                )


# --------------------------------------------------------------------------
# Gardes locales: la hierarchie de ce module par-dessus `previz_common`
# --------------------------------------------------------------------------


def _require_text(value: Any, label: str) -> str:
    return _common_require_text(value, label, error_type=EncodePrevizError)


def _optional_text(value: Any, label: str) -> str | None:
    return _common_optional_text(value, label, error_type=EncodePrevizError)


def _require_int(value: Any, label: str) -> int:
    return _common_require_int(value, label, error_type=EncodePrevizError)


def _relative_path(value: Any, label: str) -> str:
    return _common_relative_path(value, label, error_type=EncodePrevizError)


def _exact_rate(fps: Any) -> str:
    return _common_exact_rate(fps, error_type=EncodePrevizError)


def _require_number(value: Any, label: str) -> Any:
    return _common_require_number(value, label, error_type=EncodePrevizError)


def _require_bool(value: Any, label: str) -> bool:
    """Booleen strict: ni coercition, ni `None`.

    `bool(None)` vaut `False`, donc un producteur qui **omet** le drapeau d'une
    mire le verrait rendu « vraie frame » (revue 5.8, couche 2, finding 5).
    """
    if not isinstance(value, bool):
        raise EncodePrevizError(f"{label} doit etre un booleen, recu {value!r}")
    return value


def _require_cardinal(value: Any, label: str) -> int:
    """Cardinal positif ou nul."""
    count = _require_int(value, label)
    if count < 0:
        raise EncodePrevizError(
            f"{label} doit etre un cardinal positif ou nul, recu {value!r}"
        )
    return count


def _require_dimensions(value: Any, label: str) -> tuple[int, int]:
    """Geometrie `(largeur, hauteur)`: deux entiers strictement positifs.

    Meme refus de collection **non ordonnee** que :func:`_codes` -- garde
    ajoutee en revue, sur une mesure: `tuple({1, 1080})` rend `(1080, 1)` ou
    `(1, 1080)` selon la graine de hachage du processus, si bien qu'une demande
    `1x1080` publiait un master `1080x1` un processus sur deux. Le registre reel
    n'a que `hd1080` et `uhd2160`, mais `encode._parse_custom_resolution` admet
    **toute** geometrie `<L>x<H>` strictement positive, vignettes comprises, et
    c'est la que l'inversion devient atteignable.
    """
    if value is None:
        raise EncodePrevizError(
            f"{label} n'est pas arretee. `encode.settle_resolution` ramene toute "
            "demande -- registre, `native` ou personnalisee -- sur une geometrie "
            "definitive avant de nommer le master; publier une geometrie inconnue "
            "annoncerait un master dont personne ne connait la taille."
        )
    if isinstance(value, str):
        raise EncodePrevizError(
            f"{label} doit etre un couple (largeur, hauteur), pas une chaine: "
            f"{value!r}"
        )
    if not isinstance(value, Sequence):
        raise EncodePrevizError(
            f"{label} doit etre une sequence **ordonnee** (largeur, hauteur), "
            f"recu {type(value).__name__}: {value!r}. Une collection non ordonnee "
            "intervertirait les deux dimensions d'un processus a l'autre"
        )
    items = tuple(value)
    if len(items) != 2:
        raise EncodePrevizError(
            f"{label} doit porter exactement 2 composantes (largeur, hauteur), "
            f"recu {value!r}"
        )
    width = _require_int(items[0], f"{label}[0]")
    height = _require_int(items[1], f"{label}[1]")
    if width <= 0 or height <= 0:
        raise EncodePrevizError(
            f"{label} doit porter deux dimensions strictement positives, recu "
            f"{value!r}"
        )
    return width, height


def _codes(values: Any, label: str) -> tuple[str, ...]:
    """Sequence **ordonnee** de codes, jamais une chaine ni un ensemble.

    Deux refus, et pas un:

    * une chaine se decouperait en lettres et le document porterait des codes
      d'un caractere. Ce n'est pas une precaution theorique:
      `require_known_codes("AB", ("A", "B"))` rend `('A', 'B')` -- mesure sur le
      socle, qui itere sur la sequence recue sans regarder ce qu'elle est;
    * une collection **non ordonnee** (`set`, `frozenset`, generateur) casse la
      promesse centrale du module: l'ordre d'iteration d'un `set` depend de la
      graine de hachage du processus, et la meme entree rendrait des documents
      differents d'un processus a l'autre (mesure a la revue de 5.8).
    """
    if values is None:
        return ()
    if isinstance(values, str):
        raise EncodePrevizError(
            f"{label} doit etre une sequence de codes, pas une chaine: {values!r}"
        )
    if not isinstance(values, Sequence):
        raise EncodePrevizError(
            f"{label} doit etre une sequence **ordonnee** de codes (liste ou "
            f"tuple), recu {type(values).__name__}: {values!r}. Une collection "
            "non ordonnee rendrait deux documents differents pour la meme entree "
            "d'un processus a l'autre"
        )
    return tuple(_require_text(code, f"Code de {label}") for code in values)


def _names(values: Any, label: str) -> tuple[str, ...]:
    """Sequence ordonnee de chaines libres (noms de fichiers, descriptions).

    Meme double refus que :func:`_codes`, et pour la meme mesure: une chaine
    passee au lieu d'un tuple est **explosee caractere par caractere** par
    l'iteration, et le document porterait des noms d'un caractere. Les deux
    gardes sont separees parce qu'elles ne disent pas la meme chose -- l'une
    porte sur un vocabulaire ferme, l'autre sur du texte libre -- et qu'une
    seule aurait fait passer le message de refus de l'une pour celui de l'autre.
    """
    if values is None:
        return ()
    if isinstance(values, str):
        raise EncodePrevizError(
            f"{label} doit etre une sequence, pas une chaine: {values!r}. Une "
            "chaine s'itere caractere par caractere et le document porterait "
            "des valeurs d'un caractere."
        )
    if not isinstance(values, Sequence):
        raise EncodePrevizError(
            f"{label} doit etre une sequence **ordonnee** (liste ou tuple), recu "
            f"{type(values).__name__}: {values!r}"
        )
    return tuple(
        _require_text(item, f"{label}[{index}]") for index, item in enumerate(values)
    )


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    """Dictionnaire a cles `str`, et rien d'autre.

    La garde de cle est une correction de revue, sur une mesure:
    `json.dumps({1: "a"})` rend `{"1":"a"}` **sans le dire**, si bien qu'une cle
    incoherente ne ressortait pas incoherente mais corrigee -- le contraire du
    transport verbatim. Et le dictionnaire rendu portait alors des cles `int`,
    `float`, `bool` ou `None`, ce qui contredit « aucun objet Python non JSON »
    et interdit de comparer le document a sa relecture. 6.1 declare
    `container_tags: dict[str, str]`, donc la garde est sans effet observable
    pour le producteur reel.
    """
    if not isinstance(value, Mapping):
        raise EncodePrevizError(
            f"{label} doit etre un dictionnaire, recu "
            f"{type(value).__name__}: {value!r}"
        )
    for key in value:
        if not isinstance(key, str):
            raise EncodePrevizError(
                f"{label} n'accepte que des cles chaines, recu "
                f"{type(key).__name__}: {key!r}. `json.dumps` coerce toute cle "
                "scalaire en chaine sans le dire, et la forme rendue divergerait "
                "de la forme scellee."
            )
    return value


def _require_canonicalizable(value: Any, label: str) -> Any:
    """Garde de serialisabilite d'un sous-dictionnaire transporte verbatim.

    Elle existe parce que `canonical_json` n'honore **aucun** `error_type`:
    l'invariant « chaque garde leve la hierarchie de son appelant » vaut pour les
    gardes du socle, pas pour sa recette de canonicalisation. Un `NaN`, un objet
    non serialisable, un cycle ou une profondeur excessive y levent
    respectivement `ValueError`, `TypeError`, `ValueError` et `RecursionError` --
    dont deux sortent de la hierarchie que ce module promet.

    Le chemin est joignable: ce sous-dictionnaire est transporte **verbatim**,
    sans garde de valeur, et `json.loads` accepte `NaN` et `Infinity` a la
    lecture d'une sonde ffprobe sans que la valeur soit jamais retypee. Sans
    cette garde, l'explosion arrive chez le consommateur qui canonicalise le
    document, loin de l'entree fautive et hors de la hierarchie promise.
    """
    try:
        canonical_json(value)
    except (TypeError, ValueError, RecursionError) as error:
        raise EncodePrevizError(
            f"{label} n'est pas canonicalisable ({type(error).__name__}: "
            f"{error}). Le document serait illisible chez son destinataire et "
            "l'erreur sortirait de la hierarchie EncodePrevizError."
        ) from error
    return value


def _container_tags(value: Any) -> Mapping[str, Any]:
    """Les tags du master: gardes, puis **recopies en profondeur**.

    La copie a la construction est une correction de revue, et elle ne remplace
    pas celle de la serialisation -- les deux protegent de deux cotes opposes,
    exactement comme :func:`_require_canonicalizable` et :func:`_fingerprint_of`.
    Mesure du defaut ferme ici: l'appelant gardait une reference vivante sur son
    dictionnaire, si bien qu'un `tags["fps"] = float("nan")` **apres** le
    `build` faisait exploser `canonical_json` chez le consommateur, en
    `ValueError` nu -- c'est-a-dire le mode de defaillance exact que la garde de
    canonicalisation existe pour empecher, simplement decale d'un instant. Un
    document annonce « fige et comparable » ne peut pas dependre de ce que son
    appelant fait de son dictionnaire ensuite.
    """
    tags = _require_canonicalizable(_require_mapping(value, "container_tags"),
                                    "container_tags")
    return copy.deepcopy(dict(tags))


def _fingerprint_of(payload: Any, label: str) -> str:
    """Empreinte de la famille, avec la meme garde que ci-dessus.

    `fingerprint_of` canonicalise: il leve donc les memes exceptions, hors
    hierarchie. Les deux gardes ne se remplacent pas -- celle-ci protege ce que
    le module **scelle**, l'autre ce qu'il **transporte**.
    """
    try:
        return fingerprint_of(payload)
    except (TypeError, ValueError, RecursionError) as error:
        raise EncodePrevizError(
            f"{label} n'est pas canonicalisable ({type(error).__name__}: "
            f"{error}): l'empreinte scellerait une chaine invalide."
        ) from error


def _known_value(value: Any, vocabulary: Any, label: str) -> Any:
    """Confronter une valeur au vocabulaire **verse par l'appelant**.

    Troisieme voie du dilemme de 5.8: le vocabulaire ferme de la fiabilite du
    timecode vit dans `video_metadata`, que ce module ne peut ni importer ni
    recopier sans creer un second vocabulaire voisin. Mais
    `require_known_codes` prend le vocabulaire **en argument**: l'appelant, qui
    lit deja le catalogue, peut le verser. `None` (defaut) ne controle rien.

    Le court-circuit ne teste **que** le vocabulaire: le `value is None` qu'il
    portait etait une branche morte, mesuree en revue -- le seul appelant passe
    le resultat de `_require_text(timecode_reliability, ...)`, qui refuse `None`
    avant d'arriver ici, et `timecode_reliability` figure deja dans les champs
    obligatoires de `_project_plan`. Cet epic a deja paye deux branches sans
    emetteur; celle-ci n'en fait pas une troisieme.
    """
    if vocabulary is None:
        return value
    require_known_codes(
        (value,),
        _codes(vocabulary, f"{label} (vocabulaire)"),
        label=f"{label} hors du vocabulaire verse par l'appelant",
        error_type=EncodePrevizError,
    )
    return value


def _encode_codes(values: Any) -> tuple[str, ...]:
    """Vocabulaire ferme des constats transportes: inconnu refuse.

    **Ni deduplication ni tri**, et c'est voulu: la famille est transportee
    verbatim depuis 6.1, donc dans son ordre d'emission. `require_known_codes`
    accepte un code repete et le rend tel quel -- c'est le comportement recherche,
    pas une tolerance. Trier perdrait l'ordre; dedoublonner effacerait le fait
    qu'un constat a ete emis deux fois.
    """
    return require_known_codes(
        _codes(values, "warnings.encode"),
        ENCODE_PREVIZ_WARNING_CODES,
        label="Code de constat d'encodage inconnu",
        error_type=EncodePrevizError,
    )


#: Les seuls caracteres admis dans les deux membres d'une cadence rationnelle.
#: `str.isdigit()` ne convient pas: il accepte les chiffres arabo-indiens, que
#: `int()` lit ensuite sans broncher, et le document porterait une cadence que
#: personne ne peut relire en ASCII.
_DIGITS = frozenset("0123456789")


def _rational_rate(value: Any, label: str) -> str:
    """Cadence deja rationnelle: forme `num/den` exigee, **puis** canonicalisee.

    Deux gestes, et ils ne se remplacent pas. La forme est exigee d'abord parce
    que `exact_rate` accepte une chaine decimale (`"29.97"` rend `2997/100`)
    sans passer par le recalage NTSC de `codec_profiles`, la ou le meme flottant
    rend `30000/1001`: deux recettes, deux empreintes, pour la meme cadence. La
    canonicalisation vient ensuite parce que `"30"` et `"50/2"` designent la
    cadence de `"30/1"` et `"25/1"` sans s'ecrire comme elles.

    Idempotent sur ce que 6.1 produit: `EncodePlan.exact_frame_rate` sort de
    `codec_profiles.exact_frame_rate`, qui rend toujours une fraction reduite
    sous la forme `f"{numerateur}/{denominateur}"`.
    """
    text = _require_text(value, label)
    numerator, separator, denominator = text.partition("/")
    if (
        not separator
        or not numerator
        or not denominator
        or not set(numerator) <= _DIGITS
        or not set(denominator) <= _DIGITS
    ):
        raise EncodePrevizError(
            f"{label} doit etre une cadence rationnelle 'num/den' a deux membres "
            f"entiers, recu {value!r}. C'est la forme que 6.1 produit, et la "
            "seule qui rende une empreinte unique par cadence: une ecriture "
            "decimale en produirait une seconde pour la meme cadence."
        )
    return _exact_rate(text)


def _refusal_code(value: Any) -> str:
    """Motif de refus: un code du vocabulaire de refus de 6.1, et rien d'autre."""
    code = _require_text(value, "refusal_code")
    return require_known_codes(
        (code,),
        ENCODE_PREVIZ_REFUSAL_CODES,
        label="Motif de refus d'encodage inconnu",
        error_type=EncodePrevizError,
    )[0]


# --------------------------------------------------------------------------
# Construction
# --------------------------------------------------------------------------


def build_encode_previz(
    *,
    generated_at_utc: str,
    project_id: str,
    lot_id: str,
    profile_id: str,
    container: str,
    state: str = ENCODE_PREVIZ_STATE_PLANNED,
    lot_state: str | None = None,
    resolution: TargetResolutionLike | None = None,
    source_size: Sequence[int] | None = None,
    frames: Sequence[SequenceFrameLike] = (),
    exact_frame_rate: str | None = None,
    fps_target: Any = None,
    timecode: TimecodePlanLike | None = None,
    timecode_reliability: str | None = None,
    timecode_reliability_vocabulary: Sequence[str] | None = None,
    verdict: CompletenessVerdictLike | None = None,
    container_tags: Mapping[str, Any] | None = None,
    master_path_relative: str | None = None,
    estimated_bytes: Any = None,
    encoded_bytes: Any = None,
    nonconforming_files: Sequence[str] = (),
    empty_files: Sequence[str] = (),
    declared_bounds: Sequence[Any] = (None, None),
    refusal_code: str | None = None,
    refused_candidates: Sequence[str] = (),
    encode_warnings: Sequence[str] = (),
) -> EncodePreviz:
    """Projeter la decision de 6.1 en document de previz d'encodage.

    **Projection stricte**: rien n'est recalcule, rien n'est recompte, rien n'est
    reconcilie. Deux valeurs d'entree incoherentes entre elles ressortent telles
    quelles -- une cadence qui ne colle pas au timecode, un verdict qui annonce
    plus de frames que la sequence n'en porte, une resolution sans rapport avec
    la source. Seule exception, nommee: la cadence passe par la forme canonique
    unique `codec_profiles.exact_frame_rate`.

    Parameters
    ----------
    generated_at_utc:
        Horodatage UTC ISO 8601 suffixe `Z`, **fourni par l'appelant**: lire
        l'horloge ici rendrait le document non deterministe.
    project_id, lot_id, profile_id, container:
        Identite du document, presente dans les trois etats. `lot_id` est le lot
        retenu en `planned` / `encoded`, le lot **demande** en `refused`.
    state:
        `planned`, `encoded` ou `refused`.
    lot_state:
        Etat du lot au manifest, **entree de decision**: 6.1 refuse d'encoder en
        deca de `scan`. Obligatoire hors `refused`, interdit en `refused`.
    resolution:
        `encode.TargetResolution` **arretee** (`settle_resolution`). Sa `size`
        est la geometrie retenue.
    source_size:
        Geometrie des frames source, telle que 6.1 l'a sondee. Transportee pour
        que l'interface puisse montrer la mise a l'echelle; elle n'est jamais
        confrontee a la resolution retenue.
    frames:
        La sequence, **dans l'ordre ou elle sera encodee**. Chemins relatifs au
        dossier projet: `EncodePlan.frame_paths` porte des chemins absolus, et
        les relativiser ici serait un calcul.
    exact_frame_rate, fps_target:
        L'un **ou** l'autre, jamais les deux. `EncodePlan.exact_frame_rate` est
        deja sous la forme `"num/den"` et se transporte verbatim; `fps_target`
        est le flottant d'un appelant qui n'aurait que lui, et passe alors par
        `exact_rate`. Fournir les deux est refuse: deux recettes pour une meme
        cadence sont exactement ce que la forme canonique existe pour empecher.
    timecode:
        `encode.TimecodePlan`. `emitted`, `manifest_value` et `base_rate` sont
        **omis** du document quand ils manquent, jamais rendus `null`.
    timecode_reliability, timecode_reliability_vocabulary:
        Fiabilite declaree du timecode **pour le profil retenu**, transportee
        verbatim depuis `video_metadata.TECHNICAL_METADATA_MATRIX["timecode"]
        ["reliability"]`. Le vocabulaire vit chez le catalogue; l'appelant peut
        le verser pour que le controle passe du temps de test au temps de
        construction. `None` ne controle rien.
    verdict:
        `encode.CompletenessVerdict`, transporte tel quel. Son `found` n'est
        jamais confronte au cardinal de `frames`.
    container_tags:
        Les tags que le master portera, **transportes verbatim**: c'est le seul
        sous-dictionnaire libre du document, et il est canonicalise a la
        construction (voir :func:`_require_canonicalizable`) puis recopie en
        profondeur a la serialisation.
    master_path_relative:
        Chemin relatif du master a produire. **Constatation**: 6.1 le derive de
        `lot_id`, `profile_id`, du conteneur et du segment de resolution, donc
        de valeurs deja scellees par l'empreinte.
    estimated_bytes, encoded_bytes:
        Majoration du poids du master, fournie par 6.1, et poids **reel** une
        fois encode. Le second est obligatoire en `encoded` et interdit ailleurs.
    nonconforming_files, empty_files:
        Ce que 6.1 a ecarte de la sequence, par nom. Constatations.
    declared_bounds:
        `(first_frame_timecode, last_frame_timecode)` **declares par le lot**,
        tels quels, jamais recalcules. Ils se lisent en face des bornes reelles,
        qui sont les timecodes des frames de la sequence.
    refusal_code, refused_candidates:
        Motif du refus et candidats nommes, en etat `refused` uniquement.
    encode_warnings:
        Constats informatifs de 6.1 (`EncodePlan.findings`, ou
        `EncodeCommandResult.findings` apres execution), transportes verbatim,
        dans l'ordre, sans deduplication.

    Raises
    ------
    EncodePrevizError
        Etat inconnu, horodatage non conforme, code hors vocabulaire, champ
        obligatoire absent ou interdit pour l'etat, chemin absolu, resolution non
        arretee, cadence inexploitable, sous-dictionnaire non canonicalisable,
        entree structurellement incomplete.
    """
    if state not in ENCODE_PREVIZ_STATES:
        raise EncodePrevizError(
            f"Etat de previz inconnu: {state!r}. Vocabulaire ferme: "
            f"{', '.join(ENCODE_PREVIZ_STATES)}"
        )
    generated = normalize_generated_at_utc(
        generated_at_utc, error_type=EncodePrevizError, example=_GENERATED_AT_EXAMPLE
    )
    subject = EncodePrevizSubject(
        project_id=_require_text(project_id, "project_id"),
        lot_id=_require_text(lot_id, "lot_id"),
        profile_id=_require_text(profile_id, "profile_id"),
        container=_require_text(container, "container"),
    )
    warnings = EncodePrevizWarnings(encode=_encode_codes(encode_warnings))

    refused = state == ENCODE_PREVIZ_STATE_REFUSED
    refusal = _refusal_section(
        refused, refusal_code=refusal_code, refused_candidates=refused_candidates
    )
    if refused:
        _refuse_plan_material(
            lot_state=lot_state,
            resolution=resolution,
            source_size=source_size,
            frames=frames,
            exact_frame_rate=exact_frame_rate,
            fps_target=fps_target,
            timecode=timecode,
            timecode_reliability=timecode_reliability,
            timecode_reliability_vocabulary=timecode_reliability_vocabulary,
            verdict=verdict,
            container_tags=container_tags,
            master_path_relative=master_path_relative,
            estimated_bytes=estimated_bytes,
            encoded_bytes=encoded_bytes,
            nonconforming_files=nonconforming_files,
            empty_files=empty_files,
            declared_bounds=declared_bounds,
        )
        return EncodePreviz(
            previz_schema_version=PREVIZ_SCHEMA_VERSION,
            kind=ENCODE_PREVIZ_KIND,
            state=state,
            generated_at_utc=generated,
            subject=subject,
            warnings=warnings,
            refusal=refusal,
        )

    try:
        plan = _project_plan(
            state=state,
            lot_state=lot_state,
            resolution=resolution,
            source_size=source_size,
            frames=frames,
            exact_frame_rate=exact_frame_rate,
            fps_target=fps_target,
            timecode=timecode,
            timecode_reliability=timecode_reliability,
            timecode_reliability_vocabulary=timecode_reliability_vocabulary,
            verdict=verdict,
            container_tags=container_tags,
            master_path_relative=master_path_relative,
            estimated_bytes=estimated_bytes,
            encoded_bytes=encoded_bytes,
            nonconforming_files=nonconforming_files,
            empty_files=empty_files,
            declared_bounds=declared_bounds,
        )
    except EncodePrevizError:
        raise
    # Deux types, et **seulement** ceux dont l'emetteur est nomme et exerce.
    # `AttributeError`: le protocole est structurel, donc un producteur ampute
    # d'un champ arrive jusqu'ici. `TypeError`: la lecture d'un attribut execute
    # le code du producteur -- un champ calcule qui explose remonte son
    # exception a lui. `IndexError` et `KeyError` etaient attrapes sans emetteur
    # trouvable (les deux seules indexations portent sur un `tuple` deja
    # construit et sont precedees d'un controle de longueur; le module ne fait
    # aucun acces par cle), et cet epic a deja paye deux branches sans emetteur:
    # elles sont retirees plutot que laissees non mesurees.
    except (AttributeError, TypeError) as exc:
        raise EncodePrevizError(
            f"Entree structurellement incomplete ou malformee: {exc}"
        ) from exc

    return EncodePreviz(
        previz_schema_version=PREVIZ_SCHEMA_VERSION,
        kind=ENCODE_PREVIZ_KIND,
        state=state,
        generated_at_utc=generated,
        subject=subject,
        warnings=warnings,
        plan=plan,
        fingerprints=EncodePrevizFingerprints(
            decision=_fingerprint_of(
                _decision_fingerprint_payload(subject, plan), "fingerprints.decision"
            )
        ),
    )


def _refusal_section(
    refused: bool, *, refusal_code: Any, refused_candidates: Any
) -> EncodePrevizRefusal | None:
    """Ce que l'etat `refused` exige, et ce qu'il interdit ailleurs.

    Les candidats passent par `_names` **avant** le branchement, et non dans la
    seule branche du refus: c'est une correction de revue, sur une mesure. Le
    `tuple(refused_candidates)` de la branche non refusee -- c'est-a-dire le
    chemin nominal de tout document `planned` -- levait un `TypeError` nu sur
    `refused_candidates=42`, hors de la hierarchie que ce module promet, et il
    ne voyait ni la chaine explosee caractere par caractere ni la collection non
    ordonnee.
    """
    candidates = _names(refused_candidates, "refused_candidates")
    if not refused:
        if refusal_code is not None:
            raise EncodePrevizError(
                f"refusal_code n'a de sens qu'en etat "
                f"{ENCODE_PREVIZ_STATE_REFUSED!r}: un document qui annonce un "
                "encodage ne porte pas le motif de son refus"
            )
        if candidates:
            raise EncodePrevizError(
                f"refused_candidates n'a de sens qu'en etat "
                f"{ENCODE_PREVIZ_STATE_REFUSED!r}: des candidats ecartes "
                "n'existent que la ou aucun lot n'a ete retenu"
            )
        return None
    if refusal_code is None:
        raise EncodePrevizError(
            f"refusal_code est obligatoire en etat "
            f"{ENCODE_PREVIZ_STATE_REFUSED!r}: le motif vient du vocabulaire "
            "ferme de refus de 6.1 et se transporte verbatim"
        )
    return EncodePrevizRefusal(
        code=_refusal_code(refusal_code),
        candidates=candidates,
    )


def _refuse_plan_material(**material: Any) -> None:
    """Un document `refused` ne porte aucun element de plan.

    La garde est explicite plutot que silencieuse: un appelant qui a un plan en
    main et un refus decrit **deux** faits, et les fondre dans un document
    unique annoncerait un encodage que 6.1 vient de refuser. Le tuple par
    defaut de `declared_bounds` est le seul cas ou « fourni » ne veut pas dire
    « non vide », d'ou son traitement a part.

    `timecode_reliability_vocabulary` fait partie du materiel refuse depuis la
    revue: il en etait absent sans que rien ne le justifie, alors que les seize
    autres arguments de plan y sont. Sans consequence sur le document -- le
    vocabulaire n'y entre pas -- mais l'argument « un appelant qui a un plan en
    main et un refus decrit **deux** faits » vaut aussi pour lui.

    Les trois regimes de detection ne sont pas une inconsistance mais le calque
    des **defauts** de la signature: un argument de sequence a `()` pour defaut,
    donc « fourni » y veut dire « non vide »; un argument de mapping ou de
    scalaire a `None`, donc « fourni » y veut dire « pose ». `container_tags={}`
    est ainsi refuse la ou `frames=[]` est ignore, et c'est correct: le premier
    est une valeur posee, le second est le defaut ecrit autrement.
    """
    for label, value in material.items():
        if label == "declared_bounds":
            supplied = any(item is not None for item in _bounds_items(value))
        elif isinstance(value, (tuple, list)):
            supplied = bool(value)
        else:
            supplied = value is not None
        if supplied:
            raise EncodePrevizError(
                f"{label} n'a pas de sens en etat "
                f"{ENCODE_PREVIZ_STATE_REFUSED!r}: aucun encodage n'aura lieu, "
                "donc rien de ce qu'il aurait produit n'est connu"
            )


def _project_plan(
    *,
    state: str,
    lot_state: Any,
    resolution: Any,
    source_size: Any,
    frames: Any,
    exact_frame_rate: Any,
    fps_target: Any,
    timecode: Any,
    timecode_reliability: Any,
    timecode_reliability_vocabulary: Any,
    verdict: Any,
    container_tags: Any,
    master_path_relative: Any,
    estimated_bytes: Any,
    encoded_bytes: Any,
    nonconforming_files: Any,
    empty_files: Any,
    declared_bounds: Any,
) -> EncodePrevizPlan:
    """Projeter le plan de 6.1, valeur par valeur, sans en reconcilier aucune."""
    for label, value in (
        ("lot_state", lot_state),
        ("resolution", resolution),
        ("source_size", source_size),
        ("timecode", timecode),
        ("timecode_reliability", timecode_reliability),
        ("verdict", verdict),
        ("container_tags", container_tags),
        ("master_path_relative", master_path_relative),
        ("estimated_bytes", estimated_bytes),
    ):
        if value is None:
            raise EncodePrevizError(
                f"{label} est obligatoire en etat {state!r}: le document decrit "
                "ce que l'encodage produira, et cette valeur en fait partie"
            )
    if exact_frame_rate is not None and fps_target is not None:
        raise EncodePrevizError(
            "exact_frame_rate et fps_target sont exclusifs: deux recettes de "
            "cadence produiraient deux empreintes pour la meme cadence, et un "
            "consommateur qui les compare conclurait a tort a une peremption"
        )
    if exact_frame_rate is None and fps_target is None:
        raise EncodePrevizError(
            "La cadence du master est une entree de decision: fournir "
            "`exact_frame_rate` (forme 'num/den' du plan de 6.1) ou `fps_target` "
            "(le flottant, ramene a la forme canonique unique)"
        )

    width, height = _require_dimensions(resolution.size, "resolution.size")
    source_width, source_height = _require_dimensions(source_size, "source_size")
    first_bound, last_bound = _declared_bounds(declared_bounds)
    return EncodePrevizPlan(
        lot_state=_require_text(lot_state, "lot_state"),
        resolution=PrevizResolution(
            requested=_require_text(resolution.requested, "resolution.requested"),
            origin=_require_text(resolution.origin, "resolution.origin"),
            width_px=width,
            height_px=height,
            resolution_id=_optional_text(
                resolution.resolution_id, "resolution.resolution_id"
            ),
        ),
        source_width_px=source_width,
        source_height_px=source_height,
        fps_target_exact=(
            _rational_rate(exact_frame_rate, "exact_frame_rate")
            if exact_frame_rate is not None
            else _exact_rate(_require_number(fps_target, "fps_target"))
        ),
        timecode=PrevizTimecode(
            reliability=_known_value(
                _require_text(timecode_reliability, "timecode_reliability"),
                timecode_reliability_vocabulary,
                "timecode_reliability",
            ),
            emitted=_optional_text(timecode.emitted, "timecode.emitted"),
            manifest_value=_optional_text(
                timecode.manifest_value, "timecode.manifest_value"
            ),
            base_rate=_optional_text(timecode.base_rate, "timecode.base_rate"),
        ),
        completeness=_project_completeness(verdict),
        sequence=_project_sequence(frames),
        container_tags=_container_tags(container_tags),
        master_path_relative=_relative_path(
            master_path_relative, "master_path_relative"
        ),
        estimated_bytes=_require_cardinal(estimated_bytes, "estimated_bytes"),
        discarded=PrevizDiscarded(
            nonconforming_files=_names(nonconforming_files, "nonconforming_files"),
            empty_files=_names(empty_files, "empty_files"),
        ),
        declared_first_frame_timecode=first_bound,
        declared_last_frame_timecode=last_bound,
        encoded_bytes=(
            None
            if encoded_bytes is None
            else _require_cardinal(encoded_bytes, "encoded_bytes")
        ),
    )


def _bounds_items(value: Any) -> tuple[Any, Any]:
    """Le couple de bornes, controle de forme seulement.

    Extraite de `_declared_bounds` en revue pour que l'etat `refused` passe par
    la **meme** porte: `_refuse_plan_material` faisait `tuple(value)` sur
    `declared_bounds` sans garde, si bien que `build(state="refused",
    declared_bounds=42)` levait un `TypeError` nu -- hors de la hierarchie que
    ce module promet -- alors que le meme argument en etat `planned` etait
    correctement refuse. L'asymetrie etait involontaire.

    Le refus de collection **non ordonnee** est la garde ecrite quatre fois
    ailleurs et qui manquait ici. Mesure du defaut ferme: avec
    `declared_bounds={"00:00:00:00", "00:00:00:24"}`, le document publiait la
    premiere borne comme derniere un processus sur deux, selon la graine de
    hachage -- et fabriquait ainsi le diagnostic `BORNES_DE_LOT_DIVERGENTES` que
    cette fonction dit precisement ne pas vouloir effacer.
    """
    if isinstance(value, str):
        raise EncodePrevizError(
            f"declared_bounds doit etre un couple (premiere, derniere), pas une "
            f"chaine: {value!r}"
        )
    if not isinstance(value, Sequence):
        raise EncodePrevizError(
            "declared_bounds doit etre une sequence **ordonnee** (premiere, "
            f"derniere), recu {type(value).__name__}: {value!r}. Une collection "
            "non ordonnee intervertirait les deux bornes d'un processus a l'autre"
        )
    items = tuple(value)
    if len(items) != 2:
        raise EncodePrevizError(
            "declared_bounds doit porter exactement 2 composantes (premiere, "
            f"derniere), recu {value!r}"
        )
    return items[0], items[1]


def _declared_bounds(value: Any) -> tuple[str | None, str | None]:
    """Les deux bornes declarees par le lot, telles quelles.

    Elles ne sont **jamais** confrontees aux timecodes de la sequence: c'est
    precisement leur divergence que 6.1 nomme (`BORNES_DE_LOT_DIVERGENTES`), et
    la corriger ici effacerait le diagnostic.
    """
    first, last = _bounds_items(value)
    return (
        _optional_text(first, "declared_bounds[0]"),
        _optional_text(last, "declared_bounds[1]"),
    )


def _page_indexes(values: Any, label: str) -> tuple[int, ...]:
    """Des **index de page**, jamais des timecodes.

    Le piege que 6.1 a paye d'un bloquant: une page absente ne laisse aucun slot,
    donc aucun timecode n'est recalculable pour elle. Le verdict de 6.1 rend des
    index, et ce document ne promet rien d'autre.
    """
    if values is None:
        return ()
    if isinstance(values, str):
        raise EncodePrevizError(
            f"{label} doit etre une sequence d'index de page, pas une chaine: "
            f"{values!r}"
        )
    if not isinstance(values, Sequence):
        raise EncodePrevizError(
            f"{label} doit etre une sequence **ordonnee** d'index de page (liste "
            f"ou tuple), recu {type(values).__name__}: {values!r}"
        )
    return tuple(
        _require_int(index, f"{label}[{position}]")
        for position, index in enumerate(values)
    )


def _project_completeness(verdict: Any) -> PrevizCompleteness:
    """Le verdict de 6.1, transporte sans un recomptage."""
    return PrevizCompleteness(
        found=_require_cardinal(verdict.found, "verdict.found"),
        complete=_require_bool(verdict.complete, "verdict.complete"),
        missing_pages=_page_indexes(verdict.missing_pages, "verdict.missing_pages"),
        synthetic_present=_names(
            verdict.synthetic_present, "verdict.synthetic_present"
        ),
        synthetic_missing=_names(
            verdict.synthetic_missing, "verdict.synthetic_missing"
        ),
        expected=(
            None
            if verdict.expected is None
            else _require_cardinal(verdict.expected, "verdict.expected")
        ),
    )


def _project_sequence(frames: Any) -> tuple[PrevizSequenceFrame, ...]:
    """La sequence, dans l'ordre recu, jamais re-triee.

    L'ordre est une **entree de decision**: c'est celui dans lequel les images
    entrent dans le master. Re-trier ici -- par rang, par timecode, par nom --
    fabriquerait un master different de celui que 6.1 produira.
    """
    if isinstance(frames, str):
        raise EncodePrevizError(
            f"frames doit etre une sequence de frames, pas une chaine: {frames!r}"
        )
    if not isinstance(frames, Sequence):
        raise EncodePrevizError(
            "frames doit etre une sequence **ordonnee** (liste ou tuple), recu "
            f"{type(frames).__name__}: {frames!r}. Une collection non ordonnee "
            "rendrait deux masters differents pour la meme entree"
        )
    if not frames:
        raise EncodePrevizError(
            "frames est vide: un encodage sans image n'existe pas, et 6.1 refuse "
            "deja ce cas (DOSSIER_DE_LOT_VIDE) avant d'avoir un plan"
        )
    return tuple(
        PrevizSequenceFrame(
            output_rank=_require_int(frame.output_rank, f"frames[{position}].output_rank"),
            frame_path_relative=_relative_path(
                frame.frame_path_relative, f"frames[{position}].frame_path_relative"
            ),
            frame_timecode=_require_text(
                frame.frame_timecode, f"frames[{position}].frame_timecode"
            ),
            # Inconditionnel, `false` compris (EPIC5-ARB-8): un drapeau omis se
            # relit « vraie frame ».
            synthetic=_require_bool(frame.synthetic, f"frames[{position}].synthetic"),
        )
        for position, frame in enumerate(frames)
    )


def _decision_fingerprint_payload(
    subject: EncodePrevizSubject, plan: EncodePrevizPlan
) -> dict[str, Any]:
    """Les entrees de decision de l'encodage, et rien d'autre.

    Ni le chemin du master, ni la fiabilite du timecode, ni les mires, ni le
    verdict, ni l'estimation de taille, ni les avertissements: une empreinte
    sensible a une constatation signalerait des peremptions imaginaires.
    """
    payload: dict[str, Any] = {
        "fps_target_exact": plan.fps_target_exact,
        "lot_id": subject.lot_id,
        "lot_state": plan.lot_state,
        "profile_id": subject.profile_id,
        "resolution_height_px": plan.resolution.height_px,
        "resolution_width_px": plan.resolution.width_px,
        "sequence_digest": _sequence_digest(plan.sequence),
    }
    # Omis, jamais `None` (motif 3.5): l'empreinte d'un lot sans timecode reste
    # ainsi identique a ce qu'elle serait si le champ n'existait pas.
    if plan.timecode.base_rate is not None:
        payload["timecode_base_rate"] = plan.timecode.base_rate
    if plan.timecode.emitted is not None:
        payload["timecode_start"] = plan.timecode.emitted
    _check_fingerprint_contract(
        payload,
        DECISION_FINGERPRINT_FIELDS,
        DECISION_FINGERPRINT_OPTIONAL_FIELDS,
        "DECISION_FINGERPRINT_FIELDS",
    )
    return payload


def _sequence_digest(sequence: Sequence[PrevizSequenceFrame]) -> str:
    """Sous-condensat de la sequence ordonnee.

    Mecanisme d'`ingested_pages_digest` de 5.8, et il n'y en a pas d'autre: un
    tuple de noms de champs **scalaires** ne peut pas porter une collection, si
    bien qu'une empreinte batie dessus serait insensible a l'ordre des images.
    Le condensat porte sur une **liste**, donc l'ordre y entre.
    """
    return _fingerprint_of(
        [_sequence_frame_digest_entry(frame) for frame in sequence],
        "sequence_digest",
    )


def _sequence_frame_digest_entry(frame: PrevizSequenceFrame) -> dict[str, Any]:
    """Ce qu'une frame apporte au sous-condensat.

    Les valeurs sont celles que le document **publie**, ce qui est la seule
    facon qu'une empreinte scelle ce qu'elle montre.
    """
    entry = {
        "frame_path_relative": frame.frame_path_relative,
        "frame_timecode": frame.frame_timecode,
        "output_rank": frame.output_rank,
    }
    _check_fingerprint_contract(
        entry, SEQUENCE_FRAME_DIGEST_FIELDS, (), "SEQUENCE_FRAME_DIGEST_FIELDS"
    )
    return entry


def _check_fingerprint_contract(
    payload: Mapping[str, Any],
    fields: Sequence[str],
    optional: Sequence[str],
    name: str,
) -> None:
    """Garde-fou de contrat, pas un calcul.

    Un payload d'empreinte ne peut ni porter un champ absent de la constante
    exportee, ni en omettre un qui n'est pas declare optionnel. Sans elle, une
    constante et son payload divergeraient en silence et l'empreinte cesserait
    de sceller ce que le tuple annonce.
    """
    unknown = sorted(set(payload) - set(fields))
    missing = sorted(set(fields) - set(payload) - set(optional))
    if unknown or missing:
        raise EncodePrevizError(
            f"Le payload d'empreinte diverge de {name} (champs inattendus: "
            f"{unknown}, champs manquants: {missing}, attendu {list(fields)})"
        )


# --------------------------------------------------------------------------
# Serialisation
# --------------------------------------------------------------------------


def _resolution_to_json_dict(resolution: PrevizResolution) -> dict[str, Any]:
    document: dict[str, Any] = {
        "requested": resolution.requested,
        "origin": resolution.origin,
        "width_px": resolution.width_px,
        "height_px": resolution.height_px,
    }
    if resolution.resolution_id is not None:
        document["resolution_id"] = resolution.resolution_id
    return document


def _timecode_to_json_dict(timecode: PrevizTimecode) -> dict[str, Any]:
    # `reliability` est inconditionnel: c'est une propriete du profil, toujours
    # connue. Les trois autres sont **omis** quand ils manquent, jamais `null`.
    document: dict[str, Any] = {"reliability": timecode.reliability}
    if timecode.emitted is not None:
        document["emitted"] = timecode.emitted
    if timecode.manifest_value is not None:
        document["manifest_value"] = timecode.manifest_value
    if timecode.base_rate is not None:
        document["base_rate"] = timecode.base_rate
    return document


def _completeness_to_json_dict(completeness: PrevizCompleteness) -> dict[str, Any]:
    document: dict[str, Any] = {
        "found": completeness.found,
        "complete": completeness.complete,
        "missing_pages": list(completeness.missing_pages),
        "synthetic_present": list(completeness.synthetic_present),
        "synthetic_missing": list(completeness.synthetic_missing),
    }
    if completeness.expected is not None:
        document["expected"] = completeness.expected
    return document


def _plan_to_json_dict(plan: EncodePrevizPlan) -> dict[str, Any]:
    document: dict[str, Any] = {
        "lot_state": plan.lot_state,
        "resolution": _resolution_to_json_dict(plan.resolution),
        "source_size": {
            "width_px": plan.source_width_px,
            "height_px": plan.source_height_px,
        },
        "fps_target_exact": plan.fps_target_exact,
        "timecode": _timecode_to_json_dict(plan.timecode),
        "completeness": _completeness_to_json_dict(plan.completeness),
        "sequence": [
            {
                "output_rank": frame.output_rank,
                "frame_path_relative": frame.frame_path_relative,
                "frame_timecode": frame.frame_timecode,
                # Inconditionnel des qu'une frame existe (EPIC5-ARB-8): le regime
                # « champ optionnel omis » ne s'y applique pas.
                "synthetic": frame.synthetic,
            }
            for frame in plan.sequence
        ],
        # Copie **profonde**: `dict(...)` ne recopie que le premier niveau, donc
        # muter un sous-dict du document rendu mutait l'objet dit « gele », deux
        # appels successifs ne rendaient plus le meme JSON et l'empreinte ne
        # correspondait plus a son propre contenu -- regression reelle du
        # 2026-08-05 chez 3.5.
        "container_tags": copy.deepcopy(dict(plan.container_tags)),
        "master_path_relative": plan.master_path_relative,
        "estimated_bytes": plan.estimated_bytes,
        "discarded": {
            "nonconforming_files": list(plan.discarded.nonconforming_files),
            "empty_files": list(plan.discarded.empty_files),
        },
    }
    bounds: dict[str, Any] = {}
    if plan.declared_first_frame_timecode is not None:
        bounds["first_frame_timecode"] = plan.declared_first_frame_timecode
    if plan.declared_last_frame_timecode is not None:
        bounds["last_frame_timecode"] = plan.declared_last_frame_timecode
    # Section entiere omise quand le lot n'en declare aucune: un lot ne du scan
    # ne porte pas ces champs, et un objet vide serait une section morte.
    if bounds:
        document["declared_bounds"] = bounds
    if plan.encoded_bytes is not None:
        document["encoded_bytes"] = plan.encoded_bytes
    return document


def encode_previz_to_json_dict(previz: EncodePreviz) -> dict[str, Any]:
    """Forme JSON **normative** du document, deterministe et serialisable.

    Nom volontairement distinct de `previz_to_json_dict` (3.5), de
    `pdf_previz_to_json_dict` (4.9) et de `scan_previz_to_json_dict` (5.8):
    l'homonymie est exactement ce qu'ARB-14 a du resorber une fois.

    Aucun objet Python non JSON, aucune `Fraction` nue, aucun `Path`, aucun
    octet d'image, aucun base64. Passer le resultat a
    `previz_common.canonical_json` produit la meme chaine octet pour octet d'un
    processus a l'autre.
    """
    document: dict[str, Any] = {
        # Socle d'enveloppe partage: les quatre champs de tete sont rendus par
        # `previz_common.envelope_head`, avec les valeurs **du document** et
        # jamais des constantes relues -- un document construit sous une autre
        # version de schema doit se rendre tel qu'il a ete construit.
        **envelope_head(
            schema_version=previz.previz_schema_version,
            kind=previz.kind,
            state=previz.state,
            generated_at_utc=previz.generated_at_utc,
        ),
        "subject": {
            "project_id": previz.subject.project_id,
            "lot_id": previz.subject.lot_id,
            "profile_id": previz.subject.profile_id,
            "container": previz.subject.container,
        },
    }
    if previz.plan is not None:
        document["plan"] = _plan_to_json_dict(previz.plan)
    if previz.refusal is not None:
        document["refusal"] = {
            "code": previz.refusal.code,
            "candidates": list(previz.refusal.candidates),
        }
    document["warnings"] = {"encode": list(previz.warnings.encode)}
    if previz.fingerprints is not None:
        document["fingerprints"] = {"decision": previz.fingerprints.decision}
    return document
