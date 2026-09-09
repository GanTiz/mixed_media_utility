"""Gardes de typage numerique partagees (action item 2 de la retro Epic 4).

En Python, ``bool`` est une sous-classe de ``int``: ``isinstance(True, int)``
vaut ``True`` et ``True == 1``. Toute validation ecrite naivement comme
``isinstance(value, int) and value > 0`` accepte donc ``True`` et le traite
comme un ``1`` — un DPI a ``True``, un ``page_count`` a ``True``, un canal de
couleur a ``True``. Le correctif (tester ``bool`` **avant** ``int``) a ete
trouve cinq fois independamment en revue d'Epic 4, sur cinq modules
differents; la retro en a fait un action item.

Ce module est la reponse: la subtilite est ecrite **une fois** et se lit dans
le nom de la fonction.

Contrat volontairement minimal — ces fonctions rendent un booleen et ne levent
rien. Chaque module appelant garde sa propre classe d'exception metier et son
propre message (``PatchValuesIntegrityError``, ``PayloadValidationError``,
...): centraliser aussi la levee obligerait a fusionner des hierarchies
d'exceptions qui n'ont aucune raison de l'etre, et c'est la garde de type qui
etait dupliquee, pas les messages.

Module **pur**: aucune dependance, pas meme la bibliotheque standard, pour
qu'il soit importable depuis les modules verrouilles comme purs par test AST
(``patch_values.py``, ``patch_presets.py``).
"""

from __future__ import annotations


def is_strict_int(value: object) -> bool:
    """``True`` si ``value`` est un entier Python qui n'est pas un booleen.

    C'est la garde a utiliser partout ou un entier est attendu:
    ``if not is_strict_int(dpi) or dpi <= 0: raise ...``
    """
    return isinstance(value, int) and not isinstance(value, bool)


def is_strict_number(value: object) -> bool:
    """``True`` si ``value`` est un entier ou un flottant, jamais un booleen.

    Variante pour les grandeurs qui acceptent les deux (cadences, dimensions
    en millimetres, epaisseurs de trait).
    """
    return isinstance(value, (int, float)) and not isinstance(value, bool)
