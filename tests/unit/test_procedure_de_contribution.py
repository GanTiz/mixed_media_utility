"""La procedure documentee doit mener a une suite qui TOURNE.

**Le defaut que ce banc ferme.** Jusqu'au 2026-09-10,
`docs/guide-developpeur/contribuer.md` donnait **une** installation
(`pip install -e ".[dev]"`) la ou l'integration continue en fait **deux** --
la seconde etant `packaging/mmu-tui`, qui porte `textual`.

Mesure du jour : `textual` n'est declare dans **aucune** dependance de
`mmu-cli` (ni coeur, ni `gui`, ni `dev`, ni `test`, ni `full`), et **138
fichiers de test** importent le paquet `mixed_media_utility.tui`, qui l'emploie
dans 27 modules. Sans la seconde installation, ces 138 fichiers echouent a se
CHARGER -- avant qu'un seul test ne soit joue -- et aucune garde ne les saute.

**Un tiers qui suivait la procedure a la lettre ne pouvait pas jouer la
suite.** C'est le seul defaut de ce dossier de nettoyage qui touche un
utilisateur reel plutot que le confort d'un agent.

**Ce que ce banc mesure, et pourquoi la CI ne suffisait pas.** La CI passe :
elle fait les deux installations. C'est precisement ce qui rendait l'ecart
invisible -- le vert de la CI ne dit rien de la procedure ECRITE. Ce banc
compare les deux declarations l'une a l'autre.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

_RACINE = Path(__file__).resolve().parents[2]
_CI = _RACINE / ".github" / "workflows" / "ci.yml"
_DOC = _RACINE / "docs" / "guide-developpeur" / "contribuer.md"
_PYPROJECT = _RACINE / "pyproject.toml"
_PAQUET_TUI = _RACINE / "packaging" / "mmu-tui" / "pyproject.toml"

#: `pip install -e <cible>` ou la cible est LOCALE (un chemin, pas un paquet
#: d'index). C'est ce qu'un contributeur doit reproduire a l'identique.
_INSTALL_LOCAL = re.compile(r"pip install\s+-e\s+(?P<cible>[.\w/\[\]\"'-]+)")


def _cibles_locales(texte: str) -> set[str]:
    cibles = set()
    for m in _INSTALL_LOCAL.finditer(texte):
        cible = m.group("cible").strip("\"'")
        # On compare la RACINE de la cible, pas ses extras : la CI installe
        # `.[test]` la ou un contributeur veut `.[dev]`, et c'est legitime --
        # ce qui doit coincider est l'ENSEMBLE DES PAQUETS installes.
        cibles.add(cible.split("[")[0].rstrip("/") or ".")
    return cibles


def test_toute_installation_locale_de_la_CI_est_dans_la_procedure():
    """L'invariant central : la doc declare ce que la CI execute.

    C'est cette comparaison qui manquait. Chacune des deux declarations etait
    coherente avec elle-meme ; rien ne les confrontait.
    """
    ci = _cibles_locales(_CI.read_text(encoding="utf-8"))
    doc = _cibles_locales(_DOC.read_text(encoding="utf-8"))
    manquantes = ci - doc
    assert not manquantes, (
        f"la CI installe {sorted(manquantes)} que `contribuer.md` ne donne "
        "pas. Un contributeur qui suit la procedure ne pourra pas jouer la "
        "suite, et le vert de la CI ne le dira jamais -- elle, elle fait les "
        "deux installations."
    )


def test_FRONTIERE_NEGATIVE_la_procedure_ne_donne_pas_UNE_seule_installation():
    """La forme fautive, nommee pour qu'elle ne revienne pas.

    Une procedure a une ligne « marche » du point de vue de qui l'ecrit : elle
    installe quelque chose. Seul le CARDINAL la demasque.
    """
    doc = _cibles_locales(_DOC.read_text(encoding="utf-8"))
    assert len(doc) >= 2, (
        f"`contribuer.md` ne donne que {sorted(doc)}. Le projet livre DEUX "
        "distributions, et la seconde porte `textual` -- sans elle, 138 "
        "fichiers de test echouent a se charger."
    )


def test_le_MOTIF_est_mesure_et_non_recite_textual_n_est_pas_dans_mmu_cli():
    """Si `textual` entrait un jour dans `mmu-cli`, ce banc devrait tomber.

    C'est ce qui empeche la procedure de garder une seconde installation
    devenue inutile -- et la prose qui l'explique de devenir fausse.
    """
    d = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))["project"]
    partout = " ".join(
        [str(d.get("dependencies", []))]
        + [str(v) for v in d.get("optional-dependencies", {}).values()]
    )
    assert "textual" not in partout, (
        "`textual` est desormais une dependance de `mmu-cli` : la seconde "
        "installation n'est plus necessaire, et la prose de `contribuer.md` "
        "qui l'explique est devenue fausse. Reprendre les deux."
    )
    tui = tomllib.loads(_PAQUET_TUI.read_text(encoding="utf-8"))["project"]
    assert any("textual" in dep for dep in tui.get("dependencies", [])), (
        "`textual` n'est plus declare par `mmu-tui` non plus : d'ou vient-il ?"
    )


def test_l_ENJEU_est_mesure_beaucoup_de_bancs_dependent_du_paquet_tui():
    """La prose annonce 138 bancs : ce test verifie l'ordre de grandeur.

    Un chiffre ecrit dans un document et jamais remesure est exactement ce que
    ce depot documente comme se perimant en silence.
    """
    import ast
    concernes = set()
    for f in (_RACINE / "tests").rglob("test_*.py"):
        try:
            arbre = ast.parse(f.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):  # pragma: no cover
            continue
        for n in ast.walk(arbre):
            noms = []
            if isinstance(n, ast.Import):
                noms = [a.name for a in n.names]
            elif isinstance(n, ast.ImportFrom) and n.module:
                noms = [n.module]
            if any(m.split(".")[0] == "textual"
                   or m.startswith("mixed_media_utility.tui") for m in noms):
                concernes.add(f)
                break
    assert len(concernes) >= 100, (
        f"seulement {len(concernes)} bancs dependent de `textual` ou du "
        "paquet `tui`. Si ce cardinal s'effondre, la prose de "
        "`contribuer.md` surestime l'enjeu et doit etre reprise."
    )
