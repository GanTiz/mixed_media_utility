# -*- coding: utf-8 -*-
"""Modele de la liste de l'ecran de gestion de projet (story 7.1, AC 2/AC 3).

**Ce module ne sait RIEN du contenu d'un projet.** Il porte, par ligne, le
nom du dossier, son chemin, ses deux dates et -- quand le projet est
illisible -- le motif verbatim leve par le coeur. Rien d'autre : aucun etat
de contenu, aucun compteur, aucun badge de deduction (`EPIC7-ARB-27`,
`EPIC7-ARB-14` : ce qu'un projet contient se decouvre en l'ouvrant).

Cette ignorance est **mesuree** par un grep de frontiere sur ce fichier
(`tests/unit/gui/test_frontieres_ecran_projet.py`) : les trois mots du
vocabulaire de contenu n'y apparaissent nulle part, commentaires compris.
C'est ce qui rend la regle tenable dans le temps -- et c'est aussi pourquoi
les motifs d'erreur sont **lus** des exceptions du coeur et jamais recopies
en litteraux ici.

Aucun import Qt : le modele est du Python pur, donc mesurable sans banc
graphique. La surface (`ecran_projet.py`) le consomme, il ne la connait pas.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

#: Les trois cles de tri offertes par la surface (AC 2). L'ordre de ce
#: tuple est l'ordre d'apparition dans le selecteur.
CLES_DE_TRI = ("nom", "creation", "modification")

#: Rangs de tete, dans l'ordre : les projets EPINGLES precedent le dernier
#: projet ouvert, qui precede tout le reste.
#:
#: Les deux exigences -- « dernier projet en tete » (`EXPERIENCE.md`) et « un
#: projet epingle resiste au tri par date et reste en tete »
#: (`EPIC7-ARB-37`) -- disent toutes deux « en tete » et **aucune source ne
#: tranchait laquelle prime**. La revue de vague 2 a instruit les quatre
#: sources (spine, DESIGN.md, ARB-37, epics.md) sans en trouver une seule
#: qui le dise. Arbitrage rendu par Egan le 2026-08-25 (`EPIC7-ARB-61`) :
#: **l'epingle passe devant**, parce qu'epingler est un geste DELIBERE de
#: l'operatrice tandis que « dernier ouvert » est un effet de bord de son
#: travail -- un choix explicite prime sur un automatisme. Le dernier ouvert
#: garde son lisere et reste donc immediatement reperable.
#:
#: Un projet a la fois epingle et dernier ouvert prend le rang le plus fort.
_RANG_EPINGLE = 0
_RANG_DERNIER_OUVERT = 1
_RANG_ORDINAIRE = 2


@dataclass(frozen=True)
class LigneProjet:
    """Une ligne de la liste : ce qui s'affiche, et rien de plus.

    * ``nom`` -- nom du dossier de travail ;
    * ``chemin`` -- son chemin sur le disque ;
    * ``date_creation`` -- horodatage RFC3339 **lu** du fichier de projet
      quand il y en a un, ``None`` sinon : jamais deduit d'autre chose
      (decision d'ecriture 2 de la fiche -- un troisieme porteur de la meme
      verite est une occasion de divergence) ;
    * ``date_modification`` -- date de derniere ecriture du fichier de
      projet, donnee du systeme de fichiers (secondes epoch) ;
    * ``motif`` -- ``None`` quand le projet se lit ; sinon le message de
      l'exception levee par le coeur, **verbatim** ;
    * ``epingle`` -- pose par le modele depuis les preferences, jamais lu
      du disque du projet.
    """

    nom: str
    chemin: Path
    date_creation: str | None = None
    date_modification: float | None = None
    motif: str | None = None
    epingle: bool = False

    @property
    def ouvrable(self) -> bool:
        """Vrai tant qu'aucun motif d'echec n'est porte par la ligne.

        Une ligne qui porte un motif reste **listee** (la faire disparaitre
        ferait d'un message fugace le seul porteur d'un echec) mais ne
        s'ouvre pas.
        """
        return self.motif is None


def _repere(chemin) -> str:
    """Cle d'identite d'une ligne : son chemin, sous forme normalisee.

    Deux designations differentes du meme dossier (chemin relatif, lien,
    barre finale) doivent designer la meme ligne, sans quoi un import
    creerait un doublon de ce qui est deja liste.
    """
    return str(Path(chemin).expanduser().resolve())


class ModeleProjets:
    """La liste : ordre, recherche, epingles, dernier ouvert.

    Le modele **ne lit pas le disque** : il recoit des ``LigneProjet``
    deja construites (par ``depot_projets``) et se contente de les
    ordonner et de les filtrer.
    """

    def __init__(self, lignes=(), *, epingles=(), dernier_ouvert=None):
        self._lignes: list[LigneProjet] = []
        self._epingles: set[str] = {_repere(c) for c in epingles}
        self._dernier_ouvert: str | None = (
            _repere(dernier_ouvert) if dernier_ouvert is not None else None
        )
        self._cle_de_tri = CLES_DE_TRI[0]
        self._croissant = True
        self._recherche = ""
        self.remplacer(lignes)

    # --- alimentation ---------------------------------------------------

    def remplacer(self, lignes) -> None:
        """Poser l'ensemble des lignes, en reappliquant l'etat d'epingle."""
        self._lignes = [self._avec_epingle(ligne) for ligne in lignes]

    def ajouter(self, ligne: LigneProjet) -> LigneProjet:
        """Ajouter une ligne, ou remplacer celle qui porte le meme chemin.

        Remplacer plutot qu'empiler : designer deux fois le meme dossier
        (par « ouvrir » puis par « importer ») ne fabrique jamais un
        doublon.
        """
        pose = self._avec_epingle(ligne)
        repere = _repere(pose.chemin)
        for indice, existante in enumerate(self._lignes):
            if _repere(existante.chemin) == repere:
                self._lignes[indice] = pose
                return pose
        self._lignes.append(pose)
        return pose

    def retirer(self, chemin) -> bool:
        """Retirer une ligne de la liste connue. Rend vrai si elle y etait.

        **Rien n'est touche sur le disque** : ce modele ne l'ecrit jamais, et
        ce geste-ci n'en fait pas exception. Il retire une ligne des
        preferences de l'utilisatrice, c'est tout -- redesigner le meme
        dossier la fait revenir a l'identique.

        Les trois etats qui portent ce chemin partent ensemble : la ligne, son
        epingle et son rang de « dernier ouvert ». En laisser un derriere
        ferait revenir le projet en tete de liste au prochain import, ou pire
        le ferait resister au tri sans qu'aucune epingle ne se voie nulle
        part.
        """
        repere = _repere(chemin)
        avant = len(self._lignes)
        self._lignes = [
            ligne for ligne in self._lignes if _repere(ligne.chemin) != repere
        ]
        self._epingles.discard(repere)
        if self._dernier_ouvert == repere:
            self._dernier_ouvert = None
        return len(self._lignes) != avant

    def _avec_epingle(self, ligne: LigneProjet) -> LigneProjet:
        return replace(ligne, epingle=_repere(ligne.chemin) in self._epingles)

    # --- tri et recherche -----------------------------------------------

    @property
    def cle_de_tri(self) -> str:
        return self._cle_de_tri

    def definir_tri(self, cle: str, *, croissant: bool = True) -> None:
        """Choisir la cle de tri parmi ``CLES_DE_TRI``."""
        if cle not in CLES_DE_TRI:
            raise ValueError(
                f"Cle de tri inconnue : {cle!r}. Attendu : {', '.join(CLES_DE_TRI)}"
            )
        self._cle_de_tri = cle
        self._croissant = bool(croissant)

    @property
    def recherche(self) -> str:
        return self._recherche

    def definir_recherche(self, terme: str | None) -> None:
        """Filtrer sur le nom ET le chemin, sans egard a la casse."""
        self._recherche = (terme or "").strip()

    # --- epingle et dernier ouvert ---------------------------------------

    def epingles(self) -> tuple[str, ...]:
        """Les chemins epingles, ordonnes -- forme persistable telle quelle."""
        return tuple(sorted(self._epingles))

    def est_epingle(self, chemin) -> bool:
        return _repere(chemin) in self._epingles

    def basculer_epingle(self, chemin) -> bool:
        """Epingler ou desepingler ; rend l'etat obtenu."""
        repere = _repere(chemin)
        if repere in self._epingles:
            self._epingles.discard(repere)
        else:
            self._epingles.add(repere)
        self._lignes = [self._avec_epingle(ligne) for ligne in self._lignes]
        return repere in self._epingles

    @property
    def dernier_ouvert(self) -> str | None:
        return self._dernier_ouvert

    def definir_dernier_ouvert(self, chemin) -> None:
        self._dernier_ouvert = _repere(chemin) if chemin is not None else None

    def est_dernier_ouvert(self, chemin) -> bool:
        """Vrai pour la ligne qui porte le lisere de « dernier ouvert »."""
        return (
            self._dernier_ouvert is not None
            and _repere(chemin) == self._dernier_ouvert
        )

    # --- restitution ------------------------------------------------------

    def _rang_de_tete(self, ligne: LigneProjet) -> int:
        # L'ordre des deux tests EST l'arbitrage `EPIC7-ARB-61` : l'epingle
        # est lue en premier, donc un projet epingle passe devant le dernier
        # ouvert. Inverser ces deux lignes inverse la decision.
        if ligne.epingle:
            return _RANG_EPINGLE
        if self.est_dernier_ouvert(ligne.chemin):
            return _RANG_DERNIER_OUVERT
        return _RANG_ORDINAIRE

    def _valeur_de_tri(self, ligne: LigneProjet):
        if self._cle_de_tri == "nom":
            return ligne.nom.casefold()
        if self._cle_de_tri == "creation":
            return ligne.date_creation
        return ligne.date_modification

    def _correspond(self, ligne: LigneProjet) -> bool:
        if not self._recherche:
            return True
        terme = self._recherche.casefold()
        return terme in ligne.nom.casefold() or terme in str(ligne.chemin).casefold()

    def lignes(self) -> tuple[LigneProjet, ...]:
        """Les lignes filtrees puis ordonnees, telles que la surface les peint.

        Ordre, dans cet ordre exact :

        1. la valeur de tri courante, ascendante ou descendante ; une ligne
           dont la valeur manque (une date jamais ecrite, ou un projet
           illisible qui n'a pu en fournir aucune) va **en fin**, quel que
           soit le sens -- une valeur manquante n'est ni petite ni grande,
           et la faire basculer d'un bout a l'autre au changement de sens
           donnerait a l'absence de donnee le poids d'une donnee ;
        2. par-dessus, le rang de tete (epingles, puis dernier ouvert,
           `EPIC7-ARB-61`) --
           applique en **second** et par un tri stable, donc il deplace
           les lignes de tete sans jamais melanger l'ordre des autres.
        """
        retenues = [ligne for ligne in self._lignes if self._correspond(ligne)]

        renseignees = [l for l in retenues if self._valeur_de_tri(l) is not None]
        muettes = [l for l in retenues if self._valeur_de_tri(l) is None]
        renseignees.sort(key=self._valeur_de_tri, reverse=not self._croissant)
        muettes.sort(key=lambda ligne: ligne.nom.casefold())

        ordonnees = renseignees + muettes
        ordonnees.sort(key=self._rang_de_tete)
        return tuple(ordonnees)

    def chemins(self) -> tuple[str, ...]:
        """Les chemins de TOUTES les lignes connues, ordre d'ajout preserve.

        C'est la forme que les preferences persistent : la liste connue
        suit l'utilisateur, elle ne suit ni le tri ni la recherche du
        moment.
        """
        return tuple(str(ligne.chemin) for ligne in self._lignes)
