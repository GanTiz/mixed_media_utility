# -*- coding: utf-8 -*-
"""Story 7.2, AC 5 -- les deux familles de signes, qui ne se confondent jamais.

`DESIGN.md`, correction du 2026-08-23 :

* **completude** d'un lot -> `badge-state` (« que manque-t-il dans ce lot ? »),
  disque plein / anneau creux / disque hachure ;
* **rattachement** d'un objet -> `state-glyph` (« que dois-je faire de cet
  objet ? »), delie / non rattache / incomplet, un geste par glyphe
  (`EPIC7-ARB-5`, cas d'usage `EPIC7-ARB-12`).

« Fondre les deux familles dans un seul signe » est un *Don't* : les deux
sont ici des controles distincts, dans deux colonnes distinctes.
"""

import pytest

import fabriques_chutier as fab
from mixed_media_utility.gui import catalogue, jetons
from mixed_media_utility.gui import chutier as module_chutier
from mixed_media_utility.gui import modele_chutier as modele
from mixed_media_utility.gui.coquille import Coquille


@pytest.fixture
def coquille(qtbot):
    fenetre = Coquille()
    qtbot.addWidget(fenetre)
    fenetre.show()
    qtbot.waitExposed(fenetre)
    fenetre.resize(jetons.ESPACEMENTS["queue-overlay-threshold"], 800)
    qtbot.wait(20)
    return fenetre


# ---------------------------------------------------------------------------
# Le rush delinke : couleur de TEXTE + glyphe, jamais un badge.
# ---------------------------------------------------------------------------


def test_le_rush_delinke_en_seconde_position_porte_la_couleur_et_le_glyphe(
    qtbot, coquille
):
    # Fixture aux chemins morts : seul `medias/alpha.mov` existe, donc c'est
    # le SECOND rush qui est delie -- la cible n'est pas en premiere position.
    coquille.poser_projet(
        fab.manifest_deux_rushes_deux_lots_chacun(),
        existe=fab.liaison_factice(["medias/alpha.mov"]),
    )
    qtbot.wait(10)
    arbre = coquille.chutier.arbre

    delie = arbre.element("rush-beta")
    lie = arbre.element("rush-alpha")

    # La couleur est la VARIANTE DE TEXTE, jamais la chromie pleine.
    assert delie.foreground(module_chutier.COLONNE_LIBELLE).color().name().upper() == (
        jetons.COULEURS["state-absent-text"].upper()
    )
    assert lie.foreground(module_chutier.COLONNE_LIBELLE).color().name().upper() == (
        jetons.COULEURS["text-primary"].upper()
    )

    # Le glyphe DOUBLE la couleur : elle ne porte jamais seule.
    glyphe = arbre.itemWidget(delie, module_chutier.COLONNE_GLYPHE)
    assert isinstance(glyphe, module_chutier.GlypheDeRattachement)
    assert glyphe.text() == "⊘"
    assert glyphe.etat == modele.GLYPHE_DELIE
    # Nominativement : l'autre rush n'en porte pas.
    assert arbre.itemWidget(lie, module_chutier.COLONNE_GLYPHE) is None


def test_le_rush_delinke_ne_porte_aucun_badge_ni_mention_d_origine(qtbot, coquille):
    # « Pas de badge, le code couleur suffit » : le rush delie n'a AUCUN
    # badge textuel et aucune mention d'origine dans sa ligne.
    coquille.poser_projet(
        fab.manifest_deux_rushes_deux_lots_chacun(),
        existe=fab.liaison_factice(["medias/alpha.mov"]),
    )
    qtbot.wait(10)
    arbre = coquille.chutier.arbre
    delie = arbre.element("rush-beta")
    assert arbre.itemWidget(delie, module_chutier.COLONNE_BADGE) is None
    assert delie.text(module_chutier.COLONNE_LIBELLE) == "rush-beta"


def test_le_rush_delinke_est_peint_ainsi_dans_tous_les_chutiers(qtbot, coquille):
    # « Le rush est peint ainsi dans TOUS les chutiers ou il apparait » : le
    # panneau d'arborescence le peint aussi, bien qu'il ne porte pas de signe.
    coquille.poser_projet(
        fab.manifest_deux_rushes_deux_lots_chacun(),
        existe=fab.liaison_factice(["medias/alpha.mov"]),
    )
    qtbot.wait(10)
    element = coquille.arbre_arborescence.element("rush-beta")
    assert element.foreground(
        module_chutier.COLONNE_LIBELLE
    ).color().name().upper() == jetons.COULEURS["state-absent-text"].upper()


def test_le_scan_non_identifie_porte_le_glyphe_non_rattache(qtbot, coquille):
    # Deuxieme glyphe de la famille : l'objet existe, on ignore de quelle
    # planche il s'agit -- il faut l'IDENTIFIER. Cible en seconde position.
    document = fab.document_de_detection(
        lot_id="lot-cadence-24",
        pages=[
            fab.page_detectee(0, 0, lot_id="lot-cadence-24", largeur_px=110),
            fab.page_detectee(
                1,
                None,
                lot_id="lot-cadence-24",
                status="unidentified",
                qr_status="unreadable",
                largeur_px=175,
            ),
        ],
        pages_expected=2,
    )
    coquille.poser_projet(
        fab.manifest_deux_lots_meme_rush(),
        documents_de_detection=[document],
        existe=fab.liaison_factice(["medias/alpha.mov"]),
    )
    coquille.designer("lot-cadence-24")
    qtbot.wait(10)
    arbre = coquille.chutier.arbre
    non_rattaches = [
        identifiant
        for identifiant in arbre.tous_les_identifiants()
        if isinstance(
            arbre.itemWidget(arbre.element(identifiant), module_chutier.COLONNE_GLYPHE),
            module_chutier.GlypheDeRattachement,
        )
        and arbre.itemWidget(
            arbre.element(identifiant), module_chutier.COLONNE_GLYPHE
        ).etat
        == modele.GLYPHE_NON_RATTACHE
    ]
    assert len(non_rattaches) == 1
    glyphe = arbre.itemWidget(
        arbre.element(non_rattaches[0]), module_chutier.COLONNE_GLYPHE
    )
    assert glyphe.text() == "?"
    assert glyphe.couleur == jetons.COULEURS["text-secondary"]


# ---------------------------------------------------------------------------
# Un badge ET un glyphe sur le meme lot : deux controles DISTINCTS.
# ---------------------------------------------------------------------------


def test_un_lot_incomplet_porte_un_badge_ET_un_glyphe_dans_deux_controles(
    qtbot, coquille
):
    coquille.poser_projet(
        fab.manifest_deux_lots_meme_rush(),
        existe=fab.liaison_factice(["medias/alpha.mov"]),
    )
    coquille.designer("rush-alpha")
    qtbot.wait(10)
    arbre = coquille.chutier.arbre

    # Cible en SECONDE position : le lot a 18/1, incomplet.
    incomplet = arbre.element("lot-cadence-18")
    badge = arbre.itemWidget(incomplet, module_chutier.COLONNE_BADGE)
    glyphe = arbre.itemWidget(incomplet, module_chutier.COLONNE_GLYPHE)

    assert isinstance(badge, module_chutier.BadgeDeCompletude)
    assert isinstance(glyphe, module_chutier.GlypheDeRattachement)
    # DEUX controles, dans deux colonnes : jamais un signe fusionne.
    assert badge is not glyphe
    assert type(badge) is not type(glyphe)
    assert module_chutier.COLONNE_BADGE != module_chutier.COLONNE_GLYPHE
    assert badge.etat == modele.BADGE_INCOMPLET
    assert glyphe.etat == modele.GLYPHE_INCOMPLET
    assert glyphe.text() == "⚠"

    # Le lot complet, lui, porte un badge et AUCUN glyphe.
    complet = arbre.element("lot-cadence-24")
    assert isinstance(
        arbre.itemWidget(complet, module_chutier.COLONNE_BADGE),
        module_chutier.BadgeDeCompletude,
    )
    assert arbre.itemWidget(complet, module_chutier.COLONNE_GLYPHE) is None


def test_complet_avec_mires_n_est_jamais_peint_comme_complet(qtbot, coquille):
    manifest = fab.manifest_deux_lots_meme_rush()
    manifest["lots"][1]["reconstructed_frame_count"] = 9
    manifest["lots"][1]["synthetic_frame_count"] = 2
    coquille.poser_projet(
        manifest, existe=fab.liaison_factice(["medias/alpha.mov"])
    )
    coquille.designer("rush-alpha")
    qtbot.wait(10)
    arbre = coquille.chutier.arbre
    mires = arbre.itemWidget(
        arbre.element("lot-cadence-18"), module_chutier.COLONNE_BADGE
    )
    complet = arbre.itemWidget(
        arbre.element("lot-cadence-24"), module_chutier.COLONNE_BADGE
    )
    assert mires.etat == modele.BADGE_COMPLET_AVEC_MIRES
    assert complet.etat == modele.BADGE_COMPLET
    # Trois choses les separent : la couleur, la forme, le libelle.
    assert mires.couleur_texte != complet.couleur_texte
    assert mires.forme != complet.forme
    assert mires.text() != complet.text()


# ---------------------------------------------------------------------------
# (J) Les couleurs sont LUES du module de jetons et valent celles de DESIGN.md.
# ---------------------------------------------------------------------------


def test_les_trois_glyphes_prennent_les_couleurs_de_design(qtbot, coquille):
    attendu = {
        modele.GLYPHE_DELIE: "state-absent-text",
        modele.GLYPHE_NON_RATTACHE: "text-secondary",
        modele.GLYPHE_INCOMPLET: "state-substitute-text",
    }
    assert module_chutier.JETON_COULEUR_GLYPHE == attendu
    assert set(attendu) == set(modele.GLYPHES_DE_RATTACHEMENT)
    for etat, jeton in attendu.items():
        glyphe = module_chutier.GlypheDeRattachement(etat, catalogue.CHAINES)
        assert glyphe.couleur == jetons.COULEURS[jeton]
        # Aucune chromie PLEINE en texte : le jeton porte est soit une
        # variante `-text`, soit un neutre.
        assert jeton in jetons.VARIANTES_TEXTE or jeton in jetons.NEUTRES
        assert jeton not in jetons.SEMANTIQUES
        # La bulle dit le GESTE, lue du catalogue.
        assert glyphe.toolTip() == catalogue.CHAINES[f"glyphe-{etat}"]


def test_les_trois_badges_prennent_les_couleurs_et_les_formes_de_design(coquille):
    attendu = {
        modele.BADGE_COMPLET: ("state-complete", "disque-plein"),
        modele.BADGE_COMPLET_AVEC_MIRES: ("state-substitute", "disque-hachure"),
        modele.BADGE_INCOMPLET: ("state-absent", "anneau-creux"),
    }
    assert set(attendu) == set(modele.BADGES_DE_COMPLETUDE)
    surface = jetons.COULEURS["surface-panel"]
    formes = set()
    for etat, (chromie, forme) in attendu.items():
        badge = module_chutier.BadgeDeCompletude(etat, catalogue.CHAINES, surface)
        # Le TEXTE prend la variante `-text` (plancher 4,5:1 en 11 px).
        assert badge.couleur_texte == jetons.COULEURS[f"{chromie}-text"]
        # Le FOND est la chromie pleine a 16 %, COMPOSEE sur la surface.
        assert badge.couleur_fond == jetons.composer_sur(
            jetons.COULEURS[chromie], surface
        )
        assert badge.couleur_fond != jetons.COULEURS[chromie]
        assert badge.forme == forme
        formes.add(forme)
    # Redondance non chromatique : trois formes DISTINCTES.
    assert len(formes) == 3


def test_le_glyphe_incomplet_est_rendu_plus_grand_que_les_deux_autres(coquille):
    # `DESIGN.md` : 14 px, sauf U+26A0 dont l'oeil est plus petit -> 15 px.
    assert (
        jetons.ICONOGRAPHIE["glyphe-incomplet-px"] > jetons.ICONOGRAPHIE["glyphe-px"]
    )
    grand = module_chutier.GlypheDeRattachement(
        modele.GLYPHE_INCOMPLET, catalogue.CHAINES
    )
    petit = module_chutier.GlypheDeRattachement(modele.GLYPHE_DELIE, catalogue.CHAINES)
    assert f"{jetons.ICONOGRAPHIE['glyphe-incomplet-px']}px" in grand.styleSheet()
    assert f"{jetons.ICONOGRAPHIE['glyphe-px']}px" in petit.styleSheet()


# ---------------------------------------------------------------------------
# Pictogrammes provisoires : la boite est fixee des maintenant.
# ---------------------------------------------------------------------------


def test_les_pictogrammes_tiennent_dans_la_boite_fixee(coquille):
    from PySide6.QtGui import QColor

    cote = jetons.ICONOGRAPHIE["boite-px"]
    tailles = set()
    for type_de_noeud in modele.TYPES_DE_NOEUD:
        icone = module_chutier.pictogramme(
            type_de_noeud, QColor(jetons.COULEURS["text-primary"])
        )
        assert not icone.isNull(), type_de_noeud
        tailles.add((icone.availableSizes()[0].width(), icone.availableSizes()[0].height()))
    assert tailles == {(cote, cote)}
    # Un type inconnu ne rend AUCUNE icone plutot qu'une icone par defaut qui
    # mentirait sur le niveau (symetrique du test ci-dessus).
    assert module_chutier.pictogramme("type-invente", QColor()).isNull()


# ---------------------------------------------------------------------------
# Frontiere : aucun badge d'origine ni de deduction (`EPIC7-ARB-14`).
# ---------------------------------------------------------------------------


#: Les mots qu'un badge de deduction porterait -- « pas un nouveau badge de
#: deduction » : un ancetre reconstruit depuis un scan peuple l'arbre comme
#: les autres.
_MOTS_DE_DEDUCTION = ("déduit", "deduit", "déduction", "deduction", "reconstruit")


def test_aucun_badge_ne_porte_une_origine_ni_une_deduction():
    # Le vocabulaire des badges est EXACTEMENT les trois etats de
    # completude : aucun quatrieme badge n'existe pour dire d'ou vient un
    # objet.
    assert set(module_chutier.JETON_CHROMIE_BADGE) == set(modele.BADGES_DE_COMPLETUDE)
    assert set(module_chutier.FORME_BADGE) == set(modele.BADGES_DE_COMPLETUDE)
    for etat in modele.BADGES_DE_COMPLETUDE:
        libelle = catalogue.CHAINES[f"badge-{etat}"].lower()
        for mot in _MOTS_DE_DEDUCTION:
            assert mot not in libelle, f"badge d'origine : {etat} / {mot}"


def test_la_frontiere_du_badge_de_deduction_mord_vraiment():
    # Symetrique : le motif attraperait bien un libelle fautif.
    fautif = "Reconstruit depuis un scan".lower()
    assert any(mot in fautif for mot in _MOTS_DE_DEDUCTION)


def test_un_lot_venu_du_seul_scan_ne_porte_pas_de_badge_supplementaire(
    qtbot, coquille
):
    # `EPIC7-ARB-14` mesure sur l'arbre de widgets : la branche reconstruite
    # depuis un scan seul porte sa completude ordinaire, et **un seul** badge.
    orphelin = fab.document_de_detection(
        lot_id="lot-venu-du-scan",
        rush_id="rush-gamma",
        pages=[
            fab.page_detectee(0, 0, lot_id="lot-venu-du-scan", rush_id="rush-gamma"),
            fab.page_detectee(
                1, 1, lot_id="lot-venu-du-scan", rush_id="rush-gamma", largeur_px=185
            ),
        ],
        pages_expected=2,
        empreinte=fab.EMPREINTES[2],
    )
    coquille.poser_projet(
        fab.manifest_deux_lots_meme_rush(),
        documents_de_detection=[orphelin],
        existe=fab.liaison_factice(["medias/alpha.mov"]),
    )
    coquille.designer("rush-gamma")
    qtbot.wait(10)
    arbre = coquille.chutier.arbre
    element = arbre.element("lot-venu-du-scan")
    badge = arbre.itemWidget(element, module_chutier.COLONNE_BADGE)
    assert badge.etat == modele.BADGE_COMPLET
    # Aucune troisieme colonne de signe : l'arbre en a exactement trois.
    assert arbre.columnCount() == module_chutier.NOMBRE_DE_COLONNES
    assert module_chutier.NOMBRE_DE_COLONNES == 3
