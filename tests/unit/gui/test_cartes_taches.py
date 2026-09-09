# -*- coding: utf-8 -*-
"""Story 7.3, AC 3 -- deux etats honnetes sur les cartes, et rien de plus.

Ce banc mesure : les trois libelles d'etat viennent du catalogue, le motif
d'echec est **exactement** `str(exc)` du coeur (P9), un code du coeur n'a
**pas** d'entree au catalogue, et **aucun** libelle de progression n'existe --
ni jauge, ni pourcentage, ni duree.

La carte d'echec passe par le VRAI chemin : une vraie fonction du coeur
(`scan_detect.run_scan_detect`) est soumise au vrai `Executeur` sur une entree
illisible, et c'est l'exception qu'elle leve qui est comparee au texte
affiche. Un test qui poserait le motif a la main ne mesurerait que lui-meme.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from mixed_media_utility import scan_detect
from mixed_media_utility.gui import cartes_taches, catalogue, executeur

MARQUE = "‹M›"


@pytest.fixture
def panneau(qtbot):
    surface = cartes_taches.PanneauDeTaches()
    qtbot.addWidget(surface)
    return surface


def _litteraux_hors_docstring(chemin: Path) -> list[str]:
    """Les chaines litterales d'un module, **docstrings exclues**.

    Un docstring a le droit de nommer ce que le module ne fait PAS -- c'est
    meme ce qui rend l'interdit lisible. Le confondre avec un libelle rendrait
    la frontiere inapplicable, ou pire : ferait supprimer l'explication pour
    faire passer un test.
    """
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    docstrings = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                              ast.ClassDef)):
            corps = getattr(noeud, "body", [])
            if (corps and isinstance(corps[0], ast.Expr)
                    and isinstance(corps[0].value, ast.Constant)
                    and isinstance(corps[0].value.value, str)):
                docstrings.add(id(corps[0].value))
    return [
        noeud.value for noeud in ast.walk(arbre)
        if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str)
        and id(noeud) not in docstrings
    ]


# ---------------------------------------------------------------------------
# Les trois etats viennent du catalogue
# ---------------------------------------------------------------------------


def test_les_etats_des_cartes_viennent_du_catalogue(qtbot):
    marque = {cle: MARQUE + valeur for cle, valeur in catalogue.CHAINES.items()}
    panneau = cartes_taches.PanneauDeTaches(marque)
    qtbot.addWidget(panneau)
    carte = panneau.ajouter("pile-alpha")

    attendus = {
        executeur.EN_COURS: "etat-tache-en-cours",
        executeur.TERMINEE: "etat-tache-terminee",
        executeur.ECHOUEE: "etat-tache-echouee",
    }
    assert carte.texte_de_l_etat() == MARQUE + catalogue.CHAINES[
        attendus[executeur.EN_COURS]]
    for etat, cle in attendus.items():
        carte.refleter(etat)
        assert carte.texte_de_l_etat() == MARQUE + catalogue.CHAINES[cle]
        assert carte.etat == etat
    # Les trois libelles sont DISTINCTS : trois etats rendus par un seul
    # libelle passeraient les assertions ci-dessus si le catalogue les
    # confondait.
    assert len({catalogue.CHAINES[cle] for cle in attendus.values()}) == 3


def test_un_etat_inconnu_leve_plutot_que_de_s_afficher_vide(panneau):
    carte = panneau.ajouter("pile-alpha")
    with pytest.raises(ValueError):
        carte.refleter("etat-invente")


# ---------------------------------------------------------------------------
# Le motif d'echec est celui du coeur, lu et jamais recopie (P9)
# ---------------------------------------------------------------------------


def test_le_motif_d_echec_est_celui_du_coeur(qtbot, tmp_path, panneau):
    """Le VRAI chemin : une vraie fonction du coeur, un vrai executeur."""
    inexistant = tmp_path / "nulle-part"
    projet = tmp_path / "projet"

    # Ce que le coeur dit, mesure a la source.
    with pytest.raises(Exception) as capture:
        scan_detect.run_scan_detect(projet, inexistant, dpi=300)
    motif_du_coeur = str(capture.value)
    assert motif_du_coeur

    carte = panneau.ajouter(inexistant.name)
    file_de_taches = executeur.Executeur()
    tache = file_de_taches.soumettre(
        scan_detect.run_scan_detect,
        {"project_dir": tmp_path / "projet-bis", "scan_path": inexistant,
         "dpi": 300},
    )
    tache.echouee.connect(
        lambda motif: carte.refleter(executeur.ECHOUEE, motif))
    qtbot.waitUntil(lambda: carte.etat == executeur.ECHOUEE, timeout=5000)

    # **Exactement** le texte du coeur : ni prefixe, ni suffixe, ni traduction.
    assert carte.texte_du_motif() == motif_du_coeur
    assert carte.texte_du_motif() == tache.motif


def test_un_code_du_coeur_ne_passe_pas_par_le_catalogue(panneau):
    """Le motif s'affiche verbatim et n'a AUCUNE entree au catalogue."""
    codes = (
        "Chemin de scan introuvable: /nulle/part",
        scan_detect.ARRET_AUCUNE_PLANCHE_IDENTIFIEE,
        scan_detect.ARRET_PILE_DE_CALIBRATION_SEULE,
    )
    carte = panneau.ajouter("pile-alpha")
    for code in codes:
        carte.refleter(executeur.ECHOUEE, code)
        assert carte.texte_du_motif() == code
        assert code not in catalogue.CHAINES
        assert code not in catalogue.CHAINES.values()


# ---------------------------------------------------------------------------
# Zero libelle de progression, tant qu'aucune MESURE n'existe (EPIC7-ARB-67)
# ---------------------------------------------------------------------------

#: Ce qu'aucun libelle ne doit porter tant qu'aucune mesure reelle n'existe sur
#: ce chemin. `EPIC7-ARB-67` a leve la moitie PRODUIT du differe -- le temps se
#: calcule et sera affiche -- mais pas celle-ci : « aucun temps n'est affiche
#: avant qu'une mesure reelle existe ». La story de coeur 5.28 emet sur les
#: taches d'extraction, jamais sur `scan detect` ; c'est 7.6 qui affichera.
_INTERDITS_DE_PROGRESSION = ("temps restant", "restant", "ETA", "%")

#: Les cles de catalogue de CETTE surface -- la file, les cartes, l'atelier.
#: Le balayage y est borne, et pas au catalogue entier, parce qu'un `%` n'est
#: pas en soi un libelle de progression : `vue-taille-reelle` (« 100 % »),
#: pose par la story 7.4, est une ECHELLE d'affichage. L'interdit
#: d'`EPIC7-ARB-67` porte sur ce que la tache dit de son avancement, pas sur
#: tout usage du signe. Borner ici plutot que retirer le signe de la liste :
#: un `%` sur une carte de tache resterait un pourcentage d'avancement.
_PREFIXES_DE_LA_SURFACE = (
    "etat-tache-", "carte-", "panneau-taches-", "atelier-scan-", "zone-tampon-")


def _chaines_de_la_surface():
    chaines = {
        cle: valeur for cle, valeur in catalogue.CHAINES.items()
        if cle.startswith(_PREFIXES_DE_LA_SURFACE)
    }
    # Le balayage porte sur quelque chose : sans cette garde, un renommage de
    # prefixe rendrait la frontiere verte et vide.
    assert len(chaines) > 20, chaines
    return chaines


def test_zero_temps_restant_dans_les_libelles():
    fautifs = {
        cle: valeur for cle, valeur in _chaines_de_la_surface().items()
        if any(mot in valeur for mot in _INTERDITS_DE_PROGRESSION)
    }
    assert fautifs == {}, f"libelle de progression au catalogue : {fautifs}"

    source = Path(cartes_taches.__file__)
    litteraux = _litteraux_hors_docstring(source)
    trouves = [
        (mot, texte) for texte in litteraux
        for mot in _INTERDITS_DE_PROGRESSION if mot in texte
    ]
    assert trouves == [], f"libelle de progression dans les cartes : {trouves}"
    # Aucune jauge non alimentee : ni le widget, ni son import.
    texte_du_module = source.read_text(encoding="utf-8")
    assert "QProgressBar" not in texte_du_module

    # Temoin : le balayage porte sur quelque chose. Sans lui, un module vide
    # ou un catalogue renomme passerait tout aussi vert.
    assert len(litteraux) > 10, len(litteraux)
    assert len(_chaines_de_la_surface()) > 20


def test_la_frontiere_de_progression_mord_vraiment():
    fautif = "Terminée dans 12 s — 40 % (ETA), temps restant"
    trouves = [mot for mot in _INTERDITS_DE_PROGRESSION if mot in fautif]
    assert set(trouves) == set(_INTERDITS_DE_PROGRESSION), trouves


# ---------------------------------------------------------------------------
# La carte terminee nomme son objet ET son issue -- sur DEUX cartes
# ---------------------------------------------------------------------------


def test_la_carte_terminee_nomme_son_objet_et_son_issue(panneau):
    """Deux cartes, deux objets, **deux issues differentes**.

    La cible est la SECONDE : une carte qui rendrait toujours la premiere ne
    se demasquerait pas sur une collection uniforme.
    """
    premiere = panneau.ajouter("pile-alpha")
    seconde = panneau.ajouter("planche-beta.pdf")
    premiere.refleter(executeur.TERMINEE)
    seconde.refleter(executeur.ECHOUEE, "Chemin de scan introuvable: /x")

    assert panneau.cartes() == (premiere, seconde)
    assert "pile-alpha" in premiere.texte_de_l_objet()
    assert "planche-beta.pdf" in seconde.texte_de_l_objet()
    # Les deux issues sont differentes, et chacune est sur SA carte.
    assert premiere.texte_de_l_etat() == catalogue.CHAINES["etat-tache-terminee"]
    assert seconde.texte_de_l_etat() == catalogue.CHAINES["etat-tache-echouee"]
    assert premiere.texte_du_motif() == ""
    assert seconde.texte_du_motif() == "Chemin de scan introuvable: /x"


def test_une_carte_nomme_le_lot_quand_le_coeur_en_a_trouve_un(panneau):
    carte = panneau.ajouter("pile-alpha")
    carte.nommer("pile-alpha", "lot-scan-18")
    texte = carte.texte_de_l_objet()
    assert "pile-alpha" in texte and "lot-scan-18" in texte
    assert texte == catalogue.CHAINES["carte-objet-lot"].format(
        objet="pile-alpha", lot="lot-scan-18")
