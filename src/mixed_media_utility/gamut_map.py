"""Registre versionne des compressions de gamut `G` (story 5.10).

Pourquoi ce module existe
--------------------------
Le pilote CMJN **ecrete**: plusieurs valeurs sources saturees tombent sur la
meme encre, et cette perte est *plusieurs-vers-un*, donc aucune LUT ne
l'inverse. `G` deplace le contenu hors de ces zones **avant** l'impression, de
facon strictement monotone, pour que la perte cesse d'etre destructive.

La difference tient en une phrase, et elle est la raison d'etre du module:
l'ecretage concentre une perte **non bornee** aux extremites; la quantification
d'impression repartit une perte **bornee par `1/k`** uniformement sur tout le
domaine. Le plateau est ce qu'on supprime, la quantification est ce qu'on
borne.

Ce module **definit** `G` et son inverse analytique; il n'**applique** `G^-1` a
aucune image. L'expansion au scan, apres la correction `C` et avec ses modes
degrades, appartient a la story 5.4b. L'inverse est present ici comme
**definition de l'injectivite**: sans lui, la reversibilite ne serait pas
verifiable et l'invariant 3 d'EPIC5-ARB-2 resterait une affirmation.

Ce que le MVP achete, et ce qu'il n'achete pas
-----------------------------------------------
La compression livree, `gamut-map-lin-1`, est **affine par canal** et identique
sur les trois canaux. Elle ne traite donc **pas** l'ecretage de chrominance:
`(255, 0, 0)` devient `(240, 15, 15)`, toujours tres au-dela du gamut CMJN
atteignable, et le constat mesure d'EPIC5-ARB-2 -- 63,3 % des pixels utiles
hors de l'enveloppe des patchs -- n'est pas resorbe. Ce que le MVP achete est le
**mecanisme**: versionne, exactement reversible, declare au QR et au manifest,
teste. Pas le dimensionnement, qui suppose de connaitre la frontiere reelle du
gamut de l'imprimante -- c'est le mandat des sentinelles de 5.9, et a deux
echelons par axe (EPIC5-ARB-17b) elles **detectent** un ecretage sans le
localiser assez finement pour dimensionner `G` toutes seules.

Le defaut est l'identite, et ce n'est pas provisoire par negligence
--------------------------------------------------------------------
`DEFAULT_GAMUT_MAP = "gamut-map-none-1"` (EPIC5-ARB-15). La moitie
« decomprimer » vit dans la story 5.4b, **post-MVP**: un defaut comprimant
ferait imprimer, scanner et exporter des frames que **rien** ne decomprime --
visiblement delavees, sans qu'aucune etape n'echoue. La compression reelle
s'active donc explicitement, `--gamut-map gamut-map-lin-1`, pour les essais
d'impression et la planche de caracterisation. Le defaut bascule le jour ou
5.4b livre `G^-1`, et c'est une decision datee, pas un ajustement de dev.

Deux regles de quantification, et l'asymetrie est voulue
---------------------------------------------------------
Sur le chemin **identite**, la reduction 16 -> 8 bits reste la troncature
`>> 8` du contrat d'origine (`pdf_render`), **bit pour bit**: l'identite
bit-exacte est l'ancrage de non-regression le plus sur d'une restructuration
qui touche le seul chemin de pixels du PDF. Sur le chemin **comprime**,
l'arrondi est au plus proche, parce qu'une troncature y ajouterait un demi-code
de biais systematique que `1/k` amplifierait au retour. L'asymetrie est locale,
declaree ici, et testee des deux cotes.

Le registre n'est jamais edite en place
----------------------------------------
Modifier les parametres d'une compression, c'est **enregistrer un nouvel
identifiant** (invariant 5 d'EPIC5-ARB-2). Une planche imprimee doit rester
resolvable depuis son seul `gamut_map_id`: si les parametres derriere un
identifiant changeaient, toutes les planches deja tirees deviendraient
silencieusement inexpansibles. C'est aussi pourquoi aucun parametre numerique
n'est expose a la ligne de commande.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np

from .io.payload import (
    GAMUT_MAP_ID_MAX_LENGTH,
    GAMUT_MAP_ID_PREFIX,
    GAMUT_MAP_IDENTITY,
    validate_gamut_map_id,
)
from .numeric_guards import is_strict_int, is_strict_number

#: Facteur de compression minimal admis a la construction. `k = 0.5` double
#: deja le bruit du scanner **et** le pas de quantification au retour: en
#: dessous, l'expansion amplifierait plus de bruit qu'elle ne recupere
#: d'information. La borne est posee a la construction et non en revue.
MIN_COMPRESSION_FACTOR = 0.5

#: Defaut du MVP (EPIC5-ARB-15). Voir le docstring du module: il ne bascule
#: qu'une fois `G^-1` livree par la story 5.4b.
DEFAULT_GAMUT_MAP = GAMUT_MAP_IDENTITY

#: Profondeur du canal d'impression. Contrainte **externe**: reportlab passe
#: par PIL, qui ne transporte pas le RVB 16 bits. Ce plafond n'a rien a voir
#: avec la precondition 16 bits de la story 5.0, qui porte sur le chemin
#: **scan**, ou une troncature detruisait de l'information avant toute mesure.
PRINT_CHANNEL_MAX = 255

#: Dtype de travail **declare**: le module contractualise « la meme image
#: d'entree produit strictement le meme raster a chaque rendu », et un dtype
#: flottant implicite le casserait en silence selon la plateforme.
WORKING_DTYPE = np.float64


def _as_numeric(values, where: str) -> np.ndarray:
    """Convertir en tableau flottant, ou refuser -- jamais un `nan` silencieux.

    `np.asarray(None, dtype=float)` rend `nan` sans lever: la transformation
    aurait alors « fonctionne » sur une entree qui n'existe pas, et le defaut ne
    se verrait qu'a la serialisation ou a l'affichage, plusieurs etages plus loin.
    """
    try:
        array = np.asarray(values, dtype=WORKING_DTYPE)
    except (TypeError, ValueError) as error:
        raise GamutMapError(f"{where}: entree non numerique: {values!r}.") from error
    if array.size and not np.all(np.isfinite(array)):
        raise GamutMapError(
            f"{where}: entree non finie. Une valeur non finie traverserait la "
            "transformation sans lever et ne casserait qu'a la serialisation."
        )
    return array


class GamutMapError(ValueError):
    """Base attrapable des refus du registre de compressions."""


class UnknownGamutMapError(GamutMapError):
    """Identifiant de compression absent du registre.

    Jamais un repli silencieux sur l'identite: un repli produirait un
    `gamut_map_id` qui **ment** sur la transformation appliquee, et le seul
    symptome serait une expansion fausse au scan, des mois plus tard.
    """


@dataclass(frozen=True)
class GamutMap:
    """Une compression de gamut, avec son inverse exact et son cout chiffre.

    `G(x) = low + (high - low) * x` sur le domaine normalise [0, 1], identique
    sur les trois canaux -- donc **neutre en teinte**. L'axe neutre pese lourd
    dans le jeu d'ajustement (4 valeurs sur 10 en `patch-values-2`), et une
    compression qui deriverait la teinte ferait travailler la correction `C`
    contre `G`, sur les patchs memes qui la contraignent.

    L'inverse `G^-1(y) = (y - low) / (high - low)` est en **forme close**:
    l'injectivite est satisfaite par construction, pas par une verification
    numerique heureuse.

    Les trois derniers champs sont le **cout mesure** de l'entree, porte par
    l'entree elle-meme: les tests les lisent au lieu de recopier des litteraux,
    de sorte qu'enregistrer une compression plus agressive ne puisse pas passer
    sous une tolerance ecrite pour une autre.
    """

    gamut_map_id: str
    low: float
    high: float
    #: Ecart maximal d'un aller-retour sur la grille 8 bits, **en codes**,
    #: avant re-arrondi. Vaut `0.5 / k` par construction.
    round_trip_tolerance_codes: float
    #: Nombre de codes 8 bits d'entree qui entrent en collision apres
    #: quantification. Strictement positif des que `k < 1` (principe des
    #: tiroirs): 256 codes d'entree vers moins de 256 codes de sortie.
    collision_count_8bit: int
    description: str

    def __post_init__(self) -> None:
        try:
            # Contrat d'identifiant **consomme** de 5.9, pas redeclare ici: une
            # seule borne pour une meme donnee. L'exception est re-levee dans
            # la famille du module pour qu'un appelant du registre n'ait pas a
            # connaitre sa delegation -- une base attrapable qui laisse fuir
            # une autre hierarchie est un mensonge de contrat.
            validate_gamut_map_id(self.gamut_map_id)
        except Exception as error:
            raise GamutMapError(str(error)) from error
        for name, value in (("low", self.low), ("high", self.high)):
            if not is_strict_number(value):
                raise GamutMapError(
                    f"{self.gamut_map_id}: {name} doit etre un nombre, recu "
                    f"{value!r} (`True` est un `int`)."
                )
            if not 0.0 <= float(value) <= 1.0:
                raise GamutMapError(
                    f"{self.gamut_map_id}: {name} = {value!r} hors du domaine "
                    "normalise [0, 1]."
                )
        if self.high <= self.low:
            raise GamutMapError(
                f"{self.gamut_map_id}: high ({self.high}) doit etre "
                f"strictement superieur a low ({self.low}) -- sinon `G` n'est "
                "pas strictement monotone et n'est pas inversible."
            )
        if self.factor < MIN_COMPRESSION_FACTOR:
            raise GamutMapError(
                f"{self.gamut_map_id}: facteur de compression "
                f"{self.factor!r} sous le plancher {MIN_COMPRESSION_FACTOR}. "
                f"L'expansion amplifierait le bruit par {1 / self.factor:.2f}."
            )
        if (
            not is_strict_number(self.round_trip_tolerance_codes)
            or not math.isfinite(self.round_trip_tolerance_codes)
            or self.round_trip_tolerance_codes < 0
        ):
            raise GamutMapError(
                f"{self.gamut_map_id}: tolerance d'aller-retour invalide: "
                f"{self.round_trip_tolerance_codes!r}."
            )
        # La tolerance est confrontee a l'erreur **reellement mesuree** sur la
        # grille 8 bits, pas seulement declaree. Sans cela elle n'etait bornee
        # par rien: la porter a `inf` -- ou simplement de 0,57 a 5,7 -- rendait
        # le test d'aller-retour vacuement vrai, et le seul rempart chiffre du
        # cout de la compression devenait une donnee non gardee.
        measured = self._measured_round_trip_error()
        if self.round_trip_tolerance_codes < measured:
            raise GamutMapError(
                f"{self.gamut_map_id}: tolerance annoncee "
                f"{self.round_trip_tolerance_codes} inferieure a l'erreur "
                f"mesuree {measured:.6f} code sur la grille 8 bits."
            )
        if self.round_trip_tolerance_codes > 2.0 * measured + 0.01:
            raise GamutMapError(
                f"{self.gamut_map_id}: tolerance annoncee "
                f"{self.round_trip_tolerance_codes} disproportionnee face a "
                f"l'erreur mesuree {measured:.6f}. Une tolerance gonflee rend "
                "le test d'aller-retour vacuement vrai."
            )
        if not is_strict_int(self.collision_count_8bit) or self.collision_count_8bit < 0:
            raise GamutMapError(
                f"{self.gamut_map_id}: cardinal de collisions invalide: "
                f"{self.collision_count_8bit!r}."
            )

    def _measured_round_trip_error(self) -> float:
        """Erreur maximale d'aller-retour **mesuree** sur les 256 codes 8 bits.

        Vaut `0.5 / k` par construction pour une compression affine, et zero
        pour l'identite -- dont l'aller-retour 8 bits est exact. C'est la
        mesure, et non la formule, qui borne la valeur declaree: une entree
        future d'une autre forme n'a pas a suivre `0.5 / k`.
        """
        codes = np.arange(256, dtype=np.float64)
        printed = np.rint((self.low + self.factor * (codes / 255.0)) * 255.0)
        printed = np.clip(printed, 0, PRINT_CHANNEL_MAX)
        recovered = ((printed / 255.0) - self.low) / self.factor * 255.0
        return float(np.abs(recovered - codes).max())

    @property
    def factor(self) -> float:
        """Facteur `k = high - low`. `1/k` est le cout de l'expansion."""
        return float(self.high) - float(self.low)

    @property
    def is_identity(self) -> bool:
        """L'identite est une **valeur de premier rang**, pas un cas degrade.

        Elle declare qu'aucune compression n'a ete appliquee, ce qui est une
        information vraie et utile a l'expansion -- et c'est le defaut du MVP.
        """
        return self.low == 0.0 and self.high == 1.0

    def compress(self, values):
        """`G` sur le domaine normalise [0, 1]. Accepte un scalaire ou un tableau."""
        return self.low + self.factor * _as_numeric(values, "compress")

    def expand(self, values):
        """`G^-1`, inverse analytique exact. **Definition**, pas application.

        L'application au scan -- apres la correction `C`, avec ses modes
        degrades -- appartient a la story 5.4b.

        Hors de l'image de `G` -- c'est-a-dire hors `[low, high]` -- la fonction
        rend une valeur hors de `[0, 1]` plutot que de la ramener au bord: c'est
        volontaire et 5.4b devra en decider. Ecreter ici masquerait une mesure
        aberrante au lieu de la rendre visible, et le scan est justement la ou
        l'aberration signale un probleme.
        """
        return (_as_numeric(values, "expand") - self.low) / self.factor

    def to_print_8bit(self, array: np.ndarray) -> np.ndarray:
        """Appliquer `G` puis quantifier vers 8 bits, **une seule fois**.

        C'est le point unique de reduction de profondeur du chemin
        d'impression. Comprimer *apres* une reduction prealable serait le piege
        central de cette story: la quantification serait deja prise, `G` la
        comprimerait, et `G^-1` l'amplifierait par `1/k` -- le resultat
        compilerait, les aller-retours flottants passeraient, et le defaut
        n'apparaitrait qu'en bandes sur une image reelle.

        Sur le chemin identite la troncature `>> 8` d'origine est conservee bit
        pour bit; ailleurs l'arrondi est au plus proche. Voir le docstring du
        module pour le motif de l'asymetrie.
        """
        if not isinstance(array, np.ndarray):
            raise GamutMapError(
                f"Tableau attendu, recu {type(array).__name__}."
            )
        if array.dtype == np.uint8:
            source_max = 255
        elif array.dtype == np.uint16:
            source_max = 65535
        else:
            raise GamutMapError(
                f"Profondeur non geree pour l'impression: {array.dtype}. "
                "Attendu: 8 ou 16 bits par canal."
            )
        if self.is_identity:
            # Bit pour bit avec le contrat d'origine. Le raccourci n'est pas une
            # optimisation: passer par le flottant changerait la regle d'arrondi
            # (troncature -> plus proche) et donc les octets produits, sur le
            # chemin **nominal** du MVP.
            #
            # `.copy()` sur le cas 8 bits: sans lui la fonction rendait
            # **l'objet d'entree lui-meme**, si bien que la propriete, la
            # contiguite et l'accessibilite en ecriture du resultat differaient
            # entre les deux chemins d'une fonction dont toute la these est
            # qu'ils ne different que par l'arrondi.
            return array.copy() if source_max == 255 else (array >> 8).astype(np.uint8)
        normalised = array.astype(WORKING_DTYPE) / source_max
        compressed = self.compress(normalised)
        codes = np.rint(compressed * PRINT_CHANNEL_MAX)
        return np.clip(codes, 0, PRINT_CHANNEL_MAX).astype(np.uint8)


_IDENTITY = GamutMap(
    gamut_map_id=GAMUT_MAP_IDENTITY,
    low=0.0,
    high=1.0,
    round_trip_tolerance_codes=0.0,
    collision_count_8bit=0,
    description=(
        "Aucune compression. Valeur de premier rang et defaut du MVP "
        "(EPIC5-ARB-15): elle declare qu'aucune compression n'a ete appliquee."
    ),
)

_LINEAR = GamutMap(
    gamut_map_id="gamut-map-lin-1",
    low=0.06,
    high=0.94,
    # 0.5 / k = 0.5 / 0.88 = 0.5682 code; declaree a 0.57, arrondi au
    # centieme superieur, pour que la comparaison des tests ne porte pas sur
    # une egalite flottante exacte.
    round_trip_tolerance_codes=0.57,
    # Plage de sortie 15..240, soit 226 codes distincts sur 256: 30 collisions.
    collision_count_8bit=30,
    description=(
        "Compression affine par canal, identique sur R, G et B, donc neutre en "
        "teinte. k = 0.88, 1/k = 1.136. Sort le contenu des deux zones "
        "d'ecretage par canal -- saturation d'encrage et papier nu -- que les "
        "sentinelles de 5.9 instrumentent. Ne traite pas l'ecretage de "
        "chrominance: voir le docstring du module."
    ),
)

#: Registre en `MappingProxyType`: un dict nu laisserait substituer une
#: transformation a l'execution et contournerait tout le versionnement.
GAMUT_MAPS = MappingProxyType(
    {_IDENTITY.gamut_map_id: _IDENTITY, _LINEAR.gamut_map_id: _LINEAR}
)


def known_gamut_map_ids() -> tuple[str, ...]:
    """Identifiants du registre, l'identite en premier."""
    return tuple(GAMUT_MAPS)


def get_gamut_map(gamut_map_id: str) -> GamutMap:
    """Resoudre une compression par identifiant, ou refuser en nommant le vocabulaire."""
    try:
        return GAMUT_MAPS[gamut_map_id]
    except (KeyError, TypeError) as error:
        raise UnknownGamutMapError(
            f"Compression de gamut inconnue: {gamut_map_id!r}. Identifiants "
            f"connus: {', '.join(known_gamut_map_ids())}."
        ) from error


__all__ = [
    "DEFAULT_GAMUT_MAP",
    "GAMUT_MAPS",
    "GAMUT_MAP_ID_MAX_LENGTH",
    "GAMUT_MAP_ID_PREFIX",
    "GAMUT_MAP_IDENTITY",
    "MIN_COMPRESSION_FACTOR",
    "PRINT_CHANNEL_MAX",
    "WORKING_DTYPE",
    "GamutMap",
    "GamutMapError",
    "UnknownGamutMapError",
    "get_gamut_map",
    "known_gamut_map_ids",
]
