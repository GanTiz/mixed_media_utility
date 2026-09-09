# -*- coding: utf-8 -*-
"""Le banc qui REGARDE : aucun pixel peint n'est etranger a la palette.

**Pourquoi ce fichier existe.** Les 450 autres tests GUI mesurent ce qui est
*ecrit* -- qu'aucune couleur litterale ne vive hors de `jetons.py`, que les
neutres soient strictement neutres, que chaque texte tienne son plancher de
contraste. Aucun ne regarde ce qui est *peint*. C'est une frontiere reelle, et
elle a laisse passer trois defauts de la meme famille :

* revue de vague 2 -- le viewport et le porteur de la liste de projets, gris
  clair au milieu d'une coque sombre, sur la premiere surface du produit ;
* 2026-08-26 -- les poignees de `QSplitter`, **deux bandes verticales de haut
  en bas** en plein milieu de la coquille ;
* 2026-08-26 -- le gris de controle par defaut de Windows sur **66 % de la vue
  galerie**, invisible tant qu'on ne regardait pas la surface hors de sa
  coquille.

Les trois ont la meme cause : un widget qu'aucun selecteur ne vise retombe sur
le style natif de la plateforme. Aucune relecture ne les trouve, aucun test
d'ecriture non plus -- il faut peindre et compter.

**Ce que le test mesure, et pourquoi pas « toute couleur est un jeton ».**
L'anticrenelage fabrique des melanges : un `border-radius` sur une ligne pose
des dizaines de teintes intermediaires entre le fond de la ligne et la toile,
et exiger la palette exacte rendrait le test faux au premier arrondi. Ce qui
distingue un defaut d'un melange, c'est la **surface couverte** : un melange
d'anticrenelage borde des formes, il ne remplit pas des panneaux. Le seuil
porte donc sur la proportion, et il est volontairement bas -- les trois
defauts ci-dessus couvraient 20 %, 66 %, et deux bandes pleine hauteur.

**Il tourne sous Windows sans banc graphique.** `QWidget.grab()` rend le widget
dans un `QPixmap` sans passer par la capture d'ecran du systeme : ni Xvfb, ni
fenetre au premier plan.
"""

from __future__ import annotations

import collections

import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

import fabriques_detection as fab
from mixed_media_utility.gui import catalogue, jetons, scan_jugement
from mixed_media_utility.gui import lecture_detection as lecture
from mixed_media_utility.gui.__main__ import _application_qt
from mixed_media_utility.gui.coquille import Coquille

#: Part maximale de l'image qu'une couleur etrangere a le droit d'occuper.
#: 0,5 %, soit environ 6 500 pixels sur une fenetre 1400x860 : largement de
#: quoi border toutes les formes arrondies d'un ecran, et tres loin des
#: 20 a 66 % que couvraient les defauts reels.
PART_TOLEREE = 0.005

#: L'echantillonnage. Un pixel sur deux dans chaque direction, soit un quart
#: de l'image : assez pour qu'un panneau entier ne puisse pas passer entre les
#: mailles, assez peu pour que le test reste sous la seconde.
PAS = 2


@pytest.fixture(autouse=True)
def feuille_d_application():
    """Poser la feuille d'application sur la `QApplication` du banc.

    **Sans elle ce fichier ne mesure rien de ce que voit l'utilisatrice** :
    pytest-qt construit sa propre `QApplication`, sur laquelle personne n'a
    jamais pose la feuille du produit. Les widgets s'y peindraient au style
    natif -- le test rougirait pour la mauvaise raison, ou pire, on baisserait
    le seuil jusqu'a ce qu'il passe.
    """
    _application_qt()
    yield
    QApplication.instance().setStyleSheet("")


def _couleurs_peintes(widget) -> collections.Counter:
    """Peindre le widget et compter ses couleurs."""
    widget.show()
    QApplication.processEvents()
    image = widget.grab().toImage()
    compte: collections.Counter = collections.Counter()
    for y in range(0, image.height(), PAS):
        for x in range(0, image.width(), PAS):
            compte[QColor(image.pixel(x, y)).name().upper()] += 1
    return compte


def couleurs_etrangeres(widget):
    """Les couleurs hors palette qui couvrent plus que la part toleree.

    Rend une liste de couples `(couleur, part)`, la plus etendue d'abord --
    de sorte que le message d'echec nomme le coupable et dise son ampleur,
    plutot que de laisser chercher.
    """
    connues = {valeur.upper() for valeur in jetons.COULEURS.values()}
    compte = _couleurs_peintes(widget)
    total = sum(compte.values()) or 1
    etrangeres = [
        (couleur, n / total)
        for couleur, n in compte.items()
        if couleur not in connues and n / total > PART_TOLEREE
    ]
    return sorted(etrangeres, key=lambda paire: -paire[1])


# ---------------------------------------------------------------------------
# Les surfaces
# ---------------------------------------------------------------------------


def test_la_coquille_ne_peint_AUCUNE_couleur_etrangere(qtbot):
    """La surface ou vivaient les deux bandes blanches de poignee."""
    coquille = Coquille()
    qtbot.addWidget(coquille)
    coquille.resize(1400, 860)

    etrangeres = couleurs_etrangeres(coquille)

    assert etrangeres == [], (
        "couleurs hors palette dans la coquille : "
        + ", ".join(f"{c} sur {p:.1%}" for c, p in etrangeres)
    )


@pytest.mark.parametrize("onglet", ["page", "galerie"])
def test_l_atelier_scan_ne_peint_AUCUNE_couleur_etrangere(qtbot, onglet):
    """L'atelier **hors de sa coquille**, et c'est tout l'interet.

    Dans la coquille, ces surfaces laissent voir la toile de celle-ci : le
    defaut du 2026-08-26 y etait donc invisible. Une surface qui n'est juste
    que par l'endroit ou on la pose n'est pas juste.

    Les DEUX onglets, et non un seul : leurs fonds sont poses par deux
    branches distinctes, et le gris de Windows couvrait 66 % de l'un contre
    20 % de l'autre -- n'en mesurer qu'un laisserait passer la moitie.
    """
    document = lecture.depuis_json(fab.deux_pages_cible_seconde())
    atelier = scan_jugement.AtelierScanJugement(catalogue.CHAINES)
    qtbot.addWidget(atelier)
    atelier.resize(1400, 860)
    atelier.poser_document(document, document.page_par_adresse(*fab.ADRESSE_CIBLE))
    atelier.onglets.activer(onglet)
    QApplication.processEvents()

    etrangeres = couleurs_etrangeres(atelier)

    assert etrangeres == [], (
        f"couleurs hors palette dans l'atelier Scan ({onglet}) : "
        + ", ".join(f"{c} sur {p:.1%}" for c, p in etrangeres)
    )


def test_les_poignees_de_splitter_sont_PEINTES(qtbot):
    """Le defaut le plus visible du 2026-08-26, vise nommement.

    Il ne peut pas etre laisse au test de proportion ci-dessus, et la mesure le
    dit : deux poignees de `splitter-width` sur une fenetre de 1400 px de large
    occupent moins de 0,5 % de l'image. Elles passeraient donc sous le seuil --
    tout en formant, a l'oeil, deux bandes claires de haut en bas, plus
    visibles que le contenu.

    C'est pourquoi ce test-ci ne compte pas : il va **lire le pixel a
    l'endroit exact de chaque poignee**, position obtenue du splitter lui-meme
    et non devinee.
    """
    coquille = Coquille()
    qtbot.addWidget(coquille)
    coquille.resize(1400, 860)
    coquille.show()
    QApplication.processEvents()

    poignees = [
        coquille.splitter.handle(indice)
        for indice in range(1, coquille.splitter.count())
    ]
    assert poignees, "le splitter ne porte aucune poignee, le test ne mesure rien"

    image = coquille.grab().toImage()
    attendu = jetons.COULEURS["border"].upper()
    for indice, poignee in enumerate(poignees, start=1):
        centre = poignee.mapTo(coquille, poignee.rect().center())
        lu = QColor(image.pixel(centre.x(), centre.y())).name().upper()
        assert lu == attendu, (
            f"la poignee {indice} est peinte {lu} au lieu de {attendu} "
            f"(position {centre.x()},{centre.y()})"
        )


# ---------------------------------------------------------------------------
# Le garde-fou du garde-fou
# ---------------------------------------------------------------------------


def test_le_banc_VOIT_reellement_une_couleur_etrangere(qtbot):
    """Sans ce volet, un `couleurs_etrangeres` qui rendrait toujours `[]` --
    parce qu'il compte mal, parce que la capture est vide, parce que le seuil
    est trop haut -- ferait passer les trois tests ci-dessus en promettant une
    garantie qui n'existe pas.

    On peint donc DELIBEREMENT une surface hors palette et l'on exige que le
    banc la nomme. La couleur choisie n'est pas un neutre : elle ne peut etre
    ni un jeton, ni un melange de deux jetons de la coque.
    """
    coquille = Coquille()
    qtbot.addWidget(coquille)
    coquille.resize(400, 300)
    coquille.setStyleSheet("QMainWindow { background: #FF00FF; }")

    etrangeres = couleurs_etrangeres(coquille)

    assert etrangeres, "le banc ne voit pas une surface entierement hors palette"
    assert etrangeres[0][0] == "#FF00FF"
    assert etrangeres[0][1] > 0.5, "la couleur doit couvrir l'essentiel du widget"


def test_la_part_toleree_laisse_passer_un_bord_ANTICRENELE(qtbot):
    """Volet symetrique du precedent : le seuil doit etre au-dessus de ce que
    l'anticrenelage produit reellement, sinon la seule facon de garder le banc
    vert serait de retirer les arrondis de la spine.

    Mesure sur la coquille : la somme de TOUTES les couleurs hors palette y
    reste sous la part toleree, alors que la coque porte des coins arrondis
    (`rounded.lg` sur la scene, `rounded.md` sur les lignes).
    """
    coquille = Coquille()
    qtbot.addWidget(coquille)
    coquille.resize(1400, 860)

    connues = {valeur.upper() for valeur in jetons.COULEURS.values()}
    compte = _couleurs_peintes(coquille)
    total = sum(compte.values()) or 1
    part_hors_palette = sum(n for c, n in compte.items() if c not in connues) / total

    assert 0 < part_hors_palette < 0.10, (
        "des melanges existent (sinon le test ne prouve rien) et ils restent "
        f"marginaux -- mesure : {part_hors_palette:.1%}"
    )
