# -*- coding: utf-8 -*-
"""Story 7.4, AC 5 -- UN composant de controles de vue, et les onglets.

« Un jeu de controles de vue commun a toutes les surfaces d'image [...] c'est
donc un composant, pas trois reglages » (correction ``A10``).
"""

import ast
from pathlib import Path

import pytest

import fabriques_detection as fab
from mixed_media_utility.gui import scan_jugement, barre_de_vue, catalogue, jetons
from mixed_media_utility.gui import lecture_detection as lecture

_PAQUET_GUI = Path(jetons.__file__).resolve().parent


def _atelier(qtbot, chaines=None):
    atelier = scan_jugement.AtelierScanJugement(chaines or catalogue.CHAINES)
    qtbot.addWidget(atelier)
    atelier.resize(1200, 800)
    atelier.show()
    return atelier


# ---------------------------------------------------------------------------
# UN composant, instancie par les trois surfaces
# ---------------------------------------------------------------------------


def test_les_trois_surfaces_instancient_la_MEME_classe_de_barre_de_vue(qtbot):
    atelier = _atelier(qtbot)
    surfaces = (atelier.vue_page, atelier.vue_galerie, atelier.vue_frame)
    assert len(surfaces) == 3
    for surface in surfaces:
        # Assertion sur le TYPE, pas sur l'apparence : trois barres qui se
        # ressembleraient sans partager leur classe seraient trois reglages.
        assert type(surface.barre_de_vue) is barre_de_vue.BarreDeVue
    # Trois INSTANCES distinctes : une barre partagee serait un seul controle
    # pour trois scenes, ce qui est un autre defaut.
    assert len({id(surface.barre_de_vue) for surface in surfaces}) == 3


def test_le_depot_ne_contient_qu_une_implementation_de_ces_cinq_controles():
    """Le grep : une seconde implementation serait une divergence en attente.

    On cherche les modules de ``gui/`` qui definissent les CINQ controles.
    Le balayage porte sur le code (AST), jamais sur les docstrings.
    """
    definisseurs = []
    for source in sorted(_PAQUET_GUI.rglob("*.py")):
        arbre = ast.parse(source.read_text(encoding="utf-8"))
        litteraux = {
            noeud.value
            for noeud in ast.walk(arbre)
            if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str)
        }
        attendus = set(barre_de_vue.CONTROLES_DE_VUE)
        if attendus.issubset(litteraux):
            definisseurs.append(source.name)
    assert definisseurs == ["barre_de_vue.py"], (
        f"plus d'une implementation des controles de vue : {definisseurs}"
    )


def test_le_bouton_d_ajustement_s_intitule_ajuster_et_jamais_largeur(qtbot):
    """``EPIC7-ARB-17``, verbatim : « "ajuster", et non "largeur" »."""
    barre = barre_de_vue.BarreDeVue(catalogue.CHAINES)
    qtbot.addWidget(barre)
    bouton = barre.boutons[barre_de_vue.CONTROLE_AJUSTER]
    assert bouton.text().casefold() == "ajuster"
    assert barre.libelle(barre_de_vue.CONTROLE_AJUSTER) == bouton.text()
    # Aucune chaine « largeur » ne designe CE bouton -- ni son libelle, ni
    # son nom d'objet, ni son infobulle. « Pleine largeur » reste, mais c'est
    # un AUTRE bouton, et le test le verifie explicitement.
    for texte in (bouton.text(), bouton.objectName(), bouton.toolTip()):
        assert "largeur" not in texte.casefold(), texte
    autre = barre.boutons[barre_de_vue.CONTROLE_PLEINE_LARGEUR]
    assert autre is not bouton
    assert "largeur" in autre.text().casefold()


def test_les_cinq_controles_sont_la_et_le_zoom_est_continu(qtbot):
    barre = barre_de_vue.BarreDeVue(catalogue.CHAINES)
    qtbot.addWidget(barre)
    assert set(barre.controles) == set(barre_de_vue.CONTROLES_DE_VUE)
    assert len(barre_de_vue.CONTROLES_DE_VUE) == 5
    # Continu, SANS PALIERS (`EXPERIENCE.md`, Interaction Primitives).
    assert barre.zoom.pageStep() == 1
    assert barre.zoom.singleStep() == 1
    assert barre.zoom.tickPosition().name == "NoTicks"


def test_zero_libelle_de_controle_de_vue_ecrit_en_dur_dans_un_ecran():
    """Ils viennent du catalogue, jamais d'un module d'ecran."""
    libelles = {
        catalogue.CHAINES[f"vue-{cle}"] for cle in barre_de_vue.CONTROLES_DE_VUE
    }
    libelles |= {
        catalogue.CHAINES[f"scan-onglet-{cle}"]
        for cle in barre_de_vue.ONGLETS_DE_VUE
    }
    fautifs = {}
    for nom in ("scan_jugement.py", "surimpressions.py", "raster_de_page.py",
                "barre_de_vue.py"):
        arbre = ast.parse((_PAQUET_GUI / nom).read_text(encoding="utf-8"))
        litteraux = {
            noeud.value
            for noeud in ast.walk(arbre)
            if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str)
        }
        trouves = sorted(litteraux & libelles)
        if trouves:
            fautifs[nom] = trouves
    assert fautifs == {}, f"libelle en dur dans un ecran : {fautifs}"


def test_le_grep_de_libelle_en_dur_mord_sur_un_temoin():
    """Le symetrique : le grep echoue vraiment quand il doit."""
    libelles = {catalogue.CHAINES["vue-ajuster"]}
    temoin = ast.parse('bouton = QPushButton("Ajuster")\n')
    litteraux = {
        noeud.value for noeud in ast.walk(temoin)
        if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str)
    }
    assert litteraux & libelles == {"Ajuster"}


# ---------------------------------------------------------------------------
# Onglets : absent sans objet, grise quand indisponible (EPIC7-ARB-24)
# ---------------------------------------------------------------------------


def test_l_onglet_frame_est_ABSENT_puis_present_jamais_grise(qtbot):
    atelier = _atelier(qtbot)
    document = lecture.depuis_json(fab.deux_pages_cible_seconde())
    atelier.poser_document(document, document.page_par_adresse(*fab.ADRESSE_CIBLE))
    assert barre_de_vue.ONGLET_FRAME not in atelier.onglets.cles
    # Absent, et non present-et-grise : le critere est la REVERSIBILITE.
    assert atelier.onglets.count() == 2
    with pytest.raises(KeyError):
        atelier.onglets.activer(barre_de_vue.ONGLET_FRAME)

    rang, index = fab.ADRESSE_CIBLE
    atelier.ouvrir_la_frame((rang, index, 1))
    assert barre_de_vue.ONGLET_FRAME in atelier.onglets.cles
    assert atelier.onglets.vue_courante() == barre_de_vue.ONGLET_FRAME
    indice = atelier.onglets.cles.index(barre_de_vue.ONGLET_FRAME)
    assert atelier.onglets.isTabEnabled(indice)


def test_un_controle_indisponible_est_GRISE_et_present(qtbot):
    """L'autre moitie d'``EPIC7-ARB-24``, et elle n'est pas la meme."""
    barre = barre_de_vue.BarreDeVue(catalogue.CHAINES)
    qtbot.addWidget(barre)
    bouton = barre.boutons[barre_de_vue.CONTROLE_TAILLE_REELLE]
    barre.griser(barre_de_vue.CONTROLE_TAILLE_REELLE)
    assert not bouton.isEnabled()
    assert bouton.parent() is barre        # present, jamais retire
    assert bouton in barre.controles.values()
    barre.griser(barre_de_vue.CONTROLE_TAILLE_REELLE, False)
    assert bouton.isEnabled()


def test_l_onglet_lecteur_n_existe_pas_dans_cette_story(qtbot):
    """Le lecteur est 7.6. Un onglet sans objet est absent, pas grise."""
    atelier = _atelier(qtbot)
    document = lecture.depuis_json(fab.deux_pages_cible_seconde())
    atelier.poser_document(document)
    rang, index = fab.ADRESSE_CIBLE
    atelier.ouvrir_la_frame((rang, index, 0))
    assert "lecteur" not in atelier.onglets.cles
    assert set(atelier.onglets.cles) <= set(barre_de_vue.ONGLETS_DE_VUE)
    assert "lecteur" not in barre_de_vue.ONGLETS_DE_VUE
    # Et aucune chaine de catalogue de cette story ne nomme un onglet lecteur.
    assert "scan-onglet-lecteur" not in catalogue.CHAINES


def test_changer_de_lot_referme_la_vue_vignette_unique(qtbot):
    """Son objet a disparu : son onglet aussi -- absent, jamais grise."""
    atelier = _atelier(qtbot)
    document = lecture.depuis_json(fab.deux_pages_cible_seconde())
    atelier.poser_document(document)
    rang, index = fab.ADRESSE_CIBLE
    atelier.ouvrir_la_frame((rang, index, 1))
    assert barre_de_vue.ONGLET_FRAME in atelier.onglets.cles
    atelier.poser_document(lecture.depuis_json(fab.deux_pages_cible_seconde()))
    assert barre_de_vue.ONGLET_FRAME not in atelier.onglets.cles
    assert atelier.vue_frame.adresse is None
