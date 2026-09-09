# -*- coding: utf-8 -*-
"""Cartes de tache : la surface visible de l'executeur (story 7.3, AC 3).

`gui/executeur.py` (7.0) existe depuis le socle et sa docstring le dit :
« les cartes visibles sont la story 7.3 ». Les voici.

**Deux etats honnetes, et rien de plus** (FR4, v1) : *en cours*, puis
*terminee* ou *echouee avec son motif*. Les trois libelles se lisent au
catalogue (`etat-tache-en-cours`, `-terminee`, `-echouee`).

**Le motif d'echec est LU du coeur, jamais recopie** (P9).
`executeur._Execution.run()` fournit deja `str(exc)` : ce module le pose tel
quel dans une etiquette, sans prefixe, sans traduction, sans reformulation.
Un code du coeur n'entre jamais au catalogue.

**Aucune jauge, aucun chiffre de duree.** Ce n'est plus un differe de
faisabilite depuis `EPIC7-ARB-67` -- Egan a tranche que la duree se calcule et
qu'elle sera affichee --, c'est un interdit de **mesure** : « aucun temps
n'est affiche avant qu'une mesure reelle existe ». Sur le chemin `scan
detect`, aucune fonction du coeur n'emet de cadence par page ; la story de
coeur 5.28 emet sur les taches d'**extraction**, pas ici, et c'est 7.6 qui
consommera ce canal. Une jauge non alimentee est un mensonge, et un compte a
rebours tire d'une cadence supposee en est un autre.
"""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from . import catalogue as _catalogue
from . import executeur as _executeur
from . import jetons

#: La cle de catalogue du libelle d'etat, par etat de l'executeur. Une table
#: plutot qu'un `if` : le vocabulaire d'etats est celui de `executeur`, et un
#: etat neuf doit lever ici plutot que s'afficher vide.
CLE_D_ETAT = {
    _executeur.EN_COURS: "etat-tache-en-cours",
    _executeur.TERMINEE: "etat-tache-terminee",
    _executeur.ECHOUEE: "etat-tache-echouee",
}

#: La bordure de la carte, par etat. La spine ne decrit que l'etat terminee
#: (« bordure et barre en `state-complete` ») ; l'echec prend la seule
#: semantique qui dit « il n'y a rien ici », et jamais l'accent -- une
#: activite n'est pas un verdict.
JETON_DE_BORDURE = {
    _executeur.EN_COURS: "bordure",
    _executeur.TERMINEE: "bordure-terminee",
    _executeur.ECHOUEE: "bordure-echouee",
}


def _feuille_de_la_carte(etat):
    """La feuille de style d'une carte, composee des seuls jetons de la spine."""
    c = jetons.CARTE_DE_TACHE
    n = jetons.NEUTRES
    return (
        f"QFrame#carte-de-tache {{"
        f" background: {c['fond']};"
        f" border: 1px solid {c[JETON_DE_BORDURE[etat]]};"
        f" border-radius: {c['rayon']}px; }}"
        f" QFrame#carte-de-tache QLabel {{ color: {n['text-primary']}; }}"
    )


class CarteDeTache(QFrame):
    """Une tache de fond, visible : son objet, son etat, et son motif s'il echoue."""

    def __init__(self, objet, chaines=None, parent=None):
        super().__init__(parent)
        self._chaines = dict(_catalogue.CHAINES if chaines is None else chaines)
        self._etat = _executeur.EN_COURS
        self.setObjectName("carte-de-tache")
        e = jetons.ESPACEMENTS

        colonne = QVBoxLayout(self)
        colonne.setContentsMargins(e["4"], e["3"], e["4"], e["3"])
        colonne.setSpacing(e["1"])

        # L'objet : ce sur quoi la tache travaille. C'est une donnee de
        # l'operateur (un nom d'entree, un identifiant de lot du coeur), pas
        # un libelle de catalogue -- la phrase qui l'encadre, elle, en vient.
        self.libelle_objet = QLabel(self)
        self.libelle_objet.setWordWrap(True)
        self.libelle_objet.setStyleSheet(
            f"color: {jetons.CARTE_DE_TACHE['titre']};")
        colonne.addWidget(self.libelle_objet)

        self.libelle_etat = QLabel(self)
        self.libelle_etat.setWordWrap(True)
        colonne.addWidget(self.libelle_etat)

        # Le motif : VIDE tant que rien n'a echoue. Quand il vient, c'est
        # `str(exc)` du coeur, octet pour octet.
        self.libelle_motif = QLabel(self)
        self.libelle_motif.setWordWrap(True)
        self.libelle_motif.setVisible(False)
        self.libelle_motif.setStyleSheet(
            f"color: {jetons.CARTE_DE_TACHE['texte-echec']};")
        colonne.addWidget(self.libelle_motif)

        self.nommer(objet)
        self._appliquer()

    # --- Lecture -------------------------------------------------------

    @property
    def etat(self) -> str:
        """L'etat courant, dans le vocabulaire de `executeur`."""
        return self._etat

    def texte_de_l_objet(self) -> str:
        return self.libelle_objet.text()

    def texte_de_l_etat(self) -> str:
        return self.libelle_etat.text()

    def texte_du_motif(self) -> str:
        """Le motif affiche -- `str(exc)` du coeur, sans prefixe."""
        return self.libelle_motif.text()

    # --- Transitions ---------------------------------------------------

    def nommer(self, objet, lot=None) -> None:
        """Nommer l'objet de la carte, et le lot que le coeur y a trouve.

        Sans `lot`, la carte nomme l'entree deposee -- c'est ce qu'elle sait
        au moment ou la tache part. Avec, elle nomme l'entree ET le lot :
        c'est ce que le coeur a trouve, et une entree peut en donner
        plusieurs (AC 8a).
        """
        if lot is None:
            self.libelle_objet.setText(
                self._chaines["carte-objet"].format(objet=objet))
        else:
            self.libelle_objet.setText(
                self._chaines["carte-objet-lot"].format(objet=objet, lot=lot))

    def refleter(self, etat, motif=None) -> None:
        """Porter un etat de l'executeur sur la carte, et son motif s'il y en a."""
        if etat not in CLE_D_ETAT:
            raise ValueError(
                f"etat de tache inconnu {etat!r}, attendu l'un de "
                f"{tuple(CLE_D_ETAT)}")
        self._etat = etat
        self.libelle_motif.setText("" if motif is None else str(motif))
        self.libelle_motif.setVisible(motif is not None)
        self._appliquer()

    def refleter_la_tache(self, tache) -> None:
        """Porter l'etat courant d'une :class:`executeur.Tache`."""
        self.refleter(tache.etat, tache.motif)

    def _appliquer(self):
        self.libelle_etat.setText(self._chaines[CLE_D_ETAT[self._etat]])
        self.setStyleSheet(_feuille_de_la_carte(self._etat))


class PanneauDeTaches(QFrame):
    """La file des cartes : une carte par tache, dans l'ordre de soumission."""

    def __init__(self, chaines=None, parent=None):
        super().__init__(parent)
        self._chaines = dict(_catalogue.CHAINES if chaines is None else chaines)
        self._cartes: list[CarteDeTache] = []
        self.setObjectName("panneau-de-taches")
        e = jetons.ESPACEMENTS
        self.setMaximumWidth(jetons.CARTE_DE_TACHE["largeur"])

        colonne = QVBoxLayout(self)
        colonne.setContentsMargins(
            e["panel-pad"], e["panel-pad"], e["panel-pad"], e["panel-pad"])
        colonne.setSpacing(e["3"])

        self.titre = QLabel(self._chaines["panneau-taches-titre"], self)
        self.titre.setWordWrap(True)
        colonne.addWidget(self.titre)

        self.libelle_vide = QLabel(self._chaines["panneau-taches-vide"], self)
        self.libelle_vide.setWordWrap(True)
        colonne.addWidget(self.libelle_vide)

        self._hote = QWidget(self)
        self.pile = QVBoxLayout(self._hote)
        self.pile.setContentsMargins(0, 0, 0, 0)
        self.pile.setSpacing(e["3"])
        colonne.addWidget(self._hote)
        colonne.addStretch(1)

    def ajouter(self, objet, lot=None) -> CarteDeTache:
        """Poser une carte neuve, *en cours*, et la rendre."""
        carte = CarteDeTache(objet, self._chaines, self._hote)
        if lot is not None:
            carte.nommer(objet, lot)
        # **L'element entre dans la vue AVANT d'etre garni** : l'inverse ne
        # pose rien et ne leve rien -- defaut reel de la vague 2.
        self.pile.addWidget(carte)
        self._cartes.append(carte)
        self.libelle_vide.setVisible(False)
        return carte

    def cartes(self) -> tuple:
        """Les cartes, dans l'ordre de soumission."""
        return tuple(self._cartes)

    def vider(self) -> None:
        """Retirer toutes les cartes (changement de projet)."""
        for carte in self._cartes:
            self.pile.removeWidget(carte)
            carte.setParent(None)
            carte.deleteLater()
        self._cartes = []
        self.libelle_vide.setVisible(True)
