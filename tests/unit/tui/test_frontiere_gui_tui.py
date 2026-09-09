# -*- coding: utf-8 -*-
"""La frontiere entre les deux surfaces : ce que la TUI a le droit de prendre.

**Une frontiere existante a du bouger, et voici ce qui la remplace.**
`tests/unit/gui/test_frontieres_gui.py::test_le_coeur_n_importe_jamais_le_paquet_gui`
balayait tout `src/mixed_media_utility/` **sauf** `gui/` et y interdisait tout
import de la GUI. L'arrivee d'une seconde surface l'a fait rougir : `tui/jetons`
importe `gui.jetons`, et il le **doit** -- l'AC 2 de la story 11.0 et
`DESIGN.md` section 5 de la TUI l'exigent l'un comme l'autre, « sans quoi les
deux surfaces divergeront au premier ajustement de contraste ».

L'intention de cette frontiere -- « la GUI est un client du coeur, elle n'est
jamais importee **par lui** » -- ne visait pas un autre client. Ce qu'elle
protegeait vraiment, c'est que **Qt n'entre pas dans un graphe d'import qui n'en
veut pas** : la TUI existe pour les sessions SSH sans X11 et les machines
legeres, ou PySide6 peut tout simplement ne pas etre installe.

Ce fichier remplace donc une garde de perimetre par deux gardes de fond, plus
serrees que celle qu'elles remplacent :

1. la TUI n'importe de la GUI que des modules **nommes un par un**, et
   l'assertion est une **egalite** -- le suivant fera rougir ;
2. importer la TUI **n'importe aucun toolkit Qt**, mesure dans un processus ou
   PySide6 est rendu indisponible.

**La liste a grandi une fois, deliberement** (story 11.2) : `gui.depot_projets`
rejoint `gui.jetons`, parce que la creation d'un projet y vit deja et qu'une
seconde implementation cote TUI ferait ecrire deux `project.json` differents
pour le meme geste. C'est le motif de l'elargissement, pas une derogation : la
garde 2, elle, ne s'est pas relachee -- elle s'est **etendue** au graphe
d'import complet que cette story fait entrer.
"""

import ast
import importlib
import subprocess
import sys
from pathlib import Path

import pytest

#: Les modules de `gui/` que la TUI a le droit de prendre. **Une liste nommee,
#: et l'assertion reste une EGALITE** : un troisieme import doit rougir. Un
#: `issubset`, ou un motif large comme « tout `gui/` sans Qt », transformerait
#: cette frontiere en formalite -- c'est precisement ce que la story 11.2
#: refuse de faire en l'elargissant.
#:
#: **Pourquoi elle s'elargit, et le motif est le meme que pour les jetons.**
#: `gui/depot_projets.py` porte deja la creation d'un projet : `creer_projet`,
#: `manifeste_minimal`, `dossier_cible` et les trois refus, tous branches sur
#: `ensure_project_layout` et l'ecriture atomique validee du coeur. Une seconde
#: implementation cote TUI divergerait au premier ajustement, et **c'est le
#: coeur qui perdrait** : deux surfaces ecriraient deux `project.json`
#: differents pour le meme geste. C'est mot pour mot l'argument qui a fait
#: importer `gui.jetons` plutot que de recopier six couleurs.
#:
#: Ce que le nom du paquet suggere -- « la TUI depend de la GUI » -- est
#: trompeur, et les deux tests de fond ci-dessous mesurent ce qui compte
#: vraiment : **aucun toolkit Qt n'entre dans le graphe d'import de la TUI**,
#: ni directement ni transitivement.
MODULES_GUI_AUTORISES = {
    "mixed_media_utility.gui.jetons",
    "mixed_media_utility.gui.depot_projets",
}

TOOLKITS = ("PySide6", "PyQt5", "PyQt6", "shiboken6")

#: Programme joue dans un processus ou PySide6 est rendu introuvable. S'il
#: imprime la coque, c'est que la TUI se monte sur une machine sans Qt.
#: **Le bloqueur passe par `find_spec`, pas par `find_module`.** Le protocole
#: `find_module` / `load_module` est retire depuis Python 3.12 : un bloqueur
#: ecrit avec lui n'est jamais consulte, donc il ne bloque rien et le test qui
#: s'appuie dessus est vert sans avoir rien mesure. C'est le volet symetrique
#: ci-dessous qui l'a demasque -- une premiere redaction employait bien
#: `find_module`, et `import PySide6.QtWidgets` passait tranquillement.
PROGRAMME_SANS_QT = """
import sys

INTERDITS = ("PySide6", "shiboken6")

class Bloqueur:
    def find_spec(self, nom, chemin=None, cible=None):
        if nom.split(".")[0] in INTERDITS:
            raise ImportError("PySide6 indisponible (simule)")
        return None

sys.meta_path.insert(0, Bloqueur())
sys.path.insert(0, "src")

from mixed_media_utility.tui.coque import CoqueTui
from mixed_media_utility.tui import jetons

charges = sorted(m for m in sys.modules if m.split(".")[0] in
                 ("PySide6", "PyQt5", "PyQt6", "shiboken6"))
print("coque=", CoqueTui.__name__, sep="")
print("jetons=", len(jetons.COULEURS), sep="")
print("toolkits=", ",".join(charges), sep="")
"""


#: Le paquet de la GUI, nomme une fois : c'est lui qui distingue « importer un
#: module DE `gui/` » de « importer un symbole DANS un module de `gui/` ».
PAQUET_GUI = "mixed_media_utility.gui"


def _imports_de_gui(chemin, paquet_tui):
    """Les **modules** de `gui/` importes par un fichier, en nom absolu.

    La mesure porte sur le module atteint, jamais sur le symbole pris dedans :
    `from ..gui.depot_projets import NOM_FICHIER_PROJET` et
    `from ..gui.depot_projets import creer_projet` atteignent le **meme**
    module, et les compter separement ferait grossir la frontiere a chaque
    symbole -- elle cesserait alors de mesurer ce qu'elle promet.

    Les deux formes se distinguent par leur cible : quand celle-ci est le
    paquet nu (`from ..gui import jetons`), chaque alias **est** un module ;
    quand elle est deja un module (`from ..gui.jetons import NEUTRES`), c'est
    elle qu'on retient.
    """
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    trouves = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.ImportFrom):
            if noeud.level:
                # Import relatif : `..gui` depuis `tui/` vaut le paquet racine.
                base = "mixed_media_utility" if noeud.level == 2 else \
                    "mixed_media_utility.tui"
                cible = f"{base}.{noeud.module}" if noeud.module else base
            else:
                cible = noeud.module or ""
            if not (".gui" in cible or cible.endswith("gui")):
                continue
            if cible == PAQUET_GUI:
                trouves.update(f"{cible}.{alias.name}" for alias in noeud.names)
            else:
                trouves.add(cible)
        elif isinstance(noeud, ast.Import):
            trouves.update(alias.name for alias in noeud.names
                           if ".gui" in alias.name)
    return trouves


def test_la_tui_ne_prend_de_la_gui_que_les_modules_nommes(sources_tui, paquet_tui):
    """Frontiere de fond : deux modules, nommes, et l'assertion est une EGALITE.

    Plus serree que celle qu'elle remplace : l'ancienne garde interdisait tout
    import de la GUI depuis le reste du depot, sans distinguer le coeur d'une
    seconde surface. Celle-ci autorise **exactement** ce qui est liste et fera
    rougir le troisieme -- y compris un import ajoute par megarde dans un
    module d'atelier des vagues suivantes.
    """
    pris = set()
    for chemin in sources_tui:
        pris |= _imports_de_gui(chemin, paquet_tui)
    assert pris == MODULES_GUI_AUTORISES, sorted(pris)


def test_la_mesure_mord_sur_un_TROISIEME_import(tmp_path, paquet_tui):
    """Volet symetrique : un module qui prendrait `gui.coquille` doit sortir.

    Il prend **aussi** les deux modules autorises, pour que la mesure porte sur
    l'ajout et non sur l'absence des deux autres -- une assertion qui rougirait
    de toute facon ne prouverait rien de l'elargissement.
    """
    chemin = tmp_path / "module_fautif.py"
    chemin.write_text("from ..gui import coquille\n"
                      "from mixed_media_utility.gui.jetons import NEUTRES\n"
                      "from ..gui.depot_projets import creer_projet\n",
                      encoding="utf-8")
    pris = _imports_de_gui(chemin, paquet_tui)
    assert "mixed_media_utility.gui.coquille" in pris
    assert pris > MODULES_GUI_AUTORISES
    assert pris != MODULES_GUI_AUTORISES


def test_deux_symboles_du_meme_module_ne_comptent_que_pour_un(tmp_path, paquet_tui):
    """La mesure porte sur le MODULE atteint, pas sur le symbole pris dedans.

    Sans cette propriete, la frontiere grossirait d'une entree a chaque symbole
    importe et il faudrait la relacher a chaque commit -- c'est-a-dire qu'elle
    cesserait de mesurer quoi que ce soit.
    """
    chemin = tmp_path / "deux_symboles.py"
    chemin.write_text("from ..gui.depot_projets import creer_projet\n"
                      "from ..gui.depot_projets import NOM_FICHIER_PROJET\n",
                      encoding="utf-8")
    assert _imports_de_gui(chemin, paquet_tui) == {
        "mixed_media_utility.gui.depot_projets"}


#: Les modules de `gui/` que la TUI importe et qui, eux, importent des choses.
#: `gui/jetons.py` n'importe RIEN et se mesure a part (test ci-dessous) ;
#: `gui/depot_projets.py` importe `io/` et `gui/modele_projets.py`, donc la
#: garde qui compte pour lui n'est pas « il n'importe rien » mais « rien de ce
#: qu'il importe n'amene Qt ».
MODULES_GUI_SANS_QT = ("depot_projets", "modele_projets")

#: Programme joue dans un processus ou PySide6 est rendu introuvable, etendu a
#: l'ECRAN PROJET de la story 11.2 : c'est lui qui fait entrer
#: `gui.depot_projets` dans le graphe d'import de la TUI, et donc lui qu'il
#: faut monter pour que la mesure porte sur le produit reel -- `mmu-tui` sur
#: une session SSH sans X11, ou PySide6 peut ne pas etre installe du tout.
PROGRAMME_SANS_QT_AVEC_PROJET = PROGRAMME_SANS_QT.replace(
    "from mixed_media_utility.tui import jetons",
    "from mixed_media_utility.tui import jetons\n"
    "from mixed_media_utility.tui import projets\n"
    "from mixed_media_utility.tui.projets import diagnostiquer, Recents",
).replace(
    'print("jetons=", len(jetons.COULEURS), sep="")',
    'print("jetons=", len(jetons.COULEURS), sep="")\n'
    'print("projets=", projets.FICHIER_RECENTS, sep="")',
)


@pytest.mark.parametrize("module", MODULES_GUI_SANS_QT)
@pytest.mark.parametrize("toolkit", TOOLKITS)
def test_les_modules_gui_pris_par_la_tui_n_importent_aucun_toolkit(module, toolkit):
    """AC 6.3, volet DIRECT : mesure a l'AST sur le fichier lui-meme."""
    cible = importlib.import_module(f"mixed_media_utility.gui.{module}")
    arbre = ast.parse(Path(cible.__file__).read_text(encoding="utf-8"))
    racines = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            racines.update(a.name.split(".")[0] for a in noeud.names)
        elif isinstance(noeud, ast.ImportFrom) and not noeud.level:
            racines.add((noeud.module or "").split(".")[0])
    assert toolkit not in racines, f"gui/{module}.py importe {toolkit}"


def test_le_module_de_jetons_de_la_gui_n_importe_rien():
    """**C'est ce qui rend l'import inoffensif**, et ca se mesure au lieu de se
    supposer : un `gui/jetons.py` qui importerait un widget ferait entrer Qt
    dans la TUI par la porte de derriere."""
    from mixed_media_utility.gui import jetons as jetons_gui

    arbre = ast.parse(open(jetons_gui.__file__, encoding="utf-8").read())
    imports = [n for n in ast.walk(arbre)
               if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert imports == [], f"gui/jetons.py importe {imports}"


@pytest.mark.parametrize("toolkit", TOOLKITS)
def test_aucun_module_de_la_tui_n_importe_un_toolkit(toolkit, sources_tui):
    for chemin in sources_tui:
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        racines = set()
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Import):
                racines.update(a.name.split(".")[0] for a in noeud.names)
            elif isinstance(noeud, ast.ImportFrom) and not noeud.level:
                racines.add((noeud.module or "").split(".")[0])
        assert toolkit not in racines, chemin.name


def test_la_tui_se_monte_sur_une_machine_sans_qt(racine_depot):
    """La mesure qui compte pour le produit : `mmu-tui` sur une session SSH.

    Le processus fils rend PySide6 introuvable par un bloqueur de `meta_path`.
    Si la TUI s'y importe et expose ses jetons, aucun toolkit n'est dans son
    graphe d'import -- et l'operateur d'une machine sans Qt a une interface.
    """
    resultat = subprocess.run([sys.executable, "-c", PROGRAMME_SANS_QT],
                              cwd=racine_depot, capture_output=True,
                              text=True, timeout=120)
    assert resultat.returncode == 0, resultat.stderr
    sortie = dict(ligne.split("=", 1)
                  for ligne in resultat.stdout.strip().splitlines())
    assert sortie["coque"] == "CoqueTui"
    assert sortie["jetons"] == "6"
    assert sortie["toolkits"] == "", (
        f"un toolkit Qt est entre dans le graphe : {sortie['toolkits']}")


def test_l_ecran_projet_se_monte_lui_aussi_sans_qt(racine_depot):
    """AC 6.3 et 6.4, volet TRANSITIF -- et c'est celui qui compte vraiment.

    Le test precedent monte la coque, qui ne touche pas a `gui.depot_projets`.
    Celui-ci importe le modele du palier 0, donc **tout le graphe** que la
    story 11.2 fait entrer : `gui.depot_projets`, `gui.modele_projets`, `io/`
    et `jsonschema`. Une garde AST sur les deux fichiers de `gui/` ne dirait
    rien de ce que ceux-ci importent a leur tour ; ici, un `import PySide6`
    ajoute a n'importe quel maillon fait tomber le processus fils.

    C'est la seule mesure de ce fichier qui parle du produit tel qu'il tourne :
    `mmu-tui` sur une session SSH sans X11, ou PySide6 peut ne pas etre
    installe du tout.
    """
    resultat = subprocess.run([sys.executable, "-c", PROGRAMME_SANS_QT_AVEC_PROJET],
                              cwd=racine_depot, capture_output=True,
                              text=True, timeout=120)
    assert resultat.returncode == 0, resultat.stderr
    sortie = dict(ligne.split("=", 1)
                  for ligne in resultat.stdout.strip().splitlines())
    assert sortie["coque"] == "CoqueTui"
    assert sortie["projets"] == "recents-v1.json"
    assert sortie["toolkits"] == "", (
        f"un toolkit Qt est entre dans le graphe : {sortie['toolkits']}")


def test_le_bloqueur_de_toolkit_bloque_vraiment(racine_depot):
    """Volet symetrique : sans lui, le test precedent serait vert sur une
    machine ou PySide6 n'est de toute facon pas installe -- ou pire, vert alors
    que le bloqueur ne bloquerait rien."""
    programme = PROGRAMME_SANS_QT.replace(
        "from mixed_media_utility.tui.coque import CoqueTui",
        "import PySide6.QtWidgets\nCoqueTui = PySide6.QtWidgets.QWidget")
    resultat = subprocess.run([sys.executable, "-c", programme],
                              cwd=racine_depot, capture_output=True,
                              text=True, timeout=120)
    assert resultat.returncode != 0
    assert "PySide6 indisponible (simule)" in resultat.stderr


# ---------------------------------------------------------------------------
# Un risque cree PAR cet epic : la TUI double la GUI ecran pour ecran, donc les
# noms de fichiers de test se percutent par construction.
# ---------------------------------------------------------------------------

def test_aucun_nom_de_FICHIER_de_test_n_est_en_double(racine_depot):
    """Sans `__init__.py`, deux `test_ecran_projet.py` dans deux dossiers
    donnent le **meme** nom de module : pytest interrompt la collecte de la
    suite ENTIERE.

    Le piege est que la panne ne se voit pas en lançant `tests/unit/tui` seul
    -- elle n'apparait qu'a la suite complete, c'est-a-dire tard et loin. Elle
    a coute une collecte le 2026-08-28. La convention du depot est le suffixe
    `_tui` (`test_jetons_tui.py` la porte deja).
    """
    from collections import Counter

    noms = Counter(chemin.name
                   for chemin in (racine_depot / "tests").rglob("test_*.py"))
    doublons = sorted(nom for nom, combien in noms.items() if combien > 1)
    assert doublons == [], doublons


def test_le_comptage_des_doublons_MORD(racine_depot, tmp_path):
    """Volet symetrique : un comptage a zero sur un balayage muet serait vert
    quoi qu'il arrive. Ici le meme calcul, sur un arbre qui porte le doublon,
    doit le nommer."""
    from collections import Counter

    for dossier in ("gui", "tui"):
        (tmp_path / dossier).mkdir()
        (tmp_path / dossier / "test_ecran_projet.py").write_text("", encoding="utf-8")
    noms = Counter(chemin.name for chemin in tmp_path.rglob("test_*.py"))
    assert sorted(nom for nom, combien in noms.items() if combien > 1) == \
        ["test_ecran_projet.py"]
