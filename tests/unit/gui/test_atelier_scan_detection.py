# -*- coding: utf-8 -*-
"""Story 7.3 -- le bouton, les cartes, l'annonce, la reouverture, le refus.

AC 2b a 2e, AC 4, AC 6 et AC 8, mesures sur la vraie coquille et le vrai
executeur. La fonction du coeur est **injectee** : le defaut est
`scan_detect.run_scan_detect`, et le banc y substitue un appelable qui ecrit
de VRAIS documents `scan_previz` et rend un VRAI `ScanDetectOutcome`, ou qui
appelle une VRAIE garde du coeur pour lever son exception. Ce que le banc ne
fait jamais, c'est fabriquer un motif a la main : le motif compare est
toujours celui du coeur (P9).

Regle des fabriques : trois entrees distinguables, deux lot aux completudes
differentes, **cible en seconde position** dans chaque collection.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import fabriques_scan as fab
from mixed_media_utility.gui import (
    catalogue,
    chargeur_detections,
    executeur,
    modele_chutier,
)
from mixed_media_utility.gui.atelier_scan import AtelierScan
from mixed_media_utility.gui.coquille import Coquille
from mixed_media_utility.io import project_layout, scan_manifest


# ---------------------------------------------------------------------------
# Fabriques de fonctions de detection : de VRAIS documents, de VRAIS refus
# ---------------------------------------------------------------------------


detection_qui_ecrit = fab.detection_qui_ecrit


def detection_qui_confronte_le_manifest(payload_par_nom):
    """Un appelable qui appelle la VRAIE garde du coeur, par nom d'entree.

    C'est le chemin de l'AC 6 : `check_scan_conflicts` lit le manifest du
    projet ouvert et refuse la planche d'un autre projet. Le motif affiche est
    donc celui de l'exception du coeur, jamais une phrase du banc.
    """

    def detecter(project_dir, scan_path, dpi,
                 remplacer_les_detections=False):
        payload = payload_par_nom.get(Path(scan_path).name)
        if payload is not None:
            # La VRAIE garde du coeur, sur le VRAI manifest du projet ouvert.
            scan_manifest.check_scan_conflicts(
                project_dir, [payload], failed_page_indexes=(), overwrite=False)
        return fab.issue(())

    return detecter


def _projet(tmp_path, *, manifest=None):
    projet = tmp_path / "projet"
    projet.mkdir(parents=True, exist_ok=True)
    if manifest is not None:
        (projet / "project.json").write_text(
            json.dumps(manifest), encoding="utf-8")
    return projet


def _fenetre(qtbot, projet, detecter, *, manifest=None):
    fenetre = Coquille()
    qtbot.addWidget(fenetre)
    fenetre.atelier_scan._detecter = detecter
    fenetre.ouvrir_projet(projet, manifest)
    return fenetre


def _deposer(fenetre, chemins, *, dpi=600):
    entrees = fenetre.zone_tampon.deposer_des_chemins(list(chemins))
    for entree in entrees:
        fenetre.zone_tampon.modele.poser_le_dpi(entree.identifiant, dpi)
    fenetre.zone_tampon.rafraichir()
    return entrees


def _attendre(qtbot, fenetre, cardinal):
    qtbot.waitUntil(
        lambda: len(fenetre.atelier_scan.panneau_taches.cartes()) >= cardinal
        and all(carte.etat != executeur.EN_COURS
                for carte in fenetre.atelier_scan.panneau_taches.cartes()),
        timeout=5000)


# ---------------------------------------------------------------------------
# AC 2b -- le bouton vit au chutier, et rien ne part tout seul
# ---------------------------------------------------------------------------


def test_le_bouton_detecter_est_au_chutier(qtbot):
    fenetre = Coquille()
    qtbot.addWidget(fenetre)
    fenetre.show()
    qtbot.waitExposed(fenetre)

    bouton = fenetre.zone_tampon.bouton_detecter
    # Le bouton est un descendant de la zone tampon, elle-meme dans la colonne
    # du chutier -- jamais dans la scene (la previz est role 4 : `EPIC7-ARB-40`).
    assert bouton in fenetre.zone_tampon.findChildren(type(bouton))
    assert fenetre.zone_tampon in fenetre.zone_chutier.findChildren(
        type(fenetre.zone_tampon))
    assert bouton not in fenetre.scene.findChildren(type(bouton))
    assert bouton.text() == catalogue.CHAINES["zone-tampon-detecter"]


def test_aucune_detection_ne_part_toute_seule(qtbot, tmp_path):
    appels = []

    def detecter(project_dir, scan_path, dpi,
                 remplacer_les_detections=False):
        appels.append(scan_path)
        return fab.issue(())

    projet = _projet(tmp_path)
    fenetre = _fenetre(qtbot, projet, detecter)
    dossier, pdf, _image = fab.trois_chemins_distinguables(tmp_path)
    _deposer(fenetre, [dossier, pdf])

    # Deux entrees deposees, cochees, avec leur dpi : rien n'est soumis.
    assert appels == []
    assert fenetre.atelier_scan.panneau_taches.cartes() == ()
    # Temoin : le clic, lui, soumet -- sans quoi ce test serait vert et vide.
    fenetre.zone_tampon.bouton_detecter.click()
    _attendre(qtbot, fenetre, 2)
    assert len(appels) == 2


def test_deux_entrees_du_meme_chemin_ne_lancent_qu_une_seule_detection(
        qtbot, tmp_path):
    """F15 (revue de vague 3) -- deux entrees du meme chemin, UN SEUL appel.

    `ModeleDeZoneTampon.deposer` autorise DELIBEREMENT deux entrees du meme
    chemin (`test_deux_depots_du_meme_chemin_restent_deux_entrees`), et ce
    test ne le casse pas -- les deux entrees restent deux entrees, chacune
    sa carte (AC 2c). Mais `scan_ingest.ingest_scan_lot` derive
    `ingest_slug` du seul chemin, DETERMINISTE : deux appels au coeur sur le
    meme chemin viseraient le meme `scans/<slug>/ingest.json`. `lancer` ne
    doit donc soumettre qu'UN SEUL appel par chemin distinct.
    """
    appels = []

    def detecter(project_dir, scan_path, dpi,
                 remplacer_les_detections=False):
        appels.append(scan_path)
        return fab.issue(())

    projet = _projet(tmp_path)
    fenetre = _fenetre(qtbot, projet, detecter)
    dossier, _pdf, _image = fab.trois_chemins_distinguables(tmp_path)
    # DEUX depots du MEME chemin.
    fenetre.zone_tampon.deposer_des_chemins([dossier])
    fenetre.zone_tampon.deposer_des_chemins([dossier])
    for entree in fenetre.zone_tampon.modele.entrees:
        fenetre.zone_tampon.modele.poser_le_dpi(entree.identifiant, 600)
    fenetre.zone_tampon.rafraichir()
    entrees = fenetre.zone_tampon.modele.entrees
    assert len(entrees) == 2
    assert entrees[0].identifiant != entrees[1].identifiant

    fenetre.zone_tampon.bouton_detecter.click()
    _attendre(qtbot, fenetre, 2)

    # Un SEUL appel au coeur, malgre DEUX entrees cochees du meme chemin.
    assert appels == [dossier]

    # Ce que la file affiche pour la SECONDE entree : sa PROPRE carte (une
    # carte par entree, invariant AC 2c inchange), qui suit le MEME
    # aboutissement que la premiere -- sans qu'un second appel n'ait jamais
    # ete soumis.
    cartes = fenetre.atelier_scan.panneau_taches.cartes()
    assert len(cartes) == 2
    assert cartes[0].etat == executeur.TERMINEE
    assert cartes[1].etat == executeur.TERMINEE


# ---------------------------------------------------------------------------
# AC 2c -- une carte par detection, cible en SECONDE position
# ---------------------------------------------------------------------------


def test_une_carte_par_detection(qtbot, tmp_path):
    projet = _projet(tmp_path)
    documents = [fab.document_du_lot_complet()]
    fenetre = _fenetre(qtbot, projet, detection_qui_ecrit(documents))
    chemins = fab.trois_chemins_distinguables(tmp_path)
    _deposer(fenetre, chemins)

    fenetre.zone_tampon.bouton_detecter.click()
    _attendre(qtbot, fenetre, 3)

    cartes = fenetre.atelier_scan.panneau_taches.cartes()
    assert len(cartes) == 3
    # Chaque carte nomme SON objet, et la cible est la seconde : trois cartes
    # portant le meme nom passeraient un test qui ne regarderait que le
    # cardinal.
    noms = [chemin.name for chemin in chemins]
    assert len(set(noms)) == 3
    for carte, nom in zip(cartes, noms):
        assert nom in carte.texte_de_l_objet(), (carte.texte_de_l_objet(), nom)
    assert noms[1] in cartes[1].texte_de_l_objet()
    assert noms[1] not in cartes[0].texte_de_l_objet()


# ---------------------------------------------------------------------------
# AC 2d -- le dpi est obligatoire et sans defaut
# ---------------------------------------------------------------------------


def test_sans_dpi_le_bouton_detecter_est_inactif(qtbot, tmp_path):
    projet = _projet(tmp_path)
    fenetre = _fenetre(qtbot, projet, detection_qui_ecrit([]))
    chemins = fab.trois_chemins_distinguables(tmp_path)
    entrees = fenetre.zone_tampon.deposer_des_chemins(list(chemins))

    bouton = fenetre.zone_tampon.bouton_detecter
    assert bouton.isEnabled() is False
    # Et il DIT pourquoi : le motif vient du catalogue, jamais d'un silence.
    assert fenetre.zone_tampon.libelle_inactif.text() == catalogue.CHAINES[
        "zone-tampon-detecter-sans-dpi"]

    # Un dpi sur la seule cible (la SECONDE) ne suffit pas : les deux autres
    # sont toujours cochees et sans dpi.
    fenetre.zone_tampon.ligne(entrees[1].identifiant).champ_dpi.setText("600")
    assert bouton.isEnabled() is False

    # Decocher les deux autres : la file n'a plus que des entrees avec dpi.
    fenetre.zone_tampon.ligne(entrees[0].identifiant).case.setChecked(False)
    fenetre.zone_tampon.ligne(entrees[2].identifiant).case.setChecked(False)
    assert bouton.isEnabled() is True
    assert fenetre.zone_tampon.libelle_inactif.text() == ""

    # Tout decocher : l'autre motif, distinct du premier.
    fenetre.zone_tampon.ligne(entrees[1].identifiant).case.setChecked(False)
    assert bouton.isEnabled() is False
    assert fenetre.zone_tampon.libelle_inactif.text() == catalogue.CHAINES[
        "zone-tampon-detecter-sans-entree"]


def test_le_dpi_saisi_est_celui_qui_part_au_coeur(qtbot, tmp_path):
    """Le dpi n'est ni arrondi, ni remplace, ni suppose."""
    recus = []

    def detecter(project_dir, scan_path, dpi,
                 remplacer_les_detections=False):
        recus.append((Path(scan_path).name, dpi))
        return fab.issue(())

    projet = _projet(tmp_path)
    fenetre = _fenetre(qtbot, projet, detecter)
    chemins = fab.trois_chemins_distinguables(tmp_path)
    entrees = fenetre.zone_tampon.deposer_des_chemins(list(chemins))
    # Trois dpi DIFFERENTS, cible en seconde position : un appariement inverse
    # entre entree et dpi se voit, un remplissage uniforme le cacherait.
    for entree, valeur in zip(entrees, ("300", "600", "1200")):
        fenetre.zone_tampon.ligne(entree.identifiant).champ_dpi.setText(valeur)

    fenetre.zone_tampon.bouton_detecter.click()
    _attendre(qtbot, fenetre, 3)
    assert recus == [
        (chemins[0].name, 300), (chemins[1].name, 600), (chemins[2].name, 1200)]


# ---------------------------------------------------------------------------
# AC 2e -- la completude est ANNONCEE, lue du modele du chutier
# ---------------------------------------------------------------------------


def test_la_completude_annoncee_vient_du_modele_du_chutier(qtbot, tmp_path):
    projet = _projet(tmp_path, manifest=fab.manifest_des_deux_lot())
    documents = list(fab.deux_documents_aux_completudes_differentes())
    fenetre = _fenetre(qtbot, projet, detection_qui_ecrit(documents),
                       manifest=fab.manifest_des_deux_lot())
    dossier, _pdf, _image = fab.trois_chemins_distinguables(tmp_path)
    _deposer(fenetre, [dossier])

    fenetre.zone_tampon.bouton_detecter.click()
    _attendre(qtbot, fenetre, 1)
    qtbot.waitUntil(lambda: len(fenetre.atelier_scan.annonces()) == 2, timeout=5000)

    annonces = fenetre.atelier_scan.annonces()
    # La valeur annoncee est EXACTEMENT celle que le modele du chutier derive
    # des memes documents : deux implementations divergeraient un jour.
    relus = fab.relire(documents)
    for annonce, document in zip(annonces, relus):
        attendu = modele_chutier._completude_du_document([document])
        assert (annonce.badge, annonce.planches_manquantes) == attendu
    # Et les deux lot ne disent PAS la meme chose : une annonce uniforme
    # passerait la boucle ci-dessus si les deux documents se ressemblaient.
    assert annonces[0].badge != annonces[1].badge


def test_les_planches_manquantes_sont_nommees_par_lot(qtbot, tmp_path):
    projet = _projet(tmp_path, manifest=fab.manifest_des_deux_lot())
    documents = list(fab.deux_documents_aux_completudes_differentes())
    fenetre = _fenetre(qtbot, projet, detection_qui_ecrit(documents),
                       manifest=fab.manifest_des_deux_lot())
    dossier, _pdf, _image = fab.trois_chemins_distinguables(tmp_path)
    _deposer(fenetre, [dossier])
    fenetre.zone_tampon.bouton_detecter.click()
    qtbot.waitUntil(lambda: len(fenetre.atelier_scan.annonces()) == 2, timeout=5000)

    # La CIBLE est le SECOND lot -- celui qui est incomplet.
    cible = fenetre.atelier_scan.annonces()[1]
    assert cible.lot == fab.LOT_INCOMPLET
    assert cible.planches_manquantes == (1,)

    textes = fenetre.atelier_scan.textes_annonces()
    assert len(textes) == 2
    # Chaque phrase nomme SON lot, et la planche manquante est dite.
    assert fab.LOT_COMPLET in textes[0] and fab.LOT_INCOMPLET not in textes[0]
    assert fab.LOT_INCOMPLET in textes[1]
    assert catalogue.CHAINES["atelier-scan-planches-manquantes"].format(
        planches="1") in textes[1]
    # Le lot complet dit qu'il ne manque rien -- une absence NOMMEE.
    assert catalogue.CHAINES["atelier-scan-aucune-planche-manquante"] in textes[0]


def test_output_frames_est_vide_au_moment_de_l_annonce(qtbot, tmp_path):
    """Contrat C (V3.a) : comptage REEL du dossier, jamais un drapeau."""
    projet = _projet(tmp_path, manifest=fab.manifest_des_deux_lot())
    documents = list(fab.deux_documents_aux_completudes_differentes())
    fenetre = _fenetre(qtbot, projet, detection_qui_ecrit(documents),
                       manifest=fab.manifest_des_deux_lot())

    releves = []
    fenetre.atelier_scan.completude_annoncee.connect(
        lambda _annonces: releves.append(
            fenetre.atelier_scan.cardinal_des_frames_ecrites()))

    dossier, _pdf, _image = fab.trois_chemins_distinguables(tmp_path)
    _deposer(fenetre, [dossier])
    fenetre.zone_tampon.bouton_detecter.click()
    qtbot.waitUntil(lambda: bool(releves), timeout=5000)

    assert releves == [0], releves
    # Temoin : le comptage compte VRAIMENT. Un fichier pose dans le dossier de
    # sortie se voit -- sans quoi `0` ne prouverait rien.
    sortie = projet / project_layout.SCAN_FRAMES_DIRNAME
    sortie.mkdir(parents=True, exist_ok=True)
    (sortie / "frame_0001.tiff").write_bytes(b"x")
    assert fenetre.atelier_scan.cardinal_des_frames_ecrites() == 1


@pytest.mark.parametrize("racines_peuplees, attendu", [
    # Un projet NEUF seul : une frame scannee, une seule racine.
    ((project_layout.SCAN_FRAMES_DIRNAME,), 1),
    # Un projet D'AVANT seul -- `EPIC11-ARB-222`, il ne se convertit pas.
    # C'est le cas que l'ancien comptage rendait a ZERO, donc un contrat C qui
    # annoncait « aucune frame ecrite » sur un projet qui venait d'en ecrire.
    ((project_layout.LEGACY_OUTPUT_FRAMES_DIRNAME,), 2),
    # Les deux a la fois -- ce que rien n'ecrit, mais qu'une main fabrique.
    # Le total est la SOMME : le resolveur ne rend l'ancienne racine que si
    # elle existe, donc aucune n'est comptee deux fois.
    ((project_layout.SCAN_FRAMES_DIRNAME,
      project_layout.LEGACY_OUTPUT_FRAMES_DIRNAME), 3),
])
def test_le_comptage_voit_les_DEUX_racines_de_frames_scannees(
        qtbot, tmp_path, racines_peuplees, attendu):
    """Story 11.14 -- volet symetrique du renommage (`EPIC11-ARB-222`).

    **Le cardinal n'est PAS uniforme d'une racine a l'autre** (regle des
    fabriques, point 1) : la racine neuve porte une frame, l'ancienne en porte
    deux. Un comptage qui ne lirait qu'une racine rendrait `1` la ou `3` est
    attendu, et un comptage qui les confondrait rendrait `2` -- deux pannes que
    des cardinaux egaux laisseraient toutes deux passer pour un succes.

    Et les trois cas placent la cible **a chaque bord** de la collection de
    racines (point 4) : seule en tete, seule en queue, puis aux deux -- un
    balayage tronque d'un cote comme de l'autre rougit.
    """
    projet = _projet(tmp_path, manifest=fab.manifest_des_deux_lot())
    fenetre = _fenetre(qtbot, projet, detection_qui_ecrit([]),
                       manifest=fab.manifest_des_deux_lot())
    cardinaux = {project_layout.SCAN_FRAMES_DIRNAME: 1,
                 project_layout.LEGACY_OUTPUT_FRAMES_DIRNAME: 2}
    for nom in racines_peuplees:
        racine = projet / nom / "lot-a"
        racine.mkdir(parents=True, exist_ok=True)
        for index in range(cardinaux[nom]):
            (racine / f"scan_r_12p5_00-00-00-{index:02d}.tiff").write_bytes(b"x")

    assert fenetre.atelier_scan.cardinal_des_frames_ecrites() == attendu


# ---------------------------------------------------------------------------
# AC 4 -- fermer, rouvrir : la completude est toujours la
# ---------------------------------------------------------------------------


def test_la_completude_survit_a_la_reouverture(qtbot, tmp_path):
    manifest = fab.manifest_des_deux_lot()
    projet = _projet(tmp_path, manifest=manifest)
    documents = list(fab.deux_documents_aux_completudes_differentes())
    fenetre = _fenetre(qtbot, projet, detection_qui_ecrit(documents),
                       manifest=manifest)
    dossier, _pdf, _image = fab.trois_chemins_distinguables(tmp_path)
    _deposer(fenetre, [dossier])
    fenetre.zone_tampon.bouton_detecter.click()
    qtbot.waitUntil(lambda: len(fenetre.atelier_scan.annonces()) == 2, timeout=5000)

    avant = modele_chutier.noeud_par_identifiant(
        fenetre.racines(), fab.LOT_INCOMPLET)
    assert avant is not None
    verdict_avant = (avant.badge, avant.detail.get("planches_manquantes"))

    # L'objet fenetre est DETRUIT : rien ne peut survivre en session.
    fenetre.close()
    fenetre.deleteLater()
    del fenetre

    seconde = Coquille()
    qtbot.addWidget(seconde)
    seconde.ouvrir_projet(projet)
    # La CIBLE est le SECOND lot : un chargeur qui rendrait toujours le
    # premier document ne se demasquerait pas autrement.
    apres = modele_chutier.noeud_par_identifiant(
        seconde.racines(), fab.LOT_INCOMPLET)
    assert apres is not None
    assert (apres.badge, apres.detail.get("planches_manquantes")) == verdict_avant
    # Et les deux lot restent distinguables apres relecture.
    complet = modele_chutier.noeud_par_identifiant(
        seconde.racines(), fab.LOT_COMPLET)
    assert complet.badge != apres.badge


def test_la_completude_ne_vit_pas_en_session(qtbot, tmp_path):
    """Aucun etat de completude en attribut de module ni en variable globale."""
    import ast

    from mixed_media_utility.gui import atelier_scan as module_atelier

    interdits = ("completude", "badge", "manquante")
    for module in (module_atelier, chargeur_detections):
        arbre = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        # (a) aucune affectation de MODULE dont le nom parle de completude.
        for noeud in arbre.body:
            if isinstance(noeud, (ast.Assign, ast.AnnAssign)):
                cibles = ([noeud.target] if isinstance(noeud, ast.AnnAssign)
                          else noeud.targets)
                for cible in cibles:
                    nom = getattr(cible, "id", "")
                    assert not any(mot in nom.lower() for mot in interdits), nom
        # (b) aucun `global` : c'est l'autre facon d'ecrire un etat de module.
        globaux = [n for n in ast.walk(arbre) if isinstance(n, ast.Global)]
        assert globaux == [], module.__name__

    # Temoin : le balayage porte sur des modules qui parlent bien de
    # completude -- sinon il serait vert et vide.
    source = Path(module_atelier.__file__).read_text(encoding="utf-8")
    assert "completude" in source.lower()


def test_l_ordre_de_chargement_est_deterministe(tmp_path):
    projet = _projet(tmp_path)
    documents = list(fab.deux_documents_aux_completudes_differentes())
    # Ecrits dans le DESORDRE et sous deux slugs differents : l'ordre rendu
    # doit rester celui du couple (slug, nom), jamais celui du disque.
    fab.ecrire_les_documents(
        projet, [documents[1]], ingest_slug="zulu", noms=["detect-b"])
    fab.ecrire_les_documents(
        projet, [documents[0]], ingest_slug="alpha", noms=["detect-a"])

    for _tentative in range(3):
        resultat = chargeur_detections.charger(projet)
        assert [d.subject.lot_id for d in resultat.documents] == [
            fab.LOT_COMPLET, fab.LOT_INCOMPLET]
        assert resultat.illisibles == ()


def test_un_document_illisible_est_nomme(tmp_path):
    projet = _projet(tmp_path)
    documents = list(fab.deux_documents_aux_completudes_differentes())
    fab.ecrire_les_documents(projet, documents, noms=["detect-a", "detect-b"])
    # Un TROISIEME fichier, illisible, et il n'est PAS le premier.
    abime = (projet / "scans" / fab.INGEST_SLUG / "detections" / "detect-c.json")
    abime.write_text("{ ceci n'est pas du json", encoding="utf-8")

    resultat = chargeur_detections.charger(projet)
    # Les deux lisibles sont la, le troisieme est NOMME avec son motif.
    assert [d.subject.lot_id for d in resultat.documents] == [
        fab.LOT_COMPLET, fab.LOT_INCOMPLET]
    assert len(resultat.illisibles) == 1
    assert resultat.illisibles[0].chemin == abime
    assert resultat.illisibles[0].motif, "un document refuse porte son motif"


def test_deux_detections_du_meme_lot_donnent_deux_documents(qtbot, tmp_path):
    """Contrat AC 4 de 5.25 : le second n'ecrase pas le premier."""
    projet = _projet(tmp_path, manifest=fab.manifest_des_deux_lot())
    premier = [fab.document_du_lot_incomplet()]
    fenetre = _fenetre(
        qtbot, projet,
        detection_qui_ecrit(premier, noms=["detect-20260825120000Z"]),
        manifest=fab.manifest_des_deux_lot())
    dossier, _pdf, _image = fab.trois_chemins_distinguables(tmp_path)
    _deposer(fenetre, [dossier])
    fenetre.zone_tampon.bouton_detecter.click()
    qtbot.waitUntil(
        lambda: bool(fenetre.atelier_scan.annonces()), timeout=5000)
    assert fenetre.atelier_scan.annonces()[0].planches_manquantes == (1,)

    # Seconde passe : le MEME lot, complet cette fois.
    complet = fab.document_du_lot_incomplet()
    complet["pages"].append(fab.fab.page_detectee(
        4, 1, page_count=3, lot_id=fab.LOT_INCOMPLET, rush_id=fab.RUSH,
        project_id=fab.PROJET, largeur_px=201))
    complet["counters"]["pages_present"] = 3
    fenetre.atelier_scan._detecter = detection_qui_ecrit(
        [complet], noms=["detect-20260825130000Z"])
    fenetre.zone_tampon.bouton_detecter.click()
    qtbot.waitUntil(
        lambda: fenetre.atelier_scan.annonces()[0].planches_manquantes == (),
        timeout=5000)

    chemins = chargeur_detections.chemins_de_documents(projet)
    assert len(chemins) == 2, chemins
    # Le PREMIER reste lisible : il n'a pas ete ecrase.
    ancien = chargeur_detections.charger_ces_documents([chemins[0]])
    assert modele_chutier._completude_du_document(ancien.documents) == (
        modele_chutier.BADGE_INCOMPLET, (1,))


# ---------------------------------------------------------------------------
# AC 6 -- le scan d'un autre projet, refuse avec le motif du coeur
# ---------------------------------------------------------------------------


@pytest.fixture
def refus_inter_projets(qtbot, tmp_path):
    """Deux entrees, **une seule** en conflit, et la fautive est la SECONDE."""
    manifest = fab.manifest_des_deux_lot()
    projet = _projet(tmp_path, manifest=manifest)
    dossier, pdf, _image = fab.trois_chemins_distinguables(tmp_path)
    # **Une seule** entree est en conflit, et c'est la SECONDE : une detection
    # qui refuserait toute la passe au premier refus se verrait ici. La
    # premiere n'a pas de payload dans la table, donc rien ne la confronte --
    # elle aboutit.
    par_nom = {pdf.name: fab.payload_de_planche(project_id="proj-etranger")}
    fenetre = _fenetre(
        qtbot, projet, detection_qui_confronte_le_manifest(par_nom),
        manifest=manifest)
    _deposer(fenetre, [dossier, pdf])
    return fenetre, projet, (dossier, pdf), par_nom


def test_un_scan_d_un_autre_projet_echoue_avec_le_motif_du_coeur(
        qtbot, refus_inter_projets):
    fenetre, projet, chemins, par_nom = refus_inter_projets

    # Ce que le coeur dit, mesure a la source.
    with pytest.raises(Exception) as capture:
        scan_manifest.check_scan_conflicts(
            projet, [par_nom[chemins[1].name]],
            failed_page_indexes=(), overwrite=False)
    motif_du_coeur = str(capture.value)

    fenetre.zone_tampon.bouton_detecter.click()
    _attendre(qtbot, fenetre, 2)

    cartes = fenetre.atelier_scan.panneau_taches.cartes()
    assert len(cartes) == 2
    # La SECONDE echoue, la premiere non : une detection qui refuserait tout
    # le lot au premier refus se verrait ici.
    assert cartes[0].etat == executeur.TERMINEE
    assert cartes[1].etat == executeur.ECHOUEE
    assert cartes[1].texte_du_motif() == motif_du_coeur
    assert "proj-etranger" in motif_du_coeur


def test_l_entree_refusee_reste_dans_la_file(qtbot, refus_inter_projets):
    fenetre, _projet, chemins, _par_nom = refus_inter_projets
    fenetre.zone_tampon.bouton_detecter.click()
    _attendre(qtbot, fenetre, 2)

    entrees = fenetre.zone_tampon.modele.entrees
    assert [entree.chemin for entree in entrees] == list(chemins)
    # Elle reste, et elle est NOMMEE : son motif est celui du coeur.
    fautive = entrees[1]
    assert fautive.motif
    assert fenetre.zone_tampon.ligne(fautive.identifiant).texte_du_motif() == (
        fautive.motif)
    # Elle n'est pas rangee dans l'arbre non plus.
    assert modele_chutier.noeud_par_identifiant(
        fenetre.racines(), "proj-etranger") is None


def test_un_refus_n_ecrit_rien(qtbot, refus_inter_projets):
    fenetre, projet, _chemins, _par_nom = refus_inter_projets
    manifest_avant = (projet / "project.json").read_text(encoding="utf-8")

    fenetre.zone_tampon.bouton_detecter.click()
    _attendre(qtbot, fenetre, 2)

    assert chargeur_detections.chemins_de_documents(projet) == ()
    sortie = projet / project_layout.OUTPUT_FRAMES_DIRNAME
    ecrites = (
        [c for c in sortie.rglob("*") if c.is_file()] if sortie.is_dir() else [])
    assert ecrites == []
    assert (projet / "project.json").read_text(encoding="utf-8") == manifest_avant


# ---------------------------------------------------------------------------
# `EPIC7-ARB-90` -- « Souhaitez-vous lancer une nouvelle detection sur ce
# fichier ? » Oui / Non, et ce que chacune des deux reponses fait vraiment.
#
# L'AC prescrit les deux mesures ; ni l'une ni l'autre n'avait ete ecrite. La
# modale est INJECTEE, par le meme motif que la fonction de detection : le
# banc y substitue un appelable qui rend `True` ou `False` sans rien
# afficher, plutot que de piloter une boite bloquante hors de portee d'un
# banc offscreen.
# ---------------------------------------------------------------------------


def _lot_deja_detecte(projet, chemin):
    """Poser un document de detection la ou le coeur ira le chercher.

    Le dossier est demande a `scan_ingest.dossier_de_lot_par_defaut`, comme le
    fait l'atelier : le composer ici ferait de ce test une seconde definition
    du chemin, donc un test qui reste vert quand la vraie derivation change.
    """
    from mixed_media_utility import scan_detect, scan_ingest

    detections = scan_detect.dossier_des_detections(
        scan_ingest.dossier_de_lot_par_defaut(projet, chemin))
    detections.mkdir(parents=True, exist_ok=True)
    depose = detections / "detect-20260826T080000Z.json"
    depose.write_text('{"rang": 0}', encoding="utf-8")
    return depose


def _fenetre_avec_confirmation(qtbot, projet, detecter, reponse):
    """La coquille, avec la modale de remplacement remplacee par `reponse`.

    Rend `(fenetre, questions)`, `questions` recueillant les libelles sur
    lesquels la question a ete posee -- une question qui ne serait jamais
    posee est un ecrasement silencieux, et c'est ce que l'arbitrage interdit.
    """
    questions = []

    def confirmer(objet):
        questions.append(objet)
        return reponse

    fenetre = Coquille()
    qtbot.addWidget(fenetre)
    fenetre.atelier_scan._detecter = detecter
    fenetre.atelier_scan._confirmer_le_remplacement = confirmer
    fenetre.ouvrir_projet(projet, None)
    return fenetre, questions


def test_un_oui_demande_le_remplacement_au_coeur(qtbot, tmp_path):
    """La question est posee, et le « Oui » atteint le POINT D'APPEL du coeur.

    Compter les cartes ne suffirait pas : une implementation qui poserait la
    question puis lancerait sans `remplacer_les_detections` produirait la meme
    carte, et l'ancienne detection resterait -- l'operatrice ayant pourtant
    repondu oui.
    """
    projet = _projet(tmp_path)
    _dossier, pdf, _image = fab.trois_chemins_distinguables(tmp_path)
    depose = _lot_deja_detecte(projet, pdf)
    detecter = fab.detection_qui_ecrit([])
    fenetre, questions = _fenetre_avec_confirmation(qtbot, projet, detecter, True)
    _deposer(fenetre, [pdf])

    fenetre.zone_tampon.bouton_detecter.click()
    _attendre(qtbot, fenetre, 1)

    assert len(questions) == 1, "la question doit etre posee UNE fois"
    assert Path(pdf).name in questions[0]
    assert detecter.appels == [(pdf, True)]
    assert depose.exists(), (
        "l'effacement appartient au COEUR, pas a l'atelier : ce que la GUI "
        "fait, c'est le demander")


def test_un_non_ne_lance_rien_et_laisse_l_entree_dans_la_file(qtbot, tmp_path):
    """Volet symetrique. « Non » ne doit pas etre un « Oui » plus lent :
    aucune tache, aucune carte, et l'entree reste cochee dans la file --
    l'operatrice peut changer d'avis sans re-deposer son fichier."""
    projet = _projet(tmp_path)
    _dossier, pdf, _image = fab.trois_chemins_distinguables(tmp_path)
    depose = _lot_deja_detecte(projet, pdf)
    detecter = fab.detection_qui_ecrit([])
    fenetre, questions = _fenetre_avec_confirmation(qtbot, projet, detecter, False)
    _deposer(fenetre, [pdf])

    fenetre.zone_tampon.bouton_detecter.click()
    qtbot.wait(50)

    assert len(questions) == 1
    assert detecter.appels == []
    assert fenetre.atelier_scan.panneau_taches.cartes() == ()
    assert depose.exists()
    entrees = fenetre.zone_tampon.modele.entrees
    assert [entree.chemin for entree in entrees] == [Path(pdf)]


def test_un_lot_sans_detection_ne_pose_aucune_question(qtbot, tmp_path):
    """Le cas nominal, et le temoin des deux tests ci-dessus : sans lui, ils
    seraient verts sur un code qui pose la question a CHAQUE lancement -- ce
    qui rendrait le geste courant insupportable."""
    projet = _projet(tmp_path)
    _dossier, pdf, _image = fab.trois_chemins_distinguables(tmp_path)
    detecter = fab.detection_qui_ecrit([])
    fenetre, questions = _fenetre_avec_confirmation(qtbot, projet, detecter, False)
    _deposer(fenetre, [pdf])

    fenetre.zone_tampon.bouton_detecter.click()
    _attendre(qtbot, fenetre, 1)

    assert questions == []
    assert detecter.appels == [(pdf, False)]


def test_un_non_ne_pose_pas_la_question_une_seconde_fois(qtbot, tmp_path):
    """Deux entrees du meme fichier, un « Non » : UNE question.

    Defaut mesure : deux modales. Un refus ne laisse aucune tache derriere
    lui, donc il ne laissait AUCUNE trace, et la boucle reposait la question a
    chaque entree du meme chemin -- alors que le dedoublonnage F15 promet
    « aucune seconde question ». Le « Oui », lui, laissait sa tache : c'est
    pourquoi seul le chemin du refus etait fautif, et pourquoi le mesurer
    exigeait le cas « Non » ET le doublon a la fois.
    """
    projet = _projet(tmp_path)
    _dossier, pdf, _image = fab.trois_chemins_distinguables(tmp_path)
    _lot_deja_detecte(projet, pdf)
    detecter = fab.detection_qui_ecrit([])
    fenetre, questions = _fenetre_avec_confirmation(qtbot, projet, detecter, False)
    fenetre.zone_tampon.deposer_des_chemins([pdf])
    fenetre.zone_tampon.deposer_des_chemins([pdf])
    for entree in fenetre.zone_tampon.modele.entrees:
        fenetre.zone_tampon.modele.poser_le_dpi(entree.identifiant, 600)
    fenetre.zone_tampon.rafraichir()
    assert len(fenetre.zone_tampon.modele.entrees) == 2

    fenetre.zone_tampon.bouton_detecter.click()
    qtbot.wait(50)

    assert len(questions) == 1, (
        f"la question a ete posee {len(questions)} fois pour un seul lot")
    assert detecter.appels == []
    assert fenetre.atelier_scan.panneau_taches.cartes() == ()
    # Les DEUX entrees restent dans la file, intactes : un refus ne retire rien.
    assert len(fenetre.zone_tampon.modele.entrees) == 2


def test_un_oui_ne_pose_pas_la_question_une_seconde_fois_non_plus(qtbot, tmp_path):
    """Volet symetrique du dedoublonnage : un « Oui » vaut aussi pour les deux
    entrees, et n'entraine qu'UN SEUL appel au coeur -- deux appels viseraient
    le meme `ingest.json`."""
    projet = _projet(tmp_path)
    _dossier, pdf, _image = fab.trois_chemins_distinguables(tmp_path)
    _lot_deja_detecte(projet, pdf)
    detecter = fab.detection_qui_ecrit([])
    fenetre, questions = _fenetre_avec_confirmation(qtbot, projet, detecter, True)
    fenetre.zone_tampon.deposer_des_chemins([pdf])
    fenetre.zone_tampon.deposer_des_chemins([pdf])
    for entree in fenetre.zone_tampon.modele.entrees:
        fenetre.zone_tampon.modele.poser_le_dpi(entree.identifiant, 600)
    fenetre.zone_tampon.rafraichir()

    fenetre.zone_tampon.bouton_detecter.click()
    _attendre(qtbot, fenetre, 2)

    assert len(questions) == 1
    assert detecter.appels == [(pdf, True)]
    # Une carte par entree (invariant AC 2c), une seule tache derriere.
    assert len(fenetre.atelier_scan.panneau_taches.cartes()) == 2


def test_deux_depots_de_la_meme_selection_en_ordres_inverses_ne_lancent_qu_une_passe(
    qtbot, tmp_path
):
    """F15, sur la quatrieme forme d'entree. Defaut mesure : DEUX appels.

    L'ordre du geste ne fait pas deux lots. `scan_ingest._ordonner_une_selection`
    range une selection par nom normalise avant de l'ingerer : deposer `a` puis
    `b`, ou `b` puis `a`, donne le meme lot, le meme slug, donc le meme
    `ingest.json`. Une cle de dedoublonnage qui gardait l'ordre du depot
    laissait donc partir deux passes concurrentes sur le meme fichier -- ce que
    le dedoublonnage existe precisement pour empecher.
    """
    projet = _projet(tmp_path)
    premiere = tmp_path / "sd" / "a.tiff"
    seconde = tmp_path / "sd" / "b.tiff"
    premiere.parent.mkdir(parents=True, exist_ok=True)
    premiere.write_bytes(b"aa")
    seconde.write_bytes(b"bb")
    detecter = fab.detection_qui_ecrit([])
    fenetre = _fenetre(qtbot, projet, detecter)
    fenetre.zone_tampon.deposer_des_chemins([str(premiere), str(seconde)])
    fenetre.zone_tampon.deposer_des_chemins([str(seconde), str(premiere)])
    for entree in fenetre.zone_tampon.modele.entrees:
        fenetre.zone_tampon.modele.poser_le_dpi(entree.identifiant, 600)
    fenetre.zone_tampon.rafraichir()
    entrees = fenetre.zone_tampon.modele.entrees
    assert len(entrees) == 2
    assert entrees[0].chemins != entrees[1].chemins, (
        "les deux entrees portent bien les chemins dans des ordres DIFFERENTS")

    fenetre.zone_tampon.bouton_detecter.click()
    _attendre(qtbot, fenetre, 2)

    assert len(detecter.appels) == 1, (
        f"{len(detecter.appels)} passes lancees sur le meme lot")
    # Une carte par entree (invariant AC 2c), une seule tache derriere.
    assert len(fenetre.atelier_scan.panneau_taches.cartes()) == 2


def test_deux_selections_REELLEMENT_differentes_lancent_bien_deux_passes(
    qtbot, tmp_path
):
    """Volet symetrique : sans lui, une cle qui rendrait toujours la meme
    valeur passerait le test precedent et ne lancerait plus qu'une detection,
    quoi qu'on depose."""
    projet = _projet(tmp_path)
    premiere = tmp_path / "sd" / "a.tiff"
    seconde = tmp_path / "sd" / "b.tiff"
    troisieme = tmp_path / "sd" / "c.tiff"
    premiere.parent.mkdir(parents=True, exist_ok=True)
    for chemin, octets in ((premiere, b"aa"), (seconde, b"bb"), (troisieme, b"cc")):
        chemin.write_bytes(octets)
    detecter = fab.detection_qui_ecrit([])
    fenetre = _fenetre(qtbot, projet, detecter)
    fenetre.zone_tampon.deposer_des_chemins([str(premiere), str(seconde)])
    fenetre.zone_tampon.deposer_des_chemins([str(seconde), str(troisieme)])
    for entree in fenetre.zone_tampon.modele.entrees:
        fenetre.zone_tampon.modele.poser_le_dpi(entree.identifiant, 600)
    fenetre.zone_tampon.rafraichir()

    fenetre.zone_tampon.bouton_detecter.click()
    _attendre(qtbot, fenetre, 2)

    assert len(detecter.appels) == 2
