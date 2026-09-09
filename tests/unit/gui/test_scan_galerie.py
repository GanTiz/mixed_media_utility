# -*- coding: utf-8 -*-
"""Story 7.4, AC 4 et AC 6 -- la galerie, ses trous, et la vue vignette unique.

« Les trous se voient et gardent leur place. » Et **aucune image de frame
n'est fabriquee** : les images legeres de la detection sont une dependance
nommee non livree, et recadrer le raster de page pour simuler une vignette
creerait une seconde source pour la meme frame -- ce que le produit a refuse
le 2026-08-17.
"""

import ast
import json
from pathlib import Path

from PySide6.QtCore import Qt

import fabriques_detection as fab
from mixed_media_utility.gui import scan_jugement, catalogue, chutier, jetons
from mixed_media_utility.gui import lecture_detection as lecture
from mixed_media_utility.gui import modele_chutier

_PAQUET_GUI = Path(jetons.__file__).resolve().parent

#: Le document **REEL** ecrit par `scan detect` : une planche lue proprement
#: (`page_index: 0`, quatre zones **sans** frame -- rien n'est ecrit avant la
#: story d'ecriture) et une feuille blanche refusee, sans numero de planche.
#: C'est sur lui que la double derivation de la completude a ete mesuree
#: divergente le 2026-08-25.
_DOCUMENT_REEL = (
    Path(__file__).resolve().parents[2]
    / "fixtures" / "detection-scan-reelle" / "detect-ok-et-refus.json"
)


def _galerie(qtbot, document):
    galerie = scan_jugement.VueGalerie(catalogue.CHAINES)
    qtbot.addWidget(galerie)
    galerie.resize(1200, 900)
    galerie.show()
    galerie.poser(document)
    return galerie


def _zone_avec_frame(slot, rang, index, *, largeur, hauteur, synthetique=None,
                     chemin="frames/f.tiff"):
    return fab.zone(
        slot, rang, index, largeur_px=largeur, hauteur_px=hauteur,
        frame_path_relative=chemin, synthetic=synthetique,
        synthetic_reason="FRAME_MANQUANTE" if synthetique else None,
    )


# ---------------------------------------------------------------------------
# AC 4 -- les pages, leur ordre, leurs trous
# ---------------------------------------------------------------------------


def test_le_trou_d_une_planche_absente_garde_SA_PLACE(qtbot):
    """Trois planches d'index 0, 2 et 3 sur un cardinal de 4 : la 1 manque.

    **0-based**, comme tout ce que le depot produit (`EPIC7-ARB-73`) : la
    fixture de cette famille etait 1-based jusqu'au 2026-08-25, ce qui rendait
    la protection de ses mutants illusoire (finding F11). Le trou vise n'est
    ni le premier ni le dernier index : un calcul qui prendrait un bord se
    verrait.
    """
    pages = [
        fab.page(1, 0, page_count=4),
        fab.page(2, 2, page_count=4),
        fab.page(3, 3, page_count=4),
    ]
    document = lecture.depuis_json(fab.document(pages))
    assert scan_jugement.planches_manquantes(document) == (1,)
    galerie = _galerie(qtbot, document)
    assert galerie.suite_rendue == (
        ("page", (1, 0)),
        ("trou", 1),
        ("page", (2, 2)),
        ("page", (3, 3)),
    )
    # Les suivantes ne sont PAS decalees : elles gardent leur rang relatif.
    presentes = [
        entree for entree in galerie.suite_rendue if entree[0] == "page"
    ]
    assert presentes == [("page", (1, 0)), ("page", (2, 2)), ("page", (3, 3))]
    assert len(galerie.trous) == 1
    assert galerie.trous[0].page_index == 1
    assert galerie.trous[0].etat == scan_jugement.CASE_ABSENTE


def test_le_trou_de_la_PREMIERE_planche_d_un_lot_0_based_est_AFFICHE(qtbot):
    """Finding F11 : la planche ``0`` manque, et c'est elle que l'ecran doit dire.

    Le cas le plus courant du terrain -- la premiere feuille du lot reste dans
    le bac -- et le seul que l'heuristique d'origine (`0 if 0 in presents else
    1`) ne pouvait pas voir : sans planche ``0`` presente, elle DEDUISAIT un
    lot 1-based, nommait manquante la planche ``3`` (qui n'existe pas dans un
    lot de trois numerote de 0 a 2) et n'affichait **aucun** trou pour la
    planche ``0``, la seule qui manque reellement.

    Ce test rougit contre le code d'avant le correctif F1, sur les deux
    assertions a la fois : la liste des manquantes ET la place du trou.
    """
    document = lecture.depuis_json(fab.lot_0_based_premiere_planche_absente())
    assert scan_jugement.planches_manquantes(document) == (0,)
    galerie = _galerie(qtbot, document)
    # Le trou est EN TETE parce que la planche 0 est celle qui manque -- et
    # les deux planches presentes sortent par numero, pas par ordre de scan.
    assert galerie.suite_rendue == (
        ("trou", 0),
        ("page", (1, 1)),
        ("page", (2, 2)),
    )
    assert [trou.page_index for trou in galerie.trous] == [0]
    # Et aucune planche inexistante n'est nommee : un lot de trois planches
    # 0-based va de 0 a 2, jamais jusqu'a 3.
    assert scan_jugement.planches_manquantes(document) != (
        fab.LOT_0_BASED_CARDINAL,)


def test_la_galerie_affiche_par_NUMERO_DE_PLANCHE_et_le_trou_garde_sa_place(qtbot):
    """`EPIC7-ARB-76` : l'operatrice raisonne en planches, pas en ordre de scan.

    La mesure qui a produit l'arbitrage, transposee ici : un lot de trois
    planches dont la **1** manque, **scanne a l'envers** -- la planche 2 est
    passee la premiere sous le scanner, la planche 0 ensuite. Le coeur
    (`scan_detect.pages_du_lot`) range le document par ``read_rank``, et c'est
    son contrat ; la galerie, elle, affiche par ``page_index``.

    Avant le correctif, la liste rendue etait ``['[trou 1]', 'planche 2',
    'planche 0']`` : le trou pose **en tete**, c'est-a-dire l'inverse exact de
    la promesse « chaque trou garde sa place ».
    """
    a_l_envers = [
        fab.page(1, 2, page_count=3),
        fab.page(2, 0, page_count=3, zones=fab.deux_zones(2, 0, premier_slot=2)),
    ]
    galerie = _galerie(qtbot, lecture.depuis_json(fab.document(a_l_envers)))
    assert galerie.suite_rendue == (
        ("page", (2, 0)),
        ("trou", 1),
        ("page", (1, 2)),
    )
    # Le `read_rank` n'est pas perdu pour autant : chaque case le porte
    # toujours, c'est le premier membre de son adresse.
    assert [ligne.page.adresse for ligne in galerie.lignes] == [(2, 0), (1, 2)]

    # Volet symetrique, et il est le coeur de l'arbitrage : la MEME pile posee
    # dans l'ordre des planches rend EXACTEMENT la meme galerie. L'ordre du
    # document ne se lit plus a l'ecran.
    a_l_endroit = [a_l_envers[1], a_l_envers[0]]
    rendu_a_l_endroit = _galerie(
        qtbot, lecture.depuis_json(fab.document(a_l_endroit))
    ).suite_rendue
    assert rendu_a_l_endroit == galerie.suite_rendue


def test_une_planche_sans_numero_passe_APRES_celles_qui_en_ont_un(qtbot):
    """Le tri par planche ne peut pas ranger ce qui n'a pas de numero.

    Une page dont le QR n'a rien livre n'a pas de place dans la suite des
    planches : elle va en queue, et le trou de la planche absente se pose
    **parmi les numerotees**, jamais derriere elle.
    """
    pages = [
        fab.page(1, None, page_count=3, qr_status="no_symbol_detected",
                 identite=False, template_source="manifest"),
        fab.page(2, 0, page_count=3),
    ]
    galerie = _galerie(qtbot, lecture.depuis_json(fab.document(pages)))
    assert galerie.suite_rendue == (
        ("page", (2, 0)),
        ("trou", 1),
        ("trou", 2),
        ("page", (1, None)),
    )


def test_les_quatre_emplacements_prennent_leur_etat_NOMINATIVEMENT(qtbot):
    """Le TROISIEME porte la mire, le QUATRIEME est absent -- par index.

    Une fabrique uniforme rendrait toute permutation invisible : les quatre
    emplacements ont ici quatre geometries differentes et trois etats
    differents.
    """
    rang, index = 2, 1
    zones = [
        _zone_avec_frame(0, rang, index, largeur=1337, hauteur=752,
                         synthetique=False, chemin="frames/f0.tiff"),
        _zone_avec_frame(1, rang, index, largeur=1401, hauteur=799,
                         synthetique=False, chemin="frames/f1.tiff"),
        _zone_avec_frame(2, rang, index, largeur=1455, hauteur=805,
                         synthetique=True, chemin="frames/f2.tiff"),
        fab.zone(3, rang, index, largeur_px=1522, hauteur_px=811),
    ]
    pages = [fab.page(1, 0, page_count=2), fab.page(rang, index, page_count=2,
                                                    zones=zones)]
    galerie = _galerie(qtbot, lecture.depuis_json(fab.document(pages)))
    ligne = next(
        ligne for ligne in galerie.lignes if ligne.page.adresse == (rang, index)
    )
    etats = {case.slot_index: case.etat for case in ligne.cases}
    assert etats == {
        0: scan_jugement.CASE_PRESENTE,
        1: scan_jugement.CASE_PRESENTE,
        2: scan_jugement.CASE_MIRE,
        3: scan_jugement.CASE_ABSENTE,
    }
    jetons_de_bordure = {case.slot_index: case.jeton_bordure for case in ligne.cases}
    assert jetons_de_bordure[2] == "state-substitute"
    assert jetons_de_bordure[3] == "state-absent"
    # Les deux premieres ne sont NI l'un NI l'autre.
    assert jetons_de_bordure[0] not in ("state-substitute", "state-absent")
    assert jetons_de_bordure[1] not in ("state-substitute", "state-absent")
    # Et la mire n'est jamais confondue avec une frame complete.
    assert jetons_de_bordure[2] != jetons_de_bordure[0]


def test_le_badge_de_completude_distingue_complet_de_complet_avec_mires(qtbot):
    """Lot **0-based** de deux planches, toutes deux presentes : rien ne manque.

    La fixture etait 1-based (planches 1 et 2 d'un lot de deux) jusqu'au
    2026-08-25 : une fois la completude derivee **une seule fois** et en base
    zero (`EPIC7-ARB-73`), un tel lot est incomplet -- il lui manque la
    planche 0. Ce qui distingue les deux verdicts mesures ici est la MIRE,
    et elle seule.
    """
    rang, index = 2, 1

    def document(avec_mire):
        zones = [
            _zone_avec_frame(0, rang, index, largeur=1337, hauteur=752,
                             synthetique=False, chemin="frames/f0.tiff"),
            _zone_avec_frame(1, rang, index, largeur=1401, hauteur=799,
                             synthetique=bool(avec_mire),
                             chemin="frames/f1.tiff"),
        ]
        autres = [
            _zone_avec_frame(0, 1, 0, largeur=1300, hauteur=700,
                             synthetique=False, chemin="frames/g0.tiff"),
            _zone_avec_frame(1, 1, 0, largeur=1310, hauteur=710,
                             synthetique=False, chemin="frames/g1.tiff"),
        ]
        return lecture.depuis_json(fab.document([
            fab.page(1, 0, page_count=2, zones=autres),
            fab.page(rang, index, page_count=2, zones=zones),
        ]))

    complet = document(False)
    assert scan_jugement.planches_manquantes(complet) == ()
    assert (
        scan_jugement.badge_de_completude_des_planches(complet)
        == modele_chutier.BADGE_COMPLET
    )
    avec_mires = document(True)
    assert (
        scan_jugement.badge_de_completude_des_planches(avec_mires)
        == modele_chutier.BADGE_COMPLET_AVEC_MIRES
    )
    assert (
        scan_jugement.badge_de_completude_des_planches(avec_mires)
        != modele_chutier.BADGE_COMPLET
    )
    galerie = _galerie(qtbot, avec_mires)
    assert galerie.badge.etat == modele_chutier.BADGE_COMPLET_AVEC_MIRES


def test_les_DEUX_surfaces_rendent_LE_MEME_verdict_sur_le_document_REEL(qtbot):
    """Finding F1 / `EPIC7-ARB-73`, mesure a la source du probleme.

    Le 2026-08-25, sur ce fichier-la, `modele_chutier._completude_du_document`
    rendait ``('complet', ())`` pendant que la surface du jugement rendait
    ``incomplet`` : meme document, meme session, meme lot, deux verdicts.

    Trois raisons, et ce test les mesure toutes les trois d'un coup :

    * le cardinal attendu (``counters.pages_expected`` vaut 1 ici) n'a plus
      qu'une source ;
    * la planche presente porte ``page_index: 0`` -- l'origine est zero, pas
      une heuristique ;
    * **aucune** zone ne porte de ``frame_path_relative`` a l'etape
      `detected`, et la page refusee n'a **aucune** zone : ce que la
      completude mesure ici, ce sont **les planches du lot**, pas les frames.
      Exiger les frames rendait le badge constant a ``incomplet``.
    """
    assert _DOCUMENT_REEL.is_file(), _DOCUMENT_REEL
    brut = json.loads(_DOCUMENT_REEL.read_text(encoding="utf-8"))
    document = lecture.depuis_json(brut)

    # Le volet qui donne son sens au reste : ce document ne porte aucune frame
    # et sa page refusee aucune zone. Sans lui, ce test pourrait passer sur un
    # document reconstruit, qui n'est pas ce que la chaine produit aujourd'hui.
    assert all(
        zone.frame_path_relative is None
        for page in document.pages for zone in page.page.frame_zones
    )
    assert any(not page.page.frame_zones for page in document.pages)

    badge = scan_jugement.badge_de_completude_des_planches(document)
    assert (badge, scan_jugement.planches_manquantes(document)) == (
        modele_chutier._completude_du_document([document.previz]))
    assert badge == modele_chutier.BADGE_COMPLET
    galerie = _galerie(qtbot, document)
    assert galerie.badge.etat == badge
    # La page refusee n'a pas de numero de planche : elle sort en queue, et
    # elle ne creuse aucun trou -- le lot n'attend qu'une planche.
    assert galerie.suite_rendue == (("page", (0, 0)), ("page", (1, None)))
    assert galerie.trous == []


def test_le_badge_et_le_glyphe_sont_DEUX_CONTROLES_DISTINCTS(qtbot):
    """Les deux familles de signes ne se fondent jamais en un signe unique.

    Le badge repond a « que manque-t-il dans ce lot ? » ; le glyphe a « que
    dois-je faire de cet objet ? ». Le second releve d'``EPIC7-ARB-5``, le
    premier **non** (correction de `DESIGN.md` du 2026-08-23, section 1.4).
    """
    pages = [
        fab.page(1, 0, page_count=2),
        # Planche dont le QR n'a pas livre son index : elle n'est rattachee
        # a rien, donc elle porte le GLYPHE -- jamais un badge.
        fab.page(2, None, page_count=2, qr_status="no_symbol_detected",
                 identite=False, template_source="manifest"),
    ]
    galerie = _galerie(qtbot, lecture.depuis_json(fab.document(pages)))
    badges = galerie.findChildren(chutier.BadgeDeCompletude)
    glyphes = galerie.findChildren(chutier.GlypheDeRattachement)
    assert len(badges) == 1
    assert len(glyphes) == 1
    assert badges[0] is not glyphes[0]
    assert type(badges[0]) is not type(glyphes[0])
    assert badges[0].objectName() == "badge-state"
    assert glyphes[0].objectName() == "state-glyph"
    # Le vocabulaire de chaque famille lui reste : « incomplet » est legitime
    # ici, dans les DEUX familles, et le grep de l'AC 1 ne les balaye pas.
    assert modele_chutier.BADGE_INCOMPLET in modele_chutier.BADGES_DE_COMPLETUDE
    assert modele_chutier.GLYPHE_INCOMPLET in modele_chutier.GLYPHES_DE_RATTACHEMENT


def test_aucune_case_ne_fabrique_d_image_de_frame(qtbot):
    document = lecture.depuis_json(fab.deux_pages_cible_seconde())
    galerie = _galerie(qtbot, document)
    for ligne in galerie.lignes:
        for case in ligne.cases:
            # La vignette est un CADRE vide : rien qui ressemble a une image.
            assert case.vignette.layout() is None
            assert case.vignette.findChildren(object) == []
            # Sa legende est SOUS elle, hors de l'image.
            indice_vignette = case.layout().indexOf(case.vignette)
            indice_legende = case.layout().indexOf(case.legende)
            assert indice_legende > indice_vignette
            assert case.legende.parent() is case
            assert case.legende.parent() is not case.vignette


def test_la_legende_d_une_case_est_en_typographie_data_sm(qtbot):
    document = lecture.depuis_json(fab.deux_pages_cible_seconde())
    galerie = _galerie(qtbot, document)
    case = galerie.lignes[0].cases[0]
    taille = jetons.TYPOGRAPHIE["data-sm"]["taille"]
    assert f"font-size: {taille}px" in case.legende.taille.styleSheet()


def test_le_zoom_de_vignettes_est_continu_et_au_dessus_de_la_scene(qtbot):
    document = lecture.depuis_json(fab.deux_pages_cible_seconde())
    galerie = _galerie(qtbot, document)
    assert galerie.zoom_vignettes.pageStep() == 1
    assert galerie.zoom_vignettes.tickPosition().name == "NoTicks"
    # Au-dessus de la scene : il est dans l'en-tete, pas dans le defilement.
    assert galerie.zoom_vignettes.parent() is galerie
    assert galerie.zoom_vignettes not in galerie.defilement.findChildren(
        type(galerie.zoom_vignettes)
    )


def test_zero_lecture_d_image_de_frame_et_zero_recadrage_du_raster():
    """Grep de frontiere de l'AC 4, sur les modules de la galerie."""
    interdits = (
        "imread", "QPixmap(", "QImageReader", "frame_path_relative)",
        ".copy(QRect", "copy(x", "cropped", "setClipRect",
    )
    for nom in ("scan_jugement.py", "surimpressions.py"):
        source = (_PAQUET_GUI / nom).read_text(encoding="utf-8")
        arbre = ast.parse(source)
        appels = {
            noeud.func.attr if isinstance(noeud.func, ast.Attribute)
            else getattr(noeud.func, "id", "")
            for noeud in ast.walk(arbre) if isinstance(noeud, ast.Call)
        }
        assert "imread" not in appels, nom
        assert "cropped" not in appels, nom
        assert "setClipRect" not in appels, nom
        # `frame_path_relative` est LU (pour connaitre l'etat d'une case),
        # jamais ouvert : aucun `open` ni `Path(...)` ne le suit.
        assert "open" not in appels, nom
    for interdit in ("QImageReader", "imread"):
        assert interdit not in (
            _PAQUET_GUI / "scan_jugement.py"
        ).read_text(encoding="utf-8"), interdit


# ---------------------------------------------------------------------------
# AC 6 -- la vue vignette unique
# ---------------------------------------------------------------------------


def _atelier_avec_trois_vignettes(qtbot):
    rang, index = 2, 1
    zones = [
        fab.zone(0, rang, index, largeur_px=1337, hauteur_px=752),
        fab.zone(1, rang, index, largeur_px=1401, hauteur_px=799),
        fab.zone(2, rang, index, largeur_px=1522, hauteur_px=811),
    ]
    document = lecture.depuis_json(fab.document([
        fab.page(1, 0, page_count=2),
        fab.page(rang, index, page_count=2, zones=zones),
    ]))
    atelier = scan_jugement.AtelierScanJugement(catalogue.CHAINES)
    qtbot.addWidget(atelier)
    atelier.resize(1200, 900)
    atelier.show()
    atelier.poser_document(document)
    return atelier, document, (rang, index)


def test_un_clic_sur_la_SECONDE_vignette_ouvre_CETTE_frame_la(qtbot):
    atelier, _document, adresse = _atelier_avec_trois_vignettes(qtbot)
    ligne = next(
        ligne for ligne in atelier.vue_galerie.lignes if ligne.page.adresse == adresse
    )
    assert len(ligne.cases) == 3
    seconde = ligne.cases[1]
    qtbot.mouseClick(seconde, Qt.MouseButton.LeftButton)
    assert atelier.vue_frame.adresse == (adresse[0], adresse[1], 1), (
        "le clic n'a pas ouvert la SECONDE vignette -- un rendu qui prendrait "
        "toujours la premiere ne se demasque pas autrement"
    )
    assert atelier.vue_frame.zone.slot_index == 1
    # Plein panneau : c'est une vue a part entiere, pas un agrandissement de
    # la grille -- elle est la vue courante de la pile.
    assert atelier.pile.currentWidget() is atelier.vue_frame
    # Et elle a son propre zoom dedans.
    assert atelier.vue_frame.barre_de_vue is not atelier.vue_galerie.barre_de_vue


def test_le_panneau_lateral_de_la_vue_vignette_s_ouvre_deja_RETRACTE(qtbot):
    atelier, _document, adresse = _atelier_avec_trois_vignettes(qtbot)
    assert atelier.vue_frame.panneau_lateral.est_retracte
    atelier.ouvrir_la_frame((adresse[0], adresse[1], 1))
    assert atelier.vue_frame.panneau_lateral.est_retracte
    # Sa poignee de rappel est la : retracte n'est pas absent.
    assert atelier.vue_frame.panneau_lateral.poignee.isVisibleTo(
        atelier.vue_frame
    )
    # La galerie, elle, s'ouvre DEPLIEE : l'etat est par vue.
    assert not atelier.vue_galerie.panneau_lateral.est_retracte


def test_l_etat_retracte_est_memorise_PAR_VUE_et_jamais_globalement(qtbot):
    atelier, _document, adresse = _atelier_avec_trois_vignettes(qtbot)
    rang, index = adresse
    atelier.ouvrir_la_frame((rang, index, 1))
    # L'operateur deplie le panneau de la vue vignette.
    atelier.vue_frame.panneau_lateral.deplier()
    assert not atelier.vue_frame.panneau_lateral.est_retracte
    # Il revient a la galerie, dont l'etat n'a pas bouge.
    atelier.onglets.activer("galerie")
    assert not atelier.vue_galerie.panneau_lateral.est_retracte
    atelier.vue_galerie.panneau_lateral.retracter()
    # Il rouvre une AUTRE frame : la vue vignette garde SON etat...
    atelier.ouvrir_la_frame((rang, index, 2))
    assert atelier.vue_frame.adresse == (rang, index, 2)
    assert not atelier.vue_frame.panneau_lateral.est_retracte
    # ... et celui de la galerie n'a pas ete modifie par ce geste.
    assert atelier.vue_galerie.panneau_lateral.est_retracte
    # Les trois panneaux sont trois objets distincts : partager l'objet
    # partagerait l'etat, ce qu'`EPIC7-ARB-25` refuse.
    panneaux = {
        id(vue.panneau_lateral) for vue in atelier.vues.values()
    }
    assert len(panneaux) == 3
