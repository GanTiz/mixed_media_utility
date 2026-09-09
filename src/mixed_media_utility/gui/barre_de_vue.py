# -*- coding: utf-8 -*-
"""Controles de vue et onglets de vue (story 7.4, AC 5).

**UN composant, pas trois reglages** (correction ``A10``) : « Un jeu de
controles de vue commun a toutes les surfaces d'image [...] c'est donc un
composant, pas trois reglages. » :class:`BarreDeVue` est instanciee par les
trois surfaces d'image de cette story -- mode PDF, galerie, vue vignette
unique -- et le sera par 7.6 (lecteur), 7.9 (Extraction) et 7.10 (Pdf) : elle
vit donc dans un module partageable de ``gui/``, pas dans celui de l'atelier
Scan.

Le bouton d'ajustement s'intitule **« ajuster »**, et non « largeur »
(``EPIC7-ARB-17``) ; comme tous les autres, son libelle est **lu du
catalogue**, jamais ecrit en dur dans un ecran.

Les controles sont **au-dessus** de la scene : « rien d'autre n'entre dans le
cadre du ``viewer-stage`` » (``EXPERIENCE.md``).

Onglets de vue (``EPIC7-ARB-24``) : « un onglet sans objet est **absent** »,
« un controle temporairement indisponible est **grise** ». Le critere est la
**reversibilite**, pas la disponibilite a l'instant t -- d'ou deux mecanismes
distincts et jamais interchangeables : :meth:`OngletsDeVue.poser_onglets`
pour ce qui n'a pas d'objet, ``setEnabled`` pour ce qui en a un mais ne peut
pas servir maintenant.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QSlider, QTabBar

from . import jetons

#: Les cinq controles de vue, dans l'ordre de la correction ``A10``. La cle
#: est aussi la cle de catalogue (prefixee ``vue-``) : un controle sans
#: libelle au catalogue est impossible a instancier.
CONTROLE_ZOOM = "zoom"
CONTROLE_AJUSTER = "ajuster"
CONTROLE_PLEINE_LARGEUR = "pleine-largeur"
CONTROLE_PLEINE_HAUTEUR = "pleine-hauteur"
CONTROLE_TAILLE_REELLE = "taille-reelle"

CONTROLES_DE_VUE: tuple[str, ...] = (
    CONTROLE_ZOOM,
    CONTROLE_AJUSTER,
    CONTROLE_PLEINE_LARGEUR,
    CONTROLE_PLEINE_HAUTEUR,
    CONTROLE_TAILLE_REELLE,
)

#: Les boutons, c'est-a-dire les controles moins le zoom, qui est continu.
BOUTONS_DE_VUE: tuple[str, ...] = CONTROLES_DE_VUE[1:]

#: Bornes du zoom, en pourcents. Continu, **sans paliers**
#: (``EXPERIENCE.md``, Interaction Primitives) : un `QSlider` sans pas de page
#: ni graduations, et non une liste de facteurs.
ZOOM_MIN_POURCENT = 10
ZOOM_MAX_POURCENT = 400
ZOOM_DEFAUT_POURCENT = 100

#: Les onglets de vue de cette story. `lecteur` n'y est pas : c'est 7.6.
ONGLET_PAGE = "page"
ONGLET_GALERIE = "galerie"
ONGLET_FRAME = "frame"

ONGLETS_DE_VUE: tuple[str, ...] = (ONGLET_PAGE, ONGLET_GALERIE, ONGLET_FRAME)


class BarreDeVue(QFrame):
    """Les cinq controles de vue. **Une seule implementation dans le depot.**"""

    zoom_change = Signal(int)
    controle_active = Signal(str)

    def __init__(self, chaines, parent=None):
        super().__init__(parent)
        self.setObjectName("barre-de-vue")
        self._chaines = chaines
        espacements = jetons.ESPACEMENTS
        self.couleurs_posees = (jetons.COULEURS["surface-panel"],)
        self.setStyleSheet(
            f"#barre-de-vue {{ background: {jetons.COULEURS['surface-panel']}; }}"
        )
        ligne = QHBoxLayout(self)
        ligne.setContentsMargins(
            espacements["panel-pad"], espacements["3"],
            espacements["panel-pad"], espacements["3"],
        )
        ligne.setSpacing(espacements["gutter"])

        #: Le zoom, continu. `setPageStep(1)` et aucune graduation : les
        #: paliers sont explicitement bannis par les Interaction Primitives.
        self.zoom = QSlider(Qt.Orientation.Horizontal, self)
        self.zoom.setObjectName("vue-zoom")
        self.zoom.setRange(ZOOM_MIN_POURCENT, ZOOM_MAX_POURCENT)
        self.zoom.setValue(ZOOM_DEFAUT_POURCENT)
        self.zoom.setSingleStep(1)
        self.zoom.setPageStep(1)
        self.zoom.setTickPosition(QSlider.TickPosition.NoTicks)
        self.zoom.setToolTip(chaines["vue-zoom"])
        self.zoom.setAccessibleName(chaines["vue-zoom"])
        self.zoom.valueChanged.connect(self.zoom_change.emit)
        ligne.addWidget(self.zoom, 1)

        #: Les quatre boutons, par cle. `ajuster` est le premier : c'est le
        #: geste par defaut d'une surface d'image.
        self.boutons: dict[str, QPushButton] = {}
        for cle in BOUTONS_DE_VUE:
            bouton = QPushButton(chaines[f"vue-{cle}"], self)
            bouton.setObjectName(f"vue-{cle}")
            bouton.setMinimumHeight(espacements["hit-min"])
            bouton.clicked.connect(
                lambda _coche=False, cle=cle: self.controle_active.emit(cle)
            )
            self.boutons[cle] = bouton
            ligne.addWidget(bouton, 0)

    @property
    def controles(self) -> dict[str, object]:
        """Les cinq controles par cle -- le zoom compris."""
        return {CONTROLE_ZOOM: self.zoom, **self.boutons}

    def accorder_le_zoom(self, pourcent) -> None:
        """Poser le curseur sur un facteur DEJA applique, sans le reemettre.

        Appelee apres « ajuster », « pleine largeur », « pleine hauteur » ou
        « taille reelle », qui changent le facteur reel sans passer par le
        curseur. Sans elle, le curseur resterait a 100 % pendant que l'image en
        fait 180 -- il mentirait sur l'etat de la vue.

        Le signal est BLOQUE le temps de la pose : le laisser partir ferait
        redemander a la scene son propre facteur, arrondi au pourcent, et
        « taille reelle » ne serait plus exacte (elle vaut rarement un compte
        rond). C'est le seul endroit du module ou un signal est bloque, et il
        l'est pour cette raison-la.
        """
        valeur = max(ZOOM_MIN_POURCENT, min(ZOOM_MAX_POURCENT, int(pourcent)))
        precedent = self.zoom.blockSignals(True)
        try:
            self.zoom.setValue(valeur)
        finally:
            self.zoom.blockSignals(precedent)

    def libelle(self, cle: str) -> str:
        """Le libelle affiche d'un controle, tel que le catalogue le donne."""
        return self._chaines[f"vue-{cle}"]

    def griser(self, cle: str, indisponible: bool = True) -> None:
        """Griser un controle **sans le retirer** (``EPIC7-ARB-24``).

        Un controle temporairement indisponible est grise et PRESENT : le
        retirer effacerait la trace de ce qui redeviendra possible.
        """
        self.controles[cle].setEnabled(not indisponible)


def feuille_des_onglets() -> str:
    """La feuille des onglets de vue, composee des SEULS jetons de la spine.

    **Ce qu'elle corrige, et pourquoi ce n'etait pas un defaut de cablage.**
    L'exclusivite des vues est reelle depuis 7.4 -- ``AtelierScanJugement``
    porte un ``QStackedWidget``, une vue et une seule est montee a la fois.
    Ce que l'essai de terrain du 2026-08-27 a vu (« l'ecran galerie semble se
    comporter comme un panneau lateral alors qu'il est cense etre un onglet
    qui remplace la vue pdf ») est un defaut de **chrome** : la feuille
    d'application ne distingue l'onglet courant que par la couleur de son
    TEXTE (``text-secondary`` -> ``text-primary``), soit le seul signe qu'une
    capture ne montre pas et qu'un oeil ne cherche pas. Deux libelles poses
    aux deux bouts d'une barre pleine largeur, sans fond ni liseré, ne se
    lisent pas comme des onglets exclusifs.

    Trois signes, donc, et aucun n'est chromatique seul : l'onglet courant
    porte un **fond leve** (``surface-raised``, la surface des controles), son
    **texte passe au primaire**, et un **liseré d'accent** court sous lui.
    L'accent est ici une valeur de TRAIT, jamais un aplat sous du texte --
    c'est la regle des chromies pleines de ``DESIGN.md``.

    **Jeton manquant, nomme comme tel** : la spine ne porte aucune epaisseur
    de liseré. ``ESPACEMENTS["1"]`` (2 px) est employe faute de mieux -- c'est
    une composition a partir de l'existant, pas une valeur inventee, et
    ``jetons.py`` est hors du perimetre de ce correctif. Une epaisseur de
    trait dediee serait plus juste.
    """
    n = jetons.NEUTRES
    a = jetons.ACCENT
    e = jetons.ESPACEMENTS
    r = jetons.RAYONS
    return (
        f"QTabBar#onglets-de-vue {{ background: {n['surface-panel']}; }}"
        f" QTabBar#onglets-de-vue::tab {{"
        f" background: {n['surface-panel']};"
        f" color: {n['text-secondary']};"
        f" padding: {e['3']}px {e['6']}px;"
        f" margin-right: {e['1']}px;"
        f" border: none;"
        f" border-top-left-radius: {r['sm']}px;"
        f" border-top-right-radius: {r['sm']}px;"
        # Un liseré de la MEME couleur que le fond sur l'onglet au repos : il
        # reserve la place du liseré d'accent, sinon l'onglet courant serait
        # plus haut que les autres et la barre sauterait a chaque changement.
        f" border-bottom: {e['1']}px solid {n['surface-panel']}; }}"
        f" QTabBar#onglets-de-vue::tab:hover {{"
        f" background: {n['surface-hover']};"
        f" color: {n['text-primary']}; }}"
        f" QTabBar#onglets-de-vue::tab:selected {{"
        f" background: {n['surface-raised']};"
        f" color: {n['text-primary']};"
        f" border-bottom: {e['1']}px solid {a['accent']}; }}"
    )


class OngletsDeVue(QTabBar):
    """Les onglets de vue : absents sans objet, jamais grises.

    ``EPIC7-ARB-24`` : « un onglet sans objet est absent » ; le critere est la
    **reversibilite**. Un onglet ``frame`` sans vignette ouverte n'est pas un
    controle temporairement indisponible : il n'a **rien** a montrer, donc il
    n'existe pas -- jusqu'a ce qu'une vignette lui donne son objet.

    Ils se LISENT comme des onglets exclusifs : « c'est OU pdf OU galerie OU
    lecteur » (essai de terrain du 2026-08-27). Le chrome qui le dit est dans
    :func:`feuille_des_onglets` ; l'exclusivite elle-meme est celle du
    ``QStackedWidget`` de l'atelier, et elle n'a pas change.
    """

    vue_changee = Signal(str)

    def __init__(self, chaines, parent=None):
        super().__init__(parent)
        self.setObjectName("onglets-de-vue")
        self._chaines = chaines
        self._cles: list[str] = []
        # **Les onglets ne s'etalent pas d'un bout a l'autre de l'ecran.**
        # `expanding` vaut vrai par defaut chez Qt : deux onglets se
        # partageaient alors toute la largeur de l'atelier, ce qui les faisait
        # lire comme deux en-tetes de panneau plutot que comme deux onglets.
        # Ils prennent desormais la largeur de leur libelle, alignes a gauche.
        self.setExpanding(False)
        # La base native de la barre se peint au style de la plateforme -- le
        # meme defaut que les fleches et les poignees de la passe de chrome du
        # 2026-08-26. Le fond de la barre vient de la feuille, pas de Qt.
        self.setDrawBase(False)
        self.setStyleSheet(feuille_des_onglets())
        self.currentChanged.connect(self._relayer)
        self.poser_onglets((ONGLET_PAGE, ONGLET_GALERIE))

    def poser_onglets(self, cles) -> None:
        """Poser exactement ces onglets, dans cet ordre.

        La vue courante est conservee si elle survit ; sinon on retombe sur
        le premier onglet -- jamais sur un onglet qui n'existe plus.
        """
        cles = tuple(cles)
        if cles == tuple(self._cles):
            return
        courante = self.vue_courante()
        self.blockSignals(True)
        while self.count():
            self.removeTab(self.count() - 1)
        for cle in cles:
            self.addTab(self._chaines[f"scan-onglet-{cle}"])
        self._cles = list(cles)
        self.blockSignals(False)
        if courante in cles:
            self.setCurrentIndex(cles.index(courante))
        elif cles:
            self.setCurrentIndex(0)

    @property
    def cles(self) -> tuple[str, ...]:
        """Les cles des onglets PRESENTS, dans l'ordre affiche."""
        return tuple(self._cles)

    def vue_courante(self) -> str | None:
        indice = self.currentIndex()
        if 0 <= indice < len(self._cles):
            return self._cles[indice]
        return None

    def activer(self, cle: str) -> None:
        """Passer sur cet onglet ; ``KeyError`` s'il n'est pas present."""
        if cle not in self._cles:
            raise KeyError(f"onglet de vue absent : {cle!r}")
        self.setCurrentIndex(self._cles.index(cle))

    def _relayer(self, _indice) -> None:
        courante = self.vue_courante()
        if courante is not None:
            self.vue_changee.emit(courante)


__all__ = [
    "BOUTONS_DE_VUE",
    "BarreDeVue",
    "CONTROLES_DE_VUE",
    "CONTROLE_AJUSTER",
    "CONTROLE_PLEINE_HAUTEUR",
    "CONTROLE_PLEINE_LARGEUR",
    "CONTROLE_TAILLE_REELLE",
    "CONTROLE_ZOOM",
    "ONGLETS_DE_VUE",
    "ONGLET_FRAME",
    "ONGLET_GALERIE",
    "ONGLET_PAGE",
    "OngletsDeVue",
    "ZOOM_DEFAUT_POURCENT",
    "ZOOM_MAX_POURCENT",
    "ZOOM_MIN_POURCENT",
    "feuille_des_onglets",
]
