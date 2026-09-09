"""Calibration couleur active : la correction `C = M o A` et sa metrique.

Story 5.4b. **Rien n'est tranche ici** : la forme de la correction, le domaine de
travail, la ponderation, la metrique et ses seuils sont donnes par le Gate 4 ferme
par la story 5.4a, et ce module les applique verbatim. Les renvois sont nommes a
chaque fonction pour qu'une relecture puisse confronter le code a la decision et
non a une reformulation :

* `EPIC5-ARB-25` -- la correction s'ajuste et s'applique dans le domaine
  **linearise** sRGB (IEC 61966-2-1), et le resultat est reencode ensuite ;
* `EPIC5-ARB-26` -- `C = M o A` : etage `A` affine par canal (6 parametres) ajuste
  sur les seules valeurs de role `neutral_axis`, puis etage `M`, matrice 3x3 dont
  **chaque ligne somme a 1** (6 parametres libres), ajustee sur le jeu d'ajustement
  apres `A` ;
* `EPIC5-ARB-28` -- critere `delta_e76_srgb_d65`, diagnostic
  `channel_relative_deviation`, seuils de l'entree `color-acceptance-1` ;
* `EPIC5-ARB-29` -- les jeux se lisent **par role et par preset**, jamais par
  enumeration litterale ;
* `EPIC5-ARB-31` -- moindres carres de l'etage `A` **ponderes** par le carre du
  jacobien de l'OETF au point de reference, et **garde de non-degradation**.

Contrat d'ordre des canaux : **BGR**, celui de toute la chaine
(`color_pipeline.py`). Les valeurs de reference de `patch_values` sont declarees en
**RGB** ; la conversion se fait a un endroit unique et explicite, et elle est
verrouillee par un test asymetrique -- une inversion R/B ne casse pas une image, elle
produit une correction qui converge sur les mauvaises couleurs et rend un resultat
**plausible**.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Protocol, runtime_checkable

import numpy as np

from . import patch_values
from .io import calibration_profile
from .numeric_guards import is_strict_int, is_strict_number

# ---------------------------------------------------------------------------
# EPIC5-ARB-25 : fonctions de transfert, ecrites ici pour que rien ne les choisisse
# ---------------------------------------------------------------------------

#: Seuils et coefficients de l'IEC 61966-2-1, nommes plutot que semes en litteraux.
_EOTF_KNEE, _OETF_KNEE = 0.04045, 0.0031308
_SLOPE, _OFFSET, _GAMMA = 12.92, 0.055, 2.4


def eotf(encoded):
    """Encode sRGB [0, 1] -> lineaire. `EPIC5-ARB-25`, formule verbatim."""
    values = np.asarray(encoded, dtype=np.float64)
    return np.where(values <= _EOTF_KNEE,
                    values / _SLOPE,
                    ((values + _OFFSET) / (1.0 + _OFFSET)) ** _GAMMA)


def oetf(linear):
    """Lineaire -> encode sRGB [0, 1]. `EPIC5-ARB-25`, formule verbatim.

    L'ecretage a [0, 1] **n'est pas fait ici** : `EPIC5-ARB-30` en fait un point de
    decision nomme, et l'enfouir dans la fonction de transfert le rendrait invisible.
    """
    values = np.asarray(linear, dtype=np.float64)
    with np.errstate(invalid="ignore"):
        curved = (1.0 + _OFFSET) * np.power(np.maximum(values, 0.0), 1.0 / _GAMMA) - _OFFSET
    return np.where(values <= _OETF_KNEE, _SLOPE * values, curved)


def oetf_jacobian_squared(linear):
    """`w = (ds/dL)^2` evalue en `L`. **Ponderation de `EPIC5-ARB-31`, clause 1.**

    En lumiere lineaire les quatre ancres neutres de `patch-values-2` valent
    0,0070 / 0,1559 / 0,5776 / 0,9131 : `neutral-020` ne pese que 0,70 % de la
    dynamique, et un moindre carre **non** pondere l'ignore presque completement --
    mesure a l'appui, il rend l'ancre sombre 35 fois pire que ne rien faire, tout en
    restant `applied`. Ponderer par le jacobien de l'OETF revient a minimiser
    l'erreur **telle qu'elle sera vue apres reencodage**, sans quitter le domaine
    lineaire qu'`EPIC5-ARB-25` impose.

    Propriete qui justifie de la prendre partout: si la distorsion est vraiment
    affine dans la lumiere, le fit pondere et le fit non pondere rendent les memes
    coefficients. La ponderation est donc neutre la ou le modele tient et
    reparatrice la ou il ne tient pas.
    """
    values = np.asarray(linear, dtype=np.float64)
    curved = ((1.0 + _OFFSET) / _GAMMA) ** 2 * np.power(
        np.maximum(values, np.finfo(np.float64).tiny), 2.0 * (1.0 / _GAMMA - 1.0))
    return np.where(values <= _OETF_KNEE, _SLOPE ** 2, curved)


# ---------------------------------------------------------------------------
# EPIC5-ARB-28 : le critere, le diagnostic et les seuils vivent dans color_metrics
# ---------------------------------------------------------------------------
#
# Ils y ont ete **deplaces** le 2026-08-11, sur le bloquant B4 de la revue en trois
# couches: l'arbitrage nomme le module, la fonction, la dataclasse de sortie et
# l'exception, et rien de tout cela n'existait. Les noms sont reimportes ici parce que
# c'est ce module qui orchestre une page -- mais ils ne sont plus **definis** deux fois:
# deux definitions de la metrique qui divergeraient rendraient la correction fausse d'un
# cote sans qu'aucun test des deux modules ne le voie.

from .color_metrics import (  # noqa: E402
    ACTIVE_COLOR_ACCEPTANCE_ID,
    ACTIVE_DISTORTION_BUDGET_ID,
    ACTIVE_DIVERGENCE_GUARD_ID,
    COLOR_ACCEPTANCE_REGISTRY,
    COLOR_DISTORTION_REGISTRY,
    DEGRADATION_TOLERANCE_DE76 as _DEGRADATION_TOLERANCE_DE76,
    DIVERGENCE_REGISTRY,
    FAILURE_DEGRADES_RESIDUAL,
    FAILURE_DISTORTION_BUDGET,
    FAILURE_METRIC,
    SRGB_TO_XYZ_D65_BGR,
    ColorAcceptance,
    ColorDistortionBudget,
    ColorMetricError,
    DivergenceGuard,
    PageAcceptanceResult,
    UnknownColorAcceptanceError,
    UnknownColorDistortionBudgetError,
    UnknownDivergenceGuardError,
    channel_relative_deviation,
    delta_e76_srgb_d65,
    evaluate_page_acceptance,
    get_color_acceptance,
    get_distortion_budget,
    get_divergence_guard,
    # Story 5.23: les deux registres neufs et la mesure brute a brute. Importes
    # nommement comme tout le reste du module: la garde de divergence brute et la garde
    # de degradation maximale sont **consultees** ici, jamais redigees.
    ACTIVE_MAX_DEGRADATION_GUARD_ID,
    ACTIVE_RAW_DIVERGENCE_GUARD_ID,
    get_max_degradation_guard,
    get_raw_divergence_guard,
    max_degradation_exceeds,
    raw_divergence_de76,
    raw_divergence_exceeds,
    is_grey_reference,
    lab_from_linear_bgr,
    lab_from_srgb_bgr,
    linear_bgr_from_lab,
)

#: Identifiant de la **forme** de correction, `C = M o A` d'`EPIC5-ARB-26`. Porte par le
#: profil et par le resultat de page, y compris sur un echec: un echec dont on ne sait
#: pas quelle forme a echoue n'est pas relisable.
CORRECTION_FORM_ID = "color-correction-affine-matrix-1"

#: Seconde forme, **ajoutee a cote de la premiere et jamais a sa place** (story 5.16,
#: AC 1, mandat d'`EPIC5-ARB-53`): `L*` affine ajustee sur le seul axe neutre, puis
#: `(a*, b*)` par une 2x2 avec decalage ajustee sur tous les points d'ajustement.
#:
#: Ce qu'elle achete, et c'est un changement de **famille** et non de reglage: les deux
#: etages sont **orthogonaux par construction** -- corriger `L*` ne deplace ni `a*` ni
#: `b*`. La forme en vigueur ne le garantit pas: son etage `A` applique des gains par
#: canal RGB ajustes sur les gris, donc il deplace les rapports entre canaux de toute
#: couleur non neutre, donc sa teinte. Mesure du 2026-08-10: `A` seule laisse 3,37 dE76
#: de biais de chroma sur la peau la ou le scan brut n'en a que 0,94.
CORRECTION_FORM_LAB_ID = "color-correction-lab-lightness-chroma-1"

#: Provenance de la correction appliquee a une page (story 5.16, AC 10). Deux regimes,
#: deux valeurs: sans ce champ, une frame corrigee depuis la page de calibration du lot
#: et une frame corrigee depuis les pastilles de sa propre feuille seraient
#: **indistinguables au manifest**, et c'est precisement ce qu'on relit quand un
#: resultat surprend. Declares ici, tout en haut, parce que `PageCalibration` en porte
#: le defaut.
CORRECTION_SOURCE_OWN_SHEET = "own_sheet_patches"
CORRECTION_SOURCE_CALIBRATION_PAGE = "lot_calibration_page"
#: Provenance d'une correction appliquee depuis un **profil de chaine** (story
#: 5.22, `EPIC5-ARB-80`): le profil a ete ajuste une fois par `scan calibrate`
#: sur une page de calibration, consigne dans le projet sous `versions/`, puis
#: **reutilise** pour tous les lots de la chaine -- jamais re-ajuste sur une
#: page du lot. Le champ source du manifest designe le profil (par son
#: `chain_id`), pas une page du lot (`AC 5`).
CORRECTION_SOURCE_CHAIN_PROFILE = "chain_profile"


# ---------------------------------------------------------------------------
# EPIC5-ARB-26 : les deux etages
# ---------------------------------------------------------------------------

def fit_stage_a(measured_linear, reference_linear, weights=None):
    """Etage `A`: gain et decalage **par canal**, 6 parametres. `EPIC5-ARB-26`.

    Ajuste sur les seules valeurs de role `neutral_axis` -- l'appelant les a deja
    filtrees par `EPIC5-ARB-29`, ce module ne connait aucune enumeration litterale.
    Ponderation par defaut: celle d'`EPIC5-ARB-31`, evaluee sur la **reference**.
    """
    measured = np.atleast_2d(np.asarray(measured_linear, dtype=np.float64))
    reference = np.atleast_2d(np.asarray(reference_linear, dtype=np.float64))
    if measured.shape != reference.shape or measured.shape[-1] != 3:
        raise ValueError(
            f"formes incompatibles: {measured.shape} contre {reference.shape}, "
            "trois canaux attendus."
        )
    if len(measured) < 2:
        # Deux points au moins par canal: une affine a deux parametres ajustee sur un
        # seul point est indeterminee, et `lstsq` rendrait une solution de norme
        # minimale d'apparence valide.
        raise ValueError(
            f"etage A: {len(measured)} valeur(s) d'axe neutre, deux au minimum."
        )
    if weights is None:
        weights = oetf_jacobian_squared(reference)
    weights = np.broadcast_to(np.asarray(weights, dtype=np.float64), reference.shape)

    parameters = np.empty((3, 2), dtype=np.float64)
    for channel in range(3):
        root = np.sqrt(weights[:, channel])
        design = np.stack([measured[:, channel], np.ones(len(measured))], axis=1)
        parameters[channel] = np.linalg.lstsq(
            design * root[:, None], reference[:, channel] * root, rcond=None)[0]
    return parameters


def apply_stage_a(parameters, linear):
    values = np.asarray(linear, dtype=np.float64)
    gains = np.asarray(parameters, dtype=np.float64)[:, 0]
    offsets = np.asarray(parameters, dtype=np.float64)[:, 1]
    return values * gains + offsets


def fit_stage_m(after_a_linear, reference_linear):
    """Etage `M`: 3x3 dont **chaque ligne somme a 1**, 6 parametres libres.

    La contrainte n'est pas decorative et n'est pas ajoutee apres coup: elle est
    **parametree**, ligne par ligne, sous la forme
    `out_c - in_3 = u (in_i - in_c) + v (in_j - in_c)`. Elle laisse donc tout triplet
    neutre invariant, ce qui rend les deux etages orthogonaux -- `M` ne peut pas
    defaire sur l'axe neutre ce qu'`A` vient d'y fixer -- et fait tomber les
    9 parametres d'une 3x3 libre a 6.

    Corollaire mesure et ecrit dans `EPIC5-ARB-26`: pour un triplet neutre les deux
    regresseurs valent 0, donc les valeurs d'axe neutre ne contraignent pas `M`. Sur
    `patch-values-2`, 6 lignes informatives sur 10.
    """
    source = np.atleast_2d(np.asarray(after_a_linear, dtype=np.float64))
    target = np.atleast_2d(np.asarray(reference_linear, dtype=np.float64))
    if source.shape != target.shape or source.shape[-1] != 3:
        raise ValueError(
            f"formes incompatibles: {source.shape} contre {target.shape}, "
            "trois canaux attendus."
        )
    if len(source) < 2:
        # Deux regresseurs libres par ligne: un seul point les laisse indetermines et
        # `lstsq` rendrait la solution de norme minimale -- donc l'**identite**, une
        # matrice d'apparence parfaitement valide qui ne corrige rien. Symetrique de la
        # garde de `fit_stage_a`, qui manquait ici (finding mineur de la couche 2).
        raise ValueError(
            f"etage M: {len(source)} valeur(s) informative(s), deux au minimum. "
            "Une 3x3 ajustee sur un point rendrait l'identite sans le dire.")
    rows = []
    for channel in range(3):
        others = [index for index in range(3) if index != channel]
        design = np.stack([source[:, index] - source[:, channel] for index in others],
                          axis=1)
        solved = np.linalg.lstsq(design, target[:, channel] - source[:, channel],
                                 rcond=None)[0]
        row = np.zeros(3, dtype=np.float64)
        row[channel] = 1.0 - float(solved.sum())
        for index, value in zip(others, solved):
            row[index] = float(value)
        rows.append(row)
    return np.asarray(rows, dtype=np.float64)


@runtime_checkable
class AnyCorrectionProfile(Protocol):
    """Ce qu'un profil de correction doit porter pour etre **applique**, quelle que soit sa forme.

    Mineur m6 de la couche 1 de la revue de 5.16: `PageCalibration.profile` etait annote
    `CorrectionProfile | None` alors que le champ recoit **aussi** un
    `LabCorrectionProfile`, la story 5.16 rendant explicitement les deux formes
    interchangeables. Aucun effet a l'execution -- rien ne verifie les types ici -- mais
    c'etait la seule declaration du module qui **contredisait** le protocole que la story
    installe, et une annotation fausse est lue comme une intention.

    C'est un `Protocol` et non l'union `CorrectionProfile | LabCorrectionProfile`, pour la
    raison meme qui a fait ecrire les deux formes ainsi: une union se **reecrit a chaque
    forme nouvelle**, dans les trois sites qui l'annoncent, et c'est exactement le couplage
    que la docstring de `LabCorrectionProfile` dit vouloir eviter -- « un `isinstance` a ces
    endroits aurait fait de chaque forme nouvelle une modification de tous ». Les deux
    membres nommes ici sont les deux que `apply_profile_to_image` et
    `apply_correction_to_frames` consomment reellement, ni plus ni moins.

    Il est `runtime_checkable` pour rester **verifiable par un test** plutot que par un
    lecteur: un `isinstance` est possible dans la suite, ou il constate que les deux formes
    livrees satisfont le protocole. Ce depot ne s'en sert pas dans le code de production,
    ou une forme nouvelle doit passer sans qu'aucun point d'application la reconnaisse.
    """

    #: Identifiant de la **forme** de correction, celui que le manifest inscrit.
    correction_id: str

    def apply_linear(self, linear):
        """Appliquer la correction a une image lineaire, et rendre une image lineaire."""
        ...


@dataclass(frozen=True)
class CorrectionProfile:
    """Le profil de correction d'**une** page. `color-correction-affine-matrix-1`.

    Porte les deux etages et l'identifiant de forme, jamais une image. C'est le
    « type ou protocole de profil de correction » que l'AC 6 de 5.4b demande en
    remplacement de `request_active_calibration`, dont la revue de 5.5 a dit qu'il
    n'etait « pas un hook mais une exception non branchee ».
    """

    stage_a: np.ndarray
    stage_m: np.ndarray
    correction_id: str = CORRECTION_FORM_ID

    def apply_linear(self, linear):
        """`A` puis `M`, **dans l'ordre de l'ajustement** (`EPIC5-ARB-26`)."""
        return apply_stage_a(self.stage_a, linear) @ np.asarray(self.stage_m).T


def fit_correction(measured_bgr, reference_bgr, neutral_mask) -> CorrectionProfile:
    """Ajuster `C = M o A` sur une page. Entrees en sRGB encode, ordre **BGR**.

    `neutral_mask` designe les valeurs de role `neutral_axis`, resolues par
    l'appelant depuis le preset (`EPIC5-ARB-29`): ce module ne porte aucune
    enumeration de `value_id`, faute de quoi une planche `patches-12-v1` et une
    planche `patches-18-v2` s'ajusteraient sur le meme jeu ecrit en dur.
    """
    mask = np.asarray(neutral_mask, dtype=bool)
    measured_linear = eotf(measured_bgr)
    reference_linear = eotf(reference_bgr)
    stage_a = fit_stage_a(measured_linear[mask], reference_linear[mask])
    after_a = apply_stage_a(stage_a, measured_linear)
    stage_m = fit_stage_m(after_a, reference_linear)
    return CorrectionProfile(stage_a=stage_a, stage_m=stage_m)


# ---------------------------------------------------------------------------
# Story 5.16, AC 1 et 2 : la seconde forme, et ses cardinaux gardes
# ---------------------------------------------------------------------------

#: Cardinaux minimaux de la forme Lab, **nommes** plutot que semes dans les gardes.
#:
#: `L*` est une affine a deux parametres: deux clartes neutres **distinctes** au moins,
#: sans quoi la droite est indeterminee. La 2x2 avec decalage a trois parametres libres
#: par sortie: trois points de chroma **distincts** au moins.
MIN_DISTINCT_NEUTRALS_FOR_LIGHTNESS = 2
MIN_DISTINCT_CHROMA_POINTS = 3

#: Motifs de refus des deux gardes, **assertables par leur chaine** (AC 2). Ils ne sont
#: pas decoratifs: le defaut qu'ils ferment est celui corrige sur `fit_stage_m` le
#: 2026-08-11, ou un seul point rendait l'**identite** -- une matrice parfaitement
#: valide qui ne corrige rien, donc un faux succes et non une erreur.
REFUSAL_LIGHTNESS_NEEDS_TWO_NEUTRALS = "lightness_needs_two_distinct_neutrals"
REFUSAL_CHROMA_NEEDS_THREE_POINTS = "chroma_needs_three_distinct_points"


class UnderdeterminedAdjustmentSet(ValueError):
    """Le jeu d'ajustement n'atteint pas le cardinal minimal de la forme demandee.

    Sous-classe de `ValueError` **deliberement**: `calibrate_page` attrape deja
    `ValueError` pour rendre `FAILURE_UNDERDETERMINED_ADJUSTMENT`, donc la nouvelle
    forme entre dans le vocabulaire d'echec existant de l'AC 8 sans en ouvrir un
    second. Ce qu'elle ajoute est le **motif nomme** (`reason`), que l'AC 2 exige
    assertable par sa chaine: « refuse » et « refuse pour cette raison » ne sont pas la
    meme garantie, et c'est la seconde qui empeche qu'une matrice identite reapparaisse
    sous un autre pretexte.
    """

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(f"{reason}: {message}")
        self.reason = reason


def distinct_neutral_lightness_count(measured_lab, neutral_mask) -> int:
    """Cardinal des clartes neutres **distinctes** du jeu d'ajustement.

    La distinction se juge sur la valeur **mesuree** et non sur la reference, parce que
    c'est la mesure qui forme la colonne de la matrice de conception. Deux references
    distinctes (`neutral-065` et `neutral-200`) lues identiquement -- scan sature,
    plancher d'encrage -- laissent l'affine tout aussi indeterminee, et `lstsq` rendrait
    alors la solution de norme minimale: une pente proche de zero, c'est-a-dire « ecraser
    toute la page sur une seule clarte ». Resultat plausible, donc non detecte.

    Distinction **exacte** et non a tolerance: une tolerance serait un seuil, donc une
    entree d'arbitrage, et la garde porte sur la rang-deficience et non sur son
    voisinage. Le voisinage (deux neutres presque confondus) est une question ouverte
    distincte, versee au `deferred-work.md` plutot que tranchee en passant.
    """
    lightness = np.asarray(measured_lab, dtype=np.float64)[
        np.asarray(neutral_mask, dtype=bool), 0]
    return int(np.unique(lightness).size)


def distinct_chroma_point_count(lab, neutral_mask) -> int:
    """Cardinal des points de chroma **distincts**, les neutres comptant pour un seul.

    Regle de comptage donnee mot pour mot par l'AC 2: « les neutres comptent pour un
    seul point, leur chroma cible etant nulle ». Elle est **deliberement
    conservatrice** -- mathematiquement, deux neutres mesures a des chroma differentes
    forment bien deux lignes distinctes de la conception --, et c'est le bon sens de
    l'erreur: sous-compter ne peut que refuser davantage, jamais laisser passer un jeu
    indetermine. Tous les neutres tirent la meme contrainte utile (« ne pas colorer un
    gris »), et un jeu qui n'aurait que des neutres ne contraint pas une 2x2.

    **Le parametre s'appelle `lab` et non `measured_lab`** (finding de revue de 5.20,
    ferme le 2026-08-19). Les deux appelants ne lui donnent pas la meme chose, et c'est
    delibere des deux cotes: `fit_lab_chroma` compte sur la **mesure**, la forme
    courbe+chroma sur la **reference** -- pour le motif mesure ecrit a son point d'appel.
    Un nom qui annonce la mesure faisait donc de l'un des deux appels une contradiction
    apparente, et l'asymetrie reelle -- qui est un choix -- se lisait comme un oubli.
    """
    chroma = np.asarray(lab, dtype=np.float64)[..., 1:3]
    mask = np.asarray(neutral_mask, dtype=bool)
    non_neutral = np.unique(chroma[~mask], axis=0) if (~mask).any() else np.empty((0, 2))
    return int(len(non_neutral)) + int(bool(mask.any()))


def fit_lab_lightness(measured_lab, reference_lab, neutral_mask):
    """`L*` affine, ajustee sur le **seul axe neutre**. Rend (pente, decalage).

    Sur le seul axe neutre parce que c'est la ou la clarte est mesurable sans que la
    teinte s'y melange, et parce que c'est le choix mesure le 2026-08-10: ajuster sur
    tous les points sur-corrige la peau de ~3 unites de `L*`.
    """
    measured = np.atleast_2d(np.asarray(measured_lab, dtype=np.float64))
    reference = np.atleast_2d(np.asarray(reference_lab, dtype=np.float64))
    mask = np.asarray(neutral_mask, dtype=bool)
    distinct = distinct_neutral_lightness_count(measured, mask)
    if distinct < MIN_DISTINCT_NEUTRALS_FOR_LIGHTNESS:
        raise UnderdeterminedAdjustmentSet(
            REFUSAL_LIGHTNESS_NEEDS_TWO_NEUTRALS,
            f"l'affine de clarte de '{CORRECTION_FORM_LAB_ID}' exige "
            f"{MIN_DISTINCT_NEUTRALS_FOR_LIGHTNESS} clartes neutres distinctes, "
            f"{distinct} trouvee(s) sur {int(mask.sum())} neutre(s). Une affine "
            "ajustee sur un point unique rendrait la solution de norme minimale, "
            "c'est-a-dire une correction qui ne corrige rien sans le dire.")
    lightness = measured[mask, 0]
    design = np.stack([lightness, np.ones(len(lightness))], axis=1)
    solved = np.linalg.lstsq(design, reference[mask, 0], rcond=None)[0]
    return float(solved[0]), float(solved[1])


def fit_lab_chroma(measured_lab, reference_lab, neutral_mask):
    """`(a*, b*)` par une 2x2 **avec decalage**, sur TOUS les points d'ajustement.

    Tous les points, neutres compris: un neutre y contribue legitimement, sa chroma
    cible etant nulle, donc il tire la correction vers « ne pas colorer un gris » --
    ce qui est exactement voulu.

    Rend (matrice 2x2, decalage 2). L'application est `ab @ matrice.T + decalage`, et
    elle ne touche **jamais** a `L*`: c'est l'orthogonalite de l'AC 1, et elle est une
    propriete de la forme, pas une precaution d'ecriture.
    """
    measured = np.atleast_2d(np.asarray(measured_lab, dtype=np.float64))
    reference = np.atleast_2d(np.asarray(reference_lab, dtype=np.float64))
    mask = np.asarray(neutral_mask, dtype=bool)
    distinct = distinct_chroma_point_count(measured, mask)
    if distinct < MIN_DISTINCT_CHROMA_POINTS:
        raise UnderdeterminedAdjustmentSet(
            REFUSAL_CHROMA_NEEDS_THREE_POINTS,
            f"la 2x2 avec decalage de '{CORRECTION_FORM_LAB_ID}' exige "
            f"{MIN_DISTINCT_CHROMA_POINTS} points de chroma distincts, {distinct} "
            "trouve(s) (les neutres comptent pour un seul point, leur chroma cible "
            "etant nulle). Sous ce cardinal, `lstsq` rendrait l'identite: une matrice "
            "valide qui ne corrige rien.")
    design = np.stack(
        [measured[:, 1], measured[:, 2], np.ones(len(measured))], axis=1)
    solved = np.linalg.lstsq(design, reference[:, 1:3], rcond=None)[0]
    return np.asarray(solved[:2].T, dtype=np.float64), np.asarray(
        solved[2], dtype=np.float64)


@dataclass(frozen=True)
class LabCorrectionProfile:
    """Le profil de correction d'une page sous `color-correction-lab-lightness-chroma-1`.

    Deux etages, **orthogonaux par construction**: `L*` par une affine, `(a*, b*)` par
    une 2x2 avec decalage. Meme protocole que `CorrectionProfile` -- `apply_linear` et
    `correction_id` --, et c'est ce qui rend les deux formes interchangeables partout ou
    une correction est **appliquee** (`apply_profile_to_image`,
    `apply_correction_to_frames`) sans qu'aucun de ces points ait a savoir laquelle il
    tient. Un `isinstance` a ces endroits aurait fait de chaque forme nouvelle une
    modification de tout le chemin d'application.
    """

    lightness_slope: float
    lightness_offset: float
    chroma_matrix: np.ndarray
    chroma_offset: np.ndarray
    correction_id: str = CORRECTION_FORM_LAB_ID

    def apply_linear(self, linear):
        """Lumiere lineaire BGR -> lumiere lineaire BGR, via Lab.

        L'aller-retour Lab est exact a 1e-15 pres (verrouille dans
        `test_color_metrics`), donc l'erreur de la correction est celle de son
        ajustement et non celle de sa representation.
        """
        values = lab_from_linear_bgr(np.asarray(linear, dtype=np.float64))
        corrected = np.empty_like(values)
        corrected[..., 0] = values[..., 0] * self.lightness_slope + self.lightness_offset
        corrected[..., 1:3] = (values[..., 1:3] @ np.asarray(self.chroma_matrix).T
                               + np.asarray(self.chroma_offset))
        return linear_bgr_from_lab(corrected)


def fit_correction_lab(measured_bgr, reference_bgr,
                       neutral_mask) -> LabCorrectionProfile:
    """Ajuster la forme Lab sur un jeu d'ajustement. Entrees en sRGB encode, **BGR**.

    Meme signature que `fit_correction`, au mot pres: c'est ce qui permet au registre
    de formes de les resoudre par identifiant sans que l'appelant ne se ramifie.
    """
    mask = np.asarray(neutral_mask, dtype=bool)
    measured_lab = lab_from_linear_bgr(eotf(measured_bgr))
    reference_lab = lab_from_linear_bgr(eotf(reference_bgr))
    slope, offset = fit_lab_lightness(measured_lab, reference_lab, mask)
    matrix, chroma_offset = fit_lab_chroma(measured_lab, reference_lab, mask)
    return LabCorrectionProfile(
        lightness_slope=slope, lightness_offset=offset,
        chroma_matrix=matrix, chroma_offset=chroma_offset)


# ---------------------------------------------------------------------------
# Story 5.20, AC 1, 3 et 6 : la troisieme forme, robuste a l'ecrasement des noirs
# ---------------------------------------------------------------------------

#: Troisieme forme, **ajoutee a cote des deux premieres et jamais a leur place**
#: (story 5.20, AC 1, mandat d'`EPIC5-ARB-72`): une courbe de tonalite monotone par
#: canal **ancree sur l'axe neutre**, puis un etage de chroma 2x2 **sans decalage** dans
#: Lab.
#:
#: **Ce qu'elle achete, et pourquoi une matrice unique ne pouvait pas l'acheter.** Le
#: scanner d'Egan ecrase les noirs de facon stable et reproductible -- trois mesures
#: independantes convergentes, la source de niveau 8 se lit a 60-63 -- et cette
#: compression n'est pas affine. `color-correction-affine-matrix-1` la traite avec deux
#: parametres par canal, donc elle paie l'ombre en deformant les hautes lumieres: sur la
#: capture HP a reglage actif, le blanc du treillis passe de 245,4 mesure (dE76 = 0,3 de
#: sa reference, deja juste) a 226 corrige (dE76 = 6,7). C'est la correction qui deforme,
#: pas le scan -- le motif meme d'`EPIC5-ARB-72`.
#:
#: **Les deux defauts du prototype explore pendant le diagnostic sont evites par
#: construction, pas corriges apres coup.** Le prototype etait une courbe isotone par
#: canal ajustee sur les 130 pastilles; mesure ici sur les trois captures reelles, il
#: laisse `lattice-068-068-068` a 35,7 dE76 sur `scan-WIN` -- un point d'ancrage direct --
#: et teinte l'axe neutre de 14,5 a 37,4 codes d'ecart entre canaux.
#:
#: * **confusion inter-canal (AC 3)**: la courbe ne voit que les valeurs neutres. Elle
#:   n'a donc jamais a mapper un meme code brut sur deux references differentes -- la
#:   contradiction qui degradait les neutres du prototype n'existe pas dans son jeu
#:   d'ajustement. La correction chromatique est portee par l'etage 2x2, qui lit le
#:   **triplet entier** et non un canal isole: deux pastilles qui partagent un code sur un
#:   seul canal y restent distinctes;
#: * **teinte de l'axe neutre (AC 6)**: les trois canaux partagent le meme axe de sortie
#:   -- `anchors_out` est **un** vecteur, pas trois --, donc chaque valeur neutre du jeu
#:   d'ajustement est envoyee **exactement** sur sa reference grise. C'est la premiere des
#:   deux options que l'AC 6 laisse ouvertes: « partager les memes ancrages en position
#:   entre les trois canaux ». L'etage de chroma, lui, est sans decalage: un triplet neutre
#:   a `(a*, b*) = (0, 0)` et une 2x2 sans decalage laisse l'origine invariante -- meme
#:   principe que les lignes de somme 1 de `fit_stage_m`, une propriete de la forme et non
#:   une precaution d'ecriture.
CORRECTION_FORM_TONE_CHROMA_ID = "color-correction-tone-curve-chroma-1"

#: La forme **active en production** (story 5.21, mandat `H9` option (a)): celle que la
#: commande `scan` demande quand personne ne nomme de forme.
#:
#: **Distincte de `CORRECTION_FORM_ID`, et c'est tout l'objet de cette constante.**
#: `CORRECTION_FORM_ID` reste l'identifiant de la forme affine et ne change ni de nom ni
#: de valeur: onze sites du module le lisent, et trois d'entre eux ne sont pas des
#: decisions de forme active mais des **cles de registre** ou l'**identite** d'une classe
#: de profil (`CORRECTION_FORMS`, `CORRECTION_FORM_EXCLUDES_INK_FLOOR`,
#: `CorrectionProfile.correction_id`). Y changer la valeur romprait la politique par
#: forme qu'`EPIC5-ARB-77` vient d'introduire -- la forme affine se declarerait courbe.
#:
#: Ce que la bascule achete, mesure pendant la revue de 5.20 (`H9`) sur les trois
#: captures reelles de `projects/chendj-mat/scans/`: la forme courbe+chroma est la
#: **seule** des trois a passer le budget de distorsion. Les deux autres degradent l'axe
#: neutre sur `12p5_test` -- +6,43 pour l'affine, +3,79 pour la Lab, contre un budget a
#: 2,5. 5.20 avait change ce qui est **juge** sans changer ce qui est **applique**;
#: cette constante est ce qui ferme l'ecart.
ACTIVE_CORRECTION_FORM_ID = CORRECTION_FORM_TONE_CHROMA_ID

#: Cardinal minimal d'ancrages de la courbe de tonalite. Deux points au moins: une
#: interpolation lineaire par morceaux sur un seul ancrage n'est pas une courbe, et
#: `np.interp` rendrait alors une **constante** -- toute la page ecrasee sur une clarte,
#: resultat plausible et donc non detecte, le meme faux succes que la matrice identite
#: fermee sur `fit_stage_m` le 2026-08-11.
MIN_NEUTRAL_TONE_ANCHORS = 2

#: Motifs de refus de la forme, **assertables par leur chaine** comme ceux de la forme
#: Lab. Les trois ferment trois faux succes distincts et non trois variantes du meme.
REFUSAL_TONE_NEEDS_TWO_NEUTRALS = "tone_curve_needs_two_neutral_anchors"
REFUSAL_TONE_ANCHORS_NOT_MONOTONE = "tone_curve_anchors_not_strictly_increasing"
REFUSAL_NEUTRAL_REFERENCE_NOT_GREY = "neutral_reference_is_not_grey"
REFUSAL_TONE_CHROMA_NEEDS_THREE_POINTS = "tone_chroma_needs_three_distinct_points"
REFUSAL_TONE_CHROMA_RANK_DEFICIENT = "tone_chroma_design_rank_deficient"

#: Le rapport entre la PLUS PETITE et la plus grande valeur singuliere en deca
#: duquel une conception de chroma est tenue pour deficiente.
#:
#: POURQUOI UN SEUIL NOMME plutot que le rang rendu par `lstsq`. Avec
#: `rcond=None`, numpy coupe a `max(M, N) * eps`, c'est-a-dire **exactement au
#: plancher de bruit** : le rang d'une conception colineaire y bascule d'une
#: compilation de BLAS a l'autre. Mesure du 2026-09-08 sur trois points
#: colineaires en Lab : le refus tombe ici (numpy 2.4.6, rapport 2,6e-17) et
#: **ne tombe pas** sur deux des trois jobs du runner GitHub -- meme code,
#: meme entree, `DID NOT RAISE`. Un refus produit qui depend de la machine
#: n'est pas un refus.
#:
#: LE SEUIL EST ENCADRE PAR DEUX MESURES, et l'ecart entre elles est de quinze
#: ordres de grandeur -- il n'y a donc rien d'arbitraire a choisir dedans :
#:
#:     trois points COLINEAIRES     rapport 2,6e-17
#:     trois chromas franches       rapport 2,8e-01
#:
#: 1e-10 laisse sept ordres de grandeur au-dessus du cas degenere et neuf
#: en-dessous du cas sain. Ce qui change de comportement est la bande
#: intermediaire, ou l'ajustement de chroma n'a de toute facon aucun sens
#: numerique : l'y refuser est ce que le refus existe pour faire -- eviter le
#: faux succes d'une page ramenee sur un seul axe.
SEUIL_DE_RANG_DE_LA_CHROMA = 1e-10


def _est_de_rang_deficient(singular) -> bool:
    """Une conception de chroma ne determine-t-elle qu'une droite (ou un point) ?

    Lit les valeurs singulieres plutot que le rang : c'est la meme information,
    mais le seuil est ALORS le notre, donc il ne bouge pas d'une machine a
    l'autre. Une conception sans aucune valeur singuliere, ou dont la plus
    grande est nulle, est deficiente par construction.
    """
    return _rapport_singulier(singular) <= SEUIL_DE_RANG_DE_LA_CHROMA


def _rapport_singulier(singular) -> float:
    """La plus petite valeur singuliere rapportee a la plus grande.

    Rend `0.0` quand la conception n'a pas deux valeurs singulieres, ou que la
    plus grande est nulle : les deux cas sont deficients par construction, et
    `0.0` les fait tomber sous n'importe quel seuil strictement positif -- une
    seule sortie plutot que deux, et le message de refus a un nombre a citer.
    """
    valeurs = np.asarray(singular, dtype=np.float64).ravel()
    if valeurs.size < 2 or not valeurs[0] > 0.0:
        return 0.0
    return float(valeurs[-1] / valeurs[0])

#: Ecart maximal admis entre canaux, en codes 8 bits, sur une valeur **neutre en
#: reference** apres correction. AC 6 de la story 5.20, `EPIC5-ARB-75`.
#:
#: **Derive et non pose.** Distribution nulle mesuree le 2026-08-13: la correction
#: `color-correction-tone-curve-chroma-1` ajustee sur une capture et jugee sur l'autre
#: capture de la **meme feuille physique** (`rush-bitch-4-scan2` et `scan-WIN`, deux
#: logiciels a correction desactivee, dont le sprint change proposal etablit qu'ils
#: coincident a -1,1/+0,2 code pres) laisse au pire **0,54 code** d'ecart entre canaux,
#: sur les deux sens de transport. Le seuil retenu est **2,78 fois** ce pire cas nul,
#: exactement le rapport qu'`EPIC5-ARB-57` a retenu pour le seuil de divergence.
#:
#: Ce qu'il encadre de l'autre cote, mesure sur les memes donnees: le scan brut porte
#: deja 2,0 a 3,0 codes d'ecart entre canaux sur ses propres neutres -- c'est le
#: plancher physique --, la forme Lab en laisse 3,9 a 4,4, et le prototype du diagnostic
#: 14,5 a 37,4. Le seuil est donc **sous** le bruit propre du scanner, ce qui n'est
#: tenable que parce que la forme retenue annule cet ecart par construction et non par
#: ajustement.
NEUTRAL_AXIS_MAX_CHANNEL_SPREAD_8BIT = 1.5


def neutral_tone_anchors(measured_linear, reference_linear, neutral_mask):
    """Ancrages de la courbe de tonalite. Rend `(entrees (K, 3), sorties (K,))`.

    **Un seul vecteur de sorties pour les trois canaux**, et c'est tout l'objet de la
    fonction: c'est ce qui rend l'axe neutre invariant par construction. La sortie d'un
    ancrage est la clarte de reference de la valeur neutre, identique sur ses trois
    canaux par definition d'un gris -- et cette definition est **verifiee** plutot que
    supposee, faute de quoi un appelant qui marquerait `neutral` une valeur coloree
    ferait de l'invariance de l'axe neutre une declaration fausse.

    Deux ancrages synthetiques encadrent les mesures, `0 -> 0` et `1 -> 1`, et ils ne
    sont pas decoratifs: `np.interp` **plafonne** hors de son domaine. Sans le bas, tout
    ce qui est plus sombre que le neutre le plus sombre ressortirait a la clarte de ce
    neutre -- avec l'exclusion du plancher d'encrage (AC 7), cela voudrait dire tout
    ecraser sur le niveau 68. Sans le haut, le papier nu ressortirait a 245.
    """
    measured = np.atleast_2d(np.asarray(measured_linear, dtype=np.float64))
    reference = np.atleast_2d(np.asarray(reference_linear, dtype=np.float64))
    mask = np.asarray(neutral_mask, dtype=bool)
    if measured.shape != reference.shape or measured.shape[-1] != 3:
        raise ValueError(
            f"formes incompatibles: {measured.shape} contre {reference.shape}, "
            "trois canaux attendus.")

    grey = reference[mask]
    if grey.size and not np.allclose(grey, grey[:, :1], rtol=0.0, atol=1e-12):
        raise UnderdeterminedAdjustmentSet(
            REFUSAL_NEUTRAL_REFERENCE_NOT_GREY,
            f"'{CORRECTION_FORM_TONE_CHROMA_ID}' ancre les trois canaux sur une seule "
            "clarte par valeur neutre, donc une valeur marquee neutre dont la reference "
            "n'est pas grise rendrait cet ancrage ambigu -- et l'invariance de l'axe "
            "neutre, qui est la propriete de cette forme, deviendrait une declaration "
            "fausse au lieu d'une garantie.")

    levels = grey[:, 0]
    # Tri **stable**: deux valeurs neutres de meme clarte de reference gardent leur ordre
    # d'entree, donc deux executions sur les memes donnees rendent les memes ancrages.
    # Le cas est refuse quelques lignes plus bas -- des sorties egales ne sont pas
    # strictement croissantes -- mais il doit l'etre pour ce motif-la et non parce que le
    # tri a choisi une permutation au hasard.
    order = np.argsort(levels, kind="stable")
    anchors_in = measured[mask][order]
    anchors_out = levels[order]
    if len(anchors_out) < MIN_NEUTRAL_TONE_ANCHORS:
        raise UnderdeterminedAdjustmentSet(
            REFUSAL_TONE_NEEDS_TWO_NEUTRALS,
            f"la courbe de tonalite de '{CORRECTION_FORM_TONE_CHROMA_ID}' exige "
            f"{MIN_NEUTRAL_TONE_ANCHORS} valeurs d'axe neutre, {len(anchors_out)} "
            "trouvee(s). Sur un ancrage unique, `np.interp` rend une constante: toute "
            "la page ecrasee sur une clarte, resultat plausible et donc non detecte.")

    # Les bornes synthetiques ne sont posees que si elles etendent reellement le
    # domaine: un ancrage mesure exactement a 0 ou a 1 les rendrait dupliquees, donc
    # non strictement croissantes, donc refusees par la garde suivante -- pour une
    # raison qui n'a rien a voir avec le defaut qu'elle cherche.
    if anchors_in.min() > 0.0 and anchors_out[0] > 0.0:
        anchors_in = np.vstack([np.zeros((1, 3), dtype=np.float64), anchors_in])
        anchors_out = np.concatenate([[0.0], anchors_out])
    if anchors_in.max() < 1.0 and anchors_out[-1] < 1.0:
        anchors_in = np.vstack([anchors_in, np.ones((1, 3), dtype=np.float64)])
        anchors_out = np.concatenate([anchors_out, [1.0]])

    # **Stricte** croissance, sur les entrees comme sur les sorties. `np.interp` ne leve
    # pas sur un `xp` non croissant: il rend des valeurs silencieusement fausses. Et le
    # cas n'est pas theorique -- c'est exactement le regime du plancher d'encrage, ou
    # deux references distinctes se lisent a la meme valeur, la contradiction que
    # `ensure_no_ink_floor_value_in_adjustment_set` retire du jeu.
    if not (np.all(np.diff(anchors_in, axis=0) > 0.0)
            and np.all(np.diff(anchors_out) > 0.0)):
        raise UnderdeterminedAdjustmentSet(
            REFUSAL_TONE_ANCHORS_NOT_MONOTONE,
            f"les ancrages de '{CORRECTION_FORM_TONE_CHROMA_ID}' ne sont pas "
            "strictement croissants sur les trois canaux. Deux references neutres "
            "distinctes lues a la meme valeur -- le regime du plancher d'encrage -- "
            "demandent de mapper une meme mesure sur deux clartes: `np.interp` ne leve "
            "pas dessus, il rend des valeurs fausses sans le dire.")
    return anchors_in, anchors_out


def apply_tone_curve(anchors_in, anchors_out, linear):
    """Interpoler la courbe de tonalite, canal par canal, sur les memes sorties.

    La boucle est sur les **canaux** et non sur les pixels: `np.interp` ne prend qu'un
    `xp` a la fois, et les trois `xp` different -- c'est ce qui corrige la dominante du
    scanner. Ce qui ne differe pas, et qui porte la garantie, c'est `fp`.
    """
    values = np.asarray(linear, dtype=np.float64)
    entries = np.asarray(anchors_in, dtype=np.float64)
    exits = np.asarray(anchors_out, dtype=np.float64)
    # Le cardinal de canaux est **refuse** et non suppose (finding de revue de 5.20,
    # ferme le 2026-08-19). La boucle parcourt `range(3)` et la sortie vient de
    # `np.empty_like`: un tableau BGRA ressortait avec son quatrieme canal jamais ecrit,
    # c'est-a-dire une sortie non deterministe que rien ne signale -- l'alpha perdu, et
    # un resultat plausible. `neutral_tone_anchors` refuse deja une forme qui n'a pas
    # trois canaux a l'ajustement; l'application le refuse desormais aussi.
    if values.ndim == 0 or values.shape[-1] != 3:
        raise ValueError(
            f"'{CORRECTION_FORM_TONE_CHROMA_ID}' applique sa courbe canal par canal sur "
            f"trois canaux BGR, tableau de forme {values.shape} recu. Un quatrieme "
            "canal ressortirait non initialise et la sortie serait plausible.")
    corrected = np.empty_like(values)
    for channel in range(3):
        corrected[..., channel] = np.interp(
            values[..., channel], entries[:, channel], exits)
    return corrected


def fit_tone_chroma(after_tone_linear, reference_linear):
    """Etage de chroma: une 2x2 **sans decalage** sur `(a*, b*)`. Rend la matrice.

    Sans decalage, et c'est la moitie de l'invariance de l'axe neutre: un triplet neutre
    a `(a*, b*) = (0, 0)`, et une application lineaire laisse l'origine ou elle est. Un
    decalage -- celui que porte `fit_lab_chroma` de la forme Lab -- colorerait tout gris
    de la meme quantite, ce qui est precisement le defaut que l'AC 6 refuse.

    `L*` n'est **jamais** touche: la courbe de tonalite l'a deja fixe, et un second
    etage qui y reviendrait defrait sur l'axe neutre ce que le premier vient d'y poser.
    C'est la meme orthogonalite que celle de la forme Lab, et c'est aussi la raison
    mesuree pour laquelle un etage matriciel 3x3 residuel **n'est pas** retenu ici: teste
    le 2026-08-13 sur les trois captures, `fit_stage_m` apres la courbe fait passer la
    pire degradation par pastille de +18,1 a +29,7 dE76 sur `rush-bitch-4-scan2`.
    """
    source = lab_from_linear_bgr(np.atleast_2d(
        np.asarray(after_tone_linear, dtype=np.float64)))
    target = lab_from_linear_bgr(np.atleast_2d(
        np.asarray(reference_linear, dtype=np.float64)))
    design = source[:, 1:3]
    solved, _residuals, _rank, singular = np.linalg.lstsq(
        design, target[:, 1:3], rcond=None)
    if _est_de_rang_deficient(singular):
        # Un jeu qui ne porte que des neutres a une chroma mesuree quasi nulle: la
        # conception est de rang 1 ou 0, et `lstsq` rend alors la solution de norme
        # minimale -- une matrice **nulle**, qui envoie toute couleur sur l'axe neutre.
        # Une page entierement desaturee est parfaitement plausible a l'oeil d'un
        # controle automatique: c'est le faux succes, pas l'erreur.
        raise UnderdeterminedAdjustmentSet(
            REFUSAL_TONE_CHROMA_RANK_DEFICIENT,
            f"la 2x2 de chroma de '{CORRECTION_FORM_TONE_CHROMA_ID}' est ajustee sur "
            f"une conception dont les valeurs singulieres sont dans un rapport de "
            f"{_rapport_singulier(singular):.2e}, sous le seuil de "
            f"{SEUIL_DE_RANG_DE_LA_CHROMA:.0e} : elle ne determine qu'une droite. "
            "A ce rang `lstsq` rend la "
            "matrice nulle, c'est-a-dire une correction qui desature toute la page sans "
            "le dire.")
    return np.asarray(solved.T, dtype=np.float64)


@dataclass(frozen=True)
class ToneCurveCorrectionProfile:
    """Le profil d'une page sous `color-correction-tone-curve-chroma-1`.

    Deux etages orthogonaux, comme la forme Lab, mais le premier est une **courbe** et
    non une affine: c'est ce qui lui permet de suivre une compression tonale que deux
    parametres par canal ne peuvent pas suivre.

    `tone_anchors_out` est de rang 1 -- **un** vecteur pour les trois canaux -- et c'est
    la forme executable de la garantie de l'AC 6. Un lecteur qui verrait trois vecteurs
    ici saurait immediatement que la garantie est perdue.
    """

    tone_anchors_in: np.ndarray
    tone_anchors_out: np.ndarray
    chroma_matrix: np.ndarray
    correction_id: str = CORRECTION_FORM_TONE_CHROMA_ID

    def apply_linear(self, linear):
        """Lumiere lineaire BGR -> lumiere lineaire BGR: courbe, puis chroma."""
        toned = apply_tone_curve(self.tone_anchors_in, self.tone_anchors_out, linear)
        values = lab_from_linear_bgr(toned)
        corrected = np.empty_like(values)
        corrected[..., 0] = values[..., 0]
        corrected[..., 1:3] = values[..., 1:3] @ np.asarray(self.chroma_matrix).T
        return linear_bgr_from_lab(corrected)


def fit_correction_tone_chroma(measured_bgr, reference_bgr,
                               neutral_mask) -> ToneCurveCorrectionProfile:
    """Ajuster la forme courbe+chroma. Entrees en sRGB encode, ordre **BGR**.

    Meme signature que `fit_correction` et `fit_correction_lab`, au mot pres: c'est ce
    qui permet au registre de resoudre les trois formes par identifiant sans qu'aucun
    appelant ne se ramifie.

    L'ordre des deux ajustements n'est pas commutatif et il est celui de l'application:
    la chroma s'ajuste **apres** la courbe, sur les valeurs que la courbe a deja
    deplacees. L'ajuster sur les mesures brutes lui ferait corriger une chroma que la
    courbe va ensuite modifier.
    """
    mask = np.asarray(neutral_mask, dtype=bool)
    measured_linear = eotf(measured_bgr)
    reference_linear = eotf(reference_bgr)
    anchors_in, anchors_out = neutral_tone_anchors(
        measured_linear, reference_linear, mask)
    # Cardinal de chroma, **lu sur la reference** et avant tout ajustement. Le rang de
    # la conception ne suffit pas ici, et la mesure le montre: apres la courbe, un jeu
    # entierement neutre a une chroma de l'ordre de 1e-5 -- non pas zero, parce que les
    # coefficients publies de `SRGB_TO_XYZ_D65_BGR` sont arrondis a la septieme decimale
    # et que leurs lignes ne somment donc pas exactement au blanc D65. `lstsq` y voit
    # deux valeurs singulieres du meme ordre, donc **rang 2**, et rend une matrice
    # ajustee sur du bruit d'arrondi. La regle de cardinal, elle, est exacte et
    # deterministe -- c'est la meme que celle de la forme Lab, avec sa constante.
    distinct = distinct_chroma_point_count(
        lab_from_linear_bgr(np.atleast_2d(reference_linear)), mask)
    if distinct < MIN_DISTINCT_CHROMA_POINTS:
        raise UnderdeterminedAdjustmentSet(
            REFUSAL_TONE_CHROMA_NEEDS_THREE_POINTS,
            f"la 2x2 de chroma de '{CORRECTION_FORM_TONE_CHROMA_ID}' exige "
            f"{MIN_DISTINCT_CHROMA_POINTS} points de chroma de reference distincts, "
            f"{distinct} trouve(s) (les neutres comptent pour un seul point, leur "
            "chroma cible etant nulle). Un jeu sans couleur ferait ajuster la matrice "
            "sur le bruit d'arrondi de la matrice XYZ, ce qui rend une correction "
            "arbitraire et non un refus.")
    after_tone = apply_tone_curve(anchors_in, anchors_out, measured_linear)
    chroma = fit_tone_chroma(after_tone, reference_linear)
    return ToneCurveCorrectionProfile(
        tone_anchors_in=anchors_in, tone_anchors_out=anchors_out,
        chroma_matrix=chroma)


def neutral_axis_channel_spread_8bit(corrected_bgr, neutral_mask) -> float:
    """Pire ecart **entre canaux**, en codes 8 bits, sur les valeurs neutres corrigees.

    La statistique de l'AC 6 de la story 5.20, et elle est ecrite ici parce que la
    moyenne BGR -- la seule qui ait ete rapportee pendant tout le diagnostic du
    2026-08-13 -- **masque exactement le defaut cherche**: un gris dont le rouge manque
    de 28 codes et dont le vert et le bleu sont justes a une moyenne presque correcte, et
    se lit pourtant comme un virage franc vers le bleu-vert. C'est Egan qui a releve le
    defaut a l'oeil sur la page de comparaison, apres des dizaines de mesures moyennees
    qui ne le voyaient pas.

    L'ecart se lit a la moyenne des trois canaux de **chaque** valeur, pas a l'ecart
    entre le maximum et le minimum: la moyenne est le gris que la valeur devrait etre, et
    l'ecart a cette moyenne dit de combien chaque canal s'en eloigne, ce qui est la
    grandeur que l'oeil lit. Rend `0.0` quand aucune valeur n'est neutre -- il n'y a alors
    rien a mesurer, et ce n'est pas un verdict de non-teinte: l'appelant qui juge un jeu
    sans neutre juge un jeu qui n'a pas d'axe neutre.

    **`evaluate_acceptance` ne publie donc pas ce `0.0` tel quel** (`EPIC5-ARB-78`): il
    verifie d'abord qu'il existe une valeur neutre et publie `None` sinon. La difference
    compte a l'endroit ou la valeur devient un document: zero est la lecture d'un axe
    neutre **parfait**, et l'ecrire la ou rien n'a ete lu serait le faux succes que ce
    module ferme partout ailleurs. Ici, ou la valeur est un nombre rendu a un appelant qui
    connait son masque, `0.0` reste la reponse juste et evite un `float | None` a chaque
    site de calcul.
    """
    corrected = np.atleast_2d(np.asarray(corrected_bgr, dtype=np.float64))
    mask = np.asarray(neutral_mask, dtype=bool)
    if not mask.any():
        return 0.0
    greys = corrected[mask] * 255.0
    return float(np.abs(greys - greys.mean(axis=1, keepdims=True)).max())


class UnknownCorrectionFormError(ValueError):
    """`correction_form_id` absent du registre. Jamais un repli sur la forme active.

    Un repli serait pire qu'un echec: le manifest porterait l'identifiant demande et le
    resultat viendrait d'une autre forme, donc deux corrections differentes seraient
    indistinguables a posteriori -- exactement ce que l'AC 10 existe pour empecher.
    """


#: Registre des **formes** de correction, une entree par identifiant.
#:
#: **Ses cles sont des identifiants de forme, jamais « la forme active »** -- la cle
#: `CORRECTION_FORM_ID` designe la forme affine et rien d'autre. La story 5.16 avait
#: adosse ici une seconde phrase, aujourd'hui perimee: la forme affine y etait dite
#: « le defaut de `calibrate_page` », ce qui etait vrai jusqu'a la story 5.21 et ne l'est
#: plus -- le defaut de production est desormais `ACTIVE_CORRECTION_FORM_ID`. Ce que
#: l'AC 1 de 5.16 exigeait (jeux de test inchanges au bit pres) portait sur
#: `fit_correction` et sur l'ajout d'une forme *a cote* de l'autre; le choix de la forme
#: demandee quand personne n'en nomme est une decision de production, tranchee par `H9`
#: sur mesure et non par ce registre.
CORRECTION_FORMS: "MappingProxyType[str, object]" = MappingProxyType({
    CORRECTION_FORM_ID: fit_correction,
    CORRECTION_FORM_LAB_ID: fit_correction_lab,
    CORRECTION_FORM_TONE_CHROMA_ID: fit_correction_tone_chroma,
})


def get_correction_form(correction_form_id: str):
    """Resoudre l'ajusteur d'une forme, ou echouer explicitement."""
    try:
        return CORRECTION_FORMS[correction_form_id]
    except (KeyError, TypeError):
        raise UnknownCorrectionFormError(
            f"Forme de correction inconnue: '{correction_form_id}'. Formes connues: "
            f"{', '.join(CORRECTION_FORMS)}. Une forme devinee rendrait le manifest "
            "menteur sur ce qui a ete applique."
        ) from None


# ---------------------------------------------------------------------------
# EPIC5-ARB-31 clause 2, absorbee par le budget de distorsion d'EPIC5-ARB-73
# ---------------------------------------------------------------------------
#
# **Depuis la story 5.20, la garde de non-degradation n'est plus un mecanisme distinct**
# (`EPIC5-ARB-74`): elle **est** la clause de moyenne de `color-distortion-budget-1`,
# plafond a zero, et son motif d'echec garde son nom (`correction_degrades_residual`).
# La tolerance numerique ci-dessous n'a pas bouge et vaut toujours pour la meme raison.
# Ce qui a change est ce qui **s'ajoute** a elle: les seuils absolus de
# `color-acceptance-1` ne commandent plus le statut, une seconde clause le fait -- la
# degradation maximale de l'axe neutre.

#: Les deux motifs d'echec de la metrique et la tolerance numerique de la garde de
#: non-degradation sont **definis dans `color_metrics`** et importes plus haut: c'est la
#: que la decision se prend, donc la que le vocabulaire vit. Rappel de ce que la
#: tolerance est et n'est pas, parce que c'est le point qu'une relecture rate:
#: `EPIC5-ARB-31` clause 2 dit « si `mean_delta_e` apres correction **excede**
#: `mean_delta_e` avant correction, la page est `failed` », et lue au pied de la lettre
#: en flottant cette clause fait echouer une page **parfaite** -- les deux agregats
#: valent conceptuellement 0, l'ajustement laisse un residu de l'ordre de 1e-14, et
#: `1e-14 > 0` est vrai. La tolerance est donc **numerique** et bornee au bruit de
#: calcul; une tolerance perceptuelle serait une revision de la clause, donc une
#: nouvelle entree d'arbitrage.
#:
#: **L'ecretage n'est pas un motif d'echec et ne le sera jamais** (`EPIC5-ARB-16`): un
#: ecretage revele par les sentinelles est une limite physique de l'imprimante, et l'y
#: mettre jetterait des planches exploitables.


@dataclass(frozen=True)
class AcceptanceVerdict:
    """Verdict d'acceptation d'une page, avec ce qui l'a produit.

    `mean_delta_e` et `max_delta_e` sont rapportes **a cote** du statut et non
    seulement resumes par lui: le 2026-08-10 a montre qu'un verdict binaire pose sur
    une grandeur qui vit au voisinage de son seuil bascule sur du bruit, et qu'un
    lecteur doit pouvoir voir qu'un cas est limite.
    """

    status: str
    mean_delta_e: float
    max_delta_e: float
    mean_delta_e_before: float
    acceptance_id: str
    failure_reason: str | None = None
    #: Ce que le **budget de distorsion** a mesure. Il a commande `status` le temps d'un
    #: arbitrage (`EPIC5-ARB-72`, story 5.20) et ne le commande plus depuis
    #: `EPIC5-ARB-78`: les trois grandeurs ci-dessous sont **informatives**, au meme titre
    #: que les deux agregats absolus au-dessus. Elles restent portees ici parce que c'est
    #: ce qui les fait voyager jusqu'au manifest -- une mesure qu'on ne publie pas est une
    #: mesure qu'on ne fait pas.
    distortion_budget_id: str = ""
    mean_degradation_de76: float = 0.0
    max_neutral_degradation_de76: float | None = None
    #: La plus grande degradation isolee, toutes pastilles confondues (`EPIC5-ARB-78`),
    #: et le booleen qui dit si les deux clauses du budget etaient tenues. Jamais un
    #: plafond: Egan a explicitement refuse d'en poser un (« je ne sais pas comment poser
    #: une valeur dessus »), et ce qui est publie est la mesure, pas un verdict.
    #:
    #: **Defauts `None`, pas `0.0`/`True`** (deuxieme passe de revue, `EPIC5-ARB-78`,
    #: 2026-08-14), meme correctif et meme motif que sur `PageAcceptanceResult` dans
    #: `color_metrics.py`, dont ces deux champs sont recopies: `evaluate_acceptance` les
    #: transmet toujours calcules, donc ces defauts ne sont jamais lus en production,
    #: mais `0.0`/`True` sont les lectures les plus flatteuses possibles la ou rien
    #: n'aurait ete mesure -- exactement ce que `neutral_axis_channel_spread_8bit`
    #: evite deja pour son propre champ.
    max_degradation_de76: float | None = None
    distortion_budget_met: bool | None = None
    #: L'ecart entre canaux sur l'axe neutre **corrige**, en codes 8 bits: la statistique
    #: de l'AC 6 de la story 5.20, celle qu'Egan a reperee a l'oeil sur la page de
    #: comparaison ("la teinte (verte?) et la temperature de couleur des blancs qui vire
    #: au bleu"). Elle etait ecrite depuis 5.20 et **n'avait aucun appelant** -- finding de
    #: sa revue --, ce qu'`EPIC5-ARB-78` corrige en la calculant systematiquement et en la
    #: publiant, jamais en l'opposant a un seuil. `None` quand le jeu ne porte aucune
    #: valeur de reference grise: il n'y a alors pas d'axe neutre a mesurer, et publier
    #: `0.0` serait affirmer l'absence de teinte la ou rien n'a ete lu.
    neutral_axis_channel_spread_8bit: float | None = None
    #: Le resultat complet de la signature d'`EPIC5-ARB-28`, porte tel quel: c'est lui
    #: qui contient `worst_value_id`, `per_value` et `sample_count`, donc ce qui rend
    #: une metrique relisable apres coup. Le verdict ci-dessus n'en est que la partie
    #: dont l'orchestration a besoin pour trancher un statut.
    detail: PageAcceptanceResult | None = None


def evaluate_acceptance(measured_raw_bgr, corrected_bgr, reference_bgr,
                        acceptance_id: str = ACTIVE_COLOR_ACCEPTANCE_ID,
                        *, value_ids: tuple[str, ...] | None = None,
                        values_version: str = "",
                        distortion_budget_id: str = ACTIVE_DISTORTION_BUDGET_ID
                        ) -> AcceptanceVerdict:
    """Mesurer une page et rendre son verdict. `EPIC5-ARB-28`, `-72` et `-78`.

    **Depuis `EPIC5-ARB-78` (2026-08-13), aucun seuil de couleur ne rend plus `failed`
    ici**, et c'est le second et dernier changement de sens de cette fonction. Elle
    calcule et publie quatre familles de grandeurs, dont aucune n'est opposee a un
    plafond:

    * les deux agregats absolus de `color-acceptance-1` -- a quelle distance du theorique
      la page se trouve. Ils ont cesse de commander le statut a `EPIC5-ARB-72`: le scan
      Windows du 2026-08-13 affiche 15,42 dE76 de moyenne **sans aucune correction**, et
      le tirage qui a valide la methode le 2026-08-11 en affiche 11,66;
    * la degradation **moyenne** par pastille (`EPIC5-ARB-31` clause 2, absorbee par
      `EPIC5-ARB-74`) et la degradation **maximale sur l'axe neutre** (`EPIC5-ARB-75`).
      Elles ont commande le statut le temps d'une journee et ne le commandent plus:
      Egan ne peut juger ni l'une ni l'autre en dE76, et la seconde s'est revele avoir
      une marge de 0,04 code sur `12p5_test`. Leur verdict reste publie, en clair, par
      `distortion_budget_met`;
    * la plus grande degradation **isolee** toutes pastilles confondues, qui n'a jamais
      eu de plafond;
    * l'ecart entre canaux de l'axe neutre **corrige**, en codes 8 bits -- la statistique
      de l'AC 6, calculee ici et nulle part ailleurs sur le chemin de production.

    **Ce qui rend encore `failed` est ailleurs et d'une autre nature**: les echecs de
    calcul du vocabulaire ferme de l'AC 8 de 5.4b (page illisible, patchs introuvables,
    jeu sous-determine, dpi invalide, page hors trois canaux), leves par les fonctions qui
    lisent la page ou ajustent la correction. Le statut rendu ici vaut donc toujours
    `applied` -- ce qui n'est pas un raccourci d'implementation mais la decision
    d'`EPIC5-ARB-78` mot pour mot: « on ne bloque rien a cause d'un seuil etc. On
    informe. »

    **Adaptateur depuis le 2026-08-11**: le calcul vit dans
    `color_metrics.evaluate_page_acceptance`, la signature nommee par `EPIC5-ARB-28`.
    Cette fonction ne fait plus que deux choses, et ce sont les deux qui appartiennent a
    l'orchestration d'une page: fabriquer les identifiants quand l'appelant n'en a pas
    (les tests d'unite travaillent sur des tableaux nus) et traduire `passed` en statut
    `applied` / `failed`, mot du vocabulaire de l'AC 8 de 5.4b et non de la metrique.
    """
    measured_raw = np.atleast_2d(np.asarray(measured_raw_bgr, dtype=np.float64))
    corrected = np.atleast_2d(np.asarray(corrected_bgr, dtype=np.float64))
    reference = np.atleast_2d(np.asarray(reference_bgr, dtype=np.float64))
    if value_ids is None:
        # Identifiants positionnels, sur une largeur fixe pour que l'ordre
        # lexicographique de la metrique coincide avec l'ordre d'entree -- sans quoi
        # `per_value` melangerait 10 et 2.
        value_ids = tuple(f"row-{index:04d}" for index in range(len(corrected)))
    if not (len(value_ids) == len(corrected) == len(reference) == len(measured_raw)):
        raise ColorMetricError(
            f"cardinalites incoherentes: {len(value_ids)} identifiants, "
            f"{len(corrected)} mesures corrigees, {len(reference)} references, "
            f"{len(measured_raw)} mesures brutes")
    # **L'unicite des identifiants se verifie ici, avant la conversion en mapping**
    # (deuxieme passe de revue, `EPIC5-ARB-78`, 2026-08-14): `{key: tuple(row) for key,
    # row in zip(value_ids, corrected)}` ecrase silencieusement une ligne des qu'un
    # identifiant se repete -- la construction du dict ne garde que la derniere valeur du
    # doublon, et l'information de perte disparait avant meme d'atteindre `_validated`
    # dans `color_metrics`, qui ne voit plus qu'un mapping deja ampute. Reproduit: un jeu
    # avec un `value_id` duplique publiait `neutral_sample_count=1` a cote d'un
    # `neutral_axis_channel_spread_8bit` mesure sur l'autre ligne du meme id -- une ligne
    # disparait sans refus, ce qui est exactement le risque que la regle des fabriques de
    # ce depot (CLAUDE.md) documente sous une autre forme.
    if len(set(value_ids)) != len(value_ids):
        vus: set[str] = set()
        doublons = sorted({value_id for value_id in value_ids
                           if value_id in vus or vus.add(value_id)})
        raise ColorMetricError(
            f"value_ids porte des identifiants dupliques: "
            f"{', '.join(doublons[:5])}{'...' if len(doublons) > 5 else ''}. Une cle "
            "repetee ecraserait silencieusement une ligne du mapping value_id -> "
            "triplet, et toute statistique derivee (dont l'axe neutre) se calculerait "
            "sur un jeu ampute d'une valeur sans qu'aucun refus ne le dise.")

    result = evaluate_page_acceptance(
        measured={key: tuple(row) for key, row in zip(value_ids, corrected)},
        reference={key: tuple(row) for key, row in zip(value_ids, reference)},
        measured_raw={key: tuple(row) for key, row in zip(value_ids, measured_raw)},
        values_version=values_version,
        acceptance_id=acceptance_id,
        distortion_budget_id=distortion_budget_id,
    )
    # L'axe neutre se lit **sur la meme definition que le budget** -- l'egalite exacte des
    # trois canaux de la reference (`color_metrics.is_grey_reference`) -- et non sur un
    # masque que l'appelant fournirait. Deux derivations de « neutre » sur le meme chemin
    # seraient deux verites, et c'est la statistique de l'AC 6 qui jugerait alors une
    # famille qui n'est pas celle qu'elle nomme.
    grey = np.asarray([is_grey_reference(row) for row in reference], dtype=bool)
    spread = float(neutral_axis_channel_spread_8bit(corrected, grey)) if grey.any() \
        else None
    return AcceptanceVerdict(
        # Litteral et non derive de `result.passed` (deuxieme passe de revue,
        # `EPIC5-ARB-78`, 2026-08-14): `result.passed` est desormais **toujours** `True`
        # depuis la meme story (`evaluate_page_acceptance` ne refuse plus rien), donc le
        # ternaire etait mort -- sa branche `else "failed"` n'a plus de domaine
        # d'activation. `color_metrics` a deja ecrit son propre litteral pour ce meme
        # piege, documente le 2026-08-12: aligner sur la meme forme plutot que de
        # laisser un ternaire dont une branche ne se reverra jamais.
        status="applied",
        mean_delta_e=result.mean_delta_e,
        max_delta_e=result.max_delta_e,
        mean_delta_e_before=result.mean_delta_e_before_correction,
        acceptance_id=result.acceptance_id,
        failure_reason=result.failure_reason,
        detail=result,
        distortion_budget_id=result.distortion_budget_id,
        mean_degradation_de76=result.mean_degradation_de76,
        max_neutral_degradation_de76=result.max_neutral_degradation_de76,
        max_degradation_de76=result.max_degradation_de76,
        distortion_budget_met=result.distortion_budget_met,
        neutral_axis_channel_spread_8bit=spread,
    )


# ---------------------------------------------------------------------------
# AC 2, 3, 8 et 9 : orchestration par page
# ---------------------------------------------------------------------------

#: Vocabulaire ferme des motifs d'echec (AC 8). Chacun laisse passer l'image **non
#: corrigee**, jamais a demi corrigee: « ce qui n'a pas ete corrige est declare non
#: corrige ». L'ecretage n'y est pas et n'y sera jamais (`EPIC5-ARB-16`).
FAILURE_PATCHES_NOT_FOUND = "patches_not_found"
FAILURE_PATCHES_OUT_OF_RANGE = "patches_out_of_plausible_range"
FAILURE_REPLICATE_DISPERSION = "replicate_dispersion_too_high"
FAILURE_UNKNOWN_PATCH_PRESET = "unknown_patch_preset"
FAILURE_UNKNOWN_VALUES_VERSION = "unknown_patch_values_version"
FAILURE_UNKNOWN_GAMUT_MAP = "unknown_gamut_map"

#: Aucun placement de pastilles n'est defini pour le couple (template, preset) declare
#: par le QR. Ajoute le 2026-08-11 sur un finding majeur de la couche 2: la resolution
#: du placement levait `UndefinedPlacementError` **hors** du vocabulaire de l'AC 8, donc
#: une exception traversait `calibrate_page` la ou toutes les autres causes rendent un
#: `PageCalibration` motive. Le cas devient courant avec le versionnement de la
#: geometrie de page: un `template_id` d'une version non encore placee tombe ici.
FAILURE_PLACEMENT_UNDEFINED = "patch_placement_undefined"

#: Le jeu d'ajustement de la page ne suffit pas a determiner la correction: moins de
#: deux valeurs d'axe neutre pour l'etage `A`, ou moins de deux valeurs informatives
#: pour l'etage `M`. `EPIC5-ARB-29` clause 5 demande un verdict explicite pour ce cas;
#: il remontait en `ValueError` nue, donc hors du vocabulaire de l'AC 8 (couches 1 et 3).
FAILURE_UNDERDETERMINED_ADJUSTMENT = "adjustment_set_underdetermined"

#: `dpi` invalide. Il etait accepte a `600.5` comme a `-1` (finding mineur de la
#: couche 2): un dpi non entier decale chaque conversion en pixels d'une fraction, donc
#: le carre echantillonne, **sans lever d'erreur**.
FAILURE_INVALID_DPI = "invalid_dpi"

#: La page redressee ne porte pas trois canaux. **Ajoute a la passe de correction de
#: 5.19** (bloquant B3 de la couche 1), et le motif n'est pas theorique: un scan en
#: niveaux de gris est une entree **licite** de la chaine -- `color_pipeline
#: .validate_bgr_input`, par laquelle toute page passe a l'ingestion, accepte
#: explicitement `ndim == 2` et les cardinaux 1, 3 et 4 --, et ses frames etaient ecrites
#: non corrigees avant que 5.19 n'envoie la page de calibration a `sample_patches`. Le
#: declencheur est un reglage a un clic sur n'importe quel scanner a plat.
#:
#: **Le plantage n'etait pas le pire.** `sample_patches` fait `window.reshape(-1, 3)`:
#: que ce reshape leve ou non ne depend que d'une arithmetique. Sur un scan a canal alpha
#: il **reussit** des que l'aire du carre echantillonne multipliee par 4 est divisible
#: par 3, et rend alors des triplets qui melangent les canaux -- mesure a l'unite sur une
#: page BGRA uniforme `(10, 120, 240, 255)` a 200 ppp: `[0.613, 0.613, 0.613]` au lieu de
#: `[0.039, 0.471, 0.941]`, un gris parfaitement plausible a la place d'un rouge sature.
#: Une correction de lot ajustee sur des mesures de cette nature serait plausible,
#: disponible, declaree `applied` et appliquee aux pixels de **toutes** les planches du
#: lot. Le refus qu'une pastille plus loin finissait par produire etait un accident
#: d'arithmetique, pas une garde.
#:
#: La garde est donc posee **avant** l'echantillonnage, et non par un `except ValueError`
#: autour: un `except` couvrirait aussi les vraies pannes et ne dirait rien du cas ou le
#: reshape reussit -- c'est-a-dire du seul cas dangereux.
FAILURE_NOT_THREE_CHANNELS = "page_not_three_channels"

#: La page de calibration est **presente et son role est connu**, mais sa geometrie n'a
#: pas ete resolue: coin corne, marqueur d'angle abime. `EPIC5-ARB-70`, ajoute a la passe
#: de correction de 5.19 sur un majeur des couches 1 et 3.
#:
#: Le motif existe parce que le lot sortait alors **indistinguable** d'un lot ou la
#: feuille manque: statut `not_applied`, journal disant « aucune page de calibration lue »
#: d'une page qui y etait, et aucune trace dans le document de la raison pour laquelle ce
#: lot n'avait pas de couleur. Le cas symetrique -- page presente dont les pastilles ne se
#: lisent pas -- rendait `failed` avec son motif: deux pannes de terrain quasi identiques,
#: deux declarations opposees, et c'etait la plus probable des deux qui mentait.
#:
#: **La frontiere du motif est ce que le code peut savoir.** Il n'est pose que si le QR a
#: livre son payload, donc si le role est connu. Un QR illisible laisse le role
#: inconnaissable et le lot vaut `not_applied`: on ne declare pas en echec une page dont
#: rien ne dit qu'elle etait la page de calibration.
FAILURE_PAGE_GEOMETRY_UNRESOLVED = "calibration_page_geometry_unresolved"

#: La forme de correction demandee n'est pas au registre. **Ajoute a la passe de
#: correction de 5.16** (bloquant B2 de la couche 1, F3 de la couche 2), et le motif est
#: une asymetrie de regime, pas un oubli de vocabulaire.
#:
#: Le regime **local** resolvait la forme tot et echouait avant d'avoir lu une pastille.
#: Le regime **transporte**, lui, prend l'identifiant sur le **profil importe**
#: (`getattr(imported_profile, "correction_id", ...)`) et sautait explicitement cette
#: validation: la forme inconnue n'etait donc decouverte qu'a l'interieur
#: d'`assess_divergence`, dont le `except ValueError` l'absorbait --
#: `UnknownCorrectionFormError` **est** un `ValueError`. Consequence mesuree: une page
#: dont le residu importe vaut 33 dE76 ressortait `applied`, avec `diverges = None` et un
#: motif qui disait « exces non calculable » la ou la verite etait « forme inconnue ».
#:
#: Ce n'est donc pas un repli sur la forme active -- que le depot interdit explicitement,
#: docstring d'`UnknownCorrectionFormError` -- c'est le **contournement silencieux d'un
#: refus**, sans le drapeau que l'AC 15 exige explicite. La garde etait desarmee
#: precisement dans le regime pour lequel elle existe.
FAILURE_UNKNOWN_CORRECTION_FORM = "unknown_correction_form"

#: Seuil de dispersion inter-repliques, en dE76. Tranche par Egan le 2026-08-10
#: (option (c): seuil dur **et** valeur rapportee). Pose a ~4 fois le bruit median
#: mesure entre repliques d'une meme valeur sur une meme page -- 1,08 dE76 au scan
#: propre, 1,29 sur le chemin PDF. Un seuil sous le bruit ferait echouer des pages sur
#: du bruit; celui-ci est **provisoire** et se revise au troisieme tirage.
MAX_REPLICATE_DISPERSION_DE76 = 5.0

#: Bornes de plausibilite d'une mesure de pastille, en sRGB encode normalise. Une
#: valeur hors de ces bornes ne vient pas d'une pastille imprimee mais d'un
#: echantillonnage qui a manque sa cible -- page mal redressee, emplacement decale.
#: Volontairement larges: leur role est d'attraper une erreur de geometrie, pas de
#: juger une couleur.
#:
#: **Borne haute portee de 0,995 a 1,0 le 2026-08-11** (bloquant B6 de la revue).
#: Mesure: sur le tirage reel, `neutral-245` -- la valeur la plus claire du jeu
#: d'ajustement -- ressort a 253,62/255, soit 0,9946. L'ancienne borne etait donc a
#: **0,10 code** au-dessus d'une mesure legitime: un code de plus et les sept pages
#: du tirage etaient refusees sous `patches_out_of_plausible_range`, un motif qui
#: annonce une erreur de geometrie -- donc un diagnostic faux en plus d'un refus
#: injustifie.
#:
#: Ce que cela concede, et il faut l'ecrire: **la borne haute ne discrimine plus le
#: papier nu**. Elle ne peut pas: la fenetre entre `neutral-245` imprime (253,6) et
#: le papier nu (~255) est de 1,4 code sur le tirage reel, sous la variation du
#: papier. Distinguer les deux est le travail de la sentinelle blanche, qui porte un
#: **cadre imprime** precisement pour etre localisable (story 5.9, AC 5) -- pas celui
#: d'un intervalle sur une valeur encodee. La borne haute reste donc une garde de
#: **domaine** (une mesure hors [0, 1] est impossible et signale un bug), et c'est la
#: borne basse qui garde la geometrie: echantillonner hors feuille ou dans une zone
#: noire ressort pres de 0.
PLAUSIBLE_RANGE = (0.01, 1.0)

#: Facteur d'indiscernabilite des sentinelles: deux niveaux consecutifs plus proches
#: que `SENTINEL_DISCRIMINATION_FACTOR` fois le bruit de mesure ne sont pas
#: distinguables par cette mesure, ce qui est exactement ce que la regle de lecture de
#: 5.9 demande de constater. Valeur reprise du banc de terrain
#: (`scripts/research/patch_delta_e_field_measurement.py`), qui a produit les verdicts
#: publies dans `analyse-2026-08-10-campagne-terrain.md`: le code et le banc doivent
#: rendre le **meme** verdict sur les memes donnees, sinon le depot porte deux verites.
SENTINEL_DISCRIMINATION_FACTOR = 2.0

#: Motif rendu quand un axe n'est pas mesurable: ses valeurs ne sont pas sur la page.
REASON_VALUES_ABSENT = "values_absent_from_sheet"

#: Motif rendu quand le bruit de mesure n'est pas estimable, donc le seuil
#: d'indiscernabilite non calculable. **Pas** un verdict de non-ecretage: voir
#: `measurement_noise_de76`.
REASON_NOISE_NOT_ESTIMABLE = "measurement_noise_not_estimable"


def sampled_square_mm(size_mm: float) -> tuple[float, float]:
    """Rendre (retrait, cote) du carre echantillonne d'une pastille.

    **Aucun nombre n'est declare ici**: le retrait et le cote viennent de
    `patch_presets`, ou la geometrie du carre est une propriete du **placement**
    (AC 2). Depuis `EPIC5-ARB-17(a)`, ce retrait porte **seul** la protection contre
    la contamination inter-pastilles -- la regle d'adjacence qui interdisait deux
    pastilles saturees voisines a ete supprimee, et `patches-18-v2` en place douze
    chromatiques sur dix-huit, donc voisines par construction. Elargir la zone mesuree
    ne degrade plus une precaution redondante: cela supprime la derniere.

    Le cas des tailles autres que `PATCH_SIZE_MM` est traite **proportionnellement**,
    parce qu'un retrait fixe de 3,0 mm ne laisserait rien a mesurer sur une pastille
    de 6 mm -- taille que la mesure du 2026-08-10 rend envisageable.
    """
    from . import patch_presets

    if size_mm == patch_presets.PATCH_SIZE_MM:
        return patch_presets.SAMPLING_INSET_MM, patch_presets.SAMPLED_SIDE_MM
    ratio = patch_presets.SAMPLING_INSET_MM / patch_presets.PATCH_SIZE_MM
    inset = size_mm * ratio
    return inset, size_mm - 2 * inset


def page_has_three_channels(rectified_page) -> bool:
    """La page redressee porte-t-elle exactement trois canaux ?

    Precondition de `sample_patches`, posee ici plutot que chez ses deux appelants pour
    qu'ils la pesent du **meme** poids: la fonction qui echantillonne fait
    `reshape(-1, 3)`, donc toute autre forme rend soit une exception nue, soit -- pire --
    des triplets qui melangent les canaux. Voir `FAILURE_NOT_THREE_CHANNELS`.

    Rendre un booleen et non lever: chacun des deux appelants possede son propre
    vocabulaire d'echec et sa propre provenance a porter.
    """
    shape = getattr(rectified_page, "shape", ())
    return len(shape) == 3 and shape[2] == 3


def sample_patches(rectified_page, layout, dpi: int):
    """Echantillonner les pastilles **sur la page redressee**, aux positions resolues.

    Jamais sur le scan brut (deuxieme precondition LUT), jamais a des positions
    devinees. L'appelant a resolu `layout` par `patch_presets.resolve_patch_layout`,
    donc depuis `template_id` et `patch_preset_id` lus au payload.

    Rend (mesures BGR normalisees, `value_id` par mesure). Une pastille dont le carre
    echantillonne tombe hors de la page est **omise** et son absence se voit au
    cardinal: la garde de l'AC 8 la traite, ce niveau ne devine rien.
    """
    from . import page_templates

    measured, ids = [], []
    for patch in layout:
        inset, side = sampled_square_mm(patch.size_mm)
        x0, y0 = page_templates.mm_to_px(patch.x_mm + inset, patch.y_mm + inset, dpi)
        x1, y1 = page_templates.mm_to_px(
            patch.x_mm + inset + side, patch.y_mm + inset + side, dpi)
        height, width = rectified_page.shape[:2]
        if x0 < 0 or y0 < 0 or x1 > width or y1 > height or x1 <= x0 or y1 <= y0:
            continue
        window = rectified_page[y0:y1, x0:x1]
        if window.size == 0:
            continue
        # L'echelle se choisit sur la **largeur** du type et non sur son identite: un TIFF
        # de scanner gros-boutien porte le dtype `>u2`, que `color_pipeline
        # .validate_bgr_input` declare licite et normalise, et pour lequel
        # `dtype == np.uint16` est **faux**. L'echelle 255 etait alors appliquee a des codes
        # 16 bits: mesure a l'unite sur la meme page, `44,3` a `242,9` au lieu de `0,17` a
        # `0,95` (finding `F3` de la revue de la passe de correction). Le sens etait prudent
        # -- la garde de plausibilite attrapait le cas -- mais le motif accusait
        # l'impression la ou la cause etait un reglage de scanner, et tout le lot ressortait
        # `failed`. C'est la moitie « ordre d'octets » de l'ecart que le bloquant B3 avait
        # ferme du cote « cardinal de canaux ».
        scale = 65535.0 if window.dtype.itemsize == 2 else 255.0
        measured.append(window.reshape(-1, 3).mean(axis=0) / scale)
        ids.append(patch.value_id)
    return np.asarray(measured, dtype=np.float64).reshape(-1, 3), tuple(ids)


def replicate_dispersion(measured_bgr, ids):
    """Dispersion entre repliques d'une **meme** valeur, en dE76. AC 3b.

    Le signal le plus precoce d'un scan inexploitable, bien avant que la metrique ne
    bascule. Elle mesure autre chose qu'elle: on peut avoir une dispersion elevee et
    une correction encore bonne, ou l'inverse.

    Moyenner des valeurs **differentes** detruirait l'information que la repetition
    existe pour produire (piege 5): on ne moyenne que les repliques d'une meme valeur,
    et la dispersion est le **maximum** des ecarts a la moyenne de chaque groupe --
    pas leur moyenne, qui diluerait une replique salement imprimee dans les autres.

    Rend (dispersion maximale, cardinal de pixels non consomme ici, detail par valeur).
    """
    groups: dict[str, list[np.ndarray]] = {}
    for value_id, row in zip(ids, measured_bgr):
        groups.setdefault(value_id, []).append(row)
    detail: dict[str, float] = {}
    for value_id, rows in groups.items():
        # Une valeur vue une seule fois n'a **pas** une dispersion de zero: elle n'en a
        # pas. L'inscrire a 0,0 publiait la meilleure lecture possible la ou rien n'a
        # ete lu -- finding majeur des couches 2 et 3 -- et rendait de surcroit
        # l'agregat insensible: avec un preset a `repetition = 1`, tout valait zero.
        if len(rows) < 2:
            continue
        stack = np.asarray(rows)
        centre = stack.mean(axis=0)
        detail[value_id] = float(delta_e76_srgb_d65(stack, centre).max())
    worst = max(detail.values()) if detail else None
    return worst, detail


def measurement_noise_de76(measured_bgr, ids) -> float:
    """Bruit de la chaine, en dE76: **mediane des ecarts par paires** de repliques.

    Grandeur distincte de `replicate_dispersion`, et le confondre etait le bloquant B2
    de la revue du 2026-08-11. Les deux se calculent sur les memes donnees et ne
    repondent pas a la meme question:

    * `replicate_dispersion` est un **maximum des ecarts a la moyenne**: elle repond a
      « une replique est-elle salement imprimee », donc elle doit remonter la pire;
    * ce bruit-ci est une **mediane des ecarts par paires**: il repond a « quel ecart
      cette chaine ne sait pas reproduire », donc il doit **ignorer** l'aberration.
      Median et non moyenne pour la meme raison qu'au banc de terrain: une pastille
      aberrante (poussiere, pli) ne doit pas gonfler le seuil et **masquer** un
      ecretage.

    Ce que la confusion produisait, mesure sur les 7 pages reelles du tirage a
    sentinelles: un seuil de 4,46 a 5,04 au lieu de 2,30 a 3,71, et **les cinq axes
    declares ecretes** alors que `analyse-2026-08-10-campagne-terrain.md` §2 publie
    rouge et bleu **non** ecretes. Le meme jeu de donnees rendait donc deux verdicts
    selon l'outil qui le lisait.

    Rend `nan` quand aucune valeur n'a deux repliques: le bruit n'est alors pas
    estimable, ce qui n'est **pas** la meme chose que « bruit nul ». L'appelant en tire
    un verdict `unavailable`, jamais un `clipped: False`.
    """
    groups: dict[str, list[np.ndarray]] = {}
    for value_id, row in zip(ids, measured_bgr):
        groups.setdefault(value_id, []).append(row)
    spreads: list[float] = []
    for rows in groups.values():
        if len(rows) < 2:
            continue
        stack = np.asarray(rows)
        spreads.extend(
            float(delta_e76_srgb_d65(stack[i], stack[j]))
            for i in range(len(stack)) for j in range(i + 1, len(stack)))
    return float(np.median(spreads)) if spreads else float("nan")


def aggregate_by_value(measured_bgr, ids) -> tuple[tuple[str, ...], np.ndarray]:
    """Moyenne des repliques, **par valeur**. H4, et elle n'etait pas faite.

    H4 (`decisions-2026-08-08-epic-5.md`) pose l'agregation en deux temps: moyenne
    arithmetique sur le carre echantillonne, par replique; **puis moyenne des
    repliques, par valeur**. Et il ajoute que la dispersion inter-repliques est
    rapportee separement et *n'entre pas dans la valeur agregee*.

    Bloquant B3 de la revue du 2026-08-11: le second temps manquait. Metrique et
    ajustement voyaient 20 lignes -- 10 valeurs x 2 repliques -- au lieu de 10 valeurs,
    donc la dispersion inter-repliques entrait dans `mean` et dans `max`, ce que H4
    interdit mot pour mot. Effet chiffre: une replique deplacee de 0,10 consommait
    12,095 des 16,0 du plafond d'acceptation **sans declencher aucun motif d'echec**.
    Le plafond mesurait alors partiellement le bruit du papier au lieu de l'erreur de
    couleur, c'est-a-dire autre chose que ce qu'il declare mesurer.

    L'ordre de sortie est **lexicographique par `value_id`**, comme `per_value` et
    `worst_value_id` de la signature d'`EPIC5-ARB-28`: deux executions sur les memes
    donnees doivent rendre le meme tableau, sans quoi une metrique n'est pas
    reproductible.
    """
    groups: dict[str, list[np.ndarray]] = {}
    for value_id, row in zip(ids, measured_bgr):
        groups.setdefault(value_id, []).append(row)
    ordered = tuple(sorted(groups))
    if not ordered:
        return (), np.zeros((0, 3), dtype=np.float64)
    stacked = np.asarray(
        [np.mean(np.asarray(groups[value_id]), axis=0) for value_id in ordered],
        dtype=np.float64)
    return ordered, stacked


def clipping_verdict(measured_bgr, ids, chains, noise_de76):
    """Verdict d'ecretage depuis les sentinelles. AC 9, regle de lecture de 5.9.

    **Independant du statut** (`EPIC5-ARB-16`): les quatre combinaisons statut x
    ecretage sont representables et aucune n'est interdite. Un ecretage n'est pas un
    echec de la correction, c'est une limite physique de l'imprimante.

    Regle reprise et non reecrite: *deux niveaux consecutifs d'une meme chaine mesures
    comme indiscernables valent ecretage de cet axe; si l'indiscernabilite commence
    des le couple in-gamut/mediane, l'ecretage est plus precoce que l'echelon median
    et la localisation s'arrete la -- le MVP ne pretend pas mieux.*

    Le verdict porte **son ecart et son seuil** a cote du booleen. Motif mesure le
    2026-08-10: un booleen pose sur une grandeur qui vit au voisinage de son seuil
    bascule sur du bruit -- blanc et vert ont change de verdict entre deux conditions
    de la meme feuille, les quatre valeurs encadrant le seuil.
    """
    threshold = SENTINEL_DISCRIMINATION_FACTOR * noise_de76
    means: dict[str, np.ndarray] = {}
    for value_id, row in zip(ids, measured_bgr):
        means.setdefault(value_id, []).append(row)
    means = {key: np.mean(rows, axis=0) for key, rows in means.items()}

    verdicts = {}
    for axis, chain in chains.items():
        if any(value_id not in means for value_id in chain) or len(chain) < 2:
            verdicts[axis] = {"clipped": None, "reason": REASON_VALUES_ABSENT}
            continue
        gaps = [float(delta_e76_srgb_d65(means[first], means[second]))
                for first, second in zip(chain, chain[1:])]
        onset = next(
            (index for index, gap in enumerate(gaps) if gap <= threshold), None)
        verdicts[axis] = {
            "clipped": onset is not None,
            # Rang du couple ou l'indiscernabilite commence, et l'identifiant de
            # l'echelon correspondant. Le rang 0 est le couple in-gamut/mediane, que
            # la regle de 5.9 traite a part: l'ecretage est alors plus precoce que
            # l'echelon median et la localisation s'arrete la.
            "onset_index": onset,
            "onset_value_id": None if onset in (None, 0) else chain[onset],
            "gaps_de76": gaps,
            "threshold_de76": threshold,
        }
    return verdicts


def clipping_summary(verdicts: dict) -> dict | None:
    """Forme **manifest** du verdict d'ecretage, celle que le schema exige.

    Point dur trouve par la revue du 2026-08-11 (bloquant B5): la story declare la
    forme des resultats de page, et le schema que la story 5.7 a **deja livre** rend
    `clipping.detected` obligatoire (`project.schema.json`,
    `reconstruction.page_calibration_results.items.clipping.required`). Le dictionnaire
    par axe rendu par `clipping_verdict` ne le porte pas: un manifest ecrit dessus
    etait **invalide**, et ce n'etait pas rattrape par un test parce que la story 5.7
    n'ecrit encore que le statut.

    Deux points de semantique, qui etaient faux et le sont corriges ici:

    * `onset_step` est de type `string | null` au schema, pas un entier: c'est
      l'**identifiant de l'echelon** ou l'indiscernabilite commence. `null` ne veut
      pas dire « pas d'ecretage », il veut dire « des le couple in-gamut/mediane »,
      donc *plus precoce que l'echelon median* -- l'ancien code y mettait `0`, ce qui
      inversait la lecture;
    * quand **rien** n'est mesurable, cette fonction rend `None` et l'appelant
      **n'ecrit pas** la cle. C'est la regle deja tenue par
      `io/scan_manifest._build_calibration_results`: ecrire `{detected: false}` sans
      avoir mesure serait affirmer « aucun ecretage detecte » la ou la verite est
      « rien n'a ete mesure ».

    Le detail par axe est conserve sous `per_axis` -- le schema declare
    `additionalProperties: true` a cet endroit, et le detail est ce qui permet de
    relire un verdict de frontiere sans relancer le scan.
    """
    measurable = {axis: verdict for axis, verdict in verdicts.items()
                  if verdict.get("clipped") is not None}
    if not measurable:
        return None
    clipped = sorted(axis for axis, verdict in measurable.items() if verdict["clipped"])
    # `onset_step` est un champ de page la ou `axes` en est une liste: on retient
    # l'ecretage le plus **precoce**, a egalite le premier axe par ordre alphabetique
    # -- deterministe, comme `worst_value_id` l'est pour la metrique.
    onset_value_id = None
    if clipped:
        earliest = min(clipped, key=lambda axis: (measurable[axis]["onset_index"], axis))
        onset_value_id = measurable[earliest]["onset_value_id"]
    return {
        "detected": bool(clipped),
        "axes": clipped,
        "onset_step": onset_value_id,
        "per_axis": dict(verdicts),
    }


@dataclass(frozen=True)
class PageCalibration:
    """La forme des resultats de calibration **d'une page**. AC 9.

    Declaree ici, **ecrite** par la story 5.7 qui possede le manifest. Contrainte de
    la matrice de responsabilite: `page_calibration_results` est manifest-uniquement,
    interdit dans le nom de fichier, le QR, ArUco et le conteneur video.

    `gamut_map_id` n'en fait **pas** partie: c'est un champ de niveau lot
    (`EPIC5-ARB-20`), porte une seule fois par `lots[].gamut_map_id`. Deux
    emplacements pour une meme donnee, ce sont deux verites.
    """

    status: str
    values_version: str
    patch_preset_id: str
    profile: AnyCorrectionProfile | None
    acceptance: AcceptanceVerdict | None
    #: `None` quand la dispersion n'a **pas ete mesuree**, et non `0.0`. Publier zero
    #: pour « non mesure » etait un finding majeur des couches 2 et 3: zero est la
    #: valeur d'une page parfaite, donc la meilleure lecture possible affichee la ou
    #: rien n'a ete lu -- le meme faux succes que R12, applique a la dispersion.
    replicate_dispersion_de76: float | None
    channel_relative_deviation_before_correction: tuple[float, float, float] | None
    #: `None` quand aucun axe n'est mesurable: la cle n'est alors pas ecrite au
    #: manifest (`EPIC5-ARB-52`).
    clipping: dict | None
    #: Identifiants de **forme** et de **seuils**, portes meme sur un echec. Finding de
    #: la revue de 5.4a, verse au `deferred-work` et repris ici: sur une page `failed`,
    #: ni la forme de correction tentee ni l'entree d'acceptation ne survivaient --
    #: `profile` et `acceptance` etant tous deux `None`. Un echec dont on ne sait pas
    #: contre quoi il a echoue n'est pas relisable, et c'est precisement le cas ou on
    #: relit.
    #:
    #: **Ce defaut n'a pas bascule sur `ACTIVE_CORRECTION_FORM_ID`** (story 5.21), a la
    #: difference de son homologue de `LotCorrection`, et la raison est mesurable et non
    #: stylistique: les trois constructions de production de ce type -- `_failed`,
    #: la sortie nominale de `calibrate_page`, et `calibration_page_result` -- passent
    #: **toutes** la forme effective (`form_id`, ou celle du lot). Aucun chemin de
    #: production ne peut donc atteindre ce defaut, et un defaut inatteignable ne peut
    #: pas produire l'enregistrement menteur que la bascule existe pour empecher. Il
    #: reste ce qu'il a toujours ete: un filet pour une construction directe.
    correction_form_id: str = CORRECTION_FORM_ID
    acceptance_id: str = ACTIVE_COLOR_ACCEPTANCE_ID
    failure_reason: str | None = None
    input_warnings: tuple[str, ...] = ()
    #: **D'ou vient la correction appliquee** (AC 10 de 5.16). Present dans les deux
    #: regimes et distinct entre eux: sans lui, une frame corrigee depuis la page de
    #: calibration du lot et une frame corrigee depuis les pastilles de sa propre
    #: feuille sont indistinguables a posteriori.
    correction_source: str = CORRECTION_SOURCE_OWN_SHEET
    #: Identifiant de la page qui a produit la correction: la page de calibration du
    #: lot dans le regime transporte, la page elle-meme dans le regime de repli.
    correction_source_page_id: str | None = None
    #: Ce que la garde de divergence a mesure, ou `None` quand aucune correction n'a
    #: ete importee -- une page qui s'ajuste sur elle-meme ne peut pas diverger d'elle.
    divergence: "DivergenceAssessment | None" = None
    #: Le message rendu a l'operateur, quand le motif d'echec en a un. Porte **a cote**
    #: du motif ferme et jamais a sa place: le motif est du vocabulaire, le message est
    #: ce que l'operateur lit, et les confondre rend l'un des deux inutilisable.
    failure_message: str | None = None
    #: Pourquoi une page `not_applied` ne porte **pas** de correction, quand la reponse
    #: n'est pas « il n'y en avait pas » (`EPIC5-ARB-78`). Deliberement **distinct** de
    #: `failure_reason` et d'un autre vocabulaire: le repli automatique est un echec,
    #: `--cc off` est un choix, et les confondre ferait rescanner une feuille que
    #: personne n'a jugee mauvaise. `None` est le cas ordinaire.
    not_applied_reason: str | None = None
    #: **La chaine de scan dont vient la correction** (story 5.22, `AC 9`), quand elle
    #: vient d'un profil de chaine. `None` dans tous les autres regimes.
    #:
    #: Champ **distinct** de `correction_source_page_id` et non une reutilisation: les
    #: deux repondent a deux questions qui ne se confondent pas. `correction_chain_id`
    #: dit *pour quelle chaine* le profil a ete consigne -- c'est lui qui designe le
    #: fichier `versions/calibration/<chain_id>.json` --, tandis que
    #: `correction_source_page_id` continue de designer *la page de calibration qui a
    #: ajuste les coefficients*, valeur que le profil porte et que la relecture rend.
    #: Ecraser la seconde par la premiere aurait perdu la seule trace de la feuille
    #: physique a rescanner si la calibration de la chaine devait etre reprise.
    correction_chain_id: str | None = None
    #: **Ce que le profil de chaine avait mesure au moment ou il a ete ajuste**, relu du
    #: fichier de profil (bloquant `C2` de la revue de 5.22). `None` partout ailleurs.
    #:
    #: Champ **distinct** d'`acceptance`, et l'asymetrie est le fond du correctif:
    #: `acceptance` est le verdict que **cette** passe a mesure sur **cette** page, le
    #: champ ci-dessous celui qu'une autre passe a mesure sur la feuille de calibration
    #: de la chaine. Les fondre en un seul ferait dire au manifest qu'une grandeur datee
    #: du jour de la calibration a ete mesuree sur ce scan -- c'est ce que la docstring de
    #: `chain_correction_from_document` refuse, et le refus reste entier: le verdict
    #: voyage sous son propre nom, jamais a la place de celui de la page.
    chain_profile_acceptance: AcceptanceVerdict | None = None
    #: **L'ecart brut a brut entre cette planche et la page de calibration du lot**
    #: (story 5.23, AC 2 et 4). `None` quand il n'est pas calculable -- pas de page de
    #: calibration lue dans ce scan, ou son bandeau de temoins non imprime. Il
    #: n'**avertit** que, et ne refuse jamais: c'est tout l'objet d'`EPIC5-ARB-82`.
    raw_divergence: "RawDivergenceAssessment | None" = None


def _not_applied_page(*, reason: str, preset_id: str, values_version: str,
                      dispersion: float | None = None,
                      clipping: dict | None = None,
                      warnings: tuple[str, ...] = (),
                      correction_form_id: str = CORRECTION_FORM_ID,
                      correction_source: str = CORRECTION_SOURCE_OWN_SHEET,
                      correction_source_page_id: str | None = None,
                      correction_chain_id: str | None = None,
                      chain_profile_acceptance: "AcceptanceVerdict | None" = None,
                      divergence: "DivergenceAssessment | None" = None,
                      failure_message: str | None = None) -> PageCalibration:
    """Une page **non corrigee sans que rien n'ait echoue**. Story 5.22, AC 6 et 7.

    Symetrique de `_failed`, et la symetrie est le point: les deux rendent une page
    sans `profile`, donc des frames ecrites telles quelles, mais elles ne disent pas
    la meme chose a l'operateur et n'appellent pas le meme geste. Un echec envoie
    rescanner; un `not_applied` dit qu'une decision reste a prendre.

    `EPIC5-ARB-80` decision 5 fait basculer la divergence de la premiere categorie
    vers la seconde: une planche qui derive au-dela de `color-divergence-1` n'est plus
    un refus dur mais un **avertissement chiffre** doublé d'une proposition. Le motif
    voyage donc sous `not_applied_reason` et **jamais** sous `failure_reason` -- un
    lecteur qui filtre les pages en echec sur la presence du champ d'echec compterait
    sinon comme panne une planche que personne n'a jugee mauvaise (`EPIC5-ARB-78`,
    meme argument que pour `--cc off`).

    `failure_message` garde son nom malgre le statut: c'est le champ « ce que
    l'operateur lit », deja porte par `PageCalibration`, et lui en ajouter un second
    ferait deux emplacements pour la meme donnee. Il porte ici le message
    d'avertissement, chiffre, et non un motif d'echec.
    """
    return PageCalibration(
        status=color_pipeline_not_applied(), values_version=values_version,
        patch_preset_id=preset_id, profile=None, acceptance=None,
        replicate_dispersion_de76=dispersion,
        channel_relative_deviation_before_correction=None,
        clipping=clipping, input_warnings=warnings,
        correction_form_id=correction_form_id,
        correction_source=correction_source,
        correction_source_page_id=correction_source_page_id,
        correction_chain_id=correction_chain_id,
        # Le verdict du profil voyage **avec** l'identifiant de chaine et sur les memes
        # sorties que lui, echecs compris: la question a laquelle il repond -- « ce profil,
        # que deformait-il quand il a ete ajuste ? » -- se pose exactement quand
        # l'operateur relit une page que ce profil n'a pas corrigee.
        chain_profile_acceptance=chain_profile_acceptance,
        divergence=divergence, failure_message=failure_message,
        # `failure_reason` reste **None**: c'est ce qui distingue structurellement
        # cette sortie d'un echec, et non seulement la valeur du statut.
        not_applied_reason=reason)


def _failed(reason: str, *, preset_id: str, values_version: str,
            dispersion: float | None = None, clipping: dict | None = None,
            warnings: tuple[str, ...] = (),
            correction_form_id: str = CORRECTION_FORM_ID,
            correction_source: str = CORRECTION_SOURCE_OWN_SHEET,
            correction_source_page_id: str | None = None,
            correction_chain_id: str | None = None,
            chain_profile_acceptance: "AcceptanceVerdict | None" = None,
            divergence: "DivergenceAssessment | None" = None,
            failure_message: str | None = None) -> PageCalibration:
    """Construire un echec: statut `failed`, motif nomme, **aucune correction**.

    `correction_form_id` garde le defaut `CORRECTION_FORM_ID` (story 5.21): fonction
    privee, ses **deux** appelants -- la fermeture `_fail` de `calibrate_page` et
    `calibration_page_result` -- nomment tous les deux la forme effective, donc ce defaut
    est inatteignable par construction et ne decide rien. Le basculer donnerait
    l'apparence d'une decision de forme active la ou il n'y a qu'un filet de signature.
    """
    return PageCalibration(
        status="failed", values_version=values_version, patch_preset_id=preset_id,
        profile=None, acceptance=None, replicate_dispersion_de76=dispersion,
        channel_relative_deviation_before_correction=None,
        # `clipping` reste `None` s'il l'est: `or {}` publiait un dictionnaire vide,
        # que le consommateur ne distingue pas d'un verdict rendu sans axe ecrete.
        clipping=clipping, failure_reason=reason, input_warnings=warnings,
        correction_form_id=correction_form_id,
        correction_source=correction_source,
        correction_source_page_id=correction_source_page_id,
        correction_chain_id=correction_chain_id,
        # Meme regle que sur `_not_applied_page`: le verdict du profil accompagne
        # l'identifiant de chaine, y compris sur un echec.
        chain_profile_acceptance=chain_profile_acceptance,
        divergence=divergence, failure_message=failure_message)


#: Chaines de lecture de l'ecretage, **derivees des valeurs** et non des noms.
def sentinel_chains(table) -> dict:
    """Rendre {axe: (in-gamut, mediane, extreme, ...)} depuis la table de valeurs.

    La regle de lecture de 5.9 compare des niveaux **consecutifs d'une meme chaine**,
    la tete etant la valeur in-gamut. Reste a dire quelle valeur d'ajustement est la
    tete de quelle chaine, et c'est fait ici **par proximite colorimetrique**, jamais
    par analyse du `value_id`.

    Motif, et il vient d'un bug attrape le 2026-08-10 sur ce fichier meme: une
    premiere version cherchait la tete par suffixe de nom (`...red` pour
    `sentinel-red-1`). Elle marchait pour les trois axes chromatiques et **echouait
    silencieusement** pour le noir et le blanc, dont les tetes s'appellent
    `neutral-020` et `neutral-245` -- aucun nom ne contient « black » ni « white ».
    Les deux chaines sortaient sans tete, donc sans le couple in-gamut/mediane que la
    regle demande de comparer en premier, et le verdict d'ecretage du noir devenait
    incalculable **sans qu'aucune erreur soit levee**. Une regle derivee des valeurs
    est juste pour toute version future de la table sans edition (`EPIC5-ARB-29`).
    """
    adjustment = tuple(table.adjustment_values())
    if not adjustment:
        return {}
    references = np.asarray([value.rgb for value in adjustment], dtype=np.float64) / 255.0

    grouped: dict[str, list] = {}
    for sentinel in table.sentinel_values():
        target = np.asarray(sentinel.rgb, dtype=np.float64) / 255.0
        distances = np.linalg.norm(references - target, axis=1)
        head = adjustment[int(np.argmin(distances))]
        grouped.setdefault(head.value_id, []).append(sentinel)

    chains = {}
    for head_id, sentinels in grouped.items():
        # L'ordre de la chaine va de l'in-gamut vers l'extreme: on trie les
        # sentinelles par eloignement croissant a la tete, ce qui rend l'ordre des
        # echelons sans lire aucun suffixe numerique.
        head_rgb = np.asarray(
            next(v.rgb for v in adjustment if v.value_id == head_id), dtype=np.float64) / 255.0
        sentinels.sort(key=lambda value: float(np.linalg.norm(
            np.asarray(value.rgb, dtype=np.float64) / 255.0 - head_rgb)))
        # L'axe est nomme par sa tete: seul identifiant sans ambiguite et entierement
        # derive. Un libelle « joli » demanderait une table de correspondance, donc
        # une enumeration litterale -- exactement ce qu'EPIC5-ARB-29 interdit.
        chains[head_id] = tuple([head_id] + [value.value_id for value in sentinels])
    return chains


# ---------------------------------------------------------------------------
# Story 5.16, AC 4 et 5 : la source d'ajustement **externe** a la page corrigee
# ---------------------------------------------------------------------------

class UnknownLatticeValueError(ValueError):
    """Une mesure presentee comme du treillis ne porte aucun identifiant connu.

    Jamais un repli sur « ignorer la mesure »: une page de calibration dont la moitie
    des pastilles ne se resout pas n'est pas une page de calibration degradee, c'est un
    echantillonnage qui a manque sa cible -- le meme mode d'echec que
    `FAILURE_PATCHES_NOT_FOUND` couvre pour une planche d'images.
    """


@dataclass(frozen=True)
class ExternalAdjustmentSource:
    """Un jeu d'ajustement mesure **ailleurs** que sur la page qu'il corrigera.

    C'est la forme executable d'`EPIC5-ARB-54`: la correction du lot s'ajuste sur la
    page de calibration dediee, premiere page du lot, et se transporte aux planches
    d'images. Le cout de ce transport est mesure et non suppose -- **+0,01 dE76** pour
    la forme en vigueur, **+0,02** pour la forme Lab, sur sept pages du meme tirage --
    et c'est ce prealable qui rend le montage licite plutot qu'hypothetique.

    `source_page_id` est ce qui rend l'AC 10 tenable: il **voyage avec la correction**
    jusqu'au manifest de chaque page corrigee.

    Les deux cardinaux sont portes a cote du jeu parce que ce sont eux que l'AC 4
    epingle, et ils ne se deduisent pas l'un de l'autre: `read_patch_count` est ce que
    la page portait, `retained_patch_count` ce que le filtre de saturation a garde, et
    `len(value_ids)` ce qu'il reste **apres l'agregation H4 par valeur** -- trois
    nombres differents, dont deux se confondent des que le replicat vaut 1.

    `ink_floor_excluded` enregistre **la politique de plancher d'encrage sous laquelle
    ce jeu a ete construit**, et non la forme qui l'a demandee (`EPIC5-ARB-77`). Deux
    formes qui partagent la politique -- la forme en vigueur et la forme Lab -- se
    transportent donc un jeu l'une a l'autre sans friction, alors qu'un jeu filtre pour
    la forme affine presente a `color-correction-tone-curve-chroma-1` est refuse: c'est
    exactement l'incoherence qui compte, et rien de plus. Enregistrer l'identifiant de
    forme a la place refuserait le transport affine <-> Lab, qui est licite et deja
    exerce en test.
    """

    source_page_id: str
    value_ids: tuple[str, ...]
    measured_bgr: np.ndarray
    reference_bgr: np.ndarray
    neutral_mask: np.ndarray
    read_patch_count: int
    retained_patch_count: int
    ink_floor_excluded: bool = True


#: Politique de plancher d'encrage, **une entree par forme** et non une liste
#: d'exceptions (`EPIC5-ARB-77`). Le total est exige plutot que suppose: une forme
#: ajoutee demain sans entree ici leve, au lieu d'heriter en silence de la politique de
#: sa voisine -- c'est la meme raison qui interdit a `get_correction_form` de replier
#: sur la forme active, et une frontiere negative l'epingle en test.
#:
#: `True` = le plancher d'encrage (`lattice-008-008-008`, sous `SHADOW_FLOOR_8BIT`) est
#: **retire** du jeu d'ajustement. Mesure du 2026-08-13, rejouee le meme jour par la
#: revue de la story 5.20 sur les trois captures reelles, en dE76 moyen gagne par
#: l'exclusion (positif = l'exclusion aide):
#:
#: * forme en vigueur : +0,686 / +0,710 / +0,006 -- exclusion retenue ;
#: * forme courbe+chroma : **-1,407 / -1,408 / -0,870** -- exclusion **retiree**, elle
#:   degrade les trois captures. La forme traite l'ecrasement des noirs par sa courbe,
#:   donc le point le plus sombre est pour elle une mesure utile et non une
#:   contradiction ;
#: * forme Lab : -0,652 / -0,644 / +0,119 -- inchangee, hors du mandat tranche par
#:   Egan le 2026-08-13, et la reserve est nommee dans `EPIC5-ARB-77`.
CORRECTION_FORM_EXCLUDES_INK_FLOOR: "MappingProxyType[str, bool]" = MappingProxyType({
    CORRECTION_FORM_ID: True,
    CORRECTION_FORM_LAB_ID: True,
    CORRECTION_FORM_TONE_CHROMA_ID: False,
})


class InkFloorPolicyMismatchError(Exception):
    """Un jeu d'ajustement presente a une forme dont la politique de plancher differe.

    **Deliberement pas une `ValueError`**, et c'est la moitie de son interet:
    `fit_lot_correction_from_page` enveloppe `fit_from_external_source` dans un
    `except ValueError` qui rend `FAILURE_UNDERDETERMINED_ADJUSTMENT`. Une faute de
    programmation -- construire le jeu pour une forme et l'ajuster avec une autre --
    s'y traduirait en refus de terrain motive, c'est-a-dire en page de calibration
    declaree illisible alors qu'elle est parfaitement lisible. Le diagnostic serait
    alors adresse au scanner et non au code.
    """


def correction_form_excludes_ink_floor(correction_form_id: str) -> bool:
    """La forme retire-t-elle le plancher d'encrage de son jeu d'ajustement ?

    Resout par le registre et **leve** sur une forme inconnue ou non declaree, jamais
    un defaut implicite: une forme nouvelle dont personne n'a tranche la politique doit
    faire echouer l'appel, pas heriter d'un `True` que rien n'a mesure pour elle.
    """
    get_correction_form(correction_form_id)
    try:
        return CORRECTION_FORM_EXCLUDES_INK_FLOOR[correction_form_id]
    except KeyError:
        raise UnknownCorrectionFormError(
            f"Forme '{correction_form_id}' sans politique de plancher d'encrage "
            f"declaree dans CORRECTION_FORM_EXCLUDES_INK_FLOOR. L'effet de l'exclusion "
            "depend de la forme -- mesure a +0,7 dE76 pour la forme en vigueur et a "
            "-1,4 pour la forme courbe+chroma (`EPIC5-ARB-77`) --, donc il se tranche "
            "sur mesure et se declare ici.") from None


def lattice_adjustment_source(measured_bgr, value_ids, *,
                             source_page_id: str,
                             correction_form_id: str = ACTIVE_CORRECTION_FORM_ID
                             ) -> ExternalAdjustmentSource:
    """Construire le jeu d'ajustement depuis les mesures du treillis d'une page.

    Trois choses se passent ici, dans cet ordre, et aucune n'est laissee a l'appelant:

    1. **le refus des sondes d'ombre** (AC 5). Une garde qui refuse, pas un filtre a
       ne pas oublier: les verser degrade la correction de 4,66 a 4,81 dE76;
    2. **le filtre de saturation** de `patch_values`, applique sur la **reference**,
       **et depuis la story 5.20 le filtre de plancher d'encrage** (AC 7): le treillis
       porte son propre niveau le plus sombre, `lattice-008-008-008`, qu'aucune des deux
       gardes precedentes ne couvrait -- la premiere lit un prefixe d'identifiant que ce
       point n'a pas, la seconde une saturation qui est nulle sur un neutre. Mesure du
       2026-08-13 sur `scan-WIN`, forme en vigueur: 14,09 -> 13,41 dE76 moyen et
       35,04 -> 33,42 en maximum. **Ce second filtre est conditionnel a la forme**
       depuis `EPIC5-ARB-77` (revue de 5.20): l'effet mesure ci-dessus est celui de la
       forme en vigueur, et il s'inverse sur `color-correction-tone-curve-chroma-1`
       (-1,407 / -1,408 / -0,870 dE76 sur les trois captures). La forme est donc un
       argument de cette fonction, pas une hypothese;
    3. **l'agregation H4** -- moyenne des repliques par valeur -- avant tout
       ajustement, comme le bloquant B3 de la revue du 2026-08-11 l'exige pour une
       planche d'images. Le banc de recherche, lui, ajustait sur les repliques
       distinctes; c'est le seul ecart assume avec lui, et il va dans le sens de la
       regle du depot.

    **Le filtre de plancher est pose ici et non dans
    `patch_values.calibration_lattice_adjustment_values`**, alors que le filtre de
    saturation, lui, y vit. Ce n'est pas une inconsistance: cette fonction-la est aussi
    ce qui **place** les pastilles sur la page imprimee
    (`patch_presets.resolve_calibration_page_patches`). Y retirer une valeur retirerait
    une pastille de la planche, donc deplacerait toutes les suivantes dans la grille --
    et les pages deja imprimees (le tirage `chendj-mat` du 2026-08-13, 130 pastilles) ne
    se reliraient plus aux positions ou elles ont ete imprimees. Le plancher est une
    regle d'**ajustement**, pas une regle d'impression: une valeur imprimee et mesuree
    qu'on n'ajuste pas reste une valeur qu'on peut juger.

    **`correction_form_id` ne sert qu'a la politique de plancher** (`EPIC5-ARB-77`),
    jamais a ajuster quoi que ce soit: l'ajustement reste entierement dans
    `fit_from_external_source`. Il est **nomme** et non positionnel, comme
    `source_page_id`: un troisieme argument positionnel derriere deux tableaux est
    exactement la forme d'appel ou une inversion silencieuse se glisse.

    **Son defaut suit la forme active** (`ACTIVE_CORRECTION_FORM_ID`, story 5.21) et il
    ne peut pas suivre autre chose: cette fonction et `fit_from_external_source` forment
    un couple dont les deux moities doivent s'accorder sur la politique de plancher. Un
    appelant direct qui laisserait les deux defauts jouer avec des constantes differentes
    construirait un jeu filtre pour une forme et l'ajusterait par l'autre -- exactement
    l'`InkFloorPolicyMismatchError` d'`EPIC5-ARB-77`, leve sur un appel dont aucun des
    deux termes n'est faux pris isolement.
    """
    ids = patch_values.ensure_no_shadow_probe_in_adjustment_set(value_ids)
    exclut_plancher = correction_form_excludes_ink_floor(correction_form_id)
    measured = np.atleast_2d(np.asarray(measured_bgr, dtype=np.float64))
    if len(ids) != len(measured):
        raise ColorMetricError(
            f"cardinalites incoherentes pour le treillis de '{source_page_id}': "
            f"{len(ids)} identifiants, {len(measured)} mesures")

    lattice = {value.value_id: value for value in patch_values.calibration_lattice_values()}
    unknown = sorted({value_id for value_id in ids if value_id not in lattice})
    if unknown:
        raise UnknownLatticeValueError(
            f"Identifiant(s) de treillis inconnu(s) sur '{source_page_id}': "
            f"{', '.join(unknown[:5])}{'...' if len(unknown) > 5 else ''}. Le treillis "
            "est derive de ses niveaux, donc un identifiant absent n'est pas une "
            "valeur nouvelle: c'est une mesure qui ne sait pas ce qu'elle a lu.")

    retained = np.array(
        [patch_values.lattice_saturation_8bit(lattice[value_id].rgb)
         <= patch_values.CALIBRATION_LATTICE_SATURATION_LIMIT_8BIT
         and not (exclut_plancher
                  and patch_values.is_below_ink_floor(lattice[value_id].rgb))
         for value_id in ids],
        dtype=bool)
    kept_ids = tuple(value_id for value_id, keep in zip(ids, retained) if keep)
    # La garde est appelee **sur le jeu retenu**, donc elle constate ce que le filtre
    # ci-dessus vient de faire au lieu de le repeter. Son domaine d'activation reel est
    # ailleurs et il est nomme franchement: un appelant qui construit son propre
    # `ExternalAdjustmentSource` -- la dataclasse est publique et `fit_from_external_source`
    # la consomme telle quelle -- ne passe par aucun filtre. Sans cette ligne, le filtre
    # serait « une regle que l'appelant doit se souvenir d'appliquer », c'est-a-dire
    # exactement ce que la docstring de `calibration_lattice_adjustment_values` refuse.
    #
    # **Elle ne s'appelle que sous la politique qui l'a motivee** (`EPIC5-ARB-77`): sur
    # une forme qui garde le plancher, elle leverait sur toute page reelle -- le point
    # est imprime sur chaque page de calibration, donc toujours mesure. Ce n'est pas
    # une exception a la garde, c'est son domaine: elle dit « ce jeu ne doit pas porter
    # le plancher », un enonce qui n'a de sens que pour une forme qui le retire.
    if exclut_plancher:
        patch_values.ensure_no_ink_floor_value_in_adjustment_set(
            lattice[value_id] for value_id in kept_ids)
    aggregated_ids, aggregated = aggregate_by_value(measured[retained], kept_ids)
    reference = np.asarray(
        [np.asarray(lattice[value_id].rgb[::-1], dtype=np.float64) / 255.0
         for value_id in aggregated_ids], dtype=np.float64).reshape(-1, 3)
    neutral = np.array(
        [len(set(lattice[value_id].rgb)) == 1 for value_id in aggregated_ids], dtype=bool)
    return ExternalAdjustmentSource(
        source_page_id=source_page_id,
        value_ids=aggregated_ids,
        measured_bgr=aggregated,
        reference_bgr=reference,
        neutral_mask=neutral,
        read_patch_count=len(ids),
        retained_patch_count=int(retained.sum()),
        ink_floor_excluded=exclut_plancher,
    )


#: Motif de refus de la garde de conditionnement/rang. `EPIC5-ARB-78`.
REFUSAL_DESIGN_MATRIX_ILL_CONDITIONED = "adjustment_design_matrix_ill_conditioned"

#: Conditionnement maximal de la matrice de conception d'un jeu d'ajustement.
#: `EPIC5-ARB-78` (2026-08-13), **reformule au 2026-08-14** (deuxieme passe de revue,
#: `EPIC5-ARB-78`).
#:
#: **Ce que la garde attrape, et pourquoi elle est devenue necessaire ce jour-la.** Une
#: page de calibration **vierge** -- feuille non imprimee posee au scanner -- traverse
#: toutes les gardes geometriques: ses mesures valent 1,0, donc elles sont dans les bornes
#: de plausibilite (dont la borne haute *est* 1,0), le jeu porte bien deux neutres
#: distincts au sens des identifiants, et `lstsq` resout le systeme degenere **sans
#: lever**. Le resultat est une correction d'apparence normale, ajustee sur rien, et
#: appliquee aux pixels de **toutes** les planches du lot. Jusqu'a `EPIC5-ARB-78`, ce
#: regime etait attrape en aval par la garde de non-degradation; celle-ci devenant
#: informative, il est attrape ici, **a la source**.
#:
#: **Ce n'est pas un jugement de couleur, et c'est ce qui autorise cette garde a rester
#: bloquante** quand les seuils de distorsion cessent de l'etre: elle ne dit pas si une
#: correction est bonne, elle dit si le systeme a une solution fiable. Meme categorie que
#: `FAILURE_UNDERDETERMINED_ADJUSTMENT`, dont elle emprunte le motif plutot que d'en
#: inventer un.
#:
#: **Ce seuil n'est plus la garantie structurelle** -- ca l'a ete jusqu'au 2026-08-14, et
#: ca ne resiste pas au rejoue. La deuxieme passe de revue (trois couches, chacune avec sa
#: propre mesure executee independamment) a constate que ce nombre est **libre entre 12 et
#: 1000** dans la suite actuelle -- aucun test n'encadre plus finement -- et que le
#: « plancher fautif » cite plus haut lors de la premiere derivation (104,8, feuille vierge
#: + bruit de scanner) ne se rejoue pas: le meme generateur, sur 40 a 300 tirages, rend un
#: minimum mesure de **77,7 a 79,5**, jamais 104,8. La derivation numerique publiee a la
#: premiere passe etait donc fausse, pas seulement optimiste, et la republier telle quelle
#: aurait ete la reproduire. Ce que ce module garantit desormais **par construction et non
#: par seuil** est porte par `design_matrix_rank_deficient` ci-dessous: un jeu de moins de
#: quatre mesures, ou dont les mesures sont lineairement dependantes (le cas exact de la
#: feuille vierge, mesures uniformes), n'a **mathematiquement** pas de solution unique,
#: quel que soit le conditionnement que `numpy.linalg.cond` en rapporte -- et cette
#: garde-la ne se regle pas, elle se verifie.
#:
#: Le nombre ci-dessous **reste un signal secondaire, informatif**: une page dont le
#: conditionnement franchit ce seuil sans etre rang-deficiente (un jeu pauvre, bande de
#: luminance etroite) est refusee par prudence, mais ce n'est plus la garantie que la
#: premiere redaction pretendait deriver. Valeur **conservee** au niveau ou elle a ete
#: posee -- 30 -- parce qu'elle reste tres au-dessus de tout jeu legitime mesure (pire cas
#: nul rejoue: 9,94) et tres en dessous de toute feuille vierge mesuree (rejoue: >= 1e3),
#: et qu'un mouvement du nombre sans nouvelle mesure serait la meme faute que celle
#: corrigee ici.
MAX_DESIGN_MATRIX_CONDITION_NUMBER = 30.0


def _design_matrix(measured_bgr) -> np.ndarray:
    """Matrice de conception `[mesures en lumiere lineaire | 1]`, N x 4.

    Factoree hors de `design_matrix_condition_number` et de
    `design_matrix_rank_deficient` (deuxieme passe de revue, `EPIC5-ARB-78`): les deux
    gardes -- la structurelle et la numerique -- doivent lire **exactement** la meme
    matrice, sans quoi l'une pourrait refuser un jeu que l'autre accepte pour une raison
    qui ne serait qu'un ecart d'implementation entre deux copies.

    La colonne de uns y est parce que les trois formes ajustent un terme constant (le
    decalage de `fit_stage_a`, l'ordonnee a l'origine de `fit_lab_lightness`, les ancrages
    de la courbe): sans elle, un jeu entierement uniforme paraitrait de rang 1 au lieu de
    l'etre reellement pour les systemes qu'on resout.
    """
    linear = eotf(np.atleast_2d(np.asarray(measured_bgr, dtype=np.float64)))
    return np.hstack([linear, np.ones((len(linear), 1), dtype=np.float64)])


def design_matrix_condition_number(measured_bgr) -> float:
    """Conditionnement de la matrice de conception d'un jeu d'ajustement.

    La matrice est `[mesures en lumiere lineaire | 1]`, N x 4, et non la matrice propre a
    l'une des trois formes: c'est **le meme jeu de mesures** qui alimente les trois, et
    une garde par forme dirait trois fois la meme chose avec trois nombres a maintenir.

    **Ne rend pas fiablement `inf` sur un jeu exactement degenere.** La premiere redaction
    de cette docstring l'affirmait; la deuxieme passe de revue du 2026-08-14 l'a mesure
    fausse -- sur la feuille vierge exacte (mesures uniformes, rang 1), `numpy.linalg.cond`
    rend `2,19e50`, un nombre fini de plus de cinquante ordres de grandeur, jamais `inf`.
    C'est un fait de virgule flottante (le calcul passe par une SVD dont la plus petite
    valeur singuliere n'est jamais tout a fait nulle) et non un bug de ce module: c'est
    justement pourquoi `ensure_design_matrix_conditioned` n'appuie plus sa garantie sur ce
    nombre seul, mais sur `design_matrix_rank_deficient`, verifiee **avant** lui.
    """
    return float(np.linalg.cond(_design_matrix(measured_bgr)))


def design_matrix_rank_deficient(measured_bgr) -> bool:
    """La matrice de conception a-t-elle mathematiquement une solution non unique ?

    Garde **structurelle**, ajoutee a la deuxieme passe de revue d'`EPIC5-ARB-78`
    (2026-08-14) parce que le seuil de conditionnement seul n'est fiable dans aucun des
    deux sens: un jeu a une ou deux lignes (rang deficient par cardinal) peut mesurer un
    conditionnement **sous** `MAX_DESIGN_MATRIX_CONDITION_NUMBER`, et un jeu legitime mais
    pauvre peut le depasser. Un rang insuffisant, lui, est un **fait d'algebre lineaire
    verifiable exactement** -- pas un jugement de couleur, pas un gout numerique -- donc
    coherent avec la philosophie d'`EPIC5-ARB-78`: aucun seuil de qualite a faire approuver
    par Egan.

    Deux conditions, l'une et l'autre suffisantes:

    * **moins de lignes que de colonnes** (`len(mesures) < 4`): le systeme est
      sous-determine par simple cardinal, quelles que soient les valeurs;
    * **rang de colonnes insuffisant** (`numpy.linalg.matrix_rank`, tolerance par SVD, donc
      robuste a l'arrondi qui empeche `design_matrix_condition_number` de rendre `inf`):
      c'est le cas exact de la feuille vierge -- ses mesures sont uniformes, donc les
      quatre colonnes de la matrice de conception sont des multiples scalaires les unes des
      autres, et le rang vaut 1 quel que soit le cardinal de lignes.
    """
    design = _design_matrix(measured_bgr)
    return len(design) < design.shape[1] or int(np.linalg.matrix_rank(design)) < design.shape[1]


def ensure_design_matrix_conditioned(measured_bgr, *, source_page_id: str) -> float:
    """Refuser un jeu d'ajustement dont le systeme n'a pas de solution fiable.

    Leve une `UnderdeterminedAdjustmentSet` -- donc une `ValueError`, donc
    `FAILURE_UNDERDETERMINED_ADJUSTMENT` chez les appelants qui la rattrapent. Le motif
    est **reutilise** et non invente: une feuille vierge est une variante de « pas de
    source utilisable », exactement ce que ce motif nomme deja, et Egan l'a tranche ainsi
    -- « sans page de calibration on accepte de scanner le lot mais sans correction
    puisqu'on n'a pas de source ». Le repli qui en resulte existe depuis 5.16/5.19: frames
    ecrites non corrigees, motif declare, aucun arret de la commande.

    **Deux gardes, dans cet ordre, et l'ordre porte un sens** (deuxieme passe de revue,
    `EPIC5-ARB-78`, 2026-08-14):

    1. `design_matrix_rank_deficient` -- **structurelle**, verifiee la premiere parce
       qu'elle est le fait le plus sur: un rang insuffisant n'a pas de solution unique,
       point final, et ce n'est vrai pour aucune valeur de seuil numerique;
    2. le conditionnement contre `MAX_DESIGN_MATRIX_CONDITION_NUMBER` -- **signal
       secondaire et informatif**, qui peut encore refuser un jeu pauvre mais non
       rang-deficient. Il ne pretend plus deriver une garantie que la premiere passe lui
       attribuait a tort: voir la docstring du seuil.

    Rend le conditionnement mesure quand les deux passent, plutot que `None`: un test qui
    verifie la frontiere lit la grandeur au lieu de la deviner
    (`test_le_seuil_de_conditionnement_porte_sa_valeur_et_sa_derivation`).
    **Corrige a la deuxieme passe de revue (2026-08-14)**: la redaction precedente
    promettait aussi qu'un appelant « qui voudra le publier n'aura pas a le recalculer »
    -- faux au moment ou c'etait ecrit, et toujours vrai aujourd'hui: les deux appelants
    (`fit_from_external_source`, `calibrate_page`) jettent la valeur de retour, et ce
    nombre n'atteint aucun artefact persistant. La promesse est retiree plutot que
    laissee a decouvrir a la prochaine lecture; publier le conditionnement au manifest
    reste possible mais ouvrirait une question de forme (ou, sous quel nom) qui n'est
    pas celle de ce correctif.
    """
    if design_matrix_rank_deficient(measured_bgr):
        raise UnderdeterminedAdjustmentSet(
            REFUSAL_DESIGN_MATRIX_ILL_CONDITIONED,
            f"le jeu d'ajustement de '{source_page_id}' a une matrice de conception dont "
            "le rang est insuffisant (moins de mesures que de parametres libres, ou "
            "mesures lineairement dependantes): le systeme n'a mathematiquement pas de "
            "solution unique, independamment de tout seuil de conditionnement "
            "(`EPIC5-ARB-78`). Le cas mesure est la page de calibration **vierge**: "
            "toutes ses mesures valent 1,0, `lstsq` y resout un systeme degenere sans "
            "lever, et la correction qui en sort est d'apparence normale, ajustee sur "
            "rien, et appliquee a toutes les planches du lot. Rescannez la page de "
            "calibration de ce lot -- ou verifiez qu'elle a bien ete imprimee.")
    condition = design_matrix_condition_number(measured_bgr)
    if not np.isfinite(condition) or condition > MAX_DESIGN_MATRIX_CONDITION_NUMBER:
        raise UnderdeterminedAdjustmentSet(
            REFUSAL_DESIGN_MATRIX_ILL_CONDITIONED,
            f"le jeu d'ajustement de '{source_page_id}' a une matrice de conception de "
            f"conditionnement {condition:.4g}, au-dela de "
            f"{MAX_DESIGN_MATRIX_CONDITION_NUMBER} (`EPIC5-ARB-78`) -- signal secondaire "
            "et informatif, un jeu pauvre plutot qu'un fait de rang. Rescannez la page de "
            "calibration de ce lot -- ou verifiez qu'elle a bien ete imprimee.")
    return condition


@dataclass(frozen=True)
class _ValeurDeJeuExterne:
    """Le couple `(value_id, rgb)` que `ensure_no_ink_floor_value_in_adjustment_set` lit.

    La garde travaille sur des **valeurs** et non sur des identifiants nus -- la clarte
    ne se lit pas dans un nom --, et un `ExternalAdjustmentSource` porte ses references
    en BGR normalise. Cette structure remet l'echelle a 8 bits sans dependre de la table
    du treillis: un jeu externe peut nommer des valeurs qui n'y sont pas, et le plancher
    d'encrage est un fait de clarte, pas d'appartenance a une table.

    Le champ s'appelle `rgb` parce que c'est le nom que la garde lit, et il recoit ici un
    triplet **BGR**. Ce n'est pas une negligence: le predicat de plancher lit le canal le
    plus clair, une statistique que l'ordre des trois canaux ne change pas.
    """

    value_id: str
    rgb: tuple[float, float, float]


def fit_from_external_source(source: ExternalAdjustmentSource, *,
                            correction_form_id: str = ACTIVE_CORRECTION_FORM_ID):
    """Ajuster la correction du **lot** sur la page de calibration.

    La forme se resout par identifiant (`CORRECTION_FORMS`) et non par ramification:
    ajouter une troisieme forme un jour ne doit pas rouvrir ce point.

    **Le defaut est la forme active** (story 5.21). Le chemin de production ne l'atteint
    pas -- `fit_lot_correction_from_page` passe toujours son propre `correction_form_id`
    --, mais la fonction est publique et directement appelable (bancs de recherche,
    tests), et son defaut doit s'accorder avec celui de `lattice_adjustment_source` pour
    la raison dite la-bas.

    **La politique de plancher du jeu est confrontee a celle de la forme**
    (`EPIC5-ARB-77`), et c'est ce qui garde cette fonction coherente avec
    `lattice_adjustment_source`: depuis que l'exclusion depend de la forme, un jeu
    filtre pour l'une et ajuste par l'autre est une correction ajustee sur un jeu que
    personne n'a voulu. Les deux sens sont fautifs et pour deux raisons differentes --
    le plancher absent prive la courbe de la mesure qui documente l'ecrasement des
    noirs, le plancher present demande a la forme affine de mapper deux references
    distinctes sur une meme mesure. Aucun des deux ne se voit dans le resultat: la
    correction sort plausible.

    **La garde de conditionnement est posee ici et nulle part ailleurs** (`EPIC5-ARB-78`),
    alors que l'arbitrage nomme les deux fonctions du couple. Motif: c'est le seul point
    par lequel *tout* ajustement sur une source externe passe -- la production enchaine
    `lattice_adjustment_source` puis cette fonction, et un appelant qui construit son
    `ExternalAdjustmentSource` a la main (la dataclasse est publique) n'a que celle-ci sur
    son chemin. La doubler en amont donnerait une seconde garde qu'aucune entree ne
    franchirait jamais la premiere, c'est-a-dire une garantie affichee sans domaine
    d'activation: le piege que ce module ferme partout ailleurs.
    """
    fit = get_correction_form(correction_form_id)
    attendu = correction_form_excludes_ink_floor(correction_form_id)
    if bool(source.ink_floor_excluded) != attendu:
        raise InkFloorPolicyMismatchError(
            f"le jeu d'ajustement de '{source.source_page_id}' a ete construit avec "
            f"ink_floor_excluded={bool(source.ink_floor_excluded)}, et "
            f"'{correction_form_id}' en exige {attendu} (`EPIC5-ARB-77`). Reconstruire "
            "le jeu pour cette forme -- `lattice_adjustment_source(..., "
            f"correction_form_id='{correction_form_id}')` -- plutot que de le "
            "transporter: l'ecart vaut 1,4 dE76 de residu et ne se voit pas au "
            "resultat.")
    # La politique declaree est confrontee au **contenu** du jeu, et pas seulement a
    # elle-meme (finding de revue de 5.20, ferme le 2026-08-19). Le desaccord ci-dessus
    # lit `source.ink_floor_excluded`, c'est-a-dire ce que le jeu **dit** de lui; ici on
    # lit ce qu'il **porte**. Un `ExternalAdjustmentSource` construit a la main -- la
    # dataclasse est publique, c'est le seul chemin qui ne passe par aucun filtre -- peut
    # declarer `ink_floor_excluded=True` et porter quand meme `lattice-008-008-008`:
    # mesure le 2026-08-19, ce jeu-la etait accepte et rendait un `CorrectionProfile`
    # d'apparence normale. C'est le domaine d'activation reel de la garde, celui que la
    # revue lui trouvait manquant: sur le chemin de production elle constate un filtre
    # deja passe, ici elle refuse une contradiction que rien d'autre ne voit.
    if attendu:
        # Les triplets partent en BGR et non remis en RGB, **et c'est sans effet**: le
        # predicat de plancher lit le canal le plus **clair**, donc l'ordre des trois ne
        # le change pas. Les remettre dans l'ordre donnerait une ligne de code dont
        # aucune mutation ne serait observable -- une garantie affichee sans domaine,
        # c'est-a-dire le defaut meme que ce bloc ferme.
        patch_values.ensure_no_ink_floor_value_in_adjustment_set(
            _ValeurDeJeuExterne(value_id, tuple(
                float(component) * 255.0 for component in triplet))
            for value_id, triplet in zip(source.value_ids,
                                         np.atleast_2d(np.asarray(
                                             source.reference_bgr,
                                             dtype=np.float64))))
    # **Apres** le desaccord de politique, et l'ordre porte un sens: le desaccord est une
    # faute de programmation (elle leve hors du vocabulaire de terrain), la degenerescence
    # est un fait de terrain (elle leve dedans). Diagnostiquer un bug de cablage comme une
    # feuille vierge enverrait rescanner une page qui n'a rien.
    ensure_design_matrix_conditioned(source.measured_bgr,
                                     source_page_id=source.source_page_id)
    return fit(source.measured_bgr, source.reference_bgr, source.neutral_mask)


# ---------------------------------------------------------------------------
# Story 5.19, AC 1 et 9 : la correction **du lot**, ajustee une seule fois
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LotCorrection:
    """La correction du lot et sa provenance, ou le motif pour lequel elle n'existe pas.

    **Une seule par lot** (AC 1 de la story 5.19): l'ajustement se fait sur la page de
    calibration et le resultat se transporte aux planches d'images. Un ajustement par
    planche serait le re-ajustement par page qu'`EPIC5-ARB-57` interdit, et ce type
    existe pour que la contrainte se lise dans la signature: un appelant qui voudrait
    re-ajuster devrait construire un second objet, ce qui se voit.

    `profile` vaut `None` quand la page de calibration est **illisible**, et c'est un cas
    de nature differente d'une page qui **diverge** (AC 9): l'un rend la correction du
    lot impossible -- il n'y a aucun profil a transporter --, l'autre concerne une seule
    planche et laisse les autres corrigees. Les deux ne partagent aucun motif: ceux d'ici
    viennent du vocabulaire ferme de l'AC 8 de 5.4b (`FAILURE_*`), celui-la est
    `FAILURE_PAGE_DIVERGES` et ne peut pas apparaitre ici.

    Les deux cardinaux sont ceux qu'`ExternalAdjustmentSource` porte, recopies ici pour
    qu'un echec les porte aussi: une page de calibration dont on ne sait pas combien de
    pastilles ont ete lues n'est pas diagnosticable, et c'est precisement le cas ou on
    relit (finding de la revue de 5.4a, applique a l'echelle du lot).
    """

    source_page_id: str
    template_id: str
    profile: AnyCorrectionProfile | None = None
    #: **Le seul defaut de transport du module qui bascule avec les points d'entree**
    #: (story 5.21), et il bascule parce qu'il est le seul qui soit **atteint en
    #: production**: `cli.py` construit ce type directement sur ses deux chemins d'echec
    #: amont -- page de calibration presente mais non redressable
    #: (`FAILURE_PAGE_GEOMETRY_UNRESOLVED`) et raster non relisable
    #: (`FAILURE_PATCHES_NOT_FOUND`) -- sans nommer de forme, parce qu'aucune n'a encore
    #: tourne a ce stade. Le laisser sur `CORRECTION_FORM_ID` ecrirait au manifest, via
    #: `calibration_page_result`, qu'un lot echoue sous la forme affine alors que la
    #: forme demandee par la commande `scan` etait la forme active: un enregistrement
    #: faux sur precisement les lots qu'on relit. Le champ repond a « sous quelle forme
    #: ce lot devait etre corrige », pas a « quelle forme a produit ce profil ».
    #:
    #: Le champ homologue de `PageCalibration` ne bascule **pas**, et l'asymetrie se
    #: verifie: ses trois constructions de production (`_failed`, `calibrate_page`,
    #: `calibration_page_result`) passent toutes la valeur effective, donc son defaut
    #: n'est atteint que par une construction directe.
    correction_form_id: str = ACTIVE_CORRECTION_FORM_ID
    read_patch_count: int = 0
    retained_patch_count: int = 0
    failure_reason: str | None = None
    failure_message: str | None = None
    #: Ce que la correction du lot deforme, mesure sur la page qui l'a produite
    #: (`EPIC5-ARB-78`). `None` quand aucune correction n'a ete ajustee -- il n'y a alors
    #: rien a mesurer, ce qui n'est pas la meme chose qu'une distorsion nulle. Le champ
    #: existe pour que la mesure atteigne le manifest: depuis que le budget de distorsion
    #: n'y refuse plus rien, ne pas la publier reviendrait a ne pas la faire.
    acceptance: AcceptanceVerdict | None = None
    #: L'operateur a-t-il demande que la correction soit appliquee (`--cc off`,
    #: `EPIC5-ARB-78`) ? **Ajoute a la deuxieme passe de revue** (2026-08-14): ce choix
    #: est une decision de **lot**, connue avant meme que la page de calibration ne soit
    #: lue, et il vit desormais ici plutot que sur un parametre separe de
    #: `calibration_page_result`. Avant ce champ, le meme fait etait porte deux fois --
    #: une fois ici implicitement (par la construction de l'appelant), une fois par un
    #: parametre `correction_applied` passe a cote --, et un appelant qui oublierait de
    #: le transmettre explicitement heritait silencieusement du defaut `True`. Une seule
    #: verite, portee par l'objet qui represente le lot, independamment de l'issue de la
    #: page de calibration elle-meme (illisible, degeneree ou lue avec succes).
    correction_requested: bool = True
    #: **D'ou vient cette correction de lot** (bloquant `C3` de la revue de 5.22). Le
    #: champ existe parce que `calibration_page_result` ecrivait `own_sheet_patches` en
    #: **litteral**: quand le profil de chaine gagne et que la feuille de calibration est
    #: restee dans la pile scannee, son entree de manifest declarait « la correction vient
    #: des pastilles de cette feuille » alors qu'aucun de ses pixels n'avait ete lu. La
    #: provenance des planches disait `chain_profile`, celle de la page de calibration du
    #: meme lot disait `own_sheet_patches`, et les deux decrivaient la meme passe -- deux
    #: verites, exactement ce que le reste du module refuse.
    #:
    #: Le defaut reste `own_sheet_patches`: c'est litteralement vrai de toute correction
    #: construite par `fit_lot_correction_from_page`, donc tout appelant d'avant 5.22
    #: garde son comportement au champ pres.
    correction_source: str = CORRECTION_SOURCE_OWN_SHEET
    #: La chaine dont le profil a fourni la correction, `None` dans le regime de repli.
    #: **Distinct de `source_page_id`**, meme partage que sur `PageCalibration`: celui-ci
    #: designe le fichier `versions/calibration/<chain_id>.json`, celui-la la feuille
    #: physique qui a ajuste les coefficients.
    chain_id: str | None = None
    #: **Le verdict d'acceptation relu du fichier de profil** (bloquant `C2` de la revue
    #: de 5.22), distinct d'`acceptance` juste au-dessus et jamais confondu avec lui:
    #: `acceptance` est ce que **cette** passe a mesure, celui-ci ce que la passe de
    #: calibration avait mesure, un autre jour, sur une autre feuille. Les republier sous
    #: la meme cle attribuerait a ce scan une mesure qu'il n'a pas faite.
    #:
    #: Il existe parce que la mesure etait serialisee par `_acceptance_document` et
    #: **relue par personne**: douze grandeurs ecrites dans un fichier que rien
    #: n'ouvrait, ce qui defait `EPIC5-ARB-78` par construction -- « depuis que le budget
    #: de distorsion ne refuse plus rien, ne pas publier une mesure revient a ne pas la
    #: faire ».
    imported_acceptance: AcceptanceVerdict | None = None
    #: **Les pastilles temoins de la page de calibration, mesurees BRUTES** (story 5.23,
    #: AC 2). Portees en suite de couples et non en dictionnaire: `LotCorrection` est
    #: `frozen`, et une suite triee par identifiant rend l'ordre d'iteration independant
    #: de la graine de hachage du processus -- meme regle que
    #: `RawDivergenceMeasure.paired_value_ids`.
    #:
    #: Vide -- et non `None` -- dans les trois regimes ou la mesure n'existe pas: profil
    #: de chaine reutilise (la feuille de calibration n'est pas dans ce scan), page de
    #: calibration illisible, ou bandeau non imprime parce que la feuille est anterieure
    #: a la story 5.23. Un vide se lit « pas de mesure », jamais « ecart nul ».
    witness_raw_bgr: tuple[tuple[str, tuple[float, float, float]], ...] = ()
    #: **Pourquoi le bandeau n'a rien rendu, quand il n'a rien rendu** (`EPIC5-ARB-104`).
    #: Chaine vide = le bandeau a ete mesure (ou la question ne s'est pas posee: profil de
    #: chaine reutilise, aucune feuille dans cette passe); sinon, l'un des motifs de
    #: `RAW_DIVERGENCE_BAND_REASONS`.
    #:
    #: Le champ existe parce qu'un `witness_raw_bgr` vide portait **cinq** regimes
    #: physiquement distincts sous une seule valeur, dont deux rendaient le manifest faux:
    #: un bandeau imprime puis rogne au redressage etait declare « papier nu ». Le vide dit
    #: « pas de mesure », il ne dit pas **laquelle** des cinq raisons -- et l'appelant ne
    #: pouvait pas la deviner, donc il ne pouvait que se tromper.
    witness_band_reason: str = ""

    def witness_raw_mapping(self) -> dict:
        """Les temoins bruts sous la forme que `raw_divergence_de76` consomme."""
        return {value_id: triplet for value_id, triplet in self.witness_raw_bgr}

    @property
    def available(self) -> bool:
        """Y a-t-il une correction a transporter ? Jamais deduit d'un motif absent."""
        return self.profile is not None


#: Ce que l'operateur lit quand la page de calibration du lot n'est pas exploitable.
#:
#: **Aucun mot de divergence n'y figure, et c'est l'AC 9** (frontiere negative verifiee
#: par test): les deux cas se ressemblent a la lecture -- « la couleur n'a pas ete
#: appliquee » -- et se traitent de facon opposee. Une page de calibration illisible se
#: rescanne pour recuperer **tout** le lot; une planche deviante se rescanne pour
#: recuperer **cette feuille**. Confondre les deux motifs enverrait l'operateur
#: rescanner la mauvaise feuille.
_CALIBRATION_PAGE_UNREADABLE_TEMPLATE = (
    "Page de calibration '{page}' inexploitable ({motif}): aucune correction de lot "
    "n'a pu etre ajustee, donc les planches de ce lot sont ecrites **non corrigees** "
    "et le declarent. Le lot reste exploitable tel quel; pour obtenir la correction, "
    "rescannez la page de calibration de ce lot."
)


def fit_lot_correction_from_page(rectified_page, *, template_id: str, dpi: int,
                                 source_page_id: str,
                                 correction_form_id: str = ACTIVE_CORRECTION_FORM_ID,
                                 correction_requested: bool = True,
                                 patch_preset_id: str | None = None,
                                 ) -> LotCorrection:
    """Ajuster la correction du lot sur le raster **redresse** de sa page de calibration.

    C'est le point d'entree que la story 5.16 avait laisse sans appelant: elle a livre
    `lattice_adjustment_source` et `fit_from_external_source`, et rien ne les appelait
    depuis la production. Cette fonction les enchaine et **ajoute les gardes** que
    `calibrate_page` porte pour une planche d'images, parce que la page de calibration
    est lue par un autre chemin et ne beneficiait donc d'aucune d'entre elles.

    **Pourquoi ce n'est pas `calibrate_page`**, et c'est la seule divergence assumee
    avec la lettre de l'AC 1 de la story: `calibrate_page` resout ses positions par
    `patch_presets.resolve_patch_layout(template_id, patch_preset_id)`, c'est-a-dire le
    placement des pastilles d'une **planche d'images**. Une page de calibration ne porte
    pas ces pastilles: elle porte le **treillis**, place par
    `resolve_calibration_page_patches(template_id)` et derive du **role** et non d'un
    preset (`patch_preset_id` est un champ de niveau lot, donc une page ne peut pas
    declarer le sien). Appeler `calibrate_page` sur ce raster echantillonnerait des
    positions ou il n'y a rien de ce qu'elle croit lire -- soit un refus
    `patches_not_found` sur une page parfaitement lisible, soit, pire, une correction
    **plausible** ajustee sur des morceaux de treillis pris pour des pastilles de
    planche. L'esprit de l'AC est tenu -- l'ajustement a lieu **une seule fois par lot**,
    sur la page de calibration --, sa lettre ne peut pas l'etre.

    Les motifs d'echec sont ceux du vocabulaire ferme de l'AC 8 de 5.4b, jamais un code
    nouveau: la cause est exactement la meme (dpi absurde, placement indefini, pastilles
    introuvables, mesures implausibles, jeu sous-determine), seule la page change.

    Deux gardes que cette fonction **ne** porte pas, dites franchement plutot que
    laissees a deviner:

    * `UnknownLatticeValueError` n'est pas rattrapee: les identifiants viennent du
      treillis resolu quelques lignes plus haut, donc le cas n'est pas atteignable
      depuis ici. Une garde qu'aucune entree ne franchit n'est pas une garantie, c'est
      un des quatre pieges nommes du 2026-08-12;
    * il n'y a **aucune garde de dispersion**. Elle porterait sur les repliques du
      treillis, et le refus qu'elle produirait porterait sur le **lot entier** -- alors
      que la dispersion est le symptome d'un scan bruyant, que la correction rattrape en
      partie. Le regime deviant se juge planche par planche, par la garde de divergence.

    La correction rendue est **mesuree** avant d'etre rendue disponible, et sa mesure
    voyage avec elle (`acceptance`). Elle ne la refuse plus depuis `EPIC5-ARB-78`: voir la
    fin de fonction, le regime qui l'avait rendue necessaire, et la garde de
    conditionnement qui l'a remplacee a la source.
    """
    from . import page_templates, patch_presets

    def _echec(reason: str) -> LotCorrection:
        return LotCorrection(
            source_page_id=source_page_id, template_id=template_id,
            correction_form_id=correction_form_id, failure_reason=reason,
            failure_message=_CALIBRATION_PAGE_UNREADABLE_TEMPLATE.format(
                page=source_page_id, motif=reason),
            correction_requested=correction_requested)

    # `dpi` d'abord, comme dans `calibrate_page` et pour la meme raison: il gouverne
    # toutes les conversions en pixels, donc un dpi invalide rend fausse toute mesure
    # suivante au lieu de lever.
    if not is_strict_int(dpi) or dpi <= 0:
        return _echec(FAILURE_INVALID_DPI)
    # Le cardinal de canaux se pese avant toute mesure, et pour la meme raison que le
    # `dpi`: passe cette ligne, une page qui n'est pas BGR rend des mesures fausses au
    # lieu de lever. Le regime est licite en amont -- un scan monochrome traverse
    # l'ingestion -- donc c'est un refus motive, pas une faute de programmation.
    if not page_has_three_channels(rectified_page):
        return _echec(FAILURE_NOT_THREE_CHANNELS)
    # La forme est resolue tot et **leve**: ici l'identifiant est un argument de
    # l'appelant, pas une donnee du terrain, donc une valeur inconnue est une faute de
    # programmation -- meme asymetrie que le regime local de `calibrate_page`.
    get_correction_form(correction_form_id)
    try:
        patches = patch_presets.resolve_calibration_page_patches(template_id)
    except (patch_presets.UndefinedPlacementError,
            page_templates.UnknownTemplateError):
        return _echec(FAILURE_PLACEMENT_UNDEFINED)

    measured, ids = sample_patches(rectified_page, patches, dpi)
    if len(measured) < len(patches):
        # Une pastille dont le carre echantillonne tombe hors de la page est omise par
        # `sample_patches`: sur une page de calibration, cela veut dire que le redressage
        # a rate ou que la feuille est rognee. Ajuster la correction du lot sur le
        # sous-ensemble qui reste serait ajuster sur un jeu que la page ne declare pas.
        return _echec(FAILURE_PATCHES_NOT_FOUND)
    low, high = PLAUSIBLE_RANGE
    if measured.min() < low or measured.max() > high:
        # Meme role que sur une planche: attraper une erreur de **geometrie**, pas juger
        # une couleur. Le treillis est borne loin des extremes par construction -- ses
        # niveaux vont de 8 a 245 en codes 8 bits --, donc la garde a un sens sur toutes
        # ses pastilles et non sur un sous-ensemble.
        #
        # **Les deux bornes n'ont pas le meme domaine d'activation, et le dire est le
        # correctif** (finding `m1` de la revue de 5.19): `sample_patches` normalise ses
        # mesures en divisant par `255` ou `65535`, donc `measured.max() > 1.0` est
        # **inatteignable** tant que cette normalisation tient -- une pastille saturee
        # rend exactement `1.0`. Seule la borne basse peut mordre ici. La moitie haute est
        # conservee parce qu'elle est la moitie d'un invariant qu'un changement de
        # normalisation casserait en silence, mais elle n'est pas une garantie: la
        # presenter comme telle serait la huitieme occurrence de « une garde annoncee sans
        # son domaine d'activation ». Les deux bouts sont epingles par
        # `test_les_deux_bornes_de_plausibilite_du_treillis_ont_des_domaines_distincts`.
        return _echec(FAILURE_PATCHES_OUT_OF_RANGE)

    # **Le meme `correction_form_id` gouverne les deux appels**, et c'est ce qui rend
    # l'incoherence de politique de plancher inatteignable depuis la production
    # (`EPIC5-ARB-77`): le jeu est filtre pour la forme qui l'ajustera, jamais pour une
    # autre. La garde de `fit_from_external_source` ne mord donc que sur un appelant qui
    # enchaine les deux a la main -- son domaine reel, nomme plutot que suppose.
    source = lattice_adjustment_source(measured, ids, source_page_id=source_page_id,
                                       correction_form_id=correction_form_id)
    try:
        profile = fit_from_external_source(source,
                                          correction_form_id=correction_form_id)
    except UnderdeterminedAdjustmentSet as erreur:
        # **Le message specifique de la garde levee n'est plus ecrase par le gabarit
        # generique** (deuxieme passe de revue, `EPIC5-ARB-78`, 2026-08-14). Le motif reste
        # `FAILURE_UNDERDETERMINED_ADJUSTMENT` -- vocabulaire ferme de l'AC 8, inchange --
        # mais le message est celui de l'exception elle-meme: pour la garde de
        # conditionnement/rang, il dit « verifiez qu'elle a bien ete imprimee », une action
        # qui a un sens sur une feuille vierge, la ou `_CALIBRATION_PAGE_UNREADABLE_TEMPLATE`
        # ne proposait que « rescannez la page » -- un geste qui ne peut rien changer sur
        # une page qui n'a jamais rien porte.
        return LotCorrection(
            source_page_id=source_page_id, template_id=template_id,
            correction_form_id=correction_form_id,
            failure_reason=FAILURE_UNDERDETERMINED_ADJUSTMENT,
            failure_message=str(erreur),
            correction_requested=correction_requested)
    except ValueError:
        # Sous-determination du jeu d'ajustement d'une autre nature que celles typees
        # `UnderdeterminedAdjustmentSet` ci-dessus (aucune connue aujourd'hui sur ce
        # chemin, mais le vocabulaire d'echec reste ferme sur toute `ValueError`): meme
        # motif, message generique faute de detail actionnable de plus.
        return _echec(FAILURE_UNDERDETERMINED_ADJUSTMENT)

    # **La correction du lot est mesuree sur la page qui l'a produite, et cette mesure est
    # publiee** -- elle ne refuse plus rien (`EPIC5-ARB-78`). Ce qu'elle refusait est
    # nomme franchement, parce que c'est le seul endroit du depot ou le regime avait ete
    # mesure: une page de calibration **blanche** -- feuille vierge posee au scanner,
    # treillis non imprime -- passe toutes les gardes geometriques. Ses 130 mesures valent
    # 1,0, donc elles sont dans les bornes de plausibilite (dont la borne haute *est*
    # 1,0), le jeu porte bien deux neutres distincts au sens des identifiants, et `lstsq`
    # rend une matrice sur un systeme degenere **sans lever**. Le resultat etait un
    # `LotCorrection` disponible, d'apparence normale, ajuste sur rien -- et il aurait ete
    # applique aux pixels de **toutes** les planches du lot.
    #
    # Ce regime est desormais attrape **plus haut et a la source**, par la garde de
    # conditionnement de `fit_from_external_source`: le `except ValueError` ci-dessus l'a
    # deja traduit en `FAILURE_UNDERDETERMINED_ADJUSTMENT`, donc le flux n'arrive ici
    # qu'avec un systeme resoluble. Le remplacement n'est pas de commodite: l'ancienne
    # garde jugeait une **couleur** (de combien la correction degrade), la nouvelle juge
    # un **calcul** (le systeme a-t-il une solution fiable), et c'est la seule des deux
    # categories qu'`EPIC5-ARB-78` laisse bloquer.
    #
    # La mesure, elle, reste faite et voyage jusqu'au manifest par `calibration_page_result`:
    # une page de calibration qui produit la correction de tout un lot est precisement
    # celle dont on veut lire ce que sa correction deforme.
    corrected = oetf(np.clip(profile.apply_linear(eotf(source.measured_bgr)), 0.0, 1.0))
    acceptance = evaluate_acceptance(
        source.measured_bgr, corrected, source.reference_bgr,
        value_ids=source.value_ids)
    # **Le motif voyage avec la mesure** (`EPIC5-ARB-104`): les deux sortent ensemble de
    # l'echantillonnage et sont portees ensemble par la correction du lot. Prendre les
    # temoins et jeter le motif est exactement ce qui rendait le manifest faux -- un
    # bandeau imprime puis rogne s'y declarait « papier nu ».
    temoins_bruts, motif_bandeau = _sample_calibration_witness_band(
        rectified_page, template_id=template_id,
        patch_preset_id=patch_preset_id, dpi=dpi)
    return LotCorrection(
        source_page_id=source_page_id, template_id=template_id, profile=profile,
        correction_form_id=correction_form_id,
        read_patch_count=source.read_patch_count,
        retained_patch_count=source.retained_patch_count,
        correction_requested=correction_requested,
        acceptance=acceptance,
        witness_raw_bgr=temoins_bruts,
        witness_band_reason=motif_bandeau)


def _sample_calibration_witness_band(
        rectified_page, *, template_id: str, patch_preset_id: str | None, dpi: int
) -> tuple[tuple[tuple[str, tuple[float, float, float]], ...], str]:
    """Mesurer **brut** le bandeau de temoins de la page de calibration. Story 5.23.

    C'est la moitie manquante de la mesure brute a brute: la planche d'images echantillonne
    deja ses temoins dans `calibrate_page`, la page de calibration ne les echantillonnait
    pas du tout -- son chemin de lecture ne connaissait que le treillis.

    **Elle ne peut pas faire echouer le lot, et c'est une decision et non une prudence.**
    La correction du lot s'ajuste sur le **treillis**; le bandeau ne sert qu'a repondre a
    « ces deux feuilles se comportent-elles pareil ? ». Un bandeau illisible, absent du
    tirage ou pose sur un gabarit qui ne sait pas le placer doit donc coûter la **mesure**
    de divergence, jamais la correction -- sans quoi la story qui existe pour cesser de
    refuser une correction en introduirait un nouveau motif de refus.

    **Elle rend `(temoins, motif)`, et c'est `EPIC5-ARB-104`.** Elle rendait les seuls
    temoins, donc **cinq** regimes physiquement distincts sortaient sous la meme valeur --
    un tuple vide -- alors que ce docstring prenait deja soin de les nommer un a un. Le
    nom ne voyageait pas avec la mesure, si bien que l'appelant ne pouvait pas les
    distinguer et se rabattait sur le plus frequent. Deux d'entre eux rendaient le
    manifest **faux**: un bandeau imprime puis rogne au redressage, et une feuille dont le
    preset est mal orthographie, y etaient declares `raw_divergence_witness_band_not_printed`,
    c'est-a-dire « papier nu », la ou il y a de l'encre. Le motif est vide **si et
    seulement si** des temoins sont rendus; sinon il porte l'un des cinq noms:

    * `patch_preset_id` absent -- l'appelant n'a pas su dire quel preset le lot declare
      (`RAW_DIVERGENCE_BAND_NO_PRESET`);
    * **la feuille declare un preset anterieur au bandeau** sur la page de calibration
      (`patch_presets.calibration_page_carries_witness_band`,
      `RAW_DIVERGENCE_BAND_NOT_PRINTED`). C'est le regime qui compte
      en pratique: toutes les pages de calibration qui existent aujourd'hui, celle du lot
      de reference `chendj-mat` comprise, ont ete imprimees avant la story 5.23 et leurs
      colonnes laterales sont du **papier nu**. Les echantillonner rend 58,72 et 59,05
      dE76 d'ecart brut a brut -- mesure du 2026-08-17 --, c'est-a-dire la distance entre
      des pastilles imprimees et du papier blanc: un avertissement chiffre, permanent, et
      vrai de rien;
    * **le preset declare est inconnu du registre** -- une faute de frappe
      (`UnknownPatchPresetError`, `RAW_DIVERGENCE_BAND_PRESET_UNKNOWN`). C'est
      precisement ce que la garde de `calibration_page_carries_witness_band` leve
      **expres**, et que cet appelant confondait avec « ce preset n'a pas de bandeau »:
      le seul appelant de production annulait donc le service que la garde rend, et
      l'asymetrie etait entiere -- cote planche d'images le meme preset inconnu donne
      `FAILURE_PLACEMENT_UNDEFINED`, cote page de calibration c'etait le silence;
    * le gabarit ne sait pas poser le bandeau sur une page de calibration
      (`UndefinedPlacementError`, `UnknownTemplateError`,
      `RAW_DIVERGENCE_BAND_PLACEMENT_UNDEFINED`);
    * le bandeau lu est **ampute** -- une pastille au moins tombe hors de la page
      (`RAW_DIVERGENCE_BAND_CROPPED`).

    Les cinq motifs sont ceux du **vocabulaire de divergence** et pas un second jeu de
    noms traduit ensuite: deux vocabulaires apparies par une table divergent au premier
    ajout, et le symptome serait un manifest qui nomme un regime avec le mot d'un autre.
    """
    from . import page_templates, patch_presets

    if not patch_preset_id:
        return (), RAW_DIVERGENCE_BAND_NO_PRESET
    try:
        if not patch_presets.calibration_page_carries_witness_band(patch_preset_id):
            return (), RAW_DIVERGENCE_BAND_NOT_PRINTED
        band = patch_presets.resolve_calibration_page_witnesses(
            template_id, patch_preset_id)
    except patch_presets.UnknownPatchPresetError:
        # **Nomme, plus avale.** Cette exception est levee volontairement par la garde de
        # `calibration_page_carries_witness_band`; la ranger avec les deux suivantes
        # revenait a la lever pour rien.
        return (), RAW_DIVERGENCE_BAND_PRESET_UNKNOWN
    except (patch_presets.UndefinedPlacementError,
            page_templates.UnknownTemplateError):
        return (), RAW_DIVERGENCE_BAND_PLACEMENT_UNDEFINED
    measured, ids = sample_patches(rectified_page, band, dpi)
    if len(measured) < len(band):
        # Une pastille du bandeau tombee hors page: le redressage a rate ou la feuille est
        # rognee. On ne mesure pas une divergence sur un bandeau ampute -- c'est le meme
        # refus de sous-ensemble silencieux que le treillis oppose deja au-dessus, sauf
        # qu'ici il ne coute que la mesure. **Le motif dit qu'il y avait de l'encre**: le
        # confondre avec « bandeau non imprime » etait la faussete la plus couteuse des
        # cinq, l'operateur lisant « papier nu » d'une feuille qu'il a imprimee.
        return (), RAW_DIVERGENCE_BAND_CROPPED
    mapping = witness_raw_mapping(measured, ids)
    return (tuple((value_id, mapping[value_id]) for value_id in sorted(mapping)), "")


# ---------------------------------------------------------------------------
# Story 5.22, AC 1 et 2 : le format de profil de chaine (serialisation)
# ---------------------------------------------------------------------------
#
# La persistance vit dans `io/calibration_profile` **pur** (listes de nombres,
# json canonique, ecriture atomique); les deux fonctions ci-dessous sont la
# moitie **couleur** du couple: elles convertissent l'objet numpy en document
# et le document en objet. Une seule source de verite (`Dev Notes 4`): les
# coefficients vivent dans le fichier de profil, le manifest porte la
# **provenance**, jamais les coefficients.


def _acceptance_document(acceptance: AcceptanceVerdict | None) -> dict:
    """Projection plate d'un verdict d'acceptation pour le fichier de profil.

    C'est la **mesure** (Dev Notes, tache 1), pas une decision: elle dit a
    quel point la page de calibration qui a produit le profil a ete ajustee.
    Seule la partie plate du verdict y entre -- `detail` (la signature
    d'`EPIC5-ARB-28`, par valeur) resterait un miroir du registre et ne se
    relit pas: le fichier est autoportant, pas une copie du manifest.
    """
    if acceptance is None:
        return {}
    return {
        "status": acceptance.status,
        "acceptance_id": acceptance.acceptance_id,
        "mean_delta_e": float(acceptance.mean_delta_e),
        "max_delta_e": float(acceptance.max_delta_e),
        "mean_delta_e_before": float(acceptance.mean_delta_e_before),
        "distortion_budget_id": acceptance.distortion_budget_id,
        "mean_degradation_de76": float(acceptance.mean_degradation_de76),
        "max_neutral_degradation_de76": (
            None if acceptance.max_neutral_degradation_de76 is None
            else float(acceptance.max_neutral_degradation_de76)),
        "max_degradation_de76": (
            None if acceptance.max_degradation_de76 is None
            else float(acceptance.max_degradation_de76)),
        "distortion_budget_met": acceptance.distortion_budget_met,
        "neutral_axis_channel_spread_8bit": (
            None if acceptance.neutral_axis_channel_spread_8bit is None
            else float(acceptance.neutral_axis_channel_spread_8bit)),
    }


def acceptance_from_document(document: dict | None) -> AcceptanceVerdict | None:
    """Relire le verdict d'acceptation consigne dans un fichier de profil.

    **L'inverse de `_acceptance_document`, et la raison d'etre de la fonction est qu'il
    n'en existait aucun** (bloquant `C2` de la revue de 5.22): `profile_to_document`
    ecrivait douze grandeurs sous la cle `acceptance`, et un `grep '"acceptance"'` sur
    `src/` ne rendait que cette ecriture -- aucun lecteur. Or le regime que la story
    installe est celui ou le lot est corrige par un **profil de chaine**, donc celui ou
    la page de calibration n'est plus dans le scan: sans relecture, la seule mesure de ce
    que la correction deforme cessait d'atteindre le manifest le jour ou ce regime est
    devenu nominal. Un champ ecrit que personne ne relit est du code mort; celui-ci
    devient un champ **lu**, ce qui est l'autre issue possible et la seule qui preserve
    `EPIC5-ARB-78`.

    Ce qui est rendu est **plat**: `detail` (la signature d'`EPIC5-ARB-28`, par valeur)
    n'est pas serialise et ne se devine pas, donc il reste `None`. C'est deliberement
    visible plutot que reconstruit: un `PageAcceptanceResult` fabrique de toutes pieces
    ferait croire a des mesures par pastille qui n'ont jamais ete relues.

    Un document **vide** (`{}`, ce qu'ecrit `_acceptance_document(None)`) rend `None` et
    non un verdict a zero: « aucune mesure » et « une mesure nulle » sont deux faits
    differents, et c'est la regle que tout ce module tient sur `replicate_dispersion` et
    sur `neutral_axis_channel_spread_8bit`.
    """
    if not document:
        return None
    return AcceptanceVerdict(
        status=document["status"],
        mean_delta_e=float(document["mean_delta_e"]),
        max_delta_e=float(document["max_delta_e"]),
        mean_delta_e_before=float(document["mean_delta_e_before"]),
        acceptance_id=document["acceptance_id"],
        distortion_budget_id=document["distortion_budget_id"],
        mean_degradation_de76=float(document["mean_degradation_de76"]),
        max_neutral_degradation_de76=_optional_float(
            document["max_neutral_degradation_de76"]),
        max_degradation_de76=_optional_float(document["max_degradation_de76"]),
        distortion_budget_met=document["distortion_budget_met"],
        neutral_axis_channel_spread_8bit=_optional_float(
            document["neutral_axis_channel_spread_8bit"]),
        # `detail` reste `None`: voir la docstring. Le verdict relu porte ce que le
        # fichier porte, jamais davantage.
        detail=None,
    )


def _optional_float(valeur) -> float | None:
    """`None` reste `None`, tout le reste devient un flottant. Jamais `float(None)`."""
    return None if valeur is None else float(valeur)


def profile_to_document(profile: AnyCorrectionProfile, *, chain_id: str,
                        source_page_id: str, template_id: str,
                        read_patch_count: int, retained_patch_count: int,
                        ink_floor_excluded: bool,
                        acceptance: AcceptanceVerdict | None = None,
                        witness_raw_bgr=(), witness_band_reason: str = "",
                        label: str = "", comment: str = "",
                        scan_dir: str = "") -> dict:
    """Le document de profil (lists de nombres) depuis un profil ajuste.

    C'est ce que `scan calibrate` consigne dans le projet (`AC 1`, `AC 2`):
    le profil porte tout ce qu'une relecture a besoin -- identite de chaine,
    forme, coefficients en ordre **BGR** documente, cardinaux du jeu, politique
    de plancher d'encrage et provenance -- sans rien attendre du manifest.

    `correction_form_id` est lu **sur le profil**, jamais deduit: un profil
    construit sous une forme l'ecrit sous la sienne, et le manifest porterait
    sinon une forme devinee.

    **`witness_raw_bgr` est ce qui rend le profil autoportant pour la divergence brute a
    brute** (story 5.23, mesure du 2026-08-18). Ce sont les mesures **sans aucune
    correction** des pastilles temoins de la page de calibration, appariables par
    identifiant avec celles d'une planche scannee des mois plus tard. Sans elles, la
    comparaison d'`EPIC5-ARB-82` n'etait calculable que si les deux feuilles se
    trouvaient dans la **meme passe de scan** -- c'est-a-dire jamais dans le regime
    nominal de la calibration par chaine, et c'est ce que le manifeste du 2026-08-18 a
    montre en rendant `raw_divergence_no_calibration_sheet` sur une chaine pourtant
    calibree.

    `label` et `comment` sont ce que **l'operateur** a nomme (AC 8quater): une
    etiquette qui donnera le nom du fichier, et un commentaire libre destine au survol
    dans la GUI. Ils s'ajoutent, ils ne remplacent rien -- le document garde son
    `chain_id`, sa forme, ses coefficients, ses cardinaux et ses temoins.

    Le champ est **absent** du document quand rien n'a ete mesure -- page de calibration
    sans bandeau (`patches-14-v3`), bandeau ampute, gabarit qui ne sait pas le poser --
    et jamais present-mais-vide: `io/calibration_profile` refuse la liste vide, parce que
    « pas mesure » et « mesure, rien trouve » ne s'ecrivent pas pareil au manifeste.

    **`witness_band_reason` dit laquelle de ces trois facons** (`EPIC5-ARB-104`), et c'est
    ce qui ferme le second etage du defaut ci-dessus. Sans lui, le document omettait le
    bloc vide, la relecture rendait une suite vide, et la chaine ressortait
    `raw_divergence_no_calibration_sheet` -- « aucune feuille de calibration dans ce
    scan » -- d'une page qui **a bien ete lue** et dont la correction vient d'elle: le
    fichier persistait la faussete, a chaque scan suivant et pour toujours.

    Il suit **le meme patron** que les temoins et pas un second: ecrit seulement s'il porte
    un motif, jamais present-mais-vide -- `io/calibration_profile` refuse la chaine vide
    pour la raison qui lui fait refuser la liste vide, « un motif, mais lequel » n'etant pas
    un fait. Un profil dont le bandeau a ete mesure n'a donc ni l'un ni l'autre a dire, et
    son document est exactement celui d'avant cette story.
    """
    coefficients: dict = {}
    if isinstance(profile, CorrectionProfile):
        coefficients = {
            "stage_a": [[float(v) for v in row] for row in profile.stage_a],
            "stage_m": [[float(v) for v in row] for row in profile.stage_m],
        }
    elif isinstance(profile, LabCorrectionProfile):
        coefficients = {
            "lightness_slope": float(profile.lightness_slope),
            "lightness_offset": float(profile.lightness_offset),
            "chroma_matrix": [
                [float(v) for v in row] for row in profile.chroma_matrix],
            "chroma_offset": [float(v) for v in profile.chroma_offset],
        }
    elif isinstance(profile, ToneCurveCorrectionProfile):
        coefficients = {
            "tone_anchors_in": [
                [float(v) for v in row] for row in profile.tone_anchors_in],
            "tone_anchors_out": [float(v) for v in profile.tone_anchors_out],
            "chroma_matrix": [
                [float(v) for v in row] for row in profile.chroma_matrix],
        }
    else:
        raise UnknownCorrectionFormError(
            f"Profil d'une forme non serialisable: {getattr(profile, 'correction_id', '?')!r}. "
            "`profile_to_document` connait les trois formes enregistrees; une "
            "forme nouvelle doit l'etendre explicitement, jamais etre devinee.")
    document = {
        "schema_version": calibration_profile.PROFILE_SCHEMA_VERSION,
        "chain_id": chain_id,
        "correction_form_id": profile.correction_id,
        "coefficients": coefficients,
        "read_patch_count": read_patch_count,
        "retained_patch_count": retained_patch_count,
        "ink_floor_excluded": ink_floor_excluded,
        "source_page_id": source_page_id,
        "template_id": template_id,
        "acceptance": _acceptance_document(acceptance),
    }
    temoins = calibration_profile.witness_raw_to_document(witness_raw_bgr)
    if temoins:
        document[calibration_profile.WITNESS_RAW_FIELD] = temoins
    # Le motif, **et jamais la chaine vide**: la garde du module de persistance la refuse,
    # et elle a raison de le faire -- l'absence du champ dit deja « rien a signaler ».
    # Les deux champs sont donc exclusifs en pratique sans que rien n'ait a l'imposer: une
    # mesure reussie ne porte pas de motif, un motif ne vient jamais avec des temoins.
    if witness_band_reason:
        document[calibration_profile.WITNESS_BAND_REASON_FIELD] = witness_band_reason
    # **L'etiquette et le commentaire de l'operateur** (story 5.23, AC 8quater). Ecrits
    # seulement s'ils portent quelque chose: passer `label=""` doit produire exactement
    # le document que 5.22 produisait, sans quoi un appelant qui transmet une valeur
    # vide et un appelant qui ne transmet rien ecriraient deux documents differents pour
    # le meme fait -- « l'operateur n'a rien nomme ».
    #
    # Le **fichier**, lui, porte leur defaut: `write_profile` serialise le document
    # normalise, et la fusion pure les complete par la chaine vide. C'est exactement le
    # regime d'`acceptance` depuis 5.22, et il reste idempotent.
    if label:
        document[calibration_profile.LABEL_FIELD] = label
    if comment:
        document[calibration_profile.COMMENT_FIELD] = comment
    # **Le profil NOMME le dossier de scan dont il est issu** (`EPIC11-ARB-262`,
    # tranche par Egan le 2026-09-07, sur son constat de terrain : « Le scan de la page
    # de calibration apparait en non declare alors que je l'ai importe au projet »).
    # C'est la seule declaration d'identite qui relie une mire a son dossier : ni
    # `chain_id` ni `source_page_id` n'en portent la trace, et les trois heuristiques
    # de ressemblance disponibles ecarteraient un vrai lot de planches.
    #
    # Meme patron que l'etiquette et le commentaire, et pour le meme motif : ecrit
    # seulement s'il porte quelque chose. Un appelant qui transmet `""` et un appelant
    # qui ne transmet rien doivent produire le MEME document -- « on ne sait pas d'ou
    # ce profil vient » --, sans quoi le champ dirait deux choses pour un seul fait.
    if scan_dir:
        document[calibration_profile.SCAN_DIR_FIELD] = scan_dir
    return document


#: Construction d'un objet profil depuis ses coefficients, **par identifiant
#: de forme** (`Dev Notes 1`): jamais un type devine du contenu. La cle est
#: d'abord resolue par `get_correction_form`, donc une forme inconnue leve
#: avant que le contenu soit lu.
_PROFILE_BUILDERS: "MappingProxyType[str, object]" = MappingProxyType({
    CORRECTION_FORM_ID: (
        lambda coefficients: CorrectionProfile(
            stage_a=np.asarray(coefficients["stage_a"], dtype=np.float64),
            stage_m=np.asarray(coefficients["stage_m"], dtype=np.float64))),
    CORRECTION_FORM_LAB_ID: (
        lambda coefficients: LabCorrectionProfile(
            lightness_slope=float(coefficients["lightness_slope"]),
            lightness_offset=float(coefficients["lightness_offset"]),
            chroma_matrix=np.asarray(coefficients["chroma_matrix"], dtype=np.float64),
            chroma_offset=np.asarray(coefficients["chroma_offset"], dtype=np.float64))),
    CORRECTION_FORM_TONE_CHROMA_ID: (
        lambda coefficients: ToneCurveCorrectionProfile(
            tone_anchors_in=np.asarray(coefficients["tone_anchors_in"], dtype=np.float64),
            tone_anchors_out=np.asarray(coefficients["tone_anchors_out"], dtype=np.float64),
            chroma_matrix=np.asarray(coefficients["chroma_matrix"], dtype=np.float64))),
})


def profile_from_document(document: dict) -> AnyCorrectionProfile:
    """Reconstruire l'objet profil depuis un document de profil charge.

    Le type est choisi par `correction_form_id` -- jamais par le contenu, c'est
    la doctrine de `Dev Notes 1` -- et l'identifiant est d'abord valide par
    `get_correction_form`, donc une forme inconnue leve un
    `UnknownCorrectionFormError` plutot que de produire un profil de travers.
    L'objet reconstruit est **equivalant** au profil en memoire d'origine au
    sens de l'`AC 1`: egalite des coefficients a la precision serialisee (les
    listes du fichier), et egalite de la sortie `apply_linear` sur une image
    de test.
    """
    form_id = document["correction_form_id"]
    get_correction_form(form_id)
    coefficients = document["coefficients"]
    builder = _PROFILE_BUILDERS.get(form_id)
    if builder is None:
        raise UnknownCorrectionFormError(
            f"Forme '{form_id}' sans constructeur de profil au rechargement. "
            "Un profil recharge sous une forme dont le constructeur manque "
            "serait applique avec des coefficients mal interpretes.")
    return builder(coefficients)


#: L'operateur a demande que la correction ne soit pas appliquee (`--cc off`,
#: `EPIC5-ARB-78`). **Ce n'est pas un motif d'echec** et il ne rejoint pas le vocabulaire
#: ferme de l'AC 8 de 5.4b: rien n'a rate, une correction disponible n'a deliberement pas
#: ete posee sur les pixels. Le distinguer du repli automatique est tout son objet -- les
#: deux produisent des frames non corrigees, et un seul des deux appelle un rescan.
NOT_APPLIED_OPERATOR_OPT_OUT = "correction_declined_by_operator"


def calibration_page_result(correction: LotCorrection, *,
                            patch_preset_id: str) -> PageCalibration:
    """Ce que la **page de calibration elle-meme** declare au manifest. Story 5.19.

    Elle est une page **presente** du lot, donc `_build_calibration_results` lui fait une
    entree quoi qu'il arrive. Sans resultat propre, cette entree reprend le statut du
    **lot**, et les deux valeurs que cela produit sont fausses toutes les deux:

    * lot `applied` -> la page de calibration se declare `applied` alors qu'elle ne porte
      aucune frame et qu'aucun de ses pixels n'a ete corrige. C'est le faux succes du
      risque R12, ecrit dans le document sur la page dont depend toute la correction;
    * lot `failed` parce qu'une **autre** feuille diverge -> la page de calibration se
      declare en echec alors qu'elle a parfaitement produit la correction du lot. Or
      c'est exactement la confusion que l'AC 9 interdit: l'operateur qui relit ce
      document irait rescanner la page de calibration au lieu de la feuille deviante.

    Le statut rendu est donc `not_applied` quand l'ajustement a reussi -- litteralement
    vrai: aucune correction n'a ete **appliquee** a cette page, et il n'y avait rien a y
    appliquer --, et `failed` avec son motif quand il a echoue. `profile` reste `None`
    dans les deux cas, ce qui interdit structurellement qu'un appelant fasse corriger des
    pixels avec cette entree.

    **`correction_source` se lit sur la correction du lot, il n'est plus ecrit ici en
    litteral** (bloquant `C3` de la revue de 5.22). Il valait `own_sheet_patches` sans
    condition, ce qui etait litteralement vrai du seul regime de repli -- la correction
    ajustee sur les pastilles de cette feuille. Le regime nominal de 5.22 le rendait faux
    sur un cas atteignable et ordinaire: l'operateur rescanne le lot **avec la feuille de
    calibration restee dans la pile**, le profil de chaine gagne, `_fit_lot_correction`
    n'est jamais atteint, aucun pixel de cette feuille n'est lu -- et l'appariement par
    identifiant tombe pourtant juste, parce que le profil porte le `source_page_id` de
    cette meme feuille. L'entree d'index 0 declarait alors « la correction vient des
    pastilles de cette feuille » quand elle venait de
    `versions/calibration/<chain_id>.json`. C'est la classe du mutant `M25` -- les
    cardinaux ecrits sur le mauvais lot --, ici appliquee a la provenance.

    `correction_source_page_id` continue de designer la feuille qui a **ajuste** les
    coefficients, dans les deux regimes: elle-meme au repli, celle que le profil nomme
    quand il vient de la chaine. C'est la seule facon de lire au document d'ou est venue
    la correction que les autres pages ont importee, et c'est aussi ce qui rend
    diagnosticable le cas ou les deux feuilles portent le meme identifiant sans etre le
    meme scan.

    `values_version` est vide, comme sur les echecs precoces de `calibrate_page`, et pour
    la meme raison: le treillis est **derive** de ses niveaux et ne vient d'aucune table
    versionnee (`patch_values.calibration_lattice_values`). Inventer une version serait
    declarer une reference qui n'existe pas. `patch_preset_id` est celui que le **lot**
    declare, parce que c'est ce que le QR de cette page porte -- pas la provenance du
    treillis, qui vient du role.

    **Le choix `--cc off` se lit sur `correction.correction_requested`, jamais sur un
    parametre separe** (deuxieme passe de revue, `EPIC5-ARB-78`, 2026-08-14: avant ce
    correctif, cette fonction prenait un `correction_applied` distinct que l'appelant
    devait se souvenir de transmettre -- deux emplacements pour le meme fait, ce sont
    deux verites, et un appelant qui l'aurait omis aurait heritage silencieusement du
    defaut `True`). `LotCorrection.correction_requested` est connu **avant** que cette
    page ne soit meme lue -- c'est une decision de lot --, donc le lire ici plutot que de
    le faire porter par un second parametre est la version qui ne peut pas diverger de
    ce que le reste du document sait deja.
    """
    if correction.available:
        return PageCalibration(
            status=color_pipeline_not_applied(), values_version="",
            patch_preset_id=patch_preset_id, profile=None,
            # La mesure de ce que la correction du lot deforme, publiee sur la page qui
            # l'a produite (`EPIC5-ARB-78`). `profile` reste `None`: publier une mesure
            # n'est pas rendre une correction applicable, et c'est ce `None` qui interdit
            # structurellement a un appelant de corriger des pixels depuis cette entree.
            acceptance=correction.acceptance,
            # Et le verdict **relu du profil**, sous sa cle a lui (bloquant `C2`): dans le
            # regime de chaine, `correction.acceptance` vaut `None` -- rien n'a ete
            # remesure -- et sans ce second champ l'entree ne porterait plus aucune mesure
            # de ce que la correction deforme.
            chain_profile_acceptance=correction.imported_acceptance,
            replicate_dispersion_de76=None,
            channel_relative_deviation_before_correction=None, clipping=None,
            correction_form_id=correction.correction_form_id,
            correction_source=correction.correction_source,
            correction_chain_id=correction.chain_id,
            correction_source_page_id=correction.source_page_id,
            # Le seul cas ou `not_applied` sur cette page ne veut pas dire « il n'y avait
            # rien a appliquer ici »: la correction existait, elle etait exploitable, et
            # l'operateur a demande `--cc off`. Sans ce champ, le document serait
            # identique a celui d'un lot corrige -- la page de calibration ne portant
            # jamais de frame corrigee dans aucun des deux cas.
            not_applied_reason=(None if correction.correction_requested
                                else NOT_APPLIED_OPERATOR_OPT_OUT))
    return _failed(
        correction.failure_reason, preset_id=patch_preset_id, values_version="",
        correction_form_id=correction.correction_form_id,
        # Meme lecture que sur la branche disponible, et pour la meme raison: un echec
        # dont on ne sait pas d'ou la correction devait venir n'est pas relisable. Un
        # profil de chaine ne produit pas d'echec de lot -- il n'y a rien a lire sur la
        # feuille --, donc en pratique cette branche reste `own_sheet_patches`; la lire
        # sur l'objet plutot que l'ecrire en litteral evite qu'un regime futur la rende
        # fausse en silence, ce qui est exactement ce qui vient d'arriver au-dessus.
        correction_source=correction.correction_source,
        correction_chain_id=correction.chain_id,
        chain_profile_acceptance=correction.imported_acceptance,
        correction_source_page_id=correction.source_page_id,
        failure_message=correction.failure_message)


def color_pipeline_not_applied() -> str:
    """`color_pipeline.NOT_APPLIED_STATUS`, resolu **tardivement**.

    L'import est dans la fonction et non en tete de module: `color_pipeline` importe
    `color_calibration` pour appliquer un profil, donc un import de tete ici fermerait le
    cycle. La valeur est **lue** chez son proprietaire et jamais recopiee -- deux
    orthographes du meme statut divergeraient en silence a l'ecriture.
    """
    from . import color_pipeline

    return color_pipeline.NOT_APPLIED_STATUS


# ---------------------------------------------------------------------------
# Story 5.16, AC 13 a 16 : la garde de divergence
# ---------------------------------------------------------------------------

#: Une page diverge de la page de calibration du lot. **Le refus porte la page, jamais
#: le lot** (`EPIC5-ARB-57`, et Egan mot pour mot: « on refuse la page et on demande un
#: rescan de cette page precisement »): un refus de lot obligerait a tout reprendre
#: pour une feuille.
FAILURE_PAGE_DIVERGES = "page_diverges_from_calibration_page"

#: L'exces de residu n'est pas calculable: la page ne peut pas ajuster sa propre
#: correction, donc le troisieme nombre de l'AC 16 n'existe pas et l'exces non plus.
#: **Ce n'est pas un verdict de non-divergence**, exactement comme
#: `REASON_NOISE_NOT_ESTIMABLE` n'est pas un verdict de non-ecretage. La garde ne
#: refuse alors pas: elle porte sur un exces **mesure et trop grand**, pas sur
#: l'absence de mesure -- meme regle que la garde de dispersion.
REASON_DIVERGENCE_NOT_COMPUTABLE = "divergence_excess_not_computable"

#: Nom du drapeau de contournement (AC 15). Declare **ici** parce que c'est ici que le
#: contournement existe; son branchement en ligne de commande appartient a la tache qui
#: possede `cli.py`. Il ne contient aucun mot de reglage: on contourne une garde, on ne
#: regle pas sa valeur.
DIVERGENCE_BYPASS_FLAG = "--appliquer-la-correction-de-calibration-telle-quelle"


@dataclass(frozen=True)
class DivergenceAssessment:
    """Ce que la garde a mesure sur **une** page, et ce qu'elle en conclut.

    Les trois residus sont portes ensemble parce que l'AC 16 en exige trois dans le
    message: l'exces, le seuil enregistre, et le residu que la page obtiendrait sous sa
    **propre** correction. Le troisieme est ce qui distingue « cette page derive » de
    « ce papier est bruyant », et sans lui l'operateur ne peut rien juger.

    **Le residu propre est une mesure, jamais une correction retenue.**
    `EPIC5-ARB-57` tranche que la page deviante n'est **jamais** re-ajustee sur ses
    propres pastilles: la correction appliquee est celle de la page de calibration,
    refus ou contournement. Ajuster le profil propre pour en lire le residu n'est pas
    l'appliquer -- et c'est la seule facon d'obtenir le troisieme nombre.

    `diverges` vaut `None` quand l'exces n'est pas calculable: un booleen pose sur une
    grandeur qu'on n'a pas mesuree est le defaut d'`EPIC5-ARB-52`.
    """

    page_id: str
    source_page_id: str
    #: Residu de la correction **importee**, mesure sur les pastilles temoins de la page.
    imported_residual_de76: float
    #: Residu que la page obtiendrait avec sa **propre** correction, ou `None`.
    own_residual_de76: float | None
    #: `importe - propre`, ou `None`. C'est la statistique d'`EPIC5-ARB-57`.
    excess_residual_de76: float | None
    divergence_id: str
    threshold_de76: float
    diverges: bool | None
    reason: str | None = None
    bypassed: bool = False


def residual_de76(profile, measured_bgr, reference_bgr) -> float:
    """Residu moyen en dE76 d'un profil sur un jeu de pastilles, apres ecretage.

    L'ecretage a [0, 1] est celui d'`EPIC5-ARB-30`, et il est **avant** la mesure: un
    residu calcule sur des valeurs hors bornes mesurerait un pixel qui n'existe pas.
    """
    corrected = oetf(np.clip(profile.apply_linear(eotf(measured_bgr)), 0.0, 1.0))
    return float(delta_e76_srgb_d65(corrected, reference_bgr).mean())


def assess_divergence(measured_bgr, reference_bgr, neutral_mask, imported_profile, *,
                      page_id: str, source_page_id: str,
                      correction_form_id: str = ACTIVE_CORRECTION_FORM_ID,
                      divergence_id: str = ACTIVE_DIVERGENCE_GUARD_ID,
                      bypass: bool = False) -> DivergenceAssessment:
    """Mesurer l'**exces de residu** d'une page, et trancher contre le seuil enregistre.

    Statistique d'`EPIC5-ARB-57`, verbatim: appliquer a la page la correction de la
    page de calibration, mesurer le residu sur ses pastilles temoins, et **retirer** le
    residu que la page obtiendrait avec sa propre correction. Ce retrait est ce qui
    rend la grandeur comparable d'une page a l'autre: sans lui, une page dont le papier
    est bruyant depasserait n'importe quel seuil pour une raison qui n'est pas la
    divergence.

    Le seuil se lit dans le **registre versionne** (`color_metrics.DIVERGENCE_REGISTRY`)
    et n'est jamais pose en litteral ici: c'est le defaut d'`EPIC5-ARB-52`, ou un seuil
    tranche en passant a produit un verdict inoperant.

    **`correction_form_id` n'est pas un enregistrement ici, c'est un calcul**: il choisit
    la forme sous laquelle le profil *propre* de la page est ajuste, donc le troisieme
    nombre du refus et l'exces lui-meme. Son defaut suit donc la forme active (story
    5.21) et non la forme affine: le seul appelant de production (`calibrate_page`) le
    derive du profil importe, et un appelant direct tient presque toujours un profil
    produit par la production, donc de la forme active. Un exces calcule contre un profil
    propre d'une autre famille que le profil importe ne mesure plus une divergence.
    """
    guard = get_divergence_guard(divergence_id)
    imported = residual_de76(imported_profile, measured_bgr, reference_bgr)
    own_residual: float | None = None
    excess: float | None = None
    reason: str | None = None
    # --- Bloquant B2 de la revue de 5.16: la resolution SORT du `try` -------------------
    #
    # `get_correction_form` leve `UnknownCorrectionFormError`, qui **est** un `ValueError`
    # (sous-classe deliberee). Tant qu'elle etait appelee **dans** le `try` ci-dessous, le
    # `except ValueError` l'absorbait: une forme inconnue etait classee « exces non
    # calculable », `diverges` restait `None`, et `calibrate_page` ne refusait pas -- sur un
    # residu importe de 33 dE76. Ce n'etait pas un repli sur la forme active, que le depot
    # interdit explicitement: c'etait le **contournement silencieux d'un refus**, sans le
    # drapeau que l'AC 15 exige explicite.
    #
    # Le `except` reste sur `ValueError` et non sur `UnderdeterminedAdjustmentSet` seule, et
    # ce n'est pas un relachement: les deux formes ne portent **pas** la sous-determination
    # par la meme classe. La forme Lab leve `UnderdeterminedAdjustmentSet` avec son motif
    # nomme; les deux etages de la forme en vigueur (`fit_stage_a`, `fit_stage_m`) levent un
    # `ValueError` nu, et ce sont des definitions historiques que l'AC 1 exige **intactes au
    # caractere**. Ce qui rend la garde correcte n'est donc pas l'etroitesse du `except`,
    # c'est que la seule exception qui n'avait rien a faire dedans ne peut plus y arriver.
    forme = get_correction_form(correction_form_id)
    try:
        own_profile = forme(measured_bgr, reference_bgr, neutral_mask)
    except ValueError:
        # Le jeu temoin de la page ne determine pas une correction: le troisieme nombre
        # de l'AC 16 n'existe pas, donc l'exces non plus. On le **dit** au lieu de poser
        # un exces de zero, qui serait la meilleure lecture possible la ou rien n'a ete
        # mesure -- le meme faux succes que la dispersion publiee a 0,0 (revue de 5.4b).
        reason = REASON_DIVERGENCE_NOT_COMPUTABLE
    else:
        own_residual = residual_de76(own_profile, measured_bgr, reference_bgr)
        excess = imported - own_residual
    return DivergenceAssessment(
        page_id=page_id,
        source_page_id=source_page_id,
        imported_residual_de76=imported,
        own_residual_de76=own_residual,
        excess_residual_de76=excess,
        divergence_id=guard.divergence_id,
        threshold_de76=guard.max_excess_residual_de76,
        diverges=None if excess is None else excess > guard.max_excess_residual_de76,
        reason=reason,
        bypassed=bool(bypass) and excess is not None
        and excess > guard.max_excess_residual_de76,
    )


#: Une planche diverge de la source de correction et **aucun geste explicite** ne
#: demande de lui appliquer le profil quand meme (story 5.22, `EPIC5-ARB-80`
#: decision 5 et 6). Ses frames sont ecrites telles quelles et le manifest le
#: declare.
#:
#: **Motif de `not_applied`, pas d'echec**, et c'est tout le changement de regime
#: apporte par cette story: jusqu'ici la divergence rendait `FAILURE_PAGE_DIVERGES`,
#: donc un refus dur dont la seule issue etait le rescan ou le contournement. Le
#: mecanisme etait par lot, la correction s'ajustait a chaque scan, et une feuille
#: reposee autrement derivait -- si bien que la conception **fabriquait** le refus que
#: subissaient les trois captures de `projects/chendj-mat/scans/`, alors que la chaine
#: et le scanner etaient les memes. La divergence redevient donc ce qu'elle est: une
#: mesure a soumettre a l'operateur, jamais un verdict rendu a sa place.
#:
#: `FAILURE_PAGE_DIVERGES` **est conserve** et n'est pas du code mort: il reste le
#: vocabulaire sous lequel les manifests deja ecrits declarent leurs planches
#: refusees, et le lire doit rester possible.
NOT_APPLIED_PAGE_DIVERGES = "page_diverges_without_explicit_apply"

# **Ce motif n'a plus de producteur depuis la story 5.23** (`EPIC5-ARB-82` decision 1),
# exactement comme `FAILURE_PAGE_DIVERGES` n'en avait plus depuis 5.22, et pour la meme
# raison poussee d'un cran: la divergence ne refuse plus rien du tout, ni en echec ni en
# `not_applied`. Il est conserve, et ce n'est pas du code mort: c'est le vocabulaire sous
# lequel les manifests **deja ecrits** declarent leurs planches livrees en brut, et le
# relire doit rester possible.
#
# `divergence_warning_message`, elle, a ete **retiree** par la meme story, et le
# traitement asymetrique des deux est delibere: un motif est une valeur qui vit dans des
# documents persistes sur le disque d'Egan, une fonction de message est du code, et un
# message que plus aucun chemin ne produit ne se relit nulle part -- il se maintient, se
# teste et vieillit pour rien. Son remplacant est `raw_divergence_warning_message`, qui
# porte l'autre grandeur -- l'ecart brut a brut -- et dit que la correction a ete
# appliquee quand meme.


# ---------------------------------------------------------------------------
# Story 5.23 : la divergence se mesure BRUTE A BRUTE, et elle n'avertit que
# ---------------------------------------------------------------------------
#
# `EPIC5-ARB-82`. Ce bloc est le **cablage** de production de la grandeur que
# `color_metrics.raw_divergence_de76` calcule: echantillonner les memes pastilles
# temoins sur les deux feuilles, apparier par identifiant, comparer sans qu'aucun profil
# n'intervienne, et **avertir** au-dela du seuil enregistre. La bascule de politique est
# ici et nulle part ailleurs: `calibrate_page` ne rend plus `not_applied` a cause d'une
# divergence, quelle qu'en soit la grandeur.

#: Nom du drapeau qui garde le scan **brut** sans qu'aucune invite ne soit posee
#: (`EPIC5-ARB-82` decision 6, AC 5). Declare **ici**, dans le module qui possede la
#: decision d'appliquer ou non la correction, et jamais recopie en litteral dans
#: `cli.py`: c'est la meme regle que `DIVERGENCE_BYPASS_FLAG`, et elle a la meme raison
#: d'etre -- deux redactions du meme nom divergent, et l'aide de la commande finit par
#: annoncer un drapeau que le code ne reconnait plus.
#:
#: Il ne contient **aucun mot de reglage** (frontiere negative de l'AC 5): on refuse une
#: correction, on ne choisit pas un seuil. `--seuil` et `--tolerance` restent interdits.
RAW_OUTPUT_FLAG = "--garder-le-scan-brut"

#: **Aucune mesure de temoins de page de calibration n'est disponible pour ce lot**, ni
#: dans cette passe de scan, ni dans le profil de chaine applique. Il n'y a alors aucune
#: mesure brute a confronter, et ce n'est pas un verdict de non-divergence.
#:
#: Sa portee s'est **retrecie** avec la correction du 2026-08-18, et c'est tout l'objet de
#: celle-ci: avant, il couvrait tout le regime nominal de 5.22 -- profil de chaine
#: reutilise, donc feuille de calibration absente de la passe --, c'est-a-dire que la
#: mesure centrale d'`EPIC5-ARB-82` n'avait **jamais** lieu en production. Depuis que le
#: profil porte les mesures brutes de ses temoins, il ne reste vrai que de deux cas:
#: profil ecrit avant cette mesure, ou page de calibration sans bandeau de temoins.
RAW_DIVERGENCE_NO_CALIBRATION_SHEET = "raw_divergence_no_calibration_sheet"

#: La page de calibration **a ete lue**, et son bandeau de temoins n'a rien donne: feuille
#: imprimee avant la story 5.23 (ses colonnes laterales sont du papier nu), gabarit qui ne
#: sait pas poser le bandeau, ou bandeau ampute par le redressage.
#:
#: **Distinct du precedent, et la distinction se lit sur le type et non sur un parametre
#: de plus**: `calibration_raw` a `None` dit « aucune feuille de calibration dans ce
#: scan », un mapping **vide** dit « feuille lue, bandeau inexploitable ». Les confondre
#: ferait ecrire au manifest qu'aucune feuille de calibration n'a ete lue d'un lot dont la
#: correction vient precisement d'elle -- exactement la faussete qu'`EPIC5-ARB-70` a
#: fermee ailleurs.
#:
#: **Sa portee s'est retrecie une seconde fois, le 2026-08-19** (`EPIC5-ARB-104`): il ne
#: couvre plus que le regime pour lequel il a ete ecrit -- la feuille est **anterieure au
#: bandeau**, ses colonnes laterales sont du papier nu. Les trois autres facons de ne rien
#: mesurer sur un bandeau ont chacune leur nom ci-dessous, parce que deux d'entre elles
#: portent de l'encre et que les declarer « papier nu » etait faux.
RAW_DIVERGENCE_BAND_NOT_PRINTED = "raw_divergence_witness_band_not_printed"

#: **Le lot n'a pas dit quel preset sa feuille declare** -- `patch_preset_id` absent a la
#: mesure. Rien n'a ete lu et rien ne pouvait l'etre: ce n'est ni « papier nu » ni un
#: echec de lecture, c'est une question qui n'a pas ete posee.
RAW_DIVERGENCE_BAND_NO_PRESET = "raw_divergence_witness_band_no_preset_declared"

#: **Le preset declare est inconnu du registre**: une faute de frappe, ou un tirage compose
#: par une version que ce depot ne connait pas. C'est ce que la garde de
#: `patch_presets.calibration_page_carries_witness_band` leve **expres** -- « je ne connais
#: pas ce preset » et « ce preset n'a pas de bandeau » sont deux faits differents --, et
#: c'est le motif qui empeche l'unique appelant de production de l'avaler.
RAW_DIVERGENCE_BAND_PRESET_UNKNOWN = "raw_divergence_witness_band_preset_unknown"

#: **Le gabarit ne sait pas poser le bandeau** sur une page de calibration: geometrie v1,
#: gabarit inconnu, ou pose refusee. La feuille peut parfaitement porter de l'encre; c'est
#: le lecteur qui ne sait pas ou regarder.
RAW_DIVERGENCE_BAND_PLACEMENT_UNDEFINED = (
    "raw_divergence_witness_band_placement_undefined")

#: **Le bandeau est ampute**: au moins une pastille tombe hors de la page redressee --
#: redressage rate, ou feuille rognee au massicot. Le regime le plus couteux a confondre
#: avec « papier nu »: il y a de l'encre, et le manifest disait le contraire.
RAW_DIVERGENCE_BAND_CROPPED = "raw_divergence_witness_band_cropped"

#: Le **vocabulaire ferme** des motifs que la mesure du bandeau peut rendre, dans l'ordre
#: ou `_sample_calibration_witness_band` les rencontre. Enumere une seule fois: un test
#: epingle qu'ils sont cinq et deux a deux distincts, et une addition muette au manifest
#: ne peut donc pas passer inapercue.
RAW_DIVERGENCE_BAND_REASONS: tuple[str, ...] = (
    RAW_DIVERGENCE_BAND_NO_PRESET,
    RAW_DIVERGENCE_BAND_NOT_PRINTED,
    RAW_DIVERGENCE_BAND_PRESET_UNKNOWN,
    RAW_DIVERGENCE_BAND_PLACEMENT_UNDEFINED,
    RAW_DIVERGENCE_BAND_CROPPED,
)

#: Aucune valeur temoin n'est lisible sur les deux feuilles a la fois. Distinct des deux
#: precedents: la matiere etait la, la lecture a echoue.
RAW_DIVERGENCE_NO_PAIR = "raw_divergence_no_readable_pair"


@dataclass(frozen=True)
class RawDivergenceAssessment:
    """Ce que la mesure brute a brute a rendu sur **une** planche, et sa conclusion.

    Story 5.23, AC 2 et 4. Deliberement **distinct** de `DivergenceAssessment`, qui reste
    ce qu'il etait: les deux grandeurs ne se comparent pas -- ici un ecart brut entre deux
    feuilles mesurees sans aucune correction, la-bas un exces de residu entre deux
    ajustements compares a la theorie -- et les fondre ferait relire le 5,0 comme « le 1,0
    releve », ce que la reserve du registre interdit explicitement.

    `mean_raw_de76` et `exceeds` valent `None` ensemble quand la mesure n'a pas pu etre
    faite: un booleen pose sur une grandeur qu'on n'a pas mesuree est le defaut
    d'`EPIC5-ARB-52`, et `reason` dit alors **lequel** des trois regimes on est.
    """

    page_id: str
    source_page_id: str
    divergence_id: str
    threshold_de76: float
    #: Ecart brut moyen en dE76, ou `None` quand la mesure n'a pas eu lieu.
    mean_raw_de76: float | None
    #: Valeurs effectivement appariees, triees.
    paired_value_ids: tuple[str, ...] = ()
    #: Valeurs ecartees de la moyenne, chacune avec son motif.
    excluded: tuple[tuple[str, str], ...] = ()
    #: L'ecart depasse-t-il **strictement** le seuil enregistre ? `None` si non mesure.
    exceeds: bool | None = None
    reason: str | None = None


def witness_raw_mapping(measured_bgr, ids) -> dict:
    """Mesures **brutes** des temoins, par identifiant de valeur, repliques moyennees.

    Le point de passage oblige entre `sample_patches` et `raw_divergence_de76`: c'est ici
    que l'appariement cesse d'etre positionnel. La moyenne des repliques est celle de H4
    (`aggregate_by_value`), la meme que celle qui nourrit l'ajustement -- deux agregations
    differentes sur le meme chemin seraient deux verites.

    Aucun profil n'intervient et il ne peut pas en intervenir: la fonction ne recoit que
    des mesures et des identifiants.
    """
    value_ids, aggregated = aggregate_by_value(measured_bgr, ids)
    return {value_id: tuple(float(component) for component in row)
            for value_id, row in zip(value_ids, aggregated)}


class WitnessBandRaw(dict):
    """Les mesures brutes du bandeau **et** le motif quand il n'y en a pas.

    `EPIC5-ARB-104`. C'est un `dict` -- donc `dict(...)`, `not`, `in` et l'appariement par
    identifiant marchent exactement comme avant -- portant un attribut de plus. Le choix
    d'un attribut plutot que d'un parametre supplementaire est celui de la story: le motif
    doit **voyager avec la mesure**, sans quoi chaque relais entre le producteur et le
    manifest est une occasion de le perdre, et c'est ce qui s'est produit.

    `reason` vide se lit « il y a une mesure, ou la question ne s'est pas posee »; sinon,
    l'un de `RAW_DIVERGENCE_BAND_REASONS`.
    """

    __slots__ = ("reason",)

    def __init__(self, mapping=(), *, reason: str = ""):
        super().__init__(mapping)
        self.reason = reason


def witness_band_reason_of(calibration_raw) -> str:
    """Le motif porte par une mesure de bandeau, ou la chaine vide.

    Un point de lecture unique plutot qu'un `getattr` recopie a chaque relais: un mapping
    ordinaire -- ce que passent les tests et les appelants d'avant `EPIC5-ARB-104` -- n'en
    porte pas, et se lit « motif inconnu », jamais « pas de motif ».
    """
    return getattr(calibration_raw, "reason", "") or ""


def calibration_witness_raw_for_lot(correction, *, from_chain_profile: bool):
    """La moitie « page de calibration » de la mesure brute a brute, pour **ce** lot.

    Story 5.23, correction du 2026-08-18. Cette fonction porte une decision de trois
    regimes, et elle vit **ici**, dans le module qui possede la politique de correction,
    plutot que dans une expression conditionnelle de `cli.py` -- meme regle que
    `RAW_OUTPUT_FLAG`: une decision recopiee au point d'usage se reecrit tot ou tard
    differemment ailleurs.

    * **la page de calibration est dans cette passe de scan** (`from_chain_profile` faux):
      on rend ce qui a ete mesure sur elle, y compris un mapping **vide** -- « feuille
      lue, bandeau inexploitable », motif `raw_divergence_witness_band_not_printed`;
    * **la correction vient d'un profil de chaine qui porte ses temoins**: on rend les
      mesures du profil. C'est ce qui rend la comparaison possible hors de la passe qui a
      lu la feuille, donc dans le regime nominal;
    * **la correction vient d'un profil sans temoins** (profil anterieur au 2026-08-18,
      ou page sans bandeau): `None`, soit « aucune mesure disponible », jamais un ecart
      nul -- un zero est la lecture de deux feuilles identiques.

    Le vide et le `None` ne sont donc pas interchangeables, et la distinction voyage par
    le **type**, comme `assess_raw_divergence` l'attend.

    **Le troisieme regime s'est scinde en deux le 2026-08-19** (`EPIC5-ARB-104`), et c'est
    le second etage du meme defaut: un profil de chaine qui porte un **motif** de bandeau a
    bel et bien vu sa page de calibration -- elle a ete lue, son bandeau n'a rien donne, et
    le fichier le dit. Le rabattre sur `None` faisait sortir
    `raw_divergence_no_calibration_sheet` d'une chaine dont la page **a ete lue**: le
    profil persistait la faussete, exactement ce que le commentaire voisin revendique
    fermer (`EPIC5-ARB-70`). `None` ne reste donc vrai que d'un profil qui ne dit rien du
    tout -- ecrit avant que la mesure existe.
    """
    temoins = correction.witness_raw_mapping()
    motif = correction.witness_band_reason
    if temoins:
        return WitnessBandRaw(temoins)
    if from_chain_profile and not motif:
        return None
    return WitnessBandRaw((), reason=motif or RAW_DIVERGENCE_BAND_NOT_PRINTED)


def assess_raw_divergence(*, sheet_raw, calibration_raw, page_id: str,
                          source_page_id: str,
                          divergence_id: str = ACTIVE_RAW_DIVERGENCE_GUARD_ID,
                          calibration_band_reason: str = ""
                          ) -> RawDivergenceAssessment:
    """Confronter les temoins bruts des deux feuilles, et **avertir** au-dela du seuil.

    Story 5.23, AC 2 et 4. La comparaison au seuil n'est pas ecrite ici: elle est
    deleguee a `color_metrics.raw_divergence_exceeds`, qui porte la frontiere stricte
    (« egal n'avertit pas ») **en un seul endroit**. L'ecrire une seconde fois est ce qui
    ferait diverger les deux redactions au premier mutant `>` / `>=`.

    `calibration_raw` vide -- profil de chaine reutilise, donc aucune page de calibration
    lue par ce scan -- n'est pas un ecart de zero: c'est une mesure qui n'a pas eu lieu,
    et elle se declare.

    `calibration_band_reason` dit **laquelle** des quatre facons de ne rien mesurer sur un
    bandeau (`EPIC5-ARB-104`). Il est lu sur la mesure elle-meme quand elle en porte un
    (`WitnessBandRaw`), et le parametre reste explicite pour les appelants qui construisent
    la mesure a la main. Absent, le motif retombe sur `RAW_DIVERGENCE_BAND_NOT_PRINTED`:
    c'est le regime nominal, et c'est ce que la fonction declarait deja des quatre.
    """
    guard = get_raw_divergence_guard(divergence_id)

    def _sans_mesure(reason: str) -> RawDivergenceAssessment:
        return RawDivergenceAssessment(
            page_id=page_id, source_page_id=source_page_id,
            divergence_id=guard.divergence_id,
            threshold_de76=guard.max_mean_raw_de76,
            mean_raw_de76=None, exceeds=None, reason=reason)

    if calibration_raw is None:
        return _sans_mesure(RAW_DIVERGENCE_NO_CALIBRATION_SHEET)
    if not calibration_raw:
        return _sans_mesure(calibration_band_reason
                            or witness_band_reason_of(calibration_raw)
                            or RAW_DIVERGENCE_BAND_NOT_PRINTED)
    try:
        mesure = raw_divergence_de76(sheet_raw=sheet_raw,
                                     calibration_raw=calibration_raw)
    except ColorMetricError:
        # Aucune paire lisible. La moyenne sur un jeu vide serait un chiffre sans donnee,
        # et `raw_divergence_de76` refuse plutot que de la rendre: on traduit ce refus en
        # « non mesure », jamais en « ne diverge pas ».
        return _sans_mesure(RAW_DIVERGENCE_NO_PAIR)
    return RawDivergenceAssessment(
        page_id=page_id, source_page_id=source_page_id,
        divergence_id=guard.divergence_id,
        threshold_de76=guard.max_mean_raw_de76,
        mean_raw_de76=mesure.mean_delta_e76,
        paired_value_ids=mesure.paired_value_ids,
        excluded=tuple((item.value_id, item.reason) for item in mesure.excluded),
        exceeds=raw_divergence_exceeds(mesure.mean_delta_e76,
                                       divergence_id=guard.divergence_id),
    )


def raw_divergence_warning_message(assessment: RawDivergenceAssessment) -> str:
    """L'avertissement que l'operateur recoit au-dela du seuil. AC 4 de 5.23.

    Trois nombres exiges par l'AC, et **la phrase qui dit que la correction a quand meme
    ete appliquee**: c'est elle qui distingue cet avertissement de tous ceux que 5.22
    ecrivait, ou l'ecart chiffre annoncait une planche livree en brut.

    Le message ne contient **ni « refus » ni « rescann »** (frontiere negative de l'AC 4,
    verifiee sur le message complet). Le motif est mesure et non stylistique: sur le lot
    reel d'Egan, le mot « rescannez » envoyait l'operateur reprendre une feuille qui
    venait d'etre ecrite sur le disque. Et il ne porte aucun mot de reglage, meme regle
    qu'ailleurs dans ce module: la valeur enregistree est nommee par son **identifiant de
    registre**, ce qui la rend relisable sans la rendre negociable.
    """
    if assessment.mean_raw_de76 is None:
        raise ValueError(
            "raw_divergence_warning_message sur une divergence non mesuree "
            f"({assessment.reason!r}). Un avertissement chiffre sans chiffre serait "
            "exactement le faux succes que ce module refuse partout ailleurs.")
    ecartees = ""
    if assessment.excluded:
        ecartees = (
            f" {len(assessment.excluded)} valeur(s) temoin ecartee(s) de la moyenne: "
            + ", ".join(f"{value_id} ({motif})"
                        for value_id, motif in assessment.excluded) + ".")
    return (
        f"Page '{assessment.page_id}': ses pastilles temoins mesurees SANS correction "
        f"s'ecartent de celles de '{assessment.source_page_id}' de "
        f"{assessment.mean_raw_de76:.2f} dE76 en moyenne, au-dela des "
        f"{assessment.threshold_de76:.2f} dE76 enregistres sous "
        f"'{assessment.divergence_id}'. Ecart mesure sur "
        f"{len(assessment.paired_value_ids)} valeur(s) appariee(s) par identifiant."
        f"{ecartees} La correction a ete appliquee quand meme: les deux feuilles ne se "
        "comportent pas tout a fait pareil, et une correction imparfaite reste plus "
        "proche de la source que pas de correction du tout."
    )


def max_degradation_warning_message(acceptance: AcceptanceVerdict,
                                    *, page_id: str,
                                    guard_id: str = ACTIVE_MAX_DEGRADATION_GUARD_ID
                                    ) -> str:
    """L'avertissement de la garde de degradation maximale. AC 7 de 5.23.

    Il **nomme la valeur de pastille concernee**, et c'est l'AC: « la plus grande
    degradation vaut +18 dE76 » n'est pas actionnable, `lattice-188-128-188` l'est --
    l'operateur sait quelle couleur regarder sur sa planche.

    Le nom de la pastille vit sur `acceptance.detail` (`PageAcceptanceResult`) et non sur
    le verdict plat: un verdict construit a la main n'en porte pas, et le message le dit
    plutot que d'inventer un identifiant.
    """
    guard = get_max_degradation_guard(guard_id)
    detail = acceptance.detail
    pastille = (detail.worst_degradation_value_id if detail is not None else "")
    nomme = f"'{pastille}'" if pastille else "non identifiee (verdict sans detail)"
    return (
        f"Page '{page_id}': la correction degrade une pastille de "
        f"{acceptance.max_degradation_de76:+.2f} dE76, au-dela des "
        f"{guard.max_degradation_de76:.2f} dE76 enregistres sous '{guard.guard_id}'. "
        f"Pastille concernee: {nomme}. La correction ameliore la page dans son ensemble "
        f"({acceptance.mean_degradation_de76:+.2f} dE76 de degradation moyenne, negatif "
        "= amelioration) et elle a ete appliquee; c'est cette couleur-la qu'il faut "
        "regarder si un artefact visuel apparait."
    )


def calibrate_page(rectified_page, *, template_id: str, patch_preset_id: str,
                   dpi: int, input_warnings: tuple[str, ...] = (),
                   correction_form_id: str = ACTIVE_CORRECTION_FORM_ID,
                   imported_profile=None,
                   imported_source_page_id: str | None = None,
                   imported_correction_source: str = CORRECTION_SOURCE_CALIBRATION_PAGE,
                   imported_chain_id: str | None = None,
                   imported_acceptance: "AcceptanceVerdict | None" = None,
                   page_id: str | None = None,
                   divergence_bypass: bool = False,
                   divergence_id: str = ACTIVE_DIVERGENCE_GUARD_ID,
                   calibration_witness_raw: Mapping | None = None,
                   raw_divergence_id: str = ACTIVE_RAW_DIVERGENCE_GUARD_ID,
                   ) -> PageCalibration:
    """Calibrer **une** page: lire ses pastilles, ajuster, juger, declarer.

    Une page = un jeu de pastilles = une correction = les frames de cette page
    (AC 5). Aucune moyenne inter-pages, aucun repli sur la correction d'une page
    voisine: si une page n'a pas de correction exploitable, ce sont **ses** frames qui
    sont marquees, pas celles du lot.

    `input_warnings` transporte les avertissements des pages qui nourrissent
    l'ajustement -- `PDF_EMBEDS_LOSSY_IMAGE` et compagnie. Tranche par Egan
    (`EPIC5-ARB-47`): le PDF **reste** une entree de premier rang, y compris degrade,
    et ce qui change est la **tracabilite**. Une correction issue d'une entree abimee
    reste utilisable *et* reconnaissable. Aucun refus n'est ajoute sur ce motif.

    **Deux regimes depuis la story 5.16, et le regime par defaut reste l'ancien.**

    * sans `imported_profile`, la page s'ajuste sur ses propres pastilles, et c'est ce
      qui se passe quand personne ne choisit de regime. **La forme sous laquelle elle
      s'ajuste, elle, a change avec la story 5.21**: le defaut de `correction_form_id`
      est `ACTIVE_CORRECTION_FORM_ID` et non plus `CORRECTION_FORM_ID`, donc l'ancienne
      garantie « inchange au bit pres » de l'AC 1 de 5.16 ne vaut plus que pour un appel
      qui **nomme** `correction_form_id=CORRECTION_FORM_ID`. Le regime n'a pas bouge, la
      forme si;
    * avec `imported_profile`, la correction vient de la **page de calibration du lot**
      (`EPIC5-ARB-54`) et les pastilles de la page ne servent plus qu'a la **verifier**:
      residu, dispersion, verdict d'ecretage, et la garde de divergence
      d'`EPIC5-ARB-57`. La page deviante n'est **jamais** re-ajustee sur ses propres
      pastilles -- ni au refus, ni au contournement.

    `page_id` nomme la page dans le refus de divergence: sans lui, le message dirait
    « une page du lot », et Egan demande « un rescan de cette page precisement ».

    **`imported_acceptance` transporte le verdict consigne dans le profil de chaine**
    (bloquant `C2` de la revue de 5.22), et il ne remplace jamais `acceptance`: celui-ci
    est ce que **cette** page a mesure, celui-la ce que la feuille de calibration de la
    chaine avait mesure le jour de la calibration. Il vaut `None` dans le regime local --
    une page qui s'ajuste sur elle-meme n'importe rien --, et l'appelant est le seul a
    pouvoir le fournir, exactement comme pour `imported_chain_id`: le profil ne porte que
    des coefficients, la mesure vit dans le document qui l'entoure.
    """
    from . import patch_presets

    # La provenance est etablie **avant** toute garde: un echec doit la porter aussi,
    # pour la meme raison que la forme de correction et l'entree de seuils y sont deja
    # (finding de la revue de 5.4a). Un echec dont on ne sait pas quelle correction a
    # ete tentee, ni d'ou elle venait, n'est pas relisable.
    transported = imported_profile is not None
    # **La provenance du profil importe est NOMMEE par l'appelant** depuis la story
    # 5.22, au lieu d'etre deduite du seul fait qu'un profil est importe. Deux
    # provenances transportees existent maintenant -- la page de calibration du lot
    # (`EPIC5-ARB-54`, ancien tirage) et le profil de chaine (`EPIC5-ARB-80`) --, et
    # elles ne se devinent pas: seul l'appelant sait d'ou vient le profil qu'il passe.
    # Le defaut reste la page de calibration, donc tout appelant d'avant 5.22 garde
    # exactement son comportement.
    correction_source = (imported_correction_source if transported
                         else CORRECTION_SOURCE_OWN_SHEET)
    source_page_id = imported_source_page_id if transported else page_id
    chain_id = imported_chain_id if transported else None
    # Meme regle que pour `chain_id`, et elle est structurelle et non de commodite: sans
    # profil importe il n'y a aucun verdict importe, donc une valeur passee par erreur
    # dans le regime local est **ignoree** plutot que publiee -- publier la mesure d'un
    # profil sur une page qui s'est ajustee toute seule serait la faute que ce champ
    # existe pour empecher.
    chain_acceptance = imported_acceptance if transported else None
    form_id = (getattr(imported_profile, "correction_id", correction_form_id)
               if transported else correction_form_id)
    def _fail(reason: str, **kwargs) -> PageCalibration:
        """`_failed` avec la provenance de **cet** appel, pour ne pas l'oublier une fois.

        Elle serait oubliee: il y a huit points de sortie en echec dans cette fonction,
        et un seul qui perdrait la provenance suffirait a rendre un echec non relisable.
        """
        return _failed(reason, correction_form_id=form_id,
                       correction_source=correction_source,
                       correction_source_page_id=source_page_id,
                       correction_chain_id=chain_id,
                       chain_profile_acceptance=chain_acceptance, **kwargs)

    # **La fermeture `_decline` a ete retiree avec la story 5.23**, et son absence est le
    # correctif lui-meme: elle n'avait qu'un appelant, la branche de refus de divergence,
    # et cette branche n'existe plus (`EPIC5-ARB-82` decision 1). La garder « au cas ou »
    # laisserait dans cette fonction une porte de sortie `not_applied` que rien n'ouvre --
    # exactement la forme sous laquelle un refus revient par inadvertance a la revision
    # suivante. `_not_applied_page` reste, elle: `calibration_page_result` la construit
    # toujours pour la page de calibration elle-meme, qui ne porte aucune frame.

    # `dpi` d'abord: il gouverne toutes les conversions en pixels, donc un dpi invalide
    # rend toute mesure suivante fausse. Il etait accepte a 600,5 comme a -1.
    if not is_strict_int(dpi) or dpi <= 0:
        return _fail(FAILURE_INVALID_DPI, preset_id=patch_preset_id,
                     values_version="", warnings=input_warnings)
    # Meme garde que sur la page de calibration, meme rang, meme motif: une planche
    # monochrome ou a canal alpha traverse l'ingestion, et 5.19 lui donne un appelant de
    # production. Sans elle, la moitie des scans en niveaux de gris tuait la commande et
    # l'autre moitie -- selon la divisibilite par trois de l'aire echantillonnee --
    # ajustait une correction sur des gris.
    if not page_has_three_channels(rectified_page):
        return _fail(FAILURE_NOT_THREE_CHANNELS, preset_id=patch_preset_id,
                     values_version="", warnings=input_warnings)
    # La forme est resolue tot, **dans les deux regimes**: une forme inconnue doit echouer
    # avant d'avoir lu une pastille, et jamais retomber sur la forme active -- un repli
    # rendrait le manifest menteur sur ce qui a ete applique (AC 10).
    #
    # **Le regime transporte etait exclu de cette resolution, et c'est le bloquant B2 de la
    # revue de 5.16.** L'identifiant y vient du profil **importe**, donc d'une valeur que
    # rien ne validait: la forme inconnue n'etait decouverte qu'a l'interieur
    # d'`assess_divergence`, dont le `except ValueError` l'absorbait --
    # `UnknownCorrectionFormError` **est** un `ValueError`. La garde etait donc muette
    # exactement dans le regime pour lequel elle existe -- celui ou la correction vient
    # d'ailleurs -- et une page dont le residu importe valait 33 dE76 ressortait `applied`
    # sous un motif qui disait « exces non calculable ».
    #
    # **L'asymetrie des deux branches est deliberee, et elle suit la nature de la faute.**
    # Dans le regime local, `correction_form_id` est un **argument de l'appelant**: une
    # valeur inconnue est une faute de programmation, elle leve, et c'est le contrat que
    # l'AC 1 epingle. Dans le regime transporte, l'identifiant est une **donnee** -- il
    # vient du profil importe, donc du document ou du terrain -- et une donnee fautive doit
    # rendre un motif du vocabulaire ferme de l'AC 8, comme toutes les autres causes, en
    # portant la provenance de cet appel.
    if not transported:
        get_correction_form(correction_form_id)
    else:
        try:
            get_correction_form(form_id)
        except UnknownCorrectionFormError:
            return _fail(FAILURE_UNKNOWN_CORRECTION_FORM, preset_id=patch_preset_id,
                         values_version="", warnings=input_warnings)
    try:
        preset = patch_presets.get_patch_preset(patch_preset_id)
    except patch_presets.UnknownPatchPresetError:
        return _fail(FAILURE_UNKNOWN_PATCH_PRESET, preset_id=patch_preset_id,
                     values_version="", warnings=input_warnings)
    try:
        table = patch_values.get_patch_values_table(preset.values_version)
    except patch_values.UnknownPatchValuesVersionError:
        return _fail(FAILURE_UNKNOWN_VALUES_VERSION, preset_id=patch_preset_id,
                     values_version=preset.values_version, warnings=input_warnings)

    version = table.version
    try:
        layout = patch_presets.resolve_patch_layout(template_id, patch_preset_id)
    except patch_presets.UndefinedPlacementError:
        return _fail(FAILURE_PLACEMENT_UNDEFINED, preset_id=patch_preset_id,
                     values_version=version, warnings=input_warnings)
    measured, ids = sample_patches(rectified_page, layout, dpi)
    if len(measured) < len(layout):
        return _fail(FAILURE_PATCHES_NOT_FOUND, preset_id=patch_preset_id,
                     values_version=version, warnings=input_warnings)

    adjustment_ids = {value.value_id for value in table.adjustment_values()}
    neutral_ids = {value.value_id for value in table.adjustment_values()
                   if value.role == patch_values.ROLE_NEUTRAL}
    keep = np.array([value_id in adjustment_ids for value_id in ids], dtype=bool)

    # La garde de plausibilite ne porte que sur le **jeu d'ajustement**, et c'est un
    # correctif de conception, pas un assouplissement. Une premiere version la posait
    # sur toutes les pastilles: elle faisait echouer **toute page reelle**, parce que
    # `sentinel-black-1` vaut (0,0,0) et `sentinel-white-1` (255,255,255) -- ce sont
    # leurs valeurs par construction. Or `patch_values` exclut volontairement ces deux
    # ancres du jeu d'ajustement (`patch_values.py:89-95`: saturation d'encrage, papier
    # nu non mesurable), donc le jeu d'ajustement est **borne loin des extremes par
    # specification** et c'est exactement sur lui que la garde a un sens. Son role est
    # d'attraper une erreur de geometrie -- page mal redressee, emplacement decale --
    # pas de juger une couleur.
    low, high = PLAUSIBLE_RANGE
    if keep.any() and (measured[keep].min() < low or measured[keep].max() > high):
        return _fail(FAILURE_PATCHES_OUT_OF_RANGE, preset_id=patch_preset_id,
                     values_version=version, warnings=input_warnings)

    dispersion, _detail = replicate_dispersion(measured, ids)
    # Le verdict d'ecretage est calcule **avant** la garde de dispersion et rendu
    # meme sur un echec: il repond a « que reste-t-il du contenu source », pas a
    # « la correction est-elle bonne » (EPIC5-ARB-16). Les quatre combinaisons
    # statut x ecretage sont representables.
    #
    # Le seuil se calcule sur le bruit **median par paires** et non sur la dispersion
    # (bloquant B2 de la revue du 2026-08-11: deux grandeurs differentes, voir
    # `measurement_noise_de76`). Et quand le bruit n'est pas estimable, chaque axe sort
    # `unavailable` -- l'ancien repli `noise = 1.0` inventait un seuil, ce qui rendait
    # le verdict d'autant plus aveugle que le tirage etait propre: sur une page
    # parfaite, le seuil tombait a 1e-13 dE76 et un ecretage reel de 0,547 sortait
    # `clipped: False`.
    noise = measurement_noise_de76(measured, ids)
    chains = sentinel_chains(table)
    # `noise <= 0` est traite comme non estimable, et pas seulement `nan`: un bruit nul
    # rend le seuil degenere, donc le verdict devient « egalite bit a bit » -- une page
    # de synthese parfaite declarerait non ecrete tout ecart non nul, aussi petit
    # soit-il. Aucun tirage reel n'a un bruit nul; une entree qui en a un n'est pas une
    # mesure, et on ne rend pas un verdict dessus.
    if not np.isfinite(noise) or noise <= 0.0:
        verdicts = {axis: {"clipped": None, "reason": REASON_NOISE_NOT_ESTIMABLE}
                    for axis in chains}
    else:
        verdicts = clipping_verdict(measured, ids, chains, noise)
    clipping = clipping_summary(verdicts)
    # `dispersion is None` -- aucune valeur n'a deux repliques -- ne declenche pas ce
    # refus: la garde porte sur une dispersion **mesuree et trop haute**, pas sur
    # l'absence de mesure. Un preset a `repetition = 1` reste donc calibrable, ce que
    # `patch_presets.single` rend possible, et le champ rendu dit `None` plutot que zero.
    if dispersion is not None and dispersion > MAX_REPLICATE_DISPERSION_DE76:
        return _fail(FAILURE_REPLICATE_DISPERSION, preset_id=patch_preset_id,
                     values_version=version, dispersion=dispersion,
                     clipping=clipping, warnings=input_warnings)

    reference_by_id = {
        value.value_id: np.asarray(value.rgb[::-1], dtype=np.float64) / 255.0
        for value in table.values}
    # Agregation H4: moyenne des repliques **par valeur**, avant tout ajustement et
    # toute metrique. Sans elle, la dispersion inter-repliques entre dans le plafond
    # d'acceptation (bloquant B3).
    fit_ids, fit_measured = aggregate_by_value(
        measured[keep], tuple(value_id for value_id, taken in zip(ids, keep) if taken))
    fit_reference = np.asarray([reference_by_id[value_id] for value_id in fit_ids])
    neutral_mask = np.array([value_id in neutral_ids for value_id in fit_ids], dtype=bool)

    # **La mesure brute a brute, story 5.23** (`EPIC5-ARB-82` decision 2). Elle est prise
    # sur **toutes** les pastilles temoins de la planche -- `keep` filtre le jeu
    # d'*ajustement*, ce qui est une autre question -- et sur les mesures **brutes**,
    # avant tout profil. C'est le meme tableau `measured` que le reste de la fonction:
    # une seconde passe d'echantillonnage relirait le meme raster pour rendre les memes
    # nombres, avec le risque que les deux jeux divergent un jour.
    sheet_witness_raw = witness_raw_mapping(measured, ids)
    raw_divergence = assess_raw_divergence(
        sheet_raw=sheet_witness_raw,
        # `None` et `{}` ne sont **pas** le meme cas et ne sont pas fondus ici: le premier
        # dit « aucune feuille de calibration lue par ce scan », le second « feuille lue,
        # bandeau inexploitable ». Un `or {}` ecrirait le second motif sur le premier
        # regime, qui est le regime nominal depuis 5.22.
        calibration_raw=(None if calibration_witness_raw is None
                         else dict(calibration_witness_raw)),
        # **Le motif, pris sur la mesure et non reconstruit ici** (`EPIC5-ARB-104`). Le
        # `dict(...)` ci-dessus normalise la mesure et perd l'attribut au passage: c'est
        # voulu -- la moitie qui sert au calcul reste un mapping ordinaire --, mais le
        # motif doit alors etre lu **avant** cette normalisation, sur l'objet transmis.
        calibration_band_reason=witness_band_reason_of(calibration_witness_raw),
        page_id=page_id or "", source_page_id=source_page_id or "",
        divergence_id=raw_divergence_id)

    divergence: DivergenceAssessment | None = None
    if transported:
        # **La correction est celle de la page de calibration, telle quelle.** Aucun
        # ajustement sur les pastilles de cette page: `EPIC5-ARB-57` l'interdit, et le
        # profil propre calcule par `assess_divergence` ne sert qu'a **mesurer** le
        # troisieme nombre du message de refus -- il n'est jamais retenu.
        profile = imported_profile
        divergence = assess_divergence(
            fit_measured, fit_reference, neutral_mask, imported_profile,
            page_id=page_id or "", source_page_id=source_page_id or "",
            correction_form_id=form_id, divergence_id=divergence_id,
            bypass=divergence_bypass)
        # **AUCUN refus ici, et c'est toute la story 5.23** (`EPIC5-ARB-82` decisions 1
        # et 4). Le bloc qui rendait `_decline(NOT_APPLIED_PAGE_DIVERGES, ...)` a ete
        # retire: la correction s'applique **quel que soit l'ecart mesure**, et l'ecart
        # sert a avertir.
        #
        # Ce qui a motive le retrait est mesure et non doctrinal. Sur le lot reel
        # `chendj-mat`, le 2026-08-17, code 5.22 complet: les planches sortaient non
        # corrigees pour un exces de +2,13 et +2,50 dE76 contre un seuil a 1,00 -- alors
        # que la correction refusee divise par 2,7 a 3,3 l'ecart au rush d'origine (16,48
        # dE76 sans correction, 4,93 a 6,05 avec, banc du 2026-08-11 sur la seule planche
        # dont les frames sources sont au depot). Refuser de passer de 16,5 a 6,0 parce
        # que deux feuilles different de 2,5 n'est pas un arbitrage prudent, c'est une
        # panne.
        #
        # `assess_divergence` **reste appelee** et son resultat reste publie au manifest:
        # `color-divergence-1` demeure enregistre et lisible (AC 6), c'est le vocabulaire
        # sous lequel les manifests deja ecrits declarent leurs planches. Ce qui a
        # disparu est sa **consequence**, pas sa mesure. `divergence_bypass` n'a donc plus
        # rien a contourner sur ce chemin; il continue de marquer `bypassed` sur la mesure,
        # ce que la garde de `io/scan_manifest` confronte a la demande explicite.
    else:
        try:
            # **La garde de conditionnement/rang, ici aussi** (deuxieme passe de revue,
            # `EPIC5-ARB-78`, 2026-08-14): ce regime local est celui ou une page s'ajuste
            # sur ses propres pastilles, donc une feuille vierge posee ici traverse
            # exactement les memes gardes geometriques qu'une page de calibration vierge
            # -- et jusqu'ici, rien n'appelait cette garde sur ce chemin. Non atteignable
            # depuis la CLI aujourd'hui (`fit_lot_correction_from_page` est le seul appele
            # en production, voir le Dev Agent Record), mais fonction publique par defaut
            # sur un chemin fragile: l'ancienne unique protection de ce regime
            # (`if acceptance.status != "applied"`, retiree par `EPIC5-ARB-78`) est
            # devenue inatteignable par ce meme diff, et cette fonction ne doit pas rester
            # sans garde structurelle pour autant.
            ensure_design_matrix_conditioned(fit_measured, source_page_id=page_id or "")
            profile = get_correction_form(correction_form_id)(
                fit_measured, fit_reference, neutral_mask)
        except UnderdeterminedAdjustmentSet as erreur:
            # Meme choix qu'a `fit_lot_correction_from_page`: le message specifique de la
            # garde levee (conditionnement/rang comme ci-dessus, ou cardinal insuffisant
            # pour la forme demandee) est **preserve**, jamais ecrase par un gabarit
            # generique.
            return _fail(FAILURE_UNDERDETERMINED_ADJUSTMENT, preset_id=patch_preset_id,
                         values_version=version, dispersion=dispersion,
                         clipping=clipping, warnings=input_warnings,
                         failure_message=str(erreur))
        except ValueError:
            # Sous-determination du jeu d'ajustement (`EPIC5-ARB-29` clause 5) d'une nature
            # non typee `UnderdeterminedAdjustmentSet` (aucune connue aujourd'hui, meme
            # remarque qu'a `fit_lot_correction_from_page`): message generique.
            return _fail(FAILURE_UNDERDETERMINED_ADJUSTMENT, preset_id=patch_preset_id,
                         values_version=version, dispersion=dispersion,
                         clipping=clipping, warnings=input_warnings)
    corrected = oetf(np.clip(profile.apply_linear(eotf(fit_measured)), 0.0, 1.0))
    # Les identifiants et la version de table sont passes a la metrique: c'est ce qui
    # rend `worst_value_id` et `per_value` exploitables, et une metrique calculee contre
    # une table archivee encore interpretable (`EPIC5-ARB-28`).
    acceptance = evaluate_acceptance(fit_measured, corrected, fit_reference,
                                     value_ids=fit_ids, values_version=version)
    per_channel = acceptance.detail.channel_relative_deviation_before_correction

    return PageCalibration(
        status=acceptance.status,
        values_version=version,
        patch_preset_id=patch_preset_id,
        profile=profile if acceptance.status == "applied" else None,
        acceptance=acceptance,
        replicate_dispersion_de76=dispersion,
        channel_relative_deviation_before_correction=tuple(float(v) for v in per_channel),
        clipping=clipping,
        failure_reason=acceptance.failure_reason,
        input_warnings=input_warnings,
        correction_form_id=form_id,
        correction_source=correction_source,
        correction_source_page_id=source_page_id,
        correction_chain_id=chain_id,
        # Les deux verdicts voyagent ensemble et ne se recouvrent pas: `acceptance`
        # ci-dessus est ce que cette planche a mesure contre le profil importe,
        # `chain_profile_acceptance` ce que le profil avait mesure le jour ou il a ete
        # ajuste. Confondre les deux ferait dire au manifest qu'une degradation datee
        # d'un autre jour a ete constatee sur cette feuille.
        chain_profile_acceptance=chain_acceptance,
        divergence=divergence,
        raw_divergence=raw_divergence,
    )


def chain_correction_from_document(document: dict, *,
                                   correction_requested: bool = True) -> LotCorrection:
    """La correction d'un lot, **reutilisee** depuis un profil de chaine. Story 5.22.

    `EPIC5-ARB-80` decision 1: le profil est ajuste **une fois par chaine** par
    `scan calibrate`, consigne dans le projet, puis reutilise pour tous les lots de la
    chaine. Cette fonction est le point ou le document relu redevient l'objet que le
    chemin de scan transporte deja -- `imported_profile` de `calibrate_page` --, donc
    **aucune** planche n'est ajustee sur ses propres pastilles (`AC 5`).

    Le type rendu est `LotCorrection` et non un type nouveau, et c'est ce qui rend le
    branchement petit: `_scanned_pages_for_output` et `derive_lot_calibration_status`
    le consomment sans une ligne de plus. Ce que le nom perd en exactitude -- ce n'est
    plus « la correction du lot » mais « celle de sa chaine » -- le champ
    `source_page_id` le rattrape: il designe la page de calibration qui a ajuste les
    coefficients, valeur que le profil porte et que la relecture rend.

    **`acceptance` reste `None`, deliberement.** Le verdict d'acceptation mesure au
    moment de la calibration vit dans le fichier de profil, et le republier *sous cette
    cle* l'attribuerait a **ce** scan: le manifest decrirait comme mesuree sur ce lot une
    grandeur mesuree un autre jour, sur une autre feuille. Un profil recharge ne
    remesure rien.

    **Ce qui change au bloquant `C2` de la revue: le verdict relu voyage quand meme, sous
    `imported_acceptance`.** La justification ci-dessus etait juste sur le fond et fausse
    sur la conclusion. La donnee existe, elle est serialisee, elle est datee de la
    calibration -- et sans relecture elle n'atteignait plus **aucun** artefact des que le
    lot etait corrige par profil de chaine, c'est-a-dire dans le regime nominal que cette
    story installe. Deux cles distinctes disent les deux faits sans les confondre:
    `acceptance` = « mesure sur ce scan », `imported_acceptance` = « mesure consignee dans
    le profil ». Une seule cle aurait force a choisir entre mentir et se taire.

    La provenance est **portee par l'objet** et non plus rededuite par ses consommateurs
    (bloquant `C3`): `correction_source` et `chain_id` disent d'ou vient cette correction,
    ce qui evite a `calibration_page_result` d'ecrire `own_sheet_patches` en litteral sur
    une feuille de calibration dont aucun pixel n'a servi.
    """
    return LotCorrection(
        source_page_id=document["source_page_id"],
        template_id=document["template_id"],
        profile=profile_from_document(document),
        correction_form_id=document["correction_form_id"],
        read_patch_count=document["read_patch_count"],
        retained_patch_count=document["retained_patch_count"],
        acceptance=None,
        imported_acceptance=acceptance_from_document(document.get("acceptance")),
        correction_source=CORRECTION_SOURCE_CHAIN_PROFILE,
        # Lu **dans le document** et non passe par l'appelant: le fichier de profil porte
        # deja `chain_id`, et le prendre en parametre ouvrirait un second emplacement pour
        # le meme fait -- celui ou un appelant nommerait une chaine et en chargerait une
        # autre, sans que rien ne le signale.
        chain_id=document["chain_id"],
        correction_requested=correction_requested,
        # **Les temoins bruts consignes dans le profil** (story 5.23, mesure du
        # 2026-08-18). C'est par eux que la divergence brute a brute redevient calculable
        # hors de la passe de scan qui a lu la page de calibration -- donc dans le regime
        # nominal de la calibration par chaine. Un profil ecrit avant cette mesure n'a pas
        # le champ: la fusion pure lui donne son defaut vide, et le manifeste declare
        # `raw_divergence_no_calibration_sheet`, qui reste vrai de lui.
        witness_raw_bgr=calibration_profile.witness_raw_of_document(document),
        # **Et le motif, quand le profil en porte un** (`EPIC5-ARB-104`). C'est lui qui
        # distingue « ce profil ne dit rien de son bandeau » -- ecrit avant la mesure, donc
        # `raw_divergence_no_calibration_sheet` reste vrai de lui -- de « sa page a ete lue
        # et son bandeau n'a rien donne, voici pourquoi ». Les deux rendaient jusqu'ici la
        # meme suite vide, et `calibration_witness_raw_for_lot` ne pouvait que les
        # confondre.
        witness_band_reason=calibration_profile.witness_band_reason_of_document(document),
    )


def correction_provenance_summary(result: PageCalibration) -> dict:
    """Forme **manifest** de la provenance de la correction. AC 10 et 15.

    Meme partage de responsabilite que `clipping_summary`, et pour le meme motif: la
    **forme** est declaree par la story qui produit la donnee, l'**ecriture** appartient
    a la story qui possede le manifest. Le schema livre par 5.7 declare
    `additionalProperties: true` sur les entrees de `page_calibration_results`, donc ces
    champs s'y ajoutent sans revision de schema -- ce qui est verifie par test et non
    suppose.

    Ce que le dictionnaire garantit, et qui est tout l'objet de l'AC 10: le champ de
    provenance est present dans les **deux** regimes et y porte des valeurs
    **differentes**. Un champ absent dans l'un des deux ne distingue rien -- il faut
    alors deviner, et deviner sur un manifest est ce que ce projet refuse partout
    ailleurs.

    La trace du contournement (AC 15) est **dans** le bloc de divergence et nulle part
    ailleurs: le drapeau et l'ecart qui l'a motive se lisent ensemble ou ne se lisent
    pas. Deux emplacements pour la meme donnee, ce sont deux verites.

    **Le motif d'echec est projete depuis la passe de correction de 5.19** (findings des
    couches 2 et 3). Il ne l'etait pas, et la consequence tenait en une phrase: une page
    refusee declarait `failed` sans dire **pourquoi**, le motif ne vivant que dans la
    console et `logs/scan.log`. Le seul artefact persistant ne disait donc pas quelle
    feuille rescanner ni ce qu'elle avait -- alors que le tutoriel livre par la story
    promettait le contraire, et que le schema declare le champ depuis 5.7. Il n'est
    present que sur un echec, ou il est le seul renseignement actionnable.
    """
    entry: dict = {
        "correction_source": result.correction_source,
        "correction_source_page_id": result.correction_source_page_id,
        "correction_form_id": result.correction_form_id,
    }
    if result.correction_chain_id is not None:
        # **La chaine de scan dont vient la correction** (story 5.22, AC 6 et 9). Sous
        # une cle a elle et seulement quand elle existe: absente, l'entree est
        # exactement celle d'avant la story, ce qui est la forme sous laquelle la
        # non-regression octet a octet de l'AC 7 peut tenir.
        #
        # Le `chain_id` suffit a **retrouver** le profil applique
        # (`versions/calibration/<chain_id>.json`), et c'est tout ce que le manifest en
        # dit: les coefficients vivent une seule fois, dans le fichier de profil. Deux
        # emplacements seraient deux verites, et celle du manifest vieillirait sans que
        # rien ne le signale.
        entry["correction_chain_id"] = result.correction_chain_id
    if result.chain_profile_acceptance is not None:
        # **Le verdict consigne dans le profil de chaine, republie** (bloquant `C2` de la
        # revue de 5.22). Sous une cle a lui, jamais fondu dans `distortion`: ce dernier
        # dit ce que la correction a deforme **sur cette page et lors de ce scan**,
        # celui-ci ce qu'elle deformait sur la feuille de calibration de la chaine, le
        # jour ou le profil a ete ajuste. Une seule cle aurait force a choisir entre
        # attribuer a ce scan une mesure qu'il n'a pas faite et ne rien publier -- et
        # « ne rien publier » etait l'etat de fait: douze grandeurs ecrites dans
        # `versions/calibration/<chain_id>.json` que `grep` ne trouvait relues nulle part.
        #
        # La forme est **exactement** celle du fichier, obtenue par le meme projecteur:
        # une seconde redaction ici divergerait a la premiere evolution du format, et le
        # symptome serait un manifest qui decrit le verdict d'un profil avec les champs
        # d'un autre. C'est la meme regle que ce module tient partout ailleurs.
        entry["chain_profile_acceptance"] = _acceptance_document(
            result.chain_profile_acceptance)
    if result.failure_reason is not None:
        entry["failure_reason"] = result.failure_reason
    if result.not_applied_reason is not None:
        # Sous une **cle differente** de `failure_reason`, et pas seulement sous une
        # valeur differente: un lecteur qui filtre les pages en echec le fait sur la
        # presence du champ d'echec, et y glisser un choix d'operateur ferait compter
        # comme panne un lot que personne n'a juge mauvais (`EPIC5-ARB-78`).
        entry["not_applied_reason"] = result.not_applied_reason
    acceptance = result.acceptance
    if acceptance is not None:
        # **Le budget de distorsion, publie** (`EPIC5-ARB-78`). Il etait calcule depuis la
        # story 5.20 et n'atteignait aucun artefact persistant -- finding verse au
        # `deferred-work.md` le meme jour, puis rendu bloquant par cet arbitrage: depuis
        # que le budget ne refuse plus rien, une mesure non publiee est une mesure non
        # faite. Aucun de ces champs n'a de plafond ici; ils disent ce que la
        # correction a deforme, et c'est au lecteur d'en juger.
        detail = acceptance.detail
        entry["distortion"] = {
            "budget_id": acceptance.distortion_budget_id,
            "mean_degradation_de76": acceptance.mean_degradation_de76,
            "max_neutral_degradation_de76": acceptance.max_neutral_degradation_de76,
            "max_degradation_de76": acceptance.max_degradation_de76,
            # **`worst_degradation_value_id` et `worst_neutral_value_id`, ajoutes a la
            # deuxieme passe de revue** (`EPIC5-ARB-78`, 2026-08-14): calcules depuis
            # `evaluate_page_acceptance` mais sans lecteur jusqu'ici -- sans eux, « la
            # plus grande degradation » n'etait pas actionnable, l'operateur ne pouvant
            # pas savoir quelle pastille regarder. Les deux vivent sur `detail`
            # (`PageAcceptanceResult`, la signature d'`EPIC5-ARB-28`) et non directement
            # sur `AcceptanceVerdict`, donc `None` quand `detail` lui-meme est absent --
            # un verdict construit a la main (tests) plutot que par `evaluate_acceptance`.
            "worst_degradation_value_id":
                detail.worst_degradation_value_id if detail is not None else None,
            "worst_neutral_value_id":
                detail.worst_neutral_value_id if detail is not None else None,
            "neutral_axis_channel_spread_8bit":
                acceptance.neutral_axis_channel_spread_8bit,
            # Les deux clauses enregistrees etaient-elles tenues ? Publie **a cote** des
            # mesures et jamais a leur place: un booleen seul redeviendrait le verdict
            # binaire que cet arbitrage retire, les mesures seules obligeraient chaque
            # lecteur a retrouver le registre pour les situer.
            "budget_met": acceptance.distortion_budget_met,
        }
    divergence = result.divergence
    if divergence is not None:
        entry["divergence"] = {
            "guard_id": divergence.divergence_id,
            "threshold_de76": divergence.threshold_de76,
            "excess_residual_de76": divergence.excess_residual_de76,
            "imported_residual_de76": divergence.imported_residual_de76,
            "own_residual_de76": divergence.own_residual_de76,
            "diverges": divergence.diverges,
            "bypassed": divergence.bypassed,
        }
        if divergence.reason is not None:
            entry["divergence"]["reason"] = divergence.reason
    raw_divergence = result.raw_divergence
    if raw_divergence is not None:
        # **L'ecart brut a brut, publie sous sa propre cle** (story 5.23, AC 2 et 4). A
        # cote de `divergence` et jamais a sa place: les deux nombres ne se comparent pas
        # -- ici un ecart entre deux feuilles mesurees sans aucune correction, la-bas un
        # exces de residu entre deux ajustements compares a la theorie -- et les publier
        # sous la meme cle ferait relire le 5,0 comme « le 1,0 releve », ce que la reserve
        # du registre `color-divergence-2` interdit mot pour mot.
        #
        # `mean_raw_de76` a `None` avec un `reason` est le regime « non mesure », et il se
        # distingue d'un ecart nul: un zero est la lecture de deux feuilles identiques.
        entry["raw_divergence"] = {
            "guard_id": raw_divergence.divergence_id,
            "threshold_de76": raw_divergence.threshold_de76,
            "mean_raw_de76": raw_divergence.mean_raw_de76,
            "exceeds": raw_divergence.exceeds,
            "paired_value_ids": list(raw_divergence.paired_value_ids),
            "excluded": [{"value_id": value_id, "reason": motif}
                         for value_id, motif in raw_divergence.excluded],
        }
        if raw_divergence.reason is not None:
            entry["raw_divergence"]["reason"] = raw_divergence.reason
    return entry


class GamutExpansionRefused(ValueError):
    """`gamut_map_id` inconnu du registre: echec motive, jamais un repli sur l'identite.

    Une expansion devinee est pire qu'aucune, et un repli produirait un resultat de
    calibration **qui ment** (AC 8).
    """


@dataclass(frozen=True)
class ExpansionClipping:
    """`expansion_clipped_pixel_count` d'`EPIC5-ARB-30` clause 4, par borne.

    **Diagnostic, sans seuil et sans verdict**, au meme titre que
    `channel_relative_deviation`. Refuser la page serait pire que la declarer: le
    letterbox papier ecrete **par construction** sur toute page 2.35:1, et un refus
    jetterait des planches parfaitement exploitables.

    **Distinct du verdict d'ecretage des sentinelles**, et l'arbitrage insiste: celui-la
    parle du gamut de l'imprimante, celui-ci des bornes numeriques de l'expansion. Deux
    grandeurs, deux noms, jamais un seul.

    Les cardinaux sont en **composantes** et non en pixels: un pixel dont un seul canal
    depasse est ecrete sur ce canal seul, et compter le pixel entier surestimerait.
    """

    below_zero_pixel_count: int
    above_one_pixel_count: int
    component_count: int

    @property
    def clipped_component_count(self) -> int:
        return self.below_zero_pixel_count + self.above_one_pixel_count

    @property
    def clipped(self) -> bool:
        return self.clipped_component_count > 0


def apply_correction_to_frames(zone_bgr, profile: AnyCorrectionProfile, gamut_map_id: str):
    """Appliquer `C` puis `G^-1` a une zone de frame. **Jamais dans l'autre ordre.**

    `EPIC5-ARB-2` invariant 1: `C` corrige une distorsion physique **mesuree**,
    `G^-1` inverse une transformation numerique **deliberee**, et l'ordre inverse
    amplifierait l'erreur residuelle par le gain de l'expansion.

    Cette story **applique** `G^-1`, elle ne le **definit pas**: la transformation et
    son inverse vivent dans le registre versionne de 5.10, resolus ici par
    identifiant. Un identifiant inconnu est un echec, pas un repli --
    `gamut-map-none-1` est en revanche une valeur presente et valide de premier rang,
    traitee en no-op **verifie** par le registre lui-meme.
    """
    from . import gamut_map as gamut_module

    try:
        mapping = gamut_module.get_gamut_map(gamut_map_id)
    except gamut_module.UnknownGamutMapError as error:
        raise GamutExpansionRefused(
            f"{FAILURE_UNKNOWN_GAMUT_MAP}: {gamut_map_id!r} absent du registre. "
            "Une expansion devinee est pire qu'aucune."
        ) from error

    corrected = apply_profile_to_image(zone_bgr, profile)
    expanded = mapping.expand(corrected)
    # Comptage des pixels ecretes **par borne**, avant l'ecretage. `EPIC5-ARB-30`
    # clause 4, et le cas n'est pas theorique: les bandes de letterbox d'un rush 2.35:1
    # posees dans une zone 16:9 sont a l'interieur d'`image_rect_mm`, donc dans la zone
    # frame, et elles sont **en papier nu** -- `drawImage` n'y ecrit aucun fond. Ces
    # pixels n'ont jamais subi `G`, donc `G^-1` les envoie au-dessus de 1. Sans ecretage,
    # un `astype(uint16)` replie 1,0114 sur 743, soit du quasi-noir: les bandes blanches
    # deviendraient noires et les noirs blancs, « une image plausible », sans exception.
    values = np.asarray(expanded, dtype=np.float64)
    clipping = ExpansionClipping(
        below_zero_pixel_count=int((values < 0.0).sum()),
        above_one_pixel_count=int((values > 1.0).sum()),
        component_count=int(values.size),
    )
    return np.clip(values, 0.0, 1.0), clipping


def apply_profile_to_image(image_bgr, profile: AnyCorrectionProfile):
    """Appliquer `C` seule a une image BGR, et rendre du sRGB encode dans [0, 1].

    Extraite pour que `color_pipeline` **delegue** au lieu de recopier l'EOTF: deux
    definitions de la fonction de transfert qui divergeraient rendraient la correction
    fausse d'un cote sans qu'aucun test des deux modules ne le voie.

    Le point d'ecretage a [0, 1] est **ici**, nomme, et non enfoui dans l'OETF:
    `EPIC5-ARB-30` en fait un point de decision.

    **Echelle par dtype, explicitee le 2026-08-11.** La version precedente ecrivait
    `scale = 65535.0 if dtype == uint16 else 255.0`, donc elle divisait par 255 une
    entree **flottante deja normalisee** -- silencieusement, en la traitant comme un
    quasi-noir. Or tout le reste de ce module travaille en flottant normalise
    (`eotf`, `oetf`, `apply_linear`), si bien que le cas le plus naturel d'appel depuis
    le module lui-meme etait celui qui se trompait. Les entiers portent desormais le
    maximum de leur type, les flottants sont pris tels quels et **verifies** dans
    [0, 1]: une entree hors bornes est une erreur nommee, pas un resultat plausible.
    """
    array = np.asarray(image_bgr)
    if np.issubdtype(array.dtype, np.integer):
        scale = float(np.iinfo(array.dtype).max)
        linear = eotf(array.astype(np.float64) / scale)
    else:
        values = array.astype(np.float64)
        if values.size and (values.min() < -1e-9 or values.max() > 1.0 + 1e-9):
            raise ValueError(
                "apply_profile_to_image attend un flottant deja normalise dans "
                f"[0, 1]; recu [{values.min():.4f}, {values.max():.4f}]. Une image "
                "codee en entier doit garder son dtype entier pour que son echelle "
                "soit deduite du type et non devinee.")
        linear = eotf(values)
    return oetf(np.clip(profile.apply_linear(linear), 0.0, 1.0))


def adjustment_and_neutral_masks(values):
    """Rendre (jeu d'ajustement, masque d'axe neutre) depuis des `PatchValue`.

    Passe par les **roles** et par l'API de la table, jamais par une enumeration
    (`EPIC5-ARB-29`, et AC 3c de 5.4b): une sentinelle injectee dans l'ajustement
    est un point ecrete par construction, elle tirerait toute la correction, et le
    symptome serait une correction **plausible** -- pas une erreur.
    """
    kept = [value for value in values if value.role != patch_values.ROLE_GAMUT_SENTINEL]
    neutral = np.array([value.role == patch_values.ROLE_NEUTRAL for value in kept],
                       dtype=bool)
    return tuple(kept), neutral
