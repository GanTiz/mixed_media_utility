# -*- coding: utf-8 -*-
"""Story 7.2, AC 6 -- l'arbre nu d'abord.

Pas de menu contextuel (il arrive en 7.11 avec son inventaire,
`EPIC7-ARB-37`), pas de dossiers d'organisation (E7 a mesure qu'ils n'ont
**nulle part ou etre ecrits** -- aucun support au `project.json`), pas de
filtre (`bin-filters` viendra avec le besoin, `EPIC7-ARB-4`). Egalement hors
perimetre, portes par le chemin du scan : la file « En attente de lecture »,
le bouton Detecter, la section Calibration (7.3+), le mode vignette.

Ces tests mesurent des **absences**. Chacun a donc son symetrique, ou une
assertion qui prouve que le balayage porte sur quelque chose : « un test peut
etre vert et vide » est un motif que ce depot a deja paye.
"""

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMenu

import fabriques_chutier as fab
from mixed_media_utility.gui import catalogue, jetons
from mixed_media_utility.gui import chutier as module_chutier
from mixed_media_utility.gui import modele_chutier as modele
from mixed_media_utility.gui.coquille import Coquille

#: Les modules de production que cette story pose.
_MODULES_DE_LA_STORY = ("chutier.py", "modele_chutier.py")

#: Les cles de catalogue qui appartiennent a CETTE surface.
_PREFIXES_DE_LA_SURFACE = ("chutier-", "badge-", "glyphe-", "cardinal-", "action-")


def _sources_de_la_story():
    paquet = Path(module_chutier.__file__).resolve().parent
    sources = [paquet / nom for nom in _MODULES_DE_LA_STORY]
    for source in sources:
        assert source.exists(), source
    return sources


def _chaines_de_la_surface():
    chaines = {
        cle: valeur
        for cle, valeur in catalogue.CHAINES.items()
        if cle.startswith(_PREFIXES_DE_LA_SURFACE)
    }
    # Le balayage porte sur quelque chose : sans cette garde, un renommage de
    # prefixe rendrait tous les tests de frontiere verts et vides.
    assert len(chaines) > 20, chaines
    return chaines


@pytest.fixture
def coquille(qtbot):
    fenetre = Coquille()
    qtbot.addWidget(fenetre)
    fenetre.show()
    qtbot.waitExposed(fenetre)
    fenetre.resize(jetons.ESPACEMENTS["queue-overlay-threshold"], 800)
    qtbot.wait(20)
    fenetre.poser_projet(
        fab.manifest_six_types(),
        documents_de_detection=[fab.detection_de_lot_alpha_1()],
        existe=fab.liaison_factice(["medias/alpha.mov", "medias/beta.mov"]),
    )
    return fenetre


# ---------------------------------------------------------------------------
# Pas de menu contextuel : il arrive en 7.11 avec son inventaire.
# ---------------------------------------------------------------------------


#: Les chemins par lesquels un menu contextuel pourrait exister. La POLITIQUE
#: `NoContextMenu` n'est pas dans cette liste : elle est la garde, pas le
#: symptome.
_CHEMINS_DE_MENU = (
    "QMenu",
    "contextMenuEvent",
    "customContextMenuRequested",
    "ActionsContextMenu",
    "addAction(",
)


def test_aucun_menu_contextuel_dans_les_modules_de_la_story():
    fautifs = {}
    for source in _sources_de_la_story():
        texte = source.read_text(encoding="utf-8")
        trouves = [motif for motif in _CHEMINS_DE_MENU if motif in texte]
        if trouves:
            fautifs[source.name] = trouves
    assert fautifs == {}, f"menu contextuel cable : {fautifs}"


def test_la_frontiere_du_menu_contextuel_mord_vraiment():
    # Symetrique : le balayage attrape bien un menu s'il y en avait un.
    fautif = "menu = QMenu(self)\nmenu.addAction(action)"
    assert [motif for motif in _CHEMINS_DE_MENU if motif in fautif]


def test_les_deux_arbres_refusent_explicitement_le_menu_contextuel(coquille):
    for arbre in (coquille.arbre_arborescence, coquille.chutier.arbre):
        assert arbre.contextMenuPolicy() == Qt.ContextMenuPolicy.NoContextMenu


def test_le_clic_droit_sur_une_ligne_ne_declenche_rien(qtbot, coquille):
    arbre = coquille.arbre_arborescence
    arbre.expandAll()
    qtbot.wait(10)
    element = arbre.element("lot-alpha-1")
    rectangle = arbre.visualItemRect(element)
    atelier_avant = coquille.atelier_actif()
    designation_avant = coquille.designation()

    qtbot.mouseClick(
        arbre.viewport(), Qt.MouseButton.RightButton, pos=rectangle.center()
    )
    qtbot.wait(20)

    # Assertion EXPLICITE, pas un comportement par defaut non teste :
    # aucun menu n'est apparu, rien n'a navigue, rien n'a ete designe.
    assert coquille.findChildren(QMenu) == []
    assert coquille.atelier_actif() == atelier_avant
    assert coquille.designation() == designation_avant


# ---------------------------------------------------------------------------
# Pas de filtre, pas de dossiers d'organisation, pas de zone tampon.
# ---------------------------------------------------------------------------


#: Ce que l'AC 6 nomme comme hors perimetre. Les mots sont cherches dans les
#: LIBELLES de la surface -- ce que l'operatrice lirait --, pas dans les
#: commentaires du code, qui ont le droit de nommer ce qui viendra.
_HORS_PERIMETRE = (
    "filtre",
    "filtrer",
    "dossier",
    "en attente de lecture",
    "détecter",
    "detecter",
    "calibration",
    "vignette",
)


def test_aucune_chaine_hors_perimetre_au_catalogue_de_cette_surface():
    fautifs = {}
    for cle, valeur in _chaines_de_la_surface().items():
        trouves = [mot for mot in _HORS_PERIMETRE if mot in valeur.lower()]
        if trouves:
            fautifs[cle] = trouves
    assert fautifs == {}, f"chaine hors perimetre : {fautifs}"


def test_la_frontiere_du_hors_perimetre_mord_vraiment():
    fautif = "Filtrer les dossiers de la Calibration".lower()
    assert [mot for mot in _HORS_PERIMETRE if mot in fautif]


def test_le_chutier_ne_porte_ni_barre_de_filtres_ni_zone_tampon(coquille):
    # L'inventaire des enfants directs du chutier : un en-tete, un bouton
    # plein ecran, un arbre. Rien d'autre -- l'arbre nu.
    chutier = coquille.chutier
    assert chutier.arbre.parent() is chutier
    assert not hasattr(chutier, "barre_filtres")
    assert not hasattr(chutier, "zone_tampon")
    assert not hasattr(chutier, "bouton_detecter")
    assert not hasattr(chutier, "section_calibration")


# ---------------------------------------------------------------------------
# Les dossiers d'organisation restent possibles -- rien ici ne les empeche.
# ---------------------------------------------------------------------------


def test_le_modele_ne_suppose_pas_que_tout_noeud_vient_du_manifest():
    # E7 : les dossiers d'organisation n'ont nulle part ou etre ecrits
    # aujourd'hui, mais « rien ici ne doit rendre leur venue impossible ».
    # La preuve mesurable : le modele porte deja un noeud qui ne vient PAS du
    # manifest -- la branche reconstruite depuis un scan seul.
    racines = modele.construire_arbre(
        fab.manifest_deux_lots_meme_rush(),
        documents_de_detection=[
            fab.document_de_detection(
                lot_id="lot-venu-du-scan",
                rush_id="rush-gamma",
                pages=[
                    fab.page_detectee(
                        0, 0, lot_id="lot-venu-du-scan", rush_id="rush-gamma"
                    ),
                    fab.page_detectee(
                        1,
                        1,
                        lot_id="lot-venu-du-scan",
                        rush_id="rush-gamma",
                        largeur_px=195,
                    ),
                ],
                pages_expected=2,
                empreinte=fab.EMPREINTES[1],
            )
        ],
        existe=fab.liaison_factice(["medias/alpha.mov"]),
    )
    hors_manifest = [
        noeud
        for noeud in modele.parcourir(racines)
        if noeud.detail.get("vient_du_manifest") is False
    ]
    assert hors_manifest, "aucun noeud hors manifest : la frontiere ne mesure rien"
    # Et son symetrique : les noeuds du manifest se declarent, eux aussi.
    du_manifest = [
        noeud
        for noeud in modele.parcourir(racines)
        if noeud.detail.get("vient_du_manifest") is True
    ]
    assert du_manifest


def test_le_modele_ne_fabrique_aucune_seconde_hierarchie_par_type(coquille):
    # « Aucun dossier automatique par type » (`EPIC7-ARB-4`) : sous un rush,
    # on trouve des lots -- jamais un noeud groupeur invente.
    rush = modele.noeud_par_identifiant(coquille.racines(), "rush-alpha")
    for enfant in rush.enfants:
        assert enfant.type in (modele.TYPE_LOT, modele.TYPE_LOT_RECONSTRUIT)
        assert enfant.detail["rush_id"] == "rush-alpha"


# ---------------------------------------------------------------------------
# Aucune ecriture : le chutier lit, il ne modifie rien.
# ---------------------------------------------------------------------------


def test_les_modules_de_la_story_n_ecrivent_rien():
    ecritures = ("open(", "write_text", "write_bytes", ".write(", "mkdir", "os.replace")
    fautifs = {}
    for source in _sources_de_la_story():
        texte = source.read_text(encoding="utf-8")
        trouves = [motif for motif in ecritures if motif in texte]
        if trouves:
            fautifs[source.name] = trouves
    assert fautifs == {}, f"ecriture dans un module du chutier : {fautifs}"


def test_la_frontiere_d_ecriture_mord_vraiment():
    ecritures = ("open(", "write_text", "write_bytes", ".write(", "mkdir", "os.replace")
    fautif = "chemin.write_text(contenu)"
    assert [motif for motif in ecritures if motif in fautif]


def test_le_modele_ne_mute_jamais_le_manifest_qu_on_lui_donne():
    # Corollaire mesure de « aucune ecriture » : la source rendue apres
    # construction est identique, cle par cle.
    import copy

    manifest = fab.manifest_deux_lots_meme_rush()
    temoin = copy.deepcopy(manifest)
    document = fab.document_de_detection(
        lot_id="lot-cadence-24",
        pages=[
            fab.page_detectee(0, 1, lot_id="lot-cadence-24", largeur_px=115),
            fab.page_detectee(1, 0, lot_id="lot-cadence-24", largeur_px=125),
        ],
        pages_expected=2,
    )
    temoin_document = copy.deepcopy(document)
    modele.construire_arbre(
        manifest,
        documents_de_detection=[document],
        existe=fab.liaison_factice(["medias/alpha.mov"]),
    )
    assert manifest == temoin
    assert document == temoin_document
