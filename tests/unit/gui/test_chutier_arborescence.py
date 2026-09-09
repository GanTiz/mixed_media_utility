# -*- coding: utf-8 -*-
"""Retours de terrain du 2026-08-27 -- `EPIC7-ARB-94` et `EPIC7-ARB-85`.

Quatre corrections du PANNEAU d'arborescence, mesurees sur ce qui se voit
plutot que sur ce qui est ecrit :

* (a) le panneau n'a qu'**une** colonne -- les deux colonnes de signes, qu'il
  ne remplit jamais, lui prenaient 32 px sur 160 et coupaient les noms en
  « rus... » (capture ``image-1.png``) ;
* (b) **un seul** lisere de selection -- ``QTreeWidget::item:selected`` en
  peignait un par CELLULE, soit trois traits bleus sur une ligne du chutier
  (« comme 2 niveaux de selection », captures ``image-2`` a ``image-4``) ;
* (c) les **traits de niveau** et les expandeurs ``+`` / ``-`` de la maquette
  ``key-chutier-v2.html``, perdus en route ;
* (d) la **ligne racine** qui rend la portee « projet entier » atteignable
  (`EPIC7-ARB-85`) -- moitie composant, la coquille cable l'autre.

**Le banc n'a AUCUNE police** : `QFontDatabase.families()` rend une liste vide
sous `offscreen` ici, et tout texte se peint en tofu -- deux glyphes distincts
donnent le meme rectangle. Les tests qui portent sur le CHOIX d'un glyphe
enregistrent donc les commandes de peinture dans un `QPicture` et y relisent le
caractere reellement emis ; ceux qui portent sur la PRESENCE d'encre se
contentent des pixels, le tofu etant de l'encre comme une autre.

Regle des fabriques du depot : la fixture porte **deux rushes distinguables de
deux lots chacun**, et la cible des assertions est partout la **seconde** --
un `find` fautif qui rend toujours le premier element ne se demasque pas
autrement.
"""

import pytest
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QPainter, QPicture, QPixmap
from PySide6.QtWidgets import QHeaderView, QStyle, QStyleOptionViewItem

import fabriques_chutier as fab
from mixed_media_utility.gui import catalogue, jetons
from mixed_media_utility.gui import chutier as module_chutier
from mixed_media_utility.gui import modele_chutier as modele

#: Le libelle de la ligne racine, tel que la coquille le composera.
LIBELLE_RACINE = catalogue.CHAINES["arborescence-racine"].format(projet="projet_demo")

#: Une couleur qui n'appartient a AUCUN jeton : elle remplit le calque avant le
#: rendu, si bien qu'un pixel non peint ne peut jamais se faire passer pour un
#: pixel de l'interface.
_TEMOIN_NON_PEINT = Qt.GlobalColor.magenta


# ---------------------------------------------------------------------------
# Fixtures et outils de mesure
# ---------------------------------------------------------------------------


@pytest.fixture
def racines():
    """Deux rushes distinguables, deux lots distinguables chacun."""
    return modele.construire_arbre(
        fab.manifest_deux_rushes_deux_lots_chacun(),
        documents_de_detection=[],
        existe=fab.liaison_factice(["medias/alpha.mov", "medias/beta.mov"]),
    )


def _arbre(qtbot, *, montre_les_signes, largeur=240, hauteur=500):
    arbre = module_chutier.ArbreDeChutier(
        catalogue.CHAINES, montre_les_signes=montre_les_signes
    )
    qtbot.addWidget(arbre)
    arbre.resize(largeur, hauteur)
    arbre.show()
    qtbot.waitExposed(arbre)
    return arbre


@pytest.fixture
def panneau(qtbot, racines):
    """Le panneau d'arborescence -- celui qui ne montre aucun signe."""
    arbre = _arbre(qtbot, montre_les_signes=False)
    arbre.poser(racines)
    return arbre


@pytest.fixture
def chutier(qtbot, racines):
    """Le chutier -- celui qui porte les deux familles de signes."""
    arbre = _arbre(qtbot, montre_les_signes=True, largeur=300)
    arbre.poser(racines)
    return arbre


def _image_de(arbre):
    """Le rendu du viewport, sur un calque temoin non peint."""
    calque = QPixmap(arbre.viewport().size())
    calque.fill(_TEMOIN_NON_PEINT)
    arbre.viewport().render(calque)
    return calque.toImage()


def _est(image, x, y, couleur):
    return image.pixelColor(x, y).name().upper() == couleur.upper()


def _bandes_horizontales(image, y, couleur):
    """Les `(x, largeur)` des suites contigues d'une couleur, sur la ligne `y`."""
    trouvees = []
    debut = None
    for x in range(image.width()):
        if _est(image, x, y, couleur):
            if debut is None:
                debut = x
        elif debut is not None:
            trouvees.append((debut, x - debut))
            debut = None
    if debut is not None:
        trouvees.append((debut, image.width() - debut))
    return trouvees


def _hauteur_de_trait(image, x, y_premier, y_dernier, couleur):
    """Combien de pixels de `couleur` la colonne `x` porte entre deux ordonnees."""
    return sum(
        1
        for y in range(y_premier, y_dernier + 1)
        if _est(image, x, y, couleur)
    )


def _premier_x_d_encre(image, rectangle, fonds):
    """L'abscisse de la premiere encre d'une ligne, fonds exclus.

    Sert a mesurer que le lisere **reserve sa place au repos** : si la place
    n'etait prise qu'a la selection, le contenu de la ligne selectionnee se
    decalerait, et cette abscisse changerait d'un etat a l'autre.
    """
    fonds = tuple(couleur.upper() for couleur in fonds)
    for x in range(rectangle.left(), rectangle.right() + 1):
        for y in range(rectangle.top(), rectangle.bottom() + 1):
            if image.pixelColor(x, y).name().upper() not in fonds:
                return x
    return None


def _commandes_de_branche(arbre, identifiant):
    """Les commandes de peinture que `drawBranches` emet pour une ligne.

    Le banc n'ayant aucune police, le seul moyen de savoir QUEL glyphe est
    peint est de relire le flux de commandes : `QPicture` le serialise, et une
    `QString` y voyage en UTF-16 gros-boutiste.
    """
    element = arbre.element(identifiant)
    index = arbre.indexFromItem(element, module_chutier.COLONNE_LIBELLE)
    ligne = arbre.visualItemRect(element)
    branche = QRect(0, ligne.top(), ligne.left(), ligne.height())
    tableau = QPicture()
    peintre = QPainter(tableau)
    try:
        arbre.drawBranches(peintre, branche, index)
    finally:
        peintre.end()
    return bytes(tableau.data())


def _porte(commandes, glyphe):
    return glyphe.encode("utf-16-be") in commandes


def _profondeur(arbre, identifiant):
    profondeur = 0
    parent = arbre.element(identifiant).parent()
    while parent is not None:
        profondeur += 1
        parent = parent.parent()
    return profondeur


def _abscisse_du_trait(arbre, identifiant):
    """L'abscisse du trait de filiation qui relie une ligne a son parent."""
    indentation = arbre.indentation()
    return _profondeur(arbre, identifiant) * indentation - indentation // 2


# ===========================================================================
# `EPIC7-ARB-94` (a) -- le panneau d'arborescence n'a qu'UNE colonne
# ===========================================================================


def test_le_panneau_d_arborescence_n_a_qu_une_seule_colonne(panneau):
    assert panneau.columnCount() == module_chutier.NOMBRE_DE_COLONNES_SANS_SIGNES
    assert module_chutier.NOMBRE_DE_COLONNES_SANS_SIGNES == 1


def test_le_chutier_garde_SES_DEUX_colonnes_de_signes(chutier):
    """Symetrique du precedent : **rien n'est fondu**.

    « Il est structurellement impossible de fondre les deux familles de signes
    en un seul signe » (`DESIGN.md`) : la correction du panneau ne doit pas
    servir de porte d'entree a cette fusion.
    """
    assert chutier.columnCount() == module_chutier.NOMBRE_DE_COLONNES
    assert module_chutier.NOMBRE_DE_COLONNES == 3
    assert module_chutier.COLONNE_BADGE != module_chutier.COLONNE_GLYPHE
    entete = chutier.header()
    for colonne in (module_chutier.COLONNE_BADGE, module_chutier.COLONNE_GLYPHE):
        assert entete.sectionResizeMode(colonne) == (
            QHeaderView.ResizeMode.ResizeToContents
        )


def test_le_libelle_prend_TOUTE_la_largeur_du_panneau(qtbot, racines):
    """Mesure, pas mode de redimensionnement : la largeur reellement obtenue.

    Au plancher de la poignee (160 px), la colonne du libelle valait 128 px
    avant le correctif -- les deux colonnes vides prenaient 16 px chacune, soit
    20 % du panneau, sans jamais rien montrer.
    """
    panneau = _arbre(
        qtbot,
        montre_les_signes=False,
        largeur=jetons.ESPACEMENTS["tree-panel-min-width"],
    )
    panneau.poser(racines)
    utile = panneau.viewport().width()
    assert panneau.columnWidth(module_chutier.COLONNE_LIBELLE) == utile, (
        "la colonne du libelle ne prend pas toute la largeur du panneau : "
        f"{panneau.columnWidth(module_chutier.COLONNE_LIBELLE)} px sur {utile}"
    )


def test_le_plancher_de_section_du_panneau_ne_reserve_plus_de_largeur(panneau):
    """`Stretch` ne suffisait pas : Qt refuse a une section de descendre sous
    `minimumSectionSize`, 16 px ici. C'est ce plancher, et non le mode, qui
    donnait leur largeur aux deux colonnes vides."""
    assert panneau.header().minimumSectionSize() == 0


def test_un_nom_de_rush_n_est_plus_TRONQUE_dans_le_panneau(qtbot, racines):
    """La mesure du defaut d'Egan : « rus... » (capture ``image-1.png``).

    Le panneau est dimensionne a la largeur **exactement necessaire** au nom
    du SECOND rush -- indentation, lisere, pictogramme et texte compris. La
    mesure ne depend donc d'aucune metrique de police codee en dur : avec une
    seule colonne le nom tient tout juste, avec trois il est elide.
    """
    cible = "rush-beta"
    sonde = _arbre(qtbot, montre_les_signes=False)
    sonde.poser(racines)
    texte = sonde.element(cible).text(module_chutier.COLONNE_LIBELLE)
    metriques = sonde.fontMetrics()
    requis = metriques.horizontalAdvance(texte)
    marges = (
        sonde.indentation()
        + jetons.ARBORESCENCE["lisere-selection-px"]
        + jetons.ICONOGRAPHIE["boite-px"]
        + jetons.ESPACEMENTS["2"]
    )

    panneau = _arbre(qtbot, montre_les_signes=False, largeur=requis + marges)
    panneau.poser(racines)
    rectangle = panneau.visualRect(
        panneau.indexFromItem(
            panneau.element(cible), module_chutier.COLONNE_LIBELLE
        )
    )
    disponible = rectangle.width() - (marges - panneau.indentation())
    assert disponible >= requis, (
        f"{disponible} px pour un nom qui en demande {requis} : il sera coupe"
    )
    assert (
        metriques.elidedText(texte, Qt.TextElideMode.ElideRight, disponible) == texte
    )


# ===========================================================================
# `EPIC7-ARB-94` (b) -- UN SEUL lisere de selection
# ===========================================================================


def test_une_seule_bande_d_accent_sur_la_ligne_selectionnee(chutier):
    """Le compte de CELLULES qui recoivent le lisere, mesure sur le rendu.

    Avant le correctif : trois bandes d'accent sur la meme ligne du chutier --
    ``(12, 4)``, ``(268, 4)``, ``(284, 4)`` --, les deux dernieres a droite du
    nom. C'est litteralement ce qu'Egan decrit : « 2 niveaux de selection
    (double ligne bleue a droite du nom) ».
    """
    cible = chutier.element("rush-beta")
    chutier.setCurrentItem(cible)
    ligne = chutier.visualItemRect(cible)
    bandes = _bandes_horizontales(
        _image_de(chutier), ligne.center().y(), jetons.COULEURS["accent"]
    )
    assert len(bandes) == 1, f"{len(bandes)} traits d'accent sur la ligne : {bandes}"
    depart, largeur = bandes[0]
    assert largeur == jetons.ARBORESCENCE["lisere-selection-px"]
    assert depart == ligne.left()


def test_aucune_autre_ligne_ne_porte_de_lisere(chutier):
    """Symetrique : le balayage precedent mesure bien quelque chose."""
    chutier.setCurrentItem(chutier.element("rush-beta"))
    image = _image_de(chutier)
    autre = chutier.visualItemRect(chutier.element("rush-alpha"))
    assert (
        _bandes_horizontales(image, autre.center().y(), jetons.COULEURS["accent"]) == []
    )


def test_la_feuille_de_style_ne_peint_plus_le_lisere(panneau, chutier):
    """Une regle de style ne sait pas distinguer les colonnes : elle n'a donc
    plus le droit de porter l'accent."""
    for arbre in (panneau, chutier):
        assert jetons.COULEURS["accent"] not in arbre.styleSheet()


def test_seule_la_colonne_du_libelle_recoit_le_lisere(chutier):
    """Le predicat du delegue, colonne par colonne -- et a l'etat de repos."""
    delegue = chutier.lisere
    index = chutier.indexFromItem(
        chutier.element("rush-beta"), module_chutier.COLONNE_LIBELLE
    )
    recues = []
    for colonne in range(module_chutier.NOMBRE_DE_COLONNES):
        option = QStyleOptionViewItem()
        option.state = QStyle.StateFlag.State_Selected
        if delegue.peint_le_lisere(option, index.siblingAtColumn(colonne)):
            recues.append(colonne)
    assert recues == [module_chutier.COLONNE_LIBELLE]

    au_repos = QStyleOptionViewItem()
    au_repos.state = QStyle.StateFlag.State_Enabled
    assert not delegue.peint_le_lisere(au_repos, index)


def test_le_lisere_reserve_sa_place_au_repos(chutier):
    """Une bordure qui n'apparaitrait qu'a la selection decalerait le texte.

    Mesure : l'abscisse de la premiere encre de la ligne -- son pictogramme --
    est **la meme** que la ligne soit selectionnee ou non. La largeur reservee
    et la largeur peinte sont d'ailleurs le meme jeton, ce que la feuille de
    style doit continuer de dire.
    """
    largeur = jetons.ARBORESCENCE["lisere-selection-px"]
    assert f"border-left: {largeur}px solid transparent" in chutier.styleSheet()

    cible = chutier.element("rush-beta")
    au_repos = _premier_x_d_encre(
        _image_de(chutier),
        chutier.visualItemRect(cible),
        (jetons.COULEURS["surface-panel"], jetons.COULEURS["accent"]),
    )
    chutier.setCurrentItem(cible)
    selectionne = _premier_x_d_encre(
        _image_de(chutier),
        chutier.visualItemRect(cible),
        (
            jetons.COULEURS["surface-hover"],
            jetons.COULEURS["surface-panel"],
            jetons.COULEURS["accent"],
        ),
    )
    assert au_repos is not None and selectionne is not None
    assert au_repos == selectionne, (
        f"le contenu de la ligne se decale a la selection : {au_repos} -> "
        f"{selectionne}"
    )


# ===========================================================================
# `EPIC7-ARB-94` (c) -- traits de niveau et expandeurs `+` / `-`
# ===========================================================================


def test_l_expandeur_n_apparait_QUE_sur_un_noeud_qui_a_des_enfants(panneau):
    """L'invariant `EPIC7-ARB-3` : « son absence est l'information ».

    La cible sans enfant est le **second** lot du **second** rush -- jamais le
    premier element d'une collection.
    """
    panneau.expandAll()
    avec_enfants = _commandes_de_branche(panneau, "rush-beta")
    sans_enfant = _commandes_de_branche(panneau, "lot-beta-2")
    signes = (
        jetons.ICONOGRAPHIE["glyphe-deplier"],
        jetons.ICONOGRAPHIE["glyphe-replier-niveau"],
    )
    assert any(_porte(avec_enfants, signe) for signe in signes)
    assert not any(_porte(sans_enfant, signe) for signe in signes)
    assert panneau.montre_un_expandeur(panneau.element("rush-beta"))
    assert not panneau.montre_un_expandeur(panneau.element("lot-beta-2"))


def test_l_expandeur_bascule_du_plus_au_moins_quand_le_niveau_se_deplie(panneau):
    """`+` replie, `-` deplie -- les deux signes viennent des jetons."""
    deplier = jetons.ICONOGRAPHIE["glyphe-deplier"]
    replier = jetons.ICONOGRAPHIE["glyphe-replier-niveau"]
    assert deplier != replier

    panneau.collapseAll()
    replie = _commandes_de_branche(panneau, "rush-beta")
    panneau.expandAll()
    deplie = _commandes_de_branche(panneau, "rush-beta")

    assert _porte(replie, deplier) and not _porte(replie, replier)
    assert _porte(deplie, replier) and not _porte(deplie, deplier)


def test_les_traits_de_filiation_s_arretent_au_dernier_objet_d_un_niveau(panneau):
    """« Les traits d'arbre s'arretent au dernier objet d'un niveau ».

    Transcrit de ``key-chutier-v2.html`` :
    ``.kids > .node:last-child::before { height:14px; bottom:auto }``. La cible
    est le **second** lot -- le dernier --, et son symetrique le premier, qui
    doit au contraire prolonger le trait.
    """
    panneau.expandAll()
    image = _image_de(panneau)
    couleur = jetons.COULEURS["border"]
    mesures = {}
    for identifiant in ("lot-beta-1", "lot-beta-2"):
        ligne = panneau.visualItemRect(panneau.element(identifiant))
        milieu = ligne.top() + ligne.height() // 2
        x = _abscisse_du_trait(panneau, identifiant)
        mesures[identifiant] = (
            _hauteur_de_trait(image, x, ligne.top(), milieu - 1, couleur),
            _hauteur_de_trait(image, x, milieu + 1, ligne.bottom(), couleur),
        )
    haut_premier, bas_premier = mesures["lot-beta-1"]
    haut_dernier, bas_dernier = mesures["lot-beta-2"]
    # Les deux rejoignent leur parent par le haut...
    assert haut_premier > 0 and haut_dernier > 0
    # ... mais seul celui qui a un frere en dessous prolonge le trait.
    assert bas_premier > 0, "le trait ne descend pas vers le frere suivant"
    assert bas_dernier == 0, (
        f"le trait continue sous le dernier objet du niveau ({bas_dernier} px)"
    )


def test_le_raccord_horizontal_relie_le_trait_a_la_ligne(panneau):
    """Le second trait de la maquette : ``.kids > .node > .row::before``."""
    panneau.expandAll()
    image = _image_de(panneau)
    ligne = panneau.visualItemRect(panneau.element("lot-beta-2"))
    milieu = ligne.top() + ligne.height() // 2
    bandes = _bandes_horizontales(image, milieu, jetons.COULEURS["border"])
    assert bandes, "aucun raccord horizontal sur la ligne"
    depart, largeur = bandes[0]
    assert depart == _abscisse_du_trait(panneau, "lot-beta-2")
    assert largeur > jetons.ARBORESCENCE["trait-px"]


def test_le_premier_niveau_ne_porte_aucun_trait_de_filiation(panneau):
    """La maquette ne trace de filets que dans `.kids` : une ligne de premier
    niveau n'a pas de parent a rejoindre."""
    panneau.expandAll()
    image = _image_de(panneau)
    ligne = panneau.visualItemRect(panneau.element("rush-beta"))
    for y in range(ligne.top(), ligne.bottom() + 1):
        assert _bandes_horizontales(image, y, jetons.COULEURS["border"]) == []


def test_le_trait_de_filiation_a_la_graisse_et_la_couleur_des_jetons(panneau):
    """Aucune valeur litterale : la graisse et la chromie se lisent des jetons.

    Le calque est rempli d'une couleur temoin avant le rendu : un trait absent
    ne peut donc pas se confondre avec un fond.
    """
    panneau.expandAll()
    image = _image_de(panneau)
    ligne = panneau.visualItemRect(panneau.element("lot-beta-1"))
    haut = ligne.top() + 2
    bandes = _bandes_horizontales(image, haut, jetons.COULEURS["border"])
    assert len(bandes) == 1, bandes
    depart, largeur = bandes[0]
    assert largeur == jetons.ARBORESCENCE["trait-px"]
    assert depart == _abscisse_du_trait(panneau, "lot-beta-1")


# ===========================================================================
# `EPIC7-ARB-85` -- la ligne racine
# ===========================================================================


def test_la_ligne_racine_devient_le_seul_premier_niveau(panneau, racines):
    """« On perd le niveau le plus eleve » : il est desormais une ligne."""
    panneau.poser(racines, libelle_racine=LIBELLE_RACINE)
    assert panneau.topLevelItemCount() == 1
    tete = panneau.topLevelItem(0)
    assert tete.text(module_chutier.COLONNE_LIBELLE) == LIBELLE_RACINE
    assert tete is panneau.element(module_chutier.IDENTIFIANT_RACINE)
    # TOUS les noeuds de `racines` deviennent ses enfants, dans l'ordre pose.
    assert [
        tete.child(rang).text(module_chutier.COLONNE_LIBELLE)
        for rang in range(tete.childCount())
    ] == panneau.identifiants_racines()
    assert panneau.libelle_racine() == LIBELLE_RACINE


def test_sans_libelle_racine_le_comportement_est_STRICTEMENT_celui_d_avant(
    panneau, racines
):
    """Symetrique : la ligne racine est une option, jamais un nouvel invariant."""
    panneau.poser(racines)
    assert panneau.topLevelItemCount() == len(racines)
    assert panneau.element(module_chutier.IDENTIFIANT_RACINE) is None
    assert module_chutier.IDENTIFIANT_RACINE not in panneau.tous_les_identifiants()
    assert panneau.libelle_racine() is None


def test_les_rushes_ET_leurs_lots_restent_visibles_sous_la_ligne_racine(
    panneau, racines
):
    """`expandToDepth(0)` s'arreterait a la ligne racine et cacherait tout.

    Mesure : la hauteur rendue de la ligne. Un element dont le parent est
    replie a un rectangle vide -- c'est ce que rendait le depliage d'avant.
    Cible : le **second** lot du **second** rush.
    """
    panneau.poser(racines, libelle_racine=LIBELLE_RACINE)
    for identifiant in ("rush-beta", "lot-beta-2"):
        rectangle = panneau.visualItemRect(panneau.element(identifiant))
        assert rectangle.height() > 0, f"{identifiant} est cache sous la ligne racine"
    assert panneau.element(module_chutier.IDENTIFIANT_RACINE).isExpanded()


def test_un_clic_sur_la_ligne_racine_emet_l_identifiant_racine(qtbot, panneau, racines):
    """Elle designe comme n'importe quelle autre ligne : c'est la coquille qui
    traduira `IDENTIFIANT_RACINE` en portee `None`."""
    panneau.poser(racines, libelle_racine=LIBELLE_RACINE)
    rectangle = panneau.visualItemRect(
        panneau.element(module_chutier.IDENTIFIANT_RACINE)
    )
    with qtbot.waitSignal(panneau.designation_changee, timeout=1000) as attente:
        qtbot.mouseClick(
            panneau.viewport(), Qt.MouseButton.LeftButton, pos=rectangle.center()
        )
    assert attente.args == [module_chutier.IDENTIFIANT_RACINE]


def test_un_clic_sur_la_ligne_racine_n_ouvre_RIEN(qtbot, panneau, racines):
    """`EPIC7-ARB-2` tient : un clic designe, un double-clic ouvre."""
    panneau.poser(racines, libelle_racine=LIBELLE_RACINE)
    ouvertures = []
    panneau.ouverture_demandee.connect(ouvertures.append)
    rectangle = panneau.visualItemRect(
        panneau.element(module_chutier.IDENTIFIANT_RACINE)
    )
    qtbot.mouseClick(
        panneau.viewport(), Qt.MouseButton.LeftButton, pos=rectangle.center()
    )
    qtbot.wait(20)
    assert ouvertures == []


def test_la_ligne_racine_n_est_JAMAIS_cochable(chutier, racines):
    """`selection.actionnables(IDENTIFIANT_RACINE)` n'existe pas cote modele :
    la ligne racine sort du balayage, et sa case avec.

    Le symetrique est dans le meme test : une ligne qui a des actionnables,
    elle, recoit bien sa case -- sans quoi le balayage pourrait etre vide.
    """
    chutier.poser(racines, libelle_racine=LIBELLE_RACINE)
    chutier.refleter_la_selection(modele.Selection(racines, "atelier-pdf"))

    racine = chutier.element(module_chutier.IDENTIFIANT_RACINE)
    assert not (racine.flags() & Qt.ItemFlag.ItemIsUserCheckable)
    assert (
        racine.data(module_chutier.COLONNE_LIBELLE, Qt.ItemDataRole.CheckStateRole)
        is None
    )
    cochable = chutier.element("rush-beta")
    assert cochable.flags() & Qt.ItemFlag.ItemIsUserCheckable
    assert cochable.checkState(module_chutier.COLONNE_LIBELLE) == (
        Qt.CheckState.Unchecked
    )


def test_la_ligne_racine_ne_porte_AUCUN_signe(qtbot):
    """Ni badge de completude, ni glyphe de rattachement.

    La fixture porte deux lots du meme rush dont le **second** est incomplet :
    le symetrique -- un badge la ou il en faut un -- est mesure dans le meme
    test, sinon l'absence pourrait etre celle de tous les badges.
    """
    racines = modele.construire_arbre(
        fab.manifest_deux_lots_meme_rush(),
        documents_de_detection=[],
        existe=fab.liaison_factice(["medias/alpha.mov"]),
    )
    arbre = _arbre(qtbot, montre_les_signes=True, largeur=300)
    arbre.poser(racines, libelle_racine=LIBELLE_RACINE)
    racine = arbre.element(module_chutier.IDENTIFIANT_RACINE)
    for colonne in (module_chutier.COLONNE_BADGE, module_chutier.COLONNE_GLYPHE):
        assert arbre.itemWidget(racine, colonne) is None
    incomplet = arbre.itemWidget(
        arbre.element("lot-cadence-18"), module_chutier.COLONNE_BADGE
    )
    assert incomplet is not None
    assert incomplet.etat == modele.BADGE_INCOMPLET


def test_les_lectures_restent_coherentes_avec_la_ligne_racine(panneau, racines):
    """Ce que chaque lecture rend une fois la ligne racine posee.

    La ligne racine n'est **pas** un noeud du modele : elle n'entre ni dans
    `racines()` ni dans `identifiants_racines()`, `noeud()` ne lui rend rien --
    mais elle est bien une ligne posee, donc `element()`, `designer()` et
    `tous_les_identifiants()` la connaissent.
    """
    panneau.poser(racines, libelle_racine=LIBELLE_RACINE)
    assert panneau.racines() == tuple(racines)
    assert panneau.identifiants_racines() == ["rush-alpha", "rush-beta"]
    assert module_chutier.IDENTIFIANT_RACINE not in panneau.identifiants_racines()

    tous = panneau.tous_les_identifiants()
    assert module_chutier.IDENTIFIANT_RACINE in tous
    assert {"rush-alpha", "rush-beta", "lot-beta-2"} <= set(tous)

    assert panneau.noeud(module_chutier.IDENTIFIANT_RACINE) is None
    assert panneau.noeud("rush-beta").identifiant == "rush-beta"
    assert panneau.element(module_chutier.IDENTIFIANT_RACINE) is not None


def test_designer_atteint_la_ligne_racine_ET_un_noeud_qui_n_est_pas_le_premier(
    panneau, racines
):
    """La cible n'est pas en premiere position : c'est le **second** lot du
    **second** rush, deux niveaux sous la ligne racine."""
    panneau.poser(racines, libelle_racine=LIBELLE_RACINE)
    assert panneau.designer("lot-beta-2")
    assert panneau.designation() == "lot-beta-2"
    assert panneau.element("rush-beta").isExpanded()

    assert panneau.designer(module_chutier.IDENTIFIANT_RACINE)
    assert panneau.designation() == module_chutier.IDENTIFIANT_RACINE
