# -*- coding: utf-8 -*-
"""Story 7.4, AC 8 -- la bascule brut / corrige est GLOBALE (``EPIC7-ARB-69``).

Interdit mesure, verbatim : « Aucun ecran ne porte sa propre bascule locale,
ni un etat de calibration qui lui soit propre. »

Ce banc mesure la difference entre **global** et **local**, ce qu'un test sur
un seul ecran ne saurait pas faire.
"""

import ast
import json
from pathlib import Path

from PySide6.QtGui import QColor, QImage

import fabriques_detection as fab
import fabriques_scan as fab_scan
from mixed_media_utility.gui import barre_de_vue, catalogue, jetons
from mixed_media_utility.gui import coquille as coquille_module
from mixed_media_utility.gui import lecture_detection as lecture
from mixed_media_utility.gui import modele_chutier, raster_de_page, scan_jugement
from mixed_media_utility.gui.coquille import Coquille

_PAQUET_GUI = Path(jetons.__file__).resolve().parent

#: Deux images DISTINGUABLES, une par variante : sans cela la bascule
#: pourrait ne rien changer et le test rester vert.
COULEUR_BRUTE = QColor(40, 40, 40)
COULEUR_CORRIGEE = QColor(200, 200, 200)


def _image(couleur):
    image = QImage(64, 48, QImage.Format.Format_RGB888)
    image.fill(couleur)
    return image


def _montage(qtbot, avec_source_corrigee=True):
    """Une coquille, un atelier branche sur SA preference, un document."""
    document = lecture.depuis_json(fab.deux_pages_cible_seconde())
    images = {}
    for page in document.pages:
        images[(page.adresse, raster_de_page.IMAGE_BRUTE)] = _image(COULEUR_BRUTE)
        if avec_source_corrigee:
            images[(page.adresse, raster_de_page.IMAGE_CORRIGEE)] = _image(
                COULEUR_CORRIGEE
            )
    fournisseur = raster_de_page.FournisseurDeTest(images)

    coquille = Coquille()
    qtbot.addWidget(coquille)
    coquille.preference_image.poser_disponibilite(avec_source_corrigee)
    coquille.bascule_image.rafraichir()

    atelier = scan_jugement.AtelierScanJugement(
        catalogue.CHAINES, coquille.preference_image, fournisseur
    )
    qtbot.addWidget(atelier)
    atelier.resize(1200, 800)
    atelier.show()
    atelier.poser_document(document, document.page_par_adresse(*fab.ADRESSE_CIBLE))
    return coquille, atelier, document


def _teinte(image):
    assert image is not None
    return image.pixelColor(0, 0).red()


# ---------------------------------------------------------------------------
# Global contre local : deux surfaces, une seule bascule, la meme session
# ---------------------------------------------------------------------------


def test_le_CONTRAT_DE_WIDGET_relie_deux_surfaces_a_une_seule_preference(qtbot):
    """Ce que ce test mesure, et ce qu'il NE mesure PAS.

    Il mesure le **contrat de widget** : un atelier de jugement construit sur
    la preference d'une coquille voit ses deux surfaces changer ensemble. Il
    ne mesure **pas** l'application, parce qu'il fait le cablage lui-meme --
    `AtelierScanJugement(...)` est appele ici, dans le banc.

    Son nom promettait la coquille avant la revue de vague 3 (finding F2) :
    aucun module de `src/` ne faisait ce cablage, si bien que la seule preuve
    de l'AC 8 portait sur deux widgets poses cote a cote par un test. La
    mesure sur l'application ASSEMBLEE est
    `test_la_bascule_de_l_EN_TETE_traverse_la_surface_de_jugement_ASSEMBLEE`,
    plus bas ; celui-ci reste, parce qu'un contrat de widget est ce qui tient
    quand la coquille change de forme.
    """
    coquille, atelier, _document = _montage(qtbot)
    mode_pdf = atelier.vue_page.scene.contenu
    galerie = atelier.vue_galerie.lignes[0].apercu.contenu
    assert mode_pdf is not galerie, "deux surfaces DISTINCTES, pas deux vues d'une"

    assert _teinte(mode_pdf.image) == COULEUR_BRUTE.red()
    assert _teinte(galerie.image) == COULEUR_BRUTE.red()

    # Le geste : le bouton de l'EN-TETE de la coquille, rien d'autre.
    coquille.bascule_image.click()
    assert coquille.preference_image.variante == raster_de_page.IMAGE_CORRIGEE

    assert _teinte(mode_pdf.image) == COULEUR_CORRIGEE.red()
    assert _teinte(galerie.image) == COULEUR_CORRIGEE.red()

    coquille.bascule_image.click()
    assert _teinte(mode_pdf.image) == COULEUR_BRUTE.red()
    assert _teinte(galerie.image) == COULEUR_BRUTE.red()


def test_la_troisieme_surface_suit_elle_aussi(qtbot):
    """La vue vignette unique lit la meme preference : aucune copie locale."""
    coquille, atelier, _document = _montage(qtbot)
    rang, index = fab.ADRESSE_CIBLE
    atelier.ouvrir_la_frame((rang, index, 1))
    vignette = atelier.vue_frame.scene.contenu
    assert _teinte(vignette.image) == COULEUR_BRUTE.red()
    coquille.bascule_image.click()
    assert _teinte(vignette.image) == COULEUR_CORRIGEE.red()


def test_la_valeur_survit_a_un_aller_retour_d_onglets_et_a_un_changement_de_lot(
    qtbot,
):
    coquille, atelier, _document = _montage(qtbot)
    coquille.bascule_image.click()
    assert coquille.preference_image.variante == raster_de_page.IMAGE_CORRIGEE

    # Aller-retour sur la barre d'onglets d'ateliers de la coquille.
    depart = coquille.barre_onglets.currentIndex()
    for indice in range(len(coquille.ateliers())):
        coquille.activer_atelier(indice)
    coquille.activer_atelier(depart)
    assert coquille.barre_onglets.currentIndex() == depart
    assert coquille.preference_image.variante == raster_de_page.IMAGE_CORRIGEE

    # Aller-retour sur les onglets de VUE de l'atelier.
    atelier.onglets.activer(barre_de_vue.ONGLET_GALERIE)
    atelier.onglets.activer(barre_de_vue.ONGLET_PAGE)
    assert coquille.preference_image.variante == raster_de_page.IMAGE_CORRIGEE

    # Changement de lot : un autre document, la meme preference.
    autre = lecture.depuis_json(fab.deux_pages_cible_seconde())
    atelier.poser_document(autre)
    assert coquille.preference_image.variante == raster_de_page.IMAGE_CORRIGEE
    assert atelier.vue_page.variante_dimage == raster_de_page.IMAGE_CORRIGEE


# ---------------------------------------------------------------------------
# L'AC 8 sur l'APPLICATION ASSEMBLEE (finding F2, `EPIC7-ARB-74`)
# ---------------------------------------------------------------------------
#
# Ce que les trois tests ci-dessus ne savent pas faire : ils construisent
# `AtelierScanJugement` eux-memes. Tant qu'aucun module de `src/` ne le
# construisait, l'AC 8 -- « mesuree en basculant DEPUIS LA COQUILLE » --
# n'etait prouvee que par contrat de widget. Ici la coquille est SEULE, et la
# surface de jugement s'atteint par le geste de l'operatrice.


#: Les deux familles de teintes, et **une valeur par page dans chacune** : un
#: appariement inverse entre une page et sa surface ne se verrait pas sur un
#: remplissage uniforme (regle des fabriques, famille du mutant M33).
_TEINTE_BRUTE = 40
_TEINTE_CORRIGEE = 200


def _teinte_attendue(read_rank, variante):
    """La teinte de cette page dans cette variante. Deux familles disjointes."""
    base = (
        _TEINTE_CORRIGEE
        if variante == raster_de_page.IMAGE_CORRIGEE
        else _TEINTE_BRUTE
    )
    return base + read_rank


class _FournisseurDeBanc:
    """La SEULE substitution du banc assemble : la source des images.

    Elle est necessaire et bornee : le depot ne contient **aucune** image
    corrigee (`EPIC5-ARB-5`, la calibration active est post-MVP), donc le
    vrai `FournisseurDeProjet` declare la variante corrigee indisponible et
    la bascule ne changerait jamais rien nulle part. Tout le reste du chemin
    -- l'ouverture du projet, la relecture du document, l'ouverture du scan,
    la construction de l'atelier, le branchement de la preference -- est
    celui de l'application.

    Il retient aussi `racine` et `dpi` : c'est ce qui mesure que le dpi de
    rendu vient du DOCUMENT et non d'une constante de la GUI.
    """

    def __init__(self, racine, dpi):
        self.racine = racine
        self.dpi = dpi

    def variante_disponible(self, variante):
        return variante in raster_de_page.VARIANTES_D_IMAGE

    def image(self, page, variante=raster_de_page.IMAGE_BRUTE):
        read_rank, _page_index = page.adresse
        return _image(QColor(_teinte_attendue(read_rank, variante), 0, 0))


#: La CIBLE : la seconde page du SECOND lot (`lot-scan-18`), donc le dernier
#: noeud de scan de l'arbre -- jamais le premier. Un chemin qui rendrait
#: toujours le premier document, ou la premiere page, ne se demasquerait pas
#: autrement. Elle est aussi la page dont `read_rank` (2) et `page_index` (2)
#: coincident le moins avec ceux de sa voisine (rang 1, planche 0).
_RANG_CIBLE = 2
_PLANCHE_CIBLE = 2
_RANG_VOISIN = 1


def _projet_avec_deux_lots(tmp_path):
    """Un projet REEL sur le disque : son manifest et ses deux documents.

    Les documents sont ecrits la ou le coeur les ecrit et dans la forme
    canonique qu'il pose : la coquille les relit par son propre chemin, sans
    qu'aucune valeur ne lui soit passee de la main a la main.
    """
    projet = tmp_path / "projet"
    projet.mkdir(parents=True, exist_ok=True)
    manifest = fab_scan.manifest_des_deux_lot()
    (projet / "project.json").write_text(json.dumps(manifest), encoding="utf-8")
    fab_scan.ecrire_les_documents(
        projet, list(fab_scan.deux_documents_aux_completudes_differentes())
    )
    return projet, manifest


def _noeuds_de_scan(coquille):
    """Les noeuds de scan de l'arbre du chutier, dans l'ordre de l'arbre."""
    return [
        noeud
        for noeud in modele_chutier.parcourir(coquille.racines())
        if noeud.type == modele_chutier.TYPE_SCAN
    ]


def _coquille_sur_le_projet(qtbot, tmp_path):
    """Une coquille SEULE, un projet ouvert, la fabrique de source substituee."""
    projet, manifest = _projet_avec_deux_lots(tmp_path)
    coquille = Coquille()
    qtbot.addWidget(coquille)
    fournisseurs = []

    def fabrique(racine, dpi):
        fournisseur = _FournisseurDeBanc(racine, dpi)
        fournisseurs.append(fournisseur)
        return fournisseur

    coquille.fabrique_de_fournisseur = fabrique
    coquille.ouvrir_projet(projet, manifest)
    return coquille, projet, fournisseurs


def test_la_bascule_de_l_EN_TETE_traverse_la_surface_de_jugement_ASSEMBLEE(
    qtbot, tmp_path
):
    """AC 8 sur l'application : le banc ne construit PAS `AtelierScanJugement`.

    Il construit la coquille seule, ouvre un projet, puis atteint le second
    temps de l'atelier Scan par le geste de l'operatrice -- le double-clic qui
    OUVRE un scan au chutier (`EPIC7-ARB-11`, `Coquille.ouvrir`). C'est ce
    test qui rend l'AC 8 vraie au sens ou elle est ecrite (« mesuree en
    basculant depuis la coquille ») : avant lui, la seule preuve etait deux
    widgets cables a la main par un banc.
    """
    coquille, projet, fournisseurs = _coquille_sur_le_projet(qtbot, tmp_path)

    # Rien n'est encore juge : la page du Scan est a son PREMIER temps.
    assert coquille.temps_du_scan_courant() is coquille.atelier_scan
    assert fournisseurs == []

    scans = _noeuds_de_scan(coquille)
    cibles = [
        noeud for noeud in scans
        if noeud.read_rank == _RANG_CIBLE and noeud.page_index == _PLANCHE_CIBLE
    ]
    assert len(cibles) == 1, [n.identifiant for n in scans]
    cible = cibles[0]
    assert scans.index(cible) > 0, "la cible n'est jamais en premiere position"

    # LE GESTE : ouvrir le scan au chutier. Rien d'autre.
    assert coquille.ouvrir(cible.identifiant) == coquille_module.CLE_ATELIER_SCAN
    assert coquille.atelier_courant() == coquille_module.CLE_ATELIER_SCAN
    # La page du Scan est passee a son SECOND temps, et c'est la coquille qui
    # a construit la surface -- le banc ne l'a jamais instanciee.
    assert coquille.temps_du_scan_courant() is coquille.atelier_jugement

    # Le dpi de rendu vient du DOCUMENT (`subject.scan_dpi_detection`), lu et
    # non choisi par la GUI.
    assert [(f.racine, f.dpi) for f in fournisseurs] == [(projet, 600)]

    atelier = coquille.atelier_jugement
    mode_pdf = atelier.vue_page.scene.contenu
    # La galerie affiche par numero de planche (`EPIC7-ARB-76`) : la planche 0
    # d'abord, le trou de la planche 1, la CIBLE en seconde ligne.
    assert atelier.vue_galerie.suite_rendue == (
        ("page", (_RANG_VOISIN, 0)),
        ("trou", 1),
        ("page", (_RANG_CIBLE, _PLANCHE_CIBLE)),
    )
    galerie_cible = atelier.vue_galerie.lignes[1].apercu.contenu
    galerie_voisine = atelier.vue_galerie.lignes[0].apercu.contenu
    assert mode_pdf is not galerie_cible, "deux surfaces DISTINCTES"

    brute = raster_de_page.IMAGE_BRUTE
    corrigee = raster_de_page.IMAGE_CORRIGEE
    assert _teinte(mode_pdf.image) == _teinte_attendue(_RANG_CIBLE, brute)
    assert _teinte(galerie_cible.image) == _teinte_attendue(_RANG_CIBLE, brute)
    assert _teinte(galerie_voisine.image) == _teinte_attendue(_RANG_VOISIN, brute)

    # LE GESTE : le bouton de l'en-tete de la coquille, rien d'autre.
    assert coquille.bascule_image.isEnabled()
    coquille.bascule_image.click()
    assert coquille.preference_image.variante == corrigee

    assert _teinte(mode_pdf.image) == _teinte_attendue(_RANG_CIBLE, corrigee)
    assert _teinte(galerie_cible.image) == _teinte_attendue(_RANG_CIBLE, corrigee)
    assert _teinte(galerie_voisine.image) == _teinte_attendue(_RANG_VOISIN, corrigee)

    # Et le retour, sur le meme bouton.
    coquille.bascule_image.click()
    assert _teinte(mode_pdf.image) == _teinte_attendue(_RANG_CIBLE, brute)
    assert _teinte(galerie_cible.image) == _teinte_attendue(_RANG_CIBLE, brute)


def test_ouvrir_un_scan_ne_MONTE_pas_la_surface_pour_les_autres_objets(
    qtbot, tmp_path
):
    """Le volet symetrique : sans lui, un cablage inconditionnel serait vert.

    Ouvrir un LOT mene a l'atelier Pdf (`EPIC7-ARB-11`) et laisse la page du
    Scan a son premier temps ; seul l'ouverture d'un scan la fait basculer.
    """
    coquille, _projet, fournisseurs = _coquille_sur_le_projet(qtbot, tmp_path)
    lots = [
        noeud
        for noeud in modele_chutier.parcourir(coquille.racines())
        if noeud.type == modele_chutier.TYPE_LOT
    ]
    assert len(lots) == 2, [n.identifiant for n in lots]
    # La CIBLE est le SECOND lot : un parcours qui rendrait toujours le
    # premier ne se demasquerait pas autrement.
    assert coquille.ouvrir(lots[1].identifiant) == "atelier-pdf"
    assert coquille.temps_du_scan_courant() is coquille.atelier_scan
    assert fournisseurs == []


def test_revenir_au_PREMIER_temps_sans_controle_neuf(qtbot, tmp_path):
    """Detecter ramene au temps 1, et changer de projet aussi.

    Aucun bouton n'a ete ajoute pour naviguer entre les deux temps : ce sont
    les gestes qui existaient deja qui commutent la page du Scan.
    """
    coquille, _projet, _fournisseurs = _coquille_sur_le_projet(qtbot, tmp_path)
    cible = _noeuds_de_scan(coquille)[-1]
    coquille.ouvrir(cible.identifiant)
    assert coquille.temps_du_scan_courant() is coquille.atelier_jugement

    # Le bouton « detecter » du chutier : le travail du temps 1 se voit.
    coquille.zone_tampon.detection_demandee.emit(())
    assert coquille.temps_du_scan_courant() is coquille.atelier_scan

    # Et un AUTRE projet referme la surface, parce que la planche qu'elle
    # montrait appartenait au precedent.
    coquille.ouvrir(cible.identifiant)
    assert coquille.temps_du_scan_courant() is coquille.atelier_jugement
    coquille.ouvrir_projet(None)
    assert coquille.temps_du_scan_courant() is coquille.atelier_scan


def _empreinte_du_dossier(racine):
    """Chemin ET octets de chaque fichier : une reecriture identique se voit
    au chemin, une reecriture differente au contenu."""
    return sorted(
        (str(chemin.relative_to(racine)), chemin.read_bytes())
        for chemin in racine.rglob("*")
        if chemin.is_file()
    )


def test_monter_la_surface_n_AJOUTE_aucune_ecriture(qtbot, tmp_path):
    """AC 9 de 7.4 : cette story LIT, et le cablage ne lui ajoute rien.

    Le fournisseur n'est **pas** substitue ici : c'est le vrai
    `FournisseurDeProjet` que la coquille construit, sur un projet reel dont
    on compare l'arborescence ET les octets avant et apres. C'est aussi ce
    qui mesure que la disponibilite de la variante corrigee est **derivee du
    fournisseur** et non ecrite : le vrai declare qu'aucune image corrigee
    n'existe (`EPIC5-ARB-5`), et la bascule reste grisee sans qu'aucun ecran
    n'en ait juge localement.
    """
    projet, manifest = _projet_avec_deux_lots(tmp_path)
    coquille = Coquille()
    qtbot.addWidget(coquille)
    coquille.ouvrir_projet(projet, manifest)
    avant = _empreinte_du_dossier(projet)
    assert avant, "le projet du banc doit porter des fichiers"

    cible = _noeuds_de_scan(coquille)[-1]
    assert coquille.ouvrir(cible.identifiant) == coquille_module.CLE_ATELIER_SCAN
    assert coquille.temps_du_scan_courant() is coquille.atelier_jugement

    assert _empreinte_du_dossier(projet) == avant
    assert not coquille.bascule_image.isEnabled()
    assert coquille.preference_image.variante == raster_de_page.IMAGE_BRUTE


def test_un_scan_dont_le_document_est_INTROUVABLE_laisse_la_page_au_temps_1(
    qtbot, tmp_path
):
    """Montrer une surface de jugement vide serait pire que ne rien changer."""
    coquille, _projet, fournisseurs = _coquille_sur_le_projet(qtbot, tmp_path)
    cible = _noeuds_de_scan(coquille)[-1]
    orphelin = modele_chutier.Noeud(
        type=modele_chutier.TYPE_SCAN,
        identifiant=cible.identifiant,
        read_rank=cible.read_rank,
        page_index=cible.page_index,
        detail={"empreinte_detection": "sha256-v1:" + "f" * 64},
    )
    assert coquille.juger_ce_scan(orphelin) is False
    assert coquille.temps_du_scan_courant() is coquille.atelier_scan
    assert fournisseurs == []


# ---------------------------------------------------------------------------
# Sans source corrigee : GRISEE et PRESENTE (EPIC7-ARB-24)
# ---------------------------------------------------------------------------


def test_sans_source_corrigee_la_bascule_est_grisee_et_PRESENTE(qtbot):
    coquille, atelier, _document = _montage(qtbot, avec_source_corrigee=False)
    bouton = coquille.bascule_image
    assert not bouton.isEnabled()
    # Presente : « le critere est la reversibilite, pas la disponibilite a
    # l'instant t ». La retirer effacerait la trace de ce qui redeviendra
    # possible.
    assert bouton.parent() is coquille.en_tete
    # Et l'ecran DIT pourquoi.
    assert bouton.toolTip() == catalogue.CHAINES["image-bascule-indisponible"]
    assert bouton.accessibleName() == bouton.toolTip()
    # Aucune image corrigee n'est fabriquee pour la circonstance.
    coquille.preference_image.basculer()
    assert coquille.preference_image.variante == raster_de_page.IMAGE_BRUTE
    assert _teinte(atelier.vue_page.scene.contenu.image) == COULEUR_BRUTE.red()


def test_le_fournisseur_de_projet_declare_l_absence_de_source_corrigee(tmp_path):
    """Aucune image corrigee n'existe dans le depot au 2026-08-25.

    La calibration active est post-MVP (`EPIC5-ARB-5`) et toute page detectee
    sort `calibration.status = not_applied`. Le fournisseur le DIT, il n'en
    fabrique pas une.
    """
    fournisseur = raster_de_page.FournisseurDeProjet(tmp_path, 300)
    assert fournisseur.variante_disponible(raster_de_page.IMAGE_BRUTE)
    assert not fournisseur.variante_disponible(raster_de_page.IMAGE_CORRIGEE)
    document = lecture.depuis_json(fab.deux_pages_cible_seconde())
    page = document.page_par_adresse(*fab.ADRESSE_CIBLE)
    assert fournisseur.image(page, raster_de_page.IMAGE_CORRIGEE) is None


def test_retirer_la_source_corrigee_ramene_a_l_image_brute(qtbot):
    """Garder une variante sans source afficherait un vide."""
    coquille, atelier, _document = _montage(qtbot)
    coquille.bascule_image.click()
    assert coquille.preference_image.variante == raster_de_page.IMAGE_CORRIGEE
    coquille.preference_image.poser_disponibilite(False)
    assert coquille.preference_image.variante == raster_de_page.IMAGE_BRUTE
    assert _teinte(atelier.vue_page.scene.contenu.image) == COULEUR_BRUTE.red()


# ---------------------------------------------------------------------------
# Greps de frontiere de l'AC 8
# ---------------------------------------------------------------------------

#: Les modules d'ECRAN de cette story. La coquille n'en fait pas partie :
#: c'est elle, et elle seule, qui a le droit de definir cet etat.
MODULES_D_ECRAN = ("scan_jugement.py", "surimpressions.py", "barre_de_vue.py")


def _classes_et_attributs(nom_de_module):
    arbre = ast.parse((_PAQUET_GUI / nom_de_module).read_text(encoding="utf-8"))
    attributs = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Attribute):
            attributs.add(noeud.attr)
        elif isinstance(noeud, ast.Name):
            attributs.add(noeud.id)
    return attributs


def test_zero_bascule_locale():
    """Le seul point de definition de cet etat est la coquille."""
    for nom in MODULES_D_ECRAN:
        attributs = _classes_et_attributs(nom)
        assert "PreferenceDImage" not in attributs, nom
        assert "BasculeDImage" not in attributs, nom
        assert "poser_variante" not in attributs, nom
        assert "poser_disponibilite" not in attributs, nom
        # `basculer` non plus : un ecran qui saurait basculer porterait la
        # bascule.
        assert "basculer" not in attributs, nom
        # Ni etat de calibration propre.
        assert "calibration" not in attributs, nom
    # La coquille, elle, les definit -- et c'est le SEUL module de `gui/` qui
    # le fasse.
    definisseurs = []
    for source in sorted(_PAQUET_GUI.rglob("*.py")):
        arbre = ast.parse(source.read_text(encoding="utf-8"))
        classes = {
            noeud.name for noeud in ast.walk(arbre) if isinstance(noeud, ast.ClassDef)
        }
        if {"PreferenceDImage", "BasculeDImage"} & classes:
            definisseurs.append(source.name)
    assert definisseurs == ["coquille.py"], definisseurs


def test_le_grep_anti_bascule_locale_MORD_sur_un_module_temoin(tmp_path):
    """Le symetrique : sans lui, le grep pourrait etre vert et vide."""
    temoin = tmp_path / "ecran_temoin.py"
    temoin.write_text(
        "class VueFautive:\n"
        "    def __init__(self):\n"
        "        self.calibration = None\n"
        "    def basculer(self):\n"
        "        self.calibration = not self.calibration\n",
        encoding="utf-8",
    )
    arbre = ast.parse(temoin.read_text(encoding="utf-8"))
    attributs = {
        noeud.attr for noeud in ast.walk(arbre) if isinstance(noeud, ast.Attribute)
    }
    assert "calibration" in attributs
    fonctions = {
        noeud.name for noeud in ast.walk(arbre)
        if isinstance(noeud, ast.FunctionDef)
    }
    assert "basculer" in fonctions


def test_l_icone_vient_de_la_table_d_iconographie(qtbot):
    """(J) -- zero glyphe litteral dans les modules de cette story."""
    coquille = Coquille()
    qtbot.addWidget(coquille)
    assert (
        coquille.bascule_image.text()
        == jetons.ICONOGRAPHIE["glyphe-bascule-image"]
    )
    glyphe = jetons.ICONOGRAPHIE["glyphe-bascule-image"]
    for nom in (*MODULES_D_ECRAN, "coquille.py", "raster_de_page.py",
                "lecture_detection.py"):
        arbre = ast.parse((_PAQUET_GUI / nom).read_text(encoding="utf-8"))
        litteraux = {
            noeud.value for noeud in ast.walk(arbre)
            if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str)
        }
        assert glyphe not in litteraux, (
            f"glyphe litteral dans {nom} : la substitution du jeu d'icones "
            "cesserait d'etre un remplacement d'assets"
        )
