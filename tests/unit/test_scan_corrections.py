# -*- coding: utf-8 -*-
"""Banc de la couche de correction manuelle (story 7.5, T6 ; `EPIC7-ARB-95`).

Le regime A tient ou tombe sur une seule mesure : la couche est **invisible**
pour tout lecteur d'aujourd'hui, et l'empreinte de detection ne bouge pas.
C'est ce que ce banc mesure en premier, contre le **vrai** lecteur
(`scan_previz_from_json_dict`), pas contre une doublure.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_BANC_GUI = Path(__file__).resolve().parent / "gui"
if str(_BANC_GUI) not in sys.path:
    sys.path.insert(0, str(_BANC_GUI))

import fabriques_scan as fs  # noqa: E402
from mixed_media_utility import (  # noqa: E402
    previz_common,
    scan_corrections,
    scan_crop,
    scan_previz,
)

#: Un document de detection **reellement produit par le coeur** : c'est la
#: sortie de `scan detect` sur une planche reelle, versee au depot en 7.4. Les
#: mesures d'octets ci-dessous partent de LUI, jamais d'un document mis en
#: scene par le banc -- un test qui reserialiserait lui-meme sa fixture avant
#: de comparer ne mesurerait que sa propre mise en scene, et c'est exactement
#: ce qui a laisse passer la seconde recette de canonicalisation de 7.5.
DOCUMENT_REEL = (
    Path(__file__).resolve().parents[1]
    / "fixtures" / "detection-scan-reelle" / "detect-ok-et-refus.json"
)


def document_reel_sur_disque(tmp_path, nom="detection.json"):
    """Copie octet pour octet du document du coeur, dans un dossier jetable."""
    chemin = tmp_path / nom
    chemin.write_bytes(DOCUMENT_REEL.read_bytes())
    return chemin


# ---------------------------------------------------------------------------
# Fabriques -- deux planches corrigees DISTINGUABLES, cible hors premiere place
# ---------------------------------------------------------------------------
#
# `EPIC7-ARB-102` : la fabrique qui vivait ici produisait deux `ZoneCorrigee`.
# Le levier des zones a ete retire -- les rectangles de decoupe viennent du
# gabarit, jamais de la detection, donc les corriger ne redressait rien --, et
# la fabrique avec lui. Ce que la couche porte, et donc ce que tout ce banc
# mesure, ce sont les CONTOURS des quatre marqueurs ArUco.


def _carre(marqueur, centre_x, centre_y, cote=40.0):
    """Le contour d'un marqueur, centre sur ce point -- quatre sommets."""
    demi = cote / 2.0
    return (marqueur, (
        (centre_x - demi, centre_y - demi),
        (centre_x + demi, centre_y - demi),
        (centre_x + demi, centre_y + demi),
        (centre_x - demi, centre_y + demi),
    ))


def deux_planches_corrigees():
    """Deux planches corrigees, sur deux rangs DIFFERENTS.

    La cible naturelle des assertions est la **seconde** : un `find` fautif qui
    rendrait toujours la premiere ne se demasque pas autrement. Les quatre
    carres de chaque planche sont eux-memes tous distincts -- une permutation de
    marqueurs ne se voit que si les contours different.
    """
    return (
        scan_corrections.CoinsCorriges(
            read_rank=0,
            carres=(_carre(0, 10.5, 11.5), _carre(1, 900.0, 12.25),
                    _carre(2, 890.75, 600.5), _carre(3, 12.0, 598.0)),
        ),
        scan_corrections.CoinsCorriges(
            read_rank=1,
            carres=(_carre(0, 20.5, 21.5), _carre(1, 910.0, 22.25),
                    _carre(2, 880.75, 610.5), _carre(3, 22.0, 608.0)),
        ),
    )


# ---------------------------------------------------------------------------
# La mesure qui fonde le regime A
# ---------------------------------------------------------------------------


def test_la_couche_laisse_le_document_RELU_EGAL_a_celui_d_avant():
    """`EPIC7-ARB-95` : l'empreinte signe la detection, qui n'a pas change."""
    brut = fs.document_du_lot_complet()
    avant = scan_previz.scan_previz_from_json_dict(brut)

    corrige = scan_corrections.poser_les_coins(brut, deux_planches_corrigees())
    apres = scan_previz.scan_previz_from_json_dict(corrige)

    assert apres == avant


def test_l_empreinte_de_detection_ne_bouge_pas():
    """C'est l'identite des noeuds du chutier qui en depend."""
    brut = fs.document_du_lot_complet()
    corrige = scan_corrections.poser_les_coins(brut, deux_planches_corrigees())
    assert corrige["fingerprints"] == brut["fingerprints"]


def test_les_pages_sortent_BIT_POUR_BIT_comme_elles_sont_entrees():
    brut = fs.document_du_lot_complet()
    pages_avant = json.dumps(brut["pages"], sort_keys=True)
    corrige = scan_corrections.poser_les_coins(brut, deux_planches_corrigees())
    assert json.dumps(corrige["pages"], sort_keys=True) == pages_avant


def test_poser_ne_mute_pas_le_document_d_origine():
    brut = fs.document_du_lot_complet()
    scan_corrections.poser_les_coins(brut, deux_planches_corrigees())
    assert scan_corrections.CLE_DOCUMENT not in brut


def test_un_document_jamais_corrige_ressort_OCTET_POUR_OCTET(tmp_path):
    """L'interdit verbatim de `EPIC7-ARB-95`, mesure sur des **octets**.

    « Un document jamais corrige produit, apres passage par 7.5, exactement les
    **memes octets** qu'avant -- aucune reecriture gratuite. »

    Le document de depart est celui du coeur, lu sur le disque ; il ressort par
    le vrai chemin d'ecriture (`poser` **puis** `ecrire`), et ce sont ses
    octets relus qui sont compares. Toute serialisation differente de celle du
    producteur -- une indentation, un `ensure_ascii=False`, un saut de ligne
    final, un separateur avec espace -- fait tomber ce test. La version
    d'avant, qui comparait deux `json.dumps` en memoire sans jamais appeler
    `ecrire`, ne pouvait en attraper aucune.
    """
    chemin = document_reel_sur_disque(tmp_path)
    avant = chemin.read_bytes()

    document = json.loads(avant.decode("utf-8"))
    scan_corrections.ecrire(chemin, scan_corrections.poser_les_coins(document, ()))

    assert chemin.read_bytes() == avant


def test_le_fichier_ecrit_est_dans_la_forme_canonique_DU_DEPOT(tmp_path):
    """Un seul point de canonicalisation, et c'est celui du depot.

    `previz_common.canonical_json` est le serialiseur du producteur
    (`scan_detect`, deux sites) ; cette couche ecrit **le meme fichier** et
    doit donc passer par lui. Le test compare les octets ecrits a ceux de ce
    serialiseur -- une seconde recette locale, meme equivalente en apparence,
    tombe ici.
    """
    chemin = tmp_path / "detection.json"
    document = json.loads(DOCUMENT_REEL.read_bytes().decode("utf-8"))
    corrige = scan_corrections.poser_les_coins(document, deux_planches_corrigees())

    scan_corrections.ecrire(chemin, corrige)

    assert chemin.read_bytes() == previz_common.canonical_json(corrige).encode("utf-8")


def test_le_fichier_ecrit_ne_porte_AUCUN_SAUT_DE_LIGNE(tmp_path):
    """Le document cesse de dependre de l'OS, et c'est une mesure directe.

    L'ecrivain atomique ouvre son temporaire en mode texte **sans**
    `newline=""` : tout `\\n` qu'on lui donne ressort `\\r\\n` sous Windows.
    Mesure de la campagne du 2026-08-27 sur un document reel de 2130 octets :
    l'aller-retour rendait 3123 octets et **120 CRLF**. La forme canonique
    n'ayant aucun saut de ligne, il n'y a plus rien a traduire -- et le compte
    de CRLF est la facon la plus courte de le dire.
    """
    chemin = tmp_path / "detection.json"
    document = json.loads(DOCUMENT_REEL.read_bytes().decode("utf-8"))

    scan_corrections.ecrire(chemin, scan_corrections.poser_les_coins(document, deux_planches_corrigees()))

    octets = chemin.read_bytes()
    assert octets.count(b"\r\n") == 0
    assert octets.count(b"\n") == 0


def test_un_NaN_est_REFUSE_a_l_ecriture_et_ne_laisse_aucun_fichier(tmp_path):
    """`allow_nan=False`, comme le producteur -- et pas comme `json.dumps`.

    `json.dumps` emet `NaN` et `Infinity` par defaut : **aucun** parseur JSON
    strict ne les accepte, donc le document serait illisible chez son
    destinataire. La seconde recette de serialisation les laissait passer
    (`b'{"a": NaN, ...'`), la forme canonique du depot les refuse.
    """
    chemin = tmp_path / "detection.json"
    document = json.loads(DOCUMENT_REEL.read_bytes().decode("utf-8"))
    document["counters"]["frames_written"] = float("nan")

    with pytest.raises(ValueError):
        scan_corrections.ecrire(chemin, document)

    # Le refus tombe AVANT l'ecrivain atomique : rien n'est cree, pas meme un
    # temporaire.
    assert list(tmp_path.iterdir()) == []


def test_annuler_toutes_les_corrections_REDONNE_LES_OCTETS_d_origine(tmp_path):
    """Aller-retour complet sur disque : corriger, tout annuler, re-comparer.

    C'est le geste reel de l'operatrice qui revient sur son jugement. Les deux
    ecritures passent par `ecrire` ; la cible de la comparaison est l'octet du
    document du coeur, pas un objet Python.
    """
    chemin = document_reel_sur_disque(tmp_path)
    avant = chemin.read_bytes()

    document = json.loads(avant.decode("utf-8"))
    scan_corrections.ecrire(chemin, scan_corrections.poser_les_coins(document, deux_planches_corrigees()))
    corrige = json.loads(chemin.read_bytes().decode("utf-8"))
    assert corrige != document, "la fixture ne prouve rien si la couche n'a rien pose"

    scan_corrections.ecrire(chemin, scan_corrections.poser_les_coins(corrige, ()))

    assert chemin.read_bytes() == avant


# ---------------------------------------------------------------------------
# Lecture : le repli permanent, et les refus
# ---------------------------------------------------------------------------


def test_un_document_sans_couche_rend_un_dictionnaire_vide():
    """Repli permanent : tout document ecrit avant 7.5 passe par la."""
    assert scan_corrections.lire_les_coins(fs.document_du_lot_complet()) == {}


def test_l_aller_retour_conserve_les_deux_corrections():
    brut = fs.document_du_lot_complet()
    planches = deux_planches_corrigees()
    relu = scan_corrections.lire_les_coins(
        scan_corrections.poser_les_coins(brut, planches))
    assert set(relu) == {0, 1}
    # La SECONDE, celle qui n'est pas en premiere position.
    assert relu[1] == planches[1]


def test_une_couche_d_un_autre_schema_est_refusee_pas_devinee():
    brut = fs.document_du_lot_complet()
    brut = dict(brut)
    # Un schema qui n'est **ni** celui des coins **ni** celui, retire, des
    # zones : le refus doit porter sur l'inconnu en general, pas seulement sur
    # le seul autre nom que le depot ait jamais ecrit.
    brut[scan_corrections.CLE_DOCUMENT] = {
        "schema": "manual-corrections-v9", "pages": []}
    with pytest.raises(scan_corrections.CorrectionInvalide) as refus:
        scan_corrections.lire_les_coins(brut)
    # Le refus NOMME les deux schemas : celui qu'on a lu, celui qu'on attendait.
    assert "manual-corrections-v9" in str(refus.value)
    assert scan_corrections.SCHEMA_DE_CORRECTION in str(refus.value)


# `EPIC7-ARB-102` -- CE QUI VIVAIT ICI. Huit tests de forme portant sur le
# rectangle d'une zone : adresse incomplete, cote de rectangle manquant,
# dialecte du document (`crop_rect_px`), booleen passant pour un entier, zone
# degeneree, doublon d'adresse. Ils sont retires **avec** le lecteur qu'ils
# mesuraient. Leurs equivalents portant sur les CONTOURS -- qui sont, eux,
# corrigeables -- vivent en fin de fichier : contour a trois sommets refuse,
# booleen refuse pour une abscisse, quatre marqueurs exiges, doublon de planche
# refuse.


def test_une_couche_SANS_CLE_pages_est_lue_comme_une_couche_vide():
    """Le repli `[]` de `couche.get("pages", [])`, mesure.

    Une couche qui declare le bon schema sans porter de planche n'est pas une
    anomalie : c'est le seul etat qu'une ecriture interrompue plus haut peut
    laisser, et il se lit « aucune correction », jamais une explosion.
    """
    brut = dict(fs.document_du_lot_complet())
    brut[scan_corrections.CLE_DOCUMENT] = {
        "schema": scan_corrections.SCHEMA_DE_CORRECTION
    }
    assert scan_corrections.lire_les_coins(brut) == {}


def test_POSER_refuse_deux_corrections_pour_la_MEME_planche():
    """La garde du cote ECRITURE -- celui que la GUI appelle.

    `lire_les_coins` refuse bruyamment une ambiguite de rang ; `poser_les_coins`
    doit la refuser aussi, sans quoi la doctrine ne tient que du cote lecture et
    l'interface peut ecrire un fichier que le lecteur du depot refusera ensuite.

    Regle des fabriques : **trois** planches distinguables, et le doublon n'est
    ni en premiere ni en deuxieme position -- une garde qui ne comparerait que
    les deux premieres passerait un test ou le doublon ouvre la liste.
    """
    premiere, seconde = deux_planches_corrigees()
    doublon = scan_corrections.CoinsCorriges(
        read_rank=seconde.read_rank,
        carres=(_carre(0, 1.0, 2.0), _carre(1, 3.0, 4.0),
                _carre(2, 5.0, 6.0), _carre(3, 7.0, 8.0)),
    )
    assert doublon != seconde, "le doublon doit etre distinguable du premier"

    with pytest.raises(scan_corrections.CorrectionInvalide) as refus:
        scan_corrections.poser_les_coins(
            fs.document_du_lot_complet(), (premiere, seconde, doublon))

    # Le refus NOMME le rang en litige : sans lui, l'operatrice ne sait pas
    # laquelle de ses corrections rejouer.
    assert str(seconde.read_rank) in str(refus.value)


# `EPIC7-ARB-102` : le test qui mesurait ici la frontiere exacte de la garde --
# « deux emplacements de la MEME planche restent acceptes, l'adresse est un
# COUPLE » -- n'a plus d'objet. Une planche se redresse d'un bloc, sur ses
# quatre marqueurs : l'adresse d'une correction est le seul rang de lecture, et
# deux corrections du meme rang sont par construction une ambiguite.


# ---------------------------------------------------------------------------
# L'ecriture atomique
# ---------------------------------------------------------------------------


def test_l_ecriture_est_atomique_et_relisible(tmp_path):
    chemin = tmp_path / "detection.json"
    brut = fs.document_du_lot_complet()
    scan_corrections.ecrire(chemin, scan_corrections.poser_les_coins(brut, deux_planches_corrigees()))
    relu = json.loads(chemin.read_text(encoding="utf-8"))
    assert set(scan_corrections.lire_les_coins(relu)) == {0, 1}
    # Le vrai lecteur du depot relit le fichier ecrit.
    assert scan_previz.scan_previz_from_json_dict(relu) == (
        scan_previz.scan_previz_from_json_dict(brut)
    )


def test_un_echec_en_cours_d_ecriture_laisse_le_document_d_origine_INTACT(
    tmp_path, monkeypatch
):
    """Le seul fichier qui porte le jugement de l'operatrice."""
    from mixed_media_utility import scan_detect

    chemin = tmp_path / "detection.json"
    origine = json.dumps(fs.document_du_lot_complet(), sort_keys=True)
    chemin.write_text(origine, encoding="utf-8")

    def _echouer(_path, _texte):
        raise OSError("disque plein au milieu de l'ecriture")

    monkeypatch.setattr(scan_detect, "ecrire_document_json_atomiquement", _echouer)
    with pytest.raises(OSError):
        scan_corrections.ecrire(chemin, fs.document_du_lot_complet())

    assert chemin.read_text(encoding="utf-8") == origine


def test_aucun_temporaire_ne_reste_apres_une_ecriture_reussie(tmp_path):
    chemin = tmp_path / "detection.json"
    scan_corrections.ecrire(chemin, fs.document_du_lot_complet())
    restes = [p.name for p in tmp_path.iterdir() if p.name != chemin.name]
    assert restes == []


# ---------------------------------------------------------------------------
# L'application au plan -- `EPIC7-ARB-102` : elle n'existe plus
# ---------------------------------------------------------------------------
#
# Quatre tests vivaient ici, sur `scan_corrections.appliquer_au_plan` : la
# correction s'applique a l'emplacement VISE et pas a une position, une
# correction d'un autre rang ne touche pas cette page, un plan sans correction
# traverse SANS COPIE, le reste du plan est conserve. Ils mesuraient un
# appariement soigneux -- et un appariement soigneux vers une geometrie qui ne
# pouvait pas etre fausse.
#
# La correction n'entre plus dans le plan de decoupe : elle entre dans le
# **redressement**, en amont. `cli._scanned_pages_for_output` derive
# l'homographie des quatre contours corriges et redresse la page avec elle ; le
# plan, lui, continue de venir du gabarit, inchange. Ce chemin-la est mesure
# dans `tests/unit/test_scan_write_corrections.py`.


# ---------------------------------------------------------------------------
# EPIC7-ARB-102 -- la couche porte desormais les COINS, et les deux versions
# se refusent mutuellement
# ---------------------------------------------------------------------------


def test_les_carres_font_UN_ALLER_RETOUR_sans_perte():
    """Ecrire puis relire rend **exactement** les memes contours, flottants compris.

    Les arrondir serait une perte silencieuse : un sommet pose a la loupe tombe
    entre deux pixels, et c'est cette fraction que la loupe existe pour donner.
    La cible verifiee est la **seconde** planche.

    Ce sont bien les CONTOURS qui sont compares, pas les centres : le centre se
    deduit, et deux contours differents peuvent partager un centre -- comparer
    les centres laisserait donc passer une perte de forme.
    """
    brut = fs.document_du_lot_complet()

    relu = scan_corrections.lire_les_coins(
        scan_corrections.poser_les_coins(brut, deux_planches_corrigees()))

    assert sorted(relu) == [0, 1]
    assert relu[1].carres == deux_planches_corrigees()[1].carres


def test_le_centre_se_DEDUIT_du_contour_et_n_est_pas_persiste():
    """Le document porte des **contours** ; le centre n'y figure jamais.

    C'est ce qui permet de rouvrir une correction pour la retoucher : un centre
    persiste aurait perdu le geste, et l'operatrice devrait tout refaire.
    """
    corrigee = deux_planches_corrigees()[1]
    ecrit = corrigee.as_document()[scan_corrections.CLE_COINS][0]

    assert set(ecrit) == {"marker_id", "quad"}
    assert len(ecrit["quad"]) == scan_corrections.SOMMETS_PAR_CARRE
    # Et le centre reste calculable, par la definition unique du depot.
    assert corrigee.centres[0] == (
        (0,) + scan_corrections.centre_du_carre(corrigee.carres[0][1]))


def test_la_couche_de_coins_laisse_le_document_RELU_EGAL_a_celui_d_avant():
    """`EPIC7-ARB-95` tient inchange sous le nouveau levier.

    C'est la mesure qui fonde le regime A, refaite pour les coins : la couche est
    invisible au **vrai** lecteur du depot, pas a une doublure.
    """
    brut = fs.document_du_lot_complet()
    avant = scan_previz.scan_previz_from_json_dict(brut)

    corrige = scan_corrections.poser_les_coins(brut, deux_planches_corrigees())

    assert scan_previz.scan_previz_from_json_dict(corrige) == avant
    assert corrige["fingerprints"] == brut["fingerprints"]
    assert scan_corrections.CLE_DOCUMENT not in brut


def test_annuler_toutes_les_corrections_de_coins_retire_la_couche():
    """Une liste vide **retire** la couche au lieu d'en ecrire une vide.

    Sans cela, « annuler toutes ses corrections » laisserait une trace et le
    document ne redeviendrait jamais celui d'avant -- l'interdit verbatim de
    `EPIC7-ARB-95`, « aucune reecriture gratuite ».
    """
    brut = fs.document_du_lot_complet()
    corrige = scan_corrections.poser_les_coins(brut, deux_planches_corrigees())

    assert scan_corrections.poser_les_coins(corrige, ()) == brut


def test_un_document_sans_couche_rend_aucun_coin():
    """Le repli permanent : la couche est additive, son absence n'est pas une
    anomalie et ne se signale pas."""
    assert scan_corrections.lire_les_coins(fs.document_du_lot_complet()) == {}


def test_une_couche_de_ZONES_deja_ecrite_est_refusee_en_NOMMANT_l_arbitrage():
    """**Le test qui empeche le silence**, et c'est le defaut qu'il ferme.

    Le levier des zones a ete retire par `EPIC7-ARB-102`, lecteur et ecrivain
    compris -- mais des documents portant sa couche ont pu etre ecrits par la
    vague 4 **avant** l'arbitrage, et ils sont sur le disque d'Egan. Les deux
    couches vivent sous la meme cle de document et ne different que par leur
    `schema` : un lecteur qui accepterait l'autre version lirait sa liste
    absente et rendrait « aucune correction » **sans un mot**, c'est-a-dire
    effacerait en silence un travail que l'operatrice croit avoir fait.

    La couche v1 est forgee ici a la main, et c'est deliberé : il n'existe plus
    d'ecrivain capable de la produire, donc la seule facon de mesurer le refus
    est de reconstituer ce qu'un document d'avant porte reellement.
    """
    document_de_zones = dict(fs.document_du_lot_complet())
    document_de_zones[scan_corrections.CLE_DOCUMENT] = {
        "schema": scan_corrections.SCHEMA_DE_CORRECTION_V1,
        "zones": [
            {"read_rank": 0, "slot_index": 0,
             "crop_rect_px": {"x": 10, "y": 20, "width": 100, "height": 50}},
            {"read_rank": 1, "slot_index": 3,
             "crop_rect_px": {"x": 640, "y": 480, "width": 320, "height": 160}},
        ],
    }

    with pytest.raises(scan_corrections.CorrectionInvalide) as refus:
        scan_corrections.lire_les_coins(document_de_zones)

    # Le refus NOMME le changement plutot que d'opposer deux numeros de version :
    # l'operatrice doit apprendre que son levier a ete retire, pas qu'un schema
    # ne correspond pas.
    message = str(refus.value)
    assert "EPIC7-ARB-102" in message
    assert "coins ArUco" in message


def test_une_couche_de_COINS_se_relit_elle_meme_sans_refus():
    """La contrepartie du refus ci-dessus : il est cible, pas general.

    Sans cette moitie, un lecteur qui refuserait **tout** passerait le test
    precedent -- et la couche courante serait illisible.
    """
    document = scan_corrections.poser_les_coins(
        fs.document_du_lot_complet(), deux_planches_corrigees())
    assert set(scan_corrections.lire_les_coins(document)) == {0, 1}


@pytest.mark.parametrize(
    "identifiants, raison",
    [
        ((0, 1, 2), "trois marqueurs"),
        ((0, 1, 2, 2), "un marqueur en double et un manquant"),
    ],
)
def test_une_planche_corrigee_porte_EXACTEMENT_quatre_marqueurs(identifiants, raison):
    """Les deux pieges reels de la detection, refuses a la construction.

    Le coeur porte deja `REFUS_COINS_MANQUANTS` et `REFUS_COINS_EN_DOUBLE` ; les
    poser ici evite qu'un etat impossible soit **ecrit sur le disque** et
    n'echoue qu'a la relecture, une session plus tard.
    """
    carres = tuple(
        _carre(identifiant, 100.0 * (rang + 1), 100.0)
        for rang, identifiant in enumerate(identifiants)
    )
    with pytest.raises(scan_corrections.CorrectionInvalide):
        scan_corrections.CoinsCorriges(read_rank=0, carres=carres), raison


def test_un_contour_a_TROIS_sommets_est_refuse_a_la_construction():
    """Trois sommets ne definissent pas un contour, et un centre calcule sur
    trois points serait faux d'apparence valide -- c'est le centre qui redresse
    la page.
    """
    tronque = (0, ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0)))
    with pytest.raises(scan_corrections.CorrectionInvalide):
        scan_corrections.CoinsCorriges(
            read_rank=0,
            carres=(tronque, _carre(1, 5, 5), _carre(2, 9, 9), _carre(3, 1, 9)),
        )


def test_un_booleen_ne_passe_pas_pour_une_abscisse():
    """`True` est un `int` en Python : sans garde il s'ecrivait « x = 1 ».

    Meme doctrine et meme phrase que `_entier`, dont ce module porte deja le
    piege pour les rectangles.
    """
    droit = [[1.0, 2.0], [3.0, 2.0], [3.0, 4.0], [1.0, 4.0]]
    with pytest.raises(scan_corrections.CorrectionInvalide):
        scan_corrections.CoinsCorriges.depuis_document({
            "read_rank": 0,
            scan_corrections.CLE_COINS: [
                {"marker_id": 0,
                 "quad": [[True, 2.0], [3.0, 2.0], [3.0, 4.0], [1.0, 4.0]]},
                {"marker_id": 1, "quad": droit},
                {"marker_id": 2, "quad": droit},
                {"marker_id": 3, "quad": droit},
            ],
        })


def test_deux_corrections_pour_la_MEME_planche_sont_refusees():
    """L'ambiguite se refuse des deux cotes -- ecriture et lecture --, comme
    pour les zones : laquelle des deux vaut ne se devine pas."""
    coins = deux_planches_corrigees()[1]

    with pytest.raises(scan_corrections.CorrectionInvalide):
        scan_corrections.poser_les_coins(fs.document_du_lot_complet(), (coins, coins))


# ---------------------------------------------------------------------------
# EPIC7-ARB-103 -- l'identite saisie a la main, seconde liste de la meme couche
# ---------------------------------------------------------------------------


def deux_identites_saisies():
    """Deux identites, sur deux rangs DIFFERENTS et tous champs distincts.

    La cible naturelle des assertions est la **seconde** : un `find` fautif qui
    rendrait toujours la premiere ne se demasque pas autrement. Les gabarits
    eux-memes different -- deux identites qui ne differeraient que par leur rang
    laisseraient passer un appariement par position.
    """
    return (
        scan_corrections.IdentiteManuelle(
            read_rank=0, lot_id="lot-alpha",
            template_id="tpl-a4-portrait-2f-v1",
            frames_per_page=2, page_index=0,
            first_frame_timecode="01:00:00:00",
            last_frame_timecode="01:00:01:00",
        ),
        scan_corrections.IdentiteManuelle(
            read_rank=3, lot_id="lot-beta",
            template_id="tpl-a4-paysage-4f-v2",
            frames_per_page=4, page_index=2,
            first_frame_timecode="02:11:22:03",
            last_frame_timecode="02:11:25:03",
        ),
    )


def test_les_identites_font_un_ALLER_RETOUR_sans_perte():
    brut = fs.document_du_lot_complet()
    identites = deux_identites_saisies()

    relu = scan_corrections.lire_les_identites(
        scan_corrections.poser_les_identites(brut, identites))

    assert set(relu) == {0, 3}
    # La SECONDE, celle qui n'est pas en premiere position.
    assert relu[3] == identites[1]


def test_la_couche_d_identites_laisse_le_document_RELU_EGAL_a_celui_d_avant():
    """`EPIC7-ARB-95` tient pour la seconde liste comme pour la premiere.

    C'est la mesure qui fonde le regime A, refaite sur ce qui vient d'y entrer :
    le **vrai** lecteur du depot relit un document porteur d'identites saisies et
    rend un objet egal a celui d'avant. Sans elle, l'identite manuelle serait un
    champ que `scan_previz` apprendrait -- et l'empreinte de detection devrait
    bouger.
    """
    brut = fs.document_du_lot_complet()
    avant = scan_previz.scan_previz_from_json_dict(brut)

    corrige = scan_corrections.poser_les_identites(brut, deux_identites_saisies())

    assert scan_previz.scan_previz_from_json_dict(corrige) == avant
    assert corrige["fingerprints"] == brut["fingerprints"]


def test_poser_des_identites_ne_mute_pas_le_document_d_origine():
    brut = fs.document_du_lot_complet()
    scan_corrections.poser_les_identites(brut, deux_identites_saisies())
    assert scan_corrections.CLE_DOCUMENT not in brut


def test_un_document_sans_couche_ne_rend_AUCUNE_identite():
    assert scan_corrections.lire_les_identites(fs.document_du_lot_complet()) == {}


def test_une_couche_de_COINS_SEULS_ne_rend_aucune_identite():
    """Les deux listes sont independantes, et l'absence de l'une n'est pas une
    anomalie : corriger la geometrie d'une planche ne dit rien de son identite.
    """
    document = scan_corrections.poser_les_coins(
        fs.document_du_lot_complet(), deux_planches_corrigees())
    assert scan_corrections.lire_les_identites(document) == {}


def test_une_couche_d_IDENTITES_SEULES_ne_rend_aucun_coin():
    """La symetrique, et elle n'est pas gratuite : sans elle, un lecteur de
    coins qui leverait sur une couche sans `pages` rendrait inexploitable toute
    planche dont on n'a saisi que l'identite.
    """
    document = scan_corrections.poser_les_identites(
        fs.document_du_lot_complet(), deux_identites_saisies())
    assert scan_corrections.lire_les_coins(document) == {}


# ---------------------------------------------------------------------------
# Les deux listes COEXISTENT -- le defaut qu'un ecrivain naif produit
# ---------------------------------------------------------------------------


def test_ecrire_les_identites_CONSERVE_les_coins_deja_poses():
    """**Le piege central de la seconde liste**, et il est silencieux.

    Les deux listes vivent sous la meme cle de document. Un ecrivain qui
    reecrirait la couche entiere -- ce que `poser_les_coins` faisait tant qu'il
    etait seul -- effacerait l'autre liste sans un mot. Le geste reel qui le
    declenche est ordinaire : corriger la geometrie d'une planche, puis saisir
    son identite au formulaire.
    """
    document = scan_corrections.poser_les_coins(
        fs.document_du_lot_complet(), deux_planches_corrigees())

    document = scan_corrections.poser_les_identites(
        document, deux_identites_saisies())

    assert set(scan_corrections.lire_les_coins(document)) == {0, 1}
    assert set(scan_corrections.lire_les_identites(document)) == {0, 3}


def test_ecrire_les_coins_CONSERVE_les_identites_deja_saisies():
    """L'ordre inverse du geste, et il doit tenir aussi : saisir l'identite
    d'une planche muette, puis en corriger les quatre coins.
    """
    document = scan_corrections.poser_les_identites(
        fs.document_du_lot_complet(), deux_identites_saisies())

    document = scan_corrections.poser_les_coins(
        document, deux_planches_corrigees())

    assert set(scan_corrections.lire_les_identites(document)) == {0, 3}
    assert set(scan_corrections.lire_les_coins(document)) == {0, 1}


def test_retirer_UNE_liste_laisse_l_autre_et_la_couche():
    """Annuler ses corrections de geometrie n'annule pas son identite saisie."""
    document = scan_corrections.poser_les_identites(
        scan_corrections.poser_les_coins(
            fs.document_du_lot_complet(), deux_planches_corrigees()),
        deux_identites_saisies())

    document = scan_corrections.poser_les_coins(document, ())

    assert scan_corrections.lire_les_coins(document) == {}
    assert set(scan_corrections.lire_les_identites(document)) == {0, 3}
    assert scan_corrections.CLE_DOCUMENT in document


def test_retirer_LES_DEUX_listes_fait_disparaitre_la_couche(tmp_path):
    """« Tout annuler » redonne exactement le document d'avant, aux OCTETS.

    Une couche vidée qui resterait presente -- ne portant plus que son numero de
    schema -- laisserait une trace de corrections qui n'existent plus, et le
    document ne ressortirait plus octet pour octet.
    """
    chemin = document_reel_sur_disque(tmp_path)
    avant = chemin.read_bytes()
    document = json.loads(avant.decode("utf-8"))

    document = scan_corrections.poser_les_coins(document, deux_planches_corrigees())
    document = scan_corrections.poser_les_identites(document, deux_identites_saisies())
    scan_corrections.ecrire(chemin, document)
    assert chemin.read_bytes() != avant, "la fixture ne prouve rien sans couche"

    document = json.loads(chemin.read_bytes().decode("utf-8"))
    document = scan_corrections.poser_les_coins(document, ())
    document = scan_corrections.poser_les_identites(document, ())
    scan_corrections.ecrire(chemin, document)

    assert scan_corrections.CLE_DOCUMENT not in json.loads(
        chemin.read_bytes().decode("utf-8"))
    assert chemin.read_bytes() == avant


# ---------------------------------------------------------------------------
# La provenance, et les refus de forme
# ---------------------------------------------------------------------------


def test_la_PROVENANCE_est_ecrite_dans_le_document():
    """`EPIC7-ARB-103` : « le manifest garde la marque de sa provenance ».

    Le champ est ecrit a la source, dans le document que la main a modifie. Un
    lecteur en aval ne peut donc pas confondre une identite affirmee par un
    humain avec une identite decodee -- « le jour ou un timecode est faux, il
    faut savoir qui l'a dit ».
    """
    document = scan_corrections.poser_les_identites(
        fs.document_du_lot_complet(), deux_identites_saisies())
    ecrites = document[scan_corrections.CLE_DOCUMENT][scan_corrections.CLE_IDENTITES]

    assert [entree["source"] for entree in ecrites] == (
        [scan_corrections.PROVENANCE_MANUELLE] * 2)


def test_une_identite_SANS_provenance_est_refusee_pas_devinee():
    """Le refus qui donne son sens au champ.

    Une entree qui ne dit pas d'ou elle vient n'est pas une identite manuelle :
    la lire comme telle ferait passer pour « affirmee par un humain » quelque
    chose que personne n'a affirme. C'est l'inverse exact de ce que le champ
    existe pour porter.
    """
    entree = deux_identites_saisies()[1].as_document()
    del entree["source"]
    brut = dict(fs.document_du_lot_complet())
    brut[scan_corrections.CLE_DOCUMENT] = {
        "schema": scan_corrections.SCHEMA_DE_CORRECTION,
        scan_corrections.CLE_IDENTITES: [entree],
    }
    with pytest.raises(scan_corrections.CorrectionInvalide):
        scan_corrections.lire_les_identites(brut)


@pytest.mark.parametrize("champ", list(scan_corrections.CHAMPS_D_IDENTITE))
def test_une_identite_a_qui_il_manque_un_champ_est_refusee(champ):
    """Les six champs sont exiges NOMMEMENT, y compris le gabarit.

    Le parametrage se derive de la constante du module, jamais recopie : un
    champ ajoute au formulaire sans etre exige ici passerait inapercu.
    """
    entree = deux_identites_saisies()[1].as_document()
    del entree[champ]
    brut = dict(fs.document_du_lot_complet())
    brut[scan_corrections.CLE_DOCUMENT] = {
        "schema": scan_corrections.SCHEMA_DE_CORRECTION,
        scan_corrections.CLE_IDENTITES: [entree],
    }
    with pytest.raises(scan_corrections.CorrectionInvalide) as refus:
        scan_corrections.lire_les_identites(brut)
    assert champ in str(refus.value)


@pytest.mark.parametrize("champ", ["lot_id", "template_id",
                                   "first_frame_timecode", "last_frame_timecode"])
@pytest.mark.parametrize("valeur", ["", "   ", 4, None])
def test_un_champ_de_texte_vide_ou_non_textuel_est_refuse(champ, valeur):
    """Un identifiant blanc se lirait comme un identifiant."""
    entree = deux_identites_saisies()[1].as_document()
    entree[champ] = valeur
    brut = dict(fs.document_du_lot_complet())
    brut[scan_corrections.CLE_DOCUMENT] = {
        "schema": scan_corrections.SCHEMA_DE_CORRECTION,
        scan_corrections.CLE_IDENTITES: [entree],
    }
    with pytest.raises(scan_corrections.CorrectionInvalide):
        scan_corrections.lire_les_identites(brut)


@pytest.mark.parametrize("champ", ["read_rank", "frames_per_page", "page_index"])
def test_un_booleen_ne_passe_pas_pour_un_entier_d_identite(champ):
    """`True` est un `int` en Python : il se lirait « 1 frame par page »."""
    entree = deux_identites_saisies()[1].as_document()
    entree[champ] = True
    brut = dict(fs.document_du_lot_complet())
    brut[scan_corrections.CLE_DOCUMENT] = {
        "schema": scan_corrections.SCHEMA_DE_CORRECTION,
        scan_corrections.CLE_IDENTITES: [entree],
    }
    with pytest.raises(scan_corrections.CorrectionInvalide):
        scan_corrections.lire_les_identites(brut)


def test_une_planche_a_ZERO_frame_est_refusee():
    with pytest.raises(scan_corrections.CorrectionInvalide):
        scan_corrections.IdentiteManuelle(
            read_rank=0, lot_id="lot", template_id="tpl", frames_per_page=0,
            page_index=0, first_frame_timecode="a", last_frame_timecode="b")


def test_un_numero_de_planche_NEGATIF_est_refuse():
    with pytest.raises(scan_corrections.CorrectionInvalide):
        scan_corrections.IdentiteManuelle(
            read_rank=0, lot_id="lot", template_id="tpl", frames_per_page=2,
            page_index=-1, first_frame_timecode="a", last_frame_timecode="b")


def test_le_numero_de_planche_ZERO_est_ACCEPTE():
    """La frontiere exacte, et elle mord : le depot numerote ses planches **a
    partir de zero** (`scan_detect.ORIGINE_DES_PAGE_INDEX`). Un plancher pose a
    « strictement positif » refuserait la premiere planche de tout lot.
    """
    identite = scan_corrections.IdentiteManuelle(
        read_rank=0, lot_id="lot", template_id="tpl", frames_per_page=2,
        page_index=0, first_frame_timecode="a", last_frame_timecode="b")
    assert identite.page_index == 0


def test_deux_identites_pour_la_MEME_planche_sont_refusees_A_LA_LECTURE():
    entree = deux_identites_saisies()[1].as_document()
    brut = dict(fs.document_du_lot_complet())
    brut[scan_corrections.CLE_DOCUMENT] = {
        "schema": scan_corrections.SCHEMA_DE_CORRECTION,
        scan_corrections.CLE_IDENTITES: [entree, dict(entree)],
    }
    with pytest.raises(scan_corrections.CorrectionInvalide):
        scan_corrections.lire_les_identites(brut)


def test_deux_identites_pour_la_MEME_planche_sont_refusees_A_L_ECRITURE():
    """La garde du cote ECRITURE -- celui que la GUI appelle.

    Regle des fabriques : **trois** identites distinguables, et le doublon n'est
    ni en premiere ni en deuxieme position.
    """
    premiere, seconde = deux_identites_saisies()
    doublon = scan_corrections.IdentiteManuelle(
        read_rank=seconde.read_rank, lot_id="lot-gamma",
        template_id="tpl-a4-portrait-1f-v1", frames_per_page=1, page_index=9,
        first_frame_timecode="03:00:00:00", last_frame_timecode="03:00:00:00")
    assert doublon != seconde

    with pytest.raises(scan_corrections.CorrectionInvalide) as refus:
        scan_corrections.poser_les_identites(
            fs.document_du_lot_complet(), (premiere, seconde, doublon))
    assert str(seconde.read_rank) in str(refus.value)


def test_les_identites_sortent_TRIEES_par_rang_de_lecture():
    """Deux ecritures des memes identites rendent le meme texte, comme partout
    ailleurs dans ce depot -- sans quoi un document jamais retouche changerait
    d'octets d'une session a l'autre.
    """
    premiere, seconde = deux_identites_saisies()
    dans_un_sens = scan_corrections.poser_les_identites(
        fs.document_du_lot_complet(), (seconde, premiere))
    dans_l_autre = scan_corrections.poser_les_identites(
        fs.document_du_lot_complet(), (premiere, seconde))
    assert dans_un_sens == dans_l_autre
    rangs = [entree["read_rank"] for entree
             in dans_un_sens[scan_corrections.CLE_DOCUMENT][
                 scan_corrections.CLE_IDENTITES]]
    assert rangs == [0, 3]
