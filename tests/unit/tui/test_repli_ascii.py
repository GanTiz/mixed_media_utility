# -*- coding: utf-8 -*-
"""Story 11.0, AC 3.3 -- `--ascii` couvre TOUT le texte, pas les seuls glyphes.

Le repli ne couvrait que la table de glyphes. Les libelles ecrits en dur --
lignes de raccourcis, separateurs, `— aucun projet —`, l'abregement `…` --
restaient en UTF-8 : deux zones de l'ecran sur cinq n'etaient pas ASCII sur un
terminal qui, par hypothese, ne rend pas l'UTF-8 (revue de vague 1, couche 2).
"""

import pytest

from mixed_media_utility.tui import jetons
from mixed_media_utility.tui.coque import (
    CoqueTui,
    Contexte,
    Palier,
    PalierTemoin,
    message_trop_petit,
)
from mixed_media_utility.tui.execution import (
    EcranExecution,
    EcranInterruption,
    EcranRefus,
    PanneauConfirmation,
    SurfaceExecution,
)
from mixed_media_utility.tui.noms import ModeleNoms, NomEditable
from mixed_media_utility.tui.panneau import ChoixExclusif, Issue, LigneChiffree, Panneau


#: **Le balayage vit desormais dans `src/`, et ce banc le RE-EXPORTE.**
#: Story 11.9, lot A1. Les deux fonctions ci-dessous etaient ecrites ici depuis
#: la story 11.0 ; le manuel des raccourcis en a besoin **en production**, et un
#: module de `src/` ne peut pas importer un banc. Elles sont donc REMONTEES dans
#: `tui/manuel.py` -- pas recopiees : quatre bancs d'epic les importent par ce
#: chemin (`test_majuscules_des_raccourcis`, `test_sobriete_et_grille_extraction`,
#: `test_paliers`, `test_arb140_passages_sans_q_quitter`), et un second balayage
#: divergerait du premier au premier ecran ajoute. C'est litteralement le motif
#: ecrit dans `test_arb140_passages_sans_q_quitter.py:48-53` : « on le REUTILISE
#: plutot que d'en ecrire un second, qui divergerait ».
#:
#: Les deux noms publics de ce fichier ne bougent pas, et c'est ce qui fait que
#: les quatre bancs n'ont pas une ligne a changer.
from mixed_media_utility.tui.manuel import (  # noqa: E402  (re-export)
    classes_d_ecran,
    lignes_de_raccourcis_du_paquet,
)


def test_le_balayage_voit_les_lignes_contextuelles_et_pas_seulement_les_classes():
    """Volet symetrique du balayage etendu.

    Sans lui, la generalisation ci-dessus pourrait ne rien voir de plus que
    l'ancienne et passerait pour un renforcement sans en etre un.
    """
    lignes = lignes_de_raccourcis_du_paquet()
    portees_par_une_classe = {f"{nom}.raccourcis"
                              for nom in classes_d_ecran()}
    hors_classe = set(lignes) - portees_par_une_classe
    assert hors_classe, "aucune ligne contextuelle vue : la garde ne mesure rien de plus"
    assert any("ecran_projet" in nom for nom in hors_classe), sorted(hors_classe)


@pytest.mark.parametrize("nom,ligne",
                         sorted(lignes_de_raccourcis_du_paquet().items()))
def test_aucune_ligne_de_raccourcis_contextuelle_ne_deborde(nom, ligne):
    """Meme mesure que pour les lignes de classe, etendue aux contextuelles."""
    assert jetons.colonnes(ligne) <= jetons.largeur_utile(), (
        nom, jetons.colonnes(ligne))


@pytest.mark.parametrize("nom,ligne",
                         sorted(lignes_de_raccourcis_du_paquet().items()))
def test_toute_ligne_de_raccourcis_contextuelle_se_replie_en_ascii(nom, ligne):
    replie = jetons.replier_ascii(ligne)
    assert replie.isascii(), (nom, replie)
    assert jetons.colonnes(replie) <= jetons.largeur_utile(), (
        nom, jetons.colonnes(replie))


def test_le_balayage_des_ecrans_trouve_les_classes_du_paquet():
    """Volet symetrique du balayage : sans lui, une garde qui ne verrait aucune
    classe serait verte sur tout."""
    classes = classes_d_ecran()
    assert len(classes) >= 8, sorted(classes)
    noms = {cle.rsplit(".", 1)[1] for cle in classes}
    assert {"Palier", "PalierTemoin", "EcranChiffre", "PanneauConfirmation",
            "EcranExecution", "EcranInterruption", "EcranRefus",
            "EcranResultat"} <= noms


@pytest.mark.parametrize("nom,classe", sorted(classes_d_ecran().items()))
def test_aucune_ligne_de_raccourcis_ne_deborde_de_la_grille(nom, classe):
    """`textual` REPLIE une ligne trop longue au lieu de la tronquer : sur une
    zone de hauteur 1, la fin disparait sans bruit. La confirmation faisait 77
    colonnes pour 76, et son « Echap retour » etait invisible.

    Parametre par classe plutot que dans une boucle : un rouge nomme la classe
    fautive au lieu de rendre un dictionnaire a lire.
    """
    assert jetons.colonnes(classe.raccourcis) <= jetons.largeur_utile(), (
        nom, jetons.colonnes(classe.raccourcis))


def test_la_garde_de_raccourcis_mord_sur_une_ligne_trop_longue():
    """Volet symetrique. **Il ne fabrique plus de classe temoin** : la
    precedente version en definissait une, qui restait visible de
    `Palier.__subclasses__` et faisait rougir la garde reelle selon l'ordre
    d'execution des tests -- le defaut que la garde etait censee empecher, dans
    la garde elle-meme.
    """
    trop_longue = "x" * (jetons.largeur_utile() + 1)
    assert jetons.colonnes(trop_longue) > jetons.largeur_utile()


@pytest.mark.parametrize("nom,classe", sorted(classes_d_ecran().items()))
def test_toute_ligne_de_raccourcis_se_replie_en_ascii(nom, classe):
    replie = jetons.replier_ascii(classe.raccourcis)
    assert replie.isascii(), (nom, replie)
    if classe.raccourcis:
        assert replie, "un repli ne vide jamais une ligne"


@pytest.mark.parametrize("texte", [
    "↑↓ choisir   Espace retenir   ⏎ valider   Échap retour",
    "mmu · — aucun projet — · Projet",
    "Terminal trop petit : 79 colonnes sur 24 lignes.",
    "abrège… l'été",
])
def test_le_repli_rend_de_l_ascii_pur_sans_perdre_le_sens(texte):
    replie = jetons.replier_ascii(texte)
    assert replie.isascii(), replie
    # Le sens survit : les mots restent des mots, seuls les signes changent.
    for mot in ("choisir", "valider", "projet", "Terminal", "colonnes"):
        if mot in texte:
            assert mot in replie


def test_le_repli_nomme_les_touches_au_lieu_de_les_effacer():
    """`⏎` devient `Entree`, pas rien : un raccourci sans sa touche ne sert
    plus a rien."""
    assert "Entree" in jetons.replier_ascii("⏎ valider")
    assert "^v" in jetons.replier_ascii("↑↓ choisir")


def test_le_repli_laisse_l_ascii_intact():
    """Volet symetrique : un repli qui abimerait l'ASCII deja pur casserait les
    chemins de fichiers et les identifiants."""
    intact = "projet_demo_rush_01_25fps  84/124 frames  [x] ( )"
    assert jetons.replier_ascii(intact) == intact


# --------------------------------------------------------------------------
# Le repli, vu depuis les ecrans montes
# --------------------------------------------------------------------------

def coque_ascii(**kwargs) -> CoqueTui:
    return CoqueTui(paliers=[PalierTemoin("Projet", "⏎ ouvrir   q quitter"),
                             PalierTemoin("Ateliers", "⏎ entrer   q quitter")],
                    contexte=Contexte("projet_demo",
                                      objet="rush_01 · 25 fps · 4:12"),
                    ascii_seul=True, **kwargs)


def zones(app) -> dict:
    from textual.widgets import Static
    return {identifiant: str(app.screen.query_one(f"#{identifiant}",
                                                  Static).content)
            for identifiant in ("bandeau", "etat", "raccourcis")}


def test_les_trois_zones_fixes_sont_ascii_en_mode_ascii(banc):
    """Deux zones sur cinq ne l'etaient pas."""
    ecran = PanneauConfirmation(
        Panneau("A ecrire", [LigneChiffree("Frames ecrites", 186, "frames")]),
        ChoixExclusif([Issue("ecrire", "Extraire", ecrit=True),
                       Issue("annuler", "Annuler")]),
        ModeleNoms([NomEditable("projet_demo_rush_01_25fps"),
                    NomEditable("projet_demo_rush_01_12p5")]))

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        return zones(pilote.app)

    for identifiant, texte in banc(coque_ascii(), scenario).items():
        assert texte.isascii(), (identifiant, texte)


def test_le_cartouche_et_les_issues_sont_ascii_en_mode_ascii(banc):
    from textual.widgets import Static

    ecran = PanneauConfirmation(
        Panneau("A ecrire", [LigneChiffree("Bornes",
                                           "00:00:04:12 → 00:00:09:08")]),
        ChoixExclusif([Issue("ecrire", "Extraire", ecrit=True),
                       Issue("annuler", "Annuler")]),
        ModeleNoms([NomEditable("projet_demo_rush_01_25fps"),
                    NomEditable("projet_demo_rush_01_12p5")]))

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        textes = [str(pilote.app.screen.query_one("#chiffres", Static).content),
                  str(pilote.app.screen.query_one("#issues", Static).content)]
        textes += [str(w.content) for w in pilote.app.screen.query(".nom")]
        return textes

    for texte in banc(coque_ascii(), scenario):
        assert texte.isascii(), texte


def test_l_ecran_de_refus_est_ascii_en_mode_ascii(banc):
    from textual.widgets import Static

    ecran = EcranRefus("pile-de-calibration-seule",
                       "La pile ne porte que des pages de calibration.",
                       conserve=["les 12 pages ingerees"],
                       suites=["consigner par `scan ... calibrate`"])

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        return str(pilote.app.screen.query_one("#refus", Static).content)

    assert banc(coque_ascii(), scenario).isascii()


def test_la_progression_est_ascii_en_mode_ascii(banc):
    surface = SurfaceExecution("frames")
    emetteur = surface.emetteur(124)
    ecran = EcranExecution(surface, "Extraction en cours — lot 1 sur 2")

    async def scenario(pilote):
        app = pilote.app
        app.descendre(ecran)
        await pilote.pause()
        emetteur.emettre(84)
        await pilote.pause()
        from textual.widgets import Static
        return (zones(app)["etat"],
                str(app.screen.query_one("#tache", Static).content),
                str(app.screen.query_one("#journal", Static).content))

    for texte in banc(coque_ascii(), scenario):
        assert texte.isascii(), texte


def test_le_message_sous_le_plancher_est_ascii(banc):
    from textual.widgets import Static

    async def scenario(pilote):
        return str(pilote.app.screen.query_one("#trop-petit", Static).content)

    assert banc(coque_ascii(), scenario, taille=(79, 24)).isascii()


# --------------------------------------------------------------------------
# L'appariement positionnel du message de plancher
# --------------------------------------------------------------------------

def test_le_message_de_plancher_n_intervertit_pas_largeur_et_hauteur():
    """Un appariement positionnel non mesure : le message pouvait annoncer
    « 24 colonnes sur 79 lignes » (revue de vague 1, couche 2).

    Les deux valeurs sont **distinguables** -- c'est la regle des fabriques
    appliquee a deux arguments plutot qu'a une collection.
    """
    message = message_trop_petit(79, 24)
    assert "79 colonnes" in message
    assert "24 lignes" in message
    assert "24 colonnes" not in message
    assert "79 lignes" not in message


def test_le_message_de_plancher_nomme_aussi_la_taille_due_dans_le_bon_ordre():
    message = message_trop_petit(40, 12)
    assert message.index("40") < message.index("80")
    assert message.index("12") < message.index("24")
    # Et les deux exigences ne sont pas interverties non plus.
    assert message.index(str(jetons.LARGEUR_PLANCHER)) < message.index(
        str(jetons.HAUTEUR_PLANCHER))
