# -*- coding: utf-8 -*-
"""Le point d'entree de COEUR d'`encode` -- le master d'un lot, de bout en bout.

Story 11.8, **lot B1**, AC 2.1, 2.2 et 2.4. Ce module porte la sequence que
`cli.encode_command` orchestrait jusqu'ici : gardes d'ouverture, validation du
manifest, decision (`encode.plan_encode`), recapitulatif, consentement, balayage
des residus, encodage sous le filet de `SIGTERM`, verification technique, et
declaration au manifest.

**Pourquoi il existe.** L'atelier Exports de la TUI n'a, aujourd'hui, **rien a
appeler** : `encode_command` porte la sequence entiere dans son propre corps,
prend un objet `args` argparse, lit `stdin`, imprime sur `stdout`/`stderr` et
rend un entier -- et la TUI a **interdiction d'importer `cli`** (frontiere de la
11.4b, mesuree par `tests/unit/tui/test_frontiere_cli.py`). C'est mot pour mot
le motif d'`EPIC11-ARB-129` pour le temps 2 du Scan, et le **quatrieme** geste
de cette famille apres `scan_detect.run_scan_detect` (7.3),
`scan_write.ecrire_depuis_le_document` (11.4b, lot S1) et
`makepdf.generer_les_planches_du_lot` (11.7, lot B). Il suit leur patron, il
n'en invente pas un.

**Pourquoi un module NEUF, et pas une fonction de plus dans `encode.py`.**
`encode.py` declare, et **un banc verrouille**, qu'il n'ecrit jamais le
manifest : `test_the_decision_module_still_never_writes_the_manifest` compte a
zero les noms `persist_encode` et `_atomic_write` dans son source. Cette
frontiere est celle qui empeche la decision de dependre du document -- « son
inverse aurait rendu l'encodage impossible a tester sans manifest ». Or la
sequence deplacee ici **declare au manifest**, puisque c'est ce que la story 6.5
a branche. La poser dans `encode.py` aurait donc casse une frontiere mesuree
pour loger une commodite ; elle vit a cote, exactement comme `makepdf.py` vit a
cote de `pdf_composition.py`.

**Le contrat, en une phrase** : ce module ne met en forme aucun message pour un
terminal, ne lit jamais `stdin` et ne rend aucun code de retour -- il **leve**
les refus nommes et les exceptions du coeur **inchangees**, et rend un
:class:`MasterDuLot` sur le chemin qui aboutit. `cli.encode_command` en devient
une **enveloppe** : memes codes de sortie (`0`, `1`, `2`, `3`, `130`, `143`),
memes messages imprimes, meme `logs/encode.log`, meme master octet pour octet.

**Le corps a ete DEPLACE, jamais reecrit** (AC 2.2). Une seconde redaction
divergerait, et l'ecart ne se verrait que sur les masters produits. La mesure du
deplacement est le dossier d'identite du lot (`tests/unit/test_encode_noyau.py`,
reference `tests/fixtures/identite-encode-bad2f294.json`) : vingt-cinq
invocations reelles de `cli.main` qui **encodent pour de vrai**, comparees au
releve joue AVANT le deplacement -- code de sortie, `stdout`/`stderr` au
caractere pres, condensat SHA-256 de chaque fichier, rapport `ffprobe` champ a
champ, manifest aplati et `logs/encode.log`. L'ensemble des scenarios qui
divergent doit y etre **vide**.

**Ce module ne lit JAMAIS `stdin` et n'imprime jamais.** Sous `textual`, `stdin`
appartient a la boucle d'evenements et un appel bloquant y gele l'interface
entiere (`EPIC7-ARB-106`) ; une ligne imprimee, elle, tombe **sous** l'ecran
dessine. Les trois points ou la sequence parlait a un terminal sont donc devenus
des **rappels optionnels** -- `annoncer_le_recapitulatif`, `confirmer_l_encodage`
et `annoncer_le_master` --, sur le patron exact d'`annoncer_la_completude` et
`confirmer_l_ecrasement` de `scan_write`.

**Il journalise, en revanche, et exactement ou la commande le faisait.** Le
journal n'est pas une sortie de terminal : c'est la trace durable de la passe, et
`logs/encode.log` fait partie de l'observable que l'AC 2.2 fige. Les seules
lignes qui restent a l'enveloppe sont celles de ses `except` -- un refus est
journalise la ou il devient un code de sortie.

**Il n'a aucun parametre de NOM DE MASTER, et c'est un fait mesure plutot qu'un
oubli.** `EPIC11-ARB-141` a retire l'edition des noms partout ou elle ne peut
pas etre effective, et `encode.plan_encode` n'a aucun parametre de nom : un
master est nomme par `io.naming`, pas par un operateur. La frontiere de l'AC 2.4
mesure l'ensemble **exact** des mots-cles transmis au coeur, ce qui rend ce
retrait **reversible** : le jour ou `plan_encode` gagnera ce parametre, elle
rougira au lieu de laisser l'ecart redevenir invisible.

Ce module est du **coeur** : il n'importe ni `cli`, ni `gui/`, ni `tui/`.
"""

from __future__ import annotations

import contextlib
import logging
import signal
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema.exceptions import ValidationError

from . import codec_profiles, encode, video_metadata
from .io import encode_manifest, extraction_manifest, project_layout
from .io.extraction_manifest import ExtractionPersistenceError
from .io.manifest import validate_manifest
from .io.naming import NamingError

__all__ = [
    "CODES_DE_SORTIE",
    "CODE_ARRET_DEMANDE",
    "CODE_ERREUR",
    "CODE_INTERRUPTION_CLAVIER",
    "CODE_PREREQUIS_ABSENT",
    "CODE_REFUS",
    "CODE_SUCCES",
    "EncodageInterrompu",
    "EncodageNonConsenti",
    "ErreurDeDisquePendantEncodage",
    "MasterDuLot",
    "MOTS_CLES_DE_LA_DECISION",
    "PHASES",
    "RefusDOuvertureDuProjet",
    "TerminaisonDemandee",
    "code_de_sortie",
    "encoder_le_master_du_lot",
    "le_signal_tue_l_encodeur",
    "ouvrir_le_journal",
    "refuser_l_ouverture_du_projet",
]


# ---------------------------------------------------------------------------
# Les refus propres a cette sequence
# ---------------------------------------------------------------------------

class RefusDOuvertureDuProjet(ValueError):
    """Le projet n'est pas ouvrable : dossier absent, ou manifest absent.

    Elle derive de `ValueError` comme `RefusDeMakepdf` et
    `ScanDetectError`, et pour le meme motif qu'elle n'est **pas** une
    `encode.EncodeDecisionError` : cette derniere exige un code du vocabulaire
    ferme de la story 6.1, et les deux gardes d'ouverture n'en ont aucun -- elles
    precedent le vocabulaire, comme elles precedent le journal.
    """


class EncodageNonConsenti(Exception):
    """L'operateur n'a pas accorde l'encodage. **Rien n'a ete ecrit.**

    Elle porte le message que le rappel de consentement a rendu, verbatim : les
    trois motifs de refus (mode non interactif sans drapeau, saisie interrompue,
    reponse negative) ne disent pas la meme chose, et les recomposer ici en
    ferait une seconde redaction.

    Elle n'est pas un echec : c'est le motif de la story 3.3 -- rien n'a rate,
    l'operateur a dit non --, et c'est pourquoi elle vaut `3` et non `1`.
    """


class TerminaisonDemandee(BaseException):
    """`SIGTERM` recu pendant l'encodage.

    Distincte de `KeyboardInterrupt`, qui nomme `SIGINT` : les deux signaux
    n'ont ni la meme origine (`Ctrl-C` contre `kill`, `docker stop`,
    ordonnanceur) ni le meme code de sortie conventionnel (130 contre 143).

    Deplacee de `cli._EncodeTerminated`, qui n'en est plus qu'un alias : la TUI
    a le meme besoin -- un encodage arrete ne doit pas laisser ffmpeg orphelin
    -- et elle ne peut pas importer `cli` pour l'obtenir.

    **Elle derive de `BaseException`, comme `KeyboardInterrupt`, et ce n'est
    pas un detail de gout.** Elle est levee depuis un GESTIONNAIRE DE SIGNAL,
    donc elle peut surgir n'importe ou dans le bloc `le_signal_tue_l_encodeur`
    -- au milieu d'une boucle de lecture, au milieu d'un rappel de progression,
    n'importe quand. Or ce chemin traverse plusieurs absorbeurs larges dont
    l'existence est LEGITIME : le canal de progression est observationnel
    (`EPIC7-ARB-79`, il ne casse jamais ce qu'il observe) et `emettre` absorbe
    donc tout ce que le rappel leve. Une exception d'ARRET qui derive
    d'`Exception` est avalee par chacun d'eux, et un arret d'operateur rend
    alors un SUCCES.

    **Ce que la mesure a coute avant d'aboutir ici**, et c'est pourquoi le
    motif est ecrit plutot que sous-entendu :

    * revue de la story 6.7, couche 1, finding `P4` : canal actif, un `SIGTERM`
      rendait `rc=0` **apres 6,0 s** -- l'encodage allait au bout -- la ou le
      repli `AR3` levait a 1,5 s ;
    * premiere fermeture, par une garde LOCALE dans `codec_profiles` : elle a
      ferme ce site-la et **deux defauts neufs** que la couche de reprise a
      mesures. Elle introduisait un `except ImportError: return False`, que la
      frontiere de la story 8.4 interdit nommement au coeur -- rouge mesurable
      sur `test_le_coeur_ne_se_rabat_jamais_en_silence_sur_une_dependance_absente`.
      Et elle ne couvrait **pas** la fenetre du rappel : un arret tombant dans
      `EmetteurProgression.emettre` restait avale **aux deux sites**, le flux
      lu jusqu'au bout et les trois frames sondees apres l'arret.

    La classe de base ferme les deux d'un seul geste, sans garde nulle part et
    sans toucher `progression.py` : aucun `except Exception` du depot ne voit
    plus passer un arret demande. C'est exactement le regime dont
    `KeyboardInterrupt` beneficie deja, et c'est pour ca qu'elle n'a jamais eu
    besoin de garde.

    **Ce que ce choix impose, dit plutot que tu** : qui veut l'attraper doit la
    NOMMER. Les deux sites du depot le font deja
    (`encoder_le_master_du_lot` et `cli._EncodeTerminated`), et
    `test_l_arret_demande_derive_de_BaseException` mesure que la classe de base
    ne se reperd pas.
    """


class EncodageInterrompu(Exception):
    """Une interruption -- clavier ou signal -- pendant la sequence.

    **Elle porte la PHASE**, et c'est tout ce qui la justifie : les trois
    endroits ou la sequence peut etre interrompue ne laissent pas le meme etat
    derriere eux, donc ne disent pas la meme chose ni ne rendent le meme code.

    * `decision` -- rien n'a ete encode, rien n'a ete ecrit ;
    * `encodage` -- l'encodeur est tue avec la commande, le master precedent est
      intact, un fichier d'attente peut subsister ;
    * `persistance` -- le master **est ecrit** et n'est **pas** declare, le
      manifest precedent est intact.

    Le message est compose ici plutot que dans l'enveloppe parce qu'il enonce ce
    que la sequence a laisse sur le disque : seule la sequence le sait, et une
    interface qui le recomposerait le recomposerait peut-etre faux.
    """

    def __init__(self, message: str, *, phase: str,
                 par_signal: bool = False) -> None:
        super().__init__(message)
        if phase not in PHASES:
            raise ValueError(
                f"Phase d'interruption inconnue: {phase!r}. Phases: "
                f"{', '.join(PHASES)}.")
        #: L'une de :data:`PHASES`.
        self.phase = phase
        #: Vrai pour `SIGTERM`, faux pour `Ctrl-C`. C'est **lui** qui commande
        #: le code de sortie (143 contre 130), jamais la phase.
        self.par_signal = par_signal

    @property
    def code_de_sortie(self) -> int:
        return CODE_ARRET_DEMANDE if self.par_signal else CODE_INTERRUPTION_CLAVIER


class ErreurDeDisquePendantEncodage(OSError):
    """Le disque a lache **pendant** l'encodage : plus d'espace, plus de droits.

    Une sous-classe nommee plutot qu'une `OSError` nue, et c'est une mesure :
    l'enveloppe rendait `1` pour une `OSError` **de la phase d'encodage
    seulement**. Une `OSError` de la phase de decision remontait -- et remonte
    toujours -- en trace Python. Un filet pose sur `OSError` nue dans la table
    de sortie aurait donc referme, en silence, un chemin que la commande
    laissait ouvert : un changement d'observable, ce que l'AC 2.2 interdit.
    """


#: Les trois phases ou la sequence peut etre interrompue. Nommees, et
#: **fermees** : une quatrieme phase serait un endroit de plus ou l'etat laisse
#: sur le disque n'est pas celui que le message annonce.
PHASES: tuple[str, ...] = ("decision", "encodage", "persistance")


# ---------------------------------------------------------------------------
# Codes de sortie, et la table qui les commande
# ---------------------------------------------------------------------------

#: Succes.
CODE_SUCCES = 0
#: Tout refus en amont, sans qu'aucun fichier ait ete ecrit ; echec en cours
#: d'encodage ; verification technique en echec ; echec de declaration.
CODE_ERREUR = 1
#: Prerequis externe absent -- ffmpeg sans l'encodeur du profil, ffprobe
#: introuvable : la meme classe de panne que celle dont `extract` fait un `2`.
CODE_PREREQUIS_ABSENT = 2
#: Refus de confirmation (motif de la story 3.3) : rien n'a echoue, l'operateur
#: a simplement dit non.
CODE_REFUS = 3
#: Interruption clavier (`SIGINT`).
CODE_INTERRUPTION_CLAVIER = 130
#: Arret demande (`SIGTERM`).
CODE_ARRET_DEMANDE = 143

#: La table exception -> code de sortie, **dans l'ordre de la pile d'`except`
#: qu'elle remplace**. Elle vivait dans `cli.encode_command` seule ; c'est le
#: meme geste qu'`EPIC11-ARB-75` a fait pour `extract` (`extraction.CODES_DE_SORTIE`),
#: et pour le meme motif : `tui/palier_projet.py` interdit a la TUI d'importer
#: `cli.py`, et l'atelier doit rendre le meme code que la commande.
#:
#: **L'ordre est l'AC, pas une commodite.** `EncoderUnavailableError` et
#: `ProbeUnavailableError` derivent toutes deux de `EncodeError` : placees
#: apres elle, elles rendraient `1` au lieu de `2`. De meme
#: `EncodeVerificationRefused` derive d'`EncodeDecisionError` -- les deux valent
#: `1`, mais l'ordre les garde lisibles dans le sens ou la pile les lisait.
#:
#: **Ce qui n'y figure PAS est aussi une mesure.** `KeyboardInterrupt` et
#: `TerminaisonDemandee` n'y sont pas : elles sont converties en
#: :class:`EncodageInterrompu` par la sequence, qui seule connait la phase.
#: `OSError` nue n'y est pas non plus : seule la sous-classe
#: :class:`ErreurDeDisquePendantEncodage` y figure -- voir son docstring.
CODES_DE_SORTIE: tuple[tuple[type[BaseException], int], ...] = (
    (RefusDOuvertureDuProjet, CODE_ERREUR),
    (EncodageNonConsenti, CODE_REFUS),
    (encode.EncodeVerificationRefused, CODE_ERREUR),
    (encode.EncodeDecisionError, CODE_ERREUR),
    (codec_profiles.EncoderUnavailableError, CODE_PREREQUIS_ABSENT),
    (codec_profiles.ProbeUnavailableError, CODE_PREREQUIS_ABSENT),
    (video_metadata.FfprobeNotFoundError, CODE_PREREQUIS_ABSENT),
    (codec_profiles.EncodeError, CODE_ERREUR),
    (video_metadata.MetadataVerificationError, CODE_ERREUR),
    (NamingError, CODE_ERREUR),
    (ValidationError, CODE_ERREUR),
    (ExtractionPersistenceError, CODE_ERREUR),
    (ErreurDeDisquePendantEncodage, CODE_ERREUR),
)


def code_de_sortie(exc: BaseException) -> int | None:
    """Le code de :data:`CODES_DE_SORTIE`, ou `None` pour une exception hors table.

    `None` et non un code par defaut : une exception hors table est un defaut de
    programmation, et lui donner `1` la deguiserait en refus metier -- ce que
    l'enveloppe d'`extract` a explicitement refuse de faire (`EPIC11-ARB-75`).
    La premiere entree qui correspond gagne, comme une pile d'`except`.
    """
    for famille, code in CODES_DE_SORTIE:
        if isinstance(exc, famille):
            return code
    return None


# ---------------------------------------------------------------------------
# Ce que la sequence rend quand elle aboutit
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MasterDuLot:
    """Ce que l'encodage d'un lot a produit **et** declare.

    Deux objets et rien de recalcule : celui que la story 6.1 rend
    (`EncodeCommandResult` : le plan, l'issue, la description d'encodage, le
    rapport de verification, les constats) et celui que la story 6.5 rend
    (`persist_encode`). Les recomposer ici en ferait deux verites.
    """

    #: `encode.EncodeCommandResult`, verbatim.
    resultat: Any
    #: Ce que `io.encode_manifest.persist_encode` a rendu, verbatim.
    persisted: Any
    #: Le recapitulatif **tel qu'il a ete annonce**, garde pour qu'une interface
    #: puisse le reafficher a l'ecran de resultat sans le recomposer.
    recapitulatif: str


# ---------------------------------------------------------------------------
# Le journal -- une seule recette, celle qui vivait dans `cli`
# ---------------------------------------------------------------------------

def ouvrir_le_journal(project_dir: Path) -> logging.Logger:
    """Logger d'`encode` : `logs/encode.log`, **sans handler console**.

    Deplace de `cli._configure_encode_logger`, qui n'en est plus qu'un relais :
    une interface qui appelle ce module doit obtenir **le meme** journal -- meme
    fichier, meme format -- sans avoir a importer `cli`, ce qui lui est interdit.
    Une seconde recette divergerait au premier reglage change.

    Pas de handler console, contrairement a `extract` et `makepdf` : le
    recapitulatif de l'AC 14 fait une quinzaine de lignes et il est **aussi**
    journalise. Avec un handler console, l'operateur le lisait deux fois -- une
    sur stdout, une sur stderr. La commande possede sa sortie utilisateur, le
    journal possede la trace.
    """
    logger = logging.getLogger(
        f"mixed_media_utility.encode.{project_dir.resolve()}")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    log_path = project_dir / project_layout.LOGS_DIRNAME / "encode.log"
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(file_handler)

    return logger


def _journal(logger: logging.Logger | None) -> logging.Logger:
    """Le journal de la passe, ou celui du module quand l'appelant n'en donne pas.

    Le PARAMETRE ne change aucun comportement observable -- ni le master ecrit,
    ni les exceptions levees, ni le manifest : meme contrat que le `logger` de
    `scan_detect.run_scan_detect` et de `makepdf.generer_les_planches_du_lot`.
    """
    return logger if logger is not None else logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Les gardes d'ouverture -- AVANT tout journal, comme dans le corps d'origine
# ---------------------------------------------------------------------------

def refuser_l_ouverture_du_projet(project_dir: Path) -> Path:
    """Les deux gardes qui precedent **toute** ouverture de journal.

    Elles precedent le journal dans le corps d'origine, et ce n'est pas un
    detail de mise en page : `mmu encode --project <inexistant>` n'a jamais cree
    ni arborescence, ni `logs/encode.log`. Les garder ici, avant
    `ensure_project_layout`, est ce qui preserve cette propriete -- et le
    dossier d'identite la mesure, par l'inventaire du dossier apres refus.

    Rend le chemin du manifest quand les deux gardes passent.
    """
    project_dir = Path(project_dir)
    if not project_dir.is_dir():
        raise RefusDOuvertureDuProjet(
            f"Le dossier projet n'existe pas: {project_dir}. encode opere "
            "sur un projet existant, il n'en cree pas.")
    manifest_path = project_dir / extraction_manifest.MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise RefusDOuvertureDuProjet(
            f"Aucun manifest {extraction_manifest.MANIFEST_FILENAME} dans "
            f"{project_dir}. Le verdict de completude, le registre des mires et "
            "la cadence du lot ne vivent nulle part ailleurs.")
    return manifest_path


# ---------------------------------------------------------------------------
# Le filet de SIGTERM -- il voyage avec la sequence qu'il protege
# ---------------------------------------------------------------------------

class le_signal_tue_l_encodeur:
    """Faire de `SIGTERM` une exception, le temps de l'encodage.

    Deplace de `cli._terminate_kills_the_encoder`, qui n'en est plus qu'un
    alias. Il voyage avec la sequence parce que la promesse qu'il tient est
    celle de la **sequence**, pas celle d'une interface : un atelier de TUI qui
    encoderait sans lui laisserait le meme ffmpeg orphelin.

    Mesure du 2026-08-10, et c'est un defaut a soi seul : un `kill -TERM` sur la
    commande tuait Python et laissait **ffmpeg orphelin** aller jusqu'au bout --
    36 Mo ecrits apres la mort du CLI, sur un master de 44 Mo -- pendant que le
    message annoncait "encodage arrete". L'operateur voyait la main rendue et la
    machine continuait de remplir le disque.

    La cause vit dans la fabrique 6.0 (`subprocess.run` sans groupe de
    processus), la promesse ici. Le geste correct de ce cote de la frontiere :
    transformer le signal en exception dans le thread principal. `subprocess.run`
    tue alors son enfant avant de propager -- c'est son contrat
    (`Popen.__exit__` sur toute `BaseException`) -- et le `finally` de la
    fabrique retire ses temporaires. Aucune ligne de `codec_profiles` n'est
    touchee.

    Le gestionnaire precedent est restaure a la sortie, y compris en cas
    d'erreur : une commande qui rend la main ne laisse pas derriere elle une
    disposition de signal modifiee. En dehors du thread principal,
    `signal.signal` leve `ValueError` : le contexte se degrade alors en no-op
    plutot que de faire echouer un appel de bibliotheque. **C'est exactement le
    regime d'un fil de travail de la TUI**, et le degrader plutot que refuser
    est ce qui rend ce module appelable des deux cotes.
    """

    def __init__(self) -> None:
        self._previous = None
        self._installed = False

    def __enter__(self):
        def _raise(signum, frame):  # pragma: no cover - depend du signal recu
            raise TerminaisonDemandee(f"signal {signum}")

        try:
            self._previous = signal.signal(signal.SIGTERM, _raise)
            self._installed = True
        except (ValueError, OSError):
            self._installed = False
        return self

    def __exit__(self, exc_type, exc, traceback):
        if self._installed:
            with contextlib.suppress(ValueError, OSError):
                signal.signal(signal.SIGTERM, self._previous)
        return False


# ---------------------------------------------------------------------------
# Le point d'entree
# ---------------------------------------------------------------------------

#: L'ensemble **EXACT** des mots-cles que ce module transmet a la decision
#: (`encode.plan_encode`), AC 2.4. Il mesure deux choses a la fois, et la
#: seconde est celle qui compte :
#:
#: * ce qui part **part** -- le lot vise, le profil, la resolution, les deux
#:   consentements structurels (`overwrite`, `accept_incomplete`) et la cadence
#:   source, sans laquelle un lot ne d'une planche 2.0 n'a aucune cadence ;
#: * ce qui **ne part pas** : il n'y a **aucun** mot-cle de nom de master. C'est
#:   `EPIC11-ARB-141` applique -- « on retire l'edition des noms partout ou elle
#:   ne peut pas etre effective » --, et l'ensemble exact est ce qui rend ce
#:   retrait **reversible** : le jour ou `plan_encode` gagnera ce parametre, la
#:   frontiere rougira.
#:
#: Il ne porte pas non plus `ffprobe_bin`, que `plan_encode` accepte : la
#: commande ne l'a jamais passe, donc le deplacement ne le passe pas. Ajouter un
#: mot-cle qu'aucun appelant n'employait aurait ete une reecriture, pas un
#: deplacement.
#: **`nouvelle_version` est entre a la COUTURE des lots B0 et B1** (2026-09-03),
#: et c'est cette frontiere qui l'a fait entrer. Les deux lots ont ete developpes
#: en parallele, chacun dans son worktree : B0 a ajoute `--nouvelle-version` au
#: parser et le mot-cle a `plan_encode` ; B1 a reduit `encode_command` a son
#: enveloppe sur un arbre qui les ignorait encore. La fusion a trois voies n'a
#: leve AUCUN conflit -- les deux lots editent des regions differentes de
#: `cli.py` --, et le resultat passait `nouvelle_version=args.nouvelle_version` a
#: un point d'entree qui ne l'acceptait pas : un `TypeError` sur **tout**
#: `mmu encode`, pas seulement avec l'option. C'est exactement ce que cette
#: frontiere existe pour attraper, et son volet symetrique -- « le banc echoue
#: aussi si un mot-cle DISPARAIT » -- est ce qui la rend capable de le voir.
#: **`reconstruction_visee` entre par la story 6.8** (`EPIC11-ARB-190`), et il
#: entre ICI plutot qu'au parser argparse d'`encode`. Le consommateur vise est
#: l'atelier Exports (story 11.8, ecran 1), qui appelle ce point d'entree -- la
#: TUI a interdiction d'importer `cli`. Ajouter une option a l'`ArgumentParser`
#: ferait diverger deux scenarios du dossier d'identite, qui recopient la ligne
#: `usage:` d'argparse : ce cablage-la se decide a part, avec la regeneration
#: de la reference qu'il coute.
MOTS_CLES_DE_LA_DECISION: frozenset[str] = frozenset({
    "lot_id", "profile_id", "resolution", "overwrite", "nouvelle_version",
    "accept_incomplete", "cadence_source_override", "reconstruction_visee",
})


def encoder_le_master_du_lot(
    project_dir,
    *,
    lot_id,
    profile_id=codec_profiles.DEFAULT_PROFILE_ID,
    resolution=None,
    overwrite=False,
    nouvelle_version=False,
    accept_incomplete=False,
    cadence_source_override=None,
    reconstruction_visee=None,
    logger=None,
    annoncer_le_recapitulatif=None,
    confirmer_l_encodage=None,
    annoncer_le_master=None,
    rappel_progression=None,
) -> MasterDuLot:
    """Decider, encoder, verifier, basculer, declarer -- et **lever** ce qui refuse.

    :param project_dir: le dossier projet ouvert.
    :param lot_id: le `lot_id` canonique du lot a encoder.
    :param profile_id: l'un des sept profils de `codec_profiles.PROFILES`.
    :param resolution: un identifiant du registre, `native`, une resolution
        personnalisee `<largeur>x<hauteur>`, ou `None` pour le defaut.
    :param overwrite: viser le master **existant** au lieu de refuser
        (`EPIC11-ARB-89`).
    :param accept_incomplete: encoder un lot dont le verdict de completude est
        negatif -- un consentement explicite, jamais un defaut.
    :param cadence_source_override: le `--cadence-source` de la CLI, decimal ou
        `'num/den'`, transmis **tel quel** a `resolve_source_rate` (story 6.6,
        AC 1bis). Jamais converti en `float` ici : `8.333333` retombe sur une
        fraction proche mais **differente** de `25/3`.
    :param reconstruction_visee: la passe de scan dont les frames sont encodees
        (story 6.8, `EPIC11-ARB-190`) -- un rang (`int`) ou un
        `output_frames_dir` relatif au projet (`str`). `None` garde le
        comportement d'avant la story : la **derniere** passe, celle que le
        champ scalaire du lot designe. Une passe designee mais absente du
        disque **refuse en la nommant**, sans jamais se rabattre sur une
        autre (`EPIC11-ARB-89`).
    :param logger: journal de la passe. Optionnel : la CLI passe le sien
        (`logs/encode.log`), une interface n'en passe aucun et le journal du
        module suffit. Le PARAMETRE ne change aucun comportement observable.
    :param annoncer_le_recapitulatif: rappel **optionnel** appele avec le
        recapitulatif, **avant** que le consentement soit demande. La CLI y passe
        `print`, une interface y passe son ecran de confirmation. Son absence ne
        change rien a l'observable : le recapitulatif part au journal dans les
        deux cas.
    :param confirmer_l_encodage: rappel **optionnel** rendant `(accorde,
        message)`. `None` vaut **accorde sans question** -- c'est le regime d'une
        interface qui a deja pose la question sur son propre ecran, et c'est le
        seul defaut qui ne bloque pas un appelant sans terminal. La CLI y passe
        son invite `[o/N]`, qui porte le drapeau `--yes`.
    :param annoncer_le_master: rappel **optionnel** appele avec le
        `EncodeCommandResult`, **apres** la bascule et **avant** la declaration
        au manifest. Sa position n'est pas un detail : c'est la seule fenetre ou
        « Master ecrit » doit etre dit meme si la declaration echoue ensuite, et
        c'est exactement ce que la commande faisait.
    :raises RefusDOuvertureDuProjet: dossier projet ou manifest absent.
    :raises EncodageNonConsenti: le rappel de consentement a dit non.
    :raises EncodageInterrompu: `Ctrl-C` ou `SIGTERM`, avec sa **phase**.
    :raises ErreurDeDisquePendantEncodage: le disque a lache pendant l'encodage.

    Les autres refus -- vocabulaire ferme de la story 6.1, encodeur absent,
    ffprobe introuvable, verification technique, nommage, schema, persistance --
    traversent **inchanges** : les deguiser en refus de ce module aplatirait la
    hierarchie que chaque module a construite et perdrait le chainage.

    **L'ordre des gardes n'est pas cosmetique**, et il a voyage tel quel : les
    deux gardes d'ouverture, puis l'arborescence, puis le manifest valide, puis
    la decision, puis le recapitulatif, puis le consentement -- et `outputs/`
    n'est cree qu'**apres** l'accord. « Un refus qui arrive apres une
    destruction n'est pas un refus. »
    """
    project_dir = Path(project_dir)
    manifest_path = refuser_l_ouverture_du_projet(project_dir)

    project_layout.ensure_project_layout(project_dir)
    logger = _journal(logger)

    # -- phase 1 : la decision, avant le moindre octet ------------------------
    try:
        manifest = validate_manifest(manifest_path)
        plan = encode.plan_encode(
            project_dir,
            manifest,
            lot_id=lot_id,
            profile_id=profile_id,
            resolution=resolution,
            overwrite=overwrite,
            nouvelle_version=nouvelle_version,
            accept_incomplete=accept_incomplete,
            cadence_source_override=cadence_source_override,
            reconstruction_visee=reconstruction_visee,
        )
    except KeyboardInterrupt:
        raise EncodageInterrompu(
            f"\n{encode.ENCODE_KEYBOARD_INTERRUPT}: rien n'a ete encode.",
            phase="decision") from None

    recapitulatif = encode.render_summary(plan)
    if annoncer_le_recapitulatif is not None:
        annoncer_le_recapitulatif(recapitulatif)
    for ligne in recapitulatif.splitlines():
        logger.info(ligne)

    # -- le consentement -- rien n'a encore ete ecrit -------------------------
    if confirmer_l_encodage is not None:
        accorde, message = confirmer_l_encodage()
        if not accorde:
            logger.warning(message)
            raise EncodageNonConsenti(message)

    # -- phase 2 : l'encodage -------------------------------------------------
    try:
        # `outputs/` n'est cree qu'ici: un refus en amont ne laisse derriere lui
        # ni fichier ni dossier de sortie -- `ensure_project_layout` a en
        # revanche deja cree `logs/`, `planches/` et `scans/` plus haut, ce qui
        # est vrai de toutes les sous-commandes du depot.
        swept = encode.prepare_output_directory(plan)
        for chemin in swept:
            logger.info("Residu d'encodage balaye: %s", chemin)
        with le_signal_tue_l_encodeur():
            resultat = encode.execute_plan(
                plan, swept=swept, rappel_progression=rappel_progression)
    except (KeyboardInterrupt, TerminaisonDemandee) as exc:
        # Le constat porte un code du vocabulaire ferme, comme tous les autres:
        # `INTERRUPTION_CLAVIER` etait declare et n'etait leve nulle part, ce qui
        # est du vocabulaire mort et non un contrat tenu.
        par_signal = isinstance(exc, TerminaisonDemandee)
        code = (encode.ENCODE_TERMINATION_REQUESTED if par_signal
                else encode.ENCODE_KEYBOARD_INTERRUPT)
        origine = "Arret demande (SIGTERM)" if par_signal else "Interruption clavier"
        message = (
            f"\n{code}: {origine}, encodage arrete et encodeur tue avec lui. Le "
            "master precedent est intact et aucun master neuf n'a ete pose. Un "
            f"fichier d'attente peut subsister dans {plan.output_path.parent} (nom "
            "cache, prefixe par un point); il n'est balaye qu'au-dela de 24 h, "
            "donc le retirer a la main est plus rapide que d'attendre.")
        logger.warning(message.strip())
        raise EncodageInterrompu(message, phase="encodage",
                                 par_signal=par_signal) from None
    except OSError as exc:
        raise ErreurDeDisquePendantEncodage(
            f"Erreur d'acces disque pendant l'encodage: {exc}. Verifier "
            "l'espace disponible et les droits d'ecriture sur le dossier projet."
        ) from exc

    logger.info("Master ecrit: %s", resultat.outcome.output_path)
    if annoncer_le_master is not None:
        annoncer_le_master(resultat)

    # -- phase 3 : la declaration au manifest (story 6.5) ---------------------
    #
    # Et rien d'autre. Le master existe deja a son chemin final; un echec ici ne
    # le retire pas.
    try:
        # **Le contexte de signal couvre AUSSI la persistance**, et c'est une
        # asymetrie fermee plutot qu'un elargissement de confort. Juste en
        # dessous, `KeyboardInterrupt` pendant cette meme phase rend un constat
        # nomme -- manifeste intact, master ecrit et non declare. `SIGTERM` a
        # la meme milliseconde ne rendait RIEN : le gestionnaire etait deja
        # restaure au defaut a la sortie du bloc d'encodage, donc le signal
        # tuait le process net, sans message et sans entree de journal. Deux
        # fenetres de meme nature, une seule tenue, et le contrat `:raises` du
        # module annoncait les deux.
        #
        # Le nom du contexte parle de l'encodeur parce que c'est ce qu'il tue
        # PENDANT l'encodage ; ici il n'y a plus d'enfant a tuer, et ce qu'il
        # tient est l'autre moitie de sa promesse -- faire du signal une
        # exception, pour que la phase puisse dire ce qu'elle laisse.
        with le_signal_tue_l_encodeur():
            persisted = encode_manifest.persist_encode(
                project_dir,
                encode_manifest.EncodeRecord.from_command_result(resultat))
    except ExtractionPersistenceError as exc:
        # Le chemin du master voyage **sur l'exception**, comme `pdf_path` sur
        # celle de `makepdf` : l'enveloppe ne l'a plus en main sur ce chemin, et
        # le recomposer serait re-deriver une convention qu'`io.naming` possede.
        exc.master_path = Path(resultat.outcome.output_path)
        raise
    except (KeyboardInterrupt, TerminaisonDemandee) as exc:
        # Seul point du chemin `encode` qui rendait une trace Python nue, alors
        # que cette commande annonce elle-meme un contrat `130`. La fenetre est
        # courte (quelques kilo-octets ecrits) mais elle est reelle, et ce
        # qu'elle laisse derriere elle est exactement ce qu'il faut dire: le
        # `project.json` est intact, le master est ecrit et **non declare**.
        #
        # Les DEUX origines sont rattrapees ici, et le constat dit laquelle:
        # l'operateur qui lit `INTERRUPTION_CLAVIER` apres un `kill -TERM`
        # chercherait un clavier que personne n'a touche. C'est la meme
        # discrimination que la phase d'encodage fait dix lignes plus haut.
        par_signal = isinstance(exc, TerminaisonDemandee)
        code = (encode.ENCODE_TERMINATION_REQUESTED if par_signal
                else encode.ENCODE_KEYBOARD_INTERRUPT)
        origine = ("arret demande (SIGTERM)" if par_signal
                   else "interruption clavier")
        message = (
            f"\n{code}: {origine} "
            "pendant l'ecriture du manifest. Le "
            f"{extraction_manifest.MANIFEST_FILENAME} est intact et sans "
            "temporaire residuel, mais le master est ecrit et n'est **pas** "
            f"declare: {resultat.outcome.output_path}. Reprise: relancer la meme "
            "commande avec --overwrite.")
        logger.warning(message.strip())
        raise EncodageInterrompu(message, phase="persistance",
                                 par_signal=par_signal) from None

    logger.info(
        "Manifest mis a jour: %s (lot %s, master %s)",
        persisted.manifest_path, persisted.lot_id, persisted.master_path)
    return MasterDuLot(resultat=resultat, persisted=persisted,
                       recapitulatif=recapitulatif)
