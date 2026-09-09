# -*- coding: utf-8 -*-
"""Story 11.0, AC 4 -- les trois paliers, et ce que `Echap` fait exactement."""

from pathlib import Path

import pytest
from textual.widgets import Static

from mixed_media_utility.tui.coque import (
    Contexte,
    CoqueTui,
    Palier,
    PalierTemoin,
    paliers_temoins,
)


class PalierFormulaire(Palier):
    """Un palier qui SAIT ecrire : il rend la mesure de l'AC 4.3 capable de bouger.

    Un temoin incapable d'ecrire rendrait « aucun fichier ecrit » vrai pour une
    raison sans rapport avec `Echap`. Celui-ci ecrit sur `valider()`, et le test
    verifie les deux sens.
    """

    titre = "Formulaire"
    raccourcis = "⏎ valider   Échap abandonner"

    def __init__(self, dossier: Path) -> None:
        super().__init__()
        self.dossier = dossier
        self.saisie = ""

    def contenu(self) -> list[Static]:
        return [Static("Nom du lot"), Static("> ")]

    def valider(self) -> Path:
        cible = self.dossier / f"{self.saisie or 'sans_nom'}.txt"
        cible.write_text(self.saisie, encoding="utf-8")
        return cible


def test_trois_paliers_et_un_seul_monte_a_la_fois(banc):
    """AC 4.1 : la pile a trois etages, l'ecran affiche le sommet et lui seul."""
    async def scenario(pilote):
        app = pilote.app
        vus = [(app.rang, app.screen.titre)]
        for _ in range(2):
            app.descendre()
            await pilote.pause()
            vus.append((app.rang, app.screen.titre))
        # Le sommet est bien le seul palier dessine : les paliers du dessous
        # ne sont pas dans l'arbre de l'ecran courant.
        contenu = [w.content for w in app.screen.query(".temoin")]
        return vus, contenu

    vus, contenu = banc(CoqueTui(), scenario)
    assert vus == [(0, "Projet"), (1, "Ateliers"), (2, "Extraction")]
    assert contenu == ["Extraction"]


def test_echap_remonte_d_un_palier_sur_les_deux_transitions(banc):
    """AC 4.2 : depuis le palier 2, `Echap` rend le 1 -- et non le 0.

    Les deux transitions sont mesurees : une remontee qui viderait la pile
    d'un coup serait verte si l'on ne testait que la descente d'un seul cran.
    """
    async def scenario(pilote):
        app = pilote.app
        app.descendre()
        await pilote.pause()
        app.descendre()
        await pilote.pause()
        etapes = [(app.rang, app.screen.titre)]
        await pilote.press("escape")
        await pilote.pause()
        etapes.append((app.rang, app.screen.titre))
        await pilote.press("escape")
        await pilote.pause()
        etapes.append((app.rang, app.screen.titre))
        # Un `Echap` de plus a la racine ne fait rien : il ne quitte pas.
        await pilote.press("escape")
        await pilote.pause()
        etapes.append((app.rang, app.screen.titre))
        return etapes

    assert banc(CoqueTui(), scenario) == [
        (2, "Extraction"), (1, "Ateliers"), (0, "Projet"), (0, "Projet")]


def test_un_formulaire_abandonne_par_echap_n_ecrit_rien(banc, tmp_path):
    """AC 4.3 : comptage de fichiers, a zero, sur un repertoire temoin."""
    temoin = tmp_path / "temoin"
    temoin.mkdir()
    formulaire = PalierFormulaire(temoin)

    async def scenario(pilote):
        app = pilote.app
        app.descendre(formulaire)
        await pilote.pause()
        formulaire.saisie = "lot_25fps"
        await pilote.press("escape")
        await pilote.pause()
        return app.rang

    assert banc(CoqueTui(), scenario) == 0
    assert list(temoin.iterdir()) == []


def test_le_comptage_de_fichiers_bouge_quand_on_valide(tmp_path):
    """AC 4.3, volet symetrique : la mesure sait voir une ecriture.

    Sans lui, un repertoire vide prouverait seulement que le temoin n'ecrit
    jamais -- pas qu'`Echap` s'en abstient.
    """
    temoin = tmp_path / "temoin"
    temoin.mkdir()
    formulaire = PalierFormulaire(temoin)
    formulaire.saisie = "lot_25fps"
    formulaire.valider()
    assert [c.name for c in temoin.iterdir()] == ["lot_25fps.txt"]


def test_seul_le_segment_de_palier_change_au_fil_de_la_navigation(banc):
    """AC 4.4 : le projet et l'objet traversent les etages sans bouger."""
    contexte = Contexte(projet="projet_demo", objet="rush_01 · 25 fps")

    async def scenario(pilote):
        app = pilote.app
        bandeaux = [app.screen.query_one("#bandeau", Static).content]
        app.descendre()
        await pilote.pause()
        bandeaux.append(app.screen.query_one("#bandeau", Static).content)
        return bandeaux

    avant, apres = banc(CoqueTui(contexte=contexte), scenario)
    assert avant != apres
    for bandeau in (avant, apres):
        assert bandeau.startswith("mmu · projet_demo · ")
        assert bandeau.rstrip().endswith("rush_01 · 25 fps")
    assert "· Projet " in avant
    assert "· Ateliers " in apres


def test_sans_projet_le_bandeau_le_dit_au_lieu_de_laisser_un_trou(banc):
    async def scenario(pilote):
        return pilote.app.screen.query_one("#bandeau", Static).content

    assert "— aucun projet —" in banc(CoqueTui(), scenario)


def test_chaque_palier_porte_ses_propres_raccourcis(banc):
    """La derniere ligne suit le palier : c'est une donnee du palier."""
    async def scenario(pilote):
        app = pilote.app
        vus = [app.screen.query_one("#raccourcis", Static).content]
        app.descendre()
        await pilote.pause()
        vus.append(app.screen.query_one("#raccourcis", Static).content)
        return vus

    racine, ateliers = banc(CoqueTui(), scenario)
    assert racine != ateliers
    # `Q quitter` en MAJUSCULE : c'est l'affichage, pas la touche. Le binding
    # reste `("q", ...)`, ce que `test_q_quitte` ci-dessous mesure a la frappe.
    assert "Q quitter" in racine and "Q quitter" in ateliers
    assert "Échap" in ateliers and "Échap" not in racine


def test_q_quitte(banc):
    """AC 4.5, premiere moitie."""
    async def scenario(pilote):
        await pilote.press("q")
        await pilote.pause()
        return pilote.app._exit

    assert banc(CoqueTui(), scenario) is True


def test_q_demande_confirmation_quand_une_tache_tourne(banc):
    """AC 4.5, seconde moitie : la sortie n'est pas immediate, elle est demandee."""
    async def scenario(pilote):
        app = pilote.app
        app.tache_en_cours = True
        await pilote.press("q")
        await pilote.pause()
        return app._exit, app.confirmation_de_sortie_demandee

    sorti, demande = banc(CoqueTui(), scenario)
    assert sorti is False
    assert demande is True


def test_echap_pendant_une_tache_n_est_plus_une_remontee(banc):
    """`DESIGN.md` section 4 : la story 11.1 branchera l'ecran d'interruption ici."""
    async def scenario(pilote):
        app = pilote.app
        app.descendre()
        await pilote.pause()
        app.tache_en_cours = True
        await pilote.press("escape")
        await pilote.pause()
        return app.rang, app.interruption_demandee

    assert banc(CoqueTui(), scenario) == (1, True)


def test_la_fabrique_de_paliers_rend_trois_etages_distinguables():
    """Regle des fabriques : trois elements, tous differents les uns des autres."""
    paliers = paliers_temoins()
    assert len(paliers) == 3
    assert len({p.titre for p in paliers}) == 3
    assert len({p.raccourcis for p in paliers}) == 3


def test_descendre_avec_un_palier_fourni_empile_celui_la_et_pas_le_suivant(banc):
    """La cible n'est PAS en premiere position : un `descendre` qui rendrait
    toujours l'etage suivant des temoins ne se demasque pas autrement."""
    invite = PalierTemoin("Scan", "Échap ateliers", "Scan")

    async def scenario(pilote):
        app = pilote.app
        app.descendre(invite)
        await pilote.pause()
        return app.rang, app.screen.titre

    assert banc(CoqueTui(), scenario) == (1, "Scan")


@pytest.mark.parametrize("descentes_en_trop", [1, 5])
def test_descendre_trop_bas_donne_UN_ecran_pas_encore_et_pas_un_etage_fantome(
        banc, descentes_en_trop):
    """La pile connue a trois etages, et rien ne lui en ajoute un quatrieme.

    **Le contrat a change le 2026-08-28, il n'a pas ete affaibli.** Descendre
    sous le dernier palier ne rend plus la main en silence : cela ouvre l'ecran
    « pas encore », qui nomme ce qui manque et quand il arrive. Ce que ce test
    garde de sa version d'origine, c'est l'essentiel -- **aucun etage fantome
    n'est cree** : les paliers connus restent trois, et l'ecran « pas encore »
    ne s'empile pas sur lui-meme, quel que soit le nombre de pressions.

    Deux nombres de descentes en trop, dont un bien superieur a un : un ecran
    qui s'empilerait a chaque pression passerait un test a une seule descente.
    """
    async def scenario(pilote):
        app = pilote.app
        for _ in range(2 + descentes_en_trop):
            app.descendre()
            await pilote.pause()
        return (app.rang, app.passages_empiles,
                type(app.screen).__name__, len(app._paliers))

    # Le rang s'arrete au **dernier palier reel** (2 sur trois paliers) et le
    # seul ecran « pas encore » compte comme un passage, quel que soit le
    # nombre de descentes en trop. Mesurer `rang == 3` reviendrait a mesurer
    # une hauteur de pile, c'est-a-dire le defaut que `V2-M1` a coute.
    assert banc(CoqueTui(), scenario) == (2, 1, "EcranPasEncore", 3)


def test_entree_descend_reellement_au_clavier_sur_les_deux_transitions(banc):
    """La touche que la ligne de raccourcis promet atteint bien `descendre`.

    **Aucun test ne pressait cette touche** : tous les tests de navigation
    ci-dessus appellent `app.descendre()` en Python, et la liaison clavier
    n'existait pas -- le lanceur nu montrait une pile de navigation dans
    laquelle on ne pouvait pas descendre, alors que chaque palier annonce
    « ⏎ ouvrir » ou « ⏎ entrer ». Meme famille que les defauts de la revue de
    vague 1 : le modele mesure, le clavier non.

    Les **deux** transitions sont mesurees, comme pour `Echap` a l'AC 4.2 : une
    liaison qui n'agirait qu'au premier etage passerait un test a une seule
    pression.
    """
    async def scenario(pilote):
        etapes = []
        await pilote.press("enter")
        await pilote.pause()
        etapes.append((pilote.app.rang, pilote.app.screen.titre))
        await pilote.press("enter")
        await pilote.pause()
        etapes.append((pilote.app.rang, pilote.app.screen.titre))
        return etapes

    assert banc(CoqueTui(), scenario) == [(1, "Ateliers"), (2, "Extraction")]


def test_entree_au_dernier_palier_mene_a_l_ecran_pas_encore(banc):
    """Au clavier : le dernier palier annonce `⏎`, donc `⏎` doit mener quelque part.

    « Ce serait bien que la navigation soit complete quitte a ne mener nulle
    part, comme ca on sait que c'est temporaire et que ce n'est pas un bug »
    (Egan, 2026-08-28, apres avoir lu une touche inerte comme un blocage).

    Cinq pressions et non une : l'ecran ne doit pas s'empiler sur lui-meme, et
    on mesure **le texte rendu** -- pas seulement le type de l'ecran --, sans
    quoi un ecran vide passerait.
    """
    async def scenario(pilote):
        for _ in range(5):
            await pilote.press("enter")
            await pilote.pause()
        ecran = pilote.app.screen
        return (pilote.app.rang, pilote.app.passages_empiles),             chr(10).join(ecran.lignes())

    (rang, empiles), texte = banc(CoqueTui(), scenario)
    # **Un seul passage empile, et le rang immobile.** L'ecran « pas encore »
    # est un passage : cinq pressions n'en posent qu'un, et aucune ne fait
    # croire qu'on a descendu un palier de plus.
    assert empiles == 1, "l'ecran « pas encore » ne s'empile pas sur lui-meme"
    assert rang == 2, "il ne fait pas croire a un palier de plus"
    assert "Extraction" in texte, "il nomme ce qui a ete demande"
    assert "n'existe pas encore" in texte, "il dit que c'est une absence"
    assert "vague 3" in texte, (
        "il dit QUAND : sans echeance, « pas encore fait » et « abandonne » se "
        "ressemblent")


def test_un_palier_revisite_retrouve_ses_widgets(banc):
    """Un palier quitte puis retrouve est le MEME ecran, pas un sosie.

    Tranche par Egan le 2026-08-28 : « un palier visité doit retrouver son état
    où on l'a laissé ».

    **Ce test mesure l'etat du WIDGET, pas la pile** -- et c'est tout son
    interet. `textual` detruit tout ecran depile qui n'est pas installe
    (`App._replace_screen`), et le re-push le recompose : `rang` et
    `screen.titre` etaient donc justes des deux cotes du defaut, ce qui a rendu
    trois mesures successives aveugles. Ce qui change, c'est que les widgets
    sont **d'autres objets**, et que le chemin de peinture differe -- d'ou la
    trame en retard qu'Egan voyait dans son terminal.
    """
    async def scenario(pilote):
        app = pilote.app
        await pilote.press("enter")
        await pilote.pause()
        palier = app.screen
        temoins = [id(enfant) for enfant in palier.children]
        await pilote.press("escape")
        await pilote.pause()
        # C'est ICI que la mesure mord : entre la remontee et la redescente.
        survivant = (palier.is_attached, len(palier.children))
        await pilote.press("enter")
        await pilote.pause()
        return survivant, temoins, [id(enfant) for enfant in app.screen.children]

    survivant, avant, apres = banc(CoqueTui(), scenario)
    assert survivant == (True, len(avant)), (
        "le palier quitte doit RESTER monte et garder ses enfants ; s'il est "
        "detruit, la pile reste juste et l'ecran a un cran de retard")
    assert avant and apres == avant, (
        "les widgets doivent etre les MEMES objets d'une visite a l'autre")


# ===========================================================================
# Lot I, finding `I8` -- `F1 aide` etait promis PARTOUT et lie NULLE PART
# ===========================================================================

def lignes_de_raccourcis_qui_promettent_F1() -> dict:
    """Toutes les lignes de raccourcis du paquet qui annoncent `F1 aide`.

    Elles sont **lues du paquet**, jamais recopiees : le nombre exact importe
    moins que le fait qu'il ne soit pas nul, et une liste ecrite ici
    divergerait au premier ecran ajoute.
    """
    from test_repli_ascii import lignes_de_raccourcis_du_paquet

    return {nom: ligne for nom, ligne in lignes_de_raccourcis_du_paquet().items()
            if "F1" in ligne}


def test_F1_est_promis_par_le_produit_et_LIE_par_la_coque():
    """La frontiere du finding `I8`, dans les deux sens.

    `F1 aide` figure sur des lignes de raccourcis du produit -- et
    `DESIGN.md` section 4 en fait l'un des « trois raccourcis presents sur tout
    ecran **sans exception** » -- alors que **rien** ne liait la touche :
    `CoqueTui.BINDINGS` ne portait que `escape` et `q`. C'est la classe de
    defaut que `CoqueTui.on_event` documente (« une touche annoncee en ligne de
    raccourcis devenait **inerte** »), ici a l'etat pur.

    Le volet symetrique est la premiere assertion : sans elle, retirer `F1` de
    toutes les lignes rendrait le test vert sans rien avoir tenu.
    """
    promesses = lignes_de_raccourcis_qui_promettent_F1()
    assert promesses, "aucune ligne ne promet F1 : la mesure ne mesure rien"
    touches_liees = {liaison[0] for liaison in CoqueTui.BINDINGS}
    assert "f1" in touches_liees, (sorted(touches_liees), sorted(promesses))


def test_F1_ouvre_le_MANUEL_et_ne_s_empile_pas_sur_lui_meme(banc):
    """La promesse est **tenue pour de bon** depuis la story 11.9, lot C.

    Ce test mesurait, jusqu'au 2026-09-03, l'ecran « pas encore » que `F1`
    empilait : il nommait l'absence et son echeance (`T1-1`, `T1-2`), suivant
    le motif qu'Egan a pose le 2026-08-28 -- « quitte a ne mener nulle part
    [...] comme ca on sait que c'est temporaire et que ce n'est pas un bug ».
    L'echeance est arrivee : `action_aide` empile
    `ecran_manuel.EcranManuel`, derive du paquet.

    **Ce qui NE change pas est le coeur du test, et c'est pour ca qu'il est
    retargete plutot que reecrit** : les deux invariants de passage --
    `passages_empiles == 1` apres CINQ pressions, et `rang == 0` -- valaient
    pour l'ecran d'avant et valent pour celui-ci. La garde de non-empilement a
    d'ailleurs du etre **reportee** de `descendre` vers `action_aide` au lot C,
    et sans ce test elle serait partie avec l'ancien ecran.

    **Cinq pressions et non une** : c'est ce qui a demasque le defaut d'origine
    sur `descendre` le 2026-08-28, ou cinq appels empilaient cinq ecrans.
    """
    async def scenario(pilote):
        for _ in range(5):
            await pilote.press("f1")
            await pilote.pause()
        return (pilote.app.rang, pilote.app.passages_empiles,
                type(pilote.app.screen).__name__,
                chr(10).join(pilote.app.screen.composer()))

    rang, empiles, ecran, texte = banc(CoqueTui(), scenario)
    assert empiles == 1, "l'aide s'empile sur elle-meme"
    assert rang == 0, "F1 ne fait pas croire qu'on a descendu un palier"
    assert ecran == "EcranManuel", ecran
    assert "n'existe pas encore" not in texte, (
        "F1 ouvre encore l'ecran qui annonce une absence : la 11.9 l'a comblee")
    assert "Raccourcis" in texte, texte
    assert "F1" in texte, "le manuel n'annonce meme pas la touche qui l'ouvre"


def test_F1_depuis_un_palier_PROFOND_revient_la_ou_on_etait(banc):
    """`F1` est un passage, pas une navigation : `Echap` ramene a l'ecran
    d'ou l'on vient, et **pas d'un palier plus haut**.

    Le palier vise n'est ni le premier ni le dernier de la pile temoin : un
    depilement qui remonterait toujours a la racine, ou qui compterait `F1`
    comme un palier, ne se demasque pas sur une pile a un seul etage.
    """
    async def scenario(pilote):
        await pilote.press("enter")             # palier 1, « Ateliers »
        await pilote.pause()
        avant = (pilote.app.rang, pilote.app.screen.titre)
        await pilote.press("f1")
        await pilote.pause()
        pendant = pilote.app.screen.titre
        await pilote.press("escape")
        await pilote.pause()
        return avant, pendant, (pilote.app.rang, pilote.app.screen.titre)

    avant, pendant, apres = banc(CoqueTui(), scenario)
    assert avant == (1, "Ateliers")
    assert pendant == "Manuel", (
        "F1 doit ouvrir le manuel (story 11.9, lot C), pas l'ecran d'absence")
    assert apres == avant, (avant, apres)
