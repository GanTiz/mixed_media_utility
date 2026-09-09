# -*- coding: utf-8 -*-
"""Enchainement de lancement : l'ecran de projet, puis la coquille (7.1, AC 3).

« L'ecran de gestion de projet ouvre chaque session, dernier projet en
tete. Il n'y a pas de reprise implicite dans le dernier atelier ouvert : on
rentre par le projet. » (`EXPERIENCE.md`, Reprise du travail apres
interruption.) Ce module est litteralement cette phrase :

* au demarrage, l'ecran de gestion s'affiche -- **toujours**, meme quand un
  seul projet est connu, meme quand aucun ne l'est. Aucun saut direct dans
  un atelier, aucune ouverture automatique ;
* ouvrir un projet ferme l'ecran et donne la main a la coquille du socle
  (story 7.0), avec ce projet pour contexte ;
* **un seul projet ouvert a la fois** (`EXPERIENCE.md`, Foundation) :
  ouvrir un second remplace le premier, il ne s'y ajoute pas ;
* **le retour a l'accueil ne ferme rien** (`EPIC7-ARB-92`, 2026-08-27).
  Egan, second essai de terrain : « Pas de bouton pour retourner a l'ecran
  de projets et pouvoir en changer. Oblige de relancer l'interface a chaque
  fois. » Le bouton vit dans l'en-tete de la coquille ; c'est ici qu'il est
  cable, parce que la coquille ne sait pas ce qu'est l'ecran des projets.
  Revenir masque la coquille, jamais ne la detruit : le projet reste ouvert,
  et **le rouvrir depuis la liste ne relit pas le disque pour rien** -- la
  meme coquille reparait, avec l'atelier, la portee et la planche jugee ou
  l'operatrice les avait laisses ;
* **les deux surfaces s'ouvrent MAXIMISEES** (`EPIC7-ARB-93`). La coquille
  s'ouvrait a son plancher, donc systematiquement dans son pire regime.

Le contexte de projet vit ici, et le seul effet visible sur la coquille est
son titre de fenetre, pose par une chaine du catalogue.
"""

from __future__ import annotations

from PySide6.QtCore import QObject

from . import catalogue as _catalogue
from .coquille import Coquille
from .ecran_projet import EcranProjet


class LancementApplication(QObject):
    """Porte l'ecran de gestion, la coquille courante, et le projet ouvert.

    ``fabrique_de_coquille`` est injectable pour le banc : le defaut
    construit la vraie ``Coquille`` du socle.
    """

    def __init__(self, *, ecran=None, fabrique_de_coquille=None, chaines=None, parent=None):
        super().__init__(parent)
        self._chaines = dict(_catalogue.CHAINES if chaines is None else chaines)
        self.ecran = ecran if ecran is not None else EcranProjet(chaines=self._chaines)
        self._fabrique = fabrique_de_coquille or (lambda: Coquille(chaines=self._chaines))
        self.coquille = None
        self.projet_ouvert = None
        self.ecran.projet_ouvert.connect(self._sur_ouverture)

    def demarrer(self):
        """Afficher l'ecran de gestion, maximise. Rien d'autre ne s'ouvre."""
        self.ecran.showMaximized()
        return self.ecran

    def revenir_a_l_accueil(self):
        """Le bouton d'accueil : remontrer la liste, ne RIEN fermer.

        `EPIC7-ARB-92`. La coquille est masquee, pas detruite : son projet
        reste ouvert, son atelier courant, sa portee de chutier et sa
        surface de jugement sont intacts. Rouvrir le meme projet depuis la
        liste retombe donc dessus sans relire le disque (voir
        `_sur_ouverture`).
        """
        if self.coquille is not None:
            self.coquille.hide()
        self.ecran.showMaximized()
        self.ecran.raise_()
        return self.ecran

    def _sur_ouverture(self, ligne):
        """Fermer l'ecran, poser le contexte, montrer la coquille."""
        # Rouvrir le projet DEJA ouvert, depuis l'accueil : on remontre la
        # coquille telle quelle. Reconstruire ici detruirait l'etat que le
        # bouton d'accueil vient explicitement de preserver, et relirait le
        # disque « pour rien » (`EPIC7-ARB-92`).
        if (
            self.coquille is not None
            and self.projet_ouvert is not None
            and ligne.chemin == self.projet_ouvert.chemin
        ):
            self.ecran.hide()
            self.coquille.showMaximized()
            self.coquille.raise_()
            return self.coquille

        if self.coquille is not None:
            # Un seul projet a la fois : la coquille precedente s'en va,
            # elle ne cohabite pas avec la nouvelle.
            self.coquille.close()
            self.coquille.deleteLater()
            self.coquille = None

        self.projet_ouvert = ligne
        self.ecran.hide()
        coquille = self._fabrique()
        coquille.setWindowTitle(
            self._chaines["fenetre-titre-projet"].format(projet=ligne.nom)
        )
        # **La couture entre les deux stories, et elle manquait** (correctif du
        # 2026-08-26, `sprint-change-proposal-2026-08-26.md`). Sans cet appel la
        # coquille s'ouvre avec `_project_dir` a `None` : l'arbre reste vide sur
        # TOUS les projets, et le premier clic sur « Detecter » passe `None` a
        # `run_scan_detect`, qui leve « argument should be a str or an
        # os.PathLike object [...] not NoneType » sur son `Path(project_dir)`.
        # Les deux cotes de la couture etaient corrects et testes isolement ;
        # c'est la jonction qui ne l'etait pas.
        #
        # AVANT `show()` : la coquille s'affiche deja peuplee, plutot que de
        # passer par un etat vide visible le temps de la lecture du disque.
        # Le bouton d'accueil de l'en-tete (`EPIC7-ARB-92`) : cable AVANT
        # l'affichage, sinon un clic tres tot resterait sans effet.
        coquille.accueil_demande.connect(self.revenir_a_l_accueil)
        coquille.ouvrir_projet(ligne.chemin)
        # MAXIMISEE (`EPIC7-ARB-93`) : la coquille ne s'ouvre plus a son
        # plancher, sous le seuil de repli de l'arborescence.
        coquille.montrer_en_grand()
        self.coquille = coquille
        return coquille
