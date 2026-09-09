"""Selection des tests fondee sur ce qui est INSTALLE, jamais sur un chemin.

Motif, mesure le 2026-08-30 (story 8.4, AC 7). La CI lancait
`pytest tests/unit --ignore=tests/unit/gui`, en supposant que tout ce qui exige
une dependance optionnelle vit dans `tests/unit/gui/`. L'hypothese etait fausse
DANS LES DEUX SENS :

* 31 fichiers hors de `tests/unit/gui/` importaient `cv2` -- corrige a la
  racine par EPIC8-ARB-1, OpenCV etant desormais une dependance de base.

**Rectification de la revue (2026-08-31).** La premiere redaction de ce module
ajoutait un second grief : « quatre fichiers hors de `tests/unit/gui/` importent
PySide6 ». **C'etait faux, et les trois couches de revue l'ont trouve
independamment.** Les quatre fichiers en cause (`test_cadence_previz.py`,
`test_encode_previz.py`, `test_extraction_previz.py`, `test_scan_previz.py`) ne
font que CITER le nom `PySide6` en litteral de chaine, dans les listes d'imports
interdits de leurs propres frontieres -- ils interdisent a la previsualisation
d'importer un toolkit graphique. Ils sont collectes et passent sans Qt.

L'auteur avait lu un grep la ou il fallait un AST : le symetrique exact de
l'erreur qu'il venait de corriger deux heures plus tot sur la verification de
`ffmpeg-python`. Consequence a retenir : ce module ecarte AUJOURD'HUI exactement
le meme ensemble que l'ancien `--ignore`. Sa superiorite ne vient pas d'un
defaut qu'il corrigerait tout de suite, mais de ce qu'il ne repose plus sur une
hypothese de chemin -- et `tests/unit/test_selection_par_dependance.py` mesure
desormais ce module, pour qu'un tel constat ne puisse plus etre ecrit faux.

Un chemin ne dit pas ce dont un test a besoin. Ce conftest le DEDUIT des
imports du fichier, et ne l'ecarte que si la dependance manque reellement dans
l'environnement courant. Consequences voulues :

* poste de developpement avec l'extra `[gui]` installe : rien n'est ecarte,
  toute la suite tourne, y compris `tests/unit/gui/` ;
* CI du job `test`, sans l'extra : les seuls fichiers ecartes sont ceux qui ne
  PEUVENT pas s'importer, et le motif du saut est affiche ;
* aucun reglage a maintenir quand un test change de dossier ou qu'un nouveau
  fichier se met a importer Qt.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _chemins_bmad import DOSSIER as DOSSIER_DE_METHODE  # noqa: E402
from _chemins_bmad import chemins_joints  # noqa: E402

#: Modules dont l'absence rend un fichier de test non collectable, et la
#: distribution qui les fournit -- pour que le message nomme ce qu'il faut
#: installer plutot que de laisser lire une trace d'import.
MODULES_OPTIONNELS = {
    "PySide6": "mmu-tui[gui]",
    "pytestqt": "mmu-tui[gui]",
}

#: Fixtures fournies par un PLUGIN pytest optionnel, et le module qui les
#: apporte. Une dependance peut n'etre visible par AUCUN import : le conftest
#: de `tests/unit/gui/` n'importe ni PySide6 ni pytest-qt, il se contente de
#: nommer la fixture `qapp` en parametre. Chercher les imports ne suffit donc
#: pas -- il faut aussi reconnaitre l'usage de ces noms.
#: Releve exhaustif sur la roue `pytest-qt==4.4.0`. `qapp_cls` a ete ajoute par
#: la revue : c'est la SIXIEME, elle manquait, et c'est justement la voie
#: documentee pour fournir une sous-classe de `QApplication` -- donc celle
#: qu'un conftest Qt a une vraie raison d'employer. Les autres sont inertes sur
#: l'arbre d'aujourd'hui (seule `qapp` porte quelque chose) et restent la pour
#: le jour ou elles serviront.
FIXTURES_OPTIONNELLES = {
    "qapp": "pytestqt",
    "qapp_args": "pytestqt",
    "qapp_cls": "pytestqt",
    "qtbot": "pytestqt",
    "qtlog": "pytestqt",
    "qtmodeltester": "pytestqt",
}

#: Racine de l'arborescence de tests, borne de la remontee vers les conftest
#: parents. Sans elle, la remontee sortirait du depot.
RACINE_DES_TESTS = Path(__file__).resolve().parent


def _est_disponible(module: str) -> bool:
    """Vrai si `module` est importable dans l'environnement courant."""
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        # `find_spec` leve si un paquet parent est lui-meme absent ou casse :
        # dans les deux cas le module n'est pas utilisable.
        return False


def _modules_optionnels_requis(fichier: Path) -> set[str]:
    """Rend les modules optionnels qu'un fichier de test exige pour s'importer.

    Un test exige Qt s'il importe PySide6 ou pytest-qt directement, ou s'il
    importe un module de `mixed_media_utility.gui` -- lequel importe PySide6 au
    chargement. Cette derniere voie est INDIRECTE et se manquerait a ne
    chercher que `PySide6` dans le texte du fichier.
    """
    try:
        arbre = ast.parse(fichier.read_text(encoding="utf-8"), filename=str(fichier))
    except (SyntaxError, UnicodeDecodeError, OSError, FileNotFoundError):
        # Un fichier illisible n'est pas ecarte ici : c'est a pytest de le
        # signaler comme erreur de collecte, pas a ce filtre de le masquer.
        return set()

    requis: set[str] = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            noms = [alias.name for alias in noeud.names]
        elif isinstance(noeud, ast.ImportFrom):
            noms = [noeud.module] if noeud.module else []
        else:
            continue
        for nom in noms:
            racine = nom.split(".")[0]
            if racine in MODULES_OPTIONNELS:
                requis.add(racine)
            elif nom.startswith("mixed_media_utility.gui"):
                requis.add("PySide6")

    # Second releve : les fixtures de plugin, nommees en PARAMETRE de fonction
    # et invisibles a l'analyse des imports.
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        arguments = noeud.args
        parametres = [a.arg for a in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs)]
        for parametre in parametres:
            if parametre in FIXTURES_OPTIONNELLES:
                requis.add(FIXTURES_OPTIONNELLES[parametre])
    return requis


def _modules_optionnels_du_contexte(fichier: Path) -> set[str]:
    """Rend ce que les `conftest.py` du dossier et de ses parents exigent.

    Un fichier de test peut n'importer AUCUNE dependance optionnelle et rester
    inexecutable : `tests/unit/gui/conftest.py` declare une fixture autouse qui
    depend de `qapp` (pytest-qt). Sans pytest-qt, tout test de ce dossier
    echoue sur « fixture 'qapp' not found » -- y compris les tests de frontiere
    qui ne font que lire des fichiers source et n'importent jamais Qt.

    Mesure du 2026-08-30 : neuf tests de
    `tests/unit/gui/test_frontieres_ecran_projet.py` tombaient ainsi. Le
    besoin se HERITE du dossier ; le deduire du seul fichier ne suffit pas.
    """
    requis: set[str] = set()
    dossier = fichier.parent
    while True:
        conftest = dossier / "conftest.py"
        if conftest.is_file() and conftest != Path(__file__):
            requis |= _modules_optionnels_requis(conftest)
        if dossier == RACINE_DES_TESTS or dossier == dossier.parent:
            break
        dossier = dossier.parent
    return requis


RACINE_DU_DEPOT = RACINE_DES_TESTS.parent


def _archives_absentes(fichier: Path) -> list[str]:
    """Les chemins de `_bmad-output/` que ce banc construit et qui MANQUENT.

    **Le regime que ceci ferme, et il n'existe que sur le depot PUBLIC.**
    `EPIC11-ARB-268` laisse l'archive de travail hors de l'orphelin, a trois
    chemins pres. Quatre bancs de TRACABILITE lisent pourtant des documents qui
    restent prives -- une fiche de story, deux dossiers d'arbitrage, une note de
    liaison. Sur le public, ces quatre-la echouent A LA COLLECTE, et le
    `pytest tests/unit -x -q` de `ci.yml` s'arrete au premier : la porte
    `valider` de la release devient infranchissable pour une raison qui n'est
    pas un defaut du produit.

    **Pourquoi ici et non par un drapeau de CI.** Une liste de `--ignore` dans
    `ci.yml` derive des qu'un banc neuf lit un cinquieme document, et rien ne le
    dirait -- la CI publique n'existe pas encore pour rougir. Ici, la regle est
    la MEME que celle du reste de ce module : on ecarte ce qui ne PEUT pas
    tourner, et on nomme pourquoi. Elle ne fait rien sur le depot de travail,
    ou les fichiers existent : c'est ce que
    `tests/unit/test_perimetre_public.py` mesure.

    **Le tri « lit » contre « nomme pour interdire » se fait sur la FORME**, et
    il a ete paye : la premiere redaction ecartait
    `test_politiques_du_depot.py`, dont la frontiere NOMME l'ancien chemin
    d'`ARCHITECTURE_DETAILED.md` pour le REFUSER. Ecarter ce banc-la aurait
    retire du public la garde qui empeche un chemin perime de revenir --
    l'inverse exact du but. :func:`chemins_joints` ne rend donc que les chemins
    bati par une chaine de `/`, ce qui separe les cinq bancs sans une exception
    nommee ; la mesure est dans son docstring.

    Second garde-fou : un ANCETRE du chemin doit exister. Sinon `_bmad-output/`
    n'est pas livre du tout et le banc a d'autres raisons de tomber, qu'on ne
    masque pas.
    """
    try:
        source = fichier.read_text(encoding="utf-8")
    except OSError:                              # pragma: no cover - defensif
        return []
    # **Le garde-fou porte sur la RACINE de l'archive, pas sur le parent du
    # chemin**, et la nuance a ete trouvee par le banc plutot que par la
    # relecture. Un banc bati `_RACINE / "_bmad-output" / ...` : sur un arbre
    # ou `_bmad-output/` n'existe pas du tout, le parent de ce premier segment
    # est la racine du depot, qui existe toujours -- la garde passait et
    # l'ecart se declenchait. Or ce cas-la (sdist, clone partiel, arbre casse)
    # n'est pas le regime public : le banc a d'autres raisons de tomber, et un
    # saut silencieux les masquerait toutes. C'est le pire des faux verts.
    if not (RACINE_DU_DEPOT / DOSSIER_DE_METHODE).is_dir():
        return []
    absents = []
    for chemin in sorted(chemins_joints(source)):
        cible = RACINE_DU_DEPOT / chemin
        if cible.exists():
            continue
        absents.append(chemin)
    return absents


def pytest_ignore_collect(collection_path: Path, config) -> bool | None:
    """Ecarte un fichier de test dont une dependance optionnelle manque.

    `pytest_ignore_collect` et non `pytest_collection_modifyitems` : l'echec
    survient a l'IMPORT du module de test ou a la resolution de ses fixtures,
    donc pendant la collecte. Un filtre pose apres s'executerait trop tard.
    """
    # Un REPERTOIRE d'abord : pytest charge le `conftest.py` d'un dossier AVANT
    # d'appeler ce hook sur les fichiers qu'il contient. Si ce conftest importe
    # lui-meme la dependance absente, la collecte ENTIERE tombe -- y compris des
    # fichiers sans aucun rapport, ailleurs dans l'arbre. Ecarter le dossier en
    # amont est le seul moment ou l'on peut encore l'eviter.
    if collection_path.is_dir():
        requis = _modules_optionnels_requis(collection_path / "conftest.py")
        if any(not _est_disponible(module) for module in requis):
            print(f"\n[conftest] dossier {collection_path.name}/ ecarte : son conftest.py exige une dependance absente.")
            return True
        return None

    # Les DEUX conventions par defaut de pytest (`python_files`), et non la
    # seule `test_*.py` : aucun `python_files` n'est configure dans ce depot,
    # donc `*_test.py` est collecte aussi. Un fichier de cette forme echappait
    # au filtre et, avec le `-x` de la CI, arretait le job.
    if collection_path.suffix != ".py":
        return None
    nom = collection_path.name
    if not (nom.startswith("test_") or nom.endswith("_test.py")):
        return None

    requis = _modules_optionnels_requis(collection_path)
    requis |= _modules_optionnels_du_contexte(collection_path)
    manquants = {module for module in requis if not _est_disponible(module)}
    if not manquants:
        absentes = _archives_absentes(collection_path)
        if absentes:
            print(
                f"\n[conftest] {collection_path.name} ecarte : il lit "
                f"{', '.join(absentes)}, que ce depot ne porte pas "
                "(`EPIC11-ARB-268`, archive de travail restee privee)."
            )
            return True
        return None

    distributions = sorted({MODULES_OPTIONNELS[m] for m in manquants})
    print(
        f"\n[conftest] {collection_path.name} ecarte : "
        f"{', '.join(sorted(manquants))} absent(s). "
        f"Installer {' '.join(distributions)} pour l'executer."
    )
    return True
