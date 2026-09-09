"""Tests de la calibration couleur active (story 5.4b, coeur des fonctions pures).

Ce fichier verifie que le code **applique** les decisions du Gate 4, et non qu'il
fait quelque chose de raisonnable. Chaque test nomme l'arbitrage qu'il verrouille:
sans cela, une reecriture ulterieure passerait les tests en changeant la decision.
"""

from __future__ import annotations

import re

import numpy as np
import pytest

from mixed_media_utility import color_calibration as cc
from mixed_media_utility import color_metrics as cm
from mixed_media_utility import patch_presets, patch_values


# --- EPIC5-ARB-25 : les fonctions de transfert -------------------------------

def test_eotf_oetf_aller_retour_est_neutre():
    """Sans cette propriete, une derive de correction serait imputee a l'ajustement."""
    encoded = np.linspace(0.0, 1.0, 4096)
    assert np.abs(cc.oetf(cc.eotf(encoded)) - encoded).max() < 1e-12


def test_eotf_respecte_le_coude_de_la_specification():
    """Le segment lineaire sous 0,04045, la puissance 2,4 au-dessus."""
    assert cc.eotf(0.04045) == pytest.approx(0.04045 / 12.92)
    assert cc.eotf(1.0) == pytest.approx(1.0)
    assert cc.eotf(0.0) == pytest.approx(0.0)


def test_ponderation_neutre_quand_la_distorsion_est_affine_en_lumiere():
    """Contre-epreuve d'`EPIC5-ARB-31`, et c'est elle qui justifie la ponderation.

    Si la distorsion est *vraiment* affine dans la lumiere, le fit pondere et le fit
    non pondere doivent rendre **les memes** coefficients: la ponderation est alors
    neutre la ou le modele physique tient. Un test qui ne verifierait que le cas
    reparateur laisserait passer une ponderation qui deforme le cas nominal.
    """
    reference = np.linspace(0.02, 0.95, 6)[:, None] * np.ones((1, 3))
    measured = (reference - 0.02) / 1.1  # affine en lumiere, inversible
    weighted = cc.fit_stage_a(measured, reference)
    unweighted = cc.fit_stage_a(measured, reference, weights=np.ones_like(reference))
    assert np.abs(weighted - unweighted).max() < 1e-9


def test_ponderation_repare_l_ancre_sombre():
    """Le cas que la ponderation existe pour traiter: distorsion non affine.

    Un engraissement de point (gamma dans l'encode) n'est pas affine en lumiere. Le
    fit non pondere ignore alors l'ancre sombre, qui ne pese que ~0,7 % de la
    dynamique lineaire; le fit pondere doit lui rendre un meilleur residu **sur
    cette ancre**, ce qui est la propriete demandee et non un residu global plus bas.
    """
    reference_encoded = np.array([20, 110, 200, 245], dtype=np.float64) / 255.0
    reference = cc.eotf(reference_encoded)[:, None] * np.ones((1, 3))
    measured = cc.eotf(np.power(reference_encoded, 1.0 / 1.18))[:, None] * np.ones((1, 3))

    weighted = cc.apply_stage_a(cc.fit_stage_a(measured, reference), measured)
    unweighted = cc.apply_stage_a(
        cc.fit_stage_a(measured, reference, weights=np.ones_like(reference)), measured)
    dark_weighted = abs(cc.oetf(weighted[0, 0]) - reference_encoded[0])
    dark_unweighted = abs(cc.oetf(unweighted[0, 0]) - reference_encoded[0])
    assert dark_weighted < dark_unweighted


def test_etage_a_refuse_un_seul_point():
    """Une affine ajustee sur un point est indeterminee; `lstsq` rendrait une
    solution de norme minimale d'apparence valide."""
    with pytest.raises(ValueError, match="deux au minimum"):
        cc.fit_stage_a(np.array([[0.5, 0.5, 0.5]]), np.array([[0.4, 0.4, 0.4]]))


# --- EPIC5-ARB-28.1 : le critere --------------------------------------------

def test_matrice_xyz_est_en_ordre_bgr():
    """`EPIC5-ARB-28.1` exige la forme permutee **ecrite dans le code**.

    Verification par la propriete qui distingue les deux formes: la luminance `Y`
    d'un bleu pur est faible (0,0722) et celle d'un vert pur est forte (0,7152). Une
    matrice canonique nourrie de BGR inverserait les deux et rendrait un Lab
    plausible et faux.
    """
    matrix = np.asarray(cc.SRGB_TO_XYZ_D65_BGR)
    blue_y = matrix[1] @ np.array([1.0, 0.0, 0.0])
    green_y = matrix[1] @ np.array([0.0, 1.0, 0.0])
    assert blue_y == pytest.approx(0.0721750)
    assert green_y == pytest.approx(0.7151522)
    assert np.allclose(matrix.sum(axis=1), np.asarray([0.95047, 1.0, 1.08883]), atol=2e-4)


def test_metrique_identite_rend_zero():
    values = np.array([[0.1, 0.5, 0.9], [0.8, 0.2, 0.4]])
    assert cc.delta_e76_srgb_d65(values, values).max() == pytest.approx(0.0)


def test_metrique_temoin_asymetrique_rouge_bleu():
    """**Le test qui attrape une inversion R/B.** Un patch neutre ne detecte rien.

    En BGR, `(0, 0, 1)` est un rouge pur et `(1, 0, 0)` un bleu pur. Si la chaine
    confondait les deux, une correction convergerait sur les mauvaises couleurs et
    rendrait un resultat plausible -- c'est le piege que le contrat BGR de
    `color_pipeline` documente apres mesure de revue.
    """
    red_bgr = np.array([[0.0, 0.0, 1.0]])
    blue_bgr = np.array([[1.0, 0.0, 0.0]])
    assert cc.delta_e76_srgb_d65(red_bgr, blue_bgr)[0] > 100.0
    # Et les deux ne sont pas symetriques en clarte: le rouge est plus clair.
    assert cc.lab_from_srgb_bgr(red_bgr)[0, 0] > cc.lab_from_srgb_bgr(blue_bgr)[0, 0]


def test_metrique_deviation_connue_est_calculable_a_la_main():
    """Un ecart de clarte seul doit rendre exactement `|dL*|`."""
    reference = np.array([[0.5, 0.5, 0.5]])
    lighter = np.array([[0.6, 0.6, 0.6]])
    expected = abs(cc.lab_from_srgb_bgr(lighter)[0, 0] - cc.lab_from_srgb_bgr(reference)[0, 0])
    assert cc.delta_e76_srgb_d65(lighter, reference)[0] == pytest.approx(expected)


def test_metrique_jeu_vide_ne_rend_pas_un_nan_silencieux():
    """Comportement declare plutot que `nan`: un jeu vide est une erreur d'appelant."""
    empty = np.zeros((0, 3))
    result = cc.delta_e76_srgb_d65(empty, empty)
    assert result.shape == (0,)


# --- EPIC5-ARB-28.2 : le diagnostic -----------------------------------------

def test_diagnostic_porte_sur_la_mesure_brute_et_par_canal():
    """`EPIC5-ARB-28.2`: domaine encode, entree brute, trois nombres par canal.

    Une dominante bleue de +10 % doit ressortir sur le **canal bleu**, en position 0
    du triplet BGR. Si le diagnostic etait calcule sur la mesure corrigee, il
    rendrait ~0 -- c'est exactement ce que la correction a enleve.
    """
    reference = np.array([[0.5, 0.5, 0.5], [0.25, 0.25, 0.25]])
    measured = reference * np.array([1.10, 1.0, 1.0])
    per_channel, detail = cc.channel_relative_deviation(measured, reference)
    assert per_channel[0] == pytest.approx(0.10)
    assert per_channel[1] == pytest.approx(0.0)
    assert detail.shape == reference.shape


def test_diagnostic_a_un_plancher_au_denominateur():
    """Le plancher rend la formule totale, sans quoi une reference nulle diviserait
    par zero."""
    per_channel, _ = cc.channel_relative_deviation(
        np.array([[0.0, 0.0, 0.0]]), np.array([[0.0, 0.0, 0.0]]))
    assert np.isfinite(per_channel).all()


@pytest.mark.parametrize("mesure,reference", [
    (None, np.array([[0.5, 0.5, 0.5]])),
    (np.array([[0.5, 0.5, 0.5]]), None),
    (None, None),
])
def test_diagnostic_refuse_none_plutot_que_de_rendre_un_nan_silencieux(mesure, reference):
    """Deuxieme passe de revue, `EPIC5-ARB-78` (2026-08-14): `np.asarray(None,
    dtype=float)` vaut silencieusement `nan` en numpy, et sans ce refus le diagnostic
    ressortait `(nan, nan, nan)` sans lever -- la meme propagation silencieuse que
    `ColorMetricError` existe pour fermer ailleurs dans ce module.
    """
    with pytest.raises(cc.ColorMetricError, match="None"):
        cc.channel_relative_deviation(mesure, reference)


def test_diagnostic_refuse_une_entree_non_finie():
    """Meme garde, sur `nan`/`inf` fournis directement plutot que via `None`."""
    reference = np.array([[0.5, 0.5, 0.5]])
    with pytest.raises(cc.ColorMetricError, match="finie"):
        cc.channel_relative_deviation(np.array([[np.nan, 0.5, 0.5]]), reference)
    with pytest.raises(cc.ColorMetricError, match="finie"):
        cc.channel_relative_deviation(reference, np.array([[np.inf, 0.5, 0.5]]))


# --- EPIC5-ARB-26 : les deux etages -----------------------------------------

def test_etage_m_a_ses_lignes_de_somme_un():
    """La contrainte est **parametree**, pas ajoutee apres coup: elle doit tenir
    exactement, quelles que soient les donnees."""
    rng = np.random.default_rng(3)
    source = rng.random((12, 3))
    target = rng.random((12, 3))
    matrix = cc.fit_stage_m(source, target)
    assert np.abs(matrix.sum(axis=1) - 1.0).max() < 1e-12


def test_etage_a_recupere_des_parametres_distincts_par_canal():
    """Finding majeur de la couche 1: **aucun test n'avait de donnees distinctes par
    canal**, donc une permutation des canaux survivait a l'ajustement.

    Tous les tests existants nourrissaient `fit_stage_a` de valeurs identiques sur les
    trois canaux (`reference[:, None] * ones((1, 3))`). Sur des donnees uniformes, echanger
    deux canaux ne change rien -- c'est la regle des fabriques du CLAUDE.md, appliquee aux
    canaux plutot qu'aux elements d'une collection. Ici chaque canal porte son propre gain
    et son propre decalage, et le fit doit les rendre **chacun a sa place**.
    """
    gains = np.array([0.80, 0.95, 1.12])
    offsets = np.array([0.030, -0.010, 0.005])
    reference = np.stack([np.linspace(0.05, 0.90, 8),
                          np.linspace(0.10, 0.85, 8),
                          np.linspace(0.02, 0.95, 8)], axis=1)
    # `measured` est ce qu'on lit quand la reference a subi (gain, decalage) par canal:
    # le fit doit donc rendre l'inverse, canal par canal.
    measured = (reference - offsets) / gains
    parameters = cc.fit_stage_a(measured, reference, weights=np.ones_like(reference))
    assert parameters[:, 0] == pytest.approx(gains, rel=1e-9), (
        f"gains rendus {parameters[:, 0]} pour {gains}: un canal permute ne se voit "
        "que sur des donnees distinctes par canal")
    assert parameters[:, 1] == pytest.approx(offsets, abs=1e-9)
    # Contre-epreuve: les trois gains sont deux a deux differents, sans quoi le test
    # ci-dessus passerait aussi avec une permutation.
    assert len(set(np.round(gains, 6))) == 3
    # **Et l'application doit employer chaque parametre sur son canal.** Verifier le
    # seul ajustement ne suffit pas: une permutation dans `apply_stage_a` survit,
    # parce que l'etage `M` ajuste ensuite l'absorbe -- mesure en mutant
    # `values * gains` en `values * gains[::-1]`, qui laissait tous les tests verts.
    applied = cc.apply_stage_a(parameters, measured)
    assert applied == pytest.approx(reference, abs=1e-9), (
        "apply_stage_a doit rendre la reference canal par canal; une permutation des "
        "canaux y est invisible tant que seul le fit est verifie")


def test_etage_m_reconstruit_une_matrice_connue():
    """Finding majeur de la couche 1: `fit_stage_m` n'etait compare a **aucune matrice
    connue**, donc un appariement positionnel inverse survivait.

    Les tests existants verifiaient des **proprietes** (lignes de somme 1, neutres
    invariants), qu'une matrice transposee satisfait tout aussi bien: la transposee d'une
    matrice a lignes de somme 1 n'a pas ses lignes de somme 1 en general, mais le
    reajustement la ramene dans la contrainte, et le residu ne le dit pas. C'est la
    famille de defauts que le CLAUDE.md documente -- appariement positionnel -- et elle
    ne se voit que sur une matrice **asymetrique** dont on connait la reponse.
    """
    known = np.array([
        [0.90, 0.07, 0.03],
        [0.05, 0.88, 0.07],
        [0.02, 0.10, 0.88],
    ])
    assert np.abs(known.sum(axis=1) - 1.0).max() < 1e-12
    assert np.abs(known - known.T).max() > 0.01, (
        "la matrice temoin doit etre asymetrique: une matrice symetrique est egale a "
        "sa transposee, donc elle ne peut pas demasquer une inversion")

    rng = np.random.default_rng(7)
    source = rng.uniform(0.05, 0.95, size=(24, 3))
    target = source @ known.T
    fitted = cc.fit_stage_m(source, target)
    assert fitted == pytest.approx(known, abs=1e-9), (
        f"matrice rendue\n{fitted}\npour\n{known}")


def test_les_deux_etages_sont_orthogonaux_et_la_restriction_aux_neutres_compte():
    """Finding majeur de la couche 1: **l'orthogonalite des deux etages n'etait testee
    par rien**, alors que c'est la propriete pour laquelle `EPIC5-ARB-26` restreint
    l'etage `A` au role `neutral_axis`.

    Mesure de la couche: ajuster `A` sur tout le jeu au lieu des seuls neutres fait
    passer le residu de 0,0000 a 2,1855 dE76. Un test qui ne verifiait que « les neutres
    restent invariants sous `M` » laissait donc passer un `A` ajuste sur le mauvais
    sous-ensemble -- la moitie de l'invariant.
    """
    table = patch_values.active_table()
    kept, neutral = cc.adjustment_and_neutral_masks(table.adjustment_values())
    reference = np.array([[v.rgb[2], v.rgb[1], v.rgb[0]] for v in kept],
                         dtype=np.float64) / 255.0
    # Distorsion exactement dans la classe que `C = M o A` inverse: affine par canal en
    # lumiere, puis diaphonie a lignes de somme 1.
    crosstalk = np.array([[0.93, 0.05, 0.02], [0.03, 0.94, 0.03], [0.02, 0.06, 0.92]])
    linear = cc.eotf(reference)
    measured = cc.oetf(np.clip((linear * 0.92 + 0.02) @ crosstalk.T, 0.0, 1.0))

    correct = cc.fit_correction(measured, reference, neutral)
    residual_correct = float(cc.delta_e76_srgb_d65(
        cc.oetf(np.clip(correct.apply_linear(cc.eotf(measured)), 0.0, 1.0)),
        reference).mean())

    # Le meme ajustement, `A` pris sur **tout** le jeu: c'est la mutation que rien ne
    # tuait. Le masque devient tout-vrai.
    everywhere = cc.fit_correction(measured, reference, np.ones(len(reference), bool))
    residual_everywhere = float(cc.delta_e76_srgb_d65(
        cc.oetf(np.clip(everywhere.apply_linear(cc.eotf(measured)), 0.0, 1.0)),
        reference).mean())

    assert residual_correct < 0.05, (
        f"la forme specifiee doit inverser exactement cette classe: {residual_correct}")
    assert residual_everywhere > 10 * max(residual_correct, 1e-6), (
        f"ajuster A hors de l'axe neutre doit degrader visiblement le residu: "
        f"{residual_everywhere:.4f} contre {residual_correct:.4f} dE76 -- sinon la "
        "restriction d'EPIC5-ARB-26 n'est pas ce que le code applique")


def test_etage_m_laisse_les_neutres_invariants():
    """C'est la raison d'etre de la contrainte: `M` ne peut pas defaire sur l'axe
    neutre ce qu'`A` vient d'y fixer, donc les deux etages sont orthogonaux."""
    rng = np.random.default_rng(11)
    matrix = cc.fit_stage_m(rng.random((10, 3)), rng.random((10, 3)))
    neutral = np.array([[0.37, 0.37, 0.37]])
    assert np.abs(neutral @ matrix.T - neutral).max() < 1e-12


def test_les_valeurs_neutres_ne_contraignent_pas_l_etage_m():
    """Corollaire mesure d'`EPIC5-ARB-26`: pour un triplet neutre les deux
    regresseurs valent 0. Ajouter des neutres ne doit donc pas bouger `M`."""
    rng = np.random.default_rng(5)
    chromatic_src, chromatic_dst = rng.random((6, 3)), rng.random((6, 3))
    neutral = np.array([[0.1, 0.1, 0.1], [0.8, 0.8, 0.8]])
    without = cc.fit_stage_m(chromatic_src, chromatic_dst)
    with_neutrals = cc.fit_stage_m(np.vstack([chromatic_src, neutral]),
                                   np.vstack([chromatic_dst, neutral]))
    assert np.abs(without - with_neutrals).max() < 1e-9


def test_correction_identite_rend_un_profil_neutre():
    """Le test qui echoue si le modele est mal pose."""
    table = patch_values.active_table()
    kept, neutral = cc.adjustment_and_neutral_masks(table.adjustment_values())
    reference = np.array([[v.rgb[2], v.rgb[1], v.rgb[0]] for v in kept],
                         dtype=np.float64) / 255.0
    profile = cc.fit_correction(reference, reference, neutral)
    corrected = cc.oetf(profile.apply_linear(cc.eotf(reference)))
    assert cc.delta_e76_srgb_d65(corrected, reference).max() < 1e-6


def test_correction_recupere_une_deviation_synthetique_connue():
    """Gain, decalage et diaphonie injectes: la correction doit les defaire."""
    table = patch_values.active_table()
    kept, neutral = cc.adjustment_and_neutral_masks(table.adjustment_values())
    reference = np.array([[v.rgb[2], v.rgb[1], v.rgb[0]] for v in kept],
                         dtype=np.float64) / 255.0
    crosstalk = np.array([[0.94, 0.03, 0.03], [0.02, 0.96, 0.02], [0.04, 0.02, 0.94]])
    distorted_linear = (cc.eotf(reference) @ crosstalk.T) * 0.93 + 0.02
    measured = cc.oetf(np.clip(distorted_linear, 0.0, 1.0))

    profile = cc.fit_correction(measured, reference, neutral)
    corrected = cc.oetf(np.clip(profile.apply_linear(cc.eotf(measured)), 0.0, 1.0))
    before = cc.delta_e76_srgb_d65(measured, reference).mean()
    after = cc.delta_e76_srgb_d65(corrected, reference).mean()
    assert after < before / 3.0


# --- EPIC5-ARB-29 et AC 3c : les jeux se lisent par role --------------------

def test_le_jeu_d_ajustement_exclut_les_sentinelles_sur_le_resultat():
    """Verifie sur le **resultat** et pas seulement sur l'API appelee: un point
    ecrete par construction tirerait toute la correction."""
    table = patch_values.active_table()
    kept, neutral = cc.adjustment_and_neutral_masks(
        tuple(table.adjustment_values()) + tuple(table.sentinel_values()))
    roles = {value.role for value in kept}
    assert patch_values.ROLE_GAMUT_SENTINEL not in roles
    assert len(kept) == len(table.adjustment_values())
    assert int(neutral.sum()) == sum(
        1 for v in table.adjustment_values() if v.role == patch_values.ROLE_NEUTRAL)


def test_cardinal_du_jeu_d_ajustement_est_resolu_par_version():
    """12 pour `patch-values-1`, 10 pour `patch-values-2` (`EPIC5-ARB-17(b)`)."""
    assert len(patch_values.get_patch_values_table("patch-values-1").adjustment_values()) == 12
    assert len(patch_values.get_patch_values_table("patch-values-2").adjustment_values()) == 10


def test_aucun_nombre_de_geometrie_n_est_redeclare_ici():
    """AC 2 de 5.4b: la geometrie d'echantillonnage est **consommee**, jamais
    recopiee -- un litteral `3.0` dans cette story serait le bug, pas la valeur."""
    assert patch_presets.SAMPLED_SIDE_MM == (
        patch_presets.PATCH_SIZE_MM - 2 * patch_presets.SAMPLING_INSET_MM)
    assert not hasattr(cc, "SAMPLING_INSET_MM")
    assert not hasattr(cc, "SAMPLED_SIDE_MM")


# --- EPIC5-ARB-28 et -31 : le verdict ---------------------------------------

def test_verdict_applied_sous_les_deux_seuils():
    reference = np.array([[0.5, 0.5, 0.5], [0.3, 0.4, 0.6]])
    corrected = reference + 0.004
    raw = reference + 0.06
    verdict = cc.evaluate_acceptance(raw, corrected, reference)
    assert verdict.status == "applied"
    assert verdict.failure_reason is None
    assert verdict.acceptance_id == "color-acceptance-1"


def test_un_ecart_absolu_seul_ne_rend_plus_le_verdict_failed():
    """`EPIC5-ARB-72`, story 5.20: la distance au theorique ne bloque plus.

    Meme retournement que `test_les_seuils_absolus_sont_rapportes_mais_ne_commandent_
    plus_le_statut` cote metrique, vu du verdict de page: le triplet corrige est a plus
    de 8,0 dE76 de sa reference et le verdict est `applied`, parce que la correction
    n'a **rien deplace** -- `corrected` est aussi la mesure brute. Ce qui refuse
    desormais est le deplacement, pas la distance.
    """
    reference = np.array([[0.5, 0.5, 0.5]])
    corrected = np.array([[0.5, 0.5, 0.95]])
    verdict = cc.evaluate_acceptance(corrected, corrected, reference)
    assert verdict.mean_delta_e > 8.0
    assert verdict.status == "applied"
    assert verdict.failure_reason is None
    assert verdict.detail.acceptance_thresholds_met is False


def test_une_correction_qui_empire_la_page_est_mesuree_et_non_plus_refusee():
    """`EPIC5-ARB-31` clause 2, puis `EPIC5-ARB-78` pour sa consequence.

    Le regime est le meme qu'avant -- une correction qui **empire** la page --, et il
    reste entierement lisible: la degradation moyenne est positive, le budget est declare
    non tenu, les deux agregats se comparent. Ce qui a change est que le verdict ne
    s'en sert plus: « on ne bloque rien a cause d'un seuil etc. On informe. »
    """
    reference = np.array([[0.5, 0.5, 0.5]])
    raw = np.array([[0.505, 0.505, 0.505]])
    corrected = np.array([[0.53, 0.53, 0.53]])
    verdict = cc.evaluate_acceptance(raw, corrected, reference)
    assert verdict.status == "applied"
    assert verdict.failure_reason is None
    assert verdict.mean_delta_e > verdict.mean_delta_e_before
    assert verdict.mean_degradation_de76 > 0.0
    assert verdict.distortion_budget_met is False, (
        "le depassement reste publie: informer suppose que la mesure survive au refus")


def test_le_verdict_rapporte_ses_agregats_a_cote_du_statut():
    """Un booleen pose sur une grandeur qui vit au voisinage de son seuil bascule
    sur du bruit: le lecteur doit voir le chiffre (constat du 2026-08-10)."""
    reference = np.array([[0.5, 0.5, 0.5]])
    verdict = cc.evaluate_acceptance(reference, reference, reference)
    assert verdict.mean_delta_e == pytest.approx(0.0)
    assert verdict.max_delta_e == pytest.approx(0.0)


def test_un_value_id_duplique_est_refuse_plutot_que_de_faire_disparaitre_une_ligne():
    """Deuxieme passe de revue, `EPIC5-ARB-78` (2026-08-14).

    `evaluate_acceptance` construit ses mappings par `{key: ... for key, row in
    zip(value_ids, tableau)}` -- une cle repetee y ecrase silencieusement une ligne, et
    `color_metrics._validated` ne peut plus la voir: le mapping qu'elle recoit est deja
    ampute. Regle des fabriques (CLAUDE.md): quatre pastilles distinguables, et le
    doublon porte sur la **deuxieme et troisieme**, ni la premiere ni la derniere -- un
    refus qui ne mordrait que sur un doublon en tete ou en queue ne se demasque pas
    autrement.
    """
    value_ids = ("a-rouge", "b-vert", "b-vert", "d-bleu")
    triplets = np.array([
        [0.10, 0.15, 0.75],
        [0.20, 0.60, 0.25],
        [0.21, 0.61, 0.24],
        [0.70, 0.20, 0.10],
    ])
    with pytest.raises(cc.ColorMetricError, match="doublon|duplique"):
        cc.evaluate_acceptance(triplets, triplets, triplets, value_ids=value_ids)


def test_des_value_ids_tous_distincts_ne_declenchent_pas_le_refus_de_doublon():
    """Contre-epreuve indispensable: la garde ne doit mordre que sur un vrai doublon."""
    value_ids = ("a-rouge", "b-vert", "c-jaune", "d-bleu")
    triplets = np.array([
        [0.10, 0.15, 0.75],
        [0.20, 0.60, 0.25],
        [0.80, 0.75, 0.10],
        [0.70, 0.20, 0.10],
    ])
    verdict = cc.evaluate_acceptance(triplets, triplets, triplets, value_ids=value_ids)
    assert verdict.status == "applied"


def test_l_ecretage_n_est_pas_un_motif_d_echec():
    """`EPIC5-ARB-16`: le vocabulaire ferme des motifs ne gagne aucune valeur pour
    l'ecretage, sinon on jetterait des planches exploitables."""
    reasons = {value for name, value in vars(cc).items()
               if name.startswith("FAILURE_")}
    assert not any("clip" in reason or "ecret" in reason for reason in reasons)


def test_registre_d_acceptation_refuse_un_seuil_sous_un_de76():
    """Garde opposable aux versions futures: sous 1,0 la metrique mesurerait la
    quantification tant que `source_bit_depth` peut valoir 8."""
    with pytest.raises(ValueError, match="sous le plancher de 1.0 dE76"):
        cc.ColorAcceptance("color-acceptance-2", 0.5, 16.0)


def test_registre_d_acceptation_est_ferme_a_l_execution():
    with pytest.raises(TypeError):
        cc.COLOR_ACCEPTANCE_REGISTRY["color-acceptance-1"] = None


def test_entree_d_acceptation_inconnue_est_un_echec_explicite():
    with pytest.raises(cc.UnknownColorAcceptanceError, match="inconnue"):
        cc.get_color_acceptance("color-acceptance-42")


# --- Integration contre les vrais producteurs -------------------------------

def test_integration_contre_la_vraie_table_et_le_vrai_preset():
    """Action item 3 de la retro Epic 4: positions et valeurs viennent des **vrais**
    producteurs, jamais de fixtures recopiees ni de `SimpleNamespace`.

    Et l'assertion porte sur **chaque famille de valeurs** projetee, pas seulement
    sur un agregat: `EPIC5-ARB-39` a montre qu'un test d'integration qui n'assert
    pas par famille survit aux mutations qu'il devait attraper.
    """
    layout = patch_presets.resolve_patch_layout("tpl-a4-portrait-2f-v1", "patches-18-v2")
    preset = patch_presets.get_patch_preset("patches-18-v2")
    table = patch_values.get_patch_values_table(preset.values_version)
    placed = {patch.value_id for patch in layout}

    adjustment = {value.value_id for value in table.adjustment_values()}
    sentinels = {value.value_id for value in table.sentinel_values()}
    assert adjustment <= placed
    assert sentinels <= placed
    assert adjustment.isdisjoint(sentinels)
    # Chaque role attendu est represente, et le neutre a bien 4 niveaux en v2.
    roles = {value.role for value in table.adjustment_values()}
    assert roles == {patch_values.ROLE_NEUTRAL, patch_values.ROLE_PRIMARY,
                     patch_values.ROLE_SECONDARY}
    assert sum(1 for v in table.adjustment_values()
               if v.role == patch_values.ROLE_NEUTRAL) == 4


# --- AC 2, 3b, 8 et 9 : orchestration par page ------------------------------

#: Ecart, en codes 8 bits, entre les deux repliques d'une meme valeur dans la fabrique
#: de page. Pose a 1 code: le bruit par paires qui en resulte est de l'ordre de celui
#: mesure sur les scans reels (1,08 dE76 au scan propre, 1,29 sur le chemin PDF), et la
#: moyenne des deux repliques reste **exactement** la valeur de reference, les offsets
#: etant opposes. Une fabrique a repliques identiques rendrait le bruit nul, donc le
#: seuil d'indiscernabilite des sentinelles degenere.
_REPLICATE_OFFSET_CODES = 1.0


def _synthetic_rectified_page(template_id="tpl-a4-portrait-2f-v1",
                              preset_id="patches-18-v2", dpi=600,
                              distort=None,
                              replicate_offset_codes=None) -> np.ndarray:
    """Fabriquer une page redressee portant les pastilles a leurs vraies positions.

    Les positions viennent de `resolve_patch_layout` **reel** et les valeurs de la
    table **reelle**: c'est l'exigence d'integration de l'action item 3 de la retro
    Epic 4. Deux repetitions par valeur sont donc placees a des abscisses eloignees,
    comme sur une planche, ce qui rend la dispersion mesurable -- une page qui ne
    porterait qu'un exemplaire par valeur rendrait la regle des fabriques inoperante.

    **Refondue le 2026-08-11 (revue en trois couches).** La version precedente peignait
    chaque pastille en **aplat uniforme** et donnait la **meme** valeur aux deux
    repliques. Les trois couches ont trouve independamment ce que cela rendait
    inobservable, et c'etait la quatrieme occurrence de la regle des fabriques du
    CLAUDE.md:

    * **la geometrie d'echantillonnage**: `sample_patches` pouvait ignorer le retrait et
      mesurer les 12 mm entiers sans qu'un seul test rougisse, puisque tout le carre
      portait la meme couleur. La fabrique peint donc desormais une **couronne de
      contraste** sur les 3 mm de retrait -- ce que le retrait existe pour ne jamais
      mesurer, a savoir le bord d'encrage -- et la vraie valeur au centre seul. La
      couronne occupe 75 % de l'emprise (144 - 36 mm2): un echantillonnage qui la
      mordrait ne se tromperait pas d'un cheveu, il mesurerait autre chose. Elle n'est
      **jamais** distordue, pour que la distorsion appliquee reste attribuable;
    * **le bruit inter-repliques**: les deux repliques d'une valeur recoivent des
      offsets **opposes** de `_REPLICATE_OFFSET_CODES`, donc leur moyenne reste
      exactement la valeur de reference (l'agregation H4 est verifiable) tandis que le
      bruit de mesure devient non nul et realiste -- l'ordre de grandeur mesure sur les
      scans reels est 1,08 dE76. Sans lui, le seuil d'indiscernabilite des sentinelles
      est degenere et le verdict d'ecretage n'est pas calculable.
    """
    from mixed_media_utility import page_templates, scan_detection

    geometry = scan_detection.resolve_page_geometry(template_id, dpi)
    width, height = geometry["page_size_px"]
    page = np.full((height, width, 3), 255, dtype=np.uint8)
    table = patch_values.get_patch_values_table(
        patch_presets.get_patch_preset(preset_id).values_version)
    reference = {value.value_id: value.rgb for value in table.values}
    seen: dict[str, int] = {}
    for patch in patch_presets.resolve_patch_layout(template_id, preset_id):
        replicate = seen.get(patch.value_id, 0)
        seen[patch.value_id] = replicate + 1
        rgb = np.asarray(reference[patch.value_id], dtype=np.float64) / 255.0
        bgr = rgb[::-1] if distort is None else distort(rgb[::-1])
        # Offsets opposes: +delta sur la premiere replique, -delta sur la seconde, donc
        # la moyenne par valeur est exacte et le bruit par paires ne l'est pas.
        signed = 1.0 if replicate % 2 == 0 else -1.0
        offset = (_REPLICATE_OFFSET_CODES if replicate_offset_codes is None
                  else replicate_offset_codes)
        bgr = np.clip(bgr + signed * offset / 255.0, 0.0, 1.0)
        x0, y0 = page_templates.mm_to_px(patch.x_mm, patch.y_mm, dpi)
        x1, y1 = page_templates.mm_to_px(
            patch.x_mm + patch.size_mm, patch.y_mm + patch.size_mm, dpi)
        # Couronne de contraste sur toute l'emprise, puis la vraie valeur au centre.
        page[y0:y1, x0:x1] = np.clip(
            (1.0 - bgr) * 255.0, 0, 255).round().astype(np.uint8)
        # La couronne est peinte d'apres les constantes de `patch_presets`, qui
        # decrivent **l'impression**, et non d'apres `cc.sampled_square_mm`, qui est la
        # fonction sous test. Les appeler ici rendrait la fabrique tautologique: une
        # mutation qui ferait mesurer les 12 mm entiers deplacerait *aussi* la peinture,
        # et la page resterait mesuree juste. Verifie en mutant (0, size): le test de
        # page tombe desormais.
        inset = patch_presets.SAMPLING_INSET_MM
        side = patch_presets.SAMPLED_SIDE_MM
        cx0, cy0 = page_templates.mm_to_px(
            patch.x_mm + inset, patch.y_mm + inset, dpi)
        cx1, cy1 = page_templates.mm_to_px(
            patch.x_mm + inset + side, patch.y_mm + inset + side, dpi)
        page[cy0:cy1, cx0:cx1] = np.clip(
            bgr * 255.0, 0, 255).round().astype(np.uint8)
    return page


def test_page_identite_rend_applied_et_une_correction_neutre():
    page = _synthetic_rectified_page()
    result = cc.calibrate_page(page, template_id="tpl-a4-portrait-2f-v1",
                               patch_preset_id="patches-18-v2", dpi=600)
    assert result.status == "applied"
    assert result.failure_reason is None
    assert result.profile is not None
    assert result.acceptance.mean_delta_e < 1.0
    assert result.values_version == "patch-values-2"


def test_page_recupere_une_distorsion_et_reste_applied():
    def distort(bgr):
        return np.clip(cc.oetf(cc.eotf(bgr) * 0.92 + 0.03), 0.0, 1.0)

    page = _synthetic_rectified_page(distort=distort)
    result = cc.calibrate_page(page, template_id="tpl-a4-portrait-2f-v1",
                               patch_preset_id="patches-18-v2", dpi=600)
    assert result.status == "applied"
    assert result.acceptance.mean_delta_e < result.acceptance.mean_delta_e_before


def test_preset_inconnu_est_un_echec_motive_sans_correction():
    page = _synthetic_rectified_page()
    result = cc.calibrate_page(page, template_id="tpl-a4-portrait-2f-v1",
                               patch_preset_id="patches-999-v9", dpi=600)
    assert result.status == "failed"
    assert result.failure_reason == cc.FAILURE_UNKNOWN_PATCH_PRESET
    assert result.profile is None


def test_pastilles_hors_bornes_plausibles_echouent():
    """Une page uniformement noire n'est pas une page de pastilles: c'est un
    echantillonnage qui a manque sa cible."""
    from mixed_media_utility import scan_detection
    geometry = scan_detection.resolve_page_geometry("tpl-a4-portrait-2f-v1", 600)
    width, height = geometry["page_size_px"]
    result = cc.calibrate_page(np.zeros((height, width, 3), np.uint8),
                               template_id="tpl-a4-portrait-2f-v1",
                               patch_preset_id="patches-18-v2", dpi=600)
    assert result.status == "failed"
    assert result.failure_reason == cc.FAILURE_PATCHES_OUT_OF_RANGE


def test_dispersion_inter_repliques_est_rapportee_et_peut_faire_echouer():
    """AC 3b et reponse (c) d'Egan: seuil dur **et** valeur rapportee.

    L'assertion portait sur `== 0.0` tant que la fabrique donnait la meme valeur aux
    deux repliques -- elle constatait donc que rien ne varie sur des donnees ou rien ne
    pouvait varier. Elle porte desormais sur l'ecart **reellement introduit** par la
    fabrique, ce qui la rend sensible: une dispersion rendue nulle, ou moyennee au lieu
    d'etre maximisee, la fait tomber.
    """
    page = _synthetic_rectified_page()
    result = cc.calibrate_page(page, template_id="tpl-a4-portrait-2f-v1",
                               patch_preset_id="patches-18-v2", dpi=600)
    assert result.replicate_dispersion_de76 > 0.0, (
        "la fabrique introduit un ecart entre repliques: une dispersion nulle veut "
        "dire que la grandeur n'est pas calculee")
    # Dispersion et bruit sont **deux statistiques distinctes** sur les memes donnees,
    # et les confondre etait le bloquant B2. A deux repliques, l'ecart a la moyenne vaut
    # **la moitie** de l'ecart par paires, a la non-linearite du Lab pres: la moyenne
    # est prise dans le domaine encode, donc elle n'est pas le milieu en Lab. L'ecart
    # mesure est de 2 % sur la plupart des valeurs et culmine sur `neutral-020`, la ou
    # `L*` est le plus raide -- d'ou une tolerance relative de 5 % et non une egalite.
    # La relation ne vaut pas non plus entre les deux **agregats**, l'un etant un
    # maximum et l'autre une mediane: ce test verrouille aussi cette distinction.
    # Mesure par le vrai `sample_patches`, qu'aucun test n'appelait jusqu'ici.
    layout = patch_presets.resolve_patch_layout(
        "tpl-a4-portrait-2f-v1", "patches-18-v2")
    measured, ids = cc.sample_patches(page, layout, 600)
    worst, detail = cc.replicate_dispersion(measured, ids)
    assert worst == pytest.approx(result.replicate_dispersion_de76)
    for value_id in detail:
        rows = np.asarray([row for row, vid in zip(measured, ids) if vid == value_id])
        assert len(rows) == 2, "la fabrique doit poser deux repliques par valeur"
        pairwise = float(cc.delta_e76_srgb_d65(rows[0], rows[1]))
        assert detail[value_id] == pytest.approx(pairwise / 2.0, rel=0.05), (
            f"{value_id}: l'ecart a la moyenne doit valoir la moitie de l'ecart "
            "par paires")
    noise = cc.measurement_noise_de76(measured, ids)
    assert worst > noise / 2.0, (
        "l'agregat de dispersion est un MAXIMUM et le bruit une MEDIANE: les "
        "confondre revient a calibrer un seuil sur une autre statistique que celle "
        "qu'il compare")
    assert cc.MAX_REPLICATE_DISPERSION_DE76 > 1.29, (
        "le seuil doit rester au-dessus du bruit inter-repliques mesure sur papier")


def test_la_garde_de_dispersion_mord_reellement():
    """Finding majeur de la couche 2: **la couche de refus etait morte.**

    Le seuil n'etait epingle que par `MAX_REPLICATE_DISPERSION_DE76 > 1.29`, donc le
    porter de 5,0 a 500,0 laissait tous les tests verts -- aucune page ne le franchissait
    jamais. Ici la fabrique pose un ecart entre repliques assez grand pour le franchir,
    et le refus doit tomber avec son motif.
    """
    page = _synthetic_rectified_page(replicate_offset_codes=13.0)
    result = cc.calibrate_page(page, template_id="tpl-a4-portrait-2f-v1",
                               patch_preset_id="patches-18-v2", dpi=600)
    assert result.status == "failed"
    assert result.failure_reason == cc.FAILURE_REPLICATE_DISPERSION
    assert result.replicate_dispersion_de76 > cc.MAX_REPLICATE_DISPERSION_DE76, (
        "la valeur qui a fait echouer la page doit etre rapportee: reponse (c) "
        "d'Egan, seuil dur ET valeur")
    assert result.profile is None
    # Le verdict d'ecretage survit au refus: il repond a une autre question
    # (`EPIC5-ARB-16`), et les quatre combinaisons doivent rester representables.
    assert result.clipping is not None


def test_une_dispersion_non_mesurable_n_est_pas_publiee_a_zero():
    """Finding majeur des couches 2 et 3: `0.0` est la valeur d'une page **parfaite**.

    Publier zero pour « non mesure » affiche la meilleure lecture possible la ou rien
    n'a ete lu. Une valeur vue une seule fois n'a pas une dispersion nulle, elle n'en a
    pas -- et l'absence de mesure ne doit pas non plus declencher le refus, qui porte
    sur une dispersion mesuree et trop haute.
    """
    measured = np.array([[0.4, 0.5, 0.6], [0.7, 0.2, 0.3]])
    worst, detail = cc.replicate_dispersion(measured, ("seule-a", "seule-b"))
    assert worst is None
    assert detail == {}


def test_un_placement_non_defini_est_un_echec_motive_et_non_une_exception(monkeypatch):
    """Finding majeur de la couche 2: `UndefinedPlacementError` traversait
    `calibrate_page`, **hors** du vocabulaire de l'AC 8, la ou toutes les autres causes
    rendent un resultat motive.

    Le cas devient courant depuis le versionnement de la geometrie de page du
    2026-08-11: un `template_id` d'une version dont les colonnes ne sont pas encore
    placees tombe exactement ici.

    Aucun couple (template, preset) n'est non couvert **aujourd'hui** en production:
    le chemin s'atteint donc en faisant lever la resolution, ce qui verifie le
    traitement et non l'atteignabilite. Celle-ci viendra avec la premiere version de
    geometrie ajoutee, et le test de `page_templates` qui verrouille l'echec bruyant de
    `resolve_patch_layout` en est le pendant.
    """
    def refuse(template_id, preset_id):
        raise patch_presets.UndefinedPlacementError(
            f"aucun placement pour ({template_id}, {preset_id})")

    # La page se fabrique **avant** le monkeypatch: la fabrique consomme elle aussi
    # `resolve_patch_layout` pour savoir ou peindre.
    page = _synthetic_rectified_page()
    monkeypatch.setattr(patch_presets, "resolve_patch_layout", refuse)
    result = cc.calibrate_page(page, template_id="tpl-a4-portrait-2f-v1",
                               patch_preset_id="patches-18-v2", dpi=600)
    assert result.status == "failed"
    assert result.failure_reason == cc.FAILURE_PLACEMENT_UNDEFINED
    assert result.profile is None


def test_etage_m_refuse_un_seul_point_au_lieu_de_rendre_l_identite():
    """Symetrique de la garde de `fit_stage_a`, qui manquait (couche 2).

    Deux regresseurs libres par ligne: un seul point les laisse indetermines et `lstsq`
    rend la solution de norme minimale, c'est-a-dire **l'identite** -- une matrice
    d'apparence parfaitement valide qui ne corrige rien.
    """
    with pytest.raises(ValueError, match="deux au minimum"):
        cc.fit_stage_m(np.array([[0.4, 0.5, 0.6]]), np.array([[0.45, 0.5, 0.55]]))


def test_un_jeu_d_ajustement_sous_determine_est_declare_et_non_leve():
    """`EPIC5-ARB-29` clause 5: le cas indetermine doit avoir un **verdict**.

    Il remontait en `ValueError` nue depuis `fit_stage_a`, donc hors du vocabulaire de
    l'AC 8 -- une page qui ne peut pas etre corrigee doit le declarer comme toutes les
    autres causes, sinon l'appelant voit une exception la ou il attend un resultat.
    """
    page = _synthetic_rectified_page()
    table = patch_values.active_table()

    class OneNeutral:
        """Table dont l'axe neutre ne porte qu'une valeur: `A` est indetermine."""
        version = table.version

        def __getattr__(self, name):
            return getattr(table, name)

        def adjustment_values(self):
            values = list(table.adjustment_values())
            neutrals = [v for v in values if v.role == patch_values.ROLE_NEUTRAL]
            others = [v for v in values if v.role != patch_values.ROLE_NEUTRAL]
            return tuple(neutrals[:1] + others)

    import unittest.mock as mock
    with mock.patch.object(patch_values, "get_patch_values_table",
                           return_value=OneNeutral()):
        result = cc.calibrate_page(page, template_id="tpl-a4-portrait-2f-v1",
                                   patch_preset_id="patches-18-v2", dpi=600)
    assert result.status == "failed"
    assert result.failure_reason == cc.FAILURE_UNDERDETERMINED_ADJUSTMENT
    assert result.profile is None


@pytest.mark.parametrize("dpi", [600.5, 0, -1, True, "600"])
def test_un_dpi_invalide_est_declare_et_non_consomme(dpi):
    """Finding mineur de la couche 2: `dpi` n'etait pas valide.

    Il gouverne **toutes** les conversions en millimetres vers pixels, donc un dpi non
    entier decale le carre echantillonne d'une fraction de pixel a chaque bord, sans
    lever d'erreur -- et un dpi negatif produisait des tranches vides.
    `True` est refuse explicitement: `isinstance(True, int)` est vrai en Python, et la
    garde bool-avant-int est une convention du depot (`numeric_guards`).
    """
    page = _synthetic_rectified_page()
    result = cc.calibrate_page(page, template_id="tpl-a4-portrait-2f-v1",
                               patch_preset_id="patches-18-v2", dpi=dpi)
    assert result.status == "failed"
    assert result.failure_reason == cc.FAILURE_INVALID_DPI


#: Le vocabulaire ferme des motifs d'echec (AC 8 de 5.4b). `FAILURE_DISTORTION_BUDGET`
#: y a ete **ajoute le 2026-08-19** (finding de la revue de 5.20): il en fait partie
#: depuis la story 5.20 et n'etait nomme par aucune assertion, donc renommable sans
#: qu'un test le voie -- exactement le defaut que ce test existe pour fermer.
MOTIFS_D_ECHEC_DU_VOCABULAIRE_FERME = (
    "FAILURE_PATCHES_NOT_FOUND", "FAILURE_PATCHES_OUT_OF_RANGE",
    "FAILURE_REPLICATE_DISPERSION", "FAILURE_UNKNOWN_PATCH_PRESET",
    "FAILURE_UNKNOWN_VALUES_VERSION", "FAILURE_UNKNOWN_GAMUT_MAP",
    "FAILURE_PLACEMENT_UNDEFINED", "FAILURE_UNDERDETERMINED_ADJUSTMENT",
    "FAILURE_INVALID_DPI", "FAILURE_DEGRADES_RESIDUAL", "FAILURE_METRIC",
    "FAILURE_DISTORTION_BUDGET",
)


@pytest.mark.parametrize("reason", MOTIFS_D_ECHEC_DU_VOCABULAIRE_FERME)
def test_chaque_motif_d_echec_est_nomme_et_distinct(reason):
    """Finding majeur de la couche 3: **cinq motifs sur huit n'etaient nommes par
    aucune assertion**, donc renommables sans qu'un test le voie -- alors que le
    vocabulaire d'echec est ce que le manifest publie et ce qu'un operateur lit.
    """
    value = getattr(cc, reason)
    assert isinstance(value, str) and value, f"{reason} doit etre une chaine non vide"
    others = {getattr(cc, name) for name in MOTIFS_D_ECHEC_DU_VOCABULAIRE_FERME
              if name != reason}
    assert value not in others, f"{reason} collisionne avec un autre motif"
    # L'ecretage n'est PAS un motif d'echec et ne le sera jamais (`EPIC5-ARB-16`).
    assert "clip" not in value and "ecret" not in value


def test_les_trois_motifs_informatifs_restent_definis_et_n_ont_plus_aucun_emetteur():
    """Finding de la revue de 5.20 (ferme le 2026-08-19), avec sa premisse deplacee.

    La revue demandait que `FAILURE_DISTORTION_BUDGET` entre au test de vocabulaire
    ferme « alors qu'il est desormais le motif qui decide ». Il ne decide plus:
    `EPIC5-ARB-78` a rendu les deux clauses du budget **informatives** et
    `EPIC5-ARB-72` avait deja retire son pouvoir a `FAILURE_METRIC`. La propriete a
    epingler n'est donc pas « il decide » mais son contraire, et c'est elle qu'aucun
    test ne portait: les trois motifs restent **definis** -- ils appartiennent au
    vocabulaire ferme de l'AC 8 de 5.4b et figurent dans des manifests deja ecrits --
    et ne sont **emis par personne**.

    Sans ce test, les deux sens du fait sont perdus a la fois: les retirer casserait la
    relecture des manifests anciens, et les reemettre reintroduirait un jugement de
    couleur bloquant, ce que l'arbitrage retire explicitement.
    """
    import ast
    import inspect

    informatifs = {
        "FAILURE_METRIC": "acceptance_metric_failed",
        "FAILURE_DEGRADES_RESIDUAL": "correction_degrades_residual",
        "FAILURE_DISTORTION_BUDGET": "correction_distortion_exceeds_budget",
    }
    # Definis, et a leur valeur exacte -- ecrite en litteral, parce que c'est cette
    # chaine-la qui est deja dans les manifests produits.
    for nom, chaine in informatifs.items():
        assert getattr(cc, nom) == chaine
        assert getattr(cm, nom) == chaine
        assert nom in MOTIFS_D_ECHEC_DU_VOCABULAIRE_FERME

    # Et sans emetteur: aucune affectation de ces constantes a un `failure_reason`, ni
    # aucun passage en argument nomme, dans les deux modules qui les portent. La lecture
    # passe par l'AST plutot que par un `grep`, pour ne dependre ni de l'espacement ni
    # du nom du module a l'appel.
    for module in (cc, cm):
        arbre = ast.parse(inspect.getsource(module))
        for noeud in ast.walk(arbre):
            emis = None
            if isinstance(noeud, ast.keyword) and noeud.arg in (
                    "failure_reason", "not_applied_reason", "reason"):
                emis = noeud.value
            elif isinstance(noeud, ast.Assign) and any(
                    isinstance(cible, ast.Name)
                    and cible.id in ("failure_reason", "reason")
                    for cible in noeud.targets):
                emis = noeud.value
            if emis is None:
                continue
            nom = emis.id if isinstance(emis, ast.Name) else (
                emis.attr if isinstance(emis, ast.Attribute) else None)
            assert nom not in informatifs, (
                f"{module.__name__}:{noeud.lineno}: {nom} est emis comme motif alors "
                "qu'`EPIC5-ARB-78` l'a rendu informatif")

    # Le temoin: la lecture ci-dessus **voit** bien un emetteur quand il y en a un.
    # Sans lui, une boucle qui ne trouverait jamais rien passerait aussi.
    emetteurs = []
    for module in (cc, cm):
        for noeud in ast.walk(ast.parse(inspect.getsource(module))):
            if isinstance(noeud, ast.keyword) and noeud.arg == "failure_reason" and \
                    isinstance(noeud.value, ast.Name):
                emetteurs.append(noeud.value.id)
    assert emetteurs, "aucun `failure_reason=<Name>` trouve: la lecture ne voit rien"


def test_un_echec_porte_encore_la_forme_de_correction_et_l_entree_de_seuils():
    """Finding de la revue de 5.4a, verse au `deferred-work` et repris ici.

    Sur une page `failed`, `profile` et `acceptance` valent tous deux `None`: ni la
    forme de correction tentee ni l'entree d'acceptation ne survivaient. Un echec dont
    on ne sait pas contre quoi il a echoue n'est pas relisable -- et c'est precisement
    le cas ou on relit.
    """
    page = _synthetic_rectified_page()
    ok = cc.calibrate_page(page, template_id="tpl-a4-portrait-2f-v1",
                           patch_preset_id="patches-18-v2", dpi=600)
    ko = cc.calibrate_page(page, template_id="tpl-a4-portrait-2f-v1",
                           patch_preset_id="patches-999-v9", dpi=600)
    assert ko.status == "failed" and ko.profile is None
    # **La forme portee est celle qui a ete tentee**, donc la forme active depuis la
    # bascule de la story 5.21 -- et l'attendu suit le defaut plutot que de le figer:
    # ce test porte sur la survie de l'identifiant a travers un echec, pas sur la valeur
    # de cet identifiant. L'egalite entre les deux appels est la moitie qui compte: un
    # echec doit declarer la meme forme que le succes obtenu au meme appel.
    assert ko.correction_form_id == ok.correction_form_id == cc.ACTIVE_CORRECTION_FORM_ID
    assert cc.ACTIVE_CORRECTION_FORM_ID != cc.CORRECTION_FORM_ID
    assert ko.acceptance_id == ok.acceptance_id == "color-acceptance-1"


@pytest.mark.parametrize("preset_id, expected_values", [
    ("patches-18-v2", "patch-values-2"),
    ("patches-12-v1", "patch-values-1"),
    ("patches-9-v1", "patch-values-1"),
    ("patches-14-v3", "patch-values-3"),
])
def test_les_quatre_presets_livres_se_calibrent_dont_le_defaut_de_la_cli(
        preset_id, expected_values):
    """Finding majeur de la couche 1: **un seul preset etait couvert**, et ce n'etait
    pas celui de la ligne de commande.

    `pdf_composition.DEFAULT_PATCH_PRESET` est le preset que toute planche produite sans
    `--nombre-patchs` porte, et **il a change avec `EPIC5-ARB-67`**: `patches-14-v3` au
    lieu de `patches-12-v1`. Le parametrage couvre donc les **quatre** presets du
    registre, dont les deux tables extremes: `patch-values-1` n'a aucune sentinelle -- le
    verdict d'ecretage n'y est pas calculable, ce qui est precisement ce qui a fait
    basculer le defaut -- et `patch-values-3` les porte toutes.

    L'assertion de fin ne recopie plus la table attendue du defaut: elle exige que le
    defaut soit **couvert par ce parametrage** et qu'il rende un verdict d'ecretage. Un
    defaut qui repasserait sur une table sans sentinelle ferait echouer ce test, ce qui
    est le sens de l'arbitrage.
    """
    from mixed_media_utility import pdf_composition

    page = _synthetic_rectified_page(preset_id=preset_id)
    result = cc.calibrate_page(page, template_id="tpl-a4-portrait-2f-v1",
                               patch_preset_id=preset_id, dpi=600)
    assert result.status == "applied", (
        f"{preset_id}: {result.failure_reason}")
    assert result.values_version == expected_values
    assert result.patch_preset_id == preset_id
    if expected_values == "patch-values-1":
        # Aucune sentinelle: le verdict n'est pas calculable, et il ne doit pas etre
        # publie comme un « aucun ecretage detecte ».
        assert result.clipping is None, (
            "sans sentinelle, le verdict d'ecretage n'est pas calculable: publier "
            "`detected: false` affirmerait une absence jamais mesuree")
    else:
        assert result.clipping is not None
    if preset_id == pdf_composition.DEFAULT_PATCH_PRESET:
        # Le defaut de la CLI est **dans** ce parametrage, et il rend un verdict
        # d'ecretage: c'est la propriete qu'`EPIC5-ARB-67` a achetee, et elle etait
        # fausse de l'ancien defaut.
        assert result.clipping is not None, (
            "le preset compose par defaut doit rendre le verdict d'ecretage calculable "
            "(EPIC5-ARB-67): sans sentinelle, la calibration ne peut pas fonctionner")


def test_le_diagnostic_est_rapporte_par_canal_et_ne_decide_rien():
    page = _synthetic_rectified_page()
    result = cc.calibrate_page(page, template_id="tpl-a4-portrait-2f-v1",
                               patch_preset_id="patches-18-v2", dpi=600)
    assert result.channel_relative_deviation_before_correction is not None
    assert len(result.channel_relative_deviation_before_correction) == 3


def test_les_avertissements_d_entree_sont_transportes_et_ne_refusent_rien():
    """`EPIC5-ARB-47`: le PDF degrade reste accepte, ce qui change est la tracabilite."""
    page = _synthetic_rectified_page()
    result = cc.calibrate_page(page, template_id="tpl-a4-portrait-2f-v1",
                               patch_preset_id="patches-18-v2", dpi=600,
                               input_warnings=("PDF_EMBEDS_LOSSY_IMAGE",))
    assert result.status == "applied"
    assert result.input_warnings == ("PDF_EMBEDS_LOSSY_IMAGE",)


# --- AC 9 : le verdict d'ecretage, orthogonal au statut ----------------------

def test_les_chaines_de_sentinelles_ont_toutes_une_tete_in_gamut():
    """Le bug attrape le 2026-08-10: le noir et le blanc sortaient **sans tete**,
    donc sans le couple in-gamut/mediane, et le verdict devenait incalculable sans
    qu'aucune erreur soit levee."""
    chains = cc.sentinel_chains(patch_values.active_table())
    assert set(chains) == {"primary-red", "primary-green", "primary-blue",
                           "neutral-020", "neutral-245"}
    for head, chain in chains.items():
        assert chain[0] == head and len(chain) >= 2


def test_aucune_chaine_sur_une_table_sans_sentinelle():
    """`patch-values-1` n'en porte aucune: le verdict y est NON CALCULABLE, et c'est
    le constat de la revue de 5.4a -- il se ferme par un tirage, pas par du code."""
    assert cc.sentinel_chains(patch_values.get_patch_values_table("patch-values-1")) == {}


def test_ecretage_et_statut_sont_independants():
    """`EPIC5-ARB-16`: les quatre combinaisons sont representables. Ici une page dont
    la correction converge **et** dont une chaine est indiscernable doit rendre
    `applied` **et** l'avertissement."""
    def flatten_black(bgr):
        # On ecrase la chaine du noir: neutral-020 et sentinel-black-1 deviennent
        # indiscernables, sans toucher au reste de la page.
        return np.array([0.08, 0.08, 0.08]) if bgr.max() < 0.1 else bgr

    page = _synthetic_rectified_page(distort=flatten_black)
    result = cc.calibrate_page(page, template_id="tpl-a4-portrait-2f-v1",
                               patch_preset_id="patches-18-v2", dpi=600)
    assert result.status == "applied"
    assert result.clipping["detected"] is True
    assert "neutral-020" in result.clipping["axes"]
    assert result.clipping["per_axis"]["neutral-020"]["clipped"] is True
    assert result.failure_reason is None


def test_l_echelle_se_deduit_du_type_et_non_d_une_egalite_de_dtype():
    """Verrou de la couche basse du cas gros-boutien, teste **sans** passer par
    `color_pipeline`, dont la normalisation d'ordre des octets masquerait le defaut.

    `np.dtype(">u2") == np.uint16` est **faux** sur une machine petit-boutienne. Une
    echelle deduite par egalite de dtype vaut donc 255 pour un scan 16 bits en ordre
    `MM`, et l'image sort saturee a blanc: plausible et fausse. L'echelle se deduit du
    **type entier** et de son maximum.
    """
    neutral = cc.CorrectionProfile(
        stage_a=np.array([[1.0, 0.0], [1.0, 0.0], [1.0, 0.0]]), stage_m=np.eye(3))
    big_endian = np.full((2, 2, 3), 32768, dtype=">u2")
    assert big_endian.dtype != np.uint16, "le cas n'a d'interet qu'en ordre MM"
    out = cc.apply_profile_to_image(big_endian, neutral)
    assert out.max() < 0.99, f"gris a mi-echelle sorti sature: {out.max()}"
    # Et les deux ordres d'octets doivent rendre exactement la meme chose.
    assert out == pytest.approx(
        cc.apply_profile_to_image(big_endian.astype(np.uint16), neutral), abs=1e-12)


def test_un_flottant_hors_bornes_est_refuse_plutot_que_reechelonne():
    """L'autre moitie du meme defaut: un flottant **deja normalise** etait divise par
    255, donc traite comme un quasi-noir -- silencieusement, et c'etait le cas d'appel
    le plus naturel depuis ce module, ou tout travaille en flottant normalise."""
    neutral = cc.CorrectionProfile(
        stage_a=np.array([[1.0, 0.0], [1.0, 0.0], [1.0, 0.0]]), stage_m=np.eye(3))
    normalised = np.full((2, 2, 3), 0.5, dtype=np.float64)
    out = cc.apply_profile_to_image(normalised, neutral)
    assert out == pytest.approx(normalised, abs=1e-12), (
        "un flottant normalise doit traverser une correction neutre inchange")
    with pytest.raises(ValueError, match="deja normalise"):
        cc.apply_profile_to_image(np.full((2, 2, 3), 128.0), neutral)


def test_la_correction_ajustee_sur_une_page_ne_permute_pas_les_canaux():
    """Bloquant B1: le point unique RGB->BGR n'etait verrouille par **rien**.

    Les trois couches de la revue du 2026-08-11 l'ont trouve independamment. Retirer le
    `[::-1]` qui reordonne la reference passait les 3 039 tests du depot: le residu ne
    peut pas le voir, parce que l'ajustement **compense** l'inversion en rendant une
    `stage_m` egale a la matrice de permutation. La page sort alors `applied` avec
    `mean_delta_e = 0,0000` -- et tout rouge sort bleu.

    Le verrou ne peut donc pas porter sur le residu. Il porte sur le **sens de la
    couleur**: une correction ajustee sur une page fidele, appliquee a un rouge sature,
    doit rendre un rouge. C'est le seul enonce qu'une permutation ne satisfait pas.
    """
    page = _synthetic_rectified_page()
    result = cc.calibrate_page(page, template_id="tpl-a4-portrait-2f-v1",
                               patch_preset_id="patches-18-v2", dpi=600)
    assert result.profile is not None
    # Rouge sature, en BGR encode normalise comme tout le chemin de correction.
    red_bgr = np.array([[[0.05, 0.05, 0.90]]], dtype=np.float64)
    out = cc.apply_profile_to_image(red_bgr, result.profile)
    blue, green, red = out[0, 0]
    assert red > green and red > blue, (
        f"un rouge corrige doit rester rouge, obtenu BGR={out[0, 0]} -- une "
        "permutation des canaux rend ici un bleu tout en affichant un residu nul")
    # Et symetriquement sur le bleu, faute de quoi un test qui ne verifierait qu'un
    # seul canal passerait avec une permutation qui echange les deux autres.
    blue_bgr = np.array([[[0.90, 0.05, 0.05]]], dtype=np.float64)
    out_blue = cc.apply_profile_to_image(blue_bgr, result.profile)
    assert out_blue[0, 0][0] > out_blue[0, 0][2], (
        f"un bleu corrige doit rester bleu, obtenu BGR={out_blue[0, 0]}")


def test_la_forme_du_verdict_d_ecretage_est_celle_que_le_schema_exige():
    """Bloquant B5 de la revue du 2026-08-11: un manifest ecrit sur l'ancienne forme
    etait **invalide**.

    Le schema livre par la story 5.7 rend `clipping.detected` obligatoire et donne
    `onset_step` de type `string | null`. La forme rendue etait un dictionnaire par
    axe, sans `detected`, et portait un **entier** de rang d'echelon dont le 0 --
    « l'indiscernabilite commence des le couple in-gamut/mediane » -- est precisement
    le cas que le schema demande de coder `null`.
    """
    import json
    from pathlib import Path

    schema = json.loads(
        (Path(__file__).resolve().parents[2]
         / "src/mixed_media_utility/specs/project.schema.json").read_text())
    declared = (schema["properties"]["reconstruction"]["properties"]
                ["page_calibration_results"]["items"]["properties"]["clipping"])

    page = _synthetic_rectified_page()
    result = cc.calibrate_page(page, template_id="tpl-a4-portrait-2f-v1",
                               patch_preset_id="patches-18-v2", dpi=600)
    for key in declared["required"]:
        assert key in result.clipping, f"cle requise au schema absente: {key}"
    assert isinstance(result.clipping["detected"], bool)
    assert isinstance(result.clipping["axes"], list)
    assert result.clipping["onset_step"] is None or isinstance(
        result.clipping["onset_step"], str), (
        "onset_step est l'identifiant d'un echelon, pas son rang")


def test_un_ecretage_precoce_rend_onset_step_null_et_non_zero():
    """La semantique inversee de `onset_step`, verrouillee par une mesure.

    Quand l'indiscernabilite commence des le **premier** couple (in-gamut/mediane),
    l'ecretage est plus precoce que l'echelon median et la localisation s'arrete la:
    le schema veut `null`. L'ancien code y ecrivait `0`, qu'un lecteur interprete
    naturellement comme « premier echelon », soit l'inverse.
    """
    def flatten_black(bgr):
        return np.array([0.08, 0.08, 0.08]) if bgr.max() < 0.1 else bgr

    page = _synthetic_rectified_page(distort=flatten_black)
    result = cc.calibrate_page(page, template_id="tpl-a4-portrait-2f-v1",
                               patch_preset_id="patches-18-v2", dpi=600)
    axis = result.clipping["per_axis"]["neutral-020"]
    assert axis["onset_index"] == 0, "l'ecrasement porte sur le premier couple"
    assert axis["onset_value_id"] is None
    assert result.clipping["onset_step"] is None


def test_le_verdict_d_ecretage_porte_son_ecart_et_son_seuil():
    """Constat du 2026-08-10: un booleen pose sur une grandeur au voisinage de son
    seuil bascule sur du bruit; le lecteur doit voir les deux nombres."""
    page = _synthetic_rectified_page()
    result = cc.calibrate_page(page, template_id="tpl-a4-portrait-2f-v1",
                               patch_preset_id="patches-18-v2", dpi=600)
    entry = result.clipping["per_axis"]["primary-red"]
    assert "gaps_de76" in entry and "threshold_de76" in entry
    assert entry["threshold_de76"] > 0.0, (
        "un seuil nul rend le verdict equivalent a une egalite bit a bit")


def test_sans_bruit_estimable_le_verdict_d_ecretage_est_indisponible():
    """Bloquant B2: le seuil est proportionnel au bruit, donc un bruit nul le degenere.

    Une page dont les repliques sont identiques n'a pas un bruit « nul », elle a un
    bruit **non estimable**. L'ancien code y substituait un plancher de 1,0 dE76
    invente, ni arbitre ni teste. Ici le verdict sort `unavailable` -- pas
    `clipped: False`, qui affirmerait une absence d'ecretage jamais mesuree.
    """
    page = _synthetic_rectified_page(replicate_offset_codes=0.0)
    result = cc.calibrate_page(page, template_id="tpl-a4-portrait-2f-v1",
                               patch_preset_id="patches-18-v2", dpi=600)
    assert result.clipping is None, (
        "aucun axe n'etant mesurable, la cle n'est pas ecrite du tout: la story 5.7 "
        "tient la meme regle -- ecrire {detected: false} sans avoir mesure serait "
        "affirmer une absence d'ecretage")


# --- AC 5 : application aux frames, puis G^-1 -------------------------------

def test_application_aux_frames_fait_c_puis_g_inverse():
    page = _synthetic_rectified_page()
    result = cc.calibrate_page(page, template_id="tpl-a4-portrait-2f-v1",
                               patch_preset_id="patches-18-v2", dpi=600)
    zone = np.full((8, 8, 3), 128, dtype=np.uint8)
    out, clipping = cc.apply_correction_to_frames(zone, result.profile,
                                                  "gamut-map-none-1")
    assert out.shape == zone.shape
    assert 0.0 <= out.min() and out.max() <= 1.0
    assert clipping.component_count == out.size


def test_l_ecretage_de_l_expansion_est_compte_par_borne_sur_le_letterbox_papier():
    """`EPIC5-ARB-30` clause 4, que le code n'implementait pas (couches 1 et 3).

    Le cas de l'arbitrage, reproduit: les bandes de letterbox d'un rush 2.35:1 posees
    dans une zone 16:9 sont **a l'interieur** d'`image_rect_mm`, donc dans la zone frame,
    et elles sont en **papier nu** -- `drawImage` n'y ecrit aucun fond. Ces pixels n'ont
    jamais subi `G`, donc `G^-1` les envoie au-dessus de 1. Sans comptage, le seul
    signal etait l'image elle-meme, et l'arbitrage chiffre ce qu'elle devient: sans
    ecretage, `1,0114` replie par `astype(uint16)` donne **743**, du quasi-noir. Les
    bandes blanches deviendraient noires, « une image plausible », sans exception et
    sans `failed` -- la metrique ne voit rien, elle porte sur les pastilles.
    """
    neutral = cc.CorrectionProfile(
        stage_a=np.array([[1.0, 0.0], [1.0, 0.0], [1.0, 0.0]]), stage_m=np.eye(3))
    # Une zone dont les deux premieres lignes sont du papier nu et le reste du contenu:
    # la fabrique est **heterogene**, sinon on ne saurait pas si le comptage porte sur
    # les bons pixels.
    zone = np.full((4, 3, 3), 128, dtype=np.uint8)
    zone[:2] = 255

    out, clipping = cc.apply_correction_to_frames(zone, neutral, "gamut-map-lin-1")
    assert clipping.above_one_pixel_count == 2 * 3 * 3, (
        f"les six pixels de papier nu (18 composantes) doivent etre comptes en "
        f"depassement haut, obtenu {clipping.above_one_pixel_count}")
    assert clipping.below_zero_pixel_count == 0
    assert clipping.clipped is True
    assert clipping.component_count == zone.size
    # L'image est bien ecretee, et non repliee.
    assert out.max() <= 1.0 and out.min() >= 0.0
    assert out[0, 0] == pytest.approx(np.ones(3))

    # Contre-epreuve: un contenu qui ne deborde pas ne doit rien compter, sans quoi le
    # diagnostic serait un compteur toujours positif -- donc sans information.
    inside = np.full((4, 3, 3), 100, dtype=np.uint8)
    _, quiet = cc.apply_correction_to_frames(inside, neutral, "gamut-map-lin-1")
    assert quiet.clipped_component_count == 0
    assert quiet.clipped is False


def test_gamut_map_inconnu_est_refuse_jamais_un_repli_sur_l_identite():
    """AC 8: une expansion devinee est pire qu'aucune, et un repli produirait un
    resultat de calibration qui **ment**."""
    page = _synthetic_rectified_page()
    result = cc.calibrate_page(page, template_id="tpl-a4-portrait-2f-v1",
                               patch_preset_id="patches-18-v2", dpi=600)
    with pytest.raises(cc.GamutExpansionRefused, match="absent du registre"):
        cc.apply_correction_to_frames(np.zeros((4, 4, 3), np.uint8),
                                      result.profile, "gamut-map-inconnu-9")


def test_gamut_map_none_est_un_no_op_verifie_et_non_un_defaut():
    """`gamut-map-none-1` est une valeur presente et valide de premier rang."""
    from mixed_media_utility import gamut_map
    assert gamut_map.get_gamut_map("gamut-map-none-1").is_identity


# --- AC 12 : l'ordre C puis G^-1, et l'aller-retour sur contenu reel ---------

def test_ordre_echoue_si_g_inverse_est_applique_avant_c():
    """AC 5 et `EPIC5-ARB-2` invariant 1. **Test d'ordre, pas de difference.**

    Le montage reproduit l'aller-retour reel: un contenu in-gamut est **comprime** par
    `G` avant impression, la chaine print+scan le distord, puis on le recupere. Le bon
    ordre est `C` puis `G^-1`; l'ordre inverse amplifie l'erreur residuelle par le gain
    de l'expansion, ce qui est precisement le motif de l'invariant.

    Un test qui n'assertait que « les deux ordres diffèrent » passerait aussi avec une
    implementation qui les intervertit tous les deux.
    """
    from mixed_media_utility import gamut_map

    mapping = gamut_map.get_gamut_map("gamut-map-lin-1")
    assert not mapping.is_identity, "il faut une compression reelle pour tester l'ordre"

    rng = np.random.default_rng(19)
    original = rng.uniform(0.15, 0.85, size=(64, 3))
    printed = mapping.compress(original)

    # Distorsion print+scan: gain, decalage et diaphonie, en lumiere.
    crosstalk = np.array([[0.95, 0.03, 0.02], [0.02, 0.96, 0.02], [0.03, 0.02, 0.95]])
    scanned = cc.oetf(np.clip((cc.eotf(printed) @ crosstalk.T) * 0.94 + 0.02, 0.0, 1.0))

    # La correction est ajustee sur les pastilles, qui ne sont JAMAIS comprimees
    # (invariant 2): on ajuste donc sur la meme distorsion appliquee aux references.
    table = patch_values.active_table()
    kept, neutral = cc.adjustment_and_neutral_masks(table.adjustment_values())
    reference = np.array([[v.rgb[2], v.rgb[1], v.rgb[0]] for v in kept],
                         dtype=np.float64) / 255.0
    patches = cc.oetf(np.clip((cc.eotf(reference) @ crosstalk.T) * 0.94 + 0.02, 0.0, 1.0))
    profile = cc.fit_correction(patches, reference, neutral)

    corrected = cc.oetf(np.clip(profile.apply_linear(cc.eotf(scanned)), 0.0, 1.0))
    right_order = np.clip(mapping.expand(corrected), 0.0, 1.0)

    expanded_first = np.clip(mapping.expand(scanned), 0.0, 1.0)
    wrong_order = cc.oetf(np.clip(profile.apply_linear(cc.eotf(expanded_first)), 0.0, 1.0))

    error_right = float(cc.delta_e76_srgb_d65(right_order, original).mean())
    error_wrong = float(cc.delta_e76_srgb_d65(wrong_order, original).mean())
    assert error_right < error_wrong, (
        f"C puis G^-1 doit battre l'ordre inverse: {error_right:.2f} contre "
        f"{error_wrong:.2f} dE76")

    # **Et c'est bien la fonction de production qui fait cet ordre-la.** Le bloc
    # ci-dessus reimplemente les deux ordres a la main: il verrouille l'invariant, pas
    # son implementation. La revue du 2026-08-11 a montre que l'inversion pouvait etre
    # introduite **dans** `apply_correction_to_frames` sans qu'un test rougisse -- son
    # seul appel passait `gamut-map-none-1`, ou les deux ordres coincident par
    # definition. On la compare donc au bon ordre, avec une compression **reelle**.
    produced, _ = cc.apply_correction_to_frames(
        scanned.reshape(-1, 1, 3), profile, "gamut-map-lin-1")
    assert produced.reshape(-1, 3) == pytest.approx(right_order, abs=1e-12), (
        "apply_correction_to_frames doit rendre exactement C puis G^-1")


def test_aller_retour_nominal_sur_le_rush_reel():
    """AC 12: la validation nominale porte sur un contenu **realiste**.

    `epics.md:209` interdit que la validation couleur repose exclusivement sur la mire
    synthetique saturee a 100 %, pire cas non representatif. La fixture fournie est
    `tests/TEST_FILE.mp4` -- contenu reel, tons chair, la famille de teintes la plus
    critique perceptivement.

    **Une fixture manquante bloque, elle ne se substitue pas** (piege 8): si le fichier
    n'est pas la, le test echoue de facon visible et n'est jamais rendu vert par un
    contenu de remplacement.
    """
    import pathlib

    import cv2

    fixture = pathlib.Path("tests/TEST_FILE.mp4")
    assert fixture.exists(), (
        "fixture de rush realiste absente: la validation nominale est bloquee, elle "
        "ne se substitue pas par du synthetique (epics.md:209, piege 8 de 5.4b)")
    capture = cv2.VideoCapture(str(fixture))
    ok, frame = capture.read()
    capture.release()
    assert ok and frame is not None

    crosstalk = np.array([[0.95, 0.03, 0.02], [0.02, 0.96, 0.02], [0.03, 0.02, 0.95]])

    def distort(encoded):
        return cc.oetf(np.clip((cc.eotf(encoded) @ crosstalk.T) * 0.93 + 0.025, 0.0, 1.0))

    table = patch_values.active_table()
    kept, neutral = cc.adjustment_and_neutral_masks(table.adjustment_values())
    reference = np.array([[v.rgb[2], v.rgb[1], v.rgb[0]] for v in kept],
                         dtype=np.float64) / 255.0
    profile = cc.fit_correction(distort(reference), reference, neutral)

    # On mesure sur une reduction: la comparaison porte sur la couleur, et travailler
    # en pleine resolution mesurerait surtout le temps de calcul.
    small = cv2.resize(frame, (frame.shape[1] // 8, frame.shape[0] // 8),
                       interpolation=cv2.INTER_AREA).astype(np.float64) / 255.0
    scanned = distort(small.reshape(-1, 3))
    recovered = cc.oetf(np.clip(profile.apply_linear(cc.eotf(scanned)), 0.0, 1.0))

    truth = small.reshape(-1, 3)
    before = float(cc.delta_e76_srgb_d65(scanned, truth).mean())
    after = float(cc.delta_e76_srgb_d65(recovered, truth).mean())
    assert after < before / 2.0, f"aller-retour nominal: {before:.2f} -> {after:.2f} dE76"


# --- AC 2 et 3b : la geometrie d'echantillonnage et son cran de repli --------

def test_carre_echantillonne_est_strictement_interieur_au_cadre_de_la_sentinelle_blanche():
    """AC 2, cas particulier a ne pas manquer, **verifie et non suppose**.

    Un `(255,255,255)` etant indiscernable du papier nu, 5.9 impose a la sentinelle
    blanche un cadre imprime de **1,0 mm** sur le bord interieur de l'emprise -- il
    occupe donc [0, 1] mm depuis chaque bord. Le carre echantillonne occupe [3, 9] mm,
    soit **2,0 mm** de marge de chaque cote entre le carre et le cadre.

    C'est la seconde des deux inclusions chiffrees de 5.9, et celle qui appartient a
    cette story.
    """
    from mixed_media_utility import patch_presets

    inset, side = cc.sampled_square_mm(patch_presets.PATCH_SIZE_MM)
    frame_thickness = 1.0
    assert inset == 3.0 and side == 6.0
    assert inset > frame_thickness, "le carre mordrait le cadre imprime"
    assert inset - frame_thickness == pytest.approx(2.0)
    assert inset + side == pytest.approx(9.0)
    assert inset + side < patch_presets.PATCH_SIZE_MM - frame_thickness


def test_la_geometrie_est_consommee_et_non_figee(monkeypatch):
    """AC 12: substituer la constante doit **deplacer** la zone mesuree.

    Si un nombre avait ete fige quelque part -- constante locale, litteral de test,
    valeur par defaut de signature -- ce test resterait vert alors que la story a
    recopie une valeur. C'est le seul moyen de verifier « consomme, jamais
    redeclare » autrement qu'a la relecture.
    """
    from mixed_media_utility import patch_presets

    before = cc.sampled_square_mm(patch_presets.PATCH_SIZE_MM)
    monkeypatch.setattr(patch_presets, "SAMPLING_INSET_MM", 4.0)
    monkeypatch.setattr(patch_presets, "SAMPLED_SIDE_MM", 4.0)
    after = cc.sampled_square_mm(patch_presets.PATCH_SIZE_MM)
    assert after != before
    assert after == (4.0, 4.0)


def test_dispersion_reste_valide_au_cardinal_de_pixels_du_repli(monkeypatch):
    """AC 3b: la statistique doit tenir aux **deux** cardinaux, pas seulement au nominal.

    `SAMPLING_INSET_MM` est une valeur **non mesuree** et 5.9 chiffre son premier cran
    de repli: portee a 4,0 mm, elle fait tomber le cote echantillonne a 4,0 mm, soit
    ~8 900 px a 600 ppp contre ~20 100 px au nominal. Un estimateur dimensionne pour
    20 100 px et silencieusement invalide a 8 900 rendrait le repli **impraticable au
    moment ou il serait necessaire** -- c'est-a-dire au premier pilote papier ou la
    bave depasserait le retrait.
    """
    from mixed_media_utility import patch_presets

    for inset, side in ((3.0, 6.0), (4.0, 4.0)):
        monkeypatch.setattr(patch_presets, "SAMPLING_INSET_MM", inset)
        monkeypatch.setattr(patch_presets, "SAMPLED_SIDE_MM", side)
        page = _synthetic_rectified_page()
        result = cc.calibrate_page(page, template_id="tpl-a4-portrait-2f-v1",
                                   patch_preset_id="patches-18-v2", dpi=600)
        pixels = round((side / 25.4 * 600) ** 2)
        assert result.status == "applied", (
            f"le repli a {side:g} mm ({pixels} px par replique) doit rester praticable")
        # L'estimateur doit rester **calculable et sensible** aux deux cardinaux: la
        # fabrique introduit un ecart entre repliques, et il doit ressortir dans les
        # deux cas. L'ancienne assertion (`== 0.0`) passait aussi bien sur un
        # estimateur qui ne calculait rien.
        assert result.replicate_dispersion_de76 > 0.0, (
            f"a {side:g} mm l'ecart entre repliques n'est plus mesure")


def test_agregation_declaree_moyenne_sur_le_carre_et_maximum_entre_repliques():
    """AC 3a: l'agregation est **declaree**, et les deux niveaux sont distincts.

    Sur les pixels d'une pastille: la **moyenne** du carre echantillonne -- le carre
    est un aplat imprime, sa moyenne est l'estimateur naturel et une mediane n'y
    apporterait rien qu'un cout.

    Entre repliques d'une meme valeur: le **maximum** des ecarts a la moyenne du groupe,
    et non leur moyenne, qui diluerait une replique salement imprimee dans les autres
    -- or « un patch salement imprime » est precisement le cas terrain que l'AC nomme.
    """
    reference = np.array([[0.5, 0.5, 0.5]])
    clean = np.repeat(reference, 3, axis=0)
    tainted = np.vstack([clean[:2], np.array([[0.9, 0.5, 0.5]])])
    worst_clean, _ = cc.replicate_dispersion(clean, ("v", "v", "v"))
    worst_tainted, detail = cc.replicate_dispersion(tainted, ("v", "v", "v"))
    assert worst_clean == pytest.approx(0.0)
    assert worst_tainted > 5.0, "une replique aberrante doit ressortir, pas etre diluee"
    assert set(detail) == {"v"}


# =============================================================================
# Story 5.20 -- la troisieme forme, et le fixture derive des trois captures reelles
# =============================================================================
#
# **Ce que ce bloc de constantes est, et pourquoi il n'est pas sous `tests/fixtures/`.**
# Ce sont les mesures des pastilles du treillis, lues sur la page de calibration
# **redressee** des trois captures reelles versees au depot (`projects/chendj-mat/
# scans/`), apres l'agregation H4 des deux repliques -- exactement ce que
# `lattice_adjustment_source` presente a l'ajustement en production. Les rasters, eux,
# ne sont pas ici: `tests/fixtures/` ne porte que des actifs binaires reels dans ce
# depot, et les trois captures pesent 408 Mo.
#
# Extraction reproductible: `scripts/research/lattice_from_real_scans.py`, qui enchaine
# `scan_ingest.ingest_scan_lot`, `scan_detection.detect_lot_pages`,
# `scan_crop.warp_detected_page`, `patch_presets.resolve_calibration_page_patches` et
# `color_calibration.sample_patches` -- le meme chemin que la production, pas un second.
#
# Les valeurs sont en **codes 8 bits** et en ordre **BGR**, celui de toute la chaine.
# Trois decimales: la mesure est une moyenne sur ~35 000 pixels, elle porte plus que le
# code entier, et l'arrondir a l'entier deplacerait les dE76 de ce fichier de ~0,1.
#
# Les trois captures viennent du **meme scanner physique** et du **meme tirage**, et
# elles couvrent deux regimes d'acquisition que le produit ne controle pas:
#
# | constante                 | capture               | pilote  | correction du pilote |
# | ---                       | ---                   | ---     | ---                  |
# | `_MEASURED_SCAN_WIN`      | `scan-WIN`            | Windows | aucune               |
# | `_MEASURED_HP_CORRECTION_OFF` | `rush-bitch-4-scan2` | HP     | desactivee           |
# | `_MEASURED_HP_CORRECTION_ON`  | `12p5_test`       | HP      | **active**           |
#
# La troisieme est la plus deformee (mean dE76 brut 30,6 contre 15,4 pour les deux
# autres) et c'est une consigne directe d'Egan qu'elle soit couverte a part entiere:
# c'est le resultat d'un reglage d'acquisition, pas un accident.
#: `scan-WIN` -- 65 valeurs, mesurees en codes 8 bits sur la page
#: de calibration redressee du lot, apres agregation H4 des deux repliques.
_MEASURED_SCAN_WIN: dict[str, tuple[float, float, float]] = {
    "lattice-008-008-008": (60.758, 61.688, 63.016),
    "lattice-008-008-068": (114.608, 88.723, 80.158),
    "lattice-008-008-128": (162.129, 100.255, 81.602),
    "lattice-008-068-008": (80.396, 111.194, 85.972),
    "lattice-008-068-068": (113.996, 108.126, 73.381),
    "lattice-008-068-128": (187.185, 126.790, 76.312),
    "lattice-008-128-008": (81.030, 150.791, 82.871),
    "lattice-008-128-068": (93.796, 146.471, 64.622),
    "lattice-008-128-128": (171.587, 151.606, 66.147),
    "lattice-068-008-008": (74.519, 68.200, 111.702),
    "lattice-068-008-068": (106.196, 63.931, 123.661),
    "lattice-068-008-128": (161.073, 80.965, 117.984),
    "lattice-068-068-008": (64.335, 106.311, 112.186),
    "lattice-068-068-068": (116.344, 117.037, 119.317),
    "lattice-068-068-128": (176.623, 115.981, 111.688),
    "lattice-068-068-188": (192.790, 119.224, 98.402),
    "lattice-068-128-008": (66.441, 144.777, 104.472),
    "lattice-068-128-068": (86.195, 150.328, 106.072),
    "lattice-068-128-128": (153.506, 153.735, 105.717),
    "lattice-068-128-188": (208.204, 155.823, 107.083),
    "lattice-068-188-068": (76.083, 180.833, 97.777),
    "lattice-068-188-128": (127.582, 184.650, 99.100),
    "lattice-068-188-188": (194.134, 186.326, 105.611),
    "lattice-128-008-008": (82.934, 57.192, 170.179),
    "lattice-128-008-068": (107.363, 45.597, 172.584),
    "lattice-128-008-128": (135.097, 48.983, 168.309),
    "lattice-128-068-008": (62.198, 100.161, 165.903),
    "lattice-128-068-068": (101.411, 97.399, 165.403),
    "lattice-128-068-128": (160.620, 94.811, 167.453),
    "lattice-128-068-188": (180.194, 105.776, 145.197),
    "lattice-128-128-008": (57.243, 143.510, 152.111),
    "lattice-128-128-068": (84.565, 147.544, 151.951),
    "lattice-128-128-128": (154.477, 154.730, 157.155),
    "lattice-128-128-188": (207.158, 154.088, 149.240),
    "lattice-128-128-245": (217.852, 160.280, 132.321),
    "lattice-128-188-068": (55.151, 179.810, 129.738),
    "lattice-128-188-128": (124.826, 190.449, 139.679),
    "lattice-128-188-188": (190.313, 190.778, 141.551),
    "lattice-128-188-245": (228.763, 180.420, 142.436),
    "lattice-128-245-128": (117.337, 203.320, 123.311),
    "lattice-128-245-188": (172.187, 209.437, 130.605),
    "lattice-128-245-245": (241.182, 211.148, 147.230),
    "lattice-188-068-068": (83.577, 70.121, 211.782),
    "lattice-188-068-128": (137.412, 47.461, 205.991),
    "lattice-188-068-188": (164.157, 69.478, 187.599),
    "lattice-188-128-068": (74.937, 135.555, 203.784),
    "lattice-188-128-128": (137.006, 134.274, 202.219),
    "lattice-188-128-188": (190.070, 126.990, 197.311),
    "lattice-188-128-245": (199.703, 134.125, 178.430),
    "lattice-188-188-068": (47.793, 177.979, 187.946),
    "lattice-188-188-128": (129.851, 192.905, 199.608),
    "lattice-188-188-188": (198.268, 197.112, 201.737),
    "lattice-188-188-245": (236.261, 197.823, 187.590),
    "lattice-188-245-128": (110.729, 219.513, 180.356),
    "lattice-188-245-188": (179.475, 227.581, 186.522),
    "lattice-188-245-245": (246.027, 231.383, 194.640),
    "lattice-245-128-128": (133.415, 128.849, 236.117),
    "lattice-245-128-188": (162.913, 117.972, 234.830),
    "lattice-245-128-245": (196.537, 128.009, 235.304),
    "lattice-245-188-128": (131.634, 184.879, 242.405),
    "lattice-245-188-188": (197.011, 191.647, 241.507),
    "lattice-245-188-245": (228.993, 186.567, 242.669),
    "lattice-245-245-128": (110.391, 233.299, 241.441),
    "lattice-245-245-188": (187.081, 242.454, 244.032),
    "lattice-245-245-245": (242.413, 240.934, 241.707),
}

#: `rush-bitch-4-scan2` -- 65 valeurs, mesurees en codes 8 bits sur la page
#: de calibration redressee du lot, apres agregation H4 des deux repliques.
_MEASURED_HP_CORRECTION_OFF: dict[str, tuple[float, float, float]] = {
    "lattice-008-008-008": (59.779, 61.084, 62.084),
    "lattice-008-008-068": (113.947, 88.186, 79.569),
    "lattice-008-008-128": (161.927, 99.979, 81.720),
    "lattice-008-068-008": (79.177, 109.895, 84.814),
    "lattice-008-068-068": (113.208, 107.483, 73.082),
    "lattice-008-068-128": (186.081, 125.578, 75.628),
    "lattice-008-128-008": (80.148, 150.173, 82.419),
    "lattice-008-128-068": (93.926, 146.890, 65.568),
    "lattice-008-128-128": (171.952, 151.928, 66.904),
    "lattice-068-008-008": (74.394, 68.208, 111.427),
    "lattice-068-008-068": (105.619, 63.738, 123.119),
    "lattice-068-008-128": (160.445, 80.685, 117.545),
    "lattice-068-068-008": (62.496, 105.097, 111.130),
    "lattice-068-068-068": (115.117, 115.808, 118.359),
    "lattice-068-068-128": (176.440, 115.581, 111.556),
    "lattice-068-068-188": (192.652, 118.991, 98.163),
    "lattice-068-128-008": (66.240, 144.481, 104.127),
    "lattice-068-128-068": (85.857, 150.397, 105.878),
    "lattice-068-128-128": (152.515, 153.043, 106.325),
    "lattice-068-128-188": (207.868, 155.323, 107.148),
    "lattice-068-188-068": (75.134, 180.220, 97.294),
    "lattice-068-188-128": (126.655, 183.444, 98.405),
    "lattice-068-188-188": (192.336, 184.545, 104.612),
    "lattice-128-008-008": (81.742, 56.243, 168.964),
    "lattice-128-008-068": (106.635, 44.430, 172.065),
    "lattice-128-008-128": (134.537, 48.654, 167.794),
    "lattice-128-068-008": (61.803, 99.070, 165.122),
    "lattice-128-068-068": (100.800, 95.802, 164.783),
    "lattice-128-068-128": (159.848, 93.545, 166.647),
    "lattice-128-068-188": (179.290, 104.931, 144.259),
    "lattice-128-128-008": (56.836, 142.695, 151.359),
    "lattice-128-128-068": (84.397, 147.437, 151.398),
    "lattice-128-128-128": (154.949, 154.575, 157.492),
    "lattice-128-128-188": (206.334, 153.512, 148.752),
    "lattice-128-128-245": (216.965, 159.616, 131.784),
    "lattice-128-188-068": (55.016, 179.252, 129.009),
    "lattice-128-188-128": (124.033, 190.014, 138.987),
    "lattice-128-188-188": (189.503, 189.992, 140.970),
    "lattice-128-188-245": (228.106, 179.751, 142.152),
    "lattice-128-245-128": (117.043, 203.190, 122.926),
    "lattice-128-245-188": (171.725, 208.983, 130.305),
    "lattice-128-245-245": (240.329, 210.441, 146.710),
    "lattice-188-068-068": (83.280, 69.777, 211.634),
    "lattice-188-068-128": (137.209, 47.202, 206.054),
    "lattice-188-068-188": (163.673, 68.723, 187.224),
    "lattice-188-128-068": (74.536, 134.610, 202.745),
    "lattice-188-128-128": (136.757, 133.470, 201.716),
    "lattice-188-128-188": (189.099, 126.109, 196.265),
    "lattice-188-128-245": (198.182, 133.219, 177.157),
    "lattice-188-188-068": (48.047, 177.436, 187.381),
    "lattice-188-188-128": (129.485, 192.525, 199.289),
    "lattice-188-188-188": (197.784, 196.660, 201.239),
    "lattice-188-188-245": (234.792, 196.436, 186.375),
    "lattice-188-245-128": (109.123, 217.811, 178.614),
    "lattice-188-245-188": (178.395, 226.667, 185.528),
    "lattice-188-245-245": (245.059, 230.587, 194.010),
    "lattice-245-128-128": (132.738, 127.987, 235.958),
    "lattice-245-128-188": (162.053, 117.628, 233.714),
    "lattice-245-128-245": (195.568, 127.976, 233.608),
    "lattice-245-188-128": (130.809, 184.023, 240.777),
    "lattice-245-188-188": (197.118, 191.702, 240.640),
    "lattice-245-188-245": (228.130, 186.223, 241.199),
    "lattice-245-245-128": (110.876, 233.018, 241.138),
    "lattice-245-245-188": (186.396, 241.236, 242.876),
    "lattice-245-245-245": (241.637, 239.928, 240.656),
}

#: `12p5_test` -- 65 valeurs, mesurees en codes 8 bits sur la page
#: de calibration redressee du lot, apres agregation H4 des deux repliques.
_MEASURED_HP_CORRECTION_ON: dict[str, tuple[float, float, float]] = {
    "lattice-008-008-008": (77.673, 78.182, 78.555),
    "lattice-008-008-068": (132.584, 116.268, 111.113),
    "lattice-008-008-128": (179.337, 136.998, 126.560),
    "lattice-008-068-008": (113.982, 131.406, 116.682),
    "lattice-008-068-068": (135.862, 132.323, 114.023),
    "lattice-008-068-128": (203.002, 158.633, 131.742),
    "lattice-008-128-008": (130.137, 176.385, 133.940),
    "lattice-008-128-068": (132.077, 170.232, 121.424),
    "lattice-008-128-128": (194.853, 180.257, 132.313),
    "lattice-068-008-008": (107.759, 105.657, 130.150),
    "lattice-068-008-068": (132.294, 110.572, 145.221),
    "lattice-068-008-128": (180.569, 133.669, 152.306),
    "lattice-068-068-008": (108.116, 129.566, 131.161),
    "lattice-068-068-068": (143.323, 143.946, 144.991),
    "lattice-068-068-128": (197.594, 155.958, 153.311),
    "lattice-068-068-188": (208.162, 156.166, 143.433),
    "lattice-068-128-008": (116.693, 167.887, 139.095),
    "lattice-068-128-068": (131.460, 175.355, 145.304),
    "lattice-068-128-128": (180.013, 181.114, 151.415),
    "lattice-068-128-188": (230.999, 192.106, 164.574),
    "lattice-068-188-068": (142.898, 209.680, 154.393),
    "lattice-068-188-128": (166.878, 210.228, 154.400),
    "lattice-068-188-188": (221.372, 217.190, 167.533),
    "lattice-128-008-008": (127.170, 120.245, 187.461),
    "lattice-128-008-068": (146.484, 123.846, 192.231),
    "lattice-128-008-128": (163.281, 125.725, 187.108),
    "lattice-128-068-008": (116.401, 138.382, 181.544),
    "lattice-128-068-068": (139.544, 139.559, 183.330),
    "lattice-128-068-128": (187.207, 149.890, 192.400),
    "lattice-128-068-188": (201.802, 154.036, 177.066),
    "lattice-128-128-008": (118.770, 168.273, 172.798),
    "lattice-128-128-068": (127.849, 170.138, 172.269),
    "lattice-128-128-128": (181.527, 181.911, 183.265),
    "lattice-128-128-188": (229.678, 191.558, 188.190),
    "lattice-128-128-245": (239.922, 198.614, 181.259),
    "lattice-128-188-068": (126.395, 202.470, 165.553),
    "lattice-128-188-128": (167.689, 213.955, 179.520),
    "lattice-128-188-188": (216.005, 217.966, 186.858),
    "lattice-128-188-245": (245.430, 214.882, 189.512),
    "lattice-128-245-128": (169.072, 228.944, 174.245),
    "lattice-128-245-188": (210.064, 238.466, 186.759),
    "lattice-128-245-245": (248.861, 239.041, 196.776),
    "lattice-188-068-068": (147.255, 145.476, 234.006),
    "lattice-188-068-128": (174.786, 140.040, 227.936),
    "lattice-188-068-188": (192.959, 144.957, 210.261),
    "lattice-188-128-068": (140.424, 173.458, 218.366),
    "lattice-188-128-128": (176.263, 177.333, 221.424),
    "lattice-188-128-188": (214.277, 175.246, 219.087),
    "lattice-188-128-245": (222.596, 179.112, 205.482),
    "lattice-188-188-068": (138.973, 209.460, 212.140),
    "lattice-188-188-128": (180.942, 223.151, 226.536),
    "lattice-188-188-188": (222.778, 222.533, 224.965),
    "lattice-188-188-245": (248.083, 230.915, 222.726),
    "lattice-188-245-128": (167.370, 242.538, 209.460),
    "lattice-188-245-188": (213.703, 247.324, 218.162),
    "lattice-188-245-245": (248.668, 245.584, 219.654),
    "lattice-245-128-128": (181.281, 181.168, 249.082),
    "lattice-245-128-188": (197.715, 174.627, 249.028),
    "lattice-245-128-245": (225.680, 185.083, 249.403),
    "lattice-245-188-128": (189.113, 221.900, 250.911),
    "lattice-245-188-188": (232.902, 230.995, 250.030),
    "lattice-245-188-245": (243.156, 222.838, 250.097),
    "lattice-245-245-128": (170.520, 246.766, 248.212),
    "lattice-245-245-188": (216.467, 247.802, 247.287),
    "lattice-245-245-245": (245.433, 245.575, 245.939),
}

#: Les trois captures, nommees pour que chaque test les parcoure **toutes** plutot que
#: d'en choisir une. Consigne directe d'Egan (AC 2 de la story 5.20): « la correction
#: doit passer sur TOUS les fichiers de l'echantillon reel, pas seulement sur certains ».
#: Un test ecrit sur une seule capture ne dirait rien du regime a reglage HP actif, qui
#: est celui ou la forme en vigueur effondre le blanc.
REAL_CAPTURES: dict[str, dict[str, tuple[float, float, float]]] = {
    "scan-WIN": _MEASURED_SCAN_WIN,
    "rush-bitch-4-scan2": _MEASURED_HP_CORRECTION_OFF,
    "12p5_test": _MEASURED_HP_CORRECTION_ON,
}


def _real_capture(name: str, *, exclude_ink_floor: bool = True):
    """Rendre `(value_ids, mesures BGR, references BGR, masque neutre)` d'une capture.

    Les references ne sont **pas** stockees avec les mesures: elles sont derivees du
    treillis (`patch_values.calibration_lattice_values`), comme en production. Les figer
    dans le fixture ferait deux verites pour un fait, et la premiere reference posee de
    travers rendrait tous les chiffres de ce fichier faux et coherents entre eux.

    `exclude_ink_floor` reproduit le filtre de l'AC 7. Il est **parametrable** parce que
    l'effet de ce filtre est lui-meme mesure par un test: le passer en dur rendrait
    l'exclusion invisible a la mesure qui la justifie.
    """
    lattice = {value.value_id: value
               for value in patch_values.calibration_lattice_values()}
    measured_map = REAL_CAPTURES[name]
    value_ids = tuple(
        value_id for value_id in sorted(measured_map)
        if not (exclude_ink_floor
                and patch_values.is_below_ink_floor(lattice[value_id].rgb)))
    measured = np.asarray(
        [measured_map[value_id] for value_id in value_ids], dtype=np.float64) / 255.0
    reference = np.asarray(
        [np.asarray(lattice[value_id].rgb[::-1], dtype=np.float64) / 255.0
         for value_id in value_ids], dtype=np.float64)
    neutral = np.asarray(
        [len(set(lattice[value_id].rgb)) == 1 for value_id in value_ids], dtype=bool)
    return value_ids, measured, reference, neutral


def _corrected(profile, measured):
    """Mesures corrigees, ecretees et reencodees -- le chemin exact de la production."""
    return cc.oetf(np.clip(profile.apply_linear(cc.eotf(measured)), 0.0, 1.0))


def _grey_ladder(*, cast=(1.0, 1.0, 1.0), levels=(0.05, 0.25, 0.55, 0.90)):
    """Fabrique d'un jeu neutre **a plusieurs niveaux distincts**, avec dominante.

    Regle des fabriques de `CLAUDE.md`: quatre niveaux differents et non un remplissage
    uniforme -- une permutation d'ancrages ou une courbe qui rendrait une constante ne se
    voit que si les niveaux different. `cast` multiplie chaque canal separement, donc les
    trois courbes ont des ancrages **distincts en entree**: sans dominante, un bug qui
    partagerait les entrees au lieu des sorties serait invisible.
    """
    reference = np.asarray([[level] * 3 for level in levels], dtype=np.float64)
    measured = np.clip(reference * np.asarray(cast, dtype=np.float64), 0.0, 1.0)
    return measured, reference, np.ones(len(levels), dtype=bool)


def _chromatic_pair():
    """Deux valeurs chromatiques **distinguables**, pour rendre la 2x2 de rang 2."""
    reference = np.asarray([[0.20, 0.60, 0.30], [0.70, 0.25, 0.50]], dtype=np.float64)
    measured = np.asarray([[0.28, 0.62, 0.36], [0.72, 0.33, 0.53]], dtype=np.float64)
    return measured, reference, np.zeros(2, dtype=bool)


def _mixed_adjustment_set():
    """Un jeu complet: quatre neutres **et** deux chromatiques, la cible en 5e position.

    « Au moins un test place la cible ailleurs qu'en premiere position »: les valeurs
    chromatiques, dont depend le rang de la 2x2, sont les deux **dernieres**. Un ajusteur
    qui ne lirait que la tete du jeu rendrait une conception de rang 0 et serait refuse,
    au lieu de passer en silence.
    """
    grey_m, grey_r, grey_n = _grey_ladder(cast=(1.10, 1.04, 0.96))
    chroma_m, chroma_r, chroma_n = _chromatic_pair()
    return (np.vstack([grey_m, chroma_m]), np.vstack([grey_r, chroma_r]),
            np.concatenate([grey_n, chroma_n]))


# --- AC 1 : le registre gagne une entree, les deux autres ne bougent pas ------

def test_le_registre_porte_trois_formes_et_les_deux_anciennes_sont_les_memes_objets():
    """AC 1: la forme nouvelle est **ajoutee a cote**, jamais a la place.

    L'assertion porte sur l'**identite** des ajusteurs enregistres et non sur leur
    presence: une reecriture de `fit_correction` qui garderait le meme nom passerait un
    test d'appartenance, et c'est precisement le changement que l'AC interdit -- les jeux
    de test existants doivent rendre des resultats inchanges au bit pres.
    """
    assert set(cc.CORRECTION_FORMS) == {
        cc.CORRECTION_FORM_ID,
        cc.CORRECTION_FORM_LAB_ID,
        cc.CORRECTION_FORM_TONE_CHROMA_ID,
    }
    assert cc.CORRECTION_FORMS[cc.CORRECTION_FORM_ID] is cc.fit_correction
    assert cc.CORRECTION_FORMS[cc.CORRECTION_FORM_LAB_ID] is cc.fit_correction_lab
    assert cc.CORRECTION_FORMS[cc.CORRECTION_FORM_TONE_CHROMA_ID] is \
        cc.fit_correction_tone_chroma
    # La forme **en vigueur** ne change pas: l'AC 1 interdit aussi de deplacer ce qui
    # est choisi quand personne ne choisit.
    assert cc.CORRECTION_FORM_ID == "color-correction-affine-matrix-1"
    assert cc.CORRECTION_FORM_TONE_CHROMA_ID == "color-correction-tone-curve-chroma-1"


def test_les_trois_formes_satisfont_le_protocole_d_application():
    """AC 1: le Protocol est le **seul** contrat que les points d'application lisent.

    Verifie a l'execution et non par relecture: `AnyCorrectionProfile` est
    `runtime_checkable` exactement pour que ce test existe.
    """
    measured, reference, neutral = _mixed_adjustment_set()
    for form_id in cc.CORRECTION_FORMS:
        profile = cc.get_correction_form(form_id)(measured, reference, neutral)
        assert isinstance(profile, cc.AnyCorrectionProfile), form_id
        assert profile.correction_id == form_id
        # Et il **applique** vraiment: un profil qui satisferait le protocole sans rien
        # faire rendrait l'entree telle quelle.
        linear = cc.eotf(measured)
        assert not np.allclose(profile.apply_linear(linear), linear), form_id


def test_la_forme_nouvelle_traverse_les_deux_points_d_application_sans_les_modifier():
    """AC 1: `apply_profile_to_image` et `apply_correction_to_frames` sont intacts.

    Le test les **exerce** avec la forme nouvelle plutot que de constater que leur
    source n'a pas change: c'est la garantie utile, et elle epingle du meme coup que le
    profil accepte une image `(H, W, 3)` et non seulement une table `(N, 3)`.
    """
    measured, reference, neutral = _mixed_adjustment_set()
    profile = cc.fit_correction_tone_chroma(measured, reference, neutral)
    image = np.linspace(0.02, 0.98, 4 * 5 * 3).reshape(4, 5, 3)
    corrected = cc.apply_profile_to_image(image, profile)
    assert corrected.shape == image.shape
    assert np.isfinite(corrected).all()
    assert (corrected >= 0.0).all() and (corrected <= 1.0).all()
    expanded, clipping = cc.apply_correction_to_frames(image, profile, "gamut-map-none-1")
    assert expanded.shape == image.shape
    assert clipping.component_count == image.size


# --- AC 6 : l'axe neutre, invariant par construction --------------------------

def test_l_axe_neutre_est_rendu_exactement_sur_les_trois_captures_reelles():
    """AC 6, et c'est la propriete centrale de la forme.

    Chaque valeur **neutre en reference** du jeu d'ajustement est un ancrage de la
    courbe, et les trois canaux partagent le meme vecteur de sorties: elle ressort donc
    exactement sur sa reference grise, et l'ecart entre canaux est nul -- pas « petit ».

    Le seuil enregistre (`NEUTRAL_AXIS_MAX_CHANNEL_SPREAD_8BIT`) est verifie **en plus**
    de l'egalite exacte, parce que c'est lui qui vaudra pour une correction transportee
    d'une page a l'autre, ou l'egalite exacte ne tient plus.
    """
    for name in REAL_CAPTURES:
        _ids, measured, reference, neutral = _real_capture(name)
        assert neutral.sum() >= 2, (
            f"{name}: moins de deux neutres, la courbe ne serait pas ajustable")
        profile = cc.fit_correction_tone_chroma(measured, reference, neutral)
        corrected = _corrected(profile, measured)
        spread = cc.neutral_axis_channel_spread_8bit(corrected, neutral)
        assert spread < cc.NEUTRAL_AXIS_MAX_CHANNEL_SPREAD_8BIT, name
        # **1e-4 code et non zero, et le chiffre a une cause nommee**: les coefficients
        # publies de `SRGB_TO_XYZ_D65_BGR` sont arrondis a la septieme decimale, donc
        # leurs lignes ne somment pas exactement au blanc D65 et un triplet parfaitement
        # neutre porte une chroma residuelle de ~1,4e-5 unite Lab. L'etage de chroma la
        # deplace, d'ou ~3e-6 code de teinte au retour. C'est 500 000 fois sous le seuil
        # enregistre, et c'est la limite de la representation, pas celle de la forme.
        assert spread == pytest.approx(0.0, abs=1e-4), (
            f"{name}: l'invariance de l'axe neutre est une propriete de la forme, "
            "pas un residu d'ajustement")
        # Et le gris ne sort pas seulement neutre: il sort **a la bonne clarte**.
        assert np.abs(corrected[neutral] - reference[neutral]).max() * 255 < 0.01, name


def test_le_cinquieme_neutre_jamais_ancre_ressort_gris_lui_aussi():
    """AC 6, le seul neutre que la garantie **ne** couvre pas par construction.

    Finding de la revue de 5.20 (ferme le 2026-08-19): les quatre neutres verifies par le
    test precedent sont exactement les quatre ancrages de la courbe, donc `spread ~ 0` y
    est garanti par la forme et non mesure. Le seul neutre du treillis qui n'est jamais
    ancre sous cette fabrique est `lattice-008-008-008`, que `_real_capture` retire par
    defaut (filtre du plancher d'encrage): on l'ajuste **sans** lui, puis on lui applique
    la correction obtenue. C'est la seule mesure de cette page qui dit quelque chose du
    comportement **entre** les ancrages, et c'est ce que vaudra une correction transportee
    d'une page a l'autre.

    Les trois valeurs sont ecrites **en litteral** et non relues du code: elles sont le
    fait mesure, pas une consequence de la forme.
    """
    attendu = {"scan-WIN": 0.2029, "rush-bitch-4-scan2": 0.2911, "12p5_test": 0.0790}
    assert set(attendu) == set(REAL_CAPTURES), (
        "les trois captures sont couvertes, pas seulement celle qui arrange")
    floor_ids = patch_values.ink_floor_lattice_value_ids()
    assert floor_ids == ("lattice-008-008-008",), (
        "le neutre non ancre est celui-la; s'il change, ce test doit etre rejoue")
    lattice = {value.value_id: value
               for value in patch_values.calibration_lattice_values()}
    cible = lattice[floor_ids[0]]
    assert len(set(cible.rgb)) == 1, "la cible doit etre un gris, sans quoi rien a mesurer"

    for name, chiffre in attendu.items():
        _ids, measured, reference, neutral = _real_capture(name)
        assert floor_ids[0] not in _ids, (
            f"{name}: la cible est ancree, la mesure perdrait son objet")
        profile = cc.fit_correction_tone_chroma(measured, reference, neutral)
        hors_ancrage = np.asarray(
            [REAL_CAPTURES[name][floor_ids[0]]], dtype=np.float64) / 255.0
        corrige = _corrected(profile, hors_ancrage)
        spread = cc.neutral_axis_channel_spread_8bit(corrige, np.ones(1, bool))
        assert spread == pytest.approx(chiffre, abs=0.005), (name, spread)
        # Et le fait qui compte pour l'AC 6: meme hors ancrage, l'ecart reste **sous**
        # le seuil enregistre -- ce que le test des quatre ancrages ne pouvait pas dire.
        assert spread < cc.NEUTRAL_AXIS_MAX_CHANNEL_SPREAD_8BIT, name
    # Le temoin negatif: sans correction, la capture porte un ecart bien plus grand sur
    # cette meme valeur. Sans lui, les trois chiffres ci-dessus seraient tenus par une
    # correction qui ne ferait rien.
    brut = np.asarray(
        [REAL_CAPTURES["scan-WIN"][floor_ids[0]]], dtype=np.float64) / 255.0
    assert cc.neutral_axis_channel_spread_8bit(brut, np.ones(1, bool)) > 1.0


def _echelle_grise_melangee():
    """Quatre neutres presentes **hors ordre croissant de reference**, plus deux couleurs.

    Finding de la revue de 5.20 (ferme le 2026-08-19): toutes les fabriques presentaient
    deja les neutres en ordre croissant, donc le tri de `neutral_tone_anchors` etait un
    no-op et quatre mutants d'ordre survivaient (`argsort` -> `arange`, permutation
    retiree sur les entrees, permutation retiree sur les sorties). L'ordre choisi ne
    commence ni ne finit par un extreme: 0,55 / 0,05 / 0,90 / 0,25.
    """
    grey_m, grey_r, grey_n = _grey_ladder(cast=(1.10, 1.04, 0.96),
                                          levels=(0.55, 0.05, 0.90, 0.25))
    chroma_m, chroma_r, chroma_n = _chromatic_pair()
    return (np.vstack([grey_m, chroma_m]), np.vstack([grey_r, chroma_r]),
            np.concatenate([grey_n, chroma_n]))


def test_les_ancrages_sont_tries_quel_que_soit_l_ordre_d_entree_du_jeu():
    """AC 6: `np.interp` ne leve pas sur un `xp` non croissant, il ment.

    Le jeu melange et le jeu trie decrivent **les memes** ancrages: la forme ne depend
    pas de l'ordre dans lequel l'appelant a range ses valeurs. C'est ce qui rend
    l'egalite ci-dessous forte -- elle porte sur les tableaux entiers, pas seulement sur
    la monotonie.
    """
    melange = _echelle_grise_melangee()
    profil_melange = cc.fit_correction_tone_chroma(*melange)

    grey_m, grey_r, grey_n = _grey_ladder(cast=(1.10, 1.04, 0.96),
                                          levels=(0.05, 0.25, 0.55, 0.90))
    chroma_m, chroma_r, chroma_n = _chromatic_pair()
    profil_trie = cc.fit_correction_tone_chroma(
        np.vstack([grey_m, chroma_m]), np.vstack([grey_r, chroma_r]),
        np.concatenate([grey_n, chroma_n]))

    assert np.allclose(profil_melange.tone_anchors_in, profil_trie.tone_anchors_in)
    assert np.allclose(profil_melange.tone_anchors_out, profil_trie.tone_anchors_out)
    assert np.allclose(profil_melange.chroma_matrix, profil_trie.chroma_matrix)
    # Strictement croissants sur les sorties **et** sur les trois entrees: c'est la
    # propriete que le tri existe pour tenir, et `np.interp` ne la verifie pas.
    assert np.all(np.diff(profil_melange.tone_anchors_out) > 0.0)
    assert np.all(np.diff(profil_melange.tone_anchors_in, axis=0) > 0.0)
    # Les quatre niveaux de la fabrique sont bien distincts et bien desordonnes a
    # l'entree: sans cela ce test serait vert et vide.
    _measured, reference, neutral = melange
    niveaux = reference[neutral][:, 0]
    assert len(set(niveaux.tolist())) == 4
    assert not np.all(np.diff(niveaux) > 0.0), "le jeu doit entrer desordonne"


def test_l_appariement_entrees_sorties_des_ancrages_survit_au_desordre():
    """AC 6, le second volet: le tri **et** la permutation appliquee aux deux tableaux.

    Trier les sorties sans permuter les entrees (ou l'inverse) casse l'appariement
    positionnel -- la faute de la famille `M33`/`M25` de `CLAUDE.md`. Le test le lit
    directement: chaque neutre du jeu doit se retrouver, entree **et** sortie ensemble,
    a la meme position du couple d'ancrages.
    """
    measured, reference, neutral = _echelle_grise_melangee()
    profile = cc.fit_correction_tone_chroma(measured, reference, neutral)
    interieur_in = profile.tone_anchors_in[1:-1]
    interieur_out = profile.tone_anchors_out[1:-1]
    attendus = sorted(zip(reference[neutral][:, 0].tolist(),
                          measured[neutral].tolist()))
    assert len(interieur_out) == len(attendus) == 4
    for position, (niveau, mesure) in enumerate(attendus):
        assert interieur_out[position] == pytest.approx(cc.eotf(niveau), abs=1e-12)
        assert np.allclose(interieur_in[position], cc.eotf(np.asarray(mesure)))


def test_les_bornes_synthetiques_ne_sont_pas_posees_quand_une_mesure_les_occupe():
    """AC 6, condition limite **atteignable en champ**: le noir ecrete a 0,0.

    Finding de la revue de 5.20 (ferme le 2026-08-19): les deux conditions qui posent les
    bornes `0 -> 0` et `1 -> 1` n'etaient jamais vues fausses, donc `and` -> `or` et
    `>` -> `>=` survivaient tous les deux. Le regime n'a rien de theorique: c'est
    exactement l'ecrasement des noirs que cette story adresse -- un neutre mesure a 0,0
    sur les trois canaux -- et son symetrique, le blanc souffle a 1,0.

    Ce que le test exige: l'ajustement **reussit**. Poser la borne quand une mesure
    l'occupe deja creerait un ancrage duplique, donc non strictement croissant, donc
    refuse -- pour un motif qui n'a rien a voir avec le defaut que la garde cherche.
    """
    chroma_m, chroma_r, chroma_n = _chromatic_pair()

    for extreme, position, cardinal in ((0.0, 0, 5), (1.0, -1, 5)):
        grey_m, grey_r, grey_n = _grey_ladder(levels=(0.05, 0.25, 0.55, 0.90))
        grey_m = grey_m.copy()
        grey_m[position] = extreme
        profile = cc.fit_correction_tone_chroma(
            np.vstack([grey_m, chroma_m]), np.vstack([grey_r, chroma_r]),
            np.concatenate([grey_n, chroma_n]))
        # Cinq ancrages et non six: une seule borne synthetique a ete posee, celle du
        # cote oppose. Le cardinal est ecrit en litteral -- quatre neutres, une borne.
        assert len(profile.tone_anchors_out) == cardinal, extreme
        assert profile.tone_anchors_in.shape == (cardinal, 3), extreme
        assert np.all(np.diff(profile.tone_anchors_out) > 0.0)
        assert np.all(np.diff(profile.tone_anchors_in, axis=0) > 0.0)
        # La mesure extreme est bien restee dans les ancrages, a sa place.
        assert profile.tone_anchors_in[position].min() == pytest.approx(extreme,
                                                                       abs=1e-12)

    # Le temoin positif, sans lequel le cardinal ci-dessus ne dirait rien: quand aucune
    # mesure n'occupe les extremes, les **deux** bornes sont posees -- six ancrages.
    grey_m, grey_r, grey_n = _grey_ladder(levels=(0.05, 0.25, 0.55, 0.90))
    nominal = cc.fit_correction_tone_chroma(
        np.vstack([grey_m, chroma_m]), np.vstack([grey_r, chroma_r]),
        np.concatenate([grey_n, chroma_n]))
    assert len(nominal.tone_anchors_out) == 6
    assert nominal.tone_anchors_out[0] == 0.0 and nominal.tone_anchors_out[-1] == 1.0
    assert np.all(nominal.tone_anchors_in[0] == 0.0)
    assert np.all(nominal.tone_anchors_in[-1] == 1.0)


def test_la_courbe_refuse_un_tableau_qui_n_a_pas_trois_canaux():
    """Finding de la revue de 5.20 (ferme le 2026-08-19): `apply_tone_curve` supposait 3.

    La boucle parcourt `range(3)` et la sortie vient de `np.empty_like`: un tableau BGRA
    ressortait avec son quatrieme canal **non initialise**, donc une sortie non
    deterministe et silencieuse -- l'alpha perdu sans qu'aucun appelant l'apprenne. Le
    cardinal de canaux est desormais un refus, comme il l'est deja a l'ajustement
    (`neutral_tone_anchors` leve sur une forme qui n'a pas trois canaux).
    """
    entrees = np.asarray([[0.0, 0.0, 0.0], [0.5, 0.5, 0.5], [1.0, 1.0, 1.0]])
    sorties = np.asarray([0.0, 0.4, 1.0])
    # Le temoin positif: trois canaux passent, et la courbe fait quelque chose.
    bgr = np.asarray([[[0.2, 0.3, 0.4], [0.6, 0.7, 0.8]]])
    rendu = cc.apply_tone_curve(entrees, sorties, bgr)
    assert rendu.shape == (1, 2, 3)
    assert not np.allclose(rendu, bgr)

    for canaux in (1, 2, 4):
        fautif = np.full((1, 2, canaux), 0.5)
        with pytest.raises(ValueError, match="trois canaux"):
            cc.apply_tone_curve(entrees, sorties, fautif)


def test_le_cardinal_de_chroma_de_la_forme_nouvelle_se_lit_sur_la_reference():
    """AC 2: la forme courbe+chroma compte ses points de chroma sur la **reference**.

    Finding de la revue de 5.20 (ferme le 2026-08-19): l'asymetrie avec `fit_lab_chroma`,
    qui compte sur la mesure, n'etait epinglee par aucun test -- remplacer
    `reference_linear` par `measured_linear` au point d'appel ne faisait echouer personne.
    Le parametre a ete renomme `lab` dans le meme mouvement, pour que les deux appels
    cessent de se contredire a la lecture.

    La fabrique separe les deux lectures: trois references chromatiques **distinctes**
    que le scanner rend a une **meme** mesure grise. Sur la reference le cardinal vaut 4
    et l'ajustement passe; sur la mesure il vaut 2 et l'ajustement serait refuse.
    """
    grey_m, grey_r, grey_n = _grey_ladder(cast=(1.06, 1.00, 0.94))
    ref_chroma = np.asarray([[0.20, 0.60, 0.30], [0.70, 0.25, 0.50],
                             [0.35, 0.55, 0.62]])
    mesure_confondue = np.full((3, 3), 0.42)
    measured = np.vstack([grey_m, mesure_confondue])
    reference = np.vstack([grey_r, ref_chroma])
    neutral = np.concatenate([grey_n, np.zeros(3, dtype=bool)])

    lab_reference = cc.lab_from_linear_bgr(np.atleast_2d(cc.eotf(reference)))
    lab_mesure = cc.lab_from_linear_bgr(np.atleast_2d(cc.eotf(measured)))
    # Les deux cardinaux, en litteral: 4 sur la reference, 2 sur la mesure. Le minimum
    # exige vaut 3, donc les deux lectures ne rendent pas le meme verdict.
    assert cc.distinct_chroma_point_count(lab_reference, neutral) == 4
    assert cc.distinct_chroma_point_count(lab_mesure, neutral) == 2
    assert cc.MIN_DISTINCT_CHROMA_POINTS == 3

    # C'est la reference qui decide: l'ajustement passe.
    profile = cc.fit_correction_tone_chroma(measured, reference, neutral)
    assert profile.correction_id == cc.CORRECTION_FORM_TONE_CHROMA_ID
    assert np.asarray(profile.chroma_matrix).shape == (2, 2)


def test_les_deux_derivations_de_neutre_s_accordent_sur_tout_jeu_d_ajustement():
    """Finding de la revue de 5.20 (ferme le 2026-08-19): deux definitions coexistent.

    L'ajustement lit un **role declare** (`ROLE_NEUTRAL` dans les tables, l'egalite des
    trois canaux dans le treillis), le budget de distorsion une propriete **derivee**
    (`is_grey_reference`). Rien ne forcait leur accord, et une table ajoutee demain avec
    un role pose de travers ferait juger a la clause de l'axe neutre une famille qui
    n'est pas celle qu'elle nomme -- le risque nomme en 5.7.

    La frontiere est **totale**: toutes les tables du registre, plus le treillis, et non
    la seule table active.
    """
    for version in patch_values.known_versions():
        table = patch_values.get_patch_values_table(version)
        valeurs = table.adjustment_values()
        assert valeurs, f"{version}: jeu d'ajustement vide, la boucle serait vide"
        for value in valeurs:
            declare = value.role == patch_values.ROLE_NEUTRAL
            derive = cm.is_grey_reference(
                [component / 255.0 for component in value.rgb])
            assert declare is derive, (
                f"{version}/{value.value_id}: role={value.role!r} rgb={value.rgb} -- "
                "les deux derivations de « neutre » divergent")
        # Et la boucle n'est pas vide de son objet: chaque jeu porte au moins deux
        # neutres et au moins une valeur qui n'en est pas.
        roles = [value.role == patch_values.ROLE_NEUTRAL for value in valeurs]
        assert sum(roles) >= 2 and not all(roles), version

    # Le treillis passe par l'heuristique et non par le role: meme accord exige.
    treillis = patch_values.calibration_lattice_values()
    gris = [value for value in treillis
            if cm.is_grey_reference([c / 255.0 for c in value.rgb])]
    assert len(gris) == 5, "cinq neutres au treillis, en litteral"
    for value in treillis:
        heuristique = len(set(value.rgb)) == 1
        derive = cm.is_grey_reference([c / 255.0 for c in value.rgb])
        assert heuristique is derive, (value.value_id, value.rgb)

    # Les deux sentinelles de gamut sont grises **et** non neutres, et c'est delibere:
    # elles sont ecretees par construction et exclues du jeu d'ajustement. Le nommer ici
    # empeche de lire l'accord ci-dessus comme un accord universel qu'il n'est pas.
    table = patch_values.get_patch_values_table("patch-values-2")
    sentinelles_grises = [
        value for value in table.values
        if value.role == patch_values.ROLE_GAMUT_SENTINEL
        and cm.is_grey_reference([c / 255.0 for c in value.rgb])]
    assert {value.value_id for value in sentinelles_grises} == {"sentinel-black-1",
                                                                "sentinel-white-1"}
    for value in sentinelles_grises:
        assert value.role != patch_values.ROLE_NEUTRAL
        assert value not in table.adjustment_values()


def test_le_vecteur_de_sorties_de_la_courbe_est_unique_et_pas_un_par_canal():
    """AC 6, la garantie sous sa forme executable.

    C'est le mutant le plus dangereux de cette forme: donner a chaque canal **sa**
    reference (`reference[mask][:, channel]`) au lieu de la clarte partagee. Sur un
    treillis, les trois references d'un neutre sont egales, donc le mutant serait
    **invisible** sur les captures reelles. Ce qui le tue est la forme de l'objet --
    `tone_anchors_out` est de rang 1 -- et un jeu ou la mutation change le resultat: la
    fabrique porte une dominante par canal, donc les entrees different entre canaux
    meme quand les sorties ne le peuvent pas.
    """
    measured, reference, neutral = _mixed_adjustment_set()
    profile = cc.fit_correction_tone_chroma(measured, reference, neutral)
    assert profile.tone_anchors_out.ndim == 1
    assert len(profile.tone_anchors_out) == len(profile.tone_anchors_in)
    assert profile.tone_anchors_in.shape[1] == 3
    # Les entrees, elles, different bien entre canaux: sans cela la dominante ne serait
    # pas corrigee et ce test serait vert et vide.
    interior = profile.tone_anchors_in[1:-1]
    assert np.abs(interior[:, 0] - interior[:, 2]).max() > 1e-6


def test_l_etage_de_chroma_laisse_l_origine_invariante():
    """AC 6: la 2x2 est **sans decalage**, donc `(a*, b*) = (0, 0)` reste a l'origine.

    C'est la seconde moitie de l'invariance de l'axe neutre -- la premiere etant les
    ancrages partages --, et elle se verifie sur la matrice et sur son effet. Un
    decalage colorerait tout gris de la meme quantite, sans que la courbe puisse le
    rattraper.
    """
    measured, reference, neutral = _mixed_adjustment_set()
    profile = cc.fit_correction_tone_chroma(measured, reference, neutral)
    assert np.asarray(profile.chroma_matrix).shape == (2, 2)
    greys = np.asarray([[0.2, 0.2, 0.2], [0.8, 0.8, 0.8]], dtype=np.float64)
    lab = cc.lab_from_linear_bgr(cc.eotf(greys))
    # « Nulle » a 1,4e-5 pres: les coefficients publies de la matrice XYZ sont arrondis
    # a la septieme decimale, donc leurs lignes ne somment pas exactement au blanc D65.
    # C'est la seule raison pour laquelle l'invariance de l'axe neutre n'est pas exacte
    # au bit pres, et elle n'appartient pas a cette forme.
    assert np.abs(lab[:, 1:3]).max() < 1e-4, "un gris a une chroma quasi nulle"
    moved = lab[:, 1:3] @ np.asarray(profile.chroma_matrix).T
    assert np.abs(moved).max() <= np.abs(lab[:, 1:3]).max() * np.abs(
        np.asarray(profile.chroma_matrix)).sum()
    # Le seul fait qui compte, et il est exact: **l'origine est un point fixe**.
    origine = np.zeros((1, 2)) @ np.asarray(profile.chroma_matrix).T
    assert np.abs(origine).max() == 0.0


def test_la_statistique_de_l_axe_neutre_ne_se_lit_pas_en_moyenne_bgr():
    """AC 6, piege nomme: **une moyenne BGR masque une teinte**.

    Le triplet de ce test a une moyenne exacte et un rouge a 30 codes de sa cible -- le
    defaut qu'Egan a releve a l'oeil apres des dizaines de mesures moyennees qui ne le
    voyaient pas. La statistique doit le rendre, une moyenne des trois canaux le
    rendrait nul.
    """
    tinted = np.asarray([[0.5 + 30 / 255, 0.5, 0.5 - 30 / 255]], dtype=np.float64)
    assert tinted.mean() == pytest.approx(0.5)
    assert cc.neutral_axis_channel_spread_8bit(tinted, np.ones(1, bool)) == \
        pytest.approx(30.0, abs=1e-6)
    # Aucune valeur neutre: rien n'a ete mesure, et zero est ce que rend une mesure
    # parfaite. La fonction rend zero **et** son contrat le dit -- l'appelant qui juge
    # un jeu sans neutre juge un jeu sans axe neutre.
    assert cc.neutral_axis_channel_spread_8bit(tinted, np.zeros(1, bool)) == 0.0


# --- AC 3 : la confusion inter-canal, traitee et mesuree ----------------------

def test_les_neutres_ne_sont_jamais_degrades_par_les_pastilles_saturees():
    """AC 3: le defaut du prototype est **structurellement impossible** ici.

    Constat du diagnostic: une courbe par canal ajustee sur les 130 pastilles confond
    une pastille neutre a 68 et une pastille saturee dont un canal vaut aussi 68, et
    degrade ainsi `lattice-068-068-068` jusqu'a 35,7 dE76 -- alors que ce point est l'un
    de ses propres ancrages. La cause est que la courbe doit mapper **une meme mesure
    sur deux references differentes**.

    La forme retenue ne peut pas rencontrer cette contradiction: son jeu d'ajustement de
    tonalite ne contient **que** des neutres, dont les references sont distinctes deux a
    deux par construction du treillis. Le test le constate a la sortie sur les trois
    captures -- residu nul sur chaque neutre -- et il constate aussi que la contradiction
    **existe bien dans les donnees**, sans quoi il serait vert et vide.
    """
    for name in REAL_CAPTURES:
        value_ids, measured, reference, neutral = _real_capture(name)
        profile = cc.fit_correction_tone_chroma(measured, reference, neutral)
        corrected = _corrected(profile, measured)
        residual = cc.delta_e76_srgb_d65(corrected[neutral], reference[neutral])
        assert residual.max() < 0.05, (
            f"{name}: un ancrage neutre a {residual.max():.2f} dE76 de sa reference")

        # Le regime que le prototype ne savait pas traiter est present: au moins un
        # couple (neutre, chromatique) partage un code brut a moins d'un code sur un
        # canal, alors que leurs references y different de plus de 30 codes.
        confondus = [
            (value_ids[i], value_ids[j], channel)
            for i in np.flatnonzero(neutral) for j in np.flatnonzero(~neutral)
            for channel in range(3)
            if abs(measured[i, channel] - measured[j, channel]) * 255 < 1.0
            and abs(reference[i, channel] - reference[j, channel]) * 255 > 30
        ]
        assert confondus, (
            f"{name}: aucun couple confondu dans les mesures, ce test serait vide")


#: AC 3, « avec le chiffre a l'appui »: separation restituee par l'etage de chroma sur le
#: pire couple confondu de chaque capture, mesuree le 2026-08-13 et rejouee le 2026-08-19.
#: Codes 8 bits. `ecart_reference` est ce que les deux references separent, `sans` ce que
#: la courbe seule restitue, `avec` ce que la courbe et l'etage de chroma restituent
#: ensemble.
#:
#: Ce que le tableau rend lisible et que l'inegalite seule cachait: la confusion est
#: **attenuee et non eliminee** (23%, 1% et 20% de l'ecart de reference), et sur
#: `rush-bitch-4-scan2` la marge de l'inegalite vaut 0,58 - 0,54 = **0,04 code**. C'est
#: le meme ordre de grandeur que la marge de 0,04 code qui a fait rendre informatif le
#: seuil d'`EPIC5-ARB-75` (`EPIC5-ARB-78`): a ce regime, l'inegalite ne dit rien.
SEPARATION_RESTITUEE_PAR_L_ETAGE_DE_CHROMA = {
    "scan-WIN": {
        "ecart_reference": 60.0, "sans": 1.897, "avec": 13.789,
        "paire": ("lattice-068-068-068", "lattice-245-128-188")},
    "rush-bitch-4-scan2": {
        "ecart_reference": 57.0, "sans": 0.542, "avec": 0.582,
        "paire": ("lattice-188-188-188", "lattice-188-128-245")},
    "12p5_test": {
        "ecart_reference": 57.0, "sans": 0.241, "avec": 11.550,
        "paire": ("lattice-188-188-188", "lattice-188-128-245")},
}


def test_l_etage_de_chroma_separe_ce_que_la_courbe_seule_confond():
    """AC 3, le chiffre a l'appui -- et ce que la forme **ne** garantit pas.

    Il faut le dire franchement: la courbe de tonalite est elle aussi une fonction 1D
    par canal, donc deux pastilles qui partagent un code brut sur un canal ressortent
    **au meme code sur ce canal** apres la courbe seule. Ce qui les separe est l'etage
    de chroma, qui lit le triplet entier.

    La mesure porte donc sur ce que l'etage de chroma **ajoute**, sur le pire couple
    confondu de chaque capture: la separation restituee passe de zero (courbe seule) a
    une valeur strictement positive. La confusion est **attenuee et non eliminee** --
    c'est la reponse que l'AC 3 autorise explicitement, chiffre a l'appui, et elle vaut
    parce que le defaut mesure du prototype portait sur les **neutres**, que la forme
    retenue rend exactement (test precedent).
    """
    for name in REAL_CAPTURES:
        value_ids, measured, reference, neutral = _real_capture(name)
        profile = cc.fit_correction_tone_chroma(measured, reference, neutral)
        # Meme courbe, etage de chroma neutralise: c'est la variante « courbe seule ».
        tone_only = cc.ToneCurveCorrectionProfile(
            tone_anchors_in=profile.tone_anchors_in,
            tone_anchors_out=profile.tone_anchors_out,
            chroma_matrix=np.eye(2))
        avec = _corrected(profile, measured)
        sans = _corrected(tone_only, measured)

        pires = [
            (abs(reference[i, channel] - reference[j, channel]) * 255, i, j, channel)
            for i in np.flatnonzero(neutral) for j in np.flatnonzero(~neutral)
            for channel in range(3)
            if abs(measured[i, channel] - measured[j, channel]) * 255 < 1.0
            and abs(reference[i, channel] - reference[j, channel]) * 255 > 30
        ]
        ecart_reference, i, j, channel = max(pires)
        sans_separation = abs(sans[i, channel] - sans[j, channel]) * 255
        avec_separation = abs(avec[i, channel] - avec[j, channel]) * 255
        assert sans_separation < 0.1 * ecart_reference, (
            f"{name}: la courbe seule restitue deja {sans_separation:.1f} codes sur "
            f"{ecart_reference:.0f}, la confusion n'est pas celle qu'on mesure")
        assert avec_separation > sans_separation, (
            f"{name}: l'etage de chroma ne separe rien sur {value_ids[i]} / "
            f"{value_ids[j]} (ecart de reference {ecart_reference:.0f} codes)")

        # **Le chiffre a l'appui** (finding de la revue de 5.20, ferme le 2026-08-19).
        # L'inegalite ci-dessus etait tout ce que ce test disait, alors que l'AC 3 exige
        # un chiffre -- et l'inegalite seule masquait que la marge vaut **0,04 code** sur
        # `rush-bitch-4-scan2`, c'est-a-dire du bruit. Les trois valeurs sont ecrites en
        # litteral: elles sont le fait mesure le 2026-08-13, pas une consequence de la
        # forme, et une reecriture de la forme doit les faire bouger.
        attendu = SEPARATION_RESTITUEE_PAR_L_ETAGE_DE_CHROMA[name]
        assert ecart_reference == pytest.approx(attendu["ecart_reference"], abs=0.01)
        assert avec_separation == pytest.approx(attendu["avec"], abs=0.01), name
        assert sans_separation == pytest.approx(attendu["sans"], abs=0.01), name
        assert (value_ids[i], value_ids[j]) == attendu["paire"], name


# --- AC 4 et 5 : le budget de distorsion, sur les trois captures --------------

def test_la_forme_nouvelle_tient_le_budget_de_distorsion_sur_les_trois_captures():
    """AC 2 et AC 4: **toutes** les captures, pas seulement les propres.

    C'est la consigne d'Egan sous sa forme executable. Les deux regimes d'acquisition y
    sont: pilote a correction desactivee (deux captures, mean dE76 brut ~15,4) et pilote
    a correction active (`12p5_test`, mean dE76 brut 30,6).
    """
    for name in REAL_CAPTURES:
        value_ids, measured, reference, neutral = _real_capture(name)
        profile = cc.fit_correction_tone_chroma(measured, reference, neutral)
        corrected = _corrected(profile, measured)
        verdict = cc.evaluate_acceptance(measured, corrected, reference,
                                         value_ids=value_ids)
        assert verdict.status == "applied", (
            f"{name}: {verdict.failure_reason} "
            f"(degradation moyenne {verdict.mean_degradation_de76:+.2f}, "
            f"neutre {verdict.max_neutral_degradation_de76:+.2f})")
        assert verdict.max_neutral_degradation_de76 <= 0.0, (
            f"{name}: la forme ne doit degrader **aucun** neutre, elle les ancre")
        assert verdict.distortion_budget_id == "color-distortion-budget-1"


def test_le_budget_distingue_toujours_la_forme_en_vigueur_sur_la_capture_la_plus_deformee():
    """AC 4 amende par `EPIC5-ARB-78`: le critere doit toujours **distinguer**, il ne
    refuse plus.

    Regime mesure le 2026-08-13, et c'est le motif litteral d'`EPIC5-ARB-72`: sur la
    capture au pilote HP a reglage actif, `color-correction-affine-matrix-1` fait passer
    le blanc du treillis de 0,3 dE76 de sa reference (il etait deja juste avant
    correction) a 6,7 apres. C'est la correction qui deforme, pas le scan.

    **Ce que le test verifie apres l'amendement**: la capture fautive et les deux captures
    propres restent **discernables au document** -- `distortion_budget_met` faux d'un cote,
    vrai de l'autre -- alors que les trois sont desormais `applied`. Sans le second volet,
    une mesure devenue constante passerait ce test; sans le premier, on ne verrait pas que
    le refus a bien disparu.
    """
    mesures = {}
    for name in REAL_CAPTURES:
        value_ids, measured, reference, neutral = _real_capture(name)
        profile = cc.fit_correction(measured, reference, neutral)
        corrected = _corrected(profile, measured)
        verdict = cc.evaluate_acceptance(measured, corrected, reference,
                                         value_ids=value_ids)
        mesures[name] = verdict

    fautive = mesures["12p5_test"]
    assert fautive.status == "applied", (
        "plus aucun seuil de couleur ne refuse une page (`EPIC5-ARB-78`)")
    assert fautive.failure_reason is None
    assert fautive.distortion_budget_met is False, (
        "le depassement de la capture la plus deformee reste publie")
    # Le plafond est **lu au registre**, jamais recopie ici: un litteral dans le test
    # rendrait le registre decoratif du cote de la verification aussi.
    budget = cc.get_distortion_budget(cc.ACTIVE_DISTORTION_BUDGET_ID)
    assert fautive.max_neutral_degradation_de76 > budget.max_neutral_degradation_de76, (
        fautive.max_neutral_degradation_de76)
    for propre in ("scan-WIN", "rush-bitch-4-scan2"):
        assert mesures[propre].status == "applied", propre
        assert mesures[propre].distortion_budget_met is True, (
            f"{propre}: une mesure qui declarerait tout hors budget ne distinguerait "
            "plus rien")


def test_les_seuils_absolus_ne_refusent_plus_aucune_des_trois_captures():
    """AC 5: `color-acceptance-1` reste **calcule et consultable**, jamais bloquant.

    Le fait qui a declenche la story: les trois captures reelles sont toutes au-dela des
    8,0 dE76 de moyenne du registre, avec la forme nouvelle comme avec les anciennes --
    et le tirage qui a valide la methode le 2026-08-11 l'etait aussi (11,66 dE76, rejoue
    le 2026-08-13). Le seuil est donc rapporte, il ne refuse plus.
    """
    for name in REAL_CAPTURES:
        value_ids, measured, reference, neutral = _real_capture(name)
        profile = cc.fit_correction_tone_chroma(measured, reference, neutral)
        corrected = _corrected(profile, measured)
        verdict = cc.evaluate_acceptance(measured, corrected, reference,
                                         value_ids=value_ids)
        assert verdict.mean_delta_e > 8.0, (
            f"{name}: la capture ne franchit plus le seuil, ce test perdrait son objet")
        assert verdict.detail.acceptance_thresholds_met is False
        assert verdict.status == "applied"
    assert "color-acceptance-1" in cc.COLOR_ACCEPTANCE_REGISTRY


# --- AC 7 : le plancher d'encrage rejoint la garde des sondes d'ombre ---------

def test_exclure_le_niveau_le_plus_sombre_du_treillis_ameliore_le_residu():
    """AC 7, mesure de 2026-08-13 sur `scan-WIN`: **14,09 -> 13,41** dE76 moyen.

    Le test rejoue la mesure au lieu de la citer: c'est elle qui justifie l'exclusion, et
    une exclusion dont l'effet n'est pas verifie se relit comme un gout. L'ecart est
    exige **strictement positif sur les trois captures** -- si le point aidait sur l'une
    d'elles, l'AC 7 serait a rouvrir et non a tenir.
    """
    for name in REAL_CAPTURES:
        gains = []
        for exclude in (False, True):
            _ids, measured, reference, neutral = _real_capture(
                name, exclude_ink_floor=exclude)
            profile = cc.fit_correction(measured, reference, neutral)
            corrected = _corrected(profile, measured)
            gains.append(float(
                cc.delta_e76_srgb_d65(corrected, reference).mean()))
        avec, sans = gains
        assert sans < avec, f"{name}: exclure le plancher degrade ({sans} >= {avec})"
    # Le chiffre publie, sur la capture ou il a ete mesure.
    _ids, measured, reference, neutral = _real_capture(
        "scan-WIN", exclude_ink_floor=False)
    avec = float(cc.delta_e76_srgb_d65(
        _corrected(cc.fit_correction(measured, reference, neutral), measured),
        reference).mean())
    assert avec == pytest.approx(14.09, abs=0.02)


def test_le_plancher_d_encrage_ne_deplace_pas_les_pastilles_imprimees():
    """AC 7, **frontiere negative**: l'exclusion porte l'ajustement, pas l'impression.

    Le meme filtre pose dans `calibration_lattice_adjustment_values` retirerait une
    pastille de la grille imprimee, donc deplacerait toutes les suivantes -- et les pages
    deja tirees (le tirage `chendj-mat`, 130 pastilles) ne se reliraient plus aux
    positions ou elles ont ete imprimees. Le cardinal place est donc epingle.
    """
    values = patch_values.calibration_lattice_adjustment_values()
    exclues = set(patch_values.ink_floor_lattice_value_ids())
    assert exclues, "aucune valeur sous le plancher: ce test serait vide"
    assert exclues <= {value.value_id for value in values}, (
        "les valeurs exclues de l'ajustement restent **imprimees**")
    placees = patch_presets.resolve_calibration_page_patches("tpl-a4-portrait-8f-v2")
    assert len(placees) == 2 * len(values) == 130


def test_le_jeu_d_ajustement_du_treillis_perd_le_plancher_et_lui_seul():
    """AC 7 vue depuis le producteur de production, `lattice_adjustment_source`.

    **La forme est nommee** (story 5.21): l'exclusion du plancher est la politique de la
    forme affine (`EPIC5-ARB-77`), pas celle du defaut de production. Sous la forme active
    le plancher est **garde**, et c'est ce que verifie le test parametre
    `test_le_jeu_du_treillis_suit_la_politique_de_plancher_de_sa_forme` un peu plus bas.
    """
    lattice = {value.value_id: value
               for value in patch_values.calibration_lattice_values()}
    value_ids = tuple(sorted(REAL_CAPTURES["scan-WIN"]))
    measured = np.asarray(
        [REAL_CAPTURES["scan-WIN"][value_id] for value_id in value_ids],
        dtype=np.float64) / 255.0
    source = cc.lattice_adjustment_source(measured, value_ids,
                                         source_page_id="page-de-calibration",
                                         correction_form_id=cc.CORRECTION_FORM_ID)
    exclues = set(patch_values.ink_floor_lattice_value_ids())
    assert exclues & set(value_ids), "le plancher doit etre present a l'entree"
    assert not exclues & set(source.value_ids)
    # Et rien d'autre n'est perdu: le filtre de saturation ne mord pas ici, les
    # mesures venant du treillis **deja filtre** qui est imprime sur la page.
    assert set(source.value_ids) == set(value_ids) - exclues
    assert source.read_patch_count == len(value_ids)
    assert source.retained_patch_count == len(value_ids) - len(exclues & set(value_ids))


# --- AC 7 rouverte pour la forme nouvelle : `EPIC5-ARB-77` --------------------

def _capture_complete(name):
    """Une capture reelle **avec** son plancher d'encrage, ordre du treillis conserve.

    Fabrique distincte de `_real_capture`, qui applique le filtre de production: ici on
    veut les 125 valeurs telles que la page les porte, y compris celle que l'AC 7
    retirait inconditionnellement avant `EPIC5-ARB-77`.
    """
    lattice = {value.value_id: value
               for value in patch_values.calibration_lattice_values()}
    measured_map = REAL_CAPTURES[name]
    value_ids = tuple(sorted(measured_map))
    measured = np.asarray(
        [measured_map[value_id] for value_id in value_ids], dtype=np.float64) / 255.0
    reference = np.asarray(
        [np.asarray(lattice[value_id].rgb[::-1], dtype=np.float64) / 255.0
         for value_id in value_ids], dtype=np.float64)
    neutral = np.asarray(
        [len(set(lattice[value_id].rgb)) == 1 for value_id in value_ids], dtype=bool)
    return value_ids, measured, reference, neutral


#: Gain moyen en dE76 apporte par l'exclusion du plancher, **par forme et par capture**,
#: mesure le 2026-08-13 (revue de 5.20, rejouee a l'application d'`EPIC5-ARB-77`).
#: Positif = l'exclusion aide. C'est le tableau qui a rouvert l'AC 7.
GAIN_ATTENDU_DE_L_EXCLUSION = {
    cc.CORRECTION_FORM_ID: {
        "scan-WIN": +0.686, "rush-bitch-4-scan2": +0.710, "12p5_test": +0.006},
    cc.CORRECTION_FORM_TONE_CHROMA_ID: {
        "scan-WIN": -1.407, "rush-bitch-4-scan2": -1.408, "12p5_test": -0.870},
}


@pytest.mark.parametrize("form_id", sorted(GAIN_ATTENDU_DE_L_EXCLUSION))
def test_l_effet_de_l_exclusion_du_plancher_change_de_signe_selon_la_forme(form_id):
    """`EPIC5-ARB-77`: l'exclusion aide la forme affine et **degrade** la forme nouvelle.

    Le test rejoue les six mesures au lieu de les citer -- c'est leur **signe** qui
    decide de la politique, et une politique dont l'effet n'est pas verifie se relit
    comme un gout. Les deux formes sont parcourues dans le meme test parametre pour que
    l'assertion soit comparative: une mesure faite sur la seule forme nouvelle ne dirait
    pas que le signe **change**, seulement qu'il est negatif.
    """
    attendu = GAIN_ATTENDU_DE_L_EXCLUSION[form_id]
    fit = cc.get_correction_form(form_id)
    for name in REAL_CAPTURES:
        residus = {}
        for exclude in (False, True):
            _ids, measured, reference, neutral = _real_capture(
                name, exclude_ink_floor=exclude)
            corrected = _corrected(fit(measured, reference, neutral), measured)
            residus[exclude] = float(
                cc.delta_e76_srgb_d65(corrected, reference).mean())
        gain = residus[False] - residus[True]
        assert gain == pytest.approx(attendu[name], abs=0.01), (form_id, name, gain)
        # Et le signe, qui est ce que la politique lit -- assert separement, parce
        # qu'une tolerance de 0,01 sur +0,006 ne le contraint pas.
        exclut = cc.correction_form_excludes_ink_floor(form_id)
        assert exclut is (gain > 0.0), (
            f"{form_id}/{name}: la politique ({exclut}) contredit la mesure ({gain})")


def test_chaque_forme_du_registre_declare_sa_politique_de_plancher():
    """`EPIC5-ARB-77`, frontiere **negative**: le registre de politique est **total**.

    Une forme ajoutee demain sans entree ici heriterait sinon en silence de la politique
    de sa voisine -- et l'effet mesure vaut 2,1 dE76 d'ecart entre les deux politiques
    sur la forme nouvelle. C'est le meme refus de repli implicite que
    `get_correction_form` porte deja pour la forme elle-meme.
    """
    assert set(cc.CORRECTION_FORM_EXCLUDES_INK_FLOOR) == set(cc.CORRECTION_FORMS)
    # Les deux politiques sont representees: un registre qui rendrait `True` partout
    # satisferait l'egalite ci-dessus et ne dirait plus rien.
    assert set(cc.CORRECTION_FORM_EXCLUDES_INK_FLOOR.values()) == {True, False}
    assert cc.correction_form_excludes_ink_floor(cc.CORRECTION_FORM_ID) is True
    assert cc.correction_form_excludes_ink_floor(cc.CORRECTION_FORM_LAB_ID) is True
    assert cc.correction_form_excludes_ink_floor(
        cc.CORRECTION_FORM_TONE_CHROMA_ID) is False
    with pytest.raises(cc.UnknownCorrectionFormError):
        cc.correction_form_excludes_ink_floor("color-correction-inventee-1")


@pytest.mark.parametrize("form_id,attendu", [
    (cc.CORRECTION_FORM_ID, True),
    (cc.CORRECTION_FORM_LAB_ID, True),
    (cc.CORRECTION_FORM_TONE_CHROMA_ID, False),
])
def test_le_jeu_du_treillis_suit_la_politique_de_plancher_de_sa_forme(form_id, attendu):
    """`EPIC5-ARB-77` vue depuis le producteur de production.

    **La cible n'est pas en premiere position**, et c'est l'objet de la permutation:
    `lattice-008-008-008` est le premier identifiant du treillis dans l'ordre trie comme
    dans l'ordre de placement, donc un filtre fautif qui retirerait « le premier » au
    lieu de « celui sous le plancher » serait invisible sur l'ordre naturel. La
    permutation deplace le plancher en **derniere** position et emmene les mesures avec
    lui -- elle exerce donc aussi l'appariement positionnel entre identifiants et
    mesures, la classe critique de la politique de mutation.
    """
    value_ids, measured, _reference, _neutral = _capture_complete("scan-WIN")
    plancher = set(patch_values.ink_floor_lattice_value_ids())
    assert value_ids[0] in plancher, (
        "l'ordre naturel place bien la cible en tete: sans cela la permutation "
        "ci-dessous ne prouverait rien")

    ordre = [i for i, v in enumerate(value_ids) if v not in plancher] + \
            [i for i, v in enumerate(value_ids) if v in plancher]
    permutes = tuple(value_ids[i] for i in ordre)
    assert permutes[-1] in plancher and permutes[0] not in plancher

    for ids, mesures in ((value_ids, measured), (permutes, measured[ordre])):
        source = cc.lattice_adjustment_source(
            mesures, ids, source_page_id="page-de-calibration",
            correction_form_id=form_id)
        assert source.ink_floor_excluded is attendu
        garde = plancher & set(source.value_ids)
        assert garde == (set() if attendu else plancher), (form_id, ids[0])
        assert source.retained_patch_count == len(ids) - (len(plancher) if attendu else 0)
        # L'appariement mesure/identifiant survit a la permutation: la mesure rendue
        # pour un identifiant donne est **la sienne**, pas celle de son voisin.
        rendu = dict(zip(source.value_ids, source.measured_bgr))
        origine = dict(zip(ids, mesures))
        for value_id, valeur in rendu.items():
            assert valeur == pytest.approx(origine[value_id]), value_id


def test_un_jeu_filtre_pour_une_forme_est_refuse_par_l_autre():
    """`EPIC5-ARB-77`: les deux sens du desaccord de politique sont fautifs.

    Ni l'un ni l'autre ne se voit au resultat -- les deux rendent un profil plausible --,
    et l'ecart mesure vaut 1,4 dE76 de residu. Le transport affine <-> Lab, lui, reste
    licite: les deux formes partagent la politique, donc c'est bien **la politique** que
    la garde confronte et non l'identifiant de forme.
    """
    value_ids, measured, _reference, _neutral = _capture_complete("scan-WIN")
    pour_affine = cc.lattice_adjustment_source(
        measured, value_ids, source_page_id="p0",
        correction_form_id=cc.CORRECTION_FORM_ID)
    pour_courbe = cc.lattice_adjustment_source(
        measured, value_ids, source_page_id="p0",
        correction_form_id=cc.CORRECTION_FORM_TONE_CHROMA_ID)

    with pytest.raises(cc.InkFloorPolicyMismatchError) as sans_plancher:
        cc.fit_from_external_source(
            pour_affine, correction_form_id=cc.CORRECTION_FORM_TONE_CHROMA_ID)
    with pytest.raises(cc.InkFloorPolicyMismatchError) as avec_plancher:
        cc.fit_from_external_source(
            pour_courbe, correction_form_id=cc.CORRECTION_FORM_ID)
    # Le refus nomme la page et les deux politiques, sans quoi il ne dirait pas de quel
    # cote reconstruire le jeu.
    for leve in (sans_plancher, avec_plancher):
        assert "p0" in str(leve.value) and "EPIC5-ARB-77" in str(leve.value)

    # Temoins positifs, sans lesquels une garde qui refuserait **tout** passerait: la
    # forme pour laquelle le jeu est construit, et le transport entre les deux formes
    # qui partagent la politique.
    cc.fit_from_external_source(pour_affine, correction_form_id=cc.CORRECTION_FORM_ID)
    cc.fit_from_external_source(pour_affine,
                                correction_form_id=cc.CORRECTION_FORM_LAB_ID)
    cc.fit_from_external_source(
        pour_courbe, correction_form_id=cc.CORRECTION_FORM_TONE_CHROMA_ID)


def test_un_jeu_construit_a_la_main_ne_peut_pas_mentir_sur_son_plancher():
    """Finding de la revue de 5.20 (ferme le 2026-08-19): la garde du plancher d'encrage
    n'avait aucun domaine d'activation.

    `ensure_no_ink_floor_value_in_adjustment_set` n'etait appelee que dans
    `lattice_adjustment_source`, sur `kept_ids` -- un jeu que le filtre venait de
    produire trois lignes plus haut --, donc elle constatait et ne pouvait jamais lever.
    Son domaine reel est ici: `ExternalAdjustmentSource` est une dataclasse **publique**,
    et un jeu construit a la main ne passe par aucun filtre.

    Le desaccord de politique du test precedent ne le couvre pas: il lit ce que le jeu
    **dit** de lui (`ink_floor_excluded`), pas ce qu'il **porte**. Mesure le 2026-08-19
    avant correction: un jeu declarant `ink_floor_excluded=True` et portant quand meme
    `lattice-008-008-008` etait accepte, et rendait un `CorrectionProfile` d'apparence
    normale.
    """
    plancher = patch_values.ink_floor_lattice_value_ids()
    assert plancher == ("lattice-008-008-008",)
    value_ids, measured, reference, neutral = _capture_complete("scan-WIN")
    assert plancher[0] in value_ids, "la capture complete porte le plancher"

    menteur = cc.ExternalAdjustmentSource(
        source_page_id="page-a-la-main", value_ids=value_ids, measured_bgr=measured,
        reference_bgr=reference, neutral_mask=neutral,
        read_patch_count=len(value_ids), retained_patch_count=len(value_ids),
        ink_floor_excluded=True)
    with pytest.raises(patch_values.InkFloorValueInAdjustmentSetError) as leve:
        cc.fit_from_external_source(menteur, correction_form_id=cc.CORRECTION_FORM_ID)
    assert plancher[0] in str(leve.value)

    # Temoin positif 1: le meme jeu, ampute de la seule valeur fautive, passe. Sans lui
    # la garde pourrait refuser toute capture complete pour une autre raison.
    garde = np.asarray([value_id not in plancher for value_id in value_ids], dtype=bool)
    honnete = cc.ExternalAdjustmentSource(
        source_page_id="page-a-la-main", value_ids=tuple(
            value_id for value_id, keep in zip(value_ids, garde) if keep),
        measured_bgr=measured[garde], reference_bgr=reference[garde],
        neutral_mask=neutral[garde], read_patch_count=len(value_ids),
        retained_patch_count=int(garde.sum()), ink_floor_excluded=True)
    assert cc.fit_from_external_source(
        honnete, correction_form_id=cc.CORRECTION_FORM_ID).correction_id == \
        cc.CORRECTION_FORM_ID

    # Temoin positif 2: la garde **ne s'applique pas** a une forme qui garde le plancher.
    # Sans ce volet, elle refuserait la forme courbe+chroma sur toute page reelle -- le
    # plancher y est imprime, donc toujours mesure.
    assert cc.correction_form_excludes_ink_floor(
        cc.CORRECTION_FORM_TONE_CHROMA_ID) is False
    pour_courbe = cc.ExternalAdjustmentSource(
        source_page_id="page-a-la-main", value_ids=value_ids, measured_bgr=measured,
        reference_bgr=reference, neutral_mask=neutral,
        read_patch_count=len(value_ids), retained_patch_count=len(value_ids),
        ink_floor_excluded=False)
    assert cc.fit_from_external_source(
        pour_courbe,
        correction_form_id=cc.CORRECTION_FORM_TONE_CHROMA_ID).correction_id == \
        cc.CORRECTION_FORM_TONE_CHROMA_ID

    # Et le chemin de production reste indemne: le jeu qu'il construit passe la garde.
    produit = cc.lattice_adjustment_source(
        measured, value_ids, source_page_id="p0",
        correction_form_id=cc.CORRECTION_FORM_ID)
    assert plancher[0] not in produit.value_ids
    cc.fit_from_external_source(produit, correction_form_id=cc.CORRECTION_FORM_ID)


def test_le_desaccord_de_politique_n_est_pas_un_refus_de_terrain():
    """`EPIC5-ARB-77`: `InkFloorPolicyMismatchError` n'est **pas** une `ValueError`.

    `fit_lot_correction_from_page` enveloppe `fit_from_external_source` dans un
    `except ValueError` qui rend `FAILURE_UNDERDETERMINED_ADJUSTMENT`. Si la garde y
    entrait, une faute de programmation deviendrait une page de calibration declaree
    illisible, et le diagnostic serait adresse au scanner plutot qu'au code -- le meme
    piege que le vocabulaire ferme de l'AC 8 de 5.4b existe pour eviter.
    """
    assert not issubclass(cc.InkFloorPolicyMismatchError, ValueError)
    # Et le motif de terrain qu'elle ne doit pas usurper existe bien par ailleurs.
    assert cc.FAILURE_UNDERDETERMINED_ADJUSTMENT


# Le pendant **bout en bout** de cette politique -- `fit_lot_correction_from_page`
# filtre le treillis pour la forme qu'il ajuste -- est mesure dans
# `test_scan_calibration_application.py`, qui possede la fabrique de page de calibration
# reellement lisible (`build_page` sous `PRESSE_CALIBRATION`). Le recopier ici en
# fabriquerait une seconde, moins fidele, pour la meme propriete.


# --- Les gardes de la forme : quatre faux succes fermes ------------------------

def test_la_courbe_refuse_un_seul_ancrage_neutre():
    """Sur un ancrage unique `np.interp` rend une **constante**: toute la page ecrasee
    sur une clarte, resultat plausible donc non detecte."""
    measured, reference, neutral = _mixed_adjustment_set()
    seul = neutral.copy()
    seul[np.flatnonzero(seul)[1:]] = False
    with pytest.raises(cc.UnderdeterminedAdjustmentSet) as erreur:
        cc.fit_correction_tone_chroma(measured, reference, seul)
    assert erreur.value.reason == cc.REFUSAL_TONE_NEEDS_TWO_NEUTRALS


def test_la_courbe_refuse_des_ancrages_non_strictement_croissants():
    """Le regime du plancher d'encrage: deux references distinctes lues a la meme
    valeur. `np.interp` ne leve pas dessus, il rend des valeurs fausses sans le dire.

    La cible est placee **ailleurs qu'en premiere position**: ce sont les deuxieme et
    troisieme niveaux qui se confondent, pas les deux premiers.
    """
    measured, reference, neutral = _mixed_adjustment_set()
    fautif = measured.copy()
    fautif[2] = fautif[1]
    with pytest.raises(cc.UnderdeterminedAdjustmentSet) as erreur:
        cc.fit_correction_tone_chroma(fautif, reference, neutral)
    assert erreur.value.reason == cc.REFUSAL_TONE_ANCHORS_NOT_MONOTONE

    # Le regime **symetrique**, et c'est lui qui rend le tri stable inobservable
    # (finding de la revue de 5.20 sur les mutants d'ordre, mesure le 2026-08-19): deux
    # neutres de meme clarte de **reference** rendent deux sorties egales, donc non
    # strictement croissantes, donc refusees -- quelle que soit la permutation que le
    # tri a choisie entre elles. Le mutant qui retire `kind="stable"` est donc
    # equivalent, et c'est ce test qui le dit plutot qu'une note de revue: sur des
    # clartes distinctes les deux tris rendent la meme permutation, et sur des clartes
    # egales les deux echouent ici.
    egal = reference.copy()
    egal[2] = egal[1]
    with pytest.raises(cc.UnderdeterminedAdjustmentSet) as erreur_egal:
        cc.fit_correction_tone_chroma(measured, egal, neutral)
    assert erreur_egal.value.reason == cc.REFUSAL_TONE_ANCHORS_NOT_MONOTONE


def test_la_courbe_refuse_une_valeur_dite_neutre_dont_la_reference_est_coloree():
    """L'invariance de l'axe neutre est une **garantie**, donc son hypothese se verifie.

    Sans cette garde, un appelant qui marquerait neutre une valeur coloree ferait
    ancrer les trois canaux sur la seule composante bleue de sa reference, et la
    propriete annoncee deviendrait une declaration fausse.
    """
    measured, reference, neutral = _mixed_adjustment_set()
    reference = reference.copy()
    reference[2] = (0.55, 0.55, 0.62)
    with pytest.raises(cc.UnderdeterminedAdjustmentSet) as erreur:
        cc.fit_correction_tone_chroma(measured, reference, neutral)
    assert erreur.value.reason == cc.REFUSAL_NEUTRAL_REFERENCE_NOT_GREY


def test_la_chroma_refuse_un_jeu_sans_couleur():
    """Un jeu entierement neutre ne determine pas une 2x2, et le rang ne le dit pas.

    Mesure faite a l'ecriture, et c'est elle qui a fait ajouter la regle de cardinal:
    apres la courbe, un jeu entierement neutre a une chroma de l'ordre de **1e-5** --
    l'arrondi des coefficients publies de la matrice XYZ, pas zero. `lstsq` y voit deux
    valeurs singulieres du meme ordre, donc rang 2, et rend une matrice ajustee sur ce
    bruit: une correction arbitraire presentee comme valide. La garde de rang, seule,
    ne l'attrapait pas.
    """
    measured, reference, neutral = _grey_ladder(cast=(1.08, 1.02, 0.95))
    with pytest.raises(cc.UnderdeterminedAdjustmentSet) as erreur:
        cc.fit_correction_tone_chroma(measured, reference, neutral)
    assert erreur.value.reason == cc.REFUSAL_TONE_CHROMA_NEEDS_THREE_POINTS


def test_la_chroma_refuse_une_conception_de_rang_un():
    """La garde de rang garde son domaine propre: trois points de chroma **distincts**
    mais **colineaires** passent le cardinal et ne determinent pourtant qu'une droite.

    `lstsq` rendrait alors la solution de norme minimale, c'est-a-dire une projection
    sur cette droite: toutes les couleurs de la page ramenees sur un seul axe de
    chroma. Le construire demande de partir de Lab -- en BGR la colinearite ne se pose
    pas a la main --, ce que `linear_bgr_from_lab` permet exactement.
    """
    colineaire = cc.linear_bgr_from_lab(np.asarray(
        [[50.0, 10.0, 20.0], [60.0, 20.0, 40.0], [70.0, 30.0, 60.0]]))
    cible = cc.linear_bgr_from_lab(np.asarray(
        [[52.0, 8.0, 25.0], [61.0, 24.0, 33.0], [69.0, 27.0, 58.0]]))
    with pytest.raises(cc.UnderdeterminedAdjustmentSet) as erreur:
        cc.fit_tone_chroma(colineaire, cible)
    assert erreur.value.reason == cc.REFUSAL_TONE_CHROMA_RANK_DEFICIENT


def test_le_SEUIL_de_rang_est_ENCADRE_par_les_deux_conceptions_mesurees():
    """Le seuil n'est pas choisi, il est pris entre deux faits distants de 1e15.

    Sans ce banc, `SEUIL_DE_RANG_DE_LA_CHROMA` pourrait etre relache jusqu'a
    refuser des pages saines, ou resserre jusqu'a retrouver le plancher de
    bruit -- c'est-a-dire jusqu'a redevenir dependant de la machine, ce qui est
    exactement le defaut ferme le 2026-09-08.
    """
    colineaire = cc.linear_bgr_from_lab(np.asarray(
        [[50.0, 10.0, 20.0], [60.0, 20.0, 40.0], [70.0, 30.0, 60.0]]))
    saine = cc.linear_bgr_from_lab(np.asarray(
        [[50.0, 40.0, -30.0], [60.0, -20.0, 45.0], [70.0, 5.0, 5.0]]))

    def rapport(lineaire):
        lab = cc.lab_from_linear_bgr(np.atleast_2d(
            np.asarray(lineaire, dtype=np.float64)))
        valeurs = np.linalg.svd(lab[:, 1:3], compute_uv=False)
        return float(valeurs[-1] / valeurs[0])

    degeneree, franche = rapport(colineaire), rapport(saine)
    # L'anti-vacuite : les deux conceptions sont REELLEMENT de part et d'autre,
    # et de tres loin. Sans cette ligne, deux rapports egaux rendraient
    # l'encadrement vrai pour n'importe quel seuil.
    assert degeneree < 1e-14 < 1e-3 < franche
    assert degeneree < cc.SEUIL_DE_RANG_DE_LA_CHROMA < franche


@pytest.mark.parametrize("valeurs, deficiente", [
    ([1.0, 1e-11], True),          # sous le seuil : refus
    ([1.0, 1e-10], True),          # AU seuil : refus, la comparaison est large
    ([1.0, 1e-9], False),          # au-dessus : accepte
    ([83.666, 2.177e-15], True),   # le cas colineaire REEL, mesure
    ([83.666, 23.42], False),      # une conception franche
    ([1.0], True),                 # une seule valeur singuliere
    ([], True),                    # aucune
    ([0.0, 0.0], True),            # la plus grande est nulle
])
def test_le_predicat_de_rang_MORD_des_DEUX_cotes_du_seuil(valeurs, deficiente):
    """La frontiere elle-meme, jouee au seuil et de part et d'autre.

    Les trois derniers cas sont les degenerescences que le predicat doit
    absorber sans lever : une conception sans deux valeurs singulieres, et une
    dont la plus grande est nulle, sont deficientes par construction -- et un
    `ZeroDivisionError` a leur place serait le blocage sec que le depot refuse.
    """
    assert cc._est_de_rang_deficient(np.asarray(valeurs)) is deficiente


def test_le_message_de_refus_CITE_le_rapport_et_le_seuil():
    """Un refus qui ne dit pas de combien il refuse n'aide pas a le corriger."""
    colineaire = cc.linear_bgr_from_lab(np.asarray(
        [[50.0, 10.0, 20.0], [60.0, 20.0, 40.0], [70.0, 30.0, 60.0]]))
    cible = cc.linear_bgr_from_lab(np.asarray(
        [[52.0, 8.0, 25.0], [61.0, 24.0, 33.0], [69.0, 27.0, 58.0]]))
    with pytest.raises(cc.UnderdeterminedAdjustmentSet) as erreur:
        cc.fit_tone_chroma(colineaire, cible)
    message = str(erreur.value)

    # Le seuil est une CONSTANTE du module : il se cite tel quel.
    assert f"{cc.SEUIL_DE_RANG_DE_LA_CHROMA:.0e}" in message

    # Le rapport, lui, sort de `lstsq` donc de BLAS : il DEPEND DE LA MACHINE.
    # Le run 7 de la CI publique (2026-09-08) a rendu 1,06e-15 la ou cette
    # machine rend 2,6e-17 -- deux ordres de grandeur d'ecart, sur le meme
    # code et les memes entrees. Une frontiere qui epinglait l'exposant
    # mesurait donc la machine et non le message ; celle-ci verifie la
    # PROPRIETE qu'on veut vraiment du message : qu'il cite un rapport, et que
    # ce rapport soit effectivement sous le seuil qu'il cite. Elle est plus
    # forte que l'ancienne, puisqu'elle attrape en plus un message incoherent.
    cite = re.search(r"rapport de ([0-9.]+e[+-][0-9]+)", message)
    assert cite, f"le message ne cite aucun rapport : {message}"
    rapport = float(cite.group(1))
    assert 0.0 < rapport <= cc.SEUIL_DE_RANG_DE_LA_CHROMA


def test_les_refus_de_la_forme_entrent_dans_le_vocabulaire_d_echec_existant():
    """`UnderdeterminedAdjustmentSet` est un `ValueError`, donc `calibrate_page` et
    `fit_lot_correction_from_page` rendent `adjustment_set_underdetermined` sans qu'un
    second vocabulaire d'echec soit ouvert."""
    assert issubclass(cc.UnderdeterminedAdjustmentSet, ValueError)
    motifs = {cc.REFUSAL_TONE_NEEDS_TWO_NEUTRALS,
              cc.REFUSAL_TONE_ANCHORS_NOT_MONOTONE,
              cc.REFUSAL_NEUTRAL_REFERENCE_NOT_GREY,
              cc.REFUSAL_TONE_CHROMA_NEEDS_THREE_POINTS,
              cc.REFUSAL_TONE_CHROMA_RANK_DEFICIENT}
    assert len(motifs) == 5, "cinq faux succes distincts, cinq motifs distincts"


def test_les_bornes_synthetiques_encadrent_le_domaine_et_ne_le_plafonnent_pas():
    """Sans elles, `np.interp` **plafonne**: tout ce qui est plus sombre que le neutre
    le plus sombre ressortirait a la clarte de ce neutre, et le papier nu a 245.

    Le test verifie les deux bouts sur une entree hors du domaine mesure, et il verifie
    que la courbe reste **strictement croissante** de bout en bout: un plafonnement se
    lirait comme une egalite entre deux entrees distinctes.
    """
    measured, reference, neutral = _mixed_adjustment_set()
    profile = cc.fit_correction_tone_chroma(measured, reference, neutral)
    assert profile.tone_anchors_out[0] == 0.0
    assert profile.tone_anchors_out[-1] == 1.0
    sombre = np.full((1, 3), 0.001, dtype=np.float64)
    clair = np.full((1, 3), 0.999, dtype=np.float64)
    plus_sombre = cc.apply_tone_curve(profile.tone_anchors_in,
                                      profile.tone_anchors_out, cc.eotf(sombre) / 2)
    assert (plus_sombre < cc.apply_tone_curve(
        profile.tone_anchors_in, profile.tone_anchors_out, cc.eotf(sombre))).all()
    assert (cc.apply_tone_curve(profile.tone_anchors_in, profile.tone_anchors_out,
                                cc.eotf(clair)) < 1.0).all()


def test_la_forme_nouvelle_est_resolue_par_le_registre_dans_le_chemin_de_lot():
    """`fit_from_external_source` resout la forme par identifiant, sans ramification:
    la troisieme forme y entre sans que ce point soit rouvert (AC 1).

    Le jeu est construit **pour la forme qui l'ajuste** depuis `EPIC5-ARB-77`: la
    politique de plancher d'encrage depend de la forme, donc les deux appels portent le
    meme identifiant. C'est ce que `fit_lot_correction_from_page` fait en production.
    """
    value_ids = tuple(sorted(REAL_CAPTURES["scan-WIN"]))
    measured = np.asarray(
        [REAL_CAPTURES["scan-WIN"][value_id] for value_id in value_ids],
        dtype=np.float64) / 255.0
    source = cc.lattice_adjustment_source(
        measured, value_ids, source_page_id="p0",
        correction_form_id=cc.CORRECTION_FORM_TONE_CHROMA_ID)
    profile = cc.fit_from_external_source(
        source, correction_form_id=cc.CORRECTION_FORM_TONE_CHROMA_ID)
    assert profile.correction_id == cc.CORRECTION_FORM_TONE_CHROMA_ID
    assert isinstance(profile, cc.ToneCurveCorrectionProfile)
    # Et le plancher est bien **reste** dans le jeu que la forme a ajuste: sans cette
    # ligne le test passerait a l'identique sur la politique inverse.
    assert source.ink_floor_excluded is False
    assert set(patch_values.ink_floor_lattice_value_ids()) <= set(source.value_ids)


def test_le_silence_de_l_appelant_laisse_le_budget_informatif_sur_les_trois_captures():
    """AC 5 de la story 5.21: `EPIC5-ARB-78` (budget de distorsion informatif) doit
    rester vrai sur le chemin par lequel `cli.py` atteint desormais la forme active --
    c'est-a-dire **sans nommer** `correction_form_id` sur aucun des deux appels, exactement
    comme `fit_lot_correction_from_page` le fait en production.

    Sans ce test, une regression qui referait du budget un seuil bloquant *pour le defaut
    silencieux specifiquement* (par exemple un branchement conditionnel sur "la forme n'a
    pas ete nommee") passerait tous les tests existants: ils nomment tous la forme, cette
    story vient tout juste de le confirmer par lecture.
    """
    for name in REAL_CAPTURES:
        value_ids = tuple(sorted(REAL_CAPTURES[name]))
        measured = np.asarray(
            [REAL_CAPTURES[name][value_id] for value_id in value_ids],
            dtype=np.float64) / 255.0
        source = cc.lattice_adjustment_source(measured, value_ids, source_page_id=name)
        profile = cc.fit_from_external_source(source)
        assert profile.correction_id == cc.ACTIVE_CORRECTION_FORM_ID
        corrected = _corrected(profile, source.measured_bgr)
        verdict = cc.evaluate_acceptance(source.measured_bgr, corrected,
                                         source.reference_bgr,
                                         value_ids=source.value_ids)
        # `applied` partout, y compris `12p5_test` qui reste hors budget: le budget
        # informe, il ne refuse plus (`EPIC5-ARB-72`), et ce reste vrai par silence.
        assert verdict.status == "applied", (name, verdict.failure_reason)


def test_le_silence_de_l_appelant_laisse_la_garde_de_conditionnement_bloquante():
    """AC 5, pendant de la garde: `EPIC5-ARB-78` reste bloquant sur une feuille vierge
    quand personne ne nomme la forme, sur les deux appels du couple.

    Meme jeu degenere que `test_une_page_de_calibration_vierge_est_refusee_a_la_source`,
    rejoue sans y nommer de forme -- c'est la seule chose que ce test ajoute face a lui.
    """
    value_ids, vierge = _jeu_degenere()
    source = cc.lattice_adjustment_source(vierge, value_ids,
                                          source_page_id="calibration-vierge-silence")
    with pytest.raises(cc.UnderdeterminedAdjustmentSet) as erreur:
        cc.fit_from_external_source(source)
    assert erreur.value.reason == cc.REFUSAL_DESIGN_MATRIX_ILL_CONDITIONED


def test_le_point_d_entree_de_production_couvre_les_trois_captures_reelles(monkeypatch):
    """AC 6 de la story 5.21: `fit_lot_correction_from_page`, le point d'entree que
    `cli.py` appelle **sans jamais nommer de forme**, exerce sur les trois captures
    reelles de `chendj-mat`.

    Aucun raster redresse ne vit en fixture (`tests/fixtures/` ne porte aucun TIFF,
    CLAUDE.md): ce que `sample_patches` en extrairait est **injecte directement** -- les
    mesures reelles de `REAL_CAPTURES`, reordonnees sur les pastilles que le gabarit
    resout reellement pour la page de calibration. Tout le reste de la fonction tourne
    sans double: validation du dpi, resolution de la forme par le registre, enchainement
    `lattice_adjustment_source` -> `fit_from_external_source`, construction du
    `LotCorrection` et de son verdict d'acceptation.
    """
    template_id = "tpl-a4-portrait-4f-v2"
    patches = patch_presets.resolve_calibration_page_patches(template_id)
    patch_ids = {patch.value_id for patch in patches}
    for name, mesures in REAL_CAPTURES.items():
        assert set(mesures) == patch_ids, (
            f"{name}: le gabarit doit porter exactement les valeurs que la capture "
            "mesure, sans quoi le reordonnancement ci-dessous serait un remplissage "
            "muet plutot qu'une reprojection fidele")

    resultats = {}
    for name, mesures in REAL_CAPTURES.items():
        def _sample_patches_factice(_page, layout, _dpi, _mesures=mesures):
            valeurs = np.asarray(
                [_mesures[patch.value_id] for patch in layout],
                dtype=np.float64) / 255.0
            return valeurs, tuple(patch.value_id for patch in layout)

        monkeypatch.setattr(cc, "sample_patches", _sample_patches_factice)
        page_factice = np.full((16, 16, 3), 255, dtype=np.uint8)
        resultats[name] = cc.fit_lot_correction_from_page(
            page_factice, template_id=template_id, dpi=600,
            source_page_id=f"{name}-p0")

    for name in ("scan-WIN", "rush-bitch-4-scan2"):
        lot = resultats[name]
        assert lot.available, (name, lot.failure_reason, lot.failure_message)
        assert lot.correction_form_id == cc.ACTIVE_CORRECTION_FORM_ID
        assert lot.acceptance is not None and lot.acceptance.status == "applied", (
            name, lot.acceptance.failure_reason if lot.acceptance else None)

    # `12p5_test` -- documente, chiffre, pas suppose (AC 6). Ce que ce test mesure et
    # que `test_le_budget_distingue_toujours_la_forme_en_vigueur_...` ne mesure pas: ce
    # dernier tient le budget hors de portee sous la forme **affine** (`fit_correction`);
    # ici, par le vrai point d'entree de production et sous la forme **active**, avec la
    # vraie politique de plancher d'encrage de cette forme (le plancher **reste** dans le
    # jeu, `EPIC5-ARB-77`), `12p5_test` tient elle aussi le budget: `distortion_budget_met`
    # est **vrai** et la degradation neutre maximale est negative (une amelioration, pas
    # une degradation) -- mesure du 2026-08-14, -0,27 dE76. C'est le fait, pas une reprise
    # de l'attendu d'un autre test: 12p5_test ne se distingue plus des deux autres
    # captures une fois le plancher correctement conserve pour cette forme.
    douze = resultats["12p5_test"]
    assert douze.available, (douze.failure_reason, douze.failure_message)
    assert douze.correction_form_id == cc.ACTIVE_CORRECTION_FORM_ID
    assert douze.acceptance is not None
    assert douze.acceptance.status == "applied", douze.acceptance.failure_reason
    assert douze.acceptance.distortion_budget_met is True, (
        "mesure du 2026-08-14: 12p5_test tient le budget par le vrai chemin de "
        "production -- si ce n'est plus vrai, le chiffre document ci-dessus a change "
        "et doit etre requalifie, pas simplement ajuste")
    assert douze.acceptance.max_neutral_degradation_de76 is not None
    assert douze.acceptance.max_neutral_degradation_de76 <= 0.0, (
        f"degradation neutre maximale mesuree: "
        f"{douze.acceptance.max_neutral_degradation_de76:+.2f} dE76")


def test_la_forme_nouvelle_traverse_calibrate_page_sur_un_jeu_qui_n_est_pas_le_treillis():
    """AC 1: la forme est utilisable sur les **deux** jeux d'ajustement du depot.

    Le treillis porte cinq valeurs neutres, `patch-values-2` en porte quatre et
    six chromatiques -- deux jeux de cardinaux et de compositions differents. Une forme
    qui ne marcherait que sur l'un des deux ne serait pas une forme du registre, et le
    chemin de la planche d'images est celui que 5.19 a cable a la production.

    Le test parcourt les **trois** formes et non la seule nouvelle: c'est ce qui rend
    l'assertion comparative plutot que ponctuelle, et c'est aussi la non-regression que
    l'AC 1 demande sur les deux anciennes.
    """
    page = _synthetic_rectified_page()
    for form_id in cc.CORRECTION_FORMS:
        result = cc.calibrate_page(page, template_id="tpl-a4-portrait-2f-v1",
                                   patch_preset_id="patches-18-v2", dpi=600,
                                   correction_form_id=form_id)
        assert result.status == "applied", (form_id, result.failure_reason)
        assert result.correction_form_id == form_id
        assert result.profile is not None
        assert result.profile.correction_id == form_id
        # Le budget est evalue et rapporte dans les trois cas, pas seulement quand il
        # refuse: un critere dont on ne lit le chiffre qu'a l'echec n'est pas relisable.
        assert result.acceptance.distortion_budget_id == "color-distortion-budget-1"
        assert result.acceptance.max_neutral_degradation_de76 is not None


def test_le_seuil_de_l_axe_neutre_porte_sa_valeur_et_sa_derivation():
    """`EPIC5-ARB-75`: un seuil qu'aucun test n'epingle se relit comme un gout.

    La valeur est confrontee **et** encadree par les deux bornes qui l'ont produite, de
    sorte qu'une revision silencieuse casse le test pour le bon motif: le seuil doit
    rester au-dessus du pire cas nul mesure sur le transport entre les deux captures de
    la meme feuille physique (0,54 code) et loin sous l'ecart que le scan brut porte
    lui-meme sur ses propres neutres (2,0 a 3,0 codes selon la capture).

    La borne basse est **mesuree ici**, pas recopiee: le transport croise est rejoue sur
    les deux captures propres, dans les deux sens.
    """
    assert cc.NEUTRAL_AXIS_MAX_CHANNEL_SPREAD_8BIT == 1.5

    propres = ("scan-WIN", "rush-bitch-4-scan2")
    pire_transport = 0.0
    for source, cible in (propres, propres[::-1]):
        _ids_s, mesures_s, references_s, neutres_s = _real_capture(source)
        _ids_c, mesures_c, references_c, neutres_c = _real_capture(cible)
        profile = cc.fit_correction_tone_chroma(mesures_s, references_s, neutres_s)
        corrected = _corrected(profile, mesures_c)
        pire_transport = max(
            pire_transport,
            cc.neutral_axis_channel_spread_8bit(corrected, neutres_c))
    assert pire_transport > 0.0, (
        "un transport qui ne deplace rien ne mesure pas la distribution nulle")
    assert cc.NEUTRAL_AXIS_MAX_CHANNEL_SPREAD_8BIT > 2.0 * pire_transport, (
        f"le seuil ({cc.NEUTRAL_AXIS_MAX_CHANNEL_SPREAD_8BIT}) doit garder une marge "
        f"sur le pire cas nul mesure ({pire_transport:.2f} codes)")

    # Borne haute: l'ecart que le **scan brut** porte deja sur ses propres neutres est le
    # plancher physique de ce qu'une correction transportee peut atteindre. Un seuil au
    # niveau de ce plancher ne dirait plus rien de la correction.
    for name in REAL_CAPTURES:
        _ids, mesures, _references, neutres = _real_capture(name)
        brut = cc.neutral_axis_channel_spread_8bit(mesures, neutres)
        assert cc.NEUTRAL_AXIS_MAX_CHANNEL_SPREAD_8BIT < brut, (
            f"{name}: le seuil n'est plus sous l'ecart du scan brut ({brut:.2f})")


# ---------------------------------------------------------------------------
# `EPIC5-ARB-78` -- la garde de conditionnement, et les champs informatifs
# ---------------------------------------------------------------------------

def _jeu_degenere(*, niveau: float = 1.0, bruit_niveaux: tuple[float, ...] | None = None):
    """Une page de calibration **vierge**: identifiants distincts, mesures degenerees.

    Regle des fabriques, sous sa forme utile ici: la collection porte plusieurs elements
    **distinguables par leur identifiant et par leur reference** -- c'est bien un treillis
    complet --, et ce sont les **mesures** qui sont toutes egales par defaut. C'est
    exactement le regime de terrain: une feuille non imprimee traverse toutes les gardes
    geometriques, ses pastilles sont a leur place, et chacune lit le papier nu.

    `niveau` est un parametre parce que le papier ne lit pas forcement 1,0: un blanc
    ecrete lit 1,0, une feuille correctement exposee lit 0,95 a 0,98. La degenerescence
    ne depend pas du niveau, et un test ecrit sur le seul 1,0 laisserait croire le
    contraire.

    **`bruit_niveaux`, ajoute a la deuxieme passe de revue d'`EPIC5-ARB-78` (finding sur
    la regle des fabriques du CLAUDE.md)**: le remplissage uniforme ci-dessus ne rend
    visible aucune permutation ni aucune variation de valeur, et c'est precisement le
    regime fautif **realiste** -- feuille vierge **+ bruit de scanner**, celui qui a
    produit les chiffres de la premiere derivation du seuil -- qui n'etait jamais
    construit en fixture. Quand ce parametre est fourni, chaque pastille recoit un
    niveau **different** (cycle sur `bruit_niveaux` si plus court que le treillis): les
    mesures sont donc non-uniformes et distinguables. Le jeu reste degenere pour une
    raison **structurelle** et non numerique: chaque pastille reste exactement neutre
    (les trois canaux egaux **sur sa propre ligne**), donc les trois colonnes
    chromatiques de la matrice de conception restent des multiples scalaires l'une de
    l'autre ligne a ligne -- le rang reste au plus 2, quel que soit le cardinal de
    niveaux distincts portes par `bruit_niveaux`.
    """
    lattice = {value.value_id: value
               for value in patch_values.calibration_lattice_values()}
    value_ids = tuple(sorted(lattice))
    if bruit_niveaux is None:
        measured = np.full((len(value_ids), 3), float(niveau), dtype=np.float64)
    else:
        niveaux = np.asarray(
            [bruit_niveaux[index % len(bruit_niveaux)]
             for index in range(len(value_ids))],
            dtype=np.float64)
        measured = np.tile(niveaux[:, None], (1, 3))
    return value_ids, measured


def test_une_feuille_vierge_bruitee_reste_rang_deficiente():
    """La variante non-uniforme de `_jeu_degenere` (regle des fabriques, CLAUDE.md).

    Contre-epreuve indispensable en premiere ligne: sans elle, un remplissage constant
    passerait ce test aussi bien qu'un bruit reel -- c'est la meme fabrique qui produirait
    les deux, et seule l'assertion de non-uniformite les distingue.
    """
    _value_ids, bruite = _jeu_degenere(
        bruit_niveaux=(0.95, 0.97, 0.99, 1.0, 0.96, 0.98, 0.94))
    assert len(set(np.round(bruite[:, 0], 6).tolist())) > 1, (
        "la fixture doit porter plusieurs niveaux distincts, pas un remplissage uniforme")
    assert cc.design_matrix_rank_deficient(bruite)
    with pytest.raises(cc.UnderdeterminedAdjustmentSet) as erreur:
        cc.ensure_design_matrix_conditioned(bruite, source_page_id="calibration-bruitee")
    assert erreur.value.reason == cc.REFUSAL_DESIGN_MATRIX_ILL_CONDITIONED


@pytest.mark.parametrize("cardinal", [1, 2, 3])
def test_un_jeu_de_moins_de_quatre_mesures_est_rang_deficient_par_cardinal(cardinal):
    """Garde structurelle, premiere branche: moins de lignes que de colonnes (4).

    Vraie quelles que soient les valeurs -- meme des valeurs parfaitement distinctes et
    non colineaires ne suffisent pas a determiner 4 parametres libres avec moins de 4
    equations. Valeurs prises dans les captures reelles, jamais synthetiques a la main,
    pour que le test porte sur des triplets plausibles.
    """
    _ids, mesures, _reference, _neutre = _real_capture("scan-WIN")
    sous_ensemble = np.asarray(mesures[:cardinal], dtype=np.float64)
    assert cc.design_matrix_rank_deficient(sous_ensemble)


def test_un_jeu_legitime_d_au_moins_quatre_mesures_n_est_pas_rang_deficient():
    """Contre-epreuve: la garde structurelle ne doit pas mordre sur un jeu ordinaire,
    sans quoi elle refuserait toute page reelle plutot que la seule feuille vierge."""
    for name in REAL_CAPTURES:
        _ids, mesures, _reference, _neutre = _real_capture(name)
        assert not cc.design_matrix_rank_deficient(mesures), name


def test_une_page_de_calibration_vierge_est_refusee_a_la_source():
    """`EPIC5-ARB-78`: le regime que la garde de non-degradation attrapait en aval.

    Mesure faite a l'ecriture de 5.20 et reprise ici: une feuille vierge passe **toutes**
    les gardes geometriques -- ses mesures valent 1,0, donc elles sont dans les bornes de
    plausibilite dont la borne haute *est* 1,0, et le jeu porte bien deux neutres
    distincts au sens des identifiants. `lstsq` resout le systeme degenere sans lever, et
    la correction qui en sort est d'apparence normale, ajustee sur rien, et appliquee aux
    pixels de **toutes** les planches du lot.

    Ce que le test epingle et qui est le point de l'arbitrage: c'est un echec de
    **calcul** -- le systeme n'a pas de solution fiable --, donc il reste bloquant la ou
    les seuils de couleur ont cesse de l'etre.
    """
    for niveau in (1.0, 0.97):
        value_ids, measured = _jeu_degenere(niveau=niveau)
        source = cc.lattice_adjustment_source(
            measured, value_ids, source_page_id="calibration-vierge",
            correction_form_id=cc.CORRECTION_FORM_ID)
        with pytest.raises(cc.UnderdeterminedAdjustmentSet) as erreur:
            cc.fit_from_external_source(source,
                                        correction_form_id=cc.CORRECTION_FORM_ID)
        assert erreur.value.reason == cc.REFUSAL_DESIGN_MATRIX_ILL_CONDITIONED
        # Le refus nomme la page et dit le geste: sans cela il envoie chercher au hasard.
        assert "calibration-vierge" in str(erreur.value)
        assert "vierge" in str(erreur.value).lower()


@pytest.mark.parametrize("form", [
    cc.CORRECTION_FORM_ID, cc.CORRECTION_FORM_LAB_ID, cc.CORRECTION_FORM_TONE_CHROMA_ID])
def test_la_garde_de_conditionnement_vaut_pour_les_trois_formes(form):
    """La garde porte sur le **jeu de mesures**, pas sur une forme.

    C'est ce qui justifie de n'en ecrire qu'une: les trois formes resolvent des systemes
    differents, mais toutes les trois sur les memes mesures, et un jeu degenere les rend
    toutes les trois indeterminees. Une garde par forme dirait trois fois la meme chose
    avec trois nombres a maintenir.
    """
    value_ids, measured = _jeu_degenere()
    source = cc.lattice_adjustment_source(
        measured, value_ids, source_page_id="calibration-vierge",
        correction_form_id=form)
    with pytest.raises(cc.UnderdeterminedAdjustmentSet) as erreur:
        cc.fit_from_external_source(source, correction_form_id=form)
    assert erreur.value.reason == cc.REFUSAL_DESIGN_MATRIX_ILL_CONDITIONED


def test_le_refus_de_conditionnement_entre_dans_le_vocabulaire_d_echec_existant():
    """`EPIC5-ARB-78` **reutilise** `FAILURE_UNDERDETERMINED_ADJUSTMENT` au lieu d'ouvrir
    un motif neuf.

    Tranche par Egan dans l'arbitrage lui-meme: une feuille vierge est une variante de
    « pas de source utilisable », exactement ce que ce motif nomme deja. Le mecanisme qui
    rend cette reutilisation vraie est le typage de l'exception -- `ValueError`, donc
    rattrapee par le `except` de `fit_lot_correction_from_page` et de `calibrate_page` --
    et c'est lui que ce test epingle **par le comportement des deux fonctions**, pas par
    une tautologie de hierarchie de classes (finding de la deuxieme passe de revue,
    2026-08-14: la premiere version de ce test se contentait d'`issubclass`, et la
    docstring qu'il gardait affirmait a tort que `calibrate_page` rattrapait deja la garde
    -- faux au moment ou c'etait ecrit, elle ne l'appelait pas encore. Vrai depuis que
    `calibrate_page` appelle `ensure_design_matrix_conditioned` sur son regime local.)
    """
    # `fit_lot_correction_from_page` -- deja verifie ailleurs sur la meme fixture
    # (`test_une_page_de_calibration_vierge_est_refusee_a_la_source`), rejoue ici pour
    # que ce test reste falsifiable seul, sans dependre de l'ordre d'execution.
    value_ids, vierge = _jeu_degenere()
    source = cc.lattice_adjustment_source(
        vierge, value_ids, source_page_id="calibration-vierge",
        correction_form_id=cc.CORRECTION_FORM_ID)
    with pytest.raises(cc.UnderdeterminedAdjustmentSet) as leve_source_externe:
        cc.fit_from_external_source(source, correction_form_id=cc.CORRECTION_FORM_ID)
    assert leve_source_externe.value.reason == cc.REFUSAL_DESIGN_MATRIX_ILL_CONDITIONED

    # `calibrate_page`, regime local (une page qui s'ajuste sur ses propres pastilles):
    # toutes les pastilles lisent blanc, exactement le regime « feuille vierge » construit
    # cette fois par le vrai pipeline d'echantillonnage plutot que par une matrice a la
    # main.
    page = _synthetic_rectified_page(distort=lambda bgr: np.ones_like(bgr))
    resultat = cc.calibrate_page(page, template_id="tpl-a4-portrait-2f-v1",
                                 patch_preset_id="patches-18-v2", dpi=600)
    assert resultat.status == "failed"
    assert resultat.failure_reason == cc.FAILURE_UNDERDETERMINED_ADJUSTMENT
    assert resultat.profile is None
    assert "imprimee" in (resultat.failure_message or "").lower(), (
        "le message specifique de la garde doit survivre, pas le gabarit generique")

    assert issubclass(cc.UnderdeterminedAdjustmentSet, ValueError)
    assert cc.REFUSAL_DESIGN_MATRIX_ILL_CONDITIONED not in (
        cc.REFUSAL_TONE_NEEDS_TWO_NEUTRALS,
        cc.REFUSAL_TONE_ANCHORS_NOT_MONOTONE,
        cc.REFUSAL_NEUTRAL_REFERENCE_NOT_GREY,
        cc.REFUSAL_TONE_CHROMA_NEEDS_THREE_POINTS,
        cc.REFUSAL_TONE_CHROMA_RANK_DEFICIENT,
        cc.REFUSAL_LIGHTNESS_NEEDS_TWO_NEUTRALS,
        cc.REFUSAL_CHROMA_NEEDS_THREE_POINTS,
    ), "sept faux succes distincts, sept motifs distincts"


def test_le_seuil_de_conditionnement_porte_sa_valeur_et_sa_derivation():
    """`EPIC5-ARB-78`: un seuil qu'aucun test n'encadre se relit comme un gout.

    Les deux bornes de l'intervalle vide sont **rejouees ici** et non recopiees:

    * la distribution **nulle** -- les trois captures reelles, sous les deux politiques de
      plancher d'encrage, soit six jeux legitimes. Le seuil doit rester nettement
      au-dessus du pire d'entre eux, sans quoi la garde refuserait des pages parfaitement
      lisibles;
    * le regime **fautif** -- la feuille vierge, dont le conditionnement est ici
      litteralement infini (rang 1). Le seuil doit rester nettement dessous.

    Le troisieme volet est celui qui empeche une garde decorative: sur les six jeux
    legitimes, `fit_from_external_source` doit **passer**.
    """
    assert cc.MAX_DESIGN_MATRIX_CONDITION_NUMBER == 30.0

    pire_legitime = 0.0
    for name in REAL_CAPTURES:
        for form in (cc.CORRECTION_FORM_ID, cc.CORRECTION_FORM_TONE_CHROMA_ID):
            value_ids = tuple(sorted(REAL_CAPTURES[name]))
            measured = np.asarray(
                [REAL_CAPTURES[name][value_id] for value_id in value_ids],
                dtype=np.float64) / 255.0
            source = cc.lattice_adjustment_source(
                measured, value_ids, source_page_id=name, correction_form_id=form)
            conditionnement = cc.design_matrix_condition_number(source.measured_bgr)
            pire_legitime = max(pire_legitime, conditionnement)
            # Temoin positif: sans lui, une garde qui refuserait **tout** satisferait
            # l'encadrement numerique sans qu'aucun test ne s'en apercoive.
            cc.fit_from_external_source(source, correction_form_id=form)
    assert pire_legitime > 1.0, (
        "un conditionnement de 1 signalerait une fabrique degeneree, pas un jeu reel")
    assert cc.MAX_DESIGN_MATRIX_CONDITION_NUMBER > 2.5 * pire_legitime, (
        f"le seuil ({cc.MAX_DESIGN_MATRIX_CONDITION_NUMBER}) doit garder une marge sur "
        f"le pire jeu legitime mesure ({pire_legitime:.3f})")

    _value_ids, vierge = _jeu_degenere()
    assert not np.isfinite(cc.design_matrix_condition_number(vierge)) \
        or cc.design_matrix_condition_number(vierge) > 100.0 \
        * cc.MAX_DESIGN_MATRIX_CONDITION_NUMBER, (
        "la feuille vierge doit rester tres loin au-dessus du seuil")


def test_le_conditionnement_ne_juge_pas_une_couleur_mais_un_calcul():
    """Frontiere **negative** d'`EPIC5-ARB-78`: la garde qui reste bloquante ne doit pas
    etre un seuil de couleur deguise.

    La preuve est un couplage: une capture reelle dont la correction sort **hors budget**
    de distorsion -- `12p5_test` sous la forme en vigueur, le regime que le budget refusait
    encore ce matin -- doit passer la garde de conditionnement sans encombre. Si le
    conditionnement mordait sur la deformation plutot que sur la resolubilite, les deux
    verdicts coincideraient et on aurait simplement renomme le refus.
    """
    value_ids, measured, reference, neutral = _real_capture("12p5_test")
    profile = cc.fit_correction(measured, reference, neutral)
    verdict = cc.evaluate_acceptance(measured, _corrected(profile, measured), reference,
                                     value_ids=value_ids)
    assert verdict.distortion_budget_met is False, (
        "le cas n'a d'interet que si cette capture sort bien du budget")
    conditionnement = cc.design_matrix_condition_number(measured)
    assert conditionnement < cc.MAX_DESIGN_MATRIX_CONDITION_NUMBER, conditionnement


def test_l_ecart_entre_canaux_de_l_axe_neutre_est_publie_par_le_verdict():
    """`EPIC5-ARB-78`, item n°2 de la revue de 5.20: la statistique de l'AC 6 avait ete
    ecrite par 5.20 et n'avait **aucun appelant**.

    Elle est desormais calculee a chaque verdict, sur la meme definition de « neutre » que
    le budget -- l'egalite exacte des trois canaux de la reference --, et publiee. Le test
    verifie les deux regimes que la story a mesures: la forme nouvelle annule l'ecart sur
    les trois captures reelles (invariance par construction), la forme en vigueur en
    laisse un mesurable. Une statistique qui rendrait toujours zero passerait le premier
    volet et pas le second.
    """
    for name in REAL_CAPTURES:
        value_ids, measured, reference, neutral = _real_capture(name)
        nouvelle = cc.fit_correction_tone_chroma(measured, reference, neutral)
        verdict = cc.evaluate_acceptance(
            measured, _corrected(nouvelle, measured), reference, value_ids=value_ids)
        assert verdict.neutral_axis_channel_spread_8bit == pytest.approx(0.0, abs=1e-4), (
            f"{name}: la forme nouvelle ancre l'axe neutre par construction")

        affine = cc.fit_correction(measured, reference, neutral)
        temoin = cc.evaluate_acceptance(
            measured, _corrected(affine, measured), reference, value_ids=value_ids)
        assert temoin.neutral_axis_channel_spread_8bit > 0.5, (
            f"{name}: la forme en vigueur laisse un ecart, et la statistique doit le "
            f"voir ({temoin.neutral_axis_channel_spread_8bit})")


def test_l_ecart_entre_canaux_vaut_None_quand_aucune_reference_n_est_grise():
    """`None` et non `0.0`: zero est la valeur d'un axe neutre parfait, donc l'ecrire ici
    publierait la meilleure lecture possible la ou rien n'a ete lu.

    C'est la meme regle que `max_neutral_degradation_de76` suit deja, et elle est
    verifiee sur le **verdict** parce que c'est lui qui atteint le manifest.
    """
    reference = np.asarray([[0.10, 0.15, 0.75], [0.20, 0.60, 0.25]])
    verdict = cc.evaluate_acceptance(reference, reference, reference)
    assert verdict.neutral_axis_channel_spread_8bit is None
    assert verdict.max_neutral_degradation_de76 is None
    # Contre-epreuve: une seule valeur grise ajoutee et la statistique existe.
    avec_gris = np.vstack([reference, [[0.5, 0.5, 0.5]]])
    assert cc.evaluate_acceptance(
        avec_gris, avec_gris, avec_gris).neutral_axis_channel_spread_8bit == \
        pytest.approx(0.0)


def test_le_budget_et_l_axe_neutre_sont_publies_au_manifest():
    """`EPIC5-ARB-78`: « calculees et publiees au manifest, en information seulement ».

    Le finding verse au `deferred-work.md` le 2026-08-13 -- « le budget de distorsion
    n'est pas publie au manifest » -- cesse d'etre differable des lors que le budget ne
    refuse plus rien: une page portait son motif sans le chiffre qui l'avait produit, elle
    ne porterait desormais **plus rien du tout**.

    La projection est verifiee sur le vrai producteur (`correction_provenance_summary`) et
    sur un vrai `AcceptanceVerdict`, jamais sur un objet de synthese: c'est la seule facon
    qu'un renommage de champ se voie.

    **Les valeurs attendues sont des litteraux independants, pas `verdict.<champ>`**
    (deuxieme passe de revue, `EPIC5-ARB-78`, 2026-08-14): la premiere version comparait
    le dict publie a l'objet dont il est recopie -- auto-referentiel, incapable de
    detecter une corruption **en amont** de la projection (un champ mal calcule
    resterait invisible: la projection recopierait fidelement une valeur deja fausse).
    Les litteraux ci-dessous sont mesures une fois sur `12p5_test` par le vrai pipeline
    (`fit_correction` + `evaluate_acceptance`) et pinnes, comme
    `MAX_DESIGN_MATRIX_CONDITION_NUMBER == 30.0` l'est ailleurs dans ce fichier.
    """
    value_ids, measured, reference, neutral = _real_capture("12p5_test")
    profile = cc.fit_correction(measured, reference, neutral)
    verdict = cc.evaluate_acceptance(measured, _corrected(profile, measured), reference,
                                     value_ids=value_ids)
    resultat = cc.PageCalibration(
        status="applied", values_version="", patch_preset_id="patches-14-v3",
        profile=None, acceptance=verdict, replicate_dispersion_de76=None,
        channel_relative_deviation_before_correction=None, clipping=None,
        correction_source=cc.CORRECTION_SOURCE_CALIBRATION_PAGE,
        correction_source_page_id="calibration-0")
    entree = cc.correction_provenance_summary(resultat)
    distorsion = entree["distortion"]
    assert distorsion["budget_id"] == "color-distortion-budget-1"
    assert distorsion["mean_degradation_de76"] == pytest.approx(-16.302899253136555)
    assert distorsion["max_neutral_degradation_de76"] == pytest.approx(6.430168843398678)
    assert distorsion["max_degradation_de76"] == pytest.approx(9.594500987939817)
    assert distorsion["worst_degradation_value_id"] == "lattice-068-068-008"
    assert distorsion["neutral_axis_channel_spread_8bit"] == pytest.approx(
        1.1774027907425761)
    assert distorsion["worst_neutral_value_id"] == "lattice-245-245-245"
    # Le booleen est publie **a cote** des mesures: seul, il redeviendrait le verdict
    # binaire que l'arbitrage retire; les mesures seules obligeraient chaque lecteur a
    # retrouver le registre pour les situer.
    assert distorsion["budget_met"] is False
    # Le bloc est **absent** quand rien n'a ete mesure: publier des zeros pour une page
    # refusee avant toute mesure serait le faux succes que ce module combat partout.
    sans_mesure = cc.PageCalibration(
        status="failed", values_version="", patch_preset_id="patches-14-v3",
        profile=None, acceptance=None, replicate_dispersion_de76=None,
        channel_relative_deviation_before_correction=None, clipping=None,
        failure_reason=cc.FAILURE_PATCHES_NOT_FOUND)
    assert "distortion" not in cc.correction_provenance_summary(sans_mesure)


def test_le_motif_du_choix_de_l_operateur_ne_se_confond_pas_avec_un_echec():
    """`EPIC5-ARB-78`, `--cc off`: « motif declare **distinct** du repli automatique ».

    Distinct sous **deux** aspects, et le test tient les deux parce qu'un seul ne
    suffirait pas: une cle differente de `failure_reason` -- un lecteur qui compte les
    pages en echec le fait sur la presence de ce champ -- et une valeur qui n'appartient
    pas au vocabulaire ferme des motifs d'echec de l'AC 8 de 5.4b.
    """
    # Le choix se lit desormais sur `LotCorrection.correction_requested` (deuxieme passe
    # de revue, `EPIC5-ARB-78`, 2026-08-14) -- deux objets, un par choix, plutot qu'un
    # second parametre passe a `calibration_page_result`.
    correction_refusee = cc.LotCorrection(
        source_page_id="calibration-0", template_id="tpl-a4-portrait-2f-v2",
        profile=object(), correction_form_id=cc.CORRECTION_FORM_ID,
        correction_requested=False)
    correction_appliquee = cc.LotCorrection(
        source_page_id="calibration-0", template_id="tpl-a4-portrait-2f-v2",
        profile=object(), correction_form_id=cc.CORRECTION_FORM_ID)
    refuse = cc.calibration_page_result(correction_refusee, patch_preset_id="patches-14-v3")
    applique = cc.calibration_page_result(correction_appliquee,
                                          patch_preset_id="patches-14-v3")
    assert refuse.status == applique.status == cc.color_pipeline_not_applied(), (
        "le statut ne gagne pas une quatrieme valeur: le vocabulaire du contrat 5.5 "
        "est ferme, et `encode` n'a pas a apprendre un mot pour un fait qu'il traite")
    assert refuse.not_applied_reason == cc.NOT_APPLIED_OPERATOR_OPT_OUT
    assert applique.not_applied_reason is None, (
        "sans ce volet, un champ pose systematiquement ne distinguerait rien")
    assert refuse.failure_reason is None, "rien n'a echoue: c'est un choix"

    entree = cc.correction_provenance_summary(refuse)
    assert entree["not_applied_reason"] == cc.NOT_APPLIED_OPERATOR_OPT_OUT
    assert "failure_reason" not in entree
    assert "not_applied_reason" not in cc.correction_provenance_summary(applique)
    # Le motif n'entre pas dans le vocabulaire ferme des echecs, et c'est structurel.
    assert cc.NOT_APPLIED_OPERATOR_OPT_OUT not in {
        cc.FAILURE_PATCHES_NOT_FOUND, cc.FAILURE_PATCHES_OUT_OF_RANGE,
        cc.FAILURE_REPLICATE_DISPERSION, cc.FAILURE_UNKNOWN_PATCH_PRESET,
        cc.FAILURE_UNKNOWN_VALUES_VERSION, cc.FAILURE_UNKNOWN_GAMUT_MAP,
        cc.FAILURE_PLACEMENT_UNDEFINED, cc.FAILURE_UNDERDETERMINED_ADJUSTMENT,
        cc.FAILURE_INVALID_DPI, cc.FAILURE_NOT_THREE_CHANNELS,
        cc.FAILURE_PAGE_GEOMETRY_UNRESOLVED, cc.FAILURE_UNKNOWN_CORRECTION_FORM,
        cc.FAILURE_DEGRADES_RESIDUAL, cc.FAILURE_DISTORTION_BUDGET, cc.FAILURE_METRIC,
        cc.FAILURE_PAGE_DIVERGES,
    }


# ---------------------------------------------------------------------------
# Revue de 5.22 -- le verdict du profil de chaine, sa provenance, et l'ordre BGR
# ---------------------------------------------------------------------------


def _verdict_mesurable() -> cc.AcceptanceVerdict:
    """Un verdict d'acceptation dont **les douze grandeurs sont deux a deux distinctes**.

    Regle des fabriques appliquee a un enregistrement plat: une fabrique qui poserait la
    meme valeur partout rendrait invisible toute permutation de champs a la
    serialisation -- exactement la famille `M33`, transposee d'une collection a un
    dictionnaire. Chaque nombre est ici unique, donc un couple de champs echange se
    voit.

    Les valeurs ne sont opposees a aucun seuil et n'en recopient aucun (`EPIC5-ARB-52`):
    ce sont des mesures, et la relecture n'a pas de verdict a rendre.
    """
    return cc.AcceptanceVerdict(
        status="applied",
        mean_delta_e=3.25,
        max_delta_e=7.5,
        mean_delta_e_before=11.75,
        acceptance_id="color-acceptance-1",
        distortion_budget_id="color-distortion-budget-1",
        mean_degradation_de76=0.5,
        max_neutral_degradation_de76=1.25,
        max_degradation_de76=2.75,
        distortion_budget_met=True,
        neutral_axis_channel_spread_8bit=4.5,
    )


def _profil_affine_distinguable() -> cc.CorrectionProfile:
    """Un profil affine dont **aucune ligne n'est symetrique de son etage voisin**.

    `stage_a` porte un couple (gain, decalage) **par canal** -- forme (3, 2) -- et
    `stage_m` une matrice (3, 3): les deux etages sont donc distinguables par leur forme
    **et** par leurs valeurs, ce qui fait mourir le mutant « `stage_a` <-> `stage_m`
    echanges » de la campagne de la couche 2, survivant sur les fabriques du depot. Les
    trois canaux de `stage_a` different entre eux, sans quoi une permutation de canaux
    resterait invisible ici comme elle l'etait sur les ancres de tonalite.
    """
    return cc.CorrectionProfile(
        stage_a=np.array([[1.02, 0.01], [0.99, -0.02], [1.05, 0.03]], dtype=np.float64),
        stage_m=np.array([[0.90, 0.05, 0.02],
                          [0.03, 0.94, 0.06],
                          [0.01, 0.07, 0.88]], dtype=np.float64),
    )


def _document_de_profil(*, chain_id: str = "chaine-z",
                        acceptance: cc.AcceptanceVerdict | None = None,
                        profile=None) -> dict:
    """Le document que `scan calibrate` consigne, par son **vrai** projecteur."""
    return cc.profile_to_document(
        profile if profile is not None else _profil_affine_distinguable(),
        chain_id=chain_id,
        source_page_id="lot-a-p0",
        template_id="tpl-a4-portrait-2f-v2",
        read_patch_count=14,
        retained_patch_count=13,
        ink_floor_excluded=False,
        acceptance=acceptance,
    )


def test_le_verdict_consigne_dans_le_profil_se_relit_grandeur_par_grandeur():
    """Aller-retour de `_acceptance_document`, et il n'en existait **aucun**.

    Bloquant `C2` de la revue de 5.22: douze grandeurs etaient serialisees a chaque
    `scan calibrate` et un `grep '"acceptance"'` sur `src/` ne rendait que l'ecriture --
    aucun lecteur. Un champ que rien ne relit est du code mort; ce test est la moitie
    « lecture » qui le rend vivant.

    L'egalite porte sur **chaque** grandeur et non sur un agregat: deux champs echanges a
    la serialisation rendraient un verdict d'apparence normale, et c'est precisement le
    mode d'echec qu'une fabrique aux valeurs distinctes existe pour attraper.
    """
    verdict = _verdict_mesurable()
    relu = cc.acceptance_from_document(cc._acceptance_document(verdict))
    assert relu is not None
    for champ in ("status", "acceptance_id", "mean_delta_e", "max_delta_e",
                  "mean_delta_e_before", "distortion_budget_id",
                  "mean_degradation_de76", "max_neutral_degradation_de76",
                  "max_degradation_de76", "distortion_budget_met",
                  "neutral_axis_channel_spread_8bit"):
        assert getattr(relu, champ) == getattr(verdict, champ), champ
    # `detail` **ne se reconstruit pas**: il n'est pas serialise, et le fabriquer ferait
    # croire a des mesures par pastille qui n'ont jamais ete relues.
    assert relu.detail is None


def test_un_verdict_absent_du_profil_se_relit_none_et_jamais_a_zero():
    """« Aucune mesure » et « une mesure nulle » sont deux faits differents.

    Meme regle que `replicate_dispersion_de76` et `neutral_axis_channel_spread_8bit`:
    rendre un verdict a zero serait la lecture la plus flatteuse possible la ou rien n'a
    ete mesure.
    """
    assert cc.acceptance_from_document(cc._acceptance_document(None)) is None
    assert cc.acceptance_from_document({}) is None
    assert cc.acceptance_from_document(None) is None
    # Et le domaine ou la garde **mord**: un document peuple rend un verdict, sans quoi la
    # clause ci-dessus serait vraie pour toute entree et ne garantirait rien.
    assert cc.acceptance_from_document(
        cc._acceptance_document(_verdict_mesurable())) is not None


def test_les_valeurs_nulles_du_profil_ne_deviennent_pas_des_zeros():
    """Les trois grandeurs optionnelles restent `None` a la relecture.

    Elles valent `None` quand le jeu ne porte pas ce qu'il faut pour les mesurer -- pas
    d'axe neutre, pas de degradation maximale calculable. Un `float(None)` leverait; un
    repli sur `0.0` publierait « aucune degradation » la ou rien n'a ete lu.
    """
    partiel = cc.AcceptanceVerdict(
        status="applied", mean_delta_e=1.5, max_delta_e=2.5, mean_delta_e_before=6.5,
        acceptance_id="color-acceptance-1",
        distortion_budget_id="color-distortion-budget-1",
        mean_degradation_de76=0.25,
        max_neutral_degradation_de76=None, max_degradation_de76=None,
        distortion_budget_met=None, neutral_axis_channel_spread_8bit=None)
    relu = cc.acceptance_from_document(cc._acceptance_document(partiel))
    assert relu.max_neutral_degradation_de76 is None
    assert relu.max_degradation_de76 is None
    assert relu.neutral_axis_channel_spread_8bit is None
    assert relu.distortion_budget_met is None
    # Temoin positif sur les memes trois champs: le `None` ci-dessus vient de la donnee et
    # non d'une relecture qui perdrait tout.
    assert relu.mean_degradation_de76 == 0.25


def test_la_correction_de_chaine_porte_sa_provenance_et_le_verdict_du_profil():
    """Bloquants `C2` et `C3`: la provenance et la mesure voyagent avec la correction.

    Avant ce correctif, `chain_correction_from_document` rendait un `LotCorrection`
    indiscernable d'une correction ajustee sur la feuille du lot: rien dans l'objet ne
    disait qu'il venait d'un fichier de profil. Ses deux consommateurs devaient donc le
    **redeviner**, et `calibration_page_result` le redevinait faux.
    """
    verdict = _verdict_mesurable()
    correction = cc.chain_correction_from_document(
        _document_de_profil(chain_id="chaine-z", acceptance=verdict))
    assert correction.correction_source == cc.CORRECTION_SOURCE_CHAIN_PROFILE
    assert correction.chain_id == "chaine-z"
    # `acceptance` reste `None`: rien n'a ete remesure par cette passe, et l'y poser
    # attribuerait a ce scan une grandeur mesuree un autre jour.
    assert correction.acceptance is None
    # ... et le verdict relu voyage sous **son** nom.
    assert correction.imported_acceptance is not None
    assert correction.imported_acceptance.mean_degradation_de76 == (
        verdict.mean_degradation_de76)
    # `source_page_id` continue de designer la feuille qui a ajuste les coefficients: sans
    # elle, la seule trace de la page physique a rescanner serait perdue.
    assert correction.source_page_id == "lot-a-p0"


def test_un_profil_sans_verdict_ne_fabrique_pas_de_mesure():
    """Le domaine inerte de la garde precedente, sur la valeur livree.

    Un profil consigne avant que le verdict ne soit serialise -- ou par un `scan
    calibrate` qui n'a rien mesure -- porte `acceptance: {}`. La relecture doit rendre
    `None`, faute de quoi le manifest publierait douze zeros presentes comme mesures.
    """
    correction = cc.chain_correction_from_document(_document_de_profil(acceptance=None))
    assert correction.imported_acceptance is None
    entree = cc.correction_provenance_summary(
        cc.calibration_page_result(correction, patch_preset_id="patches-14-v3"))
    assert "chain_profile_acceptance" not in entree


def test_une_feuille_de_calibration_restee_dans_la_pile_ne_declare_pas_ses_pastilles():
    """Bloquant `C3`, et c'est la classe du mutant `M25` appliquee a la provenance.

    Le regime est **nominal**: l'operateur genere la page de calibration du lot `L`, la
    scanne, lance `scan ... calibrate` -- le profil consigne porte alors
    `source_page_id = "L-p0"` --, puis rescanne le lot `L` **avec la feuille restee dans
    la pile**. Le profil de chaine gagne, aucun pixel de cette feuille n'est lu, et
    pourtant l'appariement par identifiant tombe juste: son entree de manifest declarait
    `own_sheet_patches`, « la correction vient des pastilles de cette feuille », quand
    elle venait de `versions/calibration/<chain>.json`. La provenance des planches disait
    `chain_profile`, celle de la page de calibration du meme lot disait autre chose, et
    les deux decrivaient la meme passe.
    """
    correction = cc.chain_correction_from_document(
        _document_de_profil(chain_id="chaine-z", acceptance=_verdict_mesurable()))
    page = cc.calibration_page_result(correction, patch_preset_id="patches-14-v3")
    entree = cc.correction_provenance_summary(page)
    assert entree["correction_source"] == cc.CORRECTION_SOURCE_CHAIN_PROFILE
    assert entree["correction_chain_id"] == "chaine-z"
    # Le verdict du profil atteint le document, sous sa cle a lui: c'est le retour du
    # chemin que le bloquant `C2` avait coupe.
    assert entree["chain_profile_acceptance"]["mean_degradation_de76"] == 0.5
    # Et il n'est **pas** publie comme une mesure de ce scan: `distortion` vient de
    # `acceptance`, qui reste absent. Sans ce volet, les deux cles diraient la meme chose
    # et le manifest aurait deux verites pour un seul fait.
    assert "distortion" not in entree
    assert page.acceptance is None


def test_une_correction_ajustee_sur_la_feuille_du_lot_dit_toujours_ses_pastilles():
    """Le temoin symetrique, sans lequel le test precedent ne distinguerait rien.

    Une garde qui ne se verifie que dans le regime ou elle mord laisse passer la version
    qui repond la meme chose partout. Ici: la lecture sur l'objet doit rendre
    `own_sheet_patches` au repli, exactement comme le litteral qu'elle remplace.
    """
    correction = cc.LotCorrection(
        source_page_id="lot-a-p0", template_id="tpl-a4-portrait-2f-v2",
        profile=object(), correction_form_id=cc.CORRECTION_FORM_ID)
    entree = cc.correction_provenance_summary(
        cc.calibration_page_result(correction, patch_preset_id="patches-14-v3"))
    assert entree["correction_source"] == cc.CORRECTION_SOURCE_OWN_SHEET
    assert "correction_chain_id" not in entree
    assert "chain_profile_acceptance" not in entree


def test_un_echec_de_page_de_calibration_garde_la_provenance_de_sa_correction():
    """Un echec dont on ne sait pas d'ou la correction devait venir n'est pas relisable.

    Meme regle que pour `correction_form_id`, portee jusqu'ici par la branche disponible
    seulement. La branche d'echec lisait `own_sheet_patches` en litteral, ce qui est vrai
    aujourd'hui -- un profil de chaine ne produit pas d'echec de lot -- et le serait reste
    par accident: c'est exactement de cette facon que le litteral de la branche voisine
    est devenu faux.
    """
    echec = cc.LotCorrection(
        source_page_id="lot-a-p0", template_id="tpl-a4-portrait-2f-v2", profile=None,
        correction_form_id=cc.CORRECTION_FORM_ID,
        failure_reason=cc.FAILURE_PATCHES_NOT_FOUND,
        correction_source=cc.CORRECTION_SOURCE_CHAIN_PROFILE, chain_id="chaine-z")
    page = cc.calibration_page_result(echec, patch_preset_id="patches-14-v3")
    assert page.status == "failed"
    entree = cc.correction_provenance_summary(page)
    assert entree["correction_source"] == cc.CORRECTION_SOURCE_CHAIN_PROFILE
    assert entree["correction_chain_id"] == "chaine-z"
    assert entree["failure_reason"] == cc.FAILURE_PATCHES_NOT_FOUND
    # `not_applied_reason` reste **absent** sur un echec: un lecteur qui filtre les pages
    # en panne le fait sur la presence de `failure_reason`, et les deux ne se melangent
    # jamais.
    assert "not_applied_reason" not in entree


def test_le_verdict_du_profil_est_ignore_quand_la_page_s_ajuste_sur_elle_meme():
    """Les deux bouts de la garde de `calibrate_page`: inerte au repli, mordante au transport.

    Sans le volet inerte, un appelant qui passerait le verdict d'un profil dans le regime
    local ferait publier au manifest la degradation d'une correction que cette page n'a
    pas utilisee -- une mesure vraie, attribuee a la mauvaise passe.
    """
    def distort(bgr):
        return np.clip(cc.oetf(cc.eotf(bgr) * 0.92 + 0.03), 0.0, 1.0)

    verdict = _verdict_mesurable()
    page = _synthetic_rectified_page(distort=distort)

    local = cc.calibrate_page(page, template_id="tpl-a4-portrait-2f-v1",
                              patch_preset_id="patches-18-v2", dpi=600,
                              page_id="lot-a-p1", imported_acceptance=verdict)
    # Le regime est bien le regime nominal, et non un echec precoce qui rendrait la
    # clause suivante vraie pour une tout autre raison.
    assert local.status == "applied"
    assert local.chain_profile_acceptance is None, (
        "sans profil importe il n'y a aucun verdict importe: la valeur est ignoree")
    assert "chain_profile_acceptance" not in cc.correction_provenance_summary(local)

    # Le profil transporte est celui que **cette** page a produit: la garde de divergence
    # ne mord donc pas, et le regime mesure est bien celui d'une planche corrigee par un
    # profil venu d'ailleurs.
    transporte = cc.calibrate_page(
        page, template_id="tpl-a4-portrait-2f-v1", patch_preset_id="patches-18-v2",
        dpi=600, page_id="lot-a-p1", imported_profile=local.profile,
        imported_source_page_id="lot-a-p0",
        imported_correction_source=cc.CORRECTION_SOURCE_CHAIN_PROFILE,
        imported_chain_id="chaine-z", imported_acceptance=verdict)
    assert transporte.status == "applied"
    assert transporte.chain_profile_acceptance is verdict
    entree = cc.correction_provenance_summary(transporte)
    assert entree["chain_profile_acceptance"]["max_degradation_de76"] == 2.75
    assert entree["correction_chain_id"] == "chaine-z"
    # Les deux verdicts coexistent sans se recouvrir: `distortion` vient de la mesure de
    # **cette** passe, `chain_profile_acceptance` de celle consignee dans le profil. Sans
    # ce volet, une redaction qui ecraserait l'un par l'autre resterait verte.
    assert entree["distortion"]["mean_degradation_de76"] != (
        entree["chain_profile_acceptance"]["mean_degradation_de76"])


def test_les_ancres_de_tonalite_voyagent_dans_l_ordre_bgr_declare():
    """`E-F2` de la couche 2: une permutation de canaux etait **invisible**.

    `profile_to_document` documente que les coefficients voyagent « en ordre **BGR**
    documente », et c'est la propriete centrale du format: trois canaux echanges a la
    serialisation rendent un profil qui corrige toutes les images de travers, sans
    exception ni symptome. Or toutes les fabriques d'ancres du depot posaient des lignes
    aux trois canaux egaux (`[0.4, 0.4, 0.4]`), donc toute permutation etait l'identite
    sur la fixture: le mutant « chaque ligne renversee » survivait aux 17 tests de
    `test_calibration_profile.py`.

    Cette fabrique-ci rend les trois canaux **distincts sur chaque ligne** et les lignes
    distinctes entre elles: la permutation se voit, et l'ordre des ancres aussi.
    """
    profil = cc.ToneCurveCorrectionProfile(
        tone_anchors_in=np.array([[0.00, 0.01, 0.02],
                                  [0.40, 0.42, 0.38],
                                  [0.95, 0.97, 0.93]], dtype=np.float64),
        tone_anchors_out=np.array([0.0, 0.45, 1.0], dtype=np.float64),
        chroma_matrix=np.array([[0.98, 0.03], [0.05, 0.91]], dtype=np.float64))
    document = _document_de_profil(profile=profil)
    coefficients = document["coefficients"]
    # L'egalite est **ligne a ligne et canal a canal**, jamais un `allclose` global: c'est
    # ce qui distingue « les memes nombres » de « les memes nombres dans le meme ordre ».
    assert coefficients["tone_anchors_in"] == [[0.00, 0.01, 0.02],
                                               [0.40, 0.42, 0.38],
                                               [0.95, 0.97, 0.93]]
    assert coefficients["tone_anchors_out"] == [0.0, 0.45, 1.0]
    assert coefficients["chroma_matrix"] == [[0.98, 0.03], [0.05, 0.91]]

    relu = cc.profile_from_document(document)
    assert isinstance(relu, cc.ToneCurveCorrectionProfile)
    assert np.array_equal(relu.tone_anchors_in, profil.tone_anchors_in)
    assert np.array_equal(relu.tone_anchors_out, profil.tone_anchors_out)
    assert np.array_equal(relu.chroma_matrix, profil.chroma_matrix)


def test_les_deux_etages_de_la_forme_affine_ne_se_confondent_pas_a_la_serialisation():
    """`E-F3`: la forme affine n'etait ni serialisee ni rechargee par aucun test.

    D'ou le mutant « `stage_a` <-> `stage_m` echanges » qui survivait: rien ne construisait
    un `CorrectionProfile` a travers le couple document/profil. Intervertir les deux etages
    d'une correction affine change **tous** les pixels, sans erreur ni message.
    """
    profil = _profil_affine_distinguable()
    document = _document_de_profil(profile=profil)
    assert document["correction_form_id"] == cc.CORRECTION_FORM_ID
    assert document["coefficients"]["stage_a"] == [[1.02, 0.01],
                                                   [0.99, -0.02],
                                                   [1.05, 0.03]]
    assert document["coefficients"]["stage_m"] == [[0.90, 0.05, 0.02],
                                                   [0.03, 0.94, 0.06],
                                                   [0.01, 0.07, 0.88]]
    relu = cc.profile_from_document(document)
    assert isinstance(relu, cc.CorrectionProfile)
    assert np.array_equal(relu.stage_a, profil.stage_a)
    assert np.array_equal(relu.stage_m, profil.stage_m)
    # Et la sortie, qui est ce que l'`AC 1` promet: le profil recharge applique la meme
    # correction que celui d'origine. Les deux etages ayant des formes differentes, un
    # echange leverait -- mais l'egalite des pixels est la propriete demandee.
    lumiere = np.array([[0.2, 0.35, 0.5], [0.6, 0.45, 0.3]], dtype=np.float64)
    assert np.allclose(relu.apply_linear(lumiere), profil.apply_linear(lumiere))
