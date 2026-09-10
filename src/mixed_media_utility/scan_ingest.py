"""Ingestion d'un lot de pages scannees (story 5.1).

Porte d'entree de l'Epic 5. Ce module est **la seule** autorite du depot sur la
question « comment un fichier de scan devient un tableau d'image en memoire ».
Il ne detecte rien, ne recadre rien, ne corrige aucune couleur et n'ecrit aucun
manifest: son livrable est un **jeu de pages normalise** et un rapport de ce
qui a ete lu.

Quatre formes d'entree, une seule sortie
----------------------------------------
`--scan` accepte un dossier d'images, un fichier image unique ou un document
PDF multipage (EPIC5-ARB-4), et depuis `EPIC7-ARB-88` une **sequence de
chemins de fichiers** -- la selection multiple d'un explorateur ou d'un
glisser-deposer, qui est *un* lot et non N lots. Les quatre produisent la meme
sequence ordonnee de pages, portant les memes mesures, et **aucune story aval
ne sait par quelle forme le lot est entre**.

Le localisateur, et pourquoi ce n'est pas un chemin
---------------------------------------------------
Une page de dossier a un chemin propre; une page de PDF n'en a aucun, elle
n'existe comme fichier nulle part. Le localisateur est donc un couple
`(chemin relatif de la source, index de page)`, l'index valant `None` pour une
page-fichier. Un rapport qui n'exposerait qu'un chemin obligerait soit a
mentir, soit a ecrire N images derivees sur le disque de l'operateur.
Corollaire assume: relire une page de PDF la **re-rasterise**. C'est
deterministe -- le DPI du rapport fixe le facteur d'echelle -- et c'est un cout
de temps, jamais de fidelite.

Profondeur de bits: constatee, jamais fabriquee
-----------------------------------------------
La lecture passe par `cv2.IMREAD_UNCHANGED`, jamais par un `cv2.imread` nu qui
ramenerait un TIFF 16 bits a 8 bits sans un mot. Une page 8 bits est acceptee
et **declaree** 8 bits: la montee en 16 bits (`x257`) appartient a l'export de
la story 5.6, pas a l'ingestion. Constater une profondeur et en fabriquer une
sont deux choses differentes, et l'aller-retour de gamut d'EPIC5-ARB-2 rend la
distinction critique -- l'expansion amplifie le pas de quantification par `1/k`.

Cas du PDF: PDFium rasterise **exclusivement en 8 bits par canal**. Une page
issue d'un PDF porte donc `source_bit_depth = 8`, declare comme tel y compris
si le PDF embarque une image 16 bits. Ce n'est pas une entorse a l'invariant:
sur un PDF il n'y a rien a tronquer, 8 bits est le plafond reel du rendu, et
l'honnetete consiste a le dire (`PDF_RASTERIZED_AT_8_BITS`) plutot qu'a
revendiquer 16. La consequence -- un lot ingere en PDF entre degrade dans
l'aller-retour de gamut -- est un avertissement, pas un refus: la decision
appartient a l'operateur.

Ordre des pages
---------------
Pour un dossier, tri lexicographique du nom **normalise** (casse repliee, forme
NFC), jamais l'ordre de `os.listdir`. Pour un PDF, l'index de page du document,
jamais l'etiquette de page (`get_page_label`), qui est une chaine d'affichage
arbitraire, parfois absente et non unique. Cet ordre est un **rang de lecture**,
pas le `page_index` metier: celui-la est declare par le QR, et sa
reconciliation appartient a la story 5.2.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import unicodedata
from collections.abc import Mapping, Sequence
from numbers import Real
from typing import Any, NamedTuple
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from . import color_pipeline, progression, qr_codes
from .extraction_previz import FINGERPRINT_PREFIX, canonical_json, fingerprint_of
from .io import project_layout, version_ranks
from .io.naming import VERSION_RANK_MAX, VERSION_RANK_MIN
from .numeric_guards import is_strict_int, is_strict_number

# Extensions reconnues comme pages-fichiers. Tout le reste d'un dossier est
# ignore **sans avertissement et sans etre compte**: le compteur du rapport
# compte des pages, pas des entrees de repertoire (defaut `observed_frame_count`
# consigne en revue de 3.4). `.DS_Store`, `Thumbs.db` et les sous-dossiers
# tombent donc silencieusement.
IMAGE_EXTENSIONS: tuple[str, ...] = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")
PDF_EXTENSIONS: tuple[str, ...] = (".pdf",)

#: Ce qui PORTE des pages, quelle que soit la forme d'entree (`EPIC11-ARB-157`,
#: Egan le 2026-09-01 : « on doit tout accepter : pdf seul, dans un dossier,
#: avec des images ... tout en vrac »).
#:
#: **L'union, jamais une troisieme redaction.** Les deux tables ci-dessus
#: restent les sources ; celle-ci les reunit une fois pour toutes les formes
#: d'entree. Un format ajoute a l'une des deux entre ici sans qu'on y touche --
#: c'est exactement la divergence qui a fait refuser un PDF coche alors que le
#: meme PDF passait au curseur.
PAGE_EXTENSIONS: tuple[str, ...] = IMAGE_EXTENSIONS + PDF_EXTENSIONS

#: Nom du rapport d'ingestion, ecrit a la racine du dossier de lot.
INGEST_DOCUMENT_FILENAME = "ingest.json"

# Le PDF est un espace utilisateur a 72 points par pouce: c'est la seule
# constante qui relie le DPI declare au facteur d'echelle du rendu.
PDF_POINTS_PER_INCH = 72.0

#: Plafond du DPI declare. Il ne borne pas un scanner reel -- aucun n'approche
#: 20 000 ppp -- il borne la **faute de frappe**: sans plafond, un entier Python
#: arbitrairement grand franchit la garde de positivite puis fait exploser la
#: conversion en flottant (`OverflowError: int too large to convert to float`)
#: plusieurs etages plus loin, hors de toute hierarchie d'erreurs nommee.
#: Meme ordre de grandeur que `qr_codes.MAX_RENDER_SIDE_PX`, qui borne deja le
#: rendu pour exactement ce motif. Ajoute apres la revue de 5.2 (5.2-C2-07);
#: un seul plafond pour l'ingestion **et** la detection, jamais deux.
MAX_SCAN_DPI = 20000

#: Vocabulaire **ferme** des avertissements d'ingestion. Un code hors de cette
#: liste est refuse a la construction: un avertissement en chaine libre n'est
#: pas exploitable par la GUI (5.8) ni par le manifest (5.7).
#: Nom distinct de ceux de 3.5 et 4.9 a dessein -- trois vocabulaires voisins
#: fusionnes seraient trois contrats melanges.
SCAN_INGEST_WARNING_CODES: tuple[str, ...] = (
    "DPI_BELOW_QR_MINIMUM",
    "DPI_DECLARED_DIFFERS_FROM_FILE",
    "DPI_NOT_MEASURABLE",
    "MIXED_PAGE_DIMENSIONS",
    "MIXED_BIT_DEPTHS",
    "UNREADABLE_FILE_SKIPPED",
    "PDF_RASTERIZED_AT_8_BITS",
    "PDF_EMBEDS_LOSSY_IMAGE",
    "ALPHA_CHANNEL_DROPPED",
    "IMAGE_PAGES_PARTIALLY_READABLE",
)

#: Un fichier image porte plus de pages que le lecteur n'a su en rendre
#: (story 5.31, finding `C2-1` de la couche 2 de la revue).
#:
#: **Le compteur et le lecteur ne sont pas le meme programme**, et ils
#: divergent : le cardinal se lit chez Pillow (`n_frames`, qui parcourt les
#: repertoires sans decoder), les pixels se lisent chez OpenCV
#: (`imreadmulti`). Mesure : un PNG anime est compte a deux pages par Pillow et
#: OpenCV n'en pagine qu'une. `cv2.imcount` ne rattrape rien -- il rend `2` lui
#: aussi.
#:
#: **La premiere redaction faisait SAUTER le fichier entier** dans ce cas, ce
#: qui etait une regression mesuree : le meme fichier s'ingerait a une page
#: avant la story. Faire l'inverse -- rendre les pages lues sans rien dire --
#: serait le lot plausible et incomplet que cette story existe pour fermer.
#: C'est donc une TROISIEME issue (`EPIC11-ARB-89`) : les pages lisibles sont
#: ingerees, et l'ecart est **nomme**.
IMAGE_PAGES_PARTIALLY_READABLE = "IMAGE_PAGES_PARTIALLY_READABLE"

#: Une page portait un canal alpha qui n'etait **pas** uniformement opaque, et
#: il a ete retire (story 5.30, `EPIC11-ARB-281`).
#:
#: **Retirer plutot que refuser**, parce qu'`EPIC11-ARB-89` interdit le blocage
#: sec : « Un refus qui n'offre aucune issue est aussi fautif qu'une
#: destruction silencieuse. » **Mais l'annoncer**, parce que le retrait n'est
#: alors plus neutre -- sur un alpha ASSOCIE (`ExtraSamples = 1`, ce que le
#: scanner de terrain ecrit) les valeurs sont premultipliees, donc un pixel a
#: demi transparent sort plus sombre qu'il ne devrait.
#:
#: Le cas n'a **aucun artefact de terrain** : le seul scan mesure porte un
#: alpha a `255` partout, une seule valeur distincte sur 35,8 millions de
#: pixels. Ce code existe par doctrine, pas par observation, et c'est dit
#: plutot que tu.
ALPHA_NON_OPAQUE_RETIRE = "ALPHA_CHANNEL_DROPPED"

# Filtres PDF qui signent une image compressee avec perte. Une page de scan qui
# n'est qu'un JPEG encapsule porte deja des artefacts de blocs, invisibles a
# l'oeil mais bien presents dans la mesure des patchs.
_LOSSY_PDF_FILTERS: tuple[str, ...] = ("DCTDecode", "JPXDecode")

# Ecart relatif tolere entre le DPI declare et celui que porte le fichier.
# Au-dela, le rapport le dit -- il ne remplace jamais la valeur declaree.
_DPI_RELATIVE_TOLERANCE = 0.02

# Longueur maximale d'un slug d'ingestion. 255 est la limite d'un nom de fichier
# sur ext4 et NTFS; on reste en deca pour laisser la place au chemin qui
# l'englobe.
_MAX_SLUG_LENGTH = 120


class ScanIngestError(RuntimeError):
    """Base attrapable de tous les echecs durs d'ingestion.

    Un appelant qui veut simplement refuser un lot rattrape cette classe; les
    sous-classes disent **pourquoi** (motif de `PageGeometryError`).
    """


class UnsupportedScanInputError(ScanIngestError):
    """L'entree n'est ni un dossier, ni une image lisible, ni un PDF ouvrable."""


class EmptyScanLotError(ScanIngestError):
    """Le lot ne contient aucune page exploitable.

    Un dossier vide, un dossier dont aucun fichier n'est lisible, ou un PDF sans
    page. Rendre une sequence vide en succes serait le faux succes du risque
    R12: l'operateur croirait avoir ingere un lot.
    """


class InvalidScanDpiError(ScanIngestError):
    """`--dpi` absent, non entier, ou nul/negatif.

    Le DPI n'a pas de defaut ici, contrairement au chemin POC: un DPI faux
    fausse toute la geometrie aval **sans erreur visible** (risque R8).
    """


class PdfIngestError(ScanIngestError):
    """Le document PDF est chiffre, corrompu, ou une de ses pages ne rend pas.

    Sur un PDF il n'y a **pas** de saut de page: sauter decalerait tout ce qui
    suit et produirait un lot silencieusement incomplet.
    """


@dataclass(frozen=True)
class PageLocator:
    """Ou retrouver une page, sans supposer qu'elle existe comme fichier.

    ``page_index`` vaut ``None`` pour une page-fichier et l'index de page du
    document pour une page de PDF.
    """

    source_path: str
    page_index: int | None = None

    def as_document(self) -> dict:
        return {"source_path": self.source_path, "page_index": self.page_index}


@dataclass(frozen=True)
class IngestedPage:
    """Une page du lot, mesuree sur la donnee et jamais deduite de l'extension."""

    read_rank: int
    locator: PageLocator
    scan_input_format: str
    source_bit_depth: int
    width_px: int
    height_px: int
    channels: int
    #: Taille du canevas en points PDF, `None` pour une page-fichier. Sans elle,
    #: `MIXED_PAGE_DIMENSIONS` serait illisible sur un PDF: a DPI constant, deux
    #: tailles de pixels viennent de deux tailles de canevas.
    canvas_size_pt: tuple[float, float] | None = None
    warnings: tuple[str, ...] = ()

    def as_document(self) -> dict:
        return {
            "read_rank": self.read_rank,
            "locator": self.locator.as_document(),
            "scan_input_format": self.scan_input_format,
            "source_bit_depth": self.source_bit_depth,
            "width_px": self.width_px,
            "height_px": self.height_px,
            "channels": self.channels,
            "canvas_size_pt": (
                None if self.canvas_size_pt is None else list(self.canvas_size_pt)
            ),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class ScanIngestReport:
    """Ce que l'ingestion a lu. Aucun pixel, aucun base64, aucun chemin absolu."""

    ingest_slug: str
    scans_dir: str
    declared_dpi: int
    measured_dpi: float | None
    pages: tuple[IngestedPage, ...]
    skipped_files: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def as_document(self) -> dict:
        return {
            "ingest_slug": self.ingest_slug,
            "scans_dir": self.scans_dir,
            "declared_dpi": self.declared_dpi,
            "measured_dpi": self.measured_dpi,
            "page_count": len(self.pages),
            "skipped_file_count": len(self.skipped_files),
            "skipped_files": list(self.skipped_files),
            "warnings": list(self.warnings),
            "pages": [page.as_document() for page in self.pages],
        }


def validate_warning_code(code: str) -> str:
    """Refuser tout code hors du vocabulaire ferme."""
    if code not in SCAN_INGEST_WARNING_CODES:
        raise ValueError(
            f"Code d'avertissement d'ingestion inconnu: {code!r}. Vocabulaire "
            f"ferme: {', '.join(SCAN_INGEST_WARNING_CODES)}."
        )
    return code


def validate_ingest_slug(slug: str) -> str:
    """Valider un slug d'ingestion, ou lever.

    Le slug devient un **segment de chemin** sous `scans/`. Sans cette garde,
    un `--lot-slug ../../evade` ecrivait les pages et le rapport deux niveaux
    au-dessus du projet, et la commande rendait `0` -- un succes annonce pour
    des fichiers deposes hors du projet (trouve en revue, 5.1-C1-03 / C2-1).

    La regle est donc: un seul segment, ni separateur, ni `.`, ni `..`, ni
    chemin absolu. Le vocabulaire est celui des identifiants du depot
    (`^[A-Za-z0-9_-]+$`), a une exception pres assumee -- le point est tolere,
    parce qu'un slug derive du nom d'un fichier de scan en porte souvent un.
    """
    if not isinstance(slug, str) or not slug.strip():
        raise UnsupportedScanInputError(
            f"Slug d'ingestion invalide: {slug!r}. Une chaine non vide est attendue."
        )
    if slug in (".", ".."):
        raise UnsupportedScanInputError(
            f"Slug d'ingestion invalide: {slug!r}. Il designerait le dossier "
            "`scans/` lui-meme ou son parent, pas un lot."
        )
    if "/" in slug or "\\" in slug or "\x00" in slug:
        raise UnsupportedScanInputError(
            f"Slug d'ingestion invalide: {slug!r}. Un slug est un **segment** de "
            "chemin, jamais un chemin: il ne peut contenir aucun separateur. "
            "Sans cette regle, un slug remontant sortirait du projet."
        )
    if len(slug) > _MAX_SLUG_LENGTH:
        raise UnsupportedScanInputError(
            f"Slug d'ingestion trop long ({len(slug)} caracteres, maximum "
            f"{_MAX_SLUG_LENGTH}): il ne tiendrait pas comme nom de dossier sur "
            "tous les systemes de fichiers."
        )
    # **Le fragment de version est RESERVE** (trouve en revue, couche 2).
    # `scans/scan-WIN_v2` etait simultanement l'origine de la famille
    # `scan-WIN_v2` et le rang 2 de la famille `scan-WIN` : deux familles pour
    # un seul dossier, et le prochain rang de la premiere devenait
    # `scan-WIN_v2_v2`. Un slug ne peut donc pas se terminer comme un rang.
    fragment = re.search(r"_v([0-9]+)$", slug)
    if fragment is not None and (
        VERSION_RANK_MIN <= int(fragment.group(1)) <= VERSION_RANK_MAX
        and not fragment.group(1).startswith("0")
    ):
        raise UnsupportedScanInputError(
            f"Slug d'ingestion invalide: {slug!r}. Le fragment "
            f"`_v{fragment.group(1)}` est RESERVE aux rangs de version "
            "(`EPIC11-ARB-88`): ce dossier serait a la fois un scan a part "
            "entiere et la version "
            f"{fragment.group(1)} du slug {slug[:fragment.start()]!r}. "
            "Deux issues: choisir un slug qui ne se termine pas par un rang "
            f"(par exemple {slug[:fragment.start()]}-{fragment.group(1)!s}), ou "
            f"ingerer sous {slug[:fragment.start()]!r} avec --nouvelle-version, "
            "qui posera le rang lui-meme."
        )
    return slug


def validate_scan_dpi(dpi: object) -> int:
    """Valider le DPI declare. Aucun defaut: il est **fourni** ou l'ingestion echoue."""
    if not is_strict_int(dpi) or dpi <= 0 or dpi > MAX_SCAN_DPI:
        raise InvalidScanDpiError(
            f"DPI de scan invalide: {dpi!r}. Un entier de 1 a {MAX_SCAN_DPI} est "
            "attendu, et il est obligatoire: contrairement au chemin POC, "
            "l'ingestion ne suppose pas 300. Un DPI faux fausse toute la "
            "geometrie aval sans erreur visible."
        )
    return dpi


def _normalised_sort_key(name: str) -> tuple[str, str]:
    """Cle de tri stable d'une machine a l'autre.

    Deux pieges reunis: la casse (un scanner Windows ecrit `PAGE_01.TIF`, un
    autre `page_01.tif`) et la forme Unicode (`e` accentue s'ecrit NFC sur un
    systeme, NFD sur un autre -- deux chaines differentes pour le meme nom
    affiche). La normalisation NFC puis le repli de casse rendent le tri
    identique partout. Le nom brut departage les egalites, pour que la cle
    reste totale.
    """
    return (unicodedata.normalize("NFC", name).casefold(), name)


def _measure_file_dpi(path: Path) -> float | None:
    """Lire la resolution declaree par le fichier, ou `None` si absente.

    Mesure **informative**: elle est confrontee au DPI declare, jamais
    substituee. Un scanner en auto-fit ecrit une resolution qui ne correspond
    pas a l'echelle reelle de la page.
    """
    # L'import vit HORS du `try` (revue 8.4, EPIC8-ARB-1). Sous le `try`, le
    # `except Exception` l'englobait -- or `ImportError` est une sous-classe
    # d'`Exception` : Pillow absent, cette fonction rendait `None` EN SILENCE
    # et la chaine poursuivait sur « DPI non declare » au lieu d'echouer en
    # nommant le paquet manquant. Pillow etant une dependance de base, son
    # absence signale une installation cassee et doit rester une panne franche.
    # Le `try` ne couvre plus que ce qu'il devait couvrir : les erreurs de
    # LECTURE du fichier (absent, tronque, format inconnu), pour lesquelles
    # `None` est la bonne reponse -- la mesure est informative.
    from PIL import Image

    try:
        with Image.open(path) as image:
            dpi = image.info.get("dpi")
    except Exception:
        return None
    if not dpi:
        return None
    if not isinstance(dpi, (tuple, list)):
        return _resolution_lisible(dpi)
    # **LES DEUX AXES, et le plus bas des deux** (findings `C1` et `C2-4` de la
    # revue de 5.30, trouves independamment par deux couches).
    #
    # Cette ligne lisait `dpi[0]` seul. Le defaut etait invisible tant que le
    # dpi d'un TIFF n'etait jamais lu ; c'est 5.30 qui le rend atteignable, et
    # c'est donc 5.30 qui le porte. Regime mesure -- un TIFF declarant
    # `XResolution = 600` et `YResolution = 150`, ingere a 600 ppp : la mesure
    # rendait `600.0` et **aucun avertissement**, sur une page dont un axe est
    # au quart de la resolution annoncee.
    #
    # Or c'est exactement le faux succes que l'AC 7 de la 5.1 existe pour
    # attraper : elle est posee contre le **scanner en auto-fit** (risque R8),
    # et l'auto-fit est precisement ce qui produit deux resolutions differentes
    # sur les deux axes.
    #
    # **Le plus bas, et ce n'est pas une regle neuve** : c'est celle que
    # `_measure_pages_dpi` applique deja d'une page a l'autre -- « c'est elle
    # qui borne la finesse reellement disponible ». Elle est ici recopiee d'un
    # cran plus bas, d'un axe a l'autre, plutot qu'inventee.
    mesures = [lu for lu in (_resolution_lisible(axe) for axe in dpi[:2])
               if lu is not None]
    return min(mesures) if mesures else None


def _resolution_lisible(valeur: object) -> float | None:
    """La resolution declaree par un fichier, en flottant, ou `None`.

    **Ce n'est pas `is_strict_number`, et c'est le defaut que 5.30 ferme.**
    Cette fonction lisait la resolution par `is_strict_number`, qui teste
    `isinstance(valeur, (int, float))`. Pillow rend un
    `PIL.TiffImagePlugin.IFDRational` pour la resolution de **tout** TIFF --
    pas seulement ceux d'Apple : contre-mesure faite sur un TIFF ecrit par
    Pillow lui-meme. Le dpi d'un TIFF n'a donc **jamais** ete lu, et l'AC 7 de
    la 5.1 -- le dpi declare confronte au dpi du fichier, posee contre le
    scanner en auto-fit (risque R8) -- n'a jamais joue sur le format que le
    produit recommande pour scanner. Sur un PNG, ou Pillow rend un `float`,
    elle jouait.

    **La garde partagee n'est pas elargie pour autant.** `is_strict_number`
    reste intacte : d'autres appelants l'emploient sur des cadences et des
    millimetres, ou son refus des types exotiques est voulu. C'est ici, au
    point de lecture, que la valeur lue est convertie.

    **Le `nan` ET l'`inf` sont refuses explicitement, et aucun des deux n'est
    theorique.** `float(IFDRational(0, 0))` ne leve pas, il rend `nan`, et un
    TIFF peut porter `0/0` en `XResolution`. L'`inf`, lui, arrive par un autre
    chemin -- une `XResolution` de type TIFF `DOUBLE` (12) ou `FLOAT` (11)
    portant l'infini, que Pillow relit tel quel : mesure faite, `info["dpi"]`
    rend `(inf, inf)` en flottants ordinaires. La premiere redaction de cette
    docstring le passait sous silence, et une couche de revue l'a cru
    inatteignable ; une autre a mesure qu'il l'etait, ET qu'il est **porteur**
    -- sans cette clause, `report_json` leve `Out of range float values are
    not JSON compliant` et **le lot entier est perdu a l'ecriture du
    rapport**. Un `nan` rendu ici traverserait
    :func:`_dpi_warnings` sans rien declencher -- `abs(nan - declare) >
    declare * tolerance` vaut `False` -- : un dpi illisible passerait pour un
    dpi **conforme**, c'est-a-dire un faux succes de la famille exacte que
    l'AC 7 existe pour attraper.
    """
    if isinstance(valeur, bool) or not isinstance(valeur, Real):
        return None
    try:
        mesure = float(valeur)
    except (TypeError, ValueError, ZeroDivisionError, OverflowError):
        return None
    # `nan` echoue les DEUX comparaisons : `not (mesure > 0)` l'attrape, la
    # ecrire `mesure <= 0` ne l'attraperait pas.
    if not mesure > 0 or mesure == float("inf"):
        return None
    return mesure


def _measure_pages_dpi(paths: list[Path]) -> float | None:
    """DPI mesure du lot, ou `None` si aucune page ne le declare.

    Mesure sur **toutes** les pages et non sur la seule premiere du tri
    (5.1-C2-6): la premiere peut etre celle qui sera ensuite sautee comme
    illisible, et un lot dont les pages declarent deux resolutions differentes
    doit le montrer plutot que de rendre celle qui arrive en tete.
    """
    measured = [value for value in (_measure_page_file_dpi(path) for path in paths)
                if value]
    if not measured:
        return None
    # La plus basse: c'est elle qui borne la finesse reellement disponible.
    return min(measured)


def _measure_page_file_dpi(path: Path) -> float | None:
    """Le dpi d'UN fichier porteur de pages, quelle que soit sa nature.

    Le point de dispatch du dpi, jumeau de celui de `_ingest_files`
    (`EPIC11-ARB-157`). Sans lui, :func:`_measure_pages_dpi` passait un PDF a
    :func:`_measure_file_dpi`, qui ne sait lire que des images : le PDF rendait
    `None` et **disparaissait du `min`**. Un dossier melangeant un PDF a 200 dpi
    et des TIFF a 600 aurait donc annonce 600 -- le faux succes que l'AC 7 nomme
    exactement, reintroduit par la porte du melange.
    """
    if path.suffix.lower() in PDF_EXTENSIONS:
        # **Aucun `try` ici, et son absence est mesuree.** La premiere
        # redaction en portait un, sur `(UnsupportedScanInputError, ValueError)`,
        # avec un commentaire qui le presentait comme une politique active.
        # `_measure_pdf_dpi` rattrape deja `ScanIngestError` ET enveloppe sa
        # boucle d'un `except Exception` : elle rend `None`, elle ne leve
        # jamais. La garde etait donc du code qu'aucune fabrique ne peut
        # atteindre, double d'un commentaire qui affirmait le contraire -- et
        # le lot D de cette meme story a retire une garde inatteignable plutot
        # que de la doubler d'un test impossible. Verifie en execution :
        # `_measure_page_file_dpi(<pdf casse>)` rend `None`.
        return _measure_pdf_dpi(path)
    if _pages_d_un_fichier_image(path) > 1:
        # **La plus basse de ses pages**, comme `_measure_pages_dpi` le fait
        # deja d'un dossier : c'est elle qui borne la finesse reellement
        # disponible. Sans cette branche, un multipage passait a
        # `_measure_file_dpi`, qui ne lit que sa PREMIERE page -- le meme faux
        # succes que l'AC 7 nomme, par la porte du multipage.
        return _measure_image_multipage_dpi(path)
    return _measure_file_dpi(path)


def _measure_image_multipage_dpi(path: Path) -> float | None:
    """Le dpi d'un fichier image a N pages : le PLUS BAS de ses pages.

    Mesure **informative**, comme :func:`_measure_file_dpi` : son echec rend
    `None` et ne fait pas echouer une ingestion valide.
    """
    from PIL import Image

    mesures: list[float] = []
    try:
        with Image.open(path) as image:
            for index in range(int(getattr(image, "n_frames", 1))):
                image.seek(index)
                dpi = image.info.get("dpi")
                if not dpi:
                    continue
                # **LES DEUX AXES ici aussi** (finding `C1-2` de la couche 1) :
                # c'est le jumeau du defaut de `_measure_file_dpi`, dans une
                # fonction NEUVE -- donc le correctif de l'autre ne l'atteignait
                # pas. Mesure : un TIFF `XResolution=600 / YResolution=75`
                # rendait 600.0.
                axes = dpi[:2] if isinstance(dpi, (tuple, list)) else (dpi,)
                mesures.extend(lu for lu in
                               (_resolution_lisible(axe) for axe in axes)
                               if lu is not None)
    except Exception:
        return None
    return min(mesures) if mesures else None


def _pages_d_un_fichier_image(path: Path) -> int:
    """Combien de pages un fichier IMAGE porte -- **sans decoder un seul pixel**.

    Story 5.31 (`EPIC11-ARB-282`), retour de terrain : `Apple Image Capture`
    ecrit volontiers un TIFF multipage, et `cv2.imread` en rend la PREMIERE
    page en se taisant sur les autres. Mesure sur le fichier reel a deux
    pages : `page_count: 1`, `EXIT=0`, lot incomplet, aucun rouge.

    **Les repertoires, pas les bandes.** `n_frames` lit la chaine d'IFD du
    fichier ; decoder pour compter ferait payer un decodage complet a chaque
    affichage de l'ecran de depot, sur un dossier qu'on ne fait que regarder.

    **Un fichier qu'on ne sait pas ouvrir compte pour UNE page**, jamais zero
    -- meme regle que le PDF juste en dessous, et pour le meme motif : il sera
    saute a l'ingestion et nomme au rapport, et l'annoncer a zero le ferait
    disparaitre du cardinal sans un mot.

    L'import de Pillow vit **hors** du `try`, comme dans
    :func:`_measure_file_dpi` et pour la meme raison mesuree en revue 8.4 :
    sous le `try`, `except Exception` engloberait `ImportError` et une
    installation cassee rendrait `1` en silence.
    """
    return len(_indices_de_pages_d_un_fichier_image(path)) or 1


#: Bit 0 de `NewSubfileType` (tag 254) : « image de resolution REDUITE ». Le
#: tag `SubfileType` (255), plus ancien, code la meme chose par la valeur 2.
_TIFF_NEW_SUBFILE_TYPE = 254
_TIFF_SUBFILE_TYPE = 255
_TIFF_REDUCED_RESOLUTION_BIT = 1
_TIFF_SUBFILE_TYPE_REDUCED = 2


def _indices_de_pages_d_un_fichier_image(path: Path) -> tuple[int, ...]:
    """Les INDEX des repertoires qui sont de vraies pages, dans l'ordre.

    **Une liste d'index et non un cardinal**, et c'est ce qui fait la
    difference : le compteur et le lecteur ne sont pas le meme programme --
    Pillow compte les repertoires, OpenCV decode les pixels --, donc il leur
    faut une **seule** table de correspondance plutot que deux arithmetiques
    qui coincident tant qu'aucun repertoire n'est saute.

    **Une VIGNETTE n'est pas une page** (finding `C2-2` de la couche 2). Un
    scanner peut ecrire un apercu de resolution reduite comme second
    repertoire ; le compter ferait un lot **sur**-complet, plausible, et
    d'accord avec son propre cardinal -- l'inverse exact du defaut que la story
    ferme, donc invisible au controle d'egalite. Les repertoires marques
    `NewSubfileType` bit 0, ou `SubfileType == 2`, sont ecartes.

    **Ce que cette exclusion ne mesure PAS, dit plutot que tu** : aucun des deux
    fichiers de terrain du 2026-09-09 ne porte de vignette (deux repertoires,
    deux pages pleines). La garde est posee sur une fabrique de synthese, et le
    depot sait ce que ca vaut -- « une fixture de synthese peut fabriquer une
    panne que le terrain n'a PAS ».

    L'import de Pillow vit **hors** du `try` (revue 8.4) : sous le `try`,
    `except Exception` engloberait `ImportError` et une installation cassee
    rendrait une page en silence.
    """
    from PIL import Image

    try:
        with Image.open(path) as image:
            cardinal = int(getattr(image, "n_frames", 1))
            if cardinal <= 1:
                return (0,)
            indices = []
            for index in range(cardinal):
                image.seek(index)
                tags = getattr(image, "tag_v2", {})
                nouveau = tags.get(_TIFF_NEW_SUBFILE_TYPE)
                ancien = tags.get(_TIFF_SUBFILE_TYPE)
                reduite = (
                    (nouveau is not None
                     and int(nouveau) & _TIFF_REDUCED_RESOLUTION_BIT)
                    or (ancien is not None
                        and int(ancien) == _TIFF_SUBFILE_TYPE_REDUCED)
                )
                if not reduite:
                    indices.append(index)
    except Exception:
        # **On demande au LECTEUR ce que le compteur n'a pas su dire**
        # (finding `C1-1` de la couche 1). La premiere redaction rendait `1`
        # ici, avec pour justification que « le fichier sera saute a
        # l'ingestion et nomme au rapport ». C'etait faux des que Pillow
        # echoue la ou OpenCV reussit -- et leurs plafonds different d'un
        # facteur douze : mesure sur un TIFF de deux pages a 180 Mpx la page,
        # Pillow leve `DecompressionBombError` (seuil 178 956 970 pixels) et
        # OpenCV lit les deux. Le fichier n'etait alors ni saute ni nomme : il
        # rendait UNE page, zero avertissement, et la seconde disparaissait --
        # exactement le defaut que cette story ferme, reintroduit par la porte
        # du `except`.
        #
        # `cv2.imcount` ne decode pas les pixels non plus. Il ne sait pas
        # distinguer une vignette d'une page ; c'est le prix du repli, et il
        # vaut mieux qu'une page perdue en silence.
        try:
            compte = int(cv2.imcount(str(path)))
        except Exception:
            return (0,)
        return tuple(range(compte)) if compte > 0 else (0,)
    return tuple(indices) or (0,)


def _cardinal_des_pages(paths: list[Path]) -> int:
    """Combien de PAGES une liste de fichiers porte -- pas combien de fichiers.

    `EPIC11-ARB-157`. Trois fichiers dont un PDF de trois pages font **cinq**
    pages, et c'est ce cardinal-la que l'ecran de depot annonce. Compter les
    fichiers rendrait `3` : un compte faux presente comme une mesure, ce que le
    depot interdit deja partout ailleurs.

    Un PDF qu'on ne sait pas ouvrir compte pour **une** page plutot que zero. Il
    sera saute a l'ingestion et nomme au rapport ; l'annoncer a zero le ferait
    disparaitre du cardinal sans un mot -- exactement ce que
    :func:`_materialise_selection` refuse de faire des fichiers absents.
    """
    total = 0
    for path in paths:
        if path.suffix.lower() not in PDF_EXTENSIONS:
            # Une image porte N pages elle aussi (`EPIC11-ARB-282`). Ce n'est
            # pas une troisieme nature : c'est la SECONDE -- un fichier, N
            # pages -- appliquee a une image.
            total += _pages_d_un_fichier_image(path)
            continue
        try:
            document = _open_pdf(path)
        except (PdfIngestError, EmptyScanLotError, UnsupportedScanInputError,
                ValueError):
            # **Le MEME tuple que `_ingest_files`, et son absence ici etait le
            # defaut le plus grave de la vague** -- trouve independamment par
            # les trois couches de la revue.
            #
            # `_open_pdf` ne leve que `PdfIngestError` (chiffre, corrompu) ou
            # `EmptyScanLotError` (zero page), et AUCUNE des deux n'est
            # sous-classe d'`UnsupportedScanInputError` : les trois descendent
            # directement de `ScanIngestError`. La branche de secours
            # ci-dessous n'etait donc atteinte par rien, et `mesurer_la_source`
            # LEVAIT sur un dossier que `ingest_scan_lot` ingerait.
            #
            # Consequence a l'ecran, mesuree : `designer` rend ce refus
            # verbatim et ne pose pas la source -- un dossier de dix planches
            # dont UNE est un PDF illisible devenait indesignable, alors que le
            # coeur en ingere neuf. C'est mot pour mot le blocage d'Egan,
            # reintroduit par son propre correctif : « un format que le coeur
            # ingere et que l'ecran refuse ».
            #
            # Le correctif avait ete pose sur `_ingest_files` et pas sur son
            # jumeau. Les deux gardes se lisent desormais ensemble.
            total += 1
            continue
        try:
            total += len(document)
        finally:
            document.close()
    return total


def _measure_pdf_dpi(pdf_path: Path) -> float | None:
    """DPI des images embarquees d'un PDF, ou `None` s'il n'en porte aucune.

    Sans cette mesure, le faux succes que l'AC 7 decrit nommement etait
    indetectable (5.1-C3-3 / C2-7): un `--dpi 600` sur une page dont l'image
    embarquee n'est qu'a 200 dpi produit une page de 600 dpi **nominaux** et de
    200 dpi reels -- dimensions correctes, detail inexistant. C'est exactement
    le risque R8, et il est d'autant plus vicieux sur un PDF que `--dpi` y
    pilote le rendu.
    """
    try:
        document = _open_pdf(pdf_path)
    except ScanIngestError:
        return None
    measured: list[float] = []
    try:
        for page_index in range(len(document)):
            for obj in document[page_index].get_objects():
                metadata = getattr(obj, "get_metadata", None)
                if metadata is None:
                    continue
                horizontal = getattr(metadata(), "horizontal_dpi", None)
                if is_strict_number(horizontal) and horizontal > 0:
                    measured.append(float(horizontal))
    except Exception:
        # Mesure informative: son echec ne fait pas echouer une ingestion valide.
        return None
    finally:
        document.close()
    return min(measured) if measured else None


def _bit_depth_of(array: np.ndarray) -> int:
    """Profondeur **constatee** du tableau lu."""
    if array.dtype == np.uint8:
        return 8
    if array.dtype.kind == "u" and array.dtype.itemsize == 2:
        return 16
    raise UnsupportedScanInputError(
        f"Profondeur de pixel non geree a l'ingestion: {array.dtype}. Attendu "
        "8 ou 16 bits non signes par canal. Un scan flottant (TIFF 32 bits, "
        ".hdr, .pfm) doit etre converti en amont: le convertir ici reviendrait "
        "a choisir a la place de l'operateur quelle plage devient 0-65535."
    )


def _channels_of(array: np.ndarray) -> int:
    return 1 if array.ndim == 2 else array.shape[2]


class PageImageLue(NamedTuple):
    """Ce qu'une lecture de page-fichier rend, **constat compris**.

    Le tableau est celui que la chaine emploie -- trois canaux BGR apres
    retrait d'un eventuel alpha --, tandis que `canaux_du_fichier` dit ce que
    **le fichier** portait. Les deux se separent sur un scan RGBA, et cette
    separation est le contrat : le rapport d'ingestion est un CONSTAT de ce qui
    a ete lu, pas un compte rendu de ce que la chaine a garde. Les confondre
    ferait declarer `channels: 3` d'un fichier qui en porte quatre, c'est-a-dire
    effacer du rapport la seule trace de ce que le scanner a ecrit.
    """

    tableau: np.ndarray
    canaux_du_fichier: int
    avertissements: tuple[str, ...]


def _sans_canal_alpha(array: np.ndarray) -> tuple[np.ndarray, tuple[str, ...]]:
    """Retirer le quatrieme canal d'une page, et dire s'il portait quelque chose.

    **Le declencheur est un retour de terrain, pas une hypothese** (story 5.30,
    `EPIC11-ARB-281`) : `Apple Image Capture` -- l'utilitaire de scan livre avec
    macOS -- ecrit `SamplesPerPixel = 4` et `ExtraSamples = (1,)` la ou le
    pilote de l'imprimante ecrit trois canaux. Un seul nombre separe les deux
    fichiers, et il faisait refuser toute la calibration
    (`color_calibration.FAILURE_NOT_THREE_CHANNELS`) sur un scan dont le QR
    livrait pourtant son payload et dont la geometrie ArUco se resolvait.

    **Retirer un alpha OPAQUE ne perd rien**, et c'est ce qui rend le geste
    sur : mesure sur le fichier de terrain, une seule valeur distincte (255)
    sur 35,8 millions de pixels. C'est aussi ce qui le distingue du cas gris,
    que l'ingestion continue de laisser passer tel quel : convertir du gris en
    BGR **fabriquerait** une couleur que le scan ne porte pas, alors que
    retirer un alpha opaque n'enleve aucune information.

    **Le retrait vit ICI et nulle part ailleurs.** Meme discipline que
    `io/version_ranks.py` : un appelant qui recopierait le calcul serait la
    seconde redaction que ce depot paie a chaque fois -- le finding `m4` de la
    revue de 5.19 l'a deja paye sur la profondeur de bits.

    La copie est **voulue** : `array[:, :, :3]` est une vue non contigue, et le
    reste de la chaine (cv2, l'export TIFF 16 bits) suppose la contiguite.
    """
    if array.ndim != 3 or array.shape[2] != 4:
        return array, ()
    alpha = array[:, :, 3]
    opaque = bool((alpha == np.iinfo(alpha.dtype).max).all())
    avertissements = () if opaque else (ALPHA_NON_OPAQUE_RETIRE,)
    return np.ascontiguousarray(array[:, :, :3]), avertissements


def lire_une_page_image(path: Path, page_index: int | None = None) -> PageImageLue:
    """Lire une page-fichier : le tableau employable, et ce que le fichier portait.

    `IMREAD_UNCHANGED`, jamais `cv2.imread` nu. L'entree est validee par
    `color_pipeline.validate_bgr_input`, importee et jamais reecrite: elle
    traite deja l'`uint16` big-endian qu'un scanner ecrit en byte order `MM`,
    et elle **accepte** deliberement un a quatre canaux -- elle valide, elle ne
    normalise pas. La normalisation est ici, une fois.

    ``page_index`` designe une page d'un fichier MULTIPAGE (story 5.31). Deux
    pieges tenus ici, tous deux mesures :

    (1) **la surcharge BORNEE d'`imreadmulti`**, `(fichier, start, count)`, et
    jamais celle qui lit tout : a 600 ppp en RGBA une page pese 143 Mo, donc un
    fichier de dix pages ferait 1,4 Go en memoire pour en rendre une ;

    (2) **le `flags` se passe EXPLICITEMENT.** Son defaut n'est pas
    `IMREAD_UNCHANGED` -- c'est `IMREAD_ANYCOLOR` sur cette surcharge --, et
    sans lui un TIFF 16 bits redescendrait a 8 bits sans un mot, ce que la
    docstring de ce module interdit depuis 5.1.

    Et le verdict se lit sur la LISTE rendue, jamais sur le booleen : un index
    hors bornes rend une liste vide.
    """
    if page_index is None:
        array = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    else:
        _, pages = cv2.imreadmulti(str(path), page_index, 1,
                                   flags=cv2.IMREAD_UNCHANGED)
        array = pages[0] if len(pages) else None
    if array is None:
        raise UnsupportedScanInputError(
            f"Image de scan illisible: {path}"
            + ("" if page_index is None else f" (page {page_index})"))
    array = color_pipeline.validate_bgr_input(array)
    canaux_du_fichier = _channels_of(array)
    tableau, avertissements = _sans_canal_alpha(array)
    return PageImageLue(tableau, canaux_du_fichier, avertissements)


def read_image_page(path: Path) -> np.ndarray:
    """Les pixels d'une page-fichier, en BGR et a la profondeur du scan.

    Enveloppe de :func:`lire_une_page_image` pour les appelants qui n'ont que
    faire du constat -- `load_page_array` en tete, c'est-a-dire le contrat de
    jonction publie a l'usage des stories aval. Sa signature ne change pas.
    """
    return lire_une_page_image(path).tableau


def _render_pdf_page(document, page_index: int, dpi: int) -> np.ndarray:
    """Rasteriser une page de PDF au DPI **declare**, en BGR 8 bits.

    Deux pieges tenus ici.

    (1) PDFium rend deja du BGR: ajouter un `cvtColor(..., COLOR_RGB2BGR)` par
    reflexe inverserait rouge et bleu, ce que `validate_bgr_input` ne peut pas
    detecter.

    (2) `to_numpy()` rend une **vue** du tampon du bitmap (`OWNDATA` faux), pas
    une copie. Motif corrige apres verification (revue de 5.1): contrairement a
    ce qui etait ecrit ici, la vue ne pointe **pas** sur de la memoire liberee
    des la collecte du bitmap -- pypdfium2 5.12.1 attache son finalizer au
    buffer, que la vue retient par `.base`, et quatre tentatives de corruption
    (deux `bitmap_maker`, `gc.collect()`, 320 Mo de ballast) laissent le tampon
    intact. La copie est neanmoins **conservee**, pour trois raisons qui ne
    dependent pas de la version: elle detache le tableau d'un detail
    d'implementation d'une dependance tierce, elle rend le tableau contigu et
    proprietaire de ses donnees comme le reste du depot le suppose, et une vue
    conservee retiendrait tout le tampon de page en memoire pour un lot entier.
    """
    try:
        page = document[page_index]
        bitmap = page.render(scale=dpi / PDF_POINTS_PER_INCH)
        array = np.array(bitmap.to_numpy(), copy=True)
    except Exception as error:  # pypdfium2 leve ses propres types
        raise PdfIngestError(
            f"Echec du rendu de la page {page_index} du PDF: {error}. Sur un PDF "
            "il n'y a pas de saut de page: sauter decalerait tout ce qui suit et "
            "produirait un lot silencieusement incomplet."
        ) from error
    return color_pipeline.validate_bgr_input(array)


def _pdf_page_has_lossy_image(page) -> bool:
    """Vrai si la page embarque une image compressee avec perte.

    Beaucoup de pilotes de scanner ecrivent un PDF dont chaque page n'est qu'un
    JPEG encapsule: le rendu sera propre en apparence et portera pourtant des
    artefacts de blocs, que la mesure des patchs prendra pour du signal.
    """
    try:
        for obj in page.get_objects():
            filters = getattr(obj, "get_filters", None)
            if filters is None:
                continue
            if any(name in _LOSSY_PDF_FILTERS for name in filters()):
                return True
    except Exception:
        # L'inspection est informative: son echec ne doit pas faire echouer une
        # ingestion par ailleurs valide.
        return False
    return False


def _open_pdf(path: Path):
    import pypdfium2 as pdfium

    try:
        document = pdfium.PdfDocument(path)
    except Exception as error:
        raise PdfIngestError(
            f"Document PDF inexploitable: {path} ({error}). Un PDF chiffre, "
            "corrompu ou protege par mot de passe est un echec dur, jamais une "
            "sequence vide rendue en succes."
        ) from error
    if len(document) == 0:
        document.close()
        raise EmptyScanLotError(f"Le document PDF ne contient aucune page: {path}")
    return document


def _discover_folder_pages(folder: Path) -> tuple[list[Path], list[str]]:
    """Lister les pages-fichiers d'un dossier, dans l'ordre deterministe de l'AC 3."""
    # `is_file()` est faux sur un lien symbolique casse: sans le second test,
    # un `page_01.tif` pointant dans le vide n'etait ni page, ni saut, ni compte,
    # ni avertissement -- le faux succes R12 exact (5.1-C2-5). Il est desormais
    # retenu comme candidat, et le saut nomme intervient a la lecture.
    candidates = [
        entry
        for entry in folder.iterdir()
        if entry.suffix.lower() in PAGE_EXTENSIONS
        and (entry.is_file() or entry.is_symlink())
    ]
    candidates.sort(key=lambda entry: _normalised_sort_key(entry.name))
    ignored = sorted(
        entry.name
        for entry in folder.iterdir()
        if entry.is_file() and entry.suffix.lower() not in PAGE_EXTENSIONS
    )
    return candidates, ignored


def _normaliser_la_selection(scan_path) -> list[Path] | None:
    """Rendre la selection ordonnee et validee, ou ``None`` si c'en est pas une.

    Une chaine et un `Path` sont des chemins, pas des sequences : ils sont
    ecartes explicitement, sinon `str` -- qui est iterable -- serait pris pour
    une selection de caracteres.

    Tout ce qui n'est pas un **fichier porteur de pages** est refuse ici, avec
    son chemin : un dossier n'a pas de sens dans une selection -- il est deja
    une forme d'entree a lui seul --, et un chemin absent doit se dire avant
    toute copie plutot qu'apparaitre comme une page manquante.

    **Le PDF, lui, y a desormais sa place** (`EPIC11-ARB-157`). Ce paragraphe
    disait le contraire -- « le second porte ses pages en interne et ne se
    melange pas a des images » --, et il l'a dit trois lignes au-dessus du code
    qui venait de lever ce refus. C'est la classe de defaut que `CLAUDE.md`
    documente sur ses propres regles : une prose qui survit au code qu'elle
    decrit.
    """
    if isinstance(scan_path, (str, Path)) or not isinstance(scan_path, Sequence):
        return None

    chemins = [Path(entree) for entree in scan_path]
    if not chemins:
        raise EmptyScanLotError(
            "Selection de scan vide: aucun fichier a ingerer."
        )

    absents = [chemin for chemin in chemins if not chemin.exists()]
    if absents:
        raise UnsupportedScanInputError(
            "Chemin de scan introuvable: "
            + ", ".join(str(chemin) for chemin in absents)
        )
    non_pages = [
        chemin for chemin in chemins
        if chemin.is_dir() or chemin.suffix.lower() not in PAGE_EXTENSIONS
    ]
    if non_pages:
        raise UnsupportedScanInputError(
            "Une selection de scan ne porte que des pages ("
            f"{', '.join(PAGE_EXTENSIONS)}). Refuses: "
            + ", ".join(str(chemin) for chemin in non_pages)
            + ". Un dossier s'ingere en designant le dossier."
        )

    ordonnes = _ordonner_une_selection(chemins)
    _refuser_les_noms_en_double(ordonnes)
    return ordonnes


def _slug_par_defaut_d_une_selection(selection: list[Path], scans_root: Path) -> str:
    """Le nom du dossier parent commun, ou le nom du premier fichier.

    Selectionner les 25 TIFF d'un dossier doit donner le meme lot que designer
    ce dossier : le slug est donc celui du **dossier**, pas celui d'un des
    fichiers. Sans parent commun -- une selection prise dans deux dossiers --
    on retient le parent du premier fichier **dans l'ordre de lecture**, qui
    est deja deterministe, et jamais l'ordre d'arrivee des chemins.

    Les deux cas donnent **la meme expression**, et c'est pourquoi il n'y en a
    qu'une ici : quand tous les parents sont egaux, le parent commun EST celui
    du premier fichier. Un conditionnel sur le cardinal d'un ensemble de
    parents a ete ecrit puis retire -- ses deux cotes rendaient la meme valeur,
    aucune mesure ne les distinguait, et son cote « ensemble » introduisait une
    dependance a un ordre d'iteration qui n'en est pas un (revue du
    2026-08-27). Le seul ordre qui decide ici est celui de la LECTURE, pose par
    :func:`_ordonner_une_selection` avant que cette fonction ne soit appelee.

    Un cas echappe a cette regle : quand le parent commun est la **racine
    `scans/` du projet**. Son nom donnerait le slug `scans`, donc un lot
    `scans/scans/` -- un dossier au nom de son propre parent, qui ne dit rien
    de ce qu'il contient. On retient alors le nom du premier fichier, qui est
    exactement ce qu'une image seule aurait donne.
    """
    parent = selection[0].parent.resolve()
    try:
        est_la_racine = parent == scans_root.resolve()
    except OSError:
        est_la_racine = False
    return selection[0].stem if est_la_racine else parent.name


def _ordonner_une_selection(sources) -> list[Path]:
    """Ordonner une SELECTION de fichiers par la meme regle qu'un dossier.

    L'ordre est un **rang de lecture** et il doit etre deterministe : le tri
    est celui de :func:`_discover_folder_pages` (nom normalise, casse repliee,
    NFC), et non l'ordre dans lequel un explorateur de fichiers ou un
    glisser-deposer a rendu les chemins -- celui-la depend du systeme et
    donnerait deux `read_rank` differents pour la meme selection.
    """
    return sorted(sources, key=lambda entry: _normalised_sort_key(entry.name))


def _cle_de_nom(nom: str) -> str:
    """La cle sous laquelle deux noms de fichier **entrent en collision**.

    Le point unique de cette question, et il n'est pas anodin : deux noms qui
    ne different que par la CASSE designent le meme fichier sur NTFS et sur
    APFS -- c'est-a-dire sur les deux systemes ou ce projet tourne --, et deux
    fichiers differents sur ext4. Comparer les noms tels quels revient donc a
    supposer un systeme de fichiers sensible a la casse ; les gardes bâties
    sur cette supposition ne mordaient pas la ou elles servent.

    On tranche du cote de la SURETE, et de la meme facon partout : deux noms
    homonymes a la casse pres sont traites comme le meme nom, sur tous les
    systemes. Le prix est un refus de trop sur un systeme sensible a la casse,
    ou l'operatrice renomme un fichier ; le prix inverse est une page perdue
    en silence, ce que le depot refuse par principe (R12).
    """
    return nom.casefold()


def _refuser_les_noms_en_double(sources: list[Path]) -> None:
    """Refuser une selection ou deux fichiers portent le meme nom.

    Deux pages selectionnees dans deux dossiers differents mais homonymes
    atterriraient sous le meme nom dans le lot : la seconde copie ecraserait
    la premiere et le lot perdrait une page **en silence**, avec un cardinal
    juste au rapport. C'est le faux succes R12, et il se refuse plutot qu'il
    ne s'arbitre.

    **Homonymes a la casse pres compris** (revue du 2026-08-27) : la
    comparaison portait sur les noms tels quels, et laissait donc passer
    `gauche/Planche.tiff` avec `droite/planche.tiff`. Mesure du defaut sur
    NTFS : aucun refus, **un seul** fichier sur le disque, portant le contenu
    de la SECONDE, un rapport annoncant deux pages dont l'une designe un
    fichier qui n'existe pas, `skipped_files` vide et aucun avertissement.
    C'est mot pour mot le faux succes que cette fonction existe pour refuser.
    """
    noms = [entry.name for entry in sources]
    cles = [_cle_de_nom(nom) for nom in noms]
    # Le message nomme les fichiers TELS QUE l'operatrice les voit, pas leur
    # cle : lui montrer `planche.tiff` quand son dossier porte `Planche.tiff`
    # lui ferait chercher un fichier qui n'existe pas.
    doubles = sorted(
        {nom for nom, cle in zip(noms, cles) if cles.count(cle) > 1})
    if doubles:
        raise UnsupportedScanInputError(
            "Deux fichiers de la selection portent le meme nom: "
            f"{', '.join(doubles)}. Ils s'ecraseraient l'un l'autre dans le "
            "lot. Renommer l'un des deux, ou ingerer les dossiers separement."
        )


def _dpi_warnings(declared_dpi: int, measured_dpi: float | None) -> list[str]:
    warnings: list[str] = []
    if declared_dpi < qr_codes.QR_MIN_SCAN_DPI:
        # Non bloquant: la decision de refus appartient au decodage QR de 5.2.
        warnings.append("DPI_BELOW_QR_MINIMUM")
    if measured_dpi is None:
        warnings.append("DPI_NOT_MEASURABLE")
    elif abs(measured_dpi - declared_dpi) > declared_dpi * _DPI_RELATIVE_TOLERANCE:
        warnings.append("DPI_DECLARED_DIFFERS_FROM_FILE")
    return warnings


def _homogeneity_warnings(pages: list[IngestedPage]) -> list[str]:
    warnings: list[str] = []
    if len({(page.width_px, page.height_px) for page in pages}) > 1:
        warnings.append("MIXED_PAGE_DIMENSIONS")
    if len({page.source_bit_depth for page in pages}) > 1:
        warnings.append("MIXED_BIT_DEPTHS")
    return warnings


def _ingest_pdf(
    pdf_path: Path, *, relative_source: str, dpi: int, rang_initial: int = 0,
    emetteur: progression.EmetteurProgression | None = None,
    deja_faites: int = 0,
) -> tuple[list[IngestedPage], list[str]]:
    """Les pages d'un PDF, numerotees a partir de ``rang_initial``.

    ``emetteur`` et ``deja_faites`` portent le canal de progression, en
    **ajout pur** : sans eux, la fonction fait exactement ce qu'elle faisait.
    ``deja_faites`` est ce que les fichiers PRECEDENTS du lot ont deja fait
    avancer -- un PDF au milieu d'un dossier reprend le compte la ou il en
    etait plutot que de le faire reculer a zero, ce que
    :class:`~mixed_media_utility.progression.EmetteurProgression` refuserait
    de toute facon en silence (jalon non progressif).

    **Le jalon tombe APRES la rasterisation de la page**, jamais avant : c'est
    la rasterisation qui coute, et annoncer une page faite avant de l'avoir
    faite est le meme mensonge qu'une barre completee artificiellement.

    **`read_rank` est un rang de lecture GLOBAL au lot, pas un index de page
    dans son document** (`EPIC11-ARB-157`). Il valait `page_index` tant qu'un
    PDF etait forcement la seule source du lot ; depuis qu'un PDF peut se
    trouver au milieu d'un dossier ou d'une selection, deux sources
    redemarreraient la numerotation a zero et deux pages du meme lot porteraient
    le rang `0`. L'index de page, lui, n'est pas perdu : il reste dans le
    `PageLocator`, qui est le seul endroit ou il veut dire quelque chose.
    """
    document = _open_pdf(pdf_path)
    pages: list[IngestedPage] = []
    try:
        for page_index in range(len(document)):
            array = _render_pdf_page(document, page_index, dpi)
            page_warnings = ["PDF_RASTERIZED_AT_8_BITS"]
            if _pdf_page_has_lossy_image(document[page_index]):
                page_warnings.append("PDF_EMBEDS_LOSSY_IMAGE")
            size = document[page_index].get_size()
            pages.append(
                IngestedPage(
                    read_rank=rang_initial + page_index,
                    locator=PageLocator(relative_source, page_index),
                    scan_input_format="pdf",
                    source_bit_depth=_bit_depth_of(array),
                    width_px=int(array.shape[1]),
                    height_px=int(array.shape[0]),
                    channels=_channels_of(array),
                    canvas_size_pt=(float(size[0]), float(size[1])),
                    warnings=tuple(validate_warning_code(c) for c in page_warnings),
                )
            )
            if emetteur is not None:
                emetteur.emettre(deja_faites + page_index + 1)
    finally:
        document.close()
    return pages, []


def _ingest_image_multipage(
    image_path: Path, *, relative_source: str, rang_initial: int = 0,
    emetteur: progression.EmetteurProgression | None = None,
    deja_faites: int = 0,
) -> tuple[list[IngestedPage], list[str]]:
    """Les pages d'un fichier image multipage, jumelle de :func:`_ingest_pdf`.

    Meme signature, meme politique, meme emission de jalons -- **et c'est
    voulu** : `EPIC11-ARB-157` a pose UN dispatch entre un fichier a une page
    et un fichier a N pages. Un TIFF multipage n'est pas une troisieme nature,
    c'est la seconde appliquee a une image.

    **Une page illisible fait sauter le FICHIER ENTIER, en le nommant**, comme
    pour un PDF : rendre les pages saines d'un fichier dont une page manque
    produirait exactement le lot plausible et incomplet que cette story existe
    pour fermer -- et il serait, lui, indistinguable d'un fichier sain. Le
    `raise` remonte a :func:`_ingest_files`, qui nomme le fichier au rapport et
    laisse vivre les autres du dossier.

    `read_rank` reste un rang de lecture GLOBAL au lot ; l'index de page vit
    dans le `PageLocator`, seul endroit ou il veut dire quelque chose.
    """
    pages: list[IngestedPage] = []
    indices = _indices_de_pages_d_un_fichier_image(image_path)
    avertissements_du_lot: list[str] = []
    for rang, page_index in enumerate(indices):
        try:
            page_lue = lire_une_page_image(image_path, page_index)
        except (UnsupportedScanInputError, ValueError):
            if not pages:
                # Pas une seule page lisible : c'est un fichier illisible, et
                # l'appelant le saute en le nommant, comme un PDF corrompu.
                raise
            # **Au moins une page lue : le fichier n'est pas perdu, et l'ecart
            # est NOMME** (finding `C2-1`). Ni la regression qui faisait
            # disparaitre un fichier que la version d'avant ingerait, ni le lot
            # court et muet que la story ferme.
            avertissements_du_lot.append(IMAGE_PAGES_PARTIALLY_READABLE)
            break
        array = page_lue.tableau
        pages.append(
            IngestedPage(
                # Le RANG suit les pages produites, l'INDEX designe le
                # repertoire du fichier : les deux divergent des qu'une
                # vignette est ecartee, et les confondre ferait un trou dans la
                # numerotation du lot.
                read_rank=rang_initial + rang,
                locator=PageLocator(relative_source, page_index),
                scan_input_format=image_path.suffix.lower().lstrip("."),
                source_bit_depth=_bit_depth_of(array),
                width_px=int(array.shape[1]),
                height_px=int(array.shape[0]),
                channels=page_lue.canaux_du_fichier,
                warnings=tuple(validate_warning_code(c)
                               for c in page_lue.avertissements),
            )
        )
        if emetteur is not None:
            emetteur.emettre(deja_faites + rang + 1)
    return pages, avertissements_du_lot


def _le_saut_peut_emettre(
    emetteur: progression.EmetteurProgression | None,
    pages_produites: list,
) -> bool:
    """Un fichier SAUTE a-t-il le droit de faire avancer la barre ?

    **Une branche de saut n'OUVRE jamais la suite des jalons ; elle la
    continue si elle est deja ouverte** (AC 9.3 de la story 11.4e,
    `EPIC7-ARB-79` : « un refus d'ingestion ne produit aucune progression »,
    finding `A1` de la revue du canal de progression).

    Mesure du regime que la garde ferme, avant correctif, sur un dossier de
    deux fichiers tous deux illisibles : jalons `(1, 2)` puis `(2, 2)`, soit
    une barre a **100 %** et un lot annonce a deux pages qui ne seront jamais
    detectees, **puis** `EmptyScanLotError`. Apres : aucun jalon.

    **La variante rejetee, parce qu'elle a ete mesuree et non supposee.** Une
    premiere redaction ouvrait aussi la suite quand ``emetteur.dernier > 0``,
    au motif qu'un PDF ayant rasterise neuf pages avant d'echouer a la
    dixieme a bel et bien fait du travail, et que taire son jalon de
    rattrapage laisse un **trou** dans la suite. Le trou est reel ; il est
    aussi sans consequence, une suite de jalons n'ayant jamais eu a etre
    consecutive. Le prix, lui, ne l'etait pas : sur un dossier ne portant que
    ce PDF-la, le rattrapage completait la barre a `3/3` **juste avant** le
    refus `EmptyScanLotError` -- c'est-a-dire exactement le mensonge que le
    finding `A1` ferme, reintroduit par sa propre correction. Un trou dans une
    suite qui atteint son total vaut mieux qu'une barre completee sur un refus.

    **Ce que la garde ne ferme PAS, dit plutot que tu** : les jalons emis
    *depuis* :func:`_ingest_pdf` pour des pages reellement rasterisees
    partent, eux, avant que l'exception ne soit connue. Un dossier ne portant
    qu'un PDF partiellement rasterisable emet donc encore de la progression
    avant son refus -- mesure : `(1, 3)` puis `(2, 3)`, soit une barre a 67 %,
    puis `EmptyScanLotError`. La fermer demanderait de differer TOUS les
    jalons d'un PDF jusqu'a sa derniere page, c'est-a-dire de rendre muette la
    phase la plus longue de la calibration : la dette `CALIB-N1` exactement.
    C'est une tolerance documentee, mesuree par
    `test_un_PDF_partiellement_rasterisable_SEUL_emet_encore_avant_son_refus`.
    """
    if emetteur is None:
        return False
    return bool(pages_produites)


def _ingest_files(
    files: list[Path], *, base_dir: Path, dpi: int,
    emetteur: progression.EmetteurProgression | None = None,
) -> tuple[list[IngestedPage], list[str]]:
    """Ingerer une liste de fichiers porteurs de pages, PDF compris.

    ``emetteur`` est le canal de progression, **optionnel** (`AR3`) : sans lui
    cette fonction se comporte exactement comme avant, jusqu'a la lecture de
    disque pres.

    **Le compteur avance sur les pages TRAVERSEES, pas sur les pages
    PRODUITES**, et l'ecart n'est pas theorique : un fichier saute -- image
    illisible, PDF chiffre -- ne produit aucune page mais a bel et bien coute
    du temps. Compter les seules pages produites ferait une barre qui cale sur
    chaque saut, puis rattrape d'un bond ; pire, sur un dossier dont la
    derniere planche est illisible, elle n'atteindrait jamais son total alors
    que le travail est fini.

    **Les deux comptes se lisent sur la meme echelle, et c'est une egalite qui
    se TIENT plutot qu'elle ne se suppose** : pour tout fichier saute, le
    compteur avance exactement de ce que :func:`_cardinal_des_pages` a compte
    pour lui -- une page pour un PDF qui ne s'ouvre meme pas, ses N pages pour
    un PDF qui s'ouvre. La redaction precedente affirmait cette egalite en ne
    rattrapant qu'**une** page, ce qui etait vrai du PDF illisible et **faux du
    PDF partiellement rasterisable** : celui-la s'ouvre, donc le cardinal le
    compte pour N, mais sa page fautive fait lever :func:`_render_pdf_page`
    apres que les jalons des pages precedentes sont deja partis. Le compteur
    retombait alors a ``deja_faites + 1``, c'est-a-dire **sous** le dernier
    jalon emis : tout ce qui suivait passait sous la ligne d'eau
    d':class:`~mixed_media_utility.progression.EmetteurProgression` et etait
    absorbe en silence. Mesure sur un PDF de dix pages fautif a la dixieme
    suivi de trois TIFF : cardinal `13`, jalons `1..9`, puis plus rien -- une
    barre figee a 69 % sur un travail termine (finding `A2` de la revue du
    canal de progression).

    **Aucun jalon avant la premiere page reellement PRODUITE** (AC 9.3 de la
    story 11.4e, `EPIC7-ARB-79` : « un refus d'ingestion ne produit aucune
    progression »). Les deux branches de saut passent donc par
    :func:`_le_saut_peut_emettre`, qui leur interdit d'**ouvrir** la suite des
    jalons. Sans ce report, un dossier dont TOUS les fichiers sont illisibles
    emettait `(1, 2)` puis `(2, 2)` -- une barre menee jusqu'a **100 %**, un
    lot annonce a deux pages qui ne seront jamais detectees -- avant de lever
    `EmptyScanLotError` : l'ecran annoncait complet un travail qui n'a jamais
    commence (finding `A1`). Le report **ne revient pas** au comptage des
    pages produites que le paragraphe ci-dessus ecarte : le premier jalon emis
    porte deja les fichiers sautes en tete, il les rattrape d'un coup au lieu
    de les taire. Un dossier partiellement lisible atteint donc toujours son
    total ; un dossier entierement illisible n'emet rien du tout.

    **Le point de dispatch unique entre les deux natures de page-fichier**
    (`EPIC11-ARB-157`). Une image donne une page, un PDF en donne autant qu'il
    en porte, et les rangs de lecture se suivent d'un fichier a l'autre : c'est
    ce qui fait qu'un dossier melange rend UN lot ordonne plutot que deux
    numerotations juxtaposees.

    Un PDF illisible est **saute en le nommant**, exactement comme une image
    illisible, et non leve : dans un dossier de dix planches, un PDF chiffre ne
    doit pas emporter les neuf autres. Le PDF designe SEUL garde son refus dur
    -- la ou il est la seule source, un saut silencieux rendrait un lot vide.
    """
    pages: list[IngestedPage] = []
    skipped: list[str] = []
    #: Les avertissements qui portent sur le LOT et non sur une page -- une
    #: lecture partielle de fichier multipage, pour l'instant.
    avertissements_de_lot: list[str] = []
    # Les pages traversees depuis le debut du lot -- l'echelle du canal.
    faites = 0
    for path in files:
        if path.suffix.lower() in PDF_EXTENSIONS:
            # **La relativisation est HORS du `try`**, comme dans la branche
            # image trente lignes plus bas. Dedans, son `ValueError` tombait
            # dans le tuple de saut : un PDF parfaitement LISIBLE dont le
            # chemin ne se relativise pas -- `project_dir` relatif et scan
            # absolu, ce que la CLI produit -- etait annonce « illisible » et
            # compte dans `UNREADABLE_FILE_SKIPPED`. Un defaut de CHEMIN
            # presente comme un defaut de CONTENU, et un saut nomme FAUX.
            relative_source = path.relative_to(base_dir).as_posix()
            try:
                pages_du_pdf, _ = _ingest_pdf(
                    path,
                    relative_source=relative_source,
                    dpi=dpi,
                    rang_initial=len(pages),
                    emetteur=emetteur,
                    deja_faites=faites,
                )
            except (PdfIngestError, EmptyScanLotError,
                    UnsupportedScanInputError, ValueError):
                # **`PdfIngestError` en tete, et son absence etait un vrai
                # defaut** : c'est l'erreur que `_open_pdf` leve sur un PDF
                # chiffre, corrompu ou vide, donc la SEULE que cette branche
                # rencontre en pratique. Sans elle, la politique de saut
                # documentee juste au-dessus ne s'appliquait a rien -- un PDF
                # casse au milieu d'un dossier de dix planches emportait les
                # neuf autres. Trouve par la campagne de mutation (mutant
                # `M8`), qui a survecu faute de banc, puis par le banc ecrit
                # pour le tuer.
                skipped.append(path.name)
                # **Le rattrapage se DEMANDE au cardinal, il ne se recopie
                # pas** (finding `A2`). Un PDF qui ne s'ouvre pas vaut une
                # page ; un PDF qui s'ouvre et dont une page ne se rasterise
                # pas en vaut N, parce que c'est N que le total annonce.
                # `_cardinal_des_pages` est deja le seul endroit ou ce calcul
                # est ecrit -- meme discipline que la regle des rangs de
                # `io/version_ranks.py` --, on l'interroge sur ce fichier-la
                # plutot que d'en recopier une moitie. L'ouverture de PDF
                # qu'il coute n'est payee que sur le chemin d'erreur.
                faites += _cardinal_des_pages([path])
                if _le_saut_peut_emettre(emetteur, pages):
                    emetteur.emettre(faites)
                continue
            pages.extend(pages_du_pdf)
            faites += len(pages_du_pdf)
            continue
        # **Le second etage du dispatch d'`EPIC11-ARB-157`** : une image porte
        # N pages comme un PDF. La relativisation est HORS du `try`, pour le
        # meme motif que la branche PDF ci-dessus.
        if _pages_d_un_fichier_image(path) > 1:
            relative_source = path.relative_to(base_dir).as_posix()
            try:
                pages_du_fichier, alertes = _ingest_image_multipage(
                    path,
                    relative_source=relative_source,
                    rang_initial=len(pages),
                    emetteur=emetteur,
                    deja_faites=faites,
                )
            except (UnsupportedScanInputError, ValueError):
                skipped.append(path.name)
                # Le rattrapage se DEMANDE au cardinal, il ne se recopie pas :
                # un fichier de N pages en vaut N, parce que c'est N que le
                # total annonce.
                faites += _cardinal_des_pages([path])
                if _le_saut_peut_emettre(emetteur, pages):
                    emetteur.emettre(faites)
                continue
            pages.extend(pages_du_fichier)
            avertissements_de_lot.extend(alertes)
            faites += len(pages_du_fichier)
            continue
        try:
            page_lue = lire_une_page_image(path)
            array = page_lue.tableau
            depth = _bit_depth_of(array)
        except (UnsupportedScanInputError, ValueError):
            # Le message precis de `_bit_depth_of` (« profondeur non geree »)
            # etait avale ici et remplace par « illisible » (5.1-C2). Il est
            # desormais journalise dans le rapport par le nom du fichier saute;
            # le distinguer plus finement demanderait un second code
            # d'avertissement, hors du vocabulaire ferme de l'AC 9.
            # Un fichier illisible dans un dossier par ailleurs valide est saute
            # en le nommant; c'est un dossier **entierement** illisible qui est
            # un echec dur.
            skipped.append(path.name)
            faites += 1
            if _le_saut_peut_emettre(emetteur, pages):
                emetteur.emettre(faites)
            continue
        pages.append(
            IngestedPage(
                read_rank=len(pages),
                locator=PageLocator(path.relative_to(base_dir).as_posix()),
                scan_input_format=path.suffix.lower().lstrip("."),
                source_bit_depth=depth,
                width_px=int(array.shape[1]),
                height_px=int(array.shape[0]),
                # **Ce que le FICHIER portait**, pas ce que la chaine a garde:
                # un scan RGBA declare `4` et rend trois canaux. Le rapport est
                # un constat, et effacer le quatrieme canal d'ici retirerait la
                # seule trace de ce que le scanner a ecrit.
                channels=page_lue.canaux_du_fichier,
                # `validate_warning_code` sur CE chemin aussi (finding `T1` de
                # la couche 1, `C2-5` de la couche 2, trouve deux fois) : les
                # trois autres constructions d'`IngestedPage` validaient, celle
                # -ci non. Mesure par greffon : un code hors du vocabulaire
                # ferme atterrissait dans `ingest.json` **sans une levee**, ce
                # que le vocabulaire existe precisement pour empecher.
                warnings=tuple(validate_warning_code(c)
                               for c in page_lue.avertissements),
            )
        )
        faites += 1
        if emetteur is not None:
            emetteur.emettre(faites)
    return pages, skipped, avertissements_de_lot


def ingest_scan_lot(
    project_dir: str | Path,
    scan_path: str | Path,
    *,
    dpi: int,
    ingest_slug: str | None = None,
    nouvelle_version: bool = False,
    manifest: Mapping[str, Any] | None = None,
    rappel_progression=None,
) -> ScanIngestReport:
    """Ingerer un lot de pages scannees et rendre son rapport.

    ``ingest_slug`` est un **slug operateur**, jamais un `lot_id` metier: a
    l'ingestion, l'identite du lot n'est pas connue. Sa confrontation au QR
    appartient a la story 5.2.

    ``scan_path`` prend **quatre** formes, et les quatre produisent la meme
    sequence ordonnee de pages -- aucune story aval ne sait par laquelle le lot
    est entre :

    * un **dossier** d'images ;
    * un **PDF** multipage ;
    * une **image** seule ;
    * une **sequence de chemins de fichiers** (liste ou tuple), qui est *un*
      lot et non N lots -- donc un seul `ingest.json` (`EPIC7-ARB-88`). C'est
      la forme que produit une selection multiple dans un explorateur ou un
      glisser-deposer de plusieurs fichiers. Son slug par defaut est le nom du
      **dossier parent commun**, comme si le dossier entier avait ete designe ;
      a defaut de parent commun, celui du premier fichier dans l'ordre de
      lecture.

    **La progression** (dette `CALIB-N1`, fermee le 2026-09-07).
    ``rappel_progression`` est `None` ou un appelable `(faites, total)` ; le
    canal est celui du depot -- :class:`progression.EmetteurProgression` --,
    aucun second mecanisme n'est redige. C'est un **ajout pur** : sans rappel,
    la fonction ne compte rien, ne lit rien de plus sur le disque et rend le
    meme rapport.

    Le motif est mesure et non theorique : sur un PDF 300 dpi, l'ingestion est
    la plus longue des trois phases de
    :func:`~mixed_media_utility.scan_calibrate.calibrer_la_chaine`, et elle
    etait la seule des trois a etre muette. Sur une mire -- une page -- la
    barre restait donc immobile du debut a la fin, puis affichait `1/1`.

    **Le total est le cardinal des PAGES, pas des fichiers** : il se mesure par
    :func:`_cardinal_des_pages`, la meme fonction que l'ecran de depot
    interroge, pour qu'un PDF de trois pages au milieu d'un dossier compte pour
    trois des deux cotes. Ce cardinal coute une ouverture de PDF, donc il n'est
    mesure **que** si un rappel est fourni.
    """
    dpi = validate_scan_dpi(dpi)
    project_dir = Path(project_dir)

    # La selection est reduite AVANT toute autre lecture : un seul chemin dans
    # une liste est exactement le cas a un chemin, et le traiter comme une
    # selection ferait diverger son slug (nom du dossier parent) de celui que
    # le meme fichier obtient seul (son propre nom sans extension).
    selection = _normaliser_la_selection(scan_path)
    if selection is not None and len(selection) == 1:
        scan_path, selection = selection[0], None
    if selection is None:
        scan_path = Path(scan_path)
        if not scan_path.exists():
            raise UnsupportedScanInputError(
                f"Chemin de scan introuvable: {scan_path}")
        default_slug = scan_path.stem if scan_path.is_file() else scan_path.name
    else:
        default_slug = _slug_par_defaut_d_une_selection(
            selection, project_dir / project_layout.SCANS_DIRNAME)

    slug = validate_ingest_slug(ingest_slug or default_slug)
    # `nouvelle_version` ingere dans un dossier VOISIN au lieu de refuser ou
    # d'ecraser (`EPIC11-ARB-104`). Le rang est resolu ici, avant toute
    # ecriture, parce qu'il entre dans le nom du dossier -- l'ajouter apres
    # coup ferait diverger le dossier reel du rang declare.
    rang_de_version = None
    if nouvelle_version:
        rang = resolve_scan_version_rank(Path(project_dir), slug, manifest)
        # Sur un slug jamais ingere, le drapeau produit l'ORIGINE et non une
        # « version 2 de rien » : sans effet plutot que refuse, refuser serait
        # un blocage sec sur une intention realisable.
        rang_de_version = None if rang == version_ranks.RANG_ORIGINE else rang
    lot_dir = project_layout.scan_lot_dir(project_dir, slug, rang_de_version)

    # L'ordre des trois gestes n'est pas indifferent, et c'est le correctif du
    # bloquant 5.1-C1-01: on **decouvre a la source**, on materialise ensuite, et
    # on ingere la liste decouverte. La premiere version decouvrait dans la
    # destination apres y avoir copie, si bien qu'un residu d'un lot precedent
    # devenait une page du lot courant -- une page a la source, trois au rapport,
    # sans un avertissement.
    # **L'emetteur se construit APRES la materialisation de chaque forme**, et
    # jamais avant : le cardinal des pages ne se mesure que sur la liste des
    # fichiers reellement retenus. Le construire plus haut obligerait a deviner
    # un total, c'est-a-dire a afficher un chiffre non mesure.
    def _emetteur(fichiers: list[Path]) -> progression.EmetteurProgression | None:
        """L'emetteur du lot, ou `None` quand personne n'ecoute (`AR3`).

        Le `None` n'est pas une micro-optimisation : `_cardinal_des_pages`
        OUVRE chaque PDF pour le compter, et une ingestion sans rappel ne doit
        pas payer une lecture de plus que celle d'avant ce canal.
        """
        if rappel_progression is None:
            return None
        return progression.EmetteurProgression(
            rappel_progression, _cardinal_des_pages(fichiers))

    if selection is not None:
        lot_dir, files = _materialise_selection(selection, lot_dir)
        pages, skipped, alertes = _ingest_files(
            files, base_dir=project_dir, dpi=dpi, emetteur=_emetteur(files))
        measured = _measure_pages_dpi(files)
    elif scan_path.is_dir():
        sources, _ignored = _discover_folder_pages(scan_path)
        if not sources:
            raise EmptyScanLotError(
                f"Aucune page dans {scan_path} (extensions reconnues: "
                f"{', '.join(PAGE_EXTENSIONS)})."
            )
        lot_dir = _materialise_folder(scan_path, lot_dir, sources)
        files = [lot_dir / path.name for path in sources]
        pages, skipped, alertes = _ingest_files(
            files, base_dir=project_dir, dpi=dpi, emetteur=_emetteur(files))
        measured = _measure_pages_dpi(files)
    elif scan_path.suffix.lower() in PDF_EXTENSIONS:
        copied = _materialise_file(scan_path, lot_dir)
        lot_dir = copied.parent
        pages, skipped = _ingest_pdf(
            copied, relative_source=copied.relative_to(project_dir).as_posix(),
            dpi=dpi, emetteur=_emetteur([copied])
        )
        alertes = []
        measured = _measure_pdf_dpi(copied)
    elif scan_path.suffix.lower() in IMAGE_EXTENSIONS:
        copied = _materialise_file(scan_path, lot_dir)
        lot_dir = copied.parent
        pages, skipped, alertes = _ingest_files(
            [copied], base_dir=project_dir, dpi=dpi,
            emetteur=_emetteur([copied]))
        measured = _measure_pages_dpi([copied])
    else:
        raise UnsupportedScanInputError(
            f"Forme d'entree non supportee: {scan_path}. Attendu un dossier "
            f"d'images, une image ({', '.join(IMAGE_EXTENSIONS)}) ou un PDF."
        )

    if not pages:
        raise EmptyScanLotError(
            f"Aucune page lisible dans {scan_path}: "
            f"{len(skipped)} fichier(s) illisible(s) saute(s)."
        )

    # `dict.fromkeys` plutot qu'un `set` : l'ordre des avertissements est
    # deterministe, et le rapport entre dans un condensat.
    warnings = list(dict.fromkeys(
        _dpi_warnings(dpi, measured) + _homogeneity_warnings(pages) + alertes))
    if skipped:
        warnings.append("UNREADABLE_FILE_SKIPPED")
    return ScanIngestReport(
        ingest_slug=slug,
        # Derive du dossier **reellement utilise**, jamais reconstruit depuis le
        # slug: une ingestion en place sous `scans/<date>/<lot>/` produisait
        # sinon un `scans_dir` inexistant, et la CLI mourait sur une
        # `FileNotFoundError` nue apres une ingestion pourtant reussie
        # (5.1-C1-02 / C2-4).
        scans_dir=_relative_to_project(lot_dir, project_dir),
        declared_dpi=dpi,
        measured_dpi=measured,
        pages=tuple(pages),
        skipped_files=tuple(skipped),
        warnings=tuple(validate_warning_code(code) for code in warnings),
    )


def _relative_to_project(path: Path, project_dir: Path) -> str:
    """Chemin relatif au projet, ou echec explicite s'il en sort.

    Aucun chemin absolu n'entre dans un artefact produit (AC 5), et un chemin
    qui sort du projet n'est pas relativisable: le dire vaut mieux que d'ecrire
    une suite de `..` dans un rapport cense etre portable.
    """
    try:
        return path.resolve().relative_to(project_dir.resolve()).as_posix()
    except ValueError as error:
        raise UnsupportedScanInputError(
            f"Chemin hors du projet: {path}. Un artefact d'ingestion ne peut "
            "porter que des chemins relatifs au projet."
        ) from error


def _is_inside(path: Path, parent: Path) -> bool:
    """Vrai si `path` est sous `parent`, **apres resolution**.

    `Path.relative_to` est purement lexical: un dossier exterieur atteint par
    `scans/../..` lui paraissait deja sous `scans/` et etait donc ingere sans
    copie, contre l'AC 5 (5.1-C2-3). La resolution ferme ce chemin de traverse.
    """
    try:
        path.resolve().relative_to(parent.resolve())
    except (ValueError, OSError):
        return False
    return True


def _same_bytes(left: Path, right: Path) -> bool:
    """Vrai si les deux fichiers ont exactement le meme contenu.

    Un cote illisible (lien casse, permission) rend `False`: on ne peut pas
    affirmer l'identite, donc on ne l'affirme pas.
    """
    try:
        if not right.is_file() or left.stat().st_size != right.stat().st_size:
            return False
    except OSError:
        return False
    digest = hashlib.sha256
    try:
        return digest(left.read_bytes()).digest() == digest(right.read_bytes()).digest()
    except OSError:
        return False


#: Ligne d'eau des versions de scan, de niveau PROJET (`EPIC11-ARB-104`).
#: Indexee par SLUG et non par lot : a l'ingestion le lot n'est pas connu, il
#: est porte par le QR et decode a l'etape suivante.
SCAN_WATERMARKS_FIELD = "scan_version_watermarks"


def resolve_scan_version_rank(
    project_dir: Path, ingest_slug: str, manifest: Mapping[str, Any] | None = None
) -> int:
    """Le rang du PROCHAIN scan de ce slug : la ligne d'eau plus un.

    `EPIC11-ARB-104` (Egan, 2026-08-31) : « TOUT objet doit pouvoir etre ecrase
    ou versionne. » Le scan etait le dernier objet du circuit a ne pas l'etre,
    et le scenario qui l'a montre est celui d'Egan : on reprend une planche
    imprimee, on ajoute un point rouge dans un coin, on rescanne -- le contenu
    a change, l'identite non.

    Meme regle que les trois autres objets versionnables (`io.version_ranks`) :
    un rang se CONSOMME, il ne se rend qu'en queue et sur demande.

    Le disque est consulte en PLUS du manifeste, jamais a la place : un dossier
    de scan present que le manifeste ignore -- ingere avant cet arbitrage, ou
    depose a la main -- a bel et bien consomme son rang.
    """
    lignes = (manifest or {}).get(SCAN_WATERMARKS_FIELD)
    declaree = lignes.get(ingest_slug) if isinstance(lignes, Mapping) else None
    rangs = _rangs_de_scans_sur_le_disque(project_dir, ingest_slug)
    if not rangs and not isinstance(declaree, int):
        return version_ranks.RANG_ORIGINE
    rang = version_ranks.prochain_rang(version_ranks.ligne_d_eau(declaree, rangs))
    if rang > VERSION_RANK_MAX:
        raise UnsupportedScanInputError(version_ranks.refus_de_rangs_epuises(
            "scan", ingest_slug,
            # **Une issue doit exister** (`EPIC11-ARB-89`, trouve en revue,
            # couches 2 et 3). La redaction d'avant proposait de « supprimer le
            # DERNIER scan de ce slug en liberant son rang » : aucune commande
            # ne supprime un scan seul. Le geste reel passe par le lot, et il
            # faut le dire tel qu'il est plutot que de promettre plus fin.
            # Le geste FIN existe depuis `EPIC11-ARB-111`. La redaction
            # d'avant envoyait vers `--avec-scans`, qui emporte le lot entier
            # ET ne libere aucun rang de scan : une issue inoperante, donc un
            # blocage sec deguise.
            "Trois issues: supprimer le DERNIER scan de ce slug en liberant "
            "son rang (`mmu project remove --lot <id> --scan <slug de "
            "famille> --version <rang> --liberer-le-rang --confirmer`, qui ne "
            "retire que ce scan), "
            "ingerer sous un autre --lot-slug, ou ecraser sciemment le scan "
            "existant (--overwrite).",
        ))
    return rang


def _rangs_de_scans_sur_le_disque(project_dir: Path, ingest_slug: str) -> set[int]:
    """Les rangs dont le DOSSIER existe deja sous `scans/`."""
    racine = Path(project_dir) / project_layout.SCANS_DIRNAME
    if not racine.is_dir():
        return set()
    presents = {chemin.name for chemin in racine.iterdir() if chemin.is_dir()}
    rangs: set[int] = set()
    for rang in [version_ranks.RANG_ORIGINE, *range(VERSION_RANK_MIN, VERSION_RANK_MAX + 1)]:
        nom = project_layout.scan_lot_dir(
            project_dir, ingest_slug,
            version_rank=None if rang == version_ranks.RANG_ORIGINE else rang,
        ).name
        if nom in presents:
            rangs.add(rang)
    return rangs


def _refuse_destructive_overwrite(lot_dir: Path, sources: list[Path]) -> None:
    """Refuser d'ecraser un lot deja materialise par un contenu **different**.

    Sans garde, une seconde ingestion sous le meme slug ecrasait les fichiers du
    premier lot -- y compris quand la seconde echouait ensuite, si bien que le
    rapport du premier survivait en decrivant des pixels qui n'existaient plus
    (5.1-C3-1). La copie « fait foi »: elle est parfois la seule trace restante,
    la cle USB ayant ete rendue.

    Re-ingerer **le meme** scan reste en revanche legitime et doit rester
    idempotent: un operateur qui relance la commande apres une coupure ne doit
    pas avoir a inventer un nouveau slug. La garde ne mord donc que sur une
    collision de nom portant un contenu different -- le seul cas ou quelque
    chose serait reellement perdu.
    """
    if not lot_dir.exists():
        return
    # Indexe par la cle de collision, jamais par le nom brut : sur NTFS,
    # copier `usb/planche.tiff` dans un lot qui porte deja `Planche.tiff`
    # ECRASE ce dernier, et la garde le laissait passer parce que les deux
    # chaines different. Mesure du defaut : le fichier du lot passait d'un
    # contenu a l'autre sans un mot, alors que le cas strictement homonyme,
    # lui, refusait bien -- c'etait donc la casse et rien d'autre.
    by_name = {_cle_de_nom(path.name): path for path in sources}
    conflicting = [
        entry.name
        for entry in sorted(lot_dir.iterdir())
        if entry.is_file()
        and _cle_de_nom(entry.name) in by_name
        and not _same_bytes(by_name[_cle_de_nom(entry.name)], entry)
    ]
    if conflicting:
        # TROIS issues, dont une NON destructive et automatique
        # (`EPIC11-ARB-104`). Les deux d'origine etaient des corvees manuelles:
        # inventer un slug, ou vider le dossier -- et la seconde detruit la
        # version d'avant. Le scenario d'Egan les rend insuffisantes: on
        # reprend une planche imprimee, on ajoute un point rouge dans un coin,
        # on rescanne. Le contenu a change, l'identite non, et il n'y a aucune
        # raison d'inventer un nom pour cela.
        raise UnsupportedScanInputError(
            f"Le lot '{lot_dir.name}' contient deja "
            f"{len(conflicting)} fichier(s) de meme nom mais de contenu different "
            f"({', '.join(conflicting[:3])}). L'ingestion n'ecrase pas un lot "
            "existant: la copie fait foi et peut etre la seule trace restante du "
            "scan. Trois issues: relancer avec --nouvelle-version pour ingerer "
            "un scan VOISIN sans toucher a celui-ci (le rang entre dans le nom "
            "du dossier); choisir un autre --lot-slug; ou vider ce dossier "
            "volontairement."
        )


def _materialise_folder(scan_path: Path, lot_dir: Path, sources: list[Path]) -> Path:
    """Ingerer en place si le dossier est deja sous `scans/`, sinon le copier.

    ``sources`` est la liste **decouverte a la source**: seuls ces fichiers sont
    copies, et ce sont eux qui feront les pages. Copier le dossier entier puis
    relire la destination etait le bloquant 5.1-C1-01.
    """
    scans_root = lot_dir.parent
    if _est_un_dossier_de_lot(scan_path, scans_root):
        # Deja un dossier de lot sous `scans/`: ingestion en place, aucun
        # octet deplace. `scans/` lui-meme est exclu -- il contient les lots,
        # il n'en est pas un.
        return scan_path

    _refuse_destructive_overwrite(lot_dir, sources)
    lot_dir.mkdir(parents=True, exist_ok=True)
    for entry in sources:
        try:
            # `copy2`, jamais `move`: le dossier de l'operateur n'est pas a nous.
            shutil.copy2(entry, lot_dir / entry.name)
        except OSError:
            # Un lien symbolique casse, un fichier disparu entre la decouverte
            # et la copie, une permission refusee: on ne copie pas, et le
            # fichier manquera a l'arrivee. Le saut sera alors **constate a la
            # lecture** et nomme dans le rapport. Une seule politique de saut,
            # au meme endroit, plutot que deux qui pourraient diverger.
            continue
    return lot_dir


def _est_un_dossier_de_lot(dossier: Path, scans_root: Path) -> bool:
    """Vrai quand ``dossier`` est un dossier de LOT, sous `scans/`.

    `scans/` lui-meme n'en est pas un : c'est la racine qui **contient** les
    lots. Sans cette distinction, un fichier depose directement dans
    `<projet>/scans/` etait ingere « en place » avec `scans/` pour dossier de
    lot, et son `ingest.json` allait s'ecrire a la racine des lots -- un
    rapport de lot posé sur l'arborescence entiere, que le lot suivant
    ecrasait. `_is_inside` seul rend vrai pour la racine comme pour ses
    descendants ; c'est ce qu'il fallait separer (`EPIC7-ARB-88`).
    """
    if not _is_inside(dossier, scans_root):
        return False
    try:
        return dossier.resolve() != scans_root.resolve()
    except OSError:
        return False


def _materialise_selection(
    sources: list[Path], lot_dir: Path
) -> tuple[Path, list[Path]]:
    """Materialiser une SELECTION de fichiers dans un lot **unique**.

    Meme politique que :func:`_materialise_folder`, transposee a une liste de
    chemins qui ne partagent pas forcement un dossier : ingestion en place
    quand la selection tient dans un seul dossier deja situe sous `scans/`,
    copie sinon. Rend le dossier de lot **reellement utilise** et la liste des
    fichiers a lire, dans cet ordre-la -- jamais un chemin reconstruit d'un
    cote et une liste de l'autre.

    Les fichiers absents de la copie (permission refusee, source disparue)
    restent dans la liste rendue, a leur place dans le lot : le saut est
    **constate a la lecture** et nomme au rapport (`skipped_files` +
    `UNREADABLE_FILE_SKIPPED`), par la meme politique unique que le dossier.
    Les retirer de la liste les ferait disparaitre du cardinal sans un mot --
    trois fichiers deposes, une page au rapport, zero avertissement.
    """
    scans_root = lot_dir.parent
    parents = {entry.parent.resolve() for entry in sources}
    if len(parents) == 1:
        unique = next(iter(parents))
        if _est_un_dossier_de_lot(unique, scans_root):
            # Deja sous `scans/`: aucun octet deplace. Seuls les fichiers
            # SELECTIONNES feront des pages, meme si le dossier en porte
            # d'autres -- c'est la liste qui fait foi, pas le dossier.
            return unique, list(sources)

    _refuse_destructive_overwrite(lot_dir, sources)
    lot_dir.mkdir(parents=True, exist_ok=True)
    for entry in sources:
        destination = lot_dir / entry.name
        try:
            if entry.resolve() == destination.resolve():
                # La source EST deja a sa place. Cela arrive des qu'une
                # selection s'etale sur plusieurs dossiers dont l'un est le
                # lot vise : `shutil.copy2(x, x)` leve alors -- `SameFileError`
                # ailleurs, `PermissionError` sous Windows, toutes deux des
                # `OSError`.
                #
                # **Tolerance documentee, mesuree le 2026-08-27.** Cette garde
                # n'a plus d'effet OBSERVABLE depuis que la liste rendue est
                # reconstruite depuis les sources : sans elle, l'`OSError` est
                # simplement rattrapee douze lignes plus bas, et le rapport est
                # identique -- meme cardinal, meme `skipped_files` vide, meme
                # fichier intact. Son mutant survit donc, et c'est normal.
                #
                # Elle reste parce qu'elle ne protege pas le rapport mais le
                # FICHIER : elle rend l'intention explicite et ne fait pas
                # dependre l'integrite d'une page deja rangee d'un detail
                # d'implementation de `shutil` -- aujourd'hui `copyfile` teste
                # `_samefile` et leve avant d'ouvrir la destination, donc sans
                # rien tronquer, mais rien dans le contrat de `shutil` ne le
                # promet. Le prix d'un `if` contre le risque de tronquer la
                # seule copie restante d'un scan : le choix ne se discute pas.
                continue
            shutil.copy2(entry, destination)
        except OSError:
            # Un fichier disparu entre la decouverte et la copie, une
            # permission refusee, un disque plein : on ne copie pas, et le
            # fichier manquera a l'arrivee. Le saut est **constate a la
            # lecture** et nomme dans le rapport -- voir ci-dessous.
            continue
    # La liste des fichiers a lire est RECONSTRUITE depuis les sources, comme
    # le fait `_materialise_folder`, et non accumulee au fil des copies
    # reussies. C'est ce qui fait qu'un fichier absent a l'arrivee devient un
    # `skipped_files` nomme et un `UNREADABLE_FILE_SKIPPED`, au lieu de
    # disparaitre du cardinal en silence : trois fichiers deposes, une page au
    # rapport, zero avertissement -- le faux succes R12, mesure le 2026-08-27.
    # Une seule politique de saut, au meme endroit, pour le dossier comme pour
    # la selection.
    return lot_dir, [lot_dir / entry.name for entry in sources]


def _materialise_file(scan_path: Path, lot_dir: Path) -> Path:
    """Copier un fichier exterieur sous `scans/<slug>/`; la copie fait foi.

    Un fichier deja range dans un dossier de LOT est ingere en place. Un
    fichier pose directement dans `<projet>/scans/` ne l'est pas : il est
    copie sous son propre `scans/<slug>/`, parce que `scans/` n'est pas un lot
    (`EPIC7-ARB-88`).
    """
    scans_root = lot_dir.parent
    if _est_un_dossier_de_lot(scan_path.parent, scans_root):
        return scan_path

    _refuse_destructive_overwrite(lot_dir, [scan_path])
    destination = lot_dir / scan_path.name
    lot_dir.mkdir(parents=True, exist_ok=True)
    # `copy2`, jamais `move`: deplacer viderait le dossier source de l'operateur.
    shutil.copy2(scan_path, destination)
    return destination


def load_page_array(
    project_dir: str | Path, locator: PageLocator, *, dpi: int
) -> np.ndarray:
    """Charger les pixels d'une page depuis son **localisateur**.

    Point d'entree publie a l'usage des stories aval (contrat de jonction pose a
    5.2): elles obtiennent leurs pixels par ici, jamais par un `cv2.imread`
    local. La signature prend un localisateur et non un chemin, precisement
    parce qu'une page de PDF n'a pas de chemin propre -- une signature par
    chemin rendrait la forme PDF inaccessible et la ferait re-implementer
    ailleurs, avec un ordre de canaux et une profondeur decides une seconde fois.
    """
    dpi = validate_scan_dpi(dpi)
    source = Path(project_dir) / locator.source_path
    # **Le dispatch se fait sur la NATURE du fichier, jamais sur la presence
    # d'un index** (story 5.31). Il lisait `page_index is None` : depuis qu'une
    # page d'IMAGE peut porter un index, ce critere aurait envoye chaque page
    # de TIFF multipage dans `_open_pdf` -- une panne franche, mais LOIN de sa
    # cause, et seulement a la lecture des pixels, c'est-a-dire apres une
    # ingestion qui a l'air reussie.
    if source.suffix.lower() not in PDF_EXTENSIONS:
        return lire_une_page_image(source, locator.page_index).tableau
    document = _open_pdf(source)
    try:
        return _render_pdf_page(document, locator.page_index, dpi)
    finally:
        document.close()


def report_document(report: ScanIngestReport) -> dict:
    """Document serialisable du rapport, empreinte comprise."""
    document = report.as_document()
    document["fingerprint"] = fingerprint_of(document)
    return document


def report_json(report: ScanIngestReport) -> str:
    """Serialisation canonique: deux ingestions identiques rendent le meme texte.

    Les helpers de canonicalisation sont ceux de `extraction_previz`, importes
    et jamais recopies -- deux recettes qui divergent sont exactement le defaut
    corrige en revue de 3.5.
    """
    return canonical_json(report_document(report))


def slug_par_defaut(project_dir, scan_path) -> str:
    """Le slug que `ingest_scan_lot` retiendrait pour cette entree.

    **Sans rien ingerer, sans rien ecrire, sans rien lire du disque** au-dela
    de l'existence des chemins. Une interface qui veut savoir *avant* de
    lancer une passe si le lot vise porte deja une detection
    (`EPIC7-ARB-90`) a besoin de ce nom-la, et il n'y a qu'une facon correcte
    de le derive : celle qu'`ingest_scan_lot` applique. La recopier cote GUI
    la ferait diverger au premier changement -- c'est exactement le motif de
    `decisions-2026-08-02.md`, decision 2.

    Rend le slug **valide** (il passe `validate_ingest_slug`) ou leve, avec le
    meme motif que l'ingestion aurait leve.
    """
    project_dir = Path(project_dir)
    selection = _normaliser_la_selection(scan_path)
    if selection is not None and len(selection) == 1:
        scan_path, selection = selection[0], None
    if selection is None:
        scan_path = Path(scan_path)
        if not scan_path.exists():
            raise UnsupportedScanInputError(
                f"Chemin de scan introuvable: {scan_path}")
        brut = scan_path.stem if scan_path.is_file() else scan_path.name
    else:
        brut = _slug_par_defaut_d_une_selection(
            selection, project_dir / project_layout.SCANS_DIRNAME)
    return validate_ingest_slug(brut)


#: Les quatre formes d'entree de l'ingestion (`EPIC7-ARB-88`), **nommees**.
#: Jusqu'ici elles n'existaient que comme branches d'un `if` : une interface qui
#: doit dire « 1 PDF, 8 pages » plutot que « 8 fichiers » n'avait aucun moyen de
#: demander de quelle forme il s'agit, et devait redecider elle-meme -- c'est-a-
#: dire ecrire une seconde fois la regle que ce module porte
#: (`EPIC7-ARB-88` : « c'est l'ingestion qui distingue les quatre formes, et elle
#: seule »).
FORME_DOSSIER = "dossier"
FORME_PDF = "pdf"
FORME_IMAGE = "image"
FORME_SELECTION = "selection"


@dataclass(frozen=True)
class SourceMesuree:
    """Ce qu'une source de scan **contient et pese**, sans rien ingerer.

    Story 11.5, lot B (AC 3.4). Pendant de :func:`mesurer_le_dpi`, et pour le
    meme motif : une interface doit pouvoir montrer ce qui sera lu **avant**
    que le lot n'entre dans le projet. Elle n'ecrit rien, ne copie rien, ne cree
    aucun dossier de lot et n'exige aucun dpi.

    ``cardinal`` compte des **PAGES**, dans toutes les formes
    (`EPIC11-ARB-157`). Il comptait des fichiers pour un dossier et une
    selection, ce qui etait exact tant qu'un fichier valait une page ; depuis
    qu'un PDF peut se trouver au milieu d'un dossier, trois fichiers peuvent
    faire six pages, et rendre `3` serait un compte faux presente comme une
    mesure.

    ``fichiers`` dit **sur combien de fichiers** ces pages sont reparties. Les
    deux sont necessaires, et c'est la raison d'etre du champ : sans lui,
    l'appelant ne peut pas choisir son mot. `EPIC11-ARB-26` demande « page »
    pour un PDF et « fichier » pour le reste, et cette regle ne se decide plus
    a partir de la seule `forme` -- un dossier melange porte les deux natures.
    La question qu'un ecran pose est « ce nombre compte-t-il des fichiers ? »,
    et elle se repond par `cardinal == fichiers`.

    ``dpi`` est la mesure de :func:`mesurer_le_dpi`, **informative** comme elle :
    elle est confrontee au dpi declare, jamais substituee.
    """

    forme: str
    cardinal: int
    octets: int
    dpi: float | None
    #: Combien de FICHIERS portent ces pages. `1` pour un PDF seul et pour une
    #: image seule -- un document est un fichier, quel que soit son nombre de
    #: pages.
    #:
    #: **Sans defaut, et c'est delibere.** Il en avait un (`= 1`), et une
    #: construction qui l'oubliait produisait exactement le compte faux que
    #: cette vague existe pour supprimer : `SourceMesuree(FORME_DOSSIER, 24,
    #: ...)` sans `fichiers` rendait « 24 pages » pour 24 fichiers image,
    #: puisque `unite_du_cardinal` lit l'ecart des deux nombres. Le depot
    #: refuse la valeur devinee la ou une mesure est attendue (`poids_du_fichier`
    #: : « `None` et jamais `0` [...] refuse la valeur devinee »), et un champ
    #: qui SERT a decider d'un mot est une mesure. Les deux sites de production
    #: le passent explicitement ; l'absence de defaut fait de l'oubli une
    #: erreur d'appel plutot qu'un compte faux.
    fichiers: int


def _reconnaitre_la_source(scan_path):
    """La forme d'entree, ses fichiers et son chemin -- ou un refus **nomme**.

    Rend `(forme, fichiers, chemin)`. ``fichiers`` est la liste ordonnee des
    pages-fichiers, `None` pour un PDF (ses pages n'existent comme fichiers
    nulle part) ; ``chemin`` est le chemin designe, `None` pour une selection
    qui n'en a pas un seul.

    **Une seule redaction de la reconnaissance des quatre formes.** Elle etait
    dans le corps de :func:`mesurer_le_dpi` ; :func:`mesurer_la_source` en avait
    besoin mot pour mot, et une seconde redaction aurait diverge exactement la
    ou personne ne regarde -- sur les refus, qui sont des chemins qu'aucun
    parcours nominal n'exerce.
    """
    # `scan_path` est passe TEL QUEL au normalisateur de selection, jamais
    # coerce en `Path` : c'est lui, et lui seul, qui distingue une sequence de
    # chemins d'un chemin unique. Le `TypeError` qu'une sequence de non-chemins
    # (`b"..."`, une liste d'entiers) y ferait lever est retraduit en refus
    # nomme -- c'est la moitie que l'AC 7.4 de la 11.4b ajoute a l'existant.
    try:
        selection = _normaliser_la_selection(scan_path)
    except TypeError as exc:
        raise UnsupportedScanInputError(
            f"Forme d'entree non mesurable: {scan_path!r}. Une sequence de "
            "scan ne porte que des chemins de fichiers."
        ) from exc
    # Meme reduction qu'a l'ingestion, et pour la meme raison : un seul chemin
    # dans une liste est exactement le cas a un chemin, et le traiter comme une
    # selection ferait diverger la mesure d'un PDF designe seul de celle du
    # meme PDF designe dans une liste d'un element.
    if selection is not None and len(selection) == 1:
        scan_path, selection = selection[0], None
    if selection is not None:
        return FORME_SELECTION, selection, None

    if not isinstance(scan_path, (str, Path)):
        raise UnsupportedScanInputError(
            f"Forme d'entree non mesurable: {scan_path!r} "
            f"({type(scan_path).__name__}). Attendu un dossier d'images, une "
            f"image ({', '.join(IMAGE_EXTENSIONS)}), un PDF, ou une sequence "
            "de chemins de fichiers."
        )
    chemin = Path(scan_path)
    if not chemin.exists():
        raise UnsupportedScanInputError(f"Chemin de scan introuvable: {chemin}")
    if chemin.is_dir():
        sources, _ignores = _discover_folder_pages(chemin)
        if not sources:
            # Le **meme** refus nomme que l'ingestion leverait sur ce dossier,
            # et non un `None`. Les deux reponses ne disent pas la meme chose :
            # `None` veut dire « des pages, aucune resolution declaree », et le
            # confondre avec « aucune page » ferait afficher « dpi non
            # mesurable » sur un dossier qui ne sera de toute facon jamais
            # ingere.
            raise EmptyScanLotError(
                f"Aucune page dans {chemin} (extensions reconnues: "
                f"{', '.join(PAGE_EXTENSIONS)})."
            )
        return FORME_DOSSIER, sources, chemin
    if chemin.suffix.lower() in PDF_EXTENSIONS:
        return FORME_PDF, None, chemin
    if chemin.suffix.lower() in IMAGE_EXTENSIONS:
        return FORME_IMAGE, [chemin], chemin
    raise UnsupportedScanInputError(
        f"Forme d'entree non supportee: {chemin}. Attendu un dossier "
        f"d'images, une image ({', '.join(IMAGE_EXTENSIONS)}) ou un PDF."
    )


def _poids(chemin: Path) -> int:
    """La taille d'un fichier, ou `0` s'il ne se `stat` pas.

    Un fichier disparu entre la liste et la mesure n'est pas une panne
    d'affichage : la somme le compte pour rien, et l'ingestion, elle, dira ce
    qu'il en est. Cette fonction ne refuse pas -- elle **pese**.
    """
    try:
        return chemin.stat().st_size
    except OSError:
        return 0


def mesurer_le_dpi(scan_path) -> float | None:
    """Le dpi que les fichiers **declarent**, sans rien copier ni rien ingerer.

    Story 11.4b, lot S5 (AC 7). Pendant de :func:`slug_par_defaut` et de
    :func:`dossier_de_lot_par_defaut`, pour le meme motif : une interface doit
    pouvoir montrer une valeur **avant** que le lot n'entre dans le projet.
    `EPIC11-ARB-38` l'exige mot pour mot -- « la valeur mesuree est affichee a
    cote du champ, **des le depot** » -- et c'etait intenable jusqu'ici :
    :func:`_measure_pages_dpi` est privee, et ses trois appelants exigent deja
    un dpi **et** ont deja copie les fichiers dans le projet (fait F5 de la
    11.4b).

    **Ce que cette fonction ne fait pas**, et c'est tout son objet : elle
    n'ecrit rien, ne copie rien, ne cree aucun dossier de lot, et **n'exige
    aucun dpi**. Elle ne lit du disque que les fichiers designes, et n'en lit
    que l'en-tete de resolution.

    **La mesure reste informative** (AC 7.3), verbatim de
    :func:`_measure_file_dpi` : « Mesure **informative** : elle est confrontee
    au DPI declare, **jamais substituee**. » Cette fonction **rend** la mesure
    et ne la substitue a rien : aucun chemin d'ingestion ne l'appelle, et le
    dpi de l'ingestion reste celui que l'operateur declare. Un scanner en
    auto-fit ecrit une resolution qui ne correspond pas a l'echelle reelle de
    la page ; s'en servir comme dpi serait le risque R8, en pire -- une valeur
    *qui a l'air juste*.

    **Les quatre formes d'entree de l'ingestion** (`EPIC7-ARB-88`), et rien
    d'autre : un dossier d'images, un PDF, une image seule, une **sequence de
    chemins de fichiers**. Ce qu'elle ne sait pas mesurer est refuse
    **nommement**, jamais par un `TypeError` nu -- piege deja paye a
    `scan_detect.py:250-260`, ou coercer `scan_path` en `Path` detruisait la
    quatrieme forme et remplacait un motif lisible par un message Python
    affiche sur une carte de tache.

    Rend :

    * la **plus basse** des resolutions declarees par les pages du lot,
      mesuree sur **toutes** les pages et non sur la premiere du tri -- c'est
      :func:`_measure_pages_dpi`, appelee et jamais recopiee : une seconde
      redaction de la regle du minimum divergerait de celle que le rapport
      d'ingestion inscrit dans `measured_dpi`, et l'ecart ne se verrait
      **jamais** puisque les deux valeurs ne sont pas affichees au meme
      moment ;
    * ``None`` quand **aucune** page ne declare de resolution (AC 7.2) --
      jamais une valeur devinee, jamais le dpi d'un voisin.

    **Le PDF est mesure, et c'est un ecart assume a la recommandation Q2 de la
    fiche.** Q2 recommandait de rendre `None` pour un PDF « plutot que de
    rendre une valeur derivee d'une taille de media box ». Sa premisse est
    fausse dans ce depot, verifie : :func:`_measure_pdf_dpi` ne derive rien
    d'une media box, elle lit le `horizontal_dpi` des images **embarquees**, et
    son docstring dit pourquoi elle existe -- « un `--dpi 600` sur une page
    dont l'image embarquee n'est qu'a 200 dpi produit une page de 600 dpi
    nominaux et de 200 dpi reels ». C'est litteralement le cas qu'`EPIC11-ARB-38`
    veut faire voir a l'operateur avant qu'il ne saisisse son dpi. Rendre
    `None` la ou l'ingestion, dix secondes plus tard, ecrira `measured_dpi:
    200` au rapport, ce serait **deux verites** pour un seul fait
    (`EPIC5-ARB-78`). La fonction rend donc, forme par forme, exactement la
    mesure que l'ingestion inscrira.
    """
    forme, fichiers, chemin = _reconnaitre_la_source(scan_path)
    if forme == FORME_PDF:
        return _measure_pdf_dpi(chemin)
    return _measure_pages_dpi(fichiers)


def mesurer_la_source(scan_path) -> SourceMesuree:
    """Ce que la source **contient et pese**, avec son dpi, sans rien ingerer.

    Story 11.5, lot B (AC 3.4 et AC 3.5). Un ecran de depot doit annoncer
    « 1 PDF · 8 pages · 1,2 Go » ou « 24 fichiers · 1,9 Go » **avant** toute
    ingestion, et le vocabulaire n'y est pas cosmetique : confondre pages et
    fichiers est ce qui ferait declarer un lot incomplet a tort.

    **La forme est rendue, jamais redecidee par l'appelant.** `EPIC7-ARB-88` :
    « c'est l'ingestion qui distingue les quatre formes, **et elle seule** ».
    Une interface qui compterait elle-meme les fichiers d'un dossier ecrirait
    une seconde fois le filtre d'extensions de :func:`_discover_folder_pages`,
    et les deux comptes divergeraient au premier `.webp` ajoute a la table.

    **Aucune forme ne compte des fichiers depuis `EPIC11-ARB-157`** : le
    cardinal compte des PAGES partout, et `fichiers` dit sur combien de
    fichiers elles se repartissent. Ce paragraphe annoncait « le PDF est le
    seul cas ou le cardinal n'est pas un compte de fichiers », ce qui etait
    vrai la veille et faux le jour ou le dossier et la selection ont cesse de
    compter des fichiers.

    Le cardinal d'un PDF designe SEUL s'obtient par :func:`_open_pdf`, le point
    unique d'ouverture du module : un PDF chiffre, corrompu ou vide y leve son
    refus nomme plutot que de rendre `0`, qui se lirait comme « un PDF de zero
    page » et donc comme un document valide et vide. **Au milieu d'un dossier
    ou d'une selection, le meme PDF ne leve pas** : il compte pour une page et
    sera saute a l'ingestion, parce qu'un document illisible ne doit pas rendre
    tout un lot indesignable.

    Rend un :class:`SourceMesuree`. Leve les **memes** refus que
    :func:`mesurer_le_dpi` sur les memes entrees -- ils viennent tous deux de
    :func:`_reconnaitre_la_source`.
    """
    forme, fichiers, chemin = _reconnaitre_la_source(scan_path)
    if forme == FORME_PDF:
        document = _open_pdf(chemin)
        try:
            cardinal = len(document)
        finally:
            document.close()
        return SourceMesuree(forme, cardinal, _poids(chemin),
                             _measure_pdf_dpi(chemin), fichiers=1)
    # **Le poids se somme sur les pages RETENUES**, pas sur le dossier entier :
    # un `Thumbs.db` ou un `.DS_Store` ne sera jamais lu, et le compter ferait
    # annoncer un poids que rien n'ingerera. Les deux moities de la ligne --
    # cardinal et poids -- portent donc sur exactement le meme ensemble.
    # **Le cardinal compte des PAGES, pas des fichiers** (`EPIC11-ARB-157`) :
    # un dossier de trois PDF de 1, 3 et 2 pages annonce `6`. Le poids, lui,
    # reste celui des FICHIERS retenus -- c'est ce qui sera lu sur le disque.
    return SourceMesuree(forme, _cardinal_des_pages(fichiers),
                         sum(_poids(f) for f in fichiers),
                         _measure_pages_dpi(fichiers), fichiers=len(fichiers))


def dossier_de_lot(project_dir, report: ScanIngestReport) -> Path:
    """Le dossier de lot **reellement utilise** par cette ingestion.

    Point unique de cette derivation. Tous les artefacts d'une passe --
    `ingest.json`, `tri.json`, `detections/` -- vivent dans CE dossier, et
    aucun d'eux ne doit le recomposer depuis `report.ingest_slug` : les deux
    divergent des qu'un fichier deja range sous `<projet>/scans/<lot>/` est
    ingere en place, le slug valant alors le nom du fichier et non celui du
    dossier. La passe eparpillait sinon ses trois documents dans deux dossiers,
    dont un dossier de lot **fantome** sans images ni rapport (mesure du
    2026-08-27, `EPIC7-ARB-88`).
    """
    return Path(project_dir) / Path(report.scans_dir)


def dossier_de_lot_par_defaut(project_dir, scan_path) -> Path:
    """Le dossier de lot qu'une passe emploierait, **sans rien ingerer**.

    Pendant de :func:`slug_par_defaut`, pour la meme raison : une interface
    qui veut savoir, AVANT de lancer, si le lot vise porte deja une detection
    (`EPIC7-ARB-90`) doit regarder au bon endroit. Le slug ne suffit pas -- il
    ne nomme le dossier que dans le cas ou l'ingestion copie.

    Ne lit du disque que l'existence et la nature des chemins, n'ecrit rien.
    """
    project_dir = Path(project_dir)
    scans_root = project_dir / project_layout.SCANS_DIRNAME
    lot_par_le_slug = project_layout.scan_lot_dir(
        project_dir, slug_par_defaut(project_dir, scan_path))

    selection = _normaliser_la_selection(scan_path)
    if selection is not None and len(selection) == 1:
        scan_path, selection = selection[0], None
    if selection is not None:
        parents = {chemin.parent.resolve() for chemin in selection}
        if len(parents) == 1 and _est_un_dossier_de_lot(
            next(iter(parents)), scans_root
        ):
            return next(iter(parents))
        return lot_par_le_slug

    chemin = Path(scan_path)
    if chemin.is_dir():
        return chemin if _est_un_dossier_de_lot(chemin, scans_root) else lot_par_le_slug
    if _est_un_dossier_de_lot(chemin.parent, scans_root):
        return chemin.parent
    return lot_par_le_slug


def chemin_du_rapport(project_dir, report: ScanIngestReport) -> Path:
    """Ou `ingest.json` s'ecrit : sous le dossier **reellement utilise**.

    Implementation unique, et c'est tout son objet. `report.scans_dir` est
    derive du dossier de lot que l'ingestion a vraiment employe ; le
    reconstruire depuis `report.ingest_slug` donne un chemin **different** des
    que le lot n'est pas sous `scans/<slug>/`.

    **Le cas vivant est le RANG DE VERSION**, et il est mesure : une seconde
    ingestion du meme lot ecrit sous `scans/<slug>_v2/` pendant que
    `ingest_slug` garde `<slug>`. La reconstruction viserait donc toujours le
    rang 1, c'est-a-dire le dossier d'une AUTRE version -- et l'ecraserait.
    `tests/unit/test_chemin_du_rapport_de_scan.py` joue les rangs 1, 2 et 3.

    **Ce que ce docstring disait et qui n'est plus vrai** (corrige le
    2026-09-07, sur mesure). Il citait « un fichier deja situe sous
    `<projet>/scans/` », dont `scans_dir` « vaut alors `scans` ». Ce regime est
    ferme depuis `EPIC7-ARB-88`, qui a exclu `scans/` lui-meme de
    `_est_un_dossier_de_lot` : un tel fichier recoit desormais son propre
    dossier de lot (`scans/Ma Mire/`), et le chemin reconstruit **coincide**.
    La seule divergence vivante etait donc la seule que rien ne mesurait,
    pendant que la prose decrivait celle qui ne l'etait plus -- ce que le meme
    banc tient maintenant des deux cotes, dont une frontiere negative sur cette
    phrase-ci.

    Cette divergence a deja coute une `FileNotFoundError` nue apres une
    ingestion pourtant reussie (5.1-C1-02 / C2-4, corrige a l'epoque du seul
    cote de `scan`), puis une seconde fois du cote de `scan detect` et de la
    GUI -- `[Errno 2] ... scans\\<slug>\\ingest.json`, essai de terrain du
    2026-08-27, `EPIC7-ARB-88`. Les deux appelants passent desormais par ici :
    il n'y a plus de second endroit ou se tromper.
    """
    return dossier_de_lot(project_dir, report) / INGEST_DOCUMENT_FILENAME


def ecrire_le_rapport(project_dir, report: ScanIngestReport) -> Path:
    """Ecrire `ingest.json` a sa place et rendre son chemin."""
    chemin = chemin_du_rapport(project_dir, report)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(report_json(report), encoding="utf-8")
    return chemin


__all__ = [
    "FINGERPRINT_PREFIX",
    "IMAGE_EXTENSIONS",
    "PAGE_EXTENSIONS",
    "INGEST_DOCUMENT_FILENAME",
    "PDF_EXTENSIONS",
    "SCAN_INGEST_WARNING_CODES",
    "ALPHA_NON_OPAQUE_RETIRE",
    "IMAGE_PAGES_PARTIALLY_READABLE",
    "EmptyScanLotError",
    "IngestedPage",
    "InvalidScanDpiError",
    "PageLocator",
    "PdfIngestError",
    "ScanIngestError",
    "ScanIngestReport",
    "UnsupportedScanInputError",
    "chemin_du_rapport",
    "ecrire_le_rapport",
    "dossier_de_lot",
    "dossier_de_lot_par_defaut",
    "ingest_scan_lot",
    "mesurer_le_dpi",
    "slug_par_defaut",
    "load_page_array",
    "lire_une_page_image",
    "read_image_page",
    "report_document",
    "report_json",
    "validate_scan_dpi",
    "validate_warning_code",
]
