# -*- coding: utf-8 -*-
"""Banc headless des tests TUI (story 11.0, AC 8).

Le contrat du banc : **la suite passe sans terminal**. `textual` n'ouvre aucun
peripherique sous `App.run_test()` -- il pilote un ecran virtuel a la taille
demandee --, il n'y a donc ni variable d'affichage a poser ni ecran a
emprunter, contrairement au banc GUI qui doit forcer `QT_QPA_PLATFORM`. C'est
la difference de fond entre les deux bancs, et elle explique pourquoi ce
conftest est court la ou celui de `tests/unit/gui/` doit reparer une fuite
d'environnement.

**Pourquoi `asyncio.run` et non `pytest-asyncio`.** `run_test()` est un
gestionnaire de contexte asynchrone, donc un test qui l'emploie doit vivre dans
une boucle. Le depot n'a **pas** `pytest-asyncio` (`requirements-dev.txt` ne
porte que `mutmut`), et cette story n'a aucune raison de lui imposer une
dependance de test de plus : :func:`piloter` ouvre la boucle elle-meme et rend
un test **synchrone** ordinaire. Les neuf stories suivantes heritent de ce
choix.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Awaitable, Callable

import pytest

# Convention du depot : le paquet s'importe depuis src/ par insertion de
# chemin, pas par installation -- meme geste que tests/unit/gui/conftest.py,
# fait UNE fois pour tout le dossier.
_RACINE = Path(__file__).resolve().parents[3]
_SRC = str(_RACINE / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

#: Taille du banc par defaut : le plancher exact de `EPIC11-ARB-21`. Mesurer au
#: plancher et non au-dessus est delibere : un ecran qui tient a 100x30 et
#: deborde a 80x24 est un defaut que seule cette taille demasque.
TAILLE_PLANCHER = (80, 24)


def piloter(app, scenario: Callable[[Any], Awaitable[Any]],
            taille: tuple[int, int] = TAILLE_PLANCHER):
    """Monte `app` sous `run_test` et deroule `scenario(pilote)`.

    `scenario` est une coroutine qui recoit le pilote `textual` et rend ce que
    le test veut asserter. La valeur rendue traverse : c'est ce qui permet
    d'observer l'application **pendant** qu'elle est montee -- une fois le
    gestionnaire de contexte referme, l'arbre de widgets n'existe plus, et une
    assertion posee apres coup ne mesurerait rien.
    """
    async def _tour():
        async with app.run_test(size=taille) as pilote:
            return await scenario(pilote)

    return asyncio.run(_tour())


@pytest.fixture
def racine_depot() -> Path:
    """La racine du depot -- les frontieres negatives grepent dessus."""
    return _RACINE


@pytest.fixture
def paquet_tui() -> Path:
    """`src/mixed_media_utility/tui/`, cible des greps de frontiere."""
    return _RACINE / "src" / "mixed_media_utility" / "tui"


@pytest.fixture
def sources_tui(paquet_tui) -> list[Path]:
    """Tous les `.py` du paquet TUI.

    L'assertion de cardinal n'est pas decorative : une frontiere negative
    appliquee a un paquet vide serait verte sans rien mesurer, et c'est
    exactement le mode de panne que les volets symetriques cherchent a
    exclure. Ici on exclut l'autre moitie : que la cible existe.
    """
    fichiers = sorted(paquet_tui.rglob("*.py"))
    assert len(fichiers) >= 2, (
        "le paquet TUI doit porter plusieurs modules : une frontiere posee "
        f"sur un paquet quasi vide ne mesure rien (trouve {fichiers!r})"
    )
    return fichiers


@pytest.fixture
def banc():
    """Rend :func:`piloter`. C'est le moyen T de toutes les stories de l'epic."""
    return piloter
