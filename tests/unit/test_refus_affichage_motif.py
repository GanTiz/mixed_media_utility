"""Story 11.4, lot B1 -- `DisplayUnavailableError` porte un motif nu.

`EPIC11-ARB-73` : les trois refus de `cadence_previz.ensure_display_available`
nomment tous `--no-display`, l'option qu'`EPIC11-ARB-41` interdit d'exposer
dans la TUI. L'exception gagne donc un attribut `motif` -- la phrase **sans**
son conseil d'option -- et la CLI garde son message actuel, inchange au
caractere pres.

Ce banc porte les deux moities de cette promesse, et elles ne se mesurent pas
au meme moment :

* `test_les_trois_refus_rendent_le_message_exact_du_baseline` est vert
  **avant et apres** le changement. C'est lui, et lui seul, qui prouve que
  rien de ce que la CLI imprime ne bouge ;
* les autres mesurent l'ajout : le motif existe, il ne nomme pas l'option, et
  la recomposition `motif + conseil` rend exactement le message.
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import cadence_previz
from mixed_media_utility.cadence_previz import DisplayUnavailableError

#: Les trois branches de refus, dans l'ordre ou `ensure_display_available` les
#: pose, avec leur message **releve sur le depot** au commit `2da4205` (lot A
#: de la 11.4), et non reecrit de memoire. Les trois cas sont volontairement
#: distinguables -- environnements differents, messages differents, conseils
#: differents : une table dont les trois lignes se ressembleraient ne verrait
#: pas un appariement inverse.
CAS_DE_REFUS: tuple[tuple[str, dict[str, str], bool, str, str], ...] = (
    (
        "ni DISPLAY ni WAYLAND_DISPLAY",
        {},
        False,
        "DISPLAY_UNAVAILABLE: aucun affichage disponible (ni DISPLAY ni "
        "WAYLAND_DISPLAY dans l'environnement). Relancer dans une session "
        "graphique, ou utiliser --no-display pour une lecture mesuree sans "
        "fenetre.",
        "Relancer dans une session graphique, ou utiliser --no-display pour "
        "une lecture mesuree sans fenetre.",
    ),
    (
        "DISPLAY defini mais socket absente",
        {"DISPLAY": ":42"},
        False,
        "DISPLAY_UNAVAILABLE: DISPLAY=':42' est defini mais aucun serveur "
        "graphique ne repond a cette adresse (/tmp/.X11-unix/X42 est absent). "
        "C'est le cas d'une connexion distante sans redirection graphique, ou "
        "d'une session detachee de son affichage. Relancer dans une session "
        "graphique, ou utiliser --no-display pour une lecture mesuree sans "
        "fenetre.",
        "Relancer dans une session graphique, ou utiliser --no-display pour "
        "une lecture mesuree sans fenetre.",
    ),
    (
        # Message REVISE le 2026-09-06 (EPIC11-ARB-253 et -89), et c'est le
        # seul des trois qui bouge. Deux motifs cumules :
        #   * `paquet` devient `roue`, la roue headless etant desormais celle
        #     que le produit installe -- ce n'est plus un cas exotique ;
        #   * le conseil nomme ses DEUX issues au lieu d'une. `EPIC11-ARB-89`
        #     l'exige de toute sortie qui refuse, et l'issue manquante est
        #     precisement celle qui REND la fonction perdue.
        # Ce que ce changement ne coute pas : ce message n'a JAMAIS ete imprime
        # avant le 2026-09-06, le garde qui le leve ne s'etant jamais
        # declenche (`hasattr(cv2, "imshow")` rend `True` sur la roue
        # headless). Il n'y a donc pas de contrat CLI rompu -- il y a un refus
        # qui existe enfin.
        "OpenCV compile sans interface",
        {"WAYLAND_DISPLAY": "wayland-0"},
        True,
        "DISPLAY_UNAVAILABLE: cette compilation d'OpenCV n'expose aucune "
        "interface graphique (roue 'headless'). Utiliser --no-display pour "
        "une lecture mesuree sans fenetre, ou installer la roue OpenCV avec "
        "interface : pipx inject --force mmu-tui opencv-python -- elle exige "
        "en plus les bibliotheques systeme libGL et libX11.",
        "Utiliser --no-display pour une lecture mesuree sans fenetre, ou "
        "installer la roue OpenCV avec interface : pipx inject --force "
        "mmu-tui opencv-python -- elle exige en plus les bibliotheques "
        "systeme libGL et libX11.",
    ),
)


def _lever(monkeypatch, environ: dict[str, str], sans_interface_opencv: bool):
    """Provoquer un refus et rendre l'exception, sans toucher a l'environnement reel.

    `ensure_display_available` recoit `environ` et `platform` en argument : la
    fabrication du cas ne passe donc jamais par `os.environ`. Seule la
    troisieme branche demande une compilation d'OpenCV sans interface, qui se
    rend par `monkeypatch`.

    **La fabrication a change le 2026-09-06, et c'est le fond du correctif.**
    Elle amputait `cv2` de son `imshow` -- c'est-a-dire qu'elle reproduisait la
    facon dont le garde CROYAIT detecter le cas, pas la facon dont le cas se
    produit. Mesure : sur la vraie roue headless 5.0.0, `imshow` EXISTE
    (`hasattr` rend `True`) et c'est l'APPEL qui leve. Le banc fabriquait donc
    une panne que le terrain n'a pas, et il est reste vert pendant que le garde
    ne se declenchait jamais -- exactement la famille de defaut que CLAUDE.md
    nomme (« une fixture de synthese peut fabriquer une panne que le terrain
    n'a PAS »).

    Ce qu'une roue headless porte REELLEMENT, et ce qu'on fabrique donc ici :
    une ligne `GUI:` valant `NONE` dans `cv2.getBuildInformation()`.
    """
    if sans_interface_opencv:
        monkeypatch.setattr(
            cv2, "getBuildInformation",
            lambda: "  Version control:  4.10.0\n  GUI:              NONE\n",
        )
    with pytest.raises(DisplayUnavailableError) as capture:
        cadence_previz.ensure_display_available(
            environ=environ, platform="linux")
    return capture.value


@pytest.mark.parametrize(
    "nom, environ, sans_interface_opencv, message, conseil", CAS_DE_REFUS,
    ids=[cas[0] for cas in CAS_DE_REFUS])
def test_les_trois_refus_rendent_le_message_exact_du_baseline(
    monkeypatch, nom, environ, sans_interface_opencv, message, conseil
):
    """Le contrat CLI, au caractere pres. VERT AVANT ET APRES le changement.

    Une egalite stricte, pas un `in` : c'est la seule forme qui rougit sur une
    ponctuation deplacee, un espace double ou un conseil recompose autrement.
    """
    exception = _lever(monkeypatch, environ, sans_interface_opencv)
    assert str(exception) == message


@pytest.mark.parametrize(
    "nom, environ, sans_interface_opencv, message, conseil", CAS_DE_REFUS,
    ids=[cas[0] for cas in CAS_DE_REFUS])
def test_le_motif_ne_nomme_jamais_l_option_interdite(
    monkeypatch, nom, environ, sans_interface_opencv, message, conseil
):
    """`EPIC11-ARB-41`, frontiere negative : zero `no-display` dans le motif.

    La sous-chaine est cherchee sans le tiret cadratin ni le prefixe `--` :
    `no-display` attrape aussi bien `--no-display` qu'une mention en prose.
    """
    exception = _lever(monkeypatch, environ, sans_interface_opencv)
    assert "no-display" not in exception.motif


@pytest.mark.parametrize(
    "nom, environ, sans_interface_opencv, message, conseil", CAS_DE_REFUS,
    ids=[cas[0] for cas in CAS_DE_REFUS])
def test_le_message_est_exactement_le_motif_suivi_du_conseil(
    monkeypatch, nom, environ, sans_interface_opencv, message, conseil
):
    """Une seule redaction : le message CLI se recompose depuis ses deux morceaux.

    Si le motif etait redige a part du message -- deuxieme redaction -- cette
    egalite tomberait des la premiere divergence de formulation.
    """
    exception = _lever(monkeypatch, environ, sans_interface_opencv)
    assert exception.conseil == conseil
    assert f"{exception.motif} {exception.conseil}" == message
    assert exception.motif.endswith(".")


def test_les_trois_motifs_sont_distincts():
    """Volet symetrique : trois refus, trois motifs, jamais un motif unique.

    Un `motif` constant -- par exemple recopie du premier cas -- satisferait
    la frontiere negative ci-dessus sans rien dire de vrai. La mesure porte
    donc sur le cardinal, sur les trois cas et pas sur le premier.
    """
    motifs = {cas[3].split(" Relancer")[0].split(" Utiliser")[0]
              for cas in CAS_DE_REFUS}
    assert len(motifs) == len(CAS_DE_REFUS)


def test_le_troisieme_cas_porte_bien_un_conseil_different_des_deux_premiers():
    """Regle des fabriques : la cible n'est pas en premiere position.

    Les deux premieres branches partagent le meme conseil ; la troisieme a le
    sien. Un decoupage qui prendrait toujours le conseil de la premiere
    branche passerait sur les deux premiers cas et tombe ici.
    """
    conseils = [cas[4] for cas in CAS_DE_REFUS]
    assert conseils[0] == conseils[1]
    assert conseils[2] != conseils[0]


# --------------------------------------------------------------------------
# Les deux refus du sink, qui portent la meme exception
# --------------------------------------------------------------------------


class _ErreurCv(Exception):
    """Substitut de `cv2.error`, pour ne dependre d'aucune compilation."""


def test_le_refus_d_ouverture_de_fenetre_garde_son_message_et_gagne_son_motif(
    monkeypatch,
):
    """`CvWindowSink` leve la meme exception : elle porte le motif elle aussi.

    Ces deux refus la ne sont pas cites par `EPIC11-ARB-73`, mais ils sont
    atteignables depuis la TUI des qu'une previz s'ouvre : un `motif` qui
    nommerait l'option ici rouvrirait le trou par l'autre bout.
    """
    monkeypatch.setattr(cadence_previz, "cv2", cv2)
    monkeypatch.setattr(cv2, "error", _ErreurCv, raising=False)

    def refuser(*_args, **_kwargs):
        raise _ErreurCv("pas de backend")

    monkeypatch.setattr(cv2, "namedWindow", refuser)
    sink = cadence_previz.CvWindowSink()
    with pytest.raises(DisplayUnavailableError) as capture:
        sink.present(None, None)
    exception = capture.value
    assert str(exception) == (
        "Impossible d'ouvrir une fenetre de lecture: OpenCV a refuse "
        "'namedWindow' (pas de backend). Verifier qu'un affichage est "
        "disponible (variable DISPLAY sous Linux) et qu'OpenCV n'est pas "
        "compile sans interface graphique (paquet 'headless'). Une lecture "
        "sans affichage reste possible avec --no-display.")
    assert "no-display" not in exception.motif


def test_l_affichage_interrompu_garde_son_message_et_gagne_son_motif(monkeypatch):
    """Second refus du sink : `imshow` casse en cours de lecture."""
    monkeypatch.setattr(cv2, "error", _ErreurCv, raising=False)
    monkeypatch.setattr(cv2, "namedWindow", lambda *a, **k: None)
    monkeypatch.setattr(cv2, "getWindowProperty", lambda *a, **k: 1.0)
    monkeypatch.setattr(cv2, "waitKey", lambda *a, **k: -1)

    def refuser(*_args, **_kwargs):
        raise _ErreurCv("fenetre perdue")

    monkeypatch.setattr(cv2, "imshow", refuser)
    sink = cadence_previz.CvWindowSink()
    monkeypatch.setattr(sink, "_draw_overlay", lambda image, presentation: image)
    with pytest.raises(DisplayUnavailableError) as capture:
        sink.present(object(), None)
    exception = capture.value
    assert str(exception) == (
        "Affichage interrompu par OpenCV (fenetre perdue). Relancer avec "
        "--no-display pour une lecture mesuree sans fenetre.")
    assert "no-display" not in exception.motif
