"""Identite de chaine de scan et derive de son identifiant (story 5.22).

Une chaine de scan est l'assemblage reel **scanner + pilote + reglages +
format** qu'`EPIC5-ARB-80` designe comme le porteur de la correction couleur:
la correction est generee **une fois par chaine**, pas par lot, et reutilisee
pour tous les lots de la chaine.

L'identifiant de chaine est **auto-derive** des parametres reels de la chaine,
de facon deterministe et inter-machine, selon la doctrine du condensat de 5.12
(`io.naming.bounds_suffix`): jamais de `hash()` Python, jamais d'horodate,
jamais de chemin absolu, jamais de slug operateur, jamais de pixels. Un meme
jeu de parametres retombe sur le meme `chain_id` sur deux executions et sur
deux machines.

Materiel capture (decision de la story, mesuree sur les trois captures de
`projects/chendj-mat/scans/` le 2026-08-17) :

* `declared_dpi` -- le reglage de resolution **declare** au scan (jamais la
  mesure: elle informe et ne se substitue pas) ;
* `scan_input_format` -- le format de fichier **reellement produit** par
  l'ingestion (`pdf`, `tiff`, `png`, ...), jamais deduit d'une extension ;
* `make` / `model` -- l'identite physique du scanner, tags TIFF 271/272, en
  **best effort**: absents des trois captures reelles du depot (mesure du
  2026-08-17, tous les tags valent `None`), donc representes par `""` ;
* `software` -- le pilote, tag TIFF 305, meme regime best effort.

La **forme de page** (`template_id`) n'entre **pas** dans le materiel, et
c'est une decision mesuree de la story. Deux lots de la meme chaine qui
impriment des gabarits differents sont la **meme** chaine -- c'est exactement
le cas du declencheur (scans refuses par divergence alors que le scanner est
le meme) --, et faire varier le materiel avec le gabarit aurait recompartimente
la correction par contenu imprime, reproduisant a l'echelle de la chaine le
defaut que la story corrige au niveau du lot. La forme est portee **par le
profil** (`template_id` dans le fichier) comme provenance, sans participer a
l'identite.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from .io import naming
from .numeric_guards import is_strict_int

#: Separateur de champs du materiel condense. Le meme separateur que
#: `bounds_suffix` (lecon du 2026-08-05): il desambiguise les tuples partiels.
#:
#: **Il ne suffit pas a lui seul**, et c'est le correctif du 2026-08-17: la
#: lecon de `bounds_suffix` porte sur les tuples **partiels** (des segments
#: toujours presents empechent `(a, b)` et `(a, b, "")` de se confondre), pas
#: sur un separateur present **dans** un champ. Les champs captures ici ne sont
#: pas sous notre controle -- `make`, `model` et `software` sont des tags TIFF
#: ecrits par un pilote quelconque, et rien n'interdit a un pilote d'y mettre un
#: `|`. Sans le prefixe de longueur ci-dessous, `make='X|Y', model='Z'` et
#: `make='X', model='Y|Z'` rendaient litteralement le meme materiel, donc le
#: meme `chain_id`, donc **le meme fichier de profil pour deux chaines
#: physiquement differentes** -- le risque inverse exact de celui que la story
#: 5.22 existe pour supprimer.
CHAIN_MATERIAL_SEPARATOR = "|"

#: Delimiteur entre le prefixe de longueur d'un segment et son contenu.
#: L'encodage d'un segment est `<nombre de caracteres>:<contenu>`, ce qui rend
#: la concatenation **injective**: le lecteur lit la longueur avant le contenu,
#: donc un separateur (ou un delimiteur) present dans le contenu ne peut plus
#: etre confondu avec une frontiere de champ. Deux materiels egaux impliquent
#: alors des cinq-uplets egaux, ce qui est exactement la propriete dont depend
#: l'unicite du `chain_id`.
CHAIN_MATERIAL_LENGTH_DELIMITER = ":"

#: Longueur du condensat sha256 de la chaine, en caracteres hexadecimaux.
CHAIN_ID_HASH_LENGTH = 12

#: Tags TIFF de l'identite scanner/pilote, lus via Pillow `im.tag_v2`.
TIFF_TAG_MAKE = 271
TIFF_TAG_MODEL = 272
TIFF_TAG_SOFTWARE = 305

#: Suffixes que Pillow sait ouvrir pour y lire les tags. Un PDF n'y entre pas:
#: il ne porte pas de tags TIFF et l'identite scanner y est irremediablement
#: absente (best effort, documente).
_TAG_READABLE_SUFFIXES = frozenset(
    {".tiff", ".tif", ".png", ".jpg", ".jpeg", ".webp", ".bmp"}
)


class InvalidChainParameterError(ValueError):
    """Un parametre de chaine est hors du domaine capture.

    Deliberement pas un repli: un `chain_id` derive d'un dpi faux ou d'un
    format vide serait stable mais faux, et deux chaines differentes
    pourraient s'y confondre en silence.
    """


def chain_material(*, declared_dpi: int, scan_input_format: str,
                   make: str = "", model: str = "", software: str = "") -> str:
    """Condenser les parametres de la chaine en une chaine deterministe.

    Les cinq segments sont **toujours** presents, dans un ordre fixe, vides ou
    non: un champ absent (`""`) reste un segment distinct, ce qui empeche deux
    tuples **partiels** de se confondre (`(a, b)` contre `(a, b, "")`) et rend
    le materiel stable d'une machine a l'autre.

    Chaque segment est de plus prefixe de sa longueur
    (`<n>:<contenu>`, cf. `CHAIN_MATERIAL_LENGTH_DELIMITER`), ce qui rend
    l'encodage **injectif**: un `CHAIN_MATERIAL_SEPARATOR` present *dans* un
    tag scanner ne peut plus deplacer une frontiere de champ. Les segments
    toujours presents ne protegent que des tuples partiels; ils ne protegent
    **pas** d'un separateur dans un champ, et l'ancienne docstring promettait
    ici l'inverse de ce que le code faisait (corrige le 2026-08-17).

    Consequence assumee: l'encodage ayant change, tous les `chain_id` derives
    changent. Le `chain_id` est un **nom derive**, jamais une donnee du
    fichier de profil -- le format de profil, lui, ne bouge pas et garde son
    `PROFILE_SCHEMA_VERSION`. Un profil ecrit sous l'ancien identifiant devient
    simplement introuvable: c'est le cas nomme `ProfileNotFoundError` (`AC 3`,
    « projet recu sans son profil »), qui invite a regenerer, et non une faute
    ni un profil applique de travers. Aucune migration n'est ecrite: hors du
    projet de demonstration, aucun profil n'existe sous l'ancien encodage.
    """
    if not is_strict_int(declared_dpi) or declared_dpi <= 0:
        raise InvalidChainParameterError(
            f"DPI de chaine invalide: {declared_dpi!r}. Le reglage declare est "
            "un entier strictement positif; un dpi faux rendrait le chain_id "
            "stable mais attribue a la mauvaise chaine.")
    if not isinstance(scan_input_format, str) or not scan_input_format:
        raise InvalidChainParameterError(
            f"Format de scan invalide: {scan_input_format!r}. Le format est "
            "celui que l'ingestion a mesure, jamais une chaine vide.")
    segments = (str(declared_dpi), scan_input_format,
                str(make or ""), str(model or ""), str(software or ""))
    return CHAIN_MATERIAL_SEPARATOR.join(
        f"{len(segment)}{CHAIN_MATERIAL_LENGTH_DELIMITER}{segment}"
        for segment in segments)


def derive_chain_id(*, declared_dpi: int, scan_input_format: str,
                    make: str = "", model: str = "", software: str = "") -> str:
    """Deriver l'identifiant de chaine depuis les parametres reels.

    Deterministe et inter-machine (`hashlib.sha256`, jamais `hash()` Python),
    sans horodate, sans chemin absolu, sans slug operateur, sans pixels. Le
    resultat satisfait le pattern `^[A-Za-z0-9_-]+$` et
    `CANONICAL_ID_MAX_LENGTH` par construction: un prefixe lisible
    `<dpi>-<format>` normalise, puis un condensat hexadecimal.

    C'est la **seule** source de l'identite de chaine depuis la story 5.23 (AC 13,
    `EPIC5-ARB-88`): le drapeau qui permettait de la surcharger a la main a ete retire
    avec le role d'appariement du `chain_id` (`EPIC5-ARB-83`). Ce que cette fonction
    rend n'est donc plus « la valeur par defaut » mais la valeur tout court.
    """
    material = chain_material(
        declared_dpi=declared_dpi, scan_input_format=scan_input_format,
        make=make, model=model, software=software)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[
        :CHAIN_ID_HASH_LENGTH]
    prefix = naming.normalize_identifier(f"{declared_dpi}-{scan_input_format}")
    return f"{prefix}-{digest}"


def _normalise_tag(value: object) -> str:
    """Normaliser la valeur d'un tag TIFF en chaine, ou `""` si absente.

    Pillow rend un tag TIFF comme une chaine, des octets ou un tuple; sur les
    captures reelles du depot les tags sont absents (`None`). Le best effort
    est documente: une valeur illisible vaut `""`, jamais une exception qui
    ferait echouer la derive de chaine sur un fichier lisible par ailleurs.
    """
    if value is None:
        return ""
    if isinstance(value, (tuple, list)):
        return _normalise_tag(value[0] if value else None)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip()
    return str(value).strip()


def _first_tag_readable_path(source: Path) -> Path | None:
    """Le premier fichier image lisible de la source, ou `None`.

    Une source dossier est balayee dans l'ordre trie de ses entrees: l'ordre
    est stable d'une machine a l'autre, donc les tags lus le sont aussi. Une
    source fichier unique est prise telle quelle. Un PDF ou un chemin absent
    rend `None` (aucun tag a y lire).
    """
    if source.is_dir():
        candidates = sorted(
            p for p in source.iterdir()
            if p.is_file() and p.suffix.lower() in _TAG_READABLE_SUFFIXES)
        return candidates[0] if candidates else None
    if source.is_file():
        return source
    return None


def read_scan_tags(source: str | Path) -> tuple[str, str, str]:
    """Lire `(make, model, software)` d'une source de scan, en best effort.

    Best effort au sens plein: un fichier absent, un format sans tags, une
    lecture qui echoue rendent les trois chaines vides, jamais une exception.
    Les captures reelles du depot (trois TIFF `scan-WIN`, mesurage du
    2026-08-17) portent les trois tags absents -- le materiel se reduit alors
    au sous-ensemble possede (`declared_dpi` + `scan_input_format`), et le
    profil reste reutilisable, moins discriminant.
    """
    from PIL import Image

    path = _first_tag_readable_path(Path(source))
    if path is None:
        return "", "", ""
    try:
        with Image.open(path) as image:
            tags = image.tag_v2
            return (
                _normalise_tag(tags.get(TIFF_TAG_MAKE)),
                _normalise_tag(tags.get(TIFF_TAG_MODEL)),
                _normalise_tag(tags.get(TIFF_TAG_SOFTWARE)),
            )
    except Exception:
        # Best effort documente: une source illisible pour Pillow (PDF, raster
        # abime) ne doit pas empecher la derive de chaine.
        return "", "", ""


def report_scan_input_format(report) -> str:
    """Le format de fichier mesure du scan, canonise pour la chaine.

    Le rapport d'ingestion porte un `scan_input_format` **par page**
    (`scan_ingest.IngestedPage`): le format de la chaine est l'ensemble trie
    des formats mesures, rejoint par `+` -- deterministe, insensible a l'ordre
    de lecture, et distinct d'un slug operateur. Un PDF multipage et une page
    fichier TIFF ne s'y confondent pas.
    """
    formats = sorted({page.scan_input_format for page in report.pages})
    if not formats:
        raise InvalidChainParameterError(
            "Rapport de scan sans aucune page: le format de la chaine ne peut "
            "pas etre derive d'un scan vide.")
    return "+".join(formats)