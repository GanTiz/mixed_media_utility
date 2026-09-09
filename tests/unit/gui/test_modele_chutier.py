# -*- coding: utf-8 -*-
"""Story 7.2, AC 2 -- le modele d'arbre du chutier.

L'arbre se construit de **deux sources et d'elles seules** : le manifest du
projet ouvert et les documents de detection de 5.25. L'ordre d'affichage est
l'ordre des sources -- **jamais re-trie localement** --, et l'appariement
lot <-> noeud se fait **par identifiant**, jamais par position.

C'est le finding **E14** promu AC : la classe de defaut la plus payee du
depot (5.6/`M33`, 5.7/`M25`, 5.8). Chaque fixture applique la regle des
fabriques, y compris celles que les AC ne nomment pas.
"""

import re
from pathlib import Path

import pytest

import fabriques_chutier as fab
from mixed_media_utility.gui import modele_chutier as modele


# ---------------------------------------------------------------------------
# AC 2 -- deux lots du meme rush a deux cadences, cible en SECONDE position.
# ---------------------------------------------------------------------------


def _par_identifiant(noeuds, identifiant):
    """Retrouver un noeud par SON identifiant -- jamais par sa position."""
    trouves = [noeud for noeud in noeuds if noeud.identifiant == identifiant]
    assert len(trouves) == 1, f"{identifiant} introuvable ou duplique : {trouves}"
    return trouves[0]


def test_deux_lots_du_meme_rush_a_deux_cadences_portent_chacun_son_etat():
    # Le cas nominal v2.1 (risque R12) : la cible des assertions est le lot
    # `lot-cadence-18`, en SECONDE position, et l'assertion est nominative --
    # quel lot porte quelle cadence et quel etat, jamais les seuls cardinaux.
    arbre = modele.construire_arbre(
        fab.manifest_deux_lots_meme_rush(),
        existe=fab.liaison_factice(["medias/alpha.mov"]),
    )
    rush = _par_identifiant(arbre, "rush-alpha")
    assert len(rush.enfants) == 2

    cible = _par_identifiant(rush.enfants, "lot-cadence-18")
    autre = _par_identifiant(rush.enfants, "lot-cadence-24")

    assert cible.detail["fps_target_exact"] == "18/1"
    assert cible.badge == modele.BADGE_INCOMPLET
    assert autre.detail["fps_target_exact"] == "24000/1001"
    assert autre.badge == modele.BADGE_COMPLET
    # Les deux cadences sont DIFFERENTES : un appariement inverse se voit.
    assert cible.detail["fps_target_exact"] != autre.detail["fps_target_exact"]


def test_l_appariement_lot_noeud_se_fait_par_identifiant_jamais_par_position():
    # Les lots du manifest sont donnes dans un ordre ou le lot du second rush
    # precede un lot du premier : un appariement positionnel rattacherait le
    # mauvais lot au mauvais rush.
    manifest = fab.manifest_deux_rushes_deux_lots_chacun()
    manifest["lots"] = [
        manifest["lots"][2],  # lot-beta-1
        manifest["lots"][0],  # lot-alpha-1
        manifest["lots"][3],  # lot-beta-2
        manifest["lots"][1],  # lot-alpha-2
    ]
    arbre = modele.construire_arbre(
        manifest, existe=fab.liaison_factice(["medias/alpha.mov", "medias/beta.mov"])
    )
    beta = _par_identifiant(arbre, "rush-beta")
    alpha = _par_identifiant(arbre, "rush-alpha")
    assert [noeud.identifiant for noeud in beta.enfants] == ["lot-beta-1", "lot-beta-2"]
    assert [noeud.identifiant for noeud in alpha.enfants] == [
        "lot-alpha-1",
        "lot-alpha-2",
    ]


# ---------------------------------------------------------------------------
# AC 2 -- l'ordre vient des sources, jamais re-trie localement.
# ---------------------------------------------------------------------------


def test_l_ordre_des_lots_est_celui_du_manifest_ni_alphabetique_ni_chronologique():
    manifest = fab.manifest_deux_lots_meme_rush()
    # Ordre du manifest DELIBEREMENT contraire a l'ordre alphabetique :
    # "lot-cadence-24" avant "lot-cadence-18". Un tri local le retournerait.
    assert [lot["lot_id"] for lot in manifest["lots"]] == [
        "lot-cadence-24",
        "lot-cadence-18",
    ]
    arbre = modele.construire_arbre(
        manifest, existe=fab.liaison_factice(["medias/alpha.mov"])
    )
    rendus = [noeud.identifiant for noeud in arbre[0].enfants]
    assert rendus == ["lot-cadence-24", "lot-cadence-18"]
    # Symetrique : le tri alphabetique donnerait l'ordre inverse.
    assert rendus != ["lot-cadence-18", "lot-cadence-24"]


def test_l_ordre_des_rushes_est_celui_du_manifest():
    manifest = fab.manifest_deux_rushes_deux_lots_chacun()
    manifest["rushes"] = list(reversed(manifest["rushes"]))
    arbre = modele.construire_arbre(
        manifest, existe=fab.liaison_factice(["medias/alpha.mov", "medias/beta.mov"])
    )
    assert [noeud.identifiant for noeud in arbre] == ["rush-beta", "rush-alpha"]


def test_l_ordre_des_pages_est_celui_de_la_detection_jamais_l_ordre_des_page_index():
    # Les pages sont consignees dans l'ordre de LECTURE (`read_rank`) : la
    # planche 2 a ete lue avant la planche 0. « Jamais re-triees. »
    pages = [
        fab.page_detectee(0, 2, lot_id="lot-cadence-24", largeur_px=110),
        fab.page_detectee(1, 0, lot_id="lot-cadence-24", largeur_px=120),
        fab.page_detectee(2, 1, lot_id="lot-cadence-24", largeur_px=130),
    ]
    document = fab.document_de_detection(
        lot_id="lot-cadence-24", pages=pages, pages_expected=3
    )
    arbre = modele.construire_arbre(
        fab.manifest_deux_lots_meme_rush(),
        documents_de_detection=[document],
        existe=fab.liaison_factice(["medias/alpha.mov"]),
    )
    lot = _par_identifiant(arbre[0].enfants, "lot-cadence-24")
    planches = [noeud for noeud in lot.enfants if noeud.type == modele.TYPE_PLANCHE]
    assert [noeud.page_index for noeud in planches] == [2, 0, 1]


# ---------------------------------------------------------------------------
# AC 2 -- `read_rank` et `page_index`, jamais l'un deduit de l'autre.
# ---------------------------------------------------------------------------


def test_une_page_dont_le_page_index_differe_du_read_rank_expose_les_deux():
    # « Le 3e fichier du dossier declare etre la page 1 » : contrat de module
    # de `scan_previz`, porte dans la GUI par E14. Cible en SECONDE position.
    pages = [
        fab.page_detectee(0, 4, lot_id="lot-cadence-24", largeur_px=110),
        fab.page_detectee(2, 1, lot_id="lot-cadence-24", largeur_px=140),
    ]
    document = fab.document_de_detection(
        lot_id="lot-cadence-24", pages=pages, pages_expected=5
    )
    arbre = modele.construire_arbre(
        fab.manifest_deux_lots_meme_rush(),
        documents_de_detection=[document],
        existe=fab.liaison_factice(["medias/alpha.mov"]),
    )
    lot = _par_identifiant(arbre[0].enfants, "lot-cadence-24")
    planches = [noeud for noeud in lot.enfants if noeud.type == modele.TYPE_PLANCHE]
    cible = planches[1]

    assert cible.page_index == 1
    scan = cible.enfants[0]
    assert scan.type == modele.TYPE_SCAN
    assert scan.read_rank == 2
    assert scan.page_index == 1
    # Les deux informations sont portees SEPAREMENT : ni l'une ni l'autre
    # n'est reconstituee a partir de sa jumelle.
    assert scan.read_rank != scan.page_index
    assert scan.detail["source_path_relative"].endswith("lu-2.tif")


def test_deux_documents_du_meme_lot_qui_se_contredisent_ne_nomment_aucune_manquante():
    """Cardinal attendu contradictoire : incomplet, et AUCUNE manquante nommee.

    Trouve par la revue de vague 2 (couche 2) : c'etait la SEULE combinaison
    a deux elements que les fabriques n'exercaient pas -- tous les autres
    scenarios a deux documents d'un meme lot portaient le MEME
    `pages_expected`. La branche `len(attendus) != 1` de
    `_completude_du_document` n'etait atteinte par aucun test.

    Le comportement pinne ici est **voulu**, pas un defaut : quand deux
    documents se contredisent, le cardinal attendu n'est pas derivable, donc
    la liste des planches manquantes ne l'est pas non plus. On refuse d'en
    nommer plutot que d'en inventer depuis l'un des deux cardinaux -- et le
    badge reste `incomplet`, jamais `complet` : une contradiction ne se lit
    jamais comme une garantie.

    Le lot vise est **detecte seul** (absent du manifest) : c'est la seule
    facon d'atteindre `_completude_du_document`, un lot deja reconstruit
    tirant son badge des trois entiers du manifest. Il est en TROISIEME
    position sous son rush, jamais en tete.
    """
    def document(pages_expected, page_index, empreinte, slug):
        return fab.document_de_detection(
            lot_id="lot-detecte-seul",
            pages=[
                fab.page_detectee(
                    0, page_index,
                    lot_id="lot-detecte-seul",
                    largeur_px=110 + 10 * page_index,
                )
            ],
            pages_expected=pages_expected,
            empreinte=empreinte,
            ingest_slug=slug,
        )

    def lot_detecte(pages_expected_du_second):
        arbre = modele.construire_arbre(
            fab.manifest_deux_lots_meme_rush(),
            documents_de_detection=[
                document(3, 0, fab.EMPREINTES[0], "ing-premiere-passe"),
                document(pages_expected_du_second, 1, fab.EMPREINTES[1],
                         "ing-relecture"),
            ],
            existe=fab.liaison_factice(["medias/alpha.mov"]),
        )
        return _par_identifiant(arbre[0].enfants, "lot-detecte-seul")

    # Les deux documents se contredisent (3 contre 2) : rien n'est nomme.
    contredit = lot_detecte(2)
    assert contredit.badge == modele.BADGE_INCOMPLET
    assert contredit.detail["planches_manquantes"] == ()

    # Volet symetrique, et il est indispensable : les MEMES documents avec
    # des cardinaux D'ACCORD nomment bien la planche absente. Sans lui,
    # l'assertion ci-dessus passerait aussi sur un code qui ne nommerait
    # JAMAIS de manquante -- exactement la tautologie que la politique du
    # depot traque.
    accorde = lot_detecte(3)
    assert accorde.badge == modele.BADGE_INCOMPLET
    assert accorde.detail["planches_manquantes"] == (2,)


def test_plusieurs_scans_de_la_meme_planche_se_rangent_sous_la_meme_planche():
    # Story 5.14 : la meme planche relue deux fois. Deux documents de
    # detection DISTINGUABLES (empreintes differentes), cible en seconde
    # position -- la planche 1, pas la planche 0.
    premier = fab.document_de_detection(
        lot_id="lot-cadence-24",
        pages=[
            fab.page_detectee(0, 0, lot_id="lot-cadence-24", largeur_px=110),
            fab.page_detectee(1, 1, lot_id="lot-cadence-24", largeur_px=120),
        ],
        pages_expected=2,
        empreinte=fab.EMPREINTES[0],
    )
    second = fab.document_de_detection(
        lot_id="lot-cadence-24",
        pages=[fab.page_detectee(0, 1, lot_id="lot-cadence-24", largeur_px=150)],
        pages_expected=2,
        empreinte=fab.EMPREINTES[1],
        ingest_slug="ingest-relecture",
    )
    arbre = modele.construire_arbre(
        fab.manifest_deux_lots_meme_rush(),
        documents_de_detection=[premier, second],
        existe=fab.liaison_factice(["medias/alpha.mov"]),
    )
    lot = _par_identifiant(arbre[0].enfants, "lot-cadence-24")
    planches = [noeud for noeud in lot.enfants if noeud.type == modele.TYPE_PLANCHE]
    assert [noeud.page_index for noeud in planches] == [0, 1]
    assert len(planches[0].enfants) == 1
    assert len(planches[1].enfants) == 2
    # Les deux scans de la planche 1 sont DISTINCTS (identifiants differents).
    identifiants = {scan.identifiant for scan in planches[1].enfants}
    assert len(identifiants) == 2


# ---------------------------------------------------------------------------
# AC 2 -- completude : deux sources, deux regles, aucune re-derivation.
# ---------------------------------------------------------------------------


def test_la_completude_d_un_lot_reconstruit_vient_des_trois_entiers_du_manifest():
    # Regle ecrite au schema : complet = reconstructed == expected ET
    # synthetic == 0. Cible (`lot-cadence-18`) en SECONDE position.
    arbre = modele.construire_arbre(
        fab.manifest_deux_lots_meme_rush(),
        existe=fab.liaison_factice(["medias/alpha.mov"]),
    )
    lots = arbre[0].enfants
    assert _par_identifiant(lots, "lot-cadence-18").badge == modele.BADGE_INCOMPLET
    assert _par_identifiant(lots, "lot-cadence-24").badge == modele.BADGE_COMPLET


def test_un_lot_reconstruit_complet_mais_avec_des_mires_n_est_jamais_dit_complet():
    # « complet-avec-mires » n'est JAMAIS confondu avec « complet »
    # (EXPERIENCE.md, Etats). Cible en seconde position.
    manifest = fab.manifest_deux_lots_meme_rush()
    manifest["lots"][1]["reconstructed_frame_count"] = 9
    manifest["lots"][1]["synthetic_frame_count"] = 2
    arbre = modele.construire_arbre(
        manifest, existe=fab.liaison_factice(["medias/alpha.mov"])
    )
    cible = _par_identifiant(arbre[0].enfants, "lot-cadence-18")
    assert cible.badge == modele.BADGE_COMPLET_AVEC_MIRES
    assert cible.badge != modele.BADGE_COMPLET


def test_la_completude_d_un_lot_detecte_est_derivee_du_document_seul():
    # Fiche 5.25, AC 4 : les index absents se derivent de
    # `counters.pages_expected` et de l'ensemble des `page_index` presents,
    # sans consulter le manifest. Ici le manifest ne porte AUCUN cardinal de
    # frames pour ces lots, et la cible est en seconde position.
    manifest = fab.manifest_deux_rushes_deux_lots_chacun()
    complet = fab.document_de_detection(
        lot_id="lot-beta-1",
        pages=[
            fab.page_detectee(0, 0, lot_id="lot-beta-1", largeur_px=110),
            fab.page_detectee(1, 1, lot_id="lot-beta-1", largeur_px=120),
        ],
        pages_expected=2,
        rush_id="rush-beta",
        empreinte=fab.EMPREINTES[0],
    )
    troue = fab.document_de_detection(
        lot_id="lot-beta-2",
        pages=[
            fab.page_detectee(0, 0, lot_id="lot-beta-2", largeur_px=130),
            fab.page_detectee(1, 2, lot_id="lot-beta-2", largeur_px=140),
        ],
        pages_expected=3,
        rush_id="rush-beta",
        empreinte=fab.EMPREINTES[1],
    )
    arbre = modele.construire_arbre(
        manifest,
        documents_de_detection=[complet, troue],
        existe=fab.liaison_factice(["medias/alpha.mov", "medias/beta.mov"]),
    )
    beta = _par_identifiant(arbre, "rush-beta")
    assert _par_identifiant(beta.enfants, "lot-beta-1").badge == modele.BADGE_COMPLET
    cible = _par_identifiant(beta.enfants, "lot-beta-2")
    assert cible.badge == modele.BADGE_INCOMPLET
    # Le detail nomme la planche qui manque -- l'index 1, pas un cardinal.
    assert cible.detail["planches_manquantes"] == (1,)


def test_un_lot_sans_document_ni_cardinal_ne_porte_aucun_badge():
    # Symetrique du test precedent : sans source de completude, on n'invente
    # pas un verdict (un badge absent est une information, pas un defaut).
    manifest = fab.manifest_deux_rushes_deux_lots_chacun()
    arbre = modele.construire_arbre(
        manifest, existe=fab.liaison_factice(["medias/alpha.mov", "medias/beta.mov"])
    )
    beta = _par_identifiant(arbre, "rush-beta")
    assert _par_identifiant(beta.enfants, "lot-beta-2").badge is None


# ---------------------------------------------------------------------------
# AC 2 / role 3 -- la branche se reconstruit depuis un scan seul, sans badge
# de deduction (`EPIC7-ARB-14`), et jamais en affichage retourne (A1).
# ---------------------------------------------------------------------------


def test_un_lot_connu_du_seul_document_de_detection_peuple_l_arbre_comme_les_autres():
    manifest = fab.manifest_deux_lots_meme_rush()
    orphelin = fab.document_de_detection(
        lot_id="lot-venu-du-scan",
        rush_id="rush-gamma",
        pages=[
            fab.page_detectee(0, 0, lot_id="lot-venu-du-scan", rush_id="rush-gamma"),
            fab.page_detectee(
                1, 1, lot_id="lot-venu-du-scan", rush_id="rush-gamma", largeur_px=180
            ),
        ],
        pages_expected=2,
        empreinte=fab.EMPREINTES[2],
    )
    arbre = modele.construire_arbre(
        manifest,
        documents_de_detection=[orphelin],
        existe=fab.liaison_factice(["medias/alpha.mov"]),
    )
    # La branche reconstruite vient APRES celles du manifest : l'ordre des
    # sources d'abord, la reconstruction ensuite -- jamais un affichage
    # retourne (correction A1).
    assert [noeud.identifiant for noeud in arbre] == ["rush-alpha", "rush-gamma"]
    gamma = _par_identifiant(arbre, "rush-gamma")
    lot = _par_identifiant(gamma.enfants, "lot-venu-du-scan")
    # Aucun badge de deduction (`EPIC7-ARB-14`) : le lot porte sa completude
    # ordinaire et rien d'autre.
    assert lot.badge == modele.BADGE_COMPLET
    assert lot.type == modele.TYPE_LOT
    # Le rush absent du manifest porte le signe du manquant, deja defini.
    assert gamma.glyphe == modele.GLYPHE_NON_RATTACHE


# ---------------------------------------------------------------------------
# AC 2 -- frontiere negative : zero tri local dans le modele.
# ---------------------------------------------------------------------------


def test_le_modele_n_appelle_ni_sorted_ni_sort_sur_une_collection_des_sources():
    source = Path(modele.__file__).read_text(encoding="utf-8")
    fautifs = re.findall(r"\bsorted\s*\(|\.sort\s*\(", source)
    assert fautifs == [], f"tri local dans le modele d'arbre : {fautifs}"


def test_la_frontiere_du_tri_mord_vraiment():
    # Symetrique (« un test peut etre vert et vide ») : le motif attrape bien
    # un tri s'il y en avait un.
    motif = r"\bsorted\s*\(|\.sort\s*\("
    assert re.findall(motif, "x = sorted(lots)")
    assert re.findall(motif, "lots.sort()")
    assert re.findall(motif, "lots.sort(key=len)")
    assert not re.findall(motif, "assortiment = 3")


# ---------------------------------------------------------------------------
# AC 2 -- rien d'un etat de session, rien d'un parcours de dossier.
# ---------------------------------------------------------------------------


def test_le_modele_ne_parcourt_aucun_dossier():
    source = Path(modele.__file__).read_text(encoding="utf-8")
    for motif in ("glob(", "iterdir(", "listdir(", "walk(", "rglob("):
        assert motif not in source, f"parcours de dossier dans le modele : {motif}"


def test_un_document_qui_n_est_pas_une_previz_de_scan_est_refuse_nommement():
    manifest = fab.manifest_deux_lots_meme_rush()
    document = fab.document_de_detection(
        lot_id="lot-cadence-24", pages=[], pages_expected=0
    )
    document["kind"] = "extraction"
    with pytest.raises(modele.ChutierError):
        modele.construire_arbre(
            manifest,
            documents_de_detection=[document],
            existe=fab.liaison_factice(["medias/alpha.mov"]),
        )
