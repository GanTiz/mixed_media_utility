# -*- coding: utf-8 -*-
"""Fabriques de fixtures du chutier (story 7.2).

**Regle des fabriques du depot, appliquee ici sans exception** (CLAUDE.md,
posee apres 5.6/`M33`, 5.7/`M25` et les cinq survivants de 5.8) :

1. toute fabrique de collection produit **au moins deux elements
   distinguables** -- des valeurs differentes partout (identifiants,
   cadences, cardinaux, etats), jamais un remplissage uniforme : une
   permutation ne se voit que si les elements different ;
2. **au moins un test place la cible ailleurs qu'en premiere position** --
   toutes les fabriques ci-dessous sont donc concues pour que la cible
   naturelle des assertions soit la **seconde** ;
3. la variante multi-elements est ecrite **dans la meme story**.

Les documents de detection produits ici sont des documents `scan_previz`
**reels** : ils passent par `scan_previz.scan_previz_from_json_dict` dans le
modele, qui les refuse s'ils ne sont pas des documents complets. Une fixture
qui derive de la forme normative echoue donc bruyamment, jamais en silence.
"""

from __future__ import annotations

#: Empreintes de detection distinguables : deux documents du meme lot ne
#: doivent jamais partager la leur (elles servent d'identifiant de scan).
_EMPREINTE_A = "sha256-v1:" + "a" * 64
_EMPREINTE_B = "sha256-v1:" + "b" * 64
_EMPREINTE_C = "sha256-v1:" + "c" * 64

EMPREINTES = (_EMPREINTE_A, _EMPREINTE_B, _EMPREINTE_C)


def page_detectee(
    read_rank,
    page_index,
    *,
    page_count=None,
    status="identified",
    qr_status="decoded",
    lot_id="lot-cadence-24",
    rush_id="rush-alpha",
    project_id="proj-demo",
    largeur_px=100,
):
    """Une page du document de detection, a la forme normative de 5.25/5.26.

    `read_rank` (ordre de lecture des fichiers) et `page_index` (numero de
    planche declare par le QR) sont **fournis separement** : jamais l'un
    deduit de l'autre (`scan_previz.PAGE_ADDRESS_FIELDS`).
    """
    adresse = {"read_rank": read_rank, "page_index": page_index}
    identifie = page_index is not None
    return {
        "address": adresse,
        "read_rank": read_rank,
        "page_index": page_index,
        "page_count": page_count,
        "status": status,
        "qr_status": qr_status,
        "refusal_reason": None,
        "source": {
            "path_relative": f"scans/{lot_id}/lu-{read_rank}.tif",
            "page_index": 0,
            "scan_input_format": "tiff",
            "source_bit_depth": 16,
            # Largeur DISTINGUABLE d'une page a l'autre : un appariement
            # positionnel fautif se voit sur une valeur, pas sur un
            # remplissage uniforme.
            "width_px": largeur_px,
            "height_px": 200,
            "channels": 3,
        },
        "decoded_identity": {
            "project_id": project_id if identifie else None,
            "rush_id": rush_id if identifie else None,
            "lot_id": lot_id if identifie else None,
            "gamut_map_id": "gamut-map-none-1" if identifie else None,
        },
        "template_id": "tpl-a4-portrait-2f-v1" if identifie else None,
        "template_source": "qr" if identifie else None,
        "page_size_px": [largeur_px, 200],
        "homography": None,
        "scale": None,
        "corner_markers": [],
        "foreign_markers": [],
        "frame_zones": [],
        "calibration": None,
        "warnings": [],
    }


def document_de_detection(
    *,
    lot_id,
    pages,
    pages_expected,
    rush_id="rush-alpha",
    project_id="proj-demo",
    fps_target_exact="24000/1001",
    empreinte=_EMPREINTE_A,
    ingest_slug=None,
):
    """Un document `scan_previz` en etat `detected` (story 5.25)."""
    slug = ingest_slug or f"ingest-{lot_id}"
    return {
        "previz_schema_version": "previz-1",
        "kind": "scan",
        "state": "detected",
        "generated_at_utc": "2026-08-25T10:00:00Z",
        "subject": {
            "project_id": project_id,
            "rush_id": rush_id,
            "lot_id": lot_id,
            "ingest_slug": slug,
            "template_id": "tpl-a4-portrait-2f-v1",
            "gamut_map_id": "gamut-map-none-1",
            "fps_target_exact": fps_target_exact,
            "target_colorspace": "bt709",
            "patch_preset_id": "patches-12-v1",
            "scan_dpi_declared": 600,
            "scan_dpi_detection": 600,
            "scans_dir_relative": f"scans/{slug}",
            "output_dir_relative": None,
        },
        "counters": {
            "pages_present": len(pages),
            "pages_expected": pages_expected,
            "frames_written": None,
            "frames_expected": None,
            "synthetic_frame_count": None,
        },
        "pages": list(pages),
        "warnings": {"ingest": [], "detection": [], "output": [], "previz": []},
        "fingerprints": {"detection": empreinte, "selection": None},
    }


def manifest_deux_lots_meme_rush():
    """Le cas nominal v2.1, celui du risque R12 : **deux lots du meme rush a
    deux cadences**, valeurs distinguables partout, cible en SECONDE position.

    * `lot-cadence-24` -- 24000/1001, 12 frames attendues, 12 reconstruites,
      0 mire : **complet** ;
    * `lot-cadence-18` -- 18/1, 9 frames attendues, 7 reconstruites,
      1 mire : **incomplet**. C'est la cible, et elle est seconde.
    """
    return {
        "schema_version": "2.1",
        "project_id": "proj-demo",
        "rushes": [
            {"rush_id": "rush-alpha", "source_path": "medias/alpha.mov"},
        ],
        "lots": [
            {
                "lot_id": "lot-cadence-24",
                "rush_id": "rush-alpha",
                "state": "reconstruction",
                "fps_target_exact": "24000/1001",
                "expected_frame_count": 12,
                "reconstructed_frame_count": 12,
                "synthetic_frame_count": 0,
                "output_frames_dir": "output-frames/rush-alpha_24",
            },
            {
                "lot_id": "lot-cadence-18",
                "rush_id": "rush-alpha",
                "state": "reconstruction",
                "fps_target_exact": "18/1",
                "expected_frame_count": 9,
                "reconstructed_frame_count": 7,
                "synthetic_frame_count": 1,
                "output_frames_dir": "output-frames/rush-alpha_18",
            },
        ],
    }


def manifest_deux_rushes_deux_lots_chacun():
    """Deux rushes distinguables, **deux lots chacun** (fabrique imposee par
    l'epic pour l'AC 4). Toutes les valeurs different ; la cible des
    assertions est le **second** rush.
    """
    return {
        "schema_version": "2.1",
        "project_id": "proj-demo",
        "rushes": [
            {"rush_id": "rush-alpha", "source_path": "medias/alpha.mov"},
            {"rush_id": "rush-beta", "source_path": "medias/beta.mov"},
        ],
        "lots": [
            {
                "lot_id": "lot-alpha-1",
                "rush_id": "rush-alpha",
                "state": "pdf",
                "fps_target_exact": "24000/1001",
                "expected_frame_count": 12,
            },
            {
                "lot_id": "lot-alpha-2",
                "rush_id": "rush-alpha",
                "state": "pdf",
                "fps_target_exact": "25/1",
                "expected_frame_count": 8,
            },
            {
                "lot_id": "lot-beta-1",
                "rush_id": "rush-beta",
                "state": "pdf",
                "fps_target_exact": "18/1",
                "expected_frame_count": 6,
            },
            {
                "lot_id": "lot-beta-2",
                "rush_id": "rush-beta",
                "state": "pdf",
                "fps_target_exact": "16/1",
                "expected_frame_count": 4,
            },
        ],
    }


def liaison_factice(chemins_vivants):
    """Verificateur d'existence injectable pour `relink.statut_de_liaison`.

    Aucun test du chutier ne touche le disque : les chemins declares vivants
    sont donnes explicitement, tout le reste est un chemin mort.
    """
    vivants = set(chemins_vivants)
    return lambda chemin: chemin in vivants


def manifest_six_types():
    """Une fixture qui porte les **six types de noeud** de la carte du
    double-clic (`EPIC7-ARB-11`), en valeurs toutes distinguables.

    * `rush-alpha` -- rush ordinaire, **premier** ;
    * `rush-beta` -- rush ENCODE (son lot porte un master), **second** :
      c'est la cible, et elle n'est pas en premiere position ;
    * `lot-alpha-1` -- lot ordinaire, avec un document de detection qui lui
      donne planches et scans ;
    * `lot-alpha-2` -- lot RECONSTRUIT (le manifest porte sa sortie),
      **second lot de son rush** ;
    * `lot-beta-1` -- lot du rush encode.
    """
    return {
        "schema_version": "2.1",
        "project_id": "proj-demo",
        "rushes": [
            {"rush_id": "rush-alpha", "source_path": "medias/alpha.mov"},
            {"rush_id": "rush-beta", "source_path": "medias/beta.mov"},
        ],
        "lots": [
            {
                "lot_id": "lot-alpha-1",
                "rush_id": "rush-alpha",
                "state": "pdf",
                "fps_target_exact": "24000/1001",
                "expected_frame_count": 12,
            },
            {
                "lot_id": "lot-alpha-2",
                "rush_id": "rush-alpha",
                "state": "reconstruction",
                "fps_target_exact": "25/1",
                "expected_frame_count": 6,
                "reconstructed_frame_count": 6,
                "synthetic_frame_count": 0,
                "output_frames_dir": "output-frames/rush-alpha_25",
            },
            {
                "lot_id": "lot-beta-1",
                "rush_id": "rush-beta",
                "state": "encode",
                "fps_target_exact": "18/1",
                "expected_frame_count": 4,
                "reconstructed_frame_count": 4,
                "synthetic_frame_count": 0,
                "output_frames_dir": "output-frames/rush-beta_18",
                "encoded_masters": [
                    {"path": "outputs/beta-mezzanine.mov", "profile_id": "prores-hq"}
                ],
            },
        ],
    }


def detection_de_lot_alpha_1():
    """Le document de detection qui donne planches et scans a `lot-alpha-1`.

    Deux pages DISTINGUABLES, et `page_index != read_rank` sur la seconde --
    la cible des assertions d'adressage n'est jamais la premiere page.
    """
    return document_de_detection(
        lot_id="lot-alpha-1",
        rush_id="rush-alpha",
        pages=[
            page_detectee(0, 0, lot_id="lot-alpha-1", largeur_px=110),
            page_detectee(2, 1, lot_id="lot-alpha-1", largeur_px=170),
        ],
        pages_expected=2,
        empreinte=EMPREINTES[2],
    )
