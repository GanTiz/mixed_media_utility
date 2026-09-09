# -*- coding: utf-8 -*-
"""Point d'entree de la GUI : ``python -m mixed_media_utility.gui``.

Decision de la fiche 7.0 : la seule forme de lancement qui n'exige ni
table ``[project]`` dans ``pyproject.toml`` ni script ``bin/`` neuf ; un
lanceur ``bin/mmu-gui`` releve du packaging (Epic 8). Aucun module
existant du depot ne bouge -- la CLI (``bin/mmu`` + ``cli.py``) reste le
livrable maintenu qu'elle est (FR2, ``EPIC7-ARB-46``).
"""

import logging
import sys

from PySide6.QtWidgets import QApplication

from .application import LancementApplication
from .coquille import Coquille
from .feuille_application import feuille_application

logger = logging.getLogger(__name__)


def construire_application(arguments=None):
    """Construire (sans executer) l'application et sa coquille.

    Separee de :func:`principal` pour le banc headless : le test importe
    ce module et construit la fenetre offscreen sans boucle d'evenements.
    Reutilise le singleton ``QApplication`` s'il existe deja (pytest-qt en
    possede un) -- on n'en instancie jamais un second.

    Quand le singleton existe deja, ``arguments`` ne peut plus servir : Qt a
    lu ses arguments a la construction ORIGINALE de ce singleton, bien avant
    cet appel. Un ``arguments`` fourni ici est donc SANS EFFET -- avant ce
    correctif (revue de vague 1), c'etait silencieux, la meme classe de
    defaut que ce module refuse par ailleurs (« reste inerte »). On le rend
    explicite par un avertissement journalise plutot qu'un refus qui
    romprait le banc de test (qui appelle systematiquement cette fonction
    avec un ``QApplication`` de pytest-qt deja en place).
    """
    return _application_qt(arguments), Coquille()


def _application_qt(arguments=None):
    """Le singleton ``QApplication``, cree une seule fois.

    Extrait de ``construire_application`` par la story 7.1 pour que
    l'enchainement de lancement puisse obtenir l'application SANS
    construire au passage une coquille dont il n'a que faire (la sienne
    naitra a l'ouverture d'un projet).
    """
    application = QApplication.instance()
    if application is None:
        application = QApplication(arguments if arguments is not None else sys.argv)
    elif arguments:
        logger.warning(
            "construire_application(arguments=%r) ignore : une QApplication "
            "existe deja (singleton reutilise), ses arguments sont figes "
            "depuis sa construction originale.",
            arguments,
        )
    # **La feuille de style d'APPLICATION** (2026-08-26). Elle est posee ici et
    # pas dans un ecran parce que c'est le seul endroit qui voit tous les
    # widgets : jusqu'a cette date, tout widget qu'aucun ecran ne visait
    # retombait sur le style natif de la plateforme -- deux bandes blanches
    # verticales en plein milieu de la coquille (les poignees de `QSplitter`),
    # les cases a cocher, les barres de defilement et les infobulles du
    # systeme. Mesure et detail dans `feuille_application.py`.
    #
    # Posee a CHAQUE appel, et non seulement quand on cree le singleton : le
    # banc reutilise la `QApplication` de pytest-qt, construite avant nous, sur
    # laquelle personne n'aurait jamais pose la feuille -- les captures et les
    # tests peindraient alors autre chose que le produit.
    application.setStyleSheet(feuille_application())
    return application


def construire_lancement(arguments=None):
    """Construire (sans executer) l'application et son enchainement de lancement.

    Story 7.1 : la PREMIERE surface du produit est l'ecran de gestion de
    projet, pas la coquille -- « on rentre par le projet, jamais par un
    atelier ». ``construire_application`` reste ce qu'elle etait (la
    coquille du socle, seule, telle que la story 7.0 la contracte) et
    garde ses appelants ; c'est cette fonction-ci qui porte l'enchainement.
    """
    return _application_qt(arguments), LancementApplication()


def principal(arguments=None):
    """Creer l'application, montrer l'ecran de projet, entrer dans la boucle.

    L'ecran de gestion s'affiche a CHAQUE lancement (AC 3 de la story 7.1) :
    il n'y a aucune reprise implicite dans le dernier atelier ouvert, et
    aucune ouverture automatique meme quand un seul projet est connu.
    """
    application, lancement = construire_lancement(arguments)
    lancement.demarrer()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(principal())
