# -*- coding: utf-8 -*-
"""`E3-2` -- la detection en cours, et ce qu'elle **n'ecrit pas**.

Story 11.5, lot C (AC 5). C'est le seul ecran du **temps 1** de l'atelier Scan
qui appelle le coeur : il soumet `scan_detect.run_scan_detect` a l'hote de la
coque, montre sa progression **en pages**, deverse le journal du coeur au fil
de l'eau, et rend un :class:`RapportDeDetection` que le rapport (`E3-3`,
`E3-4`) consomme.

**L'invariant que cet atelier existe pour tenir** (`EPIC11-ARB-6`) : le temps 1
n'ecrit **aucune frame**. Le seul artefact qu'il laisse est le **document de
detection**, ecrit par le coeur, par remplacement atomique, et c'est
precisement lui qui rend « quitter ici et reprendre plus tard » possible sans
redetecter. Rien de tout cela ne touche `frames-scannees/` -- le dossier des
frames scannees, nomme une seule fois au coeur
(`project_layout.SCAN_FRAMES_DIRNAME`, story 11.14) --, et le banc le mesure
sur le **disque** -- aux inodes et au `st_mtime_ns`, jamais par condensat : une
reecriture d'une fixture deterministe rend exactement les memes octets, et
c'est le defaut deja paye par `EPIC11-ARB-83` (`CLAUDE.md`, 2026-08-30).

**Ce que ce module ne fait pas, et c'est structurel :**

* il n'ecrit **aucun second mecanisme de progression** : `SurfaceExecution` et
  `progression.EmetteurProgression` sont livres, le canal est celui-la
  (AC 5.4) ;
* il n'ecrit **aucun second ecran d'execution ni d'interruption** : il
  *alimente* ceux d'`execution.py` et n'en substitue que ce que la detection
  contredit -- ses issues, et le cartouche qui parle d'ecriture ;
* il ne **projette** pas le rapport en panneaux de lot : c'est le lot D. Il
  rend les faits du coeur, il ne les met pas en forme.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable

from jsonschema.exceptions import ValidationError
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Static

from .. import (scan_detect, scan_detection, scan_ingest,
               scan_previz, scan_sorting)
from ..io import project_layout
from ..io.extraction_manifest import ExtractionPersistenceError
from ..io.reconstruction import ReconstructionError
from . import jetons
from .atelier_extraction_ecriture import (
    RelaisDeJournal,
    _lancer_apres_le_dessin,
)
from .atelier_scan import INDENT_DU_CURSEUR
from .atelier_scan_calibrate import EcranDeJugement
from .execution import (
    EcranExecution,
    EcranInterruption,
    EcranRefus,
    SurfaceExecution,
)
from .panneau import ChoixExclusif, Issue, LigneChiffree, Panneau

# ---------------------------------------------------------------------------
# Le vocabulaire de l'ecran -- une seule redaction, celle-ci
# ---------------------------------------------------------------------------

#: L'unite comptee par la barre. **Des pages, jamais des frames** (AC 5.4) :
#: le temps 1 n'en ecrit aucune, et une barre qui compterait des frames
#: annoncerait a l'operateur exactement ce que cette story existe pour
#: empecher. C'est aussi le `total` que le coeur emet -- le nombre de pages
#: ingerees, connu de lui seul.
UNITE = "pages"

#: L'en-tete de tache de `E3-2`, verbatim de la maquette validee
#: (`E3-2-scan-detection-en-cours.txt`, l. 5). Il porte l'invariant **dans la
#: zone centrale**, jamais en ligne d'etat : `EPIC11-ARB-56` interdit un motif
#: de conception en ligne d'etat, il n'interdit rien au contenu.
TITRE_DE_LA_TACHE = "Détection en cours — aucune frame n'est écrite"

#: La droite du bandeau, verbatim de la maquette (l. 2). C'est ce qui distingue
#: l'ecran d'execution du temps 1 de celui du temps 2 (`E3-7`), qui ecrit.
OBJET_DU_BANDEAU = "temps 1 sur 2 · détecter"

#: Le segment de bandeau -- l'atelier, pas le nom de la classe d'ecran. La
#: maquette porte `mmu · projet_demo · Scan`.
PALIER_DE_L_ATELIER = "Scan"

#: Le nom du journal du produit pour cette passe. Un nom **propre a l'atelier
#: Scan**, jamais celui de l'extraction et jamais le racine : deux ateliers qui
#: partageraient un nom de logger verraient leurs lignes tomber dans le journal
#: de l'autre, et un handler pose sur le racine capterait le bruit des
#: bibliotheques tierces.
NOM_DU_JOURNAL = "mixed_media_utility.tui.scan_detection"


#: Ce que `E3-2` declare n'avoir pas ecrit quand il refuse. **Un fait**, jamais
#: un conseil : c'est l'invariant du temps 1, et il vaut aussi bien pour un
#: refus que pour un succes.
NON_ECRIT_PAR_LE_TEMPS_1 = "Aucune frame, aucun manifeste"


# ---------------------------------------------------------------------------
# Les refus du coeur sur le chemin `scan detect`
# ---------------------------------------------------------------------------

#: **Les exceptions que le coeur leve sur le chemin de la detection**, lues des
#: modules qui les DEFINISSENT et jamais d'un enveloppeur : la TUI n'importe
#: pas `cli` (AC 8.1), et une frontiere AST livree le refuse deja.
#:
#: **Ce n'est plus une copie depuis la story 11.6 (lot B)** : la table est
#: publiee par `scan_detect.REFUS_DU_COEUR` et **lue** ici, comme
#: `scan_write.CODES_DE_SORTIE` l'est ailleurs. Elle etait redigee deux fois --
#: ici et dans `cli._REFUS_DU_COEUR_SUR_DETECT` -- parce que `scan_detect` n'en
#: publiait aucune ; le lot C de la 11.5 avait ferme l'ecart **par la mesure**,
#: un test d'egalite d'ensembles, faute de pouvoir le fermer par le code
#: (son AC 9.2 : « elle ne modifie pas le coeur »). Le lot B de la 11.6, lui,
#: est une story de coeur : il l'a ferme par le code. La mesure reste, et elle
#: ne peut plus que confirmer -- c'est le bon sens de l'histoire.
#:
#: Deux copies d'une meme regle divergent au premier ajustement, et ce depot en
#: a deja mesure trois dans `project_maintenance`.
REFUS_DU_COEUR: tuple[type[BaseException], ...] = scan_detect.REFUS_DU_COEUR


@dataclass(frozen=True)
class RefusDeDetection:
    """Un refus du coeur, **nomme par son code** et jamais par « echec ».

    `EPIC11-ARB-30` et `DESIGN.md` §9 : le code **et** la phrase viennent du
    coeur. Le code est le nom de la classe **levee**, pas celui de l'entree de
    la table qui l'a attrapee -- les deux different des qu'une exception herite
    d'une autre, et c'est la classe levee qui designe la panne.
    """

    code: str
    message: str


@dataclass(frozen=True)
class DemandeDeDetection:
    """Ce que l'ecran de depot (`E3-1`) transmet a la detection.

    `source` est **passee telle quelle** au coeur : « aucune coercition ici,
    c'est l'ingestion qui distingue les quatre formes, et elle seule »
    (`EPIC7-ARB-88`, verbatim de `run_scan_detect`). La coercer en `Path` ici
    detruirait la quatrieme forme -- une sequence de chemins faisant UN lot --
    et rendrait un `TypeError` nu au lieu d'un refus lisible.

    `dpi` est **obligatoire et sans defaut** (`EPIC7-ARB-44`) : aucun appelant
    n'en invente un. La classe ne lui donne donc aucune valeur par defaut, ce
    qui fait de l'oubli une erreur de construction et non un 300 devine.
    """

    dossier_projet: Path
    source: Any
    dpi: int
    #: Quand il est donne, l'appelant **promet** que la pile est un lot unique.
    #: `None` declenche le tri par QR du vrac (`EPIC5-ARB-106`).
    ingest_slug: str | None = None
    #: **La seconde issue d'`EPIC11-ARB-89`, portee jusqu'au coeur.** A `True`,
    #: l'ingestion ecrit dans un dossier de lot **voisin** au lieu de refuser
    #: ou d'ecraser -- « Tout doit etre versionnable OU ecrase »
    #: (`EPIC11-ARB-104`, sur le scenario de la planche reprise, retouchee,
    #: et passee une seconde fois au scanner).
    #:
    #: Le defaut est `False`, et c'est le comportement d'aujourd'hui : le
    #: versionnage est une **issue retenue par l'operateur**, jamais un regime.
    #: Un defaut a `True` versionnerait toute passe, c'est-a-dire l'inverse
    #: exact de l'arbitrage.
    #:
    #: **Aucune regle de rang ne vit ici** : ce module pose un booleen, et
    #: `io/version_ranks.py` reste le seul lieu ou un rang se decide
    #: (`EPIC11-ARB-108`, « il n'y a pas de mecanisme different par objet »).
    nouvelle_version: bool = False
    #: **L'interrupteur de l'adoption d'une planche etrangere**
    #: (`EPIC7-ARB-101`, porte a la TUI le 2026-09-07 par `EPIC11-ARB-267`).
    #: A `True`, le coeur substitue l'identite du projet courant aux payloads
    #: etrangers et note leur origine au manifeste
    #: (`reconstruction.CHAMP_ORIGINE_ADOPTEE`).
    #:
    #: **Le defaut est `False`, et il le reste.** L'adoption est une issue
    #: RETENUE par l'operateur, jamais un regime -- meme forme et meme motif
    #: que `nouvelle_version` juste au-dessus. Un defaut a `True` absorberait
    #: en silence une pile prise par erreur, qui est le seul cas que le refus
    #: attrapait vraiment, et rendrait rouge la frontiere negative
    #: `test_sans_adopter_le_coeur_n_ADOPTE_RIEN`.
    #:
    #: Verbatim d'Egan qui a ouvert ce chemin (`EPIC7-ARB-101`) : « c'est le
    #: seul moyen d'ouvrir un fichier provenant d'un autre projet sans avoir le
    #: projet lui-meme ». Ce que le refus proposait a la place -- « projet a
    #: utiliser : <un projet qu'on n'a pas> » -- etait un conseil inapplicable.
    adopter: bool = False


@dataclass(frozen=True)
class RapportDeDetection:
    """Ce qu'une passe du temps 1 a produit -- des faits, jamais des phrases.

    Les trois etats sont exclusifs et nommes : une passe **aboutit** (`issue`
    porte le `ScanDetectOutcome` du coeur), elle est **refusee** (`refus`), ou
    elle est **interrompue avant d'avoir commence** (`interrompu`).
    """

    issue: Any = None
    refus: RefusDeDetection | None = None
    interrompu: bool = False

    @property
    def documents(self) -> tuple:
        """Les documents de detection ecrits par le coeur, dans l'ordre du tri.

        AC 5.3 : c'est ce chemin-la qui permet de quitter apres la detection et
        de reprendre plus tard **sans redetecter** (`EPIC11-ARB-6`). Il est lu
        du `ScanDetectOutcome`, jamais reconstruit depuis un slug -- les deux
        divergent des qu'un fichier deja sous `scans/` est ingere en place.
        """
        return () if self.issue is None else tuple(self.issue.documents)

    @property
    def motif_d_arret(self) -> str | None:
        """L'un de `scan_detect.MOTIFS_D_ARRET`, ou `None`.

        **Un arret n'est pas un refus** : une pile dont aucune planche n'a
        livre son QR, ou qui ne porte que des pages de calibration, a bel et
        bien ete ingeree et la passe a abouti. Les confondre ferait afficher un
        ecran de refus la ou le coeur rend un succes.
        """
        return None if self.issue is None else self.issue.motif_d_arret


def refus_de(exception: BaseException) -> RefusDeDetection | None:
    """Traduire une exception du coeur en refus nomme, ou rendre `None`.

    `None` signifie « la table ne nomme pas cette exception » : l'appelant
    **relaie** alors, il ne fabrique pas un refus metier. Deguiser une panne de
    programmation en refus lisible est exactement ce que la table existe pour
    empecher -- l'operateur lirait un motif rassurant sur un bug.
    """
    for classe in REFUS_DU_COEUR:
        if isinstance(exception, classe):
            # **Le code nomme la classe LEVEE, pas l'entree qui a repondu.**
            # `IdentiteIncompletable` attrapee par `CorrectionInvalide` est le
            # cas type : c'est la premiere qui designe la panne.
            return RefusDeDetection(code=type(exception).__name__,
                                    message=str(exception))
    return None


# ---------------------------------------------------------------------------
# Le canal de progression -- en pages, et sans total devine
# ---------------------------------------------------------------------------

def canal_de_progression(surface: SurfaceExecution):
    """Le **seul** canal par lequel un jalon du coeur atteint `E3-2`.

    **Il ne passe pas par `SurfaceExecution.emetteur(total)`, et le motif est
    mesure.** Cette fabrique exige un `total` connu d'avance ; or le total de
    la detection est le **nombre de pages ingerees**, et l'ingestion a lieu
    *dans* `run_scan_detect`, apres que l'ecran est monte. Le seul total
    disponible avant l'appel serait le nombre de fichiers designes, que le
    coeur declare faux d'avance : « un total devine sur le nombre de fichiers
    designes serait faux des qu'une page est illisible et sautee, ou des que le
    lot entre par un PDF » (`run_scan_detect`, verbatim).

    Le rappel rend donc `surface.noter`, qui prend `(faites, total)` -- **la
    meme arite que le canal du depot** (`progression.EmetteurProgression`
    appelle son rappel avec deux entiers positionnels) -- et qui inscrit le
    total **que le coeur emet**. Aucun second mecanisme n'est redige : c'est le
    coeur qui possede l'emetteur, sa monotonie, l'absence de doublon et
    l'absorption des defaillances (`EPIC7-ARB-79`).

    **Rendre `surface.noter` et non un `lambda` qui l'appelle** n'est pas une
    coquetterie : un objet non appelable passe a `rappel_progression` part
    `actif is False` **sans lever et sans trace**, barre figee a `0/N` -- le
    defaut paye cote extraction le 2026-08-30. Le banc mesure donc aussi que le
    canal est **actif**, en assertant sur la suite exacte des jalons recus.
    """
    return surface.noter


def journal_du_produit() -> tuple[logging.Logger, RelaisDeJournal]:
    """Le logger passe au coeur, et son relais vers le journal de `E3-2`.

    Meme geste que cote extraction, **et le relais est le sien** : la classe est
    generique -- elle ne connait ni rush ni lot --, et deux redactions du meme
    handler divergeraient. Seul le **nom** du journal change, et c'est ce qui
    empeche les lignes d'une extraction d'atterrir dans le journal du Scan.

    `propagate` est coupe : sous une TUI, tout handler herite du racine ecrit
    sur `stdout` **par-dessus** l'interface, qui est un plein ecran.
    """
    logger = logging.getLogger(NOM_DU_JOURNAL)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    relais = RelaisDeJournal()
    # Le logger est un singleton par nom : deux detections successives dans la
    # meme session reutiliseraient le meme objet, et les relais s'empileraient
    # -- chaque ligne du coeur serait inscrite autant de fois qu'il y a eu de
    # detections.
    for ancien in list(logger.handlers):
        if isinstance(ancien, RelaisDeJournal):
            logger.removeHandler(ancien)
    logger.addHandler(relais)
    return logger, relais


# ---------------------------------------------------------------------------
# L'interruption d'une detection -- DEUX issues, et aucune ne parle d'ecriture
# ---------------------------------------------------------------------------

#: La cle de l'issue qui arrete la passe. Nommee, parce que l'ecran d'execution
#: la compare et qu'une chaine ecrite deux fois divergerait.
INTERROMPRE = "interrompre"

#: Ce que l'interruption d'une **detection** propose, et ce qu'elle ne propose
#: pas. Reponse a la question `Q4` de la fiche 11.5, **retenue telle quelle** :
#: les trois issues d'`EcranInterruption` parlent d'ecriture -- « garder ce qui
#: est deja ecrit », « effacer ce qui est deja ecrit » -- et **aucune ne
#: s'applique** a une passe qui n'ecrit aucune frame. Proposer d'effacer ce
#: qu'on n'a pas ecrit est pire qu'inutile : c'est un choix qui ment sur l'etat
#: du disque.
#:
#: Deux issues suffisent, et les invariants du choix exclusif les acceptent :
#: au moins deux issues actionnables, aucune preselectionnee, au moins une qui
#: n'ecrit pas. **Ici aucune des deux n'ecrit**, ce qui est la propriete meme
#: du temps 1 -- et c'est plus fort que l'invariant, pas plus faible.
#:
#: « Ne rien poser » se lit a la lettre : ni frame, ni manifeste, ni identite
#: posee sur le lot. Le **document de detection** que le coeur aurait deja
#: ecrit n'est pas « pose sur le lot » : c'est l'artefact reutilisable
#: qu'`EPIC11-ARB-6` veut precisement voir survivre -- « un operateur qui
#: quitte apres la detection laisse un document de detection reutilisable, pas
#: un lot a moitie ecrit ».
ISSUES_DE_L_INTERRUPTION = (
    Issue(INTERROMPRE, "Interrompre, ne rien poser"),
    Issue(EcranInterruption.REPRENDRE, "Reprendre la détection"),
)


class EcranInterruptionDeDetection(EcranInterruption):
    """`T6-1` du temps 1 : deux issues, et aucune ne parle d'ecriture.

    **On reutilise `EcranInterruption`** -- son clavier, son rendu, son `Echap`
    qui reprend au lieu de remonter, ses invariants de choix. Ce qui est
    substitue est exactement ce que la detection contredit, et rien de plus :
    la liste des issues, et le titre de l'atelier au bandeau.
    """

    titre = PALIER_DE_L_ATELIER
    ISSUES = ISSUES_DE_L_INTERRUPTION


class EcranDetectionEnCours(EcranExecution):
    """`E3-2` -- la barre en pages, le journal du coeur, et zero frame.

    Trois substitutions, chacune parce que la detection contredit la valeur
    heritee de l'ecran d'ecriture :

    * ``titre`` -- le bandeau nomme l'**atelier** (`mmu · projet_demo · Scan`),
      pas la classe d'ecran ;
    * :meth:`ouvrir_l_interruption` -- deux issues au lieu de trois (voir
      :data:`ISSUES_DE_L_INTERRUPTION`) ;
    * :meth:`panneau_de_ce_qui_est_ecrit` -- le cartouche herite compte des
      unites **ecrites** ; ici rien n'est ecrit, on compte des pages **lues**.
    """

    titre = PALIER_DE_L_ATELIER

    def ouvrir_l_interruption(self) -> EcranInterruptionDeDetection:
        """Monte l'interruption **de la detection** par-dessus l'execution.

        L'empilement et le rappel sont ceux de la classe mere -- « ouvrir cet
        ecran n'arrete rien » --, seule la classe montee change. Le rappel n'est
        pas facultatif : sans lui, les issues poseraient `issue_declenchee` et
        n'appelleraient personne, c'est-a-dire un cul-de-sac clavier.
        """
        ecran = EcranInterruptionDeDetection(
            self.panneau_de_ce_qui_est_ecrit(),
            sur_issue=self.issue_d_interruption)
        self.app.descendre(ecran)
        return ecran

    def panneau_de_ce_qui_est_ecrit(self) -> Panneau:
        """Ce que la passe a **lu**, et ce qu'elle a ecrit : rien.

        Le nom de la methode est celui de la classe mere -- c'est son point
        d'appel, il ne se renomme pas depuis une sous-classe -- mais son contenu
        ne peut pas l'etre : « Pages ecrites » serait faux sur les deux mots a
        la fois. Les deux premiers chiffres sont **mesures** (ils viennent des
        jalons du coeur), donc aucun ne porte la mention de majorant ; le
        troisieme est l'invariant du temps 1, dit a l'ecran plutot que suppose.
        """
        avancement = self.surface.avancement
        return Panneau(
            "Déjà lu",
            [LigneChiffree("Pages lues", avancement.faites, UNITE),
             LigneChiffree("Pages restantes",
                           max(avancement.total - avancement.faites, 0), UNITE),
             LigneChiffree("Frames écrites", 0, "frames")],
        )


# ===========================================================================
# Le conflit d'ecriture du temps 1 -- la SECONDE ISSUE d'`EPIC11-ARB-89`
#
# Le fait que ce bloc ferme, et il etait litteralement le blocage sec que
# l'arbitrage interdit : quand la pile deposee a **deja ete ingeree sous ce
# nom**, le coeur refuse -- « L'ingestion n'ecrase pas un lot existant: la
# copie fait foi et peut etre la seule trace restante du scan »
# (`scan_ingest._refuse_destructive_overwrite`) -- et `E3-2` ne savait rendre
# qu'un `EcranRefus` : une seule issue, qui remonte au menu. C'est le scenario
# meme qui a fonde `EPIC11-ARB-104`, verbatim d'Egan : « On me dit que le scan
# existe deja ! Pourtant j'ai modifie quelque chose. »
#
# **Ce bloc n'ecrit aucune regle de versionnage**, et c'est son invariant : il
# pose un booleen sur la demande, et `io/version_ranks.py` reste le seul lieu
# ou un rang se decide (`EPIC11-ARB-108`). Aucun rang n'est annonce a l'ecran
# non plus -- voir :func:`panneau_du_conflit`.
# ===========================================================================

#: **Les codes de refus qui PEUVENT etre un conflit d'ecriture du temps 1.**
#:
#: Lu de la classe, jamais ecrit en litteral : `refus_de` nomme le code par la
#: classe **levee**, et recopier « UnsupportedScanInputError » ici en ferait une
#: seconde redaction qui divergerait au premier renommage.
#:
#: **Un seul code, et c'est delibere.** Le refus de dpi
#: (`InvalidScanDpiError`), le lot vide (`EmptyScanLotError`) et la panne PDF
#: (`PdfIngestError`) sont des classes **soeurs**, pas des sous-classes : elles
#: ne peuvent pas entrer ici par heritage. C'est ce qui fait que le refus de
#: dpi garde exactement l'ecran d'aujourd'hui (AC 5.3).
CODES_D_UN_LOT_OCCUPE: tuple[str, ...] = (
    scan_ingest.UnsupportedScanInputError.__name__,
)

#: La cle de l'issue qui versionne. Nommee, parce que le parcours la compare et
#: qu'une chaine ecrite deux fois divergerait.
ISSUE_NOUVELLE_VERSION = "nouvelle-version"

#: La cle de l'issue qui n'ecrit pas.
ISSUE_RENONCER = "renoncer"

#: Le libelle de l'issue qui versionne. Il nomme ce qui sera ecrit -- **un lot
#: VOISIN** -- et ce qui ne le sera pas : celui qui occupe deja le nom.
#:
#: **Le rang n'y parait pas**, et c'est le meme choix que `E3-6` a fait le
#: 2026-09-01 : il se resout au coeur, et l'annoncer avant l'appel serait une
#: seconde regle de rang en TUI. Le nom de la fonction qui le resout n'est pas
#: ecrit ici non plus -- la frontiere negative du versionnage balaye ce paquet
#: **prose comprise**, et une reference citee est la premiere chose qu'une
#: relecture prend pour la reference.
LIBELLE_NOUVELLE_VERSION = (
    "Ingérer une nouvelle version, sans toucher au scan existant")

#: Le libelle de l'issue qui n'ecrit rien. Elle **nomme sa destination** : une
#: sortie qui ne dit pas ou elle mene est un cul-de-sac deguise.
LIBELLE_RENONCER = "Revenir au menu Scan, ne rien ingérer"

#: Le titre du point de jugement. Il ne dit **jamais** « echec »
#: (`DESIGN.md` section 9) : il nomme ce qui occupe le nom.
TITRE_DU_CONFLIT = "Ce nom de lot est déjà pris sous scans/"

#: Les deux libelles du cartouche chiffre (AC 5.5, `EPIC11-ARB-4`).
LIBELLE_LOT_OCCUPE = "Lot déjà sur le disque"
LIBELLE_PAGES_OCCUPANTES = "Pages qu'il porte"


@dataclass(frozen=True)
class ConflitDeDetection:
    """Ce qui occupe deja le nom vise -- **des faits mesures**, jamais un rang.

    `slug` est le nom du dossier de lot que la passe visait, compose par le
    coeur (`project_layout.scan_lot_dir`) depuis le slug que le coeur aurait
    retenu (`scan_ingest.slug_par_defaut`). `pages` est le cardinal des
    fichiers qu'il porte, **compte sur le disque**.

    Aucun rang n'y figure : le rang que le coeur prendra se resout au coeur, et
    l'annoncer ici serait la valeur qui a l'air juste -- la pire des deux
    erreurs possibles (`DESIGN.md` section 3), puisqu'une version creee entre
    l'affichage et l'appel la rendrait fausse.
    """

    slug: str
    pages: int


def dossier_du_lot_vise(demande: DemandeDeDetection) -> Path | None:
    """Le dossier `scans/<slug>/` que cette demande viserait, ou `None`.

    **Les deux composants viennent du coeur**, et aucun n'est recompose ici :
    `scan_ingest.slug_par_defaut` -- publie precisement pour qu'« une interface
    qui veut savoir *avant* de lancer une passe si le lot vise porte deja une
    detection » n'ait pas a rediger la derivation une seconde fois
    (`EPIC7-ARB-90`) -- et `project_layout.scan_lot_dir`, seul lieu qui joint
    `scans/` et le slug.

    **`None` vaut « je ne sais pas ou cette passe ecrirait »**, et c'est un
    repli, jamais une regle. Il couvre notamment le chemin de scan introuvable :
    `slug_par_defaut` y leve le meme refus que l'ingestion, et un lot qu'on ne
    sait pas nommer ne peut pas etre declare occupe -- c'est ce qui fait qu'un
    chemin introuvable garde l'ecran d'aujourd'hui (AC 5.3).
    """
    try:
        slug = demande.ingest_slug or scan_ingest.slug_par_defaut(
            demande.dossier_projet, demande.source)
        return project_layout.scan_lot_dir(demande.dossier_projet, slug)
    except (scan_ingest.ScanIngestError, OSError, TypeError, ValueError):
        # Un slug refuse, une source d'une forme que l'ingestion ne nomme pas,
        # un partage reseau demonte : aucun n'a lieu de faire tomber l'ecran.
        # Le releve est un **renseignement**, et il ne vaut pas une trace
        # Python nue devant l'operateur au moment ou il lit un refus.
        return None


def pages_du_dossier(dossier: Path | None) -> int:
    """Les fichiers **presents sur le disque** dans ce dossier de lot.

    Meme geste et meme repli que `atelier_scan_ecriture.frames_du_dossier` :
    **toute panne de lecture rend zero plutot que de lever**. `is_dir()` repond
    vrai sur un partage reseau demonte, et `iterdir()` leve alors.

    On compte **tous** les fichiers et non les seules images : l'ingestion
    materialise aussi le PDF d'origine et son `ingest.json`, et un comptage
    filtre sur les extensions d'image rendrait zero sur un lot entre par PDF --
    c'est-a-dire tairait l'occupation exacte qu'`ARB-4` demande de chiffrer.
    """
    if dossier is None:
        return 0
    try:
        if not dossier.is_dir():
            return 0
        return sum(1 for entree in sorted(dossier.iterdir())
                   if entree.is_file())
    except OSError:
        return 0


def conflit_de(demande: DemandeDeDetection,
               refus: RefusDeDetection | None) -> ConflitDeDetection | None:
    """Le conflit d'ecriture derriere ce refus, ou `None`.

    **Trois conditions, et il faut les trois.** Aucune ne reecrit la regle du
    coeur : elles disent seulement « ce refus-la peut etre un conflit, et il y
    a bien quelque chose a versionner ».

    1. le refus porte un code qui **peut** etre un conflit d'ecriture
       (:data:`CODES_D_UN_LOT_OCCUPE`) -- ce qui ecarte le refus de dpi, le lot
       vide et la panne PDF, qui sont des classes soeurs ;
    2. la passe **ne demandait pas deja une version**. Un rang de version
       epuise est lui aussi un `UnsupportedScanInputError`, et il n'arrive que
       sur une passe versionnee : y reproposer « ingerer une nouvelle version »
       serait un mensonge d'ecran, et surtout un cycle sans sortie. C'est ce
       qui **borne** la reprise ;
    3. le dossier de lot vise porte **au moins un fichier**. Un lot qu'aucun
       octet n'occupe n'a rien a versionner, et offrir l'issue y serait du
       bruit sur le regime nominal.

    **Ce que la condition peut manquer, dit plutot que tu.** Le releve porte
    sur le dossier du lot ; le coeur, lui, refuse sur les **fichiers de meme
    nom et de contenu different**. Les deux divergent sur un depot qui n'apporte
    que des pages neuves dans un lot deja ingere : l'issue est alors offerte
    alors que le coeur n'aurait pas refuse -- mais ce cas n'atteint jamais cet
    ecran, puisqu'il n'y a pas eu de refus. Elle diverge aussi sur les refus
    marginaux qui partagent la classe (une forme d'entree non supportee deposee
    dans un projet ou ce nom est deja pris). C'est un **excedent**, pas un
    manque, et l'excedent est le bon sens du risque : offrir une issue de trop
    ne detruit rien -- l'operateur qui la retient obtient ce qu'elle annonce,
    un lot voisin --, n'en offrir aucune est le blocage sec qu'`ARB-89`
    interdit.
    """
    if refus is None or refus.code not in CODES_D_UN_LOT_OCCUPE:
        return None
    if demande.nouvelle_version:
        return None
    dossier = dossier_du_lot_vise(demande)
    pages = pages_du_dossier(dossier)
    if dossier is None or pages <= 0:
        return None
    return ConflitDeDetection(slug=dossier.name, pages=pages)


def issues_du_conflit() -> list[Issue]:
    """Les **deux** issues du conflit, dans l'ordre ou l'ecran les pose.

    **Jamais zero, jamais une** : « un refus qui n'offre aucune issue est aussi
    fautif qu'une destruction silencieuse » (`EPIC11-ARB-89`).

    **Pourquoi le versionnage porte `ecrit=True`.** Sur ce point de jugement,
    l'issue de versionnage est la seule qui pose un octet -- elle relance la
    passe, qui ingere. La marquer garde l'invariant d'`EPIC11-ARB-45` : le
    curseur part au montage sur la premiere issue qui n'ecrit pas, donc sur
    « Revenir au menu Scan », et aucune ecriture n'est atteignable en une seule
    frappe. La marquer `ecrit=False` ferait partir le curseur **sur elle**.

    L'ordre est celui de la deliberation : ce qu'on propose d'abord, puis la
    sortie. Le rang de l'issue principale ne bouge pas pour autant -- c'est le
    curseur qui se place, pas la liste qui se reordonne.

    **Aucune n'est preselectionnee** : c'est `ChoixExclusif.__post_init__` qui
    le leve, et cet invariant n'est pas reecrit ici.
    """
    return [Issue(ISSUE_NOUVELLE_VERSION, LIBELLE_NOUVELLE_VERSION, ecrit=True),
            Issue(ISSUE_RENONCER, LIBELLE_RENONCER)]


def choix_du_conflit() -> ChoixExclusif:
    """Le point de jugement du conflit. Le curseur part sur la sortie."""
    return ChoixExclusif(issues_du_conflit())


def panneau_du_conflit(conflit: ConflitDeDetection) -> Panneau:
    """Le cartouche qui **chiffre** ce qui occupe deja le nom (AC 5.5).

    `EPIC11-ARB-4` : une issue neuve sans chiffre n'en est pas. Sans ces deux
    lignes, l'ecran offrirait de versionner sans dire ce qui est deja la, et le
    consentement porterait sur rien.

    **Les deux valeurs sont mesurees**, aucune n'est un majorant : le slug est
    celui que le coeur aurait retenu, le cardinal est compte sur le disque.

    **Aucun rang n'y figure.** L'AC 5.5 le demandait ; la frontiere negative du
    versionnage, livree le 2026-09-01, interdit le vocabulaire de rang dans ce
    paquet prose comprise, et les deux sont incompatibles. C'est la frontiere
    qui gagne, pour le motif qu'elle porte : le rang se resout au coeur, au
    moment de l'appel, et un rang affiche avant l'appel serait faux des qu'une
    autre version nait entre les deux.
    """
    return Panneau(TITRE_DU_CONFLIT, [
        LigneChiffree(LIBELLE_LOT_OCCUPE, conflit.slug),
        LigneChiffree(LIBELLE_PAGES_OCCUPANTES, conflit.pages, UNITE),
    ])


class EcranConflitDeDetection(EcranDeJugement):
    """`T5-2` du temps 1 : deux issues, un chiffre, et la phrase du coeur.

    **On reutilise `EcranDeJugement`** -- le tronc commun des points de
    jugement de `E3-9` -- plutot que d'en rediger un second : son clavier, son
    rendu, son rang de curseur **derive** et son etat chiffre sont deja
    mesures, et deux redactions du meme ecran divergeraient au premier
    ajustement. Ce qui est substitue est exactement ce que le conflit ajoute :
    le titre de l'atelier au bandeau, et le cartouche chiffre.

    Le message du coeur voyage **verbatim** (`EPIC11-ARB-30`) : l'ecran le
    relaie, il ne le reformule pas -- c'est lui qui nomme les fichiers en
    cause.
    """

    titre = PALIER_DE_L_ATELIER

    def __init__(self, conflit: ConflitDeDetection, refus: RefusDeDetection,
                 *, retenir: Callable[[Issue], None]) -> None:
        super().__init__(TITRE_DU_CONFLIT, refus.message, choix_du_conflit(),
                         retenir=retenir)
        self.conflit = conflit
        self.refus = refus

    def contenu(self) -> list[Widget]:
        """Les memes deux widgets que la classe mere, sous des identifiants a
        cet ecran : deux ecrans qui partageraient un identifiant se
        chercheraient dans les feuilles de style le jour ou l'un des deux en
        gagne une."""
        self._corps = Static("", id="corps-conflit-detection")
        return [Vertical(self._corps, id="centre-conflit-detection")]

    def lignes(self) -> list[str]:
        """Le cartouche s'insere **entre la phrase et les issues**.

        Le rang d'insertion est **derive** de la longueur des issues, jamais
        compte a la main -- exactement comme `rang_du_curseur`, qui reste juste
        parce qu'il se derive de la meme facon. Un rang ecrit en dur ferait
        peindre le curseur sur une autre ligne des qu'une ligne s'ajoute, et
        l'operateur verrait le curseur sur l'issue qui ecrit.
        """
        lignes = super().lignes()
        rang = len(lignes) - len(self.choix.issues)
        utile = jetons.largeur_utile(self.app.size.width)
        cartouche = [INDENT_DU_CURSEUR + ligne
                     for ligne in panneau_du_conflit(self.conflit).rendu(
                         utile, self.app.ascii_seul)]
        return lignes[:rang] + cartouche + [""] + lignes[rang:]


# ---------------------------------------------------------------------------
# `EPIC11-ARB-267` -- l'adoption d'une planche etrangere se DEMANDE
#
# `EPIC7-ARB-101` (Egan, 2026-08-27) ouvre le geste : « J'aimerais qu'on puisse
# effectivement ajouter un rush / planche / scan issu d'un autre projet DANS ce
# projet. [...] C'est le seul moyen d'ouvrir un fichier provenant d'un autre
# projet sans avoir le projet lui-meme. » Le coeur sait le faire depuis la
# 11.4b ; aucune surface ne posait son interrupteur, si bien que le produit
# opposait un refus dont l'arbitrage disait deja qu'il etait « un conseil
# inapplicable » -- il renvoie vers un projet qu'on n'a pas et ne peut pas
# avoir.
#
# **Ce qu'`EPIC11-ARB-267` tranche**, Egan le 2026-09-07 sur retour de recette :
# « ce que j'ai decide pour la GUI (fenetre volante) n'a pas a s'appliquer a la
# TUI qui peut tout a fait utiliser un modele d'ecran de confirmation connu avec
# une issue "adopter" a ajouter. » C'est ce qui leve la contradiction entre
# `EPIC7-ARB-106` -- qui demandait une fenetre volante -- et la TUI, ou il
# n'existe AUCUN `ModalScreen` : tous ses points de jugement sont des ecrans
# empiles. Le grief d'origine visait une case a cocher invisible faute de
# defilement ; un ecran plein la corrige aussi bien, et mieux.
#
# Ce qui est repris d'`EPIC7-ARB-106` et ne bouge pas : **une seule question,
# meme quand plusieurs projets sont en cause, et elle les NOMME TOUS** ; un
# « oui » **relance la detection tout seul**.
# ---------------------------------------------------------------------------

#: La cle de l'issue qui adopte.
ISSUE_ADOPTER = "adopter"

#: La cle de l'issue qui laisse les planches etrangeres dehors.
ISSUE_LAISSER_DEHORS = "laisser-dehors"

#: Le libelle de l'issue qui adopte. Il nomme ce qui sera ecrit -- les planches
#: entrent dans CE projet -- et pas le mecanisme qui l'ecrit.
LIBELLE_ADOPTER = "Adopter ces planches dans ce projet et relancer la détection"

#: Le libelle de l'issue qui n'ecrit rien. Elle **nomme sa destination**, comme
#: toute sortie de ce paquet : un cul-de-sac deguise n'est pas une issue.
LIBELLE_LAISSER_DEHORS = "Voir le rapport sans les adopter"

#: Le titre du point de jugement. Il ne dit **jamais** « echec » ni « refus »
#: (`DESIGN.md` section 9) : il nomme ce qui est la.
TITRE_DE_L_ADOPTION = "Ces planches viennent d'un autre projet"

#: La phrase du point de jugement. Elle dit ce que l'adoption FAIT, parce que
#: c'est sur cela que le consentement porte -- et elle dit que l'origine reste
#: ecrite, qui est la seule chose qui rend le geste reversible a la lecture.
PHRASE_DE_L_ADOPTION = (
    "Les adopter les fait entrer dans ce projet comme si elles y avaient été "
    "produites. Leur projet d'origine reste écrit au manifeste.")

#: Les deux libelles du cartouche chiffre (AC 5.5, `EPIC11-ARB-4`).
LIBELLE_PLANCHES_ETRANGERES = "Planches concernées"
LIBELLE_PROJETS_D_ORIGINE = "Projets d'origine"


@dataclass(frozen=True)
class PlanchesEtrangeres:
    """Ce que la passe a laisse dehors -- **des faits mesures**, pas un motif.

    `projets` porte les identifiants lus dans les QR, **tries et dedoublonnes**.
    Le tri n'est pas cosmetique : `EPIC7-ARB-106` veut « une seule question,
    meme quand plusieurs projets sont en cause, et elle les nomme tous », et un
    ordre qui changerait d'une passe a l'autre ferait relire la meme liste a
    chaque fois.

    `pages` est le cardinal des pages concernees, compte sur la partition.

    **`projets` peut etre plus court que `pages`, et c'est le cas nominal** :
    trente planches d'un meme projet etranger font une seule entree ici. Les
    deux chiffres repondent a deux questions differentes -- combien j'adopte,
    et d'ou ca vient -- et les confondre en un seul ferait annoncer « 1 projet »
    pour trente planches.
    """

    projets: tuple[str, ...]
    pages: int


def planches_etrangeres_de(partition) -> "PlanchesEtrangeres | None":
    """Les planches hors perimetre d'une partition, ou `None` s'il n'y en a pas.

    **`None` et un cardinal nul ne sont pas la meme information**, la regle de
    ce paquet : `None` dit « rien a demander », et c'est ce que l'appelant teste
    pour savoir s'il monte l'ecran. Un objet a zero page ferait monter un point
    de jugement sur une question qui ne se pose pas.

    **Une entree sans `projet_a_utiliser` compte quand meme dans `pages`.** Le
    coeur laisse ce champ a `None` quand le QR ne porte pas d'identifiant
    lisible ; la page est pourtant bien dehors, et l'oublier ferait annoncer un
    cardinal plus petit que ce que l'adoption ferait entrer. Seule la liste des
    projets l'ignore -- on ne nomme pas un projet qu'on n'a pas lu.
    """
    if partition is None:
        return None
    dehors = [entree for entree in partition.hors_perimetre
              if entree.motif in scan_sorting.MOTIFS_HORS_PERIMETRE]
    if not dehors:
        return None
    projets = sorted({entree.projet_a_utiliser for entree in dehors
                      if entree.projet_a_utiliser})
    return PlanchesEtrangeres(projets=tuple(projets), pages=len(dehors))


def issues_de_l_adoption() -> list[Issue]:
    """Les **deux** issues de l'adoption, dans l'ordre ou l'ecran les pose.

    Meme invariant que le conflit, et pour le meme motif : l'adoption porte
    `ecrit=True` -- elle relance la passe, qui ingere --, donc le curseur part
    au montage sur l'issue qui n'ecrit pas (`EPIC11-ARB-45`). Aucune ecriture
    n'est atteignable en une seule frappe.

    Et **jamais zero, jamais une** (`EPIC11-ARB-89`) : la sortie qui n'adopte
    pas mene au rapport, elle ne renvoie pas au menu. C'est ce que le refus
    d'aujourd'hui ne faisait pas -- il rendait un rapport vide sans dire qu'un
    geste existait.
    """
    return [Issue(ISSUE_ADOPTER, LIBELLE_ADOPTER, ecrit=True),
            Issue(ISSUE_LAISSER_DEHORS, LIBELLE_LAISSER_DEHORS)]


def choix_de_l_adoption() -> ChoixExclusif:
    """Le point de jugement de l'adoption. Le curseur part sur la sortie."""
    return ChoixExclusif(issues_de_l_adoption())


def panneau_de_l_adoption(etrangeres: PlanchesEtrangeres) -> Panneau:
    """Le cartouche qui **chiffre** ce qui serait adopte (AC 5.5).

    `EPIC11-ARB-4` : une issue neuve sans chiffre n'en est pas. Sans ces deux
    lignes, l'ecran offrirait d'adopter sans dire combien ni d'ou, et le
    consentement porterait sur rien.

    Les projets sont joints par une virgule, **tous**, jamais tronques a un
    « et N autres » : `EPIC7-ARB-106` demande qu'une seule question les nomme
    tous, et une liste abregee rouvrirait la question qu'elle ferme. Le
    cartouche se replie comme le reste ; c'est `Panneau.rendu` qui borne.

    Quand aucun projet n'a pu etre lu -- un QR sans identifiant lisible --, la
    ligne rend le glyphe neutre plutot qu'une chaine vide : `·` dit « pas
    mesure », le vide ne dit rien.
    """
    origine = ", ".join(etrangeres.projets) or jetons.GLYPHES["neutre"]
    return Panneau(TITRE_DE_L_ADOPTION, [
        LigneChiffree(LIBELLE_PLANCHES_ETRANGERES, etrangeres.pages, UNITE),
        LigneChiffree(LIBELLE_PROJETS_D_ORIGINE, origine),
    ])


class EcranAdoptionDeLaPlanche(EcranDeJugement):
    """Le point de jugement de l'adoption : deux issues, deux chiffres.

    **On reutilise `EcranDeJugement`**, comme `EcranConflitDeDetection` juste
    au-dessus et pour le meme motif : son clavier, son rendu, son rang de
    curseur derive et son etat chiffre sont deja mesures. C'est aussi ce
    qu'`EPIC11-ARB-267` demande en toutes lettres -- « un modele d'ecran de
    confirmation connu avec une issue "adopter" a ajouter ».

    La phrase est ecrite ici et ne vient pas du coeur : il n'y a **aucun refus**
    sur ce chemin. La passe a reussi, elle a simplement laisse des pages dehors.
    C'est la difference avec le conflit, dont la phrase est celle d'une
    exception relayee verbatim.
    """

    titre = PALIER_DE_L_ATELIER

    def __init__(self, etrangeres: PlanchesEtrangeres, *,
                 retenir: Callable[[Issue], None]) -> None:
        super().__init__(TITRE_DE_L_ADOPTION, PHRASE_DE_L_ADOPTION,
                         choix_de_l_adoption(), retenir=retenir)
        self.etrangeres = etrangeres

    def contenu(self) -> list[Widget]:
        """Les memes deux widgets que la classe mere, sous des identifiants a
        cet ecran -- deux ecrans qui partageraient un identifiant se
        chercheraient dans les feuilles de style le jour ou l'un en gagne une."""
        self._corps = Static("", id="corps-adoption-detection")
        return [Vertical(self._corps, id="centre-adoption-detection")]

    def lignes(self) -> list[str]:
        """Le cartouche s'insere **entre la phrase et les issues**, a un rang
        DERIVE de la longueur des issues -- jamais compte a la main, exactement
        comme `EcranConflitDeDetection.lignes` et pour la meme raison : un rang
        ecrit en dur ferait peindre le curseur sur l'issue qui ecrit des qu'une
        ligne s'ajoute."""
        lignes = super().lignes()
        rang = len(lignes) - len(self.choix.issues)
        utile = jetons.largeur_utile(self.app.size.width)
        cartouche = [INDENT_DU_CURSEUR + ligne
                     for ligne in panneau_de_l_adoption(self.etrangeres).rendu(
                         utile, self.app.ascii_seul)]
        return lignes[:rang] + cartouche + [""] + lignes[rang:]


def trancher_le_conflit(app, issue: Issue, demande: DemandeDeDetection, *,
                        logger, sur_rapport: Callable[["RapportDeDetection"], None],
                        detection: Callable[..., Any]) -> None:
    """Ce que chacune des deux issues fait, et **les deux menent quelque part**.

    Le versionnage **relance la passe entiere** avec le drapeau pose : ecran
    d'execution neuf, meme source, meme dpi, meme journal. C'est ce qui fait de
    l'issue une ecriture reelle et non une decoration -- le finding `K3`, paye
    quatre fois dans cet epic, est precisement l'issue navigable qui n'appelle
    personne.

    **La reprise est bornee** et ce n'est pas une esperance : la demande
    relancee porte `nouvelle_version=True`, et :func:`conflit_de` refuse de
    reconnaitre un conflit sur une passe deja versionnee. Un second refus
    remonte donc l'`EcranRefus` ordinaire, jamais ce meme ecran.

    Toute autre issue -- il n'y en a qu'une, et elle n'ecrit pas -- remonte au
    menu des ateliers (`EPIC11-ARB-13`).
    """
    if issue.cle == ISSUE_NOUVELLE_VERSION:
        ecran = ouvrir_la_detection(app)
        # **Au FIL, comme la passe d'origine.** Relancer la passe entiere
        # synchroniquement ici rejouerait le gel exactement -- et sur le chemin
        # le plus expose du parcours, puisque l'ecran d'arrivee de cette
        # relance porte l'issue qui ecrit.
        lancer_la_detection(
            app, ecran, replace(demande, nouvelle_version=True),
            logger=logger, sur_rapport=sur_rapport, detection=detection)
        return
    app.revenir_aux_ateliers()


# ---------------------------------------------------------------------------
# La passe : monter l'ecran, appeler le coeur, conclure
# ---------------------------------------------------------------------------

def ouvrir_la_detection(app, *, objet: str = OBJET_DU_BANDEAU
                        ) -> EcranDetectionEnCours:
    """Monter `E3-2` **avant** d'appeler le coeur.

    L'ordre n'est pas cosmetique : `EcranExecution.on_mount` est ce qui abonne
    l'ecran aux jalons de la surface. Appeler le coeur d'abord ferait ecrire les
    jalons dans une surface que personne n'ecoute encore, et la barre resterait
    figee du debut a la fin de la detection.
    """
    surface = SurfaceExecution(unite=UNITE)
    ecran = EcranDetectionEnCours(
        surface, titre_tache=TITRE_DE_LA_TACHE,
        sur_issue=lambda issue: _interrompre(app, issue), objet=objet)
    app.descendre(ecran)
    return ecran


def _interrompre(app, issue: Issue) -> None:
    """L'issue qui arrete la passe. « Reprendre » ne vient jamais ici.

    L'interruption est **demandee** ; elle est constatee par :func:`detecter`.
    """
    app.interruption_demandee = True


def detecter(demande: DemandeDeDetection, surface: SurfaceExecution, *,
             logger, hote: Callable[..., Any] | None = None,
             interrompu: Callable[[], bool] | None = None,
             detection: Callable[..., Any] = scan_detect.run_scan_detect
             ) -> RapportDeDetection:
    """Un appel de `run_scan_detect`, heberge, et **aucune frame ecrite**.

    `hote` est `CoqueTui.executer_en_processus` : le coeur est **heberge**, pas
    relance (`EPIC11-ARB-1`, AC 5.1). Il vaut l'appel direct par defaut, pour
    que la passe se mesure sans monter d'application.

    **La granularite de l'interruption est celle-ci et pas une autre, et le
    dire est plus honnete que de faire croire a un arret immediat**
    (`interrompu` est consulte **avant** l'appel, une fois) : `run_scan_detect`
    est un appel **synchrone sans point d'arret**, et le canal de progression
    ne peut pas l'arreter -- il est observationnel par contrat
    (`EPIC7-ARB-79` : « aucune de ses defaillances ne peut faire echouer,
    ralentir notablement ni modifier le travail qu'elle observe »). Une
    interruption qui arrive pendant l'appel arrive donc **apres** : la passe a
    produit son document, et le rapport le porte au lieu de le taire. Ce qui
    reste vrai dans tous les cas, et c'est l'invariant de la story : aucune
    frame n'a ete ecrite.

    Les erreurs hors table **traversent** : voir :func:`refus_de`.
    """
    hote = hote or (lambda fonction, *args, **kwargs: fonction(*args, **kwargs))
    if interrompu is not None and interrompu():
        # Rien n'a ete appele, donc rien n'a ete pose : ni frame, ni manifeste,
        # ni document. C'est le seul regime ou « ne rien poser » est vrai a la
        # lettre, et le rapport le dit sans document.
        return RapportDeDetection(interrompu=True)
    try:
        issue = hote(
            detection,
            demande.dossier_projet,
            # **Telle quelle** : c'est l'ingestion qui distingue les quatre
            # formes (`EPIC7-ARB-88`), et elle seule.
            demande.source,
            dpi=demande.dpi,
            ingest_slug=demande.ingest_slug,
            # **Toujours transmis, versionnage ou non.** Le passer
            # conditionnellement ferait deux regimes de resolution du meme
            # rang -- c'est la lecon que `828de0d` a payee sur le temps 2 avec
            # `manifest_du_projet`. Le drapeau traverse **verbatim** : aucune
            # expression ne le recalcule, et une frontiere a l'AST le mesure.
            nouvelle_version=demande.nouvelle_version,
            # **Toujours transmis, adoption ou non**, pour la meme raison que
            # la ligne au-dessus : un drapeau passe conditionnellement ferait
            # deux regimes d'appel du meme point d'entree. Il traverse
            # VERBATIM, aucune expression ne le recalcule.
            adopter=demande.adopter,
            logger=logger,
            rappel_progression=canal_de_progression(surface),
        )
    except BaseException as exception:  # noqa: BLE001 -- voir refus_de
        refus = refus_de(exception)
        if refus is None:
            raise
        return RapportDeDetection(refus=refus)
    return RapportDeDetection(
        issue=issue,
        interrompu=bool(interrompu is not None and interrompu()))


def executer_et_conclure(app, ecran: EcranDetectionEnCours,
                         demande: DemandeDeDetection, *, logger,
                         sur_rapport: Callable[[RapportDeDetection], None],
                         detection: Callable[..., Any] = scan_detect.run_scan_detect
                         ) -> RapportDeDetection:
    """Lancer la detection, puis conclure -- un seul chemin pour les trois issues.

    C'est ce qui garantit qu'`oublier_la_tache` est appele dans tous les cas :
    un drapeau `tache_en_cours` reste a vrai ferait de `Echap` une interruption
    bien apres la fin de la passe.

    Trois conclusions, et chacune a sa destination :

    * **refus** -- `EcranRefus`, avec le code et la phrase du coeur, et rien
      d'ajoute (`DESIGN.md` §9, AC 5.5) ;
    * **interruption** -- retour au menu des ateliers du projet ouvert
      (`EPIC11-ARB-13`). Le rapport n'est pas remis a la suite : l'operateur a
      demande a s'arreter la ;
    * **passe aboutie** -- le rapport part a `sur_rapport`, que le lot du
      rapport (`E3-3` / `E3-4`) fournit.

    **`sur_rapport` n'a AUCUN defaut, et c'est structurel** : un
    `Callable | None = None` assorti d'un `if ... is not None` transforme
    l'oubli du cablage en **silence**, et c'est litteralement le finding `K3`
    -- `ouvrir_le_resultat` acceptait `sur_suite`, son unique point d'appel ne
    le passait pas, et les quatre suites etaient navigables et decoratives. Le
    rendre requis fait de l'oubli une erreur d'appel. Meme geste pour
    `detection`, dont le defaut est le **vrai** point d'entree du coeur : c'est
    le double de banc qui est l'exception, pas le defaut.
    """
    rapport = detecter(
        demande, ecran.surface, logger=logger,
        hote=app.executer_en_processus,
        interrompu=lambda: bool(app.interruption_demandee),
        detection=detection)
    return conclure_la_detection(app, rapport, demande, logger=logger,
                                 sur_rapport=sur_rapport, detection=detection)


def lancer_la_detection(app, ecran: EcranDetectionEnCours,
                        demande: DemandeDeDetection, *, logger,
                        sur_rapport: Callable[["RapportDeDetection"], None],
                        detection: Callable[..., Any] = scan_detect.run_scan_detect
                        ) -> Any:
    """La passe **dans un fil de travail**, pour que l'ecran vive pendant.

    **Ce que cette fonction ferme, et Egan l'a constate en utilisant le
    produit** (2026-09-06) : « on passe de la confirmation au succes sans voir
    la progression. L'interface se fige et toutes les touches tapees pendant
    l'attente se resolvent a la sortie. » Mesure du jour, sur la vraie boucle :
    **zero image** ecrite du montage a la fin de la passe, l'ecran meme pas
    monte, et les touches frappees pendant delivrees a l'ecran SUIVANT.

    **Pourquoi le fil et pas seulement un rendez-vous de dessin.** Un
    `call_after_refresh` fait apparaitre l'ecran **une fois** puis rend la
    boucle a l'appel synchrone : la barre se fige et les touches s'accumulent
    quand meme. Le fil est la seule forme qui garde la boucle vivante
    **pendant** la passe -- donc qui rend l'ecran veritablement interruptible
    et qui fait atterrir les touches sur l'ecran que l'operateur REGARDE.

    **Et c'est ce chemin-la qui le meritait en premier**, mesure plutot que
    suppose : l'ecran d'arrivee de cette passe (`E3-3`/`E3-4`) porte
    `Issue(ISSUE_ECRIRE, ..., ecrit=True)`. Balayage exhaustif des rafales de
    une a trois touches : **deux frappes suffisent** -- `up` puis `entree`
    declenche `ecrire`. La garde d'`EPIC11-ARB-45` (le curseur part sur une
    issue qui n'ecrit pas) tient contre la frappe accidentelle UNIQUE ; elle
    n'est pas dimensionnee pour la rafale qu'un gel produit. Les deux chemins
    PDF, dont les ecrans d'arrivee ne portent aucune issue ecrivante, ne
    couraient pas ce risque-la.

    **Le drapeau se pose ICI, avant le fil, et pas dans le fil.** Entre le
    `run_worker` et la premiere ligne du fil, la boucle tourne : un `Echap` qui
    y tomberait depilerait l'ecran de passe sous la passe. C'est le geste que
    `atelier_scan_parcours.lancer_la_passe_de_calibration` porte deja, et le
    motif est le meme. Il ne remplace pas celui d'`EcranExecution.on_mount` --
    il le devance, puisque `on_mount` ne tournait jamais quand la boucle etait
    prise.

    Rend le `Worker`, pas le rapport : le rapport n'existe pas encore quand
    cette fonction rend la main, et c'est exactement ce qui change.
    :func:`executer_et_conclure` reste, synchrone, pour les appelants qui
    veulent le rapport tout de suite -- les bancs, au premier chef.
    """
    app.tache_en_cours = True

    def passe() -> None:
        try:
            rapport = detecter(
                demande, ecran.surface, logger=logger,
                hote=app.executer_en_processus,
                interrompu=lambda: bool(app.interruption_demandee),
                detection=detection)
        except BaseException:
            # Le coeur a leve : le drapeau tombe **ici**, puisque
            # `conclure_la_detection` ne sera pas atteinte. C'est la moitie du
            # `finally` d'origine qui reste necessaire.
            app.call_from_thread(app.oublier_la_tache)
            raise
        app.call_from_thread(conclure_la_detection, app, rapport, demande,
                             logger=logger, sur_rapport=sur_rapport,
                             detection=detection)

    # **Le fil ne part qu'APRES le dessin** (mesure du 2026-09-06).
    # `EcranDetectionEnCours` est un `EcranExecution`, dont l'`on_mount`
    # RALLUME `tache_en_cours`. Or `Mount` est distribue par la boucle : un fil
    # parti dans la foulee de `descendre` pouvait eteindre le drapeau AVANT ce
    # montage, qui le rallumait ensuite -- ordre mesure a la sonde, drapeau
    # final a vrai, atelier mort pour la session sur une panne.
    #
    # Le rendez-vous ordonne les deux, et il tient l'AC d'origine par la meme
    # occasion : l'ecran est monte ET PEINT avant que le coeur parte.
    #
    # **Cette fonction ne rend donc plus le `Worker`** -- il n'existe pas
    # encore quand elle rend la main. Aucun appelant ne le lisait ; ce qui
    # compte pour eux est que le rapport arrive par `sur_rapport`.
    _lancer_apres_le_dessin(app, lambda: app.run_worker(
        passe, thread=True, name="scan-detect",
        description="detecter les planches d'un scan"))


def conclure_la_detection(app, rapport: RapportDeDetection,
                          demande: DemandeDeDetection, *, logger,
                          sur_rapport: Callable[["RapportDeDetection"], None],
                          detection: Callable[..., Any]) -> RapportDeDetection:
    """Les quatre conclusions, **et rien d'autre**. Appelee DEPUIS LA BOUCLE.

    Extraite d':func:`executer_et_conclure` sans changer une ligne de son
    corps, pour une seule raison : elle touche l'arbre de widgets -- elle
    empile, elle remonte, elle remet le rapport a son appelant -- et elle doit
    donc tourner sur la boucle d'evenements. :func:`lancer_la_detection` la
    rappelle par `call_from_thread` ; `executer_et_conclure`, qui reste
    synchrone, l'appelle directement.

    **Un seul passage par la boucle**, comme
    `atelier_scan_parcours.conclure_la_passe` : l'oubli de la tache et la
    conclusion sont dans la MEME fonction. Deux `call_from_thread` successifs
    laisseraient la boucle libre entre eux, avec `tache_en_cours` a faux et
    l'ecran de passe encore monte -- c'est le finding `F1` de la vague 4, paye
    une fois et qu'on ne repaie pas ici.
    """
    app.oublier_la_tache()
    if rapport.refus is not None:
        conflit = conflit_de(demande, rapport.refus)
        if conflit is None:
            app.descendre(EcranRefus(
                rapport.refus.code, rapport.refus.message,
                non_ecrit=[NON_ECRIT_PAR_LE_TEMPS_1]))
        else:
            # **Le seul refus qui gagne une issue est celui qui aurait
            # ECRASE.** `EPIC11-ARB-147` a corrige, le jour meme, une AC qui
            # appliquait `ARB-89` par ressemblance de forme a un refus qui
            # n'ecrivait rien : un refus qui ne detruit rien n'a pas besoin
            # d'issue de secours, et lui en fabriquer une produit un ecran qui
            # demande de choisir entre deux facons de ne rien faire.
            app.descendre(EcranConflitDeDetection(
                conflit, rapport.refus,
                retenir=lambda issue: trancher_le_conflit(
                    app, issue, demande, logger=logger,
                    sur_rapport=sur_rapport, detection=detection)))
    elif rapport.interrompu:
        app.revenir_aux_ateliers()
    else:
        sur_rapport(rapport)
    return rapport

