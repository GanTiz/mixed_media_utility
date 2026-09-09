"""Correctifs de coeur issus du second essai de terrain (2026-08-27).

Trois familles, chacune adossee a un arbitrage de
`decisions-2026-08-27-epic-7-retours-terrain.md` :

* `EPIC7-ARB-88` -- ou `ingest.json` s'ecrit, et la selection multiple comme
  QUATRIEME forme d'entree (un lot, un seul rapport) ;
* `EPIC7-ARB-90` -- le remplacement, sur demande explicite, d'une detection
  deja ecrite pour le meme lot ;
* `EPIC7-ARB-91` -- un nom d'artefact ne repete pas ce que le `lot_id` porte
  deja.

**Regle des fabriques** (CLAUDE.md) : les fabriques de ce module produisent au
moins **deux** elements aux valeurs **distinguables**, et les tests d'ordre
placent leur cible ailleurs qu'en premiere position. Une pile dont toutes les
pages seraient identiques rendrait invisible toute permutation -- c'est le
defaut paye trois fois (5.6/`M33`, 5.7/`M25`, 5.8).
"""

from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import scan_detect, scan_ingest, scan_sorting
from mixed_media_utility.io import naming, project_layout


# --- fabriques -------------------------------------------------------------


def projet(tmp_path: Path) -> Path:
    """Un dossier de projet, son arborescence posee par le COEUR."""
    dossier = tmp_path / "projet"
    dossier.mkdir()
    project_layout.ensure_project_layout(dossier)
    return dossier


def page(chemin: Path, *, valeur: int) -> Path:
    """Une page-image. `valeur` la rend DISTINGUABLE de ses voisines."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    assert cv2.imwrite(str(chemin), np.full((40, 60, 3), valeur, dtype=np.uint8))
    return chemin


def pile(dossier: Path, noms) -> list[Path]:
    """Une pile de pages aux valeurs toutes differentes, dans l'ordre donne.

    Aucun remplissage uniforme : chaque page porte sa propre valeur, si bien
    qu'une permutation se voit a la relecture des octets et pas seulement des
    noms.
    """
    return [
        page(dossier / nom, valeur=(indice + 1) * 30)
        for indice, nom in enumerate(noms)
    ]


# ---------------------------------------------------------------------------
# EPIC7-ARB-88 -- ou `ingest.json` s'ecrit
# ---------------------------------------------------------------------------


def test_le_rapport_s_ecrit_sous_le_dossier_reellement_utilise(tmp_path) -> None:
    """Le defaut exact de l'essai de terrain : `[Errno 2]` a l'ingestion.

    Un fichier deja range dans un dossier de lot sous `scans/` est ingere EN
    PLACE : `scans_dir` vaut alors ce dossier-la et **pas** `scans/<slug>`,
    puisque le slug se derive du nom du fichier. Reconstruire le chemin depuis
    le slug visait donc un dossier inexistant.
    """
    dossier = projet(tmp_path)
    lot = dossier / "scans" / "lot_deja_range"
    pile(lot, ["planche_b.tiff", "planche_a.tiff"])

    rapport = scan_ingest.ingest_scan_lot(
        dossier, lot / "planche_a.tiff", dpi=600)

    # Le slug (nom du fichier) et le dossier employe (le lot) DIVERGENT.
    assert rapport.ingest_slug == "planche_a"
    assert rapport.scans_dir == "scans/lot_deja_range"

    ecrit = scan_ingest.ecrire_le_rapport(dossier, rapport)
    assert ecrit.is_file()
    assert ecrit == lot / scan_ingest.INGEST_DOCUMENT_FILENAME
    # Et surtout : rien n'est ecrit a l'endroit reconstruit depuis le slug.
    assert not (dossier / "scans" / "planche_a").exists()


def test_la_racine_scans_n_est_pas_un_dossier_de_lot(tmp_path) -> None:
    """`scans/` contient les lots, il n'en est pas un.

    Sans cette distinction, une page posee directement dans `<projet>/scans/`
    etait ingeree « en place » avec `scans/` pour dossier de lot, et son
    rapport allait s'ecrire a la racine des lots -- ou le lot suivant l'aurait
    ecrase.
    """
    dossier = projet(tmp_path)
    pile(dossier / "scans", ["libre_b.tiff", "libre_a.tiff"])

    rapport = scan_ingest.ingest_scan_lot(
        dossier, dossier / "scans" / "libre_b.tiff", dpi=600)

    assert rapport.scans_dir == "scans/libre_b"
    ecrit = scan_ingest.ecrire_le_rapport(dossier, rapport)
    assert ecrit == dossier / "scans" / "libre_b" / "ingest.json"
    assert not (dossier / "scans" / "ingest.json").exists()


def test_une_selection_de_fichiers_fait_UN_lot_et_UN_rapport(tmp_path) -> None:
    """Le retour d'Egan, litteralement : « un unique ingest.json pour ce lot »."""
    dossier = projet(tmp_path)
    source = tmp_path / "pile_du_27"
    pile(source, ["page_c.tiff", "page_a.tiff", "page_b.tiff"])

    rapport = scan_ingest.ingest_scan_lot(
        dossier,
        [source / "page_c.tiff", source / "page_a.tiff", source / "page_b.tiff"],
        dpi=600,
    )
    scan_ingest.ecrire_le_rapport(dossier, rapport)

    assert len(rapport.pages) == 3
    # Le slug est celui du DOSSIER, comme si le dossier entier avait ete
    # designe -- pas celui d'un des trois fichiers.
    assert rapport.ingest_slug == "pile_du_27"
    assert len(list(dossier.rglob("ingest.json"))) == 1


def test_l_ordre_d_une_selection_ne_suit_pas_l_ordre_d_arrivee(tmp_path) -> None:
    """Le rang de lecture est deterministe, quel que soit l'ordre du depot.

    La cible n'est **pas** en premiere position dans la selection : un tri
    absent, ou un tri qui rendrait la liste telle quelle, se verrait ici et
    nulle part ailleurs.
    """
    dossier = projet(tmp_path)
    source = tmp_path / "brut"
    pile(source, ["page_a.tiff", "page_b.tiff", "page_c.tiff"])

    rapport = scan_ingest.ingest_scan_lot(
        dossier,
        [source / "page_c.tiff", source / "page_b.tiff", source / "page_a.tiff"],
        dpi=600,
    )

    noms = [Path(p.locator.source_path).name for p in rapport.pages]
    assert noms == ["page_a.tiff", "page_b.tiff", "page_c.tiff"]
    assert [p.read_rank for p in rapport.pages] == [0, 1, 2]


def test_une_selection_d_un_seul_fichier_est_le_cas_du_fichier_seul(tmp_path) -> None:
    """`[x]` et `x` doivent donner le MEME lot, pas deux slugs differents."""
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    a = projet(tmp_path / "a")
    b = projet(tmp_path / "b")
    source_a = page(tmp_path / "a" / "src" / "solo.tiff", valeur=30)
    source_b = page(tmp_path / "b" / "src" / "solo.tiff", valeur=30)

    en_liste = scan_ingest.ingest_scan_lot(a, [source_a], dpi=600)
    nu = scan_ingest.ingest_scan_lot(b, source_b, dpi=600)

    assert en_liste.ingest_slug == nu.ingest_slug == "solo"
    assert en_liste.scans_dir == nu.scans_dir


def test_une_selection_aux_noms_homonymes_est_refusee(tmp_path) -> None:
    """Deux pages homonymes s'ecraseraient : le lot perdrait une page en silence."""
    dossier = projet(tmp_path)
    gauche = page(tmp_path / "gauche" / "planche.tiff", valeur=30)
    droite = page(tmp_path / "droite" / "planche.tiff", valeur=90)

    with pytest.raises(scan_ingest.UnsupportedScanInputError, match="meme nom"):
        scan_ingest.ingest_scan_lot(dossier, [gauche, droite], dpi=600)


def test_une_selection_MELANGE_un_pdf_a_des_images_depuis_ARB_157(
        tmp_path) -> None:
    """Ce banc disait l'inverse jusqu'au 2026-09-01, et il avait raison alors.

    `EPIC7-ARB-88` avait ouvert la selection multiple sur un retour d'Egan qui
    parlait de **TIFF** (« si je glisse plusieurs fichiers TIFF d'un coup »), et
    le coeur la bornait aux images. `EPIC11-ARB-157` la rouvre sur un autre
    retour du meme Egan -- « on doit tout accepter : pdf seul, dans un dossier,
    avec des images ... tout en vrac » -- parce que la borne l'avait bloque :
    il avait coche UN PDF, et le refus tombait sur une selection d'un element.

    Ce que le banc mesure desormais est plus fort que « ca ne leve plus » : le
    lot compte les PAGES des deux natures reunies. Le PDF porte deux pages et
    l'image une, le lot en a **trois** -- un lot qui en rendrait deux
    (les fichiers) serait vert sous « ca ne leve pas » et faux au rapport.

    Le refus que l'arbitrage CONSERVE est mesure juste en dessous : un dossier
    n'entre pas dans une selection.
    """
    dossier = projet(tmp_path)
    image = page(tmp_path / "src" / "planche.tiff", valeur=30)
    pdf = _pdf_de_deux_pages(tmp_path / "src" / "document.pdf")

    rapport = scan_ingest.ingest_scan_lot(dossier, [image, pdf], dpi=600)
    assert len(rapport.pages) == 3
    assert sorted(p.scan_input_format for p in rapport.pages) == [
        "pdf", "pdf", "tiff"]


def test_une_selection_refuse_TOUJOURS_un_dossier(tmp_path) -> None:
    """Le volet que `EPIC11-ARB-157` n'emporte PAS, et il faut le mesurer.

    Un elargissement mal borne aurait fait entrer les dossiers avec les PDF.
    Le refus est le meme qu'avant -- « un dossier s'ingere en designant le
    dossier » -- et il nomme EXACTEMENT ce qu'il refuse, sans emporter le PDF
    ni l'image qui l'accompagnent.
    """
    dossier = projet(tmp_path)
    image = page(tmp_path / "src" / "planche.tiff", valeur=30)
    pdf = _pdf_de_deux_pages(tmp_path / "src" / "document.pdf")
    intrus = tmp_path / "src" / "un_dossier"
    intrus.mkdir(parents=True, exist_ok=True)

    with pytest.raises(scan_ingest.UnsupportedScanInputError,
                       match="que des pages") as capture:
        scan_ingest.ingest_scan_lot(dossier, [image, intrus, pdf], dpi=600)
    motif = str(capture.value)
    assert "un_dossier" in motif
    assert "planche.tiff" not in motif and "document.pdf" not in motif


def _pdf_de_deux_pages(chemin: Path) -> Path:
    """Un PDF REEL de deux pages -- un faux PDF compterait pour une page.

    Le cardinal d'une selection melangee se lit en OUVRANT le document
    (`scan_ingest._cardinal_des_pages`), et sa branche de secours compte un
    illisible pour une page : un `%PDF-1.4` nu rendrait donc `2` au lieu de `3`
    et ferait passer le banc pour la mauvaise raison.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as pdfcanvas

    chemin.parent.mkdir(parents=True, exist_ok=True)
    canevas = pdfcanvas.Canvas(str(chemin), pagesize=A4)
    for _ in range(2):
        canevas.showPage()
    canevas.save()
    return chemin


def test_une_selection_vide_est_refusee(tmp_path) -> None:
    with pytest.raises(scan_ingest.EmptyScanLotError):
        scan_ingest.ingest_scan_lot(projet(tmp_path), [], dpi=600)


def test_un_chemin_absent_de_la_selection_est_nomme(tmp_path) -> None:
    """Le chemin manquant se dit AVANT toute copie, pas comme une page absente."""
    dossier = projet(tmp_path)
    present = page(tmp_path / "src" / "planche_a.tiff", valeur=30)
    absent = tmp_path / "src" / "planche_b.tiff"

    with pytest.raises(scan_ingest.UnsupportedScanInputError) as capture:
        scan_ingest.ingest_scan_lot(dossier, [present, absent], dpi=600)
    assert "planche_b.tiff" in str(capture.value)


def test_une_chaine_reste_un_chemin_et_non_une_suite_de_caracteres(tmp_path) -> None:
    """`str` est iterable : sans garde, un chemin devenait une selection de lettres."""
    dossier = projet(tmp_path)
    source = page(tmp_path / "src" / "planche.tiff", valeur=30)

    rapport = scan_ingest.ingest_scan_lot(dossier, str(source), dpi=600)
    assert rapport.ingest_slug == "planche"


# ---------------------------------------------------------------------------
# EPIC7-ARB-90 -- remplacer une detection existante, sur demande
# ---------------------------------------------------------------------------


def _lot(dossier: Path, slug: str) -> Path:
    """Le dossier de lot `<projet>/scans/<slug>/`, tel que le coeur le compose.

    Les helpers de detection prennent desormais un DOSSIER et non un slug
    (`EPIC7-ARB-88`) : ces bancs fabriquent donc le dossier ici, une fois.
    """
    return project_layout.scan_lot_dir(dossier, slug)


def _poser_des_detections(dossier: Path, slug: str, noms) -> list[Path]:
    """Deposer des documents de detection factices, aux contenus distinguables."""
    detections = scan_detect.dossier_des_detections(_lot(dossier, slug))
    detections.mkdir(parents=True, exist_ok=True)
    poses = []
    for indice, nom in enumerate(noms):
        chemin = detections / nom
        chemin.write_text(f'{{"rang": {indice}}}', encoding="utf-8")
        poses.append(chemin)
    return poses


def test_les_detections_existantes_se_lisent_dans_un_ordre_deterministe(
    tmp_path,
) -> None:
    dossier = projet(tmp_path)
    _poser_des_detections(
        dossier, "lot_vise",
        ["detect-20260827T120000Z.json", "detect-20260826T080000Z.json"],
    )
    # Un second lot existe, et il n'est PAS le premier dans l'ordre du disque :
    # une lecture qui rendrait « le premier dossier venu » se verrait ici.
    _poser_des_detections(dossier, "autre_lot", ["detect-20260825T080000Z.json"])

    trouves = scan_detect.documents_de_detection_existants(_lot(dossier, "lot_vise"))

    assert [c.name for c in trouves] == [
        "detect-20260826T080000Z.json",
        "detect-20260827T120000Z.json",
    ]


def test_un_lot_sans_detection_ne_rend_rien(tmp_path) -> None:
    dossier = projet(tmp_path)
    _poser_des_detections(dossier, "un_autre", ["detect-20260826T080000Z.json"])
    assert scan_detect.documents_de_detection_existants(_lot(dossier, "vierge")) == ()


def test_le_remplacement_ne_touche_que_le_lot_vise(tmp_path) -> None:
    """L'effacement porte sur UN lot. Le lot vise n'est pas le premier du dossier."""
    dossier = projet(tmp_path)
    _poser_des_detections(
        dossier, "aaa_premier_lot", ["detect-20260826T080000Z.json"])
    vises = _poser_des_detections(
        dossier, "zzz_lot_vise",
        ["detect-20260826T090000Z.json", "detect-20260827T100000Z.json"],
    )

    retires = scan_detect._effacer_les_detections_existantes(
        _lot(dossier, "zzz_lot_vise"), logging.getLogger(__name__))

    assert retires == 2
    assert all(not chemin.exists() for chemin in vises)
    assert scan_detect.documents_de_detection_existants(
        _lot(dossier, "aaa_premier_lot"))


def test_sans_demande_explicite_rien_n_est_efface(tmp_path) -> None:
    """Le defaut du parametre est le comportement d'avant, sans exception."""
    import inspect

    signature = inspect.signature(scan_detect.run_scan_detect)
    assert signature.parameters["remplacer_les_detections"].default is False


# ---------------------------------------------------------------------------
# EPIC7-ARB-91 -- le nom ne repete pas ce que le lot porte deja
# ---------------------------------------------------------------------------


def test_le_pdf_de_planches_ne_repete_plus_le_rush() -> None:
    """Le cas exact d'Egan, avec ses identifiants reels."""
    lot_id = naming.build_lot_id("planche_4f_heteroclite", 4)
    assert lot_id == "planche_4f_heteroclite_4"

    # `EPIC11-ARB-171` a remplace le mot `planches` par la mise en page ; le
    # `rush_id` n'y est toujours pas, et c'est ce que ce test mesure.
    nom = naming.build_sheets_pdf_filename(
        "projet_demo", "planche_4f_heteroclite", lot_id,
        template_id="tpl-a4-portrait-4f-v2")

    assert nom == "projet_demo_planche_4f_heteroclite_4_4f-por.pdf"
    assert nom.count("planche_4f_heteroclite") == 1


def test_le_nom_de_frame_ne_repete_ni_le_rush_ni_la_cadence() -> None:
    lot_id = naming.build_lot_id("TEST_FILE", 12.5)
    assert lot_id == "TEST_FILE_12p5"

    nom = naming.build_frame_filename(
        project_id="projet_demo",
        rush_id="TEST_FILE",
        lot_id=lot_id,
        page_index=0,
        frame_timecode="00:00:00:00",
        fps_target=12.5,
        slot_index=1,
    )

    assert nom == "projet_demo_TEST_FILE_12p5_p001_s01_tc00-00-00-00.png"
    assert nom.count("TEST_FILE") == 1
    assert nom.count("12p5") == 1


@pytest.mark.parametrize(
    "rush_id, cadence",
    [("TEST_FILE", 12.5), ("rush-001", 24), ("planche_4f_heteroclite", 4)],
)
def test_le_lot_reste_lisible_du_nom_donc_le_rush_et_la_cadence_aussi(
    rush_id, cadence
) -> None:
    """Le contrat de reconstruction de 2.3 tient : rien n'est devenu illisible.

    Trois lots DISTINCTS, dont deux au meme motif de nom et un a la cadence
    fractionnaire : une convention qui ne marcherait que sur le cas entier se
    verrait ici.
    """
    lot_id = naming.build_lot_id(rush_id, cadence)

    nom = naming.build_frame_filename(
        project_id="projet_demo",
        rush_id=rush_id,
        lot_id=lot_id,
        page_index=2,
        frame_timecode="00:00:04:03",
        fps_target=cadence,
    )

    assert f"_{lot_id}_" in nom
    # Et le lot porte lui-meme le rush et la cadence, par construction.
    assert lot_id == f"{rush_id}_{naming.format_fps_short(cadence)}"


def test_les_noms_sans_lot_id_restent_strictement_inchanges() -> None:
    """Les deux conventions qui ne portaient AUCUNE repetition ne bougent pas.

    Elles sont le seul support d'identite de fichiers qui voyagent seuls
    (5.6, AC 1) : les toucher au passage aurait casse la reconstruction depuis
    le seul payload QR.
    """
    assert (
        naming.build_extracted_frame_filename("TEST_FILE", 12.5, "00:00:00:00")
        == "TEST_FILE_12p5_00-00-00-00.tiff"
    )
    assert (
        naming.build_scan_frame_filename("TEST_FILE", 12.5, "00:00:00:00")
        == "scan_TEST_FILE_12p5_00-00-00-00.tiff"
    )


# ---------------------------------------------------------------------------
# EPIC7-ARB-88 -- les trois artefacts d'une passe vivent dans UN dossier
#
# Le correctif d'origine n'avait deplace qu'`ingest.json` ; `tri.json` et
# `detections/` continuaient d'etre recomposes depuis `report.ingest_slug`.
# Sur une ingestion EN PLACE -- un fichier deja range sous
# `<projet>/scans/<lot>/`, qui est le cas nominal des essais de terrain -- le
# slug vaut le nom du FICHIER : la passe eparpillait donc ses documents dans
# deux dossiers, dont un dossier de lot fantome, sans images ni rapport.
# ---------------------------------------------------------------------------


def _lot_ingere_en_place(tmp_path: Path) -> tuple[Path, Path, object]:
    """Ingerer un fichier deja range sous `<projet>/scans/<lot>/`.

    Rend `(projet, dossier de lot, rapport)`. Le dossier porte **deux** pages
    aux valeurs distinctes et c'est la **seconde** qui est visee : une
    derivation qui rendrait « la premiere page venue » se verrait ici, et le
    slug retenu (`planche_02`) diverge alors du nom du dossier -- c'est
    exactement le regime ou les artefacts se dispersaient.
    """
    dossier = projet(tmp_path)
    lot_dir = project_layout.scan_lot_dir(dossier, "rush_du_terrain")
    pages = pile(lot_dir, ["planche_01.tiff", "planche_02.tiff"])
    rapport = scan_ingest.ingest_scan_lot(dossier, str(pages[1]), dpi=600)
    assert rapport.ingest_slug == "planche_02"
    return dossier, lot_dir, rapport


def test_les_trois_artefacts_d_une_passe_partagent_le_dossier_du_lot(
    tmp_path,
) -> None:
    dossier, lot_dir, rapport = _lot_ingere_en_place(tmp_path)

    # Les trois artefacts sont ECRITS pour de vrai, chacun par la fonction du
    # coeur qui en a la charge, et c'est l'endroit ou ils atterrissent qui est
    # mesure. Comparer des chemins composes ici serait tautologique -- une
    # assertion du genre `(X / "tri.json").parent == X` est vraie de toute
    # facon, et ne dirait rien de ce que le coeur compose de son cote.
    ingest = scan_ingest.ecrire_le_rapport(dossier, rapport)

    tri = scan_detect.ecrire_le_rapport_de_tri(
        dossier, rapport, logging.getLogger(__name__),
        scan_sorting.PartitionDeVrac(), (), "proj-demo")

    detection = scan_detect._chemin_unique_de_document(
        scan_ingest.dossier_de_lot(dossier, rapport), "2026-08-27T10:00:00Z")

    assert ingest.is_file() and tri.is_file() and detection.is_file()
    assert ingest.parent == lot_dir
    assert tri.parent == lot_dir
    assert detection.parent.parent == lot_dir
    assert detection.parent.name == scan_detect.DETECTIONS_DIRNAME


def test_le_dossier_recompose_depuis_le_slug_est_bien_un_autre_dossier(
    tmp_path,
) -> None:
    """Volet symetrique : sans lui, le test precedent pourrait etre vert en ne
    mesurant rien -- il ne prouverait que `parent` rend un parent."""
    dossier, lot_dir, rapport = _lot_ingere_en_place(tmp_path)

    fantome = project_layout.scan_lot_dir(dossier, rapport.ingest_slug)

    assert fantome != lot_dir
    assert not fantome.exists(), (
        "le dossier recompose depuis le slug ne porte NI images NI rapport : "
        "c'est la ou les detections partaient avant le correctif"
    )
    assert sorted(p.name for p in lot_dir.glob("*.tiff")) == [
        "planche_01.tiff", "planche_02.tiff"]


def test_le_dossier_de_lot_par_defaut_designe_le_lot_reel_avant_ingestion(
    tmp_path,
) -> None:
    """Ce que l'atelier interroge AVANT de lancer, pour poser sa question.

    Sans cette derivation, la GUI cherchait les detections existantes sous
    `scans/<slug>/`, n'en trouvait aucune, ne posait donc aucune question -- et
    l'ecrasement silencieux qu'`EPIC7-ARB-90` interdit avait lieu.
    """
    dossier = projet(tmp_path)
    lot_dir = project_layout.scan_lot_dir(dossier, "rush_du_terrain")
    pages = pile(lot_dir, ["planche_01.tiff", "planche_02.tiff"])

    for vise in (lot_dir, pages[0], pages[1], tuple(pages)):
        assert scan_ingest.dossier_de_lot_par_defaut(dossier, vise) == lot_dir

    # Et il rend le dossier que l'ingestion CREERA quand la source est
    # exterieure au projet : la question se pose alors au bon endroit aussi.
    externe = page(tmp_path / "ailleurs" / "planche_09.tiff", valeur=77)
    attendu = project_layout.scan_lot_dir(
        dossier, scan_ingest.slug_par_defaut(dossier, str(externe)))
    assert scan_ingest.dossier_de_lot_par_defaut(dossier, str(externe)) == attendu


def test_une_selection_multiple_traverse_run_scan_detect_sans_coercition(
    tmp_path,
) -> None:
    """Regression F1 : `scan_path = Path(scan_path)` en tete de `run_scan_detect`
    detruisait la quatrieme forme d'entree -- `TypeError: ... not 'tuple'`,
    donc la selection multiple de la zone tampon ne pouvait PAS aboutir.

    La mesure est prise **sur le disque** et de bout en bout, pas sur la
    signature : les pages synthetiques ne portent aucun QR, la passe s'arrete
    donc proprement sur son motif, mais l'ingestion, elle, a bien eu lieu.
    """
    dossier = projet(tmp_path)
    sources = pile(tmp_path / "carte_sd", ["a.tiff", "b.tiff", "c.tiff"])

    issue = scan_detect.run_scan_detect(
        dossier, tuple(str(p) for p in sources), dpi=600)

    assert issue.motif_d_arret in scan_detect.MOTIFS_D_ARRET
    assert issue.rapport_d_ingestion.is_file()
    assert len(issue.report.pages) == 3, (
        "les trois fichiers deposes font UN lot de trois pages")
    lot_dir = scan_ingest.dossier_de_lot(dossier, issue.report)
    assert issue.rapport_d_ingestion.parent == lot_dir
    assert sorted(p.name for p in lot_dir.glob("*.tiff")) == ["a.tiff", "b.tiff", "c.tiff"]


# ---------------------------------------------------------------------------
# EPIC7-ARB-90 de bout en bout : le remplacement porte sur le lot REEL
#
# L'AC prescrit une mesure sur le DISQUE, a travers `run_scan_detect` ; seules
# les briques etaient mesurees. Le regime critique est celui ou les deux
# defauts se composent : ingestion EN PLACE (slug != dossier) et remplacement
# demande. L'effacement visait alors le dossier fantome, n'y trouvait rien, et
# l'ancienne detection survivait a un « Oui » explicite.
# ---------------------------------------------------------------------------


def test_le_remplacement_demande_efface_la_detection_du_lot_reel(tmp_path) -> None:
    dossier, lot_dir, _ = _lot_ingere_en_place(tmp_path)
    poses = _poser_des_detections(
        dossier, "rush_du_terrain",
        ["detect-20260826T080000Z.json", "detect-20260827T090000Z.json"])
    assert all(chemin.is_file() for chemin in poses)
    vise = lot_dir / "planche_02.tiff"

    issue = scan_detect.run_scan_detect(
        dossier, str(vise), dpi=600, remplacer_les_detections=True)

    assert issue.motif_d_arret in scan_detect.MOTIFS_D_ARRET
    assert scan_detect.documents_de_detection_existants(lot_dir) == (), (
        "un « Oui » explicite doit emporter les detections du lot REEL")
    assert all(not chemin.exists() for chemin in poses)


def test_sans_demande_la_detection_du_lot_reel_survit_a_une_passe(tmp_path) -> None:
    """Volet symetrique, et c'est l'invariant de 5.25 : jamais d'ecrasement
    SILENCIEUX. Sans lui, le test precedent serait vert sur un code qui
    efface toujours -- ce qui serait le defaut exactement inverse."""
    dossier, lot_dir, _ = _lot_ingere_en_place(tmp_path)
    poses = _poser_des_detections(
        dossier, "rush_du_terrain",
        ["detect-20260826T080000Z.json", "detect-20260827T090000Z.json"])
    vise = lot_dir / "planche_02.tiff"

    scan_detect.run_scan_detect(dossier, str(vise), dpi=600)

    assert scan_detect.documents_de_detection_existants(lot_dir) == tuple(poses)


# ---------------------------------------------------------------------------
# Revue couche 1 -- la CASSE des noms de fichier
#
# Deux gardes du coeur comparaient des noms tels quels, ce qui suppose un
# systeme de fichiers sensible a la casse. Sur NTFS et sur APFS -- les deux
# ou ce projet tourne -- elles ne mordaient donc pas la ou elles servent.
# ---------------------------------------------------------------------------


def test_deux_homonymes_a_la_casse_pres_sont_refuses_dans_une_selection(
    tmp_path,
) -> None:
    """Le faux succes R12, mesure : aucun refus, une page perdue, un cardinal
    juste au rapport. Les valeurs des deux pages DIFFERENT, sans quoi
    l'ecrasement serait invisible."""
    dossier = projet(tmp_path)
    gauche = page(tmp_path / "gauche" / "Planche.tiff", valeur=30)
    droite = page(tmp_path / "droite" / "planche.tiff", valeur=200)

    with pytest.raises(scan_ingest.ScanIngestError) as refus:
        scan_ingest.ingest_scan_lot(
            dossier, (str(gauche), str(droite)), dpi=600)

    # Le message nomme les fichiers TELS QUE l'operatrice les voit.
    assert "Planche.tiff" in str(refus.value)
    assert "planche.tiff" in str(refus.value)


def test_deux_noms_reellement_distincts_ne_sont_pas_refuses(tmp_path) -> None:
    """Volet symetrique : sans lui, un refus systematique passerait le test
    precedent et rendrait la selection multiple inutilisable."""
    dossier = projet(tmp_path)
    gauche = page(tmp_path / "gauche" / "planche_01.tiff", valeur=30)
    droite = page(tmp_path / "droite" / "planche_02.tiff", valeur=200)

    rapport = scan_ingest.ingest_scan_lot(
        dossier, (str(gauche), str(droite)), dpi=600)

    assert len(rapport.pages) == 2


def test_la_garde_anti_ecrasement_mord_aussi_a_la_casse_pres(tmp_path) -> None:
    """La copie fait foi et peut etre la seule trace restante du scan.

    Mesure du defaut : le lot portait `Planche.tiff` (valeur 30), l'ingestion
    de `planche.tiff` (valeur 200) sous le meme slug passait sans un mot, et
    le fichier du lot changeait de contenu. Le cas strictement homonyme, lui,
    refusait bien -- c'etait donc la casse et rien d'autre.
    """
    dossier = projet(tmp_path)
    lot_dir = project_layout.scan_lot_dir(dossier, "mon_lot")
    deja = page(lot_dir / "Planche.tiff", valeur=30)
    source = page(tmp_path / "usb" / "planche.tiff", valeur=200)

    with pytest.raises(scan_ingest.ScanIngestError):
        scan_ingest.ingest_scan_lot(
            dossier, str(source), dpi=600, ingest_slug="mon_lot")

    assert int(cv2.imread(str(deja))[0, 0, 0]) == 30, (
        "le fichier deja materialise n'a PAS ete touche")


def test_re_ingerer_le_meme_scan_a_une_autre_casse_reste_idempotent(
    tmp_path,
) -> None:
    """Volet symetrique : la garde ne mord que sur un contenu DIFFERENT.

    Un operateur qui relance apres une coupure ne doit pas avoir a inventer un
    nouveau slug -- et il ne doit pas non plus etre puni parce que sa cle USB
    a rendu le nom dans une autre casse.
    """
    dossier = projet(tmp_path)
    lot_dir = project_layout.scan_lot_dir(dossier, "mon_lot")
    page(lot_dir / "Planche.tiff", valeur=30)
    source = page(tmp_path / "usb" / "planche.tiff", valeur=30)

    rapport = scan_ingest.ingest_scan_lot(
        dossier, str(source), dpi=600, ingest_slug="mon_lot")

    assert len(rapport.pages) == 1


# ---------------------------------------------------------------------------
# Revue couche 1 -- une copie sautee ne disparait pas du rapport
#
# Le correctif C1/C2 avait ete pose sans mesure qui le tienne : la couche 1 a
# reinjecte le defaut et la suite est restee verte. Le voici mesure.
# ---------------------------------------------------------------------------


def test_une_copie_impossible_devient_un_saut_declare_et_non_une_page_perdue(
    tmp_path, monkeypatch
) -> None:
    """Une page que la copie ne peut pas ecrire sort par `skipped_files`.

    Avant correctif, `_materialise_selection` rendait la liste des
    destinations effectivement copiees : une copie sautee disparaissait donc
    du lot ET du rapport, sans `skipped_files` ni avertissement -- trois
    fichiers deposes, une page au rapport, zero saut. La cible est la
    DEUXIEME des trois : un code qui sauterait toujours la premiere passerait
    un test dont la cible est premiere.
    """
    dossier = projet(tmp_path)
    sources = pile(tmp_path / "carte_sd", ["a.tiff", "b.tiff", "c.tiff"])
    vraie_copie = shutil.copy2

    def copie_qui_echoue_sur_b(source, destination, *args, **kwargs):
        if Path(source).name == "b.tiff":
            raise OSError("support en lecture seule")
        return vraie_copie(source, destination, *args, **kwargs)

    monkeypatch.setattr(scan_ingest.shutil, "copy2", copie_qui_echoue_sur_b)

    rapport = scan_ingest.ingest_scan_lot(
        dossier, tuple(str(p) for p in sources), dpi=600)

    assert len(rapport.pages) == 2, "les deux pages copiees, et elles seules"
    assert [Path(s).name for s in rapport.skipped_files] == ["b.tiff"]
    assert "UNREADABLE_FILE_SKIPPED" in rapport.warnings


# ---------------------------------------------------------------------------
# Les trois branches neuves d'`EPIC7-ARB-88` que la revue a trouvees sans
# mesure : le parent retenu quand la selection s'etale, l'exception de la
# racine `scans/`, et la garde qui distingue « deja range » de « range dans
# scans/ ». Chacune tenait par un mutant survivant.
# ---------------------------------------------------------------------------


def test_le_slug_d_une_selection_etalee_vient_du_PREMIER_EN_ORDRE_DE_LECTURE(
    tmp_path,
) -> None:
    """Sans parent commun, c'est l'ordre de LECTURE qui tranche, jamais celui
    d'arrivee des chemins.

    Les deux sont delibérement opposes ici : le fichier depose en premier
    (`z_ailleurs/b.tiff`) n'est PAS le premier en ordre de lecture
    (`a_ici/a.tiff`). Un code qui retiendrait « le premier parent venu » --
    d'un ensemble, donc sans ordre -- ou « le parent du premier chemin
    depose » donnerait l'autre reponse.
    """
    dossier = projet(tmp_path)
    tardif = page(tmp_path / "z_ailleurs" / "b.tiff", valeur=200)
    premier = page(tmp_path / "a_ici" / "a.tiff", valeur=30)

    slug = scan_ingest.slug_par_defaut(dossier, (str(tardif), str(premier)))

    assert slug == "a_ici"


def test_une_selection_prise_a_la_racine_scans_prend_le_nom_du_premier_fichier(
    tmp_path,
) -> None:
    """Le parent commun vaut `scans/` : son nom donnerait un lot `scans/scans/`.

    Un dossier au nom de son propre parent ne dit rien de ce qu'il contient.
    On retient donc le nom du premier fichier -- exactement ce qu'une image
    seule aurait donne. La cible n'est pas la premiere DEPOSEE : les deux
    ordres sont opposes, comme au test precedent.
    """
    dossier = projet(tmp_path)
    scans = dossier / project_layout.SCANS_DIRNAME
    tardif = page(scans / "b_planche.tiff", valeur=200)
    premier = page(scans / "a_planche.tiff", valeur=30)

    slug = scan_ingest.slug_par_defaut(dossier, (str(tardif), str(premier)))

    assert slug == "a_planche"


def test_une_selection_prise_a_la_racine_scans_est_MATERIALISEE_dans_un_lot(
    tmp_path,
) -> None:
    """La racine `scans/` n'est PAS un dossier de lot : on n'ingere pas en place.

    Defaut que la garde previent : `_is_inside` seul rend vrai pour la racine
    comme pour ses descendants. Les pages seraient alors restees a plat sous
    `scans/`, sans aucun dossier de lot -- et `ingest.json` se serait ecrit a
    la racine des scans, a cote de tous les autres lots du projet.
    """
    dossier = projet(tmp_path)
    scans = dossier / project_layout.SCANS_DIRNAME
    premiere = page(scans / "a_planche.tiff", valeur=30)
    seconde = page(scans / "b_planche.tiff", valeur=200)

    rapport = scan_ingest.ingest_scan_lot(
        dossier, (str(premiere), str(seconde)), dpi=600)

    lot_dir = scan_ingest.dossier_de_lot(dossier, rapport)
    assert lot_dir != scans, "le lot n'est PAS la racine des scans"
    assert lot_dir.parent == scans
    assert sorted(p.name for p in lot_dir.glob("*.tiff")) == [
        "a_planche.tiff", "b_planche.tiff"]
    assert scan_ingest.chemin_du_rapport(dossier, rapport).parent == lot_dir


def test_une_selection_deja_dans_un_lot_est_ingeree_EN_PLACE(tmp_path) -> None:
    """Volet symetrique du precedent : la garde ne doit pas tout materialiser.

    Sans lui, une implementation qui refuserait toujours l'ingestion en place
    passerait le test ci-dessus tout en recopiant les octets d'un lot deja
    range -- ce qui est l'inverse du besoin.

    Un `ingest_slug` EXPLICITE, different du nom du dossier, est ce qui rend
    les deux comportements distinguables : sans lui, le slug par defaut vaut
    le nom du dossier, les deux chemins convergent sur le meme dossier de lot
    et le test ne mesure plus rien (mutant survivant, revue du 2026-08-27).
    """
    dossier = projet(tmp_path)
    lot_dir = project_layout.scan_lot_dir(dossier, "rush_du_terrain")
    pages = pile(lot_dir, ["planche_01.tiff", "planche_02.tiff"])

    rapport = scan_ingest.ingest_scan_lot(
        dossier, tuple(str(p) for p in pages), dpi=600,
        ingest_slug="un_autre_nom")

    assert scan_ingest.dossier_de_lot(dossier, rapport) == lot_dir, (
        "la selection etait DEJA rangee : aucun octet ne bouge, meme si le "
        "slug promis par l'appelant porte un autre nom")
    assert sorted(p.name for p in lot_dir.glob("*.tiff")) == [
        "planche_01.tiff", "planche_02.tiff"]
    ailleurs = project_layout.scan_lot_dir(dossier, "un_autre_nom")
    assert not ailleurs.exists(), (
        f"des octets ont ete recopies dans {ailleurs}")


def test_une_ingestion_qui_echoue_laisse_la_detection_existante_INTACTE(
    tmp_path,
) -> None:
    """L'effacement a lieu APRES l'ingestion, jamais avant (`EPIC7-ARB-90`).

    L'arbitrage l'ecrit noir sur blanc : « une detection qui echoue a
    l'ingestion ne doit pas laisser le lot sans aucune detection ». Aucun test
    ne le tenait -- deplacer l'effacement avant l'ingestion laissait la suite
    verte (mutant N10, revue du 2026-08-27).

    Le regime : lot deja detecte, « Oui » explicite, puis une ingestion qui
    refuse. Le refus choisi est celui des homonymes a la casse pres, parce
    qu'il tombe AVANT toute ecriture -- c'est le pire cas pour l'invariant,
    celui ou rien n'aura remplace ce qu'on aurait efface.
    """
    dossier = projet(tmp_path)
    lot_dir = project_layout.scan_lot_dir(dossier, "rush_du_terrain")
    pile(lot_dir, ["planche_01.tiff", "planche_02.tiff"])
    poses = _poser_des_detections(
        dossier, "rush_du_terrain",
        ["detect-20260826T080000Z.json", "detect-20260827T090000Z.json"])
    gauche = page(tmp_path / "gauche" / "Planche.tiff", valeur=30)
    droite = page(tmp_path / "droite" / "planche.tiff", valeur=200)

    with pytest.raises(scan_ingest.ScanIngestError):
        scan_detect.run_scan_detect(
            dossier, (str(gauche), str(droite)), dpi=600,
            ingest_slug="rush_du_terrain", remplacer_les_detections=True)

    assert scan_detect.documents_de_detection_existants(lot_dir) == tuple(poses), (
        "l'ancienne detection doit survivre a une ingestion qui echoue")


def test_une_selection_dont_un_fichier_est_DEJA_dans_le_lot_ne_perd_rien(
    tmp_path,
) -> None:
    """Une selection etalee sur deux dossiers dont l'un EST le lot vise.

    `shutil.copy2(x, x)` leve alors -- `SameFileError` ailleurs,
    `PermissionError` sous Windows, toutes deux des `OSError`. La garde
    `entry.resolve() == destination.resolve()` existe pour cela, et rien ne la
    mesurait (mutant N5). Sans elle, la page deja rangee etait perdue **en
    silence** : elle serait sortie ni en page, ni en `skipped_files`.

    La page deja en place est la SECONDE en ordre de lecture, pas la premiere.
    """
    dossier = projet(tmp_path)
    lot_dir = project_layout.scan_lot_dir(dossier, "rush_du_terrain")
    deja = page(lot_dir / "b_planche.tiff", valeur=200)
    dehors = page(tmp_path / "usb" / "a_planche.tiff", valeur=30)

    rapport = scan_ingest.ingest_scan_lot(
        dossier, (str(dehors), str(deja)), dpi=600,
        ingest_slug="rush_du_terrain")

    assert len(rapport.pages) == 2, (
        "la page deja rangee compte comme les autres")
    assert rapport.skipped_files == ()
    assert sorted(p.name for p in lot_dir.glob("*.tiff")) == [
        "a_planche.tiff", "b_planche.tiff"]
    assert int(cv2.imread(str(deja))[0, 0, 0]) == 200, (
        "la page deja en place n'a pas ete ecrasee par elle-meme")
