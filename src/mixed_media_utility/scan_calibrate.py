# -*- coding: utf-8 -*-
"""Calibrer une chaine de scan -- le geste `scan ... calibrate`, au coeur.

Story 11.6, lot B (`EPIC11-ARB-129`). Ce module porte le corps que
`cli.scan_calibrate_command` et `cli._consigner_le_profil_de_chaine`
orchestraient jusqu'ici : ingestion, detection, derive de l'identite de chaine,
ajustement de la page de calibration, ecriture du profil.

**Pourquoi il existe.** `scan_detect` est la moitie amont du scan, `scan_write`
la moitie aval : les deux ont fait ce voyage hors de `cli.py` pour une raison
qui vaut mot pour mot ici -- une interface branchee sur `cli.py` recevrait des
lignes imprimees sur `stderr` **sous** l'ecran dessine, et un entier la ou elle
a besoin d'un profil ecrit ou d'un refus nomme (`tui/palier_projet.py:9-12`).
`calibrate` etait le dernier geste de la chaine de scan a n'avoir aucun point
d'entree de coeur, alors que la TUI le sert **depuis le menu d'atelier**
(`EPIC11-ARB-28`).

**Le contrat de ce module, en une phrase** : il ne met en forme aucun message
de terminal et ne rend aucun code de retour -- il **leve** ses refus, nommes, et
rend un :class:`ProfilDeChaineConsigne` sur le chemin qui aboutit.
`cli.scan_calibrate_command` et `cli._consigner_le_profil_de_chaine` en
deviennent des **enveloppeurs** : memes codes de sortie, memes messages
imprimes, memes artefacts.

**Il ne lit JAMAIS `stdin`.** Les deux decisions qui se posaient a un humain --
nommer le profil, ecraser un homonyme -- entrent par des parametres nommes :
`demander_le_nom_et_le_commentaire` et `confirmer_l_ecrasement`. Sous
`textual`, `stdin` appartient a la boucle d'evenements et un appel bloquant y
gele l'interface entiere (`EPIC7-ARB-106`).

Ce module est du **coeur** : il n'importe ni `cli`, ni `gui/`, ni `tui/`.
"""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass
from pathlib import Path

from . import (
    color_calibration,
    scan_chain,
    scan_detection,
    scan_ingest,
    scan_write,
)
from .io import (calibration_profile, payload as payload_io,
                 profile_designation, reconstruction)

#: Nom de la sous-commande qui consigne un profil de chaine, tel qu'un message
#: la cite a l'operateur (`scan ... calibrate`).
#:
#: **La valeur vit ici depuis la story 11.6 (lot B)**, et `cli.py` la lit --
#: meme motif que `scan_write.CC_FLAG` (`EPIC11-ARB-75`) : les refus du coeur y
#: renvoient l'operateur, et le coeur ne peut pas importer `cli.py`.
SCAN_CALIBRATE_SUBCOMMAND = 'calibrate'

#: L'ajustement de la page de calibration, **alias et jamais copie** de
#: `scan_write._fit_lot_correction` : c'est le meme geste que le scan applique a
#: la page qu'il trouve dans sa pile, et deux ajustements ecrits separement
#: divergeraient -- la chaine porterait alors une correction ajustee sur une
#: geometrie qui n'est pas celle des lots qui la reutiliseront.
#:
#: Le nom local existe parce que c'est **le point de substitution des bancs**:
#: l'ajustement lui-meme est eprouve contre les vrais producteurs dans les
#: fichiers de la moitie couleur, et les bancs de `calibrate` le substituent
#: pour n'y mesurer que l'orchestration. Il vivait dans `cli.py` jusqu'a la
#: story 11.6 (lot B), avec le corps qu'il sert.
_fit_lot_correction = scan_write._fit_lot_correction

#: Les pages de calibration **lues et redressables** d'une detection, **alias et
#: jamais copie** de `scan_write._read_calibration_pages` : c'est la fonction
#: que :data:`_fit_lot_correction` emploie lui-meme pour choisir la feuille sur
#: laquelle il ajuste. Le libelle de chaine se lit donc sur **exactement** la
#: page qui a produit la correction -- une seconde selection ecrite ici
#: nommerait un jour le profil d'apres une feuille que l'ajustement n'a pas
#: retenue.
_read_calibration_pages = scan_write._read_calibration_pages

#: **Les motifs de refus de la calibration, ensemble FERME et ORDONNE** (story
#: 11.6, lot B).
#:
#: Ils nomment les cinq facons dont `calibrate` refuse, **et aucun profil n'est
#: ecrit dans aucune des cinq** : « `calibrate` n'a rien d'autre a faire que
#: consigner un profil, et un profil sans identite ne serait retrouve par
#: personne [...] elle **ne se replie pas sur un profil vide** ».
#:
#: L'ordre du tuple est l'ordre des gardes -- identite, page absente, page
#: inexploitable, echec d'ecriture --, et il est mesure comme tel. Un refus qui
#: arrive apres une ecriture n'est pas un refus.
#:
#: **Un cinquieme refus n'y est PAS, et c'est delibere** : l'ajustement de la
#: page refuse par `scan_ingest.ScanIngestError`, l'exception que le coeur leve
#: deja partout ailleurs sur cette chaine. Lui donner un motif a lui ferait deux
#: noms pour un seul refus ; elle est dans :data:`CODES_DE_SORTIE`, ou un
#: appelant la nomme comme il nomme les autres refus du coeur.
#:
#: **Pourquoi une table publiee et pas seulement des exceptions.** C'est la
#: dette que le lot C de la 11.5 a payee sur la detection : `scan_detect` ne
#: publie aucune table, donc la TUI a du rediger une seconde copie du
#: vocabulaire (`deferred-work.md`). Ici la table **est** l'interface : un
#: appelant nomme un refus en comparant `motif` a l'une de ces constantes,
#: jamais en relisant la phrase.
REFUS_IDENTITE_NON_DERIVABLE = "identite-non-derivable"
REFUS_AUCUNE_PAGE_DE_CALIBRATION = "aucune-page-de-calibration"
REFUS_PAGE_INEXPLOITABLE = "page-de-calibration-inexploitable"
REFUS_PROFIL_NON_ECRIT = "profil-non-ecrit"

#: `EPIC11-ARB-266` (Egan, 2026-09-07) : la pile de calibration porte AUSSI des
#: planches d'images. Le parcours `scan` refuse deja cette pile sous ce nom
#: (`reconstruction.REFUS_PILE_SANS_PLANCHE` et `REFUS_PILE_MIXTE`, deux passes
#: separees etant le regime nominal depuis `EPIC5-ARB-86`) ; le parcours
#: `calibrate`, lui, l'acceptait -- il calibrait, n'ecrivait aucune frame, et
#: declarait le dossier de scan ENTIER, si bien que les planches qui
#: accompagnaient la mire perdaient leur mention « non declare ».
REFUS_PILE_MIXTE_EN_CALIBRATION = "pile-mixte-en-calibration"

MOTIFS_DE_REFUS_DE_CALIBRATION: tuple[str, ...] = (
    REFUS_IDENTITE_NON_DERIVABLE,
    REFUS_AUCUNE_PAGE_DE_CALIBRATION,
    REFUS_PAGE_INEXPLOITABLE,
    REFUS_PROFIL_NON_ECRIT,
    REFUS_PILE_MIXTE_EN_CALIBRATION,
)


class RefusDeCalibration(ValueError):
    """Un refus **nomme** de `calibrate` : aucun profil n'a ete ecrit.

    Elle porte son :attr:`motif` -- l'une des constantes de
    :data:`MOTIFS_DE_REFUS_DE_CALIBRATION` -- **a cote** de son message. Les
    deux ne se remplacent pas : le message est ce qu'un terminal imprime mot
    pour mot (`Erreur: <message>`, comme avant l'extraction), le motif est ce
    qu'une interface teste sans lire de phrase.

    **Le message est POSITIONNEL, le motif est NOMME et facultatif**, comme
    `scan_write.RefusDuDocumentDeDetection` et pour le meme motif : une
    exception d'une table de codes de sortie doit rester constructible avec son
    seul message, sans quoi les parcours qui balaient la table entiere -- ceux
    qui ferment les familles qu'aucun refus reel n'atteint -- ne peuvent plus
    l'instancier.
    """

    def __init__(self, message: str, *, motif: str | None = None):
        super().__init__(message)
        #: L'un de :data:`MOTIFS_DE_REFUS_DE_CALIBRATION`, ou `None` pour une
        #: instance fabriquee hors de ce module.
        self.motif = motif


#: Les refus que ce module leve et que ses enveloppeurs convertissent -- **tous
#: au meme code de sortie `1` et au meme prefixe `Erreur: `**.
#:
#: Meme forme et meme motif que `scan_write.CODES_DE_SORTIE` : la TUI doit
#: rendre le meme verdict que la CLI et a interdiction d'importer `cli.py`.
#:
#: `scan_ingest.ScanIngestError` y figure deux fois par le fait : l'ingestion la
#: leve, et l'ajustement de la page de calibration aussi. Les deux vont au meme
#: code, et chacune a deja dit sa phase au journal la ou elle est tombee.
CODE_SUCCES = 0
CODE_ERREUR = 1

CODES_DE_SORTIE: tuple[tuple[type[BaseException], int], ...] = (
    (RefusDeCalibration, CODE_ERREUR),
    (scan_ingest.ScanIngestError, CODE_ERREUR),
    (scan_detection.ScanDetectionError, CODE_ERREUR),
)


def code_de_sortie(exception: BaseException) -> int | None:
    """Le code de sortie de `calibrate` pour `exception`, ou `None` si inconnue.

    `None` veut dire « la table ne nomme pas cette exception » : l'appelant la
    **relaie** au lieu de la deguiser en refus metier -- un bug de
    programmation ne sort pas en code d'erreur ordinaire.
    """
    for classe, code in CODES_DE_SORTIE:
        if isinstance(exception, classe):
            return code
    return None


@dataclass(frozen=True)
class ProfilDeChaineConsigne:
    """Ce qu'une passe de calibration a **reellement** produit.

    Aucun champ n'est une phrase : la redaction du compte rendu appartient a
    l'appelant, exactement comme `ScanDetectOutcome` et `EcritureDuLot`.
    """

    #: Le chemin du fichier de profil ecrit, verbatim.
    profile_path: Path
    #: L'identite de chaine **derivee** des parametres reels du scan.
    chain_id: str
    #: L'etiquette donnee par l'operateur, `""` quand il n'en a pas donne.
    etiquette: str
    #: Le commentaire donne par l'operateur, `""` quand il n'en a pas donne.
    commentaire: str
    #: La correction ajustee sur la page de calibration lue, verbatim : c'est
    #: elle qui porte les cardinaux de pastilles, la provenance et les temoins.
    lot_correction: object
    #: Le document de profil tel qu'il a ete ecrit.
    document: object
    #: Le rapport d'ingestion de la passe, ou `None` quand l'appelant l'avait
    #: deja (chemin :func:`consigner_le_profil_de_chaine`).
    report: object | None = None
    #: Les AUTRES fichiers de profil que cette chaine porte, releves **apres**
    #: l'ecriture et prive de celui qu'on vient d'ecrire. C'est le fait
    #: d'`EPIC11-ARB-261` : une liste non vide dit que la chaine etait deja
    #: calibree sous un autre libelle, donc que la passe vient de creer un
    #: SECOND fichier. Le coeur ne decide rien -- il rend, et les deux
    #: interfaces avertissent et proposent les deux issues.
    autres_profils: tuple[Path, ...] = ()


def derive_chain_id(report, scan_locator, logger=None):
    """L'identite de la chaine de scan de ce rapport d'ingestion. Story 5.22, AC 4.

    L'identite est **derivee** des parametres reels du scan -- dpi declare, format
    mesure, tags scanner en best effort -- de facon deterministe et inter-machine
    (`scan_chain`). C'est la **seule** source de cette identite depuis la story 5.23
    (AC 13, `EPIC5-ARB-88`): le parametre `override`, qui portait le drapeau de
    surcharge a la main, a ete retire avec lui. Depuis `EPIC5-ARB-83` le `chain_id` ne
    sert plus a **apparier** un profil -- l'operateur designe le profil lui-meme --,
    donc le surcharger ne rattrapait plus aucune panne; il nomme, et une derivation
    deterministe nomme mieux qu'un slug saisi deux fois de deux facons.

    Rend `None` quand la derive est impossible (rapport sans page), apres l'avoir dit:
    ce n'est pas un motif d'echec de commande, c'est un lot qui sera livre en brut.
    """
    logger = logger or logging.getLogger(__name__)
    make, model, software = scan_chain.read_scan_tags(scan_locator)
    try:
        return scan_chain.derive_chain_id(
            declared_dpi=report.declared_dpi,
            scan_input_format=scan_chain.report_scan_input_format(report),
            make=make, model=model, software=software,
        )
    except scan_chain.InvalidChainParameterError as exc:
        # **Le message ne parle plus de resolution** (story 5.23, AC 12): depuis
        # `EPIC5-ARB-83` aucun profil n'est resolu par cette identite, et la seule
        # commande qui l'appelle encore -- `scan calibrate` -- s'en sert pour **nommer**
        # le fichier qu'elle produit. Annoncer une resolution empechee enverrait
        # l'operateur chercher un appariement qui n'existe plus.
        logger.warning(
            "Identite de chaine non derivable (%s): le profil de cette chaine ne peut "
            "pas etre nomme.", exc)
        return None


def libelle_de_chaine_du_scan(detection) -> str:
    """Le `scan_chain_label` que porte la page de calibration LUE, ou `""`.

    **Le libelle est dans le QR, obligatoirement** : `io.payload` le range dans
    `CALIBRATION_ONLY_FIELDS` et **refuse** une page de calibration qui ne le
    porte pas (`EPIC5-ARB-90`, aucune tolerance). C'est le nom que l'atelier PDF
    a fait saisir sous le libelle « Nom de la chaine », champ requis, et c'est
    donc **ce que l'operateur s'attend a retrouver** sur le profil que sa
    feuille produit.

    Il etait decode et jamais lu (retour terrain d'Egan, 2026-09-06 : « sans
    renseigner de nom, le nom de la chaine stocke dans le QR ne remplace pas le
    nom, qui est alors celui du pdf »). Mesure sur le scan reel qu'il a fourni
    (`hp_envy_gambetta.pdf`, 300 dpi) : le QR rend
    `scan_chain_label = 'hp envy Gambetta'` pendant que le profil s'appelait
    `HP envy Gambetta.pdf`, c'est-a-dire le nom du fichier -- les deux chaines
    different par la casse ET par l'extension, ce qui **prouve** que la valeur
    affichee ne venait pas de la feuille.

    **La valeur est rendue verbatim** : ni `strip`, ni `title`, ni
    `capitalize`. Ce que la feuille porte est ce que le profil doit porter, et
    une normalisation cosmetique ferait diverger le nom du profil du nom
    imprime sur la page.

    Rend `""` -- donc « rien a dire » et jamais une valeur inventee -- des que
    la detection ne porte pas exactement une page de calibration lisible : le
    chemin qui appelle cette fonction a deja refuse les deux autres cas
    (aucune page, page inexploitable), et le repli garde le troisieme terme de
    la precedence atteignable.
    """
    pages = _read_calibration_pages(detection)
    if len(pages) != 1:
        return ""
    payload = getattr(pages[0], "payload", None) or {}
    valeur = payload.get(payload_io.SCAN_CHAIN_LABEL_FIELD)
    return valeur if isinstance(valeur, str) else ""


def etiquette_du_profil(saisie: str, detection, chain_id: str,
                        logger=None) -> str:
    """La precedence du nom d'un profil : **saisie -> libelle du QR -> `chain_id`**.

    Une seule redaction pour les **trois** appelants du corps
    (:func:`calibrer_la_chaine`, la bascule de `scan`, et le tri en vrac), parce
    que « aucune des voies ne peut ecrire un profil que l'autre n'ecrirait pas »
    est l'invariant de ce module depuis `EPIC5-ARB-92`.

    Les trois termes, et ce que chacun vaut :

    * **la saisie de l'operateur** l'emporte toujours : il vient de nommer, et
      un libelle imprime il y a trois semaines ne doit pas le contredire ;
    * **le libelle du QR** est le terme neuf (2026-09-06). Il est present et non
      vide par contrat, donc c'est lui qui sert en regime nominal ;
    * **le `chain_id`** ne sert plus qu'aux feuilles anterieures a
      `scan_chain_label`, et il reste ce que `profile_file_stem` prend
      lui-meme quand l'etiquette est vide -- rendre `""` ici **est** ce
      troisieme terme, il n'a pas a etre recopie.

    **Le libelle du QR n'est retenu que s'il peut NOMMER un fichier**, et ce
    n'est pas du zele : `payload.validate_scan_chain_label` accepte de la prose
    (« seules les longueurs et le vide sont refuses ») la ou
    `calibration_profile.slugify_label` refuse tout ce qui n'est pas lettre,
    chiffre, espace, tiret ou souligne. Sans cette garde, une feuille nommee
    « hp envy 4520 (bureau) » ferait **refuser la calibration entiere** --
    `write_profile` levant -- alors qu'elle aboutissait avant. Un nom qu'on ne
    peut pas porter se dit au journal et se replie sur le `chain_id` ; il
    n'arrete rien. La saisie de l'operateur, elle, n'a pas cette garde et n'en
    veut pas : il a demande ce nom-la, le refus nomme lui appartient.

    La regle du nommage n'est pas reecrite ici : c'est `slugify_label` qui est
    **interrogee**, une seule autorite et pas deux.
    """
    logger = logger or logging.getLogger(__name__)
    saisie = saisie or ""
    if saisie.strip():
        return saisie
    libelle = libelle_de_chaine_du_scan(detection)
    if not libelle.strip():
        return ""
    try:
        calibration_profile.slugify_label(libelle)
    except calibration_profile.ProfileValidationError as exc:
        logger.warning(
            "Le libelle de chaine lu sur la page de calibration (%r) ne peut "
            "pas nommer un fichier (%s): le profil prend le nom de son "
            "identite de chaine '%s'. Renommez la chaine sur la page puis "
            "reimprimez-la si ce nom est voulu.", libelle, exc, chain_id)
        return ""
    return libelle


def consigner_le_profil_de_chaine(project_dir, report, detection, *, dpi,
                                  scan_locator, logger=None,
                                  demander_le_nom_et_le_commentaire=None,
                                  confirmer_l_ecrasement=None
                                  ) -> ProfilDeChaineConsigne:
    """Ajuster la page de calibration lue et consigner le profil de la chaine.

    Story 11.6, lot B : corps **deplace** de `cli._consigner_le_profil_de_chaine`,
    jamais reecrit -- meme geste que la 11.4b a fait pour la moitie aval du
    scan. Ce qui a change, et rien d'autre : l'objet `args` argparse est devenu
    des parametres nommes, les quatre `print(..., file=sys.stderr)` sont devenus
    des `raise`, l'invite de nommage est devenue un rappel, et le code de sortie
    est devenu un :class:`ProfilDeChaineConsigne`.

    Il a **deux appelants de coeur** depuis `EPIC5-ARB-92`, et c'est ce qui rend
    la bascule fidele : la sous-commande explicite (:func:`calibrer_la_chaine`),
    et la bascule que `scan` propose quand la pile ne porte que des pages de
    calibration. Aucune des deux ne peut ecrire un profil que l'autre
    n'ecrirait pas.

    Ce que l'extraction ne fait pas : re-ingerer ni re-detecter. La bascule est
    proposee apres l'ingestion et la detection de `scan`, qui sont exactement
    les memes gestes.

    :param scan_locator: ce qui a ete scanne, tel que `scan_chain.read_scan_tags`
        l'accepte -- l'identite de chaine s'en derive.
    :param demander_le_nom_et_le_commentaire: rappel **optionnel** appele avec
        le `chain_id` et rendant `(etiquette, commentaire)`. Il est appele
        **ici et pas plus haut** : tous les refus sont derriere, donc on ne
        demande jamais a l'operateur de nommer un profil qui ne sera pas ecrit.
        Son absence vaut `("", "")` -- le profil prend alors le nom de son
        `chain_id`, c'est-a-dire exactement ce que 5.22 ecrivait.
    :param confirmer_l_ecrasement: rappel **optionnel** transmis verbatim a
        `calibration_profile.write_profile`. Ce module ne lit jamais `stdin`.
    :raises RefusDeCalibration: identite non derivable, page absente, page
        inexploitable, ou profil non ecrit.
    :raises scan_ingest.ScanIngestError: l'ajustement a refuse la page.
    """
    logger = logger or logging.getLogger(__name__)
    project_dir = Path(project_dir)
    # L'identite de la chaine se **derive** des parametres reels du scan
    # (dpi declare, format mesure, tags scanner en best effort), et **rien d'autre**
    # depuis la story 5.23 (AC 13). Elle ne descend jamais d'un slug operateur.
    #
    # **La derive passe par `derive_chain_id`, exactement comme au scan**, et c'est la
    # seule forme correcte: cette commande **ecrit** le profil sous cette identite et
    # `scan_command` le **relit** sous la sienne. Deux redactions de la meme recette
    # divergeraient un jour, et le symptome serait un profil que plus aucun scan ne
    # retrouve -- c'est-a-dire la panne meme que cette story existe pour supprimer.
    chain_id = derive_chain_id(report, scan_locator, logger)
    if chain_id is None:
        # A la difference de `scan`, une identite non derivable est ici un **echec**:
        # `calibrate` n'a rien d'autre a faire que consigner un profil, et un profil
        # sans identite ne serait retrouve par personne. `derive_chain_id` a deja dit
        # pourquoi au journal.
        # **Aucun geste de nommage manuel n'est plus propose** (story 5.23, AC 13): le
        # drapeau qui nommait la chaine a la main n'existe plus, et le citer enverrait
        # vers une option inexistante. Ce qui manque ici est un scan dont on puisse
        # derive l'identite -- une page, un dpi declare --, pas un nom.
        raise RefusDeCalibration(
            "l'identite de la chaine n'a pas pu etre derivee de ce scan. "
            "Verifiez que le dossier de scan porte au moins une page lisible et que "
            "--dpi declare la resolution reelle.",
            motif=REFUS_IDENTITE_NON_DERIVABLE)

    # Meme chemin que `scan` pour ajuster la correction de la page de calibration
    # (deteuner le raster, redresser, ajuster): deux ajustements ecrits separement
    # divergeraient, et la chaine porterait alors une correction ajustee sur une
    # geometrie qui n'est pas celle des lots qui la reutiliseront.
    try:
        lot_correction = _fit_lot_correction(project_dir, detection, dpi)
    except scan_ingest.ScanIngestError as exc:
        logger.error("Refus de calibration: %s", exc)
        raise

    if lot_correction is None:
        logger.error(
            "Aucune page de calibration lue dans ce scan: rien a ajuster pour "
            "la chaine '%s'. La commande `calibrate` est explicite, elle ne se "
            "replie pas sur un profil vide.",
            chain_id,
        )
        raise RefusDeCalibration(
            "aucune page de calibration lue dans ce scan. Scannez la "
            "page de calibration de la chaine, puis relancez.",
            motif=REFUS_AUCUNE_PAGE_DE_CALIBRATION)
    if not lot_correction.available:
        logger.error(
            "Page de calibration inexploitable (%s): %s",
            lot_correction.failure_reason,
            lot_correction.failure_message,
        )
        raise RefusDeCalibration(lot_correction.failure_message,
                                 motif=REFUS_PAGE_INEXPLOITABLE)

    # Le profil porte tout ce qu'une relecture a besoin, sans rien attendre du
    # manifest (AC 1): identite de chaine, forme, coefficients, cardinaux du jeu,
    # politique de plancher d'encrage et provenance de la page qui l'a ajustee.
    #
    # La politique de plancher se lit sur la forme **du profil** (celle qui a
    # ajuste les coefficients), jamais sur `lot_correction.correction_form_id`,
    # qui repond a "sous quelle forme ce lot devait etre corrige": si les deux
    # divergeaient, le fichier porterait une politique appliquee a des
    # coefficients ajustes sous une autre.
    # **L'operateur nomme ce qu'il produit** (AC 8quater). La question est posee ici et
    # pas plus haut: tous les refus de la commande sont derriere nous, donc on ne
    # demande jamais a l'operateur de nommer un profil qui ne sera pas ecrit.
    if demander_le_nom_et_le_commentaire is None:
        etiquette, commentaire = "", ""
    else:
        etiquette, commentaire = demander_le_nom_et_le_commentaire(chain_id)
    # **Le libelle que la FEUILLE porte prend le relais d'une saisie vide**
    # (2026-09-06). La precedence entiere -- saisie, puis QR, puis `chain_id` --
    # vit dans :func:`etiquette_du_profil` et **une seule fois** : les deux
    # appelants de ce corps l'obtiennent donc identique, ce qui est exactement
    # ce qu'`EPIC5-ARB-92` exige de lui. Le troisieme terme n'est pas ecrit
    # ici : une etiquette vide est deja ce que `profile_file_stem` replie sur
    # le `chain_id`.
    etiquette = etiquette_du_profil(etiquette, detection, chain_id, logger)
    document = color_calibration.profile_to_document(
        lot_correction.profile,
        chain_id=chain_id,
        source_page_id=lot_correction.source_page_id,
        template_id=lot_correction.template_id,
        read_patch_count=lot_correction.read_patch_count,
        retained_patch_count=lot_correction.retained_patch_count,
        ink_floor_excluded=color_calibration.correction_form_excludes_ink_floor(
            lot_correction.profile.correction_id),
        acceptance=lot_correction.acceptance,
        # **Les temoins de la page, mesures BRUTS, consignes dans le profil** (story
        # 5.23, correction du 2026-08-18). Sans eux, le profil n'a rien a opposer aux
        # temoins d'une planche scannee plus tard, et la divergence brute a brute
        # d'`EPIC5-ARB-82` ne se calcule que dans la passe qui a lu la feuille --
        # c'est-a-dire jamais, la calibration par chaine existant precisement pour que
        # cette feuille ne soit scannee qu'une fois.
        witness_raw_bgr=lot_correction.witness_raw_bgr,
        # **Le motif voyage avec la mesure** (`EPIC5-ARB-104`). Sans cette ligne, le
        # second etage du defaut n'etait ferme qu'**en memoire**: la mesure du bandeau
        # distinguait bien ses cinq regimes, mais le profil ecrit ne portait que le
        # vide, si bien qu'apres relecture une chaine dont la page **a ete lue** --
        # bandeau imprime puis rogne au redressage -- ressortait
        # `raw_divergence_no_calibration_sheet`, c'est-a-dire « aucune feuille de
        # calibration ». C'est la faussete **persistee** que la revue a trouvee, et
        # elle survivait a la correction du premier etage.
        witness_band_reason=lot_correction.witness_band_reason,
        # **Le dossier de scan dont ce profil est issu** (`EPIC11-ARB-262`). Egan,
        # verbatim le 2026-09-06 : « Le scan de la page de calibration apparait en non
        # declare alors que je l'ai importe au projet. » Il l'etait parce que RIEN sur
        # le disque ne reconnaissait une mire -- ni le manifeste, que ce parcours ne
        # touche pas, ni le dossier de scan, qui ne porte que la copie du raster, ni le
        # profil. L'inventaire montrait donc un faux orphelin PERMANENT : une mire
        # n'est jamais reconstruite en lot, sa filiation n'est pas *differee* comme
        # celle d'un lot de planches, elle etait *inexistante*.
        #
        # La valeur est celle du rapport d'ingestion, **relative POSIX au projet**
        # (`scan_ingest._relative_to_project`) : elle n'est ni recomposee ici, ni
        # devinee du nom de la source -- le slug reellement employe est le seul que
        # l'inventaire retrouvera.
        #
        # **Ce que ca ne repare pas** : les projets DEJA calibres. Le champ s'ecrit a
        # la calibration ; rien ne relie retroactivement un dossier de scan a un profil
        # ecrit avant lui. Un projet existant garde son faux orphelin jusqu'a une
        # recalibration -- et le dire vaut mieux que laisser croire qu'une mise a jour
        # suffit.
        scan_dir=report.scans_dir,
        # L'etiquette **nomme le fichier**, le commentaire ne sert qu'a se relire au
        # survol (Epic 7). Ni l'un ni l'autre ne remplace quoi que ce soit du document:
        # le `chain_id`, la forme, les coefficients, les cardinaux, la provenance et
        # les temoins bruts sont ecrits a l'identique.
        label=etiquette,
        comment=commentaire,
    )
    try:
        profile_path = calibration_profile.write_profile(
            project_dir, document, confirm_overwrite=confirmer_l_ecrasement)
    except (calibration_profile.ProfileReadError, OSError) as exc:
        # **Les trois familles d'echec d'ecriture, et pas seulement la validation**
        # (revue 5.22). `write_profile` refuse le document (`ProfileValidationError`),
        # mais il echoue aussi a l'ecriture atomique (`ProfileReadError`: disque plein,
        # `os.replace` impossible) et au `mkdir` du dossier `versions/calibration/`
        # (`OSError` nue: dossier en lecture seule). Seule la premiere etait rattrapee,
        # donc les deux autres sortaient en **traceback** la ou la commande doit rendre
        # un refus nomme et le code 1 -- et un traceback ne dit pas a l'operateur que
        # son profil precedent est intact, ce que l'ecriture atomique garantit pourtant.
        #
        # `ProfileValidationError` derive de `ProfileReadError`: la nommer en plus
        # serait redondant, et la retirer ne desserre rien.
        #
        # **Le refus est renomme, jamais relaye tel quel** (story 11.6, lot B): une
        # `OSError` qui remonterait nue serait attrapee par la garde `AR2` de la
        # commande appelante et reformulee en « erreur d'acces disque pendant scan »,
        # ce qui n'est pas ce que l'operateur lisait avant l'extraction. Le message
        # reste celui de l'exception d'origine, mot pour mot.
        logger.error("Profil non ecrit pour la chaine '%s': %s", chain_id, exc)
        raise RefusDeCalibration(str(exc), motif=REFUS_PROFIL_NON_ECRIT) from exc

    logger.info(
        "Calibration consignee pour la chaine '%s' sous l'etiquette '%s': forme %s, "
        "%d pastille(s) lue(s), %d retenue(s), %d temoin(s) mesure(s) brut(s), "
        "source %s. Fichier: %s",
        chain_id,
        etiquette or "(aucune)",
        lot_correction.correction_form_id,
        lot_correction.read_patch_count,
        lot_correction.retained_patch_count,
        len(lot_correction.witness_raw_bgr),
        lot_correction.source_page_id,
        profile_path,
    )
    return ProfilDeChaineConsigne(
        profile_path=profile_path,
        chain_id=chain_id,
        etiquette=etiquette,
        commentaire=commentaire,
        lot_correction=lot_correction,
        document=document,
        report=report,
        # **Le releve d'`EPIC11-ARB-261`, pose ICI et pas dans une interface.**
        # Il l'etait dans la TUI seule, si bien que `mmu scan ... calibrate`
        # ecrivait un second profil **sans un mot** -- exactement le regime que
        # l'arbitrage ferme, laisse ouvert de moitie. Le poser sur le fait rendu
        # par le coeur donne la meme mesure aux deux interfaces, et une seule
        # redaction de la regle.
        autres_profils=tuple(
            autres_profils_de_la_chaine(project_dir, profile_path, chain_id)),
    )


def autres_profils_de_la_chaine(project_dir, chemin_ecrit,
                                chaine: str) -> list[Path]:
    """Les AUTRES fichiers de profil que cette chaine porte, apres la passe.

    **Corps deplace de `tui/atelier_scan_calibrate.profils_a_remplacer`, jamais
    reecrit** (2026-09-07) : la moitie appelante d'`EPIC11-ARB-261` n'existait
    que du cote TUI, donc la ligne de commande ne fermait rien. Une seconde
    redaction ici aurait diverge un jour, et le symptome aurait ete deux
    interfaces qui ne comptent pas les memes profils.

    **Le releve se fait APRES l'ecriture, et ce n'est pas un pis-aller.** Le
    chemin reellement ecrit est le seul qui se connaisse sans deviner : le nom
    du fichier suit la precedence *saisie -> libelle du QR -> identite de
    chaine* (:func:`etiquette_du_profil`). Une prediction d'avant-passe se
    tromperait exactement dans le cas nominal d'Egan -- ne rien saisir --, et
    dans le sens qui coute : elle annoncerait une seconde calibration sur une
    simple recalibration.

    **Ce que ce releve NE confond pas** : le fichier qu'on vient d'ecrire,
    ecarte par comparaison de chemins **resolus**. Une recalibration pure --
    meme chaine, meme nom -- rend donc une liste vide, et aucune interface
    n'avertit : `write_profile` a deja ecrase son propre fichier, ce qui est le
    regime documente depuis 5.22.
    """
    if chemin_ecrit is None or not chaine:
        return []
    ecrit = Path(chemin_ecrit).resolve()
    return [autre
            for autre in calibration_profile.profils_de_la_chaine(
                project_dir, chaine)
            if autre.resolve() != ecrit]


@dataclass(frozen=True)
class RetraitDesProfils:
    """Ce qu'un retrait a **reellement** fait. Aucun champ n'est une phrase."""

    #: Les fichiers effectivement retires.
    retires: tuple[Path, ...] = ()
    #: Les fichiers qui ont resiste, avec le motif systeme, **verbatim**.
    resistants: tuple[tuple[Path, str], ...] = ()
    #: Le profil par defaut du projet designait-il l'un des retires, et a-t-il
    #: ete repointe sur le profil qui vient d'etre ecrit ?
    defaut_suivi: bool = False


def retirer_les_profils_de_la_chaine(
        project_dir, autres, *, chemin_garde, document_garde,
        designer_le_defaut=profile_designation.record_designated_profile,
        chemin_du_defaut=profile_designation.default_profile_path,
) -> RetraitDesProfils:
    """Retirer les autres profils de cette chaine, et **faire suivre le defaut**.

    **Corps deplace de `tui/atelier_scan_calibrate`** pour le meme motif que
    :func:`autres_profils_de_la_chaine` : la seule ecriture destructive de ce
    parcours ne pouvait pas rester dans une interface quand l'autre en a besoin.

    Elle n'est atteinte que par une issue retenue a la main : c'est l'ecrasement
    CONSCIENT d'`EPIC11-ARB-89`, jamais un effet de bord.

    **Le defaut se releve AVANT le retrait, et l'ordre est le correctif.**
    `profile_designation.default_profile_path` rend `None` des que le fichier a
    disparu ; le relever apres rendrait donc `None` dans **les deux** cas, et le
    suivi ne se declencherait jamais.

    **Pourquoi le defaut suit** : sans suivi, `color.default_profile` garde un
    chemin relatif parfaitement valide vers un fichier absent -- le manifeste ne
    rougit pas, et le regime mesure est un scan qui sort **brut** avec un
    avertissement. Le contraire du suivi n'est donc pas « ne rien faire », c'est
    « casser le defaut du projet sans le dire ».

    **Un retrait qui echoue se PRONONCE** (`EPIC11-ARB-258`) et n'emporte pas
    les autres : un fichier en lecture seule ne doit pas faire perdre le retrait
    des trois autres, ni etre annonce retire. Les deux listes sont rendues
    separement pour cela.
    """
    designe_avant = chemin_du_defaut(project_dir)
    designe_avant = (designe_avant.resolve()
                     if designe_avant is not None else None)
    retires: list[Path] = []
    resistants: list[tuple[Path, str]] = []
    for autre in autres:
        try:
            autre.unlink()
        except OSError as erreur:
            # Le motif systeme voyage **verbatim** : « Permission denied » dit a
            # l'operateur quoi faire, « retrait impossible » ne dit rien.
            resistants.append((autre, str(erreur)))
            continue
        retires.append(autre)
    defaut_suivi = False
    if (designe_avant is not None and chemin_garde is not None
            and any(chemin.resolve() == designe_avant for chemin in retires)):
        designer_le_defaut(project_dir, document_garde,
                           project_path=chemin_garde,
                           source=str(chemin_garde), as_default=True)
        defaut_suivi = True
    return RetraitDesProfils(retires=tuple(retires),
                             resistants=tuple(resistants),
                             defaut_suivi=defaut_suivi)


def calibrer_la_chaine(project_dir, scan_path, *, dpi, logger=None,
                       demander_le_nom_et_le_commentaire=None,
                       confirmer_l_ecrasement=None,
                       rappel_progression=None) -> ProfilDeChaineConsigne:
    """Ingerer, detecter, ajuster, consigner -- et **lever** ce qui refuse.

    Story 11.6, lot B (`EPIC11-ARB-129`) : le **point d'entree de coeur de
    `scan ... calibrate`**, celui qui manquait. `cli.scan_calibrate_command`
    en devient un enveloppeur : memes messages, memes codes de sortie, memes
    artefacts.

    Le geste est explicite : `calibrate` ajuste, et **rien d'autre ne calibre
    une chaine**. Un echec d'ajustement ou une page de calibration absente
    refuse **sans ecrire de profil** -- jamais un profil partiel ou un defaut
    invente, c'est le pendant, a l'echelle de la chaine, de la politique des
    plans `versions/` de 5.12 (le contenu existe ou il n'existe pas).

    **La progression** (story 11.4e, AC 9.1 a 9.3). `rappel_progression` est
    **passe** -- le meme objet, jamais enveloppe -- a
    :func:`scan_ingest.ingest_scan_lot` **et** a
    :func:`scan_detection.detect_lot_pages`, qui le passe a `detect_pages` :
    aucun second mecanisme n'est redige, et le canal reste celui du depot
    (`EPIC7-ARB-79`). C'etait le seul travail long du produit sans canal de
    progression, ce qu'Egan a vu a l'usage -- « RIEN n'indique qu'on a lance le
    processus ».

    **L'ingestion N'EST PLUS MUETTE** (`deferred-work.md`, dette `CALIB-N1`,
    fermee le 2026-09-07 sur le retour de terrain « la barre de progression de
    la calibration saute de 0 a 100 »). Elle est la plus longue des trois
    phases sur un PDF 300 dpi, et elle etait la seule des trois a n'emettre
    rien : sur une mire, la barre restait donc immobile pendant tout le
    travail, puis affichait `1/1`.

    **Les DEUX suites de jalons arrivent par le meme rappel**, et la seconde
    **repart a 1** : les deux phases parcourent les memes pages, donc la
    frontiere de phase se lit sur un jalon non progressif. C'est l'appelant qui
    en fait ce qu'il veut -- la TUI declare une passe a deux lots ; la ligne de
    commande, qui n'affiche pas de barre, n'en fait rien. Agreger ici
    obligerait a envelopper le rappel, ce que l'invariant ci-dessus interdit.

    **Aucun jalon avant la premiere page INGEREE** (AC 9.3, dont la lettre
    change avec `CALIB-N1` et dont le motif ne change pas) : un refus qui tombe
    avant toute lecture de page -- chemin introuvable, forme non supportee,
    dpi invalide -- ne produit toujours aucune progression, parce qu'aucune
    page n'a ete traversee. Ce qui est ecarte est un chiffre invente, pas un
    chiffre precoce.

    :param scan_path: ce que `scan_ingest.ingest_scan_lot` accepte.
    :param dpi: le dpi de numerisation **declare**, obligatoire et sans defaut.
    :param rappel_progression: `None`, ou un appelable `(faites, total)`. Un
        autre type **leve** (AC 9.2) : « un rappel qui s'eteint en silence
        quand on lui passe le mauvais type n'est pas optionnel, il est casse ».
    :raises TypeError: `rappel_progression` n'est ni `None` ni appelable.
    :raises scan_ingest.ScanIngestError: l'ingestion a refuse la pile.
    :raises scan_detection.ScanDetectionError: la detection a refuse la pile.
    :raises RefusDeCalibration: l'un des refus de
        :data:`MOTIFS_DE_REFUS_DE_CALIBRATION`.
    """
    # **La garde de type est ICI et non dans l'emetteur**, et c'est un choix de
    # perimetre plutot qu'un oubli. `progression.EmetteurProgression` ecarte un
    # non-appelable en silence (`rappel if callable(rappel) else None`) ; l'y
    # faire lever changerait le contrat de TOUS ses appelants, extraction
    # comprise. L'AC 9.2 vise cette fonction, la garde y est.
    #
    # Elle precede l'ingestion : un rappel casse doit se dire AVANT que la
    # passe n'ait rien copie, pas apres.
    if rappel_progression is not None:
        if not callable(rappel_progression):
            raise TypeError(
                "rappel_progression doit etre appelable ou None, recu "
                f"{type(rappel_progression).__name__}. Un rappel qui s'eteint "
                "en silence quand on lui passe le mauvais type n'est pas "
                "optionnel, il est casse."
            )
        # **L'ARITE est du meme mauvais type**, et c'est la forme qu'on ecrit
        # par accident : `lambda faites: ...` est appelable, passe la garde, et
        # `EmetteurProgression` absorbe ensuite le `TypeError` **par contrat**
        # (`EPIC7-ARB-79`). Resultat mesure sur un lot de trois pages : zero
        # jalon, aucune levee, aucun message -- exactement le regime que l'AC
        # 9.2 dit fermer (revue de vague B, couche 2). Le banc du lot documente
        # lui-meme s'y etre fait prendre avec un `jalons.append` nu.
        try:
            inspect.signature(rappel_progression).bind(0, 0)
        except TypeError as exc:
            raise TypeError(
                "rappel_progression doit accepter deux entiers "
                f"(faites, total) : {exc}. Un rappel qui s'eteint en silence "
                "quand on lui passe le mauvais type n'est pas optionnel, il "
                "est casse."
            ) from exc
        except (ValueError, AttributeError):
            # Un appelable dont la signature ne s'introspecte pas (natif,
            # `functools.partial` exotique) n'est pas un motif de refus : la
            # garde mesure ce qu'elle peut lire, elle n'invente pas.
            pass
    logger = logger or logging.getLogger(__name__)
    project_dir = Path(project_dir)
    try:
        report = scan_ingest.ingest_scan_lot(
            project_dir, scan_path, dpi=dpi,
            rappel_progression=rappel_progression)
    except scan_ingest.ScanIngestError as exc:
        logger.error("Echec de l'ingestion: %s", exc)
        raise

    try:
        detection = scan_detection.detect_lot_pages(
            project_dir, report, dpi=dpi,
            rappel_progression=rappel_progression)
    except scan_detection.ScanDetectionError as exc:
        logger.error("Echec de la detection: %s", exc)
        raise

    _refuser_une_pile_mixte(detection, logger)

    return consigner_le_profil_de_chaine(
        project_dir, report, detection,
        dpi=dpi, scan_locator=scan_path, logger=logger,
        demander_le_nom_et_le_commentaire=demander_le_nom_et_le_commentaire,
        confirmer_l_ecrasement=confirmer_l_ecrasement)


#: Ce que l'operateur lit devant une pile mixte, et **il porte le geste**.
#: `EPIC11-ARB-258` : un refus se prononce. Un refus qui nommerait seulement le
#: probleme laisserait l'operateur devant une pile qu'il vient de scanner sans
#: savoir quoi en faire -- or les deux issues existent et sont a une commande.
PHRASE_DE_LA_PILE_MIXTE = (
    "cette pile porte une page de calibration ET {cardinal} planche(s) "
    "d'images. La calibration ne sait pas ecrire de frames : elle consignerait "
    "le profil et laisserait vos planches sur le disque, declarees par "
    "personne. Deux issues : scannez la page de calibration SEULE, ou passez "
    "la pile entiere a `scan` SANS --lot-slug -- il trie les feuilles par leur "
    "QR, range chaque planche dans son lot et consigne la calibration au "
    "passage."
)


def _refuser_une_pile_mixte(detection, logger=None) -> None:
    """Refuser une pile qui melange la mire et des planches. `EPIC11-ARB-266`.

    **Le parcours `scan` refusait deja cette pile ; celui-ci l'acceptait.**
    Mesure du 2026-09-07 : `calibrate` sur une pile portant la mire et quatre
    planches reelles consignait le profil, n'ecrivait aucune frame, et
    declarait le dossier de scan **entier** -- si bien que les quatre planches
    perdaient leur mention « non declare » a l'inventaire. C'est l'erreur qui
    coute le plus cher des deux : elle **cache** un oubli reel au lieu d'en
    inventer un.

    **La garde est posee ICI et pas dans `consigner_le_profil_de_chaine`**, et
    la distinction est tout le sujet. Ce corps-la a un second appelant, le tri
    en vrac de la story 5.24, dont la pile est mixte **par construction** : il
    route la page de calibration hors de la pile avant toute lecture
    d'identite, range chaque planche dans le lot que son QR declare, plusieurs
    lots compris, puis consigne. Poser la garde plus bas casserait exactement
    le parcours qui fait bien ce que ce refus interdit de faire mal.

    **Le predicat se lit du meme endroit que le refus de `scan`**
    (`io.reconstruction`), jamais recopie : deux redactions de la partition
    seraient deux verites sur la meme pile, et l'une mordrait sur ce que
    l'autre accepte. C'est le motif meme pour lequel `EPIC5-ARB-92` avait
    extrait cette partition.

    Ne rend rien : elle laisse passer ou elle leve.
    """
    logger = logger or logging.getLogger(__name__)
    payloads = [page.payload for page in getattr(detection, "pages", ())
                if getattr(page, "payload", None)]
    planches = reconstruction.planches_d_images_de_la_pile(payloads)
    # **MIXTE veut dire les DEUX, et pas seulement « il y a des planches »**
    # (trouve par `test_scan_write_noyau.py` a la course de cloture, avant
    # qu'aucun oeil ne le voie). Une pile de planches SEULES n'est pas mixte :
    # elle n'a pas de page de calibration du tout, et le refus qui la nomme
    # existe deja, plus bas et plus precis -- « aucune page de calibration lue
    # dans ce scan ». Mordre ici lui ferait lire « cette pile porte une page de
    # calibration ET 3 planches », c'est-a-dire une phrase FAUSSE de la moitie
    # de ce qu'elle affirme, sur une pile ou l'operateur a simplement oublie sa
    # mire.
    if not planches or len(planches) == len(payloads):
        return
    message = PHRASE_DE_LA_PILE_MIXTE.format(cardinal=len(planches))
    logger.error("Refus de calibration: %s", message)
    raise RefusDeCalibration(message,
                             motif=REFUS_PILE_MIXTE_EN_CALIBRATION)
