# -*- coding: utf-8 -*-
"""`EPIC11-ARB-266` -- le parcours CALIBRATION refuse une pile mixte.

Tranche par Egan le 2026-09-07, apres une mesure de terrain : `calibrate` sur
une pile portant la mire **et** quatre planches reelles consignait le profil,
n'ecrivait aucune frame, et declarait le dossier de scan **entier** -- si bien
que les quatre planches perdaient leur mention « non declare » a l'inventaire.
C'est l'erreur qui coute le plus cher des deux : elle **cache** un oubli reel
au lieu d'en inventer un.

Le parcours `scan`, lui, refusait deja cette pile (`EPIC5-ARB-86`, deux passes
separees). Les deux parcours tiennent desormais la meme regle.

**Ce que ce refus n'interdit PAS, et c'est ce que la derniere frontiere
mesure.** Le tri en vrac de la story 5.24 -- `scan` SANS `--lot-slug` --
accepte une pile mixte **par construction** : il route la page de calibration
hors de la pile avant toute lecture d'identite, range chaque planche dans le
lot que son QR declare, plusieurs lots compris, puis consigne le profil. La
garde est donc posee dans `calibrer_la_chaine` et **pas** dans
`consigner_le_profil_de_chaine`, qui est le corps que le vrac appelle. La
poser plus bas casserait exactement le parcours qui fait bien ce que ce refus
interdit de faire mal.

REGLE DES FABRIQUES. La pile de reference porte **quatre** planches
distinguables -- quatre lots differents, quatre rangs de lecture --, plus la
mire, et la mire est placee tantot en TETE, tantot au MILIEU, tantot en QUEUE.
Un balayage tronque d'un bord laisserait une planche non comptee, et le
cardinal annonce a l'operateur serait faux.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "src"))

from mixed_media_utility import scan_calibrate
from mixed_media_utility.io import reconstruction


# ---------------------------------------------------------------------------
# Fabriques
# ---------------------------------------------------------------------------

def _planche(lot: str) -> dict:
    """Une planche d'images : elle porte TOUS les champs de niveau lot.

    C'est la partition du depot (`io.reconstruction`) et non une ressemblance :
    une page est une planche parce qu'elle declare un lot, jamais parce que son
    nom y ressemble.
    """
    # Les ONZE champs de niveau lot, **lus de la table** plutot que tapes : une
    # liste recopiee ici perdrait un champ le jour ou la table en gagne un, et
    # la fabrique fabriquerait alors une page de calibration en croyant faire
    # une planche -- le banc passerait au vert en mesurant l'inverse.
    page = {champ: f"{champ}-de-{lot}"
            for champ in reconstruction._LOT_LEVEL_FIELDS}
    page.update({"lot_id": lot, "page_index": 1})
    return page


def _mire() -> dict:
    """La page de calibration : elle ne porte AUCUN champ de niveau lot.

    Depuis 5.23 (AC 8ter) elle sert une chaine de scan, pas un lot -- c'est
    exactement ce qui la rend reconnaissable sans lui inventer un role.
    """
    return {"schema_version": 2, "scan_chain_label": "epson-v850",
            "page_index": 0}


class _Page:
    def __init__(self, read_rank: int, payload: dict | None):
        self.read_rank = read_rank
        self.payload = payload


class _Detection:
    def __init__(self, payloads):
        self.pages = tuple(_Page(rang, p) for rang, p in enumerate(payloads, 1))


class _Journal:
    def __init__(self):
        self.erreurs: list[str] = []

    def error(self, message, *args):
        self.erreurs.append(message % args if args else message)

    def info(self, *args, **kwargs):
        pass


#: Les QUATRE lots distinguables de la pile de reference.
LOTS = ["a-premier_25", "m-milieu_12p5", "s-suivant_8", "z-dernier_50"]


def _pile_mixte(position_de_la_mire: int) -> list[dict]:
    """La pile de reference, la mire posee **a la position demandee**."""
    pages = [_planche(lot) for lot in LOTS]
    pages.insert(position_de_la_mire, _mire())
    return pages


# ---------------------------------------------------------------------------
# Le refus
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("position", [
    pytest.param(0, id="mire-en-TETE"),
    pytest.param(2, id="mire-au-MILIEU"),
    pytest.param(4, id="mire-en-QUEUE"),
])
def test_une_pile_MIXTE_est_refusee_ou_que_soit_la_mire(position):
    """Le refus ne depend pas de l'ordre dans lequel l'operateur a empile.

    L'operateur empile ses feuilles comme il veut -- c'est ce que le depot dit
    deja du rang de lecture. Une garde qui ne verrait la mire qu'en premiere
    position laisserait passer les deux autres regimes, et ce sont ceux-la que
    le chargeur automatique produit.
    """
    journal = _Journal()
    with pytest.raises(scan_calibrate.RefusDeCalibration) as leve:
        scan_calibrate._refuser_une_pile_mixte(
            _Detection(_pile_mixte(position)), journal)

    assert leve.value.motif == scan_calibrate.REFUS_PILE_MIXTE_EN_CALIBRATION
    assert journal.erreurs, "un refus se prononce au journal (`EPIC11-ARB-258`)"


def test_le_refus_COMPTE_les_planches_et_les_compte_TOUTES():
    """Le cardinal annonce est celui des planches, mire exclue.

    Quatre planches et une mire : un balayage tronque d'un bord annoncerait
    trois, et l'operateur chercherait une feuille qu'il a pourtant scannee.
    """
    with pytest.raises(scan_calibrate.RefusDeCalibration) as leve:
        scan_calibrate._refuser_une_pile_mixte(_Detection(_pile_mixte(2)))

    assert "4 planche(s)" in str(leve.value), str(leve.value)


def test_le_refus_NOMME_LES_DEUX_ISSUES():
    """`EPIC11-ARB-89` : jamais un blocage sec.

    Un refus qui nommerait seulement le probleme laisserait l'operateur devant
    une pile qu'il vient de scanner sans savoir quoi en faire. Les deux issues
    existent et sont a une commande : la mire seule, ou le tri en vrac.
    """
    with pytest.raises(scan_calibrate.RefusDeCalibration) as leve:
        scan_calibrate._refuser_une_pile_mixte(_Detection(_pile_mixte(0)))

    message = str(leve.value)
    assert "SEULE" in message, message
    assert "--lot-slug" in message, message


# ---------------------------------------------------------------------------
# Ce qui NE declenche PAS le refus
# ---------------------------------------------------------------------------

def test_une_pile_de_MIRE_SEULE_passe():
    """Le regime nominal d'Egan -- celui qu'il a joue hier -- reste intact."""
    scan_calibrate._refuser_une_pile_mixte(_Detection([_mire()]))


def test_une_pile_de_DEUX_MIRES_passe_ce_refus_la():
    """Deux mires ne sont pas une pile mixte, et le refus suivant s'en charge.

    `_fit_lot_correction` refuse deja un lot a deux pages de calibration
    (« un lot porte UNE page de calibration »). Refuser ici aussi nommerait le
    mauvais probleme -- l'operateur lirait « vos planches » devant une pile qui
    n'en porte aucune.
    """
    scan_calibrate._refuser_une_pile_mixte(_Detection([_mire(), _mire()]))


def test_une_pile_de_PLANCHES_SEULES_passe_ce_refus_la():
    """**MIXTE veut dire les DEUX**, et ce test est ce qui l'etablit.

    Trouve par `test_scan_write_noyau.py` a la course de cloture du
    2026-09-07, sur la premiere redaction de cette garde : elle mordait sur
    « il y a des planches » et non sur « il y a des planches ET une mire ».
    Une pile de planches seules y lisait donc « cette pile porte une page de
    calibration ET 3 planches » -- une phrase fausse de la moitie de ce qu'elle
    affirme, devant un operateur qui a simplement oublie sa mire.

    Le refus qui la nomme existe deja, plus bas et plus precis : « aucune page
    de calibration lue dans ce scan ». Celui-ci doit la laisser passer.
    """
    scan_calibrate._refuser_une_pile_mixte(
        _Detection([_planche(lot) for lot in LOTS]))


def test_une_page_MUETTE_ne_compte_pour_aucune_planche():
    """Un QR qui n'a rien livre n'est pas une identite de lot.

    C'est la meme lecon que la condition 0 de `_bascule_en_calibration_demandee`
    du parcours `scan` : une feuille muette est une planche dont on ignore
    l'identite, pas une page absente -- mais elle ne peut pas non plus servir a
    affirmer qu'il y a une planche, puisque rien ne l'a dit.
    """
    scan_calibrate._refuser_une_pile_mixte(_Detection([_mire(), None]))


# ---------------------------------------------------------------------------
# Frontieres NEGATIVES
# ---------------------------------------------------------------------------

def test_la_garde_n_est_PAS_dans_le_corps_que_le_VRAC_appelle():
    """La frontiere la plus importante de ce lot.

    Le tri en vrac de la 5.24 appelle `consigner_le_profil_de_chaine` sur une
    pile mixte **par construction**. Poser la garde la casserait le parcours
    qui fait bien exactement ce que ce refus interdit de faire mal -- et aucun
    test positif de ce fichier ne le verrait : ils passent tous par
    `_refuser_une_pile_mixte` directement.
    """
    corps = inspect.getsource(scan_calibrate.consigner_le_profil_de_chaine)
    assert "_refuser_une_pile_mixte" not in corps, (
        "la garde de pile mixte a migre dans le corps que le tri en vrac "
        "appelle : le vrac refuserait desormais la pile qu'il sait trier")

    entree = inspect.getsource(scan_calibrate.calibrer_la_chaine)
    assert "_refuser_une_pile_mixte" in entree, (
        "le parcours calibration ne refuse plus la pile mixte")


def test_la_partition_n_est_pas_RECRITE_ici():
    """Une seconde redaction serait deux verites sur la meme pile.

    C'est le motif pour lequel `EPIC5-ARB-92` avait extrait la partition. Ce
    module doit la LIRE de `io.reconstruction`, jamais recomposer une liste de
    champs de niveau lot -- l'une des deux mordrait un jour sur ce que l'autre
    accepte, et le symptome serait un parcours qui refuse ce que l'autre range.
    """
    corps = inspect.getsource(scan_calibrate._refuser_une_pile_mixte)
    assert "planches_d_images_de_la_pile" in corps, corps
    for champ in ("lot_id", "project_id", "rush_id"):
        assert champ not in corps, (
            f"`{champ}` est lu a la main ici : la partition est recopiee")


def test_le_predicat_public_rend_la_MEME_partition_que_le_refus_de_scan():
    """Les deux parcours voient la meme pile, et c'est mesure.

    `pile_sans_planche_d_images` decide le refus de `scan` ;
    `planches_d_images_de_la_pile` decide celui de `calibrate`. Les deux
    doivent s'accorder sur toute pile, sans quoi l'un mord ou l'autre laisse
    passer.
    """
    # Les cinq regimes, avec ce que CHACUN doit rendre. Une table plutot qu'un
    # `if` : la premiere redaction de ce test comparait les deux predicats par
    # une condition dont une branche etait tautologique (`all(... for _ in ())`
    # vaut `True`), donc elle ne mesurait rien sur la moitie des cas.
    attendu = [
        ([_mire()],                        0, True),
        (_pile_mixte(0),                   4, False),
        (_pile_mixte(4),                   4, False),
        ([_planche(lot) for lot in LOTS],  4, False),
        ([],                               0, False),
    ]
    for pile, cardinal, sans_planche in attendu:
        assert len(reconstruction.planches_d_images_de_la_pile(
            pile)) == cardinal, pile
        assert reconstruction.pile_sans_planche_d_images(
            pile) is sans_planche, pile

    # **L'accord des deux, dit comme une implication et non comme un exemple** :
    # « aucune planche vue » doit valoir de chaque cote. Le sens inverse n'est
    # PAS vrai, et c'est voulu -- une pile de planches SEULES n'a aucune page
    # sans identite, donc `pile_sans_planche_d_images` y rend `False` sans que
    # ce soit une pile mixte. C'est exactement pourquoi `calibrate` a besoin du
    # cardinal et ne pouvait pas se contenter du booleen.
    for pile, _, _ in attendu:
        if reconstruction.pile_sans_planche_d_images(pile):
            assert reconstruction.planches_d_images_de_la_pile(pile) == []
