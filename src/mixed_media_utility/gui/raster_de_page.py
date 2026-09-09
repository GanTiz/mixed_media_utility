# -*- coding: utf-8 -*-
"""Le raster d'une page de scan, pour l'affichage (story 7.4, AC 1 et AC 8).

**Ce module ne produit aucune image : il en CHOISIT une deja produite et la
met en forme pour l'ecran.** C'est la frontiere exacte que pose
``EPIC7-ARB-69`` sur la bascule brut / corrige : « Elle choisit quelle image
deja produite est affichee ; elle n'en calcule aucune, n'applique aucune LUT
et n'ecrit rien. »

Trois faits portes ici, et un seul est du code :

* **les pixels se demandent au coeur**, jamais a un ``cv2.imread`` local :
  ``scan_ingest.load_page_array`` est le point d'entree publie a l'usage des
  stories aval (contrat de jonction pose a 5.2), et il prend un LOCALISATEUR
  et non un chemin -- precisement parce qu'une page de PDF n'a pas de chemin
  propre ;
* **le coeur rend du BGR** (``color_pipeline.validate_bgr_input``), et Qt
  attend du RGB. L'inversion des canaux est faite ici, une fois, avec le
  piege nomme : PDFium rend deja du BGR, si bien qu'une conversion « par
  reflexe » inverserait rouge et bleu sans que rien ne le signale ;
* **aucune source corrigee n'existe dans le depot au 2026-08-25.** La
  calibration active est post-MVP (``EPIC5-ARB-5``) et toute page de
  detection sort ``calibration.status = not_applied``. Le fournisseur de
  projet le DIT (:meth:`FournisseurDeProjet.variante_disponible` rend faux
  pour la variante corrigee) plutot que de fabriquer une image pour la
  circonstance -- c'est ce qui grise la bascule sans jamais la faire
  disparaitre (``EPIC7-ARB-24``).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtGui import QImage

from .. import scan_ingest

#: Les deux variantes d'image d'une meme page. Ce sont des CHOIX
#: d'affichage, pas des traitements : la GUI n'en calcule aucune.
IMAGE_BRUTE = "brute"
IMAGE_CORRIGEE = "corrigee"
VARIANTES_D_IMAGE: tuple[str, ...] = (IMAGE_BRUTE, IMAGE_CORRIGEE)


def image_depuis_bgr(tableau: np.ndarray) -> QImage:
    """Convertir un tableau BGR du coeur en :class:`QImage` affichable.

    Deux mises en forme, toutes deux d'affichage et aucune colorimetrique :

    * **ordre des canaux** : le coeur garantit du BGR, Qt attend du RGB ;
    * **profondeur** : un scan 16 bits est ramene a 8 bits pour l'ecran, par
      decalage et non par etalement -- aucune courbe, aucun gain, aucune LUT.
      Juger la couleur se fait sur l'image, pas sur un rehaussement que
      l'outil aurait ajoute en silence.

    La copie finale est **obligatoire** : :class:`QImage` ne possede pas le
    tampon qu'on lui passe, et un tableau temporaire libere laisserait une
    image pointant dans le vide.
    """
    if tableau.ndim != 3 or tableau.shape[2] < 3:
        raise ValueError(
            f"tableau d'image inattendu (forme {tableau.shape}) : trois canaux "
            "BGR sont attendus"
        )
    if tableau.dtype == np.uint16:
        tableau = (tableau >> 8).astype(np.uint8)
    elif tableau.dtype != np.uint8:
        raise ValueError(f"profondeur d'image non affichable : {tableau.dtype}")
    rvb = np.ascontiguousarray(tableau[:, :, 2::-1])
    hauteur, largeur, _ = rvb.shape
    image = QImage(
        rvb.data, largeur, hauteur, 3 * largeur, QImage.Format.Format_RGB888
    )
    return image.copy()


class FournisseurDeProjet:
    """Les rasters d'un projet ouvert, lus par le contrat du coeur.

    **Lecture seule, et rien d'autre** : aucune ecriture, aucun recadrage,
    aucune image de frame fabriquee. Le dpi passe au rendu d'une page de PDF
    est celui que le DOCUMENT declare (``subject.scan_dpi_detection``), lu et
    non choisi ici : un dpi constant cote GUI ferait diverger l'apercu de la
    geometrie que le coeur a resolue.
    """

    def __init__(self, racine_projet: Path | str, dpi_de_detection: int):
        self.racine_projet = Path(racine_projet)
        self.dpi_de_detection = int(dpi_de_detection)

    def variante_disponible(self, variante: str) -> bool:
        """La variante demandee existe-t-elle pour ce projet ?

        Seule la variante brute existe au 2026-08-25 : la correction couleur
        n'est appliquee nulle part (``calibration.status = not_applied`` sur
        toute page detectee), donc aucune image corrigee n'a ete produite. On
        le DIT ; on n'en fabrique pas une.
        """
        return variante == IMAGE_BRUTE

    def image(self, page, variante: str = IMAGE_BRUTE) -> QImage | None:
        """Le raster de cette page dans cette variante, ou ``None``.

        ``None`` n'est pas un echec silencieux : l'ecran affiche alors sa
        phrase d'apercu indisponible, et **rien qui ressemble a une image**.
        """
        if not self.variante_disponible(variante):
            return None
        localisateur = scan_ingest.PageLocator(
            source_path=page.page.source_path_relative,
            page_index=page.page.source_page_index,
        )
        try:
            tableau = scan_ingest.load_page_array(
                self.racine_projet, localisateur, dpi=self.dpi_de_detection
            )
        except Exception:  # noqa: BLE001 -- toute panne de lecture = pas d'apercu
            return None
        try:
            return image_depuis_bgr(tableau)
        except ValueError:
            return None


class FournisseurDeTest:
    """Fournisseur explicite, pour les bancs et les captures deterministes.

    Il prend un dictionnaire ``(adresse de page, variante) -> QImage``. Il
    existe parce que **la bascule brut / corrige n'a aucune source corrigee
    dans le depot** : sans lui, l'AC 8 ne pourrait pas mesurer qu'une bascule
    posee dans la coquille atteint deux surfaces distinctes -- elle ne
    changerait jamais rien nulle part.
    """

    def __init__(self, images):
        self._images = dict(images)

    def variante_disponible(self, variante: str) -> bool:
        return any(cle[1] == variante for cle in self._images)

    def image(self, page, variante: str = IMAGE_BRUTE) -> QImage | None:
        return self._images.get((page.adresse, variante))


__all__ = [
    "FournisseurDeProjet",
    "FournisseurDeTest",
    "IMAGE_BRUTE",
    "IMAGE_CORRIGEE",
    "VARIANTES_D_IMAGE",
    "image_depuis_bgr",
]
