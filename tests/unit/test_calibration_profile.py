"""Tests du format de profil de chaine (story 5.22, AC 1 et 2).

Le fichier de profil vit dans le projet sous `versions/calibration/<chain_id>.json`,
est **autoportant** (il porte son `chain_id`, sa forme, ses coefficients et ses
metadonnees) et se relit par **fusion pure** avec defauts. La serialisation est
deterministe octet pour octet, et l'aller-retour profil -> fichier -> profil
rend la meme correction a la precision serialisee.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import color_calibration
from mixed_media_utility.io import calibration_profile

CHAIN_ID = "600-tiff-41f9fa6c9e08"


def _document_complet(**overrides) -> dict:
    doc = {
        "schema_version": calibration_profile.PROFILE_SCHEMA_VERSION,
        "chain_id": CHAIN_ID,
        "correction_form_id": color_calibration.CORRECTION_FORM_TONE_CHROMA_ID,
        "coefficients": {
            "tone_anchors_in": [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5], [1.0, 1.0, 1.0]],
            "tone_anchors_out": [0.0, 0.5, 1.0],
            "chroma_matrix": [[1.0, 0.0], [0.0, 1.0]],
        },
        "read_patch_count": 130,
        "retained_patch_count": 128,
        "ink_floor_excluded": False,
        "source_page_id": "page-1",
        "template_id": "patches-18-v2",
    }
    doc.update(overrides)
    return doc


def _profil_affine() -> color_calibration.CorrectionProfile:
    # Regle des fabriques: aucune valeur uniforme, et `stage_a` (3x2) comme
    # `stage_m` (3x3) portent des coefficients tous distincts -- un echange des
    # deux, ou une permutation de leurs lignes, se voit sur les valeurs.
    return color_calibration.CorrectionProfile(
        stage_a=np.asarray([[1.01, -0.002], [0.99, 0.004], [1.03, -0.006]],
                           dtype=np.float64),
        stage_m=np.asarray([[0.97, 0.02, 0.01], [0.03, 0.95, 0.02],
                            [0.01, 0.04, 0.95]], dtype=np.float64),
        correction_id=color_calibration.CORRECTION_FORM_ID)


def _profil_lab() -> color_calibration.LabCorrectionProfile:
    return color_calibration.LabCorrectionProfile(
        lightness_slope=1.02, lightness_offset=-0.01,
        chroma_matrix=np.asarray([[1.04, -0.03], [0.02, 0.97]], dtype=np.float64),
        chroma_offset=np.asarray([0.5, -0.25], dtype=np.float64),
        correction_id=color_calibration.CORRECTION_FORM_LAB_ID)


def _profil_tone() -> color_calibration.ToneCurveCorrectionProfile:
    return color_calibration.ToneCurveCorrectionProfile(
        tone_anchors_in=np.asarray([[0.0, 0.0, 0.0], [0.4, 0.4, 0.4],
                                    [0.9, 0.9, 0.9]], dtype=np.float64),
        tone_anchors_out=np.asarray([0.0, 0.45, 1.0], dtype=np.float64),
        chroma_matrix=np.asarray([[1.1, -0.05], [0.03, 0.98]], dtype=np.float64),
        correction_id=color_calibration.CORRECTION_FORM_TONE_CHROMA_ID)


# --- AC 1: determinisme de la serialisation --------------------------------


def test_la_serialisation_est_deterministe_octet_pour_octet() -> None:
    once = calibration_profile.serialize_profile(_document_complet())
    twice = calibration_profile.serialize_profile(_document_complet())
    assert once == twice
    assert once.endswith("\n")


def test_la_serialisation_est_insensible_a_l_ordre_des_cles() -> None:
    base = _document_complet()
    reordonee = {cle: base[cle] for cle in reversed(list(base))}
    assert (calibration_profile.serialize_profile(base)
            == calibration_profile.serialize_profile(reordonee))


# --- AC 2: le fichier vit dans le projet, autoportant ----------------------


def test_write_profile_ecrit_dans_versions_calibration(tmp_path: Path) -> None:
    chemin = calibration_profile.write_profile(
        tmp_path, _document_complet())
    assert chemin == tmp_path / "versions" / "calibration" / f"{CHAIN_ID}.json"
    assert chemin.is_file()
    assert "600-tiff-" in chemin.read_text(encoding="utf-8")


def test_aller_retour_ecriture_relecture_a_l_identique(tmp_path: Path) -> None:
    calibration_profile.write_profile(tmp_path, _document_complet())
    relu = calibration_profile.read_profile(tmp_path, CHAIN_ID)
    # Fusion pure: un champ optionnel absent complete son defaut.
    assert relu["acceptance"] == {}
    for cle, valeur in _document_complet().items():
        assert relu[cle] == valeur, cle


def test_un_projet_copie_tel_quel_permet_le_rechargement(tmp_path: Path) -> None:
    original = tmp_path / "projet"
    copie = tmp_path / "copie"
    calibration_profile.write_profile(original, _document_complet())
    # Copie des seuls fichiers du projet, sans bibliotheque machine.
    for fichier in (original / "versions").rglob("*"):
        if fichier.is_file():
            cible = copie / fichier.relative_to(original)
            cible.parent.mkdir(parents=True, exist_ok=True)
            cible.write_bytes(fichier.read_bytes())
    relu = calibration_profile.read_profile(copie, CHAIN_ID)
    assert relu["chain_id"] == CHAIN_ID
    assert relu["coefficients"] == _document_complet()["coefficients"]


# --- relecture par fusion pure: refus nommes -------------------------------


def test_un_champ_requis_manquant_est_un_refus(tmp_path: Path) -> None:
    # Un fichier present mais invalide (edite a la main, produit par une
    # ancienne version) est refuse a la relecture: jamais un defaut invente.
    invalide = _document_complet()
    del invalide["correction_form_id"]
    chemin = calibration_profile.profile_path(tmp_path, CHAIN_ID)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(calibration_profile.serialize_profile(invalide),
                      encoding="utf-8")
    with pytest.raises(calibration_profile.ProfileValidationError):
        calibration_profile.read_profile(tmp_path, CHAIN_ID)


def test_un_champ_de_type_invalide_est_un_refus(tmp_path: Path) -> None:
    invalide = _document_complet(read_patch_count="130")
    with pytest.raises(calibration_profile.ProfileValidationError):
        calibration_profile.write_profile(tmp_path, invalide)


def test_une_version_de_schema_inconnue_est_un_refus(tmp_path: Path) -> None:
    invalide = _document_complet(schema_version=999)
    with pytest.raises(calibration_profile.ProfileValidationError):
        calibration_profile.write_profile(tmp_path, invalide)


def test_un_chain_id_hors_pattern_est_un_refus(tmp_path: Path) -> None:
    """La garde porte sur le `chain_id` **du document**, seul survivant du parametre.

    `EPIC5-ARB-101` (2026-08-19) a retire l'argument `chain_id` de `write_profile`:
    il etait accepte puis re-valide, sur la meme valeur, par
    `validate_profile_document`. La valeur fautive entre donc desormais par le
    document, qui est de toute facon la seule que le nom de fichier consulte.
    """
    for mauvais in ("../escape", "avec espace", "chemin/relatif", ""):
        with pytest.raises(calibration_profile.ProfileValidationError):
            calibration_profile.write_profile(
                tmp_path, _document_complet(chain_id=mauvais))
    # Autre bout de la garde: un identifiant livre passe. Sans ce temoin, les quatre
    # refus ci-dessus seraient vrais d'une fonction qui refuserait tout.
    assert calibration_profile.write_profile(
        tmp_path, _document_complet()).is_file()


def test_un_chain_id_a_saut_de_ligne_final_est_un_refus(tmp_path: Path) -> None:
    # Domaine d'activation precis de la garde: en Python `$` accepte un saut de
    # ligne **final**, donc `re.match(r"^[A-Za-z0-9_-]+$", "x\n")` rend un
    # match. Sans `fullmatch`, un `chain_id` valant `'x\n'` ecrivait un fichier
    # `versions/calibration/x\n.json` que plus personne ne retrouvait.
    #
    # La garde reste indispensable apres le retrait du drapeau de nommage (story
    # 5.23, AC 13): le `chain_id` d'un **profil externe** est lu dans un fichier
    # JSON que le projet n'a pas produit, et c'est desormais le seul chemin par
    # lequel une valeur non derivee atteint un nom de fichier.
    for mauvais in ("x\n", "600-tiff-abc\n", "x\r\n", "x\ny"):
        with pytest.raises(calibration_profile.ProfileValidationError):
            calibration_profile.write_profile(
                tmp_path, _document_complet(chain_id=mauvais))
    # Autre bout de la garde: elle reste inerte sur un identifiant livre.
    assert calibration_profile.write_profile(
        tmp_path, _document_complet()).is_file()


def test_un_chain_id_trop_long_est_un_refus(tmp_path: Path) -> None:
    """Meme deplacement que ci-dessus: la longueur est bornee sur le document."""
    trop_long = "x" * (calibration_profile.CANONICAL_ID_MAX_LENGTH + 1)
    with pytest.raises(calibration_profile.ProfileValidationError):
        calibration_profile.write_profile(
            tmp_path, _document_complet(chain_id=trop_long))
    # Frontiere haute exacte: la longueur maximale, elle, passe.
    limite = "x" * calibration_profile.CANONICAL_ID_MAX_LENGTH
    assert calibration_profile.write_profile(
        tmp_path, _document_complet(chain_id=limite)).is_file()


def test_profil_absent_est_profile_not_found(tmp_path: Path) -> None:
    with pytest.raises(calibration_profile.ProfileNotFoundError):
        calibration_profile.read_profile(tmp_path, CHAIN_ID)


def test_un_profil_tronque_est_un_refus(tmp_path: Path) -> None:
    chemin = calibration_profile.profile_path(tmp_path, CHAIN_ID)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text('{"schema_version": 1, "chain', encoding="utf-8")
    with pytest.raises(calibration_profile.ProfileValidationError):
        calibration_profile.read_profile(tmp_path, CHAIN_ID)


def test_profile_exists_distinguent_present_et_absent(tmp_path: Path) -> None:
    assert not calibration_profile.profile_exists(tmp_path, CHAIN_ID)
    calibration_profile.write_profile(tmp_path, _document_complet())
    assert calibration_profile.profile_exists(tmp_path, CHAIN_ID)


# --- forme du bloc `coefficients`, par forme de correction -----------------
#
# La couche 2 de la revue a mesure que la validation ne verifiait que des
# **types**: un profil externe ampute d'une cle etait ecrit dans le projet puis
# levait un `KeyError` nu -- et tout scan ulterieur de la chaine replantait --,
# et une `chroma_matrix` 1x2 au lieu de 2x2 passait sans erreur en ecrivant des
# pixels ecartes de 1,83. Les tests ci-dessous epinglent la garde par ses deux
# bouts: inerte sur les trois formes reellement produites, mordante sur chaque
# deformation construite.


def _document_de(profil, chaine: str) -> dict:
    return color_calibration.profile_to_document(
        profil, chain_id=chaine, source_page_id="calib-1",
        template_id="patches-18-v2", read_patch_count=130,
        retained_patch_count=128, ink_floor_excluded=True)


def test_les_formes_connues_de_io_sont_exactement_celles_du_module_couleur() -> None:
    # Epinglage de la derive entre les deux tables: `io/` ne peut pas importer
    # `color_calibration` (cycle), donc une forme ajoutee cote couleur sans sa
    # forme de document ici doit rougir plutot que d'etre refusee en silence a
    # la relecture.
    assert (set(calibration_profile._COEFFICIENT_SHAPES)
            == set(color_calibration.CORRECTION_FORMS))
    assert (calibration_profile.MIN_TONE_ANCHOR_COUNT
            == color_calibration.MIN_NEUTRAL_TONE_ANCHORS)


def test_les_trois_formes_reellement_produites_passent_la_validation(
        tmp_path: Path) -> None:
    # Premier bout de la garde: sur ce que `profile_to_document` produit
    # vraiment, elle est inerte -- ecriture, relecture et reconstruction.
    for chaine, profil in (("chaine-tone", _profil_tone()),
                           ("chaine-lab", _profil_lab()),
                           ("chaine-affine", _profil_affine())):
        calibration_profile.write_profile(
            tmp_path, _document_de(profil, chaine))
        relu = color_calibration.profile_from_document(
            calibration_profile.read_profile(tmp_path, chaine))
        assert isinstance(relu, type(profil))


def test_une_cle_de_coefficient_manquante_est_un_refus(tmp_path: Path) -> None:
    # La cle retiree n'est jamais la premiere du bloc: un controle qui ne
    # verifierait que la premiere cle ne se demasquerait pas autrement.
    amputations = (
        ("chaine-affine", _profil_affine(), "stage_m"),
        ("chaine-lab", _profil_lab(), "chroma_offset"),
        ("chaine-tone", _profil_tone(), "chroma_matrix"),
    )
    for chaine, profil, cle in amputations:
        document = _document_de(profil, chaine)
        del document["coefficients"][cle]
        with pytest.raises(calibration_profile.ProfileValidationError) as refus:
            calibration_profile.write_profile(tmp_path, document)
        assert cle in str(refus.value)
        # Rien n'entre dans le projet: c'est ce qui empeche l'empoisonnement
        # mesure (profil consigne, puis `KeyError` a chaque scan suivant).
        assert not calibration_profile.profile_exists(tmp_path, chaine)


def test_une_cle_de_coefficient_etrangere_est_un_refus(tmp_path: Path) -> None:
    document = _document_de(_profil_tone(), "chaine-tone")
    document["coefficients"]["stage_m"] = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0],
                                           [0.0, 0.0, 1.0]]
    with pytest.raises(calibration_profile.ProfileValidationError):
        calibration_profile.write_profile(tmp_path, document)


def test_une_dimension_de_coefficient_fausse_est_un_refus(tmp_path: Path) -> None:
    # Chaque deformation vient de la table mesuree par la couche 2.
    deformations = (
        # 1x2 au lieu de 2x2: le cas qui ne levait *aucune* erreur et ecrivait
        # des pixels a 1,83 d'ecart.
        ("chaine-tone", _profil_tone(), "chroma_matrix", [[1.0, 0.0]]),
        # matrice dentelee: `inhomogeneous shape` numpy, hors de toute garde.
        ("chaine-affine", _profil_affine(), "stage_a", [[1.0, 0.0], [0.0]]),
        # 2x2 au lieu de 3x3: `could not be broadcast` a l'application.
        ("chaine-affine", _profil_affine(), "stage_m", [[1.0, 0.0], [0.0, 1.0]]),
        # vecteur de chroma d'un seul axe au lieu de deux.
        ("chaine-lab", _profil_lab(), "chroma_offset", [0.0]),
        # scalaire de la forme Lab remplace par une liste.
        ("chaine-lab", _profil_lab(), "lightness_slope", [1.0]),
    )
    for chaine, profil, cle, valeur in deformations:
        document = _document_de(profil, chaine)
        document["coefficients"][cle] = valeur
        with pytest.raises(calibration_profile.ProfileValidationError) as refus:
            calibration_profile.write_profile(tmp_path, document)
        assert cle in str(refus.value), (chaine, cle)
        assert not calibration_profile.profile_exists(tmp_path, chaine)


def test_des_cardinaux_lies_incoherents_sont_un_refus(tmp_path: Path) -> None:
    # `tone_anchors_in` et `tone_anchors_out` decrivent la meme courbe point
    # par point: des cardinaux differents ne decrivent aucune courbe.
    document = _document_de(_profil_tone(), "chaine-tone")
    document["coefficients"]["tone_anchors_out"] = [0.0, 1.0]
    with pytest.raises(calibration_profile.ProfileValidationError):
        calibration_profile.write_profile(tmp_path, document)
    # Un ancrage unique est refuse par le meme chemin (cardinal minimal).
    document = _document_de(_profil_tone(), "chaine-tone")
    document["coefficients"]["tone_anchors_in"] = [[0.0, 0.0, 0.0]]
    document["coefficients"]["tone_anchors_out"] = [0.0]
    with pytest.raises(calibration_profile.ProfileValidationError):
        calibration_profile.write_profile(tmp_path, document)


def test_une_forme_de_correction_inconnue_est_un_refus_a_l_ecriture(
        tmp_path: Path) -> None:
    # Avant ce correctif, la forme inventee passait la validation et sortait en
    # `UnknownCorrectionFormError` non rattrapee, apres l'ecriture.
    with pytest.raises(calibration_profile.ProfileValidationError):
        calibration_profile.write_profile(
            tmp_path,
            _document_complet(correction_form_id="forme-inventee-9"))
    assert not calibration_profile.profile_exists(tmp_path, CHAIN_ID)


def test_un_profil_externe_mal_forme_est_refuse_a_la_relecture(
        tmp_path: Path) -> None:
    # Le fichier a pu etre ecrit hors de ce module (profil recu a cote d'un
    # projet, edite a la main): la relecture le refuse par le meme motif nomme.
    document = _document_de(_profil_affine(), CHAIN_ID)
    del document["coefficients"]["stage_m"]
    chemin = calibration_profile.profile_path(tmp_path, CHAIN_ID)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(calibration_profile.serialize_profile(document),
                      encoding="utf-8")
    with pytest.raises(calibration_profile.ProfileValidationError):
        calibration_profile.read_profile(tmp_path, CHAIN_ID)


# --- AC 1: aller-retour profil -> fichier -> profil ------------------------


def test_aller_retour_profil_rend_la_meme_correction(tmp_path: Path) -> None:
    profil = _profil_tone()
    document = color_calibration.profile_to_document(
        profil, chain_id=CHAIN_ID, source_page_id="calib-1",
        template_id="patches-18-v2", read_patch_count=130,
        retained_patch_count=128, ink_floor_excluded=False)
    calibration_profile.write_profile(tmp_path, document)
    relu = color_calibration.profile_from_document(
        calibration_profile.read_profile(tmp_path, CHAIN_ID))

    # Egalite des coefficients a la precision serialisee.
    assert np.allclose(relu.tone_anchors_in, profil.tone_anchors_in)
    assert np.allclose(relu.tone_anchors_out, profil.tone_anchors_out)
    assert np.allclose(relu.chroma_matrix, profil.chroma_matrix)
    assert relu.correction_id == profil.correction_id

    # Egalite de la sortie `apply_linear` sur une image de test (AC 1).
    rng = np.random.default_rng(0)
    image = rng.random((16, 24, 3))
    assert np.allclose(relu.apply_linear(image), profil.apply_linear(image))


def test_aller_retour_de_la_forme_affine_rend_la_meme_correction(
        tmp_path: Path) -> None:
    # La forme affine n'etait serialisee ni rechargee par aucun test: le mutant
    # qui echange `stage_a` et `stage_m` dans `profile_to_document` passait les
    # 17 tests du fichier. Les Dev Notes de 5.22 exigent l'aller-retour sur au
    # moins deux formes; celui-ci est le second.
    profil = _profil_affine()
    document = color_calibration.profile_to_document(
        profil, chain_id=CHAIN_ID, source_page_id="calib-1",
        template_id="patches-18-v2", read_patch_count=130,
        retained_patch_count=128, ink_floor_excluded=True)

    # Le document porte les deux etages **a leur place**, avec leurs dimensions
    # propres (3x2 contre 3x3): un echange des deux cles se voit ici.
    assert document["coefficients"]["stage_a"] == [
        [1.01, -0.002], [0.99, 0.004], [1.03, -0.006]]
    assert document["coefficients"]["stage_m"][0] == [0.97, 0.02, 0.01]
    assert document["correction_form_id"] == color_calibration.CORRECTION_FORM_ID

    calibration_profile.write_profile(tmp_path, document)
    relu = color_calibration.profile_from_document(
        calibration_profile.read_profile(tmp_path, CHAIN_ID))
    assert isinstance(relu, color_calibration.CorrectionProfile)
    assert np.allclose(relu.stage_a, profil.stage_a)
    assert np.allclose(relu.stage_m, profil.stage_m)
    assert relu.correction_id == profil.correction_id

    # Egalite de la sortie `apply_linear` sur une image de test (AC 1): c'est
    # elle qui interdit qu'un echange des etages passe par compensation.
    rng = np.random.default_rng(1)
    image = rng.random((16, 24, 3))
    assert np.allclose(relu.apply_linear(image), profil.apply_linear(image))


def test_deux_formes_distinctes_ne_se_confondent_pas_a_la_relecture(
        tmp_path: Path) -> None:
    # Regle des fabriques: au moins deux formes distinguables, jamais un
    # remplissage uniforme. La cible historiquement absente -- la forme affine
    # -- est placee **en derniere** position, pas en premiere.
    for chaine, profil in (("chaine-tone", _profil_tone()),
                           ("chaine-lab", _profil_lab()),
                           ("chaine-affine", _profil_affine())):
        doc = color_calibration.profile_to_document(
            profil, chain_id=chaine, source_page_id="calib-1",
            template_id="patches-18-v2", read_patch_count=130,
            retained_patch_count=128, ink_floor_excluded=True)
        calibration_profile.write_profile(tmp_path, doc)
        relu = color_calibration.profile_from_document(
            calibration_profile.read_profile(tmp_path, chaine))
        assert relu.correction_id == profil.correction_id
        assert isinstance(relu, type(profil))


def test_une_forme_inconnue_est_refusee_au_rechargement() -> None:
    with pytest.raises(color_calibration.UnknownCorrectionFormError):
        color_calibration.profile_from_document(
            _document_complet(correction_form_id="forme-inconnue-1"))


def test_la_relecture_porte_la_politique_de_plancher(tmp_path: Path) -> None:
    # Dev Notes 2: `ink_floor_excluded` doit etre conserve au fichier -- un
    # profil recharge sans lui pourrait etre applique sous une politique de
    # plancher differente.
    calibration_profile.write_profile(tmp_path, _document_complet())
    assert calibration_profile.read_profile(tmp_path, CHAIN_ID)[
        "ink_floor_excluded"] is False
    avec_plancher = _document_complet(ink_floor_excluded=True)
    calibration_profile.write_profile(tmp_path, avec_plancher)
    assert calibration_profile.read_profile(tmp_path, CHAIN_ID)[
        "ink_floor_excluded"] is True

# ---------------------------------------------------------------------------
# Story 5.23, correction du 2026-08-18 : le profil porte la mesure BRUTE de ses
# pastilles temoins, donc la divergence brute a brute cesse d'exiger une passe unique
# ---------------------------------------------------------------------------
#
# Mesure sur les vrais scans d'Egan le 2026-08-18: chaine calibree, planches corrigees,
# et `raw_divergence = {"reason": "raw_divergence_no_calibration_sheet",
# "mean_raw_de76": null, "paired_value_ids": []}` -- la mesure centrale d'`EPIC5-ARB-82`
# n'avait jamais lieu, faute d'avoir consigne les temoins de la page de calibration.
#
# **Regle des fabriques.** La fabrique ci-dessous produit SIX valeurs distinguables
# (aucun remplissage uniforme), la valeur visee par les tests d'appariement n'est jamais
# en premiere position, et les deux jeux sont donnes dans des ordres differents: une
# permutation ne se voit que si les elements different.


#: Six temoins distinguables, en sRGB encode [0, 1], ordre **BGR**. Les identifiants sont
#: volontairement dans le desordre: c'est le regime reel -- la page pose ses temoins par
#: le bandeau de bordure, la lecture les rend dans l'ordre du balayage.
_TEMOINS_MESURES: tuple[tuple[str, tuple[float, float, float]], ...] = (
    ("secondary-magenta", (0.581, 0.232, 0.679)),
    ("primary-red", (0.180, 0.171, 0.742)),
    ("neutral-065", (0.251, 0.254, 0.257)),
    ("secondary-cyan", (0.684, 0.641, 0.233)),
    ("primary-blue", (0.622, 0.291, 0.174)),
    ("primary-green", (0.271, 0.583, 0.212)),
)


def _document_avec_temoins(temoins=_TEMOINS_MESURES, **overrides) -> dict:
    doc = _document_complet(**overrides)
    doc[calibration_profile.WITNESS_RAW_FIELD] = (
        calibration_profile.witness_raw_to_document(temoins))
    return doc


def test_le_profil_ecrit_et_relit_les_mesures_brutes_de_ses_temoins(
    tmp_path: Path,
) -> None:
    """Ce que la correction ajoute au format: la mesure voyage dans le fichier.

    Sans elle, un scan de planche fait des mois plus tard n'a **rien** a comparer, et
    c'est ce que le manifeste du 2026-08-18 declarait.
    """
    calibration_profile.write_profile(tmp_path, _document_avec_temoins())
    relu = calibration_profile.read_profile(tmp_path, CHAIN_ID)
    assert calibration_profile.witness_raw_of_document(relu) == tuple(
        sorted(_TEMOINS_MESURES))


def test_les_temoins_sont_apparies_par_identifiant_et_jamais_par_position(
    tmp_path: Path,
) -> None:
    """Le meme jeu dans deux ordres differents rend le **meme** document.

    C'est la famille `M33` / `M25`, sept fois payee ici. Le volet decisif n'est pas que
    le document soit trie: c'est que la valeur visee, placee en **derniere** position a
    l'ecriture, se relise avec **sa** mesure et pas avec celle de sa voisine.
    """
    a_l_envers = tuple(reversed(_TEMOINS_MESURES))
    calibration_profile.write_profile(tmp_path, _document_avec_temoins())
    endroit = calibration_profile.read_profile(tmp_path, CHAIN_ID)
    calibration_profile.write_profile(
        tmp_path, _document_avec_temoins(a_l_envers))
    envers = calibration_profile.read_profile(tmp_path, CHAIN_ID)
    assert endroit == envers

    # La cible n'est ni la premiere ni la derniere du jeu ecrit, et elle porte sa propre
    # mesure: un appariement positionnel lui donnerait celle de `secondary-magenta`.
    relu = dict(calibration_profile.witness_raw_of_document(envers))
    assert relu["primary-red"] == (0.180, 0.171, 0.742)
    assert relu["secondary-magenta"] == (0.581, 0.232, 0.679)
    assert len(relu) == len(_TEMOINS_MESURES)


def test_un_profil_ecrit_avant_cette_mesure_se_relit_sans_refus(tmp_path: Path) -> None:
    """Retrocompatibilite (AC 8quater, « champs optionnels »): absence != refus.

    Un profil de 5.22 n'a pas le champ. Sa relecture reussit, et la lecture des temoins
    rend une suite **vide** -- « pas mesure » --, sans qu'aucun champ ne soit invente.
    """
    ancien = _document_complet()
    assert calibration_profile.WITNESS_RAW_FIELD not in ancien
    calibration_profile.write_profile(tmp_path, ancien)
    relu = calibration_profile.read_profile(tmp_path, CHAIN_ID)
    assert calibration_profile.witness_raw_of_document(relu) == ()


def test_le_champ_est_absent_du_fichier_plutot_que_vide(tmp_path: Path) -> None:
    """« Pas mesure » et « mesure, rien trouve » ne s'ecrivent pas pareil.

    Les deux se lisent differemment au manifeste (`raw_divergence_no_calibration_sheet`
    contre `raw_divergence_witness_band_not_printed`), donc le document ne doit pas
    pouvoir les confondre: le champ est **absent**, et une liste vide explicite est un
    refus nomme -- avant toute ecriture.
    """
    calibration_profile.write_profile(tmp_path, _document_complet())
    brut = calibration_profile.profile_path(tmp_path, CHAIN_ID).read_text(
        encoding="utf-8")
    assert calibration_profile.WITNESS_RAW_FIELD not in brut

    with pytest.raises(calibration_profile.ProfileValidationError):
        calibration_profile.write_profile(
            tmp_path,
            _document_complet(**{calibration_profile.WITNESS_RAW_FIELD: []}))
    # Le refus a eu lieu **avant** l'ecriture: le fichier precedent est intact.
    assert calibration_profile.WITNESS_RAW_FIELD not in (
        calibration_profile.profile_path(tmp_path, CHAIN_ID).read_text(encoding="utf-8"))


@pytest.mark.parametrize("temoins", [
    # Triplet d'un autre cardinal: deux composantes ne decrivent aucune couleur.
    (("primary-red", (0.18, 0.17)),),
    # Composante non finie: un `nan` compare a un seuil rend toujours False.
    (("primary-red", (0.18, float("nan"), 0.74)),),
    # Mesure restee en 8 bits: elle chiffrerait une divergence de nulle part.
    (("primary-red", (18.0, 17.0, 74.0)),),
    # Composante negative.
    (("primary-red", (-0.01, 0.17, 0.74)),),
    # Identifiant vide.
    (("", (0.18, 0.17, 0.74)),),
])
def test_une_mesure_de_temoin_mal_formee_est_un_refus(tmp_path: Path, temoins) -> None:
    with pytest.raises(calibration_profile.ProfileValidationError):
        calibration_profile.write_profile(
            tmp_path,
            _document_complet(**{
                calibration_profile.WITNESS_RAW_FIELD:
                    [[value_id, list(triplet)] for value_id, triplet in temoins]}))


def test_un_doublon_ou_un_ordre_libre_de_temoins_est_un_refus(tmp_path: Path) -> None:
    """Deux fois le meme identifiant, ou un ordre non trie, sont refuses.

    Le premier ferait dependre la mesure de la derniere occurrence lue; le second ferait
    dependre le fichier de la graine de hachage du processus qui l'ecrit, donc casserait
    la reproductibilite octet pour octet.
    """
    doublon = [["primary-red", [0.18, 0.17, 0.74]], ["primary-red", [0.2, 0.2, 0.2]]]
    desordre = [["primary-red", [0.18, 0.17, 0.74]], ["neutral-065", [0.25, 0.25, 0.25]]]
    for entrees in (doublon, desordre):
        with pytest.raises(calibration_profile.ProfileValidationError):
            calibration_profile.write_profile(
                tmp_path,
                _document_complet(**{calibration_profile.WITNESS_RAW_FIELD: entrees}))


def test_la_serialisation_des_temoins_est_deterministe_et_de_precision_documentee(
    tmp_path: Path,
) -> None:
    """Deux ecritures du meme profil rendent le meme fichier, octet pour octet.

    L'arrondi a `WITNESS_RAW_DECIMALS` decimales est **idempotent** -- arrondir un nombre
    deja arrondi ne le deplace pas --, ce qui est la condition pour que l'aller-retour
    fichier -> document -> fichier soit stable. La precision retenue laisse trois ordres
    de grandeur sous le pas de quantification 8 bits (1/255).
    """
    bruite = (
        ("neutral-065", (0.2512345678901, 0.2543219876543, 0.2571111111111)),
        ("primary-red", (0.1801234567891, 0.1712345678912, 0.7423456789123)),
    )
    document = _document_avec_temoins(bruite)
    premier = calibration_profile.serialize_profile(
        calibration_profile.validate_profile_document(document))
    calibration_profile.write_profile(tmp_path, document)
    relu = calibration_profile.read_profile(tmp_path, CHAIN_ID)
    second = calibration_profile.serialize_profile(
        calibration_profile.validate_profile_document(relu))
    assert premier == second
    assert calibration_profile.profile_path(tmp_path, CHAIN_ID).read_text(
        encoding="utf-8") == premier

    ecart = max(
        abs(mesuree - relue)
        for (_, mesures), (_, relues) in zip(
            bruite, calibration_profile.witness_raw_of_document(relu))
        for mesuree, relue in zip(mesures, relues))
    assert ecart <= 0.5 * 10 ** -calibration_profile.WITNESS_RAW_DECIMALS
    assert ecart < (1.0 / 255.0) / 1000.0


def test_la_relecture_des_temoins_trie_meme_une_entree_desordonnee() -> None:
    """`witness_raw_from_document` trie par identifiant, quoi qu'on lui donne.

    Le document valide est deja trie -- `_validate_witness_raw` l'exige --, donc ce tri
    est une **seconde** garantie et pas la premiere. Elle est epinglee ici parce qu'un
    appelant peut construire la suite sans passer par la validation (fabrique de test,
    profil en memoire): sans ce tri, l'ordre d'iteration suivrait celui de l'appelant,
    et deux ordres differents rendraient deux suites differentes du meme jeu.
    """
    desordre = [["primary-red", [0.18, 0.17, 0.74]], ["neutral-065", [0.25, 0.25, 0.26]]]
    assert calibration_profile.witness_raw_from_document(desordre) == (
        ("neutral-065", (0.25, 0.25, 0.26)),
        ("primary-red", (0.18, 0.17, 0.74)),
    )
    assert calibration_profile.witness_raw_from_document(
        list(reversed(desordre))) == calibration_profile.witness_raw_from_document(
            desordre)
