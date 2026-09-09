"""Story 5.24 -- le tri par QR, fonction du coeur (AC 1 a 4, 10, 11, 13).

Ce lot ne monte **aucun** projet, n'ecrit aucun pixel et n'appelle pas la CLI :
c'est litteralement l'AC 1, et c'est ce qui rend la partition mesurable a la
seconde. Les fabriques vivent dans `fabriques_vrac.py`, multi-elements par
construction (AC 3).
"""

from __future__ import annotations

import ast
import json
import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(pathlib.Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(pathlib.Path(__file__).parent))

import fabriques_vrac as fab  # noqa: E402

from mixed_media_utility import page_roles, scan_sorting  # noqa: E402

MODULE_DE_TRI = SRC / "mixed_media_utility" / "scan_sorting.py"


def _trie(pages=None):
    return scan_sorting.trier_les_pages(
        fab.vrac_de_reference() if pages is None else pages,
        project_id_courant=fab.PROJET_COURANT,
    )


# ---------------------------------------------------------------------------
# AC 1 -- le tri est une fonction du coeur, jamais un geste de la CLI
# ---------------------------------------------------------------------------


def test_le_tri_s_appelle_sans_projet_sans_disque_et_sans_cli():
    """AC 1 : des payloads en memoire suffisent, et la partition est celle attendue."""
    partition = _trie()
    assert [lot.lot_id for lot in partition.lots] == [
        "lot_alpha_0001", "lot_beta_0002", "lot_gamma_0003"]
    assert len(partition.pages_de_calibration) == 2
    assert len(partition.reliquat) == 2
    assert len(partition.hors_perimetre) == 2


def test_le_module_de_tri_n_importe_ni_cli_ni_argparse_ni_previz():
    """Frontiere negative de l'AC 1, mesuree sur l'**arbre syntaxique** des imports.

    Un module de tri qui importerait la CLI ne serait pas reutilisable par la
    GUI, ce qui est litteralement l'objet de l'arbitrage du 2026-08-17. Le
    balayage porte sur les noms importes et non sur le texte du fichier : une
    docstring qui cite `cli` n'est pas un import, et un import ecrit autrement le
    resterait.
    """
    arbre = ast.parse(MODULE_DE_TRI.read_text(encoding="utf-8"))
    importes: list[str] = []
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            importes.extend(alias.name for alias in noeud.names)
        elif isinstance(noeud, ast.ImportFrom):
            base = noeud.module or ""
            importes.append(base)
            importes.extend(f"{base}.{alias.name}".strip(".")
                            for alias in noeud.names)
    interdits = [
        nom for nom in importes
        if nom.split(".")[-1] in {"cli", "argparse"} or nom.endswith("_previz")
    ]
    assert interdits == [], (
        f"Le module de tri importe {interdits}: il cesserait d'etre exposable "
        "a la GUI.")


def test_le_module_de_tri_n_ecrit_aucune_image_et_ne_touche_pas_au_disque():
    """Frontiere negative de l'AC 4 : rien ne bouge sur le disque (`EPIC5-ARB-108`).

    Balayage des appels du module : aucun `open`, aucun `imwrite`, aucun
    `mkdir`, aucun `shutil`, aucun `os.replace`. Le reliquat est une **liste**,
    et un dossier `reliquat/` n'est cree nulle part.
    """
    arbre = ast.parse(MODULE_DE_TRI.read_text(encoding="utf-8"))
    interdits = {
        "open", "imwrite", "imread", "mkdir", "write_text", "write_bytes",
        "replace_file", "copy", "copy2", "move", "unlink", "rmtree", "makedirs",
    }
    trouves = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Call):
            cible = noeud.func
            nom = (cible.attr if isinstance(cible, ast.Attribute)
                   else getattr(cible, "id", None))
            if nom in interdits:
                trouves.add(nom)
    assert trouves == set(), f"Le module de tri appelle {sorted(trouves)}"
    assert "reliquat/" not in MODULE_DE_TRI.read_text(encoding="utf-8")


def test_zero_occurrence_de_lot_slug_dans_le_module_de_tri():
    """AC 13, et c'est elle qui garde l'AC 1.

    Le tri ne connait pas l'argument qui decide du regime : c'est l'**appelant**
    qui choisit de l'appeler. Sans cette garde, la fonction du coeur redeviendrait
    un geste de CLI, et l'AC 1 serait vraie sur le papier seulement.
    """
    texte = MODULE_DE_TRI.read_text(encoding="utf-8")
    assert "lot_slug" not in texte
    assert "ingest_slug" not in texte.split("class RapportDeTri")[0], (
        "Le tri lui-meme ne connait aucun slug operateur; seul le rapport en "
        "porte un, et c'est une donnee de document.")


# ---------------------------------------------------------------------------
# AC 2 -- une passe accepte un vrac multi-lots et le range
# ---------------------------------------------------------------------------


def test_trois_lots_melanges_rendent_trois_lots_chacun_avec_ses_propres_pages():
    """AC 2, **page par page et jamais par cardinal**.

    Un test qui ne verifierait que « trois lots de deux pages » passerait sous
    une permutation d'appariement -- c'est exactement le mutant `M33`. On
    verifie donc **quelle** page est dans **quel** lot, par son localisateur.
    """
    partition = _trie()
    attendu = {
        "lot_alpha_0001": [
            scan_sorting.Localisateur("vrac.pdf", 3),
            scan_sorting.Localisateur("vrac.pdf", 7),
        ],
        "lot_beta_0002": [
            scan_sorting.Localisateur("vrac.pdf", 4),
            scan_sorting.Localisateur("vrac.pdf", 1),
        ],
        "lot_gamma_0003": [
            scan_sorting.Localisateur("vrac.pdf", 5),
            scan_sorting.Localisateur("vrac.pdf", 0),
        ],
    }
    obtenu = {
        lot.lot_id: [page.locator for page in lot.pages]
        for lot in partition.lots
    }
    assert obtenu == attendu


def test_aucun_lot_ne_recoit_une_page_d_un_autre_lot():
    """Frontiere negative de l'AC 2 : l'appartenance se relit **dans le payload**."""
    partition = _trie()
    for lot in partition.lots:
        for page in lot.pages:
            assert page.payload["lot_id"] == lot.lot_id
            assert page.payload["rush_id"] == lot.rush_id
            assert page.payload["project_id"] == lot.project_id


def test_deux_lots_du_meme_rush_a_deux_cadences_restent_deux_lots():
    """AC 2, risque **R12** dans sa forme d'origine -- le regime ou `M25` avait mord.

    Deux lots du meme rush a deux cadences est le **cas nominal v2.1**. Les
    fusionner ecrirait les cardinaux du scan sur le mauvais lot.
    """
    partition = _trie()
    beta = next(lot for lot in partition.lots if lot.lot_id == "lot_beta_0002")
    gamma = next(lot for lot in partition.lots if lot.lot_id == "lot_gamma_0003")
    assert beta.rush_id == gamma.rush_id == "rush_temoin"
    cadences_beta = {page.payload["timecode_base_fps"] for page in beta.pages}
    cadences_gamma = {page.payload["timecode_base_fps"] for page in gamma.pages}
    assert cadences_beta == {"25/1"}
    assert cadences_gamma == {"24/1"}
    assert beta.identite != gamma.identite


def test_le_lot_vise_n_est_pas_le_premier_arrive_ni_le_premier_rendu():
    """Point 2 de la regle des fabriques, **exerce** et non seulement declare.

    Un `find` fautif qui rendrait toujours le premier element ne se demasque pas
    autrement (`M25`, 257 tests verts).
    """
    vrac = fab.vrac_de_reference()
    premier_arrive = vrac[0].payload["lot_id"]
    partition = _trie(vrac)
    assert premier_arrive == "lot_gamma_0003"
    assert partition.lots[0].lot_id == "lot_alpha_0001"
    vise = next(lot for lot in partition.lots if lot.lot_id == "lot_beta_0002")
    assert partition.lots.index(vise) == 1


# ---------------------------------------------------------------------------
# AC 3 -- l'ordre d'arrivee n'a aucun effet
# ---------------------------------------------------------------------------


def _permutations_du_vrac() -> dict[str, list]:
    """Quatre ordres d'arrivee du **meme** vrac, dont l'ordre inverse (AC 3)."""
    initial = fab.vrac_de_reference()
    inverse = list(reversed(fab.vrac_de_reference()))
    # Un ordre « par paquets » : toutes les pages muettes et etrangeres d'abord.
    par_paquets = sorted(
        fab.vrac_de_reference(),
        key=lambda page: (page.payload is not None, page.locator_source),
    )
    # Un ordre « impairs puis pairs », qui casse toute contiguite de lot.
    brasse = [p for i, p in enumerate(fab.vrac_de_reference()) if i % 2] + [
        p for i, p in enumerate(fab.vrac_de_reference()) if not i % 2]
    return {
        "initial": initial,
        "inverse": inverse,
        "par_paquets": par_paquets,
        "brasse": brasse,
    }


def test_la_partition_est_identique_sous_quatre_permutations_dont_l_inverse():
    """AC 3 : le rangement ne depend jamais de l'ordre d'arrivee."""
    vues = {
        nom: fab.vue_canonique(_trie(vrac))
        for nom, vrac in _permutations_du_vrac().items()
    }
    reference = vues["initial"]
    for nom, vue in vues.items():
        assert vue == reference, f"La permutation {nom!r} range autrement."


def test_le_rang_de_lecture_n_apparie_jamais_une_page_a_un_lot():
    """Frontiere negative de l'AC 3, mesuree en **falsifiant** les rangs.

    Les rangs sont ici en ordre inverse du contenu : un code qui apparierait au
    rang -- ou qui trierait par rang -- rendrait une autre partition. Le role se
    lit dans le payload, l'appartenance se lit dans le payload.
    """
    vrac = fab.vrac_de_reference()
    falsifie = [
        fab.page(
            read_rank=len(vrac) - 1 - index,
            source=page.locator_source,
            page_index_source=page.locator_page_index,
            payload=page.payload,
            refusal_reason=page.refusal_reason,
        )
        for index, page in enumerate(vrac)
    ]
    assert fab.vue_canonique(_trie(falsifie)) == fab.vue_canonique(_trie(vrac))


def test_le_role_de_page_ne_se_deduit_jamais_d_un_rang():
    """Le role vient du payload, pas de la position -- y compris a l'index 0.

    Une page de calibration posee en **derniere** position du vrac reste une page
    de calibration, et une planche posee en premiere position ne devient pas une
    page de calibration parce qu'elle est arrivee la premiere.
    """
    vrac = [
        fab.page(read_rank=0, source="a.tiff",
                 payload=fab.planche(lot_id="lot_alpha_0001", page_index=0)),
        fab.page(read_rank=1, source="b.tiff",
                 payload=fab.planche(lot_id="lot_alpha_0001", page_index=1)),
        fab.page(read_rank=2, source="c.tiff",
                 payload=fab.page_de_calibration(
                     libelle=fab.LIBELLES_DE_CHAINE[1])),
    ]
    partition = _trie(vrac)
    assert [page.locator.source_path
            for page in partition.pages_de_calibration] == ["c.tiff"]
    assert len(partition.lots) == 1
    assert len(partition.lots[0].pages) == 2


# ---------------------------------------------------------------------------
# AC 4 -- deux familles, jamais confondues
# ---------------------------------------------------------------------------


def test_la_partition_est_totale_par_cardinal_et_par_inventaire_nominatif():
    """AC 4, **les deux mesures** : deux pages echangees laisseraient le cardinal juste."""
    vrac = fab.vrac_de_reference()
    partition = _trie(vrac)
    assert partition.cardinal_total == len(vrac)
    inventaire = partition.localisateurs_par_classe()
    tous = [loc for classe in inventaire.values() for loc in classe]
    assert len(tous) == len(vrac)
    assert set(tous) == {
        scan_sorting.Localisateur(page.locator_source, page.locator_page_index)
        for page in vrac
    }


def test_les_quatre_classes_sont_disjointes():
    """AC 4 : toute page est dans **exactement une** classe."""
    inventaire = _trie().localisateurs_par_classe()
    noms = list(inventaire)
    for i, gauche in enumerate(noms):
        for droite in noms[i + 1:]:
            commun = set(inventaire[gauche]) & set(inventaire[droite])
            assert commun == set(), (
                f"{gauche} et {droite} partagent {commun}")


def test_un_vrac_dont_aucune_page_ne_se_rattache_produit_un_reliquat_complet():
    """AC 4 : c'est le cas ou l'operatrice a le plus besoin de voir ce qui a resiste."""
    vrac = [
        fab.page(read_rank=0, source="muette_a.tiff", payload=None),
        fab.page(read_rank=1, source="perimee.tiff", payload=None,
                 refusal_reason="Payload schema version '1.0' is unreadable"),
        fab.page(read_rank=2, source="muette_b.tiff", payload=None),
    ]
    partition = _trie(vrac)
    assert partition.lots == ()
    assert partition.hors_perimetre == ()
    assert len(partition.reliquat) == 3
    assert {entree.motif for entree in partition.reliquat} == {
        scan_sorting.RELIQUAT_QR_MUET,
        scan_sorting.RELIQUAT_PAYLOAD_REFUSE,
    }


def test_le_reliquat_et_le_hors_perimetre_sont_deux_ensembles_et_chaque_page_est_dans_le_bon():
    """AC 4 : deux pages de chaque famille, aux motifs differents."""
    partition = _trie()
    assert {(e.locator.source_path, e.motif) for e in partition.reliquat} == {
        ("page_muette.tiff", scan_sorting.RELIQUAT_QR_MUET),
        ("page_perimee.tiff", scan_sorting.RELIQUAT_PAYLOAD_REFUSE),
    }
    assert {e.locator.source_path for e in partition.hors_perimetre} == {
        "etrangere_a.tiff", "etrangere_b.tiff"}


def test_deux_pages_etrangeres_nomment_deux_projets_differents():
    """AC 4 : le projet a utiliser vient du **QR de la page**, jamais d'une constante.

    Un test a une seule page etrangere passerait sous un code qui affiche une
    constante -- famille de
    `test_la_provenance_porte_l_identifiant_de_la_page_source_et_non_une_constante`.
    """
    partition = _trie()
    nomme = {
        entree.locator.source_path: entree.projet_a_utiliser
        for entree in partition.hors_perimetre
    }
    assert nomme == {
        "etrangere_a.tiff": fab.PROJETS_ETRANGERS[0],
        "etrangere_b.tiff": fab.PROJETS_ETRANGERS[1],
    }
    assert len(set(nomme.values())) == 2


def test_les_deux_familles_ne_partagent_aucun_code_de_motif():
    """Corollaire testable exige par `EPIC5-ARB-105` : intersection vide."""
    assert set(scan_sorting.MOTIFS_DE_RELIQUAT) & set(
        scan_sorting.MOTIFS_HORS_PERIMETRE) == set()
    partition = _trie()
    for entree in partition.reliquat:
        assert entree.motif in scan_sorting.MOTIFS_DE_RELIQUAT
        assert entree.motif not in scan_sorting.MOTIFS_HORS_PERIMETRE
    for entree in partition.hors_perimetre:
        assert entree.motif in scan_sorting.MOTIFS_HORS_PERIMETRE
        assert entree.motif not in scan_sorting.MOTIFS_DE_RELIQUAT


def test_aucune_page_du_reliquat_ou_hors_perimetre_n_est_ecrite_dans_un_lot():
    """Frontiere negative de l'AC 4, verifiee **par les localisateurs**."""
    partition = _trie()
    dans_les_lots = set(partition.localisateurs_par_classe()["lots"])
    ecartees = {e.locator for e in partition.reliquat} | {
        e.locator for e in partition.hors_perimetre}
    assert dans_les_lots & ecartees == set()


def test_une_page_de_calibration_n_est_jamais_classee_hors_perimetre():
    """Frontiere negative de l'AC 4, et elle porte le motif d'`io/payload.py:537-557`.

    Une page de calibration **ne porte aucun `project_id`** et « aucune machine
    n'a le droit de lire celui-la pour decider ». Le controle de projet ne
    s'applique donc qu'aux planches d'images.
    """
    calibration = fab.page_de_calibration(libelle=fab.LIBELLES_DE_CHAINE[0])
    assert "project_id" not in calibration
    vrac = [
        fab.page(read_rank=0, source="etrangere.tiff",
                 payload=fab.planche(lot_id="lot_x_0001", page_index=0,
                                     project_id=fab.PROJETS_ETRANGERS[0])),
        fab.page(read_rank=1, source="calib.tiff", payload=calibration),
    ]
    partition = _trie(vrac)
    assert len(partition.hors_perimetre) == 1
    assert partition.hors_perimetre[0].locator.source_path == "etrangere.tiff"
    assert [p.locator.source_path
            for p in partition.pages_de_calibration] == ["calib.tiff"]
    assert partition.reliquat == ()


def test_le_module_de_tri_ne_lit_pas_project_id_sur_une_page_de_calibration():
    """Frontiere negative de l'AC 4, mesuree sur la **structure** de la fonction.

    La lecture de `project_id` doit etre gardee par le test de role, et non
    l'inverse : le role est teste **avant** dans la chaine de classement, et le
    corps de la branche de calibration ne lit jamais `project_id`.
    """
    arbre = ast.parse(MODULE_DE_TRI.read_text(encoding="utf-8"))
    fonction = next(
        noeud for noeud in ast.walk(arbre)
        if isinstance(noeud, ast.FunctionDef) and noeud.name == "trier_les_pages"
    )
    lignes_role = [
        noeud.lineno for noeud in ast.walk(fonction)
        if isinstance(noeud, ast.Call)
        and getattr(noeud.func, "id", None) == "est_une_page_de_calibration"
    ]
    lignes_projet = [
        noeud.lineno for noeud in ast.walk(fonction)
        if isinstance(noeud, ast.Constant) and noeud.value == "project_id"
    ]
    assert lignes_role, "Le role n'est plus lu du tout dans le tri."
    assert lignes_projet, "Le projet n'est plus lu du tout dans le tri."
    assert min(lignes_role) < min(lignes_projet), (
        "Le controle de projet precede le test de role: une page de "
        "calibration pourrait etre declaree hors perimetre, ce que le retrait "
        "de `project_id` de CALIBRATION_ABSENT_FIELDS existe pour interdire.")


def test_le_tri_n_invente_aucune_identite_a_une_page_de_calibration():
    """AC 5 : le tri ne « repare » jamais une pile en inventant une identite."""
    partition = _trie()
    for page in partition.pages_de_calibration:
        for champ in ("project_id", "rush_id", "lot_id", "fps_target",
                      "timecode_base_fps"):
            assert champ not in page.payload
        assert page.payload["page_role"] == page_roles.PAGE_ROLE_CALIBRATION


def test_apres_le_tri_l_inventaire_du_disque_est_inchange(tmp_path):
    """AC 4 : mesure sur l'**arborescence**, pas sur l'absence d'un appel.

    Le reliquat **et** le hors-perimetre sont non vides, et rien n'a ete cree,
    deplace, copie ou efface -- memes chemins, memes octets.
    """
    (tmp_path / "vrac.pdf").write_bytes(b"pdf-de-synthese")
    (tmp_path / "page_muette.tiff").write_bytes(b"tiff-muet")
    (tmp_path / "etrangere_a.tiff").write_bytes(b"tiff-etranger")
    avant = {
        chemin.relative_to(tmp_path).as_posix(): chemin.read_bytes()
        for chemin in sorted(tmp_path.rglob("*")) if chemin.is_file()
    }
    partition = _trie()
    assert partition.reliquat and partition.hors_perimetre
    apres = {
        chemin.relative_to(tmp_path).as_posix(): chemin.read_bytes()
        for chemin in sorted(tmp_path.rglob("*")) if chemin.is_file()
    }
    assert apres == avant


def test_une_planche_sans_identite_de_lot_complete_va_au_reliquat_et_non_a_un_lot():
    """AC 4 : « lot inconnu du projet courant », et jamais un lot invente."""
    tronquee = dict(fab.planche(lot_id="lot_alpha_0001", page_index=1))
    tronquee.pop("lot_id")
    vrac = [
        fab.page(read_rank=0, source="a.tiff",
                 payload=fab.planche(lot_id="lot_alpha_0001", page_index=0)),
        fab.page(read_rank=1, source="tronquee.tiff", payload=tronquee),
    ]
    partition = _trie(vrac)
    assert [e.motif for e in partition.reliquat] == [
        scan_sorting.RELIQUAT_LOT_INCONNU]
    assert partition.lots[0].pages[0].locator.source_path == "a.tiff"
    assert len(partition.lots[0].pages) == 1


def test_le_tri_refuse_de_travailler_sans_projet_courant():
    """Sans identifiant de projet, le vrac cesserait d'etre borne a un projet."""
    with pytest.raises(scan_sorting.ScanSortingError):
        scan_sorting.trier_les_pages(fab.vrac_de_reference(),
                                     project_id_courant="")


# ---------------------------------------------------------------------------
# AC 7 -- la page de calibration inexploitable quitte sa classe pour le reliquat
# ---------------------------------------------------------------------------


def test_une_page_de_calibration_inexploitable_va_au_reliquat_avec_son_motif():
    """AC 7 : elle ne produit aucun profil et **ne contamine aucun lot**."""
    partition = _trie()
    cible = partition.pages_de_calibration[1]
    assert cible.scan_chain_label == fab.LIBELLES_DE_CHAINE[1]
    apres = scan_sorting.avec_entrees_de_reliquat(partition, [
        scan_sorting.EntreeDeReliquat(
            read_rank=cible.read_rank,
            locator=cible.locator,
            motif=scan_sorting.RELIQUAT_CALIBRATION_INEXPLOITABLE,
            detail="page de calibration monochrome",
        ),
    ])
    assert len(apres.pages_de_calibration) == 1
    assert apres.pages_de_calibration[0].scan_chain_label == (
        fab.LIBELLES_DE_CHAINE[0])
    assert cible.locator in {e.locator for e in apres.reliquat}
    assert apres.cardinal_total == partition.cardinal_total
    assert [lot.identite for lot in apres.lots] == [
        lot.identite for lot in partition.lots]
    # La cible n'est pas en premiere position du reliquat: un versement qui
    # empilerait sans re-trier se verrait ici.
    assert apres.reliquat[0].locator != cible.locator


def test_un_motif_de_reliquat_hors_vocabulaire_est_refuse():
    """Le vocabulaire est ferme: un motif libre est un `skip` muet deguise."""
    partition = _trie()
    with pytest.raises(scan_sorting.ScanSortingError):
        scan_sorting.avec_entrees_de_reliquat(partition, [
            scan_sorting.EntreeDeReliquat(
                read_rank=0,
                locator=scan_sorting.Localisateur("x.tiff", None),
                motif="illisible",
            ),
        ])


# ---------------------------------------------------------------------------
# AC 10 -- le rapport de tri est un document
# ---------------------------------------------------------------------------


def _rapport() -> scan_sorting.RapportDeTri:
    partition = _trie()
    return scan_sorting.RapportDeTri(
        ingest_slug="vrac-2026-08-25",
        project_id=fab.PROJET_COURANT,
        partition=partition,
        profils_crees=(
            scan_sorting.ProfilCree(
                chain_id="chaine-a",
                etiquette=fab.LIBELLES_DE_CHAINE[0],
                chemin_relatif="versions/calibration/hp-envy-4520.json",
                locator=partition.pages_de_calibration[0].locator,
            ),
            scan_sorting.ProfilCree(
                chain_id="chaine-a",
                etiquette=fab.LIBELLES_DE_CHAINE[1],
                chemin_relatif="versions/calibration/epson-v600.json",
                locator=partition.pages_de_calibration[1].locator,
            ),
        ),
    )


def test_le_rapport_fait_l_aller_retour_sans_perte():
    """AC 10 : serialisation puis relecture, sur les quatre classes."""
    rapport = _rapport()
    document = scan_sorting.rapport_to_json_dict(rapport)
    relu = scan_sorting.rapport_from_json_dict(json.loads(json.dumps(document)))
    assert scan_sorting.rapport_to_json_dict(relu) == document


def test_le_rapport_ne_contient_aucun_type_propre_a_la_cli():
    """AC 10 : ni `Namespace`, ni `Path`, ni chemin absolu de la machine."""
    document = scan_sorting.rapport_to_json_dict(_rapport())
    texte = json.dumps(document)
    assert json.loads(texte) == document
    for chemin in [c for c in _chemins(document) if isinstance(c, str)]:
        assert not chemin.startswith("/"), chemin
        assert not chemin[1:3] == ":\\", chemin


def _chemins(document) -> list:
    """Toutes les valeurs de chemin du document, quel que soit leur etage."""
    trouves: list = []
    if isinstance(document, dict):
        for cle, valeur in document.items():
            if cle in {"source_path", "chemin_relatif"}:
                trouves.append(valeur)
            trouves.extend(_chemins(valeur))
    elif isinstance(document, list):
        for element in document:
            trouves.extend(_chemins(element))
    return trouves


def test_les_quatre_classes_s_assertent_dans_le_rapport_pas_seulement_les_lots():
    """AC 10, et c'est `EPIC5-ARB-39` (5.8) : un rapport dont le hors-perimetre
    serait vide alors que la passe en a produit passerait un test qui ne regarde
    que les lots."""
    document = scan_sorting.rapport_to_json_dict(_rapport())
    assert len(document["lots"]) == 3
    assert len(document["calibration"]) == 2
    assert len(document["reliquat"]) == 2
    assert len(document["hors_perimetre"]) == 2
    assert document["page_count"] == 12
    assert [entree["projet_a_utiliser"] for entree in document["hors_perimetre"]] == [
        fab.PROJETS_ETRANGERS[0], fab.PROJETS_ETRANGERS[1]]
    assert [entree["motif"] for entree in document["reliquat"]] == [
        scan_sorting.RELIQUAT_QR_MUET, scan_sorting.RELIQUAT_PAYLOAD_REFUSE]


def test_le_rapport_nomme_chaque_profil_cree_et_les_deux_noms_different():
    """AC 10 : deux profils crees, **deux** noms -- pas un ecrase par l'autre."""
    document = scan_sorting.rapport_to_json_dict(_rapport())
    noms = [profil["chemin_relatif"] for profil in document["profils_crees"]]
    assert len(noms) == 2 and len(set(noms)) == 2
    etiquettes = [profil["etiquette"] for profil in document["profils_crees"]]
    assert etiquettes == list(fab.LIBELLES_DE_CHAINE)


def test_un_rapport_d_une_autre_version_est_refuse():
    """Il n'existe pas de lecteur bi-format, ici comme pour le payload."""
    document = scan_sorting.rapport_to_json_dict(_rapport())
    document["version"] = "tri-0"
    with pytest.raises(scan_sorting.ScanSortingError):
        scan_sorting.rapport_from_json_dict(document)


# ---------------------------------------------------------------------------
# AC 11 -- le tri tient a l'echelle du vrac reel
# ---------------------------------------------------------------------------


class _PayloadObserve(dict):
    """Un payload qui compte **combien de fois on le lit**.

    C'est la seule facon de mesurer la propriete demandee -- « aucune comparaison
    page a page de tous contre tous » -- sans ecrire un budget en secondes, que
    `EPIC5-ARB-100` a du corriger sur 5.23 exactement pour cette raison.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lectures = 0

    def __getitem__(self, cle):
        self.lectures += 1
        return super().__getitem__(cle)

    def get(self, cle, defaut=None):
        self.lectures += 1
        return super().get(cle, defaut)


def _vrac_observe(cardinal: int) -> list:
    """Un vrac de `cardinal` planches, reparties sur **quatre** lots distincts."""
    lots = ("lot_alpha_0001", "lot_beta_0002", "lot_gamma_0003", "lot_delta_0004")
    return [
        fab.page(
            read_rank=rang,
            source="vrac.pdf",
            page_index_source=rang,
            payload=_PayloadObserve(fab.planche(
                lot_id=lots[rang % len(lots)],
                page_index=rang // len(lots),
                page_count=cardinal // len(lots),
            )),
        )
        for rang in range(cardinal)
    ]


def test_le_cout_par_page_ne_croit_pas_avec_la_taille_du_vrac():
    """AC 11 : propriete de **complexite**, jamais de duree.

    Une comparaison de tous contre tous ferait croitre le nombre de lectures
    **par page** avec le cardinal du vrac. On mesure donc les deux : la lecture
    par page est identique a 40 et a 400 pages, et le total croit du meme facteur
    que le cardinal.
    """
    petit = _vrac_observe(40)
    grand = _vrac_observe(400)
    scan_sorting.trier_les_pages(petit, project_id_courant=fab.PROJET_COURANT)
    scan_sorting.trier_les_pages(grand, project_id_courant=fab.PROJET_COURANT)
    lectures_petit = [page.payload.lectures for page in petit]
    lectures_grand = [page.payload.lectures for page in grand]
    assert max(lectures_petit) == max(lectures_grand)
    assert sum(lectures_grand) == 10 * sum(lectures_petit)


def test_un_vrac_de_plusieurs_centaines_de_pages_se_trie_et_reste_disjoint():
    """AC 11 : P4 parle de « plusieurs centaines de pages »."""
    vrac = _vrac_observe(600)
    partition = scan_sorting.trier_les_pages(
        vrac, project_id_courant=fab.PROJET_COURANT)
    assert len(partition.lots) == 4
    assert partition.cardinal_total == 600
    inventaire = partition.localisateurs_par_classe()
    assert len(set(inventaire["lots"])) == 600


# ---------------------------------------------------------------------------
# Campagne de mutation de la revue de vague -- fermeture des survivants
# de classe CRITIQUE (AC 12)
# ---------------------------------------------------------------------------
#
# 437 mutants generes sur ce module, 380 tues, 57 survivants. Classes par la
# politique (section « Priorisation par dangerosite ») : 48 relevent de la
# tolerance documentee (messages d'erreur, casse, libelles), 3 sont des mutants
# EQUIVALENTS prouves tels par mesure, et 6 etaient de classe **critique**
# -- zero survivant tolere. Les deux tests ci-dessous les ferment.


def test_une_page_sans_index_de_planche_precede_toutes_les_pages_indexees():
    """La sentinelle de `_cle_de_page` place les pages sans index EN TETE.

    Survivants fermes : `_cle_de_page__mutmut_2` et `__mutmut_6`, qui
    remplacent la sentinelle `-1` par `+1`. **Classe critique** (ordre
    d'iteration). Mesure de l'effet du mutant, faite avant d'ecrire ce test :
    avec `-1` une page sans index tombe en position 0 face aux index 0, 1, 2 ;
    avec `+1` elle tombe en position **1**, entre les planches 1 et 2. Un vrac
    ou une feuille muette s'intercalerait au milieu des planches d'un lot est
    exactement ce que l'ordre de `_cle_de_page` existe pour empecher.

    Les mutants `__mutmut_3` et `__mutmut_7` (`-1` -> `-2`) sont **equivalents**
    et le restent : les deux sentinelles precedent tout index reel (>= 0) et les
    egalites se resolvent pareil. Mesure, pas suppose. Aucun test ne peut ni ne
    doit les tuer.
    """
    loc = scan_sorting.Localisateur(source_path="vrac.pdf", page_index=0)
    sans_index = scan_sorting._cle_de_page(loc, None)
    for index_reel in (0, 1, 2):
        assert sans_index < scan_sorting._cle_de_page(loc, index_reel), index_reel
    # Le meme, sur la seconde sentinelle de la fonction (l'index DANS LA SOURCE).
    sans_source = scan_sorting.Localisateur(source_path="vrac.pdf", page_index=None)
    assert (scan_sorting._cle_de_page(sans_source, 0)
            < scan_sorting._cle_de_page(loc, 0))


def test_le_rang_de_lecture_est_porte_verbatim_par_les_quatre_classes():
    """`read_rank` traverse le tri sans jamais etre perdu ni recalcule.

    Survivants fermes : les quatre `trier_les_pages__mutmut_*` qui posent
    `read_rank=None` sur une entree. **Classe critique** : `read_rank` et
    `page_index` sont les DEUX adresses d'une page et ne se deduisent jamais
    l'une de l'autre -- perdre la premiere en silence est la famille de defauts
    que ce depot a payee cinq fois. Aucun test du module ne l'assertait : le
    seul qui le faisait vivait au niveau CLI, donc hors du lot de mutation.

    Le test compare les rangs **nominativement**, classe par classe, contre le
    vrac de reference -- jamais par cardinal, qu'un `None` uniforme passerait.
    """
    partition = scan_sorting.trier_les_pages(
        fab.vrac_de_reference(), project_id_courant=fab.PROJET_COURANT)

    rangs_par_source = {
        page.locator_source: page.read_rank for page in fab.vrac_de_reference()
        if page.locator_page_index is None
    }

    # 1. Les pages rangees sous un lot.
    rangs_de_lot = sorted(
        page.read_rank for lot in partition.lots for page in lot.pages)
    assert rangs_de_lot == [0, 1, 3, 5, 7, 11], rangs_de_lot

    # 2. Les pages de calibration.
    assert sorted(p.read_rank for p in partition.pages_de_calibration) == [2, 10]

    # 3. Le reliquat -- et nommement : la feuille muette est au rang 4, la
    #    perimee au rang 8. Un `None` pose sur l'une des deux se verrait.
    reliquat = {e.locator.source_path: e.read_rank for e in partition.reliquat}
    assert reliquat["page_muette.tiff"] == rangs_par_source["page_muette.tiff"] == 4
    assert reliquat["page_perimee.tiff"] == rangs_par_source["page_perimee.tiff"] == 8

    # 4. Le hors-perimetre, nommement lui aussi.
    hors = {p.locator.source_path: p.read_rank for p in partition.hors_perimetre}
    assert hors["etrangere_b.tiff"] == 6
    assert hors["etrangere_a.tiff"] == 9

    # Aucun rang n'est perdu, et l'ensemble est exactement celui du vrac.
    tous = set(rangs_de_lot) | {p.read_rank for p in partition.pages_de_calibration}
    tous |= set(reliquat.values()) | set(hors.values())
    assert tous == set(range(12)), sorted(tous)
    assert None not in tous

    # 5. La TROISIEME famille de reliquat -- `lot-inconnu` -- n'a aucune page
    #    dans le vrac de reference (il n'en porte que deux motifs sur trois),
    #    donc son `read_rank` restait non mesure : le mutant qui le posait a
    #    `None` survivait a tout le lot. Le test qui l'exerce plus haut
    #    n'assertait que le motif. Fixture dediee, cible en SECONDE position.
    tronquee = dict(fab.planche(lot_id="lot_alpha_0001", page_index=1))
    tronquee.pop("lot_id")
    partition_tronquee = scan_sorting.trier_les_pages(
        [
            fab.page(read_rank=0, source="saine.tiff",
                     payload=fab.planche(lot_id="lot_alpha_0001", page_index=0)),
            fab.page(read_rank=1, source="tronquee.tiff", payload=tronquee),
        ],
        project_id_courant=fab.PROJET_COURANT,
    )
    (inconnue,) = partition_tronquee.reliquat
    assert inconnue.motif == scan_sorting.RELIQUAT_LOT_INCONNU
    assert inconnue.read_rank == 1, inconnue
