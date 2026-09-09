"""Tests du helper de gardes numeriques partagees (action item 2, retro Epic 4).

Le module existe pour une seule raison: en Python, ``bool`` est une sous-classe
de ``int``. Une validation ecrite naivement accepte donc ``True`` et le traite
comme un ``1`` -- un DPI a ``True``, un canal de couleur a ``True``. Le
correctif a ete trouve cinq fois independamment en revue d'Epic 4, sur cinq
modules differents.

Ces tests portent donc **d'abord** sur le cas booleen: c'est le seul qui
justifie l'existence du module, et un helper qui le raterait serait pire que le
motif duplique qu'il remplace, puisqu'il donnerait l'illusion d'etre couvert.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility.numeric_guards import is_strict_int, is_strict_number


@pytest.mark.parametrize("value", [True, False])
def test_booleans_are_never_accepted(value: bool) -> None:
    # La raison d'etre du module. `isinstance(True, int)` vaut True et
    # `True == 1`: sans cette garde, un booleen passe pour un entier valide.
    assert not is_strict_int(value)
    assert not is_strict_number(value)


@pytest.mark.parametrize("value", [0, 1, -3, 10**20])
def test_plain_integers_are_accepted_by_both_guards(value: int) -> None:
    assert is_strict_int(value)
    assert is_strict_number(value)


@pytest.mark.parametrize("value", [0.0, 2.5, -1.5, float("inf"), float("nan")])
def test_floats_are_numbers_but_not_integers(value: float) -> None:
    # Les gardes portent sur le **type**, pas sur le domaine: `inf` et `nan`
    # sont des flottants valides ici, et c'est a l'appelant de les refuser s'il
    # y a lieu (io/payload le fait pour `fps_target`). Melanger les deux
    # responsabilites rendrait le helper inutilisable ailleurs.
    assert not is_strict_int(value)
    assert is_strict_number(value)


@pytest.mark.parametrize("value", ["1", None, [1], (1,), {"a": 1}, object()])
def test_non_numbers_are_refused_by_both_guards(value: object) -> None:
    assert not is_strict_int(value)
    assert not is_strict_number(value)


def test_both_guards_have_real_callers() -> None:
    """Un helper de deduplication sans appelant est du code mort deguise.

    Cree par la story 5.9 pour cesser de recopier le motif; il n'a de sens que
    s'il est effectivement consomme. Ce test echoue si une fonction perd son
    dernier appelant -- ce qui doit etre une decision, pas un oubli.
    """
    import ast

    src_root = REPO_ROOT / "src" / "mixed_media_utility"
    guard_module = src_root / "numeric_guards.py"
    callers: dict[str, set[str]] = {"is_strict_int": set(), "is_strict_number": set()}
    for path in sorted(src_root.rglob("*.py")):
        if path == guard_module:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in callers:
                    callers[node.func.id].add(path.name)
    for name, modules in callers.items():
        assert modules, f"{name} n'a plus aucun appelant dans src/"
