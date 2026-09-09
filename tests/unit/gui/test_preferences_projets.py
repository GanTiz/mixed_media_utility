# -*- coding: utf-8 -*-
"""Preferences utilisateur de l'ecran de projet (story 7.1, Task 3).

Liste connue, epingles, dernier ouvert : trois donnees qui suivent
l'utilisateur, pas le film (`EPIC7-ARB-33`). Aucune n'entre dans un fichier
de projet, aucune n'entre dans le depot.

Tous les tests injectent un ``QSettings`` en format INI dans un dossier
TEMPORAIRE : la suite n'ecrit jamais dans les reglages reels de la machine
-- un test qui polluerait le vrai support serait vert chez son auteur et
rouge partout ailleurs.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QSettings

from mixed_media_utility.gui.preferences_projets import PreferencesProjets


@pytest.fixture
def preferences(tmp_path):
    reglages = QSettings(str(tmp_path / "reglages.ini"), QSettings.Format.IniFormat)
    return PreferencesProjets(reglages)


def test_une_preference_neuve_ne_memorise_rien(preferences):
    assert preferences.projets_connus() == ()
    assert preferences.epingles() == ()
    assert preferences.dernier_ouvert() is None


def test_la_liste_connue_fait_l_aller_retour(tmp_path, preferences):
    """Regle des fabriques : DEUX chemins distinguables, et l'ORDRE est
    verifie -- une serialisation qui rendrait un ensemble non ordonne
    passerait un aller-retour a un seul element."""
    chemins = [str(tmp_path / "projet-a"), str(tmp_path / "projet-b")]

    preferences.definir_projets_connus(chemins)
    preferences.enregistrer()

    assert list(preferences.projets_connus()) == chemins


def test_une_liste_d_un_seul_element_reste_une_liste(tmp_path, preferences):
    """Le piege que la serialisation JSON evite : le type liste de
    ``QSettings`` rend une CHAINE NUE quand la liste ne compte qu'un
    element. Ce cas-la, c'est le premier lancement d'une operatrice."""
    unique = str(tmp_path / "projet-unique")

    preferences.definir_projets_connus([unique])
    preferences.enregistrer()

    connus = preferences.projets_connus()
    assert connus == (unique,)
    assert not isinstance(connus, str)


def test_les_epingles_font_l_aller_retour(tmp_path, preferences):
    epingles = [str(tmp_path / "projet-b"), str(tmp_path / "projet-c")]

    preferences.definir_epingles(epingles)
    preferences.enregistrer()

    assert list(preferences.epingles()) == epingles


def test_le_dernier_ouvert_fait_l_aller_retour_et_se_remet_a_neant(
    tmp_path, preferences
):
    chemin = str(tmp_path / "projet-b")

    preferences.definir_dernier_ouvert(chemin)
    preferences.enregistrer()
    assert preferences.dernier_ouvert() == chemin

    preferences.definir_dernier_ouvert(None)
    preferences.enregistrer()
    assert preferences.dernier_ouvert() is None


def test_les_trois_donnees_ne_se_marchent_pas_dessus(tmp_path, preferences):
    """Elles vivent dans trois cles distinctes : ecrire l'une ne doit pas
    effacer les deux autres."""
    preferences.definir_projets_connus([str(tmp_path / "a"), str(tmp_path / "b")])
    preferences.definir_epingles([str(tmp_path / "b")])
    preferences.definir_dernier_ouvert(str(tmp_path / "a"))
    preferences.enregistrer()

    assert len(preferences.projets_connus()) == 2
    assert preferences.epingles() == (str(tmp_path / "b"),)
    assert preferences.dernier_ouvert() == str(tmp_path / "a")


def test_un_reglage_corrompu_se_lit_comme_rien_de_memorise(tmp_path):
    """Un support abime ne fait PAS tomber le premier ecran du produit.

    C'est la meme famille d'exigence que l'AC 4 (« jamais un crash au
    premier ecran que voit un utilisateur en panne »), appliquee au support
    des preferences plutot qu'au fichier de projet.
    """
    fichier = tmp_path / "reglages.ini"
    reglages = QSettings(str(fichier), QSettings.Format.IniFormat)
    reglages.setValue("projets/connus-v1", "{ceci n'est pas du JSON")
    reglages.sync()

    preferences = PreferencesProjets(
        QSettings(str(fichier), QSettings.Format.IniFormat)
    )

    assert preferences.projets_connus() == ()


def test_les_preferences_ne_touchent_a_aucun_dossier_de_projet(tmp_path):
    """« Aucune ecriture dans un projet a l'ouverture » : ouvrir lit, ne
    modifie pas. Le support des preferences est ailleurs, et on le mesure."""
    dossier_projet = tmp_path / "projet"
    dossier_projet.mkdir()
    fichier = tmp_path / "reglages.ini"
    preferences = PreferencesProjets(
        QSettings(str(fichier), QSettings.Format.IniFormat)
    )

    preferences.definir_projets_connus([str(dossier_projet)])
    preferences.definir_dernier_ouvert(str(dossier_projet))
    preferences.enregistrer()

    assert list(dossier_projet.iterdir()) == []
