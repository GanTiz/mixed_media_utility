"""Contrat de donnees de previz d'extraction (story 3.5).

Perimetre
---------
Ce module possede **la forme du document de previz d'extraction**, et rien
d'autre: ses champs, son versionnement, sa serialisation JSON, sa regle de
canonicalisation et ses empreintes de fraicheur. Il est le **contrat de
donnees**, pas une interface: aucune ligne de code d'affichage, aucun choix
de techno d'interface, aucun producteur de vignettes.

Il est **pur**: aucun `subprocess`, `cv2`, `PIL`, `numpy`, aucun ffmpeg /
ffprobe, aucun `open()`, aucune ecriture `pathlib`, aucune lecture de
manifest, aucun `argparse`, aucun `print`, aucune dependance nouvelle dans
`requirements.txt`, aucun import d'une bibliotheque d'interface graphique.
Cette purete est verrouillee par une analyse AST du fichier source dans
`tests/unit/test_extraction_previz.py` (liste blanche des imports **et**
absence d'appel aux noms `open`, `print`, `input`, `exec`, `eval`: ces deux
dernieres sont des primitives, aucun import ne les trahit).

Frontiere Epic 3 / Epic 7
-------------------------
Appartient a ce module: la forme du document, sa derivation sans duplication
depuis les stories 3.1 / 3.2 / 3.3, la contrainte de chemins relatifs, le
vocabulaire de vignette, la detection de peremption.

N'appartient pas a ce module, et n'y sera jamais ajoute sans rouvrir la
frontiere: le choix du framework, le modele d'application, le packaging, la
mise en page, la navigation, le theme, le format d'image des vignettes, le
protocole d'appel entre la previz et son afficheur, la politique de cache.
Le document JSON est la forme **normative**; les dataclasses gelees ne sont
qu'un confort de typage pour un consommateur in-process. Imposer l'objet
Python comme seul contrat exclurait d'office un consommateur hors-processus
ou distant, donc prejugerait de l'Epic 7.

Projection, jamais calcul
-------------------------
`build_extraction_previz` **projette**. Chaque champ de frame vient
litteralement de `FrameSelection` / `SelectedFrame` (story 3.2), chaque champ
source vient litteralement du rapport de la story 3.3. Aucune arithmetique de
cadence, aucun arrondi, aucune conversion de timecode, aucun comptage de
fichiers, aucune sonde, aucune verification croisee entre deux valeurs
d'entree: des entrees incoherentes ressortent incoherentes et verbatim, ce
qui est exactement le comportement teste.

Consequences directes:

* `expected_frame_count` vient de 3.2, jamais d'un `glob` (un comptage disque
  ferait passer une extraction partielle pour complete);
* `frames_present_count` est **fourni par l'appelant** en regime `extracted`,
  jamais compte ici;
* `subject.project_id` est fourni par l'appelant (l'objet de resultat de 3.1
  ne le porte pas), jamais derive ici;
* le rapport source est obtenu par `source_confirmation.source_report_to_json_dict`,
  seul serialiseur du rapport dans le produit. Ce module n'en ecrit pas un
  second (`decisions-2026-08-02.md`).

Le chemin du rush source n'est **pas** un champ du contrat, ni absolu ni
relatif: depuis la story 2.5 le rush n'a aucune obligation de vivre dans le
dossier projet, et un chemin machine-dependant n'a pas sa place dans un
document destine a circuler. Tous les chemins presents (dossier de lot,
fichiers de frames, vignettes) sont relatifs au dossier projet et en
separateur POSIX. Ce module n'ecrit **pas** de detecteur de chemin absolu: il
existe deja (`io/manifest._iter_absolute_path_violations`) et c'est lui que le
test importe.

Forme canonique d'une cadence
-----------------------------
Une seule, sans exception: `codec_profiles.exact_frame_rate`, chaine
`"num/den"` a denominateur toujours explicite (`"30/1"`, `"24000/1001"`).
Jamais `str(Fraction)` (qui rend `"30"`), jamais un flottant, jamais
`f"{fps}"`. C'est la forme deja imposee par la story 3.4: deux recettes
produiraient deux empreintes pour la meme selection, et un consommateur qui
les compare conclurait a tort a une peremption.

Canonicalisation et empreintes
------------------------------
Depuis la story 5.8, la recette vit dans `previz_common` -- domicile commun aux
trois jumelles, ouvert par la jonction que le `deferred-work.md` avait
consignee le 2026-08-06. Elle reste **re-exportee ici sous ses noms actuels**
(`canonical_json`, `fingerprint_of`, `FINGERPRINT_PREFIX`, presents dans
`__all__`): les stories 5.1 et 5.2 instruisent leurs devs de les importer
depuis ce module, et `tests/unit/test_pdf_composition.py` consomme
`extraction_previz.fingerprint_of`. La regle, elle, est inchangee et unique:
`canonical_json(obj)` rend
`json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(",", ":"))`;
`fingerprint_of(obj)` l'encode en UTF-8, le passe a `hashlib.sha256` et
prefixe `"sha256-v1:"`. Le prefixe porte la version d'algorithme, comme
`lots[].frame_timecodes_digest` (story 3.4).

Trois empreintes, trois portees **non comparables entre elles**:

* `fingerprints.selection` — les seules entrees de decision de 3.2
  (`fps_source_exact`, `fps_target_exact`, `source_frame_count`,
  `source_start_timecode`, `rounding_policy`, `timecode_base`, plus
  `source_in_timecode` / `source_out_timecode` **quand la selection est
  bornee**) et rien d'autre. Repond a: la selection montree est-elle encore
  celle qui sera produite ? Deliberement insensible aux vignettes et aux
  champs d'affichage: ajouter ou retirer une vignette ne la change pas.
  Les deux bornes y sont entrees a la revue du 2026-08-06: elles decident
  quelles images sortent, donc les omettre faisait repondre « a jour » a une
  previz calculee pour un autre extrait. Elles sont **omises** quand la
  selection ne les porte pas, de sorte que l'empreinte d'un lot non borne est
  restee identique au bit pres a celle d'avant l'extension.
* `fingerprints.source_report` — la forme JSON du rapport de la couche 1 de
  3.3. Repond a: les metadonnees montrees sont-elles encore celles qui seront
  confirmees ?
* `fingerprints.source_signature` — optionnel, **fourni par l'appelant**,
  jamais calcule ici (ce serait de l'I/O). Recette recommandee: sha256 sur
  `{taille en octets, mtime, fps_source_exact, source_frame_count}`. C'est un
  **detecteur de changement heuristique** valable dans une session locale, pas
  une preuve d'integrite: un sha256 complet d'un rush de plusieurs centaines
  de gigaoctets est hors budget et ne sera pas demande.

L'empreinte de 3.4 (`lots[].frame_timecodes_digest`) partage le prefixe et la
forme de cadence mais canonicalise autre chose (en-tete + lignes de
timecodes), sur une autre portee: les deux valeurs ne sont pas comparables et
ne doivent jamais l'etre.

Une previz n'autorise rien
--------------------------
Le document est **consultatif**. Il ne porte aucun consentement, aucun etat de
confirmation exploitable comme accord, aucun declencheur. Le consentement
appartient a la story 3.3 et se rejoue integralement au moment du lancement,
quelle que soit la fraicheur du document. Ce module n'appelle que la couche de
**construction pure** de 3.3 (`source_report_to_json_dict` et la garde de
chemin relatif), ne cite jamais le nom de sa couche d'interaction, et n'expose
aucune fonction qui lance, confirme ou valide une extraction. Un test
verrouille ces absences, textuellement et par analyse AST.

Ce qui precede est une discipline d'appel, **pas** une garantie technique, et
la version precedente de cette docstring se trompait en l'affirmant: la story
3.3 livre ses trois couches dans un fichier unique, donc
`from .source_confirmation import ...` charge l'ensemble, couche d'interaction
comprise. Rendre l'affirmation vraie supposerait de scinder
`source_confirmation.py`, ce qui appartient a la story 3.3 et non a celle-ci
(revue du 2026-08-05).

Vignettes: reference, jamais pixels
-----------------------------------
Chaque frame porte un bloc `thumbnail` decrivant **ou** trouver une image,
jamais l'image. Aucun octet, aucun base64: deux cents vignettes encodees
produiraient un document illisible, non diffable et impossible a journaliser.

`state` vaut `absent` / `exact` / `approximate`, `origin` vaut `None` /
`rush_decode` / `extracted_frame`. Un document **sans aucune vignette est
valide et complet**, et c'est le defaut. Une vignette approximative n'est
jamais presentee comme exacte: `state == "approximate"` **exige**
`decoded_source_index`, et aucun autre etat ne l'accepte. Obtenir la vignette
du rang `n` avant extraction impose de decoder le rush a `source_index(n)`:
un `-ss` place avant `-i` est rapide mais atterrit sur une image cle voisine,
donc le producteur qui prend cette voie doit le declarer. Apres extraction la
question disparait: le TIFF existe (`origin = "extracted_frame"`,
`state = "exact"`), sans rush et sans ffmpeg.

Aucun producteur de vignettes n'est implemente ici, deliberement: il n'existe
aujourd'hui aucun consommateur, et ecrire un decodeur maintenant serait du
code mort ecrit contre un besoin d'affichage inconnu. Ce module garantit que
le jour ou un fournisseur est ecrit, le contrat n'a pas a bouger.

Cas degrades
------------
Ils produisent un document **valide et partiel**, jamais une exception ni une
previz bloquee. Ils sont signales par un vocabulaire ferme de codes stables
ASCII (`PREVIZ_WARNING_CODES`). Le module etant pur, il n'en **emet** aucun
lui-meme: il les recoit de l'appelant, refuse a la construction tout code
hors vocabulaire, et les place dans `warnings.previz`. Jamais de prose.

Les trois familles d'avertissements sont transportees **verbatim et
separement**, sans fusion, sans reecriture, sans traduction:
`warnings.selection` (codes de 3.2), `warnings.previz` (codes ci-dessus),
`warnings.confirmation` (codes stables de 3.3). Etat reel du contrat de 3.3:
elle n'expose **aucun** code d'avertissement stable, sa reserve colorimetrique
vit dans la liste triee des champs `source_*` absents et dans le booleen
`unknown_color_accepted`, et son bloc d'avertissement est de la prose produite
par sa couche de rendu. `warnings.confirmation` vaut donc `[]` aujourd'hui, et
ce module ne fabrique **jamais** un code pour combler ce vide: la reserve
colorimetrique se lit dans `source_report`, transporte verbatim.

Enveloppe reutilisable
----------------------
`previz_schema_version`, `kind`, `state`, `generated_at_utc`, `subject`,
`warnings`, `fingerprints` forment une enveloppe generique, reprise telle
quelle par les previz jumelles 4.9 (PDF, `kind = "makepdf"`) et 5.8 (scan,
`kind = "scan"`), et a reprendre par 6.4 (encodage) avec son propre `kind`.
Ses champs de tete et sa recette d'empreinte vivent dans `previz_common`
depuis 5.8. Ce qui suit n'y vit pas et reste une **convention** a respecter,
pas un framework a construire: le vocabulaire de vignette, la regle « document
valide sans aucune image », la separation des familles d'avertissements, la
contrainte de chemins relatifs, la forme canonique unique des cadences et la
regle « une previz n'autorise rien ».

Convention d'ecriture: messages en francais **sans accents**, comme
`video_metadata.py`, `io/manifest.py`, `codec_profiles.py` et
`source_confirmation.py`, pour survivre a une console `cp1252`.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

from .previz_common import (
    FINGERPRINT_PREFIX,
    PREVIZ_SCHEMA_VERSION,
    PREVIZ_STATE_PLANNED,
    canonical_json,
    envelope_head,
    exact_rate as _common_exact_rate,
    fingerprint_of,
    normalize_generated_at_utc,
    optional_relative_path as _common_optional_relative_path,
    optional_text as _common_optional_text,
    require_int as _common_require_int,
    require_known_codes,
    require_relative_path as _common_relative_path,
    require_text as _common_require_text,
)
from .source_confirmation import SourceReport, source_report_to_json_dict

__all__ = [
    "PREVIZ_SCHEMA_VERSION",
    "PREVIZ_KIND_EXTRACTION",
    "PREVIZ_STATE_PLANNED",
    "PREVIZ_STATE_EXTRACTED",
    "PREVIZ_STATES",
    "THUMBNAIL_STATE_ABSENT",
    "THUMBNAIL_STATE_EXACT",
    "THUMBNAIL_STATE_APPROXIMATE",
    "THUMBNAIL_STATES",
    "THUMBNAIL_ORIGIN_RUSH_DECODE",
    "THUMBNAIL_ORIGIN_EXTRACTED_FRAME",
    "THUMBNAIL_ORIGINS",
    "THUMBNAILS_UNAVAILABLE_NO_FFMPEG",
    "THUMBNAILS_PARTIAL_BUDGET",
    "THUMBNAIL_DECODE_FAILED",
    "THUMBNAILS_APPROXIMATE_SEEK",
    "LOT_INCOMPLETE",
    "SOURCE_UNREADABLE",
    "PREVIZ_WARNING_CODES",
    "SELECTION_FINGERPRINT_FIELDS",
    "SELECTION_FINGERPRINT_OPTIONAL_FIELDS",
    "FINGERPRINT_PREFIX",
    "ExtractionPrevizError",
    "ThumbnailRef",
    "ABSENT_THUMBNAIL",
    "PrevizSubject",
    "PrevizFrame",
    "PrevizWarnings",
    "PrevizFingerprints",
    "ExtractionPreviz",
    "build_extraction_previz",
    "previz_to_json_dict",
    "canonical_json",
    "fingerprint_of",
]


# --------------------------------------------------------------------------
# Vocabulaire fige
# --------------------------------------------------------------------------

#: `kind` de la charge specifique portee par ce module. Les previz jumelles
#: 4.9 / 5.8 / 6.4 reprennent l'enveloppe avec leur propre `kind`.
#:
#: `PREVIZ_SCHEMA_VERSION`, `PREVIZ_STATE_PLANNED` et `FINGERPRINT_PREFIX` ne
#: sont plus declares ici mais dans `previz_common` (jonction ouverte par la
#: story 5.8): ils sont re-exportes sous leurs noms actuels et restent dans
#: `__all__`, les stories 5.1 et 5.2 instruisant leurs devs de les importer
#: **depuis ce module**.
PREVIZ_KIND_EXTRACTION = "extraction"

PREVIZ_STATE_EXTRACTED = "extracted"
PREVIZ_STATES: tuple[str, ...] = (PREVIZ_STATE_PLANNED, PREVIZ_STATE_EXTRACTED)

THUMBNAIL_STATE_ABSENT = "absent"
THUMBNAIL_STATE_EXACT = "exact"
THUMBNAIL_STATE_APPROXIMATE = "approximate"
THUMBNAIL_STATES: tuple[str, ...] = (
    THUMBNAIL_STATE_ABSENT,
    THUMBNAIL_STATE_EXACT,
    THUMBNAIL_STATE_APPROXIMATE,
)

THUMBNAIL_ORIGIN_RUSH_DECODE = "rush_decode"
THUMBNAIL_ORIGIN_EXTRACTED_FRAME = "extracted_frame"
#: `None` est une valeur legitime du vocabulaire: une vignette absente n'a pas
#: d'origine, et ce n'est pas un trou dans le contrat.
THUMBNAIL_ORIGINS: tuple[str | None, ...] = (
    None,
    THUMBNAIL_ORIGIN_RUSH_DECODE,
    THUMBNAIL_ORIGIN_EXTRACTED_FRAME,
)

# Vocabulaire FERME des codes de degradation. Le module pur n'en emet aucun:
# il les recoit de l'appelant et refuse tout code hors de ce tuple.
THUMBNAILS_UNAVAILABLE_NO_FFMPEG = "THUMBNAILS_UNAVAILABLE_NO_FFMPEG"
THUMBNAILS_PARTIAL_BUDGET = "THUMBNAILS_PARTIAL_BUDGET"
THUMBNAIL_DECODE_FAILED = "THUMBNAIL_DECODE_FAILED"
THUMBNAILS_APPROXIMATE_SEEK = "THUMBNAILS_APPROXIMATE_SEEK"
SOURCE_UNREADABLE = "SOURCE_UNREADABLE"

#: Le lot ne porte pas le nombre d'images qu'il annonce (ARB-13,
#: `decisions-2026-08-05.md`). Emis par ce module -- et non recu de l'appelant
#: comme les codes de vignette -- parce qu'il se deduit de la seule
#: confrontation de deux champs deja presents dans le document.
#:
#: Les deux compteurs n'etaient jamais confrontes: un document annoncant 4
#: images attendues et 4242 presentes etait construit sans une objection, et
#: aucun code du vocabulaire ne permettait de declarer un lot tronque, alors
#: que c'est la premiere chose qu'une interface doit montrer.
LOT_INCOMPLETE = "LOT_INCOMPLETE"

PREVIZ_WARNING_CODES: tuple[str, ...] = (
    LOT_INCOMPLETE,
    THUMBNAILS_UNAVAILABLE_NO_FFMPEG,
    THUMBNAILS_PARTIAL_BUDGET,
    THUMBNAIL_DECODE_FAILED,
    THUMBNAILS_APPROXIMATE_SEEK,
    SOURCE_UNREADABLE,
)

#: Les **seules** entrees de decision de la story 3.2 qui entrent dans
#: `fingerprints.selection`. Ce tuple est le contrat: y ajouter un champ
#: d'affichage rendrait l'empreinte sensible a ce qui ne decide rien.
#:
#: Les bornes de la story 3.7 y sont entrees a la revue du 2026-08-06, et le
#: motif de l'omission initiale merite d'etre garde: elles avaient ete jugees
#: « nouvelles » plutot que relues pour ce qu'elles sont, c'est-a-dire des
#: entrees de decision au meme titre que la cadence. Mesure avant correctif:
#: un extrait des images 25 a 245, un autre des images 500 a 745 et le rush
#: entier -- trois selections sans une seule image commune -- rendaient la
#: **meme** empreinte. Une empreinte qui existe pour dire « la selection
#: montree est-elle encore celle qui sera produite » repondait oui a tort.
SELECTION_FINGERPRINT_FIELDS: tuple[str, ...] = (
    "fps_source_exact",
    "fps_target_exact",
    "rounding_policy",
    "source_frame_count",
    "source_in_timecode",
    "source_out_timecode",
    "source_start_timecode",
    "timecode_base",
)

#: Les deux seuls champs du contrat qui peuvent manquer. **Omis** quand la
#: selection n'est pas bornee -- jamais ecrits a `null` -- pour deux raisons
#: qui vont dans le meme sens: c'est la regle cardinale du projet, et c'est ce
#: qui garde l'empreinte d'un lot non borne rigoureusement identique a celle
#: qu'il avait avant que le contrat ne soit etendu.
SELECTION_FINGERPRINT_OPTIONAL_FIELDS: tuple[str, ...] = (
    "source_in_timecode",
    "source_out_timecode",
)

#: Date d'exemple citee dans le refus d'horodatage de ce module. Elle n'a
#: d'effet que sur le texte du message: la conserver garde le refus
#: rigoureusement inchange apres l'extraction de la regle dans `previz_common`.
_GENERATED_AT_EXAMPLE = "2026-08-03T12:00:00Z"


class ExtractionPrevizError(ValueError):
    """Entree refusee a la construction du document.

    Derive de `ValueError` pour rester capturable par un appelant generique.
    Elle ne signale **jamais** un cas degrade (ffmpeg absent, rush illisible,
    vignette ratee): ceux-la produisent un document valide et partiel, porte
    par `warnings.previz`. Elle signale une entree qui rendrait le document
    lui-meme faux ou trompeur.
    """


# --------------------------------------------------------------------------
# Contrat consomme de la story 3.2, sans dependance de module
# --------------------------------------------------------------------------


class _SelectedFrameLike(Protocol):
    output_rank: int
    source_index: int
    frame_timecode: str


class FrameSelectionLike(Protocol):
    """Sous-ensemble de `frame_selection.FrameSelection` reellement consomme.

    Ce module lit ces champs et **aucun autre**; il ne re-trie jamais la
    sequence (`output_rank` est l'ordre canonique du lot) et ne recalcule
    aucune des valeurs qu'il transporte.
    """

    frames: Sequence[_SelectedFrameLike]
    fps_source: Any
    fps_target: Any
    source_frame_count: int
    expected_frame_count: int
    source_tail_frames: int
    rounding_policy: str
    timecode_base: str
    timecode_base_fps: Any
    source_start_timecode: str | None
    warnings: Sequence[str]
    # Story 3.7. Lus par `getattr` avec repli, donc tolerablement absents: le
    # Protocol est structurel et une selection d'avant la 3.7 doit continuer
    # de passer.
    source_in_timecode: str | None
    source_out_timecode: str | None


# --------------------------------------------------------------------------
# Canonicalisation et empreintes -- point unique, desormais partage
# --------------------------------------------------------------------------
#
# `canonical_json`, `fingerprint_of` et `FINGERPRINT_PREFIX` vivent dans
# `previz_common` depuis la story 5.8 et sont **re-exportes ici sous leurs noms
# actuels**: `tests/unit/test_pdf_composition.py` consomme
# `extraction_previz.fingerprint_of`, `test_extraction_previz.py` parcourt
# `__all__`, et les stories 5.1 et 5.2 instruisent leurs devs de les importer
# depuis ce module. La recette, elle, reste unique -- c'est tout l'objet de la
# jonction.


def _exact_rate(fps: Any) -> str:
    """Seule fonction de serialisation de cadence du module.

    Toute cadence du document passe par ici, donc par
    `codec_profiles.exact_frame_rate`: denominateur toujours explicite.
    """
    return _common_exact_rate(fps, error_type=ExtractionPrevizError)


# --------------------------------------------------------------------------
# Vignettes: reference, jamais pixels
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ThumbnailRef:
    """Reference de vignette. Aucun octet d'image, aucun base64.

    `decoded_source_index` est renseigne **uniquement** quand
    `state == "approximate"`: c'est ce qui rend l'ecart visible entre l'image
    demandee et l'image reellement decodee. Une vignette approximative
    etiquetee exacte serait une corruption silencieuse; le constructeur la
    refuse.
    """

    state: str = THUMBNAIL_STATE_ABSENT
    origin: str | None = None
    path_relative: str | None = None
    decoded_source_index: int | None = None

    def __post_init__(self) -> None:
        if self.state not in THUMBNAIL_STATES:
            raise ExtractionPrevizError(
                f"Etat de vignette inconnu: {self.state!r}. Vocabulaire ferme: "
                f"{', '.join(THUMBNAIL_STATES)}"
            )
        if self.origin not in THUMBNAIL_ORIGINS:
            raise ExtractionPrevizError(
                f"Origine de vignette inconnue: {self.origin!r}. Vocabulaire ferme: "
                "None, " + ", ".join(str(origin) for origin in THUMBNAIL_ORIGINS[1:])
            )
        if self.path_relative is not None:
            if not isinstance(self.path_relative, str):
                raise ExtractionPrevizError(
                    f"path_relative doit etre une chaine relative ou None, recu "
                    f"{self.path_relative!r}"
                )
            _relative_path(self.path_relative, "thumbnail.path_relative")

        # Les deux moities manquantes du vocabulaire (revue du 2026-08-05). Le
        # constructeur ne verrouillait qu'un seul couplage -- approximate exige
        # decoded_source_index -- et laissait passer les contradictions
        # symetriques: une vignette declaree presente sans dire ou elle est, et
        # une vignette declaree absente qui porte pourtant un chemin et une
        # origine. Un consommateur qui suit le document tombe alors soit sur
        # rien, soit sur une image qu'on lui a dit de ne pas afficher.
        if self.state == THUMBNAIL_STATE_ABSENT:
            if self.path_relative is not None:
                raise ExtractionPrevizError(
                    "Vignette absente portant un chemin: une vignette declaree "
                    f"absente ne localise rien, recu {self.path_relative!r}"
                )
            if self.origin is not None:
                raise ExtractionPrevizError(
                    "Vignette absente portant une origine: une vignette declaree "
                    f"absente ne vient de nulle part, recu {self.origin!r}"
                )
        else:
            if self.path_relative is None:
                raise ExtractionPrevizError(
                    f"Vignette '{self.state}' sans path_relative: une vignette "
                    "declaree presente doit dire ou la trouver"
                )
            if self.origin is None:
                raise ExtractionPrevizError(
                    f"Vignette '{self.state}' sans origine: le document doit dire "
                    "si l'image vient d'un decodage du rush ou d'une frame extraite"
                )
        if self.state == THUMBNAIL_STATE_APPROXIMATE:
            if self.decoded_source_index is None:
                raise ExtractionPrevizError(
                    "Vignette approximative sans decoded_source_index: une vignette "
                    "approximative n'est jamais presentee comme exacte, l'indice "
                    "reellement decode est ce qui rend l'ecart visible"
                )
            if (
                isinstance(self.decoded_source_index, bool)
                or not isinstance(self.decoded_source_index, int)
                or self.decoded_source_index < 0
            ):
                raise ExtractionPrevizError(
                    "decoded_source_index doit etre un indice de frame source base "
                    f"zero, recu {self.decoded_source_index!r}"
                )
        elif self.decoded_source_index is not None:
            raise ExtractionPrevizError(
                f"decoded_source_index n'est renseigne que pour une vignette "
                f"'{THUMBNAIL_STATE_APPROXIMATE}', recu {self.decoded_source_index!r} "
                f"pour l'etat '{self.state}'"
            )


#: Valeur par defaut de chaque frame: un document sans aucune vignette est
#: valide et complet.
ABSENT_THUMBNAIL = ThumbnailRef()


# --------------------------------------------------------------------------
# Document
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PrevizSubject:
    """Ce sur quoi porte la previz. Toutes les valeurs sont transportees."""

    project_id: str
    rush_id: str
    lot_id: str | None
    fps_source_exact: str
    fps_target_exact: str
    timecode_base: str
    timecode_base_fps_exact: str
    rounding_policy: str
    batch_dir_relative: str
    expected_frame_count: int
    source_tail_frames: int
    frames_present_count: int | None


@dataclass(frozen=True)
class PrevizFrame:
    """Une frame retenue, dans l'ordre canonique du lot (base zero)."""

    output_rank: int
    source_index: int
    frame_timecode: str
    frame_path_relative: str | None
    thumbnail: ThumbnailRef


@dataclass(frozen=True)
class PrevizWarnings:
    """Trois familles distinctes, jamais fusionnees, jamais traduites."""

    selection: tuple[str, ...] = ()
    confirmation: tuple[str, ...] = ()
    previz: tuple[str, ...] = ()


@dataclass(frozen=True)
class PrevizFingerprints:
    """De quoi detecter la peremption. Voir la docstring du module."""

    selection: str
    source_report: str
    source_signature: str | None = None


@dataclass(frozen=True)
class ExtractionPreviz:
    """Document de previz d'extraction, fige et comparable.

    Confort de typage pour un consommateur in-process; la forme **normative**
    est le JSON rendu par `previz_to_json_dict`.
    """

    previz_schema_version: str
    kind: str
    state: str
    generated_at_utc: str
    subject: PrevizSubject
    source_report: Mapping[str, Any]
    frames: tuple[PrevizFrame, ...]
    warnings: PrevizWarnings
    fingerprints: PrevizFingerprints


# --------------------------------------------------------------------------
# Construction
# --------------------------------------------------------------------------


# Les quatre gardes de type et la garde de chemin relatif vivent dans
# `previz_common` depuis la story 5.8 (elles etaient identiques mot pour mot
# chez les deux jumelles). Elles restent atteintes par ces enveloppes locales,
# qui n'ajoutent que la hierarchie d'erreur de ce module: le texte des refus est
# inchange, et les appels du fichier n'ont pas eu a bouger.


def _require_text(value: Any, label: str) -> str:
    return _common_require_text(value, label, error_type=ExtractionPrevizError)


def _optional_text(value: Any, label: str) -> str | None:
    return _common_optional_text(value, label, error_type=ExtractionPrevizError)


def _relative_path(value: Any, label: str) -> str:
    """Chemin relatif au dossier projet, ou refus (AC 5, AC 12)."""
    return _common_relative_path(value, label, error_type=ExtractionPrevizError)


def _optional_relative_path(value: Any, label: str) -> str | None:
    return _common_optional_relative_path(
        value, label, error_type=ExtractionPrevizError
    )


def _require_int(value: Any, label: str) -> int:
    return _common_require_int(value, label, error_type=ExtractionPrevizError)


def _codes(values: Any, label: str) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        raise ExtractionPrevizError(
            f"{label} doit etre une sequence de codes, pas une chaine: {values!r}"
        )
    return tuple(_require_text(code, f"Code de {label}") for code in values)


def _validate_previz_codes(codes: tuple[str, ...]) -> tuple[str, ...]:
    """Vocabulaire ferme: un code inconnu est refuse a la construction."""
    return require_known_codes(
        codes,
        PREVIZ_WARNING_CODES,
        label="Code d'avertissement de previz inconnu",
        error_type=ExtractionPrevizError,
    )


def _mapping_by_rank(
    values: Any, ranks: frozenset[int], label: str
) -> Mapping[int, Any]:
    if values is None:
        return {}
    if not isinstance(values, Mapping):
        raise ExtractionPrevizError(
            f"{label} doit etre un mapping output_rank -> valeur, recu {values!r}"
        )
    unknown = sorted(rank for rank in values if rank not in ranks)
    if unknown:
        raise ExtractionPrevizError(
            f"{label} designe des rangs absents de la selection: {unknown}. Un rang "
            "inconnu serait silencieusement ignore"
        )
    return values


def build_extraction_previz(
    *,
    selection: FrameSelectionLike,
    source_report: SourceReport,
    project_id: str,
    rush_id: str,
    batch_dir_relative: str,
    generated_at_utc: str,
    lot_id: str | None = None,
    state: str = PREVIZ_STATE_PLANNED,
    frames_present_count: int | None = None,
    frame_paths_relative: Mapping[int, str] | None = None,
    thumbnails: Mapping[int, ThumbnailRef] | None = None,
    previz_warnings: Sequence[str] = (),
    confirmation_warnings: Sequence[str] = (),
    source_signature: str | None = None,
) -> ExtractionPreviz:
    """Projeter les sorties de 3.1 / 3.2 / 3.3 en document de previz.

    **Projection stricte**: rien n'est recalcule, rien n'est recompte, rien
    n'est reconcilie. Deux valeurs d'entree incoherentes entre elles ressortent
    telles quelles.

    Parameters
    ----------
    selection:
        `FrameSelection` de la story 3.2, entiere. Ses frames sont transportees
        dans leur ordre canonique, jamais re-triees.
    source_report:
        `SourceReport` de la couche 1 (pure) de la story 3.3. Sa forme JSON est
        obtenue par `source_confirmation.source_report_to_json_dict`, seul
        serialiseur du rapport dans le produit.
    project_id:
        Fourni par l'appelant via la normalisation `nom -> identifiant` de la
        story 3.1: l'objet de resultat d'`extract` ne le porte pas, et ce
        module ne le derive jamais.
    rush_id, batch_dir_relative:
        Fournis par la story 3.1 (dossier de lot relatif via
        `io/project_layout.extract_frames_dir`).
    generated_at_utc:
        Horodatage UTC ISO 8601 suffixe `Z`, **fourni par l'appelant**: lire
        l'horloge ici rendrait le document non deterministe.
    lot_id:
        Possede par la story 3.4 (`naming.build_lot_id`). Optionnel: `None` est
        la valeur normale en regime `planned`.
    state:
        `"planned"` (avant extraction) ou `"extracted"` (apres).
    frames_present_count:
        **Fourni par l'appelant** en regime `extracted`, jamais compte ici.
        Interdit en regime `planned`.
    frame_paths_relative:
        `output_rank` -> chemin relatif du fichier de frame, en regime
        `extracted` uniquement. Un rang absent du mapping rend `null`: une
        extraction partielle se decrit, elle ne se devine pas.
    thumbnails:
        `output_rank` -> `ThumbnailRef`. Absent par defaut: un document sans
        aucune vignette est valide et complet.
    previz_warnings:
        Codes de degradation **recus** de l'appelant. Un code hors de
        `PREVIZ_WARNING_CODES` est refuse.
    confirmation_warnings:
        Codes stables de la story 3.3. Elle n'en expose aucun aujourd'hui, donc
        cette liste vaut `()`; ce module n'en fabrique jamais un pour combler
        ce vide.
    source_signature:
        Empreinte heuristique du rush, **fournie par l'appelant**, jamais
        calculee ici (ce serait de l'I/O).

    Raises
    ------
    ExtractionPrevizError
        Etat inconnu, horodatage non conforme, code de degradation hors
        vocabulaire, vignette approximative sans `decoded_source_index`,
        `frames_present_count` absent en `extracted` ou present en `planned`,
        rang inconnu dans un mapping.
    """
    if state not in PREVIZ_STATES:
        raise ExtractionPrevizError(
            f"Etat de previz inconnu: {state!r}. Vocabulaire ferme: "
            f"{', '.join(PREVIZ_STATES)}"
        )

    # Regle d'horodatage: `previz_common`, point unique de la famille depuis la
    # story 5.8 (elle etait ecrite inline ici et re-ecrite inline chez 4.9).
    generated = normalize_generated_at_utc(
        generated_at_utc,
        error_type=ExtractionPrevizError,
        example=_GENERATED_AT_EXAMPLE,
    )

    frames_source = tuple(selection.frames)
    ranks = frozenset(int(frame.output_rank) for frame in frames_source)
    paths = _mapping_by_rank(frame_paths_relative, ranks, "frame_paths_relative")
    thumbnail_refs = _mapping_by_rank(thumbnails, ranks, "thumbnails")

    if state == PREVIZ_STATE_EXTRACTED:
        if frames_present_count is None:
            raise ExtractionPrevizError(
                "frames_present_count est obligatoire en regime 'extracted' et doit "
                "etre fourni par l'appelant: ce module ne compte jamais les fichiers "
                "presents sur disque"
            )
        present_count: int | None = _require_int(
            frames_present_count, "frames_present_count"
        )
        if present_count < 0:
            raise ExtractionPrevizError(
                "frames_present_count doit etre un cardinal positif ou nul, recu "
                f"{frames_present_count!r}"
            )
        if present_count > selection.expected_frame_count:
            # Plus d'images que la selection n'en retient: le document se
            # contredit lui-meme, et aucun code d'avertissement ne saurait le
            # rattraper. Refus a la construction (ARB-13).
            raise ExtractionPrevizError(
                f"frames_present_count ({present_count}) depasse le cardinal "
                f"attendu de la selection ({selection.expected_frame_count}): un "
                "lot ne peut pas porter plus d'images que la selection n'en "
                "retient. Ce document se contredirait lui-meme"
            )
    else:
        if frames_present_count is not None:
            raise ExtractionPrevizError(
                "frames_present_count n'a pas de sens en regime 'planned': aucune "
                f"frame n'est encore ecrite, recu {frames_present_count!r}"
            )
        if paths:
            raise ExtractionPrevizError(
                "frame_paths_relative n'a pas de sens en regime 'planned': les "
                "fichiers de frames n'existent pas encore"
            )
        present_count = None

    frames: list[PrevizFrame] = []
    for frame in frames_source:
        rank = int(frame.output_rank)
        thumbnail = thumbnail_refs.get(rank, ABSENT_THUMBNAIL)
        if not isinstance(thumbnail, ThumbnailRef):
            raise ExtractionPrevizError(
                f"thumbnails[{rank}] doit etre un ThumbnailRef, recu {thumbnail!r}"
            )
        frames.append(
            PrevizFrame(
                output_rank=rank,
                source_index=frame.source_index,
                frame_timecode=frame.frame_timecode,
                frame_path_relative=_optional_relative_path(
                    paths.get(rank), f"frame_paths_relative[{rank}]"
                ),
                thumbnail=thumbnail,
            )
        )

    fps_source_exact = _exact_rate(selection.fps_source)
    fps_target_exact = _exact_rate(selection.fps_target)

    subject = PrevizSubject(
        project_id=_require_text(project_id, "project_id"),
        rush_id=_require_text(rush_id, "rush_id"),
        lot_id=_optional_text(lot_id, "lot_id"),
        fps_source_exact=fps_source_exact,
        fps_target_exact=fps_target_exact,
        timecode_base=selection.timecode_base,
        timecode_base_fps_exact=_exact_rate(selection.timecode_base_fps),
        rounding_policy=selection.rounding_policy,
        batch_dir_relative=_relative_path(batch_dir_relative, "batch_dir_relative"),
        expected_frame_count=selection.expected_frame_count,
        source_tail_frames=selection.source_tail_frames,
        frames_present_count=present_count,
    )

    # ARB-13: les deux compteurs sont confrontes, et un lot tronque est
    # declare. En regime `planned` aucune image n'est encore ecrite, donc la
    # question ne se pose pas.
    completude_codes: tuple[str, ...] = ()
    if present_count is not None and present_count < selection.expected_frame_count:
        completude_codes = (LOT_INCOMPLETE,)

    report_json = source_report_to_json_dict(source_report)

    return ExtractionPreviz(
        previz_schema_version=PREVIZ_SCHEMA_VERSION,
        kind=PREVIZ_KIND_EXTRACTION,
        state=state,
        generated_at_utc=generated,
        subject=subject,
        source_report=report_json,
        frames=tuple(frames),
        warnings=PrevizWarnings(
            selection=_codes(selection.warnings, "warnings.selection"),
            confirmation=_codes(confirmation_warnings, "warnings.confirmation"),
            previz=_validate_previz_codes(
                _codes(previz_warnings, "warnings.previz") + completude_codes
            ),
        ),
        fingerprints=PrevizFingerprints(
            selection=fingerprint_of(
                _selection_fingerprint_payload(
                    selection,
                    fps_source_exact=fps_source_exact,
                    fps_target_exact=fps_target_exact,
                )
            ),
            source_report=fingerprint_of(report_json),
            source_signature=_optional_text(source_signature, "source_signature"),
        ),
    )


def _selection_fingerprint_payload(
    selection: FrameSelectionLike, *, fps_source_exact: str, fps_target_exact: str
) -> dict[str, Any]:
    """Les entrees de decision de 3.2, et rien d'autre (AC 10).

    Ni les vignettes, ni `expected_frame_count`, ni un champ d'affichage: une
    empreinte sensible a ce qui ne decide rien signalerait des peremptions
    imaginaires. Symetriquement -- et c'est le defaut corrige le 2026-08-06 --
    une empreinte **aveugle** a une entree de decision declare a jour une
    selection qui ne l'est plus.

    `getattr` plutot qu'un acces direct: `FrameSelectionLike` est un Protocol
    **structurel**, et exiger deux attributs neufs romprait tout appelant
    anterieur a la story 3.7 sans qu'aucun typage ne le signale.
    """
    payload = {
        "fps_source_exact": fps_source_exact,
        "fps_target_exact": fps_target_exact,
        "rounding_policy": selection.rounding_policy,
        "source_frame_count": selection.source_frame_count,
        "source_start_timecode": selection.source_start_timecode,
        "timecode_base": selection.timecode_base,
    }
    for field in SELECTION_FINGERPRINT_OPTIONAL_FIELDS:
        value = getattr(selection, field, None)
        if value is not None:
            payload[field] = str(value)

    # Garde-fou de contrat, pas un calcul: le payload ne peut pas porter un
    # champ absent de la constante exportee, ni omettre un champ obligatoire.
    inconnus = set(payload) - set(SELECTION_FINGERPRINT_FIELDS)
    manquants = (
        set(SELECTION_FINGERPRINT_FIELDS)
        - set(SELECTION_FINGERPRINT_OPTIONAL_FIELDS)
        - set(payload)
    )
    if inconnus or manquants:
        raise ExtractionPrevizError(
            "Le payload d'empreinte de selection diverge de "
            f"SELECTION_FINGERPRINT_FIELDS (en trop: {sorted(inconnus)}, "
            f"manquants: {sorted(manquants)})"
        )
    return payload


# --------------------------------------------------------------------------
# Serialisation
# --------------------------------------------------------------------------


def _thumbnail_to_json_dict(thumbnail: ThumbnailRef) -> dict[str, Any]:
    return {
        "state": thumbnail.state,
        "origin": thumbnail.origin,
        "path_relative": thumbnail.path_relative,
        "decoded_source_index": thumbnail.decoded_source_index,
    }


def previz_to_json_dict(previz: ExtractionPreviz) -> dict[str, Any]:
    """Forme JSON **normative** du document, deterministe et serialisable.

    Aucun objet Python non JSON, aucune `Fraction` nue, aucun octet d'image,
    aucun base64. Passer le resultat a `canonical_json` produit la meme chaine
    octet pour octet d'un processus a l'autre.
    """
    return {
        # Socle d'enveloppe partage (story 5.8): les quatre champs de tete sont
        # rendus par `previz_common.envelope_head`, une fois pour les trois
        # jumelles. Les valeurs sont celles du document, jamais des constantes
        # relues: un document construit sous une autre version de schema doit
        # se rendre tel qu'il a ete construit.
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
            "fps_source_exact": previz.subject.fps_source_exact,
            "fps_target_exact": previz.subject.fps_target_exact,
            "timecode_base": previz.subject.timecode_base,
            "timecode_base_fps_exact": previz.subject.timecode_base_fps_exact,
            "rounding_policy": previz.subject.rounding_policy,
            "batch_dir_relative": previz.subject.batch_dir_relative,
            "expected_frame_count": previz.subject.expected_frame_count,
            "source_tail_frames": previz.subject.source_tail_frames,
            "frames_present_count": previz.subject.frames_present_count,
        },
        # Copie **profonde**: `dict(...)` ne recopie que le premier niveau, donc
        # muter un sous-dict du document rendu mutait l'`ExtractionPreviz` dit
        # « gele ». Deux appels successifs ne rendaient alors plus le meme JSON
        # (ce que l'AC 4 interdit), et `fingerprints.source_report` ne
        # correspondait plus a son propre contenu -- soit exactement la panne
        # que les empreintes existent pour empecher (revue du 2026-08-05).
        "source_report": copy.deepcopy(dict(previz.source_report)),
        "frames": [
            {
                "output_rank": frame.output_rank,
                "source_index": frame.source_index,
                "frame_timecode": frame.frame_timecode,
                "frame_path_relative": frame.frame_path_relative,
                "thumbnail": _thumbnail_to_json_dict(frame.thumbnail),
            }
            for frame in previz.frames
        ],
        "warnings": {
            "selection": list(previz.warnings.selection),
            "confirmation": list(previz.warnings.confirmation),
            "previz": list(previz.warnings.previz),
        },
        "fingerprints": {
            "selection": previz.fingerprints.selection,
            "source_report": previz.fingerprints.source_report,
            "source_signature": previz.fingerprints.source_signature,
        },
    }
