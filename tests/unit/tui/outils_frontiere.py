# -*- coding: utf-8 -*-
"""Outils de mesure des frontieres negatives de l'Epic 11.

Ils lisent du **code**, jamais du texte : l'arbre syntaxique dit ce que le
module reference vraiment, la ou un grep confond une prose d'explication
avec un import. Motif mesure a l'ecriture de la story 11.0 : le docstring de
`tui/jetons.py` explique pourquoi il n'importe pas `SEMANTIQUES`, il porte
donc le mot -- un grep de texte y mordrait et se ferait affaiblir.

Module a part, et pas dans un fichier de test : les stories suivantes de
l'epic posent leurs propres frontieres et reprennent ces mesures.
"""

import ast
from pathlib import Path


def _arbre(chemin: Path) -> ast.Module:
    return ast.parse(chemin.read_text(encoding="utf-8"), filename=str(chemin))


def _docstrings(arbre: ast.Module) -> set[int]:
    """Identite des noeuds qui sont des docstrings, a exclure des mesures."""
    porteurs = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    trouves = set()
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, porteurs):
            continue
        corps = getattr(noeud, "body", [])
        if (corps and isinstance(corps[0], ast.Expr)
                and isinstance(corps[0].value, ast.Constant)
                and isinstance(corps[0].value.value, str)):
            trouves.add(id(corps[0].value))
    return trouves


def chaines_de_code(chemin: Path) -> list[str]:
    """Les chaines litterales du code, docstrings exclus."""
    arbre = _arbre(chemin)
    exclus = _docstrings(arbre)
    return [n.value for n in ast.walk(arbre)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in exclus]


def chaines_de_docstring(chemin) -> list[str]:
    """Les docstrings du module -- exactement ce que :func:`chaines_de_code` ecarte.

    Fonction soeur de :func:`chaines_de_code`, et sa COMPLEMENTAIRE : leur
    union est l'ensemble des chaines litterales du module. Elle existe parce
    qu'une AC peut vouloir l'une, l'autre, ou les deux, et que le choix se
    mesure alors au lieu de se plaider.

    Le cas qui l'a posee (story 11.13, revue couche 3, finding F4) : l'AC 4.2
    interdit un mot dans « aucun module de ``src/`` », la frontiere ne
    mesurait que les chaines de code, et rien ne disait ou passait la
    difference. Deux mesures separees rendent l'ecart visible plutot
    qu'argumente.

    Ce qu'elle ne voit PAS, dit plutot que tu : les commentaires ``#``. Ils ne
    sont pas des noeuds de l'AST, donc aucun lecteur d'AST ne les rend -- ce ne
    sont pas non plus des litteraux, ce que ces predicats mesurent.
    """
    arbre = _arbre(Path(chemin))
    # `_docstrings` est le lieu UNIQUE ou ce depot decide ce qu'EST un
    # docstring : on le lit, on ne le recopie pas. Une seconde recette
    # divergerait de la premiere, et cette fonction et `chaines_de_code`
    # cesseraient d'etre complementaires sans que rien ne rougisse -- une
    # chaine tomberait alors dans les deux, ou dans aucune.
    retenus = _docstrings(arbre)
    return [n.value for n in ast.walk(arbre)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) in retenus]


def identifiants(chemin: Path) -> set[str]:
    """Tout nom reellement reference par le code : variables et attributs."""
    arbre = _arbre(chemin)
    noms = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Name):
            noms.add(noeud.id)
        elif isinstance(noeud, ast.Attribute):
            noms.add(noeud.attr)
        elif isinstance(noeud, ast.ImportFrom):
            noms.update(alias.name for alias in noeud.names)
        elif isinstance(noeud, ast.Import):
            noms.update(alias.name for alias in noeud.names)
    return noms


def definitions(chemin: Path) -> set[str]:
    """Tout nom DEFINI par le code : classes et fonctions.

    **Distinct de :func:`identifiants`, et le distinguo a coute un faux
    « tue ».** `identifiants` collecte `ast.Name`, `ast.Attribute` et les alias
    d'import -- c'est-a-dire ce qu'un module REFERENCE. Une classe definie et
    jamais citee par son nom lui est invisible : la couche 3 de la revue de la
    story 11.11 a injecte une classe `EcranRelinkDuRush` dans `palier_projet`
    et la frontiere d'`EPIC11-ARB-23` est restee **verte sur 30 tests**, alors
    que sa docstring promettait « aucune classe d'ecran de relink ».

    Une frontiere qui porte sur ce qu'un module EST -- et non sur ce qu'il
    appelle -- lit donc les deux ensembles. Les deux existent parce qu'ils
    repondent a deux questions : « ce module s'en sert-il ? » et « ce module
    en porte-t-il un ? ».
    """
    arbre = _arbre(chemin)
    return {noeud.name for noeud in ast.walk(arbre)
            if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.ClassDef))}


def constantes_entieres(chemin) -> list[int]:
    """Les entiers litteraux du code, docstrings et annotations compris.

    Sert la frontiere de la story 11.1 AC 2.4 : la limite de 48 caracteres est
    LUE du coeur, jamais recopiee. On lit les constantes du code et non le
    texte, parce qu'un `48` dans une phrase d'explication n'est pas une limite
    recopiee -- et une garde qui les confondrait se ferait affaiblir a la
    premiere prose.
    """
    arbre = _arbre(Path(chemin))
    return [noeud.value for noeud in ast.walk(arbre)
            if isinstance(noeud, ast.Constant)
            and isinstance(noeud.value, int)
            and not isinstance(noeud.value, bool)]


def chaines_d_octets(chemin) -> list[bytes]:
    """Les litteraux d'OCTETS du code -- ce que :func:`chaines_de_code` ne voit pas.

    Fonction soeur de :func:`chaines_de_code`, sur le modele de
    :func:`constantes_entieres`, et posee pour un defaut mesure a la story
    11.13 : la signature de pointeur Git LFS du coeur est un litteral `bytes`
    (`b"version https://git-lfs.github.com/spec/v1"`). Une frontiere qui
    n'inspecterait que les `str` serait donc **verte avant meme le retrait**
    -- c'est-a-dire qu'elle ne mesurerait rien, exactement le mode de panne
    que les volets de morsure existent pour attraper.

    Aucune exclusion de docstring ici : un docstring est par construction une
    chaine `str`, jamais un litteral d'octets.
    """
    arbre = _arbre(Path(chemin))
    return [noeud.value for noeud in ast.walk(arbre)
            if isinstance(noeud, ast.Constant) and isinstance(noeud.value, bytes)]


def _plie_une_concatenation(noeud, litteral):
    """Recompose une concatenation de litteraux, ou rend ``None``.

    Recursive et **totale** : si un seul operande n'est pas un litteral du bon
    type -- une variable, un appel, un `%` --, la recomposition echoue et rend
    ``None`` plutot qu'un fragment. Un fragment serait pire que rien : il ferait
    croire a une mesure la ou il n'y a qu'une moitie de chaine.
    """
    if isinstance(noeud, ast.Constant) and isinstance(noeud.value, litteral):
        return noeud.value
    if isinstance(noeud, ast.BinOp) and isinstance(noeud.op, ast.Add):
        gauche = _plie_une_concatenation(noeud.left, litteral)
        if gauche is None:
            return None
        droite = _plie_une_concatenation(noeud.right, litteral)
        if droite is None:
            return None
        return gauche + droite
    return None


def chaines_recomposees(chemin) -> list[str]:
    """Les chaines que le code ASSEMBLE par `+`, que les litteraux ne disent pas.

    Fonction soeur de :func:`chaines_de_code`, posee sur un survivant mesure a
    la revue de la story 11.13 : `"gi" + "t"` et `"IRRECUPER" + "ABLES"`
    reintroduisent le defaut retire sans qu'aucun litteral du module ne le
    porte. Un lecteur qui ne regarde que les `ast.Constant` est donc vert sur
    une reintroduction fonctionnellement identique -- c'est-a-dire qu'il mesure
    l'orthographe du code source, pas ce que le code produit.

    L'adjacence implicite (`"IRRECUPER" "ABLES"`) est deja pliee par
    l'analyseur en un seul `ast.Constant` : elle n'a jamais eu besoin d'ici.
    Ce qui suit ne rend que les concatenations **explicites** et **entierement
    litterales**, docstrings compris -- un docstring n'est jamais un `BinOp`.
    """
    arbre = _arbre(Path(chemin))
    recomposees = []
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.BinOp) or not isinstance(noeud.op, ast.Add):
            continue
        plie = _plie_une_concatenation(noeud, str)
        if plie is not None:
            recomposees.append(plie)
    return recomposees


def octets_recomposes(chemin) -> list[bytes]:
    """Le pendant d'octets de :func:`chaines_recomposees`.

    `b"version https://" + b"git-lfs..."` est la meme evasion, ecrite en
    octets : la frontiere LFS de la story 11.13 la manquerait sans ceci.
    """
    arbre = _arbre(Path(chemin))
    recomposes = []
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.BinOp) or not isinstance(noeud.op, ast.Add):
            continue
        plie = _plie_une_concatenation(noeud, bytes)
        if plie is not None:
            recomposes.append(plie)
    return recomposes
