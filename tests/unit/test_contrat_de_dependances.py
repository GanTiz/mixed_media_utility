"""Frontiere du contrat de dependances (story 8.4, EPIC8-ARB-1/-2/-3 ; story
8.5, EPIC8-ARB-5).

Ce banc mesure l'ECART entre deux ensembles qui doivent coincider :

* ce que le code IMPORTE reellement, releve par analyse AST de
  `src/mixed_media_utility/` ;
* ce que les `pyproject.toml` DECLARENT, dans `[project].dependencies` et dans
  l'extra `[gui]`.

**Depuis la story 8.5, il y a DEUX declarations et non plus une**, et le banc
mesure une regle de ZONE entre elles (`EPIC8-ARB-5`, Egan le 2026-09-07) :

* `pyproject.toml` a la racine declare `mmu-cli` -- le coeur, `cli/` et `gui/` ;
* `packaging/mmu-tui/pyproject.toml` declare `mmu-tui` -- `tui/` seul, qui
  depend de `mmu-cli`.

La regle, mesuree dans les DEUX sens : un paquet tiers que SEUL `tui/` importe
est declare par `mmu-tui` et **pas** par `mmu-cli` ; tout ce qui est importe
hors de `tui/` est declare par `mmu-cli` ; et rien de declare d'un cote ou de
l'autre n'est importe par personne. Sans la moitie negative, `mmu-cli`
pourrait redeclarer `textual` -- soit 28 Mo factures a qui n'installe que la
CLI, ce que la scission existe precisement pour eviter.

Motif, mesure le 2026-08-30 : les deux ensembles avaient diverge DANS LES DEUX
SENS. `opencv-contrib-python` etait importe par dix modules du coeur tout en
n'etant declare que dans l'extra `[gui]` -- si bien qu'un `pip install mmu-tui`
sans extra rendait une installation ou `cli.py` plantait a l'import. Et
`ffmpeg-python` etait declare sans qu'aucun fichier du depot ne l'importe.

Corriger `pyproject.toml` ne suffisait pas : rien n'aurait empeche la prochaine
dependance de repartir en extra. D'ou une frontiere plutot qu'un correctif.

--------------------------------------------------------------------------
MUTATIONS JOUEES sur les volets AJOUTES par la story 8.5, et leur verdict
(2026-09-07 ; l'arbre est restaure depuis une copie prise avant, jamais par
`git checkout`) :

  N1  `_du_seul_chemin_tui` rend `{}`                -> ROUGE
  N2  `_du_seul_chemin_tui` ne filtre plus           -> ROUGE (3 tests)
  N3  `_hors_zone` rend `[]`                         -> ROUGE
  N4  `_hors_zone` rend `[:1]`                       -> ROUGE
  N5  `textual` remis dans `mmu-cli`                 -> ROUGE (2)
  N6  `rich` retire de `mmu-tui`                     -> ROUGE
  N7  `ffmpeg-python` declare par `mmu-tui`          -> ROUGE (2)
  N8  `DISTRIBUTIONS_DU_DEPOT` videe                 -> ROUGE (2)
  N9  `cv2` -> `opencv-contrib-python`               -> ROUGE (3)
  N10 `_modules_python` ignore `inclure_tui`         -> ROUGE
  N11 `_modules_du_seul_chemin_tui` rend TOUT `src/` -> SURVIVANT au premier
      tour, puis ROUGE : c'est lui qui a fait ecrire
      `test_les_ZONES_partitionnent_bien_src_sans_recouvrement_ni_trou`. La
      difference d'ensembles rattrapait l'erreur sur l'arbre du jour, mais un
      paquet importe par le SEUL `gui/` serait alors passe pour une dependance
      legitime de `mmu-tui`.
--------------------------------------------------------------------------
"""

from __future__ import annotations

import ast
import sys
import tomllib
from unittest import mock
from pathlib import Path

import pytest

RACINE_DEPOT = Path(__file__).resolve().parents[2]
SOURCES = RACINE_DEPOT / "src" / "mixed_media_utility"
PYPROJECT = RACINE_DEPOT / "pyproject.toml"
#: La seconde declaration, celle de `mmu-tui` (story 8.5).
PYPROJECT_TUI = RACINE_DEPOT / "packaging" / "mmu-tui" / "pyproject.toml"

#: Les distributions du depot LUI-MEME. `mmu-tui` depend de `mmu-cli` : ce nom
#: apparait donc dans une liste de `dependencies` sans correspondre a aucun
#: `import`, et le volet « declare et importe par personne » l'accuserait a
#: tort. Ce n'est pas une tolerance -- c'est un arc INTERNE, qui a son propre
#: banc (`tests/unit/test_deux_distributions.py`).
DISTRIBUTIONS_DU_DEPOT = frozenset({"mmu-cli", "mmu-tui"})

#: Correspondance nom d'IMPORT -> nom de DISTRIBUTION.
#:
#: Elle est EXPLICITE et non devinee : `import cv2` vient de la distribution
#: `opencv-python-headless`, `import PIL` de `Pillow`. Aucune heuristique ne
#: relie ces deux noms, et une heuristique qui les relierait par hasard
#: masquerait le jour ou l'un des deux change.
#:
#: `cv2` a change de distribution le 2026-09-06 (`EPIC11-ARB-253`, porte ici
#: par la story 8.5) : `opencv-contrib-python` -> `opencv-python-headless`. Le
#: motif dominant n'est pas le poids mais l'IMPORT : la roue non-headless lie
#: son binaire a douze bibliotheques systeme graphiques qu'un conteneur nu n'a
#: pas, et `import cv2` y echoue sur `libGL.so.1` avant la premiere ligne du
#: produit. Les 51 symboles `cv2.*` employes par `src/` existent tous dans la
#: roue non-contrib, `aruco.ArucoDetector` compris.
#:
#: Les QUATRE roues d'OpenCV publient le MEME module `cv2` : cette table est
#: donc le seul endroit du depot ou le choix se lit, et c'est pourquoi il s'y
#: ecrit plutot que de se deviner.
IMPORT_VERS_DISTRIBUTION = {
    "cv2": "opencv-python-headless",
    "PIL": "Pillow",
}

#: Les roues OpenCV qui EXIGENT des bibliotheques systeme graphiques. Mesure du
#: 2026-09-06 a l'`ldd` : leur `cv2.abi3.so` reclame douze objets partages de
#: plus que la roue headless -- `libGL.so.1`, `libX11.so.6`, `libglib-2.0.so.0`
#: en tete --, absents d'un serveur nu, d'un conteneur minimal et d'un WSL sans
#: X. Sur ces postes `import cv2` echoue AVANT la premiere ligne du produit.
ROUES_OPENCV_QUI_EXIGENT_UN_AFFICHAGE = frozenset({
    "opencv-python", "opencv-contrib-python",
})

#: Modules tiers dont l'absence de declaration est ADMISE parce qu'ils ne sont
#: jamais installes : ce sont des outils de developpement importes par des
#: scripts, pas par le chemin d'execution. Vide a ce jour -- la constante
#: existe pour que l'ajout d'une exception soit un geste visible en revue,
#: jamais une ligne noyee dans le corps du banc.
TOLERANCES_DECLARATION: frozenset[str] = frozenset()


def _nom_de_distribution(nom_importe: str) -> str:
    """Rend le nom de distribution correspondant a un nom de module importe."""
    return IMPORT_VERS_DISTRIBUTION.get(nom_importe, nom_importe)


def _nom_normalise(specification: str) -> str:
    """Extrait le nom d'une specification PEP 508 (`opencv>=4.10,<4.11` -> `opencv`).

    La normalisation suit la PEP 503 : casse indifferente, et `-`, `_`, `.`
    equivalents. Sans elle, `opencv-contrib-python` et `opencv_contrib_python`
    seraient deux paquets differents pour ce banc.
    """
    nom = specification
    # `@` est dans la liste depuis la revue de la story (couche 2) : ce
    # `pyproject.toml` pose `[tool.hatch.metadata] allow-direct-references =
    # true`, donc la forme `nom@url` y est activee PAR DECISION. Sans cette
    # coupure, `pypdfium2@https://.../p.whl` se normalisait en
    # `pypdfium2@https://...`, un nom qui ne correspond a aucun import : le
    # volet anti-rechute devenait AVEUGLE en silence, et une suite entierement
    # verte pouvait cohabiter avec un coeur important Qt.
    for separateur in ("[", ">", "<", "=", "!", "~", ";", " ", "@"):
        nom = nom.split(separateur)[0]
    nom = nom.strip().lower().replace("_", "-").replace(".", "-")
    if not nom:
        raise ValueError(
            f"specification de dependance sans nom exploitable : {specification!r}. "
            "Un nom vide comparerait des ensembles qui ne se rencontrent jamais, "
            "donc ferait taire les trois volets sans rien dire."
        )
    return nom


def _modules_python(inclure_gui: bool, inclure_tui: bool = True) -> list[Path]:
    """Liste les modules de `src/`, par ZONE.

    Trois zones depuis la story 8.5, et elles ne se recouvrent pas : `gui/`
    (extra `[gui]` de `mmu-cli`), `tui/` (la distribution `mmu-tui`), et le
    reste (`mmu-cli`). Le parametre `inclure_tui` est ce qui permet de poser la
    question « qui importe ce paquet, et de quel cote de la scission ? ».
    """
    fichiers = sorted(SOURCES.rglob("*.py"))
    def _garde(fichier: Path) -> bool:
        parties = fichier.relative_to(SOURCES).parts
        if not inclure_gui and "gui" in parties:
            return False
        if not inclure_tui and "tui" in parties:
            return False
        return True
    return [f for f in fichiers if _garde(f)]


def _modules_du_seul_chemin_tui() -> list[Path]:
    """Les modules de `src/mixed_media_utility/tui/`, et eux seuls."""
    return [f for f in sorted(SOURCES.rglob("*.py"))
            if "tui" in f.relative_to(SOURCES).parts]


def _imports_tiers(fichiers: list[Path]) -> dict[str, set[str]]:
    """Rend {nom de distribution -> fichiers qui l'importent}, hors stdlib.

    Les imports relatifs (`from .foo import bar`, `node.level > 0`) et le
    paquet lui-meme sont ecartes : ils ne sont pas des dependances externes.
    """
    stdlib = set(sys.stdlib_module_names)
    releve: dict[str, set[str]] = {}
    for fichier in fichiers:
        arbre = ast.parse(fichier.read_text(encoding="utf-8"), filename=str(fichier))
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Import):
                racines = [alias.name.split(".")[0] for alias in noeud.names]
            elif isinstance(noeud, ast.ImportFrom):
                if noeud.level != 0 or not noeud.module:
                    continue
                racines = [noeud.module.split(".")[0]]
            else:
                continue
            for racine in racines:
                if racine in stdlib or racine == "mixed_media_utility":
                    continue
                distribution = _nom_normalise(_nom_de_distribution(racine))
                chemin = str(fichier.relative_to(RACINE_DEPOT))
                releve.setdefault(distribution, set()).add(chemin)
    return releve


def _full_incomplet(extras: dict[str, set[str]]) -> list[str]:
    """Rend ce que `[full]` devrait porter et ne porte pas.

    Isole en fonction pure pour etre exerce sur echantillon : mesure sur
    l'arbre reel seul, l'assertion passe que la comparaison fonctionne ou non
    -- `[full]` y est complet. Meme famille de « vert a vide » que celle deja
    fermee sur les trois volets, retrouvee une troisieme fois en rejouant la
    campagne apres correction.
    """
    return sorted((extras.get("gui", set()) | extras.get("dev", set())) - extras.get("full", set()))


def _extras_pyproject() -> dict[str, set[str]]:
    """Rend tous les extras de `pyproject.toml`, normalises."""
    donnees = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    extras = donnees["project"].get("optional-dependencies", {})
    return {nom: {_nom_normalise(d) for d in liste} for nom, liste in extras.items()}


def _tables_pyproject() -> tuple[set[str], set[str]]:
    """Rend (dependances de base, dependances de l'extra `gui`), normalisees.

    Les deux ensembles sont exiges NON VIDES. Sans cette garde, un extra
    renomme (`[gui]` -> `[qt]`, refactor plausible depuis que l'extra ne porte
    plus que Qt) ou une cle mal orthographiee rendrait l'ensemble vide : le
    volet anti-rechute n'aurait plus rien a comparer et ne pourrait plus rougir
    -- sans rien dire. C'est la meme famille que le « vert a vide » deja
    corrige sur `_imports_tiers`, sur l'autre moitie du cablage.
    """
    donnees = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    base = {_nom_normalise(d) for d in donnees["project"]["dependencies"]}
    extras = _extras_pyproject()
    gui = extras.get("gui", set())
    if not base:
        raise AssertionError("[project].dependencies est vide : la frontiere ne mesure plus rien")
    if not gui:
        raise AssertionError(
            "l'extra [gui] est vide ou absent : le volet anti-rechute ne peut "
            "plus rougir. Extra renomme ? Corriger ce banc dans le meme geste."
        )
    return base, gui


def _dependances_de_mmu_tui() -> set[str]:
    """Les dependances de `packaging/mmu-tui/pyproject.toml`, normalisees.

    Exigee NON VIDE, comme les tables de la racine et pour le meme motif : une
    liste vide n'a plus rien a comparer, donc elle ne peut plus rougir -- et
    elle ne le dit pas.
    """
    donnees = tomllib.loads(PYPROJECT_TUI.read_text(encoding="utf-8"))
    declarees = {_nom_normalise(d) for d in donnees["project"]["dependencies"]}
    if not declarees:
        raise AssertionError(
            "[project].dependencies de mmu-tui est vide : la regle de zone ne "
            "mesure plus rien")
    return declarees


#: **`TUI_PRESENTE` et `DEPENDANCES_DU_SEUL_CHEMIN_TUI` ont ete RETIREES par la
#: story 8.5**, et il faut dire pourquoi plutot que les laisser disparaitre.
#:
#: Elles existaient parce que la TUI vivait sur une branche distincte : sans
#: `tui/`, `textual` et `rich` etaient declares dans `pyproject.toml` et
#: importes par personne, donc le volet « declare et non importe » les accusait
#: a tort. La soustraction etait NOMINATIVE plutot qu'un `skipif`, precisement
#: pour ne pas eteindre le volet en bloc (mesure de la revue de 8.4 : un
#: `skipif` laissait passer `ffmpeg-python`, le defaut meme que le volet
#: existe pour attraper).
#:
#: La scission de la story 8.5 supprime la cause : `textual` et `rich` ne sont
#: plus declares que par `mmu-tui`, qui vit dans le meme commit que `tui/`.
#: Ce qui remplace la soustraction est une frontiere plutot qu'une constante --
#: `test_le_sous_arbre_tui_et_sa_DECLARATION_vont_ensemble` ci-dessous : le
#: module et sa mesure partent ensemble, dans les deux sens.


# --------------------------------------------------------------------------
# La LOGIQUE d'accusation, isolee en fonctions pures.
#
# Motif, mesure : une campagne d'injection du 2026-08-30 a laisse survivre
# trois mutants qui neutralisaient les volets (« n'accuse jamais », « ne releve
# rien »). Ils survivaient parce que, sur un arbre CORRIGE, l'ensemble des
# fautifs est vide de toute facon : `assert not fautifs` passe que le
# detecteur fonctionne ou non. Un test qui ne peut plus echouer a cesse de
# mesurer sans le dire.
#
# Ces fonctions sont donc exercees DEUX fois : sur l'arbre reel (ou l'on exige
# zero fautif) et sur des echantillons de synthese (ou l'on exige que le fautif
# soit trouve). C'est le second usage qui tue les mutants.
# --------------------------------------------------------------------------


def _manquants(importes: dict[str, set[str]], declares: set[str]) -> dict[str, list[str]]:
    """Paquets importes qui ne figurent pas dans `declares`."""
    return {
        distribution: sorted(fichiers)
        for distribution, fichiers in importes.items()
        if distribution not in declares and distribution not in TOLERANCES_DECLARATION
    }


def _fuites(importes_hors_gui: dict[str, set[str]], extra_gui: set[str]) -> dict[str, list[str]]:
    """Paquets de l'extra `gui` importes hors du sous-arbre `gui/`."""
    return {
        distribution: sorted(fichiers)
        for distribution, fichiers in importes_hors_gui.items()
        if distribution in extra_gui
    }


def _mortes(declares: set[str], importes: set[str]) -> list[str]:
    """Paquets declares qu'aucun module n'importe."""
    return sorted(declares - importes - TOLERANCES_DECLARATION)


def _du_seul_chemin_tui(
    importes_par_tui: dict[str, set[str]], importes_ailleurs: dict[str, set[str]]
) -> dict[str, list[str]]:
    """Paquets tiers que `tui/` importe et que PERSONNE d'autre n'importe.

    Ce sont les seuls que `mmu-tui` doit declarer : un paquet importe des deux
    cotes (`jsonschema`, mesure du 2026-09-07) arrive par `mmu-cli`, dont
    `mmu-tui` depend, et le redeclarer serait la redondance meme que la
    scission refuse.
    """
    return {
        distribution: sorted(fichiers)
        for distribution, fichiers in importes_par_tui.items()
        if distribution not in importes_ailleurs
    }


def _hors_zone(du_seul_tui: set[str], declares_par_cli: set[str]) -> list[str]:
    """Paquets du SEUL chemin TUI que `mmu-cli` declare quand meme.

    La moitie NEGATIVE de la regle de zone -- celle qu'aucun test positif ne
    donne. Sans elle, `mmu-cli` pourrait redeclarer `textual` et rester vert :
    tous les volets positifs seraient satisfaits, et l'installation de la seule
    CLI paierait les 28 Mo de la TUI.
    """
    return sorted(du_seul_tui & declares_par_cli)


def test_tout_import_du_coeur_est_une_dependance_de_base():
    """Aucun module hors `gui/` n'importe un paquet absent de `dependencies`.

    C'est le sens qui mordait le 2026-08-30 : dix modules importaient `cv2`,
    declare seulement dans l'extra `[gui]`.
    """
    base, _ = _tables_pyproject()
    importes = _imports_tiers(_modules_python(inclure_gui=False, inclure_tui=False))

    manquants = _manquants(importes, base)

    assert not manquants, (
        "Paquets importes par le coeur (hors gui/) et absents de "
        "[project].dependencies :\n"
        + "\n".join(
            f"  {d} <- {', '.join(f[:3])}{' ...' if len(f) > 3 else ''}"
            for d, f in sorted(manquants.items())
        )
    )


def test_toute_dependance_de_base_est_importee():
    """Aucune dependance declaree ne reste sans un import qui la justifie.

    Sens inverse du precedent, et defaut symetrique du 2026-08-30 :
    `ffmpeg-python` etait declare et importe par aucun fichier -- le projet
    appelle le PROGRAMME ffmpeg par `subprocess`, jamais ce binding.
    """
    base, _ = _tables_pyproject()
    # La zone de `mmu-cli` : tout `src/` SAUF `tui/`. Un paquet que seul `tui/`
    # importerait ne justifierait pas une declaration ici -- c'est la moitie
    # negative de la regle de zone, mesuree a part.
    importes = set(_imports_tiers(_modules_python(inclure_gui=True, inclure_tui=False)))

    mortes = _mortes(base, importes)

    assert not mortes, (
        "Paquets declares dans [project].dependencies et importes par aucun "
        f"module de src/ : {', '.join(mortes)}"
    )


def test_les_paquets_de_l_extra_gui_ne_sortent_pas_de_gui():
    """Un paquet de l'extra `[gui]` n'est importe que sous `gui/`.

    Volet qui empeche la RECHUTE : si demain une dependance du coeur repart
    dans l'extra, ce test la rattrape, meme si le premier volet a ete
    contourne par un ajout dans `TOLERANCES_DECLARATION`.
    """
    _, gui = _tables_pyproject()
    hors_gui = _imports_tiers(_modules_python(inclure_gui=False))

    fuites = _fuites(hors_gui, gui)

    assert not fuites, (
        "Paquets de l'extra [gui] importes par des modules HORS de gui/ :\n"
        + "\n".join(
            f"  {d} <- {', '.join(f[:3])}{' ...' if len(f) > 3 else ''}"
            for d, f in sorted(fuites.items())
        )
    )


# --------------------------------------------------------------------------
# Story 8.5 -- la regle de ZONE entre les DEUX declarations (AC 6).
#
# Trois enonces, et il faut les trois : sans le premier une dependance du
# chemin TUI n'est declaree nulle part et `mmu-tui` s'installe casse ; sans le
# deuxieme elle est declaree DEUX fois et la CLI paie ce qu'elle n'utilise
# pas ; sans le troisieme une declaration survit a l'import qui la justifiait.
# --------------------------------------------------------------------------


def test_le_sous_arbre_tui_et_sa_DECLARATION_vont_ensemble():
    """Le module et sa mesure partent ENSEMBLE, dans les deux sens.

    C'est le geste de liaison de `CLAUDE.md` (« un module porte sans sa mesure
    et une mesure portee sans son module sont deux defauts symetriques »),
    applique au packaging. Il remplace la constante `TUI_PRESENTE` que la story
    8.4 portait : elle existait parce que `tui/` vivait sur une autre branche,
    et une soustraction nominative se perime en silence la ou une frontiere
    parle.
    """
    tui_present = (SOURCES / "tui").is_dir()
    declaration_presente = PYPROJECT_TUI.is_file()
    assert tui_present == declaration_presente, (
        f"src/mixed_media_utility/tui/ present : {tui_present} ; "
        f"{PYPROJECT_TUI.relative_to(RACINE_DEPOT)} present : "
        f"{declaration_presente}. Les deux voyagent ensemble.")


def test_les_ZONES_partitionnent_bien_src_sans_recouvrement_ni_trou():
    """La partition elle-meme, mesuree -- sans quoi la regle de zone est molle.

    Mutant `N11`, SURVIVANT a la premiere campagne du 2026-09-07 :
    `_modules_du_seul_chemin_tui` rendant TOUS les modules de `src/` laissait
    les 22 bancs verts. Il le pouvait parce que la difference d'ensembles
    rattrapait l'erreur sur l'arbre du jour -- mais un paquet importe par le
    SEUL `gui/` serait alors accepte comme une dependance legitime de
    `mmu-tui`, ce qui est exactement le defaut que la zone existe pour fermer.

    Trois enonces, et il faut les trois : les deux zones ne se recouvrent pas,
    elles ne laissent aucun module dehors, et aucune n'est vide (une zone vide
    rendrait sa moitie de la regle muette sans le dire).
    """
    tous = set(SOURCES.rglob("*.py"))
    zone_tui = set(_modules_du_seul_chemin_tui())
    zone_cli = set(_modules_python(inclure_gui=True, inclure_tui=False))

    assert zone_tui, "la zone tui/ est vide"
    assert zone_cli, "la zone mmu-cli est vide"
    assert not (zone_tui & zone_cli), sorted(zone_tui & zone_cli)[:5]
    assert zone_tui | zone_cli == tous, sorted(tous - (zone_tui | zone_cli))[:5]
    # Et la zone tui/ ne contient QUE des chemins tui/ : la difference
    # d'ensembles ci-dessus ne le dirait pas si les deux zones se decalaient
    # ensemble.
    hors = [f for f in zone_tui if "tui" not in f.relative_to(SOURCES).parts]
    assert not hors, hors[:5]


def test_tout_paquet_du_seul_chemin_TUI_est_declare_par_mmu_tui():
    """AC 6, sens positif. `mmu-tui` declare ce que `tui/` seul importe.

    Mesure du 2026-09-07 : `textual` et `rich`, et eux seuls. `jsonschema` est
    importe des deux cotes, il arrive donc par `mmu-cli` -- le redeclarer ici
    serait la redondance que la scission refuse.
    """
    du_seul_tui = _du_seul_chemin_tui(
        _imports_tiers(_modules_du_seul_chemin_tui()),
        _imports_tiers(_modules_python(inclure_gui=True, inclure_tui=False)),
    )

    manquants = _manquants(du_seul_tui, _dependances_de_mmu_tui())

    assert not manquants, (
        "Paquets importes par le SEUL chemin tui/ et absents des dependances "
        "de packaging/mmu-tui/pyproject.toml :\n"
        + "\n".join(
            f"  {d} <- {', '.join(f[:3])}{' ...' if len(f) > 3 else ''}"
            for d, f in sorted(manquants.items())
        )
    )


def test_aucun_paquet_du_seul_chemin_TUI_n_est_declare_par_mmu_cli():
    """AC 6 et AC 7, sens NEGATIF -- celui qu'aucun test positif ne donne.

    Une reintroduction de `textual` dans `mmu-cli` laisserait TOUS les volets
    positifs verts : le paquet serait declare, importe, non mort. Seule cette
    mesure-ci la voit, et ce qu'elle protege est chiffre -- 28 Mo (mesure du
    2026-09-07 : `mmu-cli` seule 305 Mo, les deux 333 Mo).

    Elle porte sur les EXTRAS aussi, pas seulement sur la base : c'est dans un
    extra qu'`opencv` avait ete mal range le 2026-08-30.
    """
    du_seul_tui = set(_du_seul_chemin_tui(
        _imports_tiers(_modules_du_seul_chemin_tui()),
        _imports_tiers(_modules_python(inclure_gui=True, inclure_tui=False)),
    ))
    base, _ = _tables_pyproject()
    extras = _extras_pyproject()
    declares_par_cli = base | set().union(*extras.values())

    fautifs = _hors_zone(du_seul_tui, declares_par_cli)

    assert not fautifs, (
        f"Paquets du SEUL chemin tui/ declares aussi par mmu-cli : {fautifs}. "
        "Qui n'installe que la CLI les telecharge sans jamais les importer.")


def test_toute_dependance_de_mmu_tui_est_importee_par_tui():
    """AC 6, troisieme enonce : rien de declare que personne n'importe.

    Sens inverse des deux precedents, et defaut deja paye sur l'autre
    declaration le 2026-08-30 (`ffmpeg-python`). `mmu-cli` est soustrait : ce
    n'est pas un paquet tiers mais l'arc INTERNE de la scission, mesure par
    `tests/unit/test_deux_distributions.py`.
    """
    declarees = _dependances_de_mmu_tui() - DISTRIBUTIONS_DU_DEPOT
    importes = set(_imports_tiers(_modules_du_seul_chemin_tui()))

    mortes = _mortes(declarees, importes)

    assert not mortes, (
        "Paquets declares par mmu-tui et importes par aucun module de tui/ : "
        f"{', '.join(mortes)}")


def test_l_arc_INTERNE_est_bien_soustrait_et_lui_seul():
    """La soustraction de `DISTRIBUTIONS_DU_DEPOT` est PORTANTE.

    Sans ce volet, la constante pourrait etre videe sans que rien ne bouge (le
    volet ci-dessus n'accuserait alors `mmu-cli` que si quelqu'un le declarait
    -- ce qui est le cas, mais un banc qui depend d'un etat pour mesurer une
    branche ne mesure rien). On exerce donc les deux regimes.
    """
    assert "mmu-cli" in _dependances_de_mmu_tui(), (
        "l'arc mmu-tui -> mmu-cli a disparu de la declaration")
    # Sans soustraction, l'arc interne serait accuse.
    brut = _mortes(_dependances_de_mmu_tui(),
                   set(_imports_tiers(_modules_du_seul_chemin_tui())))
    assert brut == ["mmu-cli"], brut
    # Et la soustraction ne retire QUE lui : `textual` reste mesure.
    assert _mortes({"mmu-cli", "textual", "paquet-fantome"} - DISTRIBUTIONS_DU_DEPOT,
                   {"textual"}) == ["paquet-fantome"]


def test_le_detecteur_de_zone_TUI_trouve_les_paquets_exclusifs():
    """`_du_seul_chemin_tui`, sur echantillon.

    Regle des fabriques : QUATRE paquets distinguables, les exclusifs ni en
    premiere position ni tous au milieu -- une cible a CHAQUE BORD, parce qu'un
    balayage tronque est un autre mode de panne qu'un `find` fautif.
    """
    par_tui = {
        "jsonschema": {"tui/a.py"},          # partage -- pas exclusif, en tete
        "textual": {"tui/b.py", "tui/c.py"},  # EXCLUSIF, au milieu
        "numpy": {"tui/d.py"},               # partage
        "rich": {"tui/e.py"},                # EXCLUSIF, en queue
    }
    ailleurs = {"jsonschema": {"coeur.py"}, "numpy": {"coeur.py"}, "cv2": {"coeur.py"}}

    exclusifs = _du_seul_chemin_tui(par_tui, ailleurs)

    assert sorted(exclusifs) == ["rich", "textual"], exclusifs
    # La provenance est rendue, et triee : sans elle le message de rouge est
    # inexploitable en revue.
    assert exclusifs["textual"] == ["tui/b.py", "tui/c.py"]
    # Symetrie : rien d'exclusif quand tout est partage.
    assert _du_seul_chemin_tui({"numpy": {"tui/a.py"}}, {"numpy": {"coeur.py"}}) == {}


def test_le_detecteur_de_hors_zone_accuse_bien_le_bon_paquet():
    """`_hors_zone`, sur echantillon : la moitie NEGATIVE de la regle.

    DEUX fautifs et non un -- avec un seul, un `_hors_zone` qui rendrait `[:1]`
    passait ; c'est le mutant qui a survecu deux fois sur les volets voisins de
    ce meme fichier (M3 et M4 de la revue de 8.4).
    """
    du_seul_tui = {"textual", "rich"}
    declares_par_cli = {"numpy", "rich", "pillow", "textual", "segno"}

    assert _hors_zone(du_seul_tui, declares_par_cli) == ["rich", "textual"]
    # Et rien a signaler quand la zone est respectee.
    assert _hors_zone(du_seul_tui, {"numpy", "pillow"}) == []


# --------------------------------------------------------------------------
# AC 9 -- aucun repli silencieux quand une dependance manque.
#
# Les dependances du chemin TUI etant desormais TOUTES obligatoires
# (EPIC8-ARB-1), un import qui echoue signale une installation cassee. Le
# rattraper en silence pour continuer en mode degrade transformerait une panne
# franche, lisible a la premiere seconde, en comportement partiel decouvert
# beaucoup plus tard -- et sur un traitement d'image, « partiel » veut dire un
# resultat faux plutot qu'une absence de resultat.
#
# Mesure du 2026-08-30 : zero repli de ce genre dans le coeur. Le banc n'est
# donc pas un correctif, c'est ce qui empeche le premier d'apparaitre.
# --------------------------------------------------------------------------


#: Noms d'exceptions dont un handler, pose autour d'un import, avale l'echec
#: d'import. `Exception` et `BaseException` en font partie : `ImportError` en
#: est une sous-classe, et c'est la forme la PLUS COURANTE du defaut -- celle
#: que la premiere version de ce banc ne voyait pas, et qui vivait deja dans le
#: coeur (`scan_ingest.py`, corrige par cette meme story).
EXCEPTIONS_QUI_AVALENT_UN_IMPORT = (
    "ImportError",
    "ModuleNotFoundError",
    "Exception",
    "BaseException",
)


def _handler_finit_par_lever(handler: ast.ExceptHandler) -> bool:
    """Vrai si le handler se termine par un `raise` a son PREMIER niveau.

    **Pourquoi la derniere instruction et non « un `raise` quelque part ».** La
    premiere version cherchait un `ast.Raise` n'importe ou sous `ast.walk`.
    Trois formes reelles y passaient pour conformes alors qu'elles se rabattent
    (mesurees en revue, couche 2) :

    * `def absent(): raise ...` puis `module = absent` -- le `raise` est dans une
      fonction, differe, et le module continue avec un bouchon ;
    * `module = None` puis `if STRICT: raise` -- le `raise` n'est sur qu'une
      branche ;
    * un `try/except` imbrique qui re-leve, suivi de `module = None`.

    Exiger que la DERNIERE instruction du handler soit un `raise` ferme les
    trois : quel que soit le chemin, on sort en levant.

    La direction de l'erreur est assumee : un handler qui se termine par un
    `sys.exit()` est accuse a tort. C'est le sens BRUYANT -- il se voit, se
    discute et se corrige --, alors que le sens silencieux laisse un mode
    degrade vivre dans le coeur.
    """
    return bool(handler.body) and isinstance(handler.body[-1], ast.Raise)


def _suppressions_d_import(arbre: ast.AST, origine: str) -> list[str]:
    """Rend les `with contextlib.suppress(...)` qui enveloppent un import.

    Forme invisible a l'analyse des `ast.Try` : ce n'est pas un noeud `Try`.
    Elle etale exactement le meme repli silencieux, en une ligne de moins.
    """
    fautifs: list[str] = []
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.With):
            continue
        enveloppe_un_import = any(
            isinstance(interne, (ast.Import, ast.ImportFrom))
            for instruction in noeud.body
            for interne in ast.walk(instruction)
        )
        if not enveloppe_un_import:
            continue
        for element in noeud.items:
            appel = element.context_expr
            if not isinstance(appel, ast.Call):
                continue
            nom = ast.unparse(appel.func)
            if not nom.endswith("suppress"):
                continue
            attrapes = {ast.unparse(a) for a in appel.args}
            if attrapes & set(EXCEPTIONS_QUI_AVALENT_UN_IMPORT):
                fautifs.append(f"{origine}:{noeud.lineno} (suppress {sorted(attrapes)})")
    return fautifs


def _replis_silencieux(arbre: ast.AST, origine: str) -> list[str]:
    """Rend les blocs qui avalent un echec d'import sans lever.

    Un handler qui re-leve (eventuellement avec un message plus clair) est
    CONFORME : la panne reste franche. Seul le bloc qui poursuit sans rien dire
    est fautif.
    """
    fautifs: list[str] = []
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Try):
            continue
        enveloppe_un_import = any(
            isinstance(interne, (ast.Import, ast.ImportFrom))
            for instruction in noeud.body
            for interne in ast.walk(instruction)
        )
        if not enveloppe_un_import:
            continue
        for handler in noeud.handlers:
            attrape = ast.unparse(handler.type) if handler.type else "except nu"
            vise_import = handler.type is None or any(
                nom in attrape for nom in EXCEPTIONS_QUI_AVALENT_UN_IMPORT
            )
            if not vise_import:
                continue
            if not _handler_finit_par_lever(handler):
                fautifs.append(f"{origine}:{noeud.lineno} ({attrape})")
    return fautifs + _suppressions_d_import(arbre, origine)


def test_le_detecteur_de_repli_distingue_bien_les_deux_formes():
    """Auto-verification du detecteur, avant de lui faire confiance sur l'arbre.

    Regle des fabriques (CLAUDE.md) : l'echantillon porte DEUX cas
    distinguables -- un conforme, un fautif -- et le fautif n'est PAS en
    premiere position. Un detecteur qui rendrait toujours le premier bloc, ou
    qui rendrait tout, passerait un echantillon a un seul cas.
    """
    echantillon = '''
try:
    import paquet_conforme
except ImportError as erreur:
    raise RuntimeError("paquet_conforme est requis") from erreur

try:
    import paquet_fautif
except ValueError:
    raise
except ImportError:
    paquet_fautif = None
'''
    fautifs = _replis_silencieux(ast.parse(echantillon), "echantillon")

    assert len(fautifs) == 1, f"le detecteur devait trouver un seul fautif, il rend {fautifs}"
    # Le fautif est le SECOND bloc de l'echantillon : un detecteur qui rendrait
    # le premier venu se trahit ici. Et DEUX handlers sur ce `try`, le fautif en
    # second : avec un seul, un detecteur qui ne lirait que `handlers[:1]`
    # passait -- mutant M8, survivant mesure en revue.
    assert "echantillon:7" in fautifs[0], fautifs


def test_le_detecteur_de_repli_voit_les_formes_voisines_du_repli_canonique():
    """Les quatre formes que la premiere version laissait passer.

    Mesurees en revue (couche 2). Chacune est un repli silencieux reel, et
    aucune n'etait vue : `except Exception` (la plus courante), le bouchon dont
    le `raise` est differe, le `raise` conditionnel, et `contextlib.suppress`
    -- qui n'est meme pas un noeud `ast.Try`.
    """
    formes = {
        "except Exception": "try:\n    import p\nexcept Exception:\n    p = None\n",
        "raise differe": (
            "try:\n    import p\nexcept ImportError:\n"
            "    def absent():\n        raise RuntimeError('x')\n    p = absent\n"
        ),
        "raise conditionnel": (
            "try:\n    import p\nexcept ImportError:\n"
            "    p = None\n    if STRICT:\n        raise\n"
        ),
        "suppress": "import contextlib\nwith contextlib.suppress(ImportError):\n    import p\n",
    }
    non_vus = [
        nom for nom, code in formes.items()
        if not _replis_silencieux(ast.parse(code), nom)
    ]
    assert not non_vus, f"formes de repli non detectees : {non_vus}"

    # Et la forme CONFORME reste conforme : un detecteur qui accuserait tout
    # passerait le test precedent sans rien mesurer.
    conforme = "try:\n    import p\nexcept ImportError as e:\n    raise RuntimeError('p requis') from e\n"
    assert _replis_silencieux(ast.parse(conforme), "conforme") == []


#: Les SONDES DE DIAGNOSTIC, tolerees nommement et pour un motif precis.
#:
#: Elles vivent toutes dans `tui/__main__.py`, dans le rapport d'environnement
#: qu'`--diagnostic` produit -- celui qu'Egan lance quand un glyphe ne s'affiche
#: pas sur son terminal Windows (2026-09-06). Trois raisons de les distinguer
#: d'un repli de coeur, et il faut les trois :
#:
#: 1. **elles ne rendent aucun service degrade.** Chacune rend un SENTINELLE --
#:    `None`, `""` -- que l'appelant interprete comme « je ne sais pas », et le
#:    rapport l'imprime tel quel. Le coeur ne calcule rien dessus ;
#: 2. **ce qu'elles importent n'est pas une dependance manquante.** `ctypes`
#:    est de la bibliotheque standard et son attribut `windll` n'existe QUE
#:    sous Windows ; `rich` est deja tire par `textual`. Lever y ferait
#:    echouer le diagnostic sur toute machine qui n'est pas Windows, ce qui est
#:    l'exact inverse de son but ;
#: 3. **un diagnostic doit repondre sur un environnement PARTIEL.** C'est sa
#:    definition : il est lance parce que quelque chose ne va pas.
#:
#: **Ce que cette tolerance ne couvre PAS** : un import de dependance dans un
#: chemin de production, meme dans ce fichier. Le registre nomme la LIGNE, pas
#: le module -- une quatrieme sonde ajoutee demain fera rougir la frontiere, et
#: c'est voulu : elle devra etre pesee comme ces trois l'ont ete.
#:
#: **DEUX DE PLUS AU 2026-09-07, ET LA FRONTIERE A FAIT EXACTEMENT CE QUE CE
#: PARAGRAPHE ANNONCAIT.** La liaison de l'Epic 11 a apporte l'explorateur de
#: fichiers, avec deux sondes de CAPACITE -- pas de diagnostic, d'ou l'ajout au
#: nom de cette liste. Elles ont ete pesees contre les trois criteres :
#:
#: * `explorateur._volumes_windows` -- importe `ctypes` pour lire
#:   `windll.kernel32.GetLogicalDrives`, dont l'attribut `windll` n'existe QUE
#:   sous Windows. Rend `None`, sentinelle que l'appelant lit « je n'ai pas pu
#:   regarder » et non « aucun volume ». Les trois criteres tiennent tels
#:   quels, et lever ferait echouer l'explorateur sur tout poste non-Windows ;
#: * `explorateur._nom_de_compte` -- importe `getpass` (bibliotheque standard).
#:   Rend `""`. **Il ne passait PAS le troisieme critere** : ce n'est pas un
#:   diagnostic, c'est un chemin de production, et son `except Exception`
#:   avalait en plus tout defaut de programmation de sa propre ligne. Il a donc
#:   ete RESSERRE aux trois levees reelles avant d'etre tolere --
#:   `ImportError` (`pwd` absent sous Windows), `KeyError` (uid sans entree
#:   `passwd` : mesure, c'est ce que rend un conteneur), `OSError`. La
#:   tolerance porte sur un import de la bibliotheque standard, jamais sur une
#:   dependance.
SONDES_DE_DIAGNOSTIC_TOLEREES = (
    ("src/mixed_media_utility/tui/__main__.py", "_legacy_windows"),
    ("src/mixed_media_utility/tui/__main__.py", "_page_de_code"),
    ("src/mixed_media_utility/tui/__main__.py", "_police_de_la_console"),
    ("src/mixed_media_utility/tui/explorateur.py", "_volumes_windows"),
    ("src/mixed_media_utility/tui/explorateur.py", "_nom_de_compte"),
)


def _fonction_englobante(arbre: ast.AST, ligne: int) -> str:
    """Le nom de la fonction qui contient cette ligne, ou `""`.

    La tolerance porte sur une FONCTION et non sur un numero de ligne : un
    registre indexe par ligne rougirait a chaque insertion au-dessus, et un
    registre qu'on reajuste sans le lire cesse d'etre lu.
    """
    meilleure = ""
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        fin = getattr(noeud, "end_lineno", noeud.lineno)
        if noeud.lineno <= ligne <= fin:
            meilleure = noeud.name
    return meilleure


def _replis_du_depot() -> list[tuple[str, str, str]]:
    """`(fichier, fonction, repli)` pour chaque repli silencieux hors `gui/`."""
    trouves: list[tuple[str, str, str]] = []
    for fichier in _modules_python(inclure_gui=False):
        arbre = ast.parse(fichier.read_text(encoding="utf-8"),
                          filename=str(fichier))
        relatif = str(fichier.relative_to(RACINE_DEPOT))
        for repli in _replis_silencieux(arbre, relatif):
            ligne = int(repli.split(":")[1].split(" ")[0])
            trouves.append((relatif, _fonction_englobante(arbre, ligne), repli))
    return trouves


def test_le_coeur_ne_se_rabat_jamais_en_silence_sur_une_dependance_absente():
    """Aucun module hors `gui/` ne poursuit en silence apres un import rate."""
    tolerees = set(SONDES_DE_DIAGNOSTIC_TOLEREES)
    fautifs = [repli for fichier, fonction, repli in _replis_du_depot()
               if (fichier, fonction) not in tolerees]

    assert not fautifs, (
        "Replis silencieux sur un import manquant (la panne doit rester "
        "franche et nommer le paquet) :\n  " + "\n  ".join(fautifs)
    )


def test_la_TOLERANCE_des_sondes_de_diagnostic_est_PORTANTE():
    """Volet symetrique -- une tolerance perimee rend la frontiere aveugle.

    Elle le serait deux fois : le volet ci-dessus resterait vert sans plus rien
    ecarter, et une sonde NEUVE qui reprendrait le nom d'une sonde retiree
    entrerait sans etre pesee. On mesure donc les deux sens : chaque entree
    vit, et l'ensemble des replis du depot est EXACTEMENT le declare.
    """
    releves = {(fichier, fonction) for fichier, fonction, _ in _replis_du_depot()}
    assert releves == set(SONDES_DE_DIAGNOSTIC_TOLEREES), (
        "l'ensemble des replis silencieux du depot n'est plus exactement le "
        f"declare -- releves : {sorted(releves)}")


# --------------------------------------------------------------------------
# Auto-verification des trois volets, sur echantillons de synthese.
#
# Regle des fabriques (CLAUDE.md) appliquee a la lettre : chaque echantillon
# porte AU MOINS DEUX paquets distinguables -- jamais un remplissage uniforme,
# une permutation ne se voyant que si les elements different -- et le paquet
# FAUTIF n'est jamais en premiere position, faute de quoi un detecteur qui
# rendrait toujours le premier element passerait sans se trahir.
# --------------------------------------------------------------------------


def test_le_volet_importe_non_declare_accuse_bien_le_bon_paquet():
    """`_manquants` trouve le paquet non declare, et lui seul."""
    importes = {
        "numpy": {"a.py"},                    # declare -- conforme
        "opencv-contrib-python": {"b.py", "c.py"},  # FAUTIF, en 2e position
        "pillow": {"d.py"},                   # declare -- conforme
    }
    declares = {"numpy", "pillow"}

    manquants = _manquants(importes, declares)

    assert list(manquants) == ["opencv-contrib-python"], manquants
    # Les fichiers accusateurs sont rendus, et tries : un detecteur qui
    # perdrait la provenance rendrait un message inexploitable en revue.
    assert manquants["opencv-contrib-python"] == ["b.py", "c.py"]


def test_le_volet_declare_non_importe_accuse_bien_le_bon_paquet():
    """`_mortes` trouve TOUTES les dependances mortes, pas seulement la premiere.

    DEUX paquets morts et non un : avec un seul, un `_mortes` qui rendrait
    `[:1]` passait -- mutant M3, survivant mesure en revue. Et les deux morts
    encadrent un vivant, pour qu'un decoupage naif de la liste se trahisse.
    """
    declares = {"numpy", "ffmpeg-python", "pillow", "paquet-fantome"}
    importes = {"numpy", "pillow"}

    assert _mortes(declares, importes) == ["ffmpeg-python", "paquet-fantome"]
    # Symetrie : rien de mort quand tout est importe.
    assert _mortes(declares, declares) == []


def test_le_volet_anti_rechute_accuse_un_paquet_gui_sorti_de_gui():
    """`_fuites` trouve le paquet de l'extra `gui` importe hors de `gui/`."""
    importes_hors_gui = {
        "numpy": {"coeur_a.py"},                       # pas dans l'extra
        "pyside6": {"coeur_b.py", "coeur_d.py"},       # FAUTIF, en 2e position
        "jsonschema": {"coeur_c.py"},                  # pas dans l'extra
    }
    extra_gui = {"pyside6", "pytest-qt"}

    fuites = _fuites(importes_hors_gui, extra_gui)

    assert list(fuites) == ["pyside6"], fuites
    # DEUX fichiers accusateurs et non un : avec un seul, un `_fuites` qui
    # rendrait `sorted(fichiers)[:1]` passait -- mutant M4, survivant mesure en
    # revue. L'asymetrie etait mesurable entre deux fabriques de la meme story :
    # le volet « importe non declare » en avait deux et tuait son mutant.
    assert fuites["pyside6"] == ["coeur_b.py", "coeur_d.py"]
    # pytest-qt est dans l'extra mais importe par personne hors gui/ : il ne
    # doit PAS etre accuse. Un volet qui rendrait tout l'extra echouerait ici.
    assert "pytest-qt" not in fuites


def test_le_releve_d_imports_n_est_pas_vide_sur_l_arbre_reel():
    """Garde du « vert a vide » : le releve trouve reellement des paquets.

    Sans ce banc, un `_imports_tiers` qui rendrait toujours un dictionnaire
    vide ferait passer les trois volets au vert -- ils n'auraient plus rien a
    accuser. C'est le mutant M2 du 2026-08-30, survivant jusqu'ici.
    """
    importes = _imports_tiers(_modules_python(inclure_gui=False))

    assert importes, "le releve d'imports du coeur est vide : il a cesse de mesurer"
    # Deux paquets distinguables, presents quel que soit l'etat de la branche
    # (ils ne dependent pas de la presence de tui/). `cv2` est desormais rendu
    # par `opencv-python-headless` (EPIC11-ARB-253, story 8.5) : la correspondance
    # nom d'import -> nom de distribution a change, pas le releve.
    assert "numpy" in importes
    assert "opencv-python-headless" in importes


def test_la_constante_de_tolerance_a_bien_un_effet_quand_elle_n_est_pas_vide():
    """`TOLERANCES_DECLARATION` est exercee NON VIDE, sur les deux volets.

    Elle vaut `frozenset()` aujourd'hui, et c'est bien : aucune tolerance n'est
    accordee. Mais tant qu'aucun test ne l'exerce remplie, les deux branches qui
    la lisent sont INERTES -- les retirer laissait la suite verte (mutants M1 et
    M2, survivants mesures en revue). Le banc verifie donc ce que la constante
    fait quand on s'en sert, sans rien tolerer pour de vrai.

    Point 3 de la checklist des fabriques : la variante non-mono-element de la
    fabrique existe, et elle est ecrite dans la meme story.
    """
    importes = {"paquet-tolere": {"a.py"}, "paquet-fautif": {"b.py"}}
    declares = {"numpy"}

    # Sans tolerance : les deux sont accuses.
    assert sorted(_manquants(importes, declares)) == ["paquet-fautif", "paquet-tolere"]

    # Avec tolerance sur le premier : lui seul disparait, l'autre reste accuse.
    with mock.patch.object(
        sys.modules[__name__], "TOLERANCES_DECLARATION", frozenset({"paquet-tolere"})
    ):
        restants = _manquants(importes, declares)
    assert list(restants) == ["paquet-fautif"], restants

    # Meme geste sur le volet symetrique.
    assert _mortes({"mort-a", "mort-b"}, set()) == ["mort-a", "mort-b"]
    with mock.patch.object(
        sys.modules[__name__], "TOLERANCES_DECLARATION", frozenset({"mort-a"})
    ):
        assert _mortes({"mort-a", "mort-b"}, set()) == ["mort-b"]


def test_l_extra_full_reste_l_union_de_gui_et_dev():
    """`[full]` ne peut pas diverger de `[gui]` sans qu'on le voie.

    Les notes de developpement de la story designent nommement cette
    duplication comme « piege deja paye » : corriger `[gui]` sans corriger
    `[full]` laisse le defaut vivant sur un chemin. La correction a bien ete
    faite a la main -- mais rien n'empechait la rechute que la note annonce, et
    un `PySide6-Addons` ajoute au seul `[gui]` passait (mesure en revue).
    """
    extras = _extras_pyproject()
    for nom in ("gui", "dev", "full"):
        assert nom in extras, f"extra [{nom}] absent de pyproject.toml"

    manquants = _full_incomplet(extras)
    assert not manquants, (
        "l'extra [full] ne couvre plus [gui] union [dev] : "
        f"{sorted(manquants)} y manque(nt)"
    )


def test_le_nom_de_distribution_se_normalise_sur_toutes_les_formes_pep_508():
    """`_nom_normalise` sur les formes reelles, dont la reference directe.

    Mesure de la revue : sans la coupure sur `@`,
    `pypdfium2@https://.../p.whl` se normalisait en un nom qui ne correspond a
    aucun import -- le volet anti-rechute devenait AVEUGLE en silence, et une
    suite entierement verte pouvait cohabiter avec un coeur important Qt. La
    forme est activee par decision dans ce depot
    (`[tool.hatch.metadata] allow-direct-references = true`).

    DEUX formes a `@` distinguables, et la fautive n'est pas en premiere
    position (regle des fabriques).
    """
    attendus = {
        "numpy>=2.0": "numpy",
        "opencv_contrib_python>=4.10,<6": "opencv-contrib-python",
        "Pillow": "pillow",
        "PySide6@https://example.com/pyside6-6.8.whl": "pyside6",
        "pytest-qt >= 4.4 ; python_version >= '3.11'": "pytest-qt",
        "pypdfium2 @ https://example.com/p.whl": "pypdfium2",
        "paquet[extra]>=1": "paquet",
    }
    obtenus = {brut: _nom_normalise(brut) for brut in attendus}
    assert obtenus == attendus

    # Un nom vide ne se rend jamais en silence : il comparerait des ensembles
    # qui ne se rencontrent jamais, donc ferait taire les trois volets.
    for degenere in ("@https://example.com/p.whl", ">=1.0", "   "):
        with pytest.raises(ValueError):
            _nom_normalise(degenere)


def test_le_volet_full_accuse_bien_ce_qui_lui_manque():
    """`_full_incomplet` trouve ce que `[full]` ne couvre pas, et rien d'autre.

    DEUX paquets manquants, encadrant un present : un detecteur qui rendrait le
    premier venu, ou l'ensemble vide, se trahit ici.
    """
    extras = {
        "gui": {"pyside6", "pytest-qt", "paquet-oublie-a"},
        "dev": {"mutmut", "pytest", "paquet-oublie-b"},
        "full": {"pyside6", "pytest-qt", "mutmut", "pytest"},
    }
    assert _full_incomplet(extras) == ["paquet-oublie-a", "paquet-oublie-b"]

    # Et rien a signaler quand [full] couvre tout.
    complet = dict(extras, full=extras["gui"] | extras["dev"])
    assert _full_incomplet(complet) == []


def test_aucune_dependance_de_BASE_n_exige_de_bibliotheque_systeme_graphique():
    """FRONTIERE NEGATIVE : le livrable doit s'importer sur une machine VIERGE.

    Le brief d'Egan du 2026-09-06 : « pip et le script one-liner doivent livrer
    uniquement la TUI fonctionnelle sur un ordinateur totalement vierge n'ayant
    rien installe comme prerequis ».

    Ce que ce banc empeche de revenir, et ce n'est pas une question de poids :
    `opencv-python` et `opencv-contrib-python` lient leur `cv2.abi3.so` a douze
    bibliotheques systeme de plus que la roue headless -- `libGL.so.1`,
    `libX11.so.6`, `libglib-2.0.so.0`... Sur un serveur nu, un conteneur
    minimal ou un WSL sans X, `import cv2` echoue sur `ImportError: libGL.so.1`
    AVANT la premiere ligne du produit. Le script d'installation n'installe pas
    ces bibliotheques, et il ne doit pas avoir a le faire.

    La frontiere est NEGATIVE parce qu'aucun test positif ne la verrait : sur la
    machine de developpement, ou libGL est present, les deux roues marchent
    exactement pareil. Le defaut ne se voit que chez l'utilisateur.

    L'extra `[gui]` n'est PAS concerne : il installe Qt, donc il suppose deja
    un affichage. La contrainte porte sur la base seule.
    """
    base, _ = _tables_pyproject()
    fautives = base & ROUES_OPENCV_QUI_EXIGENT_UN_AFFICHAGE
    assert not fautives, (
        f"dependance(s) de base exigeant un affichage : {sorted(fautives)}. "
        "Prendre la roue 'headless' correspondante : la TUI n'ouvre aucune "
        "fenetre OpenCV, seule la lecture previz le fait et elle refuse "
        "proprement quand la roue ne sait pas afficher."
    )


def test_la_frontiere_des_roues_graphiques_MORD_bien(monkeypatch):
    """Le pendant positif : la frontiere ci-dessus rougit-elle vraiment ?

    Une frontiere negative qui ne mord pas est pire qu'une frontiere absente :
    elle donne la tranquillite sans la garantie. On lui presente donc le cas
    qu'elle doit attraper -- la roue non-headless remise en base -- et on
    verifie qu'elle le nomme.
    """
    for roue in ROUES_OPENCV_QUI_EXIGENT_UN_AFFICHAGE:
        base = {"numpy", "pillow", roue}
        fautives = base & ROUES_OPENCV_QUI_EXIGENT_UN_AFFICHAGE
        assert fautives == {roue}, roue


# --------------------------------------------------------------------------
# Un GREFFON qui exige une liaison ne s'installe jamais seul (2026-09-08).
#
# Pose apres le PREMIER run de CI reel du projet (34196288009), ou les trois
# jobs de test sont morts en moins d'une seconde, ZERO test collecte sur
# 18 747 :
#
#     ERROR: pytest-qt requires either PySide6, PyQt5 or PyQt6 installed.
#     Process completed with exit code 4.
#
# Les extras `dev` et `test` declaraient `pytest-qt` sans aucune liaison Qt.
# Ce n'est pas une declaration incomplete au sens ordinaire -- une dependance
# manquante fait echouer les tests qui l'emploient. Ici le greffon refuse de
# se CHARGER, donc pytest s'arrete avant la collecte et la suite entiere
# disparait. Une mesure qui ne tourne pas ne rougit pas : elle se tait.
#
# Ce que cette frontiere mesure, et pourquoi elle est du cote DECLARATION :
# aucune execution de la suite ne peut l'attraper, puisque l'incoherence tue
# precisement l'executeur. Elle se lit dans le fichier ou elle est ecrite.
# --------------------------------------------------------------------------

#: Greffons qui refusent de se charger sans une liaison, et la liaison qu'ils
#: acceptent. Le releve vient du message d'erreur de `pytest-qt` lui-meme.
GREFFONS_QUI_EXIGENT_UNE_LIAISON = {
    "pytest-qt": {"pyside6", "pyside6-essentials", "pyqt5", "pyqt6"},
}


def test_aucun_extra_ne_declare_un_GREFFON_sans_sa_LIAISON():
    """Tout extra qui porte `pytest-qt` porte aussi une liaison Qt.

    La regle vaut EXTRA PAR EXTRA et non sur leur union : `pip install .[test]`
    n'installe que `test`, et c'est exactement ce que fait la CI.
    """
    extras = _extras_pyproject()

    fautifs = {
        nom: greffon
        for nom, paquets in extras.items()
        for greffon, liaisons in GREFFONS_QUI_EXIGENT_UNE_LIAISON.items()
        if _nom_normalise(greffon) in paquets and not (paquets & liaisons)
    }

    assert not fautifs, (
        "Extra(s) declarant un greffon qui refuse de se charger sans liaison, "
        "sans declarer cette liaison -- pytest s'arretera avec exit 4 AVANT "
        "toute collecte :\n"
        + "\n".join(f"  [{nom}] declare {greffon}" for nom, greffon in sorted(fautifs.items()))
        + "\nSoit retirer le greffon de l'extra, soit y ajouter la liaison."
    )


def test_le_releve_des_extras_n_est_pas_vide_et_VOIT_l_appariement_reel():
    """Volet d'ANTI-VACUITE : sans lui, le test ci-dessus passe sur rien.

    Il exige les deux moities de la mesure : que des extras existent, et
    qu'au moins un d'entre eux apparie REELLEMENT le greffon a sa liaison --
    sinon un depot qui aurait retire `pytest-qt` de partout rendrait le
    premier test vert sans que l'appariement soit tenu nulle part.
    """
    extras = _extras_pyproject()
    assert extras, "aucun extra lu dans pyproject.toml"

    greffon = _nom_normalise("pytest-qt")
    liaisons = GREFFONS_QUI_EXIGENT_UNE_LIAISON["pytest-qt"]
    apparies = [nom for nom, paquets in extras.items() if greffon in paquets and (paquets & liaisons)]

    assert apparies, (
        "aucun extra n'apparie pytest-qt a une liaison Qt : la frontiere "
        "ci-dessus ne mesure plus rien"
    )


@pytest.mark.parametrize(
    "extra_fabrique",
    [
        pytest.param({"pytest-qt": None}, id="greffon-seul"),
        pytest.param({"pytest-qt": None, "pytest": None}, id="greffon-avec-pytest-mais-sans-liaison"),
    ],
)
def test_la_frontiere_du_greffon_MORD_sur_un_extra_FABRIQUE(extra_fabrique):
    """Volet SYMETRIQUE : le critere accuse bien un extra depareille.

    Sans ce volet, un critere qui ne trouverait jamais rien -- une faute de
    frappe dans le nom du greffon, par exemple -- serait vert pour toujours.
    """
    paquets = {_nom_normalise(nom) for nom in extra_fabrique}
    liaisons = GREFFONS_QUI_EXIGENT_UNE_LIAISON["pytest-qt"]

    assert _nom_normalise("pytest-qt") in paquets
    assert not (paquets & liaisons), "l'extra fabrique ne doit porter AUCUNE liaison"


def test_la_frontiere_du_greffon_NE_MORD_PAS_sur_un_extra_APPARIE():
    """Volet symetrique inverse : un extra correct n'est pas accuse."""
    paquets = {_nom_normalise(n) for n in ("pytest-qt", "PySide6-Essentials>=6.8,<6.9")}
    liaisons = GREFFONS_QUI_EXIGENT_UNE_LIAISON["pytest-qt"]

    assert _nom_normalise("pytest-qt") in paquets
    assert paquets & liaisons, "PySide6-Essentials doit compter comme liaison"
