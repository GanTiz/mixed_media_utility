# -*- coding: utf-8 -*-
"""Reconnaitre DANS QUEL DEPOT on tourne, en le mesurant plutot qu'en le declarant.

**Le probleme qu'il ferme, et il a ete chiffre.** Douze bancs de ce depot
gardent le perimetre de leur story en comparant l'arbre a un COMMIT DE
REFERENCE ecrit en dur (`_BASELINE_5_28 = "16f8fb3"`, et treize autres). Devant
un commit inatteignable, ils appellent `pytest.fail` DELIBEREMENT, avec un
motif ecrit dans leur code : « un skip se lirait comme un vert ». Ce motif est
juste -- pour un clone TRONQUE, ou le remede est `git fetch --unshallow`.

Il ne l'est plus pour le depot PUBLIC, dont l'historique est ORPHELIN par
arbitrage (`EPIC8-ARB-12`) : ces commits n'y existeront JAMAIS, et aucun
`fetch` ne les y fera apparaitre. Mesure du 2026-09-08 sur l'orphelin reel :
**27 rouges** de cette seule famille, et `pytest tests/unit -x` mourant au
premier -- donc la porte `valider` de `publish.yml` avec elle, donc aucune
publication.

**Deux etages, et le second est arrive apres le premier.** Les trois premieres
fonctions ne font sauter aucun banc : elles rendent une mesure, et l'appelant
decide. :func:`echoue_ou_saute`, elle, TRANCHE -- et elle a ete ajoutee le
2026-09-08 parce que la premiere redaction laissait la decision a sept sites
qui l'auraient prise sept fois differemment, ce que ce depot a deja paye
ailleurs. Les sept sites gardent leur MOTIF ; ils ne gardent plus la regle.

**Ce que ce module NE fait PAS, dit plutot que tu.** Il ne pose aucun crochet
de collecte. Un `pytest_ignore_collect` a ete envisage et MESURE puis ecarte :
il ne sait ecarter qu'un FICHIER entier, et les douze fichiers concernes
portent **675 tests dont 27 seulement echouent** sur l'orphelin -- 648 mesures
reelles perdues pour en reparer 27. La granularite d'un mecanisme se mesure
avant de le choisir.

**Et il ne remplace pas `pytest.fail` : il le CONSERVE la ou il est juste.**
Les deux regimes se distinguent par un CARDINAL et non par un booleen :

* **au moins une reference joignable, mais pas celle-ci** -> clone tronque,
  arbre exporte, ou reference perimee. `pytest.fail`, inchange ;
* **AUCUNE reference joignable** -> ce n'est pas le meme depot.

Mesure qui fonde la distinction, prise le 2026-09-08 sur les quatorze
references reelles :

    depot de TRAVAIL : 14 joignables sur 14
    orphelin PUBLIC  :  0 joignables sur 14

Le regime est donc TOUT OU RIEN, sans zone grise -- c'est ce qui rend la
distinction utilisable, et c'est une mesure, pas une supposition.
"""

from __future__ import annotations

import ast
import functools
import pathlib
import re
import subprocess

#: Une reference courte ou longue, telle que ces bancs l'ecrivent.
_FORME_D_UN_COMMIT = re.compile(r"^[0-9a-f]{7,40}$")


def references_de_module(source: str) -> dict[str, str]:
    """`{nom: reference}` pour chaque constante de MODULE en forme de commit.

    **Resserre au niveau module, et la mesure dit pourquoi.** Un detecteur qui
    prendrait toute chaine en forme de SHA dans le fichier rend **huit faux
    positifs** sur ce depot -- les quatre sommes de controle de
    `test_patch_presets.py`, le `deadbeef` de `test_scan_previz.py`, les
    `0123456789abcdef` de `test_naming.py` et `test_extraction_manifest.py`.
    Tous sont des litteraux EN LIGNE : arguments d'appel, valeurs de fabrique.

    Resserre aux constantes de module, il rend **douze fichiers et zero faux
    positif** (mesure du 2026-09-08 sur `tests/**/*.py`). C'est la difference
    entre une heuristique et une mesure, et elle tient a un seul mot : les
    bancs de perimetre DECLARENT leur reference, ils ne l'inventent pas au
    milieu d'un appel.
    """
    rendus: dict[str, str] = {}
    for noeud in ast.parse(source).body:
        cibles: list[str] = []
        if isinstance(noeud, ast.Assign):
            cibles = [c.id for c in noeud.targets if isinstance(c, ast.Name)]
        elif isinstance(noeud, ast.AnnAssign) and isinstance(noeud.target, ast.Name):
            cibles = [noeud.target.id]
        if not cibles or not isinstance(noeud.value, ast.Constant):
            continue
        valeur = noeud.value.value
        if isinstance(valeur, str) and _FORME_D_UN_COMMIT.match(valeur):
            for cible in cibles:
                rendus[cible] = valeur
    return rendus


def references_joignables(racine, references) -> list[str]:
    """Celles de `references` que l'historique de CE depot contient.

    Rend une LISTE et non un booleen, pour la meme raison qu'`archives_presentes`
    dans `_chemins_bmad` : c'est le cardinal qui separe « autre depot » (zero)
    de « reference perimee » (une sur deux), et un booleen aurait avale le
    second cas -- c'est-a-dire le defaut reel que ces bancs existent a trouver.
    """
    joignables = []
    for reference in references:
        rendu = subprocess.run(
            ["git", "cat-file", "-e", f"{reference}^{{commit}}"],
            cwd=str(racine), capture_output=True)
        if rendu.returncode == 0:
            joignables.append(reference)
    return joignables


def porte_l_historique_de_travail(racine, references) -> bool:
    """Vrai des qu'UNE SEULE reference est joignable ici.

    Le seuil est a un, pas a toutes : un depot qui porte treize references sur
    quatorze est le depot de travail avec une reference perimee, et cette
    quatorzieme DOIT continuer de faire echouer son banc. Seul le zero absolu
    signale un autre depot.
    """
    return bool(references_joignables(racine, references))


#: Les deux issues d'une reference inatteignable vivent ici plutot que sur
#: chaque site, pour la raison que ce depot ecrit partout ailleurs : une regle
#: recopiee sept fois se repond sept fois differemment. Les sept sites gardent
#: en revanche leur MOTIF, qui nomme la frontiere que chacun mesure.


@functools.lru_cache(maxsize=None)
def references_declarees(racine_des_tests: str) -> frozenset[str]:
    """Toutes les references de perimetre que les bancs de ce depot DECLARENT.

    Balayage complet de `tests/**/*.py` -- 354 fichiers et **1,44 s** mesures le
    2026-09-08 --, mis en cache. Le cout n'est paye que par un appelant qui a
    DEJA vu une resolution echouer : sur le depot de travail, les quatorze
    references sont joignables, donc ce balayage n'a jamais lieu.
    """
    references: set[str] = set()
    for fichier in pathlib.Path(racine_des_tests).rglob("*.py"):
        try:
            source = fichier.read_text(encoding="utf-8")
        except OSError:                          # pragma: no cover - defensif
            continue
        try:
            references |= set(references_de_module(source).values())
        except SyntaxError:                      # pragma: no cover - defensif
            continue
    return frozenset(references)


def echoue_ou_saute(racine, reference: str, motif: str):
    """Le verdict d'une reference de perimetre inatteignable, en TROIS cas.

    Les sept sites qui l'appellent ecrivaient tous `pytest.fail` avec le meme
    argument -- « un skip se lirait comme un vert ». Cet argument est juste, et
    il reste le defaut : ce n'est PAS un assouplissement, c'est une distinction
    de regime que la redaction d'origine ne pouvait pas faire.

    * **reference FABRIQUEE** (`"0" * 40` et consorts) -- aucun banc ne la
      declare : c'est une sonde qui exerce la porte, et la porte doit mordre.
      `pytest.fail`, dans tous les depots. Sans ce premier cas,
      `test_the_perimeter_gate_separates_a_copied_tree_from_a_truncated_history`
      cesserait de mesurer quoi que ce soit sur le depot public -- sa sonde y
      serait sautee au lieu d'echouer, et c'est exactement le genre de perte
      silencieuse que cette famille de bancs existe a empecher ;
    * **au moins une reference declaree joignable ici** -- clone tronque, arbre
      exporte, reference perimee. La frontiere DEVAIT s'evaluer et ne l'a pas
      fait : `pytest.fail`, le comportement d'origine, mot pour mot ;
    * **AUCUNE reference declaree joignable** -- ce n'est pas le meme depot. Sur
      l'orphelin public (`EPIC8-ARB-12`) ces commits n'existeront JAMAIS, et
      aucun `fetch` ne les y fera apparaitre : la frontiere n'a pas d'objet,
      exactement comme `_exige_git_disponible` le dit deja d'un arbre copie.
      `pytest.skip`, qui reste VISIBLE dans la liste des verdicts -- un test
      vert d'un cote et saute de l'autre s'y voit, ce que CLAUDE.md demande.

    Mesure qui separe le deuxieme cas du troisieme, prise le 2026-09-08 :
    depot de travail **14 joignables sur 14**, orphelin public **0 sur 14**.
    """
    import pytest

    declarees = references_declarees(str(pathlib.Path(__file__).resolve().parent))
    if reference not in declarees:
        pytest.fail(motif)
    try:
        joignables = references_joignables(racine, declarees)
    except OSError:
        # **`git` ABSENT est un quatrieme cas, et c'est un echec DUR.** Sans ce
        # bloc, `subprocess.run` leve `FileNotFoundError` et le banc rend une
        # trace brute au lieu de son motif ; pire, un lecteur presse pourrait
        # etre tente de compter zero reference joignable et de sauter -- ce qui
        # confondrait « pas de git » avec « pas le meme depot ». Les sites le
        # disaient deja separement (`_git_disponible`, `_exige_git_disponible`)
        # et ils avaient raison : sans git, la frontiere DEVAIT s'evaluer et ne
        # l'a pas fait.
        pytest.fail(motif)
    if joignables:
        pytest.fail(motif)
    pytest.skip(
        f"reference de perimetre {reference} inatteignable, et AUCUNE des "
        f"{len(declarees)} references declarees par les bancs de ce depot ne "
        "l'est : cet historique n'est pas celui du travail (orphelin public, "
        "`EPIC8-ARB-12`). La frontiere n'a pas d'objet ici -- elle reste dure "
        f"des qu'une seule reference est joignable. Motif d'origine : {motif}"
    )
