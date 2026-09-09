from __future__ import annotations

import inspect
import logging
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# La regle de regime -- « une reference de perimetre inatteignable est-elle un
# historique tronque, ou un AUTRE depot ? » -- vit dans `tests/_regime_du_depot.py`,
# ecrite une fois pour ses sept appelants.
sys.path.insert(0, str(REPO_ROOT / "tests"))
from _regime_du_depot import echoue_ou_saute  # noqa: E402
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import (
    cli,
    extraction,
    ffmpeg_utils,
    progression,
    scan_detect,
    scan_output_frames,
)


FRAME_NAME_PATTERN = re.compile(r"^frame_\d{4}\.png$")


requires_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None,
    reason="ffmpeg binary not available on PATH",
)


@pytest.fixture
def synthetic_video(tmp_path: Path) -> Path:
    video_path = tmp_path / "synthetic_source.mp4"
    command = [
        "ffmpeg",
        "-y",
        "-f", "lavfi",
        "-i", "color=c=red:s=64x64:d=2:r=10",
        str(video_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return video_path


@requires_ffmpeg
def test_extract_frames_produces_expected_naming(tmp_path: Path, synthetic_video: Path) -> None:
    output_dir = tmp_path / "frames"

    frames = ffmpeg_utils.extract_frames(synthetic_video, output_dir, fps=2)

    assert len(frames) >= 1
    for frame in frames:
        assert frame.parent == output_dir
        assert FRAME_NAME_PATTERN.match(frame.name)
    assert [frame.name for frame in frames] == sorted(frame.name for frame in frames)


def test_extract_frames_raises_for_missing_video(tmp_path: Path) -> None:
    missing_video = tmp_path / "does_not_exist.mp4"
    output_dir = tmp_path / "frames"

    with pytest.raises(FileNotFoundError):
        ffmpeg_utils.extract_frames(missing_video, output_dir, fps=2)


def test_ensure_ffmpeg_available_raises_for_unknown_binary() -> None:
    with pytest.raises(ffmpeg_utils.FfmpegNotFoundError):
        ffmpeg_utils.ensure_ffmpeg_available(ffmpeg_binary="ffmpeg-binary-that-does-not-exist")


# ===========================================================================
# Story 5.28 -- le canal de progression sur le chemin ffmpeg
#
# Regime de test NEUF (le seul qui mesure ce que la story ajoute) : un VRAI
# sous-processus, lance par `sys.executable`, qui ecrit de vrais fichiers a un
# rythme choisi et parle sur stderr. Il ne passe **pas** par
# `ensure_ffmpeg_available` : la resolution par `shutil.which` d'un script sans
# extension n'est pas portable sur Windows, qui est la machine de production.
# D'ou la couture `run_with_written_file_progress`, appelable seule.
# ===========================================================================


FAUX_FFMPEG = r"""
import os, sys, time

(dossier, motif, depart, nombre, pause, octets_stderr, code, marqueur,
 octets_bruts_hex) = sys.argv[1:10]
depart, nombre = int(depart), int(nombre)
octets_stderr, code = int(octets_stderr), int(code)
pause = float(pause)

os.makedirs(dossier, exist_ok=True)

# Le marqueur d'abord : c'est lui que `_rejects_fps_mode` doit retrouver, meme
# noye sous des centaines de kilo-octets de bavardage.
if marqueur:
    sys.stderr.write(marqueur + "\n")

# Des octets BRUTS, non decodables en UTF-8 : ffmpeg recopie le nom de fichier
# tel que l'OS le lui donne, et un rush accentue arrive en cp1252 sous Windows.
if octets_bruts_hex:
    sys.stderr.flush()
    sys.stderr.buffer.write(bytes.fromhex(octets_bruts_hex))
    sys.stderr.buffer.flush()

# Le deversement a lieu AVANT la premiere ecriture : sur un tube laisse sans
# vidange, le processus se bloquerait ici et aucun fichier ne tomberait jamais.
bruit = "bavardage d'encodage, ligne de remplissage sans interet\n"
ecrits = 0
while ecrits < octets_stderr:
    sys.stderr.write(bruit)
    ecrits += len(bruit)
sys.stderr.flush()

for rang in range(depart, depart + nombre):
    time.sleep(pause)
    chemin = os.path.join(dossier, motif % rang)
    with open(chemin, "wb") as sortie:
        sortie.write(b"faux tiff " + str(rang).encode("ascii"))

sys.exit(code)
"""


@pytest.fixture
def video_factice(tmp_path: Path) -> Path:
    """`extract_selected_frames` n'exige du chemin video que d'etre un fichier."""
    chemin = tmp_path / "rush_factice.mov"
    chemin.write_bytes(b"ce n'est pas une video, et personne ne la lit")
    return chemin


@pytest.fixture
def faux_binaire(monkeypatch):
    """Installer le faux ffmpeg et rendre la liste des commandes construites."""
    commandes: list[list[str]] = []

    def installer(*, nombre=None, pause=0.03, octets_stderr=0, code=0, marqueur="",
                  intervalle=0.005, octets_bruts=b""):
        monkeypatch.setattr(
            ffmpeg_utils, "ensure_ffmpeg_available", lambda b="ffmpeg": sys.executable
        )
        monkeypatch.setattr(
            ffmpeg_utils, "PROGRESSION_POLL_INTERVAL_SECONDS", intervalle
        )

        def construire(exe, video_path, chunk, output_pattern, start_rank):
            motif = Path(output_pattern)
            commande = [
                sys.executable, "-c", FAUX_FFMPEG,
                str(motif.parent),
                motif.name,
                str(start_rank),
                str(len(chunk) if nombre is None else nombre),
                str(pause),
                str(octets_stderr),
                str(code),
                marqueur,
                octets_bruts.hex(),
            ]
            commandes.append(commande)
            return commande

        monkeypatch.setattr(ffmpeg_utils, "build_frame_selection_command", construire)
        return commandes

    installer.commandes = commandes
    return installer


class Journal:
    """Rappel de progression de test."""

    def __init__(self, leve: bool = False) -> None:
        self.jalons: list[tuple[int, int]] = []
        self.leve = leve

    def __call__(self, faites, total):
        self.jalons.append((faites, total))
        if self.leve:
            raise RuntimeError("rappel fautif fourni par l'appelant")

    @property
    def paliers_intermediaires(self):
        return [(f, t) for f, t in self.jalons if 0 < f < t]


def _empreinte(dossier: Path):
    """Nom et contenu de chaque fichier -- l'artefact, pas son horodatage."""
    return sorted(
        (chemin.name, chemin.read_bytes())
        for chemin in sorted(Path(dossier).iterdir())
        if chemin.is_file()
    )


# --- AC 4 : la progression avance A L'INTERIEUR d'un unique appel ----------


def test_la_progression_avance_a_l_interieur_d_un_unique_appel_ffmpeg(
    tmp_path: Path, video_factice: Path, faux_binaire
) -> None:
    """AC 4 : un comptage par chunk ne produit aucun palier et echoue ici.

    Le lot tient largement sous `MAX_SELECT_TERMS_PER_INVOCATION` (1000), donc
    il n'y a **qu'un** appel ffmpeg : une progression par chunk sauterait de
    0 a 100 %.
    """
    commandes = faux_binaire(pause=0.03)
    indices = list(range(12))
    assert len(indices) < ffmpeg_utils.MAX_SELECT_TERMS_PER_INVOCATION

    journal = Journal()
    chemins = ffmpeg_utils.extract_selected_frames(
        video_factice, tmp_path / "tmp", indices, rappel_progression=journal
    )

    assert len(commandes) == 1, "le lot doit tenir dans un SEUL appel ffmpeg"
    assert len(chemins) == 12
    assert journal.paliers_intermediaires, (
        f"aucun palier intermediaire : {journal.jalons}"
    )
    assert journal.jalons[-1] == (12, 12)
    assert all(total == 12 for _, total in journal.jalons)


def test_les_comptes_bruts_sont_monotones_et_bornes(
    tmp_path: Path, video_factice: Path, faux_binaire, monkeypatch
) -> None:
    """AC 5 : le COMPTAGE ne recule pas et ne depasse pas le total.

    Mesure sur les comptes **bruts**, avant que `EmetteurProgression` ne les
    filtre. Asserter la monotonie sur les jalons emis ne mesurait rien : elle est
    vraie par construction de l'emetteur, qui refuse `faites <= self._dernier`
    **avant** d'appeler le rappel, si bien qu'aucune implementation du comptage
    ne pouvait faire tomber l'assertion (revue de vague 2 bis, BH-11). La borne,
    elle, mord : des residus hors plage sont poses ici expres.
    """
    faux_binaire(pause=0.02)
    dossier = tmp_path / "tmp"
    dossier.mkdir(parents=True)
    for rang in range(900, 906):
        ffmpeg_utils.temp_frame_path(dossier, rang).write_bytes(b"residu")

    bruts: list[int | None] = []
    vrai_comptage = ffmpeg_utils.count_written_temp_frames

    def comptage_trace(temp_dir, total=None, depuis=0):
        compte = vrai_comptage(temp_dir, total, depuis)
        bruts.append(compte)
        return compte

    monkeypatch.setattr(ffmpeg_utils, "count_written_temp_frames", comptage_trace)
    journal = Journal()
    ffmpeg_utils.extract_selected_frames(
        video_factice, dossier, list(range(10)), rappel_progression=journal
    )

    mesures = [compte for compte in bruts if compte is not None]
    assert mesures, "aucun comptage n'a eu lieu"
    assert mesures == sorted(mesures), f"le comptage a recule : {mesures}"
    assert all(compte <= 10 for compte in mesures), (
        f"le comptage a depasse le total malgre six residus hors plage : {mesures}"
    )
    assert journal.jalons[-1] == (10, 10)


def test_des_residus_hors_plage_ne_font_pas_monter_la_jauge_a_cent(
    tmp_path: Path, video_factice: Path, faux_binaire
) -> None:
    """EC-2, critique : la jauge annoncait 100 % pour ZERO fichier de la passe.

    `count_written_temp_frames` comptait **toutes** les entrees au motif, sans
    borne de rang ; la garde de comptage, elle, ne regarde que
    `range(len(indices))`. Les deux ne comptaient pas la meme chose. Dix residus
    aux rangs 900-909 et un ffmpeg qui n'ecrit rien donnaient `jalons =
    [(10, 10)]` pendant que la garde levait -- 100 % puis une erreur, soit le
    faux succes d'affichage qu'`EPIC7-ARB-79` existe pour interdire.

    Atteignable en production : `run_extraction` nettoie par
    `shutil.rmtree(temp_dir, ignore_errors=True)`, dont l'echec est
    **silencieux** -- regime ordinaire sous Windows quand un fichier est tenu.
    """
    faux_binaire(nombre=4, pause=0.01)
    dossier = tmp_path / "tmp"
    dossier.mkdir(parents=True)
    for rang in range(900, 910):
        ffmpeg_utils.temp_frame_path(dossier, rang).write_bytes(b"residu de la passe d'avant")

    journal = Journal()
    with pytest.raises(ffmpeg_utils.FrameExtractionError) as capture:
        ffmpeg_utils.extract_selected_frames(
            video_factice, dossier, list(range(10)), rappel_progression=journal
        )

    assert "ffmpeg n'a ecrit que 4 fichier(s) sur les 10 frames demandees" in str(
        capture.value
    )
    assert journal.jalons, "le canal doit avoir vu passer les 4 fichiers de la passe"
    assert journal.jalons[-1] == (4, 10), (
        f"le dernier jalon doit valoir le compte REEL de la passe : {journal.jalons}"
    )
    assert all(faites <= 4 for faites, _ in journal.jalons)


def test_le_comptage_borne_ignore_les_rangs_hors_de_la_passe(tmp_path: Path) -> None:
    """EC-2 : la borne est celle des rangs que la passe attend, `range(total)`."""
    dossier = tmp_path / "tmp"
    dossier.mkdir()
    for rang in (0, 1, 2):
        ffmpeg_utils.temp_frame_path(dossier, rang).write_bytes(b"de la passe")
    for rang in range(900, 910):
        ffmpeg_utils.temp_frame_path(dossier, rang).write_bytes(b"residu")

    assert ffmpeg_utils.count_written_temp_frames(dossier) == 13   # non borne
    assert ffmpeg_utils.count_written_temp_frames(dossier, 10) == 3
    assert ffmpeg_utils.count_written_temp_frames(dossier, 2) == 2


def test_le_comptage_borne_ne_liste_jamais_le_repertoire(
    tmp_path: Path, monkeypatch
) -> None:
    """BH-12 : le sondage est en O(avancee), pas en O(N) par tour.

    Un listage coute O(N) par sondage, donc O(N**2) sur la passe -- mesure a
    20,5 ms par comptage pour N = 8000, soit ~8 % d'un coeur a 4 Hz sur le
    repertoire meme ou ffmpeg ecrit, alors que l'invariant d'`EPIC7-ARB-79`
    interdit de « ralentir notablement le travail qu'elle observe ». Les noms
    etant deterministes, on sonde a partir du dernier compte connu.

    Mesure : `os.scandir` rendu explosif. Le comptage borne doit continuer de
    rendre le bon chiffre.
    """
    dossier = tmp_path / "tmp"
    dossier.mkdir()
    for rang in range(5):
        ffmpeg_utils.temp_frame_path(dossier, rang).write_bytes(b"de la passe")

    def scandir_interdit(*args, **kwargs):
        raise AssertionError("le comptage borne ne doit lister aucun repertoire")

    monkeypatch.setattr(ffmpeg_utils.os, "scandir", scandir_interdit)
    assert ffmpeg_utils.count_written_temp_frames(dossier, 10) == 5
    # Et la sonde repart du dernier compte connu, sans revoir les rangs deja vus.
    assert ffmpeg_utils.count_written_temp_frames(dossier, 10, 3) == 5


def test_le_comptage_borne_rend_None_sur_un_repertoire_illisible(tmp_path: Path) -> None:
    """AC 11 : borne ou non, un repertoire illisible donne `None`, jamais zero.

    Zero ferait reculer la jauge ; `None` la laisse ou elle est.
    """
    assert ffmpeg_utils.count_written_temp_frames(tmp_path / "absent", 10) is None
    assert ffmpeg_utils.count_written_temp_frames(None, 10) is None
    assert ffmpeg_utils.count_written_temp_frames(tmp_path / "absent") is None


# --- AC 5 et AC 12 : jamais force a 100 %, et la garde leve toujours -------


def test_un_lot_tronque_leve_toujours_et_le_dernier_jalon_reste_sous_le_total(
    tmp_path: Path, video_factice: Path, faux_binaire
) -> None:
    """AC 12 (`EPIC7-ARB-79`, interdit symetrique).

    ffmpeg n'ecrit que 3 fichiers sur 8 demandes et sort en 0 -- c'est le cas
    reel du cardinal source sur-estime. La garde de comptage doit lever, texte
    compris, **rappel branche**, et la jauge doit plafonner sous 100 % plutot
    que de masquer le defaut que cette garde existe pour lever (risque R12).
    """
    faux_binaire(nombre=3, pause=0.02)
    journal = Journal()

    with pytest.raises(ffmpeg_utils.FrameExtractionError) as capture:
        ffmpeg_utils.extract_selected_frames(
            video_factice, tmp_path / "tmp", list(range(8)),
            rappel_progression=journal,
        )

    message = str(capture.value)
    assert "ffmpeg n'a ecrit que 3 fichier(s) sur les 8 frames demandees" in message
    assert "sur-estime" in message
    assert journal.jalons, "le canal doit avoir vu passer les 3 fichiers ecrits"
    assert journal.jalons[-1] == (3, 8)
    assert journal.jalons[-1][0] < journal.jalons[-1][1]


def test_le_meme_lot_tronque_leve_le_meme_texte_sans_rappel(
    tmp_path: Path, video_factice: Path, faux_binaire
) -> None:
    """AC 12 : le texte de la garde ne depend pas de la presence du rappel."""
    faux_binaire(nombre=3, pause=0.0)
    with pytest.raises(ffmpeg_utils.FrameExtractionError) as sans:
        ffmpeg_utils.extract_selected_frames(
            video_factice, tmp_path / "sans", list(range(8))
        )
    with pytest.raises(ffmpeg_utils.FrameExtractionError) as avec:
        ffmpeg_utils.extract_selected_frames(
            video_factice, tmp_path / "avec", list(range(8)),
            rappel_progression=Journal(),
        )
    assert str(sans.value) == str(avec.value)


# --- Le piege de terrain : stderr volumineux -------------------------------


def test_un_ffmpeg_bavard_ne_bloque_jamais_l_extraction(
    tmp_path: Path, video_factice: Path, faux_binaire
) -> None:
    """Le seul test qui reproduise la panne de terrain du tube de stderr.

    Un `Popen(stderr=subprocess.PIPE)` non vidange se bloque des que le tampon
    du tube est plein (64 Kio) : le processus attend qu'on lise, la boucle de
    comptage attend qu'il finisse. Le faux binaire deverse **200 Kio** avant
    d'ecrire son premier fichier, donc un tube bloquerait avant toute ecriture.

    Faute de `pytest-timeout` au depot, la garde est un fil de surveillance :
    un blocage se solde par un echec borne, jamais par une suite suspendue.
    """
    faux_binaire(pause=0.01, octets_stderr=200 * 1024)
    journal = Journal()
    resultat: dict[str, object] = {}

    def executer():
        try:
            resultat["chemins"] = ffmpeg_utils.extract_selected_frames(
                video_factice, tmp_path / "tmp", list(range(6)),
                rappel_progression=journal,
            )
        except BaseException as erreur:  # noqa: BLE001 -- rapporte au fil principal
            resultat["erreur"] = erreur

    fil = threading.Thread(target=executer, daemon=True)
    fil.start()
    fil.join(timeout=60.0)

    assert not fil.is_alive(), (
        "l'extraction ne s'est pas terminee en 60 s : le tube de stderr est de "
        "retour (regression du piege documente en 5.28)"
    )
    assert "erreur" not in resultat, resultat.get("erreur")
    assert len(resultat["chemins"]) == 6
    assert journal.jalons[-1] == (6, 6)


def test_le_refus_de_fps_mode_survit_a_un_stderr_volumineux(
    tmp_path: Path, video_factice: Path, faux_binaire
) -> None:
    """AC 12 : le texte affiche verbatim par la GUI (P9) est inchange.

    Le marqueur est ecrit en tete puis noye sous 200 Kio : il ne se retrouve
    que si stderr a ete relu **en entier** apres la fin du processus.
    """
    faux_binaire(
        nombre=0, pause=0.0, octets_stderr=200 * 1024, code=1,
        marqueur="Unrecognized option 'fps_mode'.",
    )
    with pytest.raises(ffmpeg_utils.FrameExtractionError) as capture:
        ffmpeg_utils.extract_selected_frames(
            video_factice, tmp_path / "tmp", list(range(5)),
            rappel_progression=Journal(),
        )
    message = str(capture.value)
    assert "Cette version de ffmpeg ne connait pas l'option '-fps_mode'" in message
    assert "Version minimale exigee: ffmpeg 5.0" in message
    assert "Mettre a jour ffmpeg." in message
    assert "Unrecognized option 'fps_mode'." in message


def test_le_texte_de_l_echec_ffmpeg_generique_est_inchange(
    tmp_path: Path, video_factice: Path, faux_binaire
) -> None:
    """AC 12 : code de retour non nul, rangs cites, stderr joint."""
    faux_binaire(nombre=0, pause=0.0, code=3, marqueur="Invalid data found")
    with pytest.raises(ffmpeg_utils.FrameExtractionError) as capture:
        ffmpeg_utils.extract_selected_frames(
            video_factice, tmp_path / "tmp", list(range(5)),
            rappel_progression=Journal(),
        )
    message = str(capture.value)
    assert "Echec de l'extraction ffmpeg (code 3) sur les rangs 0 a 4" in message
    assert "Invalid data found" in message


# --- AC 8 / EC-3 / F8 : le repli `AR3` est le chemin d'AVANT --------------


def test_sans_rappel_l_extraction_ne_depend_pas_du_temporaire_systeme(
    tmp_path: Path, video_factice: Path, faux_binaire, monkeypatch
) -> None:
    """EC-3 et F8, critiques : le chemin non observe avait acquis une dependance.

    `tempfile.mkstemp` etait appele **inconditionnellement**, avant tout
    branchement sur `observe`. Le chemin « aucun rappel » -- celui de la CLI, le
    seul en production aujourd'hui -- dependait donc de l'ecrivabilite du
    repertoire temporaire **systeme**, ce que `subprocess.run(capture_output=True)`
    n'exigeait pas, et l'`OSError` remontait **nue**, hors de la hierarchie
    d'erreurs du module. L'AC 8 dit « le repli sans rappel est le comportement
    d'aujourd'hui » : il ne l'etait plus.

    « Ne pas casser le mecanisme fonctionnel pour une simple donnee de rendu »
    (Egan, `EPIC7-ARB-79`).
    """
    faux_binaire(pause=0.0)
    appels = {"n": 0}

    def mkstemp_casse(*args, **kwargs):
        appels["n"] += 1
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(ffmpeg_utils.tempfile, "mkstemp", mkstemp_casse)
    chemins = ffmpeg_utils.extract_selected_frames(
        video_factice, tmp_path / "tmp", list(range(3))
    )
    assert len(chemins) == 3
    assert appels["n"] == 0, (
        "le chemin sans rappel a touche au repertoire temporaire systeme"
    )


def test_sans_rappel_aucun_listage_du_repertoire_n_a_lieu(
    tmp_path: Path, video_factice: Path, faux_binaire, monkeypatch
) -> None:
    """BH-5, critique : « sans rappel, aucun listage » n'etait mesure par rien.

    Le mutant `observe = emetteur is not None and emetteur.actif` ->
    `observe = emetteur is not None` survivait a 153 tests sur 153 :
    `extract_selected_frames` construit **toujours** un emetteur, donc `observe`
    ne dependait que de `.actif`. Avec le mutant, le chemin CLI passait d'une
    attente bloquante a un sondage a 4 Hz du repertoire ou ffmpeg ecrit.
    """
    faux_binaire(pause=0.02)
    comptages = {"n": 0}
    vrai_comptage = ffmpeg_utils.count_written_temp_frames

    def comptage_trace(temp_dir, total=None, depuis=0):
        comptages["n"] += 1
        return vrai_comptage(temp_dir, total, depuis)

    monkeypatch.setattr(ffmpeg_utils, "count_written_temp_frames", comptage_trace)

    ffmpeg_utils.extract_selected_frames(
        video_factice, tmp_path / "sans", list(range(6))
    )
    assert comptages["n"] == 0, (
        f"{comptages['n']} comptage(s) sur le chemin sans rappel : le repli "
        "`AR3` s'est mis a scruter"
    )

    # Le temoin symetrique : avec un rappel, le comptage a bien lieu -- sans quoi
    # l'assertion ci-dessus serait vraie pour la mauvaise raison.
    ffmpeg_utils.extract_selected_frames(
        video_factice, tmp_path / "avec", list(range(6)),
        rappel_progression=Journal(),
    )
    assert comptages["n"] > 0

    # Et un rappel non appelable laisse l'emetteur INACTIF : c'est bien `.actif`,
    # pas la seule presence d'un emetteur, qui decide d'observer.
    comptages["n"] = 0
    ffmpeg_utils.extract_selected_frames(
        video_factice, tmp_path / "inerte", list(range(6)),
        rappel_progression="pas un rappel",
    )
    assert comptages["n"] == 0


#: Le nom d'un rush accentue, tel que l'OS le rend a ffmpeg sous Windows : du
#: cp1252, **non decodable en UTF-8**. C'est le cas ORDINAIRE chez Egan, pas un
#: cas tordu -- et le faux binaire du banc n'ecrivait que de l'ASCII.
STDERR_NON_UTF8 = b"Impossible d'ouvrir rush-\xe9t\xe9.mov"


@pytest.mark.parametrize("avec_rappel", [False, True], ids=["sans-rappel", "avec-rappel"])
def test_un_stderr_non_decodable_reste_une_FrameExtractionError(
    tmp_path: Path, video_factice: Path, faux_binaire, avec_rappel
) -> None:
    """BH-6, critique : `errors="replace"` n'etait epingle par aucun test.

    Le mutant `errors="replace"` -> `errors="strict"` survivait a 153/153 : le
    faux binaire n'ecrivait que de l'ASCII. Avec un rush accentue -- le cas
    ordinaire --, un echec ffmpeg benin devenait une `UnicodeDecodeError` **non
    typee, hors de `FrameExtractionError`**, remontee nue jusqu'a la CLI.

    Les **deux** branches sont mesurees : celle qui relit le fichier de stderr
    (rappel branche) et celle qui repasse par `capture_output=True` (repli
    `AR3`).
    """
    faux_binaire(nombre=0, pause=0.0, code=1, octets_bruts=STDERR_NON_UTF8)
    rappel = Journal() if avec_rappel else None

    with pytest.raises(ffmpeg_utils.FrameExtractionError) as capture:
        ffmpeg_utils.extract_selected_frames(
            video_factice, tmp_path / "tmp", list(range(4)),
            rappel_progression=rappel,
        )

    message = str(capture.value)
    assert "Echec de l'extraction ffmpeg (code 1)" in message
    assert "Impossible d'ouvrir rush-" in message
    assert ".mov" in message
    assert "\ufffd" in message, (
        "les octets non decodables doivent etre remplaces, pas faire lever"
    )


def test_les_deux_branches_rendent_le_meme_stderr_non_decodable(
    tmp_path: Path, video_factice: Path, faux_binaire
) -> None:
    """BH-6 et EC-3 : la relecture du fichier et `capture_output` decodent pareil.

    C'est ce qui autorise les deux `FrameExtractionError` a etre litteralement
    les memes des deux cotes, condition de l'AC 12 (« texte compris »).
    """
    faux_binaire(nombre=0, pause=0.0, code=1, octets_bruts=STDERR_NON_UTF8)
    with pytest.raises(ffmpeg_utils.FrameExtractionError) as sans:
        ffmpeg_utils.extract_selected_frames(
            video_factice, tmp_path / "sans", list(range(4))
        )
    with pytest.raises(ffmpeg_utils.FrameExtractionError) as avec:
        ffmpeg_utils.extract_selected_frames(
            video_factice, tmp_path / "avec", list(range(4)),
            rappel_progression=Journal(),
        )
    assert str(sans.value) == str(avec.value)


# --- AC 11 : la progression est OBSERVATIONNELLE ---------------------------


def test_un_rappel_qui_leve_ne_change_ni_les_artefacts_ni_l_issue(
    tmp_path: Path, video_factice: Path, faux_binaire, caplog
) -> None:
    """AC 11 : l'exception du rappel ne remonte pas, et le journal ne noie pas."""
    faux_binaire(pause=0.005)
    indices = list(range(20))

    temoin = ffmpeg_utils.extract_selected_frames(
        video_factice, tmp_path / "sans", indices
    )
    journal = Journal(leve=True)
    with caplog.at_level(logging.WARNING):
        mesure = ffmpeg_utils.extract_selected_frames(
            video_factice, tmp_path / "avec", indices, rappel_progression=journal
        )

    assert [chemin.name for chemin in mesure] == [chemin.name for chemin in temoin]
    assert _empreinte(tmp_path / "avec") == _empreinte(tmp_path / "sans")
    assert journal.jalons, "le rappel a bien ete appele malgre ses levees"
    avertissements = [
        enregistrement for enregistrement in caplog.records
        if enregistrement.name == "mixed_media_utility.progression"
    ]
    assert len(avertissements) == 1, (
        f"{len(avertissements)} avertissements pour {len(journal.jalons)} jalons "
        "fautifs : un rappel fautif noierait le journal"
    )


def test_un_comptage_impossible_ne_leve_pas_et_ne_recule_pas() -> None:
    """AC 11 : un repertoire non listable rend `None`, jamais zero ni une erreur."""
    assert ffmpeg_utils.count_written_temp_frames("/repertoire/qui/n/existe/pas") is None
    assert ffmpeg_utils.count_written_temp_frames(None) is None


def test_un_comptage_impossible_donne_moins_de_jalons_jamais_une_erreur(
    tmp_path: Path, video_factice: Path, faux_binaire, monkeypatch
) -> None:
    """AC 11 : le travail observe aboutit normalement, sans aucun jalon."""
    faux_binaire(pause=0.01)
    monkeypatch.setattr(
        ffmpeg_utils, "count_written_temp_frames",
        lambda dossier, total=None, depuis=0: None,
    )
    journal = Journal()
    chemins = ffmpeg_utils.extract_selected_frames(
        video_factice, tmp_path / "tmp", list(range(8)), rappel_progression=journal
    )
    assert len(chemins) == 8
    assert journal.jalons == []


def test_une_course_du_comptage_donne_moins_de_jalons_sans_recul(
    tmp_path: Path, video_factice: Path, faux_binaire, monkeypatch
) -> None:
    """AC 11 : des scrutations perdues -- moins de jalons, jamais un recul.

    Les scrutations 2 et 4 echouent, les suivantes non : le comptage **final**,
    celui qui a lieu apres la fin du processus, doit rester exact. Faire echouer
    une scrutation sur deux jusqu'au bout rendrait ce dernier comptage
    dependant de la parite du nombre de tours, c'est-a-dire du temps qu'a mis la
    machine -- un test qui echoue une fois sur deux ne mesure rien.
    """
    faux_binaire(pause=0.03)
    vrai_comptage = ffmpeg_utils.count_written_temp_frames
    tours = {"n": 0}

    def comptage_capricieux(dossier, total=None, depuis=0):
        tours["n"] += 1
        if tours["n"] in (2, 4):
            return None
        return vrai_comptage(dossier, total, depuis)

    monkeypatch.setattr(ffmpeg_utils, "count_written_temp_frames", comptage_capricieux)
    journal = Journal()
    chemins = ffmpeg_utils.extract_selected_frames(
        video_factice, tmp_path / "tmp", list(range(10)), rappel_progression=journal
    )
    assert len(chemins) == 10
    assert tours["n"] > 4, (
        f"seulement {tours['n']} scrutation(s) : les deux echecs injectes ne "
        "sont pas tous les deux tombes en cours de route"
    )
    # La monotonie des jalons emis est vraie par construction de
    # `EmetteurProgression` (mesuree dans `test_progression.py`) : l'asserter ici
    # ne mesurait rien (BH-11). Ce qui se mesure, c'est que des scrutations
    # perdues n'empechent pas le compte FINAL d'etre exact.
    assert journal.jalons[-1] == (10, 10)


def test_les_artefacts_sont_identiques_avec_et_sans_rappel(
    tmp_path: Path, video_factice: Path, faux_binaire
) -> None:
    """AC 8 et AC 11 : memes fichiers, memes noms, memes octets."""
    faux_binaire(pause=0.005)
    indices = [0, 3, 7, 11, 12, 20, 21]

    sans = ffmpeg_utils.extract_selected_frames(
        video_factice, tmp_path / "sans", indices
    )
    avec = ffmpeg_utils.extract_selected_frames(
        video_factice, tmp_path / "avec", indices, rappel_progression=Journal()
    )
    assert [chemin.name for chemin in sans] == [chemin.name for chemin in avec]
    assert _empreinte(tmp_path / "sans") == _empreinte(tmp_path / "avec")


def test_le_comptage_ne_compte_que_les_fichiers_temporaires_du_motif(
    tmp_path: Path
) -> None:
    """Un fichier etranger au motif ne gonfle pas la jauge.

    Les deux moities du filtre sont exercees separement : `note.txt` et le
    `.log` echouent sur le **suffixe**, `planche_00000003.tiff` echoue sur le
    **prefixe**. Sans ce dernier cas, un `.tiff` etranger depose dans le
    temporaire gonflait la jauge sans qu'aucun test ne le voie (revue de vague
    2 bis, BH-10).
    """
    dossier = tmp_path / "tmp"
    dossier.mkdir()
    ffmpeg_utils.temp_frame_path(dossier, 0).write_bytes(b"a")
    ffmpeg_utils.temp_frame_path(dossier, 7).write_bytes(b"b")
    (dossier / "note.txt").write_bytes(b"c")
    (dossier / "mmu_extract_00000009.log").write_bytes(b"d")
    (dossier / "planche_00000003.tiff").write_bytes(b"e")
    assert ffmpeg_utils.count_written_temp_frames(dossier) == 2


# --- AC 9 : aucun processus laisse vivant ---------------------------------


def test_aucun_processus_ne_survit_a_l_appel(
    tmp_path: Path, video_factice: Path, faux_binaire, monkeypatch
) -> None:
    """AC 9 : la couture ne laisse rien tourner derriere elle."""
    faux_binaire(pause=0.01)
    instances: list[subprocess.Popen] = []
    vrai_popen = subprocess.Popen

    class PopenTracant(vrai_popen):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            instances.append(self)

    monkeypatch.setattr(ffmpeg_utils.subprocess, "Popen", PopenTracant)
    ffmpeg_utils.extract_selected_frames(
        video_factice, tmp_path / "tmp", list(range(6)), rappel_progression=Journal()
    )
    assert instances
    assert all(processus.poll() is not None for processus in instances)


def test_une_panne_de_la_scrutation_est_absorbee_et_le_travail_aboutit(
    tmp_path: Path, video_factice: Path, faux_binaire, monkeypatch, caplog
) -> None:
    """AC 11 : « une course quelconque du fil d'observation » n'a AUCUN effet.

    Le banc codifiait exactement l'inverse : il exigeait qu'une panne survenue
    **dans la boucle de scrutation** fasse echouer `extract_selected_frames`
    (revue de vague 2 bis, F7). Or ce chemin n'existe que rappel branche : le
    canal pouvait litteralement casser ce qu'il observe, pour une donnee de
    rendu. La boucle absorbe donc, comme le reste du canal, et retombe sur
    l'attente bloquante -- c'est-a-dire sur le chemin du repli `AR3`.

    La propriete « aucun processus orphelin » est conservee : c'est elle qui
    compte dans le `finally`.
    """
    faux_binaire(pause=0.02)
    instances: list[subprocess.Popen] = []
    vrai_popen = subprocess.Popen

    class PopenExplosif(vrai_popen):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.deja_explose = False
            instances.append(self)

        def wait(self, timeout=None):
            # Seule la scrutation explose ; l'attente bloquante, celle que le
            # repli `AR3` emprunte aussi, doit rester possible.
            if timeout is not None and not self.deja_explose:
                self.deja_explose = True
                raise RuntimeError("panne au milieu de la scrutation")
            return super().wait(timeout=timeout)

    monkeypatch.setattr(ffmpeg_utils.subprocess, "Popen", PopenExplosif)
    journal = Journal()
    with caplog.at_level(logging.WARNING):
        chemins = ffmpeg_utils.extract_selected_frames(
            video_factice, tmp_path / "tmp", list(range(6)),
            rappel_progression=journal,
        )

    assert len(chemins) == 6, "le travail observe doit aboutir normalement"
    assert instances and all(processus.deja_explose for processus in instances)
    assert all(processus.poll() is not None for processus in instances)
    # Moins de jalons, jamais une erreur : le comptage final, lui, a lieu.
    assert journal.jalons[-1] == (6, 6)
    avertissements = [
        enregistrement for enregistrement in caplog.records
        if enregistrement.name == ffmpeg_utils.__name__
    ]
    assert len(avertissements) == 1, (
        f"{len(avertissements)} avertissements : la panne de scrutation se "
        "journalise une fois, pas a chaque tour"
    )


def test_aucun_processus_ne_survit_a_une_interruption(
    tmp_path: Path, video_factice: Path, faux_binaire, monkeypatch
) -> None:
    """AC 9 : le `finally` tient, y compris apres une exception qui traverse.

    `KeyboardInterrupt` derive de `BaseException` : elle n'est **pas** absorbee
    par la boucle de scrutation -- une interruption clavier n'est pas une course
    du canal --, elle traverse, et c'est justement ce qui met le `finally` a
    l'epreuve.
    """
    faux_binaire(pause=0.5)
    instances: list[subprocess.Popen] = []
    vrai_popen = subprocess.Popen

    class PopenTracant(vrai_popen):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            instances.append(self)

    def comptage_interrompu(temp_dir, total=None, depuis=0):
        raise KeyboardInterrupt("interruption clavier au milieu de la scrutation")

    monkeypatch.setattr(ffmpeg_utils.subprocess, "Popen", PopenTracant)
    monkeypatch.setattr(ffmpeg_utils, "count_written_temp_frames", comptage_interrompu)
    with pytest.raises(KeyboardInterrupt):
        ffmpeg_utils.extract_selected_frames(
            video_factice, tmp_path / "tmp", list(range(6)),
            rappel_progression=Journal(),
        )
    assert instances
    assert all(processus.poll() is not None for processus in instances)


# --- AC 7 : deux lots distinguables, cible en seconde position ------------


LOTS_DE_PROGRESSION = [
    ("lot_court", [0, 2, 4, 6, 8]),                       # 5 frames
    ("lot_vise", [1, 3, 5, 7, 9, 11, 13, 15, 17]),        # 9 frames -- LA CIBLE
]


@pytest.fixture(params=["ordre-nominal", "permute"])
def deux_lots(request):
    """Deux lots de cardinaux DIFFERENTS ; la cible n'est pas la premiere.

    La variante permutee est ce qui donne leur valeur aux deux points
    precedents : un emetteur qui rendrait toujours le total du **premier** lot,
    ou un denominateur fige d'un lot a l'autre, ne peut pas passer les deux
    ordres a la fois.
    """
    if request.param == "permute":
        return list(reversed(LOTS_DE_PROGRESSION))
    return list(LOTS_DE_PROGRESSION)


def test_chaque_lot_porte_son_propre_total_quel_que_soit_son_rang(
    tmp_path: Path, video_factice: Path, faux_binaire, deux_lots
) -> None:
    """AC 7 : le denominateur suit le lot extrait, jamais le premier vu."""
    faux_binaire(pause=0.005)
    assert len(deux_lots[0][1]) != len(deux_lots[1][1]), (
        "la fabrique doit produire deux lots DISTINGUABLES"
    )

    vise = dict(deux_lots)["lot_vise"]
    totaux_observes = {}
    for nom, indices in deux_lots:
        journal = Journal()
        ffmpeg_utils.extract_selected_frames(
            video_factice, tmp_path / nom, indices, rappel_progression=journal
        )
        assert journal.jalons[-1] == (len(indices), len(indices))
        totaux_observes[nom] = {total for _, total in journal.jalons}
        assert totaux_observes[nom] == {len(indices)}

    assert totaux_observes["lot_vise"] == {len(vise)}
    assert totaux_observes["lot_court"] != totaux_observes["lot_vise"]


# --- AC 8 : le rappel reste optionnel de bout en bout ---------------------


def test_le_rappel_de_progression_est_partout_un_mot_cle_a_defaut_None() -> None:
    """AC 8 (`AR3`) : aucune signature n'acquiert de parametre OBLIGATOIRE."""
    surfaces = [
        ffmpeg_utils.extract_selected_frames,
        extraction.run_extraction,
        scan_output_frames.write_lot_output_frames,
    ]
    for fonction in surfaces:
        parametres = inspect.signature(fonction).parameters
        assert "rappel_progression" in parametres, fonction.__name__
        parametre = parametres["rappel_progression"]
        assert parametre.default is None, fonction.__name__
        assert parametre.kind is inspect.Parameter.KEYWORD_ONLY, fonction.__name__


def test_la_cli_ne_passe_aucun_rappel_de_progression() -> None:
    """AC 8 : la CLI ne change pas -- aucune option, aucun libelle."""
    source = Path(cli.__file__).read_text(encoding="utf-8")
    assert "rappel_progression" not in source


def test_run_scan_detect_porte_LE_MEME_contrat_de_rappel_et_PAS_UN_SECOND() -> None:
    """Ce banc a change de sens le 2026-08-30, et l'histoire compte.

    **Ce qu'il mesurait, et pourquoi c'etait juste a l'epoque.** Il refusait a
    `run_scan_detect` tout parametre `rappel_progression`, sous le motif « 5.28
    emet sur les taches d'extraction, pas sur `scan detect` ». C'etait une
    **frontiere de perimetre de la story 5.28** -- une garde qui empeche une
    story de deborder --, pas un interdit d'architecture. Elle a fait son
    travail : le perimetre de 5.28 n'a pas glisse.

    **Pourquoi il change.** La story 11.4b, AC 9.2, exige verbatim l'inverse :
    « La detection recoit un canal du **meme contrat** (`EmetteurProgression`),
    **aucun second mecanisme**. » L'interface a besoin de montrer l'avancement
    des deux temps du scan ; refuser le canal a la detection obligerait a en
    inventer un second, ce que la meme phrase interdit.

    **Une frontiere de perimetre perimee ne se supprime pas, elle se retourne.**
    Ce que 5.28 protegeait vraiment, c'est qu'il n'existe **qu'un** mecanisme de
    progression dans le depot. Ce banc mesure donc desormais cela : le parametre
    existe, il porte **exactement** la meme forme que les trois autres surfaces
    (mot-cle, defaut `None`), et c'est ce qui rend impossible le « second
    mecanisme » -- une signature divergente serait le premier signe qu'on en
    fabrique un.

    **Et il garde son volet negatif** : `AR3` veut que le rappel reste
    optionnel, donc l'absence de defaut serait une regression. C'est la moitie
    qui a coute un bloquant cote extraction le 2026-08-30 -- un rappel dont le
    contrat n'est pas tenu s'eteint **en silence**, sans lever, barre figee a
    `0/N`.
    """
    parametres = inspect.signature(scan_detect.run_scan_detect).parameters
    assert "rappel_progression" in parametres, (
        "la detection a perdu son canal de progression : l'AC 9.2 de la 11.4b "
        "exige qu'elle en porte un, et du MEME contrat que l'extraction")
    parametre = parametres["rappel_progression"]
    assert parametre.default is None, (
        "le rappel de la detection est devenu obligatoire : `AR3` veut qu'il "
        "reste optionnel et que son absence ne change rien")
    assert parametre.kind is inspect.Parameter.KEYWORD_ONLY

    # Le « meme contrat », mesure et non affirme : la forme est identique a
    # celle des trois surfaces d'extraction, celles-la memes que le banc
    # `test_le_rappel_de_progression_est_partout_un_mot_cle_a_defaut_None`
    # verrouille juste au-dessus. Deux formes divergentes seraient exactement
    # le « second mecanisme » que l'AC 9.2 interdit.
    for autre in (ffmpeg_utils.extract_selected_frames, extraction.run_extraction,
                  scan_output_frames.write_lot_output_frames):
        reference = inspect.signature(autre).parameters["rappel_progression"]
        assert parametre.kind is reference.kind, autre.__name__
        assert parametre.default is reference.default, autre.__name__


# --------------------------------------------------------------------------
# AC 9 : les frontieres de perimetre, mesurees sur le diff REEL de la story
# --------------------------------------------------------------------------
#
# `grep -n "git"` sur les quatre bancs de 5.28 rendait **zero** : les trois
# interdits « hors du diff » de l'AC 9 n'etaient mesures par rien (revue de
# vague 2 bis, F6). Le substitut existant,
# `test_run_scan_detect_n_acquiert_aucun_rappel`, mesure une **signature**, pas
# l'absence du fichier dans le diff : toute modification de `scan_detect.py`
# n'ajoutant pas ce parametre passerait.
#
# Meme gabarit que 5.27 (`test_scan_detection_codes_de_refus.py`), et pour la
# meme raison mesuree la-bas : la borne haute `HEAD` a cesse d'etre juste des
# qu'un autre agent a commite sur la meme branche. La frontiere porte donc sur
# les fichiers des commits **de cette story**, reperes par le prefixe de leur
# sujet.

#: `baseline_commit` de la fiche 5.28.
_BASELINE_5_28 = "16f8fb3"

#: Prefixe de sujet des commits de cette story.
_PREFIXE_5_28 = "5.28"

#: Les seuls fichiers de production que cette story a le droit de toucher.
_PRODUCTION_5_28 = frozenset(
    {
        "src/mixed_media_utility/progression.py",
        "src/mixed_media_utility/ffmpeg_utils.py",
        "src/mixed_media_utility/extraction.py",
        "src/mixed_media_utility/scan_output_frames.py",
    }
)

#: Les interdits de l'AC 9, par prefixe de chemin, avec leur motif.
_INTERDITS_5_28: tuple[tuple[str, str], ...] = (
    (
        "src/mixed_media_utility/gui/",
        "l'affichage est en 7.6 ; `tache_de_demonstration` et le contrat de "
        "jalons de 7.0 ne bougent pas",
    ),
    ("tests/unit/gui/", "meme motif : aucune ligne de GUI dans cette story"),
    (
        "src/mixed_media_utility/scan_detect.py",
        "7.3 est `done` et son grep « zero temps restant » doit rester a zero ; "
        "`run_scan_detect` n'acquiert AUCUN rappel",
    ),
    (
        "src/mixed_media_utility/color_calibration.py",
        "chemin fragile intact : `scan write` emet AUTOUR de l'appel a "
        "`export_frame_tiff16`, jamais dedans",
    ),
    ("src/mixed_media_utility/color_pipeline.py", "meme motif, chemin fragile"),
    (
        "pyproject.toml",
        "la section [tool.mutmut] s'edite localement et ne se commite jamais "
        "scopee a une story",
    ),
)


def _sujets_et_fichiers_depuis(baseline: str):
    """`(sujet, chemins)` de chaque commit depuis `baseline`, ou echec nomme.

    Un `skip` se lirait comme un vert dans le total : si git est absent ou le
    baseline inatteignable, la frontiere ne s'evalue pas et il faut le dire.
    """
    try:
        sortie = subprocess.run(
            ["git", "log", "--name-only", "--format=%x00%s", f"{baseline}..HEAD"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True, timeout=60,
        ).stdout
    except (subprocess.SubprocessError, OSError) as error:
        echoue_ou_saute(
            REPO_ROOT, baseline,
            f"commit de reference {baseline} inatteignable ({error}) : la "
            "frontiere de perimetre ne s'evalue pas, et un skip se lirait comme "
            "un vert. Arbre exporte, historique tronque ou clone superficiel "
            "(`git fetch --unshallow`)"
        )
    commits: list[tuple[str, list[str]]] = []
    for ligne in sortie.splitlines():
        if ligne.startswith("\x00"):
            commits.append((ligne[1:], []))
        elif commits and ligne.strip():
            commits[-1][1].append(ligne.strip())
    return commits


def _fichiers_des_commits_de_la_story() -> list[str]:
    """Les chemins touches par les commits de sujet `5.28`."""
    chemins: list[str] = []
    for sujet, fichiers in _sujets_et_fichiers_depuis(_BASELINE_5_28):
        if sujet.startswith(_PREFIXE_5_28):
            chemins.extend(fichiers)
    return chemins


def test_la_story_ne_touche_aucun_module_de_production_hors_de_son_perimetre() -> None:
    """AC 9, frontiere de perimetre sur le diff de production de la story."""
    chemins = _fichiers_des_commits_de_la_story()
    assert chemins, (
        "aucun commit de la story 5.28 dans l'historique depuis le baseline : la "
        "frontiere ne mesurerait rien"
    )
    production = {chemin for chemin in chemins if chemin.startswith("src/")}
    assert production == set(_PRODUCTION_5_28), {
        "en trop": sorted(production - _PRODUCTION_5_28),
        "annonces et non touches": sorted(_PRODUCTION_5_28 - production),
    }


@pytest.mark.parametrize(
    "interdit, motif", _INTERDITS_5_28, ids=[i for i, _m in _INTERDITS_5_28]
)
def test_les_chemins_interdits_restent_hors_du_diff(interdit, motif) -> None:
    """AC 9 : les trois greps « hors du diff », mesures sur le diff reel."""
    chemins = _fichiers_des_commits_de_la_story()
    fautifs = [chemin for chemin in chemins if chemin.startswith(interdit)]
    assert fautifs == [], f"{interdit} doit rester hors du diff -- {motif}"


def test_la_frontiere_de_perimetre_de_5_28_mord_dans_les_deux_sens() -> None:
    """Le second volet : la frontiere **echoue** quand elle doit.

    Aucune assertion sur une constante litterale du test ici : celles-la sont
    vraies quel que soit l'etat du depot, et la revue de 5.27 les a nommees
    (F3). Ce qui est mesure, c'est que le **filtre par sujet selectionne
    reellement**, et que les deux interdits GUI sont bien des interdits
    atteignables -- l'historique depuis le baseline en porte, venus des autres
    agents de la branche. Sans cela, `test_les_chemins_interdits_restent_hors_du_diff`
    serait vert et vide.
    """
    commits = _sujets_et_fichiers_depuis(_BASELINE_5_28)
    a_moi = _fichiers_des_commits_de_la_story()
    tous = [chemin for _sujet, fichiers in commits for chemin in fichiers]
    assert a_moi, "aucun commit de sujet 5.28"
    assert set(a_moi) < set(tous), (
        "le filtre par sujet ne retient pas STRICTEMENT moins que l'historique "
        "complet : il ne filtre donc rien, et la frontiere est vide de sens"
    )

    # Le meme releve, retargete sur le prefixe d'un autre agent de la branche,
    # doit faire tomber les deux interdits GUI : c'est la preuve que ces deux
    # assertions peuvent echouer.
    autres = [
        chemin
        for sujet, fichiers in commits
        if sujet.startswith("passe de chrome")
        for chemin in fichiers
    ]
    assert autres, (
        "aucun commit d'un autre agent depuis le baseline : la contre-epreuve "
        "ne peut pas se faire"
    )
    for interdit in ("src/mixed_media_utility/gui/", "tests/unit/gui/"):
        assert any(chemin.startswith(interdit) for chemin in autres), (
            f"{interdit} n'apparait nulle part dans l'historique : l'interdit "
            "correspondant serait vert sans rien garantir"
        )
        assert not any(chemin.startswith(interdit) for chemin in a_moi)


def test_aucune_dependance_au_flux_de_progression_de_ffmpeg() -> None:
    """AC 9 : grep de frontiere sur le format de sortie de ffmpeg.

    Le depot paie deja `_rejects_fps_mode` sur une option absente selon les
    versions ; dependre du format de `-progress` rouvrirait la meme famille de
    panne. La scrutation compte des **fichiers**, elle ne lit rien de ffmpeg.
    """
    source = Path(ffmpeg_utils.__file__).read_text(encoding="utf-8")
    # L'option n'est jamais passee : cherchee sous sa forme de litteral, la
    # seule par laquelle elle atteindrait une ligne de commande. Les mentions
    # en commentaire, elles, disent precisement pourquoi on ne l'utilise pas.
    for litteral in ('"-progress"', "'-progress'"):
        assert litteral not in source, f"option passee a ffmpeg : {litteral}"
    for analyse in ("frame=", "out_time", "progress=end"):
        assert analyse not in source, f"analyse du flux ffmpeg trouvee : {analyse}"

    # Et la commande reellement construite n'en porte pas trace.
    commande = ffmpeg_utils.build_frame_selection_command(
        "ffmpeg", Path("rush.mov"), [0, 1, 2], Path("tmp") / "motif_%08d.tiff", 0
    )
    assert not any("progress" in str(terme) for terme in commande)


def test_la_progression_reste_globale_a_travers_plusieurs_appels_ffmpeg(
    tmp_path: Path, video_factice: Path, faux_binaire
) -> None:
    """Le decoupage en chunks ne fait jamais repartir la jauge de zero.

    `-start_number` donne aux fichiers leur rang de sortie **global** et le
    comptage porte sur tout le repertoire : trois appels successifs doivent
    produire une seule course monotone de 1 a 7, jamais trois courses de 1 a 3.
    """
    commandes = faux_binaire(pause=0.01)
    indices = [0, 2, 4, 6, 8, 10, 12]
    journal = Journal()
    chemins = ffmpeg_utils.extract_selected_frames(
        video_factice, tmp_path / "tmp", indices,
        max_select_terms=3, rappel_progression=journal,
    )
    assert len(commandes) == 3, "trois chunks attendus pour 7 indices par 3"
    assert len(chemins) == 7
    faits = [faites for faites, _ in journal.jalons]
    assert faits == sorted(faits)
    assert len(set(faits)) == len(faits)
    assert all(total == 7 for _, total in journal.jalons)
    assert journal.jalons[-1] == (7, 7)
    assert max(faits) == 7


def test_un_intervalle_de_scrutation_aberrant_retombe_sur_la_constante(
    tmp_path: Path, video_factice: Path, faux_binaire, monkeypatch
) -> None:
    """Un intervalle nul brulerait le processeur, un negatif leverait.

    La couture retombe alors sur la constante nommee du module plutot que de
    faire echouer le travail observe. `+inf` traversait la garde `not interval >
    0` puis **tuait l'extraction** depuis `subprocess._wait`, qui calcule
    `int(timeout * 1000)` et leve `OverflowError` ; une chaine levait sur le
    `float()`. Deux fois une exception venue d'un parametre dont le seul role est
    l'observation (revue de vague 2 bis, EC-7).
    """
    faux_binaire(pause=0.05)
    dossier = tmp_path / "tmp"
    dossier.mkdir()
    commande = [
        sys.executable, "-c", FAUX_FFMPEG,
        str(dossier), ffmpeg_utils.EXTRACT_TEMP_PATTERN,
        "0", "4", "0.05", "0", "0", "", "",
    ]
    for aberrant in (0, -1.0, float("inf"), float("-inf"), float("nan"), "rapide"):
        for chemin in dossier.iterdir():
            chemin.unlink()
        journal = Journal()
        emetteur = progression.EmetteurProgression(journal, 4)
        returncode, stderr = ffmpeg_utils.run_with_written_file_progress(
            commande, dossier, emetteur=emetteur, poll_interval=aberrant
        )
        assert returncode == 0
        assert stderr == ""
        assert journal.jalons[-1] == (4, 4)
        # La scrutation doit avoir REELLEMENT eu lieu a la cadence de la
        # constante : sans cette assertion, une garde absente serait rattrapee
        # par l'absorption de la boucle -- l'extraction aboutirait quand meme,
        # mais en attente bloquante, sans aucun palier intermediaire, et le
        # correctif d'EC-7 ne serait mesure par rien.
        assert journal.paliers_intermediaires, (
            f"poll_interval={aberrant!r} : aucun palier intermediaire, la "
            f"scrutation n'a pas retrouve la constante ({journal.jalons})"
        )


def test_la_couture_rend_le_stderr_relu_apres_la_fin_du_processus(
    tmp_path: Path
) -> None:
    """La couture est appelable seule et rend `(returncode, stderr)`."""
    dossier = tmp_path / "tmp"
    dossier.mkdir()
    commande = [
        sys.executable, "-c", FAUX_FFMPEG,
        str(dossier), ffmpeg_utils.EXTRACT_TEMP_PATTERN,
        "0", "1", "0.0", "0", "7", "un mot du binaire", "",
    ]
    returncode, stderr = ffmpeg_utils.run_with_written_file_progress(
        commande, dossier
    )
    assert returncode == 7
    assert "un mot du binaire" in stderr
    assert ffmpeg_utils.count_written_temp_frames(dossier) == 1
