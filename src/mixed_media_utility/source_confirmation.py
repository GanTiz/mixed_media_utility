"""Rapport de metadonnees source et confirmation avant extraction (story 3.3).

Ce module repond a une seule question: **qu'est-ce que la commande a
reellement lu dans le rush, et combien de frames va-t-elle ecrire**, avant
que le moindre octet ne parte sur disque. Il constate et il trace; il ne
corrige rien, ne convertit rien et ne suggere aucune valeur (le MVP couleur
est no-op, voir `ARCHITECTURE.md` « Decision couleur MVP » et la story 5.5).

Trois couches strictement separees, dans cet ordre:

1. `build_source_report(probe, ...)` -- **pure**. Prend le dict ffprobe
   **deja obtenu** par la story 3.1 (`video_metadata.probe_media`) et la
   `FrameSelection` **deja calculee** par la story 3.2. Aucun sous-processus,
   aucun acces disque, aucun second appel a ffprobe.
2. `render_source_report(report)` / `render_confirmation_question(report)` --
   **pures**. Texte uniquement, aucune I/O.
3. `confirm_source_metadata(report, ...)` -- **seule** couche autorisee a
   lire ou ecrire un flux. C'est aussi la seule qui ne doit jamais etre
   importee depuis un contexte de previz (story 3.5, son AC 11: « une previz
   n'autorise rien »).

Plus le helper pur `detect_interactive(in_stream, out_stream)`, expose a part
pour que la detection du mode soit testable sans toucher a `sys.stdin`.

Ce que ce module ne fait pas, volontairement:

- il ne persiste rien (story 3.4, `io/extraction_manifest.py`);
- il ne calcule aucune empreinte (story 3.5, `fingerprints.source_report`,
  sha256 du dict rendu par `source_report_to_json_dict`); une seconde recette
  de hachage pour la meme donnee reproduirait le defaut tranche par
  `decisions-2026-08-02.md`;
- il ne mappe aucun code de sortie: il **retourne** un resultat de
  confirmation, et la story 3.1, proprietaire des codes de sortie de
  `extract`, le traduit en `3` (« confirmation non accordee »). Un refus
  n'emprunte jamais `cli._handle_poc_failure`: rien n'a echoue.

Notes de contrat vers la story 3.4 (persistance):

- les champs colorimetriques du **rush** sont prefixes `source_` et vont dans
  la section `video` du manifest, jamais dans `color`: `color.source_bit_depth`
  (`color_pipeline.COLOR_MANIFEST_FIELDS`) designe la profondeur d'un **scan**
  et son domaine est limite a 8 ou 16 (`mvp_color_manifest_fragment` leve
  hors de ce couple), alors qu'un rush 10 ou 12 bits est le cas nominal;
- les sections `video` et `color` du schema v2 sont en
  `additionalProperties: true`: l'ajout des champs `source_*` par 3.4 est
  donc purement additif et ne casse aucun manifest existant. **Ne pas
  generaliser**: la racine, `rushes[]` et `lots[]` sont en
  `additionalProperties: false`, donc le bloc `lots[].confirmation` produit
  ici exige une extension de schema, qui appartient a 3.4;
- la liste des champs `source_*` absents vit **hors** du bloc de
  confirmation (Piege 8 de la story 3.4: une seule liste, cote `video`).

Convention d'ecriture: messages en francais **sans accents**, comme
`video_metadata.py`, `io/manifest.py` et `codec_profiles.py`. Ce rapport est
long et destine a une console; un accent produirait une `UnicodeEncodeError`
sous une console `cp1252` exactement au moment le moins utile.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import PurePosixPath, PureWindowsPath
from typing import TYPE_CHECKING, Any, Mapping, Protocol, Sequence

from . import video_metadata
from .codec_profiles import exact_frame_rate
from .video_metadata import FfprobeError

if TYPE_CHECKING:  # pragma: no cover - typage seulement
    # La story 3.2 est developpee en parallele: on ne depend jamais de son
    # module a l'execution, seulement de son contrat ecrit (voir
    # `FrameSelectionLike` ci-dessous).
    from .frame_selection import FrameSelection  # noqa: F401

__all__ = [
    "SourceReportError",
    "SourceFieldSpec",
    "SOURCE_FIELD_SPECS",
    "SOURCE_FIELD_PROBE_KEYS",
    "COLOR_TRIPLET_REPORT_KEYS",
    "COLOR_TRIPLET_STATUS_COMPLETE",
    "COLOR_TRIPLET_STATUS_PARTIAL",
    "COLOR_TRIPLET_STATUS_ABSENT",
    "REQUIRE_SEPARATE_UNKNOWN_COLOR_CONSENT",
    "CONFIRMATION_MODE_INTERACTIVE",
    "CONFIRMATION_MODE_NON_INTERACTIVE",
    "ABSENT_VALUE_LABEL",
    "INDETERMINATE_BIT_DEPTH_LABEL",
    "CONSENT_OPTION_HINT",
    "UNKNOWN_COLOR_OPTION_HINT",
    "SELECTION_WARNING_LABELS",
    "SourceReport",
    "ConfirmationResult",
    "build_source_report",
    "source_report_to_json_dict",
    "render_source_report",
    "render_confirmation_question",
    "confirm_source_metadata",
    "detect_interactive",
]


# --------------------------------------------------------------------------
# Politique et vocabulaire figes
# --------------------------------------------------------------------------

#: Regle d'escalade colorimetrique, en **un seul point du code** (AC 4).
#: Decidee de facon definitive le 2026-08-03 (`decisions-2026-08-03.md`,
#: decision 5, ARB-5): deux consentements distincts en mode non interactif,
#: un general et un specifique quand le triplet colorimetrique source est
#: absent ou partiel. C'est la seule des deux options qui empeche qu'un
#: consentement general pose une fois dans un script CI couvre indefiniment
#: des rushs non tagues. En mode interactif, elle n'ajoute **pas** de seconde
#: question: le bloc d'avertissement est emis juste au-dessus de la question
#: unique, donc l'operateur l'a sous les yeux au moment de repondre.
REQUIRE_SEPARATE_UNKNOWN_COLOR_CONSENT = True

CONFIRMATION_MODE_INTERACTIVE = "interactif"
CONFIRMATION_MODE_NON_INTERACTIVE = "non_interactif"

COLOR_TRIPLET_STATUS_COMPLETE = "complet"
COLOR_TRIPLET_STATUS_PARTIAL = "partiel"
COLOR_TRIPLET_STATUS_ABSENT = "absent"

ABSENT_VALUE_LABEL = "non renseigne (absent de la source)"
INDETERMINATE_BIT_DEPTH_LABEL = "indeterminee"

# Noms d'options proposes par cette story et repris par la story 3.1, qui
# possede la surface CLI (« a verrouiller en revue croisee »). Ils ne vivent
# ici que pour que le message de refus soit actionnable; changer le nom cote
# CLI se repercute en un seul point.
CONSENT_OPTION_HINT = "--yes"
UNKNOWN_COLOR_OPTION_HINT = "--accept-unknown-color"

# Sentinelles ffprobe a normaliser en None. ffprobe 6.1.1 **omet** entierement
# les champs couleur "unknown" de son JSON (docstring de module de
# `video_metadata.py`), mais d'autres builds emettent bien la chaine
# litterale. Les deux formes doivent produire la meme absence, sans quoi une
# chaine "unknown" (non vide, donc verite-vraie) serait affichee comme une
# valeur puis persistee comme une colorimetrie declaree par la story 3.4.
_ABSENT_SENTINELS = frozenset({"unknown", "unspecified", "reserved", "n/a", ""})

# ffprobe rend "0:1" pour un ratio non renseigne: c'est une sentinelle, pas un
# ratio (un pixel de largeur nulle n'existe pas).
_RATIO_SENTINELS = frozenset({"0:1", "0/1"})

# Profondeur des TIFF ecrits par `extract`, normalisee a 16 bits quelle que
# soit la profondeur du rush (`decisions-2026-08-03.md`, decision 4, ARB-4).
# Utilisee **uniquement** pour la borne haute d'occupation disque, qui doit
# majorer ce qui sera reellement ecrit: dimensionner la borne sur une source
from mixed_media_utility.constants import OUTPUT_BIT_DEPTH as _OUTPUT_BIT_DEPTH
_OUTPUT_CHANNELS = 3


@dataclass(frozen=True)
class SourceFieldSpec:
    """Une ligne de la table unique champ affiche -> cle ffprobe -> valeur.

    Rendu, journal et objet transmis a la story 3.4 lisent tous cette table:
    ils ne peuvent donc pas diverger.
    """

    report_key: str  # nom de cle `video.*` exact attendu par la story 3.4
    probe_key: str  # cle ffprobe dont la valeur provient
    label: str  # libelle console, sans accents


SOURCE_FIELD_SPECS: tuple[SourceFieldSpec, ...] = (
    SourceFieldSpec("source_codec", "codec_name", "Codec source"),
    SourceFieldSpec("source_pix_fmt", "pix_fmt", "Format de pixel"),
    # `bits_per_raw_sample` fait autorite quand il est present; a defaut, la
    # profondeur est deduite du suffixe de `pix_fmt` (voir `_deduce_bit_depth`).
    SourceFieldSpec("source_bit_depth", "bits_per_raw_sample", "Profondeur de bits"),
    SourceFieldSpec("source_sample_aspect_ratio", "sample_aspect_ratio", "Rapport de pixel"),
    SourceFieldSpec("source_color_primaries", "color_primaries", "Primaires couleur"),
    # Piege 1: `gamma` n'est pas un champ ffprobe. La grandeur lisible est la
    # fonction de transfert; ne jamais fabriquer un 2.2 ou un 2.4 a partir
    # d'elle, ce serait une donnee inventee transmise ensuite au manifest.
    SourceFieldSpec("source_color_trc", "color_transfer", "Gamma / fonction de transfert"),
    SourceFieldSpec("source_colorspace", "color_space", "Matrice / espace couleur"),
    SourceFieldSpec("source_color_range", "color_range", "Plage de valeurs"),
)

SOURCE_FIELD_PROBE_KEYS: Mapping[str, str] = {
    spec.report_key: spec.probe_key for spec in SOURCE_FIELD_SPECS
}

# Piege 2: « espace couleur » n'est pas un champ mais trois, suivis
# independamment par ffmpeg/ffprobe (mesure story 6.3, eclatement acte par la
# story 5.5). L'escalade porte sur ce triplet, et sur lui seul.
COLOR_TRIPLET_REPORT_KEYS: tuple[str, ...] = (
    "source_color_primaries",
    "source_color_trc",
    "source_colorspace",
)

# `color_range` est traite **a part**: son absence produit un avertissement
# mais **aucune** escalade. Mesure story 6.3: ProRes n'emet aucune
# signalisation de plage alors que DNxHR / H264 / HEVC emettent `tv`. Le
# master mezzanine par defaut de ce projet sort donc non signale; escalader
# dessus ferait crier la confirmation sur le format maitre recommande. Ecart
# consigne dans `deferred-work.md`, non corrige.
COLOR_RANGE_REPORT_KEY = "source_color_range"

# Traduction des codes stables emis par la story 3.2. Le noyau 3.2 n'emet que
# des codes ASCII; la prose utilisateur appartient a cette story (AC 1).
SELECTION_WARNING_LABELS: Mapping[str, str] = {
    "SOURCE_FRAME_COUNT_ESTIMATED": (
        "Le cardinal de frames source est une ESTIMATION, pas un comptage exact: "
        "le lot peut etre tronque sans que rien ne le signale."
    ),
    "NTSC_RATE_OUT_OF_SCOPE": (
        "Cadence NTSC detectee: hors cible produit du MVP, resultat non valide."
    ),
    "NON_INTEGER_SOURCE_RATE": (
        "Cadence source non entiere: le timecode reste un identifiant de frame "
        "ordonne mais derive par rapport au temps reel."
    ),
    "NON_INTEGER_TARGET_RATE": (
        "Cadence cible non entiere: verifier le nom du dossier de lot et des fichiers."
    ),
    "NON_DIVISIBLE_RATES": (
        "Cadences non divisibles: l'ecart entre deux frames retenues alterne "
        "d'une frame source (jitter borne, sans accumulation)."
    ),
}


class SourceReportError(RuntimeError):
    """Echec bloquant, anterieur a toute confirmation (AC 5).

    Deux cas et deux seulement: resolution absente / nulle / non entiere, et
    absence totale de flux video dans le probe. La story 3.1 traduit cette
    exception en code de sortie `1`; elle ne doit jamais remonter en trace
    Python devant un operateur.
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

    Cette story ne lit **que** ces champs, et aucun autre: elle ne consomme
    aucun indice de frame, ne verifie aucun arrondi et ne reimplemente aucune
    regle d'echantillonnage. `expected_frame_count` est repris verbatim,
    jamais recalcule ni recompte sur disque (un lot tronque se declarerait
    complet).
    """

    frames: Sequence[_SelectedFrameLike]
    expected_frame_count: int
    source_tail_frames: int
    warnings: Sequence[str]
    timecode_base: str
    timecode_base_fps: Fraction
    #: Bornes demandees par l'operateur (story 3.7), `None` sur une extraction
    #: complete. Reprises verbatim comme tout le reste: cette story ne les
    #: rededuit pas des timecodes de premiere et derniere frame, qui disent ce
    #: qui a ete retenu et non ce qui a ete demande. Lues par `getattr` avec
    #: repli: une selection d'avant la story 3.7 reste un `FrameSelectionLike`
    #: valide.
    source_in_timecode: str | None
    source_out_timecode: str | None


# --------------------------------------------------------------------------
# Couche 1 -- construction pure du rapport
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceReport:
    """Rapport de metadonnees source, serialisable et deterministe (AC 12).

    Aucun objet Python non serialisable, aucune `Fraction` nue: les cadences
    y figurent en chaines rationnelles exactes produites par
    `codec_profiles.exact_frame_rate` (forme `"num/den"`). Voir
    `source_report_to_json_dict` pour la forme JSON canonique, seul point de
    serialisation du rapport dans le produit.
    """

    #: `source_*` -> valeur normalisee, `None` quand la source ne dit rien.
    #: Destines a la section `video` du manifest (story 3.4).
    source_fields: Mapping[str, str | int | None]
    #: `{"width": int, "height": int}` -> `video.resolution_source`.
    resolution_source: Mapping[str, int]
    #: Resolution d'affichage apres application du SAR (Piege 4).
    display_resolution: Mapping[str, int]
    is_anamorphic: bool
    display_aspect_ratio: str | None
    bit_depth_origin: str | None  # "bits_per_raw_sample" | "pix_fmt" | None
    fps_source_exact: str | None  # "num/den", depuis `r_frame_rate`
    fps_target_exact: str  # "num/den", cadence demandee
    source_start_timecode: str | None  # affiche seulement, hors contrat 3.4
    timecode_base: str
    timecode_base_fps_exact: str
    first_frame_timecode: str | None
    last_frame_timecode: str | None
    expected_frame_count: int
    source_tail_frames: int
    selection_warnings: tuple[str, ...]
    batch_dir_relative: str
    disk_upper_bound_bytes: int
    color_triplet_status: str
    requires_unknown_color_consent: bool
    color_range_missing: bool
    #: Tous les champs `source_*` normalises a `None`, sous leurs noms de cle
    #: `video.*` exacts et tries: forme que 3.4 persiste telle quelle dans
    #: `video.source_metadata_absent_fields`, sans la recalculer.
    absent_fields: tuple[str, ...]
    #: Bornes de l'extrait demande (story 3.7), `None` sur une extraction
    #: complete. Affichees **avant** `expected_frame_count`: l'intention avant
    #: sa consequence (AC 10).
    #:
    #: En fin de dataclass et avec un defaut, pour une raison precise: la
    #: story 3.7 est additive et aucun appelant anterieur ne doit avoir a
    #: changer. `None` ne « ressemble » pas a une borne, c'est litteralement
    #: son absence -- le defaut interdit par l'AC 14 serait une borne
    #: fabriquee (`00:00:00:00`), jamais celui-ci.
    source_in_timecode: str | None = None
    source_out_timecode: str | None = None


def _normalize_probe_value(value: Any) -> Any:
    """Sentinelle ffprobe -> `None`, sans jamais substituer de valeur.

    Cle absente, `unknown`, `unspecified`, `reserved`, `N/A` et chaine vide
    produisent tous la meme absence. Aucune valeur par defaut n'est jamais
    ecrite a la place (`bt709` interdit, ni affiche ni transmis a 3.4).
    """
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.lower() in _ABSENT_SENTINELS:
            return None
        return stripped
    return value


def _normalize_ratio(value: Any) -> str | None:
    ratio = _normalize_probe_value(value)
    if ratio is None:
        return None
    text = str(ratio).strip()
    if text.lower() in _RATIO_SENTINELS:
        return None
    return text


def _parse_ratio(ratio: str | None) -> Fraction | None:
    if not ratio:
        return None
    parts = re.split(r"[:/]", ratio)
    if len(parts) != 2:
        return None
    try:
        numerator, denominator = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if numerator <= 0 or denominator <= 0:
        return None
    return Fraction(numerator, denominator)


def _coerce_positive_int(value: Any) -> int | None:
    """Entier strictement positif, ou `None`. Refuse `bool` et les flottants.

    ffprobe emet indifferemment `1920` et `"10"` selon le champ: les deux
    formes sont acceptees, une chaine non entiere ne l'est pas.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str):
        text = value.strip()
        if not text.lstrip("+").isdigit():
            return None
        parsed = int(text)
        return parsed if parsed > 0 else None
    return None


# Suffixe de profondeur des formats de pixel planaires (`yuv422p10le` -> 10).
_PIX_FMT_DEPTH_RE = re.compile(r"p(\d+)(?:le|be)?$")
# Formats sans suffixe numerique dont la profondeur par composante est connue
# sans ambiguite. Volontairement court: hors de cette table et de la regex, la
# profondeur est declaree `indeterminee`, **jamais** supposee a 8 (Piege 5).
_PIX_FMT_KNOWN_DEPTHS: Mapping[str, int] = {
    "gray": 8,
    "rgb24": 8,
    "bgr24": 8,
    "rgba": 8,
    "bgra": 8,
    "argb": 8,
    "abgr": 8,
    "nv12": 8,
    "nv21": 8,
    "uyvy422": 8,
    "yuyv422": 8,
    "rgb48le": 16,
    "rgb48be": 16,
    "bgr48le": 16,
    "bgr48be": 16,
    "gray16le": 16,
    "gray16be": 16,
}


def _deduce_bit_depth(stream: Mapping[str, Any]) -> tuple[int | None, str | None]:
    """Profondeur de bits du rush et provenance de la valeur.

    `bits_per_raw_sample` d'abord (present sur beaucoup de flux et faisant
    autorite), a defaut le suffixe de `pix_fmt`, sinon `None` rendu
    `indeterminee`. **Ne jamais supposer 8**: supposer 8 sur un rush 10 bits
    ecrirait une valeur fausse dans `video.source_bit_depth`, champ de
    tracabilite qui doit rester la profondeur reelle de la source meme depuis
    la normalisation des TIFF extraits en 16 bits (`decisions-2026-08-03.md`,
    decision 4).
    """
    declared = _coerce_positive_int(_normalize_probe_value(stream.get("bits_per_raw_sample")))
    if declared is not None:
        return declared, "bits_per_raw_sample"

    pix_fmt = _normalize_probe_value(stream.get("pix_fmt"))
    if isinstance(pix_fmt, str):
        name = pix_fmt.lower()
        match = _PIX_FMT_DEPTH_RE.search(name)
        if match:
            depth = int(match.group(1))
            if depth > 0:
                return depth, "pix_fmt"
        if name in _PIX_FMT_KNOWN_DEPTHS:
            return _PIX_FMT_KNOWN_DEPTHS[name], "pix_fmt"
        # `yuv420p`, `yuvj422p`, `gbrp`: planaire termine par `p` sans suffixe
        # numerique (la regex ci-dessus a deja capte `p10le`, `p12le`, ...),
        # donc 8 bits par composante par convention ffmpeg. Ce n'est pas une
        # supposition par defaut: c'est la lecture du nom du format de pixel,
        # et tout ce qui sort de ces deux regles reste `indeterminee`.
        if name.endswith("p"):
            return 8, "pix_fmt"
    return None, None


def normalize_relative_project_path(value: Any, label: str = "Le chemin") -> str:
    """Chemin relatif au dossier projet, normalise en POSIX, ou `ValueError`.

    **Point unique** de cette regle pour tout le projet. La story 3.5 la
    reimplementait de facon si allegee qu'elle ne la tenait pas du tout
    (`_require_text` ne verifiait que « chaine non vide »), alors que cette
    fonction gardait deja exactement le meme champ: deux stories, une meme
    donnee, deux comportements (revue du 2026-08-05).

    `io/manifest._check_no_absolute_paths` rejette tout chemin absolu dans un
    manifest v2; aucun document du projet ne doit donc en porter un. La
    verification couvre la forme Windows (`C:\\...`), invisible a
    `PurePosixPath`, et la remontee `..`, aussi destructrice qu'un chemin
    absolu: elle place la cible hors du projet, donc hors de ce qu'un
    transfert du dossier projet emporte.

    Leve `ValueError` -- et non une erreur propre a un module -- pour que
    chaque appelant l'encapsule dans **sa** hierarchie.
    """
    text = str(value).replace("\\", "/")
    if PurePosixPath(text).is_absolute() or PureWindowsPath(str(value)).is_absolute():
        raise ValueError(
            f"{label} doit etre relatif au dossier projet, pas absolu: {value!r}"
        )
    if ".." in PurePosixPath(text).parts:
        raise ValueError(
            f"{label} doit rester a l'interieur du dossier projet: {value!r} "
            "remonte au-dessus de la racine du projet"
        )
    return PurePosixPath(text).as_posix()


def _relative_batch_dir(batch_dir_relative: Any) -> str:
    """Chemin de lot du rapport source, dans la hierarchie d'erreurs de 3.3."""
    try:
        return normalize_relative_project_path(
            batch_dir_relative, "Le dossier de lot"
        )
    except ValueError as exc:
        raise SourceReportError(str(exc)) from exc


@dataclass(frozen=True)
class LectureDeLaSource:
    """Ce qu'un probe ffprobe dit de la SOURCE, sans rien devoir a une cible.

    **Extrait de `build_source_report` par la story 11.4e (lot A), sans un
    caractere de changement de comportement**, et c'est le motif entier de son
    existence : declarer un rush sans l'extraire (`EPIC11-ARB-131`) doit ecrire
    dans `rushes[]` **exactement** ce qu'une extraction y ecrirait, sans quoi
    l'entree d'un rush declare puis extrait differerait de celle du meme rush
    extrait directement -- et l'ecart ne se verrait que sur un manifeste.

    Une declaration n'a **ni cadence cible ni dossier de lot** : elle ne peut
    donc pas appeler `build_source_report`, qui exige les deux. Recopier les
    quinze lignes de lecture du flux etait l'autre issue ; c'est celle que
    `EPIC11-ARB-108` interdit partout ailleurs (« un mecanisme, un lieu »), et
    une seconde redaction des `SOURCE_FIELD_SPECS` aurait diverge au premier
    champ ajoute.
    """

    #: Le flux video du probe, tel que `video_metadata._video_stream` le rend.
    stream: Mapping[str, Any]
    #: `source_*` -> valeur normalisee, `None` quand la source ne dit rien.
    source_fields: Mapping[str, "str | int | None"]
    width: int
    height: int
    #: `"declaree"` ou `"deduite"` -- d'ou vient `source_bit_depth`.
    bit_depth_origin: str
    sample_aspect_ratio: str | None
    display_aspect_ratio: str | None


def lire_la_source(probe: Mapping[str, Any]) -> LectureDeLaSource:
    """Lire le flux video d'un probe et en normaliser les champs de source.

    Pure, sans I/O : `probe` est le dict ffprobe **deja obtenu** par l'appelant.

    Leve `SourceReportError` dans les **deux** memes cas que
    `build_source_report`, avec les **memes phrases** -- absence totale de flux
    video, et resolution absente / nulle / non entiere. La resolution n'est pas
    une annotation colorimetrique mais la propriete structurelle sans laquelle
    la sortie n'est pas definie ; tout autre champ manquant est encode par un
    `None` et non par un refus.
    """
    try:
        stream = video_metadata._video_stream(probe)
    except FfprobeError as exc:
        raise SourceReportError(
            "Aucun flux video dans le fichier source: extraction impossible "
            f"({exc}). Verifier que le fichier est bien un rush video."
        ) from exc

    width = _coerce_positive_int(stream.get("width"))
    height = _coerce_positive_int(stream.get("height"))
    if width is None or height is None:
        raise SourceReportError(
            "Resolution source inexploitable: 'width' et 'height' doivent etre des "
            "entiers strictement positifs dans la sortie ffprobe "
            f"(lu: width={stream.get('width')!r}, height={stream.get('height')!r}). "
            "Sans resolution, la sortie de l'extraction n'est pas definie."
        )

    bit_depth, bit_depth_origin = _deduce_bit_depth(stream)
    sample_aspect_ratio = _normalize_ratio(stream.get("sample_aspect_ratio"))
    display_aspect_ratio = _normalize_ratio(stream.get("display_aspect_ratio"))

    source_fields: dict[str, str | int | None] = {}
    for spec in SOURCE_FIELD_SPECS:
        if spec.report_key == "source_bit_depth":
            source_fields[spec.report_key] = bit_depth
        elif spec.report_key == "source_sample_aspect_ratio":
            source_fields[spec.report_key] = sample_aspect_ratio
        else:
            source_fields[spec.report_key] = _normalize_probe_value(stream.get(spec.probe_key))

    return LectureDeLaSource(
        stream=stream,
        source_fields=source_fields,
        width=width,
        height=height,
        bit_depth_origin=bit_depth_origin,
        sample_aspect_ratio=sample_aspect_ratio,
        display_aspect_ratio=display_aspect_ratio,
    )


def build_source_report(
    probe: Mapping[str, Any],
    *,
    fps_target: float | int | str | Fraction,
    selection: FrameSelectionLike,
    batch_dir_relative: Any,
) -> SourceReport:
    """Construire le rapport de metadonnees source. Pure, sans I/O.

    `probe` est le dict ffprobe **deja obtenu** par la story 3.1
    (`video_metadata.probe_media`): ne jamais re-prober, ce serait payer un
    second sous-processus de 60 s de timeout et surtout ouvrir un ecart entre
    ce que 3.1 a valide et ce qui est montre a l'operateur.

    `selection` est l'objet `FrameSelection` **entier** de la story 3.2, dont
    seuls `expected_frame_count`, `source_tail_frames`, `warnings`,
    `timecode_base`, `timecode_base_fps` et `frames` (bornes de la plage de
    timecodes) sont lus. Ces valeurs sont reprises **verbatim**, jamais
    recalculees.

    Leve `SourceReportError` si le probe ne porte aucun flux video, ou si
    `width` / `height` sont absents, nuls ou non entiers: la resolution n'est
    pas une annotation colorimetrique mais la propriete structurelle sans
    laquelle la sortie n'est pas definie. Aucun autre champ manquant n'est
    bloquant -- les rushs non tagues sont courants et le MVP ne consomme pas
    la colorimetrie pour transformer quoi que ce soit; bloquer rendrait le
    produit inutilisable pour un cas nominal.
    """
    lecture = lire_la_source(probe)
    stream = lecture.stream
    width, height = lecture.width, lecture.height
    bit_depth_origin = lecture.bit_depth_origin
    sample_aspect_ratio = lecture.sample_aspect_ratio
    display_aspect_ratio = lecture.display_aspect_ratio
    source_fields = dict(lecture.source_fields)

    # Piege 4: un 1920x1080 en SAR 4:3 s'affiche en 2560x1080. N'afficher que
    # width x height masquerait le probleme.
    sar = _parse_ratio(sample_aspect_ratio)
    is_anamorphic = sar is not None and sar != 1
    if is_anamorphic:
        display_width = int(round(width * sar))
        display_height = height
    else:
        display_width, display_height = width, height

    fps_source_exact = _exact_or_none(_normalize_probe_value(stream.get("r_frame_rate")))
    try:
        fps_target_exact = exact_frame_rate(fps_target)
    except (TypeError, ValueError, ZeroDivisionError, OverflowError) as exc:
        raise SourceReportError(f"Cadence cible inexploitable: {fps_target!r} ({exc})") from exc

    frames = tuple(selection.frames)
    expected_frame_count = int(selection.expected_frame_count)

    # Piege 12: borne HAUTE non compressee, jamais une prediction. Une
    # estimation fausse dans le sens optimiste est pire que pas d'estimation,
    # puisque c'est precisement l'information sur laquelle l'operateur decide.
    disk_upper_bound_bytes = (
        width * height * _OUTPUT_CHANNELS * (_OUTPUT_BIT_DEPTH // 8) * max(expected_frame_count, 0)
    )

    # Symetrique du traitement de `fps_target` ci-dessus. `FrameSelectionLike`
    # est un Protocol **structurel**: rien ne garantit qu'un appelant fournisse
    # une cadence de base exploitable, et le Piege 14 interdit d'afficher un
    # timecode sans sa base. Plutot que de laisser fuir une `ValueError` ou une
    # `ZeroDivisionError` en trace Python devant un operateur, on traduit en
    # `SourceReportError`, que la story 3.1 rend deja en code de sortie `1`.
    try:
        timecode_base_fps_exact = exact_frame_rate(selection.timecode_base_fps)
    except (TypeError, ValueError, ZeroDivisionError, OverflowError) as exc:
        raise SourceReportError(
            "Cadence de base du timecode inexploitable: "
            f"{selection.timecode_base_fps!r} ({exc})"
        ) from exc

    triplet_present = [source_fields[key] is not None for key in COLOR_TRIPLET_REPORT_KEYS]
    if all(triplet_present):
        color_triplet_status = COLOR_TRIPLET_STATUS_COMPLETE
    elif any(triplet_present):
        color_triplet_status = COLOR_TRIPLET_STATUS_PARTIAL
    else:
        color_triplet_status = COLOR_TRIPLET_STATUS_ABSENT

    return SourceReport(
        source_fields=source_fields,
        resolution_source={"width": width, "height": height},
        display_resolution={"width": display_width, "height": display_height},
        is_anamorphic=is_anamorphic,
        display_aspect_ratio=display_aspect_ratio,
        bit_depth_origin=bit_depth_origin,
        fps_source_exact=fps_source_exact,
        fps_target_exact=fps_target_exact,
        source_start_timecode=_normalize_probe_value(video_metadata._find_timecode(probe)),
        # `getattr` avec repli: `FrameSelectionLike` est un Protocol
        # **structurel**. Un acces direct forcait tout appelant anterieur a la
        # story 3.7 -- doubles de test compris -- a se doter des deux attributs,
        # ce qui contredisait l'AC 14 (revue du 2026-08-06).
        source_in_timecode=_bound_timecode(
            getattr(selection, "source_in_timecode", None)
        ),
        source_out_timecode=_bound_timecode(
            getattr(selection, "source_out_timecode", None)
        ),
        timecode_base=str(selection.timecode_base),
        timecode_base_fps_exact=timecode_base_fps_exact,
        first_frame_timecode=frames[0].frame_timecode if frames else None,
        last_frame_timecode=frames[-1].frame_timecode if frames else None,
        expected_frame_count=expected_frame_count,
        source_tail_frames=int(selection.source_tail_frames),
        selection_warnings=tuple(str(code) for code in selection.warnings),
        batch_dir_relative=_relative_batch_dir(batch_dir_relative),
        disk_upper_bound_bytes=disk_upper_bound_bytes,
        color_triplet_status=color_triplet_status,
        requires_unknown_color_consent=(
            REQUIRE_SEPARATE_UNKNOWN_COLOR_CONSENT
            and color_triplet_status != COLOR_TRIPLET_STATUS_COMPLETE
        ),
        color_range_missing=source_fields[COLOR_RANGE_REPORT_KEY] is None,
        absent_fields=tuple(sorted(key for key, value in source_fields.items() if value is None)),
    )


def _bound_timecode(value: Any) -> str | None:
    """Borne de la selection -> chaine, ou `None`. Aucune validation ici.

    La regle de bornage appartient au noyau (story 3.2 etendue par la 3.7), qui
    l'a deja fait jouer contre le cardinal reel de la source avant que ce
    rapport n'existe. Revalider ici produirait un second jeu de messages,
    divergent du premier au premier ajustement.
    """
    return None if value is None else str(value)


def _exact_or_none(rate: Any) -> str | None:
    if rate is None:
        return None
    try:
        return exact_frame_rate(rate if isinstance(rate, (str, Fraction)) else float(rate))
    except (TypeError, ValueError, ZeroDivisionError, OverflowError):
        # Une cadence source illisible n'est pas bloquante ici: la story 3.1
        # refuse deja en amont une cadence indeterminee ou VFR.
        return None


def source_report_to_json_dict(report: SourceReport) -> dict:
    """Forme JSON canonique du rapport. **Seul** serialiseur du produit.

    Rendu explicitement nomme pour la story 3.5, dont l'AC 10 calcule
    `fingerprints.source_report` comme un sha256 du rapport canonique: sans cet
    accesseur, elle ecrirait un second serialiseur du rapport source, exactement
    le defaut tranche par `decisions-2026-08-02.md`. Cette story ne calcule
    **aucune** empreinte; elle garantit seulement que le rapport est hachable
    sans ambiguite.

    Garanties (AC 12): JSON pur (aucun objet Python non serialisable, aucune
    `Fraction` nue, les cadences sont des chaines `"num/den"`), et contenu
    deterministe pour des entrees identiques, donc stable sous
    `json.dumps(..., sort_keys=True)` d'un processus a l'autre.
    """
    timecode_block: dict[str, Any] = {
        "base": report.timecode_base,
        "base_fps_exact": report.timecode_base_fps_exact,
        "first_frame": report.first_frame_timecode,
        "last_frame": report.last_frame_timecode,
        "start": report.source_start_timecode,
    }
    # Revue du 2026-08-06. Ces deux cles etaient ecrites en permanence, a
    # `null` quand aucune borne n'etait demandee, au motif que ce document
    # serait une simple trace de journal. C'etait faux a deux titres: il
    # alimente `fingerprints.source_report` (story 3.5), donc une extraction
    # NON bornee ne produisait plus la meme empreinte qu'avant la story 3.7 --
    # ce que l'AC 14 interdit -- et le projet omet partout ailleurs plutot que
    # d'ecrire `null`. (Les cles preexistantes de ce bloc gardent leur `null`:
    # les toucher changerait l'empreinte de tous les lots, y compris anciens.)
    for cle, valeur in (
        ("bound_in", report.source_in_timecode),
        ("bound_out", report.source_out_timecode),
    ):
        if valeur is not None:
            timecode_block[cle] = valeur

    return {
        "batch_dir_relative": report.batch_dir_relative,
        "bit_depth_origin": report.bit_depth_origin,
        "color": {
            "range_missing": report.color_range_missing,
            "requires_unknown_color_consent": report.requires_unknown_color_consent,
            "triplet_status": report.color_triplet_status,
        },
        "disk_upper_bound_bytes": report.disk_upper_bound_bytes,
        "display_aspect_ratio": report.display_aspect_ratio,
        "display_resolution": {
            "width": report.display_resolution["width"],
            "height": report.display_resolution["height"],
        },
        "fps_source_exact": report.fps_source_exact,
        "fps_target_exact": report.fps_target_exact,
        "is_anamorphic": report.is_anamorphic,
        "resolution_source": {
            "width": report.resolution_source["width"],
            "height": report.resolution_source["height"],
        },
        "selection": {
            "expected_frame_count": report.expected_frame_count,
            "source_tail_frames": report.source_tail_frames,
            "warnings": list(report.selection_warnings),
        },
        "source_fields": {key: report.source_fields[key] for key in sorted(report.source_fields)},
        "source_metadata_absent_fields": list(report.absent_fields),
        "timecode": timecode_block,
    }


# --------------------------------------------------------------------------
# Couche 2 -- rendu texte, aucune I/O
# --------------------------------------------------------------------------

_LABEL_WIDTH = 50


def _line(label: str, value: Any) -> str:
    return f"  {label:<{_LABEL_WIDTH}}: {value}"


def _shown(value: Any) -> str:
    return ABSENT_VALUE_LABEL if value is None else str(value)


def _format_bytes(size: int) -> str:
    units = ("octets", "Kio", "Mio", "Gio", "Tio")
    value = float(size)
    index = 0
    while value >= 1024 and index < len(units) - 1:
        value /= 1024
        index += 1
    if index == 0:
        return f"{size} octets"
    return f"{value:.2f} {units[index]} ({size} octets)"


def _timecode_with_base(report: SourceReport, timecode: str | None) -> str:
    """Piege 14: un timecode affiche porte toujours sa base et sa cadence.

    La base de timecode est **source** (`decisions-2026-08-03.md`, decision 3,
    ARB-2), et aucune validation de timecode ne se fait ici contre
    `fps_target`: la seule cadence correcte est `FrameSelection.timecode_base_fps`.
    """
    if timecode is None:
        return ABSENT_VALUE_LABEL
    return f"{timecode} (base {report.timecode_base}, cadence {report.timecode_base_fps_exact})"


def render_source_report(report: SourceReport) -> str:
    """Rendu console complet du rapport. Aucune I/O.

    Le bloc d'avertissement colorimetrique est emis **en fin de rapport**,
    donc juste au-dessus de la question unique du mode interactif (AC 4):
    l'operateur l'a sous les yeux au moment de repondre.
    """
    lines: list[str] = []
    lines.append("=== Confirmation avant extraction ===")
    lines.append("")
    lines.append("Source lue par ffprobe (aucune valeur par defaut n'est substituee)")
    lines.append(
        _line("Resolution de stockage (width x height)", f"{report.resolution_source['width']} x {report.resolution_source['height']}")
    )
    if report.is_anamorphic:
        display_shown = (
            f"{report.display_resolution['width']} x {report.display_resolution['height']}"
            f" [SAR anamorphique, display_aspect_ratio={_shown(report.display_aspect_ratio)}]"
        )
    elif report.source_fields["source_sample_aspect_ratio"] is None:
        # AC 3: aucune valeur par defaut n'est jamais substituee. Sans
        # `sample_aspect_ratio`, le rapport de pixel n'est pas connu, donc la
        # resolution d'affichage ne l'est pas non plus. Afficher la resolution
        # de stockage a cette ligne reviendrait a supposer des pixels carres,
        # c'est-a-dire a substituer un 1:1 par defaut -- exactement
        # l'anamorphose que le Piege 4 demande de rendre visible. La resolution
        # de stockage, elle, reste affichee juste au-dessus: c'est celle des
        # TIFF qui seront ecrits.
        display_shown = (
            f"{ABSENT_VALUE_LABEL} [sample_aspect_ratio absent: rapport de pixel "
            "inconnu, resolution d'affichage non determinee]"
        )
    else:
        display_shown = (
            f"{report.display_resolution['width']} x {report.display_resolution['height']}"
        )
    lines.append(_line("Resolution d'affichage (display_aspect_ratio)", display_shown))
    for spec in SOURCE_FIELD_SPECS:
        value = report.source_fields[spec.report_key]
        probe_key = spec.probe_key
        if spec.report_key == "source_bit_depth":
            if value is None:
                shown = INDETERMINATE_BIT_DEPTH_LABEL
            else:
                shown = str(value)
            if report.bit_depth_origin == "pix_fmt":
                probe_key = "deduite de pix_fmt"
            elif report.bit_depth_origin is None:
                # AC 1: la cle nommee doit etre celle d'ou la valeur provient.
                # Ici aucune des deux ne conclut; nommer `bits_per_raw_sample`
                # seul laisserait croire que la source l'a renseignee alors
                # qu'elle est absente.
                probe_key = "bits_per_raw_sample et pix_fmt sans conclusion"
            lines.append(_line(f"{spec.label} ({probe_key})", shown))
            continue
        lines.append(_line(f"{spec.label} ({probe_key})", _shown(value)))
    lines.append(_line("Cadence source (r_frame_rate)", _shown(report.fps_source_exact)))
    lines.append(_line("Cadence cible demandee", report.fps_target_exact))
    lines.append(
        _line("Timecode de depart (timecode)", _timecode_with_base(report, report.source_start_timecode))
    )
    lines.append("")
    lines.append("Selection deterministe (valeurs reprises telles quelles de la selection)")
    # AC 10 de la story 3.7: l'intention avant sa consequence. Un operateur qui
    # a demande un extrait doit voir qu'on lui montre bien un extrait, et non
    # seulement un `expected_frame_count` plus petit que prevu -- chiffre
    # indiscernable d'une erreur de cadence. Les deux lignes n'apparaissent que
    # lorsqu'une borne a ete demandee: annoncer « absente » a chaque extraction
    # complete ajouterait du bruit permanent pour dire qu'il n'y a rien a dire.
    if report.source_in_timecode is not None:
        lines.append(
            _line(
                "Borne d'entree demandee (--in)",
                _timecode_with_base(report, report.source_in_timecode),
            )
        )
    if report.source_out_timecode is not None:
        lines.append(
            _line(
                "Borne de sortie demandee (--out)",
                _timecode_with_base(report, report.source_out_timecode),
            )
        )
    lines.append(_line("Frames qui seront extraites (expected_frame_count)", report.expected_frame_count))
    lines.append(_line("Frames source non retenues en fin de rush", report.source_tail_frames))
    lines.append(
        _line(
            "Premier timecode de la selection",
            _timecode_with_base(report, report.first_frame_timecode),
        )
    )
    lines.append(
        _line(
            "Dernier timecode de la selection",
            _timecode_with_base(report, report.last_frame_timecode),
        )
    )
    lines.append("")
    lines.append("Sortie")
    lines.append(_line("Dossier de lot (relatif au projet)", report.batch_dir_relative))
    lines.append(
        _line(
            "Occupation disque, borne haute non compressee",
            _format_bytes(report.disk_upper_bound_bytes),
        )
    )
    lines.append(
        "  (borne = largeur x hauteur x 3 canaux x 2 octets x nombre de frames, "
        "TIFF 16 bits non compresse; la compression n'est pas modelisee)"
    )

    lines.extend(_render_selection_warnings(report))
    lines.extend(_render_color_warnings(report))
    return "\n".join(lines)


def _render_selection_warnings(report: SourceReport) -> list[str]:
    if not report.selection_warnings:
        return []
    lines = ["", "Avertissements de selection"]
    for code in report.selection_warnings:
        label = SELECTION_WARNING_LABELS.get(code, "Code d'avertissement non traduit par cette version.")
        lines.append(f"  [{code}] {label}")
    return lines


def _render_color_warnings(report: SourceReport) -> list[str]:
    lines: list[str] = []
    if report.requires_unknown_color_consent:
        missing = [key for key in COLOR_TRIPLET_REPORT_KEYS if report.source_fields[key] is None]
        lines.append("")
        lines.append("AVERTISSEMENT: colorimetrie source incomplete")
        lines.append(
            f"  Triplet colorimetrique {report.color_triplet_status} "
            "(color_primaries, color_transfer, color_space)."
        )
        lines.append(f"  Champs non renseignes: {', '.join(missing)}")
        lines.append(
            "  Le MVP n'applique aucune correction couleur: ce qui est absent ici le "
            "restera dans le manifest, et l'etape encode posera plus tard les flags "
            "couleur d'un profil sur des donnees dont l'espace d'origine est inconnu."
        )
    if report.color_range_missing:
        lines.append("")
        lines.append("Note: plage de valeurs (color_range) non signalee par la source.")
        lines.append(
            "  ProRes n'emet aucune signalisation de plage; ce point seul n'exige "
            "aucun consentement supplementaire."
        )
    if report.absent_fields:
        lines.append("")
        lines.append(
            "Champs source non renseignes: " + ", ".join(report.absent_fields)
        )
    return lines


def render_confirmation_question(report: SourceReport) -> str:
    """Question unique du mode interactif. Une reponse vide vaut **non**."""
    if report.requires_unknown_color_consent:
        return (
            "Confirmer l'extraction, en acceptant explicitement une colorimetrie "
            "source incomplete ? [o/N] "
        )
    return "Confirmer l'extraction ? [o/N] "


# --------------------------------------------------------------------------
# Couche 3 -- interaction, seule couche autorisee a lire ou ecrire un flux
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ConfirmationResult:
    """Resultat de la confirmation, consomme par `cli.py` (story 3.1).

    `granted` pilote le code de sortie (`3` sur refus) mais n'a pas de sens en
    persistance: un refus n'ecrit jamais de manifest. Le bloc a persister est
    rendu par `confirmation_block()`, aux trois noms exacts que 3.4 ecrit dans
    `lots[].confirmation`. `absent_fields` reste **hors** de ce bloc: 3.4 la
    persiste une seule fois, dans `video.source_metadata_absent_fields`.
    """

    granted: bool
    mode: str
    unknown_color_accepted: bool
    confirmed_at: str  # RFC3339 UTC
    absent_fields: tuple[str, ...]
    message: str

    def confirmation_block(self) -> dict:
        """Les trois champs, et seulement eux, que 3.4 persiste."""
        return {
            "mode": self.mode,
            "unknown_color_accepted": self.unknown_color_accepted,
            "confirmed_at": self.confirmed_at,
        }


_AFFIRMATIVE_ANSWERS = frozenset({"o", "oui", "y", "yes"})


def detect_interactive(in_stream: Any, out_stream: Any) -> bool:
    """Mode interactif detecte, jamais suppose. Helper pur, sans I/O.

    Exige un TTY sur le flux d'entree **et** sur le flux de sortie. Defensif
    par construction: un flux `None` (`sys.stdin` vaut `None` sous un
    interpreteur sans console, cas Windows `pythonw`) ou un objet sans methode
    `isatty` vaut **non interactif**, jamais une `AttributeError`.

    A noter cote appelant (story 3.1, proprietaire de la surface CLI): le
    drapeau de consentement force le mode non interactif quel que soit le TTY,
    puisque c'est le **canal d'acquittement** que `mode` designe, pas la nature
    du terminal.
    """
    return _is_tty(in_stream) and _is_tty(out_stream)


def _is_tty(stream: Any) -> bool:
    if stream is None:
        return False
    isatty = getattr(stream, "isatty", None)
    if not callable(isatty):
        return False
    try:
        return bool(isatty())
    except Exception:
        # Un flux ferme leve ValueError sur isatty(): non interactif, et
        # surtout pas une trace devant un operateur.
        return False


def _write(out_stream: Any, text: str) -> None:
    if out_stream is None:
        return
    out_stream.write(text)
    flush = getattr(out_stream, "flush", None)
    if callable(flush):
        flush()


def _log_report(logger: logging.Logger | None, text: str) -> None:
    if logger is None:
        return
    # Ligne a ligne plutot qu'un seul enregistrement multiligne: un journal
    # reste ainsi greppable, et l'AC 10 exige que chaque champ, sa valeur et sa
    # cle ffprobe soient traces AVANT la question.
    for line in text.splitlines():
        if line.strip():
            logger.info(line)


def _utc_now_rfc3339() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def confirm_source_metadata(
    report: SourceReport,
    *,
    interactive: bool,
    consent_granted: bool = False,
    unknown_color_accepted: bool = False,
    logger: logging.Logger | None = None,
    out_stream: Any = None,
    in_stream: Any = None,
) -> ConfirmationResult:
    """Emettre le rapport, recueillir l'accord, retourner la decision.

    Seule couche de ce module autorisee a lire ou ecrire un flux. Le rapport
    complet est emis **et journalise avant** toute question, quel que soit le
    mode: c'est le canal d'acquittement qui change, jamais la production du
    rapport. Une execution refusee laisse donc une trace complete de ce qui
    avait ete lu.

    Mode non interactif: **aucune** lecture de `in_stream` n'est tentee. Une
    commande en CI ne doit jamais se bloquer sur une entree qui ne viendra
    pas -- `input()` sur un `stdin` ouvert mais vide bloque indefiniment, ce
    qui produit un job qui ne se termine jamais. La detection du mode a donc
    lieu chez l'appelant, avant tout acces au flux.

    Le refus n'est **pas** une erreur: niveau `warning` au plus, pas de
    prefixe `Erreur:`, pas de trace d'exception. `EOFError` et
    `KeyboardInterrupt` sont des refus ordinaires, et une reponse vide vaut
    non (un `Entree` reflexe ne doit pas lancer une extraction de plusieurs
    heures et plusieurs dizaines de gigaoctets).
    """
    text = render_source_report(report)
    _write(out_stream, text + "\n")
    _log_report(logger, text)

    mode = CONFIRMATION_MODE_INTERACTIVE if interactive else CONFIRMATION_MODE_NON_INTERACTIVE

    if interactive:
        granted, message = _ask_interactively(report, out_stream, in_stream)
    else:
        granted, message = _decide_non_interactively(
            report,
            consent_granted=consent_granted,
            unknown_color_accepted=unknown_color_accepted,
        )

    # Le champ n'est jamais laisse indefini (3.4 le persiste). Il enregistre ce
    # qui a ete accepte pour CE lot: sans colorimetrie manquante, il n'y a rien
    # a accepter, donc il vaut False, dans les deux modes.
    accepted_unknown_color = bool(granted and report.requires_unknown_color_consent)

    result = ConfirmationResult(
        granted=granted,
        mode=mode,
        unknown_color_accepted=accepted_unknown_color,
        confirmed_at=_utc_now_rfc3339(),
        absent_fields=report.absent_fields,
        message=message,
    )

    if not granted:
        _write(out_stream, message + "\n")
    _log_decision(logger, result)
    return result


def _ask_interactively(
    report: SourceReport, out_stream: Any, in_stream: Any
) -> tuple[bool, str]:
    if in_stream is None:
        return False, "Confirmation non accordee: aucun flux d'entree disponible."

    _write(out_stream, render_confirmation_question(report))
    try:
        raw = in_stream.readline()
    except (EOFError, KeyboardInterrupt, OSError, ValueError):
        # Meme convention defensive que `_is_tty`, qui rattrape deja largement:
        # un terminal ferme ou rompu pendant la lecture ne leve pas `EOFError`
        # mais `ValueError` ("I/O operation on closed file") ou `OSError`. Sans
        # cette branche, la seule chose que verrait l'operateur serait une trace
        # Python. Le refus est la seule issue sure: on n'extrait jamais sans
        # accord, et un accord qui n'a pas pu etre lu n'a pas ete donne.
        return False, "Confirmation non accordee: saisie interrompue. Aucune frame n'a ete ecrite."

    if raw == "":  # fin de flux
        return False, "Confirmation non accordee: fin de l'entree. Aucune frame n'a ete ecrite."

    answer = str(raw).strip().lower()
    if answer in _AFFIRMATIVE_ANSWERS:
        return True, "Confirmation accordee."
    return False, "Confirmation non accordee. Aucune frame n'a ete ecrite."


def _decide_non_interactively(
    report: SourceReport, *, consent_granted: bool, unknown_color_accepted: bool
) -> tuple[bool, str]:
    if not consent_granted:
        hint = f"Passer {CONSENT_OPTION_HINT} pour donner l'accord sans terminal interactif"
        if report.requires_unknown_color_consent:
            hint += (
                f", et {UNKNOWN_COLOR_OPTION_HINT} car la colorimetrie source est "
                f"{report.color_triplet_status}"
            )
        return False, f"Confirmation non accordee: consentement absent en mode non interactif. {hint}."
    if report.requires_unknown_color_consent and not unknown_color_accepted:
        return False, (
            "Confirmation non accordee: la colorimetrie source est "
            f"{report.color_triplet_status} et exige un consentement supplementaire "
            f"explicite. Passer {UNKNOWN_COLOR_OPTION_HINT} en plus de "
            f"{CONSENT_OPTION_HINT}."
        )
    return True, "Confirmation accordee (mode non interactif)."


def _log_decision(logger: logging.Logger | None, result: ConfirmationResult) -> None:
    if logger is None:
        return
    absent = ", ".join(result.absent_fields) if result.absent_fields else "aucun"
    line = (
        f"Decision de confirmation: granted={str(result.granted).lower()}, "
        f"mode={result.mode}, "
        f"unknown_color_accepted={str(result.unknown_color_accepted).lower()}, "
        f"confirmed_at={result.confirmed_at}, champs source non renseignes: {absent}. "
        f"{result.message}"
    )
    if result.granted:
        logger.info(line)
    else:
        # Piege 11: un refus n'est pas une erreur. Le router en `error`
        # polluerait toute recherche d'erreur reelle dans les journaux.
        logger.warning(line)
