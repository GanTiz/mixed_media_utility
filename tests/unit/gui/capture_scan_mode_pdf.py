# -*- coding: utf-8 -*-
"""Scene DETERMINISTE du mode PDF, pour la capture de reference (7.4, AC 7).

Ce module n'est pas un fichier de tests : c'est la **fabrique de scene** que
la commande de regeneration et le banc partagent, pour que la capture
comparee et la capture versionnee soient rendues par le meme code.

La scene couvre **ce que la story fait voir** : une page portant a la fois
des zones proposees, des marqueurs decodes et une zone de QR non decode, de
sorte que **les trois familles de traits** soient dans le cadre.

Deux exigences de determinisme :

* le raster est une **image de synthese ecrite ici**, jamais un TIFF du
  depot (``tests/fixtures/`` n'en contient aucun, et Git LFS n'affecte donc
  jamais la suite) ;
* ce qui est capture est le **contenu d'image**, pas la fenetre : le rendu
  ne depend ainsi d'aucune police du systeme.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QImage, QPainter

import fabriques_detection as fab
from mixed_media_utility import qr_codes
from mixed_media_utility.gui import lecture_detection as lecture
from mixed_media_utility.gui import surimpressions

#: Nom de la reference versionnee (``tests/fixtures/captures-gui/``).
NOM_DE_REFERENCE = "scan-mode-pdf"

#: Taille de la capture, en pixels de widget. Figee : une taille qui
#: dependrait de la fenetre rendrait la reference irreproductible.
LARGEUR_CAPTURE = 640
HAUTEUR_CAPTURE = 452

#: Repere de page de la fixture, volontairement petit : la capture reste
#: legere a versionner et les traits restent lisibles a l'oeil.
LARGEUR_PAGE = 1600
HAUTEUR_PAGE = 1131


def raster_de_synthese() -> QImage:
    """Un raster deterministe : bandes de gris, sans police ni aleatoire.

    Des bandes NEUTRES et non un aplat : un aplat uniforme rendrait
    indetectable un decalage de l'image elle-meme, et les traits a halo
    doivent se lire aussi bien sur du clair que sur du sombre -- c'est
    exactement ce que la spine leur demande.
    """
    image = QImage(LARGEUR_PAGE, HAUTEUR_PAGE, QImage.Format.Format_RGB888)
    image.fill(QColor(255, 255, 255))
    peintre = QPainter(image)
    hauteur_de_bande = HAUTEUR_PAGE // 8
    for indice in range(8):
        niveau = 32 * indice
        peintre.fillRect(
            0, indice * hauteur_de_bande, LARGEUR_PAGE, hauteur_de_bande,
            QColor(niveau, niveau, niveau),
        )
    peintre.end()
    return image


def page_de_reference():
    """La page de la fixture : deux zones, quatre coins, une zone de QR.

    La page visee est la **seconde** du document (regle des fabriques), et
    son ``read_rank`` est desaligne de son ``page_index``.
    """
    rang, index = fab.ADRESSE_CIBLE
    zone_qr = fab.zone(9, rang, index, largeur_px=260, hauteur_px=260,
                       x_px=1240, y_px=60)
    zone_qr["zone_name"] = surimpressions.NOM_DE_ZONE_QR
    zones = [
        fab.zone(0, rang, index, largeur_px=520, hauteur_px=300,
                 x_px=120, y_px=420),
        fab.zone(1, rang, index, largeur_px=560, hauteur_px=320,
                 x_px=760, y_px=440),
        zone_qr,
    ]
    brut = fab.deux_pages_cible_seconde(
        zones=zones,
        qr_status=qr_codes.DECODE_NO_SYMBOL,
        largeur_px=LARGEUR_PAGE,
        hauteur_px=HAUTEUR_PAGE,
    )
    brut["pages"][1]["page_size_px"] = [LARGEUR_PAGE, HAUTEUR_PAGE]
    # Quatre coins a quatre centres DIFFERENTS, ramenes au repere de la
    # fixture : des centres uniformes rendraient toute permutation invisible.
    centres = {0: (90.0, 90.0), 1: (1510.0, 100.0),
               2: (1520.0, 1040.0), 3: (100.0, 1050.0)}
    for marqueur in brut["pages"][1]["corner_markers"]:
        marqueur["center_x_px"], marqueur["center_y_px"] = centres[
            marqueur["marker_id"]
        ]
    document = lecture.depuis_json(brut)
    return document.page_par_adresse(rang, index)


def contenu_de_reference(decalage_de_zone=0):
    """Le widget A CAPTURER : le contenu d'image, seul.

    ``decalage_de_zone`` deplace **une** surimpression de N pixels de page.
    Il existe pour le test SYMETRIQUE de l'AC 7 -- « une comparaison qui ne
    sait que dire "identique" ne mesure rien » -- et pour rien d'autre : la
    reference est toujours rendue a decalage nul.
    """
    page = page_de_reference()
    contenu = surimpressions.ContenuDImage()
    contenu.resize(LARGEUR_CAPTURE, HAUTEUR_CAPTURE)
    contenu.poser(page, raster_de_synthese())
    if decalage_de_zone:
        plan = list(contenu.plan)
        premier = plan[0]
        x, y, largeur, hauteur = premier.rectangle_px
        plan[0] = surimpressions.Trait(
            famille=premier.famille,
            identifiant=premier.identifiant,
            jeton_couleur=premier.jeton_couleur,
            rectangle_px=(x + decalage_de_zone, y, largeur, hauteur),
        )
        contenu.plan = tuple(plan)
    return contenu


#: Le registre lu par la commande de regeneration.
SCENES = {NOM_DE_REFERENCE: contenu_de_reference}
