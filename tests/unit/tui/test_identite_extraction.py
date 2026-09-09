# -*- coding: utf-8 -*-
"""Story 11.4, **lot F** -- l'identite de l'atelier Extraction avec `mmu extract`.

`EPIC11-ARB-19`, verbatim : « toute action de la TUI produit le meme artefact,
le meme manifest et le meme code retour que la commande CLI correspondante ».

Ce module est le banc de cette phrase. Sa regle de mesure tient en une ligne :
**les deux chemins tournent pour de vrai**. Un banc qui se contenterait
d'asserter que les deux cotes appellent `run_extraction` ne mesurerait qu'un
cablage, et un cablage identique peut produire des artefacts differents --
dossier, nommage, ordre. Ici `mmu extract` est appele par `cli.main`, le chemin
d'ecriture de la TUI par `preparer_le_plan` + `executer_le_plan` (le couple
exact que `ParcoursExtraction._ecrire` appelle), sur le **meme rush**, et ce
sont les octets ecrits qui sont compares.

Le detail qui rend la mesure non triviale, et qu'un banc a doubles ne verrait
jamais : les deux cotes n'empruntent pas la meme branche de
`ffmpeg_utils.run_with_written_file_progress`. Sans rappel de progression -- la
CLI -- elle fait un `subprocess.run` bloquant ; avec rappel -- la TUI, qui en
branche toujours un -- elle fait un `Popen` scrute a intervalle. Deux gestes
differents, dont l'AC 7.1 exige qu'ils rendent le **meme octet**.

Quatre sous-taches, quatre sections :

* `F1` -- l'artefact, octet a octet, sur **tout** l'arbre des frames ;
* `F2` -- le manifeste, dont l'ensemble des cles divergentes est **exactement**
  `{lots[].confirmation.mode}` ;
* `F3` -- le code retour, mesure **contre celui de `mmu extract`** pour chaque
  entree de la table du coeur, et non contre une constante recopiee ;
* `F4` -- la progression, mesuree jusqu'a l'ecran, avec le volet qui montre ce
  que le cablage naif aurait eteint en silence.

Regle des fabriques de `CLAUDE.md`, appliquee ici : **deux lots par cote, a
comptes differents** (10 et 24 frames) -- jamais un remplissage uniforme --, et
les mesures qui visent un lot en particulier visent le **second**.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from mixed_media_utility import cadence_previz, extraction, progression
from mixed_media_utility.io.extraction_manifest import MANIFEST_FILENAME
from mixed_media_utility.io.naming import build_lot_id
# Le dossier des frames extraites se LIT du coeur (story 11.14,
# `EPIC11-ARB-220` : `frames/` -> `extract-frames/`). Ce banc mesure une
# IDENTITE entre la TUI et `mmu extract` : un litteral en dur y ferait
# comparer deux arborescences dont l'une n'existe plus, et le rouge
# ressemblerait a une divergence de produit alors qu'il n'en est pas une.
from mixed_media_utility.io.project_layout import EXTRACT_FRAMES_DIRNAME
from mixed_media_utility.tui import atelier_extraction_ecriture as atelier
from mixed_media_utility.tui.execution import EcranResultat, SurfaceExecution

from outils_frontiere import constantes_entieres

requires_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="binaires ffmpeg/ffprobe absents du PATH",
)

#: Les deux cadences du banc. **Elles ne donnent pas le meme compte** (10 et 24
#: frames sur le rush du banc) : un remplissage uniforme rendrait invisible
#: toute inversion d'appariement entre un lot et son contenu -- le mutant `M33`
#: de la story 5.6, ou 165 tests restaient verts.
DEUX_CADENCES = (5.0, 12.0)

#: Le nom de projet, **le meme des deux cotes**. `project_id` derive du nom du
#: dossier : le faire varier ferait diverger le manifeste pour une raison qui
#: n'est pas celle qu'on mesure.
NOM_DE_PROJET = "projet_demo"

#: Le rush du banc : `testsrc` change a chaque frame, donc une duplication ou
#: une permutation d'images se verrait dans les condensats. 30 im/s pendant 2 s
#: = 60 frames source, d'ou 10 frames a 5 im/s et 24 a 12 im/s.
RUSH_ID = "rush_01"


class JournalMuet:
    """Un logger minimal : `run_extraction` en exige un, on n'en lit rien."""

    def info(self, *args, **kwargs) -> None:
        pass

    warning = error = debug = info


class FluxTty:
    """Un flux que `detect_interactive` reconnait comme un terminal.

    Il existe pour une raison precise : l'exception nommee de l'AC 7.2 ne se
    voit que face a un `mmu extract` **interactif**. `run_extraction` force
    `interactive=False` des que `consent_granted` est vrai (`extraction.py`,
    etape 4), donc un `mmu extract --yes` ecrit lui aussi `non_interactif` et
    la comparaison ne montrerait aucun ecart -- elle ne mesurerait pas
    l'exception, elle la contournerait.
    """

    def __init__(self, reponses=()) -> None:
        self._reponses = list(reponses)
        self.ecrit: list[str] = []

    def isatty(self) -> bool:
        return True

    def readline(self) -> str:
        return self._reponses.pop(0) if self._reponses else ""

    def write(self, texte: str) -> int:
        self.ecrit.append(texte)
        return len(texte)

    def flush(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Fabriques : un rush reel, deux projets de deux lots, un de chaque cote
# ---------------------------------------------------------------------------

def rush_reel(chemin: Path) -> Path:
    """Fabriquer le rush avec ffmpeg lui-meme, comme `test_extract_command.py`.

    Le banc reste ainsi autonome : aucun TIFF ni mp4 n'entre dans
    `tests/fixtures/`, et le rush est bit-a-bit reproductible d'une session a
    l'autre.
    """
    resultat = subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi",
         "-i", "testsrc=size=64x36:rate=30:duration=2",
         "-pix_fmt", "yuv420p", str(chemin)],
        capture_output=True, text=True)
    assert resultat.returncode == 0, resultat.stderr
    return chemin


def comptes_du_coeur(rush: Path) -> tuple[int, ...]:
    """Les cardinaux des deux cadences, **lus du coeur** par le chemin de la TUI.

    `EPIC11-ARB-30`, verbatim : « le noyau ne derive **jamais** le cardinal
    d'une duree, il l'exige ». C'est `prepare_previz` que l'ecran `E2-2`
    appelle (AC 3.2) ; le banc l'appelle aussi, plutot que d'ecrire 10 et 24 en
    dur -- un compte recopie serait faux le jour ou la selection change, et le
    banc mentirait sur la progression qu'il mesure au `F4`.
    """
    session = cadence_previz.prepare_previz(video_path=rush,
                                            fps_targets=list(DEUX_CADENCES))
    return tuple(s.expected_frame_count for s in session.selections)


def extraire_par_la_cli(projet: Path, rush: Path, *, interactif: bool) -> int:
    """Ecrire les deux lots par `mmu extract`, une invocation par cadence.

    Rend le code retour de la **derniere** invocation. `interactif` choisit le
    canal d'acquittement : la question au terminal, ou `--yes`.
    """
    from mixed_media_utility import cli   # le BANC peut l'importer, pas la TUI

    code = None
    vrai_stdin, vrai_stdout = sys.stdin, sys.stdout
    if interactif:
        # Une reponse affirmative par invocation. `_AFFIRMATIVE_ANSWERS`
        # accepte `o` ; la question porte en plus l'acceptation de la
        # colorimetrie incomplete, que la meme reponse couvre.
        sys.stdin = FluxTty(["o\n"] * len(DEUX_CADENCES))
        sys.stdout = FluxTty()
    try:
        for cadence in DEUX_CADENCES:
            arguments = ["extract", "--project", str(projet),
                         "--video", str(rush), "--fps", str(cadence)]
            if not interactif:
                arguments += ["--yes", "--accept-unknown-color"]
            code = cli.main(arguments)
            assert code == extraction.CODE_SUCCES, (cadence, code)
    finally:
        sys.stdin, sys.stdout = vrai_stdin, vrai_stdout
    return code


def extraire_par_la_tui(projet: Path, rush: Path, comptes) -> atelier.RapportExtraction:
    """Ecrire les deux lots par le chemin d'ecriture de la TUI.

    `preparer_le_plan` puis `executer_le_plan` : c'est **exactement** le couple
    que `ParcoursExtraction._ecrire` appelle, via `executer_et_conclure`. Le
    coeur n'est pas double -- c'est tout l'objet de ce module.
    """
    projet.parent.mkdir(parents=True, exist_ok=True)
    plan = atelier.preparer_le_plan(
        projet, rush_id=RUSH_ID, video_path=rush,
        cadences=list(zip(DEUX_CADENCES, comptes)),
        largeur=64, hauteur=36, couleur_inconnue_acceptee=True)
    rapport = atelier.executer_le_plan(
        plan, SurfaceExecution(unite=atelier.UNITE), logger=JournalMuet())
    assert rapport.refus is None, rapport.refus
    return rapport


@pytest.fixture(scope="module")
def deux_cotes(tmp_path_factory):
    """Trois projets ecrits une seule fois : le rush est le meme pour les trois.

    Le meme rush et non trois copies : `rushes[].source_path` et
    `source_parent` sont persistes tels quels, et trois chemins differents
    feraient diverger le manifeste sur une difference que le banc aurait
    fabriquee lui-meme.
    """
    base = tmp_path_factory.mktemp("identite")
    rush = rush_reel(base / f"{RUSH_ID}.mp4")
    comptes = comptes_du_coeur(rush)
    assert len(set(comptes)) == len(comptes), (
        "les deux lots doivent avoir des comptes DIFFERENTS : un remplissage "
        f"uniforme ne demasque aucune inversion (comptes={comptes})")

    cli_interactif = base / "cli_interactif" / NOM_DE_PROJET
    cli_yes = base / "cli_yes" / NOM_DE_PROJET
    tui = base / "tui" / NOM_DE_PROJET

    extraire_par_la_cli(cli_interactif, rush, interactif=True)
    extraire_par_la_cli(cli_yes, rush, interactif=False)
    rapport = extraire_par_la_tui(tui, rush, comptes)

    return {"rush": rush, "comptes": comptes, "rapport": rapport,
            "cli_interactif": cli_interactif, "cli_yes": cli_yes, "tui": tui}


# ---------------------------------------------------------------------------
# Outils de comparaison
# ---------------------------------------------------------------------------

def arbre_des_frames(projet: Path) -> dict[str, str]:
    """Chemin **relatif** -> condensat du contenu, sur tout `frames/`.

    Relatif et non le seul nom de fichier : le dossier de lot fait partie de
    l'artefact que l'AC 7.1 nomme (« les TIFF, leur nommage, leur dossier »).
    Un lot ecrit sous un dossier different, ou deux lots intervertis, se voient
    ici et se verraient nulle part ailleurs.
    """
    racine = projet / EXTRACT_FRAMES_DIRNAME
    return {str(chemin.relative_to(projet)):
            hashlib.sha256(chemin.read_bytes()).hexdigest()
            for chemin in sorted(racine.rglob("*")) if chemin.is_file()}


def aplatir(valeur, prefixe: str = "") -> dict[str, object]:
    """Un document JSON -> `chemin pointe -> feuille`.

    Aplatir plutot que comparer deux `dict` : l'egalite de deux documents dit
    seulement qu'ils different, jamais **ou**. L'AC 7.2 exige de nommer
    l'ensemble des cles divergentes, donc il faut des cles.
    """
    if isinstance(valeur, dict):
        aplati: dict[str, object] = {}
        for cle, sous in valeur.items():
            aplati.update(aplatir(sous, f"{prefixe}.{cle}" if prefixe else cle))
        return aplati or {prefixe: {}}
    if isinstance(valeur, list):
        aplati = {}
        for rang, sous in enumerate(valeur):
            aplati.update(aplatir(sous, f"{prefixe}[{rang}]"))
        return aplati or {prefixe: []}
    return {prefixe: valeur}


#: Les deux seuls chemins que le banc neutralise, **chacun avec son motif** :
#:
#: * `created` -- l'instant de creation de l'arborescence projet, ecrit par
#:   `project_layout`. Trois projets crees a la suite peuvent tomber de part et
#:   d'autre d'une seconde ;
#: * `lots[*].confirmation.confirmed_at` -- l'instant de la confirmation.
#:
#: Rien d'autre. En particulier ni les chemins de rush -- le banc emploie le
#: **meme** fichier des trois cotes, donc ils doivent coincider et leur
#: divergence serait un vrai defaut -- ni `confirmation.mode`, que le volet
#: symetrique ci-dessous verifie explicitement.
CHEMINS_VOLATILES = ("created", "lots[*].confirmation.confirmed_at")


def _motif(chemin_avec_etoiles: str) -> re.Pattern:
    """`lots[*].x` -> une expression qui n'accepte qu'un rang entier."""
    morceaux = [re.escape(m) for m in chemin_avec_etoiles.split("[*]")]
    return re.compile(r"\[\d+\]".join(morceaux) + r"\Z")


_VOLATILES = tuple(_motif(c) for c in CHEMINS_VOLATILES)


def est_volatile(chemin: str) -> bool:
    return any(motif.match(chemin) for motif in _VOLATILES)


_ABSENT = object()


def chemins_divergents(gauche: dict, droite: dict) -> set[str]:
    """L'**ensemble** des chemins ou les deux manifestes ne disent pas la meme
    chose -- cle manquante d'un cote comprise.

    C'est la forme que l'AC 7.2 impose : « Aucune autre cle ne diverge »
    (verbatim). Une assertion positive -- « `confirmation.mode` diverge » --
    laisserait passer toute divergence supplementaire, c'est-a-dire exactement
    ce que l'AC interdit.
    """
    a, b = aplatir(gauche), aplatir(droite)
    return {chemin for chemin in set(a) | set(b)
            if a.get(chemin, _ABSENT) != b.get(chemin, _ABSENT)
            and not est_volatile(chemin)}


def manifeste(projet: Path) -> dict:
    return json.loads((projet / MANIFEST_FILENAME).read_text(encoding="utf-8"))


# ===========================================================================
# F1 -- l'artefact, octet a octet
# ===========================================================================

@requires_ffmpeg
def test_l_ARTEFACT_ecrit_par_la_TUI_est_IDENTIQUE_OCTET_A_OCTET_a_celui_de_mmu_extract(
        deux_cotes):
    """AC 7.1, verbatim : « L'artefact ecrit (les TIFF, leur nommage, leur
    dossier) est **identique** a celui d'`mmu extract` a arguments equivalents,
    compare **octet a octet**. »

    La comparaison porte sur **tout** `frames/`, condensat par condensat, et
    non sur les seuls fichiers d'un lot : c'est ce qui fait entrer le nom du
    dossier, le nom des fichiers et le nombre de lots dans la mesure.
    """
    cote_cli = arbre_des_frames(deux_cotes["cli_interactif"])
    cote_tui = arbre_des_frames(deux_cotes["tui"])

    assert cote_cli, "le cote CLI n'a rien ecrit : la mesure ne mesurerait rien"
    assert sum(deux_cotes["comptes"]) == len(cote_cli), (
        "l'arbre compare doit porter les frames des DEUX lots")
    assert cote_tui == cote_cli, (
        "octets divergents : "
        f"{sorted(set(cote_cli) ^ set(cote_tui))} en noms, "
        f"{sorted(c for c in set(cote_cli) & set(cote_tui) if cote_cli[c] != cote_tui[c])} "
        "en contenu")


@requires_ffmpeg
def test_le_SECOND_lot_porte_le_nommage_et_le_DOSSIER_de_mmu_extract(deux_cotes):
    """Regle des fabriques : la cible est placee **ailleurs qu'en premiere
    position**. Une ecriture qui rendrait toujours le premier lot -- le mutant
    `M25` de la story 5.7, ou 257 tests restaient verts -- passe la mesure
    globale si les deux lots existent, mais pas celle-ci.
    """
    second = build_lot_id(RUSH_ID, DEUX_CADENCES[1])
    premier = build_lot_id(RUSH_ID, DEUX_CADENCES[0])
    assert second != premier, "la fabrique doit produire deux lots distinguables"

    fichiers = lambda projet, lot: sorted(
        p.name for p in (projet / EXTRACT_FRAMES_DIRNAME / lot).iterdir()
        if p.is_file())
    noms_cli = fichiers(deux_cotes["cli_interactif"], second)
    noms_tui = fichiers(deux_cotes["tui"], second)

    assert len(noms_tui) == deux_cotes["comptes"][1], (
        "le SECOND lot doit porter le compte de la SECONDE cadence, pas celui "
        "de la premiere")
    assert noms_tui == noms_cli
    assert all(nom.startswith(second) for nom in noms_tui), noms_tui


# ===========================================================================
# F2 -- le manifeste, et l'exception nommee
# ===========================================================================

def test_la_neutralisation_des_VOLATILES_n_avale_pas_ce_qu_on_MESURE():
    """Volet symetrique, et il n'est pas decoratif : un motif volatil trop
    large rendrait les deux mesures ci-dessous vertes en n'observant plus
    rien."""
    assert est_volatile("created")
    assert est_volatile("lots[1].confirmation.confirmed_at")
    assert not est_volatile("lots[1].confirmation.mode")
    assert not est_volatile("lots[1].confirmation.unknown_color_accepted")
    assert not est_volatile("rushes[0].source_path")


def test_le_COMPARATEUR_de_manifestes_voit_les_TROIS_formes_de_divergence():
    """Le banc du banc. Sans lui, l'egalite d'ensembles ci-dessous pourrait
    etre verte parce que le comparateur ne voit rien.

    Les trois formes, et elles ne se confondent pas : une valeur changee, une
    cle **presente d'un seul cote**, et une permutation de liste -- l'ordre des
    lots fait partie de ce que le manifeste dit, et un aplatissement qui
    l'ignorerait laisserait passer le mutant `M25` de la story 5.7.
    """
    reference = {"lots": [{"lot_id": "a", "state": "extraction"},
                          {"lot_id": "b", "state": "extraction"}]}

    change = {"lots": [{"lot_id": "a", "state": "extraction"},
                       {"lot_id": "b", "state": "pdf"}]}
    assert chemins_divergents(reference, change) == {"lots[1].state"}

    en_trop = {"lots": [{"lot_id": "a", "state": "extraction"},
                        {"lot_id": "b", "state": "extraction",
                         "cle_en_trop": 1}]}
    assert chemins_divergents(reference, en_trop) == {"lots[1].cle_en_trop"}

    permute = {"lots": [{"lot_id": "b", "state": "extraction"},
                        {"lot_id": "a", "state": "extraction"}]}
    assert chemins_divergents(reference, permute) == {"lots[0].lot_id",
                                                      "lots[1].lot_id"}

    assert chemins_divergents(reference, reference) == set()


@requires_ffmpeg
def test_le_MANIFESTE_ne_diverge_de_mmu_extract_INTERACTIF_que_par_confirmation_mode(
        deux_cotes):
    """AC 7.2, verbatim : « Le manifeste est identique, **a une exception
    nommee** : `lots[].confirmation.mode` vaut `non_interactif`, la TUI portant
    son propre panneau de confirmation. **Aucune autre cle ne diverge.** »

    L'assertion est celle de l'ensemble : l'AC interdit toute divergence
    supplementaire, et seule une egalite d'ensembles le mesure. Les **deux**
    lots y figurent -- l'exception vaut pour chaque lot, pas seulement le
    premier.
    """
    cote_cli = manifeste(deux_cotes["cli_interactif"])
    cote_tui = manifeste(deux_cotes["tui"])

    attendus = {f"lots[{rang}].confirmation.mode"
                for rang in range(len(DEUX_CADENCES))}
    assert chemins_divergents(cote_cli, cote_tui) == attendus

    for rang in range(len(DEUX_CADENCES)):
        assert cote_cli["lots"][rang]["confirmation"]["mode"] == "interactif"
        assert cote_tui["lots"][rang]["confirmation"]["mode"] == "non_interactif"


@requires_ffmpeg
def test_le_MANIFESTE_est_identique_a_celui_de_mmu_extract_yes_SANS_AUCUNE_exception(
        deux_cotes):
    """Le second volet, celui qui borne l'exception a ce qu'elle est.

    Fait `F5` de la fiche : `run_extraction` force `interactive=False` des que
    `consent_granted=True`, et la TUI passe forcement `consent_granted=True`
    puisqu'elle porte son propre panneau. L'ecart de l'AC 7.2 est donc un ecart
    de **canal d'acquittement**, pas un ecart d'ecriture : face au meme canal --
    `mmu extract --yes` --, l'ensemble des cles divergentes est **vide**.

    Sans ce volet, la mesure precedente serait satisfaite par une TUI qui
    ecrirait `mode` differemment pour n'importe quelle raison.
    """
    assert chemins_divergents(manifeste(deux_cotes["cli_yes"]),
                              manifeste(deux_cotes["tui"])) == set()


# ===========================================================================
# F3 -- le code retour, lu de la table descendue en B3
# ===========================================================================

def rush_factice(tmp_path: Path) -> Path:
    """Un fichier qui existe, et rien de plus.

    `validate_extraction_inputs` n'exige que l'existence : les mesures de code
    retour n'atteignent jamais ffmpeg, `run_extraction` etant remplacee par une
    panne. Elles tournent donc **sans** binaire externe.
    """
    chemin = tmp_path / f"{RUSH_ID}.mp4"
    chemin.write_bytes(b"ceci n'est pas un rush")
    return chemin


def plan_factice(projet: Path, rush: Path) -> atelier.PlanExtraction:
    """Un plan a deux lots dont les comptes different (regle des fabriques)."""
    projet.mkdir(parents=True, exist_ok=True)
    return atelier.preparer_le_plan(
        projet, rush_id=RUSH_ID, video_path=rush,
        cadences=[(DEUX_CADENCES[0], 10), (DEUX_CADENCES[1], 24)],
        largeur=64, hauteur=36, couleur_inconnue_acceptee=True)


#: Les douze entrees de la table du coeur, **lues** et jamais recopiees. Un
#: parametrage ecrit a la main en oublierait, et c'est l'oubli qui laisse
#: passer un code divergent.
ENTREES_DE_LA_TABLE = [
    pytest.param(classe, id=classe.__name__)
    for classe, _code in extraction.CODES_DE_SORTIE
]


@pytest.mark.parametrize("classe", ENTREES_DE_LA_TABLE)
def test_le_code_retour_de_la_TUI_est_CELUI_DE_MMU_EXTRACT_pour_CHAQUE_entree_de_la_table(
        tmp_path, monkeypatch, classe):
    """AC 7.3, verbatim : « Le code retour est identique. »

    `EPIC11-ARB-75`, verbatim : « La table descend dans `extraction.py` et est
    **lue des deux cotes**. La duplication avec test symetrique etait l'autre
    option : elle laisse deux tables vraies au meme moment, et un test
    symetrique ne rougit qu'apres qu'on a diverge. »

    **Aucun code attendu n'est ecrit dans ce test.** Les deux cotes sont
    compares l'un a l'autre : la meme panne est levee depuis `run_extraction`,
    `mmu extract` rend son code, la TUI rend le sien, et c'est leur egalite qui
    est mesuree. Une constante attendue recopiee ici serait une troisieme table,
    exactement ce que l'arbitrage refuse.

    Le parcours couvre **les douze entrees**, `KeyboardInterrupt` comprise --
    la seule que la CLI attrape dans une branche a part, donc la seule ou les
    deux cotes pourraient diverger sans que rien d'autre bouge.
    """
    from mixed_media_utility import cli

    panne = classe("panne simulee")

    def toujours_en_panne(**kwargs):
        raise panne

    monkeypatch.setattr(extraction, "run_extraction", toujours_en_panne)
    rush = rush_factice(tmp_path)

    code_cli = cli.main(["extract", "--project", str(tmp_path / "cote_cli"),
                         "--video", str(rush), "--fps", str(DEUX_CADENCES[0]),
                         "--yes", "--accept-unknown-color"])

    rapport = atelier.executer_le_plan(
        plan_factice(tmp_path / "cote_tui", rush),
        SurfaceExecution(unite=atelier.UNITE), logger=JournalMuet())

    assert rapport.refus is not None, "la table nomme cette panne : elle refuse"
    assert rapport.code_retour == code_cli, (
        f"{classe.__name__} : la TUI rend {rapport.code_retour}, "
        f"mmu extract rend {code_cli}")


def test_la_TUI_ne_RECOPIE_aucun_code_retour(paquet_tui):
    """Frontiere negative, forme scopee et assumee comme telle.

    « Lit la table » n'est pas mesurable par l'absence de `0` et `1` dans tout
    le module : ce sont aussi un rang de liste et un cardinal, et une frontiere
    qui les interdirait serait affaiblie a la premiere relecture. Elle est donc
    posee la ou un code recopie se cacherait : dans les quatre endroits qui
    **decident** d'un code retour, ou aucun entier litteral n'a rien a faire.

    Deux volets, pour que la frontiere ne puisse pas etre verte a vide :
    les quatre porteurs existent, et le module reference bien la table du coeur.
    """
    module = paquet_tui / "atelier_extraction_ecriture.py"
    arbre = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
    porteurs = {"code_retour", "refus_de", "refus_d_etat_de_lot",
                "executer_le_plan"}

    vus = set()
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.FunctionDef) or noeud.name not in porteurs:
            continue
        vus.add(noeud.name)
        entiers = [f.value for f in ast.walk(noeud)
                   if isinstance(f, ast.Constant)
                   and isinstance(f.value, int) and not isinstance(f.value, bool)]
        assert entiers == [], (
            f"{noeud.name} porte un entier litteral ({entiers}) : un code "
            "retour se lit de extraction.CODES_DE_SORTIE, il ne se recopie pas")

    assert vus == porteurs, f"porteurs introuvables : {porteurs - vus}"

    # Les trois codes qui n'ont aucun autre sens plausible dans ce module --
    # `0` et `1` sont exclus a dessein, ce sont aussi des rangs et des
    # cardinaux, et le volet scope ci-dessus les couvre la ou ils mordraient.
    sans_autre_sens = {extraction.CODE_PREREQUIS_ABSENT, extraction.CODE_REFUS,
                       extraction.CODE_INTERRUPTION}
    recopies = sans_autre_sens & set(constantes_entieres(module))
    assert recopies == set(), (
        f"codes de sortie recopies en clair dans le module : {recopies}")


def _lit_la_table_de_l_EXTRACTION(source: str) -> bool:
    """`extraction.correspondance_de_sortie` reference **par le code**.

    A l'AST, jamais par un grep, et pour deux motifs distincts :

    * un **commentaire** qui nomme la fonction n'en lit aucune table -- c'est
      la lecon du finding `I3`, ou le nom etait partout dans les commentaires
      et nulle part dans le code ;
    * le coeur porte **deux** fonctions de ce nom, une par chaine :
      `extraction.correspondance_de_sortie` et
      `scan_write.correspondance_de_sortie`. Ce sont **deux tables**, pas deux
      lectures de la meme, et seule la premiere est celle que
      `EPIC11-ARB-75` veut lue une fois.
    """
    arbre = ast.parse(source)
    for noeud in ast.walk(arbre):
        if (isinstance(noeud, ast.Attribute)
                and noeud.attr == "correspondance_de_sortie"
                and isinstance(noeud.value, ast.Name)
                and noeud.value.id == "extraction"):
            return True
        if (isinstance(noeud, ast.ImportFrom)
                and (noeud.module or "").split(".")[-1] == "extraction"
                and any(alias.name == "correspondance_de_sortie"
                        for alias in noeud.names)):
            return True
    return False


def test_la_TUI_LIT_la_table_du_coeur_et_n_en_porte_AUCUNE_moitie(paquet_tui):
    """Volet symetrique du precedent : une TUI qui ne lirait plus la table le
    passerait sans rien mesurer.

    La mesure est faite sur le paquet **entier** : si un second module de la
    TUI se remettait a nommer une exception avec son code, il apparaitrait ici
    comme un second lecteur de la table -- ce qui est justement ce que
    `EPIC11-ARB-75` remplace par une lecture unique.

    **Resserree le 2026-09-01 (story 11.6, lot E), sur la CHOSE et non sur le
    MOT** (`EPIC11-ARB-127`). Elle grepait `correspondance_de_sortie` en texte
    nu ; le jour ou l'atelier Scan a lu **sa** table -- celle de `scan_write`,
    une autre table, un autre vocabulaire de refus --, la garde a rougi en
    annoncant « un second lecteur », ce qui etait faux. Elle lit donc l'arbre
    et ne compte que les lecteurs de la table de l'**extraction**. On resserre
    la frontiere sur la chose ; on ne renomme pas la chose pour la faire
    passer dessous.
    """
    ecriture = paquet_tui / "atelier_extraction_ecriture.py"
    assert _lit_la_table_de_l_EXTRACTION(
        ecriture.read_text(encoding="utf-8"))

    lecteurs = sorted(
        chemin.name for chemin in paquet_tui.rglob("*.py")
        if _lit_la_table_de_l_EXTRACTION(chemin.read_text(encoding="utf-8")))
    assert lecteurs == [ecriture.name], (
        f"la table doit avoir UN lecteur dans la TUI, trouve : {lecteurs}")


def test_la_mesure_du_LECTEUR_UNIQUE_distingue_les_DEUX_tables_du_coeur():
    """Volet symetrique du resserrement : sans lui, une mesure qui ne verrait
    plus rien passerait le test ci-dessus sans rien mesurer.

    Les trois formes que la garde doit trancher : la lecture reelle, la
    lecture de l'**autre** table, et la simple mention en commentaire.
    """
    assert _lit_la_table_de_l_EXTRACTION(
        "extraction.correspondance_de_sortie(exception)")
    assert _lit_la_table_de_l_EXTRACTION(
        "from ..extraction import correspondance_de_sortie")
    assert not _lit_la_table_de_l_EXTRACTION(
        "scan_write.correspondance_de_sortie(exception)")
    assert not _lit_la_table_de_l_EXTRACTION(
        "# voir extraction.correspondance_de_sortie pour le motif")


# ===========================================================================
# F4 -- la progression, et la reserve mesuree sur `emetteur()`
# ===========================================================================

def test_l_emetteur_NU_passe_TEL_QUEL_au_coeur_ETEINDRAIT_le_canal_EN_SILENCE():
    """La reserve consignee au plan, instruite ici -- et fermee par le volet.

    Le fait mesure : `ffmpeg_utils.extract_selected_frames` remet le
    `rappel_progression` recu dans un `progression.EmetteurProgression`, dont
    le constructeur fait `rappel if callable(rappel) else None`. Or
    `SurfaceExecution.emetteur(total)` rend **un `EmetteurProgression`**, qui
    n'est pas appelable : le passer tel quel a `run_extraction` rendrait
    l'emetteur du coeur **inactif**, sans lever, sans trace, sans barre.

    La mesure est faite avec la classe du coeur elle-meme, au point exact ou le
    silence se produirait -- pas sur un `callable()` de banc, qui reproduirait
    le raisonnement au lieu de le verifier.
    """
    surface = SurfaceExecution(unite=atelier.UNITE)

    naif = progression.EmetteurProgression(surface.emetteur(24), 24)
    assert naif.actif is False, (
        "si celui-la devenait actif, l'adaptation d'arite de "
        "canal_de_progression n'aurait plus de raison d'etre")

    adapte = progression.EmetteurProgression(
        atelier.canal_de_progression(surface, 24), 24)
    assert adapte.actif is True

    # Et il transmet : `actif` ne dit que la moitie de ce qui compte.
    assert adapte.emettre(24) is True
    assert (surface.avancement.faites, surface.avancement.total) == (24, 24)


@requires_ffmpeg
def test_la_PROGRESSION_du_VRAI_run_extraction_atteint_l_ECRAN(tmp_path, banc):
    """AC 7.4, verbatim : « La progression passe par `rappel_progression` et
    `SurfaceExecution.emetteur()` : aucun second canal. »

    Le banc qui **rougit si l'emetteur cesse d'etre appele** : le coeur n'est
    pas double, ffmpeg ecrit pour de vrai, et ce sont les jalons arrives dans
    l'avancement de l'ecran monte qui sont lus. Rendre `canal_de_progression`
    a son cablage naif -- ou cesser de passer `rappel_progression` -- fait
    tomber le compte a zero jalon, sans qu'aucune exception ne soit levee.

    L'ecran est monte **avant** l'appel au coeur, comme `_ecrire` le fait :
    c'est `EcranExecution.on_mount` qui abonne l'ecran aux jalons, et l'inverse
    ferait partir la barre de la fin.

    Les deux lots ont des cardinaux **differents** : un canal qui rendrait
    toujours le premier, ou une somme qui compterait deux fois le meme, ne se
    demasquent pas sur deux lots identiques.

    **Ce que la 11.4e change ici** (AC 8.1) : la surface agrege la PASSE, donc
    le total est la somme des deux cardinaux d'un bout a l'autre, et les
    comptes de fin de lot sont **cumules**. La forme de la mesure ne change
    pas -- un jalon nomme par lot, et le dernier qui ferme la passe.
    """
    from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin

    rush = rush_reel(tmp_path / f"{RUSH_ID}.mp4")
    comptes = comptes_du_coeur(rush)
    projet = tmp_path / "cote_tui" / NOM_DE_PROJET
    projet.parent.mkdir(parents=True, exist_ok=True)
    plan = atelier.preparer_le_plan(
        projet, rush_id=RUSH_ID, video_path=rush,
        cadences=list(zip(DEUX_CADENCES, comptes)),
        largeur=64, hauteur=36, couleur_inconnue_acceptee=True)

    app = CoqueTui(paliers=[PalierTemoin("Projet", "q quitter"),
                            PalierTemoin("Ateliers", "q quitter")],
                   contexte=Contexte(NOM_DE_PROJET))
    jalons: list[tuple[int, int]] = []

    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        ecran = atelier.ouvrir_l_execution(pilote.app, plan)
        await pilote.pause()
        ecran.surface.abonner(lambda a: jalons.append((a.faites, a.total)))
        rapport = atelier.executer_et_conclure(
            pilote.app, ecran, plan, logger=JournalMuet())
        await pilote.pause()
        return rapport, ecran.surface, type(pilote.app.screen).__name__

    rapport, surface, ecran_final = banc(app, scenario)

    assert rapport.refus is None, rapport.refus
    assert rapport.code_retour == extraction.CODE_SUCCES
    assert jalons, (
        "aucun jalon n'a atteint l'ecran : le canal de progression est eteint")
    # Un jalon de fin par lot, chacun sur le CUMUL de la passe et son total.
    # C'est ce couple qui distingue un canal vivant d'un canal eteint, et le
    # cumul qui distingue une passe agregee d'une passe remise a zero par lot.
    total = sum(comptes)
    cumul = 0
    for compte in comptes:
        cumul += compte
        assert (cumul, total) in jalons, (jalons, comptes)
    assert jalons[-1] == (total, total), jalons
    assert [f for f, _t in jalons] == sorted(f for f, _t in jalons), (
        "le compte de la passe ne recule jamais entre deux lots", jalons)
    assert surface.journal, "le journal de la surface doit porter les jalons"
    assert ecran_final == EcranResultat.__name__


def test_le_canal_de_progression_est_LE_SEUL(paquet_tui):
    """« Aucun second canal », mesure sur le code plutot que sur une execution.

    Trois volets, et ils se completent : `emetteur` n'est appele que dans
    `canal_de_progression` ; `rappel_progression` n'est passe au coeur qu'a un
    seul endroit ; et les entrees basses de la surface -- `noter`, l'ecriture
    directe dans `avancement` -- ne sont touchees nulle part dans l'atelier.
    """
    modules = [paquet_tui / "atelier_extraction_ecriture.py",
               paquet_tui / "atelier_extraction.py"]
    appels_emetteur: list[str] = []
    passages_du_rappel: list[str] = []

    for module in modules:
        arbre = ast.parse(module.read_text(encoding="utf-8"),
                          filename=str(module))
        # Fonction englobante de chaque appel, pour nommer OU c'est passe.
        for fonction in [n for n in ast.walk(arbre)
                         if isinstance(n, ast.FunctionDef)]:
            for noeud in ast.walk(fonction):
                if (isinstance(noeud, ast.Call)
                        and isinstance(noeud.func, ast.Attribute)
                        and noeud.func.attr == "emetteur"):
                    appels_emetteur.append(fonction.name)
                if isinstance(noeud, ast.Call):
                    for mot_cle in noeud.keywords:
                        if mot_cle.arg == "rappel_progression":
                            passages_du_rappel.append(fonction.name)
        interdits = {"noter"} & {
            n.attr for n in ast.walk(arbre) if isinstance(n, ast.Attribute)}
        assert interdits == set(), (
            f"{module.name} touche une entree basse de la surface : {interdits}")

    assert appels_emetteur == ["canal_de_progression"], appels_emetteur
    assert passages_du_rappel == ["executer_le_plan"], passages_du_rappel


# ===========================================================================
# AC 7.5 -- le refus d'etat de lot, mesure contre le VRAI coeur
# ===========================================================================

@requires_ffmpeg
def test_un_lot_passe_a_pdf_est_REFUSE_sans_qu_AUCUNE_ecriture_ait_eu_lieu(
        tmp_path):
    """AC 7.5, verbatim : « Un lot deja passe a `pdf` ou au-dela est **refuse**
    par le coeur (`LotStateConflictError`) sans qu'aucune ecriture ait eu lieu ;
    la TUI rend ce refus tel quel. »

    Mesure contre le **vrai** coeur, et c'est la seule qui donne son sens a la
    garde : `run_extraction` ne verifie la transition qu'a sa persistance,
    c'est-a-dire **apres** avoir ecrit les TIFF et, en ecrasement, **apres**
    avoir efface le lot precedent (`_clear_existing_lot`). Un banc a double
    montre que la garde est posee avant l'appel ; celui-ci montre ce qu'elle
    protege.

    **Ce que le condensat ne mesure PAS, et c'est une mesure, pas une
    supposition.** Retirer la garde et relancer laisse les condensats
    **identiques** : le lot est efface puis reecrit, et `testsrc` etant
    deterministe, les octets qui reviennent sont les memes. Une assertion sur
    le contenu seul est donc verte des deux cotes -- c'est la fixture de
    synthese qui ne reproduit pas la panne, piege deja paye dans ce depot le
    2026-08-10. La mesure porte donc sur ce qu'une reecriture change quoi
    qu'elle rende : l'**identite des fichiers sur le disque** (numero d'inode,
    detruit par `unlink` + `replace`) et la survie d'un **temoin** depose dans
    le dossier de lot, que `_clear_existing_lot` supprimerait avec le reste.

    Le lot vise est le **SECOND** du plan : une garde qui ne regarderait que
    `lots[0]` ne se demasque pas autrement.

    **`EPIC11-ARB-83` -- ce que cette prose affirmait n'est plus vrai depuis
    `8894f52`, et il faut lire l'arbitrage avec sa date.** Il disait, le
    2026-08-30 au matin : « La garde `refus_d_etat_de_lot` de la TUI (lot E)
    est **load-bearing** : elle est ce qui tient l'AC 7.5 [...] La retirer au
    motif que "le coeur refuse de toute facon" detruirait des frames livrees. »
    C'etait exact tant que le coeur ne jugeait la transition qu'a sa
    persistance. Le lot V1 de la story 11.4c l'a **corrige le meme jour** :
    `run_extraction` juge desormais la transition a son **etape 1**, avant
    `ensure_ffmpeg_available`, et sa propre campagne le mesure aux inodes et au
    temoin (14 mutants, 14 tues).

    **Ce que la garde de la TUI est devenue, et pourquoi elle reste.** Elle
    cesse d'etre load-bearing et devient une **defense en profondeur** : ce
    n'est plus elle qui sauve les frames, c'est elle qui donne a l'operateur un
    **ecran de refus** plutot qu'une exception remontee du coeur, et qui evite
    le probe et la question de confirmation. `EPIC11-ARB-86` la protege
    nommement (« Cette garde ne se retire pas »), et ce banc en mesure le seul
    effet qui lui reste en propre : **le coeur n'est pas appele du tout**.

    **La consequence sur les deux paragraphes ci-dessus, dite plutot que tue.**
    « Retirer la garde laisse les condensats identiques » decrivait le monde
    d'avant V1 : le lot etait efface puis reecrit. Aujourd'hui, retirer la
    garde ferait refuser le coeur a son etape 1, donc les frames survivraient
    de toute facon -- ce banc ne mesure donc plus la survie des frames CONTRE
    une destruction, il mesure qu'aucun des deux etages ne l'entreprend. La
    mesure aux inodes et au temoin garde tout son sens : elle est ce qui
    distingue « rien n'a bouge » de « ca a ete reecrit a l'identique », et la
    fixture `testsrc` etant deterministe, aucun condensat ne saurait le faire.
    """
    rush = rush_reel(tmp_path / f"{RUSH_ID}.mp4")
    comptes = comptes_du_coeur(rush)
    projet = tmp_path / "projet" / NOM_DE_PROJET
    projet.parent.mkdir(parents=True, exist_ok=True)

    # 1. les deux lots sont ecrits normalement.
    extraire_par_la_tui(projet, rush, comptes)
    avant = arbre_des_frames(projet)
    assert len(avant) == sum(comptes)

    # 2. le SECOND passe a `pdf` : ses frames sont desormais referencees par
    #    une planche imprimee.
    vise = build_lot_id(RUSH_ID, DEUX_CADENCES[1])
    dossier_vise = projet / EXTRACT_FRAMES_DIRNAME / vise
    temoin = dossier_vise / "temoin-de-non-ecriture.txt"
    temoin.write_text("rien ne doit toucher ce dossier", encoding="utf-8")
    inodes = {p.name: p.stat().st_ino for p in dossier_vise.iterdir()
              if p.is_file()}
    document = manifeste(projet)
    rangs = [rang for rang, lot in enumerate(document["lots"])
             if lot["lot_id"] == vise]
    assert rangs == [1], (
        f"le lot vise doit etre le SECOND du manifeste (trouve {rangs})")
    document["lots"][rangs[0]]["state"] = "pdf"
    (projet / MANIFEST_FILENAME).write_text(json.dumps(document),
                                            encoding="utf-8")

    # 3. on redemande les deux memes cadences : les deux lots sont deja la,
    #    donc le plan est un ECRASEMENT -- le regime ou le coeur effacerait.
    plan = atelier.preparer_le_plan(
        projet, rush_id=RUSH_ID, video_path=rush,
        cadences=list(zip(DEUX_CADENCES, comptes)),
        largeur=64, hauteur=36, couleur_inconnue_acceptee=True)
    assert plan.lots[1].deja_present and plan.lots[1].etat == "pdf"

    rapport = atelier.executer_le_plan(
        plan, SurfaceExecution(unite=atelier.UNITE), logger=JournalMuet())

    assert rapport.refus is not None
    assert rapport.refus.code == "LotStateConflictError"
    assert rapport.code_retour == extraction.code_de_sortie(
        extraction.ExtractionPersistenceError("x"))

    # Le contenu, d'abord -- necessaire mais **pas suffisant**, voir le
    # docstring.
    du_lot_vise = {c: n for c, n in avant.items() if f"/{vise}/" in c}
    assert du_lot_vise, "la mesure doit porter sur un lot reellement ecrit"
    apres = arbre_des_frames(projet)
    assert {c: apres.get(c) for c in du_lot_vise} == du_lot_vise

    # Puis ce qui mord : aucun fichier n'a ete recree, et le temoin est la.
    assert temoin.is_file(), (
        "le dossier du lot passe a pdf a ete vide : le refus est arrive APRES "
        "une ecriture, ce que l'AC 7.5 interdit")
    assert {p.name: p.stat().st_ino for p in dossier_vise.iterdir()
            if p.is_file()} == inodes, (
        "les frames du lot passe a pdf ont ete effacees puis reecrites : le "
        "contenu revient identique, l'ecriture a bien eu lieu")
