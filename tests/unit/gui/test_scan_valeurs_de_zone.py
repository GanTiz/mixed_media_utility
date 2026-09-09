# -*- coding: utf-8 -*-
"""Story 7.4, AC 3 -- taille en pixels et timecode d'une zone.

Deux valeurs, deux provenances, un seul endroit ou les poser : **hors du
contenu d'image et hors du panneau lateral**.
"""

import ast
import re
from pathlib import Path

from PySide6.QtWidgets import QLabel, QWidget

import fabriques_detection as fab
from mixed_media_utility.gui import scan_jugement, catalogue, jetons
from mixed_media_utility.gui import lecture_detection as lecture
from mixed_media_utility.gui import surimpressions

_PAQUET_GUI = Path(jetons.__file__).resolve().parent

#: Les modules d'ecran DE CETTE STORY. Le grep de frontiere porte sur eux, et
#: sur eux seuls : les modules d'autres stories ont leurs propres frontieres.
MODULES_DE_LA_STORY = (
    "scan_jugement.py",
    "barre_de_vue.py",
    "lecture_detection.py",
    "raster_de_page.py",
    "surimpressions.py",
)


def _sources_de_la_story():
    """Le CODE des modules de la story, docstrings et commentaires retires.

    Le grep porte sur ce qui s'EXECUTE, jamais sur ce qui se lit : une
    docstring qui NOMME un interdit -- pour dire qu'on ne l'appelle pas --
    est exactement ce que ce depot demande d'ecrire, et un grep brut la
    prendrait pour une infraction. Retirer les docstrings est fait par
    l'AST, donc sans heuristique de texte.
    """
    sources = {}
    for nom in MODULES_DE_LA_STORY:
        chemin = _PAQUET_GUI / nom
        assert chemin.is_file(), f"module de la story introuvable : {nom}"
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if not isinstance(
                noeud,
                (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
            ):
                continue
            corps = noeud.body
            if (
                corps
                and isinstance(corps[0], ast.Expr)
                and isinstance(corps[0].value, ast.Constant)
                and isinstance(corps[0].value.value, str)
            ):
                del corps[0]
                if not corps:
                    corps.append(ast.Pass())
        sources[nom] = ast.unparse(ast.fix_missing_locations(arbre))
    return sources


def _vue(qtbot, page):
    vue = scan_jugement.VueModePdf(catalogue.CHAINES)
    qtbot.addWidget(vue)
    vue.resize(1200, 800)
    vue.show()
    vue.poser(page)
    return vue


def _trois_zones(rang, index):
    """TROIS zones de tailles differentes -- jamais un remplissage uniforme."""
    return [
        fab.zone(0, rang, index, largeur_px=1337, hauteur_px=752),
        fab.zone(1, rang, index, largeur_px=1401, hauteur_px=799),
        fab.zone(2, rang, index, largeur_px=1522, hauteur_px=811),
    ]


def test_la_lecture_de_la_zone_2_rend_SES_valeurs_et_non_celles_de_la_zone_0(qtbot):
    rang, index = fab.ADRESSE_CIBLE
    document = lecture.depuis_json(
        fab.deux_pages_cible_seconde(zones=_trois_zones(rang, index))
    )
    page = document.page_par_adresse(rang, index)
    vue = _vue(qtbot, page)
    legendes = {
        legende.slot_index: legende
        for legende in vue.legendes.findChildren(scan_jugement.LegendeDeZone)
    }
    assert sorted(legendes) == [0, 1, 2]
    zone_2 = page.zone(2)
    assert legendes[2].taille.text() == catalogue.CHAINES["scan-zone-taille"].format(
        largeur=zone_2.crop_w_px, hauteur=zone_2.crop_h_px
    )
    assert legendes[2].timecode.text() == zone_2.frame_timecode
    # Et surtout : ce ne sont PAS celles de la zone 0.
    assert legendes[2].taille.text() != legendes[0].taille.text()
    assert legendes[2].timecode.text() != legendes[0].timecode.text()


def test_permuter_deux_zones_dans_la_fixture_fait_diverger_les_legendes(qtbot):
    rang, index = fab.ADRESSE_CIBLE

    def legendes(permutee):
        zones = _trois_zones(rang, index)
        if permutee:
            # On echange les GEOMETRIES, pas les `slot_index` : c'est
            # l'appariement emplacement <-> valeurs qui est mesure.
            for cle in ("crop_rect_px", "zone_rect_px", "frame_timecode"):
                zones[0][cle], zones[2][cle] = zones[2][cle], zones[0][cle]
        document = lecture.depuis_json(
            fab.deux_pages_cible_seconde(zones=zones)
        )
        vue = _vue(qtbot, document.page_par_adresse(rang, index))
        return {
            legende.slot_index: (legende.taille.text(), legende.timecode.text())
            for legende in vue.legendes.findChildren(scan_jugement.LegendeDeZone)
        }

    assert legendes(False) != legendes(True)


def test_la_taille_vient_des_crop_px_et_jamais_des_zone_px(qtbot):
    """Les deux conventions de quantification du coeur ne coincident pas.

    5.2 arrondit l'origine et la taille **separement** : 54 zones sur 135 a
    600 ppp ont un bord qui differe d'un pixel. La fixture les fait donc
    diverger explicitement, et l'AC exige la valeur DE DECOUPE.
    """
    rang, index = fab.ADRESSE_CIBLE
    zones = _trois_zones(rang, index)
    zones[1]["zone_rect_px"] = {"x": 140, "y": 260, "width": 1400, "height": 798}
    assert zones[1]["crop_rect_px"]["width"] != zones[1]["zone_rect_px"]["width"]
    assert zones[1]["crop_rect_px"]["height"] != zones[1]["zone_rect_px"]["height"]
    document = lecture.depuis_json(fab.deux_pages_cible_seconde(zones=zones))
    page = document.page_par_adresse(rang, index)
    vue = _vue(qtbot, page)
    legende = next(
        widget for widget in vue.legendes.findChildren(scan_jugement.LegendeDeZone)
        if widget.slot_index == 1
    )
    zone = page.zone(1)
    assert (zone.crop_w_px, zone.crop_h_px) != (zone.zone_w_px, zone.zone_h_px)
    # Chiffre pour chiffre.
    assert str(zone.crop_w_px) in legende.taille.text()
    assert str(zone.crop_h_px) in legende.taille.text()
    assert str(zone.zone_w_px) not in legende.taille.text()


def test_une_zone_sans_timecode_rend_une_absence_NOMMEE(qtbot):
    rang, index = fab.ADRESSE_CIBLE
    zones = _trois_zones(rang, index)
    zones[2]["frame_timecode"] = None   # la CIBLE n'est pas la premiere
    document = lecture.depuis_json(fab.deux_pages_cible_seconde(zones=zones))
    vue = _vue(qtbot, document.page_par_adresse(rang, index))
    legendes = {
        legende.slot_index: legende
        for legende in vue.legendes.findChildren(scan_jugement.LegendeDeZone)
    }
    absente = legendes[2]
    assert absente.timecode_est_absent
    assert absente.timecode.text() == catalogue.CHAINES["scan-zone-timecode-absent"]
    # Ni zero, ni tiret muet : un `--:--:--:--` sans mot dirait « pas
    # d'image », et ce n'est pas ce que le champ dit.
    assert "--:--" not in absente.timecode.text()
    assert absente.timecode.text().strip("-: ") != ""
    # Les deux autres gardent LEUR timecode.
    assert legendes[0].timecode.text() and not legendes[0].timecode_est_absent
    assert legendes[1].timecode.text() != legendes[0].timecode.text()


def test_aucune_valeur_n_est_incrustee_sur_l_image_ni_au_panneau_lateral(qtbot):
    """Les deux interdits croises : le Don't et `EPIC7-ARB-22`.

    Confirme et durci par `EPIC7-ARB-68` : « Aucune valeur -- taille,
    timecode, rang -- n'est posee en surimpression permanente sur une image
    de frame. »
    """
    rang, index = fab.ADRESSE_CIBLE
    document = lecture.depuis_json(
        fab.deux_pages_cible_seconde(zones=_trois_zones(rang, index))
    )
    page = document.page_par_adresse(rang, index)
    vue = _vue(qtbot, page)
    valeurs = set()
    for zone in page.page.frame_zones:
        valeurs.add(str(zone.crop_w_px))
        valeurs.add(str(zone.crop_h_px))
        valeurs.add(zone.frame_timecode)

    contenu = vue.scene.contenu
    assert isinstance(contenu, surimpressions.ContenuDImage)
    # Le contenu d'image n'a AUCUN descendant : c'est structurel, et c'est ce
    # qui rend impossible qu'une valeur s'y incruste.
    assert contenu.findChildren(QWidget) == []
    # Et le module de dessin ne peint aucun texte : `drawText` n'y est pas.
    source = (_PAQUET_GUI / "surimpressions.py").read_text(encoding="utf-8")
    assert "drawText" not in source

    # Le panneau lateral de cette vue n'en porte pas non plus.
    textes_du_panneau = {
        etiquette.text()
        for etiquette in vue.panneau_lateral.findChildren(QLabel)
    }
    assert valeurs.isdisjoint(textes_du_panneau)
    assert not any(
        any(valeur in texte for valeur in valeurs if valeur)
        for texte in textes_du_panneau
    )


# ---------------------------------------------------------------------------
# Greps de frontiere de l'AC 3
# ---------------------------------------------------------------------------


def test_zero_conversion_mm_vers_px_et_zero_constante_de_dpi():
    """« La taille en pixels d'une zone se calcule, elle ne se lit pas. »

    Verbatim `EPIC7-ARB-15` -- et c'est le COEUR qui la calcule. La GUI la
    lit des `crop_*_px` du document, sans jamais toucher aux millimetres.
    """
    interdits = re.compile(
        r"mm_to_px|px_to_mm|_mm\s*\*|\*\s*dpi|dpi\s*/|/\s*25\.4|25\.4\s*|"
        r"POINTS_PER_INCH|page_size_px\(",
    )
    fautifs = {}
    for nom, source in _sources_de_la_story().items():
        trouves = sorted(set(interdits.findall(source)))
        if trouves:
            fautifs[nom] = trouves
    assert fautifs == {}, f"arithmetique de conversion dans gui/ : {fautifs}"


def test_zero_lecture_du_payload_qr_pour_produire_une_taille():
    """Seul le TIMECODE vient du QR, jamais la taille (`EPIC7-ARB-15`)."""
    for nom, source in _sources_de_la_story().items():
        assert '["payload"]' not in source, nom
        assert ".payload" not in source, nom
        assert "decode_payload" not in source, nom


def test_zero_appel_de_fonction_geometrique_du_coeur():
    """La GUI lit un document ; elle ne refait aucune geometrie (AC 1)."""
    interdits = (
        "compute_template_homography",
        "resolve_page_geometry",
        "build_page_crop_plan",
        "warpPerspective",
        "findHomography",
    )
    fautifs = {}
    for nom, source in _sources_de_la_story().items():
        trouves = [interdit for interdit in interdits if interdit in source]
        if trouves:
            fautifs[nom] = trouves
    assert fautifs == {}, f"geometrie du coeur rappelee dans gui/ : {fautifs}"


def test_le_grep_de_geometrie_mord_sur_un_module_temoin(tmp_path):
    """Le symetrique : la comparaison echoue vraiment quand elle doit.

    Le motif « un test peut etre vert et vide » a deja ete paye dans ce
    depot ; le grep est donc exerce sur un temoin fautif.
    """
    temoin = "largeur = compute_template_homography(page) * dpi / 25.4\n"
    interdits = ("compute_template_homography", "resolve_page_geometry")
    assert [i for i in interdits if i in temoin] == [
        "compute_template_homography"
    ]
    conforme = "largeur = zone.crop_w_px\n"
    assert [i for i in interdits if i in conforme] == []
