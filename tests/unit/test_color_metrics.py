"""Tests de la metrique d'acceptation. `EPIC5-ARB-28`, signature nommee.

Ce fichier existe parce que la revue en trois couches du 2026-08-11 a constate que la
signature donnee « a ecrire telle quelle » par l'arbitrage n'existait nulle part
(bloquant B4): ni le module, ni la fonction, ni la dataclasse, ni l'exception, ni les
champs de tracabilite. Chaque test nomme ce qu'il verrouille -- une signature dont les
champs ne sont pas exiges par un test se reduit au premier refactoring.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from mixed_media_utility import color_calibration as cc
from mixed_media_utility import color_metrics as cm


def _triplets(**rows):
    return {key: tuple(float(v) for v in value) for key, value in rows.items()}


def _page(*, shift=0.0):
    """Trois valeurs distinguables, la cible **jamais en premiere position**.

    Regle des fabriques du CLAUDE.md: trois valeurs de couleurs differentes, et la
    valeur qui portera le pire ecart est placee au milieu -- une metrique qui rendrait
    toujours le premier `value_id` comme `worst_value_id` ne se demasque pas autrement.
    """
    reference = _triplets(
        **{"a-neutre": (0.50, 0.50, 0.50),
           "b-rouge": (0.10, 0.15, 0.75),
           "c-vert": (0.20, 0.60, 0.25)})
    measured = {key: tuple(min(1.0, max(0.0, component + (shift if key == "b-rouge"
                                                          else 0.0)))
                           for component in value)
                for key, value in reference.items()}
    return measured, reference


# --- La signature elle-meme --------------------------------------------------

def test_la_signature_porte_les_champs_nommes_par_l_arbitrage():
    """`EPIC5-ARB-28` enumere les champs; les enumerer ici les rend opposables."""
    measured, reference = _page()
    result = cm.evaluate_page_acceptance(
        measured=measured, reference=reference, measured_raw=measured,
        values_version="patch-values-2")
    for field in ("mean_delta_e", "max_delta_e", "worst_value_id", "per_value",
                  "sample_count", "values_version", "acceptance_id", "passed",
                  "channel_relative_deviation_before_correction",
                  "channel_relative_deviation_before_correction_per_value"):
        assert hasattr(result, field), f"champ de la signature absent: {field}"
    assert result.values_version == "patch-values-2"
    assert result.acceptance_id == "color-acceptance-1"
    assert result.sample_count == 3


def test_per_value_est_trie_et_worst_value_id_n_est_pas_le_premier():
    """Deterministe **et** discriminant: la cible est au milieu de la fabrique."""
    measured, reference = _page(shift=0.20)
    result = cm.evaluate_page_acceptance(
        measured=measured, reference=reference, measured_raw=measured,
        values_version="patch-values-2")
    assert [key for key, _ in result.per_value] == sorted(reference)
    assert result.worst_value_id == "b-rouge", (
        "le pire ecart est pose sur la deuxieme valeur: une metrique qui rendrait "
        "toujours la premiere passerait un test dont la cible est en tete")
    assert result.max_delta_e == pytest.approx(
        dict(result.per_value)["b-rouge"])


def test_a_egalite_worst_value_id_est_le_premier_lexicographique():
    """Regle explicite de l'arbitrage, sans quoi deux executions peuvent differer."""
    reference = _triplets(**{"a": (0.4, 0.4, 0.4), "b": (0.4, 0.4, 0.4),
                             "c": (0.4, 0.4, 0.4)})
    measured = _triplets(**{"a": (0.5, 0.5, 0.5), "b": (0.5, 0.5, 0.5),
                            "c": (0.5, 0.5, 0.5)})
    result = cm.evaluate_page_acceptance(
        measured=measured, reference=reference, measured_raw=measured,
        values_version="patch-values-2")
    assert result.worst_value_id == "a"


# --- Ce que l'invalide devient -----------------------------------------------

def test_un_jeu_vide_est_une_erreur_nommee_et_non_un_valueerror_numpy():
    """Avant correction: `ValueError` numpy nu (« zero-size array to reduction »)."""
    with pytest.raises(cm.ColorMetricError, match="est vide"):
        cm.evaluate_page_acceptance(measured={}, reference={}, measured_raw={},
                                    values_version="patch-values-2")


def test_un_non_fini_est_refuse_et_ne_ressort_pas_en_succes_sur_un_nan():
    """**Le defaut le plus grave de B4.** Un `NaN` traversait la metrique et sortait
    en `mean_delta_e = nan` sous un statut `applied` -- donc une page acceptee sur une
    grandeur qui n'existe pas. C'est pire que le `passed=False` accidentel que
    l'arbitrage avait chiffre pour l'eviter.
    """
    measured, reference = _page()
    measured = dict(measured)
    measured["b-rouge"] = (float("nan"), 0.5, 0.5)
    with pytest.raises(cm.ColorMetricError, match="non finie"):
        cm.evaluate_page_acceptance(
            measured=measured, reference=reference, measured_raw=measured,
            values_version="patch-values-2")


def test_des_value_id_discordants_sont_refuses():
    """Comparer des valeurs differentes rendrait une distance sans sens."""
    measured, reference = _page()
    reference = dict(reference)
    reference["d-autre"] = reference.pop("c-vert")
    with pytest.raises(cm.ColorMetricError, match="memes value_id"):
        cm.evaluate_page_acceptance(
            measured=measured, reference=reference, measured_raw=measured,
            values_version="patch-values-2")


def test_un_triplet_de_mauvaise_forme_est_refuse():
    measured, reference = _page()
    measured = dict(measured)
    measured["b-rouge"] = (0.5, 0.5)
    with pytest.raises(cm.ColorMetricError, match="triplet BGR"):
        cm.evaluate_page_acceptance(
            measured=measured, reference=reference, measured_raw=measured,
            values_version="patch-values-2")


# --- Le verdict --------------------------------------------------------------

def test_une_page_fidele_passe_et_les_seuils_sont_ceux_du_registre():
    measured, reference = _page()
    result = cm.evaluate_page_acceptance(
        measured=measured, reference=reference, measured_raw=measured,
        values_version="patch-values-2")
    assert result.passed is True
    assert result.failure_reason is None
    thresholds = cm.get_color_acceptance("color-acceptance-1")
    assert (thresholds.max_mean_delta_e, thresholds.max_max_delta_e) == (8.0, 16.0)


def test_les_seuils_absolus_sont_rapportes_mais_ne_commandent_plus_le_statut():
    """`EPIC5-ARB-72`: `color-acceptance-1` cesse d'etre le critere qui bloque.

    **Le test a change de sens le 2026-08-13**, il n'a pas ete supprime, et c'est la
    frontiere que la story 5.20 doit tenir: les deux nombres du registre sont toujours
    calcules et toujours rapportes -- `acceptance_thresholds_met` le dit -- mais une page
    tres loin du theorique n'est plus refusee pour cette seule raison. Motif mesure:
    le scan Windows du 2026-08-13 affiche 15,42 dE76 de moyenne **sans aucune
    correction**, et le tirage qui a valide la methode le 2026-08-11 en affiche 11,66 --
    ce seuil n'a jamais ete celui qui a prouve que la methode marche.

    La page de ce test ne degrade rien (`measured` est `measured_raw`), donc les deux
    clauses du budget de distorsion sont a zero: ce qui est verifie ici est bien que
    l'ecart absolu **seul** ne refuse plus.
    """
    reference = _triplets(**{"a-clair": (0.9, 0.9, 0.9), "b-sombre": (0.1, 0.1, 0.1)})
    measured = _triplets(**{"a-clair": (0.2, 0.2, 0.2), "b-sombre": (0.9, 0.9, 0.9)})
    result = cm.evaluate_page_acceptance(
        measured=measured, reference=reference, measured_raw=measured,
        values_version="patch-values-2")
    assert result.mean_delta_e > 8.0, (
        "le cas n'a d'interet que si les seuils absolus sont franchis")
    assert result.acceptance_thresholds_met is False, (
        "les seuils restent calcules et rapportes: ils ne sont pas supprimes")
    assert result.acceptance_id == "color-acceptance-1"
    assert result.passed is True
    assert result.failure_reason is None


def test_la_clause_de_moyenne_est_mesuree_et_publiee_sans_rien_refuser():
    """`EPIC5-ARB-31` clause 2, puis `EPIC5-ARB-78`: la mesure reste, le refus part.

    **Le test a change de sens le 2026-08-13 et n'a pas ete supprime**, exactement comme
    son voisin l'avait fait pour les seuils absolus six heures plus tot. Une correction
    qui **empire** la page en moyenne etait refusee; elle est desormais mesuree
    (`mean_degradation_de76` strictement positive), son depassement est publie
    (`distortion_budget_met` faux) et la page passe. Motif d'Egan, textuel: « on ne
    bloque rien a cause d'un seuil etc. On informe. »

    Ce que le test continue de tenir, et qui est le vrai enjeu: le depassement reste
    **visible**. Un arbitrage qui aurait supprime la mesure en meme temps que le refus
    aurait rendu ce regime indistinguable d'une correction saine.
    """
    reference = _triplets(**{"a": (0.50, 0.50, 0.50), "b": (0.30, 0.40, 0.60)})
    raw = _triplets(**{"a": (0.505, 0.505, 0.505), "b": (0.305, 0.405, 0.605)})
    worse = _triplets(**{"a": (0.52, 0.52, 0.52), "b": (0.32, 0.42, 0.62)})
    result = cm.evaluate_page_acceptance(
        measured=worse, reference=reference, measured_raw=raw,
        values_version="patch-values-2")
    assert result.passed is True
    assert result.failure_reason is None
    assert result.mean_degradation_de76 > 0.0, (
        "la page empire bien: sans cela le test ne dit rien de la clause")
    assert result.distortion_budget_met is False, (
        "le depassement reste publie -- informer suppose que la mesure survive")
    assert result.mean_delta_e < 8.0, (
        "le cas n'a d'interet que si les seuils absolus tiennent: sinon ce n'est pas "
        "la clause de moyenne que l'on regarde")


def test_une_page_quasi_parfaite_ne_tombe_pas_sur_la_tolerance_numerique():
    """La clause de moyenne, lue au pied de la lettre en flottant, ferait echouer une
    page dont le residu n'est que du bruit de calcul -- `DEGRADATION_TOLERANCE_DE76`
    absorbe exactement ce bruit.

    **Frontiere reecrite** (deuxieme passe de revue, `EPIC5-ARB-78`, 2026-08-14): la
    premiere version n'assertait que `result.passed is True`, devenu un invariant
    depuis que la metrique ne refuse plus rien -- la frontiere ne se voyait donc plus.
    Elle se lit desormais sur `distortion_budget_met`, qui porte encore la clause de
    non-degradation absorbee (`EPIC5-ARB-31` clause 2 / `EPIC5-ARB-74`).

    Le residu est construit **explicitement**, a l'echelle du bruit de calcul documente
    (une page exacte laisse un ordre de 1e-14), plutot que laisse a l'accident d'une
    fabrique qui se trouverait exacte -- `_page()` sans decalage produit un residu
    nul a la lettre (`before == after == 0.0`), qui ne met la tolerance a l'epreuve de
    rien.
    """
    measured, reference = _page()
    # Le passage code -> dE76 amplifie fortement un petit ecart (mesure: /1000 en code
    # donne ~/10 en dE76 sur cette fabrique) -- diviseur choisi empiriquement pour rendre
    # une degradation mesurable, non nulle, et restant sous la tolerance.
    epsilon = cm.DEGRADATION_TOLERANCE_DE76 / 1000
    corrected = {key: tuple(component + epsilon for component in value)
                for key, value in measured.items()}
    result = cm.evaluate_page_acceptance(
        measured=corrected, reference=reference, measured_raw=measured,
        values_version="patch-values-2")
    assert result.passed is True
    assert 0.0 < result.mean_degradation_de76 < cm.DEGRADATION_TOLERANCE_DE76, (
        "le residu construit doit deplacer la page d'une grandeur mesurable mais sous "
        "la tolerance, sinon celle-ci n'est pas mise a l'epreuve")
    assert result.distortion_budget_met is True, (
        "un residu de calcul sous la tolerance ne doit jamais faire basculer le "
        "budget: c'est precisement ce que `DEGRADATION_TOLERANCE_DE76` existe pour "
        "empecher")
    assert cm.DEGRADATION_TOLERANCE_DE76 < 1e-6, (
        "la tolerance est numerique, pas perceptuelle: au-dela elle relacherait "
        "l'arbitrage au lieu d'absorber le bruit de calcul")


def test_une_page_qui_depasse_la_tolerance_bascule_le_budget():
    """Contre-epreuve indispensable de la frontiere ci-dessus: sans elle, une tolerance
    qui n'absorberait jamais rien -- ou qui absorberait tout -- passerait quand meme."""
    measured, reference = _page()
    au_dela = {key: tuple(component + cm.DEGRADATION_TOLERANCE_DE76 * 1e6
                          for component in value)
              for key, value in measured.items()}
    result = cm.evaluate_page_acceptance(
        measured=au_dela, reference=reference, measured_raw=measured,
        values_version="patch-values-2")
    assert result.passed is True, "la metrique ne refuse toujours rien"
    assert result.mean_degradation_de76 > cm.DEGRADATION_TOLERANCE_DE76
    assert result.distortion_budget_met is False


def test_un_acceptance_id_inconnu_est_refuse_sans_repli():
    with pytest.raises(cm.UnknownColorAcceptanceError, match="color-acceptance-9"):
        cm.evaluate_page_acceptance(
            measured=_page()[0], reference=_page()[1], measured_raw=_page()[0],
            values_version="patch-values-2", acceptance_id="color-acceptance-9")


# --- Les deux duplications declarees, verrouillees ---------------------------

def test_les_constantes_de_transfert_sont_les_memes_que_celles_de_la_correction():
    """La seconde application de l'EOTF est **declaree** par l'arbitrage; sa
    divergence, non.

    Deux fonctions de transfert qui s'ecarteraient rendraient la metrique fausse d'un
    cote sans qu'aucun test des deux modules ne le voie -- exactement le motif pour
    lequel `color_pipeline` delegue au lieu de recopier.
    """
    grid = np.linspace(0.0, 1.0, 2048)
    assert np.abs(cm.eotf(grid) - cc.eotf(grid)).max() < 1e-15


def test_la_metrique_est_la_meme_fonction_des_deux_cotes():
    """`color_calibration` reimporte la metrique; il ne la redefinit pas."""
    assert cc.delta_e76_srgb_d65 is cm.delta_e76_srgb_d65
    assert cc.lab_from_srgb_bgr is cm.lab_from_srgb_bgr
    assert cc.channel_relative_deviation is cm.channel_relative_deviation
    assert np.asarray(cc.SRGB_TO_XYZ_D65_BGR) is np.asarray(cm.SRGB_TO_XYZ_D65_BGR)


def test_le_type_de_travail_est_celui_du_depot_et_non_un_litteral():
    """`EPIC5-ARB-27` clause 1: employer `np.float64` en litteral plutot que la
    constante du depot est qualifie de « bug, pas la valeur »."""
    from mixed_media_utility import gamut_map

    assert cm.WORKING_DTYPE is gamut_map.WORKING_DTYPE
    assert cm.SRGB_TO_XYZ_D65_BGR.dtype == gamut_map.WORKING_DTYPE
    measured, reference = _page()
    result = cm.evaluate_page_acceptance(
        measured=measured, reference=reference, measured_raw=measured,
        values_version="patch-values-2")
    assert isinstance(result.mean_delta_e, float)


# --- Le raccord avec l'orchestration de page --------------------------------

def test_la_page_reelle_transporte_le_detail_de_la_signature():
    """Sans ce raccord, la signature existerait sans etre employee -- ce qui etait
    exactement l'etat avant correction, a ceci pres qu'elle n'existait pas du tout."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_color_calibration import _synthetic_rectified_page

    page = _synthetic_rectified_page()
    result = cc.calibrate_page(page, template_id="tpl-a4-portrait-2f-v1",
                               patch_preset_id="patches-18-v2", dpi=600)
    detail = result.acceptance.detail
    assert isinstance(detail, cm.PageAcceptanceResult)
    assert detail.values_version == "patch-values-2"
    assert detail.sample_count == 10, (
        "dix valeurs d'ajustement, pas vingt lignes: c'est l'agregation H4")
    assert detail.worst_value_id in dict(detail.per_value)
    assert len(detail.channel_relative_deviation_before_correction_per_value) == 10


# --- Story 5.16 : Lab dans les deux sens, une seule definition ---------------

def test_l_aller_retour_lab_lineaire_est_exact():
    """La seconde forme de correction **applique** dans Lab: il lui faut le retour.

    Sans cette exactitude, une derive de correction serait imputee a l'ajustement alors
    qu'elle viendrait de la representation -- exactement le motif pour lequel
    `test_eotf_oetf_aller_retour_est_neutre` existe du cote des fonctions de transfert.

    Le domaine balaye inclut **les deux branches** de la compression CIE: au-dessus du
    coude `_LAB_EPSILON` (la branche cubique) et en dessous (la branche affine, celle des
    ombres, ou vit le plancher d'encrage). Une inversion posee sur `f` au lieu de `f**3`
    deplacerait la frontiere de quelques 1e-3 dans les ombres, donc precisement la ou
    l'imprimante est le plus difficile a corriger.
    """
    encoded = np.array([
        [0.20, 0.50, 0.80], [0.90, 0.85, 0.30], [0.45, 0.20, 0.60],
        [0.0, 0.0, 0.0], [1.0, 1.0, 1.0],
        # Sous le coude de la compression Lab, les trois canaux et un seul.
        [0.004, 0.002, 0.001], [0.0, 0.003, 0.0], [0.002, 0.9, 0.5],
    ])
    linear = cm.eotf(encoded)
    lab = cm.lab_from_linear_bgr(linear)
    back = cm.linear_bgr_from_lab(lab)
    assert np.abs(back - linear).max() < 1e-12, np.abs(back - linear).max()
    # Les deux branches sont bien exercees: sans cela l'exactitude ne prouverait que la
    # branche cubique.
    xyz = linear @ cm.SRGB_TO_XYZ_D65_BGR.T
    ratio = xyz / np.array([0.95047, 1.0, 1.08883])
    assert (ratio > 216.0 / 24389.0).any() and (ratio <= 216.0 / 24389.0).any()


def test_la_projection_depuis_l_encode_delegue_a_la_version_lineaire():
    """Une seule definition de Lab: `lab_from_srgb_bgr` est l'EOTF puis la projection.

    Deux definitions qui divergeraient rendraient la metrique fausse d'un cote sans
    qu'aucun test des deux modules ne le voie -- c'est le motif ecrit dans le docstring
    du module, et ce test est ce qui le tient.
    """
    encoded = np.array([[0.2, 0.5, 0.8], [0.03, 0.03, 0.03], [0.99, 0.5, 0.01]])
    direct = cm.lab_from_srgb_bgr(encoded)
    composed = cm.lab_from_linear_bgr(cm.eotf(encoded))
    assert direct.tobytes() == composed.tobytes()


def test_le_blanc_de_reference_rend_une_clarte_de_cent():
    """Ancrage absolu: sans lui, une matrice ou un blanc faux resterait inversible.

    L'aller-retour est neutre pour **toute** matrice inversible et **tout** blanc
    strictement positif: il ne peut donc pas voir une matrice permutee. Ce test-ci le
    peut, parce qu'il confronte a une valeur connue de la CIE.
    """
    white = cm.lab_from_linear_bgr(np.array([1.0, 1.0, 1.0]))
    assert white[0] == pytest.approx(100.0, abs=1e-4)
    assert abs(white[1]) < 1e-3 and abs(white[2]) < 1e-3
    # Et l'ordre des canaux est bien BGR: un bleu pur est sombre et fortement negatif
    # en b*, un rouge pur est plus clair et fortement positif en a*. Une permutation
    # R/B ne casse pas une image, elle fait converger la correction ailleurs.
    blue = cm.lab_from_linear_bgr(np.array([1.0, 0.0, 0.0]))
    red = cm.lab_from_linear_bgr(np.array([0.0, 0.0, 1.0]))
    assert blue[2] < -100.0 and red[1] > 70.0
    assert red[0] > blue[0]


# =============================================================================
# Story 5.20 -- `color-distortion-budget-1`, le critere qui commande desormais
# =============================================================================
#
# `EPIC5-ARB-72` retire a `color-acceptance-1` le role de critere bloquant et le confie
# a un budget de distorsion. `EPIC5-ARB-73` en donne la formule et les deux plafonds.
# Ce bloc verrouille les trois choses qui, prises separement, se relisent comme des
# gouts: la formule, l'articulation avec la garde qui existait, et le fait que le
# nouveau critere **morde**.


def _neutral_page(*, corrected):
    """Un jeu ou la cible neutre est en **troisieme** position sur quatre.

    Regle des fabriques: quatre valeurs distinguables, deux neutres de clartes
    differentes et deux colorees, et la valeur qui portera la pire degradation neutre
    n'est ni la premiere du jeu ni le premier des neutres. Une clause qui rendrait
    toujours le premier neutre, ou toujours la premiere valeur, passerait un jeu a une
    seule valeur neutre sans se demasquer.
    """
    reference = _triplets(
        **{"a-rouge": (0.10, 0.15, 0.75),
           "b-gris-sombre": (0.20, 0.20, 0.20),
           "c-gris-clair": (0.80, 0.80, 0.80),
           "d-vert": (0.20, 0.60, 0.25)})
    raw = _triplets(
        **{"a-rouge": (0.14, 0.19, 0.71),
           "b-gris-sombre": (0.24, 0.24, 0.24),
           "c-gris-clair": (0.79, 0.79, 0.79),
           "d-vert": (0.24, 0.56, 0.29)})
    return corrected, reference, raw


def test_le_registre_du_budget_porte_ses_deux_plafonds_et_sa_mesure():
    """`EPIC5-ARB-73`: un seuil derive d'une mesure porte de quoi se relire.

    Les deux plafonds ne sont pas interchangeables et le test le dit: la moyenne est a
    **zero** -- `EPIC5-ARB-31` clause 2 absorbee verbatim, aucun relachement -- et le
    maximum de l'axe neutre est le nombre derive.
    """
    budget = cm.get_distortion_budget("color-distortion-budget-1")
    assert budget is cm.COLOR_DISTORTION_REGISTRY["color-distortion-budget-1"]
    assert cm.ACTIVE_DISTORTION_BUDGET_ID == "color-distortion-budget-1"
    assert budget.max_mean_degradation_de76 == 0.0, (
        "la clause de moyenne EST EPIC5-ARB-31 clause 2: la relever serait une "
        "revision de l'arbitrage, pas un reglage")
    assert budget.max_neutral_degradation_de76 == 2.5
    assert budget.null_distribution_max_de76 == 1.45
    assert budget.null_distribution_samples == 16
    assert len(budget.reservations) >= 3
    assert any("OPTIMISTE" in reserve for reserve in budget.reservations)
    # Le registre n'est pas editable en place: une revision passe par une entree
    # nouvelle, sans quoi elle changerait le sens des campagnes passees.
    with pytest.raises(TypeError):
        cm.COLOR_DISTORTION_REGISTRY["color-distortion-budget-2"] = budget


def test_un_budget_inconnu_echoue_au_lieu_de_retomber_sur_un_defaut():
    with pytest.raises(cm.UnknownColorDistortionBudgetError, match="pire qu'aucun"):
        cm.get_distortion_budget("color-distortion-budget-42")
    with pytest.raises(cm.UnknownColorDistortionBudgetError):
        cm.get_distortion_budget(["non", "hachable"])


def test_le_budget_refuse_un_plafond_sous_sa_distribution_nulle():
    """Meme invariant structurel que `DivergenceGuard`, et il se verifie a la
    construction: sous la distribution nulle, la garde refuse des corrections qui ne
    deforment rien."""
    with pytest.raises(ValueError, match="distribution nulle"):
        cm.ColorDistortionBudget(
            budget_id="color-distortion-budget-2", max_mean_degradation_de76=0.0,
            max_neutral_degradation_de76=1.0, null_distribution_max_de76=1.45,
            null_distribution_samples=16, reservations=("une reserve",))


def test_le_budget_refuse_une_entree_sans_reserve_ou_mal_formee():
    """Quatre gardes de construction, quatre defauts distincts -- une entree sans
    reserve se relit comme un fait etabli, un cardinal nul comme une mesure."""
    commun = dict(budget_id="color-distortion-budget-2",
                  max_mean_degradation_de76=0.0,
                  max_neutral_degradation_de76=2.5,
                  null_distribution_max_de76=1.45,
                  null_distribution_samples=16,
                  reservations=("une reserve",))
    with pytest.raises(ValueError, match="reserves"):
        cm.ColorDistortionBudget(**{**commun, "reservations": ()})
    with pytest.raises(ValueError, match="cardinal positif"):
        cm.ColorDistortionBudget(**{**commun, "null_distribution_samples": 0})
    with pytest.raises(ValueError, match="strictement positif"):
        cm.ColorDistortionBudget(**{**commun, "null_distribution_max_de76": 0.0})
    with pytest.raises(ValueError, match="negatif"):
        cm.ColorDistortionBudget(**{**commun, "max_mean_degradation_de76": -0.5})
    with pytest.raises(ValueError, match="nombre fini"):
        cm.ColorDistortionBudget(**{**commun, "max_neutral_degradation_de76": True})


def test_le_budget_refuse_un_identifiant_vide_et_une_reserve_vide():
    """Deux trous de validation trouves par la revue de 5.20, fermes le 2026-08-19.

    Ils se ressemblent et n'ont pas la meme cause: `budget_id` n'etait **pas valide du
    tout** -- il n'entrait dans aucune des boucles de `__post_init__` --, tandis que
    `reservations` l'etait par un `not self.reservations` que `("",)` satisfait, un tuple
    non vide etant « truthy ». Le second est le plus mauvais des deux: la garde existait,
    portait le bon nom, et se contournait avec une chaine vide.

    Les entrees fautives sont placees **ailleurs qu'en premiere position** dans le tuple
    de reserves: une garde qui ne lirait que `reservations[0]` passerait sinon.
    """
    commun = dict(budget_id="color-distortion-budget-2",
                  max_mean_degradation_de76=0.0,
                  max_neutral_degradation_de76=2.5,
                  null_distribution_max_de76=1.45,
                  null_distribution_samples=16,
                  reservations=("une reserve", "une autre"))
    # Le temoin: l'entree commune construit bien, sans quoi les refus ci-dessous
    # pourraient tenir a n'importe quel autre champ.
    assert cm.ColorDistortionBudget(**commun).budget_id == "color-distortion-budget-2"

    for identifiant in ("", "   ", None, 42):
        with pytest.raises(ValueError, match="budget_id"):
            cm.ColorDistortionBudget(**{**commun, "budget_id": identifiant})

    for reserves in (("",), ("   ",), ("une reserve", ""), ("une reserve", "  "),
                     ("une reserve", "une autre", ""), ("une reserve", None)):
        with pytest.raises(ValueError, match="reserves"):
            cm.ColorDistortionBudget(**{**commun, "reservations": reserves})

    # Et la frontiere positive: une reserve non vide en seconde position passe.
    assert cm.ColorDistortionBudget(
        **{**commun, "reservations": ("a", "b", "c")}).reservations == ("a", "b", "c")


def test_la_famille_neutre_est_derivee_de_la_reference_et_non_declaree():
    """Deux sources pour un meme fait divergeraient, et c'est la clause du budget qui
    jugerait alors une famille qui n'est pas celle qu'elle nomme."""
    assert cm.is_grey_reference((0.2, 0.2, 0.2)) is True
    assert cm.is_grey_reference((0.2, 0.2, 0.2 + 1e-12)) is False
    assert cm.is_grey_reference((20 / 255, 20 / 255, 20 / 255)) is True
    measured, reference = _page()
    result = cm.evaluate_page_acceptance(
        measured=measured, reference=reference, measured_raw=measured,
        values_version="patch-values-2")
    assert result.neutral_sample_count == 1, (
        "la fabrique porte une seule valeur grise: `a-neutre`")


def test_la_clause_de_l_axe_neutre_mesure_un_blanc_effondre_sans_le_refuser():
    """`EPIC5-ARB-72` sous sa forme minimale, `EPIC5-ARB-78` pour sa consequence.

    C'est le motif litteral du premier arbitrage -- le blanc de marge lu a 243/255 avant
    correction et effondre a 191 apres. La cible est le **second** neutre du jeu, pas le
    premier, et la degradation moyenne reste negative: ce qui est mesure ici est bien la
    clause de l'axe neutre et non celle de moyenne.

    Ce qu'`EPIC5-ARB-78` change: la page **passe**. Le seuil de 1,5 code de
    l'`EPIC5-ARB-75` voisin s'est revele avoir 0,04 code de marge sur `12p5_test`, et
    Egan ne juge pas un plafond en dE76 -- donc le depassement s'ecrit
    (`distortion_budget_met` faux, chiffre publie) au lieu de se decider.
    """
    corrected = _triplets(
        **{"a-rouge": (0.11, 0.16, 0.74),
           "b-gris-sombre": (0.21, 0.21, 0.21),
           "c-gris-clair": (0.62, 0.62, 0.62),
           "d-vert": (0.21, 0.59, 0.26)})
    corrected, reference, raw = _neutral_page(corrected=corrected)
    result = cm.evaluate_page_acceptance(
        measured=corrected, reference=reference, measured_raw=raw,
        values_version="patch-values-2")
    assert result.mean_degradation_de76 < 0.0, (
        "le cas n'a d'interet que si la clause de moyenne, elle, tient")
    budget = cm.get_distortion_budget(cm.ACTIVE_DISTORTION_BUDGET_ID)
    assert result.max_neutral_degradation_de76 > budget.max_neutral_degradation_de76
    assert result.worst_neutral_value_id == "c-gris-clair", (
        "la cible n'est pas le premier neutre du jeu")
    assert result.distortion_budget_met is False, (
        "le depassement de la clause reste publie, c'est tout ce qui en subsiste")
    assert result.passed is True
    assert result.failure_reason is None


#: Les deux seuils de `color-acceptance-1`, ecrits en **litteral**: c'est contre eux que
#: les quatre regimes ci-dessous sont construits, et les relire du registre ferait boucler
#: le test sur la constante que le code utilise.
SEUILS_DE_COLOR_ACCEPTANCE_1 = (8.0, 16.0)


def test_les_deux_clauses_des_seuils_absolus_sont_un_ET_et_non_un_OU():
    """Finding de la revue de 5.20 (ferme le 2026-08-19): `and` -> `or` survivait.

    `acceptance_thresholds_met` conjugue deux clauses -- moyenne sous 8, maximum sous 16
    -- et aucun test ne portait un cas ou **une seule** des deux est tenue. Il en faut
    deux et non un: les deux sens sont distincts, et un `or` ne se demasque que du cote
    ou la clause survivante est vraie.

    Le champ n'est plus bloquant depuis `EPIC5-ARB-78` -- `passed` reste vrai partout
    ici -- mais c'est lui qui dit au manifest a quelle distance du theorique la page se
    trouve, donc sa lecture doit rester juste.
    """
    reference = _triplets(**{"a-neutre": (0.50, 0.50, 0.50),
                             "b-rouge": (0.10, 0.15, 0.75),
                             "c-vert": (0.20, 0.60, 0.25)})
    max_mean, max_max = SEUILS_DE_COLOR_ACCEPTANCE_1
    acceptance = cm.get_color_acceptance(cm.ACTIVE_COLOR_ACCEPTANCE_ID)
    assert (acceptance.max_mean_delta_e, acceptance.max_max_delta_e) == \
        (max_mean, max_max), "les regimes ci-dessous sont construits pour ces seuils"

    def verdict(measured):
        page = _triplets(**measured)
        return cm.evaluate_page_acceptance(
            measured=page, reference=reference, measured_raw=page,
            values_version="patch-values-2")

    # Regime A: moyenne **au-dessus** de 8, maximum **sous** 16. Un `or` le declarerait
    # tenu, la clause du maximum etant vraie.
    haut = verdict({"a-neutre": (0.60, 0.60, 0.60),
                    "b-rouge": (0.20, 0.25, 0.85),
                    "c-vert": (0.30, 0.70, 0.35)})
    assert haut.mean_delta_e > max_mean and haut.max_delta_e < max_max, (
        haut.mean_delta_e, haut.max_delta_e)
    assert haut.acceptance_thresholds_met is False

    # Regime B: moyenne **sous** 8, maximum **au-dessus** de 16 -- le sens inverse, sans
    # lequel un `or` reste vivant dans une des deux directions.
    pointu = verdict({"a-neutre": (0.50, 0.50, 0.50),
                      "b-rouge": (0.10, 0.15, 0.75),
                      "c-vert": (0.42, 0.82, 0.47)})
    assert pointu.mean_delta_e < max_mean and pointu.max_delta_e > max_max, (
        pointu.mean_delta_e, pointu.max_delta_e)
    assert pointu.acceptance_thresholds_met is False

    # Regime C, temoin positif: les deux clauses tenues. Sans lui, un champ qui rendrait
    # `False` partout passerait les deux assertions ci-dessus.
    juste = verdict({"a-neutre": (0.51, 0.51, 0.51),
                     "b-rouge": (0.10, 0.15, 0.75),
                     "c-vert": (0.20, 0.60, 0.25)})
    assert juste.mean_delta_e < max_mean and juste.max_delta_e < max_max
    assert juste.acceptance_thresholds_met is True


def test_les_seuils_absolus_se_lisent_au_sens_large_et_non_strict(monkeypatch):
    """Finding de la revue de 5.20 (ferme le 2026-08-19): `<=` -> `<` survivait.

    L'egalite exacte n'est pas atteignable en deplacant une pastille -- la distance dE76
    d'une page est un flottant qui ne tombe pas sur 8,0 --, donc le seuil vient a la
    mesure plutot que l'inverse: une entree d'acceptation jetable dont les deux plafonds
    **sont** la moyenne et le maximum de la page. Les deux nombres sont ecrits en
    litteral, mesures le 2026-08-19 sur la page ci-dessous; les relire du resultat
    ferait boucler le test sur le code qu'il mesure.
    """
    reference = _triplets(**{"a-neutre": (0.50, 0.50, 0.50),
                             "b-rouge": (0.10, 0.15, 0.75),
                             "c-vert": (0.20, 0.60, 0.25)})
    page = _triplets(**{"a-neutre": (0.56, 0.56, 0.56),
                        "b-rouge": (0.10, 0.15, 0.75),
                        "c-vert": (0.20, 0.60, 0.25)})
    moyenne, maximum = 1.9796598290287903, 5.938979487086371

    def avec_seuils(max_mean, max_max):
        entree = cm.ColorAcceptance(acceptance_id="color-acceptance-jetable",
                                    max_mean_delta_e=max_mean,
                                    max_max_delta_e=max_max)
        monkeypatch.setattr(cm, "COLOR_ACCEPTANCE_REGISTRY",
                            {**cm.COLOR_ACCEPTANCE_REGISTRY,
                             "color-acceptance-jetable": entree})
        return cm.evaluate_page_acceptance(
            measured=page, reference=reference, measured_raw=page,
            values_version="patch-values-2",
            acceptance_id="color-acceptance-jetable")

    # La page rend bien les deux nombres annonces: sans ce controle, les seuils poses
    # ci-dessous ne seraient pas la frontiere qu'on croit.
    temoin = avec_seuils(moyenne, maximum)
    # LES LITTERAUX SE LISENT A LA TOLERANCE, la frontiere se pose sur la MESURE.
    # Corrige le 2026-09-08 : `== moyenne` etait une egalite au bit pres sur le
    # resultat d'un calcul flottant, donc vrai de cette machine-ci et faux
    # ailleurs -- le runner de CI rend 1,9796598290287852 la ou ce litteral dit
    # ...903, soit 2,6e-15 en relatif. Les litteraux gardent leur role, qui est
    # de PINNER la page : s'ils derivaient vraiment, la tolerance les
    # attraperait encore (elle est mille fois plus fine que le dernier chiffre
    # significatif qui compte).
    assert temoin.mean_delta_e == pytest.approx(moyenne, rel=1e-12)
    assert temoin.max_delta_e == pytest.approx(maximum, rel=1e-12)

    # Et les seuils se posent sur ce que la page rend REELLEMENT, sinon la
    # frontiere n'est plus a l'egalite : un seuil un ULP au-dessus de la mesure
    # rend `<` et `<=` indiscernables, et le banc devient vide sans le dire.
    # Ce n'est pas circulaire : ce qui est mesure ici est l'OPERATEUR de
    # comparaison, la distance n'etant que la position ou on l'interroge.
    mesuree, mesure_max = temoin.mean_delta_e, temoin.max_delta_e

    # **A l'egalite exacte, la page est tenue.** C'est ce que `<=` dit et ce que `<`
    # nierait, sur les deux clauses a la fois.
    assert avec_seuils(mesuree, mesure_max).acceptance_thresholds_met is True
    # Un seuil de moyenne d'un ULP sous la mesure ne l'est plus, et symetriquement pour
    # le maximum: la frontiere est bien la, et pas ailleurs.
    assert avec_seuils(math.nextafter(mesuree, 0.0),
                       mesure_max).acceptance_thresholds_met is False
    assert avec_seuils(mesuree,
                       math.nextafter(mesure_max, 0.0)).acceptance_thresholds_met is False


def _page_a_trois_neutres():
    """Cinq valeurs, **trois** neutres, la pire degradation neutre au **milieu** d'eux.

    Finding de la revue de 5.20, ferme le 2026-08-19: `_neutral_page` ne porte que deux
    neutres et place la cible en second, donc en **dernier** des neutres -- un
    `worst_neutral_value_id` qui rendrait toujours le dernier neutre y est indiscernable
    du bon. Ici la famille grise compte trois membres et la cible est le deuxieme des
    trois: ni `[0]` ni `[-1]` ne la designent.

    Le pire ecart **toutes valeurs confondues** est porte par une valeur **coloree**
    (`a-rouge`), et non par la cible neutre: sans cela, un `worst_neutral_value_id` qui
    recopierait `worst_value_id` passerait aussi.
    """
    reference = _triplets(
        **{"a-rouge": (0.10, 0.15, 0.75),
           "b-gris-sombre": (0.20, 0.20, 0.20),
           "c-gris-median": (0.50, 0.50, 0.50),
           "d-gris-clair": (0.80, 0.80, 0.80),
           "e-vert": (0.20, 0.60, 0.25)})
    raw = _triplets(
        **{"a-rouge": (0.14, 0.19, 0.71),
           "b-gris-sombre": (0.22, 0.22, 0.22),
           "c-gris-median": (0.52, 0.52, 0.52),
           "d-gris-clair": (0.79, 0.79, 0.79),
           "e-vert": (0.24, 0.56, 0.29)})
    corrected = _triplets(
        **{"a-rouge": (0.45, 0.55, 0.30),
           "b-gris-sombre": (0.205, 0.205, 0.205),
           "c-gris-median": (0.35, 0.35, 0.35),
           "d-gris-clair": (0.798, 0.798, 0.798),
           "e-vert": (0.21, 0.59, 0.26)})
    return corrected, reference, raw


def test_le_pire_neutre_n_est_ni_le_premier_ni_le_dernier_de_sa_famille():
    """Finding de la revue de 5.20 (ferme le 2026-08-19): `[position]` -> `[-1]` survivait.

    La seule fixture a plus d'un neutre en portait exactement deux, avec la cible en
    second: le dernier neutre **etait** le bon, et l'indice mutant rendait la meme
    reponse. Trois neutres et une cible mediane ferment les deux mutants d'indice a la
    fois.
    """
    corrected, reference, raw = _page_a_trois_neutres()
    result = cm.evaluate_page_acceptance(
        measured=corrected, reference=reference, measured_raw=raw,
        values_version="patch-values-2")
    assert result.neutral_sample_count == 3, (
        "trois neutres: avec deux, `[-1]` reste indiscernable de la bonne reponse")
    assert result.worst_neutral_value_id == "c-gris-median"
    # Les deux voisins de la famille grise sont nommes pour que le test dise ce qu'il
    # ecarte: ni le premier des neutres, ni le dernier.
    assert result.worst_neutral_value_id != "b-gris-sombre"
    assert result.worst_neutral_value_id != "d-gris-clair"
    # Et ce n'est pas non plus une copie de `worst_value_id`, qui est ici une couleur.
    assert result.worst_value_id == "a-rouge"
    # La valeur publiee est bien celle de la cible, et elle est ecrite en litteral --
    # la relire depuis la fixture reviendrait a la deriver du code qu'on mesure.
    assert result.max_neutral_degradation_de76 == pytest.approx(13.467, abs=0.005)


def test_une_correction_qui_ameliore_l_axe_neutre_passe():
    """Contre-epreuve: sans elle, une clause qui refuserait tout passerait le test
    precedent.

    **Temoin positif ajoute** (deuxieme passe de revue, `EPIC5-ARB-78`, 2026-08-14):
    `distortion_budget_met` n'avait aucune assertion `is True` sur un jeu portant une
    vraie valeur neutre mesuree (par opposition a `is None`, le cas ou aucune valeur
    n'est grise) -- les deux mutants `and`->`or` et expression->`None` pouvaient survivre
    faute d'un cas ou les deux clauses sont **explicitement** tenues.
    """
    corrected = _triplets(
        **{"a-rouge": (0.11, 0.16, 0.74),
           "b-gris-sombre": (0.205, 0.205, 0.205),
           "c-gris-clair": (0.798, 0.798, 0.798),
           "d-vert": (0.21, 0.59, 0.26)})
    corrected, reference, raw = _neutral_page(corrected=corrected)
    result = cm.evaluate_page_acceptance(
        measured=corrected, reference=reference, measured_raw=raw,
        values_version="patch-values-2")
    assert result.passed is True
    assert result.failure_reason is None
    assert result.mean_degradation_de76 <= 0.0, (
        "la clause de moyenne doit elle aussi tenir, sinon ce n'est pas un temoin "
        "positif du ET des deux clauses")
    assert result.max_neutral_degradation_de76 < 0.0
    assert result.distortion_budget_id == "color-distortion-budget-1"
    assert result.distortion_budget_met is True, (
        "les deux clauses tiennent: c'est le temoin positif qui manquait")


def test_la_clause_de_moyenne_bascule_le_budget_meme_quand_l_axe_neutre_est_tenu():
    """Discrimine le `and` du budget dans l'autre sens que le test de l'axe neutre
    effondre ci-dessus (deuxieme passe de revue, `EPIC5-ARB-78`, 2026-08-14).

    Les deux tests forment un couple: l'un a la clause de moyenne tenue et celle de
    l'axe neutre depassee, celui-ci a la clause de moyenne depassee et celle de l'axe
    neutre tenue -- **avec une vraie valeur grise mesuree**, pas seulement l'absence de
    neutre (deja couvert par
    `test_un_jeu_sans_valeur_grise_ne_declenche_pas_la_clause_de_l_axe_neutre`, dont le
    court-circuit `is None` a un chemin d'execution distinct). Sans ce couple, un `and`
    devenu `or` ne se demasque que dans un seul des deux sens.
    """
    corrected = _triplets(
        **{"a-rouge": (0.30, 0.35, 0.55),
           "b-gris-sombre": (0.205, 0.205, 0.205),
           "c-gris-clair": (0.798, 0.798, 0.798),
           "d-vert": (0.45, 0.75, 0.05)})
    corrected, reference, raw = _neutral_page(corrected=corrected)
    result = cm.evaluate_page_acceptance(
        measured=corrected, reference=reference, measured_raw=raw,
        values_version="patch-values-2")
    assert result.passed is True
    budget = cm.get_distortion_budget(cm.ACTIVE_DISTORTION_BUDGET_ID)
    assert result.mean_degradation_de76 > budget.max_mean_degradation_de76, (
        "le cas n'a d'interet que si la clause de moyenne, elle, echoue"
    )
    assert result.max_neutral_degradation_de76 < budget.max_neutral_degradation_de76, (
        "et que la clause de l'axe neutre, elle, tient")
    assert result.distortion_budget_met is False, (
        "une seule des deux clauses suffit a faire basculer le budget")


def test_un_jeu_sans_valeur_grise_ne_declenche_pas_la_clause_de_l_axe_neutre():
    """La garde porte sur une degradation **mesuree**, jamais sur l'absence de mesure.

    Et elle le **dit**: `max_neutral_degradation_de76` vaut `None` et non `0.0`. Zero
    est la valeur d'une correction parfaite, donc l'ecrire ici publierait la meilleure
    lecture possible la ou rien n'a ete lu -- le faux succes que ce module combat
    partout ailleurs.
    """
    reference = _triplets(**{"a-rouge": (0.10, 0.15, 0.75),
                             "b-vert": (0.20, 0.60, 0.25)})
    raw = _triplets(**{"a-rouge": (0.12, 0.17, 0.73),
                       "b-vert": (0.22, 0.58, 0.27)})
    pire = _triplets(**{"a-rouge": (0.30, 0.35, 0.55),
                        "b-vert": (0.22, 0.58, 0.27)})
    result = cm.evaluate_page_acceptance(
        measured=pire, reference=reference, measured_raw=raw,
        values_version="patch-values-2")
    assert result.neutral_sample_count == 0
    assert result.max_neutral_degradation_de76 is None
    assert result.worst_neutral_value_id is None
    # La clause de moyenne, elle, se mesure toujours: elle ne depend d'aucune famille, et
    # c'est elle qui fait sortir ce jeu du budget.
    assert result.distortion_budget_met is False
    assert result.mean_degradation_de76 > 0.0


def test_la_clause_de_moyenne_est_la_garde_de_non_degradation_absorbee():
    """AC 4: **un seul** mecanisme de non-degradation, pas deux en parallele.

    La preuve est un couplage: relever le plafond de moyenne du budget doit suffire a
    faire tenir le budget a une page que `EPIC5-ARB-31` clause 2 tenait pour degradante.
    Si l'ancienne garde subsistait a cote, le verdict publie resterait le meme.

    **Le couplage se lit sur `distortion_budget_met` depuis `EPIC5-ARB-78`**, plus sur
    `passed`: c'est le seul changement du test, et il ne l'affaiblit pas -- ce qui est
    verifie reste qu'il n'existe qu'**un** mecanisme de non-degradation, dont le plafond
    est celui du registre et de nulle part ailleurs.
    """
    reference = _triplets(**{"a": (0.50, 0.50, 0.50), "b": (0.30, 0.40, 0.60)})
    raw = _triplets(**{"a": (0.505, 0.505, 0.505), "b": (0.305, 0.405, 0.605)})
    pire = _triplets(**{"a": (0.52, 0.52, 0.52), "b": (0.32, 0.42, 0.62)})
    refuse = cm.evaluate_page_acceptance(
        measured=pire, reference=reference, measured_raw=raw,
        values_version="patch-values-2")
    assert refuse.distortion_budget_met is False
    assert refuse.mean_delta_e > refuse.mean_delta_e_before_correction

    # Une entree **de test**, resolue par le meme point d'entree que la production et
    # jamais versee au registre du depot: le registre reste ce qu'il declare etre.
    large = cm.ColorDistortionBudget(
        budget_id="color-distortion-budget-large", max_mean_degradation_de76=50.0,
        max_neutral_degradation_de76=50.0, null_distribution_max_de76=1.45,
        null_distribution_samples=16,
        reservations=("entree de test, jamais au registre",))
    registre = dict(cm.COLOR_DISTORTION_REGISTRY)
    registre[large.budget_id] = large
    from unittest import mock
    with mock.patch.object(cm, "COLOR_DISTORTION_REGISTRY", registre):
        passe = cm.evaluate_page_acceptance(
            measured=pire, reference=reference, measured_raw=raw,
            values_version="patch-values-2",
            distortion_budget_id="color-distortion-budget-large")
    assert passe.distortion_budget_met is True, (
        "une garde de non-degradation subsistant a cote du budget tiendrait encore la "
        "page pour degradante, quel que soit le plafond du registre")
    assert passe.mean_degradation_de76 > 0.0
    assert passe.mean_degradation_de76 == pytest.approx(
        refuse.mean_degradation_de76), (
        "seul le plafond change entre les deux appels, jamais la mesure")


def test_aucun_regime_de_couleur_ne_rend_plus_le_verdict_failed():
    """`EPIC5-ARB-78`, frontiere **negative** de toute la classe: on informe, on ne
    bloque plus.

    Les tests voisins montrent chacun qu'un regime donne cesse de refuser. Celui-ci
    ferme la porte a la reciproque -- qu'un regime **oublie** refuse encore --, en
    balayant les quatre familles que le module sait produire, y compris les deux
    cumulees. Il epingle aussi le fait que les deux motifs du budget restent **definis**
    et **jamais emis**: ils vivent dans des manifests deja ecrits, donc les supprimer
    rendrait illisible un document produit avant cet arbitrage.
    """
    reference = _triplets(**{"a-rouge": (0.10, 0.15, 0.75),
                             "b-gris-sombre": (0.20, 0.20, 0.20),
                             "c-gris-clair": (0.80, 0.80, 0.80),
                             "d-vert": (0.20, 0.60, 0.25)})
    raw = _triplets(**{"a-rouge": (0.14, 0.19, 0.71),
                       "b-gris-sombre": (0.24, 0.24, 0.24),
                       "c-gris-clair": (0.79, 0.79, 0.79),
                       "d-vert": (0.24, 0.56, 0.29)})
    # Quatre regimes, du plus benin au cumul: seuils absolus franchis, clause de moyenne
    # depassee, clause de l'axe neutre depassee, et les trois ensemble.
    regimes = {
        "seuils absolus": _triplets(**{"a-rouge": (0.60, 0.60, 0.10),
                                       "b-gris-sombre": (0.20, 0.20, 0.20),
                                       "c-gris-clair": (0.80, 0.80, 0.80),
                                       "d-vert": (0.20, 0.60, 0.25)}),
        "degradation moyenne": _triplets(**{"a-rouge": (0.30, 0.35, 0.55),
                                            "b-gris-sombre": (0.30, 0.30, 0.30),
                                            "c-gris-clair": (0.70, 0.70, 0.70),
                                            "d-vert": (0.35, 0.45, 0.40)}),
        "axe neutre": _triplets(**{"a-rouge": (0.11, 0.16, 0.74),
                                   "b-gris-sombre": (0.21, 0.21, 0.21),
                                   "c-gris-clair": (0.62, 0.62, 0.62),
                                   "d-vert": (0.21, 0.59, 0.26)}),
        "tout a la fois": _triplets(**{"a-rouge": (0.90, 0.05, 0.05),
                                       "b-gris-sombre": (0.75, 0.75, 0.75),
                                       "c-gris-clair": (0.20, 0.20, 0.20),
                                       "d-vert": (0.05, 0.05, 0.95)}),
    }
    hors_budget = []
    for nom, corrected in regimes.items():
        result = cm.evaluate_page_acceptance(
            measured=corrected, reference=reference, measured_raw=raw,
            values_version="patch-values-2")
        assert result.passed is True, nom
        assert result.failure_reason is None, nom
        if not result.distortion_budget_met:
            hors_budget.append(nom)
    # Contre-epreuve indispensable: sans elle, un budget qui ne mesurerait plus rien du
    # tout passerait ce test aussi bien qu'un budget qui mesure et n'oppose pas.
    assert "degradation moyenne" in hors_budget and "axe neutre" in hors_budget, (
        f"les depassements doivent rester visibles, mesures: {hors_budget}")
    # La retro-compatibilite des trois motifs eux-memes (definis, jamais emis) a son
    # propre test, dedie -- `test_les_trois_motifs_retro_compatibles_restent_definis_et_
    # jamais_emis` -- deplacee hors d'ici a la deuxieme passe de revue
    # (`EPIC5-ARB-78`, 2026-08-14): les deux assertions qui vivaient ici
    # (`FAILURE_DEGRADES_RESIDUAL != FAILURE_DISTORTION_BUDGET`, et les trois motifs
    # non-vides) sont des faits de declaration statique, verifiables en relisant le
    # module -- une tautologie de hierarchie de constantes, pas un comportement de
    # `evaluate_page_acceptance` que ce test-ci a la charge de verifier.


def test_les_trois_motifs_retro_compatibles_restent_definis_et_jamais_emis():
    """`EPIC5-ARB-78` point 1: aucun test ne nommait explicitement la retro-compatibilite
    de `FAILURE_METRIC`, `FAILURE_DEGRADES_RESIDUAL` et `FAILURE_DISTORTION_BUDGET`
    (finding de la deuxieme passe de revue, 2026-08-14) -- contrairement au reste de
    l'arbitrage, dont chaque clause a son test dedie. Les trois n'ont plus de lecteur
    de production depuis l'arbitrage -- aucune fonction ne les emet plus en
    `failure_reason` --, mais les retirer rendrait illisible un manifest ecrit avant
    lui, pour un fait qui n'a pas change.
    """
    reference = _triplets(**{"a": (0.10, 0.15, 0.75), "b": (0.20, 0.60, 0.25)})
    # Regime volontairement degradant sur les deux clauses du budget -- celui qui, avant
    # `EPIC5-ARB-78`, aurait ete le domaine d'activation de `FAILURE_DISTORTION_BUDGET`
    # et de `FAILURE_METRIC` -- pour verifier qu'un depassement mesure n'emet toujours
    # aucun des trois motifs.
    raw = _triplets(**{"a": (0.14, 0.19, 0.71), "b": (0.24, 0.56, 0.29)})
    corrected = _triplets(**{"a": (0.90, 0.05, 0.05), "b": (0.05, 0.95, 0.05)})
    result = cm.evaluate_page_acceptance(
        measured=corrected, reference=reference, measured_raw=raw,
        values_version="patch-values-2")
    assert result.failure_reason is None
    assert result.failure_reason not in (
        cm.FAILURE_METRIC, cm.FAILURE_DEGRADES_RESIDUAL, cm.FAILURE_DISTORTION_BUDGET)
    # Definis, distincts et non vides: c'est ce qui garde un manifest d'avant
    # l'arbitrage relisible, sans qu'aucun code de production ne les emette plus.
    assert cm.FAILURE_DEGRADES_RESIDUAL != cm.FAILURE_DISTORTION_BUDGET
    assert cm.FAILURE_DEGRADES_RESIDUAL != cm.FAILURE_METRIC
    assert cm.FAILURE_DISTORTION_BUDGET != cm.FAILURE_METRIC
    assert all(isinstance(motif, str) and motif for motif in
               (cm.FAILURE_DEGRADES_RESIDUAL, cm.FAILURE_DISTORTION_BUDGET,
                cm.FAILURE_METRIC))


def test_la_plus_grande_degradation_isolee_est_publiee_et_ne_bute_sur_aucun_plafond():
    """`EPIC5-ARB-78`, item n°4 de la revue de 5.20: le trou que le budget laisse.

    La clause de maximum du budget ne porte que sur l'axe neutre -- limitation mesuree,
    le treillis portant des couleurs hors gamut CMJN --, si bien qu'une correction qui
    massacre quelques pastilles saturees passait tant que la moyenne restait negative.
    Egan a refuse de poser un plafond dessus (« je ne sais pas comment poser une valeur
    dessus »); la reponse est donc de **publier la grandeur**.

    Regle des fabriques: quatre valeurs distinguables et la cible en **troisieme**
    position, ni premiere du jeu ni derniere -- un `argmax` remplace par `[0]` ou par
    `[-1]` ne se demasque pas autrement. La cible est chromatique, ce qui verifie du meme
    coup que la grandeur ne se restreint pas a la famille neutre.
    """
    reference = _triplets(**{"a-gris": (0.50, 0.50, 0.50),
                             "b-rouge": (0.10, 0.15, 0.75),
                             "c-vert": (0.20, 0.60, 0.25),
                             "d-bleu": (0.70, 0.20, 0.15)})
    # Le brut est franchement fautif sur trois pastilles sur quatre: c'est ce qui laisse
    # la degradation **moyenne** negative -- le regime que l'item n°4 decrit, « une
    # correction qui degrade fortement quelques pastilles passe tant que la moyenne
    # reste negative ».
    raw = _triplets(**{"a-gris": (0.62, 0.60, 0.58),
                       "b-rouge": (0.22, 0.27, 0.63),
                       "c-vert": (0.21, 0.59, 0.26),
                       "d-bleu": (0.58, 0.32, 0.27)})
    corrected = _triplets(**{"a-gris": (0.50, 0.50, 0.50),
                             "b-rouge": (0.10, 0.15, 0.75),
                             # Seule cette pastille est massacree, et elle est troisieme.
                             "c-vert": (0.42, 0.44, 0.48),
                             "d-bleu": (0.70, 0.20, 0.15)})
    result = cm.evaluate_page_acceptance(
        measured=corrected, reference=reference, measured_raw=raw,
        values_version="patch-values-2")
    assert result.worst_degradation_value_id == "c-vert"
    assert result.max_degradation_de76 > 20.0, result.max_degradation_de76
    assert result.mean_degradation_de76 < 0.0, (
        "le cas n'a d'interet que si la clause de moyenne, elle, tient")
    # La grandeur excede de loin le plafond de l'axe neutre du registre, et **rien** ne
    # s'y oppose: c'est litteralement le point de l'arbitrage.
    budget = cm.get_distortion_budget(cm.ACTIVE_DISTORTION_BUDGET_ID)
    assert result.max_degradation_de76 > budget.max_neutral_degradation_de76
    assert result.passed is True
    # Et la clause de l'axe neutre, elle, n'a rien vu -- elle mesure meme une
    # **amelioration**. C'est exactement le trou que l'item n°4 de la revue decrit: le
    # budget est entierement tenu pendant qu'une pastille est massacree de plus de
    # 20 dE76. Les deux grandeurs ne se remplacent donc pas, ce qui est la raison d'etre
    # de la nouvelle.
    assert result.max_neutral_degradation_de76 < 0.0
    assert result.distortion_budget_met is True
    assert result.max_degradation_de76 > result.max_neutral_degradation_de76


def test_la_degradation_est_bien_la_difference_des_deux_distances():
    """La formule, epinglee terme a terme: `dE76(corrige, ref) - dE76(brut, ref)`.

    Sans cet ancrage, un budget calcule sur `dE76(corrige, brut)` -- la formule que
    l'arbitrage suggere et que la mesure a fait ecarter -- passerait tous les autres
    tests de ce bloc en changeant ce que le critere signifie.
    """
    corrected, reference, raw = _neutral_page(corrected=_triplets(
        **{"a-rouge": (0.11, 0.16, 0.74),
           "b-gris-sombre": (0.21, 0.21, 0.21),
           "c-gris-clair": (0.79, 0.79, 0.79),
           "d-vert": (0.21, 0.59, 0.26)}))
    result = cm.evaluate_page_acceptance(
        measured=corrected, reference=reference, measured_raw=raw,
        values_version="patch-values-2")
    cles = tuple(sorted(reference))
    apres = cm.delta_e76_srgb_d65(
        np.asarray([corrected[key] for key in cles]),
        np.asarray([reference[key] for key in cles]))
    avant = cm.delta_e76_srgb_d65(
        np.asarray([raw[key] for key in cles]),
        np.asarray([reference[key] for key in cles]))
    assert result.mean_degradation_de76 == pytest.approx(float((apres - avant).mean()))
    grises = [k for k, key in enumerate(cles) if cm.is_grey_reference(reference[key])]
    assert result.max_neutral_degradation_de76 == pytest.approx(
        float((apres - avant)[grises].max()))
    # Et la distorsion brute, elle, est une **autre** grandeur: le test serait vide si
    # les deux coincidaient.
    brute = cm.delta_e76_srgb_d65(
        np.asarray([corrected[key] for key in cles]),
        np.asarray([raw[key] for key in cles]))
    assert float(brute.mean()) != pytest.approx(result.mean_degradation_de76)


def test_aucun_plafond_du_budget_n_est_pose_en_litteral_hors_du_registre():
    """Frontiere negative, meme regle que le seuil de divergence d'`EPIC5-ARB-57`.

    Un `2.5` ecrit au point d'usage rendrait le registre decoratif: le nombre qui
    decide et le nombre qui se relit seraient deux.
    """
    import ast
    import inspect

    budget = cm.get_distortion_budget(cm.ACTIVE_DISTORTION_BUDGET_ID)
    plafond = budget.max_neutral_degradation_de76

    def lignes_portant_le_plafond(source):
        """Les lignes de `source` ou la **valeur** du plafond est ecrite en dur.

        La premiere version de ce test comptait la sous-chaine `"=2.5"` -- finding de la
        revue de 5.20, ferme le 2026-08-19. Elle ne voyait ni `= 2.5`, ni `2.50`, ni
        `2.5e0`, ni `float("2.5")`, c'est-a-dire aucune des reecritures qu'une relecture
        ou un formateur produisent naturellement: la garde etait contournable **sans
        intention**. La lecture passe donc par l'arbre syntaxique et compare des
        **valeurs**, ce qu'aucune orthographe ne change.
        """
        lignes = []
        for noeud in ast.walk(ast.parse(source)):
            if not isinstance(noeud, ast.Constant) or isinstance(noeud.value, bool):
                continue
            valeur = noeud.value
            if isinstance(valeur, (int, float)) and float(valeur) == plafond:
                lignes.append(noeud.lineno)
            elif isinstance(valeur, str):
                try:
                    egal = float(valeur.strip()) == plafond
                except ValueError:
                    egal = False
                if egal:
                    lignes.append(noeud.lineno)
        return lignes

    # La valeur n'apparait que dans l'entree de registre elle-meme (module `cm`).
    dans_cm = lignes_portant_le_plafond(inspect.getsource(cm))
    dans_cc = lignes_portant_le_plafond(inspect.getsource(cc))
    assert len(dans_cm) == 1, (
        f"color_metrics: lignes {dans_cm} portent le plafond en litteral, une seule "
        "(l'entree de registre) est licite")
    assert dans_cc == [], f"color_calibration: lignes {dans_cc} portent le plafond"

    # Et la lecture est bien celle qu'on croit. Les cinq orthographes sont donnees en
    # **litteral** -- ce sont les quatre reecritures dont l'ancienne version ne voyait
    # aucune, plus la forme nominale -- et le temoin negatif ferme le test: une valeur
    # voisine ne doit pas etre confondue avec le plafond.
    assert plafond == 2.5, "le temoin ci-dessous est ecrit pour un plafond de 2,5"
    for reecriture in ("PLAFOND = 2.5", "PLAFOND =  2.5", "PLAFOND = 2.50",
                       "PLAFOND = 2.5e0", 'PLAFOND = float("2.5")'):
        assert lignes_portant_le_plafond(reecriture) == [1], (
            f"la reecriture {reecriture!r} echappe encore a la garde")
    for voisine in ("PLAFOND = 2.4", "PLAFOND = 25", 'PLAFOND = "deux et demi"'):
        assert lignes_portant_le_plafond(voisine) == [], (
            f"{voisine!r} n'est pas le plafond et ne doit pas etre compte")


# ---------------------------------------------------------------------------
# Story 5.23 (`EPIC5-ARB-82`) : les deux entrees de registre neuves
# ---------------------------------------------------------------------------


def test_le_seuil_de_divergence_brute_est_lu_au_registre_avec_sa_valeur_initiale():
    """AC 6: 5,0 dE76 d'ecart brut moyen, et il se lit par identifiant."""
    guard = cm.get_raw_divergence_guard("color-divergence-2")
    assert guard is cm.get_raw_divergence_guard(cm.ACTIVE_RAW_DIVERGENCE_GUARD_ID)
    assert guard.divergence_id == "color-divergence-2"
    assert guard.max_mean_raw_de76 == 5.0
    assert tuple(cm.RAW_DIVERGENCE_REGISTRY) == ("color-divergence-2",)


def test_une_entree_de_divergence_brute_refuse_d_exister_sans_reserves():
    """AC 6: meme garde que `color-divergence-1`, a la **construction**.

    Une reserve rangee dans un document se perd a la premiere reprise; ici elle est
    exigee par le constructeur, donc une entree muette n'est pas ecrivable.
    """
    with pytest.raises(ValueError, match="reserves"):
        cm.RawDivergenceGuard(
            divergence_id="color-divergence-test",
            max_mean_raw_de76=5.0,
            reservations=(),
        )
    # Et les trois autres invariants de valeur, chacun avec son regime.
    for valeur in (0.0, -1.0, float("nan"), float("inf"), "5.0", True):
        with pytest.raises(ValueError):
            cm.RawDivergenceGuard(
                divergence_id="color-divergence-test",
                max_mean_raw_de76=valeur,
                reservations=("une reserve",),
            )


def test_les_reserves_de_divergence_2_disent_le_provisoire_et_la_non_confusion():
    """AC 6: le minimum exige par la story, verifie sur le **texte** des reserves.

    Les deux enonces sont les seuls qui rendent l'entree relisible: sans le premier, le
    5,0 se lit comme une mesure; sans le second, il se lit comme « le 1,0 releve », ce
    qui est faux -- ce n'est pas la meme grandeur.
    """
    reserves = cm.get_raw_divergence_guard("color-divergence-2").reservations
    assert len(reserves) >= 3
    assert any("PROVISOIRE" in reserve for reserve in reserves)
    assert any("scan reel" in reserve for reserve in reserves)
    assert any("GRANDEUR DIFFERENTE" in reserve for reserve in reserves)
    assert any("color-divergence-1" in reserve for reserve in reserves)
    # L'ancienne entree reste lisible: c'est le vocabulaire des manifests deja ecrits.
    assert cm.get_divergence_guard("color-divergence-1").max_excess_residual_de76 == 1.0


def test_la_frontiere_du_seuil_de_divergence_brute_est_strictement_au_dessus():
    """AC 4: un ecart **egal** au seuil n'avertit pas, un ecart au-dessus avertit.

    Les deux bouts sont epingles au plus pres du seuil, avec un ecart d'un ulp: c'est
    ce qui tue le mutant `>` / `>=`, qu'une comparaison a 4,0 et 6,0 laisserait vivre.
    """
    seuil = cm.get_raw_divergence_guard(cm.ACTIVE_RAW_DIVERGENCE_GUARD_ID)
    plafond = seuil.max_mean_raw_de76
    assert not cm.raw_divergence_exceeds(plafond)
    assert cm.raw_divergence_exceeds(np.nextafter(plafond, plafond + 1.0))
    assert not cm.raw_divergence_exceeds(np.nextafter(plafond, 0.0))
    assert not cm.raw_divergence_exceeds(0.0)
    with pytest.raises(cm.ColorMetricError):
        cm.raw_divergence_exceeds(float("nan"))
    with pytest.raises(cm.UnknownRawDivergenceGuardError):
        cm.raw_divergence_exceeds(1.0, "color-divergence-inexistant")


def test_le_plafond_de_degradation_maximale_est_lu_au_registre():
    """AC 7: une garde neuve sur la degradation maximale **toutes pastilles**."""
    guard = cm.get_max_degradation_guard("color-max-degradation-1")
    assert guard is cm.get_max_degradation_guard(cm.ACTIVE_MAX_DEGRADATION_GUARD_ID)
    assert guard.max_degradation_de76 == 25.0
    assert guard.observed_max_de76 == 20.7
    # La grandeur gardee n'est **pas** celle du budget de distorsion: celui-ci plafonne
    # la moyenne et le maximum de l'axe neutre, et le dit lui-meme dans ses reserves.
    budget = cm.get_distortion_budget(cm.ACTIVE_DISTORTION_BUDGET_ID)
    assert budget.max_neutral_degradation_de76 != guard.max_degradation_de76
    assert any("toutes" in reserve for reserve in budget.reservations)


def test_une_entree_de_degradation_maximale_refuse_d_exister_sans_reserves():
    commun = {"guard_id": "color-max-degradation-test",
              "max_degradation_de76": 25.0,
              "observed_max_de76": 20.7}
    with pytest.raises(ValueError, match="reserves"):
        cm.MaxDegradationGuard(**commun, reservations=())
    # Un plafond **sous** le pire cas deja mesure avertirait sur tout ce qui est livre:
    # refuse a la construction, comme pour `DivergenceGuard` et le budget.
    with pytest.raises(ValueError, match="deja observee"):
        cm.MaxDegradationGuard(
            guard_id="color-max-degradation-test",
            max_degradation_de76=15.0,
            observed_max_de76=20.7,
            reservations=("une reserve",),
        )
    with pytest.raises(ValueError, match="deja observee"):
        cm.MaxDegradationGuard(
            guard_id="color-max-degradation-test",
            max_degradation_de76=20.7,
            observed_max_de76=20.7,
            reservations=("une reserve",),
        )


def test_les_reserves_du_plafond_de_degradation_disent_qu_il_attend_une_mesure():
    reserves = cm.get_max_degradation_guard("color-max-degradation-1").reservations
    assert len(reserves) >= 3
    assert any("PROVISOIRE" in reserve for reserve in reserves)
    assert any("scan reel" in reserve for reserve in reserves)
    # Et la reserve la plus importante de toutes: la garde est INERTE sur tout ce qui a
    # ete mesure. Une garde annoncee sans son domaine d'activation n'est pas une
    # garantie, et c'est l'entree elle-meme qui doit le dire.
    assert any("INERTE" in reserve for reserve in reserves)


def test_la_garde_de_degradation_est_inerte_sur_le_mesure_et_mordante_au_dela():
    """AC 7: epinglee par ses **deux** bouts.

    Volet d'inertie: les trois regimes reellement mesures dans ce depot -- le profil
    ajuste au lot de reference `chendj-mat` (+15,80), et les bornes de l'enveloppe des
    quatre formes de la story 5.20 (+9,6 et +20,7) -- ne declenchent rien. Volet de
    mordant: un profil construit pour la declencher la declenche.
    """
    for mesure in (9.6, 15.8, 20.7):
        assert not cm.max_degradation_exceeds(mesure), mesure
    plafond = cm.get_max_degradation_guard(
        cm.ACTIVE_MAX_DEGRADATION_GUARD_ID).max_degradation_de76
    assert not cm.max_degradation_exceeds(plafond)
    assert cm.max_degradation_exceeds(np.nextafter(plafond, plafond + 1.0))
    assert cm.max_degradation_exceeds(40.0)
    # `None` -- « rien n'a ete mesure » -- ne declenche pas: avertir sur une mesure
    # absente serait inventer un chiffre.
    assert not cm.max_degradation_exceeds(None)
    with pytest.raises(cm.ColorMetricError):
        cm.max_degradation_exceeds(float("nan"))
    with pytest.raises(cm.UnknownMaxDegradationGuardError):
        cm.max_degradation_exceeds(1.0, "color-max-degradation-inexistant")


def test_aucun_des_deux_seuils_neufs_n_est_pose_en_litteral_hors_du_registre():
    """`EPIC5-ARB-52`: un seuil ecrit au point d'usage rend le registre decoratif."""
    import inspect

    seuil = cm.get_raw_divergence_guard(cm.ACTIVE_RAW_DIVERGENCE_GUARD_ID)
    plafond = cm.get_max_degradation_guard(cm.ACTIVE_MAX_DEGRADATION_GUARD_ID)
    for module in (cm, cc):
        source = inspect.getsource(module)
        for valeur, attendu in (
            (seuil.max_mean_raw_de76, 1 if module is cm else 0),
            (plafond.max_degradation_de76, 1 if module is cm else 0),
        ):
            occurrences = source.count(f"={valeur}")
            assert occurrences == attendu, (module.__name__, valeur, occurrences)
