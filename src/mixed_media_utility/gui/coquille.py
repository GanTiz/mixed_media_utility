# -*- coding: utf-8 -*-
"""Coquille de l'application (story 7.0, AC 2) : fenetre unique, quatre
ateliers, zones de chrome posees et VIDES de contenu metier.

Geometrie contractuelle -- toutes les dimensions se lisent dans
``jetons.ESPACEMENTS``, aucun nombre de geometrie n'est ecrit en dur ici ;
toutes les chaines visibles se lisent dans le catalogue (AC 6).

Ce que la coquille pose (et rien de plus) :

* en-tete (``header-height``), bande centrale, barre d'onglets d'ateliers
  en BAS (``tabbar-height``), quatre onglets dans l'ordre du flux :
  Extraction / Pdf / Scan / Exports (``EXPERIENCE.md``, par. IA) ;
* dans la bande centrale : panneau d'arborescence retractable (defaut
  ``tree-panel-width``, rail ``tree-panel-rail``), poignee de largeur
  (``splitter-width``), emplacement du chutier (defaut ``bin-width`` --
  ``EPIC7-ARB-40`` : la coquille reserve l'emplacement, le contenu est
  7.2), scene centrale (plancher ``stage-min-width``), panneau lateral
  (``side-panel-width``, retractable, retracte par defaut dans la
  coquille -- son contenu est 7.1+) ;
* les regles de largeur d'``EXPERIENCE.md`` : les largeurs sont stables
  tant que l'utilisateur ne les change pas -- seul son geste les deplace,
  jamais un changement d'atelier ; le plafond de chaque poignee est
  DERIVE (les planchers des autres panneaux le bornent), jamais constant ;
* le repli automatique de l'arborescence sous ``tree-collapse-threshold``,
  sans message (``EPIC7-ARB-8``) ; un choix explicite survit au
  franchissement du seuil (le seuil fixe le defaut, il ne reprend pas la
  main -- ``EXPERIENCE.md``, question ouverte 4 de la fiche, prise ici).
"""

import json
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTabBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..io import extraction_manifest as _extraction_manifest
from . import atelier_scan as _atelier_scan
from . import catalogue as _catalogue
from . import chargeur_detections as _chargeur
from . import chutier as _chutier
from . import jetons
from . import lecture_detection as _lecture
from . import modele_chutier as _modele
from . import raster_de_page as _raster
from . import scan_jugement as _scan_jugement
from . import zone_tampon as _zone_tampon

# Fabrique des ateliers : collection ORDONNEE d'elements distinguables
# (regle des fabriques, AC 2). L'ordre est l'ordre du flux, il ne se
# renegocie pas ici : Extraction -> Pdf -> Scan -> Exports.
ORDRE_ATELIERS = (
    "atelier-extraction",
    "atelier-pdf",
    "atelier-scan",
    "atelier-exports",
)


#: La cle de l'atelier Scan dans `ORDRE_ATELIERS` : nommee une fois, ici,
#: plutot que recopiee partout ou la page se distingue des trois autres.
CLE_ATELIER_SCAN = "atelier-scan"


def _feuille_de_style(chaines_couleurs, typographie):
    """Feuille de style de la coquille, entierement lue des jetons."""
    c = chaines_couleurs
    corps = typographie["body"]
    return (
        f"QMainWindow, #bande-centrale {{"
        f" background: {c['surface-canvas']}; }}"
        f" QWidget {{ color: {c['text-primary']};"
        f" font-family: {corps['famille']};"
        f" font-size: {corps['taille']}px; }}"
        f" #en-tete, QTabBar {{ background: {c['surface-panel']}; }}"
        f" #panneau-arborescence {{ background: {c['surface-sunken']};"
        f" border-right: 1px solid {c['border']}; }}"
        f" #chutier, #panneau-lateral {{ background: {c['surface-panel']}; }}"
        f" QTabBar::tab {{ background: {c['surface-panel']};"
        f" color: {c['text-secondary']}; padding: 0px 16px; }}"
        f" QTabBar::tab:selected {{ color: {c['text-primary']};"
        f" border-top: 2px solid {c['accent']}; }}"
        f" QLabel[role='zone'] {{ color: {c['text-secondary']}; }}"
    )


class PanneauArborescence(QFrame):
    """Panneau gauche du chutier a deux panneaux (``EPIC7-ARB-40``).

    Deux etats : OUVERT (largeur reglable a la poignee, plancher
    ``tree-panel-min-width``) et REPLIE (rail de ``tree-panel-rail`` px,
    toujours actionnable : on a l'un ou l'autre, jamais rien).
    """

    def __init__(self, chaines, parent=None):
        super().__init__(parent)
        self.setObjectName("panneau-arborescence")
        e = jetons.ESPACEMENTS
        self._largeur_rail = e["tree-panel-rail"]
        self._plancher_ouvert = e["tree-panel-min-width"]
        self._repliee = False

        colonne = QVBoxLayout(self)
        colonne.setContentsMargins(0, 0, 0, 0)
        colonne.setSpacing(0)
        self._pile = QStackedWidget(self)
        colonne.addWidget(self._pile)

        # Etat ouvert : en-tete de zone + bouton de repli, corps reserve.
        contenu = QWidget(self)
        contenu_v = QVBoxLayout(contenu)
        marge = e["panel-pad"]
        contenu_v.setContentsMargins(marge, marge, marge, marge)
        entete = QHBoxLayout()
        titre = QLabel(chaines["zone-arborescence"], contenu)
        titre.setProperty("role", "zone")
        titre.setWordWrap(True)  # un en-tete a le droit de passer sur deux lignes
        entete.addWidget(titre, 1)
        # Une pastille portant un signe. La fleche Qt native d'avant se
        # peignait au style de la PLATEFORME -- un gros triangle bleu clair au
        # milieu d'une coque sombre (passe de chrome du 2026-08-26). Le libelle
        # du geste reste en infobulle, lu du catalogue.
        self.bouton_replier = QToolButton(contenu)
        self.bouton_replier.setText(jetons.ICONOGRAPHIE["glyphe-replier"])
        self.bouton_replier.setToolTip(chaines["replier-arborescence"])
        self.bouton_replier.setAccessibleName(chaines["replier-arborescence"])
        entete.addWidget(self.bouton_replier, 0)
        # L'en-tete est retenu : le bouton de repli en SORT le temps d'une
        # ouverture par-dessus le chutier, et doit y revenir a sa place
        # (`EPIC7-ARB-93`, volet b). C'est le meme principe que
        # `emplacement_contenu` pour l'arbre -- le panneau prete ses pieces,
        # il ne les duplique pas.
        self._entete = entete
        contenu_v.addLayout(entete)
        # Emplacement du contenu : l'arbre y est POSE par la coquille, et
        # peut en etre retire le temps d'une ouverture par-dessus le chutier
        # (`EPIC7-ARB-40`). Le panneau ne possede donc pas l'arbre.
        self.emplacement_contenu = QVBoxLayout()
        self.emplacement_contenu.setContentsMargins(0, 0, 0, 0)
        contenu_v.addLayout(self.emplacement_contenu, 1)
        self._pile.addWidget(contenu)

        # Etat replie : le rail, reduit a son bouton de reouverture.
        rail = QWidget(self)
        rail_v = QVBoxLayout(rail)
        rail_v.setContentsMargins(0, marge, 0, marge)
        self.bouton_rouvrir = QToolButton(rail)
        self.bouton_rouvrir.setText(jetons.ICONOGRAPHIE["glyphe-rouvrir"])
        self.bouton_rouvrir.setToolTip(chaines["rail-rouvrir-arborescence"])
        self.bouton_rouvrir.setAccessibleName(chaines["rail-rouvrir-arborescence"])
        rail_v.addWidget(self.bouton_rouvrir, 0, Qt.AlignmentFlag.AlignHCenter)
        rail_v.addStretch(1)
        self._pile.addWidget(rail)

        self._appliquer_etat()

    def poser_contenu(self, widget):
        """Poser (ou reposer) l'arbre dans l'etat ouvert du panneau."""
        self.emplacement_contenu.addWidget(widget)
        widget.show()

    def reprendre_le_bouton_de_repli(self):
        """Remettre le bouton de repli dans l'en-tete, a sa place.

        Pendant l'ouverture par-dessus le chutier, c'est la superposition qui
        l'heberge : le panneau ouvert est masque, et un bouton dans un widget
        masque n'est pas actionnable -- l'operatrice n'avait alors AUCUN geste
        pour refermer, seulement celui de designer un noeud. On deplace donc
        l'unique bouton plutot que d'en peindre un second, qui aurait diverge
        de celui-ci au premier changement d'icone.
        """
        # `addWidget` reparente : le bouton revient DANS le contenu ouvert, et
        # en derniere position de l'en-tete -- c'est-a-dire la sienne, le titre
        # portant le facteur d'etirement.
        self._entete.addWidget(self.bouton_replier, 0)
        self.bouton_replier.show()

    @property
    def est_repliee(self):
        """Vrai quand le panneau est reduit a son rail."""
        return self._repliee

    def replier(self):
        """Reduire le panneau a son rail (sans message, ``EPIC7-ARB-8``)."""
        if not self._repliee:
            self._repliee = True
            self._appliquer_etat()

    def deplier(self):
        """Rouvrir le panneau a sa largeur reglable."""
        if self._repliee:
            self._repliee = False
            self._appliquer_etat()

    def _appliquer_etat(self):
        # La geometrie du splitter s'appuie sur les bornes du widget : le
        # rail est FIXE, l'etat ouvert a un plancher et pas de plafond
        # constant (le plafond est derive des planchers voisins).
        if self._repliee:
            self._pile.setCurrentIndex(1)
            self.setMinimumWidth(self._largeur_rail)
            self.setMaximumWidth(self._largeur_rail)
        else:
            self._pile.setCurrentIndex(0)
            self.setMinimumWidth(self._plancher_ouvert)
            self.setMaximumWidth(16777215)  # QWIDGETSIZE_MAX : plafond derive


def _zone_reservee(nom_objet, libelle, chaines, parent=None):
    """Fabrique une zone de chrome VIDE de contenu metier (AC 7).

    La zone ne contient que son libelle de catalogue et la mention de
    reservation -- aucun widget metier avant les stories 7.1 a 7.3.
    """
    zone = QFrame(parent)
    zone.setObjectName(nom_objet)
    colonne = QVBoxLayout(zone)
    marge = jetons.ESPACEMENTS["panel-pad"]
    colonne.setContentsMargins(marge, marge, marge, marge)
    titre = QLabel(libelle, zone)
    titre.setProperty("role", "zone")
    titre.setWordWrap(True)
    colonne.addWidget(titre)
    reserve = QLabel(chaines["zone-reservee"], zone)
    reserve.setProperty("role", "zone")
    reserve.setWordWrap(True)
    colonne.addWidget(reserve)
    colonne.addStretch(1)
    return zone


class Coquille(QMainWindow):
    """Fenetre principale unique de l'application (AC 2)."""

    #: Emis par le bouton d'accueil de l'en-tete (`EPIC7-ARB-92`). La
    #: coquille ne sait pas ce qu'est « l'ecran des projets » -- c'est
    #: l'enchainement de lancement qui le sait et qui l'affiche. Elle
    #: n'en ferme donc RIEN : le projet ouvert le reste.
    accueil_demande = Signal()

    def __init__(self, chaines=None, parent=None):
        super().__init__(parent)
        self._chaines = dict(_catalogue.CHAINES if chaines is None else chaines)
        chaines = self._chaines
        e = jetons.ESPACEMENTS

        self.setWindowTitle(chaines["app-titre"])
        self.setMinimumSize(e["window-min-width"], e["window-min-height"])
        self.setStyleSheet(_feuille_de_style(jetons.COULEURS, jetons.TYPOGRAPHIE))

        # Memoire du choix explicite de l'operateur sur l'arborescence :
        # None = aucun choix (le seuil fixe le defaut), True = ouverte par
        # geste, False = repliee par geste. Un choix explicite survit au
        # franchissement du seuil (EXPERIENCE.md).
        self._choix_arborescence = None
        self._repli_automatique = False

        # Etat du chutier (story 7.2) : l'arbre du projet ouvert, la
        # designation courante, le mode plein ecran et l'ouverture par-dessus
        # le chutier. Rien de tout cela ne vit au projet : ce sont des
        # donnees de session GUI.
        self._racines = ()
        # Le DOSSIER du projet ouvert -- un chemin, jamais un verdict de
        # completude : celui-ci se relit du disque a chaque ouverture.
        self._project_dir = None
        self._designation = None
        #: L'objet DESIGNE en dernier, quel que soit le panneau qui l'a
        #: designe. Distinct de `_designation`, qui est la PORTEE du chutier
        #: et que seul le panneau de gauche fixe (`EPIC7-ARB-84`).
        self._contexte = None
        #: La largeur allouee au panneau d'arborescence quand il est ouvert.
        #: Retenue pour la rendre au splitter au deplilage -- voir
        #: `_recoller_la_poignee`.
        self._largeur_arborescence_ouverte = e["tree-panel-width"]
        self._plein_ecran_chutier = False
        self.selection = None
        self._geometrie_avant_plein_ecran = None
        self._survol_actif = False

        centre = QWidget(self)
        colonne = QVBoxLayout(centre)
        colonne.setContentsMargins(0, 0, 0, 0)
        colonne.setSpacing(0)

        # --- En-tete, hauteur fixe. -------------------------------------
        self.en_tete = QFrame(centre)
        self.en_tete.setObjectName("en-tete")
        self.en_tete.setFixedHeight(e["header-height"])
        entete_h = QHBoxLayout(self.en_tete)
        entete_h.setContentsMargins(e["gutter"], 0, e["gutter"], 0)
        entete_h.setSpacing(e["4"])
        # --- Retour a l'ecran des projets (`EPIC7-ARB-92`). --------------
        # Egan, second essai de terrain : « Pas de bouton pour retourner a
        # l'ecran de projets et pouvoir en changer. Oblige de relancer
        # l'interface a chaque fois. » Il est A GAUCHE DU TITRE et visible
        # EN PERMANENCE -- aucun etat de l'application ne le retire, parce
        # que c'est justement dans les etats ou l'on est coince qu'on en a
        # besoin. Son glyphe se lit dans `jetons`, son libelle du catalogue,
        # et il porte le meme texte en infobulle et en nom accessible : un
        # bouton reduit a un pictogramme n'a pas d'autre nom.
        self.bouton_accueil = QToolButton(self.en_tete)
        self.bouton_accueil.setObjectName("bouton-accueil")
        self.bouton_accueil.setText(jetons.ICONOGRAPHIE["glyphe-accueil"])
        self.bouton_accueil.setStyleSheet(
            f"font-size: {jetons.ICONOGRAPHIE['glyphe-accueil-px']}px;"
        )
        self.bouton_accueil.setToolTip(chaines["coquille-accueil"])
        self.bouton_accueil.setAccessibleName(chaines["coquille-accueil"])
        self.bouton_accueil.setFixedHeight(e["hit-min"])
        self.bouton_accueil.clicked.connect(
            lambda _coche=False: self.accueil_demande.emit()
        )
        entete_h.addWidget(
            self.bouton_accueil, 0, Qt.AlignmentFlag.AlignVCenter
        )
        titre = QLabel(chaines["app-titre"], self.en_tete)
        entete_h.addWidget(titre, 0, Qt.AlignmentFlag.AlignVCenter)
        entete_h.addStretch(1)
        # --- Bascule brut / corrige (story 7.4, AC 8, EPIC7-ARB-69). -----
        # Elle est une PREFERENCE D'APPLICATION, pas un reglage d'ecran :
        # « Il faut ajouter l'icone quelque part dans la surface pour
        # qu'elle touche la galerie, le lecteur, les planches pdf etc. »
        # Elle vit donc ici, dans l'en-tete de la coquille, et c'est le
        # SEUL point de definition de cet etat dans la GUI -- « aucun ecran
        # ne porte sa propre bascule locale, ni un etat de calibration qui
        # lui soit propre ».
        self.preference_image = PreferenceDImage(self)
        self.bascule_image = BasculeDImage(
            self.preference_image, chaines, self.en_tete
        )
        entete_h.addWidget(
            self.bascule_image, 0, Qt.AlignmentFlag.AlignVCenter
        )
        colonne.addWidget(self.en_tete)

        # --- Bande centrale : arborescence | chutier | scene [| lateral].
        bande = QWidget(centre)
        bande.setObjectName("bande-centrale")
        bande_h = QHBoxLayout(bande)
        bande_h.setContentsMargins(0, 0, 0, 0)
        bande_h.setSpacing(0)

        self.panneau_arborescence = PanneauArborescence(chaines, bande)
        # L'arbre du panneau gauche : il sert a SE PLACER -- ni badge, ni
        # compteur (`DESIGN.md`, `bin-tree-panel`). Il appartient a la
        # coquille et non au panneau, parce qu'il le quitte le temps d'une
        # ouverture par-dessus le chutier.
        self.arbre_arborescence = _chutier.ArbreDeChutier(
            chaines, montre_les_signes=False, parent=self.panneau_arborescence
        )
        self.panneau_arborescence.poser_contenu(self.arbre_arborescence)

        # Le chutier proprement dit (story 7.2) : il montre le contenu de
        # l'objet designe a gauche. `zone_chutier` reste son nom historique
        # cote geometrie (le socle 7.0 y reservait l'emplacement).
        #
        # **La colonne du chutier porte DEUX surfaces depuis la story 7.3** :
        # la file « En attente de lecture » EN HAUT (`DESIGN.md`, `bin-buffer` :
        # « position: haut du chutier, au-dessus de l'arbre »), le chutier en
        # dessous. La file est posee dans la colonne et non DANS le chutier :
        # l'arbre nu de 7.2 reste ce qu'il est, et sa frontiere -- « le chutier
        # ne porte ni barre de filtres ni zone tampon » -- tient telle quelle.
        self.colonne_chutier = QFrame(bande)
        self.colonne_chutier.setObjectName("colonne-chutier")
        pile_chutier = QVBoxLayout(self.colonne_chutier)
        pile_chutier.setContentsMargins(0, 0, 0, 0)
        pile_chutier.setSpacing(0)
        self.zone_tampon = _zone_tampon.ZoneTampon(
            chaines, parent=self.colonne_chutier)
        pile_chutier.addWidget(self.zone_tampon, 0)
        self.chutier = _chutier.Chutier(chaines, self.colonne_chutier)
        pile_chutier.addWidget(self.chutier, 1)
        self.zone_chutier = self.colonne_chutier

        # La scene porte la pile des quatre pages d'atelier (vides).
        self.scene = QFrame(bande)
        self.scene.setObjectName("scene")
        self.scene.setMinimumWidth(e["stage-min-width"])
        scene_v = QVBoxLayout(self.scene)
        scene_v.setContentsMargins(0, 0, 0, 0)
        self.pile_ateliers = QStackedWidget(self.scene)
        scene_v.addWidget(self.pile_ateliers)
        # La page `atelier-scan` cesse d'etre reservee : la vague 3 la
        # remplit. Les trois autres restent des emplacements, chacune
        # attendant sa story.
        #
        # **La page du Scan porte les DEUX TEMPS de l'atelier**, empiles :
        # « L'atelier Scan se deroule en deux temps, jamais en un »
        # (`EXPERIENCE.md`, *Points de jugement avant ecriture*). Le temps 1
        # est celui de 7.3 -- deposer, detecter, annoncer ; le temps 2 est
        # celui de 7.4 -- juger la planche avant qu'un TIFF ne s'ecrive. Un
        # seul des deux est visible a la fois, et aucun controle neuf ne les
        # separe : ce sont les gestes qui existent deja qui commutent -- le
        # bouton « detecter » du chutier ramene au temps 1, l'ouverture d'un
        # scan au chutier (double-clic, `EPIC7-ARB-11`) mene au temps 2.
        self.atelier_scan = _atelier_scan.AtelierScan(
            chaines, parent=self.pile_ateliers)
        # Le second temps LIT la preference d'image de la coquille -- c'est
        # ici, et nulle part ailleurs, que ce cablage se fait (`EPIC7-ARB-69` :
        # aucun ecran ne porte sa propre bascule). Son fournisseur de rasters
        # arrive avec le scan ouvert, parce que le dpi de rendu est celui que
        # le DOCUMENT declare.
        self.atelier_jugement = _scan_jugement.AtelierScanJugement(
            chaines, self.preference_image, parent=self.pile_ateliers)
        self.temps_du_scan = QStackedWidget(self.pile_ateliers)
        self.temps_du_scan.addWidget(self.atelier_scan)
        self.temps_du_scan.addWidget(self.atelier_jugement)
        # Fabrique du fournisseur de rasters : nommee ici pour etre
        # SUBSTITUABLE par un banc. Le depot ne contient aucune image
        # corrigee (`EPIC5-ARB-5` : la calibration active est post-MVP), donc
        # sans cette couture aucun test ne pourrait mesurer sur l'application
        # assemblee qu'une bascule posee dans l'en-tete traverse deux
        # surfaces -- elle ne changerait jamais rien nulle part.
        self.fabrique_de_fournisseur = _raster.FournisseurDeProjet
        for cle in ORDRE_ATELIERS:
            if cle == CLE_ATELIER_SCAN:
                page = self.temps_du_scan
            else:
                page = _zone_reservee(
                    cle, chaines[cle], chaines, self.pile_ateliers)
            self.pile_ateliers.addWidget(page)

        self.splitter = QSplitter(Qt.Orientation.Horizontal, bande)
        self.splitter.setHandleWidth(e["splitter-width"])
        self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(self.panneau_arborescence)
        self.splitter.addWidget(self.zone_chutier)
        self.splitter.addWidget(self.scene)
        # Defauts de largeur ; la scene absorbe le reste (plafond derive).
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setStretchFactor(2, 1)
        self.splitter.setSizes(
            [e["tree-panel-width"], e["bin-width"], e["stage-min-width"]]
        )
        bande_h.addWidget(self.splitter, 1)

        # Panneau lateral de reglages : emplacement reserve, largeur fixe,
        # RETRACTE par defaut dans la coquille (son contenu et sa politique
        # d'affichage sont 7.1+ ; a la fenetre minimale il n'entre pas dans
        # le budget de chrome de DESIGN.md, qui est calcule sans lui).
        self.panneau_lateral = _zone_reservee(
            "panneau-lateral", chaines["zone-panneau-lateral"], chaines, bande
        )
        self.panneau_lateral.setFixedWidth(e["side-panel-width"])
        self.panneau_lateral.setVisible(False)
        bande_h.addWidget(self.panneau_lateral, 0)

        # Superposition : l'arborescence ouverte PAR-DESSUS le chutier, le
        # temps de se placer -- « on a l'un ou l'autre, jamais rien ».
        self.superposition_arborescence = _chutier.SuperpositionArborescence(bande)

        colonne.addWidget(bande, 1)

        # --- Barre d'onglets d'ateliers, en BAS, hauteur fixe. ----------
        self.barre_onglets = QTabBar(centre)
        self.barre_onglets.setObjectName("barre-onglets")
        self.barre_onglets.setFixedHeight(e["tabbar-height"])
        # Largeur EGALE des quatre onglets, sur toute la barre (DESIGN.md:468,
        # "quatre ateliers dans l'ordre du flux, largeur egale"). `True` est
        # le defaut Qt ; il avait ete explicitement desactive a tort (revue
        # de vague 1, capture 7-0-capture-coquille-1500x900.png : quatre
        # onglets groupes a gauche, largeurs inegales).
        self.barre_onglets.setExpanding(True)
        # Jamais de troncature d'un libelle interactif (AC 6) ; pas de
        # boutons de defilement Qt non plus -- ils porteraient des libelles
        # internes anglais hors catalogue, et quatre onglets tiennent
        # toujours (mesure par le test des chaines gonflees de 40 %).
        self.barre_onglets.setElideMode(Qt.TextElideMode.ElideNone)
        self.barre_onglets.setUsesScrollButtons(False)
        for cle in ORDRE_ATELIERS:
            self.barre_onglets.addTab(chaines[cle])
        self.barre_onglets.currentChanged.connect(self.pile_ateliers.setCurrentIndex)
        # L'inventaire des objets ACTIONNABLES depend de l'atelier courant :
        # la selection se refait sur le bon inventaire a chaque bascule
        # (`EPIC7-ARB-10`). Elle ne se transporte pas d'un atelier a l'autre
        # -- des lots coches pour « generer des planches » ne designent rien
        # sur Exports.
        self.barre_onglets.currentChanged.connect(self._refaire_la_selection)
        colonne.addWidget(self.barre_onglets)

        self.setCentralWidget(centre)

        # Gestes de l'operateur sur l'arborescence : des CHOIX explicites.
        self.panneau_arborescence.bouton_replier.clicked.connect(
            self.replier_arborescence
        )
        # Le rail rouvre l'arborescence : EN PLACE quand la place existe,
        # PAR-DESSUS le chutier quand elle manque (`EPIC7-ARB-40`).
        self.panneau_arborescence.bouton_rouvrir.clicked.connect(
            self.rouvrir_arborescence_depuis_le_rail
        )

        # **Le bouton vit au chutier, le travail se voit a l'atelier.**
        # C'est le cablage exact d'`EPIC7-ARB-40` (role 4) : la file et son
        # bouton sont au chutier, les cartes et l'annonce sont dans la page
        # Scan, et rien ne part sans le clic.
        self.zone_tampon.detection_demandee.connect(self.atelier_scan.lancer)
        # Detecter, c'est revenir au PREMIER temps : les cartes et l'annonce
        # se voient dans la scene, et elles ne se verraient pas derriere la
        # surface de jugement d'un scan precedemment ouvert.
        self.zone_tampon.detection_demandee.connect(
            lambda _entrees: self.montrer_le_premier_temps_du_scan())
        self.atelier_scan.poser_le_projet(None, self.zone_tampon.modele)
        # Une detection qui aboutit repeuple l'arbre : le chutier relit les
        # documents du disque, jamais un etat de session.
        self.atelier_scan.detection_terminee.connect(
            self._sur_detection_terminee)
        # L'atelier pose le motif et le reliquat SUR les entrees ; la surface
        # de la file, elle, vit au chutier et doit se redessiner.
        self.atelier_scan.file_mise_a_jour.connect(self.zone_tampon.rafraichir)

        # Gestes des deux arbres : un clic designe, un double-clic ouvre.
        #
        # **Les deux arbres ne sont PLUS cables au meme couple**
        # (`EPIC7-ARB-84`, 2026-08-27). Ils l'etaient, et `designer`
        # recalcule la portee du chutier : un clic DANS le chutier rabattait
        # donc le chutier sur les enfants de la ligne cliquee, faisant
        # disparaitre la fratrie et les parents a chaque clic. « C'est le
        # role du panneau de gauche mais pas le role du panneau de droite »
        # (Egan). La surface se mangeait elle-meme.
        #
        # Seul le panneau d'arborescence fixe la portee. Le chutier designe
        # -- mise en evidence, contexte -- et ouvre, sans jamais redefinir
        # ce qu'il montre.
        self.arbre_arborescence.designation_changee.connect(self.designer)
        self.arbre_arborescence.ouverture_demandee.connect(self.ouvrir)
        self.chutier.arbre.designation_changee.connect(
            self.designer_dans_le_chutier)
        self.chutier.arbre.ouverture_demandee.connect(
            self.ouvrir_depuis_le_chutier)
        self.chutier.plein_ecran_demande.connect(self.basculer_plein_ecran_chutier)

        # La largeur reglee A LA POIGNEE est celle qu'il faudra rendre au
        # deplilage : « les largeurs sont stables tant que l'utilisateur ne
        # les change pas » (`EXPERIENCE.md`). Sans ce cablage, un reglage
        # manuel serait perdu au premier repli.
        self.splitter.splitterMoved.connect(
            lambda _position, _indice: self._memoriser_la_largeur_ouverte()
        )
        # Le splitter recalcule ses tailles a chaque disposition, et il le
        # fait DE FACON DIFFEREE : masquer la scene (plein ecran du chutier)
        # lui fait redistribuer la bande d'apres les tailles SOUHAITEES des
        # panneaux restants -- donc rendre au panneau replie la largeur d'un
        # panneau ouvert, dont son widget n'occupe que le rail. Mesure sur le
        # banc : `sizes()` passait a `[196, 759, 0]` pour un panneau large de
        # 42 px, poignee comprise. On ecoute donc le redimensionnement du
        # chutier -- le voisin immediat de la poignee -- pour recoller apres
        # coup. La reentrance est bornee : le second passage trouve un ecart
        # nul et rend la main.
        self.zone_chutier.installEventFilter(self)

        # Taille de la fenetre CONSTRUITE (et non montree) : le plancher.
        # C'est la valeur de reference des bancs de geometrie, qui mesurent
        # tous a une taille qu'ils posent eux-memes.
        #
        # **La fenetre reelle s'ouvre MAXIMISEE** (`EPIC7-ARB-93`) : voir
        # `montrer_en_grand`, appele par l'enchainement de lancement. Elle
        # s'ouvrait jusqu'ici a ce plancher-ci, c'est-a-dire
        # systematiquement SOUS `tree-collapse-threshold` : son PIRE regime,
        # ou l'arborescence part repliee et ou la rouvrir passe par la
        # superposition. Egan, second essai de terrain : « Par defaut on ne
        # peut pas lire le panneau de gauche. »
        self.resize(e["window-min-width"], e["window-min-height"])

    def montrer_en_grand(self):
        """Afficher la fenetre MAXIMISEE (`EPIC7-ARB-93`).

        Le geste est ici plutot que dans le constructeur pour une raison de
        contrat : construire une coquille ne l'affiche pas, et un banc qui
        pose sa propre geometrie ne doit pas se faire maximiser dans le dos.
        L'enchainement de lancement, lui, appelle ceci et rien d'autre.
        """
        self.showMaximized()
        return self

    # --- Ateliers -------------------------------------------------------

    def ateliers(self):
        """La collection ordonnee des libelles d'ateliers affiches."""
        return tuple(
            self.barre_onglets.tabText(i)
            for i in range(self.barre_onglets.count())
        )

    def atelier_actif(self):
        """Le libelle de l'atelier actif (celui de SON onglet)."""
        return self.barre_onglets.tabText(self.barre_onglets.currentIndex())

    def activer_atelier(self, indice):
        """Basculer vers l'atelier a l'indice donne (ordre du flux)."""
        self.barre_onglets.setCurrentIndex(indice)

    # --- Largeurs de panneaux (stabilite au changement d'atelier) -------

    def largeurs_panneaux(self):
        """Releve des largeurs du chrome, pour mesurer leur stabilite."""
        return {
            "arborescence": self.panneau_arborescence.width(),
            "chutier": self.zone_chutier.width(),
            "scene": self.scene.width(),
            "lateral": self.panneau_lateral.width(),
        }

    # --- Arborescence : gestes explicites et repli automatique ----------

    def replier_arborescence(self):
        """Geste explicite de repli : survit aux franchissements de seuil."""
        self._choix_arborescence = False
        self._repli_automatique = False
        self.fermer_survol_arborescence()
        self._poser_l_arborescence(repliee=True)
        self._appliquer_plancher_fenetre()

    def deplier_arborescence(self):
        """Geste explicite d'ouverture (rail) : survit aux franchissements."""
        self._choix_arborescence = True
        self._repli_automatique = False
        self.fermer_survol_arborescence()
        self._poser_l_arborescence(repliee=False)
        self._appliquer_plancher_fenetre()

    def _poser_l_arborescence(self, *, repliee):
        """Replier ou deplier le panneau, ET recoller la poignee sur son bord.

        **Le seul chemin** par lequel l'etat du panneau change : geste
        explicite, repli automatique sous le seuil, ou sortie de
        superposition. Un chemin qui appellerait `panneau.replier()` en
        direct laisserait la poignee derriere lui.
        """
        if repliee == self.panneau_arborescence.est_repliee:
            return
        self._memoriser_la_largeur_ouverte()
        if repliee:
            self.panneau_arborescence.replier()
        else:
            self.panneau_arborescence.deplier()
        self._recoller_la_poignee()

    def _memoriser_la_largeur_ouverte(self):
        """Retenir la largeur ALLOUEE au panneau ouvert, avant de le replier.

        Sans cela, deplier rendrait au panneau la largeur par defaut plutot
        que celle que l'operatrice avait reglee a la poignee -- « les largeurs
        sont stables tant que l'utilisateur ne les change pas »
        (`EXPERIENCE.md`).
        """
        if self.panneau_arborescence.est_repliee:
            return
        tailles = self.splitter.sizes()
        if tailles and tailles[0] >= jetons.ESPACEMENTS["tree-panel-min-width"]:
            self._largeur_arborescence_ouverte = tailles[0]

    def _recoller_la_poignee(self):
        """Rendre au splitter la largeur REELLE du panneau d'arborescence.

        **Le defaut, mesure sur le banc offscreen avant correctif** : fenetre
        large, panneau ouvert, le splitter allouait au panneau exactement
        `tree-panel-width` et le bord droit du panneau y etait. Apres
        `replier_arborescence()`, le panneau mesurait la largeur de son rail
        et le splitter lui allouait TOUJOURS `tree-panel-width` : la poignee
        et le chutier restaient a leur ancienne abscisse, laissant entre le
        rail et le chutier un vide egal a la difference des deux -- plus de
        cent pixels. C'est litteralement le retour d'Egan :
        « il se reduit a droite mais la poignee qui est collee sur son bord
        droit ne suit pas, il faut la "recoller" manuellement. »

        La cause : `QSplitter` garde les tailles qu'on lui a posees et ne les
        recalcule pas parce qu'un enfant a change de plafond de largeur. On
        les lui repose donc explicitement, et la scene absorbe l'ecart --
        c'est elle qui a le facteur d'etirement.

        **En plein ecran, l'ecart est rendu a la scene comme ailleurs**, bien
        qu'elle soit masquee, et le chutier le recoit quand meme : `QSplitter`
        borne un enfant invisible a zero et redistribue. Un aiguillage qui
        aurait vise le chutier explicitement a ete ecrit puis RETIRE -- aucune
        mesure ne le distinguait de celui-ci, sur aucun des deux regimes.
        Cette fonction epingle donc la largeur du panneau partout, sans
        connaitre le plein ecran.

        Les largeurs mesurees vivent dans les tests, jamais ici : une note qui
        les recopierait ferait entrer dans ce module des chiffres qui
        appartiennent a `DESIGN.md`, ce qu'une frontiere de 7.2 interdit.
        """
        tailles = self.splitter.sizes()
        if len(tailles) < 3:
            return
        e = jetons.ESPACEMENTS
        # Tant que le splitter n'est pas DISPOSE, ses tailles sont des
        # valeurs d'attente (mesure : `[30, 30, 30]` a la construction) et
        # les reposer y ecraserait les defauts de largeur que Qt va poser
        # lui-meme au premier `resizeEvent` reel. On ne recolle une poignee
        # que sur une allocation qui existe -- c'est-a-dire au moins la somme
        # des planchers des trois panneaux.
        if sum(tailles) < (
            e["tree-panel-rail"] + e["bin-min-width"] + e["stage-min-width"]
        ):
            return
        if self.panneau_arborescence.est_repliee:
            cible = e["tree-panel-rail"]
        else:
            cible = max(
                self._largeur_arborescence_ouverte, e["tree-panel-min-width"]
            )
        ecart = tailles[0] - cible
        if ecart == 0:
            return
        tailles[0] = cible
        tailles[2] = tailles[2] + ecart
        self.splitter.setSizes(tailles)

    # --- Le chutier a deux panneaux (story 7.2) ------------------------

    def poser_projet(self, manifest, documents_de_detection=(), *, existe=None):
        """Poser l'arbre du projet ouvert dans les deux panneaux.

        L'arbre vient du manifest ET des documents de detection, et de rien
        d'autre : aucun etat de session, aucun parcours de dossier
        (``EXPERIENCE.md``, Reprise). La designation courante est conservee
        si le noeud existe encore, remise a la portee du projet sinon.
        """
        self._racines = _modele.construire_arbre(
            manifest, documents_de_detection, existe=existe
        )
        # **Le panneau de GAUCHE porte une ligne racine, le chutier NON**
        # (`EPIC7-ARB-85`). C'est la position par defaut a l'ouverture d'un
        # projet, et la seule facon d'y revenir apres avoir designe. Le
        # chutier, lui, montre le CONTENU de la portee : une ligne racine y
        # remettrait le contenant dans le contenu.
        self.arbre_arborescence.poser(
            self._racines, libelle_racine=self._libelle_de_la_racine()
        )
        self._refaire_la_selection()
        if _modele.noeud_par_identifiant(self._racines, self._designation) is None:
            self._designation = None
        # La ligne designee suit la portee : la racine quand la portee est le
        # projet entier, le noeud sinon. Sans cela l'etat par defaut serait
        # legal mais invisible -- exactement le defaut qu'`EPIC7-ARB-85`
        # corrige.
        self.arbre_arborescence.designer(
            _chutier.IDENTIFIANT_RACINE
            if self._designation is None
            else self._designation
        )
        self._rafraichir_le_chutier()

    def _libelle_de_la_racine(self):
        """Le libelle de la ligne racine : le nom du dossier de projet ouvert.

        Le nom est de la DONNEE -- il vient du disque -- et seule son
        enveloppe est un libelle de catalogue. Sans projet ouvert, la ligne
        le dit plutot que d'afficher un nom vide.
        """
        if self._project_dir is None:
            return self._chaines["arborescence-racine-sans-projet"]
        return self._chaines["arborescence-racine"].format(
            projet=Path(self._project_dir).name
        )

    def ouvrir_projet(self, project_dir, manifest=None, *, existe=None):
        """Ouvrir un projet : relire le manifest ET les documents du DISQUE.

        C'est ce qui fait survivre la completude a la fermeture (FR7,
        `EPIC7-ARB-49`) : aucune valeur de completude n'est conservee en
        session, elle est **relue** du document de detection de 5.25 a chaque
        ouverture. Une fenetre detruite puis reconstruite sur le meme dossier
        retrouve donc exactement le meme verdict.

        Rend le :class:`chargeur_detections.ResultatDeChargement`, dont les
        documents illisibles -- **nommes**, jamais avales.
        """
        project_dir = None if project_dir is None else Path(project_dir)
        # Changer de projet referme la surface de jugement : le scan qu'elle
        # montrait appartient a l'ancien projet. Rouvrir le MEME dossier ne la
        # referme pas -- c'est ce que fait `_sur_detection_terminee` a chaque
        # detection aboutie, et une detection de fond n'a pas a arracher
        # l'operatrice a la planche qu'elle est en train de juger.
        change_de_projet = project_dir != self._project_dir
        self._project_dir = project_dir
        if change_de_projet:
            self.montrer_le_premier_temps_du_scan()
            # « Elle est la position par defaut a l'ouverture d'un projet »
            # (`EPIC7-ARB-85`) : on entre par le projet entier, jamais par
            # la designation heritee du projet precedent.
            self._designation = None
            self._contexte = None
        self.atelier_scan.poser_le_projet(project_dir, self.zone_tampon.modele)
        if project_dir is None:
            self.poser_projet(manifest, (), existe=existe)
            return _chargeur.ResultatDeChargement()
        if manifest is None:
            manifest = self._relire_le_manifest(project_dir)
        resultat = _chargeur.charger(project_dir)
        self.poser_projet(manifest, resultat.documents, existe=existe)
        return resultat

    @staticmethod
    def _relire_le_manifest(project_dir):
        """Relire `project.json`, ou rendre `None` quand il n'y en a pas encore.

        Un projet sans manifest est un etat LEGAL (`persist_scan` l'ecrit a la
        premiere passe) : l'arbre est alors celui que les seuls documents de
        detection donnent -- c'est le role 3 du chutier, deja pose en 7.2.
        """
        chemin = Path(project_dir) / _extraction_manifest.MANIFEST_FILENAME
        if not chemin.is_file():
            return None
        return json.loads(chemin.read_text(encoding="utf-8"))

    def _sur_detection_terminee(self, _issue):
        """Une detection a abouti : relire le disque et repeupler l'arbre."""
        if self._project_dir is None:
            return
        self.ouvrir_projet(self._project_dir)

    def racines(self):
        """L'arbre du projet ouvert, dans l'ordre des sources."""
        return self._racines

    def atelier_courant(self):
        """La cle d'atelier de l'onglet actif (`ORDRE_ATELIERS`)."""
        return ORDRE_ATELIERS[self.barre_onglets.currentIndex()]

    def _refaire_la_selection(self, *_ignores):
        """Repartir d'une selection vide sur l'inventaire de l'atelier."""
        self.selection = _modele.Selection(self._racines, self.atelier_courant())
        self.refleter_la_selection()

    def refleter_la_selection(self):
        """Porter la selection courante sur les cases du chutier."""
        self.chutier.arbre.refleter_la_selection(self.selection)

    def designation(self):
        """L'identifiant du noeud designe, ou `None` (portee = le projet)."""
        return self._designation

    def contexte(self):
        """Le dernier objet designe, quel que soit le panneau qui l'a designe.

        Ce n'est PAS la portee du chutier : voir `designer_dans_le_chutier`.
        """
        return self._contexte

    def designer(self, identifiant):
        """UN CLIC A GAUCHE DESIGNE : la portee du chutier suit.

        « Le clic ne declenche donc plus aucune navigation »
        (`EPIC7-ARB-2`). Designer referme l'ouverture par-dessus le chutier :
        elle etait la « le temps de se placer », le placement est fait.

        **La ligne racine se traduit ici en portee `None`**
        (`EPIC7-ARB-85`) : l'etat « portee = le projet entier » existait
        depuis 7.2 dans le modele sans qu'aucun geste n'y ramene -- un etat
        legal sans chemin d'acces, si bien qu'on perdait le niveau le plus
        eleve des le premier clic. La traduction est faite ICI et nulle part
        ailleurs : `chutier` pose la ligne, la coquille dit ce qu'elle vaut.
        """
        self._designation = (
            None if identifiant == _chutier.IDENTIFIANT_RACINE else identifiant
        )
        self._contexte = identifiant
        self.arbre_arborescence.designer(identifiant)
        self._rafraichir_le_chutier()
        if self._survol_actif:
            self.fermer_survol_arborescence()

    def designer_dans_le_chutier(self, identifiant):
        """UN CLIC DANS LE CHUTIER DESIGNE, SANS TOUCHER A LA PORTEE.

        `EPIC7-ARB-84` : « le panneau de droite du chutier est cense
        conserver son arborescence complete au niveau choisi sur le panneau
        de gauche ». La ligne cliquee est mise en evidence et devient le
        contexte ; ce que le chutier montre ne bouge pas d'un cran.
        """
        self._contexte = identifiant
        self.chutier.arbre.designer(identifiant)

    def ouvrir(self, identifiant):
        """UN DOUBLE-CLIC A GAUCHE OUVRE : l'atelier ou l'objet est *en jeu*.

        Carte fixee par Egan (`EPIC7-ARB-11`), lue de
        ``modele_chutier.ATELIER_PAR_TYPE`` : rush -> Extraction, lot -> Pdf,
        planche -> Pdf, scan -> Scan, lot reconstruit -> Exports, rush
        encode -> Exports. A la vague 2 les ateliers sont des coquilles :
        ouvrir = activer l'onglet de destination avec l'objet designe pour
        contexte.

        Depuis le panneau de GAUCHE, ouvrir fixe aussi la portee : c'est le
        panneau qui la fixe, et un double-clic y contient un clic.
        """
        return self._ouvrir(identifiant, fixe_la_portee=True)

    def ouvrir_depuis_le_chutier(self, identifiant):
        """UN DOUBLE-CLIC DANS LE CHUTIER OUVRE, sans redefinir la portee.

        Le pendant exact de `designer_dans_le_chutier` (`EPIC7-ARB-84`) :
        sans lui, le correctif serait a moitie fait -- `ouvrir` appelle
        `designer`, donc un double-clic dans le chutier rabattait la portee
        aussi surement qu'un simple clic.
        """
        return self._ouvrir(identifiant, fixe_la_portee=False)

    def _ouvrir(self, identifiant, *, fixe_la_portee):
        noeud = _modele.noeud_par_identifiant(self._racines, identifiant)
        if noeud is None:
            return None
        if fixe_la_portee:
            self.designer(identifiant)
        else:
            self.designer_dans_le_chutier(identifiant)
        cle = _modele.ATELIER_PAR_TYPE[noeud.type]
        self.activer_atelier(ORDRE_ATELIERS.index(cle))
        # Ouvrir un SCAN, c'est demander a le juger : la page du Scan passe a
        # son second temps, sur la planche ouverte (`EXPERIENCE.md`). Aucun
        # autre type d'objet ne l'y mene, et la page reste au premier temps
        # quand le document du scan est introuvable ou illisible -- montrer
        # une surface de jugement vide serait pire que ne rien changer.
        if noeud.type == _modele.TYPE_SCAN:
            self.juger_ce_scan(noeud)
        return cle

    # --- Second temps de l'atelier Scan : juger (story 7.4) -------------

    def montrer_le_premier_temps_du_scan(self):
        """Ramener la page du Scan a son premier temps (deposer, detecter)."""
        self.temps_du_scan.setCurrentWidget(self.atelier_scan)

    def temps_du_scan_courant(self):
        """Le widget de temps visible sur la page du Scan."""
        return self.temps_du_scan.currentWidget()

    def poser_le_fournisseur_de_rasters(self, fournisseur):
        """Poser la source d'images du second temps, et EN DERIVER la bascule.

        La disponibilite de la variante corrigee n'est pas une valeur ecrite
        ici : elle est **demandee au fournisseur**. C'est ce qui fait que la
        bascule de l'en-tete est grisee tant qu'aucune image corrigee n'existe
        (le cas de tout le depot au 2026-08-25) sans qu'aucun ecran n'ait a en
        juger localement (`EPIC7-ARB-69`).
        """
        self.atelier_jugement.poser_fournisseur(fournisseur)
        self.preference_image.poser_disponibilite(
            fournisseur is not None
            and fournisseur.variante_disponible(_raster.IMAGE_CORRIGEE)
        )
        self.bascule_image.rafraichir()

    def juger_ce_scan(self, noeud):
        """Poser la planche de ce noeud de scan sur la surface de jugement.

        **Lecture seule de bout en bout** : le document de detection est relu
        du DISQUE (jamais d'un etat de session, `EPIC7-ARB-49`), le
        fournisseur de rasters ne fait que lire, et rien n'est ecrit nulle
        part. Rend vrai quand la surface a effectivement change de temps.
        """
        empreinte = noeud.detail.get("empreinte_detection")
        document = self._document_de_detection(empreinte)
        if document is None:
            return False
        try:
            page = document.page_par_adresse(noeud.read_rank, noeud.page_index)
        except KeyError:
            return False
        # Le dpi de rendu est celui que le DOCUMENT declare : un dpi constant
        # cote GUI ferait diverger l'apercu de la geometrie resolue par le
        # coeur.
        self.poser_le_fournisseur_de_rasters(
            self.fabrique_de_fournisseur(
                self._project_dir, document.previz.subject.scan_dpi_detection
            )
        )
        self.atelier_jugement.poser_document(document, page)
        self.temps_du_scan.setCurrentWidget(self.atelier_jugement)
        return True

    def _document_de_detection(self, empreinte):
        """Le document de detection de cette empreinte, relu du disque.

        L'empreinte est l'identite d'une detection -- c'est elle, et pas la
        position d'un fichier, qui apparie un noeud de scan a son document :
        deux detections du meme lot cohabitent legitimement dans le dossier.
        Un fichier que le lecteur normatif refuse est **saute**, jamais avale
        en une surface vide.
        """
        if self._project_dir is None or not empreinte:
            return None
        for chemin in _chargeur.chemins_de_documents(self._project_dir):
            try:
                document = _lecture.charger(chemin)
            except _lecture.LectureDetectionError:
                continue
            if document.previz.fingerprints.detection == empreinte:
                return document
        return None

    def _rafraichir_le_chutier(self):
        """Reporter la portee courante dans l'en-tete et le contenu."""
        noeud = _chutier.noeud_de_la_portee(self._racines, self._designation)
        enfants = _chutier.enfants_de_la_portee(self._racines, self._designation)
        self.chutier.poser_portee(noeud, enfants)
        self.refleter_la_selection()

    # --- Plein ecran du chutier ----------------------------------------

    @property
    def plein_ecran_chutier_actif(self):
        """Vrai quand le chutier occupe la bande entre en-tete et onglets."""
        return self._plein_ecran_chutier

    def basculer_plein_ecran_chutier(self):
        """Basculer le mode plein ecran du chutier, distinct de la fenetre.

        **Le plein ecran masque la SCENE, et rien d'autre** (`EPIC7-ARB-86`,
        2026-08-27). Il repliait aussi l'arborescence, memorisait son etat et
        le restituait a la sortie : le mecanisme etait correct, c'est son
        principe qui a ete refuse. Egan : « Utiliser le bouton de plein ecran
        sur le chutier passe l'arborescence en mode reduit par defaut. Il faut
        qu'il reste dans l'etat ou il etait avant le clic. » L'arborescence
        garde donc l'etat qu'elle avait, replie ou ouvert, et la
        memorisation/restitution de cet etat a disparu avec son objet.

        Ce qui RESTE memorise : les largeurs du splitter, rendues valeur pour
        valeur a la sortie. Elles, le plein ecran les ecrase vraiment.

        La barre d'onglets reste dans les deux etats (`DESIGN.md`, Layout).
        """
        if not self._plein_ecran_chutier:
            self.fermer_survol_arborescence()
            tailles = self.splitter.sizes()
            self._geometrie_avant_plein_ecran = list(tailles)
            self._plein_ecran_chutier = True
            self.scene.setVisible(False)
            # C'est au CHUTIER que revient la bande liberee par la scene, et a
            # lui seul. Masquer un enfant ne suffit pas a le dire : `QSplitter`
            # repartit la largeur rendue entre les enfants restants, et il la
            # coupe en DEUX -- mesure sur le banc offscreen, panneau ouvert :
            # le panneau d'arborescence passait de `tree-panel-width` a la
            # MOITIE de la fenetre, au moment precis ou l'operatrice demande a
            # voir le chutier en grand. Le chiffre exact est dans le test qui
            # porte la mesure. On repose donc
            # les tailles : le panneau garde la SIENNE, le chutier absorbe
            # exactement ce que la scene laisse (`EPIC7-ARB-86` : « le plein
            # ecran masque la SCENE, et rien d'autre »).
            if len(tailles) == 3:
                # La POIGNEE de la scene disparait avec elle : la largeur
                # disponible augmente d'autant, et `QSplitter` distribue cet
                # excedent -- au panneau. Le chutier la reclame donc lui-meme,
                # sans quoi le panneau grandissait de cinq pixels a chaque
                # passage en plein ecran, et `_memoriser_la_largeur_ouverte`
                # finissait par retenir cette derive comme un reglage de
                # l'operatrice : mesure sur six allers-retours avec repli, une
                # largeur de poignee gagnee par tour, sans borne.
                self.splitter.setSizes([
                    tailles[0],
                    tailles[1] + tailles[2] + jetons.ESPACEMENTS["splitter-width"],
                    0,
                ])
        else:
            self._plein_ecran_chutier = False
            self.scene.setVisible(True)
            if self._geometrie_avant_plein_ecran is not None:
                self.splitter.setSizes(self._geometrie_avant_plein_ecran)
                self._geometrie_avant_plein_ecran = None
            # APRES `setSizes`, jamais avant : les tailles rendues sont celles
            # d'avant le plein ecran, et le panneau a pu se replier ENTRE-TEMPS
            # (le rail est actionnable dans tous les regimes, `EPIC7-ARB-93`).
            # On rendait alors `tree-panel-width` a un rail, ce qui est
            # exactement le vide entre le rail et le chutier dont le retour
            # de terrain parle -- « il faut la recoller manuellement ».
            # Recoller ici couvre le cas symetrique aussi --
            # deplie pendant le plein ecran, replie avant.
            self._recoller_la_poignee()
        self.chutier.refleter_le_plein_ecran(self._plein_ecran_chutier)

    # --- L'arborescence par-dessus le chutier --------------------------

    @property
    def survol_arborescence_actif(self):
        """Vrai quand l'arborescence est ouverte PAR-DESSUS le chutier."""
        return self._survol_actif

    def rouvrir_arborescence_depuis_le_rail(self):
        """Le geste du rail : rouvrir l'arborescence, sans jamais rien perdre.

        Deux regimes, et c'est la **place disponible** qui tranche, jamais
        une preference :

        * la place existe -> le panneau se rouvre EN PLACE, comme le socle
          7.0 l'a pose (rien n'est vole au chutier ni a la scene) ;
        * la place manque -> l'arborescence s'ouvre **par-dessus le
          chutier**, « le temps de se placer » : le chutier passe avant elle
          (`EPIC7-ARB-40`), et la scene ne descend jamais sous son plancher.

        Dans les deux cas c'est un **choix explicite** : le seuil de repli
        ne reprend pas la main dessus.

        **Et le geste est REVERSIBLE** (`EPIC7-ARB-93`, 2026-08-27). Pendant
        la superposition, le panneau est sur son rail : le bouton du rail est
        alors le SEUL controle visible de l'arborescence -- celui de repli vit
        dans l'etat ouvert du panneau, qui n'est pas affiche. Rien ne fermait
        donc la superposition sinon designer un objet, et Egan l'a paye :
        « impossible de le reduire. Il faut alors passer en plein ecran et
        cliquer sur l'ancrage pour qu'il se remette a sa place. » Le meme
        bouton referme ce qu'il a ouvert.
        """
        if self._survol_actif:
            self.fermer_survol_arborescence()
            return
        if not self.panneau_arborescence.est_repliee:
            return
        # Trouvee par la revue de vague 2, sur le cas « replie PAR le plein
        # ecran » : celui-la n'existe plus (`EPIC7-ARB-86`, le plein ecran ne
        # touche plus a l'arborescence), mais l'etat que la garde protege,
        # lui, reste atteignable -- replier a la main, PUIS passer en plein
        # ecran. Sans elle, le rail rouvrait le panneau EN PLACE tandis que
        # `_plein_ecran_chutier` restait vrai et que la scene restait masquee:
        # deux mecanismes d'exclusivite composes en un etat qu'aucun des deux
        # ne decrit. En plein ecran la reponse est celle de la spine -- « le
        # rail rouvre l'arborescence PAR-DESSUS le chutier, le temps de se
        # placer » (`EPIC7-ARB-40`) --, jamais en place: ouvrir en place
        # volerait au chutier la bande que le plein ecran vient de lui donner.
        if (
            not self._plein_ecran_chutier
            and self.width() >= self._plancher_fenetre_ouverte()
        ):
            self.deplier_arborescence()
            return
        self._choix_arborescence = True
        self._repli_automatique = False
        self._survol_actif = True
        # Le bouton de repli part AVEC l'arbre : le geste de fermeture doit
        # rester atteignable dans ce regime aussi (`EPIC7-ARB-93`, volet b).
        self.superposition_arborescence.accueillir(
            self.arbre_arborescence, self.panneau_arborescence.bouton_replier)
        self._placer_la_superposition()

    def fermer_survol_arborescence(self):
        """Rendre l'arbre au panneau et refermer la superposition."""
        if not self._survol_actif:
            return
        self._survol_actif = False
        self.superposition_arborescence.rendre(
            self.arbre_arborescence, self.panneau_arborescence.poser_contenu
        )
        self.panneau_arborescence.reprendre_le_bouton_de_repli()

    def _placer_la_superposition(self):
        """Poser la superposition SUR le chutier, a la largeur du panneau."""
        e = jetons.ESPACEMENTS
        bande = self.superposition_arborescence.parentWidget()
        if bande is None:
            return
        gauche = self.panneau_arborescence.x() + self.panneau_arborescence.width()
        largeur = min(e["tree-panel-width"], max(0, bande.width() - gauche))
        self.superposition_arborescence.setGeometry(
            gauche, 0, largeur, bande.height()
        )
        self.superposition_arborescence.raise_()

    def _plancher_fenetre_ouverte(self):
        """Largeur de fenetre minimale pour ouvrir l'arborescence EN PLACE.

        Plancher de l'arborescence + deux poignees + plancher du chutier +
        plancher de la scene. En dessous, ouvrir en place mordrait
        `stage-min-width`, que ce module enonce comme « jamais franchi ».
        """
        e = jetons.ESPACEMENTS
        return max(
            e["window-min-width"],
            e["tree-panel-min-width"]
            + 2 * e["splitter-width"]
            + e["bin-min-width"]
            + e["stage-min-width"],
        )

    def _plancher_fenetre(self):
        """Largeur minimale REELLE de la fenetre, selon l'etat du panneau.

        Le jeton statique ``window-min-width`` (960) suppose le panneau
        d'arborescence REPLIE (rail, 42 px). Ouvert -- par defaut ou par
        choix explicite --, le besoin reel est plus grand : plancher de
        l'arborescence + deux poignees de splitter + plancher du chutier +
        plancher de la scene. Sans ce recalcul, un choix explicite
        d'ouverture pris a la largeur minimale pousse la scene hors de la
        fenetre : ``stage-min-width`` (le plancher que ce module enonce
        lui-meme comme « jamais franchi ») etait alors demande sur 1060 px
        pour 960 px disponibles -- reproduit par l'Edge Case Hunter de la
        revue de vague 1.
        """
        e = jetons.ESPACEMENTS
        if self.panneau_arborescence.est_repliee:
            return e["window-min-width"]
        return self._plancher_fenetre_ouverte()

    def _appliquer_plancher_fenetre(self):
        """Recalculer le plancher de fenetre et grandir si le besoin excede.

        `setMinimumWidth` seul empeche l'operatrice de redescendre SOUS le
        plancher par un futur redimensionnement ; il ne fait rien pour une
        fenetre DEJA plus etroite que le nouveau plancher au moment du
        geste -- d'ou le `resize()` explicite quand c'est le cas.
        """
        plancher = self._plancher_fenetre()
        self.setMinimumWidth(plancher)
        if self.width() < plancher:
            self.resize(plancher, self.height())

    def eventFilter(self, objet, evenement):  # noqa: N802 (API Qt)
        """Recoller la poignee apres une disposition differee du splitter.

        **Uniquement quand le panneau est REPLIE** : ouvert, c'est le
        splitter qui dit la verite -- forcer une largeur ici defairait le
        geste de l'operatrice au moment meme ou elle tire la poignee.
        """
        if (
            objet is self.zone_chutier
            and evenement.type() == QEvent.Type.Resize
            and self.panneau_arborescence.est_repliee
        ):
            self._recoller_la_poignee()
        return super().eventFilter(objet, evenement)

    def resizeEvent(self, evenement):
        super().resizeEvent(evenement)
        if self._survol_actif:
            self._placer_la_superposition()
        if self._plein_ecran_chutier:
            # Le mode plein ecran est un choix explicite : le seuil de repli
            # ne le defait pas en rouvrant l'arborescence par-dessus lui.
            self.setMinimumWidth(self._plancher_fenetre())
            return
        seuil = jetons.ESPACEMENTS["tree-collapse-threshold"]
        sous_le_seuil = self.width() < seuil
        panneau = self.panneau_arborescence
        if sous_le_seuil:
            # Sous le seuil le panneau se replie SEUL, sans message
            # (EPIC7-ARB-8) -- sauf si l'operateur l'a ouvert par geste :
            # le seuil fixe le defaut, il ne reprend pas la main.
            if not panneau.est_repliee and self._choix_arborescence is not True:
                self._poser_l_arborescence(repliee=True)
                self._repli_automatique = True
        else:
            # Au-dessus du seuil on ne rouvre que ce que le seuil avait
            # replie : un repli choisi par l'operateur reste replie.
            if panneau.est_repliee and self._repli_automatique:
                self._poser_l_arborescence(repliee=False)
                self._repli_automatique = False
        # Le plancher suit l'etat courant du panneau. On ne fait ici que
        # RESSERRER ou RELACHER la borne (`setMinimumWidth`) -- jamais de
        # `resize()` depuis un `resizeEvent` (recursion) : le seul chemin
        # qui grandit la fenetre est le geste explicite ci-dessus, deja
        # hors de cet evenement.
        self.setMinimumWidth(self._plancher_fenetre())


# ---------------------------------------------------------------------------
# Bascule brut / corrige -- preference GLOBALE (story 7.4, AC 8)
#
# `EPIC7-ARB-69`, verbatim : « Aucun ecran ne porte sa propre bascule locale,
# ni un etat de calibration qui lui soit propre. » L'etat vit ici, une fois,
# et tout ecran qui affiche une image scannee le LIT -- mode PDF, galerie et
# vue vignette unique en 7.4 ; le lecteur et les planches aux stories
# suivantes. Aucun ecran n'en tient une copie.
#
# Frontiere de coeur : cette bascule choisit **quelle image deja produite**
# est affichee. Elle n'en calcule aucune, n'applique aucune LUT, n'ecrit
# rien -- le pipeline couleur n'est pas touche.
# ---------------------------------------------------------------------------


class PreferenceDImage(QObject):
    """La variante d'image affichee, pour toute l'application.

    Un seul etat, un seul signal. La disponibilite de la source corrigee est
    portee ici aussi, parce qu'elle conditionne la bascule et qu'un ecran qui
    en jugerait localement recreerait l'etat local que l'arbitrage interdit.
    """

    variante_changee = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._variante = _raster.IMAGE_BRUTE
        self._source_corrigee_disponible = False

    @property
    def variante(self):
        return self._variante

    @property
    def source_corrigee_disponible(self):
        """Existe-t-il une image corrigee pour ce qui est affiche ?

        Faux tant qu'aucune n'a ete produite -- ce qui est le cas de tout le
        depot au 2026-08-25, la calibration active etant post-MVP
        (`EPIC5-ARB-5`). La bascule est alors **grisee et presente**, jamais
        absente : « le critere est la reversibilite, pas la disponibilite a
        l'instant t » (`EPIC7-ARB-24`).
        """
        return self._source_corrigee_disponible

    def poser_disponibilite(self, disponible):
        """Declarer si une source corrigee existe pour le lot affiche.

        Retirer la source alors que la variante corrigee est active ramene a
        l'image brute : garder une variante sans source afficherait un vide
        la ou l'operateur attend une image.
        """
        self._source_corrigee_disponible = bool(disponible)
        if not self._source_corrigee_disponible:
            self.poser_variante(_raster.IMAGE_BRUTE)

    def poser_variante(self, variante):
        if variante not in _raster.VARIANTES_D_IMAGE:
            raise ValueError(f"variante d'image inconnue : {variante!r}")
        if variante == _raster.IMAGE_CORRIGEE and not self._source_corrigee_disponible:
            return
        if variante == self._variante:
            return
        self._variante = variante
        self.variante_changee.emit(variante)

    def basculer(self):
        """Passer d'une variante a l'autre. Sans source corrigee : rien."""
        cible = (
            _raster.IMAGE_BRUTE
            if self._variante == _raster.IMAGE_CORRIGEE
            else _raster.IMAGE_CORRIGEE
        )
        self.poser_variante(cible)


class BasculeDImage(QPushButton):
    """Le controle d'en-tete de la bascule brut / corrige.

    Son icone est lue de `jetons.ICONOGRAPHIE` -- **aucun glyphe litteral
    ici** --, et son libelle du catalogue. Sans source corrigee elle est
    GRISEE et PRESENTE, et l'infobulle dit pourquoi.
    """

    def __init__(self, preference, chaines, parent=None):
        super().__init__(jetons.ICONOGRAPHIE["glyphe-bascule-image"], parent)
        self.setObjectName("bascule-image")
        self._preference = preference
        self._chaines = chaines
        self.setCheckable(True)
        self.setFixedHeight(jetons.ESPACEMENTS["hit-min"])
        self.setStyleSheet(
            f"font-size: {jetons.ICONOGRAPHIE['glyphe-bascule-image-px']}px;"
        )
        self.clicked.connect(lambda _coche=False: self._preference.basculer())
        preference.variante_changee.connect(self._refleter)
        self._refleter(preference.variante)

    def _refleter(self, variante):
        disponible = self._preference.source_corrigee_disponible
        self.setEnabled(disponible)
        self.setChecked(variante == _raster.IMAGE_CORRIGEE)
        libelle = self._chaines[
            "image-variante-corrigee"
            if variante == _raster.IMAGE_CORRIGEE
            else "image-variante-brute"
        ]
        if disponible:
            self.setToolTip(f"{self._chaines['image-bascule-brut-corrige']} — {libelle}")
        else:
            self.setToolTip(self._chaines["image-bascule-indisponible"])
        self.setAccessibleName(self.toolTip())

    def rafraichir(self):
        """Relire la disponibilite (elle change avec le lot affiche)."""
        self._refleter(self._preference.variante)
