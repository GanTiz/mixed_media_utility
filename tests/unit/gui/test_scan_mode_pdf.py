# -*- coding: utf-8 -*-
"""Story 7.4, AC 1 et AC 3 -- le mode PDF.

Ce que ce banc mesure : les surimpressions sont **integralement lues** du
document, aucune position n'est fabriquee, l'etat de page est rendu verbatim,
et les valeurs par zone sortent des bons champs et au bon endroit.
"""

import json
from pathlib import Path

import pytest
from PySide6.QtWidgets import QLabel

import fabriques_detection as fab
from mixed_media_utility import layout, qr_codes, scan_detection
from mixed_media_utility.gui import scan_jugement, catalogue
from mixed_media_utility.gui import lecture_detection as lecture
from mixed_media_utility.gui import surimpressions

_DOCUMENT_REEL = (
    Path(__file__).resolve().parents[2]
    / "fixtures" / "detection-scan-reelle" / "detect-ok-et-refus.json"
)


def _vue(qtbot, chaines=None):
    vue = scan_jugement.VueModePdf(chaines or catalogue.CHAINES)
    qtbot.addWidget(vue)
    vue.resize(1200, 800)
    vue.show()
    return vue


def _page_refusee(**surcharges):
    """Une page refusee telle que le coeur en ecrit : rien de geometrique."""
    defauts = dict(
        status=scan_detection.PAGE_REFUSED,
        qr_status=qr_codes.DECODE_NO_SYMBOL,
        identite=False,
        homographie=False,
        coins=False,
        zones=[],
    )
    defauts.update(surcharges)
    return defauts


# ---------------------------------------------------------------------------
# AC 1 -- les zones proposees, nominativement, et celles de l'autre page jamais
# ---------------------------------------------------------------------------


def test_la_vue_rend_les_zones_de_cette_page_et_aucune_de_l_autre(qtbot):
    document = lecture.depuis_json(fab.deux_pages_cible_seconde())
    cible = document.page_par_adresse(*fab.ADRESSE_CIBLE)
    leurre = document.page_par_adresse(*fab.ADRESSE_LEURRE)
    vue = _vue(qtbot)
    vue.poser(cible)

    zones = [
        trait for trait in vue.plan_de_surimpressions
        if trait.famille == surimpressions.FAMILLE_ZONE
    ]
    # Nominativement : chaque rectangle est EXACTEMENT celui du document.
    assert [(trait.identifiant, trait.rectangle_px) for trait in zones] == [
        (zone.slot_index,
         (zone.crop_x_px, zone.crop_y_px, zone.crop_w_px, zone.crop_h_px))
        for zone in cible.page.frame_zones
    ]
    # Et aucun de l'autre page : les deux jeux sont disjoints par
    # construction (emplacements 0-1 contre 2-3, tailles differentes).
    rectangles_du_leurre = {
        (zone.crop_x_px, zone.crop_y_px, zone.crop_w_px, zone.crop_h_px)
        for zone in leurre.page.frame_zones
    }
    assert rectangles_du_leurre.isdisjoint(
        {trait.rectangle_px for trait in zones}
    )
    assert len(zones) == 2, "une fabrique mono-zone ne mesurerait rien"
    # Et le rectangle vient des `crop_*_px`, **jamais** des `zone_*_px` :
    # les deux conventions de quantification du coeur divergent d'un pixel
    # (mesure par 5.2), et la fabrique les fait donc diverger aussi. Sans
    # cette divergence, lire le mauvais champ resterait invisible -- mutant
    # mesure le 2026-08-25.
    for trait, zone in zip(zones, cible.page.frame_zones):
        assert (zone.crop_x_px, zone.crop_w_px) != (zone.zone_x_px, zone.zone_w_px)
        assert trait.rectangle_px[0] == zone.crop_x_px
        assert trait.rectangle_px[2] == zone.crop_w_px
        assert trait.rectangle_px[0] != zone.zone_x_px


def test_les_quatre_marqueurs_sont_rendus_a_leurs_quatre_centres_lus(qtbot):
    document = lecture.depuis_json(fab.deux_pages_cible_seconde())
    cible = document.page_par_adresse(*fab.ADRESSE_CIBLE)
    vue = _vue(qtbot)
    vue.poser(cible)
    marques = {
        trait.identifiant: trait.centre_px
        for trait in vue.plan_de_surimpressions
        if trait.famille == surimpressions.FAMILLE_MARQUEUR
    }
    assert marques == dict(fab.CENTRES_DE_COIN)
    assert len(set(marques.values())) == 4, (
        "des centres uniformes rendraient toute permutation invisible"
    )


def test_permuter_deux_centres_dans_la_fixture_change_le_rendu(qtbot):
    """Le symetrique : sans lui, le test precedent pourrait etre vide.

    C'est litteralement le mutant M33 de la story 5.6 -- appariement
    positionnel inverse, 165 tests verts -- transpose ici.
    """
    brut = fab.deux_pages_cible_seconde()
    coins = brut["pages"][1]["corner_markers"]
    coins[0]["center_x_px"], coins[2]["center_x_px"] = (
        coins[2]["center_x_px"], coins[0]["center_x_px"]
    )
    coins[0]["center_y_px"], coins[2]["center_y_px"] = (
        coins[2]["center_y_px"], coins[0]["center_y_px"]
    )
    document = lecture.depuis_json(brut)
    vue = _vue(qtbot)
    vue.poser(document.page_par_adresse(*fab.ADRESSE_CIBLE))
    marques = {
        trait.identifiant: trait.centre_px
        for trait in vue.plan_de_surimpressions
        if trait.famille == surimpressions.FAMILLE_MARQUEUR
    }
    assert marques != dict(fab.CENTRES_DE_COIN)
    assert marques[0] == fab.CENTRES_DE_COIN[2]
    assert marques[2] == fab.CENTRES_DE_COIN[0]


def test_une_page_refusee_ne_dessine_rien_et_nomme_ses_quatre_manquants(qtbot):
    motif = "QR inexploitable (no_symbol_detected) et aucun manifest local."
    document = lecture.depuis_json(
        fab.deux_pages_cible_seconde(**_page_refusee(refusal_reason=motif))
    )
    page = document.page_par_adresse(*fab.ADRESSE_CIBLE)
    vue = _vue(qtbot)
    vue.poser(page)

    # ZERO marque : sans homographie il n'existe aucune position attendue,
    # et en inventer une donnerait une geometrie fausse d'apparence valide.
    assert vue.plan_de_surimpressions == ()
    # Les quatre identifiants attendus, NOMMES.
    assert page.marqueurs_manquants == tuple(layout.CORNER_MARKER_IDS)
    texte = vue.etat_de_page.marqueurs.text()
    for identifiant in layout.CORNER_MARKER_IDS:
        assert str(identifiant) in texte
    # Et le motif, CARACTERE POUR CARACTERE.
    assert motif in vue.etat_de_page.refus.text()
    assert vue.etat_de_page.refus.text().endswith(motif)


def test_les_marqueurs_etrangers_sont_listes_et_jamais_dessines(qtbot):
    # DEUX marqueurs etrangers de roles differents, la cible en seconde
    # position dans la liste : un rendu qui ne prendrait que le premier se
    # demasque.
    etrangers = [
        fab.marqueur_etranger(41, "calibration", *fab.ADRESSE_CIBLE),
        fab.marqueur_etranger(57, "reperage", *fab.ADRESSE_CIBLE),
    ]
    document = lecture.depuis_json(
        fab.deux_pages_cible_seconde(foreign_markers=etrangers)
    )
    vue = _vue(qtbot)
    vue.poser(document.page_par_adresse(*fab.ADRESSE_CIBLE))
    texte = vue.etat_de_page.etrangers.text()
    assert "41" in texte and "calibration" in texte
    assert "57" in texte and "reperage" in texte
    # AUCUNE marque dessinee pour eux : le document ne porte aucune de leurs
    # coordonnees, donc il n'existe rien a placer.
    identifiants_dessines = {
        trait.identifiant for trait in vue.plan_de_surimpressions
        if trait.famille == surimpressions.FAMILLE_MARQUEUR
    }
    assert 41 not in identifiants_dessines and 57 not in identifiants_dessines


def test_la_zone_de_qr_n_est_dessinee_que_si_le_document_en_porte_une(qtbot):
    """La troisieme famille de traits, et l'etat mesure du depot.

    Le document de detection ne porte **aucun rectangle de QR** : le coeur ne
    projette en pixels que les zones d'image. La GUI n'en fabrique donc
    jamais un -- ce serait une conversion mm -> px et une homographie, les
    deux interdits mesures de l'AC 1 et de l'AC 3. Elle sait en revanche
    l'honorer si le document en porte un, et c'est ce que ce test fige.
    """
    rang, index = fab.ADRESSE_CIBLE
    zone_qr = fab.zone(9, rang, index, largeur_px=400, hauteur_px=400)
    zone_qr["zone_name"] = surimpressions.NOM_DE_ZONE_QR
    zones = fab.deux_zones(rang, index) + [zone_qr]
    document = lecture.depuis_json(
        fab.deux_pages_cible_seconde(
            zones=zones, qr_status=qr_codes.DECODE_NO_SYMBOL
        )
    )
    vue = _vue(qtbot)
    vue.poser(document.page_par_adresse(*fab.ADRESSE_CIBLE))
    familles = [trait.famille for trait in vue.plan_de_surimpressions]
    assert surimpressions.FAMILLE_QR_NON_DECODE in familles
    trait_qr = next(
        trait for trait in vue.plan_de_surimpressions
        if trait.famille == surimpressions.FAMILLE_QR_NON_DECODE
    )
    assert trait_qr.rectangle_px == (
        zone_qr["crop_rect_px"]["x"], zone_qr["crop_rect_px"]["y"],
        zone_qr["crop_rect_px"]["width"], zone_qr["crop_rect_px"]["height"],
    )
    assert trait_qr.jeton_couleur == "state-substitute"

    # Le meme document avec un QR LU ne porte pas cet etat : le State Pattern
    # ne vise que le NON decode.
    lu = lecture.depuis_json(
        fab.deux_pages_cible_seconde(zones=zones, qr_status=qr_codes.DECODE_OK)
    )
    vue.poser(lu.page_par_adresse(*fab.ADRESSE_CIBLE))
    assert surimpressions.FAMILLE_QR_NON_DECODE not in [
        trait.famille for trait in vue.plan_de_surimpressions
    ]


def test_aucun_document_reel_ne_porte_de_rectangle_de_qr():
    """Le fait qui commande le test precedent, mesure a sa source."""
    brut = json.loads(_DOCUMENT_REEL.read_text(encoding="utf-8"))
    noms = {
        zone["zone_name"] for page in brut["pages"] for zone in page["frame_zones"]
    }
    assert noms and surimpressions.NOM_DE_ZONE_QR not in noms


# ---------------------------------------------------------------------------
# EPIC7-ARB-66 -- « incomplets » sort de la specification
# ---------------------------------------------------------------------------


def test_aucun_etat_de_marqueur_ne_dit_incomplet(qtbot):
    """Portee STRICTE : les etats de MARQUEURS, et eux seuls.

    Les badges de completude (AC 4) et les glyphes de rattachement
    (`EPIC7-ARB-5`) sont deux **autres** familles, qui gardent leur
    vocabulaire : le grep ne les balaye pas.
    """
    document = lecture.depuis_json(
        fab.deux_pages_cible_seconde(**_page_refusee(refusal_reason="Refus."))
    )
    vue = _vue(qtbot)
    vue.poser(document.page_par_adresse(*fab.ADRESSE_CIBLE))
    bandeau = vue.etat_de_page
    textes = [bandeau.marqueurs.text(), bandeau.etrangers.text()]
    textes += [
        etiquette.text()
        for etiquette in bandeau.findChildren(QLabel)
    ]
    for texte in textes:
        assert "incomplet" not in texte.lower(), (
            f"un etat de marqueur dit « incomplet » : {texte!r} -- ce voyant "
            "n'a aucun producteur au coeur (EPIC7-ARB-66)"
        )
    # Et aucune entree de catalogue DESTINEE A CETTE FAMILLE n'en contient.
    familles_de_marqueurs = {
        cle: valeur for cle, valeur in catalogue.CHAINES.items()
        if cle.startswith("scan-marqueur")
    }
    assert familles_de_marqueurs, "le grep ne balayerait rien"
    for cle, valeur in familles_de_marqueurs.items():
        assert "incomplet" not in valeur.lower(), cle


# ---------------------------------------------------------------------------
# EPIC7-ARB-66 -- le code de refus a cote de la phrase
# ---------------------------------------------------------------------------


def test_le_code_de_refus_accompagne_la_phrase(qtbot):
    """Deux pages refusees pour deux motifs DISTINCTS, la cible en SECONDE.

    **Le cas positif n'a aucun producteur au 2026-08-25** : la story de coeur
    5.27 -- celle qui doit poser les codes enumeres au seul site de refus
    (`scan_detection.py`) -- n'est pas livree, la vague 2 bis ayant ete
    ecartee. Ce cas est donc ecrit contre un document de **synthese** portant
    un champ de code, et il mesure **la LECTURE, jamais la production**. Rien
    ici ne fabrique un producteur de codes : ce serait faire 5.27 hors de son
    perimetre.
    """
    rang_leurre, index_leurre = fab.ADRESSE_LEURRE
    rang_cible, index_cible = fab.ADRESSE_CIBLE
    motif_leurre = "Marqueurs ArUco de coin manquants : [0, 1, 2, 3]."
    motif_cible = "Planche perimee : le lot a ete recompose depuis."
    code_leurre = "geometrie-marqueurs-manquants"
    code_cible = "planche-perimee"
    pages = [
        fab.page(
            rang_leurre, index_leurre,
            **_page_refusee(refusal_reason=motif_leurre, code_de_refus=code_leurre),
        ),
        fab.page(
            rang_cible, index_cible,
            **_page_refusee(refusal_reason=motif_cible, code_de_refus=code_cible),
        ),
    ]
    document = lecture.depuis_json(fab.document(pages))
    vue = _vue(qtbot)

    # La CIBLE, en seconde position : chacune rend SON code et SA phrase.
    cible = document.page_par_adresse(rang_cible, index_cible)
    vue.poser(cible)
    assert cible.code_de_refus == code_cible
    assert code_cible in vue.etat_de_page.code.text()
    assert code_leurre not in vue.etat_de_page.code.text()
    assert vue.etat_de_page.refus.text().endswith(motif_cible)
    assert vue.etat_de_page.code.isVisible() or not vue.isVisible()

    leurre = document.page_par_adresse(rang_leurre, index_leurre)
    vue.poser(leurre)
    assert code_leurre in vue.etat_de_page.code.text()
    assert vue.etat_de_page.refus.text().endswith(motif_leurre)


def test_permuter_les_deux_motifs_dans_la_fixture_fait_diverger_le_rendu(qtbot):
    """Le symetrique du test precedent : sans lui, il pourrait etre vide."""
    rang_cible, index_cible = fab.ADRESSE_CIBLE
    rang_leurre, index_leurre = fab.ADRESSE_LEURRE
    motifs = ("Motif A.", "Motif B.")
    codes = ("code-a", "code-b")

    def rendu(ordre):
        pages = [
            fab.page(rang_leurre, index_leurre, **_page_refusee(
                refusal_reason=motifs[ordre[0]], code_de_refus=codes[ordre[0]])),
            fab.page(rang_cible, index_cible, **_page_refusee(
                refusal_reason=motifs[ordre[1]], code_de_refus=codes[ordre[1]])),
        ]
        document = lecture.depuis_json(fab.document(pages))
        vue = _vue(qtbot)
        vue.poser(document.page_par_adresse(rang_cible, index_cible))
        return (vue.etat_de_page.refus.text(), vue.etat_de_page.code.text())

    assert rendu((0, 1)) != rendu((1, 0))


def test_sans_champ_de_code_la_phrase_est_rendue_SEULE(qtbot):
    """Le REPLI de l'AC 1, et c'est le regime NOMINAL du 2026-08-25.

    Ecrit contre un **vrai document produit par `scan detect`** : la story de
    coeur 5.27 n'etant pas livree, aucun document du depot ne porte de code,
    et un document ecrit avant elle n'en portera **jamais**. Le repli est
    donc permanent -- il n'y a rien a retirer plus tard.

    Ce qui est mesure : ni code vide, ni code invente, ni code derive de la
    phrase.
    """
    document = lecture.charger(_DOCUMENT_REEL)
    refusee = document.pages[1]
    assert refusee.page.status == scan_detection.PAGE_REFUSED
    assert refusee.code_de_refus is None

    vue = _vue(qtbot)
    vue.poser(refusee)
    assert vue.etat_de_page.code.text() == ""
    assert vue.etat_de_page.code.isHidden() or not vue.isVisible()
    # La phrase, elle, est bien la, entiere.
    assert vue.etat_de_page.refus.text().endswith(refusee.page.refusal_reason)
