from __future__ import annotations

import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility.io import payload as payload_io
from mixed_media_utility.io.payload import (
    ALERT_BUDGET_BYTES,
    NOMINAL_BUDGET_BYTES,
    PAYLOAD_SCHEMA_VERSION,
    PayloadBudgetExceeded,
    PayloadValidationError,
    build_page_payload,
    check_payload_budget,
    parse_payload,
    serialize_payload,
    validate_payload,
)


def _slots() -> list[dict]:
    return [
        {"slot_index": 0, "frame_timecode": "00:00:00:00"},
        {"slot_index": 1, "frame_timecode": "00:00:01:12"},
    ]


def _valid_payload() -> dict:
    """Payload minimal valide, construit par le vrai producteur."""
    return build_page_payload(
        project_id="demo-project-01",
        rush_id="rush-a1",
        lot_id="lot-0007",
        page_index=0,
        page_count=1,
        timecode_base_fps="25/1",
        fps_target=24.0,
        template_id="tpl-a4-portrait-2f-v1",
        patch_preset_id="patches-12-v1",
        target_colorspace="bt709",
        gamut_map_id=payload_io.GAMUT_MAP_IDENTITY,
        slots=_slots(),
    )


def test_build_page_payload_contains_required_fields() -> None:
    payload = build_page_payload(
        project_id="example-001",
        rush_id="rush-001",
        lot_id="lot-001",
        page_index=0,
        page_count=1,
        timecode_base_fps="25/1",
        fps_target=24.0,
        template_id="template-a4-16x9",
        patch_preset_id="patch-preset-mvp",
        target_colorspace="rec709",
        gamut_map_id="gamut-map-none-1",
        slots=_slots(),
    )

    assert payload["schema_version"] == PAYLOAD_SCHEMA_VERSION
    assert payload["project_id"] == "example-001"
    assert payload["rush_id"] == "rush-001"
    assert payload["lot_id"] == "lot-001"
    assert payload["page_index"] == 0
    assert payload["page_count"] == 1
    assert payload["fps_target"] == 24.0
    assert payload["template_id"] == "template-a4-16x9"
    assert payload["patch_preset_id"] == "patch-preset-mvp"
    assert payload["target_colorspace"] == "rec709"
    assert payload["slots"] == _slots()


def test_build_page_payload_rejects_page_index_out_of_range() -> None:
    with pytest.raises(PayloadValidationError, match="page_index"):
        build_page_payload(
            project_id="example-001",
            rush_id="rush-001",
            lot_id="lot-001",
            page_index=2,
            page_count=2,
            timecode_base_fps="25/1",
            fps_target=24.0,
            template_id="template-a4-16x9",
            patch_preset_id="patch-preset-mvp",
            target_colorspace="rec709",
            gamut_map_id="gamut-map-none-1",
            slots=_slots(),
        )


def test_build_page_payload_rejects_empty_slots() -> None:
    with pytest.raises(PayloadValidationError, match="slots"):
        build_page_payload(
            project_id="example-001",
            rush_id="rush-001",
            lot_id="lot-001",
            page_index=0,
            page_count=1,
            timecode_base_fps="25/1",
            fps_target=24.0,
            template_id="template-a4-16x9",
            patch_preset_id="patch-preset-mvp",
            target_colorspace="rec709",
            gamut_map_id="gamut-map-none-1",
            slots=[],
        )


def test_build_page_payload_rejects_non_positive_fps() -> None:
    with pytest.raises(PayloadValidationError, match="fps_target"):
        build_page_payload(
            project_id="example-001",
            rush_id="rush-001",
            lot_id="lot-001",
            page_index=0,
            page_count=1,
            timecode_base_fps="25/1",
            fps_target=0,
            template_id="template-a4-16x9",
            patch_preset_id="patch-preset-mvp",
            target_colorspace="rec709",
            gamut_map_id="gamut-map-none-1",
            slots=_slots(),
        )


@pytest.mark.parametrize(
    "valeur",
    [
        24.0,     # flottant : la forme interdite par l'AC 1, jamais un aller-retour sur.
        "24",     # pas de denominateur.
        "0/1",    # numerateur nul.
        "24/0",   # denominateur nul.
        "",       # chaine vide.
        True,     # bool : `isinstance(True, int)` vaut vrai en Python, jamais accepte ici.
    ],
)
def test_build_page_payload_rejects_malformed_timecode_base_fps(valeur) -> None:
    """AC 1, story 2.7 : les formes invalides de la cadence source sont nommees.

    Chaque forme est un piege distinct pris seul (regle des fabriques, meme motif que
    `gamut_map_id` plus bas dans ce fichier): un flottant qui survivrait a un
    aller-retour JSON casserait `"30000/1001"` (le cas NTSC reel), et un bool qui
    passerait le test `isinstance(..., int)` de Python sans garde explicite est
    exactement le piege que `gamut_map_id` a deja paye ailleurs dans ce module.
    """
    with pytest.raises(PayloadValidationError, match="timecode_base_fps"):
        build_page_payload(
            project_id="example-001",
            rush_id="rush-001",
            lot_id="lot-001",
            page_index=0,
            page_count=1,
            timecode_base_fps=valeur,
            fps_target=24.0,
            template_id="template-a4-16x9",
            patch_preset_id="patch-preset-mvp",
            target_colorspace="rec709",
            gamut_map_id="gamut-map-none-1",
            slots=_slots(),
        )


def test_serialize_payload_is_compact_and_human_readable() -> None:
    payload = build_page_payload(
        project_id="example-001",
        rush_id="rush-001",
        lot_id="lot-001",
        page_index=0,
        page_count=1,
        timecode_base_fps="25/1",
        fps_target=24.0,
        template_id="template-a4-16x9",
        patch_preset_id="patch-preset-mvp",
        target_colorspace="rec709",
        gamut_map_id="gamut-map-none-1",
        slots=_slots(),
    )

    text = serialize_payload(payload)

    assert isinstance(text, str)
    # Story 5.17: ce qui est imprime porte les **cles courtes**. Le nom long ne doit
    # pas y figurer -- une serialisation qui emettrait les deux formes couterait les
    # octets que la story vient de gagner, et le test qui epinglait `project_id`
    # aurait laisse passer exactement cela.
    assert '"pid"' in text
    assert "project_id" not in text
    assert '"example-001"' in text
    # No whitespace padding: compact separators keep the payload short.
    assert ", " not in text
    assert ": " not in text


def test_payload_roundtrip_through_serialize_and_parse() -> None:
    payload = build_page_payload(
        project_id="example-001",
        rush_id="rush-001",
        lot_id="lot-001",
        page_index=0,
        page_count=1,
        timecode_base_fps="25/1",
        fps_target=24.0,
        template_id="template-a4-16x9",
        patch_preset_id="patch-preset-mvp",
        target_colorspace="rec709",
        gamut_map_id="gamut-map-none-1",
        slots=_slots(),
    )

    text = serialize_payload(payload)
    parsed = parse_payload(text)

    assert parsed == payload


def test_parse_payload_rejects_invalid_json() -> None:
    with pytest.raises(PayloadValidationError):
        parse_payload("{not-json")


def test_parse_payload_rejects_missing_required_field() -> None:
    payload = build_page_payload(
        project_id="example-001",
        rush_id="rush-001",
        lot_id="lot-001",
        page_index=0,
        page_count=1,
        timecode_base_fps="25/1",
        fps_target=24.0,
        template_id="template-a4-16x9",
        patch_preset_id="patch-preset-mvp",
        target_colorspace="rec709",
        gamut_map_id="gamut-map-none-1",
        slots=_slots(),
    )
    del payload["rush_id"]
    text = serialize_payload(payload)

    with pytest.raises(PayloadValidationError, match="rush_id"):
        parse_payload(text)


def test_validate_payload_rejects_slot_missing_frame_timecode() -> None:
    payload = build_page_payload(
        project_id="example-001",
        rush_id="rush-001",
        lot_id="lot-001",
        page_index=0,
        page_count=1,
        timecode_base_fps="25/1",
        fps_target=24.0,
        template_id="template-a4-16x9",
        patch_preset_id="patch-preset-mvp",
        target_colorspace="rec709",
        gamut_map_id="gamut-map-none-1",
        slots=_slots(),
    )
    payload["slots"] = [{"slot_index": 0}]

    with pytest.raises(PayloadValidationError, match="frame_timecode"):
        validate_payload(payload)


def test_check_payload_budget_reports_within_nominal_for_typical_payload() -> None:
    payload = build_page_payload(
        project_id="example-001",
        rush_id="rush-001",
        lot_id="lot-001",
        page_index=0,
        page_count=1,
        timecode_base_fps="25/1",
        fps_target=24.0,
        template_id="template-a4-16x9",
        patch_preset_id="patch-preset-mvp",
        target_colorspace="rec709",
        gamut_map_id="gamut-map-none-1",
        slots=_slots(),
    )

    report = check_payload_budget(payload)

    assert report.size_bytes == len(serialize_payload(payload).encode("utf-8"))
    assert report.nominal_budget == NOMINAL_BUDGET_BYTES
    assert report.alert_budget == ALERT_BUDGET_BYTES
    assert report.within_nominal is True
    assert report.within_alert is True


def test_check_payload_budget_flags_beyond_nominal_but_within_alert() -> None:
    """Le regime intermediaire existe, et le cardinal qui l'atteint est **cherche**.

    Ce test epinglait 10 emplacements. La story 5.17 (cles courtes) a fait retomber
    un payload de 10 emplacements **sous** le budget nominal, et le test ne mesurait
    alors plus le regime qu'il nomme -- il aurait fallu qu'il echoue pour le dire, ce
    qu'il a fait, mais un test qui suit la premiere frontiere plutot qu'un cardinal
    fige n'aurait rien eu a reecrire. C'est la lecon, pas le chiffre.
    """
    def report_for(count: int):
        return check_payload_budget(build_page_payload(
            project_id="example-001",
            rush_id="rush-001",
            lot_id="lot-001",
            page_index=0,
            page_count=1,
            timecode_base_fps="25/1",
            fps_target=24.0,
            template_id="template-a4-16x9",
            patch_preset_id="patch-preset-mvp",
            target_colorspace="rec709",
            gamut_map_id="gamut-map-none-1",
            slots=[{"slot_index": index, "frame_timecode": "00:00:00:00"}
                   for index in range(count)],
        ))

    first_over_nominal = next(
        count for count in range(1, 40) if not report_for(count).within_nominal
    )
    report = report_for(first_over_nominal)

    assert NOMINAL_BUDGET_BYTES < report.size_bytes <= ALERT_BUDGET_BYTES
    assert report.within_nominal is False
    assert report.within_alert is True
    # Le cardinal precedent est, lui, sous le budget nominal: la frontiere est bien
    # une frontiere et non le premier cardinal essaye.
    assert report_for(first_over_nominal - 1).within_nominal is True


def test_check_payload_budget_raises_when_exceeding_ceiling() -> None:
    slots = [
        {"slot_index": index, "frame_timecode": "00:00:00:00"} for index in range(200)
    ]
    payload = build_page_payload(
        project_id="example-001",
        rush_id="rush-001",
        lot_id="lot-001",
        page_index=0,
        page_count=1,
        timecode_base_fps="25/1",
        fps_target=24.0,
        template_id="template-a4-16x9",
        patch_preset_id="patch-preset-mvp",
        target_colorspace="rec709",
        gamut_map_id="gamut-map-none-1",
        slots=slots,
    )

    with pytest.raises(PayloadBudgetExceeded, match="768"):
        check_payload_budget(payload)


# --- Story 5.9: gamut_map_id, onzieme champ scalaire obligatoire ------------


def test_gamut_map_id_is_required_and_named_in_the_error() -> None:
    # EPIC5-ARB-13: rien n'a ete imprime en usage reel, donc aucune
    # compatibilite ascendante a construire. Le champ est obligatoire, sans
    # bump de schema_version, sans branche « champ absent » nulle part.
    payload = _valid_payload()
    del payload["gamut_map_id"]
    with pytest.raises(payload_io.PayloadValidationError) as excinfo:
        payload_io.validate_payload(payload)
    assert "gamut_map_id" in str(excinfo.value)


def test_gamut_map_id_did_not_bump_the_schema_version() -> None:
    # Piege 3 de la story 5.9: ne pas se servir de la simplification
    # d'EPIC5-ARB-13 comme d'un pretexte pour bumper « tant qu'a faire ». Ce
    # qu'epinglait ce test, c'est que **l'ajout d'un champ** n'a pas bumpe.
    #
    # La version, elle, a bumpe deux fois depuis (5.17: format a cles courtes;
    # 2.7: `timecode_base_fps`, EPIC7-ARB-56) -- mais ni l'une ni l'autre pour
    # `gamut_map_id`. Ce test suit donc la constante plutot que de l'epingler
    # (lecon de la tautologie 5.9, `politique-revue-et-mutation-testing.md`
    # section 6): sa propriete reste "gamut_map_id est present, sans branche
    # champ absent, quelle que soit la version courante".
    assert "gamut_map_id" in payload_io._REQUIRED_SCALAR_FIELDS
    assert "gamut_map_id" in payload_io.PAYLOAD_SHORT_KEYS
    assert "gamut_map_id" not in payload_io.REREAD_DEFAULTS


def test_the_identity_is_a_first_class_value_not_a_degraded_case() -> None:
    assert payload_io.GAMUT_MAP_IDENTITY == "gamut-map-none-1"
    assert payload_io.validate_gamut_map_id(payload_io.GAMUT_MAP_IDENTITY)
    payload_io.validate_payload(_valid_payload())


@pytest.mark.parametrize(
    "value",
    [
        "gamut-map-none-1",
        "gamut-map-perceptual-1",
        "gamut-map-soft-clip-12",
    ],
)
def test_well_formed_gamut_map_ids_are_accepted(value: str) -> None:
    assert payload_io.validate_gamut_map_id(value) == value
    assert len(value) <= payload_io.GAMUT_MAP_ID_MAX_LENGTH


@pytest.mark.parametrize(
    "value",
    [
        "",
        "none-1",                    # prefixe absent
        "gamut-map-none",            # version absente
        "gamut-map--1",              # nom vide
        "GAMUT-MAP-NONE-1",          # majuscules
        "gamut_map_none_1",          # separateurs invalides
        "gamut-map-none-v1",         # version non numerique
        None,
        42,
    ],
)
def test_malformed_gamut_map_ids_are_refused(value) -> None:
    with pytest.raises(payload_io.PayloadValidationError):
        payload_io.validate_gamut_map_id(value)


def test_gamut_map_id_longer_than_the_contract_is_refused() -> None:
    # AC 12: la longueur est une contrainte de contrat, pas une recommandation.
    # Chaque caractere coute un octet au payload QR, et le budget est mesure.
    too_long = "gamut-map-" + "a" * 13 + "-1"
    assert len(too_long) == payload_io.GAMUT_MAP_ID_MAX_LENGTH + 1
    with pytest.raises(payload_io.PayloadValidationError) as excinfo:
        payload_io.validate_gamut_map_id(too_long)
    message = str(excinfo.value)
    assert str(len(too_long)) in message
    assert str(payload_io.GAMUT_MAP_ID_MAX_LENGTH) in message
    # Un caractere de moins passe: la borne est inclusive.
    at_limit = "gamut-map-" + "a" * 12 + "-1"
    assert len(at_limit) == payload_io.GAMUT_MAP_ID_MAX_LENGTH
    assert payload_io.validate_gamut_map_id(at_limit)


def test_the_builder_has_no_default_for_gamut_map_id() -> None:
    """Un defaut aurait cree exactement le motif que la story combat (AC 11).

    `gamut-map-none-1` serait juste aujourd'hui et faux en silence des que la
    story 5.10 applique une compression reelle: un appelant qui oublie
    l'argument emettrait un payload declarant « aucune compression » sur une
    image comprimee, et le scan ne la decomprimerait pas. La regle du depot est
    de rendre la faute impossible, pas detectable.
    """
    import inspect

    signature = inspect.signature(payload_io.build_page_payload)
    parameter = signature.parameters["gamut_map_id"]
    assert parameter.default is inspect.Parameter.empty
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY


def test_the_contract_itself_validates_gamut_map_id_not_only_the_helper() -> None:
    """Mutant survivant en revue (5.9-C1-1): retirer l'appel a
    `validate_gamut_map_id` depuis `validate_payload` laissait la suite verte.

    Tous les tests appelaient le validateur **en direct**; aucun ne verifiait
    que le contrat l'invoque. Dans la sandbox mutee, un
    `gamut_map_id: "PERCEPTUAL v2 (?!)"` traversait `parse_payload` et
    atterrissait dans le manifest reconstruit. Ce test passe donc par la
    surface publique et par elle seule.
    """
    for malformed in ("PERCEPTUAL v2 (?!)", "none-1", "gamut-map-" + "a" * 20 + "-1", ""):
        payload = _valid_payload()
        payload["gamut_map_id"] = malformed
        with pytest.raises(PayloadValidationError):
            validate_payload(payload)
        with pytest.raises(PayloadValidationError):
            build_page_payload(
                project_id="demo-project-01", rush_id="rush-a1", lot_id="lot-0007",
                page_index=0, page_count=1, fps_target=24.0, timecode_base_fps="25/1",
                template_id="tpl-a4-portrait-2f-v1", patch_preset_id="patches-12-v1",
                target_colorspace="bt709", gamut_map_id=malformed, slots=_slots(),
            )


def test_a_malformed_gamut_map_id_cannot_survive_a_serialize_parse_roundtrip() -> None:
    # La lecture ne normalise rien et n'injecte aucun defaut (EPIC5-ARB-13):
    # un payload malforme doit etre refuse a l'entree comme a la sortie.
    payload = _valid_payload()
    payload["gamut_map_id"] = "gamut-map-NONE-1"
    with pytest.raises(PayloadValidationError):
        validate_payload(payload)
    text = serialize_payload(payload)
    with pytest.raises(PayloadValidationError):
        validate_payload(parse_payload(text))
