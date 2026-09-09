# -*- coding: utf-8 -*-
"""Le PARCOURS de l'atelier Exports : ce qui relie les six modules d'ecran.

Story 11.8, **lot B5**, le cablage. Les six modules `atelier_exports_*` ont ete
ecrits par cinq lots differents (C, D, E, F, G), et **aucun n'etait relie a un
autre** : chacun descendait sur un `EcranPasEncore` qui NOMMAIT ce qui manque
plutot que de se taire. Ce module est l'endroit unique ou ces raccords
s'injectent, et il retire les quatre `CE_QUI_MANQUE_...` avec eux.

L'ordre du parcours, et ce qui l'impose
----------------------------------------

``E4-1`` -> ``E4-2`` -> (``E4-3b`` **si** un master existe) -> ``E4-3``
-> ``E4-4`` -> ``E4-5``

* `EPIC11-ARB-28`, verbatim : « **Extraction et Exports n'en ont pas** » (de
  menu d'atelier). Cet atelier ouvre donc **directement** sur `E4-1`, et une
  frontiere negative de l'AC 5.1 le mesure ;
* `EPIC11-ARB-172`, applique ici comme a l'atelier Pdf : le conflit de version
  se tranche **AVANT** la confirmation. Le rang entre dans le nom du fichier
  que `E4-3` affiche ; quand la confirmation s'affiche, ce nom doit etre un
  **fait** ;
* `EPIC11-ARB-89` : `E4-3b` offre **trois** issues -- creer la version
  suivante, remplacer sciemment apres avertissement, annuler -- et jamais un
  blocage sec. Le curseur part sur `Annuler` (`EPIC11-ARB-7`, « Ok sur
  annuler »), invariant leve par `panneau.ChoixExclusif` et non repose ici.

Ce que ce module ne fait pas, et c'est structurel
--------------------------------------------------

* il **n'importe jamais `cli`** (AC 2.3, frontiere AST du lot B4) : le point
  d'entree de coeur est `encode_master.encoder_le_master_du_lot` ;
* il **ne juge aucune valeur du coeur** (AC 11.2). Profils, resolutions, codes
  de refus, conteneurs, categories et etats de lot **traversent** : ce module
  les transporte, il n'en compare aucun a un litteral. Les deux seules
  comparaisons a un mot du coeur passent par une **constante nommee**
  (`encode.ENCODE_MASTER_ALREADY_PRESENT`), jamais par une chaine ecrite ici ;
* il **ne calcule aucun rang**. Le rang propose vient de
  `encode.resolve_master_version_rank`, et le rang du master present est **lu
  de l'inventaire du manifeste** (`io.encode_manifest`). `EPIC11-ARB-92`,
  verbatim d'Egan : « il ne faut pas rendre le rang » ;
* il **ne pose jamais le mot-cle de progression en dur**. Il passe par
  :func:`~mixed_media_utility.tui.atelier_exports_execution.raccord_de_progression`,
  qui compose ce mot-cle **depuis la signature** du point d'entree appele : il
  rend `{}` aujourd'hui et le mot-cle le jour ou la story 6.7 le posera, sans
  qu'une ligne de `tui/` change (`EPIC11-ARB-184`).

Ce que ce module TRANSMET au coeur, et l'ensemble est EXACT
------------------------------------------------------------

`encode_master.MOTS_CLES_DE_LA_DECISION` gele l'ensemble des mots-cles de
decision, et l'AC 2.4 en fait une frontiere qui mord **des deux cotes** : un
mot-cle qui apparait et un mot-cle qui disparait la font rougir. Ce parcours
les passe **tous les huit**, et rien de plus que `logger` -- qui n'est pas une
decision.

**`logger` n'est pas facultatif ici, et ce n'est pas le finding `I0`.**
`encode_master` retombe sur `logging.getLogger(__name__)` quand on ne lui en
donne pas, et ce journal-la **propage vers la racine** : sous `textual`, un
handler herite du racine ecrit sur `stdout` **par-dessus** l'ecran dessine.
`journal_du_produit()` coupe cette propagation, et c'est la seule raison pour
laquelle ce parcours passe un journal.

Deux ecarts SIGNALES et non tranches, parce qu'ils appartiennent a Egan
------------------------------------------------------------------------

1. **`accept_incomplete` part a `False`, toujours.** Aucun arbitrage ne dit
   qu'un `⏎` sur `Encoder` vaut le consentement que
   `--accept-incomplete-lot` demande a la ligne de commande, et le poser ici
   l'inventerait. Consequence mesuree : un lot troue ne descend **jamais** sur
   `E4-3`, il descend sur le refus du coeur (`LOT_INCOMPLET`), dont la phrase
   voyage verbatim. `atelier_exports_confirmation.ETAT_INCOMPLET` est donc,
   aujourd'hui, une surface que le produit n'atteint pas -- c'est dit plutot
   que comble ;
2. **`E4-2` ne transmet `cadence_source_override` que sur divergence reelle**
   (`ReglagesDeL_encodage.cadence_source_transmise`, lot D), parce que
   `encode.resolve_source_rate` emet sa note d'ecrasement meme quand la valeur
   fournie EGALE celle du lot -- et cette note nomme `--cadence-source`, une
   option de ligne de commande qui n'a aucun sens dans une TUI. Ce parcours
   **prend la valeur que l'ecran a deja tranchee** ; il ne rouvre pas la
   question.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping

from .. import encode, encode_master
from ..io import encode_manifest
from . import projet_lecture
from .atelier_exports_confirmation import (
    ISSUE_ANNULER,
    ISSUE_ENCODER,
    ISSUE_MODIFIER,
    EcranExportsConfirmation,
    plan_du_master,
)
from .atelier_exports_execution import (
    ATTRIBUT_DE_L_ECRAN_DE_LA_PASSE,
    CLE_INTERROMPRE,
    EcranEncodageEnCours,
    EcranInterruptionDeLEncodage,
    PassageDeLEncodage,
    raccord_de_progression,
)
from .atelier_exports_lot import (
    Balayage,
    Balayeur,
    Designation,
    EcranDesLotsAEncoder,
    ListeDesLotsAEncoder,
    LotsMalFormes,
    balayer_le_lot,
)
from .atelier_exports_reglages import (
    EcranReglagesDeL_encodage,
    LotAEncoder,
    ReglagesDeL_encodage,
)
from .atelier_exports_resultat import (
    SUITE_AUTRE_LOT,
    SUITE_DOSSIER,
    SUITE_FICHIER,
    MasterEcrit,
    ouvrir_le_dossier_du_master,
    ouvrir_le_fichier_du_master,
    ouvrir_le_resultat,
)
from .atelier_exports_versions import (
    CLE_ANNULER,
    CLE_CREER,
    CLE_REMPLACER,
    EcranMasterExistant,
    conflit_du_master,
)
from .atelier_extraction_ecriture import _lancer_apres_le_dessin, journal_du_produit
from .atelier_scan_resultat import chronometre
from .coque import EcranPasEncore
from .execution import EcranRefus
from .panneau import Issue

#: Le nom de l'ouvrier `textual` de la passe d'encodage. Nomme plutot
#: qu'anonyme, et **distinct** de celui de l'extraction : deux ouvriers
#: homonymes rendraient deux mesures interchangeables, et un banc qui cherche
#: « la course » n'en verrait qu'une.
OUVRIER_DE_L_ENCODAGE = "exports-encoder"

# ===========================================================================
# Ce que ce parcours decide de lui-meme -- et il y en a tres peu
# ===========================================================================

#: Ce que le refus d'un projet sans lot encodable dit. **Ce n'est pas un refus
#: du coeur** -- `EPIC11-ARB-30` gouverne ceux-la et la TUI n'y ajoute rien --,
#: c'est l'invariant du modele de la liste, dont la phrase est celle que
#: `atelier_exports_lot` a redigee. La recomposer ici en ferait une seconde
#: redaction du meme constat.
#:
#: Le cas est **rare mais atteignable** : l'entree `Exports` du menu des
#: ateliers est conditionnee a l'existence d'un lot encodable
#: (`projet_lecture.entrees`), mais rien n'empeche le dernier dossier de frames
#: de disparaitre entre l'affichage du menu et la frappe de `⏎`.
CODE_AUCUN_LOT = "AUCUN_LOT_A_ENCODER"

#: Ce qu'un refus hors du vocabulaire ferme affiche comme code. Il n'invente
#: rien : c'est le **nom de la classe** que le coeur a levee, la seule chose
#: qui le nomme quand il ne porte pas de code (`RefusDOuvertureDuProjet`,
#: `EncodageInterrompu`). Un code invente serait pire qu'un nom de classe.
def code_du_refus(refus: BaseException) -> str:
    """Le code du vocabulaire ferme, ou le nom de la classe levee.

    `encode.EncodeDecisionError` porte son code ; les quatre refus propres a la
    sequence (`encode_master`) n'en portent aucun -- « elles precedent le
    vocabulaire, comme elles precedent le journal ». Le message, lui, voyage
    **verbatim** dans les deux cas (`EPIC11-ARB-30`).
    """
    code = getattr(refus, "code", None)
    return code if isinstance(code, str) and code else type(refus).__name__


def phrase_du_refus(refus: BaseException) -> str:
    """La phrase du refus SANS le code, qui est rendu dans son propre champ.

    `encode.EncodeDecisionError` retient sa phrase seule (`.message`) en plus
    du `str(...)` prefixe par le code -- c'est ce que la ligne de commande
    imprime, et c'est bon la. Ici l'ecran porte deja le code dans son
    cartouche : relayer `str(refus)` le ferait lire DEUX fois.

    **Et le prefixe ne se retire pas par decoupage de chaine.** Un
    `split(": ", 1)` ecrit ici traiterait le premier deux-points de la phrase
    comme une frontiere -- il suffit d'un message qui en porte un pour couper
    au mauvais endroit --, et ce serait la TUI qui requalifierait le refus du
    coeur, ce qu'`EPIC11-ARB-30` interdit. On lit donc ce que le coeur retient,
    et `str(...)` ne sert que de repli pour les refus qui ne sont pas du
    vocabulaire ferme.
    """
    phrase = getattr(refus, "message", None)
    return phrase if isinstance(phrase, str) and phrase else str(refus)


#: Les familles de refus que ce parcours **rattrape**, table close. Elles sont
#: lues de `encode_master.CODES_DE_SORTIE` -- la table que l'enveloppe de la
#: CLI emploie deja pour rendre son code de sortie --, plus l'interruption, que
#: cette table ne porte pas parce qu'elle vaut deux codes selon son origine.
#:
#: **Lues, jamais recopiees** : une liste ecrite ici vieillirait en silence le
#: jour ou le coeur ajoute un refus, exactement comme la liste explicite de
#: `MODULES_DE_COEUR` que le lot B4 a remplacee par une decouverte.
#:
#: Ce qui n'y figure pas **traverse**, et c'est delibere : « deguiser une panne
#: inconnue en refus metier ferait lire un motif rassurant sur un bug ».
REFUS_NOMMES: tuple[type[BaseException], ...] = tuple(
    famille for famille, _code in encode_master.CODES_DE_SORTIE
) + (encode_master.EncodageInterrompu,)

#: Ce que l'ecran de refus propose de FAIRE, en clair et dans l'ordre ou
#: l'operateur les pese. Ce sont les touches que `EcranRefus` annonce deja dans
#: sa ligne de raccourcis, dites en mots : une liste de touches n'est pas une
#: liste d'issues, et `EPIC11-ARB-89` demande des issues.
SUITES_DU_REFUS = (
    "Échap : revenir en arrière, le lot et les réglages sont intacts",
    "⏎ : revenir aux ateliers",
)

#: Ce qu'on dit du fichier conserve, et **seulement quand il y en a un**.
#:
#: **La premiere redaction disait « se supprime a la main », et c'etait faux.**
#: Le coeur balaie ces residus tout seul : `encoder_le_master_du_lot` appelle
#: `encode.prepare_output_directory` a chaque passe, qui appelle
#: `codec_profiles.sweep_encode_residues` sur le dossier des masters. Le seuil
#: d'age -- 24 h par defaut -- n'est pas une negligence : « un temporaire
#: vivant appartient a un autre encodage en cours ».
#:
#: Envoyer l'operateur supprimer a la main ce que l'outil retire de lui-meme
#: est exactement le genre de corvee qu'`EPIC11-ARB-104` refuse. Ce qui reste
#: vrai, et qu'il faut donc dire : le fichier occupe de la place en attendant,
#: et rien n'interdit de l'effacer plus tot.
#:
#: **Une suite ACTIONNABLE serait mieux, et elle n'est pas posee ici** :
#: `EcranRefus` rend `suites` en texte et ne traite que `⏎` au clavier ; lui
#: donner une issue declenchable demanderait de toucher `execution.py`, que
#: huit sites de montage partagent. C'est une amelioration, pas un blocage --
#: l'operateur n'a plus rien a faire pour que le disque se nettoie.
#:
#: **Elle s'appelle PHRASE et non SUITE, et le nom est le fond du sujet**
#: (renomme le 2026-09-07, sur finding `C1-2` de la couche 1 de la revue).
#: `test_couverture_des_suites` recense toute constante de premier niveau
#: nommee `SUITE_*` et exige alors du module qu'il figure a `COUVERTURES` avec
#: un rappel, et qu'il porte au moins DEUX suites. Le premier jet l'a nommee
#: `SUITE_...` et a rendu deux bancs rouges -- non par collision de noms
#: fortuite, mais parce que la garde avait raison : elle existe pour attraper
#: « quatre suites proposees, une seule marche », et ce texte n'est justement
#: PAS une suite navigable. Le renommer est donc l'aveu exact de ce qu'il est,
#: pas un contournement de la frontiere ; l'y faire entrer aurait demande de
#: lui inventer un rappel qui ne mene nulle part.
PHRASE_DU_FICHIER_CONSERVE = (
    "Le fichier conservé est balayé tout seul par un prochain encodage, "
    "passé 24 h ; l'effacer plus tôt ne casse rien"
)


def _conserve_du_refus(refus: BaseException) -> list[str]:
    """Le chemin que le coeur a **volontairement** garde, s'il en nomme un.

    `encode.EncodeVerificationRefused` le porte en propre (`staged_path`) :
    « Sans ce chemin dans l'exception, le message d'erreur ne pourrait pas dire
    ou regarder, et le fichier resterait un residu anonyme. » La TUI le lit sur
    l'exception plutot que de le deviner d'un dossier de sortie -- deux refus
    du meme code peuvent porter deux fichiers d'attente differents.

    Les autres refus de la table close n'en portent aucun, et la liste est
    alors vide : `EcranRefus` fait disparaitre la rubrique plutot que d'afficher
    un titre sans ligne.
    """
    chemin = getattr(refus, "staged_path", None)
    return [] if chemin is None else [str(chemin)]


#: **Le consentement d'un lot troue ne se donne pas ici** -- voir la tete de
#: module, ecart 1. La valeur est nommee plutot qu'ecrite en litteral au point
#: d'appel : le jour ou Egan tranche, c'est cette ligne qui change, et une
#: seule.
CONSENTEMENT_AU_LOT_INCOMPLET = False


# ===========================================================================
# Les deux depilements -- ce qu'une suite doit faire AVANT de recommencer
# ===========================================================================

def remonter_a_l_ouverture_de_l_atelier(app) -> None:
    """Depiler jusqu'a la **page d'ouverture** de l'atelier Exports (`E4-1`).

    **Ce n'est PAS celle d'`atelier_exports_resultat`, et l'ecart est mesure.**
    Celle-la depile les **passages** et s'arrete au premier palier non
    transitoire, sur le motif qu'« Extraction et Exports n'ont pas » de menu
    d'atelier, « si bien que cet atelier-ci n'a qu'une seule station sous ses
    passages -- `E4-1` ». La mesure dit autre chose : `E4-2`
    (`EcranReglagesDeL_encodage`) est **lui aussi** `TRANSITOIRE = False`, et
    c'est voulu -- « une station du parcours : on y revient depuis la
    confirmation ». Un depilement par passages s'arrete donc sur les
    **reglages** du lot qu'on vient d'encoder, pas sur la liste des lots.

    On depile donc jusqu'a l'ECRAN vise, exactement comme
    `atelier_pdf_parcours.remonter_a_l_ouverture_de_l_atelier` le fait pour son
    menu, et pour la meme raison : l'atelier connait son propre ecran
    d'ouverture, il n'a pas a en deviner la profondeur.

    **On ne remonte pas plus haut** (`EPIC11-ARB-13`) : cette suite s'arrete un
    cran EN DESSOUS du menu des ateliers, dans l'atelier ou l'operateur
    travaille. C'est le retour, et lui seul, qui remonte au menu -- et c'est ce
    qui rend les deux issues de `E4-5` **discernables**, ce qu'elles n'etaient
    pas tant que `E4-1` n'etait pas branche.

    **Et on ne depile pas a l'aveugle** : si aucun `E4-1` n'est dans la pile,
    la fonction ne fait rien plutot que de vider la pile jusqu'a la racine. Un
    depilement qui ne sait pas ou il va est pire que pas de depilement.
    """
    if not any(isinstance(ecran, EcranDesLotsAEncoder)
               for ecran in app.screen_stack):
        return
    while (len(app.screen_stack) > 1
           and not isinstance(app.screen, EcranDesLotsAEncoder)):
        app.pop_screen()


def remonter_aux_reglages(app) -> None:
    """Depiler les **passages** jusqu'au premier palier de station.

    C'est ce que `Modifier les réglages` doit faire, et ce que `Annuler` fait
    aussi : les deux issues non ecrivantes de `E4-3` sortent du meme passage.
    L'ecran de conflit et la confirmation sont declares `TRANSITOIRE`, `E4-2`
    ne l'est pas : le depilement se lit donc de la **declaration des ecrans**
    plutot que d'un compte de paliers ecrit ici, qui serait faux au premier
    ecran insere -- et il l'a ete cote Pdf, ou l'inversion d'`EPIC11-ARB-172`
    a glisse un ecran entre les reglages et la confirmation (finding `F4`).
    """
    while app.passages_empiles and len(app.screen_stack) > 1:
        app.pop_screen()


# ===========================================================================
# Ce que le manifeste dit d'un master DEJA la
# ===========================================================================

def master_declare(manifeste: Mapping[str, Any] | None, lot_id: str,
                   chemin: Path) -> Mapping[str, Any]:
    """L'entree d'inventaire du master present, ou un document vide.

    **L'appariement se fait par CHEMIN, jamais par rang** : la cle de
    l'inventaire *est* le chemin relatif du master
    (`encode_manifest.MASTER_INVENTORY_KEY`), et « ce n'est pas `profile_id`
    [...] une cle par profil ecraserait un master present et voulu ». Prendre
    « la premiere entree du lot » designerait le mauvais master des que le lot
    en porte deux, ce qui est litteralement le mutant `M25` de la story 5.7.

    Le lot lui-meme se cherche **jusqu'au bout** de `lots[]`, pour la meme
    raison. Un document vide est un regime nominal : un master pose a la main
    sur le disque n'a aucune entree d'inventaire, et les lignes qu'il aurait
    alimentees **disparaissent** au lieu de sortir a zero.
    """
    nom = Path(chemin).name
    for lot in (manifeste or {}).get("lots") or ():
        if not isinstance(lot, Mapping) or lot.get("lot_id") != lot_id:
            continue
        for entree in lot.get(encode_manifest.MASTER_INVENTORY_FIELD) or ():
            if not isinstance(entree, Mapping):
                continue
            declare = entree.get(encode_manifest.MASTER_INVENTORY_KEY)
            if isinstance(declare, str) and Path(declare).name == nom:
                return entree
    return {}


def frames_du_balayage(balayage: Balayage | None) -> int:
    """Le cardinal de frames **compte sur le disque**, ou zero.

    Zero n'est pas une invention : c'est ce que le balayage a compte quand le
    coeur a refuse le lot (dossier disparu, cadence inexploitable) -- rien n'a
    pu etre ordonne, donc rien n'a ete trouve. Et c'est aussi la seule valeur
    disponible quand `⏎` a ete frappe avant que le lot ne soit compte, ce que
    `Designation.balayage` autorise nommement (« `⏎` n'attend pas la fin du
    balayage »).

    **Il n'entre dans aucune decision** : c'est la droite du bandeau de `E4-2`
    et rien d'autre. Ce qui decide -- le verdict de completude, le cardinal
    d'echantillons, le poids -- est resolu par `encode.plan_encode` un ecran
    plus loin, sur le disque, et non ici.
    """
    verdict = getattr(balayage, "verdict", None)
    return 0 if verdict is None else verdict.found


# ===========================================================================
# Le parcours
# ===========================================================================

class ParcoursExports:
    """Les six ecrans de l'atelier Exports, cables les uns aux autres.

    Meme forme que `ParcoursPdf` et `ParcoursScan`, et pour le meme motif :
    chaque rappel a besoin de ce que le precedent a produit -- le lot designe,
    la reconstruction visee, les reglages retenus, la decision de conflit --,
    et les methodes liees le portent sans rendre l'etat implicite.

    **Ce parcours n'ecrit qu'a un seul endroit** : :meth:`lancer`. Tout ce qui
    precede -- designation, reglages, conflit, confirmation -- lit le manifeste
    et le disque, et rien d'autre. C'est l'invariant qui tient l'AC 4.4 cote
    parcours : monter `E4-3b` trois fois et annuler trois fois ne consomme
    **aucun** rang, parce que `encode.plan_encode` et
    `encode.resolve_master_version_rank` n'ecrivent rien -- la ligne d'eau ne
    monte qu'a la declaration au manifeste, apres l'ecriture reelle.
    """

    def __init__(self, app, dossier_projet, *,
                 encoder: Callable[..., Any] | None = None,
                 planifier: Callable[..., Any] | None = None,
                 balayeur: Balayeur = balayer_le_lot,
                 horloge: Callable[[], float] | None = None) -> None:
        self.app = app
        self.dossier_projet = Path(dossier_projet)
        #: Le double de banc du point d'entree de coeur. Son defaut est le
        #: **vrai** point d'entree (`encode_master.encoder_le_master_du_lot`) :
        #: c'est le double qui est l'exception, pas le defaut.
        self._encoder = encoder
        #: Le double de banc de la **decision**. Son defaut est
        #: `encode.plan_encode`, qui sonde chaque frame par `ffprobe` : un banc
        #: qui n'a ni frames ni `ffprobe` passe le sien, et le produit paie la
        #: vraie sonde.
        self._planifier = planifier
        #: **Pas un `Callable | None`** : le defaut est le vrai balayage du
        #: disque (`balayer_le_lot`), jamais `None`. Le meme balayeur part a
        #: `E4-1` et sert au repli de :meth:`designer` -- deux balayeurs pour
        #: un seul ecran divergeraient.
        self._balayeur = balayeur
        #: L'horloge du chronometre de la passe, injectable pour qu'un banc
        #: mesure la duree **sans attendre**.
        self._horloge = horloge
        #: Le journal du produit. Voir la tete de module : il n'est pas la pour
        #: alimenter un ecran -- `E4-4` n'en porte aucun (`EPIC11-ARB-189`) --,
        #: il est la pour que le coeur n'ecrive pas sur `stdout` par-dessus
        #: l'interface.
        self._logger, self._relais = journal_du_produit()

        #: Le manifeste, **relu a chaque entree dans le parcours**. Une seule
        #: lecture alimente la liste des lots, le plan et le conflit : juger
        #: sur un document et en afficher un autre est la classe de defaut que
        #: cette relecture unique ferme.
        self.manifeste: Mapping[str, Any] | None = None
        #: Le lot designe a `E4-1`, ou `None`.
        self.designation: Designation | None = None
        #: Les reglages retenus a `E4-2`, ou `None`.
        self.reglages: ReglagesDeL_encodage | None = None
        #: Le plan que `E4-3` montre et que `E4-4` execute, ou `None`.
        self.plan: Any = None
        #: Ce que l'operateur a retenu a `E4-3b`. Les deux drapeaux sont
        #: **exclusifs** -- `plan_encode` refuse nommement la combinaison
        #: (`VERSION_ET_ECRASEMENT_COMBINES`) --, et ce sont les deux issues
        #: du meme conflit d'ecriture.
        self.nouvelle_version = False
        self.ecraser = False
        #: Le passage de `E4-4`, ou `None` avant l'encodage.
        self.passage: PassageDeLEncodage | None = None
        #: Le chronometre de la passe, monte **avant** l'appel au coeur : une
        #: duree mesuree apres coup ne compterait pas l'encodage.
        self._ecoule: Callable[[], float] | None = None
        #: Ce que la passe a ecrit, retenu **sur le parcours** et non relu de
        #: `app.screen` : les deux ouvertures de `E4-5` ne changent pas d'ecran
        #: mais `Ouvrir le dossier` pose une ligne d'etat, et rien ne garantit
        #: que l'ecran du sommet soit encore `E4-5` au moment ou une suite
        #: arrive -- un filet `EcranPasEncore` a pu se glisser au-dessus. Lire
        #: le master sur le sommet de pile serait lire l'objet d'un autre
        #: ecran, ou lever.
        self.ecrit: MasterEcrit | None = None

    # -- lecture -------------------------------------------------------------

    def charger(self) -> Mapping[str, Any] | None:
        """Relire le manifeste. **Une seule lecture par entree dans l'atelier.**"""
        self.manifeste = projet_lecture.lire_manifeste(self.dossier_projet)
        return self.manifeste

    @property
    def point_d_entree(self) -> Callable[..., Any]:
        """Ce que le parcours appellera reellement.

        C'est **lui** que le raccord de progression interroge, et non le point
        d'entree du produit : le raccord compose son mot-cle depuis la
        signature de l'appele, et interroger un autre objet que celui qu'on
        appelle rendrait la jonction d'`EPIC11-ARB-184` verte sans rien
        prouver.
        """
        return self._encoder or encode_master.encoder_le_master_du_lot

    # -- etape 1 : le menu des ateliers -> `E4-1` -----------------------------

    def ouvrir(self):
        """`E4-1`. **Aucun menu d'atelier ne s'intercale.**

        `EPIC11-ARB-28`, verbatim : « **Extraction et Exports n'en ont pas** :
        une seule entree chacun, donc le menu serait un ecran a franchir pour
        rien. »

        Un projet **sans aucun lot encodable** n'ouvre pas une liste vide : le
        modele leve -- « une liste vide n'est pas un choix, c'est un ecran sans
        objet » --, et le parcours le **dit** plutot que de tomber. La phrase
        affichee est celle du modele, jamais une seconde redaction du meme
        constat.
        """
        self.charger()
        self.nouvelle_version = self.ecraser = False
        try:
            liste = ListeDesLotsAEncoder.depuis_le_coeur(self.manifeste,
                                                         self.dossier_projet)
        except LotsMalFormes as vide:
            ecran = EcranRefus(CODE_AUCUN_LOT, str(vide))
            self.app.descendre(ecran)
            return ecran
        ecran = EcranDesLotsAEncoder(liste, self._balayeur,
                                     continuer=self.designer)
        self.app.descendre(ecran)
        return ecran

    # -- etape 2 : `E4-2` / `E4-2b`, les reglages -----------------------------

    def designer(self, designation: Designation) -> EcranReglagesDeL_encodage:
        """`⏎` sur un lot : monter les reglages, sur **ce** lot-la.

        Le document de lot voyage **entier** jusqu'au modele des reglages
        (`LotAEncoder.du_manifest`) : c'est lui que `encode.resolve_source_rate`
        lit, et le recopier en champs separes ferait de cet ecran une seconde
        redaction de ce que le coeur sait tirer d'un lot.

        Le balayage est **celui de l'ecran quand il a eu lieu**, et refait
        sinon : `⏎` n'attend pas la fin du balayage, et le cardinal de frames
        du bandeau ne doit pas dependre de la vitesse du disque. C'est le
        **meme** balayeur des deux cotes.
        """
        self.designation = designation
        self.nouvelle_version = self.ecraser = False
        balayage = designation.balayage
        if balayage is None:
            balayage = self._balayeur(
                designation.lot, self.dossier_projet, self.manifeste or {},
                designation.reconstruction_visee)
        reglages = ReglagesDeL_encodage(
            lot=LotAEncoder.du_manifest(designation.lot,
                                        frames_du_balayage(balayage)))
        ecran = EcranReglagesDeL_encodage(reglages,
                                          continuer=self.trancher_les_reglages)
        self.app.descendre(ecran)
        return ecran

    # -- etape 3 : la decision, et le conflit AVANT la confirmation ----------

    def planifier(self, *, nouvelle_version: bool = False,
                  ecraser: bool = False):
        """Le plan du coeur, **une decision et aucune ecriture**.

        Les huit mots-cles de `encode_master.MOTS_CLES_DE_LA_DECISION` sont
        ceux que `encode.plan_encode` porte : ce parcours les passe **ici** et
        au point d'entree de coeur, et l'AC 2.4 mesure que les deux ensembles
        sont le meme -- un mot-cle ajoute d'un cote seulement ferait afficher a
        `E4-3` un plan que l'encodage ne suivrait pas.

        **`plan_encode` n'ecrit rien**, et c'est ce qui tient l'AC 4.4 : le
        rang y est resolu contre le manifeste, jamais consomme. Ce parcours
        l'appelle jusqu'a **trois** fois pour un seul conflit -- une fois pour
        savoir qu'il y en a un, une fois par issue offerte -- et la ligne d'eau
        ne bouge pas d'un cran.
        """
        planifier = self._planifier or encode.plan_encode
        return planifier(
            self.dossier_projet,
            self.manifeste if isinstance(self.manifeste, Mapping) else {},
            **self.decision(nouvelle_version=nouvelle_version,
                            ecraser=ecraser))

    def decision(self, *, nouvelle_version: bool = False,
                 ecraser: bool = False) -> dict[str, Any]:
        """**L'ensemble EXACT des mots-cles de decision** (AC 2.4).

        Il est compose **une fois** et sert aux deux appels -- la decision
        affichee et l'encodage --, si bien qu'ils ne peuvent pas diverger. Un
        mot-cle de plus ou de moins n'est pas un detail d'implementation :
        `encode_master.MOTS_CLES_DE_LA_DECISION` le gele, et une frontiere le
        mesure dans les deux sens.

        Chaque valeur est **transportee**, aucune n'est jugee : le profil et la
        resolution sortent de `E4-2`, la cadence source de la seule methode qui
        tranche si elle diverge du lot, la reconstruction de `E4-1`, et les
        deux drapeaux de conflit de `E4-3b`.
        """
        return {
            "lot_id": self.designation.lot_id,
            "profile_id": self.reglages.profil,
            "resolution": self.reglages.resolution,
            "overwrite": ecraser,
            "nouvelle_version": nouvelle_version,
            "accept_incomplete": CONSENTEMENT_AU_LOT_INCOMPLET,
            "cadence_source_override": self.reglages.cadence_source_transmise(),
            "reconstruction_visee": self.designation.reconstruction_visee,
        }

    def trancher_les_reglages(self, reglages: ReglagesDeL_encodage):
        """`⏎` a `E4-2` : le conflit **d'abord**, la confirmation ensuite.

        `EPIC11-ARB-172`, applique a cet atelier : le nom du master -- rang de
        version compris -- entre dans le cartouche de `E4-3`, et il doit y etre
        un **fait**. L'inversion **coute zero ecran** : quand aucun master
        n'existe, aucun ecran de conflit ne se monte.

        **C'est le coeur qui dit qu'un master existe, jamais un `Path.exists()`
        ecrit ici** : `check_output_destination` est la seule redaction du
        depot de « la destination est-elle libre ? », et elle rend son verdict
        sous un code du vocabulaire ferme. L'ensemble des situations qui
        descendent sur `E4-3b` est donc **exactement** celui ou le coeur leve
        `ENCODE_MASTER_ALREADY_PRESENT`, et le banc le mesure dans les deux
        sens.
        """
        self.reglages = reglages
        try:
            self.plan = self.planifier()
        except encode.EncodeDecisionError as refus:
            if refus.code != encode.ENCODE_MASTER_ALREADY_PRESENT:
                return self.refuser(refus)
            return self.montrer_le_conflit()
        return self.confirmer()

    # -- etape 4 : `E4-3b`, un master qui existe deja ------------------------

    def montrer_le_conflit(self):
        """`E4-3b`. **Trois issues, et le curseur sur celle qui n'ecrit rien.**

        Les deux plans qui suivent sont ceux des deux issues ecrivantes, et ils
        sont montes **avant** l'ecran : c'est le seul moyen d'annoncer ce que
        chacune ferait sans le deviner. Celui de l'ecrasement nomme le master
        **present** -- c'est le chemin que la passe occuperait --, celui de la
        version nomme le voisin.

        Un refus sur l'un des deux (rangs epuises, destination inutilisable)
        est **relaye tel quel** plutot que d'ouvrir un ecran de conflit dont
        une issue mentirait : `EPIC11-ARB-89` interdit une issue inerte autant
        qu'une destruction silencieuse, et le refus du coeur porte, lui, ses
        deux issues.

        **Le rang propose vient de `encode.resolve_master_version_rank`, et le
        rang present de l'INVENTAIRE.** Aucun des deux n'est recalcule ici
        (AC 8.4) : le premier est la ligne d'eau plus un, le second est ce que
        la declaration du master a ecrit -- absent au rang d'origine, ce qui
        est exactement ce que `MasterEnConflit.rang = None` dit.
        """
        try:
            present = self.planifier(ecraser=True)
            rang_propose = encode.resolve_master_version_rank(
                self.manifeste if isinstance(self.manifeste, Mapping) else {},
                present.lot_id,
                profile_id=present.profile_id,
                container=present.container,
                resolution_segment=encode.resolution_name_segment(
                    present.resolution))
        except encode.EncodeDecisionError as refus:
            return self.refuser(refus)
        entree = master_declare(self.manifeste, present.lot_id,
                                present.output_path)
        conflit = conflit_du_master(
            present.output_path,
            lot_id=present.lot_id,
            profile_id=present.profile_id,
            container=present.container,
            resolution_segment=encode.resolution_name_segment(
                present.resolution),
            # Le rang du master **present**, lu de son entree d'inventaire.
            # `None` y vaut l'origine : le schema pose `minimum: 2` et
            # `to_entry` **omet** le champ au rang 1, si bien que l'absence est
            # la facon dont le manifeste dit « l'origine ».
            rang=entree.get(encode_manifest.MASTER_VERSION_RANK_FIELD),
            rang_propose=rang_propose,
            # La cible de la passe -- « la meme cle qu'ici » --, resolue par le
            # coeur. Ce n'est pas la geometrie du master present, que rien ne
            # rend, et la ligne qui la porte ne pretend pas le contraire.
            geometrie=present.resolution.size or present.source_size,
            # Les echantillons du master **present**, lus de son inventaire.
            # Rien d'autre ne les porte : ni sa cadence ni sa duree ne sont
            # declarees nulle part, donc les deux segments **disparaissent**
            # plutot que de sortir a zero.
            echantillons=entree.get("frame_count"),
        )
        ecran = EcranMasterExistant(conflit, retenir=self.retenir_le_conflit)
        self.app.descendre(ecran)
        return ecran

    def retenir_le_conflit(self, issue: Issue):
        """Les **trois** issues de `E4-3b`, et chacune mene ailleurs.

        * `Créer la vN` -- la version voisine, qui n'efface rien. Le plan est
          refait avec le drapeau, donc le nom que `E4-3` affichera porte deja
          son `_vN` ;
        * `Remplacer ce master` -- l'ecriture destructive **consciente**
          d'`EPIC11-ARB-89`. Elle passe par la confirmation comme l'autre : une
          ecriture qui sauterait le point de jugement parce qu'elle a deja
          traverse un avertissement en ferait deux, pas un ;
        * `Annuler` -- retour aux reglages, et **rien n'est ecrit**. On remonte
          au palier, pas d'un cran : le conflit et la confirmation sont deux
          passages, et `Annuler` sort du passage.

        Les deux drapeaux sont poses **exclusivement** : `plan_encode` refuse
        nommement leur combinaison, et deux issues d'un meme conflit ne se
        cumulent pas.
        """
        if issue.cle == CLE_ANNULER:
            remonter_aux_reglages(self.app)
            return None
        self.nouvelle_version = issue.cle == CLE_CREER
        self.ecraser = issue.cle == CLE_REMPLACER
        try:
            self.plan = self.planifier(nouvelle_version=self.nouvelle_version,
                                       ecraser=self.ecraser)
        except encode.EncodeDecisionError as refus:
            return self.refuser(refus)
        return self.confirmer()

    # -- etape 5 : `E4-3`, la confirmation -----------------------------------

    def confirmer(self) -> EcranExportsConfirmation:
        """`E4-3`. **Le nom du master y est un FAIT**, rang compris.

        C'est tout l'objet d'`EPIC11-ARB-172` : le conflit vient d'etre
        tranche, donc `..._v2.mov` est deja vrai au moment ou l'ecran l'ecrit,
        et il le sera encore sur le disque.

        La reconstruction est **donnee** et facultative : aucun producteur de
        coeur ne dit de quelle passe un master est issu (`EPIC11-ARB-193`), et
        `E4-1` la designe. Ce parcours transporte donc ce que l'operateur a
        designe -- rien quand le lot ne porte qu'une passe --, et la ligne
        disparait dans ce cas plutot que d'afficher un rang invente.
        """
        ecran = EcranExportsConfirmation(
            plan_du_master(self.plan,
                           reconstruction=self.nom_de_la_reconstruction()),
            sur_issue=self.trancher_la_confirmation)
        self.app.descendre(ecran)
        return ecran

    def nom_de_la_reconstruction(self) -> str | None:
        """Sous quel nom `E4-3` annonce la reconstruction encodee, ou `None`.

        C'est le **dossier** que `E4-1` a designe, tel quel : c'est ce que
        `encode.check_lot_admission` accepte et ce que le coeur a recu. `None`
        quand le lot ne porte aucun historique de passes -- la ligne disparait
        alors, ce qui est un fait et non un manque.
        """
        visee = getattr(self.designation, "reconstruction_visee", None)
        return None if visee is None else str(visee)

    def trancher_la_confirmation(self, issue: Issue):
        """Les trois issues de `E4-3`. **Une seule ecrit.**

        `Modifier les réglages` et `Annuler` ramenent aux **reglages**, et pas
        « d'un palier » : l'ecran de conflit peut s'etre glisse entre les deux
        (`EPIC11-ARB-172`), et une remontee d'un cran atterrirait alors sur un
        conflit deja tranche -- c'est-a-dire ailleurs que la ou le libelle
        l'annonce, et **seulement** quand un master existait. Un comportement
        qui depend d'un etat qu'aucune ligne de l'ecran ne dit est un piege,
        pas une variante. C'est le finding `F4` de la story 11.7, pris a la
        source.

        Les deux ne se distinguent pas l'une de l'autre, et pour la meme raison
        que cote Pdf : les deux ramenent l'operateur la ou il reglait, sans que
        rien ne soit ecrit.
        """
        if issue.cle == ISSUE_ENCODER:
            return self.encoder()
        if issue.cle in (ISSUE_MODIFIER, ISSUE_ANNULER):
            remonter_aux_reglages(self.app)
            return None
        return None

    # -- etape 6 : `E4-4` / `T6-1`, l'encodage --------------------------------

    def encoder(self) -> EcranEncodageEnCours:
        """Monter `E4-4` **avant** d'appeler le coeur, puis lancer la passe.

        L'ordre n'est pas cosmetique, et il est mesure ailleurs dans ce depot :
        a l'instruction qui suit `descendre`, `on_mount` n'a pas encore tourne
        -- le rotor n'est pas arme et l'ecran n'a rien dessine. Appeler le
        coeur dans la foulee ferait donc travailler la passe entiere devant un
        ecran vide, c'est-a-dire le grief exact qu'`EPIC11-ARB-184` ferme :
        « RIEN n'indique qu'on a lance le processus ».

        `_lancer_apres_le_dessin` est le rendez-vous que `textual` offre pour
        cela, et son repli direct existe pour les appelants qui ne montent
        aucune application.

        **Et le rendez-vous NE SUFFIT PAS -- mesure du 2026-09-06, sur le
        terrain.** Egan, verbatim : « Le glyphe d'attente (lecture des frames)
        [...] sur le terminal VS Code il est **immobile**. » Ce n'est pas une
        affaire de police : le rotor de `EcranEncodageEnCours` est un
        `set_interval`, et un minuteur `textual` ne bat que si la **boucle
        d'evenements** tourne. Le rendez-vous differe d'une image puis rend la
        boucle a :meth:`lancer`, qui la garde du premier au dernier octet de
        l'encodage -- l'ecran apparait une fois et se fige, rotor compris.

        Le fil est la seule forme qui garde la boucle vivante PENDANT la
        passe, et il part **sous** le rendez-vous : les deux proprietes sont
        distinctes et il faut les deux -- le rendez-vous pour que `on_mount`
        arme le rotor avant que le coeur parte, le fil pour qu'il batte.

        **Le chronometre part avant l'appel**, jamais apres : une duree mesuree
        apres coup ne compterait pas l'encodage.
        """
        self.passage = PassageDeLEncodage.du_plan(self.plan)
        ecran = EcranEncodageEnCours(self.passage, sur_issue=self.interrompre)
        # **Le drapeau de tache s'allume ICI, au point d'appel, et pas au
        # montage de l'ecran** -- meme geste et meme motif que
        # `atelier_pdf_execution.ouvrir_la_generation` : a l'instruction qui
        # suit `descendre`, `on_mount` n'a pas encore tourne, donc un drapeau
        # pose au montage ne protegerait rien de la fenetre qui suit.
        #
        # Sans lui, `q` sautait la porte de `CoqueTui.action_quitter` et
        # quittait la TUI **en une frappe, sans avertissement**, pendant
        # l'encodage : mesure par la couche 1 de la revue, qui a monte l'ecran
        # et constate `app.is_running` a faux. `Echap` n'etait pas touche,
        # `EcranEncodageEnCours.on_key` l'interceptant lui-meme pour `T6-1`.
        # C'est la TROISIEME occurrence de cette classe dans l'epic -- les deux
        # precedentes sont documentees a
        # `tests/unit/tui/test_atelier_pdf_execution.py:741` -- et le
        # correctif n'avait jamais ete porte a cet atelier.
        #
        # L'extincteur, lui, existait deja : le `finally` de :meth:`lancer`
        # appelle `oublier_la_tache()` quoi qu'il arrive. Un drapeau qu'on
        # eteint sans jamais l'allumer est une surface morte, et c'est
        # exactement ce que la revue a trouve.
        setattr(self.app, ATTRIBUT_DE_L_ECRAN_DE_LA_PASSE, ecran)
        self.app.tache_en_cours = True
        self.app.descendre(ecran)
        self._ecoule = (chronometre() if self._horloge is None
                        else chronometre(self._horloge))
        _lancer_apres_le_dessin(self.app, lambda: self.app.run_worker(
            self.lancer, thread=True, name=OUVRIER_DE_L_ENCODAGE,
            description="encoder le master d'un lot"))
        return ecran

    def lancer(self):
        """L'appel du coeur, **heberge et non relance** (`EPIC11-ARB-1`).

        **Elle tourne DANS LE FIL depuis le 2026-09-06**, et c'est ce qui
        change tout le reste de son corps : elle n'a plus le droit de toucher
        l'arbre de widgets. Les trois conclusions -- abandon, refus, compte
        rendu -- empilent un ecran, donc chacune repasse par la boucle par un
        **unique** `call_from_thread`, qui porte aussi l'extinction du drapeau
        de tache. Un seul appel et pas deux : entre deux passages par la
        boucle, l'ecran serait rendu a l'operateur avec `tache_en_cours` deja
        eteint et rien de monte.

        **Le mot-cle de progression n'est pas ecrit ici.**
        `raccord_de_progression` le compose depuis la signature du point
        d'entree qu'on appelle : `{}` aujourd'hui, `rappel_progression`
        le jour ou la story 6.7 le posera -- et **aucune ligne de `tui/` ne
        changera ce jour-la**, ce qui est l'AC de frontiere de cette story-la.

        **Une interruption retenue avant l'appel n'encode rien** (AC 9.6). La
        passe du coeur est synchrone : entre le dessin de `E4-4` et cette
        ligne, la boucle d'evenements tourne, et c'est la seule fenetre ou
        `T6-1` peut etre atteint. La consulter ici est donc la seule facon
        d'honorer une interruption -- et ce qu'elle laisse est exactement ce
        que `T6-1` annonce : aucun master, aucune declaration, un manifeste
        intact.

        Les refus de la table close descendent sur l'ecran de refus, avec le
        message du coeur **verbatim** (`EPIC11-ARB-30`). Ce qui est hors table
        **traverse** : deguiser une panne inconnue en refus metier ferait lire
        un motif rassurant sur un bug.
        """
        if self.app.interruption_demandee:
            # `abandonner` remonte aux ateliers, donc il DEPILE : il ne peut
            # pas tourner ici. (`revenir_aux_ateliers` eteint lui-meme le
            # drapeau, c'est pourquoi cette branche n'en porte pas.)
            self.app.call_from_thread(self.abandonner)
            return None
        try:
            master = self.app.executer_en_processus(
                self.point_d_entree,
                self.dossier_projet,
                logger=self._logger,
                **raccord_de_progression(self.passage, self.point_d_entree),
                **self.decision(nouvelle_version=self.nouvelle_version,
                                ecraser=self.ecraser),
            )
        except REFUS_NOMMES as refus:                 # noqa: BLE001 -- close
            self.app.call_from_thread(self._conclure_le_refus, refus)
            return None
        except BaseException:
            # **Quoi qu'il arrive.** Un drapeau de tache reste allume tue
            # l'atelier pour la session entiere : `Échap` cesse de depiler et
            # `q` ne quitte plus. C'est la moitie du `finally` d'origine qui
            # reste necessaire : la panne hors table traverse -- « deguiser
            # une panne inconnue en refus metier ferait lire un motif
            # rassurant sur un bug » --, donc aucune conclusion ne sera
            # atteinte et le drapeau doit tomber quand meme. L'exception
            # continue son chemin, elle n'est pas avalee.
            self.app.call_from_thread(self.app.oublier_la_tache)
            raise
        self.app.call_from_thread(self._conclure_le_master, master)
        return None

    def _conclure_le_master(self, master):
        """Oublier la tache, RETIRER `E4-4`, puis conclure. En un seul passage.

        L'ordre du drapeau est celui du `finally` d'origine -- il tombait avant
        l'appel a :meth:`conclure` -- et il est conserve tel quel : ce lot
        deplace la passe sur un fil, il ne rearbitre pas son cycle de vie.

        Le retrait de `E4-4`, lui, est neuf : voir
        :meth:`_retirer_l_ecran_de_la_passe`.
        """
        self.app.oublier_la_tache()
        self._retirer_l_ecran_de_la_passe()
        return self.conclure(master)

    def _conclure_le_refus(self, refus: BaseException):
        """Le meme geste sur le chemin de refus. Meme ordre, meme motif.

        **C'est ici que le cul-de-sac du 2026-09-06 se ferme**, et c'est le
        chemin par lequel Egan l'a rencontre : un refus de verification
        technique, `EcranRefus` empile PAR-DESSUS un `E4-4` dont la passe
        n'existe plus.
        """
        self.app.oublier_la_tache()
        self._retirer_l_ecran_de_la_passe()
        return self.refuser(refus)

    def _retirer_l_ecran_de_la_passe(self) -> None:
        """Depiler `E4-4` avant de monter le compte rendu ou le refus.

        **Le CUL-DE-SAC que ce geste ferme, mesure sur le terrain le
        2026-09-06.** Egan, verbatim : « Aucune issue sur cet ecran. Pas
        d'interruption possible [...] Oblige de quitter ». La boucle etait
        fermee, et aucune de ses cinq marches n'etait fautive a elle seule :

        1. :meth:`refuser` empilait `EcranRefus` **par-dessus** `E4-4`, qui
           restait dessous ;
        2. `Echap` sur `EcranRefus` depile -- on retombait donc sur `E4-4`,
           l'ecran d'un encodage **qui n'a plus lieu**, rotor compris ;
        3. son `on_key` intercepte `escape` (a juste titre : pendant une passe,
           laisser la touche remonter ferait disparaitre la tache de la vue) et
           monte `T6-1` ;
        4. « Interrompre » posait un drapeau que plus personne ne lit -- la
           passe etant finie -- et ne depilait rien ;
        5. `Echap` sur `T6-1` vaut « Reprendre » et redescend sur l'ecran mort.

        Seul `⏎` sur `EcranRefus` en sortait, et il n'etait plus atteignable
        une fois entre dans la boucle. `EPIC11-ARB-89` etait viole a la lettre :
        « Un refus qui n'offre aucune issue est aussi fautif qu'une destruction
        silencieuse. »

        **Le geste porte sur les DEUX conclusions, pas seulement sur le
        refus.** Le chemin nominal empilait `E4-5` par-dessus le meme `E4-4`
        mort : `Echap` depuis le compte rendu y retombait exactement pareil.
        Egan n'a rencontre que la branche de refus -- c'est celle qui lui est
        arrivee --, mais reparer la seule branche vue aurait laisse le piege
        entier sur l'autre.

        **On ne depile que ce qu'on a soi-meme monte**, et par IDENTITE :
        l'application retient l'ecran de la passe courante, et c'est lui qu'on
        retire de la pile. Un `pop_screen` inconditionnel retirerait l'ecran de
        quelqu'un d'autre le jour ou la conclusion arrive dans un etat imprevu
        -- c'est la meme discipline que la garde d'extinction du drapeau au
        demontage.

        **CORRIGE le 2026-09-07 : la premiere version de ce geste ne fermait
        rien.** Elle ne depilait que si `E4-4` etait **au sommet** ::

            if self.app.screen is ecran: self.app.pop_screen()

        La couche 2 de la revue a mesure que le cul-de-sac rouvrait entier des
        qu'un ecran tiers etait monte -- et que les **deux seules touches**
        qu'annonce `RACCOURCIS_ENCODAGE_EN_COURS`, `Echap` et `F1`, en montent
        une. Autrement dit la garde tombait en defaut exactement sur le geste
        d'Egan. La pile mesuree, cinq marches rejouees une par une ::

            [..., EcranEncodageEnCours, EcranInterruptionDeLEncodage, EcranResultatDuMaster]

        La condition d'identite n'etait pas fausse, elle etait **mal placee** :
        employee comme condition de DEPILEMENT elle est insuffisante, employee
        comme condition d'ARRET elle est juste. C'est ce que fait desormais
        `CoqueTui.retirer_l_ecran`, ecrite une fois pour les deux ateliers qui
        en ont besoin plutot que recopiee ici.
        """
        ecran = getattr(self.app, ATTRIBUT_DE_L_ECRAN_DE_LA_PASSE, None)
        retirer = getattr(self.app, "retirer_l_ecran", None)
        if ecran is None or retirer is None:
            return
        retirer(ecran)

    def interrompre(self, issue: Issue) -> None:
        """L'issue de `T6-1` qui arrete la passe. **L'autre ne vient pas ici.**

        « Reprendre l'encodage » est de la navigation : l'ecran la traite
        lui-meme en depilant. Seule « Interrompre » atteint le parcours, qui
        seul sait ce qu'il a ouvert.

        L'interruption est **demandee**, jamais imposee au coeur en cours de
        route : `encoder_le_master_du_lot` n'offre aucun point de sortie, et
        promettre un arret a la frame serait promettre ce que le coeur ne
        propose pas. La demande est honoree par :meth:`lancer`, **avant**
        l'appel : c'est la seule fenetre ou elle change quelque chose, et
        c'est la seule ou l'ecran dit vrai.

        **DEUX defauts sont fermes ici le 2026-09-06, et le premier est
        bloquant.**

        *Le cul-de-sac.* Cette methode posait un drapeau et **ne depilait
        rien** : `T6-1` restait monte apres qu'on avait choisi « Interrompre »,
        et son `Echap` valant « Reprendre », il redescendait sur l'ecran
        d'encodage. Egan, verbatim : « Echap pendant un rendu mene a l'ecran
        d'interruption mais l'interruption ne donne rien. Oblige de quitter ».
        Un ecran d'interruption qui survit a son issue est un cul-de-sac, quel
        que soit ce que l'issue declenche par ailleurs -- et c'est la moitie du
        piege que :meth:`_retirer_l_ecran_de_la_passe` ferme par l'autre bout.

        *Le mensonge.* Une fois le coeur parti, la demande n'arrete plus rien
        -- `codec_profiles` appelle `subprocess.run`, qui ne rend la main qu'a
        la fin --, et `T6-1` continuait d'annoncer « aucun master ne sera
        écrit ». Depiler sans le dire aurait laisse l'operateur devant un
        rotor qui tourne en croyant avoir arrete la passe, c'est-a-dire un
        ecran qui ment. Le passage porte donc desormais la demande, et `E4-4`
        la **dit en clair** dans sa ligne d'etat.

        **Ce qui n'est PAS fait ici, dit plutot que tu** : l'annulation reelle.
        Elle demande que `codec_profiles.run_encode` retienne son `Popen` au
        lieu d'appeler `subprocess.run`, c'est-a-dire une modification du
        coeur -- hors perimetre de cette nuit sur consigne d'Egan, et consignee
        en dette avec son origine.
        """
        if issue.cle != CLE_INTERROMPRE:
            return
        self.app.interruption_demandee = True
        if self.passage is not None:
            self.passage.demander_l_interruption()
        # **Depiler `T6-1`, et rien de plus.** L'ecran d'encodage reste : la
        # passe, elle, tourne toujours, et c'est lui qui porte desormais la
        # phrase qui le dit. Le faire disparaitre laisserait l'operateur sur le
        # menu pendant qu'un encodage ecrit un master dans son dos, puis verrait
        # `E4-5` surgir de nulle part.
        ecran = getattr(self.app, "screen", None)
        if isinstance(ecran, EcranInterruptionDeLEncodage):
            self.app.pop_screen()

    def abandonner(self):
        """Ce qu'une interruption laisse : **rien**, et on le dit en sortant.

        `EPIC11-ARB-13` : la fin d'une execution ramene au menu des ateliers du
        projet ouvert. Il n'y a pas de compte rendu a montrer -- aucun master
        n'a ete ecrit, et `E4-5` affirme ce qui existe sur le disque : le
        monter ici serait exactement l'etat « ou le passage suivant croirait
        l'encodage fini ».
        """
        self.app.revenir_aux_ateliers()
        return None

    # -- etape 7 : `E4-5`, le compte rendu ------------------------------------

    def refuser(self, refus: BaseException) -> EcranRefus:
        """Le refus du coeur, **relaye tel quel** (`EPIC11-ARB-30`).

        La TUI met en forme -- elle n'interprete pas, elle ne resume pas, elle
        ne requalifie pas. Le code est celui du vocabulaire ferme quand le
        refus en porte un, le nom de la classe levee sinon.

        Ce n'est pas un blocage sec : `EcranRefus` annonce `⏎ revenir aux
        ateliers`, et le message du coeur porte lui-meme ses issues -- c'est
        l'AC 4.6, qui mesure qu'aucun refus d'`encode` ne nomme une option qui
        n'existe pas.

        **L'ecran sait rendre trois listes, et ce point d'appel n'en remplissait
        aucune** (2026-09-06). `EcranRefus` porte `Non ecrit`, `Conserve` et
        `Suites` ; il recevait un code et une phrase, rien d'autre. Or ce
        refus-la a precisement quelque chose a dire sous `Conserve` : quand la
        verification technique echoue, `encode` **garde le fichier d'attente
        expres, pour diagnostic**, et la bascule n'a pas eu lieu -- le master
        precedent est intact octet a octet. C'est contractuel, l'exception
        porte le chemin en propre (`staged_path`), et le taire transformait une
        conservation deliberee en residu anonyme : Egan a supprime ce fichier
        a la main en le prenant pour une fuite.

        **Le refus de verification est SYSTEMATIQUE sur le terrain d'Egan**
        (mesure du 2026-09-06 : `expected_technical_metadata` exige
        `color_primaries` et `color_transfer` des sept profils, et un h264 y est
        refuse au meme titre qu'un DNxHD). Chaque tentative laisse donc un
        fichier d'attente. Ce n'est pas une fuite -- `prepare_output_directory`
        les balaie a la passe suivante, passe 24 h --, mais c'etait MUET, et
        c'est le silence qui a fait supprimer le fichier a la main.

        **Les trois listes sont LUES, jamais recomposees.** Le chemin conserve
        vient de l'exception ; le nom du master non ecrit vient du passage,
        c'est-a-dire de `plan.output_path.name`, donc de ce qu'`io.naming` a
        decide. Un nom recompose ici divergerait du fichier reel le jour ou la
        convention bouge.
        """
        conserve = _conserve_du_refus(refus)
        suites = list(SUITES_DU_REFUS)
        if conserve:
            suites.append(PHRASE_DU_FICHIER_CONSERVE)
        ecran = EcranRefus(code_du_refus(refus), phrase_du_refus(refus),
                           conserve=conserve,
                           non_ecrit=self._non_ecrit_du_refus(),
                           suites=suites)
        self.app.descendre(ecran)
        return ecran

    def _non_ecrit_du_refus(self) -> list[str]:
        """Le master que la passe n'a PAS ecrit, ou rien si on ne le sait pas.

        Le passage n'existe qu'a partir de :meth:`encoder` : un refus leve
        avant -- la planification, par exemple -- n'a aucun nom de master a
        annoncer, et en inventer un serait pire que de se taire.
        """
        if self.passage is None or not self.passage.nom_du_master:
            return []
        return [self.passage.nom_du_master]

    def conclure(self, master):
        """Monter `E4-5` sur ce que la passe a **ecrit et declare**.

        La duree d'encodage est celle du chronometre monte avant l'appel ; la
        duree du **master**, elle, est `None` -- rien au coeur ne la rend, et
        `MesureDuMaster` n'a aujourd'hui aucun producteur. La ligne disparait
        donc plutot que de se deriver de `frame_count / frame_rate`, ce que la
        tete de `atelier_exports_resultat` interdit nommement.
        """
        self.ecrit = MasterEcrit.du_master(
            master,
            duree_d_encodage_s=None if self._ecoule is None else self._ecoule())
        return ouvrir_le_resultat(self.app, self.ecrit, sur_suite=self.suivre)

    def suivre(self, suite: str) -> None:
        """Les suites de `E4-5`, et **chacune mene ailleurs**.

        `Ouvrir le dossier` et `Ouvrir le fichier` remettent au bureau et
        **disent** ce qui s'est passe, sans changer d'ecran : le compte rendu
        reste lisible au moment ou l'operateur va le comparer au contenu du
        dossier.

        `Encoder un autre lot` **depile jusqu'a `E4-1`**. C'est ce qui la rend
        discernable de `Retour aux ateliers`, que `EcranResultat` sert
        lui-meme en remontant d'un cran de plus (`EPIC11-ARB-13`) : tant que
        `E4-1` n'etait pas branche, les deux issues faisaient la meme chose --
        le lot G l'a note, ce cablage-ci le ferme, et le banc le mesure par
        l'ecran d'arrivee des deux.

        Une suite inconnue ne consomme pas la touche en silence : elle mene a
        l'ecran qui **nomme** l'absence.
        """
        if self.ecrit is not None and suite == SUITE_DOSSIER:
            ouvrir_le_dossier_du_master(self.app, self.ecrit)
            return
        if self.ecrit is not None and suite == SUITE_FICHIER:
            ouvrir_le_fichier_du_master(self.app, self.ecrit)
            return
        if suite == SUITE_AUTRE_LOT:
            remonter_a_l_ouverture_de_l_atelier(self.app)
            return
        self.app.descendre(EcranPasEncore(
            suite, self.app.QUAND_ARRIVENT_LES_ATELIERS))


def ouvrir_l_atelier_exports(app, dossier_projet, **reglages):
    """Ce que l'entree *Exports* du menu des ateliers ouvre.

    C'est le rappel que `ChaineReelle` injecte, et sa signature est celle que
    `ChaineReelle.atelier_exports` appelle : `(app, dossier)`. Tout le reste
    est du reglage que seuls les bancs fournissent -- meme forme que
    `atelier_scan_parcours.ouvrir_l_atelier_scan`.
    """
    return ParcoursExports(app, dossier_projet, **reglages).ouvrir()


__all__ = [
    "CODE_AUCUN_LOT",
    "CONSENTEMENT_AU_LOT_INCOMPLET",
    "ParcoursExports",
    "REFUS_NOMMES",
    "code_du_refus",
    "frames_du_balayage",
    "master_declare",
    "ouvrir_l_atelier_exports",
    "remonter_a_l_ouverture_de_l_atelier",
    "remonter_aux_reglages",
]
