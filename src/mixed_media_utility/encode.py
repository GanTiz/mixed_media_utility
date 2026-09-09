"""Decision d'encodage d'un lot scanne (story 6.1).

Ce module possede **la decision** et rien d'autre: quel lot, quelles frames,
dans quel ordre, a quelle taille, a quelle cadence, sous quel nom, et que faire
quand il manque quelque chose. La **fabrique** de commande, elle, appartient a
la story 6.0 (`codec_profiles`) et n'est jamais reecrite ici: aucun argv ffmpeg
n'est construit dans ce fichier, aucun `subprocess` n'y est lance. Le point
d'entree consomme est `codec_profiles.run_encode`, jamais
`build_encode_command`: l'appeler puis lancer son propre processus perdrait
toutes les gardes que 6.0 existe pour poser (reservation atomique de la cible,
temporaire a extension conservee, controle de cardinal avant bascule,
nettoyage en `finally`).

**Frontiere declaree, et verrouillee par test: ce module n'ecrit pas le
manifest.** C'est la story 6.5, developpee dans la meme vague (EPIC6-ARB-4).
Aucun `project.json` n'est ouvert en ecriture, aucun etat de lot n'est pose,
aucun champ n'est ajoute a `lots[]`. La frontiere est declaree ici sur le motif
exact de la story 4.1, qui declarait ne jamais ecrire le manifest jusqu'a ce
que 5.11 le fasse: la declarer n'est pas un commentaire, c'est ce qui rend
l'ouverture future explicite plutot que silencieuse.

Ce que ce module lit, et pourquoi il refuse un dossier d'images nu
(EPIC6-ARB-2): le disque **ne sait pas** distinguer une mire de synthese d'une
vraie frame -- meme nom par construction, aucun tag. Le verdict de completude,
le registre des mires, la cadence du lot et le timecode de depart vivent
**uniquement** dans le manifest. Un dossier nu produirait donc un master faux
sans le dire.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path, PurePosixPath
from typing import Any

from . import codec_profiles, color_pipeline, scan_output_frames, video_metadata
from .io import (
    encode_manifest, extraction_manifest, metadata_matrix, naming,
    project_layout, version_ranks,
)
from .io.manifest import LOT_STATES
from .numeric_guards import is_strict_number

# --------------------------------------------------------------------------
# La FRONTIERE du vocabulaire (story 11.14, `EPIC11-ARB-214` et `221`)
# --------------------------------------------------------------------------
#
# Ce module porte les deux moities du renommage a la fois, et les confondre est
# le seul vrai risque de la story. Elle est ecrite ICI plutot que tenue de
# tete, et une frontiere negative la MESURE
# (`test_encode_noyau.py::test_les_chaines_VISIBLES_...`).
#
# **Ce qui NE bouge PAS -- les CLES de manifeste, gelees par `EPIC11-ARB-221`
# (regime « surfaces seules », `Q7` fermee le 2026-09-04).** `output_frames_dir`
# reste `output_frames_dir`, le schema ne monte pas de version, et aucun
# lecteur ne connait « deux formes » pour une cle. Cela couvre :
#
#   * toute lecture litterale du document -- `lot.get("output_frames_dir")`,
#     `entree.get("output_frames_dir")` ;
#   * toute PHRASE qui NOMME la cle a l'operateur : le refus
#     `ENCODE_OUTPUT_DIR_NOT_DECLARED` dit « ne declare aucun
#     `output_frames_dir` », et c'est exactement ce qu'il doit dire -- c'est la
#     cle qu'il faudra ecrire dans le manifeste. La renommer dans le message
#     ferait chercher a l'operateur une cle qui n'existe pas, c'est-a-dire un
#     blocage sec deguise (`EPIC11-ARB-89`) ;
#   * les champs de `ReconstructionDeLot` et d'`EncodableLot`, qui portent le
#     nom de la cle qu'ils transportent. Ils sont lus par `tui/` -- hors du
#     perimetre de ce lot --, donc leur renommage est une operation a part et
#     il est NOMME dans le compte rendu plutot que fait a moitie.
#
#   Le commentaire de `scan_previz.py:294-300`, deja cite plus bas -- « un code
#   qui nomme un fait deja nomme par un producteur livre prend l'orthographe du
#   producteur » -- cesse d'etre une convention locale et devient ici
#   l'application directe d'`EPIC11-ARB-221` : le producteur du document, c'est
#   le manifeste, et son orthographe est gelee.
#
# **Ce qui BOUGE -- tout ce que l'OPERATEUR lit, et tout chemin ECRIT :**
#
#   * les libelles d'objet des messages : le CONTENANT versionne est un
#     « lot scanne », son CONTENU un « jeu de frames scannees ». « dossier »
#     nommait un contenant generique la ou un type existe (AC 6.2 : un objet se
#     nomme par son type) ;
#   * **le mot « reconstruction » cesse d'etre un libelle** (`EPIC11-ARB-223`,
#     2026-09-04, lot F). C'etait le TROISIEME nom de la meme passe de scan --
#     l'operateur tapait une option, en lisait un deuxieme dans le refus de
#     cette meme commande, et un troisieme ici. Les cinq refus de
#     `_resoudre_la_reconstruction_visee` disent desormais « lot scanne ».
#     **La ligne de partage est nette et elle se mesure** : ce que l'operateur
#     LIT en prose bouge ; ce qu'une machine COMPARE ne bouge pas -- ni le code
#     `RECONSTRUCTION_INCONNUE` (miroite caractere pour caractere dans
#     `encode_previz.ENCODE_PREVIZ_REFUSAL_CODES`, et branche par la TUI), ni
#     la cle `reconstructions` (`EPIC11-ARB-221`), ni la section
#     `reconstruction` du manifeste, qui decrit un AUTRE objet -- le detail par
#     frame d'`io/reconstruction` -- et que renommer confondrait deux choses au
#     lieu d'en clarifier une ;
#   * les noms de dossier cites en exemple ou en prose : `frames-scannees/` et
#     `extract-frames/`, jamais `output-frames/` ni `frames/` ;
#   * les noms d'objet en francais : « frames scannees », jamais « frames
#     rescannees ». Le VERBE « rescanner » reste, lui, parfaitement valide --
#     `EPIC11-ARB-105` en fait le geste qui produit une VERSION --, et « ce lot
#     n'a pas ete rescanne » dit l'action, pas l'objet.
#
# **Aucun chemin ne se compose en chaine litterale** : les noms de dossier
# vivent dans `io/project_layout` et nulle part ailleurs. Ce module n'en
# compose aucun -- il ne fait que joindre au projet la valeur RELATIVE que le
# manifeste declare --, et la frontiere ci-dessus le tient dans ce sens aussi.

# --------------------------------------------------------------------------
# Vocabulaire ferme des constats (AC 17)
# --------------------------------------------------------------------------
#
# Regle d'orthographe deja ecrite dans le depot (`scan_previz.py:294-300`): un
# code qui nomme un fait deja nomme par le vocabulaire ferme d'un producteur
# livre prend l'orthographe **du producteur**, au caractere pres. D'ou la
# cohabitation assumee de codes francais (venus de `io/extraction_manifest` et
# de `io/scan_manifest`) et d'un code anglais (`HETEROGENEOUS_FRAME_SHAPES`,
# venu de `scan_output_frames`): reprendre l'orthographe du producteur vaut
# mieux qu'une harmonisation qui ferait deux vocabulaires pour un seul fait.

#: Lot absent de `lots[]`. Orthographe de `extraction_manifest.VERIFY_LOT_ABSENT`.
ENCODE_LOT_ABSENT = extraction_manifest.VERIFY_LOT_ABSENT

#: `lots[].output_frames_dir` n'est pas declare. Orthographe de
#: `extraction_manifest.VERIFY_FRAMES_DIR_NOT_DECLARED`.
ENCODE_OUTPUT_DIR_NOT_DECLARED = extraction_manifest.VERIFY_FRAMES_DIR_NOT_DECLARED

#: Le dossier declare n'existe pas sur le disque. Orthographe de
#: `extraction_manifest.VERIFY_FRAMES_DIR_ABSENT`.
ENCODE_OUTPUT_DIR_ABSENT = extraction_manifest.VERIFY_FRAMES_DIR_ABSENT

#: Le dossier existe mais ne porte aucune frame conforme au lot vise. Distinct
#: du precedent: un dossier cree par `ensure_project_layout` et jamais rempli
#: est le cas nominal d'un projet dont le scan n'a pas encore eu lieu.
ENCODE_OUTPUT_DIR_EMPTY = "DOSSIER_DE_LOT_VIDE"

#: L'etat du lot est en deca de `scan`. Cause distincte de celle du dossier
#: absent, donc **code distinct** (AC 3): un lot en `reconstruction` passe une
#: garde d'etat sans porter la moindre frame, et confondre les deux ferait
#: lire "etat insuffisant" a un operateur dont le lot est au bon etat.
#:
#: Ce code nomme **un seul** fait: l'etat. La revue du 2026-08-10 a releve qu'il
#: en nommait quatre -- l'etat, une cadence non numerique, un `rush_id` absent et
#: un champ de la matrice 2.4 sans valeur -- ce qui est le defaut symetrique de
#: celui que l'AC 3 corrige en separant l'etat du dossier. Les trois autres faits
#: ont desormais leur code.
ENCODE_LOT_STATE_TOO_EARLY = "ETAT_DE_LOT_INSUFFISANT"

#: `lots[].fps_target` n'est pas un nombre: la cadence du master n'a aucune
#: source. Rien a voir avec l'etat du lot, qui peut etre parfaitement `scan`.
ENCODE_FRAME_RATE_UNUSABLE = "CADENCE_DE_LOT_INEXPLOITABLE"

#: `lots[].rush_id` est absent: la convention de nom des frames scannees n'est
#: pas reconstructible. Fait distinct de l'etat, la encore.
ENCODE_RUSH_ID_ABSENT = "RUSH_ID_ABSENT_DU_LOT"

#: Story 6.6, AC 1bis, elargi par la story 2.7 (payload 2.1, `EPIC7-ARB-56`). Le
#: lot ne porte pas `timecode_base_fps` -- typiquement une planche imprimee en
#: payload 2.0 (avant la story 2.7, qui a fait porter la cadence source par le
#: QR) ou un manifest reconstruit d'une source qui ne l'ecrit pas -- et
#: l'operateur n'a pas complete `--cadence-source`: la cadence source du master
#: n'a alors aucune valeur -- jamais un repli silencieux sur `fps_target`, qui
#: degraderait le master exactement comme le lot reel qui a motive cette story
#: (`EPIC6-ARB-6`).
ENCODE_SOURCE_RATE_MISSING = "CADENCE_SOURCE_MANQUANTE"

#: Story 6.6, AC 1bis -- **ce refus ne se produit plus depuis la story 2.7**
#: (payload 2.1, `EPIC7-ARB-56` / AC epics 2.7). Avant cette story, le lot
#: portant deja `timecode_base_fps` **et** `--cadence-source` passe en meme
#: temps etait refuse: laisser le flag l'emporter aurait ecrase silencieusement
#: une valeur qui faisait deja foi. **Renverse par la story 2.7**: le papier ne
#: se met pas a jour (`EPIC7-ARB-51`) -- une cadence source fausse imprimee sur
#: une planche ne peut etre corrigee qu'a l'encodage, donc l'option **doit**
#: pouvoir ecraser la valeur du lot. `resolve_source_rate` ne leve plus jamais
#: ce code: les deux presents font desormais gagner l'option, avec un
#: avertissement structure (`EncodePlan.source_rate_override_note`) qui nomme
#: les deux valeurs plutot qu'un ecrasement muet.
#:
#: **Elle reste declaree et dans `ENCODE_REFUSAL_CODES`** -- exception mesuree,
#: pas un oubli (la regle du depot est "aucune constante inerte", lecon E06/F10
#: de 5.16): `encode_previz.py` porte un miroir **litteral** de ce tuple,
#: confronte caractere a caractere par
#: `tests/unit/test_encode_previz.py::test_the_refusal_vocabulary_mirrors_its_producer_character_for_character`,
#: et la story 2.7 lui est **explicitement interdite** (aucune ligne de GUI/previz,
#: `EPIC7-ARB-46`). Retirer ce code casserait ce miroir sans pouvoir le reparer
#: dans le meme geste. Voir Dev Agent Record de la story 2.7 et
#: `deferred-work.md` pour le retrait complet, reserve a une story autorisee a
#: toucher `encode_previz.py`.
ENCODE_SOURCE_RATE_REDUNDANT = "CADENCE_SOURCE_REDONDANTE"

#: Story 6.6, trouve par la revue en trois couches (Edge Case Hunter, finding
#: 1/3): un `hold_count` calcule non strictement positif (cadence source
#: fournie plus basse que celle reellement encodee dans les noms de frame --
#: chemin reel avec `--cadence-source`; ou `lot["source_tail_frames"]`
#: negatif -- manifest corrompu) ecarterait silencieusement une frame du
#: master (`range(count)` vide pour un `count <= 0`), sans aucun signal.
#: Refuse au lieu de perdre une image sans le dire.
ENCODE_HOLD_COUNT_NOT_POSITIVE = "MAINTIEN_DE_FRAME_NON_POSITIF"

#: Story 6.6, meme revue, finding 3: `lot["source_tail_frames"]` porte une
#: valeur qui ne se convertit pas en entier (manifest corrompu) -- un
#: `ValueError` nu de `int(...)` remontait hors de la hierarchie du module.
ENCODE_SOURCE_TAIL_FRAMES_UNUSABLE = "QUEUE_DE_LOT_INEXPLOITABLE"

#: Un champ exige au conteneur video par la matrice 2.4 n'a aucune valeur. Fait
#: distinct de l'etat: le lot peut etre au bon etat et le projet muet.
ENCODE_MATRIX_FIELD_MISSING = "CHAMP_DE_MATRICE_SANS_VALEUR"

#: Plusieurs tirages du meme lot d'extraction (story 5.12): refus, candidats
#: nommes. Choisir automatiquement est exclu (EPIC6-ARB, point 4).
ENCODE_MULTIPLE_PRINTS = "TIRAGES_MULTIPLES"

#: Formes heterogenes dans la sequence. Orthographe de
#: `scan_output_frames.SCAN_OUTPUT_WARNING_CODES`, au caractere pres.
ENCODE_HETEROGENEOUS_SHAPES = "HETEROGENEOUS_FRAME_SHAPES"

#: Le lot est troue: moins de frames conformes que le cardinal attendu.
#: Orthographe de `scan_manifest.SCAN_LOT_INCOMPLETE`.
ENCODE_LOT_INCOMPLETE = "LOT_INCOMPLET"

#: Aucun cardinal de reference: `expected_frame_count` est absent du lot.
#: Orthographe de `scan_manifest.SCAN_EXPECTED_FRAME_COUNT_INDETERMINABLE`.
ENCODE_EXPECTED_COUNT_INDETERMINABLE = "CARDINAL_ATTENDU_INDETERMINABLE"

#: Plus de frames conformes que le cardinal attendu. Orthographe de
#: `extraction_manifest.VERIFY_UNEXPECTED_FRAMES`.
ENCODE_UNEXPECTED_FRAMES = extraction_manifest.VERIFY_UNEXPECTED_FRAMES

#: Le cardinal est le bon et la selection n'est **pas** la bonne: l'empreinte
#: recalculee depuis le disque differe de `lots[].frame_timecodes_digest`.
#: Orthographe de `extraction_manifest.VERIFY_DIGEST_MISMATCH`.
ENCODE_DIGEST_MISMATCH = extraction_manifest.VERIFY_DIGEST_MISMATCH

#: Les bornes du lot (`first_frame_timecode` / `last_frame_timecode`) ne sont pas
#: celles de la sequence trouvee sur le disque, alors que le cardinal, lui,
#: correspond. Aucun producteur du depot ne nomme ce fait: le code est neuf.
ENCODE_BOUNDS_MISMATCH = "BORNES_DE_LOT_DIVERGENTES"

#: Le timecode recule dans une suite ordonnee chronologiquement: franchissement
#: de 24 h (`frame_selection._format_timecode` reboucle modulo 86400 * fps).
ENCODE_TIMECODE_DECREASING = "TIMECODE_DECROISSANT"

#: Le timecode de depart lu au manifest est invalide dans sa propre base, ou
#: sort des bornes une fois converti dans la base du master.
ENCODE_TIMECODE_UNCONVERTIBLE = "TIMECODE_DE_DEPART_INCONVERTIBLE"

#: Un master est deja present et `--overwrite` n'a pas ete demande.
ENCODE_MASTER_ALREADY_PRESENT = "MASTER_DEJA_PRESENT"
#: Les 98 rangs de version d'un master au meme profil sont pris
#: (`EPIC11-ARB-91`). Code distinct de `MASTER_DEJA_PRESENT`: la
#: situation est differente et les issues aussi.
ENCODE_MASTER_RANKS_EXHAUSTED = "RANGS_DE_MASTER_EPUISES"

#: `--nouvelle-version` et `--overwrite` passes ensemble (story 11.8, AC 4.1).
#: Meme forme que le refus d'`extraction.run_extraction` pour le couple
#: `--nouvelle-version` / `--ecrasement-conscient`: ce sont **deux issues du
#: meme conflit d'ecriture**, jamais deux a la fois. Les combiner demanderait
#: un troisieme comportement qu'`EPIC11-ARB-89` n'a jamais decrit -- ecrire un
#: master de rang voisin ET ecraser quelque chose, sans dire quoi.
ENCODE_VERSION_AND_OVERWRITE = "VERSION_ET_ECRASEMENT_COMBINES"

#: Le **lot scanne** designe ne correspond a aucune passe de l'historique
#: du lot (story 6.8, `EPIC11-ARB-190`). **Le CODE garde le mot que le LIBELLE
#: a perdu** (`EPIC11-ARB-223`) : sa valeur est un jeton de contrat, miroite
#: caractere pour caractere dans `encode_previz` et compare par la TUI ; les
#: phrases qu'il accompagne, elles, disent « lot scanne ». Code distinct de
#: `DOSSIER_DE_LOT_ABSENT`, qui dit qu'une passe **connue** n'est plus sur le
#: disque: ici le lot n'a jamais connu cette passe, et les deux situations
#: n'ont ni la meme cause ni les memes issues. Le refus **enumere les passes
#: disponibles** -- `EPIC11-ARB-89`: un refus qui n'offre aucune issue est
#: aussi fautif qu'une destruction silencieuse.
ENCODE_RECONSTRUCTION_UNKNOWN = "RECONSTRUCTION_INCONNUE"

#: `outputs/` existe en tant que **fichier**. Sans ce constat,
#: `mkdir(parents=True, exist_ok=True)` leve un `FileExistsError` nu.
ENCODE_OUTPUTS_IS_A_FILE = "DOSSIER_DE_SORTIE_EST_UN_FICHIER"

#: Le chemin du master existe en tant que **repertoire**. Mesure du 2026-08-10:
#: sans ce constat, `--overwrite` payait l'encodage complet avant que la bascule
#: ne leve `IsADirectoryError`, rendu par la CLI en "verifier l'espace disponible
#: et les droits d'ecriture" -- un diagnostic qui accuse le disque pour une cause
#: qui n'a rien a voir, et un fichier d'attente de la taille d'un master
#: abandonne sur place. Fait distinct de `ENCODE_OUTPUTS_IS_A_FILE`, qui porte
#: sur le **dossier** de sortie.
ENCODE_MASTER_IS_A_DIRECTORY = "MASTER_EST_UN_REPERTOIRE"

#: Destination non inscriptible (droits, disque plein, systeme en lecture seule).
ENCODE_DESTINATION_NOT_WRITABLE = "DESTINATION_NON_INSCRIPTIBLE"

#: `video_metadata.verify_technical_metadata` a rendu au moins un champ non
#: conforme sur le fichier produit. Le master precedent reste intact et le
#: fichier fautif est conserve pour diagnostic (AC 13, AC 15).
ENCODE_TECHNICAL_VERIFICATION_FAILED = "VERIFICATION_TECHNIQUE_EN_ECHEC"

#: Interruption clavier pendant l'encodage (`SIGINT`, `Ctrl-C`).
ENCODE_KEYBOARD_INTERRUPT = "INTERRUPTION_CLAVIER"

#: Arret demande par signal pendant l'encodage (`SIGTERM`: `kill`, `docker
#: stop`, ordonnanceur). Fait distinct du precedent, et il fallait le distinguer:
#: mesure du 2026-08-10, un `SIGTERM` sur la commande tuait Python et laissait
#: **ffmpeg orphelin** aller jusqu'au bout (36 Mo ecrits apres la mort du CLI),
#: pendant que le message annoncait "encodage arrete".
ENCODE_TERMINATION_REQUESTED = "ARRET_DEMANDE"

#: Resolution de sortie inconnue du registre et non exprimable en `<L>x<H>`.
ENCODE_UNKNOWN_RESOLUTION = "RESOLUTION_INCONNUE"

#: Refus **bloquants**: chacun arrete la commande avant tout encodage, sauf
#: ceux qui portent explicitement sur une etape posterieure.
ENCODE_REFUSAL_CODES: tuple[str, ...] = (
    ENCODE_LOT_ABSENT,
    ENCODE_LOT_STATE_TOO_EARLY,
    ENCODE_FRAME_RATE_UNUSABLE,
    ENCODE_RUSH_ID_ABSENT,
    ENCODE_MATRIX_FIELD_MISSING,
    ENCODE_OUTPUT_DIR_NOT_DECLARED,
    ENCODE_OUTPUT_DIR_ABSENT,
    ENCODE_OUTPUT_DIR_EMPTY,
    ENCODE_MULTIPLE_PRINTS,
    ENCODE_HETEROGENEOUS_SHAPES,
    ENCODE_LOT_INCOMPLETE,
    ENCODE_EXPECTED_COUNT_INDETERMINABLE,
    ENCODE_UNEXPECTED_FRAMES,
    ENCODE_DIGEST_MISMATCH,
    ENCODE_BOUNDS_MISMATCH,
    ENCODE_TIMECODE_DECREASING,
    ENCODE_TIMECODE_UNCONVERTIBLE,
    ENCODE_MASTER_ALREADY_PRESENT,
    ENCODE_MASTER_RANKS_EXHAUSTED,
    ENCODE_OUTPUTS_IS_A_FILE,
    ENCODE_MASTER_IS_A_DIRECTORY,
    ENCODE_DESTINATION_NOT_WRITABLE,
    ENCODE_TECHNICAL_VERIFICATION_FAILED,
    ENCODE_KEYBOARD_INTERRUPT,
    ENCODE_TERMINATION_REQUESTED,
    ENCODE_UNKNOWN_RESOLUTION,
    ENCODE_SOURCE_RATE_MISSING,
    ENCODE_SOURCE_RATE_REDUNDANT,
    ENCODE_HOLD_COUNT_NOT_POSITIVE,
    ENCODE_SOURCE_TAIL_FRAMES_UNUSABLE,
    ENCODE_VERSION_AND_OVERWRITE,
    ENCODE_RECONSTRUCTION_UNKNOWN,
)

#: La section `reconstruction` decrit un **autre** lot que celui vise. C'est
#: une information, pas un refus: la section est unique par document et le
#: scan d'un second lot ecrase le detail du premier (schema, propriete
#: `reconstruction`). Fonder quoi que ce soit dessus serait le bloquant B1.
ENCODE_RECONSTRUCTION_OTHER_LOT = "RECONSTRUCTION_DECRIT_UN_AUTRE_LOT"

#: Des fichiers presents dans le dossier ne suivent pas la convention de nom du
#: lot vise. Orthographe de `extraction_manifest.VERIFY_NONCONFORMING_NAMES`.
ENCODE_NONCONFORMING_FILES = extraction_manifest.VERIFY_NONCONFORMING_NAMES

#: Le lot porte des mires de synthese, encodees telles quelles (EPIC6-ARB-3).
#: Orthographe de `scan_manifest.SCAN_SYNTHETIC_FRAMES_PRESENT`.
ENCODE_SYNTHETIC_FRAMES_PRESENT = "FRAMES_SYNTHETIQUES_PRESENTES"

#: Aucun timecode n'est reinjecte: le lot ne porte pas `timecode_base_fps`.
#: Depuis la story 2.7 (payload 2.1), un lot ne du scan seul porte desormais ce
#: champ: ce constat ne vise donc plus qu'une planche imprimee en payload 2.0
#: (avant la story 2.7) ou un manifest reconstruit d'une source qui ne l'ecrit
#: pas. `timecode_base` (l'enum `source`/`target` du manifest), lui, n'a jamais
#: ete porte par le QR et ne l'est toujours pas -- chaque octet du QR se paie.
ENCODE_NO_TIMECODE = "AUCUN_TIMECODE_REINJECTE"

#: Retrait du 2026-08-10 -- `TIMECODE_NON_REINJECTABLE_A_CETTE_CADENCE` a ete
#: **supprime** du vocabulaire, avec l'abstention qu'il nommait. Il disait: la
#: cadence du master rend un champ de frames que la fabrique 6.0 ne sait pas
#: confronter, donc aucun timecode n'est reinjecte. La correction de la story
#: 6.0 (commit `8713094`) rend cette confrontation agnostique a la largeur
#: d'ecriture, si bien que le constat n'avait plus **aucun** emetteur possible.
#: Le vocabulaire etant ferme (AC 17), un code declare et jamais emis est un
#: defaut -- c'est le reproche deja fait a `INTERRUPTION_CLAVIER` par la revue.

#: Le timecode de depart retenu **n'est pas** celui de la premiere frame
#: reellement presente sur le disque: le master porterait un timecode qui designe
#: une image absente.
#:
#: La revision precedente conditionnait ce constat a `timecode_base_fps` present
#: **et** `first_frame_timecode` absent -- combinaison que le seul producteur du
#: depot ne sait pas produire (`io/extraction_manifest.py:825-826` les ecrit sur
#: deux lignes consecutives). La branche etait donc morte, et le cas reel -- un
#: trou en tete sous `--accept-incomplete-lot` -- tombait dans la branche muette.
#: Le constat porte desormais sur la **confrontation** du depart retenu avec
#: `sequence.timecodes[0]`, qui est productible et mesurable.
ENCODE_TIMECODE_NOT_LOT_START = "TIMECODE_DE_DEPART_NON_CANONIQUE"

#: Le timecode de depart est legal dans sa base source et **n'existe pas** dans
#: la base du master: son champ `ff` depasse `ceil(cadence du master) - 1`.
#: Aucun timecode n'est alors reinjecte -- voir `express_timecode_in_master_base`
#: pour la decision de sens et sa mesure.
ENCODE_TIMECODE_START_OUT_OF_BASE = "TIMECODE_DE_DEPART_HORS_BASE_DU_MASTER"

#: Des fichiers de **0 octet** portant un nom conforme ont ete ecartes de la
#: sequence. La story 5.6 range deja un fichier vide dans `nonconforming_files`
#: ("l'ecriture n'etant pas atomique, c'est la forme la plus courante d'artefact
#: d'une passe interrompue"); les compter comme des frames faisait passer un lot
#: troue pour complet, et le refus arrivait ensuite sous un code qui nommait
#: autre chose.
ENCODE_EMPTY_FILES = "FICHIERS_VIDES_ECARTES"

#: La resolution demandee n'a pas le rapport d'aspect de la source: l'image sera
#: **deformee**. L'AC 8 declare la question fermee au MVP parce que toutes les
#: entrees du registre sont en 16:9 -- mais la clause (c) admet un
#: `<largeur>x<hauteur>` libre, et `1000x1000` sur une source 16:9 sortait
#: deforme sans un mot.
ENCODE_ASPECT_RATIO_CHANGED = "RATIO_D_ASPECT_MODIFIE"

#: `color.target_colorspace` du projet ne correspond pas a la colorimetrie du
#: profil retenu. Sans ce constat, la table `PROJECT_TO_PROFILE_COLORSPACE`
#: n'avait **aucun appelant de production** et un projet declarant autre chose
#: que `rec709` recevait un master tague `bt709` en silence.
ENCODE_PROJECT_COLORSPACE_DIVERGENT = "COLORIMETRIE_PROJET_DIVERGENTE"

#: Le master est tague `bt709` alors que la chaine produit des valeurs issues
#: d'un scanner, donc sRGB de fait (AC 16). Approximation assumee et nommee.
ENCODE_SRGB_APPROXIMATION = "APPROXIMATION_SRGB_TAGUEE_REC709"

#: Un lot troue est encode sur consentement explicite (EPIC6-ARB-3). Le master
#: declare son incompletude au recapitulatif; sa persistance appartient a 6.5.
ENCODE_INCOMPLETE_ACCEPTED = "LOT_INCOMPLET_ASSUME"

#: Des residus d'encodage tues (SIGTERM/SIGKILL) ont ete balayes par
#: `codec_profiles.sweep_encode_residues` avant de commencer.
ENCODE_RESIDUES_SWEPT = "RESIDUS_D_ENCODAGE_BALAYES"

#: Constats **informatifs**: ils n'arretent rien, ils se disent.
ENCODE_INFORMATIONAL_CODES: tuple[str, ...] = (
    ENCODE_RECONSTRUCTION_OTHER_LOT,
    ENCODE_NONCONFORMING_FILES,
    ENCODE_EMPTY_FILES,
    ENCODE_SYNTHETIC_FRAMES_PRESENT,
    ENCODE_NO_TIMECODE,
    ENCODE_TIMECODE_START_OUT_OF_BASE,
    ENCODE_TIMECODE_NOT_LOT_START,
    ENCODE_ASPECT_RATIO_CHANGED,
    ENCODE_PROJECT_COLORSPACE_DIVERGENT,
    ENCODE_SRGB_APPROXIMATION,
    ENCODE_INCOMPLETE_ACCEPTED,
    ENCODE_RESIDUES_SWEPT,
)

#: Vocabulaire complet, valide a la construction (motif de
#: `VERIFICATION_CODES` et de `SCAN_PERSISTENCE_CODES`).
ENCODE_CODES: tuple[str, ...] = ENCODE_REFUSAL_CODES + ENCODE_INFORMATIONAL_CODES


def validate_encode_code(code: str) -> str:
    """Garde de vocabulaire: un constat hors table est un defaut, pas une prose.

    Leve une `ValueError` nue, et non une `EncodeDecisionError`: un code hors
    vocabulaire est une faute de **programmation** de ce module, pas un refus
    opposable a l'operateur, et lui donner un code du vocabulaire ferme
    reviendrait a nommer d'un constat legitime ce qui n'en est pas un.
    """
    if code not in ENCODE_CODES:
        raise ValueError(
            f"Constat d'encodage inconnu: {code!r}. Vocabulaire ferme: "
            f"{', '.join(ENCODE_CODES)}."
        )
    return code


class EncodeDecisionError(Exception):
    """Refus de la decision d'encodage, porteur d'un code du vocabulaire ferme.

    Une seule classe plutot qu'une hierarchie: ce qui distingue deux refus ici
    est leur **code**, pas leur traitement -- la CLI les rend tous en `1` et le
    code est ce que l'operateur lit. Une hierarchie parallele au vocabulaire
    ferme serait une seconde ecriture du meme classement.
    """

    def __init__(self, code: str, message: str) -> None:
        self.code = validate_encode_code(code)
        #: La phrase SEULE, sans le code qui la prefixe dans `str(...)`.
        #:
        #: **Elle est retenue parce que `str(self)` ne se defait pas.** Le
        #: rendu `"<CODE>: <phrase>"` est ce que la ligne de commande imprime,
        #: et il est bon la ; mais une surface qui affiche le code dans son
        #: propre champ -- la TUI le fait -- le lisait alors DEUX fois, une
        #: dans son cartouche et une en tete du message. La seule autre issue
        #: etait de retirer le prefixe par decoupage de chaine cote TUI,
        #: c'est-a-dire de requalifier le refus du coeur : exactement ce
        #: qu'`EPIC11-ARB-30` interdit.
        self.message = message
        super().__init__(f"{self.code}: {message}")


class EncodeVerificationRefused(EncodeDecisionError):
    """La verification technique a echoue sur le fichier produit.

    Porte le chemin du fichier **conserve pour diagnostic**: la bascule n'a pas
    eu lieu, donc le master precedent est intact octet a octet (AC 13). Sans ce
    chemin dans l'exception, le message d'erreur ne pourrait pas dire ou
    regarder, et le fichier resterait un residu anonyme.
    """

    def __init__(self, message: str, *, staged_path: Path, report: dict) -> None:
        super().__init__(ENCODE_TECHNICAL_VERIFICATION_FAILED, message)
        self.staged_path = staged_path
        self.report = report


# --------------------------------------------------------------------------
# Registre des resolutions de sortie (AC 8, EPIC6-ARB-5)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class OutputResolution:
    """Une entree nommee du registre des resolutions de sortie."""

    resolution_id: str
    width: int
    height: int

    @property
    def size(self) -> tuple[int, int]:
        return (self.width, self.height)


#: Registre des resolutions de sortie, sur le motif de `page_templates._REGISTRY`,
#: `patch_presets` et `gamut_map`.
#:
#: `EPIC6-ARB-5` exige que **ajouter une resolution ne coute qu'une ligne**,
#: sans toucher au chemin de code: c'est le critere de faute verifiable en
#: revue. Le defaut d'`EPIC6-ARB-1` (1920x1080) est une entree **comme les
#: autres**, jamais un cas particulier cable -- l'ecrire en constante de module
#: aurait satisfait l'arbitrage 1 et rendu couteuse chaque resolution suivante.
#:
#: Toutes les entrees sont en 16:9 au MVP, comme la geometrie des frames
#: scannees (3307x1860 mesure sur les deux lots reels du depot, pour un rush
#: 16:9 **comme** pour un rush 2.35:1): la question du recadrage ou des bandes
#: ne se pose donc pas. Elle se posera a la premiere entree qui ne l'est pas,
#: et rejoint alors `EPIC5-ARB-1` (ratio natif, differe).
RESOLUTION_REGISTRY: dict[str, OutputResolution] = {
    "hd1080": OutputResolution("hd1080", 1920, 1080),
    "uhd2160": OutputResolution("uhd2160", 3840, 2160),
}

#: Defaut d'`EPIC6-ARB-1`. 3307x1860 etant deja du 16:9, la reduction est un
#: simple redimensionnement, sans recadrage ni deformation; et le defaut regle
#: definitivement la parite, la ou 66 combinaisons gabarit x dpi sur 99 rendent
#: une dimension impaire que `libx264`/`libx265` refusent.
DEFAULT_RESOLUTION_ID = "hd1080"

#: Mot reserve designant la geometrie **native** des frames du lot. Ce n'est pas
#: une entree du registre (sa geometrie n'est connue qu'apres avoir sonde les
#: frames), mais elle suit **le meme chemin de mise a l'echelle**: il n'existe
#: pas deux recettes de redimensionnement (`EPIC6-ARB-5`, clause 3).
NATIVE_RESOLUTION_KEYWORD = "native"


def known_resolution_ids() -> tuple[str, ...]:
    """Identifiants du registre, tries. Derives, jamais recopies."""
    return tuple(sorted(RESOLUTION_REGISTRY))


@dataclass(frozen=True)
class TargetResolution:
    """Resolution retenue pour le master, et d'ou elle vient.

    `size` vaut `None` pour la seule demande `native`, dont la geometrie n'est
    connue qu'apres avoir sonde les frames: elle est resolue par
    `settle_resolution`, qui ramene **toutes** les demandes sur le meme chemin.
    """

    requested: str
    origin: str  # "defaut", "registre", "native" ou "personnalisee"
    resolution_id: str | None = None
    size: tuple[int, int] | None = None


def resolve_output_resolution(value: str | None) -> TargetResolution:
    """Resoudre la demande de resolution: registre, `native`, ou `<L>x<H>`.

    Une resolution personnalisee est admise par cette meme porte et suit le
    meme chemin: le depot a deja ferme trois fois le defaut "deux recettes pour
    une meme chose" (deux recettes d'identifiant, deux recettes de condensat,
    deux vocabulaires de codes).
    """
    if value is None:
        entry = RESOLUTION_REGISTRY[DEFAULT_RESOLUTION_ID]
        return TargetResolution(
            requested=DEFAULT_RESOLUTION_ID,
            origin="defaut",
            resolution_id=entry.resolution_id,
            size=entry.size,
        )
    text = str(value).strip()
    if text in RESOLUTION_REGISTRY:
        entry = RESOLUTION_REGISTRY[text]
        origin = "defaut" if text == DEFAULT_RESOLUTION_ID else "registre"
        return TargetResolution(
            requested=text, origin=origin, resolution_id=entry.resolution_id, size=entry.size
        )
    if text == NATIVE_RESOLUTION_KEYWORD:
        return TargetResolution(requested=text, origin="native")
    custom = _parse_custom_resolution(text)
    return TargetResolution(requested=text, origin="personnalisee", size=custom)


def _parse_custom_resolution(text: str) -> tuple[int, int]:
    """Lire une resolution personnalisee `<largeur>x<hauteur>`, ou refuser.

    `isdecimal` et non `isdigit`, et l'ecart n'est pas theorique: `str.isdigit()`
    est vrai pour les exposants (`'2'.isdigit()` sur `U+00B2`) que `int()`
    refuse, et la commande rendait alors une trace Python nue au lieu du refus
    `RESOLUTION_INCONNUE` prevu. Symetriquement, `isdecimal` reste vrai pour les
    chiffres pleine chasse et arabo-indiens, que `int()` accepte: la garde et la
    conversion parlent enfin du meme ensemble.
    """
    width_text, separator, height_text = text.lower().partition("x")
    if not separator or not width_text.isdecimal() or not height_text.isdecimal():
        raise EncodeDecisionError(
            ENCODE_UNKNOWN_RESOLUTION,
            f"Resolution de sortie inconnue: {text!r}. Valeurs admises: les "
            f"identifiants du registre ({', '.join(known_resolution_ids())}), "
            f"{NATIVE_RESOLUTION_KEYWORD!r} pour la geometrie des frames, ou une "
            "resolution personnalisee de forme <largeur>x<hauteur>.",
        )
    width, height = int(width_text), int(height_text)
    if width <= 0 or height <= 0:
        raise EncodeDecisionError(
            ENCODE_UNKNOWN_RESOLUTION,
            f"Resolution de sortie invalide: {text!r}. Les deux dimensions sont "
            "strictement positives.",
        )
    return (width, height)


def settle_resolution(
    target: TargetResolution, source_size: tuple[int, int]
) -> TargetResolution:
    """Arreter la geometrie definitive, `native` comprise, et la renommer.

    Une taille personnalisee (ou native) qui coincide avec une entree du
    registre **reprend son identifiant**. Sans cela, `--resolution 1920x1080`
    et le defaut produiraient deux noms de master differents pour un fichier
    strictement identique -- c'est-a-dire deux recettes de nom pour une meme
    sortie, exactement ce que l'AC 12 existe pour empecher.
    """
    size = target.size if target.size is not None else source_size
    for entry in RESOLUTION_REGISTRY.values():
        if entry.size == size:
            origin = target.origin
            if target.resolution_id is None:
                # Une demande native ou personnalisee qui retombe sur une entree
                # nommee garde la trace de ce qui a ete demande, mais porte
                # desormais l'identite du registre.
                origin = "defaut" if entry.resolution_id == DEFAULT_RESOLUTION_ID else "registre"
            return TargetResolution(
                requested=target.requested,
                origin=origin,
                resolution_id=entry.resolution_id,
                size=size,
            )
    return TargetResolution(
        requested=target.requested, origin=target.origin, resolution_id=None, size=size
    )


def resolution_name_segment(target: TargetResolution) -> str | None:
    """Segment de resolution du nom de master, ou `None` pour le defaut.

    Il n'apparait **que** hors defaut: sans lui, les deux sorties possibles d'un
    meme lot au meme profil (defaut et native) porteraient le meme nom.
    """
    if target.size is None:
        raise EncodeDecisionError(
            ENCODE_UNKNOWN_RESOLUTION,
            "Geometrie non arretee: `settle_resolution` doit etre appelee avant "
            "de nommer le master.",
        )
    if target.resolution_id == DEFAULT_RESOLUTION_ID:
        return None
    if target.resolution_id is not None:
        return target.resolution_id
    return f"{target.size[0]}x{target.size[1]}"


# --------------------------------------------------------------------------
# Colorimetrie declaree (AC 16)
# --------------------------------------------------------------------------

#: Correspondance entre l'orthographe du projet (`color.target_colorspace`,
#: `cli.MVP_TARGET_COLORSPACE`) et celle des profils d'encodage
#: (`EncodeProfile.colorspace`). Deux orthographes pour une meme chose, et la
#: correspondance vit **a un seul endroit**.
#:
#: `bt709` y figure comme cle **et** comme valeur, et ce n'est pas un doublon:
#: `color.target_colorspace` n'est contraint par le schema qu'a etre une chaine
#: non vide, et les producteurs reels ecrivent les deux orthographes -- `rec709`
#: par `init-project` (`cli.MVP_TARGET_COLORSPACE`), `bt709` par le payload QR
#: quand c'est cette orthographe-la qui a ete choisie a la fabrication des
#: planches. Un projet qui parle deja la langue des profils n'est pas un projet
#: divergent, et le faire crier serait un faux positif sur le chemin nominal.
PROJECT_TO_PROFILE_COLORSPACE: dict[str, str] = {"rec709": "bt709", "bt709": "bt709"}

#: Approximation assumee, consignee au `deferred-work.md`: la chaine produit des
#: valeurs issues d'un **scanner**, donc sRGB de fait, que le master tague
#: `bt709`. sRGB et Rec.709 partagent primaires et point blanc, seule la courbe
#: de transfert differe. L'ecart se ferme en le nommant.
#:
#: **Ce constat reste vrai apres la story 5.19, et sa derniere phrase, non**
#: (AC 11). Il portait « le MVP n'applique aucune correction colorimetrique
#: active », ce qui etait vrai jusqu'a ce que la correction du lot soit cablee
#: au chemin de scan -- et devenait faux le jour ou elle l'a ete, sur le meme
#: recapitulatif. La phrase est donc retiree, et **rien d'autre**: la correction
#: active ajuste la reponse du couple imprimante/scanner, elle ne change pas la
#: courbe de transfert de l'espace de sortie. Confondre les deux sujets aurait
#: fait retirer un constat vrai. Ce que la correction a fait se lit sur le
#: **second** champ du recapitulatif, `CALIBRATION_SUMMARY_LABELS`, jamais ici.
SRGB_APPROXIMATION_NOTE = (
    "Approximation assumee: les valeurs viennent d'un scanner, donc sRGB de "
    "fait, et le master est tague bt709. sRGB et Rec.709 partagent primaires "
    "et point blanc, seule la courbe de transfert differe."
)

#: Ce que le recapitulatif dit de la correction couleur, par valeur du contrat 5.5.
#:
#: Second champ exige par l'AC 11 de la story 5.19: le constat sRGB ci-dessus parle de la
#: **courbe de transfert**, celui-ci de la **correction active**. Deux sujets, deux
#: champs -- les fondre en une phrase est exactement ce qui avait rendu le premier faux.
#:
#: Le libelle est une phrase et non l'identifiant brut: c'est l'operateur qui lit ce
#: recapitulatif, et `not_applied` ne lui dit pas s'il doit rescanner quelque chose.
CALIBRATION_SUMMARY_LABELS: dict[str, str] = {
    "not_applied": (
        "aucune correction active (le lot ne porte pas de page de calibration lue); "
        "les pixels du master sont ceux du scan"
    ),
    "applied": (
        "correction active appliquee aux pixels, ajustee sur la page de calibration du "
        "lot; le detail par page vit dans reconstruction.page_calibration_results"
    ),
    "failed": (
        "correction active tentee et non aboutie: les pixels du master sont ceux du "
        "scan, et le manifest nomme la page en cause"
    ),
}


def calibration_summary_line(lot: Mapping[str, Any]) -> str:
    """Ce que la correction couleur a fait **sur ce lot**, tel qu'il le declare. AC 11.

    Lu au manifest et **jamais deduit** d'autre chose: le seul producteur du champ est la
    chaine de scan, et `encode` n'a aucun moyen de reconstituer ce qui est arrive aux
    pixels en les regardant -- une frame corrigee et une frame non corrigee sont deux
    TIFF 16 bits indiscernables.

    **Le champ lu est celui du lot encode, jamais celui du projet** (`EPIC5-ARB-68`).
    C'etait le contraire, et la portee etait le defaut: `encode` produit un master par
    lot, et sur le cas nominal de la v2.1 -- deux lots du meme rush a deux cadences, un
    seul avec sa page de calibration -- le master du lot **non corrige** s'annoncait
    « correction active appliquee aux pixels », contredit ligne par ligne par
    `page_calibration_results`. La docstring d'alors revendiquait « lu au manifest et
    jamais deduit »: c'etait vrai de la lecture, faux de la **portee**, et une lecture
    exacte d'un champ qui parle d'autre chose est un faux succes de la famille R12.

    Un champ absent se lit `not_applied`, comme partout ailleurs dans ce depot -- et
    cette clause porte desormais plus de poids qu'avant, puisque le champ de lot n'est
    ecrit que quand il dit quelque chose: c'est l'etat d'un lot ecrit avant que le champ
    n'existe **et** celui d'un lot qui n'a jamais eu de page de calibration. Les deux
    decrivent correctement ce qui est arrive a ses pixels. Une valeur **inconnue** du
    contrat, elle, ne se traduit pas en phrase: elle est rendue telle quelle et nommee
    inconnue, parce que la deviner ferait dire au recapitulatif quelque chose que le
    manifest ne dit pas.
    """
    declared = (lot or {}).get("color_calibration_status")
    if declared is None:
        declared = color_pipeline.NOT_APPLIED_STATUS
    label = CALIBRATION_SUMMARY_LABELS.get(str(declared))
    if label is None:
        return f"{declared} (valeur hors du contrat 5.5, rendue telle quelle)"
    return f"{declared} -- {label}"


def profile_colorspace_for_project(project_colorspace: str | None) -> str | None:
    """Rendre l'orthographe de profil correspondant a celle du projet, ou `None`.

    `None` signifie "le projet ne declare rien de connu": on ne devine pas, et
    le profil garde la sienne. La table est le seul endroit du depot ou les deux
    orthographes se rencontrent.
    """
    if project_colorspace is None:
        return None
    return PROJECT_TO_PROFILE_COLORSPACE.get(str(project_colorspace))


def confront_project_colorspace(
    manifest: Mapping[str, Any], profile: codec_profiles.EncodeProfile
) -> list[str]:
    """Confronter `color.target_colorspace` du projet a celle du profil retenu.

    Sans cet appel, la table de correspondance n'avait **aucun lecteur de
    production** (mesure: `profile_colorspace_for_project` n'apparaissait que
    dans sa propre definition et dans `__all__`), et son unique test la
    confrontait a elle-meme -- la forme exacte du test tautologique que le
    `CLAUDE.md` a inscrit apres la story 5.9. Consequence concrete: un projet
    declarant autre chose que `rec709` recevait un master tague `bt709` sans le
    moindre constat.

    Ce n'est pas un refus: le MVP n'applique aucune correction colorimetrique
    active, le profil porte sa colorimetrie et c'est elle qui part au conteneur.
    Ce qui manquait etait de le **dire**.
    """
    declared = (manifest.get("color") or {}).get("target_colorspace")
    if not declared:
        return []
    if profile_colorspace_for_project(str(declared)) == profile.colorspace:
        return []
    return [ENCODE_PROJECT_COLORSPACE_DIVERGENT]


#: Tolerance relative sur le rapport d'aspect, en fraction exacte. Elle n'est pas
#: cosmetique et le seuil est mesure: la geometrie des frames scannees reelles
#: du depot est
#: **3307x1860**, dont le rapport (1,77796) n'est pas exactement 16:9 (1,77778)
#: -- 16:9 de 1860 vaudrait 3306,67, et la parite du gabarit a tranche pour 3307.
#: Une egalite exacte crierait donc sur le chemin **nominal**. L'ecart reel y est
#: de 0,01 %, la ou un `1000x1000` sur la meme source est a 44 %: un pour cent
#: separe les deux de trois ordres de grandeur.
ASPECT_RATIO_TOLERANCE = Fraction(1, 100)


def _same_aspect_ratio(source: tuple[int, int], target: tuple[int, int]) -> bool:
    """Les deux geometries ont-elles le meme rapport d'aspect, a la tolerance pres ?

    Arithmetique de fractions exactes, jamais de flottants: le rapport de deux
    rapports est ici un rationnel, et le comparer a `1 +/- tolerance` ne demande
    aucun arrondi.
    """
    ratio = (Fraction(target[0], target[1])) / (Fraction(source[0], source[1]))
    return abs(ratio - 1) <= ASPECT_RATIO_TOLERANCE


# --------------------------------------------------------------------------
# Selection du lot (AC 3, AC 4)
# --------------------------------------------------------------------------

#: Etat minimal exige, lu dans l'ordre canonique de `io/manifest.LOT_STATES`.
#: L'ordre n'est **jamais** recompare a la main (regle de 5.7): il est lu ici,
#: et `validate_lot_state_transition` reste le seul juge des transitions.
MINIMUM_LOT_STATE = "scan"

#: Champ de niveau lot que la story 5.12 cree (son AC 5) pour rattacher un
#: tirage a son lot d'extraction. Il n'existe pas encore dans le depot: c'est le
#: **seul** point a reprendre le jour ou 5.12 est livree, et le rattachement
#: passe exclusivement par lui.
#:
#: Il ne passe **jamais** par une analyse du suffixe `-<condensat8>`: cet espace
#: de noms est deja occupe par le condensat de **bornes** de la story 3.7
#: (`io/naming.bounds_suffix`), et le manifest reel du depot porte trois lots de
#: cette forme. Deux natures de condensat partagent le meme espace de noms.
DERIVED_FROM_LOT_FIELD = "source_lot_id"


def _lots(manifest: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [lot for lot in (manifest.get("lots") or []) if isinstance(lot, Mapping)]


def find_lot_candidates(
    manifest: Mapping[str, Any], lot_id: str
) -> list[Mapping[str, Any]]:
    """Rendre les lots designes par `lot_id`: lui-meme, ou ses tirages.

    Un lot est candidat s'il porte cet identifiant, ou s'il **derive** de ce lot
    d'extraction. La designation directe d'un tirage rend donc un seul candidat,
    et la designation du lot d'extraction en rend autant qu'il a de tirages.
    """
    return [
        lot
        for lot in _lots(manifest)
        if lot.get("lot_id") == lot_id or lot.get(DERIVED_FROM_LOT_FIELD) == lot_id
    ]


def describe_lot_candidate(lot: Mapping[str, Any]) -> str:
    """Une ligne qui dit ce qui distingue un tirage d'un autre (AC 4)."""
    expected = lot.get("expected_frame_count")
    reconstructed = lot.get("reconstructed_frame_count")
    synthetic = lot.get("synthetic_frame_count")
    return (
        f"{lot.get('lot_id')} (etat {lot.get('state')}, cardinal attendu "
        f"{'inconnu' if expected is None else expected}, frames reelles "
        f"{'inconnu' if reconstructed is None else reconstructed}, mires "
        f"{'inconnu' if synthetic is None else synthetic}, lot scanne "
        f"{lot.get('output_frames_dir') or 'non declare'})"
    )


def select_lot(manifest: Mapping[str, Any], lot_id: str) -> Mapping[str, Any]:
    """Choisir le lot vise, ou refuser en nommant les candidats.

    **Choisir automatiquement est exclu**: "le plus complet" n'est pas "celui
    qu'on veut" -- un tirage volontairement partiel est legitime -- et "le plus
    recent" ferait dependre l'oeuvre d'un horodatage que le depot s'interdit de
    persister. L'operateur tranche par `--lot`.
    """
    candidates = find_lot_candidates(manifest, lot_id)
    if not candidates:
        known = sorted(str(lot.get("lot_id")) for lot in _lots(manifest))
        raise EncodeDecisionError(
            ENCODE_LOT_ABSENT,
            f"Aucun lot {lot_id!r} dans le manifest. Lots declares: "
            f"{', '.join(known) if known else 'aucun'}.",
        )
    if len(candidates) > 1:
        lines = "\n  - ".join(describe_lot_candidate(lot) for lot in candidates)
        raise EncodeDecisionError(
            ENCODE_MULTIPLE_PRINTS,
            f"Plusieurs tirages derivent du lot {lot_id!r}; le choix est "
            f"editorial et n'est pas automatisable. Relancer avec --lot sur "
            f"l'un des candidats:\n  - {lines}",
        )
    return candidates[0]


#: Le registre durable des passes de scan d'un lot (`EPIC11-ARB-109`), ecrit
#: par `io.scan_manifest._fusionner_l_historique_de_reconstruction`. Nomme ici
#: plutot que recopie en litteral a chaque lecture.
RECONSTRUCTIONS_FIELD = "reconstructions"


@dataclass(frozen=True)
class ReconstructionDeLot:
    """Une passe de scan du lot, telle que l'historique la porte (story 6.8).

    `rang` vaut `None` -- et `presente` `False` -- quand l'entree ne declare
    aucun `output_frames_dir`. Le schema ne rend `required` que `ingest_slug`,
    donc le cas est **legal**, et l'entree reste **enumeree**: la sauter
    obligerait l'appelant a rejuger ce que le coeur a deja vu
    (`EPIC11-ARB-30`).
    """

    rang: int | None
    output_frames_dir: str
    ingest_slug: str
    presente: bool


def enumerer_les_reconstructions(
    lot: Mapping[str, Any], project_dir: Path
) -> list[ReconstructionDeLot]:
    """Les passes de scan d'un lot, **dans l'ordre du manifest** (story 6.8).

    **Le coeur enumere, l'appelant n'en juge pas** -- meme geste que
    :func:`list_encodable_lots` (`EPIC11-ARB-30`). Rien n'est filtre, rien
    n'est deduplique: une entree dont le dossier a disparu du disque est rendue
    avec `presente=False` plutot qu'omise, parce que c'est precisement ce que
    l'operateur doit voir pour comprendre pourquoi une version n'est plus
    joignable.

    **L'ordre n'est JAMAIS trie** (`EPIC11-ARB-109`): `lots[].reconstructions`
    est chronologique et porte l'information "quelle passe a suivi laquelle",
    que le tri detruirait. C'est la meme regle que celle de son producteur.

    Le rang se lit **au nom du dossier**, par l'inverse de la fabrique de
    fragment (`io.naming.rang_du_fragment_de_version`) et jamais par une
    expression reguliere ecrite ici: la forme `_v<rang>` a un seul proprietaire.
    """
    racine = Path(project_dir)
    passes: list[ReconstructionDeLot] = []
    for entree in (lot.get(RECONSTRUCTIONS_FIELD) or []):
        if not isinstance(entree, Mapping):
            continue
        dossier = entree.get("output_frames_dir")
        dossier = dossier if isinstance(dossier, str) and dossier else ""
        slug = entree.get("ingest_slug")
        passes.append(ReconstructionDeLot(
            rang=naming.rang_du_fragment_de_version(
                PurePosixPath(dossier).name) if dossier else None,
            output_frames_dir=dossier,
            ingest_slug=str(slug) if isinstance(slug, str) else "",
            presente=bool(dossier) and (racine / dossier).is_dir(),
        ))
    return passes


def _decrire_les_reconstructions(passes: Sequence[ReconstructionDeLot]) -> str:
    """Les passes disponibles, en une ligne chacune, pour un message de refus.

    `EPIC11-ARB-89`: un refus qui n'offre aucune issue est aussi fautif qu'une
    destruction silencieuse. Nommer ce qui existe **est** l'issue.
    """
    if not passes:
        return "aucune"
    return "\n  - " + "\n  - ".join(
        f"rang {'inconnu' if p.rang is None else p.rang}, lot scanne "
        f"{p.output_frames_dir or 'non declare'} (scan {p.ingest_slug or 'non declare'}"
        f"{'' if p.presente else ', ABSENT du disque'})"
        for p in passes
    )


def _resoudre_la_reconstruction_visee(
    lot: Mapping[str, Any], project_dir: Path, designation: object
) -> Path:
    """Le dossier de la passe **designee**, ou un refus qui la nomme (story 6.8).

    Deux formes de designation, toutes deux resolues **ici** pour qu'aucun
    appelant -- la TUI la premiere -- n'ait a traduire l'une en l'autre: un
    `int` (le rang de la passe) ou un `str` (son `output_frames_dir`, relatif
    au projet).

    **La chaine est NORMALISEE avant comparaison, et l'antislash est accepte**
    -- corrige le 2026-09-03, finding R7 de la revue: cette docstring disait
    "separateurs POSIX", c'est-a-dire l'INVERSE de ce que le code fait, et la
    normalisation n'avait aucun test (ses deux mutants survivaient). Quatre
    formes rendent donc la meme passe: `frames-scannees/x`,
    `frames-scannees/x/`, `./frames-scannees/x` et `frames-scannees\\x`.

    L'arbitrage est **de garder le code et de corriger la phrase**, et son
    motif est le NFR1: Windows est une plateforme cible, un operateur y copie
    un chemin depuis l'explorateur, et lui refuser sa propre orthographe serait
    un blocage sec sur une faute qui n'en est pas une. Le cout residuel est dit
    plutot que taire: sur un systeme POSIX, un dossier dont le nom contient
    litteralement un antislash serait mal lu. Le producteur n'en ecrit aucun
    (`io.naming._relative_posix`), donc le cas demande un manifeste edite a la
    main -- et c'est reversible en une ligne si Egan tranche l'autre sens.

    **Aucun repli, jamais** (`EPIC11-ARB-89`, AC 3 de la story): une passe
    designee dont le dossier a disparu refuse **en le nommant**, et ne se
    rabat sur aucune autre -- se rabattre encoderait, sous le nom demande, une
    matiere que l'operateur n'a pas demandee.
    """
    passes = enumerer_les_reconstructions(lot, project_dir)
    lot_id = lot.get("lot_id")

    # `bool` est un `int` en Python: sans cette garde, `True` designerait le
    # rang 1 **en silence**, c'est-a-dire un choix pris a la place de
    # l'operateur -- exactement ce que cette story ferme.
    if isinstance(designation, bool) or not isinstance(designation, (int, str)):
        raise EncodeDecisionError(
            ENCODE_RECONSTRUCTION_UNKNOWN,
            f"Lot scanne vise inexploitable pour le lot {lot_id!r}: "
            f"{designation!r} est un {type(designation).__name__}, alors qu'un "
            "rang (entier) ou un dossier (chaine, relatif au projet) est "
            f"attendu. Passes declarees par ce lot: "
            f"{_decrire_les_reconstructions(passes)}",
        )

    if isinstance(designation, int):
        vise = next((p for p in passes if p.rang == designation), None)
    else:
        cible = PurePosixPath(str(designation).replace("\\", "/")).as_posix()
        vise = next((p for p in passes if p.output_frames_dir == cible), None)

    if vise is None or not vise.output_frames_dir:
        raise EncodeDecisionError(
            ENCODE_RECONSTRUCTION_UNKNOWN,
            f"Aucun lot scanne {designation!r} pour le lot {lot_id!r}. "
            f"Passes declarees par ce lot: {_decrire_les_reconstructions(passes)}",
        )

    # -- le confinement, AVANT toute lecture du disque (finding R4 de la revue
    # du 2026-09-03). Sans lui, trois pannes mesurees a la sonde : un
    # `output_frames_dir` **absolu** faisait sortir un `ValueError` NU de
    # `plan_encode` -- hors du vocabulaire ferme de refus, et leve APRES que
    # la decision entiere ait ete prise, si bien qu'une TUI recevait une trace
    # la ou le contrat promet un code ; `"../hors-projet"` faisait CONSTRUIRE
    # un plan sur des frames etrangeres au projet ; et `"/etc"` faisait
    # balayer `/etc` avant de refuser. Le depot avait deja ferme cette famille
    # deux fois (`project_layout.scan_frames_dir_from_slug`,
    # `project_maintenance._sous_le_projet`) : la regle vit desormais dans
    # `io/project_layout`, ce lecteur-ci l'appelle plutot que de la recopier.
    #
    # Le code n'est PAS neuf, et c'est delibere : `RECONSTRUCTION_INCONNUE` dit
    # deja "cette designation ne rend aucune passe exploitable de ce lot", ce
    # qui est exactement le cas ; en ajouter un obligerait a le miroiter dans
    # `encode_previz.ENCODE_PREVIZ_REFUSAL_CODES`, que le banc de la previz
    # tient egal caractere pour caractere.
    dossier = Path(project_dir) / vise.output_frames_dir
    try:
        confine = project_layout.est_strictement_sous_le_projet(project_dir, dossier)
    except OSError as erreur:  # boucle de liens, chemin trop long
        raise EncodeDecisionError(
            ENCODE_RECONSTRUCTION_UNKNOWN,
            f"Le lot scanne {designation!r} du lot {lot_id!r} declare un "
            f"dossier qui n'a pas pu etre resolu ({erreur}): "
            f"{vise.output_frames_dir!r}. Refuse plutot que suppose. Passes "
            f"declarees par ce lot: {_decrire_les_reconstructions(passes)}",
        ) from erreur
    if not confine:
        raise EncodeDecisionError(
            ENCODE_RECONSTRUCTION_UNKNOWN,
            f"Le lot scanne {designation!r} du lot {lot_id!r} declare un "
            f"dossier qui SORT du projet: {vise.output_frames_dir!r} designe "
            f"{Path(dossier).resolve()}, hors de {Path(project_dir).resolve()}. "
            "Un chemin absolu, une remontee (`..`) ou un lien symbolique vers "
            "l'exterieur feraient encoder une matiere etrangere au projet sous "
            "le nom d'une passe de ce lot. Un manifeste sain n'en produit "
            "aucun: celui-ci est corrompu ou modifie a la main. Deux issues: "
            "corriger le manifeste, ou designer une passe contenue. Passes "
            f"declarees par ce lot: {_decrire_les_reconstructions(passes)}",
        )
    if not dossier.is_dir():
        raise EncodeDecisionError(
            ENCODE_OUTPUT_DIR_ABSENT,
            f"Le lot scanne designe du lot {lot_id!r} est introuvable sur "
            f"le disque: {vise.output_frames_dir} (scan "
            f"{vise.ingest_slug or 'non declare'}). Aucune autre passe n'a ete "
            "retenue a sa place: encoder celle d'a cote produirait, sous le nom "
            "demande, une matiere qui n'a pas ete demandee. Deux issues: "
            "designer une passe presente, ou rescanner celle-ci.",
        )
    return dossier


def check_lot_admission(
    lot: Mapping[str, Any],
    project_dir: Path,
    *,
    reconstruction_visee: object = None,
) -> Path:
    """Garde d'admission sur la **matiere**, pas seulement sur l'etat (AC 3).

    La garde d'etat seule est insuffisante, et c'est mesure:
    `io/reconstruction.DEFAULT_LOT_STATE` vaut `reconstruction`, qui est a
    l'index 3 de `LOT_STATES`, donc **superieur** a `scan`. Un lot recree depuis
    des payloads passe donc une garde "au moins scan" alors qu'il ne porte ni
    `output_frames_dir`, ni aucun cardinal de scan, et qu'aucun fichier
    n'existe. Quatre causes, quatre codes.

    **`reconstruction_visee` (story 6.8, `EPIC11-ARB-190`) choisit la PASSE,
    jamais la garde.** L'etat du lot est verifie **dans tous les regimes** et
    **avant** toute resolution de dossier: c'est la meme garde, jamais recopiee
    -- une seconde redaction du critere ne se verrait par aucun test de
    comportement, et c'est ce que la frontiere AST de `list_encodable_lots`
    mesure deja par ailleurs.

    * `None` (defaut) -- le champ **scalaire** `lots[].output_frames_dir`,
      c'est-a-dire la **derniere** passe. C'est le comportement d'avant cette
      story, messages compris ;
    * un rang ou un dossier -- la passe designee dans `lots[].reconstructions`,
      resolue par :func:`_resoudre_la_reconstruction_visee`. Le scalaire n'est
      alors **pas** consulte: `DOSSIER_DE_LOT_NON_DECLARE` dit "ce lot n'a pas
      ete rescanne", ce qui n'a rien a repondre a un operateur qui vient de
      nommer une passe. La designation prime, et c'est elle qui est jugee.
    """
    state = lot.get("state")
    if state not in LOT_STATES or LOT_STATES.index(str(state)) < LOT_STATES.index(
        MINIMUM_LOT_STATE
    ):
        raise EncodeDecisionError(
            ENCODE_LOT_STATE_TOO_EARLY,
            f"Le lot {lot.get('lot_id')!r} est a l'etat {state!r}: il faut au "
            f"moins {MINIMUM_LOT_STATE!r} pour encoder. Ordre des etats: "
            f"{', '.join(LOT_STATES)}.",
        )
    if reconstruction_visee is not None:
        return _resoudre_la_reconstruction_visee(
            lot, Path(project_dir), reconstruction_visee)
    declared = lot.get("output_frames_dir")
    if not declared:
        raise EncodeDecisionError(
            ENCODE_OUTPUT_DIR_NOT_DECLARED,
            f"Le lot {lot.get('lot_id')!r} ne declare aucun `output_frames_dir`: "
            "il n'a pas ete rescanne, et son etat ne suffit pas a le dire (un lot "
            "reconstruit depuis des payloads porte un etat superieur a `scan` sans "
            "porter la moindre frame).",
        )
    lot_dir = project_dir / str(declared)
    if not lot_dir.is_dir():
        raise EncodeDecisionError(
            ENCODE_OUTPUT_DIR_ABSENT,
            f"Le lot scanne declare par le lot {lot.get('lot_id')!r} est "
            f"introuvable: {declared}.",
        )
    return lot_dir


@dataclass(frozen=True)
class EncodableLot:
    """Un lot que la garde d'admission accepte, et le dossier qu'elle a resolu.

    Le dossier est **rendu avec le lot** plutot que laisse a recalculer:
    `project_dir / lot["output_frames_dir"]` est une convention de chemin, et
    la faire reecrire par chaque appelant -- la TUI la premiere -- serait une
    seconde redaction de cette convention, exactement ce que l'enumeration
    existe pour fermer (`EPIC11-ARB-30`).
    """

    lot: Mapping[str, Any]
    output_frames_dir: Path


def list_encodable_lots(
    manifest: Mapping[str, Any], project_dir: Path
) -> list[EncodableLot]:
    """Les lots encodables d'un projet, dans l'ordre du manifest (story 11.8, AC 3).

    **Elle APPELLE la garde, elle ne la recopie pas.** Le critere entier vit
    dans :func:`check_lot_admission` -- etat au moins `MINIMUM_LOT_STATE`,
    `output_frames_dir` declare, et dossier present -- et cette fonction ne
    fait que le passer lot par lot. Une seconde redaction du critere est le
    defaut que cette enumeration ferme, pas une facon de l'ecrire.

    **Le defaut ferme, mesure le 2026-09-02**, et il jouait dans les deux sens
    a la fois: `tui/projet_lecture.ETATS_RECONSTRUITS` jugeait un lot
    encodable sur son seul etat, ce qui donnait

    * **trop strict** -- un lot a l'etat `scan` portant ses frames est
      encodable, et la TUI fermait l'entree `Exports` sur « aucun lot
      reconstruit » alors qu'`mmu encode` passait sur le meme projet;
    * **trop laxiste** -- un lot recree depuis des payloads porte l'etat
      `reconstruction` **sans** `output_frames_dir` (c'est
      `io/reconstruction.DEFAULT_LOT_STATE`, et c'est le motif d'existence de
      la garde). La TUI ouvrait, le coeur refusait par
      `ENCODE_OUTPUT_DIR_NOT_DECLARED`.

    Un lot refuse est **saute**, jamais rendu avec son motif: une enumeration
    qui porterait les refus serait un rapport, et l'appelant devrait alors
    trier -- c'est-a-dire rejuger. Qui veut le motif appelle la garde, qui le
    nomme par un code.

    L'ordre est celui du manifest, jamais un tri: `lots[]` porte l'ordre de
    **premiere creation**, et le reordonner ferait dire a l'ecran une
    anciennete que le document ne porte pas.
    """
    racine = Path(project_dir)
    admis: list[EncodableLot] = []
    for lot in _lots(manifest):
        try:
            lot_dir = check_lot_admission(lot, racine)
        except EncodeDecisionError:
            continue
        admis.append(EncodableLot(lot=lot, output_frames_dir=lot_dir))
    return admis


# --------------------------------------------------------------------------
# Construction de la sequence (AC 5)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SequencePlan:
    """La sequence retenue, et ce qui a ete ecarte."""

    names: tuple[str, ...]
    timecodes: tuple[str, ...]
    nonconforming: tuple[str, ...]
    empty: tuple[str, ...] = ()


def plan_sequence(
    names: Sequence[str],
    *,
    rush_id: str,
    fps_target: float,
    empty_names: Sequence[str] = (),
) -> SequencePlan:
    """Ordonner les noms conformes au lot vise par leur timecode **decode**.

    Fonction **pure**, et c'est ce qui la rend falsifiable: l'ordre de lecture
    d'un dossier est celui du systeme de fichiers (mesure par la story 6.0 sur
    six frames: `05,03,04,06,01,02`), donc un test doit pouvoir lui passer une
    suite deliberement melangee.

    La conformite n'est **jamais** reecrite: elle passe par
    `scan_output_frames.is_conforming_scan_frame_name`, dont le contrat est
    l'egalite du nom reconstruit avec le nom lu, via `io/naming`. Reconstruire
    le prefixe en local serait une seconde ecriture de la convention.

    Tout fichier present et non conforme est **signale** et n'entre pas dans la
    sequence: le rapport 5.6 distingue deja `preexisting_frames` et
    `nonconforming_files`, et `concat` ne peut pas ramasser un fichier que
    l'appelant n'a pas nomme.

    `empty_names` porte les noms dont le fichier fait **0 octet**. Ils sont
    ecartes comme non conformes, quel que soit leur nom: `scan_output_frames.
    _verify_output_dir` range deja un fichier vide dans `nonconforming_files`
    ("l'ecriture n'etant pas atomique, c'est la forme la plus courante
    d'artefact d'une passe interrompue", correction de la revue de 5.6). Les
    compter faisait passer un lot troue pour complet, et le refus tombait
    ensuite, apres la sonde, sous `HETEROGENEOUS_FRAME_SHAPES` -- un code qui
    nomme la forme pour un fait de taille. La taille n'est pas lue ici: cette
    fonction reste **pure**, c'est l'appelant qui sonde le disque.
    """
    empty = set(empty_names)
    retained: list[tuple[tuple[int, ...], str, str]] = []
    rejected: list[str] = []
    for name in names:
        if name in empty or not scan_output_frames.is_conforming_scan_frame_name(
            name, rush_id, fps_target
        ):
            rejected.append(name)
            continue
        timecode = naming.read_scan_frame_timecode(name)
        retained.append((_timecode_sort_key(timecode), timecode, name))
    retained.sort()
    return SequencePlan(
        names=tuple(item[2] for item in retained),
        timecodes=tuple(item[1] for item in retained),
        nonconforming=tuple(sorted(rejected)),
        empty=tuple(sorted(name for name in names if name in empty)),
    )


def _timecode_sort_key(timecode: str) -> tuple[int, ...]:
    """Cle de tri d'un timecode **decode**, jamais de la chaine du nom."""
    return tuple(int(part) for part in timecode.split(":"))


def check_chronology(timecodes: Sequence[str], *, origin: str) -> None:
    """Refuser une suite chronologique qui recule: franchissement de 24 h.

    `frame_selection._format_timecode` reboucle modulo `86400 * fps`: un lot qui
    franchit 24 h voit son tri lexicographique diverger de son ordre temporel, et
    le nom des frames ne porte **rien** qui permette de le rattraper. Le cas est
    donc declare, detecte sur les suites dont l'ordre chronologique est connu par
    ailleurs -- les bornes du lot, et les emplacements de `reconstruction`
    lorsqu'elle decrit ce lot -- et **refuse**, plutot que silencieusement mal
    ordonne.
    """
    for index in range(1, len(timecodes)):
        if _timecode_sort_key(timecodes[index]) < _timecode_sort_key(timecodes[index - 1]):
            raise EncodeDecisionError(
                ENCODE_TIMECODE_DECREASING,
                f"Le timecode recule entre {timecodes[index - 1]} et "
                f"{timecodes[index]} dans {origin}: le lot franchit 24 h et le "
                "timecode reboucle modulo 86400 * fps. L'ordre reel n'est pas "
                "reconstructible depuis les noms de fichiers.",
            )


def reconstruction_for_lot(
    manifest: Mapping[str, Any], lot_id: str
) -> Mapping[str, Any] | None:
    """La section `reconstruction` **si et seulement si** elle decrit ce lot.

    La section est "UNIQUE par document, reecrite en entier a chaque
    reconstruction: le scan d'un second lot ecrase le detail par frame du
    premier" (schema, propriete `reconstruction`). Le manifest reel du depot est
    deja dans ce cas: deux lots a l'etat `scan`, une seule section qui en decrit
    un. Fonder la sequence dessus declarerait l'autre lot -- complet, 5 frames
    sur 5 -- troue a 12 frames sur 13.
    """
    section = manifest.get("reconstruction")
    if not isinstance(section, Mapping):
        return None
    return section if section.get("lot_id") == lot_id else None


# --------------------------------------------------------------------------
# Verdict de completude (AC 6)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CompletenessVerdict:
    """Verdict de lot, lu sur les cardinaux de `lots[]` et eux seuls."""

    expected: int | None
    found: int
    synthetic_present: tuple[str, ...]
    synthetic_missing: tuple[str, ...]
    missing_pages: tuple[int, ...]
    complete: bool


def assess_completeness(
    lot: Mapping[str, Any],
    sequence: SequencePlan,
    reconstruction: Mapping[str, Any] | None,
) -> CompletenessVerdict:
    """Confronter le cardinal trouve au cardinal attendu, sans jamais deviner.

    Le verdict se lit sur `lots[]`, que le schema designe explicitement comme
    faisant foi ("le verdict de LOT se lit sur `lots[]` [...] et lui seul repond
    a 'ce lot est-il fini ?'"). Il ne se lit **pas** sur `reconstruction.slots[]`:
    `io/reconstruction` n'itere que sur `sorted(provided_indexes)`, donc les
    slots d'une page absente n'y entrent **jamais**. Un parcours de `slots[]`
    voit alors autant de slots que de fichiers et conclut "complet".

    Regle de precedence des mires: **le disque fait foi pour la presence, le
    manifest pour la nature.** `synthetic_frames` est un registre durable alors
    que la confrontation au disque n'a lieu qu'a l'ecriture: un nom peut y
    figurer sans que le fichier existe. Un nom au registre sans fichier est un
    **trou**, pas une mire.
    """
    expected = lot.get("expected_frame_count")
    expected = expected if isinstance(expected, int) and not isinstance(expected, bool) else None
    present = set(sequence.names)
    registry = tuple(
        str(name) for name in (lot.get("synthetic_frames") or []) if isinstance(name, str)
    )
    synthetic_present = tuple(name for name in registry if name in present)
    synthetic_missing = tuple(name for name in registry if name not in present)
    missing_pages: tuple[int, ...] = ()
    if reconstruction is not None:
        missing_pages = tuple(
            int(index)
            for index in (reconstruction.get("missing_pages") or [])
            if isinstance(index, int) and not isinstance(index, bool)
        )
    found = len(sequence.names)
    return CompletenessVerdict(
        expected=expected,
        found=found,
        synthetic_present=synthetic_present,
        synthetic_missing=synthetic_missing,
        missing_pages=missing_pages,
        complete=expected is not None and expected == found,
    )


@dataclass(frozen=True)
class _DigestFrame:
    """Une ligne de la recette d'empreinte, et rien d'autre."""

    output_rank: int
    frame_timecode: str


@dataclass(frozen=True)
class _DigestView:
    """Vue minimale d'une selection, telle que la recette d'empreinte la lit.

    `extraction_manifest.compute_frame_timecodes_digest` ne lit que quatre
    choses: `rounding_policy`, `timecode_base`, `timecode_base_fps` et, par
    frame, `output_rank` et `frame_timecode`. Les quatre vivent sur `lots[]` (le
    manifest reel les porte sur les deux lots scannes du depot) et les rangs
    sont les positions dans la sequence triee.

    Une vue, et non une `FrameSelection` reconstituee: la selection porte une
    dizaine d'autres champs -- `fps_source`, `source_index`, `source_tail_frames`
    -- que ce module ne connait pas et qu'il faudrait inventer. Une valeur
    inventee dans un objet qui se presente comme une selection finirait par etre
    lue par autre chose que la recette. Ce qui compte est que la **recette**
    reste unique et importee, jamais retapee ici.
    """

    frames: tuple[_DigestFrame, ...]
    rounding_policy: str
    timecode_base: str
    timecode_base_fps: str


#: Champs d'en-tete de la recette d'empreinte (story 3.4). Sans les trois,
#: l'empreinte n'est pas recalculable et la confrontation ne se fait pas.
DIGEST_HEADER_FIELDS: tuple[str, ...] = (
    "rounding_policy",
    "timecode_base",
    "timecode_base_fps",
)


def confront_selection_identity(
    lot: Mapping[str, Any], sequence: SequencePlan
) -> None:
    """Confronter l'**identite** de la sequence, pas seulement son cardinal.

    Le verdict de completude compte des fichiers; il ne dit rien de savoir si ce
    sont les bons. Mesure du 2026-08-10 sur le lot reel a 5 frames: un seul
    fichier renomme vers un timecode etranger a la selection, et la commande
    annoncait "5 conformes pour 5 attendues" puis encodait. La conformite passe
    en effet par `is_conforming_scan_frame_name(nom, rush_id, fps_target)`,
    c'est-a-dire **rush + cadence** et jamais le lot: deux lots du meme rush a la
    meme cadence produisent des noms identiques.

    Or le manifest porte deux confrontations plus fortes, et gratuites:

    * les **bornes** du lot, `first_frame_timecode` / `last_frame_timecode`;
    * le **`frame_timecodes_digest`**, dont la recette canonique vit dans
      `io/extraction_manifest.compute_frame_timecodes_digest` et qui "change si
      un timecode change, si l'ordre change". Recalcul verifie sur le materiau
      reel du depot: les deux lots scannes (`TEST_FILE_12p5` a 13 frames dont
      deux mires, `rush_test_235_1920x817_25fps_1` a 5) rendent l'empreinte
      **exactement** persistee.

    Les deux ne valent que sur un lot dont le cardinal correspond: sur un lot
    troue assume, elles divergent par construction, et c'est le constat de
    completude qui parle. L'appelant ne l'invoque donc que sur un lot complet.
    """
    if not sequence.timecodes:
        return
    for field, observed, place in (
        ("first_frame_timecode", sequence.timecodes[0], "premiere"),
        ("last_frame_timecode", sequence.timecodes[-1], "derniere"),
    ):
        declared = lot.get(field)
        if declared and not _same_timecode(str(declared), observed):
            raise EncodeDecisionError(
                ENCODE_BOUNDS_MISMATCH,
                f"Le lot {lot.get('lot_id')!r} declare {field} = {declared!r} et sa "
                f"{place} frame conforme porte {observed!r}. Le cardinal correspond, "
                "la selection non: le dossier contient des frames qui ne sont pas "
                "celles de ce lot.",
            )
    persisted = lot.get("frame_timecodes_digest")
    if not persisted or any(not lot.get(field) for field in DIGEST_HEADER_FIELDS):
        return
    view = _DigestView(
        frames=tuple(
            _DigestFrame(output_rank=rank, frame_timecode=timecode)
            for rank, timecode in enumerate(sequence.timecodes)
        ),
        rounding_policy=str(lot["rounding_policy"]),
        timecode_base=str(lot["timecode_base"]),
        timecode_base_fps=str(lot["timecode_base_fps"]),
    )
    recomputed = extraction_manifest.compute_frame_timecodes_digest(view)
    if recomputed != persisted:
        raise EncodeDecisionError(
            ENCODE_DIGEST_MISMATCH,
            f"L'empreinte de selection recalculee depuis le dossier du lot "
            f"{lot.get('lot_id')!r} vaut {recomputed} et le manifest declare "
            f"{persisted}. Le cardinal correspond, la selection non: un timecode "
            "ou un ordre a change depuis l'extraction.",
        )


def enforce_completeness(
    verdict: CompletenessVerdict, lot_id: str, *, accept_incomplete: bool
) -> list[str]:
    """Appliquer le verdict et rendre les constats informatifs a rapporter.

    Quatre issues, la quatrieme n'etant pas prevue par la story et pourtant
    atteignable: un fichier de nom conforme mais de timecode etranger au lot
    fait **depasser** le cardinal attendu. Le taire reviendrait a encoder une
    sequence dont personne n'a valide la composition.
    """
    if verdict.expected is None:
        raise EncodeDecisionError(
            ENCODE_EXPECTED_COUNT_INDETERMINABLE,
            f"Le lot {lot_id!r} ne porte aucun `expected_frame_count`: il n'est "
            "pas ecrit quand la derniere page manque, et aucun cardinal de "
            "reference n'existe alors. Encoder reviendrait a declarer complete "
            "une sequence dont personne ne connait la longueur.",
        )
    if verdict.found > verdict.expected:
        raise EncodeDecisionError(
            ENCODE_UNEXPECTED_FRAMES,
            f"Le lot {lot_id!r} porte {verdict.found} frames conformes pour un "
            f"cardinal attendu de {verdict.expected}: {verdict.found - verdict.expected} "
            "de trop. Le dossier contient des frames qui n'appartiennent pas a "
            "cette selection.",
        )
    findings: list[str] = []
    if verdict.found < verdict.expected:
        detail = (
            f"pages manquantes (index): {', '.join(str(i) for i in verdict.missing_pages)}"
            if verdict.missing_pages
            else "les index de page manquants ne sont pas connus (la section "
            "`reconstruction` ne decrit pas ce lot)"
        )
        orphans = (
            f" Noms au registre des mires sans fichier sur le disque: "
            f"{', '.join(verdict.synthetic_missing)}."
            if verdict.synthetic_missing
            else ""
        )
        message = (
            f"Le lot {lot_id!r} est troue: {verdict.found} frames conformes pour "
            f"{verdict.expected} attendues, soit {verdict.expected - verdict.found} "
            f"manquante(s). {detail}.{orphans} Les timecodes des frames manquantes "
            "n'existent nulle part: aucun timecode ne peut etre recalcule pour une "
            "page absente."
        )
        if not accept_incomplete:
            raise EncodeDecisionError(ENCODE_LOT_INCOMPLETE, message)
        findings.append(ENCODE_INCOMPLETE_ACCEPTED)
    if verdict.synthetic_present:
        findings.append(ENCODE_SYNTHETIC_FRAMES_PRESENT)
    return findings


# --------------------------------------------------------------------------
# Cadence et timecode (AC 9, AC 10)
# --------------------------------------------------------------------------


def resolve_frame_rate(lot: Mapping[str, Any]) -> tuple[float, str]:
    """Rendre `(fps_target brut, cadence exacte)` du lot.

    **Portee retrecie par la story 6.6.** `fps_target` n'est plus la cadence de
    mux du master (voir `resolve_source_rate`): c'est desormais un parametre de
    **selection** exclusivement, qui sert ici a deux fins qui n'ont rien a voir
    avec la cadence d'encodage -- retrouver, par son nom, les frames que
    `plan_sequence` doit matcher sur le disque (la convention de nommage encode
    `fps_target`, jamais la cadence source), et alimenter le tag conteneur
    documentaire `fps_target` (`build_container_tags`, matrice 2.4: ce tag
    documente la decimation d'origine, pas la cadence reellement muxee). Cette
    fonction ne decide donc plus de rien qui touche a `-r`.
    """
    fps_target = lot.get("fps_target")
    if not is_strict_number(fps_target):
        raise EncodeDecisionError(
            ENCODE_FRAME_RATE_UNUSABLE,
            f"Le lot {lot.get('lot_id')!r} ne porte pas de `fps_target` numerique: "
            f"{fps_target!r}. La convention de nom des frames n'a alors aucune "
            "source. L'etat du lot n'est pas en cause.",
        )
    try:
        exact = codec_profiles.exact_frame_rate(fps_target)
    except (ValueError, TypeError, ZeroDivisionError, OverflowError) as exc:
        # `fps_target` a 0, negatif, `NaN` ou `1e-7` remontait une `ValueError`
        # **nue** hors de la hierarchie du module. Le schema l'intercepte au
        # niveau CLI (`minimum: 0` mesure), mais la fonction est publique.
        raise EncodeDecisionError(
            ENCODE_FRAME_RATE_UNUSABLE,
            f"Le lot {lot.get('lot_id')!r} porte une `fps_target` inexploitable "
            f"({fps_target!r}): {exc}",
        ) from exc
    return float(fps_target), exact


def resolve_source_rate(
    lot: Mapping[str, Any], *, cadence_source_override: object = None
) -> tuple[float, str, str | None]:
    """Rendre `(cadence source effective brute, cadence exacte, note)` du lot (AC 1bis).

    **C'est cette cadence, et plus jamais `fps_target`, qui mux le master**
    (story 6.6, `EPIC6-ARB-6`) -- mesure: un lot livre a `fps_target` alors
    qu'il n'a pas ete tenu (frames dedoublees) n'est pas defilable image par
    image dans DaVinci Resolve, qui arrondit toute cadence non entiere au
    plafond pour son champ de timecode et cale son pas de defilement sur cet
    arrondi plutot que sur la cadence reelle du conteneur.

    Trois cas, aucun ne devine:

    * `lot["timecode_base_fps"]` present, `cadence_source_override` absent ->
      c'est la cadence source effective, sans intervention de l'operateur;
    * absent, `cadence_source_override` fourni -> c'est la cadence source
      effective, completee explicitement par l'operateur (`encode
      --cadence-source`), jamais devinee;
    * absent, rien fourni -> refus nomme (`ENCODE_SOURCE_RATE_MISSING`). Aucun
      repli silencieux sur `fps_target`: c'est exactement la degradation que
      cette story corrige.

    **Le quatrieme cas -- les deux presents -- n'est plus un refus depuis la
    story 2.7** (payload 2.1, `EPIC7-ARB-56` / AC epics 2.7, qui renverse le
    refus `ENCODE_SOURCE_RATE_REDUNDANT` pose par 6.6): l'**option prime**,
    parce que le papier ne se met pas a jour (`EPIC7-ARB-51`) -- une cadence
    source fausse imprimee sur une planche ne peut etre corrigee qu'a
    l'encodage. `note` (troisieme element du tuple rendu) porte alors
    l'avertissement structure qui nomme les **deux** valeurs et leur
    provenance (valeur du lot ecartee, valeur de l'option retenue); `None`
    dans les trois autres cas.
    """
    # Story 6.6, corrige apres la revue en trois couches (Edge Case Hunter,
    # finding 4): la premiere ecriture testait `bool(base) or (isinstance(...)
    # and base > 0)` -- la seconde clause etait du code mort (un int/float > 0
    # est deja truthy), ce qui laissait passer `base=True` comme "present" au
    # lieu de l'exclure comme prevu, et classait `base=0` comme **absent**
    # plutot que **present mais inexploitable** -- incoherent avec
    # `resolve_frame_rate`, qui traite `fps_target=0` comme present-et-refuse
    # (`ENCODE_FRAME_RATE_UNUSABLE`), jamais comme absent. Presence = la cle
    # porte une valeur non-`None`, point. La validite (type, signe, fini) est
    # entierement laissee a `exact_frame_rate` ci-dessous, exactement comme
    # `resolve_frame_rate` le fait deja pour `fps_target`.
    base = lot.get("timecode_base_fps")
    has_base = base is not None
    has_override = cadence_source_override is not None
    # Revue de vague 0 (Epic 7): `lot_id` peut etre absent ou vide sur un lot
    # dont l'identite manque -- l'avertissement structure ci-dessous doit
    # rester lisible ("lot None: ...") plutot que d'exposer le `None` brut.
    lot_id = lot.get("lot_id") or "<identite absente>"
    note: str | None = None
    if has_base and has_override:
        # Story 2.7 (EPIC7-ARB-56): plus un refus -- l'option **prime**, avec un
        # avertissement structure qui nomme les deux valeurs et leur provenance
        # au lieu d'un ecrasement muet.
        note = (
            f"lot {lot_id!r}: cadence source du lot ({base!r}, portee par le "
            f"QR/manifest) ecartee ; cadence source de --cadence-source retenue "
            f"({cadence_source_override!r})"
        )
        raw = cadence_source_override
    elif not has_base and not has_override:
        raise EncodeDecisionError(
            ENCODE_SOURCE_RATE_MISSING,
            f"Le lot {lot_id!r} ne porte pas `timecode_base_fps` (planche "
            "imprimee en payload 2.0, avant la story 2.7, ou manifest "
            "reconstruit d'une source autre que le scan ou l'extraction). La "
            "cadence source du master n'a alors aucune valeur: completer "
            "explicitement avec `--cadence-source <cadence>` (decimale ou "
            "'num/den'), jamais un repli automatique sur `fps_target`.",
        )
    else:
        raw = base if has_base else cadence_source_override
    try:
        exact = codec_profiles.exact_frame_rate(raw)
    except (ValueError, TypeError, ZeroDivisionError, OverflowError) as exc:
        raise EncodeDecisionError(
            ENCODE_FRAME_RATE_UNUSABLE,
            f"Le lot {lot_id!r} porte une cadence source inexploitable ({raw!r}): "
            f"{exc}",
        ) from exc
    return float(Fraction(exact)), exact, note


def _hold_counts(
    timecodes: Sequence[str], *, rate: str, source_tail_frames: int | None
) -> list[int]:
    """Combien de fois tenir chaque frame retenue, dans l'ordre (AC 3, AC 5).

    `hold_count(n) = index(timecodes[n+1]) - index(timecodes[n])` pour toutes
    les frames sauf la derniere -- l'ecart entre deux timecodes consecutifs,
    deja en base source (fait verifie sur un lot reel: le nom de chaque frame
    porte son timecode en base source, jamais en base `fps_target`). Verrouille
    par la garantie deja existante de `frame_selection.py`: cet ecart vaut
    toujours `floor(k)` ou `ceil(k)` (`k = fps_source/fps_target`), jamais autre
    chose -- constant quand `k` est entier (12,5 ; 25/3 ; 25/4 ...), alternant
    entre les deux sinon (20 ; 15 ...).

    La derniere frame couvre `1 + source_tail_frames` quand ce champ est connu
    sur le lot (formule `EPIC6-ARB-6`) -- sinon `1`, sans queue devinee:
    `source_tail_frames` n'a pas d'equivalent au QR (aucun octet ne le
    justifie: la derniere frame d'une planche scannee n'a pas besoin d'etre
    tenue plus longtemps pour etre reconnue) et reste donc **propre a
    l'extraction** meme depuis que la story 2.7 fait porter
    `timecode_base_fps` par un lot ne du scan seul. L'absence d'information se
    traite comme "rien a ajouter", jamais comme une invitation a extrapoler.

    Sequence vide -> liste vide. Sequence d'une seule frame -> `[1 +
    source_tail_frames]` ou `[1]`: aucun ecart a mesurer, seule la queue compte.

    **Deux gardes ajoutees apres la revue en trois couches (Edge Case Hunter,
    findings 1 et 3), aucune des deux ne devinant quoi que ce soit -- elles
    refusent au lieu de perdre une image sans le dire**:

    * `source_tail_frames` illisible en entier (manifest corrompu, ex.
      chaine non numerique) leve `ENCODE_SOURCE_TAIL_FRAMES_UNUSABLE` au lieu
      d'un `ValueError` nu hors de la hierarchie du module;
    * tout `hold_count` calcule non strictement positif -- rate fourni
      (`--cadence-source`) plus bas que la cadence reellement encodee dans
      les noms de frame, ou `source_tail_frames` negatif -- leve
      `ENCODE_HOLD_COUNT_NOT_POSITIVE`. Sans cette garde, `range(count)` est
      silencieusement vide pour un `count <= 0` et la frame disparait du
      master sans qu'aucun signal ne le dise: mesure, `_hold_counts(["00:00:00:25",
      "00:00:01:00"], rate="24/1", ...)` rend `[-1, 1]`, qui aurait efface la
      premiere frame.
    """
    if not timecodes:
        return []
    if source_tail_frames is None:
        tail = 0
    else:
        try:
            tail = int(source_tail_frames)
        except (TypeError, ValueError) as exc:
            raise EncodeDecisionError(
                ENCODE_SOURCE_TAIL_FRAMES_UNUSABLE,
                f"`source_tail_frames` inexploitable ({source_tail_frames!r}): {exc}",
            ) from exc
    indices = [codec_profiles.timecode_to_frame_index(tc, rate) for tc in timecodes]
    counts = [indices[i + 1] - indices[i] for i in range(len(indices) - 1)]
    counts.append(1 + tail)
    invalid = [count for count in counts if count < 1]
    if invalid:
        raise EncodeDecisionError(
            ENCODE_HOLD_COUNT_NOT_POSITIVE,
            f"Maintien de frame non strictement positif calcule ({invalid}), a la "
            f"cadence {rate!r}: une frame disparaitrait du master sans aucun "
            "signal. Cause probable: la cadence source fournie (--cadence-source) "
            "est plus basse que celle reellement encodee dans les noms de frame, "
            "ou `source_tail_frames` est negatif sur un manifest corrompu.",
        )
    return counts


def frames_per_timecode_second(rate: str) -> int:
    """Nombre d'images que compte **une seconde de timecode** a `rate`.

    Convention d'ffmpeg, mesuree et non supposee: le champ `ff` compte jusqu'a
    `ceil(rate) - 1`, ce qui est exactement la borne que
    `codec_profiles.validate_timecode` applique. A 12,5 im/s une seconde de
    timecode compte donc **13** images -- et n'est, de ce fait, pas une seconde
    de temps reel. C'est ce decalage qui rend la question de sens du timecode de
    depart non triviale: voir `express_timecode_in_master_base`.
    """
    fraction = Fraction(rate)
    return -(-fraction.numerator // fraction.denominator)  # ceil


# Retrait du 2026-08-10: `timecode_field_width` vivait ici et n'a plus
# d'appelant. Elle calculait la largeur d'ecriture du champ `ff` par ffmpeg
# pour alimenter une abstention hors de la fenetre `11 <= ceil(cadence) <= 100`
# -- abstention levee ci-dessous. La **mesure** qu'elle portait n'est pas
# perdue: elle est canonique dans `codec_profiles.timecode_frame_field_width`
# (story 6.0, commit `8713094`), qui est la seule a en avoir besoin puisque
# c'est la fabrique qui confronte le timecode relu. En garder une copie morte
# ici ferait vivre le meme fait a deux endroits, avec le risque habituel: une
# remesure corrige l'un et pas l'autre.


def express_timecode_in_master_base(timecode: str, master_rate: str) -> str | None:
    """Re-exprimer le timecode de depart dans la base du master, ou rendre `None`.

    **La premisse de la revision precedente etait fausse, et elle a ete
    remesuree.** Cette fonction s'appelait `convert_timecode_base` et faisait une
    regle de trois sur les images, au motif que "ffmpeg ne recopie pas
    `-timecode`, il le re-rend a la cadence de sortie". Mesure du 2026-08-10,
    encodages reels a `-r 25/2` puis relecture du `tmcd`::

        -timecode 00:00:00:04  ->  00:00:00:04
        -timecode 00:00:00:12  ->  00:00:00:12
        -timecode 00:00:02:00  ->  00:00:02:00
        -timecode 01:00:00:00  ->  01:00:00:00
        -timecode 00:00:00:14  ->  00:00:01:01     <-- le seul qui bouge

    ffmpeg rend **verbatim** tout timecode legal. Le seul qui bouge est celui
    dont le champ `ff` **deborde** la borne de la base cible (`ff` plafonne a 12
    a 12,5 im/s): c'est une normalisation de debordement, pas un rescalage. La
    mesure unique dont la premisse etait tiree portait sur ce cas-la, et elle
    avait ete generalisee a tort. Cout du defaut, mesure: un rush partant a
    `01:00:00:00` ressortait tague `00:57:41:07`, soit 2 min 19 s d'ecart --
    `90000 / 25 * 12,5 = 45000` images, puis `45000 / 13 = 3461,5 s`, la
    conversion melangeant le compte `ceil` et le taux exact dans une seule
    formule.

    **Decision de sens, tranchee ici et pas laissee implicite.**
    `first_frame_timecode` est exprime dans `timecode_base_fps`, qui peut
    differer de la cadence du master (c'est le cas de **tous** les lots du depot:
    base `25/1`, cadences cibles 1, 5, 10, 12,5, 15). Quand les deux bases
    different, deux reponses sont defendables et elles divergent, parce qu'a
    12,5 im/s une seconde de timecode compte 13 images et n'est donc pas une
    seconde de temps reel (`frames_per_timecode_second`):

    * **preserver l'instant** -- convertir en temps reel puis re-exprimer:
      `01:00:00:00` en base `25/1` vers `25/2` donne `00:57:41:07`. La position
      sur la timeline en images du master est juste, et l'etiquette ne designe
      plus rien de reconnaissable;
    * **preserver l'etiquette (l'identite de l'image)** -- le timecode nomme
      *cette image physique de la source*, propriete que la chaine tient depuis
      la selection ("la meme image physique porte toujours le meme timecode,
      quelle que soit la cadence d'extraction", `frame_selection.py:93-98`).

    **C'est l'etiquette qui est retenue**, pour une raison mesurable et une
    raison d'usage. Mesurable: ffmpeg ecrit la valeur telle quelle, donc rien
    n'oblige a la transformer -- la transformation etait la reponse a un fait qui
    n'existe pas. D'usage: la reinjection sert a raccrocher le master au rush
    d'origine en post-production, et un master annonce a `00:57:41:07` pour un
    rush a `01:00:00:00` ne raccroche a rien. La cadence propre du master porte
    ensuite le temps reel de la sequence; seule l'origine est etiquetee ici.

    Consequence assumee: une etiquette dont le champ `ff` n'existe pas dans la
    base du master (`00:00:00:16` vers 15 im/s, ou `ff` plafonne a 14) **n'est
    pas representable**. Aucune autre valeur n'est alors emise -- en ecrire une
    autre serait ecrire une autre etiquette, c'est-a-dire designer une autre
    image. La fonction rend `None`, l'appelant nomme le fait
    (`ENCODE_TIMECODE_START_OUT_OF_BASE`) et le master sort sans timecode.

    Si les deux bases sont egales, la valeur ressort donc **verbatim**, sans
    calcul: c'est un cas particulier de la regle, jamais une branche a part.
    """
    parts = timecode.split(":")
    if len(parts) != 4:
        raise ValueError(
            f"Timecode {timecode!r}: quatre champs hh:mm:ss:ff attendus."
        )
    frames = int(parts[3])
    if frames >= frames_per_timecode_second(master_rate):
        return None
    return timecode


@dataclass(frozen=True)
class TimecodePlan:
    """Ce qui sera pose en `-timecode`, et d'ou ca vient."""

    emitted: str | None
    manifest_value: str | None = None
    base_rate: str | None = None
    findings: tuple[str, ...] = ()


def plan_timecode(
    lot: Mapping[str, Any],
    sequence: SequencePlan,
    *,
    master_rate: str,
) -> TimecodePlan:
    """Resoudre le timecode de depart, sa base et son expression (AC 10).

    Trois cas, dans cet ordre, et aucun ne devine:

    * `lots[].timecode_base_fps` existe (lot ne de l'extraction, ou -- depuis
      la story 2.7, payload 2.1 -- lot ne du scan d'une planche imprimee sous
      2.1) -> on l'emploie comme base de **validation**;
    * absent (planche imprimee en payload 2.0, avant la story 2.7, ou manifest
      reconstruit d'une source qui ne l'ecrit pas) -> **aucun timecode
      reinjecte**, fait nomme, jamais devine;
    * le depart vient de `lots[].first_frame_timecode` s'il existe, sinon de la
      premiere frame **presente**.

    La garde de depart non canonique confronte le depart retenu a
    `sequence.timecodes[0]`, c'est-a-dire a la premiere frame **reellement
    presente sur le disque**, et rien d'autre. Elle etait auparavant conditionnee
    a l'absence de `first_frame_timecode`: le seul producteur du depot ecrit ce
    champ et `timecode_base_fps` sur deux lignes consecutives
    (`io/extraction_manifest.py:825-826`), la branche n'etait donc pas
    productible, et le cas reel -- un trou en tete sous
    `--accept-incomplete-lot` -- passait par la branche muette. Mesure du
    2026-08-10 sur `TEST_FILE_12p5` prive de sa premiere frame: le master
    relisait `00:00:00:00` alors que sa premiere image etait `00:00:00:02`.

    Le cardinal n'entre plus dans cette garde: un lot peut etre complet en
    cardinal et decale en tete (une frame surnumeraire en compense une
    manquante), et un lot troue en queue est parfaitement canonique en tete.
    Seule la confrontation des timecodes repond a la question posee.

    **Levee du 2026-08-10 -- il n'y a plus d'abstention de cadence.** Cette
    fonction refusait de reinjecter tout timecode hors de la fenetre
    `11 <= ceil(cadence du master) <= 100`, sous le constat
    `TIMECODE_NON_REINJECTABLE_A_CETTE_CADENCE`. Le motif etait reel au moment
    ou il a ete pose: ffmpeg ecrit le champ `ff` sur `len(str(ceil(cadence) -
    1))` chiffres, `validate_timecode` n'acceptait que deux chiffres et
    `verify_encoded_output` comparait des **chaines** -- un master juste etait
    refuse. Ce motif a disparu avec la correction de la story 6.0 (commit
    `8713094`): la confrontation porte desormais sur l'**image designee**
    (`codec_profiles.timecodes_equivalent`) et non sur l'ecriture.

    Le repli n'etait donc plus une prudence, c'etait une perte seche: il privait
    de tout timecode les lots a 1, 5 et 10 im/s, soit **trois des cinq cadences
    reelles du projet** -- le stop-motion, qui est le coeur de cible. Mesure du
    2026-08-10 rejouee sur cette branche, encodages ProRes reels relus a
    `ffprobe`, `-timecode` demande contre `tmcd` relu::

        1/1   `00:00:00:00` -> `00:00:00:0`   accepte
        5/1   `00:00:00:04` -> `00:00:00:4`   accepte
        10/1  `00:00:00:09` -> `00:00:00:9`   accepte
        25/1  `00:00:00:14` -> `00:00:00:14`  accepte   (temoin dans la fenetre)
        25/2  `00:00:00:12` -> `00:00:00:12`  accepte   (temoin a 12,5 im/s)
        120/1 `00:00:00:99` -> `00:00:00:099` accepte

    et, aux six memes cadences, un timecode qui designe une **autre image** est
    toujours refuse par `verify_encoded_output`, un `ff` hors bornes toujours
    refuse avant l'encodage. Ce qui est absorbe est la largeur d'ecriture, rien
    d'autre.
    """
    base = lot.get("timecode_base_fps")
    if not base:
        return TimecodePlan(emitted=None, findings=(ENCODE_NO_TIMECODE,))
    # Aucune garde de cadence ici, et c'est une **levee** datee du 2026-08-10,
    # motivee et mesuree dans la docstring ci-dessus. Les deux abstentions qui
    # subsistent portent sur le **sens** -- pas de base de timecode au lot,
    # etiquette non representable dans la base du master -- jamais sur la
    # mise en forme du champ de frames.
    findings: list[str] = []
    first_present = sequence.timecodes[0] if sequence.timecodes else None
    start = lot.get("first_frame_timecode") or first_present
    if not start:
        return TimecodePlan(emitted=None, findings=(ENCODE_NO_TIMECODE,))
    if first_present is not None and not _same_timecode(str(start), first_present):
        findings.append(ENCODE_TIMECODE_NOT_LOT_START)
    try:
        base_rate = codec_profiles.exact_frame_rate(base)
        # Validation contre la base **du manifest**, jamais contre la cadence
        # d'encodage: un lot a 4 im/s depuis une source a 30 porte des `ff`
        # jusqu'a 29, parfaitement legaux et pourtant rejetes par `ceil(4)`.
        codec_profiles.validate_timecode(str(start), base_rate)
        emitted = express_timecode_in_master_base(str(start), master_rate)
    except (ValueError, TypeError, ZeroDivisionError) as exc:
        raise EncodeDecisionError(
            ENCODE_TIMECODE_UNCONVERTIBLE,
            f"Timecode de depart {start!r} inexploitable en base {base!r} vers la "
            f"cadence du master {master_rate}: {exc}",
        ) from exc
    if emitted is None:
        # L'etiquette n'existe pas dans la base du master. En emettre une autre
        # designerait une autre image: on n'en emet aucune, et on le dit.
        findings.append(ENCODE_TIMECODE_START_OUT_OF_BASE)
        return TimecodePlan(
            emitted=None,
            manifest_value=str(start),
            base_rate=base_rate,
            findings=tuple(findings),
        )
    codec_profiles.validate_timecode(emitted, master_rate)
    return TimecodePlan(
        emitted=emitted,
        manifest_value=str(start),
        base_rate=base_rate,
        findings=tuple(findings),
    )


def _same_timecode(left: str, right: str) -> bool:
    """Deux timecodes designent-ils la meme image ?

    Comparaison sur les **champs decodes** et non sur les chaines: le manifest et
    le nom de fichier sont produits par deux recettes distinctes, et une
    difference de remplissage (`0:0:0:2` contre `00:00:00:02`) ferait crier une
    garde qui n'a rien a signaler. Une chaine non decodable retombe sur l'egalite
    litterale plutot que de lever: la garde informe, elle ne refuse pas.
    """
    try:
        return _timecode_sort_key(left) == _timecode_sort_key(right)
    except ValueError:
        return left == right


# --------------------------------------------------------------------------
# Tags de conteneur (AC 11)
# --------------------------------------------------------------------------


def build_container_tags(
    manifest: Mapping[str, Any],
    lot: Mapping[str, Any],
    *,
    profile_id: str,
    frame_rate: str,
    frame_timecode: str | None,
) -> dict[str, str]:
    """Calculer le jeu de tags **depuis** la matrice 2.4, jamais en le retapant.

    `io/metadata_matrix` est la transcription executable de la matrice de
    responsabilite; elle connait le canal `VIDEO_CONTAINER` et, par champ,
    `REQUIRED` / `OPTIONAL` / `FORBIDDEN`. Le jeu est **derive** par `is_allowed`
    sur le precedent explicite de `video_metadata.py:190-195` -- module qui
    derive ses classifications au lieu de les retaper, precisement parce qu'une
    version retapee avait fini par contredire la matrice faisant autorite.

    Consequence directe et verifiable: `lot_id` est `FORBIDDEN` au conteneur
    video et n'est donc **jamais** tague, si evident qu'il paraisse de le poser.

    Calculer des valeurs ne franchit pas la frontiere de l'AC 18: cette fonction
    ne construit aucun argv, elle rend un dictionnaire que la fabrique 6.0
    traduit.
    """
    channel = metadata_matrix.Channel.VIDEO_CONTAINER
    candidates: dict[str, str | None] = {
        "project_id": _as_tag(manifest.get("project_id")),
        "rush_id": _as_tag(lot.get("rush_id")),
        "lot_id": _as_tag(lot.get("lot_id")),
        "fps_target": frame_rate,
        "codec_target_profile": profile_id,
        "frame_timecode": frame_timecode,
    }
    tags = {
        name: value
        for name, value in candidates.items()
        if value and metadata_matrix.is_allowed(name, channel)
    }
    missing = [
        name
        for name in metadata_matrix.known_fields()
        if metadata_matrix.get_cell(name, channel).responsibility
        is metadata_matrix.Responsibility.REQUIRED
        and name not in tags
    ]
    if missing:
        raise EncodeDecisionError(
            ENCODE_MATRIX_FIELD_MISSING,
            f"Champs exiges au conteneur video par la matrice 2.4 et sans valeur: "
            f"{', '.join(sorted(missing))}. L'etat du lot n'est pas en cause.",
        )
    return tags


def _as_tag(value: Any) -> str | None:
    """Rendre une valeur de tag exploitable, ou `None`.

    Une valeur vide produit un fichier ou le tag est simplement absent, `rc=0`,
    sans avertissement: indistinguable d'une reinjection ratee. Elle est donc
    ecartee ici plutot que passee a la fabrique, qui la refuserait.
    """
    if value is None:
        return None
    text = str(value).strip()
    return text or None


# --------------------------------------------------------------------------
# Plan complet et recapitulatif (AC 12, AC 14)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class EncodePlan:
    """Tout ce que la commande a decide, avant d'ecrire le moindre octet."""

    project_dir: Path
    lot_id: str
    lot_state: str
    profile_id: str
    container: str
    resolution: TargetResolution
    source_size: tuple[int, int]
    frame_paths: tuple[Path, ...]
    frame_rate: float
    exact_frame_rate: str
    timecode: TimecodePlan
    verdict: CompletenessVerdict
    container_tags: dict[str, str]
    output_path: Path
    overwrite: bool
    #: Story 6.6, AC 2/AC 3. Frames telles que **muxees**: chaque frame de
    #: `frame_paths` y apparait `hold_count(n)` fois consecutives, a la cadence
    #: source effective (`frame_rate`/`exact_frame_rate`, plus jamais
    #: `fps_target`). `frame_paths`, lui, garde son sens actuel -- les frames
    #: **distinctes retenues** par la selection, utilise par le verdict de
    #: completude et l'estimation de poids -- jamais les deux confondus.
    muxed_frame_paths: tuple[Path, ...] = ()
    findings: tuple[str, ...] = ()
    nonconforming: tuple[str, ...] = ()
    #: Noms de 0 octet ecartes de la sequence (artefacts d'une passe interrompue).
    empty_files: tuple[str, ...] = ()
    #: Bornes **declarees** par le lot, telles quelles, jamais recalculees.
    declared_bounds: tuple[str | None, str | None] = (None, None)
    #: Timecodes de la sequence retenue, dans l'ordre encode. Ils rendent les
    #: bornes reelles affichables au recapitulatif, en face des declarees.
    sequence_timecodes: tuple[str, ...] = ()
    #: Ce que la correction couleur a fait, tel que le manifest le declare (AC 11 de
    #: 5.19). Porte sur le plan et non recalcule au rendu, comme tout le reste du
    #: recapitulatif: `render_summary` ne relit aucun document.
    calibration_summary: str = ""
    #: Story 2.7 (EPIC7-ARB-56): note structuree, non vide seulement quand
    #: `--cadence-source` a ecrase une `timecode_base_fps` deja portee par le
    #: lot -- nomme les **deux** valeurs et leur provenance (troisieme element
    #: rendu par `resolve_source_rate`). Hors du vocabulaire ferme des constats
    #: (`ENCODE_CODES`), delibere: `encode_previz.py` en porte un miroir
    #: litteral que cette story ne touche pas (voir `ENCODE_SOURCE_RATE_REDUNDANT`),
    #: donc ce champ transporte le detail nomme sans y ajouter de code.
    source_rate_override_note: str = ""
    #: Rang de version du MASTER que ce plan va ecrire (`EPIC11-ARB-91`),
    #: `None` au rang d'origine. Distinct du rang du LOT, qui vit deja dans
    #: `lot_id`. Il est **decide une seule fois**, par `plan_encode`, et
    #: transporte de la : le nom du fichier et l'entree d'inventaire le lisent
    #: tous deux ici, sans jamais le recalculer -- deux calculs pourraient
    #: diverger, et le manifeste declarerait alors un rang que le fichier ne
    #: porte pas.
    master_version_rank: int | None = None
    #: Story 6.8 (`EPIC11-ARB-190`). Le dossier de la reconstruction que
    #: l'operateur a **designee**, relatif au projet -- vide quand aucune
    #: designation n'a ete faite, c'est-a-dire quand la derniere passe a servi.
    #:
    #: **Le vide n'est pas une commodite, c'est ce qui tient un observable.**
    #: `render_summary` n'emet sa ligne que si ce champ est non vide, si bien
    #: qu'un encodage sans designation rend le recapitulatif d'avant cette
    #: story, au caractere pres -- ce que le dossier d'identite d'`encode`
    #: (25 invocations reelles, `stdout` fige) exige.
    reconstruction_designee: str = ""

    @property
    def masters_family_key(self) -> str:
        """La cle de famille sous laquelle la LIGNE D'EAU de ce master se range.

        Portee par le plan plutot que recalculee par la persistance: la
        frontiere de la story 5.11 interdit a `io.encode_manifest` de nommer
        `build_master_filename`, et le motif vaut ici -- un module de
        persistance qui recalcule une cle peut la faire diverger de celle
        contre laquelle le rang a ete resolu. `encode` decide, la persistance
        lit.
        """
        return cle_de_famille_de_master(
            self.profile_id, resolution_name_segment(self.resolution)
        )

    @property
    def frame_count(self) -> int:
        return len(self.frame_paths)

    @property
    def estimated_bytes(self) -> int:
        """Ordre de grandeur **majorant** du poids du master.

        Question ouverte 2, tranchee: oui, mais en ordre de grandeur
        explicitement approximatif et **jamais optimiste** (sens d'erreur impose
        par le Piege 12 de la story 3.3). La borne est celle du debit non
        compresse de l'espace de sortie, qui majore tous les profils du
        catalogue: annoncer moins ferait decouvrir le disque plein a la fin.

        **Corrige apres la revue en trois couches de la story 6.6** (Edge Case
        Hunter, finding 2): le compte qui compte est celui reellement muxe
        (`muxed_frame_paths`, avec les frames tenues), pas le compte
        **distinct** retenu par la selection (`frame_count`) -- sinon
        l'estimation redevient optimiste (violant son propre contrat) d'un
        facteur egal au maintien moyen, exactement sur le cas nominal de cette
        story (un lot decime). Repli sur `frame_count` pour un `EncodePlan`
        construit hors de `plan_encode` (qui ne peuple jamais
        `muxed_frame_paths`).
        """
        width, height = self.resolution.size or self.source_size
        muxed_count = len(self.muxed_frame_paths) or self.frame_count
        return width * height * 3 * muxed_count


def cle_de_famille_de_master(profile_id: str, resolution_segment: str | None) -> str:
    """La cle sous laquelle la ligne d'eau d'un master est rangee.

    Le profil ET la resolution, parce que deux masters d'un lot qui different
    par l'un ou l'autre ne sont PAS deux versions l'un de l'autre : la story
    6.1 produit deux sorties voulues pour le meme lot, et les confondre ferait
    numeroter `_v2` un premier encodage en ProRes HQ au motif qu'un ProRes 422
    existe.
    """
    return profile_id if not resolution_segment else f"{profile_id}|{resolution_segment}"


def masters_version_watermark(
    manifest: Mapping[str, Any],
    lot_id: str,
    *,
    profile_id: str,
    container: str,
    resolution_segment: str | None = None,
) -> int:
    """Le plus haut rang de master JAMAIS employe pour cette famille.

    `EPIC11-ARB-92`, etendu aux masters par Egan le 2026-08-31. **Un rang se
    consomme** : retirer le master de rang 2 alors que le 3 existe ne rend pas
    le 2. Le motif, etendu depuis les planches : un master livre a un client a
    quitte le disque comme une planche quitte l'imprimante, et un rang qui
    ressort ment sur ce qu'il designe.

    Se lit au manifeste ; a defaut (manifeste anterieur) elle se DEDUIT du plus
    haut rang declare a l'inventaire -- exact pour tout historique ou aucun
    rang de queue n'a ete retire, et prudent partout ailleurs.
    """
    lot = next(
        (l for l in (manifest.get("lots") or [])
         if isinstance(l, Mapping) and l.get("lot_id") == lot_id),
        None,
    )
    cle = cle_de_famille_de_master(profile_id, resolution_segment)
    lignes = (lot or {}).get(encode_manifest.MASTERS_WATERMARK_FIELD)
    declaree = lignes.get(cle) if isinstance(lignes, Mapping) else None
    return version_ranks.ligne_d_eau(
        declaree,
        _rangs_de_masters(lot, lot_id, profile_id, container, resolution_segment),
    )


def _rangs_de_masters(
    lot: Mapping[str, Any] | None,
    lot_id: str,
    profile_id: str,
    container: str,
    resolution_segment: str | None,
) -> set[int]:
    """Les rangs declares a l'inventaire pour cette famille de master.

    LE RANG VIENT DU MANIFESTE, ET DE LUI SEUL. Le nom ne sert qu'a dire si
    l'entree appartient a la meme famille -- la resolution n'etant pas un champ
    de l'inventaire (elle est lisible du fichier ; la persister creerait une
    seconde verite), le nom est son seul porteur.
    """
    rangs: set[int] = set()
    for entree in (lot or {}).get("encoded_masters") or []:
        if not isinstance(entree, Mapping):
            continue
        rang = entree.get(encode_manifest.MASTER_VERSION_RANK_FIELD)
        rang = rang if isinstance(rang, int) and not isinstance(rang, bool) else 1
        chemin = entree.get(encode_manifest.MASTER_INVENTORY_KEY)
        if not isinstance(chemin, str) or not chemin:
            continue
        base_attendue = naming.build_master_filename(
            lot_id=lot_id, profile_id=profile_id, container=container,
            resolution_segment=resolution_segment,
        )
        nom = PurePosixPath(chemin).name
        suffixe = "" if rang == 1 else naming.format_version_suffix(rang)
        tige, _, extension = nom.rpartition(".")
        if suffixe and tige.endswith(suffixe):
            tige = tige[: -len(suffixe)]
        if f"{tige}.{extension}" == base_attendue:
            rangs.add(rang)
    return rangs


def resolve_master_version_rank(
    manifest: Mapping[str, Any],
    lot_id: str,
    *,
    profile_id: str,
    container: str,
    resolution_segment: str | None = None,
) -> int:
    """Le rang du PROCHAIN master de cette famille : la ligne d'eau plus un.

    **Ce resolveur vit dans `encode`, pas dans `encode_manifest`** : la
    frontiere statique de la story 5.11 interdit a `encode_manifest` de nommer
    `build_master_filename`, et le motif tient -- un module de PERSISTANCE qui
    recalcule un identifiant peut le faire diverger de celui qui a ete ecrit.

    **Ce n'est plus « le premier rang libre »** (`EPIC11-ARB-92`). La redaction
    d'origine rendait le TROU ; Egan l'a corrige et etendu aux trois objets
    versionnables. Le calcul lui-meme vit dans `io.version_ranks`, ecrit une
    fois pour les trois.
    """
    if not (manifest.get("lots") or []):
        return version_ranks.RANG_ORIGINE
    lot = next(
        (l for l in manifest["lots"]
         if isinstance(l, Mapping) and l.get("lot_id") == lot_id),
        None,
    )
    cle = cle_de_famille_de_master(profile_id, resolution_segment)
    lignes = (lot or {}).get(encode_manifest.MASTERS_WATERMARK_FIELD)
    declaree = lignes.get(cle) if isinstance(lignes, Mapping) else None
    rangs = _rangs_de_masters(lot, lot_id, profile_id, container, resolution_segment)
    if not rangs and not isinstance(declaree, int):
        # Aucun master de cette famille, jamais : le prochain est l'ORIGINE.
        return version_ranks.RANG_ORIGINE
    rang = version_ranks.prochain_rang(version_ranks.ligne_d_eau(declaree, rangs))
    if rang > naming.VERSION_RANK_MAX:
        raise EncodeDecisionError(
            ENCODE_MASTER_RANKS_EXHAUSTED,
            version_ranks.refus_de_rangs_epuises(
                f"master, profil {profile_id!r}", lot_id,
                # Le geste FIN existe depuis `EPIC11-ARB-111`, livre par le
                # meme diff que ce message : la redaction d'avant affirmait
                # qu'"aucune commande ne supprime un master seul" et envoyait
                # detruire un lot entier de plusieurs Go pour rien.
                #
                # **L'issue se DESIGNE par les arguments qui ont produit le
                # master** (`EPIC11-ARB-224`), et cette ligne-ci etait la
                # SEULE des quatre refus jumeaux a avoir garde son chemin :
                # `--master` est devenu un drapeau nu dans le meme diff, si
                # bien qu'`argparse` rendait `unrecognized arguments` (code 2)
                # sur la premiere issue -- et que meme sans le jeton parasite
                # le coeur refusait, `--profile` etant desormais exige. Des
                # deux issues annoncees, seule la DESTRUCTRICE restait
                # jouable : le blocage sec deguise que `scan_ingest` nomme mot
                # pour mot, et une contradiction frontale de la clause
                # centrale du contrat, « aucun chemin, jamais ».
                #
                # Le profil est INTERPOLE plutot que laisse en gabarit : il
                # est en portee, c'est lui dont les rangs sont epuises, et un
                # refus qui nomme l'objet reel vaut mieux qu'un patron a
                # remplir. `--resolution` n'y figure pas -- le contrat ne
                # l'exige que lorsqu'il LEVE une ambiguite, et dans ce cas
                # c'est `_famille_de_master` qui la nomme, avec les
                # resolutions declarees par le lot.
                f"Deux issues: supprimer le DERNIER master de cette famille en "
                f"liberant son rang (`mmu project remove --lot <id> --master "
                f"--profile {profile_id} --version <rang> --liberer-le-rang "
                f"--confirmer`, qui ne retire que ce master), ou ecraser "
                f"sciemment un master existant "
                f"(--overwrite).",
            ),
        )
    return rang


def build_master_output_path(
    project_dir: Path,
    lot_id: str,
    profile: codec_profiles.EncodeProfile,
    resolution: TargetResolution,
    version_rank: int | None = None,
) -> Path:
    """Chemin complet du master: `outputs/<nom construit par io/naming>`.

    `version_rank` est le rang du MASTER (`EPIC11-ARB-91`), **transporte tel
    quel** jusqu'a `build_master_filename` -- ce module decide du rang, il ne
    fabrique pas le fragment de nom. Il vaut `None` au rang d'origine, seule
    valeur que `format_version_suffix` accepte de ne pas ecrire (le rang 1 y
    est refuse nommement).

    **Ce parametre existait au nommage et n'atteignait jamais le nom** : la
    mesure du 2026-09-02 comptait zero site d'appel passant `version_rank`,
    si bien que `--nouvelle-version` aurait resolu un rang 2 pour ecrire, sous
    le nom du rang 1, par-dessus le master existant -- c'est-a-dire la
    destruction que l'option existe pour eviter.
    """
    filename = naming.build_master_filename(
        lot_id=lot_id,
        profile_id=profile.profile_id,
        container=profile.container,
        resolution_segment=resolution_name_segment(resolution),
        version_rank=version_rank,
    )
    return project_layout.outputs_dir(project_dir) / filename


def render_summary(plan: EncodePlan) -> str:
    """Recapitulatif emis **avant** d'encoder (AC 14).

    L'encodage est l'operation la plus couteuse de la chaine: le lot reel du
    depot pese 146 Mo pour 13 frames, et un lot de production en compte
    plusieurs centaines. Le recapitulatif n'est donc pas du confort.
    """
    width, height = plan.resolution.size or plan.source_size
    lines = [
        "Recapitulatif de l'encodage (rien n'a encore ete ecrit)",
        f"  Lot                 : {plan.lot_id} (etat {plan.lot_state})",
        f"  Profil              : {plan.profile_id} -> conteneur .{plan.container}",
        f"  Resolution          : {width}x{height} "
        f"({plan.resolution.origin}"
        f"{'' if plan.resolution.resolution_id is None else ', ' + plan.resolution.resolution_id}"
        f"), source {plan.source_size[0]}x{plan.source_size[1]}",
        # Story 6.6: la cadence est desormais la cadence SOURCE effective, pas
        # `fps_target` -- et les frames retenues sont tenues autant de fois
        # que necessaire pour la restituer (AC 1, AC 2). L'ancienne mention
        # "aucune repetition d'images" decrivait le contraire de ce que fait
        # ce plan des que le lot a ete decime.
        f"  Cadence             : {plan.exact_frame_rate} im/s "
        f"({len(plan.muxed_frame_paths)} echantillon(s) au master pour "
        f"{plan.frame_count} frame(s) distincte(s) retenue(s))",
        f"  Frames              : {plan.frame_count} conformes pour "
        f"{'cardinal inconnu' if plan.verdict.expected is None else str(plan.verdict.expected) + ' attendues'}",
        f"  Mires               : {len(plan.verdict.synthetic_present)} "
        f"(encodees telles quelles)",
    ]
    if plan.reconstruction_designee:
        # Story 6.8: la ligne n'est emise QUE si une passe a ete designee. Sans
        # designation, le recapitulatif est celui d'avant la story, au caractere
        # pres -- ce que le dossier d'identite d'`encode` exige. Et quand une
        # passe est designee, la taire priverait l'operateur du seul moyen de
        # verifier ce qu'il vient de demander.
        lines.append(f"  Reconstruction      : {plan.reconstruction_designee} (designee)")
    if plan.source_rate_override_note:
        # Story 2.7 (EPIC7-ARB-56): avertissement structure -- l'option a
        # ecrase la cadence source du lot, jamais un ecrasement muet.
        lines.append(f"  Cadence source      : {plan.source_rate_override_note}")
    if plan.verdict.synthetic_present and len(plan.verdict.synthetic_present) == plan.frame_count:
        lines.append(
            "  Attention           : ce lot est constitue a 100 % de mires de "
            "synthese; le master ne portera aucune image reellement scannee."
        )
    if plan.timecode.emitted is None:
        # Deux motifs seulement depuis la levee du 2026-08-10: l'etiquette
        # n'existe pas dans la base du master, ou le lot ne porte pas de base du
        # tout. Le troisieme -- "la cadence n'est pas confrontable" -- annoncait
        # une abstention qui n'a plus lieu (voir `plan_timecode`).
        if ENCODE_TIMECODE_START_OUT_OF_BASE in plan.findings:
            motif = (
                f"le depart {plan.timecode.manifest_value} n'existe pas dans la base "
                f"du master ({plan.exact_frame_rate}: le champ de frames y plafonne "
                f"a {frames_per_timecode_second(plan.exact_frame_rate) - 1}); en "
                "emettre un autre designerait une autre image"
            )
        else:
            motif = (
                "le lot ne porte pas de `timecode_base_fps` (planche imprimee "
                "en payload 2.0, avant la story 2.7, ou manifest reconstruit "
                "d'une source qui ne l'ecrit pas)"
            )
        lines.append(f"  Timecode            : aucun ({motif})")
    else:
        lines.append(
            f"  Timecode            : {plan.timecode.emitted} "
            f"(depuis {plan.timecode.manifest_value} en base "
            f"{plan.timecode.base_rate}; l'etiquette designe l'image source et "
            "sort verbatim, jamais rescalee)"
        )
    lines.extend(
        [
            f"  Sortie              : {plan.output_path}"
            f"{' (ecrasement demande)' if plan.overwrite else ''}",
            f"  Poids attendu       : environ {_format_bytes(plan.estimated_bytes)} "
            "au plus (ordre de grandeur majorant, jamais optimiste)",
            f"  Colorimetrie        : {SRGB_APPROXIMATION_NOTE}",
            # Deux lignes et non une (AC 11 de 5.19): celle du dessus parle de la courbe
            # de transfert de l'espace de sortie, celle-ci de la correction active. Les
            # avoir fondues est ce qui avait rendu la premiere fausse.
            f"  Correction couleur  : "
            f"{plan.calibration_summary or calibration_summary_line({})}",
        ]
    )
    if plan.nonconforming:
        lines.append(
            f"  Fichiers ecartes    : {len(plan.nonconforming)} nom(s) non "
            f"conforme(s) au lot, dont {plan.nonconforming[0]}"
        )
    if plan.empty_files:
        lines.append(
            f"  Fichiers vides      : {len(plan.empty_files)} fichier(s) de 0 octet "
            f"ecarte(s), dont {plan.empty_files[0]} (artefact d'une passe "
            "interrompue, jamais une frame)"
        )
    if plan.sequence_timecodes:
        # Les bornes sont au recapitulatif parce que c'est le seul endroit ou
        # l'operateur peut voir que la sequence trouvee n'est pas celle que le
        # manifest decrit -- un cardinal juste ne dit rien de l'identite.
        declared_first, declared_last = plan.declared_bounds
        declared = (
            f", manifest {declared_first or 'inconnue'} -> {declared_last or 'inconnue'}"
            if declared_first or declared_last
            else ", manifest muet sur les bornes"
        )
        lines.append(
            f"  Bornes              : {plan.sequence_timecodes[0]} -> "
            f"{plan.sequence_timecodes[-1]} (sequence trouvee){declared}"
        )
    for code in plan.findings:
        lines.append(f"  Constat             : {code}")
    return "\n".join(lines)


def _format_bytes(size: int) -> str:
    """Rendre un poids en unite lisible, en ASCII strict."""
    value = float(size)
    for unit in ("o", "Ko", "Mo", "Go"):
        if value < 1024 or unit == "Go":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} Go"


# --------------------------------------------------------------------------
# Assemblage du plan
# --------------------------------------------------------------------------


def plan_encode(
    project_dir: Path,
    manifest: Mapping[str, Any],
    *,
    lot_id: str,
    profile_id: str = codec_profiles.DEFAULT_PROFILE_ID,
    resolution: str | None = None,
    overwrite: bool = False,
    nouvelle_version: bool = False,
    accept_incomplete: bool = False,
    cadence_source_override: object = None,
    reconstruction_visee: object = None,
    ffprobe_bin: str = "ffprobe",
) -> EncodePlan:
    """Decider tout ce qui peut l'etre avant d'ecrire le moindre octet.

    L'ordre des gardes n'est pas cosmetique: le lot, puis sa matiere, puis la
    sequence, puis le verdict, puis les formes -- chaque etape ne parle que de
    ce que la precedente a etabli, et aucune ne lit un fichier avant d'etre sure
    que le lot est le bon.

    ``cadence_source_override`` porte le ``--cadence-source`` de la CLI
    (story 6.6, AC 1bis): decimal ou ``'num/den'``, transmis tel quel a
    ``resolve_source_rate``, qui tranche seul s'il est acceptable, redondant ou
    manquant.

    ``nouvelle_version`` porte le ``--nouvelle-version`` de la CLI (story 11.8,
    AC 4.1/4.2, `EPIC11-ARB-89`), et il est **exclusif** d'``overwrite``: ce
    sont les deux issues du meme conflit d'ecriture, jamais deux a la fois --
    l'une ecrit a cote sans toucher a ce qui existe, l'autre detruit
    sciemment. Pose, le rang du prochain master de la famille est resolu par
    `resolve_master_version_rank` contre le manifeste **existant** (la ligne
    d'eau plus un, `EPIC11-ARB-92`), puis transporte jusqu'au nom du fichier
    et jusqu'a l'entree d'inventaire.

    **Resoudre un rang n'en consomme aucun** (AC 4.4): cette fonction n'ecrit
    rien. La ligne d'eau ne monte qu'a la declaration au manifeste, apres
    l'ecriture reelle -- monter trois fois un ecran de conflit et l'annuler
    trois fois laisse donc la ligne d'eau ou elle etait.
    """
    project_dir = Path(project_dir)
    # Story 11.8, AC 4.1 (`EPIC11-ARB-89`), sur le modele litteral du refus
    # d'`extraction.run_extraction`: deux issues DISTINCTES du meme conflit
    # d'ecriture ne se combinent pas. Le refus est le tout premier geste de la
    # fonction -- avant le catalogue de profils, avant le registre de
    # resolutions, avant la moindre lecture du manifeste -- parce qu'aucune de
    # ces etapes ne peut rendre la combinaison licite, et qu'un refus paye
    # apres un `ffprobe` serait un refus paye trop cher.
    if nouvelle_version and overwrite:
        raise EncodeDecisionError(
            ENCODE_VERSION_AND_OVERWRITE,
            "--nouvelle-version et --overwrite sont deux issues DISTINCTES du "
            "meme conflit d'ecriture et ne se combinent pas: la premiere ecrit "
            "un master de rang voisin (le master present reste intact), la "
            "seconde ecrase le master present. Choisir l'une des deux. Rien "
            "n'a ete encode.",
        )
    profile = codec_profiles.get_profile(profile_id)
    target = resolve_output_resolution(resolution)

    lot = select_lot(manifest, lot_id)
    resolved_lot_id = str(lot.get("lot_id"))
    # Story 6.8: la designation se resout **ici**, exactement la ou la garde
    # d'admission etait deja appelee. Ni plus haut -- aucune etape amont ne
    # rendrait licite une passe qui n'existe pas --, ni plus bas, le balayage du
    # dossier suivant immediatement.
    lot_dir = check_lot_admission(
        lot, project_dir, reconstruction_visee=reconstruction_visee)

    # `fps_target`/`exact_rate`: parametre de SELECTION uniquement depuis la
    # story 6.6 -- ils servent au nommage des frames (`plan_sequence` ci-dessous)
    # et au tag conteneur documentaire (`build_container_tags`), jamais a la
    # cadence de mux. `source_rate`/`source_rate_exact`: la cadence source
    # EFFECTIVE, celle qui mux desormais le master (AC 1, AC 1bis) -- refuse tot,
    # avant toute lecture du disque, si elle n'est ni portee par le lot ni
    # completee par l'operateur.
    fps_target, exact_rate = resolve_frame_rate(lot)
    source_rate, source_rate_exact, source_rate_override_note = resolve_source_rate(
        lot, cadence_source_override=cadence_source_override
    )
    rush_id = str(lot.get("rush_id") or "")
    if not rush_id:
        raise EncodeDecisionError(
            ENCODE_RUSH_ID_ABSENT,
            f"Le lot {resolved_lot_id!r} ne declare aucun `rush_id`: la convention "
            "de nom des frames scannees n'est alors pas reconstructible. L'etat "
            "du lot n'est pas en cause.",
        )

    entries = sorted(
        (entry for entry in lot_dir.iterdir() if entry.is_file()), key=lambda e: e.name
    )
    names = [entry.name for entry in entries]
    # La taille est lue **ici**, pas dans la fonction de plan, qui reste pure:
    # un fichier de 0 octet sous un nom conforme est un artefact d'ecriture
    # interrompue, pas une frame.
    empty_names = [entry.name for entry in entries if entry.stat().st_size == 0]
    sequence = plan_sequence(
        names, rush_id=rush_id, fps_target=fps_target, empty_names=empty_names
    )
    if not sequence.names:
        raise EncodeDecisionError(
            ENCODE_OUTPUT_DIR_EMPTY,
            f"Le lot scanne {lot_dir} ne porte aucune frame conforme au lot "
            f"{resolved_lot_id!r} ({len(names)} fichier(s) present(s)). Rescanner "
            "le lot avant d'encoder.",
        )

    findings: list[str] = []
    reconstruction = reconstruction_for_lot(manifest, resolved_lot_id)
    if reconstruction is None and isinstance(manifest.get("reconstruction"), Mapping):
        findings.append(ENCODE_RECONSTRUCTION_OTHER_LOT)

    # Franchissement de 24 h: il ne se voit pas sur le disque, dont les noms sont
    # a largeur fixe et se trient donc toujours "dans l'ordre". Les deux seules
    # suites dont l'ordre chronologique est connu par ailleurs sont les bornes du
    # lot et les emplacements de `reconstruction` lorsqu'elle decrit ce lot.
    bounds = [
        str(lot[field])
        for field in ("first_frame_timecode", "last_frame_timecode")
        if lot.get(field)
    ]
    check_chronology(bounds, origin=f"les bornes du lot {resolved_lot_id!r}")
    if reconstruction is not None:
        slots = sorted(
            (slot for slot in (reconstruction.get("slots") or []) if isinstance(slot, Mapping)),
            key=lambda slot: slot.get("slot_index", 0),
        )
        check_chronology(
            [str(slot.get("frame_timecode")) for slot in slots if slot.get("frame_timecode")],
            origin=f"les emplacements de `reconstruction` du lot {resolved_lot_id!r}",
        )

    verdict = assess_completeness(lot, sequence, reconstruction)
    findings.extend(
        enforce_completeness(verdict, resolved_lot_id, accept_incomplete=accept_incomplete)
    )
    if verdict.complete:
        # Le cardinal est le bon: c'est le seul cas ou l'identite de la selection
        # est confrontable. Sur un lot troue assume, bornes et empreinte
        # divergent par construction et c'est le constat d'incompletude qui parle.
        confront_selection_identity(lot, sequence)
    if sequence.nonconforming:
        findings.append(ENCODE_NONCONFORMING_FILES)
    if sequence.empty:
        findings.append(ENCODE_EMPTY_FILES)
    findings.append(ENCODE_SRGB_APPROXIMATION)
    findings.extend(confront_project_colorspace(manifest, profile))

    frame_paths = tuple(lot_dir / name for name in sequence.names)
    # Homogeneite verifiee **avant** l'appel a la fabrique (AC 7): 6.0 recoit une
    # liste de chemins et fige la geometrie sur la premiere entree, les suivantes
    # etant redimensionnees en silence sans que le cardinal ne bouge. La garde de
    # 6.0 est la derniere, celle-ci est la premiere -- et c'est elle qui ferme le
    # renvoi nommement adresse a l'Epic 6 par le `deferred-work.md`.
    try:
        source_size = codec_profiles.ensure_uniform_frame_shapes(
            frame_paths, ffprobe_bin=ffprobe_bin
        )
    except codec_profiles.EncodeConfigurationError as exc:
        raise EncodeDecisionError(ENCODE_HETEROGENEOUS_SHAPES, str(exc)) from exc

    settled = settle_resolution(target, source_size)
    try:
        codec_profiles.check_target_dimensions(profile, *settled.size)
    except codec_profiles.EncodeConfigurationError as exc:
        raise EncodeDecisionError(ENCODE_UNKNOWN_RESOLUTION, str(exc)) from exc
    if not _same_aspect_ratio(source_size, settled.size):
        findings.append(ENCODE_ASPECT_RATIO_CHANGED)

    # Story 6.6, AC 1/AC 6: le timecode de depart se valide et s'exprime
    # desormais contre la cadence source EFFECTIVE, plus jamais `fps_target` --
    # c'est elle qui mux le master, donc c'est sa base que `-timecode` doit
    # respecter.
    timecode = plan_timecode(lot, sequence, master_rate=source_rate_exact)
    findings.extend(timecode.findings)

    # `frame_rate=exact_rate` (fps_target) ici: tag conteneur **documentaire**
    # (matrice 2.4, cle `fps_target`), qui decrit la decimation d'origine et
    # n'a jamais decrit la cadence de mux -- ne pas le confondre avec
    # `source_rate_exact`, ci-dessous sur `EncodePlan.exact_frame_rate`.
    tags = build_container_tags(
        manifest,
        lot,
        profile_id=profile.profile_id,
        frame_rate=exact_rate,
        frame_timecode=timecode.emitted,
    )
    # Story 11.8, AC 4.2. Le rang se resout **ici**, apres `settled`: la cle de
    # famille porte la resolution, et la resolution n'est connue qu'une fois la
    # cible confrontee a la taille source (`settle_resolution`). La resoudre
    # plus haut la rangerait sous la cle de la resolution DEMANDEE, qui n'est
    # pas toujours celle qui sera ecrite -- deux masters de la meme famille
    # tomberaient alors sous deux lignes d'eau.
    master_version_rank: int | None = None
    if nouvelle_version:
        rang = resolve_master_version_rank(
            manifest,
            resolved_lot_id,
            profile_id=profile.profile_id,
            container=profile.container,
            resolution_segment=resolution_name_segment(settled),
        )
        # Le rang d'origine ne porte AUCUN fragment de nom, et
        # `format_version_suffix` refuse nommement le rang 1. Demander une
        # nouvelle version d'une famille qui n'a encore aucun master n'est pas
        # une erreur -- il n'y a simplement rien a versionner -- et le nom
        # ordinaire est le bon.
        master_version_rank = None if rang == version_ranks.RANG_ORIGINE else rang
    output_path = build_master_output_path(
        project_dir, resolved_lot_id, profile, settled, version_rank=master_version_rank
    )
    # Refus de destination **avant** le recapitulatif et avant tout encodage: il
    # ne sert a rien d'annoncer une operation dont la sortie est deja occupee.
    check_output_destination(output_path, overwrite=overwrite)

    # Story 6.6, AC 2/AC 3: chaque frame retenue est tenue hold_count(n) fois --
    # la liste muxee n'est jamais la liste distincte. `sequence.timecodes` est
    # deja en base source (mesure sur un lot reel) et deja dans l'ordre de
    # `frame_paths`, construits ensemble par `plan_sequence`.
    #
    # **Garde trouvee en integration, hors AC ecrites, et necessaire**: sur un
    # lot INCOMPLET (page perdue, `--accept-incomplete-lot`), l'ecart entre
    # deux timecodes retenus consecutifs ne distingue pas un ecart de
    # decimation normal d'un trou de contenu reel. Appliquer `_hold_counts`
    # tel quel y tiendrait une frame plus longtemps pile a l'endroit du trou --
    # c'est-a-dire combler un manque par la repetition de l'image precedente,
    # exactement ce que ce module interdit ailleurs en toutes lettres
    # (`--accept-incomplete-lot`: "aucun trou n'est jamais comble par
    # repetition de l'image precedente"). Sur un lot incomplet, aucune frame
    # n'est donc tenue (`hold_count(n) = 1` partout): le master degrade en
    # duree exactement a l'endroit du trou, plutot que d'inventer une image.
    if verdict.complete:
        hold_counts = _hold_counts(
            sequence.timecodes,
            rate=source_rate_exact,
            source_tail_frames=lot.get("source_tail_frames"),
        )
    else:
        hold_counts = [1] * len(sequence.timecodes)
    muxed_frame_paths = tuple(
        path for path, count in zip(frame_paths, hold_counts) for _ in range(count)
    )

    return EncodePlan(
        project_dir=project_dir,
        lot_id=resolved_lot_id,
        lot_state=str(lot.get("state")),
        profile_id=profile.profile_id,
        container=profile.container,
        resolution=settled,
        source_size=source_size,
        frame_paths=frame_paths,
        muxed_frame_paths=muxed_frame_paths,
        frame_rate=source_rate,
        exact_frame_rate=source_rate_exact,
        timecode=timecode,
        verdict=verdict,
        container_tags=tags,
        output_path=output_path,
        overwrite=overwrite,
        findings=tuple(findings),
        nonconforming=sequence.nonconforming,
        empty_files=sequence.empty,
        declared_bounds=(
            lot.get("first_frame_timecode"),
            lot.get("last_frame_timecode"),
        ),
        sequence_timecodes=sequence.timecodes,
        calibration_summary=calibration_summary_line(lot),
        source_rate_override_note=source_rate_override_note or "",
        master_version_rank=master_version_rank,
        # Story 6.8. Le dossier REELLEMENT retenu, releve sur `lot_dir` plutot
        # que sur la designation brute: un rang et un dossier designent la meme
        # passe, et le plan doit dire la passe, pas la facon de l'avoir nommee.
        reconstruction_designee=(
            "" if reconstruction_visee is None
            else lot_dir.relative_to(project_dir).as_posix()
        ),
    )


# --------------------------------------------------------------------------
# Execution (AC 13, AC 15)
# --------------------------------------------------------------------------


def check_output_destination(
    output_path: Path, *, overwrite: bool
) -> None:
    """Refuser la destination **sans rien creer**, et avant le recapitulatif.

    Trois refus, trois codes, et aucun des trois n'ecrit quoi que ce soit: un
    **fichier** deja present a l'emplacement du dossier de sortie (que
    `mkdir(parents=True, exist_ok=True)` rendrait en `FileExistsError` nu), le
    chemin du master occupe par un **repertoire**, et un master deja present sans
    `--overwrite`. Tous font echouer la commande **avant tout encodage** --
    jamais apres avoir lu 900 frames.

    Le cas du repertoire est mesure, et il coutait cher: `--overwrite` sur une
    cible qui est un dossier payait l'encodage complet, puis la bascule levait
    `IsADirectoryError`, rendue par la CLI en "verifier l'espace disponible et
    les droits d'ecriture" -- diagnostic faux -- en laissant un fichier d'attente
    de la taille d'un master. La garde porte donc sur la cible et pas seulement
    sur son parent, et elle ne depend **pas** de `--overwrite`: un repertoire ne
    s'ecrase pas.

    Separee de `prepare_output_directory` parce que l'ordre compte: un refus en
    amont ne doit laisser **aucun** fichier ni dossier derriere lui, pas meme un
    `outputs/` vide cree pour rien.
    """
    directory = output_path.parent
    if directory.exists() and not directory.is_dir():
        raise EncodeDecisionError(
            ENCODE_OUTPUTS_IS_A_FILE,
            f"{directory} existe et n'est pas un dossier: le master ne peut pas y "
            "etre ecrit. Deplacer ou renommer ce fichier.",
        )
    if output_path.is_dir():
        raise EncodeDecisionError(
            ENCODE_MASTER_IS_A_DIRECTORY,
            f"{output_path} existe et est un repertoire: le master ne peut pas "
            "prendre sa place, et --overwrite n'ecrase pas un dossier. Deplacer ou "
            "renommer ce repertoire. Rien n'a ete encode.",
        )
    if output_path.exists() and not overwrite:
        # TROIS issues, jamais une seule (`EPIC11-ARB-89`). La redaction
        # d'origine ne proposait que `--overwrite`, c'est-a-dire la
        # destruction comme unique sortie -- exactement ce que l'arbitrage
        # interdit. Ce qui bloquait la mise en conformite jusqu'ici etait de
        # savoir si la convention `_v2` se transposait a un master ;
        # `EPIC11-ARB-91` l'a tranche : elle s'y transpose, le nom portant
        # deja le profil et la resolution, un `_v2` y est univoque.
        raise EncodeDecisionError(
            ENCODE_MASTER_ALREADY_PRESENT,
            f"Le master {output_path} existe deja. Trois issues: relancer avec "
            "--nouvelle-version pour ecrire une version voisine sans toucher a "
            "celle-ci; relancer avec --overwrite pour l'ecraser sciemment; ou "
            "supprimer ce qui est devenu inutile "
            "(`mmu project remove --lot <id>`, qui retire le lot et tous ses "
            "masters). Rien n'a ete encode.",
        )


def prepare_output_directory(plan: EncodePlan) -> list[Path]:
    """Creer `outputs/` et balayer les residus, une fois l'accord donne.

    Deux pannes ordinaires que `mkdir` rend en trace Python nue: un projet en
    lecture seule et un disque plein.
    """
    directory = plan.output_path.parent
    check_output_destination(plan.output_path, overwrite=plan.overwrite)
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise EncodeDecisionError(
            ENCODE_DESTINATION_NOT_WRITABLE,
            f"Destination inutilisable: {directory} ({exc}).",
        ) from exc
    # Balayage des residus d'un encodage **tue** (SIGTERM/SIGKILL, contre
    # lesquels aucun `finally` de Python ne se deroule). Ils sont caches, portent
    # l'extension du conteneur, et `Path.glob('*.mov')` les matche: pour tout
    # inventaire du depot, un temporaire perime est un master.
    return codec_profiles.sweep_encode_residues(directory)


def _staged_output_path(plan: EncodePlan) -> Path:
    """Chemin du master **en attente de verification**, voisin de sa cible.

    6.0 verifie son propre cardinal sur son temporaire avant bascule, mais elle
    bascule ensuite vers le chemin qu'on lui donne: elle n'expose aucun point ou
    faire passer la verification technique de l'AC 15. Cette story encode donc
    vers un chemin d'attente, verifie, puis bascule elle-meme -- sans quoi un
    master valide serait remplace par un fichier que la commande vient de
    declarer non conforme, l'AC 13 disant l'inverse dans son propre titre.

    La forme du nom est celle que `codec_profiles.sweep_encode_residues` sait
    reconnaitre (`.<tronc>.<pid>-<12 hex>.<conteneur>`): un fichier d'attente
    oublie apres un diagnostic reste balayable, et il est cache, donc absent des
    inventaires de masters.

    **Le tronc, et non le nom complet** (corrige le 2026-09-06, sur retour
    d'Egan qui a du supprimer a la main un
    `.TEST_FILE_7p5_mmu_dnxhr_hqx.mov.2624-0d2c0cbf1e1c.mov`). Le nom complet
    portait deja l'extension du conteneur, que la forme rajoute en queue: le
    fichier d'attente sortait donc en **double extension**, illisible et
    inquietant pour qui le trouve.

    Ce qui NE bouge pas, et il faut dire pourquoi, parce que les deux morceaux
    restants ont l'air tout aussi ornementaux:

    * **l'extension de queue est obligatoire.** `run_encode` appelle
      `check_output_extension` sur ce chemin-la et refuse toute extension qui
      contredit le conteneur du profil -- un chemin d'attente sans extension,
      ou en `.tmp`, ne s'encode pas du tout;
    * **`<pid>-<12 hex>` est ce que le balayage reconnait.**
      `codec_profiles._TEMP_NAME_RE` vaut `\\.\\d+-[0-9a-f]{12}(\\.[^.]+)?$`:
      raccourcir l'empreinte, ou la remplacer par autre chose que des chiffres
      suivis de douze hexa, rend le residu **non balayable** -- c'est-a-dire un
      fichier cache de la taille d'un master que tout inventaire du depot
      compte comme un master.

    Le confort qui reste a gagner n'est donc pas dans le nom: c'est que le
    refus **propose** la suppression au lieu de laisser l'operateur la faire a
    la main. Cela appartient a l'ecran de refus, pas a cette fonction.
    """
    unique = f"{os.getpid()}-{uuid.uuid4().hex[:12]}"
    return plan.output_path.parent / f".{plan.output_path.stem}.{unique}.{plan.container}"


def reserve_master_path(plan: EncodePlan) -> bool:
    """Reserver **atomiquement** la cible avant l'encodage, et dire si on l'a fait.

    C'est le bloquant que la revue a trouve deux fois, independamment. La story
    6.0 a construit `_reserve_output_path` (`O_CREAT | O_EXCL`) precisement pour
    fermer la course entre deux encodages -- et 6.1 encodait vers un chemin
    d'attente **prive**, donc la reservation ne portait que sur un chemin que
    personne ne disputait: la cible, elle, n'etait plus protegee par rien. Le
    `os.replace` final ne relisait ni `overwrite` ni l'existence de la cible.

    Mesure du 2026-08-10, deux `encode` simultanes sur le meme lot: `rc=0` des
    deux cotes, "Master ecrit" des deux cotes, **un** seul fichier -- et chacun
    affichait sa description d'encodage, dont l'une decrivait un fichier qui
    n'existait plus. Mesure jumelle: un master pose entre le plan et la bascule
    etait detruit **sans `--overwrite`**. La fenetre valait toute la duree de
    l'encodage (6 s mesurees pour 13 frames en `uhd2160`, donc des minutes sur un
    lot de production).

    Le geste: poser la cible en `O_CREAT | O_EXCL` **avant** d'encoder, puis
    basculer par-dessus sa propre reservation. La creation et le test d'existence
    sont alors le meme appel systeme, et le second encodage recoit
    `MASTER_DEJA_PRESENT` au lieu de detruire le premier.

    Deux consequences assumees, dites plutot que decouvertes:

    * un fichier de **0 octet** occupe le nom du master pendant l'encodage. C'est
      exactement ce que fait deja 6.0 pour son propre appel, et le `finally` de
      `execute_plan` le retire des que l'encodage echoue. Un `SIGKILL` en laisse
      un: la relance suivante le refuse sous `MASTER_DEJA_PRESENT`, refus
      correct puisque le nom est bien pris, et `--overwrite` le leve;
    * en `overwrite=True`, **aucune** reservation: on ne pose pas `O_EXCL` sur un
      fichier qu'on vient d'accepter d'ecraser. Deux appelants en `--overwrite`
      sur la meme cible restent une course gagnee par le dernier -- contrat que
      6.0 declare deja pour ce mode, et qui est ce que le drapeau demande.
    """
    if plan.overwrite:
        return False
    try:
        handle = os.open(plan.output_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError as exc:
        # Story 11.8, AC 4.7. **Deux issues, dont une non destructive**, la ou
        # ce refus n'en offrait qu'une -- et elle detruisait. Il etait recense
        # dans `DETTES_CONNUES` sous le motif d'`EPIC11-ARB-107` (« la commande
        # a deja propose ses issues a son entree ; ce refus-ci ne se declenche
        # que si le fichier est apparu DEPUIS, donc la bonne reponse est
        # "recommencez" et non un menu »). Ce motif tient, et il DICTE la
        # seconde issue au lieu de l'interdire : relancer la commande resout a
        # nouveau le rang contre le manifeste, donc contre le master que
        # l'autre passe vient d'y declarer. Ce que l'arbitrage ecartait etait
        # de proposer un RANG calcule ici -- il pourrait etre pris a son tour
        # -- pas de nommer la relance elle-meme.
        raise EncodeDecisionError(
            ENCODE_MASTER_ALREADY_PRESENT,
            f"Le master {plan.output_path} existe deja: un autre encodage l'a "
            "pose entre la decision et l'ecriture. Deux issues: relancer la "
            "commande telle quelle (le rang de version sera resolu a nouveau "
            "contre le manifeste, qui porte desormais ce master), ou relancer "
            "avec --overwrite pour l'ecraser sciemment. Rien n'a ete encode.",
        ) from exc
    except IsADirectoryError as exc:
        raise EncodeDecisionError(
            ENCODE_MASTER_IS_A_DIRECTORY,
            f"{plan.output_path} existe et est un repertoire: le master ne peut pas "
            "prendre sa place. Rien n'a ete encode.",
        ) from exc
    except OSError as exc:
        raise EncodeDecisionError(
            ENCODE_DESTINATION_NOT_WRITABLE,
            f"Chemin de sortie inutilisable: {plan.output_path} ({exc}).",
        ) from exc
    os.close(handle)
    return True


def expected_technical_metadata(plan: EncodePlan) -> dict[str, Any]:
    """Ce que le master **doit** porter, en vocabulaire de `video_metadata`.

    Au minimum `MANDATORY_TECHNICAL_FIELDS`: une demande qui les omet rend une
    verification vide de sens, sur laquelle `all(...)` vaut `True`, c'est-a-dire
    un succes complet sans qu'un seul champ ait ete lu.
    """
    profile = codec_profiles.get_profile(plan.profile_id)
    width, height = plan.resolution.size or plan.source_size
    expected: dict[str, Any] = {
        "codec": profile.probe_codec_name,
        "resolution": f"{width}x{height}",
        "frame_rate": plan.exact_frame_rate,
        "pixel_format": profile.pix_fmt,
        "colorspace": profile.colorspace,
        "color_primaries": profile.colorspace,
        "color_transfer": profile.colorspace,
    }
    if plan.timecode.emitted is not None:
        expected["timecode"] = plan.timecode.emitted
    return expected


@dataclass(frozen=True)
class EncodeCommandResult:
    """Ce que la commande a produit, sans jamais l'ecrire au manifest."""

    plan: EncodePlan
    outcome: codec_profiles.EncodeOutcome
    manifest_fields: dict
    verification: dict
    swept_residues: tuple[Path, ...] = ()
    findings: tuple[str, ...] = ()


def execute_plan(
    plan: EncodePlan,
    *,
    swept: Sequence[Path] = (),
    ffprobe_bin: str = "ffprobe",
    rappel_progression=None,
) -> EncodeCommandResult:
    """Encoder, verifier, **puis** basculer. Jamais l'inverse.

    L'encodage lui-meme est integralement delegue a `codec_profiles.run_encode`:
    cette story ne construit aucun argv et ne lance aucun processus. Ce qu'elle
    ajoute est la verification technique de l'AC 15 -- dont `verify_technical_metadata`
    recoit ici son **premier consommateur de production** -- et la bascule finale,
    qui n'a lieu que si cette verification passe.

    Le nom du binaire d'encodage n'apparait nulle part dans ce module, pas meme
    en valeur par defaut: la fabrique porte le sien. C'est ce qui rend le critere
    de faute de la story mecaniquement verifiable -- un litteral de binaire
    d'encodage, ou un `subprocess`, signerait le debordement sur la story 6.0.

    **La cible est reservee atomiquement avant l'encodage** et la bascule se fait
    sous cette reservation: voir `reserve_master_path` pour la mesure du defaut
    qu'elle ferme. Le `finally` retire la reservation si la bascule n'a pas eu
    lieu -- un fichier vide pose la ou il n'y avait rien ne peut pas detruire un
    master preexistant, et le laisser bloquerait la relance.
    """
    reserved = reserve_master_path(plan)
    replaced = False
    staged = _staged_output_path(plan)
    try:
        outcome = codec_profiles.run_encode(
            plan.profile_id,
            # Story 6.6, AC 2: la liste **muxee** (frames tenues), jamais la
            # liste distincte -- `plan.frame_rate` est desormais la cadence
            # source effective, cadence a laquelle cette liste se lit.
            plan.muxed_frame_paths,
            plan.frame_rate,
            staged,
            target_size=plan.resolution.size,
            timecode=plan.timecode.emitted,
            # La base de validation reste celle du manifest, meme apres
            # expression dans la base du master: elle porte sur la valeur emise,
            # qui est desormais lue dans la base du master, donc `None` -- la
            # fabrique retombe alors sur la cadence d'encodage, qui est
            # exactement la bonne base pour cette valeur-la.
            timecode_base_fps=None,
            container_tags=plan.container_tags,
            overwrite=False,
            ffprobe_bin=ffprobe_bin,
            rappel_progression=rappel_progression,
        )
        report = video_metadata.verify_technical_metadata(
            str(staged), expected_technical_metadata(plan), ffprobe_bin=ffprobe_bin
        )
        divergent = {name: entry for name, entry in report.items() if not entry["ok"]}
        if divergent:
            detail = "; ".join(
                f"{name}: obtenu {entry['actual']!r} au lieu de {entry['expected']!r}"
                for name, entry in sorted(divergent.items())
            )
            # **Le refus NOMME ses deux outils.** Le 2026-09-06, ce message est
            # remonte du terrain sans version, et le diagnostic a coute une
            # soiree: la cause etait un renversement de comportement de ffmpeg
            # entre 6 et 8 sur le tagage colorimetrique, que le seul numero de
            # version aurait designe d'emblee. Les deux comptent et ils peuvent
            # differer: ffmpeg **ecrit** le fichier, ffprobe le **relit**, et une
            # divergence entre les deux binaires est elle-meme un diagnostic.
            #
            # La chaine est **fabriquee par `codec_profiles`** et non ici: ce
            # module ne doit porter aucun litteral nommant le binaire
            # d'encodage (AC 18, banc negatif
            # `test_the_decision_module_builds_no_command_and_spawns_no_process`),
            # et un `f"ffmpeg {...}"` ecrit ici l'a fait rougir.
            outils = codec_profiles.format_tool_provenance(
                outcome.ffmpeg_version, ffprobe_bin
            )
            raise EncodeVerificationRefused(
                f"Le fichier produit ne porte pas ce qu'il devait porter ({detail}). "
                f"Produit et relu avec: {outils}. "
                f"La bascule n'a pas eu lieu: le master precedent est intact. Fichier "
                f"conserve pour diagnostic: {staged}",
                staged_path=staged,
                report=report,
            )
        os.replace(staged, plan.output_path)
        replaced = True
    finally:
        if reserved and not replaced:
            # La reservation est un fichier **vide** pose la ou il n'y avait
            # rien: la retirer ne peut pas detruire un master preexistant. Un
            # `unlink` qui echoue ne doit jamais remplacer l'erreur en cours
            # (lecon de la story 6.0, meme geste).
            try:
                plan.output_path.unlink(missing_ok=True)
            except OSError:
                pass
    final = codec_profiles.EncodeOutcome(
        profile_id=outcome.profile_id,
        output_path=str(plan.output_path),
        frame_count=outcome.frame_count,
        frame_rate=outcome.frame_rate,
        source_size=outcome.source_size,
        target_size=outcome.target_size,
        encoded_size=outcome.encoded_size,
        filter_chain=outcome.filter_chain,
        pix_fmt=outcome.pix_fmt,
        timecode=outcome.timecode,
        timecode_base=outcome.timecode_base,
        # Reporte tel quel: c'est la version du binaire qui a reellement encode,
        # relevee par la fabrique. La recalculer ici sonderait un `ffmpeg` du
        # PATH, qui n'est pas forcement celui-la.
        ffmpeg_version=outcome.ffmpeg_version,
    )
    findings = list(plan.findings)
    if swept:
        findings.append(ENCODE_RESIDUES_SWEPT)
    return EncodeCommandResult(
        plan=plan,
        outcome=final,
        # Description d'un **encodage**, rendue par 6.0 et que la story 6.5
        # persistera. Elle est calculee ici pour etre affichee et transmise; elle
        # n'est ecrite dans aucun manifest.
        manifest_fields=codec_profiles.encode_manifest_fields(final),
        verification=report,
        swept_residues=tuple(swept),
        findings=tuple(findings),
    )


__all__ = [
    "DEFAULT_RESOLUTION_ID",
    "DERIVED_FROM_LOT_FIELD",
    "ENCODE_CODES",
    "ENCODE_INFORMATIONAL_CODES",
    "ENCODE_REFUSAL_CODES",
    "EncodableLot",
    "EncodeCommandResult",
    "EncodeDecisionError",
    "EncodePlan",
    "EncodeVerificationRefused",
    "ReconstructionDeLot",
    "NATIVE_RESOLUTION_KEYWORD",
    "PROJECT_TO_PROFILE_COLORSPACE",
    "RECONSTRUCTIONS_FIELD",
    "RESOLUTION_REGISTRY",
    "SRGB_APPROXIMATION_NOTE",
    "TargetResolution",
    "assess_completeness",
    "build_container_tags",
    "build_master_output_path",
    "check_chronology",
    "check_lot_admission",
    "check_output_destination",
    "confront_project_colorspace",
    "confront_selection_identity",
    "execute_plan",
    "expected_technical_metadata",
    "express_timecode_in_master_base",
    "frames_per_timecode_second",
    "enumerer_les_reconstructions",
    "known_resolution_ids",
    "list_encodable_lots",
    "plan_encode",
    "plan_sequence",
    "plan_timecode",
    "prepare_output_directory",
    "profile_colorspace_for_project",
    "reconstruction_for_lot",
    "reserve_master_path",
    "render_summary",
    "resolution_name_segment",
    "resolve_frame_rate",
    "resolve_output_resolution",
    "resolve_source_rate",
    "select_lot",
    "settle_resolution",
    "validate_encode_code",
]
