# -*- coding: utf-8 -*-
"""Le zoom des surfaces d'image : il AGIT (passe de chrome du 2026-08-26).

Motif de ce fichier. Jusqu'a cette date, `BarreDeVue` emettait `zoom_change`
et `controle_active`, `VueGalerie` portait un curseur `zoom_vignettes` -- et
**personne ne s'y abonnait**. Le curseur glissait, les quatre boutons
s'enfoncaient, l'image ne bougeait pas d'un pixel : « le zoom sur la page pdf
n'est absolument pas fonctionnel » (Egan, premier essai de terrain).

Les tests d'alors mesuraient la barre : ses bornes, son pas, son absence de
graduation, l'unicite de sa classe. Aucun ne mesurait son EFFET -- et
`test_scan_frontieres_jugement.py` allait jusqu'a appeler
`barre_de_vue.zoom.setValue(180)` au milieu d'un parcours, pour verifier
qu'aucun fichier n'etait ecrit : le curseur etait donc actionne par le banc,
sans que rien ne demande a l'image d'avoir bouge.

C'est la lecon a retenir, et elle est de la meme famille que la regle des
fabriques : **un signal dont aucun test ne mesure l'effet est un signal qu'on
peut oublier de brancher sans qu'aucun test ne rougisse.**
"""

from __future__ import annotations

import pytest

import fabriques_detection as fab
from mixed_media_utility.gui import barre_de_vue, catalogue, scan_jugement
from mixed_media_utility.gui import lecture_detection as lecture


@pytest.fixture
def atelier(qtbot):
    """Un atelier montrant un document a DEUX pages, cible en seconde."""
    document = lecture.depuis_json(fab.deux_pages_cible_seconde())
    surface = scan_jugement.AtelierScanJugement(catalogue.CHAINES)
    qtbot.addWidget(surface)
    surface.resize(1200, 800)
    surface.show()
    surface.poser_document(document, document.page_par_adresse(*fab.ADRESSE_CIBLE))
    return surface


def _reference(vue):
    return vue.scene.contenu.rectangle_de_reference()


# ---------------------------------------------------------------------------
# Le curseur agit sur l'image
# ---------------------------------------------------------------------------


def test_glisser_le_curseur_AGRANDIT_reellement_l_image(atelier):
    """L'assertion porte sur la GEOMETRIE rendue, pas sur la valeur du curseur.

    Mesurer `zoom.value() == 200` serait tautologique : c'est la valeur qu'on
    vient de poser. Ce qui doit changer, c'est le rectangle ou la page
    atterrit.
    """
    vue = atelier.vue_page
    avant = _reference(vue)
    assert avant.width() > 0, "la page n'est pas rendue, le test ne mesure rien"

    vue.barre_de_vue.zoom.setValue(200)

    apres = _reference(vue)
    assert apres.width() == pytest.approx(avant.width() * 2.0, rel=0.02)
    assert apres.height() == pytest.approx(avant.height() * 2.0, rel=0.02)


def test_le_curseur_reduit_AUSSI(atelier):
    """Volet symetrique : sans lui, un branchement qui ne saurait qu'agrandir
    -- ou qui poserait un facteur constant -- passerait le test precedent."""
    vue = atelier.vue_page
    avant = _reference(vue)

    vue.barre_de_vue.zoom.setValue(50)

    assert _reference(vue).width() == pytest.approx(avant.width() * 0.5, rel=0.02)


def test_le_zoom_emporte_les_surimpressions_avec_l_image(atelier):
    """Les traits suivent la page, sinon ils mentent sur ce qui sera decoupe.

    C'est l'assertion qui compte le plus de ce fichier : un zoom applique a
    l'image seule laisserait les zones proposees a leur place d'avant,
    c'est-a-dire **a cote de ce qu'elles designent**.
    """
    vue = atelier.vue_page
    contenu = vue.scene.contenu
    assert contenu.plan, "la page ne porte aucun trait, le test ne mesure rien"
    trait = contenu.plan[0]
    avant = contenu.rectangle_du_trait(trait)
    page_avant = _reference(vue)

    vue.barre_de_vue.zoom.setValue(200)

    apres = contenu.rectangle_du_trait(trait)
    page_apres = _reference(vue)
    assert apres.width() == pytest.approx(avant.width() * 2.0, rel=0.02)
    # Et il reste au meme endroit RELATIF dans la page.
    relatif_avant = (avant.x() - page_avant.x()) / max(page_avant.width(), 1)
    relatif_apres = (apres.x() - page_apres.x()) / max(page_apres.width(), 1)
    assert relatif_apres == pytest.approx(relatif_avant, abs=0.01)


# ---------------------------------------------------------------------------
# Les quatre boutons
# ---------------------------------------------------------------------------


def test_ajuster_ramene_la_page_ENTIERE_dans_la_scene(atelier):
    vue = atelier.vue_page
    contenu = vue.scene.contenu
    vue.barre_de_vue.zoom.setValue(300)
    assert contenu.rectangle_de_reference().width() > contenu.width()

    vue.barre_de_vue.boutons[barre_de_vue.CONTROLE_AJUSTER].click()

    rendu = contenu.rectangle_de_reference()
    assert rendu.width() <= contenu.width() + 1
    assert rendu.height() <= contenu.height() + 1


def test_pleine_largeur_et_pleine_hauteur_ne_font_PAS_la_meme_chose(atelier):
    """Deux boutons distincts doivent produire deux cadrages distincts.

    Sans ce volet, quatre boutons cables sur le meme geste passeraient chacun
    leur test pris isolement -- c'est la forme que prendrait un copier-coller
    de branchement.
    """
    vue = atelier.vue_page
    contenu = vue.scene.contenu

    vue.barre_de_vue.boutons[barre_de_vue.CONTROLE_PLEINE_LARGEUR].click()
    largeur = contenu.rectangle_de_reference()
    vue.barre_de_vue.boutons[barre_de_vue.CONTROLE_PLEINE_HAUTEUR].click()
    hauteur = contenu.rectangle_de_reference()

    assert largeur.width() == pytest.approx(contenu.width(), abs=2)
    assert hauteur.height() == pytest.approx(contenu.height(), abs=2)
    assert largeur.size() != hauteur.size()


def test_un_bouton_de_vue_ACCORDE_le_curseur_au_facteur_obtenu(atelier):
    """Un curseur reste a 100 % pendant que l'image en fait 180 mentirait."""
    vue = atelier.vue_page
    vue.barre_de_vue.boutons[barre_de_vue.CONTROLE_PLEINE_LARGEUR].click()

    attendu = round(vue.scene.contenu.zoom * 100)
    assert vue.barre_de_vue.zoom.value() == attendu


def test_taille_reelle_donne_un_pixel_pour_un_pixel(atelier):
    """Et l'accord du curseur ne doit pas lui reprendre sa precision.

    Si l'accord reemettait `zoom_change`, la scene se verrait redemander son
    propre facteur ARRONDI au pourcent : le pixel-pour-pixel serait perdu au
    premier clic, sans qu'aucune valeur affichee ne le montre.
    """
    vue = atelier.vue_page
    vue.barre_de_vue.boutons[barre_de_vue.CONTROLE_TAILLE_REELLE].click()

    largeur_px = vue.scene.contenu.repere_px[0]
    assert vue.scene.contenu.rectangle_de_reference().width() == pytest.approx(
        largeur_px, rel=0.01
    )


# ---------------------------------------------------------------------------
# Le deplacement : un zoom sans deplacement ne sert a rien
# ---------------------------------------------------------------------------


def test_une_page_agrandie_se_DEPLACE_a_la_souris(atelier, qtbot):
    """Agrandir pour ne plus pouvoir atteindre le coin qu'on visait, c'est
    pire que ne pas agrandir."""
    from PySide6.QtCore import QPoint, Qt

    contenu = atelier.vue_page.scene.contenu
    atelier.vue_page.barre_de_vue.zoom.setValue(300)
    avant = contenu.rectangle_de_reference()

    depart = QPoint(contenu.width() // 2, contenu.height() // 2)
    qtbot.mousePress(contenu, Qt.MouseButton.LeftButton, pos=depart)
    qtbot.mouseMove(contenu, pos=depart + QPoint(60, 40))
    qtbot.mouseRelease(
        contenu, Qt.MouseButton.LeftButton, pos=depart + QPoint(60, 40)
    )

    apres = contenu.rectangle_de_reference()
    assert (apres.x(), apres.y()) != (avant.x(), avant.y()), (
        "la page agrandie n'a pas bouge"
    )


def test_une_page_ENTIEREMENT_visible_ne_se_deplace_pas(atelier, qtbot):
    """Volet symetrique. Sans lui, un deplacement toujours actif passerait le
    test precedent tout en permettant de pousser hors du cadre une page qui
    tenait entierement dedans -- et l'operatrice n'aurait aucun moyen de
    savoir dans quelle direction la ramener."""
    from PySide6.QtCore import QPoint, Qt

    contenu = atelier.vue_page.scene.contenu
    atelier.vue_page.barre_de_vue.boutons[barre_de_vue.CONTROLE_AJUSTER].click()
    avant = contenu.rectangle_de_reference()

    depart = QPoint(contenu.width() // 2, contenu.height() // 2)
    qtbot.mousePress(contenu, Qt.MouseButton.LeftButton, pos=depart)
    qtbot.mouseMove(contenu, pos=depart + QPoint(80, 60))
    qtbot.mouseRelease(
        contenu, Qt.MouseButton.LeftButton, pos=depart + QPoint(80, 60)
    )

    apres = contenu.rectangle_de_reference()
    assert (apres.x(), apres.y()) == (avant.x(), avant.y())


# ---------------------------------------------------------------------------
# Le zoom de vignettes de la galerie
# ---------------------------------------------------------------------------


def test_le_curseur_de_vignettes_agrandit_les_apercus(atelier):
    galerie = atelier.vue_galerie
    assert len(galerie.lignes) >= 2, "la fabrique doit poser DEUX pages"
    # La cible est la SECONDE ligne : un branchement qui n'agirait que sur la
    # premiere -- ou sur une seule -- se demasque.
    seconde = galerie.lignes[1]
    avant = seconde.apercu.minimumHeight()

    galerie.zoom_vignettes.setValue(200)

    assert seconde.apercu.minimumHeight() == pytest.approx(avant * 2, abs=2)
    assert galerie.lignes[0].apercu.minimumHeight() == pytest.approx(avant * 2, abs=2)


def test_redescendre_a_cent_pour_cent_rend_la_taille_de_depart(atelier):
    """Le zoom se recalcule depuis la REFERENCE, jamais depuis la valeur
    courante : sinon deux zooms successifs se composent et 100 % ne revient
    jamais."""
    galerie = atelier.vue_galerie
    seconde = galerie.lignes[1]
    depart = seconde.apercu.minimumHeight()

    galerie.zoom_vignettes.setValue(200)
    galerie.zoom_vignettes.setValue(150)
    galerie.zoom_vignettes.setValue(100)

    assert seconde.apercu.minimumHeight() == depart
