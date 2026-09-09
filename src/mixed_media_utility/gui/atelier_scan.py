# -*- coding: utf-8 -*-
"""Atelier Scan, PREMIER temps -- deposer, detecter, annoncer (story 7.3).

« L'atelier Scan se deroule en deux temps, jamais en un » (`EXPERIENCE.md`).
Ceci est le **premier** : deposer (la file vit au chutier), detecter, et
**annoncer ce qui manque avant qu'un seul TIFF ne soit ecrit**. Le **second**
temps -- juger : mode PDF, verrous, galerie, mode lecteur -- est la story 7.4
et vit dans `gui/scan_jugement.py` ; l'ecriture des frames est la 7.6.

**Ce que ce module fait, en une phrase** : il soumet a l'executeur la fonction
du coeur `scan_detect.run_scan_detect`, une tache par entree cochee, il montre
une carte par tache puis **une carte par lot que le coeur a trouve**, et il
annonce la completude de chacun -- **lue** de
`modele_chutier._completude_du_document`, jamais recalculee ici.

**Ce qu'il ne fait pas, et c'est structurel** : il ne decoupe aucune pile. Le
tri par QR est une fonction du coeur (5.24, AC 1) ; cet ecran **montre** son
resultat, il ne rejoue aucune de ses regles (`EPIC7-ARB-64`, AC 8c). Ce que la
detection n'a rattache a rien **reste dans la file, nomme**, avec le motif lu
du rapport de tri.

**Aucune jauge, aucun chiffre de duree** : voir `cartes_taches`, qui porte
l'interdit d'`EPIC7-ARB-67` et sa condition de levee.

Le motif d'un echec est celui du coeur, verbatim : `executeur.Tache` porte
deja `str(exc)`, et la carte le pose tel quel (P9).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import scan_detect, scan_ingest
from ..io import project_layout
from . import catalogue as _catalogue
from . import cartes_taches as _cartes
from . import chargeur_detections as _chargeur
from . import executeur as _executeur
from . import jetons
from . import modele_chutier as _modele
from . import modele_zone_tampon as _modele_tampon


@dataclass(frozen=True)
class Annonce:
    """La completude d'un lot detecte, telle qu'elle sera dite.

    Les trois champs viennent de `modele_chutier._completude_du_document` et
    du document lui-meme. **Aucun n'est derive ici** : une seconde
    implementation de la completude divergerait de celle du chutier le jour ou
    l'une des deux change, et l'arbre contredirait l'annonce.
    """

    lot: str
    badge: str
    planches_manquantes: tuple


def _cle_de_lot(entree) -> tuple:
    """Ce qui fait que deux entrees designent LE MEME lot pour le coeur.

    L'ordre du geste ne compte pas. `scan_ingest._ordonner_une_selection`
    range une selection par nom normalise avant de l'ingerer : deposer
    `a.tiff` puis `b.tiff`, ou l'inverse, donne le meme lot, le meme slug et
    donc le meme `ingest.json`. Une cle qui garderait l'ordre du depot voyait
    la deux choses distinctes -- et le dedoublonnage F15, justement la pour
    empecher deux passes de viser le meme `ingest.json`, laissait alors partir
    DEUX appels concurrents. Mesure du defaut le 2026-08-27 : deux depots des
    memes deux fichiers, ordres inverses, deux appels au coeur.

    La casse est neutralisee pour la meme raison que dans le coeur : sur NTFS,
    `Planche.tiff` et `planche.tiff` sont un seul fichier.
    """
    return tuple(sorted(
        (str(chemin.parent), chemin.name.casefold()) for chemin in entree.chemins))


class AtelierScan(QWidget):
    """La page Scan : les cartes de tache, et l'annonce de completude."""

    #: Emise a la fin de chaque tache, avec le `ScanDetectOutcome` du coeur.
    detection_terminee = Signal(object)
    #: Emise a chaque annonce, avec le tuple d':class:`Annonce` courant.
    #: **Contrat C (V3.a)** : au moment ou elle part, aucun TIFF n'est ecrit.
    completude_annoncee = Signal(object)
    #: Emise des que l'atelier a pose quelque chose SUR une entree de la file
    #: -- un motif d'echec, un reliquat, les lot trouves. La surface de la file
    #: vit au chutier : elle ne peut se redessiner que si on le lui dit. Un
    #: modele juste et une surface muette ne valent rien (defaut mesure ici).
    file_mise_a_jour = Signal()

    def __init__(self, chaines=None, executeur=None, fonction_de_detection=None,
                 parent=None, fonction_de_confirmation=None):
        super().__init__(parent)
        self._chaines = dict(_catalogue.CHAINES if chaines is None else chaines)
        chaines = self._chaines
        self._executeur = _executeur.Executeur(self) if executeur is None else executeur
        # **Le point d'appel du coeur est injectable, et c'est tout ce qu'il
        # est** : le defaut est la vraie fonction, et le banc y substitue un
        # appelable qui leve de VRAIES exceptions du coeur. Sans cette couture,
        # mesurer un refus inter-projets exigerait de peindre des planches.
        self._detecter = (
            scan_detect.run_scan_detect if fonction_de_detection is None
            else fonction_de_detection)
        # **La modale de remplacement est injectable pour la MEME raison**
        # (`EPIC7-ARB-90`) : le defaut est la vraie boite Qt, et le banc y
        # substitue un appelable qui rend `True` ou `False` sans rien
        # afficher. Sans cette couture, mesurer « Oui » et « Non » exigerait
        # de piloter une modale bloquante -- ce qu'un banc offscreen ne fait
        # pas. Le motif est celui de `fonction_de_detection`, pas un autre.
        self._confirmer_le_remplacement = (
            self._modale_de_remplacement if fonction_de_confirmation is None
            else fonction_de_confirmation)
        self._project_dir = None
        self._modele_de_file = None
        self._annonces: tuple[Annonce, ...] = ()
        e = jetons.ESPACEMENTS

        self.setObjectName("atelier-scan")
        rangee = QHBoxLayout(self)
        rangee.setContentsMargins(e["6"], e["6"], e["6"], e["6"])
        rangee.setSpacing(e["gutter"])

        # --- Colonne gauche : l'annonce de completude, avant toute ecriture.
        gauche = QFrame(self)
        gauche.setObjectName("annonce-de-completude")
        colonne = QVBoxLayout(gauche)
        colonne.setContentsMargins(0, 0, 0, 0)
        colonne.setSpacing(e["3"])

        self.titre = QLabel(chaines["atelier-scan-titre"], gauche)
        self.titre.setWordWrap(True)
        colonne.addWidget(self.titre)

        self.titre_annonce = QLabel(chaines["atelier-scan-annonce"], gauche)
        self.titre_annonce.setWordWrap(True)
        colonne.addWidget(self.titre_annonce)

        self.libelle_sans_annonce = QLabel(
            chaines["atelier-scan-annonce-vide"], gauche)
        self.libelle_sans_annonce.setWordWrap(True)
        colonne.addWidget(self.libelle_sans_annonce)

        self._hote_annonces = QWidget(gauche)
        self.pile_annonces = QVBoxLayout(self._hote_annonces)
        self.pile_annonces.setContentsMargins(0, 0, 0, 0)
        self.pile_annonces.setSpacing(e["2"])
        colonne.addWidget(self._hote_annonces)
        colonne.addStretch(1)
        rangee.addWidget(gauche, 1)

        # --- Colonne droite : la file des cartes de tache (FR4).
        self.defilement_taches = QScrollArea(self)
        self.defilement_taches.setWidgetResizable(True)
        self.defilement_taches.setFrameShape(QFrame.Shape.NoFrame)
        self.defilement_taches.setFixedWidth(
            jetons.CARTE_DE_TACHE["largeur"])
        self.panneau_taches = _cartes.PanneauDeTaches(
            chaines, self.defilement_taches)
        self.defilement_taches.setWidget(self.panneau_taches)
        self.defilement_taches.viewport().setAutoFillBackground(False)
        self.defilement_taches.setStyleSheet("background: transparent;")
        rangee.addWidget(self.defilement_taches, 0)

        self._libelles_d_annonce: list[QLabel] = []

    # --- Mise en place -------------------------------------------------

    def poser_le_projet(self, project_dir, modele_de_file=None) -> None:
        """Dire a l'atelier sur quel projet il travaille, et sur quelle file.

        `modele_de_file` est le modele de la zone tampon : c'est lui qui porte
        les entrees, et c'est sur lui que l'atelier repose le motif d'un echec
        et le reliquat d'une passe -- pour que l'entree **reste, nommee**.

        Le projet est **transmis au modele de file** dans le meme mouvement :
        c'est ce qui lui permet de demander au coeur le nom du lot d'une
        selection (`EPIC7-ARB-88`), et c'est le seul endroit ou ce projet-la
        est connu des deux cotes a la fois.
        """
        self._project_dir = None if project_dir is None else Path(project_dir)
        self._modele_de_file = modele_de_file
        if modele_de_file is not None:
            modele_de_file.poser_le_projet(self._project_dir)

    @property
    def executeur(self):
        return self._executeur

    def annonces(self) -> tuple:
        """Les annonces de completude courantes, dans l'ordre de leur venue."""
        return self._annonces

    def textes_annonces(self) -> tuple:
        """Le texte AFFICHE de chaque annonce -- ce que l'oeil lit."""
        return tuple(libelle.text() for libelle in self._libelles_d_annonce)

    # --- Le lancement : une tache par entree cochee ---------------------

    def lancer(self, entrees) -> tuple:
        """Soumettre **une tache par entree**, et poser **une carte par tache**.

        Rien ne part sans ce clic : cette methode n'est appelee que par le
        signal `detection_demandee` de la zone tampon, lui-meme emis au seul
        clic sur `Detecter`.

        **Dedoublonnage par `scan_path` (F15, revue de vague 3)** :
        `ModeleDeZoneTampon.deposer` autorise DELIBEREMENT deux entrees du
        meme chemin (teste,
        `test_deux_depots_du_meme_chemin_restent_deux_entrees`) -- et cette
        methode ne casse pas ce comportement, les deux entrees restent deux
        entrees dans la file. Mais `scan_ingest.ingest_scan_lot` derive
        `ingest_slug` du seul chemin, DETERMINISTE : deux entrees du meme
        chemin visent donc le meme `scans/<slug>/ingest.json`. Soumettre une
        tache par entree lancerait deux appels a `run_scan_detect` sur le
        meme chemin -- un travail redondant qui ecrit deux fois le meme
        fichier, sans jamais se comparer. On ne soumet donc qu'**une seule**
        tache par chemin DISTINCT : les entrees suivantes du meme chemin
        posent leur propre carte (une carte par entree, invariant AC 2c
        inchange) mais SUIVENT le resultat de la tache deja soumise, au lieu
        d'en lancer une seconde.

        **La cle de dedoublonnage est `entree.chemins`, pas `entree.chemin`**
        (`EPIC7-ARB-88`). Depuis qu'une selection multiple est UNE entree,
        `chemin` porte soit un `Path` soit un tuple de `Path` : indexer un
        dictionnaire dessus melangerait deux types de cle, et une liste --
        forme naturelle d'une selection -- ne serait meme pas hachable, ce qui
        aurait fait exploser F15 avec un `TypeError` au premier depot
        multiple. `chemins` rend **toujours** un tuple, donc toujours
        hachable, et confond au passage l'entree a un chemin et la selection a
        un seul element : les deux visent bien le meme lot.

        **La question du remplacement se pose AVANT toute soumission**
        (`EPIC7-ARB-90`) : voir :meth:`_detections_existantes`. Un « Non »
        n'ouvre ni tache ni carte, et l'entree reste dans la file, intacte --
        « rien n'en sort tout seul » (7.3, AC 1).
        """
        taches = []
        # chemins -> tache deja soumise pour ce lot (F15/dedoublonnage).
        taches_par_chemin: dict[tuple, object] = {}
        # Les cles pour lesquelles l'operatrice a deja repondu « Non ». Un refus
        # ne laisse aucune tache derriere lui : sans ce second registre, il ne
        # laissait donc AUCUNE trace, et la boucle reposait la question a
        # chaque entree du meme fichier. Mesure du defaut : deux entrees du
        # meme chemin, reponse « Non » -- deux modales, la ou la docstring
        # ci-dessous promet « aucune seconde question ». Le « Oui », lui, en
        # laissait une (sa tache), et c'est pourquoi lui seul allait bien.
        refuses: set[tuple] = set()
        for entree in entrees:
            libelle = _modele_tampon.libelle_d_entree(entree, self._chaines)
            cle = _cle_de_lot(entree)
            if cle in refuses:
                # La question a deja ete posee pour ce lot, et tranchee par un
                # « Non ». On ne la repose pas, et cette entree reste dans la
                # file comme la premiere -- intacte, sans carte.
                continue
            tache_existante = taches_par_chemin.get(cle)
            if tache_existante is not None:
                # Doublon de chemin : aucun second appel au coeur, et **aucune
                # seconde question** -- la premiere a deja tranche pour ce
                # lot-la. La carte de CETTE entree suit le meme aboutissement
                # (terminee ou echouee, memes lot, meme reliquat, meme hors
                # perimetre) que la tache deja soumise pour ce chemin.
                carte = self.panneau_taches.ajouter(libelle)
                tache_existante.terminee.connect(
                    partial(self._sur_fin, entree, carte))
                tache_existante.echouee.connect(
                    partial(self._sur_echec, entree, carte))
                self._rattraper(entree, carte, tache_existante)
                taches.append(tache_existante)
                continue
            # `EPIC7-ARB-90` : une detection existante sur le meme fichier se
            # remplace, mais **sur confirmation explicite**. Le defaut du
            # coeur reste le refus d'ecraser.
            remplacer = bool(self._detections_existantes(entree))
            if remplacer and not self._confirmer_le_remplacement(libelle):
                refuses.add(cle)
                continue
            carte = self.panneau_taches.ajouter(libelle)
            tache = self._executeur.soumettre(
                self._detecter,
                {
                    "project_dir": self._project_dir,
                    "scan_path": entree.chemin,
                    "dpi": entree.dpi,
                    "remplacer_les_detections": remplacer,
                },
            )
            tache.terminee.connect(partial(self._sur_fin, entree, carte))
            tache.echouee.connect(partial(self._sur_echec, entree, carte))
            # **Course reelle, mesuree ici** : `Executeur.soumettre` DEMARRE la
            # tache avant de la rendre, donc elle peut atteindre son etat final
            # -- et emettre son signal -- AVANT que les deux connexions
            # ci-dessus n'existent. Le signal est alors perdu et la carte reste
            # « en cours » pour toujours, sans erreur. Symptome : la suite de
            # cet atelier echouait environ un tour sur trois, sur un test
            # different a chaque fois, par expiration d'attente. Le rattrapage
            # ci-dessous relit l'etat de la tache une fois connectee ; les deux
            # chemins sont rendus idempotents par la garde en tete de
            # `_sur_fin` et de `_sur_echec`, si bien que le premier arrive
            # gagne et que le second ne fait rien.
            self._rattraper(entree, carte, tache)
            # La cle POSEE est celle qui sera LUE au tour suivant. Ecrire
            # `entree.chemin` ici alors que la lecture porte sur
            # `entree.chemins` ne leve rien : le dictionnaire se remplit avec
            # des cles que personne ne cherche, et le dedoublonnage F15 cesse
            # simplement d'avoir lieu, en silence. Les deux lignes doivent
            # nommer le meme attribut.
            taches_par_chemin[cle] = tache
            taches.append(tache)
        return tuple(taches)

    # --- EPIC7-ARB-90 : une detection existante se remplace, sur demande ---

    def _detections_existantes(self, entree) -> tuple:
        """Les documents de detection deja ecrits pour le lot de cette entree.

        **Les deux moities sont demandees au coeur** : le dossier de lot par
        `scan_ingest.dossier_de_lot_par_defaut` -- « il n'y a qu'une facon
        correcte de le deriver : celle qu'`ingest_scan_lot` applique » --, et
        les documents par `scan_detect.documents_de_detection_existants`.
        Composer l'un ou chercher les autres ici les ferait diverger au premier
        changement du coeur, ce qui est exactement le defaut que
        `EPIC7-ARB-88` vient de payer sur le chemin d'`ingest.json`.

        C'est le DOSSIER qui est demande, pas le slug : les deux ne coincident
        pas quand l'ingestion a lieu en place, et chercher les detections sous
        `scans/<slug>/` n'en aurait alors trouve aucune -- donc aucune question
        posee, et l'ecrasement silencieux que l'arbitrage interdit.

        Rend `()` -- donc **aucune question** -- dans deux cas : aucun projet
        ouvert, et une entree que le coeur refuse de nommer. Le refus n'est pas
        rejoue ici : la passe le dira, avec son motif verbatim (P9). Poser la
        question sur une entree que l'ingestion va rejeter serait demander a
        l'operatrice d'arbitrer un ecrasement qui n'aura jamais lieu.
        """
        if self._project_dir is None:
            return ()
        try:
            lot_dir = scan_ingest.dossier_de_lot_par_defaut(
                self._project_dir, entree.chemin)
        except scan_ingest.ScanIngestError:
            return ()
        return scan_detect.documents_de_detection_existants(lot_dir)

    def _modale_de_remplacement(self, objet) -> bool:
        """Poser la question a l'operatrice ; rendre son « Oui » ou son « Non ».

        « Souhaitez-vous lancer une nouvelle detection sur ce fichier ? » --
        la formulation est celle du catalogue, verbatim de l'essai de terrain.
        Le bouton par DEFAUT est « Non » : l'ecrasement ne s'obtient jamais
        par une validation distraite, c'est tout ce qui separe `EPIC7-ARB-90`
        de l'ecrasement silencieux que 5.25 (AC 2) refuse.
        """
        chaines = self._chaines
        boite = QMessageBox(self)
        boite.setWindowTitle(chaines["zone-tampon-detection-existante-titre"])
        boite.setText(
            chaines["zone-tampon-detection-existante"].format(objet=objet))
        oui = boite.addButton(
            chaines["zone-tampon-detection-existante-oui"],
            QMessageBox.ButtonRole.YesRole)
        non = boite.addButton(
            chaines["zone-tampon-detection-existante-non"],
            QMessageBox.ButtonRole.NoRole)
        boite.setDefaultButton(non)
        boite.exec()
        return boite.clickedButton() is oui

    def _rattraper(self, entree, carte, tache) -> None:
        """Appliquer l'etat deja atteint par une tache connectee trop tard."""
        if carte.etat != _executeur.EN_COURS:
            return
        if tache.etat == _executeur.TERMINEE:
            self._sur_fin(entree, carte, tache.resultat)
        elif tache.etat == _executeur.ECHOUEE:
            self._sur_echec(entree, carte, tache.motif)

    # --- Les deux issues -----------------------------------------------

    def _sur_echec(self, entree, carte, motif) -> None:
        """Une tache a echoue : le motif du coeur, verbatim, et l'entree RESTE.

        Rien n'est retire de la file (correction A2), rien n'est range dans
        l'arbre : l'entree reste, nommee, avec le motif qui dit pourquoi.

        **Idempotent** : le signal et le rattrapage de :meth:`lancer` peuvent
        arriver tous les deux ; le premier gagne, le second ne fait rien.
        """
        if carte.etat != _executeur.EN_COURS:
            return
        carte.refleter(_executeur.ECHOUEE, motif)
        if self._modele_de_file is not None:
            self._modele_de_file.poser_le_motif(entree.identifiant, motif)
            self.file_mise_a_jour.emit()

    def _sur_fin(self, entree, carte, issue) -> None:
        """Une tache a abouti : N cartes pour N lot trouves, puis l'annonce.

        **Idempotent**, meme motif que `_sur_echec` : sans cette garde, un
        rattrapage double du signal poserait DEUX fois les cartes de lot.

        **F13 (revue de vague 3) -- le rapport de tri se lit AVANT toute
        mutation de carte.** `_lire_le_rapport_de_tri` peut lever : un
        `tri.json` illisible n'a pas le droit de passer pour un tri vide
        (voir la docstring de `chargeur_detections.charger_le_rapport_de_tri`
        -- l'exception n'est donc jamais avalee ici). Mais si elle etait lue
        APRES que les cartes ont ete marquees TERMINEE, l'exception
        traverserait ce slot Qt en laissant la fenetre a moitie mise a jour :
        cartes closes, mais ni `_annoncer` ni `detection_terminee.emit` ne
        s'executeraient. En la lisant ici, en tete, l'exception remonte
        encore -- rien n'est avale -- mais avant toute mutation : soit tout
        ce qui suit s'execute, soit rien n'a bouge.
        """
        if carte.etat != _executeur.EN_COURS:
            return
        resultat = _chargeur.charger_ces_documents(issue.documents)
        documents = resultat.documents
        rapport = self._lire_le_rapport_de_tri(issue)

        if not documents:
            # Les deux arrets non fautifs du coeur (aucune planche identifiee,
            # pile de calibration seule). La carte est TERMINEE -- la passe a
            # bien eu lieu -- et porte le motif du coeur, VERBATIM : ce code
            # n'entre pas au catalogue, il s'affiche tel quel (P9).
            carte.refleter(_executeur.TERMINEE, issue.motif_d_arret)
        else:
            self._poser_les_cartes_de_lot(entree, carte, documents)

        self._poser_le_reliquat(entree, rapport)
        self._poser_le_hors_perimetre(entree, rapport)
        if self._modele_de_file is not None:
            self.file_mise_a_jour.emit()
        self._annoncer(documents)
        self.detection_terminee.emit(issue)

    def _poser_les_cartes_de_lot(self, entree, carte, documents) -> None:
        """**Une carte par lot trouve**, la premiere reprenant celle de la tache.

        A ne pas confondre avec l'AC 2c : la, N entrees deposees donnaient N
        cartes ; ici **une** entree en donne N parce que le coeur y a trouve N
        lot. Les cartes suivantes sont posees a la file, dans l'ordre des
        documents -- c'est-a-dire celui du tri du coeur, jamais un ordre
        recalcule ici.
        """
        # Le nom de l'objet est celui du MODELE (`libelle_d_entree`), la meme
        # redaction que la ligne de la file : une selection s'y nomme par son
        # lot et son cardinal, un chemin unique par son nom de fichier. Deux
        # redactions donneraient deux noms pour une seule entree.
        libelle = _modele_tampon.libelle_d_entree(entree, self._chaines)
        identifiants = []
        for indice, document in enumerate(documents):
            identite = document.subject.lot_id
            identifiants.append(identite)
            if indice == 0:
                carte.nommer(libelle, identite)
                carte.refleter(_executeur.TERMINEE)
            else:
                suivante = self.panneau_taches.ajouter(libelle, identite)
                suivante.refleter(_executeur.TERMINEE)
        if self._modele_de_file is not None:
            self._modele_de_file.poser_les_lot_trouves(
                entree.identifiant, identifiants)

    def _lire_le_rapport_de_tri(self, issue):
        """Relire le rapport de tri de la passe, ou `None` -- AVANT toute carte.

        **F13 (revue de vague 3)** : appelee en tete de `_sur_fin`, avant
        toute mutation de carte -- voir sa docstring pour le motif complet.
        `chargeur_detections.charger_le_rapport_de_tri` **leve** deliberement
        sur un `tri.json` illisible ; cette methode ne l'attrape pas.
        """
        if self._modele_de_file is None or self._project_dir is None:
            return None
        return _chargeur.charger_le_rapport_de_tri(
            self._project_dir, issue.report.ingest_slug)

    def _poser_le_reliquat(self, entree, rapport) -> None:
        """Reporter sur l'entree ce que le tri n'a rattache a rien.

        Le rapport de tri est **lu** (`_lire_le_rapport_de_tri`), jamais
        recompose : le localisateur et le motif viennent de lui, et le motif
        appartient au vocabulaire ferme de 5.24.
        """
        if rapport is None or self._modele_de_file is None:
            return
        self._modele_de_file.poser_le_reliquat(
            entree.identifiant,
            [(_texte_de_localisateur(reste.locator), reste.motif)
             for reste in rapport.partition.reliquat],
        )

    def _poser_le_hors_perimetre(self, entree, rapport) -> None:
        """Reporter sur l'entree ce que le tri a range HORS PERIMETRE (F14).

        `partition.hors_perimetre` (`scan_sorting.EntreeHorsPerimetre`) est
        une classe DISJOINTE du reliquat dans la partition de 5.24 -- une
        page qui appartient a un autre projet, avec le projet a utiliser
        (`EPIC5-ARB-105` : « l'operateur ne doit pas avoir a le deviner »).
        Avant ce correctif, aucun module de `gui/` ne lisait cette classe :
        une pile ou toutes les pages identifiees finissaient hors perimetre
        rendait une carte TERMINEE muette et un reliquat vide, indistinguable
        d'un vrac ou rien d'anormal n'a ete trouve.

        Le localisateur, le motif et `projet_a_utiliser` viennent du rapport,
        **jamais recomposes ici** -- meme regle que `_poser_le_reliquat`.
        """
        if rapport is None or self._modele_de_file is None:
            return
        self._modele_de_file.poser_le_hors_perimetre(
            entree.identifiant,
            [(_texte_de_localisateur(dehors.locator), dehors.motif,
              dehors.projet_a_utiliser)
             for dehors in rapport.partition.hors_perimetre],
        )

    # --- L'annonce, AVANT toute ecriture --------------------------------

    def _annoncer(self, documents) -> None:
        """Annoncer, **par lot**, quelles planches manquent.

        La valeur vient de `modele_chutier._completude_du_document` et de rien
        d'autre. Les documents d'un meme lot sont regroupes -- plusieurs scans
        d'une meme planche s'additionnent, c'est le contrat de 5.25 (AC 4) --,
        et l'ordre reste celui de leur venue.
        """
        index: dict[str, list] = {}
        ordre: list[str] = []
        for document in documents:
            identite = document.subject.lot_id
            if identite not in index:
                index[identite] = []
                ordre.append(identite)
            index[identite].append(document)

        annonces = []
        for identite in ordre:
            badge, manquantes = _modele._completude_du_document(index[identite])
            if badge is None:
                continue
            annonces.append(Annonce(
                lot=identite, badge=badge, planches_manquantes=manquantes))
        if not annonces:
            return
        self._annonces = tuple(annonces)
        self._rendre_les_annonces()
        # **Contrat C (V3.a)** : l'annonce part AVANT toute ecriture de frame.
        # Le banc compte reellement `frames-scannees/` a la reception de ce
        # signal -- un drapeau ne prouverait rien.
        self.completude_annoncee.emit(self._annonces)

    def _rendre_les_annonces(self) -> None:
        for libelle in self._libelles_d_annonce:
            self.pile_annonces.removeWidget(libelle)
            libelle.setParent(None)
            libelle.deleteLater()
        self._libelles_d_annonce = []

        chaines = self._chaines
        for annonce in self._annonces:
            # Le libelle du badge est celui du chutier (`badge-<etat>`) : une
            # seule redaction pour l'arbre et pour l'annonce, donc elles ne
            # peuvent pas se contredire.
            texte = chaines["atelier-scan-completude"].format(
                lot=annonce.lot, badge=chaines[f"badge-{annonce.badge}"])
            if annonce.planches_manquantes:
                separateur = chaines["atelier-scan-separateur"]
                planches = separateur.join(
                    str(index) for index in annonce.planches_manquantes)
                texte += separateur + chaines[
                    "atelier-scan-planches-manquantes"].format(planches=planches)
            else:
                texte += chaines["atelier-scan-separateur"] + chaines[
                    "atelier-scan-aucune-planche-manquante"]
            libelle = QLabel(texte, self._hote_annonces)
            libelle.setWordWrap(True)
            self.pile_annonces.addWidget(libelle)
            self._libelles_d_annonce.append(libelle)
        self.libelle_sans_annonce.setVisible(not self._annonces)

    # --- Le contrat C, mesurable de l'exterieur -------------------------

    def cardinal_des_frames_ecrites(self) -> int:
        """Le nombre de frames scannees presentes dans le projet.

        Comptage REEL du dossier, jamais un drapeau : c'est exactement ce que
        l'AC 2e exige au moment de l'annonce, et un booleen tenu a jour par le
        code teste serait tenu par le code qu'il pretend mesurer.

        **Les DEUX racines sont comptees** (story 11.14, `EPIC11-ARB-222`).
        Un projet deja sur disque porte ses frames scannees sous la racine
        d'avant (`project_layout.LEGACY_OUTPUT_FRAMES_DIRNAME`), un projet neuf
        sous `SCAN_FRAMES_DIRNAME`, et aucun des deux n'est converti. N'en
        compter qu'une rendrait ce cardinal systematiquement nul sur les projets
        d'avant -- c'est-a-dire un contrat C qui annonce « aucune frame ecrite »
        alors que le scan vient d'en ecrire.

        Les racines sont celles de `io/project_layout`, jamais recomposees ici :
        c'est le module qui possede la regle de cohabitation, et son resolveur
        ne rend l'ancienne que si elle existe reellement -- donc aucun double
        comptage. Le nom d'avant lui-meme n'est pas ecrit ici, il est NOMME par
        sa constante : il n'a qu'un proprietaire, et une frontiere negative le
        mesure.
        """
        if self._project_dir is None:
            return 0
        return sum(
            1
            for racine in project_layout.racines_de_frames_scannees(
                self._project_dir)
            if racine.is_dir()
            for chemin in racine.rglob("*")
            if chemin.is_file()
        )


def _texte_de_localisateur(localisateur) -> str:
    """Nommer une page par son localisateur : chemin, et index s'il en a un.

    Le meme couple que le rapport d'ingestion de 5.1 -- « exactement
    l'identifiant dont le reliquat a besoin pour nommer une page qui n'existe
    comme fichier nulle part ».
    """
    if localisateur.page_index is None:
        return str(localisateur.source_path)
    return f"{localisateur.source_path}#{localisateur.page_index}"
