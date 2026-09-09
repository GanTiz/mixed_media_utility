# -*- coding: utf-8 -*-
"""La feuille de style d'APPLICATION : ce que personne ne peignait.

**Le defaut que ce module supprime, et sa mesure** (captures du 2026-08-26,
`scripts/gui/capturer_ecrans.py`). Jusqu'ici chaque ecran peignait ses propres
surfaces -- 45 appels a ``setStyleSheet`` repartis sur 9 modules -- et rien ne
peignait le reste. Tout widget qu'aucun selecteur ne visait retombait sur le
style natif de la plateforme, c'est-a-dire CLAIR au milieu d'une coque sombre :

* les poignees des ``QSplitter`` de la coquille formaient **deux bandes
  blanches verticales de haut en bas**, plus visibles que le contenu ;
* la bascule brut/corrige, grisee, etait un **gros rectangle gris clair** dans
  l'en-tete ;
* les cases a cocher, les expandeurs d'arbre, les fleches de ``QComboBox``, les
  barres de defilement et les infobulles etaient tous natifs.

Aucun des 443 tests ne pouvait le voir : ils mesurent ce qui est **ecrit**
(aucune couleur litterale hors de `jetons.py`, neutres neutres, contrastes au
plancher) et jamais ce qui est **peint**. Le premier defaut de cette famille
avait ete trouve en revue de vague 2 -- le porteur de la liste de projets -- et
corrige un widget a la fois ; ce module corrige la CLASSE.

**Pourquoi ici et pas dans un ecran de plus.** Une feuille posee sur la
``QApplication`` est le dernier recours de la cascade Qt : une regle posee sur
un widget ou un de ses ancetres l'emporte a specificite egale. Les 45 feuilles
existantes gardent donc exactement leur effet, et celle-ci ne s'applique qu'la
ou personne n'a rien dit. C'est ce qui permet de la poser sans relire les neuf
modules.

**Aucun selecteur `QWidget` nu.** Peindre `QWidget` peindrait AUSSI les
surfaces qui doivent rester transparentes -- les libelles poses sur une ligne
de projet, les superpositions de l'atelier Scan -- et l'on remplacerait un
defaut visible par un defaut sournois. Chaque regle nomme sa classe.
"""

from __future__ import annotations

from . import jetons


def feuille_application() -> str:
    """La feuille, entierement lue des jetons (aucun litteral ici)."""
    c = jetons.COULEURS
    e = jetons.ESPACEMENTS
    r = jetons.RAYONS
    corps = jetons.TYPOGRAPHIE["body"]
    return "".join(
        (
            # --- fenetres et boites de dialogue -------------------------
            # `QDialog` couvre les boites que l'outil ouvre lui-meme. Les
            # boites SYSTEME (choix de dossier) restent natives : elles
            # appartiennent au systeme, pas a l'application, et les
            # repeindre serait mentir sur leur provenance.
            f"QMainWindow, QDialog {{ background: {c['surface-canvas']}; }}",
            # --- LES SURFACES D'ATELIER ---------------------------------
            # Mesure du 2026-08-26, sur la capture de l'atelier Scan seul : le
            # gris de controle par defaut de Windows -- celui des boites de
            # dialogue du systeme -- **couvrait 66 % de la vue galerie** et
            # 20 % de la vue page. Ces surfaces ne peignent pas
            # leur fond ; dans la coquille elles laissaient voir la toile de
            # celle-ci, et le defaut restait invisible tant qu'on ne les
            # regardait pas seules. Une surface qui n'est juste que par
            # l'endroit ou on la pose n'est pas juste : sortie de la coquille
            # -- en fenetre detachee, en capture, en test -- elle redevient
            # grise.
            #
            # Elles sont nommees une par une plutot que visees par un
            # selecteur large : c'est la meme discipline que `#liste-projets`
            # et `#porteur-de-liste`, et elle vaut pour la meme raison --
            # un descendant mordrait sur les lignes et les cases.
            f" #atelier-scan-jugement, #vue-mode-pdf, #vue-galerie,"
            f" #vue-vignette-unique, #atelier-scan {{"
            f" background: {c['surface-canvas']}; }}",
            # Le viewport d'une zone defilante et le widget porte a
            # l'interieur sont DEUX widgets de plus, et c'est exactement par
            # la que le defaut etait deja passe en revue de vague 2.
            f" QScrollArea {{ background: {c['surface-canvas']};"
            f" border: none; }}",
            f" QScrollArea > QWidget > QWidget {{"
            f" background: {c['surface-canvas']}; }}",
            f" #grille-emplacements, #ligne-page-galerie {{"
            f" background: {c['surface-canvas']}; }}",
            f" #panneau-lateral-de-vue, #corps-panneau-lateral {{"
            f" background: {c['surface-panel']}; }}",
            # --- LES POIGNEES DE SPLITTER -------------------------------
            # Le defaut le plus visible de la capture du 2026-08-26. La
            # poignee prend la couleur de la BORDURE, pas celle d'une
            # surface : c'est une ligne de separation, et c'est ce qu'elle
            # doit avoir l'air d'etre.
            f" QSplitter::handle {{ background: {c['border']}; }}",
            f" QSplitter::handle:horizontal {{ width: {e['1']}px; }}",
            f" QSplitter::handle:vertical {{ height: {e['1']}px; }}",
            # Au survol elle se signale -- c'est la seule facon de decouvrir
            # qu'elle se deplace, faute de curseur redimensionne visible sur
            # une capture.
            f" QSplitter::handle:hover {{ background: {c['accent']}; }}",
            # --- boutons ------------------------------------------------
            # `min-height` autant que `padding` : mesure du 2026-08-26 sur la
            # capture de la vue galerie, ou les quatre boutons de vue
            # (« Ajuster », « Pleine largeur »...) avaient leur texte **coupe
            # en haut et en bas**. Une rangee serree donne au bouton moins que
            # sa hauteur souhaitee, et le remplissage mange alors la place du
            # glyphe. La hauteur minimale de la zone de contenu est donc
            # posee, plutot que laissee dependre de ce que le voisin veut bien
            # ceder.
            f" QPushButton {{ background: {c['surface-raised']};"
            f" color: {c['text-primary']};"
            f" border: 1px solid {c['border-strong']};"
            f" border-radius: {r['sm']}px;"
            f" min-height: {e['6']}px;"
            f" padding: {e['3']}px {e['6']}px; }}",
            f" QPushButton:hover {{ background: {c['surface-hover']}; }}",
            f" QPushButton:disabled {{ color: {c['text-disabled']};"
            f" border-color: {c['border']}; }}",
            # **L'action primaire, a l'accent PLEIN.** Les maquettes en
            # posent exactement une par surface (« Creer un projet »,
            # « Generer 3 planches », « C'est une planche a imprimer ») et
            # tout le reste en contour gris. Sans elle, trois boutons de
            # meme poids ne disent pas par ou commencer -- defaut rapporte
            # par Egan au premier essai (« aucun bouton »).
            #
            # C'est le SEUL emploi de l'accent en aplat sous du texte, et il
            # est licite parce que `accent-on` est blanc pur : le couple
            # tient le plancher non textuel et le libelle est en 13 px gras,
            # pas en 11 px de donnee.
            f" QPushButton[primaire='true'] {{ background: {c['accent']};"
            f" color: {c['accent-on']}; border: 1px solid {c['accent']};"
            f" font-weight: 600; }}",
            f" QPushButton[primaire='true']:hover {{"
            f" background: {c['accent-pressed']};"
            f" border-color: {c['accent-pressed']}; }}",
            f" QPushButton[primaire='true']:disabled {{"
            f" background: {c['surface-raised']}; color: {c['text-disabled']};"
            f" border-color: {c['border']}; }}",
            # --- boutons-outils : la pastille des maquettes -------------
            # `plein ecran`, `Filtres`, `tout` : un fond leve, un rayon
            # court, un texte secondaire. Jamais le carre gris natif.
            f" QToolButton {{ background: transparent;"
            f" color: {c['text-secondary']}; border: 1px solid transparent;"
            f" border-radius: {r['sm']}px;"
            f" padding: {e['1']}px {e['3']}px; }}",
            f" QToolButton:hover {{ background: {c['surface-hover']};"
            f" color: {c['text-primary']}; border-color: {c['border']}; }}",
            f" QToolButton:checked {{ color: {c['accent-text']};"
            f" border-color: {c['accent']}; }}",
            f" QToolButton:disabled {{ color: {c['text-disabled']};"
            f" background: transparent; border-color: transparent; }}",
            # --- cases a cocher -----------------------------------------
            f" QCheckBox {{ color: {c['text-primary']};"
            f" spacing: {e['3']}px; }}",
            f" QCheckBox::indicator, QTreeWidget::indicator {{"
            f" width: {e['5']}px; height: {e['5']}px;"
            f" border: 1px solid {c['border-strong']};"
            f" border-radius: {r['sm']}px;"
            f" background: {c['surface-sunken']}; }}",
            f" QCheckBox::indicator:checked, QTreeWidget::indicator:checked {{"
            f" background: {c['accent']}; border-color: {c['accent']}; }}",
            f" QCheckBox::indicator:indeterminate,"
            f" QTreeWidget::indicator:indeterminate {{"
            f" background: {c['accent-pressed']};"
            f" border-color: {c['accent']}; }}",
            f" QCheckBox::indicator:disabled, QTreeWidget::indicator:disabled {{"
            f" border-color: {c['border']}; background: {c['surface-panel']}; }}",
            # --- champs de saisie et listes deroulantes -----------------
            f" QLineEdit, QSpinBox, QComboBox, QPlainTextEdit, QTextEdit {{"
            f" background: {c['surface-raised']}; color: {c['text-primary']};"
            f" border: 1px solid {c['border']};"
            f" border-radius: {r['sm']}px; padding: {e['3']}px; }}",
            f" QLineEdit:focus, QSpinBox:focus, QComboBox:focus,"
            f" QPlainTextEdit:focus, QTextEdit:focus {{"
            f" border-color: {c['accent']}; }}",
            f" QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled {{"
            f" color: {c['text-disabled']}; }}",
            # La fleche native de `QComboBox` est un triangle systeme, clair
            # sous Windows. On peint la zone, et le triangle prend la
            # couleur du texte plutot que celle du bureau.
            f" QComboBox::drop-down {{ border: none;"
            f" width: {e['7']}px; }}",
            f" QComboBox::down-arrow {{ image: none;"
            f" border-left: {e['2']}px solid transparent;"
            f" border-right: {e['2']}px solid transparent;"
            f" border-top: {e['2']}px solid {c['text-secondary']};"
            f" width: 0px; height: 0px; }}",
            f" QComboBox QAbstractItemView {{"
            f" background: {c['surface-raised']}; color: {c['text-primary']};"
            f" border: 1px solid {c['border']};"
            f" selection-background-color: {c['surface-hover']};"
            f" selection-color: {c['text-primary']}; }}",
            # --- arbres et listes ---------------------------------------
            # Les expandeurs natifs sont des chevrons systeme. `DESIGN.md`
            # (et la maquette du chutier v2) veulent un signe TYPOGRAPHIQUE
            # -- « le signe + dit qu'il y a des enfants, son absence dit
            # qu'il n'y en a pas ». On retire l'image native ; le signe est
            # pose par le composant, qui seul sait s'il y a des enfants.
            f" QTreeView::branch {{ background: transparent; }}",
            f" QTreeView::branch:has-children:closed,"
            f" QTreeView::branch:has-children:open {{ image: none; }}",
            f" QHeaderView::section {{ background: {c['surface-panel']};"
            f" color: {c['text-secondary']}; border: none;"
            f" padding: {e['2']}px {e['4']}px; }}",
            f" QAbstractItemView {{ outline: none; }}",
            # --- barres de defilement -----------------------------------
            # Natives, elles sont des rubans gris clair a fleches. Ici : un
            # pouce discret sur un rail transparent, sans boutons.
            f" QScrollBar:vertical {{ background: transparent;"
            f" width: {e['5']}px; margin: 0px; }}",
            f" QScrollBar:horizontal {{ background: transparent;"
            f" height: {e['5']}px; margin: 0px; }}",
            f" QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{"
            f" background: {c['border-strong']};"
            f" border-radius: {r['sm']}px;"
            f" min-height: {e['7']}px; min-width: {e['7']}px; }}",
            f" QScrollBar::handle:hover {{ background: {c['text-disabled']}; }}",
            f" QScrollBar::add-line, QScrollBar::sub-line {{"
            f" height: 0px; width: 0px; border: none;"
            f" background: transparent; }}",
            f" QScrollBar::add-page, QScrollBar::sub-page {{"
            f" background: transparent; }}",
            # --- curseurs (zoom) ----------------------------------------
            f" QSlider::groove:horizontal {{ background: {c['surface-sunken']};"
            f" height: {e['2']}px; border-radius: {r['sm']}px; }}",
            f" QSlider::sub-page:horizontal {{ background: {c['accent']};"
            f" height: {e['2']}px; border-radius: {r['sm']}px; }}",
            f" QSlider::handle:horizontal {{ background: {c['text-primary']};"
            f" width: {e['5']}px; height: {e['5']}px;"
            f" margin: -{e['3']}px 0px;"
            f" border-radius: {r['sm']}px; }}",
            f" QSlider::handle:horizontal:disabled {{"
            f" background: {c['text-disabled']}; }}",
            # --- barres d'onglets ---------------------------------------
            f" QTabBar {{ background: {c['surface-panel']};"
            f" qproperty-drawBase: 0; }}",
            f" QTabBar::tab {{ background: {c['surface-panel']};"
            f" color: {c['text-secondary']};"
            f" padding: {e['4']}px {e['6']}px; border: none; }}",
            f" QTabBar::tab:hover {{ color: {c['text-primary']}; }}",
            f" QTabBar::tab:selected {{ color: {c['text-primary']}; }}",
            # --- infobulles et menus ------------------------------------
            f" QToolTip {{ background: {c['surface-raised']};"
            f" color: {c['text-primary']};"
            f" border: 1px solid {c['border-strong']};"
            f" padding: {e['3']}px; }}",
            f" QMenu {{ background: {c['surface-raised']};"
            f" color: {c['text-primary']};"
            f" border: 1px solid {c['border']}; }}",
            f" QMenu::item:selected {{ background: {c['surface-hover']}; }}",
            # --- typographie de base ------------------------------------
            # `QLabel` et non `QWidget` : un `QLabel` pose sur une surface
            # deja peinte doit rester TRANSPARENT, sans quoi chaque libelle
            # dessinerait son propre rectangle par-dessus la ligne qui le
            # porte.
            f" QLabel {{ background: transparent;"
            f" color: {c['text-primary']};"
            f" font-family: {corps['famille']};"
            f" font-size: {corps['taille']}px; }}",
        )
    )
