"""Greffon pytest: relever les tests desactives au titre de `EPIC5-ARB-84`.

Il est charge par `-p _collecte_desactives_vrac` dans un **sous-processus** lance par
`test_desactivation_regime_vrac.py`, en `--collect-only` sur l'arbre `tests/` entier.

Pourquoi un greffon et pas un parcours de source. L'AC 11 exige un compte
**verifiable**, et un test qui recompterait lui-meme les decorateurs poses dans les
fichiers ne prouverait rien -- c'est la tautologie payee trois fois dans ce depot
(5.9, puis deux fois le 2026-08-18). Le compteur reel est **le collecteur de pytest**:
c'est lui qui deplie les parametrages, applique les marqueurs de classe et de module, et
decide ce qui sera saute. On lui pose la question, on ne la refait pas a sa place.

`--collect-only` sur tout `tests/` coute ~2 s (4957 tests), donc l'AC 9 -- le lot de
tests de la story sous 10 s -- reste tenue.

**Deuxieme releve, ajoute le 2026-08-19** (`EPIC5-ARB-100`, injection par AC de l'AC 9):
le greffon releve aussi les `skip` **inconditionnels** qui ne portent pas la sentinelle. Il ne le faisait
pas, et c'etait un trou exact sur l'AC 11: un `@pytest.mark.skip(reason="instable sur
cette machine")` pose sur n'importe quel test actif du depot etait **invisible** des
quatre assertions du registre -- elles ne voient que ce que la sentinelle leur montre. Or
l'AC 11 pose qu'« un skip muet est un echec d'AC »: c'est precisement le skip muet qui
echappait au compteur. Le second releve va dans `COLLECTE_AUTRES_JSON`.

**Portee du second releve: `skip` seulement, jamais `skipif`.** Les 144 `skipif` du depot
sont des portes d'environnement (`ffmpeg`/`Xvfb` absents du PATH) dont le cardinal depend
de la machine: les epingler en litteral ferait rougir la suite sur un poste ou ffmpeg est
installe, c'est-a-dire mesurer l'environnement au lieu du depot. Un endormissement
clandestin s'ecrit `skip`, pas `skipif(True)`, et c'est cette forme-la qui est comptee.
"""

from __future__ import annotations

import json
import os

SENTINELLE = "[REGIME-VRAC]"

_releves: list[list[str]] = []
#: Les `skip` **sans** sentinelle: tout endormissement qui n'est pas au titre de
#: `EPIC5-ARB-84`. Legitimes ou non, ils sont comptes et nommes -- c'est ce qui rend un
#: endormissement clandestin visible.
_autres: list[list[str]] = []


def _raison(mark) -> str:
    """La raison d'un `pytest.mark.skip`, quelle que soit la forme d'appel."""
    if "reason" in mark.kwargs:
        return str(mark.kwargs["reason"])
    return str(mark.args[0]) if mark.args else ""


def pytest_collection_modifyitems(items):
    for item in items:
        for mark in item.iter_markers(name="skip"):
            raison = _raison(mark)
            if SENTINELLE in raison:
                _releves.append([item.nodeid, raison])
            else:
                _autres.append([item.nodeid, raison])
            break


def pytest_sessionfinish(session, exitstatus):
    for variable, releve in (("COLLECTE_VRAC_JSON", _releves),
                             ("COLLECTE_AUTRES_JSON", _autres)):
        destination = os.environ.get(variable)
        if not destination:
            continue
        with open(destination, "w", encoding="utf-8") as fichier:
            json.dump(releve, fichier, ensure_ascii=True, indent=1)
