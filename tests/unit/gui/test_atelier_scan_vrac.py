# -*- coding: utf-8 -*-
"""Story 7.3, AC 8 -- l'ecran RANGE le vrac, et ce qui resiste reste visible.

Banc SEPARE, et le commit qui le porte l'est aussi : l'AC 8 est la seule de
cette fiche qui depende d'une story exterieure a la vague -- **5.24**, dont
l'AC 13 cable le tri par QR sur `scan detect`. Elle est `done` et fusionnee,
donc cette AC est developpee ; l'isoler garde la propriete que la fiche
demande, a savoir qu'on puisse la lire et la juger seule.

Le scenario est celui du prestataire, mot pour mot dans `EXPERIENCE.md`
(Flow 4, etapes 5-6) : « Detection sur tout : l'outil range chaque page sous
son lot par les QR. Le vrac est devenu une arborescence. » Et son corollaire :
« ce que la detection ne rattache pas reste dans le tampon, visible et nomme,
plutot que de disparaitre ».

**Ce que l'ecran ne fait toujours pas** : aucun decoupage local. Le tri est
une fonction du coeur (5.24, AC 1) ; l'interface lit le rapport de tri et les
documents produits. Mesure par `test_frontieres_scan.py`, garde 2.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import fabriques_scan as fab
from mixed_media_utility import scan_detect, scan_sorting
from mixed_media_utility.gui import catalogue, chargeur_detections, executeur, modele_chutier
from mixed_media_utility.gui.coquille import Coquille


detection_qui_ecrit = fab.detection_qui_ecrit


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
# AC 8 -- l'ecran RANGE le vrac (EPIC7-ARB-64, exige 5.24 livree)
# ---------------------------------------------------------------------------


def test_une_entree_a_deux_lots_produit_deux_cartes(qtbot, tmp_path):
    """**Une** entree, N lot trouves, N cartes -- a ne pas confondre avec 2c."""
    manifest = fab.manifest_des_deux_lot()
    projet = _projet(tmp_path, manifest=manifest)
    documents = list(fab.deux_documents_aux_completudes_differentes())
    fenetre = _fenetre(qtbot, projet, detection_qui_ecrit(documents),
                       manifest=manifest)
    dossier, _pdf, _image = fab.trois_chemins_distinguables(tmp_path)
    _deposer(fenetre, [dossier])

    fenetre.zone_tampon.bouton_detecter.click()
    _attendre(qtbot, fenetre, 2)

    cartes = fenetre.atelier_scan.panneau_taches.cartes()
    assert len(cartes) == 2, [c.texte_de_l_objet() for c in cartes]
    # Chacune nomme SON lot ; la cible est la seconde.
    assert fab.LOT_COMPLET in cartes[0].texte_de_l_objet()
    assert fab.LOT_INCOMPLET in cartes[1].texte_de_l_objet()
    assert fab.LOT_INCOMPLET not in cartes[0].texte_de_l_objet()
    # Les deux nomment l'entree d'origine : c'est le meme depot.
    for carte in cartes:
        assert dossier.name in carte.texte_de_l_objet()
    # Et l'arborescence s'est peuplee des deux branches.
    for identite in (fab.LOT_COMPLET, fab.LOT_INCOMPLET):
        assert modele_chutier.noeud_par_identifiant(
            fenetre.racines(), identite) is not None


def test_un_document_de_detection_par_lot_trouve(qtbot, tmp_path):
    """Comptage REEL du dossier, et chaque document est HOMOGENE."""
    manifest = fab.manifest_des_deux_lot()
    projet = _projet(tmp_path, manifest=manifest)
    documents = list(fab.deux_documents_aux_completudes_differentes())
    fenetre = _fenetre(qtbot, projet, detection_qui_ecrit(documents),
                       manifest=manifest)
    dossier, _pdf, _image = fab.trois_chemins_distinguables(tmp_path)
    _deposer(fenetre, [dossier])
    fenetre.zone_tampon.bouton_detecter.click()
    _attendre(qtbot, fenetre, 2)

    chemins = chargeur_detections.chemins_de_documents(projet)
    assert len(chemins) == 2, chemins
    relus = chargeur_detections.charger_ces_documents(chemins)
    identites = []
    for document in relus.documents:
        # HOMOGENE, et mesure sur les PAGES : chaque page identifiee declare
        # le lot du sujet, et un seul. Un document qui melangerait deux lot
        # passerait un test qui ne regarderait que `subject.lot_id`.
        declares = {
            page.decoded_lot_id for page in document.pages
            if page.decoded_lot_id is not None
        }
        assert declares == {document.subject.lot_id}, declares
        assert document.pages, "un document homogene porte des pages"
        identites.append(document.subject.lot_id)
    assert identites == [fab.LOT_COMPLET, fab.LOT_INCOMPLET]
    assert len(set(identites)) == 2


def test_le_reliquat_reste_dans_le_tampon(qtbot, tmp_path):
    """Ce que le tri n'a rattache a rien reste dans la file, NOMME."""
    manifest = fab.manifest_des_deux_lot()
    projet = _projet(tmp_path, manifest=manifest)
    rapport = fab.rapport_de_tri_avec_reliquat()
    fenetre = _fenetre(
        qtbot, projet,
        detection_qui_ecrit([fab.document_du_lot_complet()], rapport=rapport),
        manifest=manifest)
    dossier, pdf, _image = fab.trois_chemins_distinguables(tmp_path)
    entrees = _deposer(fenetre, [dossier, pdf])
    fenetre.zone_tampon.bouton_detecter.click()
    _attendre(qtbot, fenetre, 2)

    # Les deux entrees sont toujours la.
    assert len(fenetre.zone_tampon.modele.entrees) == 2
    reste = fenetre.zone_tampon.modele.entrees[0].reliquat
    assert len(reste) == 1
    localisateur, motif = reste[0]
    # La page est NOMMEE par son localisateur, et le motif est celui du
    # vocabulaire ferme de 5.24 -- lu du rapport, jamais recompose.
    attendu = rapport.partition.reliquat[0]
    assert localisateur == attendu.locator.source_path
    assert motif == attendu.motif
    from mixed_media_utility import scan_detect, scan_sorting
    assert motif in scan_sorting.MOTIFS_DE_RELIQUAT
    # Et il est AFFICHE : un modele juste et une surface muette ne valent rien.
    affiche = fenetre.zone_tampon.ligne(entrees[0].identifiant).texte_du_reliquat()
    assert localisateur in affiche and motif in affiche


def test_un_vrac_partiel_n_est_jamais_annonce_complet(qtbot, tmp_path):
    """La meme pile : un lot range, une page au reliquat -> rien de complet."""
    manifest = fab.manifest_des_deux_lot()
    projet = _projet(tmp_path, manifest=manifest)
    rapport = fab.rapport_de_tri_avec_reliquat()
    fenetre = _fenetre(
        qtbot, projet,
        detection_qui_ecrit([fab.document_du_lot_incomplet()], rapport=rapport),
        manifest=manifest)
    dossier, _pdf, _image = fab.trois_chemins_distinguables(tmp_path)
    _deposer(fenetre, [dossier])
    fenetre.zone_tampon.bouton_detecter.click()
    qtbot.waitUntil(
        lambda: bool(fenetre.atelier_scan.annonces()), timeout=5000)

    textes = fenetre.atelier_scan.textes_annonces()
    assert textes
    # Aucun libelle de rattachement complet nulle part dans l'annonce.
    for texte in textes:
        assert catalogue.CHAINES["badge-complet"] not in texte
        assert catalogue.CHAINES["atelier-scan-aucune-planche-manquante"] not in texte
    assert catalogue.CHAINES["badge-incomplet"] in textes[0]
    # Et le reliquat est visible, nomme.
    assert fenetre.zone_tampon.modele.entrees[0].reliquat


# ---------------------------------------------------------------------------
# F13 (revue de vague 3) -- un tri.json illisible leve encore (P9), mais
# AVANT toute mutation de carte : la fenetre ne reste jamais a moitie mise a
# jour.
# ---------------------------------------------------------------------------


def test_un_tri_illisible_ne_laisse_pas_la_fenetre_a_moitie_mise_a_jour(
        qtbot, tmp_path):
    """F13 -- regression DETERMINISTE du flake reproduit par la revue.

    La revue de vague 3 (couche 1) a reproduit un `tri.json` lu a ZERO
    OCTET par une course de threads (1 echec sur 5 suites GUI completes,
    7-10% mesure). Cette course n'est PAS rejouee ici -- une course entre
    threads OS ne se reproduit pas de facon fiable en test. La panne est
    posee A L'AVANCE a la place : le fichier est deja illisible avant meme
    que le clic ne parte, donc AUCUNE course a gagner, et la meme ligne de
    code (`chargeur_detections.charger_le_rapport_de_tri`) leve pour la
    meme raison (`json.JSONDecodeError` sur un contenu vide).

    Deux choses sont verifiees : (a) la garantie de la docstring de
    `charger_le_rapport_de_tri` tient encore -- l'exception n'est PAS avalee
    -- et (b) contrairement a l'etat d'avant ce correctif, elle survient
    AVANT toute mutation de carte : rien n'est a moitie mis a jour.
    """
    manifest = fab.manifest_des_deux_lot()
    projet = _projet(tmp_path, manifest=manifest)
    documents = [fab.document_du_lot_complet()]
    fenetre = _fenetre(
        qtbot, projet, detection_qui_ecrit(documents), manifest=manifest)
    dossier, _pdf, _image = fab.trois_chemins_distinguables(tmp_path)
    entrees = _deposer(fenetre, [dossier])

    # Le tri.json de CE slug est illisible AVANT le clic : la panne est
    # certaine, pas une course.
    chemin_du_tri = chargeur_detections.chemin_du_rapport_de_tri(
        projet, fab.INGEST_SLUG)
    chemin_du_tri.parent.mkdir(parents=True, exist_ok=True)
    chemin_du_tri.write_text("", encoding="utf-8")

    with qtbot.captureExceptions() as exceptions:
        fenetre.zone_tampon.bouton_detecter.click()
        qtbot.waitUntil(lambda: len(exceptions) >= 1, timeout=5000)

    # (a) ca leve encore -- ce n'est jamais avale silencieusement (P9).
    assert len(exceptions) == 1
    assert exceptions[0][0] is json.decoder.JSONDecodeError

    # (b) et RIEN n'a ete mute avant que l'exception ne remonte : la carte
    # n'a jamais atteint TERMINEE, aucun reliquat ni hors-perimetre pose,
    # aucune annonce.
    carte = fenetre.atelier_scan.panneau_taches.cartes()[0]
    assert carte.etat == executeur.EN_COURS
    entree = fenetre.zone_tampon.modele.entree(entrees[0].identifiant)
    assert entree.reliquat == ()
    assert entree.hors_perimetre == ()
    assert fenetre.atelier_scan.annonces() == ()


# ---------------------------------------------------------------------------
# F14 (revue de vague 3) -- hors perimetre : classe DISJOINTE du reliquat,
# et visible.
# ---------------------------------------------------------------------------


def _rapport_avec_reliquat_et_hors_perimetre(*, ingest_slug=fab.INGEST_SLUG):
    """Un lot range, UNE page au reliquat, DEUX pages hors perimetre.

    Regle des fabriques : les deux entrees hors perimetre sont
    distinguables (localisateur, `projet_a_utiliser` differents), et les
    assertions du test visent la SECONDE -- un appariement inverse entre
    localisateur/motif/projet ne se verrait pas sur une seule entree.
    """
    payload_une = {"project_id": fab.PROJET, "rush_id": fab.RUSH,
                   "lot_id": fab.LOT_COMPLET, "page_index": 0, "page_count": 1}
    lot = scan_sorting.LotTrie(
        project_id=fab.PROJET, rush_id=fab.RUSH, lot_id=fab.LOT_COMPLET,
        pages=(
            scan_sorting.PageRangee(
                read_rank=0,
                locator=scan_sorting.Localisateur("scans/vrac/page_01.tiff"),
                payload=payload_une),
        ),
    )
    partition = scan_sorting.PartitionDeVrac(
        lots=(lot,),
        reliquat=(
            scan_sorting.EntreeDeReliquat(
                read_rank=1,
                locator=scan_sorting.Localisateur("scans/vrac/page_02.tiff"),
                motif=scan_sorting.RELIQUAT_QR_MUET,
                detail=None),
        ),
        hors_perimetre=(
            scan_sorting.EntreeHorsPerimetre(
                read_rank=2,
                locator=scan_sorting.Localisateur("scans/vrac/page_03.tiff"),
                motif=scan_sorting.HORS_PERIMETRE_PROJET_ETRANGER,
                projet_a_utiliser="proj-voisin-1"),
            scan_sorting.EntreeHorsPerimetre(
                read_rank=3,
                locator=scan_sorting.Localisateur("scans/vrac/page_04.tiff"),
                motif=scan_sorting.HORS_PERIMETRE_PROJET_ETRANGER,
                projet_a_utiliser="proj-voisin-2"),
        ),
    )
    return scan_sorting.RapportDeTri(
        ingest_slug=ingest_slug, project_id=fab.PROJET, partition=partition)


def test_le_hors_perimetre_reste_dans_le_tampon_disjoint_du_reliquat(
        qtbot, tmp_path):
    """F14 -- une page hors perimetre s'affiche, SANS se fondre dans le reliquat.

    Avant ce correctif : `_poser_le_reliquat` ne lisait que
    `partition.reliquat` ; `partition.hors_perimetre` n'etait lu par AUCUN
    module de `gui/` (grep : zero occurrence).
    """
    manifest = fab.manifest_des_deux_lot()
    projet = _projet(tmp_path, manifest=manifest)
    rapport = _rapport_avec_reliquat_et_hors_perimetre()
    fenetre = _fenetre(
        qtbot, projet,
        detection_qui_ecrit([fab.document_du_lot_complet()], rapport=rapport),
        manifest=manifest)
    dossier, _pdf, _image = fab.trois_chemins_distinguables(tmp_path)
    entrees = _deposer(fenetre, [dossier])
    fenetre.zone_tampon.bouton_detecter.click()
    _attendre(qtbot, fenetre, 1)

    entree = fenetre.zone_tampon.modele.entree(entrees[0].identifiant)
    # (a) le reliquat et le hors-perimetre restent DEUX listes disjointes --
    # jamais fusionnees en une seule.
    assert len(entree.reliquat) == 1
    assert len(entree.hors_perimetre) == 2
    localisateur_reliquat, _motif_reliquat = entree.reliquat[0]
    assert localisateur_reliquat == "scans/vrac/page_02.tiff"
    localisateurs_hp = {loc for loc, _m, _p in entree.hors_perimetre}
    assert localisateurs_hp == {"scans/vrac/page_03.tiff", "scans/vrac/page_04.tiff"}
    assert localisateur_reliquat not in localisateurs_hp

    # (b) la CIBLE, en SECONDE position, garde SON propre projet_a_utiliser --
    # verbatim, jamais recompose.
    loc2, motif2, projet2 = entree.hors_perimetre[1]
    assert loc2 == "scans/vrac/page_04.tiff"
    assert projet2 == "proj-voisin-2"
    assert motif2 == scan_sorting.HORS_PERIMETRE_PROJET_ETRANGER
    loc1, _motif1, projet1 = entree.hors_perimetre[0]
    assert projet1 == "proj-voisin-1"
    assert projet1 != projet2

    # (c) et c'est AFFICHE : un modele juste et une surface muette ne valent
    # rien -- meme regle que le reliquat.
    affiche = fenetre.zone_tampon.ligne(
        entrees[0].identifiant).texte_du_hors_perimetre()
    assert "scans/vrac/page_03.tiff" in affiche
    assert "scans/vrac/page_04.tiff" in affiche
    assert "proj-voisin-1" in affiche
    assert "proj-voisin-2" in affiche


def test_hors_perimetre_seul_reste_visible_meme_quand_la_carte_est_muette(
        qtbot, tmp_path):
    """F14 -- le regime EXACT ou le defaut mordait (EC-1 de la revue).

    Quand le tri range ZERO page en lot et que toutes les pages identifiees
    finissent hors perimetre, `_detecter_le_vrac` rend `documents=()` et
    `motif_d_arret=None` -- aucun des deux arrets nommes ne s'applique.
    `_sur_fin` prend la branche `if not documents:` et pose une carte
    TERMINEE dont le motif est masque (`cartes_taches.py`, hors perimetre de
    ce correctif -- non change). Avant F14, RIEN d'autre ne disait a
    l'operateur qu'une page a ete refusee comme etrangere au projet.
    """
    manifest = fab.manifest_des_deux_lot()
    projet = _projet(tmp_path, manifest=manifest)
    partition = scan_sorting.PartitionDeVrac(
        hors_perimetre=(
            scan_sorting.EntreeHorsPerimetre(
                read_rank=0,
                locator=scan_sorting.Localisateur("scans/vrac/page_01.tiff"),
                motif=scan_sorting.HORS_PERIMETRE_PROJET_ETRANGER,
                projet_a_utiliser="proj-voisin"),
            scan_sorting.EntreeHorsPerimetre(
                read_rank=1,
                locator=scan_sorting.Localisateur("scans/vrac/page_02.tiff"),
                motif=scan_sorting.HORS_PERIMETRE_PROJET_ETRANGER,
                # Le QR n'a pas livre le projet : `None` reste `None`, jamais
                # transforme en la chaine "None".
                projet_a_utiliser=None),
        ),
    )
    rapport = scan_sorting.RapportDeTri(
        ingest_slug=fab.INGEST_SLUG, project_id=fab.PROJET, partition=partition)
    fenetre = _fenetre(
        qtbot, projet, detection_qui_ecrit([], rapport=rapport),
        manifest=manifest)
    dossier, _pdf, _image = fab.trois_chemins_distinguables(tmp_path)
    entrees = _deposer(fenetre, [dossier])
    fenetre.zone_tampon.bouton_detecter.click()
    _attendre(qtbot, fenetre, 1)

    carte = fenetre.atelier_scan.panneau_taches.cartes()[0]
    # Le regime exact du defaut : la carte EST muette (comportement de
    # `cartes_taches.py`, hors perimetre de ce correctif).
    assert carte.etat == executeur.TERMINEE
    assert carte.texte_du_motif() == ""

    # Mais la zone tampon, elle, ne l'est plus.
    entree = fenetre.zone_tampon.modele.entree(entrees[0].identifiant)
    assert len(entree.hors_perimetre) == 2
    loc2, _motif2, projet2 = entree.hors_perimetre[1]
    assert loc2 == "scans/vrac/page_02.tiff"
    assert projet2 is None
    affiche = fenetre.zone_tampon.ligne(
        entrees[0].identifiant).texte_du_hors_perimetre()
    assert "proj-voisin" in affiche
    assert "scans/vrac/page_01.tiff" in affiche
    assert "scans/vrac/page_02.tiff" in affiche


def test_le_rapport_de_tri_n_est_JAMAIS_observable_a_moitie_ecrit(
        tmp_path, monkeypatch):
    """F13 moitie (b) -- l'ecriture atomique, mesuree par sa propriete.

    La couche 1 a reproduit un flake a 7-10 % des suites GUI completes :
    `charger_le_rapport_de_tri` tombait sur un `tri.json` de **zero octet** et
    levait `JSONDecodeError`. Le mecanisme est nomme : la fabrique ecrivait par
    `write_text` nu, et `write_text` **tronque le fichier avant de le
    remplir** -- un lecteur qui tombe dans cette fenetre lit un fichier vide.

    Ce test ne rejoue pas la course : une fenetre de troncature ne se
    reproduit pas a la demande, et un test qui l'attendrait serait lui-meme
    flaky. Il mesure la **propriete** qui ferme la course, et qui est
    deterministe : pendant toute la duree de la seconde ecriture, la cible sur
    disque porte encore le PREMIER document, complet. C'est ce que `os.replace`
    garantit et ce que `write_text` ne garantit pas.

    L'observation se fait a l'instant precis ou l'ancien code avait deja
    tronque : juste avant le renommage.
    """
    rapport = fab.rapport_de_tri_avec_reliquat()
    chemin = fab.ecrire_le_rapport_de_tri(tmp_path, rapport)
    premier_contenu = chemin.read_text(encoding="utf-8")
    assert premier_contenu, "la fabrique doit avoir ecrit un premier document"

    observe = {}
    vrai_replace = scan_detect.os.replace

    def replace_observe(source, cible):
        # L'instant ou `write_text` aurait deja tronque la cible.
        observe["avant_renommage"] = Path(cible).read_text(encoding="utf-8")
        return vrai_replace(source, cible)

    monkeypatch.setattr(scan_detect.os, "replace", replace_observe)
    fab.ecrire_le_rapport_de_tri(tmp_path, rapport)

    # (a) la fabrique passe bien par le chemin atomique : sans `os.replace`,
    #     l'observateur n'aurait jamais ete appele.
    assert "avant_renommage" in observe, "le chemin atomique n'a pas ete pris"
    # (b) et a cet instant la cible portait le document COMPLET, pas zero
    #     octet. C'est l'assertion qui discrimine : sous `write_text` nu, la
    #     cible est deja tronquee ici, et c'est precisement le fichier vide
    #     que la couche 1 a vu lire.
    assert observe["avant_renommage"] != ""
    assert observe["avant_renommage"] == premier_contenu
    # (c) et le nouveau document est bien arrive, lisible.
    assert json.loads(chemin.read_text(encoding="utf-8"))
