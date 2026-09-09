# -*- coding: utf-8 -*-
"""Surface Qt de la file « En attente de lecture » (story 7.3, AC 1 et 2b-2d).

La file vit **en haut du chutier, au-dessus de l'arbre** (`DESIGN.md`,
`bin-buffer` : « position: haut du chutier, au-dessus de l'arbre »), et le
bouton `Detecter` vit **avec elle**, jamais dans la previz (`EPIC7-ARB-40`,
role 4 d'`EXPERIENCE.md`).

Ce module ne porte que la surface : la file elle-meme, ses regles et ses
gestes sont dans `modele_zone_tampon`, sans Qt. Aucune couleur ni geometrie
litterale n'y est ecrite -- tout se lit dans `jetons` --, et aucun libelle
visible n'y est en dur -- tout se lit dans `catalogue`.

**Rien ne part d'ici tout seul** : ni une detection terminee ni une detection
echouee ne retire une ligne. Le seul geste qui retire est le bouton de
retrait, et il appelle `ModeleDeZoneTampon.retirer`.

**Trois gestes, un seul chemin d'entree** (`EPIC7-ARB-87`). Le
glisser-deposer, « Importer un fichier » et « Importer un dossier » appellent
tous les trois :meth:`ZoneTampon.deposer_des_chemins` : la parite avec la CLI
-- « realiser l'operation scan sur le contenu d'un dossier » -- se retrouve
sans qu'aucune de ces trois portes n'ait sa propre lecture du depot.

**Aucun selecteur de forme** (`EPIC7-ARB-89`) : plus rien ici ne demande a
l'operatrice si son depot est une pile ou une planche -- voir le modele, qui
porte la mesure ayant tranche.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
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

from .. import scan_ingest
from . import catalogue as _catalogue
from . import jetons
from . import modele_zone_tampon as _modele


def filtre_des_scans(chaines) -> str:
    """Le filtre du selecteur de fichiers, compose des extensions du COEUR.

    `scan_ingest.IMAGE_EXTENSIONS` et `scan_ingest.PDF_EXTENSIONS`, et rien
    d'autre : une seconde liste d'extensions ecrite dans la GUI divergerait de
    ce que l'ingestion accepte reellement, et le selecteur proposerait alors
    des fichiers que la passe refuse -- ou cacherait des fichiers qu'elle
    accepte. C'est une frontiere dure de ce depot, pas une commodite.

    La phrase autour des extensions vient du catalogue (`{extensions}`).
    """
    extensions = " ".join(
        f"*{suffixe}"
        for suffixe in (*scan_ingest.IMAGE_EXTENSIONS,
                        *scan_ingest.PDF_EXTENSIONS)
    )
    return chaines["zone-tampon-filtre-fichiers"].format(extensions=extensions)


def _feuille_de_la_file():
    """La feuille de style de la file, composee des seuls jetons de la spine.

    **Le nom d'une entree se lit sur `text-primary`, jamais sur le secondaire.**
    Defaut trouve en CAPTURANT la fenetre, comme les deux plus graves de la
    vague 2 : la regle `QLabel` de cette feuille ne couvre ni `QCheckBox` ni
    `QLineEdit`, qui retombaient sur la palette par defaut de la plateforme --
    du gris sombre sur un fond `surface-sunken`, donc un nom de fichier
    illisible. Aucune couche de relecture ne voit cela.
    """
    z = jetons.ZONE_TAMPON
    n = jetons.NEUTRES
    r = jetons.RAYONS
    return (
        f"QFrame#zone-tampon {{"
        f" background: {z['fond']};"
        f" border: 1px {z['style-de-bordure']} {z['bordure']};"
        f" border-radius: {z['rayon']}px; }}"
        f" QFrame#zone-tampon QLabel {{ color: {z['texte']}; }}"
        f" QFrame#zone-tampon QCheckBox {{ color: {n['text-primary']}; }}"
        f" QFrame#zone-tampon QLineEdit {{"
        f" color: {n['text-primary']};"
        f" background: {n['surface-raised']};"
        f" border: 1px solid {n['border']};"
        f" border-radius: {r['sm']}px; }}"
        # **Le fond de la zone defilante n'est PAS peint par defaut**, et
        # c'est le second defaut trouve a la capture -- meme famille que le
        # « fond de liste non peint » de la vague 2 : la vue et son hote
        # retombent sur la couleur `Base` de la plateforme (claire), et le
        # texte clair pose dessus devient illisible. On les rend transparents
        # pour que le `surface-sunken` de la file passe a travers.
        f" QFrame#zone-tampon QScrollArea {{ background: transparent;"
        f" border: none; }}"
        f" QFrame#zone-tampon QScrollArea > QWidget > QWidget {{"
        f" background: transparent; }}"
        # Boutons : `surface-raised`, comme toute commande de la spine.
        f" QFrame#zone-tampon QPushButton,"
        f" QFrame#zone-tampon QToolButton {{"
        f" color: {n['text-primary']};"
        f" background: {n['surface-raised']};"
        f" border: 1px solid {n['border']};"
        f" border-radius: {r['sm']}px;"
        f" padding: {jetons.ESPACEMENTS['2']}px {jetons.ESPACEMENTS['4']}px; }}"
        f" QFrame#zone-tampon QPushButton:hover,"
        f" QFrame#zone-tampon QToolButton:hover {{"
        f" background: {n['surface-hover']}; }}"
        f" QFrame#zone-tampon QPushButton:disabled {{"
        f" color: {n['text-disabled']}; }}"
    )


class LigneDeTampon(QFrame):
    """Une entree deposee : sa case, son nom, son dpi, son retrait.

    Plus de ligne de forme depuis `EPIC7-ARB-89` : le controle « pile de
    planches / planche seule » etait decoratif -- il affichait une deduction
    que rien ne transmettait au coeur, et offrait de corriger une valeur qui
    n'allait nulle part.
    """

    #: L'entree a change d'etat (case cochee, dpi saisi).
    changee = Signal(str)
    #: Geste explicite de retrait -- le seul qui enleve une entree.
    retrait_demande = Signal(str)

    def __init__(self, modele, identifiant, chaines, parent=None):
        super().__init__(parent)
        self._modele = modele
        self._identifiant = identifiant
        self._chaines = chaines
        self.setObjectName("ligne-de-tampon")
        e = jetons.ESPACEMENTS

        colonne = QVBoxLayout(self)
        colonne.setContentsMargins(e["3"], e["2"], e["3"], e["2"])
        colonne.setSpacing(e["1"])

        entree = modele.entree(identifiant)
        # Le NOM de l'entree occupe SA ligne, en pleine largeur : c'est la
        # donnee la plus longue de la ligne (un nom de fichier) et la seule
        # qu'on ne peut ni abreger ni deviner. Le partager avec deux boutons
        # le faisait tronquer -- mesure a la capture.
        # Le libelle est celui du MODELE (`libelle_d_entree`) : une entree a
        # plusieurs fichiers dit son nom de lot ET combien de fichiers elle
        # porte (`EPIC7-ARB-88`), une entree a un chemin dit son nom de
        # fichier, comme avant.
        self.case = QCheckBox(_modele.libelle_d_entree(entree, chaines), self)
        self.case.setChecked(entree.cochee)
        self.case.toggled.connect(self._sur_case)
        colonne.addWidget(self.case)

        bas = QHBoxLayout()
        bas.setContentsMargins(0, 0, 0, 0)
        bas.setSpacing(e["3"])
        self.champ_dpi = QLineEdit(self)
        # **Aucun defaut** (`EPIC7-ARB-44`) : le champ part VIDE, et son
        # invite dit ce qu'on attend sans le pre-remplir.
        self.champ_dpi.setPlaceholderText(chaines["zone-tampon-dpi"])
        self.champ_dpi.textChanged.connect(self._sur_dpi)
        bas.addWidget(self.champ_dpi, 1)

        self.bouton_retirer = QToolButton(self)
        self.bouton_retirer.setText(chaines["zone-tampon-retirer"])
        self.bouton_retirer.setToolTip(chaines["zone-tampon-retirer"])
        self.bouton_retirer.setAccessibleName(chaines["zone-tampon-retirer"])
        self.bouton_retirer.clicked.connect(
            lambda: self.retrait_demande.emit(self._identifiant))
        bas.addWidget(self.bouton_retirer, 0)
        colonne.addLayout(bas)

        # Motif d'echec et reliquat : VIDES tant que rien n'est arrive. Leur
        # texte, quand il vient, est celui du coeur -- verbatim (P9).
        self.libelle_motif = QLabel(self)
        self.libelle_motif.setWordWrap(True)
        self.libelle_motif.setVisible(False)
        # Le motif d'echec porte la chromie de TEXTE de l'absence, jamais son
        # aplat : « les chromies pleines ne portent jamais de glyphe ».
        self.libelle_motif.setStyleSheet(
            f"color: {jetons.CARTE_DE_TACHE['texte-echec']};")
        colonne.addWidget(self.libelle_motif)

        self.libelle_reliquat = QLabel(self)
        self.libelle_reliquat.setWordWrap(True)
        self.libelle_reliquat.setVisible(False)
        colonne.addWidget(self.libelle_reliquat)

        # Hors perimetre (F14, revue de vague 3) : classe DISJOINTE du
        # reliquat -- son propre libelle, jamais fusionne avec
        # `libelle_reliquat`. Avant ce correctif, une page hors perimetre ne
        # s'affichait NULLE PART (grep : zero occurrence de `hors_perimetre`
        # sous `gui/`). Pas de cle de catalogue dediee disponible dans le
        # perimetre de ce correctif (`catalogue.py` appartient a un autre
        # lot de la revue) : on reutilise donc le MECANISME d'affichage deja
        # en place pour le reliquat -- meme phrase de catalogue
        # (`zone-tampon-reliquat`, deja generique : "page" et "motif" verbatim,
        # sans supposer de quelle classe ils viennent) -- et on ajoute le
        # `projet_a_utiliser`, verbatim, avec le separateur deja au
        # catalogue. C'est un pis-aller assume : une phrase dediee
        # ("Hors périmètre : {page} — {motif} — utiliser {projet}") serait
        # plus lisible, mais exige une entree de `catalogue.py`, hors de la
        # liste de fichiers de ce correctif -- a arbitrer separement.
        self.libelle_hors_perimetre = QLabel(self)
        self.libelle_hors_perimetre.setWordWrap(True)
        self.libelle_hors_perimetre.setVisible(False)
        colonne.addWidget(self.libelle_hors_perimetre)

        self.rafraichir()

    @property
    def identifiant(self) -> str:
        return self._identifiant

    # --- Gestes --------------------------------------------------------

    def _sur_case(self, cochee):
        self._modele.cocher(self._identifiant, cochee)
        self.changee.emit(self._identifiant)

    def _sur_dpi(self, texte):
        texte = texte.strip()
        try:
            self._modele.poser_le_dpi(
                self._identifiant, texte if texte else None)
        except (ValueError, _modele.ZoneTamponError):
            # Une saisie incomplete ou non numerique n'est pas un dpi : on
            # l'efface plutot que d'en inventer un. Le bouton reste alors
            # inactif ET dit pourquoi -- c'est la garde d'`EPIC7-ARB-44`.
            self._modele.poser_le_dpi(self._identifiant, None)
        self.changee.emit(self._identifiant)

    # --- Rendu ---------------------------------------------------------

    def rafraichir(self):
        """Relire l'entree et reporter son etat sur les widgets."""
        entree = self._modele.entree(self._identifiant)
        if entree is None:
            return
        self.case.setChecked(entree.cochee)
        # Le NOM se relit a chaque rafraichissement : le nom de lot d'une
        # selection n'existe qu'une fois le projet pose, et il arrive donc
        # APRES le depot dans le cas ou la file a ete remplie avant.
        self.case.setText(_modele.libelle_d_entree(entree, self._chaines))
        # Le champ reflete le dpi du MODELE. Sans cela, un dpi pose autrement
        # que par la frappe -- par un rechargement, par un banc -- laissait le
        # champ vide alors que le bouton, lui, devenait actif : la surface
        # disait le contraire de l'etat. Defaut vu a la CAPTURE, par aucun test.
        attendu = "" if entree.dpi is None else str(entree.dpi)
        if self.champ_dpi.text().strip() != attendu:
            # `blockSignals` : reecrire le champ rappellerait `_sur_dpi`, qui
            # rappellerait `rafraichir` -- une boucle, pas un rendu.
            self.champ_dpi.blockSignals(True)
            self.champ_dpi.setText(attendu)
            self.champ_dpi.blockSignals(False)

        self.libelle_motif.setText(entree.motif or "")
        self.libelle_motif.setVisible(bool(entree.motif))

        if entree.reliquat:
            modele_de_phrase = self._chaines["zone-tampon-reliquat"]
            separateur = self._chaines["atelier-scan-separateur"]
            self.libelle_reliquat.setText(separateur.join(
                modele_de_phrase.format(page=page, motif=motif)
                for page, motif in entree.reliquat))
            self.libelle_reliquat.setVisible(True)
        else:
            self.libelle_reliquat.setText("")
            self.libelle_reliquat.setVisible(False)

        if entree.hors_perimetre:
            # F14 : disjoint du reliquat, son propre libelle ET ses propres
            # chaines de catalogue -- `hors_perimetre` est une classe disjointe
            # du reliquat dans la partition de 5.24, la confondre a l'ecran
            # referait a l'oeil la fusion que le coeur refuse.
            #
            # Deux formes selon ce que le document porte : quand il livre le
            # projet a utiliser, on le NOMME (`EPIC5-ARB-105` : l'operateur
            # « ne doit pas avoir a le deviner »). Quand il ne le livre pas, on
            # n'invente aucun texte pour son absence.
            avec_projet = self._chaines["zone-tampon-hors-perimetre-projet"]
            sans_projet = self._chaines["zone-tampon-hors-perimetre"]
            separateur = self._chaines["atelier-scan-separateur"]
            phrases = []
            for page, motif, projet in entree.hors_perimetre:
                if projet is None:
                    phrase = sans_projet.format(page=page, motif=motif)
                else:
                    phrase = avec_projet.format(
                        projet=projet, page=page, motif=motif)
                phrases.append(phrase)
            self.libelle_hors_perimetre.setText(separateur.join(phrases))
            self.libelle_hors_perimetre.setVisible(True)
        else:
            self.libelle_hors_perimetre.setText("")
            self.libelle_hors_perimetre.setVisible(False)

    def texte_du_motif(self) -> str:
        """Le motif affiche, tel quel -- pour le banc comme pour l'oeil."""
        return self.libelle_motif.text()

    def texte_du_reliquat(self) -> str:
        return self.libelle_reliquat.text()

    def texte_du_hors_perimetre(self) -> str:
        """Le texte AFFICHE pour les pages hors perimetre (F14)."""
        return self.libelle_hors_perimetre.text()


class ZoneTampon(QFrame):
    """La file complete : son titre, ses lignes, et le bouton `Detecter`."""

    #: Emise au clic sur `Detecter`, avec les entrees COCHEES du modele.
    detection_demandee = Signal(object)

    def __init__(self, chaines=None, modele=None, parent=None,
                 selecteur_de_fichiers=None, selecteur_de_dossier=None):
        super().__init__(parent)
        self._chaines = dict(_catalogue.CHAINES if chaines is None else chaines)
        chaines = self._chaines
        self.modele = _modele.ModeleDeZoneTampon() if modele is None else modele
        self._lignes: list[LigneDeTampon] = []
        # **Les deux selecteurs systeme sont injectables, et c'est tout ce
        # qu'ils sont** : le defaut ouvre le vrai `QFileDialog`, et le banc y
        # substitue un appelable qui rend des chemins. Meme couture que
        # `AtelierScan.fonction_de_detection` -- sans elle, mesurer
        # `EPIC7-ARB-87` exigerait de piloter une boite de dialogue modale du
        # systeme, ce qu'aucun banc offscreen ne sait faire.
        self._choisir_des_fichiers = (
            self._selecteur_de_fichiers_natif if selecteur_de_fichiers is None
            else selecteur_de_fichiers)
        self._choisir_un_dossier = (
            self._selecteur_de_dossier_natif if selecteur_de_dossier is None
            else selecteur_de_dossier)
        e = jetons.ESPACEMENTS

        self.setObjectName("zone-tampon")
        self.setStyleSheet(_feuille_de_la_file())
        self.setAcceptDrops(True)

        colonne = QVBoxLayout(self)
        colonne.setContentsMargins(
            e["panel-pad"], e["panel-pad"], e["panel-pad"], e["panel-pad"])
        colonne.setSpacing(e["3"])

        self.titre = QLabel(chaines["zone-tampon-titre"], self)
        self.titre.setWordWrap(True)
        colonne.addWidget(self.titre)

        self.libelle_vide = QLabel(chaines["zone-tampon-vide"], self)
        self.libelle_vide.setWordWrap(True)
        colonne.addWidget(self.libelle_vide)

        # **Les deux gestes d'import** (`EPIC7-ARB-87`), a cote du depot :
        # « on n'a aucun bouton pour importer un scan autrement que par un
        # clique-depose ». Ils sont SECONDAIRES -- l'action primaire de cette
        # boite reste `Detecter`, et deux accents concurrents ne diraient plus
        # ou est le geste principal. Ils alimentent le MEME
        # `deposer_des_chemins` que le glisser-deposer.
        # **Ils sont EMPILES, pas cote a cote**, et c'est une contrainte
        # mesuree : la colonne du chutier a pour plancher `bin-min-width`, et
        # deux boutons sur une meme rangee n'y laissent qu'une centaine de
        # pixels chacun -- moins que le plus court libelle imaginable une fois
        # gonfle de 40 % (regle i18n de `DESIGN.md`). Cote a cote, la colonne
        # reclamait 558 px de plancher au lieu de 250, la poignee de largeur
        # ne pouvait plus la comprimer, et la scene sortait de la fenetre :
        # `stage-min-width`, que la coquille enonce comme « jamais franchi »,
        # l'etait. Mesure du 2026-08-27, sur la coquille assemblee.
        self.bouton_importer_fichier = QPushButton(
            chaines["zone-tampon-importer-fichier"], self)
        self.bouton_importer_fichier.setObjectName("bouton-importer-fichier")
        # Le libelle est court pour tenir dans le plancher ; le geste complet
        # se dit en infobulle, qui n'a aucune largeur a respecter. C'est la
        # meme phrase que le titre du selecteur, donc une seule redaction.
        self.bouton_importer_fichier.setToolTip(
            chaines["zone-tampon-selecteur-fichiers"])
        self.bouton_importer_fichier.setAccessibleName(
            chaines["zone-tampon-selecteur-fichiers"])
        self.bouton_importer_fichier.clicked.connect(self.importer_des_fichiers)
        colonne.addWidget(self.bouton_importer_fichier)
        self.bouton_importer_dossier = QPushButton(
            chaines["zone-tampon-importer-dossier"], self)
        self.bouton_importer_dossier.setObjectName("bouton-importer-dossier")
        self.bouton_importer_dossier.setToolTip(
            chaines["zone-tampon-selecteur-dossier"])
        self.bouton_importer_dossier.setAccessibleName(
            chaines["zone-tampon-selecteur-dossier"])
        self.bouton_importer_dossier.clicked.connect(self.importer_un_dossier)
        colonne.addWidget(self.bouton_importer_dossier)

        # Les lignes vivent dans une zone defilante : la file peut grandir
        # sans jamais pousser le chutier ni la fenetre au-dela de son plancher.
        self.defilement = QScrollArea(self)
        self.defilement.setWidgetResizable(True)
        self.defilement.setFrameShape(QFrame.Shape.NoFrame)
        # Jamais de defilement HORIZONTAL : une ligne qui deborde en largeur
        # cache le geste qui la termine. Les libelles reviennent a la ligne,
        # la file defile en hauteur, et rien ne sort du cadre.
        self.defilement.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._hote = QWidget(self.defilement)
        self.pile = QVBoxLayout(self._hote)
        self.pile.setContentsMargins(0, 0, 0, 0)
        self.pile.setSpacing(e["2"])
        self.pile.addStretch(1)
        self.defilement.setWidget(self._hote)
        self.defilement.viewport().setAutoFillBackground(False)
        self.defilement.setVisible(False)
        # La file ne mange jamais l'arbre : au-dela de quelques lignes elle
        # defile. La hauteur se COMPOSE des jetons de la spine, elle n'est pas
        # un litteral (frontiere de geometrie de 7.0).
        self.defilement.setMaximumHeight(
            e["row-height"] * jetons.ZONE_TAMPON["lignes-visibles"])
        colonne.addWidget(self.defilement, 1)

        self.bouton_detecter = QPushButton(chaines["zone-tampon-detecter"], self)
        # L'action primaire de l'atelier Scan : tout ce qui precede la sert.
        # Grisee tant qu'aucune entree n'est prete, elle retombe alors sur le
        # gris desactive -- l'accent ne ment jamais sur la disponibilite.
        self.bouton_detecter.setProperty("primaire", "true")
        self.bouton_detecter.setObjectName("bouton-detecter")
        self.bouton_detecter.clicked.connect(self._sur_detecter)
        colonne.addWidget(self.bouton_detecter)

        # Un bouton inactif DIT pourquoi il l'est (`EPIC7-ARB-44`) -- dans une
        # phrase posee a cote, jamais dans son libelle : un libelle qui
        # s'allonge cale la boite sur la longueur de la chaine, et la regle
        # i18n de `DESIGN.md` l'interdit.
        self.libelle_inactif = QLabel(self)
        self.libelle_inactif.setWordWrap(True)
        colonne.addWidget(self.libelle_inactif)

        self.rafraichir()

    # --- Depot ---------------------------------------------------------

    def deposer_des_chemins(self, chemins):
        """Deposer un chemin, une selection ou un dossier ; rend les entrees."""
        creees = self.modele.deposer(chemins)
        for entree in creees:
            ligne = LigneDeTampon(
                self.modele, entree.identifiant, self._chaines, self._hote)
            ligne.changee.connect(lambda _ignore: self.rafraichir())
            ligne.retrait_demande.connect(self.retirer)
            # Insertion AVANT l'etirement final : sans cela les lignes
            # s'empilent sous un ressort et n'apparaissent nulle part.
            self.pile.insertWidget(self.pile.count() - 1, ligne)
            self._lignes.append(ligne)
        self.rafraichir()
        return creees

    # --- Les deux gestes d'import par l'explorateur (EPIC7-ARB-87) ------

    def _selecteur_de_fichiers_natif(self):
        """Le vrai selecteur multi-fichiers du systeme ; rend des chemins.

        Le filtre vient de :func:`filtre_des_scans`, donc des extensions du
        coeur. Un « Annuler » rend une liste vide, et rien n'est depose.
        """
        chemins, _filtre = QFileDialog.getOpenFileNames(
            self, self._chaines["zone-tampon-selecteur-fichiers"], "",
            filtre_des_scans(self._chaines))
        return [Path(chemin) for chemin in chemins]

    def _selecteur_de_dossier_natif(self):
        """Le vrai selecteur de dossier du systeme ; rend zero ou un chemin."""
        chemin = QFileDialog.getExistingDirectory(
            self, self._chaines["zone-tampon-selecteur-dossier"])
        return [Path(chemin)] if chemin else []

    def importer_des_fichiers(self):
        """« Importer un fichier » : la selection part dans la MEME file.

        Une selection de plusieurs fichiers est **un lot** et non N entrees
        (`EPIC7-ARB-88`) -- c'est `ModeleDeZoneTampon.deposer` qui le tient,
        pas ce geste-ci : les trois portes d'entree de la file passent par le
        meme point et ne peuvent donc pas diverger.
        """
        return self._deposer_le_choix(self._choisir_des_fichiers())

    def importer_un_dossier(self):
        """« Importer un dossier » : la parite avec la CLI, rendue.

        « L'interface fait perdre la possibilite que la CLI donnait, a savoir
        realiser l'operation scan sur le contenu d'un dossier. » Un dossier
        reste **une** entree : c'est deja un lot pour le coeur.
        """
        return self._deposer_le_choix(self._choisir_un_dossier())

    def _deposer_le_choix(self, chemins):
        """Deposer ce qu'un selecteur a rendu, ou rien s'il a rendu rien.

        Un « Annuler » (aucun chemin) ne cree aucune entree : une file qui
        gagnerait une ligne vide sur un renoncement serait un fond de tiroir.
        """
        chemins = [Path(chemin) for chemin in (chemins or ())]
        if not chemins:
            return ()
        return self.deposer_des_chemins(chemins)

    def dragEnterEvent(self, evenement):  # noqa: N802 (API Qt)
        """Accepter un glisser qui porte des chemins, refuser le reste."""
        if evenement.mimeData().hasUrls():
            evenement.acceptProposedAction()
        else:
            evenement.ignore()

    def dragMoveEvent(self, evenement):  # noqa: N802 (API Qt)
        if evenement.mimeData().hasUrls():
            evenement.acceptProposedAction()
        else:
            evenement.ignore()

    def dropEvent(self, evenement):  # noqa: N802 (API Qt)
        """Deposer : une selection d'images est **UN lot** (`EPIC7-ARB-88`).

        « Si je glisse plusieurs fichiers TIFF d'un coup [...] il devrait y
        avoir un unique ingest.json pour ce lot de fichiers. » La repartition
        exacte est celle de `modele_zone_tampon._grouper_le_depot` : ce
        gestionnaire ne fait que transmettre les chemins, dans l'ordre.
        """
        donnees = evenement.mimeData()
        if not donnees.hasUrls():
            evenement.ignore()
            return
        chemins = [
            Path(url.toLocalFile()) for url in donnees.urls()
            if url.toLocalFile()
        ]
        if chemins:
            self.deposer_des_chemins(chemins)
        evenement.acceptProposedAction()

    # --- Retrait, et lui seul -----------------------------------------

    def retirer(self, identifiant):
        """Retirer une entree -- geste explicite, jamais automatique."""
        if not self.modele.retirer(identifiant):
            return False
        for ligne in list(self._lignes):
            if ligne.identifiant == identifiant:
                self._lignes.remove(ligne)
                self.pile.removeWidget(ligne)
                ligne.setParent(None)
                ligne.deleteLater()
        self.rafraichir()
        return True

    # --- Lecture -------------------------------------------------------

    def lignes(self) -> tuple:
        """Les lignes affichees, dans l'ordre du depot."""
        return tuple(self._lignes)

    def ligne(self, identifiant) -> LigneDeTampon | None:
        for ligne in self._lignes:
            if ligne.identifiant == identifiant:
                return ligne
        return None

    def rafraichir(self):
        """Reporter l'etat du modele sur toute la surface."""
        for ligne in self._lignes:
            ligne.rafraichir()
        vide = not self.modele.entrees
        self.libelle_vide.setVisible(vide)
        self.defilement.setVisible(not vide)
        cle = self.modele.motif_d_inactivite()
        self.bouton_detecter.setEnabled(cle is None)
        self.libelle_inactif.setText("" if cle is None else self._chaines[cle])
        self.libelle_inactif.setVisible(cle is not None)

    def _sur_detecter(self):
        """Le clic, et **rien d'autre**, declenche une detection."""
        if not self.modele.peut_detecter():
            return
        self.detection_demandee.emit(self.modele.cochees())
