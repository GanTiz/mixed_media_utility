# -*- coding: utf-8 -*-
"""Story 7.3, AC 1 -- la file « En attente de lecture ».

Ce que ce banc mesure : la file est **en haut du chutier**, son titre vient du
catalogue, on y depose un fichier / une selection / un dossier, chaque entree
porte sa case a cocher independante, et **rien n'en sort tout seul**.

Depuis l'essai de terrain du 2026-08-27 il mesure aussi les trois retours qui
touchent cette surface : les deux gestes d'import par l'explorateur
(`EPIC7-ARB-87`), la selection multiple qui est **UN lot** (`EPIC7-ARB-88`),
et la disparition du selecteur de forme (`EPIC7-ARB-89`).

Regle des fabriques : toutes les collections viennent de `fabriques_scan`, qui
produit **trois** entrees distinguables, et **la cible des assertions est la
SECONDE**.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QMimeData, QPoint, QUrl, Qt
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import QLabel

import fabriques_scan as fab
from mixed_media_utility import scan_ingest
from mixed_media_utility.gui import catalogue, modele_zone_tampon as modele
from mixed_media_utility.gui.coquille import Coquille
from mixed_media_utility.gui import zone_tampon as module_zone
from mixed_media_utility.gui.zone_tampon import ZoneTampon

MARQUE = "‹M›"


@pytest.fixture
def zone(qtbot):
    surface = ZoneTampon()
    qtbot.addWidget(surface)
    return surface


def _depot(chemins):
    """Un vrai `QDropEvent` portant des chemins locaux.

    Le geste passe par le HANDLER reel de la surface : `deposer_des_chemins`
    seul ne prouverait pas que la zone est une cible de depot.
    """
    donnees = QMimeData()
    donnees.setUrls([QUrl.fromLocalFile(str(chemin)) for chemin in chemins])
    evenement = QDropEvent(
        QPoint(5, 5), Qt.DropAction.CopyAction, donnees,
        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    # **Piege offscreen mesure ici** : `QDropEvent` ne prend PAS possession de
    # son `QMimeData`. Sans cette reference, l'objet Python est collecte des
    # le retour de cette fonction et le premier acces cote C++ segfault -- pas
    # une exception, un arret brutal du processus de test. On accroche donc la
    # donnee a l'evenement, dont la duree de vie couvre le geste.
    evenement._donnees = donnees
    return evenement


# ---------------------------------------------------------------------------
# La file est en HAUT du chutier, et son titre vient du catalogue
# ---------------------------------------------------------------------------


def test_la_zone_tampon_est_au_dessus_de_l_arbre(qtbot):
    fenetre = Coquille()
    qtbot.addWidget(fenetre)
    fenetre.show()
    qtbot.waitExposed(fenetre)

    tampon = fenetre.zone_tampon
    arbre = fenetre.chutier.arbre
    haut_du_tampon = tampon.mapTo(fenetre, QPoint(0, 0)).y()
    haut_de_l_arbre = arbre.mapTo(fenetre, QPoint(0, 0)).y()
    assert haut_du_tampon < haut_de_l_arbre, (haut_du_tampon, haut_de_l_arbre)
    # Et pas seulement « plus haut » : la file se termine AVANT que l'arbre ne
    # commence -- elles ne se chevauchent pas.
    assert haut_du_tampon + tampon.height() <= haut_de_l_arbre


def test_le_titre_vient_du_catalogue(qtbot):
    marque = {cle: MARQUE + valeur for cle, valeur in catalogue.CHAINES.items()}
    surface = ZoneTampon(chaines=marque)
    qtbot.addWidget(surface)
    assert surface.titre.text() == MARQUE + catalogue.CHAINES["zone-tampon-titre"]
    assert catalogue.CHAINES["zone-tampon-titre"] == "En attente de lecture"


# ---------------------------------------------------------------------------
# Trois depots distincts : un fichier, une selection, un dossier
# ---------------------------------------------------------------------------


def test_depot_d_un_fichier(zone, tmp_path):
    _dossier, _pdf, image = fab.trois_chemins_distinguables(tmp_path)
    zone.dropEvent(_depot([image]))
    entrees = zone.modele.entrees
    assert len(entrees) == 1
    # Un fichier SEUL reste une entree a UN chemin -- un `Path`, pas un tuple
    # d'un element. `EPIC7-ARB-88` ne change rien a ce cas-la, et cette
    # assertion est ce qui l'empeche de deriver.
    assert entrees[0].chemin == image
    assert entrees[0].chemins == (image,)
    assert entrees[0].est_une_selection is False
    assert entrees[0].nom == image.name
    assert entrees[0].nature == modele.NATURE_IMAGE


def test_depot_d_une_selection_heterogene(zone, tmp_path):
    """Un dossier et un PDF ne rejoignent JAMAIS une selection d'images.

    Ce n'est pas un choix de la GUI : c'est le refus que `scan_ingest` ecrit
    lui-meme (« Un dossier s'ingere en designant le dossier, un PDF en le
    designant seul »). Les regrouper ferait echouer tout le depot la ou trois
    entrees aboutissent.
    """
    dossier, pdf, image = fab.trois_chemins_distinguables(tmp_path)
    zone.dropEvent(_depot([image, pdf, dossier]))
    entrees = zone.modele.entrees
    assert len(entrees) == 3
    assert [entree.chemin for entree in entrees] == [image, pdf, dossier]
    # Les trois natures sont DIFFERENTES : un remplissage uniforme cacherait
    # une permutation entre l'entree et sa ligne.
    assert [entree.nature for entree in entrees] == [
        modele.NATURE_IMAGE, modele.NATURE_PDF, modele.NATURE_DOSSIER]
    # Et aucune des trois n'est une selection : chacune porte UN chemin.
    assert [entree.est_une_selection for entree in entrees] == [
        False, False, False]


# ---------------------------------------------------------------------------
# EPIC7-ARB-88 -- une selection de plusieurs fichiers est UN lot
# ---------------------------------------------------------------------------


def test_une_selection_de_quatre_images_est_UNE_entree(zone, tmp_path):
    """Le retour d'Egan, mot pour mot : « un unique ingest.json pour ce lot ».

    Avant `EPIC7-ARB-88`, ce depot rendait **quatre** entrees, donc quatre
    lots, donc quatre `ingest.json` -- et l'`[Errno 2]` que l'essai de terrain
    a vu. Il en rend **une**.
    """
    images = fab.quatre_images_d_une_selection(tmp_path)
    assert len(images) == 4
    zone.dropEvent(_depot(list(images)))

    entrees = zone.modele.entrees
    assert len(entrees) == 1
    entree = entrees[0]
    assert entree.est_une_selection is True
    # Les quatre chemins, DANS L'ORDRE DU GESTE : la GUI ne trie pas -- c'est
    # le coeur qui ordonne par nom normalise (`_ordonner_une_selection`), et
    # une GUI qui trierait ici rejouerait une regle du coeur (`EPIC7-ARB-64`).
    assert entree.chemins == tuple(images)
    # La cible est la SECONDE, ni premiere ni derniere.
    assert entree.chemins[1] == images[1]
    assert entree.chemins[1].name == "page_01_alpha.tiff"
    # Une seule ligne a l'ecran, et elle porte le cardinal.
    assert len(zone.lignes()) == 1


def test_le_nom_d_une_selection_est_le_slug_que_le_COEUR_retiendra(
        zone, tmp_path):
    """Le nom du lot est **demande au coeur**, jamais devine (`EPIC7-ARB-88`)."""
    projet = tmp_path / "projet"
    projet.mkdir()
    zone.modele.poser_le_projet(projet)
    images = fab.quatre_images_d_une_selection(tmp_path)
    zone.dropEvent(_depot(list(images)))

    entree = zone.modele.entrees[0]
    # La reference est ce que le COEUR rend, pas une chaine recopiee ici.
    attendu = scan_ingest.slug_par_defaut(projet, tuple(images))
    assert entree.nom_de_lot == attendu
    assert entree.nom == attendu
    assert attendu == fab.SELECTION_DOSSIER
    # Et il ne vaut aucun des quatre noms de fichier : un repli sur le premier
    # chemin -- le comportement quand aucun projet n'est ouvert -- se verrait.
    assert attendu not in {chemin.name for chemin in images}

    # Le libelle affiche : le nom du lot ET son cardinal.
    ligne = zone.lignes()[0]
    assert ligne.case.text() == catalogue.CHAINES[
        "zone-tampon-entree-selection"].format(nom=attendu, pages=4)


def test_le_nom_du_lot_arrive_quand_le_projet_arrive(zone, tmp_path):
    """Une selection deposee avant l'ouverture d'un projet se RENOMME.

    Sans projet il n'existe aucune racine `scans/` a comparer, donc aucun slug
    derivable : l'entree se nomme provisoirement par son premier fichier. Le
    laisser tel quel afficherait un nom que le lot n'aura jamais.
    """
    images = fab.quatre_images_d_une_selection(tmp_path)
    zone.dropEvent(_depot(list(images)))
    entree = zone.modele.entrees[0]
    assert entree.nom_de_lot is None
    assert entree.nom == images[0].name

    projet = tmp_path / "projet"
    projet.mkdir()
    zone.modele.poser_le_projet(projet)
    zone.rafraichir()

    assert entree.nom_de_lot == fab.SELECTION_DOSSIER
    assert fab.SELECTION_DOSSIER in zone.lignes()[0].case.text()


def test_deux_images_forment_deja_un_lot(zone, tmp_path):
    """Le seuil est DEUX, pas trois : deux TIFF glisses font un lot.

    Une fabrique a quatre elements ne dirait pas ou le regroupement commence ;
    ce test le mesure au bord, et sa cible reste la SECONDE image.
    """
    images = fab.quatre_images_d_une_selection(tmp_path)
    couple = (images[2], images[1])
    zone.dropEvent(_depot(list(couple)))
    entrees = zone.modele.entrees
    assert len(entrees) == 1
    assert entrees[0].est_une_selection is True
    assert entrees[0].chemins == couple
    assert entrees[0].chemins[1] == images[1]


def test_depot_d_un_dossier(zone, tmp_path):
    dossier, _pdf, _image = fab.trois_chemins_distinguables(tmp_path)
    zone.dropEvent(_depot([dossier]))
    entrees = zone.modele.entrees
    # UNE entree, pas une par fichier du dossier : le dossier est deja une
    # pile pour le coeur, l'enumerer ici serait refaire son travail.
    assert len(entrees) == 1
    assert entrees[0].nature == modele.NATURE_DOSSIER
    assert len(list(dossier.iterdir())) == 2, "le dossier porte bien 2 fichiers"


# ---------------------------------------------------------------------------
# Les cases a cocher sont independantes ; la cible est la DEUXIEME
# ---------------------------------------------------------------------------


def test_cases_a_cocher_independantes(zone, tmp_path):
    chemins = fab.trois_chemins_distinguables(tmp_path)
    zone.dropEvent(_depot(list(chemins)))
    lignes = zone.lignes()
    assert len(lignes) == 3
    # Une entree neuve est COCHEE.
    assert all(entree.cochee for entree in zone.modele.entrees)

    cible = lignes[1]           # la DEUXIEME, jamais la premiere
    cible.case.setChecked(False)

    etats = [entree.cochee for entree in zone.modele.entrees]
    assert etats == [True, False, True], etats
    assert zone.modele.cochees() == (
        zone.modele.entrees[0], zone.modele.entrees[2])


# ---------------------------------------------------------------------------
# Rien ne sort tout seul (correction A2)
# ---------------------------------------------------------------------------


def test_l_entree_reste_apres_une_detection_reussie(zone, tmp_path):
    chemins = fab.trois_chemins_distinguables(tmp_path)
    zone.dropEvent(_depot(list(chemins)))
    avant = [entree.identifiant for entree in zone.modele.entrees]

    # La fin d'une detection pose ce qu'elle a trouve SUR l'entree ; elle ne
    # la retire pas. La cible est la seconde.
    cible = zone.modele.entrees[1]
    zone.modele.poser_les_lot_trouves(cible.identifiant, [fab.LOT_COMPLET])
    zone.rafraichir()

    assert [entree.identifiant for entree in zone.modele.entrees] == avant
    assert len(zone.lignes()) == 3


def test_l_entree_reste_apres_un_echec(zone, tmp_path):
    chemins = fab.trois_chemins_distinguables(tmp_path)
    zone.dropEvent(_depot(list(chemins)))
    cible = zone.modele.entrees[1]
    zone.modele.poser_le_motif(cible.identifiant, "Chemin de scan introuvable: /nulle/part")
    zone.rafraichir()

    assert len(zone.modele.entrees) == 3
    ligne = zone.ligne(cible.identifiant)
    # Le motif affiche est celui qu'on a pose, VERBATIM.
    assert ligne.texte_du_motif() == "Chemin de scan introuvable: /nulle/part"
    assert ligne.libelle_motif.isVisibleTo(zone)


def test_seul_le_geste_explicite_retire(zone, tmp_path):
    chemins = fab.trois_chemins_distinguables(tmp_path)
    zone.dropEvent(_depot(list(chemins)))
    cible = zone.modele.entrees[1]

    assert zone.retirer(cible.identifiant) is True
    restantes = [entree.chemin for entree in zone.modele.entrees]
    # La SECONDE est partie, les deux autres sont la : un retrait qui viserait
    # toujours la premiere se verrait ici et nulle part ailleurs.
    assert restantes == [chemins[0], chemins[2]]
    assert len(zone.lignes()) == 2
    assert zone.ligne(cible.identifiant) is None


# ---------------------------------------------------------------------------
# EPIC7-ARB-89 -- le selecteur « pile de planches / planche seule » a disparu
# ---------------------------------------------------------------------------


def test_aucun_selecteur_de_forme_nulle_part(zone, tmp_path):
    """« L'outil dispose normalement des informations pour faire ce tri lui-meme. »

    La mesure qui a tranche : `forme` n'etait transmis a AUCUN appel du coeur.
    Ce test la garde en place -- il echoue si le champ, le vocabulaire ou le
    geste de correction reviennent, par le modele comme par la surface.
    """
    chemins = fab.trois_chemins_distinguables(tmp_path)
    zone.dropEvent(_depot(list(chemins)))

    # (a) le modele n'a plus ni vocabulaire de forme, ni deduction, ni
    #     correction -- les cinq noms d'`EPIC7-ARB-89`, nommes un par un.
    for nom in ("FORME_SCAN", "FORME_PLANCHE", "FORMES", "deduire_la_forme"):
        assert not hasattr(modele, nom), nom
    assert not hasattr(modele.ModeleDeZoneTampon, "corriger_la_forme")
    # (b) ni l'entree ne porte encore une forme, sur AUCUNE des trois -- un
    #     champ laisse sur la seule cible passerait un test qui n'en verrait
    #     qu'une.
    for entree in zone.modele.entrees:
        assert not hasattr(entree, "forme"), entree.nom
        assert not hasattr(entree, "forme_deduite"), entree.nom
    # (c) ni la surface : ni libelle de forme, ni bouton de correction.
    for ligne in zone.lignes():
        assert not hasattr(ligne, "libelle_forme")
        assert not hasattr(ligne, "bouton_forme")
    # (d) et aucun texte affiche par la file ne nomme encore une forme. Les
    #     libelles de reference viennent du CATALOGUE, jamais recopies ici :
    #     un test qui comparerait a « Pile de planches » ecrit en dur cesserait
    #     de mordre a la premiere retouche de redaction.
    formes = {catalogue.CHAINES["zone-tampon-forme-scan"],
              catalogue.CHAINES["zone-tampon-forme-planche"]}
    affiches = {libelle.text()
                for libelle in zone.findChildren(QLabel) if libelle.text()}
    affiches |= {ligne.case.text() for ligne in zone.lignes()}
    assert affiches & formes == set(), affiches & formes


# ---------------------------------------------------------------------------
# EPIC7-ARB-87 -- deux boutons d'import, la MEME file
# ---------------------------------------------------------------------------


def test_les_deux_boutons_d_import_alimentent_la_meme_file(qtbot, tmp_path):
    """« Il faut deux boutons : [...] un fichier unique [...] et tout un dossier. »

    Les deux selecteurs sont INJECTES : un banc offscreen ne pilote pas une
    modale systeme. Ce qu'ils rendent traverse le meme `deposer_des_chemins`
    que le glisser-deposer.
    """
    dossier, _pdf, _image = fab.trois_chemins_distinguables(tmp_path)
    images = fab.quatre_images_d_une_selection(tmp_path)
    surface = ZoneTampon(
        selecteur_de_fichiers=lambda: list(images),
        selecteur_de_dossier=lambda: [dossier])
    qtbot.addWidget(surface)

    surface.bouton_importer_fichier.click()
    # UNE entree pour les quatre fichiers : le bouton n'a pas sa propre
    # lecture du depot, il passe par la meme porte (`EPIC7-ARB-88`).
    assert len(surface.modele.entrees) == 1
    assert surface.modele.entrees[0].chemins == tuple(images)

    surface.bouton_importer_dossier.click()
    entrees = surface.modele.entrees
    assert len(entrees) == 2
    # La SECONDE est le dossier : un import qui insererait en tete se verrait.
    assert entrees[1].chemin == dossier
    assert entrees[1].nature == modele.NATURE_DOSSIER
    assert entrees[1].est_une_selection is False
    assert len(surface.lignes()) == 2


def test_un_selecteur_annule_ne_depose_rien(qtbot):
    """« Annuler » rend zero chemin : la file ne gagne aucune ligne vide."""
    surface = ZoneTampon(
        selecteur_de_fichiers=lambda: [],
        selecteur_de_dossier=lambda: [])
    qtbot.addWidget(surface)
    surface.bouton_importer_fichier.click()
    surface.bouton_importer_dossier.click()
    assert surface.modele.entrees == ()
    assert surface.lignes() == ()


def test_le_filtre_du_selecteur_vient_des_extensions_du_COEUR():
    """Aucune seconde liste d'extensions dans la GUI -- frontiere dure.

    La reference est `scan_ingest`, pas une liste ecrite dans ce test : une
    extension ajoutee au coeur doit apparaitre au filtre sans qu'on touche ni
    a la GUI ni a ce banc.
    """
    filtre = module_zone.filtre_des_scans(catalogue.CHAINES)
    attendues = (*scan_ingest.IMAGE_EXTENSIONS, *scan_ingest.PDF_EXTENSIONS)
    # Toutes les extensions du coeur y sont, et le compte y est aussi : un
    # filtre qui n'en porterait qu'une passerait un `in` isole.
    assert len(attendues) == len(set(attendues)) >= 2
    for suffixe in attendues:
        assert f"*{suffixe}" in filtre, suffixe
    assert filtre.count("*") == len(attendues)
    # Et la phrase autour vient du catalogue.
    assert filtre.startswith(
        catalogue.CHAINES["zone-tampon-filtre-fichiers"].split("{")[0])
    # Symetrique : une extension que le coeur NE reconnait PAS n'y est pas.
    assert "*.psd" not in filtre and ".psd" not in scan_ingest.IMAGE_EXTENSIONS


def test_deux_depots_du_meme_chemin_restent_deux_entrees(zone, tmp_path):
    """Un identifiant derive du seul chemin confondrait les deux."""
    _dossier, _pdf, image = fab.trois_chemins_distinguables(tmp_path)
    zone.dropEvent(_depot([image]))
    zone.dropEvent(_depot([image]))
    entrees = zone.modele.entrees
    assert len(entrees) == 2
    assert entrees[0].identifiant != entrees[1].identifiant
    zone.lignes()[1].case.setChecked(False)
    assert [entree.cochee for entree in entrees] == [True, False]


def test_le_champ_de_dpi_reflete_le_modele(zone, tmp_path):
    """Defaut vu a la CAPTURE, par aucun test : la surface disait le contraire.

    Un dpi pose autrement que par la frappe -- par un rechargement, par un
    banc -- laissait le champ VIDE alors que le bouton devenait actif. Un
    modele juste et une surface muette ne valent rien.
    """
    chemins = fab.trois_chemins_distinguables(tmp_path)
    zone.dropEvent(_depot(list(chemins)))
    entrees = zone.modele.entrees
    # Trois dpi differents, cible en SECONDE position.
    for entree, valeur in zip(entrees, (300, 600, 1200)):
        zone.modele.poser_le_dpi(entree.identifiant, valeur)
    zone.rafraichir()

    assert [ligne.champ_dpi.text() for ligne in zone.lignes()] == [
        "300", "600", "1200"]
    # Et le sens inverse tient toujours : la frappe alimente le modele.
    zone.lignes()[1].champ_dpi.setText("400")
    assert zone.modele.entrees[1].dpi == 400
    assert zone.modele.entrees[0].dpi == 300


# ---------------------------------------------------------------------------
# F14 (revue de vague 3) -- `poser_le_hors_perimetre`, DISJOINT du reliquat
# ---------------------------------------------------------------------------


def test_poser_le_hors_perimetre_est_disjoint_du_reliquat(zone, tmp_path):
    """Les deux listes ne se fondent jamais l'une dans l'autre.

    Regle des fabriques : DEUX triplets distinguables (localisateur, motif,
    projet DIFFERENTS), la cible en SECONDE position.
    """
    chemins = fab.trois_chemins_distinguables(tmp_path)
    zone.dropEvent(_depot(list(chemins)))
    cible = zone.modele.entrees[1].identifiant

    zone.modele.poser_le_reliquat(
        cible, [("page_reliquat.tiff", "reliquat-qr-absent-ou-illisible")])
    zone.modele.poser_le_hors_perimetre(
        cible,
        [
            ("page_hp_1.tiff", "hors-perimetre-projet-etranger", "proj-un"),
            ("page_hp_2.tiff", "hors-perimetre-projet-etranger", "proj-deux"),
        ],
    )

    entree = zone.modele.entree(cible)
    assert entree.reliquat == (
        ("page_reliquat.tiff", "reliquat-qr-absent-ou-illisible"),)
    assert entree.hors_perimetre == (
        ("page_hp_1.tiff", "hors-perimetre-projet-etranger", "proj-un"),
        ("page_hp_2.tiff", "hors-perimetre-projet-etranger", "proj-deux"),
    )
    # Aucune contamination croisee : le reliquat d'une autre entree que
    # `cible` reste vide, tout comme son hors-perimetre.
    autre = zone.modele.entrees[0]
    assert autre.reliquat == ()
    assert autre.hors_perimetre == ()
    # Et la SECONDE des deux entrees hors-perimetre garde SON propre projet
    # -- un appariement inverse entre l'index et le projet se verrait ici.
    assert entree.hors_perimetre[1][2] == "proj-deux"
    assert entree.hors_perimetre[0][2] != entree.hors_perimetre[1][2]


def test_poser_le_hors_perimetre_preserve_none_pour_le_projet_inconnu(
        zone, tmp_path):
    """`projet_a_utiliser=None` (le QR ne l'a pas livre) reste `None`.

    Jamais transforme en la chaine `"None"` -- ce serait fabriquer une
    valeur que le rapport de tri n'a jamais rendue.
    """
    chemins = fab.trois_chemins_distinguables(tmp_path)
    zone.dropEvent(_depot(list(chemins)))
    cible = zone.modele.entrees[1].identifiant

    zone.modele.poser_le_hors_perimetre(
        cible,
        [
            ("page_a.tiff", "hors-perimetre-projet-etranger", "proj-connu"),
            ("page_b.tiff", "hors-perimetre-projet-etranger", None),
        ],
    )

    entree = zone.modele.entree(cible)
    assert entree.hors_perimetre[0][2] == "proj-connu"
    assert entree.hors_perimetre[1][2] is None


# ---------------------------------------------------------------------------
# Revue du 2026-08-27 -- un chemin ETRANGER ne fait pas echouer tout le depot
# ---------------------------------------------------------------------------


def test_un_fichier_etranger_fait_entree_a_part_et_n_emporte_pas_les_images(
    zone, tmp_path
):
    """Defaut mesure : `page.tiff` et `notes.txt` deposes ensemble faisaient
    UNE entree de deux chemins, que le coeur refusait EN BLOC -- « Une
    selection de scan ne porte que des images » --, si bien que l'image valide
    etait perdue avec le fichier fautif.

    Le remede est celui deja applique aux dossiers et aux PDF : ce que le coeur
    refuse de melanger, la GUI ne le melange pas. Isole, le fichier etranger
    echouera seul, avec le motif verbatim du coeur (P9).
    """
    image = tmp_path / "page.tiff"
    etranger = tmp_path / "notes.txt"
    image.write_bytes(b"image")
    etranger.write_bytes(b"texte")

    zone.dropEvent(_depot([image, etranger]))

    entrees = zone.modele.entrees
    assert [entree.chemins for entree in entrees] == [(image,), (etranger,)]
    assert [entree.nature for entree in entrees] == [
        modele.NATURE_IMAGE, modele.NATURE_ETRANGERE]
    assert [entree.est_une_selection for entree in entrees] == [False, False]


def test_deux_images_de_suffixes_differents_font_toujours_UN_lot(zone, tmp_path):
    """Volet symetrique : la nouvelle nature ne doit pas casser le regroupement.

    Sans lui, une implementation qui declarerait ETRANGER tout ce qui n'est pas
    `.tiff` passerait le test precedent et defairait `EPIC7-ARB-88`. Les deux
    suffixes choisis sont differents, et aucun n'est le premier de la liste du
    coeur -- une comparaison qui ne verifierait que le premier se verrait.
    """
    premiere = tmp_path / "a.jpeg"
    seconde = tmp_path / "b.BMP"
    premiere.write_bytes(b"a")
    seconde.write_bytes(b"b")

    zone.dropEvent(_depot([premiere, seconde]))

    entrees = zone.modele.entrees
    assert len(entrees) == 1
    assert entrees[0].chemins == (premiere, seconde)
    assert entrees[0].est_une_selection is True


def test_les_suffixes_d_image_sont_LUS_du_coeur_et_non_recopies(zone):
    """Frontiere : une seconde liste d'extensions dans la GUI divergerait de
    ce que l'ingestion accepte au premier format ajoute."""
    from mixed_media_utility import scan_ingest

    assert modele.SUFFIXES_D_IMAGE is scan_ingest.IMAGE_EXTENSIONS
