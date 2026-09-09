# -*- coding: utf-8 -*-
"""Fabriques de documents de detection pour les tests de la story 7.4.

**La regle des fabriques du depot est le contrat de ce module**, et 7.4 est
precisement le regime ou elle a mordu cinq fois (5.6/M33, 5.7/M25, 5.8) :
quatre collections imbriquees -- pages, emplacements, zones, marqueurs.

1. **toute fabrique de collection produit au moins deux elements
   distinguables** : deux pages de rangs et d'index DESALIGNES, deux zones de
   tailles et de timecodes differents, quatre marqueurs a quatre centres
   differents. Jamais un remplissage uniforme -- une permutation ne se voit
   que si les elements different ;
2. **la cible de reference n'est jamais en premiere position** : les helpers
   de haut niveau placent la page visee en SECONDE position, pour qu'un
   lecteur qui rendrait toujours le premier element se demasque ;
3. la variante multi-elements est ecrite **ici**, dans la story, pas renvoyee
   a la revue.

Les documents rendus sont des dictionnaires JSON dans la forme **normative**
de ``scan_previz`` : ils passent tous par ``scan_previz_from_json_dict``, donc
tout ecart de forme est refuse par le coeur et non par ce module.
"""

from mixed_media_utility import layout, qr_codes, scan_detection, scan_previz

#: Une empreinte de detection bien formee (prefixe + 64 hexadecimaux). Sa
#: valeur n'a aucun sens metier dans un test de GUI : seule sa FORME est
#: verifiee par le lecteur du coeur.
EMPREINTE = "sha256-v1:" + "ab12cd34" * 8

#: Les quatre centres de coin, **tous differents** : c'est ce qui rend une
#: permutation de deux centres visible. Une fixture a centres uniformes
#: laisserait passer un appariement inverse (mutant M33 de 5.6).
CENTRES_DE_COIN = {
    0: (120.5, 130.5),
    1: (3300.5, 140.5),
    2: (3310.5, 2200.5),
    3: (130.5, 2210.5),
}


def marqueur_de_coin(marker_id, read_rank, page_index):
    """Un marqueur de coin, a SON centre -- jamais un centre partage."""
    centre_x, centre_y = CENTRES_DE_COIN[marker_id]
    return {
        "address": {
            "read_rank": read_rank,
            "page_index": page_index,
            "marker_id": marker_id,
        },
        "marker_id": marker_id,
        "center_x_px": centre_x,
        "center_y_px": centre_y,
    }


def quatre_coins(read_rank, page_index):
    """Les quatre coins de ``layout.CORNER_MARKER_IDS``, distinguables."""
    return [
        marqueur_de_coin(identifiant, read_rank, page_index)
        for identifiant in layout.CORNER_MARKER_IDS
    ]


def marqueur_etranger(marker_id, role, read_rank, page_index):
    """Un marqueur etranger : identifiant + role, **sans coordonnees**.

    Le document n'en porte aucune, et c'est pour cela que l'ecran le LISTE et
    ne le dessine jamais.
    """
    return {
        "address": {
            "read_rank": read_rank,
            "page_index": page_index,
            "marker_id": marker_id,
        },
        "marker_id": marker_id,
        "role": role,
    }


def zone(
    slot_index,
    read_rank,
    page_index,
    *,
    largeur_px,
    hauteur_px,
    x_px=None,
    y_px=None,
    frame_timecode="__defaut__",
    zone_rect_px=None,
    frame_path_relative=None,
    synthetic=None,
    synthetic_reason=None,
):
    """Une zone de frame, dont chaque valeur DIFFERE de celle des voisines.

    ``crop_rect_px`` et ``zone_rect_px`` sont volontairement dissociables :
    les deux conventions de quantification du coeur ne coincident pas
    toujours (mesure par 5.2), et l'AC 3 exige que la taille affichee vienne
    de ``crop_*_px``.
    """
    if x_px is None:
        x_px = 100 + 40 * slot_index
    if y_px is None:
        y_px = 200 + 60 * slot_index
    if frame_timecode == "__defaut__":
        frame_timecode = f"01:0{slot_index}:1{slot_index}:0{slot_index}"
    rect_px = {"x": x_px, "y": y_px, "width": largeur_px, "height": hauteur_px}
    if zone_rect_px is None:
        # **Les deux rectangles DIVERGENT par defaut, et c'est fidele au
        # coeur.** 5.2 arrondit l'origine et la taille SEPAREMENT
        # (`round(x*k)` et `round(w*k)`), si bien qu'un bord de zone peut
        # differer d'un pixel du bord de decoupe -- mesure : 54 zones sur
        # 135 a 600 ppp. Une fabrique qui poserait les deux rectangles
        # EGAUX rendrait indetectable une surimpression lue du mauvais
        # champ : mesure par mutation le 2026-08-25, le mutant survivait a
        # tous les bancs. C'est la regle des fabriques appliquee a une
        # collection de DEUX champs concurrents.
        zone_rect_px = {
            "x": x_px + 1, "y": y_px, "width": largeur_px - 1, "height": hauteur_px
        }
    document = {
        "address": {
            "read_rank": read_rank,
            "page_index": page_index,
            "slot_index": slot_index,
        },
        "slot_index": slot_index,
        "frame_timecode": frame_timecode,
        "zone_name": f"frame_zone_{slot_index + 1}",
        "zone_rect_mm": {
            "x": float(x_px) / 10.0,
            "y": float(y_px) / 10.0,
            "width": float(largeur_px) / 10.0,
            "height": float(hauteur_px) / 10.0,
        },
        "crop_rect_mm": {
            "x": float(x_px) / 10.0,
            "y": float(y_px) / 10.0,
            "width": float(largeur_px) / 10.0,
            "height": float(hauteur_px) / 10.0,
        },
        "crop_rect_px": dict(rect_px),
        "zone_rect_px": dict(zone_rect_px),
        "frame_path_relative": frame_path_relative,
    }
    # Le drapeau accompagne le chemin, `false` compris (EPIC5-ARB-8).
    if frame_path_relative is not None:
        document["synthetic"] = bool(synthetic)
        if synthetic:
            document["synthetic_reason"] = synthetic_reason or "FRAME_MANQUANTE"
    return document


def deux_zones(read_rank, page_index, premier_slot=0):
    """DEUX zones de tailles, positions et timecodes differents.

    La fabrique par defaut d'une collection de zones n'est jamais
    mono-element : un appariement positionnel inverse resterait invisible.
    """
    return [
        zone(
            premier_slot,
            read_rank,
            page_index,
            largeur_px=1337 + 11 * premier_slot,
            hauteur_px=752 + 7 * premier_slot,
        ),
        zone(
            premier_slot + 1,
            read_rank,
            page_index,
            largeur_px=1401 + 11 * premier_slot,
            hauteur_px=799 + 7 * premier_slot,
        ),
    ]


def page(
    read_rank,
    page_index,
    *,
    page_count=4,
    status=scan_detection.PAGE_OK,
    qr_status=qr_codes.DECODE_OK,
    refusal_reason=None,
    code_de_refus=None,
    identite=True,
    homographie=True,
    coins=True,
    zones=None,
    foreign_markers=(),
    template_source="qr",
    largeur_px=3508,
    hauteur_px=2480,
    source_path_relative=None,
):
    """Une page du document, dans la forme normative de ``scan_previz``.

    ``code_de_refus`` n'est pose que s'il est demande explicitement : **aucun
    document reel ne le porte au 2026-08-25** (la story de coeur 5.27 n'est
    pas livree), et une fabrique qui l'ajouterait par defaut mentirait sur
    l'etat du depot.
    """
    if zones is None:
        zones = deux_zones(read_rank, page_index) if status == scan_detection.PAGE_OK else []
    adresse = {"read_rank": read_rank, "page_index": page_index}
    document = {
        "address": dict(adresse),
        "read_rank": read_rank,
        "page_index": page_index,
        "page_count": page_count,
        "status": status,
        "qr_status": qr_status,
        "refusal_reason": refusal_reason,
        "source": {
            "path_relative": source_path_relative
            or f"scans/lot/page_{read_rank:02d}.png",
            "page_index": 0,
            "scan_input_format": "png",
            "source_bit_depth": 8,
            "width_px": largeur_px,
            "height_px": hauteur_px,
            "channels": 3,
        },
        "decoded_identity": {
            "project_id": "chendj-mat" if identite else None,
            "rush_id": "rush-bitch-4-chendj-mat" if identite else None,
            "lot_id": "rush-bitch-4-chendj-mat_1-c60b2a76" if identite else None,
            "gamut_map_id": "gamut-map-none-1" if identite else None,
        },
        "template_id": "tpl-a4-paysage-4f-v2",
        "template_source": template_source,
        "page_size_px": [largeur_px, hauteur_px] if homographie else None,
        "homography": (
            [1.0, 0.0, 0.5, 0.0, 1.0, 0.6, 0.0, 0.0, 1.0] if homographie else None
        ),
        "scale": (
            {"scale_x": 1.0, "scale_y": 1.0004, "residual_px": 0.41}
            if homographie
            else None
        ),
        "corner_markers": quatre_coins(read_rank, page_index) if coins else [],
        "foreign_markers": list(foreign_markers),
        "frame_zones": list(zones),
        "calibration": {"status": "not_applied"},
        "warnings": [],
    }
    if code_de_refus is not None:
        document[
            "refusal_code"  # cf. lecture_detection.CLE_CODE_DE_REFUS
        ] = code_de_refus
    return document


def document(pages, *, pages_expected=None):
    """L'enveloppe du document autour d'une liste de pages.

    Aucun cardinal n'est devine : ``pages_present`` compte les pages
    reellement passees, et le lecteur du coeur refuse toute divergence.
    """
    return {
        "previz_schema_version": scan_previz.PREVIZ_SCHEMA_VERSION,
        "kind": scan_previz.SCAN_PREVIZ_KIND,
        "state": scan_previz.SCAN_PREVIZ_STATE_DETECTED,
        "generated_at_utc": "2026-08-25T12:00:00Z",
        "subject": {
            "project_id": "chendj-mat",
            "rush_id": "rush-bitch-4-chendj-mat",
            "lot_id": "rush-bitch-4-chendj-mat_1-c60b2a76",
            "ingest_slug": "lot",
            "template_id": "tpl-a4-paysage-4f-v2",
            "gamut_map_id": "gamut-map-none-1",
            "fps_target_exact": "24/1",
            "target_colorspace": "bt709",
            "patch_preset_id": "patches-17-v4",
            "scan_dpi_declared": 300,
            "scan_dpi_detection": 300,
            "scans_dir_relative": "scans/lot",
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
        "fingerprints": {"detection": EMPREINTE, "selection": None},
    }


# ---------------------------------------------------------------------------
# Helpers de haut niveau : la cible n'est JAMAIS en premiere position
# ---------------------------------------------------------------------------

#: Adresse de la page VISEE par les tests batis sur `deux_pages_cible_seconde`.
#: `read_rank` 2 et `page_index` 1 : volontairement DESALIGNES -- la page lue
#: en second declare etre la page 1 du lot, et la page lue en premier declare
#: etre la page 3. Deduire l'un de l'autre casse ici, et nulle part ailleurs.
ADRESSE_CIBLE = (2, 1)
ADRESSE_LEURRE = (1, 3)


#: Le lot **0-based** de reference, et pourquoi il existe : le coeur numerote
#: les planches **a partir de zero** (`pdf_composition` : « `page_index` base
#: zero », `page_roles.CALIBRATION_PAGE_INDEX` vaut 0, et le document reel de
#: `tests/fixtures/detection-scan-reelle/` porte `page_index: 0`). Les
#: fabriques ci-dessus numerotent a partir de 1 -- c'etait sans consequence
#: tant que rien ne derivait la completude, et la revue de vague 3 a mesure ce
#: que cela cachait (finding F11) : sur un lot 0-based dont la PREMIERE
#: planche manque, l'heuristique d'origine nommait manquante une planche qui
#: n'existe pas et taisait celle qui manque.
LOT_0_BASED_CARDINAL = 3


def lot_0_based_premiere_planche_absente():
    """Deux planches d'un lot de TROIS, 0-based, dont la planche ``0`` manque.

    Regle des fabriques, appliquee ici comme ailleurs : deux elements
    **distinguables** (rangs de lecture et numeros de planche desalignes,
    zones de tailles differentes), et la planche visee -- la ``1``, celle qui
    suit immediatement le trou -- **n'est pas en premiere position**. Les
    pages sont de surcroit posees a l'envers du numero de planche : c'est
    l'ordre qu'un scan physique produit, et celui ou la galerie doit malgre
    tout afficher par numero (`EPIC7-ARB-76`).
    """
    return document([
        page(2, 2, page_count=LOT_0_BASED_CARDINAL,
             zones=deux_zones(2, 2, premier_slot=2)),
        page(1, 1, page_count=LOT_0_BASED_CARDINAL),
    ])


def deux_pages_cible_seconde(**surcharges_cible):
    """Deux pages distinguables, la CIBLE en seconde position.

    Le leurre porte des zones d'un autre jeu de ``slot_index`` et d'autres
    tailles : un rendu qui prendrait la premiere page se voit immediatement.
    """
    rang_leurre, index_leurre = ADRESSE_LEURRE
    rang_cible, index_cible = ADRESSE_CIBLE
    leurre = page(
        rang_leurre,
        index_leurre,
        zones=deux_zones(rang_leurre, index_leurre, premier_slot=2),
    )
    cible = page(rang_cible, index_cible, **surcharges_cible)
    return document([leurre, cible])
