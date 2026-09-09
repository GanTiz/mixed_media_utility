"""Frontiere du livrable pip : ce que la SDIST embarque (EPIC11-ARB-255).

Motif, mesure le 2026-09-06 en construisant reellement les deux archives sur
cet arbre :

    mmu_tui-0.1.0.tar.gz           77,8 Mo
    mmu_tui-0.1.0-py3-none-any.whl  2,1 Mo

Trente-sept fois la roue. Hatchling, sans `include` explicite, embarque tout ce
que git ne masque pas : `tests/` et ses fixtures LFS (66 Mo), `_bmad-output/`
(42 Mo d'artefacts de test), `.agents/` (17 Mo), les captures de `docs/`. Rien
de tout cela n'est necessaire pour INSTALLER le produit, et 78 Mo frole le
plafond de 100 Mo par fichier de PyPI -- une fixture de plus et la publication
echouait au `twine upload`, c'est-a-dire trop tard.

CE QUE CE BANC MESURE, ET POURQUOI PAS LE POIDS.

Il confronte l'`include` declare a l'ARBRE REEL, dans les deux sens : le
cardinal selectionne reste sous la borne, et il la FRANCHIT des qu'on rouvre
`tests/`. La frontiere negative est le seul moyen d'attraper la reintroduction
du defaut -- un `include` efface ne se verrait dans aucun test positif.

Le critere est le CARDINAL, pas les octets, et c'est delibere : sans `git-lfs`
installe, les fixtures valent 133 octets chacune (CLAUDE.md, 2026-09-01) et une
borne de poids ne mordrait plus. Le cardinal, lui, ne depend pas de LFS.

Ce banc ne construit PAS d'archive et n'importe pas hatchling -- il n'est pas
une dependance du depot. Il reimplemente la seule semantique d'`include` que
l'on emploie ici, le PREFIXE DE CHEMIN, et un banc ci-dessous verifie que les
motifs declares s'y tiennent : si quelqu'un ecrit un jour un vrai glob, ce
banc rougit plutot que de mesurer a cote.
"""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

import pytest

RACINE_DEPOT = Path(__file__).resolve().parents[2]
PYPROJECT = RACINE_DEPOT / "pyproject.toml"

# Borne du cardinal selectionne. Remesuree sur l'arbre FUSIONNE au 2026-09-07,
# la TUI de l'Epic 11 ayant ajoute 52 fichiers a `src/` :
#
#     selectionne aujourd'hui        147   (le paquet, README, requirements)
#     avec `tests/` rouvert          547   (400 fichiers de plus)
#
# La borne se pose ENTRE les deux, et pas au milieu par gout : elle laisse au
# paquet de quoi grossir de 70 % sans rien dire, et elle mord bien avant que
# `tests/` ne rentre. Le banc `..._MORD_...` ci-dessous mesure la seconde
# moitie de cette phrase plutot que de la croire.
#
# La mesure du 2026-09-06 annoncait 139 et 358 ; les deux ont bouge d'un
# arbre a l'autre, ce qui est le regime normal d'une borne posee sur un
# cardinal reel.
BORNE_DE_CARDINAL = 250

# Repertoires dont la presence dans la sdist EST le defaut de 2026-09-06.
REPERTOIRES_QUI_NE_DOIVENT_PAS_ENTRER = (
    "tests",
    "_bmad-output",
    ".agents",
    "docs",
    "_bmad",
    ".claude",
)


def _include_declare() -> list[str]:
    """Les motifs `include` de la cible sdist, tels que pyproject les porte.

    Rend une liste VIDE quand la cible manque, plutot que de lever : une cible
    effacee est precisement le defaut a mesurer, et elle doit produire un rouge
    NOMME. Mesure le 2026-09-06 : en levant, elle cassait la collecte du module
    entier (`KeyError: 'sdist'` dans le decorateur `parametrize`), ce qui dit
    beaucoup moins que « la cible sdist declare un include vide ».
    """
    tables = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    cible = tables.get("tool", {}).get("hatch", {}).get("build", {})
    return list(cible.get("targets", {}).get("sdist", {}).get("include", []))


def _fichiers_selectionnes(motifs) -> list[Path]:
    """Les fichiers de l'arbre reel qu'`include` retient, en semantique prefixe.

    On marche l'arbre plutot que de faire confiance au litteral : c'est l'EFFET
    de la declaration qui est mesure, pas la declaration elle-meme.

    Le `/` de tete est retire ici -- il ANCRE le motif a la racine cote
    hatchling (voir le banc d'ancrage ci-dessous), il ne designe pas la racine
    du systeme de fichiers.
    """
    retenus = []
    for motif in motifs:
        depart = RACINE_DEPOT / motif.lstrip("/")
        if depart.is_file():
            retenus.append(depart)
        elif depart.is_dir():
            retenus.extend(c for c in depart.rglob("*") if c.is_file())
    return _hors_ignores_de_git(retenus)


def _hors_ignores_de_git(chemins: list[Path]) -> list[Path]:
    """Retire ce que le VCS ignore -- ce que hatchling retire aussi.

    **Defaut mesure le 2026-09-07, et il rendait ce banc dependant de l'ordre
    des commandes.** Sans ce filtre, `rglob` comptait les `__pycache__/*.pyc`
    de l'arbre de travail : **286** fichiers apres un `pytest`, **147** dans un
    clone neuf. Le meme arbre donnait donc deux verdicts selon qu'on avait
    joue la suite avant, et c'est ce qui a fait rougir la borne a la fusion de
    l'Epic 11 -- 286 contre 250 -- alors que le paquet reel n'en porte que 147.

    Ce n'est pas un assouplissement : hatchling exclut par defaut ce que les
    fichiers d'ignore du VCS designent, `__pycache__/` en tete
    (`.gitignore:2`). Le filtre RAPPROCHE donc l'approximation de l'effet reel
    au lieu de l'en eloigner.

    Hors depot git, il ne filtre rien plutot que de lever : un banc ne rougit
    jamais pour une raison d'environnement.
    """
    if not chemins:
        return chemins
    relatifs = [str(c.relative_to(RACINE_DEPOT)) for c in chemins]
    try:
        sonde = subprocess.run(
            ["git", "check-ignore", "--stdin"], cwd=RACINE_DEPOT,
            input="\n".join(relatifs), capture_output=True, text=True,
            timeout=120)
    except (OSError, subprocess.SubprocessError):  # pragma: no cover
        return chemins
    # `check-ignore` sort a 1 quand RIEN n'est ignore, et a 128 hors depot :
    # les deux sont des reponses, pas des pannes. Seul le code 128 se traduit
    # par « je ne sais pas », donc par aucun filtrage.
    if sonde.returncode not in (0, 1):  # pragma: no cover - hors depot git
        return chemins
    ignores = set(sonde.stdout.splitlines())
    return [c for c, r in zip(chemins, relatifs) if r not in ignores]


def test_la_cible_sdist_est_scopee_explicitement():
    """Sans `include`, hatchling embarque l'arbre entier -- c'etait le defaut."""
    motifs = _include_declare()
    assert motifs, "la cible sdist declare un `include` vide : tout entrerait"


@pytest.mark.parametrize("motif", _include_declare() or [None])
def test_chaque_motif_declare_est_un_prefixe_de_chemin_reel(motif):
    """Garde-fou de la mesure elle-meme : ce banc ne sait lire que des prefixes.

    Un vrai glob (`*`, `?`, `[`) le ferait mesurer a cote sans rien dire ; il
    rougit plutot, et c'est a ce moment-la qu'on outillera la comparaison.
    """
    assert motif is not None, "la cible sdist ne declare aucun motif `include`"
    assert not set("*?[]") & set(motif), (
        f"`{motif}` est un glob : ce banc ne sait comparer que des prefixes"
    )
    assert (RACINE_DEPOT / motif.lstrip("/")).exists(), (
        f"`{motif}` est declare a l'`include` mais absent de l'arbre"
    )


@pytest.mark.parametrize("motif", _include_declare() or [None])
def test_chaque_motif_est_ANCRE_a_la_racine(motif):
    """Un motif sans `/` de tete matche a TOUTE profondeur, et ca a mordu.

    Hatchling lit `include` en semantique `.gitignore`. Mesure du 2026-09-06,
    en ouvrant l'archive construite : le motif `README.md`, ecrit sans ancrage,
    avait ramene DIX-NEUF fichiers disperses dans `_bmad/`, `_bmad-output/`,
    `docs/`, `scripts/` et `tests/` -- une partie exacte de ce que le scoping
    venait d'exclure.

    Ce banc est aussi l'aveu de sa propre limite : `_fichiers_selectionnes`
    approxime hatchling par un PREFIXE. L'approximation ne vaut que sur des
    motifs ancres ; des qu'un motif ne l'est plus, le banc mesurerait a cote
    sans rien dire. Il rougit donc a la place.
    """
    assert motif is not None, "la cible sdist ne declare aucun motif `include`"
    assert motif.startswith("/"), (
        f"`{motif}` n'est pas ancre : en semantique .gitignore il matche a "
        "toute profondeur, et ramene ce que l'`include` croit exclure"
    )


def test_le_cardinal_selectionne_reste_sous_la_borne():
    """Le sens positif : ce que la sdist embarque reste petit."""
    retenus = _fichiers_selectionnes(_include_declare())
    assert len(retenus) <= BORNE_DE_CARDINAL, (
        f"{len(retenus)} fichiers selectionnes, borne {BORNE_DE_CARDINAL}"
    )


def test_la_borne_de_cardinal_MORD_si_on_rouvre_les_fixtures():
    """La frontiere negative, sans laquelle la borne pourrait etre vide.

    Une borne qu'aucune configuration plausible ne franchit ne mesure rien. On
    rejoue donc le calcul avec `tests/` rouvert -- exactement l'etat d'avant
    l'arbitrage -- et on exige qu'il la franchisse.
    """
    retenus = _fichiers_selectionnes([*_include_declare(), "tests"])
    assert len(retenus) > BORNE_DE_CARDINAL, (
        "rouvrir `tests/` ne franchit pas la borne : elle ne mesure rien"
    )


@pytest.mark.parametrize("repertoire", REPERTOIRES_QUI_NE_DOIVENT_PAS_ENTRER)
def test_aucun_repertoire_de_travail_n_entre_dans_la_sdist(repertoire):
    """Nomme un a un les repertoires du defaut, pour que l'echec les nomme."""
    if not (RACINE_DEPOT / repertoire).exists():
        pytest.skip(f"`{repertoire}` absent de cet arbre")
    interdit = (RACINE_DEPOT / repertoire).resolve()
    for chemin in _fichiers_selectionnes(_include_declare()):
        assert interdit not in chemin.resolve().parents, (
            f"{chemin} entre dans la sdist alors que `{repertoire}/` en est exclu"
        )


def test_le_paquet_du_produit_EST_selectionne():
    """Le contrepoint positif : un scoping qui exclut tout serait vert sinon.

    On vise le paquet que `[tool.hatch.build.targets.wheel]` declare -- si
    celui-la manque, la sdist ne construit pas un produit installable, elle
    construit une archive vide qui passe toutes les bornes ci-dessus.

    **Pourquoi le paquet et non le module de `[project.scripts]`.** Ce serait la
    cible plus precise, et elle est INAPPLICABLE ICI : sur cette branche,
    `[project.scripts]` designe `mixed_media_utility.tui.__main__`, qui
    n'existe pas dans l'arbre. Ce banc rougirait sur un defaut REEL mais qui
    n'est pas le sien -- le point d'entree casse est un defaut d'empaquetage a
    trancher, pas un defaut de scoping de la sdist. Il est signale a part
    plutot que mesure ici, pour qu'un rouge de ce fichier veuille toujours dire
    << la sdist embarque mal >>.
    """
    tables = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    paquets = tables["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
    retenus = {c.resolve() for c in _fichiers_selectionnes(_include_declare())}
    for paquet in paquets:
        init = (RACINE_DEPOT / paquet / "__init__.py").resolve()
        assert init in retenus, (
            f"le paquet `{paquet}` declare a la roue n'entre pas dans la sdist"
        )


def test_le_README_declare_a_la_metadonnee_EST_selectionne():
    """`readme = "README.md"` : hatchling exige le fichier a la construction."""
    tables = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    readme = tables["project"]["readme"]
    retenus = {c.resolve() for c in _fichiers_selectionnes(_include_declare())}
    assert (RACINE_DEPOT / readme).resolve() in retenus, (
        f"`{readme}` est declare a la metadonnee mais hors de la sdist : "
        "la construction echouerait"
    )


# --------------------------------------------------------------------------
# Ce que la roue doit emporter pour FONCTIONNER, et pas seulement ce qu'elle
# ne doit pas emporter
# --------------------------------------------------------------------------
#
# Les bancs ci-dessus mesurent tous ce que le livrable ne doit PAS contenir.
# C'etait une frontiere negative sans sa symetrique, et elle a laisse passer un
# defaut mesure le 2026-09-07 : `io/manifest.py` resolvait ses trois schemas
# JSON depuis la RACINE DU DEPOT (`Path(__file__).resolve().parents[3]`).
#
#     roue construite, installee dans un venv neuf :
#       fichiers .json embarques : AUCUN  (88 fichiers au total)
#       schema attendu : <venv>/lib/python3.11/_bmad-output/specs/…
#       present ?      : False
#       validate_manifest(...) -> FileNotFoundError
#
# Autrement dit : `pip install mmu-tui` livrait un paquet incapable de valider
# un manifest. Aucun des 18 000 tests ne le voyait, parce qu'ils tournent TOUS
# depuis le depot, ou `parents[3]` tombe juste. Les schemas vivent desormais
# dans `src/mixed_media_utility/specs/`.

import json  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402

_PAQUET = RACINE_DEPOT / "src" / "mixed_media_utility"

SCHEMAS_ATTENDUS = (
    "project.schema.json",
    "project.schema.v2-0.json",
    "project.schema.legacy.json",
)


@pytest.mark.parametrize("nom", SCHEMAS_ATTENDUS)
def test_les_schemas_sont_une_DONNEE_DU_PAQUET(nom):
    """Ils doivent etre SOUS le paquet, seul arbre que la roue emporte.

    `[tool.hatch.build.targets.wheel] packages = ["src/mixed_media_utility"]` :
    un fichier hors de cet arbre n'entre pas dans la roue, quel que soit son
    interet. C'est ce qui rend l'emplacement structurant plutot que cosmetique.
    """
    assert (_PAQUET / "specs" / nom).is_file(), (
        f"{nom} n'est pas sous `src/mixed_media_utility/specs/` : il ne partira "
        "pas dans la roue")


def test_AUCUN_module_ne_resout_un_chemin_depuis_la_RACINE_DU_DEPOT():
    """Frontiere NEGATIVE : `parents[3]` est le defaut, pas le chemin.

    Depuis `src/mixed_media_utility/io/x.py`, `parents[3]` vaut la racine du
    depot dans un clone et `lib/python3.x/` dans un `site-packages`. Un module
    LIVRE n'a aucune raison de remonter au-dessus de son propre paquet : tout
    ce dont il a besoin doit voyager avec lui.

    La frontiere porte sur `src/` seul. Les tests et les scripts, eux, ont le
    droit de connaitre la racine du depot -- ils ne sont pas distribues.
    """
    fautifs = []
    for chemin in sorted(_PAQUET.rglob("*.py")):
        for numero, ligne in enumerate(
                chemin.read_text(encoding="utf-8").splitlines(), start=1):
            depouillee = ligne.lstrip()
            if depouillee.startswith("#"):
                continue
            if "parents[3]" in ligne or "parents[4]" in ligne:
                fautifs.append(
                    f"{chemin.relative_to(RACINE_DEPOT)}:{numero}: {ligne.strip()}")

    assert not fautifs, (
        "Un module livre remonte au-dessus de son propre paquet ; ce chemin "
        "sera faux une fois installe :\n  " + "\n  ".join(fautifs))


def test_le_schema_se_RESOUT_hors_du_depot__simulation_d_installation():
    """La mesure de bout en bout, sans construire de roue ni toucher au reseau.

    Le paquet est recopie AILLEURS, comme un `site-packages` le ferait, puis
    importe depuis la : c'est exactement le regime ou `parents[3]` cessait de
    tomber juste. Un sous-process, pour que l'import ne soit pas servi par le
    module deja charge dans cette session.

    C'est le banc qui manquait le 2026-09-07 -- celui qui aurait vu la panne
    avant l'utilisateur.
    """
    bac = RACINE_DEPOT / ".pytest_cache" / "simulation_installation"
    if bac.exists():
        shutil.rmtree(bac)
    bac.mkdir(parents=True)
    try:
        shutil.copytree(_PAQUET, bac / "mixed_media_utility",
                        ignore=shutil.ignore_patterns("__pycache__"))

        programme = (
            "import json, sys\n"
            "from mixed_media_utility.io import manifest as m\n"
            "from mixed_media_utility.io import reconstruction as r\n"
            "print(json.dumps({\n"
            "  'manifest': [str(p) for p in (m.DEFAULT_SCHEMA_PATH,\n"
            "               m.SCHEMA_V2_0_PATH, m.LEGACY_SCHEMA_PATH)],\n"
            "  'reconstruction': str(r.SCHEMA_PATH),\n"
            "  'tous_presents': all(p.exists() for p in (m.DEFAULT_SCHEMA_PATH,\n"
            "      m.SCHEMA_V2_0_PATH, m.LEGACY_SCHEMA_PATH, r.SCHEMA_PATH)),\n"
            "}))\n"
        )
        sortie = subprocess.run(
            [sys.executable, "-c", programme],
            cwd=bac, capture_output=True, text=True,
            env={"PYTHONPATH": str(bac), "PATH": "/usr/bin:/bin",
                 "HOME": str(bac)},
        )
        assert sortie.returncode == 0, (
            "l'import du paquet recopie a echoue :\n" + sortie.stderr[-2000:])

        vu = json.loads(sortie.stdout)
        assert vu["tous_presents"], (
            "Recopie hors du depot, le paquet ne retrouve plus ses schemas -- "
            "c'est le regime d'un `pip install`. Chemins resolus :\n  "
            + "\n  ".join(vu["manifest"] + [vu["reconstruction"]]))

        # Et ils se resolvent SOUS le paquet recopie, pas par hasard sous le
        # depot : sans cette seconde moitie, un chemin absolu fige vers l'arbre
        # de developpement passerait le test ci-dessus.
        for resolu in vu["manifest"] + [vu["reconstruction"]]:
            assert str(bac) in resolu, (
                f"schema resolu HORS du paquet recopie : {resolu}")
    finally:
        shutil.rmtree(bac, ignore_errors=True)
