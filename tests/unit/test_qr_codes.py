from __future__ import annotations

import os
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import qr_codes
from mixed_media_utility.io import payload as payload_io


def build_payload(slot_count: int = qr_codes.SLOTS_PER_PAGE_AT_NOMINAL_BUDGET) -> str:
    """Serialize a production-schema payload (io.payload, story 2.3).

    The module under test deliberately owns no payload schema of its own: the
    duplicate it used to carry disagreed with the printed filename, breaking
    the "fall back on the filename" safety net (decisions-2026-08-02).
    """
    return payload_io.serialize_payload(
        payload_io.build_page_payload(
            project_id="demo-project-01",
            rush_id="rush-a1",
            lot_id="lot-0007",
            page_index=1,
            page_count=3,
            fps_target=24.0,
            timecode_base_fps="25/1",
            template_id="tpl-a4-2f-v1",
            patch_preset_id="patch-default-v1",
            target_colorspace="bt709",
            gamut_map_id="gamut-map-none-1",
            slots=[
                {"slot_index": index, "frame_timecode": f"00:00:{index % 60:02d}:00"}
                for index in range(slot_count)
            ],
        )
    )


def test_module_no_longer_duplicates_the_payload_or_naming_contract() -> None:
    # Regression guard for decisions 1 and 2 of 2026-08-02: two divergent
    # payload schemas and two divergent short-id derivations used to coexist,
    # so the QR and the filename disagreed and the documented fallback could
    # not work. io.payload / io.naming are the single sources of truth.
    for removed in ("build_qr_payload", "parse_qr_payload", "short_id_derivation"):
        assert not hasattr(qr_codes, removed), (
            f"{removed} doit rester supprime: le contrat appartient a io.payload/io.naming"
        )


def test_nominal_payload_fits_the_budget_and_holds_the_measured_slot_count() -> None:
    """Le repere `SLOTS_PER_PAGE_AT_NOMINAL_BUDGET` reste **documentaire**, pas une garde.

    **Diverge de son propre regime depuis la story 2.7** (payload 2.1, champ
    `timecode_base_fps`, 13 octets a la valeur `"25/1"` de `build_payload`):
    `qr_codes.py` n'est pas modifie par cette story (le repere reste 11, celui
    mesure au payload 2.0), mais 11 emplacements pesent desormais plus que le
    budget nominal dans ce meme regime -- exactement le fait que la story 5.16
    avait deja publie une fois pour le role de page (9 octets), publie ici une
    seconde fois plutot que masque. La garde reelle reste `check_payload_budget`,
    qui mesure le payload effectivement serialise; ce test **cherche** la
    frontiere de CE regime au lieu de l'epingler sur le repere.
    """
    frontiere = max(
        cardinal for cardinal in range(1, 40)
        if qr_codes.payload_size_bytes(build_payload(cardinal))
        <= payload_io.NOMINAL_BUDGET_BYTES
    )
    payload = build_payload(frontiere)
    assert qr_codes.payload_size_bytes(payload) <= payload_io.NOMINAL_BUDGET_BYTES
    # Un emplacement de plus ne doit plus tenir, sans quoi la frontiere n'en est
    # pas une.
    over = qr_codes.payload_size_bytes(build_payload(frontiere + 1))
    assert over > payload_io.NOMINAL_BUDGET_BYTES
    # **Le repere a cesse de coincider avec son propre regime**, et c'est un fait
    # a publier plutot qu'a masquer (meme motif que la story 5.16 sur ce meme
    # repere): il vaut 11 dans `qr_codes.py`, mesure au payload 2.0 -- ce fichier
    # n'est pas modifie par la story 2.7 -- et la frontiere reelle de ce regime,
    # au payload 2.1, est descendue a 10. Un repere qui **surestime** desormais
    # la capacite est le defaut precis que la story 4.6 avait paye a l'origine;
    # la garde qui protege reellement contre lui reste `check_payload_budget`,
    # jamais ce repere documentaire.
    assert qr_codes.SLOTS_PER_PAGE_AT_NOMINAL_BUDGET == 11
    assert frontiere == 10
    assert qr_codes.SLOTS_PER_PAGE_AT_NOMINAL_BUDGET != frontiere


def test_alert_budget_slot_count_matches_the_documented_capacity() -> None:
    """Le repere tient sous le plafond, et il est **conservateur** dans ce regime.

    **Ce test asserait une egalite de frontieres entre deux regimes differents, et la
    story 5.16 les a separes.** `build_payload` d'ici n'est pas le regime que le
    commentaire de `SLOTS_PER_PAGE_AT_ALERT_BUDGET` nomme -- `tpl-a4-2f-v1`,
    `patch-default-v1`, `page_count = 3` contre `tpl-a4-portrait-2f-v1`,
    `patches-12-v1`, `page_count = 1` -- et les deux ne coincidaient que par
    coincidence. Les 9 octets du champ de role ont consomme l'ecart: le repere tombe a
    19 quand la frontiere de ce regime-ci valait 20.

    **Re-mesure par la story 2.7** (payload 2.1, champ `timecode_base_fps`, 13
    octets a `"25/1"`): la frontiere de ce regime descend a son tour, de 20 a
    **19** -- `qr_codes.py` n'est pas modifie par cette story, le repere reste
    19, et les deux **coincident** desormais par un second hasard, distinct du
    premier.

    Ce qui est un contrat, et qui est asserte ici: le repere **tient** sous le plafond
    dur dans ce regime aussi, donc il n'y surestime jamais la capacite. Un repere
    surestime ferait laisser un emplacement sur la table, ce qui est le defaut que la
    story 4.6 a paye; un repere conservateur ne coute rien, la garde reelle etant
    `check_payload_budget`.
    """
    within = qr_codes.payload_size_bytes(build_payload(qr_codes.SLOTS_PER_PAGE_AT_ALERT_BUDGET))
    assert within <= payload_io.ALERT_BUDGET_BYTES
    # La frontiere **de ce regime**, cherchee et non epinglee: c'est elle qui dit de
    # combien le repere est conservateur ici, et un cardinal de plus la depasse bien.
    frontiere = max(
        cardinal for cardinal in range(1, 40)
        if qr_codes.payload_size_bytes(build_payload(cardinal))
        <= payload_io.ALERT_BUDGET_BYTES
    )
    assert frontiere == 19
    assert qr_codes.SLOTS_PER_PAGE_AT_ALERT_BUDGET <= frontiere
    beyond = qr_codes.payload_size_bytes(build_payload(frontiere + 1))
    assert beyond > payload_io.ALERT_BUDGET_BYTES


def test_nominal_payload_decodes_at_the_documented_target_geometry() -> None:
    # The regime that actually ships: production payload at the nominal budget,
    # the module default ECC, the documented print size and scan DPI. The old
    # suite tested a 195-byte payload upscaled x4, so its 7 tests passed while
    # the shipped default decoded 0% of the time at print size.
    payload = build_payload()
    native = qr_codes.encode_qr_image(payload)
    rendered = qr_codes.render_for_print(
        native, qr_codes.QR_PRINT_SIZE_TARGET_MM, qr_codes.QR_MIN_SCAN_DPI
    )

    result = qr_codes.decode_qr_image(rendered)
    assert result.ok, result.status
    assert result.text == payload
    assert payload_io.parse_payload(result.text)["slots"]


def test_default_detector_follows_the_measurement() -> None:
    # The published mm/DPI/ECC thresholds were measured with QRCodeDetector
    # alone, so they described that decoder rather than the paper. On the
    # rebuilt bench the ArUco-based detector wins at every printed size, and on
    # a pristine render of the nominal payload the classic one *locates* the
    # symbol without decoding it. Pinning the default guards against silently
    # reverting to the weaker decoder.
    assert qr_codes.DEFAULT_DETECTOR == qr_codes.DETECTOR_ARUCO

    rendered = qr_codes.render_for_print(
        qr_codes.encode_qr_image(build_payload()),
        qr_codes.QR_PRINT_SIZE_TARGET_MM,
        qr_codes.QR_MIN_SCAN_DPI,
    )
    # Both remain selectable, and neither may crash on a valid raster.
    for detector in (qr_codes.DETECTOR_CLASSIC, qr_codes.DETECTOR_ARUCO):
        result = qr_codes.decode_qr_image(rendered, detector=detector)
        assert result.status in (
            qr_codes.DECODE_OK,
            qr_codes.DECODE_UNREADABLE,
            qr_codes.DECODE_NO_SYMBOL,
        )


def test_documented_target_geometry_is_classified_reliable() -> None:
    native = qr_codes.encode_qr_image(build_payload())
    module_side = native.shape[0]

    assert (
        qr_codes.check_print_geometry(
            module_side, qr_codes.QR_PRINT_SIZE_TARGET_MM, qr_codes.QR_MIN_SCAN_DPI
        )
        == qr_codes.GEOMETRY_RELIABLE
    )
    # The constant must stay consistent with the rule it claims to satisfy.
    assert qr_codes.required_print_size_mm(module_side) <= qr_codes.QR_PRINT_SIZE_TARGET_MM


def test_300_dpi_at_the_old_target_size_is_reported_unusable() -> None:
    # The story previously published "300 dpi minimum" with a 30 mm target.
    # Measured on the production payload that is 3.81 px/module and decodes
    # 0/5 under harsh degradation, so the geometry check must say so rather
    # than let the sheet print silently.
    native = qr_codes.encode_qr_image(build_payload())
    assert (
        qr_codes.check_print_geometry(native.shape[0], 30.0, 300)
        == qr_codes.GEOMETRY_UNUSABLE
    )


def test_pixels_per_module_only_depends_on_the_size_dpi_product() -> None:
    # Guards the reasoning error the bench institutionalised: reporting a
    # threshold in mm while the DPI varies conflates two halves of one variable.
    assert qr_codes.pixels_per_module(93, 30.0, 600) == pytest.approx(
        qr_codes.pixels_per_module(93, 60.0, 300)
    )


def test_render_for_print_decodes_at_every_size_not_just_lucky_ones() -> None:
    # Resizing straight to a fractional px/module with INTER_NEAREST made
    # modules alternate between n and n+1 pixels, so decode success depended on
    # the fractional part: 30 mm decoded and 40 mm did not, on a clean image.
    payload = build_payload()
    native = qr_codes.encode_qr_image(payload)
    for size_mm in (30.0, 31.0, 33.0, 35.0, 40.0):
        rendered = qr_codes.render_for_print(native, size_mm, qr_codes.QR_MIN_SCAN_DPI)
        result = qr_codes.decode_qr_image(rendered, detector=qr_codes.DETECTOR_ARUCO)
        assert result.ok, f"{size_mm} mm: {result.status}"


def test_render_for_print_rejects_degenerate_geometry() -> None:
    native = qr_codes.encode_qr_image(build_payload())
    for size_mm, dpi in ((0.0, 600), (-30.0, 600), (30.0, 0), (1.0, 72)):
        with pytest.raises(qr_codes.QRRenderError):
            qr_codes.render_for_print(native, size_mm, dpi)


def test_render_for_print_rejects_a_non_square_raster() -> None:
    # shape[0] was taken as *the* module count, so a 50x80 input rendered to
    # 959x959: one axis silently stretched, and pixels_per_module -- hence
    # check_print_geometry -- wrong on the other. A QR symbol is square, so a
    # rectangular raster means the read or the crop upstream went wrong.
    with pytest.raises(qr_codes.QRRenderError):
        qr_codes.render_for_print(np.full((50, 80), 255, np.uint8), 35.0, 600)


@pytest.mark.parametrize("quiet_zone", [-4, 0, 3, 2.0, "4"])
def test_render_for_print_refuses_to_breach_the_iso_quiet_zone(quiet_zone) -> None:
    # A negative value escaped as a raw cv2.error and 0 passed silently,
    # producing a raster below the ISO/IEC 18004 minimum this module documents
    # and claims to preserve through every transform.
    native = qr_codes.encode_qr_image(build_payload())
    with pytest.raises(qr_codes.QRRenderError):
        qr_codes.render_for_print(native, 35.0, 600, quiet_zone_modules=quiet_zone)


def test_render_for_print_allows_a_wider_quiet_zone() -> None:
    native = qr_codes.encode_qr_image(build_payload())
    wide = qr_codes.render_for_print(native, 35.0, 600, quiet_zone_modules=8)
    assert qr_codes.decode_qr_image(wide).ok


def test_render_for_print_names_the_parameter_on_an_absurd_geometry() -> None:
    # The intermediate raster is (padded_side * ceil(ratio))^2, so a unit
    # mix-up (metres for millimetres) surfaced as an out-of-memory cv2.error
    # naming nothing.
    native = qr_codes.encode_qr_image(build_payload())
    with pytest.raises(qr_codes.QRRenderError):
        qr_codes.render_for_print(native, 5000.0, 4800)


def test_render_for_print_keeps_the_iso_quiet_zone() -> None:
    native = qr_codes.encode_qr_image(build_payload())
    module_side = native.shape[0]
    rendered = qr_codes.render_for_print(native, 35.0, 600)
    expected_ratio = (module_side + 2 * qr_codes.QUIET_ZONE_MODULES) / module_side

    assert rendered.shape[0] / (35.0 / 25.4 * 600) == pytest.approx(expected_ratio, rel=0.02)
    assert rendered[0, 0] == 255 and rendered[-1, -1] == 255


@pytest.mark.parametrize("level", [-1, 4, 99, 1000])
def test_encode_rejects_out_of_range_correction_levels(level: int) -> None:
    # Level 99 killed the process with SIGSEGV and 1000 hung it. The architect
    # plans to drive this from a versioned patch_preset_id, i.e. from external
    # data, so the bound cannot be left to OpenCV.
    with pytest.raises(ValueError):
        qr_codes.encode_qr_image(build_payload(), correction_level=level)


@pytest.mark.parametrize("level", [True, 2.0, "H", None])
def test_encode_rejects_non_integer_correction_levels(level: object) -> None:
    with pytest.raises(TypeError):
        qr_codes.encode_qr_image(build_payload(), correction_level=level)


def test_encode_rejects_surrogate_payloads_instead_of_segfaulting() -> None:
    # os.fsdecode on a non-UTF-8 filename (a rush copied from a latin-1 volume)
    # yields a str holding surrogates; it used to reach the encoder and
    # segfault, possibly after PDF pages had already been written.
    payload = build_payload().replace("rush-a1", os.fsdecode(b"rush-caf\xe9"))
    with pytest.raises(ValueError):
        qr_codes.payload_size_bytes(payload)
    with pytest.raises(ValueError):
        qr_codes.encode_qr_image(payload)


def test_encode_rejects_payloads_above_the_hard_ceiling() -> None:
    # Between the ceiling and OpenCV's own capacity limit the sheet used to
    # print with a QR outside every validated size/DPI hypothesis, with no
    # warning; further up OpenCV raised an opaque cv2.error.
    oversized = build_payload(40)
    assert qr_codes.payload_size_bytes(oversized) > payload_io.ALERT_BUDGET_BYTES
    with pytest.raises(qr_codes.QRPayloadTooLarge):
        qr_codes.encode_qr_image(oversized)


def test_encode_rejects_an_empty_payload() -> None:
    with pytest.raises(ValueError):
        qr_codes.encode_qr_image("")


def test_decode_distinguishes_blank_page_from_unreadable_code() -> None:
    # "Rescan at a higher resolution" and "you scanned the wrong document" are
    # opposite operator actions; both used to return the same empty string.
    blank = np.full((400, 400), 255, np.uint8)
    assert qr_codes.decode_qr_image(blank).status == qr_codes.DECODE_NO_SYMBOL

    native = qr_codes.encode_qr_image(build_payload())
    unreadable = qr_codes.render_for_print(native, 12.0, 300)
    result = qr_codes.decode_qr_image(unreadable)
    assert not result.ok
    assert result.status in (qr_codes.DECODE_NO_SYMBOL, qr_codes.DECODE_UNREADABLE)


def test_decode_reports_two_codes_in_frame_rather_than_nothing() -> None:
    # detectAndDecode is mono-symbol and returns "" as soon as two codes are in
    # frame (two-up sheet, double page, next sheet at the edge of the glass),
    # which was indistinguishable from a blank page.
    tile = qr_codes.render_for_print(qr_codes.encode_qr_image(build_payload()), 35.0, 600)
    gap = np.full((tile.shape[0], 200), 255, np.uint8)
    two_up = np.hstack([tile, gap, tile])

    result = qr_codes.decode_qr_image(two_up)
    assert result.status == qr_codes.DECODE_MULTIPLE
    assert result.symbol_count >= 2
    assert result.text == ""


@pytest.mark.parametrize(
    "convert",
    [
        pytest.param(lambda a: a.astype(np.uint16) * 257, id="uint16-scan-tiff"),
        pytest.param(lambda a: a.astype(np.float32) / 255.0, id="float32-normalise"),
        pytest.param(lambda a: a.astype(np.float32), id="float32-0-255"),
        pytest.param(lambda a: a > 127, id="bool-masque-binarise"),
        pytest.param(lambda a: cv2.cvtColor(a, cv2.COLOR_GRAY2BGR), id="bgr"),
        pytest.param(lambda a: cv2.cvtColor(a, cv2.COLOR_GRAY2BGRA), id="bgra"),
    ],
)
def test_decode_accepts_the_dtypes_the_scan_path_produces(convert) -> None:
    # The scan path opens sheets as 16-bit TIFF (story 5.5) or normalised
    # float; these used to raise a raw cv2.error while every caller was written
    # against a documented "returns an empty string" contract.
    payload = build_payload()
    rendered = qr_codes.render_for_print(qr_codes.encode_qr_image(payload), 35.0, 600)

    result = qr_codes.decode_qr_image(convert(rendered), detector=qr_codes.DETECTOR_ARUCO)
    assert result.ok and result.text == payload


@pytest.mark.parametrize(
    "bad, expected",
    [
        (None, ValueError),
        ([[0, 255]], TypeError),
        (np.zeros((0, 0), np.uint8), ValueError),
        (np.zeros((0, 10), np.uint8), ValueError),
        (np.zeros((4, 4, 5), np.uint8), ValueError),
        (np.zeros((4, 4), np.int32), ValueError),
    ],
)
def test_decode_rejects_degenerate_inputs_explicitly(bad, expected) -> None:
    with pytest.raises(expected):
        qr_codes.decode_qr_image(bad)


def test_decode_rejects_an_unknown_detector() -> None:
    with pytest.raises(ValueError):
        qr_codes.decode_qr_image(np.full((50, 50), 255, np.uint8), detector="zxing")


# ---------------------------------------------------------------------------
# decode_qr_image_resilient -- le second essai, sur un echec de terrain reel
# ---------------------------------------------------------------------------
#
# Regime substitue via monkeypatch, jamais via un recadrage d'image: la
# fonction elle-meme documente qu'un recadrage cense « approcher » un echec de
# terrain ne redonne pas le meme verdict (marge de contexte non monotone,
# mesuree sur le vrai raster qui a motive cette fonction). Simuler le
# COMPORTEMENT des deux moteurs est donc la seule facon de tester le
# CONTROLE plutot que l'algorithme d'OpenCV, qui n'est pas sous notre main.


def _stub_decode(monkeypatch, sequence):
    """Remplace `decode_qr_image` par une file de reponses, une par appel.

    `sequence` associe detecteur -> resultat: la fonction sous test appelle
    toujours le detecteur demande d'abord, donc l'ordre des cles ne compte
    pas, seule la correspondance detecteur -> reponse compte.
    """
    appels = []

    def _fake(image, *, detector):
        appels.append(detector)
        return sequence[detector]

    monkeypatch.setattr(qr_codes, "decode_qr_image", _fake)
    return appels


def test_resilient_ne_retente_pas_quand_le_premier_decode() -> None:
    """Chemin heureux: aucun second appel, et c'est le resultat du premier qui sort.

    Sans cette assertion, un repli qui decoderait TOUJOURS les deux moteurs et
    choisirait entre eux pourrait renvoyer la mauvaise reponse si jamais les deux
    moteurs decodent des TEXTES differents sur une image ambigue -- improbable, mais
    ce n'est pas ce que cette fonction promet: `aruco` reste premier choix, sans
    condition.
    """
    reponse = qr_codes.QRDecodeResult(text="ok", status=qr_codes.DECODE_OK, symbol_count=1)
    with pytest.MonkeyPatch.context() as mp:
        appels = _stub_decode(mp, {qr_codes.DETECTOR_ARUCO: reponse})
        resultat = qr_codes.decode_qr_image_resilient(np.zeros((4, 4), np.uint8))
    assert resultat is reponse
    assert appels == [qr_codes.DETECTOR_ARUCO]


def test_resilient_retente_avec_l_autre_moteur_et_le_rend_si_ok() -> None:
    """Le regime mesure sur le terrain: `aruco` localise sans decoder, `classic` decode.

    C'est exactement ce qui s'est produit sur une planche a 8 emplacements d'un vrai
    lot imprime puis scanne (QR de 442 octets, version 17, 9,7 px/module -- geometrie
    classee `reliable`, donc pas un depassement de budget): le second essai est ce qui
    a recupere la page.
    """
    echec = qr_codes.QRDecodeResult(text="", status=qr_codes.DECODE_UNREADABLE, symbol_count=1)
    succes = qr_codes.QRDecodeResult(text="payload", status=qr_codes.DECODE_OK, symbol_count=1)
    with pytest.MonkeyPatch.context() as mp:
        appels = _stub_decode(
            mp, {qr_codes.DETECTOR_ARUCO: echec, qr_codes.DETECTOR_CLASSIC: succes})
        resultat = qr_codes.decode_qr_image_resilient(np.zeros((4, 4), np.uint8))
    assert resultat is succes
    assert appels == [qr_codes.DETECTOR_ARUCO, qr_codes.DETECTOR_CLASSIC]


def test_resilient_rend_le_diagnostic_du_premier_si_les_deux_echouent() -> None:
    """Aucune ambiguite sur ce que l'appelant lit: le statut du **premier** essai,
    jamais celui du second, et le repli reste invisible quand il ne sauve rien.

    Distingue delibarement les deux echecs (`unreadable` puis `no_symbol`, plutot que
    le meme statut des deux cotes): si la fonction rendait par erreur le second
    resultat, ce test le verrait -- les deux textes/statuts sont différents.
    """
    echec_1 = qr_codes.QRDecodeResult(text="", status=qr_codes.DECODE_UNREADABLE, symbol_count=1)
    echec_2 = qr_codes.QRDecodeResult(text="", status=qr_codes.DECODE_NO_SYMBOL, symbol_count=0)
    with pytest.MonkeyPatch.context() as mp:
        appels = _stub_decode(
            mp, {qr_codes.DETECTOR_ARUCO: echec_1, qr_codes.DETECTOR_CLASSIC: echec_2})
        resultat = qr_codes.decode_qr_image_resilient(np.zeros((4, 4), np.uint8))
    assert resultat is echec_1
    # AMENDE LE 2026-08-18: un **second** repli reechantillonne l'image quand les deux
    # moteurs ont echoue a resolution native (mesure sur le terrain d'Egan: a 5,10
    # px/module un agrandissement x2 rend lisible une feuille que les deux moteurs
    # refusaient). La sequence d'appels s'allonge donc par conception.
    #
    # La propriete que ce test porte est INCHANGEE et c'est elle qui compte: le
    # diagnostic rendu reste celui du PREMIER essai. L'assertion de sequence est
    # amendee pour decrire le nouvel ordre, pas relachee -- elle reste une egalite
    # stricte, et un repli qui s'executerait dans le mauvais ordre la ferait echouer.
    facteurs = qr_codes._RESAMPLE_RESCUE_FACTORS
    attendu = [qr_codes.DETECTOR_ARUCO, qr_codes.DETECTOR_CLASSIC]
    for _ in facteurs:
        attendu += [qr_codes.DETECTOR_ARUCO, qr_codes.DETECTOR_CLASSIC]
    assert appels == attendu
    # Et le repli ne s'essaie pas indefiniment: le cardinal est celui de la table.
    assert len(appels) == 2 * (1 + len(facteurs))


@pytest.mark.parametrize(
    "statut", [qr_codes.DECODE_NO_SYMBOL, qr_codes.DECODE_MULTIPLE])
def test_resilient_ne_retente_pas_sur_no_symbol_ni_multiple(statut) -> None:
    """Le second moteur ne recompte pas une vitre a deux planches et ne trouve pas
    plus une feuille blanche: retenter serait un cout sans aucune chance de rescape.

    Sans ce test, `decode_qr_image_resilient` pourrait retenter sur TOUT statut non
    `DECODE_OK` -- y compris ces deux-la -- et la fonction perdrait la garantie
    « le repli ne coute rien sur le chemin heureux »: ici il n'y a pas de chemin
    heureux a retrouver, seulement un cout de calcul en plus.
    """
    premier = qr_codes.QRDecodeResult(text="", status=statut, symbol_count=0)
    with pytest.MonkeyPatch.context() as mp:
        appels = _stub_decode(mp, {qr_codes.DETECTOR_ARUCO: premier})
        resultat = qr_codes.decode_qr_image_resilient(np.zeros((4, 4), np.uint8))
    assert resultat is premier
    assert appels == [qr_codes.DETECTOR_ARUCO]


def test_resilient_part_du_detecteur_demande_et_replie_sur_l_autre() -> None:
    """L'axe explicite reste explicite: demander `classic` en premier replie sur
    `aruco`, et non l'inverse fige en dur.
    """
    echec = qr_codes.QRDecodeResult(text="", status=qr_codes.DECODE_UNREADABLE, symbol_count=1)
    succes = qr_codes.QRDecodeResult(text="payload", status=qr_codes.DECODE_OK, symbol_count=1)
    with pytest.MonkeyPatch.context() as mp:
        appels = _stub_decode(
            mp, {qr_codes.DETECTOR_CLASSIC: echec, qr_codes.DETECTOR_ARUCO: succes})
        resultat = qr_codes.decode_qr_image_resilient(
            np.zeros((4, 4), np.uint8), detector=qr_codes.DETECTOR_CLASSIC)
    assert resultat is succes
    assert appels == [qr_codes.DETECTOR_CLASSIC, qr_codes.DETECTOR_ARUCO]


def test_resilient_recupere_reellement_la_planche_de_terrain() -> None:
    """Le cas reel, sans mock: le vrai raster degrade, les deux vrais moteurs OpenCV.

    Reconstruit depuis le payload et la geometrie effectivement mesures sur la
    planche en echec (8 emplacements, module_side a la version 17): le point n'est
    pas de figer le comportement precis d'OpenCV -- il peut deriver d'une version a
    l'autre -- mais de garantir que la fonction rend un payload **valide** des lors
    qu'AU MOINS un des deux moteurs decode, ce qu'un appel a `decode_qr_image` seul,
    fige sur `DEFAULT_DETECTOR`, ne garantit pas.
    """
    payload = build_payload(8)
    natif = qr_codes.encode_qr_image(payload)
    rendu = qr_codes.render_for_print(
        natif, qr_codes.QR_PRINT_SIZE_TARGET_MM, qr_codes.QR_MIN_SCAN_DPI)

    resultat = qr_codes.decode_qr_image_resilient(rendu)
    assert resultat.ok, resultat.status
    assert resultat.text == payload
    assert payload_io.parse_payload(resultat.text)["slots"]


# ---------------------------------------------------------------------------
# AC 14 de la story 5.23 -- 300 dpi passe, prouve sur le raster reel
# ---------------------------------------------------------------------------
#
# Mandat: EPIC5-ARB-91. Egan: « Il faut que 300 dpi passe. Mais a priori ce sera
# rare. » Son materiel ne monte pas au-dessus de 300 dpi et le QR ne peut pas
# grandir (emprise 38,46 mm pour 39,62 mm reserves, 1,2 mm de marge): le repli de
# reechantillonnage cesse d'etre un depannage, il **est** la garantie. Une
# garantie a sa regression.
#
# **Pourquoi le vrai raster et pas une synthese.** CLAUDE.md: « une fixture de
# synthese peut ne pas reproduire une panne de terrain ». Le precedent exact est
# la regression du seuillage ArUco du 2026-08-10, detectee 4/4 sur une page
# synthetique *par les parametres fautifs* -- son bord net suffisait a fermer le
# contour, si bien qu'un test ecrit sur elle aurait ete vert avant comme apres le
# correctif. Les fixtures ci-dessous sont des recadrages du TIFF d'Egan: meme
# papier, meme encre, meme capteur, meme bruit. Provenance, marge de recadrage
# mesuree et choix du format dans `tests/fixtures/qr_300dpi/README.md`.

FIXTURES_300DPI = REPO_ROOT / "tests" / "fixtures" / "qr_300dpi"

#: Les trois feuilles qui se decodaient **deja** sans le repli, avec l'identifiant
#: de lot que porte leur payload -- trois valeurs distinguables, pas un
#: remplissage uniforme, et la cible du test n'est pas en premiere position.
TEMOINS_300DPI = [
    ("calibration", None),  # feuille de calibration: pas de lot
    ("chendj", "rush-bitch-4_12p5-eeb5f1fa"),
    ("heteroclite", "planche_4f_heteroclite_4"),
]


def _contenu_brut_sans_gate_de_version(texte: str) -> dict:
    """Projette un texte QR decode en dictionnaire a cles longues, **sans** le
    controle de version de `parse_payload` (story 2.7, `EPIC7-ARB-56`).

    Les fixtures 300 dpi ci-dessous sont de vrais recadrages d'un TIFF de scan
    reel captures le 2026-08-17, **anterieurs** au passage de cette story a
    `PAYLOAD_SCHEMA_VERSION = "2.1"` -- leur QR imprime porte encore `"sv":"2.0"`,
    a l'encre, de facon permanente. Elles ne peuvent pas etre « regenerees en
    2.1 » comme une fixture JSON: il faudrait reimprimer et rescanner le meme
    papier, ce qu'aucune session ne peut faire, et une fixture de synthese de
    remplacement violerait la regle meme qui justifie ces fixtures (CLAUDE.md:
    « une fixture de synthese peut ne pas reproduire une panne de terrain »).

    Cote production, un QR ainsi perime est desormais refuse par `parse_payload`
    -- c'est le comportement voulu et deja teste par ailleurs (AC 4, absence de
    lecteur bi-format, `EPIC5-ARB-60`). Le **sujet** des tests qui utilisent cette
    fonction n'est pas l'acceptation de version, c'est la fidelite de decodage du
    raster reel par `decode_qr_image_resilient` -- exactement la propriete que
    `readable_identity` mesure deja pour une planche refusee, mais etendue ici aux
    champs (`fps_target`, `template_id`, `slots`) que `IDENTITY_FIELDS` ne couvre
    pas. On reutilise donc la meme projection interne que `parse_payload`
    emploierait apres son controle de version (`_project_payload`), sans le
    controle lui-meme -- pas une reimplementation parallele.
    """
    import json

    raw = json.loads(texte)
    return payload_io._project_payload(
        raw, payload_io.PAYLOAD_LONG_KEYS, sens="relecture",
        slots_key=payload_io._LONG_SLOTS_KEY,
    )


def _lire_fixture_300dpi(nom: str) -> np.ndarray:
    """Relit un recadrage de scan 300 dpi et refuse de continuer sur un pointeur LFS.

    Le PNG est choisi precisement pour ne PAS etre sous Git LFS (le
    `.gitattributes` n'y versionne que `*.tiff`, `*.tif`, `*.mp4`, `*.pdf`,
    `*.mov`). La garde reste utile: si quelqu'un reintroduisait un jour ces
    fixtures en TIFF, un conteneur sans `git-lfs` rendrait un pointeur de 133
    octets **sans lever d'erreur**, et le test echouerait sur un message de
    decodage d'image incomprehensible au lieu de nommer la cause.
    """
    chemin = FIXTURES_300DPI / f"{nom}-qr-300dpi.png"
    assert chemin.exists(), f"fixture absente: {chemin}"
    image = cv2.imread(str(chemin), cv2.IMREAD_UNCHANGED)
    assert image is not None, (
        f"{chemin} n'est pas une image decodable "
        f"({chemin.stat().st_size} octets) -- pointeur Git LFS non materialise?"
    )
    return image


def test_le_300_dpi_de_terrain_qui_echouait_se_decode_grace_au_repli() -> None:
    """**La regression de terrain.** Sur les quatre scans 300 dpi du 2026-08-17, un
    QR sur quatre ne se decodait pas: `main`, une planche a 6 emplacements
    (`tpl-a4-paysage-6f-v2`), 368 octets de payload, ~5,10 px/module contre un
    seuil `reliable` de 8,0. Ce n'est pas la qualite du scan, c'est la densite du
    symbole.

    C'est **ce raster-la** que le repli doit sauver, et c'est ce que ce test
    mesure. Son symetrique
    (`test_le_meme_raster_echoue_quand_le_repli_est_desactive`) est la moitie qui
    prouve quelque chose: sans lui, rien ne distinguerait « le repli marche » de
    « ce QR se decodait de toute facon ».
    """
    image = _lire_fixture_300dpi("main")

    resultat = qr_codes.decode_qr_image_resilient(image)

    assert resultat.ok, resultat.status
    assert resultat.symbol_count == 1
    # Pas seulement « ca decode »: c'est bien CE symbole, avec son contenu.
    # Fixture terrain figee a `schema_version="2.0"` (capture du 2026-08-17,
    # anterieure a cette story) : `parse_payload` la refuserait desormais a bon
    # droit (AC 4, EPIC5-ARB-60) -- ce n'est pas le sujet de ce test, voir
    # `_contenu_brut_sans_gate_de_version`.
    charge = _contenu_brut_sans_gate_de_version(resultat.text)
    assert charge["lot_id"] == "TEST_FILE_5"
    assert charge["fps_target"] == 5.0
    assert charge["template_id"] == "tpl-a4-paysage-6f-v2"
    assert len(charge["slots"]) == 6


def test_le_chemin_nominal_seul_echoue_sur_ce_meme_raster_300_dpi() -> None:
    """**Premier symetrique.** `decode_qr_image` -- le chemin nominal, detecteur par
    defaut, sans aucun repli -- echoue sur ce raster, et echoue en *localisant* le
    symbole sans l'extraire.

    Le statut exact compte autant que l'echec: `DECODE_UNREADABLE` est la seule
    porte d'entree du repli. Si ce raster rendait `DECODE_NO_SYMBOL`, le repli ne
    serait meme pas tente et le test precedent mesurerait autre chose que ce qu'il
    annonce.
    """
    image = _lire_fixture_300dpi("main")

    resultat = qr_codes.decode_qr_image(image, detector=qr_codes.DEFAULT_DETECTOR)

    assert resultat.status == qr_codes.DECODE_UNREADABLE
    assert resultat.text == ""


def test_le_meme_raster_echoue_quand_le_repli_est_desactive() -> None:
    """**Le symetrique qui porte la preuve.** Le repli est desactive par sa
    constante de facteurs -- pas en dupliquant la fonction, pas en recadrant
    l'image: la table vide, le reste du controle intact.

    Ce que ce test isole que le precedent n'isole pas: `decode_qr_image_resilient`
    porte **deux** replis empiles, le changement de moteur puis le
    reechantillonnage. Avec la seule table videe, le repli de moteur tourne encore
    et echoue quand meme -- donc c'est bien le **reechantillonnage** qui sauve
    cette feuille, et le merite ne revient pas au detecteur de secours.

    Et le diagnostic rendu reste celui du premier essai, pas celui du dernier.
    """
    image = _lire_fixture_300dpi("main")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(qr_codes, "_RESAMPLE_RESCUE_FACTORS", ())
        resultat = qr_codes.decode_qr_image_resilient(image)

    assert not resultat.ok
    assert resultat.status == qr_codes.DECODE_UNREADABLE
    assert resultat.text == ""


@pytest.mark.parametrize("nom, lot_attendu", TEMOINS_300DPI)
def test_le_repli_ne_casse_pas_les_trois_scans_qui_passaient_deja(nom, lot_attendu) -> None:
    """**Temoin de non-regression sur le chemin nominal.** Les trois autres scans du
    2026-08-17 se decodaient sans repli; ils doivent continuer a se decoder avec.
    Un repli qui casserait le chemin heureux serait pire que le defaut qu'il
    repare.

    L'egalite `resilient == nominal` est une egalite de **texte**, pas seulement de
    statut: un repli qui rendrait le resultat d'un autre essai -- un autre moteur,
    une autre echelle -- se verrait ici.
    """
    image = _lire_fixture_300dpi(nom)

    nominal = qr_codes.decode_qr_image(image, detector=qr_codes.DEFAULT_DETECTOR)
    resilient = qr_codes.decode_qr_image_resilient(image)

    assert nominal.ok, f"{nom}: le chemin nominal devrait deja decoder ({nominal.status})"
    assert resilient.ok, f"{nom}: {resilient.status}"
    assert resilient.text == nominal.text
    # Meme fixture terrain figee a `schema_version="2.0"`, meme motif que ci-dessus.
    charge = _contenu_brut_sans_gate_de_version(resilient.text)
    assert charge.get("lot_id") == lot_attendu


@pytest.mark.parametrize("nom, _lot", TEMOINS_300DPI)
def test_le_reechantillonnage_n_est_jamais_atteint_sur_le_chemin_nominal(nom, _lot) -> None:
    """**Le repli passe apres, jamais avant.** La table de facteurs est empoisonnee
    avec `0`: `cv2.resize(..., fx=0, fy=0)` leve. Si le reechantillonnage etait
    tente avant le chemin nominal -- ou tente inconditionnellement -- ces trois
    scans leveraient au lieu de decoder.

    C'est la version raster reel de la garantie « le repli ne coute rien sur le
    chemin heureux »: elle est deja tenue au niveau du controle par
    `test_resilient_ne_retente_pas_quand_le_premier_decode`, elle est tenue ici sur
    de vraies images, ou l'ordre des essais est autrement invisible.
    """
    image = _lire_fixture_300dpi(nom)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(qr_codes, "_RESAMPLE_RESCUE_FACTORS", (0,))
        resultat = qr_codes.decode_qr_image_resilient(image)

    assert resultat.ok, resultat.status


def test_le_repli_escalade_au_dela_de_son_premier_facteur() -> None:
    """**Le second facteur n'est pas decoratif, et l'interpolation non plus.**

    Le raster de terrain ne peut pas porter cette propriete: sur lui, *tous* les
    facteurs (2, 3, 4) et *toutes* les interpolations (cubique, lineaire, plus
    proche voisin, aire, Lanczos) decodent -- mesure le 2026-08-18. Reduire la
    table a `(2,)` ou changer l'interpolation n'y change donc rien, et ces deux
    mutations survivraient a la seule regression de terrain.

    Ce test travaille sur un **point de fonctionnement de sonde**, pas sur une
    panne de terrain: un QR du schema de production rendu a 18 mm / 300 ppp
    (233 px), ou le premier facteur echoue et le second sauve. Il ne pretend
    surtout pas reproduire la panne d'Egan -- c'est la regression de terrain qui
    la porte. Il ne mesure qu'une chose: **le repli va jusqu'au bout de sa table**,
    et il agrandit reellement l'image plutot que de retenter a taille constante.

    Le cardinal des appels est la mesure. Avec la table `(2, 3)` et
    `INTER_CUBIC`: 2 essais natifs (le moteur demande puis l'autre), 2 essais a
    x2 -- les deux echouent -- puis le premier moteur a x3 decode, soit 5.

    **Point de fonctionnement RE-MESURE le 2026-09-06, apres `EPIC11-ARB-250`.**
    Il valait `build_payload(8)` a 18 mm / 300 ppp; il vaut desormais
    `build_payload(6)` a 14 mm / 300 ppp (81 modules, 2,04 px/module, 182 px).
    Le motif est exactement celui que ce docstring annoncait -- « si quelque
    chose deplace ce point, on le RE-MESURE, on ne le relache pas » --, a ceci
    pres que ce n'est pas une version d'OpenCV qui l'a deplace mais le
    changement d'ENCODEUR: a payload egal, `segno` et l'encodeur d'OpenCV
    rendent le meme COTE mais pas les memes MODULES (masque de donnees
    different, 298 modules sur 4 761 pour une charge de 256 octets). Le symbole
    du 2026-08-18 se sauvait au facteur 3, celui d'aujourd'hui se sauve des le
    facteur 2 -- ce qui ne mesure plus rien.

    Mutations mesurees a CE point, sous OpenCV 5.0.0 et `segno` 1.6.6:

        table ramenee a `(2,)`  -> le decodage ECHOUE (4 appels, unreadable)
        `INTER_LINEAR`          -> x2 reussit, 3 appels
        `INTER_NEAREST`         -> 5 appels, inchange
        `INTER_AREA`            -> 5 appels, inchange
        `INTER_LANCZOS4`        -> 5 appels, inchange

    **Trois de ces cinq mutations ne sont donc plus attrapees ici**, la ou
    l'ancien point en attrapait quatre. C'est dit plutot que taise: ce test
    tient la propriete « la table est parcourue au-dela de son premier facteur »
    et le choix d'une interpolation qui n'est pas lineaire; il ne tient plus, a
    lui seul, le choix entre cubique, plus-proche-voisin, aire et Lanczos.
    """
    payload = build_payload(6)
    sonde = qr_codes.render_for_print(qr_codes.encode_qr_image(payload), 14, 300)

    appels: list[str] = []
    vrai_decode = qr_codes.decode_qr_image

    def _compte(image, *, detector):
        appels.append(detector)
        return vrai_decode(image, detector=detector)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(qr_codes, "decode_qr_image", _compte)
        resultat = qr_codes.decode_qr_image_resilient(sonde)

    assert resultat.ok, resultat.status
    assert resultat.text == payload
    # 2 essais a taille native, 2 essais epuises au premier facteur, puis le
    # moteur demande decode au second facteur.
    assert appels == [
        qr_codes.DETECTOR_ARUCO, qr_codes.DETECTOR_CLASSIC,   # taille native
        qr_codes.DETECTOR_ARUCO, qr_codes.DETECTOR_CLASSIC,   # facteur 2, en vain
        qr_codes.DETECTOR_ARUCO,                              # facteur 3, sauve
    ]
