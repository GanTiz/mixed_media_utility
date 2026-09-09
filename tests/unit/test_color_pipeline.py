from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import color_pipeline


def test_mvp_color_manifest_fragment_marks_not_applied() -> None:
    fragment = color_pipeline.mvp_color_manifest_fragment(
        target_color_primaries="bt709",
        target_color_trc="bt709",
        target_colorspace="bt709",
        scan_input_format="jpg",
        patch_preset_id="patch-default-v1",
        source_bit_depth=8,
    )
    assert fragment["color_calibration_status"] == color_pipeline.NOT_APPLIED_STATUS
    assert fragment["color_calibration_status"] in color_pipeline.CALIBRATION_STATUS_VALUES
    assert fragment["output_bit_depth"] == 16
    assert fragment["output_format"] == "tiff"
    assert set(fragment) == set(color_pipeline.COLOR_MANIFEST_FIELDS)


def test_export_frame_tiff16_scales_8bit_input(tmp_path: Path) -> None:
    image8 = np.full((4, 4, 3), 128, dtype=np.uint8)
    output_path = tmp_path / "frame.tiff"

    color_pipeline.export_frame_tiff16(image8, str(output_path))

    assert output_path.is_file()

    import cv2
    reloaded = cv2.imread(str(output_path), cv2.IMREAD_UNCHANGED)
    assert reloaded.dtype == np.uint16
    assert reloaded[0, 0, 0] == 128 * 257


def test_export_frame_tiff16_rejects_unsupported_dtype(tmp_path: Path) -> None:
    image_float = np.zeros((4, 4, 3), dtype=np.float32)
    with pytest.raises(ValueError):
        color_pipeline.export_frame_tiff16(image_float, str(tmp_path / "out.tiff"))


def test_apply_active_calibration_refuses_only_when_there_is_no_profile() -> None:
    """Amende par la story 5.4b, AC 6, et c'est le seul test rendu caduc.

    L'ancien `test_request_active_calibration_always_raises_in_mvp` verrouillait le
    fait que la fonction leve **inconditionnellement**, y compris pour un profil
    valide. La revue de 5.5 avait qualifie cette fonction: « ce n'est pas un hook,
    c'est une exception non branchee ». 5.4b livre le vrai contrat, donc le test qui
    exigeait l'absence de contrat n'a plus d'objet.

    Ce qui est **conserve** de l'ancien test, parce que c'etait sa seule part juste:
    sans profil, on leve, et un appelant n'obtient jamais une correction partielle
    silencieuse.
    """
    import numpy as np

    from mixed_media_utility import color_calibration

    image = np.full((4, 4, 3), 128, dtype=np.uint8)
    with pytest.raises(color_pipeline.ColorCalibrationUnavailable):
        color_pipeline.apply_active_calibration(image, None)
    with pytest.raises(color_pipeline.ColorCalibrationUnavailable):
        color_pipeline.apply_active_calibration(image, {"some": "profile"})

    neutral = color_calibration.CorrectionProfile(
        stage_a=np.array([[1.0, 0.0], [1.0, 0.0], [1.0, 0.0]]), stage_m=np.eye(3))
    corrected = color_pipeline.apply_active_calibration(image, neutral)
    assert corrected.shape == image.shape
    assert isinstance(neutral, color_pipeline.CalibrationProfile)


def test_apply_active_calibration_delegue_l_eotf_et_ne_la_recopie_pas() -> None:
    """AC 6, apport que **rien** ne verifiait (finding majeur de la couche 1).

    Le message de commit de 5.4b invoquait le danger -- deux definitions de la fonction
    de transfert qui divergeraient rendraient la correction fausse d'un cote -- mais
    aucun test ne l'ecartait: une reimplementation locale de l'EOTF dans
    `color_pipeline` passait tous les tests.

    Le verrou porte sur l'egalite **numerique** avec le chemin de `color_calibration`,
    sur un profil non trivial: un profil neutre rendrait l'entree telle quelle et ne
    distinguerait aucune fonction de transfert.
    """
    import numpy as np

    from mixed_media_utility import color_calibration

    profile = color_calibration.CorrectionProfile(
        stage_a=np.array([[0.90, 0.02], [1.05, -0.01], [1.10, 0.03]]),
        stage_m=np.array([[0.94, 0.04, 0.02], [0.03, 0.93, 0.04], [0.02, 0.05, 0.93]]))
    image = np.array([[[10, 128, 240], [200, 60, 5]]], dtype=np.uint8)
    through_pipeline = color_pipeline.apply_active_calibration(image, profile)
    direct = color_calibration.apply_profile_to_image(image, profile)
    assert through_pipeline == pytest.approx(direct, abs=0.0), (
        "`apply_active_calibration` doit **deleguer**: une EOTF recopiee sur place "
        "diverge silencieusement de celle de la chaine de correction")


def test_apply_active_calibration_ne_sature_pas_un_scan_gros_boutien() -> None:
    """Finding majeur de la couche 2: la valeur de retour de `validate_bgr_input` etait
    **jetee**, contrairement aux deux autres sites d'appel du depot.

    `np.dtype(">u2")` -- ce qu'ecrit un scanner en ordre d'octets `MM` -- n'est pas egal
    a `np.uint16` sur une machine petit-boutienne. L'echelle etait donc deduite a 255 au
    lieu de 65535, et un scan 16 bits gros-boutien **saturait a blanc en silence**: pas
    une erreur, une image plausible et fausse.

    **Ce test ne verrouille aucune des deux couches a lui seul, et il faut le dire.**
    La propriete est desormais garantie deux fois -- `validate_bgr_input` normalise
    l'ordre des octets, et `apply_profile_to_image` deduit l'echelle du **type** et non
    d'une egalite de dtype -- si bien que muter l'une des deux laisse ce test vert.
    C'est de la defense en profondeur, pas une redondance a supprimer: chacune est
    verrouillee a son propre niveau, la seconde par
    `test_l_echelle_se_deduit_du_type_et_non_d_une_egalite_de_dtype`. Ce test-ci ne
    prouve que le comportement de bout en bout.
    """
    import numpy as np

    from mixed_media_utility import color_calibration

    neutral = color_calibration.CorrectionProfile(
        stage_a=np.array([[1.0, 0.0], [1.0, 0.0], [1.0, 0.0]]), stage_m=np.eye(3))
    # Un gris a mi-echelle 16 bits, ecrit en gros-boutien.
    native = np.full((2, 2, 3), 32768, dtype=np.uint16)
    big_endian = native.astype(">u2")
    assert big_endian.dtype != np.uint16, "le cas n'a d'interet qu'en ordre MM"

    corrected = color_pipeline.apply_active_calibration(big_endian, neutral)
    assert corrected.max() < 0.99, (
        f"un gris a mi-echelle ne doit pas sortir sature: {corrected.max()}")
    assert corrected == pytest.approx(
        color_pipeline.apply_active_calibration(native, neutral), abs=1e-12), (
        "l'ordre des octets ne doit rien changer au resultat")


def test_mvp_color_manifest_fragment_rejects_empty_or_none_values() -> None:
    base = dict(
        target_color_primaries="bt709",
        target_color_trc="bt709",
        target_colorspace="bt709",
        scan_input_format="tiff",
        patch_preset_id="patch-default-v1",
        source_bit_depth=16,
    )
    # None serialised to JSON becomes null, and ffmpeg would later receive
    # "-color_trc null" at encode time (story 6.3).
    for field in ("target_color_primaries", "target_color_trc", "target_colorspace"):
        for bad in (None, "", "   "):
            with pytest.raises(ValueError):
                color_pipeline.mvp_color_manifest_fragment(**{**base, field: bad})
    with pytest.raises(ValueError):
        color_pipeline.mvp_color_manifest_fragment(**{**base, "source_bit_depth": 12})


def test_calibration_status_set_is_enforced() -> None:
    for status in color_pipeline.CALIBRATION_STATUS_VALUES:
        assert color_pipeline.validate_calibration_status(status) == status
    with pytest.raises(ValueError):
        color_pipeline.validate_calibration_status("OK")


def test_failed_calibration_is_distinguishable_from_never_calibrated() -> None:
    # "applied" and "failed" were declared but unreachable, so a batch whose
    # calibration had failed was indistinguishable from one never calibrated.
    base = dict(
        target_color_primaries="bt709", target_color_trc="bt709",
        target_colorspace="bt709", scan_input_format="tiff",
        patch_preset_id="patch-default-v1", source_bit_depth=16,
    )
    assert color_pipeline.mvp_color_manifest_fragment(
        **base, color_calibration_status="failed"
    )["color_calibration_status"] == "failed"


def test_export_frame_tiff16_rejects_non_tiff_extension(tmp_path: Path) -> None:
    # Regression: cv2.imwrite picks its encoder from the extension and silently
    # falls back to 8 bits on ".jpg" while still returning True.
    image = np.full((4, 4, 3), 1000, dtype=np.uint16)
    for name in ("frame.jpg", "frame.png", "frame", "frame.tiff.tmp"):
        with pytest.raises(ValueError):
            color_pipeline.export_frame_tiff16(image, str(tmp_path / name))


def test_export_frame_tiff16_reports_source_bit_depth(tmp_path: Path) -> None:
    r8 = color_pipeline.export_frame_tiff16(
        np.full((4, 4, 3), 128, np.uint8), str(tmp_path / "a.tiff")
    )
    r16 = color_pipeline.export_frame_tiff16(
        np.full((4, 4, 3), 1000, np.uint16), str(tmp_path / "b.tiff")
    )
    assert r8["source_bit_depth"] == 8 and r8["output_bit_depth"] == 16
    assert r16["source_bit_depth"] == 16


def test_export_frame_tiff16_is_lossless_on_16bit_input(tmp_path: Path) -> None:
    # The nominal 16-bit contract path was never tested.
    import cv2
    rng = np.random.default_rng(0)
    image = rng.integers(0, 65536, (8, 8, 3), dtype=np.uint16)
    out = tmp_path / "roundtrip.tiff"
    color_pipeline.export_frame_tiff16(image, str(out))
    reloaded = cv2.imread(str(out), cv2.IMREAD_UNCHANGED)
    assert np.array_equal(reloaded, image)


def test_export_frame_tiff16_preserves_all_pixels_and_bounds(tmp_path: Path) -> None:
    # The old test asserted a single pixel of a uniform image, so a channel swap
    # or a transposition would have passed.
    import cv2
    image = np.zeros((3, 5, 3), np.uint8)
    image[..., 0], image[..., 1], image[..., 2] = 0, 128, 255
    out = tmp_path / "bounds.tiff"
    color_pipeline.export_frame_tiff16(image, str(out))
    reloaded = cv2.imread(str(out), cv2.IMREAD_UNCHANGED)
    assert reloaded.shape == image.shape
    assert np.array_equal(reloaded, image.astype(np.uint16) * 257)
    assert reloaded[..., 0].max() == 0 and reloaded[..., 2].max() == 65535


def test_validate_bgr_input_rejects_degenerate_and_foreign_inputs(tmp_path: Path) -> None:
    with pytest.raises(TypeError):
        color_pipeline.export_frame_tiff16(None, str(tmp_path / "x.tiff"))
    with pytest.raises(TypeError):
        color_pipeline.export_frame_tiff16([[1, 2], [3, 4]], str(tmp_path / "x.tiff"))
    with pytest.raises(ValueError):
        color_pipeline.export_frame_tiff16(np.zeros((0, 0, 3), np.uint8), str(tmp_path / "x.tiff"))
    for channels in (2, 5):
        with pytest.raises(ValueError):
            color_pipeline.export_frame_tiff16(
                np.zeros((4, 4, channels), np.uint8), str(tmp_path / "x.tiff")
            )


def test_export_frame_tiff16_accepts_big_endian_uint16(tmp_path: Path) -> None:
    # A scanner writing TIFF in MM byte order yields '>u2', valid 16-bit data
    # that the old `dtype == np.uint16` test rejected.
    import cv2
    image = np.full((4, 4, 3), 1000, dtype=">u2")
    out = tmp_path / "be.tiff"
    result = color_pipeline.export_frame_tiff16(image, str(out))
    assert result["source_bit_depth"] == 16
    assert cv2.imread(str(out), cv2.IMREAD_UNCHANGED)[0, 0, 0] == 1000
