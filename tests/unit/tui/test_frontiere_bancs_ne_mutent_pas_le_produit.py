# -*- coding: utf-8 -*-
"""Aucun banc de la TUI ne mute une CLASSE de production, et ca se mesure.

**Ce que cette frontiere ferme, et il a ete paye le 2026-09-02**, trouve par la
couche 3 de la revue de la story 11.7. Le banc de l'ecran de resultat de
l'atelier Pdf posait, dans sa fabrique :

    type(objet).app = property(lambda self: self._app_factice)

`textual` fait de `Screen.app` une **propriete** -- un descripteur de donnees,
qu'une affectation sur l'instance ne masque pas. La seule facon de la remplacer
sans monter l'application est donc de la redefinir sur une classe ; ce banc
redefinissait la classe de **production**, et **ne la restaurait jamais**.

Ce que ca produit est le pire mode de panne qu'un banc puisse avoir : tout
fichier collecte **apres** celui-ci heritait de la mutation. Trois mesures d'AC
tombaient des que l'ordre de collecte changeait -- en serie comme en `-n 4` --,
chaque fichier restait vert **seul**, et le dossier entier ne restait vert que
par coincidence alphabetique. Ni le message d'echec ni la trace ne nommaient le
banc fautif : ils accusaient l'ecran innocent.

C'est de la meme famille que les faux verts que `CLAUDE.md` collectionne : une
mesure qui croit juger un arbre qu'elle a elle-meme change.

**Le geste correct** est une **sous-classe** du banc, qui porte la propriete
sans toucher a ce que le produit livre -- c'est ce que `_EcranSousBanc` fait
desormais dans `test_atelier_pdf_resultat.py`. `monkeypatch.setattr` conviendrait
aussi, parce qu'il **restaure**.

Cette frontiere porte son **volet symetrique** : elle mesure qu'elle voit bien
la faute, sur un temoin ecrit ici. Une frontiere negative dont personne n'a
verifie qu'elle mord ne mesure rien.
"""

import ast
from pathlib import Path

DOSSIER_DES_BANCS = Path(__file__).resolve().parent

TEMOIN_FAUTIF = """
def fabrique(objet):
    type(objet).app = property(lambda self: self._factice)
    return objet
"""

TEMOIN_FAUTIF_PAR_SETATTR = """
def fabrique(objet):
    setattr(type(objet), "app", property(lambda self: self._factice))
    return objet
"""

TEMOIN_SAIN = """
class _SousBanc(produit.Ecran):
    @property
    def app(self):
        return self._factice


def fabrique():
    objet = _SousBanc()
    objet._factice = object()
    return objet
"""


def _est_appel_a_type(noeud) -> bool:
    """`type(x)` -- l'expression par laquelle on atteint la classe d'un objet."""
    return (isinstance(noeud, ast.Call)
            and isinstance(noeud.func, ast.Name)
            and noeud.func.id == "type"
            and len(noeud.args) == 1)


def mutations_de_classe(source: str) -> list[tuple[int, str]]:
    """Les endroits ou le source ecrit sur la classe d'un objet vivant.

    Deux formes, et il faut les deux : l'affectation directe
    (`type(x).attr = ...`) et le detour par `setattr(type(x), "attr", ...)`.
    Ne mesurer que la premiere laisserait la seconde passer, et c'est la
    reecriture qu'un agent presse ecrit quand la premiere rougit.
    """
    trouvailles: list[tuple[int, str]] = []
    for noeud in ast.walk(ast.parse(source)):
        if isinstance(noeud, ast.Assign):
            for cible in noeud.targets:
                if isinstance(cible, ast.Attribute) and _est_appel_a_type(cible.value):
                    trouvailles.append((noeud.lineno, f"type(...).{cible.attr} = ..."))
        if (isinstance(noeud, ast.Call)
                and isinstance(noeud.func, ast.Name)
                and noeud.func.id == "setattr"
                and noeud.args
                and _est_appel_a_type(noeud.args[0])):
            trouvailles.append((noeud.lineno, "setattr(type(...), ...)"))
    return trouvailles


def test_le_temoin_FAUTIF_est_bien_vu():
    """Volet symetrique : sans lui, un balayage muet passerait pour une preuve."""
    assert mutations_de_classe(TEMOIN_FAUTIF) == [(3, "type(...).app = ...")]


def test_le_temoin_FAUTIF_PAR_SETATTR_est_bien_vu_lui_aussi():
    """Le detour par `setattr` est la reecriture naturelle, il ne doit pas passer."""
    assert mutations_de_classe(TEMOIN_FAUTIF_PAR_SETATTR) == [
        (3, "setattr(type(...), ...)")]


def test_le_temoin_SAIN_ne_declenche_rien():
    """Une sous-classe de banc est le geste correct : elle doit rester permise."""
    assert mutations_de_classe(TEMOIN_SAIN) == []


def test_aucun_banc_de_la_TUI_ne_mute_la_classe_d_un_objet():
    """L'ensemble des bancs fautifs est **exactement** vide.

    Une appartenance (« tel banc n'est pas fautif ») laisserait passer le
    suivant ; c'est l'ensemble entier qui se mesure.
    """
    fautifs: dict[str, list[tuple[int, str]]] = {}
    for banc in sorted(DOSSIER_DES_BANCS.rglob("*.py")):
        if banc.name == Path(__file__).name:
            continue
        trouvailles = mutations_de_classe(banc.read_text(encoding="utf-8"))
        if trouvailles:
            fautifs[str(banc.relative_to(DOSSIER_DES_BANCS))] = trouvailles
    assert fautifs == {}
