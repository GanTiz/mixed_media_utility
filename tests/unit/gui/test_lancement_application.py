# -*- coding: utf-8 -*-
"""L'enchainement de lancement : ecran de projet puis coquille (7.1, AC 3).

Trois exigences, mesurees ici et nulle part ailleurs :

* l'ecran de gestion s'affiche a CHAQUE lancement -- aucune reprise
  implicite dans le dernier atelier ouvert, aucune ouverture automatique
  meme quand un seul projet est connu ;
* ouvrir un projet ferme l'ecran et donne la main a la coquille du socle,
  avec ce projet pour contexte ;
* **un seul projet ouvert a la fois** : ouvrir un second remplace le
  premier, il ne s'y ajoute pas.

La coquille est remplacee par une doublure dans la plupart des tests --
non pour eviter la vraie (un test la construit pour de bon), mais pour que
l'echec d'un de ces tests designe l'enchainement et non le socle.
"""

from __future__ import annotations

import json

import pytest
from PySide6.QtCore import QSettings, Signal
from PySide6.QtWidgets import QWidget

import fabriques_chutier
from mixed_media_utility.gui import catalogue, depot_projets
from mixed_media_utility.gui.application import LancementApplication
from mixed_media_utility.gui.coquille import Coquille
from mixed_media_utility.gui.ecran_projet import EcranProjet
from mixed_media_utility.gui.preferences_projets import PreferencesProjets


class CoquilleDoublure(QWidget):
    """Doublure de la coquille : se montrer, se nommer, ET recevoir son projet.

    **La troisieme moitie manquait, et c'est ce qui a laisse passer le defaut
    du 2026-08-26** : la doublure ne portait pas `ouvrir_projet`, donc aucun
    test de ce fichier ne POUVAIT constater que l'enchainement ne l'appelait
    jamais. Une doublure qui n'expose pas la methode de son original ne mesure
    rien de la couture -- elle la masque.

    **Meme lecon, seconde application, 2026-08-27** : le bouton d'accueil
    (`EPIC7-ARB-92`) ajoute un signal `accueil_demande` a la coquille, et
    l'assemblage s'y connecte. Une doublure qui ne le porterait pas ferait
    tomber l'assemblage sur un `AttributeError` -- ou pire, si l'assemblage se
    protegeait, masquerait un cablage absent. Le signal est donc **declare
    ici**, et le test qui suit verifie qu'il n'a pas ete invente : la vraie
    coquille le porte aussi.
    """

    #: Le signal du bouton d'accueil, comme sur l'original.
    accueil_demande = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        #: Les chemins recus, dans l'ordre. Une LISTE et non un dernier appel :
        #: « un seul projet a la fois » se mesure sur la sequence.
        self.projets_ouverts = []

    def ouvrir_projet(self, project_dir, manifest=None, *, existe=None):
        self.projets_ouverts.append(project_dir)

    def montrer_en_grand(self):
        """La coquille reelle s'affiche MAXIMISEE (`EPIC7-ARB-93`).

        La doublure se contente de se montrer : un banc headless n'a pas de
        bureau a remplir, et c'est `test_la_coquille_reelle_s_ouvre_maximisee`
        qui mesure la maximisation sur la vraie surface.
        """
        self.montre_en_grand = True
        self.show()
        return self


#: Ce que l'enchainement de lancement ATTEND de la coquille. La liste vit ici,
#: une fois, et sert a la fois de contrat de la doublure et d'assertion.
MEMBRES_ATTENDUS_DE_LA_COQUILLE = (
    "ouvrir_projet",
    "montrer_en_grand",
    "accueil_demande",
)


def test_la_doublure_ne_promet_rien_que_la_vraie_coquille_n_ait(qtbot):
    """La doublure ne doit pas s'ecarter de son original.

    C'est le garde-fou du garde-fou, et il a deja servi deux fois : une
    doublure a qui il manque un membre fait tomber l'assemblage sur un
    `AttributeError` (2026-08-27, deux fois de suite : `accueil_demande` puis
    `montrer_en_grand`) ; une doublure qui en declare un que la coquille n'a
    pas rend verts des tests qui ne mesurent plus rien. On confronte donc les
    deux surfaces, dans les deux sens, plutot que de se fier a la lecture.
    """
    vraie = Coquille()
    qtbot.addWidget(vraie)
    doublure = CoquilleDoublure()
    qtbot.addWidget(doublure)

    for nom in MEMBRES_ATTENDUS_DE_LA_COQUILLE:
        assert hasattr(doublure, nom), f"la doublure ne porte pas {nom}"
        assert hasattr(vraie, nom), f"la vraie coquille ne porte pas {nom}"


def test_la_coquille_reelle_s_ouvre_maximisee(qtbot):
    """`EPIC7-ARB-93` : « A l'ouverture la fenetre de l'application est reduite. »

    Mesure sur l'etat de fenetre REEL, pas sur l'appel : c'est
    `montrer_en_grand` qui doit produire l'effet, et la doublure ne peut pas
    en temoigner.
    """
    from PySide6.QtCore import Qt

    coquille = Coquille()
    qtbot.addWidget(coquille)
    assert not (coquille.windowState() & Qt.WindowState.WindowMaximized), (
        "precondition : construire une coquille ne la maximise pas"
    )

    coquille.montrer_en_grand()

    assert coquille.windowState() & Qt.WindowState.WindowMaximized


def _ecrire_projet(dossier, identifiant, cree_le):
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / depot_projets.NOM_FICHIER_PROJET).write_text(
        json.dumps(depot_projets.manifeste_minimal(identifiant, cree_le=cree_le)),
        encoding="utf-8",
    )
    return dossier


@pytest.fixture
def deux_projets(tmp_path):
    """DEUX projets distinguables : un enchainement qui rendrait toujours le
    premier ne se demasque pas sur un projet unique."""
    return (
        _ecrire_projet(tmp_path / "travail" / "Aurore", "aurore", "2026-03-10T08:00:00Z"),
        _ecrire_projet(tmp_path / "travail" / "Brume", "brume", "2026-05-02T08:00:00Z"),
    )


@pytest.fixture
def preferences(tmp_path):
    return PreferencesProjets(
        QSettings(str(tmp_path / "reglages.ini"), QSettings.Format.IniFormat)
    )


def _lancement(qtbot, preferences, deux_projets, *, fabrique=None):
    preferences.definir_projets_connus([str(chemin) for chemin in deux_projets])
    preferences.enregistrer()
    ecran = EcranProjet(preferences=preferences, selecteur_de_dossier=lambda: None)
    qtbot.addWidget(ecran)
    fabriques = []

    def _fabrique_doublure():
        doublure = CoquilleDoublure()
        qtbot.addWidget(doublure)
        fabriques.append(doublure)
        return doublure

    lancement = LancementApplication(
        ecran=ecran, fabrique_de_coquille=fabrique or _fabrique_doublure
    )
    return lancement, fabriques


def test_le_demarrage_montre_l_ecran_et_n_ouvre_aucun_projet(
    qtbot, preferences, deux_projets
):
    lancement, fabriques = _lancement(qtbot, preferences, deux_projets)

    lancement.demarrer()
    qtbot.waitExposed(lancement.ecran)

    assert lancement.ecran.isVisible()
    assert lancement.coquille is None
    assert lancement.projet_ouvert is None
    assert fabriques == [], "une coquille a ete construite avant toute ouverture"


def test_ouvrir_un_projet_cache_l_ecran_et_montre_la_coquille(
    qtbot, preferences, deux_projets
):
    """La cible est le SECOND projet : un enchainement qui ouvrirait
    toujours le premier passerait un test a un seul projet."""
    lancement, fabriques = _lancement(qtbot, preferences, deux_projets)
    lancement.demarrer()
    qtbot.waitExposed(lancement.ecran)

    vise = next(
        widget
        for widget in lancement.ecran.widgets_de_ligne()
        if widget.ligne.nom == "Brume"
    )
    lancement.ecran.ouvrir_ligne(vise.ligne)

    assert not lancement.ecran.isVisible()
    assert lancement.coquille is fabriques[-1]
    assert lancement.coquille.isVisible()
    assert lancement.projet_ouvert.nom == "Brume"


def test_ouvrir_un_projet_transmet_son_chemin_a_la_coquille(
    qtbot, preferences, deux_projets
):
    """**Le test de couture.** L'enchainement doit APPELER `ouvrir_projet` :
    poser le titre de fenetre ne transmet aucun contexte, et une coquille sans
    contexte a l'arbre vide et fait lever `Path(None)` au premier « Detecter ».

    Cible : le SECOND projet, regle des fabriques -- un enchainement qui
    transmettrait toujours le premier passerait un test a un seul projet.
    """
    lancement, fabriques = _lancement(qtbot, preferences, deux_projets)
    lancement.demarrer()

    vise = next(
        widget
        for widget in lancement.ecran.widgets_de_ligne()
        if widget.ligne.nom == "Brume"
    )
    lancement.ecran.ouvrir_ligne(vise.ligne)

    coquille = fabriques[-1]
    assert coquille.projets_ouverts == [vise.ligne.chemin], (
        "l'enchainement n'a pas transmis le projet a la coquille"
    )


def test_ouvrir_un_second_projet_transmet_le_SECOND_chemin(
    qtbot, preferences, deux_projets
):
    """Volet symetrique du « un seul projet a la fois » : la coquille neuve
    recoit SON projet, et non celui d'avant."""
    lancement, fabriques = _lancement(qtbot, preferences, deux_projets)
    lancement.demarrer()
    par_nom = {
        widget.ligne.nom: widget for widget in lancement.ecran.widgets_de_ligne()
    }

    lancement.ecran.ouvrir_ligne(par_nom["Aurore"].ligne)
    lancement.ecran.ouvrir_ligne(par_nom["Brume"].ligne)

    premiere, seconde = fabriques
    assert premiere.projets_ouverts == [par_nom["Aurore"].ligne.chemin]
    assert seconde.projets_ouverts == [par_nom["Brume"].ligne.chemin]


def test_la_vraie_coquille_recoit_le_projet_et_peuple_son_arbre(
    qtbot, tmp_path, preferences
):
    """Le test qui aurait attrape le defaut du 2026-08-26.

    Il ne se contente pas de l'appel : il mesure son EFFET sur la vraie
    `Coquille` -- le contexte de projet est pose ET l'arbre n'est pas vide.
    Une doublure ne peut pas le mesurer, et c'est tout l'interet.

    Le manifest porte **deux lots du meme rush** (fabrique du chutier, cible
    en seconde position) : un arbre qui ne se peuplerait qu'a moitie se voit,
    la un manifest a un seul lot le masquerait.
    """
    from mixed_media_utility.gui.modele_chutier import noeud_par_identifiant

    manifeste = depot_projets.manifeste_minimal("aurore")
    fabrique = fabriques_chutier.manifest_deux_lots_meme_rush()
    manifeste["rushes"] = fabrique["rushes"]
    manifeste["lots"] = fabrique["lots"]
    dossier = tmp_path / "travail" / "Aurore"
    dossier.mkdir(parents=True)
    (dossier / depot_projets.NOM_FICHIER_PROJET).write_text(
        json.dumps(manifeste), encoding="utf-8"
    )

    coquilles = []

    def _vraie():
        fenetre = Coquille()
        qtbot.addWidget(fenetre)
        coquilles.append(fenetre)
        return fenetre

    lancement, _ = _lancement(qtbot, preferences, [dossier], fabrique=_vraie)
    lancement.demarrer()
    vise = lancement.ecran.widgets_de_ligne()[0]
    assert vise.ligne.ouvrable, f"fixture illisible : {vise.ligne.motif}"

    lancement.ecran.ouvrir_ligne(vise.ligne)

    coquille = lancement.coquille
    assert coquille.racines(), "l'arbre de la coquille est reste vide"
    # Les DEUX lots sont la, le second compris -- pas seulement le premier.
    for lot in ("lot-cadence-24", "lot-cadence-18"):
        assert noeud_par_identifiant(coquille.racines(), lot) is not None, (
            f"le lot {lot} manque a l'arbre"
        )


def test_le_titre_de_la_fenetre_porte_le_nom_du_projet_via_le_catalogue(
    qtbot, preferences, deux_projets
):
    lancement, _ = _lancement(qtbot, preferences, deux_projets)
    lancement.demarrer()

    vise = next(
        widget
        for widget in lancement.ecran.widgets_de_ligne()
        if widget.ligne.nom == "Brume"
    )
    lancement.ecran.ouvrir_ligne(vise.ligne)

    attendu = catalogue.CHAINES["fenetre-titre-projet"].format(projet="Brume")
    assert lancement.coquille.windowTitle() == attendu
    assert "Brume" in attendu


def test_un_seul_projet_ouvert_a_la_fois(qtbot, preferences, deux_projets):
    """Ouvrir un second projet REMPLACE le premier : la coquille precedente
    s'en va, elle ne cohabite pas avec la nouvelle."""
    lancement, fabriques = _lancement(qtbot, preferences, deux_projets)
    lancement.demarrer()
    par_nom = {
        widget.ligne.nom: widget for widget in lancement.ecran.widgets_de_ligne()
    }

    lancement.ecran.ouvrir_ligne(par_nom["Aurore"].ligne)
    premiere = lancement.coquille
    lancement.ecran.ouvrir_ligne(par_nom["Brume"].ligne)

    assert len(fabriques) == 2
    assert lancement.coquille is not premiere
    assert lancement.projet_ouvert.nom == "Brume"
    assert not premiere.isVisible(), "la coquille du projet precedent est restee"


def test_une_ligne_en_erreur_ne_donne_jamais_la_main_a_une_coquille(
    qtbot, tmp_path, preferences, deux_projets
):
    """Volet symetrique : le passage de main n'a lieu QUE sur une ouverture
    reelle -- un projet illisible n'en declenche aucun."""
    casse = tmp_path / "travail" / "Version inconnue"
    casse.mkdir(parents=True)
    manifeste = depot_projets.manifeste_minimal("version-inconnue")
    manifeste["schema_version"] = "9.9"
    (casse / depot_projets.NOM_FICHIER_PROJET).write_text(
        json.dumps(manifeste), encoding="utf-8"
    )
    lancement, fabriques = _lancement(
        qtbot, preferences, list(deux_projets) + [casse]
    )
    lancement.demarrer()

    cassee = next(
        widget
        for widget in lancement.ecran.widgets_de_ligne()
        if widget.ligne.nom == "Version inconnue"
    )
    lancement.ecran.ouvrir_ligne(cassee.ligne)

    assert fabriques == []
    assert lancement.coquille is None
    assert lancement.projet_ouvert is None
    # L'ecran reste la surface courante : rien ne l'a cache.
    assert lancement.ecran.isVisible()


def test_l_enchainement_construit_la_VRAIE_coquille_du_socle(
    qtbot, preferences, deux_projets
):
    """Un test au moins prend la vraie coquille : sans lui, les doublures
    ci-dessus pourraient masquer une incompatibilite avec le socle."""
    coquilles = []

    def _vraie():
        fenetre = Coquille()
        qtbot.addWidget(fenetre)
        coquilles.append(fenetre)
        return fenetre

    lancement, _ = _lancement(qtbot, preferences, deux_projets, fabrique=_vraie)
    lancement.demarrer()
    vise = next(
        widget
        for widget in lancement.ecran.widgets_de_ligne()
        if widget.ligne.nom == "Brume"
    )

    lancement.ecran.ouvrir_ligne(vise.ligne)

    assert isinstance(lancement.coquille, Coquille)
    assert lancement.coquille.ateliers(), "la coquille du socle a perdu ses ateliers"


def test_le_point_d_entree_construit_l_enchainement_pas_la_coquille_seule(qtbot):
    """`principal()` passe desormais par l'ecran de projet ; l'ancienne
    ``construire_application`` garde son contrat de socle intact."""
    from mixed_media_utility.gui.__main__ import (
        construire_application,
        construire_lancement,
    )

    _, coquille = construire_application([])
    qtbot.addWidget(coquille)
    assert isinstance(coquille, Coquille)

    _, lancement = construire_lancement([])
    qtbot.addWidget(lancement.ecran)
    assert isinstance(lancement, LancementApplication)
    assert isinstance(lancement.ecran, EcranProjet)
    assert lancement.coquille is None
