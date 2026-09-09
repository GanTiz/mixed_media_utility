# -*- coding: utf-8 -*-
"""Story 7.2, AC 1 -- le chutier a deux panneaux.

On designe a gauche, on lit a droite (`EPIC7-ARB-40`). La geometrie chiffree
appartient au module de jetons : ce fichier n'ecrit **aucune** largeur, il
les lit -- c'est aussi ce que la frontiere negative de l'AC mesure sur le
code de production.

La mecanique de poignee, le rail, le repli automatique sous
`tree-collapse-threshold` et la memoire du choix explicite sont poses par le
socle 7.0 et mesures par `test_coquille.py` : ces tests-ci **verifient
l'existant** la ou il existe et n'ajoutent que ce que 7.2 pose -- portee du
chutier, plein ecran, rail par-dessus le chutier, stabilite au changement
d'atelier.
"""

import re
from pathlib import Path

import pytest

from PySide6.QtWidgets import QHeaderView

import fabriques_chutier as fab
from mixed_media_utility.gui import chutier as module_chutier
from mixed_media_utility.gui import jetons
from mixed_media_utility.gui.coquille import Coquille


@pytest.fixture
def coquille(qtbot):
    fenetre = Coquille()
    qtbot.addWidget(fenetre)
    fenetre.show()
    qtbot.waitExposed(fenetre)
    fenetre.poser_projet(
        fab.manifest_deux_rushes_deux_lots_chacun(),
        existe=fab.liaison_factice(["medias/alpha.mov", "medias/beta.mov"]),
    )
    return fenetre


def _attendre_layout(qtbot, fenetre):
    qtbot.waitUntil(lambda: fenetre.width() > 0, timeout=2000)
    qtbot.wait(20)


# ---------------------------------------------------------------------------
# On designe a gauche, on lit a droite.
# ---------------------------------------------------------------------------


def test_designer_un_noeud_met_son_contenu_dans_le_chutier(qtbot, coquille):
    # Cible en SECONDE position : le second rush, pas le premier.
    coquille.designer("rush-beta")
    qtbot.wait(10)
    identifiants = coquille.chutier.arbre.identifiants_racines()
    assert identifiants == ["lot-beta-1", "lot-beta-2"]
    # Aucun lot du premier rush n'entre dans la portee.
    assert "lot-alpha-1" not in identifiants


def test_l_entete_du_chutier_porte_la_portee_et_son_cardinal(qtbot, coquille):
    coquille.designer("rush-beta")
    qtbot.wait(10)
    texte = coquille.chutier.entete.text()
    assert "rush-beta" in texte
    assert "2 lots" in texte
    # Le cardinal accorde : un seul enfant donne un singulier.
    coquille.designer("lot-beta-2")
    qtbot.wait(10)
    assert "lot" in coquille.chutier.entete.text()


def test_le_chutier_reste_un_arbre_on_y_deplie(qtbot, coquille):
    # Le panneau fixe la portee, il ne remplace pas la filiation : le contenu
    # du chutier porte les descendants, pas seulement les enfants directs.
    document = fab.document_de_detection(
        lot_id="lot-beta-2",
        rush_id="rush-beta",
        pages=[
            fab.page_detectee(0, 1, lot_id="lot-beta-2", rush_id="rush-beta"),
            fab.page_detectee(
                1, 0, lot_id="lot-beta-2", rush_id="rush-beta", largeur_px=190
            ),
        ],
        pages_expected=2,
    )
    coquille.poser_projet(
        fab.manifest_deux_rushes_deux_lots_chacun(),
        documents_de_detection=[document],
        existe=fab.liaison_factice(["medias/alpha.mov", "medias/beta.mov"]),
    )
    coquille.designer("rush-beta")
    qtbot.wait(10)
    element = coquille.chutier.arbre.element("lot-beta-2")
    assert element is not None
    assert element.childCount() == 2


def test_le_panneau_d_arborescence_ne_porte_ni_badge_ni_compteur(qtbot, coquille):
    # DESIGN.md : le panneau gauche sert a se placer, pas a lire -- aucun
    # compteur, aucune puce de selection, aucun badge.
    arbre = coquille.arbre_arborescence
    assert arbre.montre_les_signes is False
    element = arbre.element("rush-beta")
    assert element is not None
    assert element.text(0).strip() == "rush-beta"


# ---------------------------------------------------------------------------
# Plein ecran du chutier : la scene est masquee, la barre d'onglets reste.
# ---------------------------------------------------------------------------


def test_le_plein_ecran_du_chutier_masque_la_scene_et_garde_la_barre(qtbot, coquille):
    """`EPIC7-ARB-86` : il masque la SCENE, et rien d'autre.

    Ce test exigeait l'inverse jusqu'au 2026-08-27 -- que l'arborescence se
    replie sur son rail. Egan, second essai de terrain : « Utiliser le bouton
    de plein ecran sur le chutier passe l'arborescence en mode reduit par
    defaut. Il faut qu'il reste dans l'etat ou il etait avant le clic. »
    """
    e = jetons.ESPACEMENTS
    coquille.resize(e["queue-overlay-threshold"], 800)
    _attendre_layout(qtbot, coquille)
    avant = coquille.splitter.sizes()
    assert coquille.scene.isVisible()
    assert not coquille.panneau_arborescence.est_repliee

    coquille.basculer_plein_ecran_chutier()
    _attendre_layout(qtbot, coquille)
    assert coquille.plein_ecran_chutier_actif
    assert not coquille.scene.isVisible()
    # L'arborescence garde son etat, la barre d'onglets RESTE.
    assert not coquille.panneau_arborescence.est_repliee
    assert coquille.barre_onglets.isVisible()
    assert coquille.chutier.isVisible()

    coquille.basculer_plein_ecran_chutier()
    _attendre_layout(qtbot, coquille)
    assert not coquille.plein_ecran_chutier_actif
    assert coquille.scene.isVisible()
    assert not coquille.panneau_arborescence.est_repliee
    # La geometrie anterieure est rendue, valeur pour valeur.
    assert coquille.splitter.sizes() == avant


def test_le_plein_ecran_garde_AUSSI_une_arborescence_deja_repliee(qtbot, coquille):
    """Volet symetrique : « l'etat ou il etait » vaut dans les deux sens.

    Sans ce cas, une implementation qui DEPLIERAIT systematiquement
    passerait le test precedent -- c'est le meme defaut, retourne.
    """
    e = jetons.ESPACEMENTS
    coquille.resize(e["queue-overlay-threshold"], 800)
    _attendre_layout(qtbot, coquille)
    coquille.replier_arborescence()
    _attendre_layout(qtbot, coquille)
    assert coquille.panneau_arborescence.est_repliee

    coquille.basculer_plein_ecran_chutier()
    _attendre_layout(qtbot, coquille)
    assert coquille.panneau_arborescence.est_repliee

    coquille.basculer_plein_ecran_chutier()
    _attendre_layout(qtbot, coquille)
    assert coquille.panneau_arborescence.est_repliee


def test_le_bouton_de_l_entete_bascule_le_plein_ecran(qtbot, coquille):
    e = jetons.ESPACEMENTS
    coquille.resize(e["queue-overlay-threshold"], 800)
    _attendre_layout(qtbot, coquille)
    from PySide6.QtCore import Qt

    qtbot.mouseClick(coquille.chutier.bouton_plein_ecran, Qt.MouseButton.LeftButton)
    qtbot.wait(10)
    assert coquille.plein_ecran_chutier_actif
    qtbot.mouseClick(coquille.chutier.bouton_plein_ecran, Qt.MouseButton.LeftButton)
    qtbot.wait(10)
    assert not coquille.plein_ecran_chutier_actif


def test_le_seuil_ne_reprend_pas_la_main_pendant_le_plein_ecran(qtbot, coquille):
    """Le plein ecran est un choix explicite : un redimensionnement ne le defait pas.

    Depuis `EPIC7-ARB-86` le plein ecran ne touche plus a l'arborescence, donc
    ce que ce cas mesure n'est plus « elle reste repliee » mais « l'etat qu'elle
    avait n'est change ni par le plein ecran ni par le franchissement du
    seuil ». On la replie DELIBEREMENT avant, pour que le seuil ait quelque
    chose a defaire s'il reprenait la main.
    """
    e = jetons.ESPACEMENTS
    coquille.resize(e["tree-collapse-threshold"] + 200, 800)
    _attendre_layout(qtbot, coquille)
    coquille.replier_arborescence()
    coquille.basculer_plein_ecran_chutier()
    coquille.resize(e["tree-collapse-threshold"] + 300, 800)
    _attendre_layout(qtbot, coquille)
    assert coquille.panneau_arborescence.est_repliee
    assert coquille.plein_ecran_chutier_actif


# ---------------------------------------------------------------------------
# Le rail rouvre l'arborescence PAR-DESSUS le chutier : l'un ou l'autre,
# jamais rien (`EPIC7-ARB-40`).
# ---------------------------------------------------------------------------


def test_le_rail_rouvre_l_arborescence_par_dessus_le_chutier(qtbot, coquille):
    e = jetons.ESPACEMENTS
    # A la largeur minimale, ouvrir en place mordrait le plancher de la
    # scene : c'est precisement la ou le chutier passe avant l'arborescence.
    coquille.resize(e["window-min-width"], e["window-min-height"])
    _attendre_layout(qtbot, coquille)
    assert coquille.panneau_arborescence.est_repliee

    coquille.rouvrir_arborescence_depuis_le_rail()
    _attendre_layout(qtbot, coquille)
    assert coquille.survol_arborescence_actif
    # L'arbre est DANS la superposition, pas dans le panneau : l'un ou
    # l'autre, jamais rien -- et jamais les deux.
    assert coquille.arbre_arborescence.isVisible()
    assert coquille.superposition_arborescence.isVisible()
    assert coquille.arbre_arborescence.parent() is coquille.superposition_arborescence
    # La superposition couvre le chutier, elle ne le pousse pas.
    assert coquille.chutier.width() >= e["bin-min-width"]
    assert coquille.scene.width() >= e["stage-min-width"]

    # « Le temps de se placer » : designer referme la superposition. On
    # retombe sur le RAIL -- jamais sur rien : le bouton de reouverture est
    # la et reste actionnable.
    coquille.designer("rush-beta")
    qtbot.wait(10)
    assert not coquille.survol_arborescence_actif
    assert not coquille.superposition_arborescence.isVisible()
    assert coquille.arbre_arborescence.parent() is not (
        coquille.superposition_arborescence
    )
    assert coquille.panneau_arborescence.est_repliee
    assert coquille.panneau_arborescence.bouton_rouvrir.isVisible()
    assert coquille.panneau_arborescence.bouton_rouvrir.isEnabled()
    # Le placement a bien eu lieu : la portee du chutier a suivi.
    assert coquille.chutier.arbre.identifiants_racines() == [
        "lot-beta-1",
        "lot-beta-2",
    ]


def test_au_dessus_du_plancher_le_rail_rouvre_en_place(qtbot, coquille):
    # Quand la place existe, le rail rouvre le panneau EN PLACE (chemin du
    # socle 7.0) : la superposition ne sert qu'a l'etroit.
    e = jetons.ESPACEMENTS
    coquille.resize(e["queue-overlay-threshold"], 800)
    _attendre_layout(qtbot, coquille)
    coquille.replier_arborescence()
    qtbot.wait(10)
    assert coquille.panneau_arborescence.est_repliee

    coquille.rouvrir_arborescence_depuis_le_rail()
    _attendre_layout(qtbot, coquille)
    assert not coquille.survol_arborescence_actif
    assert not coquille.panneau_arborescence.est_repliee


def test_le_repli_referme_la_superposition(qtbot, coquille):
    e = jetons.ESPACEMENTS
    coquille.resize(e["window-min-width"], e["window-min-height"])
    _attendre_layout(qtbot, coquille)
    coquille.rouvrir_arborescence_depuis_le_rail()
    _attendre_layout(qtbot, coquille)
    assert coquille.survol_arborescence_actif

    coquille.replier_arborescence()
    qtbot.wait(10)
    assert not coquille.survol_arborescence_actif
    # Jamais rien : le rail reste actionnable.
    assert coquille.panneau_arborescence.bouton_rouvrir.isEnabled()


# ---------------------------------------------------------------------------
# Memorisation : les largeurs et l'etat de retractation valent pour les
# quatre ateliers.
# ---------------------------------------------------------------------------


def test_l_etat_retracte_et_les_largeurs_survivent_a_deux_changements_d_atelier(
    qtbot, coquille
):
    e = jetons.ESPACEMENTS
    coquille.resize(e["queue-overlay-threshold"], 800)
    _attendre_layout(qtbot, coquille)
    coquille.splitter.setSizes(
        [e["tree-panel-width"] + 40, e["bin-width"] + 25, 100000]
    )
    qtbot.wait(10)
    coquille.replier_arborescence()
    qtbot.wait(10)
    largeurs = coquille.largeurs_panneaux()

    for indice in (2, 0, 3):
        coquille.activer_atelier(indice)
        qtbot.wait(10)
        # Assertion sur les VALEURS, pas sur l'absence d'erreur.
        assert coquille.largeurs_panneaux() == largeurs, indice
        assert coquille.panneau_arborescence.est_repliee


# ---------------------------------------------------------------------------
# Frontiere negative de l'AC 1 : aucune largeur en dur dans le code de cette
# story -- les valeurs viennent du module de jetons.
# ---------------------------------------------------------------------------


#: Les modules de production que cette story pose ou modifie.
_MODULES_DE_LA_STORY = ("chutier.py", "modele_chutier.py", "coquille.py")

#: Les valeurs de geometrie que `DESIGN.md` fixe et que le code doit LIRE.
_LARGEURS_INTERDITES = ("160", "250", "330", "640", "1180")


def _sources_de_la_story():
    paquet = Path(module_chutier.__file__).resolve().parent
    return [paquet / nom for nom in _MODULES_DE_LA_STORY]


def test_aucune_largeur_de_design_en_dur_dans_le_code_du_chutier():
    fautifs = {}
    for source in _sources_de_la_story():
        texte = source.read_text(encoding="utf-8")
        trouves = [
            valeur
            for valeur in _LARGEURS_INTERDITES
            if re.search(rf"(?<![\w.]){valeur}(?![\w.])", texte)
        ]
        if trouves:
            fautifs[source.name] = trouves
    assert fautifs == {}, f"largeur de DESIGN.md en dur : {fautifs}"


def test_la_frontiere_des_largeurs_mord_vraiment():
    # Symetrique : le motif attrape bien un litteral s'il y en avait un, et
    # ne se declenche pas sur une sous-chaine anodine.
    motif = rf"(?<![\w.]){_LARGEURS_INTERDITES[0]}(?![\w.])"
    assert re.search(motif, "largeur = 160")
    assert re.search(motif, "setMinimumWidth(160)")
    assert not re.search(motif, "identifiant = 'lot-1600'")
    assert not re.search(motif, "valeur = 3160")


# ---------------------------------------------------------------------------
# Correctifs de la revue de vague 2
# ---------------------------------------------------------------------------


def test_la_colonne_du_libelle_prend_toute_la_place_restante(coquille):
    """Les six niveaux d'`EPIC7-ARB-9` doivent rester LISIBLES.

    Trouve par capture de l'interface reelle a la revue de vague 2 : sans
    mode de redimensionnement explicite, Qt donne a chacune des trois
    colonnes sa largeur de section par defaut (~100 px). Avec l'indentation
    qui croit a chaque niveau, la colonne du libelle tombait a quelques
    pixels des le niveau planche -- l'arbre affichait « Pla... », « Fi... »,
    et le chutier, « la piece la plus sollicitee de l'application », ne
    montrait plus aucun nom. Aucun test ne pouvait le voir : tous
    interrogent `element.text(0)` et le modele, jamais la largeur rendue.
    """
    for arbre in (coquille.arbre_arborescence, coquille.chutier.arbre):
        entete = arbre.header()
        assert entete.sectionResizeMode(
            module_chutier.COLONNE_LIBELLE
        ) == QHeaderView.ResizeMode.Stretch
        assert not entete.stretchLastSection()
    # Les deux colonnes de SIGNES n'existent que la ou des signes se posent
    # (`EPIC7-ARB-94` (a), 2026-08-27) : le panneau d'arborescence n'en a
    # aucune -- vides, elles lui prenaient leur largeur de section minimale et
    # coupaient les noms en « rus... ». Le mode de redimensionnement des deux
    # colonnes reste donc mesure, mais sur l'arbre qui les porte.
    entete = coquille.chutier.arbre.header()
    for colonne in (module_chutier.COLONNE_BADGE, module_chutier.COLONNE_GLYPHE):
        assert entete.sectionResizeMode(
            colonne
        ) == QHeaderView.ResizeMode.ResizeToContents
    assert coquille.arbre_arborescence.columnCount() == (
        module_chutier.NOMBRE_DE_COLONNES_SANS_SIGNES
    )


def test_le_libelle_occupe_l_essentiel_de_la_largeur_de_l_arbre(coquille):
    """Volet mesure du precedent : une largeur, pas seulement un mode.

    Le mode `Stretch` est le moyen ; ce qui compte est le resultat. Sans le
    correctif, la colonne 0 valait la section par defaut de Qt quelle que
    soit la largeur de l'arbre -- donc ce test rougit sur le code d'avant
    des que l'arbre est plus large que trois sections par defaut.
    """
    arbre = coquille.chutier.arbre
    arbre.resize(400, 300)
    largeur_utile = arbre.viewport().width()
    largeur_libelle = arbre.header().sectionSize(module_chutier.COLONNE_LIBELLE)
    assert largeur_libelle > largeur_utile // 2, (
        f"colonne du libelle {largeur_libelle} px pour un arbre de "
        f"{largeur_utile} px : les noms seront tronques"
    )


def test_le_rail_pendant_le_plein_ecran_ouvre_par_dessus_jamais_en_place(coquille):
    """Deux exclusivites composees ne doivent pas produire un troisieme etat.

    Trouve par la couche 2 de la revue de vague 2, reproduit a l'execution.
    Sans garde, le rail depliait le panneau EN PLACE tandis que
    `_plein_ecran_chutier` restait vrai et que la scene restait masquee : un
    etat qu'aucun des deux mecanismes ne decrit, et dont la sortie de plein
    ecran restaurait une geometrie qui n'avait plus de sens.

    La reponse vient de la spine : « le rail rouvre l'arborescence
    PAR-DESSUS le chutier, le temps de se placer » (`EPIC7-ARB-40`).
    Ouvrir en place volerait au chutier la bande que le plein ecran vient
    de lui donner.

    **Ce qui a change le 2026-08-27, et pourquoi ce cas survit.** Le plein
    ecran repliait alors TOUJOURS l'arborescence, si bien que l'etat fautif
    s'atteignait par le seul plein ecran. `EPIC7-ARB-86` lui retire ce geste
    -- mais l'etat, lui, reste parfaitement atteignable : replier a la main,
    PUIS passer en plein ecran. Le cas se met donc en place en deux gestes au
    lieu d'un, et la garde reste exactement aussi necessaire.
    """
    # Fenetre LARGE : au-dessus du plancher d'ouverture en place, donc sans
    # la garde le regime « en place » serait choisi. C'est le seul regime ou
    # le defaut mord.
    coquille.resize(1500, 900)
    coquille.replier_arborescence()
    coquille.basculer_plein_ecran_chutier()
    assert coquille.plein_ecran_chutier_actif
    assert coquille.panneau_arborescence.est_repliee
    assert not coquille.scene.isVisible()

    coquille.rouvrir_arborescence_depuis_le_rail()

    assert coquille.survol_arborescence_actif, (
        "en plein ecran, le rail doit ouvrir PAR-DESSUS le chutier"
    )
    assert coquille.plein_ecran_chutier_actif, (
        "le geste du rail ne doit pas sortir du plein ecran a la derobee"
    )
    assert coquille.panneau_arborescence.est_repliee, (
        "le panneau ne se deplie pas EN PLACE pendant le plein ecran"
    )
    assert not coquille.scene.isVisible(), (
        "la scene reste masquee : le plein ecran est intact"
    )


def test_hors_plein_ecran_le_rail_ouvre_toujours_en_place_quand_la_place_existe(coquille):
    """Volet symetrique : la garde ne doit PAS changer le regime nominal.

    Sans ce test, la garde ci-dessus serait satisfaite par un code qui
    ouvrirait TOUJOURS par-dessus -- ce qui casserait le rail du socle 7.0.
    """
    coquille.resize(1500, 900)
    coquille.replier_arborescence()
    coquille.rouvrir_arborescence_depuis_le_rail()

    assert not coquille.survol_arborescence_actif
    assert not coquille.panneau_arborescence.est_repliee


# ---------------------------------------------------------------------------
# La GEOMETRIE du plein ecran (revue du 2026-08-27, `EPIC7-ARB-86`)
#
# « Le plein ecran masque la SCENE, et rien d'autre » se mesurait jusqu'ici
# sur ce qui est VISIBLE. Il se mesure ici sur les LARGEURS, et c'est la que
# l'invariant tombait : masquer un enfant ne dit pas a `QSplitter` a qui
# revient sa bande, et il la coupait en deux.
# ---------------------------------------------------------------------------


def test_le_plein_ecran_ne_prend_pas_au_panneau_sa_largeur(qtbot, coquille):
    """Le panneau garde SA largeur ; le chutier absorbe toute la bande.

    Defaut mesure avant correctif sur une fenetre de 1600 : `[196, 330, 1064]`
    devenait `[798, 797, 0]` -- le panneau d'arborescence passait a la moitie
    de la fenetre au moment precis ou l'operatrice demande le chutier en grand.
    """
    coquille.resize(1600, 900)
    _attendre_layout(qtbot, coquille)
    avant = coquille.splitter.sizes()
    assert not coquille.panneau_arborescence.est_repliee

    coquille.basculer_plein_ecran_chutier()
    _attendre_layout(qtbot, coquille)
    pendant = coquille.splitter.sizes()

    assert pendant[0] == avant[0], (
        f"le panneau a change de largeur : {avant[0]} -> {pendant[0]}")
    assert pendant[2] == 0
    # Le chutier a bien recupere la bande, et pas seulement « plus qu'avant » :
    # toute la scene, plus la poignee qui disparait avec elle.
    assert pendant[1] == avant[1] + avant[2] + jetons.ESPACEMENTS["splitter-width"]


def test_la_largeur_memorisee_du_panneau_ne_derive_pas_avec_le_plein_ecran(
    qtbot, coquille
):
    """Six allers-retours avec repli ne changent RIEN a la largeur rendue.

    Defaut mesure avant correctif, sur la meme boucle : 196, 201, 206, 211,
    216, 226 -- cinq pixels par tour, la largeur d'une poignee, sans borne.
    La derive n'etait pas seulement visuelle : `_memoriser_la_largeur_ouverte`
    la retenait comme si l'operatrice avait tire la poignee.
    """
    coquille.resize(1600, 900)
    _attendre_layout(qtbot, coquille)
    reference = coquille.splitter.sizes()

    releves = []
    for _ in range(6):
        coquille.basculer_plein_ecran_chutier()
        _attendre_layout(qtbot, coquille)
        coquille.replier_arborescence()
        _attendre_layout(qtbot, coquille)
        coquille.basculer_plein_ecran_chutier()
        _attendre_layout(qtbot, coquille)
        coquille.deplier_arborescence()
        _attendre_layout(qtbot, coquille)
        releves.append(coquille.splitter.sizes())

    assert releves == [reference] * 6, (
        f"la largeur du panneau derive au fil des allers-retours : {releves}")


def test_un_repli_pendant_le_plein_ecran_rend_sa_bande_au_chutier(qtbot, coquille):
    """Replier en plein ecran donne les pixels liberes au CHUTIER.

    Test de CARACTERISATION, et c'est son objet : il fixe l'hypothese sur
    laquelle repose l'absence d'aiguillage dans `_recoller_la_poignee` --
    `QSplitter` borne un enfant invisible a zero et redistribue au visible,
    donc rendre l'ecart a la scene masquee revient a le rendre au chutier. Un
    aiguillage explicite a ete ecrit pour ce cas puis retire faute de mesure
    qui le distingue ; si Qt changeait d'avis, c'est ici que cela se verrait,
    et il faudrait alors le remettre.
    """
    e = jetons.ESPACEMENTS
    coquille.resize(1600, 900)
    _attendre_layout(qtbot, coquille)
    coquille.basculer_plein_ecran_chutier()
    _attendre_layout(qtbot, coquille)
    avant = coquille.splitter.sizes()

    coquille.replier_arborescence()
    _attendre_layout(qtbot, coquille)
    apres = coquille.splitter.sizes()

    assert apres[0] == e["tree-panel-rail"]
    assert apres[2] == 0
    assert apres[1] == avant[1] + (avant[0] - e["tree-panel-rail"])


def test_sortir_du_plein_ecran_recolle_la_poignee_sur_un_panneau_replie(
    qtbot, coquille
):
    """Le rail reste actionnable en plein ecran (`EPIC7-ARB-93`) : la geometrie
    rendue a la sortie est donc celle d'AVANT, et elle peut ne plus decrire
    l'etat du panneau.

    Defaut mesure avant correctif : sortie avec `[196, 330, 1064]` alors que le
    panneau etait un rail de 42 -- cent cinquante pixels de vide entre le rail
    et le chutier, ce que le retour de terrain appelle « recoller la poignee
    manuellement ».
    """
    e = jetons.ESPACEMENTS
    coquille.resize(1600, 900)
    _attendre_layout(qtbot, coquille)
    coquille.basculer_plein_ecran_chutier()
    _attendre_layout(qtbot, coquille)
    coquille.replier_arborescence()
    _attendre_layout(qtbot, coquille)

    coquille.basculer_plein_ecran_chutier()
    _attendre_layout(qtbot, coquille)

    assert coquille.panneau_arborescence.est_repliee
    assert coquille.splitter.sizes()[0] == e["tree-panel-rail"]


# ---------------------------------------------------------------------------
# `EPIC7-ARB-84` -- SEUL le panneau de gauche fixe la portee du chutier
#
# L'AC ajoutee le 2026-08-27 prescrit cette mesure ; elle n'avait pas ete
# ecrite. Motif du defaut : les deux arbres etaient cables sur le meme
# `Coquille.designer`, donc un clic dans le chutier le rabattait sur les
# enfants de la ligne cliquee -- la fratrie et les parents disparaissaient
# sous le doigt de l'operatrice. Egan : « le panneau de droite du chutier est
# cense conserver son arborescence complete au niveau choisi sur le panneau de
# gauche. »
# ---------------------------------------------------------------------------


def test_un_clic_dans_le_chutier_ne_change_pas_sa_portee(qtbot, coquille):
    """Ce que le chutier montre est INCHANGE, et la ligne cliquee est designee.

    Cible en seconde position des deux cotes -- le second rush a gauche, le
    second de ses lots dans le chutier : un code qui rabattrait la portee sur
    « le premier venu » passerait un test dont la cible est premiere.
    """
    coquille.designer("rush-beta")
    qtbot.wait(10)
    avant = coquille.chutier.arbre.identifiants_racines()
    assert avant == ["lot-beta-1", "lot-beta-2"], avant

    # Le SIGNAL de l'arbre du chutier, pas la methode de la coquille. Le
    # defaut d'origine n'etait pas dans le corps de `designer_dans_le_chutier`
    # -- il etait dans le FIL : les deux arbres etaient cables sur le meme
    # `Coquille.designer`. Un test qui appelle la methode mesure la methode et
    # laisse le cablage libre : recabler `designation_changee` sur `designer`
    # laissait 198 tests verts (mutant N17, revue du 2026-08-27).
    coquille.chutier.arbre.designation_changee.emit("lot-beta-2")
    qtbot.wait(10)

    assert coquille.chutier.arbre.identifiants_racines() == avant
    assert coquille.designation() == "rush-beta", (
        "la PORTEE reste celle que le panneau de gauche a fixee")
    assert coquille.contexte() == "lot-beta-2", (
        "la ligne cliquee devient le contexte : elle est designee, "
        "elle ne redefinit simplement rien")


def test_un_double_clic_dans_le_chutier_ne_change_pas_sa_portee_non_plus(
    qtbot, coquille
):
    """Le pendant exact : sans lui le correctif serait a moitie fait.

    `ouvrir` appelle `designer`, donc un double-clic dans le chutier rabattait
    la portee aussi surement qu'un simple clic -- et c'est le geste qui MENE
    quelque part, donc celui qu'on fait sans regarder le panneau de gauche.
    """
    coquille.designer("rush-beta")
    qtbot.wait(10)
    avant = coquille.chutier.arbre.identifiants_racines()

    # Meme raison : c'est le fil qui est mesure, pas le corps de la methode.
    coquille.chutier.arbre.ouverture_demandee.emit("lot-beta-2")
    qtbot.wait(10)

    assert coquille.chutier.arbre.identifiants_racines() == avant
    assert coquille.designation() == "rush-beta"
    assert coquille.contexte() == "lot-beta-2"


def test_le_panneau_de_gauche_lui_change_bel_et_bien_la_portee(qtbot, coquille):
    """Volet symetrique : les deux tests ci-dessus pourraient etre verts sur
    une portee que PLUS RIEN ne change. Ils ne mesurent quelque chose que
    parce que le geste de gauche, lui, la change."""
    coquille.designer("rush-beta")
    qtbot.wait(10)
    avant = coquille.chutier.arbre.identifiants_racines()

    # Le signal de l'arbre de GAUCHE, celui qui fixe bel et bien la portee.
    coquille.arbre_arborescence.designation_changee.emit("lot-beta-2")
    qtbot.wait(10)

    assert coquille.chutier.arbre.identifiants_racines() != avant
    assert coquille.designation() == "lot-beta-2"


# ---------------------------------------------------------------------------
# `EPIC7-ARB-93`, volet b -- le repli reste ACTIONNABLE dans tous les regimes
#
# Le volet a (fenetre maximisee) est mesure par `test_lancement_application`.
# Le volet b ne l'etait pas, et il n'etait pas tenu : pendant l'ouverture
# par-dessus le chutier, `bouton_replier` restait dans le panneau MASQUE --
# `isEnabled()` vrai, `isVisible()` faux. La seule sortie etait de designer un
# noeud, c'est-a-dire de faire un choix pour pouvoir renoncer a choisir.
# ---------------------------------------------------------------------------


def test_le_bouton_de_repli_est_visible_pendant_l_ouverture_par_dessus(
    qtbot, coquille
):
    e = jetons.ESPACEMENTS
    coquille.resize(e["window-min-width"], e["window-min-height"])
    _attendre_layout(qtbot, coquille)
    coquille.rouvrir_arborescence_depuis_le_rail()
    _attendre_layout(qtbot, coquille)
    assert coquille.survol_arborescence_actif

    bouton = coquille.panneau_arborescence.bouton_replier
    assert bouton.isVisible(), (
        "un bouton actif dans un widget masque n'est pas un geste offert")
    assert bouton.isEnabled()
    # Il est DANS la superposition : un second bouton peint a cote aurait
    # diverge de celui-ci au premier changement d'icone.
    assert bouton.window() is coquille
    assert bouton.parentWidget() is coquille.superposition_arborescence


def test_le_bouton_de_repli_referme_l_ouverture_par_dessus(qtbot, coquille):
    """Et il fait ce qu'il annonce : un clic REEL, pas un appel de methode."""
    from PySide6.QtCore import Qt

    e = jetons.ESPACEMENTS
    coquille.resize(e["window-min-width"], e["window-min-height"])
    _attendre_layout(qtbot, coquille)
    coquille.rouvrir_arborescence_depuis_le_rail()
    _attendre_layout(qtbot, coquille)

    qtbot.mouseClick(
        coquille.panneau_arborescence.bouton_replier, Qt.MouseButton.LeftButton)
    qtbot.wait(20)

    assert not coquille.survol_arborescence_actif
    assert coquille.panneau_arborescence.est_repliee
    # « L'un ou l'autre, jamais rien » : le rail reste offert.
    assert coquille.panneau_arborescence.bouton_rouvrir.isVisible()
    assert coquille.panneau_arborescence.bouton_rouvrir.isEnabled()


def test_le_bouton_de_repli_revient_a_son_entete_apres_l_ouverture_par_dessus(
    qtbot, coquille
):
    """Le panneau PRETE son bouton, il ne le donne pas.

    Sans le retour, rouvrir le panneau en place montrait un en-tete sans
    bouton de repli : l'ouverture par-dessus aurait emporte definitivement un
    geste du regime normal.
    """
    e = jetons.ESPACEMENTS
    coquille.resize(e["window-min-width"], e["window-min-height"])
    _attendre_layout(qtbot, coquille)
    coquille.rouvrir_arborescence_depuis_le_rail()
    _attendre_layout(qtbot, coquille)
    coquille.fermer_survol_arborescence()
    coquille.resize(e["tree-collapse-threshold"] + 300, 800)
    coquille.deplier_arborescence()
    _attendre_layout(qtbot, coquille)

    bouton = coquille.panneau_arborescence.bouton_replier
    assert not coquille.panneau_arborescence.est_repliee
    assert bouton.isVisible()
    assert bouton.parentWidget() is not coquille.superposition_arborescence
    # Et il marche encore : le va-et-vient n'a pas debranche le signal.
    bouton.click()
    qtbot.wait(20)
    assert coquille.panneau_arborescence.est_repliee


# ---------------------------------------------------------------------------
# `EPIC7-ARB-99` -- « l'arborescence varie sans logique apparente »
#
# Egan, second essai de terrain, apres clarification : « ce qu'il y a sous un
# objet donne varie quand je change l'objet selectionne ». Deux causes
# mesurees, toutes deux dans le RENDU -- le modele, lui, est coherent.
# ---------------------------------------------------------------------------


def _lignes_visibles(arbre):
    """Les identifiants que l'oeil voit : deplies jusqu'a la racine.

    C'est la seule mesure qui parle du retour d'Egan. Compter les elements de
    l'arbre compterait aussi ceux qu'un parent replie cache -- et c'est
    precisement ce que le defaut faisait.
    """
    from PySide6.QtWidgets import QTreeWidgetItemIterator

    visibles = []
    iterateur = QTreeWidgetItemIterator(arbre)
    while iterateur.value():
        element = iterateur.value()
        parent = element.parent()
        vu = True
        while parent is not None:
            if not parent.isExpanded():
                vu = False
                break
            parent = parent.parent()
        if vu:
            for identifiant, candidat in arbre._elements.items():
                if candidat is element:
                    visibles.append(identifiant)
                    break
        iterateur += 1
    return visibles


def _poser_un_projet_profond(qtbot, coquille):
    """Un projet ou l'arbre a VRAIMENT de la profondeur : rush > lot > planche
    > scan. Sans document de detection, le chutier s'arrete aux lots et les
    tests de depliage seraient verts en ne mesurant rien.

    Deux planches distinguables, et l'atelier SCAN est active : c'est le seul
    ou les scans sont actionnables, donc le seul ou des cases apparaissent --
    et c'est l'atelier des captures d'Egan.
    """
    from mixed_media_utility.gui.coquille import CLE_ATELIER_SCAN, ORDRE_ATELIERS

    document = fab.document_de_detection(
        lot_id="lot-beta-2",
        rush_id="rush-beta",
        pages=[
            fab.page_detectee(0, 1, lot_id="lot-beta-2", rush_id="rush-beta"),
            fab.page_detectee(
                1, 0, lot_id="lot-beta-2", rush_id="rush-beta", largeur_px=190),
        ],
        pages_expected=2,
    )
    coquille.poser_projet(
        fab.manifest_deux_rushes_deux_lots_chacun(),
        documents_de_detection=[document],
        existe=fab.liaison_factice(["medias/alpha.mov", "medias/beta.mov"]),
    )
    coquille.activer_atelier(ORDRE_ATELIERS.index(CLE_ATELIER_SCAN))
    qtbot.wait(10)


def test_ce_qu_on_voit_sous_un_objet_ne_depend_pas_de_la_portee(qtbot, coquille):
    """La MEME planche montre ses lots, vue de son rush ou vue d'elle-meme.

    Defaut mesure avant correctif (`expandToDepth`) : la portee `rush-beta`
    affichait ses deux lots mais gardait leurs enfants REPLIES, alors que la
    portee `lot-beta-2` les affichait. Ce qu'on voyait sous un objet dependait
    donc de l'endroit d'ou on le regarde.
    """
    _poser_un_projet_profond(qtbot, coquille)
    coquille.designer("rush-beta")
    qtbot.wait(10)
    depuis_le_rush = _lignes_visibles(coquille.chutier.arbre)

    coquille.designer("lot-beta-2")
    qtbot.wait(10)
    depuis_le_lot = _lignes_visibles(coquille.chutier.arbre)

    # Tout ce que la portee ETROITE montre est aussi visible depuis la LARGE.
    manquants = [i for i in depuis_le_lot if i not in depuis_le_rush]
    assert manquants == [], (
        f"visibles depuis le lot mais CACHES depuis le rush : {manquants}")
    assert "lot-beta-2" in depuis_le_rush


def test_tout_le_contenu_de_la_portee_est_deplie(qtbot, coquille):
    """Volet direct : aucun noeud du chutier n'arrive replie.

    Sans lui, le test precedent serait vert sur un arbre qui ne montre RIEN
    aux deux portees -- l'egalite de deux ensembles vides.
    """
    _poser_un_projet_profond(qtbot, coquille)
    coquille.designer("rush-beta")
    qtbot.wait(10)
    arbre = coquille.chutier.arbre
    replies = [
        identifiant for identifiant, element in arbre._elements.items()
        if element.childCount() and not element.isExpanded()
    ]

    assert replies == [], f"noeuds arrives replies : {replies}"
    # Et il y a bien de la profondeur a montrer : sans cela le test est vide.
    assert any(e.childCount() for e in arbre._elements.values())


def test_deux_freres_alignent_leur_libelle_meme_quand_l_un_n_a_pas_de_case(
    qtbot, coquille
):
    """La place de la case est RESERVEE quand la case est absente.

    Defaut mesure : `lot-beta-1` n'a aucun objet actionnable dessous, donc
    aucune case ; `lot-beta-2` en a une. Deux freres du meme type, deux
    abscisses de libelle differentes -- les indentations bancales des captures
    du 2026-08-27.

    La regle ne change pas -- pas de case veut toujours dire « aucun geste
    possible ici » -- c'est son absence qui cesse de decaler le texte.
    """
    from PySide6.QtCore import Qt

    _poser_un_projet_profond(qtbot, coquille)
    coquille.designer("rush-beta")
    qtbot.wait(10)
    arbre = coquille.chutier.arbre
    delegue = arbre.itemDelegate()

    sans_case = arbre.element("lot-beta-1")
    avec_case = arbre.element("lot-beta-2")
    assert sans_case is not None and avec_case is not None
    # Les deux sont bien freres, de meme type, a la meme profondeur.
    assert sans_case.parent() is avec_case.parent()

    from PySide6.QtWidgets import QStyleOptionViewItem

    index_sans = arbre.indexFromItem(sans_case, module_chutier.COLONNE_LIBELLE)
    index_avec = arbre.indexFromItem(avec_case, module_chutier.COLONNE_LIBELLE)
    assert not (sans_case.flags() & Qt.ItemFlag.ItemIsUserCheckable)
    assert avec_case.flags() & Qt.ItemFlag.ItemIsUserCheckable

    option = QStyleOptionViewItem()
    option.widget = arbre
    assert delegue.reserve_la_case(option, index_sans) is True
    assert delegue.reserve_la_case(option, index_avec) is False, (
        "une ligne qui PORTE une case ne doit pas en reserver une seconde")


def test_la_largeur_reservee_est_celle_du_STYLE_et_non_une_constante(
    qtbot, coquille
):
    """Volet symetrique : une reservation de zero pixel ne reserverait rien.

    Le nombre est lu du style de la plateforme -- l'indicateur n'a pas la meme
    taille partout, et une constante ecrite ici serait juste sur une machine
    et fausse sur la suivante.
    """
    from PySide6.QtWidgets import QStyleOptionViewItem

    arbre = coquille.chutier.arbre
    delegue = arbre.itemDelegate()
    option = QStyleOptionViewItem()
    option.widget = arbre

    assert delegue.largeur_de_la_case(option) > 0


def test_le_panneau_d_arborescence_ne_reserve_aucune_case(qtbot, coquille):
    """Le panneau de gauche ne porte JAMAIS de case (`DESIGN.md`,
    `bin-tree-panel` : « aucune puce de selection »). Il n'a donc rien a
    reserver, et un decalage y serait une regression pure."""
    from PySide6.QtCore import Qt

    from PySide6.QtWidgets import QStyleOptionViewItem

    _poser_un_projet_profond(qtbot, coquille)
    arbre = coquille.arbre_arborescence
    assert not arbre.montre_les_signes
    assert arbre._elements, "le panneau doit porter des lignes a mesurer"

    delegue = coquille.chutier.arbre.itemDelegate()
    option = QStyleOptionViewItem()
    option.widget = arbre
    for identifiant, element in arbre._elements.items():
        index = arbre.indexFromItem(element, module_chutier.COLONNE_LIBELLE)
        assert delegue.reserve_la_case(option, index) is False, identifiant
        # Et aucune case n'y est POSEE : c'est ce qui rend la reservation
        # inutile. Les drapeaux, eux, portent `ItemIsUserCheckable` par defaut
        # chez Qt -- s'y fier donnerait le bon resultat par accident.
        assert element.data(
            module_chutier.COLONNE_LIBELLE, Qt.ItemDataRole.CheckStateRole) is None


def _abscisse_du_premier_pixel(arbre, element, delegue):
    """Ou le CONTENU d'une cellule commence reellement, en pixels peints.

    Mesure le rendu et non la decision : un test qui n'interrogerait que
    `reserve_la_case` resterait vert si `paint` cessait d'appliquer le
    decalage -- mutant mesure survivant le 2026-08-27. C'est le meme motif que
    le banc qui lit le pixel des poignees en 7.13 : ce qui se voit se mesure
    sur ce qui est peint.
    """
    from PySide6.QtCore import QRect, Qt
    from PySide6.QtGui import QPainter, QPixmap
    from PySide6.QtWidgets import QStyleOptionViewItem

    index = arbre.indexFromItem(element, module_chutier.COLONNE_LIBELLE)
    pixmap = QPixmap(300, 24)
    pixmap.fill(Qt.GlobalColor.black)
    option = QStyleOptionViewItem()
    option.widget = arbre
    delegue.initStyleOption(option, index)
    option.rect = QRect(0, 0, 300, 24)
    peintre = QPainter(pixmap)
    try:
        delegue.paint(peintre, option, index)
    finally:
        peintre.end()
    image = pixmap.toImage()
    for x in range(300):
        for y in range(24):
            if image.pixelColor(x, y) != Qt.GlobalColor.black:
                return x
    return None


def test_la_place_reservee_est_REELLEMENT_peinte(qtbot, coquille):
    """Le contenu d'une ligne sans case commence PLUS A DROITE, d'exactement
    la largeur de la case.

    Compare le delegue du chutier a un `QStyledItemDelegate` nu sur la MEME
    ligne : la difference des deux abscisses est le decalage, et il doit valoir
    la largeur que `largeur_de_la_case` annonce. Sans cette mesure, retirer le
    decalage de `paint` laissait la suite verte.
    """
    from PySide6.QtWidgets import QStyleOptionViewItem, QStyledItemDelegate

    _poser_un_projet_profond(qtbot, coquille)
    coquille.designer("rush-beta")
    qtbot.wait(10)
    arbre = coquille.chutier.arbre
    delegue = arbre.itemDelegate()
    sans_case = arbre.element("lot-beta-1")
    assert sans_case is not None

    avec_reservation = _abscisse_du_premier_pixel(arbre, sans_case, delegue)
    sans_reservation = _abscisse_du_premier_pixel(
        arbre, sans_case, QStyledItemDelegate())

    assert avec_reservation is not None and sans_reservation is not None, (
        "rien n'a ete peint : le banc ne mesure rien")
    attendu = delegue.largeur_de_la_case(QStyleOptionViewItem())
    assert avec_reservation - sans_reservation == attendu, (
        f"decalage peint {avec_reservation - sans_reservation}, "
        f"largeur reservee annoncee {attendu}")


def test_une_ligne_QUI_PORTE_une_case_n_est_pas_decalee_en_plus(qtbot, coquille):
    """Volet symetrique : la reservation ne s'ajoute pas a la case reelle.

    Sans lui, un decalage applique a TOUTES les lignes passerait le test
    precedent et decalerait l'arbre entier d'un cran -- le defaut inverse.
    """
    from PySide6.QtWidgets import QStyledItemDelegate

    _poser_un_projet_profond(qtbot, coquille)
    coquille.designer("rush-beta")
    qtbot.wait(10)
    arbre = coquille.chutier.arbre
    delegue = arbre.itemDelegate()
    avec_case = arbre.element("lot-beta-2")

    peint = _abscisse_du_premier_pixel(arbre, avec_case, delegue)
    nu = _abscisse_du_premier_pixel(arbre, avec_case, QStyledItemDelegate())

    assert peint == nu, (
        "une ligne qui porte deja sa case ne doit recevoir aucun decalage")
