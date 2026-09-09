# -*- coding: utf-8 -*-
"""Story 11.0, AC 8 -- le banc headless, qui sert aux neuf stories suivantes."""

import os
import subprocess
import sys

from textual.containers import Vertical
from textual.widgets import Static

from mixed_media_utility.tui import jetons
from mixed_media_utility.tui.coque import CoqueTui

#: Les variables d'affichage que le banc ne doit PAS reclamer. `DISPLAY` est
#: celle d'X11, `QT_QPA_PLATFORM` celle que le banc GUI doit forcer -- la citer
#: ici dit exactement ce que ce banc-la n'a pas a faire.
VARIABLES_D_AFFICHAGE = ("DISPLAY", "WAYLAND_DISPLAY", "QT_QPA_PLATFORM")

#: Programme joue dans un processus a l'environnement lave. Il monte la coque
#: et rend les identifiants de l'arbre : s'il imprime la liste, le banc a
#: tourne sans le moindre peripherique d'affichage.
PROGRAMME_SANS_ECRAN = """
import asyncio, sys
sys.path.insert(0, "src")
from mixed_media_utility.tui.coque import CoqueTui

async def tour():
    app = CoqueTui()
    async with app.run_test(size=(80, 24)) as pilote:
        return sorted(w.id for w in app.screen.walk_children() if w.id)

print(",".join(asyncio.run(tour())))
"""


def test_le_banc_monte_au_plancher_et_rend_le_pilote(banc):
    """AC 8.1 : la taille par defaut du banc EST le plancher."""
    async def scenario(pilote):
        return pilote.app.size

    assert tuple(banc(CoqueTui(), scenario)) == (
        jetons.LARGEUR_PLANCHER, jetons.HAUTEUR_PLANCHER)


def test_le_banc_accepte_une_autre_taille(banc):
    """La taille est un argument : les stories suivantes testent au-dessus du
    plancher sans reecrire le banc."""
    async def scenario(pilote):
        return tuple(pilote.app.size)

    assert banc(CoqueTui(), scenario, taille=(120, 40)) == (120, 40)


def test_le_banc_rend_ce_que_le_scenario_rend(banc):
    """AC 8.1 : la valeur traverse -- sinon rien ne serait observable.

    Deux valeurs de nature differente, pour qu'un banc qui rendrait toujours
    la meme chose (le pilote, `None`, un booleen) se demasque.
    """
    async def rend_un_nombre(_pilote):
        return 42

    async def rend_un_texte(_pilote):
        return "lot_25fps"

    assert banc(CoqueTui(), rend_un_nombre) == 42
    assert banc(CoqueTui(), rend_un_texte) == "lot_25fps"


def test_une_assertion_porte_sur_l_arbre_de_widgets_et_pas_sur_du_texte(banc):
    """AC 8.3 : on demande QUEL widget porte quoi, pas ce que l'ecran affiche.

    Une capture de texte dirait que « Ateliers » est quelque part a l'ecran ;
    elle ne dirait pas que c'est le bandeau qui le porte, ni que la zone
    centrale est un conteneur vertical et non une grille.
    """
    async def scenario(pilote):
        app = pilote.app
        app.descendre()
        await pilote.pause()
        centre = app.screen.query_one("#centre")
        return {
            "bandeau": type(app.screen.query_one("#bandeau")).__name__,
            "centre": type(centre).__name__,
            "porteur_du_titre": app.screen.query_one("#bandeau", Static).content,
            "enfants_du_centre": [type(e).__name__ for e in centre.children],
        }

    arbre = banc(CoqueTui(), scenario)
    assert arbre["bandeau"] == Static.__name__
    assert arbre["centre"] == Vertical.__name__
    assert "Ateliers" in arbre["porteur_du_titre"]
    assert arbre["enfants_du_centre"] == [Static.__name__]


def test_le_banc_tourne_sans_aucune_variable_d_affichage(racine_depot):
    """AC 8.2 : mesure par execution reelle dans un environnement lave.

    Le processus fils ne recoit ni `DISPLAY`, ni `WAYLAND_DISPLAY`, ni
    `QT_QPA_PLATFORM`. C'est la difference de fond avec le banc GUI, qui doit
    forcer une plateforme Qt ; ici, il n'y a rien a forcer.
    """
    environnement = {c: v for c, v in os.environ.items()
                     if c not in VARIABLES_D_AFFICHAGE}
    resultat = subprocess.run([sys.executable, "-c", PROGRAMME_SANS_ECRAN],
                              cwd=racine_depot, env=environnement,
                              capture_output=True, text=True, timeout=120)
    assert resultat.returncode == 0, resultat.stderr
    assert resultat.stdout.strip() == "bandeau,centre,etat,raccourcis"


def test_l_environnement_lave_est_bien_lave():
    """Volet symetrique du precedent : la mesure retire vraiment les variables.

    Sans lui, un filtre qui ne filtrerait rien laisserait le test passer sur
    une machine qui a un ecran -- c'est-a-dire toutes celles ou on l'ecrit.
    """
    environnement = {c: v for c, v in os.environ.items()
                     if c not in VARIABLES_D_AFFICHAGE}
    assert not (set(environnement) & set(VARIABLES_D_AFFICHAGE))
    assert len(environnement) < len(os.environ) or not (
        set(os.environ) & set(VARIABLES_D_AFFICHAGE))
