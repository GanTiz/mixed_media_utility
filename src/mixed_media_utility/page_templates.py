"""Registre des templates de page imprimable (story 4.1, EPIC4-ARB-1).

Resolveur unique ``template_id -> geometrie complete`` que le contrat 4.5
exige: un ``template_id`` inconnu au scan est un echec explicite, jamais une
geometrie devinee. Chaque couple orientation x cardinal x preset de marge est
un identifiant **versionne** distinct (suffixe ``-v1``): toute modification de
geometrie est un nouvel identifiant, jamais une redefinition silencieuse.

Vocabulaire ferme (EPIC4-ARB-1)
-------------------------------
- format: A4 seulement;
- orientation: ``portrait`` ou ``paysage``;
- frames par page: portrait {1, 2, 3, 4, 6, 8}, paysage {1, 2, 4, 6, 8},
  defaut 2;
- marge: presets discrets (``MARGIN_PRESETS_MM``), jamais un flottant libre
  (decision 4.4 / EPIC4-ARB-5: la marge vit uniquement dans le QR sous forme
  de preset de template).

Grilles calculees
-----------------
La grille de zones de chaque couple est **calculee** pour maximiser la
surface de dessin: parmi les partitions exactes colonnes x rangees du
cardinal, celle qui maximise la largeur de zone, zones 16:9 exactes (jamais
d'etirement anisotrope), centrees dans la bande de frames de l'orientation.
Le template historique ``tpl-a4-portrait-2f-v1`` (celui que ``layout.py``
implemente et que 4.3/4.6 ont eprouve) doit rendre exactement
``layout.FRAME_ZONES_MM`` -- verrouille par test.

Bandes de frames et partage de la page
--------------------------------------
- portrait: bande centrale x [35, 175], y [60, 227.5] -- les colonnes
  laterales restent aux patchs (4.7), les bandes haute/basse au QR (4.1) et
  au texte (4.2);
- paysage: bande centrale x [48, 249], y [60, 148] -- les quatre colonnes
  laterales de patchs et les bandes haute/basse jouent le meme role.
Les bornes 60 mm derivent de la geometrie des marqueurs de coin
(marge 15 + symbole 30 + silence 15).

Preset de marge (decision 4.4, consommateur story 5.3)
------------------------------------------------------
``margin_mm`` est un recadrage **interieur**: la zone imprimee reste la zone
16:9 du template, l'image utile est le plus grand rectangle 16:9 centre dans
la zone retiree de la marge sur ses quatre cotes
(:func:`frame_image_rect_mm`). Le scan (5.3) recadre la zone utile depuis le
template et le preset resolus du QR -- aucune valeur de marge brute n'est
transportee ailleurs.

Purete
------
Module strictement pur: aucune dependance a cv2 / PIL / reportlab / numpy et
**pas d'import de** ``layout`` (qui tire cv2), car ``patch_presets`` --- pur
par contrat 4.7 --- importe ce registre. Les constantes de geometrie de
marqueur sont donc des **miroirs** des constantes normatives de ``layout.py``,
verrouillees egales par test (`test_marker_geometry_constants_mirror_layout`):
c'est le meme compromis que le test geometrique 4.7, qui confronte plutot
qu'il ne copie.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

# --- Vocabulaire ferme (EPIC4-ARB-1) ---------------------------------------

ORIENTATION_PORTRAIT = "portrait"
ORIENTATION_PAYSAGE = "paysage"
ORIENTATIONS = (ORIENTATION_PORTRAIT, ORIENTATION_PAYSAGE)

PAGE_FORMATS = ("A4",)
DEFAULT_PAGE_FORMAT = "A4"

FRAMES_PER_PAGE_VOCABULARY = {
    ORIENTATION_PORTRAIT: (1, 2, 3, 4, 6, 8),
    ORIENTATION_PAYSAGE: (1, 2, 4, 6, 8),
}
DEFAULT_FRAMES_PER_PAGE = 2

#: Gain de surface **par frame** de chaque barreau du vocabulaire, sur la geometrie v2
#: livree, en pourcentage. Le regime est nomme parce qu'un pourcentage sans son regime
#: n'est pas une mesure (lecon des revues de 5.17 et de 5.18): pour chaque cardinal, la
#: surface de dessin est prise a la **meilleure orientation** puis divisee par le
#: cardinal, et le barreau `(haut, bas)` est le gain qu'on obtient en descendant de
#: `haut` a `bas`. C'est la convention que
#: `test_the_cardinal_vocabulary_is_re_evaluated_on_the_optimised_geometry` **calcule**
#: sur la geometrie a chaque execution, et cette table lui est confrontee -- elle ne peut
#: donc pas deriver de ce que la production compose.
#:
#: **Elle est en production et non dans les tests parce que le motif de refus du cardinal
#: retire la cite a l'operateur** (revue de 5.18, M1): deux de ses chiffres avaient ete
#: ecrits a la main et etaient faux (« +46 % a +75 % » pour un intervalle reel de
#: +25,0 a +111,2, et « 4 pour +61,5 % » pour un barreau a +56,5 %), a vingt lignes d'une
#: table qui portait les valeurs justes. Un chiffre imprime a l'operateur se **derive**.
RUNG_GAIN_PCT_V2 = MappingProxyType({
    (8, 6): 0.0, (6, 4): 56.5, (4, 3): 25.0, (3, 2): 111.2, (2, 1): 63.6,
})

#: Seuil de gain par frame sous lequel `EPIC5-ARB-62` declare un barreau **degenere** et
#: retire le cardinal du bas. Verdict stable de 10 a 20 % sur la v2, un test le mesure.
DEGENERATE_RUNG_THRESHOLD_PCT = 15.0


def _format_pct(value: float) -> str:
    """Pourcentage a une decimale, signe explicite et virgule decimale.

    Forme du depot pour un chiffre imprime a l'operateur (`+0,0 %`, `+56,5 %`).
    """
    return f"+{value:.1f} %".replace(".", ",")


def _retired_cardinal_reason_v2(
    orientation: str, retired: int, replacement: int, fallback: int
) -> str:
    """Motif chiffre du retrait d'un cardinal de la v2, **derive** de la table de gains.

    Trois grandeurs y sont citees, et les trois se calculent depuis
    :data:`RUNG_GAIN_PCT_V2` plutot que d'etre recopiees: le gain du barreau degenere,
    l'intervalle des **autres** barreaux, et le gain du barreau de repli. Le cout en
    papier se derive des deux cardinaux eux-memes.

    Motif de cette derivation, et il est mesure: les mutants `R01` et `R02` de la
    campagne de la couche 1 changeaient chacun l'un de ces chiffres dans le litteral du
    message et **survivaient** a toute la suite, alors que la valeur juste etait epinglee
    dans le meme fichier de tests. Un litteral ne peut pas etre tenu par un test qui ne
    le regarde pas; une derivation, si.

    **Le motif porte son orientation** (`EPIC5-ARB-64`). La phrase « 6f et 8f sont tous
    deux bornes en largeur sur deux colonnes » est vraie en portrait (2c x 3r et 2c x 4r,
    4 607 mm²/frame les deux) et **fausse en paysage** (3c x 2r a 4 389 contre 4c x 2r a
    2 413), et le conseil « utiliser 8 » y coutait **45 % de surface par frame**. Depuis
    l'amendement le 6f reste offert en paysage, donc aucun operateur paysage ne lit plus
    ce motif -- mais l'orientation est passee en argument plutot que supposee, parce que
    c'est ce qui rend le motif faux quand il l'est, plutot que faux en silence.
    """
    degenerate = RUNG_GAIN_PCT_V2[(replacement, retired)]
    others = [gain for rung, gain in RUNG_GAIN_PCT_V2.items()
              if rung != (replacement, retired)]
    paper_pct = (replacement - retired) / retired * 100.0
    return (
        f"sous la geometrie v2 optimisee et en orientation {orientation}, {retired} "
        f"frames par page rendent la MEME surface par frame que {replacement} "
        f"({_format_pct(degenerate)}) pour {paper_pct:.0f} % de papier en plus: "
        f"{retired}f et {replacement}f y sont tous deux bornes en largeur sur deux "
        "colonnes. Le cardinal est donc retire du vocabulaire de cette orientation "
        f"(EPIC5-ARB-62 amende par EPIC5-ARB-64, seuil de "
        f"{DEGENERATE_RUNG_THRESHOLD_PCT:.0f} % de gain par frame), les autres barreaux "
        f"valant de {_format_pct(min(others))} a {_format_pct(max(others))}. Utiliser "
        f"{replacement} pour la meme surface par frame sur moins de papier, ou "
        f"{fallback} pour {_format_pct(RUNG_GAIN_PCT_V2[(retired, fallback)])} par frame"
    )


#: Cardinaux **retires** du vocabulaire d'une version **dans une orientation**, avec le
#: motif chiffre qui les retire (`EPIC5-ARB-62`, amende par `EPIC5-ARB-64`; AC 13 de la
#: story 5.18). Le vocabulaire d'une version dans une orientation est donc celui de
#: :data:`FRAMES_PER_PAGE_VOCABULARY` moins ces cardinaux: retirer un cardinal n'est pas
#: neutre, les `template_id` qui le portent cessant d'etre resolvables, et une planche
#: deja imprimee sous une autre version doit rester lisible -- d'ou une table **par
#: version et par orientation** et non une modification de
#: `FRAMES_PER_PAGE_VOCABULARY`, qui reste la **seule** source du vocabulaire de base.
#:
#: **Le barreau degenere a change de place, et c'etait imprevisible avant la mesure.**
#: Sur la v2 telle que 5.15 la livrait, c'etait `6f -> 4f` (+0,6 % de surface par frame
#: pour 50 % de papier en plus). Sur la geometrie optimisee c'est `8f -> 6f`: 6f et 8f y
#: sont tous deux bornes en **largeur** sur deux colonnes, donc leur zone est identique
#: et leur surface par frame aussi. Appliquer la regle avant la passe aurait retire 4f,
#: desormais un barreau parfaitement sain, et laisse 6f, qui ne sert a rien.
#:
#: **Portee du retrait, amendee le 2026-08-12 (`EPIC5-ARB-64`).** La **detection** du
#: barreau degenere ne change pas -- elle reste evaluee sur le `max` des orientations,
#: convention ecrite dans le test qui la calcule. Ce qui change est la **portee**: un
#: cardinal detecte degenere n'est retire **que des orientations ou il l'est
#: effectivement**. Le 6 est degenere en portrait (+0,0 % contre le 8f, meme surface par
#: frame pour 33 % de papier en plus) et **sain en paysage** (+81,9 %: 3c x 2r a
#: 4 389 mm²/frame contre 4c x 2r a 2 413), donc il sort du portrait et **reste offert en
#: paysage**.
#:
#: **Pourquoi la detection n'est PAS passee par orientation, alors que c'est la
#: formulation naturelle.** Mesure a l'execution avant de l'ecrire: par orientation le
#: portrait porte **trois** barreaux degeneres (`2f -> 1f` +0,00 %, `6f -> 4f` +4,99 %,
#: `8f -> 6f` +0,00 %) et le paysage aucun. Le critere retirant le cardinal **inferieur**
#: d'un barreau degenere, il flaguerait `1`, `4` **et** `6` en portrait -- et cela
#: **cascade**: le 6f retire, le barreau au-dessus du 4f devient `8f -> 4f` a +5,0 %,
#: toujours degenere. Le vocabulaire portrait tomberait a `2, 3, 8`, ce qui est
#: exactement l'issue qu'`EPIC5-ARB-64` ecarte. Un critere qui cascade s'arbitre avec sa
#: cascade sous les yeux; les trois mesures sont versees au `deferred-work.md`.
_RETIRED_CARDINALS: Mapping[str, Mapping[str, Mapping[int, str]]] = {
    "v2": MappingProxyType({
        ORIENTATION_PORTRAIT: MappingProxyType({
            6: _retired_cardinal_reason_v2(
                ORIENTATION_PORTRAIT, retired=6, replacement=8, fallback=4),
        }),
        # Le paysage ne retire rien: son barreau `8f -> 6f` vaut +81,9 %, le meilleur
        # sous 4f. Une entree vide plutot qu'une absence, pour que la lecture de la
        # table dise « mesure, et rien a retirer » et non « pas encore regarde ».
        ORIENTATION_PAYSAGE: MappingProxyType({}),
    }),
}


def retired_cardinal_reason(
    geometry_version: str, cardinal: int | None, orientation: str | None = None
) -> str | None:
    """Motif chiffre du retrait d'un cardinal, ou ``None`` s'il n'est pas retire.

    ``orientation`` a ``None`` signifie « dans **une** orientation au moins »: le motif de
    la premiere orientation qui retire ce cardinal est rendu. C'est ce que veulent les
    appelants qui ont un cardinal sans orientation sous la main; ceux qui en ont une la
    passent, et obtiennent alors ``None`` la ou le cardinal reste offert (`EPIC5-ARB-64`).
    """
    per_orientation = _RETIRED_CARDINALS.get(geometry_version, {})
    if orientation is not None:
        return per_orientation.get(orientation, {}).get(cardinal)
    for retired in per_orientation.values():
        reason = retired.get(cardinal)
        if reason is not None:
            return reason
    return None


def frames_per_page_vocabulary(
    orientation: str, geometry_version: str | None = None
) -> tuple[int, ...]:
    """Cardinaux de frames par page qu'une version accepte dans cette orientation.

    ``None`` -- le defaut du registre. Le vocabulaire depend de la version depuis la
    story 5.18: un cardinal dont la surface par frame ne progresse pas significativement
    par rapport au cardinal superieur sort du vocabulaire de la version **et de
    l'orientation** ou la mesure le constate, et **reste resolvable** ailleurs
    (`EPIC5-ARB-64`).
    """
    version = (DEFAULT_GEOMETRY_VERSION if geometry_version is None
               else geometry_version)
    retired = _RETIRED_CARDINALS.get(version, {}).get(orientation, {})
    return tuple(cardinal for cardinal in FRAMES_PER_PAGE_VOCABULARY[orientation]
                 if cardinal not in retired)


# La **comparaison** de deux mises en page de ce vocabulaire -- la domination
# d'`EPIC11-ARB-154` -- vit dans ce module pour la meme raison que le retrait
# d'un cardinal: c'est une regle de vocabulaire de geometrie, pas une regle
# d'ecran. Elle est ecrite en fin de fichier, ou elle a sous la main les zones
# du gabarit et le rectangle 16:9 qu'elle mesure
# (:func:`bilan_de_domination`).

#: Presets discrets de marge de recadrage, en mm (jamais un flottant libre).
#: Cle = valeur CLI de ``--marge``; le fragment de template est ``m<cle>``,
#: omis pour le defaut afin que le template historique garde son identifiant.
MARGIN_PRESETS_MM = {"0": 0.0, "2": 2.0, "5": 5.0}
DEFAULT_MARGIN_PRESET = "0"

# --- Miroirs des constantes normatives de layout.py (verrouilles par test) --

A4_SHORT_SIDE_MM = 210.0
A4_LONG_SIDE_MM = 297.0
MARKER_SIZE_MM = 30.0
MARKER_MARGIN_MM = 15.0
MARKER_QUIET_ZONE_MM = 15.0
PRINTER_MARGIN_MM = 5.0

#: Geometrie des pastilles, **en miroir de `patch_presets`**, pour la meme raison que
#: les constantes de marqueur sont en miroir de `layout`: `patch_presets` importe ce
#: registre, donc ce registre ne peut pas importer `patch_presets` sans cycle. Les
#: valeurs normatives restent celles de `patch_presets`, et un test verrouille
#: l'egalite -- sans lui, la bande de frames serait calculee sur une taille de pastille
#: perimee et se decalerait silencieusement.
PATCH_SIZE_MM = 12.0
PATCH_SPACING_MM = 2.0

#: Rangees qu'une colonne laterale de pastilles peut porter au plus, **tous presets
#: confondus**: le cardinal du preset le plus riche par cote (`patches-18-v2`, 18 valeurs).
#: Miroir de `patch_presets`, verrouille par test, pour la meme raison que les deux
#: constantes ci-dessus -- `patch_presets` importe ce registre, donc ce registre ne peut
#: pas l'importer sans cycle.
#:
#: Elle sert a **une** chose, et c'est la story 5.18 qui l'introduit: savoir si la bande
#: laterale garde, sous la colonne, la hauteur libre qu'un QR de flanc demande. La
#: reservation est donc bornee par ce que le **couloir** peut porter et non par ce que les
#: presets livres y posent vraiment -- ce module ignore tout des presets -- et un test
#: confronte la reservation aux placements reels, comme pour le budget de lignes
#: techniques du pied de page.
PATCH_MAX_ROWS_PER_SIDE = 18


def page_size_mm(orientation: str) -> tuple[float, float]:
    """Largeur et hauteur de la page A4 dans cette orientation."""
    if orientation == ORIENTATION_PORTRAIT:
        return A4_SHORT_SIDE_MM, A4_LONG_SIDE_MM
    return A4_LONG_SIDE_MM, A4_SHORT_SIDE_MM


# --- Miroirs du contrat du QR (story 5.15) ---------------------------------
#
# `qr_codes` tire cv2, donc ce module pur ne peut pas l'importer: memes miroirs
# verrouilles par test que les constantes de `layout`. Ils servent a **reserver** au
# bord porteur du QR le degagement dont l'emprise imprimee a besoin, ce qu'aucune
# version de geometrie ne pouvait faire avant le resserrement (le degagement de coin
# de 60 mm de la v1 le couvrait sans qu'on ait a le nommer).

QR_PRINT_SIZE_TARGET_MM = 35.0
QR_QUIET_ZONE_MODULES = 4
QR_MIN_SCAN_DPI = 600
QR_MIN_PIXELS_PER_MODULE = 8.0

#: Cotes de symbole extremes, en modules, qu'un payload de page peut produire.
#: **Mesures**, jamais un ordre de grandeur pose a la main -- c'est precisement
#: l'erreur d'un facteur trois du 2026-08-11 matin (`module_side = 33` ecrit a la main
#: la ou la capacite se mesure sur le payload serialise).
#:
#: **Domaine recalcule par la story 5.17** (cles courtes du payload,
#: `EPIC5-ARB-60`), et non recopie: le plancher descend de 73 a **61** modules, le
#: plafond ne bouge pas.
#:
#: * le plancher est celui du payload **minimal** du schema, mesure sur le chemin de
#:   production en balayant les `template_id` du registre x les trois presets de
#:   pastilles x les deux identifiants de gamut, identifiants d'une lettre, un seul
#:   emplacement, `fps_target = 24.0`: **185 octets -> 61 modules**
#:   (`tpl-a4-paysage-1f-v1`, `patches-9-v1`, `gamut-map-lin-1`). Le temoin est
#:   **corrige** par la revue de 5.17 (majeur M7): le triple qui figurait ici,
#:   `tpl-a4-paysage-1f-m2-v1`, pese bien 188 octets mais n'est pas le minimum du
#:   balayage -- son identifiant fait 23 caracteres contre 20 pour le plus court du
#:   registre, que **dix** gabarits partagent. Ce qui compte n'est de toute facon pas le
#:   cardinal d'octets, qui depend de la longueur des identifiants du projet: c'est le
#:   cote de symbole, et il vaut **61 sur la totalite du balayage** (minimum = maximum =
#:   61). C'est cette invariance qu'un test rebalaye a chaque execution, sur les deux
#:   extremites de longueur du registre -- elles bornent le domaine, la longueur d'un
#:   `template_id` etant tout ce qui en pese;
#:
#:   **Les cardinaux du registre sont retires de ce commentaire le 2026-08-12** (revue de
#:   5.18, m12), et ce n'est pas de la paresse: ils ont change **trois fois en deux
#:   jours** -- 66 avant le retrait du cardinal 6, 60 apres, 63 depuis `EPIC5-ARB-64` --
#:   et le balayage suit (378 encodages aujourd'hui, 792 quand ce commentaire a ete
#:   ecrit). Un cardinal de registre recopie dans une prose est faux au premier
#:   changement de vocabulaire, et il ne porte rien: le test le **compte**, et c'est lui
#:   qui doit le dire.
#: * le plafond reste celui du plafond dur de payload -- 768 octets. Mesure refaite:
#:   l'encodeur rend 105 modules de 690 a 711 octets et **109 de 712 a 768**, donc le
#:   plafond est inchange a 109. Une baisse du poids des cles ne le deplace pas: elle
#:   deplace ce qu'il faut d'emplacements pour l'atteindre, pas la borne.
QR_MIN_MODULE_SIDE = 61
QR_MAX_MODULE_SIDE = 109

#: Plancher de modules du QR d'une **page de calibration**, nomme a cote de celui des
#: planches et non confondu avec lui (bloquant B3 de la revue de 5.16).
#:
#: **Mesure, et non pose**: balayage des 63 gabarits x 4 presets x 2 identifiants de gamut
#: x 4 regimes d'identifiants sur le chemin de production (`plan_page_payload`, cardinal
#: **0** et role de calibration), cotes de symbole rencontres `{57, 65, 69, 73}`, minimum
#: **57**. La page de calibration ne porte **aucun** emplacement: son payload est donc le
#: plus leger de la chaine, plus leger que le minimum sur lequel `QR_MIN_MODULE_SIDE` a ete
#: mesure (« identifiants d'une lettre, **un seul** emplacement »).
#:
#: **Pourquoi une seconde constante plutot qu'abaisser la premiere**, et le reflexe inverse
#: est faux -- la couche 2 l'a mesure. `QR_MIN_MODULE_SIDE` sert aussi a
#: `qr_edge_clearance_mm()` et `qr_flank_clearance_mm()`, qui reservent le bord porteur des
#: **planches d'images**, dont le plancher reel reste 61: l'ajout du champ de role ne peut
#: qu'alourdir leur payload. L'abaisser a 57 reprendrait 0,288 mm de bande de dessin a
#: **toutes** les planches pour un symbole qu'elles ne portent jamais -- et le gain en
#: cellules serait **nul**, `qr_cells` restant a 3 et la capacite a 141 / 135.
#: **Re-mesure le 2026-08-17 (story 5.23, AC 8bis)**: le payload du role `c` perd
#: `rush_id`, `lot_id` et `fps_target`, donc le domaine mesure a 5.16 est perime.
#: Balayage rejoue a l'identique -- 63 gabarits x 5 presets x 2 identifiants de gamut
#: x 4 regimes d'identifiants, cardinal 0, role de calibration: cotes rencontrees
#: `{53, 57}`, minimum **53** (2 520 encodages). Le plancher descend donc de 57 a 53.
#:
#: Ce n'est pas un ajustement a vue: la garde de `_calibration_page_plan` a **refuse**
#: la page des que le payload a maigri, en disant que le majorant avait bouge sans que
#: le domaine suive. C'est exactement son role, et c'est la seconde fois que ce
#: mecanisme rattrape une constante perimee -- une borne mesuree se re-mesure quand ce
#: qu'elle borne change, elle ne se recopie jamais.
#:
#: **Re-mesure le 2026-08-18 (story 5.23, entree du libelle de chaine dans le QR).** Le
#: payload du role `c` perd `project_id` -- une page appartient a une chaine, pas a un
#: projet -- et gagne `scan_chain_label`. Balayage rejoue sur le chemin de production:
#: 63 gabarits x 5 presets x 2 identifiants de gamut x 3 regimes de libelle (1 caractere,
#: l'exemple d'Egan a 39, et le maximum a 96), cardinal 0, role de calibration --
#: **1 890 encodages**. Domaine rencontre `{53, 57, 61, 65}`, minimum **53**.
#:
#: Le plancher ne bouge donc **pas**, et le fait qu'il ne bouge pas est une mesure et non
#: une chance: le payload le plus leger de la chaine est celui d'un libelle d'**un**
#: caractere -- rien n'interdit a un operateur de nommer sa chaine `a` --, et les dix
#: octets qu'il coute sont a peu pres ceux que le retrait de `project_id` rend. La
#: granularite des versions de symbole absorbe le reste.
#:
#: Le **plafond**, lui, monte: 65 modules au libelle maximal contre 57 avant la story,
#: pour 245 octets, soit 48 % du budget nominal de 512. Rien n'en depend en aval --
#: l'emprise est en U, donc un symbole plus grand est **moins** encombrant sous le regime
#: plafonne a 35 mm, et c'est le plancher qui dimensionne le bloc reserve.
QR_CALIBRATION_MIN_MODULE_SIDE = 53

#: Garde entre l'emprise du QR et l'ouverture de la bande de frames. Miroir de
#: `pdf_composition._TOP_BAND_GUARD_MM`: c'est le seul choix libre de la bande haute.
TOP_BAND_GUARD_MM = 5.0


def qr_footprint_mm(module_side: int) -> float:
    """Emprise imprimee d'un symbole de ``module_side`` modules, silence ISO compris.

    Miroir de `pdf_composition._qr_footprint_rect` et de
    `qr_codes.required_print_size_mm`: la taille imprimee est
    `max(cible, plancher de lisibilite a 8 px/module a 600 dpi)`, et le silence ISO se
    compte en modules.
    """
    floor_mm = QR_MIN_PIXELS_PER_MODULE * module_side / QR_MIN_SCAN_DPI * 25.4
    printed = max(QR_PRINT_SIZE_TARGET_MM, floor_mm)
    return printed * (module_side + 2 * QR_QUIET_ZONE_MODULES) / module_side


def qr_footprint_bound_mm() -> float:
    """Majorant de l'emprise imprimee du QR sur tout payload de page recevable.

    **L'emprise n'est pas monotone en nombre de modules, et son pire cas n'est pas le
    cardinal 8** -- contre-intuitif, et le banc de recherche s'y est trompe
    (`SIZING_CARDINAL = 8`, justifie par « c'est le payload le plus lourd qui
    commande »). Elle est en U: sous ~103 modules la taille imprimee est plafonnee a la
    cible de 35 mm et le silence ISO, compte en modules, pese relativement **plus**
    quand il y en a moins (39,59 mm a 61 modules); au-dela, la taille imprimee suit le
    plancher de lisibilite et l'emprise croit (39,62 mm a 109 modules). Le maximum est
    donc a l'une des deux extremites, jamais au milieu -- c'est la meme propriete que
    la revue 5.9-C2 avait deja trouvee sur la zone reservee.

    **Le domaine de la story 5.17 place les deux extremites a egalite pratique**, et
    c'est un fait a garder sous les yeux: 39,590 mm au plancher de 61 modules contre
    39,624 mm au plafond de 109, soit **0,034 mm d'ecart**. Le point de bascule se
    calcule -- l'emprise plafonnee vaut celle du plafond quand
    `35 (m + 8) / m = 39,624`, soit `m = 60,55` -- donc le plancher passe devant des
    qu'il descend a 57 modules (une version de symbole de moins: 39,91 mm). Le `max`
    des deux extremites n'est donc pas une precaution rhetorique ici: il est a un
    demi-module de changer de branche. Avant les cles courtes, le plancher etait a 73
    modules et l'ecart de 0,79 mm.

    Deux consequences a ne pas perdre. Reserver l'emprise **du cardinal 8** ferait
    refuser les pages 1f a 3f, dont la bande haute vaudrait exactement la reservation.
    Le chiffre de 38,3 mm que la story 5.15 donnait a ce cardinal n'est d'ailleurs pas
    reproductible, et c'est en soi la lecon: l'emprise d'un cardinal **depend du
    payload**, donc de la longueur des identifiants du projet -- 101 modules et
    37,77 mm sur le balayage de la revue, 105 modules et 38,27 mm sur celui de la
    story. Un cardinal ne dimensionne rien; le domaine de modules, si. Et ne reserver
    que le regime « cible » ferait refuser les lots aux identifiants longs -- 109
    modules, 39,62 mm -- que la v1 composait sans broncher.

    La story 5.17 en donne la demonstration la plus nette: le **meme** cardinal 8, sur
    les memes identifiants, est passe de 105 a 85 modules par un simple renommage de
    cles. Un majorant qui aurait ete ecrit « l'emprise du cardinal 8 » serait devenu
    faux sans qu'une seule ligne de geometrie ne bouge.
    """
    return max(qr_footprint_mm(QR_MIN_MODULE_SIDE), qr_footprint_mm(QR_MAX_MODULE_SIDE))


def calibration_qr_footprint_bound_mm() -> float:
    """Majorant de l'emprise du QR sur **une page de calibration**, planches comprises.

    Bloquant B3 de la revue de 5.16, et le docstring de `qr_footprint_bound_mm` avait nomme
    ce cas **d'avance**: « le plancher passe devant des qu'il descend a 57 modules (une
    version de symbole de moins: 39,91 mm) ». La story 5.16 fait descendre le plancher a 57
    -- une page sans emplacement est le payload le plus leger de la chaine -- sans deplacer
    la borne, donc l'enonce « majorant sur **tout payload de page recevable** » etait faux de
    0,288 mm sur 30 des 90 configurations livrees.

    Le majorant est le **maximum des deux domaines** et non celui du seul domaine de la page
    de calibration: la page en question est bien la page de calibration, mais un majorant qui
    descendrait sous celui des planches serait faux le jour ou leur domaine remonterait, et
    `max` coute une comparaison. C'est la meme forme que le `max` des deux extremites juste
    au-dessus, et pour la meme raison: l'emprise est en **U**, donc moins de modules donne
    une emprise plus **grande** sous le regime plafonne a 35 mm -- la page la plus legere de
    la chaine est la plus encombrante, ce qui est exactement contre-intuitif.

    Cout mesure de ce majorant sur la grille: **nul**. `qr_cells` reste a 3 cellules de cote
    (`ceil((39,912 + 2) / 14) = 3`) et la capacite reste a 141 en portrait / 135 en paysage.
    Ce que la correction achete n'est donc pas de la place, c'est une marge **demontree** la
    ou elle etait accidentelle -- le `ceil` du bloc absorbait l'ecart, et c'est precisement
    ce que cette constante existe pour eviter.
    """
    return max(
        qr_footprint_bound_mm(), qr_footprint_mm(QR_CALIBRATION_MIN_MODULE_SIDE))


# --- Miroirs du contrat typographique du pied de page (story 5.15) ---------
#
# Meme motif de miroir: `pdf_composition` importe ce registre. Ces valeurs servent a
# **deriver le degagement du bord bas**, que la v1 n'avait pas besoin de nommer non
# plus (le pied de page tenait dans les 69,5 mm que les marqueurs sterilisaient deja).

BODY_FONT_MIN_PT = 8.0

#: Lignes du bloc d'identite: les 4 lignes d'identifiants (contrat 4.2) plus la ligne
#: de date-heure que le **rendu** insere (EPIC4-ARB-8).
FOOTER_IDENTITY_LINE_COUNT = 4
FOOTER_DATE_LINE_COUNT = 1

#: Lignes reservees au pied de page technique. Ce nombre depend du **contenu**
#: (longueur des identifiants) et ne peut donc pas etre derive dans un module qui
#: ignore tout du lot: il est **reserve** ici et confronte au packing reellement produit
#: par `pdf_composition._pack_lines`, sur un lot compose, par
#: `test_the_technical_line_budget_is_confronted_to_the_real_packing`.
#:
#: **Mesure refaite a la passe de correction de 5.15, parce que celle qui etait citee
#: ici ne se reproduisait pas.** Elle annoncait « a 90 mm (v1 portrait) les six segments
#: techniques se regroupent en 3 lignes »; a l'execution, sur le chemin de production,
#: c'est **4** lignes pour les gabarits dont le `template_id` porte le fragment de
#: marge, soit 12 des 33 identifiants v1. Ce que la mesure refaite dit vraiment, et qui
#: justifie le chiffre 3:
#:
#: * cette reservation ne gouverne que les versions dont le pied de page est **derive**
#:   (v2 et suivantes). Les zones de la v1 sont des litteraux (bloc de 45 mm en
#:   portrait, 42 en paysage), et son degagement bas de 69,5 mm domine largement les
#:   54,5 mm que cette pile exige: le budget y est transparent des deux cotes;
#: * sur les versions derivees, le packing reel vaut **2 lignes a 154 mm** (v2 portrait)
#:   et **1 a 241 mm** (v2 paysage). Le pire cas gouverne est donc 2, et 3 laisse
#:   exactement **une ligne** de jeu -- un segment technique de plus la consomme, deux
#:   de plus font lever `GeometryOverflowError` sur les 18 gabarits v2 portrait a la
#:   fois. Le jeu est epingle en lignes par le test, pour que son erosion se voie;
#: * les 4 lignes de la v1 a 90 mm tiennent dans son litteral de 45 mm, mais avec
#:   **3,96 mm** de reste, soit moins d'une ligne de 4,56: la v1 n'a pas de reserve
#:   parce que son bloc est plus haut, elle en a moins parce qu'il est plus etroit.
#:
#: La garde de tenue verticale de `compose_lot_plan` refuse bruyamment ce qui
#: deborderait -- jamais un texte pose dans la bande de dessin.
#:
#: **Le regime decrit ci-dessus est mort depuis la story 5.18** (constate le 2026-08-12,
#: revue de 5.18, m2), et les trois puces sont conservees parce que leurs chiffres se
#: reproduisent -- mais elles decrivent une situation qui n'existe plus. La v2 porte
#: `identity_in_header = True`, donc `footer_technical_row_count()` rend
#: :data:`FOOTER_TECHNICAL_ROW_BUDGET` (4) et **jamais ce budget**. La seule version qui
#: le lit est la **v1**, dont les zones de pied sont des litteraux et dont le bord bas est
#: domine par les 69,5 mm du degagement de coin: cette constante ne gouverne donc plus
#: aucune geometrie produite. Elle est gardee parce qu'elle est le compte de lignes du
#: **bloc de pied historique**, que les tests de non-regression de la v1 lisent, et une
#: sonde l'a verifie: la deplacer en meme temps que `FOOTER_TECHNICAL_ROW_BUDGET` est
#: **attrapee** (`Z03`, 31 tests tombent), donc la valeur est tenue -- seul son role a
#: change. La reservation qui gouverne aujourd'hui est
#: :data:`FOOTER_TECHNICAL_ROW_BUDGET`.
FOOTER_TECHNICAL_LINE_BUDGET = 3

#: Hauteur de la bande de la consigne de scan (une ligne), litteral historique de la
#: v1 conserve: 6,0 mm pour une ligne qui en exige 4,56.
FOOTER_LINE_HEIGHT_MM = 6.0

#: Ecart entre le bloc d'identite et la ligne de consigne (litteral historique v1).
FOOTER_STACK_GAP_MM = 1.0

#: Bande sous une zone de frame ou le plan pose l'etiquette de slot. Miroir de
#: `pdf_composition._SLOT_LABEL_OFFSET_MM + _SLOT_LABEL_HEIGHT_MM`: l'etiquette est
#: **hors** de la zone, donc hors de la bande de frames, et le degagement du bas doit
#: la loger. Sans elle, l'etiquette de la derniere rangee recouvrirait le pied de page
#: -- invisible sur un rendu reduit, et un texte recouvert rend un verdict sur autre
#: chose que lui-meme.
SLOT_LABEL_STRIP_MM = 5.0


def body_line_leading_mm(font_pt: float = BODY_FONT_MIN_PT) -> float:
    """Interligne du rendu, miroir de `pdf_composition.line_leading_mm`.

    **La regle est affine, jamais proportionnelle** -- `0,42 x corps + 1,2` et non
    `corps / 8 x 4,56`. La distinction n'est visible qu'hors du corps nominal, et le
    banc de la passe de design s'y est trompe: son miroir d'interligne etait
    proportionnel, donc juste a 8 pt (ou sa garde de cablage le verifiait) et faux de
    0,90 mm par ligne a 14 pt. L'erreur allait dans le sens prudent -- il annoncait
    l'entete d'identite plus cher qu'il ne l'est -- mais c'est la cinquieme hypothese
    de banc de la meme famille, et celle-ci se serait vue en appelant la fonction de
    production a deux corps differents.
    """
    return font_pt * 0.42 + 1.2


# --- Geometrie physique versionnee -----------------------------------------

#: Les deux placements de pastilles temoins qu'une version peut composer. Le nom est
#: porte par le `TemplateSpec` pour que le placement retenu soit **lisible** plutot
#: que reconstitue: une surface egale ne dit pas quel placement l'a produite.
WITNESS_PLACEMENT_SIDES = "cotes"
WITNESS_PLACEMENT_BORDERS = "haut-bas"

#: Le placement d'une **page de calibration** (story 5.16): une grille sur la page
#: entiere entre les silences de coin, et non des pastilles rangees a cote d'une
#: bande de frames -- cette page n'en a pas. Il n'entre dans **aucune** comparaison
#: de surface de dessin: il n'y a rien a dessiner sur cette page, donc rien a
#: maximiser, donc aucun candidat a departager.
#:
#: Le mot est ``treillis`` et jamais ``mire``: dans ce depot ``mires`` designe les
#: frames de remplacement de synthese (`lots[].synthetic_frames`, `EPIC5-ARB-33`),
#: et les confondre rendrait les deux registres indiscernables a la lecture.
WITNESS_PLACEMENT_LATTICE = "treillis"

#: Espacement entre deux zones de frames d'une grille. Valeur **historique** (celle du
#: template de la story 4.1: 148.75 - 60 - 78.75 = 10), conservee comme **defaut du
#: champ** `PageGeometry.frame_grid_gap_mm` et non plus comme constante lue par le
#: calcul de grille: c'est ce defaut qui garde la v1 identique sans que sa declaration
#: soit editee (AC 1 et 2 de la story 5.18).
#:
#: **Aucune justification n'en est documentee** -- le commentaire d'origine disait
#: « celui du template historique », ce qui nomme sa provenance et non sa raison. La
#: story 5.18 a donc cherche ce que le pas protege, et la reponse est a l'AC 8 de son
#: fichier: rien de mesurable au-dela de la non-tangence de deux zones voisines.
#: Voir :data:`FRAME_GRID_GAP_V2_MM`.
FRAME_GRID_GAP_MM = 10.0

#: Pas de grille **horizontal** de la geometrie v2 (`EPIC5-ARB-61` point 5). Ce que
#: 3 mm protege, et c'est tout ce qui se documente entre deux **colonnes** (AC 8 de la
#: story 5.18):
#:
#: * la **non-tangence** de deux zones voisines. C'est la seule contrainte qui se mesure
#:   ici: deux zones tangentes sont deux contours qui se confondent en un seul trait a
#:   l'impression, donc un operateur ne sait plus ou finit une frame et ou commence la
#:   suivante. Le contour est trace **sur** la frontiere de la zone, a
#:   `setLineWidth(0.3)` -- soit **0,3 pt = 0,106 mm**, l'unite par defaut de reportlab
#:   etant le point et non le millimetre (`pdf_render`, et la ligne voisine du meme
#:   fichier fait la conversion explicitement, `* mm`). Un pas de 3 mm laisse donc
#:   **2,894 mm** de blanc entre deux traits, et deux zones tangentes forment un trait
#:   unique de 0,21 mm. Le chiffre de 2,7 mm qui figurait ici lisait `0.3` comme des
#:   millimetres (corrige le 2026-08-12, revue de 5.18, M6);
#: * une marge de coupe: **non**, aucune planche n'est decoupee -- le dispositif scanne
#:   la planche entiere et recadre par homographie (story 5.3), il n'y a pas de trait de
#:   coupe dans le depot;
#: * une tolerance de detection au scan: **non**, le recadrage d'une zone se derive du
#:   `template_id` et des quatre marqueurs de coin, jamais de la frontiere entre deux
#:   zones. Aucune etape du chemin de scan ne lit ce pas.
#:
#: Il n'y a donc **pas** de raison qui exige plus que la non-tangence entre colonnes, et
#: le pas descend a la plus petite valeur qui la rend lisible a l'oeil sur du papier.
#:
#: **3 mm plutot que 1 mm est un critere de lisibilite assume, et pas une mesure**
#: (reecrit le 2026-08-12, revue de 5.18, M6). L'argument qui figurait ici -- « la derive
#: d'echelle mesuree du tirage reel est de +1,07 %, soit 2,3 mm sur la diagonale d'une
#: page, donc un pas de 1 mm n'y survivrait pas » -- ne peut pas porter la conclusion, et
#: pour deux raisons arithmetiques:
#:
#: * le chiffre ne correspond pas a la grandeur nommee: +1,07 % de la diagonale d'une A4
#:   (363,743 mm) vaut **3,892 mm**, et 2,3 mm est +1,07 % du **petit cote** (210 mm);
#: * surtout, **une derive d'echelle n'erode pas un pas**: c'est une homothetie, donc
#:   elle s'applique au pas aussi (`1 mm -> 1,0107 mm`, `3 mm -> 3,0321 mm`). Un pas de
#:   1 mm y survit exactement aussi bien qu'un pas de 3 mm -- il grandit. Ce qui
#:   pourrait manger un pas de 1 mm est une erreur de **placement**, un etalement
#:   d'encre ou une imprecision de registration, et le depot a justement isole l'echelle
#:   de l'erreur de placement (voir le docstring de :data:`GEOMETRY_V2`: la derive est
#:   mesuree sur le cote de chaque marqueur, jamais sur l'ecart entre marqueurs
#:   eloignes).
#:
#: Ce qui tient donc le choix de 3 mm est un **verdict a l'oeil**, ecrit comme tel:
#: 2,894 mm de blanc entre deux contours de 0,106 mm se voient sur du papier, 0,894 mm
#: se voient moins. Descendre a 1 mm demande une mesure d'erreur de placement ou
#: d'etalement d'encre sur un tirage reel -- elle n'existe pas dans le depot, et c'est
#: la seule barriere honnete contre 1 mm.
#:
#: **Entre deux RANGEES la contrainte est autre, et elle se mesure**: voir
#: :meth:`PageGeometry.frame_grid_row_gap_mm`. Le pas vertical n'est donc pas ce champ.
FRAME_GRID_GAP_V2_MM = 3.0

#: Les quatre bords qu'une page peut donner au QR, dans l'ordre qui **departage les
#: egalites de surface a hauteur de bande egale** (AC 3 de la story 5.18).
#:
#: L'ordre n'est pas decoratif: 6f et 8f sont bornes en **largeur**, donc leur surface
#: est rigoureusement identique au bord haut et au bord bas, et le banc de recherche a
#: rapporte `haut` pour 6f par simple ordre de boucle. Une egalite se departage par une
#: regle ecrite, jamais par l'ordre d'une iteration.
QR_EDGE_BOTTOM = "bas"
QR_EDGE_TOP = "haut"
QR_EDGE_LEFT = "gauche"
QR_EDGE_RIGHT = "droit"
QR_EDGES = (QR_EDGE_BOTTOM, QR_EDGE_TOP, QR_EDGE_LEFT, QR_EDGE_RIGHT)

#: Corps de police et nombre de lignes de l'entete d'identite (`EPIC5-ARB-63`, AC 4 de
#: la story 5.18): le nom du lot sur la premiere ligne, la pagination et la cadence sur
#: la seconde. **Mesure: cela ne coute rien** -- le bord haut n'est jamais borne par
#: l'entete mais par le degagement de coin (28 mm en v2) ou par le QR (49,6 mm), et une
#: pile de deux lignes a 14 pt n'en exige que 14,16. La tension que l'arbitrage posait
#: -- police plus grosse contre place perdue -- n'existe pas dans ce domaine.
HEADER_IDENTITY_FONT_PT = 14.0
HEADER_IDENTITY_LINE_COUNT = 2

#: Lignes d'identite que le **pied** conserve quand l'identite passe en entete: les deux
#: identifiants canoniques qu'`EPIC5-ARB-63` ne nomme pas (`project_id`, `rush_id`) et
#: que le mecanisme de secours 4.6 exige **verbatim** sur la planche -- egalite a
#: l'octet avec le payload QR et les noms de fichiers. Ils ne peuvent donc ni etre
#: tronques, ni partir dans une colonne technique de 55 mm: un identifiant canonique
#: atteint 48 caracteres, soit 81 mm au plancher de 8 pt.
FOOTER_RESIDUAL_IDENTITY_LINE_COUNT = 2

#: Colonnes sur lesquelles le pied technique se replie (`EPIC5-ARB-63`).
#:
#: **Mesure de ce que ce repli achete: exactement rien, et c'est un chiffre a garder.**
#: Le nombre de rangees reservees est le meme a une colonne et a deux, parce que la
#: largeur d'une colonne halve double le nombre de lignes que le packing produit --
#: 3 lignes a 112 mm contre 6 a 55 mm, soit 4 rangees dans les deux cas, date fondue
#: comprise. Le banc de la passe annoncait +1,2 % pour ce repli; il divisait un budget
#: de 3 lignes **fixe** par le nombre de colonnes, alors que le packing depend de la
#: largeur. Les deux colonnes sont donc gardees parce qu'Egan les demande et qu'elles
#: ne coutent rien, jamais parce qu'elles rendent de la surface.
FOOTER_TECHNICAL_COLUMNS = 2

#: Rangees reservees au pied technique quand l'identite est en entete, **date de rendu
#: comprise** (`EPIC4-ARB-8`: la date devient une ligne technique et non plus une ligne
#: a elle seule). Reservation, comme `FOOTER_TECHNICAL_LINE_BUDGET`, et confrontee au
#: packing reel par test: le pire cas mesure est le pied **retreci par le QR du bord
#: bas** (112,4 mm en portrait, donc deux colonnes de 55,2), ou les six segments
#: techniques se regroupent en 6 lignes qui, avec la date, remplissent 4 rangees.
FOOTER_TECHNICAL_ROW_BUDGET = 4

#: Ecart horizontal entre deux blocs de texte voisins, miroir de
#: `pdf_composition._TEXT_GAP_MM`. Il separe le pied de page de l'emprise du QR quand
#: celui-ci prend le bord bas, et les deux colonnes techniques l'une de l'autre.
TEXT_GAP_MM = 2.0


# ---------------------------------------------------------------------------
# La page de calibration (story 5.16, AC 3 et 4)
# ---------------------------------------------------------------------------
#
# Ce qu'elle est: la **premiere page de chaque lot** (`page_index = 0`), qui porte
# le treillis de mesure et ses quatre coins, et **aucune frame**. Sa mise en page
# se derive du couple `(template_id, role de page)` -- `template_id` ne decrivant
# plus que la geometrie des pages d'**images** du lot (voir `page_roles`).
#
# Ce qui la rend geometriquement differente de tout le reste du depot: elle n'a
# **pas de bande de frames**. Aucune bande ne dispute donc la surface aux
# pastilles, et celles-ci occupent la page entiere entre les silences des
# marqueurs de coin -- en une grille, pas en colonnes laterales.

#: Lignes d'identite que la page de calibration porte en entete, et leur corps.
#:
#: **Le corps est celui du texte courant et non `HEADER_IDENTITY_FONT_PT`, et le
#: choix est mesure.** Une pile de deux lignes a 14 pt exige 14,16 mm, donc deux
#: rangees de grille en paysage, donc **16 cellules** de moins -- la capacite
#: tombe a 119 quand le treillis en demande 130. A 8 pt la pile exige 9,12 mm,
#: tient dans une seule rangee, et la capacite reste a 135. C'est le seul endroit
#: du depot ou la tension « police plus grosse contre place perdue » que
#: `EPIC5-ARB-63` posait existe reellement, parce que c'est le seul ou la place
#: perdue est reprise a des pastilles et non a du blanc.
#: **Il depend de l'orientation depuis la story 5.23, et ce n'est pas un raffinement:
#: c'est la seule facon de porter les cinq mentions d'Egan sans perdre le paysage.**
#:
#: La page porte desormais cinq mentions imprimees -- projet, chaine de scan, « Page de
#: calibration », la consigne d'usage, et un commentaire libre facultatif -- la ou elle
#: n'en portait que deux. Elles ne tiennent pas en deux lignes: la seule consigne
#: d'usage fait 108 caracteres pour une bande de 86 en portrait.
#:
#: Le budget de chaque orientation est **derive de ce que sa grille peut financer**, et
#: un test le rejoue (`test_calibration_page_geometry`). Une rangee d'entete se paie en
#: cellules reprises au treillis, qui en exige 130:
#:
#:     portrait   10 x 16 = 160 cellules, moins 9 de QR: 2 rangees -> 131 (tient),
#:                3 rangees -> 121 (ne tient plus). Bande utile 27 mm -> **5 lignes**.
#:     paysage    16 x 10 = 160 cellules, moins 9 de QR: 1 rangee -> 135 (tient),
#:                2 rangees -> 119 (ne tient plus). Bande utile 12 mm -> **2 lignes**.
#:
#: Un budget commun aux deux orientations aurait donc coute l'une ou l'autre: a 2
#: lignes le portrait -- l'orientation **par defaut** -- ne peut pas imprimer les
#: mentions, et a 5 lignes le paysage ne peut plus porter son treillis du tout. Le
#: paysage garde ainsi exactement la geometrie qu'il avait avant la story; il refuse en
#: revanche, **explicitement et chiffre**, un jeu de mentions qui deborde ses 2 lignes
#: (voir `pdf_composition._calibration_header_lines`). Un refus chiffre est ce que ce
#: depot preferera toujours a une mention tronquee sur une feuille imprimee, qui est
#: indetectable apres coup.
CALIBRATION_HEADER_LINE_COUNT: Mapping[str, int] = MappingProxyType({
    ORIENTATION_PORTRAIT: 5,
    ORIENTATION_PAYSAGE: 2,
})


def calibration_header_line_count(orientation: str) -> int:
    """Lignes d'entete que la page de calibration reserve sous ``orientation``.

    Point de lecture unique de :data:`CALIBRATION_HEADER_LINE_COUNT`: la grille le
    consomme pour dimensionner sa bande, la composition pour refuser un texte qui
    deborde. Deux lectures directes du mapping divergeraient au premier ajout
    d'orientation, et le symptome serait une bande dimensionnee pour un nombre de
    lignes et remplie d'un autre.
    """
    try:
        return CALIBRATION_HEADER_LINE_COUNT[orientation]
    except KeyError:
        raise UnknownTemplateError(
            f"Orientation hors vocabulaire: {orientation!r}. Orientations connues: "
            f"{', '.join(sorted(CALIBRATION_HEADER_LINE_COUNT))}."
        ) from None

#: Pas de la grille de treillis: le meme que celui d'une colonne laterale, taille
#: de pastille plus espacement inter-pastilles. Il n'y a pas de second espacement
#: a inventer -- le contrat d'adjacence d'`EPIC5-ARB-17(a)` porte sur le carre
#: echantillonne, pas sur le voisinage, et il est le meme dans les deux sens.


def _cells_for_mm(needed_mm: float, step_mm: float, spacing_mm: float) -> int:
    """Cellules de grille qu'une emprise de ``needed_mm`` exige, au minimum.

    La bande utile de ``n`` cellules vaut ``n * pas - espacement`` et non ``n *
    pas``: la derniere cellule cede son espacement a la pastille suivante, qui
    doit rester a distance. Une division par le pas seul aurait rendu une cellule
    de moins sur ``(k * pas - espacement, k * pas]``, c'est-a-dire juste
    **au-dessous de chaque multiple ou exactement dessus**, jamais juste
    au-dessus -- et le symptome serait un symbole de QR imprime par-dessus la
    premiere pastille du treillis, ou un texte d'entete de 14 mm dans une bande
    de 12.

    **L'intervalle est mesure, et il etait enonce a l'envers** (mineur m3 de la
    couche 1 de la revue de 5.16: « juste au-dessus de chaque multiple »). A
    ``pas = 14`` et ``espacement = 2``, les deux formules divergent sur
    ``]12, 14]`` puis ``]26, 28]``: ``needed = 14,0`` exige **2** cellules ici et
    n'en aurait rendu qu'**une** par la division seule, tandis que
    ``needed = 14,1`` en rend deux des deux facons. La fonction etait juste; c'est
    sa justification qui designait le mauvais cote du multiple, donc qui ne se
    verifiait pas telle quelle -- et l'exemple du texte de 14 mm dans une bande de
    12 est precisement le bord ``k = 1`` de cet intervalle.
    """
    if step_mm <= 0:
        raise UnknownTemplateError(
            f"Pas de grille invalide: {step_mm!r}. Un pas strictement positif est "
            "attendu."
        )
    if needed_mm <= 0:
        return 0
    return math.ceil((needed_mm + spacing_mm) / step_mm)


@dataclass(frozen=True)
class CalibrationGrid:
    """Grille de pastilles d'une page de calibration, **derivee** de la geometrie.

    Trois furnitures seulement sur cette page, et chacune se paie en cellules
    plutot qu'en millimetres, parce que c'est la grille qui borne tout le reste:

    * les **quatre marqueurs de coin**, qui bornent la grille elle-meme: son
      origine est le degagement de coin, dans les deux directions;
    * l'**entete d'identite**, qui occupe les :attr:`header_rows` premieres
      rangees sur toute la largeur;
    * le **QR**, qui occupe un bloc carre de :attr:`qr_cells` cellules de cote,
      au coin haut-gauche de ce qui reste.

    Il n'y a **pas de pied de page**, et c'est une omission mesuree et non un
    oubli: une rangee de pied coute 16 cellules en paysage, donc ferait tomber la
    capacite a 119 quand le treillis en demande 130. La consigne de scan et le
    pied technique d'une planche d'images n'y sont donc pas; le QR porte
    l'integralite de ce qui est necessaire a la relecture, et l'entete porte ce
    qu'un operateur lit sur une pile.

    Les deux comptes de furniture sont derives de ce que leur contenu **exige**,
    jamais poses: une rangee de moins ferait imprimer un texte de 14 mm dans une
    bande de 12, une cellule de QR de moins ferait mordre le symbole sur la
    premiere pastille.
    """

    orientation: str
    patch_size_mm: float
    spacing_mm: float
    origin_x_mm: float
    origin_y_mm: float
    columns: int
    rows: int
    header_rows: int
    qr_cells: int

    @property
    def step_mm(self) -> float:
        """Pas de la grille, dans les deux directions."""
        return self.patch_size_mm + self.spacing_mm

    @property
    def capacity(self) -> int:
        """Pastilles que la page peut porter, **arithmetiquement**.

        Formule et non comptage: c'est la grandeur qu'un test confronte au
        cardinal du treillis, et elle doit se lire. Le comptage existe a cote
        (:meth:`usable_cells_mm`), et un test verifie que les deux coincident dans
        les deux orientations -- une redondance voulue: si la formule et
        l'enumeration divergent, l'une des deux place des pastilles la ou l'autre
        croit qu'il n'y en a pas.
        """
        return (self.columns * self.rows
                - self.columns * self.header_rows
                - self.qr_cells * self.qr_cells)

    def header_zone_mm(self) -> tuple[float, float, float, float]:
        """Emprise de l'entete d'identite: les premieres rangees, pleine largeur."""
        return (
            self.origin_x_mm,
            self.origin_y_mm,
            self.columns * self.step_mm - self.spacing_mm,
            self.header_rows * self.step_mm - self.spacing_mm,
        )

    def qr_zone_mm(self) -> tuple[float, float, float, float]:
        """Emprise reservee au QR: un bloc carre, sous l'entete, au bord gauche."""
        side = self.qr_cells * self.step_mm - self.spacing_mm
        return (
            self.origin_x_mm,
            self.origin_y_mm + self.header_rows * self.step_mm,
            side,
            side,
        )

    def usable_cells_mm(self) -> tuple[tuple[float, float], ...]:
        """Coins haut-gauche des cellules libres, en **ordre de lecture**.

        Ordre de lecture -- rangee par rangee, de gauche a droite -- et non un
        ordre de commodite: le treillis est balaye R puis G puis B, donc deux
        pastilles voisines dans la grille sont voisines dans le cube, et une
        rampe se lit a l'oeil sur la planche imprimee. C'est l'idiome des gammes
        de controle industrielles, deja retenu pour `_ORDER_18`.
        """
        cells: list[tuple[float, float]] = []
        for row in range(self.header_rows, self.rows):
            for column in range(self.columns):
                if column < self.qr_cells and row < self.header_rows + self.qr_cells:
                    continue
                cells.append((
                    self.origin_x_mm + column * self.step_mm,
                    self.origin_y_mm + row * self.step_mm,
                ))
        return tuple(cells)


@dataclass(frozen=True)
class PageGeometry:
    """Constituants physiques **figes** d'une version de geometrie de page.

    Pourquoi une classe et non les constantes du module (2026-08-11)
    ---------------------------------------------------------------
    L'en-tete de ce module promet depuis la story 4.1 que ``toute modification de
    geometrie est un nouvel identifiant, jamais une redefinition silencieuse``. Le
    suffixe ``-v1`` etait pourtant une chaine ecrite en dur dans
    :func:`build_template_id`, tandis que la geometrie qu'un ``template_id`` resout
    se lisait dans les constantes **globales** du module. La promesse ne tenait donc
    a rien: reduire `MARKER_SIZE_MM` -- l'objet meme du chantier d'optimisation de la
    page -- redefinissait `v1` pour les 33 gabarits a la fois, y compris pour une
    planche deja imprimee et pas encore scannee. Cote scan, le redressement aurait
    cherche les marqueurs de coin la ou la **nouvelle** geometrie les place: pas un
    recadrage approximatif, une homographie fausse, sans qu'aucune etape n'echoue.

    La derivation de la bande de frames livree la veille rendait ce risque
    **actif**: avant elle, changer la taille des marqueurs ne deplacait rien (c'etait
    le defaut); depuis, cela deplace les zones de frames de tous les gabarits.

    Chaque version est donc un jeu de constituants fige a l'import, porte par le
    ``template_id`` (suffixe ``-v<n>``) et resolu avec lui. Une geometrie resserree
    est une **version supplementaire**: `v1` reste lisible pour toujours, ce qui est
    la seule facon de pouvoir scanner une planche imprimee avant le changement.

    Les trois derniers champs restent des **valeurs historiques sans formule**: les
    expliquer ou les unifier est une decision produit, pas un refactoring.
    """

    version: str
    marker_size_mm: float
    marker_margin_mm: float
    marker_quiet_zone_mm: float
    printer_margin_mm: float
    patch_size_mm: float
    patch_spacing_mm: float
    #: Colonnes de pastilles par cote. Historique: 2 en portrait, 3 en paysage pour
    #: le meme preset, sans que rien dans le depot ne justifie la difference.
    patch_columns_per_side: Mapping[str, int]
    #: Espace entre le bloc de pastilles et le bord de la bande de frames.
    patch_to_band_gap_mm: Mapping[str, float]
    #: Supplement de degagement en bas de page, au-dela du degagement de coin, la ou
    #: le degagement du haut vaut exactement le degagement de coin.
    bottom_extra_clearance_mm: Mapping[str, float]
    #: Nombre de pastilles temoins a loger si elles passent en rangees haut/bas.
    #:
    #: ``None`` -- la v1 -- signifie « aux colonnes laterales **sans exception** »:
    #: la bande ne depend alors d'aucun cardinal, et c'est ce qui garde la v1
    #: identique au dixieme de millimetre.
    #:
    #: Une valeur signifie que les **deux** placements sont composes et que celui qui
    #: rend la plus grande surface de dessin est retenu, cardinal par cardinal
    #: (`EPIC5-ARB-55`). Choisir depuis la seule dimension limitante est une
    #: heuristique **mesuree fausse**: elle a fait chuter un cardinal de +122 % a
    #: +67 %. La dimension limitante dit ce qui borne la zone *avant* le deplacement;
    #: elle ne dit rien du cout du deplacement lui-meme.
    border_witness_count: int | None = None

    # --- Champs ajoutes par la passe de design (story 5.18) -----------------
    #
    # Les trois ont un **defaut egal au comportement historique**, et c'est ce qui rend
    # l'AC 1 verifiable: la **declaration** de la v1 plus bas n'est pas editee d'une
    # ligne -- un test l'epingle caractere par caractere -- donc la v1 ne peut pas bouger
    # par inadvertance en ajoutant un champ. Une valeur de defaut qui ne serait pas la
    # valeur historique serait, elle, une redefinition silencieuse de la v1: c'est ce que
    # la famille `J` de la campagne de mutation eprouve.

    #: Espacement entre deux zones de frames de la grille. **Etait une constante de
    #: module**, donc la meme pour toutes les versions: la v1 ne pouvait pas garder
    #: 10 mm si la v2 en voulait 3 (AC 2 de la story 5.18).
    frame_grid_gap_mm: float = FRAME_GRID_GAP_MM

    #: Bord porteur du QR, ou ``None`` si les **quatre** bords sont composes et le plus
    #: dessinant retenu, cardinal par cardinal (AC 3 de la story 5.18).
    #:
    #: Une valeur -- la v1 -- signifie « ce bord, sans exception »: la v1 garde son QR
    #: au bord haut, et rien de la comparaison ne peut la deplacer. C'est necessaire et
    #: pas seulement prudent: sous la v1 le degagement de coin (60 mm) domine l'exigence
    #: du QR (49,6), donc le haut et le bas y rendent la **meme** surface -- une
    #: comparaison y trancherait par sa regle de departage et deplacerait le QR d'une
    #: planche deja imprimee.
    qr_bearing_edge: str | None = QR_EDGE_TOP

    #: ``True`` -- l'identite du lot est en **entete** a `HEADER_IDENTITY_FONT_PT`, et
    #: le pied ne porte plus que les deux identifiants residuels et la technique sur
    #: deux colonnes (`EPIC5-ARB-63`). ``False`` -- disposition historique: quatre
    #: lignes d'identite, une ligne de date, la technique sur une colonne.
    identity_in_header: bool = False

    def corner_clearance_mm(self) -> float:
        """Bord de page -> limite interieure du silence d'un marqueur de coin."""
        return self.marker_margin_mm + self.marker_size_mm + self.marker_quiet_zone_mm

    def qr_edge_clearance_mm(self) -> float:
        """Degagement qu'exige le bord **porteur du QR**, marge d'encre comprise.

        Les quatre bords ne descendent pas ensemble: trois suivent les marqueurs, le
        quatrieme suit le QR. La bande haute est bornee en haut par la marge
        d'impression et en bas par l'ouverture de la bande de frames, donc resserrer
        le degagement de coin ne l'ouvre pas -- il l'**ecrase**
        (`analyse-2026-08-11-qr-et-gabarits-resserres.md`).

        En v1 le degagement de coin (60 mm) domine ce plancher (**49,624 mm**), donc le
        `max` de :meth:`frame_band_mm` y est transparent -- un test le verrouille. Le
        chiffre de 48,8 mm qui figurait ici etait celui d'avant le recalcul du domaine de
        modules par la story 5.17 (majorant d'emprise 38,8 -> 39,624); corrige le
        2026-08-12, revue de 5.18, m1. La conclusion, elle, ne bouge pas.
        """
        return self.printer_margin_mm + qr_footprint_bound_mm() + TOP_BAND_GUARD_MM

    def frame_grid_row_gap_mm(self) -> float:
        """Pas de grille **vertical**: il porte l'etiquette d'emplacement de la rangee.

        **Derive, jamais choisi, et c'est une mesure faite a l'execution.** Le plan pose
        sous chaque zone une etiquette `rush + s<NN> + timecode` **hors** de la zone, a
        `_SLOT_LABEL_OFFSET_MM` de son bord bas et sur `_SLOT_LABEL_HEIGHT_MM` de haut --
        soit exactement `SLOT_LABEL_STRIP_MM`. Le degagement du bord bas loge celle de la
        derniere rangee; entre deux rangees, il n'y a que le pas de grille pour la loger.

        Consequence, trouvee en faisant tomber le test global de non-chevauchement de la
        story 5.15 sur **66 combinaisons** apres avoir pose le pas a 3 mm: une etiquette
        de 5 mm dans un pas de 3 mm atterrit **dans la zone de dessin de la rangee
        suivante**. Le pas vertical vaut donc au moins la bande d'etiquette, et il la
        vaut par derivation de la constante qui la nomme -- un litteral de 5 mm ici
        cesserait d'etre juste au premier changement de la typographie de l'etiquette.

        A 5 mm l'etiquette est **tangente** a la zone suivante, et c'est voulu: le rendu
        pose la ligne de base a `hauteur - 0,5 mm` du haut de la bande, donc l'encre
        s'arrete 0,5 mm au-dessus de la frontiere. Prendre `strip + 1` couterait de
        **1,56 % a 3,80 %** de surface sur les gabarits que cela touche, pour un blanc que
        le contour de la zone occupe deja -- mesure a 6 mm sur la production seule:
        portrait 3f -2,79 %, portrait 4f -3,80 %, portrait 8f -2,20 %, paysage 4f -1,56 %,
        et **0,000 %** sur les six autres. (Le chiffre unique de 1,4 % qui figurait ici ne
        correspondait a aucun gabarit, et le pire cas vaut 2,7 fois cette annonce; corrige
        le 2026-08-12, revue de 5.18, m9. La conclusion -- coller le pas a la bande
        d'etiquette -- n'en est que renforcee.)

        A noter, et c'est le genre de chose qu'un chiffre unique cache: un cardinal a
        plusieurs rangees peut etre **insensible** au pas vertical si sa bande est bornee
        en **largeur** -- portrait 2f (1 colonne x 2 rangees) et paysage 6f et 8f
        (2 rangees) ne paient rien. Le pas vertical ne coute que la ou la hauteur borne la
        grille.

        La v1 est transparente a cette derivation: son pas de 10 mm domine largement les
        5 mm de la bande, donc `max` y rend 10 -- et un test le verrouille.
        """
        return max(self.frame_grid_gap_mm, SLOT_LABEL_STRIP_MM)

    def header_identity_clearance_mm(self) -> float:
        """Degagement qu'exige l'entete d'identite au bord haut, hors QR.

        L'entete ne s'**ajoute** pas au QR: quand le QR prend le bord haut, son emprise
        (39,6 mm) domine largement l'entete et celui-ci se pose **a cote**, dans la meme
        bande. C'est seulement quand le QR part ailleurs que l'entete devient ce qui
        borne le bord haut -- et il ne le borne pas non plus, le degagement de coin
        (28 mm en v2) etant plus grand que les 24,16 mm de la pile.

        La pile se lit du bord du papier vers le dessin: marge d'encre, les lignes
        d'entete a leur interligne, garde de bande. La garde est **celle de la bande
        haute** (`TOP_BAND_GUARD_MM`) et non l'ecart de pile du pied: c'est cette meme
        garde que :func:`header_band_mm` retire pour poser le bloc, donc en prendre une
        autre ici rendrait un degagement qui ne loge pas le bloc qu'il annonce.
        """
        return (self.printer_margin_mm
                + HEADER_IDENTITY_LINE_COUNT
                * body_line_leading_mm(HEADER_IDENTITY_FONT_PT)
                + TOP_BAND_GUARD_MM)

    def footer_identity_line_count(self) -> int:
        """Lignes d'identite que le pied de page porte sous cette disposition."""
        if self.identity_in_header:
            return FOOTER_RESIDUAL_IDENTITY_LINE_COUNT
        return FOOTER_IDENTITY_LINE_COUNT + FOOTER_DATE_LINE_COUNT

    def footer_technical_row_count(self) -> int:
        """Rangees reservees au pied technique sous cette disposition."""
        if self.identity_in_header:
            return FOOTER_TECHNICAL_ROW_BUDGET
        return FOOTER_TECHNICAL_LINE_BUDGET

    def footer_block_height_mm(self) -> float:
        """Hauteur du bloc de pied de page: ce que le **texte** exige, a son plancher.

        Derive du nombre de lignes et de l'interligne du rendu, jamais d'une constante
        additive posee sur le degagement de coin: sous la v2 le degagement de coin
        (28 mm) est plus petit que le bloc, donc un litteral placerait le pied de page
        dans la bande de frames.

        Le nombre de lignes depend de la **disposition** depuis la story 5.18: huit en
        disposition historique (4 identite + 1 date + 3 technique), six quand l'identite
        passe en entete (2 identifiants residuels + 4 rangees techniques, date fondue).
        """
        lines = self.footer_identity_line_count() + self.footer_technical_row_count()
        return lines * body_line_leading_mm()

    def bottom_text_clearance_mm(self) -> float:
        """Degagement qu'exige le bord bas pour porter le pied de page.

        Meme principe qu'au bord du QR (`EPIC5-ARB-56` point 1): un `max` avec le
        degagement de coin, pas une somme. En v1 les 69,5 mm du bord bas couvrent
        largement les 54,5 mm exiges ici, donc le `max` y est transparent lui aussi.

        La pile se lit du bord du papier vers le dessin: marge d'encre, bande de la
        consigne de scan, ecart, bloc d'identite, ecart, bande des etiquettes de slot.
        Le second ecart n'est pas decoratif: sans lui la bande de frames et le bloc
        d'identite seraient **tangents** des que la hauteur borne la grille, et une
        tangence entre deux nombres issus de divisions differentes ressort en
        chevauchement de 1e-14 mm -- defaut deja paye sur la colonne de pastilles
        paysage a x = 249,00000000000003.
        """
        return (self.printer_margin_mm + FOOTER_LINE_HEIGHT_MM + FOOTER_STACK_GAP_MM
                + self.footer_block_height_mm() + FOOTER_STACK_GAP_MM
                + SLOT_LABEL_STRIP_MM)

    def patch_block_end_mm(self, orientation: str) -> float:
        """Abscisse ou finit le bloc de pastilles d'un cote, bord de page inclus."""
        columns = self.patch_columns_per_side[orientation]
        return (self.printer_margin_mm + columns * self.patch_size_mm
                + (columns - 1) * self.patch_spacing_mm)

    def qr_edge_candidates(self) -> tuple[str, ...]:
        """Les bords porteurs du QR que cette version compose.

        Un seul -- celui que la version fige -- ou les quatre, dans l'ordre qui
        departage les egalites (`QR_EDGES`).
        """
        if self.qr_bearing_edge is None:
            return QR_EDGES
        return (self.qr_bearing_edge,)

    def lateral_first_row_y_mm(self) -> float:
        """Ordonnee de la premiere rangee d'une colonne laterale de pastilles.

        Les colonnes laterales sont dans la meme bande d'abscisses que les marqueurs de
        coin, donc elles ne peuvent commencer qu'apres leur zone de silence; un
        espacement de pastille les en separe -- exactement ce que rend la v1 (60 + 2 =
        62 mm). `patch_presets._derived_first_row_y_mm` delegue ici: une seconde recette
        divergerait de celle-ci au premier changement, et c'est **cette** ordonnee qui
        decide si un QR de flanc a de la place sous la colonne.
        """
        return self.corner_clearance_mm() + self.patch_spacing_mm

    def lateral_row_capacity(self, orientation: str) -> int:
        """Rangees qu'une colonne laterale peut porter entre les deux silences de coin."""
        _page_width, page_height = page_size_mm(orientation)
        available = (page_height - self.corner_clearance_mm()
                     - self.lateral_first_row_y_mm())
        step = self.patch_size_mm + self.patch_spacing_mm
        if available < self.patch_size_mm:
            return 0
        return int((available + self.patch_spacing_mm) // step)

    def calibration_grid(
        self, orientation: str, patch_size_mm: float
    ) -> CalibrationGrid:
        """Grille de treillis d'une page de calibration sous cette geometrie.

        ``patch_size_mm`` est **exige** et non pris sur :attr:`patch_size_mm`: la
        taille d'une pastille de page de calibration est derivee du **role de
        page** et non de la geometrie (12 mm contre les 6 mm d'une planche
        d'images sous la v2), et sa valeur normative vit dans `patch_presets`,
        seul point de verite des tailles de pastille. Un defaut ici aurait pose
        6 mm sur la page dont depend toute la correction du lot -- exactement la
        faute symetrique de celle constatee en ecrivant la story 5.15, ou un pas
        par defaut avait pose les pastilles de la v2 au pas de la v1.

        Les quatre comptes rendus sont **derives**, jamais poses:

        * les colonnes et les rangees, de la place entre les deux silences de coin
          et du pas de grille;
        * les rangees d'entete, de ce que la pile de texte exige (`ceil` sur le
          pas, espacement inter-pastilles compris: la bande utile d'une rangee est
          `pas - espacement`, pas le pas entier);
        * les cellules de QR, de l'emprise **majorante** du symbole sur cette page
          (:func:`calibration_qr_footprint_bound_mm`) et de la meme regle. Le majorant
          et non l'emprise reelle: celle-ci depend du payload, et une reservation qui
          rapetisse avec la charge utile serait une reservation qu'un lot plus
          bavard fait mordre sur une pastille.

          **Le majorant est celui de la page de calibration et non celui des planches**
          (bloquant B3 de la revue): son payload ne porte aucun emplacement, donc il
          descend a 57 modules, et l'emprise etant en U c'est **la page la plus legere
          qui est la plus encombrante** -- 39,912 mm contre les 39,624 des planches. Le
          cout en cellules est nul, ce qui rend la marge demontree au lieu
          d'accidentelle.
        """
        page_width, page_height = page_size_mm(orientation)
        clearance = self.corner_clearance_mm()
        step = patch_size_mm + self.patch_spacing_mm
        available_width = page_width - 2 * clearance
        available_height = page_height - 2 * clearance
        columns = 0
        rows = 0
        if available_width >= patch_size_mm:
            columns = int((available_width + self.patch_spacing_mm) // step)
        if available_height >= patch_size_mm:
            rows = int((available_height + self.patch_spacing_mm) // step)
        header_mm = (calibration_header_line_count(orientation)
                     * body_line_leading_mm())
        return CalibrationGrid(
            orientation=orientation,
            patch_size_mm=patch_size_mm,
            spacing_mm=self.patch_spacing_mm,
            origin_x_mm=clearance,
            origin_y_mm=clearance,
            columns=columns,
            rows=rows,
            header_rows=_cells_for_mm(header_mm, step, self.patch_spacing_mm),
            qr_cells=_cells_for_mm(
                calibration_qr_footprint_bound_mm(), step, self.patch_spacing_mm),
        )

    def lateral_free_height_mm(self, orientation: str) -> float:
        """Hauteur du couloir lateral que la colonne de pastilles ne remplit **pas**.

        **Le fait que ce calcul existe est un releve d'Egan, et la conclusion intuitive
        etait fausse dans les deux sens.** La colonne de pastilles occupe 6 mm de large
        mais pas toute la hauteur du couloir: sous elle, il reste de la place, et un QR de
        flanc peut s'y coller a la marge d'encre au lieu de se ranger a cote de la
        colonne. Le banc de recherche s'est trompe **deux fois de suite sur ce meme
        point**, dans les deux sens opposes: d'abord un `max` qui faisait chevaucher le QR
        et la colonne (section 8.6), puis un empilement horizontal qui reserve 8 mm pour
        rien la ou la hauteur libre suffit. Le degagement ne se pose donc ni d'une facon
        ni de l'autre: il se **calcule**.

        Le nombre de rangees retenu est `min(PATCH_MAX_ROWS_PER_SIDE, capacite du
        couloir)`: aucun preset du depot ne pose plus de 18 rangees par cote, et le
        couloir n'en porte pas plus qu'il n'en tient. Les deux bornes sont reelles, et la
        seconde est ce qui rend l'enonce bien forme en paysage, ou 18 rangees ne tiennent
        pas du tout.
        """
        _page_width, page_height = page_size_mm(orientation)
        rows = min(PATCH_MAX_ROWS_PER_SIDE, self.lateral_row_capacity(orientation))
        column = 0.0
        if rows > 0:
            column = (rows * self.patch_size_mm
                      + (rows - 1) * self.patch_spacing_mm)
        return ((page_height - self.corner_clearance_mm())
                - (self.lateral_first_row_y_mm() + column))

    def qr_flank_clearance_mm(self, orientation: str) -> float:
        """Degagement qu'exige un flanc porteur du QR, **calcule** (AC 3 de 5.18).

        Deux branches, et le test doit exercer les deux:

        * la hauteur libre sous la colonne loge l'emprise -- le QR se **colle** a la
          marge d'encre, a une autre ordonnee que les pastilles, et le degagement vaut
          `marge d'encre + emprise + garde` (49,62 mm). C'est le regime du **portrait**,
          ou 79 mm restent libres sous une colonne pleine;
        * elle ne la loge pas -- le QR se range **a cote** de la colonne, et le
          degagement vaut `fin du bloc de pastilles + ecart + emprise + garde`
          (57,62 mm). C'est le regime du **paysage**, ou il ne reste qu'un millimetre.

        Ecart entre les deux: 8,0 mm par flanc. **Et il ne rend aucune surface de
        dessin**: le seul cardinal qui envoie le QR sur un flanc est borne en hauteur, la
        largeur supplementaire lui est inutilisable. C'est une correction de justesse, pas
        un gain -- mais elle doit etre faite, parce qu'un futur jeu de temoins ou un futur
        cardinal la rendrait mordante.
        """
        footprint = qr_footprint_bound_mm()
        if self.lateral_free_height_mm(orientation) >= footprint:
            return self.printer_margin_mm + footprint + TOP_BAND_GUARD_MM
        lateral = (self.patch_block_end_mm(orientation)
                   + self.patch_to_band_gap_mm[orientation])
        return lateral + footprint + TOP_BAND_GUARD_MM

    def band_edges_mm(self, orientation: str, qr_edge: str) -> dict[str, float]:
        """Les **quatre** degagements de la bande, pour un bord porteur donne.

        Chacun est un `max` entre ce que le bord doit de toute facon (degagement de
        coin, pastilles laterales) et ce qu'exige l'element qu'il porte -- l'entete en
        haut, le pied de page en bas. Jamais un degagement plus une constante additive:
        c'est la forme qui a permis a la v1 de tenir sans que personne n'ait a nommer
        ces exigences, et qui les rend mordantes des que les marqueurs se resserrent.

        **Le QR est la seule exception a la regle du `max`, et son flanc se CALCULE**
        (section 8.6 de `analyse-2026-08-11-passe-de-design-v2.md`, puis le releve d'Egan
        du 2026-08-12). Sur un bord **horizontal** il se dispute le meme espace que
        l'entete ou le pied: `max`. Sur un **flanc** ni le `max` ni la somme ne sont
        justes en general -- voir :meth:`qr_flank_clearance_mm`, qui tranche sur la
        hauteur libre reelle sous la colonne de pastilles. Le banc s'est trompe deux fois
        sur ce point, une fois dans chaque sens.
        """
        if qr_edge not in QR_EDGES:
            raise UnknownTemplateError(
                f"Bord porteur du QR inconnu: '{qr_edge}'. Bords: "
                f"{', '.join(QR_EDGES)}."
            )
        clearance = self.corner_clearance_mm()
        need = self.qr_edge_clearance_mm()
        top = max(clearance, self.header_identity_clearance_mm())
        bottom = max(clearance + self.bottom_extra_clearance_mm[orientation],
                     self.bottom_text_clearance_mm())
        left = right = (self.patch_block_end_mm(orientation)
                        + self.patch_to_band_gap_mm[orientation])
        flank = self.qr_flank_clearance_mm(orientation)
        if qr_edge == QR_EDGE_TOP:
            top = max(top, need)
        elif qr_edge == QR_EDGE_BOTTOM:
            bottom = max(bottom, need)
        elif qr_edge == QR_EDGE_LEFT:
            left = flank
        else:
            right = flank
        return {"top": top, "bottom": bottom, "left": left, "right": right}

    def frame_band_candidates(
        self, orientation: str, qr_edge: str | None = None
    ) -> tuple[tuple[str, dict], ...]:
        """Les placements de temoins possibles, avec la bande que chacun laisse.

        Rend un seul candidat (`WITNESS_PLACEMENT_SIDES`) quand la version pose ses
        pastilles aux cotes sans exception, deux sinon. **Les deux sont composes**:
        c'est :meth:`frame_band_mm` qui tranche, par mesure de surface et jamais par
        heuristique.

        ``qr_edge`` vaut par defaut le bord que la version fige, et il est **exige** des
        que la version compose les quatre bords: la bande depend alors du bord, donc
        une bande rendue sans lui serait une bande devinee (contrat 4.5).
        """
        if qr_edge is None:
            if self.qr_bearing_edge is None:
                raise UnknownTemplateError(
                    f"La geometrie '{self.version}' compose les quatre bords porteurs "
                    "du QR: la bande de frames depend du bord, qui doit etre nomme."
                )
            qr_edge = self.qr_bearing_edge
        page_width, page_height = page_size_mm(orientation)
        edges = self.band_edges_mm(orientation, qr_edge)
        top, bottom = edges["top"], edges["bottom"]
        sides = {
            "x": edges["left"],
            "y": top,
            "width": page_width - edges["left"] - edges["right"],
            "height": page_height - top - bottom,
        }
        if self.border_witness_count is None:
            return ((WITNESS_PLACEMENT_SIDES, sides),)

        # Rangees horizontales: la bande gagne les colonnes laterales (elle ouvre au
        # silence des marqueurs) et paie en hauteur ce que les rangees occupent.
        #
        # Le degagement du QR sur un flanc **reste du** dans cette variante: ce qu'elle
        # rend, ce sont les pastilles laterales, pas la place du QR. Sans ce `max`, la
        # bande ouvrirait a 28 mm par-dessus une emprise de QR qui court jusqu'a
        # 52,6 mm -- exactement l'erreur de la section 8.6, reproduite un cran plus bas.
        edge = self.corner_clearance_mm()
        left_edge = max(edge, edges["left"] if qr_edge == QR_EDGE_LEFT else 0.0)
        right_edge = max(edge, edges["right"] if qr_edge == QR_EDGE_RIGHT else 0.0)
        available = page_width - 2 * edge
        step = self.patch_size_mm + self.patch_spacing_mm
        per_row = max(1, int((available + self.patch_spacing_mm) // step))
        top_count = self.border_witness_count // 2
        bottom_count = self.border_witness_count - top_count
        top_strip = self._witness_strip_mm(top_count, per_row, orientation)
        bottom_strip = self._witness_strip_mm(bottom_count, per_row, orientation)
        borders = {
            "x": left_edge,
            "y": top + top_strip,
            "width": page_width - left_edge - right_edge,
            "height": page_height - top - top_strip - bottom - bottom_strip,
        }
        return ((WITNESS_PLACEMENT_SIDES, sides), (WITNESS_PLACEMENT_BORDERS, borders))

    def _witness_strip_mm(self, count: int, per_row: int, orientation: str) -> float:
        """Encombrement vertical de ``count`` pastilles en rangees, ecart compris."""
        if count <= 0:
            return 0.0
        rows = -(-count // per_row)  # division entiere par exces
        return (rows * self.patch_size_mm + (rows - 1) * self.patch_spacing_mm
                + self.patch_to_band_gap_mm[orientation])

    def witness_placement(self, orientation: str, cardinal: int | None = None) -> str:
        """Placement de temoins retenu pour ce gabarit (mesure, pas deduit)."""
        return self._best_candidate(orientation, cardinal)[1]

    def qr_edge(self, orientation: str, cardinal: int | None = None) -> str:
        """Bord porteur du QR retenu pour ce gabarit (mesure, pas pose)."""
        return self._best_candidate(orientation, cardinal)[0]

    def frame_band_mm(self, orientation: str, cardinal: int | None = None) -> dict:
        """Bande de frames d'un gabarit, **derivee de ses constituants**.

        Avant le 2026-08-10 ces quatre nombres etaient ecrits en litteral par
        orientation. Consequence mesuree et rapportee dans
        `analyse-2026-08-10-optimisation-de-la-page.md`: **reduire la taille des
        marqueurs ne reduisait aucune marge**, la bande n'en dependant pas. Toute
        optimisation de place d'impression devait donc etre ressaisie a la main dans
        huit nombres, donc se desynchronisait au premier changement suivant.

        La derivation ne change **aucune** geometrie a constituants egaux -- un test
        le verrouille valeur par valeur contre les litteraux historiques.

        ``cardinal`` est **exige** des que la version compose deux placements de
        temoins (`border_witness_count` non nul) ou les quatre bords porteurs du QR:
        le candidat retenu depend du cardinal, donc rendre une bande sans lui serait
        une bande devinee. Il reste facultatif pour la v1, dont la bande ne depend que
        de l'orientation.
        """
        return self._best_candidate(orientation, cardinal)[2]

    def _candidates(self, orientation: str) -> tuple[tuple[str, str, dict], ...]:
        """Tous les couples (bord porteur du QR, placement de temoins) composables.

        Le produit des deux et non les deux separement: **ils sont couples**. Plus le
        pied de page s'allege, moins le QR y est gratuit, et une variante de temoins qui
        ouvre la bande au silence des marqueurs ne rend pas la meme chose selon que le
        QR mange un flanc ou non. Les traiter l'un apres l'autre rendrait un optimum
        local.
        """
        return tuple(
            (qr_edge, placement, band)
            for qr_edge in self.qr_edge_candidates()
            for placement, band in self.frame_band_candidates(orientation, qr_edge)
        )

    def _best_candidate(
        self, orientation: str, cardinal: int | None
    ) -> tuple[str, str, dict]:
        candidates = self._candidates(orientation)
        if len(candidates) == 1:
            return candidates[0]
        if cardinal is None:
            raise UnknownTemplateError(
                f"La geometrie '{self.version}' compose plusieurs candidats de bande "
                "(placements de temoins, bords porteurs du QR): la bande de frames "
                "depend du cardinal, qui doit etre nomme. Une bande rendue sans "
                "cardinal serait une bande devinee (contrat 4.5)."
            )
        best: tuple[tuple, str, str, dict] | None = None
        for qr_edge, placement, band in candidates:
            area = _drawing_area_mm2(band, cardinal, self.frame_grid_gap_mm,
                                     self.frame_grid_row_gap_mm())
            if area <= 0.0:
                continue
            key = self._ranking_key(qr_edge, placement, band, area)
            if best is None or key < best[0]:
                best = (key, qr_edge, placement, band)
        if best is None:
            raise UnknownTemplateError(
                f"Aucun candidat de bande ne laisse de grille de {cardinal} "
                f"zone(s) 16:9 sous la geometrie '{self.version}' en {orientation}."
            )
        return best[1], best[2], best[3]

    def _ranking_key(
        self, qr_edge: str, placement: str, band: Mapping[str, float], area: float
    ) -> tuple:
        """Clef de tri des candidats: la surface d'abord, puis la regle de departage.

        **La regle de departage est ecrite, et c'est un defaut du banc a ne pas
        reproduire.** 6f et 8f sont bornes en **largeur**: leur surface est identique au
        bord haut et au bord bas, et le banc rapportait `haut` pour 6f par simple ordre
        de boucle -- un verdict qui aurait change en reordonnant une boucle.

        Trois criteres, dans cet ordre:

        1. **la surface de dessin**, arrondie au centieme de mm2. L'arrondi est ce qui
           fait exister l'egalite: deux bandes de meme hauteur calculees par des
           divisions differentes rendent des flottants distants de 1e-13, et une
           comparaison stricte ferait alors trancher le dernier chiffre binaire au lieu
           de la regle;
        2. **la hauteur de bande**, la plus grande gagnant. A surface egale, c'est la
           bande la plus haute qui laisse le plus de jeu a ce qui se pose **hors** des
           zones -- les etiquettes d'emplacement sous chaque zone, et le pas de grille
           d'une partition future. Une bande large et plate n'offre pas ce jeu;
        3. **l'ordre `bas, haut, gauche, droit`** (`QR_EDGES`), puis les cotes avant les
           rangees haut/bas. Le bord bas vient en tete parce qu'il est celui que le pied
           de page paie **deja**: l'y poser est le geste dont le cout est le plus
           souvent nul, et un choix par defaut doit etre le moins cher, pas le premier
           qui vient.
        """
        return (
            -round(area, 2),
            -round(band["height"], 6),
            QR_EDGES.index(qr_edge),
            0 if placement == WITNESS_PLACEMENT_SIDES else 1,
        )


#: Geometrie de production historique, celle de toutes les planches imprimees
#: jusqu'au 2026-08-11. Construite depuis les constantes du module pour que le test
#: qui verrouille leur egalite avec `layout` et `patch_presets` garde son sens; mais
#: c'est **cet objet** que lisent les consommateurs, jamais les constantes: une
#: constante changee apres l'import ne deplace plus `v1`, par construction.
GEOMETRY_V1 = PageGeometry(
    version="v1",
    marker_size_mm=MARKER_SIZE_MM,
    marker_margin_mm=MARKER_MARGIN_MM,
    marker_quiet_zone_mm=MARKER_QUIET_ZONE_MM,
    printer_margin_mm=PRINTER_MARGIN_MM,
    patch_size_mm=PATCH_SIZE_MM,
    patch_spacing_mm=PATCH_SPACING_MM,
    patch_columns_per_side=MappingProxyType(
        {ORIENTATION_PORTRAIT: 2, ORIENTATION_PAYSAGE: 3}
    ),
    patch_to_band_gap_mm=MappingProxyType(
        {ORIENTATION_PORTRAIT: 4.0, ORIENTATION_PAYSAGE: 3.0}
    ),
    bottom_extra_clearance_mm=MappingProxyType(
        {ORIENTATION_PORTRAIT: 9.5, ORIENTATION_PAYSAGE: 2.0}
    ),
)

#: Nombre de pastilles temoins d'une planche d'images sous la geometrie resserree:
#: le jeu retenu par `EPIC5-ARB-57` -- 8 sentinelles + les tetes `neutral-020`/`245`
#: et R/V/B + 1 neutre median = 14 valeurs, en double replicat. Le doublement n'est
#: pas du confort: une valeur vue une seule fois n'a pas de dispersion, donc la garde
#: de divergence serait aveugle. Ce cardinal ne dimensionne que la variante « rangees
#: haut/bas » du placement; il n'entre dans aucune emprise laterale.
#:
#: **Passe de 28 a 34 le 2026-08-17** (story 5.23, `EPIC5-ARB-82`): le jeu temoin gagne
#: les trois secondaires (`patches-17-v4`, 17 valeurs x 2). Ce n'est pas une
#: redefinition silencieuse de la v2, et la difference se mesure au lieu de s'affirmer:
#: sous les deux valeurs, **les 30 gabarits v2 retiennent le meme candidat** (`cotes`,
#: meme bord porteur du QR) et rendent la **meme bande de frames au flottant pres** --
#: un test l'epingle gabarit par gabarit en composant les deux geometries. Le cardinal
#: ne dimensionne en effet que la variante « rangees haut/bas », qu'aucun gabarit ne
#: retient a 28 et qu'aucun ne peut retenir a 34, l'augmenter ne pouvant que la
#: desavantager. Une planche deja imprimee sous la v2 est donc composee a l'identique.
WITNESS_PATCH_COUNT_V2 = 34

#: Geometrie resserree dite « prudente » (story 5.15, mandat d'`EPIC5-ARB-56`).
#: Marqueur 15 mm (facteur 3,75 au-dessus du plancher de detection mesure a 4 mm),
#: marge 8 mm, silence 5 mm (facteur 10 au-dessus des 0,5 mm tenus), pastilles 6 mm
#: au pas de 9 mm, une colonne de temoins par cote.
#:
#: **Ce que le tirage reel dit de ces 8 mm, et il faut le lire avant d'en proposer
#: moins** (`analyse-2026-08-11-scan-des-bords.md`): le contenu imprime fait
#: **+1,07 %** de sa taille nominale (mediane sur neuf marqueurs, mesuree sur le cote
#: de chaque marqueur -- longueur connue et locale -- et non sur l'ecart entre
#: marqueurs eloignes, qui melangerait l'echelle avec l'erreur de placement). Soit
#: +1,13 mm de deplacement au bord lateral et +1,59 mm au bord haut ou bas: le bord
#: exterieur d'un marqueur de coin, a 8,0 mm nominal, atterrit a **6,9 mm** reels, et
#: l'encre a prouve qu'elle sort jusqu'a 2,0 mm du bord du papier. La v2 absorbe donc
#: la derive avec un facteur de securite superieur a trois.
#:
#: Le scenario **agressif** (marqueur 10, marge 5, silence 3) ne l'absorberait pas --
#: 3,9 mm reels et 1,9 mm de silence effectif -- et il ne doit **pas** etre enregistre
#: comme une v3 au motif que la v2 a reussi: la feuille de bords ne l'a pas eprouve.
GEOMETRY_V2 = PageGeometry(
    version="v2",
    marker_size_mm=15.0,
    marker_margin_mm=8.0,
    marker_quiet_zone_mm=5.0,
    printer_margin_mm=PRINTER_MARGIN_MM,
    patch_size_mm=6.0,
    patch_spacing_mm=3.0,
    patch_columns_per_side=MappingProxyType(
        {ORIENTATION_PORTRAIT: 1, ORIENTATION_PAYSAGE: 1}
    ),
    # **Ecart pastilles / bande porte a 2 mm dans les deux orientations** par la passe de
    # design (AC 6 de la story 5.18, mandat d'`EPIC5-ARB-61` point 6). Les 4 mm du
    # portrait et les 3 mm du paysage etaient « calibres une fois sur la production et
    # jamais rediscutes », et leur asymetrie n'est justifiee nulle part dans le depot.
    # **Le tableau de gains qui figurait ici ne se reproduit pas** (corrige le 2026-08-12,
    # revue de 5.18, m10). Il annoncait, « pas de grille a 3 mm compris et par la
    # production seule »: +7,8 % (2f), +16,9 % (3f), +15,1 % (4f), +13,4 % (6f), +27,4 %
    # (8f), +0,0 % (1f). Deux figures sur six se reproduisent, et il ne nommait pas son
    # orientation. Mesure refaite du couple complet (ecart 2 mm **et** pas de grille 3 mm)
    # contre l'etat anterieur (4/3 mm et 10 mm), tout le reste inchange:
    #
    #     cardinal   portrait   paysage   meilleure orientation
    #        1f       +4,49     +0,00       +0,00
    #        2f       +4,49     +7,07       +4,49
    #        3f      +10,06       n/a      +10,06
    #        4f      +16,09     +8,34       +8,34
    #        6f      +13,36    +13,26      +13,36
    #        8f      +15,61    +20,17      +15,61
    #
    # L'ecart au tableau annonce est **structure**, et c'est ce qui le rend interessant:
    # 3f et 4f sont precisement les gabarits que la passe envoie sur un **flanc**, ou le
    # degagement vaut `marge + emprise + garde` et ne contient pas `patch_to_band_gap` du
    # tout. Le tableau avait donc ete mesure **avant** que la selection de bord ne soit en
    # place, puis n'a pas ete refait.
    #
    # Isole (ecart seul, pas de grille inchange), le gain du passage a 2 mm vaut +4,49 %
    # (portrait 1f et 2f), +4,57 % (portrait 6f et 8f), **+0,00 %** (portrait 3f et 4f,
    # paysage 1f et 4f) et +1,5 % (paysage 2f, 6f, 8f) -- une zone unique bornee en hauteur
    # ne paie aucun ecart lateral.
    patch_to_band_gap_mm=MappingProxyType(
        {ORIENTATION_PORTRAIT: 2.0, ORIENTATION_PAYSAGE: 2.0}
    ),
    # Le supplement de degagement du bord bas reste **celui de la v1**, et ce n'est pas
    # un oubli: aucune AC de la passe de design ne le rouvre, et `EPIC5-ARB-61` ne le
    # nomme pas.
    #
    # **Il est INERTE a sa valeur livree, et le commentaire qui figurait ici affirmait
    # l'inverse** (corrige le 2026-08-12; trouve trois fois independamment -- M2 de la
    # couche 1, F5 des constats, implique par le M-4 de la couche 2). Il annoncait que ce
    # terme est « la borne du bord bas des que le QR n'y est pas (37,5 mm en portrait
    # contre 28 de degagement de coin) », que le banc de la passe l'ignorait, et que cela
    # coute « 6,4 % sur le seul cardinal qui envoie le QR sur un flanc ». Les trois enonces
    # sont faux, et le mecanisme est arithmetique:
    #
    #     bord bas SANS QR:  portrait  coin + extra = 37,5 | pied = 45,36 | retenu = 45,36
    #                        paysage   coin + extra = 30,0 | pied = 45,36 | retenu = 45,36
    #
    # Le `max` de `band_edges_mm` a **trois** termes, et `bottom_text_clearance_mm()`
    # domine `coin + extra` dans les **deux** orientations: la comparaison « 37,5 contre
    # 28 » omettait le terme qui gagne. Le modele du banc, `max(coin, pied)`, rendait donc
    # exactement ce que la production rend -- il n'ignorait rien. Et le cout n'est pas de
    # 6,4 % sur un cardinal, il est de **0,000 % sur tous les gabarits**: a sa valeur
    # livree ce champ rend exactement les memes surfaces qu'a 0,0. Le depot se
    # contredisait lui-meme a 400 lignes d'intervalle, un test **assertant** deja que le
    # supplement est domine.
    #
    # Le champ **fonctionne** -- a 20 mm il mord sur le 3f et le 4f portrait, a 40 mm sur
    # presque tous -- donc ce n'est pas un artefact de mesure mais une **valeur dominee**.
    # Les deux volets sont epingles par
    # `test_the_bottom_extra_clearance_is_inert_at_its_delivered_value`: inerte a la valeur
    # livree, **et** mordant a 20 mm. Sans le second volet le test passerait aussi si le
    # champ etait purement ignore.
    #
    # La question « pourquoi ce champ existe-t-il, s'il est inerte ? » -- marge de securite
    # a asserter, ou reste devenu inutile quand le pied a grossi a six rangees -- est
    # versee au `deferred-work.md`. Ce qui est ferme ici, c'est qu'on ne lui attribue plus
    # un gain qu'il ne produit pas.
    bottom_extra_clearance_mm=MappingProxyType(
        {ORIENTATION_PORTRAIT: 9.5, ORIENTATION_PAYSAGE: 2.0}
    ),
    border_witness_count=WITNESS_PATCH_COUNT_V2,
    frame_grid_gap_mm=FRAME_GRID_GAP_V2_MM,
    # Les quatre bords sont composes et le plus dessinant retenu, cardinal par cardinal.
    qr_bearing_edge=None,
    identity_in_header=True,
)

#: Versions de geometrie que le registre sait resoudre. Ajouter une entree ici
#: **ajoute** des `template_id`; cela n'en redefinit aucun.
GEOMETRY_VERSIONS = MappingProxyType(
    {GEOMETRY_V1.version: GEOMETRY_V1, GEOMETRY_V2.version: GEOMETRY_V2}
)

#: Version employee quand l'appelant n'en nomme pas.
#:
#: **Le defaut bascule sur la v2 le 2026-08-12**, a la livraison de la passe de design
#: (`EPIC5-ARB-61`, AC 11 de la story 5.18). C'est cette story qui referme la fenetre
#: que la passe de correction de 5.15 avait ouverte en ramenant le defaut a la v1: les
#: valeurs de la v2 sont desormais **figees par la mesure**, donc composer par defaut
#: dans cette geometrie n'expose plus a un tirage qu'une redefinition rendrait
#: illisible. Les trois faits qui exigeaient d'attendre sont repris un par un, parce
#: qu'une constante de defaut qui bouge sans trace de sa cause est exactement ce qu'une
#: session ulterieure ne saura pas re-justifier:
#:
#: 1. **la regression mesuree est levee, pas contournee**: `makepdf --orientation
#:    paysage --nombre-patchs patches-18-v2` composait sous la v1 et echouait sous la
#:    v2 (18 rangees au pas de 9 mm exigent 159 mm quand le couloir lateral d'une page
#:    paysage en offre **151** -- `lateral_row_capacity("paysage")` rend 17 rangees).
#:    Le couple reste refuse -- c'est une impossibilite geometrique, pas un defaut --
#:    et `makepdf --geometrie v1` reste cable pour le composer. Un test balaye le
#:    couple `paysage x patches-18-v2` en v1 apres la bascule.
#:
#:    **Deux corrections du 2026-08-12 (revue de 5.18, M3).** Ce fait disait « 154 mm »,
#:    le chiffre qu'une revue anterieure avait porte a **151** dans le docstring de
#:    `patch_presets._PLACEMENT_UNPLACEABLE` parce que 154 decrivait le couloir entre les
#:    deux silences et non ce que `_derived_row_capacity` mesure. Et il affirmait que le
#:    couple est refuse « en nommant sa cause »: **il ne la nomme pas.**
#:    `_PLACEMENT_UNPLACEABLE` n'est lu qu'a la **construction** du registre, pour sauter
#:    le couple; `resolve_patch_layout` ne le consulte jamais, et le couple retombe dans
#:    la branche generique « couvert mais pas pour ce preset ». Porter le motif chiffre
#:    jusqu'au refus est verse au `deferred-work.md` -- c'est un defaut anterieur a 5.18.
#:    Ce que la bascule peut revendiquer est plus modeste, et vrai: le couple est
#:    **enumere** et refuse **bruyamment**, jamais approxime;
#: 2. **`EPIC5-ARB-61` est livre**: pas de grille, ecart pastilles/bande, bord porteur
#:    du QR, mise en page du pied et de l'entete sont mesures et epingles par la story
#:    5.18. La fenetre de redefinition de la v2 se ferme donc **maintenant**: des
#:    qu'une planche v2 sort d'une imprimante, toute evolution passe par une v3;
#: 3. **le seuillage ArUco reste dimensionne sur la v1**: `detection/aruco.py`
#:    dimensionne son seuillage adaptatif sur `layout.MARKER_SIZE_MM = 30 mm` quand la
#:    v2 imprime des marqueurs de **15 mm** -- `adaptiveThreshWinSizeMax` vaut alors
#:    87 px pour un module de 44 px, soit le facteur 2 que le commentaire de
#:    `detector_parameters` dit vouloir eviter. **C'est le risque assume de la bascule**,
#:    et il l'est pour une raison mesurable: le point ne se tranche pas sur une fixture
#:    de synthese (la regression du seuillage du 2026-08-10 etait detectee 4/4 sur une
#:    page synthetique **par les parametres fautifs**, son bord net suffisant a fermer le
#:    contour), il demande un tirage v2 reel -- que seule la bascule rend atteignable.
#:    L'autre reserve versee au `deferred-work.md`, le retrait d'echantillonnage a
#:    **1,5 mm** sans plancher absolu, est du meme genre et du meme cote: assumee, parce
#:    que sa mesure exige la meme planche. Aucun des deux ne doit etre ferme **avant** la
#:    bascule, et c'est la reponse a la question que l'AC 11 pose: les fermer avant
#:    demanderait de les trancher sur une fixture de synthese, ce qui est precisement le
#:    geste que la mesure du 2026-08-10 a montre inoperant.
#:
#: **Ce que le tirage reel dit des 8 mm de la v2, a lire avant d'en proposer moins**
#: -- depouillement du scan de
#: `projects/projet_demo/srcs/Agressif_TEST_2026-08-11_174937.pdf`
#: (banc `scripts/research/analyse_edge_test_scan.py`, rapport
#: `analyse-2026-08-11-scan-des-bords.md`): les 4 reperes de limite d'encre a 5,0 mm du
#: bord sont presents (couverture 0,90 / 0,91 / 1,00 / 1,00), les 18 pastilles temoins
#: sur 18 posees a 5,0 mm du bord lateral sont entieres, le QR pose a 5,0 mm du bord
#: haut decode avec une charge utile identique octet pour octet, et les quatre coins
#: prudents a 8,0 mm sont detectes 4 sur 4. L'encre sort physiquement jusqu'a 2,0 mm du
#: bord du papier: la marge de 5 mm de la v2 dispose d'un facteur de securite superieur
#: a deux sur le bord le plus expose. Cette mesure reste acquise, et c'est desormais la
#: geometrie qu'elle valide qui est figee.
DEFAULT_GEOMETRY_VERSION = GEOMETRY_V2.version


def get_geometry(version: str) -> PageGeometry:
    """Resoudre une version de geometrie ou echouer explicitement."""
    try:
        return GEOMETRY_VERSIONS[version]
    except KeyError:
        raise UnknownTemplateError(
            f"Version de geometrie inconnue: '{version}'. Une version inconnue ne "
            "se resout jamais en geometrie devinee (contrat 4.5). Versions "
            f"connues: {', '.join(GEOMETRY_VERSIONS)}."
        ) from None


#: Les quatre nombres par orientation tels qu'ils etaient ecrits en litteral avant la
#: derivation du 2026-08-10. Conserves pour que le test de non-regression compare a une
#: valeur **figee dans le fichier** et non a un recalcul: comparer la derivation a
#: elle-meme ne verrouillerait rien.
_HISTORICAL_FRAME_BANDS_MM = {
    ORIENTATION_PORTRAIT: {"x": 35.0, "y": 60.0, "width": 140.0, "height": 167.5},
    ORIENTATION_PAYSAGE: {"x": 48.0, "y": 60.0, "width": 201.0, "height": 88.0},
}

#: Identifiant du template historique (story 4.7 l'a pose la premiere; le
#: registre le derive et un test verrouille l'egalite des deux formes).
TEMPLATE_A4_PORTRAIT_2F = "tpl-a4-portrait-2f-v1"


class UnknownTemplateError(ValueError):
    """Raised when a ``template_id`` is not part of the registry."""


@dataclass(frozen=True)
class TemplateSpec:
    """Geometrie complete d'un template de page, en mm (origine haut-gauche,
    y vers le bas, convention ``layout.py``)."""

    template_id: str
    page_format: str
    orientation: str
    frames_per_page: int
    margin_preset: str
    margin_mm: float
    page_width_mm: float
    page_height_mm: float
    grid_columns: int
    grid_rows: int
    #: Vue interne des zones de dessin. **Jamais lue directement par un consommateur**:
    #: l'acces public est la propriete `frame_zones_mm`, qui en rend des copies. Le
    #: champ portait ce nom-la jusqu'a la passe de correction de 5.15, ou la revue a
    #: mesure qu'il exposait des `dict` nus partages par tout le processus -- une
    #: mutation par un appelant corrompait le registre pour la duree du programme, et
    #: la story avait justement pose la copie defensive sur le champ voisin
    #: `frame_band`. L'asymetrie n'avait pas de raison; elle n'en a pas davantage
    #: aujourd'hui.
    frame_zones: tuple[dict, ...]
    #: Constituants physiques figes de la version portee par le `template_id`. Les
    #: consommateurs (marqueurs de coin, bande du QR, placement des pastilles) lisent
    #: **ceci** et non les constantes du module: c'est ce qui rend une planche
    #: imprimee sous une version anterieure encore scannable apres un resserrement.
    geometry: PageGeometry
    #: Bande de frames **effectivement** utilisee pour calculer les zones ci-dessus.
    #: Elle est portee par le spec et non recalculee par les consommateurs: sous une
    #: version qui compose deux placements de temoins, la bande depend du cardinal, et
    #: un consommateur qui la recalculerait par orientation seule jugerait l'emprise du
    #: QR ou du pied de page contre une autre bande que celle qui a produit les zones.
    frame_band: Mapping[str, float] = field(default_factory=dict)
    #: Placement de temoins retenu, par mesure de surface (`EPIC5-ARB-55`).
    witness_placement: str = WITNESS_PLACEMENT_SIDES
    #: Bord porteur du QR retenu, par mesure de surface (AC 3 de la story 5.18). Porte
    #: par le spec pour la meme raison que le placement des temoins: une surface egale
    #: ne dit pas quel candidat l'a produite, et **tous** les consommateurs de la page
    #: -- bande du QR, zones de pied de page, zones reservees aux pastilles -- doivent
    #: lire le meme bord que celui qui a produit les zones.
    qr_edge: str = QR_EDGE_TOP

    @property
    def geometry_version(self) -> str:
        """Version de geometrie que porte le suffixe du `template_id`."""
        return self.geometry.version

    @property
    def frame_band_mm(self) -> dict:
        """Copie de la bande de frames du gabarit (jamais la vue interne).

        Copie defensive pour la meme raison que `patch_presets.reserved_zones_mm`: une
        mutation par un appelant corromprait le registre pour tout le processus.
        """
        return dict(self.frame_band)

    @property
    def frame_zones_mm(self) -> tuple[dict, ...]:
        """Copies des zones de dessin du gabarit (jamais les dicts internes).

        Meme raison que `frame_band_mm` et `patch_presets.reserved_zones_mm`, et une
        raison de plus: ces zones sont celles que **tous** les consommateurs lisent --
        composition, recadrage au scan, resolution de geometrie -- donc une corruption
        s'y propage a l'impression comme a la relecture. Le tuple exterieur etait deja
        immuable; ce sont les dicts qu'il porte qui ne l'etaient pas.
        """
        return tuple(dict(zone) for zone in self.frame_zones)


def build_template_id(
    orientation: str,
    frames_per_page: int,
    margin_preset: str,
    geometry_version: str = DEFAULT_GEOMETRY_VERSION,
) -> str:
    """Identifiant canonique et versionne d'un couple accepte du vocabulaire."""
    if orientation not in ORIENTATIONS:
        raise UnknownTemplateError(
            f"Orientation inconnue: '{orientation}'. Vocabulaire: "
            f"{', '.join(ORIENTATIONS)}."
        )
    # Le retrait est **par orientation** depuis `EPIC5-ARB-64`: le meme cardinal peut
    # etre retire ici et offert dans l'autre orientation de la meme version.
    retired = _RETIRED_CARDINALS.get(geometry_version, {}).get(orientation, {})
    if frames_per_page in retired:
        allowed = ", ".join(
            str(v) for v in frames_per_page_vocabulary(orientation, geometry_version))
        other = [
            name for name in ORIENTATIONS
            if name != orientation
            and frames_per_page in frames_per_page_vocabulary(name, geometry_version)
        ]
        elsewhere = (
            f" Il reste offert en {', '.join(other)} sous la meme version." if other
            else ""
        )
        raise UnknownTemplateError(
            f"Cardinal de frames par page retire du vocabulaire de la geometrie "
            f"{geometry_version} en {orientation}: {frames_per_page}. Motif: "
            f"{retired[frames_per_page]}. Vocabulaire de {geometry_version} en "
            f"{orientation}: {allowed}.{elsewhere} Le cardinal reste resolvable dans les "
            "versions qui ne l'ont pas retire, pour que les planches deja imprimees "
            "restent relisibles."
        )
    if frames_per_page not in FRAMES_PER_PAGE_VOCABULARY[orientation]:
        allowed = ", ".join(str(v) for v in FRAMES_PER_PAGE_VOCABULARY[orientation])
        raise UnknownTemplateError(
            f"Cardinal de frames par page hors vocabulaire pour l'orientation "
            f"{orientation}: {frames_per_page}. Vocabulaire: {allowed}."
        )
    if margin_preset not in MARGIN_PRESETS_MM:
        raise UnknownTemplateError(
            f"Preset de marge inconnu: '{margin_preset}'. Presets: "
            f"{', '.join(MARGIN_PRESETS_MM)}."
        )
    # Valide la version avant de la coller dans l'identifiant: un suffixe fabrique
    # depuis une version inconnue produirait un `template_id` d'apparence normale que
    # `get_template` refuserait ensuite sans dire pourquoi.
    get_geometry(geometry_version)
    margin_fragment = "" if margin_preset == DEFAULT_MARGIN_PRESET else f"-m{margin_preset}"
    return (f"tpl-a4-{orientation}-{frames_per_page}f{margin_fragment}"
            f"-{geometry_version}")


def frame_band_mm(
    orientation: str,
    geometry_version: str = DEFAULT_GEOMETRY_VERSION,
    cardinal: int | None = None,
) -> dict:
    """Bande de frames de l'orientation, pour cette version de geometrie.

    ``cardinal`` est exige des que la version compose deux placements de temoins
    (voir :meth:`PageGeometry.frame_band_mm`); les consommateurs qui tiennent un
    `TemplateSpec` lisent plutot `spec.frame_band_mm`, qui porte la bande ayant
    reellement produit les zones.
    """
    return get_geometry(geometry_version).frame_band_mm(orientation, cardinal)


def _grid_shape(band_width: float, band_height: float, cardinal: int,
                gap_mm: float = FRAME_GRID_GAP_MM,
                row_gap_mm: float | None = None) -> tuple[int, int, float, float]:
    """Partition exacte colonnes x rangees maximisant la largeur de zone 16:9.

    ``gap_mm`` est le pas de grille **de la version**, passe par l'appelant depuis
    `PageGeometry.frame_grid_gap_mm`: il etait une constante de module jusqu'a la story
    5.18, donc la meme pour toutes les versions. Le defaut reste la valeur historique,
    pour que les bancs de recherche qui appellent cette fonction sans geometrie
    continuent de mesurer ce qu'ils mesuraient.

    **Cette fonction maximise deja sur les partitions uniformes** -- une annonce
    contraire (« la bande n'est pas remplie, il faut des partitions non uniformes ») a
    ete mesuree fausse: le sous-remplissage de 51 % en 3f est la consequence de zones
    16:9 dans une bande presque carree, pas d'une partition mal choisie.
    """
    row_gap_mm = gap_mm if row_gap_mm is None else row_gap_mm
    best: tuple[float, int, int] | None = None
    for columns in range(1, cardinal + 1):
        if cardinal % columns:
            continue
        rows = cardinal // columns
        width_limit = (band_width - (columns - 1) * gap_mm) / columns
        height_limit = (band_height - (rows - 1) * row_gap_mm) / rows
        if width_limit <= 0 or height_limit <= 0:
            continue
        width = min(width_limit, height_limit * 16.0 / 9.0)
        if best is None or width > best[0] + 1e-9:
            best = (width, columns, rows)
    if best is None:
        raise UnknownTemplateError(
            f"Aucune grille de {cardinal} zone(s) 16:9 ne tient dans la bande "
            f"{band_width} x {band_height} mm."
        )
    width, columns, rows = best
    return columns, rows, width, width * 9.0 / 16.0


def _drawing_area_mm2(band: Mapping[str, float], cardinal: int,
                      gap_mm: float = FRAME_GRID_GAP_MM,
                      row_gap_mm: float | None = None) -> float:
    """Surface totale de dessin qu'une bande rend pour ce cardinal, ou 0.

    ``0.0`` -- et non une exception -- quand aucune grille ne tient: cette fonction
    **compare** des candidats, dont certains peuvent ne rien laisser de composable. Le
    refus explicite reste rendu par l'appelant si aucun candidat ne tient
    (:meth:`PageGeometry._best_candidate`).
    """
    if band["width"] <= 0 or band["height"] <= 0:
        return 0.0
    try:
        _columns, _rows, zone_width, zone_height = _grid_shape(
            band["width"], band["height"], cardinal, gap_mm, row_gap_mm
        )
    except UnknownTemplateError:
        return 0.0
    return cardinal * zone_width * zone_height


def _compute_frame_zones(
    orientation: str, cardinal: int, geometry: PageGeometry
) -> tuple[tuple[int, int], tuple[dict, ...], dict, str, str]:
    qr_edge, placement, band = geometry._best_candidate(orientation, cardinal)
    gap = geometry.frame_grid_gap_mm
    row_gap = geometry.frame_grid_row_gap_mm()
    columns, rows, zone_width, zone_height = _grid_shape(
        band["width"], band["height"], cardinal, gap, row_gap
    )
    total_width = columns * zone_width + (columns - 1) * gap
    total_height = rows * zone_height + (rows - 1) * row_gap
    x0 = band["x"] + (band["width"] - total_width) / 2.0
    y0 = band["y"] + (band["height"] - total_height) / 2.0

    zones = []
    for index in range(cardinal):
        row, column = divmod(index, columns)
        zones.append(
            {
                "name": f"frame_zone_{index + 1}",
                "x": x0 + column * (zone_width + gap),
                "y": y0 + row * (zone_height + row_gap),
                "width": zone_width,
                "height": zone_height,
            }
        )
    return (columns, rows), tuple(zones), band, placement, qr_edge


def _build_registry() -> dict[str, TemplateSpec]:
    registry: dict[str, TemplateSpec] = {}
    for geometry in GEOMETRY_VERSIONS.values():
        for orientation in ORIENTATIONS:
            page_width, page_height = page_size_mm(orientation)
            for cardinal in frames_per_page_vocabulary(orientation, geometry.version):
                (columns, rows), zones, band, placement, qr_edge = _compute_frame_zones(
                    orientation, cardinal, geometry
                )
                for margin_preset, margin_mm in MARGIN_PRESETS_MM.items():
                    template_id = build_template_id(
                        orientation, cardinal, margin_preset, geometry.version
                    )
                    registry[template_id] = TemplateSpec(
                        template_id=template_id,
                        page_format=DEFAULT_PAGE_FORMAT,
                        orientation=orientation,
                        frames_per_page=cardinal,
                        margin_preset=margin_preset,
                        margin_mm=margin_mm,
                        page_width_mm=page_width,
                        page_height_mm=page_height,
                        grid_columns=columns,
                        grid_rows=rows,
                        frame_zones=zones,
                        geometry=geometry,
                        frame_band=MappingProxyType(dict(band)),
                        witness_placement=placement,
                        qr_edge=qr_edge,
                    )
    return registry


_REGISTRY = _build_registry()


def known_template_ids() -> tuple[str, ...]:
    """Tous les identifiants que le registre sait resoudre."""
    return tuple(_REGISTRY)


def get_template(template_id: str) -> TemplateSpec:
    """Resoudre ``template_id`` ou echouer explicitement (contrat 4.5)."""
    try:
        return _REGISTRY[template_id]
    except KeyError:
        raise UnknownTemplateError(
            f"Template inconnu: '{template_id}'. Un template_id inconnu ne se "
            "resout jamais en geometrie devinee (contrat 4.5). Templates "
            f"connus: {', '.join(known_template_ids())}."
        ) from None


def template_for(
    orientation: str,
    frames_per_page: int,
    margin_preset: str,
    geometry_version: str = DEFAULT_GEOMETRY_VERSION,
) -> TemplateSpec:
    """Resoudre le template d'un triplet accepte du vocabulaire."""
    return get_template(
        build_template_id(orientation, frames_per_page, margin_preset, geometry_version)
    )


#: Zones de pied de page **litterales** de la geometrie v1, par orientation. Ces
#: quatre nombres par zone ne se reconstruisent depuis aucun constituant: 240 et 45 en
#: portrait, 154 et 42 en paysage, 2 mm d'ecart entre le bloc et la ligne en paysage
#: contre 1 mm en portrait, et 1 mm de jeu sous la ligne en paysage contre 0 en
#: portrait. Une planche v1 doit s'imprimer a l'identique apres l'ajout de la v2, donc
#: on ne les derive pas: on les epingle, exactement comme `_HISTORICAL_FRAME_BANDS_MM`
#: epingle la bande de frames. Toute version **ajoutee** apres le 2026-08-11 passe par
#: la derivation de :func:`footer_zones_mm`.
_LEGACY_FOOTER_ZONES_MM: Mapping[str, Mapping[str, dict]] = {
    "v1": {
        # Les deux zones tiennent entre les silences des marqueurs du bas
        # (x [60, 150] pour y > 237): le pied de page du POC, qui court sous les
        # marqueurs, contaminait leur quiet zone -- non reproduit ici.
        ORIENTATION_PORTRAIT: {
            "footer_block": (60.0, 240.0, 90.0, 45.0),
            "footer_line": (60.0, 286.0, 90.0, 6.0),
        },
        ORIENTATION_PAYSAGE: {
            "footer_block": (60.0, 154.0, 177.0, 42.0),
            "footer_line": (60.0, 198.0, 177.0, 6.0),
        },
    },
}


def header_band_mm(spec: TemplateSpec) -> tuple[float, float, float, float]:
    """Bande **haute** du gabarit: celle des textes d'en-tete, QR ou non.

    x entre les silences des marqueurs de coin, y entre la marge physique
    d'imprimante et l'ouverture de la bande de frames, moins la garde. Seule la garde
    est un choix libre; les trois autres bornes sont des consequences.

    La bande de frames est lue **sur le spec** et non recalculee par orientation:
    depuis la v2 elle depend aussi du cardinal, et la recalculer ici jugerait
    l'emprise du QR contre une autre bande que celle qui a produit les zones.
    """
    clearance = spec.geometry.corner_clearance_mm()
    top = spec.geometry.printer_margin_mm
    return (
        clearance,
        top,
        spec.page_width_mm - 2 * clearance,
        spec.frame_band_mm["y"] - top - TOP_BAND_GUARD_MM,
    )


def footer_band_mm(spec: TemplateSpec) -> tuple[float, float, float, float]:
    """Bande **basse** du gabarit: celle du pied de page, QR ou non.

    Symetrique de :func:`header_band_mm`. Elle ouvre une garde sous la fermeture de la
    bande de frames et court jusqu'a la marge d'encre du bas.
    """
    clearance = spec.geometry.corner_clearance_mm()
    band = spec.frame_band_mm
    top = band["y"] + band["height"] + TOP_BAND_GUARD_MM
    return (
        clearance,
        top,
        spec.page_width_mm - 2 * clearance,
        spec.page_height_mm - spec.geometry.printer_margin_mm - top,
    )


def qr_band_mm(spec: TemplateSpec) -> tuple[float, float, float, float]:
    """Bande reservee au QR **sur le bord que le gabarit lui a retenu**.

    Les quatre bords ne se decrivent pas de la meme facon, et c'est la geometrie qui
    l'impose:

    * **haut** et **bas** -- la bande court entre les silences des marqueurs de coin, sur
      toute la hauteur laissee libre par la bande de frames. Le QR y partage l'espace
      avec un texte (l'entete en haut, le pied en bas), qui se pose **a cote** de lui;
    * **gauche** et **droit** -- la bande est le carre de l'emprise reservee, pose juste
      apres la colonne de pastilles et centre verticalement dans le couloir laisse libre
      par les silences des marqueurs. Elle ne court **pas** tout le flanc: la faire
      courir la ferait mordre les rangees de temoins de la variante haut/bas.

    La bande est carree sur un flanc et rectangulaire sur un bord horizontal; dans les
    deux cas `pdf_composition` y centre l'emprise **reelle** du payload et refuse
    bruyamment si elle deborde.
    """
    if spec.qr_edge == QR_EDGE_TOP:
        return header_band_mm(spec)
    if spec.qr_edge == QR_EDGE_BOTTOM:
        return footer_band_mm(spec)
    footprint = qr_footprint_bound_mm()
    geometry = spec.geometry
    clearance = geometry.corner_clearance_mm()
    free = geometry.lateral_free_height_mm(spec.orientation)
    if free >= footprint:
        # Le QR se **colle** a la marge d'encre, **sous** la colonne de pastilles: il
        # partage la bande d'abscisses de la colonne, donc il doit etre a une ordonnee
        # qu'aucune pastille n'atteint. Centre dans la hauteur libre, il reste clair de la
        # colonne au-dessus **et** du silence du marqueur du bas.
        offset = geometry.printer_margin_mm
        y = (spec.page_height_mm - clearance - free) + (free - footprint) / 2.0
    else:
        # Pas la hauteur libre: le QR se range **a cote** de la colonne, centre dans le
        # couloir laisse libre par les silences des marqueurs.
        offset = (geometry.patch_block_end_mm(spec.orientation)
                  + geometry.patch_to_band_gap_mm[spec.orientation])
        y = clearance + (spec.page_height_mm - 2 * clearance - footprint) / 2.0
    if spec.qr_edge == QR_EDGE_LEFT:
        x = offset
    else:
        x = spec.page_width_mm - offset - footprint
    return (x, y, footprint, footprint)


#: Noms des colonnes techniques du pied de page, dans l'ordre de remplissage.
FOOTER_TECHNICAL_ZONE_NAMES = tuple(
    f"footer_technical_{index + 1}" for index in range(FOOTER_TECHNICAL_COLUMNS)
)


def footer_technical_zone_name(index: int) -> str:
    """Nom de la ``index``-ieme colonne technique du pied de page."""
    return FOOTER_TECHNICAL_ZONE_NAMES[index]


def qr_reserved_zone_mm(spec: TemplateSpec) -> tuple[float, float, float, float]:
    """Emprise **reservee** au QR dans sa bande: le majorant, la ou le gabarit le pose.

    Une seule implementation pour trois consommateurs -- les zones reservees aux
    pastilles, le centrage de l'emprise reelle par la composition, et les tests
    d'emprise et de non-chevauchement. Deux recettes de placement divergeraient au
    premier changement, et le symptome serait une reservation qui a l'air d'une garde
    sans en etre une.

    Le rectangle rendu est la bande du QR retrecie a l'emprise reservee en **largeur**;
    sa hauteur reste celle de la bande, parce que c'est bien toute la hauteur de la bande
    qu'aucun autre element ne peut prendre.
    """
    band_x, band_y, band_w, band_h = qr_band_mm(spec)
    footprint = qr_footprint_bound_mm()
    if spec.qr_edge == QR_EDGE_BOTTOM:
        # Collee a droite: le pied de page occupe ce qui reste a gauche.
        x = band_x + band_w - footprint
    elif spec.qr_edge == QR_EDGE_TOP:
        # Centree sur la page, comme depuis la story 4.1 -- c'est ce qui garde une
        # planche v1 identique au dixieme de millimetre.
        x = spec.page_width_mm / 2.0 - footprint / 2.0
    else:
        x = band_x
    return (x, band_y, footprint, band_h)


def footer_zones_mm(spec: TemplateSpec) -> dict[str, tuple[float, float, float, float]]:
    """Zones du pied de page, **derivees de la geometrie du gabarit** (5.15, AC 4).

    Jusqu'au 2026-08-11 ces zones etaient deux litteraux figes par orientation dans
    `pdf_composition`. Sous la geometrie resserree le degagement de coin (28 mm) est
    **plus petit** que la hauteur du bloc d'identite (36,5 mm): les litteraux auraient
    pose le pied de page dans la bande rendue au dessin, sans qu'aucune etape n'echoue.

    La v1 conserve ses litteraux (`_LEGACY_FOOTER_ZONES_MM`), dont une planche deja
    imprimee depend et qui n'ont pas de formule.
    """
    legacy = _LEGACY_FOOTER_ZONES_MM.get(spec.geometry.version)
    if legacy is not None:
        return dict(legacy[spec.orientation])
    geometry = spec.geometry
    # Abscisse et largeur: entre les silences des marqueurs du bas, comme en v1 --
    # mais **derives** du degagement de coin plutot que recopies.
    x = geometry.corner_clearance_mm()
    width = spec.page_width_mm - 2 * x
    if spec.qr_edge == QR_EDGE_BOTTOM:
        # Le QR prend le bord bas: il se pose **a cote** du pied de page, pas
        # par-dessus. C'est la meme distinction qu'a la section 8.6 -- deux elements qui
        # doivent tenir cote a cote se somment, deux exigences qui se disputent le meme
        # espace se prennent en `max`. Le degagement du bord bas, lui, reste bien un
        # `max`: le pied et le QR partagent la **hauteur** de la bande basse, ils ne se
        # partagent que sa largeur.
        width -= qr_footprint_bound_mm() + TEXT_GAP_MM
    line_height = FOOTER_LINE_HEIGHT_MM
    line_y = spec.page_height_mm - geometry.printer_margin_mm - line_height
    # Hauteur du bloc: ce que le texte exige, au plancher typographique, jamais une
    # constante additive posee sur le degagement de coin.
    block_height = geometry.footer_block_height_mm()
    block_y = line_y - FOOTER_STACK_GAP_MM - block_height
    zones = {"footer_line": (x, line_y, width, line_height)}
    if not geometry.identity_in_header:
        zones["footer_block"] = (x, block_y, width, block_height)
        return zones
    # Disposition d'`EPIC5-ARB-63`: les identifiants residuels sur toute la largeur --
    # ils s'impriment **verbatim** et un identifiant canonique atteint 48 caracteres,
    # donc 81 mm au plancher de 8 pt -- puis la technique sur deux colonnes en dessous.
    identity_height = geometry.footer_identity_line_count() * body_line_leading_mm()
    technical_height = block_height - identity_height
    column_width = (width - (FOOTER_TECHNICAL_COLUMNS - 1) * TEXT_GAP_MM) / (
        FOOTER_TECHNICAL_COLUMNS)
    technical_y = block_y + identity_height
    zones["footer_block"] = (x, block_y, width, identity_height)
    for index in range(FOOTER_TECHNICAL_COLUMNS):
        zones[footer_technical_zone_name(index)] = (
            x + index * (column_width + TEXT_GAP_MM),
            technical_y,
            column_width,
            technical_height,
        )
    return zones



def mm_to_px(x_mm: float, y_mm: float, dpi: int) -> tuple[int, int]:
    """Convertir un point en millimetres vers des pixels au ``dpi`` donne.

    **Recette unique du depot** (story 5.2, AC 3). Elle vit ici plutot que dans
    ``layout`` parce que ce module est pur -- aucune dependance image -- alors
    que ``layout`` importe cv2: le chemin de detection du scan doit pouvoir
    convertir des millimetres sans tirer la pile de rendu. ``layout.mm_to_px``
    delegue desormais a cette fonction et reste appelable, ses consommateurs
    d'impression (``pdf_render``) et leurs tests etant inchanges.

    La politique d'arrondi est **exactement** celle d'avant le demenagement, et
    un test la verrouille par valeurs: l'impression et le scan consomment la
    meme fonction, et un arrondi qui divergerait entre les deux decalerait
    chaque crop d'un pixel a chaque bord sans jamais lever d'erreur.
    """
    px_per_mm = dpi / 25.4
    return int(round(x_mm * px_per_mm)), int(round(y_mm * px_per_mm))


def page_size_px(spec: TemplateSpec, dpi: int) -> tuple[int, int]:
    """Taille en pixels de la page **de ce template** au ``dpi`` donne.

    Contrairement a ``layout.page_size_px``, qui rend toujours 210x297: en
    paysage, l'espace de destination de l'homographie doit etre **transpose**,
    faute de quoi la page redressee est fausse -- silencieusement, pour 30
    templates sur 33.
    """
    return mm_to_px(spec.page_width_mm, spec.page_height_mm, dpi)


def corner_marker_centers_mm(spec: TemplateSpec) -> dict[int, tuple[float, float]]:
    """Centres des 4 marqueurs de coin du template, memes IDs et memes marges
    que ``layout.corner_marker_centers_mm`` (egalite verrouillee par test sur
    le template portrait).

    Lit la geometrie **du spec** et non les constantes du module: c'est ici que se
    joue la compatibilite de lecture d'une planche imprimee sous une version
    anterieure -- un scan qui chercherait les coins de la geometrie courante sur une
    page imprimee avec l'ancienne calculerait une homographie fausse en silence.
    """
    half = spec.geometry.marker_size_mm / 2
    near = spec.geometry.marker_margin_mm + half
    return {
        0: (near, near),
        1: (spec.page_width_mm - near, near),
        2: (spec.page_width_mm - near, spec.page_height_mm - near),
        3: (near, spec.page_height_mm - near),
    }


def frame_image_rect_mm(zone: dict, margin_mm: float) -> tuple[float, float, float, float]:
    """Rectangle utile de l'image dans une zone: le plus grand 16:9 centre
    dans la zone retiree de ``margin_mm`` sur ses quatre cotes.

    Pour ``margin_mm == 0`` l'image remplit exactement la zone. Le consommateur
    scan (story 5.3) recalcule ce meme rectangle depuis le template et le
    preset resolus du QR: une seule implementation, ici.
    """
    if margin_mm < 0:
        raise UnknownTemplateError(f"Marge negative invalide: {margin_mm}")
    inner_width = zone["width"] - 2.0 * margin_mm
    inner_height = zone["height"] - 2.0 * margin_mm
    if inner_width <= 0 or inner_height <= 0:
        raise UnknownTemplateError(
            f"La marge {margin_mm} mm ne laisse aucune surface utile dans la "
            f"zone {zone.get('name', '?')} ({zone['width']} x {zone['height']} mm)."
        )
    width = min(inner_width, inner_height * 16.0 / 9.0)
    height = width * 9.0 / 16.0
    x = zone["x"] + (zone["width"] - width) / 2.0
    y = zone["y"] + (zone["height"] - height) / 2.0
    return (x, y, width, height)


# --- Domination des mises en page (EPIC11-ARB-154, EPIC11-ARB-173) ----------
#
# Ces quatre fonctions vivent ici, **a cote du vocabulaire des cardinaux**
# (:func:`frames_per_page_vocabulary`), et non dans `tui/`: comparer deux
# geometries est une regle de vocabulaire de geometrie, au meme titre que le
# retrait d'un cardinal. `EPIC11-ARB-154` demande que la domination soit
# « calculee par le produit et **jamais recopiee** »; une seconde redaction dans
# une surface coincide le jour ou elle est ecrite et diverge a la premiere
# evolution de la geometrie, **sans qu'aucune etape n'echoue**. C'est la famille
# de defaut que ce depot a deja payee trois fois.
#
# Elles sont posees en fin de module et non juste sous le vocabulaire parce
# qu'elles consomment :func:`template_for` et :func:`frame_image_rect_mm`, tous
# deux definis plus bas; Python resout au moment de l'appel, mais un lecteur,
# non.


@dataclass(frozen=True)
class MiseEnPageMesuree:
    """Une mise en page candidate -- orientation x cardinal --, **mesuree**.

    Tout ce qu'un ecran de reglages affiche d'une ligne de sa liste, et rien de
    plus: la surface de dessin d'**une** frame (largeur, hauteur, et les deux
    surfaces derivees), les pages **par lot**, et le `template_id` qui a produit
    la mesure. Les nombres ne sont jamais recopies d'une table: ils sortent des
    zones du gabarit.
    """

    orientation: str
    frames_per_page: int
    template_id: str
    #: Largeur et hauteur, en mm, de la surface de dessin d'une frame -- le plus
    #: grand 16:9 inscrit dans la zone retiree de la marge, c'est-a-dire
    #: exactement le rectangle que le scan recalcule depuis le QR.
    largeur_mm: float
    hauteur_mm: float
    #: Nombre de planches **par lot**, dans l'ordre des lots recus. La somme est
    #: rendue par :attr:`pages`; c'est le tuple qui porte l'information, parce
    #: que l'arrondi se fait par lot et qu'un total ne le montre pas.
    pages_par_lot: tuple[int, ...]

    @property
    def cle(self) -> tuple[str, int]:
        """Le couple qui identifie une mise en page dans le produit."""
        return (self.orientation, self.frames_per_page)

    @property
    def surface_mm2(self) -> float:
        """Surface de dessin d'une frame, en mm²."""
        return self.largeur_mm * self.hauteur_mm

    @property
    def surface_cm2(self) -> float:
        """La meme surface en cm², l'unite que l'ecran affiche."""
        return self.surface_mm2 / 100.0

    @property
    def pages(self) -> int:
        """Total des planches de la passe, **somme des arrondis par lot**.

        Jamais `ceil(total des frames / cardinal)`: deux lots de 124 et 40
        frames a 3 frames par page font 42 + 14 = **56** planches, pas 55. Le
        papier ne se partage pas entre deux lots.
        """
        return sum(self.pages_par_lot)


def surface_de_dessin_mm(
    zones: tuple[dict, ...] | list[dict], margin_mm: float
) -> tuple[float, float]:
    """Largeur et hauteur, en mm, de la surface de dessin d'**une** frame.

    Chaque zone passe par :func:`frame_image_rect_mm` -- le plus grand 16:9
    inscrit dans la zone retiree de ``margin_mm`` sur ses quatre cotes --, et
    c'est la **plus petite** des surfaces obtenues qui est rendue: c'est la
    seule qu'un operateur puisse compter sur, quel que soit l'emplacement ou sa
    frame tombera sur la planche.

    Sur la geometrie v2 les zones d'un gabarit sont toutes de meme taille, et la
    mesure le dit (un test la refait sur les dix gabarits du vocabulaire et les
    trois presets de marge). Prendre la premiere zone rendrait donc aujourd'hui
    le meme nombre -- en le **supposant** au lieu de le mesurer, et en devenant
    faux en silence le jour ou une version composerait des zones inegales.

    **La grille n'est jamais deduite** (`AC 5.4`): ni `grid_columns`, ni
    `grid_rows`, ni `_grid_shape`, ni `_drawing_area_mm2` n'apparaissent ici.
    C'est cette deduction qui a melange les geometries v1 et v2 le 2026-09-01.
    Les zones sont **lues** au gabarit, et elles portent deja le resultat de la
    grille que ce gabarit-la a retenue.
    """
    plus_petite: tuple[float, float] | None = None
    for zone in zones:
        _x, _y, largeur, hauteur = frame_image_rect_mm(zone, margin_mm)
        if plus_petite is None or largeur * hauteur < plus_petite[0] * plus_petite[1]:
            plus_petite = (largeur, hauteur)
    if plus_petite is None:
        raise UnknownTemplateError(
            "Aucune zone de dessin: une mise en page sans emplacement ne rend "
            "aucune surface a comparer."
        )
    return plus_petite


def mesurer_les_mises_en_page(
    frames_par_lot: tuple[int, ...] | list[int],
    *,
    margin_preset: str = DEFAULT_MARGIN_PRESET,
    geometry_version: str = DEFAULT_GEOMETRY_VERSION,
) -> tuple[MiseEnPageMesuree, ...]:
    """Le **produit** des deux orientations par leur vocabulaire, mesure.

    ``frames_par_lot`` porte **un cardinal de frames par lot** de la passe, dans
    l'ordre des lots: c'est ce qui permet a l'arrondi de se faire par lot (voir
    :attr:`MiseEnPageMesuree.pages`). Une passe d'un seul lot ne distingue pas
    les deux formules et ne mesure donc rien de cette regle.

    **Le produit, et non l'orientation courante** (`EPIC11-ARB-154`): un ecran
    de reglages n'affiche qu'une orientation, mais une mise en page peut etre
    dominee par une combinaison de l'**autre** -- mesure sur cet arbre, paysage
    6f est domine par portrait 8f sur les deux criteres a la fois. Calculer sur
    la seule orientation affichee rendrait un glyphe faux, pas incomplet.

    La pagination est celle de :func:`pdf_composition.nombre_de_planches`,
    **jamais** une seconde redaction du `ceil`: c'est elle qui a pagine les
    planches deja imprimees, et un ecart entre les deux se lirait comme un
    chiffre juste. L'import est differe parce que `pdf_composition` importe ce
    module: la dependance est reelle et va dans ce sens-la, l'idiome est celui
    du depot (`scan_corrections`, `color_pipeline`, `patch_presets`).
    """
    from . import pdf_composition

    lots = tuple(frames_par_lot)
    mesures: list[MiseEnPageMesuree] = []
    for orientation in ORIENTATIONS:
        for cardinal in frames_per_page_vocabulary(orientation, geometry_version):
            spec = template_for(
                orientation, cardinal, margin_preset, geometry_version)
            largeur_mm, hauteur_mm = surface_de_dessin_mm(
                spec.frame_zones_mm, spec.margin_mm)
            mesures.append(
                MiseEnPageMesuree(
                    orientation=orientation,
                    frames_per_page=cardinal,
                    template_id=spec.template_id,
                    largeur_mm=largeur_mm,
                    hauteur_mm=hauteur_mm,
                    pages_par_lot=tuple(
                        pdf_composition.nombre_de_planches(frames, cardinal)
                        for frames in lots
                    ),
                )
            )
    return tuple(mesures)


def domine(candidate: MiseEnPageMesuree, autre: MiseEnPageMesuree) -> bool:
    """``candidate`` domine ``autre``: **surface >= ET pages <=**, au moins une stricte.

    Les deux criteres vont en sens opposes -- on veut la plus grande surface de
    dessin et le moins de papier --, donc « faire au moins aussi bien » est un
    ``>=`` d'un cote et un ``<=`` de l'autre.

    **L'inegalite stricte n'est pas un raffinement, c'est ce qui rend la
    relation utilisable.** Sans elle toute mise en page se dominerait
    elle-meme, l'ensemble des non dominees serait vide, et l'ecran n'aurait
    aucun glyphe a poser. C'est aussi ce qui dispense d'exclure ``candidate is
    autre`` a l'appel: une mise en page ne fait jamais strictement mieux
    qu'elle-meme. Deux mises en page de surface **et** de pages egales ne se
    dominent pas non plus, dans aucun sens.
    """
    au_moins_aussi_bien = (
        candidate.surface_mm2 >= autre.surface_mm2
        and candidate.pages <= autre.pages
    )
    strictement_mieux = (
        candidate.surface_mm2 > autre.surface_mm2
        or candidate.pages < autre.pages
    )
    return au_moins_aussi_bien and strictement_mieux


@dataclass(frozen=True)
class BilanDeDomination:
    """Le produit mesure, et **qui domine qui**.

    Un ecran lit ce bilan; il ne refait aucune comparaison. Les dominants d'une
    entree sont ce que la ligne « ▲ N frames <orientation> est plus optimal »
    nomme -- le seul endroit ou une combinaison de l'autre orientation
    apparait.
    """

    #: Le produit, dans l'ordre de :func:`mesurer_les_mises_en_page`.
    mises_en_page: tuple[MiseEnPageMesuree, ...]
    #: Pour **chaque** cle du produit, ses dominants, dans le meme ordre. Une
    #: entree non dominee y figure avec un tuple vide: l'absence de dominant se
    #: lit, elle ne se deduit pas d'une cle manquante.
    dominants: Mapping[tuple[str, int], tuple[MiseEnPageMesuree, ...]]

    def de(self, orientation: str, frames_per_page: int) -> MiseEnPageMesuree:
        """La mesure de cette mise en page, ou un refus explicite."""
        for mise in self.mises_en_page:
            if mise.cle == (orientation, frames_per_page):
                return mise
        raise UnknownTemplateError(
            f"Mise en page hors du produit mesure: {orientation} "
            f"{frames_per_page}f."
        )

    def dominants_de(
        self, orientation: str, frames_per_page: int
    ) -> tuple[MiseEnPageMesuree, ...]:
        """Les mises en page qui dominent celle-ci, dans l'ordre du produit."""
        self.de(orientation, frames_per_page)
        return self.dominants[(orientation, frames_per_page)]

    def est_dominee(self, orientation: str, frames_per_page: int) -> bool:
        """Vrai si au moins une autre mise en page fait mieux sur les deux criteres."""
        return bool(self.dominants_de(orientation, frames_per_page))

    def non_dominees(self) -> tuple[MiseEnPageMesuree, ...]:
        """Les mises en page que le glyphe `●` marque, dans l'ordre du produit."""
        return tuple(
            mise for mise in self.mises_en_page if not self.dominants[mise.cle]
        )

    def de_l_orientation(self, orientation: str) -> tuple[MiseEnPageMesuree, ...]:
        """La liste d'un ecran: une orientation, dans l'ordre du vocabulaire.

        **Aucune entree n'est retiree** (`EPIC11-ARB-154`, « on guide, on
        n'interdit pas »): la liste est exactement le vocabulaire de cette
        orientation, dominees comprises.
        """
        return tuple(
            mise for mise in self.mises_en_page if mise.orientation == orientation
        )


def dominants_des_mises_en_page(
    mises_en_page: tuple[MiseEnPageMesuree, ...] | list[MiseEnPageMesuree],
) -> dict[tuple[str, int], tuple[MiseEnPageMesuree, ...]]:
    """Pour chaque mise en page recue, celles qui la dominent.

    Comparaison **pure**: aucune geometrie n'est relue ici, ce qui permet de la
    mesurer sur une fabrique dont on choisit les positions. L'ordre du produit
    recu est preserve -- ni tri, ni filtre --, donc la position d'une cible dans
    une fabrique est bien celle que ce code parcourt.
    """
    produit = tuple(mises_en_page)
    vues: set[tuple[str, int]] = set()
    for mise in produit:
        if mise.cle in vues:
            raise UnknownTemplateError(
                f"Mise en page presente deux fois dans le produit: "
                f"{mise.orientation} {mise.frames_per_page}f. Un produit qui "
                "porte deux fois la meme cle rendrait un bilan dont la moitie "
                "est inatteignable."
            )
        vues.add(mise.cle)
    return {
        mise.cle: tuple(autre for autre in produit if domine(autre, mise))
        for mise in produit
    }


def bilan_de_domination(
    frames_par_lot: tuple[int, ...] | list[int],
    *,
    margin_preset: str = DEFAULT_MARGIN_PRESET,
    geometry_version: str = DEFAULT_GEOMETRY_VERSION,
) -> BilanDeDomination:
    """Mesurer le produit des deux orientations, puis le comparer a lui-meme.

    C'est le seul point d'entree qu'une surface appelle: elle ne mesure pas
    d'un cote et ne compare pas de l'autre.
    """
    mises_en_page = mesurer_les_mises_en_page(
        frames_par_lot,
        margin_preset=margin_preset,
        geometry_version=geometry_version,
    )
    return BilanDeDomination(
        mises_en_page=mises_en_page,
        dominants=dominants_des_mises_en_page(mises_en_page),
    )


# ===========================================================================
# Le REPLI de cardinal -- `EPIC11-ARB-179`, tranche par Egan le 2026-09-02
# ===========================================================================
#
# **Il n'existe qu'au basculement d'orientation, et il vit ICI.**
#
# Le coeur ne replie AUCUN cardinal de lui-meme: `build_template_id` refuse un
# couple hors vocabulaire, avec un motif nomme. La ligne de commande recoit
# l'orientation et le cardinal **ensemble**, donc elle n'a rien a deviner et ce
# refus est le bon comportement. La seule surface qui ait un cardinal deja
# choisi quand l'orientation change est la TUI -- c'est le seul declencheur du
# repli.
#
# **La regle est ecrite une fois, a cote du vocabulaire** (AC 5.6 de la story
# 11.7): une frontiere a l'AST mesure qu'aucun module de `tui/` ne calcule une
# distance entre cardinaux. Un ecran lit le resultat; il ne le recalcule pas.


@dataclass(frozen=True)
class RepliDeCardinal:
    """Ce qu'un basculement d'orientation retient, et ce qu'il avait demande.

    Deux entiers plutot qu'un seul, et ce n'est pas du confort: une surface qui
    ne recevrait que le cardinal retenu ne pourrait pas dire **qu'il y a eu**
    un repli sans le recalculer -- c'est-a-dire sans reecrire ici la regle que
    ce module tient. :attr:`a_replie` repond a la question a sa place.
    """

    orientation: str
    #: Le cardinal que l'operateur avait choisi avant de basculer.
    demande: int
    #: Le cardinal offert dans la nouvelle orientation, qui le remplace.
    retenu: int

    @property
    def a_replie(self) -> bool:
        """Vrai quand le cardinal demande n'etait pas offert et a ete remplace."""
        return self.retenu != self.demande


def replier_le_cardinal(
    orientation: str, cardinal: int, geometry_version: str | None = None
) -> RepliDeCardinal:
    """Le cardinal retenu quand ``cardinal`` bascule vers ``orientation``.

    **Le repli MONTE** (`EPIC11-ARB-179`, verbatim d'Egan: « On economise le
    papier. »): le cardinal indisponible est remplace par le cardinal offert
    **immediatement superieur**, jamais par le plus proche. Les deux cas du
    depot, et il n'y en a que deux -- `3` portrait bascule en paysage rend `4`
    (62 planches -> 31 sur un lot de 124), `6` paysage bascule en portrait rend
    `8` (31 -> 16).

    **Monter n'etait pas evident, et ce que ca coute est mesure**: `4` paysage
    offre 29 % de surface de dessin en moins par frame que `3` portrait. Egan a
    tranche en connaissance de ce chiffre.

    **Ce qui rend la regle sure plutot que seulement simple**: sur le second
    cas, :func:`retired_cardinal_reason` nomme deja `8` comme remplacant de `6`
    en portrait. Deux raisonnements independants -- monter, et le motif du
    retrait -- rendent le meme cardinal. Un test mesure cette coincidence
    plutot que de la supposer.

    Un cardinal **deja offert** se rend lui-meme: il n'y a alors pas de repli,
    et :attr:`RepliDeCardinal.a_replie` est faux. C'est ce qui permet a un ecran
    d'appeler cette fonction a **chaque** basculement, sans avoir a decider
    lui-meme s'il y a lieu de replier.

    **Aucun cardinal offert au-dessus: cette fonction REFUSE, elle ne devine
    pas.** `EPIC11-ARB-179` dit explicitement que ce cas « ne se presente pas
    aujourd'hui » et qu'il est « a poser explicitement le jour ou ca arrive,
    plutot que de laisser un `max()` decider en silence ». Un repli vers le bas
    serait exactement ce `max()` silencieux -- il renverserait la regle
    « on economise le papier » sans qu'aucune decision ne l'ait dit. Le refus
    porte donc le nom de l'arbitrage, pour que le jour venu la trace mene a la
    question plutot qu'a du code.

    Ce refus est **injoignable sur les geometries livrees**, et c'est mesure:
    `8` est le plus grand cardinal des deux vocabulaires de chaque version, donc
    tout cardinal indisponible dans une orientation a un superieur offert. Une
    frontiere balaie le produit entier des versions, des orientations et des
    vocabulaires et rougirait le jour ou une geometrie ferait tomber cette
    propriete -- **avant** qu'un ecran ait a l'affronter.
    """
    vocabulaire = frames_per_page_vocabulary(orientation, geometry_version)
    if cardinal in vocabulaire:
        return RepliDeCardinal(
            orientation=orientation, demande=cardinal, retenu=cardinal)
    superieurs = tuple(offert for offert in vocabulaire if offert > cardinal)
    if not superieurs:
        raise UnknownTemplateError(
            f"Aucun cardinal offert au-dessus de {cardinal} en {orientation} "
            f"(vocabulaire: {', '.join(str(o) for o in vocabulaire)}). "
            "EPIC11-ARB-179 fait MONTER le repli au cardinal offert "
            "immediatement superieur et ne dit PAS ce qu'il faut faire quand "
            "il n'y en a aucun: le cas est a trancher, pas a deviner. "
            "Descendre ici renverserait la regle « on economise le papier » "
            "sans qu'aucune decision ne l'ait dit."
        )
    return RepliDeCardinal(
        orientation=orientation, demande=cardinal, retenu=min(superieurs))
