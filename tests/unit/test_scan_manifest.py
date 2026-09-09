"""Tests de la creation et de la mise a jour du manifest depuis le scan (story 5.7).

Trois exigences structurent ce fichier.

**Contre les vrais producteurs** (action item 3 de la retro Epic 4): les
payloads viennent de `io.payload.build_page_payload`, les plans de decoupe de
`scan_crop`, les rapports de sortie de `scan_output_frames.write_lot_output_frames`
-- qui ecrit de vrais TIFF sur disque --, les manifests riches de
`io.extraction_manifest.build_extraction_manifest`, et les identifiants de
`io.naming`. Aucun `SimpleNamespace`, aucun dict de manifest ecrit a la main la
ou un producteur existe: `io.scan_manifest` lit le rapport de 5.6 en typage
structurel, et c'est precisement le cas ou un renommage de champ passerait
inapercu sans test d'integration.

**Aucun test qui ne puisse pas echouer.** Chaque assertion tombe si le
comportement change. Les tests de non-perte (AC 4) comparent **champ par
champ** un manifest riche avant et apres, et non un simple `is not None`; les
tests d'idempotence comparent les **octets** du fichier, seule preuve que rien
n'a bouge.

**Le seul faux pas interdit est le faux succes** (risque R12): un lot partiel
est ecrit et declare partiel, jamais declare complet; une divergence
d'identifiant d'impression est un refus nomme, jamais une fusion.
"""

from __future__ import annotations

import ast
import copy
import dataclasses
import json
import re
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from jsonschema import Draft7Validator  # noqa: E402
from jsonschema.exceptions import ValidationError  # noqa: E402

from mixed_media_utility import (  # noqa: E402
    cli,
    color_pipeline,
    layout,
    page_roles,
    page_templates,
    qr_codes,
    scan_crop,
    scan_detection,
    scan_ingest,
    scan_output_frames as sof,
    scan_sorting,
)
from mixed_media_utility.frame_selection import select_source_frames  # noqa: E402
from mixed_media_utility.io import naming, payload as payload_io  # noqa: E402
from mixed_media_utility.io import scan_manifest as sm  # noqa: E402
from mixed_media_utility.io.extraction_manifest import (  # noqa: E402
    MANIFEST_FILENAME,
    ExtractionRecord,
    LegacyManifestError,
    ManifestWriteError,
    build_extraction_manifest,
)
from mixed_media_utility.io.manifest import (  # noqa: E402
    LOT_STATES,
    validate_manifest,
)
from mixed_media_utility.io.pdf_manifest import (  # noqa: E402
    PdfRecord,
    persist_pdf_generation,
)
from mixed_media_utility.io.project_layout import (  # noqa: E402
    EXTRACT_FRAMES_DIRNAME,
    LOGS_DIRNAME,
    OUTPUTS_DIRNAME,
    SCAN_FRAMES_DIRNAME,
    SCANS_DIRNAME,
    rush_dir_slug,
)
from mixed_media_utility.io.reconstruction import (  # noqa: E402
    RECONSTRUCTION_ORIGINS,
    ReconstructionError,
    reconstruct_project_manifest,
)

MODULE_PATH = REPO_ROOT / "src" / "mixed_media_utility" / "io" / "scan_manifest.py"
SCHEMA_PATH = REPO_ROOT / "src" / "mixed_media_utility" / "specs" / "project.schema.json"

#: **Le code d'un lot ecrit AVEC des mires, depuis la story 11.4c** (lot V2,
#: AC 9.1 et AC 9.3). Les quatre sites qui le portent scannent une pile dont
#: une planche a le QR efface: deux frames sur quatre sont des mires, la
#: persistance emet `FRAMES_SYNTHETIQUES_PRESENTES` et `LOT_INCOMPLET`, et
#: l'inventaire atteint desormais le code de sortie.
#:
#: **Il n'est pas colle au lot**: la troisieme passe de
#: `test_the_scan_command_is_idempotent_on_a_lot_carrying_mires` rescanne les
#: memes planches **reparees**, retrouve quatre vraies frames et revient a
#: `0` -- l'assertion y est laissee telle quelle, et c'est elle qui mesure que
#: la degradation suit l'etat du lot et non l'histoire du projet.
#:
#: Le docstring de ce test-la observait deja le defaut, verbatim: « en code `0`
#: et avec le mot « succes » ».
#:
#: Valeur ecrite en clair, jamais lue de `scan_write.CODE_SUCCES_PARTIEL`: lire
#: la constante que l'on mesure serait le test tautologique de la story 5.9.
LOT_AVEC_MIRES_MAIS_ECRIT = 4

#: DPI volontairement bas: les vraies frames sont ecrites sur disque a chaque
#: test, et un A4 a 300 ppp coute cent fois plus cher qu'a 100 sans rien
#: prouver de plus -- la geometrie est celle du plan reel dans les deux cas.
DPI = 100
PROJECT = "proj-001"
RUSH = "rush-001"
FPS = 5.0
TPL = "tpl-a4-portrait-2f-v1"
PATCH_PRESET = "patch-values-2"
COLORSPACE = "bt709"
LOT = naming.build_lot_id(RUSH, FPS)


# --------------------------------------------------------------------------
# Fabriques: tout derive des vrais producteurs
# --------------------------------------------------------------------------


#: Libelle de chaine par defaut des pages de calibration fabriquees ici. Il est
#: nomme plutot que litteral depuis la story 5.24: les tests qui ont besoin de
#: **deux** feuilles distinguables passent le leur, et ce defaut reste celui de
#: tous les appelants anterieurs.
SCAN_CHAIN_LABEL_PAR_DEFAUT = "hp envy 4520 tiff 600 dpi auto corr off"


def make_payload(
    *,
    page_index: int,
    page_count: int = 2,
    first_slot: int | None = None,
    slot_count: int = 2,
    template_id: str = TPL,
    patch_preset_id: str = PATCH_PRESET,
    gamut_map_id: str | None = None,
    project_id: str = PROJECT,
    rush_id: str = RUSH,
    lot_id: str | None = None,
    fps_target: float = FPS,
    page_role: str = page_roles.PAGE_ROLE_IMAGES,
    timecode_base_fps: str | None = None,
    scan_chain_label: str | None = None,
    version_rank: int | None = None,
) -> dict:
    """Payload QR **reel**, valide par `io.payload`, jamais bricole a la main.

    ``page_role`` est **parametrable depuis la passe de correction de 5.16**, et son
    absence etait un trou nomme par la revue (observation de la couche 2): aucune fabrique
    de ce module ne produisait de page de calibration, donc aucun test ne faisait traverser
    un lot **contenant** une page de calibration a l'ecriture des frames puis a l'ecriture
    du manifest. C'est exactement le chemin ou vivait le bloquant B1.

    Sous le role de calibration, le cardinal d'emplacements est force a zero: c'est le
    contrat, et la garde d'`io.payload` refuserait l'inverse -- une fabrique qui pourrait
    produire une page de calibration porteuse d'emplacements serait une fabrique capable
    de fabriquer un cas impossible.
    """
    if page_role == page_roles.PAGE_ROLE_CALIBRATION:
        slot_count = 0
    if first_slot is None:
        first_slot = page_index * slot_count
    # Story 2.7 (payload 2.1): meme regime que `scan_chain_label` juste en
    # dessous -- requis sous le role images, absent (sentinelle vide, jamais
    # ecrite) sous le role calibration. Defaut "30/1", **le meme regime que**
    # `rich_extraction_manifest` (`fps_source=30`): un manifest riche existant
    # et des payloads scannes qui divergeraient sur ce champ seraient un vrai
    # conflit (`_check_manifest_conflicts`), pas un artefact de fabrique.
    if timecode_base_fps is None:
        timecode_base_fps = (
            "" if page_role == page_roles.PAGE_ROLE_CALIBRATION else "30/1"
        )
    slots = [
        {
            "slot_index": first_slot + offset,
            "frame_timecode": f"00:00:{first_slot + offset:02d}:00",
        }
        for offset in range(slot_count)
    ]
    return payload_io.build_page_payload(
        project_id=project_id,
        rush_id=rush_id,
        lot_id=lot_id if lot_id is not None else naming.build_lot_id(rush_id, fps_target),
        page_index=page_index,
        page_count=page_count,
        fps_target=fps_target,
        timecode_base_fps=timecode_base_fps,
        template_id=template_id,
        patch_preset_id=patch_preset_id,
        target_colorspace=COLORSPACE,
        gamut_map_id=gamut_map_id or payload_io.GAMUT_MAP_IDENTITY,
        slots=slots,
        page_role=page_role,
        # AMENDE PAR 5.23 (2026-08-18): le libelle de chaine est **obligatoire** sous le
        # role `c` et **refuse** ailleurs, donc la fabrique le passe conditionnellement
        # au role -- exactement comme elle force deja le cardinal d'emplacements a zero,
        # et pour la meme raison: une fabrique capable de produire un cas que le contrat
        # refuse est une fabrique capable de fabriquer un cas impossible.
        # **Le libelle est parametrable depuis la story 5.24**, et c'est le point 3
        # de la regle des fabriques: une passe de vrac peut porter DEUX pages de
        # calibration, et deux feuilles au meme libelle produiraient le meme nom de
        # fichier de profil -- donc un profil ecrase par l'autre, exactement ce que
        # l'AC 7 interdit. Une fabrique mono-valeur rendait ce defaut invisible. Le
        # defaut ne bouge pas: aucun appelant existant ne change de comportement.
        scan_chain_label=(
            (scan_chain_label or SCAN_CHAIN_LABEL_PAR_DEFAUT)
            if page_role == page_roles.PAGE_ROLE_CALIBRATION else None),
        # `EPIC11-ARB-91` / `EPIC11-ARB-176`: le rang de TIRAGE de la planche.
        # `None` reproduit exactement une planche d'AVANT l'arbitrage -- le
        # champ est alors **omis** de la charge utile, ce qui est le regime de
        # tout le parc deja imprime et le seul cas ou la convention « `v`
        # absent vaut 1 » traverse jusqu'au manifeste.
        version_rank=version_rank,
    )


def crop_plan_for(payload: dict) -> scan_crop.PageCropPlan:
    """Plan de decoupe du **vrai** module 5.3."""
    return scan_crop.build_page_crop_plan(
        template_id=payload["template_id"], slots=payload["slots"], dpi=DPI
    )


def scanned_page(payload: dict, *, failure: str | None = None) -> sof.ScannedPage:
    """Page telle que la chaine scan la remet a l'ecriture de 5.6.

    La page de calibration est reconnue **par son role** et non par son cardinal
    d'emplacements, exactement comme `cli._scanned_pages_for_output` le fait: ni plan de
    decoupe, ni frames, ni mires. C'est la quatrieme nature de page du chemin de scan.
    """
    if payload.get("page_role") == page_roles.PAGE_ROLE_CALIBRATION:
        return sof.ScannedPage(payload=payload, crop_plan=None, frames=())
    plan = crop_plan_for(payload)
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


def write_report(
    project_dir: Path,
    pages: list[sof.ScannedPage],
    *,
    overwrite: bool = False,
    color_calibration_status: str = color_pipeline.NOT_APPLIED_STATUS,
) -> sof.LotOutputReport:
    """Rapport du **vrai** module 5.6, obtenu en ecrivant de vrais TIFF."""
    return sof.write_lot_output_frames(
        project_dir,
        pages,
        overwrite=overwrite,
        color_calibration_status=color_calibration_status,
    )


def provenance(page_index: int, *, read_rank: int | None = None) -> sm.ScanPageProvenance:
    return sm.ScanPageProvenance(
        read_rank=page_index if read_rank is None else read_rank,
        status=scan_detection.PAGE_OK,
        qr_status=scan_detection.qr_codes.DECODE_OK,
        page_index=page_index,
        homography_status=sm.HOMOGRAPHY_RESOLVED,
    )


def make_record(
    payloads: list[dict],
    report: sof.LotOutputReport,
    *,
    scan_dpi: int = 600,
    ingest_slug: str = "lot-a",
    page_calibrations: tuple[tuple[int, object], ...] = (),
    divergence_bypass_requested: bool = False,
) -> sm.ScanRecord:
    return sm.ScanRecord(
        page_payloads=tuple(payloads),
        output_report=report,
        scan_dpi=scan_dpi,
        ingest_slug=ingest_slug,
        pages=tuple(provenance(payload["page_index"]) for payload in payloads),
        page_calibrations=page_calibrations,
        divergence_bypass_requested=divergence_bypass_requested,
    )


def scan_once(
    project_dir: Path,
    payloads: list[dict],
    *,
    failures: dict[int, str] | None = None,
    overwrite: bool = False,
    color_calibration_status: str = color_pipeline.NOT_APPLIED_STATUS,
    page_calibrations: tuple[tuple[int, object], ...] = (),
) -> sm.PersistedScan:
    """Une passe complete, **dans l'ordre reel de la chaine** (EPIC5-ARB-34).

    Refus prealable (5.7) -> ecriture des frames (5.6) -> manifest (5.7). Le
    harnais n'a pas le droit de court-circuiter le premier maillon: c'est
    precisement parce que les tests appelaient directement `persist_scan` que
    la destruction des frames legitimes avant un refus est passee inapercue.

    `overwrite` est **un seul drapeau** pour les deux ecritures (EPIC5-ARB-18),
    comme a la CLI: il n'y a pas d'intention d'operateur qui leve l'une sans
    l'autre.
    """
    failures = failures or {}
    project_dir.mkdir(parents=True, exist_ok=True)
    sm.check_scan_conflicts(
        project_dir,
        payloads,
        failed_page_indexes=tuple(sorted(failures)),
        overwrite=overwrite,
    )
    pages = [
        scanned_page(payload, failure=failures.get(payload["page_index"]))
        for payload in payloads
    ]
    report = write_report(
        project_dir,
        pages,
        overwrite=overwrite,
        color_calibration_status=color_calibration_status,
    )
    return sm.persist_scan(project_dir, make_record(
        payloads, report, page_calibrations=page_calibrations))


def calibration_result(status: str, *, page_id: str = "lot-a-p0"):
    """Un resultat de calibration **par page**, reduit a ce que le manifest en projette.

    Necessaire depuis `EPIC5-ARB-69`: une page ne porte plus que le statut qu'elle a
    produit, donc un test qui veut une page `applied` doit lui donner son resultat. La
    fabrique passe par le vrai type -- la projection est faite par
    `correction_provenance_summary`, et un faux objet ne prouverait rien de la forme
    ecrite au document.
    """
    from mixed_media_utility import color_calibration as cc

    return cc.PageCalibration(
        status=status,
        values_version="patch-values-1",
        patch_preset_id="patches-14-v3",
        profile=None,
        acceptance=None,
        replicate_dispersion_de76=None,
        channel_relative_deviation_before_correction=None,
        clipping=None,
        correction_source=cc.CORRECTION_SOURCE_CALIBRATION_PAGE,
        correction_source_page_id=page_id,
    )


#: Six chaines, **dans un ordre d'insertion different de l'ordre trie**, et la cible du
#: tri -- `chaine-a`, celle qui doit sortir en tete -- scannee **en derniere position**.
#:
#: Les deux proprietes sont la regle des fabriques appliquee a un tri (finding `E-F1` de
#: la couche 2 de la revue de 5.22, et le depot a deja paye exactement ce defaut a la
#: campagne 5.7). Un ensemble de **deux** elements deja inseres dans l'ordre trie ne
#: prouve jamais un tri: l'ordre d'iteration d'un `set` depend de la graine de hachage du
#: processus, et le mutant qui retire `sorted()` **survivait sous `PYTHONHASHSEED=3`**
#: tout en mourant sous d'autres graines. Six elements ramenent la coincidence a 1 sur
#: 720, et l'ordre d'insertion inverse distingue « trie » de « ordre d'arrivee ».
CHAINES_DESORDONNEES = (
    "chaine-m", "chaine-z", "chaine-c", "chaine-y", "chaine-b", "chaine-a",
)


def calibration_results_for_chains(chain_ids: tuple[str, ...]):
    """Un resultat de calibration **par page**, chacun corrige par une chaine differente.

    Le champ `profile` est renseigne parce que `_record_calibration_chains` ne consigne
    qu'une chaine ayant **reellement** corrige quelque chose: un profil charge dont toutes
    les planches divergent n'a rien corrige et ne s'inscrit pas. La fabrique doit donc
    produire le regime ou l'ecriture a lieu, sans quoi elle mesurerait le silence.

    Les `page_index` suivent l'ordre d'insertion des chaines: la page 0 porte la premiere
    chaine de la liste, pas la premiere de l'ordre trie.
    """
    from mixed_media_utility import color_calibration as cc

    return tuple(
        (index, cc.PageCalibration(
            status=color_pipeline.APPLIED_STATUS,
            values_version="patch-values-1",
            patch_preset_id="patches-14-v3",
            # Un objet quelconque suffit: ce module ne lit du profil que sa **presence**,
            # et y mettre un vrai profil ferait descendre numpy dans un test de
            # persistance sans rien mesurer de plus.
            profile=object(),
            acceptance=None,
            replicate_dispersion_de76=None,
            channel_relative_deviation_before_correction=None,
            clipping=None,
            correction_source=cc.CORRECTION_SOURCE_CHAIN_PROFILE,
            correction_source_page_id=f"lot-a-p{index}",
            correction_chain_id=chain_id,
        ))
        for index, chain_id in enumerate(chain_ids)
    )


def two_pages(**kwargs) -> list[dict]:
    return [
        make_payload(page_index=0, **kwargs),
        make_payload(page_index=1, **kwargs),
    ]


#: Gabarit v2, seul regime qui porte une page de calibration. Deux frames par page, comme
#: `TPL`, pour que la seule difference mesuree soit la page de calibration elle-meme.
TPL_V2 = "tpl-a4-portrait-2f-v2"


def v2_lot_with_calibration_page(*, images_pages: int = 2) -> list[dict]:
    """Le lot de la forme nominale depuis 5.16: page de calibration a l'index 0, puis N.

    Deux planches d'images au minimum, aux emplacements distinguables: une fabrique
    mono-planche rendrait invisible toute erreur de position dans la pagination, et c'est
    la regle des fabriques du depot.
    """
    page_count = 1 + images_pages
    pages = [make_payload(page_index=page_roles.CALIBRATION_PAGE_INDEX,
                          page_count=page_count, template_id=TPL_V2,
                          page_role=page_roles.PAGE_ROLE_CALIBRATION)]
    for rank in range(images_pages):
        pages.append(make_payload(page_index=1 + rank, page_count=page_count,
                                  first_slot=2 * rank, slot_count=2,
                                  template_id=TPL_V2))
    return pages


def lot_of(manifest: dict, lot_id: str = LOT) -> dict:
    return next(lot for lot in manifest["lots"] if lot["lot_id"] == lot_id)


def output_frames_digest(project_dir: Path) -> dict[str, bytes]:
    """Empreinte du dossier de sortie, fichier par fichier.

    Ce que la revue a montre indispensable: le refus des gardes de conflit
    protegeait le manifest et laissait detruire les frames. Comparer les octets
    du `project.json` ne prouve donc rien du seul artefact que l'operateur a mis
    des heures a produire.

    L'empreinte porte le contenu **et** la date de modification. Le contenu seul
    ne suffit pas: une passe refusee apres l'ecriture reecrit des frames
    identiques, et rien ne la distingue alors d'une passe qui n'a rien ecrit --
    la campagne de mutation l'a montre en faisant survivre deux mutants qui
    ecrivent avant de refuser.
    """
    import hashlib

    root = project_dir / SCAN_FRAMES_DIRNAME
    if not root.is_dir():
        return {}
    return {
        str(path.relative_to(root)): (
            hashlib.sha256(path.read_bytes()).hexdigest(),
            path.stat().st_mtime_ns,
        )
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def rich_extraction_manifest(
    *, fps_target: float = FPS, rush_id: str = RUSH, project_id: str = PROJECT
) -> dict:
    """Manifest riche produit par le **vrai** producteur d'extraction (story 3.4).

    Ecrire ce manifest a la main serait exactement la fixture qui « encode
    silencieusement la mauvaise convention »: la regle de non-perte de l'AC 4
    porte sur ce que l'extraction ecrit reellement, pas sur ce qu'on croit
    qu'elle ecrit.
    """
    selection = select_source_frames(
        fps_source=30, fps_target=fps_target, source_frame_count=100
    )
    record = ExtractionRecord(
        project_id=project_id,
        rush_id=rush_id,
        rush_source_name="rush-001.mov",
        lot_id=naming.build_lot_id(rush_id, fps_target),
        frames_dir_relative=f"{EXTRACT_FRAMES_DIRNAME}/{rush_dir_slug(rush_id, fps_target)}",
        selection=selection,
        fps_source=30.0,
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
        confirmed_at="2026-08-04T09:30:00Z",
    )
    return build_extraction_manifest(None, record)


def write_manifest(project_dir: Path, manifest: dict) -> Path:
    project_dir.mkdir(parents=True, exist_ok=True)
    path = project_dir / MANIFEST_FILENAME
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# AC 7 -- le schema d'abord: sans lui, l'ecriture echoue apres tout le travail
# --------------------------------------------------------------------------


#: Les **quatre** proprietes de `lots[]` que cette story declare -- la
#: quatrieme, `synthetic_frames`, est ajoutee par EPIC5-ARB-33: c'est le
#: registre durable des mires, et c'est lui qui rend les deux cardinaux
#: calculables.
STORY_LOT_PROPERTIES = (
    "output_frames_dir",
    "reconstructed_frame_count",
    "synthetic_frame_count",
    "synthetic_frames",
)


def test_the_four_lot_properties_of_this_story_are_declared() -> None:
    """`lots[].items` est en `additionalProperties: false`: un champ non declare
    est inecrivable, et l'echec survient **apres** le decodage, les
    homographies, la decoupe et l'ecriture des frames."""
    lot_schema = schema()["properties"]["lots"]["items"]
    assert lot_schema["additionalProperties"] is False
    for name in STORY_LOT_PROPERTIES:
        assert name in lot_schema["properties"], name


def test_the_mire_registry_is_declared_as_a_set_of_file_names() -> None:
    """EPIC5-ARB-33: des **noms de fichiers**, uniques, et jamais un chemin --
    c'est ce que le dossier rend et ce que le rapport de 5.6 nomme."""
    declaration = schema()["properties"]["lots"]["items"]["properties"][
        "synthetic_frames"
    ]
    assert declaration["type"] == "array"
    assert declaration["uniqueItems"] is True
    assert declaration["items"]["type"] == "string"
    assert declaration["items"]["minLength"] == 1
    validator = Draft7Validator(declaration)
    assert validator.is_valid(["scan_rush-001_5_00-00-00-00.tiff"])
    for refused in (
        ["sous/dossier.tiff"],
        ["sous\\dossier.tiff"],
        [""],
        ["a.tiff", "a.tiff"],
    ):
        assert not validator.is_valid(refused), refused


def test_the_three_printed_identifiers_keep_the_declaration_of_story_5_11() -> None:
    """Frontiere de schema (AC 7 / AC 12): 5.11 declare ces trois-la et elle
    seule; 5.7 les **ecrit** quand ils sont absents et les confronte quand ils
    sont presents (EPIC5-ARB-34), mais ecrire n'est pas declarer.

    Le test d'origine se contentait de verifier que les trois proprietes
    existent: il serait passe a l'identique si 5.7 les avait declarees
    elle-meme, ce qui est exactement ce qu'il pretendait interdire. Ici, c'est
    la **declaration** qui est epinglee -- forme exacte et story proprietaire
    nommee dans sa description --, si bien qu'une redeclaration par 5.7, qui
    aurait ecrit sa propre description comme elle l'a fait pour ses quatre
    proprietes, fait tomber le test."""
    lot_schema = schema()["properties"]["lots"]["items"]["properties"]
    assert set(sm.PRINTED_IDENTIFIER_FIELDS) == {
        "template_id",
        "patch_preset_id",
        "gamut_map_id",
    }
    for name in sm.PRINTED_IDENTIFIER_FIELDS:
        declaration = lot_schema[name]
        assert set(declaration) == {"description", "type", "minLength"}, name
        assert declaration["type"] == "string"
        assert declaration["minLength"] == 1
        assert "story 5.11" in declaration["description"], name
        assert "makepdf" in declaration["description"], name
        assert "story 5.7" not in declaration["description"], name
    for name in STORY_LOT_PROPERTIES:
        assert "story 5.11" not in lot_schema[name]["description"], name


def test_an_undeclared_lot_field_is_refused_by_the_validation_of_the_temporary(
    tmp_path: Path,
) -> None:
    """Test negatif de l'AC 13, **sur le chemin que l'AC nomme**.

    L'AC demande qu'un champ de lot ecrit sans avoir ete declare fasse echouer
    `validate_manifest` -- c'est-a-dire la validation du **temporaire** de
    `_atomic_write`, la derniere barriere avant la bascule. Le test d'origine
    posait le champ sur le manifest *relu*, ou c'est la validation interne de
    `reconstruct_project_manifest` qui attrape, et acceptait les deux
    exceptions sans les distinguer: il ne prouvait donc rien du chemin que
    l'ordre « schema d'abord » protege. Ici le champ est pose sur le document
    que la fusion vient de produire, exactement comme si `synthetic_frames`
    avait ete ecrit avant d'etre declare."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    scan_once(project_dir, two_pages())
    path = project_dir / MANIFEST_FILENAME
    before = path.read_bytes()

    payloads = two_pages()
    sm.check_scan_conflicts(project_dir, payloads, overwrite=True)
    report = write_report(
        project_dir, [scanned_page(p) for p in payloads], overwrite=True
    )
    merge = sm.build_scan_manifest(
        json.loads(before.decode("utf-8")), make_record(payloads, report)
    )
    lot_of(merge.manifest)["cardinal_bricole"] = 4

    with pytest.raises(ManifestWriteError, match="cardinal_bricole"):
        sm._atomic_write(path, merge.manifest)

    assert path.read_bytes() == before
    assert not list(project_dir.glob(f".{MANIFEST_FILENAME}.*"))


def test_an_undeclared_lot_field_of_the_read_manifest_is_refused_before_any_write(
    tmp_path: Path,
) -> None:
    """Pendant du precedent, sur l'autre validation: le champ vient cette fois
    du `project.json` relu, et c'est la garde interne de la reconstruction qui
    refuse. Aucune des deux ne laisse passer le champ."""
    project_dir = tmp_path / "projet"
    existing = rich_extraction_manifest()
    lot_of(existing)["scan_dpi_du_lot"] = 600
    path = write_manifest(project_dir, existing)
    before = path.read_bytes()

    with pytest.raises(ReconstructionError, match="scan_dpi_du_lot"):
        scan_once(project_dir, two_pages())

    assert path.read_bytes() == before
    assert not list(project_dir.glob(f".{MANIFEST_FILENAME}.*"))


def test_the_calibration_status_enum_is_the_one_of_color_pipeline() -> None:
    """Un vocabulaire ferme que le schema ne verrouille pas n'est pas ferme --
    et il n'est ajoute qu'**une** fois, avec un seul vocabulaire."""
    doc = schema()
    project_level = doc["properties"]["color"]["properties"]["color_calibration_status"]
    per_page = doc["properties"]["reconstruction"]["properties"][
        "page_calibration_results"
    ]["items"]["properties"]["status"]
    assert tuple(project_level["enum"]) == color_pipeline.CALIBRATION_STATUS_VALUES
    assert tuple(per_page["enum"]) == color_pipeline.CALIBRATION_STATUS_VALUES


def test_the_synthetic_reason_enum_is_the_closed_vocabulary_of_story_5_6() -> None:
    """Le vocabulaire est **identique des deux cotes**: il est importe, pas
    redefini (5.6, AC 14)."""
    slot_schema = schema()["properties"]["reconstruction"]["properties"]["slots"][
        "items"
    ]["properties"]
    assert tuple(slot_schema["synthetic_reason"]["enum"]) == sof.SYNTHETIC_FRAME_REASONS


def test_the_declared_vocabularies_match_their_python_constants() -> None:
    """Chaque enum du schema pose par cette story a une constante qui fait foi."""
    doc = schema()["properties"]["reconstruction"]["properties"]
    assert tuple(doc["origin"]["enum"]) == tuple(sorted(RECONSTRUCTION_ORIGINS))
    pages = doc["scan"]["properties"]["pages"]["items"]["properties"]
    assert tuple(pages["status"]["enum"]) == scan_detection.PAGE_STATUSES
    assert tuple(pages["qr_status"]["enum"]) == scan_detection.PAGE_QR_STATUSES
    assert tuple(pages["homography_status"]["enum"]) == sm.HOMOGRAPHY_STATUSES
    assert sm.SCAN_LOT_STATE in LOT_STATES


# --------------------------------------------------------------------------
# AC 1, AC 2, AC 6 -- creation depuis un scan seul
# --------------------------------------------------------------------------


def test_a_scan_alone_creates_a_valid_v2_manifest(tmp_path: Path) -> None:
    """Le cas central: un carton de planches imprimees, et rien d'autre."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    persisted = scan_once(project_dir, two_pages())

    assert persisted.manifest_path == project_dir / MANIFEST_FILENAME
    validate_manifest(persisted.manifest_path)
    document = json.loads(persisted.manifest_path.read_text(encoding="utf-8"))
    assert document["schema_version"] == "2.1"
    assert document["project_id"] == PROJECT
    assert lot_of(document)["rush_id"] == RUSH
    assert document["reconstruction"]["origin"] == "scan"
    assert document["reconstruction"]["status"] == "complete"


def test_the_manifest_is_validated_before_the_previous_one_is_replaced(
    tmp_path: Path,
) -> None:
    """Ecrire puis valider -- le motif de `reconstruct-project` -- corromprait
    le projet des lors qu'un manifest existant est enrichi (AC 2)."""
    project_dir = tmp_path / "projet"
    existing = rich_extraction_manifest()
    # `video.codec_target` a un type: une valeur absurde fait echouer la
    # validation du temporaire, jamais celle du fichier en place.
    existing["video"]["codec_target"] = 42
    path = write_manifest(project_dir, existing)
    before = path.read_bytes()

    with pytest.raises(ManifestWriteError):
        scan_once(project_dir, two_pages())

    assert path.read_bytes() == before


def test_the_scan_writes_the_output_frames_dir_of_the_report(tmp_path: Path) -> None:
    """Le chemin est **transporte** du rapport de 5.6, jamais recalcule."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    pages = [scanned_page(payload) for payload in two_pages()]
    report = write_report(project_dir, pages)
    persisted = sm.persist_scan(project_dir, make_record(two_pages(), report))

    assert lot_of(persisted.manifest)["output_frames_dir"] == report.output_dir
    assert report.output_dir.startswith(f"{SCAN_FRAMES_DIRNAME}/")


def test_a_legacy_poc_manifest_is_refused_without_any_write(tmp_path: Path) -> None:
    """Aucune migration automatique, et aucune ecriture."""
    project_dir = tmp_path / "projet"
    path = write_manifest(project_dir, {"id": "poc", "meta": {"lot": {"state": "scan"}}})
    before = path.read_bytes()

    with pytest.raises(LegacyManifestError):
        scan_once(project_dir, two_pages())

    assert path.read_bytes() == before


def test_a_lot_without_any_decoded_payload_writes_nothing(tmp_path: Path) -> None:
    """Un lot dont aucune planche n'a livre son QR n'ecrit pas un manifest
    appauvri: il ne l'ecrit pas du tout."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    pages = [scanned_page(payload) for payload in two_pages()]
    report = write_report(project_dir, pages)

    with pytest.raises(sm.ScanPersistenceError, match="Aucun payload"):
        sm.ScanRecord(
            page_payloads=(),
            output_report=report,
            scan_dpi=600,
            ingest_slug="lot-a",
        )
    assert not (project_dir / MANIFEST_FILENAME).exists()


# --------------------------------------------------------------------------
# AC 3 -- l'etat de lot passe par la garde ordonnee, et n'est jamais abaisse
# --------------------------------------------------------------------------


def test_the_scan_chain_writes_scan_on_the_v2_lot_state(tmp_path: Path) -> None:
    """`scan` recoit son premier producteur sur `lots[].state` du contrat v2."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    persisted = scan_once(project_dir, two_pages())

    assert lot_of(persisted.manifest)["state"] == "scan"
    assert persisted.state_written == "scan"
    assert sm.SCAN_STATE_CONSERVED not in persisted.findings


def test_the_reconstruct_project_subcommand_still_writes_reconstruction() -> None:
    """La sous-commande n'est pas touchee: son dict de lot reste identique a
    l'octet pres, `state` compris.

    **`timecode_base_fps` rejoint le dict par la story 2.7** (payload 2.1,
    `EPIC7-ARB-56`): `reconstruct_project_manifest` l'ecrit desormais sur le
    lot au meme titre que `fps_target`.
    """
    manifest = reconstruct_project_manifest([make_payload(page_index=0, page_count=1)])
    assert manifest["lots"] == [
        {
            "lot_id": LOT,
            "rush_id": RUSH,
            "state": "reconstruction",
            "fps_target": FPS,
            "timecode_base_fps": "30/1",
        }
    ]


@pytest.mark.parametrize("previous_state", ["extraction", "pdf"])
def test_a_lot_before_scan_moves_forward_to_scan(
    tmp_path: Path, previous_state: str
) -> None:
    """`extraction -> scan` et, depuis 5.11, `pdf -> scan`: sequence nominale
    complete d'un lot -- extrait, imprime, scanne."""
    project_dir = tmp_path / "projet"
    existing = rich_extraction_manifest()
    lot_of(existing)["state"] = previous_state
    write_manifest(project_dir, existing)

    persisted = scan_once(project_dir, two_pages())

    assert lot_of(persisted.manifest)["state"] == "scan"
    assert sm.SCAN_STATE_CONSERVED not in persisted.findings


@pytest.mark.parametrize("previous_state", ["reconstruction", "encode"])
def test_a_lot_past_scan_keeps_its_state_and_is_not_lowered(
    tmp_path: Path, previous_state: str
) -> None:
    """« Projet recree depuis des payloads, puis planches scannees » est le cas
    nominal: l'etat en place est conserve, le fait est nomme en information, et
    la commande reussit."""
    project_dir = tmp_path / "projet"
    existing = rich_extraction_manifest()
    lot_of(existing)["state"] = previous_state
    write_manifest(project_dir, existing)

    persisted = scan_once(project_dir, two_pages())

    assert lot_of(persisted.manifest)["state"] == previous_state
    assert persisted.state_written == previous_state
    assert sm.SCAN_STATE_CONSERVED in persisted.findings


def test_the_shared_state_order_places_scan_between_pdf_and_reconstruction() -> None:
    """Aucune comparaison d'etats n'est reecrite: `scan` est a l'index 2, apres
    `extraction` et `pdf`, avant `reconstruction` et `encode`.

    Sentinelle sur `LOT_STATES`, et rien d'autre: ce test n'exerce **aucune
    ligne** du code livre par cette story. Il est garde pour ce qu'il vaut -- un
    canari sur la constante dont toute la garde d'ordre depend --, mais son nom
    d'origine (`..._is_the_one_of_the_shared_guard`) laissait croire qu'il
    prouvait quelque chose de la story."""
    assert LOT_STATES.index("scan") == 2
    assert LOT_STATES.index("extraction") < LOT_STATES.index("pdf") < 2
    assert 2 < LOT_STATES.index("reconstruction") < LOT_STATES.index("encode")


def test_an_unknown_requested_state_is_a_hard_failure_not_a_silent_conservation() -> None:
    """Confondre « etat inexistant » et « retour en arriere refuse » ferait
    taire un defaut d'appel."""
    with pytest.raises(ReconstructionError, match="Etat de lot"):
        reconstruct_project_manifest(
            [make_payload(page_index=0, page_count=1)], lot_state="scanne"
        )


# --------------------------------------------------------------------------
# AC 4 -- enrichir ne fait jamais desapprendre
# --------------------------------------------------------------------------


def test_enriching_a_rich_manifest_loses_nothing_field_by_field(tmp_path: Path) -> None:
    """La comparaison porte sur **chaque** cle des sections de tete et de
    chaque entree, et pas sur une presence globale: c'est la ou la
    reconstruction appauvrissait sans un mot."""
    project_dir = tmp_path / "projet"
    existing = rich_extraction_manifest()
    existing["created"] = "2026-08-04T09:30:00Z"
    existing["artifacts"] = {"frames_dir": EXTRACT_FRAMES_DIRNAME,
                            "outputs_dir": OUTPUTS_DIRNAME}
    existing["video"] = {"codec_target": "prores_422"}
    existing["color"] = {
        "target_colorspace": COLORSPACE,
        "target_color_primaries": "bt709",
        "target_color_trc": "bt709",
        "scan_input_format": "tiff",
        "source_bit_depth": 16,
    }
    write_manifest(project_dir, existing)

    persisted = scan_once(project_dir, two_pages())
    after = persisted.manifest

    assert after["created"] == existing["created"]
    for section in ("artifacts", "video", "color"):
        for key, value in existing[section].items():
            assert after[section][key] == value, f"{section}.{key} perdu"
    before_rush = existing["rushes"][0]
    after_rush = next(r for r in after["rushes"] if r["rush_id"] == RUSH)
    for key, value in before_rush.items():
        assert after_rush[key] == value, f"rushes[].{key} perdu"
    before_lot = lot_of(existing)
    after_lot = lot_of(after)
    for key, value in before_lot.items():
        if key == "state":
            continue  # seul champ que la chaine de scan fait avancer (AC 3)
        assert after_lot[key] == value, f"lots[].{key} perdu"
    # Les champs irrecuperables depuis un scan sont precisement ceux dont la
    # perte serait definitive: le rush n'est pas sur la machine.
    assert after_lot["frame_timecodes_digest"] == before_lot["frame_timecodes_digest"]
    assert after_lot["rounding_policy"] == before_lot["rounding_policy"]
    assert after_rush["fps_source"] == 30.0
    assert after_rush["resolution_source"] == {"width": 1920, "height": 1080}


def test_the_three_printed_identifiers_survive_untouched_when_they_agree(
    tmp_path: Path,
) -> None:
    """Egalite constatee: on reecrit la meme valeur. Jamais un ecrasement au
    motif que « le QR fait foi »."""
    project_dir = tmp_path / "projet"
    existing = rich_extraction_manifest()
    lot = lot_of(existing)
    lot["template_id"] = TPL
    lot["patch_preset_id"] = PATCH_PRESET
    lot["gamut_map_id"] = payload_io.GAMUT_MAP_IDENTITY
    write_manifest(project_dir, existing)

    persisted = scan_once(project_dir, two_pages())

    after = lot_of(persisted.manifest)
    assert after["template_id"] == TPL
    assert after["patch_preset_id"] == PATCH_PRESET
    assert after["gamut_map_id"] == payload_io.GAMUT_MAP_IDENTITY


def test_other_lots_and_rushes_of_the_project_are_left_intact(tmp_path: Path) -> None:
    """Scanner un lot ne dit rien des autres; ils restent intacts et le fait
    est signale **en information** (question ouverte 4).

    Le lot vise est **le dernier** de `lots[]`, et ce n'est pas cosmetique: la
    fabrique d'origine le placait en premier, si bien qu'une regression rendant
    le premier lot venu au lieu du lot vise laissait les 257 tests verts."""
    project_dir = tmp_path / "projet"
    existing = rich_extraction_manifest()
    other = copy.deepcopy(lot_of(existing))
    other["lot_id"] = "rush-002_12"
    other["rush_id"] = "rush-002"
    existing["lots"].insert(0, other)
    existing["rushes"].append({"rush_id": "rush-002", "fps_source": 25.0})
    write_manifest(project_dir, existing)

    persisted = scan_once(project_dir, two_pages())

    assert [lot["lot_id"] for lot in persisted.manifest["lots"]][0] == "rush-002_12"
    survivor = lot_of(persisted.manifest, "rush-002_12")
    assert survivor == other
    assert sm.SCAN_OTHER_LOTS_NOT_SCANNED in persisted.findings


def test_the_cardinals_land_on_the_scanned_lot_and_not_on_the_first_one(
    tmp_path: Path,
) -> None:
    """Survivant `M25` de la campagne de revue, et litteralement le risque R12:
    une regression sur la recherche du lot faisait ecrire `output_frames_dir` et
    les deux cardinaux **sur un autre lot du meme rush**, le lot scanne ne
    recevant rien -- sans qu'aucun des 257 tests ne sonne.

    Cause: toutes les fixtures multi-lots placaient le lot vise en premier.
    C'est le `M33` de la campagne 5.6 reproduit a l'identique (« une fabrique de
    test uniforme rend une permutation invisible »), et il se ferme en corrigeant
    la fabrique avant d'ecrire le test.

    Deux lots du **meme rush** a deux cadences: le cas nominal de la v2.1."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    # Le lot a 8 im/s est scanne le premier, donc pose en tete de `lots[]`.
    scan_once(project_dir, two_pages(fps_target=8.0))
    scanned = scan_once(project_dir, two_pages())

    order = [lot["lot_id"] for lot in scanned.manifest["lots"]]
    assert order == ["rush-001_8", LOT], "le lot vise doit etre le second"
    decoy = lot_of(scanned.manifest, "rush-001_8")
    target = lot_of(scanned.manifest, LOT)
    assert target["output_frames_dir"] == f"{SCAN_FRAMES_DIRNAME}/rush-001_5"
    assert decoy["output_frames_dir"] == f"{SCAN_FRAMES_DIRNAME}/rush-001_8"
    assert target["reconstructed_frame_count"] == 4
    assert scanned.lot_id == LOT


def test_an_expected_frame_count_already_measured_is_never_overwritten(
    tmp_path: Path,
) -> None:
    """L'extraction a compte de **vraies** frames; le scan ne compte que des
    emplacements de planche. Ce qui a ete mesure une fois ne se desapprend pas."""
    project_dir = tmp_path / "projet"
    existing = rich_extraction_manifest()
    measured = lot_of(existing)["expected_frame_count"]
    write_manifest(project_dir, existing)

    persisted = scan_once(project_dir, two_pages())

    assert measured != 4, "la fixture doit rendre les deux cardinaux differents"
    assert lot_of(persisted.manifest)["expected_frame_count"] == measured
    assert sm.SCAN_EXPECTED_FRAME_COUNT_CONSERVED in persisted.findings


def test_an_indeterminable_expected_frame_count_is_never_guessed(tmp_path: Path) -> None:
    """La **derniere** page manque: le cardinal attendu est indeterminable, il
    n'est pas ecrit et il n'est pas remplace par un autre cardinal."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    persisted = scan_once(project_dir, [make_payload(page_index=0)])

    assert persisted.expected_frame_count is None
    assert "expected_frame_count" not in lot_of(persisted.manifest)
    assert sm.SCAN_EXPECTED_FRAME_COUNT_INDETERMINABLE in persisted.findings
    assert not persisted.lot_complete


# --------------------------------------------------------------------------
# AC 5 -- une divergence se refuse et se nomme, elle ne se resout pas en ecrivant
# --------------------------------------------------------------------------


def _existing_with_printed_identifiers(**overrides) -> dict:
    existing = rich_extraction_manifest()
    lot = lot_of(existing)
    lot["template_id"] = TPL
    lot["patch_preset_id"] = PATCH_PRESET
    lot["gamut_map_id"] = payload_io.GAMUT_MAP_IDENTITY
    lot.update(overrides)
    return existing


@pytest.mark.parametrize(
    "field_name, persisted_value",
    [
        ("template_id", "tpl-a4-paysage-8f-m5-v1"),
        ("patch_preset_id", "patch-values-1"),
        ("gamut_map_id", "gamut-map-srgb-clip-1"),
    ],
)
def test_a_diverging_printed_identifier_is_refused_and_discriminates_the_hypothesis(
    tmp_path: Path, field_name: str, persisted_value: str
) -> None:
    """Le refus nomme les **deux** valeurs, et **tranche** entre les deux
    hypotheses du point H2 au lieu de les enoncer a egalite.

    Sur cette branche le lot a ete trouve par son `lot_id` et un `project_id`
    divergent aurait deja ete refuse en amont: les identifiants concordent
    donc, et le verdict de H2 est toujours « planche perimee ». Presenter la
    planche etrangere comme egalement possible mettait du bruit sur le seul
    signal que cette garde existe pour porter."""
    project_dir = tmp_path / "projet"
    existing = _existing_with_printed_identifiers(**{field_name: persisted_value})
    path = write_manifest(project_dir, existing)
    before = path.read_bytes()

    with pytest.raises(sm.ScanManifestConflictError) as excinfo:
        scan_once(project_dir, two_pages())

    message = str(excinfo.value)
    assert field_name in message
    assert persisted_value in message
    assert "PERIMEE" in message
    assert "ETRANGERE" in message and "ecartee" in message
    assert "CONCORDENT" in message
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "field_name, persisted_value",
    [
        ("template_id", "tpl-a4-paysage-8f-m5-v1"),
        ("patch_preset_id", "patch-values-1"),
        ("gamut_map_id", "gamut-map-srgb-clip-1"),
    ],
)
def test_no_overwrite_flag_lifts_a_printed_identifier_conflict(
    tmp_path: Path, field_name: str, persisted_value: str
) -> None:
    """`--overwrite` ne couvre que le rescan du **meme** lot (AC 10), jamais
    l'apport d'une planche etrangere au manifest d'un autre projet."""
    project_dir = tmp_path / "projet"
    write_manifest(
        project_dir, _existing_with_printed_identifiers(**{field_name: persisted_value})
    )

    with pytest.raises(sm.ScanManifestConflictError):
        scan_once(project_dir, two_pages(), overwrite=True)


def test_equal_printed_identifiers_pass_silently_and_leave_the_manifest_unchanged(
    tmp_path: Path,
) -> None:
    """L'egalite des trois champs est la **confirmation de bout en bout** de la
    chaine impression -> QR -> scan -> manifest: aucun constat, et un rescan ne
    change pas un octet."""
    project_dir = tmp_path / "projet"
    write_manifest(project_dir, _existing_with_printed_identifiers())

    first = scan_once(project_dir, two_pages())
    after_first = (project_dir / MANIFEST_FILENAME).read_bytes()
    second = scan_once(project_dir, two_pages(), overwrite=True)

    assert first.findings == second.findings
    assert (project_dir / MANIFEST_FILENAME).read_bytes() == after_first


def test_a_lot_attached_to_another_rush_is_refused(tmp_path: Path) -> None:
    """Le meme identifiant de lot pointant sur deux rushs rend le projet aval
    indechiffrable, et l'ecrire est irrattrapable."""
    project_dir = tmp_path / "projet"
    existing = rich_extraction_manifest()
    lot_of(existing)["rush_id"] = "rush-999"
    existing["rushes"].append({"rush_id": "rush-999"})
    path = write_manifest(project_dir, existing)
    before = path.read_bytes()

    with pytest.raises(sm.ScanManifestConflictError, match="rush-999"):
        scan_once(project_dir, two_pages())

    assert path.read_bytes() == before


def test_a_diverging_page_count_is_refused(tmp_path: Path) -> None:
    """Deux tirages melanges: la passe anterieure declarait un autre nombre de
    pages pour ce lot."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    scan_once(project_dir, two_pages())
    path = project_dir / MANIFEST_FILENAME
    before = path.read_bytes()

    with pytest.raises(sm.ScanManifestConflictError, match="page_count"):
        scan_once(
            project_dir,
            [make_payload(page_index=0, page_count=3, slot_count=2)],
            overwrite=True,
        )

    assert path.read_bytes() == before


def test_a_report_describing_another_lot_than_the_payloads_is_refused(
    tmp_path: Path,
) -> None:
    """Les deux entrees d'une meme passe doivent decrire le meme lot, sinon le
    manifest declarerait le dossier de sortie d'un lot sous l'identite d'un
    autre."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    other = two_pages(rush_id="rush-002", fps_target=8.0)
    report = write_report(project_dir, [scanned_page(p) for p in other])

    with pytest.raises(sm.ScanManifestConflictError, match="rush-002"):
        sm.persist_scan(project_dir, make_record(two_pages(), report))


def test_a_conflicting_project_id_is_still_refused_by_the_reused_guard(
    tmp_path: Path,
) -> None:
    """Les gardes existantes de la reconstruction ne sont pas contournees."""
    project_dir = tmp_path / "projet"
    existing = rich_extraction_manifest(project_id="autre-projet")
    write_manifest(project_dir, existing)

    with pytest.raises(ReconstructionError, match="project_id"):
        scan_once(project_dir, two_pages())


# --------------------------------------------------------------------------
# AC 6 / AC 7 -- completude declaree, cardinaux du lot, marquage synthetique
# --------------------------------------------------------------------------


def test_a_partial_lot_is_written_and_declared_partial(tmp_path: Path) -> None:
    """Il est normal qu'une page manque a la premiere passe: le lot est ecrit
    et declare partiel, jamais refuse en bloc ni declare complet."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    persisted = scan_once(project_dir, [make_payload(page_index=0)])

    section = persisted.manifest["reconstruction"]
    assert section["status"] == "partial"
    assert section["missing_pages"] == [1]
    assert persisted.synthetic_frame_count == 0
    assert not persisted.lot_complete


def test_a_missing_page_produces_no_synthetic_frame_and_stays_a_hole(
    tmp_path: Path,
) -> None:
    """Les deux natures de manque restent nommees separement et ne sont jamais
    fondues en un seul compteur."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    persisted = scan_once(project_dir, [make_payload(page_index=0)])

    assert persisted.manifest["reconstruction"]["missing_pages"] == [1]
    assert lot_of(persisted.manifest)["synthetic_frame_count"] == 0


def test_a_lot_with_no_missing_page_but_one_mire_is_never_complete(
    tmp_path: Path,
) -> None:
    """Le seul cas ou `missing_pages` vide ne suffit pas: la page est
    **presente**, sa geometrie a echoue, le fichier existe et l'image du film
    non (EPIC5-ARB-8)."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    persisted = scan_once(
        project_dir, two_pages(), failures={1: "page_detection_failed"}
    )

    section = persisted.manifest["reconstruction"]
    assert "missing_pages" not in section
    assert section["status"] == "partial"
    assert lot_of(persisted.manifest)["synthetic_frame_count"] == 2
    assert not persisted.lot_complete
    assert sm.SCAN_SYNTHETIC_FRAMES_PRESENT in persisted.findings


def test_the_two_cardinals_sum_to_the_observed_file_count(tmp_path: Path) -> None:
    """Regle de cumul d'EPIC5-ARB-32: le total est `observed_frame_count`, le
    seul cardinal du rapport de 5.6 qui decrive le dossier entier."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    payloads = two_pages()
    pages = [
        scanned_page(payloads[0]),
        scanned_page(payloads[1], failure="frame_crop_failed"),
    ]
    report = write_report(project_dir, pages)
    persisted = sm.persist_scan(project_dir, make_record(payloads, report))

    lot = lot_of(persisted.manifest)
    assert (
        lot["reconstructed_frame_count"] + lot["synthetic_frame_count"]
        == report.observed_frame_count
    )
    assert lot["reconstructed_frame_count"] == 2
    assert lot["synthetic_frame_count"] == 2


def test_a_synthetic_frame_never_counts_as_a_reconstructed_one(tmp_path: Path) -> None:
    """Une mire n'atteste aucun contenu de film: un cardinal unique de fichiers
    ecrits declarerait le lot complet (piege 9)."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    persisted = scan_once(
        project_dir, two_pages(), failures={0: "page_detection_failed"}
    )

    assert persisted.reconstructed_frame_count == 2
    assert persisted.synthetic_frame_count == 2
    assert persisted.expected_frame_count == 4


def test_no_complete_boolean_is_added_to_the_lot(tmp_path: Path) -> None:
    """La completude du lot se lit des deux cardinaux et de
    `expected_frame_count`: un troisieme porteur de la meme verite est une
    occasion de divergence."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    persisted = scan_once(project_dir, two_pages())

    lot = lot_of(persisted.manifest)
    assert "complete" not in lot
    assert lot["reconstructed_frame_count"] == lot["expected_frame_count"]
    assert lot["synthetic_frame_count"] == 0
    assert persisted.lot_complete


def test_every_slot_of_the_scan_chain_carries_an_explicit_synthetic_flag(
    tmp_path: Path,
) -> None:
    """`synthetic` est **toujours** present, y compris a `false`: un champ
    absent se relit « vraie frame »."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    persisted = scan_once(
        project_dir, two_pages(), failures={1: "page_detection_failed"}
    )

    slots = persisted.manifest["reconstruction"]["slots"]
    assert [slot["slot_index"] for slot in slots] == [0, 1, 2, 3]
    assert [slot["synthetic"] for slot in slots] == [False, False, True, True]
    for slot in slots:
        if slot["synthetic"]:
            assert slot["synthetic_reason"] == "page_detection_failed"
        else:
            assert "synthetic_reason" not in slot


def test_the_synthetic_reason_comes_from_the_closed_vocabulary_of_story_5_6(
    tmp_path: Path,
) -> None:
    """Jamais une chaine libre, jamais `null`."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    persisted = scan_once(project_dir, two_pages(), failures={1: "frame_crop_failed"})

    reasons = {
        slot["synthetic_reason"]
        for slot in persisted.manifest["reconstruction"]["slots"]
        if slot["synthetic"]
    }
    assert reasons == {"frame_crop_failed"}
    assert reasons <= set(sof.SYNTHETIC_FRAME_REASONS)


def test_the_reconstruct_project_subcommand_writes_no_synthetic_field() -> None:
    """Elle n'ecrit aucune frame et ne peut donc rien savoir de leur nature."""
    manifest = reconstruct_project_manifest([make_payload(page_index=0, page_count=1)])

    assert manifest["reconstruction"]["slots"] == [
        {"slot_index": 0, "frame_timecode": "00:00:00:00"},
        {"slot_index": 1, "frame_timecode": "00:00:01:00"},
    ]


def test_a_complementary_pass_does_not_unlearn_the_mires_of_the_first(
    tmp_path: Path,
) -> None:
    """Le cumul decrit le **lot**, pas la passe: une seconde passe qui remplit
    les trous de la premiere ne fait pas disparaitre ses mires."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    payloads = two_pages(page_count=3, slot_count=2)
    third = make_payload(page_index=2, page_count=3, slot_count=2)

    first = scan_once(project_dir, payloads, failures={1: "page_detection_failed"})
    assert first.synthetic_frame_count == 2

    second = scan_once(project_dir, [third])

    lot = lot_of(second.manifest)
    assert lot["synthetic_frame_count"] == 2, "les mires de la premiere passe"
    assert lot["reconstructed_frame_count"] == 4
    assert second.manifest["reconstruction"]["status"] == "partial"


# --------------------------------------------------------------------------
# AC 10 -- rescan: idempotent, ou refuse, jamais destructeur
# --------------------------------------------------------------------------


def test_an_identical_rescan_is_idempotent_byte_for_byte(tmp_path: Path) -> None:
    """`_serialize` trie ses cles: l'idempotence est verifiable octet a octet,
    et aucune horodate n'entre au manifest par ce chemin."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    scan_once(project_dir, two_pages())
    path = project_dir / MANIFEST_FILENAME
    before = path.read_bytes()

    scan_once(project_dir, two_pages(), overwrite=True)

    assert path.read_bytes() == before


def test_replacing_a_mire_by_a_real_frame_is_a_gain_and_needs_no_manifest_flag(
    tmp_path: Path,
) -> None:
    """Asymetrie tranchee par l'AC 10: le gain se fait, les deux cardinaux sont
    recalcules, aucun `--overwrite` n'est requis cote manifest."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    payloads = two_pages()
    first = scan_once(project_dir, payloads, failures={1: "page_detection_failed"})
    assert first.synthetic_frame_count == 2

    second = scan_once(project_dir, payloads, overwrite=True)

    assert second.synthetic_frame_count == 0
    assert second.reconstructed_frame_count == 4
    assert second.lot_complete
    assert sm.SCAN_SYNTHETIC_REPLACED_BY_REAL in second.findings
    assert [
        slot["synthetic"] for slot in second.manifest["reconstruction"]["slots"]
    ] == [False, False, False, False]


def test_a_real_frame_becoming_synthetic_is_refused_before_any_frame_is_written(
    tmp_path: Path,
) -> None:
    """EPIC5-ARB-34, clause 2: la perte se refuse **avant** l'ecriture.

    Le defaut mesure en revue: le refus arrivait apres que 5.6 avait ecrase les
    frames legitimes, et il annoncait « aucune ecriture n'a eu lieu ». Le
    manifest etait bien intact; les images, non. Le test verrouille donc les
    **octets des frames**, pas seulement ceux du manifest -- c'est exactement
    ce que l'ancien test ne regardait pas."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    payloads = two_pages()
    scan_once(project_dir, payloads)
    path = project_dir / MANIFEST_FILENAME
    before = path.read_bytes()
    frames_before = output_frames_digest(project_dir)

    with pytest.raises(sm.ScanFrameRegressionError) as excinfo:
        scan_once(project_dir, payloads, failures={1: "page_detection_failed"})

    message = str(excinfo.value)
    assert "scan_rush-001_5_00-00-02-00.tiff" in message
    assert "avant" in message
    assert "--overwrite" in message
    assert path.read_bytes() == before
    assert output_frames_digest(project_dir) == frames_before


def test_a_real_frame_becoming_synthetic_is_accepted_with_overwrite_and_named(
    tmp_path: Path,
) -> None:
    """Assumee explicitement, la perte s'ecrit -- et elle est **nommee au
    rapport** (EPIC5-ARB-34, clause 2), jamais silencieuse. Le manifest, lui,
    ne refuse plus rien a ce stade: les mires sont deja sur le disque, et un
    manifest qui refuserait de les enregistrer continuerait de declarer reelles
    des images qui n'existent plus (clause 3)."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    payloads = two_pages()
    scan_once(project_dir, payloads)

    persisted = scan_once(
        project_dir,
        payloads,
        failures={1: "page_detection_failed"},
        overwrite=True,
    )

    assert persisted.synthetic_frame_count == 2
    assert persisted.reconstructed_frame_count == 2
    assert persisted.manifest["reconstruction"]["status"] == "partial"
    assert sm.SCAN_REAL_FRAMES_DEGRADED in persisted.findings


def test_a_mire_written_over_a_mire_is_not_a_degradation(tmp_path: Path) -> None:
    """Le refus prealable a trois conditions cumulees, et c'est ce qui
    l'empeche d'etre du bruit: une mire posee sur une mire ne detruit rien."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    payloads = two_pages()
    scan_once(project_dir, payloads, failures={1: "page_detection_failed"})

    persisted = scan_once(
        project_dir, payloads, failures={1: "page_detection_failed"}, overwrite=True
    )

    assert sm.SCAN_REAL_FRAMES_DEGRADED not in persisted.findings


def test_a_mire_written_where_nothing_exists_is_not_a_degradation(
    tmp_path: Path,
) -> None:
    """Troisieme condition: le fichier doit **exister**. Sur un premier scan il
    n'y a rien a detruire, et le refus prealable ne se declenche pas."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()

    persisted = scan_once(
        project_dir, two_pages(), failures={1: "page_detection_failed"}
    )

    assert persisted.synthetic_frame_count == 2
    assert sm.SCAN_REAL_FRAMES_DEGRADED not in persisted.findings


# --------------------------------------------------------------------------
# EPIC5-ARB-33 -- la nature d'une frame se cumule par ensemble d'identites
# --------------------------------------------------------------------------


def test_the_two_cardinals_are_derived_from_the_registry_at_a_single_place(
    tmp_path: Path,
) -> None:
    """Invariant de la redondance assumee (EPIC5-ARB-33): `synthetic_frame_count`
    vaut **exactement** `len(synthetic_frames)`, et le registre est trie.

    Deux porteurs d'une meme verite est une occasion de divergence; la
    contrepartie exigee par l'arbitrage est ce test, plus le fait que le
    cardinal soit calcule en un seul endroit."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    persisted = scan_once(
        project_dir, two_pages(), failures={1: "page_detection_failed"}
    )

    lot = lot_of(persisted.manifest)
    assert lot["synthetic_frames"] == [
        "scan_rush-001_5_00-00-02-00.tiff",
        "scan_rush-001_5_00-00-03-00.tiff",
    ]
    assert lot["synthetic_frame_count"] == len(lot["synthetic_frames"])
    assert lot["synthetic_frames"] == sorted(lot["synthetic_frames"])
    assert persisted.synthetic_frame_count == len(lot["synthetic_frames"])
    assert (
        lot["reconstructed_frame_count"] + lot["synthetic_frame_count"]
        == len(list((project_dir / lot["output_frames_dir"]).iterdir()))
    )


def test_the_registry_names_the_files_the_folder_really_carries(
    tmp_path: Path,
) -> None:
    """Des **noms de fichiers**, pas des index de slots: le registre doit se
    confronter au dossier sans passer par une seconde recette de nommage."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    persisted = scan_once(
        project_dir, two_pages(), failures={0: "frame_crop_failed"}
    )

    lot = lot_of(persisted.manifest)
    on_disk = {path.name for path in (project_dir / lot["output_frames_dir"]).iterdir()}
    assert set(lot["synthetic_frames"]) <= on_disk


def test_rescanning_a_lot_carrying_mires_changes_nothing_byte_for_byte(
    tmp_path: Path,
) -> None:
    """Le defaut central d'EPIC5-ARB-33, reproduit a l'execution avant
    correction: relancer `scan --overwrite` sans rien changer sur un lot a
    2 reelles / 2 mires le faisait passer a **0 / 4**, en code `0` et avec le
    mot « succes ». Une addition ne sait pas qu'une mire reecrite a l'identique
    est *la meme* mire; un ensemble, si."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    payloads = two_pages()
    first = scan_once(project_dir, payloads, failures={1: "page_detection_failed"})
    assert (first.reconstructed_frame_count, first.synthetic_frame_count) == (2, 2)
    path = project_dir / MANIFEST_FILENAME
    before = path.read_bytes()

    second = scan_once(
        project_dir, payloads, failures={1: "page_detection_failed"}, overwrite=True
    )
    third = scan_once(
        project_dir, payloads, failures={1: "page_detection_failed"}, overwrite=True
    )

    assert (second.reconstructed_frame_count, second.synthetic_frame_count) == (2, 2)
    assert (third.reconstructed_frame_count, third.synthetic_frame_count) == (2, 2)
    assert path.read_bytes() == before


def test_a_mire_erased_from_the_folder_is_credited_when_the_real_frame_returns(
    tmp_path: Path,
) -> None:
    """Second mecanisme mesure: `replaced` exigeait que le fichier ait ete
    **ecrase**. Un fichier efface a la main du dossier n'est pas ecrase, donc la
    passe qui le reecrit en vraie frame ne creditait rien, et le lot restait
    `0 / 2` pour toujours -- avec un constat affirmant que des mires sont
    presentes alors qu'il n'y en avait plus aucune."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    payloads = [make_payload(page_index=0, page_count=1)]
    first = scan_once(project_dir, payloads, failures={0: "page_detection_failed"})
    assert first.synthetic_frame_count == 2

    output_dir = project_dir / lot_of(first.manifest)["output_frames_dir"]
    for frame in output_dir.iterdir():
        frame.unlink()

    second = scan_once(project_dir, payloads)

    assert second.synthetic_frame_count == 0
    assert second.reconstructed_frame_count == 2
    assert second.lot_complete
    assert sm.SCAN_SYNTHETIC_FRAMES_PRESENT not in second.findings
    assert lot_of(second.manifest)["synthetic_frames"] == []


def test_a_page_by_page_scan_converges_on_a_complete_lot(tmp_path: Path) -> None:
    """Troisieme mecanisme mesure, et le plus couteux: la nature anterieure se
    lisait dans `reconstruction.slots[]`, section reecrite en entier a chaque
    passe avec les seules pages de cette passe-la. Dans un scan page par page --
    le parcours que le module revendique --, le lot ne pouvait donc **jamais**
    redevenir complet, alors que ses six fichiers etaient reels."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    pages = [make_payload(page_index=index, page_count=3) for index in range(3)]

    first = scan_once(project_dir, [pages[0]], failures={0: "page_detection_failed"})
    assert (first.reconstructed_frame_count, first.synthetic_frame_count) == (0, 2)
    scan_once(project_dir, [pages[1]])
    scan_once(project_dir, [pages[2]])

    last = scan_once(project_dir, [pages[0]], overwrite=True)

    assert (last.reconstructed_frame_count, last.synthetic_frame_count) == (6, 0)
    assert last.lot_complete
    assert sm.SCAN_SYNTHETIC_REPLACED_BY_REAL in last.findings
    assert lot_of(last.manifest)["synthetic_frames"] == []


def test_the_mire_registry_survives_the_scan_of_another_lot(tmp_path: Path) -> None:
    """La clause 4 d'EPIC5-ARB-32 est **supprimee et non remplacee**
    (EPIC5-ARB-33, clause 3): l'indetermination n'existait que parce que le
    registre etait volatile. Sur un registre porte par le lot, `S_prec` est
    toujours disponible et le cumul toujours exact -- y compris quand un autre
    lot du meme rush a ete scanne entre les deux passes, ce qui est le cas
    nominal multi-cadences de la v2.1."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    payloads = two_pages()
    scan_once(project_dir, payloads, failures={1: "page_detection_failed"})

    other = two_pages(fps_target=8.0)
    between = scan_once(project_dir, other)
    assert between.manifest["reconstruction"]["lot_id"] != LOT, "section volatile"

    persisted = scan_once(project_dir, payloads, overwrite=True)

    assert persisted.synthetic_frame_count == 0
    assert persisted.reconstructed_frame_count == 4
    assert persisted.lot_complete
    assert sm.SCAN_SYNTHETIC_REPLACED_BY_REAL in persisted.findings
    assert lot_of(persisted.manifest)["synthetic_frames"] == []


def test_the_registry_prunes_a_mire_that_left_the_folder(tmp_path: Path) -> None:
    """L'intersection avec les fichiers presents elague les mires disparues hors
    de l'outil: le registre decrit le **dossier**, pas l'histoire des passes."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    payloads = two_pages(page_count=3)
    third = make_payload(page_index=2, page_count=3)
    first = scan_once(project_dir, payloads, failures={1: "page_detection_failed"})
    assert first.synthetic_frame_count == 2

    output_dir = project_dir / lot_of(first.manifest)["output_frames_dir"]
    (output_dir / "scan_rush-001_5_00-00-02-00.tiff").unlink()

    second = scan_once(project_dir, [third])

    lot = lot_of(second.manifest)
    assert lot["synthetic_frames"] == ["scan_rush-001_5_00-00-03-00.tiff"]
    assert lot["synthetic_frame_count"] == 1
    assert lot["reconstructed_frame_count"] == 4


def test_an_inconsistent_report_cannot_produce_two_cardinals(tmp_path: Path) -> None:
    """L'invariant `len(presentes) == observed_frame_count` est **verifie**, pas
    supppose: le rapport de 5.6 est lu en typage structurel, et deux cardinaux
    derives d'un dossier decrit de deux facons ne decrivent aucun dossier."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    payloads = two_pages()
    report = write_report(project_dir, [scanned_page(p) for p in payloads])

    with pytest.raises(sm.ScanPersistenceError, match="observed_frame_count"):
        sm.build_scan_manifest(
            None,
            make_record(payloads, dataclasses.replace(report, observed_frame_count=99)),
        )


# --------------------------------------------------------------------------
# AC 6 -- `reconstruction.origin`, et le sens de son absence
# --------------------------------------------------------------------------


def test_origin_is_scan_for_the_scan_chain(tmp_path: Path) -> None:
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    persisted = scan_once(project_dir, two_pages())

    assert persisted.manifest["reconstruction"]["origin"] == "scan"


def test_origin_is_payloads_for_the_reconstruct_project_subcommand() -> None:
    manifest = reconstruct_project_manifest([make_payload(page_index=0, page_count=1)])

    assert manifest["reconstruction"]["origin"] == "payloads"


def test_origin_is_absent_from_an_extraction_manifest() -> None:
    """Son absence n'est jamais « inconnu »: elle signifie « manifest
    d'origine », l'extraction ecrivant une section vide."""
    manifest = rich_extraction_manifest()

    assert "origin" not in manifest["reconstruction"]


def test_the_payloads_to_scan_transition_is_a_licit_enrichment(tmp_path: Path) -> None:
    """Projet recree depuis des payloads, puis planches scannees: l'origine
    passe a `scan`, et l'etat de lot, lui, ne redescend pas."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    payloads = two_pages()
    reconstructed = reconstruct_project_manifest(payloads)
    write_manifest(project_dir, reconstructed)
    assert reconstructed["reconstruction"]["origin"] == "payloads"

    persisted = scan_once(project_dir, payloads)

    assert persisted.manifest["reconstruction"]["origin"] == "scan"
    assert lot_of(persisted.manifest)["state"] == "reconstruction"
    assert sm.SCAN_STATE_CONSERVED in persisted.findings


# --------------------------------------------------------------------------
# AC 7 -- provenance de scan et resultats de calibration
# --------------------------------------------------------------------------


def test_the_scan_provenance_is_declared_page_by_page(tmp_path: Path) -> None:
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    persisted = scan_once(project_dir, two_pages())

    provenance_doc = persisted.manifest["reconstruction"]["scan"]
    assert provenance_doc["scan_dpi"] == 600
    assert provenance_doc["ingest_slug"] == "lot-a"
    assert [page["page_index"] for page in provenance_doc["pages"]] == [0, 1]
    assert {page["qr_status"] for page in provenance_doc["pages"]} == {"decoded"}
    assert {page["homography_status"] for page in provenance_doc["pages"]} == {
        "resolved"
    }


def _iter_keys_and_values(node, prefix: str = ""):
    if isinstance(node, dict):
        for key, value in node.items():
            yield f"{prefix}.{key}", key, value
            yield from _iter_keys_and_values(value, f"{prefix}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _iter_keys_and_values(value, f"{prefix}[{index}]")


def test_the_scan_provenance_carries_no_timestamp(tmp_path: Path) -> None:
    """Une horodate rendrait deux passes identiques distinguables et fermerait
    la seule verification qui prouve qu'un rescan n'a rien detruit (AC 10).

    Le test d'origine ne connaissait que **trois noms litteraux**
    (`scanned_at`, `generated_at`, `timestamp`): un champ nomme `scan_date`,
    `date` ou `at` serait passe. Il est ici structurel -- parcours recursif de
    la section, motif de nom et motif de valeur --, donc capable d'echouer sur
    une horodate qu'on n'a pas pensee d'avance."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    persisted = scan_once(project_dir, two_pages())

    iso = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")
    dated_name = re.compile(r"(^|_)(at|date|time|timestamp|datetime|horodate)($|_)")
    for path, key, value in _iter_keys_and_values(
        persisted.manifest["reconstruction"], "reconstruction"
    ):
        assert not dated_name.search(key.lower()), f"nom d'horodate a {path}"
        if isinstance(value, str):
            assert not iso.search(value), f"horodate a {path}: {value!r}"


@pytest.mark.parametrize("qr_status", list(scan_detection.PAGE_QR_STATUSES))
def test_every_closed_qr_status_is_accepted_by_the_provenance(qr_status: str) -> None:
    """Le vocabulaire est celui de 5.2, importe: aucune valeur n'y est ajoutee
    ni retiree."""
    assert (
        sm.ScanPageProvenance(
            read_rank=0, status=scan_detection.PAGE_REFUSED, qr_status=qr_status
        ).qr_status
        == qr_status
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"read_rank": True, "status": "ok", "qr_status": "decoded"},
        {"read_rank": -1, "status": "ok", "qr_status": "decoded"},
        {"read_rank": 0, "status": "presque", "qr_status": "decoded"},
        {"read_rank": 0, "status": "ok", "qr_status": "lisible"},
        {"read_rank": 0, "status": "ok", "qr_status": "decoded", "page_index": True},
        {
            "read_rank": 0,
            "status": "ok",
            "qr_status": "decoded",
            "homography_status": "peut-etre",
        },
    ],
)
def test_the_provenance_refuses_what_is_outside_its_closed_vocabularies(kwargs) -> None:
    """Garde `bool`-avant-`int` comprise: `True` n'est pas un rang de lecture."""
    with pytest.raises(sm.ScanPersistenceError):
        sm.ScanPageProvenance(**kwargs)


@pytest.mark.parametrize(
    "status", [color_pipeline.NOT_APPLIED_STATUS, "failed", "applied"]
)
def test_the_calibration_status_is_transported_never_computed(
    tmp_path: Path, status: str
) -> None:
    """Le statut de **lot** est transporte, jamais calcule -- et il ne descend plus.

    Le test d'origine etait tautologique (il n'injectait que la valeur par defaut de la
    fabrique), et une valeur non nominale l'a rendu capable d'echouer. `EPIC5-ARB-69` en
    change le sujet: le statut transporte atteint le **lot** et le **projet**, et non
    plus les entrees de page. Une page pour laquelle rien n'a ete mesure se declare
    `not_applied`, ce que la seconde assertion epingle -- sans elle, l'arbitrage serait
    reversible sans qu'aucun test ne bronche.
    """
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    persisted = scan_once(
        project_dir, two_pages(), color_calibration_status=status
    )

    results = persisted.manifest["reconstruction"]["page_calibration_results"]
    assert [entry["page_index"] for entry in results] == [0, 1]
    assert {entry["status"] for entry in results} == {
        color_pipeline.NOT_APPLIED_STATUS}
    assert persisted.manifest["color"]["color_calibration_status"] == status
    lot = lot_of(persisted.manifest)
    if status == color_pipeline.NOT_APPLIED_STATUS:
        # Le lot ne gagne rien: c'est le filet de non-regression du chemin non corrige.
        assert "color_calibration_status" not in lot
    else:
        assert lot["color_calibration_status"] == status


def test_a_project_level_calibration_status_is_never_lowered_by_a_scan(
    tmp_path: Path,
) -> None:
    """`color.color_calibration_status` est de portee **projet** et la valeur
    transportee est celle d'une **passe**: l'ecrire par-dessus faisait retomber
    un projet declare `applied` a `not_applied`, en silence. Le scan connait
    strictement moins que le manifest d'origine (AC 4)."""
    project_dir = tmp_path / "projet"
    existing = rich_extraction_manifest()
    existing["color"]["color_calibration_status"] = "applied"
    write_manifest(project_dir, existing)

    persisted = scan_once(project_dir, two_pages())

    assert persisted.manifest["color"]["color_calibration_status"] == "applied"


def test_duplicate_payloads_do_not_duplicate_the_calibration_results(
    tmp_path: Path,
) -> None:
    """`reconstruct_project_manifest` dedoublonne explicitement par `page_index`
    (« identical duplicates are fine (idempotent rescans) ») et promet un
    manifest identique « regardless of order or exact duplicates ». Les
    resultats de calibration iteraient la liste **brute**, cassant cette
    promesse dans le meme document."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    payloads = two_pages()
    report = write_report(project_dir, [scanned_page(p) for p in payloads])

    merge = sm.build_scan_manifest(
        None, make_record([payloads[0], payloads[0], payloads[1]], report)
    )

    results = merge.manifest["reconstruction"]["page_calibration_results"]
    assert [entry["page_index"] for entry in results] == [0, 1]


def test_no_clipping_verdict_is_invented_before_it_has_been_measured(
    tmp_path: Path,
) -> None:
    """Ecrire `clipping: {detected: false}` sans avoir mesure dirait « aucun
    ecretage detecte » la ou la verite est « rien n'a ete mesure »."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    persisted = scan_once(project_dir, two_pages())

    for entry in persisted.manifest["reconstruction"]["page_calibration_results"]:
        assert set(entry) == {"page_index", "status"}


def test_a_page_whose_frames_are_all_mires_never_reads_applied(tmp_path: Path) -> None:
    """La mire n'est pas le contenu source et est achromatique par
    construction.

    Depuis `EPIC5-ARB-69` la garde se confronte au statut **de la page**, seul statut que
    cette page a produit: c'est donc un resultat de calibration `applied` pose sur la
    page en mires qui doit la declencher, et non le statut du lot. Confrontee au statut
    de lot, elle levait pour la panne d'une **autre** feuille -- voir le test du lot
    mixte ci-dessous, qui est le regime que ce refus faisait perdre.
    """
    project_dir = tmp_path / "projet"
    project_dir.mkdir()

    with pytest.raises(sm.ScanPersistenceError, match="applied"):
        scan_once(
            project_dir,
            two_pages(),
            failures={1: "page_detection_failed"},
            color_calibration_status="applied",
            page_calibrations=((1, calibration_result("applied")),),
        )
    assert not (project_dir / MANIFEST_FILENAME).exists()


def test_a_mixed_lot_keeps_its_manifest_and_declares_each_page_for_itself(
    tmp_path: Path,
) -> None:
    """Le lot **mixte**: une planche corrigee, une planche tombee en mires.

    C'est le regime que rien dans le depot ne produisait, et le bloquant qu'il cachait
    coutait le manifest du lot entier: la garde de coherence confrontait le statut de lot
    `applied` a une page dont **toutes** les frames etaient des mires, donc une seule
    feuille cornee dans un lot corrige faisait sortir la commande en echec **apres**
    l'ecriture des frames -- huit frames orphelines sur le disque, aucun document.

    La frontiere est exigee par `EPIC5-ARB-69`, et elle est ecrite ici avec deux pages
    **distinguables**: la page corrigee n'est pas celle qui echoue, et le test verifie
    l'appariement page par page plutot qu'un ensemble de statuts.
    """
    project_dir = tmp_path / "projet"
    project_dir.mkdir()

    persisted = scan_once(
        project_dir,
        two_pages(),
        failures={1: "page_detection_failed"},
        color_calibration_status="applied",
        page_calibrations=((0, calibration_result("applied")),),
    )

    assert (project_dir / MANIFEST_FILENAME).exists()
    results = persisted.manifest["reconstruction"]["page_calibration_results"]
    par_page = {entry["page_index"]: entry["status"] for entry in results}
    assert par_page == {0: "applied", 1: color_pipeline.NOT_APPLIED_STATUS}
    # Le lot, lui, porte bien ce que la passe a mesure sur lui.
    assert lot_of(persisted.manifest)["color_calibration_status"] == "applied"
    # Et la provenance ne descend que sur la page qui l'a produite: une entree sans
    # resultat reste a deux cles.
    assert set(results[1]) == {"page_index", "status"}
    assert "correction_source" in results[0]


@pytest.mark.parametrize("status", list(color_pipeline.CALIBRATION_STATUS_VALUES))
@pytest.mark.parametrize("detected", [True, False])
def test_the_four_status_times_clipping_combinations_are_representable(
    tmp_path: Path, status: str, detected: bool
) -> None:
    """Les deux verdicts sont **orthogonaux** (EPIC5-ARB-16): `applied` avec
    avertissement d'ecretage compris, et aucune combinaison n'est interdite."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    persisted = scan_once(project_dir, two_pages())
    document = json.loads(persisted.manifest_path.read_text(encoding="utf-8"))
    document["reconstruction"]["page_calibration_results"] = [
        {
            "page_index": 0,
            "status": status,
            "clipping": {
                "detected": detected,
                "axes": ["red"] if detected else [],
                "onset_step": "step-2" if detected else None,
            },
        }
    ]
    persisted.manifest_path.write_text(json.dumps(document), encoding="utf-8")

    assert validate_manifest(persisted.manifest_path) is not None


def test_a_calibration_status_outside_the_closed_vocabulary_is_refused(
    tmp_path: Path,
) -> None:
    """Un vocabulaire ferme non verrouille par le schema n'est pas ferme."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    persisted = scan_once(project_dir, two_pages())
    document = json.loads(persisted.manifest_path.read_text(encoding="utf-8"))
    document["reconstruction"]["page_calibration_results"][0]["status"] = "ecrete"
    persisted.manifest_path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ValidationError):
        validate_manifest(persisted.manifest_path)


# --------------------------------------------------------------------------
# AC 8 -- deux reconstructions independantes rendent les memes identifiants
# --------------------------------------------------------------------------


def test_two_independent_passes_in_a_different_page_order_are_identical(
    tmp_path: Path,
) -> None:
    """`build_lot_id` s'appuie sur `hashlib.sha256`, jamais sur le `hash()`
    randomise de Python, et la serialisation trie ses cles."""
    payloads = two_pages()
    forward = tmp_path / "avant"
    backward = tmp_path / "arriere"
    forward.mkdir()
    backward.mkdir()

    scan_once(forward, payloads)
    scan_once(backward, list(reversed(payloads)))

    assert (forward / MANIFEST_FILENAME).read_bytes() == (
        backward / MANIFEST_FILENAME
    ).read_bytes()


def test_the_lot_identifier_is_the_canonical_one(tmp_path: Path) -> None:
    """Aucun identifiant n'est fabrique a la main dans cette story."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    persisted = scan_once(project_dir, two_pages())

    assert persisted.lot_id == naming.build_lot_id(RUSH, FPS)


# --------------------------------------------------------------------------
# AC 9 -- aucun chemin absolu, aucune fuite de structure locale
# --------------------------------------------------------------------------


def test_no_absolute_path_reaches_the_written_manifest(tmp_path: Path) -> None:
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    persisted = scan_once(project_dir, two_pages())

    serialized = persisted.manifest_path.read_text(encoding="utf-8")
    assert str(tmp_path) not in serialized
    assert "\\\\" not in serialized
    validate_manifest(persisted.manifest_path)


@pytest.mark.parametrize(
    "output_dir",
    [
        f"/absolu/{SCAN_FRAMES_DIRNAME}/lot",
        f"C:\\projets\\{SCAN_FRAMES_DIRNAME}\\lot",
        "\\\\serveur\\partage\\lot",
        f"../{SCAN_FRAMES_DIRNAME}/lot",
        "",
    ],
)
def test_a_non_portable_output_dir_is_refused_before_any_write(
    tmp_path: Path, output_dir: str
) -> None:
    """`_relative_posix` attrape aussi ce que le detecteur de chemins absolus
    laisse passer: les remontees `..` et un chemin vide."""
    import dataclasses

    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    payloads = two_pages()
    report = write_report(project_dir, [scanned_page(p) for p in payloads])
    tampered = dataclasses.replace(report, output_dir=output_dir)

    with pytest.raises(sm.ExtractionPersistenceError):
        sm.persist_scan(project_dir, make_record(payloads, tampered))
    assert not (project_dir / MANIFEST_FILENAME).exists()


def test_a_relative_windows_output_dir_is_normalised_not_written_verbatim(
    tmp_path: Path,
) -> None:
    """Un antislash **relatif** ne declenche aucune garde de chemin absolu et
    casserait pourtant la portabilite: la conversion a lieu avant toute
    serialisation, et le manifest ne porte jamais l'antislash."""
    import dataclasses

    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    payloads = two_pages()
    report = write_report(project_dir, [scanned_page(p) for p in payloads])
    tampered = dataclasses.replace(report, output_dir=f"{SCAN_FRAMES_DIRNAME}\\rush-001_5")

    persisted = sm.persist_scan(project_dir, make_record(payloads, tampered))

    assert lot_of(persisted.manifest)["output_frames_dir"] == f"{SCAN_FRAMES_DIRNAME}/rush-001_5"
    assert "\\" not in persisted.manifest_path.read_text(encoding="utf-8")


def test_unicode_spaces_and_long_names_survive_the_round_trip(tmp_path: Path) -> None:
    """`_serialize` utilise `ensure_ascii=False`: les valeurs texte portent de
    l'Unicode, et le TEST_PLAN l'exige."""
    project_dir = tmp_path / "projet"
    existing = rich_extraction_manifest()
    existing["artifacts"] = {
        "frames_dir": "frames/rushes tournés été 2026",
        "outputs_dir": "sorties/" + "e" * 180,
    }
    write_manifest(project_dir, existing)

    persisted = scan_once(project_dir, two_pages())

    assert persisted.manifest["artifacts"]["frames_dir"] == "frames/rushes tournés été 2026"
    assert persisted.manifest["artifacts"]["outputs_dir"] == "sorties/" + "e" * 180
    reread = json.loads(persisted.manifest_path.read_text(encoding="utf-8"))
    assert reread["artifacts"] == persisted.manifest["artifacts"]


def test_a_lot_carrying_many_mires_keeps_its_registry_sorted(tmp_path: Path) -> None:
    """Le registre est **trie**, et c'est ce qui rend l'idempotence octet a octet
    verifiable. Un ensemble Python n'a pas d'ordre, et son ordre d'iteration
    depend de la graine de hachage du processus: sur deux elements, un registre
    non trie tombe juste une fois sur deux et le test devient une loterie. Six
    mires rendent la coincidence invraisemblable."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    payloads = [make_payload(page_index=index, page_count=4) for index in range(4)]

    persisted = scan_once(
        project_dir,
        payloads,
        failures={index: "page_detection_failed" for index in (1, 2, 3)},
    )

    registry = lot_of(persisted.manifest)["synthetic_frames"]
    assert len(registry) == 6
    assert registry == sorted(registry)
    assert persisted.synthetic_frame_count == 6


def test_a_frame_counted_as_written_but_absent_from_the_folder_is_not_present(
    tmp_path: Path,
) -> None:
    """`presentes` retranche les frames que le rapport compte comme ecrites mais
    que le dossier ne porte pas -- `missing_frames`, dont 5.6 tire son
    avertissement `EXPECTED_FRAME_FILE_MISSING`. Le cas ne se provoque pas de
    bout en bout (il suppose qu'un fichier disparaisse entre l'ecriture et la
    verification), mais le champ a un producteur reel et le rapport est lu en
    typage structurel: c'est exactement la ou un rapport se fabrique."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    payloads = two_pages()
    report = write_report(project_dir, [scanned_page(p) for p in payloads])
    disparue = report.frames[0].filename
    (project_dir / report.output_dir / disparue).unlink()

    merge = sm.build_scan_manifest(
        None,
        make_record(
            payloads,
            dataclasses.replace(
                report, missing_frames=(disparue,), observed_frame_count=3
            ),
        ),
    )

    lot = lot_of(merge.manifest)
    assert lot["reconstructed_frame_count"] == 3
    assert lot["synthetic_frame_count"] == 0


def _pass_without_any_writable_shape(
    project_dir: Path, payload: dict
) -> sm.PersistedScan:
    """Une passe ou 5.6 n'ecrit **aucune** frame.

    Le cas est etroit et il est reel: une page en echec sans plan de decoupe, et
    aucune page reussie dans la passe pour donner la forme de la mire. 5.6 sort
    alors `SYNTHETIC_FRAME_SHAPE_INDETERMINABLE` et n'ecrit rien -- si bien que
    les slots de la passe sont dans la section `reconstruction` **sans** frame
    correspondante. C'est le seul chemin ou la nature d'un slot ne peut pas
    venir de la passe courante, et il n'etait couvert par aucun test.
    """
    report = write_report(
        project_dir,
        [sof.ScannedPage(payload=payload, failure="page_detection_failed")],
    )
    assert report.frames == (), "la passe ne doit ecrire aucune frame"
    return sm.persist_scan(project_dir, make_record([payload], report))


def test_a_slot_the_pass_did_not_write_keeps_its_nature_and_its_reason(
    tmp_path: Path,
) -> None:
    """La nature du slot se lit dans le registre du lot, son motif dans le
    document precedent. Sans la premiere lecture, le detail par frame et les deux
    cardinaux se contredisent dans le meme document -- `synthetic: false` sur des
    slots que `synthetic_frame_count` compte comme mires; sans la seconde, le
    marquage perd le motif que l'AC 7 exige present si et seulement si
    `synthetic` vaut `true`."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    payloads = two_pages()
    first = scan_once(project_dir, payloads, failures={1: "page_detection_failed"})
    assert first.synthetic_frame_count == 2

    second = _pass_without_any_writable_shape(project_dir, payloads[1])

    slots = second.manifest["reconstruction"]["slots"]
    assert [slot["slot_index"] for slot in slots] == [2, 3]
    assert [slot["synthetic"] for slot in slots] == [True, True]
    assert {slot["synthetic_reason"] for slot in slots} == {"page_detection_failed"}
    assert second.synthetic_frame_count == 2
    assert second.reconstructed_frame_count == 2


def test_an_invalid_synthetic_reason_read_from_the_manifest_stays_in_the_hierarchy(
    tmp_path: Path,
) -> None:
    """Le motif est relu du **document precedent**, donc editable a la main, et
    sa garde de vocabulaire leve un `ValueError` **nu** -- hors de la hierarchie
    que la CLI capture, alors que le module promet a celle-ci un seul `except` a
    tenir. L'operateur recevait une trace Python."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    payloads = two_pages()
    scan_once(project_dir, payloads, failures={1: "page_detection_failed"})
    path = project_dir / MANIFEST_FILENAME
    document = json.loads(path.read_text(encoding="utf-8"))
    for slot in document["reconstruction"]["slots"]:
        if slot["synthetic"]:
            slot["synthetic_reason"] = "motif_bricole"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(sm.ScanPersistenceError, match="motif_bricole"):
        _pass_without_any_writable_shape(project_dir, payloads[1])


# --------------------------------------------------------------------------
# EPIC5-ARB-34 -- le refus prealable, et ce qu'il juge avant d'ecrire
# --------------------------------------------------------------------------


def test_a_stale_plate_is_refused_before_a_single_frame_is_touched(
    tmp_path: Path,
) -> None:
    """Le defaut le plus grave de la revue, reproduit ici a l'envers: sur une
    planche perimee du **meme** lot, les noms de fichiers sont identiques par
    construction, si bien que `--overwrite` faisait detruire les frames
    legitimes **puis** refuser, en annoncant « aucune ecriture n'a eu lieu ».

    Le manifest etait intact; les images, non. Le test regarde donc les octets
    des frames."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    scan_once(project_dir, two_pages())
    frames_before = output_frames_digest(project_dir)
    manifest_before = (project_dir / MANIFEST_FILENAME).read_bytes()
    assert frames_before, "la premiere passe doit avoir ecrit des frames"

    with pytest.raises(sm.ScanManifestConflictError):
        scan_once(
            project_dir,
            two_pages(template_id="tpl-a4-portrait-6f-v1"),
            overwrite=True,
        )

    assert output_frames_digest(project_dir) == frames_before
    assert (project_dir / MANIFEST_FILENAME).read_bytes() == manifest_before


def test_the_scan_chain_learns_the_three_printed_identifiers_it_does_not_carry(
    tmp_path: Path,
) -> None:
    """Repercussion de l'AC 5 (EPIC5-ARB-34): un projet ne des planches seules
    -- le cas central de cette story -- ne porte aucun des trois identifiants
    d'impression sur `lots[]`, et une garde qui saute les champs absents ne
    garde rien. Le scan les **apprend**; ecrire une valeur qu'aucun manifest ne
    portait n'est pas un ecrasement."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    persisted = scan_once(project_dir, two_pages())

    lot = lot_of(persisted.manifest)
    assert lot["template_id"] == TPL
    assert lot["patch_preset_id"] == PATCH_PRESET
    assert lot["gamut_map_id"] == payload_io.GAMUT_MAP_IDENTITY


def test_a_second_printing_of_a_lot_born_from_plates_alone_is_refused(
    tmp_path: Path,
) -> None:
    """Et c'est tout l'objet de l'apprentissage: sans lui, deux tirages
    successifs du meme rush passaient l'un pour l'autre sur un projet ne du
    scan, en fusion silencieuse, l'unique trace du premier gabarit etant
    ecrasee. Le seul garde-fou restant etait `rush_id`, qui ne distingue pas
    deux tirages du meme rush."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    scan_once(project_dir, two_pages())
    frames_before = output_frames_digest(project_dir)

    with pytest.raises(sm.ScanManifestConflictError, match="patch_preset_id"):
        scan_once(
            project_dir,
            two_pages(patch_preset_id="patch-values-1"),
            overwrite=True,
        )

    assert output_frames_digest(project_dir) == frames_before
    assert lot_of(
        json.loads((project_dir / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    )["patch_preset_id"] == PATCH_PRESET


def test_a_conflicting_project_id_is_refused_before_the_frames_are_written(
    tmp_path: Path,
) -> None:
    """Les gardes **reutilisees** de la reconstruction passent elles aussi
    avant l'ecriture: tout ce qui peut se juger avant se juge avant.

    Le projet ne porte aucune frame, et c'est delibere: sur un projet deja
    scanne, une passe refusee **apres** l'ecriture reecrit des frames au contenu
    identique. Ici, le dossier de sortie ne doit pas exister du tout."""
    project_dir = tmp_path / "projet"
    write_manifest(project_dir, rich_extraction_manifest())

    with pytest.raises(ReconstructionError, match="project_id"):
        scan_once(project_dir, two_pages(project_id="proj-002"))

    assert not (project_dir / SCAN_FRAMES_DIRNAME).exists()


def test_the_page_count_of_another_lot_is_never_confronted(tmp_path: Path) -> None:
    """La section `reconstruction` est unique par document: elle peut decrire un
    **autre** lot scanne entre-temps, et confronter deux lots l'un a l'autre
    inventerait un conflit sur un parcours nominal -- deux lots d'un meme projet
    n'ont aucune raison d'avoir le meme nombre de planches."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    petit = two_pages()
    grand = [
        make_payload(page_index=index, page_count=3, fps_target=8.0)
        for index in range(3)
    ]
    scan_once(project_dir, petit)
    between = scan_once(project_dir, grand)
    assert between.manifest["reconstruction"]["page_count"] == 3

    persisted = scan_once(project_dir, petit, overwrite=True)

    assert persisted.manifest["reconstruction"]["page_count"] == 2
    assert persisted.lot_complete


def test_a_lot_attached_to_another_rush_is_refused_before_any_write(
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "projet"
    existing = rich_extraction_manifest()
    lot_of(existing)["rush_id"] = "rush-999"
    existing["rushes"].append({"rush_id": "rush-999"})
    write_manifest(project_dir, existing)

    with pytest.raises(sm.ScanManifestConflictError, match="rattachement"):
        scan_once(project_dir, two_pages())

    assert not (project_dir / SCAN_FRAMES_DIRNAME).exists()


def test_a_plain_rescan_of_a_lot_carrying_mires_is_refused_by_the_frame_writer(
    tmp_path: Path,
) -> None:
    """Le refus prealable a trois conditions **cumulees**: une mire posee sur une
    mire ne detruit rien, et le refus qui doit arriver est alors celui de 5.6 --
    « ce fichier existe » --, pas celui de la regression. Confondre les deux
    ferait dire a la commande qu'elle va detruire l'image du film la ou elle ne
    remplacerait qu'un bouche-trou par un bouche-trou identique."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    payloads = two_pages()
    scan_once(project_dir, payloads, failures={1: "page_detection_failed"})

    with pytest.raises(sof.ScanOutputError, match="existent deja"):
        scan_once(project_dir, payloads, failures={1: "page_detection_failed"})


def test_a_failed_page_whose_frames_do_not_exist_yet_is_not_a_degradation(
    tmp_path: Path,
) -> None:
    """La garde ne regarde que les fichiers des pages **en echec**. Etendre son
    regard aux pages reussies ferait refuser, sous le nom de « regression », une
    passe qui ne detruit aucune vraie frame -- et masquerait le refus qui doit
    reellement arriver, celui de 5.6 sur les fichiers deja ecrits."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    payloads = two_pages()
    scan_once(project_dir, [payloads[0]])

    with pytest.raises(sof.ScanOutputError, match="existent deja"):
        scan_once(project_dir, payloads, failures={1: "page_detection_failed"})

    # La garde, elle, laisse passer: aucun fichier de la page en echec n'existe.
    sm.check_scan_conflicts(
        project_dir, payloads, failed_page_indexes=(1,), overwrite=False
    )


def test_the_pre_write_guard_finds_the_output_dir_of_a_shortened_lot_id(
    tmp_path: Path,
) -> None:
    """Le dossier de sortie se derive par la fonction de 5.6, jamais du `lot_id`.
    Les deux coincident sur un rush au nom court -- ce que toutes les fixtures du
    fichier emploient -- et **divergent** des que `build_lot_id` raccourcit
    l'identifiant: le dossier, lui, porte le nom entier. Une derivation a la main
    chercherait au mauvais endroit, ne verrait aucune frame a proteger, et
    laisserait la degradation passer."""
    long_rush = "rush-001-identifiant-de-rush-vraiment-tres-tres-long-pour-depasser"
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    payloads = [
        make_payload(page_index=index, page_count=2, rush_id=long_rush)
        for index in range(2)
    ]
    first = scan_once(project_dir, payloads)
    lot_id = payloads[0]["lot_id"]
    output_dir = lot_of(first.manifest, lot_id)["output_frames_dir"]
    assert output_dir.split("/")[-1] != lot_id, "la fixture doit faire diverger les deux"

    with pytest.raises(sm.ScanFrameRegressionError):
        scan_once(project_dir, payloads, failures={1: "page_detection_failed"})


def test_an_invalid_payload_is_refused_before_any_frame_is_written(
    tmp_path: Path,
) -> None:
    """La validation par page appartient a la reconstruction et elle est
    **appelee** par la garde prealable: un payload incomplet ne doit pas couter
    l'ecriture d'un dossier entier avant d'etre nomme."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    broken = make_payload(page_index=0, page_count=1)
    del broken["template_id"]

    with pytest.raises(ReconstructionError, match="template_id"):
        sm.check_scan_conflicts(project_dir, [broken])

    assert not (project_dir / SCAN_FRAMES_DIRNAME).exists()


def test_a_corrupt_mire_registry_does_not_escape_the_module_hierarchy(
    tmp_path: Path,
) -> None:
    """Le registre est lu **avant** toute validation de schema sur le chemin du
    refus prealable: un `project.json` edite a la main ne doit pas y faire sortir
    une `TypeError` nue, hors de la hierarchie que la CLI capture."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    payloads = two_pages()
    scan_once(project_dir, payloads)
    path = project_dir / MANIFEST_FILENAME
    document = json.loads(path.read_text(encoding="utf-8"))
    lot_of(document)["synthetic_frames"] = 42
    path.write_text(json.dumps(document), encoding="utf-8")

    sm.check_scan_conflicts(
        project_dir, payloads, failed_page_indexes=(1,), overwrite=True
    )


# --------------------------------------------------------------------------
# Le document relu: versions de schema et formes corrompues
# --------------------------------------------------------------------------


def _v2_0_manifest() -> dict:
    """Manifest v2.0 **reel**, dans la forme que le depot declare migrable.

    La section `video` y porte la cadence source, la cadence cible et la
    description de source pour tout le projet -- exactement ce que le contrat
    v2.1 interdit, et ce que `_migrate_v2_0` replace sur chaque rush et chaque
    lot.
    """
    return {
        "schema_version": "2.0",
        "project_id": PROJECT,
        "created": "2026-08-01T10:00:00Z",
        "rushes": [{"rush_id": RUSH, "source_path": "inputs/rush-001.mov"}],
        "lots": [{"lot_id": LOT, "rush_id": RUSH, "state": "extraction"}],
        "artifacts": {"frames_dir": EXTRACT_FRAMES_DIRNAME},
        "color": {},
        "video": {
            "fps_source": 30.0,
            "fps_target": FPS,
            "codec_target": "prores_422",
            "resolution_source": {"width": 1920, "height": 1080},
            "source_codec": "prores",
            "source_metadata_absent_fields": [],
        },
        "reconstruction": {},
    }


def test_a_real_v2_0_project_can_be_scanned(tmp_path: Path) -> None:
    """Chemin de panne **sans issue** avant correction: la garde ne testait que
    la *presence* de `schema_version`, donc la section `video` de la v2.0 --
    interdite par le contrat v2.1 -- etait fidelement restituee puis refusee par
    le schema, sur un message `jsonschema` brut portant sur une section que
    l'operateur n'avait pas touchee. Et le refus arrivait apres l'ecriture des
    frames, donc toute relance echouait a l'identique.

    `io.manifest.SCHEMA_PATHS_BY_VERSION` declare la v2.0 lisible et
    `build_extraction_manifest` la migre deja: la migration en memoire est la
    seule reponse coherente."""
    project_dir = tmp_path / "projet"
    write_manifest(project_dir, _v2_0_manifest())

    persisted = scan_once(project_dir, two_pages())

    assert persisted.manifest["schema_version"] == "2.1"
    assert "fps_source" not in persisted.manifest["video"]
    assert persisted.manifest["video"]["codec_target"] == "prores_422"
    assert persisted.manifest["rushes"][0]["fps_source"] == 30.0
    assert lot_of(persisted.manifest)["fps_target"] == FPS
    assert lot_of(persisted.manifest)["state"] == "scan"
    assert validate_manifest(persisted.manifest_path) is not None


def test_an_unknown_schema_version_is_refused_and_never_silently_rewritten(
    tmp_path: Path,
) -> None:
    """L'inverse exact de la regle que le module se donne, applique au marqueur
    qui gouverne toutes les relectures ulterieures: un `project.json` declarant
    `"2.2"` etait **retrograde** en `"2.1"` sans un mot, sans constat, et sans
    que rien ne dise ce que le document avait perdu."""
    project_dir = tmp_path / "projet"
    document = _v2_0_manifest()
    document["schema_version"] = "2.2"
    path = write_manifest(project_dir, document)
    before = path.read_bytes()

    with pytest.raises(LegacyManifestError, match="2.2"):
        scan_once(project_dir, two_pages())

    assert path.read_bytes() == before
    assert not (project_dir / SCAN_FRAMES_DIRNAME).exists()


def test_a_project_json_reduced_to_null_is_refused_not_overwritten(
    tmp_path: Path,
) -> None:
    """Cinq formes de corruption sur six etaient refusees avec un message
    actionnable; la sixieme -- un fichier reduit a `null` -- etait ecrasee en
    silence, la relecture rendant `None` aussi bien pour « fichier absent » que
    pour « fichier vide de sens »."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    path = project_dir / MANIFEST_FILENAME
    path.write_text("null", encoding="utf-8")

    with pytest.raises(sm.ScanPersistenceError, match="null"):
        scan_once(project_dir, two_pages())

    assert path.read_text(encoding="utf-8") == "null"
    assert not (project_dir / SCAN_FRAMES_DIRNAME).exists()


@pytest.mark.parametrize(
    "section, value",
    [
        ("lots", {"rush-001_5": {"lot_id": LOT}}),
        ("lots", ["rush-001_5"]),
        ("rushes", {"rush-001": {}}),
        ("rushes", [42]),
    ],
)
def test_a_malformed_lots_or_rushes_section_is_refused_not_silently_emptied(
    tmp_path: Path, section: str, value
) -> None:
    """La fusion saute les entrees non conformes: un `lots` reduit a un objet,
    ou une entree reduite a une chaine, **disparaissait** du document reecrit,
    emportant les empreintes de selection et les cardinaux attendus des autres
    lots. C'est exactement la situation ou la promesse « enrichir ne fait jamais
    desapprendre » compte le plus."""
    project_dir = tmp_path / "projet"
    document = rich_extraction_manifest()
    document[section] = value
    path = write_manifest(project_dir, document)
    before = path.read_bytes()

    with pytest.raises(sm.ScanPersistenceError, match=section):
        scan_once(project_dir, two_pages())

    assert path.read_bytes() == before


def test_a_lot_state_outside_the_closed_vocabulary_names_the_document_at_fault(
    tmp_path: Path,
) -> None:
    """Le refus etait le bon, mais il arrivait par le schema, apres l'ecriture
    des frames, et son message accusait le manifest **reconstruit** alors que la
    valeur fautive vient du manifest **relu** -- le contraire de ce que
    l'operateur doit corriger."""
    project_dir = tmp_path / "projet"
    existing = rich_extraction_manifest()
    lot_of(existing)["state"] = "bricole"
    write_manifest(project_dir, existing)

    with pytest.raises(sm.ScanManifestConflictError) as excinfo:
        scan_once(project_dir, two_pages())

    message = str(excinfo.value)
    assert "bricole" in message
    assert MANIFEST_FILENAME in message
    assert "manifest relu" in message
    assert not (project_dir / SCAN_FRAMES_DIRNAME).exists()


def test_a_non_string_lot_state_is_read_as_absent_and_the_scan_proceeds(
    tmp_path: Path,
) -> None:
    """Garde de type sur l'etat relu: `42` n'est pas un etat, et le lire tel
    quel le ferait ecrire dans le document reconstruit. Il vaut `None`, valeur
    licite que la garde de transition accepte sans condition."""
    project_dir = tmp_path / "projet"
    existing = rich_extraction_manifest()
    lot_of(existing)["state"] = 42
    write_manifest(project_dir, existing)

    persisted = scan_once(project_dir, two_pages())

    assert lot_of(persisted.manifest)["state"] == "scan"


def test_an_unknown_reconstruction_origin_is_refused() -> None:
    """Vocabulaire ferme a deux valeurs, chacune avec un producteur reel."""
    with pytest.raises(ReconstructionError, match="Origine"):
        reconstruct_project_manifest(
            [make_payload(page_index=0, page_count=1)], origin="devine"
        )


def _printed_by_the_real_makepdf(project_dir: Path, **overrides) -> dict:
    """Poser les quatre donnees d'impression par le **vrai** producteur de 5.11.

    L'AC 5 dit que la confrontation porte « sur ce que la chaine amont a
    **produit** », et l'action item 3 de la retro Epic 4 exige de tester contre
    les vrais producteurs -- ce qui etait fait pour les payloads et pour le
    rapport de 5.6, mais pas pour l'impression: la sequence nominale complete
    posait `lot["state"] = "pdf"` **a la main** sur un manifest d'extraction. Un
    renommage cote 5.11 de `lots[].patch_preset_id` serait passe inapercu et
    aurait desarme la garde centrale de l'AC 5 sans qu'aucun test ne sonne.
    """
    write_manifest(project_dir, rich_extraction_manifest())
    values = {
        "template_id": TPL,
        "patch_preset_id": PATCH_PRESET,
        "gamut_map_id": payload_io.GAMUT_MAP_IDENTITY,
    }
    values.update(overrides)
    return persist_pdf_generation(
        project_dir, PdfRecord(lot_id=LOT, **values)
    ).manifest


def test_the_nominal_sequence_runs_against_the_real_printing_producer(
    tmp_path: Path,
) -> None:
    """Sequence nominale complete d'un lot: extrait, imprime, scanne. Les trois
    identifiants viennent de l'impression, le QR les confirme, et l'etat avance
    de `pdf` a `scan` par la garde partagee."""
    project_dir = tmp_path / "projet"
    printed = _printed_by_the_real_makepdf(project_dir)
    assert lot_of(printed)["state"] == "pdf"

    persisted = scan_once(project_dir, two_pages())

    lot = lot_of(persisted.manifest)
    assert lot["state"] == "scan"
    assert lot["template_id"] == TPL
    assert lot["patch_preset_id"] == PATCH_PRESET
    assert lot["gamut_map_id"] == payload_io.GAMUT_MAP_IDENTITY
    assert sm.SCAN_STATE_CONSERVED not in persisted.findings


def test_a_plate_from_another_printing_is_refused_against_the_real_producer(
    tmp_path: Path,
) -> None:
    """Le pendant negatif, et c'est lui qui donne sa valeur au precedent: la
    confrontation porte sur ce que `makepdf` a **reellement** ecrit, pas sur un
    champ pose a la main par la fixture."""
    project_dir = tmp_path / "projet"
    _printed_by_the_real_makepdf(project_dir, template_id="tpl-a4-portrait-6f-v1")

    with pytest.raises(sm.ScanManifestConflictError, match="template_id"):
        scan_once(project_dir, two_pages())

    assert not (project_dir / SCAN_FRAMES_DIRNAME).exists()


# --------------------------------------------------------------------------
# Ce que ce module ecrit sur `lots[]`, et rien d'autre
# --------------------------------------------------------------------------


def test_the_lot_carries_exactly_what_the_two_tables_declare(tmp_path: Path) -> None:
    """`SCAN_LOT_FIELDS` se declare « le contrat, pas un resume du code », et
    trois champs de plus atterrissaient pourtant sur `lots[]` par le chemin de
    la reconstruction. Aucun test ne citait la constante, la ou ses deux soeurs
    (`EXTRACTION_LOT_FIELDS`, `PDF_LOT_FIELDS`) le sont: elle etait une
    declaration d'intention non opposable."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    persisted = scan_once(project_dir, two_pages())

    lot = lot_of(persisted.manifest)
    attendus = set(sm.SCAN_LOT_FIELDS) | set(sm.RECONSTRUCTION_LOT_FIELDS)
    # Un lot sans page de calibration ne porte pas `color_calibration_status`
    # (`EPIC5-ARB-68`): c'est ce qui tient la non-regression octet a octet du chemin non
    # corrige. La table borne donc **par le haut** ici -- rien hors table --, et le
    # second volet ci-dessous ferme l'autre bout, sans quoi un champ declare et jamais
    # ecrit passerait.
    assert set(lot) <= attendus, sorted(set(lot) - attendus)
    assert set(lot) == attendus - {"color_calibration_status"}
    assert not set(sm.SCAN_LOT_FIELDS) & set(sm.RECONSTRUCTION_LOT_FIELDS)

    # Volet 2 -- le meme lot scanne avec un statut mesure porte le champ, et **tous** les
    # autres restent les memes. Sans ce volet, la table pourrait declarer un champ que
    # rien n'ecrit jamais.
    corrige = tmp_path / "projet-corrige"
    corrige.mkdir()
    porteur = lot_of(scan_once(
        corrige, two_pages(),
        color_calibration_status=color_pipeline.APPLIED_STATUS,
    ).manifest)
    assert set(porteur) == attendus, sorted(attendus ^ set(porteur))
    assert porteur["color_calibration_status"] == color_pipeline.APPLIED_STATUS


def test_no_lot_field_is_written_outside_the_table_on_a_rich_manifest(
    tmp_path: Path,
) -> None:
    """Sur un manifest d'extraction riche, le lot garde ses vingt champs et
    n'en recoit aucun hors des deux tables."""
    project_dir = tmp_path / "projet"
    existing = rich_extraction_manifest()
    before = set(lot_of(existing))
    write_manifest(project_dir, existing)

    persisted = scan_once(project_dir, two_pages())

    added = set(lot_of(persisted.manifest)) - before
    assert added <= set(sm.SCAN_LOT_FIELDS)


# --------------------------------------------------------------------------
# Les constats: emis quand ils doivent l'etre, et jamais hors vocabulaire
# --------------------------------------------------------------------------


def test_the_incomplete_lot_finding_is_emitted_and_the_complete_one_is_not(
    tmp_path: Path,
) -> None:
    """« Ce lot est-il fini ? » est la question que le compte rendu doit
    trancher: le constat n'avait aucun test d'emission."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    partial = scan_once(project_dir, [make_payload(page_index=0)])
    assert sm.SCAN_LOT_INCOMPLETE in partial.findings

    complete = scan_once(project_dir, two_pages(), overwrite=True)
    assert sm.SCAN_LOT_INCOMPLETE not in complete.findings
    assert complete.lot_complete


def _drop_extra_conforming_frames(project_dir: Path, count: int) -> None:
    """Deposer des frames **conformes** que le lot n'attend pas.

    Un nom conforme appartient par construction a la convention du lot (meme
    `rush_id`, meme cadence): 5.6 le compte donc dans `observed_frame_count` et
    le nomme `preexisting_frames`. C'est le geste d'un operateur qui recopie un
    dossier a la main, et le seul moyen d'obtenir `observed > expected`.
    """
    output_dir = project_dir / SCAN_FRAMES_DIRNAME / "rush-001_5"
    source = next(output_dir.iterdir())
    for index in range(count):
        name = naming.build_scan_frame_filename(RUSH, FPS, f"00:00:{20 + index}:00")
        (output_dir / name).write_bytes(source.read_bytes())


def test_more_real_frames_than_expected_never_reads_complete(tmp_path: Path) -> None:
    """La stricte egalite est ce qui decide: un dossier portant plus de fichiers
    conformes que le lot n'en attend n'est pas un lot complet, c'est un dossier
    a inspecter. Aucun scenario ne faisait decider cette clause seule."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    payloads = two_pages()
    scan_once(project_dir, payloads)
    _drop_extra_conforming_frames(project_dir, 1)

    persisted = scan_once(project_dir, payloads, overwrite=True)

    assert persisted.reconstructed_frame_count == 5
    assert persisted.expected_frame_count == 4
    assert not persisted.lot_complete


def test_one_mire_forbids_completeness_even_when_the_count_matches(
    tmp_path: Path,
) -> None:
    """Clause d'EPIC5-ARB-8: « une mire interdit le verdict de completude meme
    si aucune page ne manque ». Dans tous les scenarios testes une mire faisait
    deja baisser le cardinal reconstruit, donc la clause etait **redondante** --
    et une refonte l'aurait emportee sans rien casser."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    payloads = two_pages()
    scan_once(project_dir, payloads)
    _drop_extra_conforming_frames(project_dir, 2)

    persisted = scan_once(
        project_dir, payloads, failures={1: "page_detection_failed"}, overwrite=True
    )

    assert persisted.reconstructed_frame_count == persisted.expected_frame_count == 4
    assert persisted.synthetic_frame_count == 2
    assert not persisted.lot_complete, "une mire interdit la completude"
    assert sm.SCAN_SYNTHETIC_FRAMES_PRESENT in persisted.findings


def test_apres_le_tri_le_cardinal_attendu_d_un_lot_ne_compte_aucune_calibration(
    tmp_path: Path,
) -> None:
    """REECRIT PAR 5.24 (AC 8, classe B) -- bloquant `B1` de la revue de 5.16, rebase.

    Le regime est nomme, et c'est le point de ce test: **le projet reconstruit
    depuis des planches seules** (story 2.6), c'est-a-dire un projet vierge ou
    aucun cardinal attendu n'a jamais ete persiste.
    `io.scan_manifest._resolve_expected_frame_count` y ecrit la valeur du scan
    telle quelle -- sa troisieme branche, « absent du manifest: le scan
    l'apporte ». Sur le chemin nominal `extract -> makepdf -> scan`, le defaut est
    **masque** par le cardinal venu de l'extraction ; l'assertion sur
    `SCAN_EXPECTED_FRAME_COUNT_CONSERVED` est ce qui garantit que ce test mesure
    bien le regime ou le defaut mord.

    L'assertion morte etait « la page de calibration est **dans le lot ecrit**,
    avec son role persiste »: elle n'appartient plus a aucun lot
    (`EPIC5-ARB-82`), et le tri la retire avant toute ecriture. Ce qui survit --
    et c'est ce que l'AC 8 de 5.24 annonce mot pour mot -- est que **le cardinal
    attendu d'un lot ne compte jamais une page de calibration**.

    La pile de depart en porte une; c'est le **tri** qui la retire, pas la
    fabrique. Un test qui serait parti de planches seules ne mesurerait pas la
    soustraction, il mesurerait une pile ou il n'y avait rien a soustraire.
    """
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    # **La pile est celle que le depot imprime aujourd'hui**: un lot de deux
    # planches (`page_count` ne compte qu'elles) et une page de calibration
    # **autonome**, composee seule -- `pdf_composition.CALIBRATION_ONLY_PAGE_COUNT`
    # vaut 1 depuis 5.22. `v2_lot_with_calibration_page` modelise le regime PAR LOT
    # de 5.16, ou la feuille etait litteralement la page 0 d'un lot ; ce regime-la
    # a disparu avec `EPIC5-ARB-82`.
    #
    # La page de calibration est posee **au milieu**: une pile ou elle serait
    # premiere laisserait passer un routage qui rend toujours le premier element.
    calibration = make_payload(
        page_index=page_roles.CALIBRATION_PAGE_INDEX, page_count=1,
        template_id=TPL_V2, page_role=page_roles.PAGE_ROLE_CALIBRATION)
    pile = [
        make_payload(page_index=0, page_count=2, first_slot=0, slot_count=2,
                     template_id=TPL_V2),
        calibration,
        make_payload(page_index=1, page_count=2, first_slot=2, slot_count=2,
                     template_id=TPL_V2),
    ]
    a_trier = [
        scan_sorting.PageAtrier(read_rank=rang, locator_source="vrac.pdf",
                                locator_page_index=rang, payload=payload)
        for rang, payload in enumerate(pile)
    ]
    partition = scan_sorting.trier_les_pages(a_trier, project_id_courant=PROJECT)
    assert len(partition.pages_de_calibration) == 1
    assert len(partition.lots) == 1
    payloads = [page.payload for page in partition.lots[0].pages]
    assert len(payloads) == 2

    persisted = scan_once(project_dir, payloads)

    # Le regime: rien n'etait persiste, donc rien n'a ete conserve. Cette assertion
    # est ce qui garantit que le test ne mesure pas le chemin nominal.
    assert sm.SCAN_EXPECTED_FRAME_COUNT_CONSERVED not in persisted.findings
    assert sm.SCAN_EXPECTED_FRAME_COUNT_INDETERMINABLE not in persisted.findings
    assert persisted.expected_frame_count == 4, persisted.findings
    assert persisted.reconstructed_frame_count == 4
    assert persisted.lot_complete, persisted.findings
    lot = lot_of(persisted.manifest)
    # Ce que le document **conserve**: le nombre faux repartait de la, `scan_previz`
    # le consommant comme une mesure.
    assert lot["expected_frame_count"] == 4
    assert lot["reconstructed_frame_count"] == 4
    # **Et aucune page de calibration n'est comptee dans le lot ecrit**: ni au
    # cardinal, ni au registre des roles.
    roles = persisted.manifest["reconstruction"]["page_roles"]
    assert [entree["page_role"] for entree in roles] == [
        page_roles.PAGE_ROLE_IMAGES] * 2, roles
    assert page_roles.PAGE_ROLE_CALIBRATION not in {
        entree["page_role"] for entree in roles}


def test_the_nominal_path_masks_the_calibration_page_by_conserving_the_cardinal(
) -> None:
    """Le mecanisme du masquage, exerce pour lui-meme.

    C'est le pendant du test precedent, et il existe pour que la raison du choix de regime
    soit **mesuree** et non seulement racontee: quand le manifest porte deja un cardinal,
    la valeur du scan est ecartee et le constat de conservation est emis. Un cardinal faux
    venu du scan est donc invisible sur ce chemin -- ce qui est exactement pourquoi le test
    de B1 porte sur l'autre.
    """
    resolu, findings = sm._resolve_expected_frame_count({"expected_frame_count": 4}, 6)
    assert resolu == 4
    assert findings == [sm.SCAN_EXPECTED_FRAME_COUNT_CONSERVED]
    # Et sans cardinal anterieur, la valeur du scan passe telle quelle: c'est la branche
    # que le lot reconstruit emprunte, et elle n'emet aucun constat.
    assert sm._resolve_expected_frame_count(None, 6) == (6, [])


def test_a_measured_expected_count_survives_a_pass_that_cannot_deduce_it(
    tmp_path: Path,
) -> None:
    """Aucun test ne combinait « cardinal deja persiste » et « passe
    indeterminable »: le document ne bougeait pas -- la fusion le porte deja --
    mais le verdict de completude et le compte rendu basculaient a
    « indetermine »."""
    project_dir = tmp_path / "projet"
    existing = rich_extraction_manifest()
    measured = lot_of(existing)["expected_frame_count"]
    write_manifest(project_dir, existing)

    # La **derniere** page manque: le cardinal attendu est indeterminable pour
    # cette passe, mais le manifest en porte un, mesure a l'extraction.
    persisted = scan_once(project_dir, [make_payload(page_index=0)])

    assert persisted.expected_frame_count == measured
    assert lot_of(persisted.manifest)["expected_frame_count"] == measured
    assert sm.SCAN_EXPECTED_FRAME_COUNT_CONSERVED in persisted.findings
    assert sm.SCAN_EXPECTED_FRAME_COUNT_INDETERMINABLE not in persisted.findings


def test_the_closed_vocabulary_of_findings_is_enforced_on_the_production_path(
    tmp_path: Path, monkeypatch
) -> None:
    """La fonction de garde avait son test, mais son **branchement** sur le
    chemin de production n'en avait aucun: retirer l'appel ne cassait rien.
    Detourner une constante de constat est le seul moyen d'exercer la garde la
    ou elle sert."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    monkeypatch.setattr(sm, "SCAN_LOT_INCOMPLETE", "CONSTAT_BRICOLE")

    with pytest.raises(sm.ScanPersistenceError, match="CONSTAT_BRICOLE"):
        scan_once(project_dir, [make_payload(page_index=0)])


# --------------------------------------------------------------------------
# AC 11 / AC 12 -- limite declaree, frontieres tenues
# --------------------------------------------------------------------------


def test_the_concurrency_limit_is_documented_at_the_top_of_the_module() -> None:
    """Le defaut est deja consigne deux fois au `deferred-work.md`: il ne doit
    pas se redecouvrir une cinquieme fois."""
    docstring = ast.get_docstring(ast.parse(MODULE_PATH.read_text(encoding="utf-8")))
    flattened = " ".join(docstring.lower().split())
    assert "aucun verrou** sur la sequence lecture-modification-ecriture" in flattened
    assert "une seule commande ecrivant le manifest a la fois par projet" in flattened
    assert "deferred-work.md" in flattened


@pytest.mark.parametrize(
    "forbidden",
    ["export_frame_tiff16", "compute_page_homography", "decode_qr_image", "cv2"],
)
def test_the_module_never_detects_crops_nor_writes_a_pixel(forbidden: str) -> None:
    """Frontieres de l'AC 12, verrouillees par lecture du source: cette story
    ne detecte pas (5.2), ne decoupe pas (5.3) et n'ecrit aucune frame (5.6)."""
    assert forbidden not in MODULE_PATH.read_text(encoding="utf-8")


#: Les fonctions de `cli.py` que cette story ajoute ou modifie, c'est-a-dire
#: **le chemin de la commande `scan`**. Le verrou de l'AC 12 ne portait que sur
#: `io/scan_manifest.py`, alors que la story modifie aussi `cli.py` -- ou
#: `compute_page_homography` est deja appele par le chemin POC legacy, donc la
#: ou le risque de recidive est le plus reel.
SCAN_CHAIN_FUNCTIONS = (
    "scan_command",
    # La moitie aval de `scan_command`, extraite par la story 5.26 (AC 2) pour
    # etre appelee aussi par la commande d'ecriture: elle herite du meme
    # interdit -- elle appelle les modules proprietaires et ne refait le
    # travail d'aucun. Depuis la story 11.4b (lot S1) elle vit dans le module
    # de coeur `scan_write` et `cli._ecrire_le_lot_detecte` en est
    # l'enveloppeur: les deux sont lus.
    "_ecrire_le_lot_detecte",
    "ecrire_le_lot_detecte",
    "_scanned_pages_for_output",
    "_scan_provenance",
    "_print_scan_persistence",
)


def _scan_chain_functions() -> dict:
    """Les fonctions du chemin de scan, sur les DEUX fichiers qui le portent.

    Story 11.4b (lot S1): la moitie aval -- correction, recadrage, refus
    prealable, frames, manifest -- a quitte `cli.py` pour le module de coeur
    `scan_write`, exactement comme la moitie amont avait quitte `cli.py` pour
    `scan_detect` en 7.3. Ne lire que `cli.py` ferait disparaitre l'invariant
    au lieu de le mesurer.
    """
    fonctions: dict = {}
    for fichier in ("cli.py", "scan_write.py"):
        arbre = ast.parse(
            (REPO_ROOT / "src" / "mixed_media_utility" / fichier).read_text(
                encoding="utf-8"))
        for node in ast.walk(arbre):
            if isinstance(node, ast.FunctionDef):
                fonctions.setdefault(node.name, node)
    return fonctions


def _identifiers_of(function_node: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(function_node):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


def test_the_scan_command_path_never_detects_crops_nor_writes_a_pixel() -> None:
    """AC 12, etendu a `cli.py`: la commande **appelle** les modules
    proprietaires (5.1, 5.2, 5.3, 5.6, 5.7) et ne refait le travail d'aucun.

    Le verrou d'origine lisait `io/scan_manifest.py` et lui seul; ce que l'AC
    promet n'etait donc prouve, pour `cli.py`, que par un grep de diff non
    rejouable. Ici la lecture est faite par AST, sur les seules fonctions du
    chemin de scan, si bien que le chemin POC legacy -- anterieur et hors
    perimetre -- ne fausse pas le verdict."""
    functions = _scan_chain_functions()
    for name in SCAN_CHAIN_FUNCTIONS:
        assert name in functions, name
        used = _identifiers_of(functions[name])
        for forbidden in (
            "export_frame_tiff16",
            "compute_page_homography",
            "decode_qr_image",
            "imread",
            "imwrite",
        ):
            assert forbidden not in used, f"{name} appelle {forbidden}"


def test_the_scan_command_refuses_before_it_writes_a_single_frame() -> None:
    """Verrou d'ordre (EPIC5-ARB-34, clause 1), lu sur le corps de la commande:
    l'appel a la garde prealable precede l'appel d'ecriture des frames.

    Un test de comportement le prouve deja sur un scenario; celui-ci interdit la
    **reintroduction** de l'ordre inverse par une refonte, qui est precisement la
    facon dont le defaut est ne.

    Adaptation 5.26 (extraction, AC 2): les trois appels vivent desormais dans
    `_ecrire_le_lot_detecte`, la moitie aval extraite de `scan_command` que
    `scan` et `scan-write` appellent tous deux -- l'invariant d'ordre se mesure
    a l'endroit ou le code est parti, et il protege ainsi les DEUX commandes
    d'un coup."""
    body = _scan_chain_functions()["ecrire_le_lot_detecte"]
    # L'ordre se lit sur les **numeros de ligne**, jamais sur l'ordre de
    # parcours de l'AST, qui est en largeur d'abord et ne dit rien de la
    # sequence reelle.
    lines = {
        node.func.attr: node.lineno
        for node in ast.walk(body)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    for name in ("check_scan_conflicts", "write_lot_output_frames", "persist_scan"):
        assert name in lines, name
    assert lines["check_scan_conflicts"] < lines["write_lot_output_frames"]
    assert lines["write_lot_output_frames"] < lines["persist_scan"]


def test_the_module_touches_neither_the_qr_payload_nor_the_frozen_schema() -> None:
    """`io/payload.py` reste inchange -- la matrice interdit un resultat de
    calibration dans le QR --, et `project.schema.v2-0.json` est fige."""
    source = MODULE_PATH.read_text(encoding="utf-8")
    for forbidden in ("build_page_payload", "project.schema.v2-0", "page_templates"):
        assert forbidden not in source


def test_the_persistence_codes_are_a_closed_vocabulary() -> None:
    with pytest.raises(sm.ScanPersistenceError, match="inconnu"):
        sm.validate_persistence_code("TOUT_VA_BIEN")
    for code in sm.SCAN_PERSISTENCE_CODES:
        assert sm.validate_persistence_code(code) == code


# --------------------------------------------------------------------------
# Gardes d'entree du module
# --------------------------------------------------------------------------


@pytest.mark.parametrize("dpi", [0, -1, True, 600.0, "600"])
def test_an_invalid_scan_dpi_is_refused(tmp_path: Path, dpi) -> None:
    """Garde `bool`-avant-`int` du helper partage: `True` n'est pas un DPI."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    payloads = two_pages()
    report = write_report(project_dir, [scanned_page(p) for p in payloads])

    with pytest.raises(sm.ScanPersistenceError, match="DPI"):
        sm.ScanRecord(
            page_payloads=tuple(payloads),
            output_report=report,
            scan_dpi=dpi,
            ingest_slug="lot-a",
        )


def test_a_report_missing_a_field_fails_inside_the_module_hierarchy(
    tmp_path: Path,
) -> None:
    """Le typage structurel est un choix; son prix est un refus nomme plutot
    qu'un `AttributeError` nu devant l'operateur."""

    class Incomplet:
        lot_id = LOT

    project_dir = tmp_path / "projet"
    project_dir.mkdir()

    with pytest.raises(sm.ScanPersistenceError, match="champs attendus"):
        sm.persist_scan(
            project_dir,
            sm.ScanRecord(
                page_payloads=(make_payload(page_index=0, page_count=1),),
                output_report=Incomplet(),
                scan_dpi=600,
                ingest_slug="lot-a",
            ),
        )


@pytest.mark.parametrize(
    "field_name", ["overwritten_files", "preexisting_frames", "missing_frames"]
)
def test_a_report_whose_name_lists_are_not_iterable_fails_inside_the_hierarchy(
    tmp_path: Path, field_name: str
) -> None:
    """Le module verifiait la **presence** des champs du rapport et le type de
    trois cardinaux, mais pas l'iterabilite des trois listes de noms: un `None`
    glisse a leur place sortait en `TypeError` nue, hors de la hierarchie que la
    CLI capture -- precisement le mode de panne que la docstring de la lecture
    revendique de fermer."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    payloads = two_pages()
    report = write_report(project_dir, [scanned_page(p) for p in payloads])

    with pytest.raises(sm.ScanPersistenceError, match=field_name):
        sm.build_scan_manifest(
            None,
            make_record(payloads, dataclasses.replace(report, **{field_name: None})),
        )


def test_a_report_frame_with_an_invalid_slot_index_is_refused(tmp_path: Path) -> None:
    """Garde `bool`-avant-`int` sur ce que le rapport declare: aucune garde de
    type du rapport n'avait de test negatif."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    payloads = two_pages()
    report = write_report(project_dir, [scanned_page(p) for p in payloads])
    broken = dataclasses.replace(
        report,
        frames=(dataclasses.replace(report.frames[0], slot_index=True),)
        + report.frames[1:],
    )

    with pytest.raises(sm.ScanPersistenceError, match="slot_index"):
        sm.build_scan_manifest(None, make_record(payloads, broken))


def test_a_report_frame_without_a_file_name_is_refused(tmp_path: Path) -> None:
    """Le nom de fichier est l'identite sur laquelle le registre des mires est
    tenu (EPIC5-ARB-33): il ne peut pas etre vide."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    payloads = two_pages()
    report = write_report(project_dir, [scanned_page(p) for p in payloads])
    broken = dataclasses.replace(
        report,
        frames=(dataclasses.replace(report.frames[0], filename=""),)
        + report.frames[1:],
    )

    with pytest.raises(sm.ScanPersistenceError, match="filename"):
        sm.build_scan_manifest(None, make_record(payloads, broken))


@pytest.mark.parametrize(
    "slug", ["../../evade", "lot/a", "lot\\a", " lot-a", "lot-a "]
)
def test_an_ingest_slug_that_is_a_path_is_refused(tmp_path: Path, slug: str) -> None:
    """Le depot a une regle explicite -- aucune chaine du manifest ne remonte
    au-dessus du projet -- et ce champ s'y soustrayait: il etait ecrit tel quel,
    sans passer par la normalisation appliquee a `output_frames_dir`."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    payloads = two_pages()
    report = write_report(project_dir, [scanned_page(p) for p in payloads])

    with pytest.raises(sm.ScanPersistenceError, match="segment"):
        sm.ScanRecord(
            page_payloads=tuple(payloads),
            output_report=report,
            scan_dpi=600,
            ingest_slug=slug,
        )


def test_a_project_dir_that_is_a_file_fails_inside_the_module_hierarchy(
    tmp_path: Path,
) -> None:
    """La creation du dossier projet etait **hors** du `try/except OSError` qui
    la suit, si bien qu'un `project_dir` qui est un fichier sortait en
    `FileExistsError` nue -- alors que le module promet a la CLI un seul
    `except` a tenir."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    payloads = two_pages()
    report = write_report(project_dir, [scanned_page(p) for p in payloads])
    not_a_dir = tmp_path / "pas-un-dossier"
    not_a_dir.write_text("", encoding="utf-8")

    with pytest.raises(sm.ScanPersistenceError):
        sm.persist_scan(not_a_dir, make_record(payloads, report))


def test_a_bad_lot_state_in_the_read_manifest_names_it_to_reconstruct_project() -> None:
    """Meme diagnostic sur l'autre chemin: la sous-commande partage la garde, et
    son message doit designer le manifest **local**, pas le document produit."""
    with pytest.raises(ReconstructionError, match="manifest local"):
        reconstruct_project_manifest(
            [make_payload(page_index=0, page_count=1)],
            existing_manifest={
                "lots": [{"lot_id": LOT, "rush_id": RUSH, "state": "bricole"}]
            },
        )


def test_a_manifest_that_is_not_an_object_is_refused(tmp_path: Path) -> None:
    """Un `project.json` qui contient `42` est un JSON valide et un manifest
    absurde."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    payloads = two_pages()
    report = write_report(project_dir, [scanned_page(p) for p in payloads])

    with pytest.raises(sm.ScanPersistenceError, match="objet JSON"):
        sm.build_scan_manifest(42, make_record(payloads, report))


@pytest.mark.parametrize("overwrite", [1, "oui", None])
def test_overwrite_must_be_a_boolean(tmp_path: Path, overwrite) -> None:
    """Le drapeau vit desormais sur la garde prealable, la ou le refus se
    place: la persistance, elle, n'en a plus (EPIC5-ARB-34, clause 3)."""
    project_dir = tmp_path / "projet"
    project_dir.mkdir()

    with pytest.raises(sm.ScanPersistenceError, match="booleen"):
        sm.check_scan_conflicts(project_dir, two_pages(), overwrite=overwrite)


def test_the_persistence_layer_carries_no_overwrite_flag() -> None:
    """Verrou d'EPIC5-ARB-34, clause 3: une fois les fichiers ecrits, le
    manifest enregistre le reel **sans jamais le refuser**. Un drapeau sur cette
    couche voudrait dire qu'un chemin peut encore refuser d'enregistrer ce que
    le disque porte -- c'est-a-dire mentir sur l'etat du projet."""
    import inspect

    for function in (sm.persist_scan, sm.build_scan_manifest):
        assert "overwrite" not in inspect.signature(function).parameters, function
    assert "overwrite" in inspect.signature(sm.check_scan_conflicts).parameters


# --------------------------------------------------------------------------
# AC 1 -- l'orchestration reelle: la commande `scan` de bout en bout
# --------------------------------------------------------------------------

#: La planche synthetique est rendue a 300 ppp: en dessous, les modules ArUco
#: du gabarit ne portent plus assez de pixels pour etre detectes. Le seuil de
#: fiabilite du QR (`QR_MIN_SCAN_DPI`) est plus haut encore -- l'ingestion le
#: signale, et c'est bien ce qu'elle doit faire.
CLI_DPI = 300


def build_scanned_page_image(payload: dict, *, dpi: int = CLI_DPI) -> np.ndarray:
    """Une planche imprimee **puis numerisee**, telle que l'operateur la pose.

    Les quatre marqueurs de coin sont poses aux positions nominales du **vrai**
    gabarit (`page_templates.corner_marker_centers_mm`) et dessines par le
    **vrai** generateur (`layout.generate_aruco_marker_image`); le QR porte le
    payload **serialise** par `io.payload`. Fabriquer cette image a la main --
    positions recopiees, QR simule -- ne prouverait rien de la chaine reelle.
    """
    spec = page_templates.get_template(payload["template_id"])
    width_px, height_px = page_templates.page_size_px(spec, dpi)
    page = np.full((height_px, width_px), 255, np.uint8)

    marker_px = int(round(layout.MARKER_SIZE_MM / 25.4 * dpi))
    for marker_id, (x_mm, y_mm) in page_templates.corner_marker_centers_mm(spec).items():
        marker = layout.generate_aruco_marker_image(marker_id, marker_px)
        center_x, center_y = page_templates.mm_to_px(x_mm, y_mm, dpi)
        left, top = center_x - marker_px // 2, center_y - marker_px // 2
        page[top : top + marker_px, left : left + marker_px] = marker

    symbol = qr_codes.encode_qr_image(payload_io.serialize_payload(payload))
    side = int(round(qr_codes.QR_PRINT_SIZE_TARGET_MM / 25.4 * dpi))
    enlarged = cv2.resize(symbol, (side, side), interpolation=cv2.INTER_NEAREST)
    left = (width_px - side) // 2
    top = height_px - marker_px - side - 20
    page[top : top + side, left : left + side] = enlarged
    return cv2.cvtColor(page, cv2.COLOR_GRAY2BGR)


def cli_payload(**kwargs) -> dict:
    return make_payload(page_index=0, page_count=1, first_slot=0, slot_count=2, **kwargs)


def write_scan_folder(folder: Path, payloads: list[dict]) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    for rank, payload in enumerate(payloads, start=1):
        cv2.imwrite(
            str(folder / f"page_{rank:02d}.tiff"), build_scanned_page_image(payload)
        )
    return folder


def run_scan(project_dir: Path, folder: Path, *args: str) -> int:
    return cli.main(
        [
            "scan",
            "--project",
            str(project_dir),
            "--scan",
            str(folder),
            "--dpi",
            str(CLI_DPI),
            *args,
        ]
    )


def test_the_scan_command_goes_from_the_plate_to_the_manifest(tmp_path: Path) -> None:
    """L'orchestration entiere, par la commande reelle: ingestion (5.1),
    detection (5.2), recadrage (5.3), ecriture des frames (5.6), manifest
    (5.7). Aucun maillon n'est simule."""
    folder = write_scan_folder(tmp_path / "lot-a", [cli_payload()])
    project_dir = tmp_path / "projet"

    assert run_scan(project_dir, folder) == 0

    document = validate_manifest(project_dir / MANIFEST_FILENAME)
    lot = lot_of(document)
    assert lot["state"] == "scan"
    assert lot["reconstructed_frame_count"] == 2
    assert lot["synthetic_frame_count"] == 0
    assert lot["expected_frame_count"] == 2
    assert document["reconstruction"]["origin"] == "scan"
    assert document["reconstruction"]["status"] == "complete"
    assert sorted(
        path.name for path in (project_dir / lot["output_frames_dir"]).iterdir()
    ) == [
        "scan_rush-001_5_00-00-00-00.tiff",
        "scan_rush-001_5_00-00-01-00.tiff",
    ]


def test_the_scan_command_keeps_the_decoded_payloads_between_the_steps(
    tmp_path: Path,
) -> None:
    """Point H4 des arbitrages: le document de detection ne porte ni cadence ni
    timecodes. Le payload voyage sur l'objet en memoire et **n'entre pas** au
    document, dont l'empreinte ne change donc pas."""
    folder = write_scan_folder(tmp_path / "lot-a", [cli_payload()])
    project_dir = tmp_path / "projet"
    project_layout_dir = project_dir
    project_layout_dir.mkdir(parents=True, exist_ok=True)
    from mixed_media_utility.io import project_layout

    project_layout.ensure_project_layout(project_dir)
    ingest = scan_ingest.ingest_scan_lot(project_dir, folder, dpi=CLI_DPI)
    detection = scan_detection.detect_lot_pages(project_dir, ingest, dpi=CLI_DPI)

    detected = detection.pages[0]
    assert detected.payload is not None
    assert detected.payload["slots"][0]["frame_timecode"] == "00:00:00:00"
    assert "payload" not in detected.as_document()
    assert "slots" not in json.dumps(scan_detection.report_document(detection))


def test_the_scan_command_reports_a_lot_whose_plates_carry_no_qr(
    tmp_path: Path, capsys
) -> None:
    """Ni frame ni manifest: le timecode vient du payload de sa propre page.
    L'ingestion, elle, a eu lieu, et la commande le dit sans faux succes."""
    folder = tmp_path / "lot-blanc"
    folder.mkdir()
    cv2.imwrite(str(folder / "page_01.tiff"), np.full((400, 300, 3), 200, np.uint8))
    project_dir = tmp_path / "projet"

    assert run_scan(project_dir, folder) == 0

    assert (project_dir / SCANS_DIRNAME / "lot-blanc" / "ingest.json").is_file()
    assert not (project_dir / MANIFEST_FILENAME).exists()
    assert not (project_dir / SCAN_FRAMES_DIRNAME).exists()
    assert "aucune identifiee" in capsys.readouterr().out


def test_the_scan_command_refuses_a_second_pass_without_overwrite(
    tmp_path: Path,
) -> None:
    """Regle uniforme d'EPIC5-ARB-18: ecraser un fichier existant exige
    `--overwrite`, mire ou non. Le manifest precedent reste intact."""
    folder = write_scan_folder(tmp_path / "lot-a", [cli_payload()])
    project_dir = tmp_path / "projet"
    assert run_scan(project_dir, folder) == 0
    before = (project_dir / MANIFEST_FILENAME).read_bytes()

    assert run_scan(project_dir, folder) == 1

    assert (project_dir / MANIFEST_FILENAME).read_bytes() == before


def test_the_scan_command_is_idempotent_with_overwrite(tmp_path: Path) -> None:
    """Deuxieme passe identique, drapeau assume: pas un octet ne bouge."""
    folder = write_scan_folder(tmp_path / "lot-a", [cli_payload()])
    project_dir = tmp_path / "projet"
    assert run_scan(project_dir, folder) == 0
    before = (project_dir / MANIFEST_FILENAME).read_bytes()

    assert run_scan(project_dir, folder, "--overwrite") == 0

    assert (project_dir / MANIFEST_FILENAME).read_bytes() == before


def test_the_scan_command_refuses_a_foreign_plate_even_with_overwrite(
    tmp_path: Path,
) -> None:
    """R12 de bout en bout: le drapeau autorise a reecrire des fichiers, il
    n'autorise pas a ecrire une mauvaise association."""
    folder = write_scan_folder(tmp_path / "lot-a", [cli_payload()])
    project_dir = tmp_path / "projet"
    write_manifest(
        project_dir,
        _existing_with_printed_identifiers(template_id="tpl-a4-paysage-8f-m5-v1"),
    )
    before = (project_dir / MANIFEST_FILENAME).read_bytes()

    assert run_scan(project_dir, folder, "--overwrite") == 1

    assert (project_dir / MANIFEST_FILENAME).read_bytes() == before


def erase_a_corner_marker(image: np.ndarray, *, dpi: int = CLI_DPI) -> np.ndarray:
    """Effacer un marqueur de coin: QR intact, geometrie irrecuperable.

    C'est la seule facon de faire passer une planche **par la commande reelle**
    dans la branche « page presente dont la geometrie a echoue » -- celle qui
    produit les mires. Aucune fabrique du depot ne savait la produire, et c'est
    pourquoi trois mutants de cette branche survivaient: les tests de mire
    partaient tous d'une page en echec **construite a la main**, jamais d'une
    planche reelle.
    """
    marker_px = int(round(layout.MARKER_SIZE_MM / 25.4 * dpi))
    patched = image.copy()
    patched[: marker_px * 2, : marker_px * 2] = 255
    return patched


def cli_pages() -> list[dict]:
    """Un lot de **deux** planches pour la commande reelle.

    Deux et non une, parce que 5.6 ne sait dessiner une mire que si la forme des
    frames est determinable: sur un lot d'une seule planche en echec, la passe
    n'ecrit rien du tout (`SYNTHETIC_FRAME_SHAPE_INDETERMINABLE`). Le lot mixte
    -- une planche lue, une planche perdue -- est aussi le cas reel.
    """
    return [
        make_payload(page_index=index, page_count=2, slot_count=2)
        for index in range(2)
    ]


def write_cli_folder(folder: Path, payloads: list[dict], *, broken: tuple = ()) -> Path:
    """Ecrire les planches d'un lot, certaines a marqueur de coin efface."""
    folder.mkdir(parents=True, exist_ok=True)
    for rank, payload in enumerate(payloads, start=1):
        image = build_scanned_page_image(payload)
        if payload["page_index"] in broken:
            image = erase_a_corner_marker(image)
        cv2.imwrite(str(folder / f"page_{rank:02d}.tiff"), image)
    return folder


def test_the_scan_command_writes_mires_for_a_plate_whose_geometry_failed(
    tmp_path: Path,
) -> None:
    """La branche « planche en echec » de bout en bout, par la commande reelle.

    Elle verrouille trois choses qu'aucun test ne voyait: le payload est
    **conserve** sur une page refusee (sans lui la page cesse d'etre identifiee
    et ne recoit plus de mire du tout), l'aiguillage vers le motif
    `page_detection_failed` a bien lieu, et `homography_status` vaut autre chose
    que `resolved` -- il n'avait jamais ete observe a une autre valeur."""
    payloads = cli_pages()
    folder = write_cli_folder(tmp_path / "lot-a", payloads, broken=(1,))
    project_dir = tmp_path / "projet"

    assert run_scan(project_dir, folder) == LOT_AVEC_MIRES_MAIS_ECRIT

    document = validate_manifest(project_dir / MANIFEST_FILENAME)
    lot = lot_of(document)
    assert lot["reconstructed_frame_count"] == 2
    assert lot["synthetic_frame_count"] == 2
    assert lot["synthetic_frames"] == [
        "scan_rush-001_5_00-00-02-00.tiff",
        "scan_rush-001_5_00-00-03-00.tiff",
    ]
    section = document["reconstruction"]
    assert section["status"] == "partial"
    assert "missing_pages" not in section, "la page est presente, pas manquante"
    assert [slot["synthetic"] for slot in section["slots"]] == [
        False,
        False,
        True,
        True,
    ]
    assert {
        slot["synthetic_reason"] for slot in section["slots"] if slot["synthetic"]
    } == {"page_detection_failed"}
    assert sorted(
        page["homography_status"] for page in section["scan"]["pages"]
    ) == ["resolved", "unresolved"]
    assert {page["qr_status"] for page in section["scan"]["pages"]} == {"decoded"}


def trois_planches_cli() -> list[dict]:
    """**TROIS** planches, pour que la cible puisse etre ailleurs qu'en derniere.

    `cli_pages()` en produit deux, et sa docstring justifie « deux et non une »
    sans jamais aller jusqu'a trois. C'est ce qui a laisse survivre les mutants
    de TERMINAISON de boucle de `_scanned_pages_for_output` (revue de la
    vague 3, couche 2, finding `C1`) : a deux planches, la cible en seconde
    position est aussi la **derniere**, et `continue` -> `break` y est
    indiscernable. `CLAUDE.md`, regle des fabriques, point 2 bis.
    """
    return [
        make_payload(page_index=index, page_count=3, slot_count=2)
        for index in range(3)
    ]


def test_une_planche_ILLISIBLE_AU_MILIEU_n_empeche_PAS_les_SUIVANTES(
    tmp_path: Path,
) -> None:
    """**Le mutant `continue` -> `break`, ferme sur la vraie boucle du produit.**

    Trois mutants de terminaison survivaient dans `_scanned_pages_for_output`
    (`scan_write.py:842-887`) : 288 tests verts alors qu'un `break` fait
    **abandonner toutes les planches suivantes**. Sur un lot de douze planches
    dont la troisieme echoue, neuf planches disparaissent de l'ecriture -- ni
    frames, ni mires, ni declaration.

    **La cause etait une fabrique, pas une garde manquante**, et elle a ete
    instrumentee plutot que devinee : la seule fabrique qui atteignait ces
    branches placait sa cible en **derniere** position de `report.pages`. Un
    cas est particulierement instructif -- une fixture voisine EFFACE le QR de
    `page_index == 1` sur trois pages et se croit conforme (« une page jamais
    identifiee **entre deux pages identifiees** »), mais l'ordre de
    `report.pages` n'est pas celui des `page_index` : la cible y est derniere.
    **Le point 2 bis se verifie sur la liste que le code ITERE, jamais sur
    celle que la fabrique ecrit.**

    Ce banc mesure donc les DEUX moities : la planche du milieu est declaree en
    echec ET les frames de la planche qui la SUIT existent pour de vrai.
    """
    payloads = trois_planches_cli()
    folder = write_cli_folder(tmp_path / "lot-a", payloads, broken=(1,))
    project_dir = tmp_path / "projet"

    assert run_scan(project_dir, folder) == LOT_AVEC_MIRES_MAIS_ECRIT

    document = validate_manifest(project_dir / MANIFEST_FILENAME)
    lot = lot_of(document)
    # Trois planches a deux emplacements : six frames au total, dont deux de
    # remplacement pour la planche du MILIEU -- donc QUATRE vraies.
    assert lot["reconstructed_frame_count"] == 4, (
        "les frames des planches qui SUIVENT l'echec doivent exister : un "
        "`break` a la place du `continue` les ferait disparaitre")
    assert lot["synthetic_frame_count"] == 2

    section = document["reconstruction"]
    # **Les TROIS planches sont declarees**, pas seulement celles d'avant
    # l'echec. C'est le volet qui distingue « abandonnee » de « en echec ».
    assert len(section["scan"]["pages"]) == 3, section["scan"]["pages"]
    assert "missing_pages" not in section, "aucune planche n'est MANQUANTE"
    # Et le remplacement porte sur les emplacements du MILIEU, pas de la fin :
    # une boucle qui s'arreterait a l'echec les placerait ailleurs.
    assert [slot["synthetic"] for slot in section["slots"]] == [
        False, False, True, True, False, False]


def test_the_scan_command_is_idempotent_on_a_lot_carrying_mires(
    tmp_path: Path, capsys
) -> None:
    """Le defaut d'EPIC5-ARB-33 tel qu'un operateur le rencontrait: relancer
    `scan --overwrite` sur un lot dont une planche reste illisible. Avant
    correction, la seconde passe rendait `0 frame(s) reconstruite(s), 4 de
    remplacement` pour un lot qui en porte deux vraies -- en code `0` et avec le
    mot « succes »."""
    payloads = cli_pages()
    folder = write_cli_folder(tmp_path / "lot-a", payloads, broken=(1,))
    project_dir = tmp_path / "projet"

    assert run_scan(project_dir, folder) == LOT_AVEC_MIRES_MAIS_ECRIT
    path = project_dir / MANIFEST_FILENAME
    before = path.read_bytes()

    assert run_scan(project_dir, folder, "--overwrite") == LOT_AVEC_MIRES_MAIS_ECRIT
    assert path.read_bytes() == before

    repaired = write_cli_folder(tmp_path / "lot-b", payloads)
    capsys.readouterr()
    assert run_scan(project_dir, repaired, "--overwrite") == 0

    lot = lot_of(validate_manifest(path))
    assert lot["reconstructed_frame_count"] == 4
    assert lot["synthetic_frame_count"] == 0
    assert lot["synthetic_frames"] == []
    assert "complet" in capsys.readouterr().out


def test_the_scan_command_refuses_to_degrade_real_frames_before_writing(
    tmp_path: Path, capsys
) -> None:
    """EPIC5-ARB-34, clause 2, par la commande reelle: sans le drapeau la passe
    est refusee et **rien** n'est detruit; avec lui la degradation a lieu et
    elle est **nommee** au compte rendu."""
    payloads = cli_pages()
    good = write_cli_folder(tmp_path / "lot-a", payloads)
    broken = write_cli_folder(tmp_path / "lot-b", payloads, broken=(1,))
    project_dir = tmp_path / "projet"
    assert run_scan(project_dir, good) == 0
    frames_before = output_frames_digest(project_dir)
    capsys.readouterr()

    assert run_scan(project_dir, broken) == 1

    assert output_frames_digest(project_dir) == frames_before
    assert "Regression de scan" in capsys.readouterr().err

    assert run_scan(project_dir, broken, "--overwrite") == LOT_AVEC_MIRES_MAIS_ECRIT
    assert output_frames_digest(project_dir) != frames_before
    lot = lot_of(validate_manifest(project_dir / MANIFEST_FILENAME))
    assert lot["synthetic_frame_count"] == 2
    assert sm.SCAN_REAL_FRAMES_DEGRADED in (
        project_dir / LOGS_DIRNAME / "scan.log"
    ).read_text(encoding="utf-8")


def test_the_scan_command_refuses_a_stale_plate_without_touching_the_frames(
    tmp_path: Path,
) -> None:
    """R12 de bout en bout, et dans le bon ordre: une planche perimee du meme
    lot porte les **memes noms de fichiers** par construction. Avec
    `--overwrite`, les frames legitimes etaient donc detruites, puis la commande
    refusait en annoncant « aucune ecriture n'a eu lieu »."""
    project_dir = tmp_path / "projet"
    first = write_scan_folder(tmp_path / "lot-a", [cli_payload()])
    assert run_scan(project_dir, first) == 0
    frames_before = output_frames_digest(project_dir)
    manifest_before = (project_dir / MANIFEST_FILENAME).read_bytes()

    stale = write_scan_folder(
        tmp_path / "lot-b", [cli_payload(patch_preset_id="patch-values-1")]
    )
    assert run_scan(project_dir, stale, "--overwrite") == 1

    assert output_frames_digest(project_dir) == frames_before
    assert (project_dir / MANIFEST_FILENAME).read_bytes() == manifest_before


def test_the_scan_parser_carries_the_overwrite_flag(tmp_path: Path) -> None:
    """Un seul drapeau pour les deux ecritures: c'est une seule intention."""
    folder = write_scan_folder(tmp_path / "lot-a", [cli_payload()])
    project_dir = tmp_path / "projet"

    # Sans le drapeau, argparse ne connait pas l'option et sort en code 2.
    with pytest.raises(SystemExit) as excinfo:
        cli.main(
            [
                "scan",
                "--project",
                str(project_dir),
                "--scan",
                str(folder),
                "--dpi",
                str(CLI_DPI),
                "--ecraser",
            ]
        )
    assert excinfo.value.code == 2


# ---------------------------------------------------------------------------
# Revue de 5.22, finding `E-F1` -- « liste triee » etablie sur deux elements
# ---------------------------------------------------------------------------


def _passe_de_scan(tmp_path: Path, chain_ids: tuple[str, ...],
                   *, existing: dict | None = None, overwrite: bool = False) -> dict:
    """Faire traverser un lot corrige par `chain_ids` et rendre le manifest fusionne."""
    payloads = [make_payload(page_index=index, page_count=len(chain_ids))
                for index in range(len(chain_ids))]
    report = write_report(tmp_path, [scanned_page(payload) for payload in payloads],
                          overwrite=overwrite)
    record = make_record(payloads, report,
                         page_calibrations=calibration_results_for_chains(chain_ids))
    return sm.build_scan_manifest(existing, record).manifest


def _chaines_consignees(tmp_path: Path, chain_ids: tuple[str, ...],
                        *, existing: dict | None = None) -> list[str]:
    """La liste des chaines ecrite au projet apres une passe."""
    return _passe_de_scan(
        tmp_path, chain_ids, existing=existing)["color"][sm.CALIBRATION_CHAINS_KEY]


def test_les_chaines_du_projet_sont_triees_et_non_dans_l_ordre_de_scan(
    tmp_path: Path,
) -> None:
    """Le champ est annonce **trie**, et il faut six entrees pour le prouver.

    Finding `E-F1` de la couche 2 de la revue de 5.22: le test qui gardait cette propriete
    operait sur un ensemble de **deux** chaines, inserees `chaine-a` puis `chaine-b`,
    c'est-a-dire deja dans l'ordre trie. Il ne distinguait donc pas « trie » de « ordre
    d'insertion », et le mutant qui retire `sorted()` **survivait integralement sous
    `PYTHONHASHSEED=3`** -- l'ordre d'iteration d'un `set` dependant de la graine de
    hachage du processus, la propriete tenait a pile ou face.

    Ce que le tri sert: deux projets ayant vu les memes chaines dans un ordre different
    doivent rendre le **meme** document. L'ordre de scan n'est pas une donnee.
    """
    consignees = _chaines_consignees(tmp_path, CHAINES_DESORDONNEES)
    assert consignees == sorted(CHAINES_DESORDONNEES)
    # Et le volet qui rend l'assertion falsifiable: l'ordre d'insertion est **different**
    # de l'ordre trie, donc l'egalite ci-dessus ne peut pas etre satisfaite par une
    # implementation qui rendrait l'ordre d'arrivee.
    assert list(CHAINES_DESORDONNEES) != sorted(CHAINES_DESORDONNEES)
    # La cible du tri -- la chaine qui doit sortir **en tete** -- a ete scannee en
    # **derniere** position: un `find` ou un tri fautif qui rendrait le premier element
    # rencontre ne se demasque pas autrement.
    assert CHAINES_DESORDONNEES[-1] == "chaine-a"
    assert consignees[0] == "chaine-a"


def test_les_chaines_deja_connues_du_projet_sont_fusionnees_et_retriees(
    tmp_path: Path,
) -> None:
    """La monotonie ne doit pas rendre l'ordre dependant de ce que le document portait.

    Une passe connait un seul lot, donc elle **ajoute** aux chaines deja consignees plutot
    que d'ecrire par-dessus. Si le tri ne portait que sur la nouveaute, un document
    precedent ecrit a la main -- ou par une version anterieure -- ferait rendre une liste
    dont l'ordre depend de son propre passe. Les valeurs preexistantes sont donc posees
    **en desordre**, et deux d'entre elles sont deja connues du scan: le dedoublonnage et
    le tri se mesurent ensemble.
    """
    premiere = ("chaine-x", "chaine-b", "chaine-d", "chaine-m", "chaine-y", "chaine-c")
    manifest = _passe_de_scan(tmp_path, premiere)
    deja = manifest["color"][sm.CALIBRATION_CHAINS_KEY]
    assert deja == sorted(premiere)
    # La seconde passe rescanne le meme lot sur d'autres chaines, dont **deux deja
    # connues**: le dedoublonnage et le tri se mesurent ensemble.
    consignees = _passe_de_scan(
        tmp_path, CHAINES_DESORDONNEES, existing=manifest, overwrite=True,
    )["color"][sm.CALIBRATION_CHAINS_KEY]
    assert consignees == sorted(set(premiere) | set(CHAINES_DESORDONNEES))
    for repetee in ("chaine-m", "chaine-c"):
        assert consignees.count(repetee) == 1, repetee
    # Et la seconde passe n'a rien **desappris**: la monotonie du champ est ce qui empeche
    # un rescan de faire disparaitre les chaines des lots deja numerises.
    assert set(deja) <= set(consignees)


# --------------------------------------------------------------------------
# `EPIC11-ARB-176` -- le scan persiste le RANG DE TIRAGE lu au QR
# --------------------------------------------------------------------------
#
# Le chainon manquant. Le rang traversait deja l'impression, le papier et le
# decodage ; il s'arretait juste avant d'etre **ecrit**. Ce qui suit mesure
# qu'il l'est, ce qu'il vaut quand il ne se lit pas, et qu'il ne s'ecrase
# jamais.


#: Trois rangs dont l'ensemble Python NE s'itere PAS dans l'ordre croissant
#: (`list({1, 2, 8}) == [8, 1, 2]`, table de huit alveoles, `hash(n) == n`).
#:
#: Le choix est mesure, pas decoratif : la politique du depot classe l'ordre
#: d'iteration en famille que mutmut **ne sait pas muter** (section 4.0(c)) et
#: qu'il faut donc epingler a la main. Avec trois rangs consecutifs, retirer le
#: `sorted()` de `_apprendre_les_rangs_de_tirage_scannes` ne changerait rien --
#: l'ensemble sortirait deja trie -- et le mutant survivrait sans qu'aucun test
#: ne bouge.
RANGS_DONT_L_ENSEMBLE_EST_DESORDONNE = (8, 2, 1)


def _rangs_scannes(manifest: dict, lot_id: str = LOT) -> list[int]:
    return lot_of(manifest, lot_id).get(sm.SCANNED_VERSION_RANKS_FIELD)


def test_le_scan_ecrit_l_ensemble_EXACT_des_rangs_de_tirage_lus_au_QR(
    tmp_path: Path,
) -> None:
    """`EPIC11-ARB-176`, le chainon : le rang decode atteint le manifeste.

    **Trois planches aux rangs distinguables, la cible au MILIEU** (regle des
    fabriques, point 2 bis) : un `break` a la place du `continue` de la boucle,
    ou un `payloads[:1]`, perdrait les rangs qui suivent le premier. Une
    fabrique a deux elements ne le verrait pas -- la cible y serait aussi la
    derniere.

    L'assertion porte sur l'ensemble **exact** : « 2 y figure » laisserait
    passer un rang de plus, c'est-a-dire un tirage declare scanne qui ne l'a
    pas ete, donc un refus d'ecrasement sur un objet innocent.
    """
    project_dir = tmp_path / "projet"
    haut, cible, bas = RANGS_DONT_L_ENSEMBLE_EST_DESORDONNE
    pile = [
        make_payload(page_index=0, page_count=3, version_rank=haut),
        make_payload(page_index=1, page_count=3, version_rank=cible),
        # Rang 1 : la planche d'origine, dont le champ est **omis** du payload.
        make_payload(page_index=2, page_count=3, version_rank=None),
    ]
    assert bas == 1, "le troisieme rang de la fabrique est le rang d'origine"

    persisted = scan_once(project_dir, pile)

    assert _rangs_scannes(persisted.manifest) == [1, 2, 8]
    # Et le document ECRIT reste valide : le champ est DECLARE au schema, pas
    # glisse dans un `additionalProperties: false`.
    assert _rangs_scannes(validate_manifest(persisted.manifest_path)) == [1, 2, 8]


def test_le_rang_est_TRIE_et_non_rendu_dans_l_ordre_d_un_ensemble(
    tmp_path: Path,
) -> None:
    """Le tri n'est pas cosmetique : c'est l'idempotence octet a octet.

    `sort_keys` canonise les mappings et **pas** les tableaux (story 5.7,
    AC 10). Un tableau rendu dans l'ordre d'iteration d'un `set` porterait donc
    un ordre que rien ne garantit d'une version de Python a l'autre, et deux
    passes identiques cesseraient d'etre comparables au fichier.
    """
    lot: dict = {}
    pile = [
        make_payload(page_index=rang % 2, version_rank=None if rang == 1 else rang)
        for rang in RANGS_DONT_L_ENSEMBLE_EST_DESORDONNE
    ]
    sm._apprendre_les_rangs_de_tirage_scannes(lot, pile)

    ecrit = lot[sm.SCANNED_VERSION_RANKS_FIELD]
    assert ecrit == [1, 2, 8]
    # Le temoin qui donne son sens au precedent: l'ensemble des memes rangs, lui,
    # ne sort pas trie. Sans lui, `== [1, 2, 8]` serait vrai meme sans `sorted()`.
    assert list({1, 2, 8}) != [1, 2, 8]


def test_une_planche_d_AVANT_le_rang_ecrit_1_EXPLICITEMENT(tmp_path: Path) -> None:
    """« `v` absent vaut 1 » traverse -- et il traverse parce qu'il MESURE.

    Avant `EPIC11-ARB-91` le rang n'existait pas : toute planche imprimee alors
    **est** le tirage d'origine. Verbatim d'Egan : « les anciens payloads qui ne
    portaient pas de version (2.1) sont tout de meme decodes avec v=1 ».

    Et il s'ecrit **explicitement**, a l'inverse du payload et du nom de fichier
    qui l'omettent tous deux : omis ici, `[1]` serait indiscernable de la liste
    vide, donc « le tirage d'origine a ete scanne » indiscernable de « aucun
    tirage ne l'a ete ».
    """
    project_dir = tmp_path / "projet"
    persisted = scan_once(project_dir, two_pages(version_rank=None))

    lot = lot_of(persisted.manifest)
    assert sm.SCANNED_VERSION_RANKS_FIELD in lot
    assert lot[sm.SCANNED_VERSION_RANKS_FIELD] == [1]


def test_une_page_dont_le_QR_n_a_rien_livre_n_ajoute_AUCUN_rang(
    tmp_path: Path,
) -> None:
    """Le repli du rang illisible, **asserte** et non implicite (AC 7.11c).

    C'est la reserve explicite d'`EPIC11-ARB-176` : la convention « `v` absent
    vaut 1 » repond pour le **payload**, pas pour le **scan rate**. Une page
    dont le QR ne s'est pas decode ne produit aucun payload ; elle ne contribue
    donc aucun rang, et surtout pas `1`.

    Ce serait la faute d'`extraction.CriteresIdentiteRush` -- « une duree
    absente stockee `0` affirmerait un flux vide la ou la source n'a rien dit »
    -- avec deux faussetes d'un coup : le tirage d'origine declare scanne alors
    qu'il n'a peut-etre jamais ete imprime, et le tirage dont la feuille venait
    reellement laisse ecrasable.

    Le fait n'est pas perdu pour autant, et le test le mesure aussi : il est
    ecrit, par page, en `reconstruction.scan.pages[].qr_status`.
    """
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    lisibles = [
        make_payload(page_index=0, page_count=3, version_rank=4),
        make_payload(page_index=1, page_count=3, version_rank=4),
    ]
    report = write_report(project_dir, [scanned_page(p) for p in lisibles])
    record = sm.ScanRecord(
        page_payloads=tuple(lisibles),
        output_report=report,
        scan_dpi=600,
        ingest_slug="lot-a",
        pages=(
            provenance(0),
            provenance(1),
            # La troisieme feuille etait bien sur la vitre: elle a ete lue, et
            # son QR n'a rien rendu. `page_index=None` est ce que la chaine de
            # detection remet dans ce cas -- elle ne sait meme pas quelle page
            # du lot c'etait, donc a fortiori pas de quel tirage.
            sm.ScanPageProvenance(
                read_rank=2,
                status=scan_detection.PAGE_REFUSED,
                qr_status=scan_detection.qr_codes.DECODE_UNREADABLE,
                page_index=None,
                homography_status=sm.HOMOGRAPHY_UNRESOLVED,
            ),
        ),
    )
    persisted = sm.persist_scan(project_dir, record)

    assert _rangs_scannes(persisted.manifest) == [4]
    # L'ensemble est EXACT, et c'est ce bout-la qui ferme le repli: un `1`
    # ajoute « au cas ou » rendrait `[1, 4]`.
    assert 1 not in _rangs_scannes(persisted.manifest)
    illisibles = [
        page for page in persisted.manifest["reconstruction"]["scan"]["pages"]
        if page["qr_status"] != scan_detection.qr_codes.DECODE_OK
    ]
    assert len(illisibles) == 1 and illisibles[0]["page_index"] is None


def test_un_rescan_APPREND_un_rang_et_n_en_DESAPPREND_aucun(tmp_path: Path) -> None:
    """Union, jamais ecrasement -- le modele exact de `_learn_printed_identifiers`.

    L'effet d'un ecrasement serait precis et destructeur : rescanner le `v8`
    d'un lot dont le `v1` avait ete scanne rendrait le `v1` a nouveau
    ecrasable, alors que sa feuille est posee sur un bureau. C'est la regle que
    ce module tient partout, « enrichir ne fait jamais desapprendre ».
    """
    project_dir = tmp_path / "projet"
    premier = scan_once(project_dir, two_pages(version_rank=None))
    assert _rangs_scannes(premier.manifest) == [1]

    second = scan_once(project_dir, two_pages(version_rank=8), overwrite=True)
    assert _rangs_scannes(second.manifest) == [1, 8]

    troisieme = scan_once(project_dir, two_pages(version_rank=2), overwrite=True)
    assert _rangs_scannes(troisieme.manifest) == [1, 2, 8]


def test_un_manifeste_ANTERIEUR_ne_porte_pas_la_cle_et_son_absence_ne_vaut_pas_1(
    tmp_path: Path,
) -> None:
    """Additif : l'absence dit « on ne sait pas », jamais « le rang 1 ».

    Un lot ne de l'extraction n'a jamais rien vu passer au scanner. Lui prêter
    le rang 1 par defaut interdirait d'ecraser un tirage que personne n'a
    imprime -- le blocage sec sur un objet innocent qu'`EPIC11-ARB-89`
    proscrit.
    """
    riche = rich_extraction_manifest()
    assert sm.SCANNED_VERSION_RANKS_FIELD not in lot_of(riche)
    chemin = write_manifest(tmp_path / "projet", riche)
    assert sm.SCANNED_VERSION_RANKS_FIELD not in lot_of(validate_manifest(chemin))

    # Et la cle n'est jamais ecrite VIDE: une liste vide affirmerait « aucun
    # tirage scanne » sur un lot dont l'etat dit `scan`, deux affirmations
    # contradictoires dans le meme document. Le schema le refuse aussi
    # (`minItems: 1`), et le chemin de code ne peut pas l'atteindre --
    # `ScanRecord` refuse une passe sans aucun payload decode.
    with pytest.raises(sm.ScanPersistenceError):
        sm.ScanRecord(
            page_payloads=(), output_report=object(), scan_dpi=600, ingest_slug="x",
        )


def test_une_valeur_INEXPLOITABLE_deja_au_manifeste_n_est_pas_reecrite(
    tmp_path: Path,
) -> None:
    """Lecture defensive : ce qui n'est pas un rang n'est pas un rang.

    Le schema borne les entrees a `[1, 99]` et refuse les non-entiers ; ce que
    ce module ne doit surtout pas faire est de **recopier** une valeur hors
    domaine dans un document qu'il s'apprete a valider -- l'echec sortirait
    alors sur la validation finale, loin de sa cause. Les bornes sont **lues**
    chez leurs proprietaires (`naming.VERSION_RANK_MAX`,
    `version_ranks.RANG_ORIGINE`) et jamais recopiees ici.
    """
    lot = {sm.SCANNED_VERSION_RANKS_FIELD: [
        3, "4", None, True, 0, sm.VERSION_RANK_MAX + 1, sm.RANG_ORIGINE - 1,
    ]}
    sm._apprendre_les_rangs_de_tirage_scannes(
        lot, [make_payload(page_index=0, version_rank=7)])

    # `3` survit (c'est un rang), `7` s'ajoute, tout le reste tombe. `True` est
    # un piege a part: `bool` est un `int` en Python, et sans `is_strict_int` il
    # entrerait comme un rang 1 -- c'est-a-dire qu'il inventerait le tirage
    # d'origine a partir d'une valeur corrompue.
    assert lot[sm.SCANNED_VERSION_RANKS_FIELD] == [3, 7]


def test_payload_version_rank_a_desormais_AU_MOINS_UN_site_d_appel_dans_src() -> None:
    """La frontiere du chainon (AC 7.11a) : il n'en avait AUCUN.

    Mesure du 2026-09-02, qui a fonde `EPIC11-ARB-176` : `payload_version_rank`
    savait relire le rang et personne ne l'appelait. Un test qui mesurerait
    seulement le contenu du manifeste laisserait re-deriver la lecture ailleurs
    -- un `payload.get("version_rank") or 1` recopie --, ce que le point
    d'entree unique d'`EPIC11-ARB-91` proscrit nommement.
    """
    racine = REPO_ROOT / "src" / "mixed_media_utility"
    definition = racine / "io" / "payload.py"
    appelants: dict[str, int] = {}
    for chemin in sorted(racine.rglob("*.py")):
        arbre = ast.parse(chemin.read_text(encoding="utf-8"), filename=str(chemin))
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.Call):
                continue
            cible = noeud.func
            nom = (cible.id if isinstance(cible, ast.Name)
                   else cible.attr if isinstance(cible, ast.Attribute) else None)
            if nom == "payload_version_rank":
                appelants[str(chemin.relative_to(racine))] = (
                    appelants.get(str(chemin.relative_to(racine)), 0) + 1)

    assert appelants, (
        "`payload_version_rank` n'a aucun site d'appel: le rang de tirage "
        "s'arrete encore avant d'etre ecrit (EPIC11-ARB-176)")
    assert definition.is_file(), definition
    # Et l'appelant est bien la chaine de scan, pas seulement le module qui
    # definit la fonction: sans ce second volet, ajouter un appel interne a
    # `io/payload.py` suffirait a rendre le test vert sans que le rang atteigne
    # jamais un manifeste.
    assert "io/scan_manifest.py" in appelants, sorted(appelants)
