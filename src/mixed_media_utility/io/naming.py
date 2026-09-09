"""Stable filename conventions for the MMU reconstruction chain.

Story 2.3 defines the minimal, deterministic naming contract that lets a
third party reconstruct project/rush/lot/page/slot associations directly from
file names on disk (see ARCHITECTURE_DETAILED.md section 5, matrice de
responsabilite des metadonnees).

`project_id` and `rush_id` are canonically capped at 48 characters before a
short, deterministic derive is required so file names stay usable across
filesystems while remaining stable and independent from the local machine
(`derive_short_id` relies only on `hashlib`, never on Python's randomized
`hash()`).
"""

from __future__ import annotations

from dataclasses import dataclass

import hashlib
import math
import re
import unicodedata


#: Longueur maximale d'un identifiant canonique (`project_id`, `rush_id`,
#: `lot_id`).
#:
#: **Revenue de 64 a 48 le 2026-08-31** (`EPIC11-ARB-110`, tranche par Egan sur
#: mesure). Elle avait ete portee a 64 le 2026-08-28 par `ff57780`, un commit
#: qui ne touche que ce fichier et un banc, qui n'a MESURE aucun QR, et dont le
#: message cite `EPIC5-ARB-106` -- un numero qui porte en realite « le vrac se
#: declenche par l'absence de `--lot-slug` », c'est-a-dire rien a voir. C'est
#: la reference perimee que la section « les politiques se MESURENT » du
#: CLAUDE.md signale deja.
#:
#: **La falaise est a 58 caracteres**, mesuree par le chemin de production
#: (`plan_page_payload` puis `encode_qr_image` et `symbol_version` sur le cote
#: du raster). Au cardinal 8 -- une planche a 8 frames, cardinal courant --
#: cinq identifiants de 58 caracteres encodent sur la **version 22** du
#: symbole, que `QR_BANNED_SYMBOL_VERSIONS` interdit parce que le detecteur de
#: production ne la decode a AUCUNE taille imprimee.
#:
#: ```
#: longueur 48 -> version 20  sain, dix caracteres sous la falaise
#: longueur 57 -> version 21  sain, dernier palier
#: longueur 58 -> version 22  BANNIE
#: longueur 64 -> version 22  BANNIE      <- la borne d'avant
#: ```
#:
#: 48 est donc retenue plutot que 57 : la falaise exacte ne laisserait AUCUNE
#: marge, et le prochain champ ajoute au payload reconduirait le defaut a
#: l'identique. Une frontiere de banc mesure cette marge
#: (`tests/unit/test_page_payload.py`).
CANONICAL_ID_MAX_LENGTH = 48

#: Longueur maximale TOLEREE A LA LECTURE d'un identifiant deja ecrit.
#:
#: `EPIC11-ARB-110` a ramene la borne de CREATION de 64 a 48 le 2026-08-31, sur
#: la mesure de la falaise QR. Mais la borne a valu 64 du 2026-08-28 au
#: 2026-08-31, et **des identifiants de 49 a 64 caracteres ont pu etre ecrits
#: pendant ces trois jours -- puis IMPRIMES dans le QR de planches papier**
#: (trouve en revue, couche 2, vague 3). Appliquer la borne de creation a la
#: lecture rendrait ces planches irrescannables, sans nommer d'issue : une
#: regression silencieuse sur des feuilles qu'aucun calcul ne refait.
#:
#: La tolerance est donc EXACTEMENT l'ensemble des identifiants que l'outil a
#: pu produire, et pas un caractere de plus. Elle ne s'applique qu'a la
#: LECTURE : `build_lot_id` et les autres constructeurs refusent toujours au
#: dela de `CANONICAL_ID_MAX_LENGTH`, sans quoi la falaise QR se rouvrirait.
LEGACY_ID_MAX_LENGTH = 64
SHORT_DERIVE_HASH_LENGTH = 8

#: Longueur du condensat de bornes ajoute a l'identite d'un lot borne
#: (story 3.7). Fixe, hexadecimal, donc conforme par construction au pattern
#: `^[A-Za-z0-9_-]+$` du schema v2 quelle que soit la forme des timecodes.
BOUNDS_SUFFIX_LENGTH = 8

#: Extension du fichier des frames extraites par `extract` (story 3.1).
EXTRACTED_FRAME_SUFFIX = ".tiff"

_INVALID_TIMECODE_PATTERN = re.compile(r"[\\/]")

# Pattern impose aux identifiants par `mixed_media_utility/specs/project.schema.json`
# (`project_id`, `rushes[].rush_id`, `lots[].lot_id`). Un `lot_id` qui ne le
# satisfait pas ferait echouer `validate_manifest` apres une extraction
# potentiellement longue: la garde vit donc ici, au point de construction.
_MANIFEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class NamingError(ValueError):
    """Raised when a naming helper receives an invalid input."""


def derive_short_id(value: str, max_length: int = CANONICAL_ID_MAX_LENGTH) -> str:
    """Return `value` unchanged, or a deterministic short derive if too long.

    The derive keeps a readable prefix of `value` plus a stable hash suffix,
    computed with `hashlib.sha256` so the result is identical regardless of
    the machine or Python process running it (unlike the built-in, randomized
    `hash()`).
    """
    if not value:
        raise NamingError("Cannot derive a short id from an empty value")
    if len(value) <= max_length:
        return value

    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:SHORT_DERIVE_HASH_LENGTH]
    prefix_length = max_length - SHORT_DERIVE_HASH_LENGTH - 1
    if prefix_length < 1:
        raise NamingError(f"max_length {max_length} is too small to fit a short derive")
    prefix = value[:prefix_length]
    return f"{prefix}-{digest}"


#: Caracteres a remplacer pour satisfaire `_MANIFEST_ID_PATTERN`.
_IDENTIFIER_FORBIDDEN_PATTERN = re.compile(r"[^A-Za-z0-9_-]+")
_IDENTIFIER_DASH_RUN_PATTERN = re.compile(r"-{2,}")


def normalize_identifier(value: str, *, label: str = "valeur") -> str:
    """Return a schema-conformant identifier derived from any human name.

    Helper **generique** `nom quelconque -> identifiant`, volontairement pas
    specifique au rush: la story 3.1 l'appelle sur le nom du fichier source
    pour `rush_id`, la story 3.4 sur le nom du dossier projet pour
    `project_id`. Un helper nomme et code « rush » obligerait la seconde a en
    redevelopper un second (`decisions-2026-08-02.md`, decision 2: une seule
    implementation par convention).

    Chaine de traitement, deterministe et identique sur Windows, macOS et
    Linux (risque R2):

    1. decomposition Unicode NFKD puis retrait des marques combinantes, de
       sorte que `Cafe` accentue rende `Cafe` plutot qu'une suite de
       caracteres interdits;
    2. remplacement de toute suite de caracteres hors `[A-Za-z0-9_-]` par un
       tiret unique;
    3. reduction des tirets consecutifs et retrait des tirets de bordure;
    4. raccourcissement par `derive_short_id` au-dela de
       `CANONICAL_ID_MAX_LENGTH`.

    L'ordre des etapes 1-3 avant l'etape 4 n'est pas negociable:
    `derive_short_id` recopie son prefixe **verbatim**, donc normaliser apres
    elle laisserait passer des caracteres interdits par le pattern
    `^[A-Za-z0-9_-]+$` du schema v2.

    Raises `NamingError` when the normalization yields an empty string (a name
    made only of forbidden characters, e.g. `###`), rather than calling
    `derive_short_id("")` which would raise a message mentioning an empty
    value the caller never supplied.
    """
    if value is None:
        raise NamingError(f"Impossible de normaliser {label}: valeur absente")

    text = str(value)
    decomposed = unicodedata.normalize("NFKD", text)
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    replaced = _IDENTIFIER_FORBIDDEN_PATTERN.sub("-", without_marks)
    collapsed = _IDENTIFIER_DASH_RUN_PATTERN.sub("-", replaced)
    trimmed = collapsed.strip("-")

    if not trimmed:
        raise NamingError(
            f"Impossible de deriver un identifiant depuis {label} {text!r}: apres "
            "normalisation il ne reste aucun caractere autorise. Le schema v2 impose "
            "le pattern ^[A-Za-z0-9_-]+$ (lettres ASCII, chiffres, tiret, souligne). "
            "Renommer la source avec au moins un caractere alphanumerique ASCII."
        )

    identifier = derive_short_id(trimmed)
    if not _MANIFEST_ID_PATTERN.match(identifier):
        # Defense en profondeur: inatteignable tant que les etapes ci-dessus
        # precedent `derive_short_id`, mais un reordonnancement du code le
        # rendrait atteignable en silence.
        raise NamingError(
            f"Identifiant normalise non conforme au schema v2: {identifier!r} "
            f"(depuis {label} {text!r})"
        )
    return identifier


def validate_manifest_identifier(
    value: str, *, label: str = "valeur",
    longueur_max: int = CANONICAL_ID_MAX_LENGTH,
) -> str:
    """Valider qu'un identifiant est conforme au contrat du manifest v2.

    Implementation unique de la regle « identifiant canonique » cote lecture
    (revue 4.5): pattern ``^[A-Za-z0-9_-]+$`` du schema v2 et longueur
    maximale ``CANONICAL_ID_MAX_LENGTH``. C'est **strictement** le contrat du
    schema — pas le point fixe de ``normalize_identifier``, qui est plus
    severe (il reduit les suites de tirets et retire les tirets de bordure)
    et refusait des identifiants legitimes du depot: ``derive_short_id``
    recopie son prefixe verbatim, donc ``build_lot_id`` peut produire un
    ``lot_id`` en ``...--<hash>`` parfaitement valide au schema mais non
    point-fixe. Verifier ici, jamais transformer.
    """
    if not isinstance(value, str) or not value:
        raise NamingError(f"{label} doit etre une chaine non vide, recu {value!r}")
    if len(value) > longueur_max:
        raise NamingError(
            f"{label} depasse la longueur canonique maximale de "
            f"{longueur_max} caracteres: {value!r} ({len(value)}). "
            "Un identifiant du manifest passe par derive_short_id des sa "
            "creation et ne peut pas etre plus long."
        )
    if not _MANIFEST_ID_PATTERN.fullmatch(value):
        raise NamingError(
            f"{label} non conforme au pattern ^[A-Za-z0-9_-]+$ du schema v2: "
            f"{value!r}. Passer la valeur canonique du manifest, jamais un nom "
            "humain brut (espaces, accents...)."
        )
    return value


#: Forme canonique d'un timecode de selection (story 3.2): ``hh:mm:ss:ff``.
#: La forme assainie ``hh-mm-ss-ff`` n'existe que dans les noms de fichiers.
_SELECTION_TIMECODE_PATTERN = re.compile(r"^\d{2}:\d{2}:\d{2}:\d{2}$")


def validate_frame_timecode(value: str, *, label: str = "frame_timecode") -> str:
    """Valider qu'un timecode porte la forme canonique de la selection 3.2.

    Point unique de cette regle (revue 4.5): un payload QR portant la forme
    fichier ``hh-mm-ss-ff`` casserait le recoupement QR <-> nom de fichier
    sans aucune erreur — exactement le filet de securite 4.6. Verification
    seule, aucune transformation: la conversion vers la forme fichier vit
    dans ``sanitize_timecode`` au moment du nommage.
    """
    if not isinstance(value, str) or not value:
        raise NamingError(f"{label} doit etre une chaine non vide, recu {value!r}")
    if not _SELECTION_TIMECODE_PATTERN.fullmatch(value):
        raise NamingError(
            f"{label} ne porte pas la forme canonique hh:mm:ss:ff de la "
            f"selection (story 3.2): {value!r}. La forme assainie hh-mm-ss-ff "
            "des noms de fichiers ne doit jamais entrer dans un payload."
        )
    return value


def format_fps_short(fps: float) -> str:
    """Return a compact, filename-safe short form for an fps value.

    Integral fps values (e.g. `24.0`) are rendered as `"24"`. Fractional
    values (e.g. `23.976`) keep their decimal part with the dot replaced by
    `"p"` (e.g. `"23p976"`).

    A non-finite fps (`inf`, `nan`) is refused with `NamingError` instead of
    letting `int()` raise a bare `OverflowError`/`ValueError`: no caller has a
    meaning for it and CLI entry points map `NamingError` to an actionable
    exit code (revue 4.1 du 2026-08-06).
    """
    if not math.isfinite(fps):
        raise NamingError(
            f"Cadence invalide pour un identifiant de lot: {fps!r}. La cadence "
            "doit etre un nombre fini (ex. 5, 12.5, 23.976)."
        )
    if fps == int(fps):
        return str(int(fps))
    text = f"{fps}".rstrip("0").rstrip(".")
    return text.replace(".", "p")


def sanitize_timecode(timecode: str) -> str:
    """Return a filename-safe timecode, replacing `:`/`;` separators with `-`.

    Raises `NamingError` if the result would still contain a path separator.
    """
    if not timecode:
        raise NamingError("Cannot sanitize an empty timecode")
    sanitized = timecode.replace(":", "-").replace(";", "-")
    if _INVALID_TIMECODE_PATTERN.search(sanitized):
        raise NamingError(f"Invalid timecode '{timecode}': path separators are not allowed")
    return sanitized


def bounds_suffix(
    source_in_timecode: str | None, source_out_timecode: str | None
) -> str | None:
    """Condensat identifiant une fenetre d'extraction bornee (story 3.7).

    Rend `None` quand aucune borne n'est fournie: un lot non borne garde
    exactement l'identite et le nom de dossier qu'il avait avant cette story,
    et reste indiscernable d'un lot d'avant (AC 14).

    **Un vrai condensat, jamais `derive_short_id`.** Cette derniere rend son
    entree *inchangee* sous `CANONICAL_ID_MAX_LENGTH` caracteres: ce n'est pas
    un hacheur mais un raccourcisseur conditionnel. Lui passer
    `rush-001_3_15:34:30:00_15:34:50:00` (34 caracteres) rendrait la chaine
    brute, deux-points compris, que `build_lot_id` refuserait ensuite via
    `_MANIFEST_ID_PATTERN` -- et seulement sur un nom de rush court, donc un
    defaut dependant des donnees, invisible a un test par echantillonnage.

    Le separateur `|` n'est pas decoratif: sans lui, `("15:34:30:00", None)` et
    `(None, "15:34:30:00")` condenseraient la meme chaine, alors que ce sont
    deux extraits differents (l'un part de la borne, l'autre s'y arrete).
    """
    if source_in_timecode is None and source_out_timecode is None:
        return None
    material = f"{source_in_timecode or ''}|{source_out_timecode or ''}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:BOUNDS_SUFFIX_LENGTH]


def valider_nom_court_de_cadence(nom_court: str) -> str:
    """Rend `nom_court` s'il peut nommer une cadence dans un identifiant.

    Ajout de la story 11.4, lot P (`EPIC11-ARB-62`). Le nom court d'une cadence
    est **calcule ailleurs** -- la ou la cadence est encore une `Fraction`
    exacte, c'est-a-dire `tui/cadences.nom_court_de_cadence` -- et il arrive ici
    deja ecrit. Cette fonction ne le fabrique pas, elle **refuse** ce qui ne peut
    pas entrer dans un identifiant de lot.

    Le refus est nomme et il arrive **a l'entree** : un nom court fautif qui
    passerait cette garde produirait un `lot_id` que `validate_manifest`
    rejetterait apres une extraction potentiellement longue, ce qui est
    exactement le motif pour lequel `_MANIFEST_ID_PATTERN` vit deja dans ce
    module.
    """
    if not nom_court:
        raise NamingError(
            "Nom court de cadence vide: un identifiant de lot ne peut pas etre "
            "construit sans fragment de cadence."
        )
    # **`fullmatch`, jamais `match`** (revue de la vague 3, couche 1, finding
    # `T2`). Le motif est ancre `^...$`, et en Python `$` accepte **un saut de
    # ligne final** : `.match()` laissait donc passer `'25s3\n'`, d'ou un
    # `lot_id` et surtout un COMPOSANT DE CHEMIN porteurs d'un `\n`. La ligne
    # 157 de ce meme module emploie `fullmatch` sur le meme motif depuis
    # toujours -- c'est cette asymetrie-la qui etait le defaut.
    if not _MANIFEST_ID_PATTERN.fullmatch(nom_court):
        raise NamingError(
            f"Nom court de cadence invalide: {nom_court!r}. Seuls [A-Za-z0-9_-] "
            "sont acceptes par le schema v2 du manifest (la convention "
            "`EPIC11-ARB-62` ecrit `25s3`, le `s` tenant la place de la barre)."
        )
    return nom_court


#: Bornes du rang de version d'un lot (story 5.29, `EPIC11-ARB-89`). Le rang 1
#: est le lot d'origine et ne porte **aucun** fragment -- seuls les rangs 2 et
#: au-dela recoivent `_v<rang>`. `EPIC11-ARB-88` (verbatim d'Egan) tranche pour
#: la forme sans zero de tete: `_v2` ... `_v99`, jamais `_v02`.
VERSION_RANK_MIN = 2
VERSION_RANK_MAX = 99


def format_version_suffix(version_rank: int) -> str:
    """Rend le fragment `_v<rang>` d'un identifiant de lot versionne.

    Cinquieme axe de nommage optionnel, au meme niveau que le suffixe de
    bornes (`bounds_suffix`) et le nom court de cadence
    (`valider_nom_court_de_cadence`): **calcule une fois ici**, transporte tel
    quel par `build_lot_id` et `project_layout.rush_dir_slug` (ARB-3 --
    identifiant de lot et nom de dossier ne divergent jamais).

    `version_rank` hors de `[VERSION_RANK_MIN, VERSION_RANK_MAX]` est refuse
    nommement: en dessous de 2, ce n'est pas une version (le lot d'origine
    n'a pas de fragment) ; au-dela de 99, le fragment gagnerait un troisieme
    chiffre et romprait la promesse de largeur fixe que le budget de
    `CANONICAL_ID_MAX_LENGTH` suppose deja acquise.
    """
    if not isinstance(version_rank, int) or isinstance(version_rank, bool):
        raise NamingError(
            f"Rang de version invalide: {version_rank!r} (un entier est attendu)."
        )
    if not (VERSION_RANK_MIN <= version_rank <= VERSION_RANK_MAX):
        raise NamingError(
            f"Rang de version hors bornes: {version_rank!r}. Attendu entre "
            f"{VERSION_RANK_MIN} et {VERSION_RANK_MAX} inclus (le rang 1 est le lot "
            "d'origine, qui ne porte aucun fragment de version)."
        )
    return f"_v{version_rank}"


#: Le fragment de version, reconnu **en fin de nom** et seulement la. La tige
#: est exigee non vide (`.+`) : `_v2` tout seul n'est pas un nom versionne,
#: c'est un fragment orphelin. Le premier chiffre est pris dans `[1-9]`, ce qui
#: refuse les zeros de tete d'un seul coup (`EPIC11-ARB-88` : `_v2` ... `_v99`,
#: jamais `_v02`).
_FRAGMENT_DE_VERSION = re.compile(r"^.+_v([1-9][0-9]*)$")


def rang_du_fragment_de_version(nom: str) -> int:
    """Rendre le rang de version que porte un nom -- l'inverse de la fabrique.

    C'est l'inverse exact de :func:`format_version_suffix`, et il vit **a cote
    d'elle** pour la meme raison que la regle des rangs vit une seule fois dans
    `io.version_ranks` : la forme `_v<rang>` est une convention, et une
    convention relue ailleurs qu'a l'endroit ou elle est ecrite finit par en
    devenir une seconde.

    Un nom **sans** fragment rend **1** : le rang d'origine ne porte aucun
    fragment, son absence le dit, et `format_version_suffix` refuse nommement
    de l'ecrire. Tout ce qui *ressemble* a un fragment sans en etre un --
    `_v1` (jamais ecrit), `_v0` et `_v100` (hors des bornes), `_v02` (zero de
    tete), `_vx` -- rend **1** lui aussi : ce n'est pas un rang, donc c'est le
    nom d'une origine dont la tige se termine ainsi, et non une erreur.

    **Ce module n'est pas le seul a connaitre cette forme, et le dire vaut
    mieux que le taire** : `scan_ingest` porte sa propre expression sur le meme
    fragment, pour un role different -- elle le **reserve** dans un slug
    d'ingestion, afin qu'un dossier ne soit pas a la fois un scan a part
    entiere et la version d'un autre. La rapatrier ici est un refactor qui
    appartient a la story qui touchera `scan_ingest`.
    """
    fragment = _FRAGMENT_DE_VERSION.match(str(nom))
    if fragment is None:
        return 1
    rang = int(fragment.group(1))
    if not (VERSION_RANK_MIN <= rang <= VERSION_RANK_MAX):
        return 1
    return rang


#: Largeur maximale du fragment de DESAMBIGUISATION, tiret compris : `-99`.
#:
#: Calculee, jamais ecrite en dur : elle suit `VERSION_RANK_MAX`, de sorte
#: qu'un jour ou la borne des rangs bougerait, la tige se raccourcirait
#: d'autant sans qu'on ait a y penser.
LARGEUR_MAX_FRAGMENT_DESAMBIGUISATION = 1 + len(str(VERSION_RANK_MAX))

#: Le fragment de desambiguisation, reconnu **en fin de nom** et seulement la.
#: Meme forme que `_FRAGMENT_DE_VERSION`, au separateur pres : la tige est
#: exigee non vide (`.+`) et le premier chiffre est pris dans `[1-9]`, ce qui
#: refuse les zeros de tete.
_FRAGMENT_DE_DESAMBIGUISATION = re.compile(r"^(.+)-([1-9][0-9]*)$")


def tige_de_desambiguisation(rush_id: str) -> str:
    """La TIGE sur laquelle le fragment de desambiguisation se pose.

    C'est `rush_id` lui-meme dans le cas courant, et un raccourci deterministe
    au-dela de `CANONICAL_ID_MAX_LENGTH - LARGEUR_MAX_FRAGMENT_DESAMBIGUISATION`
    caracteres.

    **Pourquoi raccourcir ICI plutot que de laisser `normalize_identifier` le
    faire apres coup**, et c'est un defaut mesure sur le code d'avant : cette
    derniere raccourcit la chaine ENTIERE, fragment compris, en recopiant un
    prefixe verbatim suivi d'un condensat -- donc le fragment DISPARAIT du nom
    ecrit. Sur un `rush_id` de 48 caracteres, deux forcages successifs
    calculaient alors le meme rang (le nom ecrit n'etant plus reconnaissable
    comme membre de la famille) et le rendaient sous le meme condensat : deux
    rushes distincts sous le meme identifiant. Raccourcir la tige d'abord, a
    largeur FIXE et independamment du rang, fait tenir tous les rangs de la
    famille sous la meme tige -- ce qui est exactement ce que
    :func:`rang_de_desambiguisation` doit pouvoir relire.

    **La tige est rendue DEJA CONFORME, et ce n'est pas une coquetterie.**
    `derive_short_id` recopie son prefixe **verbatim** : si `rush_id` porte un
    tiret a l'indice ou la coupe tombe, la tige gagne un DOUBLE tiret. Le nom
    complet repasse ensuite par `normalize_identifier`
    (:func:`extraction.disambiguated_rush_id`), qui **recolle** toute suite de
    tirets en un seul -- le nom ecrit cesse alors d'etre `<tige>-<rang>`,
    :func:`rang_de_desambiguisation` rend `None`, le rang n'est jamais compte
    employe, et **tous les homonymes suivants recoivent le rang 2**.

    Mesure du 2026-09-05, couche 2 de la revue de la 11.4e, sur un nom de
    fichier entierement naturel (`Tournage exterieur prise 001 camera A bis
    final.mov`, 47 caracteres, tiret a l'indice 35) : trois declarations, trois
    succes annonces, et **deux** entrees au manifeste -- la deuxieme ecrasee en
    silence, `build_rush_declaration_manifest` fusionnant en place par
    `rush_id`. C'est l'ecrasement destructif silencieux qu'`EPIC11-ARB-89` et
    `EPIC11-ARB-104` interdisent nommement, et c'est mot pour mot le defaut que
    le paragraphe ci-dessus declare fermer -- rouvert un appel plus loin.

    Le recollement se fait donc **ici**, sur la tige seule, avant que le rang
    ne soit pose. Il reste deterministe (fonction du seul `rush_id`), donc tous
    les rangs d'une meme famille partagent toujours la meme tige, et le
    `normalize_identifier` de l'appelant devient un no-op sur ce nom.
    """
    return _IDENTIFIER_DASH_RUN_PATTERN.sub(
        "-",
        derive_short_id(
            rush_id,
            CANONICAL_ID_MAX_LENGTH - LARGEUR_MAX_FRAGMENT_DESAMBIGUISATION,
        ),
    )


def format_rang_de_desambiguisation(rush_id: str, rang: int) -> str:
    """Rendre l'identifiant desambigue `<tige>-<rang>` (`EPIC11-ARB-233`).

    Sixieme axe de nommage, et le seul qui ne designe pas une VERSION : deux
    rushes homonymes ne sont pas deux etats d'un meme objet, ce sont deux
    objets. Le rang n'y numerote donc pas une version mais une **occurrence**
    -- ce qui est precisement pourquoi la forme est `-<rang>` et non le
    `_v<rang>` de :func:`format_version_suffix`. Ecrire `prise01_v2` dirait
    « deuxieme version de prise01 », ce qui est faux.

    Ce que la forme partage avec les versions, en revanche, c'est la **regle**
    : le rang se consomme et ne se rend qu'en queue (`io.version_ranks`,
    `EPIC11-ARB-108` -- il n'y a pas de mecanisme different par objet). Cette
    fonction n'en calcule rien ; elle met en forme le rang qu'on lui donne.

    Les bornes sont celles des rangs (`VERSION_RANK_MIN`..`VERSION_RANK_MAX`) :
    en dessous de 2 ce n'est pas une occurrence supplementaire (le premier rush
    ne porte aucun fragment, son absence le dit), au-dela de 99 le fragment
    gagnerait un chiffre et la tige raccourcie ne lui ferait plus de place.
    """
    if not isinstance(rang, int) or isinstance(rang, bool):
        raise NamingError(
            f"Rang de desambiguisation invalide: {rang!r} (un entier est attendu)."
        )
    if not (VERSION_RANK_MIN <= rang <= VERSION_RANK_MAX):
        raise NamingError(
            f"Rang de desambiguisation hors bornes: {rang!r}. Attendu entre "
            f"{VERSION_RANK_MIN} et {VERSION_RANK_MAX} inclus (le premier rush "
            "d'une famille d'homonymes ne porte aucun fragment)."
        )
    return f"{tige_de_desambiguisation(rush_id)}-{rang}"


def rang_de_desambiguisation(nom: str, tige: str) -> int | None:
    """Le rang que `nom` occupe dans la famille de `tige` -- l'inverse exact.

    Rend :

    * ``1`` quand `nom` EST la tige : le premier rush ne porte aucun fragment,
      et c'est ainsi que `io.version_ranks.RANG_ORIGINE` s'ecrit -- par
      omission ;
    * le rang quand `nom` vaut ``<tige raccourcie>-<rang>`` avec un rang dans
      les bornes ;
    * ``None`` quand `nom` n'appartient pas a cette famille -- y compris pour
      tout ce qui *ressemble* a un fragment sans en etre un (`-0`, `-100`,
      `-02`, `-hd`). Un `prise01-hd` ecrit avant `EPIC11-ARB-233` est donc un
      etranger a la famille, ce qui est exact : il occupe son nom et aucun
      rang, et le prochain forcage rendra `prise01-2`, libre.

    Vit **a cote** de la fabrique pour la meme raison que
    :func:`rang_du_fragment_de_version` : une convention relue ailleurs qu'a
    l'endroit ou elle est ecrite finit par en devenir une seconde.
    """
    texte = str(nom)
    racine = tige_de_desambiguisation(str(tige))
    if texte == str(tige) or texte == racine:
        return 1
    fragment = _FRAGMENT_DE_DESAMBIGUISATION.match(texte)
    if fragment is None or fragment.group(1) != racine:
        return None
    rang = int(fragment.group(2))
    if not (VERSION_RANK_MIN <= rang <= VERSION_RANK_MAX):
        return None
    return rang


def build_lot_id(
    rush_id: str,
    fps_target: float | int,
    *,
    source_in_timecode: str | None = None,
    source_out_timecode: str | None = None,
    fps_short_name: str | None = None,
    version_rank: int | None = None,
) -> str:
    """Return the canonical `lot_id` for `rush_id` extracted at `fps_target`.

    Convention de la story 3.4 (son AC 5), **implementation unique** du depot:
    `derive_short_id(f"{rush_id}_{format_fps_short(fps_target)}")`. La story 3.1
    l'appelle pour remplir son objet de resultat, la story 3.4 pour le
    controler; la garde `LotIdentityMismatchError` de 3.4 n'a de valeur que si
    les deux cotes appellent cette fonction et non deux copies
    (`decisions-2026-08-02.md`, decision 2).

    Deterministe et inter-machine: `derive_short_id` s'appuie sur
    `hashlib.sha256`, jamais sur le `hash()` randomise de Python.

    Le fragment de cadence passe par `format_fps_short`, donc `12.5` rend
    `12p5` et jamais `12.5`: un point violerait le pattern
    `^[A-Za-z0-9_-]+$` que le schema v2 impose a `lots[].lot_id`. C'est la
    meme fonction que celle utilisee par `project_layout.rush_dir_slug`
    depuis l'arbitrage ARB-3 du 2026-08-03, donc le nom de dossier de lot et
    l'identifiant de lot ne peuvent plus diverger.

    Depuis la story 3.7, une extraction bornee par timecodes ajoute un
    condensat de bornes (`bounds_suffix`), le **meme fragment** que celui que
    `project_layout.rush_dir_slug` ajoute de son cote (ARB-3): `rush-001_3`
    pour une extraction complete, `rush-001_3-a1b2c3d4` pour un extrait. Sans
    lui, deux extraits distincts du meme rush a la meme cadence porteraient le
    meme identifiant et pointeraient vers le meme dossier, donc le second
    ecraserait le premier.

    Depuis la story 5.29 (`EPIC11-ARB-89`), un cinquieme axe optionnel:
    `version_rank`, place **apres** le suffixe de bornes et compose par
    `format_version_suffix` -- `rush-001_3_v2` pour la seconde version d'une
    extraction complete, `rush-001_3-a1b2c3d4_v2` pour la seconde version d'un
    extrait borne. Absent (defaut), le comportement est inchange au caractere
    pres: c'est le lot de rang 1, qui ne porte aucun fragment.

    Raises `NamingError` when the result would not satisfy the schema pattern
    (e.g. a `rush_id` carrying a space, or an fps value rendered as a ratio).
    """
    if not rush_id:
        raise NamingError("Cannot build a lot id from an empty rush_id")
    suffix = bounds_suffix(source_in_timecode, source_out_timecode)
    # `fps_short_name` absent, c'est le chemin d'avant la story 11.4 et il est
    # inchange au caractere pres: tout appelant qui ne passe pas de nom court
    # obtient exactement le nom qu'il obtenait.
    if fps_short_name is None:
        fragment = format_fps_short(fps_target)
    else:
        fragment = valider_nom_court_de_cadence(fps_short_name)
    if suffix is not None:
        fragment = f"{fragment}-{suffix}"
    if version_rank is not None:
        fragment = f"{fragment}{format_version_suffix(version_rank)}"

    complet = f"{rush_id}_{fragment}"
    # Revue du 2026-08-06. `derive_short_id` raccourcit au-dela de
    # CANONICAL_ID_MAX_LENGTH, `project_layout.rush_dir_slug` non: passe ce
    # seuil, l'identifiant de lot et le nom de dossier divergent, et ARB-3
    # interdit cette divergence. Le condensat de bornes ajoute neuf
    # caracteres, ce qui abaissait le seuil de 47 a 38 -- donc a portee d'un
    # nom de fichier de camera ordinaire, mesure a la revue sur
    # `A005_C012_20260806_TOURNAGE_PLATEAU_PRISE_04` (44 caracteres): lot
    # `...PRI-b7677409` contre dossier `...PRISE_04_5-8c3c0d14`, l'identifiant
    # ayant au passage perdu jusqu'au fragment de cadence.
    #
    # Arbitrage d'Egan a la revue (option c): **refuser a l'entree** plutot que
    # de raccourcir aussi le dossier (qui rendrait illisibles les dossiers de
    # tous les rushs a nom long, y compris non bornes) ou d'ecourter le
    # condensat (qui repousserait le seuil sans le supprimer, en affaiblissant
    # la protection contre les collisions). L'operateur apprend le probleme au
    # moment ou il peut encore renommer son fichier.
    #
    # Le refus ne vise **que** les extractions bornees: le seuil du chemin non
    # borne (47 caracteres) preexiste a la story 3.7, et le durcir ici
    # changerait le comportement d'extractions deja livrees.
    if suffix is not None and len(complet) > CANONICAL_ID_MAX_LENGTH:
        marge = CANONICAL_ID_MAX_LENGTH - len(fragment) - 1
        raise NamingError(
            f"Nom de rush trop long pour une extraction bornee: {rush_id!r} fait "
            f"{len(rush_id)} caracteres, or une extraction bornee n'en accepte que "
            f"{marge} au plus (le condensat de bornes en occupe "
            f"{BOUNDS_SUFFIX_LENGTH + 1}, et l'identifiant de lot est plafonne a "
            f"{CANONICAL_ID_MAX_LENGTH}). Au-dela, l'identifiant du lot serait "
            "raccourci alors que le nom de son dossier ne le serait pas, et les "
            "deux se contrediraient dans le manifest. Deux issues: renommer le "
            "fichier source plus court, ou extraire le rush entier (sans --in ni "
            "--out), qui n'a pas cette limite."
        )

    # Story 11.4, lot P. Un nom court fourni ne se fait **jamais** tronquer:
    # `derive_short_id` remplacerait sa queue par un condensat, donc `25s3`
    # deviendrait illisible juste au moment ou il etait cense dire « une image
    # sur trois ». Le refus est nomme, comme celui de l'extraction bornee
    # ci-dessus et pour la meme raison: l'operateur apprend le probleme quand il
    # peut encore renommer son fichier. La garde ne vise **que** le chemin du
    # nom court: le seuil du chemin ordinaire (raccourcissement silencieux)
    # preexiste et le durcir changerait le nom d'extractions deja livrees.
    if fps_short_name is not None and len(complet) > CANONICAL_ID_MAX_LENGTH:
        marge = CANONICAL_ID_MAX_LENGTH - len(fragment) - 1
        raise NamingError(
            f"Nom de rush trop long pour la cadence {fps_short_name!r}: "
            f"{rush_id!r} fait {len(rush_id)} caracteres, or cette cadence n'en "
            f"accepte que {marge} au plus (l'identifiant de lot est plafonne a "
            f"{CANONICAL_ID_MAX_LENGTH}). Au-dela, le fragment de cadence serait "
            "remplace par un condensat et le nom ne dirait plus quelle cadence a "
            "ete extraite. Deux issues: renommer le fichier source plus court, "
            "ou choisir une cadence au nom plus court."
        )

    # Story 5.29 (`EPIC11-ARB-89`), meme raisonnement que les deux refus
    # ci-dessus, applique au cinquieme axe: `derive_short_id` tronquerait le
    # fragment de version par un condensat, si bien qu'une "nouvelle version"
    # perdrait jusqu'a son propre numero -- exactement ce que l'operatrice
    # demandait de lire. Le refus ne vise **que** le chemin versionne: un lot
    # de rang 1 (`version_rank is None`) garde le seuil et le comportement
    # d'avant cette story.
    if version_rank is not None and len(complet) > CANONICAL_ID_MAX_LENGTH:
        marge = CANONICAL_ID_MAX_LENGTH - len(fragment) - 1
        raise NamingError(
            f"Nom de rush trop long pour une nouvelle version (rang {version_rank}): "
            f"{rush_id!r} fait {len(rush_id)} caracteres, or cette combinaison n'en "
            f"accepte que {marge} au plus (l'identifiant de lot est plafonne a "
            f"{CANONICAL_ID_MAX_LENGTH}). Au-dela, l'identifiant de la nouvelle "
            "version serait raccourci par un condensat et pourrait perdre jusqu'a "
            "son propre numero de version. Deux issues: renommer le fichier source "
            "plus court, ou ecraser sciemment la version existante plutot que d'en "
            "creer une nouvelle."
        )

    lot_id = derive_short_id(complet)
    if not _MANIFEST_ID_PATTERN.match(lot_id):
        raise NamingError(
            f"Invalid lot id '{lot_id}': only [A-Za-z0-9_-] are allowed by the v2 "
            f"manifest schema (rush_id={rush_id!r}, fps_target={fps_target!r})"
        )
    return lot_id


def build_extracted_frame_filename(
    rush_id: str,
    fps_target: float | int,
    frame_timecode: str,
    suffix: str = EXTRACTED_FRAME_SUFFIX,
    *,
    fps_short_name: str | None = None,
) -> str:
    """Return the file name of one frame extracted by `extract` (story 3.1).

    Layout: `<rush>_<fps-court>_<timecode-assaini>.tiff`, par exemple
    `rush-001_12p5_00-00-00-00.tiff`. Il s'aligne exactement sur le slug de
    dossier de `project_layout.rush_dir_slug`, puisque les deux consomment
    `format_fps_short`.

    **Appartenance**: ce helper appartient au contrat de la story 3.1 (nommage
    des frames extraites). Il est ajoute ici par la story 3.4 pour une raison
    de sequencement et d'une seule: son AC 15 exige que
    `io/extraction_manifest.verify_extracted_lot` controle les noms de fichiers
    en **appelant** la convention plutot qu'en la reimplementant, et 3.4 est
    developpee avant 3.1. La story 3.1 le **consomme** au lieu de le recreer
    (`decisions-2026-08-02.md`, decision 2: une seule implementation).

    A ne pas confondre avec `build_frame_filename`, qui est la convention de la
    chaine PDF/scan (story 2.3) et exige un `page_index` inexistant a
    l'extraction. `build_frame_filename` reste strictement inchangee.

    Depuis la story 11.4 (lot P, `EPIC11-ARB-62`), le mot-cle optionnel
    `fps_short_name` remplace le fragment de cadence par le nom court **deja
    calcule** la ou la cadence etait encore une `Fraction` exacte
    (`tui.cadences.nom_court_de_cadence`) : `..._25s3_00-00-00-00.tiff` au lieu
    de `..._8p333333333333334_00-00-00-00.tiff`. C'est le meme mot-cle, de meme
    forme et de meme defaut, que celui de `build_lot_id` et de
    `project_layout.rush_dir_slug` : les trois fragments d'un meme lot --
    l'identifiant, le nom de dossier et le nom de fichier -- viennent du meme
    nom court ou d'aucun, jamais d'un melange des deux. Un lot dont le dossier
    dirait `25s3` et les fichiers `8p333333333333334` echouerait a
    `extraction.check_fps_form_consistency`, qui existe pour cette raison.
    """
    if not rush_id:
        raise NamingError("Cannot build an extracted frame filename from an empty rush_id")
    short_rush_id = derive_short_id(rush_id)
    # Meme dispatch, meme garde et meme defaut que `build_lot_id` : hors du nom
    # court, le chemin d'avant est repris au caractere pres.
    if fps_short_name is None:
        fps_short = format_fps_short(fps_target)
    else:
        fps_short = valider_nom_court_de_cadence(fps_short_name)
    sanitized_timecode = sanitize_timecode(frame_timecode)
    return f"{short_rush_id}_{fps_short}_{sanitized_timecode}{suffix}"


#: Timecode assaini tel que `sanitize_timecode` le produit: `hh-mm-ss-ff`.
#:
#: `[0-9]` explicite, jamais `\d`: en Python `\d` est **Unicode** par defaut, si
#: bien qu'un nom dont le dernier chiffre est un chiffre arabo-indien (U+0660)
#: etait relu et declare conforme, aller-retour complet (revue 5.6 du
#: 2026-08-08). Le
#: nom de fichier est le seul support d'identite d'une frame qui voyage seule:
#: un caractere qu'aucun systeme de destination ne rend de la meme facon n'y a
#: pas sa place. La constante est partagee par les deux lecteurs
#: (`read_extracted_frame_timecode` et `read_scan_frame_timecode`), et le
#: durcissement ne fait que **retirer** des noms non ASCII du domaine accepte.
_SANITIZED_TIMECODE_PATTERN = re.compile(r"^[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{2}$")


def read_extracted_frame_timecode(
    name: str, suffix: str = EXTRACTED_FRAME_SUFFIX
) -> str:
    """Rendre le timecode porte par un nom de frame extraite, ou echouer.

    Inverse de `build_extracted_frame_filename`, et **seul** endroit ou la
    forme `<rush>_<fps-court>_<timecode-assaini>.tiff` est relue. Sans elle,
    `io/extraction_manifest.verify_extracted_lot` reconstruisait le prefixe et
    le motif de timecode en local pour decider quels fichiers examiner, ce que
    son AC 15 interdit nommement: une seconde ecriture de la convention
    divergerait au premier ajustement de la story 3.1
    (`decisions-2026-08-02.md`, decision 2).

    Ne dit **pas** si le nom appartient au lot: l'appelant reste tenu de
    repasser le timecode a `build_extracted_frame_filename` et de comparer le
    resultat au nom lu. Cette fonction ne fait que la lecture.
    """
    if not name.endswith(suffix):
        raise NamingError(f"'{name}' ne porte pas le suffixe attendu '{suffix}'")
    stem = name[: -len(suffix)]
    _, separator, sanitized_timecode = stem.rpartition("_")
    if not separator:
        raise NamingError(f"'{name}' ne suit pas la convention <rush>_<fps>_<timecode>")
    if not _SANITIZED_TIMECODE_PATTERN.match(sanitized_timecode):
        raise NamingError(f"'{name}' ne porte pas un timecode assaini hh-mm-ss-ff")
    return sanitized_timecode.replace("-", ":")


#: Prefixe des frames **scannees** ecrites sous `frames-scannees/`
#: (story 5.6, vocabulaire tranche par la story 11.14 / `EPIC11-ARB-214`).
#:
#: Le nom de FICHIER, lui, n'a jamais ete faux : `scan_` est deja le mot
#: d'Egan, et c'est ce que le releve de la 11.14 a etabli -- « le seul
#: niveau ou le vocabulaire est faux est celui du dossier, de l'option et
#: du champ de manifeste, pas celui du fichier ». Aucun fichier deja ecrit
#: n'a donc a etre renomme, ce qui est aussi ce qu'`EPIC11-ARB-171` et
#: `EPIC11-ARB-222` exigent.
#:
#: Il distingue une frame **issue d'un scan** d'une frame extraite d'un rush
#: (`extract-frames/`), qui porte la meme forme sans prefixe. Le cout est assume et
#: documente en question ouverte 1 de la story 5.6: deux conventions voisines,
#: donc deux lecteurs a maintenir -- d'ou leur cohabitation **ici**, cote a
#: cote, pour que la divergence se voie en un coup d'oeil plutot que de se
#: decouvrir sur un dossier de sortie introuvable.
SCAN_FRAME_PREFIX = "scan_"


def build_scan_frame_filename(
    rush_id: str,
    fps_target: float | int,
    frame_timecode: str,
    suffix: str = EXTRACTED_FRAME_SUFFIX,
) -> str:
    """Nom d'une frame scannee ecrite sous `frames-scannees/` (story 5.6).

    Forme: `scan_<rush>_<fps-court>_<timecode-assaini>.tiff`, par exemple
    `scan_rush-001_12p5_00-00-00-00.tiff`. C'est **strictement** le motif de
    `build_extracted_frame_filename` prefixe de `SCAN_FRAME_PREFIX`, avec les
    memes briques (`derive_short_id`, `format_fps_short`, `sanitize_timecode`,
    `EXTRACTED_FRAME_SUFFIX`): aucune seconde recette de nommage n'est ecrite,
    ni pour la cadence, ni pour le timecode, ni pour le raccourcissement.

    **Perimetre de `derive_short_id`**: il s'applique au seul `rush_id`, jamais
    a `<rush>_<fps>`. Au-dela de `CANONICAL_ID_MAX_LENGTH` caracteres de
    `rush_id`, le nom de fichier porte donc le derive court alors que le nom de
    dossier (`project_layout.rush_dir_slug`) porte le `rush_id` entier. C'est le
    comportement deja en place cote `extract-frames/`; il est reproduit tel quel et non
    corrige ici, une correction faisant diverger les deux conventions.

    Le nom est le **seul** support d'identite d'un fichier de sortie qui voyage
    seul, sans manifest partage: il doit etre reconstructible depuis le payload
    QR de sa page et rien d'autre (story 5.6, AC 1).
    """
    if not rush_id:
        raise NamingError(
            "Cannot build a scan frame filename from an empty rush_id"
        )
    short_rush_id = derive_short_id(rush_id)
    fps_short = format_fps_short(fps_target)
    sanitized_timecode = sanitize_timecode(frame_timecode)
    return f"{SCAN_FRAME_PREFIX}{short_rush_id}_{fps_short}_{sanitized_timecode}{suffix}"


def read_scan_frame_timecode(
    name: str, suffix: str = EXTRACTED_FRAME_SUFFIX
) -> str:
    """Rendre le timecode porte par un nom de frame scannee, ou echouer.

    Inverse de `build_scan_frame_filename`, et **seul** endroit ou la forme
    `scan_<rush>_<fps-court>_<timecode-assaini>.tiff` est relue. Le prefixe est
    exige: sans lui, un nom de frame extraite (`extract-frames/`) serait accepte
    ici, et
    la verification de conformite du dossier de sortie (story 5.6, AC 7)
    declarerait conforme un fichier qui n'appartient pas a cette convention.

    Ne dit **pas** si le nom appartient au lot: l'appelant reste tenu de
    repasser le timecode a `build_scan_frame_filename` et de comparer le
    resultat au nom lu -- exactement le contrat de
    `read_extracted_frame_timecode`, dont ce lecteur est le jumeau.
    """
    if not isinstance(name, str):
        raise NamingError(
            f"Nom de frame scannee invalide: {name!r}. Une chaine est attendue."
        )
    if not name.startswith(SCAN_FRAME_PREFIX):
        raise NamingError(
            f"'{name}' ne porte pas le prefixe attendu '{SCAN_FRAME_PREFIX}' des "
            "frames scannees (story 5.6)"
        )
    if not name.endswith(suffix):
        raise NamingError(f"'{name}' ne porte pas le suffixe attendu '{suffix}'")
    stem = name[len(SCAN_FRAME_PREFIX) : -len(suffix)]
    _, separator, sanitized_timecode = stem.rpartition("_")
    if not separator:
        raise NamingError(
            f"'{name}' ne suit pas la convention scan_<rush>_<fps>_<timecode>"
        )
    if not _SANITIZED_TIMECODE_PATTERN.match(sanitized_timecode):
        raise NamingError(f"'{name}' ne porte pas un timecode assaini hh-mm-ss-ff")
    return sanitized_timecode.replace("-", ":")


#: Longueur de l'abreviation d'orientation portee par le nom d'un tirage
#: (`EPIC11-ARB-171`). Elle n'est pas une table -- `portrait` et `paysage`
#: rendent `por` et `pay` par TRONCATURE de l'orientation du gabarit, si bien
#: qu'un vocabulaire d'orientations qui changerait changerait le nom avec lui.
#: La contrepartie est une collision possible entre deux orientations qui
#: partageraient leurs trois premieres lettres : c'est une frontiere negative du
#: banc `test_nommage_des_tirages.py` qui la mesure, pas un commentaire.
ORIENTATION_ABBREV_LENGTH = 3

#: Marqueur de la forme d'AVANT `EPIC11-ARB-171` : `<projet>_<lot>_planches.pdf`.
#: Il n'est plus JAMAIS ecrit -- il est seulement RECONNU, pour que les tirages
#: deja poses sur un disque continuent de consommer leur rang.
LEGACY_SHEETS_MARKER = "planches"


def sheets_layout_fragment(template_id: str) -> str:
    """Le fragment de mise en page d'un nom de tirage: `8f-pay`, `4f-por`.

    **Il est DERIVE du `template_id`, jamais compose a part** (`EPIC11-ARB-171`,
    AC 2.9a). Le cardinal et l'orientation sont lus dans le registre des
    gabarits -- `page_templates.get_template(...)` --, et non redecoupes de la
    chaine : re-deriver ici la grammaire `tpl-a4-<ori>-<N>f[-m<marge>]-<version>`
    serait recopier une convention dont `page_templates` est proprietaire, ce
    que la mesure du 2026-09-02 ecarte nommement dans l'autre sens (« parser les
    noms presents re-deriverait une convention que `io/naming.py` possede »).

    **Deux conventions coexistent, et c'est assume** (AC 2.9b) : le gabarit
    ecrit l'orientation PUIS le cardinal (`paysage-6f`), le nom de fichier ecrit
    le cardinal PUIS l'orientation abregee (`6f-pay`). `build_template_id` fixe
    la premiere et rien ne la change ; la seconde est celle des maquettes.

    **Ce que le fragment NE porte pas**, dit plutot que tu : ni le preset de
    marge, ni la version de geometrie. Deux gabarits qui ne different que par
    l'un ou l'autre rendent donc le meme fragment. Ce n'est pas une collision de
    fichiers -- le rang, qui se compte par lot (`EPIC11-ARB-175`), avance a
    chaque tirage et distingue les deux noms --, c'est une information que le
    nom seul ne rend pas. Routee en dette plutot que tranchee ici.
    """
    # Import LOCAL, et le motif n'est pas la cyclicite: `page_templates` est une
    # feuille qui n'importe rien du paquet. Il est de ne pas trainer le registre
    # des 63 gabarits -- construit a l'import -- dans tous les consommateurs de
    # `io.naming`, dont la TUI qui n'en lit que `CANONICAL_ID_MAX_LENGTH`.
    from ..page_templates import UnknownTemplateError, get_template

    if not isinstance(template_id, str) or not template_id:
        raise NamingError(
            "Cannot build a sheets PDF filename without a template_id "
            f"(template_id={template_id!r}). C'est lui qui porte la mise en "
            "page, et le nom d'un tirage la porte depuis `EPIC11-ARB-171`."
        )
    try:
        spec = get_template(template_id)
    except UnknownTemplateError as erreur:
        # Traduit en `NamingError` a dessein: les appelants qui BALAIENT des
        # gabarits (`pdf_composition._rangs_sur_le_disque`) n'attrapent que
        # celle-la, et un refus qui leur echapperait ferait disparaitre les
        # tirages des autres formes -- exactement le mode de panne que
        # `EPIC11-ARB-175` (consequence 2) existe pour fermer.
        raise NamingError(str(erreur)) from None
    abrege = spec.orientation[:ORIENTATION_ABBREV_LENGTH]
    return f"{spec.frames_per_page}f-{abrege}"


def legacy_sheets_pdf_filename(
    project_id: str,
    rush_id: str,
    lot_id: str,
    version_rank: int | None = None,
) -> str:
    """La forme d'AVANT `EPIC11-ARB-171`, RECONNUE et jamais ecrite.

    Elle existe pour une raison mesuree : un tirage deja pose sur le disque a
    **consomme son rang**, et l'ignorer ferait re-attribuer ce rang a une
    planche neuve -- deux feuilles PAPIER portant le meme « tirage N », ce
    qu'`EPIC11-ARB-92` interdit et qu'aucun fichier ne rattrape une fois
    l'encre seche. Aucun fichier deja ecrit n'est renomme (portee tranchee par
    Egan sur `EPIC11-ARB-91`), donc l'ancienne forme reste lisible.

    Aucun chemin d'ECRITURE ne l'appelle : `build_sheets_pdf_filename` est le
    seul producteur de noms de tirages.
    """
    _refuser_identifiants_de_tirage_vides(project_id, rush_id, lot_id)
    short_project_id = derive_short_id(project_id)
    suffixe = "" if version_rank is None else format_version_suffix(version_rank)
    return f"{short_project_id}_{lot_id}_{LEGACY_SHEETS_MARKER}{suffixe}.pdf"


def _refuser_identifiants_de_tirage_vides(
    project_id: str, rush_id: str, lot_id: str
) -> None:
    """Garde commune aux deux formes de nom de tirage, ecrite une seule fois."""
    if not project_id or not rush_id or not lot_id:
        raise NamingError(
            "Cannot build a sheets PDF filename from empty identifiers "
            f"(project_id={project_id!r}, rush_id={rush_id!r}, lot_id={lot_id!r})"
        )


def build_sheets_pdf_filename(
    project_id: str,
    rush_id: str,
    lot_id: str,
    version_rank: int | None = None,
    *,
    template_id: str,
) -> str:
    """Nom du PDF de planches d'un lot (story 4.1, EPIC4-ARB-3).

    Layout: `<projet>_<lot>_<Nf-ori>[_vN].pdf`. `project_id` passe par
    `derive_short_id` comme dans `build_frame_filename`; `lot_id` est repris
    verbatim car il est deja une forme courte -- `build_lot_id` le produit par
    `derive_short_id`, et le schema v2 borne son alphabet. Le fichier sort sous
    `planches/` (`EPIC11-ARB-225`; migration `pdf/` au backlog).

    **Le `rush_id` n'entre PAS dans le nom** (`EPIC7-ARB-91`, 2026-08-27). Il y
    figurait jusqu'ici entre le projet et le lot, alors que `build_lot_id`
    construit precisement `lot_id` comme `<rush_id>_<cadence-courte>` : le nom
    portait donc le rush deux fois de suite, ce qui donnait sur un rush au nom
    parlant `projet_demo_planche_4f_heteroclite_planche_4f_heteroclite_4_planches.pdf`
    la ou `projet_demo_planche_4f_heteroclite_4_planches.pdf` dit strictement
    la meme chose. Aucune information de reconstruction n'est perdue -- le
    rush et la cadence restent lisibles **dans** le fragment `lot_id`, avec le
    decoupage que `build_lot_id` fixe.

    **`version_rank` est le rang de version de la PLANCHE**
    (`EPIC11-ARB-91`, 2026-08-31), et il ne se confond pas avec celui du lot :
    un lot versionne porte deja son rang dans son `lot_id`, donc dans ce nom.
    Celui-ci compte les reimpressions du MEME lot apres un reglage change.

    Il ne suffit pas a lui seul, et c'est ce qui distingue la planche du lot ou
    du master : **une planche imprimee a quitte le disque**. Un nom de fichier
    ne protege pas une feuille posee sur un bureau. Le rang doit donc atteindre
    AUSSI l'en-tete imprime et le payload QR -- c'est ce qu'Egan a tranche, et
    sans quoi versionner une planche serait une precaution qui s'arrete au
    moment ou elle deviendrait utile.

    Le parametre `rush_id` est **conserve a la signature** et reste valide :
    tous les appelants l'ont sous la main, il documente l'appartenance du lot,
    et le retirer casserait les appels nommes sans rien gagner. Aucun fichier
    deja ecrit n'est renomme (portee tranchee par Egan) -- c'est
    `legacy_sheets_pdf_filename` qui continue de les RECONNAITRE.

    **Le mot `planches` a disparu du nom** (`EPIC11-ARB-171`, retour A4 d'Egan,
    2026-09-02). Il ne portait aucune information -- tous les fichiers de ce
    dossier sont des planches -- alors que deux mises en page du MEME lot
    rendaient le meme nom, ce qui rendait le motif du conflit opaque : « ce
    tirage existe deja » sans dire que c'est une autre forme. La place qu'il
    occupait porte desormais la mise en page, et le nom n'a pas grandi (mesure
    sur l'exemple des maquettes : 38 caracteres avant, 36 apres).

    **`template_id` est NOMME et obligatoire.** Positionnel, il se serait glisse
    a la place de `version_rank` chez un appelant distrait, et le nom serait
    sorti sans bruit avec une mise en page fausse.

    **Aucune garde de longueur n'est posee ici** (AC 2.9e), et c'est delibere :
    la fonction n'en avait aucune, `CANONICAL_ID_MAX_LENGTH` ne l'a jamais
    bornee -- `project_id` y passe deja par `derive_short_id`, `lot_id` est
    repris verbatim --, et en poser une serait un arbitrage neuf que personne
    n'a demande. La borne reelle est celle du systeme de fichiers (255 octets
    par composant sur ext4), que ce module ne connait pas et qui etait deja
    franchissable avant cet arbitrage ; elle est routee en dette.
    """
    _refuser_identifiants_de_tirage_vides(project_id, rush_id, lot_id)
    fragment = sheets_layout_fragment(template_id)
    short_project_id = derive_short_id(project_id)
    # Le rang vient APRES le fragment de mise en page, et le motif est mesure
    # plutot que d'ecole. La premiere redaction le placait avant, en raisonnant
    # sur la lecture (« version 2 du lot de planches »). Essai fait: un lot deja
    # versionne donnait `demo_R_24_v3_v2_planches.pdf` -- DEUX fragments `_vN`
    # colles, ou ni l'oeil ni une analyse ne peuvent dire lequel est le rang du
    # lot et lequel celui de la planche.
    #
    # `build_master_filename` ne rencontre pas ce probleme pour une raison
    # precise: le marqueur `_mmu_` SEPARE les deux rangs
    # (`L_24_v2_mmu_prores_422_v3.mov`). Le fragment de mise en page joue ce
    # role de marqueur ici, exactement comme `_planches` le jouait avant
    # `EPIC11-ARB-171` -- une seule regle pour les deux noms, et non deux.
    if version_rank is not None:
        return (f"{short_project_id}_{lot_id}_{fragment}"
                f"{format_version_suffix(version_rank)}.pdf")
    return f"{short_project_id}_{lot_id}_{fragment}.pdf"


#: Longueur du fragment **lisible** du libelle de chaine conserve dans le nom du
#: PDF de page de calibration (story 5.23).
#:
#: Le libelle est de la prose saisie par l'operateur (« hp envy 4520 tiff 600 dpi
#: auto corr off »): il ne peut pas entrer verbatim dans un nom de fichier, et il
#: n'a pas de forme canonique. Le fragment sert donc a **reconnaitre** le fichier a
#: l'oeil dans `planches/`; c'est le condensat qui, lui, porte l'identite.
SCAN_CHAIN_SLUG_MAX_LENGTH = 40


def scan_chain_suffix(scan_chain_label: str) -> str:
    """Condensat identifiant un **libelle de chaine de scan** (story 5.23).

    Meme recette que :func:`bounds_suffix`, au caractere: `hashlib.sha256` du
    materiau brut, tronque a :data:`BOUNDS_SUFFIX_LENGTH` caracteres hexadecimaux.
    Deterministe et inter-machine -- jamais le `hash()` randomise de Python, jamais
    une horodate.

    **Pourquoi un condensat et pas seulement un slug**, et c'est la classe de defaut
    la plus payee du depot: `normalize_identifier` est **non injective**. « hp envy »,
    « hp-envy » et « hp  envy » rendent le meme slug `hp-envy`, donc trois chaines de
    scan distinctes ecriraient le meme fichier et la derniere ecraserait les autres
    en silence. Le condensat est calcule sur le libelle **brut**, avant toute
    normalisation, ce qui est la seule facon de faire porter l'identite par ce qui
    distingue reellement deux chaines.

    Il n'est pas non plus `derive_short_id`: celle-ci rend son entree *inchangee*
    sous `CANONICAL_ID_MAX_LENGTH` caracteres -- c'est un raccourcisseur
    conditionnel, pas un hacheur --, donc elle ne condenserait rien sur un libelle
    court et ne separerait pas deux libelles qui se normalisent pareil.
    """
    if not scan_chain_label:
        raise NamingError(
            "Cannot derive a scan chain suffix from an empty label: une page de "
            "calibration anonyme ne se distinguerait pas d'une autre."
        )
    return hashlib.sha256(
        scan_chain_label.encode("utf-8")).hexdigest()[:BOUNDS_SUFFIX_LENGTH]


#: La queue fixe du nom d'un PDF de page de calibration.
#:
#: Elle est **nommee** depuis le 2026-09-02 parce qu'un appelant la recopiait :
#: `tui/atelier_pdf_calibration.queue_du_nom` composait `_calibration.pdf` en
#: litteral, et la frontiere de l'AC 2.8 le voyait -- « un ecran a le droit
#: d'AFFICHER un nom que le manifeste lui donne ; il n'a pas le droit d'en
#: COMPOSER un ». Le geste est celui qu'`EPIC11-ARB-181` a tranche le meme jour
#: pour `RANG_ORIGINE` : la valeur vit ici, l'appelant la nomme, personne ne la
#: recopie.
CALIBRATION_PDF_SUFFIX = "_calibration.pdf"


def build_calibration_pdf_filename(project_id: str, scan_chain_label: str) -> str:
    """Nom du PDF de la **page de calibration** d'une chaine de scan.

    Layout: `<projet>_<chaine>-<condensat>_calibration.pdf`, meme recette
    d'abreviation de projet que `build_sheets_pdf_filename` et meme dossier de
    sortie (`planches/`).

    **Ni rush, ni lot dans ce nom** (story 5.23, AC 8bis, `EPIC5-ARB-82`). Le layout
    de 5.22 etait `<projet>_<rush>_<lot>_calibration.pdf`, reste du regime **par
    lot** de 5.16 ou cette page etait la page 0 d'un lot. Depuis `EPIC5-ARB-80` elle
    sert **toute une chaine de scan** -- tous les lots, tous les rushes, toutes les
    cadences -- et une page nommee d'un rush est fausse au sens propre.

    **Mais un projet en porte AUTANT que de chaines de scan**, et c'est la correction
    d'Egan du 2026-08-18: le layout intermediaire `<projet>_calibration.pdf` n'en
    autorisait qu'**une**, donc calibrer une seconde chaine dans le meme projet
    aurait exige d'ecraser la premiere. Le nom porte donc **le projet et la chaine**.

    Le libelle etant libre et verbeux, il est reduit en deux morceaux qui ne jouent
    pas le meme role: un **slug lisible** tronque a
    :data:`SCAN_CHAIN_SLUG_MAX_LENGTH`, pour reconnaitre le fichier a l'oeil, et le
    **condensat** de :func:`scan_chain_suffix`, qui porte l'identite. Deux libelles
    differents rendent donc deux noms differents, y compris quand ils se normalisent
    en un meme slug -- c'est le condensat, calcule sur le libelle brut, qui les
    separe (voir `scan_chain_suffix`).

    Le suffixe reste **different** de `_planches`: la page de calibration coexiste
    avec le PDF de planches dans le meme dossier, et un nom partage aurait fait
    ecraser l'un par l'autre en silence.
    """
    if not project_id:
        raise NamingError(
            "Cannot build a calibration PDF filename from an empty project_id "
            f"(project_id={project_id!r})"
        )
    suffix = scan_chain_suffix(scan_chain_label)
    try:
        slug = normalize_identifier(scan_chain_label, label="scan_chain_label")
    except NamingError as exc:
        # Un libelle qui ne contient **aucun** caractere alphanumerique ASCII
        # (« --- », « !!! ») ne laisse aucun fragment lisible. Le condensat suffirait a
        # nommer le fichier, mais un nom que rien ne rattache a l'oeil a une chaine est
        # exactement ce que le fragment lisible existe pour eviter: on refuse, en
        # parlant du libelle et non d'un fichier source.
        raise NamingError(
            f"Libelle de chaine de scan inutilisable pour nommer un fichier: "
            f"{scan_chain_label!r}. Il doit porter au moins un caractere "
            f"alphanumerique ASCII ({exc})"
        ) from exc
    slug = slug[:SCAN_CHAIN_SLUG_MAX_LENGTH]
    # `normalize_identifier` peut rendre un slug termine par un tiret apres la
    # troncature; le laisser produirait `...-` colle au condensat, illisible.
    slug = slug.rstrip("-") or "chaine"
    return f"{derive_short_id(project_id)}_{slug}-{suffix}{CALIBRATION_PDF_SUFFIX}"


#: Marqueur de fabrique insere dans le nom d'un master video (story 6.1).
#:
#: Il distingue un fichier produit par cet outil d'un rush d'origine depose dans
#: le meme dossier, et il ne collisionne avec aucun `profile_id` du catalogue
#: (verifie sur les sept). `grep "_mmu_"` rendait zero occurrence avant cette
#: story: la recette de nom de master n'existait nulle part.
MASTER_FILENAME_MARKER = "_mmu_"


def build_master_filename(
    *,
    lot_id: str,
    profile_id: str,
    container: str,
    resolution_segment: str | None = None,
    version_rank: int | None = None,
) -> str:
    """Nom du master video d'un lot (story 6.1, AC 12).

    Forme: `<lot_id>_mmu_<profile_id>[_<resolution>].<conteneur>`, par exemple
    `TEST_FILE_12p5_mmu_prores_hq.mov`. Motif repris de
    `build_sheets_pdf_filename`: le `lot_id` est pris **verbatim**, car il est
    deja une forme courte -- `build_lot_id` le produit par `derive_short_id` et
    le schema v2 borne son alphabet.

    Le nom porte le **lot** et non le rush: deux lots du meme rush a deux
    cadences sont le cas nominal depuis la v2.1, et un nom fonde sur le rush
    ferait porter le meme nom a deux masters differents.

    **`version_rank` est le rang du MASTER, distinct du rang du LOT**
    (`EPIC11-ARB-91`, 2026-08-31). La distinction est facile a manquer : un
    lot versionne porte deja `_v2` dans son `lot_id`, donc son master s'appelle
    deja `rushA_24_v2_mmu_prores_422.mov` sans que ce parametre existe. Ce
    parametre-ci sert au cas different et frequent : **re-encoder le MEME lot
    au MEME profil** apres un reglage change, sans creer un lot. Sans lui, la
    seule issue face au master deja present etait `--overwrite`, c'est-a-dire
    l'issue unique qu'`EPIC11-ARB-89` interdit.

    Verbatim d'Egan qui a tranche que la convention s'y transpose : « le nom
    d'un master, si je ne m'abuse, porte le codec ? Non ? Donc le v2 indique
    qu'il s'agit d'une nouvelle version du meme codec non ? » -- exact, et
    c'est ce qui rend le suffixe univoque ici : profil ET resolution etant
    deja dans le nom, un `_v2` ne peut designer qu'une nouvelle version du
    meme profil a la meme resolution.

    `resolution_segment` n'apparait **que** lorsque la resolution n'est pas le
    defaut: sans lui, les deux sorties possibles d'un meme lot au meme profil
    (defaut et native) porteraient le meme nom. Sa valeur est decidee par
    `encode.resolution_name_segment` -- identifiant du registre pour une entree
    nommee, `<largeur>x<hauteur>` pour une resolution personnalisee -- et n'est
    pas recalculee ici: ce module nomme, il ne decide pas.
    """
    if not lot_id or not profile_id or not container:
        raise NamingError(
            "Cannot build a master filename from empty identifiers "
            f"(lot_id={lot_id!r}, profile_id={profile_id!r}, container={container!r})"
        )
    stem = f"{lot_id}{MASTER_FILENAME_MARKER}{profile_id}"
    if resolution_segment:
        stem = f"{stem}_{resolution_segment}"
    # Le rang de version vient EN DERNIER, apres le profil et la resolution
    # -- meme ordre que pour un lot (cadence, puis bornes, puis version,
    # `EPIC11-ARB-88`). Ce n'est pas une preference d'ecriture : les deux
    # fragments qui precedent sont ceux qui DISTINGUENT deux masters d'un
    # meme lot, et un rang glisse entre eux ferait varier le prefixe commun
    # de deux sorties du meme profil.
    if version_rank is not None:
        stem = f"{stem}{format_version_suffix(version_rank)}"
    return f"{stem}.{container}"


def build_frame_filename(
    *,
    project_id: str,
    rush_id: str,
    lot_id: str,
    page_index: int,
    frame_timecode: str,
    fps_target: float,
    slot_index: int | None = None,
    suffix: str = ".png",
) -> str:
    """Build a deterministic, stable frame filename per the story 2.3 convention.

    Layout: `{project_id}_{lot_id}_p{page_index}_[s{slot_index}_]tc{timecode}{suffix}`
    `project_id` is shortened via `derive_short_id` when it exceeds
    `CANONICAL_ID_MAX_LENGTH`.

    **Ni le rush ni la cadence n'entrent dans le nom** (`EPIC7-ARB-91`,
    2026-08-27). Ce nom en portait **deux** repetitions, pas une :
    `build_lot_id` construit `lot_id` comme `<rush_id>_<cadence-courte>`, si
    bien que `<projet>_<rush>_<lot>_..._fps<cadence>` ecrivait le rush deux
    fois et la cadence deux fois. Un lot `TEST_FILE_12p5` donnait
    `projet_demo_TEST_FILE_TEST_FILE_12p5_p001_tc00-00-00-00_fps12p5.png`
    la ou `projet_demo_TEST_FILE_12p5_p001_tc00-00-00-00.png` dit exactement
    la meme chose.

    **Le contrat de reconstruction de la story 2.3 tient inchange** : projet,
    rush, lot, page et emplacement restent tous lisibles du seul nom de
    fichier. Le rush et la cadence se lisent **dans** le fragment `lot_id`,
    selon le decoupage que `build_lot_id` fixe -- ils ne sont pas devines.

    Les parametres `rush_id` et `fps_target` sont **conserves a la signature**
    et restent valides : ils identifient le lot chez tous les appelants et
    leur retrait casserait des appels nommes sans rien gagner. Aucun fichier
    deja ecrit n'est renomme (portee tranchee par Egan).

    A ne pas confondre avec `build_extracted_frame_filename` et
    `build_scan_frame_filename` : ces deux-la ne portent **pas** de `lot_id`,
    donc ne repetaient rien, et restent strictement inchangees.
    """
    short_project_id = derive_short_id(project_id)
    sanitized_timecode = sanitize_timecode(frame_timecode)

    components = [short_project_id, lot_id, f"p{page_index + 1:03d}"]
    if slot_index is not None:
        components.append(f"s{slot_index:02d}")
    components.append(f"tc{sanitized_timecode}")

    return "_".join(components) + suffix


# ===========================================================================
# Relire un nom : les DECOMPOSEURS, a cote de leurs fabriques
# ===========================================================================
#
# **Pourquoi ces deux fonctions vivent ICI et non dans l'ecran qui les
# emploie.** Elles ont ete ecrites dans `tui/projet_inventaire.py` et
# `tui/projet_suppression.py` par la story 11.11, et c'est une frontiere du
# depot qui a dit que c'etait faux :
# `test_versionnage_du_scan_en_tui.py::test_AUCUN_module_de_la_TUI_ne_redige_une_regle_de_RANG`
# compte a **zero** le vocabulaire des rangs dans `tui/`, prose comprise.
#
# La frontiere avait raison, et la premiere redaction se contredisait
# elle-meme : sa propre docstring citait « l'inverse exact de
# `format_version_suffix`, et il vit a cote d'elle pour la meme raison que la
# regle des rangs vit une seule fois » -- puis la posait ailleurs. Un
# decomposeur loge loin de sa fabrique est exactement la seconde convention que
# ce module existe pour empecher (`EPIC11-ARB-108`, « il n'y a pas de mecanisme
# different par objet »).


def tige_et_rang(nom: str) -> tuple[str, int]:
    """`("plan-04_12p5", 2)` pour `plan-04_12p5_v2` -- par les DEUX fonctions
    du depot, jamais par une expression ecrite ailleurs.

    :func:`rang_du_fragment_de_version` lit le rang et
    :func:`format_version_suffix` rend le fragment a retirer. Une troisieme
    expression reguliere sur la forme `_vN` serait la seconde convention que ce
    module existe pour empecher.

    Un nom sans fragment rend `(nom, 1)` : le rang d'origine n'en porte aucun,
    et son absence le dit. La garde se lit sur `VERSION_RANK_MIN` plutot que
    sur `version_ranks.RANG_ORIGINE` pour ne pas faire dependre `io.naming` de
    `io.version_ranks` -- les deux bornes disent ici la meme chose, et
    `format_version_suffix` **refuse nommement** d'ecrire un fragment sous
    `VERSION_RANK_MIN` : appeler `len()` sur son refus serait une panne.
    """
    rang = rang_du_fragment_de_version(nom)
    if rang < VERSION_RANK_MIN:
        return nom, rang
    return nom[:-len(format_version_suffix(rang))], rang


@dataclass(frozen=True)
class ProfilDuMaster:
    """Ce qu'un nom de master dit de lui-meme : profil, resolution, rang."""

    profil: str
    resolution: str | None = None
    rang: int = 1


def profil_du_master(nom: str, lot_id: str) -> ProfilDuMaster | None:
    """Relire le profil dans le nom d'un master. Rend ``None`` si le nom ne le dit pas.

    **Ce n'est pas une decomposition de nom par ressemblance**, et la
    distinction est tout le sujet -- le depot refuse partout ailleurs de
    deviner une filiation en decoupant un identifiant. Ici, trois choses
    rendent la lecture EXACTE :

    1. **le `lot_id` est connu**, il n'est pas devine. C'est le contexte que
       `EPIC11-ARB-224` impose deja aux cinq cibles fines, et il est lu du
       noeud PARENT dans l'arbre. Le prefixe se retire donc par egalite, jamais
       par une expression reguliere qui « trouverait » un lot dans un nom ;
    2. **`MASTER_FILENAME_MARKER` est un separateur ecrit par le depot**
       (`_mmu_`), pas une convention supposee : c'est litteralement ce que
       :func:`build_master_filename` interpose entre le lot et le profil ;
    3. **`codec_profiles.PROFILES` est un registre FERME** de sept
       identifiants -- celui-la meme dont :func:`build_master_filename` a
       recopie le `profile_id`. On ne lit donc pas « ce qui ressemble a un
       profil », on reconnait un membre d'un ensemble fini. Un nom qui n'en
       nomme aucun rend ``None`` plutot qu'une valeur plausible.

    **La reconnaissance s'arrete sur une FRONTIERE, et c'est la seule garde.**
    `dnxhr_hq` est un prefixe strict de `dnxhr_hqx` : un `startswith` naif
    lirait `dnxhr_hq` dans `dnxhr_hqx_uhd` et designerait le master d'un AUTRE
    profil. Le candidat doit donc s'arreter sur une fin de chaine ou sur un `_`,
    qui est le seul separateur que :func:`build_master_filename` emploie.

    **Une seconde garde a ete RETIREE, et c'est la campagne de mutation qui l'a
    demande.** Le tri par longueur decroissante -- essayer `dnxhr_hqx` avant
    `dnxhr_hq` -- rendait le meme resultat, et les deux gardes se masquaient
    mutuellement : chacune tuait le mutant de l'autre, si bien qu'**aucune des
    deux n'etait individuellement mesurable**. Deux mutants ont survecu a la
    campagne pour cette seule raison. Retirer la redondance ne perd rien -- la
    frontiere de separateur suffit, mesuree sur les sept profils du registre --
    et rend la garde restante mortelle : le mutant `startswith(profil)` meurt
    desormais.

    **Ce que ce nom NE tranche PAS, dit plutot que tu.** Le coeur arbitre sur le
    MANIFESTE, pas sur le nom : devant un master renomme a la main, il REFUSE
    au lieu de choisir, et aucun inode ne bouge. C'est ce qui rend cette lecture
    sure plutot que dangereuse -- elle propose une cible, elle ne l'impose pas.

    Ecrit sur demande d'Egan du 2026-09-05 (« il faut resoudre le probleme du
    "profile". Il est contenu dans le nom du master »), apres une premiere
    redaction qui renoncait a le lire.
    """
    from .. import codec_profiles

    # **Un `lot_id` VIDE n'est pas un lot connu** (finding `C2-10` de la couche
    # 2). Sans cette garde, `profil_du_master('_mmu_prores_hq.mov', '')` rend
    # `ProfilDuMaster('prores_hq', None, 1)` : le prefixe `"" + "_mmu_"` matche,
    # et la fonction lit un profil sans avoir jamais retire de lot. C'est
    # exactement ce que le point 1 ci-dessus interdit -- le prefixe se retire
    # par egalite avec un lot CONNU --, et la garde etait asymetrique :
    # `cible_du_noeud` ne repoussait que `lot_id is None`.
    if not lot_id:
        return None
    point = nom.rfind(".")
    tige = nom[:point] if point > 0 else nom
    prefixe = f"{lot_id}{MASTER_FILENAME_MARKER}"
    if not tige.startswith(prefixe):
        return None
    reste, rang = tige_et_rang(tige[len(prefixe):])
    if not reste:
        return None
    for profil in sorted(codec_profiles.PROFILES):
        if reste == profil:
            return ProfilDuMaster(profil, None, rang)
        if reste.startswith(f"{profil}_"):
            return ProfilDuMaster(profil, reste[len(profil) + 1:] or None, rang)
    return None


def nom_de_version(tige: str, rang: int) -> str:
    """`("plan-04_25", 2)` rend `plan-04_25_v2` -- l'inverse de :func:`tige_et_rang`.

    Elle existe pour que personne n'ait a ecrire la concatenation ailleurs. Un
    `f"{tige}_v{rang}"` compose a la main serait la seconde convention que ce
    module existe pour empecher, et il ne passerait par aucune des gardes de
    :func:`format_version_suffix` -- ni la borne haute, ni le refus nomme du
    rang d'origine.
    """
    return f"{tige}{format_version_suffix(rang)}"


#: Ce qu'un suffixe doit avoir pour compter comme une EXTENSION de fichier.
#:
#: Une borne plutot qu'un registre : `mov`, `mxf`, `pdf`, `tiff`, `png` sont
#: les extensions que ce depot produit aujourd'hui, mais en fermer la liste
#: ferait echouer la decomposition sur la premiere extension neuve -- et
#: echouer en silence, par un orphelin qui part en queue. La borne, elle, ne
#: connait rien du contenu : un suffixe court et purement alphanumerique est
#: une extension, `_v2` et `12p5` n'en sont pas.
LONGUEUR_MAX_D_EXTENSION = 8


def _coupe_l_extension(nom: str) -> tuple[str, str]:
    """`("a_v2", ".mov")` pour `a_v2.mov` ; `(nom, "")` quand il n'y en a pas."""
    point = nom.rfind(".")
    if point <= 0:
        return nom, ""
    suffixe = nom[point + 1:]
    if not suffixe.isalnum() or len(suffixe) > LONGUEUR_MAX_D_EXTENSION:
        return nom, ""
    return nom[:point], nom[point:]


def tige_et_rang_de_fichier(nom: str) -> tuple[str, int]:
    """Comme :func:`tige_et_rang`, mais le rang est AVANT l'extension.

    **Et sans elle, la greffe de version ne marchait NI pour un master NI pour
    une planche** -- trouve par la couche 2 de la revue de la story 11.11
    (finding `C2-1`), mesure :

    ```
    tige_et_rang('plan-04_25_mmu_prores_hq_v2.mov')
      -> ('plan-04_25_mmu_prores_hq_v2.mov', 1)   # le nom INTACT
    ```

    `build_master_filename` pose le fragment de version **avant** l'extension
    -- c'est la seule place ou il puisse aller, un fichier gardant son
    extension en queue --, tandis que :func:`tige_et_rang` lit le fragment en
    **fin de nom**. Les deux ont raison chacune de son cote ; ce qui manquait
    est la fonction qui les accorde. Les deux entrees `NATURE_MASTER` et
    `NATURE_PLANCHE` du registre des ancres de l'ecran d'inventaire etaient
    donc MORTES : aucune version de master ni de planche ne se greffait, et
    elles partaient toutes en queue d'arbre.

    La tige rendue **garde son extension** : c'est le nom du fichier
    d'ORIGINE, donc celui du noeud declare a cote duquel la version se pose.
    `('plan-04_25_mmu_prores_hq.mov', 2)` pour l'exemple ci-dessus.

    Un nom sans extension retombe exactement sur :func:`tige_et_rang` -- un
    lot, un scan et un rush n'en ont pas, et rien ne change pour eux.
    """
    tige, extension = _coupe_l_extension(nom)
    if not extension:
        return tige_et_rang(nom)
    sans_rang, rang = tige_et_rang(tige)
    return f"{sans_rang}{extension}", rang


def nom_de_version_de_fichier(nom: str, rang: int) -> str:
    """L'inverse EXACT de :func:`tige_et_rang_de_fichier`.

    `("plan-04_25_mmu_prores_hq.mov", 2)` rend
    `plan-04_25_mmu_prores_hq_v2.mov`, la ou :func:`nom_de_version` rendrait
    `plan-04_25_mmu_prores_hq.mov_v2` -- un nom que rien ne sait relire, et
    qu'aucun lecteur de fichiers ne reconnaitrait comme un `.mov`.

    Les deux fonctions vont par paire : decomposer d'un cote et recomposer de
    l'autre avec des regles differentes est exactement la divergence que ce
    module existe pour empecher.
    """
    tige, extension = _coupe_l_extension(nom)
    if not extension:
        return nom_de_version(nom, rang)
    return f"{nom_de_version(tige, rang)}{extension}"


def est_un_rang_de_version(rang: int | None) -> bool:
    """Ce rang designe-t-il une VERSION, ou l'origine (ou rien) ?

    Elle existe pour que ses appelants n'aient pas a ecrire `rang > 1`. Ce `1`
    est la regle des rangs -- ecrite a la main, c'est une seconde convention ;
    et un appelant qui l'ecrirait dans `tui/` redigerait une regle de rang dans
    un ecran, ce qu'une frontiere du depot compte a zero.

    ``None`` rend ``False`` : un objet sans rang n'a pas de rang. C'est
    volontairement le meme verdict que le rang d'origine, parce que les deux
    commandent la meme chose a l'appel -- ne transmettre aucune `version=` au
    coeur, qui viserait alors un fragment que rien n'ecrit.
    """
    return rang is not None and rang >= VERSION_RANK_MIN
