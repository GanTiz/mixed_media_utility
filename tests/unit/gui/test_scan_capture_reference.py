# -*- coding: utf-8 -*-
"""Story 7.4, AC 7 -- la capture de reference du mode PDF, et son comparateur.

Cette AC **cree** le moyen de verification K du depot : aucun outillage de
capture ou de comparaison d'image n'existait au ``baseline_commit``.

A la vague 3 elle n'a pas de regression a detecter. Elle est satisfaite quand
la reference existe, que le comparateur tourne, **et que le banc echoue
franchement si la reference est absente ou illisible** -- jamais un ``skip``,
qui se lirait comme un vert.
"""

import ast
from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QImage

import capture_scan_mode_pdf as scene
import capture_visuelle
from mixed_media_utility.gui import surimpressions

_RACINE_TESTS = Path(__file__).resolve().parents[2]


@pytest.fixture
def contenu(qtbot):
    widget = scene.contenu_de_reference()
    qtbot.addWidget(widget)
    return widget


# ---------------------------------------------------------------------------
# (K) -- la capture neuve est identique a la reference versionnee
# ---------------------------------------------------------------------------


def test_la_capture_neuve_est_identique_a_la_reference(contenu):
    ecart = capture_visuelle.comparer(
        capture_visuelle.capturer(contenu), scene.NOM_DE_REFERENCE
    )
    assert ecart.identiques, f"le mode PDF a change : {ecart}"


def test_la_capture_couvre_LES_TROIS_FAMILLES_de_traits(contenu):
    """La reference ne vaut que par ce qu'elle a dans le cadre."""
    familles = {trait.famille for trait in contenu.plan}
    assert familles == set(surimpressions.FAMILLES), familles
    # Et chaque famille y est bien representee par au moins un trait.
    for famille in surimpressions.FAMILLES:
        assert any(trait.famille == famille for trait in contenu.plan)


# ---------------------------------------------------------------------------
# (K), symetrique -- le test qui prouve que le test mesure quelque chose
# ---------------------------------------------------------------------------


def test_une_surimpression_deplacee_d_UN_pixel_est_refusee(qtbot):
    """Sans ce symetrique, une tolerance trop large rendrait l'AC tautologique.

    C'est le defaut trouve en 5.9 sur la constante centrale de la
    calibration, transpose ici : une comparaison qui ne sait que dire
    « identique » ne mesure rien.
    """
    decale = scene.contenu_de_reference(decalage_de_zone=1)
    qtbot.addWidget(decale)
    ecart = capture_visuelle.comparer(
        capture_visuelle.capturer(decale), scene.NOM_DE_REFERENCE
    )
    assert not ecart.identiques, (
        f"un decalage d'un pixel passe la comparaison : {ecart} -- la "
        "tolerance est trop large et l'AC serait tautologique"
    )
    assert ecart.pixels_differents > 0


def test_le_comparateur_mesure_un_ecart_croissant_avec_le_decalage(qtbot):
    """Il MESURE, il ne rend pas un booleen : deux decalages ne se valent pas."""
    ecarts = []
    for decalage in (1, 4):
        widget = scene.contenu_de_reference(decalage_de_zone=decalage)
        qtbot.addWidget(widget)
        ecarts.append(
            capture_visuelle.comparer(
                capture_visuelle.capturer(widget), scene.NOM_DE_REFERENCE
            ).pixels_differents
        )
    assert ecarts[1] > ecarts[0] > 0


def test_une_divergence_etendue_de_faible_amplitude_est_refusee_par_la_proportion(
    monkeypatch,
):
    """F10 -- ``TOLERANCE_PROPORTION_PIXELS`` doit mordre par SON axe.

    Avant ce correctif, ``pixels_differents`` ne comptait que les pixels
    dont l'ecart depassait deja ``TOLERANCE_ECART_CANAL_MAX`` : des que
    l'axe canal passait, l'axe proportion valait donc toujours zero, et
    ``TOLERANCE_PROPORTION_PIXELS`` ne changeait le verdict d'AUCUNE paire
    d'images -- exactement ce que le mutant M17
    (``TOLERANCE_PROPORTION_PIXELS = 1.0``) laissait invisible.

    Ce cas construit une divergence de faible AMPLITUDE (delta 3, sous les
    8 de ``TOLERANCE_ECART_CANAL_MAX``) mais ETENDUE a la moitie de
    l'image -- le regime exact du symetrique de l'AC 7 (un deplacement de
    surimpression change toute la longueur d'un trait), isole de tout
    widget reel pour ne mesurer QUE le comparateur.
    """
    largeur, hauteur = 100, 100
    reference = QImage(largeur, hauteur, QImage.Format.Format_RGB888)
    reference.fill(0)
    modifiee = QImage(largeur, hauteur, QImage.Format.Format_RGB888)
    modifiee.fill(0)
    delta_faible = 3
    assert delta_faible <= capture_visuelle.TOLERANCE_ECART_CANAL_MAX
    for y in range(hauteur // 2):
        for x in range(largeur):
            modifiee.setPixelColor(
                x, y, QColor(delta_faible, delta_faible, delta_faible)
            )
    ecart = capture_visuelle.ecart(reference, modifiee)
    # L'axe CANAL, SEUL, dirait deja "identique" -- la preuve qu'on est bien
    # en train de mesurer l'axe proportion, et pas un doublon du canal.
    assert ecart.ecart_canal_max <= capture_visuelle.TOLERANCE_ECART_CANAL_MAX
    assert ecart.proportion_pixels_differents == pytest.approx(0.5, abs=0.01)
    assert not ecart.identiques, (
        "une divergence etendue mais de faible amplitude passe la "
        f"comparaison : {ecart}"
    )
    # Desserrer SEULEMENT l'axe canal ne doit RIEN changer au verdict :
    # sinon ce cas mesurerait encore le mauvais axe.
    monkeypatch.setattr(capture_visuelle, "TOLERANCE_ECART_CANAL_MAX", 255)
    ecart_canal_desserre = capture_visuelle.ecart(reference, modifiee)
    assert not ecart_canal_desserre.identiques, (
        "desserrer TOLERANCE_ECART_CANAL_MAX suffit a faire passer ce cas : "
        "il mesure l'axe canal, pas l'axe proportion"
    )


def test_deux_captures_de_tailles_differentes_sont_totalement_differentes():
    """Un recadrage silencieux serait un faux vert."""
    petite = QImage(10, 10, QImage.Format.Format_RGB888)
    petite.fill(0)
    grande = QImage(20, 20, QImage.Format.Format_RGB888)
    grande.fill(0)
    ecart = capture_visuelle.ecart(petite, grande)
    assert not ecart.identiques
    assert ecart.proportion_pixels_differents == 1.0


# ---------------------------------------------------------------------------
# Reference absente ou illisible -> ECHEC DUR, jamais un skip
# ---------------------------------------------------------------------------


def test_une_reference_absente_est_un_echec_dur_et_jamais_un_skip():
    with pytest.raises(capture_visuelle.CaptureIntrouvable) as refus:
        capture_visuelle.charger_reference("aucune-reference-de-ce-nom")
    assert "absente" in str(refus.value)
    # `CaptureIntrouvable` derive d'`AssertionError` : elle FAIT ECHOUER un
    # test, elle ne le saute pas. Un `Skipped` se lirait comme un vert.
    assert issubclass(capture_visuelle.CaptureIntrouvable, AssertionError)
    assert not issubclass(
        capture_visuelle.CaptureIntrouvable, pytest.skip.Exception
    )


def test_une_reference_illisible_est_un_echec_dur(tmp_path, monkeypatch):
    corrompue = tmp_path / "captures-gui"
    corrompue.mkdir()
    (corrompue / "corrompue.png").write_bytes(b"ceci n'est pas un PNG")
    monkeypatch.setattr(capture_visuelle, "DOSSIER_REFERENCES", corrompue)
    with pytest.raises(capture_visuelle.CaptureIntrouvable) as refus:
        capture_visuelle.charger_reference("corrompue")
    assert "illisible" in str(refus.value)


def test_la_reference_ne_se_regenere_jamais_au_passage_d_un_test():
    """Une reference qui se regenere toute seule ne compare plus rien.

    Mesure : aucun module de TEST n'appelle l'ecriture de reference. Seule la
    commande explicite le fait.
    """
    dossier = Path(__file__).resolve().parent
    fautifs = []
    for source in sorted(dossier.glob("test_*.py")):
        arbre = ast.parse(source.read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.Call):
                continue
            fonction = noeud.func
            # Scope STRICT : les deux ecritures de reference de l'outillage
            # de capture, et elles seules. « enregistrer » est un verbe
            # courant du depot (les preferences de projet en ont un), et un
            # grep par nom nu accuserait sept tests de 7.1 sans rapport.
            if (
                isinstance(fonction, ast.Attribute)
                and getattr(fonction.value, "id", "") == "capture_visuelle"
                and fonction.attr in ("enregistrer", "_regenerer")
            ):
                fautifs.append(f"{source.name}:{fonction.attr}")
    assert fautifs == [], f"regeneration declenchee par un test : {fautifs}"
    # Le symetrique, sur un temoin : le grep echoue vraiment quand il doit.
    temoin = ast.parse("capture_visuelle.enregistrer(image, 'x')\n")
    trouve = [
        noeud.func.attr for noeud in ast.walk(temoin)
        if isinstance(noeud, ast.Call)
        and isinstance(noeud.func, ast.Attribute)
        and getattr(noeud.func.value, "id", "") == "capture_visuelle"
    ]
    assert trouve == ["enregistrer"]
    # Et la commande refuse d'ecrire sans son option explicite.
    source = (dossier / "capture_visuelle.py").read_text(encoding="utf-8")
    assert "--regenerer" in source
    assert 'if "--regenerer" not in sys.argv[1:]' in source


# ---------------------------------------------------------------------------
# EPIC7-ARB-65 -- une seule implementation, dans tout `tests/`
# ---------------------------------------------------------------------------

#: Les appels qui SIGNENT une comparaison d'image de capture. Un module de
#: `tests/` qui les porte definit une comparaison ; il ne doit y en avoir
#: qu'un.
_SIGNATURES_DE_COMPARAISON = ("grab", "constBits", "sizeInBytes")


def _modules_definissant_une_comparaison(racine):
    definisseurs = []
    for source in sorted(racine.rglob("*.py")):
        arbre = ast.parse(source.read_text(encoding="utf-8"))
        appels = set()
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Call):
                appels.add(
                    noeud.func.attr
                    if isinstance(noeud.func, ast.Attribute)
                    else getattr(noeud.func, "id", "")
                )
        if set(_SIGNATURES_DE_COMPARAISON) <= appels:
            definisseurs.append(source.name)
    return definisseurs


def test_une_seule_implementation_de_comparaison():
    """« Aucune story ulterieure ne construit un second mecanisme. »"""
    definisseurs = _modules_definissant_une_comparaison(_RACINE_TESTS)
    assert definisseurs == ["capture_visuelle.py"], definisseurs


def test_le_grep_d_unicite_MORD_sur_un_second_module_temoin(tmp_path):
    """Le symetrique : sans lui, le grep pourrait etre vert et vide."""
    (tmp_path / "capture_visuelle.py").write_text(
        "def f(w, i):\n"
        "    a = w.grab()\n"
        "    b = i.constBits()\n"
        "    return i.sizeInBytes()\n",
        encoding="utf-8",
    )
    assert _modules_definissant_une_comparaison(tmp_path) == [
        "capture_visuelle.py"
    ]
    (tmp_path / "second_comparateur.py").write_text(
        "def g(w, i):\n"
        "    a = w.grab()\n"
        "    b = i.constBits()\n"
        "    return i.sizeInBytes()\n",
        encoding="utf-8",
    )
    assert _modules_definissant_une_comparaison(tmp_path) == [
        "capture_visuelle.py",
        "second_comparateur.py",
    ]
