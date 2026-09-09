# -*- coding: utf-8 -*-
"""Story 7.4, AC 2 -- deux verrous independants, chacun son indicateur.

Le QR donne l'**identite** (quel lot, quelle page), les ArUco donnent la
**geometrie** (ou). Chacun a son indicateur propre, chacun trois etats, et
**aucun ne se derive de l'autre ni de la presence des zones**.
"""

import pytest

import fabriques_detection as fab
from mixed_media_utility import layout, qr_codes, scan_detection
from mixed_media_utility.gui import scan_jugement, catalogue
from mixed_media_utility.gui import lecture_detection as lecture

# ---------------------------------------------------------------------------
# Les quatre combinaisons, batites sur la forme REELLE du document
# ---------------------------------------------------------------------------

MOTIF_GEOMETRIE = "Marqueurs ArUco de coin manquants : [0, 1, 2, 3]."
MOTIF_SANS_IDENTITE = "QR inexploitable (no_symbol_detected)."
MOTIF_PERIMEE = "Planche perimee : le lot a ete recompose depuis."


def cas_1(rang, index):
    """QR livre / geometrie resolue -- la page nominale."""
    return fab.page(rang, index)


def cas_2(rang, index):
    """Refus APRES decodage : identite lisible, geometrie non resolue."""
    return fab.page(
        rang, index,
        status=scan_detection.PAGE_REFUSED,
        qr_status=qr_codes.DECODE_OK,
        refusal_reason=MOTIF_GEOMETRIE,
        identite=True, homographie=False, coins=False, zones=[],
    )


def cas_3(rang, index):
    """QR non decode, geometrie resolue par le manifeste, AUCUNE zone.

    « Quand le QR n'est pas decode, les zones d'image ne sont pas
    proposees. » La page reste `ok` : c'est le gabarit du manifeste qui a
    permis de resoudre la geometrie (`template_source` = `manifest`).
    """
    return fab.page(
        rang, index,
        status=scan_detection.PAGE_OK,
        qr_status=qr_codes.DECODE_NO_SYMBOL,
        template_source="manifest",
        identite=False, homographie=True, coins=True, zones=[],
    )


def cas_4(rang, index):
    """Refus sans identite lisible : les deux verrous rompus."""
    return fab.page(
        rang, index,
        status=scan_detection.PAGE_REFUSED,
        qr_status=qr_codes.DECODE_NO_SYMBOL,
        refusal_reason=MOTIF_SANS_IDENTITE,
        identite=False, homographie=False, coins=False, zones=[],
    )


def cas_5_planche_perimee(rang, index):
    """La planche PERIMEE : QR parfaitement lu, identite lisible, refus.

    Bloquant B1 de la revue de 5.17 : elle sort avec `qr_status` = `decoded`,
    une identite lisible **et** `status` = `refused`.
    """
    return fab.page(
        rang, index,
        status=scan_detection.PAGE_REFUSED,
        qr_status=qr_codes.DECODE_OK,
        refusal_reason=MOTIF_PERIMEE,
        identite=True, homographie=False, coins=False, zones=[],
    )


#: Les quatre cas et les DEUX etats attendus de chacun, assertes SEPAREMENT.
#: Aucun cas ne se contente d'assert que « quelque chose est rouge ».
#:
#: **Le cas 2 rend `indetermine` sur l'identite, et non `tenu`.** Ce n'est pas
#: une tolerance : c'est force par la fiche elle-meme, qui ecrit qu'une
#: planche perimee sort « sans qu'aucun champ ferme ne distingue ce refus
#: d'un refus de geometrie ». Le cas 2 et le cas 5 sont donc, au 2026-08-25,
#: LE MEME etat de champs fermes ; les separer demanderait de brancher sur la
#: phrase francaise (interdit par `EPIC7-ARB-66`) ou de deriver l'identite de
#: l'homographie (interdit par le test d'anti-derivation croisee ci-dessous).
#: C'est exactement le trou que le code de refus enumere de la story de coeur
#: **5.27** comblera -- non livree, la vague 2 bis ayant ete ecartee.
ETATS_ATTENDUS = {
    "cas_1": (lecture.VERROU_TENU, lecture.VERROU_TENU),
    "cas_2": (lecture.VERROU_INDETERMINE, lecture.VERROU_ROMPU),
    "cas_3": (lecture.VERROU_ROMPU, lecture.VERROU_TENU),
    "cas_4": (lecture.VERROU_ROMPU, lecture.VERROU_ROMPU),
}

FABRIQUES = {"cas_1": cas_1, "cas_2": cas_2, "cas_3": cas_3, "cas_4": cas_4}

#: Les quatre cas dans UN SEUL document de quatre pages, avec des adresses
#: DESALIGNEES et la page visee jamais la premiere -- un lecteur qui rendrait
#: toujours la premiere page ne se demasque pas autrement.
ADRESSES = {
    "cas_1": (1, 4),
    "cas_2": (2, 2),
    "cas_3": (3, None),
    "cas_4": (4, 1),
}


def document_des_quatre_cas():
    pages = [
        FABRIQUES[nom](*ADRESSES[nom])
        for nom in ("cas_1", "cas_2", "cas_3", "cas_4")
    ]
    return lecture.depuis_json(fab.document(pages))


def _bandeau(qtbot, page):
    bandeau = scan_jugement.BandeauDeVerrous(catalogue.CHAINES)
    qtbot.addWidget(bandeau)
    bandeau.poser(page)
    return bandeau


@pytest.mark.parametrize("nom", sorted(ETATS_ATTENDUS))
def test_les_quatre_combinaisons_assertent_les_deux_indicateurs_separement(
    qtbot, nom
):
    document = document_des_quatre_cas()
    page = document.page_par_adresse(*ADRESSES[nom])
    identite_attendue, geometrie_attendue = ETATS_ATTENDUS[nom]
    assert lecture.etat_verrou_identite(page) == identite_attendue
    assert lecture.etat_verrou_geometrie(page) == geometrie_attendue
    bandeau = _bandeau(qtbot, page)
    assert bandeau.identite.etat == identite_attendue
    assert bandeau.geometrie.etat == geometrie_attendue


def test_les_deux_indicateurs_sont_deux_controles_distincts(qtbot):
    """« Fondre les deux familles dans un seul signe » est un Don't."""
    document = document_des_quatre_cas()
    bandeau = _bandeau(qtbot, document.page_par_adresse(*ADRESSES["cas_3"]))
    assert bandeau.identite is not bandeau.geometrie
    assert bandeau.identite.objectName() != bandeau.geometrie.objectName()
    assert bandeau.identite.libelle.text() != bandeau.geometrie.libelle.text()
    # Deux etats DIFFERENTS sur la meme page : la preuve qu'aucun signe
    # unique ne peut les porter.
    assert bandeau.identite.etat != bandeau.geometrie.etat


def test_les_quatre_cas_coexistent_et_la_page_visee_n_est_jamais_la_premiere():
    document = document_des_quatre_cas()
    assert len(document.pages) == 4
    for nom, adresse in ADRESSES.items():
        page = document.page_par_adresse(*adresse)
        assert page.adresse == adresse
        if nom != "cas_1":
            assert document.pages[0].adresse != adresse
    # Rangs de lecture et index de page DESALIGNES sur trois pages sur quatre.
    desalignees = [
        page for page in document.pages
        if page.page.page_index is not None
        and page.page.page_index != page.page.read_rank
    ]
    assert len(desalignees) >= 2


def test_la_planche_perimee_rend_indetermine_et_le_motif_verbatim(qtbot):
    """Le cinquieme cas, et la raison d'etre du troisieme etat.

    Un vert serait faux, un rouge le serait aussi, et parser la phrase serait
    pire que les deux.
    """
    document = lecture.depuis_json(
        fab.document([
            cas_1(1, 4),
            cas_5_planche_perimee(2, 2),   # la cible, en SECONDE position
        ])
    )
    page = document.page_par_adresse(2, 2)
    assert page.page.qr_status == qr_codes.DECODE_OK
    assert page.page.decoded_lot_id is not None
    assert page.page.status == scan_detection.PAGE_REFUSED
    assert lecture.etat_verrou_identite(page) == lecture.VERROU_INDETERMINE

    vue = scan_jugement.VueModePdf(catalogue.CHAINES)
    qtbot.addWidget(vue)
    vue.poser(page)
    assert vue.verrous.identite.etat == lecture.VERROU_INDETERMINE
    assert vue.etat_de_page.refus.text().endswith(MOTIF_PERIMEE)


def test_le_troisieme_etat_de_geometrie_existe_sur_une_description_partielle(
    qtbot,
):
    """Une geometrie decrite a moitie ne se tranche pas au hasard.

    Le producteur d'aujourd'hui n'en emet pas -- `MIN_CORNER_MARKERS_REQUIRED`
    vaut quatre, c'est tout ou rien --, mais la GUI lit des documents qu'elle
    n'ecrit pas, et de versions qu'elle ne choisit pas. Ce test fige la
    lecture DEFENSIVE, jamais un etat affiche a partir de rien.
    """
    rang, index = fab.ADRESSE_CIBLE
    brut = fab.deux_pages_cible_seconde()
    brut["pages"][1]["corner_markers"] = [
        fab.marqueur_de_coin(identifiant, rang, index)
        for identifiant in layout.CORNER_MARKER_IDS
        if identifiant != 2
    ]
    page = lecture.depuis_json(brut).page_par_adresse(rang, index)
    assert lecture.etat_verrou_geometrie(page) == lecture.VERROU_INDETERMINE
    bandeau = _bandeau(qtbot, page)
    assert bandeau.geometrie.etat == lecture.VERROU_INDETERMINE
    # Les trois etats sont bien trois : aucun n'est un alias d'un autre.
    assert len(set(lecture.ETATS_DE_VERROU)) == 3


# ---------------------------------------------------------------------------
# Anti-fusion : aucun indicateur ne se calcule a partir de `frame_zones`
# ---------------------------------------------------------------------------


def test_vider_ou_remplir_frame_zones_ne_deplace_aucun_indicateur(qtbot):
    """La presence de zones est une CONSEQUENCE des deux verrous, jamais leur
    source. Un indicateur derive des zones echoue ces deux assertions."""
    # Cas 3 : deja sans zone -- on lui en AJOUTE.
    rang_3, index_3 = ADRESSES["cas_3"]
    sans_zone = cas_3(rang_3, index_3)
    avec_zone = cas_3(rang_3, index_3)
    avec_zone["frame_zones"] = fab.deux_zones(rang_3, index_3)
    etats = []
    for gabarit in (sans_zone, avec_zone):
        page = lecture.depuis_json(
            fab.document([cas_1(1, 4), gabarit])
        ).page_par_adresse(rang_3, index_3)
        etats.append(
            (lecture.etat_verrou_identite(page), lecture.etat_verrou_geometrie(page))
        )
    assert etats[0] == etats[1] == ETATS_ATTENDUS["cas_3"]

    # Cas 2 : on lui remplit ARTIFICIELLEMENT ses zones.
    rang_2, index_2 = ADRESSES["cas_2"]
    vide = cas_2(rang_2, index_2)
    rempli = cas_2(rang_2, index_2)
    rempli["frame_zones"] = fab.deux_zones(rang_2, index_2)
    etats = []
    for gabarit in (vide, rempli):
        page = lecture.depuis_json(
            fab.document([cas_1(1, 4), gabarit])
        ).page_par_adresse(rang_2, index_2)
        etats.append(
            (lecture.etat_verrou_identite(page), lecture.etat_verrou_geometrie(page))
        )
    assert etats[0] == etats[1] == ETATS_ATTENDUS["cas_2"]


# ---------------------------------------------------------------------------
# Anti-derivation croisee : chaque champ ne deplace QUE son verrou
# ---------------------------------------------------------------------------


def test_modifier_qr_status_seul_deplace_l_identite_et_elle_seule():
    rang, index = ADRESSES["cas_2"]
    avant = lecture.depuis_json(
        fab.document([cas_1(1, 4), cas_2(rang, index)])
    ).page_par_adresse(rang, index)
    apres_gabarit = cas_2(rang, index)
    apres_gabarit["qr_status"] = qr_codes.DECODE_UNREADABLE
    apres = lecture.depuis_json(
        fab.document([cas_1(1, 4), apres_gabarit])
    ).page_par_adresse(rang, index)
    assert lecture.etat_verrou_identite(avant) != lecture.etat_verrou_identite(apres)
    assert lecture.etat_verrou_geometrie(avant) == lecture.etat_verrou_geometrie(apres)


def test_modifier_l_homographie_seule_deplace_la_geometrie_et_elle_seule():
    rang, index = ADRESSES["cas_3"]
    avant = lecture.depuis_json(
        fab.document([cas_1(1, 4), cas_3(rang, index)])
    ).page_par_adresse(rang, index)
    apres_gabarit = cas_3(rang, index)
    apres_gabarit["homography"] = None
    apres_gabarit["corner_markers"] = []
    apres = lecture.depuis_json(
        fab.document([cas_1(1, 4), apres_gabarit])
    ).page_par_adresse(rang, index)
    assert lecture.etat_verrou_geometrie(avant) != lecture.etat_verrou_geometrie(apres)
    assert lecture.etat_verrou_identite(avant) == lecture.etat_verrou_identite(apres)


# ---------------------------------------------------------------------------
# Le motif de non-proposition : le BON motif, pas l'autre
# ---------------------------------------------------------------------------


def test_sans_zone_l_ecran_dit_LEQUEL_des_deux_verrous_manque(qtbot):
    document = document_des_quatre_cas()
    # Cas 3 : QR non decode et geometrie resolue -- c'est le QR qu'il faut
    # nommer, « pas avec "geometrie non resolue" ».
    page_3 = document.page_par_adresse(*ADRESSES["cas_3"])
    assert lecture.motif_de_non_proposition(page_3) == lecture.MOTIF_IDENTITE
    bandeau = _bandeau(qtbot, page_3)
    assert bandeau.cle_de_motif == lecture.MOTIF_IDENTITE
    assert bandeau.motif.text() == catalogue.CHAINES[lecture.MOTIF_IDENTITE]
    assert bandeau.motif.text() != catalogue.CHAINES[lecture.MOTIF_GEOMETRIE]

    # Cas 1 : les deux verrous tiennent, les zones sont la -- aucun motif.
    page_1 = document.page_par_adresse(*ADRESSES["cas_1"])
    assert lecture.motif_de_non_proposition(page_1) is None


def test_le_motif_de_geometrie_n_est_rendu_que_quand_l_identite_tient(qtbot):
    """Une page identifiee dont la geometrie n'est pas resolue.

    **Reecrit par `EPIC7-ARB-75`** (revue de vague 3). La version precedente
    figeait `MOTIF_IDENTITE` sur le cas 2 en le disant elle-meme -- « ce test
    fige l'etat MESURE, pas l'etat souhaite » -- et deferait l'affinage a la
    story de coeur 5.27. **5.27 a ete abandonnee le 2026-08-25** : l'etat
    n'etait donc pas une attente mais un regime permanent, et il affichait une
    contre-verite. Le cas 2 sort desormais sous le motif NEUTRE.

    Le motif de geometrie, lui, garde son cas propre et **n'est pas du code
    mort** : il se rencontre des que l'identite tient et que la geometrie ne
    tient pas, c'est-a-dire sur une page `ok` a description geometrique
    PARTIELLE. Le producteur d'aujourd'hui n'en emet pas
    (`MIN_CORNER_MARKERS_REQUIRED` vaut quatre : tout ou rien), mais la GUI lit
    des documents qu'elle n'ecrit pas et de versions qu'elle ne choisit pas --
    c'est le cas que la seconde moitie de ce test construit.
    """
    document = document_des_quatre_cas()
    page_2 = document.page_par_adresse(*ADRESSES["cas_2"])
    assert lecture.motif_de_non_proposition(page_2) == lecture.MOTIF_REFUS_AU_SCAN
    # Le motif de geometrie, lui, se rencontre des que l'identite tient et
    # que la geometrie ne tient pas -- une page `ok` dont la description
    # geometrique est partielle.
    rang, index = fab.ADRESSE_CIBLE
    partielle = fab.page(rang, index, zones=[])
    partielle["corner_markers"] = partielle["corner_markers"][:3]
    page = lecture.depuis_json(
        fab.document([cas_1(1, 4), partielle])
    ).page_par_adresse(rang, index)
    assert lecture.etat_verrou_identite(page) == lecture.VERROU_TENU
    assert lecture.motif_de_non_proposition(page) == lecture.MOTIF_GEOMETRIE


def test_un_QR_decode_et_des_ArUco_echoues_ne_font_JAMAIS_accuser_le_QR(qtbot):
    """Le cas de terrain dominant : le QR a tout livre, les ArUco ont lache.

    C'est la mesure qui a fonde `EPIC7-ARB-75`. La page sort du coeur avec
    `qr_status = decoded` -- donc une identite parfaitement lisible, et
    `decoded_lot_id` renseigne -- et un refus dont la phrase nomme les
    marqueurs. Avant l'arbitrage, l'ecran affichait « le QR n'a pas livre
    l'identite de cette planche » : **faux**, et faux dans le sens qui coute,
    puisque c'est la seule phrase que l'operatrice lit pour decider quoi
    refaire. Elle etait envoyee verifier le mauvais element.

    Ce que le test exige, et qui n'est pas la meme chose que « la bonne
    phrase » : l'ecran ne doit **accuser aucun des deux verrous** quand le
    document ne dit pas lequel a lache. La phrase juste ne redeviendra
    atteignable que si un producteur enumere le motif de son refus -- ce que
    5.27 devait faire, et qui n'arrivera pas.
    """
    rang, index = fab.ADRESSE_CIBLE
    refusee = fab.page(rang, index, zones=[])
    refusee["qr_status"] = qr_codes.DECODE_OK
    refusee["status"] = "refused"
    refusee["refusal_reason"] = "Marqueurs ArUco de coin manquants : [0, 1, 2, 3]."
    refusee["homography"] = None
    refusee["corner_markers"] = []
    page = lecture.depuis_json(
        fab.document([cas_1(1, 4), refusee])
    ).page_par_adresse(rang, index)

    # Le document dit que le QR a livre : le verrou d'identite n'est pas rompu.
    assert lecture.etat_verrou_identite(page) == lecture.VERROU_INDETERMINE
    assert lecture.etat_verrou_geometrie(page) == lecture.VERROU_ROMPU

    motif = lecture.motif_de_non_proposition(page)
    assert motif == lecture.MOTIF_REFUS_AU_SCAN
    # Les deux accusations nommees sont exclues, chacune pour sa raison : le QR
    # a livre, et rien dans le document ne prouve que c'est la geometrie qui a
    # motive le refus.
    assert motif != lecture.MOTIF_IDENTITE
    assert motif != lecture.MOTIF_GEOMETRIE

    # Et ce que l'oeil lit ne nomme aucun des deux.
    bandeau = _bandeau(qtbot, page)
    phrase = bandeau.motif.text()
    assert phrase == catalogue.CHAINES[lecture.MOTIF_REFUS_AU_SCAN]
    assert "QR" not in phrase
    assert "géométrie" not in phrase.lower()
