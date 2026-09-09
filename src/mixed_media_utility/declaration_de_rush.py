"""Declarer un rush dans un projet ouvert, **sans l'extraire** (story 11.4e, lot A).

`EPIC11-ARB-131`, verbatim d'Egan : « C'est un peu absurde de ne pouvoir
extraire que ce qui est deja la et qui a donc deja ete extrait. » Avant ce
module, `rushes[]` n'etait ecrit que par `persist_extraction`, qui exige un
`ExtractionRecord` complet -- selection de frames, cadence cible, entree
`lots[]`. Un rush n'entrait donc dans un projet qu'en etant **extrait**. Le
schema, lui, ne s'y opposait pas : `rushes[].required` vaut `["rush_id"]` et un
rush sans lot est valide. Ce qui manquait etait le producteur, pas le contrat.

**C'est un point d'entree de COEUR, et c'est tout le motif du lot** : la TUI a
interdiction d'importer `cli` (`EPIC11-ARB-67`), donc le geste « Ajouter un
rush » de `E2-1` -- dessine, cable a moitie et muet depuis la story 11.5 -- ne
pouvait etre cable a rien. Ce module est ce que le commentaire
d'`atelier_extraction.py` attendait : « ce que `Ajouter un rush` attend est un
point d'entree de COEUR -- declarer un rush sans l'extraire --, qui n'existe
pas ». Signature de producteur, donc : parametres **nommes**, aucun objet
`args`, aucun `print`, aucun code de sortie rendu. Il **leve** et il **rend**.

Les trois arbitrages qu'il applique, tranches par Egan le 2026-09-01
(`decisions-2026-09-01-epic11-arb-145-147-declaration-de-rush.md`) :

* `EPIC11-ARB-145` -- **une cadence source inconnue REFUSE la declaration.**
  Verbatim : « acceptation d'un rush dont la cadence est inconnue : non ». Pas
  de declaration a l'aveugle. La cadence source entre dans l'identite du lot et
  dans son nom de dossier ; un rush declare sans elle produirait une entree
  qu'aucune extraction ulterieure ne pourrait rattacher sans redemander
  l'information -- c'est-a-dire une entree qui **promet ce qu'elle ne tient
  pas**. La garde est celle de l'extraction, appelee et non reecrite :
  `qualify_source` (cadence absente, `0/0`, ou VFR) **et**
  `SourceQualification.cadence_corroboree` (`ARB-6` : une cadence annoncee mais
  inverifiable est refusee, pas reservee) ;
* `EPIC11-ARB-146` -- **le `rush_id` reste DERIVE du nom de fichier**, jamais
  choisi. Verbatim : « on garde un nom determine automatiquement selon le nom
  du rush ». Le module **appelle** `normalize_identifier`, puis
  `rush_identity_conflict` et `disambiguated_rush_id` ; il n'en recopie pas une
  ligne. Une seconde redaction divergerait au premier ajustement de la
  convention, et l'ecart ne se verrait que sur un manifeste ;
* `EPIC11-ARB-147` -- un rush deja declare menait a un **REFUS SEC, a une
  seule issue**. **Supersede sur ce point precis le 2026-09-05** par
  `EPIC11-ARB-231` ; il tient sur tout le reste (rien n'est ecrit, rien n'est
  modifie). Le motif qu'il invoquait -- « fabriquer une seconde issue
  produirait un ecran demandant a l'operateur de choisir entre deux facons de
  ne rien faire » -- est tombe avec `EPIC11-ARB-230` : relinker et declarer
  separement **font** quelque chose.

**Les trois arbitrages du 2026-09-05, qui refont l'identite du rush**
(`decisions-2026-09-05-epic11-arb-230-a-232-conflit-de-rush-et-relink.md`) :

* `EPIC11-ARB-230` -- **le dossier parent ne separe plus.** Question d'Egan,
  verbatim : « si le timecode de debut, la duree, la cadence et le nom
  coincident alors il y a "conflit" puisque c'est le meme rush ». Mesure de
  terrain avant l'arbitrage : deux copies du meme fichier dans `A/` et `B/`
  etaient declarees `prise01` puis `prise01-B`, **sans une question**. Ce
  module ne tranche donc plus l'identite avant le probe -- il ne le pouvait
  qu'en tranchant sur le dossier ;
* `EPIC11-ARB-231` -- **trois issues** au refus de conflit : relinker, « c'est
  un autre rush, le declarer separement », annuler ;
* `EPIC11-ARB-232` -- en ligne de commande, la seconde prend la forme de
  `--force-distinct`, **cite dans le refus**.

  **`EPIC11-ARB-9` est SUBORDONNE, pas annule** : la separation silencieuse
  vaut encore des qu'un critere **technique** diverge -- cadence, duree,
  timecode initial. Le multicam ordinaire (deux prises differentes) continue
  de se separer tout seul, sans question posee, et c'est un **succes**.

**L'ordre des trois etapes n'est pas negociable** (`EPIC5-ARB-34`, « un refus
qui arrive apres une destruction n'est pas un refus ») :

1. toutes les gardes **bon marche** -- projet, manifeste lisible, fichier
   source, derivation du `rush_id`, et le refus de redesignation du **meme
   fichier au meme chemin** -- avant le moindre sous-processus ;
2. le **probe** ffprobe et la qualification de la source ;
2 bis. l'**identite tranchee sur la mesure** (`EPIC11-ARB-230`) : c'est la
   qu'un homonyme se separe tout seul (`EPIC11-ARB-9`), se force
   (`EPIC11-ARB-232`) ou se refuse (`EPIC11-ARB-231`) ;
3. l'**ecriture** du manifeste, atomique et validee au schema, en dernier.

**Ce que l'etape 2 bis coute, dit plutot que tu.** Le refus de conflit
d'identite paie desormais **un** `ffprobe` -- celui de l'etape 2, jamais un
second : l'AC 1.5 (« `ffprobe` appele exactement une fois ») tient, l'AC 1.8
(« les gardes bon marche precedent le probe ») **ne tient plus pour ce
refus-la**, et c'est un ecart nomme au registre de la story plutot qu'une AC
reecrite. Il est structurel : `EPIC11-ARB-230` fait porter l'identite sur des
grandeurs que seul le probe connait, et `EPIC11-ARB-230` promet en meme temps
qu'« A-CAM/prise01.mov et B-CAM/prise01.mov reste separe tout seul des que les
deux prises different par leur duree ou leur timecode ». Les deux ensemble
exigent la mesure avant le verdict. Le seul refus qui reste bon marche est
celui qu'aucune mesure ne pourrait renverser : la redesignation du fichier
deja enregistre **a ce chemin**.

**La coupure se fait ENTRE 2 et 3, et nulle part ailleurs** (fermeture de la
dette `C-1`, 2026-09-05). `EPIC11-ARB-4` -- « obligatoire pour toute commande
qui ecrit » -- exige un panneau chiffre avant l'ecriture, et les chiffres
n'existent qu'apres l'etape 2 : la declaration se prend donc en **deux temps**,
:func:`preparer_une_declaration` (1 et 2, rien d'ecrit) puis
:func:`ecrire_la_declaration` (3). C'est le patron que
`tui.rushes.preparer_relink` / `ecrire_le_relink` porte deja, rejoue et non
reinvente. :func:`declarer_un_rush` reste, **inchangee de contrat**, comme la
composition des deux : l'appelant qui n'a rien a montrer -- la CLI -- ne paie
pas la coupure.

Aucune frame n'est ecrite et `ffmpeg` n'est **jamais** appele : ce module ne le
nomme nulle part. `ffprobe` est sa seule dependance externe, et il est appele
**exactement une fois** -- le cardinal exact de la source (`-count_frames`)
n'entre pas dans l'entree `rushes[]`, donc il n'est pas paye.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from jsonschema.exceptions import ValidationError

from . import source_confirmation, video_metadata
from .extraction import (
    cardinal_corrobore,
    ConflitIdentiteRush,
    CriteresIdentiteRush,
    ExtractionInputError,
    _source_parent_name,
    _texte_ou_none,
    comparer_identite_rush,
    disambiguated_rush_id,
    RangsDeDesambiguisationEpuises,
    qualify_source,
    rush_identity_conflict,
)
from .io.extraction_manifest import (
    MANIFEST_FILENAME,
    ExtractionPersistenceError,
    LegacyManifestError,
    ManifestWriteError,
    RushRecord,
    persist_rush_declaration,
)
from .io.manifest import load_manifest
from .io.naming import NamingError, normalize_identifier

__all__ = [
    "MOTIF_PROJET_SANS_MANIFESTE",
    "MOTIF_FICHIER_INTROUVABLE",
    "MOTIF_CHEMIN_NON_FICHIER",
    "MOTIF_SOURCE_NON_QUALIFIEE",
    "MOTIF_RUSH_DEJA_DECLARE",
    "MOTIFS_DE_REFUS",
    "ISSUES_PAR_MOTIF",
    "RefusDeDeclaration",
    "REFUS_DU_COEUR",
    "CODE_SUCCES",
    "CODE_ERREUR",
    "CODE_PREREQUIS_ABSENT",
    "CODES_DE_SORTIE",
    "correspondance_de_sortie",
    "code_de_sortie",
    "DeclarationDeRush",
    "DeclarationPreparee",
    "preparer_une_declaration",
    "ecrire_la_declaration",
    "declarer_un_rush",
]


# --------------------------------------------------------------------------
# La table de refus, PUBLIEE (AC 1.6)
# --------------------------------------------------------------------------

#: Le dossier vise ne porte pas de `project.json` lisible : il n'y a pas de
#: projet ouvert dans lequel declarer quoi que ce soit. Declarer un rush ne
#: **cree** jamais un projet -- c'est le geste de l'ecran de gestion, et lui
#: seul ecrit une identite de projet.
MOTIF_PROJET_SANS_MANIFESTE = "projet_sans_manifeste"

#: Le chemin source n'existe pas.
MOTIF_FICHIER_INTROUVABLE = "fichier_introuvable"

#: Le chemin source existe mais n'est pas un fichier (un dossier, typiquement,
#: ce qu'un explorateur rend tres facilement).
MOTIF_CHEMIN_NON_FICHIER = "chemin_non_fichier"

#: `ffprobe` n'a pas su qualifier la source : aucun flux video, resolution
#: inexploitable, **ou cadence source inconnue / inverifiable**
#: (`EPIC11-ARB-145`).
MOTIF_SOURCE_NON_QUALIFIEE = "source_non_qualifiee"

#: Ce rush est deja declare dans ce projet -- les quatre criteres d'identite
#: coincident (`EPIC11-ARB-230`). **TROIS issues** (`EPIC11-ARB-231`), qui
#: **supersedent** le refus sec a issue unique d'`EPIC11-ARB-147`.
MOTIF_RUSH_DEJA_DECLARE = "rush_deja_declare"

#: **Les cinq refus que ce module leve, et il n'y en a pas d'autre.**
#:
#: Publiee ici pour la raison qui a fait naitre `extraction.CODES_DE_SORTIE`
#: (`EPIC11-ARB-75`) et `scan_detect.REFUS_DU_COEUR` (story 11.6, lot B) : la
#: TUI doit nommer ces refus a l'ecran et a interdiction d'importer `cli.py`.
#: Dupliquer le vocabulaire laisserait deux verites au meme moment, et un test
#: symetrique ne rougirait qu'**apres** qu'on a diverge.
#:
#: **`video_metadata.FfprobeNotFoundError` n'y figure pas, et c'est delibere** :
#: un binaire absent n'est pas un jugement porte sur le rush, c'est un
#: prerequis externe manquant. `extraction.CODES_DE_SORTIE` le traite deja
#: comme tel -- code `2`, pas `1` -- et le rabattre sur
#: `MOTIF_SOURCE_NON_QUALIFIEE` effacerait cette distinction pour l'appelant.
#: Il reste **nomme** (une exception de la table `CODES_DE_SORTIE`, portant un
#: message actionnable en francais), jamais une trace Python nue.
MOTIFS_DE_REFUS: tuple[str, ...] = (
    MOTIF_PROJET_SANS_MANIFESTE,
    MOTIF_FICHIER_INTROUVABLE,
    MOTIF_CHEMIN_NON_FICHIER,
    MOTIF_SOURCE_NON_QUALIFIEE,
    MOTIF_RUSH_DEJA_DECLARE,
)

#: Les issues offertes par chaque refus, **par identite et jamais par recopie**.
#:
#: `EPIC11-ARB-89` exige au moins deux issues de toute fonctionnalite qui
#: **ecrirait par-dessus** une sortie existante. Les **quatre premiers** refus
#: tombent avant la moindre ecriture et ne detruiraient rien : ils ont chacun
#: **une** issue, et c'est l'application de l'arbitrage par son critere -- la
#: destruction -- et non par sa forme.
#:
#: **Le cinquieme en porte TROIS depuis `EPIC11-ARB-231`** (Egan, 2026-09-05,
#: choix verbatim : « Une 3e sortie sur l'ecran »), et l'ordre porte la
#: recommandation :
#:
#: 1. **relinker** -- c'est le meme rush a un autre endroit, le projet doit
#:    suivre le fichier ;
#: 2. **c'est un autre rush, le declarer separement** -- le contre-exemple
#:    n'est pas hypothetique : deux cameras jam-synchronisees, cartes
#:    formatees pareil, `prise01.mov` sur les deux. Les quatre criteres
#:    coincident et ce sont pourtant deux angles. En ligne de commande cette
#:    sortie prend la forme de `--force-distinct` (`EPIC11-ARB-232`), **cite
#:    dans le refus** ;
#: 3. **annuler** -- rien n'a ete ecrit, il n'y a rien a defaire.
#:
#: **Ce que ca retire a `EPIC11-ARB-147`, dit plutot que tu** : il posait un
#: refus SEC a issue UNIQUE et il est **supersede sur ce point precis**, par
#: le choix explicite d'Egan. Il tient sur tout le reste -- rien n'est ecrit,
#: rien n'est modifie. Le motif qui l'avait fonde (« choisir entre deux facons
#: de ne rien faire ») est tombe avec `EPIC11-ARB-230` : deux des trois issues
#: **font** quelque chose, et la troisieme n'existe que parce qu'un blocage
#: sec est interdit.
ISSUES_PAR_MOTIF: Mapping[str, tuple[str, ...]] = {
    MOTIF_PROJET_SANS_MANIFESTE: (
        "ouvrir un projet existant, ou en creer un avant de lui ajouter un rush",
    ),
    MOTIF_FICHIER_INTROUVABLE: (
        "designer un fichier qui existe",
    ),
    MOTIF_CHEMIN_NON_FICHIER: (
        "designer le fichier video lui-meme, pas le dossier qui le contient",
    ),
    MOTIF_SOURCE_NON_QUALIFIEE: (
        "reencoder le rush en cadence constante dans un conteneur qui declare "
        "sa duree, puis le declarer a nouveau",
    ),
    MOTIF_RUSH_DEJA_DECLARE: (
        "relinker le rush deja declare vers ce fichier: "
        "`mmu relink --project <projet> --rush <rush_id> --video <fichier>`",
        "c'est un autre rush malgre les quatre criteres identiques (deux "
        "cameras jam-synchronisees, par exemple): le declarer separement avec "
        "`mmu project add-rush --project <projet> --video <fichier> "
        "--force-distinct`",
        "annuler: rien n'a ete ecrit et rien n'a ete modifie, il n'y a rien a "
        "defaire",
    ),
}


class RefusDeDeclaration(RuntimeError):
    """Un des cinq refus de :data:`MOTIFS_DE_REFUS`, **nomme**.

    Porte son `motif` -- l'une des cinq constantes -- et ses `issues`, pour que
    la CLI comme la TUI les lisent au lieu de les rediger. Le message, lui, est
    en francais et actionnable : il ne remonte jamais en trace Python devant un
    operateur.

    **Il porte aussi de quoi EXPLIQUER, depuis la fermeture de `C-2`**
    (`EPIC11-ARB-148`, AC 3.6 bis) : `source_name` sur les cinq refus,
    `rush_id`, `entree` et `criteres` sur celui qui constate un identifiant
    deja pris. Sans eux, un ecran de refus ne pouvait ni nommer le rush ni dire
    **sur quoi** la machine l'a juge identique -- et le contourner en relisant
    le manifeste depuis la TUI aurait pose une seconde source de verite pour la
    meme comparaison, ce qu'`EPIC11-ARB-148` demande de tenir a un seul
    endroit.

    **Expliquer n'est pas offrir une issue de plus**, et la distinction est
    l'arbitrage lui-meme : `EPIC11-ARB-147` tient, le rush deja declare reste
    un refus **SEC** a une seule issue. :data:`ISSUES_PAR_MOTIF` n'a pas bouge
    d'une entree.

    Les quatre attributs neufs sont **optionnels et par defaut `None`** : un
    appelant qui construit un refus a la main -- c'est le cas d'un banc qui
    substitue le coeur -- garde exactement la signature d'avant.
    """

    def __init__(
        self,
        message: str,
        *,
        motif: str,
        issues: tuple[str, ...],
        source_name: str | None = None,
        rush_id: str | None = None,
        entree: Mapping[str, Any] | None = None,
        criteres: ConflitIdentiteRush | None = None,
    ) -> None:
        super().__init__(message)
        self.motif = motif
        self.issues = issues
        #: Le nom de base du fichier que l'operateur a **designe** -- accents et
        #: espaces compris, jamais l'identifiant derive (`EPIC11-ARB-153`).
        #: Pose par les cinq refus : un ecran doit pouvoir nommer ce qu'il
        #: refuse, quel que soit le motif.
        self.source_name = source_name
        #: L'identifiant deja pris, sur le seul refus qui en constate un
        #: (`MOTIF_RUSH_DEJA_DECLARE`). `None` partout ailleurs.
        self.rush_id = rush_id
        #: L'entree `rushes[]` **qui bloque**, copiee. C'est elle qui porte les
        #: valeurs declarees a montrer a l'operateur -- son propre
        #: `source_name`, sa duree, sa cadence, son timecode.
        self.entree = entree
        #: La **preuve** de la comparaison, partitionnee en divergents /
        #: concordants / non verifiables (`EPIC11-ARB-148`). `None` sur les
        #: refus qui ne comparent rien.
        self.criteres = criteres


def _refus(
    motif: str,
    message: str,
    *,
    source_name: str | None = None,
    rush_id: str | None = None,
    entree: Mapping[str, Any] | None = None,
    criteres: ConflitIdentiteRush | None = None,
    issues: tuple[str, ...] | None = None,
) -> RefusDeDeclaration:
    """Lever un refus dont les issues sont **lues** dans la table publiee.

    **`issues=` n'est pas une porte derobee, c'est la fermeture d'un defaut
    mesure** (2026-09-05, sur le terrain d'`EPIC11-ARB-233`). Un refus se rend
    en DEUX endroits -- la prose du message, et la liste structuree que la CLI
    et la TUI impriment -- et seule la prose savait s'adapter. Au troisieme
    homonyme, la prose disait « `--force-distinct` rendrait ce meme nom » et la
    liste structuree, juste en dessous, proposait toujours `--force-distinct` :
    deux issues contradictoires dans la meme sortie. La table reste le defaut
    et le cas general ; ce parametre sert au seul regime ou une issue de la
    table serait FAUSSE.
    """
    return RefusDeDeclaration(
        message,
        motif=motif,
        issues=ISSUES_PAR_MOTIF[motif] if issues is None else issues,
        source_name=source_name,
        rush_id=rush_id,
        entree=entree,
        criteres=criteres,
    )


#: Les refus que ce coeur leve et que ses enveloppeurs convertissent, sur le
#: modele exact de `scan_detect.REFUS_DU_COEUR`. Un seul type aujourd'hui : les
#: cinq motifs sont cinq valeurs d'un meme refus, pas cinq classes.
REFUS_DU_COEUR: tuple[type[BaseException], ...] = (RefusDeDeclaration,)


CODE_SUCCES = 0
CODE_ERREUR = 1
CODE_PREREQUIS_ABSENT = 2

#: La table exception -> code de sortie de la declaration, **seule source de
#: verite**. Meme forme et memes valeurs que `extraction.CODES_DE_SORTIE`, dont
#: elle est le sous-ensemble utile ici : declarer ne selectionne aucune frame,
#: n'appelle jamais ffmpeg et ne demande aucune confirmation, donc ni le code
#: `3` ni les erreurs de selection n'ont de sens sur ce chemin.
#:
#: **L'ordre est semantique** et reproduit celui d'une pile d'`except` : la
#: recherche rend la premiere entree qui correspond, et le filet `OSError` ne
#: doit jamais preceder une entree nommee.
CODES_DE_SORTIE: tuple[tuple[type[BaseException], int], ...] = (
    (RefusDeDeclaration, CODE_ERREUR),
    (NamingError, CODE_ERREUR),
    (ExtractionInputError, CODE_ERREUR),
    (source_confirmation.SourceReportError, CODE_ERREUR),
    (video_metadata.FfprobeNotFoundError, CODE_PREREQUIS_ABSENT),
    (video_metadata.FfprobeError, CODE_ERREUR),
    (LegacyManifestError, CODE_ERREUR),
    (ManifestWriteError, CODE_ERREUR),
    (ExtractionPersistenceError, CODE_ERREUR),
    (ValidationError, CODE_ERREUR),
    # Filet, et **toujours en dernier** : disque plein, projet en lecture
    # seule. Des pannes ordinaires, jamais une trace Python.
    (OSError, CODE_ERREUR),
)


def correspondance_de_sortie(
    exception: BaseException,
) -> tuple[type[BaseException], int] | None:
    """L'entree de :data:`CODES_DE_SORTIE` qui attrape `exception`, ou `None`.

    Rend `None` pour ce que la table ne nomme pas : l'appelant **relaie** alors
    l'exception au lieu de la deguiser en refus metier.
    """
    for classe, code in CODES_DE_SORTIE:
        if isinstance(exception, classe):
            return classe, code
    return None


def code_de_sortie(exception: BaseException) -> int | None:
    """Le code de sortie de la declaration pour `exception`, ou `None`."""
    correspondance = correspondance_de_sortie(exception)
    return None if correspondance is None else correspondance[1]


# --------------------------------------------------------------------------
# Le resultat, des faits et jamais une phrase
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class DeclarationDeRush:
    """Ce que la declaration a produit -- des faits, jamais des phrases.

    Aucun message compose n'y entre : la CLI redige les siens a partir de ces
    faits, la TUI redige les siens a partir des memes faits, et les deux disent
    donc la meme chose sans qu'aucune ne recopie l'autre.
    """

    #: Le `rush_id` reellement ecrit -- suffixe si `EPIC11-ARB-9` a joue.
    rush_id: str
    #: Le `rush_id` derive du seul nom de fichier, avant toute levee
    #: d'homonymie. Egal a `rush_id` dans le cas ordinaire.
    rush_id_derive: str
    #: `True` quand `EPIC11-ARB-9` a distingue deux rushes homonymes venus de
    #: deux dossiers differents. Ce n'est **pas** un refus : c'est un succes,
    #: et l'operateur en est informe par le journal.
    homonymie_levee: bool
    #: Nom du dossier parent du rush, ou `None`. Nom seul, jamais un chemin.
    source_parent: str | None
    #: `True` quand la separation a ete **demandee** par `--force-distinct`
    #: (`EPIC11-ARB-232`) plutot que constatee sur une divergence technique.
    #: Les deux levent une homonymie ; les confondre dirait a l'operateur que
    #: l'outil a juge la ou c'est lui qui a tranche.
    separation_forcee: bool
    #: Nom de base du fichier source.
    source_name: str
    #: Chemin absolu resolu du fichier source, au moment de la declaration.
    source_path: str
    #: Cadence source typee, telle qu'ecrite au manifeste.
    fps_source: float
    #: Le `project.json` ecrit.
    manifest_path: Path
    #: L'entree `rushes[]` telle qu'elle vient d'etre ecrite.
    entree: Mapping[str, Any]


# --------------------------------------------------------------------------
# Les trois etapes, nommees -- l'ordre se mesure sur elles
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class _ProjetOuvert:
    """Ce que les gardes bon marche ont etabli avant tout sous-processus."""

    project_dir: Path
    manifest_path: Path
    manifeste: Mapping[str, Any]
    project_id: str


def _gardes_bon_marche(project_dir: Path, video_path: Path) -> _ProjetOuvert:
    """Etape 1 : **toutes** les validations qui ne coutent pas un sous-processus.

    Elles precedent le probe, et le probe precede l'ecriture : c'est
    `EPIC5-ARB-34`, « un refus qui arrive apres une destruction n'est pas un
    refus ». Le lire ici plutot que dans la prose du point d'entree est
    volontaire -- l'ordre se mesure a l'execution, sur ces trois fonctions.
    """
    manifest_path = project_dir / MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise _refus(
            MOTIF_PROJET_SANS_MANIFESTE,
            f"Aucun projet ouvert dans {project_dir}: il n'y porte pas de "
            f"{MANIFEST_FILENAME}. Declarer un rush ajoute une entree a un projet "
            "existant, cela n'en cree jamais un.",
            source_name=video_path.name,
        )

    try:
        manifeste = load_manifest(manifest_path)
    except (ValueError, OSError) as exc:
        # `json.JSONDecodeError` derive de `ValueError`: un `project.json`
        # tronque -- coupure de courant, copie interrompue -- ne remonte jamais
        # en trace nue devant un operateur.
        raise _refus(
            MOTIF_PROJET_SANS_MANIFESTE,
            f"Le {MANIFEST_FILENAME} de {project_dir} n'a pas pu etre lu ({exc}). "
            "Aucune ecriture n'a eu lieu. Restaurer une copie saine du "
            "project.json, ou repartir d'un dossier projet ouvert.",
            source_name=video_path.name,
        ) from exc

    if not video_path.exists():
        raise _refus(
            MOTIF_FICHIER_INTROUVABLE,
            f"Fichier video introuvable: {video_path}",
            source_name=video_path.name,
        )
    if not video_path.is_file():
        raise _refus(
            MOTIF_CHEMIN_NON_FICHIER,
            f"Le chemin source n'est pas un fichier: {video_path}. Declarer un "
            "rush designe le fichier video lui-meme, jamais le dossier qui le "
            "contient.",
            source_name=video_path.name,
        )

    # Le `project_id` du manifeste fait foi : declarer un rush n'a jamais a
    # rebaptiser un projet. A defaut -- un manifeste ancien qui ne le porterait
    # pas --, il se derive du nom du dossier, exactement comme dans
    # `run_extraction`, par le meme appel et non par une seconde redaction.
    project_id = manifeste.get("project_id") or normalize_identifier(
        project_dir.resolve().name or project_dir.name,
        label="le nom du dossier projet",
    )

    return _ProjetOuvert(
        project_dir=project_dir,
        manifest_path=manifest_path,
        manifeste=manifeste,
        project_id=project_id,
    )


@dataclass(frozen=True)
class _IdentiteDuRush:
    rush_id: str
    rush_id_derive: str
    homonymie_levee: bool
    source_parent: str | None
    #: `True` quand la separation vient de `--force-distinct` et non d'une
    #: divergence technique (`EPIC11-ARB-232`). Les deux levent une homonymie ;
    #: une seule est un choix de l'operateur, et le compte rendu ne doit pas
    #: les confondre.
    separation_forcee: bool = False


@dataclass(frozen=True)
class _IdentiteProvisoire:
    """Ce que l'etape 1 sait de l'identite **sans avoir rien mesure**.

    Elle ne tranche pas : depuis `EPIC11-ARB-230`, ce qui separe deux rushes
    homonymes est une divergence **technique** -- cadence, duree, timecode
    initial --, et aucune des trois n'est connue avant le probe. Trancher ici
    reviendrait a trancher sur le dossier parent, c'est-a-dire sur le critere
    que l'arbitrage vient de retirer.
    """

    rush_id_derive: str
    source_parent: str | None
    #: L'entree deja declaree sous `rush_id_derive`, ou `None`. Sa presence ne
    #: veut pas dire « conflit » : elle veut dire « il faudra trancher ».
    bloquante: Mapping[str, Any] | None


def _preuve_de_l_identite(
    entree: Mapping[str, Any],
    source_parent: str | None,
    mesures: CriteresIdentiteRush | None = None,
) -> ConflitIdentiteRush:
    """La **preuve** sur laquelle le refus s'appuie, des deux cotes.

    `EPIC11-ARB-148` : un ecran ne doit pas seulement dire qu'il refuse, il
    doit dire **sur quoi** la machine a juge. Le verdict est calcule par les
    fonctions publiques d'`extraction` -- `CriteresIdentiteRush.declares` et
    `comparer_identite_rush` --, jamais par une seconde redaction : c'est le
    meme comparateur que `rush_identity_conflict` emploie, avec la meme
    normalisation (`_texte_ou_none`, importe plutot que recopie, comme
    `_source_parent_name` l'est deja depuis le lot A).

    **Le cote MESURE porte les trois criteres depuis `EPIC11-ARB-230`, et ce
    n'est pas un confort d'affichage : c'est ce qui rend l'arbitrage
    applicable.** Le dossier parent ayant cesse d'etre un critere d'identite,
    un refus prononce avant le probe n'aurait plus rien de comparable -- les
    trois criteres sortiraient tous en `non_verifiables` -- et la separation
    silencieuse d'`EPIC11-ARB-9`, que `ARB-230` **subordonne sans l'annuler**,
    ne pourrait plus jamais jouer : le multicam ordinaire (deux prises de
    durees differentes) serait refuse au lieu de se separer tout seul.

    `mesures` reste optionnel, et son absence est le regime du refus **bon
    marche** : quand l'operateur redesigne le fichier deja enregistre a ce
    chemin, aucune mesure ne peut changer le verdict (voir
    :func:`_identite_provisoire`), donc aucune n'est payee et les trois
    criteres sont **dits** non verifiables plutot qu'inventes.
    """
    verdict = comparer_identite_rush(
        CriteresIdentiteRush.declares(entree),
        mesures
        if mesures is not None
        else CriteresIdentiteRush(source_parent=_texte_ou_none(source_parent)),
    )
    # `comparer_identite_rush` est pure et laisse `entree` vide : elle ne
    # connait que deux jeux de criteres. On y pose l'entree qui bloque, par le
    # meme geste, champ pour champ, que `rush_identity_conflict` emploie deja
    # pour le cas divergent -- et non par `dataclasses.replace`, dont le nom
    # ferait rougir a tort la frontiere negative de l'AC 1.2 (« aucune seconde
    # derivation : ni `re`, ni `unicodedata`, ni `.replace` »).
    return ConflitIdentiteRush(
        entree=dict(entree),
        declares=verdict.declares,
        mesures=verdict.mesures,
        divergents=verdict.divergents,
        concordants=verdict.concordants,
        non_verifiables=verdict.non_verifiables,
    )


def _entree_sous(rushes: Any, rush_id: str) -> Mapping[str, Any] | None:
    """L'entree `rushes[]` portant ce `rush_id`, ou `None`.

    La recherche se fait par `rush_id`, **jamais par position** : `rushes[]`
    n'est pas trie et la cible peut etre en tete comme en queue.
    """
    return next(
        (
            rush
            for rush in (rushes or [])
            if isinstance(rush, Mapping) and rush.get("rush_id") == rush_id
        ),
        None,
    )


def _entree_au_chemin(rushes: Any, video_path: Path) -> Mapping[str, Any] | None:
    """L'entree `rushes[]` deja enregistree a CE chemin absolu, s'il y en a une.

    Le pendant de :func:`_entree_sous`, sur l'autre cle d'unicite du manifeste.
    Un `rush_id` ne peut designer qu'une entree, et un chemin source ne peut
    etre declare qu'une fois : la seconde declaration serait un doublon, pas
    une distinction -- et `--force-distinct` ne la rachete pas, puisque le
    drapeau affirme que c'est un AUTRE rush.

    Le chemin est compare **resolu des deux cotes** : `source_path` est ecrit
    resolu par `_build_rush_entry`, et un operateur qui redesigne le meme
    fichier par un chemin relatif ou par un lien doit tomber sur la meme
    entree.
    """
    try:
        cible = str(video_path.resolve())
    except OSError:  # pragma: no cover - un chemin illisible echoue plus loin
        return None
    for rush in rushes or []:
        if not isinstance(rush, Mapping):
            continue
        if _texte_ou_none(rush.get("source_path")) == cible:
            return rush
    return None


def _refus_de_rush_deja_declare(
    video_path: Path,
    rush_id: str,
    bloquante: Mapping[str, Any],
    source_parent: str | None,
    project_dir: Path,
    mesures: CriteresIdentiteRush | None,
    *,
    issue_de_remplacement: str | None = None,
) -> RefusDeDeclaration:
    """Le refus de conflit d'identite, avec ses TROIS issues et sa preuve.

    `EPIC11-ARB-230` : les quatre criteres coincident, c'est le meme rush,
    quel que soit le dossier. `EPIC11-ARB-231` : trois sorties, et jamais un
    blocage sec. `EPIC11-ARB-232` : en ligne de commande, la seconde sortie
    prend la forme de `--force-distinct`, **cite ici** -- la cloture
    d'`EPIC11-ARB-224` a pose qu'une commande nommee dans un refus doit etre
    tapable, doit parser, et doit changer quelque chose.

    Les deux commandes sont citees avec les valeurs **reelles** de cet
    appel-la, pas avec des gabarits : un operateur bloque doit pouvoir les
    recopier telles quelles.

    **`issue_de_remplacement` a remplace `suffixe_epuise`, et il tient
    desormais DEUX regimes au lieu d'un** (`EPIC11-ARB-233`, 2026-09-05). Le
    parametre existe pour la troisieme condition d'`EPIC11-ARB-224`, la plus
    facile a perdre : une commande citee dans un refus doit etre tapable, doit
    parser, et doit **changer quelque chose**. Citer `--force-distinct` la ou
    le drapeau ne changerait rien offre une boucle a l'operateur, c'est-a-dire
    le « blocage sec deguise » qu'`EPIC11-ARB-89` interdit.

    Ce que le suffixe de RANG a change : le regime d'origine -- « le suffixe de
    dossier est deja pris » -- a **disparu**, le rang etant toujours libre. Il
    reste ces deux-la, tous deux mesures :

    * **le meme FICHIER, deja declare** (a n'importe quel identifiant) : forcer
      ne separerait pas ce fichier de lui-meme, cela poserait deux entrees sur
      le meme chemin absolu ;
    * **les 98 rangs consommes** : la seule borne qui reste. Le texte est celui
      que `version_ranks.refus_de_rangs_epuises` redige -- une seule redaction
      pour tous les objets.

    Le remplacement porte **aussi** sur la liste structuree d'issues : la prose
    et la liste sont deux rendus du meme refus, et un seul des deux savait
    s'adapter jusqu'ici -- au troisieme homonyme, la prose disait que
    `--force-distinct` rendrait le meme nom pendant que la liste, deux lignes
    plus bas, le proposait toujours.
    """
    if issue_de_remplacement is not None:
        seconde_issue = issue_de_remplacement
    else:
        seconde_issue = (
            f"declarer un SECOND rush si c'est reellement un autre (deux "
            f"cameras jam-synchronisees, par exemple) avec "
            f"`mmu project add-rush --project {project_dir} "
            f"--video {video_path} --force-distinct`"
        )
    return _refus(
        MOTIF_RUSH_DEJA_DECLARE,
        f"Le rush {rush_id} est deja declare dans ce projet et les criteres "
        f"d'identite coincident: meme nom, meme duree, meme cadence, meme "
        f"timecode initial. Le dossier ne les separe pas (EPIC11-ARB-230). "
        f"Rien n'a ete ecrit et rien n'a ete modifie. Trois issues: relinker "
        f"le rush existant vers ce fichier avec "
        f"`mmu relink --project {project_dir} --rush {rush_id} "
        f"--video {video_path}`; {seconde_issue}; ou ne rien faire.",
        source_name=video_path.name,
        rush_id=rush_id,
        entree=dict(bloquante),
        criteres=_preuve_de_l_identite(bloquante, source_parent, mesures),
        issues=None if issue_de_remplacement is None else (
            ISSUES_PAR_MOTIF[MOTIF_RUSH_DEJA_DECLARE][0],
            issue_de_remplacement,
            ISSUES_PAR_MOTIF[MOTIF_RUSH_DEJA_DECLARE][2],
        ),
    )


def _identite_provisoire(
    projet: _ProjetOuvert, video_path: Path
) -> _IdentiteProvisoire:
    """Etape 1 (suite) : le `rush_id` derive, et le seul refus qu'on peut
    encore prononcer **sans sous-processus**.

    `EPIC11-ARB-146` : le corps de la derivation est **appele**, jamais
    reecrit.

    **Ce qui reste bon marche, et pourquoi c'est exactement ce cas-la.**
    Quand une entree deja declaree pointe sur le **fichier meme** que
    l'operateur redesigne -- meme chemin absolu resolu --, aucune mesure ne
    peut changer le verdict : les quatre criteres seront ceux de ce fichier,
    des deux cotes. Le refus tombe donc ici, sans probe -- `EPIC5-ARB-34` est
    tenu la ou il peut l'etre.

    **Le chemin se cherche sur TOUTE la liste, et pas seulement sous le
    `rush_id` derive** (trouve en mesure le 2026-09-05, en portant
    `EPIC11-ARB-233`). Avant lui, une redeclaration du meme fichier deja
    enregistre sous un identifiant LEVE -- `prise01-2`, jamais `prise01` --
    passait cette garde et n'etait arretee qu'accidentellement, plus bas, par
    la verification « l'identifiant leve est-il deja pris ». Le suffixe etant
    desormais un rang toujours libre, cette verification a disparu avec le
    regime qui la rendait atteignable, et le trou serait devenu reel : deux
    entrees pointant sur le **meme chemin absolu**, c'est-a-dire un doublon et
    non une distinction, ce qu'`EPIC11-ARB-232` n'a jamais autorise. La garde
    est donc posee la ou l'invariant vit -- un chemin source, une entree --
    plutot que la ou un nom coincidait.

    Tout le reste est **remis a apres le probe** : depuis `EPIC11-ARB-230`, le
    dossier ne separe plus rien, et ce qui separe -- cadence, duree, timecode
    initial -- n'est pas encore mesure.
    """
    rush_id_derive = normalize_identifier(
        video_path.stem, label="le nom du fichier source"
    )
    source_parent = _source_parent_name(video_path)
    rushes = projet.manifeste.get("rushes")
    bloquante = _entree_sous(rushes, rush_id_derive)

    deja_a_ce_chemin = _entree_au_chemin(rushes, video_path)
    if deja_a_ce_chemin is not None:
        # **`--force-distinct` reste cite ici, et ce n'est pas un oubli.** Sur
        # ce refus-la -- le meme FICHIER, deja declare -- le drapeau serait
        # refuse par cette meme garde : une issue qui parse et qui boucle,
        # c'est-a-dire la troisieme condition d'`EPIC11-ARB-224` en defaut.
        # L'ecart PREEXISTE a `EPIC11-ARB-233` (le refus du meme fichier citait
        # deja le drapeau, et `force_distinct=True` sur ce chemin etait deja
        # refuse) : il est donc porte a `deferred-work.md` plutot que corrige
        # ici, ou il elargirait le scope de la story.
        raise _refus_de_rush_deja_declare(
            video_path,
            str(deja_a_ce_chemin.get("rush_id") or rush_id_derive),
            deja_a_ce_chemin,
            source_parent,
            projet.project_dir,
            None,
        )

    return _IdentiteProvisoire(
        rush_id_derive=rush_id_derive,
        source_parent=source_parent,
        bloquante=bloquante,
    )


def _trancher_l_identite(
    projet: _ProjetOuvert,
    provisoire: _IdentiteProvisoire,
    mesures: CriteresIdentiteRush,
    video_path: Path,
    logger: logging.Logger,
    *,
    force_distinct: bool,
) -> _IdentiteDuRush:
    """Etape 2 (suite) : trancher l'identite **sur la mesure**, jamais sur le
    dossier.

    Trois issues et trois seulement, dans cet ordre :

    * un critere **technique** diverge -- `EPIC11-ARB-9` joue, l'identifiant
      est leve par un suffixe et c'est un **succes**, sans question posee.
      C'est le multicam ordinaire, et `EPIC11-ARB-230` le **subordonne** sans
      le retirer : deux prises differentes se separent toutes seules ;
    * rien ne diverge et l'operateur a pose `--force-distinct` : il affirme
      que c'est un autre rush (`EPIC11-ARB-232`), et l'outil le suit apres
      l'avoir journalise. C'est l'ecriture volontaire qu'`EPIC11-ARB-89`
      exige de laisser possible ;
    * rien ne diverge et rien n'a ete force : c'est le **meme rush**, refus a
      trois issues (`EPIC11-ARB-231`).

    **L'identifiant leve est libre PAR CONSTRUCTION, et c'est ce qui a
    change** (`EPIC11-ARB-233`, 2026-09-05). Le suffixe valait le dossier
    parent : deterministe, donc deux forcages depuis le meme dossier rendaient
    deux fois le meme nom, et ce module verifiait apres coup que le nom leve
    n'etait pas deja pris -- pour retomber, au troisieme homonyme, sur un refus
    sans issue qui ecrit. Le suffixe est desormais un RANG, choisi au-dessus de
    la ligne d'eau de la famille : il ne peut pas etre pris. La verification
    d'apres coup a donc disparu avec le regime qui la rendait atteignable, et
    ce que le banc mesure a sa place est l'invariant lui-meme -- sur une
    famille a trous et a rangs de bord, l'identifiant rendu n'est jamais l'un
    de ceux du manifeste.

    Le seul refus qui reste sur ce chemin est celui des **98 rangs consommes**,
    et il porte deux issues qui ecrivent.
    """
    rushes = projet.manifeste.get("rushes")
    rush_id = provisoire.rush_id_derive
    source_parent = provisoire.source_parent

    if provisoire.bloquante is None:
        return _IdentiteDuRush(
            rush_id=rush_id,
            rush_id_derive=rush_id,
            homonymie_levee=False,
            source_parent=source_parent,
        )

    conflit = rush_identity_conflict(
        rushes, rush_id, source_parent, mesures=mesures
    )
    if conflit is None and not force_distinct:
        raise _refus_de_rush_deja_declare(
            video_path,
            rush_id,
            provisoire.bloquante,
            source_parent,
            projet.project_dir,
            mesures,
        )

    try:
        rush_id_leve = disambiguated_rush_id(rush_id, rushes)
    except RangsDeDesambiguisationEpuises as epuisement:
        raise _refus_de_rush_deja_declare(
            video_path,
            rush_id,
            provisoire.bloquante,
            source_parent,
            projet.project_dir,
            mesures,
            issue_de_remplacement=str(epuisement),
        ) from epuisement
    if conflit is not None:
        logger.info(
            "Rush homonyme deja declare (%s, dossier %s): un critere technique "
            "diverge (%s), ce rush vient du dossier %s, il est donc identifie "
            "%s plutot que d'ecraser le premier",
            rush_id,
            conflit.entree.get("source_parent"),
            ", ".join(conflit.divergents),
            source_parent,
            rush_id_leve,
        )
    else:
        logger.info(
            "Rush deja declare sous %s et les criteres d'identite coincident, "
            "mais --force-distinct a ete pose (EPIC11-ARB-232): ce rush est "
            "declare separement sous %s. Rien n'a ete ecrase.",
            rush_id,
            rush_id_leve,
        )

    return _IdentiteDuRush(
        rush_id=rush_id_leve,
        rush_id_derive=rush_id,
        homonymie_levee=True,
        source_parent=source_parent,
        separation_forcee=conflit is None,
    )


@dataclass(frozen=True)
class _SourceQualifiee:
    fps_source: float
    start_timecode: str | None
    lecture: source_confirmation.LectureDeLaSource
    #: Le cardinal de frames que le conteneur declare ET que la duree du flux
    #: corrobore, ou `None`. **Ajoute a la liaison du 2026-09-05** : depuis
    #: `d244c307`, la duree est un critere d'identite du rush et
    #: `_build_rush_entry` l'ecrit. `None` est une absence assumee -- voir
    #: `_qualifier_la_source`.
    cardinal_de_frames: int | None
    #: La duree du flux video telle que le conteneur la declare, en secondes,
    #: ou `None`. **Ajoutee le 2026-09-05** pour `E2-1i` : c'est la grandeur qui
    #: a servi a TENTER la corroboration du cardinal, donc elle existe meme
    #: quand `cardinal_de_frames` vaut `None` -- et c'est exactement l'etat ou
    #: la maquette la reclame. Aucun probe de plus : elle est deja dans la
    #: qualification.
    duree_du_flux_secondes: float | None


def _qualifier_la_source(
    video_path: Path, *, ffprobe_binary: str, logger: logging.Logger
) -> _SourceQualifiee:
    """Etape 2 : le probe, **une seule fois**, et la cadence exigee (ARB-145).

    Les trois gardes sont celles de l'extraction, appelees et non reecrites :
    `qualify_source` (cadence absente, `0/0`, VFR), `cadence_corroboree`
    (`ARB-6` : une cadence annoncee mais inverifiable est refusee) et
    `lire_la_source` (flux video absent, resolution inexploitable).

    Le cardinal exact de la source n'est **pas** demande, et `-count_frames`
    n'est **jamais** paye : il decode le flux entier. C'est ce qui tient
    l'AC 1.5 -- `ffprobe` appele exactement une fois.

    **Corrige a la liaison du 2026-09-05.** Cette docstring disait « le
    cardinal n'entre pas dans l'entree `rushes[]` ». C'etait vrai le
    2026-09-01 et ca ne l'est plus : `d244c307` a fait de la **duree** un
    critere d'identite du rush (note 5 de la relecture d'Egan), stocke sur
    l'entree precisement pour qu'un rush **declare et pas encore extrait** le
    porte -- c'est-a-dire pour ce chemin-ci. Ce qui reste vrai est la depense :
    on ne prend que le cardinal que `extraction.cardinal_corrobore` valide sans
    sous-processus supplementaire, et on **omet** le critere sinon plutot que
    d'ecrire une estimation qui divergerait du comptage exact d'une extraction
    ulterieure.
    """
    # `FfprobeNotFoundError` n'est PAS attrapee ici, et c'est delibere: un
    # binaire absent est un prerequis externe manquant (code de sortie `2`),
    # jamais un jugement porte sur le rush. `FfprobeError`, elle, dit que le
    # fichier designe n'est pas une source exploitable -- c'est bien un des
    # cinq refus.
    try:
        probe = video_metadata.probe_media(
            str(video_path), ffprobe_bin=ffprobe_binary
        )
    except video_metadata.FfprobeError as exc:
        raise _refus(
            MOTIF_SOURCE_NON_QUALIFIEE,
            f"ffprobe n'a pas su lire {video_path.name}: {exc}. Verifier que le "
            "fichier est bien un rush video.",
            source_name=video_path.name,
        ) from exc

    try:
        qualification = qualify_source(probe)
    except (ExtractionInputError, video_metadata.FfprobeError) as exc:
        raise _refus(
            MOTIF_SOURCE_NON_QUALIFIEE, str(exc), source_name=video_path.name
        ) from exc

    if not qualification.cadence_corroboree:
        # `EPIC11-ARB-145` par le meme critere qu'`ARB-6`: l'outil ne sait pas
        # prouver qu'un tel rush est a cadence constante, donc la regle porte
        # sur la **non-verifiabilite**. Declarer ici produirait une entree
        # qu'aucune extraction ne pourrait honorer -- exactement l'entree qui
        # promet ce qu'elle ne tient pas.
        raise _refus(
            MOTIF_SOURCE_NON_QUALIFIEE,
            f"Cadence source inverifiable ({qualification.fps_source} im/s "
            "annoncee): ce conteneur ne declare ni la duree du flux video ni son "
            "nombre d'images, et les deux garde-fous contre une cadence variable "
            "y sont donc inoperants. Un rush declare sur une cadence fausse "
            "produirait des lots faux. Reencoder le rush en cadence constante "
            "dans un conteneur qui declare sa duree leve le refus.",
            source_name=video_path.name,
        )

    try:
        lecture = source_confirmation.lire_la_source(probe)
    except source_confirmation.SourceReportError as exc:
        raise _refus(
            MOTIF_SOURCE_NON_QUALIFIEE, str(exc), source_name=video_path.name
        ) from exc

    # Meme garde de coherence typee / exacte que `extraction._typed_rate`, et
    # au meme moment: avant la moindre ecriture. Le manifeste v2 porte les deux
    # formes et refuse de les ecrire si elles se contredisent.
    fps_source = float(qualification.fps_source)
    from .codec_profiles import exact_frame_rate

    if str(exact_frame_rate(fps_source)) != str(
        exact_frame_rate(qualification.fps_source)
    ):
        raise _refus(
            MOTIF_SOURCE_NON_QUALIFIEE,
            f"Cadence source non representable fidelement en nombre decimal: "
            f"{qualification.fps_source} donne {fps_source!r}, relu comme "
            f"{exact_frame_rate(fps_source)}. Le manifeste doit porter a la fois "
            "la valeur typee et la valeur exacte, et refuse de les ecrire si "
            "elles se contredisent.",
            source_name=video_path.name,
        )

    logger.info(
        "Source qualifiee: cadence %s im/s, %dx%d, timecode de depart %s",
        qualification.fps_source,
        lecture.width,
        lecture.height,
        qualification.start_timecode or "absent",
    )
    return _SourceQualifiee(
        fps_source=fps_source,
        start_timecode=qualification.start_timecode,
        lecture=lecture,
        cardinal_de_frames=cardinal_corrobore(qualification),
        duree_du_flux_secondes=qualification.stream_duration_seconds,
    )


# --------------------------------------------------------------------------
# Les DEUX temps, et le point d'entree qui les compose
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class DeclarationPreparee:
    """Ce qu'une declaration **ecrira**, sans que rien n'ait ete ecrit.

    C'est le temps 1 de la declaration, et c'est `EPIC11-ARB-4` qui l'exige :
    « obligatoire pour toute commande qui ecrit ». Une declaration ecrit
    `project.json`, donc l'operateur doit voir, chiffre, ce que l'outil
    s'apprete a y mettre, et pouvoir renoncer sans frais.

    **Le patron est celui de `tui.rushes.Apercu`** (`preparer_relink` /
    `ecrire_le_relink`), rejoue et non reinvente -- meme motif, meme coupure :
    ce que la sequence fait ensuite est un appel **separe**. La difference,
    voulue, tient a ce qu'un `Apercu` peut porter un refus alors qu'une
    `DeclarationPreparee` ne le peut pas : :func:`preparer_une_declaration`
    **leve**, comme tout ce module (« il leve et il rend »). Il n'existe donc
    aucune preparation invalide, et « rien n'est ecrit tant que ce n'est pas
    valide » est tenu par le **type**, sans garde a l'ecriture.

    Les chiffres que l'AC 3.3 demande a l'ecran sont tous ici -- le `rush_id`
    propose, le chemin retenu, la cadence source et le cardinal de frames
    **mesures par le probe** --, et il n'y a **aucun cout disque** : une
    declaration n'ecrit aucune image, et une ligne de cout a `0` serait une
    ligne fausse (`DESIGN.md` §3).

    Un champ non mesure vaut `None` et **s'omet** a l'affichage : c'est le cas
    de `cardinal_de_frames` quand la source ne le corrobore pas, et il ne se
    rend jamais `0` ni `--`.
    """

    #: Le dossier projet vise, tel que resolu par la preparation.
    project_dir: Path
    #: Le `project.json` qui sera reecrit.
    manifest_path: Path
    #: L'identite de projet qui fait foi (celle du manifeste, ou derivee).
    project_id: str

    #: Le `rush_id` qui **sera** ecrit -- suffixe si `EPIC11-ARB-9` a joue.
    rush_id: str
    #: Le `rush_id` derive du seul nom de fichier, avant levee d'homonymie.
    rush_id_derive: str
    #: `True` quand `EPIC11-ARB-9` a distingue deux rushes homonymes. Ce n'est
    #: pas un refus : c'est un succes, et l'ecran a de quoi le dire **avant**
    #: d'ecrire, plutot qu'apres.
    homonymie_levee: bool
    #: `True` quand la separation vient de `--force-distinct`
    #: (`EPIC11-ARB-232`) et non d'une divergence technique.
    separation_forcee: bool
    #: Nom du dossier parent du rush, ou `None`. Nom seul, jamais un chemin.
    source_parent: str | None

    #: Le VRAI nom du fichier designe -- accents et espaces compris, jamais
    #: l'identifiant derive (`EPIC11-ARB-153`, AC 3.4).
    source_name: str
    #: Le chemin absolu resolu, celui qui sera ecrit au manifeste.
    source_path: str

    #: Cadence source typee, mesuree par le probe.
    fps_source: float
    #: Resolution mesuree par le probe -- la ligne `1920 x 1080` de `E2-1e`.
    source_width: int
    source_height: int
    #: Timecode de depart, ou `None` quand la source n'en declare pas.
    source_start_timecode: str | None
    #: Cardinal de frames **corrobore**, ou `None`. Jamais une estimation.
    cardinal_de_frames: int | None
    #: Duree du flux video en secondes, telle que le conteneur la declare, ou
    #: `None`. Elle ne suit PAS le sort du cardinal : c'est elle qui sert a le
    #: corroborer, donc elle survit a son absence. C'est ce que la maquette
    #: `E2-1i` dessine -- `1920 x 1080 - 4:12` la ou le cardinal s'en va --, et
    #: ce qui manquait a l'ecran jusqu'au 2026-09-05.
    #:
    #: **Ce n'est pas une seconde source de verite sur la duree** : quand le
    #: cardinal est la, l'ecran derive toujours de `cardinal / fps`, qui est la
    #: grandeur exacte. Ce champ est le **repli**, pas le chemin nominal.
    duree_source_secondes: float | None

    #: L'enregistrement exact que :func:`ecrire_la_declaration` persistera.
    #: Equivalent du champ `manifeste` de `tui.rushes.Apercu` : « ce qui sera
    #: ecrit » est un objet, pas une promesse.
    record: RushRecord


def preparer_une_declaration(
    *,
    project_dir: str | Path,
    video_path: str | Path,
    logger: logging.Logger,
    ffprobe_binary: str = "ffprobe",
    force_distinct: bool = False,
) -> DeclarationPreparee:
    """Temps 1 : les gardes et le probe, et **rien d'ecrit** (`EPIC11-ARB-4`).

    Rend une :class:`DeclarationPreparee` -- de quoi dresser le panneau chiffre
    de l'AC 3.3 --, ou **leve** l'un des cinq refus de
    :data:`MOTIFS_DE_REFUS`. Aucun octet du projet n'est touche : la mesure de
    l'AC 1.8 (inodes, `st_mtime_ns`, temoin) vaut pour ce point d'entree comme
    pour un refus.

    **L'ordre des deux etapes qu'elle porte n'est pas negociable**
    (`EPIC5-ARB-34`) : gardes bon marche d'abord -- projet, manifeste lisible,
    fichier source, identite du rush, rush deja declare --, sous-processus
    ensuite. Un `ffprobe` paye pour un projet qui ne pouvait rien recevoir est
    exactement ce que la dette `B-3` reproche.

    `ffprobe` est appele **exactement une fois**, et c'est tout le motif de ce
    decoupage : l'ecran lit ses chiffres **ici** et ne resonde jamais la
    source. Un second probe depuis la TUI -- ou une seconde redaction de la
    qualification dans `tui/` -- etaient les deux contournements que le lot C a
    nommes plutot que d'en prendre un (`EPIC11-ARB-146`, AC 1.5).
    """
    project_dir = Path(project_dir)
    video_path = Path(video_path)

    # --- 1. gardes bon marche, toutes anterieures a tout sous-processus -----
    projet = _gardes_bon_marche(project_dir, video_path)
    provisoire = _identite_provisoire(projet, video_path)

    # --- 2. probe et qualification (EPIC11-ARB-145) -------------------------
    source = _qualifier_la_source(
        video_path, ffprobe_binary=ffprobe_binary, logger=logger
    )

    # --- 2 bis. l'identite se tranche SUR LA MESURE (EPIC11-ARB-230) --------
    # Elle ne peut pas se trancher plus tot : le dossier ayant cesse d'etre un
    # critere, ce qui separe deux homonymes -- cadence, duree, timecode
    # initial -- n'existe qu'apres le probe. Aucun probe de PLUS n'est paye :
    # c'est celui de l'etape 2, celui que l'AC 1.5 compte a un.
    identite = _trancher_l_identite(
        projet,
        provisoire,
        CriteresIdentiteRush.mesures(
            source_parent=provisoire.source_parent,
            fps_source=source.fps_source,
            source_frame_count=source.cardinal_de_frames,
            source_start_timecode=source.start_timecode,
        ),
        video_path,
        logger,
        force_distinct=force_distinct,
    )

    # Story 2.8 (AC 1, `EPIC7-ARB-41`): le chemin absolu RESOLU, jamais la
    # chaine telle que tapee -- declarer un rush est une **designation du
    # fichier par l'operateur**, au meme titre qu'un relink manuel.
    record = RushRecord(
        rush_id=identite.rush_id,
        source_name=video_path.name,
        fps_source=source.fps_source,
        source_width=source.lecture.width,
        source_height=source.lecture.height,
        source_fields=source.lecture.source_fields,
        source_start_timecode=source.start_timecode,
        source_parent=identite.source_parent,
        source_path=str(video_path.resolve()),
        # Le cardinal n'est ecrit que s'il est CORROBORE, donc exact. Absent,
        # il s'omet : `_build_rush_entry` ne pose alors ni le cardinal ni son
        # drapeau, et le critere de duree reste **non verifiable** au lieu de
        # devenir faussement divergent (liaison du 2026-09-05).
        source_frame_count=source.cardinal_de_frames,
        source_frame_count_is_exact=(
            None if source.cardinal_de_frames is None else True
        ),
    )

    return DeclarationPreparee(
        project_dir=project_dir,
        manifest_path=projet.manifest_path,
        project_id=projet.project_id,
        rush_id=identite.rush_id,
        rush_id_derive=identite.rush_id_derive,
        homonymie_levee=identite.homonymie_levee,
        separation_forcee=identite.separation_forcee,
        source_parent=identite.source_parent,
        source_name=video_path.name,
        source_path=record.source_path,
        fps_source=source.fps_source,
        source_width=source.lecture.width,
        source_height=source.lecture.height,
        source_start_timecode=source.start_timecode,
        cardinal_de_frames=source.cardinal_de_frames,
        duree_source_secondes=source.duree_du_flux_secondes,
        record=record,
    )


def ecrire_la_declaration(
    preparee: DeclarationPreparee, *, logger: logging.Logger
) -> DeclarationDeRush:
    """Temps 2 : l'ecriture, atomique et validee au schema, et elle seule.

    Ne decide rien : tous les refus sont tombes au temps 1. Ce qui peut encore
    echouer ici n'est plus un jugement porte sur le rush mais une panne
    d'ecriture -- disque plein, projet en lecture seule, manifeste devenu
    invalide --, et :data:`CODES_DE_SORTIE` la nomme deja.

    **Aucune garde de validite n'y figure, et c'est mesure plutot que promis**
    : `ecrire_le_relink` doit en porter une parce qu'un `Apercu` peut naitre
    porteur d'un refus. :func:`preparer_une_declaration` **leve** au lieu de
    rendre une preparation invalide, donc il n'existe aucune
    :class:`DeclarationPreparee` a refuser -- la garantie est portee par le
    type et non par la discipline de l'appelant, ce qui est plus fort.
    """
    persisted = persist_rush_declaration(
        preparee.project_dir, preparee.project_id, preparee.record
    )
    logger.info(
        "Manifest mis a jour: rush %s declare dans %s",
        preparee.rush_id,
        persisted.manifest_path,
    )

    entree = next(
        rush
        for rush in persisted.manifest["rushes"]
        if rush.get("rush_id") == preparee.rush_id
    )
    return DeclarationDeRush(
        rush_id=preparee.rush_id,
        rush_id_derive=preparee.rush_id_derive,
        homonymie_levee=preparee.homonymie_levee,
        separation_forcee=preparee.separation_forcee,
        source_parent=preparee.source_parent,
        source_name=preparee.source_name,
        source_path=preparee.source_path,
        fps_source=preparee.fps_source,
        manifest_path=persisted.manifest_path,
        entree=entree,
    )


# --------------------------------------------------------------------------
# Le point d'entree
# --------------------------------------------------------------------------


def declarer_un_rush(
    *,
    project_dir: str | Path,
    video_path: str | Path,
    logger: logging.Logger,
    ffprobe_binary: str = "ffprobe",
    force_distinct: bool = False,
) -> DeclarationDeRush:
    """Declarer `video_path` comme rush du projet `project_dir`, sans extraire.

    Rend un :class:`DeclarationDeRush`, ou **leve**. Aucun `print`, aucun code
    de sortie : les enveloppeurs -- `mmu project add-rush` et l'ecran
    `Ajouter un rush` -- lisent :data:`CODES_DE_SORTIE` et
    :data:`ISSUES_PAR_MOTIF`, et ne redigent ni l'un ni l'autre.

    Refus possibles, tous nommes par :data:`MOTIFS_DE_REFUS` et tous
    **anterieurs a la moindre ecriture**. `ffprobe` absent du PATH leve
    `video_metadata.FfprobeNotFoundError`, que :data:`CODES_DE_SORTIE` traite
    comme un prerequis externe (code `2`), pas comme un refus metier.

    Idempotence : il n'y en a pas. Declarer deux fois **le meme rush** -- les
    quatre criteres d'identite coincident, quel que soit le dossier
    (`EPIC11-ARB-230`) -- est un refus a **trois** issues (`EPIC11-ARB-231`) :
    relinker, declarer separement, ne rien faire. Rien n'est ecrase, rien
    n'est versionne.

    `force_distinct` est la deuxieme de ces trois issues, portee jusqu'au
    coeur (`EPIC11-ARB-232`) : l'operateur affirme que c'est un autre rush
    malgre les quatre criteres identiques -- deux cameras jam-synchronisees,
    cartes formatees pareil --, et l'outil le suit en levant l'identifiant par
    le suffixe d'`EPIC11-ARB-9`, apres l'avoir journalise. Il ne force **rien
    d'autre** : il ne desactive aucune garde et n'ecrase jamais une entree.

    **C'est desormais la COMPOSITION des deux temps**, et son contrat n'a pas
    bouge d'un mot-cle : `mmu project add-rush` et son banc l'appellent tel
    quel. Un appelant qui doit montrer un panneau chiffre **avant** d'ecrire --
    ce qu'`EPIC11-ARB-4` exige de l'ecran `Ajouter un rush` -- prend les deux
    temps separement : :func:`preparer_une_declaration` puis
    :func:`ecrire_la_declaration`. Un appelant qui n'a rien a montrer, comme la
    CLI, garde ce point d'entree-ci et ne paie pas la coupure.
    """
    return ecrire_la_declaration(
        preparer_une_declaration(
            project_dir=project_dir,
            video_path=video_path,
            logger=logger,
            ffprobe_binary=ffprobe_binary,
            force_distinct=force_distinct,
        ),
        logger=logger,
    )
