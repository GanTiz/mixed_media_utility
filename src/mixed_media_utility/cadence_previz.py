"""Previsualisation d'un rush a plusieurs cadences reduites (story 3.6).

Perimetre
---------
Ce module est un **lecteur**, et rien d'autre: il decode un rush en memoire,
presente a leur echeance les frames que ``extract`` retiendrait, mesure
l'ecart au temps reel et rend un rapport chiffre. Il repond a une question
d'arbitrage precise -- « a quoi ressemble le mouvement de ce rush a 3, 5 ou
12,5 im/s ? » -- et il ne produit rien.

**Une previz n'autorise rien.** Ce module ne cree ni lot, ni entree de
manifest, ni consentement, ni etat de confirmation reutilisable, et ne
declenche aucune extraction. Il n'importe ni ``io.extraction_manifest``, ni
``io.project_layout``, ni la couche d'interaction de la story 3.3; il n'ecrit
`project.json` ni aucun autre fichier. Symetriquement il refuse une source
VFR et une cadence cible superieure a la cadence source **avec les memes
messages** que ``extract``, puisqu'il appelle les memes gardes: il est donc
aussi un pre-vol bon marche de l'extraction, jamais son autorisation.

**Rien n'est ecrit nulle part**, y compris sur interruption: aucun fichier
temporaire, aucune image materialisee, aucun encodage. Le chemin nominal
decode et affiche. ``Ctrl+C`` libere la capture et la fenetre dans un
``finally``, emet un rapport **partiel** marque comme tel, et ne laisse aucune
trace Python.

Frontiere Epic 3 / Epic 7
-------------------------
Le choix de technologie d'interface de l'application finale appartient a
l'Epic 7 et n'est fixe nulle part a ce jour. Ce module ouvre une fenetre par
``cv2.imshow``, c'est-a-dire par une bibliotheque **deja presente** et deja
importee par cinq fichiers du depot: ce n'est pas un choix d'architecture
d'interface, c'est l'affichage minimal disponible. Critere de faute,
verifiable en revue: **si cette story ajoute une dependance a
``requirements.txt``, elle a preempte l'Epic 7.**

Corollaire assume: ``cv2.imshow`` ne fait pas une interface utilisateur. Pas
de menu, pas de barre de progression cliquable, pas de scrubbing. Un
affichage, une incrustation textuelle minimale, quelques touches. Le jour ou
l'Epic 7 choisit une technologie, il reprend le noyau de cadencement et de
mesure -- pur, sans affichage, teste -- et remplace le seul ``sink``.

Contrat de jonction avec 3.1 et 3.2
-----------------------------------
**La sequence presentee est exactement celle que ``extract`` retiendrait.**
Les indices viennent litteralement de ``frame_selection.select_source_frames``,
appele avec les memes entrees que ``extract``, obtenues par les memes
fonctions: ``video_metadata.probe_media`` -> ``extraction.qualify_source`` ->
``extraction.resolve_source_frame_count``. Aucune regle d'echantillonnage,
aucun arrondi de cadence, aucun cardinal de frames n'est calcule ici.

Le cardinal source ne vient **jamais** de ``cv2.CAP_PROP_FRAME_COUNT``: cette
valeur est derivee, souvent estimee depuis la duree et la cadence, et diverge
du comptage exact selon le conteneur. L'utiliser produirait une selection
differente de celle de ``extract`` -- la faute exacte que cette story existe
pour empecher.

``extraction.check_fps_form_consistency`` n'est **pas** appelee: c'est une
garde de nommage, or la previz ne nomme aucun fichier.

Decodage et cadencement
-----------------------
Decodage **sequentiel** par ``cv2.VideoCapture.read()``, rang compte a partir
de 0. ``cv2.CAP_PROP_POS_FRAMES`` est **proscrit**: le positionnement par
index sur un flux a images bidirectionnelles atterrit couramment sur une image
cle voisine, en silence. Pour rejouer ou revenir en arriere, la capture est
**rouverte**, jamais deplacee.

Chaque frame de rang ``r`` a un instant de presentation theorique
``t_theo(r) = source_index(r) / fps_source``, exprime dans la base de temps
**source** (ARB-2): le rush previsualise garde donc la duree qu'il a a la
lecture normale, et la cadence cible apparait comme une **saccade**, pas comme
un ralenti. Les echeances sont **absolues** depuis l'origine de la lecture et
relevees sur ``time.monotonic()``; ``cv2.waitKey`` n'est pas un ordonnanceur,
son delai ne sert qu'a rendre la main a l'interface.

L'ecart au temps reel est **mesure et rapporte, jamais subi**: le rapport
final porte le retard maximal, median et p95, la derive finale, la cadence
effective et le taux de frames en retard. Une frame est en retard au-dela de
``LATE_FRAME_TOLERANCE_S`` (20 ms, une image a 50 Hz), seuil **independant de
la cadence cible** pour que le critere ne se relache pas quand la cadence
baisse.

En cas de retard, **aucune frame de la selection n'est sautee en silence**.
Mode par defaut ``report``: toutes les frames retenues sont presentees, la
lecture dure plus longtemps que la duree nominale, l'ecart est chiffre.
Mode explicite ``skip``: les frames dont l'echeance est deja depassee peuvent
etre omises pour preserver le tempo percu, et le compte est chiffre dans le
rapport final, avec le code ``FRAMES_SKIPPED`` et la mention explicite que la
sequence vue n'etait pas la selection complete. Dans les deux cas, la session
reste un succes: un ecart mesure et rapporte n'est pas un echec.

Convention d'ecriture: messages en francais **sans accents**, y compris dans
l'incrustation a l'ecran, comme ``extraction.py`` et ``frame_selection.py``.
"""

from __future__ import annotations

import logging
import os
import statistics
import sys
import time
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import cv2

from . import extraction, video_metadata
from .codec_profiles import exact_frame_rate
from .extraction import ExtractionInputError
from .frame_selection import FrameSelection, select_source_frames
from .numeric_guards import is_strict_number

__all__ = [
    "LATE_FRAME_TOLERANCE_S",
    "LATE_FRAME_RATE_THRESHOLD",
    "FINAL_DRIFT_RATIO_THRESHOLD",
    "DEFAULT_PREVIEW_HEIGHT",
    "DEFAULT_MEMORY_BUDGET_MB",
    "ON_LATE_REPORT",
    "ON_LATE_SKIP",
    "ON_LATE_POLICIES",
    "REALTIME_NOT_HELD",
    "FRAMES_SKIPPED",
    "DECODE_TRUNCATED",
    "DISPLAY_UNAVAILABLE",
    "CACHE_EVICTED",
    "PLAYBACK_WARNING_CODES",
    "KEY_NEXT",
    "KEY_PREVIOUS",
    "KEY_REPLAY",
    "KEY_LOOP",
    "KEY_QUIT",
    "DisplayUnavailableError",
    "ScheduledFrame",
    "FrameObservation",
    "PlaybackReport",
    "PresentedFrame",
    "PassOutcome",
    "PrevizSession",
    "PrevizResult",
    "FrameCache",
    "SequentialFrameReader",
    "NullSink",
    "RecordingSink",
    "CvWindowSink",
    "build_schedule",
    "restrict_schedule",
    "should_present",
    "build_playback_report",
    "format_report_lines",
    "OVERLAY_RATE_TOLERANCE",
    "OVERLAY_LOOP_ON",
    "OVERLAY_LOOP_OFF",
    "OverlayText",
    "compute_current_rate",
    "format_overlay",
    "resize_to_height",
    "ensure_display_available",
    "prepare_previz",
    "play_cadences",
]


# --------------------------------------------------------------------------
# Constantes de contrat
# --------------------------------------------------------------------------

#: Tolerance de retard par frame presentee, en secondes. 20 ms, soit une image
#: a 50 Hz. Volontairement **independante de la cadence cible**: un seuil
#: proportionnel se relacherait mecaniquement a 3 im/s, or c'est precisement la
#: que la saccade est la plus lisible et le rendu le plus sensible.
LATE_FRAME_TOLERANCE_S = 0.020

#: Taux maximal de frames en retard au-dela duquel le temps reel n'est plus
#: declare tenu.
LATE_FRAME_RATE_THRESHOLD = 0.01

#: Derive finale maximale toleree, en fraction de la duree nominale.
FINAL_DRIFT_RATIO_THRESHOLD = 0.02

#: Hauteur d'affichage par defaut. Reglage **pose avant la lecture**, jamais
#: une degradation en vol: une resolution qui change en cours de lecture
#: modifierait la perception du mouvement au milieu de l'arbitrage.
#: Mesure du depot: une frame BGR pese 6,2 Mo en 1920x1080, 1,6 Mo en 960x540
#: et 0,4 Mo en 480x270.
DEFAULT_PREVIEW_HEIGHT = 540

#: Budget memoire par defaut du cache de frames decodees, en mebioctets.
#:
#: **Ce que le cache fait reellement**, mesure a la revue du 2026-08-05: il ne
#: fait economiser **aucun** decodage lorsqu'on passe d'une cadence a l'autre
#: (737 frames decodees avec cache, 737 sans), parce que deux cadences
#: differentes ne retiennent presque aucune frame source commune. Il ne sert
#: qu'au **rejeu a l'identique** de la meme cadence, ou il evite effectivement
#: de tout redecoder.
#:
#: Le defaut est donc ramene de 512 a 128 Mio (ARB, 2026-08-05, point 10):
#: reserver un demi-gigaoctet pour un gain qui n'existe pas sur l'usage annonce
#: -- comparer plusieurs cadences -- est un mauvais echange. A 960x540
#: (1,56 Mio par frame), 128 Mio retiennent environ 82 frames, ce qui couvre le
#: rejeu d'une passe courte. Le cache reste une **optimisation**, jamais une
#: condition de justesse: un defaut de cache redecode, il ne fausse rien.
DEFAULT_MEMORY_BUDGET_MB = 128

#: Politique de retard: presenter toutes les frames retenues et chiffrer
#: l'ecart (defaut), ou omettre les frames deja en retard pour preserver le
#: tempo percu (sur demande explicite seulement).
ON_LATE_REPORT = "report"
ON_LATE_SKIP = "skip"
ON_LATE_POLICIES = (ON_LATE_REPORT, ON_LATE_SKIP)

#: Vocabulaire **ferme** de codes d'avertissement, ASCII et stables.
REALTIME_NOT_HELD = "REALTIME_NOT_HELD"
FRAMES_SKIPPED = "FRAMES_SKIPPED"
DECODE_TRUNCATED = "DECODE_TRUNCATED"
DISPLAY_UNAVAILABLE = "DISPLAY_UNAVAILABLE"
CACHE_EVICTED = "CACHE_EVICTED"

#: Ordre canonique des codes: ``PlaybackReport.warnings`` en est toujours un
#: sous-ensemble, dans cet ordre, sans doublon.
PLAYBACK_WARNING_CODES = (
    REALTIME_NOT_HELD,
    FRAMES_SKIPPED,
    DECODE_TRUNCATED,
    DISPLAY_UNAVAILABLE,
    CACHE_EVICTED,
)

#: Touches de navigation, en codes ASCII (ce que rend ``cv2.waitKey`` masque a
#: 8 bits). Les fleches ne sont pas portables d'un backend a l'autre: les
#: lettres le sont.
KEY_NEXT = ord("n")
KEY_PREVIOUS = ord("p")
KEY_REPLAY = ord("r")
#: Bascule de la **lecture en boucle** (story 11.4, lot K2). Elle est nee d'un
#: mensonge d'interface trouve par Egan en testant le produit a la main le
#: 2026-08-30: l'atelier Extraction annoncait `L boucle` dans sa legende de
#: fenetre alors qu'aucune touche de boucle n'existait ici, et qu'aucune notion
#: de boucle n'existait dans la previz. `L` ne faisait donc pas « rien » au
#: sens strict -- comme toute touche non liee, elle tombait dans la branche par
#: defaut de `play_cadences` et faisait avancer d'une cadence, exactement comme
#: `n`. Une touche qui fait autre chose que ce qu'elle promet est pire qu'une
#: touche morte.
#:
#: **La lettre est NUE, jamais `maj+lettre`** (consigne d'Egan du 2026-08-30):
#: l'affichage se fait en majuscule pour la lisibilite de la legende, la touche
#: liee est la minuscule. `ord("L")` (76) n'est deliberement PAS liee, et ce
#: n'est pas un oubli: lier les deux ferait de la seule touche de l'interface
#: sensible a `Maj` un cas particulier invisible, et surtout `cv2.waitKey`
#: masque a 8 bits sans normaliser la casse -- deux codes, deux entrees, deux
#: chemins a mesurer pour un gain nul. `L` majuscule conserve donc le
#: comportement qu'elle a toujours eu: elle passe a la cadence suivante, comme
#: toute touche non liee.
KEY_LOOP = ord("l")
KEY_QUIT = ord("q")
_KEY_ESCAPE = 27

_BYTES_PER_MB = 1024 * 1024


class DisplayUnavailableError(RuntimeError):
    """Aucun affichage exploitable. Mappe vers le code de sortie 2.

    Prerequis externe absent, au meme titre qu'un binaire manquant: ce n'est ni
    une erreur d'entree (code 1) ni un echec de traitement. Detectee **en
    amont**, jamais laissee remonter en ``cv2.error`` illisible.

    Le refus se dit en **deux morceaux** (``EPIC11-ARB-73``, story 11.4):

    * ``motif`` -- ce qui ne va pas, et rien d'autre. Il ne nomme **aucune
      option de ligne de commande**;
    * ``conseil`` -- ce qu'on peut faire, formule pour la CLI, donc en nommant
      ``--no-display``.

    ``str(exception)`` reste la concatenation des deux, inchangee au caractere
    pres: la CLI imprime exactement ce qu'elle imprimait. La separation existe
    pour l'autre appelant -- la TUI, qui **n'expose pas** ``--no-display``
    (``EPIC11-ARB-41``) et ne peut donc ni rendre ce message verbatim, ni le
    tronquer sans en produire une seconde redaction, qui divergerait.

    Une construction a un seul argument reste valide: le message entier est
    alors le motif, et le conseil est vide.
    """

    def __init__(self, motif: str, conseil: str = "") -> None:
        super().__init__(f"{motif} {conseil}" if conseil else motif)
        #: La phrase de refus, sans conseil d'option. Lue par la TUI.
        self.motif = motif
        #: Le conseil de la CLI, qui nomme l'option. Lu par personne d'autre.
        self.conseil = conseil


# --------------------------------------------------------------------------
# Noyau pur: echeancier
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ScheduledFrame:
    """Une frame retenue et son instant de presentation theorique.

    ``source_index`` et ``output_rank`` viennent litteralement de la story 3.2
    et ne sont jamais recalcules ici. ``t_theo_s`` est exprime dans la base de
    temps **source**.
    """

    output_rank: int
    source_index: int
    frame_timecode: str
    t_theo_s: float


def build_schedule(
    selection: FrameSelection, fps_source: Fraction | None = None
) -> tuple[ScheduledFrame, ...]:
    """Rendre l'echeancier de presentation d'une selection. Fonction **pure**.

    ``t_theo(r) = source_index(r) / fps_source``, calcule en ``Fraction`` puis
    converti une seule fois en ``float`` a la frontiere: aucun flottant
    n'arbitre, et l'accumulation d'erreur d'un cumul d'intervalles est exclue
    par construction (chaque instant est calcule depuis l'origine).

    La base de temps est celle de la **source**, pas celle de la cadence
    cible: c'est ce qui donne au rush previsualise la meme duree qu'a la
    lecture normale et fait apparaitre la cadence cible comme une saccade et
    non comme un ralenti (ARB-2).
    """
    rate = Fraction(selection.fps_source if fps_source is None else fps_source)
    if rate <= 0:
        raise ExtractionInputError(
            f"Cadence source invalide pour l'echeancier: {rate!r}. Attendu une "
            "cadence strictement positive."
        )
    return tuple(
        ScheduledFrame(
            output_rank=frame.output_rank,
            source_index=frame.source_index,
            frame_timecode=frame.frame_timecode,
            t_theo_s=float(Fraction(frame.source_index) / rate),
        )
        for frame in selection
    )


def restrict_schedule(
    schedule: Sequence[ScheduledFrame],
    *,
    start_seconds: float | None = None,
    duration_seconds: float | None = None,
) -> tuple[ScheduledFrame, ...]:
    """Restreindre l'echeancier a une fenetre temporelle. Fonction **pure**.

    Semantique retenue (question ouverte 1 de la story 3.6, recommandation
    suivie): cette fonction ne touche **jamais** a la selection, elle ne fait
    que restreindre ce qui en est **presente**. Les ``source_index`` restent
    donc rigoureusement ceux que ``extract`` retiendrait -- toute autre
    semantique (selectionner sur la plage affichee) montrerait a Egan des
    frames qu'il n'obtiendra jamais et violerait l'AC 2 de la story 3.6.

    Depuis la story 3.7, la selection qu'elle recoit peut elle-meme etre
    bornee par ``--in`` / ``--out``, auquel cas elle ne porte plus sur le rush
    entier. Cela ne change rien ici, et c'est tout l'interet de la separation:
    ``--in`` / ``--out`` decident **ce qui est retenu** (dans le noyau 3.2),
    ``--start`` / ``--duration`` decident **ce qui est joue** parmi les
    retenues (ici). Cette docstring affirmait encore « la selection est
    calculee sur le rush entier », ce que la story 3.7 avait rendu faux
    (revue du 2026-08-06).

    Les ``t_theo_s`` sont rebases sur la premiere frame retenue, pour que la
    lecture demarre immediatement et non apres ``start_seconds`` d'ecran fixe.
    Le rebasement ne touche **que** l'instant de presentation.
    """
    if start_seconds is not None and start_seconds < 0:
        raise ExtractionInputError(
            f"Parametre --start invalide: {start_seconds!r}. Attendu un nombre de "
            "secondes positif ou nul."
        )
    if duration_seconds is not None and duration_seconds <= 0:
        raise ExtractionInputError(
            f"Parametre --duration invalide: {duration_seconds!r}. Attendu un nombre "
            "de secondes strictement positif."
        )

    start = 0.0 if start_seconds is None else float(start_seconds)
    end = None if duration_seconds is None else start + float(duration_seconds)

    retained = [
        frame
        for frame in schedule
        if frame.t_theo_s >= start and (end is None or frame.t_theo_s < end)
    ]
    if not retained:
        return ()
    offset = retained[0].t_theo_s
    return tuple(
        ScheduledFrame(
            output_rank=frame.output_rank,
            source_index=frame.source_index,
            frame_timecode=frame.frame_timecode,
            t_theo_s=frame.t_theo_s - offset,
        )
        for frame in retained
    )


def should_present(
    *,
    t_theo_s: float,
    elapsed_s: float,
    on_late: str = ON_LATE_REPORT,
    tolerance_s: float = LATE_FRAME_TOLERANCE_S,
) -> bool:
    """Decider si une frame doit etre presentee ou omise. Fonction **pure**.

    En mode ``report`` (defaut) la reponse est **toujours** ``True``: omettre
    une frame retenue sans le dire ferait voir une sequence differente de celle
    qu'on croit arbitrer. En mode ``skip``, une frame dont l'echeance est
    depassee de plus de ``tolerance_s`` est omise, et ce choix explicite est
    compte, affiche pendant la lecture et rappele dans le rapport.
    """
    if on_late not in ON_LATE_POLICIES:
        raise ExtractionInputError(
            f"Politique de retard inconnue: {on_late!r}. Valeurs admises: "
            f"{', '.join(ON_LATE_POLICIES)}."
        )
    if on_late == ON_LATE_REPORT:
        return True
    return (elapsed_s - t_theo_s) <= tolerance_s


# --------------------------------------------------------------------------
# Noyau pur: mesure du temps reel
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class FrameObservation:
    """Une frame effectivement remise au ``sink``, et quand elle l'a ete."""

    output_rank: int
    source_index: int
    t_theo_s: float
    t_real_s: float

    @property
    def lateness_s(self) -> float:
        """Retard contre l'echeance **absolue**, jamais contre la frame precedente.

        Un ecart mesure d'intervalle a intervalle masquerait une derive lente
        qui, sur vingt secondes, decale la fin de plusieurs images.
        """
        return self.t_real_s - self.t_theo_s


@dataclass(frozen=True)
class PlaybackReport:
    """Rapport chiffre d'une passe de lecture.

    Ce rapport n'est **pas** persiste, ne devient pas un artefact du projet et
    ne vaut aucune autorisation. Il est affiche, point.
    """

    fps_target: float
    frames_presentees: int
    frames_attendues: int
    frames_omises: int
    retard_max_s: float
    retard_median_s: float
    retard_p95_s: float
    derive_finale_s: float
    duree_nominale_s: float
    duree_reelle_s: float
    amorcage_s: float
    cadence_effective: float | None
    taux_frames_en_retard: float
    temps_reel_tenu: bool
    partiel: bool
    warnings: tuple[str, ...]


def _percentile_95(values: Sequence[float]) -> float:
    """p95 par rang le plus proche (``ceil(0.95 * n)``), sans interpolation.

    Pas d'interpolation: sur une serie de retards, une valeur interpolee entre
    deux mesures n'a jamais ete observee, et l'objet du rapport est de dire ce
    qui s'est passe.
    """
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, -(-95 * len(ordered) // 100))
    return ordered[rank - 1]


def build_playback_report(
    observations: Sequence[FrameObservation],
    *,
    fps_target: float,
    frames_attendues: int,
    duree_nominale_s: float,
    frames_omises: int = 0,
    partiel: bool = False,
    extra_warnings: Sequence[str] = (),
    amorcage_s: float = 0.0,
    late_tolerance_s: float = LATE_FRAME_TOLERANCE_S,
) -> PlaybackReport:
    """Agreger les instants observes en un rapport. Fonction **pure**.

    Aucune horloge, aucun affichage, aucune I/O: la fonction ne voit que la
    liste des instants deja releves, ce qui la rend testable sur des series
    fabriquees a la main.

    Verdict de session: le temps reel est declare **tenu** si et seulement si
    ``taux_frames_en_retard <= LATE_FRAME_RATE_THRESHOLD`` **et**
    ``abs(derive_finale_s) <= FINAL_DRIFT_RATIO_THRESHOLD * duree_nominale_s``.
    Quand la duree nominale est nulle (une seule frame retenue), le second
    critere se replie sur la tolerance par frame, faute de quoi le moindre
    retard rendrait le verdict impossible a satisfaire.
    """
    lateness = [observation.lateness_s for observation in observations]
    presentees = len(observations)

    if lateness:
        retard_max = max(lateness)
        retard_median = float(statistics.median(lateness))
        retard_p95 = _percentile_95(lateness)
        late_count = sum(1 for value in lateness if value > late_tolerance_s)
        # Une frame omise par `--on-late skip` l'a ete **parce que** son
        # echeance etait deja depassee: c'est une preuve directe de non-tenue,
        # pas une absence de mesure. Ne rapporter le retard qu'aux seules
        # frames presentees laissait le mode `skip` effacer le constat qu'il
        # est cense declencher: sur un rush 4K decode trop lentement, une frame
        # presentee sur cent-cinquante et cent-quarante-neuf omises donnaient
        # `temps reel : tenu` sans `REALTIME_NOT_HELD` (revue du 2026-08-05).
        # En mode `report`, `frames_omises` vaut zero et rien ne change.
        juges = presentees + int(frames_omises)
        taux = (late_count + int(frames_omises)) / juges if juges else 0.0
        derive = lateness[-1]
        duree_reelle = observations[-1].t_real_s
    else:
        retard_max = retard_median = retard_p95 = 0.0
        taux = 0.0
        derive = 0.0
        duree_reelle = 0.0

    drift_budget = FINAL_DRIFT_RATIO_THRESHOLD * duree_nominale_s
    if drift_budget <= 0:
        drift_budget = late_tolerance_s
    tenu = (
        taux <= LATE_FRAME_RATE_THRESHOLD
        and abs(derive) <= drift_budget
        and (presentees > 0 or frames_attendues == 0)
    )

    emitted = set(extra_warnings)
    if not tenu:
        emitted.add(REALTIME_NOT_HELD)
    if frames_omises > 0:
        emitted.add(FRAMES_SKIPPED)

    return PlaybackReport(
        fps_target=float(fps_target),
        frames_presentees=presentees,
        frames_attendues=int(frames_attendues),
        frames_omises=int(frames_omises),
        retard_max_s=retard_max,
        retard_median_s=retard_median,
        retard_p95_s=retard_p95,
        derive_finale_s=derive,
        duree_nominale_s=float(duree_nominale_s),
        duree_reelle_s=duree_reelle,
        amorcage_s=float(amorcage_s),
        # Cadence mesuree = nombre d'INTERVALLES sur la duree, pas nombre de
        # frames sur la duree: n frames delimitent n-1 intervalles, et compter
        # les frames surestime systematiquement la cadence (30 frames en 9,6 s
        # donnent 3,01 im/s, pas 3,11). Indefinie sous deux frames.
        # `None`, et non `0.0`: sous deux frames la grandeur n'est pas
        # definie, et l'imprimer a zero la presenterait comme une mesure
        # (revue du 2026-08-05).
        cadence_effective=(
            (presentees - 1) / duree_reelle
            if presentees >= 2 and duree_reelle > 0
            else None
        ),
        taux_frames_en_retard=taux,
        temps_reel_tenu=tenu,
        partiel=bool(partiel),
        warnings=tuple(code for code in PLAYBACK_WARNING_CODES if code in emitted),
    )


def format_report_lines(report: PlaybackReport) -> tuple[str, ...]:
    """Rendre le rapport en lignes de texte ASCII, sans accents. **Pure**."""
    lines = [
        f"Cadence {report.fps_target:g} im/s"
        + (" -- LECTURE PARTIELLE (session interrompue)" if report.partiel else ""),
        f"  frames presentees   : {report.frames_presentees} / "
        f"{report.frames_attendues} attendues",
        f"  frames omises       : {report.frames_omises}",
        f"  retard max / median / p95 : {report.retard_max_s * 1000:.1f} / "
        f"{report.retard_median_s * 1000:.1f} / {report.retard_p95_s * 1000:.1f} ms",
        f"  derive finale       : {report.derive_finale_s * 1000:.1f} ms "
        f"(duree nominale {report.duree_nominale_s:.3f} s, "
        f"reelle {report.duree_reelle_s:.3f} s)",
        f"  amorcage            : {report.amorcage_s * 1000:.1f} ms "
        "(decodage jusqu'a la premiere frame presentee, hors cadencement)",
        "  cadence effective   : "
        + (
            "indefinie (moins de deux frames presentees)"
            if report.cadence_effective is None
            else f"{report.cadence_effective:.3f} im/s"
        ),
        f"  frames en retard    : {report.taux_frames_en_retard * 100:.2f} % "
        f"(seuil {LATE_FRAME_TOLERANCE_S * 1000:.0f} ms par frame)",
        f"  temps reel          : {'tenu' if report.temps_reel_tenu else 'NON TENU'}",
    ]
    if report.warnings:
        lines.append(f"  codes               : {', '.join(report.warnings)}")
    if FRAMES_SKIPPED in report.warnings:
        lines.append(
            "  ATTENTION: la sequence vue n'etait PAS la selection complete "
            f"({report.frames_omises} frame(s) omise(s) par --on-late skip)."
        )
    return tuple(lines)


# --------------------------------------------------------------------------
# Presentation
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PresentedFrame:
    """Ce qui accompagne une image remise au ``sink``."""

    fps_target: float
    output_rank: int
    window_position: int
    frames_attendues: int
    source_index: int
    source_frame_count: int
    lot_total_frames: int
    frame_timecode: str
    t_theo_s: float
    t_real_s: float
    frames_omises: int
    #: Vrai quand la lecture en boucle est armee AU MOMENT de cette image.
    #: L'etat voyage avec l'image plutot que d'etre lu quelque part par le
    #: rendu: l'incrustation reste une **fonction pure** de ce qu'on lui remet,
    #: et le temoin ne peut donc pas se desynchroniser de la frame affichee.
    #:
    #: Le defaut `False` reproduit l'etat anterieur pour toute construction a
    #: la main: une previz sans boucle est exactement la previz d'avant.
    loop_active: bool = False

    @property
    def lateness_s(self) -> float:
        return self.t_real_s - self.t_theo_s


#: Marge relative avant de declarer la cadence de lecture en dessous de la
#: cible. Sans elle, une cadence tenue a la limite exacte ferait clignoter
#: la couleur au gre du bruit de l'horloge sur quelques millisecondes.
OVERLAY_RATE_TOLERANCE = 0.02  # 2 %

#: Les deux etats du temoin de boucle, ASCII et sans accent comme tout le reste
#: de l'incrustation. **Les deux existent**, et c'est le point: une bascule sans
#: temoin est un etat cache, et c'est nommement ce qu'Egan a demande le
#: 2026-08-30 en meme temps que la fonction elle-meme.
#:
#: La casse et la longueur ne sont pas un gout. Les deux libelles sont mesures
#: a `getTextSize` avec la police de `CvWindowSink` (HERSHEY_SIMPLEX, echelle
#: 0,7): 90 px et 92 px. Le budget disponible en bout de ligne sur la source la
#: plus etroite du depot -- un portrait 9:16 rendu a `DEFAULT_PREVIEW_HEIGHT`,
#: soit 304 px de large -- est de 98 px. `boucle ON` (94) passait, `boucle OFF`
#: (102) sortait du champ, c'est-a-dire disparaissait EN SILENCE, exactement le
#: defaut que la revue du 2026-08-05 avait deja paye sur le groupe de droite.
#: Les deux formes retenues tiennent, et a 2 px l'une de l'autre: la fleche ne
#: se deplace pas quand on bascule.
OVERLAY_LOOP_ON = "boucle on"
OVERLAY_LOOP_OFF = "boucle off"


def compute_current_rate(window_position: int, t_real_s: float) -> float | None:
    """Cadence de lecture moyenne depuis le debut de la passe. Fonction **pure**.

    Moyenne **cumulee** sur la duree ecoulee, jamais instantanee frame a
    frame: une mesure d'intervalle a intervalle serait dominee par le bruit
    de l'horloge sur un pas de quelques millisecondes et clignoterait sans
    rien dire de la tenue reelle de la cadence.

    Compte des **intervalles**, jamais des frames: ``t_real_s`` est mesure
    depuis la presentation de la **premiere** frame, donc ``n + 1`` frames
    couvrent ``n`` intervalles. Diviser le nombre de frames par cette duree
    surestime systematiquement la cadence, et massivement au demarrage: sur
    une lecture parfaitement tenue a 3 im/s, la premiere version de cette
    fonction affichait ``6.0/3`` a la deuxieme frame, ``4.5/3`` a la
    troisieme, et ne s'approchait de 3 qu'asymptotiquement -- une lecture
    saine paraissait donc constamment en avance, et la couleur de tenue
    restait verte meme sur une passe reellement non tenue (revue du
    2026-08-05). C'est la faute que la decision 8 de cette story condamne
    nommement, et que `build_playback_report` evite deja en raisonnant sur
    les retards.

    Avant toute mesure exploitable -- la toute premiere frame de la passe, ou
    aucun intervalle n'est encore ecoule -- retourne ``None``: il n'y a rien a
    juger, et surtout rien a afficher.
    """
    if window_position < 1 or t_real_s <= 0:
        return None
    return window_position / t_real_s


@dataclass(frozen=True)
class OverlayText:
    """Contenu textuel de l'incrustation, en une seule ligne. Fonction **pure**,
    sans aucune dependance a cv2.

    Trois zones distinctes pour permettre au rendu de colorer la zone de
    cadence independamment du reste de la ligne, sans reanalyser du texte.
    """

    left: str
    right: str
    rate: str
    rate_on_target: bool
    #: Le temoin de boucle, toujours renseigne -- jamais vide, jamais absent.
    #: Un temoin qui disparait a l'etat « pas de boucle » ne distingue pas
    #: « boucle coupee » de « le temoin n'a pas ete dessine ».
    loop: str = OVERLAY_LOOP_OFF


def format_overlay(presentation: PresentedFrame) -> OverlayText:
    """Composer l'incrustation d'une image. Fonction **pure**.

    Le timecode affiche est ``frame_timecode`` tel que rendu par la story 3.2,
    dans la base de temps **source**. Il n'est jamais revalide contre la
    cadence cible: ``validate_timecode(tc, fps_target)`` leve des que
    ``ff >= ceil(fps_target)``, ce qui arrive des la premiere seconde a
    3 im/s.

    Deux echelles distinctes, jamais melangees: ``idx X/Y`` est la position
    de l'image dans le rush source entier (``source_index`` sur
    ``source_frame_count``, base zero -- convention ``n`` de ffmpeg, deja
    etablie dans tout le module) ; le groupe a droite de la fleche est le
    rang de cette image dans le lot que ``extract`` produirait (``output_rank``
    sur ``lot_total_frames``, affiche en base un pour un lecteur humain). Avec
    ``--start``, les deux different.
    """
    # Compte les images qui ont **reellement atteint l'ecran**, pas les
    # echeances du programme: en mode `--on-late skip`, `window_position`
    # avance aussi sur les images omises, si bien que l'ecran annoncait
    # `5/5 im/s` pendant que quatre images sur dix seulement etaient montrees.
    # L'incrustation mesurait le programme, pas la lecture (revue du
    # 2026-08-05).
    presentees = presentation.window_position - presentation.frames_omises
    rate = compute_current_rate(presentees, presentation.t_real_s)
    # Deux conditions, et non une seule. La cadence affichee est une moyenne
    # **cumulee**: elle lisse les a-coups, donc elle pouvait rester au vert sur
    # une passe que le rapport declarait NON TENUE (retard maximal de 113 ms
    # sur un rush 4K). L'ecran est ce qui arbitre; il ne peut pas dire le
    # contraire du rapport. Le retard courant est donc juge avec la **meme**
    # tolerance que `build_playback_report`.
    rate_on_target = (
        True
        if rate is None
        else (
            rate >= presentation.fps_target * (1 - OVERLAY_RATE_TOLERANCE)
            and presentation.lateness_s <= LATE_FRAME_TOLERANCE_S
        )
    )
    # Arrondie a 1 decimale: la cadence mesuree est une moyenne cumulee, sa
    # sixieme decimale (rendue par `:g` sans arrondi prealable) n'apporte
    # aucune information et allonge la ligne au point de la pousser hors
    # champ sur une source etroite.
    #
    # Tant qu'aucun intervalle n'est ecoule, la place est tenue par un tiret et
    # non par la cadence cible: afficher `3/3` sur la premiere image
    # presenterait comme une mesure ce qui n'en est pas une, ce que ce projet
    # s'interdit partout ailleurs (revue du 2026-08-05).
    rate_display = "-" if rate is None else f"{round(rate, 1):g}"
    return OverlayText(
        left=(
            f"{presentation.frame_timecode}  idx {presentation.source_index}/"
            f"{presentation.source_frame_count}"
        ),
        right=f"{presentation.output_rank + 1}/{presentation.lot_total_frames}",
        rate=f"{rate_display}/{presentation.fps_target:g} im/s",
        rate_on_target=rate_on_target,
        # Le temoin est LU sur l'image remise, jamais devine: c'est ce qui
        # rend l'incrustation incapable d'annoncer une boucle que la lecture
        # ne fait pas, et reciproquement.
        loop=OVERLAY_LOOP_ON if presentation.loop_active else OVERLAY_LOOP_OFF,
    )


class NullSink:
    """Sink sans affichage: le chemin de ``--no-display``.

    Il cadence reellement (il dort jusqu'a l'echeance) mais ne montre rien:
    c'est le chemin qui rend la mesure du temps reel observable en integration
    continue, sans ecran.
    """

    interactive = False

    def __init__(self, *, sleeper: Callable[[float], Any] = time.sleep) -> None:
        self._sleeper = sleeper
        self.presented: list[PresentedFrame] = []

    def present(self, image: Any, presentation: PresentedFrame) -> None:
        self.presented.append(presentation)

    def wait(self, seconds: float) -> int | None:
        if seconds > 0:
            self._sleeper(seconds)
        return None

    def poll_key(self) -> int | None:
        return None

    def wait_for_key(self) -> int | None:
        return None

    def close(self) -> None:
        return None


class RecordingSink:
    """Sink de test: enregistre chaque frame presentee et rejoue des touches.

    Il rend la totalite de l'echeancier, des metriques, des codes et de la
    navigation verifiable de facon deterministe, sans le moindre pixel.
    """

    interactive = True

    def __init__(
        self,
        *,
        sleeper: Callable[[float], Any] = lambda seconds: None,
        keys: Sequence[int] = (),
        delays: Mapping[int, float] | None = None,
    ) -> None:
        self._sleeper = sleeper
        self._keys = list(keys)
        self._delays = dict(delays or {})
        self.presented: list[PresentedFrame] = []
        self.images: list[Any] = []
        self.closed = False

    def present(self, image: Any, presentation: PresentedFrame) -> None:
        self.presented.append(presentation)
        self.images.append(image)
        delay = self._delays.get(presentation.output_rank)
        if delay:
            self._sleeper(delay)

    def wait(self, seconds: float) -> int | None:
        if seconds > 0:
            self._sleeper(seconds)
        return None

    def poll_key(self) -> int | None:
        return None

    def wait_for_key(self) -> int | None:
        if self._keys:
            return self._keys.pop(0)
        return KEY_QUIT

    def close(self) -> None:
        self.closed = True

    @property
    def source_indices(self) -> tuple[int, ...]:
        return tuple(item.source_index for item in self.presented)


class _WindowClosedByUser(Exception):
    """L'utilisateur a ferme la fenetre: la passe s'arrete comme sur `q`.

    Interne au module. Elle ne remonte jamais a l'appelant: `_play_one_pass`
    la traite comme une sortie volontaire et rend un rapport **partiel**, de
    facon que fermer la fenetre ne fasse pas perdre le rapport, qui est le
    seul livrable de la commande (revue du 2026-08-05).
    """


class CvWindowSink:
    """Fenetre de lecture reelle, ouverte par ``cv2.imshow``.

    ``cv2.waitKey`` n'est **pas** un ordonnanceur: son delai n'est ni precis ni
    garanti. Il ne sert ici qu'a pomper les evenements de la fenetre et a lire
    une touche; l'attente est bornee par une echeance absolue relue sur
    l'horloge a chaque tour.
    """

    interactive = True

    _FONT = 0  # cv2.FONT_HERSHEY_SIMPLEX
    _FONT_SCALE = 0.7
    _LINE_HEIGHT = 34
    _MARGIN = 14
    _ARROW_HALF_LENGTH = 12
    _GROUP_GAP = 10
    # BGR: vert quand la cadence de lecture tient la cadence cible, rouge
    # sinon. L'ecart du reste de la ligne (blanc) est volontaire: seule
    # l'information qui peut se degrader merite d'attirer l'oeil.
    _RATE_COLOR_ON_TARGET = (60, 200, 60)
    _RATE_COLOR_LATE = (50, 50, 220)

    def __init__(
        self,
        *,
        window_name: str = "mixed-media-util previz",
        clock: Callable[[], float] = time.monotonic,
        pump_step_ms: int = 10,
    ) -> None:
        self._window_name = window_name
        self._clock = clock
        self._pump_step_ms = max(1, int(pump_step_ms))
        self._opened = False
        self._user_closed = False

    def window_closed(self) -> bool:
        """La fenetre a-t-elle ete fermee par l'utilisateur ?

        Sans cette lecture, `imshow` recreait silencieusement une fenetre
        detruite: fermer la fenetre ne fermait rien, et la boucle d'attente de
        touche, qui n'avait aucune condition de sortie, ne rendait jamais la
        main. L'utilisateur perdait le rapport, seul livrable de la commande
        (revue du 2026-08-05).
        """
        if not self._opened:
            return False
        try:
            return cv2.getWindowProperty(self._window_name, cv2.WND_PROP_VISIBLE) < 1
        except cv2.error:
            return True

    def _ensure_window(self) -> None:
        if self._opened:
            return
        if self._user_closed:
            # Ne jamais rouvrir ce que l'utilisateur a ferme.
            raise _WindowClosedByUser()
        try:
            # `WINDOW_GUI_NORMAL` retire la barre d'outils que le backend Qt
            # ajoute par defaut (zoom, enregistrement d'image): un outil
            # d'arbitrage de cadence n'a pas d'interface, et un bouton
            # d'enregistrement irait contre la regle « rien n'est ecrit ».
            cv2.namedWindow(
                self._window_name, cv2.WINDOW_AUTOSIZE | cv2.WINDOW_GUI_NORMAL
            )
        except cv2.error as error:
            raise DisplayUnavailableError(
                "Impossible d'ouvrir une fenetre de lecture: OpenCV a refuse "
                f"'namedWindow' ({error}). Verifier qu'un affichage est disponible "
                "(variable DISPLAY sous Linux) et qu'OpenCV n'est pas compile sans "
                "interface graphique (paquet 'headless').",
                "Une lecture sans affichage reste possible avec --no-display.",
            ) from error
        self._opened = True

    def _draw_text(self, canvas: Any, text: str, x: int, y: int, color) -> None:
        # Contour noir epais puis remplissage colore fin: lisible sur
        # n'importe quel fond, sans dependre d'un bandeau pour le texte lui
        # meme (le bandeau reste pour uniformiser la zone derriere la ligne).
        cv2.putText(
            canvas, text, (x, y), self._FONT, self._FONT_SCALE,
            (0, 0, 0), 4, cv2.LINE_AA,
        )
        cv2.putText(
            canvas, text, (x, y), self._FONT, self._FONT_SCALE,
            color, 1, cv2.LINE_AA,
        )

    def _text_width(self, text: str) -> int:
        (width, _height), _baseline = cv2.getTextSize(
            text, self._FONT, self._FONT_SCALE, 1
        )
        return width

    def _largeur_du_groupe_de_droite(self, overlay: OverlayText) -> int:
        """Largeur du groupe de droite ENTIER -- temoin de boucle compris. Pure.

        Redaction **unique**: elle sert deux fois -- a faire reculer la fleche,
        et a borner le point d'ancrage du groupe --, et deux copies
        divergeraient. Oublier le temoin ici le ferait dessiner hors champ sur
        une source etroite, c'est-a-dire disparaitre en silence: un temoin
        invisible ne temoigne de rien.
        """
        return (
            self._text_width(overlay.right)
            + self._GROUP_GAP
            + self._text_width(overlay.rate)
            + self._GROUP_GAP
            + self._text_width(overlay.loop)
        )

    def _positions_du_groupe_de_droite(
        self, overlay: OverlayText, width: int, left_end_x: int, center_x: int
    ) -> tuple[int, int, int]:
        """Abscisses du rang, de la cadence et du temoin. Fonction **pure**.

        Extraite du trace pour une seule raison: la rendre MESURABLE -- une
        geometrie enterree dans une suite de `putText` ne se verifie qu'en
        relisant des pixels, et la revue du 2026-08-05 a deja paye ce que coute
        un element dessine hors champ que personne ne voit.

        **Les trois elements se posent depuis un SEUL point d'ancrage**, borne
        par la largeur du groupe entier. Les poser au fil du texte et ne borner
        que le dernier ne suffit pas: le temoin, epingle au bord droit, venait
        alors se peindre PAR-DESSUS la cadence des que la ligne serrait
        (mesure a 520 px de large: la cadence finissait a 428 px et le temoin
        commencait a 414). Un temoin illisible ne vaut pas mieux qu'un temoin
        hors champ.

        Ce que l'ancrage NE fait pas: mordre sur le texte de gauche. La borne
        basse est `left_end_x`, decision de la revue du 2026-08-05 -- sur une
        source si etroite que la ligne entiere ne rentre pas (un portrait 9:16
        a 304 px, ou le groupe de droite debordait deja avant ce temoin), c'est
        la fleche, simple separateur, qui est sacrifiee avant l'information.
        """
        largeur_du_groupe = self._largeur_du_groupe_de_droite(overlay)
        x_rang = center_x + self._ARROW_HALF_LENGTH + self._GROUP_GAP
        x_rang = max(
            left_end_x, min(x_rang, width - self._MARGIN - largeur_du_groupe)
        )
        x_cadence = x_rang + self._text_width(overlay.right) + self._GROUP_GAP
        x_temoin = x_cadence + self._text_width(overlay.rate) + self._GROUP_GAP
        # Dernier filet, pour les seules largeurs ou la ligne ENTIERE ne rentre
        # pas: le temoin reste DANS l'image, quitte a serrer. Un temoin d'etat
        # qui disparait est pire que pas de temoin -- il fait croire a
        # l'operateur qu'il lit un ecran complet.
        x_temoin = max(
            self._MARGIN,
            min(x_temoin, width - self._MARGIN - self._text_width(overlay.loop)),
        )
        return x_rang, x_cadence, x_temoin

    def _draw_overlay(self, image: Any, presentation: PresentedFrame) -> Any:
        # Copie systematique: l'image d'origine peut etre celle du cache, et
        # une incrustation dessinee dessus se retrouverait dans toutes les
        # passes suivantes.
        canvas = image.copy()
        overlay = format_overlay(presentation)
        width = canvas.shape[1]

        # Bandeau assombri derriere la ligne: sur un rush clair, une
        # incrustation blanche cerclee de noir reste illisible, et c'est
        # justement l'ecart de cadence qu'il faut pouvoir lire d'un coup
        # d'oeil pendant l'arbitrage.
        band_bottom = self._MARGIN + self._LINE_HEIGHT
        shade = canvas.copy()
        cv2.rectangle(shade, (0, 0), (width, band_bottom), (0, 0, 0), -1)
        cv2.addWeighted(shade, 0.55, canvas, 0.45, 0.0, dst=canvas)

        baseline = self._MARGIN + int(self._LINE_HEIGHT * 0.72)
        white = (255, 255, 255)

        # Zone gauche: timecode non legende, puis position dans le rush
        # source entier.
        self._draw_text(canvas, overlay.left, self._MARGIN, baseline, white)

        # Fleche graphique, pas un caractere ASCII: elle marque visuellement
        # la bascule entre "ou on est dans le rush source" et "ce que cela
        # donnerait dans le lot". Centree sur la largeur de l'image quand la
        # place le permet, jamais au prix d'un recouvrement avec le texte de
        # gauche: sur une source etroite (portrait, ou vignette de test), le
        # texte peut depasser le centre geometrique.
        left_end_x = self._MARGIN + self._text_width(overlay.left) + self._GROUP_GAP
        # La ligne entiere doit tenir dans l'image. Sur une source portrait
        # (304 px de large), la fleche restait centree et le groupe de droite
        # -- rang dans le lot et indicateur de tenue -- etait dessine hors
        # champ, donc silencieusement invisible: l'information la plus utile
        # disparaissait sans que rien ne le dise (revue du 2026-08-05). On
        # recule donc la fleche jusqu'a ce que la fin de ligne rentre, sans
        # jamais la faire chevaucher le groupe de gauche.
        # Le temoin de boucle entre dans ce calcul comme le reste du groupe de
        # droite, par la redaction unique de `_largeur_du_groupe_de_droite`.
        right_width = self._largeur_du_groupe_de_droite(overlay)
        center_max = width - self._MARGIN - right_width - self._GROUP_GAP - self._ARROW_HALF_LENGTH
        center_x = max(width // 2, left_end_x + self._ARROW_HALF_LENGTH)
        center_x = max(left_end_x + self._ARROW_HALF_LENGTH, min(center_x, center_max))
        arrow_y = baseline - self._LINE_HEIGHT // 4
        arrow_from = (center_x - self._ARROW_HALF_LENGTH, arrow_y)
        arrow_to = (center_x + self._ARROW_HALF_LENGTH, arrow_y)
        cv2.arrowedLine(
            canvas, arrow_from, arrow_to, (0, 0, 0), 3, cv2.LINE_AA, tipLength=0.35
        )
        cv2.arrowedLine(
            canvas, arrow_from, arrow_to, white, 1, cv2.LINE_AA, tipLength=0.35
        )

        # Zone droite: rang dans le lot, cadence de lecture / cadence cible
        # (coloree en fonction de la seule chose qui peut se degrader), et
        # temoin de boucle. La geometrie des trois est calculee a part, pour
        # etre mesurable sans relire de pixels.
        x_rang, x_cadence, x_temoin = self._positions_du_groupe_de_droite(
            overlay, width, left_end_x, center_x
        )
        self._draw_text(canvas, overlay.right, x_rang, baseline, white)
        rate_color = (
            self._RATE_COLOR_ON_TARGET
            if overlay.rate_on_target
            else self._RATE_COLOR_LATE
        )
        self._draw_text(canvas, overlay.rate, x_cadence, baseline, rate_color)

        # Temoin de boucle, en BLANC comme le reste de la ligne. Le module
        # reserve deja la couleur a « la seule information qui peut se
        # degrader » (la tenue de la cadence); un second element colore
        # diluerait ce signal. L'etat se lit dans le mot, pas dans la teinte --
        # ce qui le rend aussi lisible sur une capture en niveaux de gris.
        self._draw_text(canvas, overlay.loop, x_temoin, baseline, white)
        return canvas

    def present(self, image: Any, presentation: PresentedFrame) -> None:
        self._ensure_window()
        if self.window_closed():
            self._note_user_close()
            raise _WindowClosedByUser()
        try:
            cv2.imshow(self._window_name, self._draw_overlay(image, presentation))
            cv2.waitKey(1)
        except cv2.error as error:
            raise DisplayUnavailableError(
                f"Affichage interrompu par OpenCV ({error}).",
                "Relancer avec --no-display pour une lecture mesuree sans "
                "fenetre.",
            ) from error

    def wait(self, seconds: float) -> int | None:
        deadline = self._clock() + seconds
        while True:
            remaining = deadline - self._clock()
            if remaining <= 0:
                return None
            step = max(1, min(self._pump_step_ms, int(remaining * 1000)))
            key = cv2.waitKey(step)
            if key != -1:
                return key & 0xFF
            if self.window_closed():
                self._note_user_close()
                return KEY_QUIT

    def poll_key(self) -> int | None:
        if not self._opened:
            return None
        key = cv2.waitKey(1)
        return None if key == -1 else key & 0xFF

    def wait_for_key(self) -> int | None:
        self._ensure_window()
        while True:
            key = cv2.waitKey(50)
            if key != -1:
                return key & 0xFF
            # Condition de sortie: sans elle, cette boucle ne rendait jamais
            # la main une fois la fenetre fermee.
            if self.window_closed():
                self._note_user_close()
                return KEY_QUIT

    def _note_user_close(self) -> None:
        self._user_closed = True
        self._opened = False

    def close(self) -> None:
        if self._opened:
            cv2.destroyWindow(self._window_name)
            cv2.waitKey(1)
            self._opened = False


def _local_display_socket(display: str) -> Path | None:
    """Chemin de la socket X d'un affichage **local**, ou `None`.

    Ne traite que les formes locales (`:0`, `:77.0`, `unix:1`), les seules
    verifiables sans ouvrir de connexion reseau. Une adresse distante
    (`machine:0`) rend `None`: on ne sait pas la sonder a bon compte, et
    inventer un verdict serait pire que de ne rien dire.
    """
    if not display or "/" in display:
        return None
    adresse = display[len("unix"):] if display.startswith("unix:") else display
    if not adresse.startswith(":"):
        return None
    numero = adresse[1:].split(".")[0]
    if not numero.isdigit():
        return None
    return Path("/tmp/.X11-unix") / f"X{numero}"


#: Le conseil que la CLI ajoute a deux de ses trois refus d'affichage. Il est
#: nomme parce qu'il est **partage**: le rediger deux fois ferait diverger
#: deux messages que rien n'obligerait a rester identiques (``EPIC11-ARB-73``).
#: Il nomme ``--no-display``, donc il n'est jamais rendu par la TUI.
_CONSEIL_SESSION_GRAPHIQUE = (
    "Relancer dans une session graphique, ou utiliser --no-display pour une "
    "lecture mesuree sans fenetre."
)


#: Le conseil du refus << OpenCV sans interface >>. Il nomme DEUX issues, comme
#: `EPIC11-ARB-89` l'exige de tout refus : mesurer sans fenetre, ou remplacer la
#: roue. La commande est ecrite EN ENTIER parce qu'elle n'est pas devinable --
#: `opencv-python` et `opencv-python-headless` fournissent le meme module `cv2`,
#: donc l'un remplace l'autre au lieu de s'y ajouter, et le `--force` de `pipx
#: inject` est ce qui autorise ce remplacement.
_CONSEIL_SANS_INTERFACE_OPENCV = (
    "Utiliser --no-display pour une lecture mesuree sans fenetre, ou installer "
    "la roue OpenCV avec interface : pipx inject --force mmu-tui opencv-python"
    " -- elle exige en plus les bibliotheques systeme libGL et libX11."
)


def _opencv_sait_afficher() -> bool:
    """Dire si CETTE compilation d'OpenCV peut ouvrir une fenetre.

    **La presence du symbole ne prouve rien, et c'est un piege paye.** Le garde
    d'origine testait ``hasattr(cv2, "imshow")`` : mesure du 2026-09-06 sur la
    roue headless 5.0.0, ``hasattr`` rend ``True`` et l'appel leve ensuite
    ``cv2.error: The function is not implemented``. Le garde ne s'est donc
    jamais declenche, et le refus lisible qu'il devait produire n'existait pas.

    ``getBuildInformation()`` porte, lui, la CAPACITE : la ligne ``GUI:`` vaut
    ``NONE`` sur une roue headless et nomme la boite a outils (``GTK``,
    ``COCOA``, ``WIN32``, ``QT``) sinon. C'est la seule source qui distingue les
    deux, et elle ne coute qu'une lecture de chaine.

    Le repli est PERMISSIF a dessein : si la ligne est absente d'une version
    future d'OpenCV, on laisse passer plutot que de refuser un affichage qui
    marcherait. Un faux refus retire une fonctionnalite qui existe ; un faux
    passage retombe sur le refus suivant, qui est deja ecrit.
    """
    try:
        information = cv2.getBuildInformation()
    except Exception:                     # pragma: no cover - roue improbable
        return True
    for ligne in information.splitlines():
        depouillee = ligne.strip()
        if depouillee.startswith("GUI:"):
            return depouillee.split(":", 1)[1].strip().upper() not in ("", "NONE")
    return True


def ensure_display_available(
    *, environ: Mapping[str, str] | None = None, platform: str = ""
) -> None:
    """Refuser tot une session graphique sans affichage.

    ``cv2.imshow`` sans affichage ne leve pas toujours proprement: selon la
    compilation, l'absence de ``DISPLAY`` produit une ``cv2.error`` peu lisible,
    voire un plantage du processus. La detection a donc lieu **en amont**, et
    le refus porte le code ``DISPLAY_UNAVAILABLE`` avec le code de sortie 2.
    """
    env = os.environ if environ is None else environ
    system = platform or sys.platform
    if system.startswith("linux") and not (
        env.get("DISPLAY") or env.get("WAYLAND_DISPLAY")
    ):
        raise DisplayUnavailableError(
            f"{DISPLAY_UNAVAILABLE}: aucun affichage disponible (ni DISPLAY ni "
            "WAYLAND_DISPLAY dans l'environnement).",
            _CONSEIL_SESSION_GRAPHIQUE,
        )
    # Une variable **definie** ne prouve pas qu'un serveur repond. Le cas est
    # courant: `ssh` sans redirection graphique, un `tmux` qui survit a la
    # session graphique, un conteneur qui herite `DISPLAY=:0`. Qt appelle
    # alors `qFatal()` dans le natif, et le processus meurt sur SIGABRT (code
    # 134): ni exception, ni code de sortie exploitable, ni rapport. C'est le
    # Piege 5 que cette story a nomme (revue du 2026-08-05).
    if system.startswith("linux") and not env.get("WAYLAND_DISPLAY"):
        socket_path = _local_display_socket(env.get("DISPLAY", ""))
        if socket_path is not None and not socket_path.exists():
            raise DisplayUnavailableError(
                f"{DISPLAY_UNAVAILABLE}: DISPLAY={env.get('DISPLAY')!r} est "
                "defini mais aucun serveur graphique ne repond a cette adresse "
                f"({socket_path} est absent). C'est le cas d'une connexion "
                "distante sans redirection graphique, ou d'une session detachee "
                "de son affichage.",
                _CONSEIL_SESSION_GRAPHIQUE,
            )
    if not _opencv_sait_afficher():
        raise DisplayUnavailableError(
            f"{DISPLAY_UNAVAILABLE}: cette compilation d'OpenCV n'expose aucune "
            "interface graphique (roue 'headless').",
            _CONSEIL_SANS_INTERFACE_OPENCV,
        )


# --------------------------------------------------------------------------
# Decodage sequentiel et cache memoire
# --------------------------------------------------------------------------


def resize_to_height(image: Any, height: int | None) -> Any:
    """Ramener une image a ``height`` pixels de haut, ratio conserve.

    ``INTER_AREA`` est l'interpolation adaptee a la reduction. Le
    redimensionnement a lieu **avant** la mise en cache et jamais apres:
    cacher des frames pleine resolution saturerait le budget en quelques
    dizaines d'images (6,2 Mo par frame HD contre 1,6 Mo a 960x540).
    """
    if height is None or height <= 0:
        return image
    source_height, source_width = image.shape[0], image.shape[1]
    if source_height <= height:
        return image
    width = max(1, int(round(source_width * height / source_height)))
    return cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)


class FrameCache:
    """Cache LRU borne en octets des frames deja decodees et redimensionnees.

    **Optimisation, jamais condition de justesse**: un defaut de cache
    redecode, et une eviction est signalee par ``CACHE_EVICTED`` sans jamais
    alterer la sequence presentee.
    """

    def __init__(self, budget_bytes: int) -> None:
        self.budget_bytes = int(budget_bytes)
        self._entries: dict[int, Any] = {}
        self._bytes = 0
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def __contains__(self, source_index: int) -> bool:
        return source_index in self._entries

    def __len__(self) -> int:
        return len(self._entries)

    @property
    def used_bytes(self) -> int:
        return self._bytes

    def get(self, source_index: int) -> Any | None:
        image = self._entries.get(source_index)
        if image is None:
            self.misses += 1
            return None
        # Reinsertion en queue: l'ordre d'insertion d'un dict est l'ordre LRU.
        del self._entries[source_index]
        self._entries[source_index] = image
        self.hits += 1
        return image

    def put(self, source_index: int, image: Any) -> None:
        size = int(getattr(image, "nbytes", 0))
        if source_index in self._entries:
            self._bytes -= int(getattr(self._entries[source_index], "nbytes", 0))
            del self._entries[source_index]
        if self.budget_bytes <= 0 or size > self.budget_bytes:
            # Une frame plus lourde que le budget entier n'est jamais retenue:
            # la mettre en cache reviendrait a vider le cache a chaque image.
            self.evictions += 1
            return
        self._entries[source_index] = image
        self._bytes += size
        while self._bytes > self.budget_bytes and self._entries:
            oldest = next(iter(self._entries))
            self._bytes -= int(getattr(self._entries[oldest], "nbytes", 0))
            del self._entries[oldest]
            self.evictions += 1


class SequentialFrameReader:
    """Lecture **sequentielle** d'un rush, rang compte a partir de 0.

    ``cv2.CAP_PROP_POS_FRAMES`` n'est jamais employe: le positionnement par
    index sur un flux a images bidirectionnelles atterrit couramment sur une
    image cle voisine, en silence, et la previz montrerait alors autre chose
    que ce que ``extract`` retiendrait. Revenir en arriere **rouvre** la
    capture et relit depuis le debut: c'est plus lent, et c'est juste.
    """

    def __init__(
        self,
        video_path: str | Path,
        *,
        height: int | None = DEFAULT_PREVIEW_HEIGHT,
        capture_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._video_path = str(video_path)
        self._height = height
        self._capture_factory = capture_factory or (
            lambda: cv2.VideoCapture(self._video_path)
        )
        self._capture: Any = None
        self._next_index = 0
        self.read_count = 0
        self.open_count = 0
        self.truncated = False

    def _open(self) -> None:
        self.close()
        capture = self._capture_factory()
        if hasattr(capture, "isOpened") and not capture.isOpened():
            raise ExtractionInputError(
                f"Impossible d'ouvrir le rush pour lecture: {self._video_path}. "
                "Le fichier existe mais aucun decodeur disponible ne sait le lire."
            )
        self._capture = capture
        self._next_index = 0
        self.open_count += 1

    def frame_at(self, source_index: int) -> Any | None:
        """Rendre la frame de rang ``source_index``, ou ``None`` si le flux est court.

        ``None`` signale une troncature du flux: le decodeur a rendu moins de
        frames que le cardinal etabli par ``resolve_source_frame_count``. Le
        cas est **rapporte** (``DECODE_TRUNCATED``), jamais masque.
        """
        if self._capture is None or source_index < self._next_index:
            self._open()
        image = None
        while self._next_index <= source_index:
            ok, decoded = self._capture.read()
            self.read_count += 1
            if not ok or decoded is None:
                self.truncated = True
                return None
            self._next_index += 1
            image = decoded
        return resize_to_height(image, self._height)

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None


# --------------------------------------------------------------------------
# Boucle de lecture
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PassOutcome:
    """Resultat d'une passe de lecture: son rapport et la touche qui l'a close."""

    report: PlaybackReport
    key: int | None
    interrupted: bool
    #: Etat de la lecture en boucle **a la sortie** de la passe. La bascule se
    #: fait en vol, dans `_play_one_pass`; c'est par ce champ qu'elle survit a
    #: la passe et gouverne la suivante.
    loop_active: bool = False


def _play_one_pass(
    schedule: Sequence[ScheduledFrame],
    *,
    fps_target: float,
    source_frame_count: int,
    lot_total_frames: int,
    reader: SequentialFrameReader,
    cache: FrameCache,
    sink: Any,
    clock: Callable[[], float],
    on_late: str,
    loop_active: bool = False,
    logger: logging.Logger | None = None,
) -> PassOutcome:
    """Presenter une passe complete, en tenant les echeances absolues.

    ``loop_active`` entre et ressort: la passe le porte sur chaque image
    presentee (le temoin de l'incrustation) et le rend a l'appelant, qui decide
    de rejouer ou non. Le defaut ``False`` reproduit l'etat anterieur.
    """
    observations: list[FrameObservation] = []
    omises = 0
    interrupted = False
    exit_key: int | None = None
    warnings: set[str] = set()
    evictions_before = cache.evictions

    duree_nominale = schedule[-1].t_theo_s if schedule else 0.0

    def acquire(scheduled: ScheduledFrame) -> Any | None:
        image = cache.get(scheduled.source_index)
        if image is not None:
            return image
        image = reader.frame_at(scheduled.source_index)
        if image is None:
            warnings.add(DECODE_TRUNCATED)
            if logger is not None:
                logger.warning(
                    "Flux tronque: la frame source %d n'a pas pu etre decodee "
                    "alors que le cardinal source en annonce davantage. Lecture "
                    "arretee a cette frame.",
                    scheduled.source_index,
                )
            return None
        cache.put(scheduled.source_index, image)
        return image

    # Amorcage: la premiere frame est mise a disposition **avant** que
    # l'horloge de lecture ne demarre. La lecture etant sequentielle et sans
    # positionnement par index (Piege 2), atteindre la frame 100 impose de
    # decoder les cent premieres: compter ce cout comme un retard de
    # cadencement rendrait toute fenetre `--start` structurellement en retard,
    # et masquerait le vrai objet de la mesure, qui est la capacite a TENIR la
    # cadence une fois la lecture lancee. Le cout est donc mesure a part et
    # rapporte (`amorcage_s`), jamais dissimule.
    priming_started = clock()
    primed_image = None
    if schedule:
        primed_image = acquire(schedule[0])
    origin = clock()
    amorcage_s = origin - priming_started

    try:
        for position, scheduled in enumerate(schedule):
            if primed_image is not None:
                image, primed_image = primed_image, None
            else:
                image = acquire(scheduled)
            if image is None:
                break

            deadline = origin + scheduled.t_theo_s
            key = sink.wait(deadline - clock())
            if key is None:
                key = sink.poll_key()
            # La touche de boucle **bascule un etat, elle ne clot pas la
            # passe**: c'est la seule facon de couper une boucle deja lancee
            # sans quitter la session. Elle n'apparait donc jamais dans
            # `exit_key`, et l'attente REPREND jusqu'a l'echeance de l'image en
            # cours -- `sink.wait` rend la main des la premiere touche, si bien
            # qu'une bascule non suivie d'une reprise ferait paraitre cette
            # image-la en avance et fausserait la mesure que la commande existe
            # pour rendre. L'echeance est absolue: reprendre l'attente ne
            # decale rien.
            while key == KEY_LOOP:
                loop_active = not loop_active
                key = sink.wait(deadline - clock())
                if key is None:
                    key = sink.poll_key()
            if key is not None and key in (
                KEY_NEXT, KEY_PREVIOUS, KEY_REPLAY, KEY_QUIT, _KEY_ESCAPE
            ):
                exit_key = KEY_QUIT if key == _KEY_ESCAPE else key
                break

            elapsed = clock() - origin
            if not should_present(
                t_theo_s=scheduled.t_theo_s, elapsed_s=elapsed, on_late=on_late
            ):
                omises += 1
                continue

            sink.present(
                image,
                PresentedFrame(
                    fps_target=float(fps_target),
                    output_rank=scheduled.output_rank,
                    window_position=position,
                    frames_attendues=len(schedule),
                    source_index=scheduled.source_index,
                    source_frame_count=source_frame_count,
                    lot_total_frames=lot_total_frames,
                    frame_timecode=scheduled.frame_timecode,
                    t_theo_s=scheduled.t_theo_s,
                    t_real_s=elapsed,
                    frames_omises=omises,
                    loop_active=loop_active,
                ),
            )
            observations.append(
                FrameObservation(
                    output_rank=scheduled.output_rank,
                    source_index=scheduled.source_index,
                    t_theo_s=scheduled.t_theo_s,
                    t_real_s=elapsed,
                )
            )
    except KeyboardInterrupt:
        interrupted = True
    except _WindowClosedByUser:
        exit_key = KEY_QUIT

    if cache.evictions > evictions_before:
        warnings.add(CACHE_EVICTED)

    partiel = interrupted or exit_key is not None or DECODE_TRUNCATED in warnings
    report = build_playback_report(
        observations,
        fps_target=fps_target,
        frames_attendues=len(schedule),
        duree_nominale_s=duree_nominale,
        frames_omises=omises,
        partiel=partiel,
        extra_warnings=tuple(warnings),
        amorcage_s=amorcage_s,
    )
    return PassOutcome(
        report=report,
        key=exit_key,
        interrupted=interrupted,
        loop_active=loop_active,
    )


# --------------------------------------------------------------------------
# Session
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PrevizSession:
    """Tout ce qu'une session connait de la source, calcule **une seule fois**.

    Un probe, une qualification, un cardinal, une ``FrameSelection`` par
    cadence demandee, toutes calculees avant la premiere image affichee. La
    navigation entre cadences ne repaie donc ni le probe, ni l'eventuel
    ``ffprobe -count_frames``, qui est le poste le plus cher de la preparation
    sur un rush long.
    """

    video_path: Path
    fps_source: Fraction
    source_frame_count: int
    source_frame_count_is_exact: bool
    start_timecode: str | None
    stream_duration_seconds: float | None
    fps_targets: tuple[float, ...]
    selections: tuple[FrameSelection, ...]
    schedules: tuple[tuple[ScheduledFrame, ...], ...]
    #: Verdict de ``SourceQualification.cadence_corroboree``, transporte tel
    #: quel (``EPIC11-ARB-76``, story 11.4). **La previz ne s'en sert pas**:
    #: elle ne refuse rien de plus qu'avant, la lecture comparee n'ecrivant
    #: rien. Il existe parce que ``run_extraction`` **refuse** une source dont
    #: la cadence n'est pas corroborable (``extraction.py``, ARB-6): sans ce
    #: champ, un conteneur avare -- Matroska sans duree ni ``nb_frames`` --
    #: laisse la previz reussir puis l'extraction refuser, c'est-a-dire vingt
    #: minutes de lecture avant un refus previsible des le depart. L'appelant
    #: qui enchaine les deux temps lit ce champ pour **avertir** au premier.
    #:
    #: Le defaut ``True`` reproduit l'etat anterieur -- rien n'avertissait --
    #: pour les sessions construites a la main; le seul producteur reel,
    #: ``prepare_previz``, le renseigne **toujours** explicitement.
    cadence_corroboree: bool = True


@dataclass(frozen=True)
class PrevizResult:
    """Resultat complet d'une session de lecture. Aucun artefact, aucun fichier."""

    session: PrevizSession
    reports: tuple[PlaybackReport, ...]
    interrupted: bool
    decoded_frames: int
    cache_hits: int
    cache_misses: int


def _validated_targets(fps_targets: Sequence[float]) -> tuple[float, ...]:
    if not fps_targets:
        raise ExtractionInputError(
            "Aucune cadence cible: fournir au moins un --fps (repetable pour "
            "comparer plusieurs cadences dans une seule session)."
        )
    validated: list[float] = []
    for value in fps_targets:
        if not is_strict_number(value):
            raise ExtractionInputError(
                f"Parametre --fps invalide: {value!r}. Attendu un nombre."
            )
        if value != value or value in (float("inf"), float("-inf")):
            raise ExtractionInputError(f"Parametre --fps non fini: {value!r}.")
        if value <= 0:
            raise ExtractionInputError(
                f"Parametre --fps invalide: {value}. Attendu un nombre strictement "
                "positif."
            )
        validated.append(float(value))
    return tuple(validated)


def prepare_previz(
    *,
    video_path: str | Path,
    fps_targets: Sequence[float],
    source_in_timecode: str | None = None,
    source_out_timecode: str | None = None,
    start_seconds: float | None = None,
    duration_seconds: float | None = None,
    probe: Mapping[str, Any] | None = None,
    ffprobe_binary: str = "ffprobe",
    logger: logging.Logger | None = None,
) -> PrevizSession:
    """Preparer une session: probe, qualification, cardinal, selections.

    L'ordre est impose et chaque etape est **consommee**, jamais reimplementee:
    ``video_metadata.probe_media`` -> ``extraction.qualify_source`` ->
    ``extraction.resolve_source_frame_count`` -> ``select_source_frames``.
    C'est cette chaine, et le fait qu'elle recoive exactement les memes
    arguments que ``extract``, qui garantit que la previz montre exactement les
    frames que ``extract`` retiendrait.

    Deux paires d'options, deux effets qu'il ne faut jamais confondre
    (story 3.7, AC 12):

    * ``source_in_timecode`` / ``source_out_timecode`` (``--in`` / ``--out``)
      changent **quelles frames sont retenues**. Elles descendent telles quelles
      dans ``select_source_frames``, comme dans ``extract``: c'est la meme
      fenetre, calculee une seule fois, dans le meme noyau.
    * ``start_seconds`` / ``duration_seconds`` (``--start`` / ``--duration``)
      changent **lesquelles, parmi les retenues, sont jouees** dans cette
      session. Elles n'entrent jamais dans la selection.

    Les deux paires se combinent, et ``--start`` se lit toujours sur la ligne
    de temps du rush entier -- ``t_theo_s`` derive du ``source_index`` absolu --
    et non sur celle de l'extrait.

    Rien n'est ecrit: aucune arborescence projet n'est creee, aucun journal
    fichier n'est ouvert, aucun manifest n'est touche.
    """
    path = Path(video_path)
    targets = _validated_targets(fps_targets)
    if not path.is_file():
        raise ExtractionInputError(f"Fichier video introuvable: {path}")

    probe_data = (
        video_metadata.probe_media(str(path), ffprobe_bin=ffprobe_binary)
        if probe is None
        else dict(probe)
    )
    qualification = extraction.qualify_source(probe_data)

    # ARB-12 (`decisions-2026-08-05.md`): meme garde, meme message et meme
    # moment que `extract`. Elle etait posee plus bas, dans le noyau de
    # selection, donc **apres** un eventuel `ffprobe -count_frames` qui paie un
    # decodage complet: la previz faisait attendre l'utilisateur avant de
    # refuser ce que l'extraction refusait tout de suite.
    for fps_target in targets:
        if Fraction(exact_frame_rate(fps_target)) > qualification.fps_source:
            raise ExtractionInputError(
                extraction.upsampling_refusal_message(
                    fps_target, qualification.fps_source
                )
            )

    source_frame_count, is_exact = extraction.resolve_source_frame_count(
        path, qualification, ffprobe_bin=ffprobe_binary, logger=logger
    )

    if logger is not None:
        logger.info(
            "Source qualifiee: cadence %s im/s, %d frame(s) source (%s), timecode "
            "de depart %s",
            qualification.fps_source,
            source_frame_count,
            "comptage exact" if is_exact else "ESTIMATION",
            qualification.start_timecode or "absent",
        )

    selections = tuple(
        select_source_frames(
            fps_source=qualification.fps_source,
            fps_target=fps_target,
            source_frame_count=source_frame_count,
            source_start_timecode=qualification.start_timecode,
            source_in_timecode=source_in_timecode,
            source_out_timecode=source_out_timecode,
            source_duration_seconds=qualification.stream_duration_seconds,
            source_frame_count_is_exact=is_exact,
        )
        for fps_target in targets
    )
    schedules = tuple(
        restrict_schedule(
            build_schedule(selection),
            start_seconds=start_seconds,
            duration_seconds=duration_seconds,
        )
        for selection in selections
    )
    # Le message dit sur quoi la selection a porte. Sur un extrait, affirmer
    # « la selection porte sur le rush entier » enverrait l'operateur chercher
    # une erreur de --start alors que ce sont ses bornes qui excluent la plage
    # demandee -- ou l'inverse. Les deux causes doivent rester distinguables.
    if source_in_timecode is None and source_out_timecode is None:
        portee = "la selection porte sur le rush entier"
    else:
        portee = (
            "la selection est deja bornee a l'extrait "
            f"{source_in_timecode or 'debut du rush'} -> "
            f"{source_out_timecode or 'fin du rush'}"
        )
    for fps_target, schedule in zip(targets, schedules):
        if not schedule:
            raise ExtractionInputError(
                f"Aucune frame a presenter a {fps_target:g} im/s dans la fenetre "
                f"demandee (--start / --duration): {portee}, mais aucune frame "
                "retenue ne tombe dans cette plage."
            )
    return PrevizSession(
        video_path=path,
        fps_source=qualification.fps_source,
        source_frame_count=source_frame_count,
        source_frame_count_is_exact=is_exact,
        start_timecode=qualification.start_timecode,
        stream_duration_seconds=qualification.stream_duration_seconds,
        fps_targets=targets,
        selections=selections,
        schedules=schedules,
        # Lu chez la qualification, jamais recalcule ici: le critere de
        # corroboration appartient a `extraction.SourceQualification` et une
        # seconde implementation divergerait du refus qu'elle commande.
        cadence_corroboree=qualification.cadence_corroboree,
    )


def play_cadences(
    session: PrevizSession,
    *,
    sink: Any,
    height: int | None = DEFAULT_PREVIEW_HEIGHT,
    memory_budget_mb: float = DEFAULT_MEMORY_BUDGET_MB,
    on_late: str = ON_LATE_REPORT,
    clock: Callable[[], float] = time.monotonic,
    capture_factory: Callable[[], Any] | None = None,
    logger: logging.Logger | None = None,
    reader: SequentialFrameReader | None = None,
    cache: FrameCache | None = None,
) -> PrevizResult:
    """Lire les cadences d'une session, dans **une seule** ouverture du rush.

    La navigation entre cadences se fait au clavier, sans reouvrir le fichier
    ni recalculer quoi que ce soit: ``n`` cadence suivante, ``p`` precedente,
    ``r`` rejouer, ``l`` lecture en boucle (bascule), ``q`` quitter. Un cache
    memoire borne sert les passes suivantes et les indices communs a deux
    cadences (a 25 im/s, 12,5 et 5 partagent une frame sur deux).

    **La boucle est coupee par defaut**, et elle ne s'arme que par ``l``: une
    session qui ne touche pas cette touche -- toute session ``--no-display``,
    donc toute session d'integration continue -- se deroule exactement comme
    avant. ``l`` s'appuie pendant la lecture aussi bien qu'en fin de passe;
    ``q`` reste prioritaire, y compris boucle armee, sans quoi la boucle serait
    un piege.

    ``Ctrl+C`` interrompt proprement: la capture et la fenetre sont liberees
    dans un ``finally``, un rapport **partiel** est rendu, et aucune trace
    Python n'est affichee.
    """
    if on_late not in ON_LATE_POLICIES:
        raise ExtractionInputError(
            f"Politique --on-late inconnue: {on_late!r}. Valeurs admises: "
            f"{', '.join(ON_LATE_POLICIES)}."
        )
    if height is not None and height <= 0:
        raise ExtractionInputError(
            f"Parametre --height invalide: {height!r}. Attendu un entier strictement "
            "positif."
        )
    if memory_budget_mb <= 0:
        raise ExtractionInputError(
            f"Parametre --memory-budget-mb invalide: {memory_budget_mb!r}. Attendu un "
            "nombre strictement positif."
        )

    reader = reader or SequentialFrameReader(
        session.video_path, height=height, capture_factory=capture_factory
    )
    cache = cache or FrameCache(int(memory_budget_mb * _BYTES_PER_MB))

    reports: list[PlaybackReport] = []
    interrupted = False
    current = 0
    #: Lecture en boucle: coupee au demarrage, et rien d'autre que la touche
    #: `l` ne peut l'armer. C'est ce qui rend le comportement de `mmu previz`
    #: inchange tant que personne n'appuie dessus.
    loop_active = False

    try:
        while 0 <= current < len(session.schedules):
            if logger is not None:
                logger.info(
                    "Lecture a %g im/s: %d frame(s) retenue(s) sur %d frame(s) "
                    "source",
                    session.fps_targets[current],
                    len(session.schedules[current]),
                    session.source_frame_count,
                )
                # Les reserves de la selection (story 3.2) sont calculees ici
                # depuis toujours et n'etaient dites nulle part: `extract`
                # annonce `NTSC_RATE_OUT_OF_SCOPE` la ou `previz` restait
                # muette sur le meme rush a la meme cadence. Une commande dont
                # le seul but est d'eclairer le choix d'une cadence ne peut pas
                # taire ce qui disqualifie ce choix (revue du 2026-08-05).
                for code in session.selections[current].warnings:
                    logger.info("  reserve de selection: %s", code)
            outcome = _play_one_pass(
                session.schedules[current],
                fps_target=session.fps_targets[current],
                source_frame_count=session.source_frame_count,
                lot_total_frames=session.selections[current].expected_frame_count,
                reader=reader,
                cache=cache,
                sink=sink,
                clock=clock,
                on_late=on_late,
                loop_active=loop_active,
                logger=logger,
            )
            reports.append(outcome.report)
            loop_active = outcome.loop_active
            if logger is not None:
                # Une ligne compacte pendant la session; le rapport chiffre
                # complet est rendu une seule fois, par l'appelant, a la fin.
                logger.info(
                    "Passe a %g im/s terminee: %d/%d frame(s) presentee(s), %d "
                    "omise(s), retard max %.1f ms, derive %.1f ms, temps reel %s",
                    outcome.report.fps_target,
                    outcome.report.frames_presentees,
                    outcome.report.frames_attendues,
                    outcome.report.frames_omises,
                    outcome.report.retard_max_s * 1000,
                    outcome.report.derive_finale_s * 1000,
                    "tenu" if outcome.report.temps_reel_tenu else "NON TENU",
                )

            if outcome.interrupted:
                interrupted = True
                break

            key = outcome.key
            # Rejouer sans rien demander suppose DEUX choses: que la boucle
            # soit armee, et que la passe ait reellement montre quelque chose.
            #
            # `frames_presentees > 0` n'est pas une precaution de style. Une
            # passe qui n'a rien montre -- flux tronque des la premiere image,
            # fenetre d'affichage hors du rush -- n'a jamais appele `poll_key`:
            # rebouclee, elle ne laisserait JAMAIS a l'operateur l'occasion
            # d'appuyer sur quoi que ce soit. Une boucle qu'on ne peut pas
            # couper n'est pas une fonction, c'est un blocage. Dans ce cas on
            # rend la main au clavier, boucle armee ou non.
            peut_reboucler = (
                loop_active
                and sink.interactive
                and outcome.report.frames_presentees > 0
            )
            if key is None and sink.interactive and not peut_reboucler:
                key = sink.wait_for_key()
                if key == KEY_LOOP:
                    # `l` en fin de passe arme la boucle, et la bascule VAUT la
                    # reponse: il n'y a plus de touche a attendre, la cadence
                    # courante repart. La bascule INVERSE ne s'atteint pas ici
                    # -- boucle armee, on n'attend plus de touche --, et c'est
                    # voulu: on coupe une boucle en vol, pendant que les images
                    # defilent, jamais entre deux passes.
                    loop_active = True
                    key = None
                    peut_reboucler = outcome.report.frames_presentees > 0
            if key == KEY_QUIT:
                break
            # Boucle armee et passe close par sa propre fin: on rejoue LA MEME
            # cadence, sans reouvrir le fichier ni redemander de touche.
            if key is None and peut_reboucler:
                continue
            if not sink.interactive and key is None:
                current += 1
                continue
            if key == KEY_PREVIOUS:
                current = max(0, current - 1)
            elif key == KEY_REPLAY:
                # Rejouer la meme cadence: la capture est rouverte par le
                # lecteur des qu'un indice anterieur est demande, jamais
                # deplacee par CAP_PROP_POS_FRAMES.
                continue
            else:
                current += 1
    except KeyboardInterrupt:
        interrupted = True
    finally:
        reader.close()
        sink.close()

    return PrevizResult(
        session=session,
        reports=tuple(reports),
        interrupted=interrupted,
        decoded_frames=reader.read_count,
        cache_hits=cache.hits,
        cache_misses=cache.misses,
    )
