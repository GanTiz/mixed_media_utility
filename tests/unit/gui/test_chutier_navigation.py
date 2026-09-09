# -*- coding: utf-8 -*-
"""Story 7.2, AC 3 -- un clic designe, un double-clic ouvre.

« Le clic ne declenche donc plus aucune navigation » (`EPIC7-ARB-2`). Le
double-clic ouvre selon la carte fixee par Egan (`EPIC7-ARB-11`), **un cas de
test par type** : c'est l'AC qui casse si la spine d'avant correction est
reprise -- les cas « planche -> Pdf » et « rush encode -> Exports » sont
precisement ceux qu'une lecture perimee enverrait ailleurs, ils ne sont donc
jamais fusionnes avec les autres.
"""

from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

import fabriques_chutier as fab
from mixed_media_utility.gui import chutier as module_chutier
from mixed_media_utility.gui import jetons
from mixed_media_utility.gui import modele_chutier as modele
from mixed_media_utility.gui.coquille import ORDRE_ATELIERS, Coquille


@pytest.fixture
def coquille(qtbot):
    fenetre = Coquille()
    qtbot.addWidget(fenetre)
    fenetre.show()
    qtbot.waitExposed(fenetre)
    fenetre.poser_projet(
        fab.manifest_six_types(),
        documents_de_detection=[fab.detection_de_lot_alpha_1()],
        existe=fab.liaison_factice(["medias/alpha.mov", "medias/beta.mov"]),
    )
    return fenetre


def _double_cliquer(arbre, element):
    """Un VRAI double-clic sur une ligne d'arbre, par le chemin de Qt.

    **`qtbot.mouseDClick` est inert sur ce banc** : mesure faite ici, il ne
    fait pas emettre `itemDoubleClicked` a un `QTreeWidget` sous la
    plateforme `offscreen` (aucun destinataire, aucune erreur -- un test qui
    s'en contenterait serait vert et vide). Le geste correct est celui-ci :
    un clic reel, puis l'evenement `MouseButtonDblClick` remis au viewport,
    qui passe par `QAbstractItemView.mouseDoubleClickEvent` -- donc par le
    code du produit, pas par un raccourci de test.
    """
    rectangle = arbre.visualItemRect(element)
    position = QPointF(rectangle.center())
    QApplication.sendEvent(
        arbre.viewport(),
        QMouseEvent(
            QEvent.Type.MouseButtonDblClick,
            position,
            arbre.viewport().mapToGlobal(position),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        ),
    )


def _identifiant_de_type(coquille, type_de_noeud):
    """Le premier noeud d'un type donne, retrouve par PARCOURS de l'arbre."""
    for noeud in modele.parcourir(coquille.racines()):
        if noeud.type == type_de_noeud:
            return noeud.identifiant
    raise AssertionError(f"aucun noeud de type {type_de_noeud} dans la fixture")


# ---------------------------------------------------------------------------
# Un clic designe -- et rien d'autre.
# ---------------------------------------------------------------------------


def test_un_clic_designe_sans_changer_d_atelier(qtbot, coquille):
    # L'atelier courant est Scan (3e onglet) ; on clique un noeud de type
    # rush, dont la destination serait Extraction. Les DEUX assertions.
    coquille.activer_atelier(2)
    qtbot.wait(10)
    avant = coquille.atelier_actif()

    element = coquille.arbre_arborescence.element("rush-beta")
    assert element is not None
    coquille.arbre_arborescence.setCurrentItem(element)
    coquille.arbre_arborescence.itemClicked.emit(element, 0)
    qtbot.wait(10)

    assert coquille.designation() == "rush-beta"
    assert coquille.atelier_actif() == avant


def test_un_clic_reel_a_la_souris_ne_navigue_pas(qtbot, coquille):
    # Le meme, par un VRAI clic : le chemin des signaux Qt est celui du
    # produit, pas seulement celui du test.
    coquille.resize(jetons.ESPACEMENTS["queue-overlay-threshold"], 800)
    qtbot.wait(20)
    coquille.activer_atelier(1)
    qtbot.wait(10)
    avant = coquille.atelier_actif()
    arbre = coquille.arbre_arborescence
    element = arbre.element("lot-alpha-2")
    arbre.expandAll()
    qtbot.wait(10)
    rectangle = arbre.visualItemRect(element)
    qtbot.mouseClick(arbre.viewport(), Qt.MouseButton.LeftButton, pos=rectangle.center())
    qtbot.wait(10)
    assert coquille.designation() == "lot-alpha-2"
    assert coquille.atelier_actif() == avant


# ---------------------------------------------------------------------------
# Un double-clic ouvre : la carte d'EPIC7-ARB-11, un cas par type.
# ---------------------------------------------------------------------------


def _ouvrir(coquille, identifiant):
    return coquille.ouvrir(identifiant)


def test_double_clic_sur_un_rush_ouvre_extraction(coquille):
    assert _ouvrir(coquille, "rush-alpha") == "atelier-extraction"
    assert coquille.atelier_actif() == coquille.ateliers()[0]


def test_double_clic_sur_un_lot_ouvre_pdf(coquille):
    assert _ouvrir(coquille, "lot-alpha-1") == "atelier-pdf"
    assert coquille.atelier_actif() == coquille.ateliers()[1]


def test_double_clic_sur_une_planche_ouvre_pdf(coquille):
    # Cas a NE PAS fusionner : une lecture perimee de la spine enverrait la
    # planche sur Scan. Elle est une FIN d'etape -- elle ne produit plus rien
    # dans l'outil --, donc elle renvoie a l'atelier qui l'a produite.
    identifiant = _identifiant_de_type(coquille, modele.TYPE_PLANCHE)
    assert _ouvrir(coquille, identifiant) == "atelier-pdf"
    assert coquille.atelier_actif() == coquille.ateliers()[1]


def test_double_clic_sur_un_scan_ouvre_scan(coquille):
    identifiant = _identifiant_de_type(coquille, modele.TYPE_SCAN)
    assert _ouvrir(coquille, identifiant) == "atelier-scan"
    assert coquille.atelier_actif() == coquille.ateliers()[2]


def test_double_clic_sur_un_lot_reconstruit_ouvre_exports(coquille):
    assert _ouvrir(coquille, "lot-alpha-2") == "atelier-exports"
    assert coquille.atelier_actif() == coquille.ateliers()[3]


def test_double_clic_sur_un_rush_encode_ouvre_exports(coquille):
    # Second cas a NE PAS fusionner : le rush encode n'est pas liste dans la
    # table d'origine ; c'est le principe unifie qui le place (sans
    # consommateur dans l'outil, il renvoie a l'atelier producteur).
    assert _ouvrir(coquille, "rush-beta") == "atelier-exports"
    assert coquille.atelier_actif() == coquille.ateliers()[3]


def test_la_carte_couvre_les_six_types_et_rien_de_plus(coquille):
    # La carte est fermee : un type nouveau sans destination se verrait ici
    # plutot qu'a l'execution, par un KeyError dans une main d'operatrice.
    assert set(modele.ATELIER_PAR_TYPE) == set(modele.TYPES_DE_NOEUD)
    for cle in modele.ATELIER_PAR_TYPE.values():
        assert cle in ORDRE_ATELIERS


def test_un_double_clic_reel_active_l_onglet_de_destination(qtbot, coquille):
    coquille.resize(jetons.ESPACEMENTS["queue-overlay-threshold"], 800)
    qtbot.wait(20)
    coquille.activer_atelier(0)
    qtbot.wait(10)
    arbre = coquille.arbre_arborescence
    arbre.expandAll()
    qtbot.wait(10)
    element = arbre.element("lot-alpha-1")
    rectangle = arbre.visualItemRect(element)
    qtbot.mouseClick(
        arbre.viewport(), Qt.MouseButton.LeftButton, pos=rectangle.center()
    )
    qtbot.wait(10)
    # Le clic seul n'a PAS navigue -- l'assertion qui rend le suivant
    # signifiant (sans elle, le test serait vert meme si le clic naviguait).
    assert coquille.atelier_actif() == coquille.ateliers()[0]
    _double_cliquer(arbre, element)
    qtbot.wait(10)
    assert coquille.atelier_actif() == coquille.ateliers()[1]


def test_ouvrir_un_identifiant_inconnu_ne_navigue_pas(coquille):
    # Symetrique : la carte ne se declenche pas sur ce qui n'existe pas.
    coquille.activer_atelier(2)
    avant = coquille.atelier_actif()
    assert coquille.ouvrir("noeud-qui-n-existe-pas") is None
    assert coquille.atelier_actif() == avant


# ---------------------------------------------------------------------------
# Frontiere negative : aucun autre declencheur de navigation.
# ---------------------------------------------------------------------------


def test_le_survol_n_ouvre_rien(qtbot, coquille):
    coquille.resize(jetons.ESPACEMENTS["queue-overlay-threshold"], 800)
    qtbot.wait(20)
    coquille.activer_atelier(0)
    qtbot.wait(10)
    avant = coquille.atelier_actif()
    arbre = coquille.arbre_arborescence
    arbre.expandAll()
    qtbot.wait(10)
    element = arbre.element("lot-alpha-1")
    rectangle = arbre.visualItemRect(element)
    qtbot.mouseMove(arbre.viewport(), pos=rectangle.center())
    qtbot.wait(20)
    assert coquille.atelier_actif() == avant
    assert coquille.designation() is None


def test_aucun_signal_de_survol_n_est_cable_dans_le_chutier():
    # Grep de frontiere : le composant ne connecte NI `itemEntered`, NI
    # `entered`, NI un evenement de survol -- l'ouverture au survol n'a
    # aucun chemin pour exister.
    source = Path(module_chutier.__file__).read_text(encoding="utf-8")
    for motif in ("itemEntered", ".entered.", "enterEvent", "hoverEnter"):
        assert motif not in source, f"declencheur de survol cable : {motif}"


def test_le_double_clic_ne_deplie_pas_a_la_place_d_ouvrir(coquille):
    # `setExpandsOnDoubleClick(False)` : le double-clic OUVRE, il ne se
    # depense pas a plier ou deplier une branche.
    assert coquille.arbre_arborescence.expandsOnDoubleClick() is False
    assert coquille.chutier.arbre.expandsOnDoubleClick() is False
