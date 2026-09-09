# -*- coding: utf-8 -*-
"""Vague 1 bis -- la touche annoncee n'est jamais inerte, meme collee a `Echap`.

**Ce que ces tests mesurent, et pourquoi ils ne ressemblent a aucun autre.**
Tous les tests de clavier du depot passent par `pilote.press("q")`, qui
**injecte l'evenement `Key` deja construit** et court-circuite le pilote de
terminal. Or c'est precisement la que le defaut vivait : `Echap` emet `\\x1b`,
qui est aussi le prefixe de toute sequence d'echappement, et le parseur de
`textual` colle a l'echappement toute touche arrivant dans la fenetre
`ESCDELAY`. Mesure faite sur le parseur lui-meme le 2026-08-28 :

* `Echap` puis `q` rend **`alt+q`** ;
* `Echap` puis `Entree` rend `enter` seul, l'echappement etant perdu.

Une touche annoncee en ligne de raccourcis devenait donc **inerte**, et aucun
test ne pouvait le voir. Ces tests injectent donc le nom de touche **tel que le
parseur le produit**, pas tel qu'on le tape.

**Reserve d'Egan, 2026-08-28** : il a observe le meme blocage en attendant bien
plus que la fenetre de 100 ms, ce que ce mecanisme seul n'explique pas. Ces
tests ferment ce qui est mesure ; ils ne pretendent pas fermer tout le symptome.
"""

import ast
from pathlib import Path

import pytest
from textual import events

from mixed_media_utility.tui.coque import CoqueTui


def _frapper(app, nom_de_touche: str, caractere: str | None = None) -> None:
    """Poste une touche **telle que le parseur la produit**, pas telle qu'on la tape."""
    app.post_message(events.Key(nom_de_touche, caractere))


# -- la fonction pure ------------------------------------------------------


@pytest.mark.parametrize("recue, attendue", [
    ("alt+q", "q"),
    ("alt+enter", "enter"),
    ("alt+escape", "escape"),
    ("q", "q"),
    ("enter", "enter"),
    ("alt+alt+q", "alt+q"),
])
def test_le_prefixe_d_echappement_est_retire_une_fois_et_une_seule(recue, attendue):
    """Un seul prefixe est retire : `alt+alt+q` n'est pas `q`.

    Le cas double n'est pas theorique -- c'est ce que produirait un echappement
    suivi d'un second echappement suivi d'une touche. En retirer autant qu'il y
    en a reviendrait a rendre indistinguables deux frappes differentes, et le
    volet ci-dessus (`q` inchange) mesure qu'on ne retire rien quand il n'y a
    rien a retirer.
    """
    assert CoqueTui.normaliser(recue) == attendue


# -- l'effet reel sur l'application ----------------------------------------


def test_entree_collee_a_un_echappement_descend_quand_meme(banc):
    """`alt+enter` navigue comme `enter`, sur les DEUX transitions.

    Deux transitions et non une : une normalisation qui n'agirait qu'au premier
    etage passerait un test a une seule pression.
    """
    async def scenario(pilote):
        etapes = []
        for _ in range(2):
            _frapper(pilote.app, "alt+enter", "\r")
            await pilote.pause()
            etapes.append((pilote.app.rang, pilote.app.screen.titre))
        return etapes

    assert banc(CoqueTui(), scenario) == [(1, "Ateliers"), (2, "Extraction")]


def test_echappement_colle_a_un_echappement_remonte_quand_meme(banc):
    """`alt+escape` remonte comme `escape`, et d'UN palier."""
    async def scenario(pilote):
        for _ in range(2):
            _frapper(pilote.app, "alt+enter", "\r")
            await pilote.pause()
        depart = pilote.app.rang
        _frapper(pilote.app, "alt+escape", "\x1b")
        await pilote.pause()
        return depart, pilote.app.rang

    assert banc(CoqueTui(), scenario) == (2, 1)


def test_q_colle_a_un_echappement_quitte_quand_meme(banc):
    """`alt+q` quitte. C'est le cas exact qu'Egan a observe comme inerte."""
    async def scenario(pilote):
        _frapper(pilote.app, "alt+q", "q")
        await pilote.pause()
        await pilote.pause()
        return pilote.app._running

    assert banc(CoqueTui(), scenario) is False


def test_une_touche_non_collee_traverse_inchangee(banc):
    """Volet symetrique : la normalisation ne touche pas ce qui n'a pas de prefixe.

    Sans ce volet, une normalisation qui renverrait n'importe quoi -- ou qui
    mangerait des caracteres -- passerait les trois tests ci-dessus.
    """
    async def scenario(pilote):
        _frapper(pilote.app, "enter", "\r")
        await pilote.pause()
        return pilote.app.rang, pilote.app.screen.titre

    assert banc(CoqueTui(), scenario) == (1, "Ateliers")


# -- la frontiere qui protege la normalisation -----------------------------


def test_aucune_touche_alt_n_est_liee_dans_la_tui(sources_tui):
    """La normalisation ne prend la place de rien -- et ca se mesure.

    Traiter `alt+X` comme `X` n'est defendable **que** parce qu'aucune touche
    `alt+` n'est liee : `DESIGN.md` n'emploie `Alt` dans aucune maquette ni
    aucune ligne de raccourcis. Si quelqu'un en liait une un jour, elle
    deviendrait silencieusement inatteignable. Ce test le fait rougir a la
    place.

    Le balayage porte sur les **chaines litterales** de tout le paquet, via
    l'AST : chercher dans le texte brut ferait rougir sur ce docstring-ci.

    Le prefixe **nu** est exclu : `PREFIXE_ECHAPPEMENT = "alt+"` est ce qui
    fait la normalisation, pas une touche liee. On ne cherche donc que les
    chaines qui nomment reellement une touche, c'est-a-dire plus longues que le
    prefixe.
    """
    prefixe = CoqueTui.PREFIXE_ECHAPPEMENT
    coupables = []
    for chemin in sources_tui:
        arbre = ast.parse(Path(chemin).read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str):
                if noeud.value.startswith(prefixe) and len(noeud.value) > len(prefixe):
                    coupables.append((Path(chemin).name, noeud.value))
    assert coupables == [], (
        "une touche `alt+` est liee dans la TUI ; la normalisation de "
        f"`CoqueTui.on_event` la rendrait inatteignable : {coupables}")


def test_abandonner_une_edition_marche_meme_colle_a_un_echappement(banc):
    """En edition, `alt+escape` abandonne comme `escape`.

    **C'est ici que le mode d'edition rend le defaut le plus couteux.** Le mode
    consomme TOUT -- c'est ce qui empeche `q` de quitter en pleine saisie. Une
    touche nommee arrivee prefixee y est donc consommee **sans rien faire** :
    l'operateur appuie sur `Echap` pour renoncer a sa saisie, et il ne se passe
    rien du tout, sans le moindre message.

    Premiere version de ce test, retiree : elle mesurait `alt+b` ecrivant un
    `b`. **Elle etait inerte** -- `textual` porte le caractere `b` dans
    l'evenement quelle que soit la touche, et la branche des caracteres
    imprimables ne regarde pas le nom. Elle passait avec et sans le correctif ;
    la reinjection l'a demasquee. Une touche **nommee** est le seul cas qui
    depende reellement de la normalisation.
    """
    from mixed_media_utility.tui.execution import PanneauConfirmation
    from mixed_media_utility.tui.noms import ModeleNoms, NomEditable
    from mixed_media_utility.tui.panneau import ChoixExclusif, Issue, Panneau

    # Deux noms distinguables, la cible en SECONDE position (regle des fabriques).
    noms = ModeleNoms(noms=[NomEditable("lot_a"), NomEditable("lot_b")])
    ecran = PanneauConfirmation(
        Panneau("A ecrire"),
        ChoixExclusif([Issue("ecrire", "Ecrire", ecrit=True),
                       Issue("annuler", "Annuler")]),
        noms=noms)

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        # `Tab` et non `e` depuis `EPIC11-ARB-68`.
        _frapper(pilote.app, "tab", None)       # entrer en edition
        await pilote.pause()
        _frapper(pilote.app, "down", None)      # aller au SECOND nom
        await pilote.pause()
        _frapper(pilote.app, "z", "z")          # salir la saisie
        await pilote.pause()
        sali = list(noms.valeurs)
        _frapper(pilote.app, "alt+escape", "\x1b")   # renoncer, touche collee
        await pilote.pause()
        return sali, list(noms.valeurs), noms.en_edition

    sali, apres, en_edition = banc(CoqueTui(), scenario)
    assert sali == ["lot_a", "lot_bz"], "la saisie doit d'abord etre salie"
    assert apres == ["lot_a", "lot_b"], (
        "`alt+escape` doit abandonner l'edition comme `escape` ; sans la "
        "normalisation il est consomme par le mode et ne fait RIEN")
    assert en_edition is False
