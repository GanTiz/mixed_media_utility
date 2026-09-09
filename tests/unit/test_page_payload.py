"""Tests du module de jonction payload de page -> budget -> geometrie (story 4.5).

Deux familles de regime (AC 8): les identifiants du motif 4.6 reproduisent les
bornes historiques (1/5/10 slots passent le plafond, 11 refuse), et les
identifiants a la borne canonique de 48 caracteres font basculer le meme
cardinal de regime (5 slots hors nominal, 10 refuses) -- prouvant que la
capacite est une fonction du payload reel, jamais un nombre magique.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import (
    page_payload,
    page_templates,
    patch_presets,
    pdf_composition,
    qr_codes,
)
from mixed_media_utility.frame_selection import select_source_frames
from mixed_media_utility.io import naming
from mixed_media_utility.io import payload as payload_io

MODULE_PATH = REPO_ROOT / "src" / "mixed_media_utility" / "page_payload.py"

# Identifiants du motif 4.6 (tests/unit/test_qr_codes.py): ~7-15 caracteres,
# la base des bornes historiques "5 slots au nominal, 10 au plafond".
MOTIF_46_IDS = {
    "project_id": "demo-project-01",
    "rush_id": "rush-a1",
    "lot_id": "lot-0007",
}

# Identifiants a la borne canonique CANONICAL_ID_MAX_LENGTH = 48: memes
# cardinaux, regime different.
CANONICAL_48_IDS = {
    "project_id": "p" * naming.CANONICAL_ID_MAX_LENGTH,
    "rush_id": "r" * naming.CANONICAL_ID_MAX_LENGTH,
    "lot_id": "l" * naming.CANONICAL_ID_MAX_LENGTH,
}


def lot_scoped_slots(page_index: int, slots_per_page: int) -> list[dict]:
    """Slots conformes a la convention normative 3.1: `slot_index` continu a
    l'echelle du lot, jamais remis a zero par page (piege 4 bis: le motif de
    test de 4.6 redemarre a 0 sur la page 1, il ne doit pas etre recopie).

    Les timecodes derivent de l'index GLOBAL du lot (revue 4.5): la premiere
    version repartait de 00:00:00:00 a chaque page, donc deux pages portaient
    les memes timecodes pour des slots differents -- des donnees qu'aucun lot
    reel ne produit, exactement les collisions que le recoupement QR <-> nom
    existe pour attraper.
    """
    start = page_index * slots_per_page
    slots = []
    for offset in range(slots_per_page):
        rank = start + offset
        minutes, seconds = divmod(rank, 60)
        slots.append(
            {
                "slot_index": rank,
                "frame_timecode": f"00:{minutes % 60:02d}:{seconds:02d}:00",
            }
        )
    return slots


def plan(ids: dict, *, page_index: int = 1, page_count: int = 3, slots_per_page: int = 5):
    return page_payload.plan_page_payload(
        **ids,
        page_index=page_index,
        page_count=page_count,
        fps_target=24.0,
        timecode_base_fps="25/1",
        template_id="tpl-a4-2f-v1",
        patch_preset_id="patch-default-v1",
        target_colorspace="bt709",
        gamut_map_id="gamut-map-none-1",
        slots=lot_scoped_slots(page_index, slots_per_page),
    )


def _tient_sous_le_plafond(ids: dict, slots_per_page: int) -> bool:
    """Le cardinal tient-il sous le plafond dur de payload ?

    Les frontieres de budget sont **cherchees** et non epinglees depuis la story 5.17:
    elles ont bouge deux fois en deux stories (5.9 les avait ramenees, 5.17 les a
    repoussees de dix cardinaux), et a chaque fois un test qui nommait un cardinal a
    du etre reecrit alors que la propriete qu'il mesure n'avait pas change.
    """
    try:
        plan(ids, slots_per_page=slots_per_page)
    except payload_io.PayloadBudgetExceeded:
        return False
    return True


# --- AC 6 / AC 8a: regimes avec les identifiants du motif 4.6 ---------------


# Amende par la story 5.9: `gamut_map_id` coute 34 octets a plat, et une page
# a 5 slots passe de 493 a 527 octets -- au-dela du budget nominal de 512. Le
# regime nominal s'arrete donc a 4 slots. Le cardinal 5 n'est pas retire de la
# couverture pour autant: il devient le premier cardinal **hors** budget
# nominal, teste comme tel juste en dessous, pour que le basculement soit
# epingle et non seulement subi.
@pytest.mark.parametrize("slots_per_page", [1, 4])
def test_nominal_regime_with_motif_46_ids(slots_per_page: int) -> None:
    result = plan(MOTIF_46_IDS, slots_per_page=slots_per_page)

    assert result.budget.within_nominal
    assert result.warnings == ()
    # Le QR nominal tient a la taille cible: pas d'agrandissement.
    assert result.print_size_mm == qr_codes.QR_PRINT_SIZE_TARGET_MM
    assert result.required_print_size_mm <= qr_codes.QR_PRINT_SIZE_TARGET_MM
    assert result.geometry_status == qr_codes.GEOMETRY_RELIABLE
    # Roundtrip serialize -> parse sur le payload reellement embarque.
    assert payload_io.parse_payload(result.payload_text) == result.payload


def test_the_first_cardinal_over_the_nominal_budget_is_searched_not_pinned() -> None:
    """Le basculement de budget, **cherche** plutot qu'epingle a un cardinal.

    Story 5.9, AC 12: ce test epinglait le cardinal 5, premier a depasser le budget
    nominal a cause des 34 octets de `gamut_map_id`. La story 5.17 (cles courtes) a
    porte cette frontiere de 5 a **12**, et un test qui nomme un cardinal doit alors
    etre reecrit alors que la propriete, elle, n'a pas bouge. Il cherche donc la
    frontiere, et n'epingle que ce qui est un contrat: le repere documentaire du depot
    doit valoir le dernier cardinal nominal, et le cout du champ doit rester la longueur
    exacte de son fragment JSON.

    La page s'imprime toujours: entre 512 et 768 octets, EPIC4-ARB-2 veut un
    avertissement structure, jamais un refus.
    """
    premier_hors_nominal = next(
        cardinal for cardinal in range(1, 40)
        if not plan(MOTIF_46_IDS, slots_per_page=cardinal).budget.within_nominal
    )
    nominal = plan(MOTIF_46_IDS, slots_per_page=premier_hors_nominal - 1)
    over = plan(MOTIF_46_IDS, slots_per_page=premier_hors_nominal)

    assert nominal.budget.within_nominal
    assert nominal.warnings == ()
    assert not over.budget.within_nominal
    assert over.budget.within_alert
    assert over.warnings and over.warnings[0].startswith(
        page_payload.WARNING_OVER_NOMINAL_BUDGET
    )
    # **Les deux regimes ont cesse de coincider avec la story 5.16, et c'est un fait a
    # publier plutot qu'a masquer.** Le repere documentaire de `qr_codes` est mesure sur
    # SON regime (`demo-project-01` / `rush-a1` / `lot-0007`, `rec709`) et y vaut 11; le
    # regime du motif 4.6 employe ici franchit le budget des le cardinal **11**, donc son
    # dernier cardinal nominal est 10. Les 9 octets du champ de role ont consomme
    # l'ecart: avant la story, les deux regimes rendaient tous deux 11, ce qui faisait
    # croire a une egalite qui n'etait qu'une coincidence.
    #
    # La propriete que ce test doit tenir est donc celle de **son** regime, et
    # l'appartenance du repere a un autre regime est asserée comme telle -- c'est
    # exactement ce que le majeur M4 de la revue de 5.17 a etabli: un cout en octets sans
    # son regime n'est pas une mesure. Le repere est verifie dans son propre regime par
    # `test_payload_short_keys.test_the_slots_per_page_landmarks_are_recomputed_not_copied`.
    assert premier_hors_nominal - 1 == 10
    assert qr_codes.SLOTS_PER_PAGE_AT_NOMINAL_BUDGET == 11
    assert qr_codes.SLOTS_PER_PAGE_AT_NOMINAL_BUDGET != premier_hors_nominal - 1
    # Cout du champ: constant, et egal a la longueur du fragment JSON **imprime** --
    # donc sous sa cle courte depuis 5.17, ce qui le fait passer de 34 a 25 octets.
    import json as _json

    without = dict(over.payload)
    without.pop("gamut_map_id")
    cost = over.budget.size_bytes - len(payload_io.serialize_payload(without).encode("utf-8"))
    fragment = (
        1  # la virgule qui separe du champ precedent
        + len(_json.dumps(payload_io.PAYLOAD_SHORT_KEYS["gamut_map_id"]))
        + 1  # le deux-points
        + len(_json.dumps(over.payload["gamut_map_id"]))
    )
    assert cost == fragment
    assert cost == 25


def test_over_nominal_regime_is_a_structured_warning_not_an_error() -> None:
    # EPIC4-ARB-2: entre 512 et 768 octets la page s'imprime, avec un
    # avertissement structure et un QR agrandi automatiquement -- jamais un
    # refus, jamais un silence.
    #
    # Amende par la story 5.9 (cardinal 9), puis par la story 5.17: le dernier cardinal
    # sous le plafond dur est passe de 9 a **20** (765 octets). Il est cherche, pour que
    # la prochaine evolution du payload ne redemande pas de reecrire ce test.
    dernier_sous_plafond = max(
        cardinal for cardinal in range(1, 40)
        if _tient_sous_le_plafond(MOTIF_46_IDS, cardinal)
    )
    # **19 depuis la story 5.16** (role de page): le vingtieme emplacement passe de 762 a
    # 771 octets pour un plafond de 768. Les deux regimes coincident encore ici, et c'est
    # une coincidence: le regime du repere est celui de `qr_codes`, pas celui-ci.
    assert dernier_sous_plafond == qr_codes.SLOTS_PER_PAGE_AT_ALERT_BUDGET == 19
    result = plan(MOTIF_46_IDS, slots_per_page=dernier_sous_plafond)

    assert not result.budget.within_nominal
    assert result.budget.within_alert
    assert len(result.warnings) == 1
    assert result.warnings[0].startswith(page_payload.WARNING_OVER_NOMINAL_BUDGET)
    # Le QR est agrandi a la taille requise par le payload reel.
    assert result.required_print_size_mm > qr_codes.QR_PRINT_SIZE_TARGET_MM
    assert result.print_size_mm == result.required_print_size_mm
    assert result.geometry_status == qr_codes.GEOMETRY_RELIABLE
    assert payload_io.parse_payload(result.payload_text) == result.payload


def test_ceiling_refusal_transports_the_io_payload_exception() -> None:
    # Piege 1: PayloadBudgetExceeded n'est jamais avalee ni maquillee -- c'est
    # l'exception d'io.payload elle-meme qui traverse le module de jonction.
    #
    # Amende par la story 5.9 (refus a 10 slots), puis par la story 5.17: le premier
    # cardinal refuse est passe de 10 a **21** (794 octets). Un chiffre d'octets sans son
    # regime d'identifiants n'etant pas reproductible, c'est le cardinal qui est cherche.
    premier_refuse = min(
        cardinal for cardinal in range(1, 40)
        if not _tient_sous_le_plafond(MOTIF_46_IDS, cardinal)
    )
    # **20 depuis la story 5.16** (etait 21): les 9 octets du champ de role avancent le
    # refus d'un cardinal.
    assert premier_refuse == 20
    with pytest.raises(payload_io.PayloadBudgetExceeded) as excinfo:
        plan(MOTIF_46_IDS, slots_per_page=premier_refuse)
    assert "768" in str(excinfo.value)


# --- AC 6 / AC 8b: la capacite est une fonction du payload reel -------------


def test_canonical_48_char_ids_shift_the_same_cardinal_out_of_nominal() -> None:
    # Meme cardinal, autre regime: une borne de capacite ne vaut que pour ses
    # identifiants. Le cardinal 8 est nominal avec les identifiants du motif 4.6
    # (415 octets) et hors nominal avec ceux a 48 caracteres (529) -- c'est le meme
    # ecart de 114 octets que la story 5.17 mesure sur son propre regime de reference.
    assert plan(MOTIF_46_IDS, slots_per_page=8).budget.within_nominal
    result = plan(CANONICAL_48_IDS, slots_per_page=8)

    assert not result.budget.within_nominal
    assert result.budget.within_alert
    assert result.warnings and result.warnings[0].startswith(
        page_payload.WARNING_OVER_NOMINAL_BUDGET
    )
    assert payload_io.parse_payload(result.payload_text) == result.payload


def test_canonical_48_char_ids_bring_the_refusal_forward_by_four_cardinals() -> None:
    # Le refus existe toujours, plus tot que dans le regime court: 17 contre 21. Les
    # deux cardinaux sont cherches, pas epingles -- c'est leur **ecart** qui dit que la
    # capacite est une fonction du payload reel et jamais un nombre magique.
    refus_court = min(cardinal for cardinal in range(1, 40)
                      if not _tient_sous_le_plafond(MOTIF_46_IDS, cardinal))
    refus_long = min(cardinal for cardinal in range(1, 40)
                     if not _tient_sous_le_plafond(CANONICAL_48_IDS, cardinal))
    # **(20, 16) depuis la story 5.16**, chacun avance d'un cardinal. C'est leur **ecart**
    # qui porte la propriete -- quatre cardinaux, inchange --, et c'est pour cela qu'il
    # survit a un changement de contrat de payload.
    assert (refus_court, refus_long) == (20, 16)
    assert refus_court - refus_long == 4
    with pytest.raises(payload_io.PayloadBudgetExceeded):
        plan(CANONICAL_48_IDS, slots_per_page=refus_long)


def test_slots_per_page_constants_are_documentary_not_guards() -> None:
    # Les constantes SLOTS_PER_PAGE_AT_* de qr_codes restent des reperes: le
    # helper mesure le payload reel. La preuve: le meme cardinal (5) est
    # nominal avec les identifiants courts et hors nominal avec les longs.
    short_ids = plan(MOTIF_46_IDS, slots_per_page=qr_codes.SLOTS_PER_PAGE_AT_NOMINAL_BUDGET)
    long_ids = plan(CANONICAL_48_IDS, slots_per_page=qr_codes.SLOTS_PER_PAGE_AT_NOMINAL_BUDGET)
    # **La demonstration est plus forte depuis la story 5.16**, et elle est mesuree: au
    # cardinal que le repere documente, le regime du motif 4.6 est lui-meme **au-dessus**
    # du budget nominal -- de 1 octet a l'origine, **14 depuis la story 2.7** (payload
    # 2.1, +13 octets du champ de cadence source). Si ce repere etait une garde, il
    # refuserait donc une page que le regime dont il est tire imprime sans un mot. C'est
    # precisement pour cela qu'il n'en est pas une: la garde est `check_payload_budget`,
    # qui mesure le document reellement serialise.
    assert not short_ids.budget.within_nominal
    assert short_ids.budget.size_bytes == payload_io.NOMINAL_BUDGET_BYTES + 14
    assert not long_ids.budget.within_nominal
    # ... et les deux regimes restent ordonnes, ce qui est l'autre moitie de la
    # propriete: une borne de capacite ne vaut que pour ses identifiants.
    assert long_ids.budget.size_bytes > short_ids.budget.size_bytes
    # Le cardinal 8, lui, distingue encore les deux regimes des deux cotes du budget: le
    # temoin qui empeche ce test de devenir vrai par vacuite.
    assert plan(MOTIF_46_IDS, slots_per_page=8).budget.within_nominal
    assert not plan(CANONICAL_48_IDS, slots_per_page=8).budget.within_nominal


# --- Conventions normatives 3.1 (AC 8) --------------------------------------


def test_page_index_is_base_zero_and_slot_index_is_lot_scoped() -> None:
    # page_index base zero (convention 3.1), slot_index continu a l'echelle du
    # lot entre les pages: la page 0 porte 0..4, la page 1 porte 5..9.
    page0 = plan(MOTIF_46_IDS, page_index=0, page_count=2, slots_per_page=5)
    page1 = plan(MOTIF_46_IDS, page_index=1, page_count=2, slots_per_page=5)

    assert page0.payload["page_index"] == 0
    assert page1.payload["page_index"] == 1
    assert [slot["slot_index"] for slot in page0.payload["slots"]] == [0, 1, 2, 3, 4]
    assert [slot["slot_index"] for slot in page1.payload["slots"]] == [5, 6, 7, 8, 9]
    for result in (page0, page1):
        assert payload_io.parse_payload(result.payload_text) == result.payload


# --- Identifiants canoniques (piege 6) ---------------------------------------


@pytest.mark.parametrize(
    "field, value",
    [
        ("project_id", "Mon Projet 2026"),
        ("rush_id", "rush du matin.mov"),
        ("lot_id", "x" * (naming.CANONICAL_ID_MAX_LENGTH + 1)),
        ("template_id", "template avec espaces"),
        ("patch_preset_id", "preset.v1"),
    ],
)
def test_non_canonical_identifiers_are_refused_with_the_field_name(
    field: str, value: str
) -> None:
    # Un appelant qui passe un nom humain brut casserait le recoupement
    # QR <-> nom de fichier sans erreur (piege 6): le helper refuse.
    ids = dict(MOTIF_46_IDS)
    kwargs = {
        **ids,
        "page_index": 0,
        "page_count": 1,
        "fps_target": 24.0,
        "timecode_base_fps": "25/1",
        "template_id": "tpl-a4-2f-v1",
        "patch_preset_id": "patch-default-v1",
        "target_colorspace": "bt709",
        "gamut_map_id": "gamut-map-none-1",
        "slots": lot_scoped_slots(0, 2),
    }
    kwargs[field] = value
    with pytest.raises(page_payload.NonCanonicalIdentifierError, match=field):
        page_payload.plan_page_payload(**kwargs)


def test_contract_validation_errors_propagate_unmasked() -> None:
    # Piege 5: un target_colorspace vide (manifest pas encore renseigne) doit
    # remonter comme l'erreur de validation du contrat 2.3, sans maquillage.
    with pytest.raises(payload_io.PayloadValidationError, match="target_colorspace"):
        page_payload.plan_page_payload(
            **MOTIF_46_IDS,
            page_index=0,
            page_count=1,
            fps_target=24.0,
            timecode_base_fps="25/1",
            template_id="tpl-a4-2f-v1",
            patch_preset_id="patch-default-v1",
            target_colorspace="",
            gamut_map_id="gamut-map-none-1",
            slots=lot_scoped_slots(0, 1),
        )


# --- AC 5: forme canonique du timecode, de la selection au nommage ----------


def test_timecode_roundtrip_from_frame_selection_to_both_naming_conventions() -> None:
    # Jonction reelle: une FrameSelection de la story 3.2 fournit les
    # timecodes en forme canonique hh:mm:ss:ff (base source, ARB-2). Le
    # payload les transporte tels quels; la conversion vers la forme fichier
    # hh-mm-ss-ff se fait au nommage (io/naming) et nulle part ailleurs.
    selection = select_source_frames(
        fps_source=25,
        fps_target=5,
        source_frame_count=50,
    )
    slots = [
        {"slot_index": frame.output_rank, "frame_timecode": frame.frame_timecode}
        for frame in selection.frames[:5]
    ]
    assert all(":" in slot["frame_timecode"] for slot in slots)

    result = page_payload.plan_page_payload(
        **MOTIF_46_IDS,
        page_index=0,
        page_count=1,
        fps_target=5.0,
        timecode_base_fps="25/1",
        template_id="tpl-a4-2f-v1",
        patch_preset_id="patch-default-v1",
        target_colorspace="bt709",
        gamut_map_id="gamut-map-none-1",
        slots=slots,
    )

    # Le payload embarque porte la forme canonique, jamais la forme assainie.
    parsed = payload_io.parse_payload(result.payload_text)
    for slot, source in zip(parsed["slots"], slots):
        canonical = source["frame_timecode"]
        sanitized = naming.sanitize_timecode(canonical)
        assert slot["frame_timecode"] == canonical
        assert slot["frame_timecode"].count(":") == 3
        assert sanitized not in result.payload_text

        # Convention 1 -- noms des frames extraites que makepdf lit sur disque
        # (build_extracted_frame_filename, story 3.1).
        extracted_name = naming.build_extracted_frame_filename(
            MOTIF_46_IDS["rush_id"], 5.0, canonical
        )
        assert sanitized in extracted_name
        assert canonical not in extracted_name
        # La lecture inverse restitue exactement la forme canonique du payload.
        assert naming.read_extracted_frame_timecode(extracted_name) == canonical

        # Convention 2 -- chaine PDF/scan (build_frame_filename, story 2.3),
        # la seule portant page_index / slot_index: le filet de securite de
        # l'AC 4 de 4.6 repose sur ce recoupement QR <-> nom.
        frame_name = naming.build_frame_filename(
            project_id=MOTIF_46_IDS["project_id"],
            rush_id=MOTIF_46_IDS["rush_id"],
            lot_id=MOTIF_46_IDS["lot_id"],
            page_index=0,
            frame_timecode=canonical,
            fps_target=5.0,
            slot_index=slot["slot_index"],
        )
        assert f"tc{sanitized}" in frame_name
        assert canonical not in frame_name
        assert "_p001_" in frame_name  # base un a l'affichage fichier seulement
        assert f"_s{slot['slot_index']:02d}_" in frame_name


# --- AC 7: aucun second schema, nulle part -----------------------------------


def _module_tree() -> ast.Module:
    return ast.parse(MODULE_PATH.read_text(encoding="utf-8"), filename=str(MODULE_PATH))


def test_junction_module_does_not_reimplement_any_contract() -> None:
    # Motif du test de qr_codes (decisions-2026-08-02, decision 1): le depot a
    # deja paye deux fois le prix d'un schema duplique. Le module de jonction
    # importe io/payload, io/naming et qr_codes et ne reimplemente rien:
    # ni serialisation JSON parallele, ni derivation d'identifiant, ni
    # constante de budget dupliquee, ni motif regex local.
    tree = _module_tree()

    forbidden_imports = {"json", "re", "hashlib"}
    forbidden_calls = {
        "dumps",
        "loads",
        "derive_short_id",
        "short_id_derivation",
        "sanitize_timecode",
        "build_lot_id",
        "build_frame_filename",
        "build_extracted_frame_filename",
    }
    forbidden_literals = {
        payload_io.NOMINAL_BUDGET_BYTES,
        payload_io.ALERT_BUDGET_BYTES,
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                assert root not in forbidden_imports, (
                    f"import interdit dans le module de jonction: {alias.name}"
                )
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            root = node.module.split(".")[0]
            assert root not in forbidden_imports, (
                f"import interdit dans le module de jonction: {node.module}"
            )
        if isinstance(node, ast.Call):
            name = None
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            assert name not in forbidden_calls, (
                f"appel interdit dans le module de jonction: {name} "
                "(le contrat appartient a io.payload/io.naming/qr_codes)"
            )
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            assert node.value not in forbidden_literals, (
                f"constante de budget dupliquee dans le module de jonction: {node.value}"
            )


def test_junction_module_consumes_the_three_owning_modules() -> None:
    tree = _module_tree()
    relative_imports: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level >= 1:
            module = node.module or ""
            for alias in node.names:
                relative_imports.add((module, alias.name))

    assert ("io", "naming") in relative_imports
    assert ("io", "payload") in relative_imports or any(
        module == "io.payload" for module, _ in relative_imports
    )
    assert ("", "qr_codes") in relative_imports or any(
        module == "qr_codes" for module, _ in relative_imports
    )


# ---------------------------------------------------------------------------
# Revue 4.5: gardes ajoutees (identifiants du schema, timecode, dpi, budgets)
# ---------------------------------------------------------------------------


def test_identifiers_produced_by_the_depot_own_conventions_are_accepted() -> None:
    # Revue 4.5 (finding haute): le point fixe de normalize_identifier refusait
    # des lot_id produits par build_lot_id lui-meme (derive_short_id recopie
    # son prefixe verbatim -> `...--<hash>`) et des ids schema-valides (a--b).
    long_rush = "r" * 38 + "-" + "r" * 9  # 48 chars, tiret a la borne du prefixe
    lot_id = naming.build_lot_id(long_rush, 24.0)
    assert "--" in lot_id  # la forme qui etait refusee a tort
    result = page_payload.plan_page_payload(
        project_id="a--b",
        rush_id=long_rush,
        lot_id=lot_id,
        page_index=0,
        page_count=1,
        fps_target=24.0,
        timecode_base_fps="25/1",
        template_id="tpl-a4-portrait-2f-v1",
        patch_preset_id="patches-12-v1",
        target_colorspace="rec709",
        gamut_map_id="gamut-map-none-1",
        slots=lot_scoped_slots(0, 2),
    )
    assert result.payload["lot_id"] == lot_id

    # Un nom humain brut reste refuse (piege 6): espaces hors pattern schema.
    with pytest.raises(page_payload.NonCanonicalIdentifierError):
        plan({**MOTIF_46_IDS, "rush_id": "Mon Rush 001"})


def test_file_form_timecode_is_refused_in_slots() -> None:
    # Revue 4.5: le docstring revendiquait le filet 4.6 (recoupement QR <->
    # nom) sans aucune garde -- la forme fichier hh-mm-ss-ff passait.
    with pytest.raises(page_payload.NonCanonicalTimecodeError):
        page_payload.plan_page_payload(
            **{**_plan_kwargs(MOTIF_46_IDS),
               "slots": [{"slot_index": 0, "frame_timecode": "00-00-01-00"}]},
        )


def _plan_kwargs(ids: dict, **overrides):
    kwargs = dict(
        project_id=ids["project_id"],
        rush_id=ids["rush_id"],
        lot_id=ids["lot_id"],
        page_index=0,
        page_count=1,
        fps_target=5.0,
        timecode_base_fps="25/1",
        template_id="tpl-a4-2f-v1",
        patch_preset_id="patch-default-v1",
        target_colorspace="rec709",
        gamut_map_id="gamut-map-none-1",
        slots=lot_scoped_slots(0, 2),
    )
    kwargs.update(overrides)
    return kwargs


def test_non_finite_fps_is_refused_before_reaching_the_qr() -> None:
    # Revue 4.5: NaN echappait a `<= 0` et Infinity y passait; le QR aurait
    # embarque un litteral JSON non standard illisible par un decodeur strict.
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(payload_io.PayloadValidationError):
            page_payload.plan_page_payload(**_plan_kwargs(MOTIF_46_IDS, fps_target=bad))


def test_boolean_indexes_are_refused() -> None:
    with pytest.raises(payload_io.PayloadValidationError):
        page_payload.plan_page_payload(
            **_plan_kwargs(MOTIF_46_IDS, page_index=True, page_count=2)
        )
    with pytest.raises(payload_io.PayloadValidationError):
        page_payload.plan_page_payload(
            **_plan_kwargs(
                MOTIF_46_IDS,
                slots=[{"slot_index": True, "frame_timecode": "00:00:00:00"}],
            )
        )


def test_duplicated_slot_index_is_refused() -> None:
    # Revue 4.5: deux slots au meme index rendaient le recoupement `_sNN_`
    # ambigu entre deux frames.
    with pytest.raises(payload_io.PayloadValidationError):
        page_payload.plan_page_payload(
            **_plan_kwargs(
                MOTIF_46_IDS,
                slots=[
                    {"slot_index": 3, "frame_timecode": "00:00:00:00"},
                    {"slot_index": 3, "frame_timecode": "00:00:01:00"},
                ],
            )
        )


def test_invalid_scan_dpi_is_refused_at_entry() -> None:
    # Revue 4.5: scan_dpi 0/negatif/booleen n'echouait qu'apres l'encodage
    # complet du QR, avec un message ne nommant pas le parametre.
    from mixed_media_utility import qr_codes

    for bad in (0, -600, True):
        with pytest.raises(qr_codes.QRRenderError) as excinfo:
            page_payload.plan_page_payload(**_plan_kwargs(MOTIF_46_IDS, scan_dpi=bad))
        assert "scan_dpi" in str(excinfo.value)


def test_over_nominal_warning_is_honest_about_enlargement() -> None:
    # Revue 4.5: le message disait "QR agrandi a 35.0 mm" quand la taille
    # cible etait simplement conservee.
    result = plan(CANONICAL_48_IDS, slots_per_page=8)  # 529 o, hors nominal
    assert not result.budget.within_nominal
    message = result.warnings[0]
    if result.print_size_mm > 35.0:
        assert "agrandi" in message
    else:
        assert "agrandi" not in message
        assert "conservee" in message


def test_dpi_driven_enlargement_is_signaled_at_nominal_budget() -> None:
    # Revue 4.5: a budget nominal, scan_dpi=300 agrandissait le QR a ~60 mm
    # sans un mot -- une geometrie qui ne tient plus forcement sur A4.
    result = page_payload.plan_page_payload(**_plan_kwargs(MOTIF_46_IDS, scan_dpi=300))
    assert result.budget.within_nominal
    assert result.print_size_mm > 35.0
    assert any(
        page_payload.WARNING_QR_ENLARGED_FOR_SCAN_DPI in warning
        for warning in result.warnings
    )


def test_geometry_status_is_reliable_at_the_exact_computed_threshold() -> None:
    # Revue 4.5 (arrondi flottant): a certains couples modules/dpi,
    # pixels_per_module(required_print_size_mm(...)) rendait 7.999... et la
    # taille calculee pour etre fiable etait classee degradee.
    result = page_payload.plan_page_payload(
        **_plan_kwargs(
            MOTIF_46_IDS, slots=lot_scoped_slots(0, 7), scan_dpi=300
        )
    )
    assert result.geometry_status == "reliable"
    assert result.print_size_mm >= result.required_print_size_mm


def test_plan_payload_is_isolated_from_caller_slot_mutation() -> None:
    # Revue 4.5: io.payload ne copie que la liste de slots, pas les dicts --
    # muter un dict apres l'appel faisait diverger payload et payload_text.
    slots = lot_scoped_slots(0, 2)
    result = page_payload.plan_page_payload(**_plan_kwargs(MOTIF_46_IDS, slots=slots))
    slots[0]["frame_timecode"] = "09:09:09:09"
    assert result.payload["slots"][0]["frame_timecode"] == "00:00:00:00"
    assert payload_io.parse_payload(result.payload_text) == result.payload


# --- Story 5.9, AC 12/13: le prix reel de « purement additif » --------------
#
# Le contenu ne change pas; la geometrie imprimee, si. A mesurer et a assumer,
# pas a decouvrir en revue.

LONG_IDS = tuple("x" * 48 for _ in range(5))


def _payload_bytes(slots_per_page: int, ids, *, with_field: bool) -> int:
    """Octets du payload **reellement serialise**, avec ou sans le champ."""
    result = page_payload.plan_page_payload(
        project_id=ids[0],
        rush_id=ids[1],
        lot_id=ids[2],
        page_index=0,
        page_count=3,
        fps_target=24.0,
        timecode_base_fps="25/1",
        template_id=ids[3],
        patch_preset_id=ids[4],
        target_colorspace="bt709",
        gamut_map_id=payload_io.GAMUT_MAP_IDENTITY,
        slots=[
            {"slot_index": i, "frame_timecode": f"00:00:0{i}:00"}
            for i in range(slots_per_page)
        ],
    )
    if with_field:
        return result.budget.size_bytes
    without = dict(result.payload)
    without.pop("gamut_map_id")
    return len(payload_io.serialize_payload(without).encode("utf-8"))


REFERENCE_IDS = (
    "demo-project-01",
    "rush-a1",
    "lot-0007",
    "tpl-a4-portrait-2f-v1",
    "patches-12-v1",
)


@pytest.mark.parametrize(
    ("slots_per_page", "without", "with_field"),
    # **Les deux colonnes montent de 13 octets avec la story 2.7** (payload 2.1, champ
    # `timecode_base_fps` a `"25/1"`); elles montaient de 9 avec la story 5.16 (role de
    # page). Elles mesurent le cout de `gamut_map_id`, et ce cout ne change pas -- c'est
    # le **socle** qui grossit a chaque fois. Un test qui n'aurait bouge qu'une colonne
    # aurait fait croire que le champ de gamut coute autre chose.
    [(2, 244, 269), (4, 300, 325), (5, 328, 353), (6, 356, 381), (8, 412, 437)],
)
def test_measured_payload_cost_reference_identifier_regime(
    slots_per_page: int, without: int, with_field: int
) -> None:
    # Un chiffre d'octets sans son regime d'identifiants n'est pas
    # reproductible: le regime est nomme dans REFERENCE_IDS.
    #
    # **Colonnes re-mesurees par la story 5.17** (cles courtes, `EPIC5-ARB-60`): le
    # cardinal 8 passe de 671 a 415 octets. Le cout du champ, lui, passe de 34 a 25 --
    # c'est la longueur de son fragment sous la cle courte `gmi`, et il reste constant
    # d'un cardinal a l'autre, ce qui est la propriete que ce test mesure.
    assert _payload_bytes(slots_per_page, REFERENCE_IDS, with_field=False) == without
    assert _payload_bytes(slots_per_page, REFERENCE_IDS, with_field=True) == with_field
    assert with_field - without == 25


@pytest.mark.parametrize(
    ("slots_per_page", "without", "with_field"),
    # Meme decalage de 13 octets (story 2.7) / 9 octets (story 5.16), et c'est le
    # point: il ne depend ni du cardinal ni du regime d'identifiants.
    [(2, 420, 445), (4, 476, 501), (6, 532, 557)],
)
def test_measured_payload_cost_long_identifier_regime(
    slots_per_page: int, without: int, with_field: int
) -> None:
    # Cinq identifiants a la borne canonique de 48 caracteres. Avant la story 5.17 ce
    # regime valait 751 octets a 6 slots -- hors budget nominal et a 17 octets du
    # plafond dur. Il en vaut 535: hors nominal de 23 octets, et le plafond n'est plus
    # en vue. Le cout du champ est le meme que dans le regime court, ce qui est le point.
    assert _payload_bytes(slots_per_page, LONG_IDS, with_field=False) == without
    assert _payload_bytes(slots_per_page, LONG_IDS, with_field=True) == with_field
    assert with_field - without == 25


def test_the_long_identifier_regime_at_eight_slots_is_no_longer_refused() -> None:
    """La page la plus lourde du depot est passee de **refusee** a imprimable.

    Avant la story 5.17, cinq identifiants a 48 caracteres et 8 emplacements pesaient
    813 octets **sans** `gamut_map_id`, donc au-dela du plafond dur: la page etait
    refusee a l'encodage, et la story 5.9 avait pris soin de dire que ce refus lui etait
    anterieur. Sous les cles courtes, la meme page pese 591 octets.

    C'est le gain de la story exprime sur son cas le plus dur, et c'est aussi ce qui
    justifie que les frontieres de budget de ce fichier soient desormais cherchees: ce
    refus-la a disparu, il n'y avait aucun moyen de le prevoir en relisant le code.
    """
    octets = _payload_bytes(8, LONG_IDS, with_field=True)
    # **613 depuis la story 2.7** (600 + 13 octets du champ de cadence source); 600
    # valait depuis la story 5.16 (591 + 9). La page la plus lourde du depot reste
    # imprimable: 613 pour un plafond dur de 768, hors budget nominal et loin du refus.
    assert octets == 613
    assert octets <= payload_io.ALERT_BUDGET_BYTES
    assert octets > payload_io.NOMINAL_BUDGET_BYTES


def test_the_field_costs_its_json_fragment_plus_the_identifier_length() -> None:
    # EPIC5-ARB-11 point 11b corrige la reference a +29 d'EPIC5-ARB-2, qui
    # supposait un identifiant de 11 caracteres. La formule, elle, est stable -- et
    # c'est bien une formule et non un nombre: la story 5.17 a porte l'en-tete du
    # fragment de 18 a 9 octets en raccourcissant la cle, sans toucher a la formule.
    for identifier in ("gamut-map-none-1", "gamut-map-perceptual-1"):
        base = page_payload.plan_page_payload(
            project_id=REFERENCE_IDS[0], rush_id=REFERENCE_IDS[1], lot_id=REFERENCE_IDS[2],
            page_index=0, page_count=3, fps_target=24.0, timecode_base_fps="25/1",
            template_id=REFERENCE_IDS[3], patch_preset_id=REFERENCE_IDS[4],
            target_colorspace="bt709", gamut_map_id=identifier,
            slots=[{"slot_index": 0, "frame_timecode": "00:00:00:00"}],
        )
        without = dict(base.payload)
        without.pop("gamut_map_id")
        cost = base.budget.size_bytes - len(
            payload_io.serialize_payload(without).encode("utf-8")
        )
        # L'en-tete est **derive de la table**, jamais recopie: virgule, cle courte
        # citee, deux-points, et les guillemets de la valeur.
        entete = 1 + len(payload_io.PAYLOAD_SHORT_KEYS["gamut_map_id"]) + 2 + 1 + 2
        assert entete == 9
        assert cost == entete + len(identifier)


def test_the_source_cadence_field_costs_its_json_fragment_plus_its_value_length() -> None:
    """AC 2 de la story 2.7: meme formule, declinee pour `timecode_base_fps`.

    Deux valeurs, **distinguables en longueur** -- la plus courte du depot
    (`"25/1"`) et la plus longue couramment portee par un manifest reel
    (NTSC, `"30000/1001"`) -- pour que le cout mesure soit celui de la formule
    (en-tete fixe + longueur de la valeur) et non celui d'une seule chaine.
    """
    for valeur in ("25/1", "30000/1001"):
        base = page_payload.plan_page_payload(
            project_id=REFERENCE_IDS[0], rush_id=REFERENCE_IDS[1], lot_id=REFERENCE_IDS[2],
            page_index=0, page_count=3, fps_target=24.0, timecode_base_fps=valeur,
            template_id=REFERENCE_IDS[3], patch_preset_id=REFERENCE_IDS[4],
            target_colorspace="bt709", gamut_map_id=payload_io.GAMUT_MAP_IDENTITY,
            slots=[{"slot_index": 0, "frame_timecode": "00:00:00:00"}],
        )
        without = dict(base.payload)
        without.pop("timecode_base_fps")
        cost = base.budget.size_bytes - len(
            payload_io.serialize_payload(without).encode("utf-8")
        )
        # Meme formule d'en-tete que `gamut_map_id` ci-dessus, derivee de la table pour
        # la cle courte `tbf`: virgule, cle courte citee, deux-points, guillemets de
        # la valeur.
        entete = 1 + len(payload_io.PAYLOAD_SHORT_KEYS["timecode_base_fps"]) + 2 + 1 + 2
        assert entete == 9
        assert cost == entete + len(valeur)


def _reference_plan(slots_per_page: int):
    """Plan du regime de reference, avec des timecodes valides a tout cardinal.

    Le generateur `f"00:00:0{i}:00"` employe ailleurs dans ce fichier casse des le
    dixieme emplacement (`00:00:010:00` n'est pas un timecode). Les cardinaux dont on a
    besoin ici depassent la vingtaine.
    """
    slots = []
    for rank in range(slots_per_page):
        minutes, seconds = divmod(rank, 60)
        slots.append({"slot_index": rank,
                      "frame_timecode": f"00:{minutes % 60:02d}:{seconds:02d}:00"})
    return page_payload.plan_page_payload(
        project_id=REFERENCE_IDS[0], rush_id=REFERENCE_IDS[1], lot_id=REFERENCE_IDS[2],
        page_index=0, page_count=3, fps_target=24.0, timecode_base_fps="25/1",
        template_id=REFERENCE_IDS[3], patch_preset_id=REFERENCE_IDS[4],
        target_colorspace="bt709", gamut_map_id=payload_io.GAMUT_MAP_IDENTITY,
        slots=slots,
    )


def test_the_enlargement_threshold_moved_and_the_banned_version_sits_just_below() -> None:
    """AC 13 de 5.9, re-mesuree par 5.17 -- et ce qu'on trouve en chemin.

    La story 5.9 epinglait: a 8 emplacements le cote de module passe a 105 et le
    classement a la taille cible bascule, donc `plan_page_payload` agrandit le symbole.
    Sous les cles courtes, 8 emplacements donnent **85 modules** et la taille cible
    suffit: la bascule n'a pas disparu, elle a recule.

    Ce que le balayage montre, et qui est la raison d'etre de la garde de la story 5.17:
    le premier cardinal qui exige un agrandissement est celui de **109 modules**, et
    juste en dessous se trouvent deux cardinaux a **105 modules** -- la version 22, que
    le detecteur de production ne decode a aucune taille. Un agrandissement les aurait
    laisses indecodables; ils sont classes `unusable`, donc refuses a la composition.
    """
    huit = _reference_plan(8)
    assert huit.module_side == 85
    assert huit.print_size_mm == qr_codes.QR_PRINT_SIZE_TARGET_MM
    assert huit.geometry_status == qr_codes.GEOMETRY_RELIABLE

    par_cardinal = {}
    for cardinal in range(1, 40):
        try:
            par_cardinal[cardinal] = _reference_plan(cardinal)
        except payload_io.PayloadBudgetExceeded:
            break

    bannis = [cardinal for cardinal, plan_ in par_cardinal.items()
              if qr_codes.symbol_version(plan_.module_side)
              in qr_codes.QR_BANNED_SYMBOL_VERSIONS]
    agrandis = [cardinal for cardinal, plan_ in par_cardinal.items()
                if plan_.print_size_mm > qr_codes.QR_PRINT_SIZE_TARGET_MM
                and plan_.geometry_status == qr_codes.GEOMETRY_RELIABLE]
    # **Les deux listes reculent d'un cardinal avec la story 5.16** (role de page): la
    # bande d'octets qui encode sur la version bannie ne porte plus qu'**un** cardinal, et
    # la propriete qui compte -- le premier cardinal agrandi est juste au-dessus du
    # dernier banni -- tient toujours. C'est la non-monotonie de la version de symbole en
    # octets, dans le sens ou elle **reduit** la zone dangereuse.
    #
    # **La fenetre bannie s'elargit d'un cardinal avec la story 2.7** (payload 2.1,
    # champ `timecode_base_fps`, 13 octets a `"25/1"`): mesure AVANT promesse dans la
    # fiche de la story, `[16, 17]` au lieu de `[17]`. `agrandis` ne bouge pas -- `[18,
    # 19]` -- et la propriete qui compte tient toujours: `min(agrandis) ==
    # max(bannis) + 1`. La fenetre reste hors d'atteinte de toute page reelle (aucun
    # gabarit ne depasse 8 frames par page).
    assert bannis == [16, 17], bannis
    assert agrandis == [18, 19], agrandis
    assert min(agrandis) == max(bannis) + 1
    assert all(par_cardinal[cardinal].geometry_status == qr_codes.GEOMETRY_UNUSABLE
               for cardinal in bannis)
    assert all(par_cardinal[cardinal].module_side == 105 for cardinal in bannis)
    premier_agrandi = par_cardinal[agrandis[0]]
    assert premier_agrandi.module_side == 109
    assert premier_agrandi.print_size_mm == pytest.approx(
        premier_agrandi.required_print_size_mm)
    assert premier_agrandi.print_size_mm == pytest.approx(36.91, abs=0.01)


#: Marge attendue entre la zone reservee au QR et l'emprise du symbole a 8 slots, par
#: version de geometrie. Elle est **epinglee par version** depuis la story 5.15: la
#: zone de la v1 est un litteral de 40 mm (calibre a la main sur sa bande haute de
#: 50 mm), celle de la v2 est **derivee** du majorant d'emprise -- donc plus serree, et
#: exactement nulle au cardinal ou le symbole est le plus gros (voir le balayage du
#: test suivant). Zero n'y est pas un accident: c'est la definition d'un majorant
#: atteint, et `_qr_footprint_rect` compare avec sa tolerance de 1e-9. Un chiffre
#: negatif, lui, dirait que la reservation est fausse.
_QR_ZONE_MARGIN_BY_VERSION = {"v1": 1.73, "v2": 1.35}


@pytest.mark.parametrize("geometry_version", ["v1", "v2"])
@pytest.mark.parametrize("orientation", ["portrait", "paysage"])
def test_the_enlarged_qr_still_fits_the_reserved_zone(
        orientation: str, geometry_version: str) -> None:
    """Ce que l'arbitrage ne deduit pas et qu'il faut verifier (AC 13).

    Accepter la bascule de classement n'a de sens que si le symbole agrandi,
    zone de silence comprise, tient encore dans la zone reservee -- faute de quoi il
    mordrait sur les patchs ou le texte. Verifie sur les **deux** versions de
    geometrie depuis la story 5.15: la v2 resserre la bande haute a 38,8 mm, et une
    reservation heritee de la v1 y aurait ete a la fois trop large et mal placee.
    """
    template_id = page_templates.build_template_id(
        orientation, 8, "2", geometry_version)
    result = page_payload.plan_page_payload(
        project_id=REFERENCE_IDS[0], rush_id=REFERENCE_IDS[1], lot_id=REFERENCE_IDS[2],
        page_index=0, page_count=3, fps_target=24.0, timecode_base_fps="25/1",
        template_id=template_id, patch_preset_id="patches-18-v2",
        target_colorspace="bt709", gamut_map_id=payload_io.GAMUT_MAP_IDENTITY,
        slots=[{"slot_index": i, "frame_timecode": f"00:00:0{i}:00"} for i in range(8)],
    )
    module_mm = result.print_size_mm / result.module_side
    footprint_mm = result.print_size_mm + 2 * qr_codes.QUIET_ZONE_MODULES * module_mm
    zone = next(
        z for z in patch_presets.reserved_zones_mm(template_id) if z["name"] == "qr_zone"
    )
    assert footprint_mm <= zone["width"] + 1e-9, (orientation, footprint_mm)
    assert footprint_mm <= zone["height"] + 1e-9, (orientation, footprint_mm)
    # Marge reelle, pour que son erosion soit visible si le payload grossit.
    assert zone["width"] - footprint_mm == pytest.approx(
        _QR_ZONE_MARGIN_BY_VERSION[geometry_version], abs=0.05)

    # --- Et la zone est confrontee **en abscisse**, pas seulement en dimensions ---
    #
    # Survivant M43 de la revue 5.15: decaler la zone reservee d'une demi-emprise
    # (19,8 mm sur les gabarits v2) ne faisait echouer aucun test -- ci-dessus, seules
    # la largeur et la hauteur etaient comparees, et les tests de chevauchement
    # **recalculent** l'emprise du QR au lieu de la lire dans la reservation. Une
    # reservation qui ne couvre pas ce qu'elle reserve est pire qu'absente: elle a l'air
    # d'une garde.
    #
    # **L'abscisse attendue n'est plus « le centre de la page » depuis la story 5.18**:
    # le bord porteur du QR est calcule par gabarit, et l'emprise est collee a droite de
    # la bande basse quand le QR y va -- le pied de page occupe ce qui reste. Elle est
    # donc lue par la recette de production, la meme que `_qr_footprint_rect` emprunte;
    # sans cela le test ne mesurerait pas la reservation mais une convention perimee.
    spec = page_templates.get_template(template_id)
    printed = pdf_composition._qr_footprint_rect(spec, result)
    printed_x0, printed_x1 = printed[0], printed[0] + printed[2]
    assert printed[2] == pytest.approx(footprint_mm, abs=1e-9)
    assert zone["x"] <= printed_x0 + 1e-9, (template_id, zone["x"], printed_x0)
    assert zone["x"] + zone["width"] >= printed_x1 - 1e-9, (
        template_id, zone["x"] + zone["width"], printed_x1)
    named = {z["name"]: z for z in patch_presets.reserved_zones_mm(template_id)}
    if spec.qr_edge == page_templates.QR_EDGE_TOP:
        # QR dans la bande haute, centree sur la page: les deux zones de texte qui le
        # flanquent sont donc symetriques, et une zone QR mal placee les deforme de facon
        # visible (77,0 / 37,4 mm au lieu de 57,2 / 57,2 sous le mutant).
        flanking = {name: named[name] for name in
                    ("text_header_left", "text_header_right") if name in named}
        assert set(flanking) == {"text_header_left", "text_header_right"}, template_id
        if geometry_version != "v1":  # les zones v1 sont des litteraux, non derives
            assert flanking["text_header_left"]["width"] == pytest.approx(
                flanking["text_header_right"]["width"], abs=1e-9), flanking
    else:
        # QR ailleurs: la bande haute est **entiere** pour l'entete, et c'est le pied de
        # page (ou la colonne de pastilles) qui partage l'espace avec le QR. Ce que la
        # reservation doit dire alors, c'est que ces deux-la ne se recouvrent pas.
        assert "text_header" in named, template_id
        assert "text_header_left" not in named
        header = named["text_header"]
        assert header["width"] == pytest.approx(
            page_templates.header_band_mm(spec)[2], abs=1e-9)
        for name, other in named.items():
            if name in ("qr_zone", "text_header"):
                continue
            assert not (zone["x"] < other["x"] + other["width"]
                        and other["x"] < zone["x"] + zone["width"]
                        and zone["y"] < other["y"] + other["height"]
                        and other["y"] < zone["y"] + zone["height"]), (
                template_id, name)


#: Marge la plus faible du balayage de cardinaux, par version. En v1 elle vient du
#: litteral de 40 mm; en v2 la zone **est** le majorant d'emprise, donc la marge
#: minimale est nulle -- atteinte au cardinal ou le symbole est le plus gros.
#:
#: Les deux chiffres sont **inchanges** par la story 5.17, et c'est le resultat
#: interessant: ce n'est pas la marge qui a bouge, c'est le **cardinal** qui l'atteint.
#: Il est passe de la dizaine a une vingtaine d'emplacements, parce que le symbole le
#: plus gros demande le meme nombre d'octets et que chaque emplacement en coute 28 au
#: lieu de 48. Le balayage a du etre etendu pour continuer a l'atteindre.
_QR_ZONE_WORST_MARGIN_BY_VERSION = {"v1": 0.376, "v2": 0.0}


@pytest.mark.parametrize("geometry_version", ["v1", "v2"])
def test_the_enlarged_qr_fits_the_reserved_zone_at_the_worst_cardinal(
        geometry_version: str) -> None:
    """Le cardinal 8 n'est pas le pire cas (revue 5.9-C2).

    L'emprise QR n'est pas monotone en nombre de slots: le symbole grandit par
    paliers de version QR, et la zone de silence suit le cote de module, si
    bien qu'un cardinal intermediaire peut serrer davantage. Verifier le seul
    cardinal 8 laissait donc la vraie marge minimale hors du test -- 0,376 mm
    et non 1,73. Le balayage porte desormais sur tout le vocabulaire de
    cardinaux, et la marge la plus faible est epinglee.

    **La story 5.15 s'appuie sur cette non-monotonie**: c'est elle qui fait que le
    majorant d'emprise reserve au bord porteur du QR se calcule aux deux extremites du
    domaine de modules et non au cardinal le plus lourd.
    """
    template_id = page_templates.build_template_id("portrait", 8, "2", geometry_version)
    zone = next(
        z for z in patch_presets.reserved_zones_mm(template_id) if z["name"] == "qr_zone"
    )
    margins = {}
    # **Balayage etendu par la story 5.17**: il s'arretait au cardinal 10, ou le
    # majorant d'emprise n'etait plus atteint sous les cles courtes (le symbole le plus
    # gros demande maintenant une vingtaine d'emplacements). Un balayage qui n'atteint
    # pas le majorant transforme l'assertion « marge minimale nulle » en un chiffre
    # arbitraire, et c'est exactement ce qui s'est passe. La borne haute est donc le
    # plafond de payload lui-meme, atteint par la rupture ci-dessous.
    for slots_per_page in range(1, 40):
        try:
            result = page_payload.plan_page_payload(
                project_id=REFERENCE_IDS[0], rush_id=REFERENCE_IDS[1], lot_id=REFERENCE_IDS[2],
                page_index=0, page_count=3, fps_target=24.0, timecode_base_fps="25/1",
                template_id=template_id, patch_preset_id="patches-18-v2",
                target_colorspace="bt709", gamut_map_id=payload_io.GAMUT_MAP_IDENTITY,
                slots=[
                    {"slot_index": i, "frame_timecode": f"00:00:{i // 60:02d}:{i % 60:02d}"}
                    for i in range(slots_per_page)
                ],
            )
        except payload_io.PayloadBudgetExceeded:
            break
        module_mm = result.print_size_mm / result.module_side
        footprint = result.print_size_mm + 2 * qr_codes.QUIET_ZONE_MODULES * module_mm
        margins[slots_per_page] = zone["width"] - footprint

    assert margins, "aucun cardinal exploitable"
    worst_cardinal = min(margins, key=margins.get)
    worst_margin = margins[worst_cardinal]
    # Le symbole tient partout, y compris au pire cardinal. La tolerance est celle de
    # `_qr_footprint_rect`, seul arbitre reel: la zone derivee de la v2 vaut exactement
    # le majorant d'emprise, donc l'egalite est le cas nominal et non une limite frolee.
    assert worst_margin >= -1e-9, (worst_cardinal, worst_margin)
    # Et la marge la plus faible est epinglee: son erosion doit se voir.
    assert worst_margin == pytest.approx(
        _QR_ZONE_WORST_MARGIN_BY_VERSION[geometry_version], abs=0.02
    ), (worst_cardinal, worst_margin)


# --- `EPIC11-ARB-108`, annexe QR : la frontiere que la mesure d'origine
# n'avait pas posee ------------------------------------------------------
#
# Le document du 2026-08-30 concluait « aucun regime n'atteint la version
# bannie 22 ». C'est faux, et la revue du 2026-08-31 l'a mesure : le regime
# maximal du banc valait `"x" * 48` alors que `CANONICAL_ID_MAX_LENGTH` vaut
# **64**. A la vraie borne, la version 22 est atteinte -- mais SANS le champ,
# donc ce n'est pas ce champ qui l'y met.
#
# La question qui engage un champ neuf n'est pas « le domaine touche-t-il la
# version bannie ? » mais « ce champ l'y fait-il ENTRER ? ». C'est cette
# question-la que le banc pose desormais, et elle vaudra pour le prochain
# champ ajoute au payload.

MAX_IDS = tuple("x" * naming.CANONICAL_ID_MAX_LENGTH for _ in range(5))


def _version_de_symbole(texte: str) -> int:
    """Par le CHEMIN DE PRODUCTION : le cote du raster de l'encodeur.

    Jamais un nombre de modules pose a la main -- c'est l'erreur d'un facteur
    trois du 2026-08-11 --, et jamais `cv2.QRCodeEncoder` en direct, qui est
    celle du 2026-08-30 : les versions descendaient quand les octets montaient.
    """
    return qr_codes.symbol_version(int(qr_codes.encode_qr_image(texte).shape[0]))


def _texte_de_payload(slots_per_page: int, ids, *, version_rank=None) -> str:
    extra = {} if version_rank is None else {"version_rank": version_rank}
    return page_payload.plan_page_payload(
        project_id=ids[0], rush_id=ids[1], lot_id=ids[2], page_index=0,
        page_count=3, fps_target=24.0, timecode_base_fps="25/1",
        template_id=ids[3], patch_preset_id=ids[4], target_colorspace="bt709",
        gamut_map_id=payload_io.GAMUT_MAP_IDENTITY,
        slots=[{"slot_index": i, "frame_timecode": f"00:00:{i:02d}:00"}
               for i in range(slots_per_page)],
        **extra,
    ).payload_text


def _cardinaux_reellement_composables() -> tuple[int, ...]:
    """Les cardinaux que le REGISTRE de gabarits sait produire.

    **Un banc qui balaie `range(1, 9)` mesure des planches qui n'existent
    pas** (corrige le 2026-08-31, sur remarque d'Egan). Une planche porte 1, 2,
    3, 4, 6 ou 8 frames -- jamais 7 --, et c'est precisement au cardinal 7 que
    la premiere redaction de ce test avait cru trouver un defaut. Un
    franchissement a un cardinal impossible est un fantome : il coute une
    correction et une entree de dette pour un cas qu'aucun operateur ne peut
    atteindre.

    La liste se LIT au registre plutot que d'etre figee ici : si un gabarit a
    7 emplacements etait ajoute un jour, ce test le couvrirait d'office au lieu
    de rester silencieux sur lui.
    """
    cardinaux = {
        page_templates.get_template(identifiant).frames_per_page
        for identifiant in page_templates.known_template_ids()
    }
    return tuple(sorted(c for c in cardinaux if c >= 1))


#: Aucun franchissement de la version bannie n'est cause par `version_rank` sur
#: un cardinal REELLEMENT composable (mesure le 2026-08-31).
#:
#: L'ensemble est EPINGLE plutot que simplement verifie vide : un
#: franchissement de plus, cause par ce champ ou par le prochain ajoute au
#: payload, rougit en nommant le cardinal.
FRANCHISSEMENTS_CONNUS = {"reference": (), "long": (), "maximal": ()}


@pytest.mark.parametrize("regime", ["reference", "long", "maximal"])
def test_les_franchissements_de_version_BANNIE_sont_EXACTEMENT_ceux_connus(regime):
    """Le champ ne doit pas ajouter de cardinal indecodable en silence.

    La question qui engage un champ neuf n'est pas « le domaine touche-t-il la
    version bannie ? » -- il la touche deja sans lui aux cardinaux 8 et plus du
    regime maximal -- mais « ce champ y fait-il ENTRER une combinaison qui n'y
    etait pas ? ».

    La reponse mesuree, sur les cardinaux REELLEMENT composables : **aucun**.

    La premiere redaction de ce test balayait `range(1, 9)` et croyait avoir
    trouve un franchissement au cardinal 7. Il n'existe pas de planche a 7
    frames : le defaut etait un fantome ne d'un banc qui mesurait des planches
    impossibles.
    """
    ids = {"reference": REFERENCE_IDS, "long": LONG_IDS, "maximal": MAX_IDS}[regime]
    franchissements = []
    for cardinal in _cardinaux_reellement_composables():
        try:
            sans = _version_de_symbole(_texte_de_payload(cardinal, ids))
            avec = _version_de_symbole(
                _texte_de_payload(cardinal, ids, version_rank=naming.VERSION_RANK_MAX))
        except payload_io.PayloadBudgetExceeded:
            # Le plafond dur a mordu AVANT la version de symbole : c'est un
            # refus nomme, pas un franchissement silencieux.
            continue
        if sans not in qr_codes.QR_BANNED_SYMBOL_VERSIONS \
                and avec in qr_codes.QR_BANNED_SYMBOL_VERSIONS:
            franchissements.append((cardinal, sans, avec))
    assert tuple(franchissements) == FRANCHISSEMENTS_CONNUS[regime], (
        f"Les franchissements de version BANNIE du regime {regime!r} ont change: "
        f"mesure {tuple(franchissements)}, connu {FRANCHISSEMENTS_CONNUS[regime]}. "
        "Un franchissement de PLUS rend une combinaison indecodable a toute "
        "taille imprimee ; un de MOINS est une bonne nouvelle a consigner."
    )


def test_le_banc_ne_mesure_QUE_des_planches_qui_existent():
    """La garde qui empeche le fantome de revenir.

    Elle vaut pour toute mesure de charge utile : un cardinal qu'aucun gabarit
    ne produit donne un chiffre vrai sur une planche impossible, et une
    conclusion fausse sur le produit.
    """
    cardinaux = _cardinaux_reellement_composables()
    assert 7 not in cardinaux, (
        "un gabarit a 7 emplacements est apparu : reprendre la mesure de la "
        "version de symbole, c'est le cardinal ou `version_rank` fait franchir "
        "la frontiere bannie (21 -> 22 au regime maximal)."
    )
    assert set(cardinaux) == {1, 2, 3, 4, 6, 8}, (
        f"les cardinaux composables ont change: {cardinaux}. La mesure QR de "
        "`EPIC11-ARB-108` porte sur cette liste et doit etre refaite."
    )


def test_le_regime_MAXIMAL_se_construit_sur_la_borne_REELLE_du_depot():
    """Un regime « maximal » plus court que la borne ne mesure pas le pire.

    Le banc d'origine figeait 48 en dur alors que la borne valait 64, et c'est
    exactement cet ecart qui a fait publier une conclusion fausse. Lier la
    fabrique a la constante empeche que l'ecart revienne en silence si la borne
    bouge -- dans un sens comme dans l'autre.
    """
    assert len(MAX_IDS[0]) == naming.CANONICAL_ID_MAX_LENGTH


def test_la_borne_des_IDENTIFIANTS_reste_sous_la_FALAISE_du_QR():
    """`EPIC11-ARB-110`. La frontiere qui empeche le defaut de revenir.

    La borne avait ete portee de 48 a 64 le 2026-08-28 par un commit qui n'a
    mesure aucun QR, et cela franchissait une falaise que personne n'avait
    cherchee : au cardinal 8, cinq identifiants de 58 caracteres encodent sur
    la version 22 du symbole, indecodable a toute taille imprimee.

    Ce test ne fige pas 48 : il MESURE que la borne courante, quelle qu'elle
    soit, laisse tous les cardinaux composables hors des versions bannies. Une
    remontee de la borne -- ou un champ ajoute au payload -- le fait rougir en
    disant lequel casse.
    """
    casses = []
    for cardinal in _cardinaux_reellement_composables():
        for rang in (None, naming.VERSION_RANK_MAX):
            try:
                version = _version_de_symbole(
                    _texte_de_payload(cardinal, MAX_IDS, version_rank=rang))
            except payload_io.PayloadBudgetExceeded:
                casses.append((cardinal, rang, "plafond dur 768"))
                continue
            if version in qr_codes.QR_BANNED_SYMBOL_VERSIONS:
                casses.append((cardinal, rang, f"version {version} BANNIE"))
    assert casses == [], (
        f"A la borne de {naming.CANONICAL_ID_MAX_LENGTH} caracteres, ces "
        f"combinaisons ne sont pas composables: {casses}. La falaise mesuree "
        "est a 58 caracteres au cardinal 8 (`EPIC11-ARB-110`)."
    )


def test_la_borne_garde_une_MARGE_et_pas_seulement_la_falaise():
    """48 est retenue plutot que 57, et la marge se mesure.

    A la falaise exacte, le prochain champ ajoute au payload reconduirait le
    defaut a l'identique. Ce test verifie qu'il reste de la place : les
    identifiants pourraient grandir de plusieurs caracteres sans rien casser.
    """
    # La borne se REFUSE a mesurer sa propre marge : `plan_page_payload` valide
    # la canonicite des identifiants, donc on ne peut pas lui en passer de plus
    # longs que la borne. On allonge donc le payload DEJA construit, ce qui
    # mesure exactement la meme chose -- le QR ne voit que des octets.
    reference = page_payload.plan_page_payload(
        project_id=MAX_IDS[0], rush_id=MAX_IDS[1], lot_id=MAX_IDS[2],
        page_index=0, page_count=3, fps_target=24.0, timecode_base_fps="25/1",
        template_id=MAX_IDS[3], patch_preset_id=MAX_IDS[4],
        target_colorspace="bt709", gamut_map_id=payload_io.GAMUT_MAP_IDENTITY,
        slots=[{"slot_index": i, "frame_timecode": f"00:00:{i:02d}:00"}
               for i in range(8)],
        version_rank=naming.VERSION_RANK_MAX,
    )
    cles_d_identifiant = [
        cle for cle, valeur in reference.payload.items()
        if isinstance(valeur, str) and valeur == MAX_IDS[0]
    ]
    assert cles_d_identifiant, "aucun identifiant reconnu dans le payload"

    marge = 0
    for longueur in range(naming.CANONICAL_ID_MAX_LENGTH + 1, 60):
        allonge = dict(reference.payload)
        for cle in cles_d_identifiant:
            allonge[cle] = "x" * longueur
        version = _version_de_symbole(payload_io.serialize_payload(allonge))
        if version in qr_codes.QR_BANNED_SYMBOL_VERSIONS:
            break
        marge = longueur - naming.CANONICAL_ID_MAX_LENGTH
    assert marge >= 5, (
        f"la borne de {naming.CANONICAL_ID_MAX_LENGTH} n'a que {marge} "
        "caractere(s) de marge sous la falaise : trop peu pour absorber un "
        "champ de plus au payload."
    )


def test_une_version_BANNIE_est_inutilisable_a_TOUTE_taille_imprimee():
    """La garde qui fait que rien ne s'imprime en silence.

    C'est elle qui rend le defaut ci-dessus supportable : le regime maximal
    atteint bien la version 22 au cardinal 8, mais la composition refuse.
    """
    bannie = min(qr_codes.QR_BANNED_SYMBOL_VERSIONS)
    cote = 4 * bannie + 17
    for taille_mm, dpi in ((20.0, 300), (60.0, 600), (200.0, 1200)):
        assert qr_codes.check_print_geometry(cote, taille_mm, dpi) == qr_codes.GEOMETRY_UNUSABLE
    # Controle negatif : une version voisine NON bannie reste utilisable a
    # taille genereuse, sans quoi ce test passerait pour n'importe quoi.
    voisine = 4 * (bannie + 1) + 17
    assert qr_codes.check_print_geometry(voisine, 200.0, 1200) == qr_codes.GEOMETRY_RELIABLE


def test_le_refus_de_version_BANNIE_nomme_les_DEUX_leviers():
    """`EPIC11-ARB-110`. Un message qui tait la cause fait tourner en rond.

    Il ne nommait que `--frames-par-page`, qui debloque effectivement -- mais
    l'operateur ne pouvait pas apprendre POURQUOI, ni que la longueur de ses
    identifiants pese dans chaque QR de chaque planche. Le message de la page
    de calibration nommait deja les identifiants, parce que cette page n'a
    aucun emplacement et que le cardinal n'y peut rien.
    """
    import inspect

    source = inspect.getsource(pdf_composition)
    debut = source.index("le QR encoderait sur la ")
    fin = source.index('"""', debut) if '"""' in source[debut:debut + 4000] else debut + 2000
    message = source[debut:fin]
    assert "--frames-par-page" in message
    assert "identifiants" in message, (
        "le refus ne nomme pas la longueur des identifiants, qui est la CAUSE "
        "-- l'operateur ne peut pas la deviner depuis un conseil de cardinal."
    )
