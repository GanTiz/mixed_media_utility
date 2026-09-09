# -*- coding: utf-8 -*-
"""Story 7.4, AC 6 -- coins droits, bande `mat-min` neutre, jetons lus.

Les surimpressions sont du dessin colore : c'est precisement la ou l'invariant
colorimetrique de ``DESIGN.md`` mord le plus fort. Ce banc CALCULE ses ratios
(jamais recopies du module teste : piege du test tautologique de 5.9) et itere
sur l'ENSEMBLE complet des descendants, jamais sur un echantillon.
"""

import ast
import re
from pathlib import Path

from PySide6.QtWidgets import QApplication, QLabel, QWidget

import fabriques_detection as fab
from mixed_media_utility.gui import scan_jugement, catalogue, jetons
from mixed_media_utility.gui import lecture_detection as lecture
from mixed_media_utility.gui import surimpressions

_PAQUET_GUI = Path(jetons.__file__).resolve().parent


# ---------------------------------------------------------------------------
# Outils de calcul, ecrits DANS le test (WCAG 2.1, sRGB)
# ---------------------------------------------------------------------------


def _rgb(hexa):
    return tuple(int(hexa[indice:indice + 2], 16) for indice in (1, 3, 5))


def _luminance(hexa):
    canaux = []
    for valeur in _rgb(hexa):
        proportion = valeur / 255.0
        canaux.append(
            proportion / 12.92
            if proportion <= 0.03928
            else ((proportion + 0.055) / 1.055) ** 2.4
        )
        # Coefficients sRGB, ecrits ici et non lus du module teste.
    rouge, vert, bleu = canaux
    return 0.2126 * rouge + 0.7152 * vert + 0.0722 * bleu


def _ratio(hexa_a, hexa_b):
    claire, sombre = sorted((_luminance(hexa_a), _luminance(hexa_b)), reverse=True)
    return (claire + 0.05) / (sombre + 0.05)


def _est_neutre(hexa):
    rouge, vert, bleu = _rgb(hexa)
    return rouge == vert == bleu


# ---------------------------------------------------------------------------
# Les trois surfaces d'image de la story
# ---------------------------------------------------------------------------


def _surfaces(qtbot):
    """Les trois surfaces d'image, chacune posee sur une vraie page."""
    document = lecture.depuis_json(fab.deux_pages_cible_seconde())
    page = document.page_par_adresse(*fab.ADRESSE_CIBLE)
    atelier = scan_jugement.AtelierScanJugement(catalogue.CHAINES)
    qtbot.addWidget(atelier)
    atelier.resize(1400, 900)
    atelier.show()
    atelier.poser_document(document, page)
    rang, index = fab.ADRESSE_CIBLE
    atelier.ouvrir_la_frame((rang, index, 1))
    _appliquer_les_layouts(atelier)
    scenes = [atelier.vue_page.scene, atelier.vue_frame.scene]
    scenes += [ligne.apercu for ligne in atelier.vue_galerie.lignes]
    assert len(scenes) >= 3, "les trois surfaces d'image doivent etre couvertes"
    return atelier, scenes


# ---------------------------------------------------------------------------
# (J) -- coins droits sur tout contenu d'image
# ---------------------------------------------------------------------------


def test_le_contenu_d_image_est_a_rayon_nul_et_aucun_descendant_n_en_porte(qtbot):
    _atelier, scenes = _surfaces(qtbot)
    for scene in scenes:
        contenu = scene.contenu
        assert contenu.rayon == jetons.RAYONS["none"] == 0
        # Aucun descendant : c'est structurel, donc aucun ne peut porter de
        # rayon. On le MESURE plutot que de le supposer.
        descendants = contenu.findChildren(QWidget)
        assert descendants == []
        for widget in [contenu, *descendants]:
            feuille = widget.styleSheet()
            assert "border-radius" not in feuille or "border-radius: 0px" in feuille
        # Le CADRE, lui, est arrondi : les deux moities sont mesurees.
        assert scene.rayon == jetons.RAYONS["lg"]
        assert scene.rayon != contenu.rayon


def test_une_vignette_de_galerie_est_a_coins_droits(qtbot):
    """`frame-thumb.radius` vaut `{rounded.none}` : c'est un contenu d'image."""
    document = lecture.depuis_json(fab.deux_pages_cible_seconde())
    galerie = scan_jugement.VueGalerie(catalogue.CHAINES)
    qtbot.addWidget(galerie)
    galerie.poser(document)
    cases = [case for ligne in galerie.lignes for case in ligne.cases]
    assert len(cases) >= 4
    for case in cases:
        assert (
            f"border-radius: {jetons.RAYON_CONTENU_IMAGE}px"
            in case.vignette.styleSheet()
        )
        assert jetons.RAYON_CONTENU_IMAGE == 0


# ---------------------------------------------------------------------------
# (J) -- la bande `mat-min` est du neutre pur
# ---------------------------------------------------------------------------


def _appliquer_les_layouts(racine):
    """Forcer Qt a poser les geometries avant toute mesure.

    Sans ce geste la mesure porterait sur des geometries par defaut et non
    sur la mise en page reelle -- un banc vert qui ne mesure rien, ou un
    banc rouge qui accuse a tort. Mesure au moment d'ecrire ce test : la
    scene d'une ligne de galerie, posee dans un `QScrollArea`, gardait sa
    geometrie initiale et faisait sortir la chromie du contenu **dans** la
    bande, alors qu'elle est dedans.
    """
    QApplication.processEvents()
    for widget in [racine, *racine.findChildren(QWidget)]:
        disposition = widget.layout()
        if disposition is not None:
            disposition.activate()
    QApplication.processEvents()


def _bande_de_mat(scene):
    """La bande de neutre AUTOUR du contenu, et sa largeur reelle.

    La bande est definie par la geometrie effective du contenu dans son
    cadre : c'est cela que `{spacing.mat-min}` contraint, et non un
    rectangle theorique.
    """
    cadre = scene.rect()
    contenu = scene.contenu.geometry()
    marges = (
        contenu.left() - cadre.left(),
        contenu.top() - cadre.top(),
        cadre.right() - contenu.right(),
        cadre.bottom() - contenu.bottom(),
    )
    return cadre, contenu, marges


#: F9 (revue vague 3, mutant M22) -- un inventaire declare a la main
#: (`couleurs_posees`) peut diverger de ce que la feuille de style peint
#: reellement : `#viewer-stage { background: {COULEURS['accent']} }` avec
#: `couleurs_posees` laisse a `image-mat` passait les 404 tests. Le verdict
#: doit donc venir de la feuille de style EFFECTIVE du widget -- ce que Qt
#: applique tel quel pour peindre -- et non d'un champ que la production
#: tient a jour de bonne foi.
_HEXADECIMAL_DANS_LA_FEUILLE_DE_STYLE = re.compile(r"#[0-9A-Fa-f]{6}")


def _couleurs_de_la_feuille_de_style(widget):
    """Les couleurs REELLEMENT peintes par ce widget, lues dans sa QSS.

    `QWidget.styleSheet()` rend le texte que Qt applique pour peindre ce
    widget precis -- c'est la source de peinture elle-meme, pas une
    declaration a cote. Un widget sans feuille de style ne peint aucune
    couleur par ce mecanisme et rend donc un tuple vide.
    """
    return tuple(_HEXADECIMAL_DANS_LA_FEUILLE_DE_STYLE.findall(widget.styleSheet()))


def _couleurs_posees_dans_la_bande(scene):
    """Toutes les couleurs posees dans la bande de `mat-min` de cette scene.

    On parcourt **tous** les descendants du cadre -- l'ensemble complet,
    jamais un echantillon --, on retient ceux qui MORDENT sur la bande,
    c'est-a-dire qui ne tiennent pas entierement dans le contenu, et on
    collecte les couleurs que leur feuille de style EFFECTIVE peint. La
    scene elle-meme en fait partie : c'est elle qui peint le mat et sa
    bordure.

    Le contenu d'image est exclu **par definition** : la bande est « autour
    du contenu », et une surimpression posee SUR l'image est la seule
    exception admise par `DESIGN.md`.
    """
    _cadre, contenu, _marges = _bande_de_mat(scene)
    couleurs = list(_couleurs_de_la_feuille_de_style(scene))
    for widget in scene.findChildren(QWidget):
        if widget is scene.contenu:
            continue
        if contenu.contains(widget.geometry()):
            continue
        couleurs.extend(_couleurs_de_la_feuille_de_style(widget))
    return couleurs


def test_la_bande_autour_de_toute_image_fait_au_moins_mat_min(qtbot):
    """`{spacing.mat-min}` (16 px) est un MINIMUM, pas un padding."""
    _atelier, scenes = _surfaces(qtbot)
    plancher = jetons.ESPACEMENTS["mat-min"]
    for scene in scenes:
        cadre, contenu, marges = _bande_de_mat(scene)
        assert contenu.width() > 0 and contenu.height() > 0, (
            f"contenu sans surface dans {scene.objectName()} : la bande ne "
            "mesurerait rien"
        )
        assert cadre.contains(contenu)
        for marge in marges:
            assert marge >= plancher, (scene.objectName(), marges)


def test_aucune_chromie_n_entre_dans_la_bande_mat_min(qtbot):
    _atelier, scenes = _surfaces(qtbot)
    for scene in scenes:
        couleurs = _couleurs_posees_dans_la_bande(scene)
        assert couleurs, "la bande ne mesurerait rien"
        for couleur in couleurs:
            assert _est_neutre(couleur), (
                f"chromie dans la bande mat-min de {scene.objectName()} : "
                f"{couleur}"
            )
        # Et la seule exception admise -- une surimpression posee SUR
        # l'image -- est bien, elle, chromatique : sans cela le test ne
        # distinguerait pas « pas de chromie » de « pas de couleur du tout ».
        assert any(
            not _est_neutre(couleur)
            for couleur in scene.contenu.couleurs_posees
        )


def test_le_banc_de_la_bande_mat_min_MORD_sur_un_temoin(qtbot):
    """Le symetrique : sans lui, la bande pourrait etre verte et vide.

    On pose un temoin CHROMATIQUE dans la bande d'une scene jetable, et le
    balayage doit le voir. Le temoin peint via sa feuille de style REELLE
    (`setStyleSheet`), jamais via un inventaire declare a cote : c'est
    exactement le mecanisme que F9 corrige, et un temoin qui ne poserait
    qu'un attribut `couleurs_posees` ne prouverait plus rien sur lui.
    """
    scene = surimpressions.ScenePlanche()
    qtbot.addWidget(scene)
    scene.resize(400, 300)
    scene.show()
    _appliquer_les_layouts(scene)
    temoin = QLabel(scene)
    temoin.setObjectName("temoin-chromatique")
    temoin.setStyleSheet(f"background: {jetons.COULEURS['accent']};")
    temoin.setGeometry(0, 0, 8, 8)   # dans la bande, en haut a gauche
    couleurs = _couleurs_posees_dans_la_bande(scene)
    assert jetons.COULEURS["accent"] in couleurs
    assert not all(_est_neutre(couleur) for couleur in couleurs)


def test_la_bande_mesure_la_feuille_de_style_et_pas_un_inventaire_declare(qtbot):
    """F9 -- reproduit exactement le mutant M22 au niveau du test.

    Un widget qui DECLARE `couleurs_posees` neutre tout en peignant, par sa
    feuille de style, une couleur chromatique doit faire echouer le
    balayage : c'est la divergence que `getattr(widget, "couleurs_posees",
    ())` ne pouvait pas voir.
    """
    scene = surimpressions.ScenePlanche()
    qtbot.addWidget(scene)
    scene.resize(400, 300)
    scene.show()
    _appliquer_les_layouts(scene)
    menteur = QLabel(scene)
    menteur.setObjectName("temoin-menteur")
    #: L'inventaire declare dit "neutre" -- exactement ce que M22 laisse
    #: `couleurs_posees` affirmer pendant que le fond reel devient chromatique.
    menteur.couleurs_posees = (jetons.COULEURS["border"],)
    menteur.setStyleSheet(f"background: {jetons.COULEURS['accent']};")
    menteur.setGeometry(0, 0, 8, 8)
    couleurs = _couleurs_posees_dans_la_bande(scene)
    assert jetons.COULEURS["accent"] in couleurs
    assert not all(_est_neutre(couleur) for couleur in couleurs)


def test_le_mat_et_le_papier_sont_strictement_neutres():
    for nom in ("image-mat", "paper", "overlay-halo", "overlay-handle", "border"):
        assert _est_neutre(jetons.COULEURS[nom]), nom


# ---------------------------------------------------------------------------
# (J) -- les trois familles de traits portent exactement leurs jetons
# ---------------------------------------------------------------------------


def test_les_trois_familles_portent_exactement_leurs_jetons():
    assert surimpressions.JETON_COULEUR_PAR_FAMILLE == {
        surimpressions.FAMILLE_ZONE: "accent",
        surimpressions.FAMILLE_MARQUEUR: "state-complete",
        surimpressions.FAMILLE_QR_NON_DECODE: "state-substitute",
    }
    couleurs = {
        famille: jetons.COULEURS[jeton]
        for famille, jeton in surimpressions.JETON_COULEUR_PAR_FAMILLE.items()
    }
    assert couleurs[surimpressions.FAMILLE_ZONE] == jetons.COULEURS["accent"]
    assert couleurs[surimpressions.FAMILLE_MARQUEUR] == jetons.COULEURS["state-complete"]
    assert (
        couleurs[surimpressions.FAMILLE_QR_NON_DECODE]
        == jetons.COULEURS["state-substitute"]
    )
    # Trois familles, trois couleurs DIFFERENTES : deux familles de meme
    # couleur seraient une fusion silencieuse.
    assert len(set(couleurs.values())) == 3
    assert jetons.COULEURS["overlay-halo"] == "#000000"


def test_les_traits_tiennent_le_plancher_non_textuel_contre_le_halo_et_le_mat():
    """Ratios CALCULES, jamais copies du module teste."""
    halo = jetons.COULEURS["overlay-halo"]
    mat = jetons.COULEURS["image-mat"]
    plancher = jetons.CONTRASTE_NON_TEXTUEL_MIN
    for famille, jeton in surimpressions.JETON_COULEUR_PAR_FAMILLE.items():
        trait = jetons.COULEURS[jeton]
        assert _ratio(trait, halo) >= plancher, (famille, "halo", _ratio(trait, halo))
        assert _ratio(trait, mat) >= plancher, (famille, "mat", _ratio(trait, mat))
    # Le halo lui-meme doit se detacher du papier, sinon il ne sert a rien
    # sur une marge blanche.
    assert _ratio(halo, jetons.COULEURS["paper"]) >= plancher


# ---------------------------------------------------------------------------
# Grep de frontiere : zero geometrie de surimpression en dur
# ---------------------------------------------------------------------------


def _constantes_numeriques(nom_de_module):
    arbre = ast.parse((_PAQUET_GUI / nom_de_module).read_text(encoding="utf-8"))
    return [
        noeud.value
        for noeud in ast.walk(arbre)
        if isinstance(noeud, ast.Constant)
        and isinstance(noeud.value, (int, float))
        and not isinstance(noeud.value, bool)
    ]


def test_zero_litteral_de_geometrie_de_surimpression_hors_jetons():
    """1,5 (trait), 11 (poignee) et 0,32 (opacite) n'existent nulle part ailleurs."""
    interdits = {
        jetons.SURIMPRESSIONS["trait-px"],
        jetons.SURIMPRESSIONS["poignee-px"],
        jetons.OPACITE_VIGNETTE_NON_DESIGNEE,
    }
    for nom in ("scan_jugement.py", "surimpressions.py", "barre_de_vue.py",
                "raster_de_page.py", "lecture_detection.py"):
        trouves = sorted(set(_constantes_numeriques(nom)) & interdits)
        assert trouves == [], f"geometrie de surimpression en dur dans {nom} : {trouves}"


def test_la_largeur_de_chaque_trait_est_LUE_du_module_de_jetons():
    """`halo-px` vaut 3, valeur trop banale pour un grep de litteral.

    On mesure donc l'autre bout : **aucun** appel `QPen` du module de dessin
    ne prend une largeur litterale -- elles viennent toutes d'une lecture de
    jeton.
    """
    arbre = ast.parse(
        (_PAQUET_GUI / "surimpressions.py").read_text(encoding="utf-8")
    )
    stylos = [
        noeud for noeud in ast.walk(arbre)
        if isinstance(noeud, ast.Call)
        and getattr(noeud.func, "id", "") == "QPen"
    ]
    assert len(stylos) >= 2, "le banc ne mesurerait aucun trait"
    for stylo in stylos:
        assert len(stylo.args) == 2
        largeur = stylo.args[1]
        assert not isinstance(largeur, ast.Constant), (
            f"largeur de trait litterale : {ast.dump(largeur)}"
        )
        assert isinstance(largeur, ast.Name), ast.dump(largeur)
    # Et les deux noms utilises sont bien alimentes par le module de jetons.
    source = (_PAQUET_GUI / "surimpressions.py").read_text(encoding="utf-8")
    assert 'jetons.SURIMPRESSIONS["halo-px"]' in source
    assert 'jetons.SURIMPRESSIONS["trait-px"]' in source


def test_le_remplissage_des_surimpressions_est_toujours_none():
    """`overlay-zone.fill: none` : traits, **jamais aplats**."""
    source = (_PAQUET_GUI / "surimpressions.py").read_text(encoding="utf-8")
    assert "NoBrush" in source
    assert "setBrush(QBrush" not in source
    assert "fillRect(rectangle" not in source
