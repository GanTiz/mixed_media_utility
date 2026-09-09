"""Tests de la commande `encode` et de sa decision (story 6.1).

Trois exigences structurent ce fichier, reprises des suites de l'Epic 5.

**Contre les vrais producteurs** (action item 3 de la retro Epic 4): le projet
d'entree vient de `io.extraction_manifest.build_extraction_manifest` reel, puis
de la chaine de scan reelle -- payloads de `io.payload`, plans de decoupe de
`scan_crop`, vrais TIFF ecrits par `scan_output_frames.write_lot_output_frames`,
manifest fusionne par `io.scan_manifest.persist_scan`. Aucun `SimpleNamespace`,
aucun dict de manifest ecrit a la main **la ou un producteur existe**.

**Exception unique, assumee et motivee: l'AC 4.** Aucune chaine reelle du depot
ne sait aujourd'hui produire deux lots scannes derivant du meme lot
d'extraction -- la story 5.12 n'est pas livree, et le champ de derivation
qu'elle cree (son AC 5) n'existe donc nulle part. Son test **exige** un manifest
fabrique a la main. La regle est levee pour ces tests-la, le motif est ecrit
dans chacun, et ils sont a reprendre contre le vrai producteur des que 5.12 est
livree. Sans cette levee explicite, l'AC 4 serait **non falsifiable**, ce qui
est precisement le defaut qu'elle existe pour empecher.

**Regle des fabriques du `CLAUDE.md`**: toute fabrique de lot produit au moins
deux frames distinguables (valeurs de pixels differentes par emplacement, jamais
un remplissage uniforme), et au moins un test place la cible ailleurs qu'en
premiere position. Seule exception, et c'est l'objet meme du test: le lot d'une
seule frame (borne basse reelle du depot).

**Au moins un test regarde le produit fini.** La lecon de la story 6.0 est que
tous ses tests regardaient la commande et aucun le fichier: ici, plusieurs
tests relisent le master par `ffprobe` -- cardinal, geometrie, cadence,
timecode, tags de conteneur -- et non le seul code de retour.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import copy
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import (  # noqa: E402
    cli,
    codec_profiles,
    color_pipeline,
    encode as encode_module,
    scan_crop,
    scan_detection,
    scan_output_frames as sof,
    video_metadata,
)
from mixed_media_utility.frame_selection import select_source_frames  # noqa: E402
from mixed_media_utility.io import (  # noqa: E402
    metadata_matrix,
    naming,
    payload as payload_io,
    project_layout,
    scan_manifest as sm,
)
from mixed_media_utility.io.extraction_manifest import (  # noqa: E402
    MANIFEST_FILENAME,
    ExtractionRecord,
    build_extraction_manifest,
)
from mixed_media_utility.io.project_layout import FRAMES_DIRNAME, rush_dir_slug  # noqa: E402

ENCODE_MODULE_PATH = REPO_ROOT / "src" / "mixed_media_utility" / "encode.py"
CLI_MODULE_PATH = REPO_ROOT / "src" / "mixed_media_utility" / "cli.py"

#: DPI volontairement bas, meme motif que la suite 5.7: les vraies frames sont
#: ecrites **et encodees** a chaque test, et un A4 a 600 ppp couterait trente
#: fois plus cher sans rien prouver de plus. La geometrie reste celle du plan
#: reel: 551x310 a 100 ppp sur le gabarit deux frames.
DPI = 100
PROJECT = "proj-encode"
RUSH = "rush-encode"
FPS = 5.0
TPL = "tpl-a4-portrait-2f-v1"
PATCH_PRESET = "patch-values-2"
COLORSPACE = "bt709"
LOT = naming.build_lot_id(RUSH, FPS)

#: Motif de mire, pris au vocabulaire ferme du producteur (story 5.6).
SYNTHETIC_REASON = sof.SYNTHETIC_FRAME_REASONS[0]

#: Cadence employee par les tests de **timecode**, et son lot.
#:
#: Elle valait 15 im/s parce que c'etait la seule fenetre (`11 <= ceil(cadence)
#: <= 100`) ou la confrontation de chaines de la fabrique pouvait reussir. Cette
#: raison est morte le 2026-08-10 avec la correction de la story 6.0 (commit
#: `8713094`) et la levee de l'abstention: la reinjection est desormais exercee
#: **a toutes** les cadences, celles du dessous comprises (voir les tests
#: `..._below_the_old_window_...`). 15 im/s reste la cadence de reference de ces
#: tests-la pour une autre raison, celle-la intacte: c'est la seule des cadences
#: du depot ou la frontiere de representabilite (`ff` jusqu'a 14) laisse de la
#: place des deux cotes -- `00:00:00:12` representable, `00:00:00:16` non.
FPS_TC = 15.0
LOT_TC = naming.build_lot_id(RUSH, FPS_TC)
SOURCE_FRAME_COUNT_TC = 8
#: `ff = 12` est strictement superieur a `ceil(5)`, la cadence des autres lots de
#: cette suite: c'est le piege de l'AC 10, un timecode parfaitement legal en base
#: source 30 que toute validation faite contre la cadence cible rejetterait. Il
#: est **representable** a 15 im/s (ou `ff` va jusqu'a 14), donc il ressort
#: verbatim -- c'est la frontiere basse de la decision de sens.
START_TC = "00:00:00:12"
#: L'autre cote de la meme frontiere: `ff = 16` n'existe pas a 15 im/s. Aucune
#: etiquette n'est alors emise, et surtout aucune autre n'est inventee.
OUT_OF_BASE_TC = "00:00:00:16"

#: Cadence source et cardinal choisis pour que le lot porte le **piege de
#: l'AC 10**: a 30 im/s source pour 5 im/s cible, les timecodes portent des
#: champs `ff` jusqu'a 24, tous strictement superieurs a `ceil(5) = 5`. Un
#: timecode parfaitement legal en base source est donc rejete par toute
#: validation faite contre la cadence cible.
FPS_SOURCE = 30
#: **Le lot de base franchit la seconde**, et c'est une exigence de fabrique, pas
#: un detail de fixture. Avec 24 frames source (0,8 s), tous les timecodes du lot
#: valaient `00:00:00:xx`: `hh`, `mm` et `ss` etaient nuls partout, donc **toute
#: permutation de la cle de tri rendait le meme ordre**. La campagne de mutation
#: l'a mesure -- le mutant qui trie sur `(ff, ss, mm, hh)` survivait aux 53 tests.
#: C'est la regle des fabriques du `CLAUDE.md` transposee a la dimension
#: temporelle: deux elements ne sont distinguables que si les champs qui les
#: distinguent varient. 48 frames source a 30 im/s font 1,6 s, soit huit frames a
#: 5 im/s de `00:00:00:00` a `00:00:01:12`.
SOURCE_FRAME_COUNT = 48


# --------------------------------------------------------------------------
# Fabriques: tout derive des vrais producteurs
# --------------------------------------------------------------------------


def real_selection(
    *,
    fps_target: float = FPS,
    source_start_timecode: str | None = None,
    source_frame_count: int = SOURCE_FRAME_COUNT,
):
    """Selection produite par le **vrai** noyau deterministe (story 3.2)."""
    return select_source_frames(
        fps_source=FPS_SOURCE,
        fps_target=fps_target,
        source_frame_count=source_frame_count,
        source_start_timecode=source_start_timecode,
    )


def rich_extraction_manifest(
    *,
    fps_target: float = FPS,
    rush_id: str = RUSH,
    project_id: str = PROJECT,
    source_start_timecode: str | None = None,
    source_frame_count: int = SOURCE_FRAME_COUNT,
) -> dict:
    """Manifest riche du **vrai** producteur d'extraction (story 3.4).

    C'est lui, et lui seul, qui pose `timecode_base_fps`, `first_frame_timecode`
    et `fps_target_exact`: un lot ne des planches seules ne les porte pas, et
    c'est exactement la distinction que l'AC 10 exige de traiter.
    """
    selection = real_selection(
        fps_target=fps_target,
        source_start_timecode=source_start_timecode,
        source_frame_count=source_frame_count,
    )
    record = ExtractionRecord(
        project_id=project_id,
        rush_id=rush_id,
        rush_source_name=f"{rush_id}.mov",
        lot_id=naming.build_lot_id(rush_id, fps_target),
        frames_dir_relative=f"{FRAMES_DIRNAME}/{rush_dir_slug(rush_id, fps_target)}",
        selection=selection,
        fps_source=float(FPS_SOURCE),
        fps_target=fps_target,
        source_width=1920,
        source_height=1080,
        source_fields={
            "source_codec": "prores",
            "source_pix_fmt": "yuv422p10le",
            "source_bit_depth": 10,
            "source_sample_aspect_ratio": "1:1",
            "source_color_primaries": "bt709",
            "source_color_trc": "bt709",
            "source_colorspace": "bt709",
            "source_color_range": "tv",
        },
        confirmation_mode="non_interactif",
        unknown_color_accepted=False,
        confirmed_at="2026-08-10T09:30:00Z",
    )
    return build_extraction_manifest(None, record)


def make_payload(
    *,
    page_index: int,
    timecodes: list[str],
    page_count: int,
    first_slot: int,
    project_id: str = PROJECT,
    rush_id: str = RUSH,
    fps_target: float = FPS,
) -> dict:
    """Payload QR **reel**, valide par `io.payload`, jamais bricole a la main."""
    slots = [
        {"slot_index": first_slot + offset, "frame_timecode": timecode}
        for offset, timecode in enumerate(timecodes)
    ]
    return payload_io.build_page_payload(
        project_id=project_id,
        rush_id=rush_id,
        lot_id=naming.build_lot_id(rush_id, fps_target),
        page_index=page_index,
        page_count=page_count,
        fps_target=fps_target,
        # Story 2.7 (payload 2.1): meme regime que `rich_extraction_manifest`
        # (`FPS_SOURCE = 30`) -- un manifest riche existant et des payloads
        # scannes qui divergeraient sur ce champ seraient un vrai conflit
        # (`_check_manifest_conflicts`), pas un artefact de fabrique.
        timecode_base_fps=f"{FPS_SOURCE}/1",
        template_id=TPL,
        patch_preset_id=PATCH_PRESET,
        target_colorspace=COLORSPACE,
        gamut_map_id=payload_io.GAMUT_MAP_IDENTITY,
        slots=slots,
    )


def payloads_for(
    selection, *, rush_id: str = RUSH, fps_target: float = FPS, slots_per_page: int = 2
) -> list[dict]:
    """Decouper une selection reelle en pages de `slots_per_page` emplacements."""
    timecodes = [frame.frame_timecode for frame in selection.frames]
    pages = [
        timecodes[start : start + slots_per_page]
        for start in range(0, len(timecodes), slots_per_page)
    ]
    return [
        make_payload(
            page_index=index,
            timecodes=page,
            page_count=len(pages),
            first_slot=index * slots_per_page,
            rush_id=rush_id,
            fps_target=fps_target,
        )
        for index, page in enumerate(pages)
    ]


def scanned_page(payload: dict, *, failure: str | None = None) -> sof.ScannedPage:
    """Page telle que la chaine scan la remet a l'ecriture de 5.6.

    Les frames d'une meme page portent des valeurs **differentes** (une par
    `slot_index`): un remplissage uniforme rendrait invisible toute erreur
    d'appariement, defaut trouve trois fois de suite par mutation dans l'Epic 5.
    """
    plan = scan_crop.build_page_crop_plan(
        template_id=payload["template_id"], slots=payload["slots"], dpi=DPI
    )
    if failure is not None:
        return sof.ScannedPage(payload=payload, crop_plan=plan, failure=failure)
    frames = tuple(
        np.full(
            (frame.height_px, frame.width_px, 3),
            4096 + 137 * frame.slot_index,
            np.uint16,
        )
        for frame in plan.frames
    )
    return sof.ScannedPage(payload=payload, crop_plan=plan, frames=frames)


def scan_once(
    project_dir: Path,
    payloads: list[dict],
    *,
    failures: dict[int, str] | None = None,
    absent_pages: tuple[int, ...] = (),
    existing_manifest: dict | None = None,
) -> sm.PersistedScan:
    """Une passe complete, **dans l'ordre reel de la chaine** (EPIC5-ARB-34).

    `absent_pages` retire les pages du bac de scan: rien n'est ecrit pour leurs
    emplacements, et **aucun slot ne les represente** dans `reconstruction`.
    C'est le trou reel, celui que le bloquant B2 de la revue a mesure.
    """
    failures = failures or {}
    project_dir.mkdir(parents=True, exist_ok=True)
    if existing_manifest is not None:
        (project_dir / MANIFEST_FILENAME).write_text(
            json.dumps(existing_manifest, indent=2, sort_keys=True), encoding="utf-8"
        )
    retained = [p for p in payloads if p["page_index"] not in absent_pages]
    sm.check_scan_conflicts(
        project_dir,
        retained,
        failed_page_indexes=tuple(sorted(failures)),
        overwrite=False,
    )
    pages = [
        scanned_page(payload, failure=failures.get(payload["page_index"]))
        for payload in retained
    ]
    report = sof.write_lot_output_frames(
        project_dir, pages, color_calibration_status=color_pipeline.NOT_APPLIED_STATUS
    )
    record = sm.ScanRecord(
        page_payloads=tuple(retained),
        output_report=report,
        scan_dpi=600,
        ingest_slug="lot-encode",
        pages=tuple(
            sm.ScanPageProvenance(
                read_rank=rank,
                status=scan_detection.PAGE_OK,
                qr_status=scan_detection.qr_codes.DECODE_OK,
                page_index=payload["page_index"],
                homography_status=sm.HOMOGRAPHY_RESOLVED,
            )
            for rank, payload in enumerate(retained)
        ),
    )
    return sm.persist_scan(project_dir, record)


def scanned_project(
    tmp_path: Path,
    *,
    fps_target: float = FPS,
    source_start_timecode: str | None = None,
    source_frame_count: int = SOURCE_FRAME_COUNT,
    with_extraction: bool = True,
    failures: dict[int, str] | None = None,
    absent_pages: tuple[int, ...] = (),
    slots_per_page: int = 2,
    name: str = "proj",
) -> tuple[Path, dict]:
    """Projet complet produit par la chaine reelle, rendu avec son manifest."""
    project_dir = tmp_path / name
    selection = real_selection(
        fps_target=fps_target,
        source_start_timecode=source_start_timecode,
        source_frame_count=source_frame_count,
    )
    existing = (
        rich_extraction_manifest(
            fps_target=fps_target,
            source_start_timecode=source_start_timecode,
            source_frame_count=source_frame_count,
        )
        if with_extraction
        else None
    )
    persisted = scan_once(
        project_dir,
        payloads_for(selection, fps_target=fps_target, slots_per_page=slots_per_page),
        failures=failures,
        absent_pages=absent_pages,
        existing_manifest=existing,
    )
    return project_dir, persisted.manifest


def load_manifest_dict(project_dir: Path) -> dict:
    return json.loads((project_dir / MANIFEST_FILENAME).read_text(encoding="utf-8"))


def timecode_project(tmp_path: Path, **kwargs) -> tuple[Path, dict]:
    """Projet a 15 im/s, cadence de reference des tests de **representabilite**.

    Voir `FPS_TC`: ce n'est plus "la seule fenetre reinjectable" -- il n'y a plus
    de fenetre -- mais la cadence ou `ff` plafonne a 14, donc la seule du depot
    ou la frontiere de l'AC 10 a de la place des deux cotes.
    """
    kwargs.setdefault("source_start_timecode", START_TC)
    return scanned_project(
        tmp_path,
        fps_target=FPS_TC,
        source_frame_count=SOURCE_FRAME_COUNT_TC,
        **kwargs,
    )


def lot_of(manifest: dict, lot_id: str = LOT) -> dict:
    return next(lot for lot in manifest["lots"] if lot["lot_id"] == lot_id)


def strip_timecode_base_fps(project_dir: Path, manifest: dict, *, lot_id: str = LOT) -> dict:
    """Simuler un lot ne d'un scan de planches **2.0** (story 2.7, avant l'AC 1).

    Depuis la story 2.7, `io.payload.build_page_payload` exige `timecode_base_fps`
    sur toute planche d'images: aucune fabrique de ce fichier ne peut plus produire
    un payload 2.1 qui en soit prive, donc plus aucun lot ne d'un scan **reel** via
    ce fichier n'en manque. Le seul geste fidele au regime fixture-pre-2.1 exige par
    l'AC 5 est de le retirer **apres** reconstruction -- exactement l'etat qu'un
    manifest issu d'un scan de planches imprimees avant la story aurait laisse.
    Le retrait porte sur le manifest en memoire **et** sur le fichier project.json,
    pour que les tests passant par la vraie CLI (qui relit le disque) et ceux
    passant par `plan_encode` directement voient tous deux le meme etat.
    """
    lot_of(manifest, lot_id).pop("timecode_base_fps", None)
    (project_dir / MANIFEST_FILENAME).write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    return manifest


def run_cli(project_dir: Path, *extra: str) -> int:
    return cli.main(
        ["encode", "--project", str(project_dir), "--lot", LOT, "--yes", *extra]
    )


def probe_stream(path: Path) -> dict:
    probe = video_metadata.probe_media(str(path))
    return next(s for s in probe["streams"] if s.get("codec_type") == "video")


# --------------------------------------------------------------------------
# AC 1 / AC 2 -- surface de la commande et vocabulaire de profils
# --------------------------------------------------------------------------


def encode_help_text() -> str:
    """Aide de la sous-commande, telle que `main()` la construit reellement.

    Passe par `main` plutot que par une copie du parseur: une copie divergerait
    au premier ajustement de la surface, et c'est precisement la surface qui est
    testee ici.
    """
    import contextlib
    import io as _io

    buffer = _io.StringIO()
    with contextlib.redirect_stdout(buffer), pytest.raises(SystemExit):
        cli.main(["encode", "--help"])
    return buffer.getvalue()


def test_surface_is_project_and_lot_never_a_bare_frames_directory(capsys):
    """AC 1: `--project` requis, `--lot` en option, aucun positionnel.

    Le stub POC prenait un dossier d'images nu. Il n'est **pas** compatible
    ascendant, et c'est assume (EPIC6-ARB-2): le disque ne sait pas distinguer
    une mire de synthese d'une vraie frame -- meme nom par construction, aucun
    tag -- si bien qu'un dossier nu produirait un master faux sans le dire.
    """
    aide = encode_help_text()
    assert "--project PROJECT" in aide and "--lot LOT" in aide
    # Aucun positionnel: la ligne d'usage n'en porte aucun, et la surface POC
    # `encode <frames-dir> -c prores -o out.mov` est refusee.
    usage = aide.split("options:")[0]
    assert "frames" not in usage and "--codec" not in aide and "--output" not in aide
    capsys.readouterr()
    for argv in (
        ["encode"],
        ["encode", "--project", "p"],
        ["encode", "frames/", "-c", "prores", "-o", "out.mov"],
    ):
        with pytest.raises(SystemExit):
            cli.main(argv)
        capsys.readouterr()


def test_profile_vocabulary_is_derived_from_the_catalogue(tmp_path, capsys, monkeypatch):
    """AC 2: les valeurs admises viennent de `PROFILES`, jamais recopiees.

    Les `choices=['prores','h264','hevc']` du stub n'etaient **aucun** un
    identifiant valide, et les deux profils DNxHR etaient de ce fait
    inaccessibles. Le test est falsifiable dans les deux sens: chaque profil du
    catalogue est expose, aucune valeur du stub ne l'est, puis un profil ajoute
    au catalogue apparait **sans qu'aucune ligne de `cli.py` ne bouge**.
    """
    aide = encode_help_text()
    for profile_id in codec_profiles.PROFILES:
        assert profile_id in aide
    assert codec_profiles.DEFAULT_PROFILE_ID == "prores_hq"
    assert "defaut prores_hq" in aide
    for legacy in ("prores", "h264", "hevc"):
        assert legacy not in codec_profiles.PROFILES

    project_dir, _ = scanned_project(tmp_path)
    capsys.readouterr()
    with pytest.raises(SystemExit):
        cli.main(["encode", "--project", str(project_dir), "--lot", LOT, "--profile", "prores"])
    capsys.readouterr()

    monkeypatch.setitem(
        codec_profiles.PROFILES,
        "prores_proxy",
        codec_profiles.EncodeProfile(
            profile_id="prores_proxy",
            category="secondary",
            container="mov",
            vcodec="prores_ks",
            probe_codec_name="prores",
            pix_fmt="yuv422p10le",
            colorspace="bt709",
            extra_args=("-profile:v", "0", "-vendor", "apl0"),
        ),
    )
    assert "prores_proxy" in encode_help_text()
    assert run_cli(project_dir, "--profile", "prores_proxy") == 0
    assert (
        project_layout.outputs_dir(project_dir) / f"{LOT}_mmu_prores_proxy.mov"
    ).is_file()


# --------------------------------------------------------------------------
# AC 3 -- garde d'admission sur la matiere, quatre causes, quatre codes
# --------------------------------------------------------------------------


def test_absent_lot_is_refused_and_names_the_declared_lots(tmp_path):
    """AC 3: un lot inconnu est nomme, et les lots reels sont listes."""
    project_dir, manifest = scanned_project(tmp_path)
    with pytest.raises(encode_module.EncodeDecisionError) as excinfo:
        encode_module.plan_encode(project_dir, manifest, lot_id="lot-fantome")
    assert excinfo.value.code == encode_module.ENCODE_LOT_ABSENT
    assert LOT in str(excinfo.value)


def test_state_below_scan_and_missing_output_dir_carry_distinct_codes(tmp_path):
    """AC 3: deux causes, deux messages -- et la garde d'etat seule ne suffit pas.

    Mesure a l'execution: `io.reconstruction.DEFAULT_LOT_STATE` vaut
    `reconstruction`, qui est a l'index 3 de `LOT_STATES`, donc **superieur** a
    `scan`. Un lot recree depuis des payloads passe donc une garde "au moins
    scan" sans porter la moindre frame. Manifest modifie a la main ici, parce
    que le producteur reel ne sait pas fabriquer cette combinaison: il ecrit
    toujours `output_frames_dir` en meme temps que l'etat.
    """
    from mixed_media_utility.io.manifest import LOT_STATES

    assert LOT_STATES.index("reconstruction") > LOT_STATES.index("scan")

    project_dir, manifest = scanned_project(tmp_path)

    trop_tot = copy.deepcopy(manifest)
    lot_of(trop_tot)["state"] = "extraction"
    with pytest.raises(encode_module.EncodeDecisionError) as etat:
        encode_module.plan_encode(project_dir, trop_tot, lot_id=LOT)
    assert etat.value.code == encode_module.ENCODE_LOT_STATE_TOO_EARLY

    sans_dossier = copy.deepcopy(manifest)
    lot_of(sans_dossier)["state"] = "reconstruction"
    lot_of(sans_dossier).pop("output_frames_dir")
    with pytest.raises(encode_module.EncodeDecisionError) as dossier:
        encode_module.plan_encode(project_dir, sans_dossier, lot_id=LOT)
    assert dossier.value.code == encode_module.ENCODE_OUTPUT_DIR_NOT_DECLARED
    assert dossier.value.code != etat.value.code


def test_declared_directory_absent_and_empty_carry_distinct_codes(tmp_path):
    """AC 3: dossier declare mais absent, puis present et sans frame conforme."""
    project_dir, manifest = scanned_project(tmp_path)
    lot_dir = project_dir / lot_of(manifest)["output_frames_dir"]

    frames = sorted(lot_dir.iterdir())
    for frame in frames:
        frame.unlink()
    with pytest.raises(encode_module.EncodeDecisionError) as vide:
        encode_module.plan_encode(project_dir, manifest, lot_id=LOT)
    assert vide.value.code == encode_module.ENCODE_OUTPUT_DIR_EMPTY

    lot_dir.rmdir()
    with pytest.raises(encode_module.EncodeDecisionError) as absent:
        encode_module.plan_encode(project_dir, manifest, lot_id=LOT)
    assert absent.value.code == encode_module.ENCODE_OUTPUT_DIR_ABSENT


# --------------------------------------------------------------------------
# AC 4 -- tirages multiples
# --------------------------------------------------------------------------


def _manifest_with_two_prints(manifest: dict) -> dict:
    """Manifest a deux tirages, **fabrique a la main**: levee motivee de l'AC 19.

    Aucune chaine reelle du depot ne sait produire deux lots scannes derivant du
    meme lot d'extraction: la story 5.12 n'est pas livree et le champ de
    derivation qu'elle cree (son AC 5) n'existe nulle part. A reprendre contre
    le vrai producteur des que 5.12 est livree.

    Le lot **vise** est place en **seconde** position, conformement a la regle
    des fabriques: le mutant `M25` de 5.7 -- un `find` qui rend toujours le
    premier element -- a survecu a 257 tests parce que toutes les fixtures
    placaient la cible en premier.

    **Pourquoi ces tests appellent `select_lot` au lieu de passer par la CLI**,
    et il faut le dire noir sur blanc (releve par la couche 3 de la revue):
    `lots[]` porte `additionalProperties: false` au schema et `source_lot_id`
    n'y figure pas. Mesure par la vraie CLI sur un manifest a deux tirages:

        Erreur: Invalid manifest at 'lots.10': Additional properties are not
                allowed ('source_lot_id' was unexpected)          EXIT=1

    `TIRAGES_MULTIPLES` est donc **injoignable de bout en bout aujourd'hui**: la
    commande refuse en amont, pour une autre raison et avec un autre message.
    L'AC 18 interdit a cette story de toucher `project.schema.json`, et c'est
    bien a la story 5.12 d'ajouter le champ **au schema en meme temps qu'au
    producteur**: c'est un **prerequis de 5.12**, consigne au Dev Agent Record.
    D'ici la, la logique est vraie en unite et inatteignable en integration.
    """
    document = copy.deepcopy(manifest)
    source = document["lots"][0]
    autre = copy.deepcopy(source)
    autre["lot_id"] = f"{LOT}-11111111"
    autre[encode_module.DERIVED_FROM_LOT_FIELD] = LOT
    autre["expected_frame_count"] = 2
    vise = copy.deepcopy(source)
    vise["lot_id"] = f"{LOT}-22222222"
    vise[encode_module.DERIVED_FROM_LOT_FIELD] = LOT
    document["lots"] = [autre, vise]
    return document


def test_two_prints_of_the_same_lot_are_refused_with_named_candidates(tmp_path):
    """AC 4: refus, candidats nommes, et ce qui les distingue est dit.

    Choisir automatiquement est exclu: "le plus complet" n'est pas "celui qu'on
    veut" -- un tirage volontairement partiel est legitime -- et "le plus
    recent" ferait dependre l'oeuvre d'un horodatage que le depot s'interdit de
    persister.
    """
    _, manifest = scanned_project(tmp_path)
    document = _manifest_with_two_prints(manifest)
    with pytest.raises(encode_module.EncodeDecisionError) as excinfo:
        encode_module.select_lot(document, LOT)
    assert excinfo.value.code == encode_module.ENCODE_MULTIPLE_PRINTS
    message = str(excinfo.value)
    assert f"{LOT}-11111111" in message and f"{LOT}-22222222" in message
    # Ce qui les distingue, pas seulement leur nom.
    assert "cardinal attendu 2" in message


def test_the_targeted_print_is_resolved_even_in_second_position(tmp_path):
    """AC 4 / regle des fabriques: la cible n'est pas la premiere du tableau."""
    _, manifest = scanned_project(tmp_path)
    document = _manifest_with_two_prints(manifest)
    choisi = encode_module.select_lot(document, f"{LOT}-22222222")
    assert choisi["lot_id"] == f"{LOT}-22222222"
    assert document["lots"].index(choisi) == 1


def test_lot_attachment_never_reads_the_condensate_suffix(tmp_path):
    """AC 4: deux natures de condensat partagent le meme espace de noms.

    Le suffixe `-<condensat8>` est **deja** occupe par le condensat de bornes de
    la story 3.7 (`io.naming.bounds_suffix`), et le manifest reel du depot porte
    trois lots de cette forme. Un lot borne n'est donc **pas** un tirage: le
    rattachement passe exclusivement par le champ de derivation.
    """
    _, manifest = scanned_project(tmp_path)
    document = copy.deepcopy(manifest)
    borne = copy.deepcopy(document["lots"][0])
    borne["lot_id"] = f"{LOT}-{naming.bounds_suffix('00:00:02:00', None)}"
    borne.pop(encode_module.DERIVED_FROM_LOT_FIELD, None)
    document["lots"].append(borne)
    # Aucun refus: le lot borne ne derive de rien, il n'est candidat a rien.
    assert encode_module.select_lot(document, LOT)["lot_id"] == LOT


# --------------------------------------------------------------------------
# AC 5 -- la sequence vient du dossier du lot
# --------------------------------------------------------------------------


def test_sequence_is_sorted_by_decoded_timecode_not_by_input_order(tmp_path):
    """AC 5: l'ordre de lecture d'un dossier est celui du systeme de fichiers.

    Mesure de la story 6.0 sur six frames: `glob` rend `05,03,04,06,01,02`. La
    fonction de plan est **pure** precisement pour qu'un test puisse lui passer
    une suite deliberement melangee, ce qu'aucun `iterdir` ne garantit.
    """
    project_dir, manifest = scanned_project(tmp_path)
    lot_dir = project_dir / lot_of(manifest)["output_frames_dir"]
    noms = sorted(p.name for p in lot_dir.iterdir())
    assert len(noms) >= 2
    melange = [noms[-1], noms[1], noms[0]] + noms[2:-1]
    plan = encode_module.plan_sequence(melange, rush_id=RUSH, fps_target=FPS)
    assert list(plan.names) == noms
    assert list(plan.timecodes) == sorted(plan.timecodes)


def test_lexicographic_and_chronological_order_coincide_on_conforming_names(tmp_path):
    """Ecart mesure avec ce que l'AC 19 demandait de couvrir.

    L'AC 19 exige un test sur "une sequence dont les frames ne sont pas dans
    l'ordre lexicographique de leur nom". Mesure: **cette sequence n'est pas
    constructible** avec la recette de nom du depot. Les quatre champs du
    timecode assaini sont zero-remplis a largeur fixe
    (`_SANITIZED_TIMECODE_PATTERN`), et le prefixe est commun a tout le lot: le
    tri lexicographique des noms conformes coincide donc **toujours** avec
    l'ordre chronologique. Le seul contre-exemple serait le franchissement de
    24 h, que la commande refuse explicitement.

    Le risque reel n'est donc pas le tri lexicographique mais son **absence**:
    l'ordre du systeme de fichiers, mesure par la story 6.0 comme
    `05,03,04,06,01,02`. C'est lui que le test voisin exerce.
    """
    project_dir, manifest = scanned_project(tmp_path)
    lot_dir = project_dir / lot_of(manifest)["output_frames_dir"]
    noms = [p.name for p in lot_dir.iterdir()]
    plan = encode_module.plan_sequence(noms, rush_id=RUSH, fps_target=FPS)
    assert list(plan.names) == sorted(noms)
    assert list(plan.timecodes) == sorted(plan.timecodes)
    assert len({len(nom) for nom in noms}) == 1


def test_nonconforming_files_are_reported_and_never_enter_the_sequence(tmp_path):
    """AC 5: un fichier etranger est signale, jamais encode."""
    project_dir, manifest = scanned_project(tmp_path)
    lot_dir = project_dir / lot_of(manifest)["output_frames_dir"]
    (lot_dir / "notes.txt").write_text("hors convention", encoding="utf-8")
    (lot_dir / "scan_autre-rush_5_00-00-00-00.tiff").write_bytes(b"")

    plan = encode_module.plan_encode(project_dir, manifest, lot_id=LOT)
    assert set(plan.nonconforming) == {"notes.txt", "scan_autre-rush_5_00-00-00-00.tiff"}
    assert encode_module.ENCODE_NONCONFORMING_FILES in plan.findings
    assert all(path.name.startswith("scan_" + RUSH) for path in plan.frame_paths)


def test_a_second_scanned_lot_does_not_make_the_target_lot_look_holed(tmp_path):
    """AC 5, bloquant B1: `reconstruction` est **unique par document**.

    Le schema l'ecrit lui-meme: "le scan d'un second lot ecrase le detail par
    frame du premier. Tout cardinal durable vit donc sur `lots[]` et jamais
    ici." Le manifest reel du depot est deja dans ce cas: deux lots a l'etat
    `scan`, une seule section, qui decrit l'autre. C'est le seul test qui
    attrape ce bloquant.
    """
    project_dir = tmp_path / "proj"
    premier = real_selection()
    scan_once(
        project_dir,
        payloads_for(premier),
        existing_manifest=rich_extraction_manifest(),
    )
    # Second lot du **meme** rush a une autre cadence: cas nominal v2.1. Il est
    # scanne en dernier, donc c'est **lui** que `reconstruction` decrit.
    second_fps = 10.0
    second_lot = naming.build_lot_id(RUSH, second_fps)
    existing = load_manifest_dict(project_dir)
    riche = rich_extraction_manifest(fps_target=second_fps)
    existing["lots"].extend(
        lot for lot in riche["lots"] if lot["lot_id"] == second_lot
    )
    (project_dir / MANIFEST_FILENAME).write_text(
        json.dumps(existing, indent=2, sort_keys=True), encoding="utf-8"
    )
    scan_once(project_dir, payloads_for(real_selection(fps_target=second_fps), fps_target=second_fps))

    manifest = load_manifest_dict(project_dir)
    assert manifest["reconstruction"]["lot_id"] == second_lot

    plan = encode_module.plan_encode(project_dir, manifest, lot_id=LOT)
    assert plan.verdict.complete
    assert plan.verdict.found == plan.verdict.expected
    assert encode_module.ENCODE_RECONSTRUCTION_OTHER_LOT in plan.findings
    assert encode_module.reconstruction_for_lot(manifest, LOT) is None


def test_a_lot_crossing_twenty_four_hours_is_refused_not_mis_ordered(tmp_path):
    """AC 5: `_format_timecode` reboucle modulo 86400 * fps.

    Le nom des frames ne porte rien qui permette de rattraper le rebouclage: a
    largeur fixe, le tri lexicographique et le tri chronologique coincident
    toujours. Les deux seules suites dont l'ordre chronologique est connu par
    ailleurs sont les bornes du lot et les emplacements de `reconstruction`.
    """
    with pytest.raises(encode_module.EncodeDecisionError) as bornes:
        encode_module.check_chronology(["23:59:59:20", "00:00:01:00"], origin="les bornes")
    assert bornes.value.code == encode_module.ENCODE_TIMECODE_DECREASING

    project_dir, manifest = scanned_project(tmp_path)
    document = copy.deepcopy(manifest)
    lot_of(document)["first_frame_timecode"] = "23:59:59:20"
    lot_of(document)["last_frame_timecode"] = "00:00:01:00"
    with pytest.raises(encode_module.EncodeDecisionError) as lot:
        encode_module.plan_encode(project_dir, document, lot_id=LOT)
    assert lot.value.code == encode_module.ENCODE_TIMECODE_DECREASING


def test_conformity_uses_the_repository_recipe_and_accepts_a_bounded_lot(tmp_path):
    """AC 5: la conformite n'est jamais reecrite ici.

    Mesure du 2026-08-10, et c'est un **ecart** avec ce que la story annoncait:
    pour un lot **borne** (story 3.7), le producteur ecrit
    `scan_<rush>_<fps>_<tc>.tiff` -- sans le condensat -- alors que le dossier,
    lui, porte le `lot_id` avec condensat. Reconstruire le nom attendu depuis le
    `lot_id`, comme l'AC 5 le prescrit en prevision de 5.12, rendrait donc
    **aucune** frame conforme sur un lot borne d'aujourd'hui. La recette du
    depot (`scan_output_frames.is_conforming_scan_frame_name`) est donc la seule
    employee, et c'est le point exact a reprendre quand 5.12 arrivera.
    """
    lot_borne = f"{LOT}-{naming.bounds_suffix('00:00:02:00', None)}"
    nom_reel = naming.build_scan_frame_filename(RUSH, FPS, "00:00:00:06")
    assert nom_reel == f"scan_{LOT}_00-00-00-06.tiff"
    assert nom_reel != f"scan_{lot_borne}_00-00-00-06.tiff"
    assert sof.is_conforming_scan_frame_name(nom_reel, RUSH, FPS)


# --------------------------------------------------------------------------
# AC 6 -- verdict de completude, trois issues (et une quatrieme mesuree)
# --------------------------------------------------------------------------


def test_a_missing_page_is_refused_with_the_gap_and_never_with_timecodes(tmp_path):
    """AC 6, bloquant B2: les slots d'une page absente n'entrent jamais dans `slots[]`.

    Mesure a l'execution contre le vrai producteur: un parcours de `slots[]`
    verrait autant de slots que de fichiers et conclurait "complet". Le verdict
    se lit donc sur les cardinaux de `lots[]`, que le schema designe comme
    faisant foi.

    Et les timecodes des frames manquantes **n'existent nulle part**: le depot
    l'ecrit, "aucun timecode n'est donc recalculable pour une page absente". Le
    refus rend des **index de page**, jamais des timecodes.
    """
    project_dir, manifest = scanned_project(tmp_path, absent_pages=(0,))
    lot = lot_of(manifest)
    section = manifest["reconstruction"]
    # Le trou est bien invisible dans `slots[]`: autant de slots que de fichiers.
    lot_dir = project_dir / lot["output_frames_dir"]
    assert len(section["slots"]) == len(list(lot_dir.iterdir()))
    assert section["missing_pages"] == [0]
    assert lot["expected_frame_count"] > len(section["slots"])

    with pytest.raises(encode_module.EncodeDecisionError) as excinfo:
        encode_module.plan_encode(project_dir, manifest, lot_id=LOT)
    assert excinfo.value.code == encode_module.ENCODE_LOT_INCOMPLETE
    message = str(excinfo.value)
    assert "pages manquantes (index): 0" in message
    for timecode in (frame.frame_timecode for frame in real_selection().frames):
        assert timecode not in message


def test_an_absent_expected_frame_count_is_a_distinct_refusal(tmp_path):
    """AC 6, troisieme issue: aucun cardinal de reference n'existe.

    `expected_frame_count` n'est pas ecrit quand la **derniere** page manque
    (`SCAN_EXPECTED_FRAME_COUNT_INDETERMINABLE`), et il est optionnel au schema.
    Encoder reviendrait a declarer complete une sequence dont personne ne
    connait la longueur.
    """
    project_dir, manifest = scanned_project(tmp_path)
    document = copy.deepcopy(manifest)
    lot_of(document).pop("expected_frame_count")
    with pytest.raises(encode_module.EncodeDecisionError) as excinfo:
        encode_module.plan_encode(project_dir, document, lot_id=LOT)
    assert excinfo.value.code == encode_module.ENCODE_EXPECTED_COUNT_INDETERMINABLE


def test_more_conforming_frames_than_expected_is_refused_too(tmp_path):
    """Quatrieme issue, **non prevue par la story** et pourtant atteignable.

    Un fichier de nom conforme mais de timecode etranger a la selection fait
    depasser le cardinal attendu. La table de l'AC 6 n'a que trois lignes; la
    taire reviendrait a encoder une sequence dont personne n'a valide la
    composition.
    """
    project_dir, manifest = scanned_project(tmp_path)
    lot_dir = project_dir / lot_of(manifest)["output_frames_dir"]
    premiere = sorted(lot_dir.iterdir())[0]
    intrus = naming.build_scan_frame_filename(RUSH, FPS, "00:00:10:00")
    (lot_dir / intrus).write_bytes(premiere.read_bytes())
    with pytest.raises(encode_module.EncodeDecisionError) as excinfo:
        encode_module.plan_encode(project_dir, manifest, lot_id=LOT)
    assert excinfo.value.code == encode_module.ENCODE_UNEXPECTED_FRAMES


def test_a_synthetic_name_without_a_file_counts_as_a_hole(tmp_path):
    """AC 6: le **disque** fait foi pour la presence, le manifest pour la nature.

    `synthetic_frames` est un registre durable alors que la confrontation au
    disque n'a lieu qu'a l'ecriture: un nom peut y figurer sans que le fichier
    existe. Un nom au registre sans fichier est un trou, pas une mire.
    """
    project_dir, manifest = scanned_project(
        tmp_path, failures={1: SYNTHETIC_REASON}
    )
    lot = lot_of(manifest)
    assert lot["synthetic_frames"], "le producteur doit avoir pose des mires"
    disparue = lot["synthetic_frames"][0]
    (project_dir / lot["output_frames_dir"] / disparue).unlink()

    with pytest.raises(encode_module.EncodeDecisionError) as excinfo:
        encode_module.plan_encode(project_dir, manifest, lot_id=LOT)
    assert excinfo.value.code == encode_module.ENCODE_LOT_INCOMPLETE
    assert disparue in str(excinfo.value)


def test_encode_passes_with_a_dead_absolute_source_path_on_the_manifest(tmp_path):
    """Story 2.8, AC 3: un `rushes[].source_path` absolu qui ne pointe plus
    vers rien (rush delinke) n'empeche rien -- `encode` n'a jamais lu ce
    champ (story 6.1) et cette story ne l'y fait pas commencer."""
    project_dir, manifest = scanned_project(tmp_path)
    for rush in manifest["rushes"]:
        if rush.get("rush_id") == RUSH:
            rush["source_path"] = "/machine/disparue/rush-encode.mov"
    (project_dir / MANIFEST_FILENAME).write_text(json.dumps(manifest), encoding="utf-8")

    plan = encode_module.plan_encode(project_dir, manifest, lot_id=LOT)

    assert plan.verdict.complete


def test_a_lot_carrying_mires_is_encoded_and_their_number_is_reported(tmp_path):
    """AC 6: les mires sont un contenu **voulu**, encodees telles quelles.

    Le lot reel du depot en porte 2 sur 13, et combler un trou par repetition de
    l'image precedente est interdit depuis l'AC de la story 3.2.
    """
    project_dir, manifest = scanned_project(
        tmp_path, failures={1: SYNTHETIC_REASON}
    )
    lot = lot_of(manifest)
    plan = encode_module.plan_encode(project_dir, manifest, lot_id=LOT)
    assert plan.verdict.complete
    assert len(plan.verdict.synthetic_present) == lot["synthetic_frame_count"] > 0
    assert encode_module.ENCODE_SYNTHETIC_FRAMES_PRESENT in plan.findings
    assert f"Mires               : {lot['synthetic_frame_count']}" in encode_module.render_summary(plan)


def test_a_lot_made_entirely_of_mires_is_encoded_and_the_summary_says_so(tmp_path):
    """AC 19: le lot 100 % mires est un cas reel, et il se dit."""
    # Toutes les pages du lot echouent: le cardinal de pages est **derive** de la
    # selection reelle, jamais recopie -- un lot qui s'allonge ne doit pas rendre
    # ce test faux sans qu'on le voie.
    pages = len(payloads_for(real_selection()))
    project_dir, manifest = scanned_project(
        tmp_path,
        failures={index: SYNTHETIC_REASON for index in range(pages)},
    )
    lot = lot_of(manifest)
    plan = encode_module.plan_encode(project_dir, manifest, lot_id=LOT)
    assert len(plan.verdict.synthetic_present) == plan.frame_count == lot["expected_frame_count"]
    assert "constitue a 100 % de mires" in encode_module.render_summary(plan)


def test_an_incomplete_lot_is_encodable_only_on_explicit_consent(tmp_path):
    """EPIC6-ARB-3: refus par defaut, drapeau explicite pour lever le refus."""
    project_dir, manifest = scanned_project(tmp_path, absent_pages=(0,))
    with pytest.raises(encode_module.EncodeDecisionError):
        encode_module.plan_encode(project_dir, manifest, lot_id=LOT)
    plan = encode_module.plan_encode(
        project_dir, manifest, lot_id=LOT, accept_incomplete=True
    )
    assert encode_module.ENCODE_INCOMPLETE_ACCEPTED in plan.findings
    assert plan.verdict.found < plan.verdict.expected


def test_a_single_frame_lot_is_the_real_lower_bound_and_encodes(tmp_path):
    """AC 19: borne basse reelle du depot (`expected_frame_count: 1`).

    Exception motivee a la regle des fabriques: c'est l'objet meme du test.
    """
    project_dir, manifest = scanned_project(
        tmp_path, source_frame_count=6, slots_per_page=1
    )
    document = copy.deepcopy(manifest)
    lot_dir = project_dir / lot_of(document)["output_frames_dir"]
    noms = sorted(p.name for p in lot_dir.iterdir())
    for nom in noms[1:]:
        (lot_dir / nom).unlink()
    lot_of(document)["expected_frame_count"] = 1
    plan = encode_module.plan_encode(project_dir, document, lot_id=LOT)
    assert plan.frame_count == 1 and plan.verdict.complete


# --------------------------------------------------------------------------
# AC 7 -- homogeneite des formes, avant la fabrique
# --------------------------------------------------------------------------


def test_heterogeneous_shapes_are_refused_before_any_encoding(tmp_path):
    """AC 7: le depot ne garantit **aucune** homogeneite.

    Chemin atteignable depuis la CLI: `scan --dpi` est obligatoire a chaque
    passe et n'est confronte a aucun `scan_dpi` deja persiste -- deux passes a
    deux dpi ecrivent deux formes dans le meme dossier. Mesure de la story 6.0:
    ffmpeg fige alors la geometrie sur la premiere entree et redimensionne les
    suivantes **en silence**, sans que le cardinal ne bouge.

    La forme divergente est placee ailleurs qu'en premiere position: c'est le
    seul montage qui demasque une garde ne sondant que la premiere frame.
    """
    import cv2

    project_dir, manifest = scanned_project(tmp_path)
    lot_dir = project_dir / lot_of(manifest)["output_frames_dir"]
    noms = sorted(p.name for p in lot_dir.iterdir())
    assert len(noms) >= 3
    divergente = np.full((120, 200, 3), 30000, np.uint16)
    cv2.imwrite(str(lot_dir / noms[2]), divergente)

    with pytest.raises(encode_module.EncodeDecisionError) as excinfo:
        encode_module.plan_encode(project_dir, manifest, lot_id=LOT)
    assert excinfo.value.code == encode_module.ENCODE_HETEROGENEOUS_SHAPES
    assert "200x120" in str(excinfo.value)
    assert not project_layout.outputs_dir(project_dir).exists()


# --------------------------------------------------------------------------
# AC 8 -- registre de resolutions
# --------------------------------------------------------------------------


def test_the_default_resolution_is_a_registry_entry_not_a_wired_constant():
    """AC 8 / EPIC6-ARB-5: le defaut est une entree comme les autres."""
    defaut = encode_module.resolve_output_resolution(None)
    assert defaut.resolution_id == encode_module.DEFAULT_RESOLUTION_ID
    assert defaut.size == (1920, 1080)
    assert encode_module.DEFAULT_RESOLUTION_ID in encode_module.RESOLUTION_REGISTRY


def test_adding_a_registry_entry_costs_one_line_and_no_code_path(monkeypatch):
    """AC 8b: **le** critere de faute verifiable en revue.

    Une entree ajoutee au registre doit traverser toute la chaine -- resolution,
    geometrie, segment de nom, aide de la CLI -- sans qu'aucune ligne de code ne
    soit touchee.
    """
    monkeypatch.setitem(
        encode_module.RESOLUTION_REGISTRY,
        "dci2k",
        encode_module.OutputResolution("dci2k", 2048, 1080),
    )
    cible = encode_module.resolve_output_resolution("dci2k")
    assert cible.size == (2048, 1080)
    arretee = encode_module.settle_resolution(cible, (551, 310))
    assert encode_module.resolution_name_segment(arretee) == "dci2k"
    assert "dci2k" in encode_module.known_resolution_ids()
    assert naming.build_master_filename(
        lot_id=LOT, profile_id="prores_hq", container="mov", resolution_segment="dci2k"
    ) == f"{LOT}_mmu_prores_hq_dci2k.mov"


def test_native_and_custom_resolutions_follow_the_same_scaling_path():
    """AC 8c: il n'existe pas deux recettes de redimensionnement."""
    native = encode_module.settle_resolution(
        encode_module.resolve_output_resolution("native"), (551, 310)
    )
    assert native.size == (551, 310)
    assert encode_module.resolution_name_segment(native) == "551x310"

    sur_mesure = encode_module.settle_resolution(
        encode_module.resolve_output_resolution("1280x720"), (551, 310)
    )
    assert sur_mesure.size == (1280, 720)
    assert encode_module.resolution_name_segment(sur_mesure) == "1280x720"

    # Une taille personnalisee qui coincide avec une entree nommee **reprend son
    # identite**: sinon deux noms de master differents designeraient un fichier
    # strictement identique.
    coincidence = encode_module.settle_resolution(
        encode_module.resolve_output_resolution("1920x1080"), (551, 310)
    )
    assert coincidence.resolution_id == encode_module.DEFAULT_RESOLUTION_ID
    assert encode_module.resolution_name_segment(coincidence) is None


def test_an_unknown_resolution_names_the_admitted_vocabulary():
    with pytest.raises(encode_module.EncodeDecisionError) as excinfo:
        encode_module.resolve_output_resolution("tres-grand")
    assert excinfo.value.code == encode_module.ENCODE_UNKNOWN_RESOLUTION
    assert "hd1080" in str(excinfo.value)


# --------------------------------------------------------------------------
# AC 9 / AC 10 -- cadence et timecode
# --------------------------------------------------------------------------


def test_the_frame_rate_goes_through_the_canonical_function(tmp_path):
    """AC 9: `fps_target_exact` n'est pas garanti sur un projet ne du scan.

    La cadence de **selection** passe donc systematiquement par
    `codec_profiles.exact_frame_rate`, et une cadence non entiere est
    **nominale** (le lot reel `TEST_FILE_12p5`). Depuis la story 6.6, ce champ
    n'alimente plus l'encodage (`plan.exact_frame_rate` est desormais la
    cadence source effective, `resolve_source_rate`) mais reste lisible au tag
    conteneur documentaire (`build_container_tags`, cle `fps_target`).
    """
    project_dir, manifest = scanned_project(
        tmp_path, fps_target=12.5, source_frame_count=12
    )
    document = copy.deepcopy(manifest)
    lot_of(document, naming.build_lot_id(RUSH, 12.5)).pop("fps_target_exact", None)
    plan = encode_module.plan_encode(
        project_dir, document, lot_id=naming.build_lot_id(RUSH, 12.5)
    )
    assert plan.container_tags["fps_target"] == "25/2"


def test_a_lot_born_from_the_scan_of_2_1_pages_now_encodes_without_the_option(tmp_path):
    """Story 2.7 (payload 2.1, `EPIC7-ARB-56`), renverse le baseline 6.6.

    **Comportement change, deliberement, par la story 2.7.** Un lot ne d'un scan
    de planches **2.1** porte desormais `timecode_base_fps` -- le vrai producteur
    (`build_page_payload`) l'exige sur toute planche d'images -- et
    `encode.resolve_source_rate` le lit sans aucune saisie manuelle: c'est FR17
    de l'Epic 7, zero saisie sur un lot ne du scan seul. C'etait refuse avant
    cette story (6.6, `ENCODE_SOURCE_RATE_MISSING`, voir le test symetrique
    ci-dessous pour un lot **pre-2.1**); ici le meme geste -- `with_extraction`
    reste `False`, aucun passage par `extract` -- **reussit**.
    """
    project_dir, manifest = scanned_project(tmp_path, with_extraction=False)
    lot = lot_of(manifest)
    assert lot.get("timecode_base_fps")
    plan = encode_module.plan_encode(project_dir, manifest, lot_id=LOT)
    # La cadence du master est celle du QR, mesuree sur le plan d'encodage --
    # pas seulement le fait qu'aucune exception n'ait ete levee (AC 5).
    assert plan.exact_frame_rate == lot["timecode_base_fps"]
    assert plan.timecode.emitted is not None  # AC 6: le timecode se reinjecte


def test_a_lot_born_from_the_scan_of_2_0_pages_is_still_refused_without_cadence_source(
    tmp_path,
):
    """AC 10 (2026-08-10) + story 6.6 AC 1bis (2026-08-13) -- **regime pre-2.1**.

    Un lot ne d'un scan de planches **anterieures a la story 2.7** (payload 2.0)
    ne porte pas `timecode_base_fps`: `strip_timecode_base_fps` simule cette
    fixture (AC 5, « lot sans champ (fixture pre-2.1) »), le seul geste possible
    depuis que le vrai producteur ne sait plus emettre un tel payload. Sans
    `--cadence-source` pour completer la cadence source manquante, la commande
    refuse **avant tout encodage**: jamais de repli silencieux sur `fps_target`
    -- ce comportement-la, lui, n'a pas bouge.
    """
    project_dir, manifest = scanned_project(tmp_path, with_extraction=False)
    strip_timecode_base_fps(project_dir, manifest)
    lot = lot_of(manifest)
    assert "timecode_base_fps" not in lot
    with pytest.raises(encode_module.EncodeDecisionError) as excinfo:
        encode_module.plan_encode(project_dir, manifest, lot_id=LOT)
    assert excinfo.value.code == encode_module.ENCODE_SOURCE_RATE_MISSING


def test_a_lot_born_from_the_scan_encodes_at_the_provided_cadence_source(tmp_path):
    """Story 6.6, AC 1bis: le meme lot **pre-2.1** que ci-dessus, complete
    explicitement.

    `--cadence-source` comble ce qu'aucune donnee ne porte -- jamais une valeur
    devinee. Le master mux desormais a cette cadence, pas a `fps_target`
    (AC 1), et un timecode redevient reinjectable puisque `plan_timecode` valide
    et exprime desormais contre la cadence source fournie.
    """
    project_dir, manifest = scanned_project(tmp_path, with_extraction=False)
    strip_timecode_base_fps(project_dir, manifest)
    lot = lot_of(manifest)
    plan = encode_module.plan_encode(
        project_dir, manifest, lot_id=LOT, cadence_source_override="25/1"
    )
    assert plan.exact_frame_rate == "25/1"
    assert plan.frame_rate == 25.0
    # fps_target (5.0, cf. `FPS`) ne gouverne plus rien de l'encodage: seule la
    # cadence source fournie s'y retrouve.
    assert plan.exact_frame_rate != codec_profiles.exact_frame_rate(FPS)


def test_cadence_source_option_wins_over_the_lot_when_both_are_present(tmp_path):
    """Story 2.7 (`EPIC7-ARB-56` / AC epics 2.7), **renverse le refus de 6.6**.

    Deux sources de verite pour la meme cadence coexistaient jusque-la en refus
    (`ENCODE_SOURCE_RATE_REDUNDANT`, teste jusqu'a la story 6.6). Depuis la
    story 2.7 l'option **prime**: le papier ne se met pas a jour
    (`EPIC7-ARB-51`), donc `--cadence-source` doit pouvoir corriger a
    l'encodage une cadence source fausse deja imprimee sur une planche. Les
    deux valeurs sont **distinguables** (regle des fabriques): la cadence source
    reelle du lot (mesuree, jamais recopiee ici -- l'extraction de ce fichier
    l'ecrit a `fps_source` = 30/1, cf. `FPS_SOURCE`/`rich_extraction_manifest`)
    et l'option 60/1, choisie **au-dessus** d'elle (une cadence plus basse
    ferait tomber le maintien de frame a zero ou moins, `ENCODE_HOLD_COUNT_NOT_POSITIVE`
    de la story 6.6 -- une autre garde, hors du champ de cette AC).
    """
    project_dir, manifest = scanned_project(tmp_path, with_extraction=True)
    lot = lot_of(manifest)
    valeur_du_lot = lot.get("timecode_base_fps")
    assert valeur_du_lot
    valeur_de_loption = "60/1"
    assert valeur_de_loption != valeur_du_lot  # regle des fabriques: distinguables

    plan = encode_module.plan_encode(
        project_dir, manifest, lot_id=LOT, cadence_source_override=valeur_de_loption
    )

    # L'option gagne: mesure sur le plan, pas seulement l'absence de refus.
    assert plan.exact_frame_rate == codec_profiles.exact_frame_rate(valeur_de_loption)
    assert plan.exact_frame_rate != codec_profiles.exact_frame_rate(valeur_du_lot)
    # L'avertissement structure nomme les deux valeurs et leur provenance.
    assert valeur_du_lot in plan.source_rate_override_note
    assert valeur_de_loption in plan.source_rate_override_note
    assert encode_module.ENCODE_SOURCE_RATE_REDUNDANT not in plan.findings


def test_a_source_base_timecode_beyond_the_target_rate_is_accepted(tmp_path):
    """AC 10, **le piege**: un test qui ne l'exerce pas ne prouve rien.

    Mesure: `codec_profiles.validate_timecode('00:00:00:12', 15)` passe, la ou la
    meme valeur confrontee a la cadence cible de 5 im/s leve, parce que la
    fonction applique `limit = ceil(rate)`. La validation porte donc sur la base
    **lue au manifest**, jamais sur `fps_target` -- et la valeur ressort ensuite
    telle quelle, parce que c'est une **etiquette**, pas une duree.

    **Consequence de la story 6.6, mesuree ici**: la base du manifest ET la
    cadence d'encodage sont desormais **la meme valeur** (`resolve_source_rate`
    lit `timecode_base_fps`, exactement ce que `plan_timecode` valide contre).
    Avant 6.6, elles differaient (30/1 au manifest, 15/1 au master) et
    l'etiquette restait representable par coincidence (`ff=12` existe aux deux
    cadences); ici, il n'y a plus de coincidence a demontrer -- les deux bases
    sont identiques par construction.
    """
    with pytest.raises(ValueError):
        codec_profiles.validate_timecode(START_TC, FPS)
    assert codec_profiles.validate_timecode(START_TC, "30/1") == START_TC

    project_dir, manifest = timecode_project(tmp_path)
    lot = lot_of(manifest, LOT_TC)
    assert lot["timecode_base_fps"] == "30/1"
    assert lot["first_frame_timecode"] == START_TC
    plan = encode_module.plan_encode(project_dir, manifest, lot_id=LOT_TC)
    assert plan.timecode.base_rate == "30/1"
    assert plan.timecode.manifest_value == START_TC
    # Story 6.6: la base du manifest EST la cadence d'encodage -- plus deux
    # bases distinctes qui coincident par chance.
    assert plan.timecode.base_rate == plan.exact_frame_rate == "30/1"
    assert plan.timecode.emitted == START_TC


def test_a_start_timecode_is_now_always_representable_when_the_lot_has_its_own_base(tmp_path):
    """AC 10 (2026-08-10) -- **renverse par la story 6.6 (2026-08-13)**.

    Avant 6.6: `00:00:00:16` est legal en base source 30 et **n'existait pas**
    a 15 im/s (`ff` y plafonnait a 14, cadence de mux = `fps_target`), donc
    aucun timecode n'etait emis (`ENCODE_TIMECODE_START_OUT_OF_BASE`).

    **Depuis 6.6, ce chemin de refus est mecaniquement inatteignable des que le
    lot porte sa propre `timecode_base_fps`**: la cadence de mux (AC 1) est
    desormais TOUJOURS cette meme valeur, jamais `fps_target` -- donc toute
    etiquette deja validee contre `timecode_base_fps` (juste avant, dans
    `plan_timecode`) est par construction representable dans la base du
    master, qui est la meme base. `express_timecode_in_master_base` ne peut
    plus rendre `None` que si l'appelant lui passe deux bases differentes, ce
    que `plan_encode` ne fait plus. **Consigne dans `deferred-work.md`**: le
    code `ENCODE_TIMECODE_START_OUT_OF_BASE` et cette branche sont candidats a
    un retrait de vocabulaire dedie (motif de la retraite du 2026-08-10 de
    `TIMECODE_NON_REINJECTABLE_A_CETTE_CADENCE`), hors perimetre de cette story.
    """
    project_dir, manifest = timecode_project(
        tmp_path, source_start_timecode=OUT_OF_BASE_TC
    )
    lot = lot_of(manifest, LOT_TC)
    assert lot["first_frame_timecode"] == OUT_OF_BASE_TC
    plan = encode_module.plan_encode(project_dir, manifest, lot_id=LOT_TC)
    assert encode_module.ENCODE_TIMECODE_START_OUT_OF_BASE not in plan.findings
    assert plan.timecode.manifest_value == OUT_OF_BASE_TC
    assert plan.timecode.emitted == OUT_OF_BASE_TC
    resume = encode_module.render_summary(plan)
    assert f"Timecode            : {OUT_OF_BASE_TC}" in resume
    # Et le master produit porte reellement l'etiquette: le fichier fini est
    # regarde, pas seulement la decision.
    swept = encode_module.prepare_output_directory(plan)
    result = encode_module.execute_plan(plan, swept=swept)
    master = Path(result.outcome.output_path)
    assert codec_profiles.timecodes_equivalent(
        video_metadata._find_timecode(video_metadata.probe_media(str(master))),
        OUT_OF_BASE_TC,
    )


def test_below_the_old_window_the_timecode_is_really_reinjected(tmp_path):
    """**Levee de l'abstention du 2026-08-10**, mesuree sur le produit fini.

    Etat precedent: cette story refusait de reinjecter tout timecode hors de la
    fenetre `11 <= ceil(cadence) <= 100`, sous le constat
    `TIMECODE_NON_REINJECTABLE_A_CETTE_CADENCE`. Le repli est devenu une perte
    seche avec la correction de la story 6.0 (commit `8713094`), qui rend la
    confrontation agnostique a la largeur d'ecriture -- ce que ce test
    verrouille sur le **fichier**, pas sur la decision.

    **Note story 6.6**: le lot mux desormais a `timecode_base_fps` (30/1),
    plus a `fps_target` (5/1) -- l'ecart d'ecriture entre la demande et la
    relecture qui motivait a l'origine ce test (`00:00:00:3` contre
    `00:00:00:03`) apparaissait a 5 im/s (`ff` sur un chiffre) et ne se
    reproduit plus a 30 im/s (`ff` sur deux chiffres, largeur qui coincide).
    Ce que le test verrouille reste vrai malgre tout: reinjection reelle,
    identite d'image confirmee **quelle que soit l'ecriture exacte**, et refus
    d'une autre image.
    """
    project_dir, manifest = scanned_project(tmp_path, source_start_timecode="00:00:00:03")
    assert lot_of(manifest)["timecode_base_fps"] == "30/1"
    plan = encode_module.plan_encode(project_dir, manifest, lot_id=LOT)
    assert plan.exact_frame_rate == "30/1"
    assert plan.timecode.emitted == "00:00:00:03"
    assert plan.findings == (encode_module.ENCODE_SRGB_APPROXIMATION,)
    resume = encode_module.render_summary(plan)
    assert "Timecode            : 00:00:00:03" in resume
    # Le recapitulatif n'annonce plus une abstention qui n'a plus lieu.
    assert "11 <= ceil(cadence) <= 100" not in resume
    assert "TIMECODE_NON_REINJECTABLE_A_CETTE_CADENCE" not in resume

    swept = encode_module.prepare_output_directory(plan)
    result = encode_module.execute_plan(plan, swept=swept)
    master = Path(result.outcome.output_path)
    relu = video_metadata._find_timecode(video_metadata.probe_media(str(master)))
    assert codec_profiles.timecodes_equivalent(relu, plan.timecode.emitted)
    assert result.verification["timecode"]["ok"] is True
    assert all(entry["ok"] for entry in result.verification.values())

    # Et la verification n'est pas devenue complaisante: une **autre** image est
    # toujours refusee, des deux cotes de l'ecriture (une position, deux
    # ecritures, pour qu'un test qui ne regarderait que la largeur echoue ici).
    for faux in ("00:00:00:2", "00:00:00:02", "00:00:01:00", "00:00:00:4"):
        rapport = video_metadata.verify_technical_metadata(
            str(master), {"timecode": faux}, require_mandatory=False
        )
        assert rapport["timecode"]["ok"] is False, faux


def test_at_one_image_per_second_the_timecode_is_reinjected_too(tmp_path):
    """Borne basse absolue: `ceil(1) = 1`, donc `ff` ne peut valoir que 0.

    C'est la cadence ou l'ancienne abstention mordait le plus fort, et celle ou
    l'ecriture d'ffmpeg est la plus eloignee de la forme canonique. Un lot de
    deux frames suffit et il en faut deux: une fabrique mono-element rendrait
    invisible toute erreur d'appariement (regle des fabriques du `CLAUDE.md`).
    """
    project_dir, manifest = scanned_project(tmp_path, fps_target=1.0)
    lot_id = naming.build_lot_id(RUSH, 1.0)
    lot = lot_of(manifest, lot_id)
    assert lot["timecode_base_fps"] == "30/1"
    plan = encode_module.plan_encode(project_dir, manifest, lot_id=lot_id)
    # Story 6.6: la cadence de mux est la cadence source (30/1), plus `fps_target`
    # (1/1) -- la distinction est ce que ce test verrouillait deja pour la
    # SELECTION (`plan.frame_paths`, inchange), et non pour l'encodage.
    assert plan.exact_frame_rate == "30/1"
    assert len(plan.frame_paths) == 2
    assert plan.sequence_timecodes == ("00:00:00:00", "00:00:01:00")
    assert plan.timecode.emitted == "00:00:00:00"

    swept = encode_module.prepare_output_directory(plan)
    result = encode_module.execute_plan(plan, swept=swept)
    master = Path(result.outcome.output_path)
    relu = video_metadata._find_timecode(video_metadata.probe_media(str(master)))
    assert codec_profiles.timecodes_equivalent(relu, plan.timecode.emitted)
    assert result.verification["timecode"]["ok"] is True


def test_no_cadence_abstains_from_the_timecode_any_more(tmp_path):
    """Aucune cadence n'abstient, ni sous la fenetre ni au-dessus.

    Les cadences sont parcourues avec les cas **hors fenetre au milieu et en
    fin** de table, jamais en premiere position: une garde qui ne regarderait
    que la premiere cadence, ou un test qui ne lirait que son premier resultat,
    ne se demasquent pas autrement (regle des fabriques du `CLAUDE.md`).

    L'appel est fait ici directement sur `plan_timecode` parce que les cadences
    au-dessus de la fenetre ne sont pas productibles par la chaine reelle -- la
    selection deterministe plafonne a 60 im/s (`frame_selection.py:214`). Le lot
    et la sequence, eux, restent ceux du vrai producteur.
    """
    project_dir, manifest = scanned_project(tmp_path, source_start_timecode="00:00:00:03")
    lot = lot_of(manifest)
    plan = encode_module.plan_encode(project_dir, manifest, lot_id=LOT)
    lot_dir = encode_module.check_lot_admission(lot, project_dir)
    sequence = encode_module.plan_sequence(
        [entry.name for entry in lot_dir.iterdir()],
        rush_id=RUSH,
        fps_target=FPS,
    )
    # Une fabrique mono-element ne prouverait rien: la sequence porte huit
    # timecodes distincts, et le depart vise n'est pas le seul present.
    assert len(sequence.timecodes) == 8
    assert len(set(sequence.timecodes)) == 8

    # `00:00:00:03` est representable partout ici: `ff = 3 < ceil(cadence)` des
    # 4 im/s. Les trois cadences hors de l'ancienne fenetre sont en 2e, 4e et
    # 5e position, la cadence temoin ouvrant la table.
    for cadence, largeur_ffmpeg in (
        ("25/1", 2),    # temoin, dans l'ancienne fenetre
        ("5/1", 1),     # sous la fenetre
        ("25/2", 2),    # temoin, 12,5 im/s
        ("10/1", 1),    # sous la fenetre
        ("120/1", 3),   # au-dessus de la fenetre
    ):
        resolu = encode_module.plan_timecode(lot, sequence, master_rate=cadence)
        assert resolu.emitted == "00:00:00:03", cadence
        assert resolu.findings == (), cadence
        # La largeur d'ecriture d'ffmpeg est bien celle qui motivait l'ancienne
        # abstention: le fait est intact, c'est la conclusion qui a change.
        assert codec_profiles.timecode_frame_field_width(cadence) == largeur_ffmpeg

    # Le vocabulaire ferme ne porte plus le constat retire, et **le module ne
    # peut plus l'emettre**: frontiere negative sur les litteraux du code,
    # docstrings exclues -- le module explique le retrait, il ne le pratique
    # plus. Sans elle, une reprise pourrait remettre le code sans remettre la
    # garde, ou l'inverse, et rien ne le dirait.
    assert not hasattr(encode_module, "ENCODE_TIMECODE_RATE_UNSUPPORTED")
    assert not any("NON_REINJECTABLE" in code for code in encode_module.ENCODE_CODES)
    assert not any(
        "NON_REINJECTABLE" in litteral
        for litteral in _code_string_literals(ENCODE_MODULE_PATH)
    )
    assert plan.timecode.emitted == "00:00:00:03"


def test_the_start_timecode_is_an_image_label_and_is_never_rescaled():
    """AC 10, **decision de sens tranchee** apres remesure du 2026-08-10.

    La revision precedente rescalait le timecode "dans la base du master", au
    motif que ffmpeg re-rendrait `-timecode` a la cadence de sortie. La mesure
    dit autre chose: a `-r 25/2`, `00:00:00:04`, `00:00:00:12`, `00:00:02:00` et
    `01:00:00:00` ressortent **verbatim**; seul `00:00:00:14` bouge, et il bouge
    parce qu'il est **illegal** a 12,5 im/s (`ff` y plafonne a 12) -- ffmpeg le
    normalise en `00:00:01:01`, c'est-a-dire par debordement, pas par rescalage.

    Les deux reponses possibles divergent, et il faut choisir: preserver
    l'**instant** (le rescalage: `01:00:00:00` en base `25/1` devenait
    `00:57:41:07` a 12,5 im/s, 2 min 19 s plus tot) ou preserver l'**etiquette**,
    qui designe l'image source. C'est l'etiquette qui est retenue: le timecode
    sert a raccrocher le master a son rush, et `00:57:41:07` ne raccroche a rien.

    Les deux cotes de la frontiere sont ici: representable -> verbatim,
    non representable -> `None`, jamais une autre valeur.
    """
    # Bases differentes, etiquette representable: verbatim, sans calcul.
    assert encode_module.express_timecode_in_master_base("01:00:00:00", "25/2") == "01:00:00:00"
    assert encode_module.express_timecode_in_master_base("00:00:00:12", "25/2") == "00:00:00:12"
    # Bases egales: meme regle, jamais une branche a part.
    assert encode_module.express_timecode_in_master_base("01:00:00:00", "25/1") == "01:00:00:00"
    # Etiquette absente de la base du master: aucune autre n'est inventee.
    assert encode_module.express_timecode_in_master_base("00:00:00:14", "25/2") is None
    assert encode_module.express_timecode_in_master_base("00:00:00:16", "15/1") is None
    # **La borne elle-meme**, des deux cotes: `ff` va de 0 a `ceil(cadence) - 1`.
    # Sans ces quatre valeurs, un decalage d'une image sur la borne passe -- la
    # campagne de mutation l'a mesure, le mutant `>=` devenu `>` survivait.
    assert encode_module.express_timecode_in_master_base("00:00:00:12", "25/2") == "00:00:00:12"
    assert encode_module.express_timecode_in_master_base("00:00:00:13", "25/2") is None
    assert encode_module.express_timecode_in_master_base("00:00:00:14", "15/1") == "00:00:00:14"
    assert encode_module.express_timecode_in_master_base("00:00:00:15", "15/1") is None
    # La valeur que l'ancien rescalage produisait, ecrite ici pour que la
    # revision suivante voie ce qui a ete refuse et pourquoi: 90000 images a
    # 25 im/s -> 45000 a 12,5, re-exprimees a 13 images par seconde de timecode.
    assert encode_module.frames_per_timecode_second("25/2") == 13
    assert 90000 // 25 * 12.5 == 45000 and 45000 // 13 == 3461
    assert encode_module.express_timecode_in_master_base("01:00:00:00", "25/2") != "00:57:41:07"


def test_hold_counts_are_all_one_when_k_equals_one():
    """Story 6.6, AC 9, piege 3 des Dev Notes: le cas degenere `k=1`
    (`fps_target == timecode_base_fps`) n'etait verrouille par aucun test
    dedie -- trouve par l'Acceptance Auditor de la revue en trois couches.

    Sans decimation (chaque frame source est retenue), l'ecart entre deux
    timecodes consecutifs vaut toujours 1: aucune duplication, comportement
    identique a celui d'avant la story pour ce cas precis.
    """
    timecodes = ["00:00:00:00", "00:00:00:01", "00:00:00:02", "00:00:00:03", "00:00:00:04"]
    assert encode_module._hold_counts(timecodes, rate="25/1", source_tail_frames=None) == \
        [1, 1, 1, 1, 1]
    assert encode_module._hold_counts(timecodes, rate="25/1", source_tail_frames=0) == \
        [1, 1, 1, 1, 1]


def test_a_lot_at_the_source_rate_is_encoded_without_any_duplication(tmp_path):
    """Story 6.6, AC 9, meme piege que ci-dessus, mesure de bout en bout sur un
    lot reel dont `fps_target` coincide avec `timecode_base_fps` (30/1, la
    cadence source de cette suite): la liste muxee EST la liste distincte,
    frame a frame, et le master ne contient aucune image tenue plus d'une
    fois.
    """
    project_dir, manifest = scanned_project(tmp_path, fps_target=float(FPS_SOURCE))
    lot_id = naming.build_lot_id(RUSH, float(FPS_SOURCE))
    lot = lot_of(manifest, lot_id)
    assert lot["timecode_base_fps"] == "30/1"
    plan = encode_module.plan_encode(project_dir, manifest, lot_id=lot_id)
    assert plan.exact_frame_rate == "30/1"
    assert plan.muxed_frame_paths == plan.frame_paths

    swept = encode_module.prepare_output_directory(plan)
    result = encode_module.execute_plan(plan, swept=swept)
    assert result.outcome.frame_count == len(plan.frame_paths)


def test_hold_counts_are_constant_when_k_is_an_integer():
    """Story 6.6, AC 3/AC 4 (regime a ecart constant).

    `fps_target=12.5` depuis une source a 25 im/s: `k=2`, exactement le lot
    reel qui a motive la story (`rush-bitch-4_12p5-7f152a04`). Toutes les
    frames sauf la derniere sont tenues 2 fois.
    """
    timecodes = ["00:00:00:00", "00:00:00:02", "00:00:00:04", "00:00:00:06", "00:00:00:08"]
    assert encode_module._hold_counts(timecodes, rate="25/1", source_tail_frames=None) == \
        [2, 2, 2, 2, 1]
    assert encode_module._hold_counts(timecodes, rate="25/1", source_tail_frames=0) == \
        [2, 2, 2, 2, 1]


def test_hold_counts_alternate_when_k_is_not_an_integer():
    """Story 6.6, AC 3/AC 4 (regime a ecart alternant, jamais teste par le seul
    cas constant -- meme famille de risque que la regle des fabriques du
    `CLAUDE.md`, transposee a un motif de maintien.

    `fps_target=20` depuis une source a 25 im/s: `k=1,25`, indices retenus
    0,1,2,3,5,6,7,8 sur la premiere seconde -- motif d'ecart `1,1,1,2` repete.
    """
    timecodes = [
        "00:00:00:00", "00:00:00:01", "00:00:00:02", "00:00:00:03",
        "00:00:00:05", "00:00:00:06", "00:00:00:07", "00:00:00:08",
    ]
    assert encode_module._hold_counts(timecodes, rate="25/1", source_tail_frames=None) == \
        [1, 1, 1, 2, 1, 1, 1, 1]


def test_hold_counts_last_frame_covers_the_declared_tail():
    """Story 6.6, AC 3/AC 5: `hold_count(N-1) = 1 + source_tail_frames` quand ce
    champ est connu -- formule `EPIC6-ARB-6`.
    """
    timecodes = ["00:00:00:00", "00:00:00:02"]
    assert encode_module._hold_counts(timecodes, rate="25/1", source_tail_frames=3) == [2, 4]
    assert encode_module._hold_counts(timecodes, rate="25/1", source_tail_frames=0) == [2, 1]


def test_hold_counts_never_guesses_a_tail_it_cannot_observe():
    """Story 6.6, AC 5/AC 8, piege 8: sans `source_tail_frames`, la derniere
    frame est tenue exactement une fois -- jamais une estimation.
    """
    assert encode_module._hold_counts(
        ["00:00:00:05"], rate="25/1", source_tail_frames=2
    ) == [3]
    assert encode_module._hold_counts(
        ["00:00:00:05"], rate="25/1", source_tail_frames=None
    ) == [1]
    assert encode_module._hold_counts([], rate="25/1", source_tail_frames=5) == []


def test_hold_counts_refuses_rather_than_silently_dropping_a_frame():
    """Story 6.6, trouve par la revue en trois couches (Edge Case Hunter,
    finding 1): un `hold_count` calcule non strictement positif effacerait
    silencieusement une frame du master (`range(count)` vide) sans aucun
    signal. Reproduit exactement le repro mesure par la revue: une cadence
    source fournie (24) plus basse que celle reellement encodee dans les
    timecodes (dont le `ff` atteint 25, illegal a 24 im/s) fait reculer
    l'index calcule.
    """
    with pytest.raises(encode_module.EncodeDecisionError) as excinfo:
        encode_module._hold_counts(
            ["00:00:00:25", "00:00:01:00"], rate="24/1", source_tail_frames=None
        )
    assert excinfo.value.code == encode_module.ENCODE_HOLD_COUNT_NOT_POSITIVE

    # Meme refus par l'autre voie: source_tail_frames negatif (manifest
    # corrompu) fait tomber le dernier hold_count a zero ou moins.
    with pytest.raises(encode_module.EncodeDecisionError) as excinfo:
        encode_module._hold_counts(
            ["00:00:00:05"], rate="25/1", source_tail_frames=-2
        )
    assert excinfo.value.code == encode_module.ENCODE_HOLD_COUNT_NOT_POSITIVE


def test_hold_counts_refuses_an_unreadable_tail_instead_of_a_bare_valueerror():
    """Story 6.6, finding 3 de la revue: `source_tail_frames` non convertible
    en entier (manifest corrompu) ne doit pas remonter un `ValueError` nu.
    """
    with pytest.raises(encode_module.EncodeDecisionError) as excinfo:
        encode_module._hold_counts(
            ["00:00:00:05"], rate="25/1", source_tail_frames="pas un entier"
        )
    assert excinfo.value.code == encode_module.ENCODE_SOURCE_TAIL_FRAMES_UNUSABLE


def test_resolve_source_rate_treats_a_present_but_unusable_base_as_present():
    """Story 6.6, finding 4 de la revue: `timecode_base_fps=0` est **present
    mais inexploitable**, pas **absent** -- coherent avec `resolve_frame_rate`,
    qui traite `fps_target=0` de la meme facon (`ENCODE_FRAME_RATE_UNUSABLE`,
    jamais un message qui dit "le champ est absent" pour une valeur qui,
    justement, y est.
    """
    with pytest.raises(encode_module.EncodeDecisionError) as excinfo:
        encode_module.resolve_source_rate({"lot_id": "x", "timecode_base_fps": 0})
    assert excinfo.value.code == encode_module.ENCODE_FRAME_RATE_UNUSABLE

    with pytest.raises(encode_module.EncodeDecisionError) as excinfo:
        encode_module.resolve_source_rate({"lot_id": "x", "timecode_base_fps": True})
    assert excinfo.value.code == encode_module.ENCODE_FRAME_RATE_UNUSABLE


def test_resolve_source_rate_override_note_is_readable_when_lot_id_is_missing():
    """Revue de vague 0 (Epic 7), finding Blind Hunter: l'avertissement
    structure du quatrieme cas (les deux presents, l'option prime) lisait
    autrefois `lot.get("lot_id")` sans repli -- un lot sans identite y
    affichait "lot None: ..." plutot qu'un texte lisible.
    """
    _, _, note = encode_module.resolve_source_rate(
        {"timecode_base_fps": "25/1"}, cadence_source_override="30000/1001"
    )
    assert note is not None
    assert "lot None" not in note
    assert "<identite absente>" in note


def test_an_incomplete_lot_never_fills_its_gap_by_repeating_a_frame(tmp_path):
    """Story 6.6, garde trouvee en integration (hors AC ecrites de la story).

    Un lot incomplet (page perdue, `--accept-incomplete-lot`) a un ecart
    anormalement grand entre deux timecodes retenus consecutifs, exactement a
    l'endroit du trou -- indistinguable, dans la seule structure des
    timecodes, d'un ecart de decimation normal. Appliquer `hold_count` sans
    garde y tiendrait une frame plus longtemps pile sur le trou, c'est-a-dire
    combler un manque par la repetition de l'image precedente: le module
    l'interdit en toutes lettres pour `--accept-incomplete-lot`. Sur un lot
    incomplet, aucune frame n'est donc tenue.
    """
    project_dir, manifest = scanned_project(tmp_path, absent_pages=(1,))
    plan = encode_module.plan_encode(
        project_dir, manifest, lot_id=LOT, accept_incomplete=True
    )
    assert plan.verdict.complete is False
    # Aucune duplication: la liste muxee EST la liste distincte, frame a frame.
    assert plan.muxed_frame_paths == plan.frame_paths

    swept = encode_module.prepare_output_directory(plan)
    result = encode_module.execute_plan(plan, swept=swept)
    assert result.outcome.frame_count == len(plan.frame_paths)


def test_a_start_timecode_that_is_not_the_first_present_frame_is_flagged(tmp_path):
    """AC 10, **bloquant de la revue**: le constat portait sur une branche morte.

    Il n'etait emis que si `timecode_base_fps` etait present **et**
    `first_frame_timecode` absent -- combinaison qu'aucun producteur du depot ne
    sait ecrire (`io/extraction_manifest.py:825-826` les pose sur deux lignes
    consecutives). Le cas reel -- un trou en tete, sous le drapeau
    d'`EPIC6-ARB-3` -- passait donc en silence: le master portait un timecode
    designant une image absente.

    L'etat exerce ici est **productible de bout en bout**: la page 0 n'est
    jamais passee au scanner, et le manifest garde ses deux champs.
    """
    project_dir, manifest = timecode_project(tmp_path, absent_pages=(0,))
    lot = lot_of(manifest, LOT_TC)
    assert lot["first_frame_timecode"] == START_TC  # le manifest garde ses champs
    plan = encode_module.plan_encode(
        project_dir, manifest, lot_id=LOT_TC, accept_incomplete=True
    )
    assert encode_module.ENCODE_TIMECODE_NOT_LOT_START in plan.findings
    premiere = naming.read_scan_frame_timecode(plan.frame_paths[0].name)
    assert premiere != START_TC
    assert encode_module.ENCODE_TIMECODE_NOT_LOT_START in encode_module.render_summary(plan)


def test_a_complete_lot_carries_no_non_canonical_start_finding(tmp_path):
    """Contre-epreuve: sans elle, le test precedent serait vrai par construction.

    Un lot complet part bien de sa premiere frame, et le constat doit rester
    absent -- y compris quand les deux bases different, ce qui est le cas de tous
    les lots du depot.
    """
    project_dir, manifest = timecode_project(tmp_path)
    plan = encode_module.plan_encode(project_dir, manifest, lot_id=LOT_TC)
    assert plan.verdict.complete
    assert encode_module.ENCODE_TIMECODE_NOT_LOT_START not in plan.findings
    assert plan.timecode.emitted == START_TC


# --------------------------------------------------------------------------
# AC 11 -- tags derives de la matrice 2.4
# --------------------------------------------------------------------------


def test_container_tags_are_derived_from_the_responsibility_matrix(tmp_path):
    """AC 11: calcules depuis `io.metadata_matrix`, jamais retapes.

    Consequence directe et verifiable: `lot_id` est `FORBIDDEN` au conteneur
    video et n'est donc **jamais** tague, si evident qu'il paraisse de le poser.
    """
    project_dir, manifest = scanned_project(tmp_path)
    plan = encode_module.plan_encode(project_dir, manifest, lot_id=LOT)
    canal = metadata_matrix.Channel.VIDEO_CONTAINER
    assert "lot_id" not in plan.container_tags
    assert not metadata_matrix.is_allowed("lot_id", canal)
    for name in plan.container_tags:
        assert metadata_matrix.is_allowed(name, canal)
    requis = {
        name
        for name in metadata_matrix.known_fields()
        if metadata_matrix.get_cell(name, canal).responsibility
        is metadata_matrix.Responsibility.REQUIRED
    }
    assert requis <= set(plan.container_tags)
    assert plan.container_tags["codec_target_profile"] == "prores_hq"
    assert plan.container_tags["fps_target"] == "5/1"


# --------------------------------------------------------------------------
# AC 12 -- emplacement et nom du master
# --------------------------------------------------------------------------


def test_the_master_name_carries_the_lot_the_profile_and_hors_defaut_resolution(tmp_path):
    """AC 12: deux resolutions, deux noms distincts."""
    project_dir, manifest = scanned_project(tmp_path)
    defaut = encode_module.plan_encode(project_dir, manifest, lot_id=LOT)
    natif = encode_module.plan_encode(
        project_dir, manifest, lot_id=LOT, resolution="native"
    )
    assert defaut.output_path.name == f"{LOT}_mmu_prores_hq.mov"
    assert natif.output_path.name == f"{LOT}_mmu_prores_hq_551x310.mov"
    assert defaut.output_path != natif.output_path
    assert defaut.output_path.parent == project_dir / project_layout.OUTPUTS_DIRNAME


def test_the_outputs_directory_name_is_declared_once_in_the_repository():
    """AC 12: la constante d'arborescence n'est jamais doublee.

    `cli.py` portait la chaine `"outputs"` en dur a deux endroits; elle vient
    desormais de `io.project_layout`. Le grep porte sur le code, pas sur les
    commentaires: c'est la seule formulation qui a un sens verifiable.
    """
    assert project_layout.OUTPUTS_DIRNAME == "outputs"
    literals = _code_string_literals(CLI_MODULE_PATH)
    # `outputs/` (avec la barre) reste dans le manifest **legacy** du POC, qui
    # n'est pas un chemin d'arborescence v2: il est hors du perimetre de la
    # constante, et le dire vaut mieux que le confondre.
    assert "outputs" not in literals


def test_no_master_name_collides_across_the_catalogue():
    noms = {
        naming.build_master_filename(
            lot_id=LOT, profile_id=profile_id, container=profile.container
        )
        for profile_id, profile in codec_profiles.PROFILES.items()
    }
    assert len(noms) == len(codec_profiles.PROFILES)


# --------------------------------------------------------------------------
# AC 13 / AC 15 -- ecrasement, verification avant bascule
# --------------------------------------------------------------------------


def test_an_existing_master_fails_the_command_before_any_encoding(tmp_path):
    """AC 13: le refus a lieu **pendant le plan**, jamais apres 900 frames lues."""
    project_dir, manifest = scanned_project(tmp_path)
    plan = encode_module.plan_encode(project_dir, manifest, lot_id=LOT)
    plan.output_path.parent.mkdir(parents=True, exist_ok=True)
    plan.output_path.write_bytes(b"master precedent")

    with pytest.raises(encode_module.EncodeDecisionError) as excinfo:
        encode_module.plan_encode(project_dir, manifest, lot_id=LOT)
    assert excinfo.value.code == encode_module.ENCODE_MASTER_ALREADY_PRESENT
    assert plan.output_path.read_bytes() == b"master precedent"

    # Avec le drapeau, le plan passe -- et rien n'est encore ecrit.
    encode_module.plan_encode(project_dir, manifest, lot_id=LOT, overwrite=True)
    assert plan.output_path.read_bytes() == b"master precedent"


def test_outputs_present_as_a_file_is_a_named_refusal(tmp_path):
    """AC 17: `mkdir(parents=True, exist_ok=True)` leve un `FileExistsError` nu."""
    project_dir, manifest = scanned_project(tmp_path)
    project_layout.outputs_dir(project_dir).write_text("pas un dossier", encoding="utf-8")
    with pytest.raises(encode_module.EncodeDecisionError) as excinfo:
        encode_module.plan_encode(project_dir, manifest, lot_id=LOT)
    assert excinfo.value.code == encode_module.ENCODE_OUTPUTS_IS_A_FILE


def test_a_failed_verification_leaves_the_previous_master_intact(tmp_path, monkeypatch):
    """AC 13 / AC 15: la verification porte sur le fichier **avant** bascule.

    Sinon un master valide serait remplace par un fichier que la commande vient
    de declarer non conforme, l'AC 13 disant l'inverse dans son propre titre. Le
    fichier fautif est conserve pour diagnostic.
    """
    project_dir, manifest = scanned_project(tmp_path)
    plan = encode_module.plan_encode(project_dir, manifest, lot_id=LOT, overwrite=True)
    encode_module.prepare_output_directory(plan)
    precedent = b"master precedent, parfaitement valide"
    plan.output_path.write_bytes(precedent)

    attendu = dict(encode_module.expected_technical_metadata(plan))
    attendu["codec"] = "un-codec-qui-n-existe-pas"
    monkeypatch.setattr(
        encode_module, "expected_technical_metadata", lambda _plan: attendu
    )
    with pytest.raises(encode_module.EncodeVerificationRefused) as excinfo:
        encode_module.execute_plan(plan)

    assert plan.output_path.read_bytes() == precedent
    assert excinfo.value.staged_path.is_file()
    assert excinfo.value.staged_path.name.startswith(".")

    # **Pas de DOUBLE EXTENSION** (2026-09-06, retour d'Egan: il a du supprimer
    # a la main un `.<nom>.mov.<pid>-<hex>.mov`). Le nom d'attente se batit sur
    # le **tronc** de la cible, pas sur son nom complet, qui portait deja
    # l'extension du conteneur.
    #
    # Frontiere ecrite des deux cotes, parce que retirer l'extension de queue
    # serait l'autre facon de fermer le doublon -- et elle casserait tout:
    # `run_encode` refuse un chemin d'attente dont l'extension contredit le
    # conteneur, et le balayage ne reconnaitrait plus le residu.
    nom_attente = excinfo.value.staged_path.name
    conteneur = plan.output_path.suffix
    assert nom_attente.endswith(conteneur), nom_attente
    assert nom_attente.count(conteneur) == 1, (
        f"double extension dans le nom du fichier d'attente: {nom_attente}"
    )
    assert plan.output_path.stem in nom_attente, nom_attente

    # **Le refus nomme les deux outils** (2026-09-06). Ce message est remonte du
    # terrain sans version, et le diagnostic a coute une soiree entiere: la
    # cause etait un renversement de comportement de ffmpeg entre 6 et 8 sur le
    # tagage colorimetrique, que le seul numero de version aurait designe
    # d'emblee. Frontiere ecrite sur la version **relevee**, jamais sur un
    # litteral: elle doit tenir dans un conteneur qui porte un autre binaire.
    message = str(excinfo.value)
    releve = codec_profiles.probe_tool_version("ffmpeg")
    assert releve != codec_profiles.TOOL_VERSION_UNKNOWN, "ffmpeg introuvable"
    assert f"ffmpeg {releve}" in message, message
    assert "ffprobe " in message, message
    # Le fichier d'attente reste balayable par la fabrique 6.0.
    assert codec_profiles.sweep_encode_residues(
        plan.output_path.parent, max_age_seconds=-1
    ) == [excinfo.value.staged_path]


def test_the_technical_verification_covers_the_mandatory_fields(tmp_path):
    """AC 15: une demande vide de champs obligatoires rend une verification
    vide de sens, sur laquelle `all(...)` vaut `True`.

    **Le timecode est du meme bois, et il n'etait pinne nulle part** (survivant
    `H02` de la passe de cloture du 2026-08-10): retirer le timecode de la
    demande laissait les 73 tests verts. Le produit fini etait certes relu par
    `ffprobe` dans un autre test, mais l'assertion `all(entry['ok'] ...)` du
    rapport devenait vraie **par vacuite** -- exactement le defaut que cette AC
    nomme pour les champs obligatoires, reproduit sur le seul champ conditionnel.
    Consequence reelle: un master sorti sans timecode, ou avec un autre, passait
    la verification et basculait.

    Les deux cotes de la condition sont donc exerces, et c'est ce qui la pinne:
    un lot qui **emet** une etiquette la met dans la demande, un lot qui n'en
    emet aucune n'y met rien -- sans quoi la verification confronterait un champ
    que le master n'a aucune raison de porter.

    Reecriture du 2026-08-10: le cote "aucune etiquette" reposait sur le lot a
    5 im/s, que l'abstention de cadence privait de timecode. L'abstention est
    levee et ce lot **en porte un** desormais; le cote absent est donc pris sur
    le lot ne du scan seul, qui ne porte aucune base de timecode -- une
    abstention de sens, celle-la, et non de mise en forme.

    **Story 6.6**: un lot ne du scan seul n'a plus le droit d'atteindre
    `plan_encode` sans `--cadence-source` (AC 1bis) -- fourni ici pour
    atteindre le meme point qu'avant 2026-08-10, mais `plan_timecode` lit
    `lot["timecode_base_fps"]` **directement** et non la cadence source
    fournie: l'absence de base de timecode reste donc entiere, et le cote
    "aucune etiquette" de ce test tient toujours.

    **Story 2.7**: depuis le payload 2.1, un lot ne du scan seul porte
    desormais `timecode_base_fps` par construction -- le vrai producteur
    l'exige sur toute planche d'images -- donc l'abstention de timecode que ce
    cote du test mesure n'est plus atteignable par le regime scan-only "tel
    quel". `strip_timecode_base_fps` la fait revivre en simulant le regime
    **pre-2.1** (planche imprimee en payload 2.0), seul geste fidele depuis que
    le producteur ne sait plus emettre le payload prive du champ.
    """
    project_dir, manifest = scanned_project(tmp_path, with_extraction=False)
    strip_timecode_base_fps(project_dir, manifest)
    plan = encode_module.plan_encode(
        project_dir, manifest, lot_id=LOT, cadence_source_override="30/1"
    )
    attendu = encode_module.expected_technical_metadata(plan)
    assert set(video_metadata.MANDATORY_TECHNICAL_FIELDS) <= set(attendu)
    # Ni `timecode_base` ni `timecode_base_fps` au QR: rien a confronter, meme
    # avec la cadence source completee par l'operateur.
    assert plan.timecode.emitted is None
    assert "timecode" not in attendu

    projet_tc, manifest_tc = timecode_project(tmp_path / "avec-timecode")
    plan_tc = encode_module.plan_encode(projet_tc, manifest_tc, lot_id=LOT_TC)
    attendu_tc = encode_module.expected_technical_metadata(plan_tc)
    assert plan_tc.timecode.emitted == START_TC
    assert attendu_tc["timecode"] == START_TC


# --------------------------------------------------------------------------
# AC 14 -- recapitulatif et confirmation
# --------------------------------------------------------------------------


def test_estimated_bytes_reflects_the_muxed_count_not_the_distinct_one(tmp_path):
    """Story 6.6, trouve par la revue en trois couches (Edge Case Hunter,
    finding 2): l'estimation de poids doit rester **majorante, jamais
    optimiste** (Piege 12 de la story 3.3). Sur un lot decime (k=6 ici,
    `FPS=5` depuis `FPS_SOURCE=30`), le master reel contient bien plus de
    frames que `frame_count` (le compte **distinct** retenu) -- calculer
    l'estimation depuis `frame_count` la sous-estimerait d'un facteur egal au
    maintien moyen.
    """
    project_dir, manifest = scanned_project(tmp_path)
    plan = encode_module.plan_encode(project_dir, manifest, lot_id=LOT)
    assert len(plan.muxed_frame_paths) > plan.frame_count
    width, height = plan.resolution.size or plan.source_size
    assert plan.estimated_bytes == width * height * 3 * len(plan.muxed_frame_paths)
    assert plan.estimated_bytes > width * height * 3 * plan.frame_count


def test_the_summary_says_everything_the_ac_requires(tmp_path):
    project_dir, manifest = timecode_project(tmp_path)
    plan = encode_module.plan_encode(project_dir, manifest, lot_id=LOT_TC)
    resume = encode_module.render_summary(plan)
    for fragment in (
        LOT_TC,
        "etat scan",
        "prores_hq",
        ".mov",
        "1920x1080",
        "defaut",
        "30/1",  # cadence source effective (story 6.6), plus fps_target (15/1)
        "Mires",
        START_TC,
        "Bornes",
        str(plan.output_path),
        "Poids attendu",
        "sRGB",
    ):
        assert fragment in resume
    assert resume.isascii()


def test_without_yes_and_without_a_terminal_nothing_is_encoded(tmp_path, capsys):
    """AC 14: `--yes` saute la confirmation, comme `extract`.

    Sans terminal interactif et sans drapeau, la commande ne lit **jamais**
    `stdin`: une commande en CI ne doit pas se bloquer sur une entree qui ne
    viendra pas.
    """
    project_dir, _ = scanned_project(tmp_path)
    code = cli.main(["encode", "--project", str(project_dir), "--lot", LOT])
    assert code == 3
    # Aucun fichier ni dossier derriere: `outputs/` n'est cree qu'apres l'accord.
    assert not project_layout.outputs_dir(project_dir).exists()
    sortie = capsys.readouterr().out
    assert "consentement absent" in sortie
    assert "Recapitulatif de l'encodage" in sortie


# --------------------------------------------------------------------------
# AC 16 -- colorimetrie declaree
# --------------------------------------------------------------------------


def test_the_rec709_bt709_correspondence_lives_in_a_single_place():
    """AC 16: deux orthographes pour une meme chose."""
    assert cli.MVP_TARGET_COLORSPACE == "rec709"
    assert (
        encode_module.profile_colorspace_for_project(cli.MVP_TARGET_COLORSPACE)
        == codec_profiles.PROFILES["prores_hq"].colorspace
        == "bt709"
    )
    assert encode_module.profile_colorspace_for_project("inconnu") is None
    assert "sRGB" in encode_module.SRGB_APPROXIMATION_NOTE


# --------------------------------------------------------------------------
# AC 17 -- vocabulaire ferme et codes de sortie
# --------------------------------------------------------------------------


def test_the_finding_vocabulary_is_closed_and_validated():
    assert len(set(encode_module.ENCODE_CODES)) == len(encode_module.ENCODE_CODES)
    with pytest.raises(ValueError):
        encode_module.validate_encode_code("CONSTAT_INVENTE")
    for code in encode_module.ENCODE_CODES:
        assert encode_module.validate_encode_code(code) == code
        assert code.isascii() and code == code.upper()


def test_codes_naming_an_already_named_fact_take_the_producer_spelling():
    """AC 17: l'orthographe du producteur, au caractere pres."""
    from mixed_media_utility.io import extraction_manifest, scan_manifest

    assert encode_module.ENCODE_LOT_ABSENT == extraction_manifest.VERIFY_LOT_ABSENT
    assert (
        encode_module.ENCODE_OUTPUT_DIR_NOT_DECLARED
        == extraction_manifest.VERIFY_FRAMES_DIR_NOT_DECLARED
    )
    assert encode_module.ENCODE_LOT_INCOMPLETE == scan_manifest.SCAN_LOT_INCOMPLETE
    assert (
        encode_module.ENCODE_EXPECTED_COUNT_INDETERMINABLE
        == scan_manifest.SCAN_EXPECTED_FRAME_COUNT_INDETERMINABLE
    )
    assert encode_module.ENCODE_HETEROGENEOUS_SHAPES in sof.SCAN_OUTPUT_WARNING_CODES


def test_a_refusal_upstream_exits_one_and_writes_nothing(tmp_path, capsys):
    project_dir, manifest = scanned_project(tmp_path, absent_pages=(0,))
    code = run_cli(project_dir)
    assert code == 1
    assert encode_module.ENCODE_LOT_INCOMPLETE in capsys.readouterr().err
    assert not project_layout.outputs_dir(project_dir).exists()


def test_cli_refuses_and_encodes_the_scan_only_lot_via_cadence_source(tmp_path, capsys):
    """Story 6.6, AC 1bis, de bout en bout par la CLI reelle -- **regime pre-2.1**.

    Depuis la story 2.7 un lot ne d'un scan de planches 2.1 porte sa cadence
    source sans aide (voir le test de parcours e2e dedie): `strip_timecode_base_fps`
    simule ici le regime **pre-2.1** que l'AC 5 exige de couvrir, seul geste
    possible depuis que le vrai producteur ne sait plus emettre un tel payload.
    """
    project_dir, manifest = scanned_project(tmp_path, with_extraction=False)
    strip_timecode_base_fps(project_dir, manifest)
    assert "timecode_base_fps" not in lot_of(manifest)

    code = run_cli(project_dir)
    assert code == 1
    assert encode_module.ENCODE_SOURCE_RATE_MISSING in capsys.readouterr().err
    assert not project_layout.outputs_dir(project_dir).exists()

    assert run_cli(project_dir, "--cadence-source", "25/1") == 0
    masters = list(project_layout.outputs_dir(project_dir).iterdir())
    assert len(masters) == 1
    assert probe_stream(masters[0])["r_frame_rate"] == "25/1"


def test_cli_cadence_source_option_wins_over_the_lot_end_to_end(tmp_path, capsys):
    """Story 2.7 (`EPIC7-ARB-56`), de bout en bout par la CLI reelle.

    **Renverse** `ENCODE_SOURCE_RATE_REDUNDANT` (refuse jusqu'a la story 6.6):
    l'option **prime** desormais sur la cadence source deja portee par le lot,
    avec un avertissement structure au recapitulatif qui nomme les deux
    valeurs -- mesure sur la sortie **et** sur le master reellement ecrit, pas
    seulement sur le code de retour.
    """
    project_dir, manifest = scanned_project(tmp_path)
    valeur_du_lot = lot_of(manifest).get("timecode_base_fps")
    assert valeur_du_lot
    valeur_de_loption = "60/1"
    assert valeur_de_loption != valeur_du_lot  # regle des fabriques: distinguables

    code = run_cli(project_dir, "--cadence-source", valeur_de_loption)

    assert code == 0
    sortie = capsys.readouterr().out
    assert valeur_du_lot in sortie
    assert valeur_de_loption in sortie
    assert encode_module.ENCODE_SOURCE_RATE_REDUNDANT not in sortie
    masters = list(project_layout.outputs_dir(project_dir).iterdir())
    assert len(masters) == 1
    assert probe_stream(masters[0])["r_frame_rate"] == valeur_de_loption


def test_cadence_source_argparse_type_accepts_decimal_and_fraction():
    assert cli._parse_cadence_source("12.5") == "12.5"
    assert cli._parse_cadence_source("25/3") == "25/3"
    # Story 6.6, trouve par la campagne mutmut de la revue en trois couches
    # (Blind Hunter): la frontiere `parsed <= 0` n'etait exercee que du cote
    # refuse -- un mutant qui la deplace a `parsed <= 1` survivait, faute
    # d'un test qui verifie que la valeur limite legitime `1` (1 im/s, cadence
    # stop-motion reelle du depot) est bien acceptee.
    assert cli._parse_cadence_source("1") == "1"


def test_cadence_source_argparse_type_refuses_garbage():
    with pytest.raises(argparse.ArgumentTypeError):
        cli._parse_cadence_source("pas une cadence")
    with pytest.raises(argparse.ArgumentTypeError):
        cli._parse_cadence_source("25/0")


def test_cadence_source_argparse_type_refuses_non_finite_and_non_positive():
    """Story 6.6, finding 5 de la revue en trois couches: `float`/`Fraction`
    acceptent syntaxiquement `nan`/`inf`/negatif, ce que le refuse plus loin
    `exact_frame_rate` de toute facon -- mais autant le refuser ici, a
    l'endroit precis de l'erreur, avec un message specifique a
    `--cadence-source`.
    """
    for garbage in ("nan", "inf", "-inf", "-25/3", "0", "-5"):
        with pytest.raises(argparse.ArgumentTypeError):
            cli._parse_cadence_source(garbage)


# --------------------------------------------------------------------------
# AC 18 -- frontieres tenues, verrouillees par test
# --------------------------------------------------------------------------


def _code_string_literals(path: Path) -> set[str]:
    """Litteraux de chaine du **code**, docstrings exclues.

    Les commentaires n'entrent pas dans l'AST; les docstrings, si. La frontiere
    negative ne porte que sur ce que le module **fait**, pas sur ce qu'il dit --
    ce module cite ffmpeg vingt fois pour expliquer pourquoi il ne l'appelle
    jamais.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = {
        id(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
    }
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    }


def test_the_decision_module_builds_no_command_and_spawns_no_process():
    """AC 18: un `subprocess` ou un binaire d'encodage litteral signerait le
    debordement sur la story 6.0."""
    source = ENCODE_MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "subprocess" not in imported
    literals = _code_string_literals(ENCODE_MODULE_PATH)
    assert not [value for value in literals if "ffmpeg" in value]

    # `build_encode_command` est **nommee** dans la docstring, pour dire qu'elle
    # n'est jamais appelee: le grep doit donc porter sur les appels, pas sur le
    # texte. Le point d'entree consomme est `run_encode`, et lui seul.
    appels = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            cible = node.func
            if isinstance(cible, ast.Attribute):
                appels.add(cible.attr)
            elif isinstance(cible, ast.Name):
                appels.add(cible.id)
    assert "build_encode_command" not in appels
    assert "run" not in appels and "Popen" not in appels
    assert "run_encode" in appels


def test_the_decision_module_still_never_writes_the_manifest(tmp_path):
    """AC 18, **ouverte par la story 6.5 et reduite a ce qui reste vrai**.

    La version precedente de ce test verrouillait octet a octet que la commande
    `encode` n'ecrit pas le manifest, avec sa propre condition de peremption
    ecrite dans sa docstring: « le jour ou 6.5 l'ouvre, ce test tombe, et c'est
    ce qu'on lui demande ». Ce jour est arrive -- la story 6.5 branche
    `io.encode_manifest.persist_encode` dans `cli.encode_command`, apres le
    retour d'`execute_plan`.

    Ce qui reste vrai, et que ce test tient desormais, c'est la frontiere qui
    comptait reellement: **le module de decision** (`encode.py`) n'ecrit
    toujours rien. `execute_plan` seul laisse le `project.json` strictement
    intact, et aucune fonction de persistance n'y est nommee. C'est ce qui
    empeche la fabrique de dependre du manifest -- l'inverse aurait rendu
    l'encodage impossible a tester sans document.
    """
    project_dir, manifest = scanned_project(tmp_path)
    manifest_path = project_dir / MANIFEST_FILENAME
    avant = manifest_path.read_bytes()

    plan = encode_module.plan_encode(project_dir, manifest, lot_id=LOT)
    swept = encode_module.prepare_output_directory(plan)
    result = encode_module.execute_plan(plan, swept=swept)
    assert Path(result.outcome.output_path).is_file()
    assert manifest_path.read_bytes() == avant

    source = ENCODE_MODULE_PATH.read_text(encoding="utf-8")
    for interdit in (
        "persist_scan",
        "persist_pdf_generation",
        "persist_encode",
        "_atomic_write",
    ):
        assert interdit not in source


def test_the_command_now_writes_the_manifest(tmp_path):
    """Le pendant du precedent: la **commande**, elle, ecrit desormais (6.5).

    Deux tests et non un seul, parce que ce sont deux faits opposes et qu'un
    seul test qui les melerait ne dirait plus lequel a change.
    """
    project_dir, _ = scanned_project(tmp_path)
    manifest_path = project_dir / MANIFEST_FILENAME
    avant = manifest_path.read_bytes()
    assert run_cli(project_dir) == 0
    assert manifest_path.read_bytes() != avant
    apres = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert lot_of(apres)["state"] == "encode"


def _imported_names(path: Path) -> set[str]:
    """Noms **importes** par un module, alias des `from ... import` compris."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            prefix = node.module or ""
            for alias in node.names:
                names.add(f"{prefix}.{alias.name}" if prefix else alias.name)
                names.add(alias.name)
    return names


def test_the_decision_module_imports_no_manifest_writer_and_no_scan_module():
    """AC 18: la liste des modules interdits est explicite.

    Un import suffirait a la trahir, et le test le dit en toutes lettres:
    `io.reconstruction` (section unique par document, bloquant B1),
    `io.scan_manifest`, `io.pdf_manifest` et `scan_crop` n'ont rien a faire ici.
    `scan_output_frames` est **lu** pour sa seule recette de conformite de nom,
    et `io.extraction_manifest` pour son seul vocabulaire ferme de constats.
    """
    importes = _imported_names(ENCODE_MODULE_PATH)
    for interdit in ("reconstruction", "scan_manifest", "pdf_manifest", "scan_crop"):
        assert interdit not in importes, interdit
    assert "scan_output_frames" in importes
    assert "extraction_manifest" in importes


# --------------------------------------------------------------------------
# Le produit fini -- la lecon de la story 6.0
# --------------------------------------------------------------------------


def test_the_master_actually_produced_carries_what_the_command_declared(tmp_path):
    """Aucun test de 6.0 ne regardait le produit fini. Celui-ci le regarde.

    Cardinal, geometrie, cadence, format de pixel, colorimetrie, timecode
    converti et tags de conteneur sont relus **dans le fichier**, pas dans la
    commande qui pretend les avoir poses.
    """
    project_dir, manifest = timecode_project(tmp_path)
    plan = encode_module.plan_encode(project_dir, manifest, lot_id=LOT_TC)
    swept = encode_module.prepare_output_directory(plan)
    result = encode_module.execute_plan(plan, swept=swept)

    master = Path(result.outcome.output_path)
    assert master.is_file() and master.name == f"{LOT_TC}_mmu_prores_hq.mov"
    stream = probe_stream(master)
    # Story 6.6: le master restitue la cadence source (30/1) en tenant chaque
    # frame retenue -- son cardinal (`nb_frames`) est desormais le cardinal
    # muxe, pas le cardinal **distinct** retenu par la selection
    # (`plan.frame_count`, inchange, toujours egal a `expected_frame_count`).
    assert int(stream["nb_frames"]) == len(plan.muxed_frame_paths) == SOURCE_FRAME_COUNT_TC
    assert plan.frame_count == lot_of(manifest, LOT_TC)["expected_frame_count"]
    assert (stream["width"], stream["height"]) == (1920, 1080)
    assert stream["r_frame_rate"] == "30/1"
    assert stream["pix_fmt"] == "yuv422p10le"
    assert stream["color_space"] == "bt709"

    probe = video_metadata.probe_media(str(master))
    # Verbatim: le timecode du master est **l'etiquette** de l'image source,
    # relue dans le fichier fini et non dans la decision qui pretend l'avoir posee.
    assert video_metadata._find_timecode(probe) == START_TC
    tags = (probe.get("format") or {}).get("tags") or {}
    assert tags.get("codec_target_profile") == "prores_hq"
    assert tags.get("rush_id") == RUSH
    assert "lot_id" not in tags
    assert all(entry["ok"] for entry in result.verification.values())
    # `all(...)` sur un rapport ampute est vrai par vacuite: le champ est nomme
    # explicitement, sinon retirer le timecode de la demande rendait ce test
    # vert (survivant `H02`).
    assert result.verification["timecode"]["actual"] == START_TC
    # Aucun residu: ni fichier d'attente, ni liste `concat`, ni temporaire.
    assert [p.name for p in master.parent.iterdir()] == [master.name]


def test_the_native_resolution_produces_a_second_distinct_master(tmp_path):
    """AC 8 / AC 12: la taille native reste accessible, sous un autre nom."""
    project_dir, manifest = scanned_project(tmp_path)
    assert run_cli(project_dir) == 0
    assert run_cli(project_dir, "--resolution", "native") == 0
    masters = sorted(p.name for p in project_layout.outputs_dir(project_dir).iterdir())
    assert masters == [
        f"{LOT}_mmu_prores_hq.mov",
        f"{LOT}_mmu_prores_hq_551x310.mov",
    ]
    natif = probe_stream(project_layout.outputs_dir(project_dir) / masters[1])
    assert (natif["width"], natif["height"]) == (551, 310)


def test_rerunning_without_overwrite_refuses_and_keeps_the_master_byte_for_byte(tmp_path):
    """AC 13: le master precedent n'est jamais detruit."""
    project_dir, _ = scanned_project(tmp_path)
    assert run_cli(project_dir) == 0
    master = project_layout.outputs_dir(project_dir) / f"{LOT}_mmu_prores_hq.mov"
    avant = master.read_bytes()
    assert run_cli(project_dir) == 1
    assert master.read_bytes() == avant
    assert run_cli(project_dir, "--overwrite") == 0
    assert master.is_file()


# --------------------------------------------------------------------------
# AC 13 -- la cible est reservee atomiquement, et la bascule se fait dessous
# --------------------------------------------------------------------------


def _spawn_encode(project_dir: Path, *extra: str, lot: str = LOT) -> subprocess.Popen:
    """Lancer `encode` dans un **vrai** processus, dans sa propre session.

    Deux exigences, et aucune n'est cosmetique. Un vrai processus: la course que
    ces tests reproduisent est entre deux `encode` concurrents, et deux appels
    sequentiels dans le meme interpreteur sont precisement le seul ordre ou la
    garde amont suffit -- c'est ce que faisait le test de la revision precedente.
    Sa propre session (`start_new_session`): le groupe de processus devient
    observable, donc on peut affirmer qu'apres un signal il ne reste **rien**,
    ffmpeg compris, sans jamais regarder les processus des autres tests.
    """
    return subprocess.Popen(
        [
            sys.executable, "-m", "mixed_media_utility.cli", "encode",
            "--project", str(project_dir), "--lot", lot, "--yes", *extra,
        ],
        cwd=str(REPO_ROOT),
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )


def _wait_for_encoding_to_start(project_dir: Path, timeout: float = 60.0) -> None:
    """Attendre qu'un encodage soit reellement **en cours**.

    Le repere est l'apparition d'un fichier dans `outputs/`: reservation, liste
    `concat` ou fichier d'attente, selon le moment. Sans ce point de
    rendez-vous, deux processus lances l'un apres l'autre peuvent ne pas se
    recouvrir du tout, et le test passerait alors sur du code fautif.
    """
    sortie = project_layout.outputs_dir(project_dir)
    limite = time.monotonic() + timeout
    while time.monotonic() < limite:
        if sortie.is_dir() and any(sortie.iterdir()):
            return
        time.sleep(0.02)
    raise AssertionError(f"aucun encodage n'a demarre dans {sortie} en {timeout} s")


def test_two_concurrent_encodes_leave_one_master_and_one_named_refusal(tmp_path):
    """AC 13, **bloquant**: la reservation atomique de 6.0 etait contournee.

    6.1 encodait vers un chemin d'attente **prive** puis basculait par un
    `os.replace` nu: la reservation `O_CREAT | O_EXCL` de la story 6.0 ne portait
    donc que sur un temporaire que personne ne disputait, et la cible n'etait
    plus protegee par rien. Mesure du 2026-08-10 sur le code fautif: deux
    `encode` simultanes rendaient `rc=0` **tous les deux** et "Master ecrit"
    tous les deux, pour un seul fichier -- l'un des deux masters etait detruit
    sans un mot, et chacun affichait une description d'encodage dont l'une
    decrivait un fichier qui n'existait plus.

    Deux **vrais** processus, avec un point de rendez-vous qui garantit le
    recouvrement -- et une geometrie de sortie assez lourde pour que le premier
    encodage dure encore quand le second decide. Sans ces deux precautions le
    test passerait aussi sur le code fautif, ce qui a ete verifie: en `hd1080`
    sur huit frames, le premier processus a fini avant que le second n'ait
    charge ses modules, et la garde amont suffisait.
    """
    project_dir, manifest = scanned_project(tmp_path)
    master_name = f"{LOT}_mmu_prores_hq_uhd2160.mov"
    premier = _spawn_encode(project_dir, "--resolution", "uhd2160")
    try:
        _wait_for_encoding_to_start(project_dir)
        second = _spawn_encode(project_dir, "--resolution", "uhd2160")
        sortie_seconde = second.communicate()[0]
        code_second = second.returncode
    finally:
        sortie_premiere = premier.communicate()[0]
    assert premier.returncode == 0, sortie_premiere
    assert code_second == 1, sortie_seconde
    assert encode_module.ENCODE_MASTER_ALREADY_PRESENT in sortie_seconde
    assert "Master ecrit" not in sortie_seconde

    masters = sorted(project_layout.outputs_dir(project_dir).iterdir())
    assert [p.name for p in masters] == [master_name]
    # Le master survivant est complet: ce n'est ni la reservation vide, ni un
    # fichier tronque par la bascule de l'autre. Story 6.6: le cardinal muxe
    # restitue l'integralite de la source (k=6 exact, sans reste) -- ce n'est
    # plus `expected_frame_count` (cardinal **distinct** retenu, 8 ici).
    stream = probe_stream(masters[0])
    assert int(stream["nb_frames"]) == SOURCE_FRAME_COUNT


def test_a_master_appearing_during_the_encode_is_never_overwritten(tmp_path):
    """AC 13: la fenetre entre le plan et la bascule valait toute la duree.

    Mesure du 2026-08-10 sur le code fautif: un master pose apres le plan etait
    **detruit sans `--overwrite`**, et la commande declarait un succes. La
    reservation ferme la fenetre en amont de l'encodage; ce test la pose juste
    avant `execute_plan`, c'est-a-dire au pire moment possible.
    """
    project_dir, _ = scanned_project(tmp_path)
    plan = encode_module.plan_encode(project_dir, load_manifest_dict(project_dir), lot_id=LOT)
    encode_module.prepare_output_directory(plan)
    plan.output_path.write_bytes(b"master d'un autre encodage")
    avant = plan.output_path.read_bytes()

    with pytest.raises(encode_module.EncodeDecisionError) as refus:
        encode_module.execute_plan(plan)
    assert refus.value.code == encode_module.ENCODE_MASTER_ALREADY_PRESENT
    assert plan.output_path.read_bytes() == avant
    # Et rien d'autre n'a ete laisse: la reservation n'a pas eu lieu, donc rien
    # a retirer, et aucun encodage n'a commence.
    assert [p.name for p in plan.output_path.parent.iterdir()] == [plan.output_path.name]


def test_a_failed_encode_removes_its_own_reservation(tmp_path):
    """La reservation ne doit jamais survivre a l'echec qu'elle encadre.

    Sinon un fichier de 0 octet resterait au nom du master et bloquerait toute
    relance sous `MASTER_DEJA_PRESENT` -- le contraire du service rendu.
    """
    project_dir, _ = scanned_project(tmp_path)
    plan = encode_module.plan_encode(project_dir, load_manifest_dict(project_dir), lot_id=LOT)
    encode_module.prepare_output_directory(plan)
    # Une frame retiree apres le plan: la fabrique 6.0 refuse, apres reservation.
    plan.frame_paths[1].unlink()
    with pytest.raises(codec_profiles.EncodeError):
        encode_module.execute_plan(plan)
    assert not plan.output_path.exists()
    # Et la relance suivante n'est pas bloquee par un fantome: elle refuse pour
    # la vraie raison (la frame manquante), pas pour un master qui n'existe pas.
    with pytest.raises(encode_module.EncodeDecisionError) as relance:
        encode_module.plan_encode(project_dir, load_manifest_dict(project_dir), lot_id=LOT)
    assert relance.value.code == encode_module.ENCODE_LOT_INCOMPLETE


def test_the_reservation_is_not_taken_when_overwrite_is_asked(tmp_path):
    """`--overwrite` accepte d'ecraser: on ne pose pas `O_EXCL` par-dessus.

    Contrat repris de la story 6.0, qui le declare pour son propre appel: deux
    appelants en ecrasement sur la meme cible restent une course gagnee par le
    dernier, et c'est ce que le drapeau demande.
    """
    project_dir, _ = scanned_project(tmp_path)
    assert run_cli(project_dir) == 0
    master = project_layout.outputs_dir(project_dir) / f"{LOT}_mmu_prores_hq.mov"
    plan = encode_module.plan_encode(
        project_dir, load_manifest_dict(project_dir), lot_id=LOT, overwrite=True
    )
    assert encode_module.reserve_master_path(plan) is False
    assert master.is_file() and master.stat().st_size > 0
    assert run_cli(project_dir, "--overwrite") == 0


def test_sigterm_takes_the_encoder_down_with_the_command(tmp_path):
    """Un `SIGTERM` laissait **ffmpeg orphelin** aller jusqu'au bout.

    Mesure du 2026-08-10: `kill -TERM` sur la commande, `rc=143`, et l'encodeur
    continuait d'ecrire pendant quatre secondes -- 36 Mo poses apres la mort du
    CLI -- alors que le message annoncait "encodage arrete". La cause vit dans la
    fabrique (`subprocess.run` sans groupe de processus), la promesse dans cette
    commande: le signal y devient une exception, et `subprocess.run` tue son
    enfant avant de la propager.

    Le groupe de processus est l'observable: apres l'arret, il ne doit rester
    **personne** dedans. Il isole aussi la mesure des processus des autres tests.
    """
    project_dir, _ = scanned_project(tmp_path)
    process = _spawn_encode(project_dir, "--resolution", "uhd2160")
    try:
        _wait_for_encoding_to_start(project_dir)
        process.terminate()
        sortie = process.communicate(timeout=60)[0]
    finally:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(process.pid, signal.SIGKILL)
    assert process.returncode == 143
    assert encode_module.ENCODE_TERMINATION_REQUESTED in sortie

    limite = time.monotonic() + 10.0
    while time.monotonic() < limite:
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.05)
    else:  # pragma: no cover - le defaut mesure, s'il revenait
        raise AssertionError("un processus survit au SIGTERM: l'encodeur est orphelin")
    assert not (project_layout.outputs_dir(project_dir) / f"{LOT}_mmu_prores_hq_uhd2160.mov").exists()


def test_an_interruption_carries_a_code_of_the_closed_vocabulary(tmp_path, capsys, monkeypatch):
    """AC 17: `INTERRUPTION_CLAVIER` etait declare et n'etait leve nulle part.

    Du vocabulaire mort: les deux gestionnaires imprimaient de la prose libre et
    rendaient `130` sans code, alors que l'AC exige que **tout** constat porte un
    code du tuple ferme. Les deux interruptions sont distinguees, et par leur
    code et par leur code de sortie (`130` clavier, `143` signal).
    """
    project_dir, _ = scanned_project(tmp_path)

    def _interrompt(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(encode_module, "execute_plan", _interrompt)
    assert run_cli(project_dir) == 130
    assert encode_module.ENCODE_KEYBOARD_INTERRUPT in capsys.readouterr().out

    def _termine(*args, **kwargs):
        raise cli._EncodeTerminated("signal 15")

    monkeypatch.setattr(encode_module, "execute_plan", _termine)
    assert run_cli(project_dir) == 143
    assert encode_module.ENCODE_TERMINATION_REQUESTED in capsys.readouterr().out

    # Le second gestionnaire, celui qui couvre la **decision** -- avant que le
    # moindre octet ne soit ecrit -- porte le meme code: sans ce cas, la moitie
    # du chemin d'interruption restait de la prose libre.
    def _interrompt_le_plan(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(encode_module, "plan_encode", _interrompt_le_plan)
    assert run_cli(project_dir) == 130
    amont = capsys.readouterr().out
    assert encode_module.ENCODE_KEYBOARD_INTERRUPT in amont
    assert "rien n'a ete encode" in amont


def test_the_previous_sigterm_handler_is_restored_after_the_command(tmp_path):
    """Une commande qui rend la main ne laisse pas un signal detourne.

    Le gestionnaire de `SIGTERM` n'est installe que pour la duree de l'encodage.
    S'il survivait a la commande, tout `SIGTERM` recu ensuite par le processus
    -- une application qui appelle `cli.main` en bibliotheque, un test suivant --
    leverait une exception au lieu de terminer le programme. La campagne de
    mutation a mesure qu'aucun test ne le voyait.
    """
    project_dir, _ = scanned_project(tmp_path)

    def _temoin(signum, frame):  # pragma: no cover - jamais appele
        raise AssertionError("gestionnaire temoin appele")

    precedent = signal.signal(signal.SIGTERM, _temoin)
    try:
        assert run_cli(project_dir) == 0
        assert signal.getsignal(signal.SIGTERM) is _temoin
        # Et il est restaure aussi quand la commande echoue: le second appel
        # refuse (master deja present) apres etre passe par le meme contexte.
        assert run_cli(project_dir) == 1
        assert signal.getsignal(signal.SIGTERM) is _temoin
    finally:
        signal.signal(signal.SIGTERM, precedent)


def test_a_destination_occupied_by_a_directory_is_refused_before_encoding(tmp_path):
    """Une cible qui est un **repertoire** n'etait vue qu'apres l'encodage.

    Mesure du 2026-08-10: avec `--overwrite`, tout l'encodage etait paye, puis la
    bascule levait `IsADirectoryError`, rendu par la CLI en "verifier l'espace
    disponible et les droits d'ecriture" -- un diagnostic qui accuse le disque
    pour une cause qui n'a rien a voir -- et un fichier d'attente de la taille
    d'un master restait sur le disque.
    """
    project_dir, manifest = scanned_project(tmp_path)
    sortie = project_layout.outputs_dir(project_dir)
    sortie.mkdir(parents=True, exist_ok=True)
    (sortie / f"{LOT}_mmu_prores_hq.mov").mkdir()

    for extra in ((), ("--overwrite",)):
        code = run_cli(project_dir, *extra)
        assert code == 1
        # Rien n'a ete encode: le dossier ne porte que le repertoire pris pour
        # cible, ni fichier d'attente ni liste `concat`.
        assert [p.name for p in sortie.iterdir()] == [f"{LOT}_mmu_prores_hq.mov"]

    with pytest.raises(encode_module.EncodeDecisionError) as refus:
        encode_module.plan_encode(project_dir, manifest, lot_id=LOT, overwrite=True)
    assert refus.value.code == encode_module.ENCODE_MASTER_IS_A_DIRECTORY


# --------------------------------------------------------------------------
# AC 5 / AC 6 -- l'ordre, et l'identite de la selection
# --------------------------------------------------------------------------


def test_the_sort_key_is_the_whole_timecode_not_only_its_frame_field(tmp_path):
    """Le **contenu** de la cle de tri n'etait pinne par aucun test.

    Campagne de mutation: permuter la cle en `(ff, ss, mm, hh)` laissait les 53
    tests verts, parce qu'aucun lot de fixture ne franchissait la seconde --
    `hh`, `mm` et `ss` valaient zero partout. L'absence de tri etait testee, son
    contenu non. Le lot de base franchit desormais la seconde, et ce test le
    verifie explicitement plutot que de s'y fier.
    """
    project_dir, manifest = scanned_project(tmp_path)
    lot_dir = project_dir / lot_of(manifest)["output_frames_dir"]
    noms = sorted(p.name for p in lot_dir.iterdir())
    plan = encode_module.plan_sequence(list(reversed(noms)), rush_id=RUSH, fps_target=FPS)

    champs = [tuple(int(part) for part in tc.split(":")) for tc in plan.timecodes]
    assert len({champ[2] for champ in champs}) > 1, (
        "la fabrique doit franchir la seconde, sinon toute permutation de la cle "
        "rend le meme ordre"
    )
    # Une cle permutee rendrait un **autre** ordre: c'est ce qui rend le test
    # capable de voir la difference.
    permute = [tc for _, tc in sorted((tuple(reversed(c)), tc) for c, tc in zip(champs, plan.timecodes))]
    assert permute != list(plan.timecodes)
    assert list(plan.timecodes) == sorted(plan.timecodes)


def test_chronology_compares_each_value_to_the_previous_one_everywhere(tmp_path):
    """La garde ne regardait de fait que le premier couple.

    Deux mutants survivants de la campagne: l'un limitait la comparaison au
    premier couple, l'autre comparait chaque element au **premier** au lieu du
    precedent. Aucun test ne les distinguait, le seul cas exerce ne passant que
    **deux** valeurs. C'est le point 2 de la regle des fabriques: au moins un
    test place la cible ailleurs qu'en premiere position.
    """
    # Decroissance sur le **dernier** couple: une garde limitee au premier la rate.
    with pytest.raises(encode_module.EncodeDecisionError) as tardive:
        encode_module.check_chronology(
            ["00:00:00:00", "00:00:01:00", "00:00:00:12"], origin="les bornes"
        )
    assert tardive.value.code == encode_module.ENCODE_TIMECODE_DECREASING

    # Decroissance invisible a qui compare au premier element: 00:00:01:00 est
    # bien superieur a 00:00:00:00, et pourtant la suite recule.
    with pytest.raises(encode_module.EncodeDecisionError):
        encode_module.check_chronology(
            ["00:00:00:00", "00:00:02:00", "00:00:01:00"], origin="les bornes"
        )
    # Contre-epreuve: une suite croissante de plus de deux valeurs passe.
    encode_module.check_chronology(
        ["00:00:00:00", "00:00:01:00", "00:00:02:00"], origin="les bornes"
    )


def test_a_frame_renamed_to_a_foreign_timecode_is_caught_by_the_bounds(tmp_path):
    """Le verdict ne confrontait que des **cardinaux**.

    Mesure du 2026-08-10 sur le lot reel: un seul fichier renomme vers un
    timecode etranger, et la commande annoncait "5 conformes pour 5 attendues"
    puis encodait. La conformite passe en effet par `(rush_id, fps_target)` et
    jamais par le lot: deux lots du meme rush a la meme cadence produisent des
    noms **identiques**. Le manifest porte pourtant les bornes, et elles sont
    gratuites a confronter.
    """
    project_dir, manifest = scanned_project(tmp_path)
    lot = lot_of(manifest)
    lot_dir = project_dir / lot["output_frames_dir"]
    derniere = sorted(lot_dir.iterdir())[-1]
    derniere.rename(lot_dir / f"scan_{RUSH}_5_00-00-09-00.tiff")

    with pytest.raises(encode_module.EncodeDecisionError) as refus:
        encode_module.plan_encode(project_dir, manifest, lot_id=LOT)
    assert refus.value.code == encode_module.ENCODE_BOUNDS_MISMATCH
    assert lot["last_frame_timecode"] in str(refus.value)
    assert "00:00:09:00" in str(refus.value)

    # **Les deux bornes**, et pas seulement celle de fin: la campagne de
    # mutation a mesure qu'une confrontation reduite au depart passait inapercue.
    autre_dir, autre_manifest = scanned_project(tmp_path, name="proj-depart")
    autre_lot = lot_of(autre_manifest)
    dossier = autre_dir / autre_lot["output_frames_dir"]
    premiere = sorted(dossier.iterdir())[0]
    assert premiere.name.endswith("00-00-00-00.tiff")
    premiere.rename(dossier / f"scan_{RUSH}_5_00-00-00-02.tiff")
    with pytest.raises(encode_module.EncodeDecisionError) as depart:
        encode_module.plan_encode(autre_dir, autre_manifest, lot_id=LOT)
    assert depart.value.code == encode_module.ENCODE_BOUNDS_MISMATCH
    assert "first_frame_timecode" in str(depart.value)


def test_a_frame_renamed_inside_the_bounds_is_caught_by_the_digest(tmp_path):
    """Les bornes ne voient pas un echange **au milieu**: l'empreinte, si.

    `lots[].frame_timecodes_digest` "change si un timecode change, si l'ordre
    change" (story 3.4), et sa recette canonique est importee, jamais retapee.
    Recalcul verifie sur le materiau reel du depot: les deux lots rescannes
    rendent exactement l'empreinte persistee.
    """
    project_dir, manifest = scanned_project(tmp_path)
    lot = lot_of(manifest)
    assert lot["frame_timecodes_digest"].startswith("sha256-v1:")
    lot_dir = project_dir / lot["output_frames_dir"]
    milieu = sorted(lot_dir.iterdir())[2]
    assert milieu.name.endswith("00-00-00-12.tiff")
    milieu.rename(lot_dir / f"scan_{RUSH}_5_00-00-00-14.tiff")

    with pytest.raises(encode_module.EncodeDecisionError) as refus:
        encode_module.plan_encode(project_dir, manifest, lot_id=LOT)
    assert refus.value.code == encode_module.ENCODE_DIGEST_MISMATCH
    assert lot["frame_timecodes_digest"] in str(refus.value)


def test_the_identity_confrontation_passes_on_the_nominal_lot(tmp_path):
    """Contre-epreuve: sans elle, les deux tests precedents seraient vrais par
    construction -- un refus systematique les satisferait aussi."""
    project_dir, manifest = scanned_project(tmp_path)
    lot = lot_of(manifest)
    plan = encode_module.plan_encode(project_dir, manifest, lot_id=LOT)
    sequence = encode_module.plan_sequence(
        [p.name for p in plan.frame_paths], rush_id=RUSH, fps_target=FPS
    )
    encode_module.confront_selection_identity(lot, sequence)
    assert plan.verdict.complete
    # Un lot sans empreinte ni bornes traverse sans bruit: la confrontation est
    # une confrontation, pas une exigence de champ.
    encode_module.confront_selection_identity({"lot_id": "nu"}, sequence)


def test_a_zero_byte_frame_is_never_counted_as_a_frame(tmp_path):
    """Un fichier de 0 octet sous un nom conforme faisait "complet".

    Mesure du 2026-08-10: le verdict comptait 5 sur 5, declarait le lot complet,
    et c'est une garde **aval** qui rattrapait -- en nommant le fait
    `HETEROGENEOUS_FRAME_SHAPES` alors que son message disait "frame illisible".
    La story 5.6 range deja un fichier vide dans `nonconforming_files`, pour la
    meme raison: c'est la forme la plus courante d'artefact d'une passe
    interrompue.
    """
    project_dir, manifest = scanned_project(tmp_path)
    lot_dir = project_dir / lot_of(manifest)["output_frames_dir"]
    tronquee = sorted(lot_dir.iterdir())[2]
    tronquee.write_bytes(b"")

    with pytest.raises(encode_module.EncodeDecisionError) as refus:
        encode_module.plan_encode(project_dir, manifest, lot_id=LOT)
    assert refus.value.code == encode_module.ENCODE_LOT_INCOMPLETE

    plan = encode_module.plan_encode(
        project_dir, manifest, lot_id=LOT, accept_incomplete=True
    )
    assert tronquee.name not in [p.name for p in plan.frame_paths]
    assert plan.empty_files == (tronquee.name,)
    assert encode_module.ENCODE_EMPTY_FILES in plan.findings
    assert "0 octet" in encode_module.render_summary(plan)


# --------------------------------------------------------------------------
# AC 3 / AC 8 / AC 16 -- un code par fait, et les gardes de saisie
# --------------------------------------------------------------------------


def test_four_distinct_facts_no_longer_share_the_lot_state_code(tmp_path):
    """`ETAT_DE_LOT_INSUFFISANT` nommait quatre faits differents.

    C'est le defaut symetrique de celui que l'AC 3 corrige en separant l'etat du
    dossier: un operateur dont le lot est au bon etat lisait "etat de lot
    insuffisant" parce que `fps_target` n'etait pas numerique.
    """
    project_dir, manifest = scanned_project(tmp_path)

    sans_cadence = copy.deepcopy(manifest)
    lot_of(sans_cadence)["fps_target"] = "5/1"
    with pytest.raises(encode_module.EncodeDecisionError) as cadence:
        encode_module.plan_encode(project_dir, sans_cadence, lot_id=LOT)
    assert cadence.value.code == encode_module.ENCODE_FRAME_RATE_UNUSABLE

    cadence_nulle = copy.deepcopy(manifest)
    lot_of(cadence_nulle)["fps_target"] = 0
    with pytest.raises(encode_module.EncodeDecisionError) as nulle:
        encode_module.plan_encode(project_dir, cadence_nulle, lot_id=LOT)
    assert nulle.value.code == encode_module.ENCODE_FRAME_RATE_UNUSABLE

    sans_rush = copy.deepcopy(manifest)
    lot_of(sans_rush).pop("rush_id")
    with pytest.raises(encode_module.EncodeDecisionError) as rush:
        encode_module.plan_encode(project_dir, sans_rush, lot_id=LOT)
    assert rush.value.code == encode_module.ENCODE_RUSH_ID_ABSENT

    # Le champ de matrice sans valeur n'est pas atteignable depuis `plan_encode`
    # -- les deux champs `REQUIRED` y sont toujours calcules -- donc il est
    # exerce sur la fonction publique elle-meme, et le fait est dit ici.
    with pytest.raises(encode_module.EncodeDecisionError) as matrice:
        encode_module.build_container_tags(
            manifest, lot_of(manifest), profile_id="prores_hq", frame_rate="",
            frame_timecode=None,
        )
    assert matrice.value.code == encode_module.ENCODE_MATRIX_FIELD_MISSING
    assert len(
        {cadence.value.code, rush.value.code, matrice.value.code,
         encode_module.ENCODE_LOT_STATE_TOO_EARLY}
    ) == 4


def test_a_resolution_of_non_ascii_digits_is_refused_not_a_traceback(tmp_path):
    """`str.isdigit()` est vrai pour les exposants, que `int()` refuse.

    Mesure: `--resolution` avec un exposant deux rendait `ValueError: invalid
    literal for int()` et une trace complete, la ou `RESOLUTION_INCONNUE` existe
    exactement pour ce refus. `isdecimal` decrit le meme ensemble que `int()`.

    Les caracteres non ASCII sont ecrits en **echappements**, jamais en clair:
    le depot exige de l'ASCII dans le code et les fixtures (Piege 14), et un
    litteral pleine chasse est de toute facon illisible en revue.
    """
    exposant = "\u00b2"  # EXPOSANT DEUX
    assert exposant.isdigit() and not exposant.isdecimal()
    with pytest.raises(encode_module.EncodeDecisionError) as refus:
        encode_module.resolve_output_resolution(f"{exposant}x{exposant}")
    assert refus.value.code == encode_module.ENCODE_UNKNOWN_RESOLUTION

    project_dir, _ = scanned_project(tmp_path)
    assert run_cli(project_dir, "--resolution", f"{exposant}x{exposant}") == 1
    # Les chiffres non ASCII que `int()` accepte restent acceptes, et rendent la
    # meme geometrie: la garde et la conversion parlent enfin du meme ensemble.
    pleine_chasse = "\uff11\uff19\uff12\uff10x\uff11\uff10\uff18\uff10"
    assert "\uff11".isdecimal() and int("\uff11") == 1
    assert encode_module.resolve_output_resolution(pleine_chasse).size == (1920, 1080)


def test_a_custom_resolution_that_deforms_the_image_says_so(tmp_path):
    """AC 8: le sur-mesure ouvrait le ratio d'aspect que l'AC declarait ferme.

    Mesure: source 551x310 (1,777), `--resolution 1000x1000` -> master 1000x1000,
    `rc=0`, **aucun constat**, image deformee. Le silence est ce que le depot
    s'interdit partout ailleurs. La tolerance est mesuree, pas choisie: la
    geometrie rescannee reelle du depot (3307x1860) n'est pas exactement 16:9.
    """
    project_dir, manifest = scanned_project(tmp_path)
    carre = encode_module.plan_encode(
        project_dir, manifest, lot_id=LOT, resolution="1000x1000"
    )
    assert encode_module.ENCODE_ASPECT_RATIO_CHANGED in carre.findings

    defaut = encode_module.plan_encode(project_dir, manifest, lot_id=LOT)
    assert encode_module.ENCODE_ASPECT_RATIO_CHANGED not in defaut.findings
    # La geometrie reelle du depot passe, et c'est ce que la tolerance protege.
    assert encode_module._same_aspect_ratio((3307, 1860), (1920, 1080))
    assert not encode_module._same_aspect_ratio((3307, 1860), (1920, 1200))


def test_the_project_colorspace_is_confronted_to_the_profile(tmp_path):
    """AC 16: la table de correspondance n'avait **aucun lecteur de production**.

    `PROJECT_TO_PROFILE_COLORSPACE` et `profile_colorspace_for_project` etaient
    exportes, testes contre eux-memes, et appeles par aucun chemin: un projet
    declarant autre chose que `rec709` recevait un master tague `bt709` en
    silence. Le test qui les couvrait confrontait la table a elle-meme -- la
    forme exacte du test tautologique que le `CLAUDE.md` proscrit.
    """
    project_dir, manifest = scanned_project(tmp_path)
    # Les deux orthographes reelles du depot passent: `rec709` que pose
    # `init-project`, `bt709` que porte le payload de cette fabrique.
    assert manifest["color"]["target_colorspace"] == COLORSPACE == "bt709"
    nominal = encode_module.plan_encode(project_dir, manifest, lot_id=LOT)
    assert encode_module.ENCODE_PROJECT_COLORSPACE_DIVERGENT not in nominal.findings

    autre = copy.deepcopy(manifest)
    autre["color"]["target_colorspace"] = "srgb"
    divergent = encode_module.plan_encode(project_dir, autre, lot_id=LOT)
    assert encode_module.ENCODE_PROJECT_COLORSPACE_DIVERGENT in divergent.findings
    assert encode_module.ENCODE_PROJECT_COLORSPACE_DIVERGENT in encode_module.render_summary(divergent)
    # La table reste le seul juge, et elle est reellement consultee ici.
    assert encode_module.profile_colorspace_for_project("srgb") is None
    rec709 = copy.deepcopy(manifest)
    rec709["color"]["target_colorspace"] = cli.MVP_TARGET_COLORSPACE
    assert encode_module.ENCODE_PROJECT_COLORSPACE_DIVERGENT not in encode_module.plan_encode(
        project_dir, rec709, lot_id=LOT
    ).findings
