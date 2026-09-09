# -*- coding: utf-8 -*-
"""Aucun workflow ne se declenche sur un `push` de branche.

**Ce que cette frontiere ferme, et le prix en est connu a la minute.** Le
2026-09-02, `ci.yml` partait sur `push: branches: ["**"]` plus
`pull_request` : cinq jobs a chaque push de chaque branche, dont TROIS suites
completes (Python 3.11, 3.12, 3.13). Avec plusieurs agents qui poussent en
continu, il a consomme **3062 minutes sur 231 runs** pour le seul mois de
septembre -- la quasi-totalite des **3074 minutes** incluses du compte, en une
journee. `docs.yml` en a pris 12 de plus.

GitHub a ensuite refuse de demarrer les jobs (« The job was not started because
recent account payments have failed or your spending limit needs to be
increased »), et le depot a accumule des centaines de runs rouges qui ne
mesuraient rien : duree 2 s, `runner_id` a 0, logs en 404, 0 ms facturee.

Consigne d'Egan du 2026-09-02, verbatim : « je ne veux pas que ces runs
tournent a chaque push ! On pushe constamment. Il faut qu'ils tournent quand on
les lance deliberement et pour les releases. »

**Pourquoi une frontiere et non un commentaire.** Le commentaire existe deja en
tete des deux fichiers. Mais un declencheur `push` se reintroduit en trois
lignes, par un agent qui trouvera normal qu'une CI parte sur les pushes -- c'est
la configuration par defaut de tout le monde. Rien ne le signalerait avant la
prochaine facture. Ce qui se mesure se tient ; ce qui se rappelle se perd.

**Le piege que ce banc doit eviter lui-meme** : les commentaires de ces fichiers
CITENT la configuration retiree, en toutes lettres. Un `grep` naif sur le texte
brut rougirait sur sa propre explication. La lecture se fait donc sur le bloc
`on:` analyse, jamais sur le fichier entier.
"""

from __future__ import annotations

from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
WORKFLOWS = RACINE / ".github" / "workflows"

#: Les seuls declencheurs admis. `workflow_dispatch` est le lancement delibere ;
#: `push` n'est admis que restreint a des TAGS, ce qui est le chemin de release.
DECLENCHEURS_ADMIS = {"workflow_dispatch", "push", "workflow_call"}


def _bloc_on(texte: str) -> list[str]:
    """Les lignes du bloc `on:` d'un workflow, commentaires exclus.

    Un fichier YAML de workflow tient son bloc `on:` a la colonne zero, et le
    bloc s'acheve a la premiere autre cle de colonne zero. L'analyse par
    indentation suffit pour la question posee.

    PREMISSE CORRIGEE le 2026-09-08 (story 8.10). Cette place disait « on
    n'importe pas `yaml` : il n'est pas une dependance du depot ». La seconde
    moitie est devenue FAUSSE ce jour-la : `pyyaml>=6.0` est desormais declare
    dans l'extra `[test]` de `pyproject.toml` et dans `requirements.txt`.

    Le choix, lui, ne change pas -- et il vaut mieux qu'avant, parce qu'il ne
    depend plus d'une absence. Ne rien importer du tout est ce qui ne peut
    JAMAIS sauter : c'est vrai quelle que soit la fermeture des dependances du
    jour. Le motif d'origine etait defensif ; celui-ci est structurel.
    """
    lignes, dedans = [], False
    for ligne in texte.splitlines():
        depouillee = ligne.strip()
        if depouillee.startswith("#") or not depouillee:
            continue
        if ligne.startswith("on:"):
            dedans = True
            continue
        if dedans and not ligne.startswith((" ", "\t")):
            break
        if dedans:
            lignes.append(ligne)
    return lignes


def _fichiers_de_workflow():
    trouves = sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))
    assert len(trouves) >= 2, (
        f"Moins de deux workflows trouves dans {WORKFLOWS} : l'enumeration est "
        "cassee, et un banc qui ne parcourt rien passe toujours."
    )
    return trouves


@pytest.mark.parametrize("chemin", _fichiers_de_workflow(),
                         ids=lambda p: p.name)
def test_aucun_workflow_ne_part_sur_un_push_de_BRANCHE(chemin):
    """FRONTIERE NEGATIVE : c'est le declencheur RETIRE qu'on surveille.

    Aucun test positif ne verrait revenir `push: branches:`. Un workflow qui
    part sur les pushes est parfaitement bien forme, il tourne, il est vert --
    il coute simplement 3062 minutes par mois sur un depot prive.

    La cle `branches` n'est refusee que SOUS `push`. Sous `pull_request` la
    question ne se pose pas, ce declencheur etant lui-meme retire, et un
    `push: tags:` reste admis : c'est le chemin de release voulu.
    """
    lignes = _bloc_on(chemin.read_text(encoding="utf-8"))
    assert lignes, f"{chemin.name} n'a pas de bloc `on:` analysable."

    sous_push = False
    for ligne in lignes:
        depouillee = ligne.strip()
        indentation = len(ligne) - len(ligne.lstrip())
        if indentation <= 2 and depouillee.rstrip(":") in DECLENCHEURS_ADMIS:
            sous_push = depouillee.rstrip(":") == "push"
            continue
        if indentation <= 2:
            pytest.fail(
                f"{chemin.name} declare le declencheur {depouillee!r}, hors des "
                f"declencheurs admis {sorted(DECLENCHEURS_ADMIS)}. Consigne "
                "d'Egan du 2026-09-02 : lancement delibere et releases."
            )
        if sous_push and depouillee.startswith("branches"):
            pytest.fail(
                f"{chemin.name} repart sur un push de BRANCHE ({depouillee!r}). "
                "Voir la docstring de ce module : cette configuration a consomme "
                "3062 des 3074 minutes incluses du compte en une journee. Une "
                "release se declenche par `push: tags:`, jamais par branche."
            )


@pytest.mark.parametrize("chemin", _fichiers_de_workflow(),
                         ids=lambda p: p.name)
def test_chaque_workflow_reste_lancable_A_LA_MAIN(chemin):
    """Le symetrique, sans lequel la frontiere precedente serait destructrice.

    Interdire le declenchement automatique sans garantir le declenchement
    manuel rendrait un workflow INJOIGNABLE -- une CI qu'on ne peut plus lancer
    ne vaut pas mieux qu'une CI qui ruine le budget. Les deux moities se
    mesurent ensemble, comme un module et son banc.
    """
    lignes = _bloc_on(chemin.read_text(encoding="utf-8"))
    declencheurs = {
        ligne.strip().rstrip(":") for ligne in lignes
        if (len(ligne) - len(ligne.lstrip())) <= 2
    }
    assert "workflow_dispatch" in declencheurs, (
        f"{chemin.name} n'est plus lancable a la main : ses declencheurs sont "
        f"{sorted(declencheurs)}. Ajouter `workflow_dispatch:`."
    )
