"""Metrique d'acceptation d'une page de calibration. `EPIC5-ARB-28`, verbatim.

Ce module existe **parce que l'arbitrage le nomme**. `EPIC5-ARB-28` donne le nom du
module, celui de la fonction, celui de la dataclasse de sortie, celui de l'exception
et la liste de ses champs -- « a ecrire telle quelle », son critere de suffisance etant
qu'un developpeur de 5.4b puisse l'ecrire *sans rouvrir une seule decision*. La revue
en trois couches du 2026-08-11 a constate que rien de tout cela n'existait (bloquant
B4): la metrique vivait dans `color_calibration`, sous d'autres noms, sans les champs
de tracabilite, et un `NaN` en entree rendait un statut **`applied`** avec
`mean_delta_e = nan` -- pire que le `passed=False` accidentel que l'arbitrage avait
precisement chiffre pour l'eviter.

**Pourquoi ici et pas dans `patch_values`**: `tests/unit/test_patch_values.py` interdit
a ce module toute fonction dont le nom contient `linear`, `lab`, `delta_e`, `convert`
ou `to_xyz`. La frontiere est voulue: `patch_values` declare des valeurs, il ne les
convertit pas.

**Seconde application de l'EOTF, assumee et declaree** (`EPIC5-ARB-28`, revue couche 1,
F4): la metrique linearise a son tour les triplets encodes qu'elle recoit. C'est
voulu -- elle contracte des valeurs **reencodees a l'etape 9** precisement pour mesurer
ce que l'export portera, et non un etat intermediaire que rien ne conserverait.
Consequence a connaitre: « un seul appel a l'EOTF » n'est pas un controle valide, il
y en a deux -- l'un dans la chaine de correction, l'autre ici. **Aucune troisieme
occurrence n'est legitime.**
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np

from .gamut_map import WORKING_DTYPE
from .numeric_guards import is_strict_int, is_strict_number

#: Seuils et coefficients de l'IEC 61966-2-1. Dupliques de `color_calibration` a
#: dessein: importer la chaine de correction depuis la metrique creerait un cycle, et
#: la metrique doit pouvoir etre relue seule. Un test verrouille l'egalite des deux
#: jeux de constantes -- deux fonctions de transfert qui divergeraient rendraient la
#: metrique fausse d'un cote sans qu'aucun test des deux modules ne le voie.
_EOTF_KNEE = 0.04045
_SLOPE, _OFFSET, _GAMMA = 12.92, 0.055, 2.4


class ColorMetricError(ValueError):
    """Entree invalide pour la metrique. `EPIC5-ARB-28`, nom donne par l'arbitrage.

    Existe pour que l'invalide soit **nomme**: sans elle, un jeu vide remontait un
    `ValueError` numpy nu (« zero-size array to reduction operation ») et un `NaN`
    ne remontait rien du tout -- il traversait la metrique et sortait en
    `mean_delta_e = nan` sous un statut `applied`.
    """


def eotf(encoded):
    """Encode sRGB [0, 1] -> lineaire. Seconde application declaree ci-dessus."""
    values = np.asarray(encoded, dtype=WORKING_DTYPE)
    return np.where(values <= _EOTF_KNEE,
                    values / _SLOPE,
                    ((values + _OFFSET) / (1.0 + _OFFSET)) ** _GAMMA)


#: Matrice sRGB D65 -> XYZ, **ecrite en ordre BGR** parce que c'est l'ordre de toute la
#: chaine. Chaque ligne est (coefficient B, coefficient G, coefficient R): la permuter
#: mentalement au moment de l'ecriture est l'erreur que cette forme evite.
SRGB_TO_XYZ_D65_BGR = np.array([
    (0.1804375, 0.3575761, 0.4124564),
    (0.0721750, 0.7151522, 0.2126729),
    (0.9503041, 0.1191920, 0.0193339),
], dtype=WORKING_DTYPE)

#: Blanc de reference D65, dans l'ordre X, Y, Z. **Memes chiffres que la premiere
#: implementation**, verifiee contre les valeurs CIE publiees a la deuxieme decimale:
#: un autre blanc de reference, meme plus precis, deplacerait toutes les distances et
#: donc les seuils, ce qui serait une revision d'`EPIC5-ARB-28` et pas un
#: deplacement de code.
_D65_WHITE = np.array([0.95047, 1.0, 1.08883], dtype=WORKING_DTYPE)

#: Constantes de la fonction de compression CIE L*a*b*.
_LAB_EPSILON = 216.0 / 24389.0
_LAB_KAPPA = 24389.0 / 27.0


def _lab_compress(ratio):
    return np.where(ratio > _LAB_EPSILON,
                    np.cbrt(ratio),
                    (_LAB_KAPPA * ratio + 16.0) / 116.0)


def lab_from_linear_bgr(linear_bgr):
    """sRGB **lineaire** en ordre BGR -> L*a*b* D65. Story 5.16.

    Ajoutee parce que la seconde forme de correction
    (`color-correction-lab-lightness-chroma-1`) **ajuste et applique** dans Lab, alors
    que tout le reste de la chaine travaille en lumiere lineaire (`EPIC5-ARB-25`). Elle
    a donc besoin de l'aller et du retour, et non de la seule projection depuis
    l'encode.

    Elle vit **ici** et non dans `color_calibration` pour la meme raison que la
    metrique y a ete deplacee le 2026-08-11: le blanc de reference, la matrice XYZ et
    les deux constantes de compression sont la definition de Lab, et deux definitions
    qui divergeraient rendraient la correction fausse d'un cote sans qu'aucun test des
    deux modules ne le voie. `lab_from_srgb_bgr` **delegue** desormais a cette
    fonction: la projection depuis l'encode est l'EOTF suivie de celle-ci, et l'ecrire
    deux fois etait la seule facon de les faire diverger.
    """
    xyz = np.asarray(linear_bgr, dtype=WORKING_DTYPE) @ SRGB_TO_XYZ_D65_BGR.T
    f = _lab_compress(xyz / _D65_WHITE)
    lightness = 116.0 * f[..., 1] - 16.0
    a = 500.0 * (f[..., 0] - f[..., 1])
    b = 200.0 * (f[..., 1] - f[..., 2])
    return np.stack((lightness, a, b), axis=-1)


def linear_bgr_from_lab(lab):
    """Inverse **exact** de `lab_from_linear_bgr`, verrouille par aller-retour.

    L'inverse de la compression est la branche cubique au-dessus d'`_LAB_EPSILON` et
    la branche affine en dessous, et le seuil s'exprime ici sur `f**3` et non sur le
    rapport: c'est le meme point de bascule vu de l'autre cote, et le prendre sur `f`
    deplacerait la frontiere de quelques 1e-3 dans les ombres -- exactement la zone ou
    le plancher d'encrage vit.

    **Sans cette fonction la forme Lab n'est pas applicable**: on saurait mesurer
    l'ecart et pas rendre le pixel corrige.
    """
    values = np.asarray(lab, dtype=WORKING_DTYPE)
    f_y = (values[..., 0] + 16.0) / 116.0
    f_x = f_y + values[..., 1] / 500.0
    f_z = f_y - values[..., 2] / 200.0
    f = np.stack((f_x, f_y, f_z), axis=-1)
    cubed = f ** 3
    ratio = np.where(cubed > _LAB_EPSILON, cubed, (116.0 * f - 16.0) / _LAB_KAPPA)
    xyz = ratio * _D65_WHITE
    return xyz @ np.linalg.inv(SRGB_TO_XYZ_D65_BGR).T


def lab_from_srgb_bgr(encoded_bgr):
    """sRGB **encode** en ordre BGR -> L*a*b* D65."""
    return lab_from_linear_bgr(eotf(encoded_bgr))


def delta_e76_srgb_d65(left_bgr, right_bgr):
    """`delta_e76_srgb_d65`: distance CIE76 entre deux triplets sRGB encodes BGR."""
    difference = lab_from_srgb_bgr(left_bgr) - lab_from_srgb_bgr(right_bgr)
    return np.sqrt((difference ** 2).sum(axis=-1))


#: Plancher au denominateur du diagnostic: rend la formule totale sans etre mordant en
#: pratique, la valeur d'ajustement la plus sombre etant `neutral-020`, a 20/255.
_DEVIATION_FLOOR = 1.0 / 255.0


def channel_relative_deviation(measured_raw_bgr, reference_bgr):
    """Le **diagnostic** d'`EPIC5-ARB-28.2`: sans seuil, sans verdict.

    Domaine **encode** -- « x % a cote du code imprime » n'a de sens pour un humain que
    la -- et entree **brute, avant correction**: sur un scan a dominante bleue de
    +10 %, la lecture brute rapporte +0,10 sur le canal bleu, soit l'information de
    reglage cherchee, tandis que la lecture corrigee rapporte ~0 puisque c'est
    exactement ce que `C` a enleve. Le diagnostic sert a regler la chaine, pas a
    controler `C`.

    Rend (moyenne des valeurs absolues par canal, detail par ligne).

    **Refuse `None` et tout non-fini, plutot que de le laisser se propager**
    (deuxieme passe de revue, `EPIC5-ARB-78`, 2026-08-14): `np.asarray(None,
    dtype=float)` vaut silencieusement `nan` en numpy -- pas une erreur -- et sans ce
    refus, `channel_relative_deviation(None, reference)` rendait `(nan, nan, nan)` sans
    lever, exactement la propagation silencieuse de non-finis que ce module combat
    partout ailleurs (voir `ColorMetricError`, `_validated`).
    """
    if measured_raw_bgr is None or reference_bgr is None:
        raise ColorMetricError(
            "channel_relative_deviation refuse une entree `None`: measured_raw_bgr et "
            "reference_bgr doivent tous deux etre des triplets ou tableaux de triplets "
            "finis. Sans ce refus, `np.asarray(None, dtype=float)` vaut silencieusement "
            "`nan` et le diagnostic ressortirait (nan, nan, nan) sans lever.")
    measured = np.asarray(measured_raw_bgr, dtype=WORKING_DTYPE)
    reference = np.asarray(reference_bgr, dtype=WORKING_DTYPE)
    if not np.isfinite(measured).all() or not np.isfinite(reference).all():
        raise ColorMetricError(
            "channel_relative_deviation refuse une entree non finie (NaN ou infini): "
            "un diagnostic ne doit jamais ressortir un resultat non fini sans le dire.")
    denominator = np.maximum(reference, _DEVIATION_FLOOR)
    relative = (measured - reference) / denominator
    per_channel = np.abs(relative).mean(axis=0) if relative.size else np.zeros(3)
    return tuple(float(value) for value in per_channel), relative


# ---------------------------------------------------------------------------
# Seuils: le registre versionne de l'entree d'acceptation
# ---------------------------------------------------------------------------

#: Plancher opposable a toute entree future. A `source_bit_depth = 8` un code vaut
#: ~0,4 % de l'echelle, soit `dE76 ~ 0,3` a `0,5` autour des tons moyens, et
#: `gamut-map-lin-1` multiplie ce pas par 1,136 a l'expansion. **Aucune entree
#: `color-acceptance-<n>` ne peut declarer un seuil inferieur a 1,0 dE76 tant que
#: `source_bit_depth` peut valoir 8**: en deca, la metrique mesurerait la
#: quantification.
ACCEPTANCE_THRESHOLD_FLOOR_DE76 = 1.0


class UnknownColorAcceptanceError(ValueError):
    """`acceptance_id` absent du registre. Jamais un repli sur un defaut."""


@dataclass(frozen=True)
class ColorAcceptance:
    """Une entree **versionnee** de seuils d'acceptation.

    Le rapport 2 entre le maximum et la moyenne est delibere: le critere doit echouer
    sur une erreur **systemique**, pas sur une pastille difficile. A 10 valeurs, une
    seule pese 10 % de la preuve.
    """

    acceptance_id: str
    max_mean_delta_e: float
    max_max_delta_e: float

    def __post_init__(self) -> None:
        for name in ("max_mean_delta_e", "max_max_delta_e"):
            value = getattr(self, name)
            if not is_strict_number(value):
                raise ValueError(
                    f"{self.acceptance_id}: {name} doit etre un nombre, recu "
                    f"{value!r}")
            if not np.isfinite(value):
                raise ValueError(
                    f"{self.acceptance_id}: {name} doit etre fini, recu {value!r}")
            if value < ACCEPTANCE_THRESHOLD_FLOOR_DE76:
                raise ValueError(
                    f"{self.acceptance_id}: {name} = {value} est sous le plancher de "
                    f"{ACCEPTANCE_THRESHOLD_FLOOR_DE76} dE76. En deca, la metrique "
                    "mesurerait la quantification et non la couleur.")
        if self.max_max_delta_e < self.max_mean_delta_e:
            raise ValueError(
                f"{self.acceptance_id}: le plafond du maximum "
                f"({self.max_max_delta_e}) ne peut pas etre sous celui de la moyenne "
                f"({self.max_mean_delta_e}).")


#: `color-acceptance-1`: moyenne 8 fois le plancher, maximum 16 fois.
COLOR_ACCEPTANCE_REGISTRY = MappingProxyType({
    "color-acceptance-1": ColorAcceptance(
        acceptance_id="color-acceptance-1",
        max_mean_delta_e=8.0,
        max_max_delta_e=16.0,
    ),
})

ACTIVE_COLOR_ACCEPTANCE_ID = "color-acceptance-1"


def get_color_acceptance(acceptance_id: str) -> ColorAcceptance:
    """Resoudre une entree de seuils, ou echouer explicitement."""
    try:
        return COLOR_ACCEPTANCE_REGISTRY[acceptance_id]
    except KeyError:
        raise UnknownColorAcceptanceError(
            f"Entree d'acceptation inconnue: '{acceptance_id}'. Entrees connues: "
            f"{', '.join(COLOR_ACCEPTANCE_REGISTRY)}. Un seuil devine est pire "
            "qu'aucun seuil."
        ) from None


# ---------------------------------------------------------------------------
# Story 5.16, AC 14 : le seuil de divergence entre une page et sa page de calibration
# ---------------------------------------------------------------------------

class UnknownDivergenceGuardError(ValueError):
    """`divergence_id` absent du registre. Jamais un repli sur un defaut.

    Symetrique d'`UnknownColorAcceptanceError`, et pour le meme motif: un seuil devine
    est pire qu'aucun seuil, parce qu'il produit un verdict que personne ne peut
    rattacher a une mesure.
    """


@dataclass(frozen=True)
class DivergenceGuard:
    """Une entree **versionnee** du seuil de divergence de page. `EPIC5-ARB-57`.

    Enregistree **au meme titre que les seuils d'acceptation** (AC 14), et pour la
    meme raison: une revision qui changerait le nombre sans changer l'identifiant
    changerait le sens de toutes les campagnes passees. `EPIC5-ARB-52` est le
    precedent exact -- un seuil tranche en passant y a produit un verdict inoperant.

    **Interdiction de poser la valeur en litteral au point d'usage**: la garde lit ce
    registre par identifiant, et un test de frontiere negatif verifie qu'aucun
    litteral de seuil ne reapparait dans `color_calibration`.

    Les deux champs de mesure ne sont pas decoratifs: ils sont ce qui permet de relire
    le seuil sans retrouver le banc. `null_distribution_max_de76` est le pire exces
    observe **entre pages qui ne divergent pas**, et `null_distribution_pairs` le
    cardinal sur lequel il est observe -- un maximum sur 42 couples et un maximum sur
    3 ne se lisent pas de la meme facon.
    """

    divergence_id: str
    #: Exces de residu, en dE76, au-dela duquel une page est declaree divergente.
    max_excess_residual_de76: float
    #: Pire exces mesure sur la distribution **nulle** (pages du meme tirage).
    null_distribution_max_de76: float
    #: Cardinal de couples de la distribution nulle.
    null_distribution_pairs: int
    #: Reserves de la mesure, portees **dans le code** et non seulement dans la story
    #: (exigence explicite de l'AC 14). Une reserve rangee dans un document se perd a
    #: la premiere reprise; ici elle est lue par le test qui epingle le registre.
    reservations: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("max_excess_residual_de76", "null_distribution_max_de76"):
            value = getattr(self, name)
            if not is_strict_number(value) or not np.isfinite(value) or value <= 0.0:
                raise ValueError(
                    f"{self.divergence_id}: {name} doit etre un nombre fini "
                    f"strictement positif, recu {value!r}")
        if not is_strict_int(self.null_distribution_pairs) or self.null_distribution_pairs < 1:
            raise ValueError(
                f"{self.divergence_id}: null_distribution_pairs doit etre un cardinal "
                f"positif, recu {self.null_distribution_pairs!r}")
        # Un seuil **sous** la distribution nulle refuserait des pages qui ne divergent
        # pas: c'est la seule facon de rendre la garde structurellement fausse, et elle
        # se verifie a la construction plutot qu'a la revue.
        if self.max_excess_residual_de76 <= self.null_distribution_max_de76:
            raise ValueError(
                f"{self.divergence_id}: le seuil {self.max_excess_residual_de76} dE76 "
                f"n'est pas au-dessus du pire exces de la distribution nulle "
                f"({self.null_distribution_max_de76} dE76). Un seuil sous la "
                "distribution nulle refuse des pages qui ne divergent pas.")
        if not self.reservations:
            raise ValueError(
                f"{self.divergence_id}: un seuil derive d'une mesure porte ses "
                "reserves. Sans elles, la valeur se relit comme un fait etabli.")


#: `color-divergence-1`: **1,0 dE76 d'exces de residu**. Derivation, mesuree par
#: `scripts/archive/research/divergence_threshold.py` sur les sept pages d'un meme tirage:
#: 42 couples, pire exces **+0,152 dE76** pour `color-correction-affine-matrix-1` et
#: **+0,358** pour `color-correction-lab-lightness-chroma-1`. Le seuil retenu est donc
#: pres de trois fois le pire exces observe, et 6,4 ecarts-types au-dessus de la
#: moyenne nulle de la forme Lab. Le maximum enregistre ici est celui de la **pire des
#: deux formes**: un seuil qui tiendrait pour l'une et pas pour l'autre exigerait un
#: seuil par forme, ce qui se decide, ne se subit pas.
DIVERGENCE_REGISTRY = MappingProxyType({
    "color-divergence-1": DivergenceGuard(
        divergence_id="color-divergence-1",
        max_excess_residual_de76=1.0,
        null_distribution_max_de76=0.358,
        null_distribution_pairs=42,
        reservations=(
            "La distribution nulle est mesuree sur UN SEUL tirage (sept pages "
            "imprimees et scannees ensemble): elle ne contient ni la variabilite "
            "entre deux jours ni celle entre deux rames de papier. Le seuil qui en "
            "derive est donc OPTIMISTE.",
            "AUCUNE page divergente n'a jamais ete mesuree. Le seuil est borne par "
            "le bas (la distribution nulle) et par le haut (la marge d'acceptation); "
            "rien ne dit de combien derive reellement une page imprimee avec une "
            "autre encre.",
            "La fenetre utile est etroite: le residu propre d'une page vaut ~7,1 "
            "dE76 et le plafond d'acceptation 8,0, donc au-dela de ~0,9 dE76 "
            "d'exces une page echoue a l'acceptation pour son seul residu. Si des "
            "faux positifs apparaissent, la reponse n'est PAS de relever ce nombre "
            "en silence mais de rouvrir la question du plafond d'acceptation.",
        ),
    ),
})

ACTIVE_DIVERGENCE_GUARD_ID = "color-divergence-1"


def get_divergence_guard(divergence_id: str) -> DivergenceGuard:
    """Resoudre une entree de seuil de divergence, ou echouer explicitement."""
    try:
        return DIVERGENCE_REGISTRY[divergence_id]
    except (KeyError, TypeError):
        raise UnknownDivergenceGuardError(
            f"Entree de divergence inconnue: '{divergence_id}'. Entrees connues: "
            f"{', '.join(DIVERGENCE_REGISTRY)}. Un seuil devine est pire qu'aucun "
            "seuil."
        ) from None


# ---------------------------------------------------------------------------
# Story 5.23 : la divergence se mesure BRUTE A BRUTE (`EPIC5-ARB-82`, decision 2)
# ---------------------------------------------------------------------------
#
# **Ce que cette section remplace, et pourquoi.** La garde `color-divergence-1`
# ci-dessus ne compare pas deux feuilles: elle compare deux **residus contre la
# theorie** (`patch_values`), et en tire un refus de corriger. Mesure du 2026-08-17 sur
# le lot reel `chendj-mat`: les planches d'images sortaient non corrigees pour un exces
# de +2,13 et +2,50 dE76 contre un seuil a 1,00, alors que la correction refusee divise
# par 2,7 a 3,3 l'ecart au rush d'origine (16,48 dE76 sans correction, 4,93 a 6,05 avec
# -- `analyse-2026-08-11-forme-de-la-correction-sur-le-contenu.md`).
#
# La grandeur ci-dessous est **differente**, et c'est le point: elle repond a la seule
# question qu'un operateur se pose -- « ces deux feuilles se comportent-elles pareil ? »
# -- en confrontant la mesure **brute** des memes pastilles temoins sur les deux
# feuilles. Aucune reference theorique, aucun profil de correction, aucun ajustement.

#: Motifs d'exclusion d'une valeur temoin de la moyenne. Enumeres et non rediges au
#: point d'usage: ils sont **rendus** a l'appelant, donc ils appartiennent au contrat.
RAW_EXCLUSION_ABSENT_SHEET = "absente de la planche d'images"
RAW_EXCLUSION_ABSENT_CALIBRATION = "absente de la page de calibration"
RAW_EXCLUSION_UNREADABLE_SHEET = "illisible sur la planche d'images"
RAW_EXCLUSION_UNREADABLE_CALIBRATION = "illisible sur la page de calibration"


@dataclass(frozen=True)
class ExcludedWitness:
    """Une valeur temoin **ecartee** de la moyenne, avec son motif.

    Elle existe parce qu'une moyenne calculee sur un sous-ensemble silencieux est un
    faux succes: deux feuilles dont une seule pastille sur dix-sept a ete lue rendraient
    un ecart parfaitement credible. Le motif est porte ici plutot que reconstitue par
    l'appelant -- « absente » et « illisible » ne se corrigent pas par le meme geste.
    """

    value_id: str
    reason: str


@dataclass(frozen=True)
class RawDivergenceMeasure:
    """Ecart brut moyen entre deux feuilles, et ce qui n'a pas pu y entrer."""

    #: Moyenne des dE76, sur les seules valeurs appariees.
    mean_delta_e76: float
    #: Valeurs effectivement appariees, **triees**. Le tri n'est pas cosmetique: cette
    #: sequence part au journal et au manifest, et un ordre d'iteration de `set` ou de
    #: `dict` ferait dependre une trace de la graine de hachage du processus.
    paired_value_ids: tuple[str, ...]
    #: Valeurs ecartees, triees par identifiant, chacune avec son motif.
    excluded: tuple[ExcludedWitness, ...]

    @property
    def paired_count(self) -> int:
        return len(self.paired_value_ids)


def _readable_triplet(value) -> "np.ndarray | None":
    """Le triplet est-il lisible ? Rend le vecteur BGR, ou ``None``.

    `None`, une forme qui n'est pas un triplet et un non-fini sont **le meme cas
    metier**: la pastille n'a pas ete lue. Les distinguer ici obligerait chaque
    appelant a refaire le tri, et l'un d'eux finirait par laisser passer le `nan` --
    exactement ce que `_validated` ferme sur l'autre chemin du module.
    """
    if value is None:
        return None
    try:
        triplet = np.asarray(value, dtype=WORKING_DTYPE)
    except (TypeError, ValueError):
        return None
    if triplet.shape != (3,) or not np.isfinite(triplet).all():
        return None
    return triplet


def raw_divergence_de76(
    *,
    sheet_raw: Mapping[str, tuple[float, float, float] | None],
    calibration_raw: Mapping[str, tuple[float, float, float] | None],
) -> RawDivergenceMeasure:
    """Ecart brut moyen en dE76 entre les temoins de deux feuilles. **Fonction pure.**

    Story 5.23 AC 2, `EPIC5-ARB-82` decision 2. Les deux mappings portent la mesure
    **sans aucune correction** des memes pastilles temoins -- celles de la planche
    d'images et celles de la page de calibration --, en sRGB encode, ordre **BGR**,
    comme `measured_raw` de `evaluate_page_acceptance`.

    **L'appariement se fait par identifiant de valeur, jamais par position**, et ce
    n'est pas une precaution de style: c'est la famille de defaut `M33` / `M25`, sept
    fois payee dans ce depot, et les deux feuilles n'ont aucune raison de presenter
    leurs pastilles dans le meme ordre -- l'une les pose en colonnes laterales, l'autre
    les lit apres son treillis. Un appariement positionnel rendrait un ecart parfaitement
    credible entre des couleurs differentes.

    **Aucun profil de correction n'intervient**, et la frontiere est structurelle et non
    declarative: ce module n'importe pas `color_calibration`, donc `apply_linear` est
    hors de portee de ce chemin.

    Une valeur absente d'une des deux feuilles ou illisible sur l'une des deux est
    **exclue de la moyenne et declaree** (jamais remplacee par zero: un zero est la
    lecture de deux feuilles identiques, pas celle d'une pastille non lue). Un jeu
    sans **aucune** paire leve plutot que de rendre une moyenne sur rien.
    """
    if not isinstance(sheet_raw, Mapping) or not isinstance(calibration_raw, Mapping):
        raise ColorMetricError(
            "sheet_raw et calibration_raw doivent etre des mappings "
            "value_id -> triplet BGR brut, recus "
            f"{type(sheet_raw).__name__} et {type(calibration_raw).__name__}")
    # Union triee des deux jeux: le balayage ne part **d'aucune des deux feuilles en
    # particulier**. Partir des cles de l'une rendrait invisibles les valeurs presentes
    # sur l'autre seulement, c'est-a-dire la moitie du cas « absente ».
    value_ids = tuple(sorted(set(sheet_raw) | set(calibration_raw)))
    paired: list[str] = []
    excluded: list[ExcludedWitness] = []
    distances: list[float] = []
    for value_id in value_ids:
        if value_id not in sheet_raw:
            excluded.append(ExcludedWitness(value_id, RAW_EXCLUSION_ABSENT_SHEET))
            continue
        if value_id not in calibration_raw:
            excluded.append(ExcludedWitness(value_id, RAW_EXCLUSION_ABSENT_CALIBRATION))
            continue
        left = _readable_triplet(sheet_raw[value_id])
        if left is None:
            excluded.append(ExcludedWitness(value_id, RAW_EXCLUSION_UNREADABLE_SHEET))
            continue
        right = _readable_triplet(calibration_raw[value_id])
        if right is None:
            excluded.append(
                ExcludedWitness(value_id, RAW_EXCLUSION_UNREADABLE_CALIBRATION))
            continue
        paired.append(value_id)
        distances.append(float(delta_e76_srgb_d65(left, right)))
    if not paired:
        raise ColorMetricError(
            "Aucune valeur temoin n'est lisible sur les deux feuilles a la fois "
            f"({len(excluded)} ecartee(s): "
            f"{', '.join(f'{item.value_id} ({item.reason})' for item in excluded)}). "
            "Une moyenne sur un jeu vide serait un chiffre sans donnee.")
    return RawDivergenceMeasure(
        mean_delta_e76=float(np.mean(np.asarray(distances, dtype=WORKING_DTYPE))),
        paired_value_ids=tuple(paired),
        excluded=tuple(excluded),
    )


class UnknownRawDivergenceGuardError(ValueError):
    """Identifiant d'entree de divergence brute inconnu."""


@dataclass(frozen=True)
class RawDivergenceGuard:
    """Seuil d'**avertissement** sur l'ecart brut moyen entre deux feuilles.

    Story 5.23 AC 6. Enregistree au meme titre que `DivergenceGuard`, et pour la meme
    raison: une revision qui changerait le nombre sans changer l'identifiant changerait
    le sens de toutes les campagnes passees.

    **Ce n'est pas la meme grandeur que `color-divergence-1`**, et confondre les deux
    est le seul risque reel de cette entree -- d'ou la reserve qui le dit, exigee a la
    construction comme les autres.

    **Ce seuil n'a jamais refuse une page et n'en refusera pas**: `EPIC5-ARB-82`
    decision 4 en fait un seuil d'avertissement. Au-dela, la commande avertit avec le
    chiffre et applique quand meme.
    """

    divergence_id: str
    #: Ecart brut moyen, en dE76, au-dela duquel la commande **avertit**.
    max_mean_raw_de76: float
    reservations: tuple[str, ...]

    def __post_init__(self) -> None:
        if not is_strict_number(self.max_mean_raw_de76) or \
                not np.isfinite(self.max_mean_raw_de76) or self.max_mean_raw_de76 <= 0.0:
            raise ValueError(
                f"{self.divergence_id}: max_mean_raw_de76 doit etre un nombre fini "
                f"strictement positif, recu {self.max_mean_raw_de76!r}")
        if not self.reservations:
            raise ValueError(
                f"{self.divergence_id}: un seuil qui n'a jamais ete confronte a une "
                "mesure porte ses reserves. Sans elles, la valeur se relit comme un "
                "fait etabli.")


#: `color-divergence-2`: **5,0 dE76 d'ecart brut moyen**. `EPIC5-ARB-82` decision 5.
#:
#: Ce nombre est un **point de depart tranche par Egan**, pas une derivation: la page de
#: calibration ne portait aucune valeur temoin avant cette story, donc l'ecart brut a
#: brute n'a jamais pu etre mesure une seule fois. Les seuls ordres de grandeur
#: disponibles viennent d'autres grandeurs et ne se transposent pas -- 16,48 dE76
#: d'ecart au rush sans correction, ~7,1 de residu propre d'une page, +2,13 et +2,50
#: d'exces de residu sur le lot qui a declenche l'arbitrage.
RAW_DIVERGENCE_REGISTRY = MappingProxyType({
    "color-divergence-2": RawDivergenceGuard(
        divergence_id="color-divergence-2",
        max_mean_raw_de76=5.0,
        reservations=(
            "Valeur PROVISOIRE. Elle n'a JAMAIS ete confrontee a un scan reel de la "
            "page de calibration amendee -- cette page ne porte de valeurs temoins que "
            "depuis cette story, donc aucun ecart brut a brut n'a jamais ete mesure "
            "dans ce depot. Le premier scan la confirmera ou la revisera.",
            "GRANDEUR DIFFERENTE de celle de `color-divergence-1`: ici un ECART BRUT "
            "entre deux feuilles mesurees sans aucune correction, la-bas un EXCES DE "
            "RESIDU entre deux ajustements compares a la theorie. Les deux nombres ne "
            "se comparent pas, et le 5,0 n'est en aucun cas « le 1,0 releve ».",
            "Aucune distribution nulle n'a ete mesuree: on ignore de combien deux "
            "feuilles du MEME tirage divergent en brut. Le seuil n'est donc borne par "
            "le bas par rien, et un faux positif est possible. La reponse ne serait PAS "
            "de relever ce nombre en silence mais de mesurer d'abord cette "
            "distribution, comme `color-divergence-1` l'a fait pour la sienne.",
            "Ce seuil n'est un seuil de REFUS sous aucun regime (`EPIC5-ARB-82` "
            "decision 4): au-dela, la correction s'applique quand meme et la commande "
            "avertit. Le relire comme un critere d'acceptation serait revenir a "
            "exactement ce que cette story corrige.",
        ),
    ),
})

ACTIVE_RAW_DIVERGENCE_GUARD_ID = "color-divergence-2"


def get_raw_divergence_guard(divergence_id: str) -> RawDivergenceGuard:
    """Resoudre une entree de divergence brute, ou echouer explicitement."""
    try:
        return RAW_DIVERGENCE_REGISTRY[divergence_id]
    except (KeyError, TypeError):
        raise UnknownRawDivergenceGuardError(
            f"Entree de divergence brute inconnue: '{divergence_id}'. Entrees "
            f"connues: {', '.join(RAW_DIVERGENCE_REGISTRY)}. Un seuil devine est pire "
            "qu'aucun seuil."
        ) from None


def raw_divergence_exceeds(
    mean_raw_de76: float,
    divergence_id: str = ACTIVE_RAW_DIVERGENCE_GUARD_ID,
) -> bool:
    """L'ecart brut moyen depasse-t-il le seuil ? **Comparaison strictement au-dessus.**

    La frontiere vit ici et nulle part ailleurs (AC 4): un ecart **egal** au seuil
    n'avertit pas, un ecart au-dessus avertit. L'ecrire une seconde fois au point
    d'usage est ce qui ferait diverger les deux redactions au premier mutant `>` / `>=`.
    """
    if not is_strict_number(mean_raw_de76) or not np.isfinite(mean_raw_de76):
        raise ColorMetricError(
            f"L'ecart brut moyen doit etre un nombre fini, recu {mean_raw_de76!r}. "
            "Un non-fini compare a un seuil rend toujours False, donc un silence.")
    return float(mean_raw_de76) > get_raw_divergence_guard(divergence_id).max_mean_raw_de76


class UnknownMaxDegradationGuardError(ValueError):
    """Identifiant d'entree de degradation maximale inconnu."""


@dataclass(frozen=True)
class MaxDegradationGuard:
    """Plafond d'avertissement sur la degradation **maximale toutes pastilles**.

    Story 5.23 AC 7, `EPIC5-ARB-82` decision 7. Le budget de distorsion
    (`color-distortion-budget-1`) ne plafonne que la degradation **moyenne** et le
    **maximum de l'axe neutre**; le maximum chromatique n'etait garde par rien, alors
    que c'est lui le vrai risque d'artefact visuel -- une pastille degradee de 15,8
    dE76 sur le profil ajuste au lot de reference.

    `observed_max_de76` n'est pas decoratif: c'est le pire maximum **deja mesure** dans
    ce depot, et un plafond pose en dessous mordrait sur tout ce qui a ete livre. La
    garde se relit avec lui ou pas du tout.
    """

    guard_id: str
    #: Degradation isolee, en dE76, au-dela de laquelle la commande **avertit**.
    max_degradation_de76: float
    #: Pire degradation isolee deja observee dans ce depot, toutes formes et toutes
    #: captures confondues.
    observed_max_de76: float
    reservations: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("max_degradation_de76", "observed_max_de76"):
            value = getattr(self, name)
            if not is_strict_number(value) or not np.isfinite(value) or value <= 0.0:
                raise ValueError(
                    f"{self.guard_id}: {name} doit etre un nombre fini strictement "
                    f"positif, recu {value!r}")
        # Meme invariant structurel que `DivergenceGuard` et `ColorDistortionBudget`, et
        # il se verifie a la construction plutot qu'a la revue: un plafond **sous** le
        # pire cas deja mesure avertirait sur les corrections que le depot livre et
        # valide, c'est-a-dire sur tout -- un avertissement permanent ne se lit plus.
        if self.max_degradation_de76 <= self.observed_max_de76:
            raise ValueError(
                f"{self.guard_id}: le plafond {self.max_degradation_de76} dE76 n'est "
                f"pas au-dessus de la pire degradation deja observee "
                f"({self.observed_max_de76} dE76). Sous elle, la garde avertit sur les "
                "corrections que le depot livre deja.")
        if not self.reservations:
            raise ValueError(
                f"{self.guard_id}: un plafond qui n'a jamais ete confronte a une "
                "mesure porte ses reserves. Sans elles, la valeur se relit comme un "
                "fait etabli.")


#: `color-max-degradation-1`: **25,0 dE76** de degradation isolee. Story 5.23 AC 7.
#:
#: Ce que le depot a deja mesure, et qui borne le plafond par le bas:
#:
#: * **+15,80** sur le profil reellement ajuste au lot de reference `chendj-mat`
#:   (2026-08-17), dont la degradation *moyenne* vaut pourtant -3,88 -- la correction
#:   ameliore en moyenne et abime une pastille;
#: * **+9,6 a +20,7** selon la forme et la capture, sur les trois captures et quatre
#:   formes de la story 5.20 (troisieme reserve de `color-distortion-budget-1`), le
#:   treillis portant des couleurs hors gamut CMJN dont le scan brut passe parfois pres
#:   de la reference par accident.
#:
#: Le plafond est donc pose **au-dessus de toute l'enveloppe mesuree**, et c'est
#: assume: aucun regime fautif n'a jamais ete observe, donc rien ne permet de poser la
#: frontiere entre « deforme » et « deforme trop ». Poser 16,0 ferait avertir sur le
#: profil que le depot livre, ce qui est un avertissement sur rien.
MAX_DEGRADATION_REGISTRY = MappingProxyType({
    "color-max-degradation-1": MaxDegradationGuard(
        guard_id="color-max-degradation-1",
        max_degradation_de76=25.0,
        observed_max_de76=20.7,
        reservations=(
            "Valeur PROVISOIRE. Elle n'a JAMAIS ete confrontee a un scan reel de la "
            "page de calibration amendee, ni a aucun regime que l'on saurait qualifier "
            "de fautif. Le premier scan la confirmera ou la revisera.",
            "AUCUNE correction visiblement fautive n'a jamais ete mesuree dans ce "
            "depot: le plafond est borne par le bas (l'enveloppe de +9,6 a +20,7 deja "
            "observee, dont le +15,80 du lot de reference) et par rien du tout par le "
            "haut. Il est donc INERTE sur tout ce qui a ete mesure a ce jour, et c'est "
            "un fait a connaitre avant de le lire comme une garantie.",
            "La grandeur est une degradation ISOLEE (une seule pastille), pas une "
            "moyenne: elle ne remplace ni `max_mean_degradation_de76` ni la clause de "
            "l'axe neutre de `color-distortion-budget-1`, elle garde ce qu'aucune des "
            "deux ne gardait -- le maximum chromatique.",
            "Si un faux positif apparait, la reponse n'est PAS de relever ce nombre en "
            "silence mais de mesurer la distribution des degradations isolees sur "
            "plusieurs tirages, qui n'existe pas.",
        ),
    ),
})

ACTIVE_MAX_DEGRADATION_GUARD_ID = "color-max-degradation-1"


def get_max_degradation_guard(guard_id: str) -> MaxDegradationGuard:
    """Resoudre une entree de degradation maximale, ou echouer explicitement."""
    try:
        return MAX_DEGRADATION_REGISTRY[guard_id]
    except (KeyError, TypeError):
        raise UnknownMaxDegradationGuardError(
            f"Entree de degradation maximale inconnue: '{guard_id}'. Entrees connues: "
            f"{', '.join(MAX_DEGRADATION_REGISTRY)}. Un seuil devine est pire qu'aucun "
            "seuil."
        ) from None


def max_degradation_exceeds(
    max_degradation_de76: float | None,
    guard_id: str = ACTIVE_MAX_DEGRADATION_GUARD_ID,
) -> bool:
    """La pire degradation isolee depasse-t-elle le plafond ? **Strictement au-dessus.**

    `None` -- la valeur par defaut de `PageAcceptanceResult.max_degradation_de76`, qui
    signale « rien n'a ete mesure » -- rend `False` **et c'est volontaire**: avertir sur
    une mesure absente serait inventer un chiffre. Le regime « rien n'a ete mesure » se
    signale ailleurs, par l'echec de calcul qui l'a produit.
    """
    if max_degradation_de76 is None:
        return False
    if not is_strict_number(max_degradation_de76) or \
            not np.isfinite(max_degradation_de76):
        raise ColorMetricError(
            f"La degradation maximale doit etre un nombre fini ou None, recu "
            f"{max_degradation_de76!r}. Un non-fini compare a un plafond rend toujours "
            "False, donc un silence.")
    return float(max_degradation_de76) > get_max_degradation_guard(
        guard_id).max_degradation_de76


# ---------------------------------------------------------------------------
# Story 5.20, AC 4 et 5 : le budget de distorsion, mesure de ce que la correction
# deforme -- et, depuis `EPIC5-ARB-78`, **information et non plus verdict**
# ---------------------------------------------------------------------------
#
# **Lire d'abord ceci, sinon tout ce qui suit se lit de travers.** Ce bloc a ete ecrit le
# 2026-08-13 pour un critere qui devait *remplacer* `color-acceptance-1` dans le role de
# critere bloquant. Le meme jour, apres la revue en trois couches, `EPIC5-ARB-78` a retire
# ce role au budget: ses deux plafonds sont toujours enregistres, toujours evalues et
# toujours publies (`distortion_budget_met`), mais **plus rien ici ne refuse une page**.
# La derivation des deux nombres reste consignee telle quelle -- elle est vraie, elle est
# ce qui rend les mesures relisables, et un plafond qu'on saurait un jour juger se
# retrouverait derive plutot que devine. Ce qui a change n'est pas la mesure, c'est sa
# consequence: on informe, on ne bloque plus.
#
# `EPIC5-ARB-72` retire a `color-acceptance-1` le role de critere qui commande
# `color_calibration_status`, sans le retirer du code: il reste un registre versionne,
# calcule et rapporte a chaque page, simplement plus bloquant. Le motif est mesure et non
# philosophique -- le scan Windows du 2026-08-13 affiche **15,42 dE76 de moyenne sans
# aucune correction**, donc le refus ne sanctionnait pas une correction defaillante mais
# l'ecart structurel entre un scanner grand public et une valeur theorique sRGB imprimee
# en CMJN non geree par profil. Le tirage qui a **valide** la methode le 2026-08-11 ne
# passait pas ce seuil non plus (11,66 dE76, rejoue le 2026-08-13): le critere n'a jamais
# ete celui qui a prouve que la methode marche.
#
# **Ce que le nouveau critere mesure, et pourquoi ce n'est pas litteralement
# `dE76(corrige, brut)`.** L'arbitrage suggere cette formule (« typiquement dE76(corrige,
# brut) par pastille, plafonne »), et elle a ete essayee avant d'etre ecartee, sur
# mesure: la correction d'un scan dont le niveau 8 se lit a 61 **doit** deplacer ce point
# de tres loin, et la distorsion brute mesuree sur les trois captures reelles vaut 14 a
# 33 dE76 de moyenne pour toutes les formes, y compris celles qui ne deforment rien
# d'utile. Un plafond sur cette grandeur interdirait de corriger l'ecrasement des noirs,
# c'est-a-dire exactement le defaut que la story 5.20 existe pour corriger.
#
# La grandeur retenue est la **degradation par pastille**:
#
#     degradation_i = dE76(corrige_i, reference_i) - dE76(brut_i, reference_i)
#
# Elle est negative quand la correction rapproche la pastille de sa reference, positive
# quand elle l'en eloigne. Par l'inegalite triangulaire elle **minore** dE76(corrige,
# brut): c'est la part du deplacement que l'erreur du scan brut ne justifie pas, donc
# litteralement « la distorsion introduite par la correction elle-meme ». Sur le motif
# direct d'`EPIC5-ARB-72` -- le blanc de marge lu correctement avant correction et
# effondre apres -- elle vaut exactement ce que l'oeil constate: sur la capture HP a
# reglage actif, la forme affine fait passer le blanc du treillis de 0,3 a 6,7 dE76 de sa
# reference, soit +6,4 de degradation.
#
# **Deux plafonds, sur deux familles, et la seconde n'est pas un raffinement mais la
# condition pour que le critere ait des dents.** Mesure sur les trois captures: la pire
# degradation **toutes pastilles confondues** vaut +9,6 a +20,7 dE76 pour *chacune* des
# formes essayees, y compris la meilleure -- parce que le treillis porte des couleurs que
# l'imprimante CMJN ne sait pas produire, dont le scan brut passe parfois pres de la
# reference par accident, et qu'aucune correction ne peut a la fois corriger le reste et
# ne pas les deplacer. Un plafond pose la refuserait tout ou n'attraperait rien. L'axe
# neutre, lui, est **dans le gamut par construction** -- un gris imprime est un gris
# atteignable --, donc c'est la seule famille sur laquelle une degradation par pastille
# separe une correction qui deforme d'une limite physique. C'est aussi la famille ou le
# defaut a ete vu: le blanc de marge et les gris.


class UnknownColorDistortionBudgetError(ValueError):
    """`budget_id` absent du registre. Jamais un repli sur un defaut.

    Meme motif qu'`UnknownColorAcceptanceError` et qu'`UnknownDivergenceGuardError`: un
    seuil devine produit un verdict que personne ne peut rattacher a une mesure.
    """


@dataclass(frozen=True)
class ColorDistortionBudget:
    """Une entree **versionnee** du budget de distorsion. `EPIC5-ARB-73`.

    Les deux plafonds ne portent ni sur la meme statistique ni sur la meme famille, et
    les confondre serait perdre l'un des deux:

    * `max_mean_degradation_de76` porte sur la **moyenne** de la degradation, sur
      **toutes** les valeurs du jeu. A zero, c'est `EPIC5-ARB-31` clause 2 **absorbee
      verbatim** -- « si `mean_delta_e` apres correction excede `mean_delta_e` avant, la
      page est `failed` » -- et non une garde parallele. C'est la reponse explicite que
      l'AC 4 de la story 5.20 demande: un seul mecanisme de non-degradation, dont
      l'ancien est desormais la clause de moyenne;
    * `max_neutral_degradation_de76` porte sur le **maximum** de la meme statistique,
      restreinte aux valeurs dont la reference est grise. C'est la clause nouvelle, et
      celle qui refuse le regime qu'`EPIC5-ARB-72` nomme.

    Les deux champs de mesure suivent la convention de `DivergenceGuard`, pour la meme
    raison: un seuil derive d'une mesure doit rester relisable sans retrouver le banc.
    """

    budget_id: str
    #: Plafond de la degradation **moyenne**, toutes valeurs. La tolerance numerique
    #: `DEGRADATION_TOLERANCE_DE76` s'y ajoute au point d'usage: une page parfaite laisse
    #: un residu de l'ordre de 1e-14 des deux cotes, et `1e-14 > 0` la ferait echouer.
    max_mean_degradation_de76: float
    #: Plafond de la degradation **maximale sur l'axe neutre**.
    max_neutral_degradation_de76: float
    #: Pire degradation neutre observee sur la distribution **nulle**.
    null_distribution_max_de76: float
    #: Cardinal de mesures de la distribution nulle.
    null_distribution_samples: int
    #: Reserves de la mesure, portees **dans le code** et non seulement dans la story.
    reservations: tuple[str, ...]

    def __post_init__(self) -> None:
        # L'identifiant d'abord: il **nomme** l'entree dans tous les messages qui suivent
        # et il est ce que le manifest publie. Vide, il rendrait un budget introuvable au
        # registre et un manifest illisible -- et les messages d'erreur ci-dessous
        # s'ouvriraient sur « : max_mean... ». Finding de revue de 5.20, ferme le
        # 2026-08-19.
        if not isinstance(self.budget_id, str) or not self.budget_id.strip():
            raise ValueError(
                f"budget_id doit etre une chaine non vide, recu {self.budget_id!r}. "
                "C'est par lui que le registre resout l'entree et que le manifest la "
                "republie: vide, le budget applique cesse d'etre relisable.")
        for name in ("max_mean_degradation_de76", "max_neutral_degradation_de76",
                     "null_distribution_max_de76"):
            value = getattr(self, name)
            if not is_strict_number(value) or not np.isfinite(value):
                raise ValueError(
                    f"{self.budget_id}: {name} doit etre un nombre fini, recu "
                    f"{value!r}")
        if self.max_mean_degradation_de76 < 0.0:
            raise ValueError(
                f"{self.budget_id}: max_mean_degradation_de76 = "
                f"{self.max_mean_degradation_de76} est negatif. Un plafond negatif "
                "exigerait que toute correction ameliore la page d'au moins cette "
                "quantite, ce qui n'est pas une garde de non-degradation mais une "
                "exigence de performance -- et elle refuserait une page deja juste.")
        if self.null_distribution_max_de76 <= 0.0:
            raise ValueError(
                f"{self.budget_id}: null_distribution_max_de76 doit etre strictement "
                f"positif, recu {self.null_distribution_max_de76!r}. Une distribution "
                "nulle a zero n'a pas ete mesuree, elle a ete supposee.")
        if not is_strict_int(self.null_distribution_samples) or \
                self.null_distribution_samples < 1:
            raise ValueError(
                f"{self.budget_id}: null_distribution_samples doit etre un cardinal "
                f"positif, recu {self.null_distribution_samples!r}")
        # Meme invariant structurel que `DivergenceGuard`, et il se verifie a la
        # construction plutot qu'a la revue: un plafond **sous** la distribution nulle
        # refuse des corrections qui ne deforment rien.
        if self.max_neutral_degradation_de76 <= self.null_distribution_max_de76:
            raise ValueError(
                f"{self.budget_id}: le plafond {self.max_neutral_degradation_de76} "
                f"dE76 n'est pas au-dessus de la pire degradation neutre de la "
                f"distribution nulle ({self.null_distribution_max_de76} dE76). Sous "
                "elle, la garde refuse des corrections qui ne deforment pas.")
        # `not self.reservations` seul laissait passer `("",)`: un tuple non vide de
        # chaines vides est « truthy », donc la garde etait satisfaite par une reserve qui
        # ne dit rien -- exactement le contournement qu'elle est censee fermer. Finding de
        # revue de 5.20, ferme le 2026-08-19.
        if not self.reservations or not all(
                isinstance(reserve, str) and reserve.strip()
                for reserve in self.reservations):
            raise ValueError(
                f"{self.budget_id}: un seuil derive d'une mesure porte ses reserves, et "
                "chacune est une chaine non vide. Sans elles, la valeur se relit comme "
                "un fait etabli; avec une reserve vide, elle se relit comme un fait "
                "etabli **et** documente.")


#: `color-distortion-budget-1`: moyenne a **zero** (plus la tolerance numerique) et
#: maximum de l'axe neutre a **2,5 dE76**. `EPIC5-ARB-73`.
#:
#: **Derivation du 2,5**, sur les trois captures reelles du 2026-08-13, quatre formes
#: (les deux du registre, la courbe seule, la courbe + chroma), en ajustement propre et
#: en transport croise:
#:
#: * distribution **nulle** -- les regimes ou aucune correction ne deforme l'axe neutre:
#:   les deux captures propres du meme tirage (`rush-bitch-4-scan2`, `scan-WIN`) en
#:   ajustement propre, et les deux sens de transport entre elles. Seize mesures, pire
#:   degradation neutre **+1,45 dE76**;
#: * regime **fautif** -- la capture HP a reglage actif (`12p5_test`), la plus deformee:
#:   la forme Lab y degrade l'axe neutre de +3,79 et la forme affine de **+6,43**, ce
#:   dernier etant litteralement le blanc du treillis qui passe de 0,3 a 6,7 dE76 de sa
#:   reference. C'est le motif d'`EPIC5-ARB-72`, mesure.
#:
#: Il y a donc un **intervalle vide entre 1,45 et 3,79**, et le seuil y est pose: 1,72
#: fois au-dessus du pire cas nul, 1,52 fois sous la plus faible observation fautive.
#: Poser 4,0 -- le rapport 2,8 d'`EPIC5-ARB-57` applique au nul -- laisserait passer la
#: forme Lab sur la capture la plus deformee a 0,21 dE76 pres, c'est-a-dire un verdict qui
#: bascule sur du bruit.
COLOR_DISTORTION_REGISTRY = MappingProxyType({
    "color-distortion-budget-1": ColorDistortionBudget(
        budget_id="color-distortion-budget-1",
        max_mean_degradation_de76=0.0,
        max_neutral_degradation_de76=2.5,
        null_distribution_max_de76=1.45,
        null_distribution_samples=16,
        reservations=(
            "La distribution nulle est mesuree sur UN SEUL tirage (`chendj-mat`, "
            "2026-08-13) et UN SEUL scanner physique. Elle ne contient ni la "
            "variabilite entre deux imprimantes ni celle entre deux rames de papier: "
            "le seuil qui en derive est OPTIMISTE.",
            "Le seuil est pose dans un intervalle vide entre 1,45 (pire cas nul) et "
            "3,79 (plus faible observation fautive). Cet intervalle tient a QUATRE "
            "formes et TROIS captures; une cinquieme forme pourrait le remplir, et la "
            "reponse ne serait alors PAS de relever le nombre en silence mais de "
            "rouvrir la question de la famille sur laquelle la degradation se mesure.",
            "La clause de maximum ne porte QUE sur l'axe neutre, et c'est une "
            "limitation mesuree, pas un choix de commodite: la pire degradation toutes "
            "pastilles confondues vaut +9,6 a +20,7 dE76 pour TOUTES les formes "
            "essayees, le treillis portant des couleurs hors gamut CMJN dont le scan "
            "brut passe parfois pres de la reference par accident. Une correction qui "
            "deformerait uniquement des couleurs saturees ne serait donc PAS attrapee "
            "par ce budget.",
            "`max_mean_degradation_de76 = 0.0` n'est pas un chiffre derive: c'est "
            "EPIC5-ARB-31 clause 2 reprise verbatim, absorbee ici pour qu'il n'y ait "
            "qu'un seul mecanisme de non-degradation au lieu de deux.",
        ),
    ),
})

ACTIVE_DISTORTION_BUDGET_ID = "color-distortion-budget-1"


def get_distortion_budget(budget_id: str) -> ColorDistortionBudget:
    """Resoudre une entree de budget de distorsion, ou echouer explicitement."""
    try:
        return COLOR_DISTORTION_REGISTRY[budget_id]
    except (KeyError, TypeError):
        raise UnknownColorDistortionBudgetError(
            f"Budget de distorsion inconnu: '{budget_id}'. Entrees connues: "
            f"{', '.join(COLOR_DISTORTION_REGISTRY)}. Un seuil devine est pire "
            "qu'aucun seuil."
        ) from None


def is_grey_reference(triplet) -> bool:
    """Le triplet de reference est-il gris ? **Derive de la reference, jamais declare.**

    La famille neutre du budget de distorsion se lit sur la donnee que la metrique a
    deja -- l'egalite des trois canaux de la **reference** --, et non sur un argument
    supplementaire que l'appelant fournirait. Un masque passe a cote serait une seconde
    verite: il pourrait desigher comme neutre une valeur qui ne l'est pas, et la clause
    de l'axe neutre jugerait alors une famille qui n'est pas celle qu'elle nomme.

    Egalite **exacte**: les references sont des entiers 8 bits divises par 255, donc
    trois canaux egaux le sont au bit pres. Une tolerance serait un seuil de plus, donc
    une entree d'arbitrage de plus.
    """
    values = np.asarray(triplet, dtype=WORKING_DTYPE)
    return bool(values[0] == values[1] == values[2])


#: Tolerance numerique de la garde de non-degradation d'`EPIC5-ARB-31` clause 2. Bornee
#: au niveau du bruit de calcul, et **ce n'est pas une tolerance perceptuelle**: une
#: page parfaite laisse un residu de l'ordre de 1e-14 des deux cotes, et `1e-14 > 0`
#: ferait echouer une page exacte. Une tolerance perceptuelle serait une revision de la
#: clause, donc une nouvelle entree numerotee, pas un detail d'implementation.
DEGRADATION_TOLERANCE_DE76 = 1e-9

#: Motifs d'echec de la metrique, nommes ici parce que c'est ici qu'ils se decident.
#:
#: `FAILURE_DEGRADES_RESIDUAL` **garde son nom et son sens** apres la story 5.20: il est
#: desormais emis par la clause de moyenne du budget de distorsion, qui est
#: `EPIC5-ARB-31` clause 2 absorbee verbatim. Le renommer aurait rendu illisibles les
#: manifests deja ecrits pour un fait qui n'a pas change.
#:
#: `FAILURE_METRIC` n'est **plus emis par cette fonction** depuis `EPIC5-ARB-72`: les
#: seuils absolus de `color-acceptance-1` sont calcules et rapportes
#: (`acceptance_thresholds_met`) mais ne commandent plus le statut. La constante reste
#: definie -- elle appartient au vocabulaire ferme de l'AC 8 de 5.4b et figure dans des
#: manifests deja ecrits. Elle servait aussi de motif de repli a
#: `fit_lot_correction_from_page` quand une evaluation echouait sans en nommer un; cet
#: usage a disparu avec `EPIC5-ARB-78`, l'evaluation ne pouvant plus echouer.
#:
#: **Depuis `EPIC5-ARB-78` (2026-08-13), aucun des trois n'est plus emis par cette
#: fonction**, et c'est le second changement de sens du module apres `EPIC5-ARB-72`. Les
#: deux clauses du budget de distorsion -- degradation moyenne et degradation maximale sur
#: l'axe neutre -- restent calculees et publiees, mais ne decident plus `applied`/`failed`:
#: Egan, arbitre du depot, ne peut pas juger un plafond en dE76 ni en codes 8 bits
#: (« Ces chiffres ne veulent rien dire pour moi »), et le seuil deja en vigueur
#: (`EPIC5-ARB-75`) s'est revele avoir une marge de **0,04 code** sur `12p5_test`,
#: c'est-a-dire du bruit de mesure a la frontiere reelle. Ce qui reste bloquant est
#: ailleurs et d'une autre nature: les echecs de **calcul** (page illisible, patchs
#: introuvables, jeu sous-determine, dpi invalide, page hors trois canaux), jamais un
#: jugement de couleur.
#:
#: Les trois constantes restent **definies et distinctes**: elles appartiennent au
#: vocabulaire ferme de l'AC 8 de 5.4b et figurent dans des manifests deja ecrits. Les
#: retirer rendrait illisible un document produit avant cet arbitrage, pour un fait qui
#: n'a pas change -- la mesure qui les a produits est toujours la, seule sa consequence a
#: change.
FAILURE_DEGRADES_RESIDUAL = "correction_degrades_residual"
FAILURE_METRIC = "acceptance_metric_failed"

#: La correction deforme l'axe neutre au-dela du budget enregistre. `EPIC5-ARB-73`.
#: **Informatif depuis `EPIC5-ARB-78`**: publie par `distortion_budget_met`, plus jamais
#: emis comme motif d'echec.
FAILURE_DISTORTION_BUDGET = "correction_distortion_exceeds_budget"


@dataclass(frozen=True)
class PageAcceptanceResult:
    """Sortie de la metrique. Champs donnes par `EPIC5-ARB-28`, dans son ordre.

    `values_version` et `acceptance_id` sont **reportes** et non recalcules: une
    metrique calculee contre une table archivee doit rester interpretable, et
    `sample_count` est ce qui rend la comparaison possible apres coup.
    """

    mean_delta_e: float
    max_delta_e: float
    worst_value_id: str
    per_value: tuple[tuple[str, float], ...]
    sample_count: int
    values_version: str
    acceptance_id: str
    passed: bool
    channel_relative_deviation_before_correction: tuple[float, float, float]
    channel_relative_deviation_before_correction_per_value: tuple[
        tuple[str, tuple[float, float, float]], ...]
    #: Residu **avant** correction, et motif d'echec. Hors signature d'origine: la
    #: garde de non-degradation d'`EPIC5-ARB-31` clause 2 a besoin du premier, et le
    #: vocabulaire d'echec de l'AC 8 de 5.4b a besoin du second. Les mettre ici plutot
    #: que dans une seconde dataclasse suit la raison deja tranchee pour le diagnostic
    #: 28.2: deux objets rendraient possible d'en archiver un sans l'autre.
    mean_delta_e_before_correction: float = 0.0
    failure_reason: str | None = None
    #: Ce que le budget de distorsion a mesure (story 5.20). Portes **a cote** des
    #: agregats absolus et jamais a leur place: les deux repondent a deux questions
    #: differentes -- « a quelle distance du theorique » et « de combien la correction
    #: eloigne-t-elle » -- et c'est la seconde qui commande le statut depuis
    #: `EPIC5-ARB-72`.
    distortion_budget_id: str = ""
    mean_degradation_de76: float = 0.0
    #: `None` quand le jeu ne porte **aucune** valeur de reference grise: la clause de
    #: l'axe neutre n'a alors rien mesure, ce qui n'est pas la meme chose qu'une
    #: degradation nulle. Publier `0.0` serait la meilleure lecture possible la ou rien
    #: n'a ete lu, le faux succes que ce module combat partout ailleurs.
    max_neutral_degradation_de76: float | None = None
    worst_neutral_value_id: str | None = None
    neutral_sample_count: int = 0
    #: Les seuils absolus de `color-acceptance-1` sont-ils tenus ? **Informatif depuis
    #: `EPIC5-ARB-72`**: il ne commande plus `passed`, mais il reste ce qui dit a quelle
    #: distance du theorique la page se trouve, donc il reste utile au manifest.
    acceptance_thresholds_met: bool = True
    #: La plus grande degradation **isolee**, toutes pastilles confondues -- neutres et
    #: chromatiques ensemble (`EPIC5-ARB-78`). Elle repond a la question qu'Egan a posee
    #: sans savoir y mettre un nombre (« il faut juste que la correction maximale possible
    #: soit bornee [...] je ne sais pas comment poser une valeur dessus »): elle est donc
    #: **publiee et jamais confrontee a un plafond**. La clause de l'axe neutre, elle,
    #: reste restreinte a la famille grise, et les deux ne se remplacent pas -- le treillis
    #: porte des couleurs hors gamut CMJN dont la degradation vaut +9,6 a +20,7 dE76 pour
    #: *toutes* les formes essayees, y compris les bonnes.
    #:
    #: **Defaut `None`, pas `0.0`** (deuxieme passe de revue, `EPIC5-ARB-78`, 2026-08-14):
    #: `evaluate_page_acceptance` calcule et transmet toujours une valeur reelle, donc ce
    #: defaut n'est jamais lu sur le chemin de production -- mais un `0.0` par defaut est
    #: exactement le faux succes que `neutral_axis_channel_spread_8bit` evite deux champs
    #: plus bas: zero est la lecture d'une degradation **mesuree et nulle**, pas d'une
    #: degradation non mesuree, et l'ecrire la ou rien n'a ete calcule serait la meme
    #: faute que ce module ferme partout ailleurs.
    max_degradation_de76: float | None = None
    worst_degradation_value_id: str = ""
    #: Les deux clauses du budget de distorsion sont-elles tenues ? **Informatif depuis
    #: `EPIC5-ARB-78`**, exactement au meme titre qu'`acceptance_thresholds_met` l'est
    #: depuis `EPIC5-ARB-72`: le budget reste calcule et publie, il ne decide plus. Le
    #: publier en booleen a cote de ses deux mesures est ce qui garde lisible « la
    #: correction sortait du budget » sur un manifest ou plus rien ne le refuse.
    #:
    #: **Defaut `None`, pas `True`** (deuxieme passe de revue, `EPIC5-ARB-78`,
    #: 2026-08-14): meme motif que `max_degradation_de76` ci-dessus -- `True` par defaut
    #: est la lecture la plus flatteuse possible (« budget tenu ») la ou rien n'a encore
    #: ete evalue, exactement dans l'esprit que `neutral_axis_channel_spread_8bit` evite.
    #: Jamais lu sur le chemin de production, ou cette valeur est toujours calculee.
    distortion_budget_met: bool | None = None


def _validated(name: str, mapping: Mapping[str, tuple[float, float, float]],
               expected_keys: tuple[str, ...] | None) -> tuple[str, ...]:
    """Verifier un mapping d'entree et rendre ses cles triees."""
    if not isinstance(mapping, Mapping):
        raise ColorMetricError(
            f"{name} doit etre un mapping value_id -> triplet BGR, recu "
            f"{type(mapping).__name__}")
    keys = tuple(sorted(mapping))
    if not keys:
        raise ColorMetricError(
            f"{name} est vide: une page sans pastille mesuree n'a pas de metrique. "
            "Un agregat sur un jeu vide serait un chiffre sans donnee.")
    if expected_keys is not None and keys != expected_keys:
        missing = sorted(set(expected_keys) - set(keys))
        extra = sorted(set(keys) - set(expected_keys))
        raise ColorMetricError(
            f"{name} n'a pas les memes value_id que les autres mappings. "
            f"Manquants: {missing or 'aucun'}; en trop: {extra or 'aucun'}. "
            "Comparer des valeurs differentes rendrait une distance sans sens.")
    for value_id in keys:
        triplet = np.asarray(mapping[value_id], dtype=WORKING_DTYPE)
        if triplet.shape != (3,):
            raise ColorMetricError(
                f"{name}[{value_id!r}] doit etre un triplet BGR, recu une forme "
                f"{triplet.shape}")
        if not np.isfinite(triplet).all():
            raise ColorMetricError(
                f"{name}[{value_id!r}] porte une valeur non finie ({triplet}). Un "
                "non-fini traverserait la metrique et sortirait en mean_delta_e = nan "
                "sous un statut de succes.")
    return keys


def evaluate_page_acceptance(
    *,
    measured: Mapping[str, tuple[float, float, float]],
    reference: Mapping[str, tuple[float, float, float]],
    measured_raw: Mapping[str, tuple[float, float, float]],
    values_version: str,
    acceptance_id: str = ACTIVE_COLOR_ACCEPTANCE_ID,
    distortion_budget_id: str = ACTIVE_DISTORTION_BUDGET_ID,
) -> PageAcceptanceResult:
    """Evaluer une page contre une entree d'acceptation. **Seul verdict du module.**

    Elle *evalue*, elle ne calcule pas seulement une distance: c'est ce que son nom
    porte, et c'est pourquoi `passed` en fait partie.

    Trois mappings et non deux: le critere porte sur la mesure **corrigee et
    reencodee** (`measured`), le diagnostic 28.2 sur la mesure **brute**
    (`measured_raw`). Memes cles pour les trois, meme refus des non-finis -- comparer
    des value_id differents rendrait une distance sans sens, et un non-fini rendrait un
    succes affiche sur un `nan`.

    **`passed` ne depend plus d'aucun seuil de couleur depuis le 2026-08-13**
    (`EPIC5-ARB-78`, second cycle de correct-course de la story 5.20). Cette fonction
    **mesure et publie**, elle ne refuse plus:

    * les seuils absolus de l'entree d'acceptation (`EPIC5-ARB-28`) sont calcules et
      rapportes -- `mean_delta_e`, `max_delta_e`, `acceptance_thresholds_met` -- et ils
      ont cesse de commander le statut a `EPIC5-ARB-72`: comparer un scan reel a une
      reference sRGB imprimee en CMJN non geree par profil confronte deux espaces
      incompatibles par nature, et le scan Windows du 2026-08-13 affiche 15,42 dE76 de
      moyenne **sans aucune correction**;
    * les deux clauses du **budget de distorsion** -- degradation moyenne (`EPIC5-ARB-31`
      clause 2 absorbee par `EPIC5-ARB-74`) et degradation maximale sur l'axe neutre
      (`EPIC5-ARB-75`) -- sont calculees et rapportees de meme, par
      `mean_degradation_de76`, `max_neutral_degradation_de76` et le booleen
      `distortion_budget_met`. Elles ont cesse de commander le statut a `EPIC5-ARB-78`,
      pour un motif different du precedent: l'arbitre du depot ne peut pas juger un
      plafond en dE76 (« Ces chiffres ne veulent rien dire pour moi »), et le seuil de
      1,5 code derive par la methode rigoureuse de l'epic a une marge mesuree de 0,04
      code sur `12p5_test`, c'est-a-dire du bruit;
    * s'y ajoute `max_degradation_de76`, la plus grande degradation isolee toutes
      pastilles confondues, qui n'a **jamais** eu de plafond et n'en aura pas.

    **`passed` vaut donc invariablement `True` ici, et `failure_reason` invariablement
    `None`.** Les deux champs sont conserves plutot que retires: ils appartiennent au
    contrat de sortie que `AcceptanceVerdict` et le manifest lisent, et le vocabulaire
    d'echec de l'AC 8 de 5.4b continue d'exister -- il est simplement **produit
    ailleurs**, par les echecs de calcul (page illisible, patchs introuvables, jeu
    sous-determine, dpi invalide, page hors trois canaux) qui, eux, restent bloquants.
    Un echec de calcul n'est pas un jugement de couleur: c'est la frontiere qu'
    `EPIC5-ARB-78` trace, et elle passe hors de cette fonction.
    """
    thresholds = get_color_acceptance(acceptance_id)
    budget = get_distortion_budget(distortion_budget_id)
    keys = _validated("measured", measured, None)
    _validated("reference", reference, keys)
    _validated("measured_raw", measured_raw, keys)

    corrected = np.asarray([measured[key] for key in keys], dtype=WORKING_DTYPE)
    expected = np.asarray([reference[key] for key in keys], dtype=WORKING_DTYPE)
    raw = np.asarray([measured_raw[key] for key in keys], dtype=WORKING_DTYPE)

    after = np.atleast_1d(delta_e76_srgb_d65(corrected, expected))
    before = np.atleast_1d(delta_e76_srgb_d65(raw, expected))
    mean_after, max_after = float(after.mean()), float(after.max())
    mean_before = float(before.mean())
    # A egalite, la premiere par ordre lexicographique de `value_id`: `keys` est deja
    # trie, et `argmax` rend le premier maximum -- donc deterministe par construction.
    worst_value_id = keys[int(np.argmax(after))]

    per_channel, relative = channel_relative_deviation(raw, expected)

    # Degradation par pastille: la statistique du budget de distorsion. Positive quand
    # la correction eloigne la pastille de sa reference, negative quand elle l'en
    # rapproche. `after` et `before` sont apparies **par position dans `keys`**, qui est
    # trie et partage par les trois mappings -- l'appariement est donc le meme que celui
    # que `_validated` verifie, et non un second appariement a maintenir.
    degradation = after - before
    mean_degradation = float(degradation.mean())
    # La plus grande degradation **isolee**, toutes familles confondues (`EPIC5-ARB-78`).
    # A egalite, la premiere par ordre lexicographique de `value_id`: meme regle de
    # determinisme que `worst_value_id`, `keys` etant trie et `argmax` rendant le premier
    # maximum.
    worst_degradation_position = int(np.argmax(degradation))
    max_degradation = float(degradation[worst_degradation_position])
    worst_degradation_value_id = keys[worst_degradation_position]
    # La famille neutre est **derivee de la reference** et non declaree par l'appelant:
    # une valeur est neutre si ses trois canaux de reference sont egaux. Deux sources
    # pour ce fait divergeraient, et c'est la clause du budget qui jugerait alors une
    # famille qui n'est pas celle qu'elle nomme.
    grey = np.asarray([is_grey_reference(reference[key]) for key in keys], dtype=bool)
    max_neutral_degradation: float | None = None
    worst_neutral_value_id: str | None = None
    if grey.any():
        neutral_degradation = degradation[grey]
        # A egalite, la premiere par ordre lexicographique: `keys` est trie et `argmax`
        # rend le premier maximum, donc le resultat est deterministe -- meme regle que
        # `worst_value_id`.
        position = int(np.argmax(neutral_degradation))
        max_neutral_degradation = float(neutral_degradation[position])
        worst_neutral_value_id = tuple(
            key for key, is_grey in zip(keys, grey) if is_grey)[position]

    # Les deux clauses du budget sont **evaluees et publiees**, jamais opposees a la page
    # (`EPIC5-ARB-78`). Elles gardent leur forme exacte -- meme comparaison, meme
    # tolerance numerique, meme regle « une clause ne juge que ce qu'elle a mesure »: un
    # jeu sans valeur grise laisse `max_neutral_degradation` a `None`, et l'absence de
    # mesure ne compte pas comme un depassement. Seule leur consequence a change.
    distortion_budget_met = bool(
        mean_degradation <= budget.max_mean_degradation_de76 + DEGRADATION_TOLERANCE_DE76
        and (max_neutral_degradation is None
             or max_neutral_degradation <= budget.max_neutral_degradation_de76))

    return PageAcceptanceResult(
        mean_delta_e=mean_after,
        max_delta_e=max_after,
        worst_value_id=worst_value_id,
        per_value=tuple((key, float(value)) for key, value in zip(keys, after)),
        sample_count=len(keys),
        values_version=values_version,
        acceptance_id=thresholds.acceptance_id,
        # Invariablement vrai depuis `EPIC5-ARB-78`: cette fonction mesure, elle ne
        # refuse plus. Le litteral est ecrit tel quel plutot que derive d'un `reason`
        # devenu toujours `None` -- une garde qu'aucune entree ne franchit, presentee
        # comme une garde, est l'un des quatre pieges nommes du 2026-08-12.
        passed=True,
        channel_relative_deviation_before_correction=per_channel,
        channel_relative_deviation_before_correction_per_value=tuple(
            (key, tuple(float(component) for component in row))
            for key, row in zip(keys, relative)),
        mean_delta_e_before_correction=mean_before,
        failure_reason=None,
        distortion_budget_id=budget.budget_id,
        mean_degradation_de76=mean_degradation,
        max_neutral_degradation_de76=max_neutral_degradation,
        worst_neutral_value_id=worst_neutral_value_id,
        neutral_sample_count=int(grey.sum()),
        acceptance_thresholds_met=bool(
            mean_after <= thresholds.max_mean_delta_e
            and max_after <= thresholds.max_max_delta_e),
        max_degradation_de76=max_degradation,
        worst_degradation_value_id=worst_degradation_value_id,
        distortion_budget_met=distortion_budget_met,
    )
