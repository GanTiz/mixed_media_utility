"""Story 5.26: `scan-write` -- l'ecriture des TIFF depuis un document de detection.

Le second temps du scan en deux temps (FR6 + FR7): `scan detect` (5.25) a
persiste ce que la detection a vu; cette commande le consomme tel quel --
rien n'est re-detecte -- et rejoue la MEME moitie aval que `scan`
(`_ecrire_le_lot_detecte`, une seule redaction, AC 2).

Quatre niveaux:

* **l'equivalence des deux voies** (AC 1): sur le meme scan, `scan` et
  `scan detect` + `scan-write` produisent les memes artefacts -- memes noms de
  frames, memes octets, meme manifest (les exclusions d'horodatage sont
  enumerees nominativement, et la liste est VIDE: le manifest de scan ne porte
  aucun champ d'horodatage, ce que le test verifie pour que l'apparition d'un
  tel champ oblige a le nommer ici);
* **la completude annoncee avant toute ecriture** (AC 4, FR7);
* **les refus nommes** (AC 5): introuvable, corrompu, pas une previz de scan,
  etat inattendu, document anterieur, source manquante, source remplacee a
  dimensions egales (condensat) -- zero ecriture, verifie au compte de
  fichiers (modele V3.a);
* **les gardes AR2 des la naissance** (AC 6) et les frontieres dures (AC 7).

Regle des fabriques (CLAUDE.md), appliquee nommement: les lots portent des
pages distinguables (timecodes et `page_index` differents, jamais un
remplissage uniforme -- les planches de `app.build_page` peignent quatre
couleurs de frame differentes), au moins une page est posee dans le desordre
(`page_index != read_rank`), les assertions d'appariement page -> frames sont
nominatives (par `page_index` et timecode, via les slots du payload), et la
cible est placee hors premiere position: deux documents de detection
coexistent et l'ecriture comme l'annonce visent le SECOND.
"""

from __future__ import annotations

import ast
import inspect
import json
import sys
import textwrap
from pathlib import Path

import cv2
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mixed_media_utility import (  # noqa: E402
    cli,
    scan_output_frames,
    scan_previz,
    scan_write,
)
from mixed_media_utility.io import project_layout  # noqa: E402

import test_scan_calibration_application as app  # noqa: E402
import test_scan_manifest as scan_fixtures  # noqa: E402
import test_scan_previz as previz_fixtures  # noqa: E402

#: **Le code d'un lot TROUE ou INCOMPLET, depuis la story 11.4c** (lot V2,
#: AC 9.1 et AC 9.3). Les trois sites qui le portent ci-dessous ecrivent tous
#: un lot dont une planche manque ou dont le QR est efface: la passe ecrit des
#: mires, la persistance emet `FRAMES_SYNTHETIQUES_PRESENTES` et
#: `LOT_INCOMPLET`, et l'inventaire atteint desormais le code de sortie.
#:
#: **Deux d'entre eux mesurent l'AC 9.6 en bande**: `mmu scan` et
#: `mmu scan write`, sur le meme etat de lot, rendent le **meme** code -- ils
#: le rendaient deja tous les deux `0`, ils rendent desormais tous les deux
#: celui-ci, et c'est la meme redaction du verdict qui l'ecrit.
#:
#: Valeur ecrite en clair, jamais lue de `scan_write.CODE_SUCCES_PARTIEL`: lire
#: la constante que l'on mesure serait le test tautologique de la story 5.9.
LOT_INCOMPLET_MAIS_ECRIT = 4


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


def run_write(project_dir: Path, detection: Path, *args: str) -> int:
    return cli.main([
        cli.SCAN_WRITE_COMMAND, "--project", str(project_dir),
        "--detection", str(detection), *args,
    ])


def _detection_documents(project_dir: Path, ingest_slug: str) -> list[Path]:
    return sorted(
        (project_dir / project_layout.SCANS_DIRNAME / ingest_slug
         / "detections").glob("*.json")
    )


def _manifest(project_dir: Path) -> dict:
    return json.loads((project_dir / "project.json").read_text(encoding="utf-8"))


def _frame_files(project_dir: Path) -> list[Path]:
    """Toutes les frames ecrites du projet -- la mesure V3.a du zero ecriture."""
    output_dir = project_dir / project_layout.OUTPUT_FRAMES_DIRNAME
    if not output_dir.exists():
        return []
    return sorted(p for p in output_dir.rglob("*") if p.is_file())


def _lot_desordonne(tmp_path: Path, *, name: str) -> tuple[Path, Path, list]:
    """Deux planches posees dans l'ordre INVERSE de leurs `page_index`.

    `payloads[0]` porte `page_index=0`, `payloads[1]` porte `page_index=1`;
    poser la seconde en premier rend `read_rank != page_index` pour les deux
    pages -- le desordre exige par la regle des fabriques (mutants M33/M25).
    """
    payloads = app.lot_payloads(sheet_count=2, with_calibration=False)
    folder = app.write_scan_folder(
        tmp_path / name,
        [(payloads[1], app.PRESSES_DU_TIRAGE[0]),
         (payloads[0], app.PRESSES_DU_TIRAGE[1])],
    )
    return tmp_path / f"projet-{name}", folder, payloads


def _detect_puis_document(project_dir: Path, folder: Path, slug: str) -> Path:
    assert run_detect(project_dir, folder) == 0
    documents = _detection_documents(project_dir, slug)
    assert len(documents) == 1, documents
    return documents[0]


def _timecodes_du_payload(payload: dict) -> set[str]:
    return {slot["frame_timecode"] for slot in payload["slots"]}


# ---------------------------------------------------------------------------
# AC 1 -- les deux voies produisent les memes artefacts sur le meme scan
# ---------------------------------------------------------------------------

#: Question ouverte 4 (proposition appliquee): les exclusions d'horodatage de
#: la comparaison des deux voies sont enumerees NOMINATIVEMENT -- et la liste
#: est vide, parce que le manifest de scan (`persist_scan`) ne porte aucun
#: champ d'horodatage. Le test qui suit le verifie: si un tel champ apparait
#: un jour, la comparaison casse et son nom doit etre ajoute ICI, jamais dans
#: un filtre generique « tout ce qui ressemble a une date ».
HORODATAGES_EXCLUS_DU_MANIFEST: tuple[str, ...] = ()


def test_les_deux_voies_produisent_les_memes_artefacts_sur_le_meme_scan(
    tmp_path,
) -> None:
    """Le coeur de l'AC 1, mesure de l'epic: `scan` dans un projet, `scan
    detect` puis `scan-write` dans un second projet identique -- memes noms de
    frames, memes octets, meme manifest champ par champ.

    Meme nom de dossier de scan des deux cotes ('lot'): `scans_dir` et les
    locators, qui l'embarquent, restent identiques, donc la comparaison porte
    sur les artefacts entiers et pas un sous-ensemble.

    Le lot est desordonne (page_index inverse de read_rank sur les deux
    pages) et ses planches sont distinguables (quatre couleurs de zone, deux
    presses differentes): une permutation d'appariement changerait les octets
    compares.
    """
    payloads = app.lot_payloads(sheet_count=2, with_calibration=False)
    ordered = [(payloads[1], app.PRESSES_DU_TIRAGE[0]),
               (payloads[0], app.PRESSES_DU_TIRAGE[1])]
    folder_scan = app.write_scan_folder(tmp_path / "a" / "lot", ordered)
    folder_write = app.write_scan_folder(tmp_path / "b" / "lot", ordered)
    projet_scan = tmp_path / "projet-scan"
    projet_write = tmp_path / "projet-write"

    assert run_scan(projet_scan, folder_scan) == 0
    document = _detect_puis_document(projet_write, folder_write, "lot")
    assert run_write(projet_write, document) == 0

    # Memes noms de fichiers sous output-frames/<slug-de-lot>/ -- et memes
    # octets: le chemin de pixels est identique par construction, le
    # durcissement est permis par la fiche.
    frames_scan = _frame_files(projet_scan)
    frames_write = _frame_files(projet_write)
    noms_scan = [f.relative_to(projet_scan) for f in frames_scan]
    noms_write = [f.relative_to(projet_write) for f in frames_write]
    assert noms_scan == noms_write
    assert len(noms_scan) > 0
    for gauche, droite in zip(frames_scan, frames_write):
        assert gauche.read_bytes() == droite.read_bytes(), gauche.name

    # Appariement page -> frames nominatif (regle des fabriques): chaque
    # `page_index` retrouve exactement les timecodes de SES slots dans les
    # noms de frames -- jamais un simple cardinal.
    noms_ecrits = {f.name for f in frames_write}
    for payload in payloads:
        for timecode in _timecodes_du_payload(payload):
            attendu = f"scan_{payload['lot_id']}_{timecode.replace(':', '-')}.tiff"
            assert attendu in noms_ecrits, (payload["page_index"], timecode)

    # Meme manifest, champ par champ. Les exclusions d'horodatage sont
    # enumerees nominativement -- liste vide, et le test le PROUVE: aucune cle
    # du manifest ne porte de date.
    manifest_scan = _manifest(projet_scan)
    manifest_write = _manifest(projet_write)
    for exclu in HORODATAGES_EXCLUS_DU_MANIFEST:
        manifest_scan.pop(exclu, None)
        manifest_write.pop(exclu, None)
    assert manifest_scan == manifest_write

    # Familles de valeurs assertees nominativement (EPIC5-ARB-39): identite,
    # cardinaux, statuts et motifs de calibration, mires.
    lot_scan = manifest_scan["lots"][0]
    lot_write = manifest_write["lots"][0]
    for champ in ("lot_id", "rush_id", "template_id", "state",
                  "expected_frame_count", "reconstructed_frame_count",
                  "synthetic_frame_count", "synthetic_frames",
                  "timecode_base_fps", "gamut_map_id", "patch_preset_id"):
        assert lot_scan[champ] == lot_write[champ], champ
    assert (manifest_scan["color"]["color_calibration_status"]
            == manifest_write["color"]["color_calibration_status"])
    assert (manifest_scan["reconstruction"]["page_calibration_results"]
            == manifest_write["reconstruction"]["page_calibration_results"])


def test_le_second_temps_est_un_vrai_second_temps(tmp_path, capsys) -> None:
    """`scan detect`, fin d'invocation, puis l'ecriture dans une invocation
    separee (deux `cli.main` distincts, aucun etat partage hors disque):
    frames ecrites, manifest declare, code 0."""
    project_dir, folder, payloads = _lot_desordonne(tmp_path, name="second-temps")

    document = _detect_puis_document(project_dir, folder, "second-temps")
    assert not (project_dir / "project.json").exists()
    assert _frame_files(project_dir) == []

    assert run_write(project_dir, document) == 0

    frames = _frame_files(project_dir)
    assert len(frames) == 8  # 2 planches x 4 slots
    manifest = _manifest(project_dir)
    assert manifest["lots"][0]["lot_id"] == payloads[0]["lot_id"]
    # Le document de detection reste INTACT apres ecriture (question ouverte
    # 2): ni modifie, ni supprime, ni double d'un document `reconstructed`.
    documents = _detection_documents(project_dir, "second-temps")
    assert documents == [document]
    relu = json.loads(document.read_text(encoding="utf-8"))
    assert relu["state"] == scan_previz.SCAN_PREVIZ_STATE_DETECTED


def test_l_ecriture_vise_le_second_document_jamais_le_premier(tmp_path) -> None:
    """Regle des fabriques, cible hors premiere position: deux documents de
    detection (deux lots distinguables) coexistent dans le projet, l'ecriture
    vise le SECOND, et les frames ecrites sont celles de SON lot -- verifie
    nominativement par lot_id et timecodes."""
    payloads_a = app.lot_payloads(sheet_count=2, with_calibration=False)
    payloads_b = app.lot_payloads(sheet_count=2, with_calibration=False,
                                  rush_id="rush-002")
    assert payloads_a[0]["lot_id"] != payloads_b[0]["lot_id"]
    folder_a = app.write_scan_folder(
        tmp_path / "lot-a",
        [(payloads_a[0], app.PRESSES_DU_TIRAGE[0]),
         (payloads_a[1], app.PRESSES_DU_TIRAGE[1])])
    folder_b = app.write_scan_folder(
        tmp_path / "lot-b",
        [(payloads_b[1], app.PRESSES_DU_TIRAGE[0]),
         (payloads_b[0], app.PRESSES_DU_TIRAGE[1])])
    project_dir = tmp_path / "projet-deux-lots"

    document_a = _detect_puis_document(project_dir, folder_a, "lot-a")
    document_b = _detect_puis_document(project_dir, folder_b, "lot-b")
    assert document_a != document_b

    assert run_write(project_dir, document_b) == 0

    manifest = _manifest(project_dir)
    lots = {lot["lot_id"]: lot for lot in manifest["lots"]}
    assert payloads_b[0]["lot_id"] in lots
    assert payloads_a[0]["lot_id"] not in lots
    frames = {f.name for f in _frame_files(project_dir)}
    for payload in payloads_b:
        for timecode in _timecodes_du_payload(payload):
            attendu = f"scan_{payload['lot_id']}_{timecode.replace(':', '-')}.tiff"
            assert attendu in frames, (payload["page_index"], timecode)
    # Et aucune frame du lot A: l'ecriture n'a pas vise le premier document.
    assert not any(payloads_a[0]["lot_id"] in nom for nom in frames)


def test_un_lot_troue_ecrit_comme_la_voie_historique(tmp_path) -> None:
    """Une page jamais identifiee entre deux pages identifiees: memes
    `synthetic_frames` au manifest, meme cardinal, memes frames -- l'egalite
    est mesuree entre les deux voies, famille par famille."""
    payloads = app.lot_payloads(sheet_count=3, with_calibration=False)

    folder_scan = tmp_path / "a" / "lot"
    folder_write = tmp_path / "b" / "lot"
    for folder in (folder_scan, folder_write):
        folder.mkdir(parents=True)
        for rank, (payload, press) in enumerate([
            (payloads[0], app.PRESSES_DU_TIRAGE[0]),
            (payloads[1], app.PRESSES_DU_TIRAGE[1]),
            (payloads[2], app.PRESSES_DU_TIRAGE[0]),
        ], start=1):
            page = app.build_page(payload, press=press)
            if payload["page_index"] == 1:
                _erase_qr(page, payload)
            cv2.imwrite(str(folder / f"page_{rank:02d}.tiff"), page)

    projet_scan = tmp_path / "projet-scan-troue"
    projet_write = tmp_path / "projet-write-troue"
    assert run_scan(projet_scan, folder_scan) == LOT_INCOMPLET_MAIS_ECRIT
    document = _detect_puis_document(projet_write, folder_write, "lot")
    assert run_write(projet_write, document) == LOT_INCOMPLET_MAIS_ECRIT

    lot_scan = _manifest(projet_scan)["lots"][0]
    lot_write = _manifest(projet_write)["lots"][0]
    assert lot_write["synthetic_frames"] == lot_scan["synthetic_frames"]
    assert lot_write["synthetic_frame_count"] == lot_scan["synthetic_frame_count"]
    assert lot_write["state"] == lot_scan["state"]
    noms_scan = [f.name for f in _frame_files(projet_scan)]
    noms_write = [f.name for f in _frame_files(projet_write)]
    assert noms_scan == noms_write


def test_une_planche_SANS_QR_AU_MILIEU_n_empeche_PAS_les_SUIVANTES(tmp_path) -> None:
    """**Le mutant `continue` -> `break` de la branche `payload is None`**
    (revue de la vague 3, couche 2, finding `C1`, volet `a`).

    `_scanned_pages_for_output` (`scan_write.py:842`) traite une planche dont le
    QR n'a jamais ete decode en posant une `ScannedPage(payload=None)` puis en
    CONTINUANT. Un `break` a la place ferait abandonner toutes les planches
    suivantes -- ni frames, ni mires, ni declaration --, et 288 tests restaient
    verts.

    **La voie compte, et elle a ete mesuree plutot que supposee.** Sur la voie
    `mmu scan` (vrac), une planche au QR illisible part au **reliquat** au tri
    (`reliquat-payload-refuse`) : elle n'atteint jamais cette branche. C'est la
    voie `mmu scan write`, qui recoit un document de detection ou la planche
    appartient deja au lot, qui l'atteint. Un premier banc ecrit sur la
    mauvaise voie mesurait donc autre chose que ce qu'il croyait.

    **La mesure porte sur la planche qui SUIT**, jamais sur celle qui echoue :
    c'est la seule facon de distinguer « en echec » d'« abandonnee ». Trois
    planches, le QR efface sur celle du MILIEU, l'assertion sur la troisieme.
    """
    payloads = app.lot_payloads(sheet_count=3, with_calibration=False)
    folder = tmp_path / "lot"
    folder.mkdir(parents=True)
    for rang, payload in enumerate(payloads, start=1):
        page = app.build_page(payload, press=app.PRESSES_DU_TIRAGE[0])
        if payload["page_index"] == 1:
            _erase_qr(page, payload)
        cv2.imwrite(str(folder / f"page_{rang:02d}.tiff"), page)

    projet = tmp_path / "projet"
    document = _detect_puis_document(projet, folder, "lot")
    assert run_write(projet, document) == LOT_INCOMPLET_MAIS_ECRIT

    lot = _manifest(projet)["lots"][0]
    noms = sorted(f.name for f in _frame_files(projet))
    # Trois planches a quatre emplacements : douze frames attendues. La planche
    # du milieu n'en fournit aucune vraie ; les DEUX autres, si.
    assert lot["reconstructed_frame_count"] == 8, (
        "les frames de la planche qui SUIT la planche sans QR doivent "
        "exister : un `break` a la place du `continue` les ferait "
        f"disparaitre -- obtenu {lot['reconstructed_frame_count']} : {noms}")
    # Et le volet qui distingue « en echec » d'« abandonnee » : les frames de
    # la TROISIEME planche portent ses propres timecodes.
    attendus = _timecodes_du_payload(payloads[2])
    for timecode in attendus:
        assert any(timecode.replace(":", "-") in nom for nom in noms), (
            f"la troisieme planche a perdu son emplacement {timecode} : {noms}")


def test_une_planche_SANS_PAYLOAD_ne_PRECEDE_JAMAIS_une_planche_identifiee(
        tmp_path, monkeypatch) -> None:
    """**L'invariant d'ordre dont depend une equivalence, et il n'etait garde
    par rien** (revue de la vague 3, couche 2, finding `C1`, volet `a`).

    Le mutant `continue` -> `break` sur la branche `payload is None` de
    `_scanned_pages_for_output` (`scan_write.py:842`) **survit**, et il survit
    pour une bonne raison : mesure faite, une planche sans payload arrive
    **toujours en derniere position** de `report.pages` -- les planches
    identifiees d'abord, les refusees ensuite. Rien ne la suit, donc `break` et
    `continue` y sont indiscernables. C'est une **equivalence**, pas un trou.

    **Mais l'equivalence est CONDITIONNELLE, et c'est ce que ce banc tient.**
    Elle ne vient pas de la boucle : elle vient d'un ordre pose ailleurs, en
    amont, et cet ordre a un NOM et un arbitrage.
    `scan_detect.pages_du_lot` trie par `_cle_de_planche_du_lot`
    (`scan_detect.py:1221`) sous `EPIC7-ARB-77` -- « on range les pages selon
    l'ordre indique dans le QR » --, et sa docstring dit la clause qui nous
    interesse : « **Une page sans numero de planche passe en queue.** Le QR ne
    l'a pas livree, elle ne peut pas se ranger entre deux planches
    numerotees. »

    Cette regle a ete posee pour une raison d'INTERFACE (le chutier et la
    galerie montraient deux ordres du meme lot), pas pour proteger cette
    boucle-ci. Rien ne dit aux deux endroits qu'ils dependent l'un de l'autre :
    le jour ou l'ordre changerait -- un tri par rang de lecture, par exemple,
    qui est litteralement ce que `EPIC7-ARB-77` a remplace --, le `break`
    cesserait d'etre equivalent et ferait **disparaitre en silence** toutes les
    planches suivantes. Le defaut serait alors dans une boucle que personne
    n'aurait touchee.

    Ce banc ne mesure donc pas la boucle, il mesure **ce dont la boucle
    depend** : dans `report.pages`, aucune page sans payload ne precede une
    page qui en a un. La fabrique pose la planche muette au MILIEU des
    fichiers, precisement pour que l'ordre d'entree ne suffise pas a rendre
    l'assertion vraie.
    """
    vus: list[list[object]] = []
    originel = scan_write._scanned_pages_for_output

    def espion(project_dir, report, dpi, *args, **kwargs):
        vus.append([page.payload for page in report.pages])
        return originel(project_dir, report, dpi, *args, **kwargs)

    monkeypatch.setattr(scan_write, "_scanned_pages_for_output", espion)

    payloads = app.lot_payloads(sheet_count=3, with_calibration=False)
    folder = tmp_path / "lot"
    folder.mkdir(parents=True)
    for rang, payload in enumerate(payloads, start=1):
        page = app.build_page(payload, press=app.PRESSES_DU_TIRAGE[0])
        if payload["page_index"] == 1:      # la planche MUETTE est AU MILIEU
            _erase_qr(page, payload)
        cv2.imwrite(str(folder / f"page_{rang:02d}.tiff"), page)

    projet = tmp_path / "projet"
    document = _detect_puis_document(projet, folder, "lot")
    assert run_write(projet, document) == LOT_INCOMPLET_MAIS_ECRIT

    assert vus, "la boucle de sortie n'a pas ete atteinte"
    for ordre in vus:
        assert any(p is None for p in ordre), (
            "la fabrique doit produire une planche SANS payload, sinon "
            f"l'invariant n'est pas mis a l'epreuve : {ordre}")
        premier_muet = next(r for r, p in enumerate(ordre) if p is None)
        assert all(p is None for p in ordre[premier_muet:]), (
            "une planche identifiee SUIT une planche muette : l'equivalence "
            "du mutant `continue` -> `break` de `scan_write.py:842` tombe, et "
            f"la boucle perd les planches suivantes -- ordre : {ordre}")


def _erase_qr(page, payload: dict) -> None:
    """Meme recette que `test_scan_detect_command._erase_qr`."""
    from mixed_media_utility import page_templates, patch_presets, qr_codes
    page_layout = patch_presets.resolve_page_layout(
        payload["template_id"], payload["page_role"])
    zone = next(z for z in page_layout.reserved_zones_mm if z["name"] == "qr_zone")
    side = int(round(qr_codes.QR_PRINT_SIZE_TARGET_MM / 25.4 * app.DPI))
    qr_x, qr_y = page_templates.mm_to_px(zone["x"], zone["y"], app.DPI)
    page[qr_y:qr_y + side, qr_x:qr_x + side] = 255


def _noms_appeles(fonction) -> set[str]:
    """Les noms simples appeles dans le corps de `fonction` (balayage AST)."""
    arbre = ast.parse(textwrap.dedent(inspect.getsource(fonction)))
    appels = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Call):
            if isinstance(noeud.func, ast.Attribute):
                appels.add(noeud.func.attr)
            elif isinstance(noeud.func, ast.Name):
                appels.add(noeud.func.id)
    return appels


def test_l_ecriture_ne_refait_jamais_la_detection() -> None:
    """Frontiere negative de l'AC 1 (modele
    `test_detect_n_appelle_ni_ecriture_de_frames_ni_manifest`): balayage AST
    -- zero appel de detection ou d'ingestion. Le document est consomme tel
    quel.

    **Story 11.6 (lot B): le balayage porte sur les DEUX etages.** La moitie
    HAUTE du temps 2 -- lecture du document, refus nommes, condensat,
    adaptateurs -- a quitte `cli.scan_write_command` pour le point d'entree de
    coeur `scan_write.ecrire_depuis_le_document` (`EPIC11-ARB-129`). Ne
    balayer que la commande laisserait desormais la redetection entrer par
    l'etage qui fait le travail: la frontiere suit ce qu'elle mesure.
    """
    appels = (_noms_appeles(cli.scan_write_command)
              | _noms_appeles(scan_write.ecrire_depuis_le_document))
    for interdit in ("detect_lot_pages", "ingest_scan_lot", "decode_qr_image",
                     "resolve_page_identity", "compute_page_homography"):
        assert interdit not in appels, sorted(appels)
    # Temoin positif: la commande passe bien par le point d'entree de coeur du
    # temps 2, qui passe lui-meme par la moitie aval partagee.
    assert "ecrire_depuis_le_document" in _noms_appeles(cli.scan_write_command)
    assert "ecrire_le_lot_detecte" in _noms_appeles(
        scan_write.ecrire_depuis_le_document)


# ---------------------------------------------------------------------------
# AC 2 -- une seule redaction de la moitie aval
# ---------------------------------------------------------------------------


def _appels_de(nom_de_fonction: str) -> set[str]:
    """Les expressions appelees dans le corps de cette fonction du chemin de scan
    (modele `test_bascule_calibration_pile_seule._appels_de`).

    **Story 11.4b (lot S1) : le balayage porte sur les DEUX fichiers.** La
    moitie aval a suivi l'orchestration dans le module de coeur `scan_write`,
    comme la moitie amont avait suivi `scan_detect` en 7.3 ; la chercher dans
    `cli.py` seul ferait echouer la garde sans qu'une seule redaction n'ait
    disparu. La fonction reste unique sur les deux fichiers reunis, et c'est
    l'assertion de cardinal ci-dessous qui le mesure.
    """
    racine = REPO_ROOT / "src" / "mixed_media_utility"
    corps = []
    for fichier in ("cli.py", "scan_write.py"):
        arbre = ast.parse(fichier and (racine / fichier).read_text(encoding="utf-8"))
        corps += [n for n in ast.walk(arbre)
                  if isinstance(n, ast.FunctionDef) and n.name == nom_de_fonction]
    assert len(corps) == 1, (nom_de_fonction, len(corps))
    return {ast.unparse(n.func) for n in ast.walk(corps[0]) if isinstance(n, ast.Call)}


def test_les_deux_commandes_ecrivent_par_la_meme_fonction_aval() -> None:
    """Verrou positif de l'AC 2 (modele « il n'existe qu'une redaction du
    geste »): `scan_command` ET `scan_write_command` appellent LA MEME
    fonction aval, et aucune des deux ne redige d'ecriture de frames ou de
    manifest a elle."""
    assert "_ecrire_le_lot_detecte" in _appels_de("scan_command")
    # **Story 11.6 (lot B): un etage de plus, et une seule redaction quand
    # meme.** `scan_write_command` n'appelle plus l'aval directement: elle
    # appelle le point d'entree de coeur du temps 2, qui l'appelle. Le verrou
    # mesure donc la chaine entiere -- si l'un des deux maillons se mettait a
    # rediger son ecriture a lui, l'assertion de cardinal de `_appels_de` et
    # les deux ensembles vides ci-dessous le diraient.
    assert "scan_write.ecrire_depuis_le_document" in _appels_de(
        "scan_write_command")
    assert "ecrire_le_lot_detecte" in _appels_de("ecrire_depuis_le_document")
    for commande in ("scan_command", "scan_write_command",
                     "ecrire_depuis_le_document"):
        ecritures = {appel for appel in _appels_de(commande)
                     if "write_lot_output_frames" in appel
                     or "persist_scan" in appel}
        assert ecritures == set(), (commande, sorted(ecritures))
    # Temoin positif: c'est bien l'aval qui ecrit. Story 11.4b (lot S1): l'aval
    # est le point d'entree de coeur `scan_write.ecrire_le_lot_detecte`, dont
    # `_ecrire_le_lot_detecte` n'est plus que l'enveloppeur -- une seule
    # redaction du geste, comme avant, un etage plus bas.
    aval = _appels_de("ecrire_le_lot_detecte")
    assert any("write_lot_output_frames" in appel for appel in aval)
    assert any("persist_scan" in appel for appel in aval)


def test_la_suite_scan_ne_perd_pas_la_bascule_ni_le_try_ar2() -> None:
    """Les invariants intacts restent intacts (AC 2, frontiere): la bascule
    calibration reste dans l'amont de `scan_command`, et le dernier statement
    de `scan_command` reste le `Try` d'AR2."""
    assert "_consigner_le_profil_de_chaine" in _appels_de("scan_command")
    arbre = ast.parse(inspect.getsource(cli.scan_command))
    dernier = arbre.body[0].body[-1]
    assert isinstance(dernier, ast.Try), type(dernier)
    noms = [h.type.id for h in dernier.handlers]
    assert noms == ["KeyboardInterrupt", "OSError"], noms


# ---------------------------------------------------------------------------
# AC 4 -- la completude est annoncee AVANT toute ecriture (FR7)
# ---------------------------------------------------------------------------


def _lot_incomplet(tmp_path: Path, *, name: str, rush_id: str,
                   present_indexes: list[int], page_count: int) -> tuple[Path, Path, str]:
    """Un lot dont le cardinal declare depasse ce qui est pose sur la vitre."""
    payloads = [
        scan_fixtures.make_payload(
            rush_id=rush_id, page_index=index, page_count=page_count,
            template_id=app.TEMPLATE, patch_preset_id=app.PRESET,
            fps_target=5.0,
        )
        for index in present_indexes
    ]
    folder = app.write_scan_folder(
        tmp_path / name,
        [(payload, app.PRESSES_DU_TIRAGE[0]) for payload in payloads],
    )
    return tmp_path / f"projet-{name}", folder, payloads[0]["lot_id"]


def test_un_lot_incomplet_est_annonce_puis_ecrit_quand_meme(tmp_path, capsys) -> None:
    """L'annonce porte cardinaux et index manquants nommes, ET les frames sont
    ensuite ecrites: l'annonce n'est pas un refus."""
    project_dir, folder, lot_id = _lot_incomplet(
        tmp_path, name="incomplet", rush_id="rush-001",
        present_indexes=[0, 2], page_count=4)
    document = _detect_puis_document(project_dir, folder, "incomplet")
    capsys.readouterr()

    assert run_write(project_dir, document) == LOT_INCOMPLET_MAIS_ECRIT

    sortie = capsys.readouterr().out
    assert f"Completude du lot {lot_id}" in sortie
    assert "2 page(s) identifiee(s) sur 4 attendue(s)" in sortie
    assert "manquante(s) (page_index): 1, 3" in sortie
    assert len(_frame_files(project_dir)) > 0


def test_l_annonce_precede_la_premiere_ecriture(tmp_path, capsys, monkeypatch) -> None:
    """La clause « avant » se mesure: `write_lot_output_frames` substitue par
    un espion qui leve -- l'annonce est DEJA dans la sortie au moment de
    l'echec, et aucun fichier de frame n'existe."""
    project_dir, folder, lot_id = _lot_incomplet(
        tmp_path, name="ordre", rush_id="rush-001",
        present_indexes=[0, 2], page_count=4)
    document = _detect_puis_document(project_dir, folder, "ordre")
    capsys.readouterr()

    def _espion(*args, **kwargs):
        raise scan_output_frames.ScanOutputError("espion: ecriture atteinte")

    monkeypatch.setattr(
        cli.scan_output_frames, "write_lot_output_frames", _espion)
    assert run_write(project_dir, document) == 1

    sortie = capsys.readouterr()
    assert f"Completude du lot {lot_id}" in sortie.out
    assert "manquante(s) (page_index): 1, 3" in sortie.out
    assert _frame_files(project_dir) == []


def test_l_annonce_vise_le_second_document_et_ses_index_a_lui(tmp_path, capsys) -> None:
    """Regle des fabriques: deux documents presents (deux lots aux trous
    DIFFERENTS), l'annonce vise le second et nomme SES index manquants."""
    projet_a, folder_a, _ = _lot_incomplet(
        tmp_path, name="annonce", rush_id="rush-001",
        present_indexes=[0, 1], page_count=3)
    del projet_a  # meme projet pour les deux lots
    project_dir = tmp_path / "projet-annonce-double"
    document_a = _detect_puis_document(project_dir, folder_a, "annonce")
    _, folder_b, lot_b = _lot_incomplet(
        tmp_path, name="annonce-b", rush_id="rush-002",
        present_indexes=[0, 3], page_count=5)
    document_b = _detect_puis_document(project_dir, folder_b, "annonce-b")
    assert document_a != document_b
    capsys.readouterr()

    assert run_write(project_dir, document_b) == LOT_INCOMPLET_MAIS_ECRIT

    sortie = capsys.readouterr().out
    assert f"Completude du lot {lot_b}" in sortie
    assert "2 page(s) identifiee(s) sur 5 attendue(s)" in sortie
    # Les index manquants du lot B (1, 2, 4) -- pas ceux du lot A (2).
    assert "manquante(s) (page_index): 1, 2, 4" in sortie


# ---------------------------------------------------------------------------
# AC 5 -- refus nommes: introuvable, corrompu, etat inattendu, perime
# ---------------------------------------------------------------------------


def test_un_chemin_de_document_inexistant_est_refuse_sans_ecrire(
    tmp_path, capsys,
) -> None:
    project_dir = tmp_path / "projet-absent"
    absent = tmp_path / "n-existe-pas.json"

    assert run_write(project_dir, absent) == 1

    erreur = capsys.readouterr().err
    assert "introuvable" in erreur
    assert str(absent) in erreur
    assert _frame_files(project_dir) == []
    assert not (project_dir / "project.json").exists()


def test_un_json_invalide_est_refuse_nommement(tmp_path, capsys) -> None:
    project_dir = tmp_path / "projet-corrompu"
    corrompu = tmp_path / "corrompu.json"
    corrompu.write_text('{"previz_schema_version": "previz-1",', encoding="utf-8")

    assert run_write(project_dir, corrompu) == 1

    erreur = capsys.readouterr().err
    assert "JSON invalide" in erreur
    assert _frame_files(project_dir) == []


def test_un_json_valide_qui_n_est_pas_un_scan_previz_est_refuse(
    tmp_path, capsys,
) -> None:
    """Via le lecteur de l'AC 3: un objet JSON quelconque, et un document d'un
    autre kind, sont tous deux refuses nommement."""
    project_dir = tmp_path / "projet-pas-previz"
    quelconque = tmp_path / "quelconque.json"
    quelconque.write_text('{"bonjour": "monde"}', encoding="utf-8")
    assert run_write(project_dir, quelconque) == 1
    assert "n'est pas un document de detection exploitable" in (
        capsys.readouterr().err)

    autre_kind = tmp_path / "autre-kind.json"
    document = json.loads(previz_fixtures.rendered(previz_fixtures.build()))
    document["kind"] = "extraction"
    autre_kind.write_text(json.dumps(document), encoding="utf-8")
    assert run_write(project_dir, autre_kind) == 1
    assert "previz de scan" in capsys.readouterr().err
    assert _frame_files(project_dir) == []


def test_un_document_reconstructed_est_refuse_par_son_etat(tmp_path, capsys) -> None:
    """L'ecriture ne consomme que l'etat « detection faite, aucune frame
    ecrite »: un `reconstructed` fabrique (valide par le lecteur) est refuse
    sur l'etat."""
    project_dir = tmp_path / "projet-etat"
    reconstruit = tmp_path / "reconstruit.json"
    reconstruit.write_text(
        previz_fixtures.rendered(previz_fixtures.build_reconstructed()),
        encoding="utf-8")

    assert run_write(project_dir, reconstruit) == 1

    erreur = capsys.readouterr().err
    assert "'reconstructed'" in erreur
    assert "'detected'" in erreur
    assert _frame_files(project_dir) == []


def test_un_document_anterieur_a_5_26_est_refuse_vers_scan_detect(
    tmp_path, capsys,
) -> None:
    """Un document tel que 5.25 en a produit (sans `payload` ni
    `source_digest`) est refuse nommement, avec le geste: relancer
    `scan detect` -- jamais une reconstitution devinee (NFR6)."""
    project_dir, folder, _ = _lot_desordonne(tmp_path, name="anterieur")
    document_path = _detect_puis_document(project_dir, folder, "anterieur")
    document = json.loads(document_path.read_text(encoding="utf-8"))
    for page in document["pages"]:
        page.pop("payload", None)
        page.pop("source_digest", None)
    anterieur = tmp_path / "anterieur.json"
    anterieur.write_text(json.dumps(document), encoding="utf-8")
    capsys.readouterr()

    assert run_write(project_dir, anterieur) == 1

    erreur = capsys.readouterr().err
    assert "anterieur" in erreur
    assert "detect" in erreur
    assert _frame_files(project_dir) == []


def test_un_document_sans_aucune_page_identifiee_est_refuse(tmp_path, capsys) -> None:
    """Finding [Review][Patch] 4: `scan_command` et `scan_detect_command`
    portent tous deux le garde-fou « aucune planche n'a livre son QR »
    (retour 0, aucune ecriture) ; `scan_write_command` n'en avait pas
    d'equivalent, et la boucle de refus des documents anterieurs a 5.26 ne le
    refermait pas -- une page mutique (`page_index` ET `payload` tous deux
    `None`) la traverse (elle porte un `source_digest`, donc n'est pas
    "anterieure"). Chemin mort aujourd'hui (`scan detect` ne persiste jamais
    un tel document): ce test le construit a la main pour figer le refus
    nomme plutot que de laisser la divergence silencieuse."""
    project_dir, folder, _ = _lot_desordonne(tmp_path, name="zero-identifiee")
    document_path = _detect_puis_document(project_dir, folder, "zero-identifiee")
    document = json.loads(document_path.read_text(encoding="utf-8"))
    for page in document["pages"]:
        # `source_digest` reste en place: seule la boucle de refus des
        # documents ANTERIEURS doit rester muette ici, c'est la garde neuve
        # (zero page identifiee) qui doit parler.
        del page["payload"]
        previz_fixtures._reecrire_le_page_index(page, None)
    muet = tmp_path / "zero-identifiee.json"
    muet.write_text(json.dumps(document), encoding="utf-8")
    capsys.readouterr()

    assert run_write(project_dir, muet) == 1

    erreur = capsys.readouterr().err
    assert "aucune page identifiee" in erreur
    assert _frame_files(project_dir) == []
    assert not (project_dir / "project.json").exists()


def test_une_source_remplacee_a_dimensions_egales_est_refusee_au_condensat(
    tmp_path, capsys,
) -> None:
    """L'AC 3 de l'epic, mot pour mot: entre detect et write, un fichier
    source est remplace par un autre de MEMES dimensions; l'ecriture refuse
    sur le condensat, le motif nomme la page et le fichier, aucune frame
    n'est ecrite (compte de fichiers, modele V3.a). Le symetrique -- sans
    alteration, la meme sequence ecrit -- prouve que la garde ne crie pas
    pour rien.

    Regle des fabriques: deux pages distinguables, seule la SECONDE lue est
    alteree -- le motif nomme la bonne page.
    """
    payloads = app.lot_payloads(sheet_count=2, with_calibration=False)
    ordered = [(payloads[1], app.PRESSES_DU_TIRAGE[0]),
               (payloads[0], app.PRESSES_DU_TIRAGE[1])]
    folder = app.write_scan_folder(tmp_path / "lot", ordered)
    folder_temoin = app.write_scan_folder(tmp_path / "temoin" / "lot", ordered)
    project_dir = tmp_path / "projet-perime"
    projet_temoin = tmp_path / "projet-temoin"

    document = _detect_puis_document(project_dir, folder, "lot")

    # Remplacement a dimensions egales: la SECONDE feuille lue (page_02,
    # rang de lecture 1, page_index 0) est reecrite avec une autre presse --
    # memes dimensions, meme profondeur, octets differents.
    altere = app.build_page(payloads[0], press=app.PRESSES_DU_TIRAGE[0])
    cible = project_dir / "scans" / "lot" / "page_02.tiff"
    assert cible.is_file()
    avant = cv2.imread(str(cible)).shape
    cv2.imwrite(str(cible), altere)
    assert cv2.imread(str(cible)).shape == avant
    capsys.readouterr()

    assert run_write(project_dir, document) == 1

    erreur = capsys.readouterr().err
    assert "perime" in erreur
    assert "rang de lecture 1" in erreur
    assert "page_02.tiff" in erreur
    assert _frame_files(project_dir) == []
    assert not (project_dir / "project.json").exists()

    # Le symetrique: sans alteration, la meme sequence detect -> write ecrit.
    document_temoin = _detect_puis_document(projet_temoin, folder_temoin, "lot")
    assert run_write(projet_temoin, document_temoin) == 0
    assert len(_frame_files(projet_temoin)) == 8


def test_une_source_manquante_est_refusee_avant_toute_ecriture(
    tmp_path, capsys,
) -> None:
    """Copie ingeree supprimee -> refus nomme, jamais un `FileNotFoundError`
    nu."""
    project_dir, folder, _ = _lot_desordonne(tmp_path, name="source-absente")
    document = _detect_puis_document(project_dir, folder, "source-absente")
    (project_dir / "scans" / "source-absente" / "page_01.tiff").unlink()
    capsys.readouterr()

    assert run_write(project_dir, document) == 1

    sortie = capsys.readouterr()
    assert "source manquant" in sortie.err
    assert "page_01.tiff" in sortie.err
    assert "Traceback" not in sortie.err
    assert _frame_files(project_dir) == []


# ---------------------------------------------------------------------------
# AC 6 -- AR2 des la naissance
# ---------------------------------------------------------------------------


def test_les_gardes_ar2_de_scan_write_sont_le_dernier_statement() -> None:
    """Modele exact de
    `test_les_gardes_ar2_sont_ajoutees_en_dernier_sans_reordonner_le_reste`:
    le dernier statement du corps est un `Try` dont les deux seuls
    gestionnaires sont `KeyboardInterrupt` puis `OSError`, dans cet ordre."""
    arbre = ast.parse(inspect.getsource(cli.scan_write_command))
    fonction = arbre.body[0]
    dernier = fonction.body[-1]
    assert isinstance(dernier, ast.Try), type(dernier)
    noms = [h.type.id for h in dernier.handlers]
    assert noms == ["KeyboardInterrupt", "OSError"], noms


def test_scan_write_keyboard_interrupt_rend_130_sans_trace(
    tmp_path, capsys, monkeypatch,
) -> None:
    project_dir, folder, _ = _lot_desordonne(tmp_path, name="ki-write")
    document = _detect_puis_document(project_dir, folder, "ki-write")

    def _interrompt(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli.scan_output_frames, "write_lot_output_frames", _interrompt)
    assert run_write(project_dir, document) == 130
    sortie = capsys.readouterr()
    assert "Interruption clavier" in sortie.out
    assert "scan-write" in sortie.out
    assert "Traceback" not in sortie.out
    assert "Traceback" not in sortie.err


def test_scan_write_oserror_rend_1_avec_message_actionnable(
    tmp_path, capsys, monkeypatch,
) -> None:
    project_dir, folder, _ = _lot_desordonne(tmp_path, name="os-write")
    document = _detect_puis_document(project_dir, folder, "os-write")

    def _echoue(*args, **kwargs):
        raise OSError("dossier de sortie non inscriptible (mesure de test)")

    monkeypatch.setattr(cli.scan_output_frames, "write_lot_output_frames", _echoue)
    assert run_write(project_dir, document) == 1
    sortie = capsys.readouterr()
    assert "Erreur" in sortie.err
    assert "espace" in sortie.err.lower() or "disque" in sortie.err.lower()
    assert "Traceback" not in sortie.out
    assert "Traceback" not in sortie.err


# ---------------------------------------------------------------------------
# AC 7 -- frontieres dures
# ---------------------------------------------------------------------------


def test_le_vocabulaire_des_codes_previz_ne_change_pas() -> None:
    """AC de frontiere de l'epic: egalite du tuple, aucun code ajoute, retire
    ni renomme."""
    assert scan_previz.SCAN_PREVIZ_WARNING_CODES == (
        "CALIBRATION_FAILED",
        "DPI_BELOW_QR_MINIMUM",
        "FOREIGN_MARKER_DETECTED",
        "GAMUT_CLIPPING_DETECTED",
        "LOT_INCOMPLETE",
        "PAGE_ASPECT_OUT_OF_TOLERANCE",
        "PAGE_QR_UNREADABLE",
        "PAGE_SCALE_OUT_OF_TOLERANCE",
        "SYNTHETIC_FRAME_WRITTEN",
        "TEMPLATE_FROM_MANIFEST_NOT_QR",
    )


def test_scan_write_ne_touche_aucun_champ_de_5_12_5_13_5_14() -> None:
    """Frontiere d'`EPIC7-ARB-49` (modele
    `test_detect_ne_touche_aucun_champ_de_5_12_5_13_5_14`): aucun champ de
    date de scan, discriminant de tirage ou suffixe de passe."""
    source = inspect.getsource(cli.scan_write_command)
    for interdit in ("scan_date", "tirage_discriminant", "pass_suffix",
                     "_pass2", "_take2"):
        assert interdit not in source, interdit


def test_scan_write_n_apprend_rien_du_vrac() -> None:
    """AC 13 de la story 5.24: `scan-write` est **inchange**.

    Le test qui vivait ici jusqu'au 2026-08-25 verifiait que le module de tri
    n'existait pas encore -- il a livre, donc son sujet a disparu et il est
    remplace, jamais simplement supprime. Ce qu'il gardait reellement, c'est la
    frontiere: cette commande consomme **un** document de detection et ne
    connait ni le tri, ni le vrac, ni la partition. Le rapport de tri est un
    document **separe**, et le document de detection ne recoit aucun champ pour
    le vrac.
    """
    source = inspect.getsource(cli.scan_write_command)
    for interdit in ("scan_sorting", "trier_les_pages", "partition", "vrac"):
        assert interdit not in source, interdit


def test_scan_write_expose_les_memes_options_d_ecriture_que_scan(capsys) -> None:
    """Les options d'ecriture sont lues sur les MEMES constantes que `scan`:
    l'ensemble exact des drapeaux de `scan-write`, mesure sur l'aide."""
    import re
    with pytest.raises(SystemExit):
        cli.main([cli.SCAN_WRITE_COMMAND, "--help"])
    sortie = capsys.readouterr().out
    drapeaux = set(re.findall(r"(?m)^  (--[a-z-]+)", sortie))
    attendu = {
        "--project", "--detection", "--overwrite",
        cli.CC_FLAG, cli.color_calibration.DIVERGENCE_BYPASS_FLAG,
        cli.color_calibration.RAW_OUTPUT_FLAG, cli.PROFILE_FLAG,
    }
    assert drapeaux == attendu, drapeaux
    # Et ni `--scan` ni `--dpi`: les deux vivent dans le document (question
    # ouverte 1 -- un requis-mais-ignore serait un reste inerte).
    assert "--scan" not in drapeaux
    assert "--dpi" not in drapeaux
