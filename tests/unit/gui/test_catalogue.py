# Story 7.0, AC 6 -- chaines utilisateur en catalogue, interface en
# francais, aucune boite calee sur une chaine : substitution de catalogue
# marque, puis catalogue gonfle de 40 % a la taille minimale.

import math

import pytest
from PySide6.QtWidgets import QLabel, QToolButton

from mixed_media_utility.gui import catalogue, jetons
from mixed_media_utility.gui.coquille import Coquille

MARQUE = "@@"


# ---------------------------------------------------------------------------
# Structure du catalogue.
# ---------------------------------------------------------------------------


def test_les_cles_sont_ascii_et_les_valeurs_non_vides():
    assert catalogue.CHAINES, "le catalogue ne doit pas etre vide"
    for cle, valeur in catalogue.CHAINES.items():
        assert cle.isascii(), f"cle non ASCII : {cle!r}"
        assert isinstance(valeur, str) and valeur.strip(), f"valeur vide : {cle}"


def test_le_catalogue_porte_les_quatre_ateliers():
    for cle in ("atelier-extraction", "atelier-pdf", "atelier-scan",
                "atelier-exports"):
        assert cle in catalogue.CHAINES


def test_le_catalogue_couvre_chaque_etat_de_l_executeur():
    # Contrat, pas duplication : la cle attendue se DERIVE de la constante
    # d'etat de l'executeur (``gui/executeur.py``), jamais recopiee en dur
    # ici -- un etat renomme cote executeur fait echouer ce test plutot que
    # de laisser une entree de catalogue orpheline (revue de vague 1 :
    # les trois entrees etaient posees mais cablees nulle part).
    from mixed_media_utility.gui import executeur

    etats = (executeur.EN_COURS, executeur.TERMINEE, executeur.ECHOUEE)
    # Regle des fabriques : trois etats distinguables, pas de doublon.
    assert len(set(etats)) == 3
    libelles = []
    for etat in etats:
        cle = f"etat-tache-{etat}"
        assert cle in catalogue.CHAINES, f"etat non cable au catalogue : {etat}"
        valeur = catalogue.CHAINES[cle]
        assert valeur.strip(), f"libelle vide pour l'etat {etat}"
        libelles.append(valeur)
    # Les trois libelles restent distinguables (aucun repli sur un seul
    # texte generique pour les trois etats).
    assert len(set(libelles)) == 3


# ---------------------------------------------------------------------------
# Substitution : aucun libelle de la coquille n'est une chaine en dur.
# ---------------------------------------------------------------------------


def _libelles_visibles(fenetre):
    """Tous les textes affiches par la coquille (libelles et onglets)."""
    textes = [fenetre.windowTitle()]
    for libelle in fenetre.findChildren(QLabel):
        if libelle.text():
            textes.append(libelle.text())
    for bouton in fenetre.findChildren(QToolButton):
        # Les boutons de defilement INTERNES de QTabBar (enfants de la
        # barre, desactives par la coquille) portent des noms accessibles
        # anglais poses par Qt : ce ne sont pas des libelles de la coquille.
        if bouton.parent() is fenetre.barre_onglets:
            continue
        # Le TEXTE d'un bouton-outil est un pictogramme depuis la passe de
        # chrome du 2026-08-26 (les fleches Qt natives se peignaient au style
        # de la plateforme). Un pictogramme ne se traduit pas et n'entre donc
        # jamais au catalogue : la liste est LUE de `jetons`, jamais recopiee
        # ici. Le geste, lui, reste nomme par l'infobulle et le nom
        # accessible, tous deux du catalogue -- c'est ce que ce test mesure.
        pictogrammes = jetons.pictogrammes()
        for porte in (bouton.text(), bouton.toolTip(), bouton.accessibleName()):
            if porte and porte not in pictogrammes:
                textes.append(porte)
    barre = fenetre.barre_onglets
    for indice in range(barre.count()):
        textes.append(barre.tabText(indice))
    return textes


def test_tous_les_libelles_viennent_du_catalogue(qtbot):
    # Catalogue de test aux valeurs MARQUEES : si un libelle de la coquille
    # ne porte pas la marque, il etait ecrit en dur.
    marque = {cle: MARQUE + valeur for cle, valeur in catalogue.CHAINES.items()}
    fenetre = Coquille(chaines=marque)
    qtbot.addWidget(fenetre)
    libelles = _libelles_visibles(fenetre)
    assert libelles, "la coquille doit afficher des libelles"
    fautifs = [texte for texte in libelles if MARQUE not in texte]
    assert fautifs == [], f"libelles hors catalogue : {fautifs}"


# ---------------------------------------------------------------------------
# Chaines gonflees de 40 % : aucune troncature a la taille minimale.
# ---------------------------------------------------------------------------


def _gonfler(valeur):
    """Allonger une chaine de 40 % (regle i18n de DESIGN.md)."""
    ajout = max(1, math.ceil(0.4 * len(valeur)))
    return valeur + "x" * ajout


@pytest.fixture
def coquille_gonflee(qtbot):
    gonfle = {cle: _gonfler(valeur) for cle, valeur in catalogue.CHAINES.items()}
    fenetre = Coquille(chaines=gonfle)
    qtbot.addWidget(fenetre)
    e = jetons.ESPACEMENTS
    fenetre.resize(e["window-min-width"], e["window-min-height"])
    fenetre.show()
    qtbot.waitExposed(fenetre)
    qtbot.wait(20)
    return fenetre


def test_la_coquille_gonflee_s_instancie_a_la_taille_minimale(coquille_gonflee):
    e = jetons.ESPACEMENTS
    # Aucune boite n'est calee sur une chaine : la fenetre minimale reste
    # atteignable avec toutes les chaines allongees de 40 %.
    assert coquille_gonflee.width() == e["window-min-width"]
    assert coquille_gonflee.height() == e["window-min-height"]


def test_aucun_onglet_gonfle_n_est_tronque(coquille_gonflee):
    # Les onglets sont les libelles interactifs de la coquille : pas
    # d'elide, la boite de chaque onglet couvre son texte gonfle.
    barre = coquille_gonflee.barre_onglets
    metrique = barre.fontMetrics()
    for indice in range(barre.count()):
        texte = barre.tabText(indice)
        assert metrique.elidedText(
            texte, barre.elideMode(), barre.tabRect(indice).width()
        ) == texte, f"onglet tronque : {texte!r}"
        assert barre.tabRect(indice).width() >= metrique.horizontalAdvance(texte)


def test_aucun_libelle_gonfle_n_est_tronque_horizontalement(coquille_gonflee):
    # Les libelles de zone passent sur plusieurs lignes plutot que d'etre
    # coupes : toute etiquette VISIBLE tient son texte (retour a la ligne
    # actif, ou boite au moins aussi large que le texte).
    for libelle in coquille_gonflee.findChildren(QLabel):
        if not libelle.isVisible() or not libelle.text():
            continue
        couvre = libelle.wordWrap() or (
            libelle.width() >= libelle.fontMetrics().horizontalAdvance(libelle.text())
        )
        assert couvre, f"libelle tronque : {libelle.text()!r}"
