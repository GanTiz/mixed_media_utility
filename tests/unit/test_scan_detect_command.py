"""Story 5.25: `scan detect` -- la detection seule, persistee hors manifeste.

Ce que cette suite mesure, et que rien d'autre ne mesurait avant elle: le
point de jugement central du produit (regarder ce que la detection a trouve
avant d'ecrire un seul TIFF) existe desormais, et son resultat survit au
processus qui l'a produit dans un fichier qui lui est propre.

Trois niveaux:

* **la sous-commande** -- `scan detect` enchaine ingestion (5.1) et detection
  (5.2), rien d'autre du pipeline (AC 1, AC 2);
* **le document** -- c'est un `scan_previz` en etat `detected`, construit par
  `build_scan_previz` et jamais redige une seconde fois (AC 3);
* **la survie a deux lots** -- deux detections successives ne s'ecrasent pas,
  et la completude du premier lot se relit depuis son seul fichier apres la
  seconde (AC 4, mur 3 de `EPIC7-ARB-49`).

**Regle des fabriques (CLAUDE.md), appliquee deux fois**: les deux lots du
test AC 4 portent des identifiants, des cardinaux de pages et des pages
manquantes **differents** (jamais un remplissage uniforme), et le lot dont on
relit la completude est le **premier** detecte, relu **apres** la detection
du second -- pas en premiere position. Le lot a page desordonnee du test AC 3
pose ses deux planches dans un ordre qui rend `read_rank` different de
`page_index` pour les deux pages, verifie separement champ par champ.
"""

from __future__ import annotations

import ast
import inspect
import json
import sys
from pathlib import Path

import cv2
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mixed_media_utility import (  # noqa: E402
    cli,
    page_roles,
    page_templates,
    patch_presets,
    previz_common,
    qr_codes,
    scan_detect,
    scan_detection,
    scan_previz,
)
from mixed_media_utility.io import project_layout  # noqa: E402

import test_scan_calibration_application as app  # noqa: E402
import test_scan_manifest as scan_fixtures  # noqa: E402

#: **Le code d'un lot ecrit INCOMPLET, depuis la story 11.4c** (lot V2,
#: AC 9.3). Le lot vise du vrac ci-dessous porte moins d'emplacements que son
#: gabarit : la persistance emet `LOT_INCOMPLET`, et l'inventaire atteint
#: desormais le code de sortie. Ce n'est pas un refus -- le lot est ecrit, et
#: c'est ce que la suite du test mesure au manifeste.
#:
#: Valeur ecrite en clair, jamais lue de `scan_write.CODE_SUCCES_PARTIEL` : lire
#: la constante que l'on mesure serait le test tautologique de la story 5.9.
LOT_INCOMPLET_MAIS_ECRIT = 4

CLI_PATH = REPO_ROOT / "src" / "mixed_media_utility" / "cli.py"
#: Le module de coeur qui porte l'orchestration depuis la story 7.3 (AC 2a) :
#: les balayages AST de cette suite le lisent LUI, la ou ils lisaient `cli.py`.
NOYAU_PATH = REPO_ROOT / "src" / "mixed_media_utility" / "scan_detect.py"


# ---------------------------------------------------------------------------
# Fabriques propres a cette suite
# ---------------------------------------------------------------------------


def run_scan(project_dir: Path, folder: Path, *args: str) -> int:
    return app.run_scan(project_dir, folder, *args)


def run_detect(project_dir: Path, folder: Path, *args: str) -> int:
    return cli.main([
        "scan", "--project", str(project_dir), "--scan", str(folder),
        "--dpi", str(app.DPI), *args, "detect",
    ])


def _erase_qr(page, payload: dict, *, dpi: int = app.DPI):
    """Effacer le QR d'une planche deja peinte: la feuille devient muette.

    Meme recette que `test_scan_calibration_application::_page_de_calibration_a_geometrie_perdue`,
    generalisee au role images.
    """
    page_layout = patch_presets.resolve_page_layout(
        payload["template_id"], payload["page_role"])
    zone = next(z for z in page_layout.reserved_zones_mm if z["name"] == "qr_zone")
    side = int(round(qr_codes.QR_PRINT_SIZE_TARGET_MM / 25.4 * dpi))
    qr_x, qr_y = page_templates.mm_to_px(zone["x"], zone["y"], dpi)
    page[qr_y:qr_y + side, qr_x:qr_x + side] = 255
    return page


def _write_images_lot(tmp_path: Path, *, name: str) -> tuple[Path, Path, list]:
    """Un lot de deux planches d'images, sans page de calibration.

    Le regime nominal (mixe pile refusee, `EPIC5-ARB-84`), le seul qu'`ingest en
    vrac` n'a pas encore rouvert.
    """
    payloads = app.lot_payloads(sheet_count=2, with_calibration=False)
    folder = app.write_scan_folder(
        tmp_path / name,
        [(payloads[0], app.PRESSES_DU_TIRAGE[0]),
         (payloads[1], app.PRESSES_DU_TIRAGE[1])],
    )
    project_dir = tmp_path / f"projet-{name}"
    return project_dir, folder, payloads


def _write_out_of_order_lot(tmp_path: Path, *, name: str) -> tuple[Path, Path, list]:
    """Deux planches posees dans un ordre qui inverse `read_rank` et `page_index`.

    `payloads[0]` porte `page_index=0`, `payloads[1]` porte `page_index=1`. Les
    ecrire dans l'ordre inverse fait que la **premiere** feuille lue
    (`read_rank=0`) porte `page_index=1`, et reciproquement -- les deux pages
    du lot sont donc mal appariees si l'un des deux champs est confondu avec
    l'autre, exactement le mutant M33/M25/5.8 deja paye trois fois.
    """
    payloads = app.lot_payloads(sheet_count=2, with_calibration=False)
    folder = app.write_scan_folder(
        tmp_path / name,
        [(payloads[1], app.PRESSES_DU_TIRAGE[0]),
         (payloads[0], app.PRESSES_DU_TIRAGE[1])],
    )
    project_dir = tmp_path / f"projet-{name}"
    return project_dir, folder, payloads


def _write_lot_with_a_missing_page(
    tmp_path: Path, *, name: str, rush_id: str, present_indexes: list[int],
    page_count: int, fps_target: float = 5.0,
) -> tuple[Path, Path, str]:
    """Un lot dont le cardinal declare depasse ce qui est physiquement scanne.

    `present_indexes` porte les seuls `page_index` reellement poses sur la
    vitre; les autres, jusqu'a `page_count`, sont **manquants**. C'est le lot
    dont la completude (AC 4) doit se lire correctement sur le document seul.
    """
    payloads = [
        scan_fixtures.make_payload(
            rush_id=rush_id, page_index=index, page_count=page_count,
            template_id=app.TEMPLATE, patch_preset_id=app.PRESET,
            fps_target=fps_target,
        )
        for index in present_indexes
    ]
    folder = app.write_scan_folder(
        tmp_path / name,
        [(payload, app.PRESSES_DU_TIRAGE[0]) for payload in payloads],
    )
    project_dir = tmp_path / f"projet-{name}"
    lot_id = payloads[0]["lot_id"]
    return project_dir, folder, lot_id


def _detection_documents(project_dir: Path, ingest_slug: str) -> list[Path]:
    return sorted(
        (project_dir / project_layout.SCANS_DIRNAME / ingest_slug
         / "detections").glob("*.json")
    )


def _read_document(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# AC 1 -- la sous-commande enchaine ingestion et detection, rien d'autre
# ---------------------------------------------------------------------------


def test_detect_ecrit_ingest_json_identique_a_scan_et_rend_0(tmp_path) -> None:
    """Meme chemin, meme forme, qu'on tape `scan` ou `scan ... detect`."""
    payloads = app.lot_payloads(sheet_count=2, with_calibration=False)
    ordered = [(payloads[0], app.PRESSES_DU_TIRAGE[0]),
               (payloads[1], app.PRESSES_DU_TIRAGE[1])]
    # Meme nom de base des deux cotes ('lot'): seul le `tmp_path` parent
    # differe, donc `scans_dir` et `locator.source_path` (qui l'embarquent)
    # restent identiques entre les deux passes -- la comparaison peut alors
    # porter sur le texte entier, pas seulement un sous-ensemble de champs.
    folder_scan = app.write_scan_folder(tmp_path / "a" / "lot", ordered)
    folder_detect = app.write_scan_folder(tmp_path / "b" / "lot", ordered)
    projet_scan = tmp_path / "projet-scan"
    projet_detect = tmp_path / "projet-detect"

    assert run_scan(projet_scan, folder_scan) == 0
    assert run_detect(projet_detect, folder_detect) == 0

    ingest_scan = (projet_scan / "scans" / "lot" / "ingest.json").read_text(
        encoding="utf-8")
    ingest_detect = (projet_detect / "scans" / "lot" / "ingest.json").read_text(
        encoding="utf-8")
    assert ingest_scan == ingest_detect


def test_detect_garde_les_memes_refus_d_ingestion_que_scan(tmp_path) -> None:
    """`ScanIngestError`: meme message, meme code `1`, sur les deux commandes."""
    absent = tmp_path / "n-existe-pas"
    projet_scan = tmp_path / "projet-scan"
    projet_detect = tmp_path / "projet-detect"

    code_scan = run_scan(projet_scan, absent)
    code_detect = run_detect(projet_detect, absent)

    assert code_scan == 1
    assert code_detect == 1


def test_detect_garde_les_memes_refus_de_detection_que_scan(tmp_path, monkeypatch) -> None:
    """`ScanDetectionError`: meme garde, sur les deux commandes."""
    payloads = app.lot_payloads(sheet_count=2, with_calibration=False)
    ordered = [(payloads[0], app.PRESSES_DU_TIRAGE[0]),
               (payloads[1], app.PRESSES_DU_TIRAGE[1])]
    folder = app.write_scan_folder(tmp_path / "lot", ordered)
    projet_detect = tmp_path / "projet-detect"

    def _echoue(*args, **kwargs):
        raise scan_detection.ScanDetectionError("detection en panne, mesure de test")

    # Le seam a **bouge** avec la story 5.24: `detect` appelle desormais la
    # moitie amont de la detection (`detect_pages`), pour que le tri s'insere
    # avant `_reconcile_lot`. La garde, elle, ne bouge pas -- c'est ce que ce
    # test verifie.
    monkeypatch.setattr(cli.scan_detection, "detect_pages", _echoue)
    assert run_detect(projet_detect, folder) == 1


def test_detect_sans_aucune_planche_identifiee_n_ecrit_aucun_document(
    tmp_path, capsys,
) -> None:
    """AC 1, test 3: pile muette -- constat dit, ingestion ecrite, code 0, rien de plus."""
    payloads = app.lot_payloads(sheet_count=1, with_calibration=False)
    page = app.build_page(payloads[0], press=app.PRESSES_DU_TIRAGE[0])
    _erase_qr(page, payloads[0])
    folder = tmp_path / "muet"
    folder.mkdir()
    cv2.imwrite(str(folder / "page_01.tiff"), page)
    project_dir = tmp_path / "projet-muet"

    assert run_detect(project_dir, folder) == 0

    sortie = capsys.readouterr().out
    assert "aucune identifiee" in sortie
    ingest_slug = folder.name
    detections_dir = project_dir / "scans" / ingest_slug / "detections"
    assert not detections_dir.exists() or not any(detections_dir.iterdir())
    assert (project_dir / "scans" / ingest_slug / "ingest.json").is_file()


def test_detect_sur_pile_de_calibration_seule_renvoie_a_calibrate(
    tmp_path, capsys,
) -> None:
    """Question ouverte 1: aucune identite de lot -> constat, aucun document, 0."""
    payload = app.lot_payloads()[0]
    assert payload["page_role"] == page_roles.PAGE_ROLE_CALIBRATION
    folder = tmp_path / "calib-seule"
    folder.mkdir()
    cv2.imwrite(str(folder / "page_01.tiff"),
                app.build_page(payload, press=app.PRESSE_CALIBRATION))
    project_dir = tmp_path / "projet-calib-seule"

    assert run_detect(project_dir, folder) == 0

    sortie = capsys.readouterr().out
    assert "calibrate" in sortie
    ingest_slug = folder.name
    detections_dir = project_dir / "scans" / ingest_slug / "detections"
    assert not detections_dir.exists() or not any(detections_dir.iterdir())


def test_scan_aide_ne_gagne_aucun_drapeau_nouveau(capsys) -> None:
    """Frontiere negative de l'AC 1: aucun drapeau neuf sur le parent `scan`.

    `detect` est une sous-commande, jamais un drapeau -- le motif deja refuse
    le 2026-08-17 pour `--nom`. Mesure sur l'ensemble exact des drapeaux
    connus de `scan` (hors `-h`), plutot que sur un simple grep du mot
    "detect": un flag `--detect-xxx` ajoute par erreur romprait cette egalite
    d'ensemble.
    """
    with pytest.raises(SystemExit):
        cli.main(["scan", "--help"])
    sortie = capsys.readouterr().out
    import re
    drapeaux = set(re.findall(r"(?m)^  (--[a-z-]+)", sortie))
    attendu = {
        "--project", "--scan", "--dpi", "--lot-slug", "--overwrite",
        "--cc", cli.color_calibration.DIVERGENCE_BYPASS_FLAG,
        cli.color_calibration.RAW_OUTPUT_FLAG, cli.PROFILE_FLAG,
        # **Ajoute sciemment le 2026-08-31** (`EPIC11-ARB-104`, Egan : « tout
        # doit etre versionnable OU ecrase »). `scan` etait le dernier objet
        # produit par l'outil a n'offrir qu'une issue destructrice devant une
        # sortie existante ; `--nouvelle-version` est cette seconde issue.
        #
        # La frontiere n'est PAS affaiblie : elle mesure toujours l'egalite
        # d'ensemble, donc un drapeau ajoute par megarde la fait rougir. Ce
        # qu'elle interdit est un drapeau NON DECIDE -- pas un drapeau. Et
        # elle a fait exactement son travail : elle a attrape cet ajout, que
        # la revue en trois couches n'avait pas vu, parce qu'il ne se lit ni
        # dans le diff du coeur ni dans les bancs du versionnage.
        "--nouvelle-version",
    }
    assert drapeaux == attendu, drapeaux


# ---------------------------------------------------------------------------
# AC 2 -- un fichier PAR detection, aucune frame, manifest jamais touche
# ---------------------------------------------------------------------------


def test_detect_n_ecrit_aucune_frame_v3a(tmp_path) -> None:
    """V3.a, la mesure de la revue: comptage de fichiers, jamais absence d'appel."""
    project_dir, folder, _ = _write_images_lot(tmp_path, name="v3a")

    assert run_detect(project_dir, folder) == 0

    output_dir = project_dir / project_layout.OUTPUT_FRAMES_DIRNAME
    assert not output_dir.exists() or len(list(output_dir.rglob("*"))) == 0


def test_detect_laisse_project_json_intact(tmp_path) -> None:
    """Absent avant, absent apres; present avant, identique octet pour octet apres."""
    project_dir, folder, _ = _write_images_lot(tmp_path, name="manifest")

    assert run_detect(project_dir, folder) == 0
    assert not (project_dir / "project.json").exists()

    assert run_scan(project_dir, folder, "--lot-slug", "manifest-scan") == 0
    avant = (project_dir / "project.json").read_bytes()

    assert run_detect(project_dir, folder, "--lot-slug", "manifest-scan-2") == 0
    apres = (project_dir / "project.json").read_bytes()
    assert avant == apres


def test_deux_detections_successives_produisent_deux_fichiers(tmp_path, monkeypatch) -> None:
    """La seconde n'ecrase pas la premiere -- deux detections du meme scan.

    L'horloge est figee (revue de 5.25, correctif de la fenetre TOCTOU de
    `_unique_detection_document_path`): sans elle, deux appels reels a
    `datetime.now()` different presque toujours d'une seconde a l'autre --
    `generated_at_utc` n'entre alors jamais deux fois en collision, et ce
    test passait sans exercer la moindre fois la boucle de suffixe. La figer
    force la collision a chaque execution, exactement le regime que la
    creation exclusive (`os.O_CREAT | os.O_EXCL`) doit fermer sans fenetre de
    course.
    """
    project_dir, folder, _ = _write_images_lot(tmp_path, name="double")

    class _HorlogeFigee:
        @staticmethod
        def now(tz=None):
            import datetime as _dt
            return _dt.datetime(2026, 8, 24, 12, 0, 0, tzinfo=tz)

    monkeypatch.setattr(scan_detect, "datetime", _HorlogeFigee)

    assert run_detect(project_dir, folder) == 0
    assert run_detect(project_dir, folder) == 0

    documents = _detection_documents(project_dir, "double")
    assert len(documents) == 2, documents
    assert documents[0].name != documents[1].name
    # La collision est bien celle qu'on force: l'un des deux noms est le
    # candidat de base, l'autre porte le suffixe `-2` que la boucle de
    # creation exclusive pose sur le premier deja pris -- jamais deux noms
    # differents par hasard d'horloge.
    noms = {d.name for d in documents}
    assert "detect-20260824T120000Z.json" in noms, noms
    assert "detect-20260824T120000Z-2.json" in noms, noms


def test_le_document_vit_sous_detections_jamais_a_la_place_d_ingest_json(
    tmp_path,
) -> None:
    project_dir, folder, _ = _write_images_lot(tmp_path, name="emplacement")

    assert run_detect(project_dir, folder) == 0

    documents = _detection_documents(project_dir, "emplacement")
    assert len(documents) == 1
    document_path = documents[0]
    scan_dir = project_dir / "scans" / "emplacement"
    assert document_path.parent == scan_dir / "detections"
    assert (scan_dir / "ingest.json").is_file()
    assert document_path != scan_dir / "ingest.json"


def test_detect_n_appelle_ni_ecriture_de_frames_ni_manifest() -> None:
    """Frontiere negative de l'AC 2: balayage AST du corps de `scan_detect_command`.

    `check_scan_conflicts` n'est **plus** dans la liste des interdits depuis la
    revue de 5.25: la fonction ne fait qu'une chose qui touche au manifest --
    le **lire** pour refuser une pile mixte avant toute ecriture (meme appel
    que `scan_command`, `cli.py:2200`) -- et ne l'ecrit jamais. La frontiere
    reelle porte sur l'ecriture: aucune frame, aucun manifest persiste.
    """
    # **Les deux moities du chemin sont balayees** depuis la story 5.24: le
    # corps qui construit et ecrit le document a ete extrait de la commande pour
    # avoir deux appelants (un document par lot trie), et une frontiere qui ne
    # lirait plus que la commande cesserait de voir la ou une ecriture pourrait
    # revenir.
    appels = set()
    for fonction in (cli.scan_detect_command,
                     scan_detect.run_scan_detect,
                     scan_detect.ecrire_le_document_de_detection,
                     scan_detect._detecter_le_vrac,
                     scan_detect._detecter_le_lot_promis):
        arbre = ast.parse(inspect.getsource(fonction))
        appels |= {
            noeud.func.attr for noeud in ast.walk(arbre)
            if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Attribute)
        }
    for interdit in ("write_lot_output_frames", "persist_scan"):
        assert interdit not in appels, sorted(appels)
    # Temoin positif: le refus de pile mixte est bien cable (revue de 5.25),
    # sans quoi cette frontiere ne verifierait plus rien de la garde ajoutee.
    assert "check_scan_conflicts" in appels, sorted(appels)


# ---------------------------------------------------------------------------
# AC 3 -- le document EST un scan_previz en etat `detected` (schema previz-1)
# ---------------------------------------------------------------------------


def test_le_document_ecrit_est_un_scan_previz_detected(tmp_path) -> None:
    project_dir, folder, payloads = _write_images_lot(tmp_path, name="etat")

    assert run_detect(project_dir, folder) == 0

    document = _read_document(_detection_documents(project_dir, "etat")[0])
    assert document["previz_schema_version"] == scan_previz.PREVIZ_SCHEMA_VERSION
    assert document["kind"] == scan_previz.SCAN_PREVIZ_KIND
    assert document["state"] == scan_previz.SCAN_PREVIZ_STATE_DETECTED
    assert document["counters"]["frames_written"] is None
    assert document["counters"]["frames_expected"] is None
    assert document["counters"]["synthetic_frame_count"] is None
    assert document["subject"]["lot_id"] == payloads[0]["lot_id"]


def test_chaque_page_porte_read_rank_et_page_index_jamais_confondus(tmp_path) -> None:
    """Regle des fabriques: pages dans le desordre, les deux champs verifies separement."""
    project_dir, folder, payloads = _write_out_of_order_lot(tmp_path, name="desordre")

    assert run_detect(project_dir, folder) == 0

    document = _read_document(_detection_documents(project_dir, "desordre")[0])
    pages = document["pages"]
    assert len(pages) == 2
    # Les deux champs sont presents et **au moins une** page les porte
    # differents -- jamais l'un reconstruit depuis l'autre.
    for page in pages:
        assert "read_rank" in page and "page_index" in page
        assert page["read_rank"] is not None
        assert page["page_index"] is not None
    assert any(page["read_rank"] != page["page_index"] for page in pages)
    # Appariement nominatif: la page dont l'identite decodee porte
    # `page_index=0` est bien celle du payload qui le declare, quel que soit
    # son rang de lecture -- jamais une lecture positionnelle.
    par_page_index = {page["page_index"]: page for page in pages}
    for payload in payloads:
        page = par_page_index[payload["page_index"]]
        assert page["decoded_identity"]["lot_id"] == payload["lot_id"]


def test_la_construction_verse_les_cinq_vocabulaires_fermes() -> None:
    """AC 3: le controle de vocabulaire passe au temps de construction (wiring AST)."""
    # Story 7.3 (AC 2a) : le corps a quitte `cli.py` pour le module de coeur
    # `scan_detect`. Les deux fichiers sont balayes -- le second parce qu'il
    # porte l'appel, le premier pour mesurer qu'il ne l'a pas GARDE en double.
    appels = []
    for chemin in (NOYAU_PATH, CLI_PATH):
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        appels += [
            noeud for noeud in ast.walk(arbre)
            if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Attribute)
            and noeud.func.attr == "build_scan_previz"
        ]
    assert len(appels) == 1, len(appels)
    mots_cles = {kw.arg for kw in appels[0].keywords if kw.arg}
    for attendu in (
        "ingest_warning_vocabulary", "detection_warning_vocabulary",
        "output_warning_vocabulary", "synthetic_reason_vocabulary",
        "calibration_status_vocabulary",
    ):
        assert attendu in mots_cles, sorted(mots_cles)


def test_le_fichier_ecrit_est_deja_en_forme_canonique(tmp_path) -> None:
    """Determinisme (AC 3): `canonical_json` applique au document relu rend le meme texte."""
    project_dir, folder, _ = _write_images_lot(tmp_path, name="canon")

    assert run_detect(project_dir, folder) == 0

    document_path = _detection_documents(project_dir, "canon")[0]
    texte_brut = document_path.read_text(encoding="utf-8")
    reconstruit = previz_common.canonical_json(json.loads(texte_brut))
    assert texte_brut == reconstruit


# ---------------------------------------------------------------------------
# AC 4 -- deux lots, deux fichiers, la completude du premier survit
# ---------------------------------------------------------------------------


def test_deux_lots_distinguables_rendent_deux_fichiers_et_la_completude_survit(
    tmp_path,
) -> None:
    """Mur 3 ferme (`EPIC7-ARB-49`): la section unique du manifest n'est plus le support.

    Le lot A (3 pages attendues, la page 1 manquante) est detecte **en
    premier**, puis le lot B (2 pages attendues, complet) est detecte en
    second. La completude du lot A -- la **cible** -- se relit **apres** la
    detection de B, depuis le seul fichier de A.
    """
    project_dir = tmp_path / "projet-deux-lots"
    projet_a, folder_a, lot_id_a = _write_lot_with_a_missing_page(
        tmp_path, name="lot-a", rush_id="rush-detect-a",
        present_indexes=[0, 2], page_count=3, fps_target=5.0,
    )
    projet_b, folder_b, lot_id_b = _write_lot_with_a_missing_page(
        tmp_path, name="lot-b", rush_id="rush-detect-b",
        present_indexes=[0, 1], page_count=2, fps_target=6.0,
    )
    assert lot_id_a != lot_id_b

    # Meme projet pour les deux lots -- c'est la section unique du manifest,
    # historiquement, que la story ferme.
    assert run_detect(project_dir, folder_a, "--lot-slug", "lot-a") == 0
    assert run_detect(project_dir, folder_b, "--lot-slug", "lot-b") == 0

    document_a = _read_document(_detection_documents(project_dir, "lot-a")[0])
    document_b = _read_document(_detection_documents(project_dir, "lot-b")[0])

    # Verifie nominativement: par `lot_id` et par l'ensemble des `page_index`,
    # jamais par les seuls cardinaux.
    assert document_a["subject"]["lot_id"] == lot_id_a
    assert document_b["subject"]["lot_id"] == lot_id_b
    assert {p["page_index"] for p in document_a["pages"]} == {0, 2}
    assert {p["page_index"] for p in document_b["pages"]} == {0, 1}

    # Completude du lot A, derivee du document A **seul**: cardinal attendu
    # moins l'ensemble des `page_index` presents, jamais consulte le manifest
    # (absent) ni le fichier de B.
    expected_a = document_a["counters"]["pages_expected"]
    present_a = {p["page_index"] for p in document_a["pages"]}
    missing_a = set(range(expected_a)) - present_a
    assert expected_a == 3
    assert missing_a == {1}

    expected_b = document_b["counters"]["pages_expected"]
    present_b = {p["page_index"] for p in document_b["pages"]}
    assert set(range(expected_b)) - present_b == set()

    # Deux detections, deux identites de contenu.
    assert document_a["fingerprints"]["detection"] != document_b["fingerprints"]["detection"]


# ---------------------------------------------------------------------------
# AC 5 -- AR2: `scan_command` et `scan detect` recoivent leurs gardes larges
# ---------------------------------------------------------------------------


def test_scan_keyboard_interrupt_rend_130_sans_trace(tmp_path, capsys, monkeypatch) -> None:
    project_dir, folder, _ = _write_images_lot(tmp_path, name="ki-scan")

    def _interrompt(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli.scan_output_frames, "write_lot_output_frames", _interrompt)
    assert run_scan(project_dir, folder) == 130
    sortie = capsys.readouterr()
    assert "Interruption clavier" in sortie.out
    assert "Traceback" not in sortie.out
    assert "Traceback" not in sortie.err


def test_scan_oserror_rend_1_avec_message_actionnable(tmp_path, capsys, monkeypatch) -> None:
    project_dir, folder, _ = _write_images_lot(tmp_path, name="os-scan")

    def _echoue(*args, **kwargs):
        raise OSError("disque plein (mesure de test)")

    monkeypatch.setattr(cli.scan_output_frames, "write_lot_output_frames", _echoue)
    assert run_scan(project_dir, folder) == 1
    sortie = capsys.readouterr()
    assert "Erreur" in sortie.err
    assert "espace" in sortie.err.lower() or "disque" in sortie.err.lower()
    assert "Traceback" not in sortie.out
    assert "Traceback" not in sortie.err


def test_detect_keyboard_interrupt_dit_ce_qui_n_etait_pas_en_jeu(
    tmp_path, capsys, monkeypatch,
) -> None:
    project_dir, folder, _ = _write_images_lot(tmp_path, name="ki-detect")

    def _interrompt(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli.scan_previz, "build_scan_previz", _interrompt)
    assert run_detect(project_dir, folder) == 130
    sortie = capsys.readouterr()
    assert "Interruption clavier" in sortie.out
    assert "frame" in sortie.out and "manifest" in sortie.out
    assert "Traceback" not in sortie.out
    assert "Traceback" not in sortie.err


def test_detect_oserror_rend_1(tmp_path, capsys, monkeypatch) -> None:
    project_dir, folder, _ = _write_images_lot(tmp_path, name="os-detect")

    def _echoue(*args, **kwargs):
        raise OSError("dossier non inscriptible (mesure de test)")

    monkeypatch.setattr(
        scan_detect, "ecrire_document_json_atomiquement", _echoue)
    assert run_detect(project_dir, folder) == 1
    sortie = capsys.readouterr()
    assert "Erreur" in sortie.err
    assert "Traceback" not in sortie.out
    assert "Traceback" not in sortie.err


# ---------------------------------------------------------------------------
# Revue de 5.25, patch 1 -- la pile mixte est refusee, comme sur `scan`
# ---------------------------------------------------------------------------


def test_detect_sur_pile_mixte_est_refusee_comme_scan(tmp_path, capsys) -> None:
    """Meme pile, meme refus (`REFUS_PILE_MIXTE`), sur `scan` et `scan detect`.

    Avant ce correctif, `scan_detect_command` n'appelait jamais
    `scan_manifest.check_scan_conflicts` (le refus que `scan_command` applique
    via `cli.py:2200`): une pile qui melange une page de calibration et des
    planches d'images etait acceptee, l'identite du lot etait derivee de la
    premiere planche d'**images** trouvee, et un document "detected" complet
    en sortait -- alors que `scan` sur la meme pile la refusait deja.

    La pile porte deux planches distinguables (regle des fabriques) et la
    page de calibration au milieu, ni premiere ni derniere.
    """
    payloads = app.lot_payloads(sheet_count=2, with_calibration=True)
    ordered = [
        (payloads[1], app.PRESSES_DU_TIRAGE[0]),
        (payloads[0], app.PRESSE_CALIBRATION),
        (payloads[2], app.PRESSES_DU_TIRAGE[1]),
    ]
    folder_scan = app.write_scan_folder(tmp_path / "a" / "mixte", ordered)
    folder_detect = app.write_scan_folder(tmp_path / "b" / "mixte", ordered)
    projet_scan = tmp_path / "projet-scan-mixte"
    projet_detect = tmp_path / "projet-detect-mixte"

    # **`--lot-slug` est passe depuis la story 5.24** (`EPIC7-ARB-63`): c'est
    # lui qui porte le regime ou l'operateur **promet** un lot unique, et c'est
    # ce regime-la que `REFUS_PILE_MIXTE` garde. Sans lui, la meme pile est
    # desormais **triee** sur les deux commandes (AC 5) -- le refus n'est ni
    # supprime, ni elargi, ni affaibli, il **cesse d'etre atteint** sur le
    # chemin qui trie. Le volet symetrique est
    # `test_detect_sur_pile_mixte_est_triee_sans_lot_slug`, sans lequel ce test
    # resterait vert sur un refus devenu inconditionnel.
    code_scan = run_scan(projet_scan, folder_scan, "--lot-slug", "mixte")
    sortie_scan = capsys.readouterr().err
    code_detect = run_detect(projet_detect, folder_detect, "--lot-slug", "mixte")
    sortie_detect = capsys.readouterr().err

    assert code_scan == 1, sortie_scan
    assert code_detect == 1, sortie_detect
    # Meme motif de refus des deux cotes, pas seulement le meme code de
    # sortie: le message de `_check_pile_homogene` nomme les deux familles de
    # pages en cause.
    for sortie in (sortie_scan, sortie_detect):
        assert "page(s) de calibration" in sortie, sortie
        assert "planche(s) d'images" in sortie, sortie
    # Refus **avant** toute ecriture: aucun document de detection, aucun
    # manifest.
    ingest_slug = folder_detect.name
    detections_dir = projet_detect / "scans" / ingest_slug / "detections"
    assert not detections_dir.exists() or not any(detections_dir.iterdir())
    assert not (projet_detect / "project.json").exists()


def test_pages_expected_count_exclut_toujours_la_calibration_sous_le_refus(
    tmp_path, monkeypatch,
) -> None:
    """Symptome lie au patch 1: `pages_expected_count` ne doit jamais compter une
    page de calibration -- meme exclusion que la boucle `crop_plans` juste en
    dessous, qui exclut deja explicitement `PAGE_ROLE_CALIBRATION`.

    Une fois le refus de pile mixte en place, ce symptome devient sans objet
    en pratique (la pile ne construit plus jamais de document). Le calcul
    reste neanmoins epingle **independamment** du refus: le refus est
    court-circuite ici (`check_scan_conflicts` neutralise) pour que ce test
    continue de faire echouer un mutant qui retirerait le filtre de role,
    plutot que de se contenter d'un chemin devenu inatteignable par la CLI
    nominale. La page de calibration porte un `page_count` deliberement
    **different** (99) de celui des planches (3): un filtre absent ferait
    entrer 99 dans le `max()`.
    """
    payloads = app.lot_payloads(sheet_count=2, with_calibration=True)
    assert payloads[0]["page_role"] == page_roles.PAGE_ROLE_CALIBRATION
    payloads[0] = dict(payloads[0], page_count=99)
    ordered = [
        (payloads[1], app.PRESSES_DU_TIRAGE[0]),
        (payloads[0], app.PRESSE_CALIBRATION),
        (payloads[2], app.PRESSES_DU_TIRAGE[1]),
    ]
    folder = app.write_scan_folder(tmp_path / "mixte-divergent", ordered)
    project_dir = tmp_path / "projet-mixte-divergent"

    monkeypatch.setattr(
        cli.scan_manifest, "check_scan_conflicts", lambda *a, **k: None)

    # **`--lot-slug` est passe depuis la story 5.24**, et c'est ce qui garde ce
    # test mordant: sans lui la pile est desormais **triee** et la page de
    # calibration ne rejoint aucun lot, donc elle n'atteint plus le calcul que ce
    # test epingle -- le test resterait vert en ne verifiant plus rien. Sous
    # `--lot-slug` l'operateur promet un lot unique, aucun tri n'a lieu, et la
    # pile mixte atteint bien le constructeur de document (le refus etant
    # court-circuite juste au-dessus).
    assert run_detect(project_dir, folder, "--lot-slug", "mixte-divergent") == 0

    document = _read_document(_detection_documents(project_dir, "mixte-divergent")[0])
    assert document["counters"]["pages_expected"] == 3, document["counters"]


def test_les_gardes_ar2_sont_ajoutees_en_dernier_sans_reordonner_le_reste() -> None:
    """Frontiere negative de l'AC 5: la garde large ferme l'unique `try` externe.

    Verifie sur `scan_command`: le dernier statement de haut niveau du corps
    de la fonction est un `Try` dont les deux SEULS gestionnaires sont, dans
    l'ordre, `KeyboardInterrupt` puis `OSError` -- rien n'a ete insere entre
    les deux, et aucun `except` metier n'a ete deplace dans cet enrobage.
    """
    arbre = ast.parse(inspect.getsource(cli.scan_command))
    fonction = arbre.body[0]
    dernier = fonction.body[-1]
    assert isinstance(dernier, ast.Try), type(dernier)
    noms = [h.type.id for h in dernier.handlers]
    assert noms == ["KeyboardInterrupt", "OSError"], noms

    arbre_detect = ast.parse(inspect.getsource(cli.scan_detect_command))
    fonction_detect = arbre_detect.body[0]
    dernier_detect = fonction_detect.body[-2]  # le print + return suivent le try
    # Le `try` externe de `scan_detect_command` est le dernier statement avant
    # les lignes de succes -- meme motif que `scan_command`.
    tries = [n for n in fonction_detect.body if isinstance(n, ast.Try)]
    assert len(tries) == 1, len(tries)
    noms_detect = [h.type.id for h in tries[0].handlers]
    assert noms_detect == ["KeyboardInterrupt", "OSError"], noms_detect


# ---------------------------------------------------------------------------
# AC 6 -- frontieres dures propres a cette story
# ---------------------------------------------------------------------------


def test_detect_sur_pile_mixte_est_triee_sans_lot_slug(tmp_path) -> None:
    """AC 5 et 2bis de 5.24, volet symetrique du refus ci-dessus.

    Sans `--lot-slug`, l'operateur ne promet rien et le **tri par QR** decide:
    la page de calibration quitte le lot avant toute lecture d'identite, et un
    document de detection homogene sort quand meme. Sans ce test, le precedent
    resterait vert sur un refus devenu inconditionnel -- c'est-a-dire sur
    exactement le contraire de ce que la story livre.
    """
    payloads = app.lot_payloads(sheet_count=2, with_calibration=True)
    folder = app.write_scan_folder(tmp_path / "mixte", [
        (payloads[1], app.PRESSES_DU_TIRAGE[0]),
        (payloads[0], app.PRESSE_CALIBRATION),
        (payloads[2], app.PRESSES_DU_TIRAGE[1]),
    ])
    project_dir = tmp_path / "projet-mixte-trie"

    assert run_detect(project_dir, folder) == 0

    documents = _detection_documents(project_dir, "mixte")
    assert len(documents) == 1, documents
    document = _read_document(documents[0])
    assert document["state"] == scan_previz.SCAN_PREVIZ_STATE_DETECTED
    # Le document est **homogene**: la page de calibration n'y est pas.
    assert len(document["pages"]) == 2, document["pages"]
    # Et le rapport de tri, lui, la nomme -- c'est un document SEPARE.
    rapport = json.loads(
        (project_dir / "scans" / "mixte" / cli.TRI_DOCUMENT_FILENAME).read_text(
            encoding="utf-8"))
    assert len(rapport["calibration"]) == 1
    assert len(rapport["lots"]) == 1
    # `detect` n'ajuste ni n'ecrit aucun profil (contrat de 5.25, mur 3).
    assert rapport["profils_crees"] == []
    assert not (project_dir / "versions" / "calibration").exists()


def _planche_de_lot(indice: int, page_index: int) -> dict:
    """Une planche d'un des **trois** lots temoins du vrac.

    Les trois lots sont **du meme rush a trois cadences** -- le cas nominal v2.1
    et le regime exact du risque R12 --, et non trois rushes differents: un
    projet n'accepte un scan que d'un rush que son manifest declare deja.
    """
    rush, fps = (scan_fixtures.RUSH, (5.0, 8.0, 12.5)[indice])
    return scan_fixtures.make_payload(
        page_index=page_index, page_count=2, first_slot=2 * page_index,
        slot_count=2, template_id=app.TEMPLATE, patch_preset_id=app.PRESET,
        rush_id=rush, fps_target=fps,
        page_role=page_roles.PAGE_ROLE_IMAGES)


def test_deux_lots_en_vrac_rendent_deux_documents_homogenes_et_un_rapport(
    tmp_path,
) -> None:
    """AC 10 de 5.24 (`EPIC7-ARB-63`), de bout en bout sur le chemin `detect`.

    Une pile a **deux lots** produit **deux** documents de detection, chacun
    homogene, **plus** le rapport de tri qui nomme les deux. Le contrat de 5.25
    est inchange: chaque document garde sa forme et son etat `detected`, et le
    rapport de tri est un document **separe**.

    Les deux lots sont melanges a l'arrivee et **le lot vise n'est pas le
    premier arrive**: un `find` fautif qui rendrait toujours le premier lot ne
    se demasque pas autrement (mutant `M25`, 257 tests verts).
    """
    feuilles = [
        (_planche_de_lot(1, 0), app.PRESSES_DU_TIRAGE[0]),
        (_planche_de_lot(0, 0), app.PRESSES_DU_TIRAGE[1]),
        (_planche_de_lot(1, 1), app.PRESSES_DU_TIRAGE[1]),
        (_planche_de_lot(0, 1), app.PRESSES_DU_TIRAGE[0]),
    ]
    folder = app.write_scan_folder(tmp_path / "vrac", feuilles)
    project_dir = tmp_path / "projet-vrac"

    assert run_detect(project_dir, folder) == 0

    documents = [_read_document(chemin)
                 for chemin in _detection_documents(project_dir, "vrac")]
    assert len(documents) == 2, documents
    # **Chacun homogene**: un document, un lot, et les deux lots sont distincts.
    lots = sorted(document["subject"]["lot_id"] for document in documents)
    attendus = sorted({payload["lot_id"] for payload, _ in feuilles})
    assert lots == attendus, (lots, attendus)
    for document in documents:
        assert document["state"] == scan_previz.SCAN_PREVIZ_STATE_DETECTED
        assert len(document["pages"]) == 2, document["pages"]

    rapport = json.loads(
        (project_dir / "scans" / "vrac" / cli.TRI_DOCUMENT_FILENAME).read_text(
            encoding="utf-8"))
    assert sorted(lot["lot_id"] for lot in rapport["lots"]) == attendus
    # Page par page et jamais par cardinal: chaque lot du rapport porte **ses**
    # pages.
    for lot in rapport["lots"]:
        assert len(lot["pages"]) == 2, lot
    assert rapport["reliquat"] == [] and rapport["hors_perimetre"] == []


def test_scan_write_consomme_un_document_de_vrac_sans_rien_savoir_du_tri(
    tmp_path,
) -> None:
    """AC 13 : `scan-write` est inchange -- il consomme **un** document.

    Un document produit par le chemin de vrac est un document de detection
    ordinaire: la commande d'ecriture le consomme sans avoir appris quoi que ce
    soit du vrac. C'est la moitie executable de la frontiere que
    `test_scan_write_n_apprend_rien_du_vrac` mesure au source.
    """
    feuilles = [
        (_planche_de_lot(1, 0), app.PRESSES_DU_TIRAGE[0]),
        (_planche_de_lot(0, 0), app.PRESSES_DU_TIRAGE[1]),
        (_planche_de_lot(1, 1), app.PRESSES_DU_TIRAGE[1]),
        (_planche_de_lot(0, 1), app.PRESSES_DU_TIRAGE[0]),
    ]
    folder = app.write_scan_folder(tmp_path / "vrac", feuilles)
    project_dir = tmp_path / "projet-vrac-write"
    assert run_detect(project_dir, folder) == 0

    documents = _detection_documents(project_dir, "vrac")
    assert len(documents) == 2
    # Le lot vise est celui du **second** document, jamais le premier venu.
    vise = sorted(documents)[1]
    code = cli.main([cli.SCAN_WRITE_COMMAND, "--project", str(project_dir),
                     "--detection", str(vise)])
    assert code == LOT_INCOMPLET_MAIS_ECRIT, vise

    manifeste = json.loads(
        (project_dir / "project.json").read_text(encoding="utf-8"))
    ecrit = _read_document(vise)["subject"]["lot_id"]
    assert [lot["lot_id"] for lot in manifeste["lots"]] == [ecrit]


def test_le_document_de_detection_ne_recoit_aucun_champ_pour_le_vrac(tmp_path) -> None:
    """AC 13 de 5.24: le contrat de 5.25 est **inchange**.

    Le test qui vivait ici jusqu'au 2026-08-25 verifiait que le module de tri
    n'existait pas encore -- il a livre, donc son sujet a disparu et il est
    **remplace**, jamais simplement supprime. Ce qu'il gardait reellement, c'est
    la frontiere: le document garde sa forme et son etat `detected`, et le
    rapport de tri est un document **separe**.

    L'ensemble des cles est compare a celui d'un document produit sous le regime
    `--lot-slug`, ou aucun tri n'a lieu: deux regimes, **un seul** contrat de
    document.
    """
    payloads = app.lot_payloads(sheet_count=2, with_calibration=False)
    feuilles = [(payloads[0], app.PRESSES_DU_TIRAGE[0]),
                (payloads[1], app.PRESSES_DU_TIRAGE[1])]
    promis = app.write_scan_folder(tmp_path / "a" / "pile", feuilles)
    trie = app.write_scan_folder(tmp_path / "b" / "pile", feuilles)

    assert run_detect(tmp_path / "projet-promis", promis, "--lot-slug", "pile") == 0
    assert run_detect(tmp_path / "projet-trie", trie) == 0

    gauche = _read_document(
        _detection_documents(tmp_path / "projet-promis", "pile")[0])
    droite = _read_document(
        _detection_documents(tmp_path / "projet-trie", "pile")[0])
    assert set(gauche) == set(droite)
    for interdit in ("tri", "vrac", "partition", "reliquat", "hors_perimetre"):
        assert interdit not in droite, interdit
    # **Champ a champ, hors horodatage de generation** (AC 2bis): une pile
    # mono-lot sans `--lot-slug` rend le MEME document qu'avec.
    volatiles = {"generated_at_utc", "fingerprint"}
    assert {cle: valeur for cle, valeur in droite.items() if cle not in volatiles} == {
        cle: valeur for cle, valeur in gauche.items() if cle not in volatiles}


def test_detect_ne_touche_aucun_champ_de_5_12_5_13_5_14() -> None:
    """Frontiere de `EPIC7-ARB-49`: aucun champ de date de scan, discriminant de
    tirage ou suffixe de passe sur **tout** le chemin de detection.

    **Etendu par la revue de vague de 5.24** (couche 3). Cette garde ne lisait
    que `scan_detect_command`, comme son voisin ci-dessus avant qu'il ne soit
    corrige -- or la story a extrait le corps de la commande vers deux fonctions
    pour avoir deux appelants. La garde balayait donc une quinzaine de lignes au
    lieu de deux cents, et ne couvrait plus ni le tri, ni la composition des
    pages d'un lot, ni la consignation. Verdict inchange (zero occurrence
    partout, rejoue), mais la surface avait fondu : c'est l'erosion qui etait le
    defaut, pas le verdict.
    """
    fonctions = (
        cli.scan_detect_command,
        scan_detect.run_scan_detect,
        scan_detect.ecrire_le_document_de_detection,
        scan_detect._detecter_le_vrac,
        scan_detect._detecter_le_lot_promis,
        cli._scanner_le_vrac,
        cli._pages_du_lot,
        cli._consigner_les_pages_de_calibration_du_vrac,
    )
    for fonction in fonctions:
        source = inspect.getsource(fonction)
        for interdit in ("scan_date", "tirage_discriminant", "pass_suffix",
                         "_pass2", "_take2"):
            assert interdit not in source, (fonction.__name__, interdit)

    # Temoin: la garde mord vraiment. Sans lui, un balayage qui ne lirait rien
    # (fonctions renommees, source vide) passerait tout aussi vert.
    assert any("payload" in inspect.getsource(f) for f in fonctions)
