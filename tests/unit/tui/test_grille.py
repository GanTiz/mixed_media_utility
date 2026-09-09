# -*- coding: utf-8 -*-
"""Story 11.0, AC 1 -- la grille 80x24 et son refus sous le plancher."""

import pytest
from textual.containers import Horizontal
from textual.widgets import Static

from mixed_media_utility.tui import jetons
from mixed_media_utility.tui.coque import (
    Contexte,
    CoqueTui,
    EcranPasEncore,
    assez_grand,
    message_trop_petit,
)

ZONES = ("#bandeau", "#centre", "#etat", "#raccourcis")


def _hauteurs(app):
    return {zone: app.screen.query_one(zone).size.height for zone in ZONES}


def test_les_quatre_zones_tiennent_la_repartition_du_plancher(banc):
    """AC 1.1 : 1 / 17 / 1 / 1, et la zone centrale vaut la valeur derivee."""
    async def scenario(_pilote):
        app = _pilote.app
        return _hauteurs(app), app.screen.query_one("#centre").size.width

    hauteurs, largeur_centre = banc(CoqueTui(), scenario)
    assert hauteurs == {
        "#bandeau": jetons.HAUTEUR_BANDEAU,
        "#centre": jetons.HAUTEUR_CENTRE_AU_PLANCHER,
        "#etat": jetons.HAUTEUR_ETAT,
        "#raccourcis": jetons.HAUTEUR_RACCOURCIS,
    }
    # 17, et pas 20 : le cadre et les deux filets consomment quatre lignes. La
    # valeur est ecrite ici en clair EN PLUS de la constante -- une constante
    # comparee a elle-meme ne mesurerait rien (piege du test tautologique,
    # story 5.9).
    assert jetons.HAUTEUR_CENTRE_AU_PLANCHER == 17
    assert largeur_centre == jetons.largeur_utile() == 76


@pytest.mark.parametrize("taille", [(79, 24), (80, 23), (40, 12)])
def test_sous_le_plancher_seule_la_taille_est_dessinee(banc, taille):
    """AC 1.2 : ni bandeau, ni contenu tronque -- l'arbre ne les porte plus.

    Les trois tailles couvrent les deux dimensions separement : une garde qui
    ne testerait que la largeur laisserait passer un ecran tronque en hauteur,
    qui est justement le cas d'un terminal de 80 colonnes sur 20 lignes.
    """
    async def scenario(pilote):
        app = pilote.app
        return ([w.id for w in app.screen.walk_children()],
                app.screen.query_one("#trop-petit", Static).content)

    identifiants, message = banc(CoqueTui(), scenario, taille=taille)
    assert identifiants == ["trop-petit"]
    largeur, hauteur = taille
    assert str(largeur) in message and str(hauteur) in message
    assert str(jetons.LARGEUR_PLANCHER) in message
    assert str(jetons.HAUTEUR_PLANCHER) in message


def test_le_refus_et_le_retour_se_font_au_franchissement(banc):
    """AC 1.2 : le refus arrive au retrecissement et repart a l'agrandissement.

    Un ecran monte directement trop petit serait vert avec un gestionnaire de
    taille inexistant : c'est le FRANCHISSEMENT qui demasque le defaut.
    """
    async def scenario(pilote):
        app = pilote.app
        vus = [sorted(w.id for w in app.screen.walk_children() if w.id)]
        await pilote.resize_terminal(79, 24)
        await pilote.pause()
        vus.append(sorted(w.id for w in app.screen.walk_children() if w.id))
        await pilote.resize_terminal(80, 24)
        await pilote.pause()
        vus.append(sorted(w.id for w in app.screen.walk_children() if w.id))
        return vus

    depart, retreci, revenu = banc(CoqueTui(), scenario)
    assert depart == ["bandeau", "centre", "etat", "raccourcis"]
    assert retreci == ["trop-petit"]
    assert revenu == depart


def test_au_dela_du_plancher_la_place_va_au_centre_et_jamais_en_colonne(banc):
    """AC 1.3 : la hauteur gagnee va au centre, la largeur ne cree pas de colonne."""
    async def scenario(_pilote):
        app = _pilote.app
        return (_hauteurs(app),
                app.screen.query_one("#centre").size.width,
                len(app.screen.query(Horizontal)))

    hauteurs, largeur, horizontaux = banc(CoqueTui(), scenario, taille=(120, 40))
    assert hauteurs["#centre"] == jetons.HAUTEUR_CENTRE_AU_PLANCHER + 16
    # Les trois zones fixes gardent leur hauteur : c'est tout le gain qui va au
    # centre, pas une part.
    assert hauteurs["#bandeau"] == jetons.HAUTEUR_BANDEAU
    assert hauteurs["#etat"] == jetons.HAUTEUR_ETAT
    assert hauteurs["#raccourcis"] == jetons.HAUTEUR_RACCOURCIS
    assert largeur == jetons.largeur_utile(120) == 116
    assert horizontaux == 0


@pytest.mark.parametrize("largeur,hauteur,attendu", [
    (80, 24, True),    # le plancher lui-meme est acceptable
    (81, 24, True),
    (80, 25, True),
    (79, 24, False),   # une colonne de moins
    (80, 23, False),   # une ligne de moins
    (79, 23, False),
])
def test_le_plancher_est_inclusif_dans_les_deux_dimensions(largeur, hauteur, attendu):
    """AC 1.2 : `>=` et non `>`. Les six cas encadrent les deux bornes."""
    assert assez_grand(largeur, hauteur) is attendu


def test_le_message_de_refus_nomme_la_taille_vue_avant_la_taille_due():
    """Le message dit d'abord ce qu'il voit : c'est ce que l'operateur cherche."""
    message = message_trop_petit(70, 20)
    assert message.index("70") < message.index("80")
    assert message.index("20") < message.index("24")


@pytest.mark.parametrize("fenetre,utile", [(80, 76), (120, 116), (100, 96)])
def test_la_largeur_utile_retire_le_cadre_et_les_marges(fenetre, utile):
    """La deduction est ecrite une fois ; trois largeurs la mesurent."""
    assert jetons.largeur_utile(fenetre) == utile


def test_le_bandeau_cale_l_objet_a_droite_sur_la_largeur_utile():
    """AC 1.1 : le bandeau tient la largeur utile, jamais celle de la fenetre.

    **La mesure est en COLONNES, jamais en caracteres** (revue de vague 2 bis).
    Elle etait ecrite `len(ligne)`, et sur un nom de projet en ideogrammes --
    ou chaque caractere vaut deux colonnes -- les deux comptes divergent de
    vingt : une ligne de 56 caracteres pour 76 colonnes. Un `len()` qui vaut la
    largeur utile ne dit donc rien de ce que le terminal affichera, et c'est
    exactement la famille de defauts que cette revue ferme.
    """
    ligne = Contexte("projet_demo", "Extraction", "rush_01").rendu(80)
    assert jetons.colonnes(ligne) == jetons.largeur_utile(80)
    assert ligne.startswith("mmu · projet_demo · Extraction")
    assert ligne.endswith("rush_01")


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_le_bandeau_tient_la_grille_sur_un_projet_en_DOUBLE_CHASSE(ascii_seul):
    """Le volet double chasse de la mesure ci-dessus, dans les deux modes.

    Les fixtures de bandeau du depot portaient des noms latins de 11 a 47
    caracteres : `len()` et `colonnes()` y disent la meme chose, si bien
    qu'aucune ne pouvait separer les deux mesures. Les trois noms ci-dessous
    sont **distinguables et de largeurs croissantes** ; le troisieme fait 20
    caracteres pour 40 colonnes, et le dernier deborde a lui seul la zone.
    """
    objet = "TEST_FILE_12p5"
    noms = ("projet_demo",                 # 11 car., 11 col.
            "撮影_" + "夕日" * 8,           #  3 + 16 car., 6 + 32 col.
            # **La classe `F`, et elle manquait a TOUT le depot** (revue de la
            # vague 3, couche 1, finding `C2`). `east_asian_width` distingue
            # `W` (large) de `F` (pleine chasse), et `colonnes()` compte deux
            # colonnes pour les deux. Toutes les fixtures de double chasse du
            # depot etaient en `W` : le mutant `("W", "F")` -> `("W",)`
            # survivait a 357 tests. Le latin pleine chasse n'est pas un cas de
            # laboratoire -- c'est la saisie par defaut d'un IME japonais ou
            # chinois sous Windows.
            "ＴＥＳＴ_ＦＩＬＥ",             #  9 car., 17 col. (8 en `F`)
            "夕日" * 24)                    # 24 car., 48... et bien au-dela
    # Volet symetrique : la fixture SEPARE bien les deux mesures. Sans lui,
    # elle pourrait deriver vers du latin et les assertions resteraient vertes
    # en cessant de mesurer quoi que ce soit.
    assert any(jetons.colonnes(nom) > len(nom) for nom in noms), noms
    # Et le volet PROPRE a la classe `F` : sans lui, retirer `"F"` de la table
    # de `colonnes()` laisserait l'assertion ci-dessus verte -- les noms en `W`
    # suffisent a la satisfaire.
    pleine_chasse = "ＴＥＳＴ_ＦＩＬＥ"
    assert jetons.colonnes(pleine_chasse) == 17, (
        "les huit caracteres latins PLEINE CHASSE valent deux colonnes chacun ; "
        f"obtenu {jetons.colonnes(pleine_chasse)} pour {len(pleine_chasse)} "
        "caracteres")
    for nom in noms:
        rendu = Contexte(nom, "Extraction", objet).rendu(
            jetons.LARGEUR_PLANCHER, ascii_seul)
        assert jetons.colonnes(rendu) <= jetons.largeur_utile(), (
            f"{nom!r}, ascii={ascii_seul} : le bandeau deborde "
            f"({jetons.colonnes(rendu)} colonnes) -- {rendu!r}")
        assert rendu.endswith(objet), (
            f"{nom!r}, ascii={ascii_seul} : l'objet travaille est ampute ; "
            f"c'est le PROJET qui doit ceder -- {rendu!r}")


def test_le_repli_ascii_ne_fait_jamais_perdre_la_droite_du_bandeau():
    """Le repli ASCII ALLONGE le texte, et la mesure doit venir apres lui.

    `—` rend `--`, `·` rend `.`, `…` rend `...` : une ligne calee a la bonne
    largeur en UTF-8 la depasse une fois repliee, et l'elision mange alors la
    **droite** -- c'est-a-dire l'objet travaille, celui qui porte les chiffres
    du parcours et ne se relit nulle part ailleurs.

    Mesure du 2026-08-28, en `--ascii` **sans projet ouvert** : le libelle
    `— aucun projet —` gagnait deux colonnes au repli, et `TEST_FILE_12p5`
    devenait `TEST_FILE...`. C'est la regression exacte que `BH-6` / `EC-10`
    avaient fermee, revenue par le seul chemin qui n'etait pas mesure.

    Les trois cas sont **distinguables** et la difficulte croit : sans projet
    (le libelle de substitution est le plus long en repli), avec un projet
    court, avec un projet si long qu'il doit s'abreger. Dans les trois, en
    UTF-8 comme en ASCII, l'objet est intact et c'est le **projet** qui cede.
    """
    objet = "TEST_FILE_12p5"
    cas = [
        (Contexte(None, "Extraction", objet), "sans projet"),
        (Contexte("projet_demo", "Extraction", objet), "projet court"),
        (Contexte("projet_demo_planche_4f_heteroclite_tres_long_nom",
                  "Extraction", objet), "projet trop long"),
    ]
    for contexte, etiquette in cas:
        for ascii_seul in (False, True):
            rendu = contexte.rendu(jetons.LARGEUR_PLANCHER, ascii_seul)
            assert jetons.colonnes(rendu) <= jetons.largeur_utile(), (
                f"{etiquette}, ascii={ascii_seul} : le bandeau deborde "
                f"({jetons.colonnes(rendu)} colonnes) -- {rendu!r}")
            assert rendu.endswith(objet), (
                f"{etiquette}, ascii={ascii_seul} : l'objet travaille est "
                f"ampute ; c'est le PROJET qui doit ceder -- {rendu!r}")


def test_l_ecran_pas_encore_nomme_ce_qui_manque_sans_doubler_les_guillemets():
    """Il pose ses guillemets une fois, pas deux.

    L'appelant fournit le libelle nu ; c'est l'ecran qui le met en citation.
    Les deux le faisaient, ce qui donnait « La suite de « Extraction » ».
    """
    ecran = EcranPasEncore("La suite de Extraction", "les ateliers de la vague 3")
    lignes = ecran.lignes()
    assert lignes[0] == "« La suite de Extraction »"
    assert lignes[0].count("«") == 1 and lignes[0].count("»") == 1
    assert "n'existe pas encore" in lignes[2]
    assert lignes[-1] == "Il arrive avec les ateliers de la vague 3."


def test_l_ecran_pas_encore_sans_echeance_ne_ment_pas():
    """Volet symetrique : sans echeance, il n'invente pas de ligne vide ni de date."""
    lignes = EcranPasEncore("Une action quelconque").lignes()
    assert not any("arrive" in ligne for ligne in lignes)
    assert lignes[0] == "« Une action quelconque »"
