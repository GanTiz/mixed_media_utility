# -*- coding: utf-8 -*-
"""L'ecran de gestion de projet, sur le banc headless (story 7.1).

Couvre les AC 2 (la liste, le tri, la recherche, l'epingle), 3 (dernier
projet en tete NON preselectionne, affichage a chaque lancement, passage de
main a la coquille), 4 (rushes introuvables ouvrables ; projet illisible en
ligne d'erreur avec motif, jamais un crash) et 5 (import -- meme lecture,
jamais une fusion), plus les chaines et les jetons (Task 6).

**Regle des fabriques.** La fabrique de projets de ce fichier pose TROIS
dossiers reels aux noms, chemins et dates de creation tous differents, et
chaque assertion vise un projet qui n'est ni le premier de la liste connue
ni le premier par ordre alphabetique.

Aucune preference reelle n'est touchee : toutes les surfaces recoivent un
``QSettings`` INI dans un dossier temporaire.
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime
from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, QPoint, QSettings, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QStyle,
    QStyleOptionViewItem,
    QToolButton,
)

from mixed_media_utility.gui import catalogue, depot_projets, jetons
from mixed_media_utility.gui.ecran_projet import (
    ROLES_DE_DONNEE_PURE,
    EcranProjet,
)
from mixed_media_utility.gui.preferences_projets import PreferencesProjets

MARQUE = "█"

#: Trois projets distinguables : les noms ne sont pas dans le meme ordre que
#: les dates de creation, ce qui rend visible tout tri applique a la place
#: d'un autre.
_JEU = (
    ("Aurore", "2026-03-10T08:00:00Z"),
    ("Brume", "2026-05-02T08:00:00Z"),
    ("Crepuscule", "2026-01-15T08:00:00Z"),
)


def _ecrire_projet(dossier, identifiant, cree_le):
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / depot_projets.NOM_FICHIER_PROJET).write_text(
        json.dumps(depot_projets.manifeste_minimal(identifiant, cree_le=cree_le)),
        encoding="utf-8",
    )
    return dossier


@pytest.fixture
def dossiers(tmp_path):
    """Trois dossiers de projet reels et lisibles, valeurs distinctes."""
    racine = tmp_path / "travail"
    return {
        nom: _ecrire_projet(racine / nom, nom.lower(), cree_le)
        for nom, cree_le in _JEU
    }


@pytest.fixture
def preferences(tmp_path):
    return PreferencesProjets(
        QSettings(str(tmp_path / "reglages.ini"), QSettings.Format.IniFormat)
    )


def _preferences_connaissant(preferences, dossiers, *, dernier_ouvert=None):
    preferences.definir_projets_connus([str(d) for d in dossiers])
    if dernier_ouvert is not None:
        preferences.definir_dernier_ouvert(str(dernier_ouvert))
    preferences.enregistrer()
    return preferences


def _construire(
    qtbot, preferences, *, chaines=None, dossier_choisi=None, creation=None
):
    """L'ecran, ses deux boites de dialogue neutralisees.

    ``creation`` remplace la surface de creation d'`EPIC7-ARB-82`, qui est une
    **modale** : son ``QDialog.exec()`` entre dans une boucle d'evenements dont
    un banc ne sort jamais. Sans cette injection la suite ne rend pas la main
    -- mesure faite, `pytest tests/unit/gui` restait bloque au-dela de dix
    minutes. Le dialogue lui-meme se mesure a part, **sans** ``exec()``.

    La valeur attendue est le couple ``(dossier_parent, nom)`` que
    l'operatrice aurait valide, ou ``None`` pour une annulation.
    """
    ecran = EcranProjet(
        preferences=preferences,
        chaines=chaines,
        selecteur_de_dossier=lambda: dossier_choisi,
        demandeur_de_creation=lambda: creation,
    )
    qtbot.addWidget(ecran)
    return ecran


def _noms(ecran):
    return [ligne.nom for ligne in ecran.lignes_affichees()]


# ---------------------------------------------------------------------------
# AC 2 -- la liste porte nom, chemin, deux dates
# ---------------------------------------------------------------------------


def test_chaque_ligne_porte_le_nom_le_chemin_et_les_deux_dates(
    qtbot, preferences, dossiers
):
    _preferences_connaissant(preferences, dossiers.values())
    ecran = _construire(qtbot, preferences)

    # La cible est en DEUXIEME position par ordre alphabetique.
    vise = next(
        widget for widget in ecran.widgets_de_ligne() if widget.ligne.nom == "Brume"
    )
    assert vise.libelle_nom.text() == "Brume"
    assert vise.libelle_chemin.text() == str(dossiers["Brume"])
    # `EPIC7-ARB-62` : les deux dates dans le MEME format, heure locale.
    # La reference est calculee ici, independamment du formatteur de
    # production -- une comparaison a `_texte_de_date_de_creation` serait
    # tautologique.
    attendu = (
        datetime.fromisoformat("2026-05-02T08:00:00+00:00")
        .astimezone()
        .strftime("%Y-%m-%d %H:%M")
    )
    assert attendu in vise.libelle_creation.text()
    assert vise.libelle_modification.text().strip() != ""


def test_le_tri_de_la_surface_reordonne_nominativement(qtbot, preferences, dossiers):
    _preferences_connaissant(preferences, dossiers.values())
    ecran = _construire(qtbot, preferences)

    ecran.selecteur_de_tri.setCurrentIndex(0)  # nom
    assert _noms(ecran) == ["Aurore", "Brume", "Crepuscule"]

    ecran.selecteur_de_tri.setCurrentIndex(1)  # date de creation
    assert _noms(ecran) == ["Crepuscule", "Aurore", "Brume"]


def test_la_recherche_de_la_surface_rend_la_ligne_visee(qtbot, preferences, dossiers):
    _preferences_connaissant(preferences, dossiers.values())
    ecran = _construire(qtbot, preferences)

    ecran.champ_recherche.setText("brum")

    assert _noms(ecran) == ["Brume"]


def test_l_epingle_est_actionnable_sur_la_ligne_sans_menu_contextuel(
    qtbot, preferences, dossiers
):
    """`EPIC7-ARB-37` : « sauf *rattacher a*, aucune commande n'existe
    uniquement au clic droit ». Le menu contextuel n'arrive qu'en 7.11 : le
    geste d'epingle doit donc vivre SUR la ligne, et on le mesure -- aucun
    widget de la surface n'a de politique de menu contextuel."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QWidget

    _preferences_connaissant(preferences, dossiers.values())
    ecran = _construire(qtbot, preferences)
    ecran.selecteur_de_tri.setCurrentIndex(0)

    # Aucun menu contextuel nulle part dans la surface.
    politiques = {
        widget.contextMenuPolicy() for widget in ecran.findChildren(QWidget)
    }
    assert Qt.ContextMenuPolicy.CustomContextMenu not in politiques
    assert Qt.ContextMenuPolicy.ActionsContextMenu not in politiques

    # La cible est en TROISIEME position, jamais la premiere.
    cible = next(
        widget
        for widget in ecran.widgets_de_ligne()
        if widget.ligne.nom == "Crepuscule"
    )
    cible.bouton_epingle.click()

    assert _noms(ecran)[0] == "Crepuscule"
    assert ecran.preferences.epingles(), "l'epingle n'a pas ete persistee"


def test_l_epingle_resiste_au_tri_sur_la_surface(qtbot, preferences, dossiers):
    _preferences_connaissant(preferences, dossiers.values())
    ecran = _construire(qtbot, preferences)
    ecran.selecteur_de_tri.setCurrentIndex(0)
    assert _noms(ecran)[-1] == "Crepuscule"

    cible = next(
        widget
        for widget in ecran.widgets_de_ligne()
        if widget.ligne.nom == "Crepuscule"
    )
    cible.bouton_epingle.click()
    ecran.selecteur_de_tri.setCurrentIndex(1)  # date de creation

    assert _noms(ecran)[0] == "Crepuscule"


# ---------------------------------------------------------------------------
# AC 3 -- dernier projet en tete, NON preselectionne
# ---------------------------------------------------------------------------


def test_le_dernier_ouvert_est_en_tete_et_rien_n_est_preselectionne(
    qtbot, preferences, dossiers
):
    """Les DEUX assertions, pas l'une : en tete, et index de selection nul.

    La cible « Brume » n'est ni la premiere par ordre alphabetique (Aurore
    l'est) ni la premiere par date de creation (Crepuscule l'est) : un tri
    accidentel qui donnerait le bon resultat par hasard se demasque.
    """
    _preferences_connaissant(
        preferences, dossiers.values(), dernier_ouvert=dossiers["Brume"]
    )
    ecran = _construire(qtbot, preferences)

    assert _noms(ecran)[0] == "Brume"
    assert ecran.index_selection is None
    assert ecran.widgets_de_ligne()[0].porte_lisere is True
    assert all(
        widget.porte_lisere is False for widget in ecran.widgets_de_ligne()[1:]
    )


def test_ouvrir_puis_relancer_remet_le_dernier_ouvert_en_tete(
    qtbot, preferences, dossiers
):
    """Relance simulee : une SECONDE surface batie sur les memes
    preferences, comme au lancement suivant."""
    _preferences_connaissant(preferences, dossiers.values())
    premiere = _construire(qtbot, preferences)
    cible = next(
        widget for widget in premiere.widgets_de_ligne() if widget.ligne.nom == "Brume"
    )
    premiere.ouvrir_ligne(cible.ligne)

    seconde = _construire(qtbot, preferences)

    assert _noms(seconde)[0] == "Brume"
    assert seconde.index_selection is None


def test_sans_designation_le_geste_d_ouverture_reste_sans_effet(
    qtbot, preferences, dossiers
):
    """Corollaire actionnable de la non-preselection : aucune entree ne
    s'ouvre sans designation prealable."""
    _preferences_connaissant(preferences, dossiers.values())
    ecran = _construire(qtbot, preferences)
    recus = []
    ecran.projet_ouvert.connect(recus.append)

    assert ecran.ouvrir_la_selection() is None

    assert recus == []
    assert ecran.bouton_ouvrir.isEnabled() is False


def test_designer_une_ligne_arme_l_ouverture(qtbot, preferences, dossiers):
    _preferences_connaissant(preferences, dossiers.values())
    ecran = _construire(qtbot, preferences)
    ecran.selecteur_de_tri.setCurrentIndex(0)
    recus = []
    ecran.projet_ouvert.connect(recus.append)

    # Cible en TROISIEME position.
    cible = next(
        widget
        for widget in ecran.widgets_de_ligne()
        if widget.ligne.nom == "Crepuscule"
    )
    ecran._sur_designation(cible.ligne)
    assert ecran.bouton_ouvrir.isEnabled() is True

    ouverte = ecran.ouvrir_la_selection()

    assert ouverte.nom == "Crepuscule"
    assert [ligne.nom for ligne in recus] == ["Crepuscule"]


def test_avec_un_seul_projet_connu_l_ecran_s_affiche_sans_rien_ouvrir(
    qtbot, preferences, dossiers
):
    """« Toujours affiche, meme quand un seul projet existe. Aucun saut
    direct dans un atelier. »"""
    _preferences_connaissant(preferences, [dossiers["Brume"]])
    ecran = _construire(qtbot, preferences)
    recus = []
    ecran.projet_ouvert.connect(recus.append)
    ecran.show()
    qtbot.waitExposed(ecran)

    assert ecran.isVisible()
    assert _noms(ecran) == ["Brume"]
    assert ecran.index_selection is None
    assert recus == []


def test_sans_aucun_projet_l_ecran_montre_l_etat_vide_et_ses_actions(
    qtbot, preferences
):
    ecran = _construire(qtbot, preferences)
    ecran.show()
    qtbot.waitExposed(ecran)

    assert ecran.lignes_affichees() == ()
    assert ecran.libelle_liste_vide.isVisible()
    # DEUX actions depuis `EPIC7-ARB-83`, et les deux actionnables : un ecran
    # vide dont l'action serait grisee serait une impasse au premier lancement.
    for bouton in (ecran.bouton_creer, ecran.bouton_ouvrir_dossier):
        assert bouton.isEnabled(), "une action de l'etat vide n'est pas actionnable"


# ---------------------------------------------------------------------------
# AC 4 -- sources introuvables, projets illisibles
# ---------------------------------------------------------------------------


def _projet_aux_chemins_morts(racine):
    dossier = racine / "Sources parties"
    dossier.mkdir(parents=True)
    manifeste = depot_projets.manifeste_minimal("sources-parties")
    manifeste["rushes"] = [
        {"rush_id": "rush-001", "source_path": "srcs/disparu-1.mov"},
        {"rush_id": "rush-002", "source_path": "srcs/disparu-2.mov"},
    ]
    (dossier / depot_projets.NOM_FICHIER_PROJET).write_text(
        json.dumps(manifeste), encoding="utf-8"
    )
    return dossier


def _projet_de_version_inconnue(racine):
    dossier = racine / "Version inconnue"
    dossier.mkdir(parents=True)
    manifeste = depot_projets.manifeste_minimal("version-inconnue")
    manifeste["schema_version"] = "9.9"
    (dossier / depot_projets.NOM_FICHIER_PROJET).write_text(
        json.dumps(manifeste), encoding="utf-8"
    )
    return dossier


def test_une_ligne_aux_chemins_morts_ne_porte_aucun_signe_particulier(
    qtbot, tmp_path, preferences, dossiers
):
    morts = _projet_aux_chemins_morts(tmp_path / "travail")
    _preferences_connaissant(preferences, [dossiers["Aurore"], morts, dossiers["Brume"]])
    ecran = _construire(qtbot, preferences)

    vise = next(
        widget
        for widget in ecran.widgets_de_ligne()
        if widget.ligne.nom == "Sources parties"
    )
    assert vise.ligne.ouvrable
    assert vise.libelle_motif is None
    # Aucun libelle supplementaire par rapport a une ligne saine : la
    # comparaison porte sur le CARDINAL des etiquettes, ligne contre ligne.
    saine = next(
        widget for widget in ecran.widgets_de_ligne() if widget.ligne.nom == "Aurore"
    )
    assert len(vise.findChildren(QLabel)) == len(saine.findChildren(QLabel))

    ouverte = ecran.ouvrir_ligne(vise.ligne)
    assert ouverte is not None, "l'ouverture doit aboutir malgre les chemins morts"


def test_les_trois_familles_d_echec_sont_des_lignes_en_erreur_avec_motif(
    qtbot, tmp_path, preferences, dossiers
):
    """Trois fixtures d'echec, l'erreur JAMAIS en premiere position dans la
    liste connue : dossier sain, puis les trois echecs, puis un autre sain.
    """
    racine = tmp_path / "casse"
    sans_fichier = racine / "Sans fichier"
    sans_fichier.mkdir(parents=True)
    tronque = racine / "Tronque"
    tronque.mkdir(parents=True)
    (tronque / depot_projets.NOM_FICHIER_PROJET).write_text("{", encoding="utf-8")
    inconnue = _projet_de_version_inconnue(racine)

    _preferences_connaissant(
        preferences,
        [dossiers["Aurore"], sans_fichier, tronque, inconnue, dossiers["Brume"]],
    )
    ecran = _construire(qtbot, preferences)
    ecran.selecteur_de_tri.setCurrentIndex(0)

    par_nom = {widget.ligne.nom: widget for widget in ecran.widgets_de_ligne()}
    assert set(par_nom) == {
        "Aurore",
        "Brume",
        "Sans fichier",
        "Tronque",
        "Version inconnue",
    }

    for nom in ("Sans fichier", "Tronque", "Version inconnue"):
        widget = par_nom[nom]
        assert not widget.ligne.ouvrable, f"{nom} ne devrait pas etre ouvrable"
        assert widget.libelle_motif is not None
        assert widget.libelle_motif.text().strip(), f"motif vide pour {nom}"
        assert ecran.ouvrir_ligne(widget.ligne) is None

    # Le motif de la version inconnue cite la version fautive : c'est ce que
    # le coeur ecrit, et c'est pour cela qu'on l'affiche verbatim.
    assert "9.9" in par_nom["Version inconnue"].libelle_motif.text()

    # Les trois motifs sont DISTINCTS : trois pannes, trois messages.
    motifs = {
        par_nom[nom].libelle_motif.text()
        for nom in ("Sans fichier", "Tronque", "Version inconnue")
    }
    assert len(motifs) == 3

    # Les lignes saines, elles, restent ouvrables.
    for nom in ("Aurore", "Brume"):
        assert ecran.ouvrir_ligne(par_nom[nom].ligne) is not None


def test_une_ligne_en_erreur_ne_se_designe_pas(qtbot, tmp_path, preferences, dossiers):
    inconnue = _projet_de_version_inconnue(tmp_path / "casse")
    _preferences_connaissant(preferences, [dossiers["Aurore"], inconnue])
    ecran = _construire(qtbot, preferences)

    cassee = next(
        widget
        for widget in ecran.widgets_de_ligne()
        if widget.ligne.nom == "Version inconnue"
    )
    ecran._sur_designation(cassee.ligne)

    assert ecran.index_selection is None
    assert ecran.bouton_ouvrir.isEnabled() is False


def test_une_ligne_en_erreur_reste_listee(qtbot, tmp_path, preferences, dossiers):
    """La faire disparaitre ferait d'un message fugace le seul porteur d'un
    echec -- ce que `EXPERIENCE.md` bannit."""
    inconnue = _projet_de_version_inconnue(tmp_path / "casse")
    _preferences_connaissant(preferences, [dossiers["Aurore"], inconnue])
    ecran = _construire(qtbot, preferences)

    ecran.selecteur_de_tri.setCurrentIndex(2)
    ecran.champ_recherche.setText("")

    assert "Version inconnue" in _noms(ecran)


# ---------------------------------------------------------------------------
# AC 1 (surface) -- creer
# ---------------------------------------------------------------------------


def test_creer_fabrique_le_dossier_de_projet_sous_le_dossier_designe(
    qtbot, tmp_path, preferences
):
    """`EPIC7-ARB-82` : on designe le PARENT, l'outil cree le dossier.

    Le dossier de projet n'existe pas avant le geste -- c'est tout l'objet de
    l'arbitrage : l'operatrice n'a plus a le fabriquer a la main hors de
    l'outil avant de l'ouvrir.
    """
    destination = tmp_path / "travail"
    destination.mkdir()
    assert not (destination / "Projet neuf").exists()

    ecran = _construire(qtbot, preferences, creation=(destination, "Projet neuf"))
    recus = []
    ecran.projet_ouvert.connect(recus.append)

    ecran.bouton_creer.click()

    neuf = destination / "Projet neuf"
    assert neuf.is_dir(), "l'outil cree lui-meme le dossier de projet"
    assert (neuf / depot_projets.NOM_FICHIER_PROJET).is_file()
    assert _noms(ecran) == ["Projet neuf"]
    assert [ligne.nom for ligne in recus] == ["Projet neuf"]
    assert preferences.dernier_ouvert() == str(neuf)


def test_creer_pose_l_arborescence_de_travail_du_coeur(
    qtbot, tmp_path, preferences
):
    """« et le peuple avec l'arborescence » (Egan, 2026-08-27).

    L'attendu est **lu du coeur** (`project_layout`) et non recopie ici : une
    liste de dossiers ecrite dans le test serait une seconde definition de
    l'arborescence, exactement ce que la frontiere interdit au code.
    """
    from mixed_media_utility.io import project_layout

    destination = tmp_path / "travail"
    destination.mkdir()
    ecran = _construire(qtbot, preferences, creation=(destination, "Vent"))

    ecran.bouton_creer.click()

    temoin = tmp_path / "temoin"
    temoin.mkdir()
    project_layout.ensure_project_layout(temoin)
    attendus = {chemin.name for chemin in temoin.iterdir() if chemin.is_dir()}
    assert attendus, "precondition : le coeur pose bien des dossiers"

    obtenus = {
        chemin.name for chemin in (destination / "Vent").iterdir() if chemin.is_dir()
    }
    assert attendus <= obtenus


def test_creer_sur_un_dossier_cible_deja_pourvu_n_ecrase_rien(
    qtbot, tmp_path, preferences, dossiers
):
    """Le geste nominal sur ce dossier-la, c'est « ouvrir » -- pas d'ecrasement.

    La cible porte le nom d'un projet EXISTANT, sous son propre parent : c'est
    le seul moyen de faire tomber le refus par le chemin qu'`EPIC7-ARB-82`
    emprunte desormais (parent + nom), et non par le chemin d'avant.
    """
    brume = dossiers["Brume"]
    ecran = _construire(qtbot, preferences, creation=(brume.parent, brume.name))
    recus = []
    ecran.projet_ouvert.connect(recus.append)
    avant = (brume / depot_projets.NOM_FICHIER_PROJET).read_text(encoding="utf-8")

    ecran.bouton_creer.click()

    assert recus == [], "un refus de creation ne doit rien ouvrir"
    assert ecran.libelle_echec.text() == catalogue.CHAINES[
        "ecran-projet-creation-dossier-occupe"
    ]
    apres = (brume / depot_projets.NOM_FICHIER_PROJET).read_text(encoding="utf-8")
    assert apres == avant


def test_un_nom_dont_le_coeur_ne_tire_rien_ne_laisse_aucun_dossier(
    qtbot, tmp_path, preferences
):
    """Un refus de nommage ne doit pas laisser un dossier vide derriere lui.

    L'ordre « deriver l'identifiant, PUIS creer » est le contrat ; l'inverse
    creerait le dossier avant de decouvrir que le nom ne donne aucun
    identifiant conforme au schema.
    """
    destination = tmp_path / "travail"
    destination.mkdir()
    ecran = _construire(qtbot, preferences, creation=(destination, "###"))

    ecran.bouton_creer.click()

    assert ecran.libelle_echec.text() == catalogue.CHAINES["ecran-projet-nom-refuse"]
    assert list(destination.iterdir()) == [], "aucun dossier laisse derriere"


def test_annuler_l_une_ou_l_autre_boite_ne_fait_rien(qtbot, preferences, dossiers):
    """Les DEUX actions restantes annulables, et le compte de lignes intact."""
    _preferences_connaissant(preferences, dossiers.values())
    ecran = _construire(qtbot, preferences, dossier_choisi=None, creation=None)
    recus = []
    ecran.projet_ouvert.connect(recus.append)

    ecran.bouton_creer.click()
    ecran.bouton_ouvrir_dossier.click()

    assert recus == []
    assert len(_noms(ecran)) == 3


def test_l_ecran_ne_porte_plus_de_bouton_d_import(qtbot, preferences):
    """`EPIC7-ARB-83` : deux actions, plus trois.

    Motif du retrait, mesure avant : `importer_un_projet` et
    `ouvrir_un_dossier` appelaient tous deux `_designer_et_accueillir` -- le
    meme code au caractere pres. Le comportement attendu d'un vrai import est
    ecrit dans la story 7.14.
    """
    ecran = _construire(qtbot, preferences)

    assert not hasattr(ecran, "bouton_importer")
    assert not hasattr(ecran, "importer_un_projet")
    libelles = {
        bouton.text()
        for bouton in ecran.findChildren(QPushButton)
    }
    assert catalogue.CHAINES["ecran-projet-importer"] not in libelles


# ---------------------------------------------------------------------------
# Le chemin de LECTURE d'un dossier designe : meme lecture, jamais une fusion
#
# Ces cas mesuraient « importer » jusqu'au 2026-08-27. `EPIC7-ARB-83` a retire
# ce bouton -- il appelait le meme code qu'« ouvrir un dossier », au caractere
# pres. Ce que les cas mesurent, en revanche, n'a pas disparu avec lui : c'est
# le chemin de lecture d'un dossier hors de la liste connue, et il est desormais
# emprunte par le geste restant. Les noms gardent le mot « importer » pour que
# la trace reste lisible ; ce qu'ils exercent est `ouvrir_un_dossier`.
# ---------------------------------------------------------------------------


def test_importer_ajoute_une_ligne_et_ouvre(qtbot, tmp_path, preferences, dossiers):
    _preferences_connaissant(preferences, [dossiers["Aurore"], dossiers["Brume"]])
    hors_liste = _ecrire_projet(
        tmp_path / "ailleurs" / "Delta", "delta", "2026-06-01T08:00:00Z"
    )
    ecran = _construire(qtbot, preferences, dossier_choisi=hors_liste)
    recus = []
    ecran.projet_ouvert.connect(recus.append)
    assert "Delta" not in _noms(ecran), "precondition : hors de la liste connue"

    ecran.bouton_ouvrir_dossier.click()

    assert len(_noms(ecran)) == 3
    assert "Delta" in _noms(ecran)
    assert [ligne.nom for ligne in recus] == ["Delta"]
    assert str(hors_liste) in preferences.projets_connus()


def test_importer_un_projet_aux_chemins_morts_ouvre_comme_ouvrir(
    qtbot, tmp_path, preferences
):
    morts = _projet_aux_chemins_morts(tmp_path / "ailleurs")
    ecran = _construire(qtbot, preferences, dossier_choisi=morts)
    recus = []
    ecran.projet_ouvert.connect(recus.append)

    ecran.bouton_ouvrir_dossier.click()

    assert [ligne.nom for ligne in recus] == ["Sources parties"]
    widget = ecran.widgets_de_ligne()[0]
    assert widget.libelle_motif is None


@pytest.mark.parametrize("fabrique", ["sans-fichier", "tronque", "version-inconnue"])
def test_importer_un_dossier_illisible_donne_une_ligne_en_erreur(
    qtbot, tmp_path, preferences, fabrique
):
    """Identique a « ouvrir » : les trois memes fixtures d'echec, le meme
    resultat -- ligne en erreur avec motif, non ouvrable. C'est la preuve
    que l'import emprunte le MEME chemin de lecture."""
    racine = tmp_path / "ailleurs"
    if fabrique == "sans-fichier":
        dossier = racine / "Sans fichier"
        dossier.mkdir(parents=True)
    elif fabrique == "tronque":
        dossier = racine / "Tronque"
        dossier.mkdir(parents=True)
        (dossier / depot_projets.NOM_FICHIER_PROJET).write_text("{", encoding="utf-8")
    else:
        dossier = _projet_de_version_inconnue(racine)

    ecran = _construire(qtbot, preferences, dossier_choisi=dossier)
    recus = []
    ecran.projet_ouvert.connect(recus.append)

    ecran.bouton_ouvrir_dossier.click()

    assert recus == [], "un projet illisible ne s'ouvre pas"
    widget = ecran.widgets_de_ligne()[0]
    assert widget.libelle_motif is not None
    assert widget.libelle_motif.text().strip()
    assert not widget.ligne.ouvrable


def test_importer_un_projet_dont_l_identifiant_diverge_du_dossier(
    qtbot, tmp_path, preferences
):
    """Le `project_id` se LIT du manifeste, jamais recalcule : une
    divergence avec le nom du dossier n'est pas une erreur."""
    dossier = _ecrire_projet(
        tmp_path / "ailleurs" / "Un nom de dossier",
        "tout-autre-identifiant",
        "2026-06-01T08:00:00Z",
    )
    ecran = _construire(qtbot, preferences, dossier_choisi=dossier)
    recus = []
    ecran.projet_ouvert.connect(recus.append)

    ecran.bouton_ouvrir_dossier.click()

    assert [ligne.nom for ligne in recus] == ["Un nom de dossier"]
    assert depot_projets.identifiant_declare(dossier) == "tout-autre-identifiant"


def test_deux_projets_au_meme_identifiant_coexistent_sans_fusion(
    qtbot, tmp_path, preferences
):
    """`EPIC7-ARB-60` : « importer ne fusionne jamais deux projets -- aucune
    ecriture dans un manifest existant ».

    Le second projet est importe ALORS QUE le premier, deja connu, declare
    le meme identifiant. Les deux fichiers de projet sont compares OCTET A
    OCTET avant et apres : une fusion, meme partielle, se verrait.
    """
    premier = _ecrire_projet(
        tmp_path / "ailleurs" / "Copie A", "identifiant-partage", "2026-01-01T08:00:00Z"
    )
    second = _ecrire_projet(
        tmp_path / "ailleurs" / "Copie B", "identifiant-partage", "2026-02-02T08:00:00Z"
    )
    _preferences_connaissant(preferences, [premier])
    avant = {
        chemin: (chemin / depot_projets.NOM_FICHIER_PROJET).read_bytes()
        for chemin in (premier, second)
    }

    ecran = _construire(qtbot, preferences, dossier_choisi=second)
    ecran.bouton_ouvrir_dossier.click()

    assert sorted(_noms(ecran)) == ["Copie A", "Copie B"]
    # Deux lignes distinctes par leur CHEMIN, malgre l'identifiant commun.
    chemins = {str(ligne.chemin) for ligne in ecran.lignes_affichees()}
    assert chemins == {str(premier), str(second)}
    for chemin, contenu in avant.items():
        assert (
            chemin / depot_projets.NOM_FICHIER_PROJET
        ).read_bytes() == contenu, f"{chemin} a ete reecrit : c'est une fusion"


def test_ouvrir_un_dossier_deja_connu_ne_fabrique_pas_de_doublon(
    qtbot, preferences, dossiers
):
    _preferences_connaissant(preferences, dossiers.values())
    ecran = _construire(qtbot, preferences, dossier_choisi=dossiers["Crepuscule"])

    ecran.bouton_ouvrir_dossier.click()

    assert sorted(_noms(ecran)) == ["Aurore", "Brume", "Crepuscule"]


# ---------------------------------------------------------------------------
# Task 6 -- chaines au catalogue, jetons seuls
# ---------------------------------------------------------------------------


#: Les glyphes de la table d'iconographie. Un PICTOGRAMME n'est pas un
#: libelle : il ne se traduit pas, et `jetons` lui impose meme de ne jamais
#: vivre dans un ecran -- « l'icone vit dans la table d'iconographie et jamais
#: en glyphe litteral », condition pour que le jeu d'icones reste un
#: remplacement d'assets (story 7.4, AC 8). L'exiger dans le catalogue
#: reviendrait a lui demander d'etre a la fois une chaine traduisible et un
#: asset. La liste est LUE de `jetons`, jamais recopiee ici : une icone
#: ajoutee la-bas est exemptee ici sans qu'on y pense.
_PICTOGRAMMES = jetons.pictogrammes()


def _libelles_visibles(ecran):
    """Tous les textes affiches par l'ecran, DONNEES PURES exceptees.

    Trois roles sont exemptes -- le nom d'un dossier, son chemin et le
    motif verbatim d'un echec du coeur. Ce ne sont pas des libelles du
    produit : ce sont les valeurs de l'operatrice et les messages du coeur,
    et les faire passer par le catalogue serait le defaut que l'AC 4
    interdit (« lu, jamais recopie »). La liste est LUE du module plutot
    que devinee au contenu des textes.
    """
    textes = [ecran.windowTitle()]
    for libelle in ecran.findChildren(QLabel):
        if libelle.property("role") in ROLES_DE_DONNEE_PURE:
            continue
        if libelle.text():
            textes.append(libelle.text())
    for bouton in ecran.findChildren(QPushButton):
        if bouton.text():
            textes.append(bouton.text())
    for bouton in ecran.findChildren(QToolButton):
        for porte in (bouton.text(), bouton.toolTip(), bouton.accessibleName()):
            if porte and porte not in _PICTOGRAMMES:
                textes.append(porte)
    textes.append(ecran.champ_recherche.placeholderText())
    for indice in range(ecran.selecteur_de_tri.count()):
        textes.append(ecran.selecteur_de_tri.itemText(indice))
    return [texte for texte in textes if texte]


def test_tous_les_libelles_de_l_ecran_viennent_du_catalogue(
    qtbot, tmp_path, preferences, dossiers
):
    inconnue = _projet_de_version_inconnue(tmp_path / "casse")
    _preferences_connaissant(preferences, [dossiers["Aurore"], inconnue])
    marque = {cle: MARQUE + valeur for cle, valeur in catalogue.CHAINES.items()}
    ecran = _construire(qtbot, preferences, chaines=marque)

    libelles = _libelles_visibles(ecran)

    assert libelles, "l'ecran doit afficher des libelles"
    fautifs = [texte for texte in libelles if MARQUE not in texte]
    assert fautifs == [], f"libelles hors catalogue : {fautifs}"


def test_le_motif_du_coeur_n_est_PAS_marque_par_le_catalogue(
    qtbot, tmp_path, preferences
):
    """Volet symetrique du precedent -- sans lui, un ecran qui n'afficherait
    AUCUN motif passerait le test ci-dessus sans rien prouver."""
    inconnue = _projet_de_version_inconnue(tmp_path / "casse")
    _preferences_connaissant(preferences, [inconnue])
    marque = {cle: MARQUE + valeur for cle, valeur in catalogue.CHAINES.items()}
    ecran = _construire(qtbot, preferences, chaines=marque)

    widget = ecran.widgets_de_ligne()[0]
    motif = widget.libelle_motif
    assert motif is not None
    assert MARQUE not in motif.text()
    assert "9.9" in motif.text()
    # Le nom et le chemin du dossier sont de la meme famille : des donnees
    # de l'operatrice, jamais des libelles du produit.
    assert MARQUE not in widget.libelle_nom.text()
    assert MARQUE not in widget.libelle_chemin.text()


def test_aucun_libelle_gonfle_n_est_tronque(qtbot, preferences, dossiers):
    """Chaines allongees de 40 % (regle i18n de `DESIGN.md`) : aucune boite
    n'est calee sur la largeur d'une chaine."""
    _preferences_connaissant(preferences, dossiers.values())
    gonfle = {
        cle: valeur + "x" * max(1, math.ceil(0.4 * len(valeur)))
        for cle, valeur in catalogue.CHAINES.items()
    }
    ecran = _construire(qtbot, preferences, chaines=gonfle)
    ecran.resize(
        jetons.ESPACEMENTS["window-min-width"], jetons.ESPACEMENTS["window-min-height"]
    )
    ecran.show()
    qtbot.waitExposed(ecran)
    qtbot.wait(20)

    for libelle in ecran.findChildren(QLabel):
        if not libelle.isVisible() or not libelle.text():
            continue
        couvre = libelle.wordWrap() or (
            libelle.width() >= libelle.fontMetrics().horizontalAdvance(libelle.text())
        )
        assert couvre, f"libelle tronque : {libelle.text()!r}"


def test_le_fond_est_un_neutre_PLAT_et_l_ecran_porte_le_rayon_xl(qtbot, preferences):
    """`DESIGN.md` : « la maquette y pose un degrade radial, ecart a
    corriger ». Le fond est donc un aplat de ``surface-canvas``, et
    l'ecran de lancement porte ``rounded.xl``."""
    ecran = _construire(qtbot, preferences)
    feuille = ecran.styleSheet()

    assert "gradient" not in feuille.lower()
    assert f"background: {jetons.COULEURS['surface-canvas']}" in feuille
    assert f"border-radius: {jetons.RAYONS['xl']}px" in feuille


def test_le_titre_de_l_ecran_est_en_typographie_display(qtbot, preferences):
    """`DESIGN.md` reserve ``display`` (28 px) au nom du produit sur CET
    ecran, et a lui seul."""
    ecran = _construire(qtbot, preferences)
    feuille = ecran.styleSheet()
    display = jetons.TYPOGRAPHIE["display"]

    assert ecran.titre.property("role") == "titre"
    assert f"font-size: {display['taille']}px" in feuille


# ---------------------------------------------------------------------------
# Correctifs de la revue de vague 2
# ---------------------------------------------------------------------------


def _evenement_souris(widget, type_d_evenement, bouton):
    """Un VRAI evenement Qt, remis a la main du widget.

    Les tests de designation de ce fichier appellent les methodes du modele
    (`_sur_designation`, `ouvrir_ligne`) : aucun ne passait par le chemin
    reel `mousePressEvent`/`mouseDoubleClickEvent`, si bien que le filtre de
    bouton ci-dessous n'y etait mesure nulle part. Le chutier, lui, mesure
    son clic droit depuis toujours.
    """
    position = QPoint(20, 10)
    return QMouseEvent(
        type_d_evenement,
        position,
        widget.mapToGlobal(position),
        bouton,
        bouton,
        Qt.KeyboardModifier.NoModifier,
    )


def test_le_double_clic_droit_sur_une_ligne_n_ouvre_rien(qtbot, preferences, dossiers):
    """`EPIC7-ARB-37` : aucune commande n'existe uniquement au clic droit.

    Trouve par la couche 2 de la revue de vague 2, reproduit a l'execution :
    `mouseDoubleClickEvent` emettait sans lire `evenement.button()`, donc un
    double-clic DROIT ouvrait le projet aussi surement qu'un double-clic
    gauche. La regle est mesuree et gardee sur le chutier
    (`test_chutier_frontieres.py`), elle ne l'etait pas ici -- le menu
    contextuel n'arrive qu'en 7.11.
    """
    _preferences_connaissant(preferences, dossiers.values())
    ecran = _construire(qtbot, preferences)
    # Cible en TROISIEME position alphabetique, jamais la premiere ligne.
    vise = next(
        widget for widget in ecran.widgets_de_ligne()
        if widget.ligne.nom == "Crepuscule"
    )
    ouvertures = []
    ecran.projet_ouvert.connect(ouvertures.append)

    vise.mouseDoubleClickEvent(
        _evenement_souris(
            vise, QEvent.Type.MouseButtonDblClick, Qt.MouseButton.RightButton
        )
    )
    assert ouvertures == [], "le double-clic droit a ouvert un projet"

    # Volet symetrique : le bouton GAUCHE ouvre toujours. Sans lui, un code
    # qui n'emettrait plus jamais passerait le test ci-dessus.
    vise.mouseDoubleClickEvent(
        _evenement_souris(
            vise, QEvent.Type.MouseButtonDblClick, Qt.MouseButton.LeftButton
        )
    )
    assert [ligne.nom for ligne in ouvertures] == ["Crepuscule"]


def test_le_clic_droit_sur_une_ligne_ne_la_designe_pas(qtbot, preferences, dossiers):
    """Meme regle sur le clic simple : le bouton droit ne designe pas."""
    _preferences_connaissant(preferences, dossiers.values())
    ecran = _construire(qtbot, preferences)
    vise = next(
        widget for widget in ecran.widgets_de_ligne()
        if widget.ligne.nom == "Crepuscule"
    )

    vise.mousePressEvent(
        _evenement_souris(
            vise, QEvent.Type.MouseButtonPress, Qt.MouseButton.RightButton
        )
    )
    assert ecran.index_selection is None

    vise.mousePressEvent(
        _evenement_souris(
            vise, QEvent.Type.MouseButtonPress, Qt.MouseButton.LeftButton
        )
    )
    assert ecran.index_selection is not None


def test_la_zone_de_liste_et_son_porteur_sont_peints_par_les_jetons(
    qtbot, preferences, dossiers
):
    """Le fond de la liste ne retombe jamais sur la palette par defaut.

    Trouve par capture de l'interface reelle a la revue de vague 2 : la
    regle `#liste-projets` ne peint que le `QScrollArea` lui-meme. Son
    viewport et le widget porteur qu'il contient sont deux autres widgets,
    qui retombaient sur la palette systeme et posaient un large panneau GRIS
    CLAIR au milieu d'une interface sombre -- sur la PREMIERE surface que
    voit un utilisateur, et en ecart direct a `DESIGN.md` (« fond neutre
    plat »).
    """
    _preferences_connaissant(preferences, dossiers.values())
    ecran = _construire(qtbot, preferences)

    # Le porteur est NOMME (un selecteur descendant mordrait sur les lignes).
    assert ecran._porteur.objectName() == "porteur-de-liste"
    feuille = ecran.styleSheet()
    assert "#porteur-de-liste" in feuille
    # ... et il est peint du meme neutre que la toile, jamais d'un litteral.
    canvas = jetons.COULEURS["surface-canvas"]
    for selecteur in ("#liste-projets", "#porteur-de-liste"):
        indice = feuille.index(selecteur)
        assert canvas in feuille[indice:indice + 200], (
            f"{selecteur} n'est pas peint de surface-canvas"
        )
    # Le viewport laisse passer le fond du porteur plutot que d'imposer le sien.
    assert not ecran.zone_de_liste.viewport().autoFillBackground()


def test_les_deux_dates_d_une_ligne_partagent_le_meme_format(
    qtbot, preferences, dossiers
):
    """`EPIC7-ARB-62`, arbitre par Egan le 2026-08-25.

    Trouve par capture de l'interface reelle a la revue de vague 2 : la ligne
    affichait « Cree le 2026-05-02T08:00:00Z   Modifie le 2026-08-25 06:49 ».
    La creation sortait verbatim du manifest (RFC3339 UTC), la modification
    etait formatee depuis le `mtime` -- deux formats sur la meme ligne, sur
    la premiere surface que voit un utilisateur.

    Ce test porte sur la PROPRIETE (meme forme des deux cotes) et pas sur une
    valeur, pour rester juste quel que soit le fuseau de la machine qui
    l'execute.
    """
    _preferences_connaissant(preferences, dossiers.values())
    ecran = _construire(qtbot, preferences)
    vise = next(
        widget for widget in ecran.widgets_de_ligne() if widget.ligne.nom == "Brume"
    )

    forme = re.compile(r"\b\d{4}-\d{2}-\d{2} \d{2}:\d{2}\b")
    for libelle in (vise.libelle_creation, vise.libelle_modification):
        assert forme.search(libelle.text()), libelle.text()
    # Plus rien du RFC3339 brut ne traverse jusqu'a l'ecran.
    assert "T" not in vise.libelle_creation.text().split("le ", 1)[-1]
    assert "Z" not in vise.libelle_creation.text()


def test_une_date_de_creation_illisible_est_rendue_telle_quelle(
    qtbot, preferences, dossiers, tmp_path
):
    """Une date qu'on ne sait pas formater reste une information.

    Volet symetrique du precedent : sans lui, un formatteur qui renverrait la
    chaine vide sur TOUTE entree passerait le test de forme ci-dessus (aucun
    libelle a verifier). Ici la valeur doit survivre au passage.
    """
    dossier = tmp_path / "travail" / "Bizarre"
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / depot_projets.NOM_FICHIER_PROJET).write_text(
        json.dumps(
            depot_projets.manifeste_minimal("bizarre", cree_le="pas-une-date")
        ),
        encoding="utf-8",
    )
    _preferences_connaissant(preferences, [dossier])
    ecran = _construire(qtbot, preferences)

    vise = ecran.widgets_de_ligne()[0]
    assert "pas-une-date" in vise.libelle_creation.text()


# ---------------------------------------------------------------------------
# Correctif du 2026-08-26 : la designation etait invisible
# ---------------------------------------------------------------------------


def _regle(feuille, selecteur):
    """Le corps `{ ... }` de la regle qui suit exactement `selecteur`.

    Chercher la couleur « quelque part apres le selecteur » (ce que fait un
    test voisin sur `#porteur-de-liste`, avec une fenetre de 200 caracteres)
    laisserait passer une couleur posee par la regle SUIVANTE. Ici la regle
    designee jouxte celle du dernier ouvert, qui porte deja l'accent : la
    fenetre glissante rendrait le test tautologique.
    """
    indice = feuille.index(selecteur)
    ouverture = feuille.index("{", indice)
    return feuille[ouverture + 1:feuille.index("}", ouverture)]


def test_la_ligne_designee_se_peint_a_l_accent(qtbot, preferences, dossiers):
    """« Ceci est selectionne » se dit a l'accent, et a rien d'autre.

    Defaut de terrain du 2026-08-26 : la designation ne changeait que le
    neutre de fond, de `surface-raised` a `surface-hover` -- 10/255 sur trois
    canaux, invisible. Egan : « on ne sait pas sur lequel on a clique ».
    `DESIGN.md` par. 293 reserve l'accent a cet emploi exact.
    """
    _preferences_connaissant(preferences, dossiers.values())
    ecran = _construire(qtbot, preferences)
    corps = _regle(ecran.styleSheet(), "QFrame[role='ligne'][designe='true']")

    assert jetons.COULEURS["accent"] in corps, (
        "la regle de designation ne porte pas l'accent : "
        f"{corps!r}"
    )
    # Le fond survole reste -- l'accent s'ajoute, il ne remplace pas.
    assert jetons.COULEURS["surface-hover"] in corps


def test_designer_une_ligne_ne_la_fait_pas_sauter(qtbot, preferences, dossiers):
    """La bordure d'accent prend sa place des le repos.

    Volet symetrique du precedent, et il n'est pas decoratif : une bordure
    posee sur les quatre cotes par la seule regle `[designe='true']` peindrait
    bien l'accent -- donc passerait le test ci-dessus -- tout en decalant la
    ligne de 2 px au moindre clic. La regle de repos doit deja reserver la
    MEME largeur, sur les quatre cotes.
    """
    _preferences_connaissant(preferences, dossiers.values())
    ecran = _construire(qtbot, preferences)
    feuille = ecran.styleSheet()
    largeur = jetons.ESPACEMENTS["1"]

    repos = _regle(feuille, "QFrame[role='ligne'] ")
    designee = _regle(feuille, "QFrame[role='ligne'][designe='true']")

    # `border:` et non `border-left:` -- les quatre cotes, des le repos.
    assert f"border: {largeur}px solid {jetons.COULEURS['surface-raised']}" in repos
    assert f"border: {largeur}px solid {jetons.COULEURS['accent']}" in designee


def test_la_selection_du_chutier_se_peint_aussi_a_l_accent(qtbot):
    """Meme defaut, meme correctif, sur l'autre surface qui designe.

    Le chutier peignait sa selection du meme neutre invisible. L'accent y
    passe en TRAIT et non en aplat : `jetons` interdit le glyphe sur une
    chromie pleine (plancher 4,5:1), et le tient pour un trait (3:1).

    **Ce que ce test mesurait, et ce qu'il mesure depuis le 2026-08-27.** Il
    lisait l'accent dans `QTreeWidget::item:selected` de la feuille de style.
    Cette redaction etait justement le defaut suivant : une feuille de style
    ne sait pas distinguer les colonnes, donc la regle peignait **une cellule
    sur trois** de la ligne -- trois traits bleus, ce qu'Egan a lu comme
    « 2 niveaux de selection » (`EPIC7-ARB-94`). L'accent vit desormais dans
    un delegue, et l'assertion porte sur ce qui compte vraiment : **quelle
    colonne recoit le trait**. C'est une garantie plus forte que l'ancienne,
    pas une garantie deplacee.
    """
    from mixed_media_utility.gui import chutier as _chutier

    # Les DEUX variantes : le chutier et le panneau d'arborescence ne
    # partagent ni fond ni couleur de texte, et leurs feuilles sont
    # construites par deux branches distinctes -- corriger l'une seule est
    # exactement l'erreur que ce test doit voir.
    from mixed_media_utility.gui import modele_chutier as _modele

    # Deux rushes DISTINGUABLES, et la cible n'est pas le premier : un lisere
    # peint sur « la ligne courante » quelle qu'elle soit passerait sinon.
    racines = (
        _modele.Noeud(type=_modele.TYPE_RUSH, identifiant="rush-alpha"),
        _modele.Noeud(type=_modele.TYPE_RUSH, identifiant="rush-beta"),
    )

    for montre_les_signes in (True, False):
        arbre = _chutier.ArbreDeChutier(
            catalogue.CHAINES, montre_les_signes=montre_les_signes
        )
        qtbot.addWidget(arbre)
        arbre.poser(racines)
        delegue = arbre.itemDelegate()
        assert isinstance(delegue, _chutier.LisereDeSelection), montre_les_signes

        # La ligne selectionnee recoit le trait, et sur UNE colonne : celle du
        # libelle. On interroge le delegue plutot que la feuille de style,
        # parce que c'est lui qui decide desormais -- et parce que c'est
        # justement la colonne qui etait le defaut.
        index = arbre.indexFromItem(
            arbre.element("rush-beta"), _chutier.COLONNE_LIBELLE
        )
        peintes = []
        for colonne in range(arbre.columnCount()):
            option = QStyleOptionViewItem()
            option.state = QStyle.StateFlag.State_Selected
            if delegue.peint_le_lisere(option, index.siblingAtColumn(colonne)):
                peintes.append(colonne)
        assert peintes == [_chutier.COLONNE_LIBELLE], montre_les_signes

        # En TRAIT, jamais en aplat sous le texte : la feuille ne pose aucun
        # fond d'accent sur la selection.
        corps = _regle(arbre.styleSheet(), "QTreeWidget::item:selected")
        assert f"background: {jetons.COULEURS['accent']}" not in corps

        # Et la place du trait est reservee des le repos : pas de saut.
        assert "border-left:" in _regle(arbre.styleSheet(), "QTreeWidget::item ")


# ---------------------------------------------------------------------------
# « Retirer de la liste » (correctif du 2026-08-26)
# ---------------------------------------------------------------------------


def test_retirer_ote_LA_ligne_visee_et_persiste(qtbot, preferences, dossiers):
    """Le clic sur la croix d'une ligne retire CELLE-LA, et le retrait tient
    au relancement -- les preferences sont reecrites dans la foulee.

    Cible en TROISIEME position par ordre alphabetique.
    """
    _preferences_connaissant(preferences, dossiers.values())
    ecran = _construire(qtbot, preferences)
    ecran.selecteur_de_tri.setCurrentIndex(0)

    vise = next(
        widget
        for widget in ecran.widgets_de_ligne()
        if widget.ligne.nom == "Crepuscule"
    )
    vise.bouton_retirer.click()

    assert _noms(ecran) == ["Aurore", "Brume"]
    # Le relancement voit la meme chose : c'est la persistance qui est mesuree,
    # pas seulement l'etat en memoire.
    assert _noms(_construire(qtbot, preferences)) == ["Aurore", "Brume"]


def test_retirer_ne_touche_AUCUN_fichier(qtbot, preferences, dossiers):
    """La frontiere du geste, et la promesse portee par son libelle :
    « les fichiers du projet ne sont pas touches »."""
    _preferences_connaissant(preferences, dossiers.values())
    ecran = _construire(qtbot, preferences)
    vise = next(
        widget
        for widget in ecran.widgets_de_ligne()
        if widget.ligne.nom == "Brume"
    )
    dossier = Path(vise.ligne.chemin)
    avant = sorted(chemin.name for chemin in dossier.iterdir())

    vise.bouton_retirer.click()

    assert dossier.is_dir()
    assert sorted(chemin.name for chemin in dossier.iterdir()) == avant
    assert (dossier / depot_projets.NOM_FICHIER_PROJET).is_file()
    # Et les deux autres dossiers non plus ne sont pas touches.
    for autre in dossiers.values():
        assert Path(autre).is_dir()


def test_une_ligne_en_erreur_porte_AUSSI_la_croix_de_retrait(
    qtbot, tmp_path, preferences, dossiers
):
    """C'est le cas qui exige le geste, pas celui qui s'en dispense.

    Une ligne en erreur ne se DESIGNE pas (test plus haut) : un retrait
    attache a la designation ne l'atteindrait jamais, et un dossier de projet
    supprime a la main resterait en ligne d'erreur pour toujours. C'est
    exactement ce qu'Egan a rencontre au premier essai de terrain.
    """
    inconnue = _projet_de_version_inconnue(tmp_path / "casse")
    _preferences_connaissant(preferences, [dossiers["Aurore"], inconnue])
    ecran = _construire(qtbot, preferences)

    cassee = next(
        widget
        for widget in ecran.widgets_de_ligne()
        if widget.ligne.nom == "Version inconnue"
    )
    assert cassee.ligne.ouvrable is False
    cassee.bouton_retirer.click()

    assert _noms(ecran) == ["Aurore"]


def test_retirer_ne_demande_aucune_confirmation(qtbot, preferences, dossiers, monkeypatch):
    """Aucune modale : le geste ne touche pas au disque et se defait en
    redesignant le dossier. Une confirmation ferait croire l'inverse.

    Mesure par interception de `QMessageBox.exec` -- une modale reellement
    ouverte bloquerait le banc headless, donc on la fait echouer bruyamment
    plutot que d'attendre.
    """
    from PySide6.QtWidgets import QMessageBox

    def _interdit(*args, **kwargs):
        raise AssertionError("une modale de confirmation s'est ouverte")

    monkeypatch.setattr(QMessageBox, "exec", _interdit)
    monkeypatch.setattr(QMessageBox, "exec_", _interdit, raising=False)

    _preferences_connaissant(preferences, dossiers.values())
    ecran = _construire(qtbot, preferences)
    ecran.widgets_de_ligne()[0].bouton_retirer.click()

    assert len(ecran.widgets_de_ligne()) == 2


def test_le_libelle_de_retrait_dit_que_les_fichiers_ne_sont_pas_touches(
    qtbot, preferences, dossiers
):
    """La parenthese de la spine (`EXPERIENCE.md`, inventaire des menus
    contextuels) est portee jusqu'a l'utilisatrice, pas seulement au code."""
    _preferences_connaissant(preferences, dossiers.values())
    ecran = _construire(qtbot, preferences)
    bouton = ecran.widgets_de_ligne()[0].bouton_retirer

    for porte in (bouton.toolTip(), bouton.accessibleName()):
        assert catalogue.CHAINES["ecran-projet-retirer"] in porte
        assert catalogue.CHAINES["ecran-projet-retirer-detail"] in porte


def test_retirer_le_dernier_projet_rend_l_ecran_vide(qtbot, preferences, dossiers):
    """Le chemin qu'Egan demande : repartir a zero, sans passer par les
    reglages de la machine. L'etat vide est celui du tout premier lancement."""
    _preferences_connaissant(preferences, dossiers.values())
    ecran = _construire(qtbot, preferences)

    while ecran.widgets_de_ligne():
        ecran.widgets_de_ligne()[0].bouton_retirer.click()

    assert _noms(ecran) == []
    assert ecran.libelle_liste_vide.isVisible() or not ecran.isVisible()
    assert preferences.projets_connus() == ()
