"""Tests du contrat de donnees de previz de scan (story 5.8).

Troisieme jumelle de `test_extraction_previz.py` (3.5) et `test_pdf_previz.py`
(4.9): purete AST, enveloppe `previz-1` reprise telle quelle avec
`kind = "scan"`, projection verbatim des cinq producteurs, serialisation
canonique deterministe, empreintes de peremption, vocabulaire ferme
d'avertissements.

Deux exigences structurent ce fichier, et elles ne se remplacent pas.

**Des sentinelles incoherentes** pour les tests unitaires: les entrees sont des
objets structurels (`SimpleNamespace`) faconnes comme les vrais producteurs, et
volontairement faux entre eux -- une echelle de 42, un residu negatif, un
rectangle de decoupe plus grand que la page. Si le module recalculait quoi que
ce soit, la sentinelle serait corrigee au lieu d'etre transportee (motif de
l'AC 2 de 3.5).

**Contre les vrais producteurs** pour l'integration (AC 12, action item 3 de la
retro Epic 4): le `LotOutputReport` vient du **vrai** `write_lot_output_frames`
apres ecriture sur disque, le plan de decoupe du **vrai**
`scan_crop.build_page_crop_plan`, le rapport d'ingestion du **vrai**
`scan_ingest.ingest_scan_lot` apres lecture d'un fichier image reel, et les
pages detectees sont de vraies instances de `scan_detection.DetectedPage` dont
la geometrie est resolue par le **vrai** `resolve_page_geometry`. C'est ce qui
fait tomber ces tests sur un renommage de champ chez n'importe lequel des cinq,
au lieu de laisser casser le premier consommateur reel en `AttributeError`
brute, tous tests verts.

Les vocabulaires fermes des producteurs sont importes **ici**, jamais recopies:
le module de production ne peut pas les importer (ils vivent tous dans des
modules qui tirent `cv2` ou `numpy`), donc c'est au test de confronter le
transport aux vraies valeurs.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import page_roles, previz_common, scan_previz
from mixed_media_utility.io.manifest import _iter_absolute_path_violations

MODULE_PATH = REPO_ROOT / "src" / "mixed_media_utility" / "scan_previz.py"
COMMON_MODULE_PATH = REPO_ROOT / "src" / "mixed_media_utility" / "previz_common.py"

GENERATED_AT = "2026-08-08T12:00:00Z"

SPE = scan_previz.ScanPrevizError


# ---------------------------------------------------------------------------
# Fabriques structurelles: des sentinelles volontairement incoherentes
# ---------------------------------------------------------------------------
#
# Aucune de ces valeurs n'est plausible ensemble: une page de 10 x 10 pixels
# portant un rectangle de decoupe de 3307 px de large, une echelle de 42, un
# residu negatif. C'est le point: le document doit les transporter telles
# quelles.


def make_ingested_page(**overrides):
    """Une page ingeree, **exactement** les champs que le protocole declare.

    Pas de `locator`: le module ne l'a jamais lu, et il ne le declare plus
    depuis la revue de 5.8. Une fabrique qui porterait un champ non declare
    ferait passer la suite entiere pour un fournisseur alternatif qui, lui,
    casserait.
    """
    page = SimpleNamespace(
        read_rank=0,
        scan_input_format="tiff",
        source_bit_depth=16,
        width_px=10,
        height_px=10,
        channels=3,
    )
    for key, value in overrides.items():
        setattr(page, key, value)
    return page


def make_ingest(**overrides):
    report = SimpleNamespace(
        # Volontairement **different** du `lot_id`: deux valeurs qui coincident
        # sur toutes les fixtures cachent une derivation fausse -- ici « le slug
        # d'ingestion se derive du lot_id », mutant survivant de la revue.
        ingest_slug="ingest-lot-a",
        scans_dir="scans/lot-a",
        declared_dpi=600,
        pages=(make_ingested_page(),),
        warnings=("DPI_BELOW_QR_MINIMUM",),
    )
    for key, value in overrides.items():
        setattr(report, key, value)
    return report


def make_detected_page(**overrides):
    page = SimpleNamespace(
        read_rank=0,
        status="ok",
        locator_source="scans/lot-a/p1.tif",
        locator_page_index=None,
        qr_status="decoded",
        template_id="tpl-a4-portrait-2f-v1",
        template_source="qr",
        project_id="proj-a",
        rush_id="rush-001",
        lot_id="lot-a",
        page_index=3,
        page_count=7,
        gamut_map_id="gamut-map-none-1",
        corner_centers=((0, 12.5, 13.5), (1, 999.25, -4.0)),
        foreign_markers=(SimpleNamespace(marker_id=77, role="reserved"),),
        homography=(1.5, 0.0, -2.0, 0.0, 1.5, 3.0, 0.0, 0.0, 1.0),
        page_size_px=(10, 10),
        scale=SimpleNamespace(scale_x=42.0, scale_y=0.5, residual_px=-7.25),
        frame_zones_px=(
            {"name": "frame_zone_1", "x": 826, "y": 1417, "width": 3307, "height": 1860},
        ),
        warnings=("PAGE_SCALE_OUT_OF_TOLERANCE",),
        refusal_reason=None,
        # Story 5.27: le code enumere accompagne la phrase, et une page acceptee
        # n'en porte aucun. La fabrique le declare pour la meme raison qu'elle
        # declare `refusal_reason` -- le protocole `DetectedPageLike` le lit
        # directement, sans repli.
        refusal_code=None,
    )
    for key, value in overrides.items():
        setattr(page, key, value)
    return page


def make_detection(pages=None, **overrides):
    report = SimpleNamespace(
        # Volontairement **different** du DPI declare a l'ingestion (600): les
        # deux peuvent diverger dans la vraie chaine -- 5.2 emet
        # `SCAN_DPI_DIFFERS_FROM_INGESTED` precisement pour ca --, et une
        # fixture qui leur donne la meme valeur ne fige pas leur distinction.
        scan_dpi=300,
        pages=(make_detected_page(),) if pages is None else tuple(pages),
        warnings=("TEMPLATE_FROM_MANIFEST_NOT_QR", "SCAN_DPI_DIFFERS_FROM_INGESTED"),
    )
    for key, value in overrides.items():
        setattr(report, key, value)
    return report


def make_crop_frame(slot_index: int = 0, **overrides):
    frame = SimpleNamespace(
        slot_index=slot_index,
        frame_timecode="00:00:00:00",
        zone_name="frame_zone_1",
        zone_rect_mm=(35.0, 60.0, 140.0, 78.75),
        image_rect_mm=(35.5, 60.5, 139.0, 77.75),
        crop_x_px=826,
        crop_y_px=1417,
        width_px=3307,
        height_px=1860,
    )
    for key, value in overrides.items():
        setattr(frame, key, value)
    return frame


def make_crop_plan(slot_index: int = 0, frames=None, **overrides):
    if frames is not None:
        return SimpleNamespace(frames=tuple(frames))
    return SimpleNamespace(frames=(make_crop_frame(slot_index, **overrides),))


def make_output_frame(**overrides):
    frame = SimpleNamespace(
        page_index=3,
        slot_index=0,
        path="output-frames/rush-001_5/scan_rush-001_5_00-00-00-00.tiff",
        synthetic=False,
        synthetic_reason=None,
    )
    for key, value in overrides.items():
        setattr(frame, key, value)
    return frame


def make_output_report(frames=None, **overrides):
    report = SimpleNamespace(
        output_dir="output-frames/rush-001_5",
        frames=(make_output_frame(),) if frames is None else tuple(frames),
        warnings=("SYNTHETIC_FRAME_WRITTEN",),
    )
    for key, value in overrides.items():
        setattr(report, key, value)
    return report


def build(**kwargs):
    defaults = dict(
        ingest=make_ingest(),
        detection=make_detection(),
        crop_plans={0: make_crop_plan()},
        generated_at_utc=GENERATED_AT,
        project_id="proj-a",
        rush_id="rush-001",
        lot_id="lot-a",
        template_id="tpl-a4-portrait-2f-v1",
        gamut_map_id="gamut-map-none-1",
        fps_target=5.0,
        target_colorspace="bt709",
        patch_preset_id="patches-12-v1",
        pages_expected_count=7,
        calibration_status={0: "not_applied"},
    )
    defaults.update(kwargs)
    return scan_previz.build_scan_previz(**defaults)


def build_reconstructed(**kwargs):
    defaults = dict(
        state=scan_previz.SCAN_PREVIZ_STATE_RECONSTRUCTED,
        output_report=make_output_report(),
        frames_written_count=1,
        frames_expected_count=1,
        synthetic_frame_count=0,
    )
    defaults.update(kwargs)
    return build(**defaults)


def rendered(document) -> str:
    return previz_common.canonical_json(scan_previz.scan_previz_to_json_dict(document))


# ---------------------------------------------------------------------------
# Variante multi-elements: la regle des fabriques du CLAUDE.md
# ---------------------------------------------------------------------------
#
# « Une fabrique de test qui ne produit qu'un seul element rend invisible toute
# erreur d'appariement » -- regle posee le 2026-08-08 apres trois occurrences du
# meme defaut (5.6 `M33`, 5.7 `M25`, et **cinq** survivants de cette story). Les
# fabriques ci-dessus restent mono-element pour que la fixture canonique figee
# reste lisible; la variante multi-elements est ecrite ici, dans la meme story,
# comme la clause 3 de la regle l'exige.
#
# Deux exigences la structurent:
#
# 1. **deux elements distinguables**, jamais un remplissage uniforme -- une page
#    de 10 px en tiff 16 bits et une page de 21 px en png 8 bits, une zone par
#    page contre deux, deux statuts de calibration differents, deux rectangles
#    de zone en pixels differents;
# 2. **la cible ailleurs qu'en premiere position** -- tout ce que les tests de
#    projection multi-pages verifient porte sur la page de rang **1**, la
#    seconde, parce qu'un appariement fautif qui rend toujours le premier
#    element ne se demasque pas autrement.


def make_multi_page_inputs():
    """Deux pages distinguables en tout point, et une seconde a deux zones."""
    ingested_first = make_ingested_page()
    ingested_second = make_ingested_page(
        read_rank=1,
        scan_input_format="png",
        source_bit_depth=8,
        width_px=21,
        height_px=29,
        channels=1,
    )
    detected_first = make_detected_page()
    detected_second = make_detected_page(
        read_rank=1,
        locator_source="scans/lot-a/p2.png",
        locator_page_index=2,
        page_index=4,
        template_source="manifest",
        corner_centers=((2, 1.0, 2.0),),
        foreign_markers=(),
        frame_zones_px=(
            {"name": "frame_zone_1", "x": 11, "y": 12, "width": 13, "height": 14},
            {"name": "frame_zone_2", "x": 21, "y": 22, "width": 23, "height": 24},
        ),
        warnings=("PAGE_ASPECT_OUT_OF_TOLERANCE",),
    )
    plan_second = make_crop_plan(
        frames=[
            make_crop_frame(
                slot_index=0,
                zone_name="frame_zone_1",
                frame_timecode="00:00:01:00",
            ),
            make_crop_frame(
                slot_index=1,
                zone_name="frame_zone_2",
                frame_timecode="00:00:02:00",
                zone_rect_mm=(1.0, 2.0, 3.0, 4.0),
                image_rect_mm=(1.5, 2.5, 2.5, 3.5),
                crop_x_px=5,
                crop_y_px=6,
                width_px=7,
                height_px=8,
            ),
        ]
    )
    return dict(
        ingest=make_ingest(pages=(ingested_first, ingested_second)),
        detection=make_detection(pages=[detected_first, detected_second]),
        crop_plans={0: make_crop_plan(), 1: plan_second},
        calibration_status={0: "not_applied", 1: "failed"},
    )


def make_multi_page_output_report():
    """Les trois frames que les deux pages ci-dessus reclament, et rien d'autre."""
    return make_output_report(
        frames=[
            make_output_frame(page_index=3, slot_index=0, path="out/p3_s0.tiff"),
            make_output_frame(page_index=4, slot_index=0, path="out/p4_s0.tiff"),
            make_output_frame(page_index=4, slot_index=1, path="out/p4_s1.tiff"),
        ]
    )


# ---------------------------------------------------------------------------
# AC 11: purete du module, motif AST des deux jumelles
# ---------------------------------------------------------------------------

ALLOWED_ABSOLUTE_IMPORTS = {
    "__future__",
    "dataclasses",
    "typing",
}
ALLOWED_RELATIVE_IMPORTS = {"previz_common"}
# `__import__` et `compile` fermes aussi (revue 4.9): un import dynamique
# contournerait la liste blanche sans produire de noeud Import. `compile` n'est
# interdit qu'en nom nu: `re.compile` est legitime et n'a rien du builtin de
# compilation de code.
FORBIDDEN_CALL_NAMES = {"open", "print", "input", "exec", "eval", "__import__", "compile"}
FORBIDDEN_ATTR_CALL_NAMES = FORBIDDEN_CALL_NAMES - {"compile"}

FORBIDDEN_MODULES = {
    "subprocess",
    "cv2",
    "PIL",
    "numpy",
    "pathlib",
    "argparse",
    "os",
    "sys",
    "shutil",
    "jsonschema",
    "requests",
    "tkinter",
    "PySide6",
    "PyQt5",
    "PyQt6",
    "wx",
    "kivy",
    "reportlab",
    "ffmpeg",
    "pypdfium2",
}

# `previz_common` est le socle commun ouvert par cette story. Sa liste blanche
# lui est propre: `re`, `json`, `hashlib` et `datetime` y sont legitimes -- ce
# sont la recette de canonicalisation, l'empreinte et la validation
# d'horodatage.
COMMON_ALLOWED_ABSOLUTE_IMPORTS = {
    "__future__",
    "datetime",
    "hashlib",
    "json",
    "re",
    "typing",
}
COMMON_ALLOWED_RELATIVE_IMPORTS = {
    "codec_profiles",
    "source_confirmation",
    # Ajoute par `main` (`52c0db3`) : les gardes `bool`-avant-`int`
    # passent toutes par `numeric_guards`. La liaison garde les deux
    # cotes plutot que d'en perdre un.
    "numeric_guards",
}


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _import_offenders(path: Path, absolute: set[str], relative: set[str]) -> list[str]:
    offenders = []
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in absolute:
                    offenders.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                if (node.module or "") not in relative:
                    offenders.append(f".{node.module}")
            elif (node.module or "") not in absolute:
                offenders.append(node.module or "")
    return offenders


def test_module_imports_are_whitelisted() -> None:
    assert (
        _import_offenders(
            MODULE_PATH, ALLOWED_ABSOLUTE_IMPORTS, ALLOWED_RELATIVE_IMPORTS
        )
        == []
    )


def test_the_shared_previz_module_is_pure_too() -> None:
    """Elargir les listes blanches des jumelles n'ouvre pas une porte non gardee.

    Les tests AST des trois jumelles n'inspectent que les imports **directs** de
    leur propre fichier: si `previz_common` importait `cv2`, les trois
    resteraient verts tout en ne garantissant plus rien. C'est la contrepartie
    de la jonction ouverte par l'AC 1, et elle se paie ici.
    """
    assert (
        _import_offenders(
            COMMON_MODULE_PATH,
            COMMON_ALLOWED_ABSOLUTE_IMPORTS,
            COMMON_ALLOWED_RELATIVE_IMPORTS,
        )
        == []
    )


@pytest.mark.parametrize("path", [MODULE_PATH, COMMON_MODULE_PATH])
def test_module_calls_no_io_primitive(path: Path) -> None:
    offenders = []
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in FORBIDDEN_CALL_NAMES:
                offenders.append((func.id, node.lineno))
            if isinstance(func, ast.Attribute) and func.attr in FORBIDDEN_ATTR_CALL_NAMES:
                offenders.append((func.attr, node.lineno))
    assert offenders == []


@pytest.mark.parametrize("path", [MODULE_PATH, COMMON_MODULE_PATH])
def test_module_references_no_forbidden_module(path: Path) -> None:
    referenced = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            referenced.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level:
            referenced.add((node.module or "").split(".")[0])
    assert referenced & FORBIDDEN_MODULES == set()


@pytest.mark.parametrize("path", [MODULE_PATH, COMMON_MODULE_PATH])
def test_module_never_touches_the_io_package(path: Path) -> None:
    """Le detecteur de chemins absolus existe (`io/manifest`) et c'est le test
    qui l'importe, jamais le module (AC 6 et AC 11)."""
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.ImportFrom) and node.level:
            assert not (node.module or "").startswith("io")


def test_module_never_imports_one_of_the_five_producers() -> None:
    """Le typage structurel n'est pas un confort: c'est ce qui tient l'AC 11.

    Les cinq producteurs tirent tous `cv2` ou `numpy`, directement ou par
    transitivite. Un import de complaisance -- ne serait-ce que pour lire une
    constante de vocabulaire -- ferait entrer OpenCV dans un module de contrat
    de donnees.
    """
    producers = {
        "scan_ingest",
        "scan_detection",
        "scan_crop",
        "scan_output_frames",
        "color_pipeline",
        "page_templates",
        "layout",
        "qr_codes",
    }
    for node in ast.walk(_tree(MODULE_PATH)):
        if isinstance(node, ast.ImportFrom):
            assert (node.module or "") not in producers
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[-1] not in producers


def test_requirements_gain_no_dependency_from_this_story() -> None:
    """Une dependance ajoutee en douce serait le signal d'une preemption d'Epic 7.

    Critere de faute de l'AC 11, mot pour mot: « une dependance ajoutee a
    `requirements.txt` ou un champ type par un toolkit = story fausse ».

    Reconciliation 5.26/7.0 (2026-08-24): `pyside6` et `pytest-qt` sont les
    deux ajouts MANDATES par la story 7.0 (socle GUI, sa fiche les specifie
    nommement), commites en `9b68760` par l'agent 7.0 pendant le developpement
    de 5.26. L'Epic 7 n'est donc plus une preemption a interdire mais un
    developpement en cours; l'ensemble reste epingle **en egalite stricte**
    pour que toute dependance future non mandatee continue de faire rougir ce
    test. `scan_previz` lui-meme, comme le lecteur ajoute par 5.26, n'importe
    toujours aucun de ces paquets (verrou AST de purete ci-dessus).
    """
    requirements = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
    packages = {
        line.split("==")[0].split(">=")[0].strip().lower()
        for line in requirements.splitlines()
        if line.strip() and not line.startswith("#")
    }
    assert packages == {
        "ffmpeg-python",
        # AJOUTE PAR LA STORY 8.10, et porte ici le 2026-09-09 -- il aurait du
        # l'etre dans le meme mouvement que les deux autres copies. Le defaut
        # est celui que ce depot nomme lui-meme : « un remede recopie a cinq
        # endroits diverge ». Cette frontiere existe en QUATRE exemplaires ; le
        # triage du 2026-09-08 n'en a corrige que DEUX, et la premiere CI
        # publique a rendu les deux autres rouges.
        #
        # `pyyaml` entre dans `requirements.txt` parce que
        # `tests/unit/test_politique_lfs.py` lit les workflows sur le YAML
        # ANALYSE et que sa lecture ne doit plus pouvoir SAUTER. Ce n'est donc
        # PAS une preemption d'Epic 7 -- c'est une dependance de BANC,
        # documentee a sa ligne.
        "pyyaml",
        # `EPIC11-ARB-253` / `-254` (2026-09-06) : deux RENOMMAGES, pas deux
        # ajouts, portes ici le 2026-09-07 par `5635d70a` qui a aligne
        # `requirements.txt` sur `pyproject.toml`.
        # `opencv-contrib-python` -> `opencv-python-headless` : les roues
        # non-headless lient leur binaire a douze bibliotheques systeme
        # graphiques absentes d'une machine vierge, et `import cv2` y echoue sur
        # `libGL.so.1` avant la premiere ligne du produit. Les 51 symboles
        # `cv2.*` employes par `src/` ont ete testes un a un contre la roue
        # non-contrib, aucun ne manque -- l'ArUco a quitte `contrib` pour
        # `objdetect` en 4.7.
        # `pyside6` -> `pyside6-essentials` : le metapaquet tirait 401 Mo
        # d'Addons (dont un Chromium complet pour QtWebEngine) qu'aucun fichier
        # du depot n'importe.
        # L'ensemble reste epingle en egalite STRICTE : une dependance
        # reellement AJOUTEE continue de faire rougir ce test.
        "opencv-python-headless",
        "numpy",
        "pillow",
        "reportlab",
        "pypdfium2",
        "jsonschema",
        # Reconciliation 11/EPIC11-ARB-250 (2026-09-06) : `segno` est l'ajout
        # MANDATE par l'arbitrage qui sort l'ENCODAGE QR d'OpenCV. Meme regime
        # que `pyside6` / `pytest-qt` en 2026-08-24 et `textual` en 2026-08-28 :
        # l'ensemble reste epingle en egalite STRICTE, pour que toute dependance
        # future non mandatee continue de faire rougir ce test. Le module previz
        # de cette fiche n'importe pas `segno` (verrou AST de purete ci-dessus)
        # -- `qr_codes.py` est le seul module de `src/` a l'importer, et
        # `test_encodeur_qr_segno.py` le mesure.
        #
        # Le motif, parce qu'une reconciliation sans motif est une tolerance
        # muette : la ligne 4.10/4.11 d'OpenCV ENCODE un symbole malforme
        # au-dela de la version 7, illisible par tout lecteur. Le plancher de
        # version qui aurait ferme le defaut sortait macOS 12 x86_64 de la
        # compatibilite (4.10.0.84 est la derniere roue `macosx_12_0_x86_64`) ;
        # `segno` publie une roue `py3-none-any` et n'exclut personne.
        "segno",
        "pytest",
        "pyside6-essentials",
        "pytest-qt",
        # Reconciliation 5.x/11.0 (2026-08-28) : `textual` est l'ajout
        # MANDATE par la story 11.0 (socle TUI, AC 6.2 le specifie nommement,
        # epingle par serie majeure comme les autres lignes). Meme regime que
        # `pyside6` / `pytest-qt` en 2026-08-24 : l'ensemble reste epingle en
        # egalite STRICTE, pour que toute dependance future non mandatee
        # continue de faire rougir ce test. Le module previz de cette fiche
        # n'importe toujours aucun des trois (verrou AST de purete ci-dessus).
        #
        # **Et ce jour est arrive** : la liaison du 2026-09-01 amene le paquet
        # `tui/` sur cette branche. La phrase precedente annoncait « ce banc
        # rougira si l'un vient sans l'autre » -- il a rougi, sur les trois
        # bancs previz a la fois, exactement comme elle le promettait. La ligne
        # revient donc, et `requirements.txt` la porte deja.
        "textual",
    }


# ---------------------------------------------------------------------------
# AC 2: enveloppe previz-1 reprise telle quelle, kind scan
# ---------------------------------------------------------------------------


def test_envelope_is_the_shared_one_with_its_own_kind() -> None:
    document = scan_previz.scan_previz_to_json_dict(build())
    assert document["previz_schema_version"] == previz_common.PREVIZ_SCHEMA_VERSION
    assert document["previz_schema_version"] == "previz-1"
    assert document["kind"] == "scan"
    assert document["state"] == "detected"
    assert document["generated_at_utc"] == GENERATED_AT
    assert set(document) == {
        "previz_schema_version",
        "kind",
        "state",
        "generated_at_utc",
        "subject",
        "counters",
        "pages",
        "warnings",
        "fingerprints",
    }
    # Les quatre champs de tete viennent du socle commun, pas d'une seconde
    # enveloppe redeclaree.
    assert set(previz_common.ENVELOPE_FIELDS) <= set(document)


def test_envelope_constants_are_frozen() -> None:
    assert scan_previz.SCAN_PREVIZ_KIND == "scan"
    assert scan_previz.SCAN_PREVIZ_STATES == ("detected", "reconstructed")
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
    assert scan_previz.DETECTION_FINGERPRINT_FIELDS == (
        "gamut_map_id",
        "ingested_pages_digest",
        "lot_id",
        "project_id",
        "rush_id",
        "scan_dpi_declared",
        "scan_dpi_detection",
        "template_id",
    )
    assert scan_previz.INGESTED_PAGE_DIGEST_FIELDS == (
        "channels",
        "height_px",
        "read_rank",
        "scan_input_format",
        "source_bit_depth",
        "source_page_index",
        "source_path_relative",
        "width_px",
    )


def test_the_warning_vocabulary_is_not_homonymous_with_its_twins() -> None:
    """ARB-14: l'homonymie est ce qu'un arbitrage anterieur a du resorber."""
    from mixed_media_utility import extraction_previz, pdf_previz

    assert not hasattr(scan_previz, "PREVIZ_WARNING_CODES")
    assert not hasattr(scan_previz, "previz_to_json_dict")
    assert scan_previz.SCAN_PREVIZ_WARNING_CODES != extraction_previz.PREVIZ_WARNING_CODES
    assert scan_previz.SCAN_PREVIZ_WARNING_CODES != pdf_previz.PDF_PREVIZ_WARNING_CODES
    # Le nom de la fonction de serialisation est distinct, et le nom deja pris
    # par 3.5 n'est pas reutilise.
    assert callable(scan_previz.scan_previz_to_json_dict)
    assert extraction_previz.previz_to_json_dict is not scan_previz.scan_previz_to_json_dict


def test_every_warning_code_with_a_producer_is_spelled_like_its_producer() -> None:
    """Point H5.4: deux orthographes pour le meme fait = table de traduction.

    Les vocabulaires des producteurs sont importes ici, jamais recopies: c'est
    le seul endroit du depot ou la confrontation puisse avoir lieu, le module de
    production ne pouvant pas les importer sans faire entrer `cv2`.
    """
    from mixed_media_utility import scan_detection, scan_ingest, scan_output_frames

    assert scan_previz.PAGE_QR_UNREADABLE in scan_output_frames.SCAN_OUTPUT_WARNING_CODES
    assert (
        scan_previz.SYNTHETIC_FRAME_WRITTEN
        in scan_output_frames.SCAN_OUTPUT_WARNING_CODES
    )
    assert scan_previz.DPI_BELOW_QR_MINIMUM in scan_ingest.SCAN_INGEST_WARNING_CODES
    for code in (
        scan_previz.TEMPLATE_FROM_MANIFEST_NOT_QR,
        scan_previz.FOREIGN_MARKER_DETECTED,
        scan_previz.PAGE_SCALE_OUT_OF_TOLERANCE,
        scan_previz.PAGE_ASPECT_OUT_OF_TOLERANCE,
    ):
        assert code in scan_detection.SCAN_DETECTION_WARNING_CODES
    # Et les orthographes voisines qui auraient impose une traduction sont
    # absentes: le pluriel propose par la redaction d'origine de l'AC 9 n'existe
    # chez aucun producteur.
    assert "FOREIGN_MARKERS_DETECTED" not in scan_previz.SCAN_PREVIZ_WARNING_CODES
    assert "SCALE_MISMATCH_SUSPECTED" not in scan_previz.SCAN_PREVIZ_WARNING_CODES


# ---------------------------------------------------------------------------
# AC 3: projection, jamais calcul -- sentinelles incoherentes
# ---------------------------------------------------------------------------


def test_incoherent_sentinels_travel_verbatim() -> None:
    """Si le module recalculait, la sentinelle serait corrigee, pas transportee."""
    document = scan_previz.scan_previz_to_json_dict(build())
    page = document["pages"][0]
    # Echelle absurde, residu negatif: aucune correction, aucun arrondi.
    assert page["scale"] == {"scale_x": 42.0, "scale_y": 0.5, "residual_px": -7.25}
    # Homographie verbatim, y compris ses zeros et son signe.
    assert page["homography"] == [1.5, 0.0, -2.0, 0.0, 1.5, 3.0, 0.0, 0.0, 1.0]
    # Un centre de marqueur hors page passe tel quel.
    assert page["corner_markers"][1]["center_x_px"] == 999.25
    assert page["corner_markers"][1]["center_y_px"] == -4.0
    zone = page["frame_zones"][0]
    # Un rectangle de decoupe de 3307 px dans une page de 10 px: transporte.
    assert zone["crop_rect_px"] == {"x": 826, "y": 1417, "width": 3307, "height": 1860}
    assert page["source"]["width_px"] == 10 and page["source"]["height_px"] == 10
    # Rectangle de zone et rectangle de decoupe ne sont **pas** confondus, et
    # aucun des deux n'est derive de l'autre.
    assert zone["zone_rect_mm"] == {"x": 35.0, "y": 60.0, "width": 140.0, "height": 78.75}
    assert zone["crop_rect_mm"] == {"x": 35.5, "y": 60.5, "width": 139.0, "height": 77.75}
    # Les pixels de zone viennent de 5.2, jamais recalcules depuis les mm: la
    # convention de quantification de 5.2 arrondit origine et taille separement.
    assert zone["zone_rect_px"] == {"x": 826, "y": 1417, "width": 3307, "height": 1860}


def test_read_rank_and_page_index_are_both_carried_and_never_merged() -> None:
    """Piege 3: « le 3e fichier du dossier declare etre la page 1 »."""
    page = scan_previz.scan_previz_to_json_dict(build())["pages"][0]
    assert page["read_rank"] == 0
    assert page["page_index"] == 3
    assert page["address"] == {"read_rank": 0, "page_index": 3}


def test_a_page_without_a_decoded_index_keeps_its_read_rank() -> None:
    detection = make_detection(
        pages=[make_detected_page(page_index=None, page_count=None, qr_status="detected_but_unreadable")]
    )
    page = scan_previz.scan_previz_to_json_dict(build(detection=detection))["pages"][0]
    assert page["page_index"] is None
    assert page["read_rank"] == 0
    assert page["qr_status"] == "detected_but_unreadable"
    # L'adresse reste utilisable: c'est tout l'objet de `read_rank`. Et elle ne
    # **deduit** pas `page_index` du rang de lecture (piege 3): ce test portait
    # le nom du piege et n'assertait que les champs de tete, si bien qu'un
    # `page.page_index or page.read_rank` dans l'adresse survivait -- la page se
    # mettait a declarer etre la page 0 alors que rien ne l'avait decode
    # (revue 5.8, couche 3, AC 5). Le bloc `address` est le livrable de l'AC 5,
    # c'est lui qui doit etre gele.
    assert page["address"] == {"read_rank": 0, "page_index": None}


def test_the_template_provenance_is_carried_verbatim() -> None:
    for source in ("qr", "manifest"):
        detection = make_detection(pages=[make_detected_page(template_source=source)])
        page = scan_previz.scan_previz_to_json_dict(build(detection=detection))["pages"][0]
        assert page["template_source"] == source
        assert page["template_id"] == "tpl-a4-portrait-2f-v1"


def test_foreign_markers_carry_their_role() -> None:
    page = scan_previz.scan_previz_to_json_dict(build())["pages"][0]
    assert page["foreign_markers"] == [
        {
            "address": {"read_rank": 0, "page_index": 3, "marker_id": 77},
            "marker_id": 77,
            "role": "reserved",
        }
    ]


def test_a_page_without_a_crop_plan_carries_no_zone_rather_than_a_guessed_one() -> None:
    """Si une valeur manque, elle manque: le module ne la reconstitue pas."""
    page = scan_previz.scan_previz_to_json_dict(build(crop_plans=None))["pages"][0]
    assert page["frame_zones"] == []


# ---------------------------------------------------------------------------
# AC 5: adressage stable de chaque element editable
# ---------------------------------------------------------------------------


def test_every_editable_element_carries_its_declared_address() -> None:
    document = scan_previz.scan_previz_to_json_dict(build_reconstructed())
    page = document["pages"][0]
    assert set(page["address"]) == set(scan_previz.PAGE_ADDRESS_FIELDS)
    zone = page["frame_zones"][0]
    assert set(zone["address"]) == set(scan_previz.FRAME_ZONE_ADDRESS_FIELDS)
    assert zone["address"] == {"read_rank": 0, "page_index": 3, "slot_index": 0}
    for marker in page["corner_markers"] + page["foreign_markers"]:
        assert set(marker["address"]) == set(scan_previz.MARKER_ADDRESS_FIELDS)
    assert scan_previz.ADDRESSABLE_ELEMENTS == (
        "page",
        "frame_zone",
        "corner_marker",
        "foreign_marker",
    )


def test_addresses_are_stable_across_two_builds() -> None:
    first = scan_previz.scan_previz_to_json_dict(build())["pages"][0]
    second = scan_previz.scan_previz_to_json_dict(build())["pages"][0]
    assert first["address"] == second["address"]
    assert [zone["address"] for zone in first["frame_zones"]] == [
        zone["address"] for zone in second["frame_zones"]
    ]


LAUNCH_PREFIXES = (
    "run",
    "launch",
    "start",
    "execute",
    "confirm",
    "approve",
    "authorize",
    "trigger",
    "persist",
    "save",
    "write",
    "apply",
    "validate_",
)

#: Prefixes verifies sur les **fonctions** seulement: ce sont les verbes qui
#: relanceraient une etape de la chaine scan. En constante ils seraient des
#: noms de domaine parfaitement legitimes (`DETECTION_FINGERPRINT_FIELDS`), ce
#: qui n'a rien a voir avec une fonction qui redetecte.
RELAUNCH_PREFIXES = ("detect", "redetect", "crop", "recrop", "reconstruct")


def test_the_document_authorizes_nothing() -> None:
    """Regle heritee de 3.5 et 3.6: l'AC 5 rend l'edition exprimable, pas
    applicable. L'appliquer est la story 7.4."""
    public_names = [
        node.name
        for node in ast.walk(_tree(MODULE_PATH))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    ]
    assert set(public_names) <= set(scan_previz.__all__)
    for name in public_names + list(scan_previz.__all__):
        assert not name.lower().startswith(LAUNCH_PREFIXES), name
    for name in public_names:
        assert not name.lower().startswith(RELAUNCH_PREFIXES), name
    text = rendered(build_reconstructed())
    for banned in ("granted", "consent", "confirmed_at", "approved", "editable"):
        assert banned not in text


# ---------------------------------------------------------------------------
# AC 6: serialisation canonique et deterministe, chemins relatifs
# ---------------------------------------------------------------------------

#: Fixture canonique **figee en dur**: tout renommage de champ casse ce test,
#: et l'empreinte gelee casse aussi si la recette ou les champs de decision
#: bougent. C'est le gel octet pour octet du contrat, pas une commodite.
FROZEN_CANONICAL_FIXTURE = (
    '{"counters":{"frames_expected":null,"frames_written":null,"pages_exp'
    'ected":7,"pages_present":1,"synthetic_frame_count":null},"fingerprin'
    'ts":{"detection":"sha256-v1:7ebe160c943421e84e8832742e6eaa12e9255ab3'
    'bb58ce8d8f6c366930a26f0c","selection":null},"generated_at_utc":"2026'
    '-08-08T12:00:00Z","kind":"scan","pages":[{"address":{"page_index":3,'
    '"read_rank":0},"calibration":{"status":"not_applied"},"corner_marker'
    's":[{"address":{"marker_id":0,"page_index":3,"read_rank":0},"center_'
    'x_px":12.5,"center_y_px":13.5,"marker_id":0},{"address":{"marker_id"'
    ':1,"page_index":3,"read_rank":0},"center_x_px":999.25,"center_y_px":'
    '-4.0,"marker_id":1}],"decoded_identity":{"gamut_map_id":"gamut-map-n'
    'one-1","lot_id":"lot-a","project_id":"proj-a","rush_id":"rush-001"},'
    '"foreign_markers":[{"address":{"marker_id":77,"page_index":3,"read_r'
    'ank":0},"marker_id":77,"role":"reserved"}],"frame_zones":[{"address"'
    ':{"page_index":3,"read_rank":0,"slot_index":0},"crop_rect_mm":{"heig'
    'ht":77.75,"width":139.0,"x":35.5,"y":60.5},"crop_rect_px":{"height":'
    '1860,"width":3307,"x":826,"y":1417},"frame_path_relative":null,"fram'
    'e_timecode":"00:00:00:00","slot_index":0,"zone_name":"frame_zone_1",'
    '"zone_rect_mm":{"height":78.75,"width":140.0,"x":35.0,"y":60.0},"zon'
    'e_rect_px":{"height":1860,"width":3307,"x":826,"y":1417}}],"homograp'
    'hy":[1.5,0.0,-2.0,0.0,1.5,3.0,0.0,0.0,1.0],"page_count":7,"page_inde'
    'x":3,"page_size_px":[10,10],"qr_status":"decoded","read_rank":0,"ref'
    'usal_code":null,"refusal_reason":null,"scale":{"residual_px":-7.25,"'
    'scale_x":42.0,"scale_y":0.5},"source":{"channels":3,"height_px":10,"'
    'page_index":null,"path_relative":"scans/lot-a/p1.tif","scan_input_fo'
    'rmat":"tiff","source_bit_depth":16,"width_px":10},"status":"ok","tem'
    'plate_id":"tpl-a4-portrait-2f-v1","template_source":"qr","warnings":'
    '["PAGE_SCALE_OUT_OF_TOLERANCE"]}],"previz_schema_version":"previz-1"'
    ',"state":"detected","subject":{"fps_target_exact":"5/1","gamut_map_i'
    'd":"gamut-map-none-1","ingest_slug":"ingest-lot-a","lot_id":"lot-a",'
    '"output_dir_relative":null,"patch_preset_id":"patches-12-v1","projec'
    't_id":"proj-a","rush_id":"rush-001","scan_dpi_declared":600,"scan_dp'
    'i_detection":300,"scans_dir_relative":"scans/lot-a","target_colorspa'
    'ce":"bt709","template_id":"tpl-a4-portrait-2f-v1"},"warnings":{"dete'
    'ction":["TEMPLATE_FROM_MANIFEST_NOT_QR","SCAN_DPI_DIFFERS_FROM_INGES'
    'TED"],"ingest":["DPI_BELOW_QR_MINIMUM"],"output":[],"previz":[]}}'
)


def test_document_json_matches_the_frozen_canonical_fixture() -> None:
    assert rendered(build()) == FROZEN_CANONICAL_FIXTURE


def test_serialization_is_deterministic_byte_for_byte() -> None:
    assert rendered(build()) == rendered(build())
    assert rendered(build_reconstructed()) == rendered(build_reconstructed())
    # Et strictement parseable.
    assert json.loads(rendered(build()))["kind"] == "scan"


def test_the_frame_rate_takes_the_single_canonical_form() -> None:
    assert build(fps_target=5).subject.fps_target_exact == "5/1"
    assert build(fps_target=24000 / 1001).subject.fps_target_exact == "24000/1001"
    # Absente, elle n'est pas inventee.
    assert build(fps_target=None).subject.fps_target_exact is None
    with pytest.raises(SPE, match="Cadence inexploitable"):
        build(fps_target="pas une cadence")


def test_absolute_paths_are_refused_everywhere() -> None:
    with pytest.raises(SPE, match="pas absolu"):
        build(ingest=make_ingest(scans_dir="/abs/scans"))
    with pytest.raises(SPE, match="pas absolu"):
        build(detection=make_detection(pages=[make_detected_page(locator_source="C:\\scan\\p1.tif")]))
    with pytest.raises(SPE, match="pas absolu"):
        build_reconstructed(output_report=make_output_report(output_dir="/abs/out"))
    with pytest.raises(SPE, match="pas absolu"):
        build_reconstructed(
            output_report=make_output_report(frames=[make_output_frame(path="/abs/f.tiff")])
        )
    with pytest.raises(SPE, match="interieur du dossier projet"):
        build(ingest=make_ingest(scans_dir="../ailleurs"))
    # Et le document rendu ne porte aucun chemin absolu: detecteur unique du
    # depot, importe -- jamais reecrit.
    for document in (build(), build_reconstructed()):
        assert (
            _iter_absolute_path_violations(
                scan_previz.scan_previz_to_json_dict(document)
            )
            == []
        )


def test_the_source_rush_never_appears() -> None:
    """Il n'est pas cense exister sur la machine de scan."""
    text = rendered(build_reconstructed())
    for banned in ("rush_path", "source_path_absolute", "rush_file", "mov", "mxf"):
        assert banned not in text


def test_no_pixel_and_no_base64_anywhere() -> None:
    """AC 7: des chemins relatifs, et l'Epic 7 ouvre le fichier."""
    text = rendered(build_reconstructed())
    for banned in ("base64", "data:image", "thumbnail", "pixels", "image_bytes"):
        assert banned not in text


# ---------------------------------------------------------------------------
# AC 8: peremption detectable
# ---------------------------------------------------------------------------


def test_the_fingerprint_carries_the_single_recipe_prefix() -> None:
    document = build()
    assert document.fingerprints.detection.startswith(previz_common.FINGERPRINT_PREFIX)
    assert previz_common.is_complete_fingerprint(document.fingerprints.detection)


@pytest.mark.parametrize(
    "field, value",
    [
        ("gamut_map_id", "gamut-map-bt709-clip-1"),
        ("project_id", "proj-b"),
        ("rush_id", "rush-002"),
        ("lot_id", "lot-b"),
        ("template_id", "tpl-a4-paysage-8f-m5-v1"),
    ],
)
def test_changing_a_decision_input_changes_the_fingerprint(field, value) -> None:
    """`gamut_map_id` **nommement** (piege 9): c'est le trou exact que 5.10 a
    trouve cote impression, et deux documents ne differant que par lui doivent
    avoir des empreintes differentes."""
    assert build().fingerprints.detection != build(**{field: value}).fingerprints.detection


def test_changing_the_declared_scan_dpi_changes_the_fingerprint() -> None:
    assert (
        build().fingerprints.detection
        != build(ingest=make_ingest(declared_dpi=300)).fingerprints.detection
    )


@pytest.mark.parametrize(
    "field, value",
    [
        ("width_px", 11),
        ("height_px", 11),
        ("source_bit_depth", 8),
        ("channels", 1),
        ("scan_input_format", "png"),
    ],
)
def test_changing_an_ingested_page_changes_the_fingerprint(field, value) -> None:
    """`ingested_pages_digest`: l'ensemble des pages ingerees entre bien dans
    l'empreinte, sinon relire le lot dans un autre etat passerait inapercu."""
    page = make_ingested_page(**{field: value})
    assert (
        build().fingerprints.detection
        != build(ingest=make_ingest(pages=(page,))).fingerprints.detection
    )


def test_changing_the_read_rank_of_a_page_changes_the_fingerprint() -> None:
    """Sixieme des huit champs du condensat, et l'un des deux qu'aucun test
    n'atteignait (revue 5.8, couche 3, AC 8).

    Le condensat existe pour attraper un lot **relu dans un autre ordre**: si
    le rang de lecture n'y entre pas, deux lots aux memes pages lues dans deux
    ordres portent la meme empreinte.
    """
    other = build(
        ingest=make_ingest(pages=(make_ingested_page(read_rank=5),)),
        detection=make_detection(pages=[make_detected_page(read_rank=5)]),
        crop_plans={5: make_crop_plan()},
        calibration_status={5: "not_applied"},
    )
    assert build().fingerprints.detection != other.fingerprints.detection


@pytest.mark.parametrize(
    "field, value",
    [
        ("locator_page_index", 4),
        ("locator_source", "scans/lot-a/p9.tif"),
    ],
)
def test_changing_the_page_locator_changes_the_fingerprint(field, value) -> None:
    """Les deux derniers champs du condensat, et le second qu'aucun test
    n'atteignait: `source_page_index` distingue une page multi-page de PDF d'un
    lot par ailleurs identique.

    Ils viennent du locator du document de **detection** (5.2) et non du
    rapport d'ingestion -- provenance mixte assumee et desormais ecrite dans la
    docstring d'`INGESTED_PAGE_DIGEST_FIELDS`.
    """
    other = build(detection=make_detection(pages=[make_detected_page(**{field: value})]))
    assert build().fingerprints.detection != other.fingerprints.detection


def test_the_page_digest_is_sensitive_to_the_read_order() -> None:
    """Deux lots aux memes pages, lues dans deux ordres, ne sont pas le meme lot.

    Le condensat suit l'ordre de projection, qui est celui de 5.2. Un condensat
    re-trie sur une cle stable (par chemin source, par exemple) rendrait les
    deux identiques -- mutant survivant de la revue, invisible tant qu'aucune
    fixture n'a deux pages dans deux ordres.
    """
    inputs = make_multi_page_inputs()
    forward = build(**inputs)
    reversed_pages = build(
        **{
            **inputs,
            "detection": make_detection(pages=tuple(reversed(inputs["detection"].pages))),
        }
    )
    assert [page.read_rank for page in reversed_pages.pages] == [1, 0]
    assert forward.fingerprints.detection != reversed_pages.fingerprints.detection


def test_regenerating_identically_does_not_change_the_fingerprint() -> None:
    assert build().fingerprints.detection == build().fingerprints.detection


@pytest.mark.parametrize(
    "kwargs",
    [
        {"previz_warnings": ("PAGE_QR_UNREADABLE", "CALIBRATION_FAILED")},
        {"target_colorspace": "bt2020"},
        {"patch_preset_id": "patches-18-v2"},
        {"pages_expected_count": 99},
        {"generated_at_utc": "2027-01-01T00:00:00Z"},
    ],
)
def test_what_decides_nothing_does_not_change_the_fingerprint(kwargs) -> None:
    """Piege 5: ajouter ou retirer un avertissement ne change pas l'empreinte.

    Une empreinte sensible a ce qui ne decide rien signalerait des peremptions
    imaginaires."""
    assert build().fingerprints.detection == build(**kwargs).fingerprints.detection


def test_a_clipping_verdict_stays_out_of_the_fingerprint() -> None:
    """Constatation de mesure, au meme regime que les avertissements."""
    with_verdict = build(gamut_clipping={0: True})
    assert with_verdict.fingerprints.detection == build().fingerprints.detection


def test_a_synthetic_frame_stays_out_of_the_fingerprint() -> None:
    """Elle ne change pas les entrees de decision, elle en constate l'echec."""
    real = build_reconstructed()
    synthetic = build_reconstructed(
        output_report=make_output_report(
            frames=[make_output_frame(synthetic=True, synthetic_reason="frame_crop_failed")]
        ),
        synthetic_frame_count=1,
    )
    assert real.fingerprints.detection == synthetic.fingerprints.detection


def test_an_upstream_fingerprint_travels_verbatim_and_in_complete_form() -> None:
    upstream = previz_common.fingerprint_of({"amont": 1})
    assert build(selection_fingerprint=upstream).fingerprints.selection == upstream
    # Et dans la forme **normative**, qui est le JSON (AC 6): l'assertion ne
    # portait que sur l'objet Python, si bien que rendre `"selection": None`
    # survivait -- la fixture figee ne porte que le cas `null` (revue 5.8,
    # couche 3, AC 13).
    document = scan_previz.scan_previz_to_json_dict(
        build(selection_fingerprint=upstream)
    )
    assert document["fingerprints"]["selection"] == upstream
    # Elle n'entre pas dans l'empreinte calculee ici.
    assert (
        build(selection_fingerprint=upstream).fingerprints.detection
        == build().fingerprints.detection
    )
    # Forme complete exigee: le prefixe seul n'est comparable a rien.
    for bad in ("sha256-v1:", "sha256-v1:zzzz", "deadbeef", previz_common.FINGERPRINT_PREFIX + "ab"):
        with pytest.raises(SPE, match="forme complete"):
            build(selection_fingerprint=bad)


def test_the_fingerprint_payload_cannot_diverge_from_its_exported_constant(
    monkeypatch,
) -> None:
    """La constante exportee est ce qui rend le piege 5 verifiable, et le
    garde-fou est **vivant**: on le prouve en desalignant la constante.

    Sans cette verification, un champ pourrait entrer dans l'empreinte sans
    entrer dans la constante -- et la constante ne documenterait plus rien.
    """
    payload_fields = set(scan_previz.DETECTION_FINGERPRINT_FIELDS)
    assert "gamut_map_id" in payload_fields
    for banned in ("warnings", "synthetic", "clipping", "generated_at_utc"):
        assert banned not in payload_fields

    monkeypatch.setattr(
        scan_previz,
        "DETECTION_FINGERPRINT_FIELDS",
        tuple(f for f in scan_previz.DETECTION_FINGERPRINT_FIELDS if f != "gamut_map_id"),
    )
    with pytest.raises(SPE, match="DETECTION_FINGERPRINT_FIELDS"):
        build()


def test_the_ingested_page_digest_entry_cannot_diverge_from_its_constant(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        scan_previz,
        "INGESTED_PAGE_DIGEST_FIELDS",
        scan_previz.INGESTED_PAGE_DIGEST_FIELDS + ("un_champ_de_plus",),
    )
    with pytest.raises(SPE, match="INGESTED_PAGE_DIGEST_FIELDS"):
        build()


# ---------------------------------------------------------------------------
# AC 9: vocabulaire ferme, LOT_INCOMPLETE deduit
# ---------------------------------------------------------------------------


def test_an_unknown_warning_code_is_refused() -> None:
    with pytest.raises(SPE, match="inconnu"):
        build(previz_warnings=("PAS_UN_CODE",))
    # Le code d'une jumelle n'est pas le sien.
    with pytest.raises(SPE, match="inconnu"):
        build(previz_warnings=("GEOMETRY_DEGRADED",))


def test_a_duplicated_warning_code_is_refused() -> None:
    with pytest.raises(SPE, match="duplique"):
        build(previz_warnings=("CALIBRATION_FAILED", "CALIBRATION_FAILED"))


def test_a_string_of_codes_is_refused_rather_than_split_into_letters() -> None:
    with pytest.raises(SPE, match="sequence de codes"):
        build(previz_warnings="CALIBRATION_FAILED")


def test_the_warning_family_is_sorted_for_canonical_stability() -> None:
    first = build(previz_warnings=("PAGE_QR_UNREADABLE", "CALIBRATION_FAILED"))
    second = build(previz_warnings=("CALIBRATION_FAILED", "PAGE_QR_UNREADABLE"))
    assert first.warnings.previz == ("CALIBRATION_FAILED", "PAGE_QR_UNREADABLE")
    assert rendered(first) == rendered(second)


def test_upstream_warning_families_are_carried_verbatim_and_never_merged() -> None:
    """Motif des trois familles de 3.5: jamais fusionnees, jamais traduites."""
    document = scan_previz.scan_previz_to_json_dict(
        build_reconstructed(
            previz_warnings=("CALIBRATION_FAILED",), frames_written_count=0
        )
    )
    assert document["warnings"] == {
        "ingest": ["DPI_BELOW_QR_MINIMUM"],
        "detection": [
            "TEMPLATE_FROM_MANIFEST_NOT_QR",
            "SCAN_DPI_DIFFERS_FROM_INGESTED",
        ],
        "output": ["SYNTHETIC_FRAME_WRITTEN"],
        "previz": ["CALIBRATION_FAILED", "LOT_INCOMPLETE"],
    }
    # Et les avertissements de page restent sur leur page.
    assert document["pages"][0]["warnings"] == ["PAGE_SCALE_OUT_OF_TOLERANCE"]


def test_lot_incomplete_is_refused_as_an_input() -> None:
    with pytest.raises(SPE, match="ne se fournit jamais"):
        build(previz_warnings=("LOT_INCOMPLETE",))


def test_synthetic_frame_written_is_accepted_as_an_input() -> None:
    """Il se transporte depuis le rapport de 5.6, il ne se deduit pas.

    `LOT_INCOMPLETE` reste la **seule** exception a la purete d'emission: en
    creer une seconde ouvrirait la porte aux suivantes.
    """
    document = build_reconstructed(previz_warnings=("SYNTHETIC_FRAME_WRITTEN",))
    assert "SYNTHETIC_FRAME_WRITTEN" in document.warnings.previz
    # Et il n'est **pas** deduit du compteur: un lot qui porte des mires sans
    # que l'appelant ait transporte le code ne le voit pas apparaitre.
    silent = build_reconstructed(
        output_report=make_output_report(
            frames=[make_output_frame(synthetic=True, synthetic_reason="page_detection_failed")]
        ),
        synthetic_frame_count=1,
    )
    assert "SYNTHETIC_FRAME_WRITTEN" not in silent.warnings.previz
    assert "LOT_INCOMPLETE" in silent.warnings.previz


def test_lot_incomplete_is_deduced_from_the_counters() -> None:
    complete = build_reconstructed(frames_written_count=1, frames_expected_count=1)
    assert complete.warnings.previz == ()
    truncated = build_reconstructed(frames_written_count=0, frames_expected_count=1)
    assert truncated.warnings.previz == ("LOT_INCOMPLETE",)


def test_a_lot_carrying_a_synthetic_frame_is_never_declared_complete() -> None:
    """EPIC5-ARB-32: l'egalite `ecrit == attendu` ne suffit pas.

    Sans cette clause, la previz dirait « lot complet » la ou le manifest de 5.7
    dit « partiel » -- deux morceaux verts chacun sur ses fixtures et jamais
    confrontes.
    """
    document = build_reconstructed(
        frames_written_count=1, frames_expected_count=1, synthetic_frame_count=1
    )
    assert "LOT_INCOMPLETE" in document.warnings.previz


def test_an_indeterminable_expected_count_is_never_declared_complete() -> None:
    """5.6 declare le cardinal attendu indeterminable quand aucune page n'a
    livre de payload exploitable. Le manifest ne declare alors pas le lot
    complet, et ce document non plus."""
    document = build_reconstructed(frames_expected_count=None)
    assert document.counters.frames_expected is None
    assert "LOT_INCOMPLETE" in document.warnings.previz


def test_lot_incomplete_is_never_emitted_before_anything_is_written() -> None:
    assert build().warnings.previz == ()
    assert build().counters.frames_written is None


def test_more_written_than_expected_is_refused_at_construction() -> None:
    with pytest.raises(SPE, match="depasse le cardinal attendu"):
        build_reconstructed(frames_written_count=2, frames_expected_count=1)


def test_more_synthetic_than_written_is_refused_at_construction() -> None:
    with pytest.raises(SPE, match="depasse le nombre de"):
        build_reconstructed(
            frames_written_count=1, frames_expected_count=1, synthetic_frame_count=2
        )


def test_a_page_count_above_the_expected_one_is_not_refused() -> None:
    """Un lot qui porte plus de pages qu'il n'en annonce est precisement le lot
    melange que ce document existe pour montrer."""
    document = build(pages_expected_count=0)
    assert document.counters.pages_present == 1
    assert document.counters.pages_expected == 0


# ---------------------------------------------------------------------------
# AC 10: les deux etats
# ---------------------------------------------------------------------------


def test_an_unknown_state_is_refused() -> None:
    with pytest.raises(SPE, match="Etat de previz inconnu"):
        build(state="planned")


def test_the_detected_state_forbids_every_observed_datum() -> None:
    for kwargs in (
        {"frames_written_count": 0},
        {"frames_expected_count": 0},
        {"synthetic_frame_count": 0},
    ):
        with pytest.raises(SPE, match="n'a pas de sens en regime 'detected'"):
            build(**kwargs)
    with pytest.raises(SPE, match="n'a pas de sens en regime 'detected'"):
        build(output_report=make_output_report())


def test_the_reconstructed_state_requires_what_it_declares() -> None:
    with pytest.raises(SPE, match="output_report est obligatoire"):
        build(state="reconstructed", frames_written_count=1, synthetic_frame_count=0)
    for missing in ("frames_written_count", "synthetic_frame_count"):
        kwargs = dict(frames_written_count=1, frames_expected_count=1, synthetic_frame_count=0)
        kwargs[missing] = None
        with pytest.raises(SPE, match="est obligatoire en regime 'reconstructed'"):
            build_reconstructed(**kwargs)


def test_the_reconstructed_state_carries_the_output_directory_and_paths() -> None:
    document = scan_previz.scan_previz_to_json_dict(build_reconstructed())
    assert document["state"] == "reconstructed"
    assert document["subject"]["output_dir_relative"] == "output-frames/rush-001_5"
    zone = document["pages"][0]["frame_zones"][0]
    assert zone["frame_path_relative"] == (
        "output-frames/rush-001_5/scan_rush-001_5_00-00-00-00.tiff"
    )


def test_the_detected_state_carries_no_frame_path() -> None:
    document = scan_previz.scan_previz_to_json_dict(build())
    assert document["subject"]["output_dir_relative"] is None
    zone = document["pages"][0]["frame_zones"][0]
    assert zone["frame_path_relative"] is None


# ---------------------------------------------------------------------------
# AC 4: le drapeau synthetique, inconditionnel des qu'une frame existe
# ---------------------------------------------------------------------------


def test_the_synthetic_flag_is_written_on_a_real_frame_too() -> None:
    """Piege 8: un drapeau absent se lit « vraie frame ».

    Un test qui ne verifierait que le cas `true` laisserait passer exactement
    l'omission que l'AC 4 interdit.
    """
    zone = scan_previz.scan_previz_to_json_dict(build_reconstructed())["pages"][0][
        "frame_zones"
    ][0]
    assert "synthetic" in zone
    assert zone["synthetic"] is False
    # Et une vraie frame ne porte pas de motif de remplacement.
    assert "synthetic_reason" not in zone


def test_the_synthetic_flag_and_its_reason_travel_on_a_replacement_frame() -> None:
    document = build_reconstructed(
        output_report=make_output_report(
            frames=[make_output_frame(synthetic=True, synthetic_reason="page_detection_failed")]
        ),
        synthetic_frame_count=1,
    )
    zone = scan_previz.scan_previz_to_json_dict(document)["pages"][0]["frame_zones"][0]
    assert zone["synthetic"] is True
    assert zone["synthetic_reason"] == "page_detection_failed"


def test_the_synthetic_reason_is_never_translated_or_reinterpreted() -> None:
    """Le vocabulaire ferme appartient a 5.6 et est importe **ici**."""
    from mixed_media_utility import scan_output_frames

    for reason in scan_output_frames.SYNTHETIC_FRAME_REASONS:
        document = build_reconstructed(
            output_report=make_output_report(
                frames=[make_output_frame(synthetic=True, synthetic_reason=reason)]
            ),
            synthetic_frame_count=1,
        )
        zone = scan_previz.scan_previz_to_json_dict(document)["pages"][0]["frame_zones"][0]
        assert zone["synthetic_reason"] == reason


def test_a_zone_without_a_frame_carries_no_synthetic_flag_at_all() -> None:
    zone = scan_previz.scan_previz_to_json_dict(build())["pages"][0]["frame_zones"][0]
    assert "synthetic" not in zone
    assert "synthetic_reason" not in zone


def test_the_flag_and_the_path_cannot_be_separated() -> None:
    """L'invariant est verrouille par le constructeur, pas seulement par le
    chemin nominal de projection."""
    with pytest.raises(SPE, match="ni plus ni moins"):
        scan_previz.PrevizFrameZone(
            slot_index=0,
            frame_timecode=None,
            zone_name="z",
            zone_x_mm=0.0, zone_y_mm=0.0, zone_w_mm=1.0, zone_h_mm=1.0,
            crop_x_mm=0.0, crop_y_mm=0.0, crop_w_mm=1.0, crop_h_mm=1.0,
            crop_x_px=0, crop_y_px=0, crop_w_px=1, crop_h_px=1,
            frame_path_relative="frames/a.tiff",
            synthetic=None,
        )
    with pytest.raises(SPE, match="ni plus ni moins"):
        scan_previz.PrevizFrameZone(
            slot_index=0,
            frame_timecode=None,
            zone_name="z",
            zone_x_mm=0.0, zone_y_mm=0.0, zone_w_mm=1.0, zone_h_mm=1.0,
            crop_x_mm=0.0, crop_y_mm=0.0, crop_w_mm=1.0, crop_h_mm=1.0,
            crop_x_px=0, crop_y_px=0, crop_w_px=1, crop_h_px=1,
            frame_path_relative=None,
            synthetic=False,
        )
    with pytest.raises(SPE, match="si et seulement si"):
        scan_previz.PrevizFrameZone(
            slot_index=0,
            frame_timecode=None,
            zone_name="z",
            zone_x_mm=0.0, zone_y_mm=0.0, zone_w_mm=1.0, zone_h_mm=1.0,
            crop_x_mm=0.0, crop_y_mm=0.0, crop_w_mm=1.0, crop_h_mm=1.0,
            crop_x_px=0, crop_y_px=0, crop_w_px=1, crop_h_px=1,
            frame_path_relative="frames/a.tiff",
            synthetic=False,
            synthetic_reason="page_detection_failed",
        )


def test_two_frames_at_the_same_address_are_refused() -> None:
    with pytest.raises(SPE, match="deux frames a l'adresse"):
        build_reconstructed(
            output_report=make_output_report(
                frames=[make_output_frame(), make_output_frame()]
            ),
            frames_written_count=2,
            frames_expected_count=2,
        )


# ---------------------------------------------------------------------------
# AC 4 / Dev Notes: le verdict d'ecretage, conditionnel et jamais nie
# ---------------------------------------------------------------------------


def test_the_clipping_verdict_is_omitted_when_calibration_did_not_run() -> None:
    """Jamais `null`, et surtout jamais un verdict negatif: affirmer l'absence
    d'ecretage sur la foi d'une mesure jamais faite est le seul mensonge que ce
    document puisse commettre sur ce point."""
    page = scan_previz.scan_previz_to_json_dict(build())["pages"][0]
    assert page["calibration"] == {"status": "not_applied"}
    assert "clipping_detected" not in page["calibration"]
    assert "clipping_detected" not in rendered(build())


@pytest.mark.parametrize("verdict", [True, False])
def test_a_measured_clipping_verdict_travels_verbatim(verdict) -> None:
    page = scan_previz.scan_previz_to_json_dict(
        build(calibration_status={0: "applied"}, gamut_clipping={0: verdict})
    )["pages"][0]
    assert page["calibration"] == {"status": "applied", "clipping_detected": verdict}


def test_the_verdict_and_the_status_are_never_deduced_from_each_other() -> None:
    """5.4b les tient pour independants: une correction peut converger
    proprement sur une planche par ailleurs ecretee."""
    page = scan_previz.scan_previz_to_json_dict(
        build(calibration_status={0: "applied"}, gamut_clipping={0: True})
    )["pages"][0]
    assert page["calibration"]["status"] == "applied"
    assert page["calibration"]["clipping_detected"] is True
    # Un statut `failed` n'invente pas de verdict.
    other = scan_previz.scan_previz_to_json_dict(
        build(calibration_status={0: "failed"})
    )["pages"][0]
    assert other["calibration"] == {"status": "failed"}


def test_a_clipping_verdict_without_a_calibration_status_is_refused() -> None:
    with pytest.raises(SPE, match="sans statut de calibration"):
        build(calibration_status=None, gamut_clipping={0: True})


def test_the_calibration_status_travels_from_the_real_closed_vocabulary() -> None:
    """Le vocabulaire vit dans `color_pipeline`, qui importe cv2: le module ne
    peut pas l'importer, donc c'est le test qui le confronte."""
    from mixed_media_utility import color_pipeline

    for status in color_pipeline.CALIBRATION_STATUS_VALUES:
        document = build(calibration_status={0: status})
        assert document.pages[0].calibration.status == status
    # Au MVP, c'est invariablement celui-la.
    assert color_pipeline.NOT_APPLIED_STATUS == "not_applied"


def test_a_page_without_calibration_carries_none_rather_than_a_guess() -> None:
    page = scan_previz.scan_previz_to_json_dict(build(calibration_status=None))["pages"][0]
    assert page["calibration"] is None


# ---------------------------------------------------------------------------
# Gardes de structure: rien n'est ignore en silence
# ---------------------------------------------------------------------------


def test_a_mapping_key_unknown_to_the_detection_report_is_refused() -> None:
    """Motif de 3.5: un rang inconnu serait silencieusement ignore."""
    for kwargs in (
        {"crop_plans": {9: make_crop_plan()}},
        {"calibration_status": {9: "not_applied"}},
        {"calibration_status": {0: "not_applied"}, "gamut_clipping": {0: True, 9: False}},
    ):
        with pytest.raises(SPE, match="rangs absents"):
            build(**kwargs)


def test_a_detected_page_absent_from_the_ingest_report_is_refused() -> None:
    detection = make_detection(pages=[make_detected_page(read_rank=5)])
    with pytest.raises(SPE, match="absentes du rapport d'ingestion"):
        build(detection=detection, crop_plans=None, calibration_status=None)


def test_an_ingested_page_absent_from_the_detection_report_is_refused() -> None:
    """Elle serait silencieusement absente de la previz, alors qu'une page
    ingeree et jamais detectee est exactement ce qu'une interface doit
    montrer."""
    ingest = make_ingest(
        pages=(make_ingested_page(), make_ingested_page(read_rank=1))
    )
    with pytest.raises(SPE, match="absentes du document de detection"):
        build(ingest=ingest)


def test_two_detected_pages_of_the_same_read_rank_are_refused() -> None:
    detection = make_detection(pages=[make_detected_page(), make_detected_page()])
    with pytest.raises(SPE, match="deux pages du meme rang"):
        build(detection=detection)


def test_a_structurally_incomplete_input_raises_the_module_hierarchy() -> None:
    """Un attribut manquant levait `AttributeError` brute, hors de la hierarchie
    promise (« entree refusee a la construction » = ScanPrevizError)."""
    page = make_detected_page()
    del page.scale
    with pytest.raises(SPE, match="structurellement incomplete"):
        build(detection=make_detection(pages=[page]))


def test_a_malformed_timestamp_is_refused() -> None:
    with pytest.raises(SPE, match="horodatage UTC ISO 8601"):
        build(generated_at_utc="2026-08-08 12:00:00")
    with pytest.raises(SPE, match="aucun instant reel"):
        build(generated_at_utc="2026-02-30T12:00:00Z")


def test_a_trailing_newline_never_enters_the_document() -> None:
    """`fullmatch` et non `match`, et le cas qui le prouve.

    En mode non multiligne, `$` accepte encore un saut de ligne final. Sur un
    horodatage sans fraction, la garde d'instant reel rattrape par accident --
    `rstrip("Z")` ne mord pas quand le dernier caractere est `\\n`, et
    `strptime` echoue. Avec des **secondes fractionnaires**, elle ne rattrape
    plus: `"...T12:00:00.5Z\\n".split(".")[0]` rend un instant parfaitement
    valide, et le `\\n` entrerait dans le document. C'est le seul cas qui
    distingue `match` de `fullmatch` ici, et donc le seul qui teste vraiment la
    regle (revue du 2026-08-05, regle desormais partagee par les trois
    jumelles via `previz_common`).
    """
    with pytest.raises(SPE, match="horodatage UTC ISO 8601"):
        build(generated_at_utc="2026-08-08T12:00:00.5Z\n")
    with pytest.raises(SPE, match="horodatage UTC ISO 8601"):
        build(generated_at_utc=GENERATED_AT + "\n")
    # Et la forme fractionnaire sans saut de ligne, elle, est acceptee telle
    # quelle: la garde vise le `\n`, pas la fraction.
    accepted = build(generated_at_utc="2026-08-08T12:00:00.5Z")
    assert accepted.generated_at_utc == "2026-08-08T12:00:00.5Z"


def test_a_boolean_never_passes_for_a_counter() -> None:
    """Action item 2 de la retro Epic 4: `isinstance(True, int)` vaut vrai."""
    with pytest.raises(SPE, match="doit etre un entier"):
        build_reconstructed(frames_written_count=True)
    with pytest.raises(SPE, match="doit etre un entier"):
        build(pages_expected_count=True)


def test_the_lot_identity_is_required_and_never_elected_among_the_pages() -> None:
    """Choisir celle de la premiere page fabriquerait un lot qui n'a jamais
    existe -- motif de `scan_detection.LotIdentityError`."""
    for field in ("project_id", "rush_id", "lot_id", "template_id", "gamut_map_id"):
        with pytest.raises(SPE, match="chaine non vide"):
            build(**{field: None})
    # Et l'identite du sujet n'est pas celle decodee sur la page: les deux
    # coexistent, ce qui est ce qui permet de voir un lot melange.
    document = scan_previz.scan_previz_to_json_dict(
        build(
            detection=make_detection(pages=[make_detected_page(lot_id="lot-etranger")])
        )
    )
    assert document["subject"]["lot_id"] == "lot-a"
    assert document["pages"][0]["decoded_identity"]["lot_id"] == "lot-etranger"


def test_gamut_map_id_has_no_absent_branch() -> None:
    """EPIC5-ARB-13: le champ est le onzieme champ **obligatoire** du payload,
    un payload sans lui est invalide en amont et n'atteint jamais ce module.
    Coder une branche « absent » reintroduirait un chemin mort."""
    with pytest.raises(SPE):
        build(gamut_map_id=None)
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "gamut_map_id is None" not in source
    document = scan_previz.scan_previz_to_json_dict(build())
    assert document["subject"]["gamut_map_id"] == "gamut-map-none-1"


# ---------------------------------------------------------------------------
# AC 12: integration contre les VRAIS producteurs
# ---------------------------------------------------------------------------


def test_the_real_producers_satisfy_the_previz_protocols(tmp_path: Path) -> None:
    """Action item 3 de la retrospective de l'Epic 4, ecrit des la story.

    « Le premier consommateur reel aurait casse en silence sur un renommage de
    champ, tests tous verts. » Ici la confrontation a lieu: le rapport
    d'ingestion sort du vrai `ingest_scan_lot` apres lecture d'un fichier reel,
    les pages detectees sont de vraies `DetectedPage` dont la geometrie vient du
    vrai `resolve_page_geometry`, le plan de decoupe du vrai
    `build_page_crop_plan`, et le rapport d'ecriture du vrai
    `write_lot_output_frames` apres ecriture sur disque.
    """
    from mixed_media_utility import (
        color_pipeline,
        page_templates,
        scan_crop,
        scan_detection,
        scan_ingest,
        scan_output_frames,
    )
    from mixed_media_utility.io import naming, payload as payload_io

    dpi = 300
    rush_id = "rush-001"
    fps_target = 5.0
    template_id = page_templates.build_template_id("portrait", 2, "2")
    lot_id = naming.build_lot_id(rush_id, fps_target)

    # --- 5.1: ingestion reelle d'une page ecrite sur le disque --------------
    geometry = scan_detection.resolve_page_geometry(template_id, dpi)
    width_px, height_px = geometry["page_size_px"]
    scans_source = tmp_path / "source"
    scans_source.mkdir()
    page_image = np.full((height_px, width_px, 3), 32768, dtype=np.uint16)
    assert cv2.imwrite(str(scans_source / "p001.tif"), page_image)
    ingest_report = scan_ingest.ingest_scan_lot(
        tmp_path, scans_source, dpi=dpi, ingest_slug="lot-integration"
    )
    assert isinstance(ingest_report, scan_ingest.ScanIngestReport)
    assert len(ingest_report.pages) == 1

    # --- 5.2: un vrai payload et une vraie DetectedPage ---------------------
    payload = payload_io.build_page_payload(
        project_id="projet-test",
        rush_id=rush_id,
        lot_id=lot_id,
        page_index=0,
        page_count=1,
        fps_target=fps_target,
        timecode_base_fps="25/1",
        template_id=template_id,
        patch_preset_id="patch-values-2",
        target_colorspace="bt709",
        gamut_map_id=payload_io.GAMUT_MAP_IDENTITY,
        slots=[
            {"slot_index": 0, "frame_timecode": "00:00:00:00"},
            {"slot_index": 1, "frame_timecode": "00:00:00:01"},
        ],
    )
    ingested = ingest_report.pages[0]
    detected = scan_detection.DetectedPage(
        read_rank=ingested.read_rank,
        status=scan_detection.PAGE_OK,
        locator_source=ingested.locator.source_path,
        locator_page_index=ingested.locator.page_index,
        qr_status=scan_detection.qr_codes.DECODE_OK,
        template_id=template_id,
        template_source="qr",
        project_id=payload["project_id"],
        rush_id=payload["rush_id"],
        lot_id=payload["lot_id"],
        page_index=payload["page_index"],
        page_count=payload["page_count"],
        gamut_map_id=payload["gamut_map_id"],
        corner_centers=tuple(
            (marker_id, float(x), float(y))
            for marker_id, (x, y) in sorted(geometry["corner_centers_mm"].items())
        ),
        foreign_markers=(scan_detection.ForeignMarker(marker_id=77, role="reserved"),),
        homography=tuple(float(value) for value in range(9)),
        page_size_px=geometry["page_size_px"],
        scale=scan_detection.PageScaleMeasurement(
            scale_x=1.001, scale_y=0.999, residual_px=0.42
        ),
        frame_zones_mm=geometry["frame_zones_mm"],
        frame_zones_px=geometry["frame_zones_px"],
        warnings=("FOREIGN_MARKER_DETECTED",),
        payload=payload,
    )
    detection_report = scan_detection.LotDetectionReport(
        ingest_slug=ingest_report.ingest_slug,
        scan_dpi=dpi,
        pages=(detected,),
        ingest_declared_dpi=ingest_report.declared_dpi,
    )

    # --- 5.3: le vrai plan de decoupe ---------------------------------------
    crop_plan = scan_crop.build_page_crop_plan(
        template_id=template_id, slots=payload["slots"], dpi=dpi
    )
    assert isinstance(crop_plan, scan_crop.PageCropPlan)

    # --- 5.6: le vrai rapport d'ecriture, apres ecriture reelle -------------
    frames = tuple(
        np.full((frame.height_px, frame.width_px, 3), 4096 + index, dtype=np.uint16)
        for index, frame in enumerate(crop_plan.frames)
    )
    output_report = scan_output_frames.write_lot_output_frames(
        tmp_path,
        [
            scan_output_frames.ScannedPage(
                payload=payload, crop_plan=crop_plan, frames=frames
            )
        ],
    )
    assert isinstance(output_report, scan_output_frames.LotOutputReport)
    assert output_report.written_frame_count == 2

    # --- 5.8: la previz, contre ces objets-la et aucun autre ----------------
    document = scan_previz.build_scan_previz(
        ingest=ingest_report,
        detection=detection_report,
        crop_plans={detected.read_rank: crop_plan},
        state=scan_previz.SCAN_PREVIZ_STATE_RECONSTRUCTED,
        output_report=output_report,
        generated_at_utc=GENERATED_AT,
        project_id=payload["project_id"],
        rush_id=payload["rush_id"],
        lot_id=payload["lot_id"],
        template_id=template_id,
        gamut_map_id=payload["gamut_map_id"],
        fps_target=output_report.fps_target,
        target_colorspace=output_report.target_colorspace,
        patch_preset_id=output_report.patch_preset_id,
        pages_expected_count=payload["page_count"],
        # Cardinaux **du lot** et non de la passe (EPIC5-ARB-32): ici les deux
        # coincident, la passe etant la premiere.
        frames_written_count=output_report.observed_frame_count,
        frames_expected_count=output_report.expected_frame_count,
        synthetic_frame_count=len(output_report.synthetic_frames),
        calibration_status={
            detected.read_rank: output_report.color_calibration_status
        },
        # Les cinq vocabulaires fermes, verses par l'appelant (revue 5.8,
        # couche 3): le module ne peut ni les importer ni les recopier, mais
        # l'appelant les a deja sous la main puisqu'il recoit les rapports.
        ingest_warning_vocabulary=scan_ingest.SCAN_INGEST_WARNING_CODES,
        detection_warning_vocabulary=scan_detection.SCAN_DETECTION_WARNING_CODES,
        output_warning_vocabulary=scan_output_frames.SCAN_OUTPUT_WARNING_CODES,
        synthetic_reason_vocabulary=scan_output_frames.SYNTHETIC_FRAME_REASONS,
        calibration_status_vocabulary=color_pipeline.CALIBRATION_STATUS_VALUES,
    )

    # La projection reflete les producteurs champ par champ.
    assert document.subject.scan_dpi_declared == ingest_report.declared_dpi
    assert document.subject.scans_dir_relative == ingest_report.scans_dir
    assert document.subject.output_dir_relative == output_report.output_dir
    assert document.subject.fps_target_exact == "5/1"
    assert document.pages[0].scan_input_format == ingested.scan_input_format
    assert document.pages[0].source_bit_depth == ingested.source_bit_depth
    assert document.pages[0].width_px == ingested.width_px
    assert document.pages[0].calibration.status == color_pipeline.NOT_APPLIED_STATUS

    zones = document.pages[0].frame_zones
    assert len(zones) == len(crop_plan.frames)
    for zone, planned in zip(zones, crop_plan.frames):
        assert zone.slot_index == planned.slot_index
        assert zone.frame_timecode == planned.frame_timecode
        assert (zone.zone_x_mm, zone.zone_y_mm, zone.zone_w_mm, zone.zone_h_mm) == (
            planned.zone_rect_mm
        )
        assert (zone.crop_x_mm, zone.crop_y_mm, zone.crop_w_mm, zone.crop_h_mm) == (
            planned.image_rect_mm
        )
        assert (zone.crop_x_px, zone.crop_y_px, zone.crop_w_px, zone.crop_h_px) == (
            planned.crop_x_px,
            planned.crop_y_px,
            planned.width_px,
            planned.height_px,
        )
        # Le chemin publie est celui que 5.6 a reellement ecrit, et le fichier
        # existe: la previz ne renvoie pas vers un fichier imaginaire.
        assert zone.frame_path_relative is not None
        assert (tmp_path / zone.frame_path_relative).is_file()
        # Le drapeau accompagne le chemin, `false` compris.
        assert zone.synthetic is False
        assert zone.synthetic_reason is None

    written_paths = {frame.path for frame in output_report.frames}
    assert {zone.frame_path_relative for zone in zones} == written_paths

    # Un lot reel et complet ne porte pas LOT_INCOMPLETE.
    assert document.warnings.previz == ()
    # Et les **trois** familles amont sont celles des vrais rapports, chacune
    # assertee contre son producteur. `warnings.ingest` ne l'etait dans aucun
    # des deux tests d'integration, et c'est precisement la famille qui etait
    # lue par `getattr` avec repli: les trois couches ont mesure que le mutant
    # de renommage **survivait a l'integration**, tue seulement par des
    # `SimpleNamespace` qui portent toujours le champ et ne peuvent donc rien
    # dire d'un renommage chez le producteur (AC 12).
    assert document.warnings.ingest == tuple(ingest_report.warnings)
    assert document.warnings.detection == tuple(detection_report.warnings)
    assert document.warnings.output == tuple(output_report.warnings)
    assert document.pages[0].warnings == ("FOREIGN_MARKER_DETECTED",)
    # Les vrais producteurs declarent bien le champ que le protocole exige.
    assert hasattr(ingest_report, "warnings") and hasattr(output_report, "warnings")

    # La forme normative se serialise sans objet Python residuel, sans chemin
    # absolu, et deux fois a l'identique.
    payload_json = scan_previz.scan_previz_to_json_dict(document)
    assert _iter_absolute_path_violations(payload_json) == []
    assert previz_common.canonical_json(payload_json) == previz_common.canonical_json(
        scan_previz.scan_previz_to_json_dict(document)
    )
    json.dumps(payload_json)


def test_a_real_synthetic_frame_is_seen_as_such_by_the_previz(tmp_path: Path) -> None:
    """La chaine complete d'EPIC5-ARB-8, de la mire ecrite au drapeau publie.

    Ce test tomberait si 5.6 cessait de marquer ses mires, si le motif changeait
    de vocabulaire, ou si la previz omettait le drapeau: c'est le seul endroit
    ou les deux morceaux sont confrontes.
    """
    from mixed_media_utility import (
        page_templates,
        scan_crop,
        scan_detection,
        scan_ingest,
        scan_output_frames,
    )
    from mixed_media_utility.io import naming, payload as payload_io

    dpi = 300
    rush_id = "rush-002"
    fps_target = 5.0
    template_id = page_templates.build_template_id("portrait", 2, "2")
    geometry = scan_detection.resolve_page_geometry(template_id, dpi)
    width_px, height_px = geometry["page_size_px"]

    scans_source = tmp_path / "source"
    scans_source.mkdir()
    assert cv2.imwrite(
        str(scans_source / "p001.tif"),
        np.full((height_px, width_px, 3), 32768, dtype=np.uint16),
    )
    ingest_report = scan_ingest.ingest_scan_lot(
        tmp_path, scans_source, dpi=dpi, ingest_slug="lot-mire"
    )

    payload = payload_io.build_page_payload(
        project_id="projet-test",
        rush_id=rush_id,
        lot_id=naming.build_lot_id(rush_id, fps_target),
        page_index=0,
        page_count=1,
        fps_target=fps_target,
        timecode_base_fps="25/1",
        template_id=template_id,
        patch_preset_id="patch-values-2",
        target_colorspace="bt709",
        gamut_map_id=payload_io.GAMUT_MAP_IDENTITY,
        slots=[
            {"slot_index": 0, "frame_timecode": "00:00:00:00"},
            {"slot_index": 1, "frame_timecode": "00:00:00:01"},
        ],
    )
    crop_plan = scan_crop.build_page_crop_plan(
        template_id=template_id, slots=payload["slots"], dpi=dpi
    )
    # Page presente et decodee dont la decoupe a echoue: 5.6 pose des mires.
    output_report = scan_output_frames.write_lot_output_frames(
        tmp_path,
        [
            scan_output_frames.ScannedPage(
                payload=payload, crop_plan=crop_plan, failure="frame_crop_failed"
            )
        ],
    )
    assert output_report.synthetic_frame_count == 2
    assert len(output_report.synthetic_frames) == 2

    ingested = ingest_report.pages[0]
    detected = scan_detection.DetectedPage(
        read_rank=ingested.read_rank,
        status=scan_detection.PAGE_REFUSED,
        locator_source=ingested.locator.source_path,
        locator_page_index=ingested.locator.page_index,
        qr_status=scan_detection.qr_codes.DECODE_OK,
        template_id=template_id,
        template_source="qr",
        project_id=payload["project_id"],
        rush_id=payload["rush_id"],
        lot_id=payload["lot_id"],
        page_index=payload["page_index"],
        page_count=payload["page_count"],
        gamut_map_id=payload["gamut_map_id"],
        frame_zones_mm=geometry["frame_zones_mm"],
        frame_zones_px=geometry["frame_zones_px"],
        refusal_reason="homographie non resolue",
        payload=payload,
    )
    document = scan_previz.build_scan_previz(
        ingest=ingest_report,
        detection=scan_detection.LotDetectionReport(
            ingest_slug=ingest_report.ingest_slug, scan_dpi=dpi, pages=(detected,)
        ),
        crop_plans={detected.read_rank: crop_plan},
        state=scan_previz.SCAN_PREVIZ_STATE_RECONSTRUCTED,
        output_report=output_report,
        generated_at_utc=GENERATED_AT,
        project_id=payload["project_id"],
        rush_id=payload["rush_id"],
        lot_id=payload["lot_id"],
        template_id=template_id,
        gamut_map_id=payload["gamut_map_id"],
        frames_written_count=output_report.observed_frame_count,
        frames_expected_count=output_report.expected_frame_count,
        synthetic_frame_count=len(output_report.synthetic_frames),
        # Le code se **transporte** depuis le rapport de 5.6, il ne se deduit
        # jamais du compteur.
        previz_warnings=tuple(
            code
            for code in output_report.warnings
            if code in scan_previz.SCAN_PREVIZ_WARNING_CODES
        ),
    )
    rendered_document = scan_previz.scan_previz_to_json_dict(document)
    zones = rendered_document["pages"][0]["frame_zones"]
    assert len(zones) == 2
    for zone in zones:
        assert zone["synthetic"] is True
        assert zone["synthetic_reason"] == "frame_crop_failed"
        assert (tmp_path / zone["frame_path_relative"]).is_file()
    # Le lot n'est jamais declare complet, meme si les cardinaux s'egalisent.
    assert document.counters.frames_written == document.counters.frames_expected
    assert "LOT_INCOMPLETE" in document.warnings.previz
    assert "SYNTHETIC_FRAME_WRITTEN" in document.warnings.previz
    assert "SYNTHETIC_FRAME_WRITTEN" in output_report.warnings


# ---------------------------------------------------------------------------
# Passe de correction de la revue en trois couches (2026-08-08)
# ---------------------------------------------------------------------------
#
# Chaque test de cette section ferme un finding **reproduit** par l'une des
# trois couches, ou tue un mutant survivant de la campagne. Le nom du finding
# est cite dans la docstring: une regression ici doit pouvoir se relire dans le
# rapport de revue qui l'a trouvee.


# --- Les protocoles: ce qui est declare est lu, ce qui est lu est declare ----


def test_the_protocols_declare_every_field_the_module_reads() -> None:
    """Convergence a trois voix de la revue: `warnings` etait lu par `getattr`.

    Un fournisseur qui implemente **exactement** les champs declares doit
    construire un document complet. Avant la correction, `warnings` etait lu
    par `getattr(x, "warnings", ())` sans etre declare aux protocoles: un
    renommage de champ chez 5.1 ou 5.6 ne levait rien et **vidait la famille en
    silence**, ce qui est nommement le mode de panne pour lequel l'AC 12
    existe.
    """
    declared_ingest = set(scan_previz.ScanIngestReportLike.__annotations__)
    declared_output = set(scan_previz.LotOutputReportLike.__annotations__)
    assert "warnings" in declared_ingest
    assert "warnings" in declared_output

    strict_ingest = SimpleNamespace(
        **{name: getattr(make_ingest(), name) for name in declared_ingest}
    )
    strict_output = SimpleNamespace(
        **{name: getattr(make_output_report(), name) for name in declared_output}
    )
    document = build_reconstructed(ingest=strict_ingest, output_report=strict_output)
    assert document.warnings.ingest == ("DPI_BELOW_QR_MINIMUM",)
    assert document.warnings.output == ("SYNTHETIC_FRAME_WRITTEN",)


@pytest.mark.parametrize("family", ["ingest", "output"])
def test_an_upstream_report_without_its_warnings_field_is_refused(family) -> None:
    """Le renommage de champ doit **casser**, pas vider une famille.

    C'est le seul regime tenable: `DPI_BELOW_QR_MINIMUM` ou
    `SYNTHETIC_FRAME_WRITTEN` qui n'atteignent jamais l'operateur est plus
    couteux qu'un refus a la construction. La famille `detection` etait deja
    dans ce regime, et l'ecart entre les trois etait le defaut.
    """
    if family == "ingest":
        report = make_ingest()
        del report.warnings
        with pytest.raises(SPE, match="structurellement incomplete"):
            build(ingest=report)
    else:
        report = make_output_report()
        del report.warnings
        with pytest.raises(SPE, match="structurellement incomplete"):
            build_reconstructed(output_report=report)


def test_the_ingested_page_protocol_declares_no_field_it_never_reads() -> None:
    """`IngestedPageLike.locator` etait declare et jamais lu (les trois couches).

    Le chemin source et l'index de page viennent du **locator de la detection**
    (5.2), pas du rapport d'ingestion: le sous-protocole `_PageLocatorLike` tout
    entier etait inatteignable, et la docstring de `ScanIngestReportLike`
    (« ce module lit ces champs et aucun autre ») s'en trouvait dementie.
    """
    assert not hasattr(scan_previz, "_PageLocatorLike")
    assert "locator" not in scan_previz.IngestedPageLike.__annotations__
    # Une page ingeree sans locator construit un document valide -- c'est la
    # preuve que le champ n'etait jamais lu.
    page = make_ingested_page()
    assert not hasattr(page, "locator")
    assert build().pages[0].source_path_relative == "scans/lot-a/p1.tif"


# --- Une frame ecrite que le document ne montre pas -------------------------


def test_a_written_frame_that_no_zone_claims_is_refused() -> None:
    """Couche 1 F1 / couche 2 finding 2: elles disparaissaient sans un mot.

    Trois gardes voisines du meme fichier refusent deja exactement ce mode
    d'echec en le nommant; la quatrieme manquait. Un lot dont 2 frames sur 3
    sont introuvables sortait **complet**.
    """
    with pytest.raises(SPE, match="aucune zone ou se poser"):
        build_reconstructed(
            output_report=make_output_report(
                frames=[
                    make_output_frame(page_index=3, slot_index=0, path="out/ok.tiff"),
                    make_output_frame(page_index=9, slot_index=0, path="out/orph.tiff"),
                    make_output_frame(page_index=3, slot_index=7, path="out/s7.tiff"),
                ]
            ),
            frames_written_count=3,
            frames_expected_count=3,
        )


def test_a_mire_without_a_zone_to_show_it_is_refused() -> None:
    """L'inverse exact d'EPIC5-ARB-8, atteint par l'autre bout.

    Une page refusee n'a pas de plan de decoupe -- c'est le regime normal -- et
    5.6 pose pourtant des mires pour cette page-la. Le document annoncait deux
    mires ecrites et n'en montrait **aucune**: « l'operateur doit voir la mire,
    pas seulement la lire dans un compteur ».
    """
    with pytest.raises(SPE, match="aucune zone ou se poser"):
        build_reconstructed(
            crop_plans=None,
            output_report=make_output_report(
                frames=[
                    make_output_frame(
                        slot_index=slot,
                        path=f"out/mire{slot}.tiff",
                        synthetic=True,
                        synthetic_reason="frame_crop_failed",
                    )
                    for slot in (0, 1)
                ]
            ),
            frames_written_count=2,
            frames_expected_count=2,
            synthetic_frame_count=2,
            previz_warnings=("SYNTHETIC_FRAME_WRITTEN",),
        )


def test_a_written_frame_claimed_by_two_zones_is_refused() -> None:
    """Couche 2 finding 4b: le meme fichier publie sur deux pages.

    `_frames_by_address` refuse deux frames a la meme adresse (« le chemin
    publie pour cette zone serait arbitraire »); la reciproque -- deux zones qui
    reclament la meme frame -- ne l'etait pas. Le diagnostic du lot melange
    reste entier en regime `detected`, ou aucune frame n'est ecrite.
    """
    detection = make_detection(
        pages=[make_detected_page(), make_detected_page(read_rank=1)]
    )
    kwargs = dict(
        ingest=make_ingest(pages=(make_ingested_page(), make_ingested_page(read_rank=1))),
        detection=detection,
        crop_plans={0: make_crop_plan(), 1: make_crop_plan()},
        calibration_status={0: "not_applied", 1: "not_applied"},
    )
    # Les deux pages declarent `page_index=3`: c'est le lot melange.
    assert {page.page_index for page in detection.pages} == {3}
    with pytest.raises(SPE, match="reclamees par plusieurs zones"):
        build_reconstructed(**kwargs)
    # En regime `detected`, rien n'est refuse: le diagnostic est intact.
    document = build(**kwargs)
    assert [page.page_index for page in document.pages] == [3, 3]


def test_every_written_frame_of_a_multi_page_lot_is_shown() -> None:
    """Le cas nominal de la garde: trois frames, trois zones, aucune perdue."""
    document = build_reconstructed(
        **make_multi_page_inputs(),
        output_report=make_multi_page_output_report(),
        frames_written_count=3,
        frames_expected_count=3,
    )
    published = [
        zone.frame_path_relative for page in document.pages for zone in page.frame_zones
    ]
    assert published == ["out/p3_s0.tiff", "out/p4_s0.tiff", "out/p4_s1.tiff"]


# --- La regle des fabriques: appariements, permutations, positions ----------


def test_a_multi_page_lot_pairs_every_element_by_its_own_key() -> None:
    """Cinq appariements, tous verifies sur la **seconde** page.

    Regle des fabriques (CLAUDE.md): un appariement fautif qui rend toujours le
    premier element ne se demasque que si les elements different et si la cible
    n'est pas en premiere position. Cinq mutants de la campagne vivaient de la
    fabrique mono-element: page ingeree appariee par position, plan de decoupe,
    statut de calibration, rectangle de zone en pixels apparie sans egard au
    nom, doublon de rang d'ingestion.
    """
    document = build(**make_multi_page_inputs())
    first, second = document.pages
    assert (first.read_rank, second.read_rank) == (0, 1)

    # 1. La page ingeree vient du **rang** et non de la position.
    assert (first.width_px, first.scan_input_format) == (10, "tiff")
    assert (second.width_px, second.height_px) == (21, 29)
    assert (second.scan_input_format, second.source_bit_depth, second.channels) == (
        "png",
        8,
        1,
    )

    # 2. Le plan de decoupe aussi: la seconde page a deux zones, la premiere une.
    assert len(first.frame_zones) == 1
    assert [zone.slot_index for zone in second.frame_zones] == [0, 1]
    assert [zone.frame_timecode for zone in second.frame_zones] == [
        "00:00:01:00",
        "00:00:02:00",
    ]

    # 3. Le statut de calibration aussi.
    assert first.calibration.status == "not_applied"
    assert second.calibration.status == "failed"

    # 4. Le rectangle de zone en pixels est pris **par nom de zone**.
    assert [
        (zone.zone_name, zone.zone_x_px, zone.zone_y_px, zone.zone_w_px, zone.zone_h_px)
        for zone in second.frame_zones
    ] == [("frame_zone_1", 11, 12, 13, 14), ("frame_zone_2", 21, 22, 23, 24)]

    # 5. Et les avertissements de page suivent leur page.
    assert first.warnings == ("PAGE_SCALE_OUT_OF_TOLERANCE",)
    assert second.warnings == ("PAGE_ASPECT_OUT_OF_TOLERANCE",)


def test_two_ingested_pages_of_the_same_read_rank_are_refused() -> None:
    """Le jumeau cote **ingestion** de la garde de detection.

    Il portait sa garde et son message, et aucun test ne l'atteignait: sans
    elle, la seconde page ecrase la premiere et le document decrit une page
    qu'il n'annonce pas.
    """
    ingest = make_ingest(
        pages=(make_ingested_page(), make_ingested_page(width_px=99))
    )
    with pytest.raises(SPE, match="deux pages de rang de lecture 0"):
        build(ingest=ingest)


def test_two_zones_of_the_same_slot_index_are_refused() -> None:
    """Couche 2 finding 10: l'adresse la plus fine du document, non gardee.

    C'est par elle que 7.4 dira « la zone 2 de la page 3 est mal placee ».
    """
    plan = make_crop_plan(
        frames=[make_crop_frame(slot_index=0), make_crop_frame(slot_index=0)]
    )
    with pytest.raises(SPE, match="deux emplacements d'index 0"):
        build(crop_plans={0: plan})


def test_two_zone_rects_of_the_same_name_are_refused() -> None:
    """Couche 1 F5 / couche 2 finding 9: la derniere gagnait, en silence."""
    page = make_detected_page(
        frame_zones_px=(
            {"name": "frame_zone_1", "x": 1, "y": 1, "width": 1, "height": 1},
            {"name": "frame_zone_1", "x": 100, "y": 200, "width": 300, "height": 400},
        )
    )
    with pytest.raises(SPE, match="deux zones nommees"):
        build(detection=make_detection(pages=[page]))


# --- Le socle partage: des regles ecrites, desormais pinnees ----------------


def test_the_canonical_form_stays_ascii_whatever_the_producer_carries() -> None:
    """`ensure_ascii=False` rendrait la forme canonique sensible a l'encodage.

    Le chemin est joignable sans rien d'exotique: un motif de refus accentue
    suffit. Deux chaines pour le meme document, donc **deux empreintes**.
    """
    accented = "homographie non résolue"
    document = build(
        detection=make_detection(
            pages=[make_detected_page(status="refused", refusal_reason=accented)]
        )
    )
    text = rendered(document)
    assert text.isascii()
    assert "\\u00e9" in text
    assert json.loads(text)["pages"][0]["refusal_reason"] == accented


@pytest.mark.parametrize(
    "value",
    [
        previz_common.FINGERPRINT_PREFIX + "a" * 64 + " suffixe",
        previz_common.FINGERPRINT_PREFIX + "a" * 64 + "\n",
        previz_common.FINGERPRINT_PREFIX + "A" * 64,
        previz_common.FINGERPRINT_PREFIX + "a" * 63,
    ],
)
def test_an_almost_complete_fingerprint_is_not_a_complete_one(value) -> None:
    """Deux gardes de la forme complete, chacune sans test avant la revue.

    `fullmatch` et non `match`: un suffixe apres les 64 hexadecimaux passait.
    Minuscules uniquement: deux documents portant le meme digest en deux casses
    se comparent inegaux tout en etant tous deux « valides ».
    """
    assert previz_common.is_complete_fingerprint(value) is False
    with pytest.raises(SPE, match="forme complete"):
        build(selection_fingerprint=value)


@pytest.mark.parametrize(
    "stamp",
    [
        "2026-08-08T12:00:00+02:00",
        "2026-08-08T12:00:00.5+02:00",
        "2026-08-08T12:00:00-05:00",
    ],
)
def test_a_timestamp_with_a_timezone_other_than_z_is_refused(stamp) -> None:
    """Un horodatage local rendrait la fraicheur ininterpretable.

    Le cas a secondes fractionnaires est celui qui compte: la garde d'instant
    reel ne rattrape plus (`split(".")[0]` rend un instant valide) et l'offset
    entrerait dans le document.
    """
    with pytest.raises(SPE, match="suffixe 'Z'"):
        build(generated_at_utc=stamp)


def test_a_boolean_never_passes_for_a_geometry_number() -> None:
    """Garde `bool`-avant-`int` de `require_number`, jumelle de celle des entiers.

    Action item 2 de la retro Epic 4: la garde des **entiers** etait testee,
    celle des **nombres** ne l'etait par personne -- dans le module meme que le
    Dev Agent Record designe comme « le seul domicile que les trois documents
    partagent ». Sans elle, `scale_x=True` traverse et sort `true` la ou un
    nombre est attendu.
    """
    page = make_detected_page(
        scale=SimpleNamespace(scale_x=True, scale_y=0.5, residual_px=-7.25)
    )
    with pytest.raises(SPE, match="doit etre un nombre"):
        build(detection=make_detection(pages=[page]))


@pytest.mark.parametrize("fps", ["1/0", 10**400, 0])
def test_an_unusable_frame_rate_stays_inside_the_module_hierarchy(fps) -> None:
    """`ZeroDivisionError` et `OverflowError` sortaient **nues** sans la clause.

    La docstring promet que tout refus de cadence est un `ScanPrevizError`; sans
    les deux exceptions supplementaires, deux entrees atteignables sortaient de
    la hierarchie promise.
    """
    with pytest.raises(SPE, match="Cadence inexploitable"):
        build(fps_target=fps)


def test_an_empty_string_never_passes_for_an_optional_text() -> None:
    """`optional_text` distingue « absent » de « vide », et rien ne le pinnait."""
    page = make_detected_page(template_source="")
    with pytest.raises(SPE, match="chaine non vide"):
        build(detection=make_detection(pages=[page]))


# --- L'enveloppe: un document se rend tel qu'il a ete construit -------------


def test_the_envelope_renders_the_version_of_the_document_not_the_constant() -> None:
    """Couche 1 F2 / couche 3 AC 13: la regle etait ecrite et prouvee nulle part.

    `envelope_head` prend la version de schema en **parametre** parce que relire
    la constante ferait mentir un document fige sous une version anterieure --
    exactement ce que la version d'enveloppe existe pour signaler. Quatre
    mutants de la campagne vivaient de l'absence de ce test, un par site.

    Le parametre est en outre **obligatoire**: son defaut relisait la constante,
    c'est-a-dire que la regle etait annulee par sa propre signature pour tout
    site d'appel qui oubliait l'argument.
    """
    import inspect

    signature = inspect.signature(previz_common.envelope_head)
    assert signature.parameters["schema_version"].default is inspect.Parameter.empty

    head = previz_common.envelope_head(
        kind="scan",
        state=scan_previz.SCAN_PREVIZ_STATE_DETECTED,
        generated_at_utc=GENERATED_AT,
        schema_version="previz-0",
    )
    assert head["previz_schema_version"] == "previz-0"
    assert set(head) == set(previz_common.ENVELOPE_FIELDS)


def test_a_document_frozen_under_an_older_envelope_renders_that_version() -> None:
    """La regle vue depuis le document, et non depuis le socle.

    Elle vaut pour les trois jumelles: les trois serialiseurs passent
    `schema_version=previz.previz_schema_version` a `envelope_head`, et le
    parametre est desormais obligatoire -- un site d'appel qui l'oublierait est
    un `TypeError`, plus un document qui ment.
    """
    import dataclasses

    document = build()
    stale = dataclasses.replace(document, previz_schema_version="previz-0")
    assert scan_previz.scan_previz_to_json_dict(stale)["previz_schema_version"] == (
        "previz-0"
    )
    assert scan_previz.scan_previz_to_json_dict(document)["previz_schema_version"] == (
        previz_common.PREVIZ_SCHEMA_VERSION
    )


def test_the_three_twin_serializers_pass_the_document_version_and_not_the_constant() -> None:
    """Les trois sites d'appel du socle, verifies sur l'arbre syntaxique.

    Le socle est partage et sa regle ne vaut que si les trois **passent la
    valeur du document**. Le parametre etant desormais obligatoire, un site qui
    l'oublierait est un `TypeError`; ce qui reste possible, c'est qu'un site
    passe la **constante du module** -- ce qui annulerait la regle sans rien
    casser, exactement comme le defaut relu de la premiere version.

    Verification par AST et non par `inspect.getsource`: la seconde depend des
    numeros de ligne, et rend un resultat faux des que le fichier a bouge sous
    le processus.
    """
    serializers = {
        MODULE_PATH: "scan_previz_to_json_dict",
        REPO_ROOT / "src" / "mixed_media_utility" / "extraction_previz.py": (
            "previz_to_json_dict"
        ),
        REPO_ROOT / "src" / "mixed_media_utility" / "pdf_previz.py": (
            "pdf_previz_to_json_dict"
        ),
    }
    for path, name in serializers.items():
        function = next(
            node
            for node in ast.walk(_tree(path))
            if isinstance(node, ast.FunctionDef) and node.name == name
        )
        calls = [
            node
            for node in ast.walk(function)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "envelope_head"
        ]
        assert len(calls) == 1, path
        keywords = {kw.arg: kw.value for kw in calls[0].keywords}
        assert set(keywords) == {"schema_version", "kind", "state", "generated_at_utc"}
        version = keywords["schema_version"]
        # `previz.previz_schema_version`, jamais `PREVIZ_SCHEMA_VERSION`.
        assert isinstance(version, ast.Attribute), (path, ast.dump(version))
        assert version.attr == "previz_schema_version"
        assert isinstance(version.value, ast.Name) and version.value.id == "previz"


# --- Deux valeurs qui coincident sur toutes les fixtures --------------------


def test_the_ingest_slug_is_never_derived_from_the_lot_id() -> None:
    """Troisieme famille de survivants du README: elles coincidaient partout."""
    document = build()
    assert document.subject.ingest_slug == "ingest-lot-a"
    assert document.subject.lot_id == "lot-a"
    assert document.subject.ingest_slug != document.subject.lot_id


def test_the_two_scan_dpi_are_never_confused() -> None:
    """5.2 distingue le DPI declare a l'ingestion du DPI de detection.

    Elle emet `SCAN_DPI_DIFFERS_FROM_INGESTED` precisement parce que les deux
    peuvent diverger, et c'est le second qui decide toute la geometrie.
    """
    document = build()
    assert document.subject.scan_dpi_declared == 600
    assert document.subject.scan_dpi_detection == 300


def test_changing_the_detection_scan_dpi_changes_the_fingerprint() -> None:
    """Couche 2 majeur 1 / couche 3 AC 8: le meme trou que 5.10, un champ plus loin.

    Le DPI de detection decide la taille de page redressee, les centres de
    marqueurs, l'homographie, `frame_zones_px` et le plan de decoupe qui en
    descend. La meme ingestion relue a deux DPI de detection rendait deux
    documents differents **sous une empreinte identique**.
    """
    assert "scan_dpi_detection" in scan_previz.DETECTION_FINGERPRINT_FIELDS
    assert (
        build().fingerprints.detection
        != build(detection=make_detection(scan_dpi=600)).fingerprints.detection
    )


# --- Gardes ecrites qu'aucun scenario ne faisait decider seules -------------


def test_a_mapping_that_is_not_a_mapping_is_refused() -> None:
    """Un objet dict-like non enregistre comme `Mapping` etait **accepte**."""

    class DictLike:
        def __init__(self):
            self._values = {0: make_crop_plan()}

        def __iter__(self):
            return iter(self._values)

        def get(self, key, default=None):
            return self._values.get(key, default)

    with pytest.raises(SPE, match="doit etre un mapping"):
        build(crop_plans=DictLike())


@pytest.mark.parametrize("key", [0.0, True, "0"])
def test_a_mapping_key_that_is_not_a_read_rank_is_refused(key) -> None:
    """Couche 2 finding 13: `0.0 == 0` et meme hash, donc `{0.0: plan}` passait.

    Le refus de `True` ne venait pas d'une garde de type mais du hasard de
    `frozenset({0})` qui ne contient pas `1`: sur un lot de deux pages,
    `{True: plan}` aurait vise la page de rang 1.
    """
    with pytest.raises(SPE):
        build(crop_plans={key: make_crop_plan()})


@pytest.mark.parametrize(
    "kwargs",
    [
        {"pages_expected_count": -5},
        {"frames_written_count": -1},
        {"frames_expected_count": -1},
        {"synthetic_frame_count": -1},
    ],
)
def test_a_negative_cardinal_is_refused(kwargs) -> None:
    """Les quatre cardinaux au meme regime.

    `pages_expected_count` passait par `optional_int` et acceptait -5 la ou les
    trois cardinaux de frames exigeaient « positif ou nul » (couche 2 finding 6).
    Le refus de confronter `pages_expected` a `pages_present` reste entier: il ne
    dit rien sur le signe.
    """
    with pytest.raises(SPE, match="cardinal positif ou nul"):
        build_reconstructed(**kwargs)


def test_a_synthetic_reason_is_never_read_on_a_real_frame() -> None:
    """La condition porte sur le **drapeau**, jamais sur la presence du motif.

    Un producteur qui laisse trainer un motif sur une vraie frame ne doit pas
    faire apparaitre « FRAME MANQUANTE » dans le document.
    """
    document = build_reconstructed(
        output_report=make_output_report(
            frames=[make_output_frame(synthetic=False, synthetic_reason="frame_crop_failed")]
        )
    )
    zone = document.pages[0].frame_zones[0]
    assert zone.synthetic is False
    assert zone.synthetic_reason is None


@pytest.mark.parametrize("value", [1, 0, "oui", [1], None])
def test_a_non_boolean_synthetic_flag_is_refused_by_both_paths(value) -> None:
    """Couche 2 finding 5: `bool(...)` coercait la ou tout le reste refuse.

    Le cas le plus couteux est `None`: un producteur qui **omet** le drapeau le
    voyait rendu `false`, c'est-a-dire « vraie frame » -- mot pour mot ce que le
    piege 8 interdit. La garde de `__post_init__` etait morte pour le chemin
    builder, `bool()` la desamorcant avant qu'elle ne voie la valeur.
    """
    with pytest.raises(SPE, match="doit etre un booleen"):
        build_reconstructed(
            output_report=make_output_report(
                frames=[make_output_frame(synthetic=value)]
            )
        )
    with pytest.raises(SPE, match="doit etre un booleen"):
        scan_previz.PrevizFrameZone(
            slot_index=0,
            frame_timecode=None,
            zone_name="frame_zone_1",
            zone_x_mm=0.0,
            zone_y_mm=0.0,
            zone_w_mm=1.0,
            zone_h_mm=1.0,
            crop_x_mm=0.0,
            crop_y_mm=0.0,
            crop_w_mm=1.0,
            crop_h_mm=1.0,
            crop_x_px=0,
            crop_y_px=0,
            crop_w_px=1,
            crop_h_px=1,
            frame_path_relative="out/f.tiff",
            synthetic=value if value is not None else 1,
        )


def test_a_non_boolean_clipping_verdict_is_refused() -> None:
    """Le verdict d'ecretage exige un vrai booleen, et rien ne le pinnait."""
    for value in (1, "oui", 0.0):
        with pytest.raises(SPE, match="booleen ou absent"):
            build(gamut_clipping={0: value})


def test_a_partial_zone_rect_in_pixels_is_refused() -> None:
    """Couche 2 finding 8: `zone_rect_px` n'etait conditionne que par `x`.

    Inatteignable par le builder -- les quatre valeurs y sortent du meme dict --
    mais `PrevizFrameZone` est publique et c'est 7.4 qui editera des zones.
    """
    base = dict(
        slot_index=0,
        frame_timecode=None,
        zone_name="frame_zone_1",
        zone_x_mm=0.0,
        zone_y_mm=0.0,
        zone_w_mm=1.0,
        zone_h_mm=1.0,
        crop_x_mm=0.0,
        crop_y_mm=0.0,
        crop_w_mm=1.0,
        crop_h_mm=1.0,
        crop_x_px=0,
        crop_y_px=0,
        crop_w_px=1,
        crop_h_px=1,
    )
    with pytest.raises(SPE, match="present en entier ou"):
        scan_previz.PrevizFrameZone(**base, zone_x_px=5, zone_y_px=None, zone_w_px=8, zone_h_px=9)
    with pytest.raises(SPE, match="present en entier ou"):
        scan_previz.PrevizFrameZone(**base, zone_x_px=None, zone_y_px=7, zone_w_px=8, zone_h_px=9)
    # Les quatre absents restent legitimes: une zone sans rectangle en pixels.
    assert scan_previz.PrevizFrameZone(**base).zone_x_px is None


@pytest.mark.parametrize(
    "field, value, message",
    [
        ("page_size_px", (10, 10, 10), "largeur, hauteur"),
        ("homography", tuple(float(i) for i in range(8)), "9 coefficients"),
        ("corner_centers", ((0, 1.0),), "marker_id, x, y"),
    ],
)
def test_a_geometry_of_the_wrong_shape_is_refused(field, value, message) -> None:
    """Trois gardes de forme, ecrites et jamais pinnees.

    Toutes trois atteignables par les geometries des vrais producteurs.
    """
    page = make_detected_page(**{field: value})
    with pytest.raises(SPE, match=message):
        build(detection=make_detection(pages=[page]))


def test_a_millimetre_rect_of_the_wrong_shape_is_refused() -> None:
    plan = make_crop_plan(zone_rect_mm=(35.0, 60.0, 140.0))
    with pytest.raises(SPE, match="4 composantes"):
        build(crop_plans={0: plan})


# --- Determinisme: une famille non ordonnee casse la promesse centrale -------


@pytest.mark.parametrize("family", ["ingest", "detection", "output"])
def test_an_unordered_warning_family_is_refused(family) -> None:
    """Couche 2 finding 7: quatre graines de hachage, quatre documents.

    Les trois familles amont sont transportees **verbatim**, donc dans l'ordre
    du producteur -- encore faut-il que cet ordre existe. L'ordre d'iteration
    d'un `set` Python depend de la graine du processus, et la promesse du module
    est « la meme chaine octet pour octet d'un processus a l'autre ».
    """
    unordered = {"DPI_BELOW_QR_MINIMUM", "MIXED_BIT_DEPTHS"}
    with pytest.raises(SPE, match="sequence \\*\\*ordonnee\\*\\*"):
        if family == "ingest":
            build(ingest=make_ingest(warnings=unordered))
        elif family == "detection":
            build(detection=make_detection(warnings=unordered))
        else:
            build_reconstructed(output_report=make_output_report(warnings=unordered))


# --- Les cinq vocabulaires fermes, verses par l'appelant --------------------


def test_the_caller_can_inject_the_five_closed_vocabularies() -> None:
    """Troisieme voie du dilemme pose au Dev Agent Record (couche 3).

    Le module ne peut ni importer ces vocabulaires (AC 11: ils vivent dans des
    modules qui tirent `cv2`) ni les recopier (ARB-14). Mais
    `previz_common.require_known_codes` prend le vocabulaire **en argument**:
    l'appelant, qui importe deja les producteurs, le verse. Cela ne viole ni
    l'AC 4 (qui interdit une **traduction**, pas une verification) ni l'AC 11
    (qui interdit un **import**).

    Ce sont **cinq** vocabulaires et non deux, et ils sont traites du meme
    regime: en controler deux seulement aurait cree deux regimes voisins pour le
    meme probleme.
    """
    from mixed_media_utility import (
        color_pipeline,
        scan_detection,
        scan_ingest,
        scan_output_frames,
    )

    vocabularies = dict(
        ingest_warning_vocabulary=scan_ingest.SCAN_INGEST_WARNING_CODES,
        detection_warning_vocabulary=scan_detection.SCAN_DETECTION_WARNING_CODES,
        output_warning_vocabulary=scan_output_frames.SCAN_OUTPUT_WARNING_CODES,
        synthetic_reason_vocabulary=scan_output_frames.SYNTHETIC_FRAME_REASONS,
        calibration_status_vocabulary=color_pipeline.CALIBRATION_STATUS_VALUES,
    )
    document = build_reconstructed(
        output_report=make_output_report(
            frames=[
                make_output_frame(synthetic=True, synthetic_reason="frame_crop_failed")
            ]
        ),
        synthetic_frame_count=1,
        **vocabularies,
    )
    assert document.pages[0].frame_zones[0].synthetic_reason == "frame_crop_failed"
    assert document.pages[0].calibration.status == "not_applied"


@pytest.mark.parametrize(
    "parameter, kwargs",
    [
        ("ingest_warning_vocabulary", {"ingest": lambda: make_ingest(warnings=("PAS_UN_CODE",))}),
        (
            "detection_warning_vocabulary",
            {"detection": lambda: make_detection(warnings=("PAS_UN_CODE",))},
        ),
        (
            "output_warning_vocabulary",
            {"output_report": lambda: make_output_report(warnings=("PAS_UN_CODE",))},
        ),
    ],
)
def test_an_injected_vocabulary_refuses_an_unknown_upstream_code(parameter, kwargs) -> None:
    """Le controle passe du temps de test au temps de construction.

    C'est la ou il protege un vrai consommateur, et non seulement la suite.
    """
    built = {name: factory() for name, factory in kwargs.items()}
    with pytest.raises(SPE, match="hors du vocabulaire verse par l'appelant"):
        build_reconstructed(**built, **{parameter: ("UN_CODE_CONNU",)})


def test_an_injected_vocabulary_refuses_an_unknown_synthetic_reason() -> None:
    from mixed_media_utility import scan_output_frames

    with pytest.raises(SPE, match="hors du vocabulaire verse par l'appelant"):
        build_reconstructed(
            output_report=make_output_report(
                frames=[make_output_frame(synthetic=True, synthetic_reason="pas_un_motif")]
            ),
            synthetic_frame_count=1,
            synthetic_reason_vocabulary=scan_output_frames.SYNTHETIC_FRAME_REASONS,
        )


def test_an_injected_vocabulary_refuses_an_unknown_calibration_status() -> None:
    from mixed_media_utility import color_pipeline

    with pytest.raises(SPE, match="hors du vocabulaire verse par l'appelant"):
        build(
            calibration_status={0: "presque_applique"},
            calibration_status_vocabulary=color_pipeline.CALIBRATION_STATUS_VALUES,
        )


def test_no_injected_vocabulary_keeps_the_original_regime() -> None:
    """`None` par defaut: un appelant qui ne veut pas payer ne paie pas."""
    document = build(calibration_status={0: "un_statut_inconnu"})
    assert document.pages[0].calibration.status == "un_statut_inconnu"


# --- La correspondance avec les cardinaux du manifest (AC 9) ----------------


def test_the_lot_cardinals_of_a_real_manifest_can_be_poured_in(tmp_path: Path) -> None:
    """Couche 3 AC 9: « la regle du manifest mot pour mot » n'etait pas verifiee.

    Le Dev Agent Record prescrivait a l'appelant de verser « ceux du manifest »
    sans dire lesquels, et le mapping naturel (`reconstructed_frame_count`) est
    **refuse a la construction**: il exclut les mires
    (`reconstructed = observed - len(S)`) alors que `frames_written` les inclut
    (« une frame de remplacement est une frame ecrite »). Aucun test ne versait
    de vrais cardinaux; celui-ci en verse, depuis un vrai document de manifest.
    """
    from mixed_media_utility.io import scan_manifest

    lot = {
        "reconstructed_frame_count": 1,
        "synthetic_frame_count": 1,
        "expected_frame_count": 2,
        "synthetic_frames": ["mire.tiff"],
    }
    # La correspondance nommee dans la docstring de `build_scan_previz`.
    written = lot["reconstructed_frame_count"] + lot["synthetic_frame_count"]
    document = build_reconstructed(
        output_report=make_output_report(
            frames=[
                make_output_frame(slot_index=0, path="out/reelle.tiff"),
                make_output_frame(
                    slot_index=1,
                    path="out/mire.tiff",
                    synthetic=True,
                    synthetic_reason="frame_crop_failed",
                ),
            ]
        ),
        crop_plans={
            0: make_crop_plan(
                frames=[make_crop_frame(slot_index=0), make_crop_frame(slot_index=1)]
            )
        },
        frames_written_count=written,
        frames_expected_count=lot["expected_frame_count"],
        synthetic_frame_count=lot["synthetic_frame_count"],
    )
    assert document.counters.frames_written == 2
    assert document.counters.synthetic_frame_count == 1
    # Le verdict est celui du manifest, dans les deux lectures.
    manifest_complete = (
        lot["reconstructed_frame_count"] == lot["expected_frame_count"]
        and lot["synthetic_frame_count"] == 0
    )
    assert manifest_complete is False
    assert scan_previz.LOT_INCOMPLETE in document.warnings.previz
    # Et le nom du cardinal du document est celui de l'AC 4, jamais l'homonyme
    # de la **collection** `lots[].synthetic_frames` (EPIC5-ARB-33).
    rendered_counters = scan_previz.scan_previz_to_json_dict(document)["counters"]
    assert "synthetic_frame_count" in rendered_counters
    assert "synthetic_frames" not in rendered_counters
    assert "synthetic_frames" in scan_manifest.SCAN_LOT_FIELDS


# --- Les constantes exportees: ni omission, ni invention --------------------


def test_the_envelope_fields_are_exactly_those_the_document_renders() -> None:
    """Un sous-ensemble n'attrape qu'une omission.

    La docstring de la constante annonce « qu'une jumelle n'en omet ni **n'en
    invente** aucun » (couche 2, finding 11), et la seule verification etait une
    inclusion.
    """
    document = scan_previz.scan_previz_to_json_dict(build())
    head = list(document)[: len(previz_common.ENVELOPE_FIELDS)]
    assert tuple(head) == previz_common.ENVELOPE_FIELDS


def test_every_address_carries_exactly_its_declared_fields() -> None:
    """Les trois constantes d'adresse contre les adresses reellement rendues."""
    document = scan_previz.scan_previz_to_json_dict(build_reconstructed())
    page = document["pages"][0]
    assert set(page["address"]) == set(scan_previz.PAGE_ADDRESS_FIELDS)
    for zone in page["frame_zones"]:
        assert set(zone["address"]) == set(scan_previz.FRAME_ZONE_ADDRESS_FIELDS)
    for marker in page["corner_markers"] + page["foreign_markers"]:
        assert set(marker["address"]) == set(scan_previz.MARKER_ADDRESS_FIELDS)


# ---------------------------------------------------------------------------
# Story 5.26 (AC 3): le document devient suffisant -- payload verbatim,
# condensat des octets du fichier source, et lecteur symetrique
# ---------------------------------------------------------------------------
#
# Regle des fabriques: tous les tests de cette section passent par
# `make_multi_page_inputs()` -- deux pages distinguables en tout point, toutes
# deux desordonnees (`read_rank` 0/1 contre `page_index` 3/4) -- et les
# assertions nominatives portent sur la page de rang **1**, la seconde.

# `page_role`, `template_id` et `patch_preset_id`: champs ajoutes par la
# revue de 5.26 (`_PAYLOAD_REQUIRED_FIELDS`) -- ce module ne valide toujours
# pas leur vocabulaire (qui appartient a `io/payload`), mais leur PRESENCE
# est desormais exigee a la frontiere, donc ces fabriques les portent.
PAYLOAD_RANG_0 = {
    "page_index": 3,
    "page_count": 7,
    "lot_id": "lot-a",
    "timecode_base_fps": "30/1",
    "page_role": page_roles.PAGE_ROLE_IMAGES,
    "template_id": "gabarit-a",
    "patch_preset_id": "preset-a",
    "slots": [{"slot_index": 0, "frame_timecode": "00:00:00:00"}],
}
PAYLOAD_RANG_1 = {
    "page_index": 4,
    "page_count": 7,
    "lot_id": "lot-a",
    "timecode_base_fps": "24000/1001",
    "page_role": page_roles.PAGE_ROLE_IMAGES,
    "template_id": "gabarit-a",
    "patch_preset_id": "preset-a",
    "slots": [{"slot_index": 0, "frame_timecode": "00:00:01:00"},
              {"slot_index": 1, "frame_timecode": "00:00:02:00"}],
}
DIGEST_RANG_0 = "sha256:" + "ab" * 32
DIGEST_RANG_1 = "sha256:" + "cd" * 32


def build_with_526_fields(**kwargs):
    """Document a deux pages desordonnees portant payloads et condensats."""
    defaults = dict(
        make_multi_page_inputs(),
        page_payloads={0: PAYLOAD_RANG_0, 1: PAYLOAD_RANG_1},
        source_digests={0: DIGEST_RANG_0, 1: DIGEST_RANG_1},
    )
    defaults.update(kwargs)
    return build(**defaults)


def test_le_payload_et_le_condensat_sont_transportes_verbatim_par_rang() -> None:
    """Appariement nominatif par `read_rank`, jamais positionnel: la cible est
    la page de rang 1 (page_index 4), pas la premiere."""
    document = scan_previz.scan_previz_to_json_dict(build_with_526_fields())
    seconde = next(p for p in document["pages"] if p["read_rank"] == 1)
    assert seconde["page_index"] == 4
    assert seconde["payload"] == PAYLOAD_RANG_1
    assert seconde["source_digest"] == DIGEST_RANG_1
    premiere = next(p for p in document["pages"] if p["read_rank"] == 0)
    assert premiere["payload"] == PAYLOAD_RANG_0
    assert premiere["source_digest"] == DIGEST_RANG_0


def test_le_payload_est_absent_sur_une_page_non_identifiee_jamais_null() -> None:
    """Discipline d'emission conditionnelle (meme regime que `synthetic`):
    absent quand il n'existe pas, present verbatim sinon, jamais `null`."""
    document = scan_previz.scan_previz_to_json_dict(
        build_with_526_fields(page_payloads={1: PAYLOAD_RANG_1})
    )
    premiere = next(p for p in document["pages"] if p["read_rank"] == 0)
    seconde = next(p for p in document["pages"] if p["read_rank"] == 1)
    assert "payload" not in premiere
    assert seconde["payload"] == PAYLOAD_RANG_1
    texte = previz_common.canonical_json(document)
    assert '"payload":null' not in texte
    assert '"source_digest":null' not in texte


def test_un_document_anterieur_a_5_26_se_rend_sans_les_deux_champs() -> None:
    """Additif sous `previz-1` (question ouverte 3): un document construit sans
    les deux champs reste octet pour octet celui d'avant la story -- la
    fixture canonique figee de 5.8 le prouve deja, ceci le dit nommement."""
    texte = rendered(build())
    assert '"payload"' not in texte
    assert '"source_digest"' not in texte


def test_les_deux_champs_neufs_n_entrent_pas_dans_l_empreinte() -> None:
    """`DETECTION_FINGERPRINT_FIELDS` ne bouge pas: meme document avec et sans
    les deux champs -> meme empreinte de detection."""
    assert scan_previz.DETECTION_FINGERPRINT_FIELDS == (
        "gamut_map_id",
        "ingested_pages_digest",
        "lot_id",
        "project_id",
        "rush_id",
        "scan_dpi_declared",
        "scan_dpi_detection",
        "template_id",
    )
    sans = build(**make_multi_page_inputs())
    avec = build_with_526_fields()
    assert avec.fingerprints.detection == sans.fingerprints.detection


def test_un_payload_qui_n_est_pas_un_objet_est_refuse() -> None:
    with pytest.raises(SPE, match="payload"):
        build_with_526_fields(page_payloads={1: "pas-un-objet"})


def test_un_rang_inconnu_dans_les_deux_mappings_neufs_est_refuse() -> None:
    """Meme regle que `crop_plans`: un rang inconnu serait ignore en silence."""
    with pytest.raises(SPE, match="page_payloads"):
        build_with_526_fields(page_payloads={9: PAYLOAD_RANG_0})
    with pytest.raises(SPE, match="source_digests"):
        build_with_526_fields(source_digests={9: DIGEST_RANG_0})


def test_le_determinisme_tient_avec_les_deux_champs_neufs() -> None:
    """Deux serialisations du meme document: la meme chaine octet pour octet,
    `payload` et `source_digest` compris."""
    assert rendered(build_with_526_fields()) == rendered(build_with_526_fields())


def test_l_aller_retour_complet_rend_un_objet_egal() -> None:
    """build -> to_json_dict -> canonical_json -> relecture -> objet EGAL,
    sur un document a deux pages distinguables, toutes deux desordonnees."""
    document = build_with_526_fields()
    texte = rendered(document)
    relu = scan_previz.scan_previz_from_json_dict(json.loads(texte))
    assert relu == document
    # Et la re-serialisation du relu rend la meme chaine: le lecteur n'a rien
    # complete ni corrige.
    assert rendered(relu) == texte


def test_l_aller_retour_tient_aussi_en_regime_reconstructed() -> None:
    document = build_reconstructed()
    texte = rendered(document)
    relu = scan_previz.scan_previz_from_json_dict(json.loads(texte))
    assert relu == document


def test_l_aller_retour_tient_sur_un_document_anterieur_sans_les_champs() -> None:
    """Le lecteur relit un document de 5.25 (champs absents -> `None`): le
    refus du document anterieur appartient au consommateur d'ecriture, jamais
    au lecteur -- la forme `previz-1` est additive."""
    document = build(**make_multi_page_inputs())
    relu = scan_previz.scan_previz_from_json_dict(json.loads(rendered(document)))
    assert relu == document
    assert all(page.payload is None for page in relu.pages)
    assert all(page.source_digest is None for page in relu.pages)


@pytest.mark.parametrize(
    "casse, motif",
    [
        (lambda d: "pas un objet", "objet JSON"),
        (lambda d: {**d, "kind": "extraction"}, "pas une previz de scan"),
        (lambda d: {**d, "previz_schema_version": "previz-2"}, "Version d'enveloppe"),
        (lambda d: {**d, "state": "written"}, "Etat de previz inconnu"),
        (lambda d: {k: v for k, v in d.items() if k != "subject"}, "'subject' absent"),
        (lambda d: {**d, "generated_at_utc": "hier"}, "generated_at_utc"),
    ],
)
def test_le_lecteur_refuse_nommement_les_documents_inexploitables(casse, motif) -> None:
    document = json.loads(rendered(build_with_526_fields()))
    with pytest.raises(SPE, match=motif):
        scan_previz.scan_previz_from_json_dict(casse(document))


def test_le_lecteur_refuse_une_adresse_qui_contredit_son_porteur() -> None:
    """La seule redondance du document (frontiere 7.4) se revalide: refus,
    jamais reparation -- et sur la SECONDE page, pas la premiere."""
    document = json.loads(rendered(build_with_526_fields()))
    seconde = next(p for p in document["pages"] if p["read_rank"] == 1)
    seconde["address"]["page_index"] = 99
    with pytest.raises(SPE, match="contredit son porteur"):
        scan_previz.scan_previz_from_json_dict(document)


def test_le_lecteur_refuse_des_compteurs_qui_contredisent_les_pages() -> None:
    document = json.loads(rendered(build_with_526_fields()))
    document["counters"]["pages_present"] = 5
    with pytest.raises(SPE, match="pages_present"):
        scan_previz.scan_previz_from_json_dict(document)


def test_le_lecteur_refuse_un_lot_incomplete_qui_contredit_les_compteurs() -> None:
    """`LOT_INCOMPLETE` est deduit a la construction; a la relecture il doit
    dire ce que les compteurs disent -- dans les deux sens."""
    complet = json.loads(rendered(build_reconstructed()))
    assert scan_previz.LOT_INCOMPLETE not in complet["warnings"]["previz"]
    complet["warnings"]["previz"] = [scan_previz.LOT_INCOMPLETE]
    with pytest.raises(SPE, match="contredit les compteurs"):
        scan_previz.scan_previz_from_json_dict(complet)

    incomplet = json.loads(rendered(build_reconstructed(
        output_report=make_output_report(
            frames=[make_output_frame()],
            warnings=("SYNTHETIC_FRAME_WRITTEN",),
        ),
        frames_written_count=1,
        frames_expected_count=2,
        synthetic_frame_count=0,
    )))
    assert scan_previz.LOT_INCOMPLETE in incomplet["warnings"]["previz"]
    incomplet["warnings"]["previz"] = []
    with pytest.raises(SPE, match="contredit les compteurs"):
        scan_previz.scan_previz_from_json_dict(incomplet)


def test_le_lecteur_revalide_l_invariant_du_drapeau_synthetique() -> None:
    """Un `synthetic` sans chemin de frame dans le fichier tombe dans la garde
    de `PrevizFrameZone.__post_init__` -- la meme qu'a la construction."""
    document = json.loads(rendered(build_with_526_fields()))
    seconde = next(p for p in document["pages"] if p["read_rank"] == 1)
    seconde["frame_zones"][1]["synthetic"] = False
    with pytest.raises(SPE, match="synthetic"):
        scan_previz.scan_previz_from_json_dict(document)


# ---------------------------------------------------------------------------
# Revue de 5.26 (findings [Review][Patch]): unicite de `page_index`,
# asymetrie du `null` explicite, champs requis du payload.
# ---------------------------------------------------------------------------


def _reecrire_le_page_index(page_dict: dict, nouvel_index) -> None:
    """Reecrit `page_index` a TOUTES les adresses imbriquees d'une page (le
    champ top-level, `address`, celles des marqueurs et zones, et celle du
    payload) -- **sauf** `source.page_index`, qui est un champ different
    (`source_page_index` / `locator_page_index`, l'index dans le PDF source,
    jamais l'adresse de detection). Utilitaire de test, pour garder une page
    internement coherente (adresse <-> porteur, payload <-> porteur) tout en
    la faisant collisionner avec une autre page du document, ou en la rendant
    muette."""
    page_dict["page_index"] = nouvel_index
    page_dict["address"]["page_index"] = nouvel_index
    for cle in ("corner_markers", "foreign_markers"):
        for item in page_dict.get(cle, []):
            item["address"]["page_index"] = nouvel_index
    for zone in page_dict.get("frame_zones", []):
        zone["address"]["page_index"] = nouvel_index
    if page_dict.get("payload") is not None:
        page_dict["payload"]["page_index"] = nouvel_index


def test_deux_pages_du_meme_page_index_sont_refusees() -> None:
    """Finding [Review][Patch] 1: un `page_index` duplique traverse le
    lecteur sans refus (`scan_previz.py:2823-2839`) -- deux pages au meme
    `page_index` mais de `read_rank` distincts ne sont pas attrapees par la
    garde de rang de lecture, et collisionneraient sur le meme nom de frame
    de sortie a l'ecriture: une page en ecraserait une autre.

    Regle des fabriques (CLAUDE.md): la page fautive est mise en SECONDE
    position (read_rank 1, page_index 4 -> 3), pas la premiere -- un refus
    qui ne regarderait que la premiere page ne se demasquerait pas
    autrement.
    """
    document = json.loads(rendered(build_with_526_fields()))
    premiere = next(p for p in document["pages"] if p["read_rank"] == 0)
    seconde = next(p for p in document["pages"] if p["read_rank"] == 1)
    assert premiere["page_index"] == 3
    _reecrire_le_page_index(seconde, premiere["page_index"])
    with pytest.raises(SPE, match="deux pages du meme page_index"):
        scan_previz.scan_previz_from_json_dict(document)


def test_plusieurs_pages_muettes_au_page_index_null_restent_acceptees() -> None:
    """`None` est exclu du controle d'unicite: deux pages au QR non lu sont
    legitimement muettes, sans que cela les rende indiscernables entre
    elles (elles ne portent aucune frame a nommer)."""
    document = json.loads(rendered(build_with_526_fields()))
    for page in document["pages"]:
        del page["payload"]
        page.pop("source_digest", None)
        _reecrire_le_page_index(page, None)
    relu = scan_previz.scan_previz_from_json_dict(document)
    assert [page.page_index for page in relu.pages] == [None, None]


def test_un_payload_explicitement_null_est_refuse_jamais_une_absence() -> None:
    """Finding [Review][Patch] 2: `"payload": null` etait traite comme un
    payload absent (page mutique legitime) alors que `"source_digest": null`
    etait deja refuse -- asymetrie corrigee (`scan_previz.py:2633-2640`). Une
    corruption qui viderait le payload doit etre refusee, jamais confondue
    avec une page non identifiee (qui, elle, OMET la cle)."""
    document = json.loads(rendered(build_with_526_fields()))
    seconde = next(p for p in document["pages"] if p["read_rank"] == 1)
    seconde["payload"] = None
    with pytest.raises(SPE, match="payload.*null"):
        scan_previz.scan_previz_from_json_dict(document)


def test_l_absence_de_la_cle_payload_reste_une_absence_legitime() -> None:
    """Symetrique du test ci-dessus: la cle OMISE (jamais posee `null`) est
    toujours lue comme une page non identifiee -- la forme `previz-1` reste
    additive (5.25)."""
    document = json.loads(rendered(build_with_526_fields()))
    seconde = next(p for p in document["pages"] if p["read_rank"] == 1)
    del seconde["payload"]
    relu = scan_previz.scan_previz_from_json_dict(document)
    page_de_rang_1 = next(p for p in relu.pages if p.read_rank == 1)
    assert page_de_rang_1.payload is None


@pytest.mark.parametrize("champ_absent", ["page_index", "page_role", "template_id",
                                           "patch_preset_id", "slots"])
def test_un_payload_qui_omet_un_champ_requis_est_refuse(champ_absent) -> None:
    """Finding [Review][Patch] 3: `_page_payload` ne validait la nature de
    l'objet (`isinstance(value, Mapping)`) mais aucun champ requis
    (`scan_previz.py:1712-1726`) -- un mapping arbitraire traversait la
    construction et faisait echouer bien plus loin, par une `KeyError`
    brute, un des acces positionnels de `_ecrire_le_lot_detecte` /
    `_scanned_pages_for_output` (`payload["page_role"]`,
    `payload["template_id"]`...). Parametre sur les cinq champs que ces deux
    fonctions accedent sans repli (`cli.py`)."""
    document = json.loads(rendered(build_with_526_fields()))
    seconde = next(p for p in document["pages"] if p["read_rank"] == 1)
    del seconde["payload"][champ_absent]
    with pytest.raises(SPE, match="omet le\\(s\\) champ\\(s\\) requis"):
        scan_previz.scan_previz_from_json_dict(document)


def test_un_payload_dont_le_page_index_contredit_celui_de_sa_page_est_refuse() -> None:
    """Edge Case Hunter (finding [Review][Patch] 3): le cas precis d'un
    `page_index` de payload en DESACCORD avec `page.page_index` -- distinct
    du champ absent ci-dessus, et non attrape par la garde d'adresse
    (`address.page_index`), qui ne regarde que l'adresse de la page, jamais
    le contenu du payload transporte verbatim."""
    document = json.loads(rendered(build_with_526_fields()))
    seconde = next(p for p in document["pages"] if p["read_rank"] == 1)
    assert seconde["page_index"] == 4
    seconde["payload"]["page_index"] = 99
    with pytest.raises(SPE, match="payload\\['page_index'\\].*contredit"):
        scan_previz.scan_previz_from_json_dict(document)


# ---------------------------------------------------------------------------
# Story 5.27: le code de refus enumere, du coeur au document
# ---------------------------------------------------------------------------
#
# La regle des fabriques s'applique ici a la lettre: le document est une
# **collection de pages** adressee par rang, et un transport fautif qui rendrait
# toujours le premier code, ou qui poserait le meme code partout, ne se demasque
# que sur deux pages refusees pour deux motifs **differents**, la page visee en
# **seconde** position. C'est la famille de defaut de 5.6 (`M33`), 5.7 (`M25`)
# et 5.8; elle ne se trouve que par mutation, jamais par relecture.

# Le vocabulaire du producteur est **importe**, jamais recopie: c'est la meme
# discipline que `test_every_warning_code_with_a_producer_is_spelled_like_its_producer`
# (point H5.4), et c'est ce qui fait tomber ce fichier si `scan_detection`
# renomme un code. L'interdit d'import ne porte que sur le module de production
# (`test_module_never_imports_one_of_the_five_producers`), jamais sur ses tests.
from mixed_media_utility import scan_detection  # noqa: E402

#: Deux motifs qui ne se ressemblent pas, et qu'un operateur traite
#: differemment: une planche perimee se reimprime, une page dont un coin manque
#: se rescanne. C'est exactement la paire que 7.4 doit pouvoir distinguer sans
#: lire une phrase.
REFUS_PREMIERE_PAGE = (
    scan_detection.REFUS_COINS_MANQUANTS,
    "Marqueurs ArUco de coin manquants: [2]. IDs attendus: [0, 1, 2, 3].",
)
REFUS_SECONDE_PAGE = (
    scan_detection.REFUS_PLANCHE_PERIMEE,
    "Planche perimee: schema 1.0 la ou 2.0 est attendu. Reimprimer la planche.",
)


def make_deux_pages_refusees(*, permute: bool = False):
    """Deux pages refusees distinguables, la **cible en seconde position**.

    `permute` echange les deux motifs sans rien changer d'autre: c'est ce qui
    donne leur valeur aux deux points precedents. Sans lui, un transport qui
    rendrait toujours le premier code passerait les deux tests.
    """
    premier, second = REFUS_PREMIERE_PAGE, REFUS_SECONDE_PAGE
    if permute:
        premier, second = second, premier
    entrees = make_multi_page_inputs()
    pages = list(entrees["detection"].pages)
    for page, (code, phrase) in zip(pages, (premier, second)):
        page.status = "refused"
        page.refusal_code = code
        page.refusal_reason = phrase
    entrees["detection"] = make_detection(pages=pages)
    return entrees


def _page_par_rang(document, rank: int):
    return next(page for page in document["pages"] if page["read_rank"] == rank)


def _asserter_les_deux_refus(document) -> None:
    """L'appariement rang -> (code, phrase), asserte page par page."""
    for rank, (code, phrase) in enumerate((REFUS_PREMIERE_PAGE, REFUS_SECONDE_PAGE)):
        page = _page_par_rang(document, rank)
        assert page["refusal_code"] == code, rank
        assert page["refusal_reason"] == phrase, rank


def test_le_code_de_refus_voyage_jusqu_au_document_sous_sa_cle_gelee() -> None:
    """AC 6: apres serialisation JSON complete, chaque page rend SON code.

    La cle est `refusal_code`, celle que `gui.lecture_detection` nomme deja
    (`CLE_CODE_DE_REFUS`, story 7.4, livree avant ce producteur): la nommer
    autrement laisserait l'ecran sur son repli permanent pour toujours.
    """
    document = json.loads(rendered(build(**make_deux_pages_refusees())))
    _asserter_les_deux_refus(document)
    # Deux motifs distincts, et non un remplissage uniforme.
    assert (
        _page_par_rang(document, 0)["refusal_code"]
        != _page_par_rang(document, 1)["refusal_code"]
    )


def test_permuter_les_deux_motifs_fait_echouer_l_assertion() -> None:
    """Ce que ce test mesure, c'est le test precedent.

    Une fixture a deux pages ne prouve rien si l'assertion passe aussi quand
    les deux motifs sont echanges: elle ne mesurerait que « un code est pose ».
    """
    document = json.loads(rendered(build(**make_deux_pages_refusees(permute=True))))
    with pytest.raises(AssertionError):
        _asserter_les_deux_refus(document)


def test_le_code_de_refus_survit_a_l_aller_retour_json() -> None:
    document = build(**make_deux_pages_refusees())
    relu = scan_previz.scan_previz_from_json_dict(json.loads(rendered(document)))
    assert relu == document
    assert [page.refusal_code for page in relu.pages] == [
        REFUS_PREMIERE_PAGE[0],
        REFUS_SECONDE_PAGE[0],
    ]
    # Et la phrase francaise est la, a cote, inchangee.
    assert [page.refusal_reason for page in relu.pages] == [
        REFUS_PREMIERE_PAGE[1],
        REFUS_SECONDE_PAGE[1],
    ]


def test_une_page_acceptee_ne_porte_aucun_code() -> None:
    """AC 7: `None`, jamais une chaine vide, jamais un code par defaut."""
    document = json.loads(rendered(build()))
    page = _page_par_rang(document, 0)
    assert page["status"] == "ok"
    assert page["refusal_code"] is None
    assert page["refusal_reason"] is None


def test_un_document_ecrit_avant_la_story_reste_relisible_et_rend_none() -> None:
    """AC 7, second volet: la cle **absente** est une valeur -- celle d'un
    document que ce producteur n'avait pas encore appris a ecrire. Le repli de
    7.4 (« la phrase seule, jamais de code invente ni derive ») est permanent,
    et c'est ce cas-la qu'il couvre pour toujours."""
    document = json.loads(rendered(build(**make_deux_pages_refusees())))
    for page in document["pages"]:
        del page["refusal_code"]
    relu = scan_previz.scan_previz_from_json_dict(document)
    assert [page.refusal_code for page in relu.pages] == [None, None]
    # La phrase, elle, est toujours la: le document anterieur n'en manquait pas.
    assert [page.refusal_reason for page in relu.pages] == [
        REFUS_PREMIERE_PAGE[1],
        REFUS_SECONDE_PAGE[1],
    ]


def test_un_code_de_refus_mal_forme_ne_rend_pas_le_document_illisible() -> None:
    """Inversion de la decision d'ecriture initiale (finding `BH-8`).

    Ce test exigeait l'inverse -- `refusal_code: 42` faisait refuser tout le
    document. Mesure de la couche 1 sur le document terrain
    `tests/fixtures/detection-scan-reelle/detect-ok-et-refus.json`: cette forme
    rendait **un scan entier illisible dans l'ecran**, alors qu'avant 5.27 la
    cle etait inconnue du coeur et que la GUI l'ignorait en silence. Une story
    qui ajoute un champ informatif ne peut pas durcir la lecture d'une story
    close (7.4, `done`).

    Le detail des formes tolerees, et le pendant qui borne la tolerance,
    vivent plus bas (`CODES_QUI_VALENT_ABSENT`,
    `test_la_phrase_de_refus_garde_sa_garde_entiere`).
    """
    document = json.loads(rendered(build(**make_deux_pages_refusees())))
    _page_par_rang(document, 1)["refusal_code"] = 42
    relu = scan_previz.scan_previz_from_json_dict(document)
    assert relu.pages[1].refusal_code is None


def test_un_code_inconnu_du_coeur_est_transporte_verbatim_pas_refuse() -> None:
    """Decision d'ecriture 2: valide a l'**emission**, transporte verbatim a la
    lecture -- sur le modele de `fingerprints.selection`, et non sur celui de
    `SCAN_PREVIZ_WARNING_CODES` qui rend le document illisible.

    Motif: un document est relu par des versions differentes du logiciel --
    c'est le sens meme de 5.26, qui lit un document ecrit « dans un AUTRE
    processus, la veille ». Refuser tout un scan parce qu'une version
    ulterieure a ajoute un code le rendrait illisible pour un champ purement
    informatif.
    """
    inconnu = "un-code-que-cette-version-ne-connait-pas"
    assert inconnu not in scan_detection.SCAN_REFUSAL_CODES
    document = json.loads(rendered(build(**make_deux_pages_refusees())))
    _page_par_rang(document, 1)["refusal_code"] = inconnu
    relu = scan_previz.scan_previz_from_json_dict(document)
    assert relu.pages[1].refusal_code == inconnu


def test_le_champ_de_decision_du_coeur_est_bien_celui_du_document() -> None:
    """Le transport est mesure contre le **vrai** producteur, pas contre un
    `SimpleNamespace`: un renommage du champ chez `scan_detection` doit tomber
    ici, et un `SimpleNamespace` qui porte toujours le champ ne peut rien en
    dire (mesure de la revue de 5.25 sur `warnings.ingest`)."""
    assert "refusal_code" in scan_detection.DetectedPage.__dataclass_fields__
    page = scan_detection.DetectedPage(
        read_rank=0,
        status=scan_detection.PAGE_REFUSED,
        locator_source="scans/lot-a/p1.tif",
        locator_page_index=None,
        qr_status="decoded",
        refusal_reason=REFUS_PREMIERE_PAGE[1],
        refusal_code=REFUS_PREMIERE_PAGE[0],
    )
    assert page.as_document()["refusal_code"] == REFUS_PREMIERE_PAGE[0]


def test_l_empreinte_de_detection_ne_bouge_pas_avec_le_code_de_refus() -> None:
    """AC 9. Le tuple est **ferme** et asserte a sa valeur du baseline: y faire
    entrer le code de refus declarerait perimes tous les documents deja ecrits,
    et `scan write` (5.26) les refuserait tous en bloc."""
    assert scan_previz.DETECTION_FINGERPRINT_FIELDS == (
        "gamut_map_id",
        "ingested_pages_digest",
        "lot_id",
        "project_id",
        "rush_id",
        "scan_dpi_declared",
        "scan_dpi_detection",
        "template_id",
    )
    avec = build(**make_deux_pages_refusees())
    entrees = make_deux_pages_refusees()
    for page in entrees["detection"].pages:
        page.refusal_code = None
    sans = build(**entrees)
    assert avec.fingerprints.detection == sans.fingerprints.detection
    # Et les deux documents different bien par ailleurs: sans quoi l'egalite
    # ci-dessus ne dirait rien.
    assert rendered(avec) != rendered(sans)


def test_le_vocabulaire_de_previz_reste_inchange_par_cette_story() -> None:
    """AC 10: cette story n'ajoute aucun etat, aucun statut, aucun
    avertissement aux vocabulaires existants."""
    # Aucun bump: le champ est additif a defaut `None`, sur le precedent ecrit
    # de 5.26 (`payload` et `source_digest`, sans bump eux non plus).
    assert scan_previz.PREVIZ_SCHEMA_VERSION == "previz-1"
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


#: Tout ce qui, sur ce champ, ne porte **aucun code exploitable** et doit donc
#: valoir `None` sans jamais rendre le document illisible.
#:
#: Les deux dernieres familles sont des corrections de revue de vague 2 bis:
#:
#: * la chaine **uniquement blanche** (`EC-9`) -- `require_text` ne fait aucun
#:   `strip`, si bien que `"   "` traversait et ressortait verbatim, et l'ecran
#:   affichait un badge de code vide, exactement ce que la regle interdit;
#: * la valeur **non textuelle** (`BH-8`) -- elle faisait refuser tout le
#:   document, et donc rendait illisible dans l'ecran un scan entier sur un
#:   champ purement informatif. C'est l'inverse exact de l'argument qui fonde
#:   la tolerance au vide, et c'etait un durcissement de la lecture d'une story
#:   close (7.4) qu'aucune AC n'a demande.
CODES_QUI_VALENT_ABSENT: tuple = ("", "   ", "\t", "\n  \t ", 42, [], {}, 3.5, True, None)


@pytest.mark.parametrize("valeur", CODES_QUI_VALENT_ABSENT, ids=repr)
def test_un_code_de_refus_sans_contenu_vaut_absent_a_la_relecture(valeur) -> None:
    """Regression trouvee en faisant tourner la suite de 7.4, story `done`.

    `gui/lecture_detection` a une regle ecrite -- « un code vide se lirait comme
    un code, ce qui est pire que pas de code » -- et un test qui la mesure sur
    un document portant `refusal_code: ""`. Avant 5.27, la cle etait **inconnue
    du lecteur** et traversait sans controle ; le garde-fou de la GUI faisait
    seul le travail. Poser le champ ici avec `_optional_text` a rendu le
    document **entier illisible** sur cette valeur, donc casse un test d'une
    story fermee -- que cette story n'a pas le droit de modifier (AC 10).

    La regle retenue est celle du consommateur, appliquee a la source: sur ce
    champ, **rien d'exploitable vaut absent**, et rien de ce qui y arrive ne
    peut rendre le document illisible. Ce n'est pas un relachement de garde
    generalise: c'est la portee exacte d'un champ purement informatif. La
    phrase francaise, qui est ce que l'operateur lit, garde sa garde entiere
    (`test_la_phrase_de_refus_garde_sa_garde_entiere`).
    """
    document = json.loads(rendered(build(**make_deux_pages_refusees())))
    _page_par_rang(document, 1)["refusal_code"] = valeur
    relu = scan_previz.scan_previz_from_json_dict(document)
    assert relu.pages[1].refusal_code is None
    # La phrase, elle, est intacte: c'est le code qui manque, pas le motif.
    assert relu.pages[1].refusal_reason == REFUS_SECONDE_PAGE[1]
    # Et le premier code, lui, n'a pas bouge: le vide de l'un n'efface pas
    # l'autre.
    assert relu.pages[0].refusal_code == REFUS_PREMIERE_PAGE[0]


@pytest.mark.parametrize("valeur", CODES_QUI_VALENT_ABSENT, ids=repr)
def test_un_code_sans_contenu_venu_du_COEUR_vaut_absent_lui_aussi(valeur) -> None:
    """La meme regle aux deux bouts, sans quoi la doctrine du module tombe:
    « le lecteur valide a la relecture ce que `build_scan_previz` valide a la
    construction ». Un producteur qui rendrait `""` ne doit pas faire echouer
    la construction la ou la relecture la laisse passer."""
    entrees = make_deux_pages_refusees()
    list(entrees["detection"].pages)[1].refusal_code = valeur
    document = build(**entrees)
    assert document.pages[1].refusal_code is None
    assert json.loads(rendered(document))["pages"][1]["refusal_code"] is None
    # Et le code de l'autre page traverse, lui: la tolerance porte sur la
    # valeur sans contenu, pas sur le champ.
    assert document.pages[0].refusal_code == REFUS_PREMIERE_PAGE[0]


@pytest.mark.parametrize("valeur", ["  planche-perimee  ", "planche-perimee"])
def test_un_code_qui_porte_du_contenu_traverse_verbatim(valeur) -> None:
    """Le pendant des deux tests precedents: `rien d'exploitable vaut absent`
    ne doit pas deriver en `tout vaut absent`.

    Le transport est **verbatim**, blancs de bordure compris: le `strip` sert a
    decider si la valeur porte quelque chose, il ne normalise pas ce qu'elle
    porte. Un consommateur qui compare deux documents compare des octets.
    """
    document = json.loads(rendered(build(**make_deux_pages_refusees())))
    _page_par_rang(document, 1)["refusal_code"] = valeur
    relu = scan_previz.scan_previz_from_json_dict(document)
    assert relu.pages[1].refusal_code == valeur

    entrees = make_deux_pages_refusees()
    list(entrees["detection"].pages)[1].refusal_code = valeur
    assert build(**entrees).pages[1].refusal_code == valeur


@pytest.mark.parametrize("valeur", [42, [], {}, 3.5, True, ""])
def test_la_phrase_de_refus_garde_sa_garde_entiere(valeur) -> None:
    """La frontiere de la tolerance, mesuree sur le champ voisin.

    `refusal_code` ne peut pas rendre un document illisible; `refusal_reason`,
    si -- et c'est voulu. C'est la phrase que l'operateur lit a l'ecran: une
    valeur non textuelle ou vide y est un document casse, pas un champ
    informatif manquant. Sans ce test, l'inversion de `BH-8` pourrait deriver
    en « le lecteur ne refuse plus rien » sans que rien ne le signale.

    `"   "` n'y figure pas, et c'est mesure: `require_text` ne fait aucun
    `strip`, si bien qu'une phrase uniquement blanche traverse **aussi** sur ce
    champ-la. C'est le meme trou qu'`EC-9`, sur l'autre champ; le refermer
    changerait la garde commune de tous les documents de previz, ce qui excede
    le perimetre de cette story. Verse au triage plutot qu'elargi ici.
    """
    document = json.loads(rendered(build(**make_deux_pages_refusees())))
    _page_par_rang(document, 1)["refusal_reason"] = valeur
    with pytest.raises(SPE, match="refusal_reason"):
        scan_previz.scan_previz_from_json_dict(document)

    entrees = make_deux_pages_refusees()
    list(entrees["detection"].pages)[1].refusal_reason = valeur
    with pytest.raises(SPE, match="refusal_reason"):
        build(**entrees)
