# -*- coding: utf-8 -*-
"""Lire, dans l'AST d'un banc, les chemins de `_bmad-output/` qu'il construit.

**Ecrit une fois pour deux appelants**, et c'est le point : `tests/conftest.py`
ecarte les bancs dont l'archive est absente (regime du depot PUBLIC), et
`tests/unit/test_perimetre_public.py` mesure le perimetre qu'`EPIC11-ARB-268`
autorise (regime du depot de TRAVAIL). Les deux posent la MEME question -- quel
chemin ce fichier construit-il ? -- et une seconde redaction du detecteur
divergerait de la premiere sans que rien ne le dise.

**Sur l'AST, jamais sur le texte.** Les docstrings de ce depot citent
abondamment `_bmad-output/` -- celle-ci le fait a chaque paragraphe. Un `grep`
compterait la prose et se tromperait dans les deux sens.
"""

from __future__ import annotations

import ast

#: Le nom du dossier de methode, tel qu'il apparait dans un chemin construit.
DOSSIER = "_bmad-output"


def feuilles(noeud: ast.AST) -> list[ast.AST]:
    """Aplatir une chaine de `/` en ses feuilles, de gauche a droite.

    `_RACINE / "_bmad-output" / "specs" / "project.schema.json"` est un arbre
    de `BinOp(Div)` imbrique a GAUCHE : sans cet aplatissement, on ne verrait
    que le dernier segment.
    """
    if isinstance(noeud, ast.BinOp) and isinstance(noeud.op, ast.Div):
        return feuilles(noeud.left) + feuilles(noeud.right)
    return [noeud]


def texte(noeud: ast.AST) -> str | None:
    """Le contenu d'une feuille quand c'est une chaine litterale, sinon `None`."""
    if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str):
        return noeud.value
    return None


def chemin_de_la_chaine(les_feuilles: list[ast.AST]) -> str | None:
    """Le chemin sous `_bmad-output/` qu'une chaine de `/` construit.

    On repart du segment qui NOMME le dossier -- il peut lui-meme porter la
    suite (`"_bmad-output/specs/project.schema.json"` en un seul litteral) --
    puis on colle les segments litteraux qui suivent. Un segment non litteral
    **arrete** la lecture : ce qui vient apres n'est pas connu ici, et deviner
    serait pire que de s'arreter.
    """
    for rang, feuille in enumerate(les_feuilles):
        brut = texte(feuille)
        if brut is None:
            continue
        if not (brut == DOSSIER or brut.startswith(f"{DOSSIER}/")):
            continue
        segments = [brut.strip("/")]
        for suivante in les_feuilles[rang + 1:]:
            suite = texte(suivante)
            if suite is None:
                break
            segments.append(suite.strip("/"))
        return "/".join(segments)
    return None


def chemins_construits(source: str) -> set[str]:
    """Tout chemin sous `_bmad-output/` que ce source CONSTRUIT.

    Les chaines litterales isolees comptent aussi : un banc peut porter
    `"_bmad-output/specs/project.schema.json"` en un seul morceau. Le tri entre
    « construit » et « nomme pour interdire » n'appartient pas a ce module --
    il depend de la question posee, et chaque appelant la sienne.
    """
    try:
        arbre = ast.parse(source)
    except SyntaxError:                          # pragma: no cover - defensif
        return set()
    vus: set[str] = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.BinOp) and isinstance(noeud.op, ast.Div):
            chemin = chemin_de_la_chaine(feuilles(noeud))
        else:
            brut = texte(noeud)
            chemin = (brut.strip("/") if brut and (
                brut == DOSSIER or brut.startswith(f"{DOSSIER}/")) else None)
        if chemin is not None:
            vus.add(chemin)
    return vus


def chemins_joints(source: str) -> set[str]:
    """Les chemins que ce source construit par une CHAINE de `/`, eux seuls.

    **La difference avec :func:`chemins_construits` est ce qui separe LIRE de
    NOMMER, et elle est mesuree plutot que declaree** (2026-09-07, sur un faux
    positif du conftest). Un banc qui ouvre une archive ecrit
    `_RACINE / "_bmad-output" / ... `, donc un `BinOp(Div)` ; un banc qui NOMME
    un chemin pour l'INTERDIRE le porte en litteral nu, dans un tuple compare
    par `in ligne`. Releve sur les cinq bancs concernes :

        test_politiques_du_depot.py      joints 0, nus 2   <- interdit
        test_atelier_pdf_confirmation    joints 8, nus 0   <- lit
        test_versionnage_du_pdf_en_tui   joints 7, nus 0   <- lit
        test_atelier_exports_versions    joints 8, nus 0   <- lit
        test_liaison_coeur_vague_3       joints 3, nus 0   <- lit

    Separation nette, dans les deux sens. C'est pourquoi l'ecart du conftest se
    lit sur la FORME et n'a besoin d'aucun registre de noms -- un registre
    derive, une forme ne derive pas.

    **Ce qu'elle ne couvre pas, dit plutot que tu** : un banc qui ouvrirait un
    chemin porte en un seul litteral (`open("_bmad-output/x.md")`) serait vu
    comme un nommeur et ne serait PAS ecarte -- il rougirait sur le public au
    lieu d'etre saute. Aucun banc du depot n'ecrit cela aujourd'hui ; le jour
    ou l'un le ferait, c'est un rouge nomme, pas un saut silencieux, ce qui est
    le bon sens de l'erreur.
    """
    try:
        arbre = ast.parse(source)
    except SyntaxError:                          # pragma: no cover - defensif
        return set()
    vus: set[str] = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.BinOp) and isinstance(noeud.op, ast.Div):
            chemin = chemin_de_la_chaine(feuilles(noeud))
            if chemin is not None:
                vus.add(chemin)
    return vus


def archives_presentes(racine, chemins) -> list[str]:
    """Ceux de `chemins` que CE depot porte reellement.

    **Sert a distinguer les deux regimes, jamais a autoriser un saut.** Un banc
    qui asserte quelque chose du depot de TRAVAIL -- « ici, rien n'est ecarte »,
    « ici, chaque archive declaree existe » -- ne peut pas tenir sur
    l'historique orphelin du depot PUBLIC, ou aucune de ces archives n'est par
    construction (`EPIC8-ARB-12`, `EPIC11-ARB-268`). Il n'y mesure pas un
    defaut : il mesure qu'il n'est pas chez lui.

    Le cardinal rendu -- et non un booleen -- est ce qui garde la mesure
    tranchante. `porte_l_archive_privee` ci-dessous ne saute que sur ZERO, si
    bien qu'un registre PARTIELLEMENT perime sur le depot de travail -- trois
    archives sur quatre, le cas reel d'un document renomme -- continue de faire
    rougir. Un booleen « l'archive est la ? » aurait avale ce cas.
    """
    return [chemin for chemin in chemins if (racine / chemin).exists()]


def porte_l_archive_privee(racine, chemins) -> bool:
    """Vrai si CE depot est celui du TRAVAIL, mesure et non declare.

    Aucun drapeau, aucune variable d'environnement : la question se tranche sur
    la presence des archives elles-memes. Le saut qui en decoule est donc
    STRUCTUREL -- il n'y a rien a rallumer, et c'est la meme forme que
    `test_politiques_du_depot.py` oppose a un `origin/main` hors d'atteinte.
    """
    return bool(archives_presentes(racine, chemins))
