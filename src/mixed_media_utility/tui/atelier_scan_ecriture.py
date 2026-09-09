# -*- coding: utf-8 -*-
"""`E3-7` et `T6-1` -- l'ecriture des frames du Scan, et son interruption.

Story 11.6, lot E (AC 5 et AC 6). C'est la moitie qui **ecrit** de l'atelier
Scan : elle part du **document de detection deja pose** par le temps 1 et
appelle le point d'entree de coeur livre par le lot B --
:func:`~mixed_media_utility.scan_write.ecrire_depuis_le_document` --, heberge
par la coque.

**L'invariant que ce module existe pour tenir** (`EPIC11-ARB-6`) : le temps 2
**ne redetecte rien**. Il ne connait ni `run_scan_detect`, ni
`detect_lot_pages`, ni `ingest_scan_lot` ; il consomme un document deja ecrit,
et un comptage a zero a l'AST le mesure (AC 5.2). C'est ce qui rend « quitter
apres la detection et reprendre plus tard » vrai a la lettre : le document
reste **intact** apres l'ecriture, mesure aux inodes et au `st_mtime_ns`, pas
par condensat (AC 5.5).

**Ce que ce module ne fait pas, et c'est structurel :**

* il **ne lit aucun document de detection**. `gui/` en porte deja deux
  redactions et le coeur en porte la normative
  (`scan_write.lire_le_document_de_detection`) : une troisieme ici serait la
  faute que `EPIC11-ARB-108` nomme -- « un mecanisme, un lieu ». Le plan qu'il
  recoit porte des **chemins** de documents, jamais des documents relus ;
* il **n'ecrit aucun second mecanisme de progression** : `SurfaceExecution` et
  `progression.EmetteurProgression` sont livres, le canal est celui-la. La
  difference avec le temps 1 tient en une ligne : ici le `total` est **connu
  d'avance** -- c'est ce que le document promet --, donc
  `SurfaceExecution.emetteur(total)` s'emploie, la ou le temps 1 avait du s'en
  passer (AC 5.3) ;
* il **ne redonne ni ecran d'execution ni ecran d'interruption** : il
  *sous-classe* ceux d'`execution.py`, qui n'est **pas modifie** (AC 6.3) --
  c'est un module partage avec l'atelier Extraction, et le toucher serait la
  contention que la regle de decoupage interdit ;
* il **ne cable rien** : le raccord `E3-6` -> `E3-7` -> `E3-8` est le lot H.
  Les classes et les fonctions de ce module sont exposees et attendent leur
  appelant.

**Ce qu'il laisse ouvert, dit plutot que tu.** L'issue « Interrompre et
effacer » **demande** l'interruption et n'efface rien : voir
:func:`_interrompre` et :data:`CLE_EFFACER`. C'est le regime deja livre par
l'atelier Extraction (`atelier_extraction_ecriture._interrompre` traite ses
deux issues a l'identique), et la suppression propre d'un element de projet est
la troisieme operation d'`EPIC11-ARB-89`, portee par la story 11.11. Le rapport
**nomme** l'issue retenue (`RapportDEcriture.issue_d_interruption`) pour que le
jour ou ce mecanisme arrive, il se branche sur un fait deja mesure plutot que
sur une intention perdue.
"""

from __future__ import annotations

import dataclasses
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .. import scan_output_frames, scan_write
from ..io import project_layout
from ..io.extraction_manifest import MANIFEST_FILENAME
from ..io.naming import EXTRACTED_FRAME_SUFFIX
from .atelier_extraction_ecriture import (
    RelaisDeJournal,
    _lancer_apres_le_dessin,
    en_tete_de_lot,
)
from .execution import (
    EcranExecution,
    EcranInterruption,
    EcranRefus,
    SurfaceExecution,
)
from .panneau import Issue, LigneChiffree, Panneau

# ---------------------------------------------------------------------------
# Le vocabulaire de l'ecran -- une seule redaction, celle-ci
# ---------------------------------------------------------------------------

#: L'unite comptee par la barre. **Des frames**, contrairement au temps 1 qui
#: compte des pages : c'est le jalon que le coeur emet, « un jalon par frame
#: reellement ecrite, `total` valant `len(planned)` » (`scan_output_frames.`
#: `write_lot_output_frames`, verbatim).
UNITE = "frames"

#: L'en-tete de tache de `E3-7`, radical de la maquette
#: (`E3-7-scan-ecriture-en-cours.txt`, l. 5). Le rang du lot en cours n'y est
#: **pas** : il est inscrit au journal par :func:`en_tete_de_lot`, la ou
#: l'atelier Extraction le pose deja. Voir :func:`titre_de_la_tache`.
TITRE_DE_LA_TACHE = "Écriture des TIFF"

#: Le verbe de la passe, **verbatim de la maquette approuvee**
#: `E3-7-scan-ecriture-en-cours.txt` (l. 5 : `Écriture des TIFF — lot 1 sur 2`).
#: Il vaut ici le titre de tache, les deux maquettes le voulant identique --
#: mais c'est une coincidence de redaction et non une identite : `E2-4` dit
#: « Extraction en cours » la ou son titre de tache dit « Extraction de
#: rush_01 ». Le nom distinct dit lequel des deux l'ecran d'execution lit.
LIBELLE_DE_LA_PASSE = TITRE_DE_LA_TACHE

#: La droite du bandeau, verbatim de la maquette (l. 2). C'est ce qui distingue
#: l'ecran d'execution du temps 2 de celui du temps 1 (`E3-2`), qui n'ecrit
#: rien.
OBJET_DU_BANDEAU = "temps 2 sur 2 · écrire"

#: Le segment de bandeau -- l'atelier, pas le nom de la classe d'ecran. La
#: maquette porte `mmu · projet_demo · Scan`.
PALIER_DE_L_ATELIER = "Scan"

#: Le nom du journal du produit pour cette passe. Un nom **propre au temps 2**,
#: jamais celui de la detection et jamais le racine : deux passes qui
#: partageraient un nom de logger verraient leurs lignes tomber dans le journal
#: de l'autre, et un handler pose sur le racine capterait le bruit des
#: bibliotheques tierces.
NOM_DU_JOURNAL = "mixed_media_utility.tui.scan_ecriture"

#: Le titre du cartouche de `T6-1`. Il nomme un **etat du disque**, pas une
#: action : ce qui est deja ecrit l'est, que l'on interrompe ou non.
TITRE_DE_CE_QUI_EST_ECRIT = "Déjà écrit"

#: Ce que le cartouche de `T6-1` dit rester valide (AC 6.4). Reprendre plus
#: tard ne redemande donc pas de detecter (`EPIC11-ARB-6`), et c'est un
#: **fait** du temps 2, pas un conseil d'usage.
PHRASE_DOCUMENT_VALIDE = "reste valide"

#: Le libelle de la ligne qui porte ce fait.
LIBELLE_DOCUMENT = "Document de détection"

#: Ce qu'un refus du coeur declare n'avoir pas ecrit, quand le disque le
#: confirme. **Mesure et non promesse** : la phrase n'est posee que si le
#: comptage des frames du plan rend zero (voir :func:`executer_et_conclure`).
NON_ECRIT_PAR_UN_REFUS = "Aucune frame, aucune entrée de manifeste"

#: Ce qu'un refus conserve, toujours : le document de detection. C'est
#: l'artefact reutilisable d'`EPIC11-ARB-6`, et un refus d'ecriture ne le
#: touche pas.
CONSERVE_PAR_UN_REFUS = "Le document de détection, réutilisable tel quel"


def titre_de_la_tache(plan: "PlanDEcriture") -> str:
    """`Écriture des TIFF — 2 lots`, l'en-tete de tache de `E3-7`.

    **L'ecart avec la maquette est LEVE depuis la 11.4e** (AC 8.4). Ce
    docstring disait : « le rang du lot en cours n'est PAS dans ce titre [...]
    le mettre a jour a chaque lot demanderait de toucher `execution.py`, que
    l'AC 6.3 interdit ». L'AC 10.3 de la 11.4e a leve cette interdiction, et
    `EcranExecution` redessine desormais son bloc de tete a chaque jalon.

    Le rang ne vit donc plus **seulement** au journal : `E3-7` porte
    `Écriture des TIFF — lot 1 sur 2` comme sa maquette le montre, compose de
    :data:`LIBELLE_DE_LA_PASSE` et du rang que la surface tient. Ce titre-ci
    reste ce qu'il etait pour ses autres usages -- il nomme le nombre de lots,
    pas celui en cours.
    """
    lots = len(plan.lots)
    return f"{TITRE_DE_LA_TACHE} — {lots} lot{'s' if lots > 1 else ''}"


# ---------------------------------------------------------------------------
# Les refus du coeur sur le chemin de l'ecriture
# ---------------------------------------------------------------------------

#: **La table du coeur, LUE et jamais recopiee** (AC 5.5). `scan_write` publie
#: `CODES_DE_SORTIE` -- huit familles d'exceptions et leur code de sortie --, et
#: c'est elle que la CLI lit de l'autre cote. Une seconde redaction ici
#: divergerait au premier ajustement, ce que ce depot a deja paye trois fois
#: dans `project_maintenance` ; la dette symetrique cote detection
#: (`scan_detect` ne publiait aucune table) a d'ailleurs ete fermee par le
#: lot B de cette meme story.
#:
#: L'identite se lit a ce que ce module ne nomme **aucune** classe d'exception :
#: il derive ses classes de la table, dans son ordre.
CODES_DE_SORTIE: tuple[tuple[type[BaseException], int], ...] = (
    scan_write.CODES_DE_SORTIE)

#: Les seules classes que ce module attrape, dans l'ordre de la table du coeur.
REFUS_DU_COEUR: tuple[type[BaseException], ...] = tuple(
    classe for classe, _code in CODES_DE_SORTIE)


@dataclass(frozen=True)
class RefusDEcriture:
    """Un refus du coeur, **nomme par son code** et jamais par « echec ».

    `EPIC11-ARB-30` et `DESIGN.md` §9 : le code **et** la phrase viennent du
    coeur. Le code est le nom de la classe **levee**, pas celui de l'entree de
    la table qui l'a attrapee -- les deux different des qu'une exception herite
    d'une autre, et c'est la classe levee qui designe la panne.

    `motif` porte l'une des constantes de
    :data:`~mixed_media_utility.scan_write.MOTIFS_DE_REFUS_DU_DOCUMENT` quand
    le refus vient de la moitie haute du temps 2. C'est ce qu'une interface
    teste **sans lire de phrase** ; nommer un refus en cherchant un bout de
    texte casse a la premiere reformulation.
    """

    code: str
    message: str
    code_retour: int
    motif: str | None = None
    lot_id: str | None = None


def refus_de(exception: BaseException) -> RefusDEcriture | None:
    """Traduire une exception du coeur en refus nomme, ou rendre `None`.

    `None` signifie « la table ne nomme pas cette exception » : l'appelant
    **relaie** alors, il ne fabrique pas un refus metier. Deguiser une panne de
    programmation en refus lisible est exactement ce que la table existe pour
    empecher -- l'operateur lirait un motif rassurant sur un bug.
    """
    correspondance = scan_write.correspondance_de_sortie(exception)
    if correspondance is None:
        return None
    _classe, code_retour = correspondance
    return RefusDEcriture(
        code=type(exception).__name__,
        message=str(exception),
        code_retour=code_retour,
        # `getattr` et non un `isinstance` : seul le refus de document porte un
        # motif, et le lire par son nom evite de nommer la classe ici.
        motif=getattr(exception, "motif", None),
    )


# ---------------------------------------------------------------------------
# Le plan : ce que `E3-6` a confirme, et que `E3-7` execute
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LotAEcrire:
    """Un lot du plan : **un document de detection**, et ce qu'on en fait.

    `document` est un **chemin**, jamais un document relu : ce module ne lit
    aucun document (voir le docstring de tete). C'est le coeur qui le relit,
    par la redaction normative, et qui refuse nommement les huit cas ou il
    n'est pas consommable.

    `frames` est le total **connu d'avance** que la barre affiche : ce que le
    document promet pour ce lot. Il vient du panneau que `E3-6` a deja
    calcule (`atelier_scan_rapport.PanneauDeLot.frames_attendues`), jamais
    d'une seconde derivation ici.

    `dossier` est le dossier de sortie du lot, quand l'appelant le connait.
    Il sert **au comptage du disque** de `T6-1` (AC 6.6) et a rien d'autre :
    l'ecriture, elle, resout son dossier au coeur. `None` veut dire « je ne
    sais pas ou ce lot ecrit », et le comptage rend alors zero pour lui plutot
    que d'inventer un chemin -- voir :func:`dossier_de_sortie` pour la seule
    facon de le derive sans reecrire une regle du coeur.
    """

    document: Path
    lot_id: str
    frames: int
    dossier: Path | None = None
    overwrite: bool = False
    nouvelle_version: bool = False
    livrer_brut: bool = False
    appliquer_la_correction: bool = True
    divergence_bypass: bool = False
    profil_designe: Any = None
    origine_du_profil: str | None = None


@dataclass(frozen=True)
class PlanDEcriture:
    """Les lots que `E3-6` a confirmes, dans l'ordre ou ils s'ecrivent."""

    dossier_projet: Path
    lots: tuple[LotAEcrire, ...] = ()
    #: Le `project.json` deja lu, ou `None` -- la ligne d'eau des rangs de
    #: version. Relaye tel quel au coeur ; son absence signifie « aucune
    #: version employee », jamais « projet invalide ».
    manifest_du_projet: Any = None

    @property
    def frames(self) -> int:
        """Le total du plan, tous lots confondus -- ce que `T6-1` chiffre."""
        return sum(lot.frames for lot in self.lots)


@dataclass(frozen=True)
class LotEcrit:
    """Ce qu'un lot a **reellement** produit. Aucun champ n'est une phrase."""

    lot_id: str
    frames: int
    dossier: Path | None
    correction_appliquee: bool
    profil_de_chaine_utilise: bool
    #: L':class:`~mixed_media_utility.scan_write.EcritureDuLot` verbatim. Le
    #: resultat (`E3-8`, lot F) y lit son inventaire et sa degradation : les
    #: rederiver ici en ferait une seconde redaction.
    ecriture: Any = None


@dataclass(frozen=True)
class RapportDEcriture:
    """Ce qu'une passe du temps 2 a produit -- des faits, jamais des phrases.

    Les refus sont un **tuple** et non un champ unique, et c'est une propriete
    de la boucle : un lot refuse n'annule pas les suivants (voir
    :func:`ecrire_les_lots`).
    """

    ecrits: tuple[LotEcrit, ...] = ()
    refus: tuple[RefusDEcriture, ...] = ()
    interrompu: bool = False
    #: La cle de l'issue d'interruption retenue, ou `None`. Voir le docstring
    #: de tete : elle est **nommee** meme quand rien ne l'exécute encore.
    issue_d_interruption: str | None = None
    manifeste: Path | None = None

    @property
    def frames(self) -> int:
        return sum(lot.frames for lot in self.ecrits)


# ---------------------------------------------------------------------------
# Le comptage du DISQUE -- ce que `T6-1` annonce, et jamais un jalon
# ---------------------------------------------------------------------------

def dossier_de_sortie(dossier_projet, payload) -> Path:
    """Le dossier de sortie d'un lot, **par les deux fonctions du coeur**.

    Aucune recomposition de chemin ici : `derive_lot_dir_slug` possede la regle
    (« un `lot_id` borne EST le slug, sinon c'est `rush_dir_slug` ») et
    `scan_frames_dir_from_slug` possede la jointure, avec sa garde contre un
    slug qui serait un chemin absolu -- une valeur lue sur du papier scanne.

    Le document de detection en regime `detected` ne porte **pas**
    `subject.output_dir_relative` : le lecteur de `scan_previz` le refuse
    verbatim (« n'a pas de sens en regime 'detected' : aucune frame n'est
    encore ecrite »). C'est pourquoi cette derivation existe plutot qu'une
    lecture, et c'est mesure.

    **Les trois lectures ci-dessous sont GARDEES, et la garde est le sujet**
    (liaison du 2026-09-01, frontiere `test_pile_mixte_refus`). Le payload
    d'une **page de calibration** ne porte ni `rush_id`, ni `lot_id`, ni
    `fps_target` -- `io/payload.validate_payload` en **refuse** nommement la
    presence sur cette branche-la. Trois `payload[...]` nus faisaient donc de
    cette fonction la septieme occurrence d'une famille que le depot a corrigee
    six fois : une `KeyError` nue au lieu d'un refus, sur une feuille qui se
    trouve legitimement dans une pile mixte. Le refus est pose ici, il nomme
    les champs manquants, et l'inventaire de la frontiere le declare avec sa
    garde -- qui est **relue au source**, jamais crue sur parole.
    """
    manquants = [champ for champ in ("rush_id", "fps_target", "lot_id")
                 if champ not in payload]
    if manquants:
        raise ValueError(
            "Ce payload ne designe aucun lot a ecrire : "
            f"{', '.join(manquants)} absent(s). Une page de CALIBRATION est "
            "dans ce cas par contrat (`io/payload.validate_payload` refuse ces "
            "champs sur une page de calibration), et elle n'appartient a aucun "
            "dossier de sortie -- c'est un refus nomme, jamais une KeyError.")
    slug = scan_output_frames.derive_lot_dir_slug(
        rush_id=payload["rush_id"],
        fps_target=payload["fps_target"],
        lot_id=payload["lot_id"])
    return project_layout.scan_frames_dir_from_slug(dossier_projet, slug)


def frames_du_dossier(dossier: Path | None) -> int:
    """Les frames **presentes sur le disque** dans ce dossier.

    Le suffixe est lu de `io.naming.EXTRACTED_FRAME_SUFFIX` : le nom des frames
    de scan est bati par la meme recette (`naming.py:627-635`, « aucune seconde
    recette de nommage n'est ecrite »).

    **Toute panne de lecture rend zero plutot que de lever**, comme
    `_octets_du_dossier` cote extraction : `is_dir()` repond vrai sur un
    partage reseau demonte, et `iterdir()` leve alors -- une trace Python nue
    devant l'operateur au moment ou il demande a interrompre. Le compte est un
    renseignement ; il ne vaut pas de faire tomber l'ecran.
    """
    if dossier is None:
        return 0
    try:
        if not dossier.is_dir():
            return 0
        return sum(1 for entree in dossier.iterdir()
                   if entree.is_file()
                   and entree.suffix.lower() == EXTRACTED_FRAME_SUFFIX)
    except OSError:
        return 0


def frames_sur_le_disque(plan: PlanDEcriture) -> int:
    """Le compte du **disque** pour tout le plan (AC 6.6).

    **Ce n'est pas `avancement.faites`, et la difference n'est pas theorique** :
    le dernier jalon recu dit ce que le coeur a *annonce*, le disque dit ce
    qu'un effacement emporterait. Annoncer « 40 frames » et en effacer 41
    serait une destruction que l'ecran n'a pas annoncee -- c'est pour ce sens-la
    que l'AC exige le disque, et un test mesure que les deux comptes ne sont
    pas confondus.
    """
    return sum(frames_du_dossier(lot.dossier) for lot in plan.lots)


# ---------------------------------------------------------------------------
# Le canal de progression -- en frames, et sur un total connu d'avance
# ---------------------------------------------------------------------------

def canal_de_progression(surface: SurfaceExecution, total: int):
    """Le **seul** canal par lequel un jalon du coeur atteint `E3-7`.

    Deux faits mesures, et ce sont ceux de l'extraction -- la fonction est
    reecrite ici plutot qu'importee parce que le total du scan est celui d'un
    **document**, mais le mecanisme est le meme et il n'y en a pas un second :

    * `SurfaceExecution.emetteur(total)` est le seul appel qui **remet a zero**
      l'avancement et l'estimateur (le journal, lui, ne l'est plus depuis
      `EPIC11-ARB-93`). Le sauter ferait afficher au lot suivant les jalons du
      precedent, donc un compte qui recule ;
    * le coeur attend un **appelable a deux arguments** `(faites, total)` : il
      le remet dans un `EmetteurProgression` a lui. Or l'objet rendu par
      `emetteur()` n'est **pas** appelable -- `EmetteurProgression` n'expose
      que `emettre(faites)` --, donc le passer tel quel eteindrait le canal EN
      SILENCE : `callable(...)` y rend faux et l'emetteur du coeur se declare
      inactif sans rien lever. C'est `AR3` mot pour mot : « un rappel qui
      s'eteint en silence quand on lui passe le mauvais type n'est pas
      optionnel, il est casse ».

    **Le `total` est connu d'avance ici, et c'est la difference avec le temps
    1** (AC 5.3) : la detection ne connait son cardinal qu'apres l'ingestion,
    l'ecriture le lit du document avant de commencer.
    """
    emetteur = surface.emetteur(total)
    return lambda faites, _total: emetteur.emettre(faites)


def journal_du_produit() -> tuple[logging.Logger, RelaisDeJournal]:
    """Le logger passe au coeur, et son relais vers le journal de `E3-7`.

    Meme geste que les deux autres passes, **et le relais est le leur** : la
    classe est generique -- elle ne connait ni rush ni lot --, et deux
    redactions du meme handler divergeraient. Seul le **nom** du journal
    change, et c'est ce qui empeche les lignes d'une detection d'atterrir dans
    le journal de l'ecriture.

    `propagate` est coupe : sous une TUI, tout handler herite du racine ecrit
    sur `stdout` **par-dessus** l'interface, qui est un plein ecran.
    """
    logger = logging.getLogger(NOM_DU_JOURNAL)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    relais = RelaisDeJournal()
    # Le logger est un singleton par nom : deux ecritures successives dans la
    # meme session reutiliseraient le meme objet, et les relais s'empileraient
    # -- chaque ligne du coeur serait inscrite autant de fois qu'il y a eu de
    # passes.
    for ancien in list(logger.handlers):
        if isinstance(ancien, RelaisDeJournal):
            logger.removeHandler(ancien)
    logger.addHandler(relais)
    return logger, relais


# ---------------------------------------------------------------------------
# `T6-1` -- interrompre une ecriture dit ce qu'on laisse
# ---------------------------------------------------------------------------

#: La cle de l'issue qui laisse en place ce qui est deja ecrit.
CLE_GARDER = "garder"

#: La cle de l'issue **destructrice**. Elle porte `ecrit=True`, donc le curseur
#: ne peut pas s'y poser au montage -- invariant leve par `ChoixExclusif`,
#: jamais reecrit ici.
#:
#: **Ce que cette issue fait aujourd'hui, dit plutot que tu** : elle demande
#: l'interruption, comme sa voisine, et **n'efface rien**. C'est le regime deja
#: livre par l'atelier Extraction, dont `_interrompre` traite ses deux issues a
#: l'identique ; la suppression propre d'un element de projet est la troisieme
#: operation d'`EPIC11-ARB-89` et vit dans la story 11.11. Le rapport nomme
#: l'issue retenue pour que le branchement futur porte sur un fait mesure.
CLE_EFFACER = "effacer"

#: Ce que les trois issues disent, avec leur compte reel (ecart `H14` de la
#: fiche : « la maquette est **meilleure que le code** »). Verbatim de
#: `T6-1-interruption.txt`, l. 15-17.
PHRASE_GARDER = "Interrompre et garder {compte}"
PHRASE_EFFACER = "Interrompre et effacer {compte}"
PHRASE_REPRENDRE = "Reprendre l'écriture"


def compte_de_frames(frames: int) -> str:
    """`les 40 frames`, `la frame déjà écrite`, ou ce qui reste dicible a zero.

    **A zero, il n'y a pas de compte a donner**, et « les 0 frames » serait du
    charabia : la phrase retombe alors sur celle qu'`EcranInterruption` porte
    deja -- « ce qui est deja ecrit ». Ce n'est pas une exception a l'AC 6.4,
    c'est sa seule lecture possible : l'AC demande le compte **reel**, et le
    compte reel de zero frame n'est pas un nombre a afficher.
    """
    if frames <= 0:
        return "ce qui est déjà écrit"
    if frames == 1:
        return "la frame déjà écrite"
    return f"les {frames} frames"


def issues_de_l_interruption(frames: int) -> tuple[Issue, ...]:
    """Les **trois** issues de `T6-1`, chiffrees (AC 6.2, AC 6.4).

    Contrairement au temps 1, qui n'en gardait que deux parce qu'une detection
    n'ecrit rien, `T6-1` est le cas **nominal** pour lequel les trois ont ete
    ecrites : une ecriture, elle, laisse quelque chose sur le disque.

    L'ordre est celui d'`EcranInterruption.ISSUES`, et il n'est pas neutre :
    garder est le cas le plus frequent, effacer le plus destructeur, reprendre
    le retour en arriere. Les cles aussi sont les siennes -- `REPRENDRE` est
    **lue** de la classe mere, parce que c'est elle qui la compare dans
    `traiter` et dans `issue_d_interruption` : une chaine ecrite deux fois
    divergerait.
    """
    compte = compte_de_frames(frames)
    return (
        Issue(CLE_GARDER, PHRASE_GARDER.format(compte=compte)),
        Issue(CLE_EFFACER, PHRASE_EFFACER.format(compte=compte), ecrit=True),
        Issue(EcranInterruption.REPRENDRE, PHRASE_REPRENDRE),
    )


class EcranInterruptionDeLEcriture(EcranInterruption):
    """`T6-1` -- trois issues, **chiffrees**, et `execution.py` intact.

    **On reutilise `EcranInterruption`** -- son clavier, son rendu, son `Echap`
    qui reprend au lieu de remonter, ses invariants de choix. Ce qui est
    substitue est exactement ce que l'ecriture ajoute, et rien de plus : le
    **compte reel** dans les libelles, et le titre de l'atelier au bandeau.
    C'est le patron livre par `atelier_scan_detection.EcranInterruptionDeDetection`
    (AC 6.3).

    **`ISSUES` est une propriete et non un attribut de classe**, et c'est ce
    que le chiffrage impose : le libelle depend d'un compte connu a la
    construction. La propriete est lue par `EcranInterruption.__init__` --
    `ChoixExclusif(list(self.ISSUES))` -- avant l'init de la classe mere, d'ou
    l'affectation de `frames` en premiere ligne.
    """

    titre = PALIER_DE_L_ATELIER

    def __init__(self, panneau: Panneau, frames: int,
                 sur_issue: Callable[[Issue], None] | None = None) -> None:
        #: Le compte du **disque** au moment ou l'ecran s'ouvre (AC 6.6).
        #: Pose AVANT `super().__init__`, qui lit `ISSUES`.
        self.frames = int(frames)
        super().__init__(panneau, sur_issue=sur_issue)

    @property
    def ISSUES(self) -> tuple[Issue, ...]:   # noqa: N802 -- nom de la mere
        return issues_de_l_interruption(self.frames)


# ---------------------------------------------------------------------------
# `E3-7` -- l'ecriture en cours
# ---------------------------------------------------------------------------

class EcranEcritureDuScan(EcranExecution):
    """`E3-7` -- la barre en frames, le journal du coeur, et le disque compte.

    Trois substitutions, chacune parce que l'ecriture du scan contredit la
    valeur heritee :

    * ``titre`` -- le bandeau nomme l'**atelier** (`mmu · projet_demo · Scan`),
      pas la classe d'ecran ;
    * :meth:`ouvrir_l_interruption` -- `T6-1` et ses trois issues chiffrees ;
    * :meth:`panneau_de_ce_qui_est_ecrit` -- le cartouche herite compte des
      unites depuis les **jalons** ; ici il compte les frames **sur le
      disque**, et il dit en plus ce qui reste valide.
    """

    titre = PALIER_DE_L_ATELIER

    def __init__(self, surface: SurfaceExecution, titre_tache: str = "",
                 sur_issue: Callable[[Issue], None] | None = None,
                 objet: str = "", *,
                 compter_le_disque: Callable[[], int],
                 frames_du_plan: int = 0) -> None:
        """`compter_le_disque` est **requis**, et ce n'est pas un oubli.

        Un `Callable | None = None` assorti d'un `if ... is not None`
        transformerait l'oubli du cablage en **silence** -- l'ecran annoncerait
        alors zero frame ecrite pendant qu'il y en a quarante sur le disque,
        c'est-a-dire exactement le mensonge que l'AC 6.6 existe pour empecher.
        Le rendre requis fait de l'oubli une erreur d'appel.
        """
        super().__init__(surface, titre_tache=titre_tache,
                         sur_issue=sur_issue, objet=objet)
        self._compter_le_disque = compter_le_disque
        #: Le total du plan -- ce que le document promet, tous lots confondus.
        self.frames_du_plan = int(frames_du_plan)
        #: La cle de l'issue d'interruption retenue, ou `None`. Voir
        #: :meth:`issue_d_interruption`.
        self.issue_retenue: str | None = None

    def frames_ecrites(self) -> int:
        """Le compte du **disque**, jamais celui du dernier jalon (AC 6.6)."""
        return int(self._compter_le_disque())

    def panneau_de_ce_qui_est_ecrit(self, ecrites: int | None = None) -> Panneau:
        """Ce qui est sur le disque, ce qui reste, et ce qui reste **valide**.

        Le nom de la methode est celui de la classe mere -- c'est son point
        d'appel, il ne se renomme pas depuis une sous-classe. L'argument
        optionnel n'ouvre aucun regime : il evite un **second** balayage du
        disque quand :meth:`ouvrir_l_interruption` a deja compte, et deux
        comptages a une seconde d'intervalle pendant une ecriture ne rendent
        pas le meme nombre -- le cartouche et les issues afficheraient alors
        deux chiffres differents du meme fait.

        La troisieme ligne est un **fait** et non un conseil : le document de
        detection reste valide, donc reprendre plus tard ne redemande pas de
        detecter (`EPIC11-ARB-6`, AC 6.4).
        """
        ecrites = self.frames_ecrites() if ecrites is None else ecrites
        return Panneau(
            TITRE_DE_CE_QUI_EST_ECRIT,
            [LigneChiffree("Frames écrites", ecrites, UNITE),
             LigneChiffree("Frames restantes",
                           max(self.frames_du_plan - ecrites, 0), UNITE),
             LigneChiffree(LIBELLE_DOCUMENT, PHRASE_DOCUMENT_VALIDE)],
        )

    def ouvrir_l_interruption(self) -> EcranInterruptionDeLEcriture:
        """Monte `T6-1` **par-dessus** l'execution. La tache continue derriere.

        AC 6.1 : ouvrir cet ecran n'arrete rien. C'est un empilement, pas une
        substitution -- l'ecran d'execution reste dans la pile, et l'emetteur
        du coeur continue de noter ses jalons dans la meme surface.

        Le disque est compte **une seule fois**, et le meme nombre part au
        cartouche et aux issues : deux comptages donneraient deux chiffres du
        meme fait sur un seul ecran.
        """
        ecrites = self.frames_ecrites()
        ecran = EcranInterruptionDeLEcriture(
            self.panneau_de_ce_qui_est_ecrit(ecrites), ecrites,
            sur_issue=self.issue_d_interruption)
        self.app.descendre(ecran)
        return ecran

    def issue_d_interruption(self, issue: Issue) -> None:
        """Retenir **quelle** issue a interrompu, puis faire ce que la mere fait.

        « Reprendre » n'est pas une interruption : c'est de la navigation, et la
        classe mere la traite seule. Les deux autres sont retenues **nommement**
        -- garder et effacer ne demandent pas la meme suite, et le jour ou
        l'effacement existera (`EPIC11-ARB-89`, story 11.11) il se branchera sur
        ce fait plutot que sur une intention perdue au moment du clic.
        """
        if issue.cle != EcranInterruption.REPRENDRE:
            self.issue_retenue = issue.cle
        super().issue_d_interruption(issue)


# ---------------------------------------------------------------------------
# La passe : monter l'ecran, appeler le coeur, conclure
# ---------------------------------------------------------------------------

def ouvrir_l_ecriture(app, plan: PlanDEcriture, *,
                      objet: str = OBJET_DU_BANDEAU) -> EcranEcritureDuScan:
    """Monter `E3-7` **avant** d'appeler le coeur.

    L'ordre n'est pas cosmetique : `EcranExecution.on_mount` est ce qui abonne
    l'ecran aux jalons de la surface. Appeler le coeur d'abord ferait ecrire les
    jalons dans une surface que personne n'ecoute encore, et la barre resterait
    figee du debut a la fin de l'ecriture.
    """
    surface = SurfaceExecution(unite=UNITE)
    ecran = EcranEcritureDuScan(
        surface, titre_tache=titre_de_la_tache(plan),
        sur_issue=lambda issue: _interrompre(app, issue), objet=objet,
        compter_le_disque=lambda: frames_sur_le_disque(plan),
        frames_du_plan=plan.frames)
    app.descendre(ecran)
    return ecran


def _interrompre(app, issue: Issue) -> None:
    """Les deux issues qui arretent la passe. « Reprendre » ne vient jamais ici.

    L'interruption est **demandee** ; elle est constatee **entre deux lots** par
    :func:`ecrire_les_lots`. Voir son docstring : le coeur n'offre aucun point
    d'arret a l'interieur d'un lot.

    **Elle n'efface rien**, y compris sur l'issue qui l'annonce -- voir
    :data:`CLE_EFFACER`. L'ecran, lui, a retenu laquelle des deux a ete
    validee, et :func:`executer_et_conclure` la porte au rapport.
    """
    app.interruption_demandee = True


def ecrire_les_lots(plan: PlanDEcriture, surface: SurfaceExecution, *,
                    logger, hote: Callable[..., Any] | None = None,
                    interrompu: Callable[[], bool] | None = None,
                    ecrire: Callable[..., Any] = (
                        scan_write.ecrire_depuis_le_document)
                    ) -> RapportDEcriture:
    """Ecrire les lots du plan, un appel de `ecrire_depuis_le_document` par lot.

    `hote` est `CoqueTui.executer_en_processus` : le coeur est **heberge**, pas
    relance (`EPIC11-ARB-1`, AC 5.1). Il vaut l'appel direct par defaut, pour
    que la passe se mesure sans monter d'application.

    **Un lot refuse n'annule pas les suivants** (AC 5.7), et c'est la propriete
    de cette boucle qu'un `continue` devenu `break` detruirait *sans un mot* :
    sur trois lots dont le deuxieme est refuse, un `break` ferait disparaitre
    le troisieme, et le rapport ne porterait ni son ecriture ni son refus. Le
    mutant est celui de la 11.4b, paye trois fois. Le refus est **collecte**,
    nomme, et l'ecriture continue -- ce qui est aussi la seule lecture juste du
    metier : deux lots d'un meme vrac sont deux documents independants, et le
    document perime de l'un ne dit rien de l'autre.

    `interrompu` est consulte **entre deux lots**. La granularite est celle-la
    et pas une autre : a l'interieur d'un lot, l'appel au coeur est synchrone et
    n'offre aucun point d'arret -- le canal de progression est observationnel
    par contrat (`EPIC7-ARB-79`), il ne peut rien arreter. Le dire est plus
    honnete que de faire croire a un arret immediat.

    Les erreurs hors table **traversent** : voir :func:`refus_de`.
    """
    hote = hote or (lambda fonction, *args, **kwargs: fonction(*args, **kwargs))
    ecrits: list[LotEcrit] = []
    refuses: list[RefusDEcriture] = []
    manifeste = Path(plan.dossier_projet) / MANIFEST_FILENAME
    # **La passe se declare AVANT son premier lot** (11.4e, AC 8.1), et c'est
    # ce qui leve l'ecart que `titre_de_la_tache` assumait ici : « le rang du
    # lot en cours n'est PAS dans ce titre [...] le mettre a jour a chaque lot
    # demanderait de toucher `execution.py`, que l'AC 6.3 interdit ». L'AC 10.3
    # de la 11.4e a leve cette interdiction, et `E3-7` porte desormais son rang
    # et sa liste des lots comme sa maquette les montre.
    if plan.lots:
        surface.declarer_la_passe(
            LIBELLE_DE_LA_PASSE,
            [(lot.lot_id, lot.frames) for lot in plan.lots])

    for rang, lot in enumerate(plan.lots):
        if interrompu is not None and interrompu():
            return RapportDEcriture(tuple(ecrits), tuple(refuses),
                                    interrompu=True, manifeste=manifeste)
        # **La ligne qui NOMME le lot**, et c'est elle qui rend `EPIC11-ARB-93`
        # tenable : le journal n'est plus remis a zero entre deux lots, donc les
        # jalons du precedent restent visibles ; sans en-tete, `124/124` puis
        # `1/62` se lirait comme un compte qui recule.
        surface.journal.inscrire(
            en_tete_de_lot(rang, len(plan.lots), lot.lot_id))
        rappel = canal_de_progression(surface, lot.frames)
        try:
            ecriture = hote(
                ecrire,
                plan.dossier_projet,
                lot.document,
                overwrite=lot.overwrite,
                logger=logger,
                appliquer_la_correction=lot.appliquer_la_correction,
                livrer_brut=lot.livrer_brut,
                divergence_bypass=lot.divergence_bypass,
                profil_designe=lot.profil_designe,
                origine_du_profil=lot.origine_du_profil,
                nouvelle_version=lot.nouvelle_version,
                manifest_du_projet=plan.manifest_du_projet,
                rappel_progression=rappel,
            )
        except BaseException as exception:  # noqa: BLE001 -- voir refus_de
            refus = refus_de(exception)
            if refus is None:
                # Hors table : on **relaie**. Deguiser une panne inconnue en
                # refus metier ferait lire un motif rassurant sur un bug.
                raise
            refuses.append(dataclasses.replace(refus, lot_id=lot.lot_id))
            # **LE `continue` de l'AC 5.7.** Il ne se remplace pas par un
            # `break` : les lots suivants sont des documents independants.
            continue
        ecrits.append(_lot_ecrit(lot, ecriture))
    return RapportDEcriture(tuple(ecrits), tuple(refuses),
                            manifeste=manifeste)


def _lot_ecrit(lot: LotAEcrire, ecriture) -> LotEcrit:
    """Projeter un :class:`~mixed_media_utility.scan_write.EcritureDuLot`.

    Les champs sont **lus** du rapport du coeur et jamais rederives : le
    cardinal des frames est celui que la passe a ecrit
    (`output.written_frame_count`), pas celui que le plan promettait -- « le
    compte reel, jamais le compte attendu ».
    """
    sortie = getattr(ecriture, "output", None)
    dossier = lot.dossier
    relatif = getattr(sortie, "output_dir", None)
    if relatif:
        dossier = Path(relatif)
    return LotEcrit(
        lot_id=getattr(sortie, "lot_id", None) or lot.lot_id,
        frames=int(getattr(sortie, "written_frame_count", 0) or 0),
        dossier=dossier,
        correction_appliquee=bool(
            getattr(ecriture, "correction_appliquee", False)),
        profil_de_chaine_utilise=bool(
            getattr(ecriture, "profil_de_chaine_utilise", False)),
        ecriture=ecriture,
    )


def executer_et_conclure(app, ecran: EcranEcritureDuScan, plan: PlanDEcriture,
                         *, logger,
                         sur_rapport: Callable[[RapportDEcriture], None],
                         ecrire: Callable[..., Any] = (
                             scan_write.ecrire_depuis_le_document)
                         ) -> RapportDEcriture:
    """Lancer l'ecriture, puis conclure -- un seul chemin pour les trois issues.

    C'est ce qui garantit qu'`oublier_la_tache` est appele dans tous les cas :
    un drapeau `tache_en_cours` reste a vrai ferait de `Echap` une interruption
    bien apres la fin de la passe.

    Trois conclusions, et chacune a sa destination :

    * **rien d'ecrit et un refus** -- `EcranRefus`, avec le code et la phrase du
      coeur, et rien d'ajoute (`DESIGN.md` §9, AC 5.5). Ce qu'il declare non
      ecrit est **mesure sur le disque**, jamais promis ;
    * **rien d'ecrit et une interruption** -- retour au menu des ateliers du
      projet ouvert (`EPIC11-ARB-13`) ;
    * **au moins un lot ecrit** -- le rapport part a `sur_rapport`, que le lot
      du resultat (`E3-8`) fournit. Y compris quand un autre lot a ete refuse
      ou que la passe a ete interrompue : ce qui est ecrit se montre, et le
      resultat porte les deux.

    **`sur_rapport` n'a AUCUN defaut, et c'est structurel** : un
    `Callable | None = None` assorti d'un `if ... is not None` transforme
    l'oubli du cablage en **silence** -- c'est le finding `K3`, ou les quatre
    suites d'un ecran de resultat etaient navigables et decoratives. Le rendre
    requis fait de l'oubli une erreur d'appel. Meme geste pour `ecrire`, dont le
    defaut est le **vrai** point d'entree du coeur : c'est le double de banc qui
    est l'exception, pas le defaut.

    **Elle n'est plus le chemin de PRODUCTION depuis le 2026-09-06** : le
    parcours passe par :func:`lancer_l_ecriture`, qui met le coeur au fil. Elle
    reste, synchrone, parce qu'elle est le seul moyen d'obtenir le rapport
    tout de suite -- ce dont un banc a besoin et pas un operateur. Les trois
    issues, elles, ne sont plus redigees ici : elles vivent dans
    :func:`conclure_l_ecriture`, appelee par les deux chemins, pour qu'aucune
    des deux formes ne puisse deriver de l'autre.
    """
    rapport = ecrire_les_lots(
        plan, ecran.surface, logger=logger,
        hote=app.executer_en_processus,
        interrompu=lambda: bool(app.interruption_demandee),
        ecrire=ecrire)
    return conclure_l_ecriture(app, ecran, plan, rapport,
                               sur_rapport=sur_rapport)


def conclure_l_ecriture(app, ecran: EcranEcritureDuScan, plan: PlanDEcriture,
                        rapport: RapportDEcriture, *,
                        sur_rapport: Callable[[RapportDEcriture], None]
                        ) -> RapportDEcriture:
    """Les trois issues de la passe, **sur la boucle et nulle part ailleurs**.

    Extraite de :func:`executer_et_conclure` le 2026-09-06 pour que
    :func:`lancer_l_ecriture` puisse l'appeler par `call_from_thread` : chacune
    des trois branches touche l'arbre de widgets -- deux empilent un ecran, la
    troisieme rend la main au lot du resultat qui en empile un aussi --, et
    rien de tout cela ne se fait depuis un fil de travail.

    Le decoupage est **le meme** que celui de l'atelier Extraction
    (`atelier_extraction_ecriture.conclure_l_extraction`), et pour le meme
    motif : le coeur d'un cote, la boucle de l'autre.

    **Un seul passage par la boucle**, et c'est pourquoi `oublier_la_tache`
    vit ici plutot que dans le fil : entre une extinction faite a part et le
    montage de l'ecran, la boucle rendrait a l'operateur une interface sans
    tache declaree et sans ecran de conclusion -- fenetre pendant laquelle
    `Echap` depile la passe.

    Le rapport rendu porte l'issue d'interruption retenue par l'ecran ; la lire
    ici, apres la passe, est ce qui la rend juste -- `ecran.issue_retenue` ne
    vaut quelque chose qu'une fois l'operateur passe par `T6-1`.
    """
    rapport = dataclasses.replace(
        rapport, issue_d_interruption=ecran.issue_retenue)
    app.oublier_la_tache()
    if not rapport.ecrits and rapport.refus:
        premier = rapport.refus[0]
        # **Mesure et non promesse** : « aucune frame » n'est dit que si le
        # disque le confirme. Les refus du document precedent toute ecriture,
        # mais une panne d'ecriture attrapee par la meme table peut, elle,
        # laisser des frames derriere -- l'annoncer a zero serait un mensonge.
        non_ecrit = ([NON_ECRIT_PAR_UN_REFUS]
                     if frames_sur_le_disque(plan) == 0 else [])
        app.descendre(EcranRefus(premier.code, premier.message,
                                 conserve=[CONSERVE_PAR_UN_REFUS],
                                 non_ecrit=non_ecrit))
    elif not rapport.ecrits and rapport.interrompu:
        app.revenir_aux_ateliers()
    else:
        sur_rapport(rapport)
    return rapport


#: Le nom de l'ouvrier `textual` de la passe d'ecriture du Scan. Nomme plutot
#: qu'anonyme, comme `OUVRIER_DE_L_EXTRACTION` et `OUVRIER_DE_L_ENCODAGE` : un
#: banc verifie que **cette** course est partie sans avoir a deviner laquelle,
#: et la liste des `workers` de l'application reste lisible quand deux ateliers
#: ont tourne dans la meme session.
OUVRIER_DE_L_ECRITURE = "scan-ecrire"


def lancer_l_ecriture(app, ecran: EcranEcritureDuScan, plan: PlanDEcriture, *,
                      logger,
                      sur_rapport: Callable[[RapportDEcriture], None],
                      ecrire: Callable[..., Any] = (
                          scan_write.ecrire_depuis_le_document)) -> None:
    """La passe **dans un fil de travail**, pour que `E3-7` vive pendant.

    **Le troisieme et dernier lanceur gele du depot, ferme le 2026-09-06.**
    Les deux autres -- l'extraction et l'encodage -- sont partis au fil le meme
    jour, apres qu'Egan a constate le defaut sur le terrain : « la barre de
    progression saute de 0 a 100 », « le glyphe d'attente est immobile ». Le
    chemin d'ecriture du Scan portait exactement la meme forme --
    `_lancer_apres_le_dessin` **seul** devant :func:`executer_et_conclure` --,
    et il etait la derniere ligne du registre d'exceptions de
    `tests/unit/tui/test_frontiere_du_dessin_avant_le_coeur.py`.

    **Pourquoi le rendez-vous de dessin ne suffisait pas.**
    `call_after_refresh` DIFFERE d'une image, il ne QUITTE pas la boucle :
    `E3-7` apparaissait une fois, puis l'appel synchrone au coeur gardait la
    boucle jusqu'a la derniere frame. Sur un lot de plusieurs milliers de
    frames, l'operateur lit `0 %  0/6300` fige -- indiscernable d'un coeur en
    panne, et c'est la forme la plus couteuse du defaut.

    **Les deux gestes, et il en faut DEUX.** Le fil garde la boucle vivante
    pendant la passe ; le rendez-vous le fait partir **apres** le montage. Le
    second n'est pas cosmetique : `EcranEcritureDuScan` est un
    `EcranExecution`, dont l'`on_mount` abonne l'ecran aux jalons de la surface
    **et RALLUME** `tache_en_cours`. `Mount` etant distribue par la boucle, un
    fil parti dans la foulee de `descendre` peut eteindre le drapeau **avant**
    ce montage, qui le rallume ensuite : ordre mesure a la sonde par la session
    voisine, drapeau final a vrai, atelier mort pour la session sur une panne
    (`rapport-2026-09-06-a-l-agent-epic-11-gel-des-ecrans-de-progression.md`,
    section 10).

    **Le drapeau se pose ICI, avant le fil, et pas dans le fil.** Entre le
    `run_worker` et la premiere ligne du fil, la boucle tourne : un `Echap` qui
    y tomberait depilerait `E3-7` sous la passe.

    Ne rend **rien** : le rapport n'existe pas encore quand cette fonction rend
    la main. Il arrive par `sur_rapport`, appele sur la boucle depuis
    :func:`conclure_l_ecriture`. :func:`executer_et_conclure` reste, synchrone,
    pour les appelants qui veulent le rapport tout de suite -- les bancs, au
    premier chef.
    """
    app.tache_en_cours = True

    def passe() -> None:
        try:
            rapport = ecrire_les_lots(
                plan, ecran.surface, logger=logger,
                hote=app.executer_en_processus,
                interrompu=lambda: bool(app.interruption_demandee),
                ecrire=ecrire)
        except BaseException:
            # Le coeur a leve : le drapeau tombe **ici**, puisque
            # `conclure_l_ecriture` ne sera pas atteinte. C'est la moitie du
            # `finally` d'origine qui reste necessaire, et l'exception
            # continue son chemin -- elle n'est pas avalee.
            app.call_from_thread(app.oublier_la_tache)
            raise
        app.call_from_thread(conclure_l_ecriture, app, ecran, plan, rapport,
                             sur_rapport=sur_rapport)

    _lancer_apres_le_dessin(app, lambda: app.run_worker(
        passe, thread=True, name=OUVRIER_DE_L_ECRITURE,
        description="ecrire les frames d'un scan"))

