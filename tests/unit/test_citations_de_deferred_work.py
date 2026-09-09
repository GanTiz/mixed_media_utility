# -*- coding: utf-8 -*-
"""Finding `C9` -- une entree de dette citee par le code EXISTE dans le fichier.

Le defaut d'origine : le docstring de `scan_calibrate.calibrer_la_chaine`
renvoyait a « `deferred-work.md`, entree du 2026-09-06 ». Le fichier porte
bien la dette -- c'est `CALIB-N1` --, mais aucune de ses entrees ne s'appelle
« du 2026-09-06 », et un lecteur qui la cherchait sous ce nom ne la trouvait
pas. C'est la meme famille que la reference d'arbitrage perimee que CLAUDE.md
relate : une citation ne se mesure pas plus qu'une regle non portee.

**Ce que cette frontiere mesure** : tout identifiant d'entree cite dans un
voisinage de `deferred-work.md`, dans `src/`, se retrouve dans le fichier.

**Ce qu'elle NE mesure PAS, dit plutot que tu** :

* elle ne voit pas une citation faite en PROSE, sans identifiant -- c'est
  exactement la forme qu'avait `C9`. Elle empeche la recidive sous forme
  nommee, pas la premiere occurrence sous forme anonyme. La vraie fermeture de
  `C9` est le correctif lui-meme : la citation porte desormais `CALIB-N1` ;
* elle ne verifie pas que l'identifiant designe un **titre** : les entrees du
  fichier vivent a trois niveaux de titre et deux d'entre elles sont en gras
  de debut de ligne. Exiger un niveau ferait rougir du contenu correct.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
DETTE = RACINE / "_bmad-output" / "implementation-artifacts" / "deferred-work.md"

#: La fenetre autour de `deferred-work.md` ou un identifiant est reput cite.
#: Assez large pour couvrir un paragraphe de docstring, assez etroite pour ne
#: pas ramasser un identifiant d'une autre phrase.
FENETRE = 300

#: La forme d'un identifiant d'entree : au moins deux segments majuscules.
IDENTIFIANT = re.compile(r"`([A-Z][A-Z0-9]*(?:-[A-Z0-9]+){1,3})`")

#: Les numeros d'arbitrage ne vivent PAS ici : ils vivent dans les
#: `decisions-<date>-<epic>.md`. Un docstring qui cite les deux dans la meme
#: phrase est frequent, et exiger l'arbitrage dans le fichier de dette serait
#: mesurer le mauvais fichier.
ARBITRAGE = re.compile(r"^EPIC\d+-ARB-\d+$")


def _citations() -> dict[str, set[str]]:
    citees: dict[str, set[str]] = {}
    for source in sorted(RACINE.glob("src/**/*.py")):
        texte = source.read_text(encoding="utf-8")
        for marque in re.finditer(r"deferred-work\.md", texte):
            fenetre = texte[max(0, marque.start() - FENETRE):
                            marque.end() + FENETRE]
            for identifiant in IDENTIFIANT.findall(fenetre):
                if ARBITRAGE.match(identifiant):
                    continue
                citees.setdefault(identifiant, set()).add(
                    source.relative_to(RACINE).as_posix())
    return citees


@pytest.mark.skipif(not DETTE.is_file(), reason="deferred-work.md absent")
def test_C9_toute_entree_de_dette_citee_par_le_code_EXISTE() -> None:
    citees = _citations()
    # Le volet symetrique, sans lequel la frontiere serait verte sur un `src/`
    # vide ou sur une expression reguliere cassee : au 2026-09-07 le depot en
    # porte neuf, et `CALIB-N1` est celle que `C9` a fait naitre.
    assert len(citees) >= 5, (
        f"la frontiere ne trouve plus de citation a mesurer : {sorted(citees)}")
    assert "CALIB-N1" in citees

    texte = DETTE.read_text(encoding="utf-8")
    absentes = sorted(identifiant for identifiant in citees
                      if identifiant not in texte)
    assert not absentes, (
        "ces entrees sont citees par le code et n'existent nulle part dans "
        + f"deferred-work.md : "
        + ", ".join(f"{i} (cite par {sorted(citees[i])})" for i in absentes))
