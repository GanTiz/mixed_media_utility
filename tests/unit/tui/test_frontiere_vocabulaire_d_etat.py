# -*- coding: utf-8 -*-
"""Story 11.8, lot B2 (AC 3.4) -- aucun etat de lot n'est REJUGE dans `tui/`.

**Le defaut que cette frontiere ferme, et il etait livre.**
`tui/projet_lecture.py` portait `ETATS_RECONSTRUITS = ("reconstruction",
"encode")` et decidait sur cette table si un lot etait encodable. Le coeur, lui,
decide sur `check_lot_admission` : etat au moins `MINIMUM_LOT_STATE`, **et**
`output_frames_dir` declare, **et** dossier present. Les deux definitions ne se
recouvrent pas -- elles se **croisent** --, et l'ecart jouait dans les deux sens :
l'entree `Exports` se fermait sur un lot `scan` qu'`mmu encode` encode, et
s'ouvrait sur un lot `reconstruction` recree depuis des payloads que le coeur
refuse par `ENCODE_OUTPUT_DIR_NOT_DECLARED`.

Retirer la table ne suffit pas : rien n'empecherait de la reecrire demain, sous
un autre nom ou en ligne. C'est `EPIC11-ARB-30` -- « la TUI n'ecrit aucun
jugement metier que le coeur ne porte pas » -- et une consigne ne se mesure pas.

**Ce que la frontiere mesure, et c'est une FORME, pas un mot.** Deux ecritures
sont interdites dans tout le paquet `tui/` :

1. une **collection litterale** dont un element est un etat de lot --
   `("reconstruction", "encode")`, la forme exacte du defaut ;
2. une **comparaison** contre un etat de lot litteral -- `state == "encode"`,
   `state in ("scan", "encode")`.

Les deux sont mesurees a l'**AST**, jamais au texte : la docstring de ce module
et celle de `projet_lecture` nomment les etats pour expliquer ce qu'elles ne
font pas ; un grep y mordrait et se ferait affaiblir a la premiere prose
(defaut mesure a l'ecriture de la story 11.0 sur `tui/jetons.py`).

**Ce qu'elle NE mesure PAS, dit plutot que tu.**

* un etat de lot passe en **argument** d'un appel -- `_lots_arrives_a(lots,
  "pdf")` dans `projets.py`. Cet appel ne juge pas : il demande au coeur
  combien de lots ont atteint un etat, sur la machine `ETATS_DE_LOT` qui **est**
  `io.manifest.LOT_STATES`. Tolerance deliberee, et mesuree ci-dessous pour
  qu'elle reste visible ;
* un **homonyme** -- `CHAMP_SCAN = "scan"` dans `atelier_scan_calibrate.py` est
  un identifiant de champ de formulaire, pas un etat de lot. Aucune analyse
  syntaxique ne les distingue, et c'est la raison pour laquelle la frontiere
  porte sur la **forme du jugement** et non sur la presence du mot ;
* une table reconstruite sans litteral -- `LOT_STATES[3:]`. Elle resterait
  invisible ici, comme la frontiere des politiques de `CLAUDE.md` reste aveugle
  a une regle sans identifiant. C'est le prix d'une mesure syntaxique, et il se
  dit.

**Le volet symetrique est obligatoire** : la meme mesure appliquee a un module
fabrique qui viole la regle DOIT mordre, forme par forme. Sans lui, une garde
qui ne regarderait plus rien serait verte -- le seul mode de panne qu'une
frontiere negative ne voit pas d'elle-meme.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

_RACINE = Path(__file__).resolve().parents[3]
_SRC = str(_RACINE / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mixed_media_utility.io.manifest import LOT_STATES  # noqa: E402
from mixed_media_utility.tui import projet_lecture  # noqa: E402

#: Le paquet mesure, entier. Pas un module nomme : le defaut de la 11.8 vivait
#: dans `projet_lecture`, le suivant vivra ailleurs.
PAQUET_TUI = _RACINE / "src" / "mixed_media_utility" / "tui"

#: Le nom de la table retiree par cette story. Mesure **nominale**, et elle est
#: assumee comme telle : elle ferme la reintroduction a l'identique -- y compris
#: par une comprehension, que la mesure de forme ne verrait pas --, pas une
#: table qui prendrait un autre nom.
TABLE_RETIREE = "ETATS_RECONSTRUITS"


def _est_un_etat(noeud: ast.AST) -> bool:
    return (isinstance(noeud, ast.Constant) and isinstance(noeud.value, str)
            and noeud.value in LOT_STATES)


def sites_de_jugement_d_etat(source: str, nom: str = "<source>") -> list[str]:
    """Les endroits ou ce source **juge** un etat de lot en litteral.

    Rend une ligne par site, nommant la ligne et la forme trouvee -- un rouge
    doit dire ou regarder, pas seulement qu'il y a quelque chose.
    """
    arbre = ast.parse(source, filename=nom)
    sites: list[str] = []
    for noeud in ast.walk(arbre):
        if isinstance(noeud, (ast.Tuple, ast.List, ast.Set)):
            etats = [element.value for element in noeud.elts
                     if _est_un_etat(element)]
            if etats:
                sites.append(f"{nom}:{noeud.lineno} collection d'etats {etats}")
        elif isinstance(noeud, ast.Compare):
            etats = [comp.value for comp in noeud.comparators
                     if _est_un_etat(comp)]
            if etats:
                sites.append(f"{nom}:{noeud.lineno} comparaison a {etats}")
    return sites


def sites_du_fichier(chemin: Path) -> list[str]:
    return sites_de_jugement_d_etat(chemin.read_text(encoding="utf-8"),
                                    chemin.name)


def modules_de_la_tui() -> list[Path]:
    return sorted(PAQUET_TUI.rglob("*.py"))


# ---------------------------------------------------------------------------
# La frontiere
# ---------------------------------------------------------------------------

def test_le_paquet_tui_ne_juge_AUCUN_etat_de_lot():
    """AC 3.4. **Tolerance zero**, et le balayage porte sur le paquet entier.

    Une liste d'exceptions serait le premier pas vers une seconde redaction du
    critere : le jour ou elle en porterait une, plus personne ne saurait dire si
    la TUI juge ou lit.
    """
    trouves = [site for chemin in modules_de_la_tui()
               for site in sites_du_fichier(chemin)]
    assert trouves == [], trouves


def test_le_balayage_a_bien_VU_le_paquet():
    """Volet du volet : une frontiere qui ne lirait aucun fichier serait verte.

    Le cardinal est compare a un **plancher** et non a une valeur exacte : le
    paquet grandit a chaque story, et une egalite ferait rougir la frontiere
    pour une raison qui n'est pas la sienne.
    """
    modules = modules_de_la_tui()
    assert len(modules) >= 30, [m.name for m in modules]
    assert any(m.name == "projet_lecture.py" for m in modules)


@pytest.mark.parametrize("forme,source", [
    ("la table retiree, a l'identique",
     'ETATS_RECONSTRUITS = ("reconstruction", "encode")\n'),
    ("la meme table sous un autre nom",
     'ENCODABLES = ["scan", "reconstruction"]\n'),
    ("un ensemble",
     'ENCODABLES = {"encode"}\n'),
    ("une appartenance en ligne",
     'def f(lot):\n    return lot.get("state") in ("reconstruction", "encode")\n'),
    ("une egalite en ligne",
     'def f(lot):\n    return lot.get("state") == "reconstruction"\n'),
])
def test_la_frontiere_MORD_sur_chaque_forme_du_defaut(forme, source):
    """**Volet symetrique**, une entree par forme interdite.

    L'egalite en ligne est celle qui compte le plus : c'est la reecriture la
    moins visible du critere, et celle qu'une frontiere ecrite sur le seul nom
    `ETATS_RECONSTRUITS` laisserait passer.
    """
    assert sites_de_jugement_d_etat(source), forme


@pytest.mark.parametrize("forme,source", [
    ("un etat passe en argument",
     'compte = _lots_arrives_a(lots, "pdf")\n'),
    ("une comparaison contre le vocabulaire du coeur",
     'def f(lot):\n    return lot.get("state") in ETATS_DE_LOT\n'),
    ("un homonyme qui n'est pas un etat de lot",
     'CHAMP_SCAN = "scan"\n'),
    ("une prose qui nomme les etats",
     '"""On ne compare jamais a "reconstruction" ni a "encode"."""\n'),
])
def test_la_frontiere_ne_mord_PAS_sur_ce_qu_elle_tolere(forme, source):
    """Les quatre tolerances, **ecrites** plutot que subies.

    Sans ce volet, un resserrement futur de la mesure ferait rougir des sites
    legitimes du depot sans que rien ne dise qu'ils l'etaient. La derniere
    entree est la raison pour laquelle la mesure est un AST et non un grep : ce
    source ne porte que de la prose.
    """
    assert sites_de_jugement_d_etat(source) == [], forme


# ---------------------------------------------------------------------------
# La table retiree, nommement
# ---------------------------------------------------------------------------

def test_la_table_ETATS_RECONSTRUITS_a_DISPARU():
    """AC 3.4, litteralement. Ni attribut de module, ni export."""
    assert not hasattr(projet_lecture, TABLE_RETIREE)
    assert TABLE_RETIREE not in projet_lecture.__all__


def test_AUCUN_module_de_la_tui_ne_reintroduit_ce_NOM():
    """La mesure de forme ne verrait pas `ETATS_RECONSTRUITS = LOT_STATES[3:]`.

    Celle-ci si -- elle porte sur la **cible d'affectation**, quelle que soit
    l'expression affectee. Les deux mesures sont complementaires, et aucune ne
    couvre l'autre.
    """
    coupables = []
    for chemin in modules_de_la_tui():
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            cibles = (noeud.targets if isinstance(noeud, ast.Assign)
                      else [noeud.target] if isinstance(noeud, ast.AnnAssign)
                      else [])
            for cible in cibles:
                if isinstance(cible, ast.Name) and cible.id == TABLE_RETIREE:
                    coupables.append(f"{chemin.name}:{noeud.lineno}")
    assert coupables == [], coupables
