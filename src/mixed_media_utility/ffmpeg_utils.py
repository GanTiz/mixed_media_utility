"""Wrapper utilities for extracting frame sequences via the system ffmpeg binary.

Deux chemins coexistent et ne doivent pas etre confondus:

* ``extract_frames`` -- heritage POC (story 1.1). Sort du PNG, **re-echantillonne**
  via ``-vf fps=`` (donc duplique ou saute des frames) et efface silencieusement
  les fichiers correspondant a son glob. Consomme par ``poc build-sheet``,
  verrouille par ``tests/unit/test_ffmpeg_utils.py``: signature, defauts et
  comportement inchanges.
* ``extract_selected_frames`` -- chemin ``extract`` (story 3.1). Selectionne des
  **indices de frames source** decides par ``frame_selection`` (story 3.2),
  n'interpole ni ne duplique jamais, sort du TIFF 16 bits. ``-vf fps=`` y est
  explicitement proscrit.
"""

from __future__ import annotations

import logging
import math
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import progression

_JOURNAL = logging.getLogger(__name__)


class FfmpegNotFoundError(RuntimeError):
    """Raised when the ffmpeg binary is not available on PATH."""


class FrameExtractionError(RuntimeError):
    """Raised when ffmpeg fails to extract frames from the input video."""


def ensure_ffmpeg_available(ffmpeg_binary: str = "ffmpeg") -> str:
    """Return the resolved path to the ffmpeg binary or raise FfmpegNotFoundError."""
    resolved = shutil.which(ffmpeg_binary)
    if resolved is None:
        raise FfmpegNotFoundError(
            f"Binaire ffmpeg introuvable dans le PATH ('{ffmpeg_binary}'). "
            "Installez ffmpeg et assurez-vous qu'il est accessible depuis le terminal."
        )
    return resolved


def extract_frames(
    video_path: str | Path,
    output_dir: str | Path,
    fps: float,
    ffmpeg_binary: str = "ffmpeg",
    filename_pattern: str = "frame_%04d.png",
) -> list[Path]:
    """Extract a PNG frame sequence from ``video_path`` into ``output_dir`` at ``fps``.

    Returns the sorted list of extracted frame paths. Raises FileNotFoundError if the
    input video does not exist, FfmpegNotFoundError if ffmpeg is not on PATH, and
    FrameExtractionError if ffmpeg fails or produces no frames.
    """
    video_path = Path(video_path)
    output_dir = Path(output_dir)

    if not video_path.is_file():
        raise FileNotFoundError(f"Fichier video introuvable: {video_path}")

    ffmpeg_exe = ensure_ffmpeg_available(ffmpeg_binary)
    output_dir.mkdir(parents=True, exist_ok=True)

    glob_pattern = filename_pattern.replace("%04d", "*").replace("%d", "*")
    for stale_frame in output_dir.glob(glob_pattern):
        stale_frame.unlink()

    output_pattern = output_dir / filename_pattern
    command = [
        ffmpeg_exe,
        "-y",
        "-i", str(video_path),
        "-vf", f"fps={fps}",
        str(output_pattern),
    ]

    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise FrameExtractionError(
            f"Echec de l'extraction ffmpeg (code {result.returncode}): {result.stderr.strip()}"
        )

    frames = sorted(output_dir.glob(glob_pattern))
    if not frames:
        raise FrameExtractionError(
            "Aucune frame extraite: verifiez la video source et le parametre --fps."
        )
    return frames


# --------------------------------------------------------------------------
# Chemin `extract` (story 3.1): selection par indice de frame source
# --------------------------------------------------------------------------

#: Format de pixel force en sortie, quelle que soit la profondeur du rush
#: (`decisions-2026-08-03.md`, decision 4 / ARB-4). RGB 16 bits par canal.
#: Ce n'est **pas** un gain de qualite: upscaler une source 8 bits vers 16
#: bits n'ajoute aucune information, cela uniformise seulement le traitement
#: en aval (Epic 4/5/6 n'a jamais a distinguer un lot 8 d'un lot 10 bits).
#: Laisser ffmpeg negocier le format produirait un YCbCr sous-echantillonne
#: depuis une source `yuv420p`, techniquement TIFF mais mal decode par la
#: chaine aval (`Pillow` / `reportlab`, story 4.1).
EXTRACT_PIX_FMT = "rgb48le"

#: Profondeur, en bits par canal, garantie par `EXTRACT_PIX_FMT`.
from mixed_media_utility.constants import OUTPUT_BIT_DEPTH as EXTRACT_OUTPUT_BIT_DEPTH

#: Encodeur d'image impose explicitement plutot que deduit de l'extension.
EXTRACT_VCODEC = "tiff"

#: Option de passthrough de cadence. Sans elle ffmpeg **re-cadence** la sortie
#: et le nombre de fichiers ecrits ne correspond plus a la selection.
FPS_MODE_OPTION = "-fps_mode"
FPS_MODE_VALUE = "passthrough"

#: `-fps_mode` n'existe qu'a partir de ffmpeg 5.0. L'alias historique
#: `-vsync 0` a la meme semantique sur les versions anterieures.
#: `ensure_ffmpeg_available` ne fait qu'un `shutil.which` et ne verifie aucune
#: version: le choix est donc fait explicitement ici, et le message d'erreur
#: nomme la version minimale si l'option est rejetee.
FPS_MODE_MIN_FFMPEG_VERSION = "5.0"

#: Motif de nom **temporaire**. ffmpeg ne sait emettre qu'un `%0Nd` numerique,
#: jamais les noms finaux de l'AC 4; le renommage a lieu chez l'appelant.
#: Huit chiffres et non quatre: `%04d` **ne tronque pas** au-dela de 9999, il
#: elargit le champ. Ici les noms sont de toute facon calcules et jamais tries
#: lexicographiquement, mais la largeur evite d'y revenir.
EXTRACT_TEMP_PATTERN = "mmu_extract_%08d.tiff"

#: Sous-dossier temporaire, cree dans le dossier de lot et retire par
#: l'appelant apres renommage: un `verify_extracted_lot` (story 3.4) qui
#: tomberait sur ces fichiers les signalerait comme surnumeraires.
EXTRACT_TEMP_DIRNAME = ".mmu-extract-tmp"

#: Nombre maximal de termes `eq(n\,I)` par invocation ffmpeg. Une selection de
#: plusieurs milliers de frames produit sinon une expression `select`
#: gigantesque qui depasse la longueur de ligne de commande de l'OS (Windows
#: en premier, ~32 Ko). Strategie retenue: **decoupage en plusieurs
#: invocations**, chacune numerotant sa sortie depuis `-start_number`, ce qui
#: garde les noms temporaires calculables sans aucun `glob`.
MAX_SELECT_TERMS_PER_INVOCATION = 1000

#: Intervalle de scrutation du repertoire temporaire pendant qu'un appel
#: ffmpeg tourne, en secondes. **Valeur provisoire, faute de mesure terrain**,
#: a recalibrer au premier pilote reel. Trop court, il coute un listage de
#: repertoire pour rien ; trop long, il supprime les paliers sur un lot rapide
#: et la jauge saute de 0 a 100 %, soit exactement le defaut que le comptage
#: par chunk avait (`EPIC7-ARB-67`). C'est une **scrutation**, jamais une
#: lecture du flux `-progress` de ffmpeg : le depot paie deja `_rejects_fps_mode`
#: sur une option absente selon les versions, et dependre du format de sortie
#: rouvrirait la meme famille de panne.
PROGRESSION_POLL_INTERVAL_SECONDS = 0.25


def _temp_name_bounds() -> tuple[str, str]:
    """Prefixe et suffixe litteraux de `EXTRACT_TEMP_PATTERN`.

    Sert **uniquement** a compter les fichiers deja tombes dans le repertoire
    temporaire. Le comptage n'est jamais utilise pour **nommer** un fichier :
    les noms restent calcules par `temp_frame_path`, jamais retrouves par un
    `glob` + `sorted` dont le tri diverge du tri numerique.
    """
    prefixe, _, queue = EXTRACT_TEMP_PATTERN.partition("%")
    suffixe = queue.split("d", 1)[1] if "d" in queue else ""
    return prefixe, suffixe


def _compter_par_listage(temp_dir) -> int | None:
    """Compter TOUTES les entrees du repertoire qui portent le motif temporaire.

    Comptage **non borne**, de lecture generale : il ne sait pas de quelle passe
    viennent les fichiers qu'il voit. Il n'est plus le comptage de la
    progression -- voir `count_written_temp_frames` et le finding EC-2 --, mais
    il reste la reponse a « combien de fichiers de ce motif y a-t-il ici ».

    Le filtre porte sur le **prefixe et le suffixe** du motif, les deux : un
    `.tiff` depose la par un autre outil n'est pas une frame de ce lot, pas plus
    qu'un `.log` portant notre prefixe.
    """
    prefixe, suffixe = _temp_name_bounds()
    try:
        with os.scandir(os.fspath(temp_dir)) as entrees:
            return sum(
                1
                for entree in entrees
                if entree.name.startswith(prefixe) and entree.name.endswith(suffixe)
            )
    except (OSError, TypeError, ValueError):
        return None


def count_written_temp_frames(temp_dir, total=None, depuis=0) -> int | None:
    """Compter les frames temporaires deja ecrites ; `None` si illisible.

    `None` -- et non une exception, ni zero : un repertoire illisible donne
    **moins de jalons**, jamais une erreur ni un recul de la jauge
    (`EPIC7-ARB-79`).

    **Deux regimes, et c'est delibere.**

    * `total is None` : comptage par **listage** du repertoire, non borne (voir
      `_compter_par_listage`). C'est la lecture generale, pas celle de la
      progression ;
    * `total` fourni : comptage **borne aux rangs que la passe attend**, sonde
      **depuis** `depuis`. C'est celui de la progression, et il est le seul
      cable dans `_emettre_compte`.

    Pourquoi la borne (revue de vague 2 bis, EC-2). Le listage compte toutes les
    entrees au motif, sans borne de rang ; la garde de comptage de
    `extract_selected_frames`, elle, ne regarde que `range(len(indices))`. **Les
    deux ne comptaient donc pas la meme chose** : dix residus laisses aux rangs
    900-909 par un `shutil.rmtree(..., ignore_errors=True)` **silencieusement**
    en echec -- regime ordinaire sous Windows quand un fichier est tenu --
    suffisaient a faire annoncer 10/10 a la jauge pendant que la garde levait
    « ffmpeg n'a ecrit que 0 fichier(s) ». Soit 100 % puis une erreur : le faux
    succes d'affichage qu'`EPIC7-ARB-79` existe pour interdire.

    Pourquoi la sonde plutot que le listage (revue de vague 2 bis, BH-12). Un
    listage coute O(N) par sondage, donc O(N**2) sur la passe -- mesure a 20,5 ms
    par comptage pour N = 8000, soit ~8 % d'un coeur a 4 Hz, **sur le repertoire
    meme ou ffmpeg ecrit**. L'invariant d'`EPIC7-ARB-79` dit « ne peut pas
    ralentir notablement le travail qu'elle observe ». Les noms sont
    deterministes (`temp_frame_path`), donc on ne liste pas : on sonde les rangs
    a partir du dernier compte connu, ce qui rend la passe entiere O(N) au
    total. Le muxer `image2` numerote **sans trou** depuis `-start_number` et les
    chunks s'enchainent dans l'ordre : les rangs presents sont toujours un
    prefixe de `range(total)`, et s'arreter au premier rang absent compte donc
    juste. Un lot tronque manque toujours ses **derniers** rangs, jamais ceux du
    milieu -- c'est ce que la garde de comptage constate par ailleurs.

    **Un fichier en cours d'ecriture est compte des sa creation**, et c'est
    assume : aucune taille n'est lue, seulement la presence. Le jalon peut donc
    etre en avance d'un fichier sur ce que ffmpeg a reellement fini d'ecrire. La
    propriete affichee reste tenue -- « moins de jalons, jamais un recul » --
    parce que cet ecart va dans l'**autre sens** : il ne fait jamais reculer la
    jauge. Et il ne peut pas produire de faux succes : la garde de comptage de
    `extract_selected_frames` verifie les fichiers **apres** la fin du
    processus, et le dernier jalon reste sous le total quand ils manquent.
    Fermer cet ecart demanderait de lire la taille de chaque candidat a chaque
    sondage, en course avec l'ecrivain : le prix n'en vaut pas la peine pour une
    donnee de rendu (revue de vague 2 bis, EC-8).

    **Contrat de `depuis`** : c'est un compte deja **constate**, jamais une
    esperance. `_emettre_compte` y passe `emetteur.dernier`, qui est par
    construction le nombre de rangs contigus deja trouves : les rangs
    inferieurs sont donc presents, et ne pas les resonder est juste. Un
    `depuis` invente au-dela du reel serait rendu tel quel -- c'est pourquoi il
    n'est pas un parametre d'appelant tiers.
    """
    if total is None:
        return _compter_par_listage(temp_dir)
    try:
        borne = int(total)
        rang = max(0, int(depuis))
        racine = Path(temp_dir)
        if not racine.is_dir():
            # Repertoire absent ou illisible : `None`, jamais un compte qui
            # ferait reculer la jauge.
            return None
        while rang < borne and temp_frame_path(racine, rang).exists():
            rang += 1
    except (OSError, TypeError, ValueError, OverflowError):
        return None
    return rang


def run_with_written_file_progress(
    command,
    temp_dir,
    *,
    emetteur=None,
    poll_interval=None,
) -> tuple[int, str]:
    """Executer `command` en comptant les fichiers qu'elle ecrit dans `temp_dir`.

    Rend `(returncode, stderr)`. C'est la **couture** de la story 5.28 : elle
    est appelable seule, donc testable avec un faux binaire lance par
    `sys.executable` sans passer par `ensure_ffmpeg_available`, dont la
    resolution par `shutil.which` d'un script sans extension n'est pas portable
    sur Windows.

    **Deux branches, et c'est la condition d'Egan.** Sans rappel branche --
    c'est-a-dire la CLI, le seul chemin en production aujourd'hui -- la couture
    reprend **exactement** le geste d'avant 5.28 :
    `subprocess.run(command, capture_output=True, encoding="utf-8",
    errors="replace")`. Le repli `AR3` n'acquiert ainsi aucune dependance neuve,
    en particulier pas au repertoire temporaire **systeme** : un `mkstemp`
    appele inconditionnellement faisait remonter une `OSError` nue, hors de la
    hierarchie d'erreurs du module, sur un chemin qui n'observe rien (revue de
    vague 2 bis, EC-3 et F8). « Ne pas casser le mecanisme fonctionnel pour une
    simple donnee de rendu » (Egan, `EPIC7-ARB-79`).

    **stderr va dans un fichier temporaire, jamais dans un tube -- et seulement
    quand on observe.** Une execution non bloquante ecrite naivement --
    `Popen(stderr=subprocess.PIPE)` puis une boucle de comptage, puis
    `communicate()` -- se bloque des que ffmpeg remplit le tampon du tube
    (64 Kio sur la plupart des systemes) : le processus attend qu'on lise, la
    boucle attend qu'il finisse. Ce defaut ne se voit sur aucune fixture courte,
    ffmpeg n'etant bavard que sur un vrai encodage. Le fichier supprime le tube,
    donc le blocage, et le texte relu est identique au caractere pres a celui
    que `capture_output=True` rend sur l'autre branche -- c'est ce qui permet
    aux deux `FrameExtractionError` d'etre litteralement les memes des deux
    cotes.

    **`errors="replace"` est porteur des deux cotes, pas decoratif.** ffmpeg
    recopie sur stderr le nom de fichier tel que l'OS le lui donne : un rush
    accentue arrive en cp1252 sous Windows, c'est-a-dire non decodable en UTF-8.
    En `strict`, un echec ffmpeg benin deviendrait une `UnicodeDecodeError` non
    typee, **hors de `FrameExtractionError`**, remontee nue jusqu'a la CLI
    (revue de vague 2 bis, BH-6).

    Aucun fil n'est cree : la scrutation est faite par le `timeout` de
    `Popen.wait`, et le `finally` garantit qu'aucun processus ne survit a
    l'appel, y compris apres une exception.
    """
    # Sans rappel branche, aucun listage n'a lieu : le repli `AR3` est le
    # comportement d'avant, au geste pres.
    observe = emetteur is not None and emetteur.actif
    if not observe:
        resultat = subprocess.run(
            command, capture_output=True, encoding="utf-8", errors="replace"
        )
        return resultat.returncode, resultat.stderr or ""

    try:
        interval = (
            PROGRESSION_POLL_INTERVAL_SECONDS
            if poll_interval is None
            else float(poll_interval)
        )
    except (TypeError, ValueError):
        # Un intervalle non numerique est un parametre d'**observation** : il ne
        # peut pas faire echouer le travail observe.
        interval = PROGRESSION_POLL_INTERVAL_SECONDS
    if not (interval > 0.0) or not math.isfinite(interval):
        # `isfinite` autant que `> 0` : `+inf` traversait la garde puis tuait
        # l'extraction depuis `subprocess._wait`, qui calcule
        # `int(timeout * 1000)` et leve `OverflowError` (revue de vague 2 bis,
        # EC-7).
        interval = PROGRESSION_POLL_INTERVAL_SECONDS

    descripteur, stderr_path = tempfile.mkstemp(prefix="mmu_extract_", suffix=".stderr")
    os.close(descripteur)
    try:
        with open(stderr_path, "wb") as flux_erreur:
            processus = subprocess.Popen(
                command, stdout=subprocess.DEVNULL, stderr=flux_erreur
            )
            try:
                scrutation_rompue = False
                while True:
                    try:
                        processus.wait(
                            timeout=None if scrutation_rompue else interval
                        )
                        break
                    except subprocess.TimeoutExpired:
                        _emettre_compte(emetteur, temp_dir)
                    except Exception:  # noqa: BLE001 -- AC 11, EPIC7-ARB-79
                        if scrutation_rompue:
                            # L'attente **bloquante** a leve : ce n'est plus la
                            # scrutation qui casse, c'est le chemin que le repli
                            # `AR3` emprunte aussi. Absorber ici masquerait une
                            # panne du travail observe, pas du canal.
                            raise
                        # La boucle de scrutation absorbe, comme le reste du
                        # canal : une course du fil d'observation n'a aucun
                        # effet observable sur le travail (AC 11). On cesse
                        # d'observer et l'attente redevient bloquante -- moins
                        # de jalons, jamais une erreur (revue de vague 2 bis,
                        # F7).
                        scrutation_rompue = True
                        _JOURNAL.warning(
                            "La scrutation de progression a leve ; les jalons "
                            "intermediaires sont abandonnes et l'extraction se "
                            "poursuit en attente bloquante.",
                            exc_info=True,
                        )
            finally:
                # Jamais de processus laisse vivant, meme si la boucle a ete
                # quittee par une exception (interruption clavier comprise).
                if processus.poll() is None:
                    processus.kill()
                    processus.wait()
        # Dernier comptage APRES la fin du processus : c'est le seul moment
        # ou tous les fichiers de ce lot sont tombes. Il emet le compte
        # **reel**, jamais `total` : quand ffmpeg a ecrit moins de fichiers
        # que demande, le dernier jalon reste sous le total et c'est la
        # garde de comptage qui leve. Il a lieu meme si la scrutation s'est
        # rompue : `_emettre_compte` ne leve jamais, et un jalon final vaut
        # mieux que rien.
        _emettre_compte(emetteur, temp_dir)
        stderr = Path(stderr_path).read_text(encoding="utf-8", errors="replace")
        return processus.returncode, stderr
    finally:
        try:
            os.unlink(stderr_path)
        except OSError:
            pass


def _emettre_compte(emetteur, temp_dir) -> None:
    """Compter puis emettre un jalon ; ne leve jamais (`EPIC7-ARB-79`)."""
    if emetteur is None:
        return
    # Le comptage est **borne au total attendu** (EC-2) et **sonde depuis le
    # dernier compte emis** (BH-12) : sans la borne, il ne compte pas la meme
    # chose que la garde de `extract_selected_frames` et des residus d'une passe
    # precedente suffisent a faire annoncer 100 % pendant que la garde leve ;
    # sans le point de depart, chaque sondage relit tout le repertoire, ce qui
    # coute O(N**2) sur la passe.
    compte = count_written_temp_frames(temp_dir, emetteur.total, emetteur.dernier)
    if compte is None:
        return
    emetteur.emettre(compte)


def build_select_expression(source_indices) -> str:
    """Return the `select` filter expression retaining exactly `source_indices`.

    Les virgules sont echappees (`eq(n\\,0)`), et ce n'est pas cosmetique: dans
    un filtergraph la virgule **separe les filtres**, donc `select=eq(n,0)`
    serait lu comme le filtre `select` suivi d'un filtre `0)` inexistant. La
    commande etant passee en **liste** a `subprocess.run` (aucun shell), aucun
    quoting shell n'est a ajouter, mais l'echappement du parseur de filtergraph
    de ffmpeg, lui, reste obligatoire.
    """
    indices = list(source_indices)
    if not indices:
        raise FrameExtractionError(
            "Expression de selection vide: aucune frame source a retenir."
        )
    return "+".join(f"eq(n\\,{int(index)})" for index in indices)


def build_frame_selection_command(
    ffmpeg_exe: str,
    video_path: str | Path,
    source_indices,
    output_pattern: str | Path,
    start_number: int,
) -> list[str]:
    """Build the ffmpeg command extracting exactly `source_indices` as TIFF.

    Ordre impose, chaque element ayant une raison:

    * `select` est le **premier filtre de la chaine**. Sa variable `n` compte
      les frames *entrees dans le filtre*, pas celles du fichier: tout filtre
      place avant lui (mise a l'echelle, deinterlacement, et surtout un `fps=`)
      redefinirait `n` et ferait porter la selection sur une autre sequence que
      celle calculee par la story 3.2.
    * `-vf fps=` est **proscrit** dans ce chemin (AC 6): c'est un filtre de
      re-echantillonnage qui duplique des frames.
    * le passthrough de cadence est une option de **sortie**: il se place apres
      l'entree et avant le motif de sortie.
    * `-pix_fmt` est explicite (voir `EXTRACT_PIX_FMT`).
    * `-start_number` est explicite: le muxer `image2` numerote a partir de `1`
      sans lui, ce qui decalerait tous les noms calcules.
    """
    return [
        str(ffmpeg_exe),
        "-hide_banner",
        "-nostdin",
        "-y",
        "-i", str(video_path),
        "-vf", f"select={build_select_expression(source_indices)}",
        FPS_MODE_OPTION, FPS_MODE_VALUE,
        "-pix_fmt", EXTRACT_PIX_FMT,
        "-c:v", EXTRACT_VCODEC,
        "-an",
        "-start_number", str(int(start_number)),
        str(output_pattern),
    ]


def plan_selection_chunks(
    source_indices, max_terms: int = MAX_SELECT_TERMS_PER_INVOCATION
) -> list[tuple[int, list[int]]]:
    """Split `source_indices` into `(start_rank, indices)` invocation chunks.

    `start_rank` est le rang de sortie (base zero) de la premiere frame du
    lot, donc directement la valeur a passer a `-start_number`: la frame de
    rang `r` porte toujours le nom temporaire calcule depuis `r`, quelle que
    soit la facon dont le decoupage est fait.
    """
    if max_terms < 1:
        raise FrameExtractionError(
            f"max_terms doit valoir au moins 1, recu {max_terms}"
        )
    indices = [int(index) for index in source_indices]
    return [
        (start, indices[start:start + max_terms])
        for start in range(0, len(indices), max_terms)
    ]


def temp_frame_path(temp_dir: str | Path, output_rank: int) -> Path:
    """Return the temporary file ffmpeg writes for output rank `output_rank`.

    Nom **calcule**, jamais retrouve par `glob` + `sorted`: c'est ce que fait
    `extract_frames` (heritage POC) et c'est precisement ce qui la rend
    inutilisable ici, puisqu'un tri lexicographique diverge d'un tri numerique
    des que le champ numerique s'elargit.
    """
    return Path(temp_dir) / (EXTRACT_TEMP_PATTERN % int(output_rank))


def extract_selected_frames(
    video_path: str | Path,
    temp_dir: str | Path,
    source_indices,
    *,
    ffmpeg_binary: str = "ffmpeg",
    max_select_terms: int = MAX_SELECT_TERMS_PER_INVOCATION,
    rappel_progression=None,
) -> list[Path]:
    """Extract exactly the frames at `source_indices` into `temp_dir`.

    Une frame source retenue = exactement un fichier, sans duplication ni
    interpolation (AC 6). Rend la liste des chemins temporaires **dans l'ordre
    des rangs de sortie**; le renommage vers les noms finaux appartient a
    l'appelant, qui seul connait la convention de nommage.

    Rien ne garantit cote ffmpeg que le nombre de fichiers ecrits egale le
    nombre d'indices demandes: un indice au-dela de la fin reelle du flux ne
    produit simplement **aucun fichier**, sans code d'erreur. La verification
    de presence faite ici est donc la seule garde reelle, pas une precaution
    decorative.

    `rappel_progression` est **optionnel** (`AR3`) : sans lui, rien ne change,
    ni le comportement ni les artefacts. Avec lui, il recoit des jalons
    `(faites, total)` -- deux entiers positionnels, l'arite gelee par le socle
    7.0 -- comptes sur les **fichiers reellement ecrits**, jamais sur les chunks
    ffmpeg : `MAX_SELECT_TERMS_PER_INVOCATION` vaut 1000, donc un lot reel de
    300 frames tient dans **un seul** appel et une progression par chunk
    sauterait de 0 a 100 %. Le denominateur est `len(indices)`, cardinal d'une
    liste et donc exact par construction, jamais une duree multipliee par une
    frequence d'images.

    Le canal est **observationnel** (`EPIC7-ARB-79`) : un rappel qui leve, un
    repertoire non listable ou une course quelconque du comptage donnent moins
    de jalons, jamais une erreur. L'inverse n'est **jamais** vrai : les
    `FrameExtractionError` ci-dessous et la garde de comptage traversent
    intactes, texte compris, sans quoi on echangerait un mensonge d'affichage
    contre un faux succes.
    """
    video_path = Path(video_path)
    temp_dir = Path(temp_dir)

    if not video_path.is_file():
        raise FileNotFoundError(f"Fichier video introuvable: {video_path}")

    indices = [int(index) for index in source_indices]
    if not indices:
        raise FrameExtractionError(
            "Selection vide: aucune frame source a extraire."
        )
    if any(index < 0 for index in indices):
        raise FrameExtractionError(
            f"Indices de frame source negatifs dans la selection: {indices[:5]}"
        )
    if any(later <= earlier for earlier, later in zip(indices, indices[1:])):
        raise FrameExtractionError(
            "Les indices de frame source doivent etre strictement croissants: "
            "la selection recue ne l'est pas. L'ordre canonique du lot est celui "
            "des `output_rank` de la story 3.2, il ne se re-trie jamais localement."
        )

    ffmpeg_exe = ensure_ffmpeg_available(ffmpeg_binary)
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Le total est le cardinal de la selection, connu avant le premier appel.
    # Le comptage porte sur tout le repertoire temporaire, donc il est
    # naturellement global aux chunks : `-start_number` donne aux fichiers leur
    # rang de sortie **global**, et aucun chunk ne repart de zero.
    emetteur = progression.EmetteurProgression(rappel_progression, len(indices))

    output_pattern = temp_dir / EXTRACT_TEMP_PATTERN
    for start_rank, chunk in plan_selection_chunks(indices, max_select_terms):
        command = build_frame_selection_command(
            ffmpeg_exe, video_path, chunk, output_pattern, start_rank
        )
        returncode, stderr_brut = run_with_written_file_progress(
            command, temp_dir, emetteur=emetteur
        )
        if returncode != 0:
            stderr = (stderr_brut or "").strip()
            if _rejects_fps_mode(stderr):
                raise FrameExtractionError(
                    f"Cette version de ffmpeg ne connait pas l'option "
                    f"'{FPS_MODE_OPTION}', requise pour garantir qu'aucune frame "
                    f"n'est reinseree ni dupliquee. Version minimale exigee: ffmpeg "
                    f"{FPS_MODE_MIN_FFMPEG_VERSION}. Mettre a jour ffmpeg. "
                    f"Detail: {stderr}"
                )
            raise FrameExtractionError(
                f"Echec de l'extraction ffmpeg (code {returncode}) sur les "
                f"rangs {start_rank} a {start_rank + len(chunk) - 1}: {stderr}"
            )

    frame_paths = [temp_frame_path(temp_dir, rank) for rank in range(len(indices))]
    missing = [path.name for path in frame_paths if not path.is_file()]
    if missing:
        raise FrameExtractionError(
            f"ffmpeg n'a ecrit que {len(indices) - len(missing)} fichier(s) sur les "
            f"{len(indices)} frames demandees. Manquants (au plus 5 cites): "
            f"{missing[:5]}. Cause usuelle: un indice de frame source au-dela de la "
            "fin reelle du flux, ce que ffmpeg ignore sans code d'erreur. Le cardinal "
            "de frames source transmis a la selection etait probablement sur-estime."
        )
    return frame_paths


def _rejects_fps_mode(stderr: str) -> bool:
    """Le binaire a-t-il rejete `-fps_mode` (ffmpeg anterieur a 5.0) ?"""
    lowered = stderr.lower()
    return "fps_mode" in lowered and (
        "unrecognized option" in lowered
        or "option not found" in lowered
        or "invalid argument" in lowered
    )
