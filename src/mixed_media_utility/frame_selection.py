"""Selection deterministe des frames source (story 3.2).

Perimetre
---------
Ce module possede **la regle de selection**, et rien d'autre: cardinal
retenu, indices de frames source, timecodes, politique d'arrondi, codes
d'avertissement. Il est **pur**: aucune I/O, aucun disque, aucun manifest,
aucun subprocess, aucun ffmpeg/ffprobe, aucun cv2, aucune CLI, aucune
sortie standard. Il est importable et entierement testable sans binaire
externe (AC 1, verrouille par une analyse AST dans
``tests/unit/test_frame_selection.py``).

L'execution de la decision (invocation ffmpeg, ecriture TIFF, noms de
fichiers, codes de sortie) appartient a la story 3.1; l'UX de confirmation
a la 3.3; la persistance manifest a la 3.4; la previz a la 3.5.

Politique d'arrondi (identifiant ``ROUNDING_POLICY_ID``)
-------------------------------------------------------
Tout est evalue en arithmetique rationnelle exacte (``fractions.Fraction``).
**Aucun ``float`` n'arbitre**: les cadences entrent par
``codec_profiles.exact_frame_rate`` puis ``Fraction(...)`` sur la chaine
``"num/den"`` retournee, ce qui recale au passage les decimales NTSC
arrondies (``23.976`` -> ``24000/1001``)::

    k               = fps_source / fps_target                             (k >= 1)
    N               = ceil(source_frame_count * fps_target / fps_source)
    source_index(n) = floor(n * fps_source / fps_target)   pour n dans [0, N-1]

``floor`` sur l'indice retient la frame **reellement affichee** a l'instant
cible ``n / fps_target`` (semantique de maintien, causale: jamais une image
du futur) et surtout n'a **aucun cas d'egalite a departager**, contrairement
a un arrondi au plus proche dont le tie-break (half-up / half-even) diverge
entre plateformes — c'est exactement le mecanisme du risque R4 du
``TEST_PLAN``.

``ceil`` sur le cardinal: ``n`` doit satisfaire ``n * k < source_frame_count``,
donc le nombre d'entiers valides est ``ceil(source_frame_count / k)``. La
formule couvre sans branche speciale le cas divisible comme le cas non
divisible, et garantit ``N >= 1`` des que la source a au moins une frame.

Proprietes garanties par construction (et verrouillees par tests de
propriete): suite **strictement croissante**, sans doublon, sans frame
synthetique, entierement contenue dans ``[0, source_frame_count - 1]``;
ecart entre deux indices consecutifs toujours dans ``{floor(k), ceil(k)}``,
donc jitter borne a une frame et jamais cumulatif.

Politiques envisagees et **rejetees** — a ne pas reintroduire par refactor:

* arrondi au plus proche sur l'indice: introduit un cas d'egalite dont le
  tie-break n'est pas portable entre machines;
* ``linspace(0, F - 1, N)`` arrondi (le reflexe courant): force l'inclusion
  de la derniere frame au prix d'intervalles non uniformes aux extremites,
  ce qui deforme la cadence reconstruite (R13), et passe par des flottants,
  donc par une precision dependante de la plateforme.

Dernier intervalle
------------------
La derniere frame source n'est generalement **pas** retenue (100 frames a
30 fps vers 4 fps -> dernier indice 97). ``FrameSelection.source_tail_frames``
expose exactement ``source_frame_count - 1 - dernier_index``: c'est une
donnee, pas un defaut.

Fenetre d'extraction bornee (story 3.7)
---------------------------------------
``source_in_timecode`` et ``source_out_timecode`` restreignent la selection a
une fenetre ``[in_index, out_index]`` du fichier, bornes **incluses**::

    in_index        = (timecode -> frames  -  offset_frames) % (86400 * fps_nominale)
    N               = ceil((out_index - in_index + 1) / k)
    source_index(n) = in_index + floor(n * k)

C'est la meme formule qu'au-dessus, generalisee: sans borne, ``in_index``
vaut 0, ``out_index`` vaut ``source_frame_count - 1`` et le resultat est
rigoureusement celui d'avant la story 3.7.

Trois points de vigilance, tous verifies par tests:

* les bornes sont exprimees dans la base du timecode **affiche** (donc offset
  de ``source_start_timecode`` inclus), alors que ``source_index`` est
  toujours un indice base zero du fichier brut: d'ou la soustraction;
* la soustraction est **modulaire sur 24 h**, parce que ``_format_timecode``
  reboucle deja: un rush demarre en soiree franchit minuit et une borne lue a
  l'ecran donnerait sinon un indice negatif;
* ``MAX_EXPECTED_FRAME_COUNT`` s'applique **apres** le calcul de fenetre,
  donc sur le cardinal de la fenetre. C'est ce qui permet a un rush long de
  rentrer sous le plafond a cadence elevee des lors que l'extrait est court
  (ARB-10). ``source_tail_frames``, ``source_duration_seconds`` et
  ``source_frame_count_is_exact`` restent en revanche evalues sur le
  **fichier entier**: ce sont des donnees du fichier, pas de la fenetre.

Base de temps du timecode
-------------------------
``timecode_base == "source"`` (decision d'arbitrage du 2026-08-03,
``decisions-2026-08-03.md``, decision 3 / ARB-2). Chaque frame porte un
timecode SMPTE **non-drop-frame** ``hh:mm:ss:ff`` exprime dans la base de la
cadence **source**, avec offset optionnel ``source_start_timecode``. La
meme image physique porte donc toujours le meme timecode, quelle que soit
la cadence d'extraction.

* ``timecode_base_fps`` porte la cadence source **exacte** (la ``Fraction``),
  c'est la valeur a repasser telle quelle a
  ``codec_profiles.validate_timecode``. Ce n'est **pas** la cadence nominale
  entiere du champ ``ff``: celle-ci vaut ``ceil(fps_source)`` et s'en deduit,
  elle n'est pas un champ separe.
* **Piege de lecture aval, desormais ferme dans le nom mais pas dans le
  raisonnement**: ``io/naming.build_frame_filename`` a longtemps produit
  ``..._tc{timecode}_fps{fps_target}...``, ce qui se lisait spontanement
  comme "ce timecode est a cette cadence". C'etait **faux**: ``fps_target``
  identifie le *lot*, pas la base du timecode. Depuis `EPIC7-ARB-91` le
  segment ``_fps`` a disparu du nom (la cadence reste lisible dans le
  fragment ``lot_id``, qui vaut ``<rush>_<cadence>``), mais la confusion
  reste possible sur la valeur elle-meme : valider un ``frame_timecode``
  contre ``fps_target`` le **rejette** des que ``ff >= ceil(fps_target)``
  (source 30 fps, cible 4 fps, indice 97 -> ``00:00:03:07``, et ``07 >= 4``).
  Toute validation aval se fait contre ``timecode_base_fps``.
* Le compteur d'heures **reboucle a 24 h** (convention SMPTE) avant
  formatage: sans cela ``validate_timecode`` leverait "Timecode hors bornes"
  des ``hh > 23``.
* Le drop-frame (``;``) n'est **jamais** emis, et un ``source_start_timecode``
  drop-frame est refuse en entree: ``validate_timecode`` verifie que ``;``
  n'est employe qu'a une cadence NTSC mais **pas** la legalite interne du
  numero de frame, donc le projet ne sait pas verifier ce qu'il produirait.
* Derive assumee: des que ``fps_source`` n'est pas entiere, ``ff`` est
  compte sur ``ceil(fps_source)`` — seule borne compatible avec
  ``validate_timecode`` — et le timecode derive donc par rapport au temps
  reel: environ 3,6 s par heure a 23.976 (comportement NDF standard), mais
  pres de 2 min 19 s par heure a 12.5 fps (base 13). Le noyau ne corrige pas
  cette derive; il la signale par ``NON_INTEGER_SOURCE_RATE``. A ces
  cadences, le timecode reste un identifiant de frame strictement ordonne et
  reversible, ce n'est plus une adresse temporelle fiable.

Regles de consommation (elles engagent 3.1, 3.3, 3.4 et 3.5)
------------------------------------------------------------
* ``output_rank`` et ``source_index`` sont **base zero**
  (``ARCHITECTURE_DETAILED.md`` section 3.1, normatif). Toute presentation
  base un se fait au rendu uniquement.
* ``output_rank`` est l'ordre canonique du lot: le consommateur ne re-trie
  **jamais** la sequence.
* ``expected_frame_count`` est la valeur a ecrire telle quelle dans le
  manifest, jamais un comptage de fichiers sur disque a posteriori: sinon
  une extraction partielle se declarerait complete.
* ``warnings`` porte des **codes** ASCII stables, sans doublon, dans l'ordre
  canonique de ``WARNING_CODES``. La traduction utilisateur appartient a
  3.1/3.3. L'ordre est normatif: 3.4 les persiste et 3.5 les transporte
  verbatim.
* ``FrameSelection`` satisfait ``Sequence[SelectedFrame]`` (``len()``,
  iteration, indexation) et rediffuse ``source_frame_count_is_exact`` et
  ``source_start_timecode``, que ses consommateurs lisent **ici** et nulle
  part ailleurs.

Ce que ce module ne fait pas
----------------------------
* Il n'implemente **aucune** detection de VFR: il ne voit jamais le flux et
  une cadence variable n'a de toute facon pas de ``fps_source`` unique. Il
  fait confiance a la garde amont de la story 3.1 (son AC 8) et pose la
  seule garde qu'il peut poser: la coherence
  ``source_frame_count`` / ``source_duration_seconds`` a une frame pres.
  ``source_duration_seconds`` designe la duree du **flux video**
  (``streams[].duration``), jamais celle du conteneur
  (``format.duration``), qui integre couramment la piste audio, une edit
  list ou un padding de fin et transformerait la garde en faux positif sur
  une source CFR saine.
* Il ne derive **jamais** le cardinal source d'une duree: il l'exige.
  Quand l'appelant n'a qu'une estimation, il passe
  ``source_frame_count_is_exact=False`` et le noyau emet
  ``SOURCE_FRAME_COUNT_ESTIMATED`` plutot que de deviner.
* Il ne **refuse pas** le NTSC ni les cadences non entieres: il remonte des
  codes d'avertissement. La decision de refuser est une regle de surface qui
  appartient a 3.1/3.3, proprietaires de l'UX et des codes de sortie.
* Il ne reimplemente ni ``exact_frame_rate``, ni ``NTSC_RATES``, ni
  ``validate_timecode``: ils sont consommes tels quels depuis
  ``codec_profiles``.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from fractions import Fraction
from math import ceil, floor
from typing import Union

from .codec_profiles import NTSC_RATES, exact_frame_rate, validate_timecode
from .numeric_guards import is_strict_int, is_strict_number

__all__ = [
    "MAX_SOURCE_FRAME_RATE",
    "MAX_EXPECTED_FRAME_COUNT",
    "ROUNDING_POLICY_ID",
    "TIMECODE_BASE",
    "WARNING_CODES",
    "WARNING_NTSC_RATE_OUT_OF_SCOPE",
    "WARNING_NON_INTEGER_SOURCE_RATE",
    "WARNING_NON_INTEGER_TARGET_RATE",
    "WARNING_NON_DIVISIBLE_RATES",
    "WARNING_SOURCE_FRAME_COUNT_ESTIMATED",
    "FrameSelectionError",
    "InvalidFrameRateError",
    "SelectionTooLargeError",
    "UpsamplingNotSupportedError",
    "EmptySourceError",
    "InconsistentSourceDurationError",
    "InvalidStartTimecodeError",
    "InvalidBoundsError",
    "SelectedFrame",
    "FrameSelection",
    "select_source_frames",
]


# Identifiant de politique d'arrondi. Il fait partie du contrat persiste
# (3.4, `lots[].rounding_policy`) et entre dans l'empreinte de selection de
# 3.5: changer la regle sans changer cet identifiant rendrait deux lots
# incomparables sans que rien ne le signale.
#: Cadence source maximale acceptee, en images par seconde (ARB-11,
#: `decisions-2026-08-05.md`). Tranchee par Egan le 2026-08-05, puis relevee de
#: 50 a 60 le meme jour: **le 59.94p doit rester traitable**, et la garde
#: compare `ceil(cadence)`, or `ceil(60000/1001) == 60`. Un plafond a 50 aurait
#: exclu une cadence de diffusion courante.
#:
#: La limite technique dure reste 100 -- le champ frames de `hh:mm:ss:ff` ne
#: porte que deux chiffres -- mais la limite **produit** est plus basse et
#: assumee: les rushs a 120 ou 240 i/s (ralentis) restent hors perimetre du MVP.
MAX_SOURCE_FRAME_RATE = 60

#: Nombre maximal d'images qu'un lot peut porter (ARB-10,
#: `decisions-2026-08-05.md`). Le plafond porte sur le **nombre d'images** et
#: non sur la duree du rush: c'est le nombre d'images qui determine le cout
#: disque, le nombre de planches a imprimer et le temps de scan. A 1920x1080 en
#: TIFF 16 bits, 1000 images pesent environ 12 Go et representent 500 planches
#: a deux images par planche, deja au-dela de ce qu'un atelier absorbe.
MAX_EXPECTED_FRAME_COUNT = 1000

ROUNDING_POLICY_ID = "floor-index-ceil-count-v1"

# Base de temps des timecodes emis (arbitrage ARB-2 du 2026-08-03).
TIMECODE_BASE = "source"

RateLike = Union[float, int, str, Fraction]

WARNING_NTSC_RATE_OUT_OF_SCOPE = "NTSC_RATE_OUT_OF_SCOPE"
WARNING_NON_INTEGER_SOURCE_RATE = "NON_INTEGER_SOURCE_RATE"
WARNING_NON_INTEGER_TARGET_RATE = "NON_INTEGER_TARGET_RATE"
WARNING_NON_DIVISIBLE_RATES = "NON_DIVISIBLE_RATES"
WARNING_SOURCE_FRAME_COUNT_ESTIMATED = "SOURCE_FRAME_COUNT_ESTIMATED"

# Ordre canonique et normatif des codes d'avertissement. `warnings` est
# toujours un sous-ensemble de ce tuple, dans cet ordre, sans doublon:
# l'egalite d'objets exigee par l'AC 7 en depend, et 3.4/3.5 les persistent
# et les transportent verbatim.
WARNING_CODES = (
    WARNING_NTSC_RATE_OUT_OF_SCOPE,
    WARNING_NON_INTEGER_SOURCE_RATE,
    WARNING_NON_INTEGER_TARGET_RATE,
    WARNING_NON_DIVISIBLE_RATES,
    WARNING_SOURCE_FRAME_COUNT_ESTIMATED,
)

_SECONDS_PER_DAY = 24 * 3600


class FrameSelectionError(ValueError):
    """Racine de toutes les erreurs du module.

    Elle derive de ``ValueError`` pour rester capturable par un appelant
    generique, mais un appelant informe capture cette classe unique: aucune
    entree invalide ne retourne une selection vide en silence.
    """


class SelectionTooLargeError(FrameSelectionError):
    """Le lot depasserait le plafond d'images (ARB-10).

    Distincte des erreurs de cadence: les entrees sont valides, c'est leur
    **produit** qui sort du perimetre operationnel de l'outil.
    """


class InvalidFrameRateError(FrameSelectionError):
    """Cadence source ou cible inutilisable.

    Encapsule les ``ValueError`` / ``TypeError`` remontees par
    ``codec_profiles.exact_frame_rate`` (cadence nulle, negative, non finie,
    type invalide) en conservant ``__cause__``.
    """


class UpsamplingNotSupportedError(FrameSelectionError):
    """``fps_target`` depasse ``fps_source``.

    Plafonner silencieusement a ``fps_source`` produirait un lot dont la
    cadence reelle differe du ``fps_target`` declare, valeur qui se propage
    ensuite dans le nom de dossier, le nom de fichier, le payload QR et le
    manifest: corruption silencieuse sur quatre canaux.
    """


class EmptySourceError(FrameSelectionError):
    """Declaration du cardinal source inutilisable.

    Couvre ``source_frame_count`` absent, non entier ou inferieur a 1, ainsi
    que ``source_frame_count_is_exact`` non booleen: le drapeau fait partie de
    la meme declaration, et le noyau ne devine pas plus l'un que l'autre.
    """


class InconsistentSourceDurationError(FrameSelectionError):
    """``source_frame_count`` et ``source_duration_seconds`` divergent.

    Au-dela d'une frame d'ecart, c'est la signature d'un VFR ou d'une
    cadence nominale fausse. R4 exige un echec explicite, jamais une
    approximation silencieuse.
    """


class InvalidStartTimecodeError(FrameSelectionError):
    """``source_start_timecode`` malforme, hors bornes ou drop-frame."""


class InvalidBoundsError(FrameSelectionError):
    """``source_in_timecode`` / ``source_out_timecode`` inutilisables (story 3.7).

    Volontairement **distincte** de ``InvalidStartTimecodeError``: les trois
    valeurs sont des timecodes de la meme base, mais elles ne jouent pas le
    meme role et l'operateur doit savoir laquelle des trois est en cause.
    Couvre le timecode de borne malforme ou drop-frame, la borne d'entree
    posterieure a la borne de sortie, et la borne de sortie au-dela du dernier
    index du rush.
    """


@dataclass(frozen=True)
class SelectedFrame:
    """Une frame source retenue, dans l'ordre canonique du lot.

    ``output_rank`` et ``source_index`` sont **base zero**.
    ``frame_timecode`` est un SMPTE non-drop-frame ``hh:mm:ss:ff`` exprime
    dans la base de temps **source** (voir la docstring du module).
    """

    output_rank: int
    source_index: int
    frame_timecode: str


@dataclass(frozen=True)
class FrameSelection(Sequence):
    """Resultat complet d'une selection, fige et comparable.

    Satisfait ``Sequence[SelectedFrame]``: ``len(selection)``,
    ``for frame in selection`` et ``selection[i]`` fonctionnent
    litteralement, ce qui rend valide le point de couture attendu par la
    story 3.1 (``-> Sequence[SelectedFrame]``) tout en portant les champs
    dont 3.3, 3.4 et 3.5 ont besoin.
    """

    frames: tuple[SelectedFrame, ...]
    fps_source: Fraction
    fps_target: Fraction
    source_frame_count: int
    source_frame_count_is_exact: bool
    expected_frame_count: int
    source_tail_frames: int
    rounding_policy: str
    timecode_base: str
    timecode_base_fps: Fraction
    source_start_timecode: str | None
    warnings: tuple[str, ...]
    #: Bornes de fenetre de la story 3.7, rediffusees **verbatim** telles que
    #: l'appelant les a fournies, jamais recalculees ni normalisees. Elles sont
    #: declarees en fin de dataclass, et non a cote de ``source_start_timecode``
    #: comme leur role le suggererait, parce qu'un champ a valeur par defaut ne
    #: peut pas preceder un champ sans defaut: les inserer plus haut exigerait
    #: de donner un defaut a ``warnings``, donc d'autoriser une selection sans
    #: table d'avertissements, et de modifier les appels existants (AC 14).
    source_in_timecode: str | None = None
    source_out_timecode: str | None = None

    def __len__(self) -> int:
        return len(self.frames)

    def __iter__(self) -> Iterator[SelectedFrame]:
        return iter(self.frames)

    def __getitem__(self, index):
        return self.frames[index]


def _normalize_rate(fps: RateLike, label: str) -> Fraction:
    """Normaliser une cadence en ``Fraction`` exacte.

    Passe **systematiquement** par ``codec_profiles.exact_frame_rate``, seule
    source de verite du depot: elle recale les decimales NTSC arrondies sur
    leur ratio exact. Construire une cadence depuis un ``float`` court-circuite
    ce recalage (``Fraction(23.976)`` rend le ratio binaire du flottant,
    ``Fraction("23.976")`` rend ``2997/125``, jamais ``24000/1001``).
    """
    try:
        exact = exact_frame_rate(fps)
    except (ValueError, TypeError, OverflowError, ZeroDivisionError) as error:
        # `ZeroDivisionError` n'est pas defensive: `exact_frame_rate` passe une
        # chaine "num/den" telle quelle a `Fraction`, et ffprobe emet
        # litteralement `r_frame_rate = "0/0"` sur un flux dont il ne sait pas
        # deduire la cadence. C'est exactement la valeur que la story 3.1
        # transmet ici (`video_metadata` lit `r_frame_rate` verbatim), et elle
        # remontait en `ZeroDivisionError` nue, hors de la hierarchie du module.
        raise InvalidFrameRateError(
            f"Cadence {label} invalide: {fps!r} ({error})"
        ) from error
    return Fraction(exact)


def _normalize_frame_count(source_frame_count: object) -> int:
    if not is_strict_int(source_frame_count):
        raise EmptySourceError(
            "source_frame_count doit etre un entier, "
            f"recu {source_frame_count!r}: le noyau ne derive jamais le cardinal "
            "d'une duree, il l'exige"
        )
    if source_frame_count < 1:
        raise EmptySourceError(
            f"source_frame_count doit valoir au moins 1, recu {source_frame_count}: "
            "une source vide ne produit pas un lot vide, elle produit une erreur"
        )
    return source_frame_count


def _normalize_exactness_flag(source_frame_count_is_exact: object) -> bool:
    """Exiger un booleen strict, ne jamais coercer.

    La table normative des codes d'avertissement conditionne
    ``SOURCE_FRAME_COUNT_ESTIMATED`` a ``source_frame_count_is_exact is False``.
    Un ``bool(...)`` diverge de cette table dans les deux sens, et surtout dans
    le sens dangereux: ``"false"`` est une chaine non vide, donc vraie, si bien
    qu'un cardinal estime serait rediffuse comme exact et persiste tel quel par
    3.4, sans qu'aucun code ne signale la degradation. C'est precisement le mode
    de defaillance silencieux que ce module s'interdit. Meme discipline de type
    que ``_normalize_frame_count``.
    """
    if not isinstance(source_frame_count_is_exact, bool):
        raise EmptySourceError(
            "source_frame_count_is_exact doit etre un booleen, recu "
            f"{source_frame_count_is_exact!r}: convertir cette valeur en booleen "
            "ici reviendrait a declarer exact un cardinal estime (la chaine "
            "'false' est vraie) et a emettre SOURCE_FRAME_COUNT_ESTIMATED en "
            "desaccord avec la table normative des avertissements"
        )
    return source_frame_count_is_exact


def _check_duration_consistency(
    source_duration_seconds: object,
    source_frame_count: int,
    fps_source: Fraction,
) -> None:
    """Garde de coherence cardinal / duree, a une frame pres.

    ``source_duration_seconds`` doit etre la duree du **flux video**
    (``streams[].duration``), jamais celle du conteneur.
    """
    if not is_strict_number(source_duration_seconds) and not isinstance(
        source_duration_seconds, Fraction
    ):
        raise InconsistentSourceDurationError(
            "source_duration_seconds doit etre un nombre de secondes ou None, "
            f"recu {source_duration_seconds!r}"
        )
    if isinstance(source_duration_seconds, float) and (
        source_duration_seconds != source_duration_seconds
        or source_duration_seconds in (float("inf"), float("-inf"))
    ):
        raise InconsistentSourceDurationError(
            f"source_duration_seconds non fini: {source_duration_seconds!r}"
        )
    # Conversion en Fraction avant toute comparaison: aucun float ne doit
    # entrer dans le chemin de decision (Piege 7).
    duration = Fraction(source_duration_seconds)
    if duration <= 0:
        raise InconsistentSourceDurationError(
            f"source_duration_seconds doit etre strictement positif, recu "
            f"{source_duration_seconds!r}"
        )
    expected = duration * fps_source
    deviation = abs(Fraction(source_frame_count) - expected)
    if deviation > 1:
        raise InconsistentSourceDurationError(
            f"Cardinal source incoherent avec la duree du flux: "
            f"{source_frame_count} frames declarees contre {float(expected):.3f} "
            f"attendues ({source_duration_seconds} s a {fps_source} fps), soit "
            f"{float(deviation):.3f} frames d'ecart pour une tolerance de 1. "
            "Signature usuelle d'un flux a cadence variable ou d'une cadence "
            "nominale fausse: fournir un cardinal exact (ffprobe -count_frames) "
            "ou la duree du flux video (streams[].duration) et non celle du "
            "conteneur (format.duration)"
        )


def _timecode_to_frames(
    timecode: object,
    nominal_fps: int,
    fps_source: Fraction,
    *,
    label: str,
    error_class: type[FrameSelectionError],
) -> int:
    """Convertir un timecode SMPTE non-drop-frame en nombre de frames.

    **Implementation unique** de l'arithmetique ``((h*60+m)*60+s)*fps+f`` et de
    sa validation, partagee par les trois timecodes que le noyau accepte
    (``source_start_timecode``, ``source_in_timecode``, ``source_out_timecode``).
    ``label`` et ``error_class`` sont ce qui les distingue: une borne n'est pas
    un timecode de depart, et l'operateur doit lire laquelle des trois valeurs
    il doit corriger (AC 3 de la story 3.7).
    """
    if not isinstance(timecode, str):
        raise error_class(
            f"{label} doit etre une chaine hh:mm:ss:ff ou None, recu {timecode!r}"
        )
    if ";" in timecode:
        raise error_class(
            f"{label} drop-frame refuse: {timecode!r}. "
            "Le drop-frame n'est jamais emis ni accepte par ce noyau: le projet "
            "ne sait pas verifier la legalite interne d'un numero de frame "
            "drop-frame"
        )
    try:
        validate_timecode(timecode, fps_source)
    except (ValueError, TypeError) as error:
        raise error_class(f"{label} invalide: {timecode!r} ({error})") from error
    hours, minutes, seconds, frames = (int(part) for part in timecode.split(":"))
    return ((hours * 60 + minutes) * 60 + seconds) * nominal_fps + frames


def _start_offset_frames(
    source_start_timecode: str | None, nominal_fps: int, fps_source: Fraction
) -> int:
    """Convertir ``source_start_timecode`` en nombre de frames source."""
    if source_start_timecode is None:
        return 0
    return _timecode_to_frames(
        source_start_timecode,
        nominal_fps,
        fps_source,
        label="source_start_timecode",
        error_class=InvalidStartTimecodeError,
    )


def _bound_index(
    bound_timecode: object,
    offset_frames: int,
    nominal_fps: int,
    fps_source: Fraction,
    *,
    label: str,
) -> int:
    """Convertir une borne operateur en **indice base zero du fichier brut**.

    Deux points, tous deux non negociables (AC 2 de la story 3.7):

    * la borne est exprimee dans la meme base que ``source_start_timecode``,
      c'est-a-dire le timecode SMPTE tel qu'affiche partout ailleurs dans le
      projet; l'indice, lui, ne porte **jamais** l'offset, d'ou la
      soustraction;
    * la soustraction se fait **modulo un jour**, parce que ``_format_timecode``
      reboucle deja a 24 h. Un rush demarre a ``23:50:00:00`` affiche
      ``00:02:00:00`` a l'ecran pour son indice 18 000: sans modulo, cette
      borne lue a l'ecran donnerait ``3000 - 2145000``, un indice negatif, et
      un diagnostic faux sur une valeur que l'operateur vient de lire.
    """
    total_frames = _timecode_to_frames(
        bound_timecode,
        nominal_fps,
        fps_source,
        label=label,
        error_class=InvalidBoundsError,
    )
    return (total_frames - offset_frames) % (_SECONDS_PER_DAY * nominal_fps)


def _rate_that_actually_fits(cadence: Fraction) -> str:
    """Rendre une cadence **arrondie vers le bas**, donc reellement extractible.

    Revue du 2026-08-06. Le message de refus formatait cette valeur avec
    ``:.3g``, qui arrondit au plus proche, **donc parfois vers le haut**:
    l'operateur se voyait conseiller une cadence qui reproduisait le refus.
    Mesure: fenetre de 5001 images a 25 im/s -> conseil de 5 im/s -> 1001
    images, refusees a nouveau. Un balayage exhaustif avait trouve plus de
    trois mille fenetres dans ce cas.

    L'arrondi vers le bas est **suffisant** et pas seulement prudent:
    ``expected_frame_count = ceil(fenetre * cible / source)`` croit avec la
    cadence cible, et ``cadence`` produit exactement le plafond; toute valeur
    inferieure produit donc au plus le plafond.

    La precision s'etend tant que trois chiffres significatifs rendraient
    zero: sur un rush de plusieurs heures, la cadence qui rentre descend sous
    0,01 im/s, et conseiller ``0`` ne serait pas un conseil.
    """
    if cadence <= 0:
        # Inatteignable par construction (plafond et cadence source positifs),
        # mais un conseil de zero serait pire qu'une absence de conseil.
        raise ValueError("cadence de repli non positive")

    exposant = 0
    echelle = Fraction(cadence)
    while echelle >= 10:
        echelle /= 10
        exposant += 1
    while echelle < 1:
        echelle *= 10
        exposant -= 1

    for chiffres in range(3, 13):
        decimales = chiffres - 1 - exposant
        plancher = int(cadence * Fraction(10) ** decimales)  # troncature = vers le bas
        if plancher <= 0:
            continue
        if decimales <= 0:
            return str(plancher * 10 ** (-decimales))
        chiffres_texte = str(plancher).rjust(decimales + 1, "0")
        entier, fraction = chiffres_texte[:-decimales], chiffres_texte[-decimales:]
        return f"{entier}.{fraction}".rstrip("0").rstrip(".")

    raise ValueError(f"cadence de repli non representable: {cadence}")


def _wraparound_hint(offset_frames: int) -> str:
    """Rappel du rebouclage a 24 h, **seulement quand il explique quelque chose**.

    Revue du 2026-08-06: la phrase etait concatenee sans condition, y compris
    sur un rush sans timecode de depart ou aucun rebouclage n'est possible.
    Elle expliquait alors le cas d'une borne anterieure au debut du rush a un
    operateur qui venait d'en poser une posterieure a sa fin.
    """
    if offset_frames == 0:
        return ""
    return (
        " Une borne anterieure au debut du rush ne produit jamais un index "
        "negatif: le comptage des timecodes reboucle a 24 h, elle se traduit "
        "donc en un index tres grand."
    )


def _rush_timecode_span(
    offset_frames: int,
    frame_count: int,
    nominal_fps: int,
    source_start_timecode: str | None,
    *,
    count_is_exact: bool = True,
) -> str:
    """Rappel de la plage de timecodes reellement couverte par le rush.

    Sans lui, un refus de bornage reste incomprehensible: l'operateur ne sait
    pas contre quoi sa borne a ete comparee. Le cas du rush sans tag timecode
    est dit explicitement (ARB-20), faute de quoi l'operateur croira que ses
    bornes d'horloge de tournage sont mal interpretees alors que c'est le rush
    qui ne porte rien.
    """
    premier = _format_timecode(offset_frames, nominal_fps)
    dernier = _format_timecode(offset_frames + frame_count - 1, nominal_fps)
    rappel = (
        f"Ce rush couvre {premier} a {dernier} ({frame_count} images, "
        f"index 0 a {frame_count - 1})."
    )
    if not count_is_exact:
        # Revue du 2026-08-06: le message etait identique au caractere pres,
        # que le cardinal soit compte ou estime. L'operateur se voyait refuser
        # une borne peut-etre valide contre un nombre d'images que l'outil
        # lui-meme ne fait qu'estimer, sans que rien ne le lui dise.
        rappel += (
            " Attention: ce nombre d'images est une ESTIMATION (duree x cadence),"
            " le conteneur ne declarant pas son compte exact. La borne refusee"
            " est peut-etre valide, et une borne acceptee peut depasser la vraie"
            " fin du rush. Reencoder la source dans un conteneur qui declare son"
            " nombre d'images leve l'incertitude."
        )
    if source_start_timecode is None:
        rappel += (
            " Attention: la source ne porte aucun timecode, le comptage part donc "
            "de 00:00:00:00 et non d'un timecode d'horloge de tournage."
        )
    return rappel


def _format_timecode(total_frames: int, nominal_fps: int) -> str:
    """Formater un compte de frames en ``hh:mm:ss:ff``, reboucle a 24 h.

    Le rebouclage n'est pas optionnel: ``validate_timecode`` leve
    "Timecode hors bornes" des ``hh > 23``, et un rush de vingt minutes
    demarrant a ``23:50:00:00`` deborde.
    """
    wrapped = total_frames % (_SECONDS_PER_DAY * nominal_fps)
    frames = wrapped % nominal_fps
    total_seconds = wrapped // nominal_fps
    seconds = total_seconds % 60
    minutes = (total_seconds // 60) % 60
    hours = total_seconds // 3600
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"


def _collect_warnings(
    fps_source: Fraction,
    fps_target: Fraction,
    source_frame_count_is_exact: bool,
) -> tuple[str, ...]:
    """Assembler les codes d'avertissement dans l'ordre canonique.

    Les conditions sont independantes: une cadence NTSC identique en source
    et en cible emet les trois premiers codes et **pas**
    ``NON_DIVISIBLE_RATES`` (``k = 1``).
    """
    emitted = set()
    # Appartenance a la constante du depot, jamais une liste redeclaree ni
    # une comparaison de flottants.
    if fps_source in NTSC_RATES or fps_target in NTSC_RATES:
        emitted.add(WARNING_NTSC_RATE_OUT_OF_SCOPE)
    if fps_source.denominator != 1:
        emitted.add(WARNING_NON_INTEGER_SOURCE_RATE)
    if fps_target.denominator != 1:
        emitted.add(WARNING_NON_INTEGER_TARGET_RATE)
    if (fps_source / fps_target).denominator != 1:
        emitted.add(WARNING_NON_DIVISIBLE_RATES)
    if source_frame_count_is_exact is False:
        emitted.add(WARNING_SOURCE_FRAME_COUNT_ESTIMATED)
    return tuple(code for code in WARNING_CODES if code in emitted)


def select_source_frames(
    *,
    fps_source: RateLike,
    fps_target: RateLike,
    source_frame_count: int,
    source_start_timecode: str | None = None,
    source_in_timecode: str | None = None,
    source_out_timecode: str | None = None,
    source_duration_seconds: float | int | Fraction | None = None,
    source_frame_count_is_exact: bool = True,
) -> FrameSelection:
    """Selectionner les frames source a extraire, de facon exactement reproductible.

    Deux machines differentes produisent rigoureusement le meme lot: tout le
    chemin de decision est en arithmetique rationnelle exacte, sans aucun
    ``float`` (voir la docstring du module pour la politique d'arrondi et la
    base de temps des timecodes).

    Parameters
    ----------
    fps_source, fps_target:
        Cadences, sous n'importe quelle forme acceptee par
        ``codec_profiles.exact_frame_rate`` (``float``, ``int``,
        ``"num/den"``, ``Fraction``). ``23.976``, ``"24000/1001"`` et
        ``Fraction(24000, 1001)`` produisent une selection **identique**.
    source_frame_count:
        Cardinal **exact** de frames du flux source, base un (un cardinal,
        pas un indice). Le noyau ne le derive jamais d'une duree.
    source_start_timecode:
        Timecode SMPTE non-drop-frame du debut du rush, ajoute en offset.
        Rediffuse tel quel dans le resultat (3.4 le persiste en
        ``video.source_start_timecode``, 3.5 l'inclut dans
        ``fingerprints.selection``).
    source_in_timecode, source_out_timecode:
        Bornes optionnelles et independantes de la fenetre extraite (story
        3.7), dans la **meme base de temps** que ``source_start_timecode``:
        le timecode SMPTE tel qu'affiche partout ailleurs dans le projet, et
        non un decalage relatif au debut du fichier. ``source_in_timecode``
        seul borne la fin au dernier index du rush, ``source_out_timecode``
        seul borne le debut a l'index 0, et l'absence des deux rend exactement
        la selection d'avant cette story. Les deux bornes sont **incluses**
        dans la fenetre. Rediffusees verbatim dans le resultat.
    source_duration_seconds:
        Duree du **flux video** (``streams[].duration``), optionnelle, en
        secondes (``int``, ``float`` ou ``Fraction`` — convertie en
        ``Fraction`` avant toute comparaison). Si fournie, active la garde de
        coherence a une frame pres. Ne participe jamais au calcul des indices.
    source_frame_count_is_exact:
        Booleen strict, jamais coerce. ``False`` quand l'appelant n'a qu'une
        estimation du cardinal: emet ``SOURCE_FRAME_COUNT_ESTIMATED`` et
        rediffuse le drapeau.

    Raises
    ------
    InvalidFrameRateError
        Cadence nulle, negative, non finie, de type invalide, de denominateur
        nul (``"0/0"`` de ffprobe), ou de cadence nominale superieure a
        ``MAX_SOURCE_FRAME_RATE``
        images/seconde (non representable en ``hh:mm:ss:ff``).
    EmptySourceError
        ``source_frame_count`` non entier ou inferieur a 1, ou
        ``source_frame_count_is_exact`` non booleen.
    UpsamplingNotSupportedError
        ``fps_target > fps_source``.
    InconsistentSourceDurationError
        Cardinal et duree divergents de plus d'une frame.
    InvalidStartTimecodeError
        ``source_start_timecode`` malforme, hors bornes ou drop-frame.
    InvalidBoundsError
        Borne malformee ou drop-frame, borne d'entree posterieure a la borne
        de sortie, ou borne de sortie au-dela du dernier index du rush.
    """
    fps_source_exact = _normalize_rate(fps_source, "source")
    fps_target_exact = _normalize_rate(fps_target, "cible")
    frame_count = _normalize_frame_count(source_frame_count)
    count_is_exact = _normalize_exactness_flag(source_frame_count_is_exact)

    if fps_target_exact > fps_source_exact:
        raise UpsamplingNotSupportedError(
            f"Sur-echantillonnage non supporte: cadence cible {fps_target_exact} "
            f"superieure a la cadence source {fps_source_exact}. Cadence cible "
            f"maximale admissible: {fps_source_exact} "
            f"(soit {float(fps_source_exact):g} images/seconde). Extraire plus de "
            "frames que la source n'en contient imposerait des doublons ou une "
            "interpolation, que ce noyau n'emet jamais"
        )

    if source_duration_seconds is not None:
        _check_duration_consistency(
            source_duration_seconds, frame_count, fps_source_exact
        )

    # Cadence nominale entiere du champ `ff`: la meme borne que celle que
    # `validate_timecode` applique (`ceil`), sinon les timecodes emis
    # seraient rejetes par la validation du projet lui-meme.
    nominal_fps = ceil(fps_source_exact)
    # Le champ `ff` de `hh:mm:ss:ff` ne porte que deux chiffres: au-dela de 100
    # images/seconde nominales, `_format_timecode` emet un `ff` a trois chiffres
    # que `validate_timecode` rejette par une `ValueError` **nue**, hors de la
    # hierarchie `FrameSelectionError` exigee par l'AC 13. Le defaut dependait en
    # outre des donnees, donc invisible a un test par echantillonnage: un rush a
    # 120 i/s passe vers 4 i/s (les indices retenus tombent sur des `ff` < 100)
    # et casse vers 7 i/s (indice 102). La garde est posee ici, avant toute
    # materialisation, pour que le refus soit deterministe et explique.
    if nominal_fps > MAX_SOURCE_FRAME_RATE:
        raise InvalidFrameRateError(
            f"Cadence source {fps_source_exact} hors perimetre: la cadence nominale "
            f"ceil({fps_source_exact}) vaut {nominal_fps} images/seconde, au-dela de "
            f"la limite de {MAX_SOURCE_FRAME_RATE} images/seconde retenue pour le "
            "MVP (ARB-11, decisions-2026-08-05.md). Les rushs a haute cadence "
            "(120 ou 240 i/s pour un ralenti) sont hors perimetre: les traiter "
            "suppose d'abord etendre la representation du timecode du projet, dont "
            "le champ frames de hh:mm:ss:ff ne porte que deux chiffres "
            "(codec_profiles.validate_timecode)"
        )
    offset_frames = _start_offset_frames(
        source_start_timecode, nominal_fps, fps_source_exact
    )

    # Fenetre d'extraction (story 3.7). Sans borne: `[0, frame_count - 1]`,
    # donc exactement le rush entier et exactement le calcul d'avant.
    in_index = (
        0
        if source_in_timecode is None
        else _bound_index(
            source_in_timecode,
            offset_frames,
            nominal_fps,
            fps_source_exact,
            label="source_in_timecode",
        )
    )
    out_index = (
        frame_count - 1
        if source_out_timecode is None
        else _bound_index(
            source_out_timecode,
            offset_frames,
            nominal_fps,
            fps_source_exact,
            label="source_out_timecode",
        )
    )
    # Les bornes sont validees contre le cardinal **reel** de la source, jamais
    # devinees: c'est pourquoi elles vivent ici et non dans une garde amont.
    #
    # Chaque borne hors du rush est diagnostiquee **pour elle-meme**. Avant la
    # revue du 2026-08-06, seule la borne de sortie l'etait: une `--in` seule
    # posee au-dela de la fin tombait dans la garde `in_index > out_index` et
    # s'y voyait reprocher une borne de sortie que l'operateur n'avait jamais
    # fournie, assortie d'une explication portant sur le cas exactement
    # inverse (une borne anterieure au debut).
    for valeur, index, etiquette in (
        (source_in_timecode, in_index, "source_in_timecode"),
        (source_out_timecode, out_index, "source_out_timecode"),
    ):
        if valeur is None or index <= frame_count - 1:
            continue
        cote = "d'entree" if etiquette == "source_in_timecode" else "de sortie"
        raise InvalidBoundsError(
            f"Borne {cote} hors du rush: {etiquette} {valeur!r} designe l'index "
            f"{index}, au-dela du dernier index valide {frame_count - 1}, dont "
            f"le timecode est "
            f"{_format_timecode(offset_frames + frame_count - 1, nominal_fps)}. "
            + _rush_timecode_span(
                offset_frames,
                frame_count,
                nominal_fps,
                source_start_timecode,
                count_is_exact=count_is_exact,
            )
            + _wraparound_hint(offset_frames)
        )
    if in_index > out_index:
        borne_entree = (
            source_in_timecode if source_in_timecode is not None else "absente"
        )
        borne_sortie = (
            source_out_timecode if source_out_timecode is not None else "absente"
        )
        raise InvalidBoundsError(
            f"Bornes d'extraction incoherentes: la borne d'entree "
            f"(source_in_timecode={borne_entree}, index {in_index}) est posterieure "
            f"a la borne de sortie (source_out_timecode={borne_sortie}, index "
            f"{out_index}). "
            + _rush_timecode_span(
                offset_frames,
                frame_count,
                nominal_fps,
                source_start_timecode,
                count_is_exact=count_is_exact,
            )
            + _wraparound_hint(offset_frames)
        )
    window_frame_count = out_index - in_index + 1

    # k >= 1 par la garde d'upsampling. N = ceil(fenetre / k), calcul exact.
    # Generalisation continue de la formule d'avant la story 3.7: sans borne,
    # `window_frame_count == frame_count` et le resultat est identique.
    step = fps_source_exact / fps_target_exact
    expected_frame_count = ceil(Fraction(window_frame_count) / step)

    # ARB-10 (`decisions-2026-08-05.md`): le plafond porte sur le **nombre
    # d'images** et non sur la duree du rush. C'est le bon invariant: c'est le
    # nombre d'images qui determine le cout disque, le nombre de planches a
    # imprimer et le temps de scan, pas la duree de la source. La garde est
    # posee **avant** de materialiser les frames, pour qu'un cardinal aberrant
    # ne fasse jamais travailler la machine avant d'echouer.
    if expected_frame_count > MAX_EXPECTED_FRAME_COUNT:
        # Le denominateur est le cardinal de la **fenetre**, jamais celui du
        # fichier: depuis la story 3.7, c'est la fenetre que le plafond mesure.
        # Diviser par `frame_count` conseillerait a un operateur ayant deja
        # borne son extrait une cadence jusqu'a dix fois trop basse.
        cadence_qui_rentre = (
            Fraction(MAX_EXPECTED_FRAME_COUNT)
            * fps_source_exact
            / Fraction(window_frame_count)
        )
        raise SelectionTooLargeError(
            f"Lot trop volumineux: {expected_frame_count} images seraient extraites, "
            f"au-dela du plafond de {MAX_EXPECTED_FRAME_COUNT} images par lot. Ce "
            "plafond porte sur le nombre d'images et non sur la duree du rush, "
            "parce que c'est lui qui determine le volume disque, le nombre de "
            "planches a imprimer et le temps de scan. Deux issues: viser une "
            f"cadence d'au plus {_rate_that_actually_fits(cadence_qui_rentre)} im/s "
            "pour cette "
            "plage, ou restreindre la plage extraite par les bornes de timecode "
            "--in et --out, qui laissent la cadence intacte sur un extrait plus "
            "court."
        )

    frames = []
    for output_rank in range(expected_frame_count):
        source_index = in_index + floor(step * output_rank)
        timecode = _format_timecode(offset_frames + source_index, nominal_fps)
        # Chaque timecode emis est valide contre la cadence SOURCE, jamais
        # contre la cadence cible (Piege 4).
        validate_timecode(timecode, fps_source_exact)
        frames.append(
            SelectedFrame(
                output_rank=output_rank,
                source_index=source_index,
                frame_timecode=timecode,
            )
        )

    last_index = frames[-1].source_index
    return FrameSelection(
        frames=tuple(frames),
        fps_source=fps_source_exact,
        fps_target=fps_target_exact,
        source_frame_count=frame_count,
        source_frame_count_is_exact=count_is_exact,
        expected_frame_count=expected_frame_count,
        source_tail_frames=frame_count - 1 - last_index,
        rounding_policy=ROUNDING_POLICY_ID,
        timecode_base=TIMECODE_BASE,
        timecode_base_fps=fps_source_exact,
        source_start_timecode=source_start_timecode,
        warnings=_collect_warnings(
            fps_source_exact, fps_target_exact, count_is_exact
        ),
        source_in_timecode=source_in_timecode,
        source_out_timecode=source_out_timecode,
    )
