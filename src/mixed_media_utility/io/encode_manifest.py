"""Persistance au manifest de ce qu'`encode` vient de produire (story 6.5).

Quatre donnees, et rien d'autre, apres qu'un master a ete pose a son chemin
final: `lots[].state = "encode"`, l'inventaire `lots[].encoded_masters`,
`video.codec_target` et `artifacts.outputs_dir`. La table `ENCODE_LOT_FIELDS`
(plus `ENCODE_VIDEO_FIELDS` et `ENCODE_ARTIFACT_FIELDS` pour les sections de
tete) est l'emplacement unique de chacune; **toute donnee absente de ces tables
n'est pas ecrite**. Ni date-heure d'encodage, ni taille du fichier, ni duree de
l'encodage, ni resolution, ni cadence du master: les deux premieres varient d'un
encodeur a l'autre pour un contenu identique, la troisieme a chaque execution,
et les deux dernieres se lisent du fichier par
`video_metadata.read_technical_metadata` -- les persister creerait une seconde
verite.

Ce module ferme le dernier trou du contrat d'etats: `"encode"` est, jusqu'a
cette story, **la seule** valeur de `io.manifest.LOT_STATES` sans aucun
producteur dans `src/` -- celui que la story 5.11 a comble pour `"pdf"` et la
story 5.7 pour `"scan"`. Il donne aussi son premier producteur a
`video.codec_target`, seul champ que `validate_manifest_completeness` laissait
insatisfiable sur le manifest reel du depot, et a `artifacts.outputs_dir`.

Cette story ne produit **aucun** master
---------------------------------------
La story 6.1 decide, encode et bascule; celle-ci **lit** le resultat de la
commande (`encode.EncodeCommandResult`) et le declare. Aucun identifiant n'est
re-resolu, aucun nom de fichier n'est reconstruit, aucun catalogue de profils
n'est interroge ici: deux recettes pour un meme identifiant, c'est la divergence
que la story 5.11 s'interdisait deja, et le manifest declarerait alors un
fichier que personne n'a ecrit.

Reprendre, ne pas copier
------------------------
L'ecriture atomique (`_atomic_write`), la serialisation canonique (`_serialize`,
atteinte **par** `_atomic_write`), la relecture typee
(`_load_existing_manifest`), la migration v2.0 (`_migrate_v2_0`) et la
normalisation de chemin relatif (`_relative_posix`) sont celles des stories 3.4
et 5.7, importees telles quelles depuis `io.extraction_manifest`. Il n'existe
pas de seconde version de ces fonctions dans le depot, et il ne doit pas en
exister: le contre-exemple a ne pas reproduire est `poc reconstruct-project`
(`cli.py`), qui ecrit **puis** valide -- tenable sur un projet vierge, intenable
des lors qu'un manifest existant et riche est enrichi.
`io.manifest.validate_lot_state_transition` est le **seul** juge de l'ordre des
etats: aucune comparaison d'index n'est reecrite ici.

Trois versions de manifest, sur le motif de 5.7 et non de 5.11
--------------------------------------------------------------
`validate_manifest` dispatche par `schema_version`, et
`project.schema.v2-0.json` porte lui aussi `lots[].items` en
`additionalProperties: false`. Mesure: un `lots[].encoded_masters` pose sur un
document v2.0 rend `Invalid manifest at 'lots.0': Additional properties are not
allowed`. La story 5.11 ne traite pas `schema_version` et echoue donc **apres**
que le PDF a ete ecrit; ici cela voudrait dire apres que la video a ete ecrite.
`_assert_mergeable` juge la version avant toute ecriture: legacy ->
`LegacyManifestError`, `"2.0"` -> migre **en memoire**, version inconnue ->
refus.

Il n'y a **pas** de second controle pose avant l'encodage, et c'est une mesure
et non un oubli. Sur le chemin de la commande, `cli.encode_command` appelle
`io.manifest.validate_manifest` sur le `project.json` **avant** de decider quoi
que ce soit, et cette validation refuse trois des quatre cas: un manifest legacy
(refuse contre le schema v1), une `schema_version` inconnue et un `lots[].state`
hors vocabulaire (l'enum du schema le porte). Un controle de plus n'aurait ferme
aucun chemin: il aurait seulement double une garde deja tenue, en donnant
l'illusion d'en tenir une autre.

Le quatrieme cas est le seul dont l'attribution ait ete fausse, et la revue l'a
corrigee: un document **v2.0 authentique traverse `validate_manifest` sans un
mot** -- le schema v2.0 le declare valide, c'est son role. C'est `plan_encode`
qui le refuse, faute d'`output_frames_dir` sur le lot
(`DOSSIER_DE_LOT_NON_DECLARE`), champ que le schema v2.0 ne connait pas. Ce que
`validate_manifest` refuse en annoncant « 2.0 » est un document v2.1
**re-etiquete**, qui n'est pas le meme objet. Le contrat annonce -- rien
d'encode -- tient dans les deux cas.

Corollaire, ecrit une fois ici plutot que redemontre a chaque revue: **toutes**
les branches de refus de ce module sont inatteignables depuis la commande, et
pas seulement celles de `_assert_mergeable`. L'enum de `lots[].state`, le typage
de `encoded_masters`, celui de `video` et d'`artifacts`, le refus du legacy et
de la version inconnue sont **tous au schema**, donc opposes par la validation de
tete; le lot absent est refuse par la story 6.1; le master hors `outputs/` ne
peut pas se produire puisque 6.1 construit le chemin. Le seul refus reellement
atteignable par la commande est l'`OSError` d'ecriture. Ce que ces gardes
protegent, c'est l'appel **direct** du module et la fenetre entre la decision et
l'ecriture -- voir la limite de concurrence ci-dessous. C'est aussi ce qui evite
que le motif ayant fait retirer `check_encode_persistable` (une garde
inatteignable n'est pas une garde) ne se retourne contre elles: celui-la etait
inatteignable **et** doublait une garde tenue en amont, celles-ci ferment la
seule porte qui reste ouverte.

`video.codec_target` est de portee document, la decision est de portee lot
--------------------------------------------------------------------------
Limite **nommee et mesuree**, non corrigee ici. Le schema n'offre qu'un seul
emplacement a la cible d'encodage, `video.codec_target`, et cette section est de
portee **projet**; or le profil est choisi par lot, a chaque appel de la
commande. Consequence mesuree de bout en bout: encoder `lotA` en `prores_hq`
puis `lotB` en `dnxhr_hqx` puis **relancer `lotA` a l'identique** change le
document, parce que la troisieme passe repose `prores_hq` par-dessus la valeur
du second lot. Deux projets au contenu identique encodes dans un ordre different
rendent donc deux `project.json` differents.

Ce module ne deplace pas le champ vers le lot -- ce serait le contrat de
l'Epic 2, et `("video", "codec_target")` appartient a
`io.manifest.CRITICAL_PROJECT_FIELDS_V2_1`, si bien qu'encoder **un seul** lot
satisfait deja le critere de completude « codec cible » pour tous les autres,
y compris ceux qui n'ont jamais ete encodes. Ce qu'il fait, et qui manquait,
c'est **le dire**: le remplacement d'une valeur en place emet
`ENCODE_CODEC_TARGET_REPLACED`, par symetrie exacte avec
`ENCODE_MASTER_ENTRY_REPLACED` que ce meme module emet deja pour le cas
analogue au niveau du lot. L'asymetrie -- constater au niveau du lot, se taire
au niveau du document -- etait le vrai defaut: elle rendait le seul champ de
portee projet ecrasable sans un mot.

La verite par master reste, elle, dans `lots[].encoded_masters[].profile_id`:
c'est la seule donnee qui reponde a « quel profil pour **ce** lot ».

Le manifest declare ce qui a ete produit, pas ce qui est present
---------------------------------------------------------------
Question ouverte 4, tranchee: une entree d'inventaire dont le fichier a ete
supprime a la main **n'est verifiee par rien** au MVP, et ce n'est pas un
oubli. Le manifest est un journal de ce que la chaine a produit; lui faire
sonder le disque en ferait un inventaire de ce qui reste, c'est-a-dire une
troisieme verite entre le disque et lui. La premiere personne qui rencontrera
le cas doit pouvoir lire ici que c'est le regime voulu.

Limite de concurrence, heritee et declaree
------------------------------------------
Le depot n'a **aucun verrou** sur la sequence lecture-modification-ecriture du
manifest: deux ecritures simultanees et le dernier ecrivain gagne, en rendant
tous deux un succes. Le defaut est deja consigne quatre fois au
`deferred-work.md` (revues 3.1 et 3.4, stories 5.11 et 5.7). Ce module ajoute un
**cinquieme** ecrivain -- un `encode` concurrent d'un `extract`, d'un `makepdf`
ou d'un `scan` sur le meme projet. Il ne corrige pas: il faut une politique
globale, assignee a une story transverse d'apres-Epic 6. Regle d'usage jusqu'a
nouvel ordre: **une seule commande ecrivant le manifest a la fois par projet**.

Ce que cette limite coute **ici** est particulier, et n'avait jamais ete ecrit.
Mesure de la revue: sur deux `encode` concurrents, 20 essais sur 20 declarent
**deux** succes alors qu'un des deux masters n'est declare nulle part. Chez
`extract` ou `makepdf`, la reprise est un simple rejeu; ici non. Le master etant
present sur le disque, la relance est refusee (`MASTER_DEJA_PRESENT`, code `1`),
et la seule issue que la commande propose est `--overwrite`, c'est-a-dire
**reencoder integralement un master deja correct pour reparer une ligne de
manifest** -- des dizaines de minutes de calcul sur un lot de production, pour
une donnee que personne n'a perdue. Aucun chemin de reprise moins cher n'est
invente ici: ce serait elargir la story. Le prix est nomme pour que la politique
transverse le connaisse.

Deux limites heritees de `_atomic_write` (story 3.4), partagees par les cinq
ecrivains et **non corrigees ici** parce que leur correctif est dans le module de
3.4, hors du perimetre de cette story:

* un `project.json` qui est un **lien symbolique** est remplace en silence par
  un fichier ordinaire, et la cible du lien garde le contenu d'avant encodage;
* les residus `.project.json.<...>.tmp` d'une ecriture interrompue **ne sont
  jamais balayes**, et `glob.glob('*')` ne les voit pas (leur nom commence par un
  point). Un residu present ne gene aucune persistance ulterieure.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from jsonschema.exceptions import ValidationError

from . import project_layout
from .extraction_manifest import (
    MANIFEST_FILENAME,
    MIGRATABLE_SCHEMA_VERSIONS,
    ExtractionPersistenceError,
    LegacyManifestError,
    _atomic_write,
    _load_existing_manifest,
    _migrate_v2_0,
    _relative_posix,
)
from .manifest import CURRENT_SCHEMA_VERSION, LOT_STATES, validate_lot_state_transition

# --------------------------------------------------------------------------
# Table de persistance (normative)
# --------------------------------------------------------------------------

#: Etat pose par cette story, exclusivement via
#: `io.manifest.validate_lot_state_transition`, jamais en dur. Le contre-exemple
#: du depot est `cli.py` (`"lot": {"state": "pdf", ...}`), chemin POC legacy sans
#: aucune garde. Le **bon** motif est celui d'`io.reconstruction`, qui delegue sa
#: resolution d'etat a la garde.
ENCODE_LOT_STATE = "encode"

#: Nom du champ d'inventaire et nom de sa cle. Nommes ici une seule fois: la cle
#: gouverne a la fois l'appariement d'une entree existante et le tri a
#: l'ecriture, et deux litteraux divergeraient au premier ajustement.
MASTER_INVENTORY_FIELD = "encoded_masters"
MASTER_INVENTORY_KEY = "path"

#: Emplacement unique de chaque donnee ecrite par ce module sur `lots[]`, sur le
#: motif d'`EXTRACTION_LOT_FIELDS` et de `PDF_LOT_FIELDS`. **Toute donnee absente
#: de cette table n'est pas ecrite**: la table est le contrat, pas un resume du
#: code, et un test la confronte en **egalite d'ensembles** au lot reellement
#: produit -- jamais en liste de presences, qui ne verrait pas un champ de trop.
#: Ligne d'eau des rangs de master, par famille (`EPIC11-ARB-92` etendu aux
#: masters par Egan le 2026-08-31). Nommee **ici**, chez le producteur, et
#: importee par `project_maintenance` qui la fait redescendre: le champ etait
#: jusqu'au 2026-09-03 declare dans le seul module qui RETIRE, c'est-a-dire
#: chez son consommateur, et aucun chemin d'ecriture ne le posait. Un litteral
#: de plus au moment de brancher l'ecriture aurait fait deux verites pour le
#: meme champ.
MASTERS_WATERMARK_FIELD = "masters_version_watermark"

ENCODE_LOT_FIELDS: tuple[str, ...] = (
    "state",
    MASTER_INVENTORY_FIELD,
    # Story 11.8, AC 4.3. La ligne d'eau se pose a la CONSOMMATION, comme
    # `sheets_version_watermark` chez les planches -- c'est le geste
    # qu'`EPIC11-ARB-108` exige identique pour les cinq objets versionnables,
    # et le master etait le seul des cinq a ne l'avoir que du cote du retrait.
    MASTERS_WATERMARK_FIELD,
)

#: Champs d'une entree de l'inventaire, dans l'ordre de la table normative.
#:
#: `incomplete` est la ligne conditionnelle d'`EPIC6-ARB-3`, due des lors que le
#: drapeau `--accept-incomplete-lot` est implemente -- il l'est
#: (`encode.enforce_completeness(..., accept_incomplete=...)`). Elle est ecrite
#: **toujours**, jamais omise quand elle vaut `False`: une omission serait
#: ambigue entre « master complet » et « master ecrit par une version qui ne
#: connaissait pas le drapeau », alors que l'arbitrage demande que le master
#: **declare** son incompletude. C'est aussi ce qui rend l'egalite d'ensembles
#: de cette table stable d'une entree a l'autre.
ENCODE_MASTER_FIELDS: tuple[str, ...] = (
    MASTER_INVENTORY_KEY,
    "profile_id",
    "frame_count",
    "incomplete",
    # `version_rank` n'est PAS dans cette table (EPIC11-ARB-91): elle enumere
    # les champs que TOUTE entree porte, et le rang est absent du master de
    # rang 1 -- l'y mettre rendrait invalide chaque master ordinaire. Il est
    # ecrit par omission stricte, comme `version_rank` d'un lot.
)

#: Champ ADDITIF de l'inventaire: present a partir du rang 2, jamais au rang 1.
MASTER_VERSION_RANK_FIELD = "version_rank"

#: Seul champ ecrit dans `video`, et son premier producteur du depot. La section
#: est en `additionalProperties: true` mais porte quinze interdits
#: `allOf/not/required` (les quatre `fps_*`, `resolution_source` et les dix
#: `source_*`): `codec_target` n'y figure pas, et c'est le seul nom qu'on ait le
#: droit d'y poser.
ENCODE_VIDEO_FIELDS: tuple[str, ...] = ("codec_target",)

#: Seul champ ecrit dans `artifacts`, par symetrie exacte avec le
#: `artifacts.frames_dir` de l'extraction.
ENCODE_ARTIFACT_FIELDS: tuple[str, ...] = ("outputs_dir",)

#: Equivalent de `NON_IDEMPOTENT_FIELDS` (story 3.4) et de
#: `PDF_NON_IDEMPOTENT_FIELDS` (story 5.11): **le tuple vide**. Aucun champ ecrit
#: ici ne derive de l'horloge, de la machine ni de la version de l'encodeur.
#:
#: Portee exacte de l'invariant, corrigee en revue: deux `encode` identiques
#: **du meme lot** laissent le manifest identique octet a octet. La restriction n'est
#: pas rhetorique -- des qu'un projet melange deux profils, `video.codec_target`
#: est de portee document et repasse a la valeur du dernier lot encode (voir la
#: section correspondante en tete de module). Le document reste alors fonction de
#: l'ordre des commandes, sans qu'aucun champ de cette table soit en cause: le
#: champ fautif est ecrit, mais il n'est pas *derive* -- il est simplement de la
#: mauvaise portee. C'est pourquoi il n'entre pas dans ce tuple et qu'il est
#: traite par un **constat**.
#:
#: Deux pieges specifiques, tous deux gratuits a commettre. La **taille** du
#: fichier et la **duree** d'encodage sont disponibles pour rien et sont
#: exactement ce qu'il ne faut pas persister: la premiere varie d'une version
#: d'encodeur a l'autre pour un contenu identique, la seconde a chaque
#: execution. Et l'**ordre** de l'inventaire en est un troisieme, moins visible:
#: `_serialize` emploie `sort_keys=True`, qui canonise les mappings et **pas**
#: les listes. Une liste laissee dans son ordre d'insertion porterait l'ordre
#: chronologique des encodages, c'est-a-dire un signal d'horloge deguise. D'ou
#: le tri explicite par `MASTER_INVENTORY_KEY` a l'ecriture.
ENCODE_NON_IDEMPOTENT_FIELDS: tuple[str, ...] = ()

# --------------------------------------------------------------------------
# Constats, tous informatifs (un refus est une exception, jamais un code)
# --------------------------------------------------------------------------

#: Une entree d'inventaire portant **deja** ce chemin de master a ete remplacee
#: par une entree differente: meme fichier, autre contenu declare. Le cas
#: nominal est le reencodage d'un lot dont un rescan a comble les trous -- le
#: `frame_count` monte, `incomplete` retombe a `False`. Reecrire a l'identique
#: n'emet rien: le constat nomme un changement, pas une repetition, sans quoi
#: toute relance idempotente le porterait.
ENCODE_MASTER_ENTRY_REPLACED = "ENTREE_DE_MASTER_REMPLACEE"

#: `video.codec_target` portait **deja** une autre valeur, et elle vient d'etre
#: remplacee. Le champ est de portee **document** alors que la decision qui
#: l'alimente est de portee **lot** (section dediee en tete de module): sans ce
#: constat, encoder un second lot a un autre profil reecrivait en silence la
#: cible d'encodage du projet entier, et une simple relance a l'identique du
#: premier lot la reecrivait a nouveau -- un changement de document que la
#: commande annoncait comme un succes muet.
#:
#: Strictement symetrique d'`ENCODE_MASTER_ENTRY_REPLACED`, et pour la meme
#: raison: reecrire a l'identique n'emet rien, le constat nomme un changement et
#: non une repetition, sans quoi toute relance idempotente le porterait.
ENCODE_CODEC_TARGET_REPLACED = "CIBLE_D_ENCODAGE_REMPLACEE"

#: Vocabulaire complet des constats de ce module, tous informatifs.
ENCODE_PERSISTENCE_CODES: tuple[str, ...] = (
    ENCODE_MASTER_ENTRY_REPLACED,
    ENCODE_CODEC_TARGET_REPLACED,
)


# --------------------------------------------------------------------------
# Hierarchie d'exceptions
# --------------------------------------------------------------------------


class EncodePersistenceError(ExtractionPersistenceError):
    """Racine des erreurs de persistance d'encodage.

    Sous-classe de la hierarchie de la story 3.4 pour que la CLI n'ait qu'un
    seul `except` a tenir, comme `PdfPersistenceError` avant elle. Corollaire
    assume et deja consigne: le nom de la racine parle d'extraction alors
    qu'elle couvre desormais quatre chaines de plus, et le message d'un
    temporaire invalide parle de « manifest d'extraction ». Le renommage
    appartient a une passe transverse, pas a cette story.
    """


class EncodeManifestAbsentError(EncodePersistenceError):
    """Aucun `project.json` exploitable dans le dossier projet.

    `encode` refuse deja un projet sans manifest en amont (le verdict de
    completude et le registre des mires ne vivent nulle part ailleurs); ce cas
    ne se produit donc qu'en usage direct du module, ou si le fichier disparait
    entre la validation d'entree et la fin de l'encodage.
    """


class EncodeLotAbsentError(EncodePersistenceError):
    """Le lot vise n'existe pas dans `lots[]`, rien n'est ecrit.

    Cette story ne **cree** aucun lot: la story 6.1 refuse deja un lot absent
    avant d'encoder quoi que ce soit. Un lot absent ici est l'indice que le
    manifest a change sous les pieds de la commande, pas un cas nominal a
    rattraper en fabriquant une entree.

    Limite heritee, nommee et non corrigee ici: le schema n'impose **aucune**
    unicite sur `lot_id` (mesure: deux lots de meme `lot_id` produisent un
    manifest valide) et la recherche rend le **premier** -- la famille du mutant
    `M25` de la story 5.7. Le cas n'est pas atteignable depuis les producteurs
    reels du depot, mais il l'est par edition manuelle ou fusion de projets. Le
    correctif est une contrainte de schema, donc du contrat de l'Epic 2.
    """


class EncodeLotStateRefused(EncodePersistenceError):
    """Le `lots[].state` relu n'appartient pas au vocabulaire ferme des etats.

    Refus **dur**, et c'est un choix: `encode` est terminal, donc conserver
    silencieusement une valeur hors vocabulaire la persisterait pour de bon.
    Divergence a nommer plutot qu'a masquer: `io.pdf_manifest.build_pdf_manifest`
    **conserve** au contraire l'etat en place quand la garde refuse (constat
    `ETAT_DE_LOT_CONSERVE`), parce qu'une reimpression n'invalide rien en aval.
    Le depot fait donc les deux; l'harmonisation est consignee au
    `deferred-work.md` et n'est pas tranchee ici pour un module qui n'est pas le
    notre.
    """


# --------------------------------------------------------------------------
# Objets d'entree, API figee
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class EncodedMaster:
    """Une entree de l'inventaire `lots[].encoded_masters`.

    La cle est le **chemin relatif du master**, unique par construction
    puisque c'est un chemin de fichier. Ce n'est pas `profile_id`: la story 6.1
    produit deux masters distincts pour le **meme** profil --
    `<lot_id>_mmu_prores_hq.mov` a la resolution par defaut et
    `<lot_id>_mmu_prores_hq_3307x1860.mov` en natif --, si bien qu'une cle par
    profil ecraserait un master present et voulu, c'est-a-dire exactement le
    tort que l'inventaire existe pour eviter.
    """

    path: str
    profile_id: str
    frame_count: int
    incomplete: bool
    #: Rang de version de CE master (`EPIC11-ARB-91`), `None` au rang 1.
    #: Distinct du `version_rank` du LOT: un lot versionne porte deja son rang
    #: dans son `lot_id`, donc dans le nom de son master, et ce champ ne le
    #: redit pas. Celui-ci compte les re-encodages du MEME lot au MEME profil.
    version_rank: int | None = None

    def to_entry(self) -> dict[str, Any]:
        """Rendre l'entree JSON: `ENCODE_MASTER_FIELDS`, plus le rang s'il existe.

        **Omission stricte** du rang, jamais `None` ecrit: le schema pose
        `additionalProperties: false` avec `minimum: 2`, si bien qu'un
        `version_rank: null` ou `1` ferait echouer la validation de tout
        master ordinaire. Meme regime que `version_rank` d'un lot.
        """
        entree = {
            MASTER_INVENTORY_KEY: self.path,
            "profile_id": self.profile_id,
            "frame_count": self.frame_count,
            "incomplete": self.incomplete,
        }
        if self.version_rank is not None:
            entree[MASTER_VERSION_RANK_FIELD] = self.version_rank
        return entree


@dataclass(frozen=True)
class EncodeRecord:
    """Ce qu'un encodage reussi declare au manifest.

    Toutes les valeurs sont **lues** du resultat de la commande, jamais
    recalculees.
    """

    lot_id: str
    master: EncodedMaster
    codec_target: str
    outputs_dir: str
    #: Cle de famille du master (profil, et resolution quand elle n'est pas la
    #: defaut), sous laquelle sa LIGNE D'EAU se range. **Sans defaut, et c'est
    #: delibere**: un defaut vide ferait de l'oubli de ce champ une ecriture
    #: silencieusement sautee -- exactement la surface morte que la story 11.8
    #: repare. Elle est DECIDEE par `encode.plan_encode` et seulement lue ici
    #: (`EncodePlan.masters_family_key`), la frontiere statique de la story
    #: 5.11 interdisant a ce module de nommer la fabrique de nom de master --
    #: un module de PERSISTANCE qui recalcule un identifiant peut le faire
    #: diverger de celui qui a ete ecrit.
    masters_family_key: str

    @classmethod
    def from_command_result(cls, result: Any) -> "EncodeRecord":
        """Construire l'objet depuis `encode.EncodeCommandResult`, en lisant seul.

        Ce qui est lu, et d'ou:

        * `result.plan.lot_id` -- le lot **resolu** par la story 6.1, pas celui
          saisi en ligne de commande;
        * `result.plan.profile_id` -- le profil retenu par la story 6.1;
        * `result.plan.output_path` -- le chemin ou `os.replace` vient de poser
          le master, donc son nom **final**;
        * `result.outcome.frame_count` -- le cardinal de frames reellement
          encodees, mires comprises, tel que la fabrique de la story 6.0 l'a
          verifie sur le fichier produit;
        * `result.plan.verdict.complete` -- le verdict de completude du lot, lu
          sur les cardinaux de `lots[]`.

        `incomplete` vaut exactement la negation de ce verdict, et cela coincide
        avec le seul cas ou `--accept-incomplete-lot` a servi: la story 6.1
        refuse un cardinal indeterminable et un cardinal en exces, si bien
        qu'un verdict negatif implique un lot troue explicitement assume. Les
        **mires** n'y entrent pas: elles portent un fichier et un contenu voulu,
        elles sont deja comptees par `lots[].synthetic_frame_count` depuis la
        story 5.7, et les confondre avec un trou ferait declarer incomplet un
        lot dont aucune page ne manque.

        `codec_target` recoit le **profil**, et non le nom de l'encodeur ni
        celui que la sonde rapporte: la matrice de responsabilite 2.4 nomme la
        donnee `codec_target_profile` et la classe `REQUIRED` sur le canal
        MANIFEST, or `video.codec_target` est le seul emplacement que le schema
        lui offre. C'est aussi le seul des trois qui ne perde rien: le nom de
        l'encodeur et celui de la sonde se deduisent du profil par le catalogue,
        tandis que trois profils du catalogue partagent le meme nom de sonde et
        ne s'en deduisent donc pas.
        """
        plan = result.plan
        return cls(
            lot_id=plan.lot_id,
            master=EncodedMaster(
                path=master_relative_path(plan.project_dir, plan.output_path),
                profile_id=plan.profile_id,
                frame_count=result.outcome.frame_count,
                incomplete=not plan.verdict.complete,
                # Story 11.8, AC 4.5. Le rang est LU au plan, jamais deduit du
                # nom: `_rangs_de_masters` ne relit le nom que pour dire si une
                # entree appartient a la famille, et le manifeste tranche
                # partout ailleurs. Le champ etait declare depuis
                # `EPIC11-ARB-91` et n'etait renseigne par aucun producteur --
                # il valait donc toujours `None`, et `to_entry` l'omettait
                # toujours, y compris pour un master `_v2` bel et bien ecrit.
                version_rank=plan.master_version_rank,
            ),
            codec_target=plan.profile_id,
            outputs_dir=outputs_dir_value(),
            masters_family_key=plan.masters_family_key,
        )


@dataclass(frozen=True)
class EncodeManifestMerge:
    """Resultat de la fusion pure: le document, l'etat pose, les constats."""

    manifest: dict
    state_written: str
    findings: tuple[str, ...]


@dataclass(frozen=True)
class PersistedEncode:
    """Resultat de la persistance: ce qui a ete ecrit, et ou."""

    manifest_path: Path
    lot_id: str
    manifest: dict
    state_written: str
    master_path: str
    findings: tuple[str, ...]


# --------------------------------------------------------------------------
# Ancrage d'arborescence (AC 11)
# --------------------------------------------------------------------------


def outputs_dir_value() -> str:
    """Valeur d'`artifacts.outputs_dir`, ancree sur la constante d'arborescence.

    Motif exact de l'extraction, qui ecrit `artifacts.frames_dir` depuis
    `FRAMES_DIRNAME` et jamais depuis le chemin resolu du dossier: un chemin
    resolu porte le dossier projet, donc la machine, donc casse la portabilite
    que le contrat v2 existe pour tenir. La difference assumee avec la story
    5.11, qui avait refuse d'ecrire `artifacts.patches_dir`, est que son motif
    etait la migration `patches/` -> `pdf/` d'`EPIC4-ARB-3`: elle aurait
    fabrique une donnee a migrer. Aucune migration ne pese sur `outputs/`.
    """
    return _relative_posix(project_layout.OUTPUTS_DIRNAME, "artifacts.outputs_dir")


def master_relative_path(project_dir: str | Path, output_path: str | Path) -> str:
    """Chemin relatif POSIX du master, ancre sur la constante et confronte au plan.

    Le segment de dossier vient de la constante `OUTPUTS_DIRNAME`, jamais du
    chemin resolu; seul le **nom de fichier** vient du plan, parce que lui seul
    est une decision de la story 6.1 que celle-ci n'a pas le droit de
    reconstruire.

    L'egalite du parent est verifiee plutot que supposee: sans elle, un master
    pose ailleurs qu'`outputs/` serait declare au manifest sous un chemin qui ne
    designe aucun fichier -- un mensonge silencieux, et le manifest le porterait
    pour toujours. Le refus arrive avant la moindre ecriture.
    """
    output_path = Path(output_path)
    expected_parent = project_layout.outputs_dir(project_dir)
    if output_path.parent != expected_parent:
        raise EncodePersistenceError(
            f"Le master {output_path} n'est pas dans le dossier de sortie du "
            f"projet ({expected_parent}): son chemin ne peut pas etre declare "
            f"relativement a '{project_layout.OUTPUTS_DIRNAME}/' sans designer "
            "un fichier qui n'existe pas. Aucune ecriture n'a eu lieu"
        )
    return _relative_posix(
        PurePosixPath(project_layout.OUTPUTS_DIRNAME) / output_path.name,
        "Le chemin du master",
    )


# --------------------------------------------------------------------------
# Couche pure de fusion
# --------------------------------------------------------------------------


def _assert_mergeable(existing: Mapping[str, Any] | None) -> dict:
    """Refuser un document inenrichissable, et migrer la v2.0 en memoire.

    Trois refus et une migration:

    * ce qui n'est pas un objet JSON: un `project.json` qui contient `42` est un
      JSON valide et un manifest absurde. Sans cette garde, `dict(existing)`
      levait une `TypeError` **nue**, hors de la hierarchie que la CLI capture;
    * le manifest legacy du POC (story 1.1, cle `id`, metadonnees sous
      `meta.*`), qui n'a pas de `lots[]`: l'enrichir fabriquerait un hybride
      qu'aucun des deux schemas ne decrit;
    * une `schema_version` **inconnue**: sans ce refus le document serait
      retrograde et son marqueur de version reecrit sans un mot.

    La v2.0, elle, est **migree en memoire** et jamais refusee. C'est le point
    ou le motif de la story 5.11 ne se transpose pas: elle ne traite pas
    `schema_version` et echoue donc sur un document v2.0 **apres** avoir ecrit
    son artefact, parce que `project.schema.v2-0.json` porte lui aussi
    `lots[].items` en `additionalProperties: false` et rejette tout champ neuf.
    """
    if existing is None:
        raise EncodeManifestAbsentError(
            f"Aucun {MANIFEST_FILENAME} lisible: l'encodage declare un lot "
            "existant, il ne cree pas de projet. Aucune ecriture n'a eu lieu"
        )
    if not isinstance(existing, Mapping):
        raise EncodeManifestAbsentError(
            "Le manifest lu n'est pas un objet JSON "
            f"({type(existing).__name__}): il ne peut pas porter de `lots`. "
            "Aucune ecriture n'a eu lieu. Restaurer une copie saine du "
            "project.json"
        )
    if "schema_version" not in existing:
        raise LegacyManifestError(
            f"Le {MANIFEST_FILENAME} present n'a pas de `schema_version`: c'est "
            "un manifest legacy du POC, qui ne porte pas de `lots[]`. Aucune "
            "migration automatique n'est faite et aucune ecriture n'a eu lieu"
        )
    declared = existing["schema_version"]
    if declared not in (CURRENT_SCHEMA_VERSION,) + MIGRATABLE_SCHEMA_VERSIONS:
        raise LegacyManifestError(
            f"schema_version {declared!r} non supportee (attendu "
            f"{CURRENT_SCHEMA_VERSION!r}, ou "
            f"{', '.join(MIGRATABLE_SCHEMA_VERSIONS)} migrable). Aucune "
            "migration automatique n'est faite et aucune ecriture n'a eu lieu"
        )
    merged = copy.deepcopy(dict(existing))
    if declared != CURRENT_SCHEMA_VERSION:
        merged = _migrate_v2_0(merged)
    return merged


def _find_lot(manifest: Mapping[str, Any], lot_id: str) -> dict:
    """Rendre l'entree de `lots[]` du lot vise, ou echouer sans rien ecrire."""
    lots = manifest.get("lots")
    if not isinstance(lots, list):
        raise EncodeLotAbsentError(
            "Le manifest ne porte aucune liste `lots`: impossible d'y declarer "
            f"le master du lot '{lot_id}'. Aucune ecriture n'a eu lieu"
        )
    for lot in lots:
        if isinstance(lot, dict) and lot.get("lot_id") == lot_id:
            return lot
    raise EncodeLotAbsentError(
        f"Le lot '{lot_id}' est absent de `lots[]`: l'encodage ne cree aucun "
        "lot, il met a jour une entree existante. Aucune ecriture n'a eu lieu"
    )


def _resolve_state(lot: Mapping[str, Any], lot_id: str) -> str:
    """Poser `encode` si la garde l'accepte, refuser durement sinon.

    La garde d'`io.manifest` est le **seul** juge: aucune comparaison d'index
    n'est reecrite ici. Elle a **deux** portes, et croire qu'elle ne garde rien
    parce que `encode` est le dernier etat est faux:

    * l'**ordre** (`LOT_STATES.index(new) < LOT_STATES.index(current)`) ne
      refuse jamais vers `encode`, qui est le maximum de la table: les six
      transitions -- `None`, `extraction`, `pdf`, `scan`, `reconstruction`,
      `encode` -- sont acceptees, la derniere etant la condition meme de
      l'idempotence;
    * le **vocabulaire** (`current_state not in LOT_STATES`) refuse, et ce refus
      est orthogonal a l'ordre. Il est atteignable: `_load_existing_manifest`
      relit par `load_manifest`, qui fait un `json.load` **sans** validation, si
      bien qu'un `project.json` edite a la main ou produit par un outil tiers
      arrive tel quel jusqu'ici.

    Une valeur **non textuelle** est refusee comme les autres, et c'est une
    divergence assumee avec `io.scan_manifest._assert_known_lot_state`, qui la
    lit « absente » pour ne pas diverger de `io.reconstruction`. Ici aucune
    seconde lecture du champ n'existe, et un `state` non textuel n'est pas un
    etat: le laisser passer poserait `encode` par-dessus, donc detruirait la
    seule trace de la corruption au moment ou l'operateur pourrait encore la
    voir.
    """
    current = lot.get("state")
    try:
        validate_lot_state_transition(current, ENCODE_LOT_STATE)
    except ValidationError as error:
        raise EncodeLotStateRefused(
            f"Le {MANIFEST_FILENAME} present declare lots[{lot_id!r}]."
            f"state={current!r}, et la transition {current!r} -> "
            f"{ENCODE_LOT_STATE!r} est refusee: {error.message} La valeur "
            "fautive est dans le manifest relu, pas dans le document que "
            "l'encodage produirait: la corriger a la main est la seule issue. "
            f"Etats connus, dans l'ordre: {', '.join(LOT_STATES)}. Aucune "
            "ecriture n'a eu lieu"
        ) from error
    return ENCODE_LOT_STATE


def _merge_inventory(
    lot: Mapping[str, Any], master: EncodedMaster
) -> tuple[list[dict[str, Any]], tuple[str, ...]]:
    """Ajouter ou remplacer l'entree du master **par son chemin**, puis trier.

    Un `append` aveugle ferait grossir l'inventaire d'un doublon a chaque
    reencodage; une cle `profile_id` detruirait le master mezzanine des qu'un
    derive du meme profil est produit. La cle est donc le chemin, et le tri est
    **explicite** parce que `sort_keys` ne canonise pas les listes (voir
    `ENCODE_NON_IDEMPOTENT_FIELDS`).

    Les entrees deja presentes sont conservees telles quelles: ce module en est
    le seul producteur, donc une entree malformee est une edition manuelle, et
    la refuser vaut mieux que la reecrire ou la perdre en silence.
    """
    raw = lot.get(MASTER_INVENTORY_FIELD)
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        raise EncodePersistenceError(
            f"Le champ `lots[].{MASTER_INVENTORY_FIELD}` du "
            f"{MANIFEST_FILENAME} present n'est pas une liste "
            f"({type(raw).__name__}): l'enrichir la reecrirait en perdant ce "
            "qu'elle porte. Aucune ecriture n'a eu lieu. Restaurer une copie "
            "saine du project.json"
        )
    for entry in raw:
        if not isinstance(entry, Mapping) or not isinstance(
            entry.get(MASTER_INVENTORY_KEY), str
        ):
            raise EncodePersistenceError(
                f"Une entree de `lots[].{MASTER_INVENTORY_FIELD}` du "
                f"{MANIFEST_FILENAME} present ne porte pas de "
                f"`{MASTER_INVENTORY_KEY}` textuel ({entry!r}): l'inventaire "
                "est appariee et trie par ce chemin, et une entree sans cle ne "
                "peut etre ni retrouvee ni classee. Aucune ecriture n'a eu lieu"
            )

    entry = master.to_entry()
    kept = [
        dict(existing)
        for existing in raw
        if existing.get(MASTER_INVENTORY_KEY) != entry[MASTER_INVENTORY_KEY]
    ]
    superseded = [
        dict(existing)
        for existing in raw
        if existing.get(MASTER_INVENTORY_KEY) == entry[MASTER_INVENTORY_KEY]
    ]
    findings: tuple[str, ...] = ()
    if any(existing != entry for existing in superseded):
        findings = (ENCODE_MASTER_ENTRY_REPLACED,)

    inventory = kept + [entry]
    inventory.sort(key=lambda item: item[MASTER_INVENTORY_KEY])
    return inventory, findings


def _codec_target_findings(
    video: Mapping[str, Any], codec_target: str
) -> tuple[str, ...]:
    """Constater le remplacement d'une cible d'encodage **deja posee**.

    Le premier producteur du champ ne constate rien: poser une valeur la ou il
    n'y en avait aucune n'ecrase rien. Reecrire la **meme** valeur ne constate
    rien non plus, exactement comme pour l'inventaire -- sans quoi toute relance
    idempotente porterait un constat.

    Ce qui est constate est le seul cas qui change le document sans qu'aucune
    information neuve n'arrive: un projet a plusieurs lots ou a plusieurs
    profils, ou le champ de portee **document** prend la valeur du dernier lot
    encode.
    """
    if "codec_target" not in video:
        return ()
    if video["codec_target"] == codec_target:
        return ()
    return (ENCODE_CODEC_TARGET_REPLACED,)


def _section(manifest: Mapping[str, Any], name: str) -> dict[str, Any]:
    """Rendre une section de tete copiee, ou refuser ce qui n'en est pas une.

    `dict(manifest.get(name) or {})` seul leve une `TypeError` ou une
    `ValueError` **nue** sur une section reduite a une chaine ou a un nombre --
    hors de la hierarchie que la CLI capture, donc une trace Python devant
    l'operateur sur un mode de panne parfaitement ordinaire.
    """
    section = manifest.get(name)
    if section is None:
        return {}
    if not isinstance(section, Mapping):
        raise EncodePersistenceError(
            f"La section `{name}` du {MANIFEST_FILENAME} present n'est pas un "
            f"objet JSON ({type(section).__name__}): y ecrire la reecrirait en "
            "perdant ce qu'elle porte. Aucune ecriture n'a eu lieu. Restaurer "
            "une copie saine du project.json"
        )
    return dict(section)


def _poser_la_ligne_d_eau_des_masters(
    lot: dict[str, Any], record: EncodeRecord
) -> None:
    """Faire MONTER la ligne d'eau de la famille au rang qui vient d'etre ecrit.

    Calque litteral d'`io.pdf_manifest._declare_sheets` (`EPIC11-ARB-108`:
    « Il n'y a pas de mecanisme different par objet »). Elle **monte** ici et
    ne redescend jamais: c'est ce qui fait qu'un rang se CONSOMME
    (`EPIC11-ARB-92`) -- retirer plus tard l'entree du master 2 ne rend pas le
    rang 2 tant que le 3 existe. Elle ne redescend que par le geste explicite
    de `project_maintenance`, et seulement en queue.

    **Le rang d'origine est ecrit lui aussi** (`max(ligne, 1)`), exactement
    comme chez les planches: la ligne d'eau dit le plus haut rang *employe*,
    et le premier master en emploie un. Sans cela, la premiere version
    demandee apres une suppression du master d'origine repartirait du rang 1
    et reprendrait un nom deja livre.

    Un rang de queue **retire** a fait descendre la ligne d'eau plus bas que le
    rang qu'on ecrit maintenant: le `max` est donc contre ce qui est declare,
    jamais une affectation seche, et il est calcule sur le manifeste relu et
    non sur celui d'avant la fusion.
    """
    ligne = lot.get(MASTERS_WATERMARK_FIELD)
    lignes = dict(ligne) if isinstance(ligne, Mapping) else {}
    posee = lignes.get(record.masters_family_key)
    if not isinstance(posee, int) or isinstance(posee, bool):
        posee = 0
    rang_ecrit = record.master.version_rank or 1
    lignes[record.masters_family_key] = max(posee, rang_ecrit)
    lot[MASTERS_WATERMARK_FIELD] = lignes


def build_encode_manifest(
    existing: Mapping[str, Any] | None, record: EncodeRecord
) -> EncodeManifestMerge:
    """Fusion **pure**: aucune I/O, aucune horloge, aucun acces disque.

    Le decoupage est celui de `build_extraction_manifest` et de
    `build_pdf_manifest`, pour la meme raison: l'idempotence octet a octet se
    teste sans toucher au disque.

    La mise a jour est faite **en place** sur l'entree de `lots[]` trouvee par
    `lot_id` -- jamais un `append` aveugle, jamais une reconstruction du
    document. Aucun autre lot, aucun rush, aucune section de tete autre que
    `video` et `artifacts` n'est touche, et `created` est preserve parce que
    rien ne le relit ni ne le reecrit. C'est le sens litteral de « regenerer un
    master ne fait jamais desapprendre le manifest »: le contre-exemple du depot
    est `reconstruct_project_manifest`, qui reconstruit de zero et reposait
    `artifacts: {}` et `video: {}`.
    """
    manifest = _assert_mergeable(existing)
    lot = _find_lot(manifest, record.lot_id)

    state = _resolve_state(lot, record.lot_id)
    inventory, findings = _merge_inventory(lot, record.master)

    lot["state"] = state
    lot[MASTER_INVENTORY_FIELD] = inventory
    _poser_la_ligne_d_eau_des_masters(lot, record)

    video = _section(manifest, "video")
    findings += _codec_target_findings(video, record.codec_target)
    video["codec_target"] = record.codec_target
    manifest["video"] = video

    artifacts = _section(manifest, "artifacts")
    artifacts["outputs_dir"] = record.outputs_dir
    manifest["artifacts"] = artifacts

    return EncodeManifestMerge(
        manifest=manifest, state_written=state, findings=findings
    )


# --------------------------------------------------------------------------
# Couche de persistance
# --------------------------------------------------------------------------


def persist_encode(
    project_dir: str | Path, record: EncodeRecord
) -> PersistedEncode:
    """Ecrire la declaration d'encodage dans `<project_dir>/project.json`.

    Point d'entree unique. Appele par la commande `encode` **apres** le retour
    d'`execute_plan`, donc apres son `os.replace`: le master porte alors son nom
    **final**, celui que l'inventaire declare. L'appeler plus tot -- par exemple
    apres la verification technique, qui porte sur le fichier d'attente --
    ecrirait un chemin ne designant aucun fichier, et un `os.replace` echouant
    ensuite laisserait un manifest declarant un master jamais pose. L'appeler
    depuis l'interieur d'`execute_plan` rendrait de plus la fabrique dependante
    du manifest.

    Sequence: relecture (`_load_existing_manifest`), fusion pure
    (`build_encode_manifest`), ecriture atomique **validee avant bascule**
    (`_atomic_write`). Toute erreur laisse le `project.json` precedent
    **strictement intact** et ne laisse aucun temporaire.
    """
    project_dir = Path(project_dir)
    manifest_path = project_dir / MANIFEST_FILENAME

    merge = build_encode_manifest(_load_existing_manifest(manifest_path), record)
    try:
        _atomic_write(manifest_path, merge.manifest)
    except OSError as error:
        # `_atomic_write` ouvre son temporaire **avant** son propre `try`: un
        # dossier projet non inscriptible ou un quota atteint -- le mode de
        # panne le plus probable de tout ce chemin, et le plus cruel ici
        # puisque le master vient d'etre ecrit -- remonte donc en `OSError`
        # nue, hors de la hierarchie que la CLI capture. Le defaut appartient
        # au module de la story 3.4 et son correctif est transverse (consigne
        # au `deferred-work.md`); ici on se contente de ramener l'erreur dans
        # la bonne famille, sans l'elargir ni la maquiller.
        raise EncodePersistenceError(
            f"Ecriture du manifest impossible: {error}. Le "
            f"{MANIFEST_FILENAME} precedent est intact"
        ) from error

    return PersistedEncode(
        manifest_path=manifest_path,
        lot_id=record.lot_id,
        manifest=merge.manifest,
        state_written=merge.state_written,
        master_path=record.master.path,
        findings=merge.findings,
    )


__all__ = [
    "ENCODE_ARTIFACT_FIELDS",
    "ENCODE_CODEC_TARGET_REPLACED",
    "ENCODE_LOT_FIELDS",
    "ENCODE_LOT_STATE",
    "ENCODE_MASTER_ENTRY_REPLACED",
    "ENCODE_MASTER_FIELDS",
    "ENCODE_NON_IDEMPOTENT_FIELDS",
    "ENCODE_PERSISTENCE_CODES",
    "ENCODE_VIDEO_FIELDS",
    "MASTER_INVENTORY_FIELD",
    "MASTER_INVENTORY_KEY",
    "MASTER_VERSION_RANK_FIELD",
    "MASTERS_WATERMARK_FIELD",
    "EncodeLotAbsentError",
    "EncodeLotStateRefused",
    "EncodeManifestAbsentError",
    "EncodeManifestMerge",
    "EncodePersistenceError",
    "EncodeRecord",
    "EncodedMaster",
    "PersistedEncode",
    "build_encode_manifest",
    "master_relative_path",
    "outputs_dir_value",
    "persist_encode",
]
