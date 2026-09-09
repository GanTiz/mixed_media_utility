# -*- coding: utf-8 -*-
"""Story 5.29 (`EPIC11-ARB-89`), operation « supprimer » : retirer proprement
un element de projet (lot ou rush) du manifeste et du disque.

Motif reel qui justifie ce module: le nettoyage manuel du 2026-08-27 a
detruit au `git rm -r` les frames 25p et 12p5 de `chendj-mat`, absentes de
`HEAD` donc irrecuperables (`deferred-work.md`). Sans ce mecanisme, la seule
issue possible face a un lot indesirable est un `git rm` a la main, aveugle
a la nature de ce qu'il efface.

Trois exigences, toutes mesurees par les AC de la story:

1. mettre a jour `project.json` (AC 10) -- **avant** les fichiers, jamais
   apres: un echec de suppression de fichier laisse alors un manifeste
   coherent avec ce qui reste reellement lisible, jamais l'inverse;
2. supprimer **uniquement** les fichiers de l'element vise, et les NOMMER
   tous dans le rapport (AC 9). Le classement par « nature » qui distinguait
   ici pointeur Git LFS, fichier local suivi par git et donnees de travail non
   suivies a ete RETIRE par `EPIC11-ARB-199` (Egan, 2026-09-03): « l'utilitaire
   n'a pas vocation a traiter des fichiers au sein de depots git ». Le motif
   d'origine ci-dessus reste vrai -- ce qui part, c'est la logique qui
   INSPECTAIT git, pas le souvenir de pourquoi on supprime proprement;
3. refuser de vider le dernier lot d'un projet sans confirmation explicite
   (AC 11), avec un mot-cle DISTINCT du mode non-dry-run lui-meme.

Mode dry-run par defaut (AC 9): aucune ecriture n'a lieu tant que l'appelant
n'a pas explicitement demande `dry_run=False`.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping, Sequence

from .io import naming, project_layout, version_ranks
from .io.version_ranks import RANG_ORIGINE as RANG_ORIGINE_DU_RAPPORT
from .io.pdf_manifest import SHEETS_INVENTORY_FIELD, SHEETS_WATERMARK_FIELD
from .io.encode_manifest import (
    MASTERS_WATERMARK_FIELD as ENCODE_MASTERS_WATERMARK_FIELD,
)
from .io.extraction_manifest import (
    LOT_WATERMARKS_FIELD,
    rangs_employes_de_la_famille,
)
from .io.project_layout import SCANS_DIRNAME
from .io.manifest import load_manifest

__all__ = [
    "ProjectMaintenanceError",
    "LastLotRefusedError",
    "RapportSuppression",
    "LigneDeGroupe",
    "RapportDeGroupe",
    "remove_project_element",
    "remove_project_group",
]


class ProjectMaintenanceError(RuntimeError):
    """Erreur de coeur pour la suppression d'un element de projet."""


class LastLotRefusedError(ProjectMaintenanceError):
    """Refus de vider le dernier lot ou le dernier rush d'un projet (AC 11).

    Distincte de `ProjectMaintenanceError` pour que l'appelant puisse
    distinguer « rien a supprimer sous ce nom » de « il y a bien quelque
    chose, mais le vider exige une confirmation supplementaire ».
    """


@dataclass(frozen=True)
class RapportSuppression:
    """Rapport de `remove_project_element`, en dry-run ou apres suppression.

    `fichiers_a_supprimer` nomme TOUS les fichiers vises, a plat, en chemins
    relatifs au dossier projet et en POSIX, **dans l'ordre ou l'appelant les a
    construits**. Il remplace le classement par nature retire par
    `EPIC11-ARB-199`: le rapport perd la classification, jamais
    l'information -- le cardinal et la liste restent lisibles. Le champ n'est
    ni optionnel ni pourvu d'un defaut: un rapport de suppression qui ne dirait
    pas ce qu'il supprime serait pire que le classement qu'on retire.

    `fichiers_non_supprimes` (trouve en revue) : les chemins qu'`unlink()` a
    refuse de supprimer (droits, fichier verrouille...), jamais avales en
    silence. `supprime` ne vaut `True` que si cette liste est vide -- un
    manifeste deja mis a jour (AC 10) mais des fichiers restes sur le disque
    est exactement la fuite de disque que cette story existe pour fermer, et
    elle doit se voir dans le rapport, pas seulement dans les logs.

    `fichiers_attendus_absents` : les annexes que la FILIATION designe mais
    qui ne sont pas sur le disque. Le cas normal est benin (le lot n'a
    jamais ete imprime, jamais encode), mais il faut le DIRE plutot que de
    le taire : le PDF de planches se retrouve par recalcul de son nom, si
    bien qu'un fichier renomme a la main devient invisible a ce mecanisme et
    resterait sur le disque en silence. Un master, lui, porte son chemin au
    manifeste : son absence signale un fichier deja efface ailleurs.
    """

    cible: str
    fichiers_a_supprimer: tuple[str, ...]
    dry_run: bool
    supprime: bool = False
    fichiers_non_supprimes: tuple[str, ...] = ()
    fichiers_attendus_absents: tuple[str, ...] = ()
    #: TOUS les dossiers de scan lies a ce lot presents sur le disque --
    #: NOMMES meme quand ils ne sont pas supprimes, pour que le consentement de
    #: `avec_scans` soit eclaire plutot que demande a l'aveugle.
    #:
    #: Pluriel depuis `EPIC11-ARB-109` : un lot rescanne depuis deux slugs en a
    #: deux, et n'en nommer qu'un ferait consentir a une suppression dont
    #: l'operateur ne voit pas la moitie.
    dossiers_de_scan: tuple[str, ...] = ()
    #: Ce dossier a-t-il ete inclus dans la suppression ?
    scan_inclus: bool = False
    #: L'objet retire est-il le DERNIER a date (`EPIC11-ARB-92`) ? Seul ce
    #: cas ouvre le choix de rendre le rang ; ailleurs il est consomme.
    #: Vaut pour les CINQ objets versionnables depuis `EPIC11-ARB-108`, d'ou
    #: `objet_en_queue` ci-dessous -- le nom historique parle des tirages, qui
    #: etaient le seul objet a porter le mecanisme.
    tirage_en_queue: bool = False
    #: Les rangs que `liberer_le_rang=True` rendrait (ou a rendus). Plusieurs
    #: d'un coup quand des rangs anterieurs avaient ete retires sans etre
    #: liberes : ils redeviennent la queue au meme moment.
    rangs_liberables: tuple[int, ...] = ()
    #: Les rangs ont-ils ete effectivement rendus ?
    rang_libere: bool = False
    #: Le rang de l'objet retire. Porte par le rapport plutot que redechiffre
    #: du nom par l'appelant : `naming.format_version_suffix` est le seul lieu
    #: du format, et une seconde recette de lecture serait une seconde verite
    #: (`EPIC5-ARB-78`).
    rang_vise: int = RANG_ORIGINE_DU_RAPPORT
    #: L'objet retire a-t-il un rang PROPRE ? Faux pour le seul objet de cette
    #: commande qui n'en a pas -- le jeu de frames extraites, dont le dossier
    #: porte le rang du LOT.
    #:
    #: **Le rapport le PORTE plutot que de laisser l'appelant le deduire**, et
    #: c'est mesure : sans ce champ, la CLI retombait sur sa branche « le rang
    #: reste CONSOMME: un objet posterieur existe » -- une phrase FAUSSE, qui
    #: nomme un objet posterieur inexistant, sur le seul cas ou aucun rang
    #: n'est en jeu. Un booleen deduit de `rangs_liberables` vide ne suffirait
    #: pas : un objet en queue qui ne libere rien est dans le meme etat.
    rang_independant: bool = True

    @property
    def dossier_de_scan(self) -> str | None:
        """Le PREMIER dossier de scan, ou `None`. Vue historique du pluriel."""
        return self.dossiers_de_scan[0] if self.dossiers_de_scan else None

    @property
    def objet_en_queue(self) -> bool:
        """Nom neutre de `tirage_en_queue`, qui porte desormais cinq objets."""
        return self.tirage_en_queue


def _sous_le_projet(project_dir: Path, candidat: Path, champ: str, brut: Any) -> Path:
    """Rendre `candidat` s'il est REELLEMENT sous `project_dir`, lever sinon.

    **Une seule garde, apres resolution -- et c'est le point.** La premiere
    redaction de cette garde testait `PurePosixPath(relatif).is_absolute()`,
    ce qui laissait passer TROIS evasions, chacune mesuree plutot que
    supposee (revue Opus du 2026-08-30) :

    * ``"../../ailleurs"`` -- `is_absolute()` rend `False`, et
      ``Path("/projets/p") / "../../ailleurs"`` **resout** a
      ``/ailleurs``. Mesure : un fichier hors du dossier projet a ete
      REELLEMENT detruit par `remove_project_element`, rapport
      ``supprime=True``, sans un mot ;
    * un **lien symbolique** de dossier -- aucun composant du chemin
      declare n'est suspect, mais `rglob` traverse le lien et `unlink()`
      supprime les fichiers reels a l'autre bout ;
    * ``"C:/Windows/..."`` -- `PurePosixPath(...).is_absolute()` rend `False`
      (c'est un nom de dossier `C:` pour POSIX), alors que c'est un chemin
      absolu sur la plateforme Windows que ce depot cible (NFR1).

    Tester la FORME du chemin declare ne pouvait pas les couvrir toutes : on
    teste donc le RESULTAT, apres `resolve()` (qui suit les liens). Un chemin
    qui sort du projet est refuse, quelle que soit la maniere dont il en
    sort. C'est la seule formulation qui ferme les trois d'un coup, et celles
    qu'on n'a pas encore imaginees.
    """
    racine = project_dir.resolve()
    try:
        reel = candidat.resolve()
    except OSError as erreur:  # boucle de liens, chemin trop long
        raise ProjectMaintenanceError(
            f"lots[].{champ} ({brut!r}) n'a pas pu etre resolu ({erreur}). Refuse "
            "plutot que suppose : aucune suppression n'a eu lieu."
        ) from erreur
    # **La racine du projet elle-meme est REFUSEE**, et l'admettre etait un
    # defaut de cette garde (revue Opus finale). `reel != racine and ...` la
    # laissait passer. Mesure : un `frames_dir` valant `"."`, `""` ou
    # `"frames/.."` resout sur le dossier projet, `rglob` le parcourt entier,
    # et la suppression emportait **`project.json` lui-meme** plus les frames
    # de tous les autres lots -- en rapportant un succes. Pire que le defaut
    # d'origine, puisqu'elle detruit le manifeste qui permettrait de savoir ce
    # qui a ete perdu.
    # La regle vit dans `io/project_layout` depuis le 2026-09-03 (revue de la
    # story 6.8, finding R4) : trois lecteurs la voulaient, deux l'avaient, et
    # le troisieme -- le plus neuf -- ne pouvait pas savoir qu'elle existait.
    # `reel` reste calcule ici, le message et le refus d'`OSError` en ayant
    # besoin ; `resolve()` est idempotent.
    if not project_layout.est_strictement_sous_le_projet(racine, reel):
        raise ProjectMaintenanceError(
            f"lots[].{champ} ({brut!r}) designe {reel}, qui n'est pas STRICTEMENT "
            f"contenu dans le dossier projet {racine}. Refuse plutot que suppose : un "
            "chemin remontant (`..`), un lien symbolique vers l'exterieur ou un chemin "
            "absolu feraient supprimer des fichiers etrangers au projet ; et le dossier "
            "projet LUI-MEME emporterait le manifeste et tous les autres lots. Un "
            "manifeste sain ne produit que des chemins relatifs contenus "
            "(io.naming._relative_posix) ; celui-ci est corrompu ou modifie a la main. "
            "Aucune suppression n'a eu lieu."
        )
    return candidat


def _objets_declares_par(
    project_dir: Path, manifest: Mapping[str, Any] | None, autre: Mapping[str, Any]
) -> list[tuple[Path, str, str]]:
    """TOUT ce qu'une entree de lot fait declarer au manifeste, en chemins ABSOLUS.

    Rend des triplets `(chemin resolu, nature, chemin declare)`. La nature est
    le mot que le refus emploiera : elle vient d'ici plutot que du site
    d'appel, pour que les quatre familles se nomment d'un seul endroit.

    **Les quatre familles, et pourquoi il fallait les quatre** (finding `C2-2`
    de la revue de la vague 2, couche 2). `_refuser_le_chevauchement` ne
    comparait qu'`frames_dir` et `output_frames_dir` : un `frames_dir` valant
    `"outputs"` passait la garde, `rglob` y ramassait le master encode du lot,
    et la suppression le detruisait pendant que `encoded_masters[].path`
    continuait de le declarer. Mesure du regime, avant correctif :
    `remove_project_element(..., frames_extraites=True, dry_run=False)`
    rendait `supprime=True`, la liste des fichiers portait bien le `.mov` et
    le `.pdf` -- l'apercu ne mentait pas --, et le manifeste sortait de la
    en declarant deux fichiers detruits.

    **Les dossiers de scan sont dans la liste, et ils y pesent le plus lourd.**
    Un dossier de scan ne se refabrique pas par calcul : il exige un passage
    au scanner (`EPIC11-ARB-90`), ce pourquoi le detruire demande un
    TROISIEME consentement, `avec_scans`. Un `frames_dir` valant `"scans"`
    les emportait sans ce consentement -- c'est-a-dire par la porte meme que
    le consentement existe pour fermer.

    Chaque candidat est resolu comme les dossiers le sont deja : la garde
    mesure le RESULTAT, jamais la forme du chemin declare, faute de quoi un
    lien symbolique la contournerait. Un candidat irresolvable est saute
    plutot que refuse -- on ne bloque pas une suppression sur un chemin
    ETRANGER qu'on ne sait pas lire, `_sous_le_projet` gardant la sienne.
    """
    objets: list[tuple[Path, str, str]] = []
    relatifs: list[tuple[str, str]] = []
    for chemin in _masters_declares(autre):
        relatifs.append((chemin, "le master"))
    for chemin in _planche_pdf_declaree(project_dir, manifest or {}, autre):
        relatifs.append((chemin, "la planche"))
    for brut, nature in relatifs:
        try:
            objets.append(((project_dir / brut).resolve(), nature, brut))
        except OSError:
            continue
    try:
        dossiers_de_scan = _scans_du_lot(project_dir, manifest or {}, autre)
    except ProjectMaintenanceError:
        # Un `ingest_slug` que `_sous_le_projet` refuse est le probleme d'un
        # AUTRE lot : le transformer en refus ici ferait echouer la
        # suppression demandee sur une corruption qui ne la concerne pas.
        dossiers_de_scan = []
    for dossier_de_scan in dossiers_de_scan:
        try:
            objets.append((
                dossier_de_scan.resolve(), "le dossier de scan",
                dossier_de_scan.relative_to(project_dir).as_posix()))
        except (OSError, ValueError):
            continue
    return objets


def _refuser_le_chevauchement(
    project_dir: Path, dossier: Path, champ: str, brut: Any, autres_lots: list,
    manifest: Mapping[str, Any] | None = None,
) -> None:
    """Refuser un dossier qui CONTIENT un objet declare, ou l'egale.

    Trouve en revue Opus finale. `_sous_le_projet` verifie qu'on reste dans le
    projet ; elle ne dit rien de ce qu'on emporte a l'INTERIEUR. Un
    `frames_dir` valant `"frames"` -- l'ancetre commun -- est bien sous le
    projet, et `rglob` y ramasse les frames de **tous** les lots : supprimer
    le lot vise detruisait celles des autres, que le manifeste continuait
    pourtant de declarer. Meme risque quand deux lots declarent le meme
    dossier.

    **La garde couvre desormais les QUATRE familles d'objets declares**, pas
    les deux dossiers de frames seulement (finding `C2-2`) : masters,
    planches et dossiers de scan sont eux aussi des fichiers que le manifeste
    continue de declarer apres coup. La liste vient de
    :func:`_objets_declares_par`, ecrite une fois pour ce site et pour ses
    deux appelants -- une seconde redaction diverge au premier ajustement, et
    celle-ci decide d'une destruction.

    **Ce que `autres_lots` porte n'est pas le meme ensemble selon l'appelant,
    et c'est voulu.** Le chemin du lot ENTIER supprime les annexes du lot vise
    lui-meme : les lui opposer le ferait refuser toujours, donc il ne passe
    que les AUTRES lots. Le chemin des frames extraites ne supprime QUE le
    dossier de frames : le lot vise s'y passe lui-meme, prive de son
    `frames_dir` -- sans quoi il se comparerait a sa propre cible.
    """
    for autre in autres_lots:
        if not isinstance(autre, Mapping):
            continue
        for champ_autre in ("frames_dir", "output_frames_dir"):
            relatif_autre = autre.get(champ_autre)
            if not relatif_autre:
                continue
            try:
                cible = (project_dir / str(relatif_autre)).resolve()
            except OSError:
                continue
            if cible == dossier or dossier in cible.parents:
                raise ProjectMaintenanceError(
                    f"lots[].{champ} ({brut!r}) contient -- ou egale -- le dossier du "
                    f"lot {autre.get('lot_id')!r} ({relatif_autre!r}). Le supprimer "
                    "emporterait les fichiers d'un lot que le manifeste continue de "
                    "declarer. Refuse plutot que suppose ; aucune suppression n'a eu "
                    "lieu."
                )
        for cible, nature, relatif_autre in _objets_declares_par(
                project_dir, manifest, autre):
            if cible == dossier or dossier in cible.parents:
                raise ProjectMaintenanceError(
                    f"lots[].{champ} ({brut!r}) contient -- ou egale -- {nature} du "
                    f"lot {autre.get('lot_id')!r} ({relatif_autre!r}). Le supprimer "
                    "emporterait un objet que le manifeste continue de declarer. "
                    "Refuse plutot que suppose ; aucune suppression n'a eu lieu."
                )


def _cle_de_tri_posix(project_dir: Path, chemin: Path) -> str:
    """LA cle d'ordre de tout ce que l'outil annonce detruire (`EPIC11-ARB-243`).

    Le chemin relatif au projet, en POSIX. Ecrite une fois et appelee partout
    plutot que recopiee : deux redactions d'une meme regle divergent au premier
    ajustement, et celle-ci ordonne une liste de destruction.

    Elle ne rattrape RIEN : un chemin hors du projet leve `ValueError`, comme
    avant ce refactor. `_sous_le_projet` refuse ces chemins-la bien en amont,
    et poser ici un repli les ferait passer en silence -- une branche morte
    aujourd'hui, un contournement de la garde le jour ou elle cesse de l'etre.
    """
    return chemin.relative_to(project_dir).as_posix()


def _fichiers_du_lot(
    project_dir: Path, lot: Mapping[str, Any], autres_lots: list | None = None,
    manifest: Mapping[str, Any] | None = None,
) -> list[Path]:
    """Tous les fichiers geres par ce mecanisme pour un lot: ses deux dossiers
    de frames possibles (extraites et rescannees), rien d'autre -- **chaque
    dossier parcouru dans l'ordre de ses chemins POSIX** (`EPIC11-ARB-243`),
    les dossiers dans l'ordre ou le manifeste les declare.

    `manifest` ne sert qu'a la garde de chevauchement, qui en a besoin pour
    recomposer les noms de planches des lots ANTERIEURS a l'inventaire
    (`sheets_pdfs`). Il est facultatif pour ne pas casser les appelants de
    banc ; sans lui, la garde couvre les masters et les scans des autres lots,
    et rate leurs planches deduites -- une couverture reduite, jamais fausse.

    Chaque dossier declare passe par `_sous_le_projet` AVANT d'etre parcouru.
    Chaque fichier releve y repasse aussi, **sauf s'il est lui-meme un lien
    symbolique** -- et cette exception est mesuree, pas supposee :

    * `Path.unlink()` sur un lien retire **le lien**, jamais sa cible :
      supprimer un lien pose dans un dossier de lot est donc sans danger
      pour ce qu'il designe, et le refuser serait un blocage sec sur un cas
      inoffensif ;
    * en Python 3.11, `rglob` ne **descend pas** dans un lien de dossier (le
      lien lui-meme rend `is_file() == False`, donc il n'est meme pas
      releve). La revue annoncait l'inverse comme « verifie » ; la mesure dit
      le contraire, et c'est la mesure qui tranche.

    La verification par fichier reste neanmoins en place pour les fichiers
    **reels** : elle ne coute rien et elle tient si une version ulterieure de
    Python se met a descendre dans les liens de dossier -- auquel cas de
    vrais fichiers externes seraient releves, et eux seraient bel et bien
    detruits.
    """
    fichiers: list[Path] = []
    for champ in ("frames_dir", "output_frames_dir"):
        relatif = lot.get(champ)
        if not relatif:
            continue
        dossier = _sous_le_projet(project_dir, project_dir / str(relatif), champ, relatif)
        _refuser_le_chevauchement(
            project_dir, dossier.resolve(), champ, relatif, autres_lots or [],
            manifest=manifest,
        )
        if dossier.is_dir():
            # **Parcours ORDONNE, par chemin POSIX** (`EPIC11-ARB-243`). Sans
            # ce tri, l'ordre est celui de `os.scandir` : ni alphabetique, ni
            # chronologique, ni garanti d'un `ext4` a un `APFS`. C'est la liste
            # que la boucle `unlink()` parcourt, donc l'ordre de DESTRUCTION
            # lui-meme dependait du systeme de fichiers.
            for chemin in sorted(
                dossier.rglob("*"), key=lambda c: _cle_de_tri_posix(project_dir, c)
            ):
                if not chemin.is_file():
                    continue
                if chemin.is_symlink():
                    fichiers.append(chemin)
                else:
                    fichiers.append(_sous_le_projet(project_dir, chemin, champ, relatif))
    # Les DOSSIERS restent dans l'ordre ou le manifeste les declare
    # (`frames_dir` puis `output_frames_dir`) : la liste rendue est donc
    # ordonnee PAR DOSSIER, pas globalement. L'ordre total de ce que
    # l'operateur LIT est pose un cran plus bas, par `_chemins_a_supprimer`,
    # qui seul voit la liste complete -- frames, annexes et scans reunis.
    #
    # Et les deux tris sont mesures separement, ce qui n'est pas une commodite :
    # un tri total pose en aval rendrait toute permutation amont invisible,
    # donc non mesurable. `test__fichiers_du_lot_ORDONNE_chaque_dossier...`
    # mesure celui-ci, le banc du rapport mesure l'autre.
    return fichiers


class _Declares(list):
    """Marqueur : cette liste de chemins vient du MANIFESTE, pas d'un recalcul.

    Une sous-classe de `list` plutot qu'un couple `(liste, booleen)` : les
    appelants la parcourent comme une liste ordinaire, et seul celui que la
    distinction interesse la teste. Un booleen en plus se serait fait oublier
    au premier appelant neuf.
    """


def _masters_declares(lot: Mapping[str, Any]) -> list[str]:
    """Les chemins de masters que CE lot declare, lus a `encoded_masters[].path`.

    La filiation est ecrite au manifeste, elle ne se devine pas : chaque
    entree porte son `path`, cle d'appariement unique de l'inventaire (story
    6.5). On ne recompose AUCUN nom ici -- un lot porte legitimement
    plusieurs masters (mezzanine et derive, story 6.1) a des profils et des
    resolutions differents, et seul l'inventaire dit lesquels existent.

    Une entree sans `path` exploitable est ignoree plutot que devinee : le
    contrat dit que l'inventaire declare ce qui a ete PRODUIT, jamais ce qui
    est PRESENT, et deviner un chemin ferait supprimer sur une supposition.
    """
    chemins: list[str] = []
    for entree in lot.get("encoded_masters") or []:
        if not isinstance(entree, Mapping):
            continue
        chemin = entree.get("path")
        if isinstance(chemin, str) and chemin:
            chemins.append(chemin)
    return chemins


def _planche_pdf_declaree(
    project_dir: Path, manifest: Mapping[str, Any], lot: Mapping[str, Any]
) -> list[str]:
    """TOUS les chemins de PDF de planches de ce lot, RECALCULES par la recette de nom.

    Difference de nature avec les masters, a garder en tete : le manifeste ne
    persiste PAS le chemin du PDF (il ne garde de l'etape que `template_id`,
    `patch_preset_id`, `gamut_map_id`). La filiation passe donc par le NOM,
    que `legacy_sheets_pdf_filename` produit de facon deterministe.

    Consequence assumee, signalee au rapport plutot que tue : un PDF renomme
    a la main devient invisible a ce mecanisme. C'est strictement moins sur
    qu'un chemin persiste -- mais c'est la seule filiation disponible tant
    que `makepdf` n'ecrit pas son chemin au manifeste, et l'alternative (ne
    rien supprimer) laisse TOUTES les planches sur le disque, ce qui est pire.
    """
    # **L'INVENTAIRE D'ABORD** (`EPIC11-ARB-90`). Depuis que `makepdf` ecrit
    # `lots[].sheets_pdfs`, la filiation des planches est ECRITE comme celle
    # des masters, et non plus deduite d'un nom. C'est ce qui rattrape le seul
    # cas que le recalcul ne pouvait pas voir : un PDF renomme a la main.
    declares = [
        entree.get("path")
        for entree in lot.get("sheets_pdfs") or []
        if isinstance(entree, Mapping) and isinstance(entree.get("path"), str)
        and entree.get("path")
    ]
    if declares:
        # Marqueur de NATURE : ces chemins sont DECLARES au manifeste, pas
        # devines. La difference commande le rapport -- un chemin declare et
        # absent du disque est une promesse non tenue, qui doit se voir ; un
        # nom recalcule et absent est le cas ordinaire d'un tirage jamais
        # imprime, qui noierait le rapport si on le signalait 99 fois.
        return _Declares(declares)

    # Repli sur le RECALCUL du nom, pour les manifestes ecrits avant cette
    # story. Le champ est additif : les refuser priverait de suppression tous
    # les projets existants, ce qui serait pire que la fragilite qu'on ferme.
    project_id = manifest.get("project_id")
    rush_id = lot.get("rush_id")
    lot_id = lot.get("lot_id")
    if not (project_id and rush_id and lot_id):
        return []
    noms: list[str] = []
    # **TOUS les tirages, pas seulement le premier** (revue, majeur 3). La
    # premiere redaction ne visait que le rang 1, alors que `EPIC11-ARB-91`
    # permet desormais 99 tirages par lot: supprimer un lot laissait ses
    # versions orphelines sur le disque avec `supprime=True`, et le message de
    # refus de `makepdf` prescrit pourtant `project remove` en promettant
    # qu'il « retire le lot et ses planches ».
    # **Le repli reconstruit l'ANCIENNE forme de nom**, et c'est une deduction,
    # pas un oubli (`EPIC11-ARB-171`, 2026-09-02). On n'arrive ici que si le lot
    # ne declare AUCUN `sheets_pdfs` -- champ pose par `EPIC11-ARB-90`, donc
    # anterieur a l'arbitrage sur le nom. Un manifeste sans inventaire a
    # forcement ete ecrit avant, et ses fichiers portent donc `_planches`.
    # Balayer en plus les 63 mises en page rendrait 6 300 chemins candidats par
    # lot, que `_refuser_l_annexe_partagee` reparcourt lot par lot : un cout
    # quadratique paye pour un cas qui ne peut pas exister.
    #
    # **LES DEUX RACINES**, `EPIC11-ARB-225`, et c'est le site le plus dangereux
    # des six : ces chemins sont les CANDIDATS A LA SUPPRESSION. Sous
    # `planches/` seul, supprimer un lot d'un projet ancien laisserait son PDF
    # en place, en silence, et le rapport annoncerait le lot libere.
    #
    # **Le dossier d'avant est interroge UNE fois, pas 99**, et c'est le meme
    # souci de cout que le paragraphe ci-dessus : `chemin_de_planche` fait un
    # `is_file()` par appel, et `_refuser_l_annexe_partagee` reparcourt cette
    # liste lot par lot. Quand `patches/` n'existe pas -- tout projet neuf,
    # donc le cas ordinaire -- la composition redevient purement textuelle et
    # ne coute aucune entree-sortie de plus qu'avant l'arbitrage.
    deux_racines = len(project_layout.racines_de_planches(project_dir)) > 1
    for rang in [None] + list(range(naming.VERSION_RANK_MIN, naming.VERSION_RANK_MAX + 1)):
        try:
            nom = naming.legacy_sheets_pdf_filename(
                str(project_id), str(rush_id), str(lot_id), version_rank=rang)
        except naming.NamingError:
            # Identifiants que la recette de nom refuse : on ne devine pas un
            # chemin de suppression a partir d'un nom que le nommage lui-meme
            # declare invalide.
            return []
        if deux_racines:
            chemin = project_layout.chemin_de_planche(project_dir, nom)
            noms.append(chemin.relative_to(project_dir).as_posix())
        else:
            noms.append(f"{project_layout.PLANCHES_DIRNAME}/{nom}")
    return noms


def _refuser_l_annexe_partagee(
    project_dir: Path, reel: Path, relatif: str, autres_lots: list,
    manifest: Mapping[str, Any] | None = None,
) -> None:
    """Refuser de supprimer un fichier annexe qu'un AUTRE lot declare aussi.

    Symetrique, au niveau FICHIER, de `_refuser_le_chevauchement` au niveau
    dossier -- necessaire pour la meme raison : masters et planches vivent
    dans des dossiers PARTAGES (`outputs/`, `planches/`), la ou les frames ont
    chacune leur dossier propre. Deux lots declarant le meme `path` sont une
    incoherence de manifeste ; supprimer pour l'un detruirait la sortie de
    l'autre, sans trace.
    """
    for autre in autres_lots:
        if not isinstance(autre, Mapping):
            continue
        candidats = list(_masters_declares(autre))
        # `_planche_pdf_declaree` rend desormais TOUTE la famille de tirages
        # (rang 1 plus les 98 versions), pas un chemin unique -- consequence
        # du correctif de fuite de la revue. Le second appelant doit suivre :
        # une liste concatenee la ou un `append` attendait une chaine.
        # **Le VRAI manifeste, pas un `project_id` bidon** (trouve en revue,
        # couche 1). Le repli par recalcul de nom utilisait `{"project_id":
        # "x"}` : les noms produits ne pouvaient JAMAIS egaler un chemin reel
        # du projet, donc la garde ne fonctionnait que par l'inventaire
        # `sheets_pdfs`. Sur un lot anterieur a l'inventaire, elle etait
        # inerte -- et le faux identifiant masquait cette limite au lieu de la
        # dire.
        candidats.extend(_planche_pdf_declaree(project_dir, manifest or {}, autre))
        for candidat in candidats:
            try:
                meme = (project_dir / candidat).resolve() == reel
            except OSError:
                continue
            if meme:
                raise ProjectMaintenanceError(
                    f"Le fichier annexe {relatif!r} est aussi declare par le lot "
                    f"{autre.get('lot_id')!r}. Le supprimer detruirait une sortie "
                    "d'un autre lot: aucune suppression n'a eu lieu. Corriger le "
                    "manifeste (deux lots ne partagent ni master ni planche) "
                    "avant de rejouer."
                )


def _rang_et_base_du_slug(slug: str) -> tuple[int, str]:
    """Le rang de version porte par un slug, et sa famille.

    **Une seule lecture du fragment, et elle colle a `EPIC11-ARB-88`** (trouve
    en revue, couche 2). Deux redactions coexistaient, et l'une acceptait un
    zero de tete : `validate_ingest_slug` autorise `S_v05` -- c'est un slug
    operateur legitime, la convention n'ecrivant jamais de zero -- pendant que
    la famille le lisait comme le rang 5 de `S`. Le dossier existait et
    `--scan S_v05` repondait « aucun dossier » : l'objet devenait non
    supprimable, sur deux verites portant le meme nom.
    """
    fragment = re.search(r"_v([0-9]+)$", slug)
    if fragment is None or fragment.group(1).startswith("0"):
        return version_ranks.RANG_ORIGINE, slug
    valeur = int(fragment.group(1))
    if not (naming.VERSION_RANK_MIN <= valeur <= naming.VERSION_RANK_MAX):
        return version_ranks.RANG_ORIGINE, slug
    return valeur, slug[: fragment.start()]


def _cible_fine_donnee(valeur: object) -> bool:
    """Une cible fine est DONNEE des qu'elle n'est ni absente ni baissee.

    **UN SEUL predicat pour la garde et pour la repartition** (revue
    `EPIC11-ARB-224`, couche 2 `C2-2`, couche 1 `C1-06` -- critique,
    destruction silencieuse, et REGRESSION mesuree des deux cotes).

    Le diff d'`EPIC11-ARB-224` a remplace `if valeur is not None` par
    `if valeur` dans la liste des cibles fines -- motive, puisque trois des
    quatre cibles etaient devenues des drapeaux nus. Mais `scan` est reste une
    CHAINE, et la chaine vide est le seul point ou les deux lectures divergent :
    elle etait **absente** pour les six gardes et **donnee** pour la
    repartition, restee en `is not None`.

    Ce que ca coutait, mesure : `--scan "" --planche --confirmer` rendait
    « Une seule cible fine a la fois » sur `0a00c9b06` et **detruisait la
    planche sans un mot**, code retour 0, sur `89fbd1d31`. Les cinq autres
    gardes tombaient avec elle -- `--avec-scans`, `--confirmer-dernier-lot`,
    l'exigence de `lot_id`, et `--version`, qui rendait alors un refus FAUX.

    `is not False` plutot que `is not None` : les trois drapeaux nus sont deja
    contraints a de VRAIS booleens par la garde « un entier n'est pas un
    drapeau », donc `False` y est leur seule facon d'etre absents, quand
    `scan=None` est la sienne. Un seul predicat couvre les deux natures sans
    en privilegier une.
    """
    return valeur is not None and valeur is not False


#: La restriction PROPRE a `remove`, ecrite une fois : le refus d'`encode`
#: annonce `native` parmi les valeurs admises, ce qui est vrai chez lui et faux
#: ici -- sa geometrie se tire des frames, que cette commande ne lit pas. Sans
#: cette phrase, le refus renverrait l'operateur vers une valeur que le refus
#: suivant lui reprendrait : le tourniquet qu'`EPIC11-ARB-89` interdit.
_SANS_NATIVE = (
    " Dans `remove`, `native` n'est pas admis: sa geometrie n'est connue qu'en"
    " sondant les frames du lot."
)


def _segment_de_resolution_demande(resolution: str | None) -> str:
    """Le segment de nom que produirait `--resolution <valeur>` a l'encodage.

    **La regle du PRODUCTEUR est APPELEE, plus jamais reecrite** (revue
    `EPIC11-ARB-224`, couche 1 `C1-01`, couche 2 `C2-1`, couche 3 `F7`). La
    redaction precedente annoncait dans cette meme docstring « la MEME regle
    qu'`encode.resolution_name_segment`, pas une seconde » (`EPIC5-ARB-78`) et
    comparait pourtant la chaine BRUTE au defaut. Or `encode` ne nomme jamais
    depuis la chaine brute : il passe par `resolve_output_resolution` puis
    `settle_resolution`, **qui normalise** -- « une taille personnalisee (ou
    native) qui coincide avec une entree du registre reprend son identifiant ».

    Mesure de la revue, sur six formes qu'`encode` accepte : `native`,
    `1920x1080` et `3840x2160` -- **les arguments memes qui ont produit le
    master** -- ne designaient AUCUN master. Quatre sur six. C'etait donc bien
    une seconde recette de nom, vivant sous une docstring qui affirmait le
    contraire, et defaisant la premisse d'`EPIC11-ARB-224` : « les memes
    arguments qui ont servi a les generer pour les identifier ».

    **Et la chaine VIDE detruisait le master par defaut** (`C2-1`, `F7`,
    destruction silencieuse, code retour 0). `""` n'etait ni `None` ni
    l'identifiant du defaut : elle sortait donc par le chemin nominal en
    rendant `""`, qui est exactement le segment du nom par defaut. Regime reel :
    `--resolution "$RES"` avec la variable non definie. Elle est desormais
    refusee par la porte du producteur elle-meme (`_parse_custom_resolution`
    n'y voit aucun separateur), sans qu'aucune garde de ce module n'ait a
    recopier ce jugement.

    Deux refus NOMMES plutot qu'un blocage sec (`EPIC11-ARB-89`) : `native` dit
    pourquoi il ne peut pas etre arrete ici et par quoi le remplacer ; toute
    autre valeur retombe sur le refus d'`encode`, qui liste les identifiants du
    registre et la forme `<largeur>x<hauteur>`.

    L'import est LOCAL parce qu'`encode` tire la chaine d'encodage entiere, et
    que `project_maintenance` est appele par des chemins qui n'en ont pas
    besoin.
    """
    from .encode import (
        EncodeDecisionError,
        NATIVE_RESOLUTION_KEYWORD,
        resolution_name_segment,
        resolve_output_resolution,
        settle_resolution,
    )

    if resolution is None:
        return ""
    try:
        demande = resolve_output_resolution(resolution)
    except EncodeDecisionError as erreur:
        raise ProjectMaintenanceError(
            f"--resolution {resolution!r} ne nomme aucune resolution. "
            f"{erreur}{_SANS_NATIVE} Aucune suppression n'a eu lieu."
        ) from erreur
    if demande.size is None:
        # `native` est la seule demande dont la geometrie n'est pas connue de
        # l'argument : `settle_resolution` la tire des frames du lot, que cette
        # commande ne lit pas. La refuser NOMMEMENT vaut mieux que de la faire
        # retomber en silence sur le defaut -- c'est le meme defaut que la
        # chaine vide, un cran plus haut.
        raise ProjectMaintenanceError(
            f"--resolution {resolution!r} ne se resout pas ici: la geometrie "
            f"de {NATIVE_RESOLUTION_KEYWORD!r} n'est connue qu'en sondant les "
            "frames du lot, et `remove` ne les lit pas. Donner la resolution "
            "par son identifiant de registre, ou par la geometrie que le nom "
            "du master porte (<largeur>x<hauteur>). Aucune suppression n'a eu "
            "lieu."
        )
    # `settle_resolution` ne consulte la geometrie SOURCE que pour une demande
    # `native`, ecartee juste au-dessus : lui rendre celle de la demande n'est
    # donc pas un faux-semblant, c'est la meme geometrie.
    arretee = settle_resolution(demande, demande.size)
    return resolution_name_segment(arretee) or ""


def _segment_de_resolution_declare(
    chemin: str, lot_id: str, profil: str, rang: int
) -> str | None:
    """Le segment de resolution que porte le NOM d'un master declare.

    `""` quand le nom n'en porte aucun -- c'est le defaut --, et `None` quand
    le nom ne suit pas la recette (`build_master_filename`), donc quand rien
    ne peut en etre derive : un master renomme a la main est dans ce cas, et
    le distinguer du defaut est indispensable, sinon il serait apparie a
    l'aveugle avec la resolution par defaut.

    **La resolution n'est PAS un champ de l'inventaire**, et c'est ecrit dans
    `encode._rangs_de_masters` : « elle est lisible du fichier ; la persister
    creerait une seconde verite, le nom est son seul porteur ». La derivation
    passe donc par le nom -- et le PREFIXE qu'elle retire est celui que
    `build_master_filename` produit lui-meme, plutot qu'un `f"{lot}_mmu_{p}"`
    reecrit ici : deux recettes pour le meme fait sont deux verites.
    """
    nom = PurePosixPath(chemin).name
    tige, _, _extension = nom.rpartition(".")
    if not tige:
        return None
    if rang != version_ranks.RANG_ORIGINE:
        try:
            suffixe = naming.format_version_suffix(rang)
        except naming.NamingError:
            return None
        if not tige.endswith(suffixe):
            return None
        tige = tige[: -len(suffixe)]
    try:
        prefixe = PurePosixPath(naming.build_master_filename(
            lot_id=lot_id, profile_id=profil, container="x")).stem
    except naming.NamingError:
        return None
    if tige == prefixe:
        return ""
    if tige.startswith(prefixe + "_"):
        return tige[len(prefixe) + 1:]
    return None


def _refuser_un_designateur_versionne(option: str, valeur: str, nu: str) -> None:
    """`EPIC11-ARB-224` : le designateur nomme la FAMILLE, `--version` le rang.

    Sans ce refus, `--scan S_v3` designerait la famille `S_v3` -- qui n'existe
    pas -- et l'operateur lirait « aucun scan de ce nom », ce qui est vrai mais
    illisible : la panne est dans la GRAMMAIRE, pas dans le manifeste. C'est
    aussi le seul endroit ou la moitie CLI de `Q12` se ferme, puisque plus
    aucune chaine saisie ne porte alors de fragment de rang.
    """
    rang, _base = _rang_et_base_du_slug(nu)
    if rang == version_ranks.RANG_ORIGINE:
        return
    raise ProjectMaintenanceError(
        f"{option} nomme une FAMILLE, jamais une version: {valeur!r} porte le "
        f"fragment `_v{rang}`. Le rang se donne par --version {rang}. Aucune "
        "suppression n'a eu lieu."
    )


def _slug_valide(slug: object) -> str | None:
    """Un slug d'ingestion utilisable comme SEGMENT sous `scans/`, ou `None`.

    `_sous_le_projet` ne suffit pas ici et la revue l'a mesure: un slug
    `../frames/<autre lot>` RESTE sous le projet, donc passe la garde -- et
    fait supprimer les frames d'un autre lot, avec `supprime=True` et sans un
    mot, pendant que le manifeste continue de declarer ce lot. C'est
    litteralement l'incident du 2026-08-27 que ce module existe pour empecher.
    Le banc ne couvrait que la variante SORTANTE (`../../evasion`): une moitie
    du domaine.
    """
    if not isinstance(slug, str) or not slug:
        return None
    if slug in (".", "..") or PurePosixPath(slug).parts != (slug,):
        raise ProjectMaintenanceError(
            f"Slug d'ingestion invalide au manifeste: {slug!r}. Un slug est un "
            "SEGMENT de chemin sous `scans/`, jamais un chemin: il ne porte ni "
            "separateur, ni `.`, ni `..`. Aucune suppression n'a eu lieu."
        )
    return slug


def _scans_du_lot(
    project_dir: Path, manifest: Mapping[str, Any], lot: Mapping[str, Any]
) -> list[Path]:
    """TOUS les dossiers de scan de ce lot -- filiation INVERSE et DIFFEREE.

    C'est la troisieme nature de filiation de ce module, et la plus fragile des
    trois. Il faut la dire en entier plutot que la subir.

    **Pourquoi elle est differee.** A l'ingestion, le lot n'est pas connu : le
    nom du dossier (`scans/<slug>/`) est un slug OPERATEUR, ce que la personne a
    tape, et l'identite du lot est portee par le QR imprime sur les planches,
    decode a l'etape suivante seulement (`scan_lot_dir`, story 5.1). Le lien
    n'existe donc qu'APRES reconstruction.

    **Ce qui a change le 2026-08-31** (`EPIC11-ARB-109`, choix d'Egan : « un
    historique par lot »). Cette fonction lisait la section `reconstruction` de
    tete, qui est SINGULIERE -- un projet n'en porte qu'une, celle de la
    derniere passe. Un lot reconstruit puis suivi d'un autre perdait donc la
    trace de son scan, et la suppression rendait `None` : l'operateur
    retombait sur le `rm -rf` manuel, la fuite meme que cette commande ferme.
    Elle lit desormais `lots[].reconstructions`, registre DURABLE porte par le
    lot, et rend TOUS ses dossiers -- un lot rescanne depuis deux slugs en a
    deux, et n'en oublier qu'un laisserait des images derriere.

    **Le repli sur la section de tete est conserve** pour les manifestes
    ecrits avant ce registre: sans lui, la suppression des scans regresserait
    sur tout projet existant.

    **Et pourquoi le lien ne suffit pas a supprimer.** Un dossier de scan
    contient des images de planches PAPIER numerisees : les refaire coute un
    passage au scanner, pas un calcul. Les rendre ici ne les supprime pas -- il
    faut le consentement explicite de `avec_scans`.
    """
    slugs: list[str] = []

    for entree in lot.get("reconstructions") or []:
        if not isinstance(entree, Mapping):
            continue
        slug = _slug_valide(entree.get("ingest_slug"))
        if slug is not None and slug not in slugs:
            slugs.append(slug)

    if not slugs:
        # REPLI, manifeste anterieur au registre. La section de tete ne vaut
        # que si elle parle bien de CE lot: un lien qui designe un autre lot ne
        # se devine pas par ressemblance de nom -- ce serait le `rm -rf` a
        # l'aveugle que ce module remplace.
        reconstruction = manifest.get("reconstruction")
        if isinstance(reconstruction, Mapping) \
                and reconstruction.get("lot_id") == lot.get("lot_id"):
            scan = reconstruction.get("scan")
            if isinstance(scan, Mapping):
                slug = _slug_valide(scan.get("ingest_slug"))
                if slug is not None:
                    slugs.append(slug)

    return [
        _sous_le_projet(
            project_dir, project_dir / SCANS_DIRNAME / slug, "ingest_slug", slug)
        for slug in slugs
    ]

def _annexes_du_lot(
    project_dir: Path,
    manifest: Mapping[str, Any],
    lot: Mapping[str, Any],
    autres_lots: list | None = None,
) -> tuple[list[Path], list[str]]:
    """Les sorties LOURDES du lot -- masters encodes et PDF de planches.

    Rend `(fichiers presents, chemins attendus mais absents)`. Le second
    terme n'est pas du confort : sans lui, un PDF renomme a la main ou un
    master deja efface disparaissent du rapport, et l'operateur croit avoir
    tout libere alors qu'un fichier de plusieurs centaines de Mo reste.

    Ce sont des FICHIERS, pas des dossiers : `outputs/` et `planches/` sont
    partages entre tous les lots du projet, on n'y supprime jamais le
    dossier, seulement les entrees que CE lot declare.
    """
    presents: list[Path] = []
    absents: list[str] = []
    relatifs = list(_masters_declares(lot))
    planches = _planche_pdf_declaree(project_dir, manifest, lot)
    if isinstance(planches, _Declares):
        # DECLAREES au manifeste : toutes sont attendues, y compris absentes.
        # C'est ce que l'inventaire apporte de neuf -- un tirage renomme a la
        # main garde une entree, et son absence a l'emplacement promis se dit
        # au lieu de disparaitre du rapport.
        relatifs.extend(planches)
    elif planches:
        # DEDUITES d'un recalcul de nom (manifeste anterieur a l'inventaire) :
        # seul le tirage de rang 1 est attendu, les 98 autres ne sont
        # signales que s'ils existent -- sans quoi chaque suppression
        # rapporterait 98 absences qui n'apprennent rien.
        relatifs.append(planches[0])
        relatifs.extend(r for r in planches[1:] if (project_dir / r).is_file())

    for relatif in relatifs:
        chemin = _sous_le_projet(project_dir, project_dir / relatif, "annexe", relatif)
        _refuser_l_annexe_partagee(
            project_dir, chemin.resolve(), relatif, autres_lots or [], manifest
        )
        if chemin.is_file():
            presents.append(chemin)
        else:
            absents.append(PurePosixPath(relatif).as_posix())
    return presents, absents


def _chemins_a_supprimer(project_dir: Path, fichiers: list[Path]) -> tuple[str, ...]:
    """Les `fichiers` en chemins relatifs POSIX, TRIES par chemin complet.

    Remplace le classement par nature retire par `EPIC11-ARB-199`.

    **L'ordre est celui du chemin POSIX complet** (`EPIC11-ARB-243`, tranche
    par Egan le 2026-09-05 : « Trier dans le coeur, par chemin complet.
    L'apercu redevient parcourable ET comparable ligne a ligne entre deux
    executions -- c'est le geste reel d'un operateur qui hesite avant de
    detruire. »). Les dossiers ressortent donc groupes et les frames dans
    l'ordre de leurs numeros, quelle que soit la maniere dont les appelants
    ont assemble leur liste.

    **Ce que cet ordre remplace, et pourquoi il fallait le remplacer.** La
    redaction precedente rendait « l'ordre recu », presente comme « le seul
    stable et le seul que l'operateur reconnaisse » ; la revue 11.13 (couche 1
    F2, couche 2 F9, couche 3 F1 et F5) l'a mesure faux sur les deux moities.
    Pour le chemin du lot, la liste recue venait de `_fichiers_du_lot`, qui
    peuple par `dossier.rglob("*")` : l'ordre etait celui de `os.scandir`.
    Mesure sur douze frames : ni l'ordre de creation, ni l'ordre alphabetique,
    et rien ne le garantissait d'un `ext4` a un `APFS`. Sur un lot 4K a 12 im/s
    -- des milliers de lignes, le cas meme que la commande existe pour servir
    --, une liste que l'on ne peut ni parcourir ni comparer a l'apercu
    precedent n'est pas une defense contre une destruction.

    **Le tri est TOTAL et il est pose ici, au lieu unique de la projection**,
    donc il vaut pour les trois appelants -- suppression d'un tirage, delien,
    suppression d'un lot -- et il recouvre toutes les sources d'une meme liste
    (frames, annexes, scans), que les appelants concatenent bloc par bloc. Le
    tri de `_fichiers_du_lot`, lui, ordonne la liste de fichiers reelle, donc
    la boucle `unlink()` : les deux tris portent la meme cle
    (`_cle_de_tri_posix`) et ne peuvent pas diverger.

    La projection reste fidele au CARDINAL : un chemin d'entree pour un chemin
    de sortie, sans filtre et **sans deduplication** (mesure par
    `test__chemins_a_supprimer_est_une_projection_FIDELE_sans_deduplication`).
    Un tri n'est pas une deduplication -- une entree repetee ressort deux fois,
    desormais cote a cote --, et l'y glisser resterait un correctif
    d'AFFICHAGE : l'apercu cesserait de montrer le doublon pendant que la
    boucle `unlink()` continuerait de passer deux fois. Le doublon se ferme la
    ou il nait (dette `11.13-D1`).

    Lieu UNIQUE du calcul `relative_to(...).as_posix()` pour le rapport : les
    trois appelants passent par ici plutot que de recopier la recette.
    """
    return tuple(sorted(_cle_de_tri_posix(project_dir, chemin) for chemin in fichiers))


def _ecrire_manifeste(manifest_path: Path, manifest: Mapping[str, Any]) -> None:
    """Ecriture ATOMIQUE : temp file dans le meme dossier, fsync, puis
    `os.replace` (trouve en revue -- l'ecriture directe d'avant laissait un
    `project.json` tronque en cas de crash pendant le `write_text`, sur le
    modele exact que `io/extraction_manifest._atomic_write` documente deja
    « Ordre non negociable » pour la persistance d'extraction)."""
    contenu = json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    descripteur, chemin_temp = tempfile.mkstemp(
        dir=str(manifest_path.parent), prefix=f".{manifest_path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(descripteur, "w", encoding="utf-8") as flux:
            flux.write(contenu)
            flux.flush()
            os.fsync(flux.fileno())
        os.replace(chemin_temp, manifest_path)
    except BaseException:
        try:
            os.unlink(chemin_temp)
        except OSError:
            pass
        raise


def _ligne_d_eau_de_la_famille_du_lot(
    manifest: Mapping[str, Any], lot: Mapping[str, Any]
) -> tuple[str | None, int, set[int]]:
    """La famille d'un lot, sa ligne d'eau et les rangs qui lui RESTERONT.

    Rend `(base_id, ligne, rangs_restants)`. `base_id` vaut `None` quand le lot
    n'appartient a aucune famille versionnee -- il n'y a alors pas de ligne
    d'eau a tenir.
    """
    base_id = lot.get("base_lot_id") or lot.get("lot_id")
    if not isinstance(base_id, str) or not base_id:
        return None, version_ranks.RANG_ORIGINE, set()
    employes = rangs_employes_de_la_famille(manifest, base_id)
    lignes = manifest.get(LOT_WATERMARKS_FIELD)
    declaree = lignes.get(base_id) if isinstance(lignes, Mapping) else None
    ligne = version_ranks.ligne_d_eau(declaree, employes)
    rang = lot.get("version_rank")
    rang = rang if isinstance(rang, int) and not isinstance(rang, bool) \
        else version_ranks.RANG_ORIGINE
    return base_id, ligne, employes - {rang}


def _poser_la_ligne_d_eau_du_lot(
    manifest: dict, base_id: str, ligne: int, rangs_restants: set[int],
    liberer_le_rang: bool, en_queue: bool,
) -> None:
    """Ecrire (ou faire redescendre) `lot_version_watermarks[base_id]`.

    **C'est la piece qui manquait, et son absence retournait l'arbitrage**
    (trouve par les TROIS couches de la revue du 2026-08-31). Le champ etait
    declare au schema et lu par le resolveur, mais aucun chemin ne l'ecrivait :
    retirer la version 3 d'une famille faisait retomber le prochain rang a 3,
    c'est-a-dire rendre le rang PAR DEFAUT et sans demande -- l'inverse exact
    d'`EPIC11-ARB-92`, dont le point 3 dit « jamais par defaut ».

    Le geste est le meme que pour les planches, et c'est le propos
    d'`EPIC11-ARB-108` : « il n'y a pas de mecanisme different par objet ».
    """
    lignes = manifest.get(LOT_WATERMARKS_FIELD)
    if not isinstance(lignes, dict):
        lignes = {}
    if liberer_le_rang and en_queue:
        nouvelle = max(rangs_restants or {0})
        if nouvelle > version_ranks.RANG_ORIGINE:
            lignes[base_id] = nouvelle
        else:
            # Rendre jusqu'a l'ORIGINE, c'est RETIRER la cle (`EPIC11-ARB-88`,
            # omission stricte) -- l'ecrire a 1 laisserait une ligne DECLAREE.
            lignes.pop(base_id, None)
    elif ligne > version_ranks.RANG_ORIGINE:
        # Sans la demande explicite, la ligne est POSEE telle quelle : la
        # deduire du plus haut rang restant reviendrait a liberer en silence.
        lignes[base_id] = ligne
    else:
        # **Une famille qui n'a jamais depasse l'origine n'a rien a memoriser**
        # (trouve en revue, couche 2). La redaction d'avant ecrivait
        # `{"<lot>": 1}` a CHAQUE suppression de lot ordinaire : une cle morte
        # par lot supprime, et precisement ce que la branche des tirages venait
        # de corriger -- « l'ecrire a 1 laisserait une ligne DECLAREE ».
        lignes.pop(base_id, None)
    if lignes:
        manifest[LOT_WATERMARKS_FIELD] = lignes
    else:
        manifest.pop(LOT_WATERMARKS_FIELD, None)


#: Les noms des champs de ligne d'eau, importes plutot que recopies : chacun
#: appartient au module qui le RESOUT, et une seconde ecriture de la chaine
#: serait une seconde verite (`EPIC5-ARB-78`).
SCAN_WATERMARKS_FIELD = "scan_version_watermarks"
OUTPUT_FRAMES_WATERMARK_FIELD = "output_frames_version_watermark"
#: **Celui-ci l'est vraiment depuis le 2026-09-03** (story 11.8) : il etait
#: recopie ici alors que le commentaire ci-dessus promettait un import, et il
#: n'etait declare NULLE PART ailleurs -- le champ vivait dans le module qui le
#: retire et dans aucun de ceux qui l'ecrivent. Brancher l'ecriture sans le
#: rapatrier chez son producteur aurait fige deux litteraux de la meme chaine
#: dans deux modules qui la font bouger en sens inverse.
MASTERS_WATERMARK_FIELD = ENCODE_MASTERS_WATERMARK_FIELD


@dataclass(frozen=True)
class _FamilleVersionnee:
    """Ce qu'il faut savoir d'une famille pour lui appliquer LA regle.

    `EPIC11-ARB-108` : « il n'y a pas de mecanisme different par objet ». Ce
    descripteur existe pour que la regle -- ligne d'eau, condition de queue,
    queue liberable, refus nomme -- soit ecrite UNE fois dans
    `_retirer_un_objet_versionne` et parametree ici, plutot que recopiee pour
    chaque nouvelle cible. Recopier serait exactement le defaut que la revue du
    2026-08-31 a trouve dans ce module meme.
    """

    #: Le mot qui nomme l'objet dans les messages (« master », « scan », ...).
    nom: str
    #: L'identifiant lisible de la cible, pour le rapport.
    cible: str
    #: Les rangs que la famille DECLARE encore, cible comprise.
    rangs_declares: set[int]
    #: La ligne d'eau telle qu'elle est persistee, ou n'importe quoi d'autre.
    ligne_declaree: object
    #: Le rang de la cible.
    rang: int
    #: Les fichiers a supprimer si la suppression est confirmee.
    fichiers: tuple[Path, ...]
    #: Retirer l'entree de la cible du manifeste (mutation en place).
    retirer_l_entree: Callable[[], None]
    #: Poser la ligne d'eau, ou la RETIRER quand l'argument est `None` --
    #: l'omission stricte est ce qui dit l'origine (`EPIC11-ARB-88`).
    poser_la_ligne: Callable[[int | None], None]
    #: Cet objet a-t-il un rang PROPRE, ou son rang est-il celui de son
    #: contenant ?
    #:
    #: **`EPIC11-ARB-108` dit que le mecanisme est le meme partout ; il ne dit
    #: pas que tout objet porte un rang.** Le jeu de frames extraites d'un lot
    #: est le contre-exemple mesure : son dossier est nomme par
    #: `project_layout.extract_frames_dir(..., version_rank=)`, qui recoit le
    #: rang du LOT -- `extraction._build_lot` ecrit `frames_dir` a partir du
    #: meme `version_rank` que `lot_id`. Il n'y a donc pas deux familles mais
    #: une : `extract-frames/rush-a_24` et `extract-frames/rush-a_24_v2` sont
    #: les dossiers de DEUX LOTS, pas deux versions du meme jeu.
    #:
    #: Traiter ce jeu comme une famille a lui aurait un effet, et il est
    #: destructeur : `liberer_le_rang` rendrait le rang du lot alors que
    #: l'entree du lot RESTE au manifeste, si bien que le lot suivant
    #: reprendrait un numero deja porte. Le drapeau porte donc ce fait plutot
    #: que de le laisser deviner, et le refus qui va avec est NOMME.
    rang_independant: bool = True
    #: Le mot qui nomme le CONTENANT porteur du rang, quand `rang_independant`
    #: est faux. Il n'a de sens que la, et le refus le nomme : « son rang est
    #: celui du lot qui le porte » se lit, « son rang est celui de son
    #: contenant » ne se lit pas.
    contenant: str = "lot"


def _refus_de_rang_non_independant(objet: str, contenant: str, option: str) -> str:
    """Le texte du refus quand on demande un rang a un objet qui n'en a pas.

    **Ecrit UNE fois pour deux appelants** -- la garde d'arguments de
    :func:`remove_project_element` et :func:`_retirer_un_objet_versionne` --,
    pour la meme raison que `version_ranks.refus_de_liberer_hors_queue` : deux
    redactions du meme refus divergent au premier ajustement, et celle-ci
    porte sur un geste destructeur.

    **Deux issues nommees, jamais un mur** (`EPIC11-ARB-89`) : viser le
    contenant, qui porte le rang pour de bon, ou renoncer au rang et ne
    retirer que le contenu.
    """
    return (
        f"{option} ne s'applique pas a un {objet}: il n'a pas de rang PROPRE, "
        f"son rang est celui du {contenant} qui le porte. Deux issues: viser "
        f"le {contenant} lui-meme, dont le rang vit dans son identifiant "
        f"(`EPIC11-ARB-221`), ou retirer le {objet} seul -- son contenu part, "
        f"le rang du {contenant} reste porte par une entree qui existe "
        "toujours. Aucune suppression n'a eu lieu."
    )


def _ligne_d_eau_inexistante(_valeur: int | None) -> None:
    """La ligne d'eau d'un objet qui n'a pas de rang propre : il n'y en a pas.

    **Une levee plutot qu'un `pass`**, et c'est le point. Une fonction muette
    posee ici serait exactement la « surface morte » que la revue du
    2026-08-31 a trouvee sur quatre champs de ligne d'eau -- declaree, lue,
    ecrite par personne, et retournant l'arbitrage en silence. Celle-ci rend
    le defaut BRUYANT : si `_retirer_un_objet_versionne` appelait un jour la
    ligne d'eau d'une famille sans rang propre, la campagne le verrait au lieu
    de le laisser passer.
    """
    raise ProjectMaintenanceError(
        "Defaut interne: une ligne d'eau a ete posee sur un objet qui n'a pas "
        "de rang propre. Aucune suppression n'a eu lieu."
    )


def _poser_les_lignes_d_eau_des_scans(
    project_dir: Path, manifest: dict, lot: Mapping[str, Any]
) -> None:
    """Consommer les rangs des scans qu'une suppression de lot emporte.

    Sans elle, `--avec-scans` rendait toute la famille de scans par defaut :
    les dossiers partaient, plus rien ne portait leur rang, et le resolveur
    repartait de l'origine. Le meme defaut que pour les lots, sur le chemin qui
    detruit ce qui coute un passage au scanner a refaire.
    """
    familles: dict[str, set[int]] = {}
    for entree in lot.get("reconstructions") or []:
        if not isinstance(entree, Mapping):
            continue
        try:
            slug = _slug_valide(entree.get("ingest_slug"))
        except ProjectMaintenanceError:
            continue
        if slug is None:
            continue
        rang, base = _rang_et_base_du_slug(slug)
        familles.setdefault(base, set()).add(rang)
    if not familles:
        return
    lignes = manifest.get(SCAN_WATERMARKS_FIELD)
    lignes = dict(lignes) if isinstance(lignes, Mapping) else {}
    for base, rangs in familles.items():
        lignes[base] = version_ranks.ligne_d_eau(lignes.get(base), rangs)
    manifest[SCAN_WATERMARKS_FIELD] = lignes


def _retirer_un_objet_versionne(
    project_dir: Path, manifest_path: Path, manifest: dict,
    famille: _FamilleVersionnee, dry_run: bool, liberer_le_rang: bool,
) -> RapportSuppression:
    """LA regle de retrait, ecrite une fois pour toutes les familles.

    Elle est le pendant exact de `io/version_ranks.py` cote LIBERATION : ce
    module-la dit comment un rang s'attribue, celle-ci comment il se rend. Les
    deux appellent les memes quatre fonctions, et c'est le propos
    d'`EPIC11-ARB-108`.
    """
    ligne = version_ranks.ligne_d_eau(famille.ligne_declaree, famille.rangs_declares)
    # **Un objet SANS rang propre n'entre dans aucune des deux branches de la
    # regle**, et c'est mesure plutot que suppose : `est_en_queue(1, 1)` rend
    # `True`, si bien qu'un jeu de frames extraites aurait ete declare « dernier
    # a date » et aurait ouvert le choix de rendre un rang qui appartient a son
    # lot. Le drapeau coupe la branche a sa racine, et le refus est NOMME --
    # jamais le refus « hors queue », qui parlerait d'un rang posterieur qui
    # n'existe pas.
    en_queue = (
        version_ranks.est_en_queue(famille.rang, ligne)
        if famille.rang_independant else False
    )
    if liberer_le_rang and not famille.rang_independant:
        raise ProjectMaintenanceError(
            _refus_de_rang_non_independant(
                famille.nom, famille.contenant, "liberer_le_rang="))
    if liberer_le_rang and not en_queue:
        raise ProjectMaintenanceError(
            version_ranks.refus_de_liberer_hors_queue(famille.rang, ligne, famille.nom)
            + " Aucune suppression n'a eu lieu."
        )

    restants = famille.rangs_declares - {famille.rang}
    liberables = version_ranks.rangs_liberables(ligne, restants) if en_queue else ()
    presents = tuple(c for c in famille.fichiers if c.exists())
    absents = tuple(
        sorted(
            c.relative_to(project_dir).as_posix()
            for c in famille.fichiers if not c.exists()
        )
    )
    # **Les DOSSIERS se developpent** (trouve en revue, couche 1). Le filtre
    # `is_file()` rendait une liste vide pour `--scan` et `--frames`, dont les
    # cibles sont des arborescences : l'apercu annoncait « 0 fichier(s) » avant
    # de supprimer huit TIFF, sans la liste ni l'avertissement d'irreversible.
    # L'operateur confirmait a l'aveugle exactement ce que le mode apercu
    # existe pour lui montrer -- et le chemin `--avec-scans`, lui, les
    # enumerait deja un par un : la cible fine regressait sur le seul point qui
    # justifie l'apercu.
    a_rapporter: list[Path] = []
    for chemin in presents:
        if chemin.is_dir() and not chemin.is_symlink():
            a_rapporter.extend(c for c in chemin.rglob("*") if c.is_file())
        else:
            a_rapporter.append(chemin)
    fichiers_a_supprimer = _chemins_a_supprimer(project_dir, a_rapporter)

    if dry_run:
        return RapportSuppression(
            cible=famille.cible, fichiers_a_supprimer=fichiers_a_supprimer,
            dry_run=True, supprime=False, fichiers_attendus_absents=absents,
            tirage_en_queue=en_queue, rangs_liberables=liberables,
            rang_libere=bool(liberer_le_rang and en_queue), rang_vise=famille.rang,
            rang_independant=famille.rang_independant,
        )

    # LE MANIFESTE D'ABORD (AC 10) : un echec de suppression de fichier laisse
    # alors un manifeste coherent avec ce qui reste lisible. La copie d'avant
    # sert au rollback du bas de fonction.
    avant = json.loads(json.dumps(manifest))
    famille.retirer_l_entree()
    if liberer_le_rang and en_queue:
        nouvelle = max(restants or {0})
        famille.poser_la_ligne(
            nouvelle if nouvelle > version_ranks.RANG_ORIGINE else None)
    elif en_queue:
        # Sans la demande explicite, la ligne est POSEE telle quelle : la
        # deduire du plus haut rang restant reviendrait a liberer en silence.
        famille.poser_la_ligne(ligne)
    _ecrire_manifeste(manifest_path, manifest)

    echecs: list[str] = []
    for chemin in presents:
        try:
            if chemin.is_dir() and not chemin.is_symlink():
                shutil.rmtree(chemin)
            else:
                chemin.unlink()
        except OSError:
            echecs.append(chemin.relative_to(project_dir).as_posix())
    # **Un echec partiel RESTAURE le manifeste** (trouve en revue, couche 1),
    # comme le chemin du lot entier le fait deja et pour le motif qu'il ecrit :
    # la cible se resout PAR le manifeste, si bien que retirer l'entree alors
    # que le fichier survit rendait l'objet introuvable -- le rejeu repondait
    # « ne declare aucun master a ce chemin », donc zero issue, et l'operateur
    # retombait sur le `rm -rf` manuel que cette commande existe pour fermer.
    if echecs:
        _ecrire_manifeste(manifest_path, avant)
    return RapportSuppression(
        cible=famille.cible, fichiers_a_supprimer=fichiers_a_supprimer,
        dry_run=False, supprime=not echecs,
        fichiers_non_supprimes=tuple(sorted(echecs)),
        fichiers_attendus_absents=absents,
        tirage_en_queue=en_queue, rangs_liberables=liberables,
        rang_libere=bool(liberer_le_rang and en_queue and not echecs),
        rang_vise=famille.rang,
        rang_independant=famille.rang_independant,
    )


def _rang_d_une_entree(entree: Mapping[str, Any]) -> int:
    valeur = entree.get("version_rank")
    if isinstance(valeur, int) and not isinstance(valeur, bool):
        return valeur
    return version_ranks.RANG_ORIGINE


def _rangs_des_dossiers(racine: Path, base: str, exclus: set[str]) -> dict[int, Path]:
    """Les rangs dont le DOSSIER existe, pour la famille `base`.

    `exclus` porte les noms qui appartiennent a une AUTRE famille -- le defaut
    de collision trouve en revue : `output-frames/<lot>_v2` est le dossier du
    LOT v2, pas le rescan v2 du lot d'origine.
    """
    trouves: dict[int, Path] = {}
    if not racine.is_dir():
        return trouves
    presents = {c.name: c for c in racine.iterdir() if c.is_dir()}
    for rang in [version_ranks.RANG_ORIGINE,
                 *range(naming.VERSION_RANK_MIN, naming.VERSION_RANK_MAX + 1)]:
        nom = base if rang == version_ranks.RANG_ORIGINE else (
            f"{base}{naming.format_version_suffix(rang)}")
        if nom in presents and nom not in exclus:
            trouves[rang] = presents[nom]
    return trouves


def _slug_du_lot_scanne(lot: Mapping[str, Any]) -> str:
    """Le slug du dossier de frames scannees de ce lot, par la recette de l'ecrivain.

    `scan_output_frames.derive_lot_dir_slug` est le seul lieu de cette recette ;
    la recopier ici en serait une seconde (`EPIC5-ARB-78`). Le manifeste, quand
    il declare `output_frames_dir`, prime sur tout recalcul.
    """
    from .scan_output_frames import derive_lot_dir_slug

    return derive_lot_dir_slug(
        rush_id=str(lot.get("rush_id") or ""),
        fps_target=lot.get("fps_target"),
        lot_id=str(lot.get("lot_id") or ""),
    )


def _famille_de_master(
    project_dir: Path, manifest: dict, lot: Mapping[str, Any],
    profil: str, resolution: str | None, rang_vise: int,
) -> _FamilleVersionnee:
    """La famille d'un master, identifiee par les ARGUMENTS QUI L'ONT PRODUIT.

    `EPIC11-ARB-224`, second temps, verbatim d'Egan : « pourquoi designer
    l'emplacement des masters ? [...] Avec le lot, le codec et la version
    l'outil sait retrouver le master precis. Son emplacement, de plus, est au
    manifeste non ? » -- oui, et c'est lui qui le sait. Demander un chemin a
    l'operateur, c'est lui demander de recalculer ce que l'outil a ecrit.

    Le profil reste ce qui borne la famille (story 6.5) : un lot porte
    legitimement plusieurs masters -- mezzanine et derivee, profils et
    resolutions differents --, et deux masters de profils differents ne sont
    pas deux versions l'un de l'autre (`cle_de_famille_de_master`).

    **`resolution` n'est exigee que lorsqu'elle LEVE une ambiguite**, et le
    refus nomme alors les resolutions declarees plutot que d'en deviner une.
    L'exiger toujours ferait taper un argument inutile dans le cas courant --
    un lot n'a le plus souvent qu'une resolution par profil.

    **L'ambiguite non levable est REFUSEE, pas resolue par `next()`**, et
    c'est le prix -- dit plutot que tu -- du retrecissement du designateur :
    le chemin etait unique par construction, le couple ne l'est pas. Prendre
    la premiere entree ferait detruire une sortie que l'operateur ne visait
    pas, ce qui est la meme famille de defaut que « le scan d'un AUTRE lot ».
    """
    lot_id = str(lot.get("lot_id") or "")
    entrees = [
        e for e in (lot.get("encoded_masters") or [])
        if isinstance(e, Mapping) and isinstance(e.get("path"), str) and e["path"]
    ]
    du_profil = [e for e in entrees if e.get("profile_id") == profil]
    if not du_profil:
        profils = sorted({str(e.get("profile_id")) for e in entrees})
        raise ProjectMaintenanceError(
            f"Le lot {lot_id!r} ne declare aucun master au profil {profil!r}. "
            f"Profils declares: {profils or 'aucun'}. Aucune suppression n'a "
            "eu lieu."
        )
    au_rang = [e for e in du_profil if _rang_d_une_entree(e) == rang_vise]
    if not au_rang:
        rangs = sorted({_rang_d_une_entree(e) for e in du_profil})
        raise ProjectMaintenanceError(
            f"Le lot {lot_id!r} ne declare aucun master au profil {profil!r} "
            f"et au rang {rang_vise}. Rangs declares pour ce profil: {rangs}. "
            "Aucune suppression n'a eu lieu."
        )

    def _segment(entree: Mapping[str, Any]) -> str | None:
        return _segment_de_resolution_declare(
            entree["path"], lot_id, profil, _rang_d_une_entree(entree))

    def _lisible(segment: str | None) -> str:
        if segment == "":
            return "(defaut)"
        return "(nom non conforme)" if segment is None else segment

    segments = {_segment(e) for e in au_rang}
    if resolution is None and len(segments) > 1:
        # **Le refus NOMME ce qui est declare, il ne devine pas.** Prendre la
        # premiere entree detruirait la sortie par defaut sous les yeux d'un
        # operateur qui visait l'autre resolution -- et l'ordre de la liste
        # n'est meme pas une information, c'est l'ordre d'ecriture.
        # **Une entree dont le nom ne suit pas la recette n'est atteignable
        # par AUCUNE `--resolution`**, et le taire ferait tourner l'operateur
        # en rond entre un refus qui propose un argument et un argument qui ne
        # rend rien. Le refus dit donc la limite en meme temps que l'issue.
        illisible = (
            " Une des entrees porte un nom qui ne suit pas la recette de"
            " `build_master_filename`: aucune --resolution ne la designe, il"
            " faut corriger le manifeste."
            if None in segments else ""
        )
        raise ProjectMaintenanceError(
            f"Le lot {lot_id!r} declare plusieurs resolutions au profil "
            f"{profil!r} et au rang {rang_vise}: "
            f"{', '.join(sorted(_lisible(s) for s in segments))}. "
            f"Preciser --resolution pour lever l'ambiguite.{illisible} "
            "Aucune suppression n'a eu lieu."
        )
    if resolution is None:
        candidats = list(au_rang)
    else:
        vise = _segment_de_resolution_demande(resolution)
        candidats = [e for e in au_rang if _segment(e) == vise]
        if not candidats:
            lisibles = sorted(_lisible(s) for s in segments)
            raise ProjectMaintenanceError(
                f"Le lot {lot_id!r} ne declare aucun master au profil "
                f"{profil!r}, au rang {rang_vise} et a la resolution "
                f"{resolution!r}. Resolutions declarees a ce rang: "
                f"{', '.join(lisibles)}. Aucune suppression n'a eu lieu."
            )
    if len(candidats) > 1:
        conflit = sorted(str(e["path"]) for e in candidats)
        raise ProjectMaintenanceError(
            f"Le lot {lot_id!r} declare {len(candidats)} masters pour le meme "
            f"profil {profil!r}, la meme resolution et le meme rang "
            f"{rang_vise}: {', '.join(conflit)}. Aucun argument ne les "
            "distingue, et en choisir un detruirait une sortie qui n'etait "
            "pas visee. Corriger le manifeste avant de rejouer. Aucune "
            "suppression n'a eu lieu."
        )
    cible = candidats[0]
    chemin_vise = cible["path"]
    # **LA FAMILLE SE LIT DU PRODUCTEUR, ELLE NE SE RECOMPOSE PAS** (revue
    # `EPIC11-ARB-224`, couche 1 `C1-03` et couche 3 `F2` -- critique, deux
    # couches sur trois, par deux chemins independants).
    #
    # `encode.cle_de_famille_de_master` borne la famille par le profil ET la
    # resolution, et dit pourquoi : « deux masters d'un lot qui different par
    # l'un ou l'autre ne sont PAS deux versions l'un de l'autre ». Cette
    # fonction lisait et ecrivait sous le profil SEUL, et composait
    # `rangs_declares` de tous les masters du profil, resolutions confondues.
    # La redaction precedente citait meme cette fonction-la a l'appui de la
    # moitie qu'elle gardait -- et le contrat d'`EPIC11-ARB-224` a repris cette
    # moitie ; c'est le CODE d'`encode` qui a raison, la clause du contrat est
    # corrigee avec ce correctif.
    #
    # Trois consequences mesurees, enchainees : liberer le rang de queue d'une
    # famille non par defaut etait refuse au motif d'un master d'une AUTRE
    # famille (`EPIC11-ARB-92` retourne en silence) ; la ligne d'eau etait
    # posee sur la cle du VOISIN, en annoncant `rang_libere=True` ; et le
    # producteur le confirmait -- le prochain encodage par defaut sautait a
    # `_v3` pendant que la famille liberee repartait a `_v4`.
    #
    # La racine PRECEDE `EPIC11-ARB-224` -- l'appariement par chemin composait
    # deja la meme cle. Ce qui la rend atteignable deliberement, c'est que ce
    # module SAIT desormais lire la resolution : il la derive, la nomme, refuse
    # sur elle. Faire TAPER une resolution a l'operateur porte la promesse
    # qu'elle discrimine.
    from .encode import cle_de_famille_de_master

    segment_cible = _segment(cible)
    cle_de_famille = cle_de_famille_de_master(profil, segment_cible)
    if segment_cible is None:
        # **Un nom non conforme n'appartient a aucune famille LISIBLE**, et le
        # perimetre le plus large est ici le plus prudent : restreindre la
        # famille a « les autres entrees illisibles » rendrait un rang de
        # queue qu'un master conforme detient peut-etre encore. On garde donc
        # le profil entier, c'est-a-dire le comportement d'avant, pour le seul
        # cas que le refus d'ambiguite declare deja atteignable par AUCUNE
        # `--resolution`.
        parents = du_profil
    else:
        parents = [e for e in du_profil if _segment(e) == segment_cible]
    lignes = lot.get(MASTERS_WATERMARK_FIELD)
    declaree = lignes.get(cle_de_famille) if isinstance(lignes, Mapping) else None

    def retirer() -> None:
        for entree_lot in manifest.get("lots") or []:
            if isinstance(entree_lot, dict) and entree_lot.get("lot_id") == lot.get("lot_id"):
                restant = [
                    e for e in (entree_lot.get("encoded_masters") or [])
                    if e is not cible
                ]
                if restant:
                    entree_lot["encoded_masters"] = restant
                else:
                    entree_lot.pop("encoded_masters", None)

    def poser(valeur: int | None) -> None:
        for entree_lot in manifest.get("lots") or []:
            if isinstance(entree_lot, dict) and entree_lot.get("lot_id") == lot.get("lot_id"):
                lignes_lot = entree_lot.get(MASTERS_WATERMARK_FIELD)
                lignes_lot = dict(lignes_lot) if isinstance(lignes_lot, Mapping) else {}
                if valeur is None:
                    lignes_lot.pop(cle_de_famille, None)
                else:
                    lignes_lot[cle_de_famille] = valeur
                if lignes_lot:
                    entree_lot[MASTERS_WATERMARK_FIELD] = lignes_lot
                else:
                    entree_lot.pop(MASTERS_WATERMARK_FIELD, None)

    chemin = _sous_le_projet(
        project_dir, project_dir / chemin_vise, "path", chemin_vise)
    # **La meme garde que les deux autres chemins** (trouve en revue,
    # couche 1). Le diff venait de la porter au chemin `--tirage` en la
    # motivant mot pour mot, et `--master`, ecrit dans le meme diff, ne
    # l'avait pas : un `encoded_masters[].path` declare par DEUX lots etait
    # supprime pour l'un, detruisant la sortie de l'autre sans trace.
    autres_lots = [
        l for l in (manifest.get("lots") or [])
        if isinstance(l, Mapping) and l.get("lot_id") != lot.get("lot_id")
    ]
    _refuser_l_annexe_partagee(
        project_dir, chemin.resolve(), chemin_vise, autres_lots, manifest)
    return _FamilleVersionnee(
        nom="master", cible=f"{lot.get('lot_id')} (master {chemin_vise})",
        rangs_declares={_rang_d_une_entree(e) for e in parents},
        ligne_declaree=declaree, rang=_rang_d_une_entree(cible),
        fichiers=(chemin,), retirer_l_entree=retirer, poser_la_ligne=poser,
    )


def _famille_de_scan(
    project_dir: Path, manifest: dict, lot: Mapping[str, Any],
    famille_visee: str, rang: int,
) -> _FamilleVersionnee:
    """La famille d'un dossier de scan, identifiee par son slug de FAMILLE.

    **`EPIC11-ARB-224`** : le slug donne est celui de la famille -- le nom du
    dossier prive de son fragment `_vN` --, et le rang arrive par `--version`.
    Le slug REEL de la cible ne se recompose pas : il se lit, soit de la
    declaration du lot, soit du dossier trouve sur le disque. Les deux sources
    existaient deja et disent le meme nom ; en fabriquer une troisieme serait
    la faute que `_rang_et_base_du_slug` a ete ecrit pour fermer.
    """
    base = _slug_valide(famille_visee)
    if base is None:
        raise ProjectMaintenanceError(
            f"Slug de scan invalide: {famille_visee!r}. Aucune suppression "
            "n'a eu lieu.")
    # **LE SCAN DOIT APPARTENIR AU LOT VISE** (trouve en revue, couche 1,
    # CRITIQUE). Cette fonction enumerait `scans/` et supprimait, sans jamais
    # consulter `lot["reconstructions"]` : `--lot A --scan SB` detruisait le
    # scan du lot B, avec `supprime=True`, pendant que le manifeste de B
    # continuait de le declarer. Une faute de frappe de slug suffisait.
    #
    # C'est la gravite maximale de ce module : un dossier de scan porte des
    # planches PAPIER numerisees, la seule famille d'objets que ce fichier
    # declare lui-meme non recalculable. Et c'est litteralement l'incident du
    # 2026-08-27 -- le meme defaut que le diff revendiquait avoir ferme pour
    # `sheets_pdfs[].path`, avec la meme moitie de domaine oubliee.
    #
    # `_famille_de_master` verifie l'appartenance par `encoded_masters`,
    # `_famille_du_lot_scanne` par le `lot_id` : seule celle-ci ne le faisait
    # pas.
    def _designe_la_cible(valeur: object) -> bool:
        """Ce slug declare est-il la version visee de la famille visee ?

        La comparaison passe par `_rang_et_base_du_slug` des DEUX cotes : c'est
        la lecture unique du fragment, celle qui refuse un zero de tete. La
        remplacer ici par une concatenation `base + _vN` reintroduirait la
        seconde verite que cette fonction-la existe pour supprimer.
        """
        return isinstance(valeur, str) and _rang_et_base_du_slug(valeur) == (
            rang, base)

    # **TOUS LES LOTS SONT BALAYES, LE PREMIER NE FAIT PAS FOI** (revue
    # `EPIC11-ARB-224`, couche 1 `C1-04` -- critique, classe « ordre
    # d'iteration », zero survivant tolere).
    #
    # La redaction precedente s'arretait au PREMIER lot qui declare le slug
    # (`break`). Mesure : meme manifeste, meme commande, seul l'ORDRE de
    # `manifest["lots"]` change -- cible en TETE, le dossier de scan d'un lot
    # TIERS etait detruit en laissant l'autre lot le declarer, pendant ; cible
    # en QUEUE, le refus se contredisait dans la meme phrase (« ne declare
    # aucun scan... Scans declares par ce lot: ['S_v2'] »). Les deux issues
    # sont fausses, chacune a sa facon, et un verdict qui depend de l'ordre
    # d'ecriture du manifeste n'est pas un verdict.
    #
    # `_famille_de_master` refusait deja ce cas par `_refuser_l_annexe_partagee`
    # (« un `encoded_masters[].path` declare par DEUX lots etait supprime pour
    # l'un, detruisant la sortie de l'autre sans trace ») : c'est le PATRON du
    # meme fichier, rejoue ici. Le diff d'`EPIC11-ARB-224` avait ferme la moitie
    # APPARTENANCE de cette boucle et laisse la moitie PARTAGE.
    #
    # Un dossier de scan porte des planches PAPIER numerisees : la seule
    # famille d'objets que ce module declare lui-meme non recalculable. La
    # regle 4.0(c) de la politique dit par ailleurs que mutmut est aveugle a
    # cette classe -- elle ne se mesure que par une fabrique qui place la cible
    # a CHAQUE BORD de la liste parcourue.
    declarants: list[tuple[Any, str]] = []
    for autre in (manifest.get("lots") or []):
        if not isinstance(autre, Mapping):
            continue
        sien = next(
            (e.get("ingest_slug")
             for e in (autre.get("reconstructions") or [])
             if isinstance(e, Mapping) and _designe_la_cible(e.get("ingest_slug"))),
            None,
        )
        if sien is not None:
            declarants.append((autre.get("lot_id"), sien))
    if len(declarants) > 1:
        raise ProjectMaintenanceError(
            f"Le dossier de scan de famille {base!r} au rang {rang} est "
            f"declare par PLUSIEURS lots: "
            f"{', '.join(repr(l) for l, _s in declarants)}. Le supprimer "
            "detruirait ce qu'un autre lot declare, et laisserait sa "
            "declaration pendante: aucune suppression n'a eu lieu. Corriger le "
            "manifeste (deux lots ne partagent pas un dossier de scan) avant "
            "de rejouer."
        )
    slug, proprietaire = (declarants[0][1], declarants[0][0]) if declarants \
        else (None, None)
    if proprietaire is None:
        # Repli sur la section de tete, pour un manifeste anterieur au registre.
        tete = manifest.get("reconstruction")
        if isinstance(tete, Mapping) and isinstance(tete.get("scan"), Mapping) \
                and _designe_la_cible(tete["scan"].get("ingest_slug")):
            slug = tete["scan"]["ingest_slug"]
            proprietaire = tete.get("lot_id")
    if proprietaire != lot.get("lot_id"):
        declares = sorted(
            str(e.get("ingest_slug"))
            for e in (lot.get("reconstructions") or []) if isinstance(e, Mapping)
        )
        appartenance = (
            f" Il est declare par le lot {proprietaire!r}."
            if proprietaire is not None
            else " Aucun lot de ce projet ne le declare."
        )
        raise ProjectMaintenanceError(
            f"Le lot {lot.get('lot_id')!r} ne declare aucun scan de famille "
            f"{base!r} au rang {rang}.{appartenance} Scans declares par ce lot: "
            f"{declares or 'aucun'}. Un dossier de scan porte des planches "
            "PAPIER numerisees: le supprimer sur la foi d'un nom, sans que le "
            "lot le declare, detruirait ce qu'aucun calcul ne refait. Aucune "
            "suppression n'a eu lieu."
        )

    racine = project_dir / SCANS_DIRNAME
    # **AUCUNE exclusion ici, et c'est mesure.** Ma premiere redaction excluait
    # les slugs des autres reconstructions du projet -- ce qui retirait de la
    # famille `S` ses propres versions `S_v2` et `S_v3`, puisqu'elles y
    # figurent aussi. Resultat : le rang du milieu devenait liberable et la
    # queue rendait deux rangs au lieu d'un.
    #
    # L'exclusion serait de toute facon sans objet : `validate_ingest_slug`
    # REFUSE depuis ce meme jour qu'un slug se termine par `_v2..._v99`, donc
    # aucun scan a part entiere ne peut ressembler a la version d'un autre.
    # C'est exactement la garde qui rend cette enumeration sure -- la
    # difference avec les frames, ou le slug est un `lot_id` et ou un lot
    # versionne porte legitimement `_v2`.
    presents = _rangs_des_dossiers(racine, base, set())
    # **Une entree dont le dossier a disparu se DELIE** (trouve en revue,
    # couche 2). `--tirage` traite ce cas depuis le debut -- l'entree part meme
    # quand le fichier est introuvable -- et `--scan` refusait : l'entree
    # devenait immortelle sauf a supprimer le lot entier, c'est-a-dire un
    # blocage sec au sens d'`EPIC11-ARB-89`. C'est la DECLARATION du lot qui
    # autorise le retrait, pas la presence du dossier.
    declare_par_le_lot = any(
        isinstance(e, Mapping) and _designe_la_cible(e.get("ingest_slug"))
        for e in (lot.get("reconstructions") or [])
    )
    if rang not in presents and not declare_par_le_lot:
        raise ProjectMaintenanceError(
            f"Aucun dossier de scan de famille {base!r} au rang {rang} sous "
            f"{SCANS_DIRNAME}/, et le lot {lot.get('lot_id')!r} ne le declare "
            f"pas. Dossiers de cette famille: "
            f"{sorted(c.name for c in presents.values()) or 'aucun'}. "
            "Aucune suppression n'a eu lieu."
        )
    # Le slug REEL de la cible, LU et jamais compose : il vient de la
    # declaration du lot, qui fait foi.
    #
    # **La branche de repli a ete RETIREE : elle etait INATTEIGNABLE** (revue
    # `EPIC11-ARB-224`, couche 2, corollaire mesure de `M13`). `slug` ne valait
    # `None` a cet endroit que si `proprietaire is None`, et l'on n'y arrive
    # qu'apres `proprietaire == lot["lot_id"]`, non nul par construction du
    # dispatch. Une surface morte est pire qu'inutile : aucun mutant ne peut y
    # etre tue, donc elle se lit comme une garantie que rien ne tient.
    fichiers = (presents[rang],) if rang in presents else ()
    rangs_declares = set(presents) | ({rang} if declare_par_le_lot else set())
    lignes = manifest.get(SCAN_WATERMARKS_FIELD)
    declaree = lignes.get(base) if isinstance(lignes, Mapping) else None

    def retirer() -> None:
        # L'ENTREE du scan vit dans l'historique de reconstruction du lot
        # (`EPIC11-ARB-109`) : la retirer evite que la filiation continue de
        # designer un dossier supprime.
        for entree_lot in manifest.get("lots") or []:
            if isinstance(entree_lot, dict) and entree_lot.get("lot_id") == lot.get("lot_id"):
                restant = [
                    e for e in (entree_lot.get("reconstructions") or [])
                    if not (isinstance(e, Mapping)
                            and _designe_la_cible(e.get("ingest_slug")))
                ]
                if restant:
                    entree_lot["reconstructions"] = restant
                else:
                    entree_lot.pop("reconstructions", None)

    def poser(valeur: int | None) -> None:
        lignes_projet = manifest.get(SCAN_WATERMARKS_FIELD)
        lignes_projet = dict(lignes_projet) if isinstance(lignes_projet, Mapping) else {}
        if valeur is None:
            lignes_projet.pop(base, None)
        else:
            lignes_projet[base] = valeur
        if lignes_projet:
            manifest[SCAN_WATERMARKS_FIELD] = lignes_projet
        else:
            manifest.pop(SCAN_WATERMARKS_FIELD, None)

    return _FamilleVersionnee(
        nom="scan", cible=f"{lot.get('lot_id')} (scan {slug})",
        rangs_declares=rangs_declares, ligne_declaree=declaree, rang=rang,
        fichiers=fichiers, retirer_l_entree=retirer, poser_la_ligne=poser,
    )


def _famille_du_lot_scanne(
    project_dir: Path, manifest: dict, lot: Mapping[str, Any], rang_vise: int
) -> _FamilleVersionnee:
    """La famille des LOTS SCANNES d'un lot, identifiee par un rang.

    Le slug de base est le `lot_id` : le rang porte ici sur la PASSE de scan,
    distinct du rang du LOT qui vit deja dans l'identifiant (`EPIC11-ARB-105`).

    **Story 11.14** -- le mot est celui d'Egan : « a partir d'un scan on
    reproduit un lot scanne qui est lui meme un ensemble de frames scannees ».
    Ce que cette granularite retire est donc **un lot scanne**, pas « un jeu de
    frames » : le depot ne nommait ici que le contenu, et c'est ce qui
    l'empechait d'etre un objet versionnable comme les autres
    (`EPIC11-ARB-104`, `EPIC11-ARB-108`).

    **Les DEUX racines sont parcourues** (`EPIC11-ARB-171`) : le nom neuf et
    celui d'avant, qui reste RECONNU. Elles sont lues de `project_layout`,
    jamais recomposees ici. Sans cela, « le nom d'avant n'est plus jamais
    ecrit » serait tenu par un outil incapable de rien retirer des projets
    deja sur le disque -- c'est-a-dire le blocage sec qu'`EPIC11-ARB-89`
    interdit.
    """
    # **LA MEME RECETTE DE NOM QUE L'ECRIVAIN** (trouve en revue, couche 2).
    # Cette fonction prenait le `lot_id` pour le nom du dossier ; l'ecriture,
    # elle, passe par `derive_lot_dir_slug`. Les deux coincident tant que
    # l'identifiant tient sous la borne, et DIVERGENT des qu'il est raccourci :
    # `--frames 2` refusait alors « aucun jeu de rang 2 » sur un lot qui en a
    # un, sans issue. Deux recettes pour le meme fait sont deux verites
    # (`EPIC5-ARB-78`) -- et le manifeste porte deja la reponse.
    base = str(lot.get("lot_id") or "")
    declare = lot.get("output_frames_dir")
    if isinstance(declare, str) and declare:
        base = PurePosixPath(declare).name
    else:
        try:
            base = _slug_du_lot_scanne(lot)
        except Exception:
            pass
    autres = set()
    for autre in (manifest.get("lots") or []):
        if not isinstance(autre, Mapping) or autre.get("lot_id") == lot.get("lot_id"):
            continue
        sien = autre.get("output_frames_dir")
        if isinstance(sien, str) and sien:
            autres.add(PurePosixPath(sien).name)
        else:
            try:
                autres.add(_slug_du_lot_scanne(autre))
            except Exception:
                autres.add(str(autre.get("lot_id")))
    # La racine NEUVE d'abord, celle d'avant ensuite : un rang trouve des deux
    # cotes -- ce que rien n'ecrit, mais qu'une main peut fabriquer -- est
    # retire par son dossier NEUF, et jamais deux fois.
    presents: dict[int, Path] = {}
    for racine in project_layout.racines_de_frames_scannees(project_dir):
        for rang, chemin in _rangs_des_dossiers(racine, base, autres).items():
            presents.setdefault(rang, chemin)
    if rang_vise not in presents:
        raise ProjectMaintenanceError(
            f"Le lot {lot.get('lot_id')!r} n'a aucun lot scanne de "
            f"rang {rang_vise}. Rangs presents: {sorted(presents) or 'aucun'}. "
            "Aucune suppression n'a eu lieu."
        )
    declaree = lot.get(OUTPUT_FRAMES_WATERMARK_FIELD)

    def retirer() -> None:
        # **Le manifeste ne doit pas continuer de designer un dossier
        # supprime** (trouve en revue, couche 1). Il n'y a pas d'entree par
        # PASSE, mais le lot porte `output_frames_dir` et les cardinaux qui en
        # derivent : retirer le jeu qu'ils designent les laissait pointer dans
        # le vide, et toute etape aval mourait plus loin sur une erreur de bas
        # niveau sans rapport.
        vise = presents[rang_vise].relative_to(project_dir).as_posix()
        for entree_lot in manifest.get("lots") or []:
            if not (isinstance(entree_lot, dict)
                    and entree_lot.get("lot_id") == lot.get("lot_id")):
                continue
            if entree_lot.get("output_frames_dir") != vise:
                continue
            entree_lot.pop("output_frames_dir", None)
            # Les cardinaux DERIVENT du dossier : ils ne veulent plus rien dire
            # sans lui, et les garder ferait croire a des frames presentes.
            for cle in ("frame_count", "reconstructed_frame_count",
                        "synthetic_frame_count", "synthetic_frames"):
                entree_lot.pop(cle, None)

    def poser(valeur: int | None) -> None:
        for entree_lot in manifest.get("lots") or []:
            if isinstance(entree_lot, dict) and entree_lot.get("lot_id") == lot.get("lot_id"):
                if valeur is None:
                    entree_lot.pop(OUTPUT_FRAMES_WATERMARK_FIELD, None)
                else:
                    entree_lot[OUTPUT_FRAMES_WATERMARK_FIELD] = valeur

    return _FamilleVersionnee(
        nom="lot scanne", cible=f"{lot.get('lot_id')} (lot scanne v{rang_vise})",
        rangs_declares=set(presents), ligne_declaree=declaree, rang=rang_vise,
        fichiers=(presents[rang_vise],), retirer_l_entree=retirer, poser_la_ligne=poser,
    )


def _famille_des_frames_extraites(
    project_dir: Path, manifest: dict, lot: Mapping[str, Any]
) -> _FamilleVersionnee:
    """Le jeu de frames EXTRAITES d'un lot -- il y en a UN, et un seul.

    **Retour de terrain d'Egan du 2026-09-06** : « on ne peut pas retirer d'un
    projet un jeu de frames extraites sans emporter autre chose ». Jusqu'ici
    les frames extraites ne partaient qu'avec le lot entier -- masters,
    planches et scans compris --, c'est-a-dire une destruction PLUS large que
    celle demandee, ce qui est pire qu'un refus (`EPIC11-ARB-89`).

    **Ce jeu N'EST PAS un sixieme objet versionnable, et c'est mesure.** Le
    dossier se nomme par `project_layout.extract_frames_dir(...,
    version_rank=)`, qui recoit le rang du LOT : `extraction._build_lot` ecrit
    `lots[].frames_dir` a partir du meme `version_rank` que `lot_id`. Donc
    `extract-frames/rush-a_24` et `extract-frames/rush-a_24_v2` sont les
    dossiers de DEUX LOTS, jamais deux versions d'un meme jeu -- exactement la
    collision que le parametre `exclus` de :func:`_rangs_des_dossiers` ferme
    du cote des lots scannes. Il n'existe donc ni famille, ni ligne d'eau, ni
    `--version` a lire ici : le rang se donne en nommant le lot
    (`EPIC11-ARB-221`, l'identifiant est la cle gelee).

    C'est aussi pourquoi ce module ne pose AUCUN champ de ligne d'eau neuf :
    en poser un ferait des frames extraites un objet versionnable de plus,
    exactement ce que `extraction.py` refuse deja pour le rush (« poser un
    champ de ligne d'eau ferait du rush un sixieme objet versionnable »).

    **Le manifeste cesse de designer le dossier, et RIEN d'autre ne bouge.**
    Seul `frames_dir` pointe vers lui ; les autres champs du lot
    (`expected_frame_count`, les timecodes, le condensat, `output_bit_depth`)
    sont ecrits par `_build_lot` a partir de la SELECTION, jamais d'un
    comptage sur disque -- ils decrivent le plan d'extraction, que la
    reextraction compare, et les effacer detruirait ce plan sans rien gagner.
    `state` non plus n'est pas touche : le ramener en arriere ecrirait une
    transition que `validate_lot_state_transition` interdit. La reextraction
    d'un lot avance reste possible, elle passe par l'ecrasement conscient --
    une issue, pas un mur.
    """
    declare = lot.get("frames_dir")
    if not declare:
        # **Un refus qui NOMME, avec ses issues** : le lot existe, mais rien
        # ne dit ou vivent ses frames. Deviner `extract-frames/<lot_id>` serait
        # une seconde recette de nom (`EPIC5-ARB-78`) et ferait supprimer sur
        # une supposition -- le meme geste que `_masters_declares` refuse.
        raise ProjectMaintenanceError(
            f"Le lot {lot.get('lot_id')!r} ne declare aucun `frames_dir`: il "
            "n'y a pas de jeu de frames extraites a retirer. Deux issues: si "
            "un dossier de frames existe sans etre declare, il apparait comme "
            "ORPHELIN a l'inventaire et se retire par la; sinon, retirer le "
            "lot entier. Aucune suppression n'a eu lieu."
        )
    dossier = _sous_le_projet(
        project_dir, project_dir / str(declare), "frames_dir", declare)
    # LES MEMES DEUX GARDES QUE `_fichiers_du_lot`, et pas une de moins : un
    # `frames_dir` valant `"frames"` -- l'ancetre commun -- ramasserait les
    # frames de TOUS les lots, et `"."` ou `"frames/.."` emporterait
    # `project.json` lui-meme. Les deux ont ete payees ; passer a cote par une
    # porte d'entree neuve les rouvrirait toutes les deux.
    autres = [l for l in (manifest.get("lots") or []) if l is not lot]
    # **Le lot LUI-MEME entre dans la comparaison, prive de son `frames_dir`.**
    # `_fichiers_du_lot` supprime tout le lot ensemble, donc le chevauchement
    # de ses propres objets lui est indifferent ; ici on ne retire QUE les
    # frames extraites, et tout ce que le lot declare PAR AILLEURS -- son
    # dossier de frames scannees, ses masters, ses planches, ses dossiers de
    # scan -- reste declare apres coup. Un `frames_dir` qui les contient les
    # emporterait en silence.
    #
    # **La cle `frames_dir` est la seule retiree de la copie, et il le faut** :
    # la laisser ferait comparer la cible a elle-meme, donc refuser toujours.
    # La premiere redaction ne reprenait que `output_frames_dir` et laissait
    # les trois autres familles sans garde -- c'est le finding `C2-2`, mesure :
    # un `frames_dir` valant `"outputs"` detruisait le master encode du lot
    # pendant que `encoded_masters[].path` continuait de le declarer.
    soi = {cle: valeur for cle, valeur in lot.items() if cle != "frames_dir"}
    _refuser_le_chevauchement(
        project_dir, dossier.resolve(), "frames_dir", declare,
        autres + [soi], manifest=manifest)

    def retirer() -> None:
        # **On delie l'entree qui declare CE dossier, pas toutes celles qui
        # portent le meme `lot_id`** (finding `C2-9`). Le jumeau
        # `_famille_du_lot_scanne.retirer` se garde ainsi depuis toujours ;
        # celui-ci ne le faisait pas. Mesure du regime, avant correctif : deux
        # entrees `lot_id="L"` de `frames_dir` DIFFERENTS et disjoints -- que
        # le chevauchement ne refuse donc pas -- rendaient un seul dossier
        # supprime et DEUX entrees deliees, laissant les frames de la seconde
        # orphelines, sans un mot. Un manifeste qui porte deux entrees de meme
        # identifiant est deja incoherent ; en delier une de trop n'est pas
        # une facon de le dire, c'est une seconde perte.
        for entree_lot in manifest.get("lots") or []:
            if not (isinstance(entree_lot, dict)
                    and entree_lot.get("lot_id") == lot.get("lot_id")):
                continue
            if entree_lot.get("frames_dir") != declare:
                continue
            entree_lot.pop("frames_dir", None)

    rang = _rang_d_une_entree(lot)
    return _FamilleVersionnee(
        nom="jeu de frames extraites",
        cible=f"{lot.get('lot_id')} (frames extraites)",
        # Un seul rang declare, celui du lot : la « famille » se reduit a son
        # unique membre, ce qui est la verite de cet objet.
        rangs_declares={rang}, ligne_declaree=None, rang=rang,
        fichiers=(dossier,), retirer_l_entree=retirer,
        poser_la_ligne=_ligne_d_eau_inexistante,
        rang_independant=False, contenant="lot",
    )


def _retirer_un_tirage(
    project_dir: Path,
    manifest_path: Path,
    manifest: dict,
    lot: Mapping[str, Any],
    tirage: int,
    dry_run: bool,
    liberer_le_rang: bool = False,
) -> RapportSuppression:
    """Retirer UN tirage de planches: son fichier s'il est la, son entree TOUJOURS.

    C'est la dissociation que ce mecanisme tenait deja pour les rushs, portee
    ici : **l'entree au manifeste et le fichier sur le disque sont deux choses
    differentes**, et la premiere se retire meme quand la seconde est
    introuvable.

    Sans cela, un tirage renomme a la main occupait son rang **pour toujours**
    -- aucune commande ne pouvait retirer son entree, et le rang etait perdu
    pour le projet. Un blocage sec, exactement ce qu'`EPIC11-ARB-89` interdit.

    **LE RANG NE SE REND PAS** (`EPIC11-ARB-92`, Egan 2026-08-31 : « il ne faut
    pas rendre le rang, la v2 a ete consommee par la v3 qui se trouve
    apres »). Retirer le tirage 2 alors que le 3 existe laisse le prochain a
    4 : sans cela, deux planches PAPIER porteraient toutes deux « v2 », et une
    fois l'encre seche aucun fichier ne rattrape cela.

    **Un seul cas rend un rang : le retrait du DERNIER tirage a date**, et
    seulement sur `liberer_le_rang=True`. La ligne d'eau redescend alors
    jusqu'au plus haut rang encore declare -- ce qui peut liberer PLUSIEURS
    rangs d'un coup, et c'est voulu : si le 2 avait ete retire quand le 3
    existait, retirer le 3 rend les deux ensemble, parce que les deux
    redeviennent la queue au meme moment.

    Demander la liberation d'un rang qui n'est PAS en queue est refuse
    nommement plutot qu'ignore : c'est une demande dont l'operateur attend un
    effet, et la taire lui ferait croire le rang disponible.
    """
    def _rang_de(entree):
        valeur = entree.get("version_rank")
        return valeur if isinstance(valeur, int) and not isinstance(valeur, bool) else 1

    inventaire = [
        e for e in (lot.get(SHEETS_INVENTORY_FIELD) or []) if isinstance(e, Mapping)
    ]
    # LA LIGNE D'EAU, par le module partage (`EPIC11-ARB-108`). Elle etait
    # recalculee ici a la main, et les deux redactions divergeaient deja: la
    # copie retenait la valeur declaree TELLE QUELLE, la ou `ligne_d_eau` la
    # borne par le plus haut rang employe. Sur une famille `1,2,3` dont le
    # manifeste declare une ligne a 2 -- manifeste abime, ou edite --, la copie
    # acceptait de liberer un rang que la regle refuse. Elle acceptait aussi
    # une ligne d'eau BOOLEENNE et une ligne nulle ou negative, qui rendaient
    # tout rang « en queue » et desactivaient le refus.
    ligne_actuelle = version_ranks.ligne_d_eau(
        lot.get(SHEETS_WATERMARK_FIELD), {_rang_de(e) for e in inventaire})
    en_queue = version_ranks.est_en_queue(tirage, ligne_actuelle)

    vise = [e for e in inventaire if _rang_de(e) == tirage]
    # **Un rang CONSOMME dont l'entree est deja partie se libere quand meme**
    # (trouve en revue, couche 2). Retirer le tirage 99 avec le defaut laisse
    # la ligne d'eau a 99 et plus aucune entree qui le porte: le refus
    # d'epuisement proposait alors « retirer le dernier tirage en liberant son
    # rang », et ce geste se heurtait a « aucun tirage de rang 99 ». Les deux
    # issues nommees etaient refusees ensemble, et il ne restait que
    # l'ecrasement destructeur -- le mur exact qu'`EPIC11-ARB-89` interdit.
    #
    # Le retrait porte alors sur le RANG SEUL: aucun fichier, aucune entree, la
    # seule ligne d'eau. Il reste soumis a la meme condition de queue que tout
    # autre, donc il ne peut pas rendre un rang du milieu.
    liberation_de_rang_seul = bool(
        not vise and liberer_le_rang and en_queue and tirage <= ligne_actuelle
    )
    if not vise and not liberation_de_rang_seul:
        rangs = sorted({_rang_de(e) for e in inventaire})
        issue = ""
        if tirage <= ligne_actuelle:
            # Le rang a bien servi, son entree est simplement partie. Nommer le
            # geste plutot que de laisser l'operateur devant une liste ou son
            # rang ne figure pas: le refus doit dire par ou sortir.
            issue = (
                f" Le rang {tirage} a pourtant ete CONSOMME (ligne d'eau: "
                f"{ligne_actuelle}): son entree a deja ete retiree. Pour ne "
                "liberer que le rang, relancer avec --liberer-le-rang."
            )
        raise ProjectMaintenanceError(
            f"Le lot {lot.get('lot_id')!r} ne declare aucune planche de rang "
            f"{tirage}. Planches declarees: {rangs or 'aucun'}.{issue} "
            "Aucune suppression n'a eu lieu."
        )

    if liberer_le_rang and not en_queue:
        raise ProjectMaintenanceError(
            version_ranks.refus_de_liberer_hors_queue(
                tirage, ligne_actuelle, "planche")
            + " Aucune suppression n'a eu lieu."
        )

    # Les AUTRES lots, pour la garde d'annexe partagee ci-dessous.
    autres_lots = [
        l for l in (manifest.get("lots") or [])
        if isinstance(l, Mapping) and l.get("lot_id") != lot.get("lot_id")
    ]

    presents: list[Path] = []
    absents: list[str] = []
    for entree in vise:
        relatif = entree.get("path")
        if not isinstance(relatif, str) or not relatif:
            continue
        chemin = _sous_le_projet(project_dir, project_dir / relatif, "path", relatif)
        # **La meme garde que le chemin « lot entier »** (trouve en revue,
        # couche 1). Ce chemin-ci ne l'avait pas: un `sheets_pdfs[].path`
        # designant la sortie d'un AUTRE lot etait supprime, le rapport
        # annoncait `supprime=True`, et le manifeste continuait de declarer
        # l'autre lot -- une destruction sans trace. La moitie du domaine
        # seulement avait recu la garde.
        _refuser_l_annexe_partagee(
            project_dir, chemin.resolve(), relatif, autres_lots, manifest)
        (presents if chemin.is_file() else absents).append(
            chemin if chemin.is_file() else PurePosixPath(relatif).as_posix())

    # **Le MOT est « planche », pas « tirage »** (`EPIC11-ARB-224`, second
    # temps, Egan verbatim : « "--tirage" n'est pas un mot de vocabulaire.
    # C'est "planche". »). `Q5` etait ouverte tant que l'option disait un mot
    # et la nature publiee un autre ; elle ne l'est plus, et laisser « tirage »
    # ici remettrait DEUX mots pour un objet dans le meme ecran -- le finding
    # `F2` exactement, a une nuit d'intervalle.
    cible = f"{lot.get('lot_id')} (planche {tirage})"
    fichiers_a_supprimer = _chemins_a_supprimer(project_dir, presents)
    # Ce qui serait rendu : la queue contigue qui redevient libre, par le
    # module partage (`EPIC11-ARB-108`). Calcule AVANT toute ecriture, pour que
    # l'apercu dise exactement ce que la confirmation ferait.
    restant = [e for e in inventaire if _rang_de(e) != tirage]
    rangs_restants = {_rang_de(e) for e in restant}
    liberables = (
        version_ranks.rangs_liberables(ligne_actuelle, rangs_restants)
        if en_queue else ()
    )

    if dry_run:
        return RapportSuppression(
            cible=cible, fichiers_a_supprimer=fichiers_a_supprimer, dry_run=True,
            supprime=False, fichiers_attendus_absents=tuple(absents),
            tirage_en_queue=en_queue, rangs_liberables=liberables,
            rang_vise=tirage,
            # Renseigne AUSSI en apercu (trouve en revue, couche 1): sans lui,
            # la CLI proposait de « relancer avec --liberer-le-rang » a un
            # operateur qui venait de le passer.
            rang_libere=bool(liberer_le_rang and en_queue),
        )

    # L'entree D'ABORD (AC 10, meme ordre que pour un lot): un echec de
    # suppression de fichier laisse alors un manifeste coherent avec ce qui
    # reste lisible.
    for entree_lot in manifest.get("lots") or []:
        if isinstance(entree_lot, dict) and entree_lot.get("lot_id") == lot.get("lot_id"):
            if restant:
                entree_lot[SHEETS_INVENTORY_FIELD] = restant
            else:
                entree_lot.pop(SHEETS_INVENTORY_FIELD, None)
            if liberer_le_rang and en_queue:
                # Redescente jusqu'au plus haut rang ENCORE declare. Elle
                # libere d'un coup tous les rangs de queue devenus libres --
                # y compris ceux dont l'entree avait ete retiree plus tot
                # sans que leur rang le soit, puisqu'ils redeviennent la queue
                # au meme moment.
                nouvelle = max(rangs_restants or {0})
                if nouvelle > version_ranks.RANG_ORIGINE:
                    entree_lot[SHEETS_WATERMARK_FIELD] = nouvelle
                else:
                    # **Rendre jusqu'a l'ORIGINE, c'est RETIRER le champ, pas
                    # l'ecrire a 1** (trouve en revue, couche 2). L'ecrire a 1
                    # laissait un entier que la garde du resolveur prenait pour
                    # une ligne d'eau declaree: le prochain tirage repartait a
                    # 2 alors que la CLI venait d'annoncer « rang 1 rendu ».
                    # L'absence du champ est ce qui dit l'origine
                    # (`EPIC11-ARB-88`, omission stricte).
                    entree_lot.pop(SHEETS_WATERMARK_FIELD, None)
            elif en_queue:
                # Sans la demande explicite, la ligne d'eau est POSEE telle
                # quelle plutot que laissee implicite: un manifeste anterieur
                # n'en portait pas, et la deduire du plus haut rang restant
                # reviendrait a liberer le rang en silence.
                entree_lot[SHEETS_WATERMARK_FIELD] = ligne_actuelle
    _ecrire_manifeste(manifest_path, manifest)

    echecs: list[str] = []
    for chemin in presents:
        try:
            chemin.unlink()
        except OSError:
            echecs.append(chemin.relative_to(project_dir).as_posix())
    return RapportSuppression(
        cible=cible, fichiers_a_supprimer=fichiers_a_supprimer, dry_run=False,
        supprime=not echecs, fichiers_non_supprimes=tuple(sorted(echecs)),
        fichiers_attendus_absents=tuple(absents),
        tirage_en_queue=en_queue, rangs_liberables=liberables,
        rang_libere=bool(liberer_le_rang and en_queue), rang_vise=tirage,
    )

def remove_project_element(
    project_dir: str | Path,
    *,
    lot_id: str | None = None,
    rush_id: str | None = None,
    dry_run: bool = True,
    confirmation_dernier_lot: bool = False,
    avec_scans: bool = False,
    planche: bool = False,
    liberer_le_rang: bool = False,
    master: bool = False,
    profile: str | None = None,
    resolution: str | None = None,
    scan: str | None = None,
    lot_scanne: bool = False,
    frames_extraites: bool = False,
    version: int | None = None,
) -> RapportSuppression:
    """Supprimer proprement un lot ou un rush de `project_dir` (AC 9 a AC 11).

    Vise EXACTEMENT un lot (`lot_id=...`) ou un rush (`rush_id=...`), jamais
    les deux, jamais aucun -- un appel ambigu est un refus, pas une devinette.

    **Mode dry-run par defaut** (`dry_run=True`): rend le rapport sans rien
    ecrire ni supprimer. `dry_run=False` effectue la suppression, dans
    l'ordre impose par l'AC 10: le manifeste **avant** les fichiers.

    Un rush qui porte encore des lots est refuse: cette fonction ne cascade
    jamais une suppression, l'appelant supprime les lots un par un d'abord.

    Vider le dernier lot -- ou le dernier rush -- d'un projet exige
    `confirmation_dernier_lot=True`, un mot-cle DISTINCT de `dry_run=False`
    (AC 11): deux consentements empiles, jamais un seul qui couvre les deux.

    **`avec_scans` est un TROISIEME consentement, et il est separe pour une
    raison de nature** (`EPIC11-ARB-90`). Tout le reste de ce que supprime
    cette fonction -- frames extraites, masters, planches -- se REFABRIQUE par
    calcul a
    partir du rush source. Un dossier de scan, non : il porte des images de
    planches PAPIER numerisees, et les refaire demande de retrouver les
    feuilles et de repasser au scanner. Le confondre avec `dry_run=False`
    ferait detruire par un geste ordinaire ce qui coute une manipulation
    physique a reproduire.

    Le dossier de scan est NOMME dans le rapport meme sans ce consentement:
    l'operateur doit voir qu'il existe pour decider, sinon le consentement
    n'est pas eclaire.

    **`planche` vise UNE SEULE planche au lieu du lot entier**
    (`EPIC11-ARB-90`, question d'Egan du 2026-08-31). Il exige `lot_id`, et il
    repose sur la distinction que le depot tient deja pour les rushs :
    **l'entree au manifeste et le fichier sur le disque sont deux choses
    differentes**. Un rush dont le fichier source vit sur un disque debranche
    se retire quand meme -- son entree part, `0 fichier(s)`.

    Le meme raisonnement vaut ici, et il ferme une fuite qui n'avait aucune
    issue : un tirage RENOMME a la main garde une entree que rien ne pouvait
    plus retirer, et cette entree occupe son rang **definitivement**. L'outil
    ne peut pas reconnaitre le fichier renomme -- il ne le supprimera pas --
    mais il peut delier l'entree, ce qui rend le rang au projet. C'est
    exactement l'issue qu'`EPIC11-ARB-89` exige : jamais un blocage sec.

    **`frames_extraites` vise LE jeu de frames extraites du lot, seul**
    (retour de terrain d'Egan du 2026-09-06). C'est la cinquieme cible fine et
    la seule sans rang PROPRE : le dossier est nomme par le `version_rank` du
    LOT, si bien que `--version` et `--liberer-le-rang` y sont refuses
    NOMMEMENT plutot qu'ignores -- le detail mesure est dans
    :func:`_famille_des_frames_extraites`. Le lot RESTE declare ; il cesse
    seulement de designer un dossier qui n'existe plus.

    **`lot_scanne` vise UN SEUL lot scanne du lot** (story 11.14,
    `EPIC11-ARB-214`). C'est l'ancienne cible `frames=` puis
    `frames_scannees=`, RENOMMEE et non doublee : la granularite reste la
    sixieme, elle prend seulement le mot de l'objet qu'elle retire.

    **ON DESIGNE UN OBJET PAR LES ARGUMENTS QUI L'ONT PRODUIT**
    (`EPIC11-ARB-224`, Egan le 2026-09-05 : « il faudrait aussi une coherence
    entre la commande remove et les commandes qui produisent les objets
    correspondants. Avec les memes arguments qui ont servi a les generer pour
    les identifier. »). Les cinq cibles fines se lisent donc de la meme
    facon : les arguments du producteur, plus `version=` pour le rang -- **a
    une exception, et elle est structurelle** : `frames_extraites` n'a pas de
    rang a lui. `extraction._build_lot` ecrit `frames_dir` et `lot_id` depuis
    la MEME valeur de `version_rank`, si bien que deux dossiers de frames sont
    ceux de deux LOTS, jamais deux versions d'un meme jeu. `version=` lui est
    donc refuse nommement, et non pas simplement ignore.

    * `planche=True` (produite par `makepdf`) et `lot_scanne=True` (produit
      par `scan-write`) sont des DRAPEAUX NUS -- un lot ne porte qu'une
      famille de chaque, il n'y a rien a designer de plus ;
    * `master=True` s'accompagne de `profile=` -- le parametre d'`encode` --
      et, seulement lorsqu'elle leve une ambiguite, de `resolution=`. **Aucun
      chemin** : l'emplacement est au manifeste, c'est lui qui le sait ;
    * `scan=` prend un slug de FAMILLE, le nom du dossier prive de son
      fragment `_vN` ;
    * sans `version=`, la cible est le rang d'ORIGINE -- `EPIC11-ARB-88` dit
      que ce rang ne porte aucun fragment, et son absence le dit ici aussi.

    **`lot_id` garde le `lot_id` COMPLET**, fragment inclus, et c'est la seule
    asymetrie : c'est une cle de manifeste gelee par `EPIC11-ARB-221`, et
    c'est le CONTEXTE des cinq cibles fines. `version=` se lie donc a la
    cible fine, comme `liberer_le_rang=` le fait deja ; sans cible fine il est
    REFUSE plutot qu'ignore, le rang du lot vivant deja dans son identifiant.

    **Le raccord `frames=` a ete RETIRE le 2026-09-04** (revue 11.14, couche
    1, finding `T1`), puis `frames_scannees=` et `tirage=` le 2026-09-05, par
    le meme arbitrage de retrait PUR (`EPIC11-ARB-220`) : ni alias, ni refus
    special. Un entier passe a `planche=`, `master=` ou `lot_scanne=` est en
    revanche refuse NOMMEMENT, et ce n'est pas la meme chose : `2` est vrai au
    sens de Python, donc l'ancien appelant leverait le drapeau et retomberait
    sur le rang d'origine -- il supprimerait la version 1 en croyant supprimer
    la 2. Une chaine passee a `master=` tombe dans le meme filet, et c'est
    exactement l'ancienne forme `master="outputs/....mov"`.
    """
    if (lot_id is None) == (rush_id is None):
        raise ProjectMaintenanceError(
            "remove_project_element vise EXACTEMENT un lot (lot_id=...) ou un rush "
            "(rush_id=...), jamais les deux a la fois, jamais aucun des deux."
        )
    for nom_drapeau, valeur in (("planche", planche), ("master", master),
                                ("lot-scanne", lot_scanne),
                                ("frames-extraites", frames_extraites)):
        # **Un entier n'est pas un drapeau** (`EPIC11-ARB-224`). Le symetrique
        # exact du refus qui vivait ici avant -- « un booleen n'est pas un
        # rang » --, et il mord PLUS FORT : `2` est vrai au sens de Python,
        # donc un appelant reste a l'ancienne signature verrait le drapeau
        # leve et le rang retomber a l'ORIGINE. Il supprimerait la version 1
        # en croyant supprimer la 2, sans un mot.
        if not isinstance(valeur, bool):
            raise ProjectMaintenanceError(
                f"--{nom_drapeau} est un DRAPEAU nu, recu {valeur!r}. Le rang "
                f"se donne par --version. Aucune suppression n'a eu lieu."
            )
    if version is not None and (
            isinstance(version, bool) or not isinstance(version, int)):
        # **Un booleen n'est pas un rang** (trouve en revue, couche 2, sur les
        # cibles qui portaient alors le rang elles-memes). `--version True`
        # supprimerait le rang d'ORIGINE sous le nom « v True ».
        raise ProjectMaintenanceError(
            f"--version attend un RANG entier, recu {version!r} "
            f"({'un booleen' if isinstance(version, bool) else type(version).__name__}). "
            "Aucune suppression n'a eu lieu."
        )
    if version is not None and version != version_ranks.RANG_ORIGINE and not (
            naming.VERSION_RANK_MIN <= version <= naming.VERSION_RANK_MAX):
        # **UN RANG SE BORNE, ET LE DEPOT LE BORNE PARTOUT AILLEURS** (revue
        # `EPIC11-ARB-224`, couche 2 `C2-3`, critique). Le diff validait
        # `--version` contre le booleen et contre le non-entier, jamais contre
        # `VERSION_RANK_MIN`/`MAX` : `--version 0`, `-1` et `999` atteignaient
        # les resolveurs.
        #
        # Sur `--planche`, le refus qui en sortait affirmait « le rang 0 a
        # pourtant ete CONSOMME (ligne d'eau: 3) » -- FAUX, zero n'est pas un
        # rang, la branche testant seulement `rang <= ligne_actuelle` -- et
        # nommait comme issue `--liberer-le-rang`, qui rendait **le meme refus
        # mot pour mot** (`est_en_queue(0, 3)` vaut `False`). Les deux issues
        # nommees etaient refusees ensemble : le blocage sec deguise
        # qu'`EPIC11-ARB-89` interdit, et que le commentaire du refus voisin
        # revendique justement fermer.
        #
        # Ce refus-ci nomme DEUX issues reellement typables : un rang de la
        # plage, ou l'omission qui vise l'origine.
        raise ProjectMaintenanceError(
            f"--version {version} est hors des rangs possibles. Le rang "
            f"d'ORIGINE est {version_ranks.RANG_ORIGINE} et ne porte aucun "
            f"fragment (`EPIC11-ARB-88`); les versions vont de "
            f"{naming.VERSION_RANK_MIN} a {naming.VERSION_RANK_MAX}. Viser une "
            f"version existante (--version {naming.VERSION_RANK_MIN}..."
            f"{naming.VERSION_RANK_MAX}), ou OMETTRE --version pour viser "
            "l'origine. Aucune suppression n'a eu lieu."
        )
    if planche and lot_id is None:
        raise ProjectMaintenanceError(
            "planche= vise une planche DANS un lot: il exige lot_id=. "
            "Un rush ne porte pas de planche. Aucune suppression n'a eu lieu."
        )
    if _cible_fine_donnee(scan):
        _refuser_un_designateur_versionne("--scan", scan, scan)
    # **Les arguments PRODUCTEURS n'ont de sens qu'avec la cible qu'ils
    # designent** (`EPIC11-ARB-224`). Les ignorer serait pire ici qu'ailleurs :
    # `--lot L --profile prores_422` sans `--master` viserait le LOT ENTIER,
    # c'est-a-dire la destruction la plus large de cette commande, sur un
    # malentendu. « Un drapeau sans effet est un mensonge », deja paye deux
    # fois dans ce module.
    for nom_argument, valeur in (("--profile", profile),
                                 ("--resolution", resolution)):
        if valeur is not None and not master:
            raise ProjectMaintenanceError(
                f"{nom_argument} accompagne --master, qui designe un master par "
                "les arguments qui l'ont produit: seul, il ne designe rien et "
                "la cible serait le LOT ENTIER. Aucune suppression n'a eu lieu."
            )
    if master and profile is None:
        # Deviner le profil serait le meme geste que deviner un chemin -- et un
        # lot porte legitimement plusieurs masters (story 6.5, docstring de
        # `_famille_de_master`).
        raise ProjectMaintenanceError(
            "--master exige --profile: un lot porte legitimement plusieurs "
            "masters, a des profils differents, et aucun n'est le defaut. "
            "Aucune suppression n'a eu lieu."
        )
    cibles_fines = [
        nom for nom, valeur in (
            ("planche", planche), ("master", master), ("scan", scan),
            ("lot-scanne", lot_scanne), ("frames-extraites", frames_extraites),
        ) if _cible_fine_donnee(valeur)
    ]
    if len(cibles_fines) > 1:
        raise ProjectMaintenanceError(
            "Une seule cible fine a la fois: "
            + ", ".join(f"--{n}" for n in cibles_fines)
            + " ont ete donnes ensemble. Chacune vise un objet versionne "
            "different, et les combiner ne veut rien dire. Aucune suppression "
            "n'a eu lieu."
        )
    if cibles_fines and lot_id is None:
        raise ProjectMaintenanceError(
            f"--{cibles_fines[0]} vise un objet DANS un lot: il exige lot_id=. "
            "Aucune suppression n'a eu lieu."
        )
    if cibles_fines and avec_scans:
        # **Un drapeau sans effet est un mensonge** (trouve en revue, couche 2).
        # `--avec-scans` accompagne la suppression d'un LOT ; sur une cible
        # fine il n'etait ni honore ni signale, et le dossier de scan n'etait
        # meme pas nomme. La cible `--scan` fait le geste explicitement.
        raise ProjectMaintenanceError(
            f"--avec-scans accompagne la suppression d'un LOT entier: il n'a "
            f"aucun sens avec --{cibles_fines[0]}, qui vise un seul objet. "
            "Pour retirer un dossier de scan seul, utiliser --scan <slug>. "
            "Aucune suppression n'a eu lieu."
        )
    if cibles_fines and confirmation_dernier_lot:
        raise ProjectMaintenanceError(
            f"--confirmer-dernier-lot protege le DERNIER lot d'un projet: il "
            f"n'a aucun sens avec --{cibles_fines[0]}, qui ne retire pas le "
            "lot. Aucune suppression n'a eu lieu."
        )
    if version is not None and not cibles_fines:
        # **Un drapeau sans effet est un mensonge**, et l'ignorer serait pire
        # ici qu'ailleurs : l'operateur croirait avoir vise une version. Le
        # rang d'un LOT vit dans son `lot_id` -- cle de manifeste gelee par
        # `EPIC11-ARB-221` --, il n'y a donc pas de second lieu ou l'ecrire.
        raise ProjectMaintenanceError(
            "--version porte le rang d'une CIBLE FINE (--planche, --lot-scanne, "
            "--scan, --master): sans l'une d'elles il n'a rien a designer. Le "
            "rang d'un lot vit dans son lot_id, fragment compris -- viser une "
            "autre version du lot, c'est la nommer (--lot <id>_v<rang>). "
            "Aucune suppression n'a eu lieu."
        )
    if _cible_fine_donnee(frames_extraites):
        # **Les deux refus propres au seul objet de cette commande qui n'a pas
        # de rang PROPRE.** Ils sont poses ici, avec les autres gardes
        # d'arguments, et non plus bas : un argument sans effet se refuse avant
        # que le manifeste soit meme lu, sinon un lot sans `frames_dir` rendrait
        # « pas de frames a retirer » a qui a surtout mal designe sa cible.
        #
        # Le motif est mesure et il vit dans `_famille_des_frames_extraites` :
        # le dossier de frames extraites porte le rang du LOT, pas le sien. Un
        # `--version` lu ici designerait le dossier d'un AUTRE lot, et un
        # `--liberer-le-rang` rendrait un rang qu'une entree encore declaree
        # porte -- deux lots finiraient par porter le meme numero.
        if version is not None:
            raise ProjectMaintenanceError(
                _refus_de_rang_non_independant(
                    "jeu de frames extraites", "lot", "--version")
            )
        if liberer_le_rang:
            raise ProjectMaintenanceError(
                _refus_de_rang_non_independant(
                    "jeu de frames extraites", "lot", "--liberer-le-rang")
            )
    if liberer_le_rang and lot_id is None:
        # **Un drapeau sans effet est un mensonge** (trouve en revue, couches 2
        # et 3). Il etait ignore en silence, ce que la docstring de
        # `version_ranks.refus_de_liberer_hors_queue` interdit explicitement :
        # « l'operateur qui passe le drapeau en attend un effet ; l'ignorer lui
        # ferait croire le rang disponible ».
        raise ProjectMaintenanceError(
            "liberer_le_rang= porte sur un objet VERSIONNE: il exige lot_id=, "
            "seul ou avec planche=. Un rush n'a pas de rang de version -- son "
            "identifiant ne porte jamais de fragment `_vN`. Aucune suppression "
            "n'a eu lieu."
        )

    project_dir = Path(project_dir)
    manifest_path = project_dir / "project.json"
    if manifest_path.is_file():
        try:
            manifest: dict[str, Any] = dict(load_manifest(manifest_path))
        except (ValueError, OSError) as erreur:
            # Trouve en revue : un `project.json` corrompu levait le
            # `json.JSONDecodeError`/`OSError` BRUT de `load_manifest`, pas
            # l'erreur de domaine que le reste de ce module declare.
            raise ProjectMaintenanceError(
                f"{manifest_path} est illisible ou n'est pas un JSON valide ({erreur}). "
                "Aucune suppression n'a eu lieu."
            ) from erreur
    else:
        manifest = {}
    lots = list(manifest.get("lots") or [])
    rushes = list(manifest.get("rushes") or [])

    if lot_id is not None:
        cible = lot_id
        lot = next((l for l in lots if isinstance(l, Mapping) and l.get("lot_id") == lot_id), None)
        if lot is None:
            raise ProjectMaintenanceError(
                f"Lot inconnu du manifeste de {project_dir}: {lot_id!r}"
            )
        # LE RANG DE LA CIBLE FINE, lu une seule fois pour les quatre
        # (`EPIC11-ARB-224`). Son ABSENCE dit l'ORIGINE, elle ne dit pas
        # « pas de version » : `EPIC11-ARB-88` etablit que le rang d'origine
        # ne porte aucun fragment, et c'est la meme convention qui se lit ici.
        rang_vise = version if version is not None else version_ranks.RANG_ORIGINE
        # **LE MEME predicat que la garde ci-dessus**, pour les cinq cibles
        # (`C2-2`). C'est la divergence entre les deux lectures qui detruisait
        # en silence, pas l'une ou l'autre prise isolement : les ecrire toutes
        # avec `_cible_fine_donnee` est ce qui empeche la divergence de
        # revenir, la ou corriger un seul des deux cotes la laisserait
        # possible au prochain argument qui change de nature.
        if _cible_fine_donnee(planche):
            return _retirer_un_tirage(
                project_dir, manifest_path, manifest, lot, rang_vise, dry_run,
                liberer_le_rang=liberer_le_rang)
        # Les trois cibles fines qu'`EPIC11-ARB-111` a AJOUTEES -- un compte
        # historique, pas celui de l'ensemble courant, qui en porte cinq --,
        # toutes servies par LA
        # regle unique -- elles ne fournissent qu'un descripteur de famille.
        if _cible_fine_donnee(master):
            return _retirer_un_objet_versionne(
                project_dir, manifest_path, manifest,
                _famille_de_master(project_dir, manifest, lot, profile,
                                   resolution, rang_vise),
                dry_run, liberer_le_rang)
        if _cible_fine_donnee(scan):
            return _retirer_un_objet_versionne(
                project_dir, manifest_path, manifest,
                _famille_de_scan(project_dir, manifest, lot, scan, rang_vise),
                dry_run, liberer_le_rang)
        if _cible_fine_donnee(lot_scanne):
            return _retirer_un_objet_versionne(
                project_dir, manifest_path, manifest,
                _famille_du_lot_scanne(
                    project_dir, manifest, lot, rang_vise),
                dry_run, liberer_le_rang)
        # La cinquieme cible fine, et la seule qui n'ait pas de rang propre :
        # elle ne recoit donc pas `rang_vise`, qui est ici l'ORIGINE par defaut
        # et n'aurait designe qu'elle-meme (`--version` est refuse plus haut).
        if _cible_fine_donnee(frames_extraites):
            return _retirer_un_objet_versionne(
                project_dir, manifest_path, manifest,
                _famille_des_frames_extraites(project_dir, manifest, lot),
                dry_run, liberer_le_rang)
        # LA LIGNE D'EAU DE LA FAMILLE (`EPIC11-ARB-108`). Calculee avant toute
        # ecriture, pour que l'apercu dise exactement ce que la confirmation
        # ferait -- et pour que le refus hors queue tombe avant la moindre
        # suppression.
        base_famille, ligne_famille, restants_famille = (
            _ligne_d_eau_de_la_famille_du_lot(manifest, lot))
        rang_du_lot = lot.get("version_rank")
        rang_du_lot = (
            rang_du_lot if isinstance(rang_du_lot, int)
            and not isinstance(rang_du_lot, bool) else version_ranks.RANG_ORIGINE
        )
        en_queue_lot = version_ranks.est_en_queue(rang_du_lot, ligne_famille)
        if liberer_le_rang and not en_queue_lot:
            raise ProjectMaintenanceError(
                version_ranks.refus_de_liberer_hors_queue(
                    rang_du_lot, ligne_famille, "lot")
                + " Aucune suppression n'a eu lieu."
            )
        liberables_lot = (
            version_ranks.rangs_liberables(ligne_famille, restants_famille)
            if en_queue_lot else ()
        )
        if len(lots) <= 1 and not confirmation_dernier_lot:
            raise LastLotRefusedError(
                f"{lot_id!r} est le DERNIER lot de ce projet. Le supprimer viderait le "
                "projet de tout lot. Issue: relancer avec --confirmer-dernier-lot (en "
                "ligne de commande) ou confirmation_dernier_lot=True (en appel de "
                "coeur) pour confirmer explicitement cette suppression."
            )
        autres = [l for l in lots if l is not lot]
        fichiers = _fichiers_du_lot(project_dir, lot, autres, manifest=manifest)
        # Les annexes LOURDES, par filiation (Egan, 2026-08-31). Sans elles
        # le versionnage ne fait qu'AGGRAVER l'occupation disque: une version
        # de lot 4K a 12 im/s pese plus de 2 Go, et ne liberer que les frames
        # revenait a ne rendre que la moitie legere.
        annexes, attendus_absents = _annexes_du_lot(project_dir, manifest, lot, autres)
        fichiers = fichiers + annexes
        # Les scans, sous leur consentement propre (`EPIC11-ARB-90`), et TOUS
        # depuis `EPIC11-ARB-109`: un lot rescanne depuis deux slugs en a deux,
        # et n'en supprimer qu'un laisserait des images derriere en annoncant
        # `supprime=True`.
        dossiers_presents = [
            d for d in _scans_du_lot(project_dir, manifest, lot) if d.is_dir()
        ]
        scans_signales = tuple(
            d.relative_to(project_dir).as_posix() for d in dossiers_presents
        )
        scans_supprimes = list(dossiers_presents) if avec_scans else []
        if avec_scans:
            for dossier, signale in zip(dossiers_presents, scans_signales):
                for chemin in dossier.rglob("*"):
                    if chemin.is_file():
                        fichiers.append(
                            chemin if chemin.is_symlink()
                            else _sous_le_projet(
                                project_dir, chemin, "ingest_slug", signale)
                        )
    else:
        base_famille, ligne_famille, restants_famille = None, version_ranks.RANG_ORIGINE, set()
        en_queue_lot, liberables_lot = False, ()
        rang_du_lot = version_ranks.RANG_ORIGINE
        cible = rush_id
        rush = next(
            (r for r in rushes if isinstance(r, Mapping) and r.get("rush_id") == rush_id), None
        )
        if rush is None:
            raise ProjectMaintenanceError(
                f"Rush inconnu du manifeste de {project_dir}: {rush_id!r}"
            )
        lots_du_rush = [l for l in lots if isinstance(l, Mapping) and l.get("rush_id") == rush_id]
        if lots_du_rush:
            noms = ", ".join(sorted(str(l.get("lot_id")) for l in lots_du_rush))
            raise ProjectMaintenanceError(
                f"Le rush {rush_id!r} porte encore {len(lots_du_rush)} lot(s) ({noms}): "
                "remove_project_element ne supprime jamais un rush qui porte encore des "
                "lots. Supprimer d'abord chaque lot, un par un."
            )
        if len(rushes) <= 1 and not confirmation_dernier_lot:
            raise LastLotRefusedError(
                f"{rush_id!r} est le DERNIER rush de ce projet. Le supprimer viderait le "
                "projet de tout rush. Issue: relancer avec --confirmer-dernier-lot (en "
                "ligne de commande) ou confirmation_dernier_lot=True (en appel de "
                "coeur) pour confirmer explicitement cette suppression."
            )
        # Un rush source n'a pas de fichiers geres par ce mecanisme au-dela de
        # son entree manifest: son fichier source original vit hors du
        # dossier projet (`rush_source_path`, invariant de portabilite v2),
        # et aucun lot n'y est plus rattache (garde ci-dessus).
        fichiers = []
        attendus_absents: list[str] = []
        scans_signales: tuple[str, ...] = ()
        scans_supprimes: list[Path] = []

    fichiers_a_supprimer = _chemins_a_supprimer(project_dir, fichiers)

    if dry_run:
        return RapportSuppression(
            cible=cible,
            fichiers_a_supprimer=fichiers_a_supprimer,
            dry_run=True,
            supprime=False,
            fichiers_attendus_absents=tuple(attendus_absents),
            dossiers_de_scan=scans_signales,
            scan_inclus=bool(avec_scans and scans_signales),
            tirage_en_queue=en_queue_lot,
            rangs_liberables=liberables_lot,
            rang_libere=bool(liberer_le_rang and en_queue_lot),
            rang_vise=rang_du_lot,
        )

    # AC 10: le manifeste D'ABORD -- un echec de suppression de fichier laisse
    # alors un manifeste coherent avec ce qui reste reellement lisible. La
    # copie d'avant sert au rollback du bas de fonction.
    manifest_avant = json.loads(json.dumps(manifest))
    if lot_id is not None:
        manifest["lots"] = [
            l for l in lots if not (isinstance(l, Mapping) and l.get("lot_id") == lot_id)
        ]
        if base_famille is not None:
            _poser_la_ligne_d_eau_du_lot(
                manifest, base_famille, ligne_famille, restants_famille,
                liberer_le_rang, en_queue_lot)
        # **La ligne d'eau des SCANS aussi** (trouve en revue, couche 3, et
        # c'est le chemin DESTRUCTEUR principal). `--avec-scans` fait le
        # `rmtree` des dossiers de scan -- la couche 2 avait nomme ce chemin
        # explicitement -- et rien ne posait `scan_version_watermarks` :
        # supprimer un lot portant les scans S, S_v2 et S_v3 faisait retomber
        # le prochain rang de 4 a 1, soit TROIS rangs rendus par defaut et sans
        # demande. C'est l'inverse du point 3 d'`EPIC11-ARB-92`, et sur des
        # planches PAPIER qu'aucun calcul ne refait.
        #
        # La ligne est posee TELLE QUELLE : `--liberer-le-rang` porte sur le
        # rang du LOT, pas sur ceux de ses scans, et rendre ces derniers en
        # passant serait exactement la liberation silencieuse qu'on ferme ici.
        if avec_scans:
            _poser_les_lignes_d_eau_des_scans(project_dir, manifest, lot)
    else:
        manifest["rushes"] = [
            r for r in rushes if not (isinstance(r, Mapping) and r.get("rush_id") == rush_id)
        ]
    _ecrire_manifeste(manifest_path, manifest)

    dossiers_touches: set[Path] = set()
    echecs: list[str] = []
    for chemin in fichiers:
        dossiers_touches.add(chemin.parent)
        try:
            chemin.unlink()
        except OSError:
            # Trouve en revue : avale en silence, le rapport rendait
            # `supprime=True` alors qu'un fichier restait sur le disque --
            # exactement la fuite de disque que cette story existe pour
            # fermer (droits, fichier verrouille, systeme de fichiers en
            # lecture seule). Le manifeste est deja a jour (AC 10, ordre
            # impose) ; le rapport doit desormais le DIRE.
            echecs.append(chemin.relative_to(project_dir).as_posix())
    # Le sous-arbre du SCAN entier, et pas seulement les dossiers parents des
    # fichiers supprimes (revue, majeur 1). Jusqu'ici ce mecanisme ne visait
    # que des dossiers PLATS (`frames/<lot>/`); un dossier de scan peut etre
    # arborescent, et il l'etait: `scans/<slug>/pages/...` laissait
    # `scans/<slug>` et `scans/<slug>/pages` derriere lui avec
    # `supprime=True`. Un scan VIDE, lui, n'entrait meme pas dans
    # `dossiers_touches` et survivait a sa propre suppression.
    for scan_supprime in scans_supprimes:
        if not scan_supprime.is_dir():
            continue
        for chemin in sorted(
            scan_supprime.rglob("*"), key=lambda p: len(p.parts), reverse=True
        ):
            if chemin.is_dir() and not chemin.is_symlink():
                dossiers_touches.add(chemin)
        dossiers_touches.add(scan_supprime)

    # Nettoyage des dossiers devenus vides, du plus profond au moins profond,
    # jamais du dossier projet lui-meme (hors de portee de ce mecanisme).
    for dossier in sorted(dossiers_touches, key=lambda p: len(p.parts), reverse=True):
        try:
            if dossier.is_dir() and not any(dossier.iterdir()):
                dossier.rmdir()
        except OSError:
            pass

    # **Un echec partiel RESTAURE l'entree du manifeste** (revue Opus finale).
    # L'ordre « manifeste d'abord » (AC 10) existe pour qu'un echec laisse un
    # manifeste coherent avec ce qui reste lisible -- mais la cible se resout
    # PAR `lot_id`, si bien que retirer l'entree alors que les fichiers
    # survivent rendait le lot introuvable : `remove_project_element` rendait
    # ensuite « Lot inconnu du manifeste ». Zero issue, l'operateur retombait
    # sur le `rm -rf` manuel, c'est-a-dire la fuite que cette commande existe
    # pour fermer -- creee par elle. Des lors que des fichiers restent, le lot
    # EXISTE encore : le manifeste doit le declarer, et le geste redevient
    # rejouable.
    if echecs:
        _ecrire_manifeste(manifest_path, manifest_avant)
    return RapportSuppression(
        cible=cible,
        fichiers_a_supprimer=fichiers_a_supprimer,
        dry_run=False,
        supprime=not echecs,
        fichiers_non_supprimes=tuple(sorted(echecs)),
        fichiers_attendus_absents=tuple(attendus_absents),
        dossiers_de_scan=scans_signales,
        scan_inclus=bool(avec_scans and scans_signales),
        tirage_en_queue=en_queue_lot,
        rangs_liberables=liberables_lot,
        # Un echec partiel RESTAURE le manifeste d'avant, donc la ligne d'eau
        # n'a pas bouge non plus : le rapport ne doit pas annoncer un rang rendu.
        rang_libere=bool(liberer_le_rang and en_queue_lot and not echecs),
        rang_vise=rang_du_lot,
    )


# ---------------------------------------------------------------------------
# `EPIC11-ARB-264` -- supprimer un GROUPE : N appels, au mieux, ligne par ligne
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LigneDeGroupe:
    """Le compte rendu d'UNE cible d'un groupe : ce qu'elle etait, ce qu'elle
    est devenue, et **pourquoi** quand elle a refuse.

    Un couple `(rapport, refus)` plutot qu'un booleen : le rapport porte deja
    tout ce qui s'est passe quand ca s'est bien passe, et un refus porte une
    phrase que rien d'autre ne sait rediger -- c'est le coeur qui sait pourquoi
    il refuse, et le reecrire au-dessus serait une seconde verite
    (`EPIC5-ARB-78`).

    **Exactement l'un des deux est renseigne**, et le `__post_init__` le tient :
    une ligne qui porterait les deux, ou aucun, ne dirait rien de ce qui est
    arrive a l'objet -- c'est-a-dire la seule chose que ce rapport existe pour
    dire.
    """

    #: Les mots-cles passes a `remove_project_element`, verbatim. Ils sont
    #: gardes plutot que reduits a un libelle : c'est ce qu'il faut retaper pour
    #: rejouer la ligne, et `EPIC11-ARB-264` demande qu'on puisse « relancer en
    #: sachant ce qui reste ».
    cible: Mapping[str, Any]
    #: Ce que l'operateur LIT de cette ligne. Compose par l'appelant, qui seul
    #: connait le vocabulaire de son ecran (AC 1.3).
    libelle: str
    rapport: RapportSuppression | None = None
    #: Le message du coeur, VERBATIM. Vide quand la ligne est passee.
    refus: str = ""
    #: Vrai quand `refus` porte une INTERRUPTION -- une exception hors du
    #: domaine du coeur, `OSError` en tete -- plutot qu'un refus prononce.
    #:
    #: **La distinction est de NATURE, et elle se dit** (findings `C2-5` /
    #: `C3-6`). Un refus garantit que rien n'a ete detruit ; une interruption
    #: ne garantit rien -- un volume plein pendant la RESTAURATION du
    #: manifeste laisse des fichiers detruits et un manifeste deja ecrit. Les
    #: deux voyagent dans le meme champ pour que `refusees` -- que l'ecran lit
    #: pour decider si le groupe est parti -- les compte toutes les deux : se
    #: tromper du cote prudent est le seul sens acceptable.
    interrompue: bool = False

    def __post_init__(self) -> None:
        if (self.rapport is None) == (not self.refus):
            raise ProjectMaintenanceError(
                f"Ligne de groupe incoherente pour {self.libelle!r}: elle doit "
                "porter SOIT un rapport, SOIT un refus, jamais les deux et "
                "jamais aucun."
            )

    @property
    def passee(self) -> bool:
        """La ligne a-t-elle fait ce qu'on lui demandait ?

        **Un rapport ne suffit pas** : `remove_project_element` rend un rapport
        avec `supprime=False` quand des fichiers ont resiste (droits, fichier
        verrouille). Lire la seule presence du rapport ferait compter comme
        « partie » une ligne dont les fichiers occupent toujours le disque --
        exactement la fuite que le champ `fichiers_non_supprimes` existe pour
        rendre visible.

        En apercu, ou rien n'est ecrit, `supprime` vaut faux pour tout le
        monde : la ligne est « passee » des lors que le coeur ne l'a pas
        refusee.
        """
        if self.rapport is None:
            return False
        return self.rapport.dry_run or self.rapport.supprime


@dataclass(frozen=True)
class RapportDeGroupe:
    """Ce que N suppressions ont fait, **ligne par ligne** (`EPIC11-ARB-264`).

    Egan, verbatim de l'option qu'il a choisie le 2026-09-07 : « Au mieux, avec
    un compte rendu ligne par ligne. Le projet peut rester a moitie supprime, et
    il faut relancer en sachant ce qui reste. »

    **Il n'y a donc PAS de champ « reussi »**, et c'est delibere : un booleen
    global sur une operation qui admet le succes partiel ferait lire « echec »
    a un groupe dont neuf lignes sur dix sont parties, ou « succes » a un groupe
    dont une ligne a resiste. Les cardinaux se lisent des lignes, qui sont la
    verite.
    """

    lignes: tuple[LigneDeGroupe, ...]
    dry_run: bool

    @property
    def passees(self) -> tuple[LigneDeGroupe, ...]:
        return tuple(l for l in self.lignes if l.passee)

    @property
    def refusees(self) -> tuple[LigneDeGroupe, ...]:
        """Les lignes que le coeur a refusees, **et elles seules**.

        Distinctes des lignes qui ont laisse des fichiers derriere elles : un
        refus n'a rien detruit, un echec partiel si. Les confondre ferait
        annoncer « rien n'a bouge » sur un groupe a moitie parti.

        **Les lignes INTERROMPUES y figurent aussi**, et la garantie « un
        refus n'a rien detruit » ne vaut donc que des lignes dont
        `interrompue` est faux -- que :attr:`interrompues` isole. Elles sont
        comptees ici parce que le seul lecteur de cette liste s'en sert pour
        decider si le groupe est parti EN ENTIER : les en sortir ferait
        annoncer un groupe complet la ou une ligne a explose.
        """
        return tuple(l for l in self.lignes if l.refus)

    @property
    def interrompues(self) -> tuple[LigneDeGroupe, ...]:
        """Les lignes qu'une exception HORS DOMAINE a arretees.

        Un `OSError` -- volume plein, montage passe en lecture seule : le
        regime de terrain d'un projet sur disque externe -- traversait
        `remove_project_group` et emportait le compte rendu des lignes
        PRECEDENTES, deja detruites. C'est le contraire exact de
        `EPIC11-ARB-264` (« au mieux, ligne par ligne ; il faut relancer en
        sachant ce qui reste »), et c'est ce que le finding `C2-5` a mesure.
        """
        return tuple(l for l in self.lignes if l.interrompue)

    @property
    def partiellement_supprimees(self) -> tuple[LigneDeGroupe, ...]:
        """Les lignes acceptees dont des fichiers ont resiste."""
        return tuple(
            l for l in self.lignes
            if l.rapport is not None and not l.rapport.dry_run
            and not l.rapport.supprime
        )

    @property
    def fichiers_a_supprimer(self) -> tuple[str, ...]:
        """TOUS les chemins des lignes acceptees, dans l'ordre des lignes.

        **Concatenes, jamais fusionnes ni tries a nouveau.** Chaque appel a
        `remove_project_element` a deja trie SA liste par chemin POSIX
        (`EPIC11-ARB-243`) ; un tri global par-dessus melangerait les objets et
        ferait perdre la seule chose que la liste de groupe ajoute -- savoir
        quel fichier part avec quelle ligne.
        """
        chemins: list[str] = []
        for ligne in self.lignes:
            if ligne.rapport is not None:
                chemins.extend(ligne.rapport.fichiers_a_supprimer)
        return tuple(chemins)


def remove_project_group(
    project_dir: str | Path,
    cibles: Sequence[tuple[str, Mapping[str, Any]]],
    *,
    dry_run: bool = True,
    retirer=None,
) -> RapportDeGroupe:
    """Supprimer les N objets d'un GROUPE, au mieux (`EPIC11-ARB-264`).

    `cibles` est une suite de couples `(libelle, mots-cles)`. Les mots-cles sont
    ceux de :func:`remove_project_element` -- cette fonction n'en compose aucun
    et n'en juge aucun : **la boucle est au-dessus, jamais dedans**. Un groupe
    n'existe pas au coeur (`project_inventory` ne produit aucun noeud de
    regroupement, c'est l'ecran qui les fabrique), et `planche=True` « vise UNE
    SEULE planche au lieu du lot entier » : il n'y a donc rien a elargir a
    l'interieur du coeur, seulement N appels a enchainer au-dessus.

    **Au mieux, jamais tout-ou-rien** -- c'est l'arbitrage, et le document
    `decisions-2026-09-07-epic11-arb-264.md` porte les trois options. Un refus
    n'annule pas les lignes precedentes et n'arrete pas les suivantes : chacune
    est tentee, et le rapport dit pour chacune ce qui s'est passe.

    **Et une PANNE non plus n'arrete le groupe** (finding `C2-5`). La premiere
    redaction n'attrapait que `ProjectMaintenanceError` : un `OSError` du coeur
    -- volume plein, montage passe en lecture seule, c'est-a-dire le regime de
    terrain d'un projet sur disque externe -- traversait cette boucle et
    emportait le compte rendu des lignes DEJA DETRUITES. « Au mieux, ligne par
    ligne » devenait, exactement dans le regime ou l'arbitrage compte le plus,
    « tout perdu, y compris la trace ». Une panne devient donc une ligne, comme
    un refus, marquee `interrompue` parce que ce n'est pas la meme chose : un
    refus n'a rien detruit, une interruption ne le promet pas.

    **Pourquoi le tout-ou-rien n'etait pas une option honnete**, et c'est mesure
    plutot que suppose : `remove_project_element` restaure SON entree de
    manifeste sur echec, mais rien ne remet un fichier detruit ni un dossier
    passe au `rmtree`. Un « tout ou rien » n'aurait pu annuler que la moitie
    manifeste, c'est-a-dire produire un manifeste declarant des fichiers
    disparus -- exactement l'incoherence que l'ordre « manifeste d'abord »
    (AC 10) existe pour empecher.

    **L'ORDRE est celui que l'appelant donne, et il n'est pas trie.** Les
    membres d'un groupe viennent de l'arbre, qui garde l'ordre du manifeste, et
    cet ordre porte une information qu'un tri detruirait (`EPIC11-ARB-109`).
    C'est aussi l'ordre de DESTRUCTION, donc celui que l'apercu doit montrer.

    **Chaque appel relit `project.json`**, et c'est ce qui rend N appels
    successifs corrects plutot que fragiles : une ligne devenue invalide parce
    que la precedente est partie refuse AVEC SA VRAIE RAISON, au lieu d'agir sur
    un etat perime.

    `retirer` est le point d'injection des bancs. Il vaut
    :func:`remove_project_element` par defaut -- pose ici et non dans la
    signature, un defaut evalue a la definition figeant la fonction avant que
    les bancs puissent la doubler par le module.
    """
    if retirer is None:
        retirer = remove_project_element
    cibles = tuple(cibles)
    if not cibles:
        # **Un refus NOMME plutot qu'un succes a zero ligne.** Un groupe sans
        # membre n'existe pas dans l'arbre -- il n'est fabrique que s'il a des
        # objets a porter --, donc une liste vide dit qu'un appelant s'est
        # trompe de noeud. Rendre un rapport vide le lui cacherait, et l'ecran
        # annoncerait « 0 fichier supprime » comme un travail accompli.
        raise ProjectMaintenanceError(
            "remove_project_group vise les N objets d'un groupe: la liste de "
            "cibles est vide, il n'y a rien a supprimer. Un groupe sans membre "
            "n'existe pas dans l'arbre d'inventaire. Aucune suppression n'a eu "
            "lieu."
        )
    lignes: list[LigneDeGroupe] = []
    for libelle, cible in cibles:
        try:
            rapport = retirer(project_dir, dry_run=dry_run, **dict(cible))
        except ProjectMaintenanceError as refus:
            # **La raison REELLE, verbatim** (`EPIC11-ARB-258` : un refus se
            # prononce). Une phrase generique -- « cet objet n'a pas pu etre
            # supprime » -- couterait exactement ce que l'arbitrage veut
            # eviter : relancer sans savoir ce qui reste, ni pourquoi.
            #
            # **Un refus MUET reste une ligne, jamais un groupe avorte**
            # (finding `C3-6`). `LigneDeGroupe.refus` prend la vacuite pour
            # discriminant : un `ProjectMaintenanceError("")` faisait lever
            # `__post_init__` HORS de ce `try`, et le groupe entier rendait
            # zero ligne -- une exception de compte rendu detruisant le compte
            # rendu. Aucun site du coeur ne leve aujourd'hui sans message : le
            # risque est structurel, et c'est pourquoi il se ferme ici, au
            # seul endroit qui fabrique une ligne a partir d'une exception,
            # plutot qu'en affaiblissant l'invariant -- qui est juste.
            lignes.append(LigneDeGroupe(
                cible=dict(cible), libelle=libelle,
                refus=str(refus) or (
                    f"{type(refus).__name__} sans message. Le coeur a refuse "
                    "cette ligne sans dire pourquoi ; aucune suppression n'a eu "
                    "lieu pour elle. Rejouer la cible seule pour obtenir la "
                    "raison.")))
            continue
        except Exception as panne:
            # **Rien ne traverse cette boucle** (finding `C2-5`). Le coeur ne
            # leve pas que des refus : `_ecrire_manifeste` releve ses
            # `OSError` -- volume plein, montage en lecture seule --, et
            # `unlink` peut lever ce que le systeme veut. Une exception qui
            # traversait emportait le compte rendu des lignes PRECEDENTES,
            # deja detruites : le tout-ou-rien que `EPIC11-ARB-264` refuse,
            # obtenu par accident.
            #
            # **`Exception`, jamais `BaseException`** : un `KeyboardInterrupt`
            # est une demande d'ARRET de l'operateur, pas une panne de ligne.
            # L'avaler ferait continuer le groupe apres un Ctrl-C, c'est-a-dire
            # detruire ce qu'on vient de demander d'epargner.
            lignes.append(LigneDeGroupe(
                cible=dict(cible), libelle=libelle, interrompue=True,
                refus=(
                    f"Interrompue par {type(panne).__name__}: {panne}. Cette "
                    "ligne n'est PAS un refus: elle a peut-etre detruit une "
                    "partie de ses fichiers avant de s'arreter, et le "
                    "manifeste peut ne plus la declarer. Verifier cet objet "
                    "avant de rejouer.")))
            continue
        lignes.append(LigneDeGroupe(cible=dict(cible), libelle=libelle,
                                    rapport=rapport))
    return RapportDeGroupe(lignes=tuple(lignes), dry_run=dry_run)
