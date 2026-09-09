"""Qualification de la source et orchestration de `extract` (story 3.1).

Perimetre
---------
Ce module possede ce que la story 3.1 possede et rien d'autre: la validation
des entrees, la qualification du rush (cadence, detection VFR, cardinal de
frames source, timecode de depart), l'assemblage du dossier de lot et des
noms de fichiers, l'appel a ffmpeg, le renommage, puis l'assemblage de
l'`ExtractionRecord` et l'appel de persistance.

Il **consomme** et ne reimplemente jamais:

* `frame_selection.select_source_frames` (story 3.2) -- la regle de selection.
  Aucun arrondi de cadence, aucune boucle d'indices, aucun re-tri ne vit ici.
* `source_confirmation` (story 3.3) -- le rapport source et la confirmation.
* `io.extraction_manifest.persist_extraction` (story 3.4) -- la persistance.
* `io.naming` / `io.project_layout` (Epic 2) -- identifiants, slugs et chemins.

`cli.py` ne garde que le parsing d'arguments et le mapping des exceptions vers
les codes de sortie (`ARCHITECTURE_DETAILED.md` section 5; la story 2.5 a
procede ainsi pour `project_layout`).

Plusieurs rushs, plusieurs cadences, un seul projet
---------------------------------------------------
Extraire un meme rush vers plusieurs cadences cibles dans un meme projet est
un usage **nominal** depuis le 2026-08-04 (`decisions-2026-08-04.md`), pas un
cas limite: chaque cadence produit son propre lot (`build_lot_id` inclut la
cadence), son propre dossier (`frames/<rush>_<fps-court>/`) et sa propre
entree `lots[]`, qui porte desormais `fps_target`. Aucun avertissement n'est
emis et aucune cadence n'est refusee de ce fait; les lots deja presents
restent verifiables tels quels.

Base de temps du timecode
-------------------------
La base est **source** (`decisions-2026-08-03.md`, decision 3 / ARB-2) et elle
est machine-lisible dans `FrameSelection.timecode_base_fps`. Regle imperative:
ne **jamais** valider un timecode issu de la selection contre `fps_target`. Le
nom de fichier porte pourtant `fps_target` juste a cote du timecode, ce qui se
lit spontanement comme « ce timecode est a cette cadence »: c'est faux.
`validate_timecode(tc, fps_target)` **leve** des que `ff >= ceil(fps_target)`
(source 30 fps, cible 4 fps, indice source 97 -> `00:00:03:07`, et `07 >= 4`).
Ce module ne revalide donc aucun timecode: la story 3.2 les a deja valides
contre la cadence source au moment de les emettre.

Convention d'ecriture: messages en francais **sans accents**, comme
`io/manifest.py`, `codec_profiles.py` et `source_confirmation.py`.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping

from jsonschema.exceptions import ValidationError

from . import ffmpeg_utils, source_confirmation, video_metadata
from .codec_profiles import exact_frame_rate
from .frame_selection import (
    FrameSelection,
    FrameSelectionError,
    select_source_frames,
)
from .io import project_layout
from .io.extraction_manifest import (
    EXTRACTION_OUTPUT_BIT_DEPTH,
    MANIFEST_FILENAME,
    ExtractionPersistenceError,
    ExtractionRecord,
    LotStateConflictError,
    PersistedExtraction,
    message_avertissement_ecrasement,
    persist_extraction,
    resolve_version_rank,
    validate_extraction_state_transition,
)
from .io.manifest import load_manifest
from .io.naming import (
    NamingError,
    bounds_suffix,
    build_extracted_frame_filename,
    build_lot_id,
    format_fps_short,
    VERSION_RANK_MAX,
    format_rang_de_desambiguisation,
    normalize_identifier,
    rang_de_desambiguisation,
)
from .io import version_ranks

__all__ = [
    "VFR_RELATIVE_TOLERANCE",
    "COUNT_FRAMES_TIMEOUT_SECONDS",
    "CODE_SUCCES",
    "CODE_ERREUR",
    "CODE_PREREQUIS_ABSENT",
    "CODE_REFUS",
    "CODE_INTERRUPTION",
    "CODES_DE_SORTIE",
    "code_de_sortie",
    "correspondance_de_sortie",
    "ExtractionInputError",
    "SourceQualification",
    "ExtractionOutcome",
    "check_fps_form_consistency",
    "CRITERES_IDENTITE_RUSH",
    "CRITERE_DE_DERNIER_RECOURS",
    "CriteresIdentiteRush",
    "ConflitIdentiteRush",
    "comparer_identite_rush",
    "disambiguated_rush_id",
    "RangsDeDesambiguisationEpuises",
    "rangs_de_desambiguisation_employes",
    "qualify_source",
    "rush_identity_conflict",
    "upsampling_refusal_message",
    "cardinal_corrobore",
    "resolve_source_frame_count",
    "count_frames_exact",
    "run_extraction",
]


#: Ecart relatif maximal tolere entre `avg_frame_rate` et `r_frame_rate`
#: avant de declarer la source a cadence variable (AC 8, risque R4).
#:
#: Au-dela, la cadence nominale ne decrit plus le flux et tout lot produit
#: serait silencieusement faux. La valeur n'est **pas** adossee a une mesure
#: sur corpus reel: le corpus du `TEST_PLAN.md` ne contient aujourd'hui aucune
#: source VFR (question ouverte 6 de la story). A rouvrir si des faux positifs
#: apparaissent sur des sources CFR legitimes.
VFR_RELATIVE_TOLERANCE = 0.01

#: `-count_frames` decode le flux entier: il est paye seulement quand
#: `nb_frames` ne recoupe pas la duree, et il peut etre long sur un rush long.
COUNT_FRAMES_TIMEOUT_SECONDS = 1800


class ExtractionInputError(RuntimeError):
    """Entree invalide ou source inexploitable. Mappe vers le code de sortie 1.

    Meme role que `cli.PocInputError` pour les commandes POC: elle porte un
    message actionnable en francais et ne remonte jamais en trace Python
    devant un operateur.
    """


# --------------------------------------------------------------------------
# Codes de sortie de `extract`, et la table qui les commande
# --------------------------------------------------------------------------

#: Les cinq codes de sortie dont `extract` est proprietaire. Ils vivaient dans
#: `cli.py` seul jusqu'a la story 11.4 (`EPIC11-ARB-75`).
#:
#: * `0` succes;
#: * `1` erreur d'entree ou de traitement;
#: * `2` prerequis externe absent -- **les deux** classes distinctes
#:   `ffmpeg_utils.FfmpegNotFoundError` et `video_metadata.FfprobeNotFoundError`;
#: * `3` refus de confirmation (story 3.3). Ce chemin n'affiche aucun prefixe
#:   `Erreur:`: rien n'a echoue, l'operateur a simplement dit non;
#: * `130` interruption clavier, convention shell (128 + SIGINT).
CODE_SUCCES = 0
CODE_ERREUR = 1
CODE_PREREQUIS_ABSENT = 2
CODE_REFUS = 3
CODE_INTERRUPTION = 130

#: La table exception -> code de sortie de `extract`, **seule source de verite**
#: depuis la story 11.4 (`EPIC11-ARB-75`).
#:
#: Pourquoi elle est ici et non dans `cli.py`. La TUI a besoin du meme code
#: retour -- son AC exige qu'il soit identique -- et elle a interdiction
#: d'importer `cli.py` (`tui/palier_projet.py`: « Ce module appelle io/, jamais
#: cli.py »). L'autre option etait de dupliquer la table avec un test
#: symetrique: elle laisse deux tables vraies au meme moment, et un test
#: symetrique ne rougit qu'**apres** qu'on a diverge.
#:
#: **L'ordre est semantique et reproduit celui de la pile d'`except`** qu'elle
#: remplace: la recherche rend la premiere entree qui correspond. Deux entrees
#: peuvent attraper la meme exception -- une classe qui heriterait de deux
#: d'entre elles, et surtout le filet `OSError` en derniere position, qui ne
#: doit jamais preceder une entree nommee. Reordonner cette table change donc
#: des codes de sortie: c'est une modification de contrat, pas de presentation.
#:
#: `KeyboardInterrupt` y figure bien qu'elle derive de `BaseException` et non
#: d'`Exception`: c'est l'appelant qui doit l'attraper a part, la table se
#: contente de dire quel code elle vaut.
CODES_DE_SORTIE: tuple[tuple[type[BaseException], int], ...] = (
    (ExtractionInputError, CODE_ERREUR),
    (NamingError, CODE_ERREUR),
    # Hierarchie complete de la story 3.2 (upsampling, source vide, duree
    # incoherente, cadence invalide, timecode de depart invalide): jamais
    # laissee remonter en trace Python.
    (FrameSelectionError, CODE_ERREUR),
    (source_confirmation.SourceReportError, CODE_ERREUR),
    (ffmpeg_utils.FfmpegNotFoundError, CODE_PREREQUIS_ABSENT),
    (video_metadata.FfprobeNotFoundError, CODE_PREREQUIS_ABSENT),
    (video_metadata.FfprobeError, CODE_ERREUR),
    (ffmpeg_utils.FrameExtractionError, CODE_ERREUR),
    (ExtractionPersistenceError, CODE_ERREUR),
    (ValidationError, CODE_ERREUR),
    (KeyboardInterrupt, CODE_INTERRUPTION),
    # Filet, et **toujours en dernier**: disque plein, projet en lecture seule,
    # `logs/` ou `frames/` non inscriptible. Des pannes ordinaires qui
    # remontaient en trace Python devant l'operateur (revue du 2026-08-05).
    (OSError, CODE_ERREUR),
)


def correspondance_de_sortie(
    exception: BaseException,
) -> tuple[type[BaseException], int] | None:
    """Rendre l'entree de `CODES_DE_SORTIE` qui attrape `exception`, ou `None`.

    C'est la forme complete: elle dit **quelle** entree a repondu, pas
    seulement le code. L'appelant en a besoin quand il traite une entree
    autrement que les autres -- la CLI reformule le message du filet `OSError`
    et n'a aucun moyen de savoir, du seul code `1`, si c'est ce filet ou une
    entree nommee qui a repondu.

    Rend `None` pour ce que la table ne nomme pas: l'appelant **relaie** alors
    l'exception au lieu de la deguiser en refus metier. Une pile d'`except`
    nommee ne les attrapait pas non plus.
    """
    for classe, code in CODES_DE_SORTIE:
        if isinstance(exception, classe):
            return classe, code
    return None


def code_de_sortie(exception: BaseException) -> int | None:
    """Le code de sortie de `extract` pour `exception`, ou `None` si inconnue."""
    correspondance = correspondance_de_sortie(exception)
    return None if correspondance is None else correspondance[1]


@dataclass(frozen=True)
class SourceQualification:
    """Ce que `extract` retient du probe ffprobe pour piloter la selection."""

    fps_source: Fraction
    stream_duration_seconds: float | None
    declared_frame_count: int | None
    start_timecode: str | None
    avg_frame_rate: Fraction | None

    @property
    def cadence_corroboree(self) -> bool:
        """La cadence nominale a-t-elle pu etre recoupee par une autre grandeur ?

        Deux garde-fous protegent contre une cadence variable: l'ecart entre
        `avg_frame_rate` et `r_frame_rate`, et la coherence entre le cardinal
        d'images et la duree du flux. Sur un conteneur Matroska, ffprobe
        n'expose **ni** la duree du flux **ni** `nb_frames`, et rend
        `avg_frame_rate` egal a `r_frame_rate` meme sur une source a cadence
        reellement variable: les deux gardes tombent alors ensemble, pour la
        meme cause.

        Reproduit a la revue du 2026-08-05 sur un rush passant de 25 a 10 im/s:
        `extract` rendait un succes, declarait le lot conforme, persistait
        `fps_source: 25.0` la ou la cadence moyenne reelle etait 17,5, et les
        timecodes -- qui sont les noms de fichiers et voyagent dans le payload
        QR -- derivaient de pres d'une seconde.

        Depuis ARB-6 (`decisions-2026-08-05.md`), une cadence non corroborable
        **refuse** l'extraction: Egan a tranche que le cout d'un refus, reparable
        par un reencodage, est preferable a celui d'un lot silencieusement faux
        qui se propage jusqu'au PDF et au QR code.
        """
        return self.stream_duration_seconds is not None or self.declared_frame_count is not None


@dataclass(frozen=True)
class ExtractionOutcome:
    """Resultat complet d'une execution de `extract`.

    `granted=False` designe un refus de confirmation (story 3.3): rien n'a ete
    ecrit, aucun dossier de lot n'a ete cree, et l'appelant renvoie le code de
    sortie `3` sans passer par le chemin d'erreur.
    """

    granted: bool
    message: str
    project_id: str | None = None
    rush_id: str | None = None
    lot_id: str | None = None
    frames_dir: Path | None = None
    frames_dir_relative: str | None = None
    written_frame_count: int = 0
    output_bit_depth: int = EXTRACTION_OUTPUT_BIT_DEPTH
    selection: FrameSelection | None = None
    persisted: PersistedExtraction | None = None


# --------------------------------------------------------------------------
# Qualification de la source
# --------------------------------------------------------------------------


def _parse_probe_rate(raw: Any) -> Fraction | None:
    """Cadence ffprobe `"num/den"` -> `Fraction`, ou `None` si inexploitable.

    ffprobe rend `0/0` pour une cadence indeterminee: `Fraction` leve alors
    `ZeroDivisionError`, cas volontairement traite comme une absence et non
    comme une erreur de programmation.
    """
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        value = Fraction(text)
    except (ValueError, ZeroDivisionError):
        return None
    return value if value > 0 else None


def _coerce_positive_int(raw: Any) -> int | None:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _coerce_positive_float(raw: Any) -> float | None:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError):
        return None
    if value != value or value in (float("inf"), float("-inf")) or value <= 0:
        return None
    return value


def _source_parent_name(video_path: Path) -> str | None:
    """Nom du dossier contenant le rush, ou `None` s'il n'y en a pas d'utile.

    **Nom seul, jamais le chemin** (ARB-9, `decisions-2026-08-05.md`). Egan
    voulait tracer le chemin d'acces original pour distinguer deux rushs
    homonymes; le contrat v2 interdit tout chemin absolu dans le manifest
    (`io/manifest._check_no_absolute_paths`), parce qu'un chemin machine ne veut
    rien dire sur le poste qui recevra le projet -- ce qui est la raison d'etre
    de tout l'Epic 2. Le nom du dossier parent est un **fragment relatif**: il
    porte l'information de provenance (`A-CAM`, `B-CAM`) sans nommer ni machine
    ni utilisateur.
    """
    parent = video_path.resolve().parent.name
    return parent or None


#: Les criteres qui font l'identite d'un rush, dans l'ordre normatif ou un
#: ecran doit les montrer. **Cet ensemble est ferme et se mesure par egalite**
#: (`tests/unit/test_identite_rush.py`, section C.1): un critere ajoute en
#: silence rougit, la ou une mesure d'appartenance laisserait passer toute
#: divergence supplementaire.
#:
#: **`EPIC11-ARB-230` (Egan, 2026-09-05) : le dossier parent n'en fait plus
#: partie.** Verbatim de la question qui l'ouvre : « si le timecode de debut,
#: la duree, la cadence et le nom coincident alors il y a "conflit" puisque
#: c'est le meme rush ». Les quatre criteres d'identite sont donc le **nom**,
#: la **duree**, la **cadence** et le **timecode initial**, et eux seuls -- le
#: nom etant la cle `rush_id` sous laquelle la comparaison se fait, ce tuple
#: n'en porte que les **trois** autres. Tous identiques : c'est le meme rush,
#: quel que soit le dossier.
#:
#: Ce que le retrait ferme, mesure de bout en bout avant l'arbitrage : deux
#: copies du meme fichier dans `A/prise01.mp4` et `B/prise01.mp4` etaient
#: declarees `prise01` puis `prise01-B`, **sans une question**, alors que les
#: quatre criteres coincidaient (26 frames, 25/1, 00:00:00:00). Le dossier
#: seul suffisait a lever une divergence, que `_identite_du_rush` resolvait en
#: silence par un suffixe.
#:
#: `source_parent` **reste** sur :class:`CriteresIdentiteRush` -- il nomme la
#: provenance a l'ecran --, et il reste le **separateur de dernier recours**
#: du regime degrade decrit par :data:`CRITERE_DE_DERNIER_RECOURS`. Ce qu'il a
#: cesse d'etre est un critere d'**identite**.
#:
#: **Et il ne fournit plus le suffixe non plus**, depuis `EPIC11-ARB-233`
#: (2026-09-05) : :func:`disambiguated_rush_id` pose un RANG. Le dossier
#: garde donc exactement UN role, celui de dernier recours, la ou il en avait
#: deux -- et le role qu'il perd est celui ou il ne distinguait rien, deux
#: homonymes de deux tournages differents partageant leur dossier `hd/`.
#:
#: Note 5 de la relecture d'Egan du 2026-09-01, verbatim: « pas si leurs
#: timecodes ne correspondent pas EXACTEMENT (duree, base, timecode initial).
#: Ce serait tres rare. Il faut ajouter ces criteres dans la comparaison, et
#: les stocker... ». Les trois criteres qu'elle nomme sont exactement ceux qui
#: restent:
#:
#: * `fps_source_exact` -- la **base de timecode**. Elle n'a pas de champ
#:   propre sur le rush, et n'en a pas besoin: `frame_selection` pose
#:   `timecode_base = TIMECODE_BASE` (`"source"`) et
#:   `timecode_base_fps = fps_source_exact`, donc la base de timecode **est**
#:   la cadence source, que `rushes[].fps_source_exact` porte deja. Ecrire la
#:   meme valeur sous deux noms dans un meme manifeste ouvrirait une
#:   divergence que rien ne mesurerait; l'egalite, elle, est mesuree
#:   (section C.7 du banc), et si elle tombe un jour ce banc rougit;
#: * `source_frame_count` -- la **duree**, en cardinal de frames et jamais en
#:   secondes de flux. C'est le vocabulaire que `lots[].source_frame_count` et
#:   `relink.CRITERES_IDENTITE_RELINK` emploient deja, et c'est le cardinal qui
#:   commande une extraction: deux flux dont les durees flottantes different a
#:   la troisieme decimale portent le meme cardinal et produisent le meme lot;
#: * `source_start_timecode` -- le **timecode initial**, seul des trois que le
#:   rush portait deja.
#:
#: `source_name` n'y figure pas, et c'est delibere: `rush_id` en derive
#: (`normalize_identifier(video_path.stem)`), donc deux entrees comparees sous
#: le meme `rush_id` portent toujours le meme nom de base. Ce serait un critere
#: constamment concordant, c'est-a-dire une preuve qui ne prouve rien.
CRITERES_IDENTITE_RUSH: tuple[str, ...] = (
    "fps_source_exact",
    "source_frame_count",
    "source_start_timecode",
)

#: Le dossier parent : **separateur de dernier recours, jamais critere
#: d'identite** (`EPIC11-ARB-230`).
#:
#: Il ne pese que dans le **regime degrade** de :func:`rush_identity_conflict`
#: -- celui d'un appelant qui ne peut RIEN mesurer, donc qui ne peut pas
#: appliquer `ARB-230`. Il y en a un seul dans le depot, et il ne peut pas
#: cesser de l'etre : :func:`run_extraction`, a qui l'AC 1.1 de la story 11.4c
#: (`EPIC11-ARB-83`) interdit de sonder la source **avant** la transition
#: d'etat du lot -- or `lot_id` derive du `rush_id` que cette garde arbitre.
#:
#: Sans ce dernier recours, `extract` cesserait de separer
#: `A-CAM/prise01.mov` de `B-CAM/prise01.mov` et le second **ecraserait**
#: l'entree du premier : exactement la destruction qu'`EPIC11-ARB-9` a fermee
#: le 2026-08-05, et que `test_arb9_deux_rushs_homonymes_ne_s_ecrasent_plus`
#: mesure encore. `EPIC11-ARB-230` subordonne `ARB-9`, il ne l'annule pas.
#:
#: **Ce n'est donc pas une exception PAR APPELANT mais un regime, et il se
#: nomme** : quand la mesure existe, elle tranche seule et le dossier ne pese
#: rien ; quand elle n'existe pas, le verdict serait vide et le dossier est
#: tout ce qui reste. Amener `extract` sous `ARB-230` demande de resoudre la
#: tension avec `ARB-83` -- c'est en dette dans `deferred-work.md`, pas ici.
CRITERE_DE_DERNIER_RECOURS: str = "source_parent"


@dataclass(frozen=True)
class CriteresIdentiteRush:
    """Les quatre criteres d'identite d'un rush, chacun present ou **absent**.

    `None` veut dire « rien n'a ete dit », jamais « zero » ni « chaine vide »:
    c'est la meme regle que `source_confirmation._normalize_probe_value`
    (« Sentinelle ffprobe -> `None`, sans jamais substituer de valeur »).
    Une duree absente stockee `0` affirmerait un flux vide la ou la source
    n'a rien dit, et un timecode absent stocke `00:00:00:00` affirmerait une
    source taguee a l'heure zero.
    """

    source_parent: str | None = None
    fps_source_exact: str | None = None
    source_frame_count: int | None = None
    source_start_timecode: str | None = None

    @classmethod
    def declares(cls, entree: Mapping[str, Any] | None) -> "CriteresIdentiteRush":
        """Lire les criteres **declares** dans une entree `rushes[]`.

        Toute valeur inexploitable -- cle absente, chaine vide, cardinal nul ou
        negatif (le schema pose `minimum: 1`), type inattendu -- se lit comme
        une absence. Elle ne se lit **jamais** comme une valeur par defaut:
        un manifeste ancien ou corrompu ne doit pas faire diverger un rush,
        il doit rendre le critere non verifiable.
        """
        entree = entree or {}
        return cls(
            source_parent=_texte_ou_none(entree.get("source_parent")),
            fps_source_exact=_texte_ou_none(entree.get("fps_source_exact")),
            source_frame_count=_coerce_positive_int(entree.get("source_frame_count")),
            source_start_timecode=_texte_ou_none(entree.get("source_start_timecode")),
        )

    @classmethod
    def mesures(
        cls,
        *,
        source_parent: str | None,
        fps_source: Fraction | float | str,
        source_frame_count: int | None,
        source_start_timecode: str | None,
    ) -> "CriteresIdentiteRush":
        """Les criteres **mesures** sur le fichier, normalises pour comparaison.

        Les trois grandeurs viennent du **seul** chemin de sondage du depot --
        `video_metadata.probe_media` -> `qualify_source` ->
        `resolve_source_frame_count` --, celui que `relink.probe_reel` et
        `tui.atelier_extraction_ecriture.sonder_la_source` empruntent deja.
        Cette fabrique n'en ouvre pas un second: elle **normalise**, elle ne
        mesure rien.

        La cadence passe par `codec_profiles.exact_frame_rate`, la **meme**
        fonction que `io.extraction_manifest._build_rush_entry` emploie pour
        ecrire: sans cela `Fraction(25, 1)` et la chaine `"25/1"` du manifeste
        ne se compareraient jamais egales.

        Scalaires plutot qu'un objet, et c'est delibere: les deux porteurs du
        depot ne portent pas les memes noms de champ
        (`SourceQualification.start_timecode` contre
        `tui.atelier_extraction.SourceSondee.source_start_timecode`), et exiger
        l'un des deux forcerait l'autre appelant a reconstruire un objet qu'il
        n'a pas. `depuis_la_qualification` reste la porte typee pour le
        premier.
        """
        return cls(
            source_parent=_texte_ou_none(source_parent),
            fps_source_exact=exact_frame_rate(fps_source),
            source_frame_count=_coerce_positive_int(source_frame_count),
            source_start_timecode=_texte_ou_none(source_start_timecode),
        )

    @classmethod
    def depuis_la_qualification(
        cls,
        *,
        source_parent: str | None,
        qualification: SourceQualification,
        source_frame_count: int | None,
    ) -> "CriteresIdentiteRush":
        """La porte **typee** pour un appelant qui tient une `SourceQualification`.

        C'est le cas d'`extract` et de `relink`. Elle ne fait que nommer les
        champs: toute la normalisation vit dans `mesures`, en un seul endroit.
        """
        return cls.mesures(
            source_parent=source_parent,
            fps_source=qualification.fps_source,
            source_frame_count=source_frame_count,
            source_start_timecode=qualification.start_timecode,
        )


@dataclass(frozen=True)
class ConflitIdentiteRush:
    """Le verdict de la comparaison, avec la **preuve** des deux cotes.

    Note 2 d'Egan, verbatim: « montrer la preuve : le nom et les infos
    techniques communes ». Un ecran de conflit n'a pas seulement besoin de
    savoir qu'il y a conflit: il doit pouvoir montrer ce qui rapproche les
    deux rushs autant que ce qui les separe. Les trois listes partitionnent
    donc `CRITERES_IDENTITE_RUSH` exactement -- ni recouvrement, ni oubli.
    """

    #: L'entree `rushes[]` deja declaree, copiee.
    entree: Mapping[str, Any]
    declares: CriteresIdentiteRush
    mesures: CriteresIdentiteRush
    #: Compares des deux cotes et **differents**: ce sont eux qui font conflit.
    divergents: tuple[str, ...]
    #: Compares des deux cotes et egaux: la preuve que c'est le meme rush.
    concordants: tuple[str, ...]
    #: Absents d'au moins un cote: **dits**, jamais comptes comme divergence.
    non_verifiables: tuple[str, ...]

    @property
    def en_conflit(self) -> bool:
        return bool(self.divergents)


def _texte_ou_none(brut: Any) -> str | None:
    """Chaine non vide, ou `None`. Aucune substitution, jamais."""
    if brut is None or isinstance(brut, bool):
        return None
    texte = str(brut).strip()
    return texte or None


def comparer_identite_rush(
    declares: CriteresIdentiteRush, mesures: CriteresIdentiteRush
) -> ConflitIdentiteRush:
    """Confronter criteres declares et criteres mesures, critere par critere.

    Trois cases, et un critere tombe dans exactement une:

    * **divergent** -- present des deux cotes et different. Egan demande une
      correspondance « EXACTEMENT »: aucune tolerance, pas meme d'une frame.
      La tolerance de `relink` (`TOLERANCE_DUREE_RELINK_FRAMES`) repond a une
      autre question -- « ce fichier est-il celui que je cherche ? » -- ou un
      faux negatif coute un relink manuel; ici un faux positif ferait fusionner
      deux rushs distincts, ce qui detruit;
    * **concordant** -- present des deux cotes et egal;
    * **non verifiable** -- absent d'au moins un cote. Meme doctrine que
      `relink.ReferenceIdentite.criteres_verifiables`: ce qui n'est pas
      comparable est **dit**, jamais compte comme une divergence. Sans cela,
      tout rush declare avant cette story -- qui ne porte aucun cardinal --
      deviendrait conflictuel du jour au lendemain.

    Fonction **pure**: elle n'ouvre aucun fichier et n'impose aucun ordre
    d'appel. C'est ce qui permet a l'ecran de conflit de la story 11.4e de
    l'appeler apres son propre probe, et a `run_extraction` de l'appeler avant
    le sien (voir la note d'ordre dans `run_extraction`).
    """
    divergents: list[str] = []
    concordants: list[str] = []
    non_verifiables: list[str] = []
    for critere in CRITERES_IDENTITE_RUSH:
        declare = getattr(declares, critere)
        mesure = getattr(mesures, critere)
        if declare is None or mesure is None:
            non_verifiables.append(critere)
        elif declare != mesure:
            divergents.append(critere)
        else:
            concordants.append(critere)
    return ConflitIdentiteRush(
        entree={},
        declares=declares,
        mesures=mesures,
        divergents=tuple(divergents),
        concordants=tuple(concordants),
        non_verifiables=tuple(non_verifiables),
    )


def rush_identity_conflict(
    existing_rushes: Any,
    rush_id: str,
    source_parent: str | None,
    *,
    mesures: CriteresIdentiteRush | None = None,
) -> ConflitIdentiteRush | None:
    """L'entree deja declaree sous ce `rush_id` decrit-elle un **autre** rush ?

    Rend le verdict de conflit, ou `None` s'il n'y en a pas. Deux rushs
    homonymes dans deux dossiers differents -- `A-CAM/prise01.mov` et
    `B-CAM/prise01.mov`, cas de tournage multicamera parfaitement ordinaire --
    etaient le **meme** rush pour l'outil: le second ecrasait le premier et le
    message d'erreur poussait vers `--overwrite`, c'est-a-dire vers la
    destruction (revue du 2026-08-05).

    **`EPIC11-ARB-230`: le dossier parent ne separe plus.** Deux rushs
    homonymes venus de deux dossiers differents ne sont plus, par ce seul
    fait, deux rushs distincts. Ce qui les separe est une divergence
    **technique** -- cadence, duree, timecode initial --, et rien d'autre.
    Deux copies du meme fichier dans `A/` et `B/` rendent donc `None`: c'est
    le meme rush, l'appelant a un conflit a poser a l'operateur.

    `mesures` porte les criteres mesures sur le fichier
    (`CriteresIdentiteRush.mesures`). **Il est optionnel, et son absence n'est
    pas un oubli**: elle declare que l'appelant ne peut RIEN mesurer, ce qui
    est exactement le regime de `run_extraction`, ou la garde precede le probe
    pour une raison mesuree (voir la note d'ordre dans `run_extraction`).

    **Ce regime degrade garde le dossier comme separateur de DERNIER RECOURS**
    (:data:`CRITERE_DE_DERNIER_RECOURS`), et il le faut: sans mesure, les
    trois criteres d'identite sont non verifiables, le verdict serait
    **toujours** vide, et `extract` cesserait de separer `A-CAM/prise01.mov`
    de `B-CAM/prise01.mov` -- le second ecraserait l'entree du premier, ce
    qu'`EPIC11-ARB-9` a ferme le 2026-08-05. `ARB-230` **subordonne** `ARB-9`,
    il ne l'annule pas: le dossier ne pese plus rien des que la mesure existe,
    et il est tout ce qui reste quand elle n'existe pas.

    L'appariement se fait par `rush_id`, jamais par position, et la boucle
    s'arrete sur la **premiere** entree qui porte ce `rush_id` -- il n'y en a
    qu'une, `rush_id` etant la cle de la liste.
    """
    dossier_mesure = _texte_ou_none(source_parent)
    for rush in existing_rushes or []:
        if not isinstance(rush, Mapping) or rush.get("rush_id") != rush_id:
            continue
        declares = CriteresIdentiteRush.declares(rush)
        verdict = comparer_identite_rush(
            declares,
            mesures
            if mesures is not None
            else CriteresIdentiteRush(source_parent=dossier_mesure),
        )
        divergents = verdict.divergents
        if not divergents and mesures is None:
            # Regime degrade, et **lui seul**: rien de technique n'etait
            # comparable, donc le verdict ci-dessus ne pouvait pas etre autre
            # chose que vide. Le dossier reprend alors son role d'`ARB-9`.
            # Sous `mesures`, cette branche est morte -- c'est ce que mesure
            # le volet symetrique de la section C.4 du banc d'identite.
            if (
                declares.source_parent is not None
                and dossier_mesure is not None
                and declares.source_parent != dossier_mesure
            ):
                divergents = (CRITERE_DE_DERNIER_RECOURS,)
        if not divergents:
            return None
        return ConflitIdentiteRush(
            entree=dict(rush),
            declares=verdict.declares,
            mesures=verdict.mesures,
            divergents=divergents,
            concordants=verdict.concordants,
            non_verifiables=verdict.non_verifiables,
        )
    return None


class RangsDeDesambiguisationEpuises(ExtractionInputError):
    """Les 98 rangs d'une famille d'homonymes sont tous consommes.

    **Nommee** plutot que rabattue sur :class:`ExtractionInputError` nue :
    c'est le SEUL regime ou `--force-distinct` ne peut plus rien rendre, et
    l'appelant qui redige un refus a issues (`declaration_de_rush`) doit
    pouvoir le reconnaitre sans lire le texte du message.
    """


def rangs_de_desambiguisation_employes(
    rushes: Any, rush_id: str
) -> tuple[int, ...]:
    """Les rangs deja employes par la famille d'homonymes de `rush_id`.

    Le rang 1 est celui du rush qui ne porte aucun fragment ; les suivants sont
    lus du nom ecrit, par :func:`io.naming.rang_de_desambiguisation`. Tout ce
    qui n'appartient pas a la famille est ignore -- dont les
    `<rush_id>-<dossier>` ecrits AVANT `EPIC11-ARB-233`, qui occupent un nom
    sans occuper de rang.

    **Le manifeste est la seule source consultee, et c'est une difference avec
    `scan_ingest.resolve_scan_version_rank`**, qui interroge le disque en plus :
    un rush n'a pas de dossier a lui, il n'existe que par son entree. Rien
    d'autre ne pourrait dire qu'un rang a servi.
    """
    rangs: list[int] = []
    for rush in rushes or []:
        if not isinstance(rush, Mapping):
            continue
        nom = rush.get("rush_id")
        if not isinstance(nom, str):
            continue
        rang = rang_de_desambiguisation(nom, rush_id)
        if rang is not None:
            rangs.append(rang)
    return tuple(rangs)


def disambiguated_rush_id(rush_id: str, rushes: Any) -> str:
    """`rush_id` suffixe par un RANG, pour lever une homonymie (`EPIC11-ARB-233`).

    **Ce que le rang remplace, et pourquoi** (Egan, 2026-09-05). Le suffixe
    valait le **dossier immediat** du fichier, et deux defauts l'ont fait
    tomber, tous deux mesures sur le terrain :

    * il ne distinguait rien. `03_tournage_mai/hd/prise01.mov` et
      `04_tournage_juin/hd/prise01.mov` rendaient `prise01` puis `prise01-hd`
      -- `hd` etant le dossier que les deux ont en COMMUN ;
    * il **bloquait au troisieme**. Un `prise01.mov` dans un troisieme `hd/`
      n'avait plus aucune issue qui ecrit : le suffixe etant deterministe et
      deja pris, il ne restait qu'a renommer la source a la main. C'est mot
      pour mot la corvee manuelle qu'`EPIC11-ARB-104` refuse.

    Le rang ferme le second **par construction** plutot que par un cas
    particulier : tant que la borne n'est pas atteinte, un rang libre existe.

    **La regle des rangs n'est pas recopiee ici** (`EPIC11-ARB-108`, regle
    `versionnage-mecanisme-unique` du CLAUDE.md) : `io.version_ranks` la tient
    pour tous les objets et c'est lui qui rend la ligne d'eau et le rang
    suivant. Ce module ne fournit que ses donnees.

    **Ce qui n'est PAS tenu, dit plutot que tu** : la ligne d'eau est DEDUITE
    des rangs encore employes, elle n'est persistee nulle part. Retirer le
    dernier homonyme d'une famille rend donc son rang **par defaut**, la ou
    `EPIC11-ARB-92` veut qu'un rang se consomme et ne se rende que sur demande.
    Poser un champ de ligne d'eau (comme `lot_version_watermarks` et
    `scan_version_watermarks`) ferait du rush un sixieme objet versionnable, ce
    qu'`EPIC11-ARB-233` ne tranche pas : c'est en dette, pas en oubli.
    """
    rangs = rangs_de_desambiguisation_employes(rushes, rush_id)
    ligne = version_ranks.ligne_d_eau(None, rangs)
    rang = version_ranks.prochain_rang(ligne)
    if rang > VERSION_RANK_MAX:
        raise RangsDeDesambiguisationEpuises(
            version_ranks.refus_de_rangs_epuises(
                "rush homonyme",
                rush_id,
                # Deux issues qui ECRIVENT, et non une corvee et un mur
                # (`EPIC11-ARB-89`). La premiere libere reellement un rang --
                # la ligne d'eau etant deduite, retirer le dernier homonyme
                # rend son rang ; la seconde sort de la famille pour de bon.
                "Deux issues: retirer l'un des homonymes de ce projet "
                "(`mmu project remove --project <projet> --rush <rush_id> "
                "--confirmer`), ce qui rend son rang; ou renommer le fichier "
                "source pour lui donner un identifiant qui ne soit plus un "
                "homonyme.",
            )
        )
    return normalize_identifier(
        format_rang_de_desambiguisation(rush_id, rang),
        label="le nom du fichier source et son rang d'homonyme",
    )


def upsampling_refusal_message(fps_target: Any, fps_source_exact: Fraction) -> str:
    """Message unique de refus du sur-echantillonnage (ARB-12).

    `extract` et `previz` refusent la meme chose et doivent en dire autant:
    un utilisateur qui essaie une cadence en previsualisation puis en
    extraction doit lire la **meme phrase**. Les deux gardes vivaient dans deux
    modules et rendaient deux messages differents, alors que la docstring de la
    story 3.6 annoncait l'inverse (`decisions-2026-08-05.md`, ARB-12).
    """
    return (
        f"Cadence cible {fps_target} im/s superieure a la cadence source "
        f"{float(fps_source_exact):g} im/s: le sur-echantillonnage exigerait de "
        "dupliquer ou d'interpoler des frames, ce que cet outil ne fait "
        f"jamais. Cadence cible maximale admissible: {float(fps_source_exact):g} "
        "im/s."
    )


def qualify_source(probe: Mapping[str, Any]) -> SourceQualification:
    """Lire et **qualifier** la source, en refusant toute cadence non fiable.

    Critere de refus (AC 8), explicite et teste sur fixtures JSON ffprobe:

    * `r_frame_rate` absent, nul, illisible ou `0/0` -- la cadence nominale
      n'existe pas, donc aucune selection deterministe n'est definissable;
    * ecart relatif entre `avg_frame_rate` et `r_frame_rate` superieur a
      `VFR_RELATIVE_TOLERANCE` -- signature usuelle d'une cadence variable.

    La cadence transmise au noyau de selection est **`r_frame_rate`** (cadence
    nominale, celle que `video_metadata.TECHNICAL_METADATA_MATRIX["frame_rate"]`
    utilise deja), jamais `avg_frame_rate`.

    La duree lue est celle du **flux video** (`streams[].duration`), jamais
    celle du conteneur (`format.duration`): cette derniere integre couramment
    la piste audio, une edit list ou un padding de fin, et transformerait la
    garde de coherence du noyau en faux positif sur une source CFR saine.
    """
    try:
        stream = video_metadata._video_stream(dict(probe))
    except video_metadata.FfprobeError as exc:
        raise ExtractionInputError(
            f"Aucun flux video dans le fichier source: extraction impossible ({exc})."
        ) from exc

    fps_source = _parse_probe_rate(stream.get("r_frame_rate"))
    if fps_source is None:
        raise ExtractionInputError(
            "Cadence source indeterminee: ffprobe ne declare pas de 'r_frame_rate' "
            f"exploitable (lu: {stream.get('r_frame_rate')!r}). Une source a cadence "
            "variable ou sans cadence nominale ne permet aucune selection "
            "deterministe, et produirait un lot silencieusement faux. Re-encoder le "
            "rush en cadence constante avant extraction."
        )

    avg_frame_rate = _parse_probe_rate(stream.get("avg_frame_rate"))
    if avg_frame_rate is not None:
        deviation = abs(avg_frame_rate - fps_source) / fps_source
        if deviation > Fraction(VFR_RELATIVE_TOLERANCE).limit_denominator(1000000):
            raise ExtractionInputError(
                "Source a cadence variable (VFR) refusee: 'avg_frame_rate' "
                f"({avg_frame_rate}, soit {float(avg_frame_rate):.6g} im/s) s'ecarte de "
                f"'r_frame_rate' ({fps_source}, soit {float(fps_source):.6g} im/s) de "
                f"{float(deviation) * 100:.3f} %, au-dela de la tolerance de "
                f"{VFR_RELATIVE_TOLERANCE * 100:.3f} %. Une cadence variable n'a pas de "
                "cadence source unique: le lot extrait serait silencieusement faux. "
                "Re-encoder le rush en cadence constante avant extraction."
            )

    return SourceQualification(
        fps_source=fps_source,
        stream_duration_seconds=_coerce_positive_float(stream.get("duration")),
        declared_frame_count=_coerce_positive_int(stream.get("nb_frames")),
        start_timecode=video_metadata._find_timecode(dict(probe)),
        avg_frame_rate=avg_frame_rate,
    )


def count_frames_exact(
    video_path: str | Path, *, ffprobe_bin: str = "ffprobe"
) -> int | None:
    """Compter exactement les frames du flux video, ou rendre `None`.

    Paye un decodage complet (`-count_frames`). N'est appele que lorsque
    `nb_frames` ne recoupe pas `duration * r_frame_rate`, jamais
    systematiquement.
    """
    if shutil.which(ffprobe_bin) is None:
        raise video_metadata.FfprobeNotFoundError(
            f"Binaire ffprobe introuvable dans le PATH: {ffprobe_bin!r}"
        )
    try:
        result = subprocess.run(
            [
                ffprobe_bin,
                "-v", "error",
                "-count_frames",
                "-select_streams", "v:0",
                "-show_entries", "stream=nb_read_frames",
                "-of", "json",
                "--",
                str(video_path),
            ],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=COUNT_FRAMES_TIMEOUT_SECONDS,
            check=True,
        )
        payload = json.loads(result.stdout)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return None

    for stream in payload.get("streams") or []:
        counted = _coerce_positive_int(stream.get("nb_read_frames"))
        if counted is not None:
            return counted
    return None


def cardinal_corrobore(qualification: SourceQualification) -> int | None:
    """Le cardinal de frames que le conteneur declare ET que la duree confirme.

    **Corps extrait de `resolve_source_frame_count` a la liaison du 2026-09-05
    (story 11.4e, lot A), jamais reecrit.** Il y a maintenant deux appelants du
    meme critere -- l'extraction, qui a le droit de payer un `-count_frames`
    quand la corroboration echoue, et la DECLARATION d'un rush, qui ne l'a pas
    (AC 1.5 : `ffprobe` appele **exactement une fois**). Une seconde redaction
    du « a une frame pres » divergerait, et l'ecart ne se verrait que sur un
    manifeste deja ecrit -- exactement ce que la sous-tache A2 interdit pour la
    derivation du `rush_id`.

    Rend `None` -- jamais `0`, jamais une estimation -- quand `nb_frames` est
    absent, quand la duree du flux l'est, ou quand les deux se contredisent de
    plus d'une frame. C'est une **absence**, au sens de
    `CriteresIdentiteRush.declares` : « rien n'a ete dit », a distinguer d'un
    cardinal mesure.

    Fonction pure : elle ne sonde rien et n'ouvre aucun sous-processus. C'est
    ce qui permet a la declaration de l'appeler apres son unique probe.
    """
    declared = qualification.declared_frame_count
    duration = qualification.stream_duration_seconds
    if declared is None or duration is None:
        return None
    attendu = Fraction(duration).limit_denominator(1000000) * qualification.fps_source
    if abs(Fraction(declared) - attendu) <= 1:
        return declared
    return None


def resolve_source_frame_count(
    video_path: str | Path,
    qualification: SourceQualification,
    *,
    ffprobe_bin: str = "ffprobe",
    logger: logging.Logger | None = None,
) -> tuple[int, bool]:
    """Etablir le cardinal de frames source, et dire s'il est exact.

    Regle imposee par la story 3.2, qui **exige** un cardinal et ne le derive
    jamais d'une duree: n'utiliser `nb_frames` que s'il recoupe
    `duration * r_frame_rate` a une frame pres; sinon payer `-count_frames`;
    si seule une estimation reste disponible, la declarer
    (`source_frame_count_is_exact=False`) plutot que de la faire passer pour
    un comptage.

    La raison est asymetrique et vaut d'etre retenue: un cardinal
    **sur-estime** fait produire a ffmpeg moins de fichiers que la selection
    n'en attend et declenche la garde de compte de l'AC 6 -- echec bruyant,
    acceptable. Un cardinal **sous-estime** tronque le lot en silence avec un
    `expected_frame_count` coherent avec les fichiers presents -- echec
    silencieux, inacceptable.
    """
    corrobore = cardinal_corrobore(qualification)
    if corrobore is not None:
        return corrobore, True

    declared = qualification.declared_frame_count
    duration = qualification.stream_duration_seconds
    expected = (
        Fraction(duration).limit_denominator(1000000) * qualification.fps_source
        if duration is not None
        else None
    )

    if logger is not None:
        logger.info(
            "Cardinal source non corrobore (nb_frames=%s, duree flux=%s s, cadence=%s): "
            "comptage exact par ffprobe -count_frames en cours",
            declared, duration, qualification.fps_source,
        )

    counted = count_frames_exact(video_path, ffprobe_bin=ffprobe_bin)
    if counted is not None:
        return counted, True

    if declared is not None:
        return declared, False
    if expected is not None:
        estimated = int(expected)
        if estimated >= 1:
            return estimated, False

    raise ExtractionInputError(
        "Cardinal de frames source indeterminable: ni 'nb_frames', ni un comptage "
        "'ffprobe -count_frames', ni la duree du flux video ne permettent de "
        "l'etablir. La selection deterministe exige un cardinal, elle ne le devine "
        "jamais."
    )


# --------------------------------------------------------------------------
# Gardes de nommage
# --------------------------------------------------------------------------


def check_fps_form_consistency(
    rush_id: str,
    fps_target: float | int,
    *,
    source_in_timecode: str | None = None,
    source_out_timecode: str | None = None,
) -> str:
    """Verifier que dossier et nom de fichier formatent le fps identiquement.

    Filet de securite en **defense en profondeur** (AC 5). Depuis l'arbitrage
    ARB-3 du 2026-08-03 (`decisions-2026-08-03.md`, decision 2),
    `project_layout.rush_dir_slug` consomme `naming.format_fps_short` comme le
    nom de fichier, donc les deux formes convergent sur toute cadence et cette
    garde ne doit plus **jamais** se declencher. Elle est conservee plutot que
    retiree: elle compare les deux formes **reellement produites**, donc une
    divergence reintroduite par un refactor futur echouerait ici, a l'entree,
    plutot que de produire un lot dont le dossier et les fichiers se
    contredisent.

    Avant cet arbitrage, une cadence non entiere donnait `rush_12.5` contre
    `12p5`, et le point violait au passage le pattern `^[A-Za-z0-9_-]+$` du
    schema v2.

    Depuis la story 3.7 la garde connait les **bornes**, et retire leur
    condensat avant de comparer. Sans cela elle comparerait `3-a1b2c3d4` a `3`
    et refuserait **toute** extraction bornee avant meme le probe, sur un motif
    sans aucun rapport avec la demande de l'operateur (AC 7). Les bornes ne
    sont transmises a `rush_dir_slug` que lorsqu'il y en a: un appel non borne
    reste litteralement l'appel d'avant cette story.
    """
    bornes = (
        {
            "source_in_timecode": source_in_timecode,
            "source_out_timecode": source_out_timecode,
        }
        if source_in_timecode is not None or source_out_timecode is not None
        else {}
    )
    slug = project_layout.rush_dir_slug(rush_id, fps_target, **bornes)
    prefix = f"{rush_id}_"
    directory_form = slug[len(prefix):] if slug.startswith(prefix) else slug
    suffix = bounds_suffix(source_in_timecode, source_out_timecode)
    if suffix is not None:
        # Revue du 2026-08-06: le filet avait une maille manquante. Il
        # attrapait un condensat **faux** (le suffixe ne correspond pas), mais
        # laissait passer un condensat **absent** -- alors que c'est
        # precisement l'absence qui ferait pointer un extrait vers le dossier
        # de l'extraction complete, donc l'ecrasement que l'AC 6 existe pour
        # empecher. Constater la presence avant de retirer, jamais l'inverse.
        if not directory_form.endswith(f"-{suffix}"):
            raise ExtractionInputError(
                f"Extraction bornee refusee: le nom de dossier de lot "
                f"({slug!r}, via project_layout.rush_dir_slug) ne porte pas le "
                f"condensat de bornes attendu (-{suffix}, via "
                "io.naming.bounds_suffix). Sans ce condensat, cet extrait "
                "pointerait vers le dossier de l'extraction complete du meme "
                "rush a la meme cadence et l'ecraserait. Les deux fonctions "
                "doivent produire le meme fragment (ARB-3)."
            )
        directory_form = directory_form[: -len(suffix) - 1]
    filename_form = format_fps_short(fps_target)

    if directory_form != filename_form:
        raise ExtractionInputError(
            f"Cadence cible {fps_target!r} refusee: le nom de dossier de lot et le nom "
            f"des fichiers ne formatent pas la cadence de la meme facon "
            f"(dossier: {directory_form!r} via project_layout.rush_dir_slug, "
            f"fichiers: {filename_form!r} via naming.format_fps_short). Un lot dont le "
            "dossier et les fichiers se contredisent n'est pas identifiable par un "
            "tiers. Choisir une cadence cible dont les deux formes coincident."
        )
    return filename_form


def _typed_rate(value: Fraction | float | int, label: str, exact_value: Fraction) -> float:
    """Rendre la cadence en `float` pour le manifest, en verifiant l'aller-retour.

    Le schema v2 type `video.fps_source` / `fps_target` en `number`, alors que
    `FrameSelection` ne porte que des `Fraction`. La story 3.4 refuse d'ecrire
    un couple typee / exacte incoherent -- mais elle le refuserait **apres**
    une extraction potentiellement longue. La verification est donc faite ici,
    a l'entree, pour echouer avant le premier octet ecrit.
    """
    typed = float(value)
    if Fraction(exact_frame_rate(typed)) != exact_value:
        raise ExtractionInputError(
            f"Cadence {label} non representable fidelement en nombre decimal: "
            f"{exact_value} donne {typed!r}, relu comme {exact_frame_rate(typed)}. "
            "Le manifest v2 doit porter a la fois la valeur typee et la valeur "
            "exacte, et refuse de les ecrire si elles se contredisent."
        )
    return typed


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------


def _clear_existing_lot(frames_dir: Path, *, keep_temp: bool = False) -> None:
    """Retirer les fichiers d'un lot precedent, sur demande explicite seulement.

    `keep_temp` preserve le dossier temporaire d'extraction: le nettoyage a
    lieu **apres** que ffmpeg a reussi, donc le temporaire contient a ce
    moment-la les images qui vont remplacer le lot (revue du 2026-08-05).
    """
    for entry in frames_dir.iterdir():
        if entry.is_file():
            entry.unlink()
        elif entry.is_dir() and entry.name == ffmpeg_utils.EXTRACT_TEMP_DIRNAME:
            if not keep_temp:
                shutil.rmtree(entry, ignore_errors=True)


def _etat_declare_du_lot(manifest_path: Path, lot_id: str) -> Any:
    """L'etat que le manifeste declare pour `lot_id`, ou `None` s'il n'en dit rien.

    Story 11.4c, lot V1 (`EPIC11-ARB-83`). Cette lecture n'existe que pour
    permettre a `run_extraction` de faire juger la transition d'etat **avant**
    ffmpeg. Elle passe par `io.manifest.load_manifest`, **seul point d'entree
    public** de lecture d'un manifeste: `_load_existing_manifest` et `_find_lot`
    d'`io.extraction_manifest` sont prives, et les recopier ici ferait deux
    lecteurs de la meme chose.

    Rend `None` -- c'est-a-dire « aucun conflit possible » -- dans **quatre**
    cas, tous deliberes:

    * le manifeste n'existe pas encore (premier lot du projet);
    * il est illisible (JSON casse, droits). Un manifeste illisible n'est pas un
      conflit d'etat: la persistance de l'etape 6 a deja ses propres refus pour
      ce cas (`LegacyManifestError`, `ValidationError`), et les doubler ici
      changerait le message rendu a l'operateur pour une panne qui n'est pas
      celle que cette story corrige;
    * il ne declare pas ce `lot_id` (extraction neuve dans un projet existant);
    * il le declare sans `state` -- cas que `validate_lot_state_transition`
      accepte explicitement et qui doit donc rester acceptable.

    Les deux `isinstance` du corps sont de la meme famille que le deuxieme cas:
    un document dont `lots` n'est pas une liste d'objets n'est pas un manifeste,
    et il ne se juge pas ici.

    La recherche est un parcours des `lots[]` **par egalite de `lot_id`**: elle
    rend le lot vise, jamais le premier de la liste (mutant `M25` de la story
    5.7, ou les cardinaux etaient ecrits sur le mauvais lot).

    **La valeur trouvee est rendue TELLE QUELLE, sans filtre de type**, et c'est
    delibere: la persistance fait exactement `existing_lot.get("state")` et
    laisse `validate_lot_state_transition` juger. Un `state` corrompu -- une
    chaine inconnue, un entier -- doit donc etre refuse des l'amont, avec le
    meme motif (« Etat de lot courant inconnu »), et non silencieusement lu
    comme une absence d'etat: ce serait donner a l'amont et a l'aval deux avis
    differents sur le meme manifeste.
    """
    if not manifest_path.is_file():
        return None
    try:
        declare = load_manifest(manifest_path)
    except (ValueError, OSError):
        # `json.JSONDecodeError` derive de `ValueError`.
        return None
    if not isinstance(declare, Mapping):
        return None
    lots = declare.get("lots")
    if not isinstance(lots, list):
        return None
    for lot in lots:
        if isinstance(lot, Mapping) and lot.get("lot_id") == lot_id:
            return lot.get("state")
    return None


def _manifeste_charge(manifest_path: Path) -> Mapping[str, Any]:
    """Le manifeste complet a `manifest_path`, ou `{}` s'il est absent/illisible.

    Story 5.29 (`EPIC11-ARB-89`), operation « versionner »: `resolve_version_rank`
    a besoin de la liste entiere des lots, pas seulement de l'etat d'un
    `lot_id` donne comme `_etat_declare_du_lot`. Memes quatre replis
    delibarement muets que sa voisine (absent, illisible, mal forme, `lots`
    n'est pas une liste): un manifeste qui ne peut pas etre lu ici n'est pas
    un conflit de rang -- `resolve_version_rank` rendra simplement 2, et la
    persistance (etape 6) a ses propres refus pour un manifeste illisible.
    """
    if not manifest_path.is_file():
        return {}
    try:
        declare = load_manifest(manifest_path)
    except (ValueError, OSError):
        return {}
    if not isinstance(declare, Mapping):
        return {}
    return declare


def validate_extraction_inputs(
    project_dir: str | Path, video_path: str | Path, fps_target: Any
) -> None:
    """Valider les entrees de `extract` sans **rien** ecrire sur le disque.

    Extraite de `run_extraction` pour que la CLI puisse l'appeler **avant** de
    creer l'arborescence projet et le journal. La commande creait auparavant
    `frames/`, `logs/`, `planches/` et le reste avant toute validation:
    `extract --project / --video ... --fps 1` creait donc reellement des
    dossiers a la racine du systeme, puis echouait (revue du 2026-08-05).

    Une seule implementation: `run_extraction` appelle la meme fonction, donc
    l'API programmatique reste gardee de la meme facon que la CLI.
    """
    project_dir = Path(project_dir)
    video_path = Path(video_path)

    if not isinstance(fps_target, (int, float)) or isinstance(fps_target, bool):
        raise ExtractionInputError(
            f"Parametre --fps invalide: {fps_target!r}. Attendu un nombre."
        )
    if fps_target != fps_target or fps_target in (float("inf"), float("-inf")):
        raise ExtractionInputError(f"Parametre --fps non fini: {fps_target!r}.")
    if fps_target <= 0:
        raise ExtractionInputError(
            f"Parametre --fps invalide: {fps_target}. Attendu un nombre strictement "
            "positif."
        )
    if not video_path.is_file():
        raise ExtractionInputError(f"Fichier video introuvable: {video_path}")
    if project_dir.exists() and not project_dir.is_dir():
        raise ExtractionInputError(
            f"Le chemin projet n'est pas un dossier: {project_dir}"
        )


def run_extraction(
    *,
    project_dir: str | Path,
    video_path: str | Path,
    fps_target: float,
    source_in_timecode: str | None = None,
    source_out_timecode: str | None = None,
    overwrite: bool = False,
    nouvelle_version: bool = False,
    ecrasement_conscient: bool = False,
    consent_granted: bool = False,
    unknown_color_accepted: bool = False,
    logger: logging.Logger,
    in_stream: Any = None,
    out_stream: Any = None,
    ffmpeg_binary: str = "ffmpeg",
    ffprobe_binary: str = "ffprobe",
    rappel_progression=None,
) -> ExtractionOutcome:
    """Executer `extract` de bout en bout: probe, selection, accord, TIFF, manifest.

    Ordre impose, chaque etape ayant une raison:

    1. **toutes** les validations d'entree bon marche, avant le moindre appel
       externe couteux (AC 1) -- **y compris la transition d'etat du lot vise**
       depuis la story 11.4c (`EPIC11-ARB-83`): un lot deja passe a `pdf` ou
       au-dela est refuse ici, avant ffmpeg et donc avant toute ecriture, et
       non plus a l'etape 6 apres que l'etape 5 a efface ses frames;
    2. probe ffprobe et qualification de la source (AC 8);
    3. selection deterministe, consommee telle quelle depuis la story 3.2;
    4. confirmation (story 3.3) -- apres le probe et la selection, tous deux
       bon marche, et **avant** l'appel ffmpeg qui est l'etape couteuse. Sur
       refus: aucun appel ffmpeg, aucun fichier ecrit, **aucun dossier de lot
       cree**;
    5. extraction, controle du compte de fichiers, puis renommage;
    6. persistance manifest (story 3.4), juste apres l'ecriture reussie des
       TIFF (`decisions-2026-08-03.md`, decision 1 / ARB-1).

    `rappel_progression` est **optionnel** (`AR3`, story 5.28) et n'est que
    **transmis**: rien n'est calcule ici. Il atteint l'etape 5, la seule qui
    dure, et y recoit des jalons `(faites, total)` comptes sur les fichiers
    reellement ecrits. Sans lui -- le cas de la CLI, qui n'en passe aucun --
    le comportement est celui d'aujourd'hui.

    `nouvelle_version` et `ecrasement_conscient` (story 5.29, `EPIC11-ARB-89`)
    sont les deux issues du refus de transition d'etat de l'etape 1, mutuellement
    exclusives:

    * `nouvelle_version=True` -- le lot vise est celui du premier rang de
      version au-dessus de la LIGNE D'EAU (un rang se consomme et ne se
      reutilise pas, `EPIC11-ARB-92` -- ce n'est PAS le trou de la
      sequence), calcule
      contre le manifeste existant. Son `lot_id` est **distinct** de celui du
      lot d'origine: aucun conflit d'etat n'est possible, le lot existant
      reste intact;
    * `ecrasement_conscient=True` -- **avec** `consent_granted=True`, jamais
      l'un sans l'autre (meme exigence que l'AC 8 de la story 3.3 pour
      l'accord avant ffmpeg): le refus de transition d'etat de l'etape 1 est
      contourne pour cet appel seul, et l'extraction ecrase le lot en place.
      Aucune machine a etats n'est assouplie: c'est un contournement
      journalise d'un seul appel, jamais une mutation de
      `validate_lot_state_transition`.

    Les deux ensemble sont un refus nomme (AC 5): ce sont deux issues d'un
    meme conflit, jamais deux a la fois.
    """
    project_dir = Path(project_dir)
    video_path = Path(video_path)

    # --- 1. validations d'entree, toutes anterieures a tout appel externe ---
    validate_extraction_inputs(project_dir, video_path, fps_target)

    rush_id = normalize_identifier(video_path.stem, label="le nom du fichier source")
    project_reference = project_dir.resolve().name or project_dir.name
    project_id = normalize_identifier(project_reference, label="le nom du dossier projet")
    source_parent = _source_parent_name(video_path)

    # ARB-9: deux rushs homonymes dans deux dossiers differents sont deux rushs
    # distincts, pas le meme. Le conflit est detecte contre le manifest deja
    # ecrit, et leve par un RANG (`EPIC11-ARB-233`) plutot que par un
    # ecrasement.
    #
    # **Corrige le 2026-09-05, finding `F17` de la revue 11.4e.** Cette place
    # disait « leve par un suffixe derive du dossier parent ». `EPIC11-ARB-9`
    # tient sur son critere -- il faut lever, jamais ecraser --, seule la FORME
    # de la levee a change : `disambiguated_rush_id` pose un rang.
    #
    # **Pourquoi cette garde ne recoit PAS les criteres mesures, et pourquoi
    # elle ne peut pas descendre apres le probe** (note 5 de la relecture du
    # 2026-09-01, mesure du 2026-09-02). La comparaison complete
    # (`CRITERES_IDENTITE_RUSH`: base de timecode, duree, timecode initial --
    # le dossier parent en est SORTI depuis `EPIC11-ARB-230`) exige
    # ffprobe. La remonter ici imposerait de remonter
    # `probe_media` avec elle -- et l'AC 1.1 de la story 11.4c
    # (`EPIC11-ARB-83`) mesure exactement l'inverse: la transition d'etat du
    # lot est jugee **avant** `ensure_ffmpeg_available`, binaires absents du
    # `PATH` a l'appui, pour qu'un lot deja passe a `pdf` soit refuse sans
    # qu'aucun appel externe ne soit paye. Or `lot_id` derive du `rush_id` que
    # cette garde-ci arbitre: probe avant la garde = probe avant la transition
    # d'etat. Les deux frontieres ne peuvent pas etre vraies ensemble, et
    # c'est celle de l'ARB-83 qui protege contre une destruction.
    #
    # La comparaison complete appartient donc au chemin de **declaration**, ou
    # elle ne coute rien: `tui.atelier_extraction_ecriture.sonder_la_source`
    # sonde deja la source avant tout ecran, et rend les quatre criteres. Ici,
    # `mesures` reste absent: les trois criteres qu'il porterait sont declares
    # **non verifiables**, jamais divergents, et le verdict est identique a
    # celui d'avant la note 5.
    manifest_path = Path(project_dir) / MANIFEST_FILENAME
    if manifest_path.is_file():
        try:
            declare = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            declare = {}
        conflit = rush_identity_conflict(
            declare.get("rushes"), rush_id, source_parent
        )
        if conflit is not None:
            ancien = rush_id
            # `EPIC11-ARB-233` : le suffixe est un RANG, ici comme partout
            # ailleurs. Le regime degrade au-dessus, lui, n'a pas bouge -- le
            # dossier reste le CRITERE de dernier recours de ce chemin-ci,
            # faute de mesure. Ce sont deux roles distincts, et seul le second
            # survit : laisser ce chemin nommer par le dossier pendant que la
            # declaration nomme par le rang donnerait DEUX identifiants au meme
            # rush selon la porte d'entree.
            rush_id = disambiguated_rush_id(rush_id, declare.get("rushes"))
            logger.info(
                "Rush homonyme deja declare (%s, dossier %s): ce rush vient du "
                "dossier %s, il est donc identifie %s plutot que d'ecraser le "
                "premier",
                ancien,
                conflit.entree.get("source_parent"),
                source_parent,
                rush_id,
            )

    # Bornes de fenetre (story 3.7): elles entrent dans l'identite du lot et
    # dans son nom de dossier, sans quoi un extrait ecraserait l'extraction
    # complete du meme rush a la meme cadence. Aucune revalidation ici: la
    # regle de bornage appartient au noyau (3.2), qui la fait jouer plus bas,
    # une fois le cardinal reel de la source connu.
    bornes = {
        "source_in_timecode": source_in_timecode,
        "source_out_timecode": source_out_timecode,
    }
    check_fps_form_consistency(rush_id, fps_target, **bornes)

    # Story 5.29 (`EPIC11-ARB-89`), AC 5: deux issues du meme conflit, jamais
    # deux a la fois -- les combiner serait un troisieme comportement que la
    # politique n'a jamais decrit. `overwrite` (AC 9 de la story 3.3) porte
    # deja la MEME intention qu'`ecrasement_conscient` sur le dossier de
    # frames : `nouvelle_version` doit donc etre exclusif des DEUX,
    # trouve en revue -- l'asymetrie (seul `ecrasement_conscient` etait
    # garde) laissait passer `--nouvelle-version --overwrite` sans refus ni
    # semantique documentee.
    if nouvelle_version and ecrasement_conscient:
        raise ExtractionInputError(
            "--nouvelle-version et --ecrasement-conscient sont deux issues DISTINCTES "
            "du meme conflit d'ecriture et ne se combinent pas: la premiere cree un "
            "lot_id different (ce lot-ci reste intact), la seconde ecrase ce lot en "
            "place. Choisir l'une des deux."
        )
    # **`--overwrite` n'est PAS exclusif de `--nouvelle-version`, et la premiere
    # redaction de cette story se trompait.** Elle les avait rendus exclusifs au
    # motif que « --overwrite n'a rien a ecraser puisque le dossier de la
    # nouvelle version est neuf ». La revue Opus du 2026-08-30 a mesure que
    # cette premisse est FAUSSE : le dossier du rang resolu peut etre deja
    # peuple -- c'est meme le cas produit par la fuite que `RapportSuppression.
    # fichiers_non_supprimes` documente (manifeste a jour, fichiers restes).
    # L'exclusion produisait alors un BLOCAGE SEC parfait : le refus de la
    # garde AC 9 conseille `--overwrite`, que cette exclusion refusait, et
    # `--ecrasement-conscient` etait exclu lui aussi. Zero issue -- exactement
    # la forme qu'`EPIC11-ARB-89` interdit, dans la story qui porte cet
    # arbitrage.
    #
    # Les deux drapeaux sont en realite **orthogonaux** : `nouvelle_version`
    # choisit QUEL lot est vise, `overwrite` dit quoi faire si le dossier de ce
    # lot est deja peuple. `ecrasement_conscient`, lui, reste exclusif de
    # `nouvelle_version` : ces deux-la sont bien deux issues du meme conflit
    # d'ETAT.

    version_rank: int | None = None
    base_lot_id: str | None = None
    if nouvelle_version:
        # AC 2: le rang se lit au manifeste EXISTANT, jamais au nom. Et c'est
        # la LIGNE D'EAU plus un, jamais le trou de la sequence
        # (`EPIC11-ARB-92`): un rang se consomme. Ce commentaire disait
        # l'inverse -- « premier rang LIBRE (le trou de la sequence), pas
        # maximum + 1 » -- alors que le code faisait deja le contraire.
        manifest_existant = _manifeste_charge(manifest_path)
        version_rank = resolve_version_rank(manifest_existant, rush_id, fps_target, **bornes)
        base_lot_id = build_lot_id(rush_id, fps_target, **bornes)

    lot_id = build_lot_id(rush_id, fps_target, version_rank=version_rank, **bornes)

    frames_dir = project_layout.extract_frames_dir(
        project_dir, rush_id, fps_target, version_rank=version_rank, **bornes
    )
    frames_dir_relative = frames_dir.relative_to(project_dir).as_posix()

    # AC 9: un lot deja present n'est jamais efface implicitement.
    #
    # Story 5.29 (`EPIC11-ARB-89`): un ecrasement conscient CONSENTI
    # (`ecrasement_conscient=True` ET `consent_granted=True`) satisfait cette
    # garde au meme titre qu'`--overwrite` -- ecraser sciemment un lot veut
    # dire ecraser son dossier de frames autant que la transition d'etat qui
    # le protege ; exiger un troisieme mot-cle pour le seul dossier ferait de
    # l'ecrasement conscient une issue incomplete.
    # Lu UNE fois: les deux avertissements et le jugement de transition le
    # nomment, et deux lectures ouvriraient une fenetre ou ils pourraient se
    # contredire sur le meme lot.
    _etat_du_lot = _etat_declare_du_lot(manifest_path, lot_id)
    ecrasement_effectif = overwrite or (ecrasement_conscient and consent_granted)
    if frames_dir.is_dir() and any(entry.is_file() for entry in frames_dir.iterdir()):
        if not ecrasement_effectif:
            raise ExtractionInputError(
                f"Un lot est deja present dans {frames_dir_relative} et ne sera pas "
                "efface implicitement. Relancer avec --overwrite pour le remplacer, "
                "ou choisir une autre cadence cible (donc un autre lot)."
            )
        if ecrasement_conscient and consent_granted:
            # AC 7 : l'avertissement doit accompagner TOUT ecrasement
            # consenti, pas seulement celui qui traverse le refus de
            # transition d'etat (le `except LotStateConflictError` plus bas).
            # Trouve en revue : un lot encore en etat `extraction` (ou
            # inconnu du manifeste) dont le dossier de frames porte deja des
            # fichiers ne leve JAMAIS `LotStateConflictError` -- il aurait
            # ete efface en silence, exactement la destruction sans
            # avertissement qu'`EPIC11-ARB-89` interdit.
            logger.warning(
                "%s Le dossier de frames %s sera efface avant reecriture.",
                message_avertissement_ecrasement(lot_id, _etat_du_lot),
                frames_dir_relative,
            )

    # `EPIC11-ARB-83` (story 11.4c, lot V1): la transition d'etat est jugee
    # **ICI**, avant le moindre appel externe, et non plus a la seule etape 6.
    #
    # Ce que ce deplacement corrige, mesure: l'effacement du lot precedent et
    # le renommage des TIFF sont a l'etape 5, la persistance -- seul endroit
    # d'ou `LotStateConflictError` pouvait etre levee -- a l'etape 6. Un lot
    # deja passe a `pdf` ou au-dela voyait donc ses frames **detruites et
    # remplacees** avant que la transition ne soit jugee, et le message du
    # refus, « Aucune ecriture n'a eu lieu », n'etait vrai **que du
    # manifeste**. Verbatim de l'arbitrage: « La transition d'etat doit etre
    # **jugee en amont**, avant ffmpeg, sans toucher a l'ordre de
    # l'effacement. »
    #
    # **Ce n'est donc PAS un deplacement de `_clear_existing_lot`**, et ce
    # point est aussi important que le refus lui-meme: l'effacement reste a
    # l'etape 5, apres l'appel a ffmpeg, pour la raison de correction opposee
    # que le commentaire de la revue du 2026-08-05 documente sur place. Deux
    # gardes qui se croisent, chacune a sa place.
    #
    # Le jugement est delegue a `validate_extraction_state_transition`, qui
    # appelle `io.manifest.validate_lot_state_transition` -- la **meme**
    # fonction que la persistance et que `tui.refus_d_etat_de_lot`. Aucune
    # machine a etats n'est reecrite, et le message du refus n'a qu'une
    # redaction.
    #
    # Story 5.29 (`EPIC11-ARB-89`), AC 6: l'ecrasement conscient CONTOURNE ce
    # jugement pour cet appel seul -- jamais une mutation de
    # `validate_lot_state_transition`, jamais un assouplissement global. Un
    # lot versionne (`nouvelle_version=True`) n'atteint jamais cette branche:
    # son `lot_id` est neuf, donc `current_state` vaut deja `None` et le
    # jugement passe sans conflit.
    try:
        validate_extraction_state_transition(lot_id, _etat_du_lot)
    except LotStateConflictError:
        if not (ecrasement_conscient and consent_granted):
            raise
        logger.warning(
            "%s", message_avertissement_ecrasement(lot_id, _etat_du_lot)
        )

    # Arborescence de base seulement (`scans/`, `planches/`, `logs/`): appeler
    # `ensure_project_layout` avec un manifest creerait deja le dossier de lot,
    # ce que l'AC 8 de la story 3.3 interdit tant que l'accord n'est pas donne.
    project_layout.ensure_project_layout(project_dir)

    # --- 2. probe et qualification ------------------------------------------
    ffmpeg_utils.ensure_ffmpeg_available(ffmpeg_binary)
    probe = video_metadata.probe_media(str(video_path), ffprobe_bin=ffprobe_binary)
    qualification = qualify_source(probe)

    fps_source_exact = qualification.fps_source
    fps_target_exact = Fraction(exact_frame_rate(fps_target))
    if fps_target_exact > fps_source_exact:
        raise ExtractionInputError(upsampling_refusal_message(fps_target, fps_source_exact))

    if not qualification.cadence_corroboree:
        # ARB-6 (`decisions-2026-08-05.md`): refus, pas reserve. L'outil ne sait
        # pas prouver qu'un tel rush est a cadence variable -- c'est justement
        # l'angle mort -- donc la regle porte sur la **non-verifiabilite**. Elle
        # refuse aussi des rushs sains dont le conteneur est avare en
        # metadonnees, cout assume par Egan: un lot silencieusement faux se
        # propage jusqu'au PDF et au QR code, un refus se repare par un
        # reencodage.
        raise ExtractionInputError(
            f"Cadence source inverifiable ({fps_source_exact} im/s annoncee): ce "
            "conteneur ne declare ni la duree du flux video ni son nombre "
            "d'images, et 'avg_frame_rate' y est recopie sur 'r_frame_rate' meme "
            "sur une source a cadence variable. Les deux garde-fous contre une "
            "cadence variable sont donc inoperants sur ce fichier, et un rush a "
            "cadence variable produirait des timecodes faux -- donc des noms de "
            "fichiers faux, propages jusqu'au PDF et au QR code -- sans que rien "
            "ne le signale. Reencoder le rush en cadence constante dans un "
            "conteneur qui declare sa duree (par exemple: ffmpeg -i <rush> "
            "-vsync cfr -r <cadence> <sortie>.mov) leve le refus."
        )

    source_frame_count, is_exact = resolve_source_frame_count(
        video_path, qualification, ffprobe_bin=ffprobe_binary, logger=logger
    )
    logger.info(
        "Source qualifiee: cadence %s im/s, %d frame(s) source (%s), timecode de "
        "depart %s",
        fps_source_exact,
        source_frame_count,
        "comptage exact" if is_exact else "ESTIMATION",
        qualification.start_timecode or "absent",
    )

    # --- 3. selection deterministe (story 3.2), consommee telle quelle ------
    selection = select_source_frames(
        fps_source=fps_source_exact,
        fps_target=fps_target,
        source_frame_count=source_frame_count,
        source_start_timecode=qualification.start_timecode,
        source_in_timecode=source_in_timecode,
        source_out_timecode=source_out_timecode,
        source_duration_seconds=qualification.stream_duration_seconds,
        source_frame_count_is_exact=is_exact,
    )

    # Coherence typee / exacte verifiee ici plutot qu'a la persistance, qui
    # n'intervient qu'apres une extraction potentiellement longue.
    typed_fps_source = _typed_rate(fps_source_exact, "source", selection.fps_source)
    typed_fps_target = _typed_rate(fps_target, "cible", selection.fps_target)

    # --- 4. confirmation (story 3.3) ----------------------------------------
    report = source_confirmation.build_source_report(
        probe,
        fps_target=fps_target,
        selection=selection,
        batch_dir_relative=frames_dir_relative,
    )
    # Le drapeau de consentement force le mode non interactif quel que soit le
    # TTY: `mode` designe le canal d'acquittement, pas la nature du terminal.
    interactive = (
        False
        if consent_granted
        else source_confirmation.detect_interactive(in_stream, out_stream)
    )
    confirmation = source_confirmation.confirm_source_metadata(
        report,
        interactive=interactive,
        consent_granted=consent_granted,
        unknown_color_accepted=unknown_color_accepted,
        logger=logger,
        out_stream=out_stream,
        in_stream=in_stream,
    )
    if not confirmation.granted:
        return ExtractionOutcome(
            granted=False,
            message=confirmation.message,
            project_id=project_id,
            rush_id=rush_id,
            lot_id=lot_id,
            frames_dir=frames_dir,
            frames_dir_relative=frames_dir_relative,
            selection=selection,
        )

    # --- 5. extraction, controle de compte, renommage -----------------------
    frames_dir.mkdir(parents=True, exist_ok=True)

    temp_dir = frames_dir / ffmpeg_utils.EXTRACT_TEMP_DIRNAME
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)

    try:
        temp_paths = ffmpeg_utils.extract_selected_frames(
            video_path,
            temp_dir,
            [frame.source_index for frame in selection],
            ffmpeg_binary=ffmpeg_binary,
            rappel_progression=rappel_progression,
        )

        # AC 6: le compte de fichiers est verifie AVANT le renommage, pour
        # qu'un ecart reste visible plutot que d'etre masque par des noms
        # finaux plausibles. `expected_frame_count` vient de la story 3.2 et
        # jamais d'un comptage disque: un lot tronque se declarerait complet.
        if len(temp_paths) != len(selection):
            raise ffmpeg_utils.FrameExtractionError(
                f"Nombre de fichiers extraits ({len(temp_paths)}) different du nombre "
                f"de frames selectionnees ({len(selection)}). Aucun lot partiel n'est "
                "declare comme un succes."
            )

        # Le lot precedent n'est retire qu'**ici**: ffmpeg a reussi, le compte
        # est verifie, et les images de remplacement sont sur le disque. Le
        # faire avant l'appel a ffmpeg detruisait un lot valide sur la seule
        # intention de le remplacer: un echec d'extraction laissait alors un
        # dossier vide et un manifest qui continuait de declarer le lot
        # complet, soit exactement le mensonge que l'AC 6 existe pour fermer
        # (revue du 2026-08-05).
        if ecrasement_effectif:
            _clear_existing_lot(frames_dir, keep_temp=True)

        # Renommage dans l'ordre des `output_rank`, jamais par glob + sorted.
        written: list[Path] = []
        for frame, temp_path in zip(selection, temp_paths):
            final_path = frames_dir / build_extracted_frame_filename(
                rush_id, fps_target, frame.frame_timecode
            )
            temp_path.replace(final_path)
            written.append(final_path)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    if len(written) != selection.expected_frame_count:
        raise ffmpeg_utils.FrameExtractionError(
            f"Lot incomplet: {len(written)} fichier(s) ecrit(s) pour "
            f"{selection.expected_frame_count} frame(s) attendue(s)."
        )

    logger.info(
        "%d frame(s) TIFF %d bits ecrite(s) dans %s",
        len(written), EXTRACTION_OUTPUT_BIT_DEPTH, frames_dir_relative,
    )

    # --- 6. persistance manifest (story 3.4), decision ARB-1 ----------------
    # Story 2.8 (AC 1, EPIC7-ARB-41): le chemin absolu RESOLU (liens et
    # relatif deja resolus au moment de l'extraction), jamais la chaine telle
    # que tapee -- c'est ce qui permet de retrouver le fichier plus tard, pas
    # ce que l'operateur a saisi. `.resolve()` a deja ete verifie utilisable
    # sur ce chemin par `validate_extraction_inputs` (le fichier existe).
    rush_source_path = str(video_path.resolve())
    record = ExtractionRecord(
        project_id=project_id,
        rush_id=rush_id,
        rush_source_name=video_path.name,
        rush_source_parent=source_parent,
        rush_source_path=rush_source_path,
        lot_id=lot_id,
        frames_dir_relative=frames_dir_relative,
        selection=selection,
        fps_source=typed_fps_source,
        fps_target=typed_fps_target,
        source_width=int(report.resolution_source["width"]),
        source_height=int(report.resolution_source["height"]),
        source_fields=report.source_fields,
        confirmation_mode=confirmation.mode,
        unknown_color_accepted=confirmation.unknown_color_accepted,
        confirmed_at=confirmation.confirmed_at,
        version_rank=version_rank,
        base_lot_id=base_lot_id,
        ecrasement_conscient=ecrasement_conscient and consent_granted,
    )
    persisted = persist_extraction(project_dir, record)
    logger.info("Manifest mis a jour: lot %s dans %s", lot_id, persisted.manifest_path)

    return ExtractionOutcome(
        granted=True,
        message=f"{len(written)} frame(s) extraite(s) dans {frames_dir_relative}",
        project_id=project_id,
        rush_id=rush_id,
        lot_id=lot_id,
        frames_dir=frames_dir,
        frames_dir_relative=frames_dir_relative,
        written_frame_count=len(written),
        selection=selection,
        persisted=persisted,
    )
