"""QR page payload contract for the MMU reconstruction chain.

Story 2.3 defines the minimal, versioned payload embedded in the QR code
printed on each patch sheet page. The payload is the reconstruction source of
truth for a third party: it must be enough, on its own, to identify the
project/rush/lot, the page position, the target frame rate/colorspace and the
`slot_index -> frame_timecode` mapping for every frame slot printed on that
page.

Serialization keeps the payload as plain, uncompressed, human-readable JSON
(compact separators only) so it stays debuggable in the field, per
ARCHITECTURE_DETAILED.md section 6.

Deux formes, une seule table (story 5.17, `EPIC5-ARB-60`)
---------------------------------------------------------
Depuis le schema `2.0`, ce que le QR **porte** n'est pas ce que le depot
manipule: le dictionnaire en memoire garde ses noms longs (`rush_id`,
`target_colorspace`...) et la serialisation les projette sur des **cles
courtes** de deux a trois caracteres (`rid`, `tcs`...) par la table unique
`PAYLOAD_SHORT_KEYS`. La relecture applique l'inverse, par la meme table, de
sorte qu'une boucle rende le dictionnaire d'origine a l'identique.

Motif du choix: 256 octets gagnes au pire cardinal (698 -> 442), ce qui fait
repasser tous les cardinaux sous le budget nominal et sort le QR d'une page a
8 frames du regime de symbole que le detecteur de production ne decode pas.
Motif de la **frontiere** -- projeter a l'ecriture plutot que raccourcir
partout: la reconstruction, le scan et les manifests sont ecrits contre les
noms longs, et les raccourcir aurait echange ces 256 octets contre un depot
illisible.

Consequence assumee, sans lecteur bi-format: une planche imprimee sous `1.0`
n'est plus relisible. **Depuis la story 2.7** (payload `2.1`, `EPIC7-ARB-56`:
« la branche de lecture 1.0 est supprimee dans le meme geste »), `parse_payload`
la rend `PayloadVersionMissing` -- son format a cles longues ne porte jamais la
cle courte `sv` que ce lecteur exige, donc elle tombe desormais dans le meme
refus qu'un QR etranger. Ce n'etait pas le cas avant cette story:
`PayloadSchemaVersionRefused` la distinguait alors, en la nommant « planche
perimee, a reimprimer » -- exact au regard du parc, aucune planche `1.0` n'ayant
jamais ete imprimee hors materiel de test.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from ..numeric_guards import is_strict_int
from ..page_roles import (  # noqa: F401  (re-exporte le vocabulaire du contrat)
    PAGE_ROLE_CALIBRATION,
    PAGE_ROLE_IMAGES,
    PAGE_ROLES,
    page_role_label,
    validate_page_role,
)


#: Version du schema **imprime**. Passee de `1.0` a `2.0` par la story 5.17
#: (`EPIC5-ARB-60`): les cles du payload sont raccourcies, donc le format change et
#: aucune planche imprimee sous `1.0` n'est relisible. Il n'y a **pas** de lecteur
#: bi-format, par decision d'Egan -- seul du materiel de test a ete imprime, et deux
#: chemins de lecture se paieraient a chaque evolution ulterieure du payload.
#:
#: **Passee de `2.0` a `2.1` par la story 2.7** (`EPIC7-ARB-56`, jalon de gel du
#: format `EPIC7-ARB-51`, ~2026-09-02): le payload gagne `timecode_base_fps`, requis
#: sur une planche d'images. Le champ n'a **aucun** defaut juste a la relecture --
#: deviner une cadence source est exactement ce que la story 6.6 interdit -- donc le
#: bump de version est ce qui le rend exigible sans violer « une planche imprimee
#: reste relisible » (meme regle que `page_role`, prise cette fois par la version
#: plutot que par un defaut). Dans le meme geste, la branche de lecture `1.0` est
#: **supprimee** (`EPIC7-ARB-56`: « la branche de lecture 1.0 est supprimee dans le
#: meme geste »): un QR a cles longues (l'ancien format `1.0`) tombe desormais dans
#: `PayloadVersionMissing`, pas dans un refus de planche perimee -- ce qui est exact
#: au regard du parc, aucune planche `1.0` n'ayant jamais ete imprimee hors
#: materiel de test.
PAYLOAD_SCHEMA_VERSION = "2.1"

# QR payload size guard-rails from ARCHITECTURE_DETAILED.md section 6: a
# nominal soft budget to aim for, and a hard ceiling that must never be
# exceeded so the printed QR code stays reliably scannable.
NOMINAL_BUDGET_BYTES = 512
ALERT_BUDGET_BYTES = 768

#: Nom long du libelle de chaine de scan porte par le payload du role `c`.
SCAN_CHAIN_LABEL_FIELD = "scan_chain_label"

#: Longueur maximale du libelle de chaine de scan, en caracteres (story 5.23).
#:
#: **Deux bornes se rencontrent ici, et c'est la plus serree qui commande. La reponse
#: a change une fois: elle est mesuree, pas raisonnee.**
#:
#: 1. *Le QR*, ou chaque caractere coute un octet -- meme raisonnement que
#:    `GAMUT_MAP_ID_MAX_LENGTH`. Pire cas mesure sur le chemin de production (page de
#:    calibration, gabarit et preset aux identifiants les plus longs, aucun
#:    emplacement, `target_colorspace` de 9 caracteres): **245 octets** a 96 caracteres
#:    de libelle, soit 48 % du budget nominal de 512 et 32 % du plafond de 768; symbole
#:    de **65 modules**, loin de la version bannie 22 (105 modules), geometrie
#:    `reliable` et aucun avertissement. Le QR ne devient pas la borne avant plusieurs
#:    centaines de caracteres.
#: 2. *L'entete imprime*, qui reste la borne. Les mentions de la page s'impriment
#:    **verbatim** (`pdf_composition._require_verbatim`) au plancher de police de 8 pt,
#:    dans une bande dont la hauteur se paie en cellules reprises au treillis: la
#:    grille ne finance que **21 cellules** de mobilier, soit **2 rangees** en portrait
#:    -- l'orientation par defaut --, soit **5 lignes de 86 caracteres**.
#:
#: La borne est donc le **nombre total de lignes** que les mentions exigent au pire
#: cas: projet de 48 caracteres, libelle et commentaire **sans aucune espace** donc
#: insecables, date de generation comprise. A (96, 72) les mentions tiennent
#: exactement dans les 5 lignes financees; a (104, 72) comme a (96, 80) elles en
#: exigent 6. Un test epingle les deux bouts.
#:
#: **Ce que la valeur a coute en route**, parce que le chemin explique le chiffre. La
#: premiere redaction posait 64, sous une regle plus stricte -- « une mention qui tient
#: dans une ligne n'est jamais coupee », donc le bloc « Chaine de scan : <libelle> »
#: devait rester sous les 86 caracteres de la bande, soit 69 au plus, arrondi a 64.
#: Elle reste la borne de **lisibilite**: au-dela de 69, un libelle sans espace est
#: reporte a la ligne suivante du prefixe qui l'annonce. Ce n'est pas une troncature et
#: rien n'est perdu, seulement moins joli -- et Egan a demande un maximum
#: **confortable**, ce que 64 n'etait pas (son propre exemple en fait deja 39).
SCAN_CHAIN_LABEL_MAX_LENGTH = 96


#: Champs que **seul** le role `c` porte (story 5.23). Symetrique exact de
#: `CALIBRATION_ABSENT_FIELDS`: la meme table dit ce qu'une page de calibration n'a
#: pas et ce qu'elle est seule a avoir, donc les deux refus se lisent au meme
#: endroit et ne peuvent pas diverger.
_CALIBRATION_ONLY_FIELDS: tuple[str, ...] = (SCAN_CHAIN_LABEL_FIELD,)
CALIBRATION_ONLY_FIELDS: frozenset[str] = frozenset(_CALIBRATION_ONLY_FIELDS)

#: Nom du champ de rang de version de la PLANCHE (`EPIC11-ARB-91`, 2026-08-31).
VERSION_RANK_FIELD = "version_rank"

#: Champs **facultatifs** du payload -- troisieme famille, a cote des champs de
#: toute page et des champs du seul role `c`.
#:
#: `version_rank` est le premier de cette famille, et la famille existe pour lui.
#: Il ne pouvait entrer dans aucune des deux autres: le rendre requis aurait
#: refuse **toute planche deja imprimee** (aucune ne le porte), et le reserver a
#: un role n'a pas de sens puisqu'il s'applique aux planches d'images.
#:
#: **Absent vaut rang 1** (verbatim d'Egan, 2026-08-31: « les anciens payloads
#: qui ne portaient pas de version (2.1) sont tout de meme decodes avec v=1 »).
#: Ce defaut ROMPT avec le precedent du depot -- `EPIC7-ARB-56` monte la version
#: de schema et supprime la branche de lecture ancienne --, et il faut qu'il le
#: rompe: applique ici, ce precedent aurait rendu illisible tout le parc de
#: planches deja sur papier. Il est de surcroit EXACT et non complaisant: une
#: planche sans le champ et une planche neuve de rang 1 designent la meme chose,
#: elles doivent etre indistinguables. C'est le regime deja retenu pour
#: `lots[].version_rank` au manifeste, donc une seule convention pour le meme
#: fait a deux endroits, et non deux.
_OPTIONAL_SCALAR_FIELDS: tuple[str, ...] = (VERSION_RANK_FIELD,)
OPTIONAL_SCALAR_FIELDS: frozenset[str] = frozenset(_OPTIONAL_SCALAR_FIELDS)

#: Les champs de la charge utile que `sheets_pdf_filename_from_payload` consomme
#: pour reconstruire le nom d'un tirage (`EPIC11-ARB-178`).
#:
#: Table plutot que quatre litteraux au point d'usage, et le motif est celui du
#: depot: c'est le **contrat** de la reconstruction inverse -- « voici ce que le
#: papier doit porter pour qu'on sache d'ou il vient » --, et un banc le
#: confronte en ensemble EXACT a la signature de `build_sheets_pdf_filename`.
#: `version_rank` n'y figure pas: il est OPTIONNEL par `EPIC11-ARB-91`, et
#: `payload_version_rank` repond pour lui.
_SHEETS_NAME_PAYLOAD_FIELDS: tuple[str, ...] = (
    "project_id",
    "rush_id",
    "lot_id",
    "template_id",
)

#: Bornes du rang, LUES a `io.naming` et jamais recopiees: deux emplacements
#: pour le meme fait sont deux verites (`EPIC5-ARB-78`).
#:
#: **Ce commentaire a d'abord surmonte deux litteraux `2` et `99`** -- il
#: affirmait exactement ce qu'il ne faisait pas. Mesure de la revue: porter
#: `naming.VERSION_RANK_MAX` a 50 laissait `payload` accepter le rang 99 que
#: le NOM refusait alors, et les 32 tests du banc restaient verts. La forme
#: correcte etait deja dans le depot, a `io/extraction_manifest.py`.
from .naming import VERSION_RANK_MAX, VERSION_RANK_MIN  # noqa: E402

#: Le module lui-meme, pour `sheets_pdf_filename_from_payload` (`EPIC11-ARB-178`):
#: elle **appelle** le constructeur de noms de tirages plutot que d'en recopier la
#: convention, et un banc mesure que changer l'un change l'autre.
from . import naming  # noqa: E402

#: La regle du versionnage vit dans `io/version_ranks.py`, ecrite une fois pour
#: tous les objets versionnables (`EPIC11-ARB-108`): le rang d'origine s'y lit,
#: il ne se recopie pas en litteral.
from .version_ranks import RANG_ORIGINE  # noqa: E402

# Field order mirrors the "Payload recommande" list in
# ARCHITECTURE_DETAILED.md section 6, kept stable for readability/debugging.
_REQUIRED_SCALAR_FIELDS = (
    "schema_version",
    "project_id",
    "rush_id",
    "lot_id",
    "page_index",
    "page_count",
    # --- page_role (story 5.16, EPIC5-ARB-54) ---------------------------------
    #
    # Douzieme champ scalaire, et le seul de **niveau page** en dehors du couple
    # d'indexation: il est pose ici, a cote de `page_index`, parce que c'est ce
    # qu'il est. Il ne peut pas etre de niveau lot -- `template_id`,
    # `patch_preset_id` et `page_count` le sont, et l'invariant d'identite de lot
    # refuse deux pages qui les declarent differents; declarer le role par l'un
    # d'eux aurait donc scinde un tirage en deux lots au lieu de decrire deux
    # pages du meme lot (mesure a l'execution, story 5.16, AC 3).
    #
    # Cout mesure: 9 octets, uniformement sur les six cardinaux -- voir
    # `page_roles` pour le regime, le pire cas et les deux pieges (non-monotonie
    # de la version de symbole, table de cles contractuelle).
    "page_role",
    "fps_target",
    # --- timecode_base_fps (story 2.7, EPIC7-ARB-56, payload 2.1) -------------
    #
    # Treizieme champ scalaire: la cadence SOURCE du rush, a cote de sa voisine
    # `fps_target` (la cadence CIBLE) parce que c'est la meme grandeur physique --
    # une cadence -- lue a deux endroits differents de la chaine. Chaine
    # rationnelle exacte `num/den`, jamais un flottant: c'est la forme que le
    # manifest porte deja (`lots[].timecode_base_fps`, produite par
    # `codec_profiles.exact_frame_rate`) et que `encode.resolve_source_rate`
    # attend verbatim.
    #
    # Requis sur une planche d'images, **sans** entree dans `REREAD_DEFAULTS`: le
    # bump de version a `2.1` est ce qui rend ce champ exigible sans violer « une
    # planche imprimee reste relisible » -- il n'a, a la difference de
    # `page_role`, aucun defaut juste: deviner une cadence source est exactement
    # l'interdit que la story 6.6 pose (`EPIC6-ARB-6`).
    "timecode_base_fps",
    "template_id",
    "patch_preset_id",
    "target_colorspace",
    "gamut_map_id",
)

# --- gamut_map_id (story 5.9, EPIC5-ARB-13 / ARB-11) ------------------------
#
# Onzieme champ scalaire, **obligatoire des le depart**: rien n'a ete imprime
# en usage reel, donc il n'y a aucune compatibilite ascendante a construire.
# Consequence assumee et ecrite: pas de bump de `PAYLOAD_SCHEMA_VERSION`, pas
# de normalisation au parsing, pas de valeur par defaut injectee a la lecture,
# aucune branche « champ absent » nulle part. `gamut-map-none-1` (l'identite)
# est une valeur valide de premier rang, pas un cas degrade.
#
# La longueur maximale est une **contrainte de contrat**, pas une
# recommandation (EPIC5-ARB-11 point 11c). Le fragment JSON
# `,"gamut_map_id":"<id>"` coute 18 + longueur de l'identifiant. Justification
# chiffree: le seul regime ou le plafond dur de 768 octets est encore
# atteignable sans avoir deja ete depasse est celui des identifiants longs a
# 6 slots (717 octets sans le champ); la borne arithmetique y serait de 33
# caracteres (717 + 18 + 33 = 768) et ne laisserait **aucune** marge a une
# evolution ulterieure du payload, tandis que 24 coute au plus 42 octets et en
# laisse 9. Et 24 suffit au format: `gamut-map-` (10) + nom (<= 11) + `-` (1)
# + version (<= 2) -- `gamut-map-none-1` en consomme 16,
# `gamut-map-perceptual-1` 22.
GAMUT_MAP_ID_PREFIX = "gamut-map-"
GAMUT_MAP_ID_MAX_LENGTH = 24

#: Champs du contrat qui ont un **defaut a la relecture**, et eux seuls.
#:
#: **Regle du depot, ecrite ici parce que c'est ici qu'elle s'applique: une planche
#: imprimee doit rester relisible.** Un champ **requis** ajoute sous une version de
#: schema deja posee viole cette regle -- une planche imprimee avant l'ajout leve
#: `PayloadValidationError` avec un message qui dit « champ requis manquant », donc qui
#: envoie diagnostiquer un QR abime la ou la feuille est simplement anterieure au champ.
#: C'est le majeur M3 de la couche 3 de la revue de 5.16: `page_role` avait ete ajoute
#: comme requis sous la **meme** chaine `2.0` que 5.17 venait de poser.
#:
#: Deux issues existaient -- une version de schema `2.1`, ou un defaut a la relecture --
#: et c'est la seconde qui est retenue, parce que le champ **a** un defaut sur lequel il
#: n'y a rien a arbitrer: une planche anterieure au role est une planche d'images, il n'en
#: existait pas d'autre. Le defaut ne s'applique **qu'a l'absence complete du champ**: une
#: valeur presente et hors vocabulaire, vide ou nulle reste un refus, parce que c'est
#: alors un champ abime et non une feuille ancienne.
#:
#: L'asymetrie avec `gamut_map_id` juste au-dessus est deliberee et tient a la direction de
#: la faute, la meme que celle de `build_page_payload`: un defaut `gamut-map-none-1` serait
#: *juste aujourd'hui et faux demain*, en silence, alors que `PAGE_ROLE_IMAGES` est le
#: regime **strict** -- un defaut faux se fait refuser par la garde d'emplacements.
REREAD_DEFAULTS: Mapping[str, Any] = MappingProxyType({
    "page_role": PAGE_ROLE_IMAGES,
})

#: Identite: aucune compression de gamut appliquee. Valeur de premier rang, et
#: la seule que `makepdf` emet au MVP -- l'implementation de `G` appartient a
#: la story 5.10, le choix de `G^-1` a 5.4.
GAMUT_MAP_IDENTITY = "gamut-map-none-1"

#: `gamut-map-<nom>-<version>`, ASCII minuscule. Le nom et la version sont
#: separes par le dernier tiret; le nom ne peut pas etre vide.
_GAMUT_MAP_ID_PATTERN = re.compile(r"^gamut-map-[a-z0-9]+(?:-[a-z0-9]+)*-[0-9]+$")
_REQUIRED_SLOT_FIELDS = ("slot_index", "frame_timecode")

#: `num/den`, deux entiers separes par une barre, denominateur toujours explicite
#: (story 2.7): c'est la forme que `codec_profiles.exact_frame_rate` produit et
#: accepte deja verbatim. Local a ce module (AC 1: `io.payload` n'importe que
#: `page_roles`, et cette legerete est un choix du module -- il ne verifie que la
#: FORME, l'exactitude de la valeur appartient a l'appelant qui la lit du manifest).
_TIMECODE_BASE_FPS_PATTERN = re.compile(r"^[0-9]+/[0-9]+$")


# --- Table de correspondance des cles courtes (story 5.17, EPIC5-ARB-60) ----
#
# **Une seule table**, consommee par la serialisation et par le parsing. Deux tables
# qui divergent est le defaut ferme en revue de 3.5, et ici la divergence serait
# silencieuse a l'ecriture et fatale a la relecture: un QR imprime avec un `rid` que
# le parseur lirait `rd` n'est plus decodable du tout, et le papier ne se corrige pas.
#
# Elle est **plate**: les deux champs d'emplacement (`slot_index`, `frame_timecode`)
# y cohabitent avec les champs scalaires parce que les deux jeux de noms sont
# disjoints -- une seule table suffit donc a projeter le document entier, niveau
# racine et emplacements compris.
#
# **Deux a trois caracteres, jamais une lettre.** Choix assume: descendre a une
# lettre par champ gagne environ 15 octets de plus et rend illisible un payload
# decode a la main lors d'un diagnostic. C'est un mauvais echange -- ce payload
# voyage imprime sur du papier, et le seul outil garanti sur place est un oeil.
#
# Gain mesure en serialisant un payload reel: 96 octets sur les champs scalaires et
# 20 octets par emplacement -- deux grandeurs qui, elles, ne dependent d'aucun regime,
# etant la somme des ecarts de longueur de la table (test dedie).
#
# **Les octets, eux, dependent du regime, et il est nomme** (revue de 5.17, majeur M6):
# 362 -> 246 au cardinal 1 et 698 -> 442 au cardinal 8 valent dans le **regime de banc**
# de `tests/unit/test_payload_short_keys.payload_for` -- les trois identifiants du projet
# de demonstration (`projet_demo` / `planche_4f_heteroclite` /
# `planche_4f_heteroclite_4`), mais le gabarit `tpl-a4-portrait-2f-v1`, le preset
# `patches-12-v1`, `bt709` et `fps_target = 24.0`. Ce n'est donc pas « le vrai payload de
# production », et le balayage des cardinaux n'est pas une page: `tpl-a4-portrait-2f-v1`
# n'a que **deux** zones de dessin et ne peut pas porter 8 emplacements. On mesure ici le
# poids d'une charge utile, pas la composabilite d'une planche.
#
# Les deux mesures de terrain qui l'encadrent, prises pour eviter de relire ces
# chiffres comme ceux d'une page reelle:
#   * sous le contenu **reel** du lot `planche_4f_heteroclite_4`
#     (`tpl-a4-paysage-4f-v1`, `patches-18-v2`, `rec709`, `fps 4.0`): 361 -> 245 au
#     cardinal 1, 505 -> 329 a son cardinal reel de 4, 697 -> 441 au cardinal 8;
#   * sur les douze gabarits qui portent reellement 8 frames
#     (`tpl-a4-paysage-8f-m2-v1` et suivants): 700 -> 444 au cardinal 8.
# Les trois valeurs (441, 442, 444) sont sous les 512 du budget nominal et encodent
# toutes sur 85 modules, donc rien n'en depend en aval -- c'est la phrase qui les
# annoncait, pas les chiffres, qui etait fausse.
PAYLOAD_SHORT_KEYS: Mapping[str, str] = MappingProxyType({
    "schema_version": "sv",
    "project_id": "pid",
    "rush_id": "rid",
    "lot_id": "lid",
    "page_index": "pi",
    "page_count": "pc",
    # Story 5.16: un champ nouveau **s'ajoute a la table**, il ne se glisse pas
    # dans un payload -- `_rename_keys` refuse toute cle qui n'y est pas, et c'est
    # la garde voulue. Deux caracteres comme ses voisins d'indexation.
    "page_role": "pr",
    "fps_target": "fps",
    # Story 2.7 (EPIC7-ARB-56): la cadence SOURCE du rush, cle courte de trois
    # caracteres comme `patch_preset_id` -> `ppi`, initiales de `timecode_base_fps`.
    "timecode_base_fps": "tbf",
    "template_id": "tid",
    "patch_preset_id": "ppi",
    "target_colorspace": "tcs",
    "gamut_map_id": "gmi",
    # Story 5.23 (correction d'Egan du 2026-08-18): le libelle de la chaine de scan
    # entre dans le payload du role `c`. Meme recette que ses voisins -- initiales du
    # nom long, trois caracteres, ASCII minuscule, comme `patch_preset_id` -> `ppi`.
    # Il n'est **pas** dans `_REQUIRED_SCALAR_FIELDS`: ce n'est pas un champ de toute
    # page mais un champ **du seul role `c`** (`CALIBRATION_ONLY_FIELDS`), symetrique
    # de `CALIBRATION_ABSENT_FIELDS` juste en face.
    "scan_chain_label": "scl",
    # `EPIC11-ARB-91` (Egan, 2026-08-31): le rang de version de la PLANCHE.
    #
    # `vr` et non `v`, bien qu'Egan ait ecrit « v pour version ». Il nommait le
    # SENS du champ, pas sa longueur, et la table a sur ce point une convention
    # deliberee que l'AC 1 de la story 5.17 mesure: deux a trois caracteres,
    # jamais une lettre par champ. Son motif tient ici mieux qu'ailleurs -- ce
    # payload voyage IMPRIME, et le seul outil garanti sur place est un oeil.
    # La seule exception de la table est `slots` -> `s`, qui n'est pas un champ
    # mais l'enveloppe des emplacements.
    #
    # Cout de la fidelite a la convention: UN octet par planche. Le depot a
    # deja tranche cet echange dans l'autre sens -- descendre a une lettre par
    # champ gagnerait 15 octets et rendrait un payload indechiffrable a la
    # main. Un octet contre la meme lisibilite est le meme echange.
    #
    # BUDGET, mesure par le chemin de production sur les TROIS regimes que le
    # banc epingle (une premiere redaction de ce commentaire ne citait que le
    # regime de reference et presentait sa marge comme « le pire cardinal »):
    #
    #   regime      card. 8 : base -> rang 2 -> rang 99   marge/512 au rang 99
    #   reference             464     471       472               +40
    #   identifiants longs    527     534       535               -23
    #   identifiants maximaux 551     558       559               -47
    #
    # Cout: 7 octets aux rangs 2 a 9, 8 octets aux rangs 10 a 99. Les deux
    # derniers regimes etaient DEJA au-dessus du budget nominal avant ce champ
    # -- c'est le constat que `test_the_absolute_identifier_ceiling_is_the_one
    # _regime_still_over_nominal` epingle, et il ne naît pas ici. Ce qui compte
    # et qui est verifie: aucun regime, a aucun cardinal, ne franchit le
    # PLAFOND DUR de 768, et aucun n'atteint la version de symbole 22
    # (`QR_BANNED_SYMBOL_VERSIONS`), indecodable a toute taille d'impression.
    "version_rank": "vr",
    "slots": "s",
    "slot_index": "si",
    "frame_timecode": "ft",
})

#: Table inverse, **derivee** et jamais ecrite a la main: c'est la seule facon de ne
#: pas pouvoir faire diverger l'ecriture de la lecture. Sa bijectivite est verifiee
#: par test et non par une garde a l'import -- une cle courte dupliquee ferait
#: disparaitre une entree ici, ce qu'un test doit dire en echouant plutot qu'en
#: empechant le module de se charger.
PAYLOAD_LONG_KEYS: Mapping[str, str] = MappingProxyType(
    {short: long for long, short in PAYLOAD_SHORT_KEYS.items()}
)

#: Cle courte de la version de schema. Sa presence dit « planche de ce dispositif »,
#: son absence dit « QR etranger » (AC 3) -- et depuis la story 2.7 (retrait de la
#: branche de lecture 1.0, `EPIC7-ARB-56`), c'est la **seule** forme examinee a la
#: relecture: la cle longue jumelle qui distinguait encore une planche `1.0` perimee
#: d'un QR etranger a ete retiree avec la branche qui la lisait.
_SHORT_SCHEMA_VERSION_KEY = PAYLOAD_SHORT_KEYS["schema_version"]
_SHORT_SLOTS_KEY = PAYLOAD_SHORT_KEYS["slots"]
_LONG_SLOTS_KEY = "slots"

#: Les deux **niveaux** du document, dans les deux formes de cles. La table est plate --
#: les deux jeux de noms etant disjoints, une seule suffit a projeter le document
#: entier -- mais plate ne veut pas dire indifferente au niveau: une cle d'emplacement
#: a la racine, ou une cle de racine dans un emplacement, est un champ **hors contrat**
#: et c'est exactement ce que `_rename_keys` existe pour refuser. Sans ces quatre
#: ensembles, les trois formes de confusion etaient acceptees dans les deux sens
#: (majeur M2 de la revue de 5.17), et le message de refus proposait a l'operateur les
#: quatorze cles sans dire laquelle allait ou.
#:
#: Ils sont exprimes dans les **noms longs** seuls -- ceux du contrat, qui sont deja
#: declares par `_REQUIRED_SCALAR_FIELDS` et `_REQUIRED_SLOT_FIELDS` -- et jamais par
#: une liste de cles courtes recopiee: une seconde liste de cles courtes serait
#: exactement la seconde table que l'AC 1 interdit. Le niveau d'une entree de table se
#: lit donc du cote long, quel que soit le sens dans lequel la table est parcourue.
_ROOT_LEVEL_LONG = frozenset((
    *_REQUIRED_SCALAR_FIELDS,
    *_CALIBRATION_ONLY_FIELDS,
    *_OPTIONAL_SCALAR_FIELDS,
    _LONG_SLOTS_KEY,
))
_SLOT_LEVEL_LONG = frozenset(_REQUIRED_SLOT_FIELDS)
_ALL_LONG_NAMES = _ROOT_LEVEL_LONG | _SLOT_LEVEL_LONG

#: Les cinq champs qui **nomment** une feuille, et les seuls qu'un document refuse
#: livre encore (voir `readable_identity`). `template_id`, `fps_target` et les
#: emplacements n'y sont pas: ceux-la commandent la geometrie, la cadence et le
#: decoupage, et les lire d'un document que le parseur vient de refuser reviendrait a
#: exploiter une planche declaree inexploitable. Nommer n'est pas exploiter.
IDENTITY_FIELDS: tuple[str, ...] = (
    "project_id",
    "rush_id",
    "lot_id",
    "page_index",
    "page_count",
)

#: Les trois champs d'identite qui sont des chaines; les deux autres sont des entiers.
_IDENTITY_TEXT_FIELDS = frozenset({"project_id", "rush_id", "lot_id"})


class PayloadValidationError(ValueError):
    """Raised when a page payload does not satisfy the story 2.3 contract.

    Porte l'**identite encore lisible** du document refuse (`readable_identity`),
    vide par defaut et posee par `parse_payload` quand le texte a pu etre decode en
    objet JSON. Un refus qui ne transporterait pas cette identite ferait perdre a une
    planche perimee son `lot_id`, donc sa presence au lot -- voir
    `readable_identity` pour la mesure qui l'exige (bloquant B1 de la revue de 5.17).
    """

    #: Vide par defaut, et **immuable**: un refus leve ailleurs que dans
    #: `parse_payload` (validation d'un payload construit en memoire, par exemple)
    #: n'a aucun document scanne a nommer, et une valeur par defaut mutable
    #: partagee par toutes les instances serait un piege classique.
    readable_identity: Mapping[str, Any] = MappingProxyType({})


class PayloadSchemaVersionRefused(PayloadValidationError):
    """Payload dont la version de schema n'est pas celle du lecteur (story 5.17).

    Cas nominal: une planche imprimee sous `1.0`, donc a cles longues. Le refus est
    **nomme** plutot que fatal ou partiel: sans lui, un payload `1.0` traverserait la
    projection des cles courtes en perdant tous ses champs et echouerait plus loin sur
    un « champ requis absent » qui n'apprend rien a l'operateur. Ce qu'il doit savoir
    tient en une phrase: cette planche est perimee, il faut la reimprimer.
    """


class PayloadVersionMissing(PayloadValidationError):
    """Payload ne portant **aucune** des deux cles de version (story 5.17).

    Distinct du refus ci-dessus, et la distinction est operationnelle: une planche
    perimee se reimprime, un QR etranger (etiquette de colis, code d'un autre
    dispositif) se met a la poubelle. Les confondre enverrait l'operateur reimprimer
    une planche qui n'a jamais existe.
    """


class PayloadBudgetExceeded(ValueError):
    """Raised when a serialized payload exceeds the QR size ceiling."""


@dataclass(frozen=True)
class PayloadBudgetReport:
    """Result of a payload size budget check."""

    size_bytes: int
    nominal_budget: int
    alert_budget: int
    within_nominal: bool
    within_alert: bool


def build_page_payload(
    *,
    project_id: str,
    rush_id: str,
    lot_id: str,
    page_index: int,
    page_count: int,
    fps_target: float,
    timecode_base_fps: str,
    template_id: str,
    patch_preset_id: str,
    target_colorspace: str,
    gamut_map_id: str,
    slots: list[dict[str, Any]],
    page_role: str = PAGE_ROLE_IMAGES,
    scan_chain_label: str | None = None,
    version_rank: int | None = None,
) -> dict[str, Any]:
    """Build a versioned page payload dict and validate it against the contract.

    ``timecode_base_fps`` **est requis et sans defaut** (story 2.7, payload
    2.1), meme motif que ``gamut_map_id`` juste en dessous: deviner une
    cadence source est l'interdit central de la story 6.6
    (`EPIC6-ARB-6`), donc un defaut serait *un repli silencieux*, exactement
    ce que cette story existe pour supprimer. C'est le bump de version a
    `2.1` qui rend le champ exigible sans violer « une planche imprimee reste
    relisible » (voir `PAYLOAD_SCHEMA_VERSION`).

    ``page_role`` **a un defaut**, et c'est le seul champ de ce contrat qui en a
    un -- l'asymetrie avec ``gamut_map_id`` juste en dessous est deliberee et
    tient a la direction de la faute (story 5.16). Un defaut
    `gamut-map-none-1` serait *juste aujourd'hui et faux demain*, en silence:
    l'appelant qui l'oublie declare « aucune compression » sur une image
    comprimee. Le defaut `PAGE_ROLE_IMAGES`, lui, est le regime **strict**: un
    appelant qui l'oublie sur une page de calibration produit un payload de
    planche d'images **sans emplacement**, que la garde de ``slots`` refuse
    juste en dessous. La faute reste donc impossible a commettre en silence, ce
    qui est la regle du depot -- ici elle est tenue par le refus et non par
    l'absence de defaut.

    ``gamut_map_id`` est **requis et sans defaut** (story 5.9). Un defaut
    `gamut-map-none-1` aurait epargne la reecriture mecanique des appels de
    test, mais il aurait cree exactement le motif que cette story combat par
    ailleurs: une valeur juste par defaut, qui devient fausse en silence des
    que la story 5.10 applique une compression reelle. Un appelant qui oublie
    l'argument emettrait alors un payload declarant « aucune compression » sur
    une image comprimee, et le scan ne la decomprimerait pas. La regle du depot
    est de rendre la faute **impossible**, pas detectable.
    """
    payload: dict[str, Any] = {
        "schema_version": PAYLOAD_SCHEMA_VERSION,
        "project_id": project_id,
        "rush_id": rush_id,
        "lot_id": lot_id,
        "page_index": page_index,
        "page_count": page_count,
        "page_role": page_role,
        "fps_target": fps_target,
        "timecode_base_fps": timecode_base_fps,
        "template_id": template_id,
        "patch_preset_id": patch_preset_id,
        "target_colorspace": target_colorspace,
        "gamut_map_id": gamut_map_id,
        "slots": list(slots),
    }
    # Story 5.23, AC 8bis: une page de calibration sert toute une chaine de scan,
    # donc elle ne declare ni rush, ni lot, ni cadence. Les arguments restent
    # acceptes -- l'appelant de 5.16 les passe encore -- mais ils ne sont pas
    # ecrits: retirer les parametres aurait casse tous les sites d'appel pour un
    # gain nul, alors que le contrat porte sur ce que la feuille DECLARE.
    if page_role == PAGE_ROLE_CALIBRATION:
        for absent in CALIBRATION_ABSENT_FIELDS:
            payload.pop(absent, None)
        # Correction d'Egan du 2026-08-18: le libelle de la chaine **entre** dans le
        # payload, et il n'y entre que sous ce role. Motif produit, et il commande la
        # direction: c'est ce qui permettra a `scan ... calibrate` de relire le
        # libelle **depuis la feuille** et de le proposer a l'operateur, au lieu de
        # le lui faire ressaisir -- une ressaisie de prose ne se recoupe avec rien.
        #
        # Le **commentaire libre** de la meme page, lui, n'y entre pas et c'est le
        # pendant du meme arbitrage: c'est de la prose destinee au lecteur humain de
        # la feuille, elle n'a rien a faire dans une charge utile qu'on paie en
        # octets et en modules de symbole.
        if scan_chain_label is not None:
            payload[SCAN_CHAIN_LABEL_FIELD] = scan_chain_label
    elif scan_chain_label is not None:
        # Refus symetrique de celui de `CALIBRATION_ABSENT_FIELDS`: une planche
        # d'images qui declarerait une chaine de scan ferait croire a la relecture
        # que la feuille porte la calibration, alors qu'elle porte des frames.
        raise PayloadValidationError(
            f"Payload field {SCAN_CHAIN_LABEL_FIELD!r} is only carried by a "
            f"calibration page (page_role='{PAGE_ROLE_CALIBRATION}'), got "
            f"page_role={page_role!r}"
        )
    # OMISSION STRICTE du rang 1 (`EPIC11-ARB-91`). Ecrire `version_rank: 1`
    # couterait 7 octets sur CHAQUE planche du parc pour dire ce
    # que l'absence dit deja -- sur un budget que deux des trois regimes
    # epingles depassent deja --, et ferait diverger deux formes du meme fait:
    # une planche
    # d'avant cette story (sans le champ) et une planche neuve de rang 1
    # cesseraient d'etre octet pour octet identiques, alors qu'elles designent
    # la meme chose.
    if version_rank is not None:
        payload[VERSION_RANK_FIELD] = version_rank
    validate_payload(payload)
    return payload


def payload_version_rank(payload: Mapping[str, Any]) -> int:
    """Le rang de version de la planche, **1 quand le champ est absent**.

    Point d'entree UNIQUE de la lecture du rang (`EPIC11-ARB-91`). Il existe
    pour que le defaut ne soit pas reecrit a chaque site: un `payload.get(...)
    or 1` recopie a trois endroits est une convention en trois exemplaires,
    donc trois occasions de diverger le jour ou le defaut change.

    Verbatim d'Egan qui a tranche le defaut: « les anciens payloads qui ne
    portaient pas de version (2.1) sont tout de meme decodes avec v=1 ».
    C'est ce qui garde relisible tout le parc deja imprime -- une planche sur
    papier ne se met pas a jour.
    """
    # `Mapping` d'abord: toute la raison d'etre de cette fonction est de
    # survivre a une relecture ABIMEE, et lever `AttributeError` sur un
    # document qui n'est pas un dictionnaire serait exactement la panne
    # qu'elle existe pour eviter.
    if not isinstance(payload, Mapping):
        return 1
    valeur = payload.get(VERSION_RANK_FIELD)
    # Pas de garde `isinstance(bool)` ici, et c'est mesure : elle serait
    # SUBSUMEE par les bornes juste en dessous (`True` vaut 1, `False` vaut 0,
    # tous deux hors de 2..99). La retirer ne change aucun comportement, et la
    # garder serait une seconde ecriture du meme classement -- un mutant qui la
    # supprime ne peut par construction faire rougir aucun test, donc elle
    # rassurerait sans rien mesurer.
    if not isinstance(valeur, int):
        return 1
    # LES BORNES AUSSI, et c'est le trou trouve en revue. La garde de type
    # seule laissait passer `0`, `1`, `-5`, `100`, `10**30`. Or la corruption
    # realiste d'un QR imprime n'est pas un changement de type -- c'est un
    # CHIFFRE QUI BASCULE: `2` lu `0`, `12` lu `102`. Ces valeurs traversaient
    # verbatim, et la reconciliation attribuait la feuille a un rang qu'aucun
    # nom de fichier, aucune etiquette imprimee et aucun tirage ne portent.
    # Le banc listait six cas, tous des erreurs de TYPE: il mesurait la moitie
    # du contrat et prenait cette moitie pour le tout.
    if not (VERSION_RANK_MIN <= valeur <= VERSION_RANK_MAX):
        return 1
    return valeur


def sheets_pdf_filename_from_payload(payload: Mapping[str, Any]) -> str:
    """Le nom du tirage dont une planche SCANNEE est issue (`EPIC11-ARB-178`).

    Demande d'Egan, verbatim (2026-09-02): « la fonction qui decode a toutes
    les cles pour savoir le nom de la planche dont est issu un scan ? En
    utilisant les memes infos et le meme systeme de nommage ? »

    **Reponse mesuree: oui, et aucun champ ne manque.** Les cinq entrees de
    `naming.build_sheets_pdf_filename` -- `project_id`, `rush_id`, `lot_id`,
    `template_id`, `version_rank` -- sont **toutes** dans la charge utile: les
    quatre premieres par `_REQUIRED_SCALAR_FIELDS`, la cinquieme par
    `VERSION_RANK_FIELD` avec l'omission du rang 1 (`EPIC11-ARB-91`). La
    reconstruction n'a donc rien a deviner et ne pose aucun arbitrage neuf.

    **UNE fonction, pas deux redactions**, et c'est le point qu'Egan a nomme.
    Cette fonction ne recompose aucune chaine: elle **appelle** le constructeur
    de noms de tirages, celui-la meme que `makepdf` emploie a l'ecriture.
    Consequence voulue et mesuree par un banc: changer la convention de nommage
    -- la place du fragment de mise en page, la forme du suffixe de rang, le
    raccourcissement du `project_id` -- change les deux sorties **ensemble**,
    parce qu'il n'y a qu'une sortie a changer.

    **Ce qu'elle NE rend pas**, dit plutot que tu:

    * **elle ne rend pas un chemin**, seulement un nom de fichier. Le dossier
      (`planches/`) appartient a `project_layout`, et un payload ne declare
      aucune arborescence: la planche scannee peut venir d'un autre poste, ou
      d'un projet dont le disque n'existe plus ici;
    * **elle ne dit pas que le fichier existe.** Elle dit sous quel nom ce
      tirage a ete ecrit **s'il l'a ete par ce depot**. Un tirage anterieur a
      `EPIC11-ARB-171` porte sur le disque la forme ancienne, que
      `naming.legacy_sheets_pdf_filename` reconnait et que celle-ci ne produit
      jamais -- c'est delibere: il n'existe qu'un seul producteur de noms
      neufs, et ce n'est pas ici que la reconnaissance des formes anciennes se
      redecide;
    * **elle ne nomme pas une page de calibration.** Celle-ci ne declare ni
      projet, ni rush, ni lot (`CALIBRATION_ABSENT_FIELDS`): elle n'est le
      tirage d'aucun lot, et son PDF a son propre nom.
    """
    if not isinstance(payload, Mapping):
        raise PayloadValidationError(
            "Impossible de reconstruire un nom de tirage depuis "
            f"{type(payload).__name__}: une charge utile decodee est attendue."
        )
    if _is_calibration_page(dict(payload)):
        raise PayloadValidationError(
            "Une page de calibration n'est le tirage d'aucun lot: elle ne "
            f"declare ni {', ni '.join(sorted(CALIBRATION_ABSENT_FIELDS))}. "
            "Son PDF porte son propre nom."
        )
    manquants = [
        champ for champ in _SHEETS_NAME_PAYLOAD_FIELDS
        if not payload.get(champ)
    ]
    if manquants:
        raise PayloadValidationError(
            "Impossible de reconstruire le nom du tirage: la charge utile ne "
            f"declare pas {', '.join(manquants)}. Une planche d'images les "
            "porte toutes."
        )
    rang = payload_version_rank(payload)
    # Le rang d'origine s'ecrit `None` a l'appel, et non `1`: c'est le
    # constructeur qui pose le fragment `_vN`, et il refuse nommement un rang 1
    # -- « le lot d'origine ne porte aucun fragment de version »
    # (`naming.format_version_suffix`). La bascule est ecrite ici parce que
    # c'est ici qu'on passe de la convention du PAYLOAD (rang 1 omis, donc lu
    # `1`) a celle du NOM (rang 1 omis, donc ecrit `None`) -- deux omissions du
    # meme fait, dont les representations en memoire different.
    return naming.build_sheets_pdf_filename(
        payload["project_id"],
        payload["rush_id"],
        payload["lot_id"],
        version_rank=None if rang == RANG_ORIGINE else rang,
        template_id=payload["template_id"],
    )


def validate_scan_chain_label(value: Any) -> str:
    """Valider un libelle de chaine de scan, ou lever.

    Le bornage de longueur n'est pas cosmetique et il a **deux** raisons, mesurees
    toutes les deux: chaque caractere coute un octet au payload QR, et les cinq
    mentions de la page s'impriment **verbatim** dans une bande d'entete dont la
    hauteur se paie en pastilles reprises au treillis (voir
    :data:`SCAN_CHAIN_LABEL_MAX_LENGTH`).

    Le libelle est de la **prose**, pas un identifiant: aucun pattern canonique ne
    lui est impose -- l'imposer obligerait l'operateur a inventer une forme pour
    « hp envy 4520 tiff 600 dpi auto corr off », c'est-a-dire a ressaisir autre chose
    que ce qu'il lit sur sa machine. Seules les longueurs et le vide sont refuses.
    """
    if not isinstance(value, str) or not value.strip():
        raise PayloadValidationError(
            f"Payload field {SCAN_CHAIN_LABEL_FIELD!r} must be a non-empty string: "
            "une page de calibration anonyme ne se distinguerait pas d'une autre."
        )
    if len(value) > SCAN_CHAIN_LABEL_MAX_LENGTH:
        raise PayloadValidationError(
            f"Payload field {SCAN_CHAIN_LABEL_FIELD!r} is {len(value)} characters "
            f"long, over the contractual maximum of {SCAN_CHAIN_LABEL_MAX_LENGTH} "
            "(chaque caractere coute un octet au QR imprime, et les mentions de la "
            f"page s'impriment verbatim): {value!r}"
        )
    return value


def validate_gamut_map_id(value: Any) -> str:
    """Valider un identifiant de transformation de gamut, ou lever.

    Le bornage de longueur n'est pas cosmetique: chaque caractere coute un
    octet au payload QR, et le budget est mesure (voir GAMUT_MAP_ID_MAX_LENGTH).
    """
    if not isinstance(value, str) or not value:
        raise PayloadValidationError("Payload field 'gamut_map_id' must be a non-empty string")
    if len(value) > GAMUT_MAP_ID_MAX_LENGTH:
        raise PayloadValidationError(
            f"Payload field 'gamut_map_id' is {len(value)} characters long, "
            f"over the contractual maximum of {GAMUT_MAP_ID_MAX_LENGTH} "
            f"(each character costs one byte of the printed QR budget): {value!r}"
        )
    if not _GAMUT_MAP_ID_PATTERN.fullmatch(value):
        raise PayloadValidationError(
            f"Payload field 'gamut_map_id' must match "
            f"'{GAMUT_MAP_ID_PREFIX}<name>-<version>' in lowercase ASCII "
            f"(e.g. '{GAMUT_MAP_IDENTITY}'), got {value!r}"
        )
    return value


def validate_timecode_base_fps(value: Any) -> str:
    """Valider la cadence SOURCE du rush (story 2.7), ou lever.

    Chaine rationnelle exacte ``num/den``, numerateur et denominateur tous deux
    des entiers strictement positifs -- jamais un flottant: c'est precisement ce
    qu'`encode.resolve_source_rate` (story 6.6) refuse de deviner, et c'est la
    forme que `codec_profiles.exact_frame_rate` produit et accepte deja
    verbatim (`"30000/1001"` ne survit pas a un aller-retour float, d'ou la
    chaine plutot qu'un nombre). La verification porte uniquement sur la FORME
    -- l'exactitude de la valeur appartient a l'appelant, qui la lit du
    manifest (`lots[].timecode_base_fps`).
    """
    if not isinstance(value, str) or not value:
        raise PayloadValidationError(
            "Payload field 'timecode_base_fps' must be a non-empty string of "
            f"the form 'num/den' (e.g. '25/1', '30000/1001'), got {value!r}"
        )
    if not _TIMECODE_BASE_FPS_PATTERN.fullmatch(value):
        raise PayloadValidationError(
            "Payload field 'timecode_base_fps' must match 'num/den' (two "
            "strictly positive integers separated by a slash, explicit "
            f"denominator), got {value!r}"
        )
    numerator_text, denominator_text = value.split("/")
    if int(numerator_text) <= 0 or int(denominator_text) <= 0:
        raise PayloadValidationError(
            "Payload field 'timecode_base_fps' must have a strictly positive "
            f"numerator and denominator, got {value!r}"
        )
    return value


#: Champs que le role `c` **n'a pas** (story 5.23, AC 8bis, `EPIC5-ARB-82`).
#:
#: Une page de calibration sert **toute une chaine de scan**: tous les lots, tous
#: les rushes, toutes les cadences. Lui faire porter un `rush_id`, un `lot_id` ou
#: une `fps_target` la declare appartenant a un lot auquel elle n'appartient pas --
#: reste du regime **par lot** de 5.16, ou elle etait litteralement la page 0 d'un
#: lot.
#:
#: Le cout n'est pas cosmetique et il a ete constate a l'usage: un operateur qui
#: voit une page nommee d'un rush la croit reservee a ce rush, et **en reimprime
#: une par lot** -- exactement le geste que la calibration par chaine existe pour
#: supprimer.
#:
#: C'est une **absence**, jamais une valeur vide: un `lot_id` a chaine vide serait
#: un identifiant faux plutot qu'un champ absent, et un lecteur qui teste la
#: presence du champ ne les distinguerait pas.
#:
#: **`project_id` les rejoint le 2026-08-18**, sur la precision d'Egan: « une page de
#: calibration ne depend pas que d'un projet. On peut utiliser la page d'un autre
#: projet dans un projet donne. Cela ne doit pas donner lieu a un refus. » Une page et
#: un profil appartiennent a une **chaine de scan**; le projet n'est qu'un lieu de
#: rangement.
#:
#: Le motif du retrait n'est pas le meme que celui des trois autres, et il vaut la
#: peine d'etre ecrit parce qu'il aurait pu servir a conclure l'inverse. Les trois
#: premiers etaient **faux** sur cette feuille: elle ne decrit aucun rush, aucun lot,
#: aucune cadence. `project_id`, lui, est **vrai** -- c'est bien le projet ou la
#: feuille a ete generee. Ce qui le disqualifie n'est donc pas sa veracite mais son
#: **role**: dans une charge utile, un champ existe pour etre lu par une machine, et
#: aucune machine n'a le droit de lire celui-la pour decider. Un champ qu'aucun chemin
#: n'a le droit de comparer invite une garde future a le comparer -- et cette garde
#: refuserait exactement le geste qu'Egan autorise.
#:
#: **La provenance, elle, n'est pas perdue**: le nom du projet reste **imprime** sur la
#: feuille (c'est la mention 1 des cinq) et reste dans le **nom du fichier**. Les deux
#: s'adressent a un lecteur humain, qui a le droit de savoir d'ou vient une feuille
#: sans que ce soit une appartenance opposable.
#:
#: **`timecode_base_fps` les rejoint par la story 2.7** (payload 2.1,
#: `EPIC7-ARB-56`), pour le meme motif que ses trois voisins de lot: une page de
#: calibration ne decrit aucun rush, donc aucune cadence source. Present sous le role
#: `c`, il est refuse exactement comme `fps_target`.
CALIBRATION_ABSENT_FIELDS: frozenset[str] = frozenset(
    {"project_id", "rush_id", "lot_id", "fps_target", "timecode_base_fps"}
)


def _is_calibration_page(payload: dict[str, Any]) -> bool:
    """Le payload decrit-il une page de calibration ?

    Lu sur `page_role`, jamais deduit de l'absence des champs ci-dessus: deduire
    le role de ce qui manque ferait passer un payload **tronque** de planche
    d'images pour une page de calibration, c'est-a-dire transformer une corruption
    en regime nominal.
    """
    return payload.get("page_role") == PAGE_ROLE_CALIBRATION


def validate_payload(payload: dict[str, Any]) -> None:
    """Raise `PayloadValidationError` if `payload` violates the story 2.3 contract."""
    calibration = _is_calibration_page(payload)
    # Le rang, s'il est present, est un entier des BORNES (`EPIC11-ARB-91`).
    # Present mais hors bornes n'est pas tolere comme l'absence l'est: absent
    # veut dire « rang 1 », tandis qu'un `0`, un `1` ou un `100` ecrit
    # signifierait quelque chose que le nom de la planche ne sait pas porter.
    if VERSION_RANK_FIELD in payload:
        rang = payload[VERSION_RANK_FIELD]
        if isinstance(rang, bool) or not isinstance(rang, int):
            raise PayloadValidationError(
                f"Payload field {VERSION_RANK_FIELD!r} must be an integer, got "
                f"{rang!r}"
            )
        if not (VERSION_RANK_MIN <= rang <= VERSION_RANK_MAX):
            raise PayloadValidationError(
                f"Payload field {VERSION_RANK_FIELD!r} must be between "
                f"{VERSION_RANK_MIN} and {VERSION_RANK_MAX}, got {rang}. Le rang 1 "
                "est l'ORIGINE et ne s'ecrit pas: son absence le dit."
            )
    # Story 5.23: le champ de chaine est **exige** sous le role `c` et **refuse**
    # partout ailleurs. Les deux sens mordent, comme pour la garde d'emplacements:
    # un seul des deux laisserait exprimable soit une page de calibration anonyme,
    # soit une planche d'images qui se declare feuille de calibration.
    if calibration:
        for field in _CALIBRATION_ONLY_FIELDS:
            if field not in payload:
                # **Le motif nomme la feuille, pas une avarie.** Une page de
                # calibration imprimee avant la story 5.23 ne porte pas ce champ, et
                # `EPIC5-ARB-90` refuse **volontairement** ces feuilles: « aucune
                # tolerance de relecture ne sera ecrite -- elle rouvrirait exactement le
                # regime que `EPIC5-ARB-82` a supprime ». La decision ne bouge pas; ce
                # qui se corrige est ce que l'operateur lit. Le motif sec envoyait
                # diagnostiquer un payload abime sur une feuille parfaitement conforme a
                # son propre tirage, et le geste (reimprimer) n'etait ecrit nulle part
                # -- meme famille que le refus de schema `1.0`, qui, lui, le dit deja.
                raise PayloadValidationError(
                    f"Payload is missing required field '{field}' on a calibration "
                    f"page (page_role='{PAGE_ROLE_CALIBRATION}'): cette feuille de "
                    "calibration a ete imprimee AVANT la story 5.23, qui a rendu la "
                    "page autonome de tout rush, lot, cadence et projet et lui a donne "
                    "le libelle de sa chaine de scan. Elle est refusee volontairement "
                    "(EPIC5-ARB-90): sa geometrie n'est pas en cause et la rescanner "
                    "n'y changera rien. Reimprimez la page de calibration de cette "
                    "chaine, puis rescannez-la."
                )
        validate_scan_chain_label(payload[SCAN_CHAIN_LABEL_FIELD])
    else:
        for field in _CALIBRATION_ONLY_FIELDS:
            if field in payload:
                raise PayloadValidationError(
                    f"Payload field '{field}' must be absent outside a calibration "
                    f"page (page_role='{PAGE_ROLE_CALIBRATION}'): got page_role="
                    f"{payload.get('page_role')!r}"
                )
    for field in _REQUIRED_SCALAR_FIELDS:
        if calibration and field in CALIBRATION_ABSENT_FIELDS:
            # Absent par contrat: mais present, il doit etre refuse plutot
            # qu'ignore -- sans quoi une page de calibration pourrait declarer
            # un lot en silence et le regime d'avant reviendrait par la fenetre.
            if field in payload:
                raise PayloadValidationError(
                    f"Payload field '{field}' must be absent on a calibration page "
                    f"(page_role='{PAGE_ROLE_CALIBRATION}'): this sheet serves a whole "
                    "scan chain, not one lot (story 5.23, EPIC5-ARB-82). Une feuille "
                    "qui declare encore ce champ a ete imprimee AVANT la story 5.23 et "
                    "est refusee volontairement (EPIC5-ARB-90): sa geometrie n'est pas "
                    "en cause, la rescanner n'y changera rien. Reimprimez la page de "
                    "calibration de cette chaine, puis rescannez-la."
                )
            continue
        if field not in payload and field not in REREAD_DEFAULTS:
            raise PayloadValidationError(f"Payload is missing required field '{field}'")

    if not calibration:
        if not isinstance(payload["project_id"], str) or not payload["project_id"]:
            raise PayloadValidationError(
                "Payload field 'project_id' must be a non-empty string")
        if not isinstance(payload["rush_id"], str) or not payload["rush_id"]:
            raise PayloadValidationError("Payload field 'rush_id' must be a non-empty string")
        if not isinstance(payload["lot_id"], str) or not payload["lot_id"]:
            raise PayloadValidationError("Payload field 'lot_id' must be a non-empty string")

    page_index = payload["page_index"]
    page_count = payload["page_count"]
    # bool est un sous-type d'int (revue 4.5): True passait pour 1 et sortait
    # en JSON comme le litteral booleen `true`, illisible pour un tiers type.
    if not is_strict_int(page_count) or page_count < 1:
        raise PayloadValidationError("Payload field 'page_count' must be an integer >= 1")
    if not is_strict_int(page_index) or not (
        0 <= page_index < page_count
    ):
        raise PayloadValidationError(
            f"Payload field 'page_index' ({page_index!r}) must satisfy 0 <= page_index < page_count ({page_count!r})"
        )

    # Une page de calibration ne porte aucune frame, donc aucune cadence: le champ
    # est absent par contrat (`CALIBRATION_ABSENT_FIELDS`) et sa garde ne s'applique
    # pas. La garde reste **entiere** pour une planche d'images.
    if not calibration:
        fps_target = payload["fps_target"]
        if not isinstance(fps_target, (int, float)) or isinstance(fps_target, bool) or fps_target <= 0:
            raise PayloadValidationError("Payload field 'fps_target' must be a number > 0")
        # NaN echappe a `<= 0` (toute comparaison est fausse) et Infinity y passe;
        # les deux se serialisent en litteraux JSON non standard (`NaN`,
        # `Infinity`) qu'aucun decodeur strict n'accepte: le QR serait illisible
        # pour la machine tierce visee par le contrat (revue 4.5).
        if not math.isfinite(fps_target):
            raise PayloadValidationError(
                f"Payload field 'fps_target' must be a finite number, got {fps_target!r}"
            )
        # Story 2.7: la cadence SOURCE, meme garde d'absence conditionnelle au role
        # que sa voisine `fps_target` (une page de calibration ne porte ni l'une ni
        # l'autre), mais une forme differente -- chaine `num/den` exacte, jamais un
        # flottant (l'interdit de la story 6.6 porte sur le fait de la DEVINER, pas
        # sur sa representation, mais un flottant y ferait un aller-retour perdant).
        validate_timecode_base_fps(payload["timecode_base_fps"])

    if not isinstance(payload["template_id"], str) or not payload["template_id"]:
        raise PayloadValidationError("Payload field 'template_id' must be a non-empty string")
    if not isinstance(payload["patch_preset_id"], str) or not payload["patch_preset_id"]:
        raise PayloadValidationError("Payload field 'patch_preset_id' must be a non-empty string")
    if not isinstance(payload["target_colorspace"], str) or not payload["target_colorspace"]:
        raise PayloadValidationError("Payload field 'target_colorspace' must be a non-empty string")
    validate_gamut_map_id(payload["gamut_map_id"])

    # Le role est valide **avant** la garde d'emplacements, qui en depend: un role
    # hors vocabulaire ferait choisir la branche stricte par defaut, donc rendrait
    # un refus qui parle des emplacements alors que la faute est sur le role.
    try:
        page_role = validate_page_role(
            payload.get("page_role", REREAD_DEFAULTS["page_role"]))
    except ValueError as error:
        raise PayloadValidationError(
            f"Payload field 'page_role' is invalid: {error}"
        ) from error

    slots = payload.get("slots")
    if not isinstance(slots, list):
        raise PayloadValidationError("Payload field 'slots' must be a list")
    # --- Garde d'emplacements, **conditionnelle au role** (story 5.16, AC 3) ---
    #
    # Elle etait inconditionnelle -- « non-empty list » -- et elle mordait sur la
    # page de calibration, qui ne porte aucune frame donc aucun emplacement. Elle
    # reste **stricte pour une planche d'images**, et l'assouplissement est
    # conditionnel dans les **deux** sens:
    #
    # * une planche d'images sans emplacement est refusee. Ce n'est pas une
    #   precaution theorique: c'est un mode d'echec reel du chemin de scan, un QR
    #   dont les emplacements ont ete perdus, et un assouplissement inconditionnel
    #   l'aurait fait passer en silence;
    # * une page de calibration **avec** emplacements est refusee elle aussi. Le
    #   role dit « aucune frame »; en accepter une serait declarer sur le papier
    #   une frame que personne ne saura ou lire, et rendrait les deux roles
    #   indiscernables a la relecture.
    #
    # La meme paire de refus existe en deux implementations independantes -- ici a
    # l'ecriture, `io.reconstruction._validate_page_payload` a la relecture -- et
    # les deux mordent. Elles restent independantes a dessein: la seconde relit un
    # document que rien ne garantit avoir traverse celle-ci.
    if page_role == PAGE_ROLE_CALIBRATION:
        if slots:
            raise PayloadValidationError(
                f"Payload field 'slots' must be empty for page_role "
                f"{PAGE_ROLE_CALIBRATION!r} ({page_role_label(PAGE_ROLE_CALIBRATION)}): "
                f"got {len(slots)} slot(s). Une page de calibration ne porte aucune "
                "frame, donc aucun emplacement."
            )
    elif not slots:
        raise PayloadValidationError(
            "Payload field 'slots' must be a non-empty list for page_role "
            f"{PAGE_ROLE_IMAGES!r} ({page_role_label(PAGE_ROLE_IMAGES)}): seule une "
            f"page de calibration (page_role {PAGE_ROLE_CALIBRATION!r}) en est "
            "dispensee."
        )
    seen_slot_indexes: set[int] = set()
    for index, slot in enumerate(slots):
        if not isinstance(slot, dict):
            raise PayloadValidationError(f"Payload slots[{index}] must be an object")
        for slot_field in _REQUIRED_SLOT_FIELDS:
            if slot_field not in slot:
                raise PayloadValidationError(f"Payload slots[{index}] is missing required field '{slot_field}'")
        slot_index = slot["slot_index"]
        if not is_strict_int(slot_index) or slot_index < 0:
            raise PayloadValidationError(f"Payload slots[{index}].slot_index must be an integer >= 0")
        # Un slot_index duplique rend le recoupement QR <-> nom de fichier
        # (`_sNN_`) ambigu entre deux frames (revue 4.5): la convention 3.1
        # exige des index continus a l'echelle du lot, donc uniques par page.
        if slot_index in seen_slot_indexes:
            raise PayloadValidationError(
                f"Payload slots[{index}].slot_index {slot_index} is duplicated: "
                "slot indexes are lot-scoped and unique (convention 3.1)"
            )
        seen_slot_indexes.add(slot_index)
        if not isinstance(slot["frame_timecode"], str) or not slot["frame_timecode"]:
            raise PayloadValidationError(f"Payload slots[{index}].frame_timecode must be a non-empty string")


def _rename_keys(
    mapping: dict[str, Any], table: Mapping[str, str], *, sens: str, niveau: str
) -> dict[str, Any]:
    """Renommer les cles de ``mapping`` par ``table``, ou refuser une cle inconnue.

    Une cle absente de la table est refusee et non recopiee verbatim: la recopier
    ferait passer un champ **hors contrat** sur le papier a l'ecriture, et pire, en
    ferait un champ silencieusement conserve a la lecture -- alors que le seul
    consommateur legitime du payload est une machine tierce qui ne connait que le
    contrat. L'ordre d'insertion est preserve, donc l'ordre des champs imprimes reste
    celui de `build_page_payload`.
    """
    renamed: dict[str, Any] = {}
    for key, value in mapping.items():
        short = table.get(key)
        if short is None:
            raise PayloadValidationError(
                f"Cle {key!r} inconnue de la table de correspondance du payload "
                f"({sens}, {niveau}). Cles admises: {sorted(table)}. La table est "
                "unique et contractuelle (story 5.17): un champ nouveau s'y ajoute, "
                "il ne se glisse pas dans un payload."
            )
        renamed[short] = value
    return renamed


def _level_tables(table: Mapping[str, str]) -> tuple[dict[str, str], dict[str, str]]:
    """Scinder ``table`` en ses deux niveaux: racine et emplacement.

    Fonctionne dans les **deux sens** sans avoir a le savoir: le niveau se lit du cote
    **long** de l'entree, celui des noms du contrat, quel que soit celui des deux qui
    porte la cle. C'est ce qui evite d'ecrire une seconde liste de cles courtes -- la
    seconde table que l'AC 1 interdit -- et ce qui fait que la partition suit la table
    si elle change, au lieu d'etre figee a l'import.

    Une entree dont **aucun** des deux cotes n'est un nom du contrat -- un champ hors
    contrat glisse dans la table -- ne se retrouve dans aucune des deux vues, donc n'est
    admise nulle part. C'est le comportement voulu: un champ nouveau s'ajoute au
    contrat *et* a son niveau, jamais a la seule table.
    """
    racine: dict[str, str] = {}
    emplacement: dict[str, str] = {}
    for key, value in table.items():
        nom_long = key if key in _ALL_LONG_NAMES else value
        if nom_long in _ROOT_LEVEL_LONG:
            racine[key] = value
        elif nom_long in _SLOT_LEVEL_LONG:
            emplacement[key] = value
    return racine, emplacement


def _project_payload(
    payload: dict[str, Any], table: Mapping[str, str], *, sens: str, slots_key: str
) -> dict[str, Any]:
    """Projeter un payload **entier** -- racine et emplacements -- par ``table``.

    Chaque niveau ne recoit que **sa** part de la table (`_level_tables`): un
    `slot_index` a la racine ou un `project_id` dans un emplacement est refuse comme
    n'importe quelle cle inconnue, et le message ne propose que les cles du niveau ou
    la faute a eu lieu. La table reste unique -- les deux vues en sont derivees --,
    l'AC 1 de la story reste tenue, et la propriete que `_rename_keys` revendique cesse
    d'etre vraie a un seul niveau sur deux.

    Les valeurs qui ne sont pas des emplacements sont transportees telles quelles: la
    forme des `slots` appartient a `validate_payload`, qui possede son message
    d'erreur. Projeter ici ce qui n'est pas un dictionnaire aurait masque son refus
    derriere une erreur de type sans rapport.
    """
    table_racine, table_emplacement = _level_tables(table)
    projected = _rename_keys(payload, table_racine, sens=sens, niveau="racine")
    slots = projected.get(slots_key)
    if isinstance(slots, list):
        projected[slots_key] = [
            _rename_keys(slot, table_emplacement, sens=sens, niveau="emplacement")
            if isinstance(slot, dict) else slot
            for slot in slots
        ]
    return projected


def serialize_payload(payload: dict[str, Any]) -> str:
    """Serialize `payload` to compact, uncompressed, human-readable JSON text.

    Les cles longues du dictionnaire en memoire sont projetees sur les **cles
    courtes** de `PAYLOAD_SHORT_KEYS` (story 5.17): c'est ce qui est imprime, et le
    seul endroit du depot ou cette projection a lieu. Le dictionnaire en memoire garde
    ses noms longs -- tout le reste de la chaine (reconstruction, scan, manifests) est
    ecrit contre eux, et les raccourcir partout aurait echange 256 octets de QR contre
    un depot illisible.

    `allow_nan=False` (revue 4.5, defense en profondeur): `json.dumps` emet
    par defaut les litteraux non standard `NaN`/`Infinity`, qu'aucun decodeur
    JSON strict n'accepte -- le QR imprime serait illisible chez le tiers.
    La validation refuse deja ces valeurs en amont.
    """
    short = _project_payload(
        payload, PAYLOAD_SHORT_KEYS, sens="serialisation", slots_key=_SHORT_SLOTS_KEY
    )
    return json.dumps(short, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _refuse_unreadable_schema(raw: dict[str, Any]) -> None:
    """Refuser, **avant** toute projection de cles, un payload que ce lecteur ne lit pas.

    **Deux cas depuis la story 2.7** (retrait de la branche de lecture `1.0`,
    `EPIC7-ARB-56`: « la branche de lecture 1.0 est supprimee dans le meme geste »).
    Avant cette story il y en avait trois, dont deux appelaient le meme refus
    (planche `1.0` a cles longues, ou format futur/intermediaire a cles courtes: tous
    deux « planche perimee, reimprimer »). Le premier de ces deux cas est retire ici,
    et son document tombe desormais dans le second refus ci-dessous -- exact au regard
    du parc, aucune planche `1.0` n'ayant jamais ete imprimee hors materiel de test
    (`EPIC5-ARB-60` interdisait deja tout lecteur bi-format; cette story acheve le
    retrait plutot que d'en ouvrir un second):

    * la cle courte `sv` porte une autre version que celle du lecteur: la planche est
      perimee (format futur, format intermediaire, ou -- depuis cette story -- l'ancien
      format `1.0` a cles longues, qui ne porte jamais `sv`, tombe donc ici seulement
      s'il porte malgre tout une cle `sv` errante) et doit etre reimprimee;
    * la cle `sv` est absente: ce n'est pas une planche de ce dispositif -- un QR
      etranger (etiquette de colis, code d'un autre dispositif) **ou** une planche `1.0`
      (cles longues, jamais de `sv`) rendent tous deux ce meme verdict maintenant.

    Le controle vient **avant** la projection parce qu'apres elle un payload etranger
    n'aurait plus aucun champ reconnaissable, et son refus aurait parle d'un
    `project_id` absent au lieu de la seule chose utile a l'operateur.
    """
    if _SHORT_SCHEMA_VERSION_KEY not in raw:
        raise PayloadVersionMissing(
            f"Payload sans version: la cle {_SHORT_SCHEMA_VERSION_KEY!r} est absente. "
            "Ce QR n'est pas une planche du dispositif (code etranger, etiquette de "
            "colis, autre document -- ou planche imprimee sous l'ancien format a cles "
            "longues du schema 1.0, dont la branche de lecture est retiree par la "
            "story 2.7, EPIC7-ARB-56): aucun tirage n'est en cause, c'est le document "
            "scanne qui n'est pas le bon."
        )
    declared = raw[_SHORT_SCHEMA_VERSION_KEY]
    if declared != PAYLOAD_SCHEMA_VERSION:
        raise PayloadSchemaVersionRefused(
            f"Version de payload {declared!r} non supportee, attendu "
            f"{PAYLOAD_SCHEMA_VERSION!r}. Il n'existe pas de lecteur bi-format "
            "(EPIC5-ARB-60): cette planche doit etre **reimprimee** pour etre "
            "rescannable."
        )


def readable_identity(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Identite encore lisible d'un document refuse, sans le projeter ni le valider.

    Motif, et il est mesure (bloquant **B1** de la revue de 5.17): une planche perimee
    est refusee par `parse_payload`, mais elle **est physiquement la** et son QR a
    parfaitement decode. Si son refus ne transporte pas son identite, elle sort du
    filtre `identified = [page for page in pages if page.lot_id]` de
    `scan_detection._reconcile_lot` -- qui est la **seule** detection du risque R12 de
    toute la chaine de scan. Consequence observee avant le correctif: une planche
    **etrangere** perimee ne declenchait plus rien du tout, son diagnostic devenant
    indistinguable de celui d'une planche illisible.

    **Seule la forme a cle courte est lue, depuis la story 2.7** (retrait de la
    branche de lecture 1.0, `EPIC7-ARB-56`): la lecture cle longue servait
    exclusivement le refus d'une planche `1.0`, qui n'existe plus -- une planche
    perimee de format futur ou intermediaire porte deja ses cles courtes, donc son
    identite se lit toujours ici. Ce retrait perd son unique consommateur en meme
    temps que `_refuse_unreadable_schema` perd la branche qui le motivait (AC 4).

    Un champ dont la **valeur** ne tient pas le contrat est **omis**, jamais rendu
    verbatim: ce qui sort d'ici entre dans le document de scan et dans la
    reconciliation, ou un `page_count` valant `"beaucoup"` leverait un `TypeError` a
    des kilometres de sa cause. Le document refuse n'a par definition traverse aucune
    validation: c'est ici, et nulle part ailleurs, que le tri se fait.
    """
    identity: dict[str, Any] = {}
    for field in IDENTITY_FIELDS:
        key = PAYLOAD_SHORT_KEYS[field]
        if key not in raw:
            continue
        value = raw[key]
        if field in _IDENTITY_TEXT_FIELDS:
            if isinstance(value, str) and value:
                identity[field] = value
        # `bool` est un sous-type d'`int` (meme piege qu'en validation): `True`
        # passerait pour la page 1 et sortirait `true` dans le document de scan.
        elif isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            identity[field] = value
    return identity


def parse_payload(text: str) -> dict[str, Any]:
    """Parse `text` back into a payload dict and validate it against the contract.

    Rend un dictionnaire a **cles longues**: la projection des cles courtes est
    l'exact inverse de celle de `serialize_payload`, par la meme table, de sorte
    qu'une boucle serialisation / relecture rende le dictionnaire d'origine a
    l'identique.

    **Tout refus posterieur au decodage JSON transporte l'identite encore lisible**
    du document (`error.readable_identity`, voir `readable_identity`): sans elle une
    planche perimee perd son `lot_id` et disparait de la reconciliation de lot.
    """
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PayloadValidationError(f"Payload text is not valid JSON: {exc}") from exc

    if not isinstance(raw, dict):
        raise PayloadValidationError("Payload text must decode to a JSON object")

    try:
        _refuse_unreadable_schema(raw)
        payload = _project_payload(
            raw, PAYLOAD_LONG_KEYS, sens="relecture", slots_key=_LONG_SLOTS_KEY
        )
        validate_payload(payload)
    except PayloadValidationError as error:
        # Pose sur **tous** les refus de ce chemin, et pas seulement sur celui de la
        # version: une planche du dispositif dont un champ est abime est aussi une
        # feuille presente, et la reconciliation doit la compter.
        error.readable_identity = MappingProxyType(readable_identity(raw))
        raise
    # Les defauts de relecture sont poses **ici** et non laisses aux consommateurs: le
    # dictionnaire rendu porte les treize champs scalaires quelle que soit l'anciennete
    # de la planche, donc aucun appelant n'a de branche « champ absent » a ecrire -- ce sont
    # ces branches, dispersees, qui divergent. Voir `REREAD_DEFAULTS` pour la regle et le
    # motif; le defaut ne remplace **jamais** une valeur presente.
    for field, value in REREAD_DEFAULTS.items():
        payload.setdefault(field, value)
    return payload


def check_payload_budget(payload: dict[str, Any]) -> PayloadBudgetReport:
    """Measure the serialized payload size against the story 2.3 budget guard-rails.

    Raises `PayloadBudgetExceeded` if the payload exceeds the
    `ALERT_BUDGET_BYTES` hard ceiling. Otherwise returns a report indicating
    whether the payload also fits within the `NOMINAL_BUDGET_BYTES` soft
    budget.
    """
    size_bytes = len(serialize_payload(payload).encode("utf-8"))
    within_alert = size_bytes <= ALERT_BUDGET_BYTES
    if not within_alert:
        raise PayloadBudgetExceeded(
            f"Payload size {size_bytes} bytes exceeds the {ALERT_BUDGET_BYTES}-byte ceiling"
        )
    return PayloadBudgetReport(
        size_bytes=size_bytes,
        nominal_budget=NOMINAL_BUDGET_BYTES,
        alert_budget=ALERT_BUDGET_BYTES,
        within_nominal=size_bytes <= NOMINAL_BUDGET_BYTES,
        within_alert=within_alert,
    )
