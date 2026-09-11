"""Table des valeurs theoriques des patchs de calibration (story 4.8).

Unique source de verite des valeurs imprimees sur les planches: le registre
de presets (story 4.7) reference des identifiants de cette table et n'en
copie jamais les triplets; la composition (4.1) lit les valeurs ici via le
registre. Module de donnees **pur**: aucune dependance image (cv2, PIL,
reportlab, numpy), c'est une table, pas un rendu.

Espace de definition (EPIC4-ARB-7)
----------------------------------
**sRGB D65, valeurs entieres 8 bits par canal**, enregistre dans la table
elle-meme (jamais suppose). Motifs instruits:

1. c'est l'unique espace que la chaine reelle sait exprimer aujourd'hui
   (reportlab pose du RGB device sans profil; les pilotes d'impression grand
   public supposent sRGB en l'absence de profil);
2. les valeurs 8 bits sont exactes, communicables et imprimables sans
   conversion — aucun arrondi cache entre la table et le PDF;
3. la conversion vers un espace lineaire ou Lab est une derivation
   deterministe de la definition sRGB (IEC 61966-2-1), documentable par 5.4;
   l'inverse (retrouver ce qui a ete imprime depuis un espace abstrait)
   exigerait de figer maintenant les decisions differees.

Equivalents informatifs: des valeurs lineaires ou Lab peuvent etre derivees
de la definition sRGB, a titre informatif seulement — elles sont **derivees,
jamais canoniques**, et ce module n'en implemente aucune (la formule de
linearisation appartient aux decisions differees a 5.4). La valeur canonique
est le triplet entier 8 bits, rien d'autre.

Ne jamais confondre avec ``target_colorspace``: l'espace des patchs decrit ce
qui est **imprime** sur la planche; ``target_colorspace`` (manifest + payload
QR) decrit la **cible de reconstruction du rush**. Les deux ne se melangent
jamais, ni dans le manifest, ni dans cette table (qui ne porte aucun champ de
cible de reconstruction).

Flux couleur de bout en bout, avec ses pertes (AC 3)
----------------------------------------------------
1. **Valeurs theoriques** (cette table, sRGB D65 8 bits) — su: exact, versionne.
2. **Rendu reportlab dans le PDF** — su: triplets poses en RGB device, sans
   profil ICC (aucune gestion ICC cablee dans la chaine POC); perdu: rien
   numeriquement, mais le PDF ne declare pas son espace — c'est la table qui
   fait foi via ``patch_preset_id``.
3. **Pilote d'impression** — conversion CMJN **non controlee** par le
   produit; perdu: la correspondance sRGB -> encre (gamut, engraissement du
   point); mesurable a posteriori uniquement via les patchs eux-memes.
4. **Papier** — su: rien; perdu: blanc du support, sechage, uniformite;
   mesurable via l'axe neutre repete sur la page.
5. **Scanner** — RVB, automatismes (exposition, balance) **non controles**
   par le produit; les hypotheses materiel ci-dessous bornent ce maillon;
   mesurable via les patchs de la meme page (correction page par page, 5.4).
6. **Lecture des patchs sur page redressee** (5.4) — les patchs sont
   echantillonnes apres homographie (4.3 / 5.2); la moyenne des patchs
   identiques d'une meme page fournit la mesure.

La LUT future corrige **scan -> reference**, ou la reference est la valeur
theorique dans son espace declare: peu importe cet espace tant qu'il est
unique, nomme et versionne ici. Cout assume: sRGB n'est ni l'espace du rush
(rec709 partage les primaires, pas la fonction de transfert) ni celui du
scanner.

Ce qui est explicitement differe a 5.4 (AC 5, decision 3 du 2026-08-02)
-----------------------------------------------------------------------
Pas de conversion couleur active, pas de profil ICC, pas de linearisation,
pas de metrique DeltaE, pas de mesure spectrale. Ces trous sont nommes ici
pour que 5.4 les retrouve; si ce module fixait l'un d'eux, il aurait
preempte 5.4 (critere de faute de la story).

Versionnement (AC 1, EPIC4-ARB-7)
---------------------------------
Toute modification de valeur est un **changement de version**, jamais une
edition en place: une planche imprimee declare (transitivement, via
``patch_preset_id`` -> preset -> version de table) les valeurs exactes de son
epoque. Une seule table active; les anciennes versions restent lisibles via
``get_patch_values_table``.

Cette garantie transitive impose une regle au registre 4.7 (revue 4.8): un
preset **fige la version litterale** de sa table a sa creation, jamais une
reference a ``ACTIVE_PATCH_VALUES_VERSION`` — sinon publier une v2 et
basculer la constante active rebrancherait les presets deja imprimes sur les
nouvelles valeurs, c'est-a-dire exactement l'edition en place que ce
versionnement interdit. Verrouille par test dans ``test_patch_presets.py``.

Les invariants de table (canaux entiers 8 bits bornes, identifiants et
triplets uniques, roles du vocabulaire ferme, prefixe de version
``patch-values-``) sont verifies **a la construction** des dataclasses
(``PatchValuesIntegrityError``): une future table v2 ne peut pas entrer dans
le registre en les violant, meme sans etre active.

Choix des ancres (piege 3): l'axe neutre s'arrete a 20 et 245 — jamais 0/0/0
(sature l'encrage: recouvrement total, engraissement non mesurable) ni
255/255/255 (papier nu: indiscernable d'une zone non imprimee, ecretage non
mesurable). Les primaires et secondaires sont volontairement desatures pour
rester dans le gamut atteignable d'une conversion CMJN non controlee: une
valeur hors gamut serait ecretee par le pilote et sa mesure ne contraindrait
plus la correction.

**Deux enonces sur les extremes purs coexistent, et ils ne se contredisent
pas** (story 5.9, EPIC5-ARB-3). Le paragraphe ci-dessus protege le **jeu
d'ajustement**: une valeur ecretee par le pilote n'y a rien a faire, elle
tirerait la correction vers un point que l'imprimante n'a jamais reproduit.
Le role ``gamut_sentinel`` fait exactement l'inverse, et c'est sa raison
d'etre: il **instrumente la frontiere** de ce gamut. Une sentinelle est
imprimee hors du gamut atteignable **deliberement**, parce que c'est la seule
facon de savoir ou l'imprimante cesse de distinguer — constat mesure le
2026-08-07: l'enveloppe convexe des 12 patchs de ``patch-values-1`` couvre
17,8 % du cube RVB, et des patchs tous interieurs au gamut sont par
construction incapables de mesurer l'ecretage.

La regle n'est donc pas supprimee, elle est **portee par le role**: aucune
valeur de role ``neutral_axis`` / ``primary`` / ``secondary`` ne vaut un
extreme pur, les valeurs de role ``gamut_sentinel`` le peuvent, et seulement
elles (verifie a la construction). La contrepartie mecanique est
``adjustment_values()`` / ``sentinel_values()``: une sentinelle ne peut pas
**atteindre** un jeu d'ajustement, ce n'est pas un filtre a poser.

Regle de lecture d'une sentinelle, a reprendre verbatim par la story de
calibration: *deux niveaux consecutifs d'une meme chaine mesures comme
indiscernables valent ecretage de cet axe; si l'indiscernabilite commence des
le couple in-gamut/mediane, l'ecretage est plus precoce que l'echelon median
et la localisation s'arrete la — le MVP ne pretend pas mieux.*
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from mixed_media_utility.numeric_guards import is_strict_int


#: Version active de la table (EPIC4-ARB-7: une seule active, les anciennes
#: conservees en lecture). Distincte du ``schema_version`` du manifest et du
#: payload: le prefixe ``patch-values-`` (impose a la construction) rend
#: toute confusion impossible.
#:
#: Bascule sur ``patch-values-2`` par EPIC5-ARB-21 (story 5.9): laisser la v1
#: active ferait mentir la constante des la premiere v2. La bascule est neutre
#: en production — ``active_table()`` n'a aucun appelant dans ``src/`` et
#: chaque preset epingle sa version **en litteral** —, donc aucune planche
#: imprimee n'est rebranchee.
ACTIVE_PATCH_VALUES_VERSION = "patch-values-2"

#: Prefixe obligatoire de toute version de table (anti-confusion avec les
#: ``schema_version`` du manifest et du payload, impose a la construction).
PATCH_VALUES_VERSION_PREFIX = "patch-values-"

ROLE_NEUTRAL = "neutral_axis"
ROLE_PRIMARY = "primary"
ROLE_SECONDARY = "secondary"
#: Role ajoute par la story 5.9 (EPIC5-ARB-3). Une sentinelle est imprimee
#: **hors** du gamut CMJN atteignable, exactement a l'inverse des trois autres
#: roles: elle n'ajuste rien, elle mesure ou l'imprimante cesse de distinguer.
ROLE_GAMUT_SENTINEL = "gamut_sentinel"
#: Role ajoute par la story 5.16 (`EPIC5-ARB-54`). Une valeur de treillis n'est
#: imprimee **que sur la page de calibration dediee**, jamais sur une planche
#: d'images: c'est le jeu d'ajustement externe sur lequel la correction du lot
#: est ajustee. Elle n'appartient a **aucune** version de table -- les tables
#: decrivent ce qui est imprime a cote des frames -- et c'est pourquoi le
#: treillis est **derive** (``calibration_lattice_values()``) et non enregistre:
#: 125 valeurs entreraient dans un registre versionne pour n'y jamais servir de
#: reference de planche.
ROLE_CALIBRATION_LATTICE = "calibration_lattice"
#: Les quatre roles que porte une **table** de valeurs. Distingues du vocabulaire
#: complet ci-dessous: le treillis est un cinquieme role, mais aucune table ne le
#: contient, et confondre les deux ferait croire qu'une planche peut porter du
#: treillis.
_TABLE_ROLES = (ROLE_NEUTRAL, ROLE_PRIMARY, ROLE_SECONDARY, ROLE_GAMUT_SENTINEL)
_KNOWN_ROLES = (*_TABLE_ROLES, ROLE_CALIBRATION_LATTICE)

#: Saturation d'encrage (recouvrement total) et papier nu. Nommes ici parce
#: que c'est le seul module autorise a ecrire un triplet: le registre de
#: presets doit pouvoir raisonner dessus sans en recopier un seul.
INK_SATURATION_BLACK_RGB = (0, 0, 0)
PAPER_WHITE_RGB = (255, 255, 255)

#: Les deux extremes purs du cube RVB. Interdits a tout role **sauf**
#: ``gamut_sentinel`` — voir les deux enonces coexistants du docstring de
#: module.
_PURE_EXTREMES = (INK_SATURATION_BLACK_RGB, PAPER_WHITE_RGB)


class UnknownPatchValuesVersionError(ValueError):
    """Raised when a table version is not part of the known registry."""


class UnknownPatchValueError(ValueError):
    """Raised when a value id does not exist in the requested table."""


class SentinelInAdjustmentSetError(ValueError):
    """Raised when a gamut sentinel is presented as an adjustment value.

    The single most dangerous mistake this module can let through (story 5.9,
    AC 6). A sentinel is clipped **by construction** -- that is its entire
    purpose. Feeding one to the correction fit would drag the whole LUT toward
    a value the printer never reproduced, and the symptom would be a plausible
    correction, not an error. Hence a guard that refuses, rather than a filter
    the caller has to remember to apply.
    """


class PatchValuesIntegrityError(ValueError):
    """Raised when a value or table violates the construction invariants.

    Les invariants sont verifies a la construction et non seulement par les
    tests de la table active (revue 4.8): une table v2 archivee ou future qui
    porterait un canal hors bornes, un identifiant duplique ou un triplet
    duplique doit echouer au moment ou elle est definie, pas rester resolvable
    en silence par ``get_patch_values_table``.
    """


@dataclass(frozen=True)
class PatchValue:
    """One theoretical reference value, canonical in the table's declared space."""

    value_id: str
    rgb: tuple[int, int, int]
    role: str
    note: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.value_id, str) or not self.value_id:
            raise PatchValuesIntegrityError(
                f"value_id doit etre une chaine non vide, recu {self.value_id!r}"
            )
        if not isinstance(self.rgb, tuple) or len(self.rgb) != 3:
            raise PatchValuesIntegrityError(
                f"rgb doit etre un triplet (r, g, b), recu {self.rgb!r} "
                f"pour '{self.value_id}'"
            )
        for channel in self.rgb:
            if not is_strict_int(channel) or not 0 <= channel <= 255:
                raise PatchValuesIntegrityError(
                    f"Canal hors du domaine entier 8 bits [0, 255]: {channel!r} "
                    f"dans '{self.value_id}' (EPIC4-ARB-7)"
                )
        if self.role not in _KNOWN_ROLES:
            raise PatchValuesIntegrityError(
                f"Role inconnu: {self.role!r} pour '{self.value_id}'. Vocabulaire "
                f"ferme: {', '.join(_KNOWN_ROLES)}"
            )
        # La regle « pas d'extreme pur » n'est pas supprimee par la story 5.9,
        # elle devient **portee par le role**: elle protege le jeu
        # d'ajustement, et les sentinelles sont precisement ce qui instrumente
        # sa frontiere. Sans cette garde, la levee de l'interdiction pour les
        # sentinelles l'aurait levee pour tout le monde.
        if self.rgb in _PURE_EXTREMES and self.role != ROLE_GAMUT_SENTINEL:
            raise PatchValuesIntegrityError(
                f"Extreme pur {self.rgb} interdit au role '{self.role}' "
                f"('{self.value_id}'): 0/0/0 sature l'encrage et 255/255/255 est "
                f"indiscernable du papier nu, donc ni l'un ni l'autre ne contraint "
                f"une correction. Seul le role '{ROLE_GAMUT_SENTINEL}' les porte, "
                "et pour mesurer l'ecretage, pas pour ajuster."
            )


@dataclass(frozen=True)
class PatchValuesTable:
    """A versioned, immutable table of theoretical patch values.

    ``color_space`` / ``white_point`` / ``bits_per_channel`` declare the
    definition space **in the table itself** (AC 2): a reader never has to
    assume it.
    """

    version: str
    color_space: str
    white_point: str
    bits_per_channel: int

    #: Enumeration **brute** de la table. Ce n'est **jamais un jeu
    #: d'ajustement**: depuis la story 5.9 elle contient des sentinelles de
    #: gamut, ecretees par construction, dont l'injection dans l'ajustement de
    #: la correction tirerait toute la LUT vers une valeur que l'imprimante n'a
    #: jamais reproduite -- et le symptome serait une correction plausible, pas
    #: une erreur. Pour ajuster une correction, appeler ``adjustment_values()``;
    #: pour detecter un ecretage, ``sentinel_values()``.
    values: tuple[PatchValue, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.version, str) or not self.version.startswith(
            PATCH_VALUES_VERSION_PREFIX
        ):
            raise PatchValuesIntegrityError(
                f"Version de table invalide: {self.version!r}. Le prefixe "
                f"'{PATCH_VALUES_VERSION_PREFIX}' est obligatoire (anti-confusion "
                "avec les schema_version du manifest et du payload)."
            )
        if not is_strict_int(self.bits_per_channel) or self.bits_per_channel < 1:
            raise PatchValuesIntegrityError(
                f"bits_per_channel invalide: {self.bits_per_channel!r}"
            )
        if not isinstance(self.values, tuple) or not self.values:
            raise PatchValuesIntegrityError(
                f"Une table de valeurs ne peut pas etre vide ({self.version})"
            )
        ids = [value.value_id for value in self.values]
        if len(ids) != len(set(ids)):
            duplicates = sorted({vid for vid in ids if ids.count(vid) > 1})
            raise PatchValuesIntegrityError(
                f"value_id duplique(s) dans la table {self.version}: "
                f"{', '.join(duplicates)}. get() resoudrait la premiere occurrence "
                "en masquant l'ambiguite."
            )
        triplets = [value.rgb for value in self.values]
        if len(triplets) != len(set(triplets)):
            raise PatchValuesIntegrityError(
                f"Triplet duplique dans la table {self.version}: deux identifiants "
                "pour la meme valeur rendraient la mesure 5.4 ambigue."
            )
        # Story 5.16: une valeur de treillis n'entre dans **aucune** table. Le
        # treillis est imprime sur la page de calibration dediee, qui n'a pas de
        # frames; une table decrit ce qu'une planche porte a cote de ses frames.
        # Sans cette garde, la separation ne tiendrait qu'a la discipline de qui
        # ecrit la prochaine version.
        lattice = [value.value_id for value in self.values
                   if value.role == ROLE_CALIBRATION_LATTICE]
        if lattice:
            raise PatchValuesIntegrityError(
                f"Valeur(s) de treillis dans la table {self.version}: "
                f"{', '.join(lattice)}. Le role '{ROLE_CALIBRATION_LATTICE}' n'est "
                "imprime que sur la page de calibration dediee, et le treillis se "
                "derive (calibration_lattice_values()) au lieu d'etre enregistre."
            )

    def value_ids(self) -> tuple[str, ...]:
        return tuple(value.value_id for value in self.values)

    def adjustment_values(self) -> tuple[PatchValue, ...]:
        """Return the values the correction may be fitted on -- sentinels excluded.

        This is the API the calibration story (5.4) must call. It cannot return
        a sentinel: the exclusion is a property of the function, not a filter
        the caller is trusted to apply. A filter is forgotten once and nobody
        sees it; a plausible-but-wrong LUT is exactly the failure mode this
        prevents (AC 6).
        """
        return ensure_no_sentinel_in_adjustment_set(
            value for value in self.values if value.role != ROLE_GAMUT_SENTINEL
        )

    def sentinel_values(self) -> tuple[PatchValue, ...]:
        """Return the gamut sentinels alone: clipping detection and sizing of ``G``.

        Empty for any table predating story 5.9 -- ``patch-values-1`` carries
        none, and that is precisely the gap EPIC5-ARB-3 measured: patches all
        inside the gamut cannot, by construction, measure the clipping of the
        CMYK driver.
        """
        return tuple(value for value in self.values if value.role == ROLE_GAMUT_SENTINEL)

    def get(self, value_id: str) -> PatchValue:
        for value in self.values:
            if value.value_id == value_id:
                return value
        raise UnknownPatchValueError(
            f"Valeur theorique inconnue: '{value_id}' n'existe pas dans la table "
            f"{self.version}. Valeurs connues: {', '.join(self.value_ids())}."
        )


def requires_printed_frame(value: PatchValue) -> bool:
    """``True`` si ``value`` est invisible sur le papier sans un cadre imprime.

    Le blanc pur n'est pas une couleur imprimee, c'est une **absence d'encre**:
    la sentinelle blanche est strictement indiscernable du fond de page, donc
    ni l'oeil ni l'echantillonnage de la calibration ne sauraient ou la lire.
    Elle doit etre localisable par une geometrie, pas par un espoir (story 5.9,
    AC 5).

    Le predicat vit ici et non dans le registre de presets: ce module est le
    seul point de verite des triplets, et ``patch_presets`` ne doit pas en
    recopier un (verrouille par ``test_registry_stores_no_color_triplet``).
    """
    return value.rgb == PAPER_WHITE_RGB


def ensure_no_sentinel_in_adjustment_set(values) -> tuple[PatchValue, ...]:
    """Return ``values`` as a tuple, or raise if any of them is a gamut sentinel.

    The public guard of AC 6, usable by any story that assembles an adjustment
    set of its own (5.4 builds one from measured patches, not from the table).
    ``PatchValuesTable.adjustment_values()`` runs it on its own output too: the
    cost is nil and it makes the invariant hold even if the role filter above
    were ever loosened.
    """
    values = tuple(values)
    sentinels = [value.value_id for value in values if value.role == ROLE_GAMUT_SENTINEL]
    if sentinels:
        raise SentinelInAdjustmentSetError(
            f"Valeur(s) sentinelle(s) presentee(s) comme jeu d'ajustement: "
            f"{', '.join(sentinels)}. Une sentinelle est ecretee par construction; "
            "l'inclure dans l'ajustement de la correction tirerait la LUT vers une "
            "valeur que l'imprimante n'a jamais reproduite. Utilisez "
            "adjustment_values() pour le jeu d'ajustement et sentinel_values() pour "
            "la detection d'ecretage."
        )
    return values


@dataclass(frozen=True)
class LutPrecondition:
    """One verifiable precondition of the future 5.4 LUT, with its guarantor."""

    statement: str
    guarantor_story: str
    guarantor_module: str


# Version en **litteral**, jamais `ACTIVE_PATCH_VALUES_VERSION`. L'indirection
# d'origine n'etait sans danger que tant qu'il n'existait qu'une seule table:
# des que l'alias bascule (EPIC5-ARB-21), elle **renommerait** la v1 en
# `patch-values-2`, ferait collisionner les deux cles du registre et rendrait
# introuvable le `"patch-values-1"` que les deux presets livres epinglent, eux,
# en litteral. Aucune des 12 valeurs ci-dessous n'est modifiee (EPIC4-ARB-7:
# pas d'edition en place); seule l'entete perd l'indirection.
_TABLE_V1 = PatchValuesTable(
    version="patch-values-1",
    color_space="sRGB",
    white_point="D65",
    bits_per_channel=8,
    values=(
        # Axe neutre, 6 niveaux regulierement espaces (pas de 0 ni de 255:
        # voir le choix des ancres dans le docstring du module).
        PatchValue("neutral-020", (20, 20, 20), ROLE_NEUTRAL,
                   "ancre sombre; 0/0/0 exclu (saturation d'encrage)"),
        PatchValue("neutral-065", (65, 65, 65), ROLE_NEUTRAL),
        PatchValue("neutral-110", (110, 110, 110), ROLE_NEUTRAL),
        PatchValue("neutral-155", (155, 155, 155), ROLE_NEUTRAL),
        PatchValue("neutral-200", (200, 200, 200), ROLE_NEUTRAL),
        PatchValue("neutral-245", (245, 245, 245), ROLE_NEUTRAL,
                   "ancre claire; 255/255/255 exclu (papier nu non mesurable)"),
        # Primaires desaturees (gamut CMJN atteignable, voir docstring).
        PatchValue("primary-red", (190, 45, 45), ROLE_PRIMARY),
        PatchValue("primary-green", (55, 150, 70), ROLE_PRIMARY),
        PatchValue("primary-blue", (45, 75, 160), ROLE_PRIMARY),
        # Secondaires desaturees.
        PatchValue("secondary-cyan", (60, 165, 175), ROLE_SECONDARY),
        PatchValue("secondary-magenta", (175, 60, 150), ROLE_SECONDARY),
        PatchValue("secondary-yellow", (220, 200, 60), ROLE_SECONDARY),
    ),
)

# --- patch-values-2 (story 5.9, EPIC5-ARB-3 / ARB-17 / ARB-21) --------------
#
# 18 valeurs = 10 d'ajustement + 8 sentinelles, soit 36 pastilles a la
# repetition 2 exigee par EPIC4-ARB-6: le plafond exact d'EPIC5-ARB-14, sans
# une cellule libre.
#
# La v2 n'est **pas** un sur-ensemble de la v1. Son jeu d'ajustement est un
# sous-ensemble **propre** de la v1: l'axe neutre passe de 6 a 4 niveaux
# (EPIC5-ARB-17(b)), `neutral-065` et `neutral-155` sont abandonnes pour
# financer les deux ancres achromatiques. Quiconque lit « v2 = v1 +
# sentinelles » se trompera. La v1 reste enregistree, resolvable, et
# `patches-12-v1` continue d'imprimer ses 12 valeurs.
#
# Les 10 valeurs d'ajustement sont reprises **par reference aux memes objets**
# `PatchValue`, jamais recopiees: recopier les triplets recreerait la double
# source de verite que les stories 4.7 et 4.8 ont paye deux fois a eviter. Le
# corollaire est que la conservation est verbatim — identifiant, triplet, role
# et note —, ce qui est precisement ce qu'achete la continuite d'inclusion.
_V2_ADJUSTMENT_VALUE_IDS = (
    # Axe neutre reduit de 6 a 4 niveaux, valeurs conservees verbatim et non
    # re-espacees: un re-espacement detruirait l'inclusion dans la v1.
    "neutral-020",
    "neutral-110",
    "neutral-200",
    "neutral-245",
    "primary-red",
    "primary-green",
    "primary-blue",
    "secondary-cyan",
    "secondary-magenta",
    "secondary-yellow",
)

# Regle de lecture des sentinelles, ecrite ici pour etre reprise verbatim par
# 5.4b plutot que reinventee: **deux niveaux consecutifs d'une meme chaine
# mesures comme indiscernables valent ecretage de cet axe; si
# l'indiscernabilite commence des le couple in-gamut/mediane, l'ecretage est
# plus precoce que l'echelon median et la localisation s'arrete la — le MVP ne
# pretend pas mieux.**
#
# Chaque axe chromatique porte une chaine ordonnee de trois niveaux dont le
# premier est la valeur in-gamut **deja presente** dans la v1, donc sans cout
# de pastille. Les deux ancres achromatiques fonctionnent de meme, leur voisin
# in-gamut etant `neutral-020` / `neutral-245`.
#
# Les niveaux medians sont **calcules**, pas choisis a vue: milieu de la bande
# non mesuree entre la valeur in-gamut et la primaire pure, arrondi au multiple
# de 5. Les trois bandes sont d'ampleur inegale (rouge 91, bleu 129, vert 138
# en distance euclidienne) — fait mesure sur la v1, pas defaut: chaque axe est
# instrumente relativement a sa propre bande.
#
# Pourquoi deux echelons et pas trois: deux suffisent a **detecter** un
# ecretage (deux niveaux voisins indiscernables *sont* l'ecretage). Les
# echelons supplementaires ne servent qu'a **localiser** finement la frontiere
# pour dimensionner automatiquement `G`, usage classe hors MVP par
# EPIC5-ARB-2. Pourquoi RVB et pas CMJ (EPIC5-ARB-17(c)): les sentinelles
# mesurent la frontiere la ou `G` travaille, et `G` opere en RVB, qui est aussi
# ce que la video contient.
_V2_SENTINEL_VALUES = (
    PatchValue(
        "sentinel-red-1", (225, 20, 20), ROLE_GAMUT_SENTINEL,
        "chaine rouge: primary-red (190,45,45) -> ICI -> sentinel-red-2 (255,0,0); "
        "mediane de la bande rouge non mesuree",
    ),
    PatchValue(
        "sentinel-red-2", (255, 0, 0), ROLE_GAMUT_SENTINEL,
        "chaine rouge, borne: rouge pur, bord du cube RVB",
    ),
    PatchValue(
        "sentinel-green-1", (25, 205, 35), ROLE_GAMUT_SENTINEL,
        "chaine verte: primary-green (55,150,70) -> ICI -> sentinel-green-2 (0,255,0); "
        "mediane de la bande verte",
    ),
    PatchValue(
        "sentinel-green-2", (0, 255, 0), ROLE_GAMUT_SENTINEL,
        "chaine verte, borne: vert pur",
    ),
    PatchValue(
        "sentinel-blue-1", (20, 40, 205), ROLE_GAMUT_SENTINEL,
        "chaine bleue: primary-blue (45,75,160) -> ICI -> sentinel-blue-2 (0,0,255); "
        "mediane de la bande bleue",
    ),
    PatchValue(
        "sentinel-blue-2", (0, 0, 255), ROLE_GAMUT_SENTINEL,
        "chaine bleue, borne: bleu pur",
    ),
    PatchValue(
        "sentinel-black-1", (0, 0, 0), ROLE_GAMUT_SENTINEL,
        "chaine noire: neutral-020 (20,20,20) -> ICI; ecretage noir, recouvrement "
        "total d'encrage. Un seul echelon: son second niveau de lecture est son "
        "voisin in-gamut, pas une seconde sentinelle",
    ),
    PatchValue(
        "sentinel-white-1", (255, 255, 255), ROLE_GAMUT_SENTINEL,
        "chaine blanche: neutral-245 (245,245,245) -> ICI; ecretage blanc, papier "
        "nu. Indiscernable du fond sans encre: cadre imprime obligatoire, "
        "patch_presets.PATCH_FRAME_MM",
    ),
)

_TABLE_V2 = PatchValuesTable(
    version="patch-values-2",
    color_space="sRGB",
    white_point="D65",
    bits_per_channel=8,
    values=tuple(_TABLE_V1.get(value_id) for value_id in _V2_ADJUSTMENT_VALUE_IDS)
    + _V2_SENTINEL_VALUES,
)

# --- patch-values-3 (story 5.16, EPIC5-ARB-54 / ARB-57) ---------------------
#
# **Le jeu temoin d'une planche d'images, et rien de plus.** Depuis
# `EPIC5-ARB-54` la correction s'ajuste sur une **page de calibration dediee**;
# ce qui reste sur une planche d'images ne sert donc plus a ajuster, mais a
# **verifier** — verdict d'ecretage, dispersion inter-repliques, residu de la
# correction transportee. Le cardinal tombe a **14 valeurs**, soit 28 pastilles
# en double replicat, soit une seule colonne par cote dans les deux
# orientations.
#
# Composition, arretee par `EPIC5-ARB-57` et reprise valeur par valeur:
#
# * les **8 sentinelles**, inchangees et reprises **par reference aux memes
#   objets** que la v2;
# * les **5 tetes de chaine** — `neutral-020`, `neutral-245`, `primary-red`,
#   `primary-green`, `primary-blue`. Les deux neutres sont la **en tant que
#   tetes**: `sentinel_chains` derive la tete de chaque chaine par proximite
#   colorimetrique, et sans elles `clipping_verdict` rend
#   `REASON_VALUES_ABSENT` sur les axes noir et blanc. Leur exclusion par
#   `EPIC5-ARB-50` etait juste pour le role de **point d'ajustement** et fausse
#   pour celui de **tete**: une valeur peut etre inutile pour un role et
#   indispensable pour un autre;
# * **1 neutre median** — `neutral-065`, pour que la derive de clarte soit
#   mesurable sur un point que le plancher d'ombre et le papier nu n'ecrasent
#   pas.
#
# **`neutral-065` n'existe pas dans la v2** (son axe neutre est reduit a 020 /
# 110 / 200 / 245 par `EPIC5-ARB-17(b)`), et c'est la raison d'etre de cette
# troisieme version: il est repris de la **v1**, par reference au meme objet
# `PatchValue`. Recopier son triplet recreerait la double source de verite que
# les stories 4.7 et 4.8 ont paye deux fois a eviter — et la conservation est
# donc verbatim, identifiant, triplet, role et note.
#
# **Les 3 secondaires n'y sont pas.** Elles ne servaient qu'au re-ajustement
# d'une page deviante sur ses propres pastilles, que `EPIC5-ARB-57` supprime:
# une page qui derive est refusee ou contournee, jamais re-ajustee. Les porter
# quand meme couterait 6 pastilles pour une capacite qu'aucun chemin n'exerce.
#
# Les v1 et v2 restent **intactes**, resolvables, et leurs presets continuent
# d'imprimer leurs valeurs.
_V3_WITNESS_VALUE_IDS = (
    # Les deux tetes achromatiques, ecartees du jeu d'ajustement par
    # EPIC5-ARB-50 et indispensables comme tetes de chaine.
    "neutral-020",
    "neutral-245",
    # Le neutre median, absent de la v2 et repris de la v1.
    "neutral-065",
    # Les trois tetes chromatiques.
    "primary-red",
    "primary-green",
    "primary-blue",
)

_TABLE_V3 = PatchValuesTable(
    version="patch-values-3",
    color_space="sRGB",
    white_point="D65",
    bits_per_channel=8,
    values=tuple(_TABLE_V1.get(value_id) for value_id in _V3_WITNESS_VALUE_IDS)
    + _V2_SENTINEL_VALUES,
)

# --- patch-values-4 (story 5.23, EPIC5-ARB-82) ------------------------------
#
# **Le jeu temoin d'`EPIC5-ARB-57` plus les trois secondaires**, et rien d'autre. La
# v3 reste intacte et resolvable: une planche deja imprimee declare ses valeurs
# transitivement par son `patch_preset_id`, donc rebrancher `patch-values-3` sur un
# jeu plus large serait l'edition en place que le versionnement de 4.8 interdit.
#
# **Pourquoi les secondaires reviennent, alors qu'`EPIC5-ARB-57` les avait retirees.**
# Son motif etait juste pour l'usage d'alors: « elles ne servaient qu'au re-ajustement
# d'une page deviante [...] les porter couterait 6 pastilles pour une capacite
# qu'aucun chemin n'exerce ». `EPIC5-ARB-82` cree ce chemin: la divergence se mesure
# desormais **brute a brute** entre deux feuilles imprimees, et une imprimante depose
# du **CMJN**. Une derive d'encre magenta ou cyan se voit sur une pastille magenta ou
# cyan et **ne se voit pas** sur un jeu RVB + neutres -- c'est la valeur ajoutee qui
# justifie les 6 pastilles, et un test le montre sur un verdict qui bascule.
#
# Les trois secondaires sont reprises **par reference aux memes objets** `PatchValue`
# que la v1 et la v2 (`secondary-cyan`, `secondary-magenta`, `secondary-yellow`, deja
# presentes dans la table **active** `patch-values-2`): aucun triplet n'est invente ni
# recopie ici, la conservation est donc verbatim -- identifiant, triplet, role, note.
#
# 17 valeurs en double replicat = **34 pastilles**, sous le plafond de 36
# (`patch_presets.MAX_PATCHES_PER_PAGE`), et 17 rangees par cote, soit exactement la
# capacite d'une colonne laterale en paysage sous la geometrie v2.
_V4_WITNESS_VALUE_IDS = _V3_WITNESS_VALUE_IDS + (
    "secondary-cyan",
    "secondary-magenta",
    "secondary-yellow",
)

_TABLE_V4 = PatchValuesTable(
    version="patch-values-4",
    color_space="sRGB",
    white_point="D65",
    bits_per_channel=8,
    values=tuple(_TABLE_V1.get(value_id) for value_id in _V4_WITNESS_VALUE_IDS)
    + _V2_SENTINEL_VALUES,
)

#: Registre des versions: une seule active a la fois, les anciennes restent
#: resolvables. Les futures versions s'ajoutent ici (dans le source) sans
#: jamais editer une table existante en place. MappingProxyType (revue 4.8):
#: un dict nu laissait substituer une table a l'execution, contournant tout le
#: versionnement.
#:
#: `ACTIVE_PATCH_VALUES_VERSION` **ne bascule pas** sur la v3 (story 5.16): la
#: v3 est le jeu **temoin** d'une planche d'images, pas un jeu d'ajustement, et
#: la rendre active ferait croire que la correction s'ajuste dessus. Le choix de
#: la version reste porte par le preset, en litteral. **Meme raison pour la v4**
#: (story 5.23): elle elargit le jeu temoin aux trois secondaires, elle ne devient
#: pas pour autant le jeu sur lequel la correction s'ajuste -- celui-la est le
#: treillis de la page de calibration, qui n'est enregistre dans aucune table.
_TABLES_BY_VERSION: "MappingProxyType[str, PatchValuesTable]" = MappingProxyType(
    {
        _TABLE_V1.version: _TABLE_V1,
        _TABLE_V2.version: _TABLE_V2,
        _TABLE_V3.version: _TABLE_V3,
        _TABLE_V4.version: _TABLE_V4,
    }
)


def known_versions() -> tuple[str, ...]:
    """Return every table version that can be resolved (active and archived)."""
    return tuple(_TABLES_BY_VERSION)


def get_patch_values_table(version: str) -> PatchValuesTable:
    """Resolve a table version, active or archived.

    Une planche deja imprimee declare sa version transitivement via
    ``patch_preset_id``: elle doit rester interpretable meme apres qu'une
    nouvelle version est devenue active.
    """
    try:
        return _TABLES_BY_VERSION[version]
    # TypeError (revue 4.8): une version non hachable (liste...) levait un
    # TypeError brut au lieu de l'erreur metier.
    except (KeyError, TypeError):
        raise UnknownPatchValuesVersionError(
            f"Version de table de valeurs inconnue: '{version}'. Versions "
            f"connues: {', '.join(known_versions())} (active: "
            f"{ACTIVE_PATCH_VALUES_VERSION}). Une planche declarant une version "
            "absente de ce registre n'est pas interpretable pour la calibration."
        ) from None


def active_table() -> PatchValuesTable:
    """Return the single active table (EPIC4-ARB-7)."""
    return _TABLES_BY_VERSION[ACTIVE_PATCH_VALUES_VERSION]


# ---------------------------------------------------------------------------
# Story 5.16 : le treillis de la page de calibration, et son filtre
# ---------------------------------------------------------------------------
#
# Ce que le treillis est: le jeu d'ajustement **externe** de `EPIC5-ARB-54`,
# imprime sur la page de calibration dediee (premiere page de chaque lot) et
# nulle part ailleurs. Mesure qui l'a fait retenir, sur les frames d'une planche
# reelle (`analyse-2026-08-11-source-du-jeu-d-ajustement.md`): **4,66 dE76** de
# contenu pour `treillis seul` contre **4,93** pour les pastilles de la feuille.
#
# Ce que le treillis n'est **pas**: une `mire`. Dans ce depot le mot `mires`
# designe les **frames de remplacement de synthese** (`lots[].synthetic_frames`,
# `EPIC5-ARB-33`), et aucun identifiant introduit ici ne porte ni `mire` ni
# `synthetic`.

#: Les cinq niveaux par canal du treillis, **mesures** et non choisis: ce sont
#: ceux de la page 2 de la cible de mesure terrain v3
#: (`scripts/archive/research/build_lut_target.py`, descripteur
#: `_bmad-output/test-artifacts/cible-de-mesure/cible_lut_v3.json`), la seule
#: source qui ait produit le 4,66 dE76 ci-dessus. Le plancher est a 8 et non a 0:
#: 0/0/0 sature l'encrage, et un treillis dont un sommet n'est pas reproductible
#: n'ajuste pas, il tire.
CALIBRATION_LATTICE_LEVELS = (8, 68, 128, 188, 245)

#: Seuil de saturation, en **codes 8 bits**, au-dela duquel une couleur de
#: treillis est ecartee du jeu d'ajustement. La saturation d'un triplet est son
#: **etendue** (`max - min`), lue sur la **reference** et non sur la mesure: on
#: ecarte ce qu'on a demande d'impossible a l'imprimante, pas ce qu'elle a
#: mal rendu.
#:
#: **C'est une regle, pas un reglage** (AC 4). Mesure: le treillis non filtre
#: rend **6,75 dE76** de contenu, le treillis filtre **4,66** — le filtre
#: ameliore de **2,09 dE76**, soit plus de cinq fois le gain de la page separee
#: elle-meme (0,27). Cause: la majorite du cube RVB est **hors gamut** de la
#: conversion CMJN, et aucune correction ne mappe une couleur inatteignable sur
#: sa reference; l'y contraindre deplace la correction pour tout le monde. 120
#: admet les tons chair et les gris colores, exclut les primaires pures.
CALIBRATION_LATTICE_SATURATION_LIMIT_8BIT = 120


def lattice_saturation_8bit(rgb) -> int:
    """Etendue `max - min` d'un triplet, en codes 8 bits. La statistique du filtre."""
    channels = tuple(rgb)
    return int(max(channels) - min(channels))


def _lattice_value_id(rgb) -> str:
    """Identifiant **derive** du triplet, donc jamais desynchronise de lui.

    Trois champs de trois chiffres a zeros de tete: l'ordre lexicographique des
    identifiants coincide alors avec l'ordre du balayage, ce dont
    `aggregate_by_value` a besoin pour rendre deux fois le meme tableau sur les
    memes donnees.
    """
    red, green, blue = (int(channel) for channel in rgb)
    return f"lattice-{red:03d}-{green:03d}-{blue:03d}"


def calibration_lattice_values() -> tuple[PatchValue, ...]:
    """Le treillis **entier**, `len(niveaux)**3` valeurs, dans l'ordre R puis G puis B.

    Derive et non enregistre: ces valeurs ne sont la reference d'aucune planche
    d'images, donc les mettre dans le registre versionne les ferait resoudre par
    `patch_preset_id` alors qu'aucun preset ne les porte. La garde de
    ``PatchValuesTable`` refuse d'ailleurs le role.
    """
    return tuple(
        PatchValue(_lattice_value_id((red, green, blue)), (red, green, blue),
                   ROLE_CALIBRATION_LATTICE)
        for red in CALIBRATION_LATTICE_LEVELS
        for green in CALIBRATION_LATTICE_LEVELS
        for blue in CALIBRATION_LATTICE_LEVELS
    )


def calibration_lattice_adjustment_values() -> tuple[PatchValue, ...]:
    """Le treillis **filtre**: les seules valeurs sur lesquelles on ajuste.

    Le filtre est applique **ici** et pas par l'appelant, pour la meme raison
    qu'``adjustment_values()`` ne peut pas rendre une sentinelle: un filtre que
    l'appelant doit se souvenir d'appliquer est oublie une fois et personne ne le
    voit — et le symptome serait une correction **plausible** ajustee sur des
    couleurs que l'imprimante n'a jamais su produire.
    """
    return tuple(
        value for value in calibration_lattice_values()
        if lattice_saturation_8bit(value.rgb) <= CALIBRATION_LATTICE_SATURATION_LIMIT_8BIT
    )


# --- Les sondes d'ombre : mesurees, et **jamais** versees a l'ajustement -----
#
# AC 5 de la story 5.16, frontiere **negative**. Les sondes d'ombre de la page 3
# de la cible v3 ont ete construites pour *trouver* le plancher d'encrage, et
# elles l'ont trouve. Ce qu'elles produisent est un **verdict**, pas un jeu
# d'ajustement — et ce n'est pas une opinion: les verser degrade la correction de
# **4,66 a 4,81 dE76** de contenu, et retirer les 12 sondes sous le plancher
# recupere exactement l'ecart (4,81 -> 4,65).
#
# Cause mesuree le 2026-08-10: sur cette imprimante les sources 2 a 20 lisent
# toutes **60-63**, avec des ecarts de 0,08 a 0,76 dE76 sous le seuil de bruit de
# 1,61 — donc indiscernables entre elles. Les verser demande a la correction de
# mapper **une meme valeur lue sur six references differentes**, ce qui n'est pas
# une contrainte informative mais une contradiction.

#: Prefixe des identifiants de sonde d'ombre. Nomme ici pour que la frontiere
#: negative de l'AC 5 soit **verifiable**: un grep de ce prefixe dans un jeu
#: d'ajustement doit rendre zero, et on ne peut pas grep ce qui n'a pas de nom.
SHADOW_PROBE_ID_PREFIX = "shadow-probe-"

#: Les huit niveaux de l'echelle d'ombre de la cible v3, mesures (descripteur
#: `cible_lut_v3.json`, `shadow_levels`).
SHADOW_PROBE_LEVELS_8BIT = (2, 5, 8, 12, 16, 20, 28, 36)

#: Plancher d'encrage mesure le 2026-08-10: **au-dessus** de 20, et non a partir
#: de 20. Les six niveaux `<= 20` sont indiscernables entre eux, ce qui laisse
#: exactement deux niveaux exploitables (28 et 36) sur les huit.
SHADOW_FLOOR_8BIT = 20


class ShadowProbeInAdjustmentSetError(ValueError):
    """Raised when a shadow probe is presented as an adjustment value.

    Symetrique de ``SentinelInAdjustmentSetError``, et pour le meme motif de
    conception: une **garde qui refuse** plutot qu'un filtre que l'appelant doit
    se souvenir d'appliquer. La mesure qui la justifie est chiffree ci-dessus.
    """


def shadow_probe_value_ids() -> tuple[str, ...]:
    """Les identifiants des sondes d'ombre, derives de leurs niveaux.

    Aucun triplet n'est construit: ces sondes ne sont imprimees par **aucune**
    page de production, ni planche d'images ni page de calibration. Leur seule
    presence dans ce module est ce qui rend la frontiere negative de l'AC 5
    verifiable au lieu d'etre declarative.
    """
    return tuple(f"{SHADOW_PROBE_ID_PREFIX}{level:03d}"
                 for level in SHADOW_PROBE_LEVELS_8BIT)


def ensure_no_shadow_probe_in_adjustment_set(value_ids) -> tuple[str, ...]:
    """Return ``value_ids`` as a tuple, or raise if any names a shadow probe."""
    value_ids = tuple(value_ids)
    probes = [value_id for value_id in value_ids
              if str(value_id).startswith(SHADOW_PROBE_ID_PREFIX)]
    if probes:
        raise ShadowProbeInAdjustmentSetError(
            f"Sonde(s) d'ombre presentee(s) comme jeu d'ajustement: "
            f"{', '.join(probes)}. Sous le plancher d'encrage mesure "
            f"({SHADOW_FLOOR_8BIT} en 8 bits) plusieurs references lisent la meme "
            "valeur: les verser demande de mapper une meme mesure sur plusieurs "
            "references, ce qui degrade la correction de 4,66 a 4,81 dE76. Ces "
            "sondes produisent un verdict de plancher, pas un jeu d'ajustement."
        )
    return value_ids


# --- Le meme plancher, sur les valeurs qui ne s'appellent pas `shadow-probe-*` ----
#
# AC 7 de la story 5.20, et c'est un ecart de **couverture** et non de regle. La garde
# ci-dessus ne connait qu'un prefixe d'identifiant, or le treillis normal porte son
# propre niveau le plus sombre -- `lattice-008-008-008`, un identifiant **different** de
# `shadow-probe-008` -- soumis au meme plancher d'encrage physique et couvert par aucune
# garde. Il n'etait filtre que par la saturation
# (`CALIBRATION_LATTICE_SATURATION_LIMIT_8BIT`), qui ne dit rien de la clarte: un point
# neutre a saturation nulle passe toujours, aussi sombre soit-il.
#
# **Le critere est la clarte, jamais le nom.** Un prefixe aurait reconduit exactement le
# defaut qu'on ferme ici -- il faudrait le rouvrir a la valeur suivante qui s'appelle
# autrement. Le predicat porte donc sur le triplet, comme le filtre de saturation, et il
# est derive de `SHADOW_FLOOR_8BIT`: le plancher est **un** fait mesure, pas deux.
#
# Mesure qui le justifie (2026-08-13, sur `scan-WIN`, forme en vigueur): retirer ce seul
# point du jeu d'ajustement fait passer le residu de 14,09 a 13,41 dE76 moyen et de 35,04
# a 33,42 en maximum. Reel, et **insuffisant seul** -- la compression tonale touche aussi
# les niveaux 68, 128 et 188, ce que la forme `color-correction-tone-curve-chroma-1`
# traite par ailleurs.


class InkFloorValueInAdjustmentSetError(ValueError):
    """Une valeur entierement sous le plancher d'encrage est presentee a l'ajustement.

    Symetrique de ``ShadowProbeInAdjustmentSetError``, avec la meme cause physique et
    un critere different: celle-la lit un prefixe d'identifiant, celle-ci lit la
    **clarte du triplet**. Les deux existent parce que le depot porte deux familles de
    valeurs sous le meme plancher et qu'un seul critere ne les couvre pas toutes.
    """


def is_below_ink_floor(rgb) -> bool:
    """Le triplet est-il **entierement** sous le plancher d'encrage mesure ?

    Le canal le plus clair porte le verdict: un triplet dont un seul canal depasse le
    plancher reste discernable de ses voisins par ce canal-la, donc il informe encore
    l'ajustement. C'est la meme asymetrie que le filtre de saturation, qui lit l'etendue
    et non la moyenne -- une statistique d'agregat masquerait le cas qu'on cherche.

    Comparaison **large** (`<=`) et non stricte: `SHADOW_FLOOR_8BIT` est mesure comme le
    dernier niveau indiscernable de ses voisins, pas comme le premier exploitable
    (« au-dessus de 20, et non a partir de 20 », mesure du 2026-08-10).

    **La lecture est en flottant et non tronquee** (finding de revue de 5.20, ferme le
    2026-08-19). Un `int(channel)` deplacait la frontiere jusqu'a un code entier vers le
    haut: `(20.9, 20.9, 20.9)` etait juge sous un plancher de 20, alors que ses trois
    canaux sont au-dessus. Le triplet du treillis est entier, donc la troncature ne
    changeait rien sur le chemin nominal -- elle mordait sur toute mesure interpolee ou
    agregee, qui est exactement ce qu'un appelant a en main quand il verifie un jeu
    construit ailleurs.
    """
    return max(float(channel) for channel in rgb) <= SHADOW_FLOOR_8BIT


def ink_floor_lattice_value_ids() -> tuple[str, ...]:
    """Les valeurs du treillis que le plancher d'encrage exclut de l'ajustement.

    **Derivees et non enumerees** (`EPIC5-ARB-29`): sur les niveaux en vigueur elles se
    reduisent au seul `lattice-008-008-008`, mais un niveau ajoute sous le plancher y
    entrerait sans edition, et un plancher revise les rendrait toutes d'un coup.
    """
    return tuple(value.value_id for value in calibration_lattice_values()
                 if is_below_ink_floor(value.rgb))


def ensure_no_ink_floor_value_in_adjustment_set(values) -> tuple:
    """Rendre ``values`` en tuple, ou refuser si l'une est sous le plancher d'encrage.

    ``values`` porte des objets a `value_id` et `rgb` -- des `PatchValue` en pratique --
    et non des identifiants nus: la clarte n'est pas lisible dans un nom, et la deduire
    d'un nom serait reconduire le defaut que cette garde ferme.
    """
    values = tuple(values)
    fautives = [value.value_id for value in values if is_below_ink_floor(value.rgb)]
    if fautives:
        raise InkFloorValueInAdjustmentSetError(
            f"Valeur(s) sous le plancher d'encrage presentee(s) comme jeu "
            f"d'ajustement: {', '.join(fautives)}. Sous {SHADOW_FLOOR_8BIT} en 8 bits, "
            "l'imprimante d'Egan rend toutes les sources 2 a 20 entre 60 et 63: les "
            "verser demande de mapper une meme mesure sur plusieurs references, ce qui "
            "n'est pas une contrainte informative mais une contradiction. Mesure du "
            "2026-08-13 sur scan-WIN: retirer le seul 'lattice-008-008-008' fait "
            "passer le residu de 14,09 a 13,41 dE76 moyen."
        )
    return values


#: Preconditions verifiables de la future LUT (AC 4), chacune avec son garant.
#: Les hypotheses qui conditionnent l'impression sont posees ici; celles qui
#: relevent de la mesure sont explicitement renvoyees a 5.4.
LUT_PRECONDITIONS: tuple[LutPrecondition, ...] = (
    LutPrecondition(
        "Les valeurs theoriques sont versionnees et retrouvables depuis "
        "patch_preset_id (preset -> version de table -> valeurs), sans edition "
        "en place possible.",
        guarantor_story="4.8 (cette story) + 4.7 (registre de presets)",
        guarantor_module="patch_values.py + patch_presets.py",
    ),
    LutPrecondition(
        "Les patchs sont lus sur la page redressee geometriquement "
        "(homographie des 4 coins ArUco), jamais sur le scan brut.",
        guarantor_story="4.3 (marqueurs) + 5.2 (detection au scan)",
        guarantor_module="layout.py + detection/aruco.py",
    ),
    LutPrecondition(
        "Chaque valeur de patch est repetee et repartie sur la page pour que "
        "la moyenne des patchs identiques d'une meme page ait un sens "
        "statistique (une seule correction par page, story 5.4).",
        guarantor_story="4.7 (AC 2: repetition >= 2, positions eloignees)",
        guarantor_module="patch_presets.py",
    ),
    LutPrecondition(
        "La surface de chaque patch est suffisante pour moyenner le tramage "
        "d'impression et survivre au redressement (dimensionnement en mm).",
        guarantor_story="4.7 (AC 5: taille de patch instruite et consignee)",
        guarantor_module="patch_presets.py",
    ),
    LutPrecondition(
        "target_colorspace est renseigne dans le manifest comme cible de "
        "reconstruction du rush - jamais confondu avec l'espace des patchs, "
        "qui est declare par la table de valeurs.",
        guarantor_story="3.4 (persistance manifest) + 4.1 (echec explicite si absent)",
        guarantor_module="io/payload.py + cli.py (makepdf)",
    ),
    LutPrecondition(
        "color_calibration_status (contrat 5.5, valeurs fermees not_applied/"
        "applied/failed) est ecrit par le fragment manifest de color_pipeline "
        "sur le chemin extraction/scan; makepdf ne l'ecrit pas et il n'entre "
        "jamais dans le payload QR (io/payload.py ne le porte pas).",
        guarantor_story="5.5 (contrat couleur MVP, close)",
        guarantor_module="color_pipeline.py",
    ),
    LutPrecondition(
        "Hypotheses materiel minimales pour l'impression et le scan des "
        "planches (bloquantes, TEST_PLAN 4.4): scanner a plat; DPI de scan au "
        "moins egal au minimum QR de la chaine (qr_codes.QR_MIN_SCAN_DPI); "
        "automatismes du scanner (exposition, balance) desactives quand le "
        "pilote le permet. Les hypotheses de mesure (echantillonnage, "
        "tolerances) sont renvoyees a 5.4.",
        guarantor_story="4.8 (posees ici) + 5.4 (mesure, differee)",
        guarantor_module="patch_values.py (documentation) + qr_codes.py (seuil DPI)",
    ),
    LutPrecondition(
        "Les valeurs de role gamut_sentinel sont exclues du jeu d'ajustement "
        "de la correction par l'API elle-meme (adjustment_values() ne peut pas "
        "en rendre une, ensure_no_sentinel_in_adjustment_set() refuse toute "
        "sentinelle presentee comme telle); elles alimentent la detection "
        "d'ecretage et le dimensionnement de G, jamais l'ajustement.",
        guarantor_story="5.9 (mecanisme) + 5.4 (usage)",
        guarantor_module="patch_values.py",
    ),
)
