# -*- coding: utf-8 -*-
"""Story 7.2, AC 4 -- selection a trois etats, cardinal, expandeurs.

« Selectionner un parent vaut selectionner ses **enfants actionnables** dans
l'atelier courant, pas tous ses descendants » ; « l'action porte son cardinal
en toutes lettres, jamais un verbe nu » (`EPIC7-ARB-10`) ; « l'expandeur
n'apparait que sur un noeud qui a des enfants : son absence est
l'information » (`EPIC7-ARB-3`).
"""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTreeWidgetItem

import fabriques_chutier as fab
from mixed_media_utility.gui import catalogue, jetons
from mixed_media_utility.gui import modele_chutier as modele
from mixed_media_utility.gui.coquille import Coquille


@pytest.fixture
def racines():
    return modele.construire_arbre(
        fab.manifest_deux_rushes_deux_lots_chacun(),
        existe=fab.liaison_factice(["medias/alpha.mov", "medias/beta.mov"]),
    )


# ---------------------------------------------------------------------------
# Selectionner un parent selectionne ses enfants ACTIONNABLES.
# ---------------------------------------------------------------------------


def test_selectionner_le_second_rush_selectionne_ses_deux_lots_et_aucun_autre(racines):
    # Fabrique imposee par l'epic : deux rushes distinguables, deux lots
    # chacun, toutes valeurs differentes. La cible est le SECOND rush, et la
    # verification est nominative -- jamais un cardinal seul.
    selection = modele.Selection(racines, "atelier-pdf")
    selection.selectionner("rush-beta")

    assert selection.identifiants() == ("lot-beta-1", "lot-beta-2")
    assert "lot-alpha-1" not in selection.identifiants()
    assert "lot-alpha-2" not in selection.identifiants()
    assert selection.etat("rush-beta") == modele.SELECTION_PLEINE
    assert selection.etat("rush-alpha") == modele.SELECTION_VIDE


def test_deselectionner_un_lot_rend_la_selection_du_rush_partielle(racines):
    selection = modele.Selection(racines, "atelier-pdf")
    selection.selectionner("rush-beta")
    # On retire le SECOND lot du rush, pas le premier.
    selection.deselectionner("lot-beta-2")

    assert selection.etat("rush-beta") == modele.SELECTION_PARTIELLE
    assert selection.identifiants() == ("lot-beta-1",)
    # Le troisieme etat est bien distinct des deux autres.
    assert selection.etat("rush-beta") != modele.SELECTION_PLEINE
    assert selection.etat("rush-beta") != modele.SELECTION_VIDE


def test_la_selection_porte_les_enfants_actionnables_pas_tous_les_descendants():
    # Sur la page Pdf, selectionner un rush selectionne ses LOTS -- « c'est
    # ce qui construit une planche » --, jamais ses planches ni ses scans.
    racines = modele.construire_arbre(
        fab.manifest_six_types(),
        documents_de_detection=[fab.detection_de_lot_alpha_1()],
        existe=fab.liaison_factice(["medias/alpha.mov", "medias/beta.mov"]),
    )
    selection = modele.Selection(racines, "atelier-pdf")
    selection.selectionner("rush-alpha")
    # `lot-alpha-2` est RECONSTRUIT : il n'est pas actionnable sur Pdf.
    assert selection.identifiants() == ("lot-alpha-1",)
    for identifiant in selection.identifiants():
        noeud = modele.noeud_par_identifiant(racines, identifiant)
        assert noeud.type == modele.TYPE_LOT


def test_l_atelier_courant_change_ce_qui_est_actionnable():
    racines = modele.construire_arbre(
        fab.manifest_six_types(),
        documents_de_detection=[fab.detection_de_lot_alpha_1()],
        existe=fab.liaison_factice(["medias/alpha.mov", "medias/beta.mov"]),
    )
    # Sur Exports, ce sont les lots RECONSTRUITS -- cible en seconde position
    # dans les enfants de `rush-alpha`.
    exports = modele.Selection(racines, "atelier-exports")
    exports.selectionner("rush-alpha")
    assert exports.identifiants() == ("lot-alpha-2",)
    # Sur Scan, ce sont les scans du lot detecte.
    scan = modele.Selection(racines, "atelier-scan")
    scan.selectionner("lot-alpha-1")
    assert len(scan.identifiants()) == 2
    for identifiant in scan.identifiants():
        assert modele.noeud_par_identifiant(racines, identifiant).type == (
            modele.TYPE_SCAN
        )


def test_basculer_est_reversible_et_passe_par_les_trois_etats(racines):
    selection = modele.Selection(racines, "atelier-pdf")
    assert selection.etat("rush-alpha") == modele.SELECTION_VIDE
    assert selection.basculer("rush-alpha") == modele.SELECTION_PLEINE
    selection.deselectionner("lot-alpha-2")
    assert selection.etat("rush-alpha") == modele.SELECTION_PARTIELLE
    # Depuis l'etat partiel, basculer COMPLETE (jamais ne vide) : c'est le
    # geste qu'une operatrice attend d'une case a demi cochee.
    assert selection.basculer("rush-alpha") == modele.SELECTION_PLEINE
    assert selection.basculer("rush-alpha") == modele.SELECTION_VIDE


def test_un_noeud_sans_enfant_actionnable_reste_vide(racines):
    # Symetrique : un lot n'a pas de scan sur l'atelier Scan tant qu'aucune
    # detection n'existe -- l'etat est vide, jamais « plein de rien ».
    selection = modele.Selection(racines, "atelier-scan")
    selection.selectionner("rush-beta")
    assert selection.identifiants() == ()
    assert selection.etat("rush-beta") == modele.SELECTION_VIDE
    assert selection.cardinal() == 0
    assert selection.est_active() is False


# ---------------------------------------------------------------------------
# L'action porte son cardinal en toutes lettres.
# ---------------------------------------------------------------------------


def test_le_libelle_d_action_accorde_a_zero_un_et_trois():
    # Les trois chaines EXACTES du catalogue. L'epic impose 0/1/3 parce que
    # l'accord singulier/pluriel est le point teste.
    assert catalogue.libelle_action("generer-planches", 0) == (
        "Générer des planches — aucun lot sélectionné"
    )
    assert catalogue.libelle_action("generer-planches", 1) == "Générer 1 planche"
    assert catalogue.libelle_action("generer-planches", 3) == "Générer 3 planches"
    # A zero, le libelle DIT que rien n'est selectionne : ce n'est ni un
    # verbe nu, ni le pluriel avec un zero dedans.
    assert "0" not in catalogue.libelle_action("generer-planches", 0)


def test_le_libelle_d_action_d_une_seconde_action_accorde_aussi():
    # Regle des fabriques : deux actions DISTINGUABLES, pas une seule -- un
    # formatteur qui rendrait toujours la premiere ne se demasque pas
    # autrement.
    assert catalogue.libelle_action("extraire-frames", 1) == "Extraire 1 frame"
    assert catalogue.libelle_action("extraire-frames", 3) == "Extraire 3 frames"
    assert catalogue.libelle_action("extraire-frames", 0) != (
        catalogue.libelle_action("generer-planches", 0)
    )


def test_le_cardinal_d_un_type_accorde_et_ne_se_confond_pas_avec_un_autre():
    assert catalogue.cardinal("lot", 1) == "1 lot"
    assert catalogue.cardinal("lot", 2) == "2 lots"
    assert catalogue.cardinal("planche", 1) == "1 planche"
    assert catalogue.cardinal("planche", 3) == "3 planches"
    assert catalogue.cardinal("rush", 2) == "2 rushes"
    # Deux types distinguables ne rendent jamais la meme chaine.
    assert catalogue.cardinal("lot", 2) != catalogue.cardinal("planche", 2)


def test_le_catalogue_couvre_les_six_types_de_noeud():
    # Contrat, pas duplication : les cles se DERIVENT du vocabulaire du
    # modele -- un type ajoute sans son cardinal echoue ici.
    for type_de_noeud in modele.TYPES_DE_NOEUD:
        assert catalogue.cardinal(type_de_noeud, 1)
        assert catalogue.cardinal(type_de_noeud, 4)


def test_le_libelle_d_action_suit_une_selection_reelle(racines):
    selection = modele.Selection(racines, "atelier-pdf")
    assert catalogue.libelle_action("generer-planches", selection.cardinal()) == (
        "Générer des planches — aucun lot sélectionné"
    )
    selection.selectionner("lot-beta-2")
    assert catalogue.libelle_action("generer-planches", selection.cardinal()) == (
        "Générer 1 planche"
    )
    selection.selectionner("rush-alpha")
    assert selection.cardinal() == 3
    assert catalogue.libelle_action("generer-planches", selection.cardinal()) == (
        "Générer 3 planches"
    )


# ---------------------------------------------------------------------------
# L'expandeur n'apparait que sur un noeud qui a des enfants.
# ---------------------------------------------------------------------------


@pytest.fixture
def coquille(qtbot):
    fenetre = Coquille()
    qtbot.addWidget(fenetre)
    fenetre.show()
    qtbot.waitExposed(fenetre)
    fenetre.resize(jetons.ESPACEMENTS["queue-overlay-threshold"], 800)
    qtbot.wait(20)
    fenetre.poser_projet(
        fab.manifest_six_types(),
        documents_de_detection=[fab.detection_de_lot_alpha_1()],
        existe=fab.liaison_factice(["medias/alpha.mov", "medias/beta.mov"]),
    )
    return fenetre


def test_un_noeud_sans_enfant_n_a_pas_d_expandeur(coquille):
    arbre = coquille.arbre_arborescence
    # `lot-alpha-2` n'a aucune detection : aucun enfant, donc AUCUN controle
    # -- l'assertion porte sur l'absence du controle, pas sur son etat.
    sans_enfant = arbre.element("lot-alpha-2")
    assert sans_enfant.childCount() == 0
    assert sans_enfant.childIndicatorPolicy() == (
        QTreeWidgetItem.ChildIndicatorPolicy.DontShowIndicatorWhenChildless
    )

    # Symetrique, sans quoi le test serait vert et vide : un noeud qui a des
    # enfants porte, lui, le controle.
    avec_enfants = arbre.element("lot-alpha-1")
    assert avec_enfants.childCount() == 2
    assert avec_enfants.childIndicatorPolicy() == (
        QTreeWidgetItem.ChildIndicatorPolicy.DontShowIndicatorWhenChildless
    )


def test_aucun_noeud_ne_force_un_expandeur_qu_il_ne_merite_pas(coquille):
    # Balayage complet : aucun element de l'arbre ne demande l'indicateur
    # inconditionnellement (`ShowIndicator`), ce qui ferait apparaitre un
    # expandeur sur une feuille.
    for arbre in (coquille.arbre_arborescence, coquille.chutier.arbre):
        for identifiant in arbre.tous_les_identifiants():
            element = arbre.element(identifiant)
            assert element.childIndicatorPolicy() != (
                QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator
            ), identifiant


def test_le_chemin_de_la_selection_se_deplie_sans_replier_le_reste(coquille):
    arbre = coquille.arbre_arborescence
    arbre.element("rush-beta").setExpanded(True)
    identifiant_de_scan = [
        noeud.identifiant
        for noeud in modele.parcourir(coquille.racines())
        if noeud.type == modele.TYPE_SCAN
    ][1]
    coquille.designer(identifiant_de_scan)

    # Le chemin du noeud designe est deplie...
    element = arbre.element(identifiant_de_scan)
    parent = element.parent()
    while parent is not None:
        assert parent.isExpanded()
        parent = parent.parent()
    # ... et la branche voisine, ouverte a la main, n'a pas ete repliee.
    assert arbre.element("rush-beta").isExpanded()


# ---------------------------------------------------------------------------
# La selection a trois etats est LISIBLE dans l'arbre (cases a cocher).
# ---------------------------------------------------------------------------


def test_le_troisieme_etat_est_visible_dans_le_chutier(coquille, qtbot):
    # Fabrique a deux rushes de DEUX lots chacun : il faut deux actionnables
    # sous un meme parent pour qu'un etat partiel existe.
    coquille.poser_projet(
        fab.manifest_deux_rushes_deux_lots_chacun(),
        existe=fab.liaison_factice(["medias/alpha.mov", "medias/beta.mov"]),
    )
    coquille.activer_atelier(1)  # Pdf : les lots sont actionnables
    qtbot.wait(10)
    # Cible en SECONDE position : le second rush, et on decoche son SECOND lot.
    coquille.selection.selectionner("rush-beta")
    coquille.selection.deselectionner("lot-beta-2")
    coquille.refleter_la_selection()
    qtbot.wait(10)

    arbre = coquille.chutier.arbre
    assert arbre.element("rush-beta").checkState(0) == Qt.CheckState.PartiallyChecked
    assert arbre.element("lot-beta-1").checkState(0) == Qt.CheckState.Checked
    assert arbre.element("lot-beta-2").checkState(0) == Qt.CheckState.Unchecked
    # Le premier rush n'est pas contamine : les trois etats sont bien
    # DERIVES, jamais poses globalement.
    assert arbre.element("rush-alpha").checkState(0) == Qt.CheckState.Unchecked


def test_changer_d_atelier_refait_la_selection_sur_le_bon_inventaire(coquille, qtbot):
    coquille.activer_atelier(1)
    qtbot.wait(10)
    assert coquille.selection.atelier == "atelier-pdf"
    coquille.activer_atelier(3)
    qtbot.wait(10)
    assert coquille.selection.atelier == "atelier-exports"
    coquille.selection.selectionner("rush-alpha")
    # Sur Exports, c'est le lot RECONSTRUIT qui est actionnable.
    assert coquille.selection.identifiants() == ("lot-alpha-2",)
