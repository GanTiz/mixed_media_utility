# -*- coding: utf-8 -*-
"""Ecran de gestion de projet (story 7.1) -- la PREMIERE surface du produit.

Elle ouvre chaque session, avant tout projet : « on rentre par le projet,
jamais par un atelier » (`EXPERIENCE.md`, Reprise du travail apres
interruption). Elle s'affiche meme quand un seul projet existe, meme quand
aucun n'existe -- aucun saut direct dans un atelier.

Ce que la surface montre, et rien d'autre (`EPIC7-ARB-27`, `EPIC7-ARB-14`) :
nom, chemin, date de creation, date de modification. Le contenu d'un projet
se decouvre en l'ouvrant.

Ce qu'elle offre : **deux** actions -- creer, ouvrir un dossier --, un tri
sur les trois cles, une recherche, et une epingle **posee sur la ligne** :
tant que le menu contextuel n'existe pas (story 7.11), une commande
accessible au seul clic droit violerait `EPIC7-ARB-37`.

**Le bouton « importer un projet existant » a ete RETIRE** le 2026-08-27
(`EPIC7-ARB-83`). Ce qui a tranche est une mesure et non un gout :
``importer_un_projet`` et ``ouvrir_un_dossier`` appelaient tous deux
``_designer_et_accueillir``, le meme code au caractere pres. Deux boutons,
un seul comportement -- l'ecran promettait une distinction qui n'existait
nulle part, et l'essai de terrain l'a lue comme un defaut. La conclusion
« trois actions » d'`EPIC7-ARB-60` tombe ; sa lecture du finding E24
(aucune fusion de projets n'est specifiee) reste valable. Le vrai import --
fichier ``.json``, dossier de destination, case « importer les medias » --
part en story dediee 7.14 : **ne pas le reintroduire ici**.

Creer, depuis `EPIC7-ARB-82`, ne demande plus le dossier de projet
lui-meme : on designe le dossier de **destination**, on saisit le **nom**,
et l'apercu montre le chemin qui va naitre (:class:`DialogueDeCreation`).

Jetons et catalogue seulement : aucune couleur litterale (elles se lisent
dans ``jetons``), aucun libelle en dur (ils se lisent dans le catalogue).
Le **motif** d'un projet illisible fait exception a la seconde regle et
c'est le point : il est lu de l'exception du coeur et affiche verbatim, en
typographie de donnees, a cote d'une phrase du catalogue.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import catalogue as _catalogue
from . import depot_projets
from . import jetons
from .modele_projets import CLES_DE_TRI, LigneProjet, ModeleProjets
from .preferences_projets import PreferencesProjets

#: Propriete Qt qui marque un libelle porteur d'un motif LU du coeur. Les
#: tests de catalogue l'exemptent : ce texte ne vient pas du catalogue, et
#: c'est une exigence, pas une tolerance.
ROLE_MOTIF = "motif"

#: Les trois roles dont le texte est de la DONNEE pure -- le nom d'un
#: dossier, son chemin, le motif verbatim d'un echec du coeur. Aucun ne
#: vient du catalogue et aucun ne doit y entrer : ce sont les valeurs de
#: l'operatrice et les messages du coeur, pas des libelles du produit. Le
#: test de substitution de catalogue lit cette liste plutot que de deviner
#: quels textes exempter.
ROLES_DE_DONNEE_PURE = ("nom", "chemin", ROLE_MOTIF)

#: Format d'affichage d'une date de systeme de fichiers. C'est une forme de
#: DONNEE (typographie ``data``), pas une phrase : elle ne se traduit pas.
_FORMAT_DATE = "%Y-%m-%d %H:%M"


def _texte_de_date_de_modification(horodatage) -> str:
    """Rendre le ``mtime`` lisible, ou la chaine vide s'il n'y en a pas."""
    if horodatage is None:
        return ""
    return datetime.fromtimestamp(horodatage).strftime(_FORMAT_DATE)


def _texte_de_date_de_creation(horodatage) -> str:
    """Rendre le ``created`` du manifest dans le MEME format que le ``mtime``.

    Trouve par la revue de vague 2, en regardant l'ecran rendu : la ligne
    affichait « Cree le 2026-08-25T06:47:15Z   Modifie le 2026-08-25 06:49 ».
    La creation sortait **verbatim** du manifest (RFC3339 UTC), la
    modification etait formatee depuis le ``mtime`` -- deux formats sur la
    meme ligne, sur la premiere surface que voit un utilisateur.

    Arbitrage rendu par Egan le 2026-08-25 (`EPIC7-ARB-62`) : **les deux en
    heure locale**. La valeur AFFICHEE de la creation change donc (conversion
    depuis UTC) ; le manifest, lui, n'est jamais touche -- cette fonction ne
    fait que lire.

    Un horodatage illisible est rendu **tel quel** plutot qu'efface : une
    date qu'on ne sait pas formater reste une information, et la faire
    disparaitre serait la meme faute que le repli silencieux que ce module
    refuse ailleurs.
    """
    if not horodatage:
        return ""
    texte = str(horodatage)
    try:
        # `fromisoformat` de Python 3.11 lit le « Z » ; on reste tolerant au
        # cas ou un manifest ancien porterait un decalage explicite.
        instant = datetime.fromisoformat(texte.replace("Z", "+00:00"))
    except ValueError:
        return texte
    if instant.tzinfo is None:
        # Horodatage sans fuseau : le contrat du manifest l'ecrit en UTC
        # (`build_extraction_manifest`), on ne devine pas autre chose.
        instant = instant.replace(tzinfo=timezone.utc)
    return instant.astimezone().strftime(_FORMAT_DATE)


def _police(nom_de_style):
    """Fragment de feuille de style issu d'un style typographique des jetons."""
    style = jetons.TYPOGRAPHIE[nom_de_style]
    return (
        f"font-family: {style['famille']};"
        f" font-size: {style['taille']}px;"
        f" font-weight: {style['graisse']};"
    )


def _feuille_de_style():
    """Toute la peinture de l'ecran, lue des jetons -- zero litteral.

    Le fond est un **neutre plat** : la maquette y posait un degrade radial,
    ecart explicitement releve comme a corriger par ``DESIGN.md``.
    """
    c = jetons.COULEURS
    r = jetons.RAYONS
    e = jetons.ESPACEMENTS
    return (
        f"#ecran-projet {{ background: {c['surface-canvas']};"
        f" border-radius: {r['xl']}px; }}"
        f" QLabel {{ color: {c['text-primary']}; background: transparent; }}"
        f" QLabel[role='titre'] {{ {_police('display')} }}"
        f" QLabel[role='accroche'] {{ color: {c['text-secondary']}; {_police('body')} }}"
        f" QLabel[role='nom'] {{ {_police('body')} }}"
        f" QLabel[role='chemin'] {{ color: {c['text-secondary']};"
        f" {_police('data-sm')} }}"
        f" QLabel[role='donnee'] {{ color: {c['text-secondary']}; {_police('data-sm')} }}"
        f" QLabel[role='phrase-echec'] {{ color: {c['state-absent-text']};"
        f" {_police('body')} }}"
        f" QLabel[role='{ROLE_MOTIF}'] {{ color: {c['state-absent-text']};"
        f" {_police('data')} }}"
        # Revue de vague 2: `#liste-projets` ne peint que le QScrollArea
        # lui-meme. Son VIEWPORT et le widget PORTEUR qu'il contient sont
        # deux autres widgets, qui retombaient sur la palette par defaut et
        # posaient un large panneau GRIS CLAIR au milieu d'une interface
        # sombre -- sur la PREMIERE surface que voit un utilisateur. Un
        # selecteur descendant (` QWidget`) mordrait aussi sur les lignes:
        # le porteur est donc nomme, et vise nommement.
        f" #liste-projets, #porteur-de-liste {{"
        f" background: {c['surface-canvas']}; border: none; }}"
        # La bordure fait le TOUR des le repos, de la couleur du fond de la
        # ligne : invisible, mais la place est prise. Sans elle, la bordure
        # d'accent de la designation ci-dessous ajouterait sa largeur aux
        # quatre cotes et ferait sauter la ligne de 2 px au clic.
        f" QFrame[role='ligne'] {{ background: {c['surface-raised']};"
        f" border-radius: {r['md']}px;"
        f" border: {e['1']}px solid {c['surface-raised']}; }}"
        # Le lisere du dernier projet ouvert : un trait d'accent sur le
        # bord, jamais une preselection (AC 3).
        f" QFrame[role='ligne'][dernier='true'] {{"
        f" border-left: {e['2']}px solid {c['accent']}; }}"
        # **La designation se peint a l'accent** (correctif du 2026-08-26).
        # `surface-hover` sur `surface-raised`, c'est 10/255 d'ecart sur les
        # trois canaux neutres : mesurable, invisible a l'oeil --
        # Egan, premier essai de terrain, « on ne sait pas sur lequel on a
        # clique ». `DESIGN.md` par. 293 reserve pourtant l'accent a exactement
        # cet emploi : « ceci est selectionne ». Le fond survole reste, il ne
        # portait simplement pas le signal a lui seul.
        #
        # La bordure d'accent fait le tour et l'emporte sur le lisere du
        # dernier ouvert quand les deux coincident : c'est la meme chromie qui
        # dit la meme chose en plus fort, pas une information perdue.
        f" QFrame[role='ligne'][designe='true'] {{"
        f" background: {c['surface-hover']};"
        f" border: {e['1']}px solid {c['accent']}; }}"
        # **Les controles communs ne sont plus redefinis ici** (passe de chrome
        # du 2026-08-26). `feuille_application.py` les peint desormais pour
        # tout le produit -- et une feuille posee sur CE widget l'emporte sur
        # celle de l'application : tant que ces regles restaient, le bouton
        # primaire de l'ecran ne prenait jamais l'accent, mesure sur capture.
        # Ne subsiste ici que ce qui est PROPRE a cet ecran : la typographie
        # de ses controles, et la couleur d'une epingle posee.
        f" QLineEdit, QComboBox, QPushButton, QToolButton {{ {_police('body')} }}"
        f" QToolButton[epingle='true'] {{ color: {c['accent-text']}; }}"
        # La surface de creation est une FENETRE fille : le selecteur
        # descendant du QSS la traverse quand meme (elle reste dans l'arbre
        # d'objets), mais son fond, lui, ne se peint que si on le nomme.
        f" #dialogue-creation {{ background: {c['surface-panel']};"
        f" border-radius: {r['lg']}px; }}"
    )


class LigneProjetWidget(QFrame):
    """Une ligne de la liste : nom, chemin, deux dates, epingle.

    Une ligne dont le projet est illisible porte en plus la phrase du
    catalogue et le motif verbatim, et elle n'est **pas** ouvrable -- mais
    elle reste listee : la faire disparaitre ferait d'un message fugace le
    seul porteur d'un echec, ce que `EXPERIENCE.md` bannit.
    """

    designee = Signal(object)
    demande_ouverture = Signal(object)
    epingle_bascule = Signal(object)
    demande_retrait = Signal(object)

    def __init__(self, ligne: LigneProjet, chaines, *, dernier_ouvert=False, parent=None):
        super().__init__(parent)
        self.ligne = ligne
        self.porte_lisere = bool(dernier_ouvert)
        self.setProperty("role", "ligne")
        self.setProperty("dernier", "true" if self.porte_lisere else "false")
        self.setProperty("designe", "false")
        self.setObjectName("ligne-projet")

        e = jetons.ESPACEMENTS
        rangee = QHBoxLayout(self)
        rangee.setContentsMargins(e["5"], e["4"], e["5"], e["4"])
        rangee.setSpacing(e["5"])

        colonne = QVBoxLayout()
        colonne.setSpacing(e["1"])

        self.libelle_nom = QLabel(ligne.nom, self)
        self.libelle_nom.setProperty("role", "nom")
        self.libelle_nom.setWordWrap(True)
        colonne.addWidget(self.libelle_nom)

        self.libelle_chemin = QLabel(str(ligne.chemin), self)
        self.libelle_chemin.setProperty("role", "chemin")
        self.libelle_chemin.setWordWrap(True)
        colonne.addWidget(self.libelle_chemin)

        # Les deux dates. Une date absente laisse un libelle VIDE : elle ne
        # se deduit de rien (AC 2), et un tiret cadratin serait deja une
        # affirmation sur ce qu'on ne sait pas.
        dates = QHBoxLayout()
        dates.setSpacing(e["5"])
        self.libelle_creation = QLabel(self._texte_creation(ligne, chaines), self)
        self.libelle_creation.setProperty("role", "donnee")
        dates.addWidget(self.libelle_creation)
        self.libelle_modification = QLabel(
            self._texte_modification(ligne, chaines), self
        )
        self.libelle_modification.setProperty("role", "donnee")
        dates.addWidget(self.libelle_modification)
        dates.addStretch(1)
        colonne.addLayout(dates)

        if self.porte_lisere:
            self.libelle_lisere = QLabel(chaines["ecran-projet-dernier-ouvert"], self)
            self.libelle_lisere.setProperty("role", "donnee")
            self.libelle_lisere.setWordWrap(True)
            colonne.addWidget(self.libelle_lisere)

        # --- volet des projets illisibles (AC 4) -------------------------
        self.libelle_motif = None
        if not ligne.ouvrable:
            phrase = QLabel(chaines["ecran-projet-illisible"], self)
            phrase.setProperty("role", "phrase-echec")
            phrase.setWordWrap(True)
            colonne.addWidget(phrase)
            self.libelle_motif = QLabel(ligne.motif, self)
            self.libelle_motif.setProperty("role", ROLE_MOTIF)
            self.libelle_motif.setWordWrap(True)
            self.libelle_motif.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            colonne.addWidget(self.libelle_motif)

        rangee.addLayout(colonne, 1)

        # --- l'epingle, SUR la ligne (EPIC7-ARB-37) ----------------------
        self.bouton_epingle = QToolButton(self)
        self.bouton_epingle.setCheckable(True)
        self.bouton_epingle.setChecked(ligne.epingle)
        self.bouton_epingle.setProperty("epingle", "true" if ligne.epingle else "false")
        libelle_epingle = chaines[
            "ecran-projet-desepingler" if ligne.epingle else "ecran-projet-epingler"
        ]
        self.bouton_epingle.setToolTip(libelle_epingle)
        self.bouton_epingle.setAccessibleName(libelle_epingle)
        # Un signe, et non la fleche Qt native : celle-ci se peignait au
        # style de la PLATEFORME -- un gros triangle bleu, qui ne ressemblait a
        # aucune epingle (passe de chrome du 2026-08-26). Plein quand elle
        # retient, en creux quand elle est libre : la difference se voit sans
        # couleur, ce que `DESIGN.md` exige de toute redondance d'etat.
        self.bouton_epingle.setText(
            jetons.ICONOGRAPHIE[
                "glyphe-epingle" if ligne.epingle else "glyphe-epingle-absente"
            ]
        )
        self.bouton_epingle.clicked.connect(
            lambda: self.epingle_bascule.emit(self.ligne)
        )
        rangee.addWidget(self.bouton_epingle, 0, Qt.AlignmentFlag.AlignTop)

        # --- retirer de la liste, SUR la ligne aussi ---------------------
        # Meme raison que l'epingle juste au-dessus, et l'inventaire des menus
        # contextuels d'`EXPERIENCE.md` porte deja le geste : « Retirer de la
        # liste *(les fichiers ne sont pas touches)* ». L'AC de frontiere de
        # 7.11 interdit au menu contextuel de CREER une fonction -- il ne peut
        # donc pas fabriquer celle-ci, elle doit preexister.
        #
        # Le bouton est present sur TOUTES les lignes, y compris celles qui
        # portent un motif d'erreur (correctif du 2026-08-26). C'est meme le
        # cas qui l'exige : un projet dont le dossier a disparu du disque
        # redevient une ligne en erreur, ne se designe pas -- donc aucun geste
        # attache a la designation ne l'atteindrait, et il resterait la pour
        # toujours. Egan y est arrive au premier essai de terrain.
        #
        # Aucune confirmation : le geste ne touche pas au disque et se defait
        # en redesignant le dossier. Une modale ici ferait croire l'inverse.
        self.bouton_retirer = QToolButton(self)
        libelle_retirer = (
            f"{chaines['ecran-projet-retirer']} — "
            f"{chaines['ecran-projet-retirer-detail']}"
        )
        self.bouton_retirer.setText(jetons.ICONOGRAPHIE["glyphe-retirer"])
        self.bouton_retirer.setToolTip(libelle_retirer)
        self.bouton_retirer.setAccessibleName(libelle_retirer)
        self.bouton_retirer.clicked.connect(
            lambda: self.demande_retrait.emit(self.ligne)
        )
        rangee.addWidget(self.bouton_retirer, 0, Qt.AlignmentFlag.AlignTop)

    @staticmethod
    def _texte_creation(ligne, chaines) -> str:
        texte = _texte_de_date_de_creation(ligne.date_creation)
        if not texte:
            return ""
        return f"{chaines['ecran-projet-cree-le']} {texte}"

    @staticmethod
    def _texte_modification(ligne, chaines) -> str:
        texte = _texte_de_date_de_modification(ligne.date_modification)
        if not texte:
            return ""
        return f"{chaines['ecran-projet-modifie-le']} {texte}"

    def marquer_designee(self, designee: bool) -> None:
        """Peindre (ou depeindre) la designation courante."""
        self.setProperty("designe", "true" if designee else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, evenement):  # noqa: N802 (API Qt)
        # Revue de vague 2: seul le bouton GAUCHE agit. Le clic droit ne
        # declenche rien tant que le menu contextuel n'existe pas (7.11) --
        # « sauf "rattacher a", aucune commande n'existe uniquement au clic
        # droit » (`EPIC7-ARB-37`). La regle etait mesuree et gardee sur le
        # chutier, jamais ici: un double-clic DROIT ouvrait le projet aussi
        # surement qu'un double-clic gauche.
        if evenement.button() == Qt.MouseButton.LeftButton:
            self.designee.emit(self.ligne)
        super().mousePressEvent(evenement)

    def mouseDoubleClickEvent(self, evenement):  # noqa: N802 (API Qt)
        if evenement.button() == Qt.MouseButton.LeftButton:
            self.demande_ouverture.emit(self.ligne)
        super().mouseDoubleClickEvent(evenement)


class DialogueDeCreation(QDialog):
    """Creer un projet : dossier de destination, nom, apercu du chemin.

    `EPIC7-ARB-82`, verbatim d'Egan : « A la creation d'un projet on demande
    le dossier de destination, qui n'est pas le dossier de projet mais le
    dossier qui va contenir le dossier de projet. [...] J'obtiens un apercu
    qui montre le chemin du projet qui va etre cree. »

    Trois elements, et l'apercu est le troisieme parce qu'il est le seul qui
    dise ce qui va **arriver au disque** : il se recalcule a chaque frappe et
    il est calcule par ``depot_projets.dossier_cible`` -- la fonction que la
    creation appelle ensuite. Une seconde concatenation ecrite ici pourrait
    diverger de ce qui est cree, et l'apercu mentirait precisement la ou il
    sert.

    Le chemin de l'apercu est de la **DONNEE** (role ``chemin``,
    typographie ``data``), comme les chemins des lignes de la liste : ce
    n'est pas un libelle du produit, c'est la valeur de l'operatrice. La
    phrase d'apercu incomplet, elle, est un libelle et vit dans sa propre
    etiquette -- sans quoi elle serait exemptee du test de substitution de
    catalogue par le role de donnee de sa voisine.

    ``selecteur_de_dossier`` est injectable pour la meme raison qu'ailleurs
    dans ce module : un banc headless ne repond pas a une boite systeme.
    """

    def __init__(self, chaines, *, selecteur_de_dossier=None, parent=None):
        super().__init__(parent)
        self._chaines = chaines
        self._selecteur = selecteur_de_dossier or self._demander_un_dossier
        #: Le dossier de destination retenu, ou ``None`` tant qu'aucun ne
        #: l'est. Ce n'est PAS le dossier de projet : c'est son futur parent.
        self.dossier_parent = None

        self.setObjectName("dialogue-creation")
        self.setWindowTitle(chaines["ecran-projet-creer-titre"])
        self.setModal(True)

        e = jetons.ESPACEMENTS
        colonne = QVBoxLayout(self)
        colonne.setContentsMargins(e["6"], e["5"], e["6"], e["5"])
        colonne.setSpacing(e["4"])

        self.titre = QLabel(chaines["ecran-projet-creer-titre"], self)
        self.titre.setProperty("role", "titre")
        self.titre.setWordWrap(True)
        colonne.addWidget(self.titre)

        # --- 1. le dossier de DESTINATION -------------------------------
        self.libelle_dossier_parent = QLabel(
            chaines["ecran-projet-creer-dossier-parent"], self
        )
        colonne.addWidget(self.libelle_dossier_parent)

        rangee = QHBoxLayout()
        rangee.setSpacing(e["4"])
        # Le chemin choisi est de la DONNEE : il ne passe pas par le
        # catalogue et il porte la typographie de donnee.
        self.libelle_parent_choisi = QLabel("", self)
        self.libelle_parent_choisi.setProperty("role", "chemin")
        self.libelle_parent_choisi.setWordWrap(True)
        rangee.addWidget(self.libelle_parent_choisi, 1)
        self.bouton_choisir = QPushButton(
            chaines["ecran-projet-creer-choisir-dossier"], self
        )
        self.bouton_choisir.clicked.connect(self.choisir_le_dossier_parent)
        rangee.addWidget(self.bouton_choisir, 0)
        colonne.addLayout(rangee)

        # --- 2. le NOM du projet ----------------------------------------
        self.libelle_nom = QLabel(chaines["ecran-projet-creer-nom"], self)
        colonne.addWidget(self.libelle_nom)
        self.champ_nom = QLineEdit(self)
        self.champ_nom.setAccessibleName(chaines["ecran-projet-creer-nom"])
        # A CHAQUE FRAPPE, pas a la validation : c'est l'apercu qui porte la
        # promesse, il doit suivre la saisie caractere par caractere.
        self.champ_nom.textChanged.connect(lambda _texte: self.rafraichir_l_apercu())
        colonne.addWidget(self.champ_nom)

        # --- 3. l'APERCU du chemin resultant ----------------------------
        self.libelle_apercu_incomplet = QLabel(
            chaines["ecran-projet-creer-apercu-incomplet"], self
        )
        self.libelle_apercu_incomplet.setProperty("role", "accroche")
        self.libelle_apercu_incomplet.setWordWrap(True)
        colonne.addWidget(self.libelle_apercu_incomplet)

        self.libelle_apercu_titre = QLabel(
            chaines["ecran-projet-creer-apercu"], self
        )
        self.libelle_apercu_titre.setProperty("role", "accroche")
        self.libelle_apercu_titre.setWordWrap(True)
        colonne.addWidget(self.libelle_apercu_titre)

        self.libelle_apercu = QLabel("", self)
        self.libelle_apercu.setProperty("role", "chemin")
        self.libelle_apercu.setWordWrap(True)
        self.libelle_apercu.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        colonne.addWidget(self.libelle_apercu)

        colonne.addStretch(1)

        # --- les deux sorties -------------------------------------------
        boutons = QHBoxLayout()
        boutons.setSpacing(e["5"])
        boutons.addStretch(1)
        self.bouton_annuler = QPushButton(
            chaines["ecran-projet-creer-annuler"], self
        )
        self.bouton_annuler.clicked.connect(self.reject)
        boutons.addWidget(self.bouton_annuler)
        self.bouton_valider = QPushButton(
            chaines["ecran-projet-creer-valider"], self
        )
        self.bouton_valider.setProperty("primaire", "true")
        self.bouton_valider.clicked.connect(self.accept)
        boutons.addWidget(self.bouton_valider)
        colonne.addLayout(boutons)

        self.rafraichir_l_apercu()

    # --- saisie ---------------------------------------------------------

    def _demander_un_dossier(self):
        """Boite de dialogue systeme. Rend ``None`` a l'annulation."""
        choisi = QFileDialog.getExistingDirectory(
            self, self._chaines["ecran-projet-creer-dossier-parent"]
        )
        return Path(choisi) if choisi else None

    def choisir_le_dossier_parent(self):
        """Designer le dossier qui contiendra le projet.

        Une annulation ne DEFAIT pas un choix precedent : elle ne fait rien.
        Effacer le dossier deja retenu parce que l'operatrice a ferme la
        boite serait une perte silencieuse.
        """
        dossier = self._selecteur()
        if dossier is None:
            return None
        self.dossier_parent = Path(dossier)
        self.libelle_parent_choisi.setText(str(self.dossier_parent))
        self.rafraichir_l_apercu()
        return self.dossier_parent

    def nom_saisi(self) -> str:
        """Le nom saisi, sans ses blancs de bordure."""
        return self.champ_nom.text().strip()

    def valeurs(self):
        """Le couple ``(dossier parent, nom)``, ou ``None`` s'il est incomplet."""
        if self.dossier_parent is None or not self.nom_saisi():
            return None
        return (self.dossier_parent, self.nom_saisi())

    # --- apercu ---------------------------------------------------------

    def chemin_d_apercu(self):
        """Le chemin qui sera cree, ou ``None`` tant qu'il manque une valeur.

        Calcule par ``depot_projets.dossier_cible`` -- la MEME fonction que
        la creation. Un nom qui n'est pas un nom (un chemin) n'a pas
        d'apercu : le refus se dira a la validation, avec sa phrase.
        """
        valeurs = self.valeurs()
        if valeurs is None:
            return None
        try:
            return depot_projets.dossier_cible(*valeurs)
        except depot_projets.NamingError:
            return None

    def rafraichir_l_apercu(self):
        """Reporter l'etat de la saisie dans l'apercu et sur la validation."""
        chemin = self.chemin_d_apercu()
        complet = chemin is not None
        self.libelle_apercu_incomplet.setVisible(not complet)
        self.libelle_apercu_titre.setVisible(complet)
        self.libelle_apercu.setVisible(complet)
        self.libelle_apercu.setText("" if chemin is None else str(chemin))
        # Valider n'est actionnable qu'une fois les deux valeurs posees : un
        # bouton qui ne peut que refuser n'apprend rien.
        self.bouton_valider.setEnabled(complet)
        return chemin

    def texte_d_apercu(self) -> str:
        """Le texte d'apercu REELLEMENT affiche, quelle que soit la branche."""
        if self.libelle_apercu.isVisibleTo(self):
            return self.libelle_apercu.text()
        return self.libelle_apercu_incomplet.text()


class EcranProjet(QWidget):
    """La surface complete : liste, tri, recherche, deux actions.

    ``selecteur_de_dossier`` est injectable pour la meme raison que la
    fabrique de reglages : un banc headless ne peut pas repondre a une
    boite de dialogue systeme. Le defaut est la vraie boite de Qt.

    ``demandeur_de_creation`` l'est pour une raison de plus : la surface de
    creation (`EPIC7-ARB-82`) est une **modale**, et ``QDialog.exec()``
    entre dans une boucle d'evenements dont un banc ne sort pas. Le defaut
    construit et execute :class:`DialogueDeCreation` ; un banc y substitue
    une fonction qui rend directement le couple ``(parent, nom)``. Le
    dialogue lui-meme se teste alors **sans** ``exec()``, ce qui est le
    seul moyen de mesurer l'apercu frappe par frappe.
    """

    #: Emis avec la ``LigneProjet`` ouverte. C'est la coquille du socle
    #: (story 7.0) qui prend la main ensuite -- un seul projet a la fois.
    projet_ouvert = Signal(object)

    def __init__(
        self,
        *,
        modele: ModeleProjets | None = None,
        preferences: PreferencesProjets | None = None,
        chaines=None,
        selecteur_de_dossier=None,
        demandeur_de_creation=None,
        parent=None,
    ):
        super().__init__(parent)
        self._chaines = dict(_catalogue.CHAINES if chaines is None else chaines)
        chaines = self._chaines
        self.preferences = preferences if preferences is not None else PreferencesProjets()
        self._selecteur = selecteur_de_dossier or self._demander_un_dossier
        self._demandeur_de_creation = (
            demandeur_de_creation or self._demander_la_creation
        )
        #: La derniere surface de creation ouverte, gardee pour le banc et
        #: pour la relire ; `None` tant qu'aucune ne l'a ete.
        self.dialogue_creation = None
        self.modele = modele if modele is not None else self._modele_depuis_les_preferences()

        #: Index de la ligne DESIGNEE. `None` a l'affichage, et c'est une
        #: exigence : « dernier projet en tete, distingue par un lisere mais
        #: NON preselectionne » (AC 3). Rien ne s'ouvre sans designation.
        self.index_selection = None
        self._widgets_de_ligne: list[LigneProjetWidget] = []
        #: Dernier echec de geste, affiche sous la barre d'actions. Toujours
        #: une phrase du catalogue -- les motifs du coeur vivent sur les
        #: lignes, jamais ici.
        self._phrase_d_echec = ""

        self.setObjectName("ecran-projet")
        self.setWindowTitle(chaines["app-titre"])
        self.setStyleSheet(_feuille_de_style())

        e = jetons.ESPACEMENTS
        colonne = QVBoxLayout(self)
        colonne.setContentsMargins(e["8"], e["7"], e["8"], e["7"])
        colonne.setSpacing(e["6"])

        self.titre = QLabel(chaines["app-titre"], self)
        self.titre.setProperty("role", "titre")
        self.titre.setWordWrap(True)
        colonne.addWidget(self.titre)

        self.accroche = QLabel(chaines["ecran-projet-accroche"], self)
        self.accroche.setProperty("role", "accroche")
        self.accroche.setWordWrap(True)
        colonne.addWidget(self.accroche)

        # --- barre de tri et de recherche --------------------------------
        barre = QHBoxLayout()
        barre.setSpacing(e["5"])
        self.champ_recherche = QLineEdit(self)
        self.champ_recherche.setPlaceholderText(chaines["ecran-projet-recherche"])
        self.champ_recherche.setAccessibleName(chaines["ecran-projet-recherche"])
        self.champ_recherche.textChanged.connect(self._sur_recherche)
        barre.addWidget(self.champ_recherche, 1)

        self.libelle_tri = QLabel(chaines["ecran-projet-tri"], self)
        self.libelle_tri.setProperty("role", "donnee")
        barre.addWidget(self.libelle_tri, 0)

        self.selecteur_de_tri = QComboBox(self)
        self.selecteur_de_tri.setAccessibleName(chaines["ecran-projet-tri"])
        for cle in CLES_DE_TRI:
            self.selecteur_de_tri.addItem(chaines[f"ecran-projet-tri-{cle}"], cle)
        self.selecteur_de_tri.currentIndexChanged.connect(self._sur_tri)
        barre.addWidget(self.selecteur_de_tri, 0)
        colonne.addLayout(barre)

        # --- la liste -----------------------------------------------------
        self.zone_de_liste = QScrollArea(self)
        self.zone_de_liste.setObjectName("liste-projets")
        self.zone_de_liste.setWidgetResizable(True)
        self.zone_de_liste.setFrameShape(QFrame.Shape.NoFrame)
        self._porteur = QWidget(self.zone_de_liste)
        self._porteur.setObjectName("porteur-de-liste")
        # Le viewport du QScrollArea est un widget de plus, entre la zone et
        # le porteur: il ne se peint pas par feuille de style depuis le
        # parent, on le rend donc transparent pour que le fond du porteur
        # traverse.
        self.zone_de_liste.viewport().setAutoFillBackground(False)
        self.zone_de_liste.viewport().setStyleSheet("background: transparent;")
        self._colonne_de_liste = QVBoxLayout(self._porteur)
        self._colonne_de_liste.setContentsMargins(0, 0, 0, 0)
        self._colonne_de_liste.setSpacing(e["3"])
        self._colonne_de_liste.addStretch(1)
        self.zone_de_liste.setWidget(self._porteur)
        colonne.addWidget(self.zone_de_liste, 1)

        self.libelle_liste_vide = QLabel(chaines["ecran-projet-liste-vide"], self)
        self.libelle_liste_vide.setProperty("role", "accroche")
        self.libelle_liste_vide.setWordWrap(True)
        colonne.addWidget(self.libelle_liste_vide)

        self.libelle_echec = QLabel("", self)
        self.libelle_echec.setProperty("role", "phrase-echec")
        self.libelle_echec.setWordWrap(True)
        colonne.addWidget(self.libelle_echec)

        # --- les deux actions, plus l'ouverture de la designation ---------
        actions = QHBoxLayout()
        actions.setSpacing(e["5"])
        self.bouton_creer = QPushButton(chaines["ecran-projet-creer"], self)
        # **L'action primaire de cette surface, et la seule** (passe de chrome
        # du 2026-08-26). `key-projet.html` met « Creer un projet » a l'accent
        # plein et les deux autres en contour gris ; l'implementation posait
        # trois gris identiques, si bien que rien ne disait par ou commencer.
        # Une surface porte AU PLUS un accent d'aplat -- deux se neutralisent.
        self.bouton_creer.setProperty("primaire", "true")
        self.bouton_creer.clicked.connect(self.creer_projet)
        actions.addWidget(self.bouton_creer)
        self.bouton_ouvrir_dossier = QPushButton(
            chaines["ecran-projet-ouvrir-dossier"], self
        )
        self.bouton_ouvrir_dossier.clicked.connect(self.ouvrir_un_dossier)
        actions.addWidget(self.bouton_ouvrir_dossier)
        # **Aucun bouton d'import ici** (`EPIC7-ARB-83`) : il faisait
        # exactement ce que fait celui d'a cote. Le vrai import est la story
        # 7.14 -- fichier `.json`, destination, case « importer les medias ».
        actions.addStretch(1)
        self.bouton_ouvrir = QPushButton(chaines["ecran-projet-ouvrir"], self)
        self.bouton_ouvrir.clicked.connect(self.ouvrir_la_selection)
        actions.addWidget(self.bouton_ouvrir)
        colonne.addLayout(actions)

        self.rafraichir()

    # --- construction depuis les preferences -----------------------------

    def _modele_depuis_les_preferences(self) -> ModeleProjets:
        """Relire la liste connue, les epingles et le dernier ouvert.

        Un chemin disparu du disque n'est PAS retire en silence : il
        redevient une ligne, avec son motif. C'est l'utilisatrice qui
        retire (story 7.11).
        """
        lignes = [
            depot_projets.lire_projet(chemin)
            for chemin in self.preferences.projets_connus()
        ]
        return ModeleProjets(
            lignes,
            epingles=self.preferences.epingles(),
            dernier_ouvert=self.preferences.dernier_ouvert(),
        )

    def _enregistrer_les_preferences(self) -> None:
        self.preferences.definir_projets_connus(self.modele.chemins())
        self.preferences.definir_epingles(self.modele.epingles())
        self.preferences.definir_dernier_ouvert(self.modele.dernier_ouvert)
        self.preferences.enregistrer()

    # --- peinture ---------------------------------------------------------

    def lignes_affichees(self) -> tuple[LigneProjet, ...]:
        """Les lignes telles qu'elles sont peintes, dans l'ordre peint."""
        return tuple(widget.ligne for widget in self._widgets_de_ligne)

    def widgets_de_ligne(self) -> tuple[LigneProjetWidget, ...]:
        return tuple(self._widgets_de_ligne)

    def rafraichir(self) -> None:
        """Rebatir la liste depuis le modele, en oubliant la designation.

        La designation ne survit pas a un changement de tri ou de recherche :
        garder un index dans une liste reordonnee designerait un autre
        projet que celui que l'operatrice avait sous les yeux.
        """
        for widget in self._widgets_de_ligne:
            self._colonne_de_liste.removeWidget(widget)
            widget.setParent(None)
            widget.deleteLater()
        self._widgets_de_ligne = []
        self.index_selection = None

        for ligne in self.modele.lignes():
            widget = LigneProjetWidget(
                ligne,
                self._chaines,
                dernier_ouvert=self.modele.est_dernier_ouvert(ligne.chemin),
                parent=self._porteur,
            )
            widget.designee.connect(self._sur_designation)
            widget.demande_ouverture.connect(self.ouvrir_ligne)
            widget.epingle_bascule.connect(self._sur_epingle)
            widget.demande_retrait.connect(self.retirer_ligne)
            self._colonne_de_liste.insertWidget(
                self._colonne_de_liste.count() - 1, widget
            )
            self._widgets_de_ligne.append(widget)

        self.libelle_liste_vide.setVisible(not self._widgets_de_ligne)
        self.libelle_echec.setText(self._phrase_d_echec)
        self.libelle_echec.setVisible(bool(self._phrase_d_echec))
        self._mettre_a_jour_le_bouton_ouvrir()

    def _mettre_a_jour_le_bouton_ouvrir(self) -> None:
        self.bouton_ouvrir.setEnabled(self.index_selection is not None)

    # --- gestes -----------------------------------------------------------

    def _sur_recherche(self, terme) -> None:
        self.modele.definir_recherche(terme)
        self.rafraichir()

    def _sur_tri(self, indice) -> None:
        cle = self.selecteur_de_tri.itemData(indice)
        if cle:
            self.modele.definir_tri(cle)
            self.rafraichir()

    def _sur_designation(self, ligne: LigneProjet) -> None:
        """Designer une ligne. Une ligne en erreur ne se designe pas."""
        if not ligne.ouvrable:
            return
        for indice, widget in enumerate(self._widgets_de_ligne):
            designee = widget.ligne.chemin == ligne.chemin
            widget.marquer_designee(designee)
            if designee:
                self.index_selection = indice
        self._mettre_a_jour_le_bouton_ouvrir()

    def _sur_epingle(self, ligne: LigneProjet) -> None:
        self.modele.basculer_epingle(ligne.chemin)
        self._enregistrer_les_preferences()
        self.rafraichir()

    def retirer_ligne(self, ligne: LigneProjet) -> bool:
        """Retirer un projet de la liste connue. Le disque n'est pas touche.

        Correctif du 2026-08-26 : jusqu'ici rien ne retirait une ligne. Un
        dossier designe par megarde -- ou dont le projet a ete supprime a la
        main -- restait dans les preferences pour toujours, et en ligne
        d'erreur permanente s'il avait disparu.

        Le geste s'applique a **toute** ligne, ouvrable ou non : c'est la
        ligne en erreur qui en a le plus besoin, et elle ne se designe pas.

        Une ligne retiree emporte la phrase d'echec courante : elle a pu etre
        posee par la creation qui vient d'echouer sur ce dossier-la, et la
        laisser afficher un refus a propos d'une ligne qui n'est plus la
        n'aurait plus de referent.
        """
        retiree = self.modele.retirer(ligne.chemin)
        if not retiree:
            return False
        self._phrase_d_echec = ""
        self._enregistrer_les_preferences()
        self.rafraichir()
        return True

    def ouvrir_la_selection(self) -> LigneProjet | None:
        """Ouvrir la ligne designee -- et ne rien faire s'il n'y en a pas.

        C'est le volet actionnable de la non-preselection : sans
        designation prealable, aucun projet ne s'ouvre.
        """
        if self.index_selection is None:
            return None
        return self.ouvrir_ligne(self._widgets_de_ligne[self.index_selection].ligne)

    def ouvrir_ligne(self, ligne: LigneProjet) -> LigneProjet | None:
        """Ouvrir un projet : memoriser, emettre, laisser la main.

        Une ligne en erreur n'est PAS ouvrable : le geste est sans effet.
        Un projet dont les sources sont introuvables s'ouvre en revanche
        normalement -- l'ecran de gestion ne verifie rien du contenu.
        """
        if not ligne.ouvrable:
            return None
        self.modele.definir_dernier_ouvert(ligne.chemin)
        self._enregistrer_les_preferences()
        self.projet_ouvert.emit(ligne)
        return ligne

    # --- les deux actions -------------------------------------------------

    def _demander_un_dossier(self):
        """Boite de dialogue systeme du socle. Rend ``None`` a l'annulation."""
        choisi = QFileDialog.getExistingDirectory(self, self._chaines["app-titre"])
        return Path(choisi) if choisi else None

    def _demander_la_creation(self):
        """Ouvrir la surface de creation ; rendre ``(parent, nom)`` ou ``None``.

        Le dialogue est **retenu** sur l'ecran plutot que jete : il porte
        l'apercu que l'operatrice vient de lire, et une inspection
        d'apres-coup (banc, capture) doit pouvoir le relire.
        """
        dialogue = DialogueDeCreation(
            self._chaines, selecteur_de_dossier=self._selecteur, parent=self
        )
        self.dialogue_creation = dialogue
        if dialogue.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialogue.valeurs()

    def creer_projet(self) -> LigneProjet | None:
        """Creer = designer un dossier de DESTINATION, nommer, laisser l'outil creer.

        `EPIC7-ARB-82` : ce qui est designe n'est plus le dossier de projet
        mais celui qui va le contenir ; le dossier de projet nait ici, avec
        l'arborescence de travail que le coeur pose.

        Trois issues sans effet sur le disque : l'annulation, un dossier
        cible deja pourvu d'un projet (`ecran-projet-creation-dossier-occupe`
        -- le geste nominal sur ce dossier-la, c'est « ouvrir », et il n'y a
        volontairement aucune modale d'ecrasement) et un nom dont le coeur ne
        tire aucun identifiant (`ecran-projet-nom-refuse`).
        """
        demande = self._demandeur_de_creation()
        if demande is None:
            return None
        dossier_parent, nom = demande
        self._phrase_d_echec = ""
        try:
            ligne = depot_projets.creer_projet(dossier_parent, nom)
        except depot_projets.ProjetExistantError:
            self._phrase_d_echec = self._chaines[
                "ecran-projet-creation-dossier-occupe"
            ]
            self.rafraichir()
            return None
        except depot_projets.NamingError:
            self._phrase_d_echec = self._chaines["ecran-projet-nom-refuse"]
            self.rafraichir()
            return None
        return self._accueillir(ligne)

    def ouvrir_un_dossier(self) -> LigneProjet | None:
        """Designer un dossier deja connu ou non, et l'ouvrir.

        C'est la SEULE porte d'entree par le disque depuis `EPIC7-ARB-83`.
        Elle ne fusionne jamais deux projets : aucune ecriture dans un
        manifeste existant, et l'identifiant d'un projet lu est celui que son
        fichier declare -- jamais recalcule, jamais confronte a celui d'un
        autre projet (`EPIC7-ARB-60`). Deux projets qui declarent le meme
        identifiant coexistent, distincts par leur chemin.
        """
        dossier = self._selecteur()
        if dossier is None:
            return None
        self._phrase_d_echec = ""
        return self._accueillir(depot_projets.lire_projet(dossier))

    def _accueillir(self, ligne: LigneProjet) -> LigneProjet | None:
        """Ajouter la ligne a la liste connue, la peindre, puis l'ouvrir.

        Une ligne illisible est **ajoutee quand meme** : elle prend sa place
        dans la liste avec son motif, et elle ne s'ouvre pas.
        """
        pose = self.modele.ajouter(ligne)
        self._enregistrer_les_preferences()
        if not pose.ouvrable:
            self.rafraichir()
            return None
        ouverte = self.ouvrir_ligne(pose)
        self.rafraichir()
        return ouverte
