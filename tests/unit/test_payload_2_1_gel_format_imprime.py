"""Story 2.7, AC 7 -- gel du format imprime (`EPIC7-ARB-51`).

A partir de cette story, le format de payload 2.1 est FIGE : une planche
imprimee sous ce schema doit rester relisible par toute version ulterieure du
lecteur -- « le papier ne se met pas a jour ». C'est la materialisation du
jalon du 2026-09-02 verbatim d'Egan (« a une certaine date on forcera juste
les planches produites a pouvoir etre decodees »).

Ce test ne se « met pas a jour » quand le payload evolue : il PROTEGE le texte
d'une page de reference, epingle octet a octet dans
`tests/fixtures/payload-2-1-gel-format-imprime/page-reference.json`. Si une
story future doit le casser, c'est un arbitrage d'Egan qu'elle doit citer en
tete de ce fichier, jamais un diff silencieux.

Regime de reference : les memes identifiants que le banc de couts de
`test_page_payload.py` (`REFERENCE_IDS`), et une cadence source **NTSC**
(`"30000/1001"`) pour couvrir la valeur la plus longue que le champ porte en
pratique -- un gel mesure sur `"25/1"` masquerait un depassement de budget sur
la valeur reelle la plus couteuse.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import qr_codes
from mixed_media_utility.io import payload as payload_io

FIXTURE = (
    REPO_ROOT / "tests" / "fixtures" / "payload-2-1-gel-format-imprime"
    / "page-reference.json"
)

# Meme regime d'identifiants que `test_page_payload.py::REFERENCE_IDS` --
# reproductible, nomme, jamais improvise.
_PROJECT_ID = "demo-project-01"
_RUSH_ID = "rush-a1"
_LOT_ID = "lot-0007"
_TEMPLATE_ID = "tpl-a4-portrait-2f-v1"
_PATCH_PRESET_ID = "patches-12-v1"
# Cadence source NTSC : la forme `num/den` la plus longue couramment portee
# par un manifest reel (`codec_profiles.exact_frame_rate`).
_TIMECODE_BASE_FPS_NTSC = "30000/1001"


def _page_de_reference() -> dict:
    """La page 2.1 de reference, par son vrai producteur (`build_page_payload`)."""
    return payload_io.build_page_payload(
        project_id=_PROJECT_ID,
        rush_id=_RUSH_ID,
        lot_id=_LOT_ID,
        page_index=0,
        page_count=3,
        fps_target=24.0,
        timecode_base_fps=_TIMECODE_BASE_FPS_NTSC,
        template_id=_TEMPLATE_ID,
        patch_preset_id=_PATCH_PRESET_ID,
        target_colorspace="bt709",
        gamut_map_id=payload_io.GAMUT_MAP_IDENTITY,
        slots=[
            {"slot_index": 0, "frame_timecode": "00:00:00:00"},
            {"slot_index": 1, "frame_timecode": "00:00:01:00"},
        ],
    )


def test_le_texte_serialise_de_la_page_de_reference_est_fige_octet_a_octet() -> None:
    """Le coeur du gel : le producteur reel rend exactement la fixture.

    Si ce test devient rouge parce que le producteur a change, la reponse n'est
    **pas** de re-generer la fixture : c'est de verifier qu'un arbitrage d'Egan
    autorise a casser la relecture des planches 2.1 deja imprimees.
    """
    texte = payload_io.serialize_payload(_page_de_reference())
    fixture_bytes = FIXTURE.read_bytes()
    assert texte.encode("utf-8") == fixture_bytes, (
        "Le texte serialise de la page de reference a change : c'est le format "
        "imprime lui-meme qui bouge (AC 7, EPIC7-ARB-51). Ceci exige un "
        "arbitrage d'Egan explicite, jamais une simple re-generation de la "
        "fixture."
    )
    # sv/schema_version au litteral, pour que le mutant qui ferait deriver
    # `PAYLOAD_SCHEMA_VERSION` sans re-figer la fixture soit attrape ici aussi.
    assert '"sv":"2.1"' in texte, texte


def test_le_qr_de_la_page_de_reference_se_decode_et_se_reparse_a_l_identique() -> None:
    """Le tour complet : texte fige -> QR -> decodeur de production -> reparse.

    C'est le trajet qu'un tirage papier emprunte reellement. Une regression
    dans `qr_codes` (capacite, ECC, seuillage) qui abimerait ce texte precis
    -- le plus long des deux valeurs de cadence source -- se verrait ici, pas
    seulement sur un payload synthetique plus court.
    """
    texte_fige = FIXTURE.read_text(encoding="utf-8")
    # Temoin: le producteur courant rend bien le texte fige (couvert par le
    # test ci-dessus, revalide ici pour que ce test soit autonome).
    assert payload_io.serialize_payload(_page_de_reference()) == texte_fige

    native = qr_codes.encode_qr_image(texte_fige)
    rendered = qr_codes.render_for_print(
        native, qr_codes.QR_PRINT_SIZE_TARGET_MM, qr_codes.QR_MIN_SCAN_DPI
    )
    result = qr_codes.decode_qr_image(rendered)

    assert result.ok, result.status
    # Relu octet a octet : un decodeur qui renverrait un texte equivalent mais
    # reordonne, ou avec un espace en plus, romprait le contrat imprime.
    assert result.text.encode("utf-8") == texte_fige.encode("utf-8")

    relu = payload_io.parse_payload(result.text)
    assert relu["project_id"] == _PROJECT_ID
    assert relu["rush_id"] == _RUSH_ID
    assert relu["lot_id"] == _LOT_ID
    assert relu["timecode_base_fps"] == _TIMECODE_BASE_FPS_NTSC
    assert relu["schema_version"] == payload_io.PAYLOAD_SCHEMA_VERSION
