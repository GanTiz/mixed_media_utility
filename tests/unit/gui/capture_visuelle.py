# -*- coding: utf-8 -*-
"""Capture et comparaison d'image pour les bancs GUI -- **bien d'epic**.

``EPIC7-ARB-65`` (2026-08-25), verbatim : « Aucune story ulterieure ne
construit un second mecanisme de capture ou de comparaison d'image. » Ce
module est donc le point unique, importable tel quel : capture headless,
comparaison, tolerance **declaree**, commande de regeneration. Il est pose
dans un module de support et **non enfoui dans le fichier de tests d'une
story** -- sa rentabilite est acquise au deuxieme usage.

Trois regles portees ici, et chacune est un piege deja paye dans ce depot :

1. **une reference absente ou illisible est un ECHEC DUR, jamais un
   ``skip``** -- un skip se lirait comme un vert alors que la comparaison ne
   s'evalue pas du tout (meme politique que le grep de frontiere du socle
   7.0) ;
2. **la reference ne se regenere JAMAIS toute seule au passage d'un test**,
   ce qui reviendrait a ne rien comparer. Elle se regenere par une commande
   explicite :

   .. code-block:: console

      python3 tests/unit/gui/capture_visuelle.py --regenerer

3. **la comparaison sait dire « different »**, pas seulement « identique » :
   une comparaison qui ne saurait que le second ne mesure rien. C'est ce que
   le test symetrique de chaque story doit exercer.

**Ce qui est capture est le CONTENU D'IMAGE**, pas la fenetre : le rendu ne
doit dependre d'aucune police du systeme pour la partie mesuree, et le
contenu d'image ne porte, par construction, aucun texte.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PySide6.QtGui import QImage

#: Ou vivent les captures de reference, versionnees dans le depot. Ce sont
#: des PNG : `tests/fixtures/` ne contient aucun TIFF et ne doit pas en
#: contenir (Git LFS n'affecte donc jamais la suite de tests).
DOSSIER_REFERENCES = (
    Path(__file__).resolve().parents[2] / "fixtures" / "captures-gui"
)

#: Tolerance DECLAREE de la comparaison. Deux seuils, et ils ne disent pas la
#: meme chose :
#:
#: * ``ecart_canal_max`` absorbe le bruit d'anticrenelage d'un rendu a
#:   l'identique -- un bord de trait peut differer d'un ou deux niveaux entre
#:   deux versions mineures de Qt sans que rien n'ait bouge ;
#: * ``proportion_pixels_differents`` est ce qui attrape un DEPLACEMENT :
#:   une surimpression decalee d'un seul pixel change toute la longueur de
#:   son trait, donc une proportion de pixels tres superieure a ce seuil.
#:
#: Les deux doivent tenir : une tolerance qui ne serait qu'un plafond de
#: niveau laisserait passer un decalage, et l'AC serait tautologique.
TOLERANCE_ECART_CANAL_MAX = 8
TOLERANCE_PROPORTION_PIXELS = 0.002

#: F10 (revue vague 3, mutant M17) -- seuil de COMPTAGE d'un pixel
#: "different", volontairement INDEPENDANT de `TOLERANCE_ECART_CANAL_MAX`.
#:
#: Avant ce correctif, `pixels_differents` ne comptait que les pixels dont
#: l'ecart depassait deja `TOLERANCE_ECART_CANAL_MAX` : des que l'axe canal
#: passait (`ecart_canal_max <= TOLERANCE_ECART_CANAL_MAX`), AUCUN pixel ne
#: pouvait donc etre compte comme different, la proportion valait
#: toujours zero, et `TOLERANCE_PROPORTION_PIXELS` ne changeait le verdict
#: `identiques` d'AUCUNE paire d'images possible -- une egalite-au-source
#: entre les deux seuils, famille du mutant M17 (revue de vague 3, story
#: 7.4 AC 7). Un pixel compte ici des qu'il differe d'AU MOINS UN niveau
#: sur un canal ; c'est `TOLERANCE_PROPORTION_PIXELS`, et lui seul, qui
#: absorbe ensuite le bruit residuel d'anticrenelage sur la PROPORTION.
_SEUIL_DE_COMPTAGE_PIXEL_DIFFERENT = 0


class CaptureIntrouvable(AssertionError):
    """Reference absente ou illisible. **Jamais un ``skip``.**"""


@dataclass(frozen=True)
class Ecart:
    """Ce que la comparaison MESURE, et qui se lit dans un message d'echec."""

    pixels_differents: int
    pixels_total: int
    ecart_canal_max: int

    @property
    def proportion_pixels_differents(self) -> float:
        return self.pixels_differents / max(self.pixels_total, 1)

    @property
    def identiques(self) -> bool:
        return (
            self.ecart_canal_max <= TOLERANCE_ECART_CANAL_MAX
            and self.proportion_pixels_differents <= TOLERANCE_PROPORTION_PIXELS
        )

    def __str__(self) -> str:
        return (
            f"{self.pixels_differents}/{self.pixels_total} pixels differents "
            f"({self.proportion_pixels_differents:.4%}), ecart canal max "
            f"{self.ecart_canal_max}"
        )


def capturer(widget) -> QImage:
    """Capturer un widget, headless.

    ``widget.grab()`` peint le widget dans un tampon hors ecran : il marche
    sous ``QT_QPA_PLATFORM=offscreen`` sans Xvfb, ce qui est le contrat du
    banc GUI depuis le socle 7.0.
    """
    return widget.grab().toImage().convertToFormat(QImage.Format.Format_RGB888)


def _tableau(image: QImage) -> np.ndarray:
    """Les pixels d'une :class:`QImage` en tableau (hauteur, largeur, 3)."""
    image = image.convertToFormat(QImage.Format.Format_RGB888)
    largeur, hauteur = image.width(), image.height()
    pointeur = image.constBits()
    brut = np.frombuffer(pointeur, dtype=np.uint8, count=image.sizeInBytes())
    # `bytesPerLine` peut depasser 3 * largeur (alignement Qt) : on decoupe
    # ligne par ligne plutot que de supposer un tampon compact.
    lignes = brut.reshape(hauteur, image.bytesPerLine())
    return lignes[:, : largeur * 3].reshape(hauteur, largeur, 3).copy()


def ecart(image_a: QImage, image_b: QImage) -> Ecart:
    """L'ecart MESURE entre deux captures.

    Deux captures de tailles differentes ne sont pas « un peu » differentes :
    elles le sont totalement, et le dire ainsi evite un faux vert par
    recadrage silencieux.
    """
    if image_a.size() != image_b.size():
        total = max(
            image_a.width() * image_a.height(), image_b.width() * image_b.height()
        )
        return Ecart(pixels_differents=total, pixels_total=total, ecart_canal_max=255)
    gauche = _tableau(image_a).astype(np.int16)
    droite = _tableau(image_b).astype(np.int16)
    delta = np.abs(gauche - droite)
    par_pixel = delta.max(axis=2)
    return Ecart(
        pixels_differents=int(
            (par_pixel > _SEUIL_DE_COMPTAGE_PIXEL_DIFFERENT).sum()
        ),
        pixels_total=int(par_pixel.size),
        ecart_canal_max=int(delta.max()) if delta.size else 0,
    )


def chemin_de_reference(nom: str) -> Path:
    return DOSSIER_REFERENCES / f"{nom}.png"


def charger_reference(nom: str) -> QImage:
    """Charger une reference versionnee. **Echec dur** si elle manque.

    « L'AC est satisfaite quand la reference existe, que le comparateur
    tourne, et que le banc echoue franchement si la reference est absente ou
    illisible -- jamais un ``skip``, qui se lirait comme un vert. »
    """
    chemin = chemin_de_reference(nom)
    if not chemin.is_file():
        raise CaptureIntrouvable(
            f"capture de reference absente : {chemin}. La regenerer "
            "explicitement (python3 tests/unit/gui/capture_visuelle.py "
            "--regenerer) apres avoir VERIFIE a l'oeil ce qu'elle fige."
        )
    image = QImage(str(chemin))
    if image.isNull():
        raise CaptureIntrouvable(f"capture de reference illisible : {chemin}")
    return image.convertToFormat(QImage.Format.Format_RGB888)


def comparer(image: QImage, nom: str) -> Ecart:
    """Comparer une capture neuve a sa reference versionnee."""
    return ecart(image, charger_reference(nom))


def enregistrer(image: QImage, nom: str) -> Path:
    """Ecrire une reference. **Appelee par la commande, jamais par un test.**"""
    DOSSIER_REFERENCES.mkdir(parents=True, exist_ok=True)
    chemin = chemin_de_reference(nom)
    if not image.save(str(chemin), "PNG"):
        raise OSError(f"ecriture de la capture impossible : {chemin}")
    return chemin


# ---------------------------------------------------------------------------
# Commande de regeneration -- explicite, jamais declenchee par un test
# ---------------------------------------------------------------------------

#: Prefixe des modules de scenes. Chaque story qui verse une reference pose
#: un `capture_<sujet>.py` a cote de ce module, exportant un dictionnaire
#: `SCENES` de `nom -> fabrique()`, ou la fabrique rend le widget A CAPTURER.
PREFIXE_MODULES_DE_SCENE = "capture_"


def _scenes_declarees() -> dict:
    """Les scenes de toutes les stories, chargees depuis ce meme dossier."""
    scenes: dict = {}
    dossier = Path(__file__).resolve().parent
    for source in sorted(dossier.glob(f"{PREFIXE_MODULES_DE_SCENE}*.py")):
        if source.name == Path(__file__).name:
            continue
        specification = importlib.util.spec_from_file_location(
            source.stem, source
        )
        module = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(module)
        scenes.update(getattr(module, "SCENES", {}))
    return scenes


def _regenerer() -> int:  # pragma: no cover -- commande, jamais un test
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance() or QApplication([])
    scenes = _scenes_declarees()
    if not scenes:
        print("Aucune scene declaree : rien a regenerer.", file=sys.stderr)
        return 1
    for nom, fabrique in sorted(scenes.items()):
        widget = fabrique()
        chemin = enregistrer(capturer(widget), nom)
        print(f"capture regeneree : {chemin}")
    del application
    return 0


if __name__ == "__main__":  # pragma: no cover -- commande
    if "--regenerer" not in sys.argv[1:]:
        print(
            "Usage : python3 tests/unit/gui/capture_visuelle.py --regenerer\n"
            "Rien n'est ecrit sans cette option : une reference qui se "
            "regenere toute seule ne compare plus rien.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    raise SystemExit(_regenerer())
