# Story 7.0, AC 2 -- fenetre unique, quatre onglets, zones de chrome,
# geometrie contractuelle (planchers, plafond derive, repli automatique,
# stabilite des largeurs au changement d'atelier).

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from mixed_media_utility.gui import jetons
from mixed_media_utility.gui.coquille import Coquille, ORDRE_ATELIERS


@pytest.fixture
def coquille(qtbot):
    fenetre = Coquille()
    qtbot.addWidget(fenetre)
    fenetre.show()
    qtbot.waitExposed(fenetre)
    return fenetre


def _attendre_layout(qtbot, fenetre):
    """Laisser la boucle d'evenements poser la geometrie."""
    qtbot.waitUntil(lambda: fenetre.width() > 0, timeout=2000)
    qtbot.wait(20)


# ---------------------------------------------------------------------------
# Taille minimale.
# ---------------------------------------------------------------------------


def test_la_fenetre_refuse_de_descendre_sous_la_taille_minimale(qtbot, coquille):
    coquille.resize(200, 200)
    _attendre_layout(qtbot, coquille)
    e = jetons.ESPACEMENTS
    assert coquille.width() >= e["window-min-width"]
    assert coquille.height() >= e["window-min-height"]


# ---------------------------------------------------------------------------
# Structure : en-tete, barre d'onglets basse, quatre ateliers dans l'ordre.
# ---------------------------------------------------------------------------


def test_en_tete_et_barre_d_onglets_aux_hauteurs_de_jetons(qtbot, coquille):
    e = jetons.ESPACEMENTS
    assert coquille.en_tete.height() == e["header-height"]
    assert coquille.barre_onglets.height() == e["tabbar-height"]
    # La barre d'onglets est en BAS : sous la bande centrale.
    assert coquille.barre_onglets.y() > coquille.en_tete.y()
    assert coquille.barre_onglets.y() > coquille.scene.y()


def test_quatre_ateliers_distinguables_dans_l_ordre_du_flux(coquille):
    ateliers = coquille.ateliers()
    assert len(ateliers) == 4
    # Elements DISTINGUABLES : quatre noms differents (regle des fabriques).
    assert len(set(ateliers)) == 4
    # L'ordre du flux : Extraction -> Pdf -> Scan -> Exports.
    assert ateliers == ("Extraction", "Pdf", "Scan", "Exports")
    assert len(ORDRE_ATELIERS) == 4


def test_l_atelier_actif_en_troisieme_position_rapporte_son_nom(qtbot, coquille):
    # Regle des fabriques : la cible est HORS premiere position (Scan, 3e),
    # et l'onglet actif rapporte SON nom, pas celui du premier.
    ateliers = coquille.ateliers()
    coquille.activer_atelier(2)
    qtbot.waitUntil(lambda: coquille.atelier_actif() == ateliers[2], timeout=2000)
    assert coquille.atelier_actif() == ateliers[2]
    assert coquille.atelier_actif() != ateliers[0]
    # La page montree est celle du meme atelier (pile alignee sur l'onglet).
    assert coquille.pile_ateliers.currentIndex() == 2


# ---------------------------------------------------------------------------
# Barre d'onglets : largeur EGALE (DESIGN.md:468). Regressif trouve par la
# revue de vague 1 : `setExpanding(False)` groupait les quatre onglets a
# gauche, a la largeur de leur contenu -- aucun test ne le mesurait.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("largeur_fenetre", [960, 1181, 1500])
def test_les_quatre_onglets_ont_une_largeur_egale_et_couvrent_la_barre(
    qtbot, coquille, largeur_fenetre
):
    e = jetons.ESPACEMENTS
    coquille.resize(largeur_fenetre, e["window-min-height"])
    _attendre_layout(qtbot, coquille)
    barre = coquille.barre_onglets
    largeurs = [barre.tabRect(i).width() for i in range(barre.count())]
    assert len(largeurs) == 4

    # Egales A L'ARRONDI PRES : la division entiere de la largeur de la
    # barre par 4 onglets peut laisser un reste (au plus 3 px, un par
    # onglet excedentaire).
    assert max(largeurs) - min(largeurs) <= 3, largeurs
    # La cible n'est pas la premiere position : le dernier onglet (Exports)
    # confronte au premier (Extraction), pas de comparaison degeneree.
    assert abs(largeurs[0] - largeurs[-1]) <= 3, largeurs

    # La barre est COUVERTE : aucun espace mort a droite, aucun debordement.
    assert sum(largeurs) == barre.width()
    assert barre.tabRect(3).x() + largeurs[3] == barre.width()


# ---------------------------------------------------------------------------
# Poignee : planchers constants, plafond derive.
# ---------------------------------------------------------------------------


def _largeurs_splitter(coquille):
    arbo, chutier, scene = coquille.splitter.sizes()
    return {"arborescence": arbo, "chutier": chutier, "scene": scene}


def test_arborescence_epinglee_a_la_largeur_minimale_ne_pousse_pas_la_scene_hors_fenetre(
    qtbot, coquille
):
    # Reproduction du defaut trouve par l'Edge Case Hunter (revue de vague
    # 1) : arborescence epinglee ouverte a window-min-width (960 px), la
    # scene reclamait x=420 largeur=640 (1060 px de besoin pour 960
    # disponibles) -- stage-min-width, que ce module enonce comme
    # "plancher, jamais franchi", etait franchi.
    e = jetons.ESPACEMENTS
    coquille.resize(e["window-min-width"], e["window-min-height"])
    _attendre_layout(qtbot, coquille)
    # Sous le seuil de repli, le defaut est replie (aucun choix explicite).
    assert coquille.panneau_arborescence.est_repliee

    # Choix explicite d'ouverture, pris a la largeur minimale.
    coquille.deplier_arborescence()
    _attendre_layout(qtbot, coquille)

    assert not coquille.panneau_arborescence.est_repliee
    # Le plancher de la scene n'est JAMAIS franchi : la fenetre a grandi
    # plutot que de laisser la scene deborder hors de la fenetre visible.
    assert coquille.scene.width() >= e["stage-min-width"]
    assert coquille.scene.x() + coquille.scene.width() <= coquille.width()
    # La fenetre a effectivement grandi au plancher recalcule (1060 px :
    # arborescence + 2 poignees + chutier + scene, tous a leur plancher).
    plancher_attendu = (
        e["tree-panel-min-width"]
        + 2 * e["splitter-width"]
        + e["bin-min-width"]
        + e["stage-min-width"]
    )
    assert coquille.width() >= plancher_attendu

    # Corollaire : la fenetre refuse desormais de redescendre sous ce
    # plancher tant que le panneau reste epingle ouvert.
    coquille.resize(e["window-min-width"], e["window-min-height"])
    _attendre_layout(qtbot, coquille)
    assert coquille.width() >= plancher_attendu
    assert coquille.scene.width() >= e["stage-min-width"]


def test_les_planchers_tiennent_aux_extremes_de_la_poignee(qtbot, coquille):
    e = jetons.ESPACEMENTS
    # Au-dessus du seuil de repli : l'arborescence est ouverte.
    coquille.resize(e["queue-overlay-threshold"], 800)
    _attendre_layout(qtbot, coquille)
    assert not coquille.panneau_arborescence.est_repliee

    extremes = [
        [100000, 0, 0],   # tout a l'arborescence
        [0, 100000, 0],   # tout au chutier
        [0, 0, 100000],   # tout a la scene
    ]
    for demande in extremes:
        coquille.splitter.setSizes(demande)
        qtbot.wait(10)
        largeurs = _largeurs_splitter(coquille)
        # Planchers constants du tableau fixe/reglable de DESIGN.md.
        assert largeurs["arborescence"] >= e["tree-panel-min-width"], demande
        assert largeurs["chutier"] >= e["bin-min-width"], demande
        # Plafond DERIVE : aucun geste ne fait descendre la scene sous son
        # plancher -- la largeur maximale d'un panneau est bornee par les
        # planchers des autres, jamais par une constante.
        assert largeurs["scene"] >= e["stage-min-width"], demande


# ---------------------------------------------------------------------------
# Arborescence : repli manuel, rail, repli automatique sous le seuil.
# ---------------------------------------------------------------------------


def test_l_arborescence_se_replie_sur_son_rail_et_se_rouvre(qtbot, coquille):
    e = jetons.ESPACEMENTS
    coquille.resize(e["queue-overlay-threshold"], 800)
    _attendre_layout(qtbot, coquille)
    assert not coquille.panneau_arborescence.est_repliee

    coquille.replier_arborescence()
    qtbot.wait(10)
    assert coquille.panneau_arborescence.est_repliee
    assert coquille.panneau_arborescence.width() == e["tree-panel-rail"]

    # Le rail est actionnable : son bouton rouvre l'arborescence.
    qtbot.mouseClick(
        coquille.panneau_arborescence.bouton_rouvrir, Qt.MouseButton.LeftButton
    )
    qtbot.wait(10)
    assert not coquille.panneau_arborescence.est_repliee
    assert coquille.panneau_arborescence.width() >= e["tree-panel-min-width"]


def test_sous_le_seuil_l_arborescence_se_replie_seule(qtbot, coquille):
    e = jetons.ESPACEMENTS
    seuil = e["tree-collapse-threshold"]
    coquille.resize(seuil + 100, 800)
    _attendre_layout(qtbot, coquille)
    assert not coquille.panneau_arborescence.est_repliee

    # Franchissement du seuil : repli SEUL, sans message (EPIC7-ARB-8).
    coquille.resize(seuil - 80, 800)
    _attendre_layout(qtbot, coquille)
    assert coquille.panneau_arborescence.est_repliee
    assert coquille.panneau_arborescence.width() == e["tree-panel-rail"]
    # Le rail reste actionnable sous le seuil.
    assert coquille.panneau_arborescence.bouton_rouvrir.isVisible()
    assert coquille.panneau_arborescence.bouton_rouvrir.isEnabled()


def test_un_choix_explicite_survit_au_franchissement_du_seuil(qtbot, coquille):
    # EXPERIENCE.md : le seuil fixe le defaut, il ne reprend pas la main.
    e = jetons.ESPACEMENTS
    seuil = e["tree-collapse-threshold"]

    # Sous le seuil, l'operatrice rouvre par le rail : choix explicite.
    coquille.resize(seuil - 80, 800)
    _attendre_layout(qtbot, coquille)
    assert coquille.panneau_arborescence.est_repliee
    qtbot.mouseClick(
        coquille.panneau_arborescence.bouton_rouvrir, Qt.MouseButton.LeftButton
    )
    qtbot.wait(10)
    assert not coquille.panneau_arborescence.est_repliee

    # Un redimensionnement toujours sous le seuil ne referme PAS le panneau.
    coquille.resize(seuil - 120, 800)
    _attendre_layout(qtbot, coquille)
    assert not coquille.panneau_arborescence.est_repliee

    # Symetrique : un repli choisi reste replie au-dessus du seuil.
    coquille.replier_arborescence()
    coquille.resize(seuil + 200, 800)
    _attendre_layout(qtbot, coquille)
    assert coquille.panneau_arborescence.est_repliee


def test_le_repli_automatique_se_rouvre_au_dessus_du_seuil(qtbot, coquille):
    # Sans choix explicite, le defaut suit le seuil dans les deux sens.
    e = jetons.ESPACEMENTS
    seuil = e["tree-collapse-threshold"]
    coquille.resize(seuil - 80, 800)
    _attendre_layout(qtbot, coquille)
    assert coquille.panneau_arborescence.est_repliee

    coquille.resize(seuil + 100, 800)
    _attendre_layout(qtbot, coquille)
    assert not coquille.panneau_arborescence.est_repliee


# ---------------------------------------------------------------------------
# Stabilite des largeurs au changement d'atelier.
# ---------------------------------------------------------------------------


def test_changer_d_atelier_ne_change_aucune_largeur(qtbot, coquille):
    e = jetons.ESPACEMENTS
    coquille.resize(e["queue-overlay-threshold"], 800)
    _attendre_layout(qtbot, coquille)
    # Une geometrie non triviale : la poignee a ete deplacee par l'operatrice.
    coquille.splitter.setSizes(
        [e["tree-panel-width"] + 30, e["bin-width"] + 20, 100000]
    )
    qtbot.wait(10)
    avant = coquille.largeurs_panneaux()

    # Deux bascules, dont une vers un atelier HORS premiere position.
    for indice in (2, 0):
        coquille.activer_atelier(indice)
        qtbot.wait(10)
        apres = coquille.largeurs_panneaux()
        # Egalite STRICTE : seul le geste de l'operatrice deplace les
        # largeurs, jamais un changement d'atelier (EXPERIENCE.md).
        assert apres == avant, f"bascule vers l'atelier {indice}"


# ---------------------------------------------------------------------------
# Point d'entree (tache 6) : construction headless sans boucle d'evenements.
# ---------------------------------------------------------------------------


def test_le_point_d_entree_construit_la_coquille_offscreen(qtbot):
    from mixed_media_utility.gui.__main__ import construire_application

    application, fenetre = construire_application([])
    qtbot.addWidget(fenetre)
    assert isinstance(fenetre, Coquille)
    fenetre.show()
    qtbot.waitExposed(fenetre)
    assert fenetre.isVisible()


def test_des_arguments_ignores_par_un_singleton_existant_sont_journalises(
    qtbot, caplog
):
    # Le banc GUI a TOUJOURS un QApplication deja construit (pytest-qt) :
    # tout appel avec des `arguments` non vides tombe donc systematiquement
    # dans la branche "singleton reutilise". Avant le correctif, l'appelant
    # n'avait ni effet ni avertissement (revue de vague 1) ; on verifie ici
    # l'avertissement, pas un effet sur Qt (impossible a observer une fois
    # le singleton construit).
    import logging

    from mixed_media_utility.gui.__main__ import construire_application

    assert QApplication.instance() is not None  # precondition : deja pose
    with caplog.at_level(logging.WARNING, logger="mixed_media_utility.gui.__main__"):
        application, fenetre = construire_application(["--un-argument-ignore"])
    qtbot.addWidget(fenetre)
    assert any(
        "arguments" in enregistrement.message and "ignore" in enregistrement.message
        for enregistrement in caplog.records
    ), "aucun avertissement journalise pour des arguments ignores"

    # Corollaire (regle des fabriques, cas symetrique) : des arguments VIDES
    # ne declenchent aucun avertissement -- il n'y a rien a ignorer.
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="mixed_media_utility.gui.__main__"):
        _, fenetre_vide = construire_application([])
    qtbot.addWidget(fenetre_vide)
    assert caplog.records == []
