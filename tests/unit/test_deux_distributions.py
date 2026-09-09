"""Frontiere des DEUX distributions : `mmu-cli` porte le coeur, `mmu-tui` en depend.

Story 8.5 (`EPIC8-ARB-5`, `-6`, `-10`, Egan le 2026-09-07, verbatim : « sur la
premiere release j'aimerais qu'on distribue la cli et la tui. Mais en deux
paquets distincts [...] Il ne faut pas installer les memes choses deux fois si
des choses se recoupent. »).

**Ce que ce banc mesure, et pourquoi une frontiere plutot qu'une relecture.**
La scission repose sur trois accords qu'AUCUN outil ne verifie tout seul :

* les deux roues ne doivent porter **aucun fichier commun** -- c'est le seul
  enonce qui mesure vraiment « non redondant ». Un compteur de taille ne le
  dirait pas : deux roues de 12 Mo peuvent etre la meme roue ;
* **trois** litteraux de version doivent s'accorder -- celui de `mmu-cli`,
  celui de `mmu-tui`, et l'epinglage `mmu-cli==X` que `mmu-tui` porte. Trois
  litteraux qui doivent s'accorder sans que rien ne les compare, c'est la
  definition d'une derive ;
* le sens de l'arc `mmu-tui -> mmu-cli` doit rester unique. C'est lui qui rend
  la CLI installable SEULE ; une dependance en retour la rendrait impossible.

**Pourquoi la moitie « roue » construit reellement.** Recalculer depuis les
`pyproject.toml` ce que hatchling MET dans une roue, c'est reecrire hatchling
-- et un banc qui reimplemente ce qu'il mesure est vert par construction. Les
roues sont donc construites par le crochet PEP 517 du backend
(`hatchling.build.build_wheel`, 0,2 s piece, mesure du 2026-09-07), puis
ouvertes.

**Ce que ce banc NE mesure pas, dit plutot que tu.** Il ne joue pas
l'installation : `pip install` des deux roues dans un venv neuf demande le
reseau et trois minutes, ce qui n'a pas sa place dans la suite unitaire. Elle a
ete jouee A LA MAIN le 2026-09-07 et ses chiffres sont dans le message du
commit de la story : les deux ensemble 333 Mo avec UN exemplaire de
`io/naming.py`, `mmu --help` et `mmu-tui --help` a EXIT=0 ; `mmu-cli` seule
305 Mo, sans textual ni rich. Ce qui EST mesure ici de ce chemin-la, c'est le
`entry_points.txt` de chaque roue -- la declaration que pip lit pour poser la
commande sur le PATH.

--------------------------------------------------------------------------
MUTATIONS JOUEES, et leur verdict (2026-09-07). Une frontiere qu'on n'a pas
vue rougir n'est pas mesuree.

  M1  `exclude` de la roue mmu-cli retire            -> ROUGE (3 tests)
  M2  `mmu-cli==0.1.0` -> `mmu-cli>=0.1.0`           -> ROUGE
  M3  `__version__ = "0.1.0"` -> `"0.2.0"`           -> ROUGE (2 tests)
  M4  `textual>=8.2,<9` remis dans mmu-cli           -> ROUGE
  M5  `mmu-tui` ajoute a l'extra [gui] de mmu-cli    -> ROUGE
  M6  script `mmu` -> `mmu-cli` dans la racine       -> ROUGE
  M7  `_communs` rend `[]`                           -> ROUGE (echantillon)
  M8  `_communs` rend le PREMIER commun seulement    -> ROUGE (echantillon)
  M9  `_versions_desaccordees` rend `[]`             -> ROUGE (echantillon)
  M10 `_charge_utile` rend tout, dist-info compris   -> ROUGE (echantillon)
  M11 `hatchling` retire de l'extra [test]           -> ROUGE
  M12 force-include de mmu-tui reprend tout `src/`   -> ROUGE (2 tests)
  M13 `exclude` du bytecode retire de mmu-tui        -> SURVIVANT, et la LIGNE
      a ete retiree plutot que le mutant ecarte : hatchling exclut le bytecode
      lui-meme (`builders/constants.py`, `builders/config.py:816`), la ligne
      ne tenait rien. Le banc, lui, mesure le resultat et reste.
  M14 `license-files = ["../../LICENSE"]`            -> ROUGE
  M15 un lien symbolique remis sous `packaging/`     -> ROUGE (2 tests)
  M16 `packaging/mmu-tui/LICENSE` ampute d'une ligne -> ROUGE
  M17 la sdist force-include les sources             -> ROUGE
--------------------------------------------------------------------------
"""

from __future__ import annotations

import ast
import importlib.util
import os
import re
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
PYPROJECT_CLI = RACINE / "pyproject.toml"
PYPROJECT_TUI = RACINE / "packaging" / "mmu-tui" / "pyproject.toml"
SOURCE_DE_VERSION = RACINE / "src" / "mixed_media_utility" / "__init__.py"

#: Les deux distributions du depot, par leur nom PyPI normalise. `mmu` etant
#: PRIS sur PyPI depuis 2022 (ModelMetricUncertainty), la distribution
#: s'appelle `mmu-cli` et la COMMANDE reste `mmu` (`EPIC8-ARB-6`).
NOM_CLI = "mmu-cli"
NOM_TUI = "mmu-tui"

#: Le prefixe de la charge utile : ce que les deux roues installent dans
#: `site-packages`, par opposition aux metadonnees.
PAQUET = "mixed_media_utility"


# --------------------------------------------------------------------------
# Lecture des deux declarations.
# --------------------------------------------------------------------------


def _declaration(chemin: Path) -> dict:
    """La table `[project]` d'un `pyproject.toml`."""
    return tomllib.loads(chemin.read_text(encoding="utf-8"))["project"]


def _nom_normalise(specification: str) -> str:
    """`PySide6-Essentials>=6.8,<6.9` -> `pyside6-essentials` (PEP 503)."""
    nom = re.split(r"[<>=!~\[;@ ]", specification.strip(), maxsplit=1)[0]
    return nom.strip().lower().replace("_", "-").replace(".", "-")


def _paquets_declares(projet: dict, avec_extras: bool) -> set[str]:
    """Les noms declares par une distribution, extras compris ou non."""
    listes = [projet.get("dependencies", [])]
    if avec_extras:
        listes += list(projet.get("optional-dependencies", {}).values())
    return {_nom_normalise(d) for liste in listes for d in liste}


def _version_de_la_source() -> str:
    """`__version__` lu dans `src/mixed_media_utility/__init__.py`.

    Lu par AST plutot qu'importe : importer le paquet tirerait `cv2`, numpy et
    le reste, ce qui ferait dependre une frontiere de packaging de
    l'installation qu'elle decrit.
    """
    arbre = ast.parse(SOURCE_DE_VERSION.read_text(encoding="utf-8"))
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Assign):
            for cible in noeud.targets:
                if isinstance(cible, ast.Name) and cible.id == "__version__":
                    return ast.literal_eval(noeud.value)
    raise AssertionError(
        f"{SOURCE_DE_VERSION} ne porte plus `__version__` : la source UNIQUE "
        "de version des deux distributions a disparu (EPIC8-ARB-10)")


def _epinglage_de_mmu_cli() -> str:
    """La borne que `mmu-tui` pose sur `mmu-cli` (`mmu-cli==0.1.0` -> `==0.1.0`)."""
    for specification in _declaration(PYPROJECT_TUI)["dependencies"]:
        if _nom_normalise(specification) == NOM_CLI:
            return specification[len(NOM_CLI):].strip()
    raise AssertionError(
        "`mmu-tui` ne depend plus de `mmu-cli` : l'arc qui porte toute la "
        "deduplication a disparu")


# --------------------------------------------------------------------------
# La LOGIQUE d'accusation, isolee en fonctions pures.
#
# Motif, deja paye deux fois dans ce depot (bancs du contrat de dependances,
# 2026-08-30) : sur un arbre CORRECT l'ensemble des fautifs est vide de toute
# facon, donc `assert not fautifs` passe que le detecteur fonctionne ou non.
# Ces fonctions sont exercees DEUX fois -- sur les roues reelles (zero fautif
# exige) et sur des echantillons de synthese (le fautif doit etre trouve).
# --------------------------------------------------------------------------


def _charge_utile(noms: set[str]) -> set[str]:
    """Les entrees d'une roue hors metadonnees (`*.dist-info/**`).

    La distinction compte : deux roues ne peuvent JAMAIS partager une entree de
    `dist-info`, dont le nom porte celui de la distribution. Comparer les
    listes brutes rendrait donc une intersection vide meme si les deux roues
    livraient le meme paquet -- vert par construction.
    """
    return {nom for nom in noms if ".dist-info/" not in nom}


def _communs(noms_cli: set[str], noms_tui: set[str]) -> list[str]:
    """Les fichiers livres par les DEUX roues."""
    return sorted(_charge_utile(noms_cli) & _charge_utile(noms_tui))


def _versions_desaccordees(
    source: str, version_cli: str, version_tui: str, epinglage: str
) -> list[str]:
    """Les ecarts entre les quatre expressions d'une seule et meme version.

    Rend une liste de motifs plutot qu'un booleen : quand deux des quatre
    derivent, on veut savoir LESQUELLES sans relancer le banc.
    """
    ecarts: list[str] = []
    if version_cli != source:
        ecarts.append(f"mmu-cli={version_cli} contre __version__={source}")
    if version_tui != source:
        ecarts.append(f"mmu-tui={version_tui} contre __version__={source}")
    if epinglage != f"=={source}":
        ecarts.append(
            f"mmu-tui epingle `mmu-cli{epinglage}` contre __version__={source}")
    return ecarts


# --------------------------------------------------------------------------
# AC 1 et AC 2 -- ce que les deux declarations disent.
# Ces volets ne construisent rien : ils tiennent meme sans backend.
# --------------------------------------------------------------------------


def test_la_racine_declare_mmu_cli_et_la_commande_mmu():
    """AC 1. Le nom de DISTRIBUTION et le nom de COMMANDE sont dissocies.

    `mmu` est pris sur PyPI depuis 2022 ; rien n'oblige un nom de distribution
    a egaler le nom de sa commande, et c'est la commande qu'Egan tape.
    """
    projet = _declaration(PYPROJECT_CLI)
    assert projet["name"] == NOM_CLI
    assert projet["scripts"] == {"mmu": "mixed_media_utility.cli:main"}, (
        "la commande posee par `mmu-cli` doit rester `mmu`, et elle seule -- "
        "`mmu-tui` est pose par l'AUTRE distribution")


def test_mmu_tui_declare_EXACTEMENT_ses_trois_dependances():
    """AC 2. Ni plus -- une quatrieme retomberait dans `mmu-cli` -- ni moins.

    L'egalite est exigee sur l'ensemble ENTIER et non sur des appartenances :
    trois `assert x in deps` laisseraient entrer une quatrieme dependance sans
    un mot, ce qui est exactement la derive que la scission existe pour eviter.
    """
    projet = _declaration(PYPROJECT_TUI)
    assert projet["name"] == NOM_TUI
    assert projet["dependencies"] == [
        f"{NOM_CLI}=={_version_de_la_source()}",
        "textual>=8.2,<9",
        "rich>=14.2",
    ], projet["dependencies"]
    assert projet["scripts"] == {
        "mmu-tui": "mixed_media_utility.tui.__main__:main"}


@pytest.mark.parametrize("module, fonction, distribution", [
    pytest.param("cli.py", "main", NOM_CLI, id="mmu -> cli:main"),
    pytest.param("tui/__main__.py", "main", NOM_TUI, id="mmu-tui -> tui.__main__:main"),
])
def test_le_point_d_entree_de_chaque_roue_EXISTE_reellement(
    module: str, fonction: str, distribution: str
) -> None:
    """Les deux cibles de `[project.scripts]`, mesurees dans le code.

    Une chaine de `[project.scripts]` n'est verifiee par personne a la
    construction : un module renomme rend une roue qui s'installe, pose la
    commande, et echoue au PREMIER lancement par `ModuleNotFoundError`. C'est
    la panne la plus tardive possible -- chez l'utilisateur.
    """
    chemin = RACINE / "src" / PAQUET / module
    assert chemin.is_file(), f"{chemin} : cible de `{distribution}` absente"
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    noms = {n.name for n in arbre.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert fonction in noms, (
        f"{module} ne definit plus `{fonction}` au premier niveau : la "
        f"commande de `{distribution}` pointerait dans le vide")


def test_l_outillage_de_developpement_reste_sur_la_racine():
    """AC 1, seconde moitie. C'est le fichier que lisent les frontieres.

    Le deplacer ferait rougir cinq bancs pour rien : `[tool.mutmut]` est le
    SEUL point de configuration lu par mutmut 3.x, et les extras `dev`, `test`
    et `gui` sont ce qu'installe un poste de developpement.
    """
    donnees = tomllib.loads(PYPROJECT_CLI.read_text(encoding="utf-8"))
    assert "mutmut" in donnees["tool"], (
        "[tool.mutmut] a quitte la racine : les campagnes de mutation ne "
        "trouvent plus leur configuration (scripts/mutation/README.md)")
    extras = set(donnees["project"]["optional-dependencies"])
    assert {"gui", "dev", "test", "full"} <= extras, sorted(extras)


# --------------------------------------------------------------------------
# AC 7 -- les frontieres NEGATIVES, celles qui attrapent une REINTRODUCTION.
# Aucun test positif ne verrait revenir `textual` dans `mmu-cli`.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("paquet", [
    pytest.param("textual", id="textual"),
    pytest.param("rich", id="rich"),
])
def test_les_paquets_du_seul_chemin_TUI_ne_reviennent_pas_dans_mmu_cli(paquet: str) -> None:
    """AC 7. Les mesurer aussi dans les EXTRAS, pas seulement dans la base.

    Une reintroduction ne se fait pas forcement en base : c'est meme dans un
    extra que `opencv` avait ete mal range le 2026-08-30, et il a fallu une
    frontiere pour le voir. Un `pip install mmu-cli[full]` qui tirerait
    textual paierait les 28 Mo que la scission existe pour ne pas payer.
    """
    projet = _declaration(PYPROJECT_CLI)
    assert paquet not in _paquets_declares(projet, avec_extras=True), (
        f"`{paquet}` est declare par `mmu-cli` : il n'est importe que sous "
        "src/mixed_media_utility/tui/, qui n'est pas dans cette roue")


def test_mmu_cli_ne_depend_JAMAIS_de_mmu_tui():
    """AC 7. Le SENS de l'arc est ce qui rend la CLI installable seule.

    Un arc en retour -- meme dans un extra, meme « pour la commodite » --
    ferait tirer textual, rich et 28 Mo a qui n'a demande que `mmu`, et
    fabriquerait un cycle de dependance entre deux paquets publies.
    """
    declares = _paquets_declares(_declaration(PYPROJECT_CLI), avec_extras=True)
    assert NOM_TUI not in declares, (
        "`mmu-cli` declare `mmu-tui` : l'arc s'est inverse, et la CLI n'est "
        "plus installable seule")


def test_l_extra_gui_reste_sur_mmu_cli_et_mmu_tui_n_a_AUCUN_extra():
    """AC 7. `gui/` voyage avec `mmu-cli`, dont `mmu-tui` depend.

    Les cinq arcs `tui -> gui` sont donc satisfaits sans deplacer un module, et
    sans troisieme paquet. Le volet symetrique -- `mmu-tui` sans extra -- dit
    qu'aucune option ne s'est glissee du mauvais cote de la scission.
    """
    assert "gui" in _declaration(PYPROJECT_CLI)["optional-dependencies"]
    assert not _declaration(PYPROJECT_TUI).get("optional-dependencies"), (
        "`mmu-tui` s'est mis a porter des extras : tout ce qui est optionnel "
        "vit sur `mmu-cli`, dont elle depend")


# --------------------------------------------------------------------------
# AC 4 -- UNE seule source de version, et un detecteur qui accuse.
# --------------------------------------------------------------------------


def test_les_deux_pyproject_LISENT_la_version_au_lieu_de_la_recopier():
    """AC 4. `dynamic = ["version"]` des deux cotes, meme fichier source.

    Sans ce volet, les deux fichiers pourraient revenir a un `version = "..."`
    litteral et s'accorder par hasard le jour de la mesure.
    """
    for chemin, remontee in ((PYPROJECT_CLI, ""), (PYPROJECT_TUI, "../../")):
        donnees = tomllib.loads(chemin.read_text(encoding="utf-8"))
        assert donnees["project"].get("dynamic") == ["version"], chemin
        assert "version" not in donnees["project"], (
            f"{chemin} porte encore un litteral de version")
        assert donnees["tool"]["hatch"]["version"]["path"] == (
            f"{remontee}src/mixed_media_utility/__init__.py"), chemin


def test_l_epinglage_de_mmu_cli_est_STRICT_et_suit_la_source():
    """AC 4. `mmu-cli==<version>`, jamais une borne large.

    Les deux roues sont deux moities d'un meme arbre : `tui/` importe le coeur
    par des chemins internes (`mixed_media_utility.io.naming`, ...) qui ne
    portent aucune garantie de compatibilite entre versions. Une borne `>=`
    ferait entrer une combinaison que personne n'a jouee.
    """
    assert _epinglage_de_mmu_cli() == f"=={_version_de_la_source()}"


def test_le_detecteur_de_desaccord_de_version_accuse_bien_le_bon_ecart():
    """Auto-verification : sur un arbre accorde, ce detecteur ne peut pas rougir.

    Regle des fabriques : QUATRE valeurs distinguables, et la fautive n'est
    jamais en premiere position -- un detecteur qui ne comparerait que la
    premiere paire passerait un echantillon plus pauvre.
    """
    # Rien a signaler quand les quatre s'accordent.
    assert _versions_desaccordees("1.2.3", "1.2.3", "1.2.3", "==1.2.3") == []

    # La roue TUI derive, seule : une accusation, la bonne.
    ecarts = _versions_desaccordees("1.2.3", "1.2.3", "1.3.0", "==1.2.3")
    assert len(ecarts) == 1 and "mmu-tui=1.3.0" in ecarts[0], ecarts

    # L'epinglage derive, seul -- le cas le plus insidieux : les deux roues
    # portent la meme version, et l'installation tire quand meme l'autre.
    ecarts = _versions_desaccordees("1.2.3", "1.2.3", "1.2.3", "==1.2.2")
    assert len(ecarts) == 1 and "epingle" in ecarts[0], ecarts

    # Une borne LARGE n'est pas un accord : `>=1.2.3` laisse entrer 2.0.
    assert _versions_desaccordees("1.2.3", "1.2.3", "1.2.3", ">=1.2.3")

    # DEUX ecarts a la fois : un detecteur qui rendrait `[:1]` se trahit ici.
    ecarts = _versions_desaccordees("1.2.3", "9.9.9", "1.2.3", "==0.0.1")
    assert len(ecarts) == 2, ecarts


# --------------------------------------------------------------------------
# AC 3 et AC 8 -- ce que les roues CONSTRUITES contiennent reellement.
#
# Le backend est appele par son crochet PEP 517 (`hatchling.build.build_wheel`)
# plutot que par `python -m build` : `build` n'est pas une dependance du depot,
# hatchling l'est deja -- `[build-system].requires` le declare.
# --------------------------------------------------------------------------


def _sait_construire(interpreteur: str) -> bool:
    """Vrai si cet interprete importe hatchling."""
    if interpreteur == sys.executable:
        return importlib.util.find_spec("hatchling") is not None
    resultat = subprocess.run(
        [interpreteur, "-c", "import hatchling"],
        capture_output=True, check=False)
    return resultat.returncode == 0


def _interpreteur_de_construction() -> str | None:
    """L'interprete qui sait construire les roues, ou `None`.

    Deux sources, dans cet ordre : l'interprete courant (le cas normal -- le
    depot declare `hatchling` dans ses extras `dev` et `test`), puis celui que
    `MMU_INTERPRETEUR_DE_CONSTRUCTION` designe. La seconde existe pour les
    conteneurs dont le python systeme refuse d'installer hatchling : celui-ci
    exige `packaging>=24.2` et Debian tient `packaging` 24.0 sans `RECORD`, si
    bien que `pip install hatchling` y echoue a la desinstallation.
    """
    if _sait_construire(sys.executable):
        return sys.executable
    designe = os.environ.get("MMU_INTERPRETEUR_DE_CONSTRUCTION", "").strip()
    if designe and Path(designe).exists() and _sait_construire(designe):
        return designe
    return None


CROCHET_PEP_517 = """
import sys
from hatchling.build import build_wheel
sys.stdout.write(build_wheel(sys.argv[1]))
"""


def _construire(racine_du_backend: Path, sortie: Path, interpreteur: str) -> Path:
    """Construit la roue de `racine_du_backend` dans `sortie`, et la rend."""
    resultat = subprocess.run(
        [interpreteur, "-c", CROCHET_PEP_517, str(sortie)],
        cwd=racine_du_backend, capture_output=True, text=True, check=False)
    assert resultat.returncode == 0, (
        f"la construction de {racine_du_backend} a echoue :\n{resultat.stderr}")
    roue = sortie / resultat.stdout.strip()
    assert roue.is_file(), f"roue annoncee et absente : {roue}"
    return roue


@pytest.fixture(scope="module")
def roues(tmp_path_factory) -> dict[str, zipfile.ZipFile]:
    """Les deux roues, construites une fois pour le module.

    **Le saut est STRUCTUREL, jamais un drapeau qu'on oublie de rallumer** : il
    ne se declenche que si aucun interprete de la machine ne sait construire, et
    `test_hatchling_est_DECLARE_pour_que_ce_saut_ne_pourrisse_pas` ci-dessous
    mesure que la declaration qui l'evite est toujours la.
    """
    interpreteur = _interpreteur_de_construction()
    if interpreteur is None:
        pytest.skip(
            "aucun interprete ne sait importer hatchling. Remede : "
            "`pip install -e .[test]` (le depot le declare), ou poser "
            "MMU_INTERPRETEUR_DE_CONSTRUCTION sur un python qui l'a.")
    sortie = tmp_path_factory.mktemp("roues")
    return {
        NOM_CLI: zipfile.ZipFile(_construire(RACINE, sortie, interpreteur)),
        NOM_TUI: zipfile.ZipFile(
            _construire(PYPROJECT_TUI.parent, sortie, interpreteur)),
    }


def test_hatchling_est_DECLARE_pour_que_ce_saut_ne_pourrisse_pas():
    """Le volet qui empeche la moitie « roue » de ce banc de devenir inerte.

    Un saut conditionnel qui saute PARTOUT est un banc mort qui s'annonce vert.
    Celui-ci ne peut plus le devenir en silence : le jour ou `hatchling` quitte
    les extras du depot, c'est ce test-ci qui rougit -- pas un saut muet.

    Il ne se joue pas non plus tout seul : `hatchling` est deja
    `[build-system].requires`, donc ce n'est pas une dependance neuve du
    produit, c'est la meme, declaree la ou un poste de developpement la lit.
    """
    donnees = tomllib.loads(PYPROJECT_CLI.read_text(encoding="utf-8"))
    assert any(_nom_normalise(d) == "hatchling"
               for d in donnees["build-system"]["requires"])
    extras = donnees["project"]["optional-dependencies"]
    for nom in ("dev", "test", "full"):
        assert any(_nom_normalise(d) == "hatchling" for d in extras[nom]), (
            f"`hatchling` a quitte l'extra [{nom}] : la moitie « roue » de "
            "test_deux_distributions.py sauterait desormais en silence")


def test_les_deux_roues_ne_livrent_AUCUN_fichier_en_commun(roues):
    """AC 3. Le seul enonce qui mesure vraiment « non redondant ».

    Mesure du 2026-09-07 : `mmu-cli` 87 fichiers de charge utile, `mmu-tui` 52,
    intersection VIDE. Les cardinaux ne sont pas asserts -- ils bougent a chaque
    module ajoute, et un banc qu'on reajuste a chaque commit cesse d'etre lu.
    """
    noms_cli = set(roues[NOM_CLI].namelist())
    noms_tui = set(roues[NOM_TUI].namelist())

    communs = _communs(noms_cli, noms_tui)

    assert not communs, (
        "fichiers livres par les DEUX roues -- l'utilisateur qui installe les "
        "deux les telecharge et les stocke deux fois :\n  "
        + "\n  ".join(communs))
    # Le volet « vert a vide » : deux roues VIDES n'ont rien en commun non
    # plus. Sans ces deux gardes, un `exclude` trop large passerait.
    assert _charge_utile(noms_cli), "la roue mmu-cli ne livre aucun module"
    assert _charge_utile(noms_tui), "la roue mmu-tui ne livre aucun module"


def test_la_roue_mmu_cli_ne_porte_AUCUN_chemin_tui(roues):
    """AC 7. La frontiere negative que le volet precedent ne donne pas.

    Une roue `mmu-cli` qui reprendrait `tui/` ferait rougir le volet ci-dessus
    -- mais seulement tant que `mmu-tui` existe. Celui-ci mord meme seul, et il
    nomme le defaut au lieu de le deduire.
    """
    fautifs = sorted(n for n in roues[NOM_CLI].namelist()
                     if n.startswith(f"{PAQUET}/tui/"))
    assert not fautifs, (
        f"la roue mmu-cli porte {len(fautifs)} chemins tui/ : l'exclusion de "
        "`[tool.hatch.build.targets.wheel]` ne joue plus")
    # Symetrique : `gui/` voyage bien avec `mmu-cli`, sinon les cinq arcs
    # `tui -> gui` seraient casses a l'execution.
    assert any(n.startswith(f"{PAQUET}/gui/") for n in roues[NOM_CLI].namelist())


def test_la_roue_mmu_tui_ne_porte_QUE_le_sous_arbre_tui(roues):
    """AC 2. Le symetrique du precedent, sur l'autre moitie de la scission."""
    hors_zone = sorted(n for n in _charge_utile(set(roues[NOM_TUI].namelist()))
                       if not n.startswith(f"{PAQUET}/tui/"))
    assert not hors_zone, (
        "la roue mmu-tui porte des fichiers hors de tui/ -- ils seraient "
        f"livres deux fois : {hors_zone}")


def test_aucune_des_deux_roues_n_embarque_de_bytecode(roues):
    """Le `__pycache__` d'un arbre de travail rend la roue non reproductible.

    Les `.pyc` portent un horodatage : deux constructions du meme commit
    rendraient deux roues differentes.

    **Ce banc ne garde AUCUNE ligne de configuration, et c'est mesure.** La
    campagne du 2026-09-07 a retire l'`exclude` que `packaging/mmu-tui` portait
    pour ce motif : les 23 bancs sont restes verts alors que
    `src/mixed_media_utility/tui/__pycache__/` existe. Hatchling exclut le
    bytecode lui-meme (`builders/constants.py`, `builders/config.py:816`), donc
    la ligne etait morte -- elle a ete retiree. Ce test garde sa raison d'etre
    entiere : il mesure le RESULTAT, pas le reglage, et il rougirait le jour ou
    un backend changerait d'avis.
    """
    for nom, roue in roues.items():
        fautifs = [n for n in roue.namelist()
                   if n.endswith(".pyc") or "__pycache__" in n]
        assert not fautifs, f"{nom} embarque du bytecode : {fautifs[:5]}"


def test_les_QUATRE_expressions_de_la_version_s_accordent(roues):
    """AC 4, sur les roues CONSTRUITES et non sur les seules declarations.

    C'est la difference qui compte : `[tool.hatch.version]` peut pointer sur un
    fichier qui existe et n'y rien lire. Les versions comparees ici sont celles
    que pip lira.
    """
    def _version(roue: zipfile.ZipFile) -> str:
        metadonnees = next(n for n in roue.namelist() if n.endswith("METADATA"))
        texte = roue.read(metadonnees).decode("utf-8")
        return re.search(r"^Version: (.+)$", texte, re.MULTILINE).group(1).strip()

    ecarts = _versions_desaccordees(
        _version_de_la_source(),
        _version(roues[NOM_CLI]),
        _version(roues[NOM_TUI]),
        _epinglage_de_mmu_cli(),
    )

    assert not ecarts, (
        "les expressions de la version ont derive (EPIC8-ARB-10) :\n  "
        + "\n  ".join(ecarts))


def test_chaque_roue_declare_la_commande_que_pip_posera(roues):
    """AC 8, moitie mesurable en unitaire : le `entry_points.txt` de la roue.

    C'est ce fichier que pip lit pour ecrire le script sur le PATH. Le mesurer
    sur la roue plutot que sur le `pyproject.toml` attrape le cas ou le backend
    ne l'aurait pas ecrit du tout.
    """
    attendus = {
        NOM_CLI: "mmu = mixed_media_utility.cli:main",
        NOM_TUI: "mmu-tui = mixed_media_utility.tui.__main__:main",
    }
    for nom, roue in roues.items():
        chemin = next((n for n in roue.namelist()
                       if n.endswith("entry_points.txt")), None)
        assert chemin, f"{nom} ne declare aucun point d'entree"
        texte = roue.read(chemin).decode("utf-8")
        assert attendus[nom] in texte, f"{nom} : {texte!r}"


def test_les_deux_roues_embarquent_le_TEXTE_de_la_licence(roues):
    """Le paquet est sous GPL-3.0-or-later : le texte voyage avec lui.

    Et il voyage sous un chemin PROPRE. Mesure du 2026-09-07 :
    `license-files = ["../../LICENSE"]` construit sans broncher et rend une
    entree `mmu_tui-0.1.0.dist-info/licenses/../../LICENSE`, qui REMONTE hors
    du `dist-info` a l'installation. La sortie est un lien symbolique
    `packaging/mmu-tui/LICENSE`, que hatchling suit.
    """
    for nom, roue in roues.items():
        licences = [n for n in roue.namelist() if "/licenses/" in n]
        assert licences, f"{nom} ne porte aucun fichier de licence"
        for chemin in licences:
            assert ".." not in chemin.split("/"), (
                f"{nom} porte un chemin de licence qui REMONTE : {chemin}")
        texte = next(roue.read(n).decode("utf-8", "replace")
                     for n in licences if n.endswith("LICENSE"))
        assert "GNU GENERAL PUBLIC LICENSE" in texte.upper(), (
            f"{nom} embarque un LICENSE qui n'est pas la GPL")


def test_aucun_LIEN_SYMBOLIQUE_ne_revient_sous_packaging():
    """Frontiere NEGATIVE, et elle ferme un piege reellement construit.

    `packaging/mmu-tui/` a porte, le 2026-09-07, trois liens symboliques vers
    les fichiers de la racine (`LICENSE`, `THIRD-PARTY-NOTICES.md`,
    `README.md`). La ROUE etait correcte -- hatchling suit le lien et embarque
    le vrai texte --, et c'est ce qui rendait le defaut invisible : la
    distribution SOURCE, elle, garde les liens tels quels, PENDANTS, et
    `pip install` sur cette sdist echoue par `LinkOutsideDestinationError`.

    Un lien vaut mieux qu'une copie partout ailleurs ; ici il casse un artefact
    sur deux, et le fait a l'installation chez l'utilisateur.
    """
    liens = sorted(str(c.relative_to(RACINE))
                   for c in (RACINE / "packaging").rglob("*") if c.is_symlink())
    assert not liens, (
        f"liens symboliques sous packaging/ : {liens}. Ils rendent la "
        "distribution source de mmu-tui non installable "
        "(LinkOutsideDestinationError).")


@pytest.mark.parametrize("nom", [
    pytest.param("LICENSE", id="LICENSE"),
    pytest.param("THIRD-PARTY-NOTICES.md", id="THIRD-PARTY-NOTICES"),
])
def test_le_texte_juridique_des_deux_distributions_est_IDENTIQUE(nom: str) -> None:
    """Le prix de la copie, mesure plutot que redoute.

    Deux textes de licence dans un depot divergent -- c'est le defaut paye le
    2026-09-07, ou le paquet declarait MIT pendant que la doc annoncait la GPL.
    La copie de `packaging/mmu-tui/` n'est donc pas une seconde source de
    verite : elle est tenue a l'OCTET contre celle de la racine.
    """
    racine = (RACINE / nom).read_bytes()
    copie = (RACINE / "packaging" / "mmu-tui" / nom).read_bytes()
    assert copie == racine, (
        f"packaging/mmu-tui/{nom} a derive de la racine "
        f"({len(copie)} octets contre {len(racine)}) : le paquet publierait "
        "un texte juridique different de celui du depot")


def test_la_distribution_SOURCE_de_mmu_tui_n_est_pas_AUTOPORTANTE(roues):
    """La limite de la forme `packaging/`, MESUREE plutot que decouverte a la
    publication.

    L'arbre de construction de `mmu-tui` est `packaging/mmu-tui/`, et son
    contenu vit deux crans plus haut : le `force-include` et le
    `[tool.hatch.version]` remontent tous deux en `../../`. Ces chemins n'ont
    aucun sens dans une sdist extraite, ou il n'y a pas de `../..`. Mesure du
    2026-09-07 : la sdist de `mmu-tui` porte SIX entrees -- pyproject, les deux
    textes juridiques, le README, `.gitignore`, `PKG-INFO` -- et pas une ligne
    de `mixed_media_utility/`.

    **Ce banc epingle cet etat, il ne le benit pas.** Deux issues, jamais un
    blocage sec, et elles appartiennent a la chaine de publication (story 8.7) :
    ne publier que la ROUE pour `mmu-tui` (elle est `py3-none-any`, donc
    universelle), ou construire les deux distributions depuis la RACINE avec un
    `pyproject.toml` genere. Le jour ou l'une des deux est jouee, ce test rougit
    et se retire -- ce qui est le but : une limite qui se referme doit se
    constater, pas se perimer en silence.
    """
    interpreteur = _interpreteur_de_construction()
    assert interpreteur, "la fixture `roues` aurait deja saute"
    import tarfile
    import tempfile
    with tempfile.TemporaryDirectory() as dossier:
        resultat = subprocess.run(
            [interpreteur, "-c",
             "import sys\nfrom hatchling.build import build_sdist\n"
             "sys.stdout.write(build_sdist(sys.argv[1]))", dossier],
            cwd=PYPROJECT_TUI.parent, capture_output=True, text=True, check=False)
        assert resultat.returncode == 0, resultat.stderr
        archive = Path(dossier) / resultat.stdout.strip()
        with tarfile.open(archive) as tar:
            noms = tar.getnames()
            liens = [m.name for m in tar.getmembers() if m.issym() or m.islnk()]

    assert not liens, (
        f"la sdist de mmu-tui porte des liens : {liens}. `pip install` y "
        "echouerait par LinkOutsideDestinationError.")
    sources = [n for n in noms if f"/{PAQUET}/" in n]
    assert not sources, (
        "la sdist de mmu-tui porte desormais ses sources : la limite s'est "
        "refermee. Relire la story 8.7 -- la publication peut inclure la "
        f"sdist, et ce test se retire. Trouve : {sources[:5]}")


# --------------------------------------------------------------------------
# Auto-verification des detecteurs, sur echantillons de synthese.
#
# Regle des fabriques (CLAUDE.md) : au moins DEUX elements distinguables, la
# cible jamais en premiere position, et une cible a CHAQUE BORD -- « au milieu »
# demasque un `find` fautif, pas un balayage tronque.
# --------------------------------------------------------------------------


def test_le_detecteur_de_fichiers_communs_les_trouve_TOUS():
    """`_communs` accuse chaque fichier partage, pas seulement le premier."""
    cli = {
        "mixed_media_utility/__init__.py",   # COMMUN, en tete
        "mixed_media_utility/cli.py",
        "mixed_media_utility/io/naming.py",  # COMMUN, au milieu
        "mixed_media_utility/layout.py",
        "mixed_media_utility/tui/coque.py",  # COMMUN, en queue
        "mmu_cli-0.1.0.dist-info/RECORD",
    }
    tui = {
        "mixed_media_utility/__init__.py",
        "mixed_media_utility/io/naming.py",
        "mixed_media_utility/tui/coque.py",
        "mixed_media_utility/tui/jetons.py",
        "mmu_tui-0.1.0.dist-info/RECORD",
    }

    assert _communs(cli, tui) == [
        "mixed_media_utility/__init__.py",
        "mixed_media_utility/io/naming.py",
        "mixed_media_utility/tui/coque.py",
    ]
    # Deux roues disjointes : rien a signaler. Un detecteur qui accuserait tout
    # passerait l'assertion precedente sans rien mesurer.
    assert _communs({"a/x.py", "a/y.py"}, {"b/z.py"}) == []


def test_le_detecteur_ecarte_les_dist_info_et_ELLES_SEULES():
    """`_charge_utile` : sans elle, l'AC 3 serait vert par construction.

    Deux `dist-info` ne peuvent JAMAIS se rencontrer -- leur nom porte celui de
    la distribution. Les compter ferait rendre une intersection vide meme a
    deux roues identiques. Le volet symetrique compte autant : un
    `_charge_utile` qui rendrait l'ensemble VIDE ferait taire l'AC 3 pareil.
    """
    noms = {
        "mmu_cli-0.1.0.dist-info/METADATA",       # ecarte, en tete
        "mixed_media_utility/cli.py",
        "mixed_media_utility/io/naming.py",
        "mmu_cli-0.1.0.dist-info/licenses/LICENSE",  # ecarte, en queue
    }
    assert _charge_utile(noms) == {
        "mixed_media_utility/cli.py",
        "mixed_media_utility/io/naming.py",
    }
    # Un nom qui CONTIENT `dist-info` sans etre une metadonnee reste livre :
    # le detecteur coupe sur le separateur, pas sur une sous-chaine.
    assert _charge_utile({"mixed_media_utility/dist-info-lecture.py"}) == {
        "mixed_media_utility/dist-info-lecture.py"}


def test_la_normalisation_des_noms_de_distribution_suit_la_PEP_503():
    """Les formes reelles des deux fichiers, dont celle qui a change en 8.5.

    DEUX formes distinguables par mecanisme -- le souligne et le point --, et
    la cible n'est pas en premiere position.
    """
    attendus = {
        "textual>=8.2,<9": "textual",
        "PySide6-Essentials>=6.8,<6.9": "pyside6-essentials",
        "opencv_python_headless>=4.10,<6": "opencv-python-headless",
        "mmu-cli==0.1.0": "mmu-cli",
        "pytest-qt >= 4.4 ; python_version >= '3.11'": "pytest-qt",
        "paquet[extra]>=1": "paquet",
        "ruamel.yaml": "ruamel-yaml",
    }
    assert {brut: _nom_normalise(brut) for brut in attendus} == attendus


def test_la_CI_INSTALLE_l_extra_dont_le_saut_de_ce_banc_depend():
    """Un saut structurel qui saute EN CI est un banc mort qui s'annonce vert.

    Le garde voisin mesure que `hatchling` reste DECLARE dans les extras. Il ne
    mesurait pas que la CI l'INSTALLE -- et elle ne l'installait pas :
    `pip install -e .` puis `pip install pytest`, rien d'autre. La declaration
    existait, la CI ne s'en servait pas, et les huit controles de roue de ce
    banc sautaient en silence en restant verts.

    Consequence mesuree le 2026-09-07 (revue 8.9, couche 1) : la seule
    verification de la scission en deux distributions -- les deux roues ne
    livrent aucun fichier en commun, chacune declare la commande que `pip`
    posera, `mmu-cli` ne porte aucun chemin `tui/` -- ne tournait NULLE PART.

    Les deux moities se tiennent : declarer sans installer, ou installer sans
    declarer, laissent toutes deux le banc inerte. Il faut les deux frontieres.
    """
    ci = (RACINE / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    # Le nom de l'extra est LU dans le pyproject, jamais recopie ici : le
    # renommer ferait rougir cette frontiere plutot que de la rendre verte a
    # tort.
    donnees = tomllib.loads(PYPROJECT_CLI.read_text(encoding="utf-8"))
    extras = donnees.get("project", {}).get("optional-dependencies", {})
    porteurs = [nom for nom, paquets in extras.items()
                if any(_nom_normalise(d) == "hatchling" for d in paquets)]
    assert porteurs, (
        "aucun extra du pyproject ne porte `hatchling` : le garde voisin "
        "devrait deja rougir, et cette frontiere n'a plus d'extra a exiger")

    installe = [l for l in ci.splitlines()
                if "pip install" in l and "-e ." in l]
    assert installe, "la CI n'installe plus le depot en editable : lecture cassee"

    couvert = any(f"[{nom}]" in ligne for nom in porteurs for ligne in installe)
    assert couvert, (
        "La CI installe le depot SANS l'extra qui porte `hatchling` "
        f"({', '.join(f'[{n}]' for n in porteurs)}), donc les huit controles "
        "de roue de ce banc y SAUTENT en restant verts.\n"
        f"  lignes lues : {installe}")


# --------------------------------------------------------------------------
# La roue qu'on SMOKE-TESTE atterrit la ou on l'INSTALLE (2026-09-08).
#
# Pose apres le PREMIER run de CI reel du projet (34196288009), ou le job
# `Build wheel + sdist` a rendu `mmu-tui: command not found`, exit 127 -- la
# panne EXACTE que le correctif du 2026-09-07 disait fermer.
#
# Ce que ce correctif avait fait, et ce qu'il avait manque : il ajoutait bien
# `python -m build --wheel packaging/mmu-tui`, donc la seconde roue etait
# CONSTRUITE. Mais `build` ecrit par defaut dans le `dist/` DU PROJET
# construit, c'est-a-dire `packaging/mmu-tui/dist/`, quand le smoke test lit
# `dist/` a la racine. Le commentaire du workflow affirmait « les deux roues
# sont installees d'un seul `pip install` [...] dans le meme dossier » : la
# prose disait vrai de l'intention et faux du chemin, et rien ne la mesurait.
#
# La regle : tout `python -m build` de ce workflow nomme son `--outdir`, et
# tous nomment le dossier que le `pip install` lit. Le defaut de `build` est
# precisement ce qui a mordu -- on ne s'en remet donc pas a lui.
# --------------------------------------------------------------------------

#: `python -m build [drapeaux] [chemin]`, avec son `--outdir` s'il en porte un.
_APPEL_DE_BUILD = re.compile(r"python -m build\b([^\n#]*)")
_OUTDIR = re.compile(r"--outdir[= ]+(\S+)")
#: `pip install dist/*.whl` et ses variantes : on ne retient que le dossier.
_INSTALLATION_DE_ROUE = re.compile(r"pip install\s+(\S*?)/\*\.whl")


def _job_de_construction_de_ci() -> str:
    """Rend le texte du job `build` de `ci.yml`, sans les jobs voisins.

    Decoupe a l'indentation des noms de job (deux espaces), comme le reste des
    frontieres de workflow du depot -- PyYAML n'est pas une dependance ici, et
    un `importorskip` rendrait la mesure SAUTEE en CI, c'est-a-dire muette.
    """
    ci = (RACINE / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    debut = ci.index("\n  build:\n")
    reste = ci[debut + 1:]
    suivant = re.search(r"\n  [a-z][\w-]*:\n", reste)
    job = reste[: suivant.start()] if suivant else reste

    # Les lignes de COMMENTAIRE sont retirees, et ce n'est pas un detail de
    # confort : la premiere redaction de cette frontiere a accuse un commentaire
    # qui CITE `python -m build` pour expliquer la panne qu'elle mesure. Un
    # banc qui lit un fichier de configuration lit aussi sa prose ; ici la prose
    # parle precisement du geste fautif, donc elle se fait accuser a sa place.
    return "\n".join(l for l in job.splitlines() if not l.lstrip().startswith("#"))


def test_chaque_python_m_build_de_la_CI_nomme_son_OUTDIR():
    """Aucun appel ne s'en remet au `dist/` par defaut du projet construit."""
    job = _job_de_construction_de_ci()
    appels = _APPEL_DE_BUILD.findall(job)

    assert appels, "aucun `python -m build` lu dans le job build : lecture cassee"

    muets = [a.strip() for a in appels if not _OUTDIR.search(a)]

    assert not muets, (
        "Appel(s) a `python -m build` sans `--outdir` : la roue atterrit dans "
        "le `dist/` du projet CONSTRUIT, pas dans celui qu'on installe.\n"
        + "\n".join(f"  python -m build {a}" for a in muets))


def test_les_DEUX_roues_atterrissent_dans_le_dossier_QU_ON_INSTALLE():
    """Le dossier ecrit et le dossier lu sont le MEME, pour tous les appels."""
    job = _job_de_construction_de_ci()

    ecrits = {m.group(1).rstrip("/") for a in _APPEL_DE_BUILD.findall(job)
              for m in [_OUTDIR.search(a)] if m}
    lus = {m.rstrip("/") for m in _INSTALLATION_DE_ROUE.findall(job)}

    assert ecrits, "aucun --outdir lu : la frontiere voisine devrait deja rougir"
    assert lus, "aucun `pip install <dossier>/*.whl` lu dans le job build"

    orphelins = ecrits - lus

    assert not orphelins, (
        "Dossier(s) ou la CI CONSTRUIT une roue sans jamais l'installer : "
        f"{', '.join(sorted(orphelins))}. Le smoke test lit "
        f"{', '.join(sorted(lus))}.\n"
        "C'est la panne du run 34196288009 : `mmu-tui: command not found`.")


def test_le_smoke_test_joue_les_DEUX_commandes_et_pas_seulement_celle_du_COEUR():
    """Volet d'ANTI-VACUITE : sans lui, les deux tests ci-dessus mesurent le vide.

    Un job qui aurait cesse de jouer `mmu-tui` serait vert pour les deux
    frontieres precedentes tout en ayant abandonne la moitie de la scission --
    c'est exactement le defaut `d8cc7736` que ce banc existe pour attraper,
    pris par l'autre bout.

    Les noms de commande sont LUS dans les deux pyproject, jamais recopies ici.
    """
    job = _job_de_construction_de_ci()

    attendues = set()
    for chemin in (PYPROJECT_CLI, PYPROJECT_TUI):
        donnees = tomllib.loads(chemin.read_text(encoding="utf-8"))
        attendues |= set(donnees.get("project", {}).get("scripts", {}))

    assert len(attendues) == 2, f"deux commandes attendues, lues : {sorted(attendues)}"

    absentes = sorted(c for c in attendues if not re.search(rf"^\s*{re.escape(c)} ", job, re.M))

    assert not absentes, (
        "Commande(s) declaree(s) par une roue mais jamais jouee(s) par le "
        f"smoke test de la CI : {', '.join(absentes)}")


# --------------------------------------------------------------------------
# Le job de TEST installe les DEUX distributions (2026-09-08).
#
# Troisieme panne du portage, trouvee par le run 34196942658 apres que les
# deux premieres eurent ete fermees :
#
#     tests/unit/test_raccords_du_nommage_des_cadences.py:61:
#         from mixed_media_utility.tui.cadences import nom_court_de_cadence
#     E   ModuleNotFoundError: No module named 'textual'
#     !!!!!! stopping after 1 failures !!!!!!
#
# Le job n'installait que `mmu-cli`, et `textual` appartient a la zone TUI --
# `tests/unit/test_contrat_de_dependances.py` mesure justement qu'il ne peut
# PAS etre declare par `mmu-cli`. La sortie n'est donc pas de recopier le
# paquet dans un extra du coeur : c'est d'installer l'AUTRE distribution.
#
# Ce que cette frontiere protege, et qui n'est pas evident : l'autre sortie
# -- ecarter les tests qui importent la TUI -- aurait rendu la CI verte en
# cessant de mesurer la moitie du produit. Une CI qui verdit en mesurant
# moins est le pire des deux mondes, et rien ne l'aurait dit.
# --------------------------------------------------------------------------


def _job_de_test_de_ci() -> str:
    """Rend le texte du job `test` de `ci.yml`, commentaires retires."""
    ci = (RACINE / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    debut = ci.index("\n  test:\n")
    reste = ci[debut + 1:]
    suivant = re.search(r"\n  [a-z][\w-]*:\n", reste)
    job = reste[: suivant.start()] if suivant else reste
    return "\n".join(l for l in job.splitlines() if not l.lstrip().startswith("#"))


def test_le_job_de_TEST_installe_les_DEUX_distributions():
    """Les deux racines de projet sont installees, pas seulement le coeur.

    Les chemins sont deduits des deux `pyproject.toml` que ce banc connait
    deja, jamais recopies : deplacer `packaging/mmu-tui` fait rougir ici.
    """
    job = _job_de_test_de_ci()
    installations = [l.strip() for l in job.splitlines() if "pip install" in l]

    assert installations, "le job `test` n'installe plus rien : lecture cassee"

    chemin_tui = PYPROJECT_TUI.parent.relative_to(RACINE).as_posix()
    porte_le_coeur = any(re.search(r"-e\s+\.(\[|\s|$)", l) for l in installations)
    porte_la_tui = any(chemin_tui in l for l in installations)

    assert porte_le_coeur, (
        "le job `test` n'installe plus le coeur en editable :\n  "
        + "\n  ".join(installations))
    assert porte_la_tui, (
        f"le job `test` n'installe pas la distribution `{chemin_tui}`, donc "
        "`textual` est absent et tout test qui importe "
        "`mixed_media_utility.tui` rend une ERREUR de collecte -- avec `-x`, "
        "la suite entiere s'arrete dessus (run 34196942658).\n  "
        + "\n  ".join(installations))


def test_la_TUI_s_installe_APRES_le_coeur_qu_elle_EPINGLE():
    """L'ordre n'est pas cosmetique : `mmu-tui` epingle `mmu-cli==<version>`.

    Mesure du 2026-09-08 en environnement jetable : `pip install -e
    ./packaging/mmu-tui` SEUL part chercher l'epingle sur l'index public et
    echoue (« No matching distribution found for mmu-cli==0.1.0 »), la
    version n'y etant pas publiee. Apres le editable de la racine, pip la
    resout sur la distribution deja presente.
    """
    job = _job_de_test_de_ci()
    lignes = [l.strip() for l in job.splitlines() if "pip install" in l]

    chemin_tui = PYPROJECT_TUI.parent.relative_to(RACINE).as_posix()
    rangs_coeur = [i for i, l in enumerate(lignes) if re.search(r"-e\s+\.(\[|\s|$)", l)]
    rangs_tui = [i for i, l in enumerate(lignes) if chemin_tui in l]

    assert rangs_coeur and rangs_tui, (
        "la frontiere voisine devrait deja rougir : une des deux "
        "installations manque")

    assert min(rangs_coeur) < min(rangs_tui), (
        "`mmu-tui` est installe AVANT le coeur qu'il epingle : pip ira "
        "chercher l'epingle sur l'index public, ou la version n'existe pas.\n  "
        + "\n  ".join(lignes))


# --------------------------------------------------------------------------
# Les BINAIRES EXTERNES que le produit cherche sont ceux que la CI installe
# (2026-09-08).
#
# Quatrieme panne du portage, run 34197301716 : les trois jobs de test morts
# au MEME test, de facon deterministe, apres 703 verts --
#
#     EncoderUnavailableError: Binaire ffmpeg introuvable dans le PATH
#
# `ffmpeg` n'est pas dans l'image `ubuntu-latest`. Ce n'est pas une commodite
# de banc qui manquait : `scripts/install.sh` installe ffmpeg pour
# l'utilisateur et la documentation le declare prerequis. Une CI sans lui
# mesure le produit dans un etat ou aucun utilisateur ne se trouve.
#
# Les noms sont LUS dans `src/`, jamais recopies ici : le produit declare ses
# binaires en DEFAUT de parametre (`ffmpeg_bin: str = "ffmpeg"`), et c'est
# cette declaration qui fait foi. Renommer le binaire cherche sans porter le
# paquet installe fait rougir ici.
# --------------------------------------------------------------------------


def _binaires_externes_du_produit() -> set[str]:
    """Rend les defauts litteraux des parametres de binaire externe de `src/`.

    Le critere est le NOM du parametre (`*_bin`, `*_binary`) associe a un
    defaut litteral de type `str`. Il attrape `ffmpeg_bin: str = "ffmpeg"` et
    `ffprobe_bin: str = "ffprobe"` sans qu'aucun des deux soit ecrit ici.
    """
    noms: set[str] = set()
    source = RACINE / "src" / "mixed_media_utility"
    for fichier in source.rglob("*.py"):
        try:
            arbre = ast.parse(fichier.read_text(encoding="utf-8"), filename=str(fichier))
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            arguments = noeud.args
            # Les defauts s'alignent sur la FIN des positionnels ; les
            # `kwonly` ont leur propre liste, alignee terme a terme et
            # pouvant porter `None` la ou il n'y a pas de defaut.
            positionnels = [*arguments.posonlyargs, *arguments.args]
            paires = list(zip(positionnels[len(positionnels) - len(arguments.defaults):],
                              arguments.defaults))
            paires += [(a, d) for a, d in zip(arguments.kwonlyargs, arguments.kw_defaults) if d]
            for parametre, defaut in paires:
                if not parametre.arg.endswith(("_bin", "_binary")):
                    continue
                if isinstance(defaut, ast.Constant) and isinstance(defaut.value, str):
                    noms.add(defaut.value)
    return noms


def test_le_releve_des_BINAIRES_du_produit_n_est_pas_vide():
    """Volet d'ANTI-VACUITE : sans lui, la frontiere voisine mesure le vide.

    Un critere de lecture casse -- un renommage de parametre, un changement
    d'idiome -- rendrait l'ensemble vide, et « tout element de l'ensemble vide
    est installe » est vrai pour toujours.
    """
    binaires = _binaires_externes_du_produit()

    assert binaires, (
        "aucun binaire externe lu dans src/ : le critere (`*_bin` / "
        "`*_binary` avec un defaut litteral) ne trouve plus rien")


def test_la_CI_installe_les_binaires_que_le_PRODUIT_cherche_dans_le_PATH():
    """Chaque binaire declare par `src/` est installe par le job de test."""
    job = _job_de_test_de_ci()
    binaires = _binaires_externes_du_produit()

    absents = sorted(b for b in binaires if not re.search(rf"\b{re.escape(b)}\b", job))

    assert not absents, (
        "Binaire(s) que le produit cherche dans le PATH et que le job de test "
        f"n'installe ni ne nomme : {', '.join(absents)}.\n"
        "L'image `ubuntu-latest` ne porte pas ffmpeg : sans installation "
        "explicite, chaque appel leve `EncoderUnavailableError` et `-x` "
        "arrete la suite (run 34197301716).")
