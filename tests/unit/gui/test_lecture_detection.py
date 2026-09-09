# -*- coding: utf-8 -*-
"""Story 7.4, Task 2 (AC 1) -- lecture du document de detection cote GUI.

Ce banc mesure trois choses et rien d'autre : que le document se relit par le
coeur, que l'ACCES SE FAIT PAR ADRESSE (jamais par position), et que la GUI
n'ajoute au document ni tolerance ni valeur inventee.
"""

import json
from pathlib import Path

import pytest

import fabriques_detection as fab
from mixed_media_utility import layout, qr_codes, scan_detection
from mixed_media_utility.gui import lecture_detection as lecture

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"

#: Document REEL, ecrit par `scan detect` (story 5.25) sur deux pages : une
#: planche en payload 2.1 lue proprement, et une feuille blanche refusee. Il
#: est versionne parce qu'il porte le regime NOMINAL du 2026-08-25 -- un
#: refus **sans** code enumere, la story de coeur 5.27 n'etant pas livree.
_DOCUMENT_REEL = _FIXTURES / "detection-scan-reelle" / "detect-ok-et-refus.json"


@pytest.fixture
def document_reel():
    assert _DOCUMENT_REEL.is_file(), (
        f"document de detection reel introuvable a {_DOCUMENT_REEL} : le banc "
        "ne mesurerait plus rien contre un vrai producteur"
    )
    return lecture.charger(_DOCUMENT_REEL)


# ---------------------------------------------------------------------------
# Contre le vrai producteur
# ---------------------------------------------------------------------------


def test_un_document_ecrit_par_scan_detect_se_relit_tel_quel(document_reel):
    # Deux pages, dans l'ordre du document : la planche lue puis la feuille
    # refusee. Rien n'est re-trie localement.
    assert [page.adresse for page in document_reel.pages] == [(0, 0), (1, None)]
    lue, refusee = document_reel.pages
    assert lue.page.status == scan_detection.PAGE_OK
    assert lue.page.qr_status == qr_codes.DECODE_OK
    assert len(lue.page.frame_zones) == 4
    assert lue.marqueurs_manquants == ()
    assert refusee.page.status == scan_detection.PAGE_REFUSED
    assert refusee.page.frame_zones == ()
    assert refusee.marqueurs_manquants == tuple(layout.CORNER_MARKER_IDS)


def test_un_document_reel_ne_porte_aucun_code_de_refus(document_reel):
    """Le REPLI de l'AC 1, et il est permanent pour CE document.

    Mise a jour du 2026-08-26 : la story de coeur **5.27 est livree** (vague
    2 bis), donc `scan_detection` pose desormais un code enumere a cote de la
    phrase. Ce test ne mesure plus « le code n'existe nulle part » -- ce serait
    faux -- mais **le repli**, qui lui ne bouge pas : ce document-ci a ete
    ecrit AVANT 5.27, il n'en portera donc jamais de code, et l'ecran doit
    afficher la phrase seule sans en inventer un.

    Le document de reference n'est **pas** regenere : c'est ce qui fait de lui
    la mesure du repli. Joindre producteur et consommateur sur une donnee
    reelle POSTERIEURE a 5.27 demande une seconde fixture, versee a
    `deferred-work.md` -- l'AC 10 de 5.27 interdisait de la produire ici.
    """
    brut = json.loads(_DOCUMENT_REEL.read_text(encoding="utf-8"))
    assert all(
        lecture.CLE_CODE_DE_REFUS not in page for page in brut["pages"]
    ), "le document de reference porterait un code : il ne serait plus le repli"
    assert [page.code_de_refus for page in document_reel.pages] == [None, None]
    # La phrase, elle, est bien la -- et elle est rendue **verbatim**.
    refusee = document_reel.pages[1]
    assert refusee.page.refusal_reason == brut["pages"][1]["refusal_reason"]
    assert refusee.page.refusal_reason


# ---------------------------------------------------------------------------
# Acces par adresse -- jamais par position (mutant M25 de 5.7)
# ---------------------------------------------------------------------------


def test_la_page_est_prise_par_adresse_et_non_par_position():
    document = lecture.depuis_json(fab.deux_pages_cible_seconde())
    cible = document.page_par_adresse(*fab.ADRESSE_CIBLE)
    assert cible.adresse == fab.ADRESSE_CIBLE
    # La cible est en SECONDE position : un acces positionnel rendrait le
    # leurre, dont les emplacements sont d'un autre jeu.
    assert document.pages[0].adresse == fab.ADRESSE_LEURRE
    assert [zone.slot_index for zone in cible.page.frame_zones] == [0, 1]
    assert [
        zone.slot_index for zone in document.pages[0].page.frame_zones
    ] == [2, 3]


def test_le_rang_de_lecture_et_l_index_de_page_ne_se_deduisent_jamais():
    # (read_rank=2, page_index=1) et (read_rank=1, page_index=3) : les deux
    # composantes sont croisees. Un lecteur qui confondrait les deux champs
    # rendrait l'autre page.
    document = lecture.depuis_json(fab.deux_pages_cible_seconde())
    rang_cible, index_cible = fab.ADRESSE_CIBLE
    rang_leurre, index_leurre = fab.ADRESSE_LEURRE
    assert rang_cible != index_cible and rang_leurre != index_leurre
    assert document.page_par_adresse(rang_cible, index_cible).adresse != (
        document.page_par_adresse(rang_leurre, index_leurre).adresse
    )
    with pytest.raises(KeyError):
        # Le couple croise n'existe pas : il ne doit rien rendre.
        document.page_par_adresse(rang_cible, index_leurre)


def test_la_zone_est_prise_par_slot_index_et_non_par_position():
    document = lecture.depuis_json(fab.deux_pages_cible_seconde())
    rang, index = fab.ADRESSE_CIBLE
    premiere = document.zone_par_adresse(rang, index, 0)
    seconde = document.zone_par_adresse(rang, index, 1)
    # Les deux zones sont DISTINGUABLES : un `find` qui rendrait toujours la
    # premiere se demasque sur la taille comme sur le timecode.
    assert (premiere.crop_w_px, premiere.crop_h_px) != (
        seconde.crop_w_px,
        seconde.crop_h_px,
    )
    assert premiere.frame_timecode != seconde.frame_timecode
    assert seconde.slot_index == 1
    with pytest.raises(KeyError):
        document.zone_par_adresse(rang, index, 7)


def test_une_zone_d_une_page_n_est_jamais_rendue_pour_une_autre():
    document = lecture.depuis_json(fab.deux_pages_cible_seconde())
    rang_cible, index_cible = fab.ADRESSE_CIBLE
    rang_leurre, index_leurre = fab.ADRESSE_LEURRE
    # Le leurre porte les emplacements 2 et 3, la cible 0 et 1 : l'appariement
    # page <-> zones est donc mesurable dans les deux sens.
    with pytest.raises(KeyError):
        document.zone_par_adresse(rang_cible, index_cible, 2)
    with pytest.raises(KeyError):
        document.zone_par_adresse(rang_leurre, index_leurre, 0)


# ---------------------------------------------------------------------------
# Marqueurs manquants : des IDENTIFIANTS, aucune position
# ---------------------------------------------------------------------------


def test_les_marqueurs_manquants_sont_nommes_par_identifiant():
    # Trois coins sur quatre : un document qu'aucun producteur n'ecrit
    # aujourd'hui (`MIN_CORNER_MARKERS_REQUIRED` vaut quatre), mais la GUI lit
    # des documents qu'elle n'ecrit pas. La cible est le coin d'ID 2 --
    # ni le premier, ni le dernier de la liste.
    coins = [
        fab.marqueur_de_coin(identifiant, 2, 1)
        for identifiant in layout.CORNER_MARKER_IDS
        if identifiant != 2
    ]
    brut = fab.deux_pages_cible_seconde()
    brut["pages"][1]["corner_markers"] = coins
    page = lecture.depuis_json(brut).page_par_adresse(*fab.ADRESSE_CIBLE)
    assert page.marqueurs_manquants == (2,)
    # Et les trois presents gardent chacun SON centre.
    centres = {
        marqueur.marker_id: (marqueur.center_x_px, marqueur.center_y_px)
        for marqueur in page.page.corner_markers
    }
    assert centres == {
        identifiant: fab.CENTRES_DE_COIN[identifiant]
        for identifiant in layout.CORNER_MARKER_IDS
        if identifiant != 2
    }
    assert len(set(centres.values())) == len(centres), (
        "des centres identiques rendraient toute permutation invisible"
    )


def test_aucun_marqueur_manquant_quand_les_quatre_coins_sont_la():
    document = lecture.depuis_json(fab.deux_pages_cible_seconde())
    assert document.page_par_adresse(*fab.ADRESSE_CIBLE).marqueurs_manquants == ()


# ---------------------------------------------------------------------------
# Aucune tolerance propre a la GUI
# ---------------------------------------------------------------------------


def test_un_document_altere_est_refuse_ici_comme_au_coeur():
    brut = fab.deux_pages_cible_seconde()
    brut["counters"]["pages_present"] = 7   # contredit les deux pages
    with pytest.raises(lecture.LectureDetectionError):
        lecture.depuis_json(brut)


def test_un_fichier_absent_est_refuse_nommement(tmp_path):
    with pytest.raises(lecture.LectureDetectionError):
        lecture.charger(tmp_path / "aucun-document.json")


def _document_a_code(valeur):
    """Deux pages, la cible en SECONDE position, dont le code vaut `valeur`."""
    brut = fab.deux_pages_cible_seconde(
        status=scan_detection.PAGE_REFUSED,
        qr_status=qr_codes.DECODE_NO_SYMBOL,
        refusal_reason="QR inexploitable.",
        identite=False,
        homographie=False,
        coins=False,
        zones=[],
    )
    brut["pages"][1][lecture.CLE_CODE_DE_REFUS] = valeur
    return brut


@pytest.mark.parametrize(
    "valeur", ["", "   ", "\t", "\n  \t ", 42, [], {}, True, 3.5],
    ids=["vide", "blancs", "tabulation", "blancs melanges",
         "entier", "liste", "mapping", "booleen", "flottant"],
)
def test_un_code_de_refus_sans_rien_d_exploitable_vaut_absent(valeur):
    """`BH-8` + `EC-9`, revue de vague 2 bis -- `[Review][Patch]` sur 7.4.

    « Elle n'invente jamais de code » vaut contre le vide, contre le BLANC, et
    contre le non textuel. Deux regimes distincts etaient casses ici :

    * `"   "` **traversait** et s'affichait comme un badge de code vide -- le
      trou etait des DEUX cotes, coeur et ecran, avec la meme condition ;
    * une valeur non textuelle rendait, apres 5.27, **tout le document
      illisible** dans l'ecran. C'est l'inverse de l'argument que la vague
      ecrit elle-meme : un champ purement informatif ne peut pas rendre un
      scan entier illisible.

    Le repli est le meme dans les neuf cas : le code vaut `None`, la phrase
    reste affichee, et **le document reste lu**.
    """
    document = lecture.depuis_json(_document_a_code(valeur))
    page = document.page_par_adresse(*fab.ADRESSE_CIBLE)
    assert page.code_de_refus is None
    # Le document reste LU, et la phrase -- elle -- est intacte.
    assert len(document.pages) == 2
    assert page.page.refusal_reason == "QR inexploitable."


def test_un_code_de_refus_qui_porte_du_contenu_traverse_verbatim():
    """La borne de l'inversion : le `strip` DECIDE, il ne normalise pas.

    Sans ce test, « rien d'exploitable vaut absent » pourrait deriver en « le
    lecteur normalise ce qu'il lit », et un code cesserait d'etre identique a
    ce que le coeur a pose.
    """
    page = lecture.depuis_json(
        _document_a_code("  qr-inexploitable-sans-manifest  ")
    ).page_par_adresse(*fab.ADRESSE_CIBLE)
    assert page.code_de_refus == "  qr-inexploitable-sans-manifest  "
