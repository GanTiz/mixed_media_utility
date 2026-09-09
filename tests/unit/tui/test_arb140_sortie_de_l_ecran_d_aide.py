# -*- coding: utf-8 -*-
"""`EPIC11-ARB-140`, geste 2 -- `Echap` SORT des ecrans de PASSAGE.

**Le cul-de-sac que ce banc ferme.** `F1` empile un ecran par-dessus n'importe
quel autre. Jusqu'ici `Echap` n'y depilait pas, et pour **deux** raisons
distinctes -- ce qui est le point : un seul correctif les ferme, mais un seul
test ne les aurait pas vues.

* **pendant une tache** : `CoqueTui.action_remonter` voit `tache_en_cours`,
  arme `interruption_demandee` et rend la main sans depiler. L'operateur qui
  demande l'aide devait donc declencher une **interruption** pour en sortir ;
* **a la racine** : `rang` compte les paliers, et l'ecran d'aide est un
  passage. `rang == 0`, donc `if self.rang > 0` ne depile pas non plus.

**Ce banc est la CONDITION du geste 1** (`test_arb140_passages_sans_q_quitter`,
qui annonce `F1 aide` sur six ecrans au lieu de deux) : sans lui, l'alignement
des lignes de raccourcis porterait le cul-de-sac de **deux** ecrans a **six**.

**RETARGETE le 2026-09-03, story 11.9 lot D -- et ELARGI plutot que deplace.**
Ce banc visait `coque.EcranPasEncore`, parce que c'est ce que `F1` empilait
quand l'arbitrage a ete tranche. Le lot C a livre le manuel, et `action_aide`
empile desormais `ecran_manuel.EcranManuel`. Viser le nouvel ecran **a la
place** de l'ancien aurait laisse `EcranPasEncore` sans mesure : il reste
atteignable par « La suite de X » (`descendre` au dernier palier), sa sortie
`Echap` est toujours traitee localement, et plus rien n'aurait rougi si elle
partait. C'est le defaut symetrique que `CLAUDE.md` nomme a la liaison -- « une
mesure portee sans son module ». Les deux passages sont donc mesures **cote a
cote**, par le meme scenario, dans les deux memes regimes.

**Les deux sens sont mesures, et le second n'est pas decoratif.** Le depot
porte le cas d'ecole : une fermeture du 2026-09-01 a pose `tache_en_cours` et
a, ce faisant, empeche `action_remonter` de depiler -- le filet de demontage de
l'ecran de collision ne se declenchait plus jamais, c'est-a-dire exactement la
panne qu'il existait pour ecarter. Un correctif qui rendrait l'aide sortable en
rendant l'**interruption** inatteignable serait la meme faute par l'autre bout.
"""
from __future__ import annotations

import pytest

from mixed_media_utility.tui.coque import (
    Contexte,
    CoqueTui,
    EcranPasEncore,
    PalierTemoin,
)
from mixed_media_utility.tui.ecran_manuel import EcranManuel
from mixed_media_utility.tui.execution import (
    EcranExecution,
    EcranInterruption,
    SurfaceExecution,
)


def coque() -> CoqueTui:
    """Deux paliers temoins : la racine et le menu des ateliers."""
    return CoqueTui(paliers=[PalierTemoin("Projet", "⏎ ouvrir  Q quitter"),
                             PalierTemoin("Ateliers", "⏎ entrer  Q quitter")],
                    contexte=Contexte("projet_demo"))


def coque_sans_suite() -> CoqueTui:
    """UN seul palier -- `descendre()` y rend donc `EcranPasEncore`.

    C'est le chemin REEL de cet ecran (`CoqueTui.descendre`, branche
    « rang + 1 >= len(paliers) »), pas un `push_screen` de sonde : un empilement
    direct mesurerait le banc plutot que le produit.
    """
    return CoqueTui(paliers=[PalierTemoin("Projet", "⏎ ouvrir  Q quitter")],
                    contexte=Contexte("projet_demo"))


async def _ouvrir_le_manuel(pilote) -> None:
    """`F1`, par le CLAVIER : c'est le geste de l'operateur."""
    await pilote.press("f1")


async def _ouvrir_la_suite_de_x(pilote) -> None:
    """`descendre()`, par l'API.

    Le clavier n'est pas uniforme entre les deux passages -- `⏎` sur un ecran
    d'execution ne descend pas --, et `descendre()` est justement ce que
    `PalierTemoin.on_key` appelle. On mesure donc le meme chemin, pris un cran
    plus bas.
    """
    pilote.app.descendre()


#: Les DEUX passages que ce banc tient cote a cote, avec de quoi les ouvrir.
#: Deux et non un : le geste 1 (`test_arb140_passages_sans_q_quitter`) mesure
#: un ensemble de passages, et un cul-de-sac ferme sur un seul d'entre eux
#: n'est pas ferme.
PASSAGES = [
    pytest.param(EcranManuel, coque, _ouvrir_le_manuel, id="manuel-par-F1"),
    pytest.param(EcranPasEncore, coque_sans_suite, _ouvrir_la_suite_de_x,
                 id="pas-encore-par-la-suite-de-X"),
]


def execution_montee() -> EcranExecution:
    surface = SurfaceExecution("frames")
    surface.emetteur(124)
    return EcranExecution(surface, "Extraction en cours")


@pytest.mark.parametrize("classe,fabrique,ouvrir", PASSAGES)
def test_echap_sur_un_passage_pendant_une_tache_DEPILE_sans_toucher_a_la_tache(
        banc, classe, fabrique, ouvrir):
    """Le cul-de-sac, ferme -- sur les DEUX passages.

    Avant : le passage etait empile, `Echap` remontait a l'application, qui
    voyait `tache_en_cours` et armait `interruption_demandee` **sans depiler**.
    L'operateur qui demandait l'aide devait donc declencher une interruption
    pour en sortir -- et l'ecran restait monte.

    Les trois observables, et il faut les trois : on est redescendu sur
    l'execution, la tache n'a pas ete touchee, et **aucune** interruption n'a
    ete armee au passage.
    """
    ecran = execution_montee()

    async def scenario(pilote):
        app = pilote.app
        app.descendre(ecran)
        await pilote.pause()
        await ouvrir(pilote)
        await pilote.pause()
        sur_le_passage = isinstance(app.screen, classe)
        await pilote.press("escape")
        await pilote.pause()
        return (sur_le_passage, type(app.screen).__name__,
                app.tache_en_cours, app.interruption_demandee)

    sur_le_passage, apres, tache, interruption = banc(fabrique(), scenario)
    assert sur_le_passage, (
        f"le passage {classe.__name__} ne s'est pas ouvert : la sonde ne "
        "mesure rien")
    assert apres == "EcranExecution", apres
    assert tache is True, "`Echap` sur le passage a touche a la tache"
    assert interruption is False, "`Echap` sur le passage a arme une interruption"


def test_l_interruption_reste_atteignable_APRES_avoir_ferme_l_aide(banc):
    """Le sens symetrique, et c'est lui qui garde le correctif honnete.

    Le depot porte le cas d'ecole : une fermeture du 2026-09-01 a pose
    `tache_en_cours` et a, ce faisant, empeche `action_remonter` de depiler --
    le filet de demontage ne se declenchait plus jamais. Un correctif qui rend
    l'aide sortable en rendant l'interruption **inatteignable** serait la meme
    faute par l'autre bout.
    """
    ecran = execution_montee()

    async def scenario(pilote):
        app = pilote.app
        app.descendre(ecran)
        await pilote.pause()
        await pilote.press("f1")
        await pilote.pause()
        await pilote.press("escape")     # on ferme l'aide
        await pilote.pause()
        await pilote.press("escape")     # on veut vraiment interrompre
        await pilote.pause()
        return type(app.screen).__name__

    assert banc(coque(), scenario) == EcranInterruption.__name__


def test_action_remonter_arme_TOUJOURS_l_interruption_hors_de_l_ecran_d_aide(banc):
    """Le correctif ne vaut QUE pour l'ecran d'aide, et rien d'autre.

    Sans ce volet, une correction qui depilerait tout passage pendant une tache
    passerait pour juste : elle rendrait l'aide sortable ET casserait la garde
    d'`EPIC11-ARB-4`, sans qu'aucun des deux tests ci-dessus ne rougisse.
    """
    async def scenario(pilote):
        app = pilote.app
        app.descendre(execution_montee())
        await pilote.pause()
        rang_avant = app.rang
        app.action_remonter()            # l'appel direct, pas la touche
        await pilote.pause()
        return app.interruption_demandee, app.rang == rang_avant

    arme, sur_place = banc(coque(), scenario)
    assert arme is True, "la garde d'une tache en cours a saute"
    assert sur_place, "`action_remonter` a depile pendant une tache"


@pytest.mark.parametrize("classe,fabrique,ouvrir", PASSAGES)
def test_echap_sort_d_un_passage_AUSSI_a_la_racine_ou_aucune_tache_ne_tourne(
        banc, classe, fabrique, ouvrir):
    """Le second cul-de-sac de la meme touche, ferme du meme geste.

    A la racine, `rang` vaut 0 -- un passage ne compte pas comme palier --,
    donc `action_remonter` ne depilait pas davantage, sans qu'aucune tache soit
    en cause. La sortie ne depend donc plus de l'endroit d'ou on l'a demandee.
    """
    async def scenario(pilote):
        app = pilote.app
        await ouvrir(pilote)
        await pilote.pause()
        sur_le_passage = isinstance(app.screen, classe)
        await pilote.press("escape")
        await pilote.pause()
        return sur_le_passage, app.rang, isinstance(app.screen, classe)

    sur_le_passage, rang, encore = banc(fabrique(), scenario)
    assert sur_le_passage, (
        f"le passage {classe.__name__} ne s'est pas ouvert : la sonde ne "
        "mesure rien")
    assert rang == 0, "la sonde n'etait pas a la racine"
    assert not encore, "`Echap` n'a pas depile le passage a la racine"
