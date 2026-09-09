# -*- coding: utf-8 -*-
"""Le chutier a deux panneaux (story 7.2) -- composants Qt.

« On designe a gauche, on lit a droite » (`EPIC7-ARB-40`, modele
``key-chutier-v2.html``) : le **panneau d'arborescence** sert a se placer, le
**chutier** montre le contenu de l'objet designe. Le chutier reste un arbre --
le panneau fixe la portee, il ne remplace pas la filiation.

Ce module ne porte **aucune** valeur de geometrie ni de couleur : toutes se
lisent de ``jetons``, tous les libelles visibles de ``catalogue``. Deux
frontieres negatives le mesurent (zero largeur de ``DESIGN.md`` en dur, zero
hexadecimal hors du module de jetons).

**Les deux familles de signes ne se confondent jamais** (``DESIGN.md``,
correction du 2026-08-23) :

* la **completude** d'un lot est un `badge-state` -- :class:`BadgeDeCompletude`,
  fond a 16 % compose sur la surface porteuse, texte en variante ``-text``,
  et une **forme** (disque plein / anneau creux / disque hachure) pour que la
  couleur ne porte jamais seule ;
* le **rattachement** d'un objet est un `state-glyph` -- :class:`GlypheDeRattachement`,
  trois glyphes qui appellent chacun un geste (retrouver / identifier /
  completer), dits en bulle au survol.

Les deux sont des controles **distincts** dans l'arbre de widgets : « Fondre
les deux familles dans un seul signe » est un *Don't* de la spine.

**Pictogrammes provisoires.** Aucun jeu d'icones n'est arrete (dependance
nommee de ``DESIGN.md``). Cette story part avec des pictogrammes traces a la
volee, dans la **boite fixee** : ``jetons.ICONOGRAPHIE`` -- 15 x 15 px, trait
1,2 px, couleur du texte courant, jamais un aplat colore. La substitution
future doit rester un remplacement d'assets.
"""

from PySide6.QtCore import QByteArray, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QStyle,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from . import catalogue as _catalogue
from . import jetons
from . import modele_chutier as modele

#: Hauteur de ligne du panneau d'arborescence (`DESIGN.md`,
#: ``bin-tree-panel.row-height``). Elle n'est pas dans le frontmatter
#: ``spacing`` -- la spine l'ecrit sur le composant --, donc elle vit ici,
#: nommee, et non en litteral dans une feuille de style.
_HAUTEUR_LIGNE_ARBORESCENCE = 26


#: Colonnes de l'arbre. Le libelle, puis **deux colonnes distinctes** pour
#: les deux familles de signes -- c'est ce qui rend structurellement
#: impossible de les fondre en un seul signe.
COLONNE_LIBELLE = 0
COLONNE_BADGE = 1
COLONNE_GLYPHE = 2
NOMBRE_DE_COLONNES = 3

#: Nombre de colonnes du PANNEAU d'arborescence (`EPIC7-ARB-94` (a)).
#: Il n'y pose ni badge ni glyphe -- `_poser_les_signes` n'est appele que
#: si `montre_les_signes` --, mais les deux colonnes vides prenaient quand
#: meme leur largeur de section minimale par defaut, soit environ un
#: cinquieme du panneau a sa largeur plancher (`tree-panel-min-width`), et
#: les noms coupes en « rus... » (capture `image-1.png` du 2026-08-27). Une
#: colonne suffit la ou aucun signe ne se pose. **Rien n'est fondu** : les
#: deux colonnes distinctes restent l'invariant de l'emploi qui, lui, montre
#: les signes.
#:
#: La largeur plancher est **nommee et non chiffree** ici, y compris en
#: commentaire : la frontiere de la story 7.2 grep les valeurs de `DESIGN.md`
#: sur tout le fichier, et elle a raison de le faire -- un chiffre recopie
#: dans un commentaire devient faux le jour ou le jeton bouge, sans que rien
#: ne le signale.
NOMBRE_DE_COLONNES_SANS_SIGNES = 1

#: Identifiant de la ligne racine du panneau d'arborescence (`EPIC7-ARB-85`).
IDENTIFIANT_RACINE = "__racine__"

#: Le type de noeud dont la ligne racine EMPRUNTE le pictogramme.
#: `key-chutier-v2.html` dessine la racine (« sequence 3 ») avec un trace de
#: DOSSIER (``M2 4.5h4l1.2 1.5H14v7.5H2z``) qui n'existe pas dans
#: ``jetons.TRACES_DE_NOEUD`` -- aucun type de noeud du modele ne le porte.
#: Plutot que d'inventer une entree de jetons hors du perimetre de cette
#: correction, la ligne racine emprunte le trace le plus proche : le lot,
#: deux dossiers decales, qui dit deja « une collection, pas un fichier ».
#: La substitution reste un remplacement d'asset -- une ligne a changer ici.
TYPE_PICTOGRAMME_RACINE = modele.TYPE_LOT

#: Les trois glyphes de rattachement, verbatim de `DESIGN.md`.
GLYPHES = {
    modele.GLYPHE_DELIE: "⊘",         # maillon brise
    modele.GLYPHE_NON_RATTACHE: "?",  # point d'interrogation
    modele.GLYPHE_INCOMPLET: "⚠",     # panneau d'avertissement
}

#: Couleur de chaque glyphe, par NOM de jeton (jamais une valeur).
JETON_COULEUR_GLYPHE = {
    modele.GLYPHE_DELIE: "state-absent-text",
    modele.GLYPHE_NON_RATTACHE: "text-secondary",
    modele.GLYPHE_INCOMPLET: "state-substitute-text",
}

#: Chromie PLEINE de chaque badge de completude : valeur d'aplat, composee a
#: 16 % sur la surface porteuse. Le TEXTE du badge prend la variante
#: ``-text`` de la meme chromie (plancher 4,5:1).
JETON_CHROMIE_BADGE = {
    modele.BADGE_COMPLET: "state-complete",
    modele.BADGE_COMPLET_AVEC_MIRES: "state-substitute",
    modele.BADGE_INCOMPLET: "state-absent",
}

#: Redondance non chromatique EXIGEE : chaque etat porte aussi une forme.
FORME_BADGE = {
    modele.BADGE_COMPLET: "disque-plein",
    modele.BADGE_COMPLET_AVEC_MIRES: "disque-hachure",
    modele.BADGE_INCOMPLET: "anneau-creux",
}

#: Les trois etats de selection, rendus par les trois etats natifs d'une case
#: a cocher Qt : le troisieme etat est VISIBLE, pas seulement modelise.
COCHE_PAR_ETAT = {
    modele.SELECTION_VIDE: Qt.CheckState.Unchecked,
    modele.SELECTION_PARTIELLE: Qt.CheckState.PartiallyChecked,
    modele.SELECTION_PLEINE: Qt.CheckState.Checked,
}

#: Le glyphe qu'on affiche pour chaque forme, en complement de la couleur.
MARQUE_DE_FORME = {
    "disque-plein": "●",
    "disque-hachure": "◐",
    "anneau-creux": "○",
}


# ---------------------------------------------------------------------------
# Pictogrammes provisoires
# ---------------------------------------------------------------------------


def _document_svg(traces, couleur, cote):
    """Composer le document SVG d'un pictogramme, a partir de ses traces.

    Un trace est soit une chaine (le `d` du chemin), soit un couple
    `(d, pointilles)` -- la maquette dit la reconstruction et le passage du
    capteur par un `stroke-dasharray`, pas par une couleur.
    """
    # `couleur` arrive en `QColor` (c'est ce que rend `_couleur_de_ligne`). Un
    # SVG veut une chaine : l'interpoler telle quelle ecrivait
    # `stroke="<PySide6.QtGui.QColor object at 0x...>"`, document invalide, donc
    # **une icone entierement vide** -- et vide sans lever, ce qui est
    # exactement la classe de defaut que la capture existe pour attraper. Elle
    # l'a attrapee.
    trait = couleur.name() if isinstance(couleur, QColor) else str(couleur)
    chemins = []
    for trace in traces:
        if isinstance(trace, str):
            chemins.append(f'<path d="{trace}"/>')
        else:
            depart, pointilles = trace
            chemins.append(f'<path d="{depart}" stroke-dasharray="{pointilles}"/>')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"'
        f' width="{cote}" height="{cote}" fill="none"'
        f' stroke="{trait}" stroke-width="{jetons.ICONOGRAPHIE["trait-px"]}"'
        f' stroke-linejoin="round" stroke-linecap="round">'
        + "".join(chemins)
        + "</svg>"
    )


def pictogramme(type_de_noeud, couleur):
    """Le pictogramme d'un type de noeud, dans sa boite fixee.

    **Transcrit de la maquette, pas redessine** (2026-08-26). La version
    precedente dessinait a la main -- un rectangle et deux traits pour un rush,
    deux rectangles decales pour un lot -- au motif qu'« aucun jeu d'icones
    n'est arrete ». Elle ne ressemblait a rien : « les icones ne correspondent
    pas du tout a ce qui avait ete maquette » (Egan, premier essai de terrain).
    Or `key-chutier-v2.html` porte les traces EXACTS, en SVG 16x16, trait
    1,2 px, `currentColor` : ils vivent desormais dans
    `jetons.TRACES_DE_NOEUD`, recopies verbatim.

    Trace au trait, **jamais un aplat colore** -- la contrainte de `DESIGN.md`
    porte sur la boite (15x15) et sur le rendu. Un type inconnu ne rend aucune
    icone plutot qu'une icone par defaut qui mentirait sur le niveau.

    Le rendu passe par ``QSvgRenderer`` plutot que par des appels de peinture :
    les chemins restent de la DONNEE, et substituer un jeu d'icones redevient
    ce que l'AC 8 de 7.4 promet -- un remplacement d'assets, sans toucher a la
    mise en page.
    """
    if type_de_noeud not in modele.TYPES_DE_NOEUD:
        return QIcon()
    traces = jetons.TRACES_DE_NOEUD.get(type_de_noeud)
    if not traces:
        return QIcon()
    cote = jetons.ICONOGRAPHIE["boite-px"]
    # Le facteur d'echelle du peripherique : sans lui, l'icone est rendue a
    # 15 px physiques sur un ecran a 150 % et sort floue.
    facteur = QApplication.primaryScreen().devicePixelRatio() if QApplication.instance() else 1.0
    pixmap = QPixmap(int(cote * facteur), int(cote * facteur))
    pixmap.setDevicePixelRatio(facteur)
    pixmap.fill(Qt.GlobalColor.transparent)
    peintre = QPainter(pixmap)
    peintre.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    rendu = QSvgRenderer(
        QByteArray(_document_svg(traces, couleur, cote).encode("utf-8"))
    )
    rendu.render(peintre)
    peintre.end()
    return QIcon(pixmap)


# ---------------------------------------------------------------------------
# Les deux familles de signes -- deux classes, jamais une
# ---------------------------------------------------------------------------


class BadgeDeCompletude(QLabel):
    """FAMILLE 1 -- la completude d'un lot. « Que manque-t-il dans ce lot ? »

    Fond a ``jetons.BADGE_FOND_OPACITE`` de la chromie pleine, **compose sur
    la surface porteuse** ; texte a la variante ``-text``, qui seule tient
    4,5:1 en 11 px. Chaque etat porte AUSSI une forme : rouge et ambre sont
    la paire la plus confusable, et l'outil s'ouvrira a des videastes dont on
    ne connait pas la vision des couleurs.
    """

    def __init__(self, etat, chaines, surface_porteuse=None, parent=None):
        chromie = jetons.COULEURS[JETON_CHROMIE_BADGE[etat]]
        surface = surface_porteuse or jetons.COULEURS["surface-panel"]
        forme = FORME_BADGE[etat]
        libelle = chaines[f"badge-{etat}"]
        # `super().__init__` d'abord : poser un attribut Python sur un QObject
        # dont la base n'est pas encore construite leve a l'execution.
        super().__init__(f"{MARQUE_DE_FORME[forme]} {libelle}", parent)
        self.etat = etat
        self.forme = forme
        self.couleur_texte = jetons.COULEURS[f"{JETON_CHROMIE_BADGE[etat]}-text"]
        self.couleur_fond = jetons.composer_sur(chromie, surface)
        self.setObjectName("badge-state")
        self.setToolTip(libelle)
        typo = jetons.TYPOGRAPHIE["label"]
        self.setStyleSheet(
            f"color: {self.couleur_texte};"
            f" background: {self.couleur_fond};"
            f" border-radius: {jetons.RAYONS['full']}px;"
            f" font-size: {typo['taille']}px;"
            f" padding: 0px {jetons.ESPACEMENTS['3']}px;"
        )


class GlypheDeRattachement(QLabel):
    """FAMILLE 2 -- le rattachement d'un objet. « Que dois-je faire ? »

    Un glyphe en fin de ligne, jamais un badge, jamais une pastille, et une
    bulle au survol qui dit le **geste** : retrouver / identifier /
    completer (`EPIC7-ARB-5`, cas d'usage `EPIC7-ARB-12`).
    """

    def __init__(self, etat, chaines, parent=None):
        super().__init__(GLYPHES[etat], parent)
        self.etat = etat
        self.couleur = jetons.COULEURS[JETON_COULEUR_GLYPHE[etat]]
        self.setObjectName("state-glyph")
        # L'infobulle dit le GESTE, elle est lue du catalogue.
        self.setToolTip(chaines[f"glyphe-{etat}"])
        self.setAccessibleName(chaines[f"glyphe-{etat}"])
        taille = jetons.ICONOGRAPHIE[
            "glyphe-incomplet-px"
            if etat == modele.GLYPHE_INCOMPLET
            else "glyphe-px"
        ]
        typo = jetons.TYPOGRAPHIE["data"]
        self.setStyleSheet(
            f"color: {self.couleur};"
            f" font-family: {typo['famille']};"
            f" font-size: {taille}px;"
        )


# ---------------------------------------------------------------------------
# Composition des libelles -- tout vient du catalogue
# ---------------------------------------------------------------------------


def libelle_de_noeud(noeud, chaines):
    """Le texte affiche d'une ligne de chutier.

    Les identifiants du coeur (``rush_id``, ``lot_id``) s'affichent
    **verbatim** : ce sont des codes, ils ne se traduisent jamais. Les
    planches et les scans portent une phrase du catalogue.

    Les numeros affiches sont ceux que le **document porte** -- ni decales,
    ni renumerotes : `read_rank` et `page_index` sont les valeurs sur
    lesquelles la CLI, les journaux et les documents s'accordent, et
    introduire ici une seconde numerotation ferait diverger l'interface de
    ses sources. La base de numerotation offerte a l'operatrice reste a
    trancher (versee a ``deferred-work.md``).
    """
    if noeud.type == modele.TYPE_PLANCHE:
        return chaines["chutier-planche"].format(planche=noeud.page_index)
    if noeud.type == modele.TYPE_SCAN:
        if noeud.page_index is None:
            return chaines["chutier-scan-non-rattache"].format(rang=noeud.read_rank)
        return chaines["chutier-scan"].format(
            rang=noeud.read_rank, planche=noeud.page_index
        )
    return noeud.identifiant


def cardinaux_par_type(noeuds, chaines):
    """« 2 rushes », « 2 lots · 3 planches » -- dans l'ordre de rencontre.

    Aucun tri : les types apparaissent dans l'ordre ou l'arbre les donne,
    c'est-a-dire dans l'ordre des sources.
    """
    comptes = {}
    for noeud in noeuds:
        comptes[noeud.type] = comptes.get(noeud.type, 0) + 1
    if not comptes:
        return chaines["chutier-cardinal-vide"]
    return chaines["chutier-cardinal-separateur"].join(
        _catalogue.cardinal(type_de_noeud, nombre, chaines)
        for type_de_noeud, nombre in comptes.items()
    )


def texte_de_portee(noeud, enfants, chaines):
    """L'en-tete du chutier : sur quoi porte ce qu'il montre."""
    cardinaux = cardinaux_par_type(enfants, chaines)
    if noeud is None:
        return chaines["chutier-portee-projet"].format(cardinaux=cardinaux)
    return chaines["chutier-portee"].format(
        objet=libelle_de_noeud(noeud, chaines), cardinaux=cardinaux
    )


# ---------------------------------------------------------------------------
# Le lisere de selection -- peint, jamais mis en feuille de style
# ---------------------------------------------------------------------------


class LisereDeSelection(QStyledItemDelegate):
    """Le trait d'accent de la ligne selectionnee, sur la colonne du libelle.

    **Pourquoi un delegue et pas une regle de style** (`EPIC7-ARB-94` (b)).
    ``QTreeWidget::item:selected { border-left: ... }`` s'applique a **chaque
    cellule** de la ligne : sur les trois colonnes du chutier, cela peignait
    trois traits bleus, ce qu'Egan a lu comme « 2 niveaux de selection (double
    ligne bleue a droite du nom) » (captures ``image-2`` a ``image-4`` du
    2026-08-27). Une feuille de style **ne sait pas distinguer les colonnes** ;
    un delegue le sait, et c'est le seul endroit ou le savoir vit.

    La place du lisere reste **reservee au repos**, en transparent, par la
    regle ``QTreeWidget::item`` : une bordure qui n'apparaitrait qu'a la
    selection decalerait le texte de la ligne selectionnee. Les deux largeurs
    -- reservee et peinte -- sont **le meme jeton**, sans quoi le decalage
    reviendrait par la porte de derriere.
    """

    def peint_le_lisere(self, option, index):
        """Cette cellule recoit-elle le lisere ? Une seule par ligne."""
        if index.column() != COLONNE_LIBELLE:
            return False
        return bool(option.state & QStyle.StateFlag.State_Selected)

    def reserve_la_case(self, option, index):
        """Cette cellule doit-elle reserver la place d'une case absente ?

        `EPIC7-ARB-99` (b), tranche par Egan le 2026-08-27. Les cases
        n'apparaissent **que** sur les noeuds portant au moins un objet
        actionnable, et cette regle ne change pas : une case sur un objet
        qu'aucune action ne touche promettrait un geste qui n'existe pas.

        Ce qui change, c'est que son ABSENCE ne decale plus le libelle. Sans
        reservation, deux freres du meme type -- un lot avec scans, un lot
        sans -- s'affichaient a deux abscisses differentes, et l'arbre
        paraissait bancal sans qu'aucune regle ne l'explique. C'est la seconde
        moitie du retour « l'arborescence varie sans logique apparente ».

        Meme principe que le lisere ci-dessus, et c'est deliberement le meme :
        une place **reservee au repos**, peinte seulement quand il y a lieu.
        """
        if index.column() != COLONNE_LIBELLE:
            return False
        # Le panneau d'arborescence ne porte JAMAIS de case (`DESIGN.md`,
        # `bin-tree-panel` : « aucune puce de selection »), donc il n'a rien a
        # reserver -- y decaler les libelles serait une regression pure. La
        # question se pose a l'ARBRE et non aux drapeaux de l'element : ceux-ci
        # portent `ItemIsUserCheckable` par defaut chez Qt, et le panneau les
        # laisse tels quels puisqu'il ne pose aucun etat de case. S'y fier
        # rendrait le bon resultat par accident, et le mauvais le jour ou l'un
        # des deux arbres nettoierait ses drapeaux.
        arbre = option.widget
        if arbre is not None and not getattr(arbre, "montre_les_signes", False):
            return False
        return not bool(index.flags() & Qt.ItemFlag.ItemIsUserCheckable)

    def largeur_de_la_case(self, option):
        """La largeur qu'occupe l'indicateur de case, lue du STYLE.

        Jamais une constante : l'indicateur est dessine par le style de la
        plateforme, et un nombre ecrit ici serait juste sur une machine et
        faux sur la suivante -- exactement le genre d'ecart que ce depot
        mesure ailleurs a coups de jetons.
        """
        style = option.widget.style() if option.widget else QApplication.style()
        return (
            style.pixelMetric(QStyle.PixelMetric.PM_IndicatorWidth, option, option.widget)
            + style.pixelMetric(
                QStyle.PixelMetric.PM_CheckBoxLabelSpacing, option, option.widget)
        )

    def paint(self, peintre, option, index):
        """Peindre la cellule, puis le lisere par-dessus s'il y a lieu."""
        if self.reserve_la_case(option, index):
            # Le CONTENU se decale ; le rectangle de la ligne, lui, ne bouge
            # pas -- le lisere reste donc a l'abscisse de la ligne, comme sur
            # les lignes qui portent une case.
            decale = QStyleOptionViewItem(option)
            decale.rect = option.rect.adjusted(
                self.largeur_de_la_case(option), 0, 0, 0)
            super().paint(peintre, decale, index)
        else:
            super().paint(peintre, option, index)
        if not self.peint_le_lisere(option, index):
            return
        peintre.fillRect(
            option.rect.x(),
            option.rect.y(),
            jetons.ARBORESCENCE["lisere-selection-px"],
            option.rect.height(),
            QColor(jetons.COULEURS["accent"]),
        )


# ---------------------------------------------------------------------------
# L'arbre
# ---------------------------------------------------------------------------


class ArbreDeChutier(QTreeWidget):
    """Un arbre de lignes de chutier, rendu depuis le modele.

    Deux emplois, une seule identite visuelle (`DESIGN.md`) :

    * le **panneau d'arborescence** (``montre_les_signes=False``) sert a se
      placer -- lignes de ``bin-tree-panel``, texte ``text-secondary``,
      **aucun compteur, aucun badge** ;
    * le **chutier** (``montre_les_signes=True``) montre le contenu de
      l'objet designe, avec ses badges et ses glyphes.

    **Un clic designe, un double-clic ouvre** (`EPIC7-ARB-2`) : le clic ne
    declenche aucune navigation. Ces deux signaux sont les **seuls**
    declencheurs du composant -- aucune ouverture au survol, aucun menu
    contextuel (7.11).
    """

    designation_changee = Signal(str)
    ouverture_demandee = Signal(str)

    def __init__(self, chaines, *, montre_les_signes=True, parent=None):
        super().__init__(parent)
        self._chaines = chaines
        self.montre_les_signes = montre_les_signes
        self._noeuds = {}
        self._elements = {}
        self._racines = ()
        self._libelle_racine = None
        self._selection = None
        self._en_reflet = False

        self.setColumnCount(
            NOMBRE_DE_COLONNES
            if montre_les_signes
            else NOMBRE_DE_COLONNES_SANS_SIGNES
        )
        self.setHeaderHidden(True)
        # Revue de vague 2: sans mode de redimensionnement explicite, Qt donne
        # a chaque colonne sa largeur de section par defaut (~100 px). Avec
        # l'indentation qui croit a chaque niveau, la colonne du libelle
        # tombait a quelques pixels des le niveau planche -- les six niveaux
        # d'`EPIC7-ARB-9` s'affichaient « Pla... », « Fi... », et le chutier,
        # « la piece la plus sollicitee de l'application », ne montrait plus
        # aucun nom. Le libelle prend donc toute la place restante, les deux
        # colonnes de signes juste ce que leur contenu demande.
        entete = self.header()
        entete.setSectionResizeMode(COLONNE_LIBELLE, QHeaderView.ResizeMode.Stretch)
        if montre_les_signes:
            entete.setSectionResizeMode(
                COLONNE_BADGE, QHeaderView.ResizeMode.ResizeToContents)
            entete.setSectionResizeMode(
                COLONNE_GLYPHE, QHeaderView.ResizeMode.ResizeToContents)
        else:
            # `Stretch` seul ne suffisait pas : Qt refuse a une section de
            # descendre sous `minimumSectionSize` (16 px, derivee de la
            # police), donc les deux colonnes vides gardaient 32 px meme sans
            # rien a montrer. La colonne du libelle est desormais la SEULE, et
            # le plancher de section est mis a zero pour qu'aucune largeur
            # residuelle ne se represente si une colonne revenait un jour.
            entete.setMinimumSectionSize(0)
        entete.setStretchLastSection(False)
        self.setRootIsDecorated(True)
        self.setUniformRowHeights(True)
        self.setMinimumWidth(0)
        self.setFrameShape(QFrame.Shape.NoFrame)
        # Le clic droit ne declenche RIEN : le menu contextuel arrive en
        # 7.11 avec son inventaire (`EPIC7-ARB-37`). On le dit au widget
        # plutot que de compter sur un defaut non teste.
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        # Le survol n'ouvre rien : aucune expansion, aucune navigation.
        self.setExpandsOnDoubleClick(False)
        self.setMouseTracking(False)

        indentation = jetons.ESPACEMENTS["5"]
        self.setIndentation(indentation)
        self.setIconSize(
            QSize(jetons.ICONOGRAPHIE["boite-px"], jetons.ICONOGRAPHIE["boite-px"])
        )
        couleurs = jetons.COULEURS
        if montre_les_signes:
            hauteur = jetons.ESPACEMENTS["row-height"]
            fond = couleurs["surface-panel"]
            texte = couleurs["text-primary"]
        else:
            hauteur = _HAUTEUR_LIGNE_ARBORESCENCE
            fond = couleurs["surface-sunken"]
            texte = couleurs["text-secondary"]
        self._surface_porteuse = fond
        self.setStyleSheet(
            f"QTreeWidget {{ background: {fond}; color: {texte};"
            f" border: none; }}"
            # Le lisere de selection prend sa place des le repos, en
            # transparent : une bordure qui n'apparait qu'a la selection
            # decalerait le texte de la ligne selectionnee. La largeur reservee
            # est **le meme jeton** que celle que le delegue peint.
            f" QTreeWidget::item {{ height: {hauteur}px;"
            f" color: {texte};"
            f" border-left: {jetons.ARBORESCENCE['lisere-selection-px']}px"
            f" solid transparent; }}"
            # **La selection se peint a l'accent** (correctif du 2026-08-26,
            # meme defaut que sur l'ecran de projet). `surface-hover` seul,
            # c'est 10/255 d'ecart avec la surface porteuse : invisible.
            # L'accent ne peut pas passer en APLAT sous le texte -- `accent-on`
            # sur `accent` ne tient que 3,8:1, sous le plancher 4,5:1 que
            # `jetons` impose aux glyphes -- donc il passe en TRAIT, ce que le
            # meme module autorise explicitement (plancher 3:1 non textuel). Le
            # fond survole reste, releve du texte secondaire au primaire.
            #
            # **Le TRAIT n'est plus ici** (`EPIC7-ARB-94` (b), 2026-08-27) :
            # `::item` designe chaque CELLULE, donc la regle en peignait un par
            # colonne -- trois traits bleus sur une ligne du chutier. Il est
            # peint par `LisereDeSelection`, qui sait, lui, ce qu'est une
            # colonne. Ne pas le remettre ici.
            f" QTreeWidget::item:selected {{"
            f" background: {couleurs['surface-hover']};"
            f" color: {couleurs['text-primary']}; }}"
        )
        # Le delegue est garde en attribut : c'est lui, et non la feuille de
        # style, qui porte desormais le lisere de selection.
        self.lisere = LisereDeSelection(self)
        self.setItemDelegate(self.lisere)

        self.itemClicked.connect(self._sur_clic)
        self.itemDoubleClicked.connect(self._sur_double_clic)
        self.itemChanged.connect(self._sur_changement)

    # --- Contenu -------------------------------------------------------

    def poser(self, racines, *, libelle_racine=None):
        """Remplacer le contenu de l'arbre par `racines` (ordre preserve).

        Quand `libelle_racine` est fourni, une **ligne racine** portant ce
        libelle est posee au premier niveau et TOUS les noeuds de `racines`
        deviennent ses enfants. Son identifiant est `IDENTIFIANT_RACINE`,
        elle n'est jamais cochable et ne porte aucun signe. Elle est
        depliee a la pose.
        Sans `libelle_racine`, le comportement est strictement celui d'avant.

        C'est la moitie COMPOSANT d'`EPIC7-ARB-85` : « on ne peut pas
        remonter a la racine du dossier de projet ». L'etat « portee = le
        projet entier » existait deja au modele (`designation is None`) sans
        qu'aucun geste n'y ramene -- un etat legal sans chemin d'acces. La
        ligne emet `designation_changee(IDENTIFIANT_RACINE)` comme n'importe
        quelle autre ; c'est la coquille qui traduit cet identifiant en
        portee `None`.
        """
        self.clear()
        self._noeuds = {}
        self._elements = {}
        self._racines = tuple(racines)
        self._libelle_racine = libelle_racine
        if libelle_racine is None:
            for noeud in self._racines:
                self.addTopLevelItem(self._construire(noeud))
        else:
            ligne_racine = self._construire_la_ligne_racine(libelle_racine)
            self.addTopLevelItem(ligne_racine)
            for noeud in self._racines:
                # `_construire` rattache deja l'element a son parent : le
                # constructeur de `QTreeWidgetItem` prend le parent.
                self._construire(noeud, ligne_racine)
        # Les signes se posent en SECONDE PASSE, une fois les elements
        # entres dans la vue : `setItemWidget` sur un element qui n'est pas
        # encore dans l'arbre ne pose rien et ne leve rien -- l'arbre
        # s'affichait alors sans aucun badge ni glyphe, en silence.
        if self.montre_les_signes:
            for identifiant, element in self._elements.items():
                noeud = self._noeuds.get(identifiant)
                # La ligne racine n'est pas un noeud du modele : elle ne
                # porte aucun signe, et la chercher dans `_noeuds` leverait.
                if noeud is not None:
                    self._poser_les_signes(element, noeud)
        # **Tout le contenu de la portee est deplie** (`EPIC7-ARB-99`, tranche
        # par Egan le 2026-08-27). C'etait `expandToDepth(0 ou 1)`, c'est-a-dire
        # UN seul niveau : les racines de la portee ouvertes, leurs enfants
        # fermes. Consequence mesuree, et c'est le retour de terrain mot pour
        # mot -- « la hierarchie apparente varie quand je change l'objet
        # selectionne » : la meme planche montrait ses scans quand elle etait
        # la portee, et les cachait quand la portee etait son lot. Ce qu'on
        # voit sous un objet dependait donc de l'endroit d'ou on le regarde,
        # ce qu'aucune regle ne rend previsible.
        #
        # Deplier tout est la seule des trois politiques envisagees ou « ce
        # qu'il y a sous un objet » ne depend jamais de la portee. Les
        # expandeurs restent : replier un niveau est un geste, ce n'est plus
        # un etat impose.
        self.expandAll()
        self.refleter_la_selection(self._selection)

    def _construire_la_ligne_racine(self, libelle):
        """La ligne racine : un libelle, un pictogramme, aucune case.

        Elle n'entre PAS dans `_noeuds` -- il n'existe aucun noeud de modele
        pour le projet entier, et en fabriquer un ici ferait mentir
        `noeud(IDENTIFIANT_RACINE)`. Elle entre dans `_elements`, parce
        qu'elle est bien une ligne posee que `designer` doit atteindre.
        """
        element = QTreeWidgetItem()
        element.setText(COLONNE_LIBELLE, libelle)
        element.setData(
            COLONNE_LIBELLE, Qt.ItemDataRole.UserRole, IDENTIFIANT_RACINE
        )
        element.setChildIndicatorPolicy(
            QTreeWidgetItem.ChildIndicatorPolicy.DontShowIndicatorWhenChildless
        )
        couleur = QColor(
            jetons.COULEURS[
                "text-primary" if self.montre_les_signes else "text-secondary"
            ]
        )
        element.setIcon(
            COLONNE_LIBELLE, pictogramme(TYPE_PICTOGRAMME_RACINE, couleur)
        )
        element.setForeground(COLONNE_LIBELLE, couleur)
        # JAMAIS cochable : la portee « projet entier » n'est pas un objet
        # qu'une action de l'atelier peut prendre.
        element.setFlags(element.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
        self._elements[IDENTIFIANT_RACINE] = element
        return element

    def libelle_racine(self):
        """Le libelle de la ligne racine posee, ou `None` s'il n'y en a pas."""
        return self._libelle_racine

    def _construire(self, noeud, parent=None):
        element = QTreeWidgetItem(parent)
        element.setText(COLONNE_LIBELLE, libelle_de_noeud(noeud, self._chaines))
        element.setData(COLONNE_LIBELLE, Qt.ItemDataRole.UserRole, noeud.identifiant)
        # L'EXPANDEUR N'APPARAIT QUE SUR UN NOEUD QUI A DES ENFANTS : son
        # absence est l'information (`EPIC7-ARB-3`). La politique est posee
        # explicitement plutot que laissee au defaut du toolkit.
        element.setChildIndicatorPolicy(
            QTreeWidgetItem.ChildIndicatorPolicy.DontShowIndicatorWhenChildless
        )
        couleur_texte = self._couleur_de_ligne(noeud)
        element.setIcon(COLONNE_LIBELLE, pictogramme(noeud.type, couleur_texte))
        element.setForeground(COLONNE_LIBELLE, couleur_texte)
        self._noeuds[noeud.identifiant] = noeud
        self._elements[noeud.identifiant] = element
        for enfant in noeud.enfants:
            element.addChild(self._construire(enfant, element))
        return element

    def _couleur_de_ligne(self, noeud):
        """La couleur d'une ligne : `foreground-delinked` pour un objet delie.

        « Un rush delie est en ``state-absent-text`` -- la variante de texte,
        pas la chromie pleine -- double du glyphe de delie » : la couleur ne
        porte jamais seule, et la chromie pleine ne porte jamais de texte.
        """
        if noeud.glyphe == modele.GLYPHE_DELIE:
            return QColor(jetons.COULEURS["state-absent-text"])
        if self.montre_les_signes:
            return QColor(jetons.COULEURS["text-primary"])
        return QColor(jetons.COULEURS["text-secondary"])

    def _poser_les_signes(self, element, noeud):
        """Poser les deux familles de signes, dans DEUX controles distincts."""
        if noeud.badge is not None:
            self.setItemWidget(
                element,
                COLONNE_BADGE,
                BadgeDeCompletude(noeud.badge, self._chaines, self._surface_porteuse),
            )
        if noeud.glyphe is not None:
            self.setItemWidget(
                element, COLONNE_GLYPHE, GlypheDeRattachement(noeud.glyphe, self._chaines)
            )

    # --- Lecture -------------------------------------------------------

    def racines(self):
        """Les noeuds de MODELE de premier niveau, dans l'ordre pose.

        La ligne racine n'en fait jamais partie : elle n'est pas un noeud du
        modele, et la compter ici ferait croire au projet entier qu'il est
        un objet du manifest.
        """
        return self._racines

    def identifiants_racines(self):
        """Les identifiants des noeuds de modele de premier niveau.

        Inchange en presence de la ligne racine, pour la meme raison que
        `racines` : ce sont les racines du MODELE, pas les lignes de tete
        de l'arbre. `IDENTIFIANT_RACINE` ne s'y trouve donc pas.
        """
        return [noeud.identifiant for noeud in self._racines]

    def tous_les_identifiants(self):
        """Tous les identifiants POSES, dans l'ordre de construction.

        `IDENTIFIANT_RACINE` en fait partie quand la ligne racine est posee
        -- c'est bien une ligne de l'arbre, qu'on peut designer et
        atteindre.
        """
        return tuple(self._elements)

    def element(self, identifiant):
        """L'element d'arbre d'un identifiant -- jamais une position."""
        return self._elements.get(identifiant)

    def noeud(self, identifiant):
        """Le noeud de modele d'un identifiant."""
        return self._noeuds.get(identifiant)

    def identifiant_de(self, element):
        """L'identifiant porte par un element d'arbre."""
        if element is None:
            return None
        return element.data(COLONNE_LIBELLE, Qt.ItemDataRole.UserRole)

    def designation(self):
        """L'identifiant du noeud designe, ou `None`."""
        return self.identifiant_de(self.currentItem())

    def designer(self, identifiant):
        """Designer un noeud par son identifiant, sans emettre de navigation."""
        element = self.element(identifiant)
        if element is None:
            return False
        self.setCurrentItem(element)
        parent = element.parent()
        # Le chemin de la selection se deplie, sans replier le reste.
        while parent is not None:
            parent.setExpanded(True)
            parent = parent.parent()
        return True

    # --- Selection a trois etats ---------------------------------------

    def refleter_la_selection(self, selection):
        """Porter l'etat a trois valeurs de `selection` sur les cases.

        Les cases n'apparaissent **que** sur les noeuds qui ont au moins un
        enfant actionnable dans l'atelier courant : une case sur un objet
        qu'aucune action ne touche promettrait un geste qui n'existe pas.
        Le panneau d'arborescence, lui, n'en porte jamais -- il sert a se
        placer (`DESIGN.md`, `bin-tree-panel` : « aucune puce de selection »).
        """
        self._selection = selection
        if not self.montre_les_signes:
            return
        self._en_reflet = True
        try:
            for identifiant, element in self._elements.items():
                # La ligne racine n'est pas un noeud du modele :
                # `selection.actionnables(IDENTIFIANT_RACINE)` n'a aucun
                # sens, et une case y promettrait un geste inexistant.
                if identifiant not in self._noeuds:
                    continue
                actionnables = (
                    () if selection is None else selection.actionnables(identifiant)
                )
                drapeaux = element.flags()
                if actionnables:
                    element.setFlags(drapeaux | Qt.ItemFlag.ItemIsUserCheckable)
                    element.setCheckState(
                        COLONNE_LIBELLE, COCHE_PAR_ETAT[selection.etat(identifiant)]
                    )
                else:
                    element.setFlags(drapeaux & ~Qt.ItemFlag.ItemIsUserCheckable)
                    element.setData(COLONNE_LIBELLE, Qt.ItemDataRole.CheckStateRole, None)
        finally:
            self._en_reflet = False

    def _sur_changement(self, element, colonne):
        """Une case cochee a la main : basculer, puis re-derive tout l'arbre."""
        if self._en_reflet or self._selection is None:
            return
        if colonne != COLONNE_LIBELLE:
            return
        identifiant = self.identifiant_de(element)
        if identifiant is None:
            return
        voulu = element.checkState(COLONNE_LIBELLE)
        etat = self._selection.etat(identifiant)
        if COCHE_PAR_ETAT[etat] == voulu:
            return
        if voulu == Qt.CheckState.Unchecked:
            self._selection.deselectionner(identifiant)
        else:
            self._selection.selectionner(identifiant)
        self.refleter_la_selection(self._selection)

    # --- Le chrome de l'arbre : filiation et expandeurs -----------------

    def montre_un_expandeur(self, element):
        """Cet element porte-t-il un expandeur ?

        **L'invariant `EPIC7-ARB-3` se lit ici, il ne se contourne pas** :
        « l'expandeur n'apparait que sur un noeud qui a des enfants ; son
        absence est l'information ». La politique posee par `_construire`
        (`DontShowIndicatorWhenChildless`) fait foi -- on la LIT plutot que de
        redecider a cote d'elle, sans quoi deux regles cohabiteraient.
        """
        politique = element.childIndicatorPolicy()
        familles = QTreeWidgetItem.ChildIndicatorPolicy
        if politique == familles.ShowIndicator:
            return True
        if politique == familles.DontShowIndicator:
            return False
        return element.childCount() > 0

    def glyphe_d_expandeur(self, element):
        """`-` quand le niveau est deplie, `+` quand il est replie.

        Les deux signes viennent de `jetons.ICONOGRAPHIE` -- le `-` est un
        U+2212, jamais un trait d'union.
        """
        cle = (
            "glyphe-replier-niveau"
            if element.isExpanded()
            else "glyphe-deplier"
        )
        return jetons.ICONOGRAPHIE[cle]

    def drawBranches(self, peintre, rectangle, index):
        """Peindre les traits de niveau et l'expandeur, jamais la fleche native.

        **Transcrit de `key-chutier-v2.html`**, pas redessine (`EPIC7-ARB-94`
        (c), retour d'Egan : « on a perdu une des specifications designees sur
        l'ux : les traits de niveaux hierarchique pour l'arborescence avec le
        +/- »). Ce que la maquette dit, regle par regle :

        * `.kids > .node::before` -- un trait VERTICAL de 1 px en
          `{colors.border}`, a gauche de la ligne, sur toute sa hauteur ;
        * `.kids > .node:last-child::before { height:14px }` -- sur le
          **dernier** objet d'un niveau, ce trait s'arrete a mi-hauteur : « les
          traits d'arbre s'arretent au dernier objet d'un niveau » ;
        * `.kids > .node > .row::before` -- un raccord HORIZONTAL de 1 px, a
          mi-hauteur, du trait vertical jusqu'a la ligne ;
        * `.exp` -- une boite carree portant `+` ou `-`, en
          `{colors.text-disabled}`, `visibility:hidden` quand le noeud n'a pas
          d'enfant. La maquette ne trace **aucun cadre** autour du signe : la
          boite est une geometrie, pas un dessin. Le premier niveau n'a ni
          trait vertical ni raccord -- il n'a pas de parent a rejoindre.

        Aucune valeur litterale ici : la graisse, le cote de la boite et les
        deux couleurs se lisent de `jetons`.
        """
        indentation = self.indentation()
        if indentation <= 0:
            return
        element = self.itemFromIndex(index)
        if element is None:
            return

        profondeur = 0
        remonte = index.parent()
        while remonte.isValid():
            profondeur += 1
            remonte = remonte.parent()

        couleur_trait = QColor(jetons.COULEURS["border"])
        graisse = jetons.ARBORESCENCE["trait-px"]
        cote = jetons.ARBORESCENCE["expandeur-boite-px"]
        gauche = rectangle.left()
        milieu_y = rectangle.top() + rectangle.height() // 2

        # La boite de l'expandeur occupe le centre de la DERNIERE cellule
        # d'indentation, celle du niveau du noeud lui-meme.
        centre_x = gauche + profondeur * indentation + indentation // 2
        boite = QRect(centre_x - cote // 2, milieu_y - cote // 2, cote, cote)
        montre = self.montre_un_expandeur(element)

        peintre.save()
        try:
            # Les traits de filiation, du niveau du noeud jusqu'a la racine.
            # Un niveau ne prolonge son trait vers le bas que s'il lui reste
            # un frere en dessous : c'est ce qui l'arrete au dernier objet.
            courant = index
            for niveau in range(profondeur, 0, -1):
                trait_x = gauche + niveau * indentation - indentation // 2
                a_un_frere_apres = (
                    courant.row() + 1
                    < index.model().rowCount(courant.parent())
                )
                if niveau == profondeur:
                    bas = rectangle.bottom() if a_un_frere_apres else milieu_y
                    peintre.fillRect(
                        trait_x,
                        rectangle.top(),
                        graisse,
                        bas - rectangle.top() + 1,
                        couleur_trait,
                    )
                    # Le raccord horizontal s'arrete au bord de la boite de
                    # l'expandeur quand il y en a une, sinon il rejoint la
                    # ligne : le signe ne se pose jamais sur un trait.
                    fin_x = boite.left() if montre else rectangle.right()
                    peintre.fillRect(
                        trait_x, milieu_y, fin_x - trait_x, graisse, couleur_trait
                    )
                elif a_un_frere_apres:
                    peintre.fillRect(
                        trait_x,
                        rectangle.top(),
                        graisse,
                        rectangle.height(),
                        couleur_trait,
                    )
                courant = courant.parent()

            if montre:
                police = peintre.font()
                police.setPixelSize(jetons.ICONOGRAPHIE["glyphe-expandeur-px"])
                peintre.setFont(police)
                peintre.setPen(QColor(jetons.COULEURS["text-disabled"]))
                peintre.drawText(
                    boite,
                    Qt.AlignmentFlag.AlignCenter,
                    self.glyphe_d_expandeur(element),
                )
        finally:
            peintre.restore()

    # --- Gestes --------------------------------------------------------

    def _sur_clic(self, element, colonne):
        # UN CLIC DESIGNE : aucune navigation, aucun changement d'atelier.
        del colonne
        identifiant = self.identifiant_de(element)
        if identifiant is not None:
            self.designation_changee.emit(identifiant)

    def _sur_double_clic(self, element, colonne):
        # UN DOUBLE-CLIC OUVRE : c'est le seul chemin d'ouverture.
        del colonne
        identifiant = self.identifiant_de(element)
        if identifiant is not None:
            self.ouverture_demandee.emit(identifiant)


# ---------------------------------------------------------------------------
# Le chutier
# ---------------------------------------------------------------------------


class Chutier(QFrame):
    """Le panneau DROIT : le contenu de l'objet designe a gauche.

    Un en-tete qui porte la **portee** et le bouton **plein ecran**, puis
    l'arbre. Ni barre de filtres, ni zone tampon, ni section Calibration :
    l'arbre nu d'abord (AC 6 ; `bin-filters` vient avec le besoin,
    `EPIC7-ARB-4`, la file et le bouton Detecter avec 7.3).
    """

    plein_ecran_demande = Signal()

    def __init__(self, chaines, parent=None):
        super().__init__(parent)
        self._chaines = chaines
        self.setObjectName("chutier")
        self.setMinimumWidth(jetons.ESPACEMENTS["bin-min-width"])

        colonne = QVBoxLayout(self)
        marge = jetons.ESPACEMENTS["panel-pad"]
        colonne.setContentsMargins(marge, marge, marge, marge)
        colonne.setSpacing(jetons.ESPACEMENTS["3"])

        ligne = QHBoxLayout()
        self.entete = QLabel(self)
        self.entete.setProperty("role", "zone")
        # Aucune boite calee sur une chaine : l'en-tete passe a la ligne.
        self.entete.setWordWrap(True)
        typo = jetons.TYPOGRAPHIE["label"]
        self.entete.setStyleSheet(
            f"color: {jetons.COULEURS['text-secondary']};"
            f" font-size: {typo['taille']}px;"
        )
        ligne.addWidget(self.entete, 1)

        self.bouton_plein_ecran = QToolButton(self)
        # Une pastille portant un signe, et non la fleche Qt native : celle-ci
        # se peignait au style de la PLATEFORME -- un gros triangle bleu clair
        # dans une coque sombre (passe de chrome du 2026-08-26). Le signe vit
        # dans `jetons.ICONOGRAPHIE`, jamais en litteral ici.
        self.bouton_plein_ecran.setText(jetons.ICONOGRAPHIE["glyphe-plein-ecran"])
        self.bouton_plein_ecran.setCheckable(True)
        self.bouton_plein_ecran.setToolTip(chaines["chutier-plein-ecran"])
        self.bouton_plein_ecran.setAccessibleName(chaines["chutier-plein-ecran"])
        self.bouton_plein_ecran.clicked.connect(
            lambda _coche: self.plein_ecran_demande.emit()
        )
        ligne.addWidget(self.bouton_plein_ecran, 0)
        colonne.addLayout(ligne)

        self.arbre = ArbreDeChutier(chaines, montre_les_signes=True, parent=self)
        colonne.addWidget(self.arbre, 1)

        self.poser_portee(None, ())

    def poser_portee(self, noeud, enfants):
        """Poser la portee du chutier et le contenu qu'elle designe."""
        self.entete.setText(texte_de_portee(noeud, enfants, self._chaines))
        self.arbre.poser(enfants)

    def refleter_le_plein_ecran(self, actif):
        """Accorder le bouton et sa bulle a l'etat reel du mode plein ecran."""
        self.bouton_plein_ecran.setChecked(actif)
        cle = "chutier-quitter-plein-ecran" if actif else "chutier-plein-ecran"
        self.bouton_plein_ecran.setToolTip(self._chaines[cle])
        self.bouton_plein_ecran.setAccessibleName(self._chaines[cle])
        self.bouton_plein_ecran.setText(
            jetons.ICONOGRAPHIE[
                "glyphe-plein-ecran-sortie" if actif else "glyphe-plein-ecran"
            ]
        )


class SuperpositionArborescence(QFrame):
    """L'arborescence ouverte PAR-DESSUS le chutier, le temps de se placer.

    « Un rail de pictogrammes reste, et rouvre l'arborescence **par-dessus**
    le chutier, le temps de se placer. On a l'un ou l'autre, **jamais
    rien** » (`EPIC7-ARB-40`). Elle **accueille l'arbre lui-meme** plutot
    qu'une copie : un seul arbre existe, donc « les deux a la fois » n'est
    pas un etat representable.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("superposition-arborescence")
        self.setAutoFillBackground(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet(
            f"#superposition-arborescence {{"
            f" background: {jetons.COULEURS['surface-sunken']};"
            f" border-right: 1px solid {jetons.COULEURS['border-strong']}; }}"
        )
        self._colonne = QVBoxLayout(self)
        marge = jetons.ESPACEMENTS["panel-pad"]
        self._colonne.setContentsMargins(marge, marge, marge, marge)
        self._colonne.setSpacing(0)
        self.hide()

    def accueillir(self, widget, bouton_de_repli=None):
        """Reparenter l'arbre ici -- et son bouton de repli -- puis se montrer.

        Le bouton vient du panneau : la superposition n'en peint pas un second
        (`EPIC7-ARB-93`, volet b). Sans lui, l'ouverture par-dessus le chutier
        n'offrait AUCUN geste de fermeture -- le bouton de repli existait bien,
        mais dans le panneau masque, donc invisible : mesure du 2026-08-27,
        `isVisible()` faux alors qu'`isEnabled()` etait vrai. La seule sortie
        etait de designer un noeud, c'est-a-dire de faire un choix pour pouvoir
        renoncer a choisir.
        """
        if bouton_de_repli is not None:
            rangee = QHBoxLayout()
            rangee.setContentsMargins(0, 0, 0, 0)
            rangee.addStretch(1)
            rangee.addWidget(bouton_de_repli, 0)
            self._colonne.addLayout(rangee)
            self._rangee_du_bouton = rangee
            bouton_de_repli.show()
        self._colonne.addWidget(widget)
        widget.show()
        self.show()
        self.raise_()

    def rendre(self, widget, destination):
        """Rendre l'arbre a sa destination et disparaitre.

        Le bouton de repli, lui, retourne a son en-tete par
        `PanneauArborescence.reprendre_le_bouton_de_repli` : c'est le panneau
        qui sait ou il va, pas la superposition.
        """
        rangee = getattr(self, "_rangee_du_bouton", None)
        if rangee is not None:
            self._colonne.removeItem(rangee)
            rangee.deleteLater()
            self._rangee_du_bouton = None
        self._colonne.removeWidget(widget)
        destination(widget)
        self.hide()


def enfants_de_la_portee(racines, identifiant):
    """Ce que le chutier montre pour une designation donnee.

    Sans designation, le chutier montre le projet entier. Avec, il montre le
    **contenu de l'objet designe** -- ses enfants et leur filiation, jamais
    l'objet lui-meme : le panneau fixe la portee, le chutier lit dedans.
    """
    if identifiant is None:
        return tuple(racines)
    noeud = modele.noeud_par_identifiant(racines, identifiant)
    if noeud is None:
        return tuple(racines)
    return noeud.enfants


def noeud_de_la_portee(racines, identifiant):
    """Le noeud designe, ou `None` quand la portee est le projet entier."""
    if identifiant is None:
        return None
    return modele.noeud_par_identifiant(racines, identifiant)
