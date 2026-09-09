"""Registre des presets de patchs de calibration (story 4.7).

Unique resolveur de ``patch_preset_id`` -- le champ existe dans le payload QR
et le manifest depuis l'Epic 2 sans que rien ne le resolve jusqu'ici. Chaque
preset reference des identifiants de valeurs de la table 4.8
(``patch_values``) et n'en copie jamais les triplets: le depot a deja paye
deux fois le prix d'une double source de verite (2.3/2.6, 4.6).

Module **pur**: aucune dependance a cv2 / PIL / reportlab / numpy, et pas
d'import de ``layout`` (qui tire cv2). Les positions sont des constantes
explicites en millimetres dans le repere du template (origine haut-gauche,
y vers le bas, convention ``layout.py``); le test geometrique de
``tests/unit/test_patch_presets.py`` confronte ces positions aux constantes
reelles de ``layout`` -- jamais des valeurs recopiees.

Presets livres (EPIC4-ARB-6, amende par EPIC5-ARB-14)
-----------------------------------------------------
- ``patches-9-v1``: 9 valeurs x 2 = 18 pastilles (axe neutre 5 niveaux +
  primaires + jaune secondaire), sur ``patch-values-1``;
- ``patches-12-v1``: 12 valeurs x 2 = 24 pastilles (axe neutre 6 niveaux +
  3 primaires + 3 secondaires), sur ``patch-values-1`` -- l'ancien maximum
  arbitre de 24 pastilles physiques par page;
- ``patches-18-v2``: 18 valeurs x 2 = 36 pastilles (10 d'ajustement +
  8 sentinelles de gamut), sur ``patch-values-2`` -- le plafond amende de
  36, atteint **exactement**, sans une cellule libre. Story 5.9.
Le preset degrade ``single`` (repetition 1) n'est pas retenu au MVP: la
clause reste dormante dans la structure (champ ``single``), aucun preset
livre ne l'active.

Chaque preset epingle sa version de table **en litteral**, jamais via
``ACTIVE_PATCH_VALUES_VERSION`` -- et depuis que la story 5.9 fait
effectivement basculer cet alias, ce n'est plus une precaution theorique:
``patches-9-v1`` et ``patches-12-v1`` continuent d'imprimer les valeurs de la
v1, exactement comme avant.

Placement (AC 3): deterministe, defini **par couple template x preset**.
Depuis la story 4.1, les templates viennent du registre ``page_templates``
(orientation x cardinal x preset de marge) et chaque couple est enregistre
explicitement ici -- ``UndefinedPlacementError`` sinon, jamais une rotation
ni une interpolation. Le placement est defini par **famille d'orientation**,
parce que le registre de templates garantit que toute la famille partage la
meme bande de frames (les grilles varient a l'interieur de la bande, jamais
au-dela); le test geometrique verifie chaque couple contre la geometrie de
**son** template, pas contre un representant.

- Portrait: deux colonnes laterales symetriques dans les bandes
  structurellement libres (x [14, 26] et x [184, 196], y [62, 228] hors quiet
  zones des marqueurs et hors bande de frames x [35, 175]). La colonne droite
  est en ordre inverse: chaque valeur apparait deux fois a plus de 100 mm
  d'ecart -- la moyenne par page (story 5.4) capture la non-uniformite
  d'eclairage et de scan.
- Paysage: la hauteur laterale libre (y [60, 150]) ne loge que 6 rangs, donc
  **deux colonnes par cote** (x 14 et 30 a gauche, 255 et 271 a droite), la
  bande de frames commencant a x = 48. Chaque valeur a une copie a gauche et
  une a droite (>= 200 mm d'ecart); les sequences de colonnes sont posees
  explicitement par preset.
- Le preset sentinelle ``patches-18-v2`` **repose sa propre geometrie de
  colonnes** (portrait x 5/19/177/191 sur 9 rangs, paysage x 5/19/33 et
  249/263/277 sur 6 rangs). Ce n'est pas un choix de confort: aucune colonne
  supplementaire ne tient a cote des colonnes actuelles, il faudrait x <= 0 a
  gauche. Les deux presets livres conservent **exactement** leurs placements
  (invariant 2 d'EPIC5-ARB-14).

Protection contre la bave d'encre inter-patchs (piege 3 de la story 4.7).
**Contrat amende par EPIC5-ARB-17(a) (story 5.9).** La regle d'origine etait
une precaution de **disposition**: alterner neutre / couleur pour qu'aucune
paire de pastilles saturees ne partage un bord. Elle est remplacee par une
**garantie geometrique d'echantillonnage**, plus precise et posee un cran
plus bas: pour tout couple (template, preset) et toute pastille placee, le
carre effectivement mesure -- ``SAMPLED_SIDE_MM`` centre sur l'emprise de
``PATCH_SIZE_MM`` -- est a au moins ``SAMPLING_INSET_MM`` de tout bord
imprime, le sien comme celui de n'importe quelle autre pastille de la page.

Pourquoi l'amendement: la bave contamine la **frontiere** entre deux
pastilles, jamais leur centre, et la story de calibration contractualise deja
une marge d'echantillonnage interieure -- contrat ecrit apres la precaution
de 4.7, qui faisait donc doublon. Les gammes de controle industrielles
(bandes Fogra, ISO 12647) posent leurs pastilles bord a bord pour cette
raison exacte: le spectrophotometre lit le centre.

Ce que l'amendement debloque, et qui le rend indissociable du choix de
configuration de ``patch-values-2``: dans un bloc de 18 cellules adjacentes
au pas de 14 mm, l'ensemble non-adjacent maximal vaut 9 (damier). Tant que
l'alternance tenait, elle plafonnait donc a **9 valeurs chromatiques** par
bloc; la v2 en porte **12**. La configuration d'EPIC5-ARB-17(b) serait
geometriquement infaisable sans l'amendement (a) -- et si le pilote papier
impose le retour a l'alternance, c'est la **configuration** qu'il faudra
reprendre, pas seulement l'ordre des colonnes.

Limite consignee et conservee de la revue 4.7: entre les deux colonnes d'un
meme cote en paysage, des pastilles se font face **en diagonale** (coins a
~4.5 mm). Ce contact quasi ponctuel reste accepte -- la bave se propage le
long des bords partages, pas entre deux coins.

Taille de patch (AC 5): ``PATCH_SIZE_MM = 12`` -- au centre de la fourchette
instruite 10-15 mm: a 600 dpi de scan un patch de 12 mm couvre ~283 px de
cote, assez pour moyenner le tramage d'impression et survivre au
redressement par homographie, tout en laissant tenir 12 rangs par colonne
sur le template actuel. ``PATCH_SPACING_MM = 2`` est l'espacement minimal
inter-patchs consigne comme contrainte d'impression (non mesure ici).

Zones reservees: emprises du QR (4.1) et des blocs de texte (4.2) que le
placement des patchs doit laisser libres -- le test geometrique 4.7 interdit
toute pastille dedans. Depuis la livraison de 4.1/4.2 elles ne sont plus le
seul filet: les emprises **reelles** du QR (agrandissement compris) et des
blocs de texte sont confrontees element par element aux patchs dans le test
global de plan de page de 4.1 (`test_no_overlap_between_any_printed_elements`).
Les reservations restent la borne statique cote patchs; leur couverture des
emprises reelles nominales est verifiee cote 4.1.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import page_templates, patch_values
from .numeric_guards import is_strict_number
from .page_roles import (
    PAGE_ROLE_CALIBRATION,
    PAGE_ROLE_IMAGES,
    page_role_label,
    validate_page_role,
)

#: Identifiant du template A4 portrait 2 zones historique (celui que
#: ``layout.py`` implemente aujourd'hui). Pose ici par la story 4.7; depuis la
#: story 4.1 le registre ``page_templates`` le derive et un test verrouille
#: l'egalite des deux formes.
TEMPLATE_A4_PORTRAIT_2F = page_templates.TEMPLATE_A4_PORTRAIT_2F

#: Maximum arbitre de pastilles physiques par page (EPIC4-ARB-6, **amende par
#: EPIC5-ARB-14**: 24 -> 36). Le chiffre est **mesure**, pas choisi: colonnes
#: de 12 mm au pas de 14 dans les bandes laterales libres, portrait 4 colonnes
#: x 12 rangs = 48 emplacements, paysage 6 colonnes x 6 rangs = 36. Le minimum
#: des deux est le plafond reel commun a toutes les orientations.
#:
#: **Ce plafond est celui d'une planche d'IMAGES, et son propre commentaire le dit**
#: (story 5.16, AC 4): il est mesure « dans les bandes **laterales libres** », donc
#: il borne ce qui tient **a cote d'une bande de frames**. Une page de calibration
#: n'en a pas: son plafond mesure vaut 141 en portrait et 135 en paysage. Le
#: plafond est donc **derive du role** (:data:`_PATCH_CEILING_BY_ROLE`) et cette
#: constante n'est **pas** relevee -- la porter a 141 la rendrait fausse pour les
#: planches d'images, qui sont le cas ou elle protege.
MAX_PATCHES_PER_PAGE = 36

#: Cote d'une pastille et espacement minimal inter-pastilles (voir docstring).
PATCH_SIZE_MM = 12.0
PATCH_SPACING_MM = 2.0

#: Cote d'une pastille sur une **page de calibration** (story 5.16, AC 4). Mesure
#: du 2026-08-12, et le choix est **derive du role**, pas pose:
#:
#: * une page de calibration n'a **aucune bande de frames** qui lui dispute la
#:   surface, donc la taille de pastille n'y est plus un compromis avec la zone de
#:   dessin: elle se choisit pour la qualite de mesure, et c'est la page dont
#:   **toute** la correction du lot depend;
#: * le carre effectivement mesure **double** -- 6,0 mm contre 3,0, soit 142 px
#:   contre 71 a 600 dpi, donc quatre fois la surface moyennee. La these entiere de
#:   la story 5.16 est que la correction est *meilleure* (4,66 contre 4,93 dE76):
#:   degrader la mesure sur la page qui la produit irait contre son propre objet;
#: * 12 mm est le regime pour lequel **tous** les chiffres du commentaire de
#:   :data:`SAMPLING_INSET_MM` ont ete mesures. A 6 mm trois de ses enonces
#:   s'inversent et l'echelle de repli la moins couteuse du depot n'est plus
#:   chiffree. La page de calibration revient dans le regime documente;
#: * le cout n'est **pas nul**, et il est mince: 141 cellules en portrait, 135 en
#:   paysage pour 130 pastilles de treillis, soit **5 cellules de marge** sur
#:   l'orientation limitante. 13 mm ne passe plus (111 en paysage). C'est pourquoi
#:   la capacite est **derivee** et confrontee au cardinal reel par test, jamais
#:   comparee a un litteral: a 5 cellules de marge, la prochaine redefinition de
#:   geometrie peut la faire tomber sans qu'aucun test ne le dise.
#:
#: **Reversible en une valeur** si l'uniformite est preferee a la qualite de
#: mesure: rendre `spec.geometry.patch_size_mm` pour les deux roles est un
#: changement d'une ligne dans :data:`_PATCH_SIZE_MM_BY_ROLE`.
CALIBRATION_PATCH_SIZE_MM = 12.0

#: Retrait d'echantillonnage (story 5.9, EPIC5-ARB-17(a)). Depuis l'amendement
#: du contrat d'adjacence, c'est **la seule** protection contre la bave d'encre
#: inter-pastilles: la zone effectivement mesuree par la calibration est un
#: carre centre plus petit que l'emprise imprimee, et la bave contamine la
#: frontiere entre deux pastilles, jamais leur centre. C'est l'idiome des
#: gammes de controle industrielles (bandes Fogra, ISO 12647), qui posent leurs
#: pastilles bord a bord parce que le spectrophotometre lit le centre.
#:
#: Valeur **posee et non mesuree**, comme tous les seuils de ce depot: 3,0 mm
#: vaut 1,5 fois l'espacement inter-pastilles et laisse un carre de 6,0 mm,
#: soit ~142 px de cote a 600 dpi (~20 000 px a moyenner). Le premier pilote
#: papier doit rapporter la bave reelle sur le cas le pire — un rouge pur RVB,
#: donc deux encres superposees, voisin d'une autre chromie. Echelle de repli,
#: par cout croissant: (1) porter ce retrait a 4,0 mm (le carre tombe a 4,0 mm,
#: ~94 px, encore exploitable) — une constante, un test, aucune geometrie
#: deplacee; (2) augmenter `PATCH_SPACING_MM`, ce qui deplace les colonnes;
#: (3) revenir a l'alternance neutre / couleur, ce qui imposerait de revenir
#: **aussi** sur la configuration de `patch-values-2` (voir docstring).
#:
#: **Tous les chiffres ci-dessus sont ceux d'une pastille de 12 mm** -- la v1, qui
#: n'est plus le defaut du depot depuis le 2026-08-12 (`makepdf --geometrie v1` la
#: compose encore). `color_calibration.sampled_square_mm` traite les autres tailles
#: **proportionnellement**, donc sous la geometrie a pastilles de 6 mm -- la v2, **qui
#: est desormais le defaut** et se compose sans aucun drapeau -- chacun d'eux change, et
#: trois enonces de ce commentaire s'inversent (mesures de la revue du 2026-08-11,
#: refaites a la passe de correction):
#:
#: * le retrait tombe a **1,5 mm**, soit **0,5 fois** l'espacement inter-pastilles de
#:   la v2 (3,0 mm) et non 1,5 fois;
#: * le carre mesure tombe a **3,0 mm**, soit **71 px** a 600 dpi (~5 000 px a
#:   moyenner) et non 142;
#: * la garde entre le cadre imprime de la sentinelle blanche et le carre mesure tombe
#:   de 2,0 a **0,5 mm**, et l'echelle de repli (1) devient un carre de **2,0 mm /
#:   47 px** -- le repli le moins couteux du depot n'est donc plus chiffre pour cette
#:   geometrie.
#:
#: Aucun **plancher absolu** n'est pose sur le cote du carre echantillonne, et ce n'est
#: pas un oubli: un plancher est un seuil, un seuil se mesure (bave reelle sur du
#: papier), et le poser au jugement serait exactement le defaut d'`EPIC5-ARB-52`. Le
#: point est verse au `deferred-work.md` avec le protocole qui le trancherait, et il y a
#: **monte en priorite** le 2026-08-12: la geometrie qui le rend mordant est desormais
#: **le defaut du depot**, alors qu'elle demandait un drapeau explicite quand le point a
#: ete verse. Un retrait a 1,5 mm sans plancher absolu est donc ce que toute planche
#: composee sans option porte, et non plus un cas qu'il faut demander.
SAMPLING_INSET_MM = 3.0

#: Cote du carre effectivement echantillonne. Derive, jamais recopie: la
#: story de calibration le **consomme**, elle ne le redeclare pas.
SAMPLED_SIDE_MM = PATCH_SIZE_MM - 2 * SAMPLING_INSET_MM

#: Epaisseur du cadre imprime de la sentinelle blanche (story 5.9, AC 5).
#: Trace sur le bord **interieur** de l'emprise, donc [0, 1] mm depuis chaque
#: bord: un cadre exterieur mangerait `PATCH_SPACING_MM` et ferait tomber la
#: garantie d'espacement d'impression. Les deux inclusions sont strictes et
#: chiffrees: le cadre est interieur a l'emprise de 12 mm, et le carre
#: echantillonne ([3, 9] mm) est interieur au cadre avec 2,0 mm de marge de
#: chaque cote. Sous une pastille de 6 mm cette marge tombe a 0,5 mm (voir
#: `SAMPLING_INSET_MM`): serree, mais strictement positive, et un test la mesure.
PATCH_FRAME_MM = 1.0


class UnknownPatchPresetError(ValueError):
    """Raised when a ``patch_preset_id`` is not part of the registry."""


class UndefinedPlacementError(ValueError):
    """Raised when a template x preset couple has no explicit placement."""


class PatchPresetGeometryError(ValueError):
    """Raised when a placement definition is internally inconsistent.

    A programming error in this module, not an operator input: it fires at
    import time rather than letting a half-placed preset reach a printed page.
    """


@dataclass(frozen=True)
class PatchPreset:
    """One versioned patch preset: identifiers only, never color values."""

    preset_id: str
    values_version: str
    value_ids: tuple[str, ...]
    repetition: int
    single: bool = False


@dataclass(frozen=True)
class PlacedPatch:
    """One patch to print: value identifier, color read from the 4.8 table at
    resolution time, and position/size in template millimeters."""

    value_id: str
    rgb: tuple[int, int, int]
    x_mm: float
    y_mm: float
    size_mm: float
    # NOTE: tout invariant ajoute ici doit etre verifie dans __post_init__,
    # sinon il n'est qu'un commentaire.
    #: Epaisseur du cadre imprime sur le bord **interieur** de l'emprise, en
    #: millimetres. ``0.0`` -- le defaut -- signifie « rectangle plein sans
    #: contour », c'est-a-dire le comportement de toutes les pastilles
    #: anterieures a la story 5.9: aucun preset existant ne change. Seule la
    #: sentinelle blanche en porte un, faute de quoi elle serait indiscernable
    #: du papier nu (AC 5).
    frame_mm: float = 0.0

    def __post_init__(self) -> None:
        # Un cadre negatif se tracerait a l'exterieur de l'emprise et mangerait
        # `PATCH_SPACING_MM`; un cadre au-dela de la moitie du cote remplirait
        # la pastille et ferait disparaitre la valeur qu'elle porte. Les deux
        # sont des erreurs de programmation, refusees a la construction plutot
        # que decouvertes sur une planche imprimee.
        if not is_strict_number(self.frame_mm) or not 0.0 <= self.frame_mm < self.size_mm / 2:
            raise PatchPresetGeometryError(
                f"Epaisseur de cadre invalide pour '{self.value_id}': "
                f"{self.frame_mm!r}. Attendu 0 <= frame_mm < size_mm / 2 "
                f"({self.size_mm / 2})."
            )


# Ordre de colonne alternant neutre / couleur (aucune paire saturee adjacente).
_ORDER_12 = (
    "neutral-020", "primary-red",
    "neutral-065", "primary-green",
    "neutral-110", "primary-blue",
    "neutral-155", "secondary-cyan",
    "neutral-200", "secondary-magenta",
    "neutral-245", "secondary-yellow",
)
# Sous-ensemble 9 valeurs (EPIC4-ARB-6: axe neutre 5 niveaux + primaires /
# secondaires reduits): les deux ancres + la rampe sombre 20/65/110 + 200,
# les 3 primaires, et le jaune secondaire (axe encre jaune, le plus distinct
# des primaires RVB). Le niveau 155 et cyan/magenta n'entrent que dans le 12.
_ORDER_9 = (
    "neutral-020", "primary-red",
    "neutral-065", "primary-green",
    "neutral-110", "primary-blue",
    "neutral-200", "secondary-yellow",
    "neutral-245",
)

# Ordre du preset sentinelle (story 5.9). Le principe qui remplace l'alternance
# neutre / couleur: les valeurs d'une meme **chaine de lecture** (in-gamut ->
# mediane -> pure) sont posees sur des cellules **contigues**, pour que la
# rampe se lise a l'oeil sur la planche imprimee. C'est l'idiome des gammes de
# controle industrielles, et un ecretage grossier devient alors visible sans
# instrument -- deux echelons voisins qui ressortent identiques *sont*
# l'ecretage.
#
# La decoupe en colonnes ne coupe aucune chaine, et c'est une contrainte a
# tenir en reordonnant: portrait 2 colonnes de 9 ([0:9] / [9:18]), paysage
# 3 colonnes de 6 ([0:6] / [6:12] / [12:18]).
#
# Rebasculement (repli (3) de l'AC 9): l'ordre vit dans ce seul tuple et dans
# `_SENTINEL_PAYSAGE_COLUMNS`. Reordonner suffit -- mais l'alternance stricte
# plafonne a 9 valeurs chromatiques par bloc de 18 cellules, et la v2 en porte
# 12: le repli est une decision de configuration, pas un reordonnancement.
_ORDER_18 = (
    # Chaine noire (2 cellules) puis un niveau neutre isole.
    "neutral-020", "sentinel-black-1",
    "neutral-110",
    # Les trois chaines chromatiques, chacune sur 3 cellules contigues.
    "primary-red", "sentinel-red-1", "sentinel-red-2",
    "primary-green", "sentinel-green-1", "sentinel-green-2",
    "primary-blue", "sentinel-blue-1", "sentinel-blue-2",
    # Secondaires (hors chaine: aucune sentinelle ne les instrumente au MVP).
    "secondary-cyan", "secondary-magenta", "secondary-yellow",
    "neutral-200",
    # Chaine blanche (2 cellules), en fin de bloc.
    "neutral-245", "sentinel-white-1",
)

# --- Ordre du preset temoin (story 5.16, AC 6 et 7) -------------------------
#
# **Ce que ce preset est**: le jeu qui reste sur une planche d'IMAGES depuis que la
# correction s'ajuste sur une page de calibration dediee (`EPIC5-ARB-54`). Il ne
# sert plus a ajuster, mais a **verifier** -- verdict d'ecretage, dispersion
# inter-repliques, residu de la correction transportee, garde de divergence
# d'`EPIC5-ARB-57`. Composition arretee valeur par valeur par `EPIC5-ARB-57`:
#
# * les **8 sentinelles** de gamut;
# * les **5 tetes de chaine** (`neutral-020`, `neutral-245`, `primary-red`,
#   `primary-green`, `primary-blue`). Les deux neutres sont la **en tant que
#   tetes**: `sentinel_chains` les derive par proximite colorimetrique, et sans
#   elles `clipping_verdict` rend `REASON_VALUES_ABSENT` sur les axes noir et
#   blanc. Leur exclusion par `EPIC5-ARB-50` etait juste pour le role de point
#   d'ajustement et fausse pour celui-ci;
# * **1 neutre median** (`neutral-065`, absent de la v2 et repris de la v1 par
#   `patch-values-3`), pour que la derive de clarte soit mesurable sur un point que
#   le plancher d'ombre et le papier nu n'ecrasent pas.
#
# 14 valeurs en double replicat = **28 pastilles**, soit **14 par cote**. Le double
# replicat n'est pas du confort: sans deux occurrences, `replicate_dispersion` n'a
# rien a mesurer et la garde d'`EPIC5-ARB-49` devient aveugle -- on ne distingue
# plus « cette page diverge » de « ce papier est bruyant ».
#
# **Aucune secondaire.** Elles ne servaient qu'au re-ajustement d'une page
# deviante, que `EPIC5-ARB-57` supprime: les porter couterait 6 pastilles pour une
# capacite qu'aucun chemin n'exerce. Frontiere negative verifiee par test.
#
# **Decoupe en colonnes: aucune chaine de lecture n'est coupee**, meme contrainte
# que `_ORDER_18` et pour la meme raison (un ecretage grossier se voit a l'oeil sur
# deux echelons voisins qui ressortent identiques). L'ordre ci-dessous se coupe
# proprement en 1 colonne de 14 (la v2, une colonne par cote) **et** en 2 colonnes
# de 7 (le portrait v1): les groupes rouge / vert / median font 7, les groupes bleu
# / noir / blanc font 7. La coupe en 3 colonnes du paysage v1 (5, 5, 4) coupe, elle,
# la chaine verte -- et c'est assume: la propriete est revendiquee pour la geometrie
# qui porte ce preset (`border_witness_count = 28` est declare par la v2), pas pour
# une orientation ou aucune planche ne sera imprimee avec lui.
_ORDER_14 = (
    # Chaine rouge, chaine verte, puis le neutre median -> 7, la premiere colonne
    # du portrait v1.
    "primary-red", "sentinel-red-1", "sentinel-red-2",
    "primary-green", "sentinel-green-1", "sentinel-green-2",
    "neutral-065",
    # Chaine bleue, chaine noire, chaine blanche -> 7, la seconde.
    "primary-blue", "sentinel-blue-1", "sentinel-blue-2",
    "neutral-020", "sentinel-black-1",
    "neutral-245", "sentinel-white-1",
)

# --- Ordre du preset temoin elargi (story 5.23, EPIC5-ARB-82) ---------------
#
# **Ce que ce preset ajoute a `patches-14-v3`**: les trois secondaires desaturees
# (`secondary-cyan`, `secondary-magenta`, `secondary-yellow`), reprises verbatim de
# `patch-values-4`. Motif, et il est mesure et non esthetique: `EPIC5-ARB-82` fait
# desormais comparer **deux feuilles imprimees** brute a brute, et une imprimante
# depose du CMJN. Une derive d'encre cyan ou magenta se voit sur une pastille cyan ou
# magenta et ne se voit **pas** sur un jeu RVB + neutres. Le chemin qui exerce cette
# capacite -- celui dont `EPIC5-ARB-57` constatait a juste titre l'absence -- existe
# depuis cet arbitrage, et c'est celui-la.
#
# **Ce preset ne remplace pas `patches-14-v3`, qui reste enregistre et inchange**: une
# planche deja imprimee declare ses valeurs par son `patch_preset_id`.
#
# Capacite, verifiee et non supposee: 17 valeurs x 2 = **34 pastilles** pour un
# plafond de `MAX_PATCHES_PER_PAGE` = 36, et **17 rangees par cote** sous la v2 (une
# colonne par cote) pour une capacite laterale de 26 en portrait et de **17 exactement
# en paysage**. Le paysage v2 est donc au bord: une dix-huitieme valeur rendrait le
# couple infaisable, et c'est un test qui le dit plutot qu'un commentaire.
#
# **Decoupe en colonnes: aucune chaine de lecture n'est coupee**, meme contrainte que
# `_ORDER_14` et `_ORDER_18`. Sous la v2 la colonne est unique (17 d'un bloc); sous la
# v1 portrait (2 colonnes par cote) la coupe tombe a 9 / 8, et l'ordre ci-dessous est
# ecrit pour que cette coupe passe **entre** deux chaines: rouge (3) + vert (3) +
# neutre median + cyan + magenta = 9, puis bleu (3) + noir (2) + blanc (2) + jaune = 8.
_ORDER_17 = (
    # Chaine rouge, chaine verte, le neutre median, puis deux secondaires -> 9.
    "primary-red", "sentinel-red-1", "sentinel-red-2",
    "primary-green", "sentinel-green-1", "sentinel-green-2",
    "neutral-065",
    "secondary-cyan", "secondary-magenta",
    # Chaine bleue, chaine noire, chaine blanche, la troisieme secondaire -> 8.
    "primary-blue", "sentinel-blue-1", "sentinel-blue-2",
    "neutral-020", "sentinel-black-1",
    "neutral-245", "sentinel-white-1",
    "secondary-yellow",
)

# La version de table est EPINGLEE en litteral, jamais via
# ACTIVE_PATCH_VALUES_VERSION (revue 4.8, confirmee par trois relecteurs):
# une planche imprimee declare ses valeurs transitivement par
# patch_preset_id -> preset -> version de table. Si le preset referencait
# l'alias actif, publier une table v2 et basculer l'alias rebrancherait les
# planches DEJA imprimees sur les nouvelles valeurs -- l'edition en place
# que le versionnement 4.8 existe pour interdire. Un nouveau jeu de valeurs
# exige de nouveaux presets (patches-*-v2) epingles sur la nouvelle version.
_PRESETS: dict[str, PatchPreset] = {
    "patches-9-v1": PatchPreset(
        preset_id="patches-9-v1",
        values_version="patch-values-1",
        value_ids=_ORDER_9,
        repetition=2,
    ),
    "patches-12-v1": PatchPreset(
        preset_id="patches-12-v1",
        values_version="patch-values-1",
        value_ids=_ORDER_12,
        repetition=2,
    ),
    "patches-18-v2": PatchPreset(
        preset_id="patches-18-v2",
        values_version="patch-values-2",
        value_ids=_ORDER_18,
        repetition=2,
    ),
    "patches-14-v3": PatchPreset(
        preset_id="patches-14-v3",
        values_version="patch-values-3",
        value_ids=_ORDER_14,
        repetition=2,
    ),
    "patches-17-v4": PatchPreset(
        preset_id="patches-17-v4",
        values_version="patch-values-4",
        value_ids=_ORDER_17,
        repetition=2,
    ),
}

#: Ordre de chaque preset, **hisse au module** (story 5.16): il etait local a
#: `_build_placements`, et le motif chiffre du refus d'un couple infaisable a besoin
#: du cardinal par cote pour se calculer plutot que se recopier.
_PRESET_ORDERS: dict[str, tuple[str, ...]] = {
    "patches-9-v1": _ORDER_9,
    "patches-12-v1": _ORDER_12,
    "patches-18-v2": _ORDER_18,
    "patches-14-v3": _ORDER_14,
    "patches-17-v4": _ORDER_17,
}

# Geometrie des deux colonnes laterales sur le template portrait 2 zones
# (verifiee contre layout par le test geometrique): premiere rangee a 62 mm,
# pas de 14 mm (12 + 2), colonnes a 14 mm et 184 mm du bord gauche.
_COLUMN_LEFT_X_MM = 14.0
_COLUMN_RIGHT_X_MM = 184.0
_COLUMN_FIRST_Y_MM = 62.0
_COLUMN_STEP_MM = PATCH_SIZE_MM + PATCH_SPACING_MM


def _two_column_placement(order: tuple[str, ...]) -> tuple[tuple[str, float, float], ...]:
    """Placement portrait: colonne gauche dans l'ordre, colonne droite en
    ordre inverse (chaque valeur deux fois, aux extremites opposees)."""
    placements: list[tuple[str, float, float]] = []
    for row, value_id in enumerate(order):
        placements.append((value_id, _COLUMN_LEFT_X_MM, _COLUMN_FIRST_Y_MM + row * _COLUMN_STEP_MM))
    for row, value_id in enumerate(reversed(order)):
        placements.append((value_id, _COLUMN_RIGHT_X_MM, _COLUMN_FIRST_Y_MM + row * _COLUMN_STEP_MM))
    return tuple(placements)


# Geometrie paysage: la bande laterale libre (y [60, 150], voir
# page_templates) ne loge que 6 rangs au pas de 14 mm -> deux colonnes par
# cote, a l'exterieur de la bande de frames (x >= 48).
_PAYSAGE_LEFT_OUTER_X_MM = 14.0
_PAYSAGE_LEFT_INNER_X_MM = 30.0
_PAYSAGE_RIGHT_INNER_X_MM = 255.0
_PAYSAGE_RIGHT_OUTER_X_MM = 271.0
_PAYSAGE_FIRST_Y_MM = 62.0

#: Sequences de colonnes paysage par preset, posees explicitement plutot que
#: derivees d'une decoupe: l'ordre de colonne est une propriete de lecture de
#: la planche imprimee, pas un detail d'implementation. Elles etaient a
#: l'origine calculees pour que l'alternance neutre / couleur tienne
#: horizontalement entre colonnes voisines; cette exigence est **amendee par
#: EPIC5-ARB-17(a)** (voir docstring du module) et les sequences sont
#: desormais conservees telles quelles au titre de la non-regression, pas de
#: l'alternance.
#: (colonne_exterieure, colonne_interieure), identiques des deux cotes -- la
#: copie gauche et la copie droite d'une valeur sont a plus de 200 mm.
#: L'alternance neutre / couleur qui motivait ces sequences est amendee par
#: EPIC5-ARB-17(a) (voir docstring du module); les deux presets livres
#: conservent neanmoins **exactement** leurs sequences, aucune pastille
#: existante ne bouge.
_PAYSAGE_COLUMNS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "patches-9-v1": (_ORDER_9[0:5], _ORDER_9[5:9]),
    "patches-12-v1": (
        _ORDER_12[0:6],
        (_ORDER_12[7], _ORDER_12[6], _ORDER_12[9], _ORDER_12[8], _ORDER_12[11], _ORDER_12[10]),
    ),
}


def _four_column_placement(preset_id: str) -> tuple[tuple[str, float, float], ...]:
    """Placement paysage: deux colonnes par cote, memes sequences des deux
    cotes (une copie a gauche, une a droite, jamais deux copies proches)."""
    outer, inner = _PAYSAGE_COLUMNS[preset_id]
    placements: list[tuple[str, float, float]] = []
    for column_x, sequence in (
        (_PAYSAGE_LEFT_OUTER_X_MM, outer),
        (_PAYSAGE_LEFT_INNER_X_MM, inner),
        (_PAYSAGE_RIGHT_INNER_X_MM, inner),
        (_PAYSAGE_RIGHT_OUTER_X_MM, outer),
    ):
        for row, value_id in enumerate(sequence):
            placements.append((value_id, column_x, _PAYSAGE_FIRST_Y_MM + row * _COLUMN_STEP_MM))
    return tuple(placements)


# --- Geometrie reposee du preset sentinelle (story 5.9, AC 9) --------------
#
# Point dur: ce ne sont PAS des colonnes ajoutables a la geometrie actuelle.
# Les colonnes existantes restant en place (portrait 14 et 184; paysage 14, 30,
# 255, 271), aucune colonne supplementaire ne tient -- a gauche il faudrait
# x <= 0, sous `PRINTER_MARGIN_MM`, et a droite x >= 28 pour une bande portrait
# qui s'arrete a 35. Le preset sentinelle repose donc **sa propre** geometrie
# de colonnes, ce qui est licite parce qu'un placement est defini par couple
# (template, preset): `patches-9-v1` et `patches-12-v1` conservent exactement
# les leurs (invariant 2 d'EPIC5-ARB-14).
#
# Portrait: 4 colonnes x 9 rangs = 36 pastilles. Bandes laterales libres
# x [5, 35] et x [175, 205]; dernier bord bas a 186 mm, sous la clearance de
# coin a 237 mm.
#
# La premiere colonne est posee **exactement** sur `PRINTER_MARGIN_MM`, donc
# sans un dixieme de jeu. C'est un choix, pas un oubli: 36 pastilles ne tiennent
# pas autrement, et la contrainte est « aucune encre a moins de 5 mm du bord »,
# que 5,0 respecte. La difference avec la tangence refusee cote bande de frames
# (x 249, portee a 252) est arithmetique et non stylistique: `5.0` est exact en
# binaire, alors que le bord de la bande de frames vaut
# `188.66666666666669 + 60.333333333333336`, donc `249.00000000000003`. Une
# tangence exacte est sure; une tangence a une valeur issue d'une division par
# trois ne l'est pas. Un test epingle les deux faits.
_SENTINEL_PORTRAIT_COLUMNS_X_MM = (5.0, 19.0, 177.0, 191.0)
_SENTINEL_PORTRAIT_ROWS = 9

# Paysage: 6 colonnes x 6 rangs = 36. Bandes libres x [5, 48] et x [249, 292];
# dernier bord bas a 144 mm, sous la bande libre qui s'arrete a 150.
#
# La colonne droite est le **miroir exact** de la gauche (dernier bord a
# 297 - PRINTER_MARGIN_MM = 292, comme le premier est a PRINTER_MARGIN_MM = 5),
# et non x 249/263/277 comme le proposait la story: poser une colonne a 249
# la rend **tangente** au bord droit de la bande de frames, qui s'arrete
# exactement a 249,0. Mesure: sur `tpl-a4-paysage-6f-v1` la zone de frame la
# plus a droite vaut x = 188.66666666666669 + 60.333333333333336, soit
# 249.00000000000003 en flottant -- le contact exact ressort donc en
# chevauchement de 3e-14 mm et fait tomber le test geometrique. Le decalage de
# 3 mm rend la marge reelle et non nominale, et symetrise les deux cotes.
_SENTINEL_PAYSAGE_COLUMNS_X_MM = (5.0, 19.0, 33.0, 252.0, 266.0, 280.0)
_SENTINEL_PAYSAGE_ROWS = 6

#: Decoupe de `_ORDER_18` en colonnes, une sequence par colonne d'un cote. La
#: decoupe ne coupe aucune chaine de lecture (voir `_ORDER_18`), et la meme
#: sequence est reprise de l'autre cote: la copie gauche et la copie droite
#: d'une valeur sont alors a 158 mm en portrait et 216 mm en paysage, tres
#: au-dela du seuil de 100 mm du test d'eloignement des doublons.
_SENTINEL_PORTRAIT_COLUMNS = (_ORDER_18[0:9], _ORDER_18[9:18])
_SENTINEL_PAYSAGE_COLUMNS = (_ORDER_18[0:6], _ORDER_18[6:12], _ORDER_18[12:18])


def _sentinel_placement(
    columns_x_mm: tuple[float, ...],
    sequences: tuple[tuple[str, ...], ...],
    first_y_mm: float,
    step_mm: float,
) -> tuple[tuple[str, float, float], ...]:
    """Placement en colonnes: memes sequences repetees de chaque cote.

    ``columns_x_mm`` enumere les colonnes de gauche a droite, la premiere
    moitie a gauche et la seconde a droite; ``sequences`` donne le contenu
    d'une moitie et est reprise telle quelle pour l'autre.

    ``step_mm`` est **exige** et non pris par defaut sur `_COLUMN_STEP_MM`: ce pas est
    celui de la v1 (12 + 2), et une geometrie resserree pose ses pastilles au pas de
    9 mm. Un defaut aurait pose les pastilles de la v2 au pas de la v1 -- constate en
    ecrivant la story 5.15, avec une derniere rangee tombant dans le silence du
    marqueur du bas et un chevauchement de 1 mm avec son symbole.
    """
    if len(columns_x_mm) % 2 != 0:
        raise PatchPresetGeometryError(
            f"Geometrie sentinelle incoherente: {len(columns_x_mm)} colonnes, un "
            "nombre pair est attendu (une moitie a gauche, une a droite, pour que "
            "les deux copies d'une valeur soient aux extremites opposees)."
        )
    half = len(columns_x_mm) // 2
    if half != len(sequences):
        raise PatchPresetGeometryError(
            f"Geometrie sentinelle incoherente: {len(columns_x_mm)} colonnes pour "
            f"{len(sequences)} sequences par cote."
        )
    placements: list[tuple[str, float, float]] = []
    for index, column_x in enumerate(columns_x_mm):
        sequence = sequences[index % half]
        for row, value_id in enumerate(sequence):
            placements.append((value_id, column_x, first_y_mm + row * step_mm))
    return tuple(placements)


#: Enumeration EXPLICITE des templates couverts par un placement, par
#: orientation (revue 4.7): ce registre ne derive JAMAIS sa couverture de
#: ``page_templates.known_template_ids()``. Un template ajoute au registre
#: 4.1 ne recoit donc aucun placement par effet de bord: il reste
#: ``UndefinedPlacementError`` jusqu'a ce qu'un humain l'ajoute ici -- et le
#: test ``test_every_known_template_has_both_preset_couples_defined`` echoue
#: alors bruyamment, transformant l'ajout en decision plutot qu'en accident.
_PLACEMENT_COVERED_CARDINALS: dict[str, tuple[int, ...]] = {
    page_templates.ORIENTATION_PORTRAIT: (1, 2, 3, 4, 6, 8),
    page_templates.ORIENTATION_PAYSAGE: (1, 2, 4, 6, 8),
}
_PLACEMENT_COVERED_MARGINS: tuple[str, ...] = ("0", "2", "5")

#: Versions de geometrie couvertes, enumerees LOCALEMENT elles aussi (story 5.15):
#: une version ajoutee au registre 4.1 ne recoit aucune colonne par effet de bord.
_PLACEMENT_COVERED_GEOMETRY_VERSIONS: tuple[str, ...] = ("v1", "v2")

#: Couples (version de geometrie, orientation, preset) dont le placement ne tient
#: **pas**, avec le chiffre qui le dit. Enumeres ici pour que la lacune soit une
#: decision lisible et non un trou du registre: `resolve_patch_layout` refuse alors le
#: couple en nommant la cause, et un test epingle cet ensemble exactement -- il echoue
#: donc aussi bien si la liste grandit en silence que si elle rapetisse.
#:
#: Mesure du cas unique connu, **refaite a la passe de correction de 5.15**:
#: `patches-18-v2` pose 18 pastilles par cote; sous la v2, la hauteur qu'une colonne
#: laterale d'une page paysage peut reellement remplir vaut **151 mm** -- 210 de page,
#: moins le silence du marqueur du bas (28), moins l'ordonnee de la premiere rangee
#: (31, soit le silence du marqueur du haut plus un espacement de pastille). Le chiffre
#: de 154 mm qui figurait ici oubliait cet espacement de tete: il decrivait le couloir
#: entre les deux silences, pas ce que `_derived_row_capacity` mesure. La conclusion ne
#: change pas -- 18 rangees de 6 mm au pas de 9 mm en exigent 159, et la capacite
#: reelle est de 17 rangees. La v2 n'ouvre qu'**une** colonne par cote, parce que c'est cette colonne unique
#: qui rend la bande de dessin large (`EPIC5-ARB-57`): ajouter une seconde colonne pour
#: ce seul preset reprendrait au dessin ce que la story 5.15 lui donne.
_PLACEMENT_UNPLACEABLE: tuple[tuple[str, str, str], ...] = (
    ("v2", page_templates.ORIENTATION_PAYSAGE, "patches-18-v2"),
)


# --- Placement derive des versions de geometrie ajoutees apres le 2026-08-11 ---
#
# Les colonnes de la v1 sont des abscisses **litterales** (14 / 184 en portrait,
# 14 / 30 / 255 / 271 en paysage) et elles le restent: une planche imprimee ne bouge
# pas. Toute version ajoutee ensuite derive ses colonnes de ses constituants -- taille
# de pastille, espacement, marge d'encre, nombre de colonnes par cote -- parce que
# c'est la seule facon qu'un resserrement des marqueurs deplace effectivement les
# pastilles. Le placement reste defini **par couple** (template_id, preset_id): rien
# n'est deduit par rotation ni par interpolation, et un couple qui ne tient pas
# geometriquement est refuse au lieu d'etre approxime.


def _derived_columns_x_mm(
    geometry: page_templates.PageGeometry, orientation: str, page_width_mm: float
) -> tuple[float, ...]:
    """Abscisses des colonnes de pastilles, de gauche a droite, moitie par moitie.

    Premiere colonne posee exactement sur la marge d'encre, colonnes suivantes vers
    l'interieur au pas `taille + espacement`; le cote droit est le miroir exact du
    gauche, si bien que les deux copies d'une valeur sont aux extremites opposees de
    la feuille (la moyenne par page capture alors la non-uniformite d'eclairage).
    """
    columns = geometry.patch_columns_per_side[orientation]
    step = geometry.patch_size_mm + geometry.patch_spacing_mm
    left = tuple(geometry.printer_margin_mm + index * step for index in range(columns))
    right = tuple(
        page_width_mm - geometry.printer_margin_mm - geometry.patch_size_mm
        - index * step
        for index in reversed(range(columns))
    )
    return left + right


def _derived_first_row_y_mm(geometry: page_templates.PageGeometry) -> float:
    """Ordonnee de la premiere rangee: juste sous le silence des marqueurs du haut.

    Les colonnes laterales sont dans la meme bande d'abscisses que les marqueurs de
    coin, donc elles ne peuvent commencer qu'apres leur zone de silence. Un espacement
    de pastille les en separe -- exactement ce que rend la v1 (60 + 2 = 62 mm).

    **Delegue a `PageGeometry` depuis la story 5.18**: cette ordonnee ne sert plus qu'ici,
    elle decide aussi si un QR pose sur un flanc a de la place **sous** la colonne. Deux
    recettes divergeraient au premier changement, et le symptome serait un QR imprime
    par-dessus des pastilles.
    """
    return geometry.lateral_first_row_y_mm()


def _derived_row_capacity(
    geometry: page_templates.PageGeometry, orientation: str
) -> int:
    """Rangees qu'une colonne laterale peut porter entre les deux silences de coin.

    **Delegue a `PageGeometry` depuis la story 5.18**, meme motif que
    `_derived_first_row_y_mm`: la capacite du couloir borne aussi la hauteur libre qu'un
    QR de flanc peut occuper, donc elle doit avoir une seule implementation.
    """
    return geometry.lateral_row_capacity(orientation)


def _derived_placement(
    geometry: page_templates.PageGeometry,
    orientation: str,
    page_width_mm: float,
    order: tuple[str, ...],
) -> tuple[tuple[str, float, float], ...] | None:
    """Placement derive d'un preset sous une geometrie, ou ``None`` s'il ne tient pas.

    ``None`` -- et non un placement tronque ni une colonne surnumeraire posee dans la
    bande de dessin: un preset qui ne tient pas sous une geometrie est un couple
    **refuse**, avec le motif chiffre dans le message. C'est le cas mesure de
    `patches-18-v2` en paysage v2: 18 rangees au pas de 9 mm exigent 159 mm quand le
    couloir entre les deux silences de coin en offre 154.
    """
    columns_x = _derived_columns_x_mm(geometry, orientation, page_width_mm)
    per_side = len(columns_x) // 2
    capacity = _derived_row_capacity(geometry, orientation)
    if per_side < 1 or capacity < 1:
        return None
    # Decoupe de la sequence en colonnes d'un cote, sans jamais couper une valeur en
    # deux: chaque colonne recoit une tranche contigue, et la meme decoupe est reprise
    # de l'autre cote.
    rows = -(-len(order) // per_side)  # division entiere par exces
    if rows > capacity:
        return None
    sequences = tuple(
        order[index * rows:(index + 1) * rows] for index in range(per_side)
    )
    # Refus d'une colonne **vide**. La garde qui vivait ici -- « la somme des tranches
    # differe du cardinal de l'ordre » -- etait morte, et demontree telle par la revue
    # de la story 5.15: la division par exces garantit `per_side * rows >= len(order)`,
    # donc les tranches couvrent toujours toute la sequence (verifie exhaustivement sur
    # `per_side` de 1 a 19 et `len(order)` de 1 a 39, jamais declenchee). La
    # degenerescence que sa forme suggerait, elle, est bien atteignable et n'etait
    # refusee par rien: avec plus de colonnes par cote que de rangees a remplir, les
    # dernieres tranches sont **vides** -- et `page_templates.patch_block_end_mm` a
    # deja rentre le bord de la bande de dessin pour **toutes** les colonnes du cote.
    # La planche paierait donc de la surface de dessin pour des colonnes qui
    # n'impriment rien, en silence. Mesure de la revue: 12 colonnes par cote et 9
    # valeurs -> 24 colonnes reservees, 18 servies. Inatteignable par les deux versions
    # enregistrees (une colonne par cote en v2), atteignable par la prochaine.
    #
    # Le refus est volontairement plus strict que « ca rentre »: 9 valeurs sur 4
    # colonnes par cote *tiendraient* sur trois colonnes, mais la quatrieme aurait
    # deja ete payee en surface de dessin. Un couple refuse se lit dans un message et
    # se corrige par une decision (declarer moins de colonnes, ou poser plus de
    # valeurs); une bande silencieusement rognee ne se lit nulle part.
    if any(not sequence for sequence in sequences):
        return None
    first_y = _derived_first_row_y_mm(geometry)
    return _sentinel_placement(
        columns_x, sequences, first_y,
        geometry.patch_size_mm + geometry.patch_spacing_mm,
    )


def _build_placements() -> dict[tuple[str, str], tuple[tuple[str, float, float], ...]]:
    """Enregistrement explicite de chaque couple template x preset.

    Les templates couverts sont enumeres LOCALEMENT (constantes ci-dessus),
    jamais decouverts depuis le registre 4.1. Le placement d'un couple est
    celui de sa famille d'orientation -- legitime parce que le registre de
    templates garantit une bande de frames unique par orientation -- et le
    test geometrique verifie chaque couple contre la geometrie reelle de SON
    template: un placement qui ne tiendrait pas sur un template particulier
    fait echouer la suite.
    """
    placements: dict[tuple[str, str], tuple[tuple[str, float, float], ...]] = {}
    families = {
        page_templates.ORIENTATION_PORTRAIT: {
            "patches-9-v1": _two_column_placement(_ORDER_9),
            "patches-12-v1": _two_column_placement(_ORDER_12),
            "patches-18-v2": _sentinel_placement(
                _SENTINEL_PORTRAIT_COLUMNS_X_MM,
                _SENTINEL_PORTRAIT_COLUMNS,
                _COLUMN_FIRST_Y_MM,
                _COLUMN_STEP_MM,
            ),
        },
        page_templates.ORIENTATION_PAYSAGE: {
            "patches-9-v1": _four_column_placement("patches-9-v1"),
            "patches-12-v1": _four_column_placement("patches-12-v1"),
            "patches-18-v2": _sentinel_placement(
                _SENTINEL_PAYSAGE_COLUMNS_X_MM,
                _SENTINEL_PAYSAGE_COLUMNS,
                _PAYSAGE_FIRST_Y_MM,
                _COLUMN_STEP_MM,
            ),
        },
    }
    orders = _PRESET_ORDERS
    for version in _PLACEMENT_COVERED_GEOMETRY_VERSIONS:
        geometry = page_templates.get_geometry(version)
        for orientation, cardinals in _PLACEMENT_COVERED_CARDINALS.items():
            page_width_mm, _page_height_mm = page_templates.page_size_mm(orientation)
            # Intersection avec le vocabulaire **de la version**: un cardinal retire
            # (`EPIC5-ARB-62`) n'a plus de `template_id`, donc lui chercher un placement
            # leverait sur un identifiant inexistant. L'enumeration locale reste
            # l'autorite sur ce que ce module place -- elle n'est pas remplacee par le
            # registre, elle est croisee avec lui.
            for cardinal in cardinals:
                if cardinal not in page_templates.frames_per_page_vocabulary(
                        orientation, version):
                    continue
                for margin in _PLACEMENT_COVERED_MARGINS:
                    template_id = page_templates.build_template_id(
                        orientation, cardinal, margin, version
                    )
                    for preset_id in tuple(_PRESETS):
                        if (version, orientation, preset_id) in _PLACEMENT_UNPLACEABLE:
                            continue
                        literal = (families[orientation].get(preset_id)
                                   if version == "v1" else None)
                        if literal is not None:
                            # Colonnes litterales de la v1: une planche imprimee ne
                            # bouge pas, et ces abscisses n'ont pas de formule.
                            #
                            # **Un preset introduit apres la v1 n'a pas de litteral,
                            # et il n'en a pas besoin** (story 5.16): les abscisses
                            # litterales existent pour que les planches **deja
                            # imprimees** ne bougent pas. Un preset qui n'a jamais
                            # ete imprime sous la v1 n'a rien a preserver, donc il
                            # derive ses colonnes comme sous toute autre version --
                            # et il les derive des constituants de la v1, donc dans
                            # sa geometrie, pas dans celle d'une autre.
                            placement = literal
                        else:
                            placement = _derived_placement(
                                geometry, orientation, page_width_mm, orders[preset_id]
                            )
                            if placement is None:
                                raise PatchPresetGeometryError(
                                    f"Aucun placement derivable pour '{template_id}' x "
                                    f"'{preset_id}' sous la geometrie {version}: le "
                                    "couple doit alors etre enumere dans "
                                    "_PLACEMENT_UNPLACEABLE avec son chiffre, pas "
                                    "laisse tomber en silence."
                                )
                        placements[(template_id, preset_id)] = placement
    return placements


#: Placements explicites par couple (template_id, preset_id). Tout nouveau
#: couple se definit ici et passe par le test geometrique -- jamais deduit.
_PLACEMENTS = _build_placements()

# Zones reservees par orientation (QR 4.1, texte 4.2, pied de page technique),
# en mm dans le repere du template. Elles bornent le placement des patchs
# (test 4.7); la confrontation des emprises reelles du QR et du texte aux
# patchs vit dans le test global de plan de page de 4.1 (voir docstring de
# `reserved_zones_mm`).
_PORTRAIT_RESERVED_ZONES: tuple[dict, ...] = (
    # Cible QR 4.6: 35 mm + quiet zone ISO, centre de la bande haute.
    {"name": "qr_zone", "x": 85.0, "y": 10.0, "width": 40.0, "height": 40.0},
    # Gabarits de blocs de texte 4.2 (identifiant de planche, projet,
    # page N/M, date-heure), bande haute de part et d'autre du QR.
    {"name": "text_header_left", "x": 60.0, "y": 10.0, "width": 25.0, "height": 40.0},
    {"name": "text_header_right", "x": 125.0, "y": 10.0, "width": 25.0, "height": 40.0},
    # Bloc d'informations bas de page (4.2), entre les quiet zones des
    # marqueurs du bas.
    {"name": "text_footer_block", "x": 60.0, "y": 240.0, "width": 90.0, "height": 45.0},
    # Ligne de pied de page technique (alignee sur le plan reel de 4.1,
    # y [286, 292], entre les silences des marqueurs du bas -- revue 4.7: la
    # reservation heritee du POC courait sous les marqueurs et laissait la
    # bande [286, 288] hors de toute emprise).
    {"name": "text_footer_line", "x": 60.0, "y": 286.0, "width": 90.0, "height": 6.0},
)

_PAYSAGE_RESERVED_ZONES: tuple[dict, ...] = (
    {"name": "qr_zone", "x": 128.5, "y": 10.0, "width": 40.0, "height": 40.0},
    {"name": "text_header_left", "x": 60.0, "y": 10.0, "width": 66.0, "height": 40.0},
    {"name": "text_header_right", "x": 171.0, "y": 10.0, "width": 66.0, "height": 40.0},
    {"name": "text_footer_block", "x": 60.0, "y": 154.0, "width": 177.0, "height": 42.0},
    {"name": "footer_line", "x": 60.0, "y": 198.0, "width": 177.0, "height": 6.0},
)

def _derived_reserved_zones(template_id: str) -> tuple[dict, ...]:
    """Zones reservees d'un gabarit d'une version **ajoutee** apres le 2026-08-11.

    Les cinq zones de la v1 sont des litteraux calibres a la main sur sa bande haute
    de 50 mm et son pied de page de 45 mm; sous la v2 la bande haute ne fait plus que
    38,8 mm et le pied de page ouvre 8 mm plus haut. Recopier les litteraux
    reserverait donc de la place la ou il n'y a plus rien et n'en reserverait plus la
    ou l'encre est passee -- une reservation fausse est pire qu'absente, parce qu'elle
    a l'air d'une garde.
    """
    spec = page_templates.get_template(template_id)
    # L'emprise reservee est posee **la ou le gabarit met son QR**, jamais au centre de
    # la bande haute par convention: depuis la story 5.18 le bord porteur est calcule, et
    # une reservation fausse est pire qu'absente parce qu'elle a l'air d'une garde. La
    # recette du placement vit dans `page_templates` -- une seconde copie ici
    # divergerait de celle que la composition applique.
    qr_x, band_y, footprint, band_height = page_templates.qr_reserved_zone_mm(spec)
    zones = [
        {"name": "qr_zone", "x": qr_x, "y": band_y,
         "width": footprint, "height": band_height},
    ]
    # La bande **haute** porte les textes d'en-tete quel que soit le bord du QR: quand le
    # QR n'y est pas, elle est libre sur toute sa largeur.
    header_x, header_y, header_width, header_height = page_templates.header_band_mm(spec)
    if spec.qr_edge == page_templates.QR_EDGE_TOP:
        left_width = qr_x - header_x
        if left_width > 0:
            zones.append({"name": "text_header_left", "x": header_x, "y": header_y,
                          "width": left_width, "height": header_height})
        right_x = qr_x + footprint
        right_width = header_x + header_width - right_x
        if right_width > 0:
            zones.append({"name": "text_header_right", "x": right_x, "y": header_y,
                          "width": right_width, "height": header_height})
    elif header_height > 0:
        zones.append({"name": "text_header", "x": header_x, "y": header_y,
                      "width": header_width, "height": header_height})
    for key, rect in sorted(page_templates.footer_zones_mm(spec).items()):
        x, y, width, height = rect
        zones.append({"name": f"text_{key}", "x": x, "y": y,
                      "width": width, "height": height})
    return tuple(zones)


_RESERVED_ZONES: dict[str, tuple[dict, ...]] = {
    template_id: (
        (
            _PORTRAIT_RESERVED_ZONES
            if page_templates.get_template(template_id).orientation
            == page_templates.ORIENTATION_PORTRAIT
            else _PAYSAGE_RESERVED_ZONES
        )
        if page_templates.get_template(template_id).geometry_version == "v1"
        else _derived_reserved_zones(template_id)
    )
    for template_id in page_templates.known_template_ids()
}


# ---------------------------------------------------------------------------
# Ce que le ROLE DE PAGE derive (story 5.16, AC 3 et 4)
# ---------------------------------------------------------------------------
#
# `template_id` decrit la geometrie des pages d'**images** du lot; la mise en page
# effective d'une page se derive du couple `(template_id, role de page)` -- voir
# `page_roles` pour la contrainte qui force cette forme. Deux attributs se derivent
# du meme couple, et c'est **un seul mecanisme applique deux fois**, pas deux
# mecanismes: la taille de pastille et le plafond de pastilles par page.
#
# Les deux tables sont indexees par le role et rien d'autre. C'est deliberement la
# forme la plus fragile a une **permutation** -- famille du mutant `M33` de la
# story 5.6, rencontree quatre fois dans ce depot -- pour que la permutation soit
# fatale a un test plutot qu'invisible: un role echange fait imprimer 12 mm sur une
# planche d'images (la premiere colonne mord alors dans la zone de dessin, defaut
# constate en ecrivant la story 5.15) et 6 mm sur la page dont depend toute la
# correction du lot.

#: Taille de pastille par role. La planche d'images lit la geometrie **de son
#: gabarit** -- une version resserree pose 6 mm et c'est cette taille qui a servi a
#: calculer sa bande de frames; la page de calibration lit
#: :data:`CALIBRATION_PATCH_SIZE_MM`, qui n'a pas de bande a respecter.
_PATCH_SIZE_MM_BY_ROLE = {
    PAGE_ROLE_IMAGES: lambda spec: spec.geometry.patch_size_mm,
    PAGE_ROLE_CALIBRATION: lambda spec: CALIBRATION_PATCH_SIZE_MM,
}

#: Replicats du treillis sur la page de calibration. **Meme motif que la repetition
#: des presets, et il n'est pas negociable**: une valeur vue une seule fois n'a pas
#: de dispersion, donc `replicate_dispersion` n'a rien a mesurer et la garde
#: d'`EPIC5-ARB-49` devient aveugle -- on ne distingue plus « cette page diverge » de
#: « ce papier est bruyant ». Le cardinal imprime est donc 65 valeurs x 2 = **130
#: pastilles**, ce qui est exactement le compte que la story 5.16 epingle.
CALIBRATION_LATTICE_REPETITION = 2

#: Plafond de pastilles par page, par role. La planche d'images garde
#: :data:`MAX_PATCHES_PER_PAGE`, mesure dans les bandes **laterales libres** donc
#: valide seulement a cote d'une bande de frames; la page de calibration derive le
#: sien de sa grille, qui est ce que la page peut reellement porter.
_PATCH_CEILING_BY_ROLE = {
    PAGE_ROLE_IMAGES: lambda spec: MAX_PATCHES_PER_PAGE,
    PAGE_ROLE_CALIBRATION: lambda spec: spec.geometry.calibration_grid(
        spec.orientation, CALIBRATION_PATCH_SIZE_MM).capacity,
}


@dataclass(frozen=True)
class PageLayout:
    """Mise en page **effective** d'une page, derivee du couple gabarit x role.

    C'est l'objet qui rend lisible la consequence semantique de l'AC 3: deux pages
    du meme lot portent le **meme** `template_id` -- l'invariant d'identite de lot
    l'exige -- et n'impriment pourtant pas la meme chose. Sans cet objet, la
    difference se reconstituerait a partir de trois appels dont rien ne dit qu'ils
    decrivent la meme page.
    """

    template_id: str
    page_role: str
    #: Zones de dessin. **Vide** sur une page de calibration: elle ne porte aucune
    #: frame, et c'est ce qui libere sa surface entiere pour le treillis.
    frame_zones_mm: tuple[dict, ...]
    patch_size_mm: float
    patch_ceiling: int
    #: Nom du placement retenu, pour qu'il soit **lisible** plutot que reconstitue:
    #: une surface egale ne dit pas quel placement l'a produite (meme motif que
    #: `TemplateSpec.witness_placement`).
    patch_placement: str
    reserved_zones_mm: tuple[dict, ...]


def patch_size_mm_for(template_id: str, page_role: str) -> float:
    """Cote d'une pastille sur ce gabarit sous ce role de page."""
    spec = page_templates.get_template(template_id)
    return float(_PATCH_SIZE_MM_BY_ROLE[validate_page_role(page_role)](spec))


def patch_ceiling_for(template_id: str, page_role: str) -> int:
    """Plafond de pastilles physiques sur ce gabarit sous ce role de page."""
    spec = page_templates.get_template(template_id)
    return int(_PATCH_CEILING_BY_ROLE[validate_page_role(page_role)](spec))


def resolve_page_layout(template_id: str, page_role: str) -> PageLayout:
    """Mise en page effective du couple ``(template_id, role de page)``."""
    role = validate_page_role(page_role)
    spec = page_templates.get_template(template_id)
    size_mm = patch_size_mm_for(template_id, role)
    ceiling = patch_ceiling_for(template_id, role)
    if role == PAGE_ROLE_CALIBRATION:
        grid = spec.geometry.calibration_grid(spec.orientation, size_mm)
        header = grid.header_zone_mm()
        qr_zone = grid.qr_zone_mm()
        return PageLayout(
            template_id=template_id,
            page_role=role,
            frame_zones_mm=(),
            patch_size_mm=size_mm,
            patch_ceiling=ceiling,
            patch_placement=page_templates.WITNESS_PLACEMENT_LATTICE,
            reserved_zones_mm=(
                {"name": "header_identity", "x": header[0], "y": header[1],
                 "width": header[2], "height": header[3]},
                {"name": "qr_zone", "x": qr_zone[0], "y": qr_zone[1],
                 "width": qr_zone[2], "height": qr_zone[3]},
            ),
        )
    return PageLayout(
        template_id=template_id,
        page_role=role,
        frame_zones_mm=spec.frame_zones_mm,
        patch_size_mm=size_mm,
        patch_ceiling=ceiling,
        patch_placement=spec.witness_placement,
        reserved_zones_mm=reserved_zones_mm(template_id),
    )


def resolve_calibration_page_patches(template_id: str) -> tuple[PlacedPatch, ...]:
    """Pastilles du treillis d'une page de calibration, dans l'ordre de lecture.

    Le jeu est derive du **role** et non d'un preset declare, et c'est une
    contrainte et non un gout: `patch_preset_id` est dans
    `io.reconstruction._LOT_LEVEL_FIELDS`, donc une page qui declarerait son propre
    preset serait refusee par l'invariant d'identite de lot -- et la story 5.12
    calcule son condensat de tirage sur cette reference, donc un preset
    page-dependant **scinderait un tirage en deux lots**.

    Le treillis est lu **filtre** (`patch_values.calibration_lattice_adjustment_values`):
    le filtre de saturation est une **regle** et non un reglage -- il ameliore la
    correction de 2,09 dE76, plus de cinq fois le gain de la page separee elle-meme,
    parce que la majorite du cube RVB est hors gamut et qu'aucune correction ne
    mappe une couleur inatteignable sur sa reference.
    """
    spec = page_templates.get_template(template_id)
    size_mm = patch_size_mm_for(template_id, PAGE_ROLE_CALIBRATION)
    grid = spec.geometry.calibration_grid(spec.orientation, size_mm)
    values = patch_values.calibration_lattice_adjustment_values()
    refus = calibration_page_refusal(template_id)
    if refus is not None:
        raise UndefinedPlacementError(refus)
    cells = grid.usable_cells_mm()
    # **Les deux replicats sont poses dans les deux moities de la grille, dans le
    # meme ordre**, et non l'un en ordre inverse de l'autre. La forme inversee est
    # celle des colonnes laterales (`_two_column_placement`), ou elle eloigne
    # effectivement les deux copies -- sur une **grille** elle fait l'inverse pour
    # les valeurs du milieu, qui se retrouvent voisines. Mesure des deux schemas sur
    # la geometrie livree, ecart minimal entre les deux copies d'une meme valeur:
    #
    #     schema          portrait   paysage
    #     deux moities     120,9 mm    96,0 mm
    #     ordre inverse     30,0 mm    15,0 mm
    #
    # L'ecart minimal du schema retenu est donc plus de six fois le pas de grille
    # dans les deux orientations, et un test le **derive** au lieu de le recopier: la
    # moyenne par page (story 5.4) ne capture la non-uniformite d'eclairage et de
    # scan que si les deux copies sont loin l'une de l'autre.
    #
    # Les cellules du **milieu** sont celles qui restent vides, et leur nombre est
    # exactement la marge de la page: 5 en paysage, 11 en portrait.
    first = cells[:len(values)]
    second = cells[len(cells) - len(values):]
    placed: list[PlacedPatch] = []
    for block in (first, second):
        # **`zip` tronque, et une pose tronquee ne se lit nulle part.** La garde de
        # capacite ci-dessus est censee avoir refuse ce cas, mais elle compare un
        # **cardinal** et cette boucle apparie des **positions**: si la premiere venait a
        # comparer autre chose que le nombre de pastilles physiques -- le cardinal des
        # valeurs plutot que celui des replicats, par exemple --, la page sortirait avec
        # moins de pastilles que le treillis n'en demande, sans un mot. Une page de
        # calibration amputee ajuste la correction du lot entier sur un jeu qu'elle ne
        # declare pas.
        if len(block) != len(values):
            raise UndefinedPlacementError(
                f"Pose incoherente du treillis sur '{template_id}': {len(block)} "
                f"cellule(s) pour {len(values)} valeur(s) a poser. La garde de capacite "
                "compare un cardinal de pastilles physiques "
                f"({CALIBRATION_LATTICE_REPETITION} replicats), et cette pose apparie "
                "des positions: les deux doivent parler du meme nombre."
            )
        for value, (x_mm, y_mm) in zip(values, block):
            placed.append(
                PlacedPatch(
                    value_id=value.value_id,
                    rgb=value.rgb,
                    x_mm=x_mm,
                    y_mm=y_mm,
                    size_mm=size_mm,
                    # Meme regle que sur une planche d'images: le cadre est decide
                    # par la **valeur**, jamais par le role ni par le preset.
                    frame_mm=PATCH_FRAME_MM
                    if patch_values.requires_printed_frame(value) else 0.0,
                )
            )
    return tuple(placed)


def resolve_calibration_page_witnesses(
    template_id: str, preset_id: str
) -> tuple[PlacedPatch, ...]:
    """Bandeau de temoins d'une page de calibration: **le meme preset qu'une planche**.

    Story 5.23, AC 1, `EPIC5-ARB-82` decision 3. La page de calibration porte le
    bandeau **par le mecanisme de bordure existant** -- les colonnes laterales que
    `resolve_patch_layout` pose deja sur une planche d'images --, et non en injectant
    des valeurs dans son treillis. Le motif est de maintenance et il est decisif:
    **un seul preset a faire evoluer**. Changer les temoins plus tard change les deux
    feuilles en meme temps, par construction, sans qu'aucune synchronisation soit a
    tenir.

    C'est aussi ce qui rend la mesure brute a brute d'`EPIC5-ARB-82` calculable: avant
    cette story les deux feuilles n'avaient **aucun identifiant de valeur en commun**
    (treillis `lattice-RRR-GGG-BBB` d'un cote, temoins nommes de l'autre), donc
    l'appariement par identifiant n'avait litteralement rien a apparier.

    Les deux jeux de la page ne se melangent pas et c'est volontaire:
    `resolve_calibration_page_patches` reste le **treillis seul**, qui est ce sur quoi
    la correction s'ajuste. Un temoin qui entrerait dans l'ajustement ferait ajuster la
    correction sur ce qu'il est precisement cense verifier.
    """
    refus = calibration_page_refusal(template_id)
    if refus is not None:
        raise UndefinedPlacementError(refus)
    witnesses = resolve_patch_layout(template_id, preset_id)
    # **La grille et les colonnes laterales ne se recouvrent pas, et ce n'est pas une
    # evidence: c'est une mesure a epingler.** Sous la v2, la grille du treillis part du
    # degagement de coin (28 mm) tandis que les colonnes laterales sont posees sur la
    # marge d'encre (5 mm), donc les deux se croisent... a 17 mm pres. Un degagement de
    # coin plus petit, une colonne de plus par cote ou une pastille plus large les
    # ferait se chevaucher, et le symptome serait une page qui imprime une pastille par
    # dessus une autre -- donc deux valeurs mesurees comme une seule, en silence.
    spec = page_templates.get_template(template_id)
    grid = spec.geometry.calibration_grid(
        spec.orientation, patch_size_mm_for(template_id, PAGE_ROLE_CALIBRATION))
    grid_x0, grid_y0 = grid.origin_x_mm, grid.origin_y_mm
    grid_x1 = grid_x0 + grid.columns * grid.step_mm - grid.spacing_mm
    grid_y1 = grid_y0 + grid.rows * grid.step_mm - grid.spacing_mm
    for patch in witnesses:
        overlaps_x = patch.x_mm < grid_x1 and patch.x_mm + patch.size_mm > grid_x0
        overlaps_y = patch.y_mm < grid_y1 and patch.y_mm + patch.size_mm > grid_y0
        if overlaps_x and overlaps_y:
            raise UndefinedPlacementError(
                f"Le temoin '{patch.value_id}' du preset '{preset_id}' tombe dans la "
                f"grille du treillis de '{template_id}': emprise du temoin "
                f"({patch.x_mm}, {patch.y_mm}) + {patch.size_mm} mm, grille "
                f"[{grid_x0}, {grid_x1}] x [{grid_y0}, {grid_y1}]. Deux pastilles "
                "superposees se mesurent comme une seule, sans qu'aucune etape "
                "n'echoue."
            )
    return witnesses


#: Presets dont une page de calibration **deja imprimee** porte a coup sur le bandeau de
#: temoins. Story 5.23, et c'est le pendant de lecture de l'AC 1.
#:
#: **Ce n'est pas la meme question que « la composition pose-t-elle un bandeau ? »**, et
#: la distinction est le fond de cette entree. La composition d'aujourd'hui pose le
#: bandeau sur toute page de calibration, quel que soit le preset; mais les feuilles qui
#: existent sur le bureau d'Egan ont ete imprimees **avant** la story 5.23, et leurs
#: colonnes laterales sont du papier nu. Un `patch_preset_id` lu au QR d'une feuille dit
#: ce qui est **sur cette feuille-la**, pas ce que la commande imprimerait aujourd'hui, et
#: c'est exactement le service que le versionnement des presets rend depuis la story 4.8.
#:
#: **Ce que ca coute d'y repondre par la mesure plutot que par cette table** a ete
#: mesure, le 2026-08-17, sur le lot reel `chendj-mat`: en echantillonnant le bandeau
#: d'une page de calibration anterieure, les deux planches sortaient avec un ecart brut a
#: brut de **58,72 et 59,05 dE76** -- l'ecart entre des pastilles imprimees et du papier
#: blanc. C'est un avertissement chiffre, permanent, et vrai de rien; et un avertissement
#: permanent ne se lit plus. Les criteres de mesure essayes pour l'eviter (etendue du
#: bandeau contre bruit de replicats de la page) ne tiennent pas: sur du papier nu, le
#: vignettage d'un scanner a plat depasse le bruit entre deux repliques voisines, donc le
#: critere declare « imprime » un bandeau vide.
#:
#: **Le sens du refus est asymetrique, et c'est delibere**: un preset absent de cette
#: table fait **taire** la mesure de divergence, jamais avertir a tort. Un tirage neuf
#: compose avec un preset archive porterait donc un bandeau que rien ne lirait -- un
#: silence, pas une faussete --, et c'est le bon cote sur lequel se tromper pour une
#: grandeur dont `EPIC5-ARB-82` dit qu'elle ne refuse rien.
CALIBRATION_PAGE_BAND_PRESETS: frozenset = frozenset({"patches-17-v4"})


def calibration_page_carries_witness_band(preset_id: str) -> bool:
    """Une page de calibration declarant ce preset porte-t-elle le bandeau de temoins ?

    Passe par `get_patch_preset`, donc un identifiant inconnu **leve** au lieu de rendre
    `False`: « je ne connais pas ce preset » et « ce preset n'a pas de bandeau » sont deux
    faits differents, et les confondre ferait taire la mesure de divergence sur une faute
    de frappe, sans un mot.
    """
    get_patch_preset(preset_id)
    return preset_id in CALIBRATION_PAGE_BAND_PRESETS


def calibration_page_patch_count(preset_id: str) -> int:
    """Pastilles **totales** d'une page de calibration: son treillis et son bandeau.

    Derive des deux jeux et jamais recopie: c'est le cardinal qu'un test confronte au
    plan de page, et une page qui declarerait moins que ce qu'elle imprime serait
    exactement le faux succes que la garde de pose du treillis ferme deja.
    """
    preset = get_patch_preset(preset_id)
    return (calibration_lattice_patch_count()
            + len(preset.value_ids) * preset.repetition)


def calibration_lattice_patch_count() -> int:
    """Pastilles qu'une page de calibration imprime: le treillis filtre, en replicats.

    Derive du descripteur du treillis et non recopie: 65 valeurs sous le seuil de
    saturation en double replicat, soit **130**. Le 106 du banc de recherche etait un
    compte de **lecture** sur un scan particulier, et il n'est pas re-mesurable.
    """
    return (len(patch_values.calibration_lattice_adjustment_values())
            * CALIBRATION_LATTICE_REPETITION)


def calibration_page_refusal(template_id: str) -> str | None:
    """Motif **chiffre** pour lequel ce gabarit ne peut pas porter de page de
    calibration, ou ``None`` s'il peut.

    **Toutes les geometries ne peuvent pas en porter une, et ce n'est pas un defaut:
    c'est une mesure.** Le dimensionnement de la story 5.16 -- 12 mm de pastille, 141
    cellules en portrait et 135 en paysage -- est celui de la **v2**, dont le degagement
    de coin vaut 28 mm. Sous la **v1**, ou il vaut 60 mm, la grille tombe a 6 x 12
    cellules en portrait, soit **57** utilisables pour un treillis qui en demande 130.
    Une page de calibration n'y tient donc pas, a aucune taille utile de pastille.

    Consequence retenue, et c'est la seule qui preserve l'additivite de l'AC 12: **un lot
    v1 se compose exactement comme avant la story**, sans page de calibration et sans
    decalage de pagination. Le drapeau `--geometrie v1` sert a recomposer ce qui est deja
    imprime; y ajouter une page en decalerait la numerotation de pied, ce que l'AC 12
    interdit precisement.

    Le motif est rendu plutot que leve, parce que l'appelant a **deux** usages: la
    composition doit pouvoir le publier en avertissement (une page absente en silence
    serait exactement le faux succes que le depot combat), et
    `resolve_calibration_page_patches` doit pouvoir le lever. Une seule redaction pour
    les deux: deux messages divergeraient.
    """
    spec = page_templates.get_template(template_id)
    size_mm = patch_size_mm_for(template_id, PAGE_ROLE_CALIBRATION)
    ceiling = patch_ceiling_for(template_id, PAGE_ROLE_CALIBRATION)
    count = calibration_lattice_patch_count()
    if count <= ceiling:
        return None
    grid = spec.geometry.calibration_grid(spec.orientation, size_mm)
    return (
        f"Treillis de {count} pastilles "
        f"({len(patch_values.calibration_lattice_adjustment_values())} valeurs en "
        f"{CALIBRATION_LATTICE_REPETITION} replicats) pour la page de calibration de "
        f"'{template_id}': au-dela des {ceiling} cellules que sa grille "
        f"({grid.columns} x {grid.rows} au pas de {grid.step_mm:.1f} mm, moins "
        f"{grid.header_rows} rangee(s) d'entete et un bloc de QR de {grid.qr_cells} "
        f"cellules de cote) peut porter a {size_mm:.1f} mm de pastille sous la "
        f"geometrie {spec.geometry_version}, dont le degagement de coin vaut "
        f"{spec.geometry.corner_clearance_mm():.0f} mm. Le plafond est derive du role, "
        "pas pose. Une geometrie qui ne peut pas porter le treillis compose ses "
        "planches d'images **sans** page de calibration et sans decalage de pagination: "
        "c'est ce qui garde un lot deja imprime identique."
    )


def known_preset_ids() -> tuple[str, ...]:
    """Return every preset id the registry can resolve."""
    return tuple(_PRESETS)


def gamut_sentinel_preset_ids() -> tuple[str, ...]:
    """Presets dont le jeu **porte** les sentinelles de gamut, derive du registre.

    Deriver et non enumerer, et le motif est un bloquant reel: l'aide de
    `--nombre-patchs` affirmait en dur « seul `patches-18-v2` porte les sentinelles de
    gamut », phrase devenue fausse le jour ou 5.16 a livre `patches-14-v3` avec ses huit
    sentinelles -- et fausse dans le sens le plus couteux, `patches-18-v2` etant refuse
    sur les quinze gabarits paysage v2 ou l'autre passe. Une phrase litterale au milieu
    d'une aide dont tout le reste est derive vieillit sans que rien ne le dise; celle-ci
    se recalcule au preset suivant.

    Le critere est celui du **verdict d'ecretage**: un preset porte les sentinelles
    quand chaque chaine de sa table est complete **dans son propre jeu de valeurs** --
    la tete in-gamut et tous ses echelons. Un preset qui reprendrait la table sans
    reprendre les pastilles ne rendrait pas le verdict calculable, et il compterait a
    tort ici. La composition des chaines est celle de `color_calibration.sentinel_chains`
    (proximite colorimetrique, jamais un suffixe de nom), appelee et non recopiee, par un
    import **local**: ce module est importe par la composition PDF, qui n'a pas a tirer
    numpy quand personne ne demande cette question.
    """
    from .color_calibration import sentinel_chains

    porteurs: list[str] = []
    for preset_id, preset in _PRESETS.items():
        table = patch_values.get_patch_values_table(preset.values_version)
        chains = sentinel_chains(table)
        if not chains:
            continue
        poses = set(preset.value_ids)
        if all(set(chaine) <= poses for chaine in chains.values()):
            porteurs.append(preset_id)
    return tuple(porteurs)


def unplaceable_couples() -> tuple[tuple[str, str, str], ...]:
    """Couples (version de geometrie, orientation, preset) refuses, copie defensive.

    Rendus pour que l'aide de la ligne de commande puisse **deriver** l'avertissement
    qui compte pour l'operateur -- quel preset a sentinelles ne se compose pas dans
    quelle orientation -- au lieu de le recopier. C'est la seconde moitie du bloquant
    B4 de la revue de 5.16: nommer les presets a sentinelles ne suffit pas si l'un des
    deux est refuse precisement dans l'orientation ou la question se pose.
    """
    return tuple(_PLACEMENT_UNPLACEABLE)


def _covered_template_ids() -> tuple[str, ...]:
    """Templates couverts par ce registre (enumeration locale, jamais derivee
    du registre 4.1 -- voir _PLACEMENT_COVERED_CARDINALS)."""
    seen: dict[str, None] = {}
    for template_id, _ in _PLACEMENTS:
        seen.setdefault(template_id, None)
    return tuple(seen)


def get_patch_preset(preset_id: str) -> PatchPreset:
    """Resolve ``preset_id`` or fail with an actionable business error."""
    try:
        return _PRESETS[preset_id]
    except KeyError:
        raise UnknownPatchPresetError(
            f"Preset de patchs inconnu: '{preset_id}'. Presets connus: "
            f"{', '.join(known_preset_ids())}. Une planche declarant un preset "
            "absent de ce registre n'est pas interpretable pour la calibration."
        ) from None


def defined_couples() -> tuple[tuple[str, str], ...]:
    """Return every (template_id, preset_id) couple with an explicit placement."""
    return tuple(_PLACEMENTS)


def reserved_zones_mm(template_id: str) -> tuple[dict, ...]:
    """Return the reserved zones (QR, text) for ``template_id``.

    Ces emprises bornent le **placement des patchs** (le test geometrique 4.7
    interdit toute pastille dedans); les emprises reelles du QR et du texte
    sont, elles, confrontees element par element aux patchs dans le test
    global de plan de page de 4.1. Un template inconnu est un echec explicite
    (revue 4.7: `.get(..., ())` rendait une liste vide silencieuse, donc un
    template mal orthographie passait pour "sans zone reservee"), et les
    dicts rendus sont des copies defensives (les zones internes etaient
    partagees entre tous les templates d'une orientation: une mutation par un
    appelant corrompait le registre pour tout le processus).
    """
    try:
        zones = _RESERVED_ZONES[template_id]
    except KeyError:
        raise UndefinedPlacementError(
            f"Aucune zone reservee pour le template '{template_id}': identifiant "
            "absent du registre de placements. Templates couverts: ceux du "
            "registre 4.1 (page_templates.known_template_ids())."
        ) from None
    return tuple(dict(zone) for zone in zones)


def _unplaceable_reason(template_id: str, preset_id: str) -> str | None:
    """Motif **chiffre** d'un couple enumere infaisable, ou ``None``.

    Les chiffres sont **calcules** a chaque appel et non recopies du commentaire de
    :data:`_PLACEMENT_UNPLACEABLE`: un chiffre imprime a l'operateur se derive, sinon
    il est faux au premier changement de geometrie -- lecon de la revue de 5.18 (M1),
    ou deux pourcentages ecrits a la main etaient faux a vingt lignes d'une table qui
    portait les valeurs justes.
    """
    if preset_id not in _PRESETS or template_id not in page_templates.known_template_ids():
        return None
    spec = page_templates.get_template(template_id)
    key = (spec.geometry_version, spec.orientation, preset_id)
    if key not in _PLACEMENT_UNPLACEABLE:
        return None
    geometry = spec.geometry
    order = _PRESET_ORDERS[preset_id]
    per_side = geometry.patch_columns_per_side[spec.orientation]
    rows = -(-len(order) // per_side) if per_side else 0
    capacity = geometry.lateral_row_capacity(spec.orientation)
    step = geometry.patch_size_mm + geometry.patch_spacing_mm
    needed_mm = (rows * geometry.patch_size_mm
                 + (rows - 1) * geometry.patch_spacing_mm) if rows else 0.0
    _page_width, page_height = page_templates.page_size_mm(spec.orientation)
    corridor_mm = (page_height - geometry.corner_clearance_mm()
                   - geometry.lateral_first_row_y_mm())
    other = [
        version for version in _PLACEMENT_COVERED_GEOMETRY_VERSIONS
        if (version, spec.orientation, preset_id) not in _PLACEMENT_UNPLACEABLE
    ]
    elsewhere = (
        f" Le couple reste composable sous la geometrie {', '.join(other)} "
        f"(makepdf --geometrie {other[0]})." if other else ""
    )
    return (
        f"Couple geometriquement infaisable, et non un placement manquant: le preset "
        f"'{preset_id}' pose {len(order)} valeur(s) par cote, soit {rows} rangee(s) de "
        f"{geometry.patch_size_mm:.1f} mm au pas de {step:.1f} mm, qui exigent "
        f"{needed_mm:.1f} mm -- quand le couloir lateral d'une page "
        f"{spec.orientation} sous la geometrie {spec.geometry_version} n'en offre que "
        f"{corridor_mm:.1f} ({capacity} rangee(s)). Motif du plafond: cette version "
        f"n'ouvre qu'{per_side} colonne(s) de temoins par cote parce que c'est cette "
        "colonne unique qui rend la bande de dessin large (`EPIC5-ARB-57`); en ajouter "
        f"une pour ce seul preset reprendrait au dessin ce que la story 5.15 lui "
        f"donne.{elsewhere}"
    )


def resolve_patch_layout(template_id: str, preset_id: str) -> tuple[PlacedPatch, ...]:
    """Resolve the full patch layout for a (template, preset) couple.

    Rend, pour chaque pastille a poser: l'identifiant de valeur, la couleur
    lue **au moment de la resolution** dans la table 4.8 declaree par le
    preset (jamais stockee ici), la position et la taille en mm. Leve
    ``UnknownPatchPresetError`` pour un preset inconnu et
    ``UndefinedPlacementError`` pour un couple sans definition explicite.
    """
    preset = get_patch_preset(preset_id)
    try:
        placements = _PLACEMENTS[(template_id, preset_id)]
    except KeyError:
        # **Le motif chiffre d'un couple enumere infaisable, porte jusqu'au refus**
        # (story 5.16; defaut releve par la revue de 5.18, M3, et verse au
        # `deferred-work.md` a l'intention de cette story). `_PLACEMENT_UNPLACEABLE`
        # n'etait lu qu'a la **construction** du registre, pour sauter le couple:
        # `resolve_patch_layout` ne le consultait jamais et le couple retombait dans
        # la branche generique « couvert mais pas pour ce preset », qui se lit comme
        # une fonctionnalite manquante alors que c'est une impossibilite geometrique
        # assumee. Le refus nomme donc maintenant sa cause, exactement comme
        # `page_templates.build_template_id` le fait pour un cardinal retire.
        unplaceable = _unplaceable_reason(template_id, preset_id)
        if unplaceable is not None:
            raise UndefinedPlacementError(unplaceable) from None
        # Message compact (revue 4.7): enumerer les 66 couples noyait le
        # couple demande; on nomme ce qui manque et ou chercher.
        covered = _covered_template_ids()
        if template_id in covered:
            detail = (
                f"le template '{template_id}' est couvert mais pas pour le "
                f"preset '{preset_id}' (presets places: "
                f"{', '.join(sorted({p for t, p in _PLACEMENTS if t == template_id}))})"
            )
        else:
            detail = (
                f"le template '{template_id}' n'est pas couvert par le registre "
                f"de placements ({len(covered)} templates couverts, voir "
                "page_templates.known_template_ids())"
            )
        raise UndefinedPlacementError(
            f"Aucun placement defini pour le couple template '{template_id}' x "
            f"preset '{preset_id}': {detail}. Un placement se definit "
            "explicitement par couple (jamais par rotation ni interpolation "
            "d'un autre template)."
        ) from None

    # EPIC4-ARB-6 applique a l'execution, pas seulement par les tests (revue
    # 4.7): la repetition declaree par le preset et le plafond de pastilles
    # physiques sont confrontes au placement reellement resolu.
    counts: dict[str, int] = {}
    for value_id, _, _ in placements:
        counts[value_id] = counts.get(value_id, 0) + 1
    expected_repetition = 1 if preset.single else preset.repetition
    wrong = {vid: n for vid, n in counts.items() if n != expected_repetition}
    if set(counts) != set(preset.value_ids) or wrong:
        raise UndefinedPlacementError(
            f"Placement incoherent pour '{template_id}' x '{preset_id}': le "
            f"preset declare repetition={expected_repetition} pour "
            f"{len(preset.value_ids)} valeur(s), le placement pose "
            f"{dict(sorted(counts.items()))}. Corriger le placement ou le preset."
        )
    # Plafond **derive du role** (story 5.16, AC 4): cette fonction ne resout que des
    # planches d'images -- une page de calibration ne declare aucun preset, son jeu
    # etant derive de son role -- donc le role est pose ici et non pris en parametre.
    # Il passe malgre tout par la table indexee par role, ce qui rend une permutation
    # des deux entrees fatale ici **et** dans `resolve_calibration_page_patches`.
    images_ceiling = patch_ceiling_for(template_id, PAGE_ROLE_IMAGES)
    if len(placements) > images_ceiling:
        raise UndefinedPlacementError(
            f"Placement de {len(placements)} pastilles pour '{template_id}' x "
            f"'{preset_id}': au-dela du maximum arbitre de "
            f"{images_ceiling} pastilles physiques par page pour une "
            f"{page_role_label(PAGE_ROLE_IMAGES)} "
            "(EPIC4-ARB-6, amende par EPIC5-ARB-14: 24 -> 36)."
        )

    # Taille lue sur la geometrie **du template** et non sur la constante du module:
    # une version resserree pose des pastilles de 6 mm, et c'est cette taille qui a
    # servi a calculer sa bande de frames. Imprimer 12 mm la ou la bande en suppose 6
    # ferait mordre la premiere colonne dans la zone de dessin -- constate en ecrivant
    # la story 5.15, sur les 11 gabarits v2 a la fois.
    # `color_calibration.sampled_square_mm` derive deja le carre echantillonne de la
    # taille reelle de la pastille, proportionnellement: aucune autre etape a changer.
    #
    # **La garde de cette lecture reste entiere pour les planches d'images** (story
    # 5.16): la taille passe desormais par la table indexee par role, et le role pose
    # ici est celui de la planche d'images. Y poser les 12 mm de la page de
    # calibration ferait mordre la premiere colonne dans la zone de dessin, defaut
    # constate a l'ecriture de 5.15 sur les 11 gabarits v2 a la fois.
    size_mm = patch_size_mm_for(template_id, PAGE_ROLE_IMAGES)
    table = patch_values.get_patch_values_table(preset.values_version)
    return tuple(
        PlacedPatch(
            value_id=value_id,
            rgb=table.get(value_id).rgb,
            x_mm=x_mm,
            y_mm=y_mm,
            size_mm=size_mm,
            # Le cadre est decide par la **valeur**, pas par le preset: c'est
            # une propriete du triplet (invisible sans encre), et le predicat
            # vit dans `patch_values`, seul point de verite des triplets.
            frame_mm=PATCH_FRAME_MM
            if patch_values.requires_printed_frame(table.get(value_id))
            else 0.0,
        )
        for value_id, x_mm, y_mm in placements
    )
