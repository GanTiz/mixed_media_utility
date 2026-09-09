# Story 7.0, AC 1 -- la pile de la machine de reference est epinglee.
#
# Le test est DECLARATIF : il verifie que requirements.txt porte les
# epinglages que le depot DECLARE, et NON les versions de l'interpreteur du
# conteneur de session. Motif, consigne d'Egan du 2026-08-24 : un test
# d'interpreteur fabriquerait un faux rouge permanent de plus (il y en a deja 6
# documentes dans deferred-work.md).
#
# PORTE le 2026-09-07, apres le commit `5635d70a`. Les quatre epinglages que ce
# banc nommait -- numpy<2, opencv-contrib 4.10, le METAPAQUET PySide6, et le
# plancher macOS -- ont tous change de forme, et ce banc etait reste en arriere :
# quatre rouges dans la non-regression large. C'est le defaut que CLAUDE.md nomme
# a la liaison, « un module porte sans sa mesure », et il se lit ici du cote de
# la mesure. Ce qui a bouge, et sur quelle mesure :
#
#   numpy>=1.24,<2  ->  numpy>=2.0            l'intersection avec `pyproject.toml`
#       (`numpy>=2.0`) etait VIDE : le fichier ne decrivait aucun environnement
#       installable. Et le plancher de NFR1 ne tombe pas avec l'epingle : numpy
#       publie encore des roues `macosx_10_9_x86_64` en 2.0 comme en 2.3
#       (releve sur l'index PyPI le 2026-09-07), donc l'iMac Intel sous macOS 12
#       reste resolvable. C'est la borne haute qui etait fausse, pas la machine.
#   opencv-contrib-python  ->  opencv-python-headless   (EPIC11-ARB-253)
#   PySide6                ->  PySide6-Essentials       (EPIC11-ARB-254)
#
# Chaque test porte desormais sa frontiere NEGATIVE : la forme d'avant ne doit
# pas revenir. Sans elle, un banc qui suit un renommage ne mesure plus rien --
# il enregistre.
#
# La partie interpreteur ne porte que sur la pile GUI elle-meme (PySide6,
# pytest-qt), installee par cette story : la, l'import et la serie de
# version se verifient reellement, en tuple d'entiers -- jamais en chaine
# ("10.0" < "2" est le piege classique).

import re
from pathlib import Path

# Racine du depot : tests/unit/gui/test_environnement.py -> trois parents.
_RACINE = Path(__file__).resolve().parents[3]
_REQUIREMENTS = _RACINE / "requirements.txt"


def _lignes_requirements():
    """Rend les lignes utiles (non vides, non commentaires) de requirements.txt."""
    texte = _REQUIREMENTS.read_text(encoding="utf-8")
    return [
        ligne.strip()
        for ligne in texte.splitlines()
        if ligne.strip() and not ligne.strip().startswith("#")
    ]


def _contrainte(nom_paquet):
    """Rend la ligne de requirements.txt du paquet nomme (unique), ou echoue."""
    motif = re.compile(r"^" + re.escape(nom_paquet) + r"(?![A-Za-z0-9._-])")
    lignes = [l for l in _lignes_requirements() if motif.match(l)]
    assert len(lignes) == 1, (
        f"{nom_paquet} doit apparaitre exactement une fois dans "
        f"requirements.txt, trouve : {lignes!r}"
    )
    return lignes[0]


def test_numpy_ALIGNE_sur_pyproject_et_le_plafond_ne_revient_pas():
    """`5635d70a` : `<2` ici contre `>=2.0` dans `pyproject.toml`, intersection VIDE.

    Un fichier de declaration qui ne decrit aucun environnement possible ne
    s'arbitre pas, il se corrige -- et c'est la borne HAUTE qui etait fausse :
    le plancher de NFR1 (iMac Intel, macOS 12, x86_64) tient sans elle, numpy
    publiant encore une roue `macosx_10_9_x86_64` en 2.0 comme en 2.3.
    """
    assert _contrainte("numpy") == "numpy>=2.0"


def test_le_plafond_NUMPY_de_NFR1_ne_REVIENT_pas():
    """Frontiere negative : `<2` remis ici rendrait `pip install -e .` insoluble.

    C'est la moitie que le test ci-dessus ne mesure pas. Une egalite de chaine
    attrape le retour de `numpy>=1.24,<2` a l'identique ; elle ne dit rien d'un
    `numpy>=1.24,<2.0` ou d'un `numpy<2` seul, qui rouvriraient le meme defaut
    sous une autre orthographe.
    """
    ligne = _contrainte("numpy")
    for operateur, version in re.findall(r"(<=?)\s*([0-9][0-9.]*)", ligne):
        borne = tuple(int(p) for p in version.split(".") if p.isdigit())
        admet_2 = borne >= (2,) if operateur == "<=" else borne > (2,)
        assert admet_2, (
            f"le plafond {operateur}{version} exclut numpy 2 ({ligne!r}) -- "
            "l'intersection avec `pyproject.toml` (numpy>=2.0) redevient vide"
        )


def test_opencv_ouvert_jusqu_au_majeur_suivant_et_toujours_contrib():
    """La borne s'ouvre le 2026-09-06 (`EPIC11-ARB-250`), et le motif a change.

    **Ce test s'appelait `test_opencv_epingle_en_4_10` et exigeait `<4.11`.**
    Ce plafond ne servait pas ArUco -- NFR1 demande la variante *contrib*, pas
    une serie : c'est le `-contrib-` du nom qui porte ArUco, et il est toujours
    exige ici. Le plafond servait la machine de reference (iMac Intel sous
    macOS 12), parce que `4.10.0.84` est la DERNIERE version publiant une roue
    `macosx_12_0_x86_64`.

    Il est devenu nuisible : c'est aussi la ligne dont l'ENCODEUR rend un
    symbole malforme au-dela de la version 7, donc un
    `pip install -r requirements.txt` neuf resolvait vers le seul regime ou
    chaque planche imprimee est irrecuperable
    (`mesure-2026-09-06-plancher-opencv-et-rendu-qr.md`).

    L'encodage passant a `segno`, OpenCV n'est plus que DETECTEUR et DECODEUR,
    role ou 4.10 est sain. La borne peut donc s'ouvrir **sans** que la machine
    de reference perde quoi que ce soit : le plancher `>=4.10` la laisse
    resoudre vers 4.10.0.84, et le plafond `<6` laisse les postes recents
    resoudre plus haut. C'est une borne qui n'exclut plus personne, ce que
    `<4.11` ne pouvait pas dire.
    """
    assert _contrainte("opencv-python-headless") == "opencv-python-headless>=4.10,<6"


def test_la_roue_OpenCV_est_la_HEADLESS_et_la_non_headless_ne_revient_pas():
    """Frontiere negative d'`EPIC11-ARB-253`, portee ici le 2026-09-07.

    Le motif dominant n'est pas le poids : la roue non-headless lie son binaire
    a douze bibliotheques systeme graphiques qu'un conteneur nu, un serveur ou
    un WSL sans X n'ont pas -- `import cv2` y echoue sur `libGL.so.1` AVANT la
    premiere ligne du produit. `contrib` tombe dans le meme mouvement : les 51
    symboles `cv2.*` employes par `src/` existent tous dans la roue non-contrib,
    `aruco.ArucoDetector` compris (l'ArUco a quitte contrib pour objdetect en
    4.7).

    Une egalite sur la ligne headless ne dit rien d'une SECONDE ligne OpenCV
    ajoutee a cote : c'est ce que ce test-ci mesure, et lui seul.
    """
    lignes = _lignes_requirements()
    for interdite in ("opencv-contrib-python", "opencv-python"):
        fautives = [
            l for l in lignes
            if re.match(re.escape(interdite) + r"(?![A-Za-z0-9._-])", l)
        ]
        assert not fautives, (
            f"la roue {interdite!r} est revenue dans requirements.txt "
            f"({fautives!r}) : elle exige douze bibliotheques systeme de plus "
            "et casse `import cv2` sur une machine sans X (EPIC11-ARB-253)"
        )


def test_le_plancher_de_la_machine_de_reference_TIENT_toujours():
    """Frontiere negative : ouvrir le plafond ne doit pas emporter le plancher.

    Le plancher `>=4.10` est ce qui garde `4.10.0.84` -- donc macOS 12 x86_64 --
    dans l'ensemble resolvable. Un plancher releve a `>=4.12` ou `>=5.0`
    sortirait la machine de reference sans qu'aucun autre banc ne le dise : les
    roues macOS de 4.11 et au-dela commencent a `macosx_13_0`.
    """
    ligne = _contrainte("opencv-python-headless")
    assert ">=4.10" in ligne, (
        "le plancher de la machine de reference (macOS 12 x86_64, roue "
        "`macosx_12_0_x86_64` publiee jusqu'a 4.10.0.84 incluse) a bouge"
    )
    assert "<4.11" not in ligne, (
        "le plafond `<4.11` est revenu : il epingle la ligne dont l'encodeur "
        "rend un symbole malforme (EPIC11-ARB-250)"
    )


def test_segno_declare_car_c_est_LUI_qui_encode_desormais():
    """`EPIC11-ARB-250` : sans cette ligne, un environnement monte depuis ce
    fichier n'encode plus aucun QR du tout.

    Elle est ici plutot que dans l'extra GUI parce que l'encodage QR est du
    coeur -- meme raison qu'`EPIC8-ARB-1` pour OpenCV, reportlab et pypdfium2.
    """
    assert _contrainte("segno") == "segno>=1.6,<2"


def test_pyside6_essentials_epingle_en_6_8():
    # Qt 6.8 LTS : derniere serie supportant macOS 12, la machine de reference.
    # `Essentials` et non le metapaquet depuis `EPIC11-ARB-254`, porte ici par
    # `5635d70a` : le metapaquet tire aussi `Addons`, 401 Mo dont 186 Mo de
    # Chromium pour QtWebEngine, dont AUCUN module n'est importe par le depot.
    assert _contrainte("PySide6-Essentials") == "PySide6-Essentials>=6.8,<6.9"


def test_le_METAPAQUET_PySide6_ne_revient_pas():
    """Frontiere negative d'`EPIC11-ARB-254` : `PySide6` nu reintroduit Addons.

    Le negatif est ici le seul verdict utile. `_contrainte("PySide6-Essentials")`
    resterait vert si quelqu'un ajoutait `PySide6` SUR UNE AUTRE LIGNE, et
    c'est exactement la forme sous laquelle les 401 Mo reviendraient.
    """
    fautives = [
        l for l in _lignes_requirements()
        if re.match(r"PySide6(?![A-Za-z0-9._-])", l)
    ]
    assert not fautives, (
        f"le metapaquet PySide6 est revenu dans requirements.txt ({fautives!r}) "
        "-- il tire PySide6-Addons, 401 Mo dont aucun module n'est importe"
    )


def test_pytest_qt_declare():
    # Le banc headless (pytest-qt + offscreen) est le contrat de l'AC 7.
    assert _contrainte("pytest-qt") == "pytest-qt>=4.4"


def test_pile_gui_importable_et_en_serie_6_8():
    # La pile GUI installee par cette story se verifie, elle, reellement :
    # import + serie de version en TUPLE d'entiers, jamais en chaine.
    import PySide6.QtCore
    import pytestqt  # noqa: F401 -- l'import est le test

    version = tuple(int(p) for p in PySide6.QtCore.qVersion().split("."))
    assert (6, 8) <= version < (6, 9), (
        f"PySide6 doit etre en serie Qt 6.8, trouve {version}"
    )


def test_requirements_dev_sans_dependance_gui():
    # Frontiere negative de l'AC 1 : requirements.txt est le SEUL fichier de
    # dependances touche -- requirements-dev.txt ne porte aucune dependance GUI.
    texte = (_RACINE / "requirements-dev.txt").read_text(encoding="utf-8")
    assert "PySide6" not in texte
    assert "pytest-qt" not in texte
