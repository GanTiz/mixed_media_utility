# -*- coding: utf-8 -*-
"""Story 11.4, lots `E6` a `E9` -- juger, executer, conclure, et le cablage.

Trois regles de mesure heritees des stories precedentes de l'epic :

* le banc n'a **ni pilote de terminal ni ecran** : les mesures de couture
  portent sur l'identite des ecrans montes, jamais sur `app.rang` seul ;
* tout test parametre porte les **deux** regimes, `ascii_seul=False` **et**
  `True` ;
* le point d'entree est **execute**, jamais relu -- « un script qui contient la
  bonne ligne et un script dont le reglage atteint l'interpreteur ne sont pas la
  meme chose » (`test_lanceur.py`).
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from mixed_media_utility import extraction
from mixed_media_utility.gui.depot_projets import creer_projet
from mixed_media_utility.io.extraction_manifest import (
    LotStateConflictError,
    MANIFEST_FILENAME,
)
from mixed_media_utility.io.naming import CANONICAL_ID_MAX_LENGTH, build_lot_id
# **Le nom du dossier des frames extraites se LIT, il ne se recopie pas.**
# Story 11.14 (`EPIC11-ARB-220`) : `frames/` est devenu
# `extract-frames/`, et les quatre litteraux que ce banc portait en dur
# ont fabrique quatre rouges qui n'etaient PAS des regressions du
# produit -- l'ecran, lui, derivait deja son chemin du coeur.
from mixed_media_utility.io.project_layout import EXTRACT_FRAMES_DIRNAME
from mixed_media_utility.tui import atelier_extraction_ecriture as atelier
from mixed_media_utility.tui import jetons, projet_lecture
from mixed_media_utility.tui.coque import (
    Contexte,
    CoqueTui,
    EcranPasEncore,
    PalierTemoin,
)
from mixed_media_utility.tui.execution import (
    EcranEcrasement,
    EcranRefus,
    EcranResultat,
    PanneauConfirmation,
    SurfaceExecution,
)
from mixed_media_utility.tui.panneau import MENTION_MAJORANT

#: Les valeurs que `E2-3` et `E2-5` DESSINENT, nommees ici une seule fois.
#: Elles etaient tapees en clair, donc recopiees d'un dessin que ce banc
#: citait sans jamais l'ouvrir. Confrontees a leur source en fin de fichier.
BORNES_DESSINEES = "00:00:04:12 → 00:00:09:08"
SOMME_DESSINEE = "124 + 42 = 166"
RACCOURCI_DU_JOURNAL = "Tab journal"

#: Les deux regimes, portes par tout test qui touche au rendu.
MODES = [pytest.param(False, id="utf8"), pytest.param(True, id="ascii")]

requires_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="binaires ffmpeg/ffprobe absents du PATH",
)


class JournalMuet:
    """Un logger minimal : `run_extraction` en exige un, on n'en lit rien."""

    def info(self, *args, **kwargs) -> None:
        pass

    warning = error = debug = info


# ---------------------------------------------------------------------------
# Fabriques. **Deux elements distinguables au minimum**, et la cible ailleurs
# qu'en premiere position -- regle des fabriques de `CLAUDE.md`.
# ---------------------------------------------------------------------------

#: Deux cadences a comptes DIFFERENTS. Un remplissage uniforme rendrait
#: invisible toute inversion d'appariement entre une cadence et son compte.
DEUX_CADENCES = ((25.0, 124), (12.5, 42))

#: Trois cadences, pour la boucle multi-lot : l'echec se provoque sur la
#: DEUXIEME, jamais sur la premiere.
TROIS_CADENCES = ((25.0, 124), (12.5, 42), (5.0, 17))


def projet(tmp_path, nom="projet_demo", lots=()) -> Path:
    """Un projet reel, cree par le coeur, dont on complete le manifeste."""
    chemin = creer_projet(tmp_path, nom).chemin
    if lots:
        document = json.loads(
            (chemin / MANIFEST_FILENAME).read_text(encoding="utf-8"))
        document["lots"] = list(lots)
        (chemin / MANIFEST_FILENAME).write_text(json.dumps(document),
                                                encoding="utf-8")
    # Le dossier qu'un lot **declare** est cree : la condition de l'entree
    # `Exports` est, depuis la story 11.8, le verdict du coeur, et il constate
    # la matiere autant que l'etat.
    for lot in lots:
        declare = lot.get("output_frames_dir")
        if declare:
            (chemin / declare).mkdir(parents=True, exist_ok=True)
    return chemin


def plan(tmp_path, cadences=DEUX_CADENCES, **kwargs) -> atelier.PlanExtraction:
    """Le plan nominal : deux lots, deux comptes differents, une resolution."""
    dossier = kwargs.pop("dossier", None) or projet(tmp_path)
    kwargs.setdefault("largeur", 1920)
    kwargs.setdefault("hauteur", 1080)
    return atelier.preparer_le_plan(
        dossier, rush_id="rush_01", video_path=tmp_path / "rush_01.mov",
        cadences=cadences, **kwargs)


def coque(**kwargs) -> CoqueTui:
    """Deux paliers temoins : la racine et le rang des ateliers.

    Deux et non un : `revenir_aux_ateliers` ne se distingue d'un retour a la
    racine que si la racine existe a cote.
    """
    return CoqueTui(paliers=[PalierTemoin("Projet", "q quitter"),
                             PalierTemoin("Ateliers", "q quitter")],
                    contexte=Contexte("projet_demo"), **kwargs)


def descendu(app, scenario, banc):
    """Monter jusqu'au rang des ateliers, puis derouler le scenario."""
    async def tour(pilote):
        pilote.app.descendre()
        await pilote.pause()
        return await scenario(pilote)

    return banc(app, tour)


def extracteur(reponses):
    """Un double de `run_extraction` : une reponse par cadence, dans l'ordre.

    `reponses` associe une cadence a ce qu'il faut faire -- un
    `ExtractionOutcome`, ou une exception a lever. Les appels sont enregistres
    pour que le test lise **ce que le coeur a recu**, pas ce qu'on croit lui
    avoir passe.
    """
    appels = []

    def faux(**kwargs):
        appels.append(kwargs)
        reponse = reponses[kwargs["fps_target"]]
        if isinstance(reponse, BaseException):
            raise reponse
        rappel = kwargs.get("rappel_progression")
        total = reponse.written_frame_count
        if rappel is not None and total:
            # Le coeur emet des jalons a travers CE seul canal.
            for faites in (total // 2, total):
                rappel(faites, total)
        return reponse

    faux.appels = appels
    return faux


def issue_reussie(dossier_projet, lot_id, frames, fichiers=0):
    """Un `ExtractionOutcome` reussi, avec un dossier de lot reellement peuple."""
    dossier = Path(dossier_projet) / EXTRACT_FRAMES_DIRNAME / lot_id
    dossier.mkdir(parents=True, exist_ok=True)
    for rang in range(fichiers):
        (dossier / f"{rang:04d}.tiff").write_bytes(b"x" * (10 + rang))
    return extraction.ExtractionOutcome(
        granted=True, message=f"{frames} frame(s)", lot_id=lot_id,
        frames_dir=dossier, written_frame_count=frames)


# ===========================================================================
# `E9` -- la chaine reelle, mesuree en EXECUTANT le point d'entree
# ===========================================================================

#: Le programme execute en sous-processus. Il appelle `main()` -- le vrai point
#: d'entree, arguments compris -- et n'ecarte que `run()`, qui exige un
#: terminal. Ce qu'il rend est ce que le produit a REELLEMENT monte.
_SONDE = r"""
import json, sys
from mixed_media_utility.tui import coque
from mixed_media_utility.tui.__main__ import main

vu = {}


def sans_terminal(self, *args, **kwargs):
    vu["paliers"] = [type(p).__name__ for p in self._paliers]
    vu["ascii_seul"] = self.ascii_seul
    vu["sans_couleur"] = self.sans_couleur
    return None


coque.CoqueTui.run = sans_terminal
code = main(sys.argv[1:])
print("SONDE " + json.dumps({"code": code, **vu}))
"""


def sonder_le_point_d_entree(racine_depot, arguments=()):
    """Executer `main()` en sous-processus et rendre ce qu'il a monte."""
    environnement = dict(os.environ,
                         PYTHONPATH=str(racine_depot / "src"),
                         NO_COLOR="")
    environnement.pop("NO_COLOR")
    resultat = subprocess.run(
        [sys.executable, "-c", _SONDE, *arguments],
        cwd=racine_depot, env=environnement, capture_output=True, text=True,
        timeout=120)
    assert resultat.returncode == 0, resultat.stderr
    for ligne in resultat.stdout.splitlines():
        if ligne.startswith("SONDE "):
            return json.loads(ligne[len("SONDE "):])
    raise AssertionError(f"la sonde n'a rien rendu : {resultat.stdout!r}")


def test_le_point_d_entree_ne_monte_AUCUN_palier_TEMOIN(racine_depot):
    """`E9` -- le defaut mesure le 2026-08-29, ferme et garde.

    `python -m mixed_media_utility.tui` construisait `CoqueTui()` sans paliers,
    donc `paliers_temoins()` : `mmu-tui` ouvrait trois ecrans TEMOINS. La mesure
    porte sur ce que le point d'entree **monte**, pas sur le texte de son
    module -- c'est la seule facon de voir la difference.
    """
    vu = sonder_le_point_d_entree(racine_depot)
    assert "PalierTemoin" not in vu["paliers"], vu["paliers"]


def test_le_point_d_entree_monte_les_TROIS_paliers_REELS_dans_l_ordre(
        racine_depot):
    """Volet symetrique : sans lui, un point d'entree qui ne monterait RIEN
    passerait le test precedent."""
    vu = sonder_le_point_d_entree(racine_depot)
    assert vu["paliers"] == ["EcranProjet", "EcranAteliers",
                             "EcranPalierProjet"], vu["paliers"]


@pytest.mark.parametrize("option,champ", [
    ("--ascii", "ascii_seul"),
    ("--sans-couleur", "sans_couleur"),
])
def test_les_deux_options_de_repli_atteignent_l_application_MONTEE(
        racine_depot, option, champ):
    """Le comportement de `--ascii` et `--sans-couleur` reste intact.

    Mesure **en aval** de l'analyse d'arguments : une option lue puis perdue
    entre `analyser()` et la construction serait invisible a un test qui
    n'interrogerait que l'analyseur.
    """
    assert sonder_le_point_d_entree(racine_depot, [option])[champ] is True
    assert sonder_le_point_d_entree(racine_depot)[champ] is False


def test_le_diagnostic_de_chemin_repond_SANS_monter_d_application(racine_depot):
    """`--diagnostic-chemin` sort avant tout import de `textual` -- inchange."""
    environnement = dict(os.environ, PYTHONPATH=str(racine_depot / "src"))
    resultat = subprocess.run(
        [sys.executable, "-m", "mixed_media_utility.tui",
         "--diagnostic-chemin"],
        cwd=racine_depot, env=environnement, capture_output=True, text=True,
        timeout=120)
    assert resultat.returncode == 0, resultat.stderr
    assert any(ligne.startswith("PYTHONPATH=")
               for ligne in resultat.stdout.splitlines())
    assert any(ligne.startswith("ESCDELAY=")
               for ligne in resultat.stdout.splitlines())


# ===========================================================================
# `E8` -- le branchement du menu des ateliers
# ===========================================================================

def chaine(tmp_path, **kwargs) -> atelier.ChaineReelle:
    """La chaine reelle, posee sur un projet reel et deja ouverte."""
    # Un lot **encodable** : sans lui, `Pdf` et `Exports` sont conditionnees et
    # leur entree ne mene nulle part -- ce qui masquerait le branchement. Depuis
    # la story 11.8, « encodable » est le verdict du coeur : l'etat ne suffit
    # plus, le lot porte aussi son `output_frames_dir`, cree par `projet`.
    dossier = kwargs.pop("dossier", None) or projet(
        tmp_path, lots=[{"lot_id": "lot_a", "state": "encode",
                         "output_frames_dir": "output-frames/lot_a"}])
    lien = atelier.ChaineReelle(**kwargs)
    lien.menu.dossier = lien.palier_projet.dossier = dossier
    lien.menu.charger()
    return lien


def test_l_entree_EXTRACTION_ouvre_E2_1_SANS_menu_intermediaire(tmp_path, banc):
    """`EPIC11-ARB-28`, verbatim : « **Extraction et Exports n'en ont pas** :
    une seule entree chacun, donc le menu serait un ecran a franchir pour
    rien. »

    **La mesure porte sur la PILE ENTIERE, pas sur son sommet.** Mesure faite en
    injectant le mutant (2026-08-29) : un `EcranPasEncore` empile avant
    l'atelier laisse `rang == 2` et `passages_empiles == 0` -- le rang ne compte
    que les paliers, et les passages ne se comptent qu'**au-dessus** du sommet,
    donc un ecran intermediaire enterre sous l'atelier est invisible aux deux.
    Le menu franchi pour rien qu'`EPIC11-ARB-28` interdit est precisement celui
    qu'on ne voit plus une fois qu'on l'a franchi.
    """
    from mixed_media_utility.tui.atelier_extraction import EcranRushes

    lien = chaine(tmp_path)

    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        lien.menu.traiter("enter")           # Extraction, en tete de liste
        await pilote.pause()
        return [type(ecran).__name__ for ecran in pilote.app.screen_stack]

    pile = banc(lien.app, scenario)
    assert pile == ["EcranProjet", "EcranAteliers", EcranRushes.__name__], pile


def test_le_menu_des_ateliers_a_QUATRE_entrees_et_EXTRACTION_en_tete():
    """L'invariant que « les TROIS AUTRES » suppose, mesure plutot que suppose.

    **Pourquoi il est pose le 2026-09-06.** Le banc voisin epinglait les rangs
    1, 2 et 3 en dur, et il a rougi le jour ou `EPIC11-ARB` a **remonte l'atelier
    Pdf avant Scan** (retour terrain d'Egan, verbatim : « remonter l'atelier
    [PDF] dans la liste AVANT scan (ordre logique) »). Ajuster les indices a la
    main aurait rendu le banc vert **sans qu'aucun invariant ne soit relu** --
    c'est le banc tautologique que la politique du depot chasse. Les rangs sont
    donc DERIVES de `ATELIERS`, et ce test-ci tient les deux hypotheses que la
    derivation ne peut pas tenir seule : le cardinal (sans quoi « les trois
    autres » cesse d'etre vrai) et la place d'Extraction (sans quoi la cible
    cesse d'etre ailleurs qu'en premiere position).
    """
    assert len(projet_lecture.ATELIERS) == 4, projet_lecture.ATELIERS
    assert projet_lecture.ATELIERS[0] == projet_lecture.EXTRACTION
    assert projet_lecture.PROJET not in projet_lecture.ATELIERS


@pytest.mark.parametrize("attendu", list(projet_lecture.ATELIERS[1:]))
def test_les_TROIS_AUTRES_ateliers_menent_a_l_ecran_PAS_ENCORE(
        tmp_path, banc, attendu):
    """La cible est **ailleurs qu'en premiere position** : Extraction occupe le
    rang 0, et un branchement qui rendrait toujours la premiere entree ne se
    demasque pas autrement.

    **Le rang est DERIVE de `ATELIERS`, jamais epingle.** L'ordre du menu est un
    arbitrage produit qui a deja bouge une fois (Pdf remonte avant Scan le
    2026-09-06) ; un banc qui le recopie rougit a chaque arbitrage sans rien
    mesurer de plus. Les deux hypotheses de cette derivation -- le cardinal et
    la tete -- sont tenues par le test juste au-dessus, faute de quoi une liste
    reduite a un element rendrait ce banc vide et vert.
    """
    rang_de_l_entree = projet_lecture.ATELIERS.index(attendu)
    lien = chaine(tmp_path)

    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        for _ in range(rang_de_l_entree):
            lien.menu.traiter("down")
        lien.menu.traiter("enter")
        await pilote.pause()
        ecran = pilote.app.screen
        return type(ecran).__name__, ecran.lignes()

    nom, lignes = banc(lien.app, scenario)
    assert nom == EcranPasEncore.__name__
    assert any(attendu in ligne for ligne in lignes), lignes
    assert any("vague 3" in ligne for ligne in lignes), lignes


def test_l_entree_PROJET_descend_au_palier_projet(tmp_path, banc):
    """`Projet` n'est pas un atelier : il descend d'un palier connu."""
    lien = chaine(tmp_path)

    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        for _ in range(4):
            lien.menu.traiter("down")
        lien.menu.traiter("enter")
        await pilote.pause()
        return pilote.app.screen

    assert banc(lien.app, scenario) is lien.palier_projet


def test_choisir_un_rush_MENE_QUELQUE_PART_meme_sans_ecran_de_cadences(
        tmp_path, banc):
    """« Une touche qui ne fait rien et ne dit rien est indistinguable d'un
    clavier casse. » Le rappel des cadences est injecte ; absent, on NOMME ce
    qui manque."""
    lien = chaine(tmp_path)

    async def scenario(pilote):
        lien.extraire("rush_01")
        await pilote.pause()
        ecran = pilote.app.screen
        return type(ecran).__name__, ecran.lignes()

    nom, lignes = banc(lien.app, scenario)
    assert nom == EcranPasEncore.__name__
    assert any("rush_01" in ligne for ligne in lignes), lignes


def test_le_rappel_des_cadences_INJECTE_recoit_le_rush_choisi(tmp_path, banc):
    """Volet symetrique : la couture existe, et elle transporte le rush."""
    vus = []
    lien = chaine(tmp_path, ouvrir_les_cadences=lambda app, d, r: vus.append(r))

    banc(lien.app, lambda pilote: _appeler(lien.extraire, "rush_01"))
    assert vus == ["rush_01"]


async def _appeler(fonction, *args):
    return fonction(*args)


# ===========================================================================
# `E6` -- le point de jugement chiffre
# ===========================================================================

def test_le_panneau_porte_les_CINQ_lignes_qu_ARB_4_exige(tmp_path):
    """`EPIC11-ARB-4` : ce qui sera produit, en quelle quantite, ce que ca coute.

    Plus les bornes, qu'Egan nomme dans sa formulation d'origine (« Apercu
    disque (majorant) + nombre de frames extraites et bornes timecode »).
    """
    entree, sortie = (part.strip() for part in BORNES_DESSINEES.split("→"))
    p = plan(tmp_path, source_in_timecode=entree, source_out_timecode=sortie)
    lignes = atelier.panneau_de_l_extraction(p).rendu(80)
    rendu = "\n".join(lignes)
    assert atelier.LIBELLE_LOTS in rendu and "2 lots" in rendu
    assert atelier.LIBELLE_BORNES in rendu
    assert BORNES_DESSINEES in rendu
    assert atelier.LIBELLE_DESTINATION in rendu
    assert f"projet_demo/{EXTRACT_FRAMES_DIRNAME}/" in rendu


def test_les_frames_sont_dites_PAR_LOT_ET_AU_TOTAL(tmp_path):
    """AC 6.1. Les deux comptes DIFFERENT : un remplissage uniforme rendrait
    `124 + 124 = 248` indistinguable d'un total mal calcule."""
    ligne = [l for l in atelier.panneau_de_l_extraction(plan(tmp_path)).rendu(80)
             if l.startswith(atelier.LIBELLE_FRAMES)][0]
    assert SOMME_DESSINEE in ligne, ligne


def test_un_lot_UNIQUE_ne_porte_pas_de_somme_a_un_terme(tmp_path):
    """Volet symetrique : `124 = 124` serait du bruit."""
    ligne = [l for l in atelier.panneau_de_l_extraction(
        plan(tmp_path, cadences=[(25.0, 124)])).rendu(80)
        if l.startswith(atelier.LIBELLE_FRAMES)][0]
    assert "=" not in ligne, ligne
    assert "124" in ligne and "frames" in ligne


def test_l_espace_disque_est_un_MAJORANT_EXPLICITE(tmp_path):
    """AC 6.1. La mention vient de `LigneChiffree`, pas d'un texte local."""
    ligne = [l for l in atelier.panneau_de_l_extraction(plan(tmp_path)).rendu(80)
             if l.startswith(atelier.LIBELLE_ESPACE)][0]
    assert MENTION_MAJORANT in ligne, ligne
    # 166 frames de 1920x1080 en 16 bits RGB, au format de taille de la TUI.
    assert "1,9 Go" in ligne, ligne


def test_une_resolution_INCONNUE_ne_porte_PAS_la_mention_de_majorant(tmp_path):
    """Volet symetrique : `(majorant)` sur « inconnu » laisserait croire qu'un
    chiffre a ete calcule."""
    p = plan(tmp_path, largeur=None, hauteur=None)
    ligne = [l for l in atelier.panneau_de_l_extraction(p).rendu(80)
             if l.startswith(atelier.LIBELLE_ESPACE)][0]
    assert MENTION_MAJORANT not in ligne, ligne
    assert "inconnu" in ligne, ligne


@pytest.mark.parametrize("ascii_seul", MODES)
def test_le_panneau_tient_la_grille_du_PLANCHER_dans_les_deux_regimes(
        tmp_path, ascii_seul):
    """AC 8.1 : mesure en COLONNES, ASCII replie AVANT la mesure."""
    p = plan(tmp_path, source_in_timecode="00:00:04:12",
             source_out_timecode="00:00:09:08", couleur_inconnue_acceptee=True)
    for source in (atelier.panneau_de_l_extraction(p),
                   atelier.panneau_de_l_ecrasement(p)):
        for ligne in source.rendu(jetons.LARGEUR_PLANCHER, ascii_seul):
            assert jetons.colonnes(ligne) <= jetons.largeur_de_cartouche(
                jetons.LARGEUR_PLANCHER), (ligne, jetons.colonnes(ligne))
            if ascii_seul:
                assert ligne.isascii(), ligne


def test_les_DEUX_noms_MONTRES_viennent_de_build_lot_id_et_sont_DISTINCTS(
        tmp_path):
    """La convention est `build_lot_id`, appelee et non recomposee.

    **Ils ne sont plus editables** (`EPIC11-ARB-141`) : ce sont des lignes de
    texte du cartouche, et `EPIC11-ARB-8` (« pre-rempli, et toujours editable »)
    en est borne -- l'operateur disposera la ou le coeur sait recevoir, et
    `run_extraction` n'a aucune place ou recevoir un nom.

    Les montrer reste exige par `EPIC11-ARB-4` : le panneau chiffre porte « ce
    qui sera produit ».
    """
    p = plan(tmp_path)
    assert atelier.noms_des_lots(p) == [
        atelier.INDENT_DES_NOMS + build_lot_id("rush_01", 25.0),
        atelier.INDENT_DES_NOMS + build_lot_id("rush_01", 12.5),
    ]
    assert len(set(atelier.noms_des_lots(p))) == 2


def test_AUCUNE_longueur_de_nom_n_est_ECRITE_dans_le_module():
    """AC 6.3 : la limite est **lue** de `io.naming.CANONICAL_ID_MAX_LENGTH`.

    Frontiere negative : le nombre `48` ne figure pas dans le module. Elle est
    doublee d'un volet symetrique -- la limite est bien celle du coeur --, sans
    quoi un module qui ne compterait rien du tout passerait aussi.
    """
    source = Path(atelier.__file__).read_text(encoding="utf-8")
    assert not re.search(r"(?<![\w.])%d(?![\w.])" % CANONICAL_ID_MAX_LENGTH,
                         source), "la limite du coeur est recopiee ici"
    from mixed_media_utility.tui import noms as modele_noms
    assert modele_noms.LIMITE == CANONICAL_ID_MAX_LENGTH


# ---------------------------------------------------------------------------
# Le point de jugement, monte
# ---------------------------------------------------------------------------

def monter_le_jugement(tmp_path, banc, scenario, **kwargs):
    """Monter `E2-3` (ou l'ecran d'ecrasement) et derouler un scenario."""
    p = kwargs.pop("plan", None) or plan(tmp_path)
    ecrit = []
    app = coque(**{c: kwargs.pop(c) for c in ("ascii_seul", "sans_couleur")
                   if c in kwargs})
    boite = {}

    async def tour(pilote):
        boite["ecran"] = atelier.ouvrir_le_point_de_jugement(
            pilote.app, p, sur_ecriture=lambda plan_: ecrit.append(plan_),
            **kwargs)
        await pilote.pause()
        return await scenario(pilote, boite["ecran"])

    return descendu(app, tour, banc), ecrit, boite


def test_un_lot_DEJA_PRESENT_ouvre_l_ECRASEMENT_et_PAS_le_panneau_nominal(
        tmp_path, banc):
    """`EPIC11-ARB-4`, corollaire verbatim : « Une commande destructive
    (ecrasement d'un lot existant) porte une confirmation **en propre**,
    distincte de celle-ci ».

    Le lot deja present est le **SECOND** : un `any` remplace par un test sur
    `lots[0]` ne se demasque pas autrement.
    """
    dossier = projet(tmp_path)
    deja = dossier / EXTRACT_FRAMES_DIRNAME / build_lot_id("rush_01", 12.5)
    deja.mkdir(parents=True)
    (deja / "0001.tiff").write_bytes(b"deja la")

    async def scenario(pilote, ecran):
        return type(ecran).__name__, ecran.panneau.titre

    (nom, titre), _, _ = monter_le_jugement(
        tmp_path, banc, scenario, plan=plan(tmp_path, dossier=dossier))
    assert nom == atelier.EcranExtractionEcrasement.__name__
    assert titre == atelier.TITRE_ECRASEMENT


def test_sans_lot_present_c_est_le_panneau_NOMINAL(tmp_path, banc):
    """Volet symetrique : sans lui, un ecran d'ecrasement rendu **toujours**
    passerait le test precedent."""
    async def scenario(pilote, ecran):
        return type(ecran).__name__, ecran.panneau.titre

    (nom, titre), _, _ = monter_le_jugement(tmp_path, banc, scenario)
    assert nom == atelier.EcranExtractionConfirmation.__name__
    assert titre == atelier.TITRE_A_ECRIRE


def test_AUCUNE_frappe_UNIQUE_depuis_le_montage_ne_declenche_une_ECRITURE(
        tmp_path, banc):
    """`EPIC11-ARB-45`, verbatim : « aucune issue **qui ecrit** n'est
    atteignable par une seule frappe depuis le montage d'un ecran »."""
    touches = ["enter", "space", "down", "up", "tab", "escape", "e", "x"]

    async def scenario(pilote, ecran):
        for touche in touches:
            ecran.traiter(touche, touche if len(touche) == 1 else None)
            # Chaque frappe part d'un ecran neuf : c'est « UNE frappe depuis le
            # montage » qu'on mesure, pas une sequence.
            ecran.choix.curseur = ecran.choix.__class__(
                list(ecran.choix.issues)).curseur
            ecran.noms.en_edition = False
        return True

    _, ecrit, _ = monter_le_jugement(tmp_path, banc, scenario)
    assert ecrit == [], "une frappe unique a declenche une ecriture"


def test_l_issue_qui_ECRIT_declenche_l_ecriture_quand_on_la_VISE(
        tmp_path, banc):
    """Volet symetrique du precedent : la sortie existe, elle demande deux
    gestes -- viser, puis valider."""
    async def scenario(pilote, ecran):
        ecran.choix.viser(atelier.ISSUE_EXTRAIRE)
        ecran.traiter("enter")
        return True

    _, ecrit, _ = monter_le_jugement(tmp_path, banc, scenario)
    assert len(ecrit) == 1


def test_ANNULER_ne_declenche_AUCUNE_ecriture_et_remonte_d_UN_palier(
        tmp_path, banc):
    """`EPIC11-ARB-2`, verbatim : « Un formulaire abandonne en cours ne produit
    aucun ecrit. »"""
    async def scenario(pilote, ecran):
        ecran.choix.viser(atelier.ISSUE_ANNULER)
        ecran.traiter("enter")
        await pilote.pause()
        return pilote.app.passages_empiles, pilote.app.rang

    (passages, rang), ecrit, _ = monter_le_jugement(tmp_path, banc, scenario)
    assert ecrit == []
    assert passages == 0 and rang == 1


#: Ce que le retrait d'`EPIC11-ARB-141` a emporte de ce banc, et pourquoi il
#: n'est pas remplace test pour test.
#:
#: Quatre tests mesuraient le MODE d'edition de `E2-3` -- la frappe dans le
#: second champ, le nom trop long qui garde l'action inaccessible, le nom hors
#: convention qui fait de meme, et le `Ctrl+R` qui rend l'acces. Les trois
#: derniers mesuraient un VERROU pose faute de cablage : `run_extraction` n'a
#: aucun argument de nom, donc extraire sur un nom edite aurait fait mentir le
#: panneau. Egan a retire le champ plutot que de garder le verrou, et les
#: quatre ont perdu leur sujet en meme temps que lui.
#:
#: Ce qui reste d'eux vit dans `test_aucun_nom_editable.py`, sous la forme qui
#: convient a un retrait : une frontiere NEGATIVE, qui rougit a la
#: reintroduction. Un test positif ne verrait jamais revenir un champ.


def test_AUCUNE_frappe_n_ouvre_plus_un_champ_de_nom_sur_E2_3(tmp_path, banc):
    """Le volet MONTE du retrait, sur le chemin que l'operateur emprunte.

    Les touches essayees sont celles qui MENAIENT quelque part : `Tab` ouvrait
    le mode, `Ctrl+R` remettait le nom, une lettre entrait dans le champ. Aucune
    n'est consommee, et rien ne s'edite -- ce n'est pas une garde ajoutee, c'est
    l'absence de destination.
    """
    async def scenario(pilote, ecran):
        consommees = {touche: ecran.traiter(
            touche, touche if len(touche) == 1 else None)
            for touche in ("tab", "ctrl+r", "z", "backspace")}
        return consommees, len(ecran.noms), ecran.noms.en_edition

    (consommees, combien, en_edition), ecrit, _ = monter_le_jugement(
        tmp_path, banc, scenario)
    assert consommees == {"tab": False, "ctrl+r": False, "z": False,
                          "backspace": False}
    assert combien == 0
    assert en_edition is False
    assert ecrit == []


def test_l_ACTION_PRINCIPALE_est_accessible_des_le_montage(tmp_path, banc):
    """Le verrou `noms_hors_convention` est parti **avec** ce qui le motivait.

    Volet positif indispensable : un retrait qui aurait laisse l'action
    inaccessible aurait ferme l'atelier sans que rien ne le dise. Le curseur ne
    la vise toujours pas (`EPIC11-ARB-45`) -- ce sont deux proprietes
    differentes, et la seconde n'a pas bouge.
    """
    async def scenario(pilote, ecran):
        avant = (ecran.action_principale_accessible,
                 ecran.choix.issues[ecran.choix.curseur].ecrit)
        ecran.choix.viser(atelier.ISSUE_EXTRAIRE)
        ecran.traiter("enter")
        return avant

    (accessible, curseur_ecrit), ecrit, _ = monter_le_jugement(
        tmp_path, banc, scenario)
    assert accessible is True
    assert curseur_ecrit is False
    assert len(ecrit) == 1


def test_MODIFIER_les_reglages_remonte_sans_ecrire(tmp_path, banc):
    async def scenario(pilote, ecran):
        ecran.choix.viser(atelier.ISSUE_MODIFIER)
        ecran.traiter("enter")
        return True

    vus = []
    _, ecrit, _ = monter_le_jugement(
        tmp_path, banc, scenario, sur_modification=lambda: vus.append(1))
    assert ecrit == [] and vus == [1]


# ===========================================================================
# `E7` -- execution, refus, resultat
# ===========================================================================

def test_la_progression_passe_par_rappel_progression_ET_par_emetteur(tmp_path):
    """AC 7.4 : « aucun second canal ».

    On mesure les deux moities : le coeur recoit bien un `rappel_progression`,
    et ce qu'il y emet **arrive** dans l'avancement de la surface.

    **Les couples attendus ont change avec la 11.4e** (AC 8.1) : la surface
    agrege desormais la PASSE, et non plus chaque lot. Le total est donc
    `124 + 42 = 166` des le premier jalon, et le compte du second lot s'ajoute
    a celui du premier au lieu de repartir de zero. Ce que la retouche ne
    change pas, et c'est ce que ce banc mesure : les deux moities du canal.
    """
    dossier = projet(tmp_path)
    p = plan(tmp_path, dossier=dossier)
    surface = SurfaceExecution(unite=atelier.UNITE)
    vus = []
    surface.abonner(lambda avancement: vus.append(
        (avancement.faites, avancement.total)))
    faux = extracteur({
        25.0: issue_reussie(dossier, p.lots[0].lot_id, 124),
        12.5: issue_reussie(dossier, p.lots[1].lot_id, 42),
    })

    rapport = atelier.executer_le_plan(p, surface, logger=JournalMuet(),
                                       extraire=faux)
    assert [a["rappel_progression"] is not None for a in faux.appels] == [True,
                                                                         True]
    assert vus == [(62, 166), (124, 166), (145, 166), (166, 166)], vus
    assert rapport.code_retour == extraction.CODE_SUCCES


def test_l_emetteur_NU_eteindrait_le_canal_EN_SILENCE():
    """Volet symetrique de `canal_de_progression`, et il n'est pas decoratif.

    `EmetteurProgression` n'est **pas appelable** : le passer tel quel a
    `run_extraction` ferait rendre faux a `callable(...)` dans
    `ffmpeg_utils.py:584`, et le canal se declarerait inactif sans rien lever.
    C'est pourquoi l'adaptation d'arite existe plutot que d'etre supposee.
    """
    surface = SurfaceExecution(unite=atelier.UNITE)
    assert not callable(surface.emetteur(10))
    assert callable(atelier.canal_de_progression(surface, 10))


def test_le_canal_REMET_A_ZERO_le_COMPTE__et_GARDE_le_journal(tmp_path):
    """**Banc d'origine RETOURNE** (`EPIC11-ARB-93`, Egan, 2026-08-30).

    Il exigeait `len(surface.journal) == 0` entre deux lots, au motif qu'« un
    journal herite montrerait les jalons du lot precedent, donc un compte qui
    recule ». Le motif etait juste pour les JALONS et faux pour le **log du
    coeur**, arrive a la vague 3 dans le meme objet : le relais n'etant vise
    qu'une fois, au montage de `E2-4`, un rebind par lot rendait injoignables
    les 58 lignes que le coeur emet -- dont un avertissement de selection.

    Ce qui reste mesure ici : le **compte** repart de zero (c'est ce qu'il
    fallait vraiment). Ce qui est mesure en plus : le journal survit, et c'est
    le **meme objet** -- un `Journal()` neuf au meme contenu laisserait le
    relais ecrire dans un objet mort.

    L'objection d'origine est fermee par l'en-tete de lot :
    `test_le_journal_GARDE_les_deux_lots_et_NOMME_chacun`.
    """
    surface = SurfaceExecution(unite=atelier.UNITE)
    atelier.canal_de_progression(surface, 124)(124, 124)
    assert surface.avancement.faites == 124
    assert len(surface.journal) == 1
    journal_avant = surface.journal

    atelier.canal_de_progression(surface, 42)
    assert surface.avancement.faites == 0
    assert surface.avancement.total == 42
    assert len(surface.journal) == 1, (
        "le jalon du lot precedent RESTE au journal (EPIC11-ARB-93)")
    assert surface.journal is journal_avant, (
        "`emetteur()` ne doit pas REBIND le journal : le relais de log garde "
        "la reference visee au montage")


def test_le_journal_GARDE_les_deux_lots_et_NOMME_chacun(tmp_path):
    """**Ce que `EPIC11-ARB-93` achete, et ce qui ferme l'objection d'origine.**

    Le defaut, mesure au parcours `H3` sur une extraction reelle : `E2-5`
    n'affichait que les deux derniers jalons du DERNIER lot, et les 58 lignes
    emises par le coeur etaient injoignables -- releve `ffprobe`, borne
    d'occupation disque, mise a jour du manifest, et un avertissement
    `[NON_INTEGER_TARGET_RATE]`. Un avertissement que personne ne peut lire ne
    protege personne.

    **TROIS lots et non deux** (`CLAUDE.md`, regle des fabriques, point 2 bis) :
    a deux lots, le second est aussi le dernier, et un `break` a la place du
    `continue` de la boucle serait indiscernable. Les trois comptes sont
    **distinguables** (124 / 42 / 17), sans quoi une permutation ne se verrait
    pas.
    """
    dossier = projet(tmp_path)
    p = plan(tmp_path, cadences=TROIS_CADENCES, dossier=dossier)
    faux = extracteur({
        25.0: issue_reussie(dossier, p.lots[0].lot_id, 124),
        12.5: issue_reussie(dossier, p.lots[1].lot_id, 42),
        5.0: issue_reussie(dossier, p.lots[2].lot_id, 17),
    })
    surface = SurfaceExecution(unite=atelier.UNITE)

    atelier.executer_le_plan(p, surface, logger=JournalMuet(), extraire=faux)

    lignes = surface.journal.lignes
    # 1. les TROIS lots ont laisse leur trace, pas seulement le dernier.
    for rang, lot in enumerate(p.lots, start=1):
        en_tete = atelier.en_tete_de_lot(rang - 1, 3, lot.lot_id)
        assert en_tete in lignes, f"le lot {rang} n'a pas d'en-tete au journal"
        assert f"{lot.frames}/{lot.frames} {atelier.UNITE}" in lignes, (
            f"le jalon final du lot {rang} a disparu du journal")

    # 2. **L'ORDRE, et il porte l'objection de la vague 1.** Chaque en-tete
    #    precede les jalons de SON lot : c'est ce qui fait que `42/42` apres
    #    `124/124` ne se lit pas comme un compte qui recule.
    rangs = [lignes.index(atelier.en_tete_de_lot(r, 3, lot.lot_id))
             for r, lot in enumerate(p.lots)]
    assert rangs == sorted(rangs), "les en-tetes ne sont pas dans l'ordre du plan"
    for (rang, lot), depart in zip(enumerate(p.lots, start=1), rangs):
        jalon = lignes.index(f"{lot.frames}/{lot.frames} {atelier.UNITE}")
        assert depart < jalon, (
            f"l'en-tete du lot {rang} doit PRECEDER ses jalons")

    # 3. Le lot du MILIEU est nomme comme les autres -- une boucle qui ne
    #    nommerait que le premier ou que le dernier ne se demasque pas
    #    autrement (regle des fabriques, point 2 bis).
    assert atelier.en_tete_de_lot(1, 3, p.lots[1].lot_id) in lignes
    # le rang AFFICHE est 1-indexe : « lot 2/3 », pas « lot 1/3 ».
    assert atelier.en_tete_de_lot(1, 3, p.lots[1].lot_id) == \
        f"-- lot 2/3 : {p.lots[1].lot_id}"


def test_le_journal_de_E2_5_est_CELUI_ou_le_relais_a_ecrit(tmp_path):
    """**Le volet d'identite, et c'est le coeur du defaut d'origine.**

    Le relais de log (`RelaisDeJournal`) est vise **une seule fois**, au
    montage de `E2-4`. Si `emetteur()` rebindait le journal a chaque lot, le
    relais continuerait d'ecrire dans un objet que plus rien n'affiche : c'est
    exactement ce que la mesure par identite d'objet a trouve au parcours `H3`
    (`viser` sur `…705104`, `ouvrir_le_resultat` recevant `…715344`).

    Ce banc mesure donc l'IDENTITE, jamais le contenu : un `Journal()` neuf au
    contenu recopie passerait un test de contenu et laisserait le defaut
    entier.
    """
    dossier = projet(tmp_path)
    p = plan(tmp_path, cadences=TROIS_CADENCES, dossier=dossier)
    faux = extracteur({
        25.0: issue_reussie(dossier, p.lots[0].lot_id, 124),
        12.5: issue_reussie(dossier, p.lots[1].lot_id, 42),
        5.0: issue_reussie(dossier, p.lots[2].lot_id, 17),
    })
    surface = SurfaceExecution(unite=atelier.UNITE)
    # ce que le produit fait au montage de `E2-4` : le relais vise CE journal.
    vise_par_le_relais = surface.journal
    # une ligne que SEUL le coeur pourrait emettre, posee AVANT le premier lot.
    vise_par_le_relais.inscrire("[NON_INTEGER_TARGET_RATE] cadence non entiere")

    atelier.executer_le_plan(p, surface, logger=JournalMuet(), extraire=faux)

    assert surface.journal is vise_par_le_relais, (
        "le journal que `E2-5` recevra doit etre CELUI que le relais a vise")
    assert "[NON_INTEGER_TARGET_RATE] cadence non entiere" in \
        surface.journal.lignes, (
            "une ligne du coeur emise avant le premier lot doit survivre "
            "aux trois lots")


def test_TROIS_lots_et_l_echec_au_SECOND_garde_le_PREMIER_ecrit(tmp_path):
    """Regle des fabriques : l'echec est provoque **ailleurs qu'en premiere
    position**. Une boucle qui s'arreterait au premier lot, ou qui rendrait
    toujours le premier resultat, ne se demasque pas autrement."""
    dossier = projet(tmp_path)
    p = plan(tmp_path, cadences=TROIS_CADENCES, dossier=dossier)
    faux = extracteur({
        25.0: issue_reussie(dossier, p.lots[0].lot_id, 124, fichiers=3),
        12.5: extraction.ExtractionInputError("cadence cible superieure"),
        5.0: issue_reussie(dossier, p.lots[2].lot_id, 17),
    })

    rapport = atelier.executer_le_plan(
        p, SurfaceExecution(unite=atelier.UNITE), logger=JournalMuet(),
        extraire=faux)

    assert [lot.lot_id for lot in rapport.lots_ecrits] == [p.lots[0].lot_id]
    assert rapport.refus is not None
    assert rapport.refus.code == "ExtractionInputError"
    assert len(faux.appels) == 2, "le troisieme lot ne doit pas etre tente"


@pytest.mark.parametrize("exception,attendu", [
    (extraction.ExtractionInputError("x"), extraction.CODE_ERREUR),
    (extraction.ffmpeg_utils.FfmpegNotFoundError("x"),
     extraction.CODE_PREREQUIS_ABSENT),
    (extraction.video_metadata.FfprobeNotFoundError("x"),
     extraction.CODE_PREREQUIS_ABSENT),
    (OSError("disque plein"), extraction.CODE_ERREUR),
])
def test_le_code_retour_est_LU_de_la_table_du_coeur(tmp_path, exception,
                                                   attendu):
    """AC 7.3 et `EPIC11-ARB-75` : la table descendue dans `extraction.py` est
    « **lue des deux cotes** ». Aucun entier n'est ecrit ici : les valeurs
    attendues sont les constantes du coeur."""
    dossier = projet(tmp_path)
    p = plan(tmp_path, cadences=[(25.0, 124)], dossier=dossier)
    rapport = atelier.executer_le_plan(
        p, SurfaceExecution(unite=atelier.UNITE), logger=JournalMuet(),
        extraire=extracteur({25.0: exception}))
    assert rapport.code_retour == attendu
    assert rapport.refus.message == str(exception)


def test_un_refus_de_confirmation_rend_le_code_du_REFUS_et_non_une_erreur(
        tmp_path):
    """`ExtractionOutcome` : « l'appelant renvoie le code de sortie `3` sans
    passer par le chemin d'erreur »."""
    dossier = projet(tmp_path)
    p = plan(tmp_path, cadences=[(25.0, 124)], dossier=dossier)
    refuse = extraction.ExtractionOutcome(granted=False,
                                          message="Confirmation refusee")
    rapport = atelier.executer_le_plan(
        p, SurfaceExecution(unite=atelier.UNITE), logger=JournalMuet(),
        extraire=extracteur({25.0: refuse}))
    assert rapport.code_retour == extraction.CODE_REFUS
    assert rapport.lots_ecrits == ()
    assert rapport.refus.message == "Confirmation refusee"


def test_une_exception_HORS_TABLE_remonte_au_lieu_d_etre_deguisee(tmp_path):
    """`correspondance_de_sortie` : « l'appelant **relaie** alors l'exception au
    lieu de la deguiser en refus metier »."""
    dossier = projet(tmp_path)
    p = plan(tmp_path, cadences=[(25.0, 124)], dossier=dossier)
    with pytest.raises(ZeroDivisionError):
        atelier.executer_le_plan(
            p, SurfaceExecution(unite=atelier.UNITE), logger=JournalMuet(),
            extraire=extracteur({25.0: ZeroDivisionError("bug")}))


def test_l_interruption_est_constatee_ENTRE_deux_lots(tmp_path):
    """La granularite est celle-la, et le rapport porte le code du coeur."""
    dossier = projet(tmp_path)
    p = plan(tmp_path, cadences=TROIS_CADENCES, dossier=dossier)
    faux = extracteur({
        25.0: issue_reussie(dossier, p.lots[0].lot_id, 124),
        12.5: issue_reussie(dossier, p.lots[1].lot_id, 42),
        5.0: issue_reussie(dossier, p.lots[2].lot_id, 17),
    })
    demandes = iter([False, True, True])
    rapport = atelier.executer_le_plan(
        p, SurfaceExecution(unite=atelier.UNITE), logger=JournalMuet(),
        extraire=faux, interrompu=lambda: next(demandes))
    assert len(rapport.lots_ecrits) == 1
    assert rapport.code_retour == extraction.CODE_INTERRUPTION


# ---------------------------------------------------------------------------
# AC 7.5 -- un lot deja passe a `pdf` est refuse SANS ecriture
# ---------------------------------------------------------------------------

def test_un_lot_deja_au_dela_d_EXTRACTION_est_REFUSE_SANS_AUCUNE_ecriture(
        tmp_path):
    """AC 7.5. Le lot vise est le **SECOND** du plan : une garde qui ne
    regarderait que `lots[0]` ne se demasque pas autrement.

    Deux mesures, et la seconde est celle qui compte : le refus porte le code du
    coeur, **et** `run_extraction` n'a jamais ete appelee pour ce lot -- donc
    aucun TIFF n'a pu etre ecrit ni efface.
    """
    vise = build_lot_id("rush_01", 12.5)
    dossier = projet(tmp_path, lots=[
        {"lot_id": build_lot_id("rush_01", 25.0), "state": "extraction"},
        {"lot_id": vise, "state": "pdf"},
    ])
    p = plan(tmp_path, dossier=dossier)
    assert p.lots[1].etat == "pdf", "l'etat du lot vise doit venir du manifeste"

    # **Le double sait extraire les DEUX lots.** Sans la seconde reponse, retirer
    # la garde ferait tomber le test sur un `KeyError` du double plutot que sur
    # ce qu'on mesure -- un rouge qui ne dirait pas que le lot a ete ecrit.
    faux = extracteur({25.0: issue_reussie(dossier, p.lots[0].lot_id, 124),
                       12.5: issue_reussie(dossier, p.lots[1].lot_id, 42)})
    rapport = atelier.executer_le_plan(
        p, SurfaceExecution(unite=atelier.UNITE), logger=JournalMuet(),
        extraire=faux)

    assert [lot.lot_id for lot in rapport.lots_ecrits] == [p.lots[0].lot_id], (
        "le lot deja passe a pdf ne doit pas figurer parmi les lots ecrits")
    assert rapport.refus is not None
    assert rapport.refus.code == LotStateConflictError.__name__
    assert rapport.code_retour == extraction.code_de_sortie(
        LotStateConflictError("x"))
    assert [a["fps_target"] for a in faux.appels] == [25.0], (
        "le lot refuse ne doit jamais atteindre run_extraction")


def test_le_message_du_refus_d_etat_vient_du_COEUR_verbatim(tmp_path):
    """`EPIC11-ARB-30` : « le code **et** la phrase viennent du coeur »."""
    from mixed_media_utility.io.manifest import (
        ValidationError,
        validate_lot_state_transition,
    )

    attendu = None
    try:
        validate_lot_state_transition("pdf", "extraction")
    except ValidationError as erreur:
        attendu = erreur.message
    lot = atelier.LotPrevu(12.5, 42, "l", tmp_path / "x", False, "pdf")
    assert atelier.refus_d_etat_de_lot(lot).message == attendu


@pytest.mark.parametrize("etat", ["extraction", None])
def test_un_lot_a_extraire_ou_INCONNU_n_est_PAS_refuse(tmp_path, etat):
    """Volet symetrique : une garde qui refuserait tout passerait le test
    precedent. `extraction -> extraction` est la condition meme de
    l'idempotence."""
    lot = atelier.LotPrevu(12.5, 42, "l", tmp_path / "x", False, etat)
    assert atelier.refus_d_etat_de_lot(lot) is None


def test_le_refus_est_rendu_TEL_QUEL_a_l_ecran(tmp_path, banc):
    """La TUI met en forme ; elle n'interprete pas, elle ne resume pas.

    Le texte affiche est une **sur-chaine exacte** du message leve.
    """
    refus = atelier.RefusDExtraction(
        code="LotStateConflictError", message="Le lot 'x' est en etat 'pdf'.",
        code_retour=extraction.CODE_ERREUR)
    rapport = atelier.RapportExtraction(lots_ecrits=(atelier.LotEcrit(
        "lot_a", 124, 25.0, 10, tmp_path),))

    async def scenario(pilote):
        ecran = atelier.ouvrir_le_refus(pilote.app, refus, rapport)
        await pilote.pause()
        return type(ecran).__name__, "\n".join(ecran.lignes())

    nom, rendu = descendu(coque(), scenario, banc)
    assert nom == EcranRefus.__name__
    assert refus.message in rendu
    assert "LotStateConflictError" in rendu
    assert "lot_a" in rendu, "ce qui a ete ecrit avant le refus doit se lire"


# ---------------------------------------------------------------------------
# `E2-5` -- le resultat et ses suites
# ---------------------------------------------------------------------------

def rapport_temoin(tmp_path) -> atelier.RapportExtraction:
    """Deux lots ecrits, **distinguables** par leurs trois colonnes."""
    return atelier.RapportExtraction(
        lots_ecrits=(
            atelier.LotEcrit("rush_01_25", 124, 25.0, 2_100_000_000, tmp_path),
            atelier.LotEcrit("rush_01_12p5", 42, 12.5, 700_000_000, tmp_path)),
        manifeste=tmp_path / MANIFEST_FILENAME)


def test_le_resultat_ne_porte_AUCUN_majorant(tmp_path):
    """Story 11.1, AC 8.2 : `EcranResultat` leve sur un panneau qui en porte un.
    Le construire est donc deja la mesure."""
    panneau = atelier.panneau_du_resultat(rapport_temoin(tmp_path))
    assert panneau.porte_un_majorant is False
    EcranResultat(panneau)


@pytest.mark.parametrize("ascii_seul", MODES)
def test_le_resultat_nomme_les_DEUX_lots_avec_leurs_chiffres_MESURES(
        tmp_path, ascii_seul):
    rendu = "\n".join(atelier.panneau_du_resultat(
        rapport_temoin(tmp_path), ascii_seul).rendu(80, ascii_seul))
    assert "rush_01_25" in rendu and "rush_01_12p5" in rendu
    assert "124" in rendu and "42" in rendu
    assert "2,0 Go" in rendu and "668 Mo" in rendu
    assert jetons.glyphes(ascii_seul)["complete"] in rendu


def test_les_suites_du_resultat_MENENT_QUELQUE_PART(tmp_path, banc):
    """`EPIC11-ARB-13` et la consigne d'Egan : « toute suite mene quelque part ».

    On valide la **DEUXIEME** suite, jamais la premiere : une navigation qui
    rendrait toujours l'entree de tete ne se demasque pas autrement.
    """
    async def scenario(pilote):
        ecran = atelier.ouvrir_le_resultat(pilote.app, rapport_temoin(tmp_path))
        await pilote.pause()
        ecran.curseur = 1
        suite = ecran.choisir()
        await pilote.pause()
        return suite, type(pilote.app.screen).__name__, ecran.suites

    suite, ecran, suites = descendu(coque(), scenario, banc)
    assert suites == [atelier.SUITE_DOSSIER, atelier.SUITE_PDF,
                      atelier.SUITE_AUTRE_RUSH, EcranResultat.RETOUR]
    assert suite == atelier.SUITE_PDF
    assert ecran == EcranPasEncore.__name__


def test_le_RETOUR_du_resultat_ramene_au_MENU_DES_ATELIERS(tmp_path, banc):
    """`EPIC11-ARB-13`, verbatim : « La fin d'une execution ramene au **menu des
    ateliers du projet ouvert** [...] **jamais** a l'ecran projet. »"""
    app = coque()

    async def scenario(pilote):
        ecran = atelier.ouvrir_le_resultat(pilote.app, rapport_temoin(tmp_path))
        await pilote.pause()
        ecran.curseur = ecran.suites.index(EcranResultat.RETOUR)
        ecran.choisir()
        await pilote.pause()
        return pilote.app.screen, pilote.app.rang, pilote.app.tache_en_cours

    ecran, rang, tache = descendu(app, scenario, banc)
    assert ecran is app._paliers[1], "on retombe au palier des ateliers"
    assert rang == 1 and tache is False


def test_un_resultat_SANS_lot_ecrit_ne_propose_pas_l_atelier_Pdf(tmp_path):
    """Proposer « composer les planches » sur zero lot serait une invite vers un
    ecran qui n'aurait rien a lister."""
    suites = atelier.suites_du_resultat(atelier.RapportExtraction())
    assert atelier.SUITE_PDF not in suites
    assert atelier.SUITE_AUTRE_RUSH in suites


@pytest.mark.parametrize("ascii_seul", MODES)
def test_la_ligne_d_etat_du_resultat_porte_une_MESURE_et_aucune_TOUCHE(
        tmp_path, ascii_seul):
    """`EPIC11-ARB-56` : la ligne d'etat « ne porte **aucune touche** [...]
    **aucun conseil d'usage** »."""
    ligne = atelier.ligne_d_etat_du_resultat(rapport_temoin(tmp_path),
                                             ascii_seul)
    assert "166" in ligne and "2 lots" in ligne
    for touche in ("Entree", "⏎", "Échap", "Echap", "Tab", "F1", "appuyez"):
        assert touche not in ligne, (touche, ligne)
    assert jetons.colonnes(ligne) <= jetons.largeur_utile(), ligne
    if ascii_seul:
        assert ligne.isascii(), ligne


def test_apres_extraction_on_retombe_au_MENU_DES_ATELIERS(tmp_path, banc):
    """La chaine complete : jugement, execution, resultat, retour."""
    dossier = projet(tmp_path)
    p = plan(tmp_path, dossier=dossier)
    faux = extracteur({
        25.0: issue_reussie(dossier, p.lots[0].lot_id, 124, fichiers=2),
        12.5: issue_reussie(dossier, p.lots[1].lot_id, 42, fichiers=1),
    })
    app = coque()

    async def scenario(pilote):
        ecran = atelier.ouvrir_l_execution(pilote.app, p)
        await pilote.pause()
        rapport = atelier.executer_et_conclure(
            pilote.app, ecran, p, logger=JournalMuet(), extraire=faux)
        await pilote.pause()
        resultat = pilote.app.screen
        resultat.curseur = resultat.suites.index(EcranResultat.RETOUR)
        resultat.choisir()
        await pilote.pause()
        return rapport, pilote.app.screen, pilote.app.rang

    rapport, ecran, rang = descendu(app, scenario, banc)
    assert [lot.lot_id for lot in rapport.lots_ecrits] == [
        p.lots[0].lot_id, p.lots[1].lot_id]
    assert rapport.code_retour == extraction.CODE_SUCCES
    assert ecran is app._paliers[1] and rang == 1


def test_le_JOURNAL_de_l_execution_arrive_jusqu_a_E2_5(tmp_path, banc):
    """Finding `I8`, troisieme volet : le FIL, pas les deux moities.

    `EcranResultat` sait desormais deplier un journal et `EcranExecution` en
    tient un ; entre les deux il faut que quelqu'un le passe, et c'est le seul
    endroit du produit ou les deux se touchent -- `E2-4` est depile au moment
    ou `E2-5` monte, son journal disparaitrait avec lui.

    **C'est le mode de panne que le commit `41c7b30` a paye sur ce meme
    journal** : « M2 a SURVECU a la premiere version du banc. Les neuf tests
    mesuraient le relais, sa politique d'attente, son desempilement -- tout sauf
    le fil. » Ce test mesure le fil, sur la chaine REELLE
    (`executer_et_conclure`), et non sur un appel direct a
    `ouvrir_le_resultat` -- lequel resterait vert si le produit oubliait de
    passer le journal.
    """
    dossier = projet(tmp_path)
    p = plan(tmp_path, dossier=dossier)
    faux = extracteur({
        25.0: issue_reussie(dossier, p.lots[0].lot_id, 124, fichiers=2),
        12.5: issue_reussie(dossier, p.lots[1].lot_id, 42, fichiers=1),
    })

    async def scenario(pilote):
        execution_ = atelier.ouvrir_l_execution(pilote.app, p)
        await pilote.pause()
        execution_.surface.journal.inscrire("14:31:47  lot 1 ecrit")
        atelier.executer_et_conclure(
            pilote.app, execution_, p, logger=JournalMuet(), extraire=faux)
        await pilote.pause()
        resultat = pilote.app.screen
        return (resultat.journal is execution_.surface.journal,
                resultat.raccourcis, list(execution_.surface.journal.lignes))

    memes, raccourcis, lignes = descendu(coque(), scenario, banc)
    assert memes, "E2-5 n'a pas recu le journal de l'execution qui precede"
    assert RACCOURCI_DU_JOURNAL in raccourcis, raccourcis
    assert lignes, "le journal releve est vide : la mesure ne mesure rien"


# ===========================================================================
# AC 7.1 et 7.2 -- l'identite avec `mmu extract`, sur un rush REEL
# ===========================================================================

def rush_reel(chemin: Path, *, rate: int = 30, duration: int = 2,
              size: str = "64x36") -> Path:
    """Fabriquer un rush avec ffmpeg lui-meme (`testsrc`), comme
    `tests/unit/test_extract_command.py` : le test reste autonome, et `testsrc`
    change a chaque frame -- une duplication s'y verrait."""
    resultat = subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi",
         "-i", f"testsrc=size={size}:rate={rate}:duration={duration}",
         "-pix_fmt", "yuv420p", str(chemin)],
        capture_output=True, text=True)
    assert resultat.returncode == 0, resultat.stderr
    return chemin


def condensats(dossier: Path) -> dict[str, str]:
    """Nom de fichier -> condensat de son contenu. La comparaison est **octet a
    octet**, jamais sur la taille."""
    return {chemin.name: hashlib.sha256(chemin.read_bytes()).hexdigest()
            for chemin in sorted(dossier.iterdir()) if chemin.is_file()}


@requires_ffmpeg
def test_l_ARTEFACT_ecrit_est_IDENTIQUE_octet_a_octet_a_celui_de_mmu_extract(
        tmp_path):
    """AC 7.1. Deux projets **du meme nom** dans deux parents differents : le
    `project_id` derive du nom du dossier, et le faire varier ferait diverger le
    manifeste pour une raison qui n'est pas celle qu'on mesure."""
    from mixed_media_utility import cli   # le BANC peut l'importer, pas la TUI

    rush = rush_reel(tmp_path / "rush_01.mp4")
    par_cli = tmp_path / "cote_cli" / "projet_demo"
    par_tui = tmp_path / "cote_tui" / "projet_demo"

    assert cli.main(["extract", "--project", str(par_cli), "--video",
                     str(rush), "--fps", "5", "--yes",
                     "--accept-unknown-color"]) == 0

    par_tui.parent.mkdir(parents=True, exist_ok=True)
    p = atelier.preparer_le_plan(
        par_tui, rush_id="rush_01", video_path=rush, cadences=[(5.0, 10)],
        largeur=64, hauteur=36, couleur_inconnue_acceptee=True)
    rapport = atelier.executer_le_plan(
        p, SurfaceExecution(unite=atelier.UNITE), logger=JournalMuet())
    assert rapport.code_retour == extraction.CODE_SUCCES, rapport.refus

    lot = build_lot_id("rush_01", 5.0)
    cote_cli = condensats(par_cli / EXTRACT_FRAMES_DIRNAME / lot)
    cote_tui = condensats(par_tui / EXTRACT_FRAMES_DIRNAME / lot)
    assert cote_cli, "le cote CLI n'a rien ecrit : la mesure ne mesurerait rien"
    assert cote_tui == cote_cli, (sorted(cote_tui), sorted(cote_cli))


#: Les cles du manifeste qui ne peuvent pas coincider entre deux executions et
#: dont la divergence n'est **pas** celle que l'AC 7.2 examine : un horodatage,
#: et les chemins absolus du dossier temporaire de chaque cote.
#:
#: **`created` y est entree au lot F**, apres l'avoir vu rougir : la cle ecrite
#: par `project_layout` s'appelle `created`, et non `created_at`. Les deux
#: projets sont crees a quelques centaines de millisecondes d'intervalle, donc
#: le test etait vert tant que la seconde ne changeait pas entre les deux --
#: mesure : un echec sur 8 a 15 executions.
_CLES_VOLATILES = ("confirmed_at", "generated_at", "created", "created_at",
                   "updated_at")


def sans_volatile(valeur, racines):
    """Neutraliser horodatages et racines de chemin, et **rien d'autre**."""
    if isinstance(valeur, dict):
        return {cle: ("<horodatage>" if cle in _CLES_VOLATILES
                      else sans_volatile(sous, racines))
                for cle, sous in valeur.items()}
    if isinstance(valeur, list):
        return [sans_volatile(sous, racines) for sous in valeur]
    if isinstance(valeur, str):
        for racine in racines:
            valeur = valeur.replace(str(racine), "<projet>")
        return valeur
    return valeur


@requires_ffmpeg
def test_le_MANIFESTE_est_identique_A_L_EXCEPTION_NOMMEE_de_confirmation_mode(
        tmp_path):
    """AC 7.2. Deux mesures : le manifeste ecrit par la TUI est identique a
    celui d'`mmu extract --yes` **cle pour cle**, et `confirmation.mode` y vaut
    `non_interactif` -- c'est l'exception nommee (fait F5 de la fiche 11.4 :
    `run_extraction` force `interactive=False` des que `consent_granted=True`).
    """
    from mixed_media_utility import cli

    rush = rush_reel(tmp_path / "rush_01.mp4")
    par_cli = tmp_path / "cote_cli" / "projet_demo"
    par_tui = tmp_path / "cote_tui" / "projet_demo"

    assert cli.main(["extract", "--project", str(par_cli), "--video",
                     str(rush), "--fps", "5", "--yes",
                     "--accept-unknown-color"]) == 0
    par_tui.parent.mkdir(parents=True, exist_ok=True)
    p = atelier.preparer_le_plan(
        par_tui, rush_id="rush_01", video_path=rush, cadences=[(5.0, 10)],
        largeur=64, hauteur=36, couleur_inconnue_acceptee=True)
    assert atelier.executer_le_plan(
        p, SurfaceExecution(unite=atelier.UNITE),
        logger=JournalMuet()).code_retour == extraction.CODE_SUCCES

    lire = lambda chemin: json.loads(
        (chemin / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    racines = (par_cli, par_tui, par_cli.parent, par_tui.parent)
    cote_cli = sans_volatile(lire(par_cli), racines)
    cote_tui = sans_volatile(lire(par_tui), racines)

    assert cote_tui["lots"][0]["confirmation"]["mode"] == "non_interactif"
    assert cote_tui == cote_cli


# --------------------------------------------------------------------------
# Revue de la vague 3, couche 2 -- le poids mesure, et le disque sous les pieds
# --------------------------------------------------------------------------

def test_le_POIDS_annonce_par_E2_5_est_MESURE_sur_le_disque(tmp_path):
    """**`_octets_du_dossier` reduite a `return 0` survivait a 2 179 tests**
    (revue de la vague 3, couche 2, finding `C3`).

    Aucun banc n'assertait sur `LotEcrit.octets` **issu d'une execution** :
    tous construisaient `LotEcrit(..., octets=10, ...)` a la main. C'est le
    motif que la vague a paye trois fois -- *le banc mesure la piece, pas le
    fil* -- sur un cartouche dont la docstring dit pourtant « **aucun
    majorant** : le travail est fait, les chiffres sont **mesures** ».

    La fabrique ecrit des fichiers de tailles **distinctes et connues**
    (`issue_reussie(..., fichiers=n)` pose `10 + rang` octets), et les deux lots
    en ont des cardinaux differents : un poids qui serait recopie d'un lot sur
    l'autre se demasque aussi.
    """
    dossier = projet(tmp_path)
    p = plan(tmp_path, cadences=DEUX_CADENCES, dossier=dossier)
    faux = extracteur({
        25.0: issue_reussie(dossier, p.lots[0].lot_id, 124, fichiers=3),
        12.5: issue_reussie(dossier, p.lots[1].lot_id, 42, fichiers=5),
    })

    rapport = atelier.executer_le_plan(
        p, SurfaceExecution(unite=atelier.UNITE), logger=JournalMuet(),
        extraire=faux)

    # `issue_reussie` ecrit `10 + rang` octets par fichier : 10+11+12 = 33,
    # puis 10+11+12+13+14 = 60. Ecrits en dur, jamais recalcules par la meme
    # formule que la fabrique -- sinon un mutant casserait les deux cotes.
    poids = [lot.octets for lot in rapport.lots_ecrits]
    assert poids == [33, 60], (
        "le poids annonce doit etre MESURE sur le disque, pas suppose : "
        f"obtenu {poids}")
    assert poids[0] != poids[1], "la fabrique doit distinguer les deux lots"


def test_les_TROIS_lectures_de_dossier_rendent_une_valeur_sur_un_disque_ILLISIBLE(
        tmp_path):
    """**Trois helpers sans garde, la ou l'explorateur en porte onze**
    (revue de la vague 3, couche 2, finding `T2`).

    `_compte_de_fichiers` etait le pire des trois : ni `is_dir()`, ni
    `except OSError`. Il levait un `FileNotFoundError` **au point de
    jugement** -- l'ecran qui compte ce qu'un ecrasement va detruire --, la ou
    ses deux freres rendaient `False` et `0`.

    Le declencheur n'a pas besoin d'etre exotique : un dossier de lot devenu
    illisible entre la pose de `deja_present` et le comptage (partage reseau
    demonte, volume ejecte, permission retiree). `is_dir()` repond vrai et
    `iterdir()` leve.

    Deux regimes mesures : le dossier **absent**, et le dossier present mais
    dont la lecture leve -- le second est le seul qui distingue une garde
    `is_dir()` d'une garde `except OSError`.
    """
    absent = tmp_path / "jamais-cree"
    assert atelier._octets_du_dossier(absent) == 0
    assert atelier._porte_des_fichiers(absent) is False
    assert atelier._compte_de_fichiers(absent) == 0

    # Le regime que `is_dir()` seul ne couvre pas : le dossier EXISTE et sa
    # lecture leve.
    illisible = tmp_path / "illisible"
    illisible.mkdir()
    (illisible / "une-frame.tiff").write_bytes(b"x" * 12)
    reel = Path.iterdir

    def iterdir_qui_leve(self):
        if self == illisible:
            raise PermissionError(13, "Permission denied", str(self))
        return reel(self)

    try:
        Path.iterdir = iterdir_qui_leve
        assert illisible.is_dir(), "le regime mesure est bien dossier PRESENT"
        assert atelier._octets_du_dossier(illisible) == 0
        assert atelier._porte_des_fichiers(illisible) is False
        assert atelier._compte_de_fichiers(illisible) == 0
    finally:
        Path.iterdir = reel

    # Volet symetrique : sur un dossier LISIBLE, les trois disent la verite --
    # sans lui, les gardes ci-dessus resteraient vertes sur trois fonctions qui
    # rendraient toujours zero.
    assert atelier._octets_du_dossier(illisible) == 12
    assert atelier._porte_des_fichiers(illisible) is True
    assert atelier._compte_de_fichiers(illisible) == 1


# ===========================================================================
# Les maquettes que ce banc citait sans les LIRE
# ===========================================================================
#
# **Le defaut, mesure le 2026-09-06.** Ce banc cite `E2-3`, `E2-4` et `E2-5`
# et n'ouvrait aucun dessin : quatre de ses valeurs en etaient recopiees.

#: Les maquettes, a leur source.
MAQUETTES = (Path(_SRC).parents[0] / "_bmad-output" / "planning-artifacts"
             / "ux-designs" / "ux-tui-2026-08-27" / "maquettes")

#: Le cadre d'un dessin separe des colonnes ; il n'est pas du texte.
CADRE_DU_DESSIN = "─│┌┐└┘├┤┬┴┼━┃▏▕"

#: Ce qui suit est la prose de relecture, pas le dessin.
SEPARATEUR_DE_NOTE = "\nNOTE"


def dessin_de_la_maquette(nom: str) -> str:
    """Le corps du dessin, cadre retire et notes coupees, espaces replies.

    Le repliement est indispensable ici : `E2-3` aligne sa somme en colonnes
    (`124  +  42        =  166`), et seule la forme repliee est comparable a
    ce que le produit rend.
    """
    brut = (MAQUETTES / nom).read_text(encoding="utf-8")
    brut = brut.split(SEPARATEUR_DE_NOTE)[0]
    return " ".join(
        "".join(" " if c in CADRE_DU_DESSIN else c for c in brut).split())


def test_les_valeurs_de_la_CONFIRMATION_sont_VERBATIM_de_E2_3():
    """Les bornes et la somme sont dans le dessin, lu a sa source.

    La somme y est ecrite en colonnes ; c'est la forme REPLIEE qui compare,
    et le contre-exemple plus bas montre que le pli n'absorbe rien d'autre.
    """
    dessin = dessin_de_la_maquette("E2-3-extraction-confirmation.txt")
    assert BORNES_DESSINEES in dessin
    assert SOMME_DESSINEE in dessin


def test_le_raccourci_du_JOURNAL_est_LE_MEME_sur_E2_4_et_sur_E2_5():
    """L'ecart d'UN MOT est FERME, et l'epingle est RETOURNEE plutot que tue.

    Elle mesurait « `E2-4` porte le mot que `E2-5` n'a pas », des deux cotes,
    pour qu'aucun des deux ne bouge en silence. `EPIC11-ARB-246` a tranche
    (Egan, 2026-09-06, par invite : « Tab journal partout ») : `E2-4` a perdu
    son mot, corrige a la source dans `_gen_extraction.py`, et les deux
    dessins portent desormais le meme jeton -- celui que l'ecran rend depuis
    toujours.

    La mesure reste **des deux cotes**, et elle est plus forte qu'avant : elle
    rougit si l'un des deux dessins regagne le mot, et elle rougit aussi s'il
    le perd entierement. Une frontiere supprimee ne rougirait plus jamais.
    """
    resultat = dessin_de_la_maquette("E2-5-extraction-resultat.txt")
    execution_ = dessin_de_la_maquette("E2-4-extraction-execution.txt")
    assert RACCOURCI_DU_JOURNAL in resultat
    assert RACCOURCI_DU_JOURNAL in execution_
    assert RACCOURCI_DU_JOURNAL + " complet" not in resultat
    assert RACCOURCI_DU_JOURNAL + " complet" not in execution_


def test_la_confrontation_REFUSE_ce_qui_n_est_PAS_dessine():
    """Frontiere negative : le pli absorbe la mise en page, PAS un ecart.

    Quatre contre-exemples, dont trois a un chiffre pres. Sans eux, une
    comparaison toujours vraie passerait les deux tests ci-dessus.
    """
    dessin = dessin_de_la_maquette("E2-3-extraction-confirmation.txt")
    assert "124 + 42 = 167" not in dessin
    assert "124 + 43 = 166" not in dessin
    assert "00:00:04:12 → 00:00:09:09" not in dessin
    assert RACCOURCI_DU_JOURNAL not in dessin
