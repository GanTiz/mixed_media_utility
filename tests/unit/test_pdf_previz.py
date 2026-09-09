"""Tests du contrat de donnees de previz PDF (story 4.9).

Jumelle de `test_extraction_previz.py` (story 3.5): purete AST, enveloppe
`previz-1` reprise telle quelle avec `kind = "makepdf"`, projection verbatim
du plan de page de 4.1, serialisation canonique deterministe, empreintes de
peremption, vocabulaire ferme d'avertissements.

Le plan d'entree des tests est un objet structurel (SimpleNamespace) faconne
comme `pdf_composition.LotComposition`: le module est duck-type (Protocol)
precisement pour ne pas importer `pdf_composition` (qui tire cv2) -- les
sentinelles incoherentes verifient le transport verbatim (motif AC 2 de 3.5).
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import extraction_previz, pdf_previz
from mixed_media_utility.io.manifest import _iter_absolute_path_violations

MODULE_PATH = REPO_ROOT / "src" / "mixed_media_utility" / "pdf_previz.py"

GENERATED_AT = "2026-08-06T12:00:00Z"


# ---------------------------------------------------------------------------
# Fabrique d'un plan structurel minimal (sentinelles transportables verbatim)
# ---------------------------------------------------------------------------


def make_plan(**overrides):
    qr = SimpleNamespace(
        payload_text='{"k":1}',
        budget=SimpleNamespace(size_bytes=402),
        print_size_mm=35.0,
        geometry_status="reliable",
        footprint_rect_mm=(85.05, 11.05, 37.9, 37.9),
    )
    frame = SimpleNamespace(
        slot_index=0,
        frame_timecode="00:00:00:00",
        frame_filename="rush-001_5_00-00-00-00.tiff",
        zone_name="frame_zone_1",
        zone_rect_mm=(35.0, 60.0, 140.0, 78.75),
        image_rect_mm=(35.0, 60.0, 140.0, 78.75),
        letterbox_policy="letterbox-centre",
    )
    marker = SimpleNamespace(marker_id=0, center_x_mm=30.0, center_y_mm=30.0, size_mm=30.0)
    patch = SimpleNamespace(
        value_id="neutral-020", rgb=(51, 51, 51), x_mm=14.0, y_mm=62.0, size_mm=12.0
    )
    block = SimpleNamespace(
        name="footer_block",
        rect_mm=(60.0, 240.0, 90.0, 45.0),
        font_pt=8.0,
        lines=("lot-a_p001", "proj-a"),
    )
    slot_label = SimpleNamespace(
        text="rush-001 s00 tc 00:00:00:00",
        rect_mm=(35.0, 139.0, 140.0, 4.0),
    )
    text = SimpleNamespace(
        sheet_label="lot-a_p001",
        blocks=(block,),
        slot_labels=(slot_label,),
        zones_mm={"footer_block": (60.0, 240.0, 90.0, 45.0)},
    )
    page = SimpleNamespace(
        page_index=0,
        template_id="tpl-a4-portrait-2f-v1",
        frames=(frame,),
        qr=qr,
        markers=(marker,),
        patches=(patch,),
        text=text,
    )
    plan = SimpleNamespace(
        project_id="proj-a",
        rush_id="rush-001",
        lot_id="lot-a",
        fps_target=5.0,
        page_format="A4",
        orientation="portrait",
        frames_per_page=2,
        margin_preset="0",
        template_id="tpl-a4-portrait-2f-v1",
        patch_preset_id="patches-12-v1",
        # AMENDE PAR LA STORY 5.10 (AC 12): `gamut_map_id` est une entree de
        # decision de la composition, donc il entre au protocole structurel,
        # a la projection JSON et a l'empreinte. Le plan de fixture doit le
        # porter, sinon la previz refuse -- ce qui est le comportement voulu.
        gamut_map_id="gamut-map-none-1",
        render_dpi=600,
        scan_dpi=600,
        frames_dir="frames/rush-001_5",
        pdf_filename="proj-a_rush-001_lot-a_planches.pdf",
        page_count=1,
        pages=(page,),
        warnings=(),
    )
    for key, value in overrides.items():
        setattr(plan, key, value)
    return plan


def build(plan=None, **kwargs):
    plan = plan if plan is not None else make_plan()
    defaults = dict(
        plan=plan,
        generated_at_utc=GENERATED_AT,
        expected_frame_count=1,
        selection_fingerprint=extraction_previz.fingerprint_of({"sentinel": 1}),
    )
    defaults.update(kwargs)
    return pdf_previz.build_pdf_previz(**defaults)


# ---------------------------------------------------------------------------
# AC 1: purete du module (motif AST de 3.5)
# ---------------------------------------------------------------------------

ALLOWED_ABSOLUTE_IMPORTS = {
    "__future__",
    "dataclasses",
    "datetime",
    "re",
    "typing",
}
# `previz_common` elargit la liste blanche a la story 5.8. La note differee du
# 2026-08-06 consignait precisement que la jonction imposerait d'elargir « la
# liste blanche des deux suites de tests dans la meme story »: c'est ici la
# seconde des deux.
#
# `extraction_previz` en a ete **retire** a la passe de correction de 5.8
# (revue couche 3, AC 1). La justification commitee disait « 4.9 continue
# d'importer les helpers sous leurs noms actuels, re-exportes »: c'etait faux
# depuis la meme passe. Avant 5.8, `pdf_previz.py` portait
# `from .extraction_previz import (...)`; apres, il n'y a plus **aucun** import
# de `extraction_previz` dans ce module -- les seules occurrences restantes sont
# de la prose de docstring, et la docstring du module dit d'ailleurs
# correctement l'inverse. Garder une porte ouverte pour un import qui n'existe
# plus affaiblit la garde, et la phrase fausse etait deposee a l'endroit meme ou
# la revue suivante ira lire. C'est un **retrecissement** de liste blanche, la
# ou l'AC 1 n'autorisait qu'un elargissement: il est assume et nomme au Dev
# Agent Record.
ALLOWED_RELATIVE_IMPORTS = {
    "codec_profiles",
    "previz_common",
    "source_confirmation",
}
# `__import__` et `compile` fermes aussi (revue 4.9): un import dynamique
# contournait la liste blanche sans produire de noeud Import. `compile` n'est
# interdit qu'en nom nu: `re.compile` (regex, module en liste blanche) est
# legitime et n'a rien du builtin de compilation de code.
FORBIDDEN_CALL_NAMES = {"open", "print", "input", "exec", "eval", "__import__", "compile"}
FORBIDDEN_ATTR_CALL_NAMES = FORBIDDEN_CALL_NAMES - {"compile"}


def _module_tree() -> ast.Module:
    return ast.parse(MODULE_PATH.read_text(encoding="utf-8"), filename=str(MODULE_PATH))


def test_module_imports_are_whitelisted():
    offenders = []
    for node in ast.walk(_module_tree()):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in ALLOWED_ABSOLUTE_IMPORTS:
                    offenders.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                if (node.module or "") not in ALLOWED_RELATIVE_IMPORTS:
                    offenders.append(f".{node.module}")
            elif (node.module or "") not in ALLOWED_ABSOLUTE_IMPORTS:
                offenders.append(node.module or "")
    assert offenders == []


def test_module_calls_no_io_primitive():
    offenders = []
    for node in ast.walk(_module_tree()):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in FORBIDDEN_CALL_NAMES:
                offenders.append((func.id, node.lineno))
            if isinstance(func, ast.Attribute) and func.attr in FORBIDDEN_ATTR_CALL_NAMES:
                offenders.append((func.attr, node.lineno))
    assert offenders == []


# ---------------------------------------------------------------------------
# AC 2: enveloppe previz-1 reprise telle quelle, kind makepdf
# ---------------------------------------------------------------------------


def test_envelope_is_the_35_envelope_with_kind_makepdf():
    document = build()
    assert document.previz_schema_version == extraction_previz.PREVIZ_SCHEMA_VERSION
    assert document.kind == pdf_previz.PDF_PREVIZ_KIND == "makepdf"
    assert document.state == pdf_previz.PDF_PREVIZ_STATE_PLANNED
    assert document.state == extraction_previz.PREVIZ_STATE_PLANNED
    assert document.generated_at_utc == GENERATED_AT
    # Canonicalisation et prefixe d'empreinte: ceux de 3.5, importes.
    assert document.fingerprints.composition.startswith(
        extraction_previz.FINGERPRINT_PREFIX
    )


def test_warning_vocabulary_has_a_distinct_name_and_the_arbitrated_codes():
    # AC 6: constante au nom distinct de PREVIZ_WARNING_CODES (motif ARB-14).
    assert pdf_previz.PDF_PREVIZ_WARNING_CODES != extraction_previz.PREVIZ_WARNING_CODES
    for code in ("GEOMETRY_DEGRADED", "LOT_INCOMPLETE", "OVER_NOMINAL_BUDGET"):
        assert code in pdf_previz.PDF_PREVIZ_WARNING_CODES


def test_invalid_timestamp_and_state_are_refused():
    with pytest.raises(pdf_previz.PdfPrevizError):
        build(generated_at_utc="hier")
    with pytest.raises(pdf_previz.PdfPrevizError):
        build(generated_at_utc="2026-02-30T25:61:61Z")
    with pytest.raises(pdf_previz.PdfPrevizError):
        build(state="imprime")


# ---------------------------------------------------------------------------
# AC 3: projection verbatim, jamais un calcul
# ---------------------------------------------------------------------------


def test_document_transports_sentinel_values_verbatim():
    # Sentinelles incoherentes (geometrie absurde, budget improbable): elles
    # ressortent telles quelles -- toute "correction" trahirait un recalcul.
    plan = make_plan()
    plan.pages[0].qr.geometry_status = "degraded"
    plan.pages[0].qr.budget.size_bytes = 4242
    plan.pages[0].frames[0].zone_rect_mm = (1.0, 2.0, 3.0, 4.5)
    document = build(plan)
    page = document.pages[0]
    assert page.qr.geometry == "degraded"
    assert page.qr.payload_bytes == 4242
    zone = page.frame_zones[0]
    assert (zone.x_mm, zone.y_mm, zone.w_mm, zone.h_mm) == (1.0, 2.0, 3.0, 4.5)
    assert zone.slot_index == 0
    assert zone.frame_timecode == "00:00:00:00"
    assert zone.frame_path_relative == "frames/rush-001_5/rush-001_5_00-00-00-00.tiff"
    # Marqueurs: coordonnees de CENTRE, nommees comme telles (revue 4.9 --
    # `x_mm` uniforme decalait chaque marqueur d'une demi-taille).
    assert page.aruco_markers[0].marker_id == 0
    assert page.aruco_markers[0].center_x_mm == 30.0
    assert page.aruco_markers[0].center_y_mm == 30.0
    # Patchs: la couleur resolue par la table 4.8 est transportee (revue 4.9:
    # sans elle, la GUI redupliquait la resolution value_id -> RGB).
    assert page.patches[0].value_id == "neutral-020"
    assert page.patches[0].rgb == (51, 51, 51)
    assert page.text_blocks[0].role == "footer_block"
    assert page.text_blocks[0].content == "lot-a_p001\nproj-a"
    # Placement image et etiquettes de slot: la planche complete, pas un
    # sous-ensemble (revue 4.9 -- l'apercu "voici ce que makepdf produira"
    # mentait sans eux).
    assert (zone.image_x_mm, zone.image_y_mm, zone.image_w_mm, zone.image_h_mm) == (
        35.0,
        60.0,
        140.0,
        78.75,
    )
    assert zone.letterbox_policy == "letterbox-centre"
    assert page.slot_labels[0].text == "rush-001 s00 tc 00:00:00:00"
    assert page.slot_labels[0].x_mm == 35.0
    # Nom de fichier PDF prevu, transporte des le regime planned (AC 4).
    assert document.pdf_filename == "proj-a_rush-001_lot-a_planches.pdf"
    # Parametres transportes.
    parameters = document.parameters
    assert parameters.template_id == "tpl-a4-portrait-2f-v1"
    assert parameters.frames_par_page == 2
    assert parameters.dpi == 600
    assert parameters.marge == "0"
    # Cadence en forme canonique unique.
    assert document.subject.fps_target_exact == "5/1"


def test_document_json_matches_the_frozen_canonical_fixture():
    # Fixture canonique figee en dur: tout renommage de champ casse ce test.
    document = build()
    rendered = extraction_previz.canonical_json(pdf_previz.pdf_previz_to_json_dict(document))
    assert rendered == FROZEN_CANONICAL_FIXTURE


def test_serialization_is_deterministic_byte_for_byte():
    first = extraction_previz.canonical_json(pdf_previz.pdf_previz_to_json_dict(build()))
    second = extraction_previz.canonical_json(pdf_previz.pdf_previz_to_json_dict(build()))
    assert first == second
    # Et strictement parseable.
    assert json.loads(first)["kind"] == "makepdf"


def test_absolute_paths_are_refused_everywhere():
    with pytest.raises(pdf_previz.PdfPrevizError):
        build(make_plan(frames_dir="/abs/frames"))
    with pytest.raises(pdf_previz.PdfPrevizError):
        build(
            state=pdf_previz.PDF_PREVIZ_STATE_RENDERED,
            frames_present_count=1,
            output_pdf_path_relative="C:\\planches\\out.pdf",
        )
    # Et le document rendu ne contient aucun chemin absolu (detecteur unique
    # du depot, importe -- jamais reecrit).
    document = build()
    assert _iter_absolute_path_violations(pdf_previz.pdf_previz_to_json_dict(document)) == []


# ---------------------------------------------------------------------------
# AC 5: empreintes de peremption
# ---------------------------------------------------------------------------


def test_composition_fingerprint_tracks_decision_inputs_only():
    baseline = build()
    identical = build()
    assert baseline.fingerprints.composition == identical.fingerprints.composition

    reparameterized = build(make_plan(frames_per_page=4))
    assert reparameterized.fingerprints.composition != baseline.fingerprints.composition

    # Un avertissement de plus ne change pas l'empreinte (entrees de decision
    # seulement, piege 4).
    warned = build(previz_warnings=("GEOMETRY_DEGRADED",))
    assert warned.fingerprints.composition == baseline.fingerprints.composition


def test_composition_fingerprint_fields_are_exported_and_exact():
    # Motif SELECTION_FINGERPRINT_FIELDS de 3.5: la constante est le contrat.
    assert pdf_previz.COMPOSITION_FINGERPRINT_FIELDS == tuple(
        sorted(pdf_previz.COMPOSITION_FINGERPRINT_FIELDS)
    )
    for field in ("template_id", "patch_preset_id", "frames_par_page", "lot_id"):
        assert field in pdf_previz.COMPOSITION_FINGERPRINT_FIELDS


def test_selection_fingerprint_is_transported_verbatim_at_the_35_recipe():
    fingerprint = extraction_previz.fingerprint_of({"selection": "x"})
    document = build(selection_fingerprint=fingerprint)
    assert document.fingerprints.selection == fingerprint
    with pytest.raises(pdf_previz.PdfPrevizError):
        build(selection_fingerprint="md5:abcd")  # recette etrangere refusee


# ---------------------------------------------------------------------------
# AC 6: vocabulaire ferme, LOT_INCOMPLETE confronte (ARB-13)
# ---------------------------------------------------------------------------


def test_unknown_warning_code_is_refused():
    with pytest.raises(pdf_previz.PdfPrevizError):
        build(previz_warnings=("CODE_INCONNU",))


def test_lot_incomplete_is_deduced_from_the_counters():
    rendered = build(
        state=pdf_previz.PDF_PREVIZ_STATE_RENDERED,
        expected_frame_count=4,
        frames_present_count=3,
        output_pdf_path_relative="planches/out.pdf",
    )
    assert "LOT_INCOMPLETE" in rendered.warnings.previz

    complete = build(
        state=pdf_previz.PDF_PREVIZ_STATE_RENDERED,
        expected_frame_count=4,
        frames_present_count=4,
        output_pdf_path_relative="planches/out.pdf",
    )
    assert "LOT_INCOMPLETE" not in complete.warnings.previz

    with pytest.raises(pdf_previz.PdfPrevizError):
        build(
            state=pdf_previz.PDF_PREVIZ_STATE_RENDERED,
            expected_frame_count=4,
            frames_present_count=4242,
            output_pdf_path_relative="planches/out.pdf",
        )


def test_planned_and_rendered_states_gate_their_fields():
    # planned: pas de compteur present, pas de chemin de PDF rendu -- mais le
    # nom de fichier PREVU est transporte depuis le plan (AC 4, revue 4.9).
    planned = build()
    assert planned.subject.frames_present_count is None
    assert planned.output_pdf_path_relative is None
    assert planned.pdf_filename == "proj-a_rush-001_lot-a_planches.pdf"
    with pytest.raises(pdf_previz.PdfPrevizError):
        build(frames_present_count=1)
    with pytest.raises(pdf_previz.PdfPrevizError):
        build(output_pdf_path_relative="planches/out.pdf")
    # rendered: les deux sont obligatoires, fournis par l'appelant.
    with pytest.raises(pdf_previz.PdfPrevizError):
        build(state=pdf_previz.PDF_PREVIZ_STATE_RENDERED)


def test_lot_incomplete_is_never_accepted_from_the_caller():
    # ARB-13 (revue 4.9): fourni par l'appelant, le code pouvait doubler la
    # deduction ou contredire les compteurs du document.
    with pytest.raises(pdf_previz.PdfPrevizError):
        build(previz_warnings=("LOT_INCOMPLETE",))
    with pytest.raises(pdf_previz.PdfPrevizError):
        build(
            state=pdf_previz.PDF_PREVIZ_STATE_RENDERED,
            expected_frame_count=4,
            frames_present_count=3,
            output_pdf_path_relative="planches/out.pdf",
            previz_warnings=("LOT_INCOMPLETE",),
        )


def test_warning_codes_are_deduplicated_refused_and_sorted():
    # Doublon: refus (deux documents identiques doivent partager leur JSON
    # canonique, revue 4.9).
    with pytest.raises(pdf_previz.PdfPrevizError):
        build(previz_warnings=("GEOMETRY_DEGRADED", "GEOMETRY_DEGRADED"))
    # Tri: l'ordre cote appelant n'influence pas la forme canonique.
    first = build(previz_warnings=("OVER_NOMINAL_BUDGET", "GEOMETRY_DEGRADED"))
    second = build(previz_warnings=("GEOMETRY_DEGRADED", "OVER_NOMINAL_BUDGET"))
    assert first.warnings.previz == second.warnings.previz
    assert extraction_previz.canonical_json(
        pdf_previz.pdf_previz_to_json_dict(first)
    ) == extraction_previz.canonical_json(pdf_previz.pdf_previz_to_json_dict(second))


def test_non_iterable_warnings_raise_the_module_error_not_typeerror():
    with pytest.raises(pdf_previz.PdfPrevizError):
        build(previz_warnings=5)
    # None se lit "aucun avertissement" (tolerance d'appel, revue 4.9: la
    # TypeError brute eclatait avant toute validation).
    assert build(previz_warnings=None).warnings.previz == ()


def test_selection_fingerprint_requires_the_full_form():
    # Prefixe seul ou digest non hexadecimal: incomparable, donc refuse
    # (revue 4.9 -- une empreinte vide ne perime jamais correctement).
    for bad in (
        extraction_previz.FINGERPRINT_PREFIX,
        extraction_previz.FINGERPRINT_PREFIX + "ZZZ pas hex",
        extraction_previz.FINGERPRINT_PREFIX + "abcd",
    ):
        with pytest.raises(pdf_previz.PdfPrevizError):
            build(selection_fingerprint=bad)


def test_frame_filename_is_validated_before_path_building():
    # None, vide ou non-chaine produisaient des chemins corrompus mais
    # "valides" (frames/.../None, le dossier lui-meme) -- revue 4.9.
    for bad in (None, "", 5):
        plan = make_plan()
        plan.pages[0].frames[0].frame_filename = bad
        with pytest.raises(pdf_previz.PdfPrevizError):
            build(plan)


def test_non_square_qr_footprint_is_refused():
    # Le schema (size_mm unique) ne peut pas porter un rect non carre: le
    # maquiller en carre cacherait un bug amont (revue 4.9).
    plan = make_plan()
    plan.pages[0].qr.footprint_rect_mm = (10.0, 10.0, 40.0, 20.0)
    with pytest.raises(pdf_previz.PdfPrevizError):
        build(plan)


def test_structurally_broken_plans_raise_the_module_error():
    # Toutes ces malformations levaient des exceptions natives brutes
    # (IndexError, AttributeError, TypeError) hors de la hierarchie promise
    # (revue 4.9).
    short_rect = make_plan()
    short_rect.pages[0].frames[0].zone_rect_mm = (1.0, 2.0)
    no_qr = make_plan()
    no_qr.pages[0].qr = None
    string_lines = make_plan()
    string_lines.pages[0].text.blocks[0].lines = "abc"
    text_in_rect = make_plan()
    text_in_rect.pages[0].frames[0].zone_rect_mm = (1.0, "2.0", 3.0, 4.0)
    for plan in (short_rect, no_qr, string_lines, text_in_rect, make_plan(pages=None)):
        with pytest.raises(pdf_previz.PdfPrevizError):
            build(plan)


# ---------------------------------------------------------------------------
# Fixture canonique figee (voir test_document_json_matches_the_frozen_...)
# ---------------------------------------------------------------------------

FROZEN_CANONICAL_FIXTURE = (
    # Fixture regeneree par la story 5.10: `gamut_map_id` rejoint les
    # parametres de composition (AC 12). C'est le seul test existant qui
    # casse mecaniquement, et la story le nomme comme tel.
    "{\"fingerprints\":{\"composition\":\"sha256-v1:98098c984485c93ec7a8bdb37bd3"
    "64ad47171cf7ec58602296e74ee6fd947883\",\"selection\":\"sha256-v1:5b302ae92"
    "1cf08efa2c61d643300a609f04c7efeb70ea8a122768e8509404768\"},\"generated_a"
    "t_utc\":\"2026-08-06T12:00:00Z\",\"kind\":\"makepdf\",\"output_pdf_path_relati"
    "ve\":null,\"pages\":[{\"aruco_markers\":[{\"center_x_mm\":30.0,\"center_y_mm\":"
    "30.0,\"marker_id\":0,\"size_mm\":30.0}],\"frame_zones\":[{\"frame_path_relati"
    "ve\":\"frames/rush-001_5/rush-001_5_00-00-00-00.tiff\",\"frame_timecode\":\""
    "00:00:00:00\",\"h_mm\":78.75,\"image_h_mm\":78.75,\"image_w_mm\":140.0,\"image"
    "_x_mm\":35.0,\"image_y_mm\":60.0,\"letterbox_policy\":\"letterbox-centre\",\"s"
    "lot_index\":0,\"w_mm\":140.0,\"x_mm\":35.0,\"y_mm\":60.0}],\"page_count\":1,\"pa"
    "ge_index\":0,\"patches\":[{\"rgb\":[51,51,51],\"size_mm\":12.0,\"value_id\":\"ne"
    "utral-020\",\"x_mm\":14.0,\"y_mm\":62.0}],\"qr\":{\"geometry\":\"reliable\",\"payl"
    "oad_bytes\":402,\"size_mm\":37.9,\"symbol_size_mm\":35.0,\"x_mm\":85.05,\"y_mm"
    "\":11.05},\"slot_labels\":[{\"h_mm\":4.0,\"text\":\"rush-001 s00 tc 00:00:00:0"
    "0\",\"w_mm\":140.0,\"x_mm\":35.0,\"y_mm\":139.0}],\"text_blocks\":[{\"content\":\""
    "lot-a_p001\\nproj-a\",\"font_pt\":8.0,\"h_mm\":45.0,\"role\":\"footer_block\",\"w"
    "_mm\":90.0,\"x_mm\":60.0,\"y_mm\":240.0}]}],\"parameters\":{\"dpi\":600,\"format"
    "\":\"A4\",\"frames_par_page\":2,\"gamut_map_id\":\"gamut-map-none-1\",\"marge\":\""
    "0\",\"orientation\":\"portrait\",\"patch_preset_id\":\"patches-12-v1\",\"templat"
    "e_id\":\"tpl-a4-portrait-2f-v1\"},\"pdf_filename\":\"proj-a_rush-001_lot-a_p"
    "lanches.pdf\",\"previz_schema_version\":\"previz-1\",\"state\":\"planned\",\"sub"
    "ject\":{\"expected_frame_count\":1,\"fps_target_exact\":\"5/1\",\"frames_prese"
    "nt_count\":null,\"lot_id\":\"lot-a\",\"project_id\":\"proj-a\",\"rush_id\":\"rush-"
    "001\"},\"warnings\":{\"previz\":[]}}"
)


def test_the_composition_fingerprint_reacts_to_the_gamut_map() -> None:
    """Le defaut que l'AC 12 nomme, et que rien ne verrouillait.

    Deux plans identiques sauf `G` produisent des planches differentes: si
    l'empreinte de composition ne bougeait pas, une previz perimee deviendrait
    indetectable -- exactement ce que la revue de 4.9 avait ferme (« l'apercu ne
    ment plus »). Un mutant retirant le champ de
    `COMPOSITION_FINGERPRINT_FIELDS` survivait a la suite complete.
    """
    assert "gamut_map_id" in pdf_previz.COMPOSITION_FINGERPRINT_FIELDS
    reference = build()
    other = build(plan=make_plan(gamut_map_id="gamut-map-lin-1"))
    assert (
        other.fingerprints.composition != reference.fingerprints.composition
    ), "changer la compression doit perimer l'apercu"
    # ... et le champ voyage jusqu'au document.
    assert pdf_previz.pdf_previz_to_json_dict(other)["parameters"]["gamut_map_id"] == (
        "gamut-map-lin-1"
    )


def test_the_previz_refuses_a_plan_without_a_resolved_gamut_map() -> None:
    # Le typage structurel accepterait un plan augmente sans erreur: la previz
    # continuerait a fonctionner **en ignorant `G`**, ce qui est le piege 8.
    with pytest.raises(pdf_previz.PdfPrevizError):
        build(plan=make_plan(gamut_map_id=""))
