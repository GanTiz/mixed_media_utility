# -*- coding: utf-8 -*-
"""Finding `C2-1` -- `Tab journal` montre quelque chose AU PLANCHER.

**Le defaut, mesure par la couche 2 de la revue de la calibration du
2026-09-06** : au plancher 80x24, le cartouche d'une passe de calibration
occupe **17 des 17 lignes** de la zone centrale. `EcranResultat` annonce
pourtant `Tab journal` dans son pied des qu'un journal lui est passe, et
`lignes_de_journal_visibles` rendait alors zero -- la touche etait annoncee,
consommee, et ne montrait rien. Le journal n'apparaissait qu'a partir de
**28 lignes de terminal**, c'est-a-dire jamais sur le format que le depot
tient pour plancher.

Une touche annoncee qui ne fait rien visiblement se lit comme une panne :
c'est `EPIC11-ARB-58`, que le docstring de `basculer_le_journal` invoque
lui-meme. Et c'est la troisieme fois que ce motif se paie sur cette famille
d'ecrans, apres les deux volets du finding `I8`.

La sortie retenue est celle qu'`EcranExecution` a deja tranchee pour la meme
zone et le meme plancher -- « deplie, le journal prend la place de la liste ».

**Le drapeau VARIE dans les deux sens**, et c'est ce qui distingue ce banc
d'une mesure a moitie : replie, le cartouche doit sortir ENTIER. Un correctif
qui rognerait le cartouche en permanence serait vert sous la seule moitie
bruyante, et il ferait perdre trois lignes de compte rendu aux ecrans qui
avaient la place.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RACINE / "src"))

from mixed_media_utility.tui import jetons
from mixed_media_utility.tui.avancement import Journal
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin
from mixed_media_utility.tui.execution import (LIGNES_MINIMALES_DU_JOURNAL,
                                               EcranResultat)
from mixed_media_utility.tui.panneau import LigneChiffree, Panneau

#: Le plancher d'`EPIC11-ARB-21`, ecrit en clair : le relire de `jetons`
#: rendrait la mesure tautologique.
PLANCHER = (80, 24)

#: Le cardinal qui remplit la zone centrale au plancher. `hauteur_centrale(24)`
#: vaut 17 ; un cartouche de 20 lignes la deborde donc franchement, ce qui est
#: le regime de la calibration mesure par la revue.
LIGNES_DU_CARTOUCHE = 20


def _panneau_qui_remplit() -> Panneau:
    """Un cartouche a 20 lignes CHIFFREES ET DISTINGUABLES.

    Vingt libelles differents plutot qu'un remplissage uniforme : c'est la
    regle des fabriques du depot, et elle porte ici -- un fenetrage qui
    garderait la QUEUE au lieu de la TETE resterait vert sur des lignes
    identiques.
    """
    return Panneau("Calibration consignee",
                   [LigneChiffree(f"mesure {rang:02d}", rang, "px")
                    for rang in range(1, LIGNES_DU_CARTOUCHE + 1)])


def _journal_garni() -> Journal:
    journal = Journal()
    for rang in range(1, 9):
        journal.inscrire(f"ligne de journal {rang}")
    return journal


def _ecran() -> EcranResultat:
    return EcranResultat(_panneau_qui_remplit(), ["Revenir"],
                         journal=_journal_garni())


def _app(ecran) -> CoqueTui:
    return CoqueTui([PalierTemoin("Ateliers", "Q quitter"), ecran],
                    Contexte("projet", "Scan"))


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_C2_1_au_PLANCHER_Tab_journal_MONTRE_le_journal(banc,
                                                        ascii_seul) -> None:
    """Le defaut lui-meme, dans les deux modes de rendu."""
    ecran = _ecran()
    app = _app(ecran)
    app.ascii_seul = ascii_seul

    async def scenario(pilote):
        ecran.journal_deplie = True
        return ecran.lignes(), ecran.lignes_de_journal_visibles()

    lignes, visibles = banc(app, scenario, PLANCHER)
    assert visibles >= LIGNES_MINIMALES_DU_JOURNAL, (
        f"le journal deplie n'a que {visibles} ligne(s) au plancher")
    inscrites = [ligne for ligne in lignes if "ligne de journal" in ligne]
    assert len(inscrites) >= LIGNES_MINIMALES_DU_JOURNAL, lignes
    # La plus RECENTE est celle qu'on vient lire : un journal qui montrerait
    # ses plus anciennes lignes montrerait le mauvais bout.
    assert "ligne de journal 8" in inscrites[-1]


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_C2_1_le_cartouche_fenetre_DIT_qu_il_est_abrege(banc,
                                                        ascii_seul) -> None:
    """L'abregement se dit, sans quoi on lit un compte rendu tronque.

    Et il garde la TETE : les premieres mesures sont celles que le cartouche
    met en avant. Vingt libelles distincts font que ce test tomberait sur un
    fenetrage qui garderait la queue.
    """
    ecran = _ecran()
    app = _app(ecran)
    app.ascii_seul = ascii_seul

    async def scenario(pilote):
        ecran.journal_deplie = True
        return ecran.cartouche()

    cartouche = banc(app, scenario, PLANCHER)
    assert len(cartouche) < LIGNES_DU_CARTOUCHE, (
        "au plancher, le cartouche DOIT ceder de la place au journal deplie")
    assert cartouche[-1].strip() == jetons.points_d_abregement(ascii_seul)
    assert any("mesure 01" in ligne for ligne in cartouche)
    assert not any("mesure 20" in ligne for ligne in cartouche)


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_C2_1_REPLIE_le_cartouche_sort_ENTIER(banc, ascii_seul) -> None:
    """L'autre sens du drapeau -- la moitie qui protege les trois ecrans
    qui avaient deja la place.

    Sans lui, un correctif qui rognerait le cartouche en permanence serait
    vert sur toute la moitie bruyante de ce banc.
    """
    ecran = _ecran()
    app = _app(ecran)
    app.ascii_seul = ascii_seul

    async def scenario(pilote):
        assert ecran.journal_deplie is False, (
            "le journal n'est jamais deplie au montage")
        return ecran.cartouche(), ecran.lignes()

    cartouche, lignes = banc(app, scenario, PLANCHER)
    assert len(cartouche) == LIGNES_DU_CARTOUCHE
    assert any("mesure 20" in ligne for ligne in cartouche)
    assert not any(ligne.strip() == jetons.points_d_abregement(ascii_seul)
                   for ligne in cartouche)
    assert not [ligne for ligne in lignes if "ligne de journal" in ligne]


def test_C2_1_le_curseur_suit_le_cartouche_AFFICHE(banc) -> None:
    """Le piege que le fenetrage ouvre, et qu'aucun autre banc ne verrait.

    `rang_du_curseur` derivait du cartouche ENTIER. Fenetre, il aurait peint
    la couleur du curseur plusieurs lignes sous la suite qu'il designe -- ou
    hors du bloc, c'est-a-dire nulle part. Le rang se mesure donc sur les
    lignes que `lignes()` rend reellement, et pas sur une seconde arithmetique.
    """
    ecran = _ecran()
    app = _app(ecran)

    async def scenario(pilote):
        ecran.journal_deplie = True
        return ecran.lignes(), ecran.rang_du_curseur()

    lignes, rang = banc(app, scenario, PLANCHER)
    assert rang is not None
    assert 0 <= rang < len(lignes)
    assert "Revenir" in lignes[rang]
